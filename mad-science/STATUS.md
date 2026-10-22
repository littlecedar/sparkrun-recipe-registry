# Board — 2026-10-22 ~14:00 ET census

| field | value |
|---|---|
| census | 2026-10-22 **~14:00 ET**, all six nodes |
| gate | **928 tests OK** (2 skipped) at `eb1a2a4`, measured 2026-10-22 ~14:00 ET; validate **not re-run this hour** (last: **56/56** plain, **17/56** strict at `4570ade` 03:49 ET) |
| baseline (`#48`) | DSv4-Flash **knapcio TP=4 1M** — `recipes/ds4/deepseek-v4.1-flash-knapcio-tp4-1m-sglang.yaml`; C1 **69.28 ± 5.25** → C10 **116.27 ± 6.22** (1.68×), house **36/37**, needle **3/3** at 32,768 / 131,072 / 983,040 (981,950 tok) — **re-measured 2026-10-22 on a fresh online boot** (`.30`–`.33`, task `sparkrun_a2e141223b52793c_d7960e70d961`, TTR 544 s, `max_model_len` 1,048,576, KV 6,849,792): C1 **60.20** / C2 85.13 / C5 114.87 / C10 **116.86** (n=5, `--skip-run`), house **37/37** @4096 thinking-on, needle **5/5** at ~999k (depths 10–50); the 69.28 / 36/37 figures stay the historical row, not replaced; the `60.20` was taken while **the same four ranks served the fleet's own inference**, so the 13 % C1 deficit is `LIKELY` self-inflicted contention and `69.28` is **not a like-for-like control today** (`recipes/ds4/README.md:218-225`) |
| foundation shape | **TP=4**; TP=2 arms supplement it; GLM-5.3 3bpw TP=4 **deferred** ("in a few days") |
| easy-traffic gate (`#49`) | single node qualifies only at C1 **≥ 69.28** *and* C10 **≥ 116.27** t/s, **≥ 10** streams, house **37/37** @4096 thinking-on — nothing clears it yet |
| owner queue | **one open item** — `#8` (larger prefill chunk) is a boot-gated experiment awaiting an owner go; `#9` recorded not fixed; `#10` is a rule; `#1`–`#7` acknowledged and closed 2026-10-22 |
| verdicts 03:30–03:45 | TP=4 **closed as a checkpoint limit**; W12 **served**; SGLang `v0.5.22` bump closed with six arms held; Spark-X2.6 FP8 **fails C1** despite +100/+66/+48/+39 % at c1/2/5/10 |

## Now

| where | owner | what | since | state |
|---|---|---|---|---|
| `.34` | control | idle after today's **Sage-A1.5 FP8** gate cell and the **pyannote** CPU diarization boot | ~14:00 | **0 containers**; both arms stand as measured rows, not as assignments |
| `.35` | control | idle after the **Ornith-1.5-122B NVFP4** one-node gate cell | ~14:00 | **0 containers**; the INT8 dead serve is **not an assignment** — it lives in Measurements only (dead at the kernel, no `int8_scaled_mm` on sm_121) |
| `.30`–`.33` | control | **production inference** — these ranks serve the fleet's own model (the knapcio TP=4 1M baseline arm, `#48`), i.e. a serving surface, not a cell surface; **`.30` is the control node**, so driving the cluster from it (ssh, `sparkrun` launches, config, inspection, log reads) is expected work | 08:49:58 | serve **up since 08:49:58, never restarted** (`sparkrun_a2e141223b52793c_d7960e70d961`, four ranks). What is fenced is executing **workloads** on `.30`–`.33` beyond what the operators placed — no research boot, benchmark cell, load or restart — and **loading the production serve** (`curl /v1/chat/completions`, any benchmark client on `:8000`); reading is fine (`AGENTS.md` §Node hygiene, the `.30`–`.33` bullet). Also banned: **removing containers by list expansion on a shared node** (`docker rm -f $(docker ps -aq)`, `\| xargs rm -f`, `prune`), measured on `.30` 08:16/08:18 — remove only ids you created and can name |
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
| 8 | 1M-context prefill is **chunk-bound, not hardware-bound** | **next lever is a larger prefill chunk — and it is a boot-gated experiment, not a guess** | effective **1684/1593/1816/1760/1837** t/s (mean 1738, 1.67× penalty vs c1); per-chunk decay quintiles 3195/1684/1518/1516/1484 (first ten 3428 → last ten 1447); `EP=1`, 384 experts local per rank; prefix-cache hits 0/0/1.6/3.7/8.6 %; **prefill CUDA graphs disabled** (`Breakable CUDA graph is incompatible with DeepSeek-V4`, `prefill.backend='disabled'`) so 1M costs **122 eager chunk launches**; 0.02 EFLOP ⇒ not compute-bound, ~15 GB/s/rank ⇒ not bandwidth-bound | open — owner decides the gated chunk experiment |
| 9 | `DSV41_MXFP8_BACKEND=b12x` is silently overridden | **recorded, not fixed** | it requires `--fp8-gemm-backend flashinfer_cutlass` and the effective value comes out `auto (omitted)` — same class as the launcher's silent drop of a request field | recorded 2026-10-22 |
| 10 | transfer authority on a shared node | **rule** — one owning session per transfer | a session with no ownership of an in-flight body copy killed a foreign `rsync` on `.34` at 04:0x, dropping it **390 GB → 307.2 GB (~83 GB)**; a queued resume over the RoCE rail then completed it (2 streams, 646–751 MB/s, 57 entries byte-identical to `.31`). Verify ownership with `ps -o pid,ppid,lstart,args` before signalling any pid, address rail IPs (`the plane-A rail addresses`/`the plane-B rail addresses`) — **never `.NN`** — while a RoCE copy is on the critical path; correction: the original copy had gone over the **management NIC** (`enP7s7`), not a rail | ack 2026-10-22 |

## Measurements

| arm | node set | cells | verdict | receipt |
|---|---|---|---|---|
| knapcio TP=4 1M (baseline) | 4 nodes | C1 **69.28 ± 5.25** / C2 86.40 / C10 **116.27 ± 6.22**; house 36/37; needle 3/3 to 981,950 — 2026-10-22 fresh boot: C1 **60.20** / C10 **116.86**, house **37/37**, needle **5/5** at ~999k | **the bar**, not a candidate | `recipes/ds4/README.md`; `~/benchmarks/knapcio-tp4-20261022/` (head: REPORT.md, perf-ladder.json, sparkrun_serve.log) |
| Mellum2.1-12B-A2.5B-Q4_K_M (llama.cpp) | 1 (`.34`) | **ten-slot 2026-10-22: C1 110.52 ± 1.77 / C2 154.30 / C5 208.29 ± 5.67 / C10 185.96 ± 2.31**; house @4096 thinking-on **36/37** (needle-1 empty reply, 1 of 3); thinking-off 31/37 | **passes the absolute bars (+59 % each) and house at the bar, FAILS the c5→c10 leg (186.0 vs 208.3, −10.7 %) — a real five-stream peak; the open question (should that forbid a c5 peak when c10 clears the bar by 60 %?) is an owner call** | `~/benchmarks/mellum-c10-20261022/REPORT.md` |
| Spark-X2.6-4B FP8 (`v0.5.22`) | 1 | **40.80 / 77.06 / 146.63 / 217.58** at c1/2/5/10 (5.3×); house **37/37** on the 4096 rerun (first pass 109/111 = 98.2 %, `trick-2` runaway) | **shipped fast tier**; fails the easy-traffic gate on C1. Temperature-0 finding 2026-10-22: greedy 4096 cap **1/5 empty** (`finish=length`, 4096 reasoning tokens) and the same-boot served-defaults control **1 right / 2 wrong / 2 empty** ⇒ the `trick-2` runaway is **model/engine per-request nondeterminism, not the sampler**; temperature 0 is now pinned for this arm | `~/benchmarks/spark-x26-20261022/`, `temp0-4096.json` |
| Spark-X2.6-4B INT8 | 1 (`.35`) | — | **dead at the kernel** — no `int8_scaled_mm` on sm_121; do not re-boot | `.35` serve log |
| Ornith-1.5-122B-NVFP4 (vLLM) | 1 (`.35`) | C1 **27.11 ± 0.38** / C2 39.53 / C5 60.37 / C10 **73.91 ± 0.70**; house **37/37** @4096 thinking-on; TTR 665.9 s, `max_model_len` 262144, KV 2,341,091 tok | **fails C1 (39 % of the bar) and C10 (64 %)**; C1 within 3 % of its own GGUF sibling Q3_K_XL (27.94) ⇒ the ~27 t/s wall is the **8.85 B-active shape on one Spark**, not the engine or the quantisation; tiers separate only under batching | `~/benchmarks/ornith-nvfp4-20261022/` |
| Sage-A1.5 FP8 (SGLang) | 1 (`.34`) | C1 **39.25 ± 0.13** / C5 100.44 / C10 **134.74 ± 2.12**; TTR 338 s, KV 3,309,804 fp8 tok | **fails C1**; mechanism = untuned triton fp8 MoE path after dropping `flashinfer_cutlass` | `~/benchmarks/sage-a15-20261022/` |
| pyannote `speaker-diarization-community-1` (CPU) | 1 (`.34`) | boot **9.56 s**, **DER = JER 2.83 %** on the real two-voice TTS fixture, RTF 0.247; synthetic fixtures collapse to one speaker (labelled adversarial) | **works as the drama-lane speaker instrument** | `recipes/media/README.md:48` |
| drama-3 TTS | 1 (`.34`) | RTF **0.813** @28.7 s, TTFA 0.646 s, seeded byte-identical, unseeded 4.2–7.7 s (σ0.93) | **arm stands** | `~/benchmarks/drama-20261022/` |
| qwen4 W12 vLLM TP=2 | 2 | **42.8 / 51.2 / 40.1** t/s, `max_model_len` 262144, KV 1,757,475 tok (6.70×), 19 min cold | served — cross-runtime column filled | `4570ade` |
| Mellum MTP draft sweep | 1 (`.32`) | **103.38** (n=1) → **90.02 / 75.94 / 66.60 / 51.38 / 47.73** (2/3/4/6/8) | **rejected**, monotone decreasing from n=1 | `~/benchmarks/mellum-mtp-draft-20261022/` |
| llama.cpp fork A/B | same node | fork tree **114.2 / 113.9** vs `a37cc4610` 98–103; fork is 1254 commits older | the ~15 % is the **upstream ref era**, not the build | `ff33ec5` |

## Gate

| suite | plain validate | strict validate | tip | measured at |
|---|---|---|---|---|
| **928 tests OK** (2 skipped) | **not re-run this hour** (last: **56/56**, 0 errors at `4570ade`) | **not re-run this hour** (last: **17/56 fail**, known false positives at `4570ade`) | suite at `eb1a2a4` | suite 2026-10-22 ~14:00 ET (`uv run python -B -m unittest discover -s tests`, 87.8 s); validates 03:49 ET — not fresh |

## Recently landed

| time ET | commit | one clause |
|---|---|---|
| 09:47 | `eb1a2a4` | **never remove containers by list expansion** on a shared node (`docker rm -f $(docker ps -aq)`, `\| xargs`, `prune`) — measured on `.30` 08:16/08:18 |
| 09:47 | `b6e7fd1` | corrected fence wording: `.30`–`.33` are fenced against **workloads**, not against control from `.30` — ssh, `sparkrun` launches and inspection stay normal work |
| 09:40 | `1e3917c` | body-copy attribution corrected: the original copy ran over the **management NIC** (`enP7s7`), never the rails |
| 09:36 | `122a28f` | MiniMax-H3 fit table completed with the **2-node and 4-node** rows |
| 09:34 | `f99f5ef` | the dead **ds4 TP=2 twin A/B** queue is struck from the board — no TODO item, nothing ever measured |
| 09:19 | `4646c34` | `.30`–`.33` marked as the fleet's **inference nodes**, not a measurement surface |
| 09:08 | `c1d4263`+`79b24fc` | Spark-X2.6 **temperature 0** pinned — the `trick-2` runaway survives greedy decoding, so it is model/engine-side, not sampling |
| 08:54 | `96d7347`+`dcc559c` | Ornith-1.5-122B NVFP4 measured and **gated on one node** — fails C1 and C10, landed as a `#49` row |
| 06:30 | `482f2f3`+`7ab424b` | Mellum measured at **ten slots**: absolute bars and house clear, c5→c10 declines (208.29 → 185.96) |
| 06:22 | `4afb211` | **Sage-A1.5 FP8 gate result recorded**: C1 39.25 fails, C10 134.74 passes |
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
