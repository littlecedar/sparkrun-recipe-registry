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

Outputs land in `<outdir>/client/`, never at the arm root: run-arm's standard
branch already writes `house.json`/`ladder.json` there (sparkrun's YAML sidecars)
and this client must not overwrite the campaign's own artefacts.  Exit status:
0 when every step measured, else the first failing step's rc; per-step rc and the
exact argv are in `client/client.json`.

Usage
-----
    python3 -B tools/h2h-client.py --cell house4096 \
        --base-url http://RANK0:PORT --outdir <receipts-dir>
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import subprocess
import sys
import tempfile
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CELLS = ("house4096", "house-bfcl", "lc-1m", "lc-128k-c5c10")


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
         image_id: str = "") -> list[tuple[str, list[str]]]:
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
    for cell, want in (("house4096", 1), ("house-bfcl", 2), ("lc-1m", 1), ("lc-128k-c5c10", 1)):
        steps = plan(cell, base, "m", "/r", "py", house_max_tokens=4096,
                     bfcl_data_dir="/d", bfcl_max_tokens=4096)
        assert len(steps) == want, (cell, steps)
        for _name, argv in steps:
            assert base in argv and not any(a.startswith("10.") for a in argv), argv
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
    ap.add_argument("--timeout", type=float, default=600.0, help="/v1/models resolve seconds")
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
    results: list[dict[str, object]] = []
    first_failure = 0
    for name, cmd in plan(args.cell, base, model, outdir, py,
                          house_max_tokens=args.house_max_tokens,
                          bfcl_data_dir=args.bfcl_data_dir,
                          bfcl_max_tokens=args.bfcl_max_tokens):
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
