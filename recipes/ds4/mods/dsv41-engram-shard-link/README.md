# dsv41-engram-shard-link

Pre-exec mod for `recipes/ds4/deepseek-v4.1-flash-1017-gsq-rco-coder-gguf-llamacpp.yaml`.

## What it does

The GSQ-RCO Coder GGUF is six shards: `IQ2_XXS/…-0000i-of-00006.gguf` for i = 1..5 (transformer,
72.12 GB) and the Engram table set as shard 6. The repo stores shard 6 at its **root**, as
`DeepSeek-V4.1-Flash-Engram-IQ4_NL.gguf` (110.60 GB), because the same file also serves the unpruned
GSQ-RCO release. llama.cpp opens shards 2..6 from the directory `-m` points at, so the serve fails
unless shard 6 exists under the shard-6 name.

The mod creates `IQ2_XXS/DeepSeek-V4.1-Flash-1017-GSQ-RCO-Coder-IQ2_XXS-00006-of-00006.gguf` in the
prepared snapshot, pointing at the Engram file. Idempotent (`ln -sfn`), no network, fail-closed.

## Contract

| | |
|:--|:--|
| Runs | pre-exec, before the serve command, inside the container |
| Input | prepared snapshot under `${MOD_HF_HUB:-/cache/huggingface/hub}/models--ISTA-DASLab--DeepSeek-V4.1-Flash-1017-GSQ-RCO-Coder-GGUF/snapshots/<rev>/` |
| Source | that snapshot's `DeepSeek-V4.1-Flash-Engram-IQ4_NL.gguf`, else any node copy of the identical file (the unpruned release's shard 6), largest first |
| Output | the shard-6 symlink in `IQ2_XXS/`; `chown -h` back to the `/cache/runtime` owner |
| Exit | `2` no prepared snapshot; `3` no Engram file on the node; `4` Engram smaller than 90 GiB; `5` link did not resolve |

The 90 GiB floor is a truncation guard, not a size claim: the card's file is 110.60 GB, and a
partially written file would otherwise boot into a model that answers from garbage rows.

## Why not download

The Engram file is byte-identical between the pruned Coder and the unpruned GSQ-RCO release, and on
this fleet `/cache` is the shared BeeGFS pool — so the common case is that the node already has it
and no 110.60 GB transfer is needed. A mod that downloaded would hide that fact and re-fetch per
node. When the file is genuinely absent the mod exits `3` with the one `hf download` line in its
log; staging it into the pool is an explicit, once-per-pool operation.

## Known defect: symlinked caches fail the floor check (measured 2026-11-08)

On the fleet's shared cache every snapshot entry is a **symlink** into the repo's `blobs/`
(`~/.cache/huggingface` → `/mnt/beegfs/huggingface`; the container sees the same tree at `/cache`).
`SIZE="$(stat -c '%s' "${SOURCE}")"` reports the link itself — **76 B** on snapshot `54229d38d5` —
not the 110,595,290,816 B blob, so the mod exits `4` "below the 90 GiB floor" with the Engram fully
staged. Reproduced in a temp hub shaped like the pool (`rc=4`, log `… is 18 B, below the 96636764160 B
floor`). The same class of bug sits in the pool fallback: `find … -type f` never matches a symlinked
snapshot, so a staged copy is invisible to that search. Fix: `stat -Lc '%s'` and a symlink-aware
fallback (`find -L … -type f`). Until then this mod cannot link on this fleet, and the arm stays
authored-not-booted for a tooling reason.

## Offline self-check (run before any boot)

The resolver is the part that can silently mis-point, so exercise it against a synthetic tree.
This is the harness that caught the first draft's wrong `find` depth:

```bash
T=/tmp/engram-selftest; rm -rf "$T"
H="$T/hub/models--ISTA-DASLab--DeepSeek-V4.1-Flash-1017-GSQ-RCO-Coder-GGUF/snapshots/rev1/IQ2_XXS"
mkdir -p "$H" && : > "$H/DeepSeek-V4.1-Flash-1017-GSQ-RCO-Coder-IQ2_XXS-00001-of-00006.gguf"
MOD_HF_HUB="$T/hub" MOD_LOGDIR="$T/logs" ./run.sh; echo "rc=$?"          # 3: no Engram on the node
truncate -s 91G "$T/hub/models--ISTA-DASLab--DeepSeek-V4.1-Flash-1017-GSQ-RCO-Coder-GGUF/snapshots/rev1/DeepSeek-V4.1-Flash-Engram-IQ4_NL.gguf"
MOD_HF_HUB="$T/hub" MOD_LOGDIR="$T/logs" ./run.sh; echo "rc=$?"          # 0: link created
MOD_HF_HUB="$T/hub" MOD_LOGDIR="$T/logs" ./run.sh; echo "rc=$?"          # 0: idempotent no-op
mkdir -p "$T/empty-hub" && MOD_HF_HUB="$T/empty-hub" MOD_LOGDIR="$T/logs" ./run.sh; echo "rc=$?"   # 2: no snapshot
```

`truncate -s` keeps the 91 GiB floor check honest without writing 91 GiB. The second run must
log `already links ... - no-op`, not re-create. The harness uses a **regular** file, which is why it
passes; make the Engram a symlink to a blob (`ln -s ../../../blobs/engram …`) and the run currently
exits `4` — that is the defect above, and the harness should flip to `rc=0` once it is fixed.

Two guard shapes here are deliberate, because both silently converted an intended exit into `rc 1`
during the first draft's own testing: an unmatched glob in a `for` body (`[[ -f "$x" ]] && y=…`)
leaves a failing status behind and `set -e` exits, and a failing `find` used as an assignment
(`X="$(find …)"`) makes the assignment itself fail. Both now use explicit `if`s and `|| true` on the
probes, so the exit codes stay meaningful — a guard whose failure mode is indistinguishable from a
crash cannot be debugged from its log.

## Read path this exposes

The Engram tables stay memory-mapped (llama.cpp's default) and are read one row per decode token.
On the fleet mapping that file lives on BeeGFS at `/cache`, so those reads cross the fabric. A low
first decode number should be attributed to that read path before it is called an engine
regression — see the recipe's caveats.
