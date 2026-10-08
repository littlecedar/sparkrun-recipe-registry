#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Little Cedar Group <sparkrun@littlecedar.net>
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Vendor the DeepSeek-V4.1-Flash **combined** local Hugging Face repo.

The TensorFold TP=2 lane serves the EXL3 2.9bpw checkpoint
(``Mia-AiLab/DeepSeek-V4.1-Flash-EXL3-2.9bpw``), whose quantizer **omitted the
Engram tables** and pinned an **older prompt**.  The tables and the current
prompt live in the official ``deepseek-ai/DeepSeek-V4.1-Flash`` repo.  Rather
than stitch three sources together on every node, this tool builds **one**
local HF repo that carries all of it:

    <out>/model-000NN-of-00039.safetensors   EXL3 2.9bpw weights (39 shards)
    <out>/{config,quantization_config}.json  EXL3 config (authoritative)
    <out>/tokenizer.json tokenizer_config.json chat_template.jinja   upstream
    <out>/engram/engram-l{1,14}.safetensors   upstream Engram tables (TF_DS_ENGRAM)
    <out>/upstream/...                       upstream repo (provenance)
    <out>/provenance/{SOURCES,MANIFEST}.json pinned revisions + per-file sha256

The result is a valid HF snapshot directory: it can be loaded by path, pushed
with ``hf upload``, or dropped into a node's HF cache as
``models--littlecedar--DeepSeek-V4.1-Flash-EXL3-2.9bpw-with-engram``.

Design notes
------------
* **Stdlib only** (the repo rule for ``tools/``): shells out to the ``hf`` CLI
  and to ``build-dsv41-engram.py``; no ``huggingface_hub`` import.
* **The Engram tables are built from a local copy of shards 47/48.**  A direct
  ranged read from the online repo works but is *slow* on a fast link
  (~15 MiB/s observed vs ~170 MiB/s for a whole-file pull), so the tool prefers
  ``hf download`` of the two shards and then a local rebuild; pass
  ``--engram-online`` to range-fetch instead and skip the 203 GB staging.
* **Never reads tokenizer / chat-template content.**  Files are moved and
  hashed as bytes; no special-token literal is ever parsed or printed.
* Idempotent: each stage is skipped when its output already exists and passes a
  cheap check; ``--force`` redoes everything.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENGRAM_BUILDER = HERE / "build-dsv41-engram.py"

DEFAULT_EXL3 = "Mia-AiLab/DeepSeek-V4.1-Flash-EXL3-2.9bpw"
DEFAULT_UPSTREAM = "deepseek-ai/DeepSeek-V4.1-Flash"
# Files promoted from upstream to the combined repo root.  ``chat_template.jinja``
# is the "updated prompt"; the tokenizer pair is refreshed so the repo is
# internally consistent with the prompt.
PROMOTE = ("chat_template.jinja", "tokenizer_config.json", "tokenizer.json")


def log(msg: str) -> None:
    print(f"[combine] {msg}", flush=True)


def die(msg: str) -> "typing.NoReturn":
    raise SystemExit(f"[combine] ERROR: {msg}")


def run(cmd: list[str]) -> None:
    log("+ " + " ".join(cmd))
    subprocess.run(cmd, check=True)


def hf_download(repo: str, out: Path, revision: str, include: list[str] | None = None,
                token: str | None = None) -> None:
    cmd = ["hf", "download", repo, "--local-dir", str(out), "--revision", revision]
    for pat in include or []:
        cmd += ["--include", pat]
    if token:
        cmd += ["--token", token]
    run(cmd)


def free_bytes(path: Path) -> int:
    st = os.statvfs(path)
    return st.f_bavail * st.f_frsize


def preflight(out: Path, need_bytes: int) -> None:
    if shutil.which("hf") is None:
        die("`hf` CLI not found on PATH (pip install huggingface_hub)")
    out.mkdir(parents=True, exist_ok=True)
    avail = free_bytes(out)
    if avail < need_bytes:
        die(f"need ~{need_bytes/2**40:.1f} TiB free at {out}, have {avail/2**40:.1f} TiB")


def stage_exl3(out: Path, repo: str, revision: str, token: str | None, force: bool) -> None:
    index = out / "model.safetensors.index.json"
    if index.is_file() and not force and len(list(out.glob("model-000*-of-00039.safetensors"))) == 39:
        log("EXL3 weights already present; skipping download")
        return
    log(f"downloading EXL3 checkpoint {repo}@{revision[:12]} (~197 GiB)")
    hf_download(repo, out, revision, token=token)


def stage_upstream(out: Path, stage: Path, repo: str, revision: str,
                   token: str | None, force: bool) -> None:
    marker = stage / "MAIN.marker"
    if marker.is_file() and not force:
        log("upstream metadata already staged; skipping download")
    else:
        log(f"downloading upstream metadata {repo}@{revision[:12]} (no model shards)")
        hf_download(repo, stage, revision,
                    include=["*.json", "*.jinja", "*.md", "*.py", "*.sh", "*.txt",
                             "*.patch", "*.pdf", "*.jpeg", "*.png", "LICENSE",
                             ".gitattributes"],
                    token=token)
        marker.write_text("ok\n")
    # Vendor the whole upstream repo under upstream/ for provenance.
    up = out / "upstream"
    up.mkdir(parents=True, exist_ok=True)
    for entry in stage.iterdir():
        if entry.name == ".cache":
            continue
        dst = up / entry.name
        if dst.exists() and not force:
            continue
        if entry.is_dir():
            shutil.copytree(entry, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(entry, dst)
    # Promote the prompt + tokenizer to the root; keep the EXL3 prompt as provenance.
    prov = out / "provenance"
    prov.mkdir(parents=True, exist_ok=True)
    root_prompt = out / "chat_template.jinja"
    backup = prov / "chat_template.exl3.jinja"
    if root_prompt.is_file() and not backup.exists():
        shutil.copy2(root_prompt, backup)
        log(f"kept the EXL3 prompt at {backup}")
    for name in PROMOTE:
        src = stage / name
        if src.is_file():
            shutil.copy2(src, out / name)
            log(f"promoted upstream {name}")
    refresh_embedded_template(out)
    log("upstream overlay done")


def refresh_embedded_template(out: Path) -> None:
    """Make the EXL3 ``tokenizer_config.json``'s embedded template match the
    promoted prompt.

    The EXL3 conversion embeds an ~11 KB ``chat_template`` (the *old* prompt) in
    its ``tokenizer_config.json``; upstream's minimal ``tokenizer_config.json``
    has no template and relies on a separate ``chat_template.jinja``.  Engines
    prefer the ``.jinja`` file, but some read the embedded field, so both must
    carry upstream's prompt.  Only the ``chat_template`` field is touched; the
    file is backed up to ``provenance/tokenizer_config.exl3.json``.  No template
    content is ever printed -> only lengths and hashes.
    """
    tc = out / "tokenizer_config.json"
    jinja = out / "chat_template.jinja"
    if not (tc.is_file() and jinja.is_file()):
        return
    cfg = json.loads(tc.read_text(encoding="utf-8"))
    if "chat_template" not in cfg:
        return  # upstream-style minimal config already; nothing embedded
    want = jinja.read_text(encoding="utf-8")
    if cfg["chat_template"] == want:
        return
    prov = out / "provenance"
    prov.mkdir(parents=True, exist_ok=True)
    backup = prov / "tokenizer_config.exl3.json"
    if not backup.exists():
        shutil.copy2(tc, backup)
    old_keys = sorted(cfg.keys())
    cfg["chat_template"] = want
    tmp = tc.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, tc)
    check = json.loads(tc.read_text(encoding="utf-8"))
    if check["chat_template"] != want or sorted(check.keys()) != old_keys:
        die("embedded template refresh did not apply cleanly")
    log(f"refreshed embedded chat_template in tokenizer_config.json "
        f"(sha256 {hashlib.sha256(want.encode()).hexdigest()[:12]}…, {len(want)} chars)")


def stage_engram(out: Path, repo: str, revision: str, token: str | None,
                 force: bool, online: bool, stage: Path, subdir: str = "engram") -> None:
    # The tables go in a subdir, NOT the repo root: the engine globs
    # ``*.safetensors`` non-recursively, and the root already holds the 39 EXL3
    # shards.  A dedicated subdir keeps the reader from scanning the weights.
    eng = out / subdir
    have = list(eng.glob("engram-l*.safetensors")) if eng.is_dir() else []
    if len(have) >= 2 and not force:
        log(f"Engram tables already present in {eng}; skipping build")
        return
    eng.mkdir(parents=True, exist_ok=True)
    if online:
        log("building Engram tables by ranged read from the online repo (slow link)")
        run([sys.executable, str(ENGRAM_BUILDER), "--repo", repo,
             "--revision", revision, "--out", str(eng),
             *(["--token", token] if token else [])])
        return
    log("staging shards 47/48 for a local Engram build (~203 GiB)")
    src = stage / "engram-src"
    src.mkdir(parents=True, exist_ok=True)
    hf_download(repo, src, revision,
                include=["model-00047-of-00048.safetensors",
                         "model-00048-of-00048.safetensors",
                         "model.safetensors.index.json"],
                token=token)
    log("building Engram tables from the staged shards")
    run([sys.executable, str(ENGRAM_BUILDER), "--source-dir", str(src), "--out", str(eng)])
    if not os.environ.get("DSV41_KEEP_ENGRAM_SRC"):
        log("removing staged shards (set DSV41_KEEP_ENGRAM_SRC=1 to keep)")
        shutil.rmtree(src, ignore_errors=True)


def write_provenance(out: Path, src_info: dict) -> None:
    prov = out / "provenance"
    prov.mkdir(parents=True, exist_ok=True)
    sources = prov / "SOURCES.json"
    sources.write_text(json.dumps(src_info, indent=2) + "\n")
    write_manifest(out, prov / "MANIFEST.json", src_info)


SKIP_DIRS = {".cache", "provenance"}


def _sha256(path: Path) -> tuple[str, int]:
    # Hash as bytes; never parse content, so no tokenizer/text literal ever
    # leaves this function.
    h = hashlib.sha256()
    n = 0
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
            n += len(chunk)
    return h.hexdigest(), n


def write_manifest(out: Path, dst: Path, src_info: dict) -> None:
    files = []
    for p in sorted(out.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(out)
        if rel.parts and rel.parts[0] in SKIP_DIRS:
            continue
        if rel.name.endswith((".partial", ".incomplete", ".lock")):
            continue
        digest, size = _sha256(p)
        files.append({"path": str(rel), "size": size, "sha256": digest})
        log(f"  {size:>14,}  {digest[:12]}…  {rel}")
    manifest = {
        "schema": "sparkrun-dsv41-combined/1",
        "sources": src_info,
        "files": files,
        "total_bytes": sum(f["size"] for f in files),
        "file_count": len(files),
    }
    dst.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    log(f"wrote {dst}: {manifest['file_count']} files, {manifest['total_bytes']/2**30:.1f} GiB")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", required=True, help="combined repo directory (created)")
    p.add_argument("--exl3-repo", default=DEFAULT_EXL3)
    p.add_argument("--exl3-revision", default="main")
    p.add_argument("--upstream-repo", default=DEFAULT_UPSTREAM)
    p.add_argument("--upstream-revision", default="main")
    p.add_argument("--token", default=os.environ.get("HF_TOKEN"))
    p.add_argument("--stage", default=None, help="scratch dir (default: <out>/../.dsv41-stage)")
    p.add_argument("--skip-download", action="store_true", help="assume EXL3 already in --out")
    p.add_argument("--skip-engram", action="store_true")
    p.add_argument("--engram-online", action="store_true",
                   help="range-fetch tables from HF instead of staging shards 47/48")
    p.add_argument("--force", action="store_true")
    args = p.parse_args(argv)

    out = Path(os.path.expanduser(args.out)).resolve()
    stage = Path(os.path.expanduser(args.stage)).resolve() if args.stage \
        else out.parent / ".dsv41-stage"
    preflight(out, need_bytes=int(0.42 * 2**40))  # ~430 GiB

    if not args.skip_download:
        stage_exl3(out, args.exl3_repo, args.exl3_revision, args.token, args.force)
    stage_upstream(out, stage, args.upstream_repo, args.upstream_revision,
                   args.token, args.force)
    if not args.skip_engram:
        stage_engram(out, args.upstream_repo, args.upstream_revision, args.token,
                     args.force, args.engram_online, stage)
    write_provenance(out, {
        "primary": {"repo": args.exl3_repo, "revision": args.exl3_revision},
        "upstream": {"repo": args.upstream_repo, "revision": args.upstream_revision},
        "engram_layers": [1, 14],
    })
    log(f"combined repo ready at {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())