# Board — 2026-10-22 03:40 ET (census 03:36, gate 03:39)

The night's verdicts are in: the SGLang `v0.5.22` bump closed with six arms held, humanizer-12B ships at Q6_K, Spark-X2.6's FP8 tier is measured-rejected despite being 2× faster, and the TP=4 block is booting. Gate **899 tests OK** (2 skipped), plain **56/56**, strict **17/56** — the same seventeen known false positives.

## Now

| where | what | since | state |
|---|---|---|---|
| `.30`+`.31`+`.32`+`.33` | `tp4-queue` — W6 on `v0.5.22`, the block's first TP=4 boot | 03:35 | **loading weights, live**: task `sparkrun_08acf79cd757a666_7afff0589a33`, `node_0`–`node_3` on `.30`/`.31`/`.32`/`.33`, four containers up since **03:35:35 ET** on `lmsysorg/sglang:v0.5.22-cu130`; client live on the head (`sparkrun run .scratch/w6-v0522/tp4-v0522.yaml -H .NN,.31,.32,.33 --transfer-mode local --no-ready-wait`, pid 97943); at **03:40 ET** the serve log on `.30` reads **`Multi-thread loading shards: 8/41` at ~13 s/shard** (~7.5 min of load left) and no endpoint yet. The set this launch chose is `.30`–`.33` (`.34` and `.35` at 0 containers) because the consecutive-node rule is lifted, so **every receipt must name the node set it used** |

## Attention

| what | why it matters | where it is tracked |
|---|---|---|
| A llama.cpp **ref below `a37cc4610`** (e.g. `9df0b73c7`) decodes **7.9–8.4 t/s** where `a37cc4610` does 98–103 — ref-level, reproduced from a clean rebuild, fixed upstream in `a37cc4610` (2026-10-22) | never pin below it; the fork's speed is simply an older ref (`b2e5e9b`, 1254 commits), not its patches | `attic/explore/AGENTS.md` §"The ref floor moved"; `mad-science/LLAMACPP-GGUF.md` §1 |
| `sparkrun run @littlecedar/<name>` resolves the **published registry**, not the worktree (2026-10-22: a bump boot served `v0.5.21` while the file said `v0.5.22`) | pass the recipe **file path** for any bump or candidate boot | `AGENTS.md` §serving traps; `recipes/ornith/README.md` |
| `docker pull repo:tag@sha256:…` stores the image **untagged**, so a peer's `image prune` deletes the very build just pulled (2026-10-22) | re-tag at once, and guard the pin before every boot: `grep -q e3a4f060 <recipe>` | `AGENTS.md`; `recipes/ornith/README.md` |
| `readiness.inference: false` makes "HTTP-ready" satisfiable by a **dead serve or a foreign listener** (2026-10-22: drama reported HTTP-ready 14.7 s while its serve had died at `sock.bind`) | assert `/v1/models` names the model; a bare port check is not a cell | `mad-science/TODO.md` drama item |
| **Mellum MTP is rejected** on the shipped engine: 108.4/109.9 t/s against the pre-registered 114 bar, acceptance 0.80, mean len 1.80 (measured 03:18) | the earlier "+44 %" was a slow-baseline artefact and must not be quoted | `recipes/explore/README.md`; `attic/explore/AGENTS.md` |
| Two licence banners owed before either arm ships (registered 02:28–02:35): Timestral **Modified MIT at a $20M/month revenue cap**; indra-ocr **modified OpenRAIL whose share-alike reaches the output** | owner decision, not a footnote — and the banner must not conflate Apache-2.0 code with restricted weights | `mad-science/TODO.md` explore items |

## Gate

| suite | plain validate | strict validate | tip | measured at |
|---|---|---|---|---|
| **899 tests OK** (2 skipped) | **56/56**, 0 errors | **17/56 fail** (known false positives) | `146b13c` | suite 03:39 ET, plain and strict 03:39 ET — tree clean, 0 dirty tracked paths |

## Recently landed

| time ET | commit | one clause |
|---|---|---|
| 03:36 | `146b13c` | **FP8 rejected**: 40.80 / 77.06 / 146.63 / 217.58 t/s (+100/+66/+48/+39 %) but house 109/111 = 98.2 %, `trick-2` looping to 4096 reasoning tokens with empty content — and `max_num_seqs: 96` is inert (all deltas inside one σ, pool 743,780), so 32 stays |
| 03:35 | `767a0f8` | the drama-3 row points at the baked `stage_init_timeout: 1800` instead of an override |
| 03:33 | `9f12054` | drama-3 **parked**: 37.69 GiB loaded in 242.84 s, then killed 2 s after `torch.compile` by vllm-omni's default 300 s stage deadline; recipe ships as a draft |
| 03:22 | `ff33ec5` | the ~15 % is the **upstream ref era**, not the fork's build: the fork's tree through our Dockerfile measures 114.2/113.9 and is 1254 commits older |
| 03:11 | `cc05822` | W12 loads through safetensors — instanttensor cannot shard at TP=2 on the pinned image |
| 03:10 | `6b82a39` + `6a1129d` | the spark-x2.6 control carries its measured outcome; the battery gains `--thinking on\|off` |

## Pointers

`mad-science/TODO.md` = the queue (work items and `# DECISIONS`). `mad-science/SESSION-RECORD.md` = dated history. `recipes/<lane>/README.md` = per-arm evidence.
