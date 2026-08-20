#!/bin/bash
# Pre-compile FlashInfer SM121 CuTe-DSL kernels with a capped ninja job count
# to avoid OOMing the DGX Spark's 128 GB unified memory during compilation.
# Kernels are cached to ~/.cache/flashinfer/ and reused on subsequent launches.

echo "[ninja-warmup] Pre-compiling FlashInfer SM121 CuTe-DSL kernels (MAX_JOBS=4)..."

MAX_JOBS=4 python -c "
import flashinfer
import b12x
print('[ninja-warmup] FlashInfer kernel compilation complete.')
"
