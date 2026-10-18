# graft-dsv41-ablit-wo-b

Pre-exec mod for the `cybersec` lane's DeepSeek-V4.1-Flash abliterated arm. It grafts the
**drowzeys `layers.10-35 attn.wo_b` sidecar** onto the **stock EXL3 2.9bpw pack** and
leaves the result under sparkrun's managed runtime cache, so the TensorFold launcher can
serve an abliterated EXL3 pack without a second checkpoint on the Hub.

| | |
|:--|:--|
| Kind | Pre-exec mod; **writes no file under the stock snapshot**. |
| License | AGPL-3.0-or-later (this repo). |
| Source | `drowzeys/DeepSeek-V4.1-Flash-Abliterated-Cybersecurity-Unleashed` (gated: auto, revision pinned) |

## Why it exists

The overlay repo ships **no weights**: two small sidecars plus the author's graft scripts. The
arm is the sidecar spliced onto a stock pack. The stock pack here is
`littlecedar/DeepSeek-V4.1-Flash-EXL3-2.9bpw-with-engram` — the ds4 TP=2 TensorFold lane's
combined repo, whose weight shards are the Mia 2.9bpw pack byte-for-byte and whose `engram/`
subdir holds the Engram tables. One pack on a node therefore serves both TP=2 arms: this mod
grafts from it, and the launcher reads the tables from it through `--stock-model`, so the
second ~189 GiB Engram copy the lane used to build per node is gone.

## Which sidecar (do not mix)

The author's `INSTALL.md` pairs a stock pack with a sidecar, and the pairs are not
interchangeable:

| Stock | Sidecar | Script |
|:--|:--|:--|
| native MXFP4 / Pollard EXL3 3.5bpw / TR3-Hybrid | `wo_b_l10_35.safetensors` (FP8) | `apply_wo_b_graft.py` |
| **Mia EXL3 2.9bpw** | `mia_exl3_wo_b_l10_35.safetensors` **EXL3 mul1 K=5** | `apply_mia_exl3_wob.py` |

This mod uses the **EXL3** pair. The pack's attention is EXL3 mul1 K=5, not FP8, and the
author forbids mixing; combining the Engram tables into the stock repo left the weight shards
untouched, so the pair still applies.

## Mechanics

- **Idempotent from the artifact**: a completed graft carries `ABLIT_META.json` with
  `n_edited == 104`; that short-circuits the whole mod.
- Resolves the stock pack in the container's HF cache (`refs/main` first, else the newest
  config-bearing snapshot) — the recipe never spells a snapshot hash. That ref is not a pin, so
  the no-op path compares the tree's own copied metadata (`config.json`, `tokenizer_config.json`,
  `model.safetensors.index.json`, `quantization_config.json`, `chat_template.jinja`) with the
  snapshot it resolved: a moved `main` must not pair a new table set with the tree's old weights.
- Fetches the author's script + sidecar from the gated overlay at the pinned revision, using
  the node token at `/cache/huggingface/token`.
- Runs the author's script unchanged, with a **symlink view of the stock dir as `--src`** and
  `/cache/runtime/dsv41-ablit` as `--dst`. That view is load-bearing twice over: the script
  `os.link`s each shard it does not edit, and Python's `os.link` uses `link(2)`, which hardlinks
  the *symlink inode* — over the snapshot's own relative `../../blobs/…` links the graft tree would
  hold links that cannot resolve from it, while the view's absolute ones resolve — and it
  `shutil.copytree`s every directory, `engram/` included, which **dereferences** the ~189 GiB table
  set. Measured 2026-10-17 with the view plus a linked `engram/`: a **119 GiB** tree, `du` ==
  `du --apparent-size`, in which only the 24 rewritten shards are real bytes. The mod links the
  stock pack's tables into the graft tree — one Engram set per node — and `--src == --dst` is
  refused, so the stock snapshot is never written.
- **Fail closed**: a missing token, a missing stock pack, an `OUTDIR` that resolves to the
  stock snapshot, an incomplete graft (`n_edited != 104`), or a complete tree whose copied
  metadata disagrees with the resolved stock generation aborts the launch. Serving the stock,
  non-abliterated checkpoint under this arm's name — or silently serving a mixed generation — is
  worse than a failed boot; delete `OUTDIR` to rebuild.

## The budget constraint (why this is synchronous)

The graft rewrites the 24 shards (of 39) that carry `layers.10-35 attn.wo_b` (~5 GiB each) and
hardlinks the rest, and it must finish inside sparkrun's **hard-coded 600 s** pre-exec hook
budget (`sparkrun/orchestration/hooks.py::run_pre_exec`) — a recipe cannot raise it.

Deferring the graft (start it detached, hold the serve command on a wrapper that waits for the
sentinel) **was tried and does not work on a cluster launch**: sparkrun holds the head on its
rendezvous/readiness gate (~300 s) before the serve command's own `readiness.port_timeout_s`
applies, so the head is declared dead while the wrapper is still waiting. Measured
2026-10-14 (task `sparkrun_d42e44075b9357cd_c390039d73a3`: "Head node failed to become ready on
`.32`" 318 s in, with the wrapper still polling). A cold node whose graft cannot fit the
600 s budget is therefore a launch failure, not a degraded serve — pre-warm the graft out of
band for such a node.

## Knobs

`STOCK_REPO` (default `littlecedar/DeepSeek-V4.1-Flash-EXL3-2.9bpw-with-engram`), `OVERLAY_REPO`,
`OVERLAY_REVISION`, `OUTDIR` (default `/cache/runtime/dsv41-ablit`), `WORKDIR`,
`TOKENFILE`, `HF_HUB`.
