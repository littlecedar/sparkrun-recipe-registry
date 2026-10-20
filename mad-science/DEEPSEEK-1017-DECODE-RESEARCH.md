# DeepSeek-V4.1-Flash-1017 — decode at TP=2 vs TP=4, and the TP=1 byte wall

**Status:** research note, 2026-10-20. **No boot was run for this note**, no recipe changed, and
nothing on the cluster was written — the head and one test-pair node were read. Answers two
questions for the `ds4` and `cybersec` lanes: what the registry's own receipts say about decode
throughput at TP=2 and TP=4 for the 2026-10-17 `-1017` refresh, and whether any 1017-class body can
be served at TP=1 on one 128 GB node.

## Scope

In: every **1017-class serve this registry has receipted**, in `recipes/ds4/` (SGLang TP=4 over the
official MXFP4/F8 base; TensorFold TP=2 over the EXL3 2.9 bpw conversion), `recipes/cybersec/` (the
TP=2 abliterated graft on the same EXL3 body), and the prior research in [`../attic/ds4/`](../attic/ds4/)
and [`../attic/cybersec/`](../attic/cybersec/). Out: the pre-1017 V4.1 base and every non-DeepSeek
arm, except where a receipt measured both in one interleaved window (that comparison is named).

Two lane-level facts bound the whole note. First, the TP=4 and TP=2 arms differ in **engine, quant,
and topology at once** — SGLang over MXFP4/F8 at TP=4 against TensorFold over EXL3 2.9 bpw at TP=2 —
so every TP=2-vs-TP=4 ratio below is a lane-vs-lane comparison at matched concurrency, not a
controlled TP sweep; the registry has never booted one engine on both topologies. Second, the
quartet is a **production** serve (`mad-science/TODO.md`, owner policy 2026-10-19), so no TP=4 arm
can be re-taken without an owner-scheduled window.

## Method and sources

1. **Read the lane docs and the receipts they cite**, then re-derived every decode cell from the
   benchmark output file rather than from the prose: `~/benchmarks/{tp4-20261018,
   ds4-v24-line-20261018, ds4-knapcio-1017-20261018, ds4-1017-ab-interleaved-20261018,
   ds4-1017-envtoggles-20261018, ds4-1017-20261017, ds4-tp2-ladder-20261018,
   cybersec-arm5-ladder-20261019}/` on the head. Cells are `llama-benchy` records with
   `is_context_prefill_phase: false` — the decode phase only. `±` is the **sample sd (ddof 1)** of the
   per-run values, recomputed here; a receipt JSON's own `tg_throughput.std` is the population sd,
   0.894× that at n=5, and some lane READMEs quote the JSON field.
2. **Read the lane YAMLs and the launcher mods** for the levers each arm actually changes
   (`recipes/ds4/*.yaml`, `recipes/ds4/mods/dsv41-sglang-overlay/launcher.py`,
   `mods/tensorfold-dsv41-launcher/launcher.py`).
3. **Measured body sizes** two ways: the Hub API's per-file byte sums
   (`/api/models/<id>?blobs=true`), and, for the EXL3 body, the checkpoint's own
   `model.safetensors.index.json` `total_size` read in a node cache. Anatomy numbers (the two Engram
   tensors, the shard dtype census) come from `../attic/ds4/AGENTS.md` §2.2, which recorded them from
   tensor shapes by HTTP Range reads.
4. **`mad-science/REPORT.md` does not exist** in this tree (`git ls-files` has no such path). The
   per-window `REPORT.md` files inside the receipt directories stand in, and this note cites those.

## Q1 — measured decode, per arm

All cells are `benchmarking/concurrency-ladder.yaml` (depth 0, 2048-token prompts, 128-token
replies, prefix caching, 5 runs/cell) unless the row says otherwise; `benchmarking/ds4-sglang-depth0-ladder.yaml`
is the C1/C4/C8/C16 shape (3 runs/cell) and is **not** comparable cell-for-cell to C2/C5/C10.

### Measured

| # | arm | body / quant | engine, TP | lever this row changes | C1 | C2 | C5 | C10 | provenance |
|--:|:--|:--|:--|:--|--:|--:|--:|--:|:--|
| 1 | knapcio, v2.3 line, boot A | official 1017, MXFP4/F8, 510.31 GB | SGLang, TP=4 EP=1, RoCEnante | the shipped v2.3 serve line; DSpark k=5 verify-all; prefill-decode interval **off**; pool pin 9.4M → engine profiled **9,277,952** | 69.65 ± 11.51 | 89.89 ± 3.57 | 113.44 ± 6.84 | 115.36 ± 6.62 | `~/benchmarks/tp4-20261018/knapcio-ladder.json`, `bench_21011c740763` |
| 2 | knapcio, v2.3 line, boot C (suite boot) | same | same | same, second boot of the window | 69.28 ± 5.25 | 86.40 ± 3.59 | 108.78 ± 14.19 | 116.27 ± 6.22 | `…/tp4-20261018/knapcio-ladder-suiteboot.json`, same bench id |
| 3 | knapcio, extra C1 bench | same | same | C1 only, n=10 | 66.40 ± 4.31 | — | — | — | `…/tp4-20261018/knapcio-c1-extra.json`, `bench_650090dd1f38` |
| 4 | **C1 pool over rows 1–3 plus the γ arm** | same | same | four same-config C1 takes pooled | **67.18 ± 6.97** (n=25, range 56.4–87.9, CV 10.4 %) | — | — | — | pooled from the four per-run sets; re-derived here, matches `recipes/ds4/README.md` |
| 5 | knapcio, γ=5 pair arm | same | same | `defaults.dspark_block_size: 5` passed explicitly (the knob's end-to-end proof) | 64.16 ± 7.97 | — | — | — | `…/tp4-20261018/gamma-p1-g5.json`, `bench_773e515ed20e` |
| 6 | knapcio, **v2.4 line, interval ON** | same | same | `--prefill-decode-interval 2`, `--swa-prefix-tails 128`, pin 7.5M | 60.22 ± 13.00 | 73.16 ± 4.96 | 95.10 ± 14.66 | 101.49 ± 10.45 | `~/benchmarks/ds4-v24-line-20261018/ladder.json` |
| 7 | knapcio, **v2.4 line, interval OFF** | same | same | interval off, pin 7.5M — **the shipped line** | 51.84 ± 17.68 | 88.35 ± 6.33 | **131.83 ± 8.50** | 123.49 ± 8.45 | `…/ds4-v24-line-20261018/pd-off/ladder.json`, `bench_42a355dda245` |
| 8 | knapcio, v2.4 line, interval OFF, re-pin | same | same | interval off, pin **6.85M** (97.9 % of the profiled 6,993,408) | 53.40 ± 21.35 | 82.02 ± 10.14 | 130.97 ± 10.50 | 119.79 ± 8.09 | `…/ds4-v24-line-20261018/confirm/ladder.json`, same bench id |
| 9 | knapcio, depth-0 shape | same | same | different **profile** (C1/C4/C8/C16, 3 runs/cell), after two cold prefill probes | 80.97 ± 4.29 | C4 118.87 ± 13.92 | C8 107.53 ± 9.64 | C16 115.90 ± 3.82 | `…/ds4-knapcio-1017-20261018/arm-1017/ladder.json`, `bench_147c4e4cadab` |
| 10 | **TensorFold TP=2, stock** | `LibertAIDAI/…-1017-EXL3-2.9bpw`, 210.72 GB, Engram ~189 GiB on NVMe | TensorFold 0.6.x, TP=2, `--parallel 4`, `--context 1048576`, vision on | the shipped TP=2 line; DSpark k=5 in-checkpoint drafts; KV grant `reserved 104.00 GiB` | **68.63 ± 3.79** | 48.05 ± 2.46 | 44.56 ± 1.75 | 42.07 ± 3.96 | `~/benchmarks/ds4-tp2-ladder-20261018/tp2-ladder.json`, `bench_2d5f1236b08d` |
| 11 | TensorFold TP=2, stock, depth-0 shape | same | same | interleaved A/B arm A, 3 boots, 5 runs/cell (means of the 3 boots) | 66.37 | C4 47.83 | C8 44.80 | C16 48.39 | `…/ds4-1017-ab-interleaved-20261018/ab-A{1,2,3}.json`, `bench_8c72b1fe3644` |
| 12 | **TensorFold TP=2, cybersec graft** | same EXL3 body + 682 MB `attn.wo_b` sidecar, Engram on | TensorFold, TP=2, same launcher | the graft (104 tensors, layers 10–35 `attn.wo_b`) | 67.02 ± 3.57 | 52.95 ± 1.67 | 47.75 ± 0.60 | 46.78 ± 0.37 | `~/benchmarks/cybersec-arm5-ladder-20261019/ladder.json`, `bench_484eb77839b4` |
| 13 | TensorFold TP=2, graft, Engram **off** | same | same | `--require-engram` bypassed on the 2026-10-17 boot | 63.7 | — | — | — | the arm's `REPORT.md` names `bench_44534d5024c0` for that boot; the decode JSON is **not** in `~/benchmarks/cybersec-arm5-20261017/` (see open unknowns) |
| 14 | TensorFold TP=2, env-toggle pair | 1017 EXL3 body | TensorFold, TP=2 | `DSV41_CERT_HEAD=1` (C1) vs `DSV41_ENGRAM_DRM_NODE=/dev/dri/card0` (D1) — two keys the TensorFold engine does **not** reference | 66.29 ± 5.41 / 66.63 ± 2.14 | C4 49.32 / 44.20 | C8 48.65 / 44.01 | C16 44.11 / 45.72 | `…/ds4-1017-envtoggles-20261018/{C1,D1}.json`, `bench_a2c64c3dc6a1`; `C1.env-proof.txt`/`D1.env-proof.txt` show `engine_files_referencing_DSV41= []` |
| 15 | TensorFold TP=2, 1017 trial, 2026-10-17 | 1017 EXL3 body, Engram under `<snapshot>/engram` | TensorFold, TP=2 | first 1017 boot on this arm (3 runs/cell) | 61.53 ± 2.40 | C4 48.87 ± 0.70 | C8 49.31 ± 0.46 | C16 48.22 ± 0.09 | `~/benchmarks/ds4-1017-20261017/ladder.json` |

Row 14 is worth reading as a **control**: two boots of the same body, same engine, each carrying an
env key the engine never reads, land at 66.3 and 66.6 t/s C1 — a 0.5 % gap. That is the tightest
same-config pair in the family and it agrees with rows 10 and 11 (68.6, 66.4).

### Projected or third-party — not measured on this registry

| lever | source, date | projected effect | why it is not in the table above |
|:--|:--|:--|:--|
| `--min-free-slots-delay 1` (scheduler) | sparkring record, 2026-09-17, in [`DS4-SPEEDUPS.md`](DS4-SPEEDUPS.md) §1 | C8 decode 85.9 → 104.0 t/s (+21 %), C8 worst first-token wait 17.0 → 1.2 s | third-party 4×GB10 boot with a pool change entangled; our TP=4 rows never exceeded C10, and C8 exists only in row 9 |
| TRT-LLM sparse MLA (`--dsv4-attn-backend trtllm`) | `DS4-SPEEDUPS.md` §5 | 2.26× kernel geomean on GB10 | needs an image rebuild; no end-to-end number |
| Candidate-only indexer scoring (upstream #43401) | `DS4-SPEEDUPS.md` §3 | −17 % decode step at 1M on 2×GB10 | needs a tree newer than the pinned image |
| 1017 NVFP4 W4A4 (`LibertAIDAI/…-1017-NVFP4`) | `DS4-SPEEDUPS.md` §10 | +7.9 % C1 measured on the **pre-1017** pack | the 1017 NVFP4 pack quantizes Engram to MXFP4, which the card says SGLang does not support — unservable today |
| DCP2 decode context parallelism | `DS4-SPEEDUPS.md` §11 | +3.4 % full model | blocked upstream (the DCP × DSpark allowlist is Kimi Linear only) |
| DSpark γ=3 | `recipes/ds4/README.md`, §12.18 | no number exists | **proven non-bootable**: all four ranks abort at decode-graph capture (`Expected size 5 but got size 4`) |
| clock state | `~/benchmarks/ds4-p0-clock-20261019/REPORT.md` | 0 on this fleet | audited 2026-10-19: the test pair ramps to 2171–2190 MHz under load (`clocks.max.sm` 3003, SW power cap, no HW slowdown), and the production quartet read 2184–2190 MHz with `clocks_throttle_reasons.active = 0x0` while serving. No latch, so no row carries a clock penalty |

Two levers the ds4 README lists are **not** knobs on this family and appear in no row: a
`mamba_full_memory_ratio` (V4.1 is MLA + sliding-window attention, not a GDN body — that knob is the
qwen3.8 lane's), and a KV-dtype sweep (both 1017 recipes declare `kv_dtype: fp8` and no receipt
differs it).

## TP=2 vs TP=4 — what the data supports

Ratios use the TensorFold pair (row 10, the only TP=2 receipt at C2/C5/C10) against the v2.3 line's
two-boot means (rows 1–2: 89.1 / 111.1 / 115.8 t/s for C2/C5/C10, as the ds4 README states them) and
against the pooled C1 (row 4).

| cell | TP=2 pair | TP=4 quartet | TP=2 as a fraction of TP=4 | TP=4 ÷ TP=2 aggregate | per node: pair (÷2) | per node: quartet (÷4) |
|:--|--:|--:|--:|--:|--:|--:|
| C1 | 68.63 | 67.18 (pooled) | **102 %** | 0.98× | 34.3 | 16.8 |
| C2 | 48.05 | 89.1 | **54 %** | 1.85× | 24.0 | 22.3 |
| C5 | 44.56 | 111.1 | **40 %** | 2.49× | 22.3 | 27.8 |
| C10 | 42.07 | 115.8 | **36 %** | 2.75× | 21.0 | 28.9 |

The graft arm (row 12) sits slightly higher — 52.95 / 47.75 / 46.78, i.e. 59 % / 43 % / 40 % of the
quartet — so the pair's band is 54–59 % at C2 and 36–43 % at C5/C10. Against the **shipped** v2.4
line (row 7, interval off), which beats the v2.3 line by 18.7 % at C5, the pair is 33.8 % at C5 and
34.1 % at C10.

**1. Aggregate decode does not scale with node count at C1, scales below the node ratio at C2, and
scales above it from C5.** Doubling nodes buys 0.98× at C1, 1.85× at C2, 2.49× at C5, and 2.75× at
C10. The reason is measurable and it is not tensor parallelism: **the pair never batches**.
Aggregate ÷ per-request throughput — the effective number of streams the engine decodes at once — is
1.00 / 0.92 / 1.26 / 1.19 across the pair's C1/C2/C5/C10 cells, against 1.00 / 1.83 / 3.88 / 6.74 on
the quartet (`tg_req_throughput` in the same receipt JSONs). So the pair's C5 and C10 cells measure
**queueing**, not capacity, and the "2.5–2.75× for 2× the nodes" is mostly the pair contributing no
batching to the comparison. The pair's launcher passes `--parallel 4`
(`mods/tensorfold-dsv41-launcher/launcher.py:406`) and its boot line prints `--parallel 4: 4 streams
share one window of 1048576 tokens (an extent each)`; whether the 4-slot config *causes* the ~1.2
effective streams is [INFERENCE] — no receipt logs the engine's admitted-request count.

**2. The quartet stops scaling at C5; the pair at C2.** On the quartet, C10 is flat against C5 on
both v2.3 boots (+1.7 %, +6.9 %) and *below* C5 by 6.3 % on the shipped v2.4 line; the depth-0 shape
is likewise flat from C4 to C16 (118.9 / 107.5 / 115.9). Its sustained ceiling is ~115–120 t/s with
131.83 as the best cell ever measured. The pair's aggregate is already below its C1 by C2 and settles
at ~42–48 t/s from C5. Per node, the pair is **2.04× the quartet at C1** and still ahead at C2
(1.07–1.19×), then behind from C5 (0.79–0.86×) and C10 (0.73–0.81×): the crossover sits between C2
and C5, i.e. at the concurrency where the quartet starts batching.

**3. The memory/headroom half of the comparison.**

| | test pair (2 × 128 GB) | production quartet (4 × 128 GB) |
|:--|:--|:--|
| weights per node | **105.36 GB** (EXL3 210.72 GB ÷ 2) = 82 % of one node | **76.89 GB** ((510.31 − 202.76) ÷ 4) = 60 % of one node |
| Engram | ~189 GiB per node, **on NVMe**, streamed by the engine (`--require-engram` fails a miss) | packed per rank on NVMe (2 × 23.6 GiB/rank, 57–73 s on the first boot) |
| KV | engine grants `reserved 104.00 GiB` plus a shared 1,048,576-token window (a grant, not an occupancy) | pool **9,277,952** tokens at 1670.75 B/token ≈ **15.5 GB per rank** — `num_key_value_heads: 1`, so KV cannot shard (`attic/ds4/AGENTS.md` §2.4) |
| context served | 1,048,576 (the pool *is* the window; four streams share it) | 1,048,576, page-shared, up to 16 slots |
| node cost | 2 nodes | 4 nodes |

So the pair converts **1.37× the weight bytes per node** into **1.02× the C1 rate for half the
nodes**, and it pays for that with no multi-stream capacity. The quartet has ~36 GB of headroom per
node after weights and KV (128 − 76.89 − 15.50); the pair has ~22 GB after weights alone, before any KV.

**4. Two receipts that look like TP=4 wins and are not.** Row 9's C1 (80.97) is 1.98 σ above the
pooled 67.18 and was taken after two cold 119k/231k prefill probes warmed the Engram and L2 caches;
the ds4 README keeps it as a draw, not an arm. Rows 6–8's C1 cells (60.22 / 51.84 / 53.40) are
cold-contaminated the other way: each ladder's first run reads 19–39 t/s, which `recipes/ds4/README.md`
documents as a ramp, so no v2.4 C1 cell is that line's C1. The pooled 67.18 stands.

## Q2 — can a 1017 body be served at TP=1? The byte arithmetic

One node is **128 GB of unified memory**; the inventory, not a spec sheet. The two anchors that say
what fits in practice:

- The TP=2 arm boots with **105.36 GB of weights per rank** (`210,721,837,240 B ÷ 2`, from the
  checkpoint's own `model.safetensors.index.json`) plus the vision tower at 0.90 GiB, and reserves
  104.00 GiB of KV grant on a 128 GB node.
- The KV pool costs **1670.75 B per token** (`recipes/ds4/README.md`, the pool-pin formula), so a
  1,048,576-token window is **1.75 GB** — it does not decide fit at any plausible quant.

A working ceiling for a TP=1 body is therefore **~105 GB** (what a 128 GB node has booted with) and
**hard ceiling, 128 GB** (the node itself). The body has **552B parameters**
(`recipes/*/*-1017-*.yaml` `metadata.model_params`, and `attic/ds4/AGENTS.md` §2.1); the Hub's own
safetensors metadata for `deepseek-ai/DeepSeek-V4.1-Flash-1017` totals **763,205,315,794** parameters,
which is the 552B body plus the 196.6B Engram (2 × 384M rows × 256) plus the MTP and vision tensors.
So bytes per body parameter = on-disk ÷ 552e9, and the bpw that fits is:

```
105 GB  →  105e9 × 8 / 552e9 = 1.52 bpw
128 GB  →  128e9 × 8 / 552e9 = 1.85 bpw   (weights alone, no KV, no workspace, no host)
```

**Every 1017-class body the registry ships or has receipted, measured:**

| body | on-disk bytes (source) | body bpw | ÷ 128 GB node | verdict |
|:--|--:|--:|--:|:--|
| official 1017 MXFP4/F8 | **510.31 GB** total (Hub file sum; `attic/ds4/AGENTS.md` §2.2: 510.29 GB, 48 shards) — of which **202.76 GB** is the two FP8 Engram tables, so body = **307.53 GB** | 4.46 | 2.40× | 4 nodes (shipped, TP=4) |
| `LibertAIDAI/…-1017-EXL3-2.9bpw` | **210,721,837,240 B** = 210.72 GB (`model.safetensors.index.json` `total_size`, read in a node cache; the Hub file sum agrees at 210.82 GB); ships **no** Engram | 3.05 | 1.65× | 2 nodes (shipped, TP=2) |
| `LibertAIDAI/…-1017-NVFP4` | **429.01 GB** total, Engram MXFP4 97.28 GiB → body ≈ 324.60 GB | 4.70 | 2.54× | does not fit any topology the lane runs (Engram unsupported in SGLang) |
| `0xSero/…-1017-EXL3-2.7bpw` | **198.60 GB** | 2.88 | 1.55× | no TP=2 receipt |
| `kaushikvira/…-1017-GSQ-agentic-strata` | body GGUF **174.36 GB** + Engram 188.8 GiB | 2.53 | 1.36× | research only; no shipped engine opens the strata format |
| `lxe/…-1017-dsx-2bit` | **148.09 GB** body (4 shards: 37.26 + 37.17 + 37.05 + 36.61) + 0.97 GB vision; the card requires the official 203 GB Engram beside it | 2.15 | 1.16× | smallest 1017 body that exists in a real runtime format; still 1.16× the whole node |
| `unsloth/…-1017-GGUF` UD-IQ1_S | **122.38 GB** body, computed two ways: the repo's 232.98 GB tier minus its 110.595 GB Engram file, and the `lxe` card's "~122 GB without Engram" | 1.77 | **0.96×** | the smallest 1017 body published anywhere — and it still does not fit: 122.38 GB is 95.6 % of the node's *total* memory before KV, activations, or a host, and 1.17× the 105 GB a node has actually booted with |

**Verdict: no 1017-class body fits TP=1, at any quantization the lanes record or the Hub publishes.**
The body arithmetic is unforgiving: 552B parameters at the ~3.05 bpw effective that the TP=2 arm's
2.9 bpw pack measures is 210.72 GB, 1.65× a whole node; the best published compression (UD-IQ1_S, 1.77 bpw) still needs 122.38 GB, and
the smallest 148 GB body needs a runtime that streams from host RAM the way `dsx` does on a
48 GB + 128 GB box — memory a Spark does not have spare, because its 128 GB *is* both. A TP=1
safetensors recipe would additionally have to hold the Engram, which no single-node path in this
registry does (both shipped arms stream it from NVMe), and a GGUF route would have to hold it too:
Unsloth's IQ4_NL Engram file is 110.595 GB on its own, and the MXFP8 one is 202.76 GB.

The two consequences worth writing down:

- **The family's smallest reachable topology is TP=2, and it is not close to TP=1.** The gap is not a
  rounding error to be closed by a flag; it is 1.17–1.65× the node on the smallest bodies that exist,
  against a 1.52 bpw target that nothing publishes.
- **Even if a body fit, quality would not survive.** The 1.77 bpw body's own publisher-measured cost
  is KL 0.373, top-1 74.4 %, perplexity 10.68 against the FP8 original's 8.56 (`lxe` card, measured
  on the Lucebox 1017 eval set). The registry's own quality bar for this family is EXL3 2.9 bpw at
  **parity with official weights** — house 36/37 both, hard tier 17/18 both, no benchmark separating
  them across 11 benches and ~1,900 paired items (`recipes/ds4/benchmarks/`). A 1.5 bpw 1017 arm would
  be a different product, not a smaller one.

## What would have to happen next

Nothing here is a recipe proposal. The gate for each item is named, and **no TP=1 recipe is
authorable today** — a recipe that cannot boot is not a plan.

1. **A TP=1 body at ≤1.5 bpw effective (≤105 GB) does not exist.** Producing one means quantizing the
   552B body ~14 % below the smallest published body (122.38 GB at 1.77 bpw), and the EXL3 recipe this
   lane runs (mul1, K=3/K=4 trellis on the routed experts) was tuned for 2.7–3.5 bpw, so a sub-1.5 bpw
   EXL3 export is unproven, not merely unpublished. Gate: a published repo whose body measures under
   105 GB, plus a card-measured quality point at or near the Official/EXL3 parity bar above.
2. **An engine that loads such a body on GB10.** Three candidate routes, each with a named gate:
   - **llama.cpp.** The pinned runtime tier's engine is `0.1.2-dev (build 1, commit b2e5e9b)` and its
     arch map lists `deepseek4` but not this family's arch (`mad-science/LLAMACPP-GGUF.md` §2);
     Unsloth's card says to use *their* llama.cpp PR. Gate: a boot of an IQ1_S-class 1017 GGUF on the
     pinned image, which also has to hold the Engram in the same 128 GB pool.
   - **`dsx`** (the 148 GB body's runtime): a Rust + CUDA engine, GPU + host-RAM split at
     48 GB + 128 GB. A Spark has no second memory tier to spill into. Gate: a demonstrated GB10
     build, which does not exist.
   - **TensorFold/SGLang with a re-quantized body.** They already stream Engram from NVMe, so only the
     body must fit. Gate: a body under 105 GB that the engine's `family.check()` admits (it refuses a
     non-`exl3` `quant_method` on this arm).
3. **A TP=2 re-measure before any TP=1 work is justified.** The pair's effective concurrency never
   exceeds ~1.4, which is the cheapest open lever in the family: one boot with a larger `--parallel`
   and a logged admitted-request count would say whether the pair's 42–48 t/s plateau is a config cap
   (in which case the pair is under-measured) or the engine's ceiling (in which case TP=2's single-user
   tag is a hardware statement). Cost: one test-pair boot. Nothing on the quartet is needed, so the
   production serve is not disturbed.
4. **An interleaved TP=2-vs-TP=4 comparison on one engine.** No such receipt exists; the whole table
   above compares two stacks. The honest version is one engine, one quant, two topologies, A/B/A/B boot
   slots — which needs the quartet's owner-scheduled window (the standing policy) and a TP=2 body the
   quartet can also serve (EXL3 2.9 bpw at 105.36 GB/node, or the official base at 76.89 GB/node).

## Open unknowns

- **Is the pair's ~1.2 effective concurrency a `--parallel 4` cap?** The launcher hardcodes
  `--parallel 4` (`launcher.py:406`) and no receipt logs an admitted-request count. [INFERENCE] until
  a boot logs it.
- **`bench_44534d5024c0` (arm 5, Engram-off, C1 63.7)** is cited by that receipt's `REPORT.md`, but its
  decode JSON is not in `~/benchmarks/cybersec-arm5-20261017/` — the directory holds boot logs, a
  contract probe, and `probe-text.json` only. The figure is a REPORT-level citation, not re-derivable
  here.
- **The TP=2 C2/C5/C10 row and the TP=2 depth-0 row come from different node pairs.** Row 10 ran on
  the production quartet's first two nodes (the receipt's own `REPORT.md` records a cold boot with
  `CUDA extensions built from scratch`, TTR 516.5 s), and rows 11–15 ran on the test pair. The lane's
  documented boot-slot spread is 7–25 %, so pooling rows 10 and 11 into one "TP=2 ladder" would be
  wrong and this note does not do it.
- **Whether the pair's engine batches at all above 4 streams.** Untested; C16 on the pair exists
  (48.39) and is *higher* than its C8 (44.80), which is not the shape a hard 4-slot cap predicts. The
  C8 instability is documented for both arms, so that inversion is a boot slot, not a signal.
- **The quartet's C1 has no interleaved v2.4-vs-1017 A/B.** The 67.18 pool is four takes on the v2.3
  line; the +13.5 % against the v2.4 baseline's 59.21 has overlapping intervals. Any TP=1 argument
  that leans on TP=4 C1 leans on a number that is still open.
- **`unsloth/…-UD-IQ1_S` body bytes are a subtraction, not a file census.** 232.98 GB (repo file sum)
  minus the 110.595 GB Engram file assumes shard 5 *is* the Engram, which the identical byte count
  supports but does not prove; the `lxe` card's "~122 GB" is the independent second reading, and no
  GGUF header was read here.
- **The 1017 NVFP4 pack has no published FP8-Engram variant**, so the W4A4 route's +7.9 % (measured on
  the pre-1017 pack) cannot be tested on the 1017 weights. `DS4-SPEEDUPS.md` §10 holds the detail.
- **`ds4-knapcio-1017-20261018/arm-1017` also carries `chat.json`**, which is the vision/contract
  probe, not a ladder; it was excluded from the table by shape, not by distrust.