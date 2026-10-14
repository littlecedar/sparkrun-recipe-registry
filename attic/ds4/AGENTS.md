# DS4 — DeepSeek V4 / V4.1-Flash Sparkrun recipes — agent guide

Durable, consolidated notes for the `recipes/ds4/` DeepSeek V4 family on NVIDIA
DGX Spark (GB10, SM121, 128 GB unified LPDDR5X/node, 2× ConnectX-7 200 GbE RoCE).
This file absorbs what used to live in `DS4-MODEL-OPTIMIZATION-WORK.md` and
`JOURNAL.md` (both deleted) and the long header comments that used to sit in the
recipe YAMLs. Read this before touching a recipe, a guard, or a mod in this lane.

**Shipped suite:** five EXL3 / vLLM recipes — `deepseek-v4.1-flash-exl3-{tp3,tp4,tp4-1m,tp6,tp6-1m}-vllm`
— all boot and serve on our cluster (measured 2026-09-24/25/26). The earlier
SGLang recipes were removed 2026-09-25 (they do not boot); see §9.

**Evidence vocabulary (repo convention, used throughout):**
- **VERIFIED** — read from a primary artifact (checkpoint header, `config.json`,
  upstream source at a pinned commit, a boot log we produced) or measured on our
  devices.
- **LIKELY** — strong secondary evidence, or a number someone else measured on
  hardware we have not touched.
- **SPECULATIVE** — reasoning without a source. Do not build on it.

Numbers we derived say "computed here"; numbers someone else measured name who.
Never promote a `LIKELY` into an unlabelled fact.

> **Tracking note (2026-10-11).** The two mods these five recipes mount —
> `mods/mount-dsv41-exl3-patches` and `mods/bound-engram-cache` — now live in
> `attic/ds4/mods/`: the EXL3 lane was the only thing left mounting them. The
> recipes' `@littlecedar/mods/…` references resolve only after both mods move
> back to `mods/` (and are pushed); the guard constants in
> `tests/test_ds4_recipes.py` and `tests/test_bound_engram_cache.py` already
> point here.

---

## 1. Objective coverage

The objective asked for recipes at TP=4, TP=3 and TP=2 "where possible", ≥1M
context, priority **quality > speed > context > TP**. Measured outcome:

| target | verdict | basis |
|:--|:--|:--|
| **TP=4 + 1M** | buildable, serves | `…-exl3-tp4-1m-vllm`, KV 5,750,109 tok (@gmu 0.85), needle ✓ @799K |
| **TP=4 (300K)** | serves | `…-exl3-tp4-vllm`, KV 5,203,288 tok, C1/C4/C8/C16 38.8/66.3/88.5/122.0 |
| **TP=3** | serves + DSpark (measured 2026-09-27) | `…-exl3-tp3-vllm`, KV 1,896,721 tok, C1/C4/C8 34.3/59.1/77.7, accept 2.40–2.50 |
| **TP=6** | serves, fastest; DSpark (measured 2026-09-27) | `…-exl3-tp6-vllm`, KV 13,594,187 tok, C1/C4/C8/C16 40.0/78.0/107.9/151.1 |
| **TP=6 + 1M** | serves + DSpark (measured 2026-09-27) | `…-exl3-tp6-1m-vllm`, KV 15,034,010 tok, C1/C8/C16 43.4/110.2/149.1, needle ✓ @799K |
| **TP=2** | **impossible, not hard** | §3 — ~257 GB non-Engram weights vs 220 GB usable on a pair |

All four TP=4/TP=6 rows were retuned 2026-09-27 to `max_num_seqs: 16` and
`gpu_memory_utilization: 0.85` (§7.12); the KV/C1/C8 figures above are from
boots of the recipes **exactly as shipped** after that retune.

TP=2 is a documented negative result and is guarded (`NoTP2`). The
`MillionTokenContext` guard makes the 1M requirement a shipped-artifact invariant.

---

## 2. The model

### 2.1 The family (VERIFIED 2026-09-19, HF API + `config.json`)

| Repo | Params | Active | Layers | Released |
|:--|--:|--:|--:|:--|
| `DeepSeek-V4-Flash` | 284B | 13B | 43 | 2026-04 |
| `DeepSeek-V4-Flash-0731` | 284B (304B card) | 13B | 43 + DSpark | 2026-07-31 |
| `DeepSeek-V4-Pro` | 1.6T | 49B | — | 2026-04 |
| `DeepSeek-V4.1-Flash` | 552B + 196B Engram | 8B prefill / 16B decode | 40 (20 enc + 20 dec) | 2026-09-10 |

V4.1-Flash is **not** a bigger V4-Flash: `model_type: deepseek_v41`,
`architectures: ["DeepseekV41ForCausalLM"]`, and a different *problem* on this
hardware. Headline "active params" is useless for planning — read bytes/token.

### 2.2 Anatomy from tensor shapes (VERIFIED, `.scratch/ds4_anatomy.py`, HTTP Range reads)

**`DeepSeek-V4.1-Flash` — 510.29 GB, 48 shards, 96,085 tensors.**
`I8` 278.59 | `F8_E4M3` 204.02 | `F8_E8M0` 23.56 | `BF16` 3.95 | `F32` 0.17 GB.
Functional: routed experts 288.78, **Engram 202.76**, MTP/DSpark 7.93, attention
5.07, shared expert 1.42, embed+head 1.32, vision 0.97, router 0.16.

**The Engram is the whole story.** Two tensors
(`layers.{1,14}.engram.embed.weight`) are `[384006168, 256]` and `[384016682, 256]`
in `F8_E4M3` — 98.31 GB each. **40% of the checkpoint lives in two embedding
lookups.** Nothing about "552B" prepares you for that, and it is the entire
engineering problem. (`DeepSeek-V4-Flash` has **no** Engram; 159.61 GB total.)

### 2.3 The official expert quant is MXFP4, not NVFP4 (VERIFIED by shape)

`expert_dtype: "fp4"` ships as `I8` holding two FP4 (E2M1) values per byte along K,
one `F8_E8M0` (ue8m0) scale per 32 K-elements. Shape arithmetic matches exactly on
all four expert tensors in both checkpoints. Consequence: **the official checkpoints
are already FP4 in the experts.** `nvidia/DeepSeek-V4.1-Flash-NVFP4` is **527.3 GB,
17 GB LARGER** than the 510.3 GB MXFP4 original (one E4M3 scale per 16 vs one ue8m0
per 32) and leaves the Engram at FP8 (`engram: null`). On a memory-limited box the
"NVFP4" repo is the **wrong** default.

### 2.4 Config fields that drive kernel and topology choices

| field | V4-Flash | V4.1-Flash | why |
|:--|:--|:--|:--|
| `num_hidden_layers` | 43 | 40 (20 enc + 20 dec) | allreduce count/step |
| `hidden_size` | 4096 | 5120 | |
| `n_routed_experts` / top-k | 256 / 6 | 384 / 6 | expert slab count |
| `n_shared_experts` | 1 | 1 | cannot fuse under HashTopK |
| `num_key_value_heads` | 1 | 1 | **KV cannot shard over TP** |
| `num_attention_heads` | 64 | 64 | TP degree must divide 64 |
| `o_groups` | 8 | 8 | TP degree must divide 8 |
| `moe_intermediate_size` | — | 2304 | **must divide to a multiple of 128 at TP** (§7.5.4) |
| `index_topk` / `index_n_heads` | 512 / 64 | 512 / 32 | indexer transient (§6.3) |
| `sliding_window` | 128 | 128 | per-layer SWA |
| `hc_mult` / `hc_sinkhorn_iters` | 4 / 20 | 4 / 20 | mHC: 4 residual streams |
| `num_nextn_predict_layers` | 1 | 3 | DSpark draft depth |
| `dspark_n_routed_experts` | — | 128 | TP must divide 128 |
| `engram_num_embeddings` | — | ~384M × 2 | the 203 GB |
| `max_position_embeddings` | 1,048,576 | 1,048,576 | YaRN factor 16 on 65,536 |

**TP-degree divisibility (computed here).** `heads=64`, `o_groups=8`, V4.1 draft
experts `=128` — divisible by 2 and 4. TP=3 and TP=6 need the **virtual-heads**
padding (64→72 / 64→96). Separately, the MXFP4-Cutlass MoE requires the expert
intermediate width to be a multiple of 128 at the TP size: `2304/6 = 384 ✓`,
`2304/4 = 576 ✗`, `2304/8 = 288 ✗`, `2304/2 = 1152 ✓` — see §9.

### 2.5 The EXL3 3.5 bpw checkpoint (VERIFIED 2026-09-23 from local HF cache `config.json`)

`bot-lab-21/DeepSeek-V4.1-Flash-EXL3-3.5bpw-Pollard` — **not** a different model:
same `deepseek_v41` architecture, `hidden_size` 5120, 40 layers, 64 heads, 384
experts. Only the **40 × 384 routed experts** are re-quantized, from packed MXFP4
to an EXL3 trellis at a K=3/K=4 mix (3.51 bpw avg). Everything else — attention,
dense FP8, MXFP4 shared experts, the DSpark drafter, native FP4 KV, the two fp8
Engram tables — is byte-identical to the release, hardlinked per shard.

`quantization_config`: `quant_method: "exl3"`, per-layer `expert_bits` (18 at
K=3/K=3, 3 at K=3up/K=4down, 19 at K=4/K=4), `codebook: mul1`, `out_scales: always`,
`original_quantization_config` = the release block. Consumed by the `cuda-exl3`
plugin's `Exl3Config`; **no `--quantization` flag is needed.**

Sizes: release 510.29 GB → EXL3 build **460.0 GB**; routed experts 288.78 → **245.4**;
shards 1, 2, 43–48 (Engram 203, vision, head, drafter) sha256-identical to release.
Non-Engram total: 307.53 (release) → **~257** (computed here, 460.0 − 202.76).

**Quality (author's numbers, in-domain):** paired held-out NLL `1.3209 → 1.3177`
(Δ −0.0032 ± 0.0055, 39 rows), served HumanEval/HumanEval+ `0.951/0.921`. These are
the author's calibration set — **our own independent held-out battery is in §7.6**.

**This does not rescue TP=2:** ~257 GB non-Engram vs 220 GB usable on a pair (§3).

---

## 3. The residency wall (load-bearing)

128 GB is *unified*: GPU, CPU, OS, page cache, NCCL buffers all draw from one pool.
`gpu_memory_utilization` / `mem_fraction_static` is a promise against device
capacity, not a guarantee against the OS. Prior Qwen3.8 work measured ~112 GB "pre"
against a 130.66 GB device — **~18 GB is what the OS and other tenants hold**
(`LIKELY`). We use **108.8 GB/node (0.85 × 128)** as the working budget and treat
100 as the comfortable ceiling.

Per-node weight residency (computed from exact tensor bytes):

| checkpoint | total | TP=1 | **TP=2** | **TP=4** | TP=8 |
|:--|--:|--:|--:|--:|--:|
| V4-Flash | 159.6 GB | 159.6 ✗ | **79.8 ✓** | 39.9 ✓ | 20.0 ✓ |
| V4-Flash-0731 (+DSpark) | 168.0 GB | 168.0 ✗ | **84.0 ✓** | 42.0 ✓ | 21.0 ✓ |
| V4.1-Flash, all-in | 510.3 GB | 510.3 ✗ | 255.1 ✗ | 127.6 ✗ | 63.8 ✓ |
| V4.1-Flash, Engram off-GPU | 307.5 GB | 307.5 ✗ | **153.8 ✗** | 76.9 ✓ | 38.4 ✓ |

### 3.1 The cluster-total-RAM bound (the only airtight one)

Because GPU and host share one pool, bytes move between them but nowhere else, so
the only unarguable budget is *cluster* RAM:

```
all weights (GB)  <=  TP_nodes × (128 − 18)
```

At TP=2 that is **220 GB**, and V4.1's non-Engram weights alone are **307.5 GB**
(release) / **~257 GB** (EXL3). This is independent of every engine flag and every
quantisation choice: the experts are *already* FP4 and that is the floor. **TP=2
for V4.1-Flash is closed.** Even a 2-bit Engram is 358.2 GB against 220. The only
escape is expert offload to NVMe, which changes the problem class from
tensor-parallel to expert-offload and puts the hot path over a disk. **V4-Flash
(166.9 GB) does fit at TP=2** — that is why the (now-removed) TP=2 recipes targeted
V4-Flash, not V4.1.

### 3.2 Where the 203 GB Engram can and cannot live

Upstream's answer is `SGLANG_ENABLE_DSV41_ENGRAM_HOST_TABLE=1` (VERIFIED, three
sources): move the tables to pinned **host** RAM, free ~100 GB of HBM into KV,
drop one all-reduce, output bitwise-identical. **On a Spark it is worth zero**: host
RAM is the same 128 GB, and `per_rank` allocates `num_embeddings / TP` host rows —
byte-identical to the GPU shard, merely relocated to the other side of the same
pool. `shared` is single-node-only (passes a memfd through `/proc/<pid>/fd/<fd>` and
hard-fails "the TP ranks must share a PID namespace", `engram.py:605-611`).
`per_rank` keeps the all-reduce; only `shared` removes it, and `shared` needs a
single node. **The upstream host-table feature does not make TP=4 fit** and is not
what our recipes rely on. The vLLM answer is the Engram-on-disk row reader (§5).

### 3.3 Two ceilings, and `sparkrun recipe vram` reports neither correctly

1. **Advertised**: `mem_fraction_static × device_total` = `0.80 × 121 = 96.8 GB`.
   What SGLang enforces; counts **GPU-resident bytes only**.
2. **Physical**: `128 − ~18 = 110 GB` of non-OS RAM. What the kernel enforces;
   counts **everything**.

Weights must clear (1); the *node* must clear (2). The trap: with the Engram host
table on, SGLang's check passes while the node needs 127.6 GB of ~110 — the OOM
arrives **after a ~25 minute checkpoint read**, from the kernel, on the node nobody
is watching. Row 2 (no host table) fails fast and honestly. `per_rank` buys nothing,
so turning the feature on converts a clean rejection into a slow confusing crash.

**`sparkrun recipe vram` under-reports DeepSeek-V4 weight bytes by ~17%.** Measured
against `nvidia/DeepSeek-V4-Flash-0731-NVFP4`: HF `usedStorage` 175.56 GB →
87.78 GB/node, `sparkrun` "Model weights" 132.25 GB → 66.13 GB/node (**−21.66
GB/node**); reported KV headroom 30.7 GB vs real 9.0 GB; it still prints
`DGX Spark fit: YES`. It applies flat `params × bytes/param` and ignores the E4M3
scale tensors, FP8 non-expert tensors, and BF16 router/norm/mHC, while its own
header warns the KV figure "covers the compressed latent cache only". **Rule:
divide the repo's HF `usedStorage` by TP and treat that as the weight cost. Never
let `recipe vram`'s `fit: YES` be the evidence a recipe boots.** For the EXL3
checkpoint it is worse — dtype `exl3` reads as unknown and it prints "Model
weights: 0.00 GB". Read `GPU KV cache size` from the boot log instead (§6).

### 3.4 What makes TP=4 work, and the only lever that fixes it

| V4.1-Flash | TP=2 (220 GB) | TP=4 (440 GB) | TP=8 (880 GB) |
|:--|--:|--:|--:|
| non-Engram weights, 307.5 GB | **✗ 87.5 over** | ✓ 132.5 spare | ✓ 572.5 spare |
| all-in, 510.3 GB | ✗ 290 over | ✗ 70.3 over | ✓ 369.7 spare |
| with INT4 Engram, ~409 GB | ✗ 189 over | ✓ **31.1 spare** | ✓ 471.1 spare |

**A 4-bit Engram is the single lever that makes TP=4 workable with no out-of-tree
kernel, and it already exists as a download:** `INCModel3/DeepSeek-V4.1-Flash-MXFP4-Engram-AutoRound`,
412.2 GB (`engram_embed: "MXFP4 packed: .weight int8 [R,128] + .scale e8m0 [R,8]"`).
Two independent confirmations: its `engram_layer_ids: [1,14]` /
`engram_num_embeddings` match our tensor shapes exactly, and its dtype census shows
`F8_E4M3` −196.62 GB, `I8` +98.31 GB (ratio 0.5000). **The blocker is software**:
SGLang's `EngramEmbedding` allocates `torch.float8_e4m3fn` rows + `float8_e8m0fnu`
scales (`engram.py:688-697`) and rejects int4-packed rows, and the checkpoint
declares `quant_method: "auto-round"`, unwired for `deepseek_v41`. `SPECULATIVE`
that the patch is small — read `engram_gather.py:40-42`, which already accepts int8
rows.

### 3.5 KV is nearly free (unusual, and it changes the design)

V4.1-Flash's global KV is **890 B/token** and only four `kv_source_layer_ids`
store it; at TP=4 the per-rank figure is **1,670.75 B/token/rank** (replicated, not
split). A full **1M context costs ~0.93 GB/sequence** — less KV than a Qwen3.8 262K
context. **KV is not the constraint; weights are, entirely.** Size the pool from
the boot log and stop thinking about it.

---

## 4. Roofline and the decode model

**Do not use the naive bandwidth roofline.** It says V4.1-Flash TP=4 with a 6-token
DSpark window moves 23 GB/rank/step → ~10 t/s, which is wrong by ~4× (measured is
45.4 t/s at TP=4). At bs=1 the step is **GEMM-efficiency- and launch-bound**, not
memory-bound.

Our step model (`.scratch/ds4_decode_model.py`), calibrated against MiaAI's
published TP=3 profile (measured ~82 ms/step): predicts **80.9 ms additive**
(agrees to 1.3%) / 59.4 ms overlapped. Terms:

```
bytes_rank = (dense_once + experts*window + draft + KV*window) / TP
t_mem      = bytes_rank / 224.6 GB/s
t_comm     = (104/40 * layers) * (100 µs + 20 µs * (TP-2))   # LL, latency-bound
t_launch   = layers * 45 kernels * 5 µs
t_step     = (t_mem + t_comm + t_launch) / accept_length
```

The additive form is the one that agrees. **The comm term is structural:** ~104
collectives/decode step, ~3,300 per 32-token block.

### 4.1 The finding: spec decode inflates the byte term on an MoE

Dense/attention/lm_head weights are read once per step regardless of window (`M`
grows, `K`/`N` don't); **routed experts are read once per token** (each token picks
its own top-6). So a window-`W` verify reads `dense + experts×W` — only the latency
term amortises. The model predicted the DSpark block-size optimum near 4, not the
default 5 — **and a measured sweep (below) overrode the interior peak**; the model's
*direction* (less than k=5) survives.

### 4.2 RESOLVED — the DSpark k-sweep (§7.7): optimum is k≈2–3, not the shipped k=5

The additive table's peak at k=4 is **wrong**. The measured optimum is k=3 (C1)
sliding to k=1 (C8), and the reason is not the byte term §4.1 computes: k=5 accepts
*more* tokens/step (2.44 vs 2.25) and is still 14% slower at C8 — its 4th/5th verify
slots land only 12%/5% of the time and cost more than they return. §4.1's premise
(each verify position costs a full expert pass) is the premise **Cohere** measured
to be wrong by a factor (unique experts scale only 1.25–1.42×). Both the model and
reality point the same way — *less speculation than the default* — but the
measurement, not the arithmetic, is the reason. See §7.7.

### 4.3 What survives from the naive roofline

- TP=8 is **not** free and buys nothing for bs=1 latency (comm-bound). Its real use
  is fitting V4.1-Flash's Engram, not speed.
- TP=4 over TP=2 on V4-Flash: model says 21.8 → 26.4 t/s additive (21% better),
  driven by `t_mem` halving while `t_comm` rises. Matches MiaAI's TP=4 > TP=3.
- vLLM's fused RoCE allreduce (`VLLM_ENABLE_ROCE_ALLREDUCE=1`) is the most
  consequential line in the Qwen3.8 cluster recipe, and it applies more here.
  SGLang has no equivalent knob; confirm the transport with `NCCL_DEBUG=INFO`.

---

## 5. The Engram-on-disk mod — the one non-negotiable piece

**All five recipes need `mods/mount-dsv41-exl3-patches`.** It installs 14 files
from `tonyd2wild/patch/exl3-tp3/` over the image's `vllm/` and `cuda_exl3/` paths
(13 upstream files plus our own `config/speculative.py`, which propagates the
virtual-heads dict `hf_overrides` to the DSpark draft config — see §7.3, §10 E7).
The load-bearing one is `engram.py`: the image ships the V4.1 model tree and the
`cuda-exl3` plugin but **not** the Engram-on-disk reader (probed read-only
2026-09-23). Without it the two 203 GB Engram tables cannot leave unified RAM and
the 4-node boot dies ~25 minutes into the checkpoint read.

The mod is **fail-closed**: it md5-verifies all 14 files, backs up each target once
(`.sparkrun-orig`), installs `virtual_heads.py` as NEW, and dies if
`DSV41_ENGRAM_DISK` is absent from the installed `engram.py` or
`DSV41_DRAFT_VIRTUAL_HEADS` is absent from the installed `config/speculative.py`.
A half-applied patch tree is worse than none and the failure it prevents is slow
and confusing.

Repo provenance: `tonyd2wild/DeepSeek-V4.1-Flash-vLLM-DGX-Spark` (MIT; patch files
are `SPDX: Apache-2.0` vLLM derivatives), cloned to `.scratch/ds4/tonyd2wild-vllm/`.

**The image** `littlecedar/dgx-spark-dsv41:exl3a` is `tonyd2wild`'s
`vllm-dsv41:exl3a` **retagged** (label `kai.exl3a=cuda-exl3-6a1ffc34` matches
`build_exl3a.sh`). Base `lmsysorg/vllm-openai:nightly-8a728663` (vLLM
`0.28.1rc1.dev388+g8a728663c`, torch 2.13.0+cu130), entrypoint `vllm serve`. Ships
`vllm/models/deepseek_v4_1/`, registry entries for `DeepseekV41ForCausalLM` and
`DSparkV41DraftModel`, and the `cuda-exl3` 1.0.x plugin. Its `engram.py` (md5
`27f27c33328a023b2d2df7d62210ae97b3`) contains none of `DSV41_ENGRAM_DISK`,
`preadv`, `O_DIRECT`.

---

## 6. Recipe mechanics, shared failure modes, and boot discipline

### 6.1 sparkrun gotchas that cost us boots

- **Consuming ENTRYPOINT.** The image declares `ENTRYPOINT ["vllm","serve"]`, which
  would parse sparkrun's appended launcher as its own flags. sparkrun refuses to
  launch until cleared — every recipe sets `executor_config: entrypoint: ""`
  (`-o entrypoint=''` is the one-off). Guarded (`test_consuming_entrypoint_cleared`).
- **`CUDA_EXL3_MODEL_PATH` is required and is a serve-line prefix, not an `env:`.**
  The cuda-exl3 drafter is a fresh process that rebuilds its quant config from the
  *summary* inlined in `config.json`, which omits `tensor_storage`; with no hint it
  dies at engine init with `EXL3: could not find tensor_storage` (**after** a
  7-minute weight load). `exl3_config.py:437-439` falls back to this env var to find
  the full `quantization_config.json`. Because **sparkrun does NOT interpolate
  `env:`**, it is written as a bare assignment prefix on the `command:` line
  (`CUDA_EXL3_MODEL_PATH=<literal snapshot path> vllm serve …`).
- **Bash does not glob a bare assignment.** `CUDA_EXL3_MODEL_PATH=/.../snapshots/*`
  passes the literal `*`, so the dir doesn't exist and the `tensor_storage` error
  returns. Proved in 3 lines (`X=/tmp/*/x bash -c 'echo $X'` → literal). Use the
  literal path.
- **HF snapshot dirs are symlink trees.** `cluster_config.resolved_model_path` cannot
  serve one: identity-mounting only the snapshot leaves `config.json` dangling and
  vLLM rejects it ("Invalid repository ID or local directory"). Use the managed
  `/cache/huggingface` mount.
- **`transfer_mode`.** The HF cache is **per-node** (no NFS export; verified
  2026-10-03 — every node's `~/.cache/huggingface` is node-local ext4 on
  `/dev/nvme0n1p2`), so the checkpoint **must be distributed to every node** and
  `distribution.model.enabled` stays **true**. (It was `false` when the head
  exported the cache over NFS; do not restore that.) With a `local` `file://`
  registry, `transfer_mode: local` fetches on the control machine and pushes —
  and it pulls the image on an amd64 control host, which fails for an arm64-only
  image (`no matching manifest for linux/amd64/v4`); `pull` hits a sparkrun 0.3.9
  bug (`sync_image_to_hosts() got an unexpected keyword argument 'ssh_options'`);
  **`delegated` works** (builds/pulls on the arm64 head node) — but `delegated`
  makes the *node* clone a local `file://` registry, which fails, so use `local`
  when the registry is a local `file://` path.
- **A bare `--hosts` does not carry the ssh user or transfer mode; a saved
  `--cluster` does.** `--hosts ${WOPR_USERNAME}@.32,…` made the *node* try to `git clone`
  our `file://` registry and fail. Fix: `sparkrun cluster create ds4tp4 --user red
  --transfer-mode local`.
- **`docker logs` is empty — the serve log is `/tmp/sparkrun_serve.log` INSIDE the
  container**, readable with `docker exec <c> cat /tmp/sparkrun_serve.log`.
- **Probe with `${WOPR_USERNAME}@` first.** `ssh siv@…` returns `Permission denied`; all six
  nodes work as `${WOPR_USERNAME}@`.

### 6.2 vLLM on this build: probing without a GPU

`vllm serve --help` **exits 1 without a GPU** (`make_arg_parser` → `DeviceConfig`
→ "Failed to infer device type"). To check flags device-free: build only the
`FrontendArgs` half of the parser, and check engine flags against the
`EngineArgs`/`AsyncEngineArgs` dataclass fields (vLLM derives `--x-y` from field
`x_y`). All 15 recipe flags are real fields; no flag is fabricated.

### 6.3 NCCL / RoCE env

Sparkrun's own InfiniBand probe fills `NCCL_NET` / `NCCL_IB_HCA` /
`NCCL_IB_GID_INDEX` / `NCCL_IB_DISABLE` / `NCCL_CROSS_NIC` / `NCCL_IB_MERGE_NICS` /
`NCCL_IGNORE_CPU_AFFINITY` per cluster, and a recipe value would **override** that
detection (validate warning `managed-comm-env`). They are deliberately **not** set.
Upstream pins them (GID 3, `rocep1s0f0`) and that is right for their fleet. The vars
we *do* set are the levers:
- `NCCL_MAX_NCHANNELS=8` — bot-lab-21's +11% C6.
- `NCCL_CUMEM_ENABLE=0` — MiaAI's pinned-buffer lever (4.7 GiB → 0.14 GiB).
- `NCCL_NVLS_ENABLE=0` — not a 4-node RoCE topology.
- `NCCL_IB_ROCE_VERSION_NUM=2`, `NCCL_IB_ADDR_FAMILY=AF_INET`, `NCCL_DEBUG=WARN`.

NCCL buffers are the biggest reclaimable host-RAM pool on a spark: VERIFIED 512
connection buffers × 9.19 MiB (Simple + LL128 + LL) = 4.7 GiB of unreclaimable
`Shmem` per node; tuning knobs cut it to 139 MB, which turned 0.2–0.8 GB free into
~6 GB free and removed the boot-time "KV lottery". The head also runs the HTTP
server, tokenizer and detokenizer — keep load generators and profilers
off it.

### 6.4 `expandable_segments` — a boot-breaking correctness trap, unresolved

Two credible sources disagree on the most-recommended PyTorch unified-memory fix:
upstream DGX Spark cells ship `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`
("avoids unified-memory fragmentation OOMs on GB10"), while MiaAI report it
produces **NaN logits above 64 prefill query tokens** (V4.1 `dsv4` backend is newer
than the V4-Flash backend the Spark cells target). We ship `expandable_segments:True`
on the EXL3 recipes (matching upstream/bot-lab-21) and add
`garbage_collection_threshold:0.6` on the TP=3/TP=6 lanes (upstream's value). Any
recipe enabling it needs a prefill smoke comparing a ~512-token greedy continuation
against the same prompt with it off. The fragmentation mechanism: each chunk
allocates an indexer-logits buffer proportional to the prefix so far, so **reserved
memory grows with the square of prompt length** — `--chunked-prefill-size 1024` at
1M gives a ~15 GB peak indexer transient vs ~60 GB at 4096 (roughly
`14 B × chunk × prefix`). **Chunk size is a memory control, not a throughput one.**

### 6.5 The KV pool must be read from the log, not computed

Budget is `MemAvailable_after_weights − 0.05 × MemAvailable_before_weights − 0.1 GB`;
SGLang's "avail mem" on GB10 is literally OS `MemAvailable`, so **page cache at load
time moves it ±0.5 GB between identical boots**. A pin the budget can't cover either
kills the boot or is silently clamped — both observed. Read
`GPU KV cache size` / `DSV4 memory calculation: …` after any change to weights, TP,
or NCCL buffers. **A 1M context *setting* is not a 1M context *capacity*** — read
the granted pool and divide (bot-lab-21's 1M row is 3.41M tokens = 3.4 concurrent
full-length requests).

### 6.6 Load-time memory is separate from steady state

`fastsafetensors` retains ~26.9 GB of staging buffers (Qwen3.8: 47.54 GB available
vs 20.78 GB), fatal against V4.1-Flash TP=4's ~32 GB headroom. Its
`fastsafetensors_weights_iterator()` also derives its CUDA device from the **global**
process-group rank (`weight_utils.py:1152`), so TP=2 at one GPU/node asks for
`cuda:1` → `invalid device ordinal` (upstream #29272, open). Any TP=2 Spark recipe
using it needs a patch, full stop. We do not use it.

### 6.7 Boot-log checklist (in order), and boot time

1. The mod installed 14 files and asserted `DSV41_ENGRAM_DISK` **and**
   `DSV41_DRAFT_VIRTUAL_HEADS` — if the log does not say both readers are present,
   **stop**.
2. `Engram DISK mode … rows [start,end)` per rank must **DIFFER per rank**;
   identical ranges means staging is wrong and lookups are wrong. (6 hash columns at
   TP=4, 8 at TP=3, 4 at TP=6.)
3. `GPU KV cache size` token count (expect ~3.3M at 300K on the tightest rank;
   far less means KV accounting is off — §6.5 trap).
4. Resolved backends in the startup log, not assumed. On a DSpark arm, the
   drafter must load (`DSpark draft model loaded`), capture
   (`Capturing dspark CUDA graphs`), and log a **Mean acceptance length > 1** on
   `Decode batch` lines — a boot that serves but accepts nothing is the
   EAGLE-on-DSpark-head failure mode, not a win (§10 E7/E8).
5. Accept length on `Decode batch` lines. **A DSpark number without an accept
   length is not a number.**
6. `free -h` per rank while serving (upstream runs 7–12 GiB free on the wide ranks).

**Boot time is ~12–13 minutes** (8 min to read the 460 GB checkpoint, then draft
weights, KV pool, CUDA-graph capture). `readiness.port_timeout_s: 7200` /
`health_timeout_s: 1800` are not paranoia — and the SGLang lane additionally found
`--watchdog-timeout 300` too short for a 167 GB load (raise to 3600).

---

## 7. The EXL3 / vLLM lane — what we measured

All five recipes serve. Engram rows are read from the checkpoint files on
node-local disk; node-local rows are a throughput follow-up only, correctness
unaffected.

> **§§7.1–7.5 below predate the 2026-09-27/28 `max_num_seqs=16` / `gmu 0.85`
> retune** and quote the gmu-0.80 KV pools and 8-seq throughput. They remain
> valid as the *history* and the TPs' mechanism, but for shipped numbers read
> **§7.12** and the current `recipes/README.md` table. Their KV figures are
> superseded (e.g. TP=4 300K 3.88M → 5.20M); their fingerprints of the arms
> (mod gates, Engram rows, drafter, o_groups) still hold.

### 7.1 TP=4 (300K) — `…-exl3-tp4-vllm`

Image `exl3a`, checkpoint distributed to each node before boot (the HF cache is
per-node), 4 nodes as one TP=4 group, boot-to-ready ≈ 13 min.
`Resolved architecture: DeepseekV41ForCausalLM`,
`quantization=exl3` auto-detected, `Engram DISK rows staged … heads [0, 6) of 24`,
`Capturing dspark CUDA graphs (FULL): 8/8`.

| measured here | value | upstream ref |
|:--|:--|:--|
| `GPU KV cache size` (300K, gmu 0.80) | **3,879,721 tok** (12.93×) | 3,304,863 (bot-lab-21) |
| Available KV memory | 31.82 GiB | 15.5 GiB wide ranks |
| weights + non-torch / rank | 60.6 GiB | 56.6–68.9 |
| free while serving, ranks 0–3 | 29 / 19 / 18 / 31 GiB | 7–24 |
| C1 / C4 / C8 (cold first boot) | **36.4 / 58.0 / 76.1 t/s** | 41.6–57.1 / 106.7–142.6 |
| DSpark mean acceptance length | 2.40–2.64 | ~2.6 |
| correctness | `27*43 → 1161`; planets distinct | — |

**Warm vs cold.** A second boot (`.30`–`.33`, KV 3,861,339) measured **37.5 / 61.9 /
88.5**; a third (C4 84.3, C8 94.0; its C1 0.6 is a cold-first-request artifact)
shows warm run-to-run spread. The README ships the warm figure; §7.7's sweep ships
its own. Both are real; they differ by warm-up only. **Label which regime a number
came from before comparing it to anything.** Our C4/C8 are below upstream's
repeat-run aggregates because ours is a cold comparison — their high numbers are
~90-minute warm repeats, and a fresh boot is consistently slower.

### 7.2 TP=4 at 1M — `…-exl3-tp4-1m-vllm` (the 1M deliverable)

Identical to ¶7.1 except `--max-model-len 1000000` and the `CUDA_EXL3_MODEL_PATH`
prefix. `GPU KV cache size: 4,200,885 tokens` (4.20× at 1M), available KV 28.35 GiB,
weights 56.61 GiB/rank, TTR 752 s. **Needle retrieval correct at 199K and 799K**
("zorbulon" both times); prefill 693.9 t/s @199K, **745.9 t/s @799K** (matches
upstream's ~673–1449 t/s band). `max_model_len: 1000000` confirmed on `/v1/models`.
799K is the single largest context this project has served. **Not shipped:** a
KV-grouping patch (`DSV41_KV_GROUPING=fine`) takes the pool to 5.57M (+63%) for
−6% single-stream / −8% C6 — a further patch, not part of the mod.

### 7.3 TP=3 — `…-exl3-tp3-vllm`

**DSpark is ON since 2026-09-27 (k=3).** Until then this arm was no-spec: the
DSpark drafter's own 64 heads fail `SpeculativeConfig` validation at TP=3
(`vllm/config/model.py:1420`, `64 % 3 = 1`), and its 128 experts don't divide by
3 either. The root cause and fix are characterized in `DSPARK-TP3-STUDY.md`:
dict `hf_overrides` are **target-only** (`compose_draft_hf_overrides`,
`speculative.py:1044-1067`), so the drafter never saw the 72/9 virtual-heads
declaration. The mod's new `config_speculative.py` propagates that dict to the
draft config; the drafter then reuses the target's modded attention and pads
exactly like the main model, while the mod's `dsv4_nvidia_model.py` already
relaxes the 128-expert assert on the no-EP path. Upstream reached the same
end-state with a 72-head `config.json` copy (`exl3tp3a11`, measured).

Two faults fixed before the no-spec arm booted: **`hf-overrides` must be flat,
not nested under `text_config`** (`DeepseekV41Config` flattens `text_config`
before vLLM applies overrides — proved device-free both ways: nested → 64 heads
IGNORED, flat → 72 applied), and DSpark had to come off (no longer true). (The
kwarg is `hf_overrides_kw`, not `hf_overrides` — passing the latter is a
`TypeError` "multiple values".)

Measured (**DSpark k=3**, 2026-09-27, `ds4tp3` = .32/.33/.34, booted before the
recipe edit on `-o` overrides): KV **1,896,721 tokens**, C1 **34.3** / C4 **59.1** /
**C8 77.7 t/s**, DSpark mean acceptance length **2.40–2.50**. That is **+117% C1,
+25% C4, +12% C8** over the no-spec arm below, on the same node count — DSpark
turns TP=3 from the slowest single-stream topology into a competitive one. Prior
**no-spec** measurement (2026-09-24): KV 2,798,624 tokens, C1 15.8 / C4 47.1 /
C8 69.1; that arm's C8 69.1 was within 9% of TP=4 **on one fewer node**. No-spec
context was 1,995,725 tokens vs 678,950 with DSpark (upstream). Raw:
`.scratch/ds4/dspark_tp36/live/`. Every §7.3 boot gate held (draft `97 params`,
dspark graphs `8/8`, Engram rows differ per rank).

### 7.4 TP=6 — `…-exl3-tp6-vllm` (fastest topology)

**It boots first try, no `/128` MoE error:** `moe_intermediate_size 2304/6 = 384 =
128×3`, so the FlashInfer-Cutlass MXFP4 MoE accepts TP=6 — the *same* check that
killed SGLang TP=4 (576). `world_size=6`, weights 41.98 GiB/rank (lightest of any
split), engine init 152 s.

**DSpark is ON and measured since 2026-09-27 (k=3)**, same mechanism as TP=3 (the
mod applies the 96/12 declaration to the drafter). **This was the first DSpark boot
at TP=6 on any cluster.** Measured: KV **12,006,501 tokens**, C1 **44.5** /
C4 **72.5** / **C8 115.3 t/s**, DSpark mean acceptance length **2.43–2.50** — above
its own no-spec baseline at *every* concurrency (see the table). The two
pure-padding ranks cost nothing at steady state. Raw:
`.scratch/ds4/dspark_tp36/live/`. Every §7.3 boot gate held.

| | TP=4 (DSpark) | TP=3 (DSpark k=3) | **TP=6 (DSpark k=3)** |
|:--|--:|--:|--:|
| `GPU KV cache size` | 3,879,721 | 1,896,721 | **12,006,501** |
| Available KV | 31.82 GiB | — | **47.5 GiB** |
| C1 / C4 / C8 agg | 36.4 / 58.0 / 76.1 | 34.3 / 59.1 / 77.7 | 44.5 / 72.5 / **115.3** |
| accept length | 2.40–2.64 | 2.40–2.50 | 2.43–2.50 |

Prior **no-spec** baselines (2026-09-24): TP=3 KV 2,798,624 / 15.8 / 47.1 / 69.1;
TP=6 KV 12,783,985 / 29.4 / 63.8 / 108.0 (weights 41.98 GiB/rank, quality 19/19
easy + 17/18 hard on both). DSpark costs TP=3 ~32% of its KV pool (2.80M→1.90M)
and TP=6 only ~6% (12.78M→12.01M).

Three findings: (1) **quality is unaffected by the two pure-padding ranks** — 8
groups pad to 12, only 8 are real, ranks 4–5 run attention that contributes nothing,
yet the battery is identical to TP=4/TP=3; (2) **the padding tax is
concurrency-dependent** — no-spec C1 (29.4) was *below* TP=4's 36.4, but by C8
no-spec TP=6 was 108 vs 76.1/69.1, so the even 128-aligned expert split wins once
there is batch; **TP=6 is a throughput topology, not a latency one**. Adding DSpark
k=3 removed the C1 weakness entirely (44.5, above TP=4's 36.4); (3) **context is
3.3× the TP=4 pool for free** (KV is replicated, per-rank weights smallest).
Caveats: prefill 553 t/s @35K vs TP=4's 1128 @191K is a *depth* difference; one
no-spec boot, one DSpark boot. Engram `heads [0,4) of 24`. Raw:
`.scratch/ds4/{quality_tp6.json, tp6conc.out, tp6conc2.out}` plus the DSpark arm in
`.scratch/ds4/dspark_tp36/live/`.

### 7.5 TP=6 at 1M — `…-exl3-tp6-1m-vllm`

KV pool **14,038,103 tokens** (14.04× at 1M) — the largest pool measured here; needle
correct at **199K and 799K**; prefill 1768 t/s @199K, 864 t/s @799K. A ~1.067M-token
prompt correctly returns HTTP **400** (over the ceiling — the limit working, not a
bug). The TP=6 300K recipe with `max_model_len: 1000000` and nothing else changed
(guard-enforced). Guards caught two real omissions in the first draft: a missing
`mods:` block (the Engram stays in RAM and the boot OOMs) and the no-spec
classification. **2026-09-27:** the no-spec classification is retired — this
sibling ships DSpark k=3 like its 300K twin (identical except context,
guard-enforced). **Both TP=6 arms booted with DSpark on 2026-09-27**; this 1M arm
was booted **exactly as shipped** (no `-o`) after the edit: KV **13,054,046 tokens**
(no-spec 14,038,103 → −7%), accept length **2.37–2.44**, C1 35.3 / C8 **118.4 t/s**
(the largest C8 measured here), `max_model_len 1000000` on `/v1/models`, quality
correct. Raw: `.scratch/ds4/dspark_tp36/live/`.

### 7.6 Quality — our own held-out battery (E5, 2026-09-24)

Every quality number in §2.5 was the checkpoint author's, in-domain. We built two
stdlib batteries in `.scratch/ds4/` — `quality_battery.py` (19 easy, exact-match)
and `quality_hard.py` (18 hard, built to fail so a non-perfect score is informative).
Deterministic (`temperature 0`), unique prompts, raw replies JSON-dumped.

| battery | score | notes |
|:--|:--|:--|
| easy (19) | **19/19 = 100%** | ceiling — proves "not catastrophically broken", ranks nothing |
| hard (18) | **17/18 = 94.4%**, stable over 3 runs | the 1 failure is character reversal |

The single failure: `hard-rev` asks to print `sparkrun` reversed; the model returns
a transposition (`nurknaps`/`nrukreps`/`nurcraps`) instead of `nurkraps`. It reverses
`hello`, `world`, `abcdef`, `machine`, `deepseek`, `banana`, `elephant`, `xylophone`,
`zorbulon`, `blorptastic`, a 28-char word, and `180` **correctly** — the weakness is
narrow (uncommon words) and reproducible. **We have NOT shown EXL3 causes it**: common
and long words pass and we have no release-checkpoint comparator. Honest label:
"a limitation of this checkpoint on this task", **not** a quantization defect.
It is also a determinism caution — at `temperature 0` the reversal differs
run-to-run, the "V4.1 is not bitwise stable across batch composition" property (§9).

**Reading for ship decisions:** the EXL3 3.5 bpw checkpoint is **safe to ship as the
default-quality lane** for reasoning, code, arithmetic, instruction-following and
recall (100%/94% here), with the caveat that it is weak on explicit
character-manipulation of rare tokens. Nothing in this battery shows quality damage
from the 3.5 bpw experts.

**DSpark is quality-neutral (measured):** re-ran the battery on TP=3 (no-spec, 2
repeats) vs TP=4 (DSpark k=5) — identical scores, same failure, and **35 of 37
first-repeat replies byte-identical**; the two differences are a comma in prose and
the flaky reversal. So DSpark changes greedy output on 2/37 tasks, both
cosmetically. Per-task replies: `.scratch/ds4/quality_tool_check.json` (TP=4),
`.scratch/ds4/quality_tp3.json` (TP=3).

### 7.7 DSpark draft-depth (k) sweep — the optimum is k≈2–3, not the shipped k=5 (2026-09-26)

**Five k values, 13 boots, unique prompts, non-streaming; n counts boots** (each
boot = 3 intra-boot repeats, median taken; GB10 inter-boot scatter is 7–25%, so
single boots rank nothing).

| k | boots | C1 agg | C4 agg | C8 agg | acc_len |
|--:|--:|--:|--:|--:|--:|
| 1 | 2 | 33.3 | 73.3 | **107.3** | 1.60 |
| **2** | 2 | **35.5** | **75.0** | 101.8 | 1.98 |
| **3** | 3 | **36.7** | 72.8 | 96.1 | 2.25 |
| 4 | 2 | 34.6 | 64.3 | 86.7 | — |
| 5 (shipped) | 4 | 33.3 | 62.1 | 84.4 | 2.44 |

**Every k in {1,2,3} beats the shipped k=5 at every concurrency ≥4.** The optimum
moves with concurrency and is always ≤3: C1 → k=3 (best C1 measured on any k),
C4 → k=2, C8 → k=1 (107.3, **+27% over k=5's 84.4**), monotone k=1>2>3>4>5. So the
shipped default was **at or near the worst of the five** at every concurrency.

**Mechanism (refutes §4.1's interior peak).** Per-position acceptance:
`k=5: 0.66 0.40 0.22 0.12 0.05`, `k=3: 0.66 0.39 0.21`, `k=2: 0.69 0.40`,
`k=1: 0.61`. Slots 4–5 of k=5 accept at 12%/5% yet each costs a verify pass over
the routed experts, so k=5 accepts the most tokens/step (2.44) and is still the
slowest. §4.1 predicted the peak at k=4; the data puts it at k=3 (C1) sliding to k=1
(C8). **Why the optimum slides down with concurrency (LIKELY):** at low concurrency
the step is latency-bound, so amortising a fixed step cost over more accepted tokens
(higher k) pays; at high concurrency the batched step is bandwidth-bound on expert
bytes, so a wider verify window multiplies the dominant term — §4.1's byte-inflation
argument *does* bind once there is a batch. That reconciles the two regimes and is
why vLLM ships *adaptive* verification.

**`k=6` is illegal** — vLLM rejects it: `num_speculative_tokens:6 must be divisible
by n_predict=5`. The DSpark drafter fixes `n_predict=5`, so legal k is **≤5 or a
multiple of 5** — why every public DSpark sweep shows {2,3,5,7} and never 4 or 6.
Our k=4 boots are the only k=4 points anyone has on this model.

**Pre-registered decision rule (written before replication,
`.scratch/ds4/ksweep/PREREGISTRATION.md`), which fired:** adopt k over k=5 iff
`C8 ratio ≥ 1.03` AND `C1 ratio ≥ 0.97`. k=3 fired (C8 1.139, C1 1.100), k=2 (1.207,
1.063), k=1 (1.272, 0.999 — flat C1, the throughput choice).

**Shipped:** `num_speculative_tokens: 3` on all five EXL3 recipes — best-C1 point,
loses nothing at C4 vs k=2, beats k=5 by ~11% at C4 and ~14% at C8 (the most
conservative departure that captures the whole win). TP=3 and TP=6 gained it on
2026-09-27 (§7.3/§7.4, §10 E7); **both those arms booted and measured 2026-09-27**
(TP=3 C1 34.3, TP=6 C1 44.5). The k-sweep below was TP=4-only, so the TP=3/TP=6
k=3 choice is a port of the optimum, now confirmed by their own boots. Capture
ladders rebuilt for k=3 (`[3,4,6,8,9,12,15,16,18,20,21,24,28,32]`). **Offer k=1 as a
documented throughput arm** for batch-serving
(`-o speculative_config='{…,"num_speculative_tokens":1,…}'`), +27% at C8. **Do not
ship k=4 or k=5.** The capture ladder must change with k (`k·n` and `(k+1)·n` up to
`8·(k+1)`), so a k change is not a one-line edit (guard: `KCaptureSizes`). Adaptive
verification MUST stay off (padded spec batches hang SM120 sparse MLA, FlashInfer #5015).

**Caveats:** one content mix (blended technical prose) — the optimum moves with
content, so a code-heavy mix may shift it up. Weight load is disk-bound and varied
710–1320 s; C8 is the least-scattered cell and was the pre-registered primary
metric. The k=1 finding is a throughput topology, not a universal win (level with
k=5 at C1).

**External triangulation (not our measurement):** tonyd2wild measured GB10 DSpark
tokens/step rising 3.27→4.06→4.19 at k=3/5/7 but with the marginal gain collapsing
(+24% for 3→5, +3.3% for 5→7 at +33% verify width) and **run k=3 in production** —
consistent with our C1 result. Cohere measured that the marginal verify token is not
a full expert pass. Artifacts: `.scratch/ds4/ksweep/` (`ALL_BOOTS.json`, `table.py`,
`PREREGISTRATION.md`, `RESEARCH-external.md`, per-arm logs).

### 7.8 The `drop-caches` mod: not useful here, and not a mitigation (2026-09-25 / 2026-09-27)

All five recipes list `@eugr/mods/drop-caches`. **It does nothing, in
every launch mode, for two independent reasons, both reproduced:**
1. **Rootless (sparkrun default) blocks the write.** `launcher.py:837` defaults
   `rootless=True` → `privileged: false` + `no-new-privileges`; `/proc/sys` is
   mounted `ro`, so `echo 3 > /proc/sys/vm/drop_caches` returns "Read-only file
   system" (rc=2). The loop process still starts — the trap.
2. **The mod has a redirection-order bug**, so it is inert even privileged:
   `echo 3 > /proc/sys/vm/drop_caches >> /tmp/drop_caches.log 2>&1`. Bash applies
   redirects left-to-right and the **last wins**, so `3` is written to the *log* and
   `drop_caches` gets nothing. Reproduced with a stand-in target (target 0 bytes,
   log "3") and under `--rootful` (write rc=0, log created, `drop_caches` still
   never written) — **`--rootful` does not fix it.**

**A real cache drop must be host-level** (`sync; echo 3 > /proc/sys/vm/drop_caches`
over ssh on each node). Two transferable rules: a mod's effect must be verified at
the point of use, not by the presence of its process; and when a shell line writes
to a file AND redirects output, check which redirect wins (`> target >> log` silently
voids the `> target`).

**2026-09-27 — is `@littlecedar/mods/drop-caches` useful for these recipes? No,
so the recipes are UNCHANGED.** The objective asked to switch from
`@eugr/mods/drop-caches` *if* the littlecedar mod mitigates the cache growth. It
does not. **The reference itself is fine** — the mod is pushed (`mods/drop-caches/run.sh`
in the littlecedar `origin/main`) and the canonical head resolves it (registry
`trusted: true`, `sparkrun registry list` row `Trusted=yes`, and
`~/.cache/sparkrun/registries/littlecedar/mods/drop-caches/run.sh` present, VERIFIED
on the canonical head 2026-09-27). So the decision is deliberate, not a resolution
failure, for three reasons:

1. **The replacement would abort every shipped launch.** sparkrun launches these
   recipes **rootless** (`api/_run.py:474` sets `rootless = not options.rootful`;
   the recipe passes no `--rootful`), and `DockerExecutor.apply_runtime_adjustments`
   then sets `privileged: false` (`orchestration/executors/docker.py:311-313`).
   `mods/drop-caches` is **fail-closed**: with `/proc/sys` mounted `ro` its write
   returns non-zero → `die` → non-zero `docker exec`, which `run_pre_exec` turns
   into a hard `RuntimeError` ("pre_exec[1] failed", `orchestration/hooks.py:411`).
   Sharing one `pre_exec` chain across all nodes means **one refusal kills the whole
   launch**. eugr's mod is a silent no-op here; the littlecedar mod is a launch
   failure. Parity wants the no-op.
2. **A recipe cannot authorize it, and trust is a local decision.** `privileged`
   is trust-gated (`core/launcher.py:157` `_TRUST_GATED_EXECUTOR_KEYS`), and a
   registry is untrusted unless the user opts in (`registries.yaml`), so an
   in-recipe `executor_config: {privileged: true}` fails closed for an untrusted
   recipe. **Even with the registry trusted, we deliberately do not set it**: the
   mod has nothing to drop at launch (reason 3), and forcing every launch
   `--privileged` is a sandbox change and a standing privilege grant bought for a
   no-op — the opposite of what parity wants.
3. **A drop at launch, even if it ran, would buy nothing measured.** The cache
   *does* grow hugely at launch — ~45–58 GiB/node from the weight load (§7.8.1) —
   and it is clean/reclaimable, but a **load-window drop bought +0.9% KV (noise)
   and less available KV** in a controlled A/B (§7.8.1). The serving-time Engram
   contribution is small and a between-legs bench concern (§11). So a recipe mod
   here is a sandbox change for a measured non-effect, not a mitigation.

**The mod itself is mechanically correct** — one stdout redirect, and the write is
verified at the point of use and made to fail closed — unlike eugr's, which writes
`3` to its log. So it is the right tool for an **explicit** privileged drop
(`sparkrun run … --rootful`, or a host `sync; echo 3 > /proc/sys/vm/drop_caches`
over ssh); it is simply **not a drop-in recipe mod** for the default launch, and
NOT a mitigation for anything the shipped recipes see. "The mod works" ≠ "the mod
is useful in this recipe."

### 7.8.1 Live boots: where the host memory actually goes, and a load-flusher that is NOT worth it (2026-09-27)

Two live boots of `…-exl3-tp4-vllm` on `.32`–`.35` (fresh, all four idle),
measuring host `Cached`/`MemFree`/`MemAvailable` through load and serving. This
section **corrects a claim I made earlier in this session** (that the Engram row
reads, not the weight load, dominate the cache) and **refutes** the
"unconditional load flusher → +55% KV" lever carried in `TUNING_BACKLOG.md` B1.3.

**1. The weight load is what fills the cache, not serving.** Boot A (no flusher),
`Cached` per node: **1.5 → 28–39 → 45–58 GiB in the first ~2.5 min**, with
`MemFree` collapsing to **~1 GiB** while `MemAvailable` stayed at 41–54 GiB. There
is **no plateau** — it kept growing until the instantaneous pre-KV read. That is
the 460 GB checkpoint streaming through the 95 GB Engram shards' mmaps and the
checkpoint shard pages the loader retains; **Engram row reads cannot be the cause here
because no request had been served yet.** After readiness the cache *fell* to a
steady ~14–27 GiB (`MemFree` ~2–6 GiB).

**2. Serving adds little.** 30 short + 4 long (~95 K prompt-token) requests moved
`Cached` by **≈0** (`.32/.35` even fell 2 GiB; the workers rose ~0.1 GiB); the
`MemFree` dip to ~2 GiB was activation footprint, not cache. The reader already
issues `POSIX_FADV_RANDOM` (`mount-dsv41-exl3-patches/files/engram.py:768`), and a
few hundred MB of rows is small against ~24 GiB of resident load cache. **Engram
rows are a prefill-scale follow-up, not the launch-time memory story.**

**3. The cache is reclaimable and is exactly the budget.** A host `drop_caches`
at serving-time jumped `MemFree` **2–6 → 15–28 GiB/node** (~24–28 GiB reclaimable),
i.e. the resident checkpoint pages are clean and freeable. So the *mechanism* the
flusher targets is real.

**4. But the load-window flusher does NOT buy KV — the lever is refuted here.**
Boot B ran the same recipe with a host-side flusher dropping clean page cache
whenever `MemFree < 8 GiB` (the `[B1.3]`/memfree-flusher design), 18 drops across
the load:

| boot | `Available KV cache memory` | `GPU KV cache size` |
|:--|--:|--:|
| A (no flusher) | **32.2 GiB** | **3,973,172 tok** |
| B (load flusher) | 29.32 GiB | 4,008,344 tok |

**+0.9% tokens — inside the +6% boot-to-boot spread (§6.5, §7.1) — and *less*
available KV.** The B1.3 "+55% pool" did not reproduce on this stack. Likely why
(`SPECULATIVE`): the load is disk/syscall-bound, so evicting cache does not speed
it, and `MemAvailable` was already ≥41 GiB throughout load, so the allocator was
never actually starved during the KV sizing. **Decision: do not ship a load-window
flusher mod, and treat B1.3 as unconfirmed.** The ingredients that *did* hold:
post-load cache is ~24 GiB/node of clean, reclaimable checkpoint pages, and the
only validated drop action is **host-level** (the mod path is §7.8).

**Machine-checked (no boot): the reader can be made cache-neutral.** Against the
real `model-00047` on node-local disk, over random 64 KiB reads:
buffered → `Cached` **+0.50 GiB** (all of it); `fadvise(DONTNEED)` per read →
**+0.01 GiB**; `O_DIRECT` → **+0.00 GiB**. Throughput was statistically identical
(100–109 MiB/s). So bounding the reader works and costs nothing measurable
at this scale — but given finding (2) it would bound a small serving-time delta,
while the large load-time cache remains (and is proven not to move KV). The
reader change is therefore **low-priority**; the load cache is the real subject.

**Implemented and BOOTED (2026-09-27): `mods/bound-engram-cache`** — a post-patch,
opt-in mod that adds `POSIX_FADV_DONTNEED` (once per gathered batch) to the installed
Engram reader. Fail-closed (md5-pinned patcher, `--check` before write, one backup,
marker-idempotent). Live-verified on a one-off variant recipe (`.32`–`.35`): mod
applied, 48/48 weights, ready, KV 4.11M vs 3.97M baseline (noise), `27*43→1161`,
~33 t/s C1. **Listed on all five EXL3 recipes** (after `mount-dsv41-exl3-patches`;
ordering guarded by `test_bound_engram_cache_after_patch_mod`) even though it buys no
KV — the user asked for it wired in. Guards in `tests/test_bound_engram_cache.py`
(negative controls included).

**Recommendation and action plan: `MEMORY-RECLAIM-PLAN.md` (same directory).** The
`instanttensor` question is **CLOSED — incompatible with this checkpoint** (§7.9);
cache drops are not a mitigation; **no recipe change**.

### 7.9 The InstantTensor load-path change was tried and REVERTED (2026-09-25)

All five recipes were briefly switched to `--load-format instanttensor` plus the
vendored `@littlecedar/mods/instanttensor-hybrid-draft-loader`. The TP=6 1M boot
with both **crashed all six nodes**; reverted in `f274545` to the last known-good
lane (`63b1e49`). The recipes load weights the way they did before (no
`--load-format`, no hybrid-draft mod).

Mechanism vs safety (both facts true): `instanttensor` IS a valid, installed, wired
vLLM load-format in the `exl3a` image (`LoadFormats`, same `DefaultModelLoader` as
`auto`/`hf`/`safetensors`), and **the mod DOES apply to the image's `get_model()`
byte-for-byte** — but **neither was ever booted**, and static validity was not
evidence of safety. A crash on **all six nodes at once** is a fleet-level failure
mode, harsher than a single-node OOM. **Do not re-apply without booting a single
node first.**

Post-mortem questions (`.swival/trash/instanttensor-reverted-2026-09-25/`, and
recoverable from `7de6c41`; reverted commits `0cc6285`, `7de6c41`): (1) did the
crash need the mod, the flag, or both — boot `--load-format instanttensor` alone on
a single node; (2) does the mod's `get_model()` patch interact with multi-node
TP/`torch.distributed` init; (3) does InstantTensor's memory accounting
(`INSTANTTENSOR_MAX_FREE_MEM_USAGE`, default 0.5) collide with the GB10
unified-memory pool. **Process lesson: for a fleet-wide change, a single-node smoke
boot must precede the full-fleet recipe.**

**ANSWERED 2026-09-27 — it is the FLAG, and the mechanism is fatal: InstantTensor
sizes a GPU buffer to the single largest tensor, which here is a 91.56 GiB Engram
table.** Reproduced **boot-free on one node** (no recipe, no TP) by opening the real
shards with the image's `instanttensor` 0.1.9:
- The checkpoint's largest tensor is `layers.14.engram.embed.weight` = **91.56 GiB**
  (measured from the safetensors headers; 6 tensors >1 GiB, 2 >8 GiB).
- `safe_open` sets its **GPU** buffer to the largest tensor and **refuses to go
  below it** (`instanttensor/_impl.py:593-620`, `_determine_buffer_size`; the buffer
  is the `GPU buffer` of `:331`, passed to native `open()` at `:664`). Observed:
  `buffer=91.55 GiB` for one Engram shard, **`183.11 GiB` for all 48 shards**
  (default overlap heuristic `:270-301`) — larger than a 128 GB GB10 node.
- Then the native loader **aborts**: `Failed to submit aio: Invalid argument` →
  `Loader thread exception: std::exception` → SIGABRT, on **both** a 4.0 GiB-buffer
  shard and the 91.55 GiB one. **Mechanism for the six-node crash (LIKELY, not
  boot-verified):** every rank opens a ≥91.56 GiB GPU buffer that cannot coexist with
  the weights — fatal independent of TP or the mod. The single-node abort itself is
  VERIFIED.
- **Answer to (1): the flag. The vendored hybrid-draft mod was a documented NO-OP**
  (its `auto` mode only flips for a same-path/same-revision draft; the DSpark drafter
  is a separate path), so it is neither necessary nor sufficient. (3) is moot: the
  collision is the buffer, not `INSTANTTENSOR_MAX_FREE_MEM_USAGE`.
- **Verdict: InstantTensor is incompatible with an Engram-class checkpoint on GB10
  and there is no version of this lever to ship. Do not re-apply.** See
  `MEMORY-RECLAIM-PLAN.md` §6 for the repro command.

### 7.10 The `mxfp8_gemm` autotuner warning — investigated, NOT worth fixing (negative)

Every TP=6 boot logged 8–9 instances of `[AutoTuner]: No tuned config covers
mxfp8_gemm input_shapes=((1, 1280), …); falling back to runner=CutlassMxfp8GemmRunner
tactic=-1`. Mechanism: FlashInfer's `AutoTuner` warns when a runtime shape has no
profiled tactic and falls back to `tactic=-1`, a *valid heuristic*
(`flashinfer/fused_moe/utils.py:195`). **Performance-only.** Correlation: the two
TP=4 recipes (`max_num_batched_tokens: 8192`) had **0** misses; TP=3 and both TP=6
recipes (`4096`) had 6–9. One test boot of the 1M recipe at mnbt 8192 took misses to
**0** but bought nothing: C1 unchanged, C8 within spread, and the **KV pool shrank
11% (14.04M → 12.51M)**. **Decision: recipes unchanged.** The warning reads like a
perf cliff (the code says "to avoid this perf cliff") and is not one — the target is
a small dense GEMM at M≈1–32 where tactic barely moves the step. Do not "fix" this
into an 11% KV loss.

### 7.11 Stale `metadata.description` prose (fixed, guarded)

The recipe *descriptions* had drifted from their own bodies in ways no flag guard
could see: TP=3 advertised "DSpark k=5" while shipping **no** `--speculative-config`;
three recipes still said "UNBOOTED" after they had booted. Fixed, and guarded by
`test_description_matches_spec_config` (a no-spec arm may not claim a DSpark k
value, a DSpark arm may not deny it, no recipe may say "UNBOOTED"). Lesson: when a
recipe body changes, the description is a **second artifact that does not update
itself**.

### 7.12 The `max_num_seqs=16` / `gmu 0.85` retune (2026-09-27/28)

The four TP=4/TP=6 recipes shipped `max_num_seqs: 8` / `gpu_memory_utilization:
0.80`. Retuned to **16** and **0.85** with the CUDA-graph ladder rebuilt to reach
`16·(k+1) = 64`; every arm was then **booted exactly as shipped** and measured.
TP=3 is unchanged (8 / 0.80) — outside the retune's scope.

**Why 0.85, and why 16, from the boot log — not arithmetic.** vLLM prints the real
per-rank budget: `Free memory on device (112.x/121.69 GiB) … Desired GPU memory
utilization is (gmu, gmu·121.69) … Actual usage is W for consumed memory (weights
+ non-torch), A for peak activation, Z for CUDAGraph memory … Current kv cache
memory in use is K`. The measured per-rank footprint is small on every TP=4/TP=6
arm (W ≈ 47–64 GiB), so 0.85 (103.44 GiB promised) leaves ~18 GiB of the 121.69 GiB
device beneath the promise — and the TP=3 arm already consumed ~94 GiB of 121.69 at
0.80 and boots. `max_num_seqs` bounds resident slot objects; **max concurrency is
pool/ctx** (§6.5), so on TP=4 1M (pool only ~5.75× a full-1M request) the 16 slots
queue rather than run 16-wide, while TP=4 300K (17.34×), TP=6 300K (45.31×) and
TP=6 1M (15.03×) run 16 concurrent requests outright.

| arm | weights+non-torch | act | graph | **KV GiB** | **KV tokens** | conc | was (0.80) | C1/C4/C8/C16 t/s |
|:--|--:|--:|--:|--:|--:|--:|--:|:--|
| TP=4 300K | 59.54 | 5.83 | 1.0 | **38.06** | **5,203,288** | 17.34× | 3,879,721 | 38.8 / 66.3 / 88.5 / **122.0** |
| TP=4 1M | 63.75 | 5.84 | 1.11 | **33.84** | **5,750,109** | 5.75× | 4,200,885 | 40.7 / 65.4 / 84.5 / **121.3** |
| TP=6 300K | 47.17 | 3.49 | 1.21 | **52.78** | **13,594,187** | 45.31× | 12,006,501 | 40.0 / 78.0 / 107.9 / **151.1** |
| TP=6 1M | 50.18 | 3.85 | 1.13 | **49.41** | **15,034,010** | 15.03× | 13,054,046 | 43.4 / 72.7 / 110.2 / **149.1** |

Pool rose (+13 % to +37 %) on every arm and **C16 is newly reachable** (the old
8-seq cap queued it). Bench: one cold boot per arm, distinct prompts, greedy,
non-streaming (`usage.completion_tokens`/elapsed — §11). Single boots rank
nothing (7–25 % inter-boot scatter); the C16 column is the least-scattered,
capacity-bound cell and the one to trust for the retune's effect. **These rows
come from a different harness than the §7.7 sweep (36.7/72.8/96.1 at k=5→3), so
do not compare across harnesses.** Quality smoke (`27*43→1161`, planets) correct
on all four; needle at **799K prompt tokens** correct on both 1M arms (TP=4 1M
639 t/s, TP=6 1M 579 t/s prefill).

**Guards updated with the retune:** `test_graph_capture_covers_max_seqs` and the
`KCaptureSizes` control derive from the recipe's own `max_num_seqs`, so they need
no literal; `test_control_truncated_capture_sizes` now mutates the 64-topped
ladder, and `test_control_unconsumed_default` was **re-anchored on
`tensor_parallel: 4`** because its old `gpu_memory_utilization: 0.80` anchor was a
tunable value that the retune broke — the control's own comment had warned
against exactly that.

**Process note (a false alarm recorded on purpose).** A ~799K prefill at ~600 t/s
takes **20–23 min**, and killing the client does **not** cancel the in-flight
prefill: the worker keeps burning CPU to finish it (`/proc/<worker>/stat` ticks
climbing). A 20–30 s probe therefore "times out" on a *busy* engine, which twice
read as a wedge before the worker cpu ticks were checked. On a GB10 deep-prefill
arm, never call a state a "hang" from a single timed-out probe (§11) — check
worker progress first.

### 7.13 The SGLang lane — knapcio's native-checkpoint overlay (2026-10-02)

A **second engine lane**, not a replacement for the EXL3/vLLM path. Source:
`knapcio/DeepSeek-V4.1-Flash-4x-DGX-Spark-TP4` @ `58f2321` (downstream of
MiaAI-Lab's recipe). Recipe `deepseek-v4.1-flash-knapcio-tp4-1m-sglang.yaml`, mod
`mods/dsv41-sglang-overlay/`, full write-up `KNAPCIO-SGLANG-INTEGRATION.md`.

**It boots and serves on our four free Sparks** (`.32`–`.35`), TP=4, EP=1,
native MXFP4/F8 checkpoint, Engram on node-local NVMe, DSpark k=5, 1M context,
RoCEnante RDMA. Image `dsv41-4x-spark:canary-roce` (33.5 GB, node-local, built
from the repo's `Dockerfile.canary-roce`; ~10 min/node incl. the in-image tests).

**Measured (our bench; boots #5 and #9 agree within 2 %):**

| t/s aggregate | C1 | C4 | C8 | C16 |
|:--|--:|--:|--:|--:|
| this lane, short-prompt harness (RoCEnante ON, verify-all) | **46.5** | **106** | **133** | **193** |
| same, NCCL only (boot #4) | 27.4 | 62.5 | 73.2 | 155.0 |
| `sparkrun benchmark` std profile (pp=2048, 3 runs) | 43.6 | 91.3 | 99.4 | 102.1 |
| shipped EXL3 TP=4 300K (§7.1 warm) | 37.5 | 61.9 | 88.5 | — |
| upstream v2.3 (their fabric/clock) | 89.7 | 165.9 | 244.6 | 357.2 |

The std-profile row is `benchmarking/ds4-sglang-depth0-ladder.yaml`
(`.scratch/ds4/knapcio/bench-sglang-depth0.json`). Its concurrency cells are lower
than the short-prompt row because llama-benchy uses **2048-token** prompts while the
short-prompt harness uses ~17; the two agree at c1. **Quote the ladder with its
prompt length attached.**

**RoCEnante is the single biggest win: 1.70×/1.69×/1.81×/1.23×** over NCCL, far
outside the 7–25 % boot spread. **C1 46.5 beats the shipped vLLM/EXL3 TP=4 lane
(37.5–40.7 warm) on the same four nodes**, at the cost of a node-local image and
~47 GiB/node of packed Engram shards.

**Three findings that are load-bearing and easy to get wrong:**
1. **`EP_SIZE=1`, never 2.** EP=2 loads (clears the MXFP4 `%128` check) but dies at
   the first decode plan: `planned dynamic direct routing is unsupported for this
   launch shape` (E192-N1152). The adapter says so: "the production profile is
   EP_SIZE=1".
2. **The SPS ragged-verify table crashes the Engram path** — upstream's own
   README lists it under "Not used". With a fitted `/state/dspark_sps.json` the
   scheduler enables and the first mixed batch dies with `AssertionError: engram
   target-verify expects one equal block per request, got 84 tokens for 16
   requests of 6`. **Upstream production is verify-all**, so the shipped recipe
   sets no table. (The table needs a dedicated record boot with
   `SGLANG_RAGGED_VERIFY_MODE=static SGLANG_DSPARK_ENABLE_SPS_RECORD=1
   SGLANG_SIMULATE_ACC_LEN=1.0` and `SKIP_SMOKE=1`, and the sweep must be capped
   to the graph tier: `--max-batch-size 16`.)
3. **Sparkrun mechanics:** `distribution_config` is a top-level key (not
   `distribution`). A **vendored** image is pulled by setting
   `containers.enabled: true` and pinning the digest in `container:` (as this
   lane now does); a **node-local** image needs `containers.enabled: false` so
   sparkrun does not try to pull a tag that is not in a registry. The HF cache
   uses the two-level `hub/blobs/<xx>/<sha>` layout so the **whole `hub/` dir**
   must be mounted for `pack_engram.py`.
4. **Portability (2026-10-02): the recipe carries NO host bind mounts.** Every
   non-model, non-image artifact — the per-rank Engram shards, boot.py's
   `launch.json`/`api-key`, the b12x JIT caches — lives under sparkrun's managed
   runtime cache
   (`~/.cache/sparkrun/runtime-cache/sglang/<model_dir>` → `/cache/runtime`),
   which sparkrun creates and chowns per node. `mods/dsv41-sglang-overlay/run.sh`
   creates + `reown`s the subdirs; `launcher.py` is the **only** component that
   learns the rank (sparkrun appends `--node-rank` to every node's serve command;
   the container env has none) and it packs this rank's Engram shards when absent,
   **detached** so a cold boot never exceeds sparkrun's ~150 s head-rendezvous
   wait (first cold boot runs Engram from the checkpoint; next boot is packed).
   `sparkrun recipe validate` no longer reports `non-portable-mount`. `/state`
   is no longer a bind mount — it is `/cache/runtime/state`.
   A mod ref of the form `@littlecedar/mods/…` resolves from the **registry git
   clone**, not the synced working tree, so iterating on a mod needs the
   `~/development` symlink layout + a bare ref (QWEN4-WORK §16); the shipped
   recipe keeps the `@littlecedar/…` form.

**E5 is now CLOSED by this lane.** The release checkpoint scores **17/18 = 94.4 %**
on the hard tier (two runs), the *same* score and the *same* single failure
(`hard-rev`) as the EXL3 lane. So the EXL3 3.5 bpw quantization costs nothing
measurable on that battery, and the one failure is a base-model limitation, not
quantization damage — see §7.6 and `KNAPCIO-SGLANG-INTEGRATION.md`.

**Remaining gap to upstream 89.7 c1** (~1.9×) is *not* a knob we have left: the
SPS table is a crash, and upstream additionally runs a 2200 MHz clock cap
convention (we are uncapped) on their own fabric. Treat 89.7 as their number.

---

---

## 8. Guards, layout ABI, and the verification ritual

### 8.1 `tests/test_ds4_recipes.py`

Stdlib-only, parses recipe text with a ~60-line regex parser — **no PyYAML** (a hard
repo rule: `tests/` and `tools/` must run on a head node, in a container, and on a
laptop with no venv; the offline cache has no PyYAML). It was once shipped importing
`yaml`, passing 26 tests while being unrunnable where it matters — never do that.
The parser must assert it parsed something, or a failed parse presents as a passing
guard (`test_parser_acted_on_real_content`).

**Guards inspect the rendered command, not the template.** A "never `NEXTN`" check
against `--speculative-algorithm {speculative_algorithm}` is decoration —
`--default speculative_algorithm=NEXTN` ships it anyway. The module has its own
`render()`. **One guard is deliberately inverted:** `DefaultsAreConsumed` must read
the *template* (placeholders are gone after rendering); its docstring says so.
**Every guard has a proven negative control**, and controls rewrite a string in
memory and re-parse, so nothing on disk is touched. **Guards scan executable lines
only** — recipe prose documents the forbidden strings; strip whole-line comments
first. Anchor controls on stable keys (e.g. `gpu_memory_utilization`), not tunable
values (`page_size` moved and broke a control once).

Guards in force (as of the shipped EXL3 suite): `SGLANG_B12X_MAX_TOKENS ==
--chunked-prefill-size` (SGLang lane); `--speculative-algorithm ∈ {DSPARK, EAGLE}`,
never `NEXTN`; no `EAGLE` on a non-V4.1 (DSpark-head) checkpoint; no
`expandable_segments` on a V4.1 *SGLang* recipe; every `defaults:` key consumed by a
placeholder; `--tp` equals `defaults.tensor_parallel` and ≤ `min_nodes`; the three
NVFP4 runner overrides present on NVFP4 and absent on MXFP4; no `--*-backend`
overrides on V4.1; Engram layout `per_rank`; no V4.1-Flash recipe may claim TP=2
(`NoTP2`); `MillionTokenContext` (1M siblings differ from their 300K twin in
`max_model_len` only); `KCaptureSizes` (capture ladder matches k);
`test_dspark_k_is_measured_optimum`; `test_dspark_spec_config` (every EXL3 arm
ships DSpark; TP=3/TP=6 must carry `virtual_heads_from`); `ModDraftConfigContract`
(the mod keeps `config_speculative.py` mapped and md5-listed — pruning it silently
reverts TP=3/TP=6 to the retired no-spec failure); `test_consuming_entrypoint_cleared`;
`test_description_matches_spec_config`; `test_instanttensor_load_and_hybrid_mod`
(now asserting the reverted state).

### 8.2 `Recipe.tp_flag()` — two runtimes, one directory

SGLang uses `--tp`; vLLM uses `--tensor-parallel-size`. A guard that hardcodes one
spelling passes vacuously on the other runtime. `Recipe.tp_flag()` reads `runtime`.
The existing guard suite once had three SGLang-only assumptions that silently ignored
the vLLM recipes; they were fixed by deriving the spelling from `runtime`, and the
new recipes were added to the shared `ALL` list — which immediately surfaced them.

### 8.3 Verification ritual before any hardware claim

```bash
set -e
H=$PWD/.local/sparkrun-home; mkdir -p "$H"
uv run python -m unittest discover -s tests
for f in recipes/ds4/*.yaml; do HOME="$H" sparkrun recipe validate "$f"; done
HOME="$H" sparkrun run <recipe> -H <node> -n | grep -o -- '--tensor-parallel-size [0-9]*'
HOME="$H" sparkrun recipe vram <recipe>          # expect it to be WRONG (§3.3)
for s in mods/*/*.sh; do bash -n "$s"; done
for p in mods/*/*.py tools/*.py; do uv run python -m py_compile "$p"; done
find mods tools -name __pycache__ -type d -exec rm -rf {} +
```

`sparkrun recipe validate` **without** `--strict` (6 of 18 existing recipes already
fail `--strict` on accepted warnings). Grep the *rendered* line, not the file — an
unmapped `defaults:` key is silently not a setting. For the vLLM lane the rendered
grep is `--tensor-parallel-size N`.

---

## 9. Dead ends and negative results (do not re-try)

**2026-09-24/25 (each cost a boot or an hour):**

- **Serving V4.1-Flash on SGLang with any published image — do not try.**
  ~~SUPERSEDED 2026-10-02 for a purpose-built image~~ — the blockers below were
  real *for the images published at the time*; they are solved by the image built
  from `knapcio/DeepSeek-V4.1-Flash-4x-DGX-Spark-TP4` (V4.1 branch + adapter
  overlay + b12x_next), now **vendored** as
  `littlecedar/dgx-spark-dsv41:canary-roce` (digest-pinned) so sparkrun pulls it
  rather than building on every node, and running
  `EP_SIZE=1` (every rank a 576-wide slice of all 384 experts, so the `%128`
  check is moot). That lane **boots and serves**; see
  `KNAPCIO-SGLANG-INTEGRATION.md` and §7.13. Three
  independent blockers: no single published image is both V4.1 and `b12x`
  (`dev-dsv41` has `DeepseekV41Config` + an SM121-accepting DeepGEMM gate but **no
  `b12x`**; `dev-v4f-2dgx-v2` has `b12x` but **no V4.1 config**); the MXFP4-Cutlass
  MoE rejects the TP=4 expert partition (`2304/4 = 576`, not a multiple of 128) and
  TP=8 (`288`); and the DeepGEMM SM121 question. Any one makes it an
  image-build/code-patch project, not a config. **The vLLM/EXL3 lane remains the
  shipped default path.**
- **The five removed SGLang recipes** (archived under
  `.swival/trash/ds4-sglang-removed-2026-09-25/`): the three V4-Flash-0731 TP=2 rows
  (MXFP4, MXFP4-nospec, NVFP4) all die with **one signature — rank-0 scheduler
  SIGTERM (exit −15) ~5 min into init**, no OOM (host 117 GB free,
  `OOMKilled=false`), no worker error, `watchdog_timeout` confirmed 3600. Three
  variants, three loader paths, one signature. **Exonerated by construction:**
  DSpark (the no-spec control died identically), shared-expert fusion (the NVFP4 arm
  runs with it disabled and died identically), OOM, the SGLang watchdog, and the
  checkpoint. Mechanism **unidentified** — record it as such. (Three wrong guesses
  are named on purpose — watchdog, DSpark, fusion — so the next session does not
  re-make them.) Next: py-spy/strace the scheduler subprocess across the 5-min mark,
  or run outside sparkrun.
- **No "TP=2 escape" for V4.1 by quantizing harder** — the EXL3 build is 10% smaller
  and still 37 GB over the pair's RAM (§3).
- **`cluster_config.resolved_model_path` cannot serve an HF snapshot dir** (symlinks
  into `../../blobs` leave `config.json` dangling).
- **Bash does not glob a bare env assignment** — cost a boot cycle, surfaced as a
  `tensor_storage` error, not a globbing one.
- **`transfer_mode: pull` is broken in sparkrun 0.3.9**; `local` cannot pull an
  arm64-only image from an amd64 control host, and makes the *node* clone a local
  `file://` registry under `delegated`.
- **A quality battery that saturates is not a quality measurement** — the 19-task
  easy tier scored 100% on a 3.5 bpw model; the hard tier exists because of this.

**Earlier (still in force):**

- **V4.1-Flash at TP=2 — closed by arithmetic, not tuning** (§3). Do not spend a
  boot on it.
- **The upstream Engram host-table feature does not relieve TP=4 memory** (§3.2).
- **`nvidia/DeepSeek-V4.1-Flash-NVFP4` is bigger than the MXFP4 original** (§2.3).
- **`--speculative-algorithm EAGLE` on a DSpark-head checkpoint** starts, serves,
  returns correct output, **accepts nothing** (`accept len: 1.00, accept rate:
  0.00`) — you pay full draft cost for zero gain. The correct output is what makes
  it easy to miss. VERIFIED (upstream docs).
- **`--speculative-algorithm NEXTN` on DeepSeek-V4** crashes at arg validation (the
  NEXTN→EAGLE alias resolves after the model hooks; sglang#38236, unfixed on main
  `2c05ed4e7`). Our Qwen3.8 recipes use `NEXTN` — **do not copy that here**.
- **Overriding `--attention-backend` / `--moe-runner-backend` / `--fp8-gemm-backend`
  on V4.1** drops the 32-wide ue8m0 blocks onto the Triton `_w8a8_block_fp8_matmul`
  fallback and costs most of the bs=1 throughput. Confirm resolved backends in the
  startup log instead of passing them.
- **Engram host-table `shared` layout on a multi-node TP group** hard-fails on PID
  namespaces (`engram.py:605-611`). Use `per_rank`.
- **`OFFLOAD_MODE=ram` on a Spark** — "The Engram tables would evict the model"
  (MiaAI, verbatim). **HiCache / CPU-offload KV / `swa_full_tokens_ratio` as memory
  tools** — not applicable: host RAM *is* GPU RAM.
- ~~**TP=3 closed by padding cost**~~ **RETRACTED 2026-09-23.** TP=3 is not a dead
  end; tonyd2wild built it with **virtual heads** (64→72, 8→9) cheaper than MiaAI's
  64→96 padding, and it measured faster than the release TP=4 at every concurrency.
  The old claim survives only narrowly: TP=3 needs padding, and naively padding like
  MiaAI did is expensive.
- **`--enable-deterministic-inference` on the V4.1 backend: refused.** Output is not
  bitwise stable across batch composition today. Do not write a regression test
  asserting cross-batch determinism.
- **`SGLANG_FLASHINFER_MOE_FUSED_FINALIZE=1`** sums the six expert outputs with
  atomic bf16 adds, so greedy outputs differ run-to-run by up to ~1 nat on
  first-token logprobs. Keep it 0 (cost ~0.3 ms/step).
- ~~**CUDA graphs on sm_12.x in vLLM are unstable; use `--enforce-eager`**~~
  **RETRACTED 2026-09-23 for this stack.** tonyd2wild serves V4.1-Flash at TP=4 on
  GB10 with `FULL_AND_PIECEWISE` graphs and no eager fallback; eager→graph is
  1.20–1.50× across C1–C6. Keep the note as "verify per stack", not "assume eager".
- **`--chunked-prefill-size 1024` on V4.1 is a memory control, not a throughput one**
  (§6.4).
- **The naive bandwidth roofline** (§4) under-predicts measured V4.1 TP=4 throughput
  by ~4×. Do not quote "10 t/s for V4.1 TP=4".

### 9.1 The SM121 DeepGEMM cliff (SGLang lane; read before believing any SGLang number)

`vroomfondel/dgxarley` documents four SM121-specific failures on 4× DGX Spark:
- **NVFP4 MoE** via sglang#25820 — merged 2026-06-22, native in v0.5.14. No longer a patch.
- **MTP/draft MoE crashes on GB10** — TVM kernel built for SM100 → `sm100f kernel not
  supported on sm121`; fix is `--speculative-moe-runner-backend marlin`.
- **`cuda_graph_max_bs` defaults to 8**; above 8 SGLang falls to eager and throughput
  collapses. Set `SGLANG_CUDA_GRAPH_MAX_BS=32`.
- **DeepGEMM hard-blocks SM121** — `deep_gemm/_C.so` allows SM100/SM120; SM121 returns
  `Unsupported architecture (attention.hpp:219)`, so `fp8_paged_mqa_logits` falls back
  to pure torch **outside the CUDA graph** at ~18 ms/step → a hard ~13–18 t/s ceiling
  independent of batch size, TP degree, or quantization. Escape:
  `SGLANG_OPT_USE_TILELANG_INDEXER=1` + `SGLANG_DISABLE_DEEP_GEMM=1` (13.5 → 18.7 t/s
  at n=1, ~42 vs ~18 at 12 concurrent) — needed a 3-line TileLang 0.1.8 patch. The
  proper fix (DeepGEMM PR #324 merged 2026-06-24; SGLang follow-ups #55/#27059 still
  open) gates on `arch_major == 12`, which numerically covers SM121 — just nobody
  has run it. **ANSWERED FOR THE SPARK IMAGE 2026-09-23:** `dev-v4f-2dgx-v2`'s
  `deep_gemm/_C.so` gates on `arch_major == 10 or arch_major == 12` and carries both
  `sm100_` and `sm120_paged_mqa_logits` symbols — so the numeric exclusion is **not**
  present in that build (LIKELY, not VERIFIED: the strings prove the *gate* accepts
  SM121, not that a kernel was *compiled*). Only a boot log settles it.
- Also: `SGLANG_TOPK_TRANSFORM_512_TORCH=0` — the native `topk_transform_512` JIT
  kernel is bit-identical to the torch fallback on SM121.
- Related unresolved: `--enable-decoder-swa-bounded-replay` + DSpark — no shipped
  cell combines them (H200 has bounded replay without DSPARK; GB300 has DSPARK
  without bounded replay). `SPECULATIVE` that the combination is sound.
- `wo_a` has no FP8 kernel on SM121 (runs as bf16 einsum at ~13 ms/step), yet the
  verified Spark cell sets `SGLANG_OPT_FP8_WO_A_GEMM=1` — worth an A/B.

---

## 10. Open questions, ranked

### EXL3 / vLLM lane (the shipped deliverable)

- **E9. Host-memory reclaim — CLOSED: leave the recipes alone.** Two live boots
  (§7.8.1) show the launch weight load, not serving, fills 45–58 GiB/node of clean
  reclaimable cache, but `MemAvailable` stayed ≥41 GiB and the KV pool sized
  correctly *with* it; a load-window flusher bought **+0.9 % KV (noise)** — refuting
  TUNING_BACKLOG B1.3. And the one lever that would prevent the cache,
  `--load-format instanttensor`, is **incompatible with this checkpoint** (91.56 GiB
  tensor → InstantTensor's ≥91.56 GiB GPU buffer → SIGABRT; §7.9, reproduced
  boot-free). **No recipe change.** Full plan: `MEMORY-RECLAIM-PLAN.md`.
- **E5 comparator — CLOSED (2026-10-02, §7.13).** The SGLang lane runs the release
  checkpoint on the same hard tier and scores **17/18 = 94.4 %** (two runs) — the
  *same* score and the *same* single failure (`hard-rev`) as EXL3. So the 3.5 bpw
  quantization costs nothing measurable on this battery; the one failure is a
  base-model limitation. The old "cannot say without the (blocked) SGLang lane" is
  resolved: the lane is no longer blocked.
- **E6. Provision node-local Engram rows.** All boots so far read rows from the
  checkpoint files on node-local disk and worked; upstream measures 129 s local vs
  309/470 s when the files are remote for the weight load, so `tools/engram_local.py`
  rows are a **throughput** follow-up, not a correctness one. Deliberately deferred.
- **E7. TP=3/TP=6 + DSpark — SOLVED AND MEASURED (2026-09-27).**
  All three DSpark-eligible arms ship DSpark k=3 and **booted and served** on
  2026-09-27 — TP=3, TP=6 300K, and TP=6 1M (the last booted exactly as shipped):
  TP=3 KV 1,896,721 tok, C1/C4/C8 34.3/59.1/77.7, accept 2.40–2.50;
  TP=6 KV 12,006,501 tok, C1/C4/C8 44.5/72.5/115.3, accept 2.43–2.50;
  TP=6 1M KV 13,054,046 tok, C1/C8 35.3/118.4, accept 2.37–2.44. (TP=4 already
  shipped DSpark k=3 and was measured earlier.)
  Root cause (characterized 2026-09-26/27, image `exl3a`): `_verify_and_get_draft_tp`
  (`vllm/config/speculative.py:1665`) sets the drafter's TP to the **target's TP**
  unless the draft is an `mlp_speculator`; `draft_tensor_parallel_size` may be **1 or
  the target TP only** (`speculative.py:395`); the failure is
  `vllm/config/model.py:1420` `total_num_attention_heads % tp != 0` (`64%3=1`,
  `64%6=4`). The **fix**: dict `hf_overrides` are target-only
  (`compose_draft_hf_overrides`, `speculative.py:1044-1067`), so the drafter never
  saw the 72/9 (TP=3) or 96/12 (TP=6) virtual-heads declaration. The mod's
  `config/speculative.py` applies that dict to the draft config; the drafter reuses
  the target's modded attention and pads like the main model, and the mod's
  `dsv4_nvidia_model.py` already relaxes the 128-expert assert on the no-EP path.
  Evidence: device-free probe (`.scratch/ds4/dspark_tp36/`), then live boots
  (`.scratch/ds4/dspark_tp36/live/`: `RESULTS.md`, `tp3_serve.log`, `tp6_serve.log`,
  `*_accept.txt`, `measure_*.out`). Every §7.3 gate held — draft `97 params`, dspark
  graphs `8/8`, Engram rows differ per rank, acceptance > 1. Upstream served the
  TP=3 end-state (72/9, `exl3tp3a11`); the TP=6 (96/12) arm was first-of-kind.
  See `DSPARK-TP3-STUDY.md`.
- **E8. `draft_tensor_parallel_size: 1` — does NOT unlock DSpark (CLOSED, dead end).**
  Probed and traced 2026-09-27: it passes `SpeculativeConfig` validation
  (`speculative.py:1686-1692` allows 1), but DSpark is an **in-worker** speculator —
  `model_runner.py:262` builds it from the worker's config, and the drafter model is
  built inside every TP worker (`spec_decode/dspark/utils.py:34-76`), while
  `draft_parallel_config` is consumed only by the v1 *proposer* path for eagle-style
  separate draft workers (`v1/spec_decode/draft_model.py:72-89`). So validation
  passes and the drafter then dies at build on `assert 64 % tp_size == 0`
  (`deepseek_v4_1/attention.py:227`) with the target's TP. **Do not spend a boot on
  it.** The accepted gate for the shipped design (E7) is unchanged: the boot must
  reach `Capturing dspark CUDA graphs` and log a **non-zero** `Mean acceptance
  length`; a boot that serves but accepts nothing is the EAGLE-on-DSpark-head failure
  mode and must be reported as such, not as a win.

### SGLang lane (second engine)

> **ANSWERED 2026-10-02 by the knapcio overlay lane (§7.13).** Q1 monkey-answered:
> the lane uses `b12x`/`b12x_next` and boots. Q2 superseded: no *published* image
> is both, but the repo **builds** one. Q3 answered yes — it captures CUDA graphs
> and serves. See `KNAPCIO-SGLANG-INTEGRATION.md`; the items below are kept as the
> pre-lane state.

1. **Does our container's DeepGEMM support SM121?** Largely answered for the Spark
   image (see §9.1); only a boot log settles it.
2. **Does `dev-dsv41` contain `b12x`, and does `dev-v4f-2dgx-v2` know
   `DeepseekV41Config`?** ANSWERED both ways: no single image is both (§9).
3. **Does the V4.1 backend run on SM121 at all?** `SPECULATIVE`; the boot either
   captures CUDA graphs or it does not.
4. **DSpark window sweep with accept length AND expert-activation counts** —
   resolves the 334 GB/s contradiction (MiaAI attribute 27 ms to the MoE GEMM and
   say it "scales with the 6-token verify window"; 6 tokens of V4.1 expert bytes at
   TP=3 is 9.02 GB, which in 27 ms needs **334 GB/s**, above the 273 GB/s spec and
   47% above the measured 227.8 GB/s copy rate — so the window-6 verify must read
   ≲3.5 tokens' worth of *distinct* experts, or the 27 ms covers more than expert
   traffic). **We should not resolve this by reasoning; it needs a profiler run.**
5. **Which `NCCL_*` knobs did MiaAI set?** Only in their `.env`, which we do not
   have. Enumerate from `NCCL_DEBUG=INFO` on our nodes (§6.3).
6. **`--enable-decoder-swa-bounded-replay` + DSpark.** No mutual-exclusion assert,
   no shipped cell combines them; `SPECULATIVE`. It is a *prefill* optimisation and
   is not numerically equivalent to full prefill.
7. **`wo_a` FP8 kernel on SM121** — worth an A/B (second-order).
8. **Is `SGLANG_OPT_USE_DSV41_GATHERED_TOPK` safe with CUDA graphs?** Reorders the
   MoE gate/topk across TP ranks to drop an all-gather; ~20% prefill; "on by default
   on SM100/SM120". Nobody has said anything about SM121; a reordering bug is a
   correctness bug.
9. **Can SGLang be made to *load* the 4-bit Engram?** Arithmetic settled (§3.4); the
   software is open. **Highest-value mod in this family.**

---

## 11. Measurement discipline

Carried forward from the Qwen3.8 corpus (the traps are hardware-generic), plus
DS4-specific additions.

- **Counting SSE chunks under-reports ~3.5×** because each chunk carries a whole
  accepted speculative block. Measure decode as `usage.completion_tokens / elapsed`
  on non-streaming requests, or from the `gen throughput` field of `Decode batch`
  lines.
- **A DSpark number without an accept length is not a number.** Acceptance is
  workload-dependent (highest on maths/code, lower on chat/agentic traces). State
  the reasoning-effort budget too.
- **Radix-cache contamination produces absurd TTFT** (dgxarley: ~5 s at 32K with a
  shared prefix; ~145 s cold with unique prompts). Use unique prompts per context,
  and give each bench leg its own `--flush-cache`.
- **`peak_throughput` in llama-benchy 0.4.0 is a 1-second sliding-window maximum**,
  not a mean (`results.py:84`). Do not compare it against a mean.
- **Never time narrow-dtype reads as `t.to(fp32).sum()`** — that instruments the
  cast (~25 GB/s), not memory; fp8 has no native reduction. The mirror trap is
  reducing a `uint8` buffer with integer-mean semantics. Any bandwidth number states
  the dtype and the reduction.
- **A kernel whose sequential control matches its scattered control measures
  neither.** Check the control before believing the number.
- **Remove probe containers before measuring** (spare containers made rank 2 5–8%
  slower on identical GEMMs). Run load generators/profilers **off the head** (it
  hosts the server, tokenizer and detokenizer; analysis needs a second CUDA
  context that cannot be created while a rank is up).
- **Read the boot log for resolved backends and the KV budget line** before believing
  any config claim (§6.5).
- **Boot time is ~12–13 minutes.** `readiness.port_timeout_s` is not paranoia.
- **The indexer fallback is visible in the boot log** — near 13–18 t/s and you did
  not look, you will tune flags for a week to fix a missing kernel (§9.1).
- **An EXL3 recipe's numbers are unbooted → every figure is a port, not a measure**
  (state it whenever one is quoted).
- **Watch the harness when comparing.** Two harnesses produced the TP=4 numbers
  (36.4/58.0/76.1 cold vs 37.5/61.9/88.5 warm, and the §7.7 sweep's 36.7/72.8/96.1 at
  k=3); compare within a harness, not across. **A number without its warm/cold label
  is not comparable to anything, including itself.**
- **Sample the CLI surface before serving when in doubt.** Confirm a flag is in the
  *loaded module*, not only in the file, or the source holds a stub.

---

## 12. References

Fetched 2026-09-19 unless noted.

**Primary:**
- [deepseek-ai/DeepSeek-V4.1-Flash](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash) — model card, tech report, `config.json`
- [DeepSeek-V4.1-Flash announcement](https://api-docs.deepseek.com/news/news260910/) — 2026-09-10
- [SGLang V4.1 cookbook](https://github.com/sgl-project/sglang/blob/main/docs/cookbook/autoregressive/DeepSeek/DeepSeek-V4_1.mdx)
- [SGLang V4 cookbook](https://github.com/sgl-project/sglang/blob/main/docs/cookbook/autoregressive/DeepSeek/DeepSeek-V4.mdx)
- [SGLang DGX Spark cell config](https://github.com/sgl-project/sglang/blob/main/docs/src/snippets/configs/deepseek-ai/deepseek-v4.jsx)
- [lmsys blog: DeepSeek-V4.1](https://www.lmsys.org/blog/2026-09-10-deepseek-v41/)

**Prior Spark deployments:**
- [MiaAI-Lab/DeepSeek-v4.1-Flash-DGX-Sparks](https://github.com/MiaAI-Lab/DeepSeek-v4.1-Flash-DGX-Sparks) — 3×/4× Spark, TP=3/TP=4, `REPORT.md` (AGPL-3.0)
- [vroomfondel/dgxarley `DEEPSEEK_V4_FLASH_NVFP4_SGLANG_GB10.md`](https://github.com/vroomfondel/dgxarley) — 4× Spark, SM121 fixes and numbers
- [0xSero/deepseek-v4-flash-0731-spark](https://huggingface.co/0xSero/deepseek-v4-flash-0731-spark)

**vLLM / EXL3 lane (read 2026-09-23):**
- [tonyd2wild/DeepSeek-V4.1-Flash-vLLM-DGX-Spark](https://github.com/tonyd2wild/DeepSeek-V4.1-Flash-vLLM-DGX-Spark) — MIT; TP4/TP3 lanes, `docs/EXL3-TP3.md`, `patch/exl3-tp3/` (the mod's source). Read at commit `d45538f6…`; cloned to `.scratch/ds4/tonyd2wild-vllm/`.
- [bot-lab-21/DeepSeek-V4.1-Flash-EXL3-3.5bpw-Pollard](https://huggingface.co/bot-lab-21/DeepSeek-V4.1-Flash-EXL3-3.5bpw-Pollard) — the checkpoint; card carries served numbers, the tuning ledger, the Engram-on-disk / NCCL-channels-8 levers.
- [Zeuss5/cuda-exl3](https://github.com/Zeuss5/cuda-exl3) — the vLLM EXL3 plugin and GB10 kernels (`6a1ffc34`, baked into our image).
- tonyd2wild `runs/2026-09-17-nvfp4` — fourteen boots of `nvidia/DeepSeek-V4.1-Flash-NVFP4` that never served; the lever that held was `--enable-expert-parallel --enable-ep-weight-filter`.

**Kernels / upstream:**
- [sgl-project/sglang#34878](https://github.com/sgl-project/sglang/pull/34878), [#35899](https://github.com/sgl-project/sglang/pull/35899), [#34018](https://github.com/sgl-project/sglang/pull/34018), [#37253](https://github.com/sgl-project/sglang/pull/37253) — SM12x `b12x` MoE + compressed-MLA
- [sgl-project/sglang#25820](https://github.com/sgl-project/sglang/pull/25820) — NVFP4 MoE, merged 2026-06-22
- [sgl-project/sglang#38236](https://github.com/sgl-project/sglang/issues/38236) — NEXTN crash
- [sgl-project/sglang#29272](https://github.com/sgl-project/sglang/pull/29272) — fastsafetensors device bug, open
- [deepseek-ai/DeepGEMM#324](https://github.com/deepseek-ai/DeepGEMM/pull/324), [sgl-project/DeepGEMM#55](https://github.com/sgl-project/DeepGEMM/pull/55) — SM120/SM121 support

**Internal (deleted with this consolidation):** `DS4-MODEL-OPTIMIZATION-WORK.md` and
`JOURNAL.md` held the full narrative; the sections above are the durable subset.
`attic/qwen4/QWEN4-MODEL-OPTIMIZATION-WORK.md` §11 is the GB10 memory-system
source. The node-handshake ledger was a `COOP.md` working file (git-ignored, not
part of the tree); node roles and the protected/shared split live node-side.


---

## From recipes/ds4/AGENTS.md (2026-10-14)

# DS4 — `recipes/ds4/` agent & developer guide

DeepSeek V4.1-Flash on NVIDIA DGX Spark (GB10, SM121, 128 GB unified LPDDR5X
per node, 2× ConnectX-7 200 GbE RoCE). Read this before touching the recipe, the
mod, or the guards in this directory.

**Scope of this file.** This directory now ships **one** recipe — the SGLang
"knapcio" lane:

- `deepseek-v4.1-flash-knapcio-tp4-1m-sglang.yaml` — SGLang, TP=4, 1M context,
  official MXFP4/F8 checkpoint, DSpark verify-all, Engram on node-local NVMe,
  RoCEnante RDMA.
- [`README.md`](README.md) — the user-facing guide (what it is, requirements,
  how to run, limits).

**The EXL3 / vLLM lane is archived.** Five vLLM recipes over
`bot-lab-21/DeepSeek-V4.1-Flash-EXL3-3.5bpw-Pollard`, the former consolidated
agent guide, the DSpark TP=3/TP=6 study, the memory-reclaim plan, the
performance triage, and the session notes were moved to
[`attic/ds4/`](../../attic/ds4/) when this recipe was chosen for go-live. They
are not shipped and not covered by the guards here. The attic copy of the agent
guide still holds the load-bearing *model* analysis (anatomy, the residency
wall, the DSpark k-sweep) and is worth reading for background, with the caveat
that it is a frozen snapshot.

**Evidence vocabulary (repo convention).** **VERIFIED** — read from a primary
artifact (a boot log, a pinned image, source at a pinned commit) or measured on
our devices. **LIKELY** — strong secondary evidence. **SPECULATIVE** — reasoning
without a source; do not build on it. Numbers derived here say "computed here";
numbers someone else measured name who. Never promote `LIKELY` into unlabelled
fact.

---

## 1. The design in one paragraph

The checkpoint is 510 GB of native MXFP4/F8 weights. 203 GB of it is the two
Engram embedding tables, which cannot coexist with the weight shards in a
single node's 128 GB unified pool. The lane therefore runs on a purpose-built
SGLang image whose reader streams Engram rows from **node-local NVMe**, packed
one shard per rank. The image's `boot.py` builds the entire `sglang.launch_server`
argv from environment variables; sparkrun appends `--dist-init-addr/--nnodes/
--node-rank` assuming `sglang serve`. The mod's `launcher.py` is the adapter
between the two: it consumes sparkrun's flags, maps them onto boot.py's
environment, applies the production configuration, resolves the checkpoint, and
`execve`s `boot.py`.

Upstream: [`knapcio/DeepSeek-V4.1-Flash-4x-DGX-Spark-TP4`](https://github.com/knapcio/DeepSeek-V4.1-Flash-4x-DGX-Spark-TP4)
@ `58f2321`, a downstream of MiaAI-Lab's recipe. The launcher, adapters, b12x
kernels, and measurement design are theirs, kept under their licences.

---

## 2. Files and the call chain

```
recipes/ds4/deepseek-v4.1-flash-knapcio-tp4-1m-sglang.yaml
  mods: "@littlecedar/mods/dsv41-sglang-overlay"
    run.sh            # fail-closed compatibility gate; creates + reowns cache dirs
    launcher.py       # RECIPE_ENV production config; rank handling; checkpoint resolution
      -> execve: /opt/dsv41/boot.py run     # builds the full sglang.launch_server argv
```

The recipe's `command:` is a one-line call to the shim:

```
python3 /workspace/mods/dsv41-sglang-overlay/launcher.py --boot
  --model {model} --port {port} --tp {tensor_parallel}
  --served-model-name {model} --context-length {max_model_len}
```

sparkrun appends the per-node distribution flags; the launcher consumes them.

---

## 3. Recipe invariants (all guarded)

These are load-bearing and each has a guard in
`tests/test_ds4_recipes.py::SglangLaneContract`.

1. **No `env:` block.** Everything — the production config *and* the checkpoint
   location — lives in the launcher, so it travels with the mod rather than with
   each recipe. The recipe passes the repo id via `{model}`; the launcher derives
   the snapshot path. Guarded by `test_recipe_env_is_empty`. Because the launcher
   applies `RECIPE_ENV` with `env.update`, this is also where every production
   switch lives: there is **no recipe-side knob** for e.g. `DSV41_FAST_LOAD`
   (§7.1) — flip it in the launcher, or not at all.
2. **TP flows through `defaults` → `command` → launcher.** sparkrun does **not**
   emit `--tp-size` when a `command:` template is present; it substitutes the
   placeholder. The template emits `--tp {tensor_parallel}` and the launcher maps
   it onto `TP_SIZE`. Without the mapping, boot.py silently falls back to TP=3 on
   a 4-node cluster. Guarded by `test_tp_flows_through_command_to_launcher`.
3. **Context length flows the same way.** `--context-length {max_model_len}` →
   `CONTEXT_LENGTH`, applied *after* `RECIPE_ENV` so the recipe (and `-o
   max_model_len=…`) wins. boot.py asserts `4096 ≤ CONTEXT_LENGTH ≤ 1048576`.
   Guarded by `test_context_length_wired_to_launcher`.
4. **The image is vendored and digest-pinned.**
   `littlecedar/dgx-spark-dsv41:canary-roce@sha256:4e5002ab…`. Guarded by
   `test_image_is_vendored_and_pinned`.
5. **No `distribution_config:` block.** sparkrun's default already distributes
   both the model and the container (`core/recipe.py:_default_distribution_config`).
   Omitting the block is behaviorally identical and one fewer thing to drift; a
   reintroduced `enabled: false` would strand workers. Guarded by
   `test_distribution_config_omitted`.
6. **No host bind mounts and no host device names.** No `volumes:`; no env value
   names a host adapter. Guarded by `test_no_host_bind_mounts`,
   `test_no_host_device_names_in_env`, `test_managed_comm_env_not_pinned`.
7. **The entrypoint is cleared** (`executor_config.entrypoint: ""`) so the
   recipe's `command:` runs instead of the image's ENTRYPOINT. Guarded by
   `test_entrypoint_cleared`.
8. **The checkpoint revision is pinned in the recipe, not the image.** The image's
   `boot.py` bakes one (`boot.py:24 REVISION`, `fb2764a5…`) but never acts on it
   here: the launcher sets `SKIP_PREPARE=1` and hands boot.py the
   sparkrun-distributed path that `{model}` renders to, so the recipe's
   `model_revision:` alone decides which snapshot is served. The pin is `main`
   (`5254448103b6…`), not the baked `fb2764a5…` — decided 2026-10-14, reasons in
   §5. Guarded by `test_checkpoint_revision_pinned_in_recipe`; mechanism and the
   `launch.json` trap are also in §5.

`readiness.port_timeout_s: 7200` / `health_timeout_s: 3600` are deliberately
generous — a cold boot reads/packs a 510 GB checkpoint.

---

## 4. The mod (`mods/dsv41-sglang-overlay/`)

**`run.sh` is a fail-closed compatibility gate.** It asserts that boot.py, the
adapter `sitecustomize.py`, b12x_next, and the engine's `engram.py` all exist,
logs the overlay paths, creates the cache subdirectories, and `reown`s them (mods
run as root; the serve user must be able to write them). It modifies **no image
file** — the overlay is gated by the upstream repo's own in-image tests.

**`launcher.py` owns the production configuration** in `RECIPE_ENV`. It applies it
with `env.update(RECIPE_ENV)`, **not** `setdefault`: the image bakes
`STATE_PATH=/state`, `DSV41_CACHE_GIB=16`, `PYTORCH_CUDA_ALLOC_CONF=…True`,
`SGLANG_RUST_BUILD_MODE`, and `OFFLOAD_MODE` into its ENV, and `boot.py` is
`execve`'d from that process, so a `setdefault` would let the image win (that bug
was caught live: `launch.json` went to the unwritable `/state` and the allocator
reverted to the `expandable_segments:True` NaN-logits mode). `RECIPE_ENV` is
disjoint from the recipe-owned keys.

Three launcher behaviours that are easy to get wrong:

- **Rank is learned from sparkrun's flags, never the container env.** sparkrun
  appends `--node-rank` to every node's serve command; the container env has no
  rank. Only the launcher sees it, so the launcher — not the mod — materializes
  this rank's Engram shards.
- **Checkpoint resolution self-heals.** `resolve_checkpoint()` accepts all three
  shapes sparkrun can hand it: the **prepared on-disk snapshot path** that
  `{model}` renders to on a real launch (`models/runtime.py:bind_runtime_models`
  rewrites the placeholder to the distributed path whenever the recipe has a
  `command:` template — a dry run still prints the repo id), a repo id resolved
  in the fixed in-container HF cache (`/cache/huggingface/hub/models--<org>--<name>`
  → `refs/main`, else any snapshot with `config.json` and
  `model.safetensors.index.json`), and a host-side `MODEL_PATH` bind (left alone).
  A cache re-resolving to a new hash cannot break the recipe, no `snapshots/<hash>`
  appears in it, and a `--served-model-name` that arrives as a path is reported
  back as the repo id.
- **Engram packing is detached.** When this rank's shards are absent, the
  launcher spawns the packer in the background so a cold boot never exceeds
  sparkrun's ~150 s head-rendezvous wait; the boot proceeds on the checkpoint
  fallback and the next boot uses the packed shards. `packed=False` on a first
  cold boot is expected.
- **It writes `/tmp/sparkrun_health_port`** as the rendezvous file the image's
  healthcheck reads (the image bakes `STATE_PATH=/state`, so a
  `$STATE_PATH`-relative path would not have round-tripped).

Cache locations (all under sparkrun's managed runtime cache, mounted at
`/cache/runtime`): `engram`, `state`, `b12x-compile`, `b12x-roce`. The host leaf
is computed by sparkrun (`core/runtime_cache.py`) and never spelled in the
recipe.

**Mod-reference resolution.** `@littlecedar/mods/…` resolves from the node's
**registry git clone**, not the synced working tree, so iterating on the mod
requires committing it (and pushing/refreshing the registry cache) before a
launch will see the new code. `sparkrun recipe validate` does **not** check mod
existence; only a real launch (or `-n`, which skips the registry sync) surfaces a
resolution failure.

---

## 5. The image

`littlecedar/dgx-spark-dsv41:canary-roce@sha256:4e5002ab58b5cca670e2624c6a0d0…`
(image `sha256:18e36391…`), arm64-only, 33.5 GB, base `lmsysorg/sglang:dev-dsv41`
+ SGLang `f80c91a4b` + the adapter overlay + b12x/b12x_next. Rebuilt 2026-10-03
for a **dynamic HEALTHCHECK**: `boot.py health` now discovers the served port at
runtime (env → the launcher's `/tmp/sparkrun_health_port` → the engine's own
`--port` from `/proc/<pid>/cmdline` → a LISTEN port from `/proc/net/tcp{,6}` →
image default). Before this, a server on any port other than 8888 reported
`Up … (unhealthy)` in `sparkrun status` while serving fine — Docker freezes
`Config.Env` at `docker run`, so a value set at runtime by the launcher is below
its view. The recipe's `readiness:` never played a part.

**Rebuilding the image.** It is arm64-only and reproducible from upstream's repo
at the pinned revision **plus the vendored `boot.py.health-port.patch`** — the
dynamic HEALTHCHECK described above is a local patch, **not** upstream (see the
trap below):

```bash
git clone https://github.com/knapcio/DeepSeek-V4.1-Flash-4x-DGX-Spark-TP4.git
cd DeepSeek-V4.1-Flash-4x-DGX-Spark-TP4 && git checkout 58f232155917d388b6053eca079c617fd306c33c
git apply /path/to/sparkrun-recipe-registry/recipes/ds4/boot.py.health-port.patch  # REQUIRED
bash scripts/fetch-sglang-canary.sh            # stages the dsv4.1 tree @ f80c91a4b
docker build -f Dockerfile.canary-roce -t dsv41-4x-spark:canary-roce .
docker tag dsv41-4x-spark:canary-roce littlecedar/dgx-spark-dsv41:canary-roce
docker push littlecedar/dgx-spark-dsv41:canary-roce
docker inspect --format '{{index .RepoDigests 0}}' littlecedar/dgx-spark-dsv41:canary-roce
# The base tag `lmsysorg/sglang:dev-dsv41` is mutable, so the printed digest is
# the pin to carry: rewrite the recipe's `container:` line with it before booting.
```

**The clone alone does NOT reproduce this image — the `git apply` line is
load-bearing.** The port discovery the paragraph above describes is a local
patch to the build context's `boot.py`; it is absent upstream. knapcio's
`boot.py` @ `58f2321` **and** at `origin/main` (`27616bec`) both run a bare
`request('/health')` against the image default 8888. A literal fresh-clone
build therefore **silently drops the fix** and produces a *different* image —
measured 2026-10-14 on the head: image `dd9d1c3c…`, digest `ac9bc917…`, whose
`boot.py health` has no `health_port()` and re-introduces
`(unhealthy)`-on-any-port-other-than-8888. **Never push that as `canary-roce`.**
With the patch applied, the cached build reproduces image `18e36391…` / digest
`4e5002ab…` exactly (patched `boot.py` sha256 `6d2b4898…`). The patch is
vendored here as [`boot.py.health-port.patch`](boot.py.health-port.patch): a
byte-exact `boot.py.pre-healthport` → `boot.py` unified diff that applies
cleanly to pristine `boot.py` @ `58f2321`.

That file is vendored, verbatim, in this directory as **`Dockerfile.knapcio-dsv41`**
(header + the exact upstream body, sha256 `4ec1976c…`) for reference beside the
TensorFold Dockerfile. It is **not** self-contained — the real build reads the knapcio
clone as context — so use the clone, not the copy, to build.

To build locally instead of pulling, retag the result
`dsv41-4x-spark:canary-roce` and add
`distribution_config: { containers: { enabled: false } }` to the recipe.

| image attribute | value |
|:--|:--|
| Registry digest | `sha256:4e5002ab58b5cca670e2624c6a0d0799642914f04487ea130c71e7f525fa9c05` |
| Image ID | `sha256:18e36391488edb088cc70e2f8d9a3e16eb82f653496fa565526a6ffd6b7c6890` |
| Base | `lmsysorg/sglang:dev-dsv41` |
| Upstream overlay | knapcio `58f2321`, SGLang `dsv4.1` @ `f80c91a4b` |
| Local patch | [`boot.py.health-port.patch`](boot.py.health-port.patch) — runtime port discovery for the dynamic HEALTHCHECK (**not** upstream) |
| Built | 2026-10-03 on `.30` (rebuilt for the dynamic HEALTHCHECK) |
| Size | 33.5 GB (arm64) |

The build reuses the base and overlay layers (Docker layer cache), so a
`boot.py`-only rebuild ran ~4–5 min despite the 33.5 GB size; the new digest
must then be redistributed to all four workers before a boot.

**The checkpoint revision lives in the recipe, not the image.** The image's `boot.py` bakes
`REVISION = fb2764a5cf321eaa5070ca8f9e892818f477c16d` (`boot.py:24`) and downloads and serves
exactly that revision when `prepare()` runs — but the launcher sets `SKIP_PREPARE=1`, so
`prepare()` only asserts the checkpoint is already on disk, and the revision sparkrun
distributes (top-level `model_revision:`) is the one the launcher serves. Two consequences. The
image cannot move the lane off the pinned snapshot by itself, and a *missing* pin would serve
whatever `main` resolves to at distribution time. `boot.py` still writes its baked constant into
`$STATE_PATH/launch.json`, so that file is **not** evidence of what was served; the launcher's
`MODEL_ID is an on-disk checkpoint dir; serving …/snapshots/<sha>` (or, for a repo-id
invocation, `resolved checkpoint <repo> -> …/<sha>`) line is. `sparkrun recipe validate` warns
`unpinned-model-revision` on this pin because the command spells no `--revision`: a false
positive for this shim lane, where the launcher receives the prepared snapshot path and the
engine never resolves a ref — it is why this recipe fails `--strict`.

**The pin is `main`, `5254448103b6…` (2026-10-12) — decided 2026-10-14, superseding the image's
baked `fb2764a5…`.** Both revisions are Hub-resolvable (`fb2764a5…` is a real 2026-09-10 commit,
not a ghost), so the question was which to serve, not which exists. The A→B delta was re-run
against the Hub: `config.json`, `tokenizer_config.json`, the safetensors index and **all 48
weight shards are byte-identical**; the only changed files are `README.md`, the reference
`encoding/` and `inference/` trees, plus the ADDED `chat_template.jinja`. That reference tree is
not in the SGLang serving path (the engine and b12x kernels come from the image), so the delta
cannot move a served *number*; it could move a served *configuration* only through the added
chat template — and that direction favours `main`, because the receipts we can date were served
from `main`. The 2026-10-11 `ds4-restore` and 2026-10-10 gamma-A/B serve logs name
`snapshots/2cba9e42aa02…` (`main`'s template-carrying ancestor; `main` is `2cba9e42` plus
doc/indexer/pycache commits), never `fb2764a5…`. Pinning the baked revision would therefore
serve a snapshot *lacking* the file every receipt ran with. `main` is also what every node cache
already holds (`refs/main` = `5254448103b6…`, 90 blobs), so a launch distributes nothing, while
`fb2764a5…` is in no node cache; the boot receipt is in §5.1. Upstream's image still bakes
`fb2764a5…` because *its* lane downloads and serves that revision — ours never acts on it. The lane
is not a standing serve: launch it only on nodes verified idle (`docker ps -q | wc -l` = 0) and stop
it by recipe name when done — §5.1 leaves all four nodes clear.

The image's torch is **2.13.0+cu130** (VERIFIED by probing the image). PyTorch
2.13 renamed `all_gather_into_tensor` → `all_gather_single` and
`reduce_scatter_tensor` → `reduce_scatter_single`; the image's SGLang tree and
vendored kernels still call the old names, so each call logs a once-per-callsite
`FutureWarning` via `torch/distributed/c10d_logger.py:83`. The launcher silences
**only** that re-emission with a **module-scoped** filter
(`PYTHONWARNINGS=ignore::FutureWarning:torch.distributed.c10d_logger`); a
message-scoped filter does not take (the leading backtick defeats `re.match`),
and a blanket `ignore::FutureWarning` would hide unrelated warnings. Guarded by
`test_torch_2_13_collective_rename_warning_suppressed`.

### 5.1 Boot receipt — the pin, served (2026-10-14)

A four-node TP=4 boot on `.30` (head), `.32`, `.33`, `.34`, launched by name with
`-H .32,.33,.30,.34` and `model_revision: 5254448103b6…`. Cold boot:
launch 08:14 EDT, `/v1/models` answering **08:25:45 EDT** (~11.5 min).

- `launcher: MODEL_ID is an on-disk checkpoint dir; serving
  /cache/huggingface/hub/models--deepseek-ai--DeepSeek-V4.1-Flash/snapshots/5254448103b6254fc646dacbca1cbbf20e9216c1`
  — the served snapshot is the recipe's pin, **not** the image's baked `fb2764a5…`. This is the §5
  evidence line; `launch.json` is not.
- `GET /v1/models` → `{"id":"deepseek-ai/DeepSeek-V4.1-Flash","object":"model",…,"max_model_len":1048576}`.
- `RoCEnante ready: world=4 hcas=rocep1s0f0,roceP2p1s0f0 gid_index=3`; `[moe_b12x_next] armed`.
- `Exact nvme Engram layer=1 rank=0 rows=[0,96001542) … packed=True`; layer 14 on rank 0 attached
  `packed=False` — the reader rejected that layer's flat shard and fell back to the checkpoint for
  it this boot (the packed shard is an optional accelerator; the fallback is exact). This is
  pre-existing packer/reader behaviour, independent of the pin; both layers were `packed=True` on
  the 2026-10-11 boot. The flat shards were hand-packed on all four ranks before this boot
  (`python3 /opt/dsv41/scripts/pack_engram.py --rank R --tp 4 --out /cache/runtime/engram` with
  `DSV41_SOURCE` = the pinned snapshot), since the caches carried only the legacy revision-keyed
  `engram/v1/fb2764a5…/` shards, which this launcher does not read.
- `DSV4 memory calculation: … full_token=9651968`; `max_total_num_tokens=9399808,
  chunked_prefill_size=4096, max_running_requests=16, context_len=1048576`.
- The image smoke line: `Structured output, tool round trip and full-budget native vision passed.`
- Distribution was a **no-op**: both the model and the image were already on every node
  (`Distributing model deepseek-ai/DeepSeek-V4.1-Flash to 4 host(s) … done (8.8s)`, OCI relay
  "already verified on all 4 receiver(s); no transfer") — the concrete payoff of pinning the cached
  revision.

C1 (`benchmarking/decode-triage.yaml`, pp 2048 / tg 128, runs 5, `--skip-run`): depth 0 →
**tg 38.3 t/s** (pp 2278.9); depth 8192 → **tg 42.5 t/s** (pp 2874.2). Quality
(`tools/quality-battery.py`): EASY 19/19 (100%), HARD **17/18** (94.4%) with the same single
`hard-rev` character-reversal failure as the recorded 17/18 — the re-pin costs nothing measurable.
Receipts: `.scratch/ds4/knapcio-tp4-boot-20261014/` (`launch.log`, `bench.log`, `battery.log`,
`ds4-tp4-c1-decode-triage_1014.{json,csv,yaml}`, `ds4-tp4-battery_1014.json`). All four nodes were
left clear.

---

## 6. Fabric and NCCL

The fleet is two RoCE planes (`the CX7 plane-A subnet` on `rocep1s0f0`,
`plane-B subnet` on `roceP2p1s0f0`), **full mesh** (a switched fabric, not a
ring), port 1 ACTIVE, port 2 DOWN, RoCEv2 GID index 3.

**No adapter/interface name is pinned anywhere.** `NCCL_NET`, `NCCL_IB_HCA`,
`NCCL_IB_GID_INDEX`, `NCCL_IB_DISABLE`, and `NCCL_CROSS_NIC` are filled by
sparkrun's own InfiniBand probe, which includes only the ACTIVE ports (dropping
the DOWN `*s0f1`). `B12X_ROCE_HCA` is deliberately unset: it takes a literal HCA
list (a host device name), and b12x's RoCEnante falls back to the detected
`NCCL_IB_HCA` when unset (`roce_oneshot.py:85,99` → `discover_hcas`). Verified
live: `RoCEnante ready: world=4 hcas=roceP2p1s0f0,rocep1s0f0 gid_index=3`.

The launcher keeps only device-free transport *tuning*:
`NCCL_P2P_DISABLE`, `NCCL_SHM_DISABLE`, `NCCL_CUMEM_ENABLE`, `NCCL_BUFFSIZE`,
`NCCL_LL128_BUFFSIZE`, `NCCL_PROTO`, `NCCL_MAX_NCHANNELS`, `NCCL_DEBUG`.

`NCCL_BUFFSIZE` is a NCCL **connection-buffer byte size** (1 MiB here), **not** a
token count; it is deliberately not wired to `CONTEXT_LENGTH`. Upstream pairs
`NCCL_BUFFSIZE=1048576` with `CONTEXT_LENGTH=262144` in one profile and with
`1048576` in another, proving the two are independent. Guarded by
`test_nccl_buffsize_is_not_context_length`.

---

## 7. Deliberately off

- **`DSPARK_SPS_TABLE` / `DSPARK_STS_TABLE`** — the ragged-verify cost tables.
  Absent, boot.py stays on the verify-all schedule. Tested and rejected: with a
  fitted table the scheduler enables and the first mixed batch dies with
  `AssertionError: engram target-verify expects one equal block per request, got
  84 tokens for 16 requests of 6` → server never healthy. Upstream's own README
  lists it as not used. **Do not ship it** (guard: `test_sps_table_absent`).
- **`DSV41_FAST_LOAD=0` (shipped).** Upstream's eager loader is off: it buys
  ~220 s per boot and costs 3–13% of the KV pool. Mechanism and the A/B that
  would replace the number: §7.1 below.
- **`DSV41_CERT_HEAD`** — -0.5 ms/step at c1 but slower from ~10 requests.
- **`DSV41_ENGRAM_DRM_NODE`** — needs a host display-reserve change.

RoCEnante is **on** (`SGLANG_ROCE_ALLREDUCE=1`, `SGLANG_ROCE_MAX_SIZE`,
`DSV41_ROCE_GATHER`); rollback is one line.

### 7.1 Fast load (`DSV41_FAST_LOAD`) — shipped `0`

**Decision.** The launcher sets `"DSV41_FAST_LOAD": "0"`. The image does not set
the variable (`Dockerfile.canary-roce` `ENV` carries only `PYTHONPATH`,
`MODEL_PATH`, `STATE_PATH`, `OFFLOAD_MODE`, `DSV41_CACHE_GIB`), and
`adapter/fast_load.py:enabled()` defaults false, so `0` is the stock SGLang
safetensors loader. We set it explicitly to record a deliberate choice rather
than an inherited default.

**What it trades** (upstream's numbers, not ours — `VERIFIED` from the vendored
source's docs, `.scratch/ds4/knapcio/docs/history.md:121,127` and
`docs/fast-load.md`, which back the README caveat):

| at EP2, same image, same night (2026-09-18) | stock loader | `DSV41_FAST_LOAD=1` |
|:--|--:|--:|
| engine start (`scheduler_e2e`) | 343–354 s | 124–129 s |
| `max_total_num_tokens` | 7.47–7.82M | 6.71–7.27M |
| bytes reaching the model | — | bitwise identical |
| decode / prefill / needle | — | unchanged |

**Mechanism, not a leak.** SGLang sizes the pool from the head's
`psutil.virtual_memory().available` (`get_available_gpu_memory`, the integrated-GPU
branch — on GB10 "device memory" is system RAM). The fast loader reads each
rank's tensors eagerly into pinned host slabs and releases everything before the
pool is sized, but ~0.8–1.5 GB has still left `MemAvailable` at that instant, and
it shows in no counter (not shmem, not page cache, not the CUDA allocator —
upstream traced most of it to driver staging state from pageable buffers and made
the buffers pinned to close the gap). There is therefore no env knob that gets
the pool back while keeping the fast path; it is one or the other.

**Not our measurement.** The 3–13% is EP2 on the 2026-09-18 stack. This lane is
**EP1**, and upstream's later pinned-slab rework moved the pool **+0.73M tokens**
against its per-tensor precursor at EP1 (`docs/fast-load.md`), so the interval
here is probably smaller. `SPECULATIVE` on any specific EP1 delta — see the boot9
receipt below for the one EP1 number we hold.

**What our fleet actually measured.** One EP1 head log exists:
`.scratch/ds4/knapcio/logs/boot9-head-serve.log` (2026-10-02). It booted with
`DSV41_FAST_LOAD` **on**, so it is not the shipped config, but it is the only real
receipt we hold:

```
DSV4 memory calculation: … bytes_per_full_token=1670.75, available_bytes=11.71 GB, full_token=6786560
DSV4 pool sizes: full=6786560, …            # the budget derived from MemAvailable
DSV4 pool sizes: full=4000000, …            # after the MAX_TOTAL_TOKENS=4000000 pin
max_total_num_tokens=4000000, context_len=1048576, available_gpu_mem=21.18 GB
```

So on our hardware the fast loader left a **6.79M**-token budget (inside upstream's
6.71–7.27M fast-loader interval), and the server then **pinned the pool to 4,000,000**
regardless.

**Shipped-config ceiling, measured 2026-10-06 (`.30/.31/.32/.33`, stock loader, 0.80).** The
boot9 log above is fast-loader; these four boots are the shipped config:

```
DSV4 memory calculation: … bytes_per_full_token=1670.75, available_bytes≈15.9 GB, full_token=9493504..9589504
DSV4 pool sizes: full=<budget>   # what MemAvailable permits at 0.80
DSV4 pool sizes: full=<pin>      # what MAX_TOTAL_TOKENS selects, clamped to the budget
```

| `MAX_TOTAL_TOKENS` pin | served `max_total_num_tokens` | free mem after boot |
|--:|--:|--:|
| 4,000,000 (old shipped) | 4,000,000 | 25.10 GB |
| 9,000,000 | 8,999,936 | 14.39 GB |
| 9,400,000 (now shipped) | 9,399,808 | 13.68 GB |
| 10,000,000 | 9,589,504 (clamped) | 13.14 GB |

**The true ceiling is `full_token` ≈ 9.5–9.6M tokens**, stable to ~1% across boots; a larger pin
is clamped, never refused. The old 4M pin used **~58% of the ceiling**, so it was raised to
**9,400,000**. `mem_fraction_static` is `(weights + KV pool) / capacity` (SGLang
`memory_hook.py`), so any pin ≤ `full_token` sits inside the same 0.80 budget and leaves the same
~20% outside it for transients — raising the pin does not eat the reserve.

**Pool is page-shared, not extent-reserved.** Unlike the TensorFold lane, SGLang does not reserve
each stream's declared window: 16 concurrent 1M-claiming requests were all admitted and decoded
(`running-req` = the `MAX_RUNNING_REQUESTS=16` cap, zero errors, zero queue). Concurrent-1M-stream
count is bounded by `MAX_RUNNING_REQUESTS` and total *actual* tokens (<9.6M), not by per-stream
reservation. **`full token usage` reads 0.00 even under real draw in this build — do not use it.**

**Still owed:** a 1M cold-prefill after the raise. With `DSV41_INDEXER_CHUNKED=1` the per-chunk
transient is bounded (~2 GB logits) and upstream measured head low-water 6.6–7.7 GB during cold
262k–1M prefills; the 9.4M pin leaves 13.68 GB at boot, so it should hold — but it was not re-run.

**1M cold prefill VERIFIED 2026-10-06 (after a fleet reset).** A ~1M-token cold prompt ingested at
**2909 tok/s** and replied correctly at the 9.4M pin. Host available dipped to ~5 GB low-water
during the prefill (the indexer transient draws ~9 GB on top of the 13.7 GB pool) then recovered
to 10 GB — so 9.4M leaves enough but the head is near its floor during a 1M prefill. The pin is
now boot- and long-prefill-verified on all four nodes.

**Do not raise `MEM_FRACTION_STATIC`.** A 0.90 probe wedged three of four nodes on 2026-10-06
(GPU pool *is* host memory on GB10; userspace/SSH dead while ping alive). Keep **0.80**: it is what
caps the pool and keeps the transient reserve. The incident is written up in §11.

**A/B if you want the shipped-config number** (mirrors §10's discipline; read the pool
from the boot log, never computed):

1. Boot the shipped recipe; record `DSV4 memory calculation: … full_token=<N>`
   from `/tmp/sparkrun_serve.log` inside the container.
2. Flip `"DSV41_FAST_LOAD": "1"` in the launcher, commit it (mod references
   resolve from the registry git clone, §4), boot again, record the same line.
3. Three boots each. `full_token` varies boot to boot (upstream saw 6.71–7.27M
   across fast-loader boots alone); a same-config control on either side is part
   of the protocol, and a single pair of boots resolves nothing.
4. `DSV41_FAST_LOAD_N_EXPERTS` was dropped with the gate: it is a fallback for
   expert-count detection that only `fast_load` reads, and it defaults from
   `config.json`'s `n_routed_experts` (384) when absent. Restoring the gate needs
   no restore of this key.

---

## 8. Boot gates (in order) and timings

Read these before believing any number. A boot that reaches ready but fails a
gate is not a win.

1. `[dsv41-sglang-overlay] overlay gate OK` and `launcher: boot.py run NNODES=4
   NODE_RANK=<r> …` — rank must differ per node.
2. `Exact nvme Engram layer=… rows=[a,b)` — row range must **differ per rank**;
   `packed=` names the `/cache/runtime/engram` shard. Missing or identical: stop.
3. `[moe_b12x_next] armed` — routed MoE on the b12x_next kernel, not a Triton
   fallback.
4. `DSV4 memory calculation: … full_token=<N>` — the granted KV pool. With the
   stock loader shipped, expect the larger pool (7.47–7.82M on upstream's EP2
   stack, §7.1); a 6.71–7.27M reading means `DSV41_FAST_LOAD` is on.
5. `Mean acceptance length > 1` on `Decode batch` lines (DSpark working).

**Timings:** boot to ready **~9 min cold**; TTR observed 171–270 s once the
checkpoint and image are resident. A first cold boot also packs Engram in the
background. **Both of those were observed with the fast loader on**, which is not
what ships: the stock loader's weight read is the slow one (~220 s more), so a
fresh boot on the shipped config will land above these figures. They are kept as
the fast-loader reference, not as the shipped recipe's boot time (§7.1).

**Cluster hygiene before any boot test:** a killed/abandoned `sparkrun run`
leaves containers holding the serve port. Because sparkrun uses `--network=host`,
the next boot's healthcheck can pass against the **old** server while the new one
fails to bind — a false "healthy". Check `sparkrun status` /
`docker ps -a | grep sparkrun` on every node first.

---

## 9. Guards and the verification ritual

`tests/test_ds4_recipes.py` is stdlib-only and parses recipe **text** with a
~60-line regex parser (no PyYAML — `tests/` and `tools/` must run on a head node,
in a container, and on a laptop with no venv). It has its own `render()`; guards
inspect the rendered command, not the template. Every guard has a proven
**negative control** (in `SglangLaneNegativeControls`), and controls mutate
strings in memory so nothing on disk is touched. Guards strip whole-line comments
before reading a block, because the recipes' prose *names* the flags it explains
the absence of.

**This guard suite no longer covers the EXL3 / vLLM lane** — those recipes and
their `Exl3LaneContract` guards moved to `attic/ds4/` with them. If the lane is
ever restored, its guards come back with it.

Ritual before any hardware claim:

```bash
set -e
H=$PWD/.local/sparkrun-home; mkdir -p "$H"
uv run python -m unittest discover -s tests
for f in recipes/*/*.yaml; do HOME="$H" sparkrun recipe validate "$f"; done
HOME="$H" sparkrun run recipes/ds4/deepseek-v4.1-flash-knapcio-tp4-1m-sglang.yaml -H <node> -n
for s in mods/*/*.sh; do bash -n "$s"; done
for p in mods/*/*.py tools/*.py; do uv run python -m py_compile "$p"; done
find mods tools -name __pycache__ -type d -exec rm -rf {} +
```

`sparkrun recipe validate` **plain** (not `--strict`): several recipes in the
registry legitimately fail `--strict` on accepted warnings, and a `suggestion`
is not a defect. A clean `validate` is not evidence a recipe boots — read the
rendered line and the boot log.

---

## 10. Measurement discipline (this lane)

- **Quote the harness with the number.** The short-prompt harness (~17-token
  prompts) and the standardized `sparkrun benchmark` profile (2048-token prompts)
  agree at c1 and diverge ~1.9× at c16, because the concurrency cell is then
  dominated by 16×2048 tokens of prefill. The README's `C1 t/s` contract is the
  short-prompt number.
- **C1 is completion-length sensitive.** The bench requests 200 tokens but the
  varied short-answer prompts often stop early, so wall time includes prefill and
  dilutes the effective decode rate. The steady-state C4/C8/C16 columns are the
  robust ones.
- **GB10 inter-boot scatter is 7–25%.** Three runs resolve nothing under ~15%;
  run a same-config control before calling an arm a win.
- **DSpark acceptance is workload-dependent** (~3/step on prose, ~6 on code). A
  DSpark number without an accept length is not a number; state the
  reasoning-effort budget too (`chat_template_kwargs {"thinking": false}` here).
- **Read the served pool from the boot log**, never computed. The loader setting
  is part of the boot's identity: quote `DSV41_FAST_LOAD` with any pool number,
  because it moves the pool 3–13% (§7.1). The fast path logs
  `DSV41 fast load ARMED: …` when it is on and nothing when it is off, so a
  missing ARMED line is the only in-log hint — a bare pool figure does not
  identify which loader produced it. (The launcher's env is also invisible to
  `docker exec env`, §11.)
- **`sparkrun benchmark --profile` resolves from the registry cache**, not the
  working tree. The serve log is `/tmp/sparkrun_serve.log` **inside** the
  container (`docker logs` is empty). Containers are reaped after a run; use
  `--no-rm` to keep one.

---

## 11. Negative results and do-not-retry

- **EP_SIZE=2 does not work.** It loads (clears the MXFP4 MoE `%128` check) but
  dies at the first decode plan: `planned dynamic direct routing is unsupported
  for this launch shape`. The production profile is **EP_SIZE=1**.
- **The SPS ragged-verify table crashes the Engram path** (section 7).
- **Pinning a host adapter or a `snapshots/<hash>` path breaks portability.** The
  former pins one machine's adapter naming; the latter breaks when the cache
  re-resolves (the launcher self-heals it).
- **`docker exec <c> env` is not a valid probe** for anything the launcher sets —
  the launcher rewrites its own environment before `execve`, so `docker exec`
  (a fresh shell) shows the image's baked values. Read the launcher's log and the
  tools' output instead.
- **`sparkrun run --dry-run` skips the InfiniBand detection step**, so it prints
  "No InfiniBand detected" and renders no `NCCL_IB_*` env — a false negative. Do
  not conclude anything about detection from a dry run.
- **The old "SGLang cannot serve V4.1-Flash" verdict is superseded** for this
  purpose-built image. It was correct for the published images available at the
  time (no single image was both V4.1 and b12x; the MXFP4-Cutlass MoE rejected
  the TP=4 partition).
- **`MEM_FRACTION_STATIC=0.90` wedges GB10 nodes (2026-10-06 incident).** Probing whether a higher
  fraction raised the KV budget (it does not: the ceiling is the 0.80 `full_token`) wedged the head
  `.30` and workers `.31`/`.32` — SSH refused (banner timeout) for >10 min while ping stayed up.
  `.30`/`.32` recovered (`.30` after a reboot); **`.31` went fully unreachable (no ping)** and had
  not returned at session end. Lesson: on GB10 the GPU pool *is* host memory, so a fraction above
  ~0.80 can exhaust the host and kill userspace. **Keep 0.80.** Recovery for a wedged node is a
  reboot; there is no in-band path (`ipmitool` present but no `/dev/ipmi0`, no BMC documented).
- **The knapcio radix/prefix cache did not hit (measured 2026-10-06).** Back-to-back requests with
  identical prompts still logged `#cached-token: 0`, despite `disable_radix_cache: False` /
  `radix_eviction_policy: lru`. The DSpark/bounded-replay serving path does not retain short-prompt
  prefixes the way stock SGLang's radix cache does — a lane behaviour, not a pool-pin regression.
  Do not assume prefix-cache reuse when sizing web/agent workloads here; the README's "warm context
  is near-instant" language carries the same caveat.

---

## 12. TensorFold TP=2 lane (`deepseek-v4.1-flash-tensorfold-tp2-1m-sglang.yaml`)

A second, independent lane in this directory: DeepSeek-V4.1-Flash on **two**
GB10 nodes, served by the TensorFold `deepseek_v41` engine over the Mia-AiLab
**EXL3 2.9bpw** checkpoint. It does not share code with the knapcio SGLang lane
above; read this section before touching it.

### 12.1 What it is

- Model anatomy: DeepSeek-V4.1-Flash, **552 B** params, **40** layers, `hidden_size` 5120, MoE with
  **384** routed experts (top-6). Two Engram tables (~203 GB) hold the FP8 embedding rows.
- Engine: [`bertholomus/TensorFold`](https://github.com/bertholomus/TensorFold),
  branch `deepseek-v41-tp2`, a fork of [ashhart/TensorFold](https://github.com/ashhart/TensorFold)
  v0.6.3 (Apache-2.0), pinned in `Dockerfile.tensorfold-dsv41` at
  `d5d7bb389ddf4325c1edf4a15dd1c23727040ea1`. The `deepseek_v41` family is a clean-room
  re-implementation of DeepSeek's MIT inference code; the fork's `tools/dsv41/ATTRIBUTION.md`
  records every source.
- Checkpoint: `Mia-AiLab/DeepSeek-V4.1-Flash-EXL3-2.9bpw` (~197 GB, 39 shards, MIT). Verified
  present on the trial pair (`.34`/`.35`): 49 files / 196.2 GiB, 39 shards totalling
  210,600,939,078 bytes, `bad=0` structural check. (The directory reads as a few MB under `du`
  because the shards are symlinks into the HF blob store — measure with `find -L … -printf %s`.)
  TensorFold's CUDA engine reads **EXL3 only** (`families/deepseek_v41/__init__.py`:
  `QUANT_METHODS = {"cuda": ("exl3",)}`, `check()` refuses any other `quant_method`), so the
  official MXFP4 checkpoint will not load here. The EXL3 repo's `config.json` has
  `model_type: deepseek_v41`, which is what `families.detect()` keys on.
- Engram: the EXL3 quant left the two FP8 Engram tables native; they are **not** in the EXL3
  repo. The engine reads them from DeepSeek's original shards **47 and 48** (~95 GB each), which
  carry `layers.{1,14}.engram.embed.{weight,scale}` and the `q_weight`/`k_weight` linears.
- Context: the served command ships the model's **full 1,048,576-token window** (see 12.13 for why
  the maximum context and the maximum KV cache are the same change here). Upstream measured its lane
  at 262,144 and found a needle at 1,039,833; the ceiling the engine enforces is 1,048,576.

### 12.2 Files and the call chain

```
recipes/ds4/deepseek-v4.1-flash-tensorfold-tp2-1m-sglang.yaml   (runtime: sglang -- the shim path)
  mods: "@littlecedar/mods/tensorfold-dsv41-launcher"
    run.sh        # fail-closed gate: tensorfold on PATH, launcher.py + HF cache present;
                  #   creates + re-owns /cache/runtime/tensorfold/{rank-cache,torch-extensions}
    launcher.py   # RECIPE_ENV production config; --dist-init-addr/--nnodes/--node-rank -> TensorFold flags
      -> execvp: tensorfold serve <MODEL_DIR> --tp 2 --rank R --master HOST --master-port PORT ...
```

The recipe's `command:` is a one-line call to the shim:

```
python3 /workspace/mods/tensorfold-dsv41-launcher/launcher.py --boot
  --model {model} --port {port} --tp {tensor_parallel}
  --served-model-name {model} --context {max_model_len}
```

sparkrun appends `--dist-init-addr HOST:PORT --nnodes N --node-rank R` to every node's serve
command; the shim consumes all three.

### 12.3 Why `runtime: sglang` and a shim (not a custom runtime plugin)

sparkrun's runtime vocabulary is a fixed set of in-tree `RuntimePlugin`s plus feature-gated
external plugins (`core/bootstrap.py`, `core/external_plugins.py`); an unknown `runtime:` name is
fatal at launch, and there is no YAML-only way to define one. The established house pattern — used
by the knapcio lane just above — is to declare `runtime: sglang`, give the recipe an explicit
`command:` template, and let a mod's Python shim consume sparkrun's appended node flags and exec a
foreign engine. This lane does the same, and inherits sparkrun's model/image distribution, the
InfiniBand/NCCL env probe, the managed runtime cache, and the readiness watcher for free. A custom
`RuntimePlugin` would be cleaner in the abstract, but it requires an out-of-tree plugin on every
node's `plugins.paths`, which is a bigger deployment surface than one mod.

### 12.4 The two load-bearing shim behaviours

1. **The rendezvous port must be passed through.** sparkrun's native-cluster launch waits for the
   head to open the rendezvous port before it starts the workers, and the port it gates on is the
   one in `--dist-init-addr` (`runtimes/_cluster_ops.py` `gate_port`; default 25000). TensorFold's
   `TCPStore` binds `--master-port` (its own default is **29551**). The shim therefore parses
   `--dist-init-addr HOST:PORT` and emits `--master-port PORT`; if it did not, the head would open
   29551 while sparkrun polls 25000 and declare the launch dead.
2. **The rank comes only from `--node-rank`.** sparkrun passes it to the head (0) and the worker
   (1); the container environment carries no rank. Only the shim sees it, so the shim sets
   `--rank`. Getting it wrong makes both ranks act as rank 0 (the `TCPStore` then has a duplicate
   server and the NCCL unique-id handoff breaks).

TensorFold's rank 0 serves HTTP and drives the rounds; rank 1 follows it (`engine.follow()`).
sparkrun launches the head first and waits for the rendezvous port, then starts the worker in
parallel; because TensorFold's rank 1 blocks in `TCPStore(...)` until rank 0 opens the store, the
head-first order is the one that works (do not be misled by upstream's "start rank 1 first" — that
advice is for starting the *processes* by hand, where the worker must be listening before the head
connects its `Link`/`Watchdog` sockets).

### 12.5 The mod (`mods/tensorfold-dsv41-launcher/`)

`run.sh` is a fail-closed pre-serve gate. It asserts `tensorfold` is on PATH, `launcher.py` exists,
and `/cache/huggingface/hub` is mounted; it creates and `reown`s the managed runtime cache
subdirectories the launcher writes. It modifies no image file and does not fail closed on a missing
Engram directory (the engine loads without them and only prints a warning — see 12.7).

`launcher.py` owns the production configuration (`RECIPE_ENV`), resolves the checkpoint, and execs
`tensorfold serve`. The env it sets:

| Env | Value | Why |
|:--|:--|:--|
| `TF_DS_REPLAY` | `1` | bounded decoder replay (DeepSeek's deployment mode); the engine default is exact prefill, which is slower and can OOM at 128K |
| `TF_DS_PREFILL_CHUNK` | `2048` | upstream's served chunk |
| `TF_DS_RANK_CACHE` | `/cache/runtime/tensorfold/rank-cache` | ~106 GiB/rank weight cache; paid once per host |
| `TF_DS_RANK_CACHE_READERS` | `32` | upstream's value |
| `TF_DS_WARM_LENGTHS` | `1,17,33,131,514,1024,2113` | upstream's warm-up lengths |
| `TORCH_EXTENSIONS_DIR` | `/cache/runtime/tensorfold/torch-extensions` | persist the first-start CUDA-extension compile |
| `TF_DS_TOKEN_MAP` | `/cache/runtime/tensorfold/token_map.json` | Engram hash table, built once from `tokenizer.json` |
| `TF_DS_ENGRAM` | `/cache/huggingface/hub/dsv41-engram` | set only when safetensors tables are present (§12.7) |
| `HOME` | `/cache/runtime/tensorfold` | the container runs as the ssh user, who may lack a writable home |

`serve` always runs with `--parallel 4 --mtp-drafts 5 --temperature 0 --no-update-check`. The first
three are upstream's served line; `--no-update-check` keeps the boot off the network.

**Local trials with a new/changed mod.** The `@littlecedar/…` reference (§4) resolves from the node's
registry clone, so it only sees committed+pushed mods. To trial a *new* mod before pushing, copy the
recipe to a scratch directory, point its `mods:` at a **relative** ref, and place a `mods/` symlink
beside it so sparkrun's adjacent-to-recipe resolution finds it:

```bash
# .scratch/ds4/boot_tf2x/recipe.yaml -> mods: "tensorfold-dsv41-launcher"  (relative, not @littlecedar/)
ln -s ../../../mods .scratch/ds4/boot_tf2x/mods
```

Then `sparkrun run` rsyncs the mod to the head's staging dir.

### 12.6 Checkpoint resolution

The shim resolves the checkpoint through the fixed HF cache mount. On a **real launch** sparkrun
renders `{model}` as the **prepared on-disk snapshot path** (it rewrites the placeholder for any
recipe with a `command:` template — `models/runtime.py::bind_runtime_models` — and a dry run still
prints the repo id), which the shim's `Path(repo).is_dir()` passthrough takes as-is. A repo id
(manual invocation, or `-o model=...`) is instead resolved in the fixed HF cache mount:
`/cache/huggingface/hub/models--Mia-AiLab--DeepSeek-V4.1-Flash-EXL3-2.9bpw/snapshots/<hash>` via
`refs/main`, else the newest config-bearing snapshot. No `snapshots/<hash>` appears in the recipe, so
a cache re-resolving to a new hash cannot break it. The same rewrite reaches
`--served-model-name {model}`; `served_model_name()` normalizes the path back to the repo id, so
the engine does not advertise a filesystem path. Verified live (2026-10-13): tensorfold boot
`8ef9b6c9a550c389_3510a5e0d37d` on `.34+.35`, `GET /v1/models` →
`littlecedar/DeepSeek-V4.1-Flash-EXL3-2.9bpw-with-engram` (owned_by `tensorfold`, 1048576 ctx,
TTR 56.0 s); the knapcio production serve `a4c699c1299bbbdf_8296561cc1cb` (`.30`) answers
`deepseek-ai/DeepSeek-V4.1-Flash`.

### 12.7 Engram is fetched from the online repo (was: distributed out-of-band)

The two Engram tables are **not** distributed by sparkrun, and they are **not** in the EXL3
checkpoint: they belong to the *official* `deepseek-ai/DeepSeek-V4.1-Flash` repo, where they are
shards 47/48 (~101.5 GB each). Pulling that whole checkpoint just to reach 189 GiB of tables ships
~285 GB the engine never reads — so the recipe no longer depends on anyone having copied the shards
onto the node by hand. It carries `mods/dsv41-engram-fetch`, which builds the tables **on each runner
node from the online repo**:

```bash
# exactly what the mod runs (canonical source: tools/build-dsv41-engram.py):
python3 build-dsv41-engram.py \
  --out /cache/huggingface/hub/dsv41-engram --workers 24
# offline completeness check; exit 0 = complete:
python3 build-dsv41-engram.py --check --out /cache/huggingface/hub/dsv41-engram
```

**How it avoids materializing the 285 GB checkpoint.** It fetches only the repo's
`model.safetensors.index.json` (~7 MB) and the two shard headers (656 / 664 B) to locate the four
`engram.embed.{weight,scale}` tensors, then **range-copies** each tensor's byte span from the HF CDN
(`curl`-style `Range:` GETs, 206 responses; unauthenticated). It never downloads a whole shard.

**What it emits, and why that is the right format.** The TensorFold reader
(`families/deepseek_v41/cuda/model.py: class Engram`) globs `*.safetensors` in `TF_DS_ENGRAM` and, per
`*.engram.embed.weight` / `*.engram.embed.scale`, records `(fd, 8 + header_len + data_offsets[0],
row_bytes=prod(shape[1:]))` and reads row `i` at `base + i*row_bytes`. So the mod writes one
`engram-l<L>.safetensors` per layer, each holding that layer's `.engram.embed.weight`
(`F8_E4M3 [N,256]`) and `.engram.embed.scale` (`F8_E8M0 [N,8]`) as two contiguous planes — the reader
contract, satisfied verbatim. (The knapcio **TP=4** lane instead reads a repacked 264-byte-record
`.bin`; the same tool emits that too via `--format packed --tensor-parallel 4 --rank R`, for parity
with `scripts/pack_engram.py`, but the TP=2 lane does not use it.) The source's sibling
`engram.wkv`/`q_weight`/`k_weight` are deliberately **not** copied: they belong to the quantized
weights and are already in the EXL3 checkpoint.

**Bounded memory (the reason it is not a plain download).** A GB10 has ~117 GB usable unified memory
and the source is 189 GiB, so a snapshot-then-read does not fit. The writer bounds each in-flight
range, writes straight to disk, and advises written pages `POSIX_FADV_DONTNEED`. Measured `VmHWM`
**0.6 GiB** while writing 94 GiB on `.34`. One ranged request per 256 MiB segment also keeps the
request count low enough to avoid HF `429` (per-chunk requests, ~12k of them, trip it).

**Verified 2026-10-06 on `.34` (task-allowed node).**
- Layer 1 built: 94.4 GiB in 411 s (235 MiB/s), exit 0, 0 retries, peak RSS 0.6 GiB.
- Byte-identical to the node's authoritative checkpoint shard 47: full-file **SHA256 match on both
  planes** (`ada3f1b3…` weight, `75a1a081…` scale), and 300/300 random rows equal via the engine's
  own `tensorfold…weights.Shards.get(rows=…)` accessor.

**Not blocking, and idempotent.** The mod launches the fetch **detached** (`setsid nohup`), so a cold
first boot is not gated on the CDN; the engine serves with the degraded warning and picks the tables up
on the next boot. It renames `.partial` files to their final names only once **every** layer is
complete, so a glob never sees a half table. A complete directory makes the mod a no-op
(`--check` exit 0). `MOD_ENGRAM_WAIT=1` blocks the launch until the tables are on disk instead.

If the directory is absent, the engine still boots and serves, with
`[tensorfold] WARNING: no Engram tables (TF_DS_ENGRAM): output will be degraded`; the mod and shim
both report the state without failing. `_default_engram()` also looks for a `*Engram*` sibling of
the model directory, but that location is inside the HF cache and would be wiped by a cache re-sync.

Measured legacy staging (2026-10-05, the manual path this mod replaces): **189.1 GiB** staged, shards
47/48 at 101.5 GB each. The staging directory reads as a few MB under `du` only because the shards are
symlinks into `~/.cache/huggingface/hub/blobs/XX/…`; measure real bytes with `find -L … -printf %s`.

Guards: `tests/test_dsv41_engram_builder.py` (stdlib-only, network-free) re-implements the reader's
addressing rule and proves the emitted bytes satisfy it; it also pins the recipe's mod order
(fetch before launcher), that the builder bundled in the mod is byte-identical to `tools/`, and that
the synchronous fetch is timeout-bounded (below).

**Boot-verified 2026-10-06 on `.34`/`.35` (Engram deleted first).**
- A boot with the fetch **synchronous** (`-e MOD_ENGRAM_WAIT=1`) fetched the full 189 GiB inside the
  recipe's pre-serve hook on `.34` and published both tables; but the fetch took longer than
  sparkrun's pre-exec hook timeout, so the *launch* was killed with
  `SSH script <- .34 TIMEOUT after 600s` / `pre_exec[2] failed`. The detached fetch survived
  the teardown and finished (files verify clean with `--check`).
- The default **detached** boot: `.34` had the tables and the mod was a **no-op**; `.35` was empty
  and the mod launched the detached fetch (which completed in **820 s, 236 MiB/s**), while the boot
  proceeded.
- After provisioning both nodes, a **fresh boot reached ready in ~70 s**; `/health` answered, the
  served model returned a completion, and **both** engine ranks held
  `TF_DS_ENGRAM=/cache/huggingface/hub/dsv41-engram` with `engram-l1.safetensors` and
  `engram-l14.safetensors` open — i.e. the fetched tables are what the served engine uses, not the
  degraded fallback.

**Shipping constraints this surfaced.**
1. *The pre-exec hook is a 600 s window.* A blocking fetch failed the launch here
   (`pre_exec[2] failed … TIMEOUT after 600s`), and on a slow Internet link a fetch can
   run for hours. The mod therefore **never blocks**: it always launches the fetch
   detached (`setsid nohup`) with a wrapper that re-owns the output and records the exit
   code; `MOD_ENGRAM_WAIT` is accepted but ignored. The engine serves degraded until the
   tables land and uses them next boot, so no launch is ever killed by the fetch.
2. *Pre-warm out-of-band on slow links.* `tools/build-dsv41-engram.py` is a standalone
   CLI (`--detach` launches it in the background, `--status` polls it, `--check` verifies
   it offline) and writes the host HF cache the container bind-mounts when run on a node
   with a bare `--out`. It resumes from its progress cursor, so a dropped ssh session or a
   stopped container does not lose work. This is the recommended path for a fresh
   deployment.
3. *Or let sparkrun distribute it.* `sparkrun` distributes **per model repo**
   (`distribute_model_from_head` rsyncs `model_cache_path(model_id)`, i.e. the whole
   `models--<org>--<name>` dir), so a second `distribution_config.models.entries` entry is
   downloaded once on the head and rsynced to every worker — verified 2026-10-06, a second
   entry rendered `Distributing model … / Model '…' synced from head to 1 worker(s)`. When
   a repo carrying the tables is pinned in the recipe, the launcher
   (`resolve_engram_dir`) reads them from that cache dir. This turns N×189 GiB of
   Internet egress into one download plus a fabric rsync. It depends on such a repo
   existing (and being trusted — pin and vet the revision); the recipe ships it commented
   out and keeps the self-contained fetch as the default.
4. *Ranks must agree on Engram.* `--tp 2` decodes on both ranks in lockstep. If exactly one rank has
   the tables (e.g. a detached fetch completes on one node between two boots), rank 0 serves from
   Engram while rank 1 is degraded — a divergence that **hangs at readiness** (`Waiting for server
   readiness...`, no `/health`). Boot with the tables **present on all ranks** (the detached fetch
   completes on every node on its first run; a `--check`-verified pre-warm can force it).

### 12.8 The image

`littlecedar/dgx-spark-dsv41@sha256:fabbe8615bb91c61fdde4a5f451f324a7449d7335fb85d453cc439985c525495`
(tag `tensorfold-tp2`), arm64-only, 33.8 GB. Source: `recipes/ds4/Dockerfile.tensorfold-dsv41`.

Base: `lmsysorg/sglang:dev-cu13` (digest `sha256:aa878e8d…`). It already carries everything the
engine compiles and links against — nvcc 13.0 + ninja, torch 2.13.0+cu130, triton 3.7.1,
libibverbs + headers (`<infiniband/verbs.h>`), libnccl.so.2, and the Python deps (numpy,
safetensors, tokenizers, huggingface-hub, jinja2, and also transformers/Pillow/xgrammar for the
vision and grammar paths). The build therefore does exactly one thing: `git clone` the fork at the
pinned commit and `pip install --no-deps .`. `--no-deps` is deliberate; installing with deps drags
a second torch and an `nvidia-nccl-cu13` wheel over the base's own, and the engine links the base's
libnccl by name (`cuda/comm.py`). The build ends with a gate that imports the engine, registers the
family, imports every runtime dep, and runs `tensorfold --version`.

Rebuild:

```bash
# on the arm64 head node, from a clone of the fork (the Dockerfile needs the repo context only
# if you COPY it; it git-clones the pinned ref itself, so build from an empty dir is fine)
docker build -f Dockerfile.tensorfold-dsv41 -t littlecedar/dgx-spark-dsv41:tensorfold-tp2 .
docker push littlecedar/dgx-spark-dsv41:tensorfold-tp2
# then pin the returned digest in the recipe's container: line
```

Bumping the engine is one `ARG TENSORFOLD_REF=...` change.

### 12.9 Boot gates and a healthy boot

1. `[tensorfold-dsv41-launcher] overlay gate OK` and `tensorfold: /…/tensorfold 0.6.3`.
2. `[tensorfold] loading DeepSeek-V4.1-Flash … on CUDA, rank R of 2`.
3. First boot only: `building CUDA extension …` (torch JIT; subsequent boots reuse
   `/cache/runtime/tensorfold/torch-extensions`) and the ~106 GiB/rank rank-cache write.
4. `[tensorfold] rank R: allocator ceiling …`.
5. `[tensorfold] DeepSeek-V4.1 engine ready: 2 rank(s), context 1048576, DSpark 5 drafts`.
6. `[tensorfold] rank 0 serving … at http://0.0.0.0:8000/v1` and `Mean acceptance length > 1` on
   decode (DSpark working). A boot that serves but accepts nothing is a failure.

With no Engram shards, expect the degraded warning from 12.7 between 2 and 5.

### 12.10 Guards

`tests/test_ds4_recipes.py` pins this lane with **`TensorfoldLaneContract`** (and
`TensorfoldLaneNegativeControls` for the mutations). It is stdlib-only and imports the shim
module directly, so it runs on a head node, in a container, or on a laptop. It pins:

- the image digest (`fabbe861…`) and `builder: docker-pull`;
- `runtime: sglang` over the **EXL3** checkpoint (`Mia-AiLab/…-EXL3-2.9bpw`) — swapping in the
  official MXFP4 repo must fail, since the engine's `family.check()` refuses a non-`exl3`
  `quant_method`;
- TP=2 = `min_nodes` = `max_nodes` = 2, and every `defaults:` key consumed by a `{placeholder}`;
- the `@littlecedar/mods/tensorfold-dsv41-launcher` reference, no host bind mounts, no pinned
  adapter names / sparkrun-managed comm env;
- the shim's two load-bearing behaviours **by executing `main()`** with `os.execvp` stubbed:
  `--dist-init-addr HOST:25000` → `--master HOST --master-port 25000` (not the engine's 29551
  default), and `--node-rank R` → `--rank R`; plus RECIPE_ENV reaching the child and a missing
  Engram dir leaving `TF_DS_ENGRAM` unset rather than failing.

What the guard **cannot** see is a real boot: the CUDA-extension compile, the rank-cache write, the
DSpark acceptance rate, and the rendezvous actually meeting. Those still need a render
(`sparkrun run … -n`) plus a launch and a reading of the boot log. Note that a launch from the
repo also needs the mod **committed and pushed** first (the `@littlecedar/` form resolves from the
node's registry clone, §4) — a local trial that must not wait on the push can copy the recipe to a
scratch dir and use the relative mod ref beside a `mods/` symlink.

**Non-boot verification (before any launch).** `sparkrun show <recipe>` parses it, and
`sparkrun run <recipe> -n` renders the full serve command and a clean 2-node cluster plan; mod,
image, and model distribution all resolve there. This confirms the mapping on paper — it does not
prove a boot (see the paragraph above).

### 12.11 Measurement discipline

- Upstream's numbers (2× GB10, greedy, DSpark k=5, 384-token prompts): C1 code 101 / prose 62 /
  structured 142 t/s; 4 concurrent 112 t/s; prefill 1.7–2.0k t/s at 8K–128K; start-to-ready 36 s
  warm. These are **upstream's**, measured on their nodes, not ours. Quote them as such.
- **Our own measurement (2026-10-05, .34/.35).** One greedy request, a mixed code/prose prompt,
  288 prompt / 256 completion tokens: **73.0 tok/s** decode (`completion_tokens / decode_s`), DSpark
  95 rounds, 262 drafted / 160 accepted → **mean acceptance 2.76 tokens/round**. 73 t/s sits inside
  upstream's 62–101 band, as a mixed prompt should. Note the engine's own `tensorfold.prefill_s`
  (0.94 s for 288 tokens ≈ 305 tok/s) is overhead-dominated at this prompt size — do **not** quote it
  as a prefill figure; a prefill number needs the 8K–128K shape.
- **Boot timings, ours.** Cold (first ever): rank-1 weight load 312 s while writing a ~106 GB
  rank cache, rank-1 ready 507 s, engine `loaded in 511.3 s`. Warm (rank cache present): rank-1
  weight load **25 s**, rank-1 ready **43.3 s**, sparkrun TTR (port open) **51.4 s**. A first-ever
  launch also pays a one-time ~510 s head→worker model sync (see 12.12). The rank cache persists
  across `sparkrun stop`/`run` because it lives under the managed `/cache/runtime`.
- **Memory, ours (cold boot).** Each rank holds ~**98.8 GiB** of EXL3 weights (`rank 0: weights in
  299 s`, `rank 1: 312 s`), plus KV + workspace; the engine's allocator ceiling was **107.1 GiB
  (rank 0) / 107.8 GiB (rank 1)**, all inside the node's 128 GB unified pool. Rank-cache files are
  ~106 GB each on disk.
- The EXL3 checkpoint is a lossy quant, but its **quality is now measured** (2026-10-06), *not* a
  caveat: on the house hard tier it scores **17/18**, identical to the knapcio official-weights
  lane, and the 11-bench hard battery (~1,900 paired items) is **every bench a tie** (paired
  McNemar, no p < 0.05; largest gap AIME +4.4 pp, discordant 6-vs-10, p=0.45). So parity is
  evidence, not hope — the earlier "quality unmeasured, do not imply parity" warning is
  **superseded**. Detail and method: §13 and `benchmarks/`.
- **DSpark acceptance is workload-dependent.** Our 73 tok/s single-stream figure carried a mean
  acceptance of 2.76 tokens/round (a healthy >1); upstream reports ~3/step on prose and ~6 on code.
  A TensorFold speed number without its accept length is not a number.
- `--parallel 4` shares one 1M window; concurrency and per-stream context-length trade off (12.13).
- The rank cache is a boot-time optimization only; its first write is not part of a warm boot.

### 12.12 Negative results / gotchas

- **The official MXFP4 checkpoint will not load**: `check()` rejects `quant_method != "exl3"`.
- **`--dist-init-addr`'s port is not decorative**: see 12.4; drop the mapping and sparkrun declares
  the head dead.
- **sparkrun launches the head first**, not rank 1; see 12.4.
- **Engram is not sparkrun-distributed**; a fresh node without the shards serves degraded, silently
  except for one log line. Pre-warm per 12.7.
- **sparkrun re-syncs the model head→worker on launch even when both nodes already hold it**, over
  the management net (`the plane-B rail addresses`) at ~400 MiB/s — 510 s for the 196 GiB checkpoint. It is a
  one-time cost per (head, worker) pair, but it dominates the first launch and is easy to misread
  as a hang during `[3/6] Distributing resources`. The rsync uses `--copy-unsafe-links`, which
  materializes the blob symlinks, so on the receiving node the model directory's real bytes must be
  measured with `find -type f -printf %s`, not `du` on the model dir (which sees only symlinks).
- **`docker exec <c> env` will not show `RECIPE_ENV`**: the shim rewrites its own environment before
  `execvp`, so a fresh shell shows the image's env, not the launcher's. Read the launcher's log line.
- **Launch detached.** A long `sparkrun run` must be started as `setsid nohup sparkrun run … &`, or a
  tool call that times out kills the launch mid-boot.
- **`sparkrun status` / `sparkrun metrics` need `-H`** (`-H .34,.35`) or they have no
  nodes to query.

### 12.13 Context window and concurrency (measured 2026-10-05)

**Hard ceiling: `--context` ≤ 1,048,576 — the model's trained window. Not one token more.** The
recipe **ships at this ceiling** (`max_model_len: 1048576`), because `--context` *is* the KV pool
here, so the largest possible context and the largest possible cache are the same change. The
engine refuses anything larger *before it loads a weight* (`cli.py:355`):

```python
if native_context and context > native_context:
    raise ValueError(f"--context {context} exceeds this model's {native_context}-token window")
```

`native_context` is `config.json`'s `max_position_embeddings` (= `1048576` here). Verified on the
trial node: `--context 1048577` → refused with that exact message; `--context 1048576` → loads.
Note this family does **not** call `cuda.capacity.admit` (which clamps to `min(target, native)`) —
the ceiling is the CLI check, and below it the window is simply `self.limit = context` with no
memory-based reduction.

**So yes — the shared KV pool is capped at 1,048,576, and it is not a memory cap.** Two things to
hold together:

1. *The pool size IS `context`.* `new_pool(cap=context + max_rows + 8)`. There is no separate,
   larger pool the window is merely a slice of.
2. *`context` cannot exceed the model's trained window.* `config.json` shows why 1,048,576 is not
   arbitrary: `rope_scaling` is YaRN with `original_max_position_embeddings: 65536, factor: 16`, and
   65,536 × 16 = 1,048,576. Past that the model has no valid positions, so the engine refuses to
   start rather than emit nonsense.

Memory is nowhere near binding. The KV cache is MLA — one shared latent KV head
(`num_key_value_heads: 1`, `head_dim: 512`) — so the marginal cost is only **~2.9 KiB/token**.
Measured: rank 0's warm-up `reserved` is **100.82 GiB at context 262144** and **102.98 GiB at
1048576** — i.e. the entire extra 786,432 tokens of window costs **2.16 GiB** per rank. Tens of
millions of tokens would fit in 128 GB; the model simply has no positions for them. So the cap is
the architecture's position range, not the hardware.

Because it is *one* pool, that 1,048,576 figure is the **sum** of all concurrent streams' extents,
not a per-stream allowance — hence "shared". Four streams can only coexist if their extents sum to
≤ 1,048,576.

**Do not carry the knapcio lane's KV numbers over to this one.** They are different engines with
different KV models, and the mistake is easy because both are `runtime: sglang` and both serve the
same model:

| | knapcio TP=4 (README "Caveats" §) | TensorFold TP=2 (this section) |
|:--|:--|:--|
| Engine | real `sglang.launch_server` + `dsv41-sglang-overlay` | `tensorfold serve` (shim) |
| Pool control | `MAX_TOTAL_TOKENS` → sglang's `--max-total-tokens`, **pinned at 9400000** in `mods/dsv41-sglang-overlay/launcher.py` | **`--context` itself**; no pool flag exists |
| Window vs pool | `CONTEXT_LENGTH` (per-request, clamped 4096..1048576) **separate** from the pool | same number — `cap = context + max_rows + 8` |
| B/token/rank | ~1,670 (TP4: ~77 GiB of weights/rank leaves room) | ~2,900 marginal, and only ~2.1 GiB nominal |
| Pool capacity | `MAX_TOTAL_TOKENS=9400000` pinned (ceiling ≈9.5–9.6M); the boot line's `full_token` is the *budget* the host allows | 1,048,576 total, ever |

Confirmations run 2026-10-05: TensorFold exposes **no** pool/total-tokens flag
(`serve --help` has none) and **no** env that sets one (grep of `families/deepseek_v41` for
`environ` shows only `TF_DS_TOKEN_MAP` and tunables). Both lanes therefore reject
`--context`/`context_length` above 1,048,576 for the *same* reason — the YaRN position range — but
knapcio *can* hold many 1M streams while TensorFold cannot hold more than one.

The `full_token=` figure in knapcio's boot line is the **maximum budget the host memory allows**,
not tokens the server holds. The server pins `MAX_TOTAL_TOKENS` under it (9,400,000 as of
2026-10-06, up from 4,000,000). Crucially the pool is **page-shared, not extent-reserved**, so a
"how many 1M streams fit" question is not `pin ÷ 1M`: 16 concurrent 1M-claiming requests all ran.
The bound is `MAX_RUNNING_REQUESTS` and total *actual* tokens. Our measured receipts are in §7.1;
the "~7.5M → 6.6 streams" pair once quoted in the README mixed a budget figure with arithmetic and
ignored the page-shared model. Corrected there and in §7.1.

**`--context` is the shared KV pool, not a per-request allowance.** At startup rank 0 prints

```
[tensorfold] --parallel 4: 4 streams share one window of <context> tokens (an extent each)
```

`families/deepseek_v41/cuda/model.py::new_pool` implements it literally — "One window of `cap`
positions that up to `slots` streams share by extents" — and `engine.py:130` sets
`cap = context + max_rows + 8`. So `--context N` means: *the whole KV cache is N tokens, and every
concurrent stream carves its extent out of it.* A stream's extent is `prompt + its max_tokens +
draft rows` (`MultiDecoder._need`), and `extents.take` first-fits it into the one window. A request
whose prompt+reply exceeds `context` is rejected up front with `context_length_exceeded`.

**Consequence — you cannot have 4 full-1M streams.** One 1M stream consumes the entire window, so a
second cannot be admitted until the first frees its extent. Total concurrent tokens ≈ `context`,
not `4 × context`.

Measured on the trial pair (`.34`/`.35`), 4 concurrent requests each declaring its own reply length,
reading `streams.decoding` from `/health`. The recipe now ships at 1,048,576; the 262,144 column is
kept because vendoring all cache in one shared pool makes the difference stark and load-bearing:

| 4 concurrent requests, each `max_tokens` | context 1,048,576 (shipped) | context 262,144 (the old value) |
|:--|:--|:--|
| 2,000 | **4** | **4** |
| 200,000 | **4** | — |
| 250,000 | **4** | **1** |
| 300,000 | **3** | — |
| 500,000 | **2** | — |
| 900,000 | **1** | — |

So, exactly:

- **Full 1M trained context: yes, shipped.** The recipe boots at `max_model_len: 1048576` (verified:
  `/v1/models` reports it, `context 1048576` in the ready line); it is needle-tested upstream to
  1,039,833 tokens. A single stream may use the whole 1M window.
- **Maximum concurrency (4) holds up to `max_tokens ≈ 250K`** at context 1M (measured: 4 at 250K,
  3 at 300K). `4 × 250K = 1M` is the budget.
- **Raising 262,144 → 1,048,576 strictly improves concurrency.** At 262K, four requests each
  declaring a 250K reply collapsed to **concurrency 1**; at 1M the same four give **4**. The larger
  pool is a superset — it can always serve anything 262K could, plus more.
- **Decode speed is unchanged by the larger pool** (measured, median of 3, same 288/256 prompt as
  the 73 tok/s figure in 12.11): **72.5 tok/s at context 1,048,576** vs 73.0 at 262,144, identical
  `drafted=262 accepted=160`. Pool pages are touched only as used, so an idle 1M window costs
  nothing at decode time.
- `--parallel 4` is a **hard cap**: 8 tiny concurrent requests still peaked at
  `streams.decoding = 4` (the other 4 waited).

Practical guidance: the largest per-request window that still keeps C concurrent streams is about
`context / C`, minus the prompt and draft rows. Shipping 1M therefore sets the widest possible
operating envelope; a client that declares a smaller `max_tokens` gets more concurrency, and one
that declares a huge one gets the whole window. Memory is *not* the limit — the window is a fixed
allocation made at admission, and the `--parallel` lanes share one forward pass rather than
multiplying the cache.

Caveat: the concurrency numbers come from the engine's `/health` `streams.decoding` counter, not a
tokens/sec benchmark; they establish the admission law. The decode figure is a real measurement
(median of 3) but of one prompt shape.

### 12.14 Vision (image input) — TP=4 yes, TP=2 no (as shipped)

The model is multimodal (DeepSeek-ViT encoder; `image_token_id` 129264), and the two lanes differ in
whether the shipped recipe exposes it. **This is a recipe/launcher property, not a checkpoint one** —
both checkpoints carry the tower.

**TP=4 (knapcio) — vision is ON and exercised every boot.** The image's `boot.py` `smoke()` sends a
generated PNG through `/v1/chat/completions` as an `image_url` part and asserts the reply names the
red circle and blue square (and `image_tokens == 1024` when the usage block reports it). `smoke()`
runs unless `SKIP_SMOKE=1`; the launcher leaves `SKIP_SMOKE` at its default `0`, so the check runs on
every boot. VERIFIED on our fleet — three boot logs end with
`Structured output, tool round trip and full-budget native vision passed.`
(`.scratch/ds4/knapcio_boot.log`, `.scratch/ds4/knapcio/logs/boot9-head-serve.log`,
`.scratch/ds4/verify94/run.log`), and the serve log shows the multimodal path arming
(`Multimodal processor concurrency enabled`, `Using triton_attn as multimodal attention backend`,
`Reserving 0.10 GB of the KV budget for post-sizing multimodal allocations`). The recipe now carries
`vision` in `metadata.tags`.

**TP=2 (TensorFold) — vision is OFF as shipped.** The engine *supports* it: the `deepseek_v41` family
declares `CUDA_VISION = True` and ships `families/deepseek_v41/cuda/vision.py` (the ViT, the aligner,
and the image spans), and the fork's `tools/dsv41/REPORT.md` §1 lists the served line as
`--vision --parallel 4 --mtp-drafts 5` with **6/6 image-input checks passing**. But `--vision` is an
opt-in CLI flag (default off; no env enables it), and the shipped
`mods/tensorfold-dsv41-launcher/launcher.py` does **not** pass it — its `tensorfold serve` line is
`--tp 2 --rank R --host … --port … --context … --parallel 4 --mtp-drafts 5 --temperature 0
--no-update-check --name …`. So the recipe serves **text only**; an `image_url` part is refused
(HTTP 400). The recipe therefore does **not** carry `vision`.

**What enabling TP=2 vision takes — now VERIFIED on our hardware (2026-10-06).** Ran on
`.32`/`.33` (head `.32`). Two changes, both required; with both, image input works.

1. **Add `--vision` to the launcher's serve line.** The engine then loads the tower on rank 0 and
   every rank routes image spans with the gates' VL bias.
2. **Supply the VL routing bias.** The EXL3 checkpoint has the tower and aligner (263 tensors,
   floating-point — no EXL3 sidecar conversion needed) but **omits `ffn.gate.bias_vl`** (0 of 43
   gates; the official `deepseek-ai/DeepSeek-V4.1-Flash` checkpoint has all 43: 40 `layers.0..39`
   plus `mtp.0..2`, each float32 `[384]`). Without it the engine warns `no ffn.gate.bias_vl found …
   image tokens route with the text bias` and image quality is degraded, though it still answers.
   `attach_vl_bias` takes a **folder** and globs `*.safetensors` in it (searching
   `TF_DS_VISION_EXTRA`, the model dir, the Engram dir, and a `DeepSeek-V4.1-Flash-extra` sibling), so
   point `TF_DS_VISION_EXTRA` at a directory holding the 43 extracted tensors — **not** at the file
   (a file path yields `VL bias for 0 gates`).

Measured results (evidence in `.scratch/ds4/vision-trial/RESULTS.md`, recipe copies
`baseline.yaml` / `vision.yaml`, overlay mod `mods/dsv41-vision-overlay/`):

- **As shipped (no `--vision`)**: image request → **HTTP 400**
  `image input requires a supported vision checkpoint served with --vision`. Text works.
- **With `--vision` only** (VL bias folder not on the path): tower loads
  (`vision tower on rank 0: 0.90 GiB; VL bias for 0 gates`), image request → HTTP 200 with a correct
  answer, but gate routing is on the text-bias fallback.
- **With `--vision` + the 43-gate VL bias folder**: `VL bias for 43 gates`; three discriminating
  images answered correctly, including a **swapped-order** image ("blue square on the left and a red
  circle on the right") and a **single-shape** image where the model rejected the two-shape premise
  and described the one actual shape. So it reads the pixels; it is not pattern-matching a canned
  answer.
- Warm boot (rank cache present) 54.6 s TTR; cold 512 s. Tower adds 0.90 GiB on rank 0.

**Bottom line.** TP=2 vision is **supported and now proven on our hardware, but not shipped**: it is
a two-part change (`--vision` + the staged VL bias), so the recipe still carries no `vision` tag and
the shipped launcher still refuses images. To ship it, add `--vision` to
`mods/tensorfold-dsv41-launcher/launcher.py`, ship the 43-gate `vl_bias.safetensors` (see
`mods/dsv41-vision-overlay/`), and set `TF_DS_VISION_EXTRA` at that folder.

The engine's own `docs/vision.md` describes `--vision` for GLM/Qwen families; the DeepSeek-V4.1 path
is the family's own `cuda/vision.py` and is what the fork's `tools/dsv41/REPORT.md` measured (6/6
image-input checks).

### 12.15 References

- Engine: [bertholomus/TensorFold, branch `deepseek-v41-tp2`](https://github.com/bertholomus/TensorFold/tree/deepseek-v41-tp2)
- Design/report: the fork's `tools/dsv41/DESIGN.md`, `REPORT.md`, `ATTRIBUTION.md`
- Checkpoint: [Mia-AiLab/DeepSeek-V4.1-Flash-EXL3-2.9bpw](https://huggingface.co/Mia-AiLab/DeepSeek-V4.1-Flash-EXL3-2.9bpw)
- Upstream recipe: [bertholomus/deepseek-v4.1-tensorfold-tp2-2xgb10](https://github.com/bertholomus/deepseek-v4.1-tensorfold-tp2-2xgb10)
- Base image: [`lmsysorg/sglang:dev-cu13`](https://hub.docker.com/r/lmsysorg/sglang)

## 13. Quality benchmarks (`benchmarks/`)

The `benchmarks/` subdirectory holds the **quality** comparison of the two live
DeepSeek-V4.1-Flash chat aliases on the cluster gateway — not a speed harness
(speed is §10/§12).

### 13.1 The two aliases and why they are the comparison

| Gateway alias | Resolved `model` in the response | What it is |
|:--|:--|:--|
| `deepseek` | `deepseek-ai/DeepSeek-V4.1-Flash` | official weights (`deepseek-ai`) |
| `deepseek-turbo` | `Mia-AiLab/DeepSeek-V4.1-Flash-EXL3-2.9bpw` | this lane's EXL3 2.9 bpw checkpoint |

The alias is a gateway routing name; the *identity* is the `model` field the
server echoes back. Never assume the alias maps to a checkpoint — read it back.
The interesting question is whether the EXL3 quantisation costs quality versus
the official weights; the harness answers exactly that.

### 13.2 The trap: the two aliases default to opposite thinking modes

`deepseek` answers immediately (`reasoning_content: null`, `reasoning_tokens: 0`);
`deepseek-turbo` defaults to **thinking on** and can spend an entire small
`max_tokens` budget emitting hidden `reasoning_content` before the visible
answer (observed: 400/400 reasoning tokens on a one-line prompt, `content: null`).
A naive A/B therefore measures *configuration*, not weights. The harness forces
**`chat_template_kwargs={"enable_thinking": false}` on both** for the headline
table, and keeps a small `--thinking on` arm only to document the divergence.

### 13.3 How to run

```bash
cd recipes/ds4/benchmarks
python3 fetch_data.py                       # stage GSM8K + ARC (stdlib, idempotent)
for m in deepseek deepseek-turbo; do
  python3 run_benchmarks.py --base-url http://<head-node>:4000 \
      --model "$m" --bench all --thinking off --limit 200 --seed 1234
done
python3 compare_results.py --thinking off   # -> results/SUMMARY.md + summary.json
```

Only `/v1/chat/completions` is routed (`/v1/completions` → HTTP 400), so the
harness is chat-only by necessity; that also rules out loglikelihood-based
multiple-choice benchmarks (`lm-eval` HellaSwag/MMLU) — generative ones (GSM8K,
ARC letter-match) are what is computable here. The runner is **resumable**: every
item is appended to `results/_raw/<model>.<bench>.<thinking>.jsonl` as it lands.

### 13.4 Files

| File | Role |
|:--|:--|
| `fetch_data.py` | stage datasets from upstream (stdlib; idempotent) |
| `run_benchmarks.py` | runner; imports `tools/quality-battery.py` **verbatim** for the house tier |
| `rescore.py` | re-score stored replies from their saved gold (no endpoint calls) |
| `compare_results.py` | aggregate → comparison table + reply-diff counts |
| `results/_raw/` | append-only per-item audit trail + run logs |

### 13.5 Result (2026-10-06, thinking off, greedy)

house 36/37 both (**hard 17/18 both** — same single failure `hard-rev`), GSM8K
97.0 vs 98.5 % (n=200), ARC 93.0 vs 93.0 % (n=200). **Parity within noise; no
measurable quantisation penalty.** Full method and caveats in `benchmarks/README.md`.

### 13.6 Rules this directory learned the hard way

- **Score changes are replayed, never re-run.** Scoring is a pure function of the
  stored reply + gold, so a scorer fix MUST go through `rescore.py` against
  `results/_raw/`, not a fresh endpoint run. The first GSM8K pass string-matched
  the value after `####` and wrongly failed `#### 8.00` against gold `8`
  (penalised turbo on 4 items, baseline on 6); `score_gsm8k()` now compares
  numerically. This is precisely why replies are kept.
- **A textual diff is not a score diff.** On GSM8K 192/200 replies differ at
  temperature 0 while the scores match within noise — keep both views.
- **Small-n caveats are mandatory.** ±3 items on n=200 is ≈ one SE; report the
  Δ as "inside noise", never as a ranking.
- **Published card numbers are a frame, not a score.** Model-card rows are for
  the *unquantized* model under DeepSeek's own harness (8-shot etc.); the EXL3
  card publishes no evals. Cite them as context only.

### 13.7 Hard battery (HLE, GPQA, MMLU-Pro, MATH-500, AIME, HumanEval, MBPP)

The mid-tier benches (§13.1–13.5) saturate. The hard tier is where a 2.9 bpw quant
*would* show a deficit if it had one, and it is where the published model-card
numbers (GPQA 90.9, HLE 36.8, HumanEval 79.4) actually live.

| Tool | Bench(es) | Grading | Needs |
|:--|:--|:--|:--|
| `fetch_hard.py` / `fetch_hard_hf.py` | stage HLE, GPQA-D, MMLU-Pro, MATH-500, AIME | — | stdlib / `datasets` venv |
| `bench_reason.py` | those five | letter, `math_verify` symbolic, integer, lenient text | `.venv-qa` for symbolic |
| `bench_code.py` | HumanEval, MBPP | **code execution** (dataset tests) in a subprocess sandbox | stdlib |
| `compare_all.py` | all of the above + the mid-tier | paired **McNemar** exact test | stdlib |
| `run_overnight.sh <model> <log>` | everything, one model, in order | — | run two in parallel |

**The single most important finding for anyone touching this harness: thinking
mode is not a free knob.** On hard items, with thinking ON, *both* models stream
hidden reasoning for the entire `max_tokens` budget and return `finish_reason:
length` with **empty `content`** (`deepseek` 16 000 tok / 307 s / empty). The
primary battery therefore runs **thinking OFF on both models** — it is the only
config that yields graded answers and the only fair same-config comparison. A
thinking-ON arm is kept only for GPQA/MATH-500, which terminate quickly. On GPQA,
thinking ON *lowers* turbo from 69.7 % to 38.0 % — reasoning actively hurts MCQ.

**Result (2026-10-06, thinking off, greedy): every benchmark is a tie.** 11
benches, ~1,900 paired items; no bench reaches p < 0.05 on McNemar. Largest gap
AIME +4.4 pp (turbo), discordant 6 vs 10 (p=0.45). See `results/RESULTS.md`.

**Method rules (learned here):**

- **Use the paired test, not the two percentages.** Both models answer the same
  items, so the question is whether the *discordant* items are lopsided, not
  whether the totals differ. `compare_all.py` reports ds-only / turbo-only counts
  and the exact binomial p. Only a large, consistent split is signal.
- **Grade MATH-500 symbolically.** `math_verify` needs `$…$` delimiters to parse
  LaTeX (`\sqrt{12}` vs `2\sqrt{3}` only verifies wrapped); a raw-string fallback
  silently mis-scores. The grader actually used is recorded per item.
- **MBPP needs the function name pinned.** Its prose prompts never state the
  required `def name(...)`, so the native setup floors at ~9 % for both models;
  injecting the reference signature lifts them to ~77 %. The pre-fix arm is kept
  as `off.nameguess` to document the difference.
- **HLE exactMatch rarely terminates** at a 2,000-token cap (the model reasons
  past it), so most non-MCQ HLE items are scored fail-for-both. That depresses the
  absolute HLE level but is symmetric — read HLE as the *gap*, not the level.

## 14. References

- Model: [deepseek-ai/DeepSeek-V4.1-Flash](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash)
- Benchmark data: `openai/gsm8k`, `allenai/ai2_arc` (ARC-Challenge), `tools/quality-battery.py`
- Hard battery: `cais/hle` (via `macabdul9/hle_text_only`), `Idavidrein/gpqa` (via `hendrydong/gpqa_diamond_mc`), `TIGER-Lab/MMLU-Pro`, `HuggingFaceH4/MATH-500`, `AI-MO/aimo-validation-aime`, `openai/openai_humaneval`, `google-research-datasets/mbpp`
- Upstream lane: [knapcio/DeepSeek-V4.1-Flash-4x-DGX-Spark-TP4](https://github.com/knapcio/DeepSeek-V4.1-Flash-4x-DGX-Spark-TP4) @ `58f2321` (downstream of [MiaAI-Lab](https://github.com/MiaAI-Lab/DeepSeek-v4.1-Flash-DGX-Sparks))
- SGLang: [V4.1 cookbook](https://github.com/sgl-project/sglang/blob/main/docs/cookbook/autoregressive/DeepSeek/DeepSeek-V4_1.mdx)
- Archived EXL3 / vLLM lane and model-anatomy analysis: [`attic/ds4/`](../../attic/ds4/)


---

## From recipes/ds4/README.md (2026-10-14)

# DeepSeek V4.1-Flash on DGX Spark — `ds4`

DeepSeek-V4.1-Flash served on four NVIDIA DGX Spark (GB10) nodes with SGLang.
This is the chosen, go-live recipe for the model; the earlier vLLM/EXL3 lane has
been retired to `attic/ds4/` (see [Retired material](#retired-material)).

| | |
|:--|:--|
| Recipe | `deepseek-v4.1-flash-knapcio-tp4-1m-sglang.yaml` |
| Engine | SGLang |
| Model | [`deepseek-ai/DeepSeek-V4.1-Flash`](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash) (native MXFP4/F8, official weights) |
| Checkpoint | `model_revision: 5254448103b6…` (2026-10-12 `main`) — the recipe pins it; byte-identical weights to the image's baked `fb2764a5…`, and every node cache already holds it ([AGENTS.md](AGENTS.md) §5) |
| Nodes | 4 (TP=4, one GB10 per node, EP=1) |
| Context | 1,048,576 tokens (served) |
| Spec decode | DSpark, verify-all |
| Transport | RoCEnante RDMA (shipped on) |
| Image | `littlecedar/dgx-spark-dsv41:canary-roce@sha256:4e5002ab…` (vendored, digest-pinned) |
| Measured | C1 46.5 / C4 106 / C8 133 / C16 193 t/s aggregate (short-prompt harness) |

## What this is

A per-node-Engram design: the model's two 203 GB Engram tables cannot live in
the 128 GB unified memory of a Spark, so they are packed to node-local NVMe and
read on demand. The engine, its kernels, and the reader all come from the
vendored image; this repository supplies only the recipe and the pre-launch mod
(`mods/dsv41-sglang-overlay/`).

Provenance: this lane adapts
[`knapcio/DeepSeek-V4.1-Flash-4x-DGX-Spark-TP4`](https://github.com/knapcio/DeepSeek-V4.1-Flash-4x-DGX-Spark-TP4)
(a downstream of MiaAI-Lab's recipe) onto sparkrun. The launcher, adapters, b12x
kernels, and measurement design are upstream's, kept under their licences.
For provenance, boot gates, and limits in full, see [`AGENTS.md`](AGENTS.md) in
this directory (the archived analysis behind this lane is in
[`attic/ds4/`](../../attic/ds4/)).

## Requirements

- **Four DGX Spark GB10 nodes**, all idle. Tensor parallelism is one node per
  rank, so TP=4 needs four nodes.
- **The pinned official checkpoint in each node's own Hugging Face cache.** The
  cache is per-node (there is no shared export), and sparkrun distributes the
  pinned revision (`model_revision: 5254448103b6…`, `main`) to every runner node.
  The pin is a revision the node caches already hold, so a launch distributes
  nothing; expect ~510 GB per node only if you re-pin to one no node has yet.
- **The image**, pulled from Docker Hub by sparkrun under its default
  distribution config. No local build is required.
- **~47 GiB of node-local disk per node** for the packed Engram shards. The
  launcher packs them automatically on first boot (detached), so normally you do
  nothing. To pre-warm or debug by hand, run this inside the serving image on
  each node, with `<R>` the node rank (`0`…`3`) and `REV` the pinned revision
  sparkrun distributed (a SHA-pinned download writes **no** `refs/main`):

  ```bash
  REV=5254448103b6254fc646dacbca1cbbf20e9216c1
  python3 /opt/dsv41/scripts/pack_engram.py \
    --model /cache/huggingface/hub/models--deepseek-ai--DeepSeek-V4.1-Flash/snapshots/$REV \
    --rank <R> --tp 4 --out /cache/runtime/engram
  ```

No host bind mounts are used. Every non-model, non-image artifact (Engram
shards, boot state, JIT caches) lives under sparkrun's managed runtime cache,
mounted at `/cache/runtime`.

## Run it

```bash
sparkrun run recipes/ds4/deepseek-v4.1-flash-knapcio-tp4-1m-sglang.yaml
````

Or if you want to specify the nodes:

```bash
sparkrun run recipes/ds4/deepseek-v4.1-flash-knapcio-tp4-1m-sglang.yaml \
  -H <node1>,<node2>,<node3>,<node4>
```

## What a healthy boot looks like

Boot to ready is **~9 minutes cold** (a first cold boot additionally packs the
Engram in the background and serves from the checkpoint; the next boot uses the
packed shards). The server is up when these appear in the serve log, in order:

1. `[dsv41-sglang-overlay] overlay gate OK`, and a launcher line naming
   `NNODES=4 NODE_RANK=<r>` — **the rank must differ per node**.
2. `launcher: MODEL_ID is an on-disk checkpoint dir; serving …/snapshots/<sha>`
   (a repo-id invocation prints `resolved checkpoint <repo> -> …/<sha>` instead)
   — `<sha>` must be the recipe's `model_revision`. `launch.json` is **not**
   evidence here: it records the image's baked revision, not the served snapshot.
3. `Exact nvme Engram layer=… rows=[a,b)` — the row range must **differ per
   rank**; identical ranges mean the staging is wrong.
4. `[moe_b12x_next] armed` — the routed MoE is on the b12x_next kernel, not a
   Triton fallback.
5. `DSV4 memory calculation: … full_token=<N>` — the granted KV pool.
6. `Mean acceptance length > 1` on `Decode batch` lines — DSpark is working. A
   boot that serves but accepts nothing is a failure, not a win.
7. `Structured output, tool round trip and full-budget native vision passed.` —
   the image's own smoke test, which includes a **native image-input check**
   (a generated PNG through `/v1/chat/completions`). This lane serves images.

## Measured performance

Two harnesses were used. The short-prompt harness uses ~17-token prompts and is what the `C1 t/s` column in the repository table refers to; the standardized `sparkrun benchmark` profile uses 2048-token prompts and is the auditable cross-check.

| t/s (aggregate decode)                                              |       C1 |      C4 |      C8 |     C16 |
|:--------------------------------------------------------------------|---------:|--------:|--------:|--------:|
| short-prompt harness (shipped config)                               | **46.5** | **106** | **133** | **193** |
| standardized profile (`benchmarking/ds4-sglang-depth0-ladder.yaml`) |     43.6 |    91.3 |    99.4 |   102.1 |
| same lane, NCCL only (RoCEnante off; not shipped)                   |     27.4 |    62.5 |    73.2 |   155.0 |

RoCEnante is the single largest lever measured on this lane (1.70×/1.69×/1.81×/
1.23× over NCCL), far outside the 7–25% GB10 boot-to-boot spread. It is shipped
on; rollback is one line in the launcher (`SGLANG_ROCE_ALLREDUCE=0`).

**Re-pin verification boot (2026-10-14).** The checkpoint pin was moved to the cached `main`
(`5254448103b6…`; rationale in [AGENTS.md](AGENTS.md) §5). A four-node boot then measured the
auditable C1 profile `benchmarking/decode-triage.yaml` (pp 2048 / tg 128, runs 5): **38.3 t/s** at
depth 0 and **42.5 t/s** at depth 8192 — inside the 7–25% inter-boot spread around the 43.6 figure
above — and the house battery returned the same **19/19 easy + 17/18 hard** (`hard-rev`) as
recorded. Boot receipt and receipts in [AGENTS.md](AGENTS.md) §5.1.

Quality: the release checkpoint scores **17/18 (94.4%)** on this project's hard
18-task tier, the same score and the same single failure as the retired EXL3
lane — so the EXL3 quantization cost nothing measurable, and that one failure is
a base-model limitation. The comparator runs the release checkpoint on the same
hard tier and returns the same score and the same single failure (character
reversal of an uncommon word); the one failure is a base-model limit, not
quantization damage.

## Caveats & Limitations with Explanations

> **Scope:** everything in this section describes the **knapcio TP=4 SGLang lane**
> (`deepseek-v4.1-flash-knapcio-tp4-1m-sglang.yaml`, SGLang + `dsv41-sglang-overlay`). It does
> **not** apply to the TensorFold TP=2 lane further down — a different engine with a different KV
> model (`--context` is a single shared pool there; see §"Context window and concurrency").

### 1M Context

A `context_length` of 1,048,576 tokens is configured, served, and needle-tested (needle passed at
985k on the canary image). Hardware memory boundaries and prefill compute impose real operational
constraints.

#### Memory Residency and Concurrency Limits

* **KV Pool Capacity:** the pool is pinned to **9,400,000 tokens** (`MAX_TOTAL_TOKENS` in the
  overlay launcher, measured on our four nodes 2026-10-06). The head's `MemAvailable` at
  `mem_fraction_static=0.80` permits **~9.5–9.6M** (`full_token=9,493,504..9,589,504`,
  `bytes_per_full_token=1670.75`); a larger pin is clamped to that, never refused. The previous
  pin was 4,000,000 — only ~58% of the ceiling — so it was raised. Upstream's ~7.5M figure is a
  *budget under a different configuration* (EP2, fast loader), not tokens this server holds; see
  [`AGENTS.md`](AGENTS.md) §7.1 for the boot receipts.
* **Concurrent 1M Streams:** SGLang's pool is page-shared, not extent-reserved — it does not hold
  each request's declared window. **16** concurrent requests each declaring ~1M tokens were all
  admitted and decoded on our nodes (the `MAX_RUNNING_REQUESTS=16` cap, zero errors); the limit is
  that cap and the ~9.5M total *actual* tokens, not a per-stream reservation. The "~6.6" this
  section previously carried was a division of the upstream ~7.5M budget by 1M, not an observed
  concurrency, and it ignored both the old 4M pin and the page-shared model; it has been removed.
* **Note:** the decode log's `full token usage` percentage reads `0.00` even under real draw in
  this build — do not judge capacity from it (`full token: N` is the usable counter).
* **A 1M cold prefill at the raised pin — VERIFIED 2026-10-06.** A ~1M-token cold prompt ingested
  at **2909 tok/s** and replied correctly with the 9.4M pin. Head available dipped to ~5 GB
  low-water during the prefill (the indexer transient draws ~9 GB over the pool) then recovered to
  10 GB, so the pin holds but the head sits near its floor during a 1M prefill.

#### Cold Prefill Latency vs. Cache Hits

* **Cold Prefill Computation:** Ingesting a cold, un-cached 1M-token prompt takes approximately 6.5 minutes of compute on this cluster.
* **Warm / Reused Context:** Leveraging prefix KV caching avoids recomputing full-context attention. Re-running queries against an existing cached context executes near instantaneously.
* **Measured caveat (2026-10-06): the radix prefix cache did not hit on this lane.** Back-to-back requests to the served lane with identical prompts still logged `#cached-token: 0`, even though the config has `disable_radix_cache: False` and `radix_eviction_policy: lru`. The DSpark / bounded-replay serving path does not retain short-prompt prefixes the way stock SGLang's radix cache does. So treat the "warm / reused context is near-instant" claim above — and the agentic-workflow recommendation that leans on it — as **unproven for this lane** until cache reuse is re-measured with production-shaped prompts. This is a serving-path behaviour, not a KV-pool regression.

#### Workload Recommendations

* **Agentic & Conversational Workflows:** Highly recommended for multi-turn conversations, agentic workflows, and document analysis where large prompt prefixes (such as codebases or knowledge bases) remain cached across interactions.
* **Stateless Cold Batches:** Avoid high concurrency of simultaneous cold 1M-token inputs without shared prefixes, as queued prefill latency will accumulate.

### Prompt-token logprobs are unavailable
...and late layers run only over the last 128 rows of a prefill (`--enable-decoder-swa-bounded-replay`); such requests return HTTP 400. Output logprobs and cache hits work. Greedy text is deterministic run to run, so an exact-match task battery is comparable, but a bitwise comparison against the release checkpoint is not available here.

#### Inability to Return Prompt-Token Logprobs (`HTTP 400`)

* **What it means:** When client requests ask for log probabilities of the input prompt tokens (e.g., via `echo: true` or `prompt_logprobs` parameters in OpenAI-compatible/SGLang APIs), the server cannot compute them and explicitly rejects the request with an `HTTP 400 Bad Request` status code.
* **Why it happens:** Calculating log probabilities across the prompt requires full forward-pass activations and output logits for every prompt token position. Because of the bounded replay optimization described below, those intermediate states are not fully computed for early prompt tokens.

#### Prefill Optimization via `--enable-decoder-swa-bounded-replay`

* **Mechanism:** SWA stands for **Sliding Window Attention**. With `--enable-decoder-swa-bounded-replay` enabled, the engine applies an aggressive prefill-phase optimization where later decoder layers process only the tail end (the last 128 rows/tokens) of the prefill sequence rather than running full attention across the entire prompt context.
* **Impact:** This significantly cuts down computation and memory bandwidth during cold prompt ingestion (prefill), which is critical for long contexts (e.g., up to 1M tokens).

#### Output Logprobs and Prompt Caching Still Function

* **Output Logprobs:** During autoregressive generation (decoding steps), token generation occurs token-by-token at the sequence boundary, meaning standard output log probabilities for generated tokens are fully supported.
* **Cache Hits:** The KV cache prefix structures remain valid for prefix caching and reuse across subsequent requests.

#### Deterministic Evaluation vs. Bitwise Checkpoint Parity

* **Exact-Match Task Battery:** Setting `temperature=0` (greedy decoding) generates deterministic output strings across repeated runs on this serving configuration. As a result, functional evaluation benchmarks (such as accuracy on question-answering, code generation, or math test batteries) can be reliably evaluated and compared.
* **Lack of Bitwise Parity:** Because late layers only attend to the last 128 rows during prefill, the resulting hidden states and logits deviate numerically from standard, full-sequence prefill execution. Consequently, outputs will not be bit-for-bit identical to outputs produced by reference release checkpoints running with baseline unconstrained prefill.

**Summary Table**

| Feature / Behavior | Status / Consequence | Explanation |
| :--- | :--- | :--- |
| **Prompt-token logprobs** | **Unavailable (`HTTP 400`)** | Intermediate logits for full prompt tokens are not computed. |
| **Output-token logprobs** | **Available** | Generated tokens compute full logits during decoding. |
| **Prefill speed / throughput** | **Accelerated** | Late layers only compute the last 128 tokens of the prompt. |
| **Prompt cache hits** | **Supported** | Prefix KV caching operates normally. |
| **Greedy reproducibility** | **Deterministic** | Output is repeatable across runs on the same configuration. |
| **Bitwise reference parity** | **Not available** | Numerical results differ from standard baseline prefill runs. |


### Fast loader disabled to reclaim 3–13% KV pool

Upstream's eager safetensors loader (`DSV41_FAST_LOAD=1`) accelerates startup at the cost of reducing the available runtime KV cache capacity. This recipe disables the fast loader to reclaim the KV pool at the cost of ~220s additional startup time.

#### Mechanism and Memory Impact

* **What the Fast Loader Does:** Rather than reading model weights sequentially via stock SGLang loaders, the fast loader reads each rank's tensors eagerly into pinned host memory slabs, parallelizing checkpoint ingestion during container startup.
* **Why the KV Pool Shrinks:** On the DGX Spark unified memory architecture, SGLang determines KV cache pool size by querying available system memory (`psutil.virtual_memory().available`). Although the fast loader releases tensor buffers before the pool is sized, temporary driver staging state and pinned page allocations retain ~0.8–1.5 GB in the unified memory pool. This reduction in reported `MemAvailable` shrinks the allocated KV cache pool from 7.47–7.82M tokens down to 6.71–7.27M tokens (a 3–13% reduction).

#### Startup Time vs. KV Capacity Trade-off

The interval below is **upstream's** (EP2, 2026-09-18 stack), not ours — our EP1 receipts sit
inside it (9.49–9.59M at the shipped stock loader). It matters less than it reads: the pool is
pinned to a fixed `MAX_TOTAL_TOKENS` either way, and the pin (not the budget) is what the server
holds, so this difference does not change concurrency at the shipped settings. See
[`AGENTS.md`](AGENTS.md) §7.1.

* **Fast Loader (`DSV41_FAST_LOAD=1`):** Reduces engine startup time from ~350 s down to ~125 s (saving ~220 s per boot), at the cost of a smaller *budget* (~6.71–7.27M vs ~7.47–7.82M tokens upstream).
* **Stock Loader (`DSV41_FAST_LOAD=0`):** Requires ~350 s for cold engine launch, and leaves a larger budget — which the 4M pin then absorbs.

#### Shipped Configuration Decision

* **Deliberately Disabled:** The recipe explicitly ships with `"DSV41_FAST_LOAD": "0"` in `launcher.py` (commit `f91fe43`) to keep the larger budget for long-context / multi-stream serving.

**Summary Table** (upstream's measurements for the two loader columns)

| Metric / Attribute | Stock Loader (`DSV41_FAST_LOAD=0`, Shipped) | Fast Loader (`DSV41_FAST_LOAD=1`) |
| :--- | :--- | :--- |
| **Engine Startup Time (`scheduler_e2e`)** | ~343–354 s | **~124–129 s** (~220 s faster) |
| **KV budget the host allows (`full_token`)** | **~7.47–7.82M tokens** | ~6.71–7.27M tokens (~3–13% smaller) |
| **KV pool actually used** | 9,400,000 (pinned, 2026-10-06) | 9,400,000 (pinned) |
| **Model Weights & Numeric Output** | Bitwise identical | Bitwise identical |
| **Inference Latency & Quality** | Unchanged | Unchanged |
| **Recommended Use Case** | **Production serving & long context** | Development & fast iteration |


### Greedy text equality is not a prefill-correctness gate

~70k-token cold prompts diverge run to run!

#### What is "Greedy Text Equality"?

* In autoregressive decoding, **greedy decoding** (setting `temperature=0` or taking `argmax(logits)`) always selects the single most probable token at each step.
* Theoretically, on deterministic systems, greedy decoding on identical inputs should yield identical, character-for-character output text across repeated runs.

#### What is a "Prefill-Correctness Gate"?

* A **correctness gate** is an automated validation check used in testing pipelines to verify that the engine initialized, ingested the prompt, and computed the initial KV cache and attention states without corruption.
* A common intuitive approach is to compare the greedy output against a golden reference string or across multiple runs: if output matches, prefill is deemed correct; if it differs, the run is flagged as failed.

#### Why It Fails for ~70k+ Token Prompts ("Diverge Run to Run")

* **Non-associative floating-point reductions**: Large-scale tensor-parallel matrix multiplications and reduction operations (e.g., across multi-node tensor parallelism, flash attention chunking, and quantized matrix formats like MXFP4/FP8) execute operations in non-deterministic order across thousands of parallel GPU threads.
* **Accumulated floating-point drift**: Across tens of thousands of tokens (such as ~70k tokens), minute rounding differences ($\approx 10^{-7}$ in float32/bfloat16 or larger in lower precisions) accumulate across layers and attention heads.
* **Argmax boundary flipping**: If the logits for the top two candidate tokens are nearly identical (e.g., $14.200001$ vs $14.200000$), a microscopic numerical delta will flip which token is selected first.
* **Autoregressive cascade**: Once a single token selection differs at step $N$, all subsequent generation steps receive different context and diverge completely.

#### Practical Implications

* **Avoid false negatives in test suites**: Treating greedy text diffs as a test failure for long-context runs will incorrectly flag healthy, performant deployments as broken.
* **Adopt robust evaluation criteria**: Prefill and engine health should be verified using downstream semantic benchmarks, needle-in-a-haystack retrieval tasks, logit tolerance thresholds, or target accuracy batteries rather than exact bitwise/string equality over massive context lengths.


### Single-stream prose is bounded by DSpark acceptance

Single-stream generation speed is constrained by the speculative acceptance rate (~3 accepted tokens per step on prose, ~6 on code).

#### Speculative Decoding Mechanism (DSpark)

* **Draft and Verify Pipeline:** DSpark employs speculative decoding to accelerate autoregressive generation. In each step, candidate tokens are drafted and verified in parallel by the target model, producing multiple output tokens per forward pass when speculation succeeds.
* **Acceptance Length Metric:** Performance gains depend directly on the mean number of speculative tokens accepted per verification step (`Mean acceptance length`).

#### Workload Entropy: Prose vs. Code

* **Structured Code Generation (~6 tokens/step):** Code contains predictable keywords, syntax structures, and indentation patterns, yielding higher speculative draft accuracy and achieving ~6 accepted tokens per step.
* **Natural Language Prose (~3 tokens/step):** Natural language prose exhibits higher entropy, varied vocabulary, and less deterministic phrasing, resulting in lower draft acceptance rates (~3 accepted tokens per step).

#### Concurrency and Throughput Scaling

* **Single-Stream (C1) Latency:** Single-user interactive requests on prose generation will experience decode speed bounded by the lower acceptance rate (~46.5 t/s aggregate).
* **Batch Concurrency (C4–C16) Throughput:** When serving concurrent streams (C4, C8, C16), GPU compute utilization increases and tensor-parallel batches saturate hardware capacity, raising aggregate throughput to 106–193 t/s.

#### Operational Notes

* **Verify Healthy Operation:** Check serving logs to confirm `Mean acceptance length > 1` on `Decode batch` lines. A speculative decode run that accepts ≤ 1 token per step indicates speculation is failing.
* **Reasoning Effort:** Configured with `chat_template_kwargs {"thinking": false}` for standard low-latency serving.


### Verify window gamma: A/B tested 2026-10-10, kept at 5

The bertholomus TP4 fork (`deepseek-v4.1-flash-dspark-tp4-4xgb10` @ `90cf3a2b`, AGPL — finding
tested, code not copied) pre-registered `DSPARK_BLOCK_SIZE` 5→2 as +6–12% over bracketed γ=3
controls. On this lane the transplant **fails**: a same-window paired A/B (same day, same nodes,
the `ds4-sglang-depth0-ladder` profile) measured γ=2 at C1 37.70 vs 37.67 (~0), C4 85.29 vs 90.10
(−5.3%), C8 92.12 vs 94.88 (−2.9%), C16 102.58 vs 98.19 (+4.5%). γ=2 loses at moderate
concurrency — matching the counter-evidence the fork itself records. Probable mechanism: this
lane's `DSV41_VERIFY_CAP=conf:0.1` + `DSV41_BLOCK_VERIFY=1` change the window economics and the
fork ran no conf cap. Receipts: `~/benchmarks/ds4-gamma2-20261010/{ladder-gamma2,ladder-gamma5-control}.{json,yaml}`; full write-up in the `DSPARK_BLOCK_SIZE` comment in `mods/dsv41-sglang-overlay/launcher.py`. Both boots ran below the 2026-10-06 receipts (documented inter-boot drift), so the verdict is within-pair, not absolute.

### Do not apply the SPS ragged-verify table

The speculative scheduling cost table (`DSPARK_SPS_TABLE` / `DSPARK_STS_TABLE`) arms the scheduler but crashes the Engram retrieval path on mixed-batch workloads.

#### What is the SPS/STS Ragged-Verify Table?

* **Ragged Verification Optimization:** The SPS (Speculative Scheduling) and STS tables provide cost models that allow the speculative scheduler to dynamically batch and verify uneven, variable-length candidate token sequences ("ragged" batches) across concurrent requests.

#### Mechanism of Failure with NVMe Engram Shards

* **Fixed-Block Invariant:** To stream DeepSeek V4.1-Flash's 203 GB Engram embedding tables from node-local NVMe within tight latency budgets, the custom Engram reader relies on strict, equal-block memory alignment per request.
* **Assertion Crash:** When ragged verification passes heterogeneous candidate sequence lengths to the verification step, the reader's batch invariant fails, throwing `AssertionError: engram target-verify expects one equal block per request, got 84 tokens for 16 requests of 6` and causing the serving worker to crash immediately on the first mixed batch.

#### Shipped Configuration Decision

* **Verify-All Mode Shipped:** The recipe deliberately leaves `DSPARK_SPS_TABLE` and `DSPARK_STS_TABLE` unset.
* **Production Stability:** Booting without the SPS table retains the uniform `verify-all` scheduling contract, ensuring complete stability across all mixed-batch production traffic.



## TensorFold TP=2 lane (two nodes)

A second lane in this directory serves the same model on **two** GB10 nodes with a
different engine. It trades the four-node SGLang lane's measured quality record and
its ability to hold several long-context streams at once for a lower node count and
better single-stream speed on a smaller (EXL3-quantized) checkpoint. Both lanes serve
the model's full 1M window; this one reaches it with two nodes instead of four, but
shares one KV pool across its streams rather than sizing the pool separately (see
[Context window and concurrency](#context-window-and-concurrency)).

| | |
|:--|:--|
| Recipe | `deepseek-v4.1-flash-tensorfold-tp2-1m-sglang.yaml` |
| Engine | TensorFold `deepseek_v41` ([bertholomus/TensorFold](https://github.com/bertholomus/TensorFold) @ `d5d7bb3`, branch `deepseek-v41-tp2`) |
| Model | [`Mia-AiLab/DeepSeek-V4.1-Flash-EXL3-2.9bpw`](https://huggingface.co/Mia-AiLab/DeepSeek-V4.1-Flash-EXL3-2.9bpw) (EXL3 2.9bpw, ~197 GB) |
| Engram | Built on-node from the online official repo by `mods/dsv41-engram-fetch` (~189 GiB) |
| Nodes | 2 (TP=2, one GB10 per node) |
| Context | **1,048,576 tokens served** — the model's full trained window, which is also the KV pool |
| Spec decode | DSpark k=5 (in-checkpoint draft blocks) |
| Image | `littlecedar/dgx-spark-dsv41@sha256:fabbe861…` (vendored, digest-pinned) |
| Measured | C1 101 code / 62 prose / 142 structured t/s; 4 streams 112 t/s (upstream's numbers on 2× GB10) |
| Boot-verified | 2026-10-05 on 2× GB10: cold ~511 s engine-load, warm **51 s** TTR; **73 tok/s** single-stream (our own number) |

**2026-10-10 needle + stability verification (our hardware, this lane):**

- **Needle: PASS at both windows tested.** 262k sweep: 3/3 needles at depths 10/50/90% (prefill
  190–364 s per probe). Deep probe: 1/1 at **958,919 prompt tokens** (depth 50%, prefill 1226.7 s,
  ~782 tok/s) — retrieval intact at ~96% of the 1M window. Records: `/tmp/ds4tp2-needle-{262k,960k}.json`.
- **Stability (the reported "looping output while reasoning"): NOT REPRODUCED.** 9 reasoning-heavy
  prompts at the served config, then the 3 worst with an 8k-token budget: zero repeated-window runs
  (loop score 1 throughout). Two prompts exhaust any budget in *non-repetitive* reasoning (18,000
  chars of fresh reasoning, `finish_reason=length`) — a thinking-budget behaviour, not a loop.
  Operationally important: the serve line **ignores request-level `temperature`/`repetition_penalty`**
  (byte-identical replies across override arms), so any future mitigation must go through the
  TensorFold launcher, not the client.

See [`AGENTS.md`](AGENTS.md) §12 for the design, the launcher/rendezvous details, and how to
rebuild the image. The lane is **boot-verified**: it loads both ranks, serves `/v1/models` and
`/v1/chat/completions`, and DSpark accepts (mean 2.76 tokens/round) — see §12.11 for our numbers.
Two caveats remain. First, the EXL3 checkpoint is a lossy quant — but its **quality is now measured**
(2026-10-06, see [Quality](#quality-measured) below): on the house hard tier it scores **17/18**,
*identical* to the official-weights lane, with no measurable gap on GSM8K or ARC-Challenge. So parity
is now evidence, not hope. Second, the shipping prerequisite that bites first: the `@littlecedar/mods/…`
reference resolves from the node's registry clone, so this recipe only launches once the mod is
committed and pushed (§12.10).

**Vision: this lane ships text-only, but the engine can do images.** DeepSeek-V4.1-Flash is
multimodal, and the TensorFold engine supports image input behind its opt-in `--vision` flag — which
the shipped launcher does not pass, so an `image_url` part is refused with HTTP 400. Verified on
`.32`/`.33` (2026-10-06) that adding `--vision` **and** staging the checkpoint's missing VL routing
bias (43 `ffn.gate.bias_vl` tensors, extracted from the official weights) makes image input work —
three discriminating images were described correctly, including a swapped-order one. It is a
two-part change, so it is not shipped. See [`AGENTS.md`](AGENTS.md) §12.14 for the full picture,
the evidence, and the overlay mod (`mods/dsv41-vision-overlay/`).

**Engram: this lane provisions its own tables from the online repo.** The EXL3 checkpoint
omits the two Engram embedding tables (layers 1 and 14, ~189 GiB); they exist only in the
*official* `deepseek-ai/DeepSeek-V4.1-Flash` checkpoint. The recipe now carries
`mods/dsv41-engram-fetch`, which runs `tools/build-dsv41-engram.py` on each runner node: it
locates the four `engram.embed.{weight,scale}` tensors via the repo's safetensors index and
copies them with **HTTP byte-range reads** — the ~285 GB checkpoint is never pulled and the
model weights are never unpacked into a local HF cache. Peak RSS is ~0.6 GiB on a node whose
source is 189 GiB. It is a no-op once the tables are complete, and it **always fetches
detached** — a slow Internet link can take hours and the pre-serve hook has a hard **600 s**
limit, so the fetch never blocks the launch; the engine serves degraded until the tables land
and uses them on the next boot. Verified 2026-10-06 on `.34`/`.35` with the tables deleted:
the executed recipe fetched all 189 GiB on-node (820 s, 236 MiB/s), a fresh boot reached ready in
~70 s, and **both** engine ranks held `TF_DS_ENGRAM` with the fetched `engram-l1/l14.safetensors`
open — the served engine uses the fetched tables, not the degraded fallback.

For a fresh or slow-link deployment there are two better paths than waiting on the per-node
fetch. **Pre-warm out-of-band**: `python3 tools/build-dsv41-engram.py --detach` on each node (then
`--status`), which resumes across interruptions and needs no container. Or let **sparkrun
distribute** the tables: uncomment the recipe's `distribution_config.models` block (an Engram repo
is downloaded once on the head and rsynced to the workers, instead of N×189 GiB of Internet
egress); the launcher reads them from that cache dir. Either way, a **rank-0/rank-1 Engram
mismatch hangs at readiness**, so make sure all ranks have the tables before booting. See
[`AGENTS.md`](AGENTS.md) §12.7, [`tools/README.md`](../../tools/README.md), and
[`mods/dsv41-engram-fetch/README.md`](../../mods/dsv41-engram-fetch/README.md).

### Combined local repo lane (weights + Engram + prompt in one repo)

The shipped `deepseek-v4.1-flash-tensorfold-tp2-1m-sglang.yaml` serves the TP=2 lane from **one**
local Hugging Face repo instead of three sources. `tools/build-dsv41-combined.py` vendors the
EXL3 2.9 bpw checkpoint, the **upstream Engram tables** (layers 1 and 14, as
`engram/engram-l{1,14}.safetensors`), and **upstream's updated prompt** (`chat_template.jinja`,
plus the same template folded into the EXL3 `tokenizer_config.json`) into a single directory with
`provenance/{SOURCES,MANIFEST}.json` pinning the source revisions and hashing every file.

The tables live in an `engram/` **subdir** because the engine globs `*.safetensors`
non-recursively; at the repo root that glob would walk the 39 EXL3 shards. The launcher now
prefers `<model_dir>/engram/`, so `model: <this repo>` is all the recipe needs — **no
`dsv41-engram-fetch` mod and no pre-warm step**. The EXL3 `config.json` stays authoritative
(its `quantization_config` is the `exl3` the engine requires); the upstream config is kept under
`upstream/` for reference.

`sparkrun` distributes a model **by repo id into the node HF hub cache**, not by local path, so
to use this lane across the cluster either push the repo (`hf upload littlecedar/…`) and point
`model:` at the id, or pre-place `models--<org>--<name>/snapshots/<rev>` on every node. See
[`tools/README.md`](../../tools/README.md) and the repo's own `provenance/README.md`.

### Context window and concurrency

**The recipe ships at `max_model_len: 1048576` — the model's full trained window.** For this engine
that is also the largest possible KV cache, because `--context` *is* the pool: TensorFold exposes no
separate pool-size flag, so a bigger context and a bigger cache are one and the same setting. It is
therefore the largest value the recipe can carry, and the engine hard-refuses anything larger before
loading a single weight:

```
$ tensorfold serve <model> --context 1048577
tensorfold: --context 1048577 exceeds this model's 1048576-token window
```

(`cli.py`: `if native_context and context > native_context: raise …`; `native_context` is
`config.json`'s `max_position_embeddings`.) `1048576` itself boots and is served — verified on
2× GB10 (`/v1/models` reports it, the engine logs `context 1048576`).

That ceiling is the **model's**, not the machine's. 1,048,576 is not a round number by accident:
the checkpoint's `rope_scaling` is YaRN with `original_max_position_embeddings: 65536` and
`factor: 16`, and 65,536 × 16 = 1,048,576. Past it the model has no valid positions, so the engine
refuses to start rather than serve nonsense. Memory would allow far more — DeepSeek-V4.1-Flash uses
MLA (one shared latent KV head), so the cache costs only ~2.9 KiB per token; measured on the trial
pair, rank 0's warm-up `reserved` was **100.8 GiB at `context 262144`** and **103.0 GiB at
`1048576`** — the entire extra 786,432 tokens of window cost **2.16 GiB**.

`max_model_len` is **not** a per-request allowance — it is the **whole KV pool**, shared by the
`--parallel` lanes. The engine says so at startup:

```
[tensorfold] --parallel 4: 4 streams share one window of 1048576 tokens (an extent each)
```

Each stream carves its own `prompt + max_tokens + draft rows` out of that one window, and a request
whose prompt+reply exceeds it is refused up front. So **concurrency and per-stream context trade
off**, and you cannot run four full-window streams:

| 4 concurrent requests, each declaring | at `max_model_len: 1048576` (shipped) | at `max_model_len: 262144` (the old value) |
|:--|:--|:--|
| 2,000 reply tokens | **4 concurrent** | **4 concurrent** |
| 200,000 | **4 concurrent** | — |
| 250,000 | **4 concurrent** | **1** |
| 300,000 | **3 concurrent** | — |
| 500,000 | **2 concurrent** | — |
| 900,000 | **1** | — |

Measured 2026-10-05 on 2× GB10 via the engine's `/health` `streams.decoding` counter (full method
and the code path in [`AGENTS.md`](AGENTS.md) §12.13). `--parallel 4` is a hard cap: eight tiny
concurrent requests still decode at most 4 at once.

- **One stream can use the whole 1M window** (that stream is then the only decoder; others queue) —
  which is what makes the recipe usable for genuine long-context work.
- **Four streams coexist up to ~250K tokens each.** The pool is a superset of the old 262K one, so
  shipping 1M **strictly improves** concurrency: four requests each declaring a 250K reply went from
  **1 concurrent** at 262K to **4 concurrent** at 1M.
- **Decode speed is unaffected by the larger pool** — measured 72.5 tok/s median at `context
  1048576` versus 73.0 at 262144, identical DSpark acceptance. Pages are touched only as used.
- Size clients' `max_tokens` to about `max_model_len / n` for *n* concurrent long-context streams.
  Upstream's reported 4-way concurrency is real, and was measured on 384-token generations
  (~4K of window each).

## Quality (measured)

The TensorFold TP=2 lane serves the **EXL3 2.9 bpw** checkpoint, so the live
question for anyone choosing between the two lanes is whether the quantisation
costs quality. It was measured directly against the official-weights lane on
2026-10-06 via the cluster gateway (`deepseek` = official, `deepseek-turbo` =
EXL3 2.9 bpw), greedy, thinking off on both:

| Benchmark (0-shot unless noted) | `deepseek` (official) | `deepseek-turbo` (EXL3 2.9bpw) | Δ | verdict |
|:--|--:|--:|--:|:--|
| House battery — hard tier | 17/18 | 17/18 | 0 | tie |
| House battery — total (37) | 36/37 = 97.3 % | 36/37 = 97.3 % | +0.0 pp | tie |
| GSM8K (n=200) | 194/200 = 97.0 % | 197/200 = 98.5 % | +1.5 pp | tie |
| ARC-Challenge (n=200) | 186/200 = 93.0 % | 186/200 = 93.0 % | +0.0 pp | tie |
| HLE text-only (n=200) | 13/200 = 6.5 % | 13/200 = 6.5 % | +0.0 pp | tie |
| GPQA Diamond (n=198) | 142/198 = 71.7 % | 138/198 = 69.7 % | −2.0 pp | tie |
| MMLU-Pro (n=400) | 328/400 = 82.0 % | 321/400 = 80.2 % | −1.8 pp | tie |
| MATH-500 (n=200) | 191/200 = 95.5 % | 188/200 = 94.0 % | −1.5 pp | tie |
| AIME 2022-24 (n=90) | 51/90 = 56.7 % | 55/90 = 61.1 % | +4.4 pp | tie |
| HumanEval (n=164, exec) | 159/164 = 97.0 % | 157/164 = 95.7 % | −1.2 pp | tie |
| MBPP (n=257, exec) | 200/257 = 77.8 % | 198/257 = 77.0 % | −0.8 pp | tie |

**The EXL3 quantisation costs nothing measurable.** Across 11 benchmarks and
~1,900 paired items, **no benchmark separates the two models** (paired McNemar,
exact, p ≥ 0.05 on every one); the largest gap is +4.4 pp (AIME, favouring turbo)
with a 6-vs-10 discordant split (p = 0.45). The sign of the tiny gaps is not even
consistent across benchmarks — the signature of noise. The complete method,
caveats, and reproduction steps are in [`benchmarks/README.md`](benchmarks/README.md);
raw results and the paired-test table are under `benchmarks/results/`, and
published reference scores for the unquantised model are in
[`benchmarks/REFERENCE-SCORES.md`](benchmarks/REFERENCE-SCORES.md).

## Retired material

The DeepSeek V4.1-Flash **vLLM / EXL3 lane** (five recipes over
`bot-lab-21/DeepSeek-V4.1-Flash-EXL3-3.5bpw-Pollard`) and its documentation —
the consolidated agent guide, the DSpark TP=3/TP=6 study, the memory-reclaim
plan, the performance triage, and the session notes — were moved to
[`attic/ds4/`](../../attic/ds4/) when this SGLang recipe was chosen for go-live.
That material is not shipped, not tested by `recipes/` guards, and kept only as
reference (it holds the load-bearing residency analysis, the DSpark k-sweep, and
a set of measured negative results). See [`attic/ds4/README.md`](../../attic/ds4/README.md).

For agents and developers working on this lane, read
[`AGENTS.md`](AGENTS.md) (same directory) before touching the recipe or the mod.
