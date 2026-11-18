#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Agentic coding battery: does a serve finish real multi-step code work, and how fast?

What it is
----------
Thirteen small repositories in two tiers. The **easy** floor (8 tasks): a failing test to fix, a
cross-file bug, a spec to implement, a duplication refactor, a config migration, a CLI to finish, a
mutable-default bug, a validation boundary. The **hard** ceiling (5 tasks) where engines actually
separate: a four-module helper extraction with an import-cycle check, a bill-split rounding bug
visible only through a repro script, an edge-case parsing table, a socket-stub client that must be
wired and proven end to end, and a golden-output regression. Every task seeds a workspace, gives the
model three tools (`read_file`, `write_file`, `run_shell`) and a bounded turn budget, then grades the
*workspace* with hidden checks the model never sees — deterministic `unittest` / string / AST /
subprocess checks, never a judge model.

Tiers and budgets
-----------------
`--tier easy|hard|all` selects the set (default `all`), and every receipt and `summary.json` records
the tier. Budgets are per task: easy 16 turns / 600 s, hard 24 turns / 900 s; `--max-turns` and
`--wall-clock` override both. Each task also carries a reference patch that `--selftest` applies
offline to prove the checker is satisfiable — evidence that a red cell is the model, not the harness.

Why a new runner rather than an existing tool
---------------------------------------------
`quality-battery.py` is single-turn exact match, `bfcl-eval.py` scores one function call,
`agentic-horizon-probe.py` scores loop degeneration on a synthetic plan/repo sandbox, and
`benchmarking/standard-suite.yaml` (tool-eval-bench) is an external pinned uvx whose scenarios
see no repository. None of them patches a file and runs that file's tests, which is the shape
this lane needs.

Engine contract
---------------
One base URL, one served model name, an optional API key from `--api-key-env` (unset means no
Authorization header — the knapcio SGLang serve is keyless). Every request sets `max_tokens` to 4096 unconditionally — one fixed output cap, never the engine's
default or ceiling — so two engines with different defaults are measured on their work, not on their
configuration; the value is recorded in `summary.json`. Requests are non-streaming, so both engines'
tool-call transport collapses to the same shape: picom assembles its streamed
argument deltas and SGLang returns complete `tool_calls` deltas, and both answer with whole
`message.tool_calls`. No delta assembly is needed here; a `length` finish is counted and
reported because it is a harness cap, not a model failure.

Receipts
--------
Per task, under `--outdir`: `<task>.json` (verdict + counters), `<task>.wire.jsonl` (every
request body and response), and the workspace itself. `<outdir>/summary.json` and a printed
table carry median/worst wall seconds — the numbers that size a comparison window. `--resume`
skips tasks that already hold a result, so a window can be re-entered.

Usage
-----
    python3 tools/agentic-battery.py --base-url http://rank0-host:8000 \\
        --model deepseek-ai/DeepSeek-V4.1-Flash-1017 --tier hard

    python3 tools/agentic-battery.py --list
    python3 tools/agentic-battery.py --selftest     # offline: every task red then green

Exit: 0 the run completed (the score is the artifact), 1 no task ran, 2 bad flags/selftest.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

SYSTEM = """You are an autonomous coding agent in a small scratch repository.
You have three tools: read_file(path), write_file(path, content) and run_shell(command).
Paths are relative to the working directory; absolute paths are refused.
Work step by step: read what you need, change code, run the project's tests to verify.
When the work is done and verified, reply with a plain final message and no tool call.
Only edit a test file if the task says the test itself is wrong."""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a UTF-8 text file relative to the working directory.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create or replace a UTF-8 text file relative to the working directory.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_shell",
            "description": "Run a shell command in the working directory; returns exit code, stdout, stderr.",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
        },
    },
]

SHELL_TIMEOUT = 60
READ_LIMIT = 20000
OUT_LIMIT = 8000
# One fixed output cap for every request on every engine: an engine whose default (or ceiling)
# differs would otherwise be measured on its configuration, not its work.
MAX_TOKENS = 4096


def _safe_path(ws: Path, raw: str) -> Path:
    p = Path(raw)
    if p.is_absolute():
        raise ValueError("absolute paths are refused")
    target = (ws / p).resolve()
    if target != ws.resolve() and ws.resolve() not in target.parents:
        raise ValueError("path escapes the workspace")
    return target


def run_tool(ws: Path, name: str, args: dict) -> str:
    """Execute one tool call inside the sandbox; always returns a string for the model."""
    try:
        if name == "read_file":
            target = _safe_path(ws, str(args.get("path", "")))
            data = target.read_text(encoding="utf-8", errors="replace")
            return data[:READ_LIMIT] + ("\n[truncated]" if len(data) > READ_LIMIT else "")
        if name == "write_file":
            target = _safe_path(ws, str(args.get("path", "")))
            target.parent.mkdir(parents=True, exist_ok=True)
            text = str(args.get("content", ""))
            target.write_text(text, encoding="utf-8")
            return f"wrote {len(text)} bytes to {args.get('path')}"
        if name == "run_shell":
            proc = subprocess.run(
                ["bash", "-lc", str(args.get("command", ""))],
                cwd=ws,
                capture_output=True,
                text=True,
                timeout=SHELL_TIMEOUT,
                env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(ws),
                     "LANG": "C.UTF-8"},
            )
            body = (proc.stdout or "") + (proc.stderr or "")
            return f"exit={proc.returncode}\n{body[-OUT_LIMIT:]}"
        return f"error: unknown tool {name!r}"
    except subprocess.TimeoutExpired:
        return f"error: command timed out after {SHELL_TIMEOUT}s"
    except (OSError, ValueError) as exc:
        return f"error: {exc}"


def chat(base_url: str, model: str, api_key: str | None, messages: list, timeout: int) -> dict:
    body = {
        "model": model,
        "messages": messages,
        "tools": TOOLS,
        "tool_choice": "auto",
        "temperature": 0.0,
        "max_tokens": MAX_TOKENS,
        "stream": False,
    }
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(
        base_url.rstrip("/") + "/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def grade(task: dict, ws: Path) -> tuple[bool, list]:
    """Run the task's hidden checks in the finished workspace."""
    checks, ok_all = [], True
    for i, chk in enumerate(task["checks"]):
        if "cmd" in chk:
            cmd = [sys.executable if part == "{python}" else part for part in chk["cmd"]]
        else:
            # In the workspace root, so imports of the task's modules resolve; written after
            # the loop, so the model never sees it.
            path = ws / f"_harness_check_{i}.py"
            path.write_text(chk["script"], encoding="utf-8")
            cmd = [sys.executable, "-B", path.name]
        try:
            proc = subprocess.run(cmd, cwd=ws, capture_output=True, text=True,
                                  timeout=chk.get("timeout", 120))
            ok = proc.returncode == 0
            tail = ((proc.stdout or "") + (proc.stderr or ""))[-800:]
        except subprocess.TimeoutExpired:
            ok, tail = False, f"timed out after {chk.get('timeout', 120)}s"
        checks.append({"name": chk.get("name") or f"check{i}", "ok": ok, "tail": tail})
        ok_all = ok_all and ok
    return ok_all, checks


def seed_workspace(task: dict, ws: Path) -> None:
    """Re-seed a task's workspace from its fixture files (idempotent)."""
    shutil.rmtree(ws, ignore_errors=True)
    ws.mkdir(parents=True, exist_ok=True)
    for rel, content in task["files"].items():
        path = ws / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def run_task(task: dict, base_url: str, model: str, api_key: str | None, root: Path,
             max_turns: int, wall_s: int, outdir: Path, request_timeout: int) -> dict:
    tdir = root / task["id"]
    ws = tdir / "workspace"
    seed_workspace(task, ws)

    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": task["prompt"]}]
    tokens = {"prompt": 0, "completion": 0}
    stats = {"turns": 0, "tool_calls": 0, "invalid_args": 0, "truncated": 0,
             "usage_missing": 0, "finish_reasons": []}
    final_text, timed_out, error = "", False, None
    start = time.time()
    wire = (outdir / f"{task['id']}.wire.jsonl").open("w", encoding="utf-8")
    try:
        for turn in range(max_turns):
            if time.time() - start > wall_s:
                timed_out = True
                break
            try:
                out = chat(base_url, model, api_key, messages, request_timeout)
            except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
                error = f"{type(exc).__name__}: {exc}"
                break
            wire.write(json.dumps({"turn": turn, "request": messages, "response": out}) + "\n")
            wire.flush()
            stats["turns"] += 1
            usage = out.get("usage") or {}
            if usage:
                tokens["prompt"] += int(usage.get("prompt_tokens") or 0)
                tokens["completion"] += int(usage.get("completion_tokens") or 0)
            else:
                stats["usage_missing"] += 1
            choice = (out.get("choices") or [{}])[0]
            finish = choice.get("finish_reason")
            stats["finish_reasons"].append(finish)
            if finish == "length":
                stats["truncated"] += 1
            msg = choice.get("message") or {}
            content = msg.get("content") or ""
            calls = msg.get("tool_calls") or []
            entry = {"role": "assistant", "content": content}
            if calls:
                entry["tool_calls"] = calls
            messages.append(entry)
            if not calls:
                final_text = content
                break
            for i, call in enumerate(calls):
                stats["tool_calls"] += 1
                fn = call.get("function") or {}
                name = fn.get("name") or ""
                raw_args = fn.get("arguments")
                if isinstance(raw_args, dict):
                    args = raw_args
                else:
                    try:
                        args = json.loads(raw_args or "{}")
                    except (json.JSONDecodeError, TypeError):
                        stats["invalid_args"] += 1
                        args = {}
                result = run_tool(ws, name, args)
                messages.append({"role": "tool",
                                 "tool_call_id": call.get("id") or f"call_{turn}_{i}",
                                 "content": result})
    finally:
        wire.close()

    wall = round(time.time() - start, 1)
    passed, checks = (False, []) if error else grade(task, ws)
    return {
        "task": task["id"], "tier": task["tier"], "title": task["title"], "pass": passed,
        "wall_s": wall, "tokens": tokens, **stats,
        "timed_out": timed_out, "error": error, "checks": checks,
        "final_text": final_text[-2000:],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base-url", default="http://127.0.0.1:8000",
                    help="engine root; /v1 is appended")
    ap.add_argument("--model", required=False, help="served model name")
    ap.add_argument("--api-key-env", default="OPENAI_API_KEY",
                    help="env var holding the bearer key; unset sends no auth header")
    ap.add_argument("--tasks", help="comma list of task ids (default: all in --tier)")
    ap.add_argument("--tier", choices=("easy", "hard", "all"), default="all",
                    help="task tier: easy floor, hard ceiling, or all (default)")
    ap.add_argument("--outdir", help="receipt dir (default ~/benchmarks/agentic-battery-<date>)")
    ap.add_argument("--fixture-root", default=str(REPO / ".scratch" / "agentic"),
                    help="workspace/fixture root, git-ignored")
    ap.add_argument("--max-turns", type=int, default=None,
                    help="override the per-task turn budget (easy 16, hard 24)")
    ap.add_argument("--wall-clock", type=int, default=None,
                    help="override the per-task wall cap (easy 600 s, hard 900 s)")
    ap.add_argument("--request-timeout", type=int, default=300)
    ap.add_argument("--resume", action="store_true", help="skip tasks that already have a result")
    ap.add_argument("--list", action="store_true", help="print the task set and its tier")
    ap.add_argument("--selftest", action="store_true",
                    help="offline self-check: every task red unsolved, green with its patch")
    args = ap.parse_args(argv)

    if args.list:
        for task in TASKS:
            print(f"{task['tier']:<5} {task['id']:<26} {task['title']}")
        return 0
    if args.selftest:
        return selftest()
    if not args.model:
        ap.error("--model is required (the served model name)")

    pool = [t for t in TASKS if args.tier == "all" or t["tier"] == args.tier]
    wanted = [t.strip() for t in args.tasks.split(",")] if args.tasks else [t["id"] for t in pool]
    by_id = {t["id"]: t for t in TASKS}
    missing = [t for t in wanted if t not in by_id]
    if missing:
        ap.error(f"unknown task(s): {', '.join(missing)}; see --list")

    outdir = Path(args.outdir or Path.home() / "benchmarks" /
                  f"agentic-battery-{time.strftime('%Y%m%d')}")
    outdir.mkdir(parents=True, exist_ok=True)
    root = Path(args.fixture_root)
    root.mkdir(parents=True, exist_ok=True)
    api_key = os.environ.get(args.api_key_env) if args.api_key_env else None

    results, rc = [], 0
    consecutive_errors = 0
    for task_id in wanted:
        receipt = outdir / f"{task_id}.json"
        if args.resume and receipt.exists():
            results.append(json.loads(receipt.read_text(encoding="utf-8")))
            continue
        result = run_task(by_id[task_id], args.base_url, args.model, api_key, root,
                          args.max_turns or by_id[task_id].get("max_turns", 16),
                          args.wall_clock or by_id[task_id].get("wall_s", 600),
                          outdir, args.request_timeout)
        receipt.write_text(json.dumps(result, indent=1), encoding="utf-8")
        results.append(result)
        tag = "PASS" if result["pass"] else "FAIL"
        tok = result["tokens"]["prompt"] + result["tokens"]["completion"]
        print(f"{task_id:<24} {tag}  {result['wall_s']:6.1f}s  turns={result['turns']:<3}"
              f" calls={result['tool_calls']:<3} tokens={tok:<7}"
              f"{'  TIMEOUT' if result['timed_out'] else ''}"
              f"{'  ERROR' if result['error'] else ''}")
        consecutive_errors = consecutive_errors + 1 if result["error"] or result["timed_out"] else 0
        if consecutive_errors >= 2:
            print("\nstopping: two consecutive tasks errored or timed out; "
                  f"{len(wanted) - len(results)} task(s) not run")
            break

    walls = [r["wall_s"] for r in results]
    walls.sort()
    summary = {
        "base_url": args.base_url, "model": args.model, "tier": args.tier,
        "max_tokens": MAX_TOKENS,
        "when": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "passed": sum(1 for r in results if r["pass"]), "tasks": len(results),
        "wall_median_s": walls[len(walls) // 2] if walls else None,
        "wall_worst_s": walls[-1] if walls else None,
        "wall_total_s": round(sum(walls), 1),
        "results": results,
    }
    (outdir / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(f"\n{summary['passed']}/{summary['tasks']} pass  "
          f"median {summary['wall_median_s']}s  worst {summary['wall_worst_s']}s  "
          f"total {summary['wall_total_s']}s  -> {outdir}")
    if not walls:
        rc = 1
    return rc


# ---------------------------------------------------------------------------
# Task set
# ---------------------------------------------------------------------------

TASKS = [
    {
        "id": "fix-failing-test",
        "title": "fix a failing discount/total module",
        "prompt": "`python -B -m unittest -q test_calc` fails in this repository. "
                  "Read the code and the test, find the bugs, fix `calc.py` so the suite passes. "
                  "Do not edit `test_calc.py`.",
        "files": {
            "calc.py": (
                "def apply_discount(price_cents, percent):\n"
                "    return price_cents - price_cents * percent // 100\n"
            ),
            "test_calc.py": (
                "import unittest\n"
                "from calc import apply_discount, total\n\n"
                "class CalcTest(unittest.TestCase):\n"
                "    def test_discount_floors_to_the_cent(self):\n"
                "        self.assertEqual(apply_discount(999, 33), 669)\n\n"
                "    def test_total_sums_items(self):\n"
                "        self.assertEqual(total([100, 250, 5]), 355)\n\n"
                "if __name__ == '__main__':\n"
                "    unittest.main()\n"
            ),
        },
        "checks": [
            {"name": "visible-suite", "cmd": ["{python}", "-B", "-m", "unittest", "-q", "test_calc"]},
            {"name": "hidden-cases", "script": (
                "import unittest\n"
                "from calc import apply_discount, total\n\n"
                "class C(unittest.TestCase):\n"
                "    def test_discount(self):\n"
                "        self.assertEqual(apply_discount(999, 33), 669)\n"
                "        self.assertEqual(apply_discount(100, 0), 100)\n"
                "        self.assertEqual(apply_discount(250, 100), 0)\n"
                "        self.assertEqual(apply_discount(1, 50), 0)\n\n"
                "    def test_total(self):\n"
                "        self.assertEqual(total([]), 0)\n"
                "        self.assertEqual(total([100, 250, 5]), 355)\n\n"
                "unittest.main(verbosity=1)\n"
            )},
        ],
    },
    {
        "id": "two-file-bug-hunt",
        "title": "cross-file bug: stock reservation loses integer type",
        "prompt": "`python -B -m unittest -q test_service` fails. The bug is not in the test. "
                  "Read `service.py` and `store.py` together and fix the root cause.",
        "files": {
            "store.py": (
                "_cache = {}\n\n"
                "def clear():\n"
                "    _cache.clear()\n\n"
                "def put(key, value):\n"
                "    _cache[key] = str(value)\n\n"
                "def get(key, default=None):\n"
                "    return _cache.get(key, default)\n"
            ),
            "service.py": (
                "from store import get, put\n\n"
                "def reserve(sku, qty):\n"
                "    have = get('stock:' + sku, 0)\n"
                "    if have < qty:\n"
                "        return False\n"
                "    put('stock:' + sku, have - qty)\n"
                "    return True\n"
            ),
            "test_service.py": (
                "import unittest\n"
                "import store\n"
                "from service import reserve\n\n"
                "class ServiceTest(unittest.TestCase):\n"
                "    def test_reserve_decrements(self):\n"
                "        store.clear()\n"
                "        store.put('stock:A', 10)\n"
                "        self.assertTrue(reserve('A', 3))\n"
                "        self.assertEqual(store.get('stock:A'), 7)\n\n"
                "if __name__ == '__main__':\n"
                "    unittest.main()\n"
            ),
        },
        "checks": [
            {"name": "visible-suite", "cmd": ["{python}", "-B", "-m", "unittest", "-q", "test_service"]},
            {"name": "hidden-roundtrip", "script": (
                "import store\n"
                "from service import reserve\n"
                "store.clear()\n"
                "assert store.get('stock:B') is None\n"
                "store.put('stock:B', 4)\n"
                "assert store.get('stock:B') == 4, store.get('stock:B')\n"
                "assert reserve('B', 4) is True\n"
                "assert store.get('stock:B') == 0\n"
                "assert reserve('B', 1) is False\n"
                "print('roundtrip ok')\n"
            )},
        ],
    },
    {
        "id": "spec-to-function",
        "title": "implement parse_duration from SPEC.md",
        "prompt": "Implement `parse_duration` in `durations.py` exactly as `SPEC.md` describes. "
                  "Run the visible test, then verify the error cases yourself.",
        "files": {
            "SPEC.md": (
                "# parse_duration\n\n"
                "`parse_duration(text) -> int` converts a duration such as `1h30m` to whole seconds.\n\n"
                "- Input is one or more `<integer><unit>` groups with no separators: units `s`, `m`, `h`, `d`.\n"
                "- The whole string must be consumed; only ASCII digits are accepted.\n"
                "- Groups may appear in any order; values may be zero. Return an int.\n"
                "- Raise `ValueError` on: empty string, no unit, unknown unit, non-integer or signed\n"
                "  value, trailing garbage, and whitespace.\n"
            ),
            "durations.py": (
                "def parse_duration(text):\n"
                "    raise NotImplementedError\n"
            ),
            "test_durations.py": (
                "import unittest\n"
                "from durations import parse_duration\n\n"
                "class DurationsTest(unittest.TestCase):\n"
                "    def test_basic(self):\n"
                "        self.assertEqual(parse_duration('1h30m'), 5400)\n\n"
                "    def test_days(self):\n"
                "        self.assertEqual(parse_duration('1d'), 86400)\n\n"
                "if __name__ == '__main__':\n"
                "    unittest.main()\n"
            ),
        },
        "checks": [
            {"name": "visible-suite", "cmd": ["{python}", "-B", "-m", "unittest", "-q", "test_durations"]},
            {"name": "hidden-table", "script": (
                "from durations import parse_duration\n"
                "ok = {'45s': 45, '2m': 120, '1h30m': 5400, '1d': 86400, '1h0m30s': 3630, '0s': 0,\n"
                "      '30m1h': 5400}\n"
                "for text, want in ok.items():\n"
                "    got = parse_duration(text)\n"
                "    assert got == want and isinstance(got, int), (text, got, want)\n"
                "for bad in ['', '30', '1x', '-5m', 'm', '1h 30m', '1.5h']:\n"
                "    try:\n"
                "        parse_duration(bad)\n"
                "    except ValueError:\n"
                "        continue\n"
                "    raise AssertionError('accepted ' + repr(bad))\n"
                "print('table ok')\n"
            )},
        ],
    },
    {
        "id": "refactor-preserve-behavior",
        "title": "remove duplicated row formatting, output unchanged",
        "prompt": "`report.py` duplicates the row formatting in `render_rows` and `render_report`. "
                  "Introduce one `format_row(row)` helper used by both. Output must stay "
                  "byte-identical and `python -B -m unittest -q test_report` must stay green.",
        "files": {
            "report.py": (
                "def render_rows(rows):\n"
                "    lines = []\n"
                "    for r in rows:\n"
                "        lines.append(f\"{r['name']:<10} {r['amount']:>8}\")\n"
                "    return '\\n'.join(lines)\n\n\n"
                "def render_report(rows):\n"
                "    lines = ['NAME           AMOUNT']\n"
                "    for r in rows:\n"
                "        lines.append(f\"{r['name']:<10} {r['amount']:>8}\")\n"
                "    return '\\n'.join(lines)\n"
            ),
            "test_report.py": (
                "import unittest\n"
                "import report\n\n"
                "ROWS = [{'name': 'a', 'amount': 1}, {'name': 'long-name', 'amount': 22}]\n\n"
                "class ReportTest(unittest.TestCase):\n"
                "    def test_render_report(self):\n"
                "        self.assertEqual(report.render_report(ROWS).splitlines()[0], 'NAME           AMOUNT')\n"
                "        self.assertEqual(len(report.render_report(ROWS).splitlines()), 3)\n\n"
                "    def test_render_rows(self):\n"
                "        self.assertEqual(len(report.render_rows(ROWS).splitlines()), 2)\n\n"
                "if __name__ == '__main__':\n"
                "    unittest.main()\n"
            ),
        },
        "checks": [
            {"name": "visible-suite", "cmd": ["{python}", "-B", "-m", "unittest", "-q", "test_report"]},
            {"name": "shared-helper", "script": (
                "import report\n"
                "ROWS = [{'name': 'a', 'amount': 1}, {'name': 'long-name', 'amount': 22}]\n"
                "want = '\\n'.join(f\"{r['name']:<10} {r['amount']:>8}\" for r in ROWS)\n"
                "assert report.render_rows(ROWS) == want\n"
                "assert report.render_report(ROWS) == 'NAME           AMOUNT\\n' + want\n"
                "calls = []\n"
                "orig = report.format_row\n"
                "report.format_row = lambda row: (calls.append(row), orig(row))[1]\n"
                "report.render_rows(ROWS)\n"
                "report.render_report(ROWS)\n"
                "assert len(calls) == 4, f'format_row used {len(calls)} times, want 4'\n"
                "print('helper shared')\n"
            )},
        ],
    },
    {
        "id": "config-migration",
        "title": "migrate INI settings to JSON without breaking callers",
        "prompt": "Migrate the settings from `settings.ini` to `settings.json` with the same values "
                  "(port as a JSON number, debug as a JSON boolean, under a `server` object). "
                  "`config.load()` must read the JSON by default and keep its return shape; remove "
                  "`settings.ini`; keep `python -B -m unittest -q test_config` green.",
        "files": {
            "settings.ini": "[server]\nport=8080\ndebug=no\n",
            "config.py": (
                "import configparser\n\n\n"
                "def load(path='settings.ini'):\n"
                "    cp = configparser.ConfigParser()\n"
                "    cp.read(path)\n"
                "    return {'port': cp.getint('server', 'port'),\n"
                "            'debug': cp.getboolean('server', 'debug')}\n"
            ),
            "test_config.py": (
                "import unittest\n"
                "import config\n\n"
                "class ConfigTest(unittest.TestCase):\n"
                "    def test_defaults(self):\n"
                "        self.assertEqual(config.load(), {'port': 8080, 'debug': False})\n\n"
                "if __name__ == '__main__':\n"
                "    unittest.main()\n"
            ),
        },
        "checks": [
            {"name": "visible-suite", "cmd": ["{python}", "-B", "-m", "unittest", "-q", "test_config"]},
            {"name": "migration", "script": (
                "import json, os\n"
                "import config\n"
                "assert os.path.exists('settings.json'), 'settings.json missing'\n"
                "assert not os.path.exists('settings.ini'), 'settings.ini still present'\n"
                "data = json.load(open('settings.json'))\n"
                "assert data == {'server': {'port': 8080, 'debug': False}}, data\n"
                "assert config.load() == {'port': 8080, 'debug': False}\n"
                "assert config.load('settings.json') == {'port': 8080, 'debug': False}\n"
                "print('migrated')\n"
            )},
        ],
    },
    {
        "id": "csv-to-json-cli",
        "title": "finish a CSV aggregation CLI",
        "prompt": "Finish `report_cli.py` so it reads the CSV given by `--input` and writes the JSON "
                  "summary its docstring specifies to `--output`. Use only the standard library. "
                  "Run it once on `sales.csv` and check the JSON before you stop.",
        "files": {
            "sales.csv": "region,amount\neast,10.5\nwest,3.25\neast,2\n",
            "report_cli.py": (
                '"""Summarise a sales CSV.\n\n'
                "Usage: python -B report_cli.py --input sales.csv --output summary.json\n\n"
                "Output JSON: one key per region, sorted by region, each an object with\n"
                "`total` (float, rounded to 2 decimals) and `rows` (int).\n"
                '"""\n'
                "import argparse\n\n\n"
                "def main():\n"
                "    ap = argparse.ArgumentParser()\n"
                "    ap.add_argument('--input', required=True)\n"
                "    ap.add_argument('--output', required=True)\n"
                "    args = ap.parse_args()\n"
                "    raise NotImplementedError('summarise here')\n\n\n"
                "if __name__ == '__main__':\n"
                "    main()\n"
            ),
        },
        "checks": [
            {"name": "cli", "script": (
                "import json, subprocess, sys\n"
                "open('cases.csv', 'w').write('region,amount\\nnorth,1.25\\nnorth,2.5\\nsouth,4\\n')\n"
                "subprocess.run([sys.executable, '-B', 'report_cli.py', '--input', 'cases.csv',\n"
                "                '--output', 'out.json'], check=True)\n"
                "got = json.load(open('out.json'))\n"
                "assert list(got) == ['north', 'south'], got\n"
                "assert got['north']['rows'] == 2 and got['south']['rows'] == 1, got\n"
                "assert got['north']['total'] == 3.75, got\n"
                "assert abs(got['south']['total'] - 4.0) < 1e-9, got\n"
                "subprocess.run([sys.executable, '-B', 'report_cli.py', '--input', 'sales.csv',\n"
                "                '--output', 'summary.json'], check=True)\n"
                "print('cli ok')\n"
            )},
        ],
    },
    {
        "id": "mutable-default-bug",
        "title": "shared default argument leaks between batches",
        "prompt": "`python -B -m unittest -q test_queue` fails. Read `queue.py` and `worker.py`, "
                  "find the root cause, and fix it without changing the public signatures.",
        "files": {
            "queue.py": (
                "def enqueue(item, items=[]):\n"
                "    items.append(item)\n"
                "    return items\n"
            ),
            "worker.py": (
                "from queue import enqueue\n\n\n"
                "def batch(items):\n"
                "    out = []\n"
                "    for item in items:\n"
                "        out = enqueue(item)\n"
                "    return out\n"
            ),
            "test_queue.py": (
                "import unittest\n"
                "from queue import enqueue\n"
                "from worker import batch\n\n"
                "class QueueTest(unittest.TestCase):\n"
                "    def test_enqueue_isolated(self):\n"
                "        self.assertEqual(enqueue('a'), ['a'])\n"
                "        self.assertEqual(enqueue('b'), ['b'])\n\n"
                "    def test_batch(self):\n"
                "        self.assertEqual(batch(['x', 'y']), ['x', 'y'])\n\n"
                "if __name__ == '__main__':\n"
                "    unittest.main()\n"
            ),
        },
        "checks": [
            {"name": "visible-suite", "cmd": ["{python}", "-B", "-m", "unittest", "-q", "test_queue"]},
            {"name": "hidden-isolation", "script": (
                "from queue import enqueue\n"
                "from worker import batch\n"
                "assert enqueue('a') == ['a']\n"
                "assert enqueue('b') == ['b']\n"
                "assert enqueue('c', []) == ['c']\n"
                "assert enqueue('d', ['z']) == ['z', 'd']\n"
                "assert batch(['x', 'y']) == ['x', 'y']\n"
                "print('isolated')\n"
            )},
        ],
    },
    {
        "id": "validation-boundary",
        "title": "stopping incomplete arguments silently becoming an order",
        "prompt": "`Account.withdraw` currently accepts anything. Add validation: raise `ValueError` "
                  "for a non-positive amount or one exceeding the balance, and leave the balance "
                  "unchanged when it raises. Keep the happy path and "
                  "`python -B -m unittest -q test_account` green.",
        "files": {
            "account.py": (
                "class Account:\n"
                "    def __init__(self, balance):\n"
                "        self.balance = balance\n\n"
                "    def withdraw(self, amount):\n"
                "        self.balance -= amount\n"
                "        return self.balance\n"
            ),
            "test_account.py": (
                "import unittest\n"
                "from account import Account\n\n"
                "class AccountTest(unittest.TestCase):\n"
                "    def test_withdraw(self):\n"
                "        acct = Account(100)\n"
                "        self.assertEqual(acct.withdraw(40), 60)\n\n"
                "if __name__ == '__main__':\n"
                "    unittest.main()\n"
            ),
        },
        "checks": [
            {"name": "visible-suite", "cmd": ["{python}", "-B", "-m", "unittest", "-q", "test_account"]},
            {"name": "hidden-validation", "script": (
                "from account import Account\n"
                "acct = Account(100)\n"
                "assert acct.withdraw(40) == 60\n"
                "for bad in (0, -5, 61):\n"
                "    before = acct.balance\n"
                "    try:\n"
                "        acct.withdraw(bad)\n"
                "    except ValueError:\n"
                "        assert acct.balance == before, (bad, acct.balance, before)\n"
                "        continue\n"
                "    raise AssertionError(f'accepted {bad}')\n"
                "assert acct.balance == 60\n"
                "print('validated')\n"
            )},
        ],
    },
    {
        "id": "multi-file-refactor",
        "tier": "hard",
        "title": "extract a shared helper across four modules",
        "prompt": "The same money and date formatting is copy-pasted in `invoices.py`, `payments.py` "
                  "and `summary.py`. Extract `format_money(cents)` and `format_date(stamp)` into a new "
                  "`textfmt.py`, delete every local copy, and make the three renderers and `cli.py`'s "
                  "output stay byte-identical. The import graph must stay acyclic. Run the suite.",
        "files": {
            "invoices.py": (
                "def _money(cents):\n"
                "    return f\"${cents // 100}.{cents % 100:02d}\"\n\n\n"
                "def _day(stamp):\n"
                "    return stamp[5:10].replace('-', '/')\n\n\n"
                "def render_invoices(rows):\n"
                "    return [f\"{r['id']} {_money(r['cents'])} {_day(r['due'])}\" for r in rows]\n"
            ),
            "payments.py": (
                "def _money(cents):\n"
                "    return f\"${cents // 100}.{cents % 100:02d}\"\n\n\n"
                "def _day(stamp):\n"
                "    return stamp[5:10].replace('-', '/')\n\n\n"
                "def render_payments(rows):\n"
                "    return [f\"{r['id']} paid {_money(r['cents'])} on {_day(r['paid'])}\" for r in rows]\n"
            ),
            "summary.py": (
                "def _money(cents):\n"
                "    return f\"${cents // 100}.{cents % 100:02d}\"\n\n\n"
                "def render_summary(rows):\n"
                "    return f\"total {_money(sum(r['cents'] for r in rows))}\"\n"
            ),
            "cli.py": (
                "import json\n"
                "import sys\n\n"
                "from invoices import render_invoices\n"
                "from payments import render_payments\n"
                "from summary import render_summary\n\n\n"
                "def main(path):\n"
                "    rows = json.load(open(path))\n"
                "    return '\\n'.join(render_invoices(rows) + render_payments(rows) + [render_summary(rows)])\n\n\n"
                "if __name__ == '__main__':\n"
                "    print(main(sys.argv[1]))\n"
            ),
            "data.json": (
                '[\n {"id": 1, "cents": 1299, "due": "2026-11-01", "paid": "2026-11-03"},\n'
                ' {"id": 2, "cents": 450, "due": "2026-11-15", "paid": "2026-11-16"}\n]\n'
            ),
            "test_app.py": (
                "import json\nimport unittest\n\n"
                "import invoices\nimport payments\nimport summary\n\n"
                "ROWS = json.load(open('data.json'))\n\n\n"
                "class AppTest(unittest.TestCase):\n"
                "    def test_invoices(self):\n"
                "        self.assertEqual(len(invoices.render_invoices(ROWS)), 2)\n\n"
                "    def test_payments(self):\n"
                "        self.assertEqual(len(payments.render_payments(ROWS)), 2)\n\n"
                "    def test_summary(self):\n"
                "        self.assertEqual(summary.render_summary(ROWS), 'total $17.49')\n\n\n"
                "if __name__ == '__main__':\n"
                "    unittest.main()\n"
            ),
        },
        "checks": [
            {"name": "visible-suite", "cmd": ["{python}", "-B", "-m", "unittest", "-q", "test_app"]},
            {"name": "golden-output", "script": (
                "import json\n"
                "import invoices, payments, summary\n"
                "rows = json.load(open('data.json'))\n"
                "assert invoices.render_invoices(rows) == ['1 $12.99 11/01', '2 $4.50 11/15']\n"
                "assert payments.render_payments(rows) == ['1 paid $12.99 on 11/03', '2 paid $4.50 on 11/16']\n"
                "assert summary.render_summary(rows) == 'total $17.49'\n"
                "print('output byte-identical')\n"
            )},
            {"name": "structure", "script": (
                "import ast\n"
                "import pathlib\n"
                "defs = {}\n"
                "imports = {}\n"
                "for path in pathlib.Path('.').glob('*.py'):\n"
                "    if path.name == 'test_app.py':\n"
                "        continue\n"
                "    tree = ast.parse(path.read_text())\n"
                "    for node in ast.walk(tree):\n"
                "        if isinstance(node, ast.FunctionDef) and node.name in {\n"
                "                'format_money', 'format_date', '_money', '_day'}:\n"
                "            defs.setdefault(node.name, []).append(path.name)\n"
                "    mods = set()\n"
                "    for node in ast.walk(tree):\n"
                "        if isinstance(node, ast.ImportFrom) and node.module:\n"
                "            mods.add(node.module.split('.')[0])\n"
                "        elif isinstance(node, ast.Import):\n"
                "            mods.update(a.name.split('.')[0] for a in node.names)\n"
                "    imports[path.stem] = {m for m in mods if pathlib.Path(m + '.py').exists()}\n"
                "assert defs.get('format_money') == ['textfmt.py'], defs\n"
                "assert defs.get('format_date') == ['textfmt.py'], defs\n"
                "assert '_money' not in defs and '_day' not in defs, defs\n"
                "for module in ('invoices', 'payments', 'summary'):\n"
                "    assert 'textfmt' in imports[module], (module, imports[module])\n"
                "assert imports['textfmt'] == set(), imports['textfmt']\n"
                "seen = set()\n"
                "def visit(name, stack):\n"
                "    assert name not in stack, 'import cycle: ' + ' -> '.join(list(stack) + [name])\n"
                "    if name in seen:\n"
                "        return\n"
                "    stack.add(name)\n"
                "    for dep in imports.get(name, ()):\n"
                "        visit(dep, stack)\n"
                "    stack.discard(name)\n"
                "    seen.add(name)\n"
                "for name in imports:\n"
                "    visit(name, set())\n"
                "print('helper single-site, imports acyclic')\n"
            )},
        ],
    },
    {
        "id": "shell-repro-rounding",
        "tier": "hard",
        "title": "bill split loses cents; only the repro script shows it",
        "prompt": "`python -B repro.py` fails: the split shares do not add up to the billed total. "
                  "Run it first. Fix `split_bill` so the shares sum exactly to the rounded total, "
                  "differ by at most one cent, and are deterministic. Keep "
                  "`python -B -m unittest -q test_ledger` green.",
        "files": {
            "ledger.py": (
                "def split_bill(total_cents, people, service=0.18):\n"
                "    share = total_cents * (1 + service) / people\n"
                "    return [round(share) for _ in range(people)]\n"
            ),
            "repro.py": (
                "from ledger import split_bill\n\n"
                "CASES = [(1000, 3), (1999, 7), (500, 2), (101, 6), (7, 4)]\n"
                "bad = 0\n"
                "for total, people in CASES:\n"
                "    shares = split_bill(total, people)\n"
                "    want = round(total * 1.18)\n"
                "    mark = 'ok' if sum(shares) == want else 'FAIL'\n"
                "    if sum(shares) != want:\n"
                "        bad += 1\n"
                "    print(f'{total}/{people}: {shares} sum={sum(shares)} want={want} {mark}')\n"
                "print('OK' if not bad else f'FAIL {bad} case(s)')\n"
                "raise SystemExit(1 if bad else 0)\n"
            ),
            "test_ledger.py": (
                "import unittest\n\n"
                "from ledger import split_bill\n\n\n"
                "class LedgerTest(unittest.TestCase):\n"
                "    def test_even_split(self):\n"
                "        self.assertEqual(split_bill(1000, 2), [590, 590])\n\n\n"
                "if __name__ == '__main__':\n"
                "    unittest.main()\n"
            ),
        },
        "checks": [
            {"name": "visible-suite", "cmd": ["{python}", "-B", "-m", "unittest", "-q", "test_ledger"]},
            {"name": "repro", "cmd": ["{python}", "-B", "repro.py"]},
            {"name": "hidden-sweep", "script": (
                "from ledger import split_bill\n"
                "for total in range(1, 400):\n"
                "    for people in range(1, 10):\n"
                "        due = round(total * 1.18)\n"
                "        shares = split_bill(total, people)\n"
                "        assert len(shares) == people, (total, people, shares)\n"
                "        assert sum(shares) == due, (total, people, shares, due)\n"
                "        assert max(shares) - min(shares) <= 1, (total, people, shares)\n"
                "        assert all(isinstance(s, int) for s in shares), shares\n"
                "        assert shares == split_bill(total, people), 'non-deterministic'\n"
                "for total, people in ((999, 3), (1, 4), (0, 2)):\n"
                "    shares = split_bill(total, people, service=0)\n"
                "    assert sum(shares) == total and len(shares) == people, (total, people, shares)\n"
                "print('sweep exact')\n"
            )},
        ],
    },
    {
        "id": "normalize-edge-table",
        "tier": "hard",
        "title": "canonicalise account keys against an edge-case spec",
        "prompt": "Implement `canonical_key` in `keys.py` exactly as `SPEC.md` describes. The hidden "
                  "table covers valid and invalid inputs; run the visible test and probe the edges "
                  "yourself before you stop.",
        "files": {
            "SPEC.md": (
                "# canonical_key\n\n"
                "`canonical_key(text) -> str` canonicalises an account key.\n\n"
                "- Strip surrounding whitespace, then uppercase the text.\n"
                "- `_`, U+2013 (en dash) and U+2014 (em dash) become `-`; runs of `-` collapse to one;\n"
                "  leading and trailing `-` are stripped.\n"
                "- The result must be 2 to 4 ASCII letters, exactly one `-`, then 4 to 8 ASCII digits.\n"
                "- The numeric part is zero-padded to 6 digits when it is shorter than 6.\n"
                "- Raise `ValueError` for anything else: empty input, a missing or second separator\n"
                "  group, non-ASCII letters, embedded whitespace, signed digits, a wrong digit count.\n"
            ),
            "keys.py": (
                "def canonical_key(text):\n"
                "    raise NotImplementedError\n"
            ),
            "test_keys.py": (
                "import unittest\n\n"
                "from keys import canonical_key\n\n\n"
                "class KeysTest(unittest.TestCase):\n"
                "    def test_basic(self):\n"
                "        self.assertEqual(canonical_key('ab-1234'), 'AB-001234')\n\n"
                "    def test_dash_variant(self):\n"
                "        self.assertEqual(canonical_key(' de\\u201398765432 '), 'DE-98765432')\n\n\n"
                "if __name__ == '__main__':\n"
                "    unittest.main()\n"
            ),
        },
        "checks": [
            {"name": "visible-suite", "cmd": ["{python}", "-B", "-m", "unittest", "-q", "test_keys"]},
            {"name": "hidden-table", "script": (
                "from keys import canonical_key\n"
                "ok = {\n"
                "    ' ab-1234 ': 'AB-001234',\n"
                "    'us_123456': 'US-123456',\n"
                "    'de\\u201398765432': 'DE-98765432',\n"
                "    'FR\\u20140042': 'FR-000042',\n"
                "    'zz-999999': 'ZZ-999999',\n"
                "    'ab__1234': 'AB-001234',\n"
                "    'abcd-12345678': 'ABCD-12345678',\n"
                "    '--gb-12345--': 'GB-012345',\n"
                "}\n"
                "for text, want in ok.items():\n"
                "    got = canonical_key(text)\n"
                "    assert got == want, (text, got, want)\n"
                "bad = ['', 'A-1234', 'ABCDE-1234', 'ab-12', 'ab-123456789', 'ab-12a4',\n"
                "       '\\u00fcs-1234', 'ab 1234', 'ab-+1234', 'ab-12-34', 'ab1234']\n"
                "for text in bad:\n"
                "    try:\n"
                "        canonical_key(text)\n"
                "    except ValueError:\n"
                "        continue\n"
                "    raise AssertionError('accepted ' + repr(text))\n"
                "print('table ok')\n"
            )},
        ],
    },
    {
        "id": "stub-service-client",
        "tier": "hard",
        "title": "wire a client to a local line service and test it end to end",
        "prompt": "Implement `collect(host, port, timeout=5.0)` in `client.py`. The service "
                  "(`service_stub.py`, started as `python -B service_stub.py <port>`) sends "
                  "newline-terminated `key=value` lines with integer values, then closes the "
                  "connection. Return a dict of ints; raise `ValueError` for a malformed line or a "
                  "non-integer value. Start the stub yourself and test the round trip.",
        "files": {
            "service_stub.py": (
                '"""Line service for client.py: python -B service_stub.py <port>."""\n'
                "import socket\n"
                "import sys\n\n"
                "PAYLOAD = {'alpha': 2, 'beta': 5}\n\n\n"
                "def serve(port):\n"
                "    listener = socket.socket()\n"
                "    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)\n"
                "    listener.bind(('127.0.0.1', port))\n"
                "    listener.listen(1)\n"
                "    print('listening', flush=True)\n"
                "    conn, _ = listener.accept()\n"
                "    with conn:\n"
                "        conn.sendall(''.join(f'{k}={v}\\n' for k, v in PAYLOAD.items()).encode())\n"
                "    listener.close()\n\n\n"
                "if __name__ == '__main__':\n"
                "    serve(int(sys.argv[1]))\n"
            ),
            "client.py": (
                "def collect(host, port, timeout=5.0):\n"
                "    raise NotImplementedError\n"
            ),
        },
        "checks": [
            {"name": "end-to-end", "timeout": 60, "script": (
                "import socket\n"
                "import threading\n"
                "from client import collect\n"
                "def serve(payload, port_holder, ready):\n"
                "    listener = socket.socket()\n"
                "    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)\n"
                "    listener.bind(('127.0.0.1', 0))\n"
                "    listener.listen(1)\n"
                "    port_holder.append(listener.getsockname()[1])\n"
                "    ready.set()\n"
                "    conn, _ = listener.accept()\n"
                "    with conn:\n"
                "        conn.sendall(payload.encode())\n"
                "    listener.close()\n"
                "def start(payload):\n"
                "    port_holder = []\n"
                "    ready = threading.Event()\n"
                "    threading.Thread(target=serve, args=(payload, port_holder, ready),\n"
                "                     daemon=True).start()\n"
                "    ready.wait(5)\n"
                "    return port_holder[0]\n"
                "good = start('ok=1\\nwarn=3\\n')\n"
                "assert collect('127.0.0.1', good) == {'ok': 1, 'warn': 3}\n"
                "bad = start('nonsense\\n')\n"
                "try:\n"
                "    collect('127.0.0.1', bad)\n"
                "except ValueError:\n"
                "    pass\n"
                "else:\n"
                "    raise AssertionError('accepted a malformed payload')\n"
                "late = start('a=1\\nb=x\\n')\n"
                "try:\n"
                "    collect('127.0.0.1', late)\n"
                "except ValueError:\n"
                "    pass\n"
                "else:\n"
                "    raise AssertionError('accepted a non-integer value')\n"
                "print('round trip ok')\n"
            )},
        ],
    },
    {
        "id": "golden-regression",
        "tier": "hard",
        "title": "add a column without moving a byte of existing output",
        "prompt": "Add an optional PRIORITY column to `render.render()`: shown only when at least one "
                  "row carries a `priority` key; header `PRIORITY` right-aligned in 8 columns, value "
                  "right-aligned in 8, and 8 blank columns for rows without one. Existing outputs "
                  "must stay byte-identical to `golden/*.txt`. The visible suite compares them.",
        "files": {
            "render.py": (
                "def render(rows):\n"
                "    lines = [f\"{'NAME':<8} {'COUNT':>5}\"]\n"
                "    for row in rows:\n"
                "        lines.append(f\"{row['name']:<8} {row['count']:>5}\")\n"
                "    return '\\n'.join(lines)\n"
            ),
            "golden/basic.txt": "NAME     COUNT\nada          3\ngrace       12\n",
            "golden/wide.txt": "NAME     COUNT\na-very-long-name     1\n",
            "golden/empty.txt": "NAME     COUNT\n",
            "test_render.py": (
                "import unittest\n\n"
                "import render\n\n\n"
                "class RenderTest(unittest.TestCase):\n"
                "    def test_basic_golden(self):\n"
                "        rows = [{'name': 'ada', 'count': 3}, {'name': 'grace', 'count': 12}]\n"
                "        self.assertEqual(render.render(rows), open('golden/basic.txt').read().rstrip('\\n'))\n\n"
                "    def test_wide_golden(self):\n"
                "        rows = [{'name': 'a-very-long-name', 'count': 1}]\n"
                "        self.assertEqual(render.render(rows), open('golden/wide.txt').read().rstrip('\\n'))\n\n\n"
                "if __name__ == '__main__':\n"
                "    unittest.main()\n"
            ),
        },
        "checks": [
            {"name": "visible-suite", "cmd": ["{python}", "-B", "-m", "unittest", "-q", "test_render"]},
            {"name": "golden-diff", "script": (
                "import render\n"
                "basic = [{'name': 'ada', 'count': 3}, {'name': 'grace', 'count': 12}]\n"
                "wide = [{'name': 'a-very-long-name', 'count': 1}]\n"
                "assert render.render(basic) == open('golden/basic.txt').read().rstrip('\\n')\n"
                "assert render.render(wide) == open('golden/wide.txt').read().rstrip('\\n')\n"
                "assert render.render([]) == open('golden/empty.txt').read().rstrip('\\n')\n"
                "p_rows = [{'name': 'ada', 'count': 3, 'priority': 7}]\n"
                "want = '\\n'.join([f\"{'NAME':<8} {'COUNT':>5} {'PRIORITY':>8}\",\n"
                "                  f\"{'ada':<8} {3:>5} {7:>8}\"])\n"
                "assert render.render(p_rows) == want, render.render(p_rows)\n"
                "mixed = [{'name': 'ada', 'count': 3, 'priority': 7}, {'name': 'bob', 'count': 4}]\n"
                "want = '\\n'.join([f\"{'NAME':<8} {'COUNT':>5} {'PRIORITY':>8}\",\n"
                "                  f\"{'ada':<8} {3:>5} {7:>8}\",\n"
                "                  f\"{'bob':<8} {4:>5} {'':>8}\"])\n"
                "assert render.render(mixed) == want, render.render(mixed)\n"
                "print('golden preserved, column added')\n"
            )},
        ],
    },
]

# Reference patches: the only proof a checker can be satisfied, used by --selftest and by
# nobody else. `None` deletes a path.
SOLUTIONS = {
    "fix-failing-test": {"calc.py": (
        "def apply_discount(price_cents, percent):\n"
        "    return price_cents * (100 - percent) // 100\n\n\n"
        "def total(items):\n"
        "    return sum(items)\n"
    )},
    "two-file-bug-hunt": {"store.py": (
        "_cache = {}\n\n"
        "def clear():\n"
        "    _cache.clear()\n\n"
        "def put(key, value):\n"
        "    _cache[key] = value\n\n"
        "def get(key, default=None):\n"
        "    return _cache.get(key, default)\n"
    )},
    "spec-to-function": {"durations.py": (
        "import re\n\n"
        "UNITS = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}\n\n\n"
        "def parse_duration(text):\n"
        "    if not isinstance(text, str) or not text:\n"
        "        raise ValueError(text)\n"
        "    total = 0\n"
        "    end = 0\n"
        "    for match in re.finditer(r'(\\d+)([smhd])', text):\n"
        "        if match.start() != end:\n"
        "            raise ValueError(text)\n"
        "        total += int(match.group(1)) * UNITS[match.group(2)]\n"
        "        end = match.end()\n"
        "    if end != len(text):\n"
        "        raise ValueError(text)\n"
        "    return total\n"
    )},
    "refactor-preserve-behavior": {"report.py": (
        "def format_row(row):\n"
        "    return f\"{row['name']:<10} {row['amount']:>8}\"\n\n\n"
        "def render_rows(rows):\n"
        "    return '\\n'.join(format_row(r) for r in rows)\n\n\n"
        "def render_report(rows):\n"
        "    return '\\n'.join(['NAME           AMOUNT'] + [format_row(r) for r in rows])\n"
    )},
    "config-migration": {
        "settings.json": '{"server": {"port": 8080, "debug": false}}\n',
        "config.py": (
            "import json\n\n\n"
            "def load(path='settings.json'):\n"
            "    data = json.load(open(path))['server']\n"
            "    return {'port': int(data['port']), 'debug': bool(data['debug'])}\n"
        ),
        "settings.ini": None,
    },
    "csv-to-json-cli": {"report_cli.py": (
        "import argparse\n"
        "import csv\n"
        "import json\n\n\n"
        "def main():\n"
        "    ap = argparse.ArgumentParser()\n"
        "    ap.add_argument('--input', required=True)\n"
        "    ap.add_argument('--output', required=True)\n"
        "    args = ap.parse_args()\n"
        "    acc = {}\n"
        "    with open(args.input, newline='') as handle:\n"
        "        for row in csv.DictReader(handle):\n"
        "            region = row['region']\n"
        "            acc.setdefault(region, {'total': 0.0, 'rows': 0})\n"
        "            acc[region]['total'] += float(row['amount'])\n"
        "            acc[region]['rows'] += 1\n"
        "    out = {k: {'total': round(acc[k]['total'], 2), 'rows': acc[k]['rows']}\n"
        "           for k in sorted(acc)}\n"
        "    with open(args.output, 'w') as handle:\n"
        "        json.dump(out, handle)\n\n\n"
        "if __name__ == '__main__':\n"
        "    main()\n"
    )},
    "mutable-default-bug": {
        "queue.py": (
            "def enqueue(item, items=None):\n"
            "    if items is None:\n"
            "        items = []\n"
            "    items.append(item)\n"
            "    return items\n"
        ),
        "worker.py": (
            "from queue import enqueue\n\n\n"
            "def batch(items):\n"
            "    out = []\n"
            "    for item in items:\n"
            "        out = enqueue(item, out)\n"
            "    return out\n"
        ),
    },
    "validation-boundary": {"account.py": (
        "class Account:\n"
        "    def __init__(self, balance):\n"
        "        self.balance = balance\n\n"
        "    def withdraw(self, amount):\n"
        "        if amount <= 0:\n"
        "            raise ValueError(amount)\n"
        "        if amount > self.balance:\n"
        "            raise ValueError(amount)\n"
        "        self.balance -= amount\n"
        "        return self.balance\n"
    )},
    "multi-file-refactor": {
        "textfmt.py": (
            "def format_money(cents):\n"
            "    return f\"${cents // 100}.{cents % 100:02d}\"\n\n\n"
            "def format_date(stamp):\n"
            "    return stamp[5:10].replace('-', '/')\n"
        ),
        "invoices.py": (
            "from textfmt import format_date, format_money\n\n\n"
            "def render_invoices(rows):\n"
            "    return [f\"{r['id']} {format_money(r['cents'])} {format_date(r['due'])}\" for r in rows]\n"
        ),
        "payments.py": (
            "from textfmt import format_date, format_money\n\n\n"
            "def render_payments(rows):\n"
            "    return [f\"{r['id']} paid {format_money(r['cents'])} on {format_date(r['paid'])}\"\n"
            "            for r in rows]\n"
        ),
        "summary.py": (
            "from textfmt import format_money\n\n\n"
            "def render_summary(rows):\n"
            "    return f\"total {format_money(sum(r['cents'] for r in rows))}\"\n"
        ),
    },
    "shell-repro-rounding": {"ledger.py": (
        "def split_bill(total_cents, people, service=0.18):\n"
        "    if people <= 0:\n"
        "        raise ValueError('people must be positive')\n"
        "    due = round(total_cents * (1 + service))\n"
        "    base, extra = divmod(due, people)\n"
        "    return [base + 1] * extra + [base] * (people - extra)\n"
    )},
    "normalize-edge-table": {"keys.py": (
        "import re\n\n"
        "SHAPE = re.compile(r'^([A-Z]{2,4})-([0-9]{4,8})$')\n\n\n"
        "def canonical_key(text):\n"
        "    if not isinstance(text, str) or not text.strip():\n"
        "        raise ValueError(text)\n"
        "    normalised = text.strip().upper()\n"
        "    for dash in ('\\u2013', '\\u2014', '_'):\n"
        "        normalised = normalised.replace(dash, '-')\n"
        "    normalised = re.sub(r'-+', '-', normalised).strip('-')\n"
        "    match = SHAPE.match(normalised)\n"
        "    if not match:\n"
        "        raise ValueError(text)\n"
        "    digits = match.group(2)\n"
        "    return f'{match.group(1)}-{digits.zfill(6)}'\n"
    )},
    "stub-service-client": {"client.py": (
        "import socket\n\n\n"
        "def collect(host, port, timeout=5.0):\n"
        "    with socket.create_connection((host, port), timeout=timeout) as sock:\n"
        "        chunks = []\n"
        "        while True:\n"
        "            data = sock.recv(4096)\n"
        "            if not data:\n"
        "                break\n"
        "            chunks.append(data)\n"
        "    values = {}\n"
        "    for line in b''.join(chunks).decode('utf-8').splitlines():\n"
        "        if not line.strip():\n"
        "            continue\n"
        "        key, sep, value = line.partition('=')\n"
        "        if not sep or not key or not value.strip().lstrip('-').isdigit():\n"
        "            raise ValueError(f'bad line: {line!r}')\n"
        "        values[key] = int(value)\n"
        "    return values\n"
    )},
    "golden-regression": {"render.py": (
        "def render(rows):\n"
        "    with_priority = any('priority' in row for row in rows)\n"
        "    header = f\"{'NAME':<8} {'COUNT':>5}\"\n"
        "    if with_priority:\n"
        "        header += f\" {'PRIORITY':>8}\"\n"
        "    lines = [header]\n"
        "    for row in rows:\n"
        "        line = f\"{row['name']:<8} {row['count']:>5}\"\n"
        "        if with_priority:\n"
        "            line += f\" {row.get('priority', ''):>8}\"\n"
        "        lines.append(line)\n"
        "    return '\\n'.join(lines)\n"
    )},
}

for _task in TASKS:
    _task.setdefault("tier", "easy")
    _task.setdefault("max_turns", 16 if _task["tier"] == "easy" else 24)
    _task.setdefault("wall_s", 600 if _task["tier"] == "easy" else 900)
    _task["solution"] = SOLUTIONS[_task["id"]]


# ---------------------------------------------------------------------------
# Offline self-test: every task is red unsolved and green with its reference patch, and a
# scripted mock proves the loop passes a solved task and fails an unsolved one.
# ---------------------------------------------------------------------------
def _mock_server(replies: list[dict], seen: list | None = None) -> tuple[ThreadingHTTPServer, str]:
    state = {"n": 0}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            if seen is not None:
                seen.append(json.loads(raw or b"{}"))
            reply = replies[min(state["n"], len(replies) - 1)]
            state["n"] += 1
            body = json.dumps({
                "choices": [{"message": reply, "finish_reason": "tool_calls" if reply.get("tool_calls") else "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            }).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_port}"


def _apply_solution(task: dict, ws: Path) -> None:
    """Write the task's reference patch; a None value deletes the path."""
    for rel, content in task["solution"].items():
        path = ws / rel
        if content is None:
            path.unlink()
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def selftest() -> int:
    failures = []
    for task in TASKS:
        if not task.get("solution"):
            failures.append(f"{task['id']}: no reference patch")
            continue
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "ws"
            seed_workspace(task, ws)
            red, _ = grade(task, ws)
            _apply_solution(task, ws)
            green, checks = grade(task, ws)
        if red:
            failures.append(f"{task['id']}: passes untouched fixture")
        if not green:
            failures.append(f"{task['id']}: reference patch fails "
                            f"{[c['name'] for c in checks if not c['ok']]}")

    # Loop mechanics: a scripted mock drives the sandbox; the same task must still pass and
    # an agent that never acts must still fail.
    task = {t["id"]: t for t in TASKS}["fix-failing-test"]

    def call(name, args):
        return {"role": "assistant", "content": "", "tool_calls": [{
            "id": "c1", "type": "function",
            "function": {"name": name, "arguments": json.dumps(args)}}]}

    good = [call("write_file", {"path": "calc.py", "content": task["solution"]["calc.py"]}),
            {"role": "assistant", "content": "DONE"}]
    lazy = [{"role": "assistant", "content": "looks fine to me"}]
    for label, replies, want in (("solved", good, True), ("unsolved", lazy, False)):
        server, base = _mock_server(replies)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp) / "out"
                out.mkdir()
                result = run_task(task, base, "mock", None, Path(tmp) / "fx", 4, 60, out, 10)
        finally:
            server.shutdown()
            server.server_close()
        if result["pass"] is not want:
            failures.append(f"loop {label}: pass={result['pass']} want {want} :: "
                            f"{[c['name'] for c in result['checks'] if not c['ok']]}")
        if label == "solved" and (result["tool_calls"] != 1 or result["turns"] != 2):
            failures.append(f"loop counters: {result['tool_calls']} calls, {result['turns']} turns")
    if failures:
        print("selftest FAILED: " + "; ".join(failures))
        return 2
    print(f"selftest ok: {len(TASKS)} tasks red unsolved and green with their patch; "
          "loop passes a solved task and fails an unsolved one")
    return 0


if __name__ == "__main__":
    sys.exit(main())
