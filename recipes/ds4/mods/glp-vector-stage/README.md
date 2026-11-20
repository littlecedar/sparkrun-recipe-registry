# glp-vector-stage

Pre-exec staging for the dual-name ("weightless") arm —
[`zz-deepseek-v4.1-flash-1017-weightless-tp4-1m.yaml`](../../zz-deepseek-v4.1-flash-1017-weightless-tp4-1m.yaml).

The steering artifact is a GLP (GGUF Layer Projection) control vector: per-layer unit
directions, fp32, 803,392 bytes, no weights. The engine projects it out of a request's
residual stream (`h ← h − α·(h·d̂)d̂`) at serve time; the checkpoint is never modified. The
file is [msuiche/DeepSeek-V4.1-Flash-1017-abliterated-cyber-GLP-39-L1-39-a0.75][vector]
(MIT, access-gated) at `2715ffd5`, sha256 `9c66d477…f5cf`, 39 layers, α 0.75.

## What it does

`run.sh` runs as root before the serve command, on every rank:

1. refuses a `/cache/runtime` that is not sparkrun's runtime-cache bind mount (same
   filesystem as `/` = the container overlay) — the staged vector would otherwise die with
   the container and the next boot would fail after the weights are already loaded;
2. resolves the file in the node's hub cache under `$HF_HOME` (the recipe's second
   `distribution_config.models.entries` entry puts it there) — missing → **fails the
   launch**, printing the exact `hf download … --revision 2715ffd5…` line;
3. verifies sha256 against the published digest — mismatch → fails the launch, naming both
   digests (a partial download or another revision is not a steered serve);
4. stages it to `/cache/runtime/glp/vector.gguf` through a temporary file and a rename, and
   skips the copy when the destination already holds the same bytes;
5. hands the directory to the user who owns the cache;
6. logs the source, the size and the digest the serve phase will read.

It never downloads and exports nothing: `WEIGHTLESS_STEER_PATH` is recipe-owned, and a mod
that `setdefault`s a variable the image bakes is a silent no-op.

## Why the boot must fail closed

Upstream's plugin and reader both fail closed on a vector they cannot apply, and an engine
that ignores an unknown steer variable serves the stock model under the steered name with
nothing in the output to say so. Staging is the one point where a missing or wrong file can
still be reported as a launch failure instead of a silent behaviour change.

## When the hub cache has no copy

The repository is gated: accept its agreement once per Hugging Face account, then on each
node

```sh
hf download msuiche/DeepSeek-V4.1-Flash-1017-abliterated-cyber-GLP-39-L1-39-a0.75 \
  glp.deepseek-v41-flash-1017-GLP-39-L1-39-a0.75.gguf \
  --revision 2715ffd51f59899115853e1118db080536966c44
```

The mod resolves whatever the hub wrote, so a manual download and the recipe's distribution
entry are the same staging path.

[vector]: https://huggingface.co/msuiche/DeepSeek-V4.1-Flash-1017-abliterated-cyber-GLP-39-L1-39-a0.75
