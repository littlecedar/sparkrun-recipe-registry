#!/usr/bin/env python3
"""stage-audit.py — prove a manifest arm can actually launch, before it costs a window.

Four partial-snapshot failures on 2026-10-29 each burned a boot: the repo directory
existed, the pinned revision held `config.json` alone, and the engine died with an
opaque tokenizer/processor error an hour later. Repo presence is not readiness.

Checks per manifest arm, and what each one means:

  image   `docker image inspect <ref>@sha256:<digest>` on the target node. The
          authoritative test: a locally retagged build has an empty `Digest` column in
          `docker images`, so matching that column reports resident images as missing.
  snapshot  the pinned revision's entry COUNT, compared with the number of files
          upstream reports for that revision. A one-file stub reads as "staged" to any
          check that only asks whether the repo is present.
  weights  at least one `*.safetensors` whose TARGET size (`stat -L`, following the HF
          cache's symlinks) is above STUB_BYTES. `du`/`ls -la` on an HF cache measure
          link paths, not bytes, and a complete 39 GB snapshot reads as 6.7 MB.

Exit codes: 0 every arm launchable on at least one free node; 1 at least one arm needs
staging; 2 the audit itself could not run.

Stdlib only; runs on the head, reads the manifest, ssh's to the free nodes.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

MANIFEST = ".scratch/tp12-campaign/manifest.json"
# Nodes come from --nodes/$STAGE_NODES: this file is tracked and the registry
# forbids cluster addresses in tracked text (tests/test_tracked_address_hygiene.py).
DEFAULT_NODES = ""
POOL = "/mnt/beegfs/huggingface/hub"
STUB_BYTES = 1 << 20  # a weight file smaller than this is a pointer, not weights


def sh(args: list[str], timeout: int = 60) -> tuple[int, str]:
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except (subprocess.SubprocessError, OSError) as exc:
        return 2, f"{type(exc).__name__}: {exc}"
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def node_sh(node: str, script: str, timeout: int = 90) -> tuple[int, str]:
    return sh(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=6", f"red@{node}", script], timeout)


def upstream_file_count(model: str, revision: str) -> int | None:
    """Files the Hub reports for this revision, or None when the call fails."""
    url = f"https://huggingface.co/api/models/{model}/revision/{revision}"
    rc, out = sh(["curl", "-sS", "-m", "20", url])
    if rc != 0 or not out.strip():
        return None
    try:
        return len(json.loads(out).get("siblings", []))
    except (ValueError, AttributeError):
        return None


def snapshot_state(model: str, revision: str, pool_node: str) -> str:
    """`entries=<n>/<upstream> weights=<ok|SHORT>` for the pinned revision on the pool."""
    repo = "models--" + model.replace("/", "--")
    path = f"{POOL}/{repo}/snapshots/{revision}"
    rc, out = node_sh(
        pool_node,
        # Recursive: the Hub's `siblings` list is recursive, so a top-level `ls`
        # under-counts any repo with a subdirectory and cries INCOMPLETE on a
        # complete snapshot (measured: spark-x2.6-4b read 19/24 for an intact tree).
        f"d={path}; n=$(find $d \\( -type f -o -type l \\) 2>/dev/null | wc -l); "
        f"w=$(for f in $d/*.safetensors; do [ -e \"$f\" ] && stat -L -c %s \"$f\"; done 2>/dev/null | sort -rn | head -1); "
        "echo \"$n ${w:-0}\"",
    )
    if rc != 0:
        return f"probe-failed({out.strip()[:40]})"
    try:
        entries, biggest = (int(x) for x in out.split()[:2])
    except ValueError:
        return f"unparsable({out.strip()[:30]})"
    weights = "ok" if biggest >= STUB_BYTES else "SHORT"
    return f"entries={entries} weights={weights}"


def image_state(container: str, nodes: tuple[str, ...]) -> str:
    """Where the pinned image resolves, by digest, on the free nodes."""
    if "@sha256:" not in container:
        return "tag-only(no digest pin)"
    have = []
    for node in nodes:
        rc, _ = node_sh(node, f"docker image inspect {container} >/dev/null 2>&1")
        if rc == 0:
            have.append(node.rsplit(".", 1)[-1])
    return "on ." + ",.".join(have) if have else "MISSING on both free nodes"


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Prove manifest arms can launch before a window is spent.")
    ap.add_argument(
        "--nodes",
        default=os.environ.get("STAGE_NODES", DEFAULT_NODES),
        help="comma-separated free nodes to probe (or $STAGE_NODES)",
    )
    args = ap.parse_args(argv)
    nodes = tuple(n.strip() for n in args.nodes.split(",") if n.strip())
    if not nodes:
        print("no nodes: pass --nodes a,b or set $STAGE_NODES", file=sys.stderr)
        return 2
    try:
        arms = json.load(open(MANIFEST))
    except (OSError, ValueError) as exc:
        print(f"cannot read {MANIFEST}: {exc}", file=sys.stderr)
        return 2
    if not isinstance(arms, list) or not arms:
        print("manifest is not a non-empty list", file=sys.stderr)
        return 2

    need = 0
    for entry in arms:
        arm = entry.get("arm") or entry.get("path", "?").split("/")[-1]
        model = entry.get("model") or ""
        container = entry.get("container") or ""
        # The recipe is the truth: the manifest lags, and `model_revision:` lives
        # in the YAML the launch actually reads.
        try:
            text = open(entry.get("path") or "", encoding="utf-8").read()
        except OSError:
            text = ""
        revision = ""
        for line in text.splitlines():
            key = line.split(":", 1)[0].strip()
            if key == "model_revision" and not revision:
                revision = line.split(":", 1)[1].strip().strip("'\"")
            elif key == "container" and not container:
                container = line.split(":", 1)[1].strip().strip("'\"")
        model = model or ""
        if not model and text:
            for line in text.splitlines():
                if line.split(":", 1)[0].strip() == "model":
                    model = line.split(":", 1)[1].strip().strip("'\"")
                    break
        if not model or not revision:
            print(f"{arm:56s} no model/revision in the manifest")
            need += 1
            continue
        upstream = upstream_file_count(model, revision)
        snap = snapshot_state(model, revision, nodes[0])
        img = image_state(container, nodes) if container else "no container in the manifest"
        bad = ("weights=SHORT" in snap) or ("MISSING" in img) or snap.startswith("probe-failed")
        if upstream is not None and "entries=" in snap:
            try:
                have = int(snap.split("entries=")[1].split()[0])
                if have < upstream:
                    snap += f"/{upstream} INCOMPLETE"
                    bad = True
            except (IndexError, ValueError):
                pass
        need += bad
        print(f"{arm:56s} {img:28s} {snap}{'' if not bad else '   <-- STAGE'}")
    print(f"\n{len(arms)} arms, {need} needing staging")
    # Named because a green line here was read as readiness on 2026-10-30 and the next boot died on
    # `ImportError: Other method (CompressedTensorsW4A16Sparse24) is not supported now`. It cannot be
    # predicted from the checkpoint: the pinned config for that arm declares 8-bit/channel and
    # 4-bit/tensor_group groups and no sparsity marker at all, while the engine demanded a Sparse24
    # class -- the scheme name is the engine's own construction, not a field. So this tool must state
    # the dimension it does not cover instead of growing a predictor that would guess.
    print("NOTE: this audits bytes -- image digest present, snapshot entry count, weight size. It does")
    print("      NOT test that the engine can execute the checkpoint's quantisation scheme.")
    return 1 if need else 0


if __name__ == "__main__":
    sys.exit(main())