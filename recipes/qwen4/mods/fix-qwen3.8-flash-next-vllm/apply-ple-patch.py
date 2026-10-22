#!/usr/bin/env python3
"""Insert the PLE_FORCE_FP8 early return into the installed ple_layer.py.

The three-line hunk in patches/ple-force-fp8.patch does not always apply to this
image (line numbers move). Inserting above the first
`if not isinstance(quant_config, Fp8Config):` is the reliable path.

https://github.com/humanrouter/qwen38-flash-next-2x-spark/blob/main/scripts/apply-ple-patch.py

Runs INSIDE the serve container (sparkrun mods exec there, as root), so it patches the
module the engine will import. The path is discovered, not hard-coded: this image ships
it under a python3.12 dist-packages tree whose exact layout has moved between builds, and
a hard-coded path silently fell through to writing a copy nothing imports.
"""
from __future__ import annotations

import glob
import pathlib
import sys
import sysconfig

NEEDLE = "if not isinstance(quant_config, Fp8Config):"
INSERT_LINES = [
    "import os",
    'if os.environ.get("VLLM_PLE_FP8_CHECKPOINT") == "1":',
    "    return Qwen3_8FlashNextPLEFp8EmbeddingMethod()",
]


def apply(src: str) -> str:
    # The marker is the env var the inserted branch reads; the upstream guard looked for
    # "PLE_FORCE_FP8", which the inserted lines never contain, so a second run duplicated the block.
    if "VLLM_PLE_FP8_CHECKPOINT" in src:
        return src
    lines = src.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.strip() == NEEDLE:
            indent = line[: len(line) - len(line.lstrip())]
            block = [indent + l + "\n" for l in INSERT_LINES]
            return "".join(lines[:i] + block + lines[i:])
    raise SystemExit(f"anchor not found: {NEEDLE!r} — refusing to write an unpatched file")


def find_modules() -> list[pathlib.Path]:
    roots = {
        sysconfig.get_paths()["purelib"],
        sysconfig.get_paths()["platlib"],
        "/usr/local/lib/python3.12/dist-packages",
    }
    # nvidia only: GB10 has no ROCm path, and the amd copy carries neither the anchor nor b12x support.
    hits = sorted(
        p for r in roots for p in glob.glob(r + "/vllm/**/nvidia/ple_layer.py", recursive=True)
    )
    if not hits:
        raise SystemExit(f"nvidia/ple_layer.py not found under {sorted(roots)}")
    return [pathlib.Path(h) for h in hits]


def main() -> None:
    for target in find_modules():
        src = target.read_text()
        # The b12x builds ship their own PLE layer that passes quant_config=None on the b12x path,
        # so the upstream Fp8Config guard this patch precedes no longer exists there. Nothing to do.
        if "_use_b12x" in src and NEEDLE not in src:
            print(f"{target} is b12x-aware with no upstream Fp8Config guard; nothing to patch")
            continue
        patched = apply(src)
        if patched == src:
            print(f"{target} already carries the PLE_FORCE_FP8 guard; nothing to do")
            continue
        backup = target.with_suffix(target.suffix + ".orig")
        if not backup.exists():
            backup.write_text(src)
        target.write_text(patched)
        print(f"patched {target} in place ({len(patched)} bytes, backup {backup.name})")


if __name__ == "__main__":
    main()
