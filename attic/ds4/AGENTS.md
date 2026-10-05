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
  `--cluster` does.** `--hosts red@10.0.4.32,…` made the *node* try to `git clone`
  our `file://` registry and fail. Fix: `sparkrun cluster create ds4tp4 --user red
  --transfer-mode local`.
- **`docker logs` is empty — the serve log is `/tmp/sparkrun_serve.log` INSIDE the
  container**, readable with `docker exec <c> cat /tmp/sparkrun_serve.log`.
- **Probe with `red@` first.** `ssh siv@…` returns `Permission denied`; all six
  nodes work as `red@`.

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
source; `recipes/COOP.md` is the node-handshake ledger (`.30/.31` are protected;
`.32/.33` are shared with the qwen4 lane).
