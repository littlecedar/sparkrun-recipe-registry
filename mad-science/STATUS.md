# Board — 2026-10-22 04:07 ET census

| field | value |
|---|---|
| census | 2026-10-22 **04:07 ET**, all six nodes |
| gate | **922 tests OK** (2 skipped) at `2007b6e`-era tree, 2026-10-22; validate **56/56** plain, **17/56** strict at `4570ade` 03:49 ET, where that run read **899 tests OK** (not re-run since) |
| baseline (`#48`) | DSv4-Flash **knapcio TP=4 1M** — `recipes/ds4/deepseek-v4.1-flash-knapcio-tp4-1m-sglang.yaml`; C1 **69.28 ± 5.25** → C10 **116.27 ± 6.22** (1.68×), house **36/37**, needle **3/3** at 32,768 / 131,072 / 983,040 (981,950 tok) — **re-measured 2026-10-22 on a fresh online boot** (`.30`–`.33`, task `sparkrun_a2e141223b52793c_d7960e70d961`, TTR 544 s, `max_model_len` 1,048,576, KV 6,849,792): C1 **60.20** / C2 85.13 / C5 114.87 / C10 **116.86** (n=5, `--skip-run`), house **37/37** @4096 thinking-on, needle **5/5** at ~999k (depths 10–50); the 69.28 / 36/37 figures stay the historical row, not replaced |
| foundation shape | **TP=4**; TP=2 arms supplement it; GLM-5.3 3bpw TP=4 **deferred** ("in a few days") |
| easy-traffic gate (`#49`) | single node qualifies only at C1 **≥ 69.28** *and* C10 **≥ 116.27** t/s, **≥ 10** streams, house **37/37** @4096 thinking-on — nothing clears it yet |
| owner queue | **empty** — all seven Attention rows acknowledged and closed 2026-10-22 |
| verdicts 03:30–03:45 | TP=4 **closed as a checkpoint limit**; W12 **served**; SGLang `v0.5.22` bump closed with six arms held; Spark-X2.6 FP8 **fails C1** despite +100/+66/+48/+39 % at c1/2/5/10 |

## Now

| where | owner | what | since | state |
|---|---|---|---|---|
| `.34` | drama-probe | drama-3 TTS arm — finished | 04:07 | **0 containers**, arm stands: RTF **0.813** @28.7 s audio, TTFA **0.646 s**, seeded decodes byte-identical; closed by the boot carrying `stage_init_timeout: 1800` |
| `.35` | sparkx-probe | Spark-X2.6 **INT8** attempt, then the re-assigned **FP8 `--max-tokens 8192`** verdict cell | 04:07 | **dead serve**: container `sparkrun_f30a2cdba68653a9_64af2f7668b6_solo` (image `fd8439732b16`) up 15 min but its serve died 03:53 ET — `NotImplementedError: No implemented int8_scaled_mm for current compute capability`; the 8192-cell FP8 verdict is the assignment |
| `.31`–`.33` | ds4 queue | ds4 TP=2 twin A/B + ornith-122b node-local NVFP4/GGUF boots | 04:07 | **queued, nothing measuring**: 0 containers on all four data nodes; load 0.35 / 0.52 / 0.84 (`.NN` / `.32` / `.33`) |
| `<head-node>` | control | **disk/staging blocker** — a boot needing **59.76 GB** died with `insufficient disk space on control` | 04:07 | **141 GB free of 3.7 TB** after the sweep (docker 20 images / 0 containers / 0 build cache); closed as a **rule, not a number**: bodies **> 60 GB node-local** (`hf download` on the node or node-to-node copy + `--offline`), control staging **≤ 60 GB** only, because the head is shared and one 78 GB stage eats nearly all of it (`AGENTS.md` §Node hygiene); the image the sweep wrongly deleted (`vllm/vllm-openai:v0.32.0@sha256:befccf0e…`, the explore qwen-image/Laguna pin) is re-pulled **by digest**, re-tagged, `RepoDigest` verified |

## Attention

| # | item | state | evidence | owner |
|---|---|---|---|---|
| 1 | TP=4 on the qwen4 labquant NVFP4 export | **closed — checkpoint limit**; do not re-try another nightly | gated-activation padding assertion on **all four ranks** after 41/41 shards load; signature retiring to `attic/qwen4/AGENTS.md` | ack 2026-10-22 |
| 2 | llama.cpp ref floor `a37cc4610` | **rule** — never pin below it | below it 7.9–8.4 t/s vs 98–103; `attic/explore/AGENTS.md` §"The ref floor moved", `mad-science/LLAMACPP-GGUF.md` §1 | ack 2026-10-22 |
| 3 | `@littlecedar/<name>` resolves the **published** registry | **rule** — pass the recipe file path | a bump boot served `v0.5.21` while the file said `v0.5.22`; `AGENTS.md` §serving traps | ack 2026-10-22 |
| 4 | `docker pull …@sha256:` lands **untagged** | **rule** — re-tag at once, grep the pin before every boot | a peer `image prune` deleted a just-pulled build; `AGENTS.md` §serving traps | ack 2026-10-22 |
| 5 | `readiness.inference: false` lets "HTTP-ready" be a dead serve | **rule** — assert `/v1/models` names the model | drama reported HTTP-ready 14.7 s while its serve had died at `sock.bind`; `.35`'s INT8 container is the same shape | ack 2026-10-22 |
| 6 | Mellum MTP | **rejected — and the rejection holds as a curve** (sweep 1–8 measured) | n=1 **103.38 ± 2.83** (+1.9 % over pooled baseline **101.50 ± 0.74**), then **90.02 / 75.94 / 66.60 / 51.38 / 47.73** at 2/3/4/6/8, acceptance saturating 2.0–2.3; verdict `recipes/explore/README.md`, receipt `~/benchmarks/mellum-mtp-draft-20261022/` | challenged, now landed |
| 7 | two licence banners — Timestral, indra-ocr | **accepted 2026-10-22**; banners still ship inside the recipes | Timestral weights **modified MIT, $20M/month cap** (code Apache-2.0); indra-ocr **modified AI Pubs OpenRAIL-M, $20M cap + no-compete + output share-alike**; runtime, not permission, is their remaining gap | ack 2026-10-22 |

## Measurements

| arm | node set | cells | verdict | receipt |
|---|---|---|---|---|
| knapcio TP=4 1M (baseline) | 4 nodes | C1 **69.28 ± 5.25** / C2 86.40 / C10 **116.27 ± 6.22**; house 36/37; needle 3/3 to 981,950 — 2026-10-22 fresh boot: C1 **60.20** / C10 **116.86**, house **37/37**, needle **5/5** at ~999k | **the bar**, not a candidate | `recipes/ds4/README.md`; `~/benchmarks/knapcio-tp4-20261022/` (head: REPORT.md, perf-ladder.json, sparkrun_serve.log) |
| Mellum2.1-12B-A2.5B-Q4_K_M (llama.cpp) | 1 (`.32`) | C1 **102.03 ± 0.35**; C10 **unmeasured**; house unmeasured | passes C1 (+47 %), needs C10 + battery | `~/benchmarks/mellum-mtp-draft-20261022/` |
| Spark-X2.6-4B FP8 (`v0.5.22`) | 1 | **40.80 / 77.06 / 146.63 / 217.58** at c1/2/5/10 (5.3×); house **37/37** on the 4096 rerun (first pass 109/111 = 98.2 %, `trick-2` runaway) | **shipped fast tier**; fails the easy-traffic gate on C1 | `~/benchmarks/spark-x26-20261022/` |
| Spark-X2.6-4B INT8 | 1 (`.35`) | — | **dead at the kernel** — no `int8_scaled_mm` on sm_121; do not re-boot | `.35` serve log |
| drama-3 TTS | 1 (`.34`) | RTF **0.813** @28.7 s, TTFA 0.646 s, seeded byte-identical, unseeded 4.2–7.7 s (σ0.93) | **arm stands** | `~/benchmarks/drama-20261022/` |
| qwen4 W12 vLLM TP=2 | 2 | **42.8 / 51.2 / 40.1** t/s, `max_model_len` 262144, KV 1,757,475 tok (6.70×), 19 min cold | served — cross-runtime column filled | `4570ade` |
| Mellum MTP draft sweep | 1 (`.32`) | **103.38** (n=1) → **90.02 / 75.94 / 66.60 / 51.38 / 47.73** (2/3/4/6/8) | **rejected**, monotone decreasing from n=1 | `~/benchmarks/mellum-mtp-draft-20261022/` |
| llama.cpp fork A/B | same node | fork tree **114.2 / 113.9** vs `a37cc4610` 98–103; fork is 1254 commits older | the ~15 % is the **upstream ref era**, not the build | `ff33ec5` |

## Gate

| suite | plain validate | strict validate | tip | measured at |
|---|---|---|---|---|
| **922 tests OK** (2 skipped) | **56/56**, 0 errors | **17/56 fail** (known false positives) | suite at `2007b6e`; validates at `4570ade` | suite 2026-10-22 this session; validates 03:49 ET — the validates are the last measurement, not fresh |

## Recently landed

| time ET | commit | one clause |
|---|---|---|
| 04:2x | `2007b6e` | `#49` easy-traffic gate + candidate ledger recorded; board converted to table-only |
| 04:1x | `15c677b` | recovered examine items folded into the queue (orca, sage, minimax-H3, pyannote) and `#48` knapcio baseline |
| 03:45 | `4570ade` | **W6 closed as a checkpoint limit** (41/41 shards, then the same assertion on every rank) and **W12 served**: 42.8/51.2/40.1 t/s, `max_model_len` 262144, KV 1,757,475 tok (6.70×), 19 min cold |
| 03:36 | `146b13c` | **FP8 rejected**: 40.80 / 77.06 / 146.63 / 217.58 t/s (+100/+66/+48/+39 %) but house 109/111 = 98.2 %, `trick-2` looping to 4096 reasoning tokens with empty content — and `max_num_seqs: 96` is inert (pool 743,780), so 32 stays |
| 03:35 | `767a0f8` | the drama-3 row points at the baked `stage_init_timeout: 1800` instead of an override |
| 03:33 | `9f12054` | drama-3 **parked**: 37.69 GiB loaded in 242.84 s, then killed 2 s after `torch.compile` by vllm-omni's default 300 s stage deadline |
| 03:22 | `ff33ec5` | the ~15 % is the **upstream ref era**, not the fork's build: the fork's tree through our Dockerfile measures 114.2/113.9 and is 1254 commits older |
| 03:11 | `cc05822` | W12 loads through safetensors — instanttensor cannot shard at TP=2 on the pinned image |

## Pointers

| doc | holds |
|---|---|
| `mad-science/TODO.md` | the queue and `# DECISIONS` (`#48` baseline, `#49` easy-traffic gate) |
| `mad-science/SESSION-RECORD.md` | dated history |
| `recipes/<lane>/README.md` | per-arm evidence and receipts |
