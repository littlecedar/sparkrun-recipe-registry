# Selection ranking (tracked snapshot)

Tracked copy of the git-ignored working draft `.local/SELECTION-RANKING-DRAFT.md`
(2026-10-10 read-only research pass; committed 2026-10-11 per the lane decision
register in `mad-science/TODO.md`, decision #6). The working draft remains the
scratch copy; treat THIS file as the durable record.

Provenance keys used below: `[IDX n]` = `README.md` line n;
`[lane] n` = `recipes/<lane>/README.md` line n; `[ds4-AG] §` =
`attic/ds4/AGENTS.md` section (as cited by the lane README).

Priorities (`mad-science/TODO.md`, order confirmed 2026-10-11): 1. node count ↓,
2. speed ↑, 3. accuracy ↑, 4. memory footprint ↓.

## Delta 2026-10-11 — facts that moved after the snapshot

The tables below are the 2026-10-10 snapshot kept verbatim for provenance.
These rows changed after it was written:

- **ds4** — the untracked `deepseek-v4.1-flash-exl3-engram-tp2-1m-sglang.yaml`
  packaging variant (ds4 row 3 in the table below) was **deleted** 2026-10-11
  (commit `5ec5019`): it was a byte-duplicate of the tensorfold TP=2 recipe,
  which already serves from the combined HF repo. The TP=2 lane is a single
  recipe.
- **qwen3** — `qwen3.8-27b-nvfp4-dspark-sglang.yaml` (qwen3 row 2) is now
  **measured**: 28.5 t/s vs DFlash2's 33.8 on the same decode-triage profile,
  a ~16% loss. Receipts in the recipe comment; the DFlash2 lane stays shipping.
  The "needs measurement" verdict on that row is closed — it measured, and lost.
- **qwen3** — the nospec-control arm (qwen3 row 3) was **retired to
  `attic/qwen3/`** on 2026-10-10 (metrics moved into the lane's `AGENTS.md` §6);
  it is no longer a lane-directory recipe.
- **qwen3** — `qwen3-coder-next-int4-autoround-vllm.yaml` (qwen3 row 4): owner
  decision 2026-10-11 is to **measure it** before the keep/de-ship call.
- **qwen4** — two solo TP=1 arms were built, boot-verified, and W3-battery'd
  2026-10-10 (38/38 each; receipts in the lane docs): the SGLang cookbook route
  (`qwen3.8-flash-next-nvfp4-solo-sglang.yaml`) and the eugr-port vLLM route
  (`qwen3.8-flash-next-nvfp4-solo-vllm-b12x.yaml`). The snapshot's qwen4 row 5
  verdict ("ported, not yet boot-verified") is superseded — both solo arms are
  measured at the battery level but still lack t/s throughput numbers; the
  "highest-leverage missing measurement" note stands for t/s specifically.
- **Selection process** — attic moves, if any, happen per-lane inside each
  lane's quality/selection pass (owner decision 2026-10-11), not as a global
  end-of-session sweep.

## 2026-10-11 session outcomes (selection pass)

Every lane got a decision or a documented blocker on this pass; **no attic move
was warranted anywhere** — the two rules that produced that outcome are "nothing
is dominated on both axes" and "a negative result is a result":

- **qwen3** — coder-next measured at **71.7 t/s C1** (2.1× the DFlash2 arm's
  33.8) and **35/37** on the paired house battery; DFlash2 measured **37/37** at
  33.8. Both stay: DFlash2 is the quality reference, coder-next the speed/coder
  arm. Keep, not de-ship — the owner's measure-before-deciding call is answered.
- **ornith** — the DFlash2 author's 114.2 t/s knob set was decomposed one knob
  per boot. **No knob is distinguishable from the 7.5% same-config boot spread**
  (marlin's two runs straddle both control boots); the clear losers are
  draft-10 (−13%), float32 (−9%) and the author's own full combination (−15%,
  the worst arm). The shipped config stands; write-up in `recipes/ornith/README.md`.
- **glm5** — image blocker closed (`vllm/vllm-openai:glm53-flash` exists,
  digest-pinned), Flash TP4 recipe drafted with the three vLLM boot traps fixed;
  **boot still pending a 4-node window**. EXL3 lane's "build" resolved as a
  clone-and-run (TensorFold `glm-dsa-tp4` branch at `ddfad35`, run via `tfrun.sh`).
- **decision** (new lane) — **two boot-verified recipes**: JEV-9B (vLLM, base + `jev-decision` LoRA
  advertised, processed `top_logprobs` served; no decision-benchmark score yet — the instrument
  targets `/v1/systemone` while JEV serves chat+logprobs) and clef-flash (SGLang, digest-pinned
  `dev-clef`; **official Typed Decisions 70.3% (1406/2000)** at 38.8 ms-class latency). Both keep.
- **explore** (new lane) — **two boot-verified recipes with measured numbers**: Nemotron-3.5-
  Lightning (**77.7 t/s C1**, DSpark acceptance length 3.67 / 88.9%, house battery 33/37) and
  Ling-3.0-flash INT4 (**45.5 t/s C1**, DSPARK engaged at accept len 2.73, house battery **37/37**;
  the third-party ~83 t/s was not reproduced — lower acceptance explains it). Both keep; Ling is
  the quality/speed balance, Nemotron the speed arm.
- **Untouched this pass** — embed, rerank, ifm, ds4 (ds4's own A/B work predates
  this pass and its receipts live in the lane docs).

## 2026-10-14 delta — qwen4 cut to two (owner decision)

The lane was cut from six shipped recipes to **two**: the fastest TP=1 and the fastest TP=2, both on
the `local-inference-lab` export. Five were measured in one window on `.34/.35` with
`benchmarking/decode-triage.yaml` (d0/d8192, C=1, 5 runs; receipts `~/benchmarks/q4-*-triage_1014_*`);
the sixth (`…-solo-sglang`) failed readiness there and was re-measured later the same day on `.34`
(`~/benchmarks/q4-solo-sglang2-triage_1014.*`).

| arm | nodes | C1 d=0 / d=8192 (tok/s) | outcome |
|---|---|---|---|
| `…-labquant-sglang` | 2 | 41.32 / 38.58 (pre-pin); 40.32 / 43.29 (re-pinned `6c01ac37`) | **kept — TP=2** |
| `…-labquant-longctx-sglang` | 2 | 42.47 / 39.04 | attic (1M quality unverified; 1M droppable) |
| `…-labquant-highcon-sglang` | 2 | 40.10 / 41.92 | attic (C1-tied; larger pool) |
| `…-nvfp4-sglang` (RadixArk) | 2 | 36.84 / 34.44 | attic (~12% slower) |
| `…-solo-vllm-b12x` | 1 | 33.92 / 34.35 | **kept — TP=1** |
| `…-solo-sglang` | 1 | 19.82 ± 2.06 / 20.97 ± 1.02 | attic (~42% below the TP=1 pick; measured after a readiness fix, `bench_253dd84c9a78`) |

This resolves — for qwen4 — the earlier "no attic move was warranted" call under the frozen ranking:
the frozen table's ranks 1–4 were four arms of one checkpoint, three of them C1-tied, and rank 5 (the
solo vLLM arm) was unmeasured. With measurements, the three TP=2 arms are one arm (keep the base) and
the TP=1 arm wins on node count despite ~18% less C1 throughput. The RadixArk checkpoint now has no
shipped recipe and its node cache is cleared (owner cache-hygiene policy).

**Sixth arm closed 2026-10-14.** The one unmeasured arm (`…-solo-sglang`) was booted and measured in a
later window: **19.82 ± 2.06 t/s d=0 / 20.97 ± 1.02 d=8192** (`bench_253dd84c9a78`) — a clear loser
to the shipped TP=1 arm (33.92 ± 1.73), so **the TP=1 pick stands**. The earlier "did not reach
readiness" verdict is superseded: it was a port timeout (the file-backed PLE load opened the port at
TTR 3477 s, past sparkrun's default 1800 s; the arm now carries `readiness.port_timeout_s: 3600`).
The measurement re-populated the RadixArk snapshot on `.34` (sparkrun distributed the 126 GiB), where
it briefly contradicts the "node cache is cleared" note above — `.30` still holds the canonical copy.

---

# SELECTION RANKING DRAFT (Phase 5 input)

_Draft prepared 2026-10-10 by a read-only research pass. NOT tracked; do not git add._
_Priorities (mad-science/TODO.md, in order): 1. node count ↓, 2. speed ↑, 3. accuracy ↑, 4. memory footprint ↓._

Provenance keys: `[IDX n]` = README.md line n; `[lane] n` = recipes/<lane>/README.md line n; `[ds4-AG] §` = attic/ds4/AGENTS.md section (as cited by README).
Shipped surface = `git ls-files 'recipes/*/*.yaml'` (18 files; ifm excluded per assignment scope). Two README-documented arms are currently **untracked WIP** (`recipes/qwen3/qwen3.8-27b-nvfp4-nospec-control-sglang.yaml`, `recipes/ds4/deepseek-v4.1-flash-exl3-engram-tp2-1m-sglang.yaml` — both show `??` in git status 2026-10-10); they are ranked below with a note.

---

## ds4 — DeepSeek V4.1-Flash

| Rank | Recipe | Nodes | Speed (measured) | Accuracy (measured) | Mem/size | Verdict |
|---|---|---|---|---|---|---|
| 1 | `deepseek-v4.1-flash-tensorfold-tp2-1m-sglang` | **2** [IDX 14] | **73.0 t/s C1** (our boot-verified number) [IDX 14, ds4:324]; upstream card: 101 code / 62 prose / 142 structured, 112 t/s @4 streams [ds4:323 — card numbers, different harness] | 17/18 hard tier; 11-benchmark paired battery, no separable gap vs official [ds4:329-334, 459-473] | EXL3 2.9bpw ~197 GB [ds4:317]; Mem — in index [IDX 14] | **Winner on priorities 1+2** (2 nodes, faster C1, measured quality parity). Contested only vs knapcio on: 4-stream concurrency cap (shared 1M KV pool, `--parallel 4` hard cap, ds4:436-447), text-only shipping (ds4:336-343), vision not shipped. |
| 2 | `deepseek-v4.1-flash-knapcio-tp4-1m-sglang` | **4** [IDX 13] | 46.5 C1 / 106 C4 / 133 C8 / 193 C16 t/s short-prompt [IDX 13, ds4:17,98]; standardized profile 43.6/91.3/99.4/102.1 [ds4:99] | 17/18 hard tier (same single base-model failure as EXL3) [ds4:106-112] | 510 GB/node, 0.80 [IDX 13] | **Contested, not a loser**: best aggregate at C16 (193 t/s) and full vision support, but 4 nodes puts it last on priority 1. |
| — | `deepseek-v4.1-flash-exl3-engram-tp2-1m-sglang` (untracked WIP) | 2 [ds4:372-374] | — same engine/lane as tensorfold; no separately recorded figures in README | inherits EXL3 quality record [ds4:451-473] | same TP=2 lane | **Packaging variant** of rank 1 (one-repo distribution, no engram-fetch mod) — not an independent arm; needs no new measurement. |

Retired: vLLM/EXL3 5-recipe lane in `attic/ds4/` [ds4:485-492] — excluded.

## ornith

| Rank | Recipe | Nodes | Speed (measured) | Accuracy | Mem/size | Verdict |
|---|---|---|---|---|---|---|
| 1 | `ornith-1.5-35b-a3b-nvfp4-dflash2-sglang` | **1** [IDX 21, lane 10] | **~100 t/s C1** [IDX 21, lane 10, 39-40 — but lane says "not re-measured on our nodes with a pinned harness", lane 69-71]. Corroboration only (draft card, different config): AR 79.3, DFlash2 114.2 C1, 236.5 C8 [lane 63-65] | — none recorded | 45 GB, 0.85 [IDX 21] | **Winner, needs measurement** (pinned-harness re-run). Cheaper node count + faster C1 than 397B on every recorded figure. |
| 2 | `littlecedar-ornith-1.5-397b-nvfp4-mtp-graft-vllm` | **4** [IDX 20, lane 11] | **41.86 t/s C1** — model-card number from a Spark-Arena 4×GB10 run, adopted as index C1 [IDX 20, lane 80-88]; tied to a floating `:latest` container tag [lane 85-88, 120-123] | — none recorded | 235 GB/node, 0.80 [IDX 20, lane 76-78] | **Contested**: flagship scale but loses priorities 1 and 2 outright; its number is a card figure, not ours. |

## qwen3 (27B, single-Spark TP=1 all arms)

| Rank | Recipe | Nodes | Speed (measured) | Accuracy | Mem/size | Verdict |
|---|---|---|---|---|---|---|
| 1 | `qwen3.8-27b-nvfp4-dflash2-sglang` | **1** [lane 6] | **CONFLICT, surface both:** index C1 = 50 [IDX 41]; lane README = **33.8 t/s** d=0 c=1 [lane 17, 31]. The lane's own worklog reconciles them as real measurements of different windows — do not silently pick one. | — no battery recorded | 21 GB, 0.85 [IDX 41] | **Winner pending conflict resolution**; only serving arm. |
| 2 | `qwen3.8-27b-nvfp4-dspark-sglang` (experimental) | **1** | **— unmeasured; never booted** [IDX 42, lane 19]; card numbers are GB300/H200, not SM121 [lane 19] | — | 21 GB, 0.85 [IDX 42] | **Needs measurement** (A/B vs dflash2, block 8). |
| 3 | `qwen3.8-27b-nvfp4-nospec-control-sglang` (untracked WIP) | **1** | 12.6 t/s control [lane 18] | — (measurement-only 🧪) | 21 GB | **Clear loser as a serving arm** ("control only — not for serving", lane 18); retained as the A/B baseline. |
| — | `qwen3-coder-next-int4-autoround-vllm.yaml` (tracked, vLLM) | 1 (per lane convention, lane 6) | **— no measured figure anywhere in the lane docs** (no index row [IDX 37-42]; absent from lane README table [lane 15-21]; NOTES.md has no coder mention) | — | — | **Needs measurement** — or de-ship; it is the only tracked arm with zero recorded numbers and no doc row. |

## qwen4 (Qwen3.8-Flash-Next)

| Rank | Recipe | Nodes | Speed (measured) | Accuracy | Mem/size | Verdict |
|---|---|---|---|---|---|---|
| 1 | `qwen3.8-flash-next-nvfp4-labquant-highcon-sglang` | **2** [IDX 50] | 44 C1 [IDX 50]; aggregate peak ~88 tok/s at k≈16–24 [IDX 50, lane 31, 53-55: 88.35/87.78 vs 78.02 across four boots] | **— no eval exists** (lane: "no accuracy evaluation exists for it", [lane 166-167, IDX 62-65]); text-only (vision tower dropped by required mod) | 106 GB, 0.80 [IDX 50] | **Contested winner**: fastest measured aggregate; blocked on a quality eval to count as selection-winner. |
| 2 | `qwen3.8-flash-next-nvfp4-labquant-sglang` (balanced base/control) | **2** [IDX 49] | 44 C1 [IDX 49]; aggregate peak **91.38 @ k=16** [lane 152] | — none [lane 166-167] | 106 GB, 0.80 [IDX 49] | **Contested** vs #1 (same checkpoint, one-knob difference; 91.38 is at k=16 where highcon targets k≈16–24). |
| 3 | `qwen3.8-flash-next-nvfp4-sglang` (RadixArk) | **2** [IDX 48] | 38 C1 [IDX 48, lane 151: 37.973]; aggregate peak **86.86 @ k=16**, ~54 @ k=24 [lane 152-153]; batching gain +119% [lane 154] | **quality reference** (vision intact) [IDX 64-65, lane 11, 167] | 135 GB, 0.80 [IDX 48] | **Contested**: slower on every measured cell but the ONLY arm with a quality standing — keep as quality reference until a labquant eval lands. |
| 4 | `qwen3.8-flash-next-nvfp4-labquant-longctx-sglang` | **2** [IDX 51] | 44 C1 [IDX 51] (same checkpoint/chain as labquant base) | **quality-unverified above ~262k**; neighbour lane needle exact at 240k, failed at 300k [IDX 58, lane 69-76] | 106 GB, 0.80 [IDX 51] | **Contested, regime-specific**: not a general selection candidate; ships the 1M route gated by a needle test that has not passed. |
| 5 | `qwen3.8-flash-next-nvfp4-solo-vllm-b12x` (TP=1) | **1** [IDX 52] | **— unmeasured; "ported, not yet boot-verified"** [IDX 52, lane 105-106] | — | 135 GB (TP=2 footprint figure; the recipe is TP=1 — re-measure) [IDX 52, lane 99] | **Needs measurement**: if it boots near the TP=2 speed it wins priority 1 outright (1 node); every number currently unmeasured. |

## embed

| Rank | Recipe | Nodes | Speed | Accuracy | Mem/size | Verdict |
|---|---|---|---|---|---|---|
| — | `qwen3-vl-embedding-2b-vllm-b12x` | 1 [IDX 27] | — [IDX 27, embed 11] | — | 0.25, size — [IDX 27] | **Needs measurement** (and they are not ranked against each other: 2B = colocatable low-cost tier, 8B = quality tier, embed 18-23). |
| — | `qwen3-vl-embedding-8b-awq-4bit-vllm-b12x` | 1 [IDX 28] | — [IDX 28, embed 12] | — (card: "quality tier", embed 23) | 0.30, size — [IDX 28] | **Needs measurement**; role-separated, not head-to-head. |

## rerank

| Rank | Recipe | Nodes | Speed | Accuracy | Mem/size | Verdict |
|---|---|---|---|---|---|---|
| — | `qwen3-vl-reranker-2b-vllm-b12x` | 1 [IDX 34] | — [IDX 34, rerank 11] | — | 0.30, size — [IDX 34] | **Needs measurement**; colocates with 2B encoder (0.25+0.30=0.55, rerank 18-22). |
| — | `qwen3-vl-reranker-8b-vllm-b12x` | 1 [IDX 35] | — [IDX 35, rerank 12] | — ("quality-tier", card label) | 0.30, size — [IDX 35] | **Needs measurement**; note index flags differ (8B lacks 🚀 — deliberately not fast, flags set in recipe metadata). |

---

## Cross-lane summary for the Phase 5 live decision

- **Only contest that follows the priorities and has full measured data: ds4** — tensorfold (2 nodes) vs knapcio (4 nodes), measured quality parity. Default pick: tensorfold, unless C16+ aggregate or shipped vision is required.
- **Highest-leverage missing measurement: qwen4 solo TP=1** (`…-solo-vllm-b12x`) — one node would beat every 2-node qwen4 arm on priority 1; currently zero numbers.
- **Fastest recorded arm overall: ornith 35B dflash2 (~100 C1, 1 node)** but the lane itself says it is not re-measured with a pinned harness — treat 100 as provisional.
- **Known number conflict (do not resolve silently): qwen3 dflash2 C1 = 50 [IDX 41] vs 33.8 [qwen3:17,31].**
- **All eight embed/rerank arms have no measured figure at all** (t/s, size, accuracy) — em dash everywhere; anything Phase 5 does with them starts with a bench.
- **Card numbers, labeled as such and not ranked on:** ornith 397B 41.86 (lane 80-88), ornith DFlash2 draft 114.2/236.5 (lane 63-65), tensorfold upstream 101/62/142/112 (ds4:323), dspark GB300/H200 (qwen3:19).
