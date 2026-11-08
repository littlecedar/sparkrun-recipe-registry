#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Travis Wichert
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""h2h-client.py -- the campaign's quality cells, one command against a live serve.

Why this file exists
--------------------
`tools/run-arm.sh` measures the ladder and the standard suite and then tears the
serve down; four head-to-head/survey cells are in neither instrument.  Each was
a long shell string in a queue row's `env`, which is unreadable there and must
not carry a node address (`tests/test_tracked_address_hygiene.py` rejects
RFC1918 literals in tracked files, and placement is 4-of-6 so a fixed endpoint
would pick the wrong API rank).  The row now carries this script plus a cell
name; the hook supplies the endpoint as `--base-url http://$NODE:$PORT` (rank 0
of run-arm's host list) and the arm directory as `--outdir $L`.  The served id
is resolved from `/v1/models`, so no model id rides in the row either.

Cells (all against `--base-url`)
--------------------------------
`house4096`      quality-battery.py --tier both --max-tokens 4096 (37 exact-match
                 tasks; the serve's own thinking mode, no chat_template_kwargs).
`house-bfcl`     house4096, then bfcl-eval.py --json: its `summary` field and
                 printed table carry the per-category correct/total.  Direct
                 bfcl, never the eval-suite wrapper (it stalled 52 min).
`lc-1m`          longctx-cell.py at 1,039,999 prompt tokens, c1, 128 output
                 tokens: ms/step + needle witness (survey arm 3).
`lc-128k-c5c10`  longctx-cell.py at 131,072 prompt tokens, c5 and c10 (survey
                 arm 5).  A needle miss at 8 output tokens makes that tool exit
                 3 while the ms/step and aggregate cells stay valid.
`completions`    the only cell that speaks `/v1/completions`: for a serve whose
                 model has no chat template (a base or a researched checkpoint),
                 where every chat-completing instrument here returns nothing.
                 Fixed prompts from `--prompts` (or a built-in set carrying a
                 deterministic one), each sent non-streaming and streaming, so
                 the receipt holds text, `usage` token counts, wall time, TTFT
                 and tok/s per prompt.  `--max-tokens` caps the answer.

Outputs land in `<outdir>/client/`, never at the arm root: run-arm's standard
branch already writes `house.json`/`ladder.json` there (sparkrun's YAML sidecars)
and this client must not overwrite the campaign's own artefacts.  Exit status:
0 when every step measured, else the first failing step's rc; per-step rc and the
exact argv are in `client/client.json`.  The `completions` cell reports why it
failed: 1 endpoint unreachable, 2 bad flags or an unusable prompt file, 3 an
answer that missed its `expect`, 4 a non-200 (status and body printed), 5 an
empty `choices[0].text` — returned nothing is a failure, never a zero-token
success.  Detail, including which prompt and which mode, is in
`client/completions.json`.

Usage
-----
    python3 -B tools/h2h-client.py --cell house4096 \
        --base-url http://RANK0:PORT --outdir <receipts-dir>
    python3 -B tools/h2h-client.py --cell completions \
        --base-url http://RANK0:PORT --outdir <receipts-dir> --prompts prompts.json

`H2H_API_KEY` is the only bearer source, read from the environment rather than a
flag so neither the artifact nor the recorded argv can carry it.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CELLS = ("house4096", "house-bfcl", "lc-1m", "lc-128k-c5c10", "completions")
# A base model has no chat template, so the signal has to be completion-shaped: one
# deterministic continuation plus two facts a pretrained checkpoint is likely to hold.
DEFAULT_PROMPTS = (
    {"id": "count", "prompt": "Complete the sequence: 1 2 3 4",
     "expect": "5", "max_tokens": 8},
    {"id": "capital", "prompt": "The capital of France is",
     "expect": "Paris", "max_tokens": 8},
    {"id": "echo", "prompt": "The word is sparkrun. The word is",
     "expect": "sparkrun", "max_tokens": 8},
)
HTTP_ERROR, EMPTY, MISS = 4, 5, 3


def api_root(url: str) -> str:
    """`http://host:port/` and a trailing `/v1` both mean the endpoint root."""
    return url.rstrip("/").removesuffix("/v1")


def served_model(base: str, timeout: float) -> str:
    with urllib.request.urlopen(base + "/v1/models", timeout=timeout) as resp:
        data = json.load(resp)["data"]
    if not data:
        raise SystemExit("h2h-client: /v1/models lists no model")
    return str(data[0]["id"])


def plan(cell: str, base: str, model: str, outdir: str, py: str, *,
         house_max_tokens: int, bfcl_data_dir: str, bfcl_max_tokens: int,
         image_id: str = "", prompts: str = "", max_tokens: int = 32,
         mode: str = "both") -> list[tuple[str, list[str]]]:
    """(step, argv) for one cell -- pure, so the self-test needs no serve."""
    # A cell without the image it ran on is not a result: longctx-cell echoes it into its JSON.
    image = ["--image-id", image_id] if image_id else []
    house = [py, os.path.join(HERE, "quality-battery.py"), base, "--model", model,
             "--tier", "both", "--max-tokens", str(house_max_tokens),
             "--json", os.path.join(outdir, "house.json")]
    bfcl = [py, os.path.join(HERE, "bfcl-eval.py"), "--base-url", base, "--model", model,
            "--data-dir", bfcl_data_dir, "--max-tokens", str(bfcl_max_tokens),
            "--json", os.path.join(outdir, "bfcl.json")]
    longctx = os.path.join(HERE, "longctx-cell.py")
    cells: dict[str, list[tuple[str, list[str]]]] = {
        "house4096": [("house", house)],
        "house-bfcl": [("house", house), ("bfcl", bfcl)],
        "lc-1m": [("longctx", [py, "-B", longctx, "--base-url", base, "--model", model,
                               "--context-length", "1039999", "--concurrency", "1",
                               "--max-tokens", "128",
                               "--json", os.path.join(outdir, "longctx-1m.json")] + image)],
        "lc-128k-c5c10": [("longctx", [py, "-B", longctx, "--base-url", base, "--model", model,
                                       "--context-length", "131072", "--concurrency", "5,10",
                                       "--max-tokens", "8",
                                       "--json", os.path.join(outdir, "longctx-128k-c5c10.json")]
                          + image)],
        # No shipped instrument speaks /v1/completions, so this cell is the tool itself:
        # the argv is the replay command, and main() runs the cell in-process.
        "completions": [("completions", [py, "-B", os.path.join(HERE, "h2h-client.py"),
                                         "--cell", "completions", "--base-url", base,
                                         "--model", model, "--outdir", outdir,
                                         "--max-tokens", str(max_tokens), "--mode", mode]
                         + (["--prompts", prompts] if prompts else []))],
    }
    return cells[cell]


def step(name: str, cmd: list[str], log_path: str) -> int:
    """Run one instrument, tee its tail to the hook log (the full output is in log_path)."""
    env = dict(os.environ, PYTHONUNBUFFERED="1")
    print("h2h-client: %s: %s" % (name, " ".join(cmd)), flush=True)
    with open(log_path, "w", encoding="utf-8") as log:
        proc = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, env=env,
                              cwd=HERE, check=False)
    with open(log_path, encoding="utf-8", errors="replace") as log:
        for line in log.readlines()[-12:]:
            print("  " + line.rstrip(), flush=True)
    return proc.returncode


def _give_up(message: str) -> None:
    """An unusable prompt file is a bad invocation, not a measurement: exit 2, loudly."""
    print("h2h-client: " + message, file=sys.stderr)
    raise SystemExit(2)


def load_prompts(path: str) -> list[dict[str, object]]:
    """Prompts from a JSON list (strings or {id,prompt,expect,max_tokens}) or one per line."""
    if path.rsplit(".", 1)[-1].lower() in ("yaml", "yml"):
        _give_up("prompt files are JSON or newline-delimited, not YAML")
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        _give_up("cannot read prompts: %s" % exc)
    try:
        data = json.loads(text)
    except ValueError:
        data = [line.strip() for line in text.splitlines()
                if line.strip() and not line.strip().startswith("#")]
    if not isinstance(data, list):
        _give_up("prompt file must hold a JSON list or one prompt per line")
    prompts: list[dict[str, object]] = []
    for item in data:
        if isinstance(item, str):
            if not item.strip():
                continue
            prompts.append({"id": "p%d" % (len(prompts) + 1), "prompt": item})
        elif isinstance(item, dict) and str(item.get("prompt") or "").strip():
            rec = {"id": str(item.get("id") or "p%d" % (len(prompts) + 1)),
                   "prompt": str(item["prompt"])}
            for key in ("expect", "max_tokens"):
                if item.get(key) is not None:
                    rec[key] = item[key]
            prompts.append(rec)
        else:
            _give_up("prompt entry needs a non-empty 'prompt': %r" % (item,))
    if not prompts:
        _give_up("%s holds no prompts" % path)
    return prompts


def completion_rate(tokens: object, window_s: float) -> float | None:
    """tok/s over an arithmetic window. None means no tokens were counted.

    Two decimals round a real rate to 0.0 on a slow runner's wall, which reads as "no
    throughput" when tokens were produced, so the digits below 0.01 are kept. A window of
    zero cannot come out of `perf_counter` (nanosecond resolution); it is reported as None
    rather than as a fabricated number.
    """
    if not isinstance(tokens, int) or tokens <= 0 or window_s <= 0:
        return None
    rate = tokens / window_s
    return round(rate, 2) if rate >= 0.01 else round(rate, 6)


def _completions_request(base: str, model: str, prompt: str, max_tokens: int,
                         stream: bool, timeout: float, api_key: str) -> dict[str, object]:
    """One /v1/completions call: text, usage counts, wall, and TTFT when streaming."""
    body: dict[str, object] = {"model": model, "prompt": prompt,
                               "max_tokens": max_tokens, "temperature": 0}
    if stream:
        body["stream"] = True
        body["stream_options"] = {"include_usage": True}
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = "Bearer " + api_key
    req = urllib.request.Request(base + "/v1/completions",
                                 data=json.dumps(body).encode(), headers=headers)
    rec: dict[str, object] = {"text": "", "prompt_tokens": None, "completion_tokens": None,
                              "wall_s": None, "ttft_s": None, "tok_per_s": None,
                              "error": None, "http_status": None}
    started = time.perf_counter()
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as exc:
        detail = exc.read()[:400].decode("utf-8", "replace")
        rec["error"] = "HTTP %s: %s" % (exc.code, detail)
        rec["http_status"] = exc.code
        print("h2h-client: completions: HTTP %s: %s" % (exc.code, detail), file=sys.stderr)
        rec["wall_s"] = round(time.perf_counter() - started, 3)
        return rec
    except Exception as exc:  # unreachable host, timeout, TLS, a stalled stream
        rec["error"] = "%s: %s" % (type(exc).__name__, exc)
        rec["wall_s"] = round(time.perf_counter() - started, 3)
        return rec
    first_token = None
    try:
        with resp:
            if stream:
                for raw in resp:
                    line = raw.decode("utf-8", "replace").strip()
                    if line.startswith("data:"):
                        line = line[5:].strip()
                    if not line or line[0] not in "{[" or line.startswith("[DONE"):
                        continue
                    try:
                        chunk = json.loads(line)
                    except ValueError:
                        continue
                    usage = chunk.get("usage") or {}
                    for key in ("prompt_tokens", "completion_tokens"):
                        if usage.get(key):
                            rec[key] = usage[key]
                    for choice in chunk.get("choices") or []:
                        piece = choice.get("text") or ""
                        if piece:
                            rec["text"] += piece
                            if first_token is None:
                                first_token = time.perf_counter()
            else:
                payload = json.loads(resp.read() or b"{}")
                usage = payload.get("usage") or {}
                rec["prompt_tokens"] = usage.get("prompt_tokens")
                rec["completion_tokens"] = usage.get("completion_tokens")
                choices = payload.get("choices") or []
                rec["text"] = (choices[0].get("text") or "") if choices else ""
    except Exception as exc:  # a stream that dies mid-flight is a failed request, not a cell
        rec["error"] = "%s: %s" % (type(exc).__name__, exc)
    elapsed = time.perf_counter() - started
    rec["wall_s"] = round(elapsed, 3)
    # Arithmetic runs on the raw delta: rounding the window first turns a sub-millisecond
    # stub answer into 0.0 and drops the rate even though tokens were counted.
    decode_s = elapsed
    if first_token is not None:
        ttft = first_token - started
        rec["ttft_s"] = round(ttft, 3)
        decode_s = elapsed - ttft
    rec["tok_per_s"] = completion_rate(rec["completion_tokens"], decode_s)
    rec["text"] = rec["text"].strip()
    return rec


def run_completions(base: str, model: str, outdir: str, prompts: list[dict[str, object]],
                    prompt_source: str, *, max_tokens: int, mode: str, timeout: float,
                    api_key: str) -> tuple[int, dict[str, object]]:
    """Every prompt both ways; the artifact keeps the text even when the cell fails."""
    modes = ("plain", "stream") if mode == "both" else (mode,)
    records: list[dict[str, object]] = []
    problems: list[str] = []
    counts = {"answered": 0, "empty": 0, "http_errors": 0, "matched": 0, "expectations": 0}
    for prompt in prompts:
        rec: dict[str, object] = {"id": prompt["id"], "prompt": prompt["prompt"]}
        if prompt.get("expect"):
            rec["expect"] = prompt["expect"]
        for kind in modes:
            out = _completions_request(base, model, str(prompt["prompt"]),
                                       int(prompt.get("max_tokens") or max_tokens),
                                       kind == "stream", timeout, api_key)
            rec[kind] = out
            where = "%s/%s" % (prompt["id"], kind)
            if out["http_status"]:
                counts["http_errors"] += 1
                problems.append("%s: %s" % (where, out["error"]))
            elif out["error"]:
                problems.append("%s: %s" % (where, out["error"]))
            elif not out["text"]:
                # An empty answer is the failure mode a base serve produces by accident:
                # usage may still count tokens, so tokens alone must never mean success.
                counts["empty"] += 1
                problems.append("%s: empty completion (choices[0].text had nothing)" % where)
            else:
                counts["answered"] += 1
                if out["completion_tokens"] is None:
                    problems.append("%s: answered but usage carried no completion_tokens" % where)
                expect = str(prompt.get("expect") or "")
                if expect:
                    counts["expectations"] += 1
                    hit = expect in str(out["text"])
                    rec["%s_matched" % kind] = hit
                    if hit:
                        counts["matched"] += 1
                    else:
                        problems.append("%s: expected %r in the completion" % (where, expect))
            line = "%s/%s wall=%ss tokens=%s ttft=%s tok/s=%s%s" % (
                prompt["id"], kind, out["wall_s"], out["completion_tokens"], out["ttft_s"],
                out["tok_per_s"], "" if out["text"] else " EMPTY")
            print("completions: " + line, flush=True)
        records.append(rec)
    rates = [c[kind]["tok_per_s"] for c in records for kind in modes
             if c.get(kind) and c[kind]["tok_per_s"] is not None]
    ttfts = [c[kind]["ttft_s"] for c in records for kind in modes
             if c.get(kind) and c[kind]["ttft_s"] is not None]
    report: dict[str, object] = {
        "tool": "h2h-client", "cell": "completions", "base_url": base, "model": model,
        "prompts_source": prompt_source, "max_tokens": max_tokens, "modes": list(modes),
        "requests": len(records) * len(modes), "summary": dict(
            counts, tok_per_s_median=round(statistics.median(rates), 2) if rates else None,
            ttft_s_median=round(statistics.median(ttfts), 3) if ttfts else None),
        "prompts": records, "problems": problems,
        "verdict": "PASS" if not problems else "FAIL",
    }
    if counts["http_errors"]:
        rc = HTTP_ERROR
    elif counts["empty"]:
        rc = EMPTY
    elif counts["matched"] != counts["expectations"]:
        rc = MISS
    else:
        rc = 0
    report["rc"] = rc
    with open(os.path.join(outdir, "completions.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1)
    for problem in problems:
        print("completions: PROBLEM: " + problem, file=sys.stderr, flush=True)
    print("completions: verdict=%s rc=%d -> %s"
          % (report["verdict"], rc, os.path.join(outdir, "completions.json")), flush=True)
    return rc, report


def house_errors(path: str) -> tuple[int, int]:
    """(tasks, replies that are transport errors) from quality-battery's --json artifact.

    quality-battery exits 0 by design (the score is the artifact), so a serve that
    rejects every request would otherwise read as a finished, zero-score cell.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return 0, 0
    tasks = errors = 0
    for tier in (data.get("tiers") or {}).values():
        for replies in (tier.get("replies") or {}).values():
            tasks += len(replies)
            errors += sum(1 for reply in replies if str(reply).startswith("<ERROR"))
    return tasks, errors


def self_test() -> int:
    assert api_root("http://h:8000/") == "http://h:8000"
    assert api_root("http://h:8000/v1") == "http://h:8000"
    base = "http://h:8000"
    for cell, want in (("house4096", 1), ("house-bfcl", 2), ("lc-1m", 1),
                       ("lc-128k-c5c10", 1), ("completions", 1)):
        steps = plan(cell, base, "m", "/r", "py", house_max_tokens=4096,
                     bfcl_data_dir="/d", bfcl_max_tokens=4096)
        assert len(steps) == want, (cell, steps)
        for _name, argv in steps:
            assert base in argv and not any(a.startswith("10.") for a in argv), argv
    comp = plan("completions", base, "m", "/r", "py", house_max_tokens=4096,
                bfcl_data_dir="/d", bfcl_max_tokens=4096, prompts="/r/p.json",
                max_tokens=16, mode="stream")[0][1]
    assert comp[2].endswith("h2h-client.py") and comp[comp.index("--mode") + 1] == "stream", comp
    assert "/r/p.json" in comp and "16" in comp, comp
    assert any("Complete the sequence" in str(p["prompt"]) for p in DEFAULT_PROMPTS), DEFAULT_PROMPTS
    lc = plan("lc-1m", base, "m", "/r", "py", house_max_tokens=4096,
              bfcl_data_dir="/d", bfcl_max_tokens=4096)[0][1]
    assert "1039999" in lc and "/r/longctx-1m.json" in lc, lc
    bf = plan("house-bfcl", base, "m", "/r", "py", house_max_tokens=4096,
              bfcl_data_dir="/d", bfcl_max_tokens=4096)
    assert bf[1][1][1].endswith("bfcl-eval.py") and "/r/bfcl.json" in bf[1][1], bf
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "house.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"tiers": {"easy": {"replies": {"a": ["<ERROR x"], "b": ["ok"]}}}}, fh)
        assert house_errors(path) == (2, 1), house_errors(path)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"tiers": {"easy": {"replies": {"a": ["<ERROR x"]}}}}, fh)
        assert house_errors(path) == (1, 1), house_errors(path)
        js = os.path.join(tmp, "p.json")
        with open(js, "w", encoding="utf-8") as fh:
            json.dump([{"id": "c", "prompt": "1 2 3", "expect": "4"}], fh)
        assert load_prompts(js) == [{"id": "c", "prompt": "1 2 3", "expect": "4"}], load_prompts(js)
        plain = os.path.join(tmp, "p.txt")
        with open(plain, "w", encoding="utf-8") as fh:
            fh.write("# comment\n\nfirst prompt\nsecond\n")
        assert [p["prompt"] for p in load_prompts(plain)] == ["first prompt", "second"]
        yml = os.path.join(tmp, "p.yaml")
        with open(yml, "w", encoding="utf-8") as fh:
            fh.write("prompt: not-in-this-repo\n")
        try:
            load_prompts(yml)
        except SystemExit as exc:
            assert exc.code == 2, exc.code
        else:
            raise AssertionError("a YAML prompt file must be refused, not line-split")
    print("selftest: OK")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--cell", choices=CELLS)
    ap.add_argument("--base-url", help="the serve root, http://rank0:port")
    ap.add_argument("--outdir", help="the arm's receipt directory")
    ap.add_argument("--model", default="auto", help="served id; 'auto' reads /v1/models")
    ap.add_argument("--house-max-tokens", type=int, default=4096)
    ap.add_argument("--bfcl-data-dir", default=os.path.expanduser("~/bfcl"))
    ap.add_argument("--bfcl-max-tokens", type=int, default=4096)
    ap.add_argument("--prompts", default="",
                    help="completions cell: JSON list or newline-delimited prompts; "
                         "default is a small set carrying a deterministic continuation")
    ap.add_argument("--max-tokens", type=int, default=32,
                    help="completions cell: output cap per prompt (an entry may set its own)")
    ap.add_argument("--mode", choices=("both", "plain", "stream"), default="both",
                    help="completions cell: non-streaming, streaming (TTFT), or both")
    ap.add_argument("--timeout", type=float, default=600.0, help="/v1/models resolve seconds")
    ap.add_argument("--request-timeout", type=float, default=600.0,
                    help="completions cell: per-request seconds")
    ap.add_argument("--selftest", action="store_true", help="offline; no serve needed")
    args = ap.parse_args(argv)
    if args.selftest:
        return self_test()
    missing = [name for name in ("cell", "base_url", "outdir") if not getattr(args, name)]
    if missing:
        ap.error("required: " + ", ".join("--" + name.replace("_", "-") for name in missing))

    base = api_root(args.base_url)
    arm_dir = os.path.abspath(os.path.expanduser(args.outdir))
    # The client proves a cell, not the image: run-arm exports the rank-0 image id and writes
    # <arm>/image.txt, so name it in the receipt (env first, file as the fallback).
    image_id = os.environ.get("ARM_IMAGE_ID", "").strip()
    if not image_id:
        try:
            with open(os.path.join(arm_dir, "image.txt"), encoding="utf-8") as fh:
                image_id = fh.read().strip()
        except OSError:
            image_id = ""
    try:
        model = args.model if args.model != "auto" else served_model(base, args.timeout)
    except (OSError, ValueError, KeyError) as exc:
        print("h2h-client: endpoint unreachable: %s: %s" % (type(exc).__name__, exc),
              file=sys.stderr)
        return 1
    outdir = os.path.join(arm_dir, "client")
    os.makedirs(outdir, exist_ok=True)
    print("h2h-client: cell=%s base=%s model=%s image=%s out=%s"
          % (args.cell, base, model, image_id or "unrecorded", outdir), flush=True)

    py = sys.executable or "python3"
    prompts: list[dict[str, object]] = [dict(p) for p in DEFAULT_PROMPTS]
    prompt_source = "default"
    if args.cell == "completions" and args.prompts:
        prompts, prompt_source = load_prompts(args.prompts), args.prompts
    results: list[dict[str, object]] = []
    first_failure = 0
    for name, cmd in plan(args.cell, base, model, outdir, py,
                          house_max_tokens=args.house_max_tokens,
                          bfcl_data_dir=args.bfcl_data_dir,
                          bfcl_max_tokens=args.bfcl_max_tokens,
                          prompts=args.prompts, max_tokens=args.max_tokens,
                          mode=args.mode):
        if name == "completions":
            # The cell is this tool: no instrument needs a subprocess, and the argv above
            # is the replay command the receipt records.
            rc, _report = run_completions(
                base, model, outdir, prompts, prompt_source, max_tokens=args.max_tokens,
                mode=args.mode, timeout=args.request_timeout,
                api_key=os.environ.get("H2H_API_KEY", ""))
        else:
            rc = step(name, cmd, os.path.join(outdir, name + ".log"))
        if name == "house":
            tasks, errors = house_errors(os.path.join(outdir, "house.json"))
            if tasks and errors == tasks:
                print("h2h-client: house answered 0/%d tasks (transport errors)" % tasks, flush=True)
                rc = rc or 2
        results.append({"step": name, "rc": rc, "argv": cmd})
        if rc != 0 and first_failure == 0:
            first_failure = rc
            if args.cell == "house-bfcl" and name == "house":
                # BFCL is the cell's longer, independent leg; a house failure must not skip it.
                print("h2h-client: house rc=%d, continuing to bfcl" % rc, flush=True)

    manifest = {
        "tool": "h2h-client", "cell": args.cell, "base_url": base, "model": model,
        "image_id": image_id,
        "receipts_dir": os.path.dirname(outdir),
        "started_utc": datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "steps": results, "rc": first_failure,
    }
    with open(os.path.join(outdir, "client.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=1)
    print("h2h-client: rc=%d -> %s" % (first_failure, os.path.join(outdir, "client.json")),
          flush=True)
    return first_failure


if __name__ == "__main__":
    sys.exit(main())
