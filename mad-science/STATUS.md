# Board — 2026-10-22 03:21 ET

Six of the night's streams closed with a verdict; four are still moving. Gate **899 tests OK**, plain validate **54/54** with 0 failures, strict **17/54** — the same seventeen known false positives, no new ones.

## Now

| where | what | since | state |
|---|---|---|---|
| `.30`–`.33` | `tp4-queue` — W6 → W12 → ds4 TP=4 → four-node suite, resumable | 01:52 | **idle, not running** — census 03:35 ET: `.30`/`.31`/`.32` at 0 containers and `.33` held by the Spark-X2.6 FP8 cell, so a quartet boot waits on `.33`; W6 **failed at the engine** (`modelopt_quant.py:2624`, gated-activation MoE padding, every rank, fit was 21 GiB/rank); W12 boot 6 died in `_restrict_instanttensor_to_selected_ranges` because the pinned b12x image's `instanttensor` has no `_determine_buffer_size`, so the arm now loads through **safetensors** (03:11) and the PLE mod patches the installed module in place (03:04); **no W12 number yet** |
| `.34` | `drama-probe` — drama-3 on the resident vLLM-Omni nightly | 02:26 | **the node is clear again** (0 containers at 03:35 ET; the dead serve's container, task `c8829c3570d86002`, is gone), so the blocker is now only a re-boot: that serve died at `Orchestrator initialization failed … not ready within 300s` (02:41 ET) while sparkrun had still printed HTTP-ready — boot by **file path** and assert `/v1/models` names drama-3 |
| `.33` | `sparkx-probe` — FP8 tier A/B live, bf16 settled as the control | 03:19 | **bf16 is a control**: C1 20.38 ± 0.09 is 61 % of the ~33 t/s roofline, so the ≥25 t/s falsifier fired; the **FP8 arm is running** since 03:18:56 ET (`XHToken/Spark-X2.6-4B-FP8`, 779,390 tokens pooled, `max_running_requests` 32, ~40 t/s per stream at 03:32) — its receipt is the open cell, and a ladder above c10 needs `max_num_seqs` raised past 32 |
| repo | `ds4-refresh` — fork-patch experiment on the EXL3 decode regression | 03:04 | **nothing landed**: no commit since `1099db9`, so the 8 t/s build still has no replacement and every arm keeps its own `container:` pin |

## Attention

| what | why it matters | where it is tracked |
|---|---|---|
| A llama.cpp **ref below `a37cc4610`** (e.g. `9df0b73c7`) decodes **7.9–8.4 t/s** where `a37cc4610` does 98–103 — ref-level, reproduced from a clean rebuild, fixed upstream in `a37cc4610` (2026-10-22) | never pin below it; the fix ships in the ref this lane already uses | `attic/explore/AGENTS.md` §"The ref floor moved to `a37cc4610`" |
| `sparkrun run @littlecedar/<name>` resolves the **published registry**, not the worktree (2026-10-22: a bump boot served `v0.5.21` while the file said `v0.5.22`) | pass the recipe **file path** for any bump or candidate boot | `AGENTS.md` §serving traps; `recipes/ornith/README.md` |
| `docker pull repo:tag@sha256:…` stores the image **untagged**, so a peer's `image prune` deletes the very build just pulled (2026-10-22) | re-tag at once, and guard the pin before every boot: `grep -q e3a4f060 <recipe>` | `AGENTS.md`; `recipes/ornith/README.md` |
| **Mellum MTP is rejected** on the shipped engine: 108.4/109.9 t/s against the pre-registered 114 bar, acceptance 0.80, mean len 1.80 (measured 03:18) | the earlier "+44 %" was a slow-baseline artefact and must not be quoted | `recipes/explore/README.md`; `attic/explore/AGENTS.md` |
| Two licence banners owed before either arm ships (registered 02:28–02:35): Timestral **Modified MIT at a $20M/month revenue cap**; indra-ocr **modified OpenRAIL whose share-alike reaches the output** | owner decision, not a footnote — and the banner must not conflate Apache-2.0 code with restricted weights | `mad-science/TODO.md` explore items |

## Gate

| suite | plain validate | strict validate | tip | measured at |
|---|---|---|---|---|
| **899 tests OK** (2 skipped) | **54/54**, 0 errors | **17/54 fail** (known false positives) | `014e0b2` | suite 03:21 ET, plain and strict 03:21 ET — tracked bytes at `014e0b2`; tree dirty: 1 path (the spark-x2.6 recipe mid-edit, itself clean in both modes) |

## Recently landed

| time ET | commit | one clause |
|---|---|---|
| 03:22 | `ff33ec5` | the ~15 % is the **upstream ref era**, not the fork's build: the fork's tree `b2e5e9b` through our Dockerfile and flags measures 114.2/113.9, and `b2e5e9b` is 1254 upstream commits older — so no flag or CUDA difference matters |
| 03:18 | `014e0b2` | same-node A/B closes the residual: fork 114.1/116.2 vs upstream 100.3/98.7, and a CUDA-13.1.1 upstream build buys nothing (99.4/100.6) |
| 03:11 | `cc05822` | W12 loads through safetensors — instanttensor cannot shard at TP=2 on the pinned image |
| 03:10 | `6b82a39` + `6a1129d` | the spark-x2.6 control carries its measured outcome; the battery gains `--thinking on\|off` |
| 03:07 | `475d07f` | humanizer Q6_K ships: C1 17.92 ± 0.04 t/s, 0/40 fact errors vs the baseline's 1, TTR 10.8 s, `/v1/completions` only |
| 03:04 | `29410d2` | the `v0.5.22` re-pin is **closed** — six arms held (TTR 238/251/129/94/94/240 s, house 37-37/37-37/—/32-37/33-37/36-37, arm A n=5 C1 97.6 ± 8.8), index digest `e3a4f060…` verified with `imagetools inspect`, 0 OSV advisories |

## Pointers

`mad-science/TODO.md` = the queue (work items and `# DECISIONS`). `mad-science/SESSION-RECORD.md` = dated history. `recipes/<lane>/README.md` = per-arm evidence.
