# Board — 2026-10-22 03:45 ET census, 03:49 ET gate

Four verdicts landed in the last twenty minutes: TP=4 is **closed as a checkpoint limit** on this NVFP4 export, W12 **served** for the first time, the SGLang `v0.5.22` bump closed with six arms held, and Spark-X2.6's FP8 tier is measured-rejected despite being 2× faster. Gate **899 tests OK** (2 skipped), plain **56/56**, strict **17/56** — the same seventeen known false positives.

## Now

| where | what | since | state |
|---|---|---|---|
| `.34` | `drama-probe` re-boot — drama-3 on the resident vLLM-Omni nightly | 03:41 | **live, loading weights**: task `c8829c3570d86002_8ed3ce77d78f`, container up since 03:41:36 ET; the serve log names `models--fishaudio--drama-3` and read **`Loading safetensors checkpoint shards: 7/8`** at 03:45 ET; this boot carries the recipe's own `stage_init_timeout: 1800`, the knob the 03:33 attempt died on |
| `.35` | `sparkx-probe` — Spark-X2.6 **FP8** re-test | 03:41 | **live and serving**: task `sparkrun_9c8e0fffc3cbe638_64af2f7668b6` on `lmsysorg/sglang:v0.5.22-cu130`, container up since 03:41:56 ET; the log names `models--XHToken--Spark-X2.6-4B-FP8` and its last line at 03:45:41 is a `200 OK` prefill batch with an empty queue |
| `.30`–`.33` | `ds4` TP=2 twin A/B — owner assignment | 03:45 | **not started**: all four nodes at **0 containers** in the 03:45 census, so nothing is measuring yet |

## Attention

| what | why it matters | where it is tracked |
|---|---|---|
| **TP=4 is closed for the qwen4 labquant NVFP4 export** — the gated-activation padding assertion fires on **all four ranks** on `v0.5.22` (`modelopt_quant.py:2942`) exactly as on `v0.5.20` (`:2624`), after 41/41 shards load on every rank (2026-10-22) | it is the **checkpoint**, not the build and not the arm — **do not re-try another nightly** expecting a different answer | `mad-science/TODO.md` TP=4 item; `attic/qwen4/AGENTS.md` |
| A llama.cpp **ref below `a37cc4610`** (e.g. `9df0b73c7`) decodes **7.9–8.4 t/s** where `a37cc4610` does 98–103 — ref-level, reproduced from a clean rebuild, fixed upstream in `a37cc4610` (2026-10-22) | never pin below it; the fork's speed is simply an older ref (`b2e5e9b`, 1254 commits), not its patches | `attic/explore/AGENTS.md` §"The ref floor moved"; `mad-science/LLAMACPP-GGUF.md` §1 |
| `sparkrun run @littlecedar/<name>` resolves the **published registry**, not the worktree (2026-10-22: a bump boot served `v0.5.21` while the file said `v0.5.22`) | pass the recipe **file path** for any bump or candidate boot | `AGENTS.md` §serving traps; `recipes/ornith/README.md` |
| `docker pull repo:tag@sha256:…` stores the image **untagged**, so a peer's `image prune` deletes the very build just pulled (2026-10-22) | re-tag at once, and guard the pin before every boot: `grep -q e3a4f060 <recipe>` | `AGENTS.md`; `recipes/ornith/README.md` |
| `readiness.inference: false` makes "HTTP-ready" satisfiable by a **dead serve or a foreign listener** (2026-10-22: drama reported HTTP-ready 14.7 s while its serve had died at `sock.bind`) | assert `/v1/models` names the model; a bare port check is not a cell | `mad-science/TODO.md` drama item |
| **Mellum MTP is rejected** on the shipped engine: 108.4/109.9 t/s against the pre-registered 114 bar, acceptance 0.80, mean len 1.80 (measured 03:18) | the earlier "+44 %" was a slow-baseline artefact and must not be quoted | `recipes/explore/README.md`; `attic/explore/AGENTS.md` |
| Two licence banners owed before either arm ships (registered 02:28–02:35): Timestral **Modified MIT at a $20M/month revenue cap**; indra-ocr **modified OpenRAIL whose share-alike reaches the output** | owner decision, not a footnote — and the banner must not conflate Apache-2.0 code with restricted weights | `mad-science/TODO.md` explore items |

## Gate

| suite | plain validate | strict validate | tip | measured at |
|---|---|---|---|---|
| **899 tests OK** (2 skipped) | **56/56**, 0 errors | **17/56 fail** (known false positives) | `4570ade` | suite 03:49 ET, plain and strict 03:49 ET — tree dirty: 1 path (the shipped W12 arm, below) |

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
