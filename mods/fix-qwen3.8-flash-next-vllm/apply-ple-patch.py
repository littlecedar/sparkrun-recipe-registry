#!/usr/bin/env python3
"""Extract ple_layer.py from the vLLM image and insert the PLE_FORCE_FP8 early return.

The three-line hunk in patches/ple-force-fp8.patch does not always apply to this
image (line numbers move). Inserting above the first
`if not isinstance(quant_config, Fp8Config):` is the reliable path.

https://github.com/humanrouter/qwen38-flash-next-2x-spark/blob/main/scripts/apply-ple-patch.py
"""
from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys

NEEDLE = "if not isinstance(quant_config, Fp8Config):"
INSERT_LINES = [
    "import os",
    'if os.environ.get("VLLM_PLE_FP8_CHECKPOINT") == "1":',
    "    return Qwen3_8FlashNextPLEFp8EmbeddingMethod()",
]
CONTAINER_PATH = (
    "/usr/local/lib/python3.12/dist-packages/vllm/models/"
    "qwen3_8_flash_next/nvidia/ple_layer.py"
)


def apply(src: str) -> str:
    if "PLE_FORCE_FP8" in src:
        return src
    lines = src.splitlines(keepends=True)
    out: list[str] = []
    inserted = False
    for line in lines:
        if not inserted and NEEDLE in line:
            indent = line[: len(line) - len(line.lstrip(" "))]
            for ins in INSERT_LINES:
                out.append(f"{indent}{ins}\n")
            inserted = True
        out.append(line)
    if not inserted:
        raise SystemExit(
            f"could not find {NEEDLE!r} in extracted ple_layer.py — "
            "image layout changed; insert the 3-line PLE_FORCE_FP8 return by hand "
            "above that check"
        )
    return "".join(out)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--image",
        default="vllm/vllm-openai:qwen38-flash-next",
        help="vLLM image to extract from",
    )
    p.add_argument(
        "--out",
        default=None,
        help="output path (default: <repo>/patched/ple_layer.py)",
    )
    args = p.parse_args()
    repo = pathlib.Path(__file__).resolve().parents[1]
    out = pathlib.Path(args.out) if args.out else repo / "patched" / "ple_layer.py"
    out.parent.mkdir(parents=True, exist_ok=True)
    print(f"extracting {CONTAINER_PATH} from {args.image}", file=sys.stderr)
    patched = apply(extract(args.image))
    out.write_text(patched)
    print(f"wrote {out} ({out.stat().st_size} bytes, PLE_FORCE_FP8 inserted)")


if __name__ == "__main__":
    main()