# reown-runtime-cache

Hand root-created runtime-cache subtrees back to the user the serve runs as, and
fail the launch if the hand-back does not stick.

## Why it exists

Mods and `pre_exec` hooks run as root; the serve runs as the owner of the
`/cache/runtime` bind mount. A hook that imports `flashinfer` while verifying
creates its JIT cache under `FLASHINFER_WORKSPACE_BASE/.cache/flashinfer`
(`flashinfer/jit/env.py`, fixed at import in 0.7.3), which for the ERNIE
sparse-MLA hook resolved to
`/cache/runtime/flashinfer/.cache/flashinfer/0.7.3/121a/flashinfer_jit.log`.
That file was born `0:0`. Every later uid-1000 serve on the node then dies
`PermissionError`, and uid 1000 cannot unlink a root-owned file, so the defect
is sticky: measured rank 3 on `.35` on 2026-11-11 (register row
`runtime-cache-flashinfer-root-owned-subtree`), repaired by a chown.

## What it does

- Infers the cache owner from the mount root (`MOD_CACHEDIR`, default
  `/cache/runtime`), exactly as the harness does, and logs `USER_UID:GID`.
- Reowns only the paths a root hook is known to create: `REOWN_PATHS`
  (default `/cache/runtime/flashinfer /cache/runtime/.cache`). Absent paths are
  skipped, not created. Model snapshot trees are deliberately **not** walked —
  a recursive chown over 35 GB of weights is not a permission fix.
- Logs each path's owner before and after and counts the paths it changed.
- **Fails closed**: after `chown`, it stats the path again and exits non-zero
  naming the path if the owner is still not the cache owner. A repair that
  silently did not stick must stop the launch, not log success.

Idempotent, `set -euo pipefail`; idle paths cost two `stat`s.

## Order

A mod list is `pre_exec` order. This mod must come **after** every mod that
writes the cache root (list it last), because its repair is a check of what
that hook just did. It also repairs leftover root-owned trees from an earlier
boot, which is the failure the row measured.

## What it does not cover

- The host-side HuggingFace cache (`~/.cache/huggingface`).
  `sparkrun setup fix-permissions` owns that path: it chowns that directory by
  default, and `--cache-dir` points it elsewhere (`scripts/fix_permissions.sh`).
- Nothing in sparkrun detects root-owned files under the *runtime* cache
  (`~/.cache/sparkrun/runtime-cache` on the host); the launch only creates and
  stamps the leaf as the substrate user. Use
  `sparkrun setup fix-permissions --cache-dir ~/.cache/sparkrun/runtime-cache`
  for the host-side repair; this mod is the prevention inside the container.

## Knobs

| Env | Default | Meaning |
|---|---|---|
| `REOWN_PATHS` | `/cache/runtime/flashinfer /cache/runtime/.cache` | Space-separated container paths to reown |
| `MOD_CACHEDIR` | `/cache/runtime` | Mount root the owner is inferred from |
| `MOD_TIMEOUT` | `120` | Harness log-read timeout |
