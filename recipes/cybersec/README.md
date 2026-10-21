# Cybersec lane — `recipes/cybersec/`

_Brought to you by Little Cedar Group._

Red-team / security-research arms: **abliterated (refusal-removed) and cybersecurity-unlocked**
checkpoints served on DGX Spark (GB10). This is a *capability* lane, not a defence one — every
arm here will answer prompts its base model refuses, and the operator supplies the guardrails.
Lane history, receipts, and operating lore live in [`attic/cybersec/`](../../attic/cybersec/)
(indexed at the bottom of this file).

## Contents

- [Gating and the token prerequisite](#gating-and-the-token-prerequisite)
- [`qwen3.8-27b-uncensored-nvfp4-sglang`](#qwen38-27b-uncensored-nvfp4-sglang) — arm 1, positive (TP=1)
- [`qwen3.8-27b-uncensored-nvfp4-nextn-sglang`](#qwen38-27b-uncensored-nvfp4-nextn-sglang) — arm 1's spec-decode sibling, positive (TP=1)
- [`qwen3.8-27b-ablit-cyber-unlock-nvfp4-dflash2-sglang`](#qwen38-27b-ablit-cyber-unlock-nvfp4-dflash2-sglang) — arm 2, positive (TP=1), overlay
- [`nex-n2.5-mini-uncensored-nvfp4-sglang`](#nex-n25-mini-uncensored-nvfp4-sglang) — arm 3, negative under SGLang; vLLM route unblocked (+ `nex-n2.5-mini-uncensored-nvfp4-vllm`)
- [`qwen3.8-flash-next-uncensored-nvfp4-sglang`](#qwen38-flash-next-uncensored-nvfp4-sglang) — arm 4, negative under SGLang; vLLM route unblocked (+ `qwen3.8-flash-next-uncensored-nvfp4-vllm`)
- [`deepseek-v4.1-flash-abliterated-cyber-tp2-tensorfold-sglang`](#deepseek-v41-flash-abliterated-cyber-tp2-tensorfold-sglang) — arm 5, positive (TP=2), graft
- [Attic index](#attic-index)

## Gating and the token prerequisite

**Every arm is gated on the Hub (`gated: auto`)** — the five arms plus arm 1's NEXTN sibling, which
serves arm 1's repo. A distributed registry cannot assume an `HF_TOKEN`, so the prerequisite is
explicit here and in every recipe's `metadata.caveats`:

- each runner node needs an `HF_TOKEN` whose user has **accepted that repo's release**, and
- two arms (2 and 5) pull *two* gated repos each (the body/stock pack and the overlay).

Without the token the model acquisition fails at launch, with the exact repo id named. **No
weights are redistributed by this registry; recipes ship repo ids, revisions, and wiring only.**

**Use.** These checkpoints are released for interpretability / refusal-mechanism study,
red-teaming, and robustness evaluation. They will produce harmful or illegal content on request.
Do not deploy them to end users, and do not point them at anything you do not own.

Sizes below are measured on-disk weight bytes, not the Hub `Parameters` field. One node ≈ 108 GB
usable at util 0.85, two ≈ 218 GB. Boot and measurement receipts for every arm (boot ids,
`GET /v1/models` answers, C1 runs, house batteries, refusal probe):
[`attic/cybersec/AGENTS.md`](../../attic/cybersec/AGENTS.md) §8.

## `qwen3.8-27b-uncensored-nvfp4-sglang`

**Arm 1 — POSITIVE (TP=1).** Weights checkpoint, no overlay.

- Model: [orcarouter/Qwen3.8-27B-Uncensored-NVFP4] — ~24.7 GB, compressed-tensors **mixed** NVFP4
  FFN + FP8 attention/GDN, static FP8 KV, `qwen3_5`; abliterated BF16 base → quantised; vision
  tower and MTP head preserved (MTP head is BF16).
- Runtime sglang, TP 1. Flags: **no `--quantization`** — SGLang auto-detects `compressed-tensors`
  from `config.json` (the card is explicit the mixed-precision `quantization_config`, including
  the FP8 `kv_cache_scheme`, must be read from the config) — and `--kv-cache-dtype auto` so the
  checkpoint keeps ownership of the KV dtype. Served id: `orcarouter/Qwen3.8-27B-Uncensored-NVFP4`.
- Boots (`GET /v1/models` = repo id); receipts in attic AGENTS.md §8. Plain decode — no spec decode
  wired even though the MTP head is preserved.
- **Decode ladder (2026-10-18, one GB10, shipped chain): C1 9.75 ± 0.24 · C2 19.67 ± 0.52 ·
  C5 41.12 ± 0.78 · C10 75.77 ± 7.18 t/s** @ d=0, pp 2048, tg 128, n=5, decode rows read from the
  `--output` file — `bench_4c30a992c771`, receipt
  `~/benchmarks/ladders-solo-20261018/cybersec-unc-ladder.yaml`. It keeps climbing to c10 because
  the pool carries the whole ladder: 358,261 fp8 KV tokens at `context_len=262144` with
  `max_running_requests=24`, so ten concurrent 2048-in/128-out requests never queue and the
  aggregate is 10 × 7.6 t/s. Same boot: battery **easy 19/19 + hard 18/18 = 37/37**
  (`cybersec-unc-battery.json`).
- **Standard suite (legs 2026-10-19, tools leg 2026-10-19/20).** The suite was relaunched tools-only
  after its first run was killed for a cap that could not hold BFCL, so this boot has **no
  machine-readable `contract` line**; the other four legs are in
  `~/benchmarks/cybersec-27b-unc-suite-20261019/`. house **37/37** (easy 19/19, hard 18/18), needle
  **3/3 at 32,768 / 131,072 and 262,144** (all PASS — this arm's pool *does* carry the top rung, unlike
  its NEXTN sibling's 167,985), hard **ARC 187/200 (93.5 %)** and **GSM8K 194/200 (97.0 %)**, tools
  **1072/1240 = 86.45 %** with **0 transport errors** in **37,366 s = 30.1 s/question**
  (`~/benchmarks/cybersec-27b-unc-tools-20261019/bfcl.json`, 1,240 records).
  The category spread degrades as the questions get harder — simple 369/400, multiple 187/200,
  parallel 183/200, parallel_multiple 168/200, irrelevance 165/240 — and the 30.1 s/question is the
  number that prices a plain-decode arm's tools leg: 1,240 questions cost ~10.4 h here against ~3.5 h
  for NEXTN and ~2.5 h for DFlash2, so a plain arm's `--job-timeout` must allow for it or its tools run
  must go cap-free.

- `mamba_full_memory_ratio: 3.51` splits the leftover pool between GDN state and the token pool —
  the same interior-point trade documented for the qwen3.8-27B lane (`attic/qwen3/AGENTS.md` §5);
  left un-retuned here (no stated traffic mix for this checkpoint).
- `kv_cache_dtype: auto` is left at `auto` so the checkpoint keeps ownership of the KV dtype: this
  export ships a static FP8 `kv_cache_scheme`, and `auto` resolves from it.

## `qwen3.8-27b-uncensored-nvfp4-nextn-sglang`

**Arm 1's spec-decode sibling — POSITIVE (TP=1).** Same checkpoint, same weights, same gated repo;
the only difference from the plain arm is the speculative block, so everything below is a measure of
NEXTN rather than of a different body. Boot-verified 2026-10-18 (`aefb625955c32638_64af2f7668b6`),
receipt `~/benchmarks/cybersec-nextn-20261018/`.

- Runtime sglang, TP 1. `speculative_algorithm: NEXTN` is the engine's alias for EAGLE with the
  target's own draft head: the engine rewrote it (`speculative_algorithm': 'EAGLE'`) and loaded the
  checkpoint's own BF16 `Qwen3_5ForCausalLMMTP` as the draft — **no `--speculative-draft-model-path`
  and nothing extra for sparkrun to distribute**. `speculative_num_steps: 3`, `topk 1`,
  `num_draft_tokens: 4` (topk 1 forces steps+1, so 4 is the only legal width).
- Serves (`GET /v1/models` = repo id, `max_model_len` 262144); TTR port 149.0 s / HTTP 162.9 s. Same
  image digest as the DFlash2 sibling (`@sha256:0b3e3970…`), `mem_fraction_static` 0.85,
  `max_num_seqs: 24`, `mamba_full_memory_ratio: 3.51`, `kv_cache_dtype: auto`.
- **Cells (`cells.json` decode rows, `bench_cab845506821`):** C1 **14.72 ± 1.13** @ d0 /
  **14.59 ± 1.14** @ d8192 against the plain-decode control's **10.21 / 9.66** — **+44.1 % /
  +51.0 %**. Acceptance length **2.774** at c=1 (n=39 decode-batch lines, min 1.80, max 3.58); all 40
  logged batches exceed 1. The arithmetic behind the gain: 2.77 tokens per verify step at 14.72 t/s
  ≈ 0.19 s/step, against 0.098 s/token on the control — the step costs ~1.9× and returns 2.77
  tokens. Battery **easy 19/19 + hard 18/18 = 37/37**, the control's own bar, unchanged.
- **Capability cost to write down — the served context is not the advertised one:**
  `max_total_num_tokens` is **167,985**, below the 262,144 `max_model_len`; a request beyond it will
  be rejected. The attribution to the draft pool is **unverified** — the control's boot log was not
  retained, so this number cannot be differenced against the plain arm in this receipt.
- For scale: the DFlash2 sibling (`.34`, a different abliterated body) runs 30.2–33.8 t/s, so NEXTN
  reaches ~44–49 % of that ceiling. Single boot: this box's inter-boot floor is 7–25 % and NEXTN's
  C1 tracks acceptance, so a second boot cannot separate those — but a 44–51 % delta is well outside
  that band.
- The recipe's `metadata.caveats` still say "Unmeasured — no receipt yet": **stale as of 2026-10-18**.

## `qwen3.8-27b-ablit-cyber-unlock-nvfp4-dflash2-sglang`

**Arm 2 — POSITIVE (TP=1).** Overlay arm: the overlay repo ships **no weights**.

- Body: [sakamakismile/Qwen3.8-27B-AEON-ULTIMATE-UNCENSORED-NVFP4] — ~20.5 GB + 0.85 GB MTP,
  compressed-tensors NVFP4, `qwen3_5`, AEON-7 abliteration. Draft: [z-lab/Qwen3.8-27B-DFlash2].
- The overlay [drowzeys keys-Qwen3.8-27B…Single-DGXSpark] adds only the cybersecurity-unlock
  **chat template** (+ the YaRN rope overlays for the 1M route), staged by
  `recipes/cybersec/mods/provide-uncensored-chat-template` into `/cache/runtime/uncensored-template/` and passed
  via `--chat-template`.
- Runtime sglang, TP 1, DFlash2 spec decode; `--kv-cache-dtype auto`. Served id:
  `sakamakismile/Qwen3.8-27B-AEON-ULTIMATE-UNCENSORED-NVFP4` — the AEON body *through the cyber
  template*.
- Boots (`GET /v1/models` = repo id; uncensored template confirmed in the serve log); receipts in
  attic AGENTS.md §8.
- **Decode ladder (2026-10-17, one GB10, shipped chain): C1 30.2 ± 1.5 · C2 49.4 ± 6.8 · C5 84.6 ± 9.1
  · C10 92.9 ± 5.1 t/s** @ d=0, pp 2048, tg 128, n=5 — `bench_3ee8fda63ada`, receipt
  `~/benchmarks/ladders-solo-20261017/`. The index row's C2/C5/C10 are this boot; its C1 33.3 is the
  earlier single-point figure. Per-request decode falls 30.2 → 25.8 → 21.3 → 14.6 t/s across the four
  cells while the aggregate rises, so the arm scales by stream count, not by per-stream speed — the
  same shape the qwen3.8-27B NVFP4 sibling shows on its own ladder.

- `chat_template_path` is the file `recipes/cybersec/mods/provide-uncensored-chat-template` writes into the managed
  runtime cache (`/cache/runtime/uncensored-template/chat_template.jinja`); the command consumes it
  via `--chat-template`.
- `max_num_seqs: 48` is a clamp, not the granted concurrency: the dense 27B body (48 GDN + 16
  full-attention layers) hits the same mamba-state-pool clamp as the qwen3.8-27B NVFP4 recipe —
  read `capped to` in the serve log for the real number.


**Standard suite — four of five legs pass (2026-10-19, one boot).** Contract `max_model_len=262144`,
ready, `finish=stop`; house **37/37** (19/19 + 18/18); hard **ARC 184/200 (92.0 %) · GSM8K 187/200
(93.5 %)**; tools **1064/1240 (85.8 %)** in 8,978 s. **Needle reads `fail` at 3/3 · 3/3 · 3/3**: the
262,144 rung's reply hit the 512-token answer budget (`status: TRUNCATED`, the reasoning-only shape the
0.9B arm also shows), so the verdict is the instrument's, not a retrieval miss — at 131,072 and 32,768
every depth answered. Receipt `~/benchmarks/cybersec-27b-ablit-suite-20261019/` (`summary.json`,
per-check JSON, `bfcl.json`).

## `nex-n2.5-mini-uncensored-nvfp4-sglang`

**Arm 3 — NEGATIVE (TP=1).** Weights checkpoint, no overlay.

- Model: [orcarouter/Nex-N2.5-mini-Uncensored-NVFP4] — ~23.9 GB, compressed-tensors NVFP4
  **routed experts only** (rest BF16), `qwen3_5_moe` (256E top-8 + 1 shared, 3:1 GDN), no MTP
  head upstream. Runtime sglang, TP 1. Served id: the repo id. Recipe flag:
  `--default-chat-template-kwargs '{"reasoning_effort": "none"}'` (Nex gates thinking on
  `reasoning_effort`, not `enable_thinking`, and ships no `generation_config.json`).
- **Negative under SGLang**; **vLLM route unblocked 2026-10-15** (companion recipe
  `nex-n2.5-mini-uncensored-nvfp4-vllm.yaml`, which serves this checkpoint on the scheme its card
  documents). Under SGLang the checkpoint loads and the server reports ready, then the first
  generation dies — NaN sample-time logits → CUDA device-side assert; with the override dropped
  it serves degenerate empty / repeated-`!` text. The named gate was **image distribution**, and it
  is resolved: the uploader documents vLLM's `CompressedTensorsW4A4`, the pinned vLLM image
  (`ghcr.io/spark-arena/dgx-vllm-eugr-nightly@sha256:7717585a…`) maps this export's
  `nvfp4-pack-quantized` group — NVFP4 weights **and** NVFP4 activations — onto
  `CompressedTensorsW4A4Fp4`, and that image is resident with an identical digest on the head,
  `.34`, and `.35` (a direct `docker pull` by digest measured 76–142 MB/s on `.34`, not the
  ~0.3 MB/s the relay streamed). **Boot receipt taken 2026-10-15** (four bounded boots, job
  `9e32c36ca6496294_8ed3ce77d78f`, receipt `~/benchmarks/cybersec-nex-20261015/`): the route comes
  up in ~4.3 min (TTR port-open 257.6 s) and `/v1/chat/completions` answers, but **generation
  degenerates** — greedy and sampled, thinking-on and answer-channel, every shape returns one
  repeated token (`duct…` greedy, `!` sampled) and the reasoning trace never closes at 800 tokens.
  So the **route** is verified and the **checkpoint** is not servable on it: the recipe stays as the
  route record and carries **no index row** (an arm that cannot serve keeps its recipe, not its row).
  Full triage, the four probes, and the container evidence: attic AGENTS.md §8.
- **Re-measured 2026-10-16 on the newer `dev-cu13`** (the digest the three SGLang arms now pin,
  `@sha256:0b3e3970…`, engine `0.0.0.dev1+gc15edf314`): the assert is gone — the server comes up and
  answers — but every greedy probe (thinking-on, answer-channel, `reasoning_effort: none`) returns 64
  identical `!` tokens, i.e. the same degeneration the vLLM route shows. The failure follows the
  **checkpoint**, not the engine. Receipt `~/benchmarks/pins-20261016/`.

- **The template kwarg is route-scoped, and the original reading was wrong for vLLM.** The claim
  above (the template gates thinking on `reasoning_effort`, so `{"reasoning_effort": "none"}` is
  required) came from the SGLang arm and has not been re-tested there; on the vLLM route the
  2026-10-15 receipt shows it is **inert** — `content: null` whether it arrives as the server
  default or per request — while `chat_template_kwargs {"enable_thinking": false}` is what fills
  `content` (1600 chars where the other shapes returned none). The vLLM recipe now ships the value
  that works; a caller wanting the scratchpad passes `{"reasoning_effort": "high"}` per request.

## `qwen3.8-flash-next-uncensored-nvfp4-sglang`

**Arm 4 — NEGATIVE (TP=2).** Weights checkpoint, no overlay.

- Model: [orcarouter/Qwen3.8-Flash-Next-Uncensored-NVFP4] — ~183.5 GB (the ~100 GB bf16 PLE
  n-gram tensor dominates the size), compressed-tensors NVFP4 experts + FP8 attention,
  weight-only, KV bf16, `qwen4_exp`. Runtime sglang, TP 2, `gpu_memory_utilization: 0.85`
  (~184 GB sits near the two-node 0.85 ceiling). Served id: the repo id.
- **Negative under SGLang; vLLM route unblocked 2026-10-15** (companion recipe
  `qwen3.8-flash-next-uncensored-nvfp4-vllm.yaml`). SGLang's compressed-tensors loader maps the
  export's scheme to `CompressedTensorsW4A16Sparse24` and refuses (`ImportError` at scheduler init) — a
  **loader-scheme** failure, not memory, distribution, or the arch. On the card's vLLM route the same
  `mixed-precision` config resolves **per group** to `CompressedTensorsW8A16Fp8` (the `naive-quantized`
  FP8 attention/GDN and shared-expert group) and `CompressedTensorsW4A4Fp4` (the NVFP4 experts group,
  weight-only), and `Qwen4ExpForConditionalGeneration` imports from `vllm/models/qwen4_exp` — both
  established in the pinned image `ghcr.io/spark-arena/dgx-vllm-eugr-nightly@sha256:7717585a…`, which
  is resident with an identical digest on the head, `.34`, and `.35`. The "image distribution is
  unusable" gate is **superseded** (see attic AGENTS.md §8): a direct `docker pull` by digest measured
  76–142 MB/s on `.34`, and the relay's ~0.3 MB/s was the relay's own stream, not the network.
  **Route evidence is loader-level, not measured serving behaviour.** The checkpoint (183.5 GB per
  node) was *not* reclaimed on 2026-10-14 as previously recorded here: both `.34` and `.35` have
  held it complete since the 2026-10-15 staging, re-verified 2026-10-21 (18/18 shards, 183.48 GB,
  zero bytes fetched), so no re-fetch cost remains and the index rows wait only on a boot receipt
  (`.35` still carries 78.06 GB of orphan `.incomplete` blobs from the 2026-10-15 attempt — residue
  for a storage pass, not a partial tree). Pinning
  `--quantization` to another value is **not** a fix: arm 1 shows SGLang reads the right scheme from
  `config.json` when the export is one it implements.

**The vLLM route is measured NOT BOOTABLE on the pinned image (2026-10-19, two launches).** Both
attempts died at model load with `ValueError: Found different quantization schemes for the shards of
language_model.model.layers.3.self_attn.qkv_proj` from compressed-tensors' `should_ignore_layer`.
Mechanism: the image's `qwen4_exp` model maps `qkv_proj` onto four shards including
`indexer.index_qk_proj` (`vllm/models/qwen4_exp/nvidia/model.py:703`) so the fused QKV+indexer GEMM
can load it, while the export keeps that indexer in bf16 (`ignore`, no `weight_scale` in the tensor
map). A fused linear cannot carry two schemes, so the loader refuses. The model's LoRA path is
written to avoid this — `model.py:726` swaps in a three-shard mapping and `qsa.py:508` skips the
fusion — but the swap lands after `get_quant_config` has already captured the four-shard mapping, so
`--enable-lora` (attempt 2, confirmed in the engine's non-default args) fails identically. Unblocking
is image-side: a vLLM build whose mapping excludes ignored shards, or a model-code mod (engine change
→ owner approval). Receipt `~/benchmarks/cybersec-flashnext-20261019/REPORT.md`. No index row.

**Both candidate engines are now refuted, on two different gates (2026-10-21).** The b12x build
`sha256:cf5a2a53…` (vLLM `0.1.dev21830+g8244d1c44.d20261015`) cannot construct the model config at
all — `ModelConfig` rejects the export's `layer_types` because `qwen_sparse_attention` is not one of
its members, so no weight is read and the compressed-tensors question above is never reached.
`vllm/vllm-openai:v0.31.0@sha256:c1c9f6fd…` clears that schema gate (multi-modal warmup and NCCL
`world_size=2` run) and then dies at worker init with
`NotImplementedError: Qwen4Exp PLE embedding does not support quantization config
CompressedTensorsConfig`. What this arm needs is an image that has **both** `qwen_sparse_attention`
and a PLE-embedding-aware compressed-tensors path; neither named build has both, and no recipe knob
moves either. Receipt `~/benchmarks/cybersec-flashnext-b12x-20261021/`.

**Engine-image trap, for any future adoption of the upstream vLLM image:** `vllm/vllm-openai`
declares `ENTRYPOINT ["vllm","serve"]`, which consumes the launcher sparkrun appends — the launch is
refused until it is cleared (`executor_config: {entrypoint: ""}`, or `-o entrypoint=` for one run).
The sparkrun-built `b12x` image has no such entrypoint, so a recipe that swaps between them needs
that line.

## `deepseek-v4.1-flash-abliterated-cyber-tp2-tensorfold-sglang`

**Arm 5 — POSITIVE (TP=2).** Graft arm: the overlay repo ships **no weights**.

- Stock: the [combined littlecedar pack][combined pack] — ~197 GB of EXL3 mul1 K=5 weights (39
  shards) **plus the Engram tables** under `engram/`, the same repo the ds4 TP=2 arm serves
  (weight shards byte-for-byte the Mia pack; pinned to `48afcd1c…`). The overlay [drowzeys
  DeepSeek-V4.1-Flash-Abliterated…Unleashed] is a 682 MB `layers.10-35 attn.wo_b` **EXL3 mul1
  K=5 sidecar** that `recipes/cybersec/mods/graft-dsv41-ablit-wo-b` grafts onto that pack under
  `/cache/runtime/dsv41-ablit` (104 tensors edited; L0-9, L36-39, MTP, embed/head, experts stay
  stock), synchronously and fail-closed inside the 600 s pre-exec hook budget (measured 148 s /
  137 s per node on the combined stock, 2026-10-17).
- Runtime sglang shim → `mods/tensorfold-dsv41-launcher` (reused unchanged from the ds4 lane).
  The command carries `--stock-model {model}`: the validator's identity token **and** the pack
  the launcher reads the Engram tables from. Served id:
  `drowzeys/DeepSeek-V4.1-Flash-Abliterated-Cybersecurity-Unleashed` — the graft tree's
  identity, not the body pack. GPU memory utilisation stays ≤ 0.85.
- **One pack per node serves both TP=2 arms** since 2026-10-17: the arm no longer mounts
  `recipes/cybersec/mods/dsv41-engram-fetch`. The graft tree links the stock pack's `engram/`
  rather than copying it. The author's script hardlinks every shard it does not edit but
  `shutil.copytree`s every *directory* — `engram/` is one — and a hardlink of the snapshot's own
  **relative** `../../blobs/…` symlink does not resolve outside the snapshot, so grafting straight
  from it both copied the ~189 GiB table set and left those shards as dead links. The mod hands the
  script a view of absolute symlinks with `engram/` excluded, and symlinks the tables in: the tree
  measures **119 GiB** (`du` == `du --apparent-size`; the 24 rewritten shards are the only real
  bytes, the other 15 and `engram/` are links).
- **The tree is generation-checked on every boot.** The mod resolves its stock from `refs/main`
  (the recipe's `model_revision` never reaches the mod), so a complete tree is only no-oped while
  its copied metadata (`config.json`, `tokenizer_config.json`, `model.safetensors.index.json`,
  `quantization_config.json`, `chat_template.jinja`) still matches the stock that resolved: a moved
  `main` fails the launch instead of pairing a new Engram table set with the tree's old hardlinked
  weights. Delete `/cache/runtime/dsv41-ablit` to rebuild at the new generation.
- **The served prompt changed with the stock.** The graft tree copies the combined pack's
  `chat_template.jinja` (the pack's 15,348 B upstream file) where the Mia-era graft carried the
  older 11,410 B exl3-era template — the guard-free one `attic/ds4/AGENTS.md` §12.14 credits for the
  2026-10-06 vision success. This arm passes no `--vision`, so it serves that file as-is: an
  `image_url` part answered HTTP 400 from the template before 2026-10-17 and a client-typed
  placeholder does so now, and any arm-5 number measured earlier is not template-comparable.
- **Decode ladder (2026-10-19, TP=2, shipped chain, engram ON):** C1 **67.02 ± 3.19 · C2 52.95 ±
  1.49 · C5 47.75 ± 0.53 · C10 46.78 ± 0.33 t/s** @ d0, pp 2048, tg 128, n=5, decode rows of
  `bench_484eb77839b4` (`ladder.json`); receipt `~/benchmarks/cybersec-arm5-ladder-20261019/`.
  The aggregate falls with concurrency — the TensorFold shape the ds4 TP=2 stock arm shows
  (68.6 / 48.1 / 44.6 / 42.1) — with per-request decode 50.19 / 38.24 / 34.29 t/s at c2/5/10.
  This C1 (engram ON) supersedes the 63.7 decode-triage figure from the engram-OFF 2026-10-17 boot
  (`bench_44534d5024c0`).
- **Standard suite — all five legs landed (2026-10-20 / 2026-10-21, one serve each).** contract ok
  (`max_model_len` 1,048,576, ready, `finish=stop`); house **37/37** (easy 19/19, hard 18/18); needle
  **3/3 at 32,768 / 131,072 / 262,144** (depth 10, `PASS` each); hard **ARC 188/200 (94.0 %)** and
  **GSM8K 197/200 (98.5 %)** with 0 empty replies; tools **1037/1240 = 83.6 %** in 3,887 s (0
  transport errors), split simple **376/400** · multiple **188/200** · parallel **181/200** ·
  parallel_multiple **177/200** · irrelevance **115/240**. The AST categories are healthy (all 1,000
  `finish=tool_calls`); the loss is `irrelevance`, all 125 misses `irrelevance_error:decoder_success`
  — a capability result, not a parser fault. Receipts `~/benchmarks/cybersec-arm5-20261020/` (four
  legs, plus the tools attempt drained at 116/1,240) and
  `~/benchmarks/cybersec-arm5-tools-20261021/` (`REPORT.md` merges all five, `bfcl.json`).
- Boots (1M ctx, `GET /v1/models` = the overlay repo id); receipts in attic AGENTS.md §8.

## Attic index

Lane state, receipts, and research notes live in [`attic/cybersec/`](../../attic/cybersec/).
Currently the directory holds one file:

| file | what it holds / question it answers |
|---|---|
| `AGENTS.md` | The lane's durable operating guide, moved here 2026-10-14 when lane docs consolidated into this README. §1 gating and the per-repo token prerequisite · §2 the served-id convention (`{served_model_name}`, never `{model}`) · §3 revision pins and why `model_revision` must be top-level · §4 measured artifact facts (on-disk sizes, quant schemes, template traps) · §5 the two overlay mods and the 600 s graft budget · §6 arm 5 detail (ds4 lane reuse, Engram) · §7 the validation ritual · §8 per-arm boot + measurement receipts. Everything after the dated heading is README material displaced by this rewrite (the old arm table with C1/battery, the overlay pairing lore, the served-id table, reproduce commands, the cache-reclamation note, other surfaced arms). Answers: why a launch died without a token, why the serve log shows a `/cache/...` id, which revision is pinned, how big each checkpoint is, why the graft must fit 600 s, what each arm measured. |

<!-- Links -->
[orcarouter/Qwen3.8-27B-Uncensored-NVFP4]: https://huggingface.co/orcarouter/Qwen3.8-27B-Uncensored-NVFP4
[sakamakismile/Qwen3.8-27B-AEON-ULTIMATE-UNCENSORED-NVFP4]: https://huggingface.co/sakamakismile/Qwen3.8-27B-AEON-ULTIMATE-UNCENSORED-NVFP4
[z-lab/Qwen3.8-27B-DFlash2]: https://huggingface.co/z-lab/Qwen3.8-27B-DFlash2
[drowzeys keys-Qwen3.8-27B…Single-DGXSpark]: https://huggingface.co/drowzeys/keys-Qwen3.8-27B-NVFP4-DFlash2-Ablit-Cybersecurity-Unlock-1M-Context-YARN-Single-DGXSpark
[orcarouter/Nex-N2.5-mini-Uncensored-NVFP4]: https://huggingface.co/orcarouter/Nex-N2.5-mini-Uncensored-NVFP4
[orcarouter/Qwen3.8-Flash-Next-Uncensored-NVFP4]: https://huggingface.co/orcarouter/Qwen3.8-Flash-Next-Uncensored-NVFP4
[Mia-AiLab/DeepSeek-V4.1-Flash-EXL3-2.9bpw]: https://huggingface.co/Mia-AiLab/DeepSeek-V4.1-Flash-EXL3-2.9bpw
[combined pack]: https://huggingface.co/littlecedar/DeepSeek-V4.1-Flash-EXL3-2.9bpw-with-engram
[drowzeys DeepSeek-V4.1-Flash-Abliterated…Unleashed]: https://huggingface.co/drowzeys/DeepSeek-V4.1-Flash-Abliterated-Cybersecurity-Unleashed
