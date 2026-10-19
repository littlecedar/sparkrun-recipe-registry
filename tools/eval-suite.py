#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Travis Wichert
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The standard evaluation suite for a live sparkrun serve (SOP).

Why this file exists
--------------------
Every lane pass until 2026-10-15 re-invented its own runner: a receipt-directory
shell script that drove the house battery, a needle ladder, a long-horizon probe
and whatever else the question needed, in whatever order, with the invocation
details alive only in that directory.  The results were good and unreproducible
by construction -- the ornith Plan-C runner existed as `run_remaining.sh` beside
its logs, and nothing generalised it to the next lane.

This tool is that runner, tracked.  It drives the repo's existing instruments
against one live OpenAI-compatible endpoint and writes ONE receipt directory:
the same axes, the same flags, the same summary shape for every arm, so numbers
from two lanes can be read side by side.

Axes (--checks; default contract,house,needle)
----------------------------------------------
contract  GET /v1/models (served id + max_model_len) plus one deterministic
          64-token completion.  Records the content/reasoning split and the
          finish_reason, because "the model answered" and "the model opened a
          reasoning block and got truncated" are different findings -- but only
          an all-empty reply is a failure (see the truncation rule below).
house     tools/quality-battery.py --tier both (19 easy + 18 hard, exact-match).
          The cheap cross-lane tripwire; the hard tier is the informative one.
needle    tools/needle-haystack.py at each --needle-lengths depth.  `auto` (the
          default) resolves to 32k, 128k and the served max_model_len (capped at
          262,144 and deduped), so an arm is probed at its advertised edge.
hard      recipes/ds4/benchmarks/run_benchmarks.py -- the shared hard tier
          (GSM8K and ARC-Challenge, 0-shot, last-number / letter scoring), the
          instrument the ds4 lane compares against.
tools     tools/bfcl-eval.py -- BFCL v3 AST scoring, the tool-calling tier for
          arms that serve a tool parser.  Needs --bfcl-data-dir; a missing data
          dir is a `skip`, never a pass.  Its completion budget is explicit --
          --bfcl-max-tokens (default 4096, the house default) -- because
          bfcl-eval's own default is 512 and a thinking arm spends that inside
          the think block.
horizon   tools/agentic-horizon-probe.py + tools/horizon-analyze.py -- the
          long-horizon agentic probe (multi-turn, growing transcript, loop
          metrics).  For agentic arms; the only axis that exercises
          session-length behaviour.

Not in this tool, on purpose
----------------------------
Speed.  Perf is sparkrun's `benchmark performance` path against a tracked
profile (benchmarking/concurrency-ladder.yaml); the SOP runs it with --skip-run
against the SAME boot, so quality and speed share one window.  The standard
external suite (`sparkrun benchmark tools`, framework tool-eval-bench) is a
scheduler-owned artifact and is invoked separately by the SOP.

Truncation is not a wrong answer
--------------------------------
The repo has paid for this three times: quality-battery's 384-token default
truncates thinking models into `content: null`, the 262k needle "misses" were a
64-token completion budget, and the first llama-cpp arm's bfcl parallel cells
were answered inside bfcl-eval's 512-token default (its leg passed no
--max-tokens at all).  So the suite defaults --house-max-tokens 4096,
--needle-max-tokens 256 and --bfcl-max-tokens 4096, and the contract check fails
only on a reply with neither content nor reasoning -- a non-empty truncated
answer is a measurement, not an error.

Verdicts
--------
Each check reports one of:
  ok     the instrument ran and produced its artifact
  fail   the instrument itself classified a failure (needle exit 3, no models
         served, an all-empty contract reply)
  skip   not requested here, or a prerequisite is missing (e.g. no data dir)
  error  the tool crashed, timed out, or wrote an unreadable artifact
Quality SCORES are never gated -- a hard-tier miss is a finding, not a verdict.
The process exits 0 iff every requested check ended ok/skip, 1 otherwise, so a
caller can chain on it.

Usage
-----
    python3 tools/eval-suite.py --base-url http://127.0.0.1:8000 \
        --label ornith-35b --outdir ~/benchmarks/ornith-35b-suite-20261015

    # the full set on an agentic long-context arm
    python3 tools/eval-suite.py --base-url http://127.0.0.1:8000 --checks all \
        --needle-lengths 32768,131072,262144 --bfcl-data-dir ~/bfcl \
        --horizon-turns 12 --outdir receipt/

Exit codes: 0 all requested checks ok, 1 a check failed or errored, 2 bad flags.
`--selftest` runs the plan/verdict/summary path against a stub tool set and an
in-process mock endpoint, offline, and is a required part of this tool.

Stdlib only, Python 3.12+.  Knows nothing about hostnames or cluster nodes --
the endpoint is a flag and the tools are found beside this file.
"""
from __future__ import annotations

import argparse
import hashlib
import http.server
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from datetime import datetime, timezone

VERSION = "1.0.1"
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

ALL_CHECKS = ("contract", "house", "needle", "hard", "tools", "horizon")
DEFAULT_CHECKS = ("contract", "house", "needle")


class CheckError(Exception):
    """An instrument-level failure inside a check.

    ``kind`` is "fail" when the instrument classified a failure and "error"
    when the tool could not run at all.
    """

    def __init__(self, message: str, kind: str = "fail") -> None:
        super().__init__(message)
        self.kind = kind


# ---------------------------------------------------------------------------
# small helpers

def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-") or "serve"


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: str):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def http_json(url: str, payload=None, timeout: float = 120.0):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def api_root(endpoint: str) -> str:
    """The server root from either `http://host:port` or `http://host:port/v1`.

    The documented convention for `--base-url` is the endpoint root, and the
    suite's own checks append `/v1/...` to it. The external instruments differ
    (needle accepts either, quality-battery builds its own `/v1/...`), so
    normalising once here makes both spellings work instead of leaving the
    caller to remember which check tolerates which.
    """
    base = endpoint.rstrip("/")
    return base[:-3] if base.endswith("/v1") else base


class Ctx:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.base = api_root(args.base_url)
        self.model = None if args.model in (None, "auto") else args.model
        self.tools = os.path.abspath(args.tools_dir or HERE)
        self.run_benchmarks = args.run_benchmarks
        self.python = args.python
        self.max_model_len = None
        self.started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        if args.outdir:
            self.outdir = os.path.abspath(args.outdir)
        else:
            self.outdir = os.path.abspath(
                f"eval-{slug(args.label or self.model or 'serve')}-"
                f"{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
            )
        os.makedirs(self.outdir, exist_ok=True)

    def tool(self, name: str) -> str:
        return os.path.join(self.tools, name)

    def path(self, name: str) -> str:
        return os.path.join(self.outdir, name)


def run_cmd(ctx: Ctx, name: str, cmd: list[str], timeout: float):
    """Run one instrument, tee stdout+stderr into <outdir>/<name>.log.

    PYTHONUNBUFFERED: every instrument is a Python script whose stdout goes to
    a *file*, so CPython block-buffers it — a long `tools` leg then looks
    identical to a hung one from outside (measured 2026-10-17: a 65-minute
    bfcl-eval run had written only the command echo).  The receipt's own
    `suite sha256` keeps a mid-sweep change to this file auditable.
    """
    logpath = ctx.path(f"{name}.log")
    rc: int | None
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    with open(logpath, "w", encoding="utf-8") as fh:
        fh.write("$ " + " ".join(cmd) + "\n\n")
        fh.flush()
        try:
            proc = subprocess.run(cmd, cwd=ctx.outdir, stdout=fh,
                                  stderr=subprocess.STDOUT, timeout=timeout, env=env)
            rc = proc.returncode
        except subprocess.TimeoutExpired:
            fh.write(f"\n[suite] TIMEOUT after {timeout:.0f}s\n")
            rc = None
        except OSError as exc:
            fh.write(f"\n[suite] could not run: {exc}\n")
            rc = None
    return rc, logpath


def log_tail(path: str, lines: int = 1) -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            tail = fh.read().strip().splitlines()[-lines:]
        return " / ".join(t.strip() for t in tail)[:160]
    except OSError:
        return ""


# ---------------------------------------------------------------------------
# checks -- each returns (verdict, headline, artifact)

def served_window(entry: dict) -> int | None:
    """The served context window: vLLM's ``max_model_len`` (or a variant
    spelling), or llama.cpp's ``meta.n_ctx`` -- its /v1/models entry has no
    top-level window key, and missing it here (found 2026-10-17, the first
    llama-cpp arm) both mis-reported the window and let the needle ladder
    plan a rung that fills the window exactly."""
    for key in ("max_model_len", "max_context_length", "context_length"):
        v = entry.get(key)
        if isinstance(v, int) and v > 0:
            return v
    meta = entry.get("meta")
    if isinstance(meta, dict):
        v = meta.get("n_ctx")
        if isinstance(v, int) and v > 0:
            return v
    return None


def check_contract(ctx: Ctx):
    art: dict = {}
    try:
        models = http_json(ctx.base + "/v1/models", timeout=ctx.args.timeout)
    except Exception as exc:  # noqa: BLE001
        raise CheckError(f"endpoint unreachable: {type(exc).__name__}: {exc}", kind="error")
    data = models.get("data") if isinstance(models, dict) else None
    if not data:
        raise CheckError("no models served (/v1/models data is empty)", kind="fail")
    entry = data[0]
    art["served_id"] = entry.get("id")
    art["max_model_len"] = served_window(entry)
    ctx.max_model_len = art["max_model_len"]
    if not ctx.model:
        ctx.model = art["served_id"]
    if art["served_id"] != ctx.model:
        art["model_mismatch"] = f"asked for {ctx.model!r}, served {art['served_id']!r}"

    body = {
        "model": ctx.model,
        "messages": [{"role": "user",
                      "content": "Reply with exactly the word READY and nothing else."}],
        "temperature": 0,
        "max_tokens": 64,
    }
    try:
        reply = http_json(ctx.base + "/v1/chat/completions", body, timeout=ctx.args.timeout)
    except Exception as exc:  # noqa: BLE001
        raise CheckError(f"chat completion failed: {type(exc).__name__}: {exc}", kind="error")
    choice = (reply.get("choices") or [{}])[0]
    msg = choice.get("message") or {}
    content = msg.get("content") or ""
    reasoning = msg.get("reasoning_content") or ""
    art.update({
        "finish_reason": choice.get("finish_reason"),
        "content_len": len(content),
        "reasoning_len": len(reasoning),
        "content_head": content.strip()[:80],
        "ready": "READY" in content.upper(),
        "usage": reply.get("usage"),
    })
    headline = (f"{art['served_id']} max_model_len={art['max_model_len']} "
                f"ready={art['ready']} finish={art['finish_reason']}")
    if not content.strip() and not reasoning.strip():
        return "fail", headline + " (all-empty reply)", art
    return "ok", headline, art


def check_house(ctx: Ctx):
    cmd = [ctx.python, ctx.tool("quality-battery.py"), ctx.base,
           "--tier", ctx.args.house_tier,
           "--max-tokens", str(ctx.args.house_max_tokens),
           "--repeat", str(ctx.args.house_repeat),
           "--json", "house.json"]
    if ctx.model:
        cmd += ["--model", ctx.model]
    rc, log = run_cmd(ctx, "house", cmd, ctx.args.job_timeout)
    if rc is None:
        raise CheckError(f"quality-battery did not run ({log_tail(log)})", kind="error")
    if rc != 0:
        raise CheckError(f"quality-battery exit {rc} ({log_tail(log)})", kind="error")
    art = load_json(ctx.path("house.json"))
    tiers = art.get("tiers") or {}
    parts = []
    for name in sorted(tiers):
        t = tiers[name]
        parts.append(f"{name} {t.get('correct')}/{t.get('total')}")
        if t.get("flaky"):
            parts[-1] += f" flaky:{len(t['flaky'])}"
    if not parts:
        raise CheckError("house.json carries no tiers", kind="error")
    art.pop("tiers", None)  # keep the receipt lean; per-task replies live in the log
    return "ok", " ".join(parts), {"tiers": {n: {k: v for k, v in t.items()
                                                 if k not in ("per_task", "replies")}
                                             for n, t in tiers.items()}, **art}


def resolve_needle_lengths(ctx: Ctx) -> list[int]:
    raw = ctx.args.needle_lengths.strip()
    if raw.lower() != "auto":
        return sorted({int(x) for x in raw.split(",") if x.strip()})
    lengths = {32768, 131072}
    if ctx.max_model_len:
        lengths.add(min(int(ctx.max_model_len), 262144))
    return sorted(x for x in lengths if not ctx.max_model_len or x <= ctx.max_model_len)


def check_needle(ctx: Ctx):
    lengths = resolve_needle_lengths(ctx)
    if not lengths:
        raise CheckError("no needle lengths to probe", kind="error")
    per: dict[str, dict] = {}
    verdict = "ok"
    for length in lengths:
        name = f"needle-{length}"
        cmd = [ctx.python, ctx.tool("needle-haystack.py"),
               "--model", ctx.model or "auto",
               "--api-endpoint", ctx.base,
               "--context-length", str(length),
               "--depths", ctx.args.needle_depths,
               "--needles-per-depth", "1",
               "--max-tokens", str(ctx.args.needle_max_tokens),
               "--timeout", str(int(ctx.args.timeout)),
               "--json", f"{name}.json"]
        rc, _log = run_cmd(ctx, name, cmd, ctx.args.job_timeout)
        entry: dict = {"rc": rc}
        try:
            art = load_json(ctx.path(f"{name}.json"))
            depths = art.get("depths") or []
            entry.update({
                "verdict": art.get("verdict"),
                "hits": sum(d.get("hits", 0) for d in depths),
                "of": sum(d.get("of", 0) for d in depths),
                "max_prompt_tokens": max((d.get("prompt_tokens") or 0)
                                         for d in depths) if depths else None,
            })
        except (OSError, ValueError):
            entry["verdict"] = "no-artifact"
        per[str(length)] = entry
        if rc == 3 or entry.get("verdict") not in (None, "PASS"):
            verdict = "fail"
        elif rc is None or rc not in (0,):
            verdict = "error" if verdict != "fail" else verdict
        if rc not in (0, 3):
            verdict = "error" if verdict != "fail" else verdict
    headline = " ".join(f"{k}:{v.get('hits')}/{v.get('of')}"
                        for k, v in per.items())
    return verdict, headline, per


def check_hard(ctx: Ctx):
    if not ctx.model:
        raise CheckError("no served model resolved (run the contract check first)", kind="error")
    outdir = ctx.path("hard")
    os.makedirs(outdir, exist_ok=True)
    benches = [b.strip() for b in ctx.args.hard_bench.split(",") if b.strip()]
    if not benches:
        raise CheckError("--hard-bench is empty", kind="error")
    for bench in benches:
        # One process per bench: run_benchmarks takes a SINGLE --bench choice
        # (house|gsm8k|arc|all) and keys its _raw/<stem>.jsonl per bench, so a
        # comma list passed through as one argv element dies with
        # "invalid choice: 'gsm8k,arc'".
        cmd = [ctx.python, ctx.run_benchmarks,
               "--base-url", ctx.base, "--model", ctx.model,
               "--bench", bench,
               "--limit", str(ctx.args.hard_limit),
               "--seed", str(ctx.args.hard_seed),
               "--outdir", outdir]
        if ctx.args.hard_thinking:
            cmd += ["--thinking", ctx.args.hard_thinking]
        if ctx.args.hard_reasoning_effort:
            cmd += ["--reasoning-effort", ctx.args.hard_reasoning_effort]
        if ctx.args.hard_extra:
            cmd += ctx.args.hard_extra.split()
        rc, log = run_cmd(ctx, f"hard-{bench}", cmd, ctx.args.job_timeout)
        if rc is None:
            raise CheckError(f"run_benchmarks --bench {bench} did not run ({log_tail(log)})",
                             kind="error")
        if rc != 0:
            raise CheckError(f"run_benchmarks --bench {bench} exit {rc} ({log_tail(log)})",
                             kind="error")
    art = {}
    for name in sorted(os.listdir(outdir)):
        if not name.endswith(".json") or name.startswith("_"):
            continue
        try:
            d = load_json(os.path.join(outdir, name))
        except (OSError, ValueError):
            continue
        if not isinstance(d, dict) or "pct" not in d:
            continue
        art[d.get("bench") or name[:-5]] = {
            "pct": d.get("pct"), "correct": d.get("correct"), "n": d.get("n"),
            "finish_reasons": d.get("finish_reasons"),
            "empty_replies": d.get("empty_replies"),
            "reasoning_effort": d.get("reasoning_effort"),
        }
    if not art:
        raise CheckError("run_benchmarks wrote no summary JSON", kind="error")
    return "ok", " ".join(f"{b}:{v['pct']:.1f}% (n={v['n']})" for b, v in art.items()), art


def check_tools(ctx: Ctx):
    if not ctx.args.bfcl_data_dir:
        return ("skip",
                ("no --bfcl-data-dir (fetch: hf download gorilla-llm/"
                 "Berkeley-Function-Calling-Leaderboard --repo-type dataset "
                 "--revision 61fc0608 --local-dir ~/bfcl)"), {})
    cmd = [ctx.python, ctx.tool("bfcl-eval.py"),
           "--base-url", ctx.base, "--data-dir", ctx.args.bfcl_data_dir,
           "--max-tokens", str(ctx.args.bfcl_max_tokens),
           "--json", "bfcl.json"]
    if ctx.args.bfcl_categories:
        cmd += ["--categories", ctx.args.bfcl_categories]
    if ctx.args.bfcl_extra:
        cmd += ctx.args.bfcl_extra.split()
    rc, log = run_cmd(ctx, "bfcl", cmd, ctx.args.job_timeout)
    if rc is None:
        raise CheckError(f"bfcl-eval did not run ({log_tail(log)})", kind="error")
    if rc != 0:
        raise CheckError(f"bfcl-eval exit {rc} ({log_tail(log)})", kind="error")
    art = load_json(ctx.path("bfcl.json"))
    overall = art.get("overall") or {}
    if not overall.get("total"):
        raise CheckError("bfcl artifact scored no questions", kind="fail")
    headline = f"overall {overall.get('pct'):.1f}% ({overall.get('correct')}/{overall.get('total')})"
    if art.get("transport_errors"):
        headline += f" transport_errors={art['transport_errors']}"
    return "ok", headline, {"overall": overall,
                            "summary": {k: {kk: vv for kk, vv in v.items()}
                                        for k, v in (art.get("summary") or {}).items()},
                            "transport_errors": art.get("transport_errors"),
                            "skipped_unsupported": art.get("skipped_unsupported")}


def check_horizon(ctx: Ctx):
    turns = ctx.args.horizon_turns
    cmd = [ctx.python, ctx.tool("agentic-horizon-probe.py"),
           "--family", ctx.args.horizon_family,
           "--base-url", ctx.base, "--out", "horizon.jsonl",
           "--temperature", str(ctx.args.horizon_temperature),
           "--max-tokens", str(ctx.args.horizon_max_tokens),
           "--turns", str(turns), "--steps-per-turn", "3",
           "--max-calls", str(3 * turns)]
    if ctx.model:
        cmd += ["--model", ctx.model]
    rc, log = run_cmd(ctx, "horizon", cmd, ctx.args.job_timeout)
    if rc is None:
        raise CheckError(f"horizon probe did not run ({log_tail(log)})", kind="error")
    if rc != 0:
        raise CheckError(f"horizon probe exit {rc} ({log_tail(log)})", kind="error")
    run_cmd(ctx, "horizon-analyze",
            [ctx.python, ctx.tool("horizon-analyze.py"), "horizon.jsonl"],
            ctx.args.job_timeout)
    try:
        summ = load_json(ctx.path("horizon.jsonl.summary.json"))
    except (OSError, ValueError):
        raise CheckError("horizon probe wrote no summary", kind="error")
    session = summ.get("session") or {}
    art = {
        "family": summ.get("family"),
        "sampling": summ.get("sampling"),
        "max_prompt_tokens": summ.get("max_prompt_tokens"),
        "session_max_window_repeat": session.get("max_window_repeat"),
        "session_words": session.get("words"),
        "plan_valid": bool(summ.get("plan")),
        "elapsed_s": summ.get("elapsed_s"),
    }
    headline = (f"session repeat max={art['session_max_window_repeat']} "
                f"max_prompt_tokens={art['max_prompt_tokens']} "
                f"plan_valid={art['plan_valid']}")
    return "ok", headline, art


CHECKS = {
    "contract": check_contract,
    "house": check_house,
    "needle": check_needle,
    "hard": check_hard,
    "tools": check_tools,
    "horizon": check_horizon,
}


# ---------------------------------------------------------------------------
# plan / run / summary

def expand_checks(raw: str) -> list[str]:
    if raw.strip().lower() == "all":
        return list(ALL_CHECKS)
    names = [x.strip() for x in raw.split(",") if x.strip()]
    unknown = [x for x in names if x not in CHECKS]
    if unknown:
        raise ValueError(f"unknown check(s): {', '.join(unknown)} (have {', '.join(ALL_CHECKS)})")
    return names


def run_suite(args) -> int:
    ctx = Ctx(args)
    print(f"[suite {VERSION}] {ctx.base} -> {ctx.outdir}")
    results: dict[str, dict] = {}
    for name in args.checks:
        t0 = time.time()
        try:
            verdict, headline, art = CHECKS[name](ctx)
        except CheckError as exc:
            verdict, headline, art = exc.kind, str(exc), {}
        except Exception as exc:  # noqa: BLE001
            verdict, headline, art = "error", f"{type(exc).__name__}: {exc}", {}
        results[name] = {"verdict": verdict, "headline": headline,
                         "seconds": round(time.time() - t0, 1), "artifact": art}
        print(f"[{verdict:5s}] {name:8s} {headline}  ({results[name]['seconds']}s)")

    payload = {
        "suite": {"name": "eval-suite", "version": VERSION,
                  "sha256": sha256_file(os.path.abspath(__file__)),
                  "argv": sys.argv[1:]},
        "started_utc": ctx.started,
        "finished_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "base_url": ctx.base,
        "model": ctx.model,
        "checks": results,
        "verdict": ("fail" if any(r["verdict"] in ("fail", "error") for r in results.values())
                    else "ok"),
    }
    with open(ctx.path("summary.json"), "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1)
    with open(ctx.path("summary.md"), "w", encoding="utf-8") as fh:
        fh.write(f"# eval-suite {VERSION} — {ctx.model or 'unknown model'}\n\n")
        fh.write(f"- endpoint: `{ctx.base}`\n- started: {ctx.started}\n")
        fh.write(f"- suite sha256: `{payload['suite']['sha256']}`\n")
        fh.write(f"- argv: `{' '.join(payload['suite']['argv'])}`\n\n")
        fh.write("| check | verdict | headline | artifact |\n|---|---|---|---|\n")
        for name, r in results.items():
            fh.write(f"| {name} | {r['verdict']} | {r['headline']} | `{name}` |\n")
    print(f"[suite] verdict {payload['verdict']} -> {ctx.path('summary.json')}")
    return 0 if payload["verdict"] == "ok" else 1


# ---------------------------------------------------------------------------
# selftest: stub tools + a mock endpoint prove the plan/verdict/summary path

_STUB = '''#!/usr/bin/env python3
import json, os, sys
mode = {mode!r}
argv = sys.argv[1:]
def opt(name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default
if mode == "house":
    json.dump({{"model": "mock", "tiers": {{"easy": {{"correct": 19, "total": 19}},
                                           "hard": {{"correct": 18, "total": 18}}}}}},
              open("house.json", "w"))
elif mode == "needle":
    json.dump({{"verdict": {nverdict!r}, "max_model_len": 32768,
               "depths": [{{"depth": 30, "requested": 32768, "prompt_tokens": 32700,
                            "hits": {nhits}, "of": 1, "latency_s": 1.0}}]}},
              open(opt("--json", "needle.json"), "w"))
    sys.exit({nrc})
elif mode == "hard":
    bench = opt("--bench", "gsm8k")
    os.makedirs(opt("--outdir", "hard"), exist_ok=True)
    json.dump({{"bench": bench, "pct": 62.5, "correct": 125, "n": 200,
               "finish_reasons": {{"stop": 200}}, "empty_replies": 0}},
              open(os.path.join(opt("--outdir", "hard"), "mock." + bench + ".json"), "w"))
elif mode == "bfcl":
    json.dump({{"overall": {{"correct": 4, "total": 5, "pct": 80.0}}, "summary": {{}},
               "transport_errors": 0, "skipped_unsupported": 0}},
              open("bfcl.json", "w"))
elif mode == "probe":
    json.dump({{"ok": True}}, open("horizon.jsonl", "w"))
    json.dump({{"family": "plan", "sampling": {{"temperature": 0.6}},
               "max_prompt_tokens": 1234, "session": {{"max_window_repeat": 1, "words": 400}},
               "plan": True, "elapsed_s": 1.0}},
              open("horizon.jsonl.summary.json", "w"))
elif mode == "analyze":
    print("mock analysis")
'''


def _mock_handler(payload: dict):
    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # quiet
            pass

        def _send(self, obj):
            body = json.dumps(obj).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            self._send({"object": "list", "data": [{"id": "mock-model", "max_model_len": 32768}]})

        def do_POST(self):
            self._send({"choices": [{"message": {"content": "READY"}, "finish_reason": "stop"}],
                        "usage": {"prompt_tokens": 12, "completion_tokens": 1}})

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    payload["port"] = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def selftest() -> int:
    failures: list[str] = []
    assert expand_checks("all") == list(ALL_CHECKS), "all must expand to every check"
    if served_window({"id": "m", "max_model_len": 32768}) != 32768:
        failures.append("served_window must read vLLM's max_model_len")
    if served_window({"id": "m", "meta": {"n_ctx": 131072}}) != 131072:
        failures.append("served_window must read llama.cpp's meta.n_ctx")
    if served_window({"id": "m", "meta": {"n_vocab": 98304}}) is not None:
        failures.append("served_window must stay None when no window is advertised")
    try:
        expand_checks("contract,nope")
        failures.append("unknown check should raise")
    except ValueError:
        pass

    with tempfile.TemporaryDirectory() as tmp:
        tools = os.path.join(tmp, "tools")
        os.makedirs(tools)
        specs = {"quality-battery.py": ("house", "PASS", 0, 1),
                 "needle-haystack.py": ("needle", "PASS", 0, 1),
                 "bfcl-eval.py": ("bfcl", "PASS", 0, 1),
                 "agentic-horizon-probe.py": ("probe", "PASS", 0, 1),
                 "horizon-analyze.py": ("analyze", "PASS", 0, 1),
                 "run_benchmarks.py": ("hard", "PASS", 0, 1)}
        for fname, (mode, nverdict, nrc, nhits) in specs.items():
            with open(os.path.join(tools, fname), "w") as fh:
                fh.write(_STUB.format(mode=mode, nverdict=nverdict, nrc=nrc, nhits=nhits))
        payload: dict = {}
        srv = _mock_handler(payload)
        base = f"http://127.0.0.1:{payload['port']}"
        outdir = os.path.join(tmp, "receipt")
        argv = ["--base-url", base, "--checks", "all", "--outdir", outdir,
                "--tools-dir", tools, "--bfcl-data-dir", tmp,
                "--needle-lengths", "32768", "--house-max-tokens", "64",
                "--run-benchmarks", os.path.join(tools, "run_benchmarks.py"),
                "--label", "mock"]
        rc = main(argv)
        if rc != 0:
            failures.append(f"mock run should exit 0, got {rc}")
        summary = load_json(os.path.join(outdir, "summary.json"))
        if summary["checks"]["house"]["headline"] != "easy 19/19 hard 18/18":
            failures.append(f"house headline wrong: {summary['checks']['house']['headline']}")
        if summary["checks"]["tools"]["headline"].startswith("no --bfcl-data-dir"):
            failures.append("tools check skipped despite --bfcl-data-dir")
        if summary["checks"]["needle"]["verdict"] != "ok":
            failures.append("needle stub should be ok")
        # One instrument process per --hard-bench entry: the default comma list
        # must yield one artifact per bench, not one process fed "gsm8k,arc".
        if set(summary["checks"]["hard"]["artifact"]) != {"gsm8k", "arc"}:
            failures.append("hard check must run one instrument process per --hard-bench entry: "
                            f"got {sorted(summary['checks']['hard']['artifact'])}")

        # the failing-instrument path must map to fail and a non-zero exit
        for fname in ("needle-haystack.py",):
            with open(os.path.join(tools, fname), "w") as fh:
                fh.write(_STUB.format(mode="needle", nverdict="FAIL", nrc=3, nhits=0))
        outdir2 = os.path.join(tmp, "receipt-fail")
        rc2 = main(["--base-url", base, "--checks", "contract,needle",
                                "--needle-lengths", "32768", "--tools-dir", tools,
                                "--outdir", outdir2])
        if rc2 != 1:
            failures.append(f"failing needle should exit 1, got {rc2}")
        s2 = load_json(os.path.join(outdir2, "summary.json"))
        if s2["checks"]["needle"]["verdict"] != "fail":
            failures.append("failing needle should map to verdict fail")
        srv.shutdown()
    for f in failures:
        print(f"[selftest] FAIL: {f}")
    print("SELFTEST PASS" if not failures else "SELFTEST FAIL")
    return 0 if not failures else 1


# ---------------------------------------------------------------------------
# cli

def _parse(argv) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base-url", required=True, help="OpenAI-compatible endpoint root")
    ap.add_argument("--model", default="auto", help="served model id, or 'auto'")
    ap.add_argument("--label", default=None, help="outdir slug (default: the model id)")
    ap.add_argument("--outdir", default=None, help="receipt directory to create")
    ap.add_argument("--checks", default=",".join(DEFAULT_CHECKS),
                    help="comma list or 'all': " + ",".join(ALL_CHECKS))
    ap.add_argument("--python", default=sys.executable, help="interpreter for the instruments")
    ap.add_argument("--tools-dir", default=None, help="where the instruments live (default: beside this file)")
    ap.add_argument("--run-benchmarks", default=os.path.join(REPO, "recipes", "ds4",
                                                             "benchmarks", "run_benchmarks.py"))
    ap.add_argument("--timeout", type=float, default=900.0, help="per-request timeout handed to the tools")
    ap.add_argument("--job-timeout", type=float, default=7200.0, help="per-check wall-clock cap")
    # house
    ap.add_argument("--house-tier", default="both", choices=["easy", "hard", "both"])
    ap.add_argument("--house-repeat", type=int, default=1)
    ap.add_argument("--house-max-tokens", type=int, default=4096)
    # needle
    ap.add_argument("--needle-lengths", default="auto")
    ap.add_argument("--needle-depths", default="10,50,90")
    ap.add_argument("--needle-max-tokens", type=int, default=256)
    # hard
    ap.add_argument("--hard-bench", default="gsm8k,arc")
    ap.add_argument("--hard-limit", type=int, default=200)
    ap.add_argument("--hard-seed", type=int, default=1234)
    ap.add_argument("--hard-thinking", default=None, choices=[None, "on", "off"])
    ap.add_argument("--hard-reasoning-effort", default=None,
                    choices=[None, "default", "high", "medium", "low"])
    ap.add_argument("--hard-extra", default=None, help="raw extra argv for run_benchmarks")
    # tools
    ap.add_argument("--bfcl-data-dir", default=None)
    ap.add_argument("--bfcl-categories", default=None, help="raw --categories value")
    ap.add_argument("--bfcl-max-tokens", type=int, default=4096,
                    help="completion budget for the tools leg (bfcl-eval's own default is 512)")
    ap.add_argument("--bfcl-extra", default=None,
                    help="raw extra argv for bfcl-eval, appended last (so it can override "
                         "--bfcl-max-tokens)")
    # horizon
    ap.add_argument("--horizon-family", default="plan", choices=["plan", "repo"])
    ap.add_argument("--horizon-turns", type=int, default=12)
    ap.add_argument("--horizon-max-tokens", type=int, default=16384)
    ap.add_argument("--horizon-temperature", type=float, default=0.6)
    return ap.parse_args(argv)


def main(argv=None) -> int:
    args = _parse(argv)
    try:
        args.checks = expand_checks(args.checks)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return run_suite(args)


if __name__ == "__main__":
    if "--selftest" in sys.argv[1:]:
        sys.exit(selftest())
    sys.exit(main())