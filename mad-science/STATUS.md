# Board — 2026-10-22 04:07 ET census, 03:49 ET gate

Four verdicts landed between 03:30 and 03:45 ET: TP=4 is **closed as a checkpoint limit** on this NVFP4 export, W12 **served** for the first time, the SGLang `v0.5.22` bump closed with six arms held, and Spark-X2.6's FP8 tier is measured-rejected despite being 2× faster. **Nothing on this board waits on the owner** — every Attention item was acknowledged and is closed below.

**Baseline = `recipes/ds4/deepseek-v4.1-flash-knapcio-tp4-1m-sglang.yaml`** (DSv4-Flash knapcio, **TP=4, 1M window** — owner decision 2026-10-22, `#48`): TP=4 is the foundation shape and TP=2 arms supplement it; **GLM-5.3 3bpw TP=4 is deferred** for a few days, and knapcio is the one that is measured (house 36/37, needle 3/3 to ~983k, C1 69.28 → C10 116.27 t/s).

## Now

| where | what | since | state |
|---|---|---|---|
| `.34` | drama-3 TTS arm — finished | 04:07 | **0 containers**, arm stands: deterministic under `seed` (byte-identical decodes), RTF **0.813** at 28.7 s audio, TTFA 0.646 s; the boot that carried `stage_init_timeout: 1800` is what closed it |
| `.35` | Spark-X2.6 **INT8** attempt, then the re-assigned **FP8 `--max-tokens 8192`** verdict cell | 04:07 | **dead serve**: container `sparkrun_f30a2cdba68653a9_64af2f7668b6_solo` (image `fd8439732b16`) is up 15 min but its serve died at 03:53 ET — `NotImplementedError: No implemented int8_scaled_mm for current compute capability` on `XHToken/Spark-X2.6-4B-INT8`; the 8192-cell FP8 verdict is the assignment |
| `.31`–`.33` | ds4 TP=2 twin A/B + ornith-122b node-local NVFP4/GGUF boots | 04:07 | **queued, nothing measuring**: all four data nodes at **0 containers**; load 0.35 / 0.52 / 0.84 (`.NN` / `.32` / `.33`) |
| `<head-node>` | **cluster-wide disk blocker** — a boot needing 59.76 GB died with `insufficient disk space on control` | 04:07 | **141 GB free of 3.7 TB** after the 2026-10-22 sweep (docker 20 images / 0 containers / 0 build cache); the blocker is closed as a **rule, not a number**: bodies **above 60 GB are node-local** (`hf download` on the target node or a node-to-node copy, plus `--offline` at launch) and the control staging path is for **≤ 60 GB** only, because the head's space is shared by every concurrent session and one 78 GB stage eats nearly all of it (`AGENTS.md` §Node hygiene) — the one image the sweep wrongly deleted (`vllm/vllm-openai:v0.32.0@sha256:befccf0e…`, the explore qwen-image/Laguna pin) is re-pulled **by digest** and re-tagged `vllm/vllm-openai:v0.32.0` on the head, `RepoDigest` verified |

## Attention

All seven former rows were **acknowledged by the owner on 2026-10-22** and are closed by subject — nothing here needs a decision. TP=4 on the qwen4 labquant NVFP4 export is **closed as a checkpoint limit**, and the failure signature is being retired with the materials to `attic/qwen4/AGENTS.md` (do not re-try another nightly: it is the checkpoint, not the build). The llama.cpp **ref floor `a37cc4610`** (below it 7.9–8.4 t/s vs 98–103) is a rule in `attic/explore/AGENTS.md` §"The ref floor moved" and `mad-science/LLAMACPP-GGUF.md` §1. `@littlecedar/<name>` **resolving the published registry** and a `@sha256:` pull **landing untagged** are both rules in `AGENTS.md` §serving traps (pass the recipe file path; re-tag at once and grep the pin before every boot). `readiness.inference: false` **making "HTTP-ready" satisfiable by a dead serve** is a rule too — the drama item asserts `/v1/models` names the model, and today's `.35` INT8 container is exactly that shape. **Mellum MTP's rejection is under challenge** by the owner: a draft-length sweep (1–8 against the vendor value) is in flight and its verdict lands in the lane docs, so the board does not pre-empt it. Both **licence banners are accepted** (2026-10-22) — the Timestral weights' modified-MIT $20M/month revenue cap and indra-ocr's modified OpenRAIL — and still ship inside the recipes because they bind downstream users; runtime, not permission, is those arms' remaining gap.

## Gate

| suite | plain validate | strict validate | tip | measured at |
|---|---|---|---|---|
| **899 tests OK** (2 skipped) | **56/56**, 0 errors | **17/56 fail** (known false positives) | `4570ade` | suite, plain and strict at **03:49 ET** — not re-run since; the tree has moved past that tip, so treat these as the last measurement, not as fresh |

## Recently landed

| time ET | commit | one clause |
|---|---|---|
| 03:45 | `4570ade` | **W6 closed as a checkpoint limit** (41/41 shards, then the same assertion on every rank) and **W12 served**: 42.8/51.2/40.1 t/s, `max_model_len` 262144, KV 1,757,475 tok (6.70×), 19 min cold |
| 03:36 | `146b13c` | **FP8 rejected**: 40.80 / 77.06 / 146.63 / 217.58 t/s (+100/+66/+48/+39 %) but house 109/111 = 98.2 %, `trick-2` looping to 4096 reasoning tokens with empty content — and `max_num_seqs: 96` is inert (pool 743,780), so 32 stays |
| 03:35 | `767a0f8` | the drama-3 row points at the baked `stage_init_timeout: 1800` instead of an override |
| 03:33 | `9f12054` | drama-3 **parked**: 37.69 GiB loaded in 242.84 s, then killed 2 s after `torch.compile` by vllm-omni's default 300 s stage deadline |
| 03:22 | `ff33ec5` | the ~15 % is the **upstream ref era**, not the fork's build: the fork's tree through our Dockerfile measures 114.2/113.9 and is 1254 commits older |
| 03:11 | `cc05822` | W12 loads through safetensors — instanttensor cannot shard at TP=2 on the pinned image |

## Pointers

`mad-science/TODO.md` = the queue (work items and `# DECISIONS`). `mad-science/SESSION-RECORD.md` = dated history. `recipes/<lane>/README.md` = per-arm evidence.
