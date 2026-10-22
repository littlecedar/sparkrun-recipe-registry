# Board — 2026-10-22 02:50 ET

Eight streams ran in parallel. The gate is **894 tests OK**, CI is green, and both long blocks are stopped on an external limit rather than on a verdict.

## Now

| where | what | since | state |
|---|---|---|---|
| `.30`–`.33` | TP=4 block — W6 → W12 → ds4 TP=4 → four-node suite, resumable | 01:52 | W6 **failed** on all four ranks (`modelopt_quant.py:2624`, gated-activation MoE padding) — an engine limit, not memory (fit was 21 GiB/rank); knapcio TP=4 suite **closed**: ARC 93.5 % / GSM8K 97.5 % in 427.6 s; W12 waits on staging at 2–5 MiB/s, attribution in flight |
| `.34` | llama.cpp regression + Mellum MTP A/B | 01:22 | **the 14× collapse is build `9df0b73c7`, not the ref**: flint ref `a37cc4610` decodes 101.4/102.7 t/s, `FA_ALL_QUANTS` adds nothing (97.1/101.7), the fork does 120/122, the crippled build 8.3–8.7; clean-rebuild test and the 15 % attribution in flight |
| `.35` | SGLang `v0.5.22` re-pin | 01:34 | arms A and B **kept** (A: TTR 238 s, pool 1,133,804, house 37/37, needle 3/3, ladder n=3 C1 94.3 vs band 100.8–101.8; B: TTR 251 s, pool 1,531,959, house 37/37); arms C–F in flight |
| repo/CI | CI gate, nightly pin sweep, weekly engine report | 01:38 | **green** on three re-dispatched runs; drift reads on the run summary plus the 90-day `refresh-sweep` artifact, and the `pin-drift` issue stays SKIPPED while the tracker is disabled |
| probes | five explorer probes and one arm authoring | 02:14 | humanizer Q4_K_M **NO_SHIP** (falsifier: 2 genuine fact errors vs the baseline's 1), one Q6_K A/B boot authorized; Spark-X2.6 arm authored — `spark2_5` is already in the pinned SGLang, so no image work |

## Attention

| what | why it matters | where it is tracked |
|---|---|---|
| ds4 EXL3 vLLM image `9df0b73c7` decodes 8.4 t/s where the same bytes do 101–103 | any arm booted from it under-measures ~12×; do not reuse that image | `attic/explore/AGENTS.md` §measured; the arms' `container:` |
| W6 cannot boot at TP=4 on this build, on every rank | a re-run without an engine fix is wasted quartet time | `attic/qwen4/arms/qwen3.8-flash-next-labquant-tp4-sglang.yaml`; `recipes/qwen4/README.md` |
| Quartet TP=4 production serve stays stopped (owner; stopped 00:38:39 ET) | `.30`–`.33` are measurement-only now | `mad-science/TODO.md` TP=4 items |
| Timestral weights are Modified MIT at a **$20M/month** revenue cap; indra-ocr weights are a modified OpenRAIL whose share-alike reaches the *output* | both need a top-of-file banner before they can ship — an owner decision, not a footnote | `mad-science/TODO.md` explore items |
| vLLM `v0.32.0` puts thinking at `message.reasoning` and reads `reasoning_tokens` as 0 | a harness reading `reasoning_content` reports a false empty reply | `recipes/explore/README.md`; TODO explore item |

## Gate

| suite | plain validate | strict validate | tip | measured at |
|---|---|---|---|---|
| **894 tests OK** (2 skipped) | **52/52**, 0 errors | **17/52 fail** (known false positives) | `de841f8` | suite 02:50 ET, plain and strict 02:50 ET — tracked bytes at `de841f8`; tree dirty: 11 paths (6 recipes), none in the strict set and all six clean at the tip's bytes |

## Recently landed

| time ET | commit | one clause |
|---|---|---|
| 02:37 | `05283d0` + `0ba9515` | humanizer quant round recorded as a measured non-ship, its instrument cited by name |
| 02:36 | `43d94a1` | the 14× decode collapse is the `9df0b73c7` build, not the ref |
| 02:35 | `9b78221` | Timestral reframed as a CPU arm with a pre-registered CRPS instrument |
| 02:31 | `93afaea` | indra-ocr registered: a CPU ONNX serve with an output share-alike |
| 02:30 | `1b28975` | drama-3 registered: licence-gated TTS, no bf16 route, no pinned engine |
| 02:28 | `a61033d` | MOSS-Image pair registered, with why no quant is needed |
| 01:38 | `d8c1339` | CI gate, nightly pin sweep, weekly llama.cpp engine report |

## Pointers

`mad-science/TODO.md` = the queue (work items and `# DECISIONS`). `mad-science/SESSION-RECORD.md` = dated history. `recipes/<lane>/README.md` = per-arm evidence.
