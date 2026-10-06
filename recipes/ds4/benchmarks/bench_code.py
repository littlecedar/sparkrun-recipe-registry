#!/usr/bin/env python3
"""Code-execution benchmark harness (HumanEval + MBPP) for the ds4 endpoints.

This is the pass@1 counterpart to `run_benchmarks.py`: instead of comparing two
text answers to a gold string, it asks the model to write a Python function,
*executes* that function against the dataset's own tests, and scores the task
passed iff every assert exits 0 inside a bounded sandbox.  Same two endpoints,
same greedy config, same resumable output layout, so the results merge into the
existing `results/` tree and `compare_results.py` reads them unchanged.

Benchmarks
----------
* humaneval -- `openai/openai_humaneval`, config `openai_humaneval`, split `test`
               (164 rows).  The row prompt is a signature + docstring with no
               body; the row `test` defines `check(candidate)` and the canonical
               runner appends `check(<entry_point>)`.
* mbpp      -- `google-research-datasets/mbpp`, config `sanitized`, split `test`
               (257 rows).  `test_list` is a list of assert statements and
               `test_imports` the imports they need.

Datasets are staged by this file from the HuggingFace **datasets-server** `rows`
API (stdlib only -- no `datasets`/`pyarrow`), paginated 100 rows per call, into
`data_code/*.jsonl`.  Staging is idempotent and happens automatically when the
files are missing; `--stage` re-fetches.

Scoring
-------
The reply is parsed for a ```python fenced block (falling back to raw text),
spliced into an executable program, and run once.  pass@1 is binary per task:
all asserts must pass.  A HumanEval program is assembled as
`<row prompt> + <extracted> + <row test> + check(<entry_point>)`; because the
row prompt's function body is a bare docstring (valid Python), a full
redefinition from the model simply overrides the stub, and a bare indented body
completes it -- both splice correctly.  An MBPP program is
`<test_imports> + <extracted> + <test_list>`.

Sandbox
-------
Plain subprocess, no container.  Each task runs in a fresh temp dir via
`python -I candidate.py` with, in the child (`preexec_fn`):
  * RLIMIT_CPU   -- 10 s CPU (SIGXCPU/SIGKILL),
  * RLIMIT_AS    -- 2 GiB address space (runaway allocation -> MemoryError),
  * RLIMIT_CORE  -- 0 (no core dumps),
  * RLIMIT_FSIZE -- 16 MiB (no disk filling),
plus a 15 s wall-clock `subprocess` timeout and a throwaway cwd.

This is a **reliability** sandbox, not a security boundary: generated code runs
as the invoking user and can read/write the filesystem and, absent host
egress rules, the network.  It bounds runaway CPU/memory/time/disk, which is
what pass@1 fairness needs.  For a genuinely untrusted model, swap the executor
for a container, e.g.
`docker run --rm --network=none -i python:3.12-slim` (the project python is 3.14;
Docker 29.8 is available).  Container isolation was not chosen here because the
generated programs are pure and tiny, the image pull/startup cost dwarfs the
eval, and the stdlib route keeps the harness dependency-free like the rest of
this directory.

Thinking control
----------------
Like `run_benchmarks.py`, `chat_template_kwargs={"enable_thinking": false|true}`
is forced so the two deployments are compared in the same effective mode
(baseline `deepseek` defaults off, turbo defaults on).

Usage
-----
    python3 bench_code.py --base-url http://host:4000 --model deepseek \\
        --bench both --thinking off --limit 3 --seed 1234 --outdir results
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import resource
import subprocess
import sys
import tempfile
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data_code")
ROWS_API = "https://datasets-server.huggingface.co/rows"

CPU_SECONDS = 10        # RLIMIT_CPU (hard is +2 s)
WALL_SECONDS = 15       # subprocess wall-clock timeout
MEM_BYTES = 2 * 1024 ** 3
FSIZE_BYTES = 16 * 1024 ** 2
REPLY_CAP = 8000        # bound the stored reply; code rarely approaches this

# dataset key -> (urlencoded dataset, config, split, expected_rows, filename)
DATASETS = {
    "humaneval": ("openai%2Fopenai_humaneval", "openai_humaneval", "test", 164,
                  "humaneval_test.jsonl"),
    "mbpp": ("google-research-datasets%2Fmbpp", "sanitized", "test", 257,
             "mbpp_sanitized_test.jsonl"),
}


# --------------------------------------------------------------------------
# staging (HuggingFace datasets-server `rows` API, stdlib only)
# --------------------------------------------------------------------------
def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "ds4-code-bench/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def stage(bench: str, force: bool) -> int:
    """Fetch one dataset to data_code/<file>.jsonl.  Idempotent unless force."""
    ds, cfg, split, expected, fname = DATASETS[bench]
    out = os.path.join(DATA, fname)
    if os.path.exists(out) and not force:
        print(f"[skip] {out} exists")
        return 0
    total = None
    offset = 0
    n = 0
    with open(out, "w") as f:
        while True:
            url = (f"{ROWS_API}?dataset={ds}&config={cfg}&split={split}"
                   f"&offset={offset}&length=100")
            d = json.loads(_get(url))
            if total is None:
                total = d["num_rows_total"]
            rows = d["rows"]
            if not rows:
                break
            for r in rows:
                row = r["row"]
                if bench == "humaneval":
                    rec = {k: row[k] for k in
                           ("task_id", "prompt", "canonical_solution", "test", "entry_point")}
                else:
                    rec = {k: row[k] for k in
                           ("task_id", "prompt", "code", "test_imports", "test_list")}
                f.write(json.dumps(rec) + "\n")
                n += 1
            offset += len(rows)
            if offset >= total:
                break
    assert n == expected == total, f"{bench}: staged {n}, API total {total}, expected {expected}"
    print(f"[ok]   {out}: {n} rows")
    return n


def ensure_data(force: bool) -> None:
    os.makedirs(DATA, exist_ok=True)
    for bench in DATASETS:
        stage(bench, force)


# --------------------------------------------------------------------------
# transport
# --------------------------------------------------------------------------
def chat_url(base: str) -> str:
    b = base.rstrip("/")
    if b.endswith("/v1/chat/completions"):
        return b
    if b.endswith("/v1"):
        return b + "/chat/completions"
    return b + "/v1/chat/completions"


def chat(base: str, model: str, prompt: str, max_tokens: int, thinking: str):
    body = {"model": model, "messages": [{"role": "user", "content": prompt}],
            "temperature": 0, "max_tokens": max_tokens}
    if thinking in ("on", "off"):
        body["chat_template_kwargs"] = {"enable_thinking": thinking == "on"}
    req = urllib.request.Request(chat_url(base), data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=900) as r:
        out = json.load(r)
    msg = out["choices"][0]["message"]
    usage = out.get("usage", {}) or {}
    # NB: this gateway reports reasoning_tokens top-level; run_benchmarks.py only
    # looks under completion_tokens_details.  Accept either.
    reason = usage.get("reasoning_tokens")
    if reason is None:
        reason = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens")
    return (msg.get("content") or ""), {
        "elapsed": round(time.time() - t0, 2),
        "tokens": usage.get("completion_tokens"),
        "reasoning_tokens": reason,
        "finish_reason": out["choices"][0].get("finish_reason"),
    }


# --------------------------------------------------------------------------
# prompt building / code extraction / program assembly
# --------------------------------------------------------------------------
_FENCE = re.compile(r"```[ \t]*([A-Za-z0-9_+\-]*)[ \t]*\r?\n(.*?)```", re.DOTALL)
_FENCE_NL = re.compile(r"```(?:python|py|python3)?[ \t]+(.*?)```", re.DOTALL)

HE_INSTR = ("\nComplete the function body. Return ONLY the complete, runnable Python code "
            "(with any needed imports and the full function definition) inside a single "
            "```python code block. Do not include explanations or example usage.\n")
MBPP_INSTR = ("\n\nWrite a Python function that solves the above. Return ONLY the complete "
              "function definition inside a single ```python code block. Do not include "
              "example usage, print statements, or test code.\n")


def _mbpp_signature(task: dict) -> str:
    """The required `def name(...)` line from the reference solution.

    MBPP's prose prompt never names the function, but its asserts call a specific
    name -- so a correct function under a different name fails.  The canonical
    viable setup supplies the signature; we do the same, which is what makes MBPP
    discriminative rather than a name-guessing lottery.
    """
    m = re.search(r"^\s*def\s+([A-Za-z_]\w*)\s*\(([^)]*)\)", task.get("code", ""), re.MULTILINE)
    if not m:
        return ""
    return f"\nThe function must be named `{m.group(1)}` and take arguments ({m.group(2).strip()})."


def build_prompt(bench: str, task: dict) -> str:
    if bench == "humaneval":
        return task["prompt"] + HE_INSTR
    return task["prompt"] + _mbpp_signature(task) + MBPP_INSTR


def extract_code(reply: str) -> str:
    """Pull the Python out of a reply: prefer a fenced block, else raw text."""
    if not reply:
        return ""
    blocks = _FENCE.findall(reply)
    if blocks:
        for lang, body in blocks:
            if (lang or "").lower() in ("", "python", "py", "python3"):
                return body.strip("\n")
        return blocks[0][1].strip("\n")
    m = _FENCE_NL.search(reply)
    if m:
        return m.group(1).strip("\n")
    return reply.strip()


def build_program(bench: str, task: dict, code: str) -> str:
    if bench == "humaneval":
        # prompt's stub body is a bare docstring (valid); a full redefinition from
        # the model overrides it, a bare indented body completes it.
        base = task["prompt"]
        if not base.endswith("\n"):
            base += "\n"
        return (base + code + "\n\n" + task["test"] +
                f"\n\ncheck({task['entry_point']})\n")
    imports = "\n".join(task.get("test_imports") or [])
    tests = "\n".join(task["test_list"])
    return f"{imports}\n{code}\n\n{tests}\n"


# --------------------------------------------------------------------------
# sandboxed execution
# --------------------------------------------------------------------------
def _limits() -> None:
    """Child-side rlimits.  Reliability bounds, not a security boundary."""
    resource.setrlimit(resource.RLIMIT_CPU, (CPU_SECONDS, CPU_SECONDS + 2))
    resource.setrlimit(resource.RLIMIT_AS, (MEM_BYTES, MEM_BYTES))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    try:
        resource.setrlimit(resource.RLIMIT_FSIZE, (FSIZE_BYTES, FSIZE_BYTES))
    except (ValueError, OSError):
        pass


def run_program(program: str) -> tuple[bool, float, str]:
    """Execute in a throwaway dir.  Return (passed, exec_seconds, reason)."""
    workdir = tempfile.mkdtemp(prefix="ds4code_")
    path = os.path.join(workdir, "candidate.py")
    with open(path, "w") as f:
        f.write(program)
    env = {"PATH": "/usr/bin:/bin", "HOME": workdir, "PYTHONHASHSEED": "0",
           "PYTHONDONTWRITEBYTECODE": "1", "LC_ALL": "C.UTF-8"}
    t0 = time.time()
    try:
        p = subprocess.run([sys.executable, "-I", "candidate.py"], cwd=workdir,
                           env=env, capture_output=True, timeout=WALL_SECONDS,
                           preexec_fn=_limits)
    except subprocess.TimeoutExpired:
        return False, round(time.time() - t0, 2), f"wall timeout after {WALL_SECONDS}s"
    finally:
        try:
            os.remove(path)
            os.rmdir(workdir)
        except OSError:
            pass
    dt = round(time.time() - t0, 2)
    if p.returncode == 0:
        return True, dt, ""
    err = p.stderr.decode(errors="replace").strip()
    last = err.splitlines()[-1] if err else ""
    return False, dt, last[:300] or f"exit code {p.returncode}"


# --------------------------------------------------------------------------
# item building / run loop
# --------------------------------------------------------------------------
def load_jsonl(path: str) -> list[dict]:
    with open(path) as f:
        return [json.loads(l) for l in f if l.strip()]


def sample(rows: list, limit: int | None, seed: int) -> list[tuple[int, dict]]:
    if limit is None or limit >= len(rows):
        return list(enumerate(rows))
    idx = sorted(random.Random(seed).sample(range(len(rows)), limit))
    return [(i, rows[i]) for i in idx]


def items_for(bench: str, limit: int | None, seed: int) -> list[dict]:
    rows = load_jsonl(os.path.join(DATA, DATASETS[bench][4]))
    out = []
    for i, r in sample(rows, limit, seed):
        if bench == "humaneval":
            tid, ep = r["task_id"], r["entry_point"]
        else:
            tid, ep = f"mbpp/{r['task_id']}", None
        out.append({"id": tid, "bench": bench, "category": bench, "entry_point": ep,
                    "prompt": build_prompt(bench, r), "_task": r})
    return out


def run_bench(a, bench: str, model: str):
    rawdir = os.path.join(a.outdir, "_raw")
    os.makedirs(rawdir, exist_ok=True)
    suffix = f".{a.tag}" if a.tag else ""
    raw = os.path.join(rawdir, f"{model}.{bench}.{a.thinking}{suffix}.jsonl")
    done: dict[str, dict] = {}
    if os.path.exists(raw):
        for line in open(raw):
            try:
                rec = json.loads(line)
                done[rec["id"]] = rec
            except Exception:  # noqa: BLE001
                pass
    items = items_for(bench, a.limit, a.seed)
    if not items:
        return None
    print(f"\n=== {bench} | model={model} | thinking={a.thinking} | "
          f"{len(items)} items ({len(done)} cached) ===", flush=True)
    if done:
        print(f"    resuming, {len(done)} already recorded", flush=True)

    with open(raw, "a") as rawf:
        for item in items:
            if item["id"] in done:
                continue
            err = None
            try:
                reply, meta = chat(a.base_url, model, item["prompt"],
                                   a.max_tokens, a.thinking)
                code = extract_code(reply)
                if code.strip():
                    passed, exec_s, reason = run_program(
                        build_program(bench, item["_task"], code))
                else:
                    passed, exec_s, reason = False, 0.0, "no code extracted"
            except Exception as e:  # noqa: BLE001
                reply = f"<ERROR {type(e).__name__}: {e}>"
                meta, code, passed, exec_s, reason = {}, "", False, 0.0, ""
                err = str(e)
            rec = {"id": item["id"], "bench": bench, "category": item["category"],
                   "entry_point": item["entry_point"],
                   "reply": reply.strip()[:REPLY_CAP], "extracted": code,
                   "passed": passed, "correct": passed,  # correct = merge w/ compare_results.py
                   "tokens": meta.get("tokens"), "elapsed": meta.get("elapsed", 0.0),
                   "exec_s": exec_s, "finish_reason": meta.get("finish_reason"),
                   "reasoning_tokens": meta.get("reasoning_tokens"),
                   "error": err, "reason": reason}
            done[item["id"]] = rec
            rawf.write(json.dumps(rec) + "\n")
            rawf.flush()
            mark = "PASS" if passed else "FAIL"
            detail = "" if passed else f"  <- {reason}"
            print(f"  [{mark}] {item['id']:14s} {item['prompt'].splitlines()[0][:46]!r}"
                  f"{detail}", flush=True)

    recs = [done[i["id"]] for i in items if i["id"] in done]
    n = len(recs)
    correct = sum(1 for r in recs if r["passed"])
    by_cat = {}
    for r in recs:
        by_cat.setdefault(r["category"], []).append(r["passed"])
    out = {"model": model, "bench": bench, "thinking": a.thinking, "n": n,
           "correct": correct, "pct": 100.0 * correct / n if n else 0.0,
           "by_category": {c: {"n": len(v), "correct": sum(v)} for c, v in sorted(by_cat.items())},
           "errors": sum(1 for r in recs if r.get("error")),
           "items": recs}
    tag = f".{a.tag}" if a.tag else ""
    dest = os.path.join(a.outdir, f"{model}.{bench}.{a.thinking}{tag}.json")
    json.dump(out, open(dest, "w"), indent=1)
    print(f"  => {bench}: {correct}/{n} = {out['pct']:.1f}%   wrote {dest}", flush=True)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base-url", help="gateway base, e.g. http://host:4000 (or the full .../v1/chat/completions)")
    ap.add_argument("--model", help="gateway model id, e.g. deepseek or deepseek-turbo")
    ap.add_argument("--bench", default="both", choices=["humaneval", "mbpp", "both"])
    ap.add_argument("--thinking", default="off", choices=["off", "on"])
    ap.add_argument("--limit", type=int, default=None, help="items per bench (default: all)")
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--tag", default="", help="extra suffix for output files, e.g. smoke")
    ap.add_argument("--max-tokens", type=int, default=2048)
    ap.add_argument("--outdir", default=os.path.join(HERE, "results"))
    ap.add_argument("--stage", action="store_true", help="re-fetch the datasets, then exit unless --base-url/--model given")
    a = ap.parse_args()

    ensure_data(force=a.stage)
    if not (a.base_url and a.model):
        if a.stage:
            return 0
        ap.error("--base-url and --model are required")
    benches = ["humaneval", "mbpp"] if a.bench == "both" else [a.bench]
    for b in benches:
        run_bench(a, b, a.model)
    return 0


if __name__ == "__main__":
    sys.exit(main())