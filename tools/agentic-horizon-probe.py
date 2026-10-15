#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Travis Wichert
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Long-horizon agentic loop probe for the Ornith 1.5 35B SGLang lane (Plan C, C1/C3).

The 2026-10-13 investigation drove nine *single-turn* reasoning prompts and found
zero repeated-window runs; the owner does not accept that as evidence about
long-horizon agentic behaviour ("it loops while reasoning on long-horizon
agentic workloads"). This probe drives the workload the report is about: a
multi-turn tool-calling session with a *growing transcript* over a sequence of
near-duplicate work items, scored per turn for a reasoning loop / degradation.

Two task families (--family):
  repo  a trivial read/patch/verify tool loop. Control: elicits almost no CoT.
  plan  an INCREMENTAL constraint-scheduling agent: each turn adds one
        requirement to a growing set and the agent must re-derive a valid
        execution order over all jobs, using tools to fetch the current state.
        Constraint enumeration is the shape that made this model reason for
        3900+ words in the 2026-10-13 single-turn probe, so this is the family
        that actually exercises long CoT with a growing context.

Degradation detector (all over the assistant reasoning channel):
  * loop metric: max count of any single 25-word window within one message
    (1 == every window unique) -- the ds4 stability metric.
  * session max_window_repeat: the same metric over ALL reasoning concatenated
    in turn order -- catches a loop that only appears across turns.
  * prior_shingle_overlap: fraction of a message's 8-word shingles already seen
    in earlier turns' reasoning. ->1 means the model is replaying earlier CoT
    (a near-duplicate-task loop); ~0 means novel reasoning.
  * finish_reason is recorded so a budget truncation (length) is separable
    from a loop.

Usage:
  python3 agentic-horizon-probe.py --base-url http://127.0.0.1:8000 \
      --family plan --temperature 0.6 --max-tokens 16384 \
      --turns 16 --steps-per-turn 3 --out horizon-plan-temp06-16k.jsonl

  # Offline check -- no GPU and no endpoint needed, only localhost:
  python3 agentic-horizon-probe.py --selftest
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

WINDOW = 25          # intra-message loop window (ds4 template)
SHINGLE = 8          # cross-turn replay shingle


# ---------------------------------------------------------------------------
# loop / degradation metrics
# ---------------------------------------------------------------------------
def _words(text: str) -> list[str]:
    return re.findall(r"\S+", text)


def windows(text: str, w: int = WINDOW) -> list[str]:
    ws = _words(text)
    if len(ws) < w:
        return []
    return [" ".join(ws[i:i + w]) for i in range(len(ws) - w + 1)]


def shingles(text: str, w: int = SHINGLE) -> set[str]:
    ws = _words(text)
    if len(ws) < w:
        return set()
    return {" ".join(ws[i:i + w]) for i in range(len(ws) - w + 1)}


def loop_metric(text: str) -> dict:
    ws = windows(text)
    words = _words(text)
    n = len(words)
    out = {"words": n, "windows": len(ws), "max_window_repeat": 1,
           "distinct_word_ratio": round(len(set(words)) / n, 4) if n else 0.0}
    if ws:
        seen: dict[str, int] = {}
        for k in ws:
            seen[k] = seen.get(k, 0) + 1
        out["max_window_repeat"] = max(seen.values())
    return out


# ---------------------------------------------------------------------------
# Task family: incremental constraint scheduling ("plan")
# ---------------------------------------------------------------------------
_TEMPLATES = [
    "J{i} must run after J{i-1}",
    "J{i} must run before J{i-1}",
    "J{i} must run after J0",
    "J{i} must run after J1",
    "J{i} must run before J2",
    "J{i} must not run immediately after J{i-1}",
]


def constraint_text(i: int) -> str:
    if i < 2:
        return "J1 must run after J0" if i == 1 else ""
    return _TEMPLATES[i % len(_TEMPLATES)].replace("{i-1}", str(i - 1)).replace("{i}", str(i))


def parse_after_before(c: str) -> tuple[str, str, str] | None:
    """Return (kind, a, b) with an ordering J_a <KIND> J_b, or None."""
    m = re.match(r"(J\d+) must run (after|before) (J\d+)", c)
    if m:
        return ("after" if m.group(2) == "after" else "before", m.group(1), m.group(3))
    m = re.match(r"(J\d+) must not run immediately after (J\d+)", c)
    if m:
        return ("notafter", m.group(1), m.group(2))
    return None


class PlanEnv:
    def __init__(self, max_jobs: int) -> None:
        self.max_jobs = max_jobs

    def constraints(self, upto: int) -> list[str]:
        return [constraint_text(i) for i in range(1, upto + 1)]

    def check(self, order: list[str], upto: int) -> str:
        if sorted(order) != sorted(f"J{i}" for i in range(upto + 1)):
            return (f"INVALID: order must be a permutation of "
                    f"{', '.join('J%d' % i for i in range(upto + 1))}")
        pos = {j: k for k, j in enumerate(order)}
        for c in self.constraints(upto):
            p = parse_after_before(c)
            if not p:
                continue
            kind, a, b = p
            if kind == "after" and not pos[a] > pos[b]:
                return f"INVALID: '{c}' violated"
            if kind == "before" and not pos[a] < pos[b]:
                return f"INVALID: '{c}' violated"
            if kind == "notafter" and pos[a] == pos[b] + 1:
                return f"INVALID: '{c}' violated"
        return "VALID: all requirements 1..%d satisfied" % upto


PLAN_TOOLS = [
    {"type": "function", "function": {
        "name": "list_jobs",
        "description": "List every job that must be scheduled (J0..Jn).",
        "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {
        "name": "get_requirements",
        "description": "Return the full list of ordering requirements issued so far.",
        "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {
        "name": "submit_plan",
        "description": "Submit a candidate execution order for validation.",
        "parameters": {"type": "object", "properties": {
            "order": {"type": "array", "items": {"type": "string"}}},
            "required": ["order"]}}},
]

PLAN_SYSTEM = (
    "You are a scheduling agent. A backlog of jobs J0..Jn must run in some total "
    "order subject to a growing list of ordering requirements. You have tools: "
    "list_jobs, get_requirements, submit_plan. For each work item: fetch the job "
    "list and the current requirements, reason carefully about an order that "
    "satisfies every requirement, submit it with submit_plan, then reply with the "
    "single line 'WORK ITEM <n> DONE'. Think step by step; do not ask questions."
)

_PLAN_VARIATIONS = [
    "Work item {i}: requirement #{i} has arrived: {c}. Re-plan the FULL execution "
    "order of all jobs J0..J{i} so every requirement 1..{i} holds. Fetch the job "
    "list and requirements with your tools, reason about the ordering, submit your "
    "plan, then reply exactly: WORK ITEM {i} DONE",
    "Work item {i}: a new constraint {c} has been added. Work out a valid order for "
    "J0..J{i} that satisfies all constraints so far. Use the tools to read the "
    "current state, submit your plan, then reply exactly: WORK ITEM {i} DONE",
    "Work item {i}: scheduling update - {c}. Derive an execution order for all jobs "
    "J0..J{i} obeying every requirement to date. Check the state with your tools, "
    "submit the plan, then reply exactly: WORK ITEM {i} DONE",
]


def plan_user_turn(i: int) -> str:
    c = constraint_text(i)
    return _PLAN_VARIATIONS[i % len(_PLAN_VARIATIONS)].format(i=i, c=c)


# ---------------------------------------------------------------------------
# Task family: trivial read/patch/verify tool loop ("repo"), a control
# ---------------------------------------------------------------------------
def mod_src(i: int) -> str:
    return (f"# module {i}\ndef add_one(x):\n    return x + 1  # BUG\n")


REPO_TOOLS = [
    {"type": "function", "function": {
        "name": "list_files", "description": "List repository files.",
        "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {
        "name": "read_file", "description": "Read a file.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "run_tests", "description": "Run a module's test.",
        "parameters": {"type": "object", "properties": {
            "module": {"type": "string"}}, "required": ["module"]}}},
    {"type": "function", "function": {
        "name": "apply_patch", "description": "Patch a file. Args: path, patch.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"}, "patch": {"type": "string"}},
            "required": ["path", "patch"]}}},
]

REPO_SYSTEM = (
    "You are an autonomous coding agent. Tools: list_files, read_file, run_tests, "
    "apply_patch. For each work item: read the module, run its test, apply a patch "
    "that makes the test pass, confirm, then reply with the single line "
    "'WORK ITEM <n> DONE'. Think step by step. Do not ask questions."
)


class RepoEnv:
    def __init__(self) -> None:
        self.files: dict[str, str] = {}
        self.patched: set[int] = set()

    def build(self, n: int) -> None:
        for i in range(n):
            self.files[f"mod_{i}.py"] = mod_src(i)
            self.files[f"test_mod_{i}.py"] = f"assert add_one(0) == 0  # test_mod_{i}\n"

    def list_files(self, _a): return "\n".join(sorted(self.files))
    def read_file(self, a):
        p = str(a.get("path", ""))
        return self.files.get(p, f"ERROR: no such file: {p}")
    def run_tests(self, a):
        m = str(a.get("module", "")).removeprefix("mod_").removesuffix(".py")
        try: i = int(m)
        except ValueError: return f"ERROR: unknown module {m!r}"
        return (f"PASS: test_mod_{i} OK" if i in self.patched
                else f"FAIL: test_mod_{i}\n  assert add_one(0) == 0 -> got 1")
    def apply_patch(self, a):
        m = re.search(r"mod_(\d+)", str(a.get("path", "")))
        if not m: return "ERROR: cannot parse module"
        i = int(m.group(1)); self.patched.add(i); return f"APPLIED: mod_{i}.py patched"


def repo_user_turn(i: int) -> str:
    return (f"Work item {i}: the test for module mod_{i} is failing. Read mod_{i}.py, "
            f"run its test, apply a patch so it passes. Finish with exactly: "
            f"WORK ITEM {i} DONE")


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------
def post(url: str, payload: dict, timeout: int) -> dict:
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def call(base: str, model: str, messages: list, args, tools: list, timeout: int) -> dict:
    body = {"model": model, "messages": messages, "tools": tools,
            "tool_choice": "auto", "temperature": args.temperature,
            "top_p": args.top_p, "top_k": args.top_k, "max_tokens": args.max_tokens}
    if args.presence_penalty:
        body["presence_penalty"] = args.presence_penalty
    if args.thinking:
        body["chat_template_kwargs"] = {"enable_thinking": True}
    if args.seed is not None:
        body["seed"] = args.seed
    return post(base.rstrip("/") + "/v1/chat/completions", body, timeout)


# ---------------------------------------------------------------------------
def _selftest() -> int:
    """Offline self-test: serve a mock OpenAI-compatible endpoint on localhost,
    drive this script against it with --family repo for 3 turns, and assert the
    transcript the probe builds is structure-valid. No GPU, no remote host."""
    role_logs: list[list[dict]] = []
    good = [False]

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):  # silence
            pass

        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n) or b"{}")
            msgs = body.get("messages", [])
            role_logs.append([{"role": m["role"],
                               "has_tool_calls": bool(m.get("tool_calls")),
                               "tool_call_id": bool(m.get("tool_call_id"))}
                              for m in msgs])
            last = msgs[-1] if msgs else {}
            # every assistant with tool_calls must be followed by exactly as
            # many tool messages as tool_calls, each with a matching id
            ok = True
            i = 0
            while i < len(msgs):
                if msgs[i]["role"] == "assistant" and msgs[i].get("tool_calls"):
                    k = len(msgs[i]["tool_calls"])
                    ids = [t["id"] for t in msgs[i]["tool_calls"]]
                    j = i + 1
                    while j < len(msgs) and msgs[j]["role"] == "tool":
                        if msgs[j].get("tool_call_id") not in ids:
                            ok = False
                        j += 1
                    if j - (i + 1) != k:
                        ok = False
                    i = j
                else:
                    i += 1
            good[0] = good[0] or ok

            if last.get("role") == "user":
                msg = {"role": "assistant", "content": "",
                       "reasoning_content": "I should read the module first. " * 4,
                       "tool_calls": [{"id": "call_1", "type": "function",
                                       "function": {"name": "read_file",
                                                    "arguments": json.dumps(
                                                        {"path": "mod_0.py"})}}]}
                fin = "tool_calls"
            else:
                msg = {"role": "assistant",
                       "content": "WORK ITEM 0 DONE",
                       "reasoning_content": "The test now passes. " * 4}
                fin = "stop"
            out = {"choices": [{"message": msg, "finish_reason": fin}],
                   "usage": {"prompt_tokens": 10, "completion_tokens": 5}}
            b = json.dumps(out).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    with tempfile.TemporaryDirectory() as td:
        out_path = os.path.join(td, "probe-selftest.jsonl")
        rc = subprocess.run(
            [sys.executable, "-B", os.path.abspath(__file__),
             "--family", "repo", "--base-url", f"http://127.0.0.1:{port}",
             "--turns", "3", "--steps-per-turn", "3", "--max-tokens", "256",
             "--out", out_path],
            capture_output=True, text=True, check=False)
        srv.shutdown()
        print("probe rc", rc.returncode)
        print(rc.stderr[-1500:])
        rows = [json.loads(l) for l in open(out_path)]
        print("rows", len(rows))
        print("summary:", json.dumps(
            json.load(open(out_path + ".summary.json"))["session"]))
        assert rc.returncode == 0, "probe failed"
        assert all(r.get("error") is None for r in rows), "probe recorded an error"
        assert good[0], "tool_calls/tool-result structure invalid in some request"
        assert len(rows) == 6, f"expected 3 turns x 2 calls, got {len(rows)}"
        assert rows[0]["n_tool_calls"] == 1 and rows[1]["n_tool_calls"] == 0
    print("SELFTEST PASS")
    return 0


# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--selftest", action="store_true",
                    help="run the offline mock-endpoint self-test and exit")
    ap.add_argument("--base-url")
    ap.add_argument("--model", default="ornith-ai/Ornith-1.5-35B-A3B-NVFP4")
    ap.add_argument("--family", choices=("plan", "repo"), default="plan")
    ap.add_argument("--temperature", type=float, default=0.6)
    ap.add_argument("--top-p", type=float, default=0.95)
    ap.add_argument("--top-k", type=int, default=20)
    ap.add_argument("--presence-penalty", type=float, default=0.0)
    ap.add_argument("--max-tokens", type=int, default=16384)
    ap.add_argument("--turns", type=int, default=16)
    ap.add_argument("--steps-per-turn", type=int, default=3)
    ap.add_argument("--max-calls", type=int, default=60)
    ap.add_argument("--thinking", action=argparse.BooleanOptionalAction, default=True)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--excerpt-chars", type=int, default=800)
    ap.add_argument("--out")
    args = ap.parse_args()

    if args.selftest:
        return _selftest()
    if not args.base_url or not args.out:
        ap.error("--base-url and --out are required")

    if args.family == "plan":
        env = PlanEnv(args.turns)
        tools, system = PLAN_TOOLS, PLAN_SYSTEM
        user_turn = plan_user_turn
        plan = None
    else:
        env = RepoEnv(); env.build(args.turns)
        tools, system = REPO_TOOLS, REPO_SYSTEM
        user_turn = repo_user_turn
        plan = None

    messages = [{"role": "system", "content": system}]
    prior_shi: set[str] = set()
    prior_win: set[str] = set()
    calls = 0
    all_reasoning: list[str] = []
    input_texts: list[str] = []
    summary = {"arm": args.out, "family": args.family, "sampling": {
        "temperature": args.temperature, "top_p": args.top_p, "top_k": args.top_k,
        "presence_penalty": args.presence_penalty, "max_tokens": args.max_tokens,
        "enable_thinking": args.thinking}, "turns": args.turns, "messages": [],
        "max_prompt_tokens": 0, "total_completion_tokens": 0}
    t_start = time.time()

    with open(args.out, "w") as fh:
        for turn in range(args.turns):
            ucontent = user_turn(turn)
            messages.append({"role": "user", "content": ucontent})
            input_texts.append(ucontent)
            for step in range(args.steps_per_turn):
                if calls >= args.max_calls:
                    break
                calls += 1
                t0 = time.time()
                try:
                    out = call(args.base_url, args.model, messages, args, tools, args.timeout)
                except urllib.error.HTTPError as e:
                    fh.write(json.dumps({"turn": turn, "step": step,
                        "error": f"HTTP {e.code}: {e.read().decode()[:300]}"}) + "\n")
                    break
                except Exception as e:  # noqa: BLE001
                    fh.write(json.dumps({"turn": turn, "step": step,
                        "error": f"{type(e).__name__}: {e}"}) + "\n")
                    break
                ch = out["choices"][0]; msg = ch["message"]
                reasoning = msg.get("reasoning_content") or ""
                content = msg.get("content") or ""
                tool_calls = msg.get("tool_calls") or []
                full_results, tool_results = [], []
                for tc in tool_calls:
                    fn = tc.get("function", {}); name = fn.get("name", "")
                    try:
                        targs = json.loads(fn.get("arguments") or "{}")
                    except json.JSONDecodeError:
                        targs = {}
                    if args.family == "plan":
                        if name == "list_jobs":
                            res = " ".join(f"J{k}" for k in range(turn + 1))
                        elif name == "get_requirements":
                            res = "\n".join(env.constraints(turn)) or "(none yet)"
                        elif name == "submit_plan":
                            order = targs.get("order") or []
                            if not isinstance(order, list):
                                res = "ERROR: order must be a list of job names"
                            else:
                                res = env.check([str(x) for x in order], turn)
                                if res.startswith("VALID"):
                                    plan = [str(x) for x in order]
                                    summary["plan_valid_submits"] = summary.get("plan_valid_submits", 0) + 1
                                else:
                                    summary["plan_invalid_submits"] = summary.get("plan_invalid_submits", 0) + 1
                        else:
                            res = f"ERROR: unknown tool {name}"
                    else:
                        h = getattr(env, name, None)
                        res = h(targs) if h else f"ERROR: unknown tool {name}"
                    full_results.append(str(res))
                    tool_results.append({"name": name, "result": str(res)[:160]})
                blob = reasoning + "\n" + content
                lm = loop_metric(blob)
                sh = shingles(blob); win = set(windows(blob))
                overlap = (len(sh & prior_shi) / len(sh)) if sh else 0.0
                prior_shi |= sh; prior_win |= win
                all_reasoning.append(reasoning)
                usage = out.get("usage", {})
                summary["max_prompt_tokens"] = max(summary["max_prompt_tokens"],
                                                   usage.get("prompt_tokens", 0))
                summary["total_completion_tokens"] += usage.get("completion_tokens", 0)
                rec = {"turn": turn, "step": step, "finish_reason": ch.get("finish_reason"),
                       "usage": usage, "elapsed_s": round(time.time() - t0, 2),
                       "reasoning_chars": len(reasoning), "content_chars": len(content),
                       "n_tool_calls": len(tool_calls), "loop": lm,
                       "prior_shingle_overlap": round(overlap, 4),
                       "tool_results": tool_results,
                       "msg_sha256": hashlib.sha256(blob.encode()).hexdigest()[:16],
                       "reasoning_head": reasoning[:args.excerpt_chars],
                       "reasoning_tail": reasoning[-args.excerpt_chars:],
                       "content_head": content[:args.excerpt_chars]}
                fh.write(json.dumps(rec) + "\n"); fh.flush()
                summary["messages"].append({k: rec[k] for k in
                    ("turn", "step", "finish_reason", "n_tool_calls", "loop",
                     "prior_shingle_overlap", "msg_sha256")})
                print(f"turn {turn} step {step} finish={ch.get('finish_reason')} "
                      f"tools={len(tool_calls)} rchars={len(reasoning)} "
                      f"words={lm['words']} repeat={lm['max_window_repeat']} "
                      f"overlap={overlap:.2f}", file=sys.stderr)

                amsg = {"role": "assistant", "content": content}
                if reasoning:
                    amsg["reasoning_content"] = reasoning
                if tool_calls:
                    amsg["tool_calls"] = [
                        {"id": tc.get("id", ""), "type": tc.get("type", "function"),
                         "function": {"name": tc.get("function", {}).get("name", ""),
                                      "arguments": tc.get("function", {}).get("arguments", "{}")}}
                        for tc in tool_calls]
                messages.append(amsg)
                if not tool_calls:
                    break
                for tc, res in zip(tool_calls, full_results):
                    messages.append({"role": "tool",
                                     "tool_call_id": tc.get("id", ""), "content": res})
                    input_texts.append(res)

    # Session repeat, decomposed: a 25-word window that also occurs in an INPUT
    # (a user turn or a tool result the agent quoted back) is not a decode loop,
    # so report the max repeat over reasoning-only windows as well.
    from collections import Counter as _C
    input_win: set[str] = set()
    for t in input_texts:
        input_win |= set(windows(t))
    reason_win = windows("\n".join(all_reasoning))
    cc = _C(w for w in reason_win if w not in input_win)
    session = loop_metric("\n".join(all_reasoning))
    session["max_window_repeat_excl_input"] = max(cc.values()) if cc else 1
    session["top_repeated_windows"] = [
        {"count": c, "in_input": w in input_win, "text": w[:180]}
        for w, c in _C(reason_win).most_common(5)]
    summary["session"] = session
    summary["plan"] = plan
    summary["elapsed_s"] = round(time.time() - t_start, 1)
    summary["calls"] = calls
    with open(args.out + ".summary.json", "w") as sh:
        json.dump(summary, sh, indent=1)
    print(f"SESSION family={args.family} max_window_repeat={session['max_window_repeat']} "
          f"excl_input={session['max_window_repeat_excl_input']} words={session['words']} "
          f"calls={calls} max_prompt={summary['max_prompt_tokens']} "
          f"elapsed={summary['elapsed_s']}s", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
