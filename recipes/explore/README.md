# Explore lane

Frontier reasoning + tool-calling models for one DGX Spark node, selected by the owner's criterion for
this lane (**accuracy decides; smaller and faster preferred**, 2026-10-13 — supersedes the registry's
node-count→speed default). Every arm here is single-node (TP=1). The lane ships the two selected
recipes (**Ling-3.0-flash-int4**, rank 1; **Kolibri-1**, rank 2) plus four measured arms added
2026-10-14 (the Poolside Laguna pair, `humanizer`, and the eval-only `Qwen-Image`), one arm **added by the
owner on 2026-10-15 and boot-verified the same day** (**Mellum2.1-12B**, from the `JetBrains/mellum21`
collection, so outside the ranking) — its index row carries the ladder and
the 36/37 house battery, and it was the first single-node text arm with C2/C5/C10 filled (the
laguna-XS arm followed with the full suite on 2026-10-17), and **2026-10-17 added the registry's first `runtime: llama-cpp` arm** (Mellum's Q4_K_M GGUF, boot-verified the same day); the LTX-2.5 video arm ships as a runbook. Everything else — measured
histories, selection receipts, serving traps and the full candidate research — lives in
[`attic/explore/`](../../attic/explore/) (index below).

## Contents

- [ling-3.0-flash-int4-dspark-sglang](#ling-30-flash-int4-dspark-sglang)
- [kolibri-1-78b-fp8-vllm](#kolibri-1-78b-fp8-vllm)
- [poolside-laguna-xs-2.1-nvfp4-dflash-vllm](#poolside-laguna-xs-21-nvfp4-dflash-vllm)
- [poolside-laguna-s-2.1-nvfp4-dflash-vllm](#poolside-laguna-s-21-nvfp4-dflash-vllm)
- [humanizer-12b-vllm](#humanizer-12b-vllm)
- [qwen-image-2.1-turbo-7b-bf16-diffusers-script](#qwen-image-21-turbo-7b-bf16-diffusers-script)
- [mellum2.1-12b-a2.5b-bf16-thinking-vllm](#mellum21-12b-a25b-bf16-thinking-vllm)
- [mellum2.1-12b-a2.5b-q4km-thinking-llamacpp](#mellum21-12b-a25b-q4km-thinking-llamacpp)
- [LTX-2.5 ComfyUI runbook (not a recipe)](#ltx-25-comfyui-runbook-not-a-recipe)
- [Attic index](#attic-index)

---

## [ling-3.0-flash-int4-dspark-sglang](ling-3.0-flash-int4-dspark-sglang.yaml)

SGLang · **1 node (TP=1)** · **rank 1 — kept (accuracy champion)**.

- **Model:** `inclusionAI/Ling-3.0-flash-int4` (MIT) + the DSpark draft `inclusionAI/Ling-3.0-flash-dspark`
  (pinned `d60b0e12…`).
- **Size / memory:** ~77 GB INT4 weights (+ 2.7 GB draft); 154 GB distributed (`model_file_selection: all`
  is required — the 17.59 MiB safetensors index exceeds the 16 MiB inventory cap).
- **Flags / non-obvious knobs:** `mem-fraction-static: 0.80` (KV pool 313,752 tokens; 0.87 stays the
  documented OOM-risk ceiling); `served_model_name: inclusionAI/Ling-3.0-flash-int4` declared *and*
  rendered (sparkrun otherwise rewrites `{model}` to the snapshot path); the draft pin is rendered as
  `--speculative-draft-model-revision {speculative_draft_model_revision}` (not distribution-only). KDA
  ReplaySSM verify path.
- **Serving note:** the official LMSYS `sglang:dev-Ling-3.0-flash` image runs the arm — the
  third-party Spark port's GHCR image predates the `dspark_components` /
  `--enable-linear-replayssm-spec` flags this recipe needs (digest-pinned).
- **Measured:** C1 **45.5 t/s** @ d0 (σ 5.5, n=5) / 32.3 @ d8k; quality **37/37** (ties the top of the
  pass); 262k needle PASS at 0.80.
- **Licence:** MIT.

## [kolibri-1-78b-fp8-vllm](kolibri-1-78b-fp8-vllm.yaml)

vLLM 0.29 + vendor plugin [`recipes/explore/mods/install-kolibri-plugin`](mods/install-kolibri-plugin) ·
**1 node (TP=1)** · **rank 2 — kept (near-tie accuracy; smaller + faster)**.

- **Model:** `Aleph-Alpha/Kolibri-1` (Apache-2.0), pinned `258cae8f…`.
- **Size / memory:** 74 GB FP8 (73.5 GiB); `gpu_memory_utilization: 0.78` → KV 18.99 GiB → 1,859,922 tokens.
- **Flags / non-obvious knobs:** the vendor image is amd64-only, so the recipe serves on the
  digest-pinned stock `vllm/vllm-openai:v0.29.0` with the pure-Python plugin installed `--no-deps` (the
  mod fails closed on import/entry-point failure, idempotent via a content marker);
  `executor_config: {entrypoint: ""}` (the image declares `ENTRYPOINT ["vllm","serve"]`); **thinking is
  ON by default** → callers need a larger `max_tokens` or thinking off, else truncated thinking yields an
  empty `content` (`tools/quality-battery.py --max-tokens`).
- **Flags (extra):** bare `recipes/explore/mods/install-kolibri-plugin` (unpublished-mod form — the scoped
  `@littlecedar/mods/…` fails) and launches need `--transfer-mode local`; `OMP_NUM_THREADS=4` and
  `gpu_memory_utilization: 0.78` (not the 0.85 ceiling) are the measured GB10 boot working point (CUDA
  reports ~11 GiB less than `MemAvailable`).
- **Measured:** C1 **47.3 t/s** @ d0 (σ 0.10) / 46.3 @ d8k; quality 36/37 @4096 (a **37/37 union** — the
  lone miss is a thinking-budget truncation).
- **Licence:** Apache-2.0.

## [poolside-laguna-xs-2.1-nvfp4-dflash-vllm](poolside-laguna-xs-2.1-nvfp4-dflash-vllm.yaml)

vLLM · **1 node (TP=1)** · measured 2026-10-14 · not selected.

*Engine held at digest-pinned `vllm/vllm-openai:v0.29.0` — vLLM 0.30.0 cannot construct this
revision's config (its own `LagunaConfig` shadows the transformers 5.17 class that does); 2026-10-16
engine-bump note in [`attic/explore/AGENTS.md`](../../attic/explore/AGENTS.md).*

- **Model:** `poolside/Laguna-XS-2.1-NVFP4` (33B total / 3B active, 256 routed experts, 3:1 SWA,
  262,144 native; OpenMDW-1.1), pinned `d32afde8…` + the first-party draft `poolside/Laguna-XS-2.1-DFlash`
  (0.92 GB), pinned `5c36361a…`.
- **Size / memory:** 21.6 GB + 0.92 GB draft; `gpu_memory_utilization: 0.55` → KV 41.56 GiB → 1,403,263
  tokens (5.35× at the native window).
- **Flags / non-obvious knobs:** NVFP4 engages natively on sm121 (`FlashInferCutlassNvFp4LinearKernel` +
  `FLASHINFER_CUTLASS` NvFp4 MoE); the draft rides in `defaults.speculative_config` with its own
  `revision`, so sparkrun both distributes and pins the blob; `num_speculative_tokens: 3` ships (a
  `decode-triage` sweep of n ∈ {3,4,7} → n=3 wins both depths); **thinking is NOT on by default despite
  the card** → the serve line passes `--default-chat-template-kwargs '{"enable_thinking": true}'`.
  **Rope caveat:** a boot warning about SWA rope is unexplained; the 2026-10-17 needle probe answers
  **3/3 at 262,144** but only 2/3 at 32k/131k (n=3 each) — the long-window miss the caveat predicted
  did not appear, and the small-depth misses are unexplained.
- **Serving note:** util 0.55 is deliberate — the weights are only ~21.6 GB of the ~121 GiB pool and
  the SWA arch keeps 262k cheap, so the low util preserves ~95 GB of node headroom.
- **Measured:** C1 **57.4 t/s** @ d0 (σ 3.4) / 55.1 @ d8k; accept len 1.89 / 29.5%; quality 36/37 @4096.
- **Standard suite (2026-10-17, `bench_9b207347ec3b`):** ladder @ d0 pp2048 tg128 n=5 — C1 **55.3**
  (σ 2.4) / C2 83.1 (σ 2.1) / C5 133.7 (σ 8.4) / C10 141.3 (σ 3.3) t/s; `tools/eval-suite.py` 3 ok /
  2 fail — house easy 19/19 + hard 16/18, needle 2/3 @32k / 2/3 @131k / **3/3 @262k** (n=3 each), arc
  66.0% (n=200) / gsm8k 90.5% (n=200), bfcl 60.1% (745/1240); the two fails are **contract**
  (`finish=length`, all-empty reply at the 262,144 window — the reasoning parser's empty-`content`
  shape, thinking burning `max_tokens`) and **needle** at the two smaller depths. TEB
  (`standard-suite.yaml`): 15 scenarios, 14 pass + 1 partial, score 97. Receipts
  `head:~/benchmarks/explore-laguna-xs-20261017/`.
- **Licence:** OpenMDW-1.1 (target and draft).

## [poolside-laguna-s-2.1-nvfp4-dflash-vllm](poolside-laguna-s-2.1-nvfp4-dflash-vllm.yaml)

vLLM · **1 node (TP=1)** · measured 2026-10-14 · not selected (capped-context single-tenant).

*Engine held at digest-pinned `vllm/vllm-openai:v0.29.0` — vLLM 0.30.0 cannot construct this
revision's config (its own `LagunaConfig` shadows the transformers 5.17 class that does); 2026-10-16
engine-bump note in [`attic/explore/AGENTS.md`](../../attic/explore/AGENTS.md).*

- **Model:** `poolside/Laguna-S-2.1-NVFP4` (117.6B total / 8.5B active MoE, native 1,048,576 ctx;
  OpenMDW-1.1) + the quantization-matched draft `poolside/Laguna-S-2.1-DFlash-NVFP4` (2.2 GB).
- **Size / memory:** 99.7 GB download / **95.61 GiB resident** (the August-2026 checkpoint — the research
  doc's ~67 GiB figure does not hold); `gpu_memory_utilization: 0.85`, `max_model_len: 122880` (120k) →
  KV 4.64 GiB / 125,796 tokens (1.02× — a single-tenant 120k arm). The 262k window does **not** fit one
  Spark (vLLM refuses; it needs ~0.89 util, above the repo's 0.85 ceiling).
- **Flags / non-obvious knobs:** DFlash `num_speculative_tokens: 3`; native FP4 path
  (`FLASHINFER_CUTLASS` NvFp4 MoE on sm121) + `FLASHINFER` attention.
  `MAX_JOBS=4` caps the cold cutlass/FP4 JIT fan-out (an uncapped nvcc can exhaust the 128 GB pool) and
  `max_num_seqs: 32` is required (DFlash crashes vLLM at the default 256).
- **Licence (recorded as required):** the *shipped* draft `poolside/Laguna-S-2.1-DFlash-NVFP4` declares
  **no licence at all**; the BF16 sibling is `license: other` with no in-repo text — "other" resolves
  only by implication to the target's OpenMDW-1.1 (commercial + non-commercial).
- **Measured:** C1 **20.49 t/s** @ d0 (σ 0.93) / 20.11 @ d8k; accept len mean 2.52 / 50.8% rate; quality
  32/37.

## [humanizer-12b-vllm](humanizer-12b-vllm.yaml)

vLLM · **1 node** · the lane's first **`/v1/completions`** arm · not selected (off-brief).

- **Model:** `jialinyyzz/humanizer` — a 12B `google/gemma-4-12B` finetune (Apache-2.0, ungated), 23.9 GB
  bf16, 8192 ctx. **Not a chat model** — it rewrites one AI-written draft so it reads human.
- **Flags / non-obvious knobs:** the working surface is `/v1/completions` with a **byte-exact prompt**
  assembled from the repo's `prompt_format.json` (`instr + "\n\n" + draft.strip() + sep`; fingerprint
  `cc51d66b4c593fbe`, asserted on every call); the checkpoint ships **no chat template** (the chat
  endpoint 400s); `--generation-config vllm` so the checkpoint's own `top_k 64` never becomes a server
  default; `limit_mm_per_prompt {"image":0,"audio":0,"video":0}` → text-only; heterogeneous head dims
  (256 sliding / 512 full) force `TRITON_ATTN`. Whole-repo distribution: **87.6 GB** at the pinned
  revision (23.9 GB safetensors + 63.6 GB of GGUFs it never loads) — and not narrowable.
  `model_file_selection` is a sparkrun **config** key, not a recipe key, and with no
  `model.safetensors.index.json` both `auto` and `all` select the full snapshot (`safetensors` errors).
  Digest-pinned `vllm/vllm-openai:v0.30.0` — moved 2026-10-16 and boot-verified on it (task
  `sparkrun_17678da2f7107eb2_a4bf874feb5a`, receipt `~/benchmarks/bump-20261016/`).
- **Measured:** ~7.6 t/s single-stream; 131.7 s per 1k output tokens; across 40 rewrites, 0 dropped facts
  (1 genuine defect found outside the instrument).
- **Licence:** Apache-2.0.

## [qwen-image-2.1-turbo-7b-bf16-diffusers-script](qwen-image-2.1-turbo-7b-bf16-diffusers-script.yaml)

diffusers engine (no `sglang`/vLLM serves it) + [`recipes/explore/mods/qwen-image-2.1-turbo-launcher`](mods/qwen-image-2.1-turbo-launcher) ·
**1 node** · eval-only.

> **LICENCE — NON-COMMERCIAL ONLY.** `Qwen/Qwen-Image-2.1-Turbo` is under the **Qwen Research License
> Agreement** (card `license: other`, `license_name: qwen-research`): **FOR NON-COMMERCIAL PURPOSES
> ONLY**. This registry is distributed to third parties. A recipe ships a repo id, not weights — each
> downloader fetches from the Hub and accepts the licence there — but **neither the weights nor images
> generated from them may be used commercially**. An operator needing commercial use must swap the
> checkpoint; the serving path (`recipes/explore/mods/qwen-image-2.1-turbo-launcher` + the recipe) is
> checkpoint-agnostic. **Owner call 2026-10-14: ship the recipe with this banner.**

- **Model:** `Qwen/Qwen-Image-2.1-Turbo` (pinned `fc13ba1986`), text-to-image + editing, 8-step distilled
  at CFG=1.
- **Size / memory:** 32.5 GB bf16 (DiT 14.2 + text encoder 17.5 + VAE 0.68); peak ~36.85 GiB torch alloc /
  37.68 GiB reserved.
- **Flags / non-obvious knobs:** `runtime: vllm` is the family whose distribution + single-node launcher
  contract the command satisfies; `command:` runs a stdlib HTTP server (`POST /generate`, `GET /health`)
  out of a `diffusers>=0.41` / `transformers>=5.17` venv the mod stages on the image's own torch
  (`vllm/vllm-openai:v0.30.0`; the venv's own `transformers>=5.17` satisfies the card's floor — the
  image's copy is unused). **VAE tiling OFF**
  (tiled decode → a pink seam column) and **`cpu_offload` OFF** (costs ~4× on a reference image);
  `--served-model-name` is rendered explicitly.
- **Measured:** 1024² / 8-step CFG=1 → **11.3–11.4 s** steady; a reference image fed back for editing
  +3.5 s; same prompt+seed → a byte-identical PNG.
- **Details:** [`attic/explore/QWEN-IMAGE.md`](../../attic/explore/QWEN-IMAGE.md).

## [mellum2.1-12b-a2.5b-bf16-thinking-vllm](mellum2.1-12b-a2.5b-bf16-thinking-vllm.yaml)

vLLM · **1 node (TP=1)** · built + **boot-verified 2026-10-15** · index row present.

*Engine held at digest-pinned `vllm/vllm-openai:v0.29.0` — vLLM 0.30.0 shadows transformers 5.17's
`MellumConfig` with its own `Qwen3MoeConfig` stub and breaks this checkpoint's nested rope config at
load; 2026-10-16 engine-bump note in [`attic/explore/AGENTS.md`](../../attic/explore/AGENTS.md).*

- **Model:** `JetBrains/Mellum2.1-12B-A2.5B-Thinking` (Apache-2.0, ungated) — 12B total / 2.5B active MoE
  (64 routed experts, 8 per token), 28 layers, 32 Q / 4 KV heads (head_dim 128), 131,072 context, sliding
  window 1,024 on 3 of every 4 layers (7 full-attention, 21 sliding) with YaRN factor 16 over 8,192 on the
  full layers; pinned `92ddae9f…` (`main`, 2026-10-07). **Owner-added 2026-10-15** from the
  `JetBrains/mellum21` collection, so it sits above the lane's ranked list and carries no ranking.
- **Size / memory:** 24.3 GB bf16 (24,301,065,318 B, 5 shards); 22.4 GiB of weights to the engine.
  `gpu_memory_utilization: 0.55` → 66.6 GiB budget, deliberately below the 0.85 ceiling: the weights are
  ~22.4 GiB of a ~121 GiB pool and a hybrid-SWA context is cheap, so the arm keeps ~55 GiB of node
  headroom. sparkrun's render estimate (7.0 GiB KV demand at 131,072, **all 28 layers assumed to cache the
  full window** — it ignores the 3:1 sliding structure) is not the engine's number; the serve log's
  `GPU KV cache size` line is.
- **Flags / non-obvious knobs:** vLLM 0.29 carries the architecture natively — `MellumForCausalLM` is a
  Qwen3-MoE subclass whose decoder layer picks the attention type per `config.layer_types[idx]` and reads
  RoPE as `config.rope_parameters[layer_type]`, i.e. exactly this checkpoint's shape — so the arm needs
  **no mods** and no registry-clone refresh. **Thinking is ON by default** (the template writes the empty
  think block only for `enable_thinking: false`): callers must budget a large `max_tokens` or a truncated
  reasoning run arrives with an empty `content`. `--reasoning-parser qwen3` (the card's choice; vLLM has
  no `mellum` parser) targets the template's own think form, but whether it actually lifts
  the trace into `reasoning_content` on this arm is **unverified** — the receipt's contract artifact
  reports `reasoning_len: 0` against `usage.reasoning_tokens: 58` (see
  [`attic/explore/MELLUM-21.md`](../../attic/explore/MELLUM-21.md) §6.2) — and
  `--enable-auto-tool-choice --tool-call-parser hermes` parses the template's
  `<tool_call>{"name": …, "arguments": …}</tool_call>` form (tool results return as a
  `<tool_response>` user turn). No draft/speculative decode: the card names the MTP head "coming soon".
- **Client-side contract:** the card's sampling point is temperature 0.6 / top_p 0.95 / top_k 20 with
  `max_tokens` up to 81,920 (thinking + answer). The recipe sets **no** server-side sampling default —
  the checkpoint's `generation_config.json` carries only bos/eos, so there is nothing to protect with
  `--generation-config` (unlike `humanizer`).
- **Measured (2026-10-15, one boot on `.35`, receipt `~/benchmarks/mellum-20261015/`):** decode ladder
  @ d0 pp2048 tg128 n=5 → **C1 42.3 ± 0.1 / C2 67.2 ± 0.6 / C5 99.9 ± 1.7 / C10 135.6 ± 1.1 t/s**;
  house battery **36/37** (easy 18/19 — the one miss is `needle-1`; hard 18/18); contract ok (served id
  is the HF repo id, `max_model_len` 131,072, finish `stop`). The arm scales cleanly to c10, which is
  what the 66.6 GiB budget was for. **Receipt gap, stated:** the serve's container had already been
  stopped when the log capture ran, so `serve.log`/`grants.txt` are empty — the engine's own
  `GPU KV cache size` line is not in the receipt, and the launch record is sparkrun's
  `launch.log` only. Card numbers (self-reported by JetBrains, unverified here): LiveCodeBench v6 82.0,
  SWE-bench Verified 47.0, BFCL v4 62.3, MMLU-Redux 87.8.
- **Licence:** Apache-2.0.
- **Details (provenance, the GGUF-route decision, the six open boot questions):**
  [`attic/explore/MELLUM-21.md`](../../attic/explore/MELLUM-21.md).

## [mellum2.1-12b-a2.5b-q4km-thinking-llamacpp](mellum2.1-12b-a2.5b-q4km-thinking-llamacpp.yaml)

llama.cpp · **1 node (TP=1)** · **the registry's first `runtime: llama-cpp` arm** — the GGUF route
[`attic/explore/MELLUM-21.md`](../../attic/explore/MELLUM-21.md) §5 deferred, shipped on the owner's
2026-10-16 directive and boot-verified 2026-10-17.

- **Model:** `JetBrains/Mellum2.1-12B-A2.5B-Thinking-GGUF` (Apache-2.0, ungated), quant `Q4_K_M` —
  8,067,705,856 B / 12,149,923,072 params (`/v1/models` meta: `ftype` `Q4_K - Medium`).
- **Engine:** `scitrera/dgx-spark-llama-cpp:b10549-cu131@sha256:ad140554…` (digest-pinned; llama.cpp
  `b2e5e9b`, CUDA 13.1); `n_ctx` 131,072 × 8 slots `kv_unified`; `--no-mmap` (GB10 forces it unless
  opted back in); `--jinja`; `--reasoning-format deepseek` splits thinking into `reasoning_content`
  while tool calls keep `finish_reason: tool_calls`.
- **Boot:** 2026-10-17 on `.34`, TTR ≈ 100 s (launch → `/v1/models` 200); served id = the HF repo id
  (`--alias` renders from its own `served_model_name` key, not `{model}` — sparkrun rewrites
  `{model}` to a checkpoint path).
- **Measured (one boot, receipt `~/benchmarks/mellum-gguf-20261017/`):** decode ladder @ d0 pp2048
  tg128 n=5 → **C1 111.9 ± 0.3 / C2 151.1 ± 2.6 / C5 208.0 ± 2.8 / C10 146.4 ± 1.5 t/s**
  (`perf-ladder.yaml`, decode rows; `bench_4247926b7b9a`). Shape: the aggregate peaks at c5 and falls
  at c10 because the arm grants 8 slots and the c10 cell runs 10 streams — per-request decode spreads
  to 32.9 ± 16.1 t/s at c10 (vs 111.9 at c1) while the engine's peak window still reaches 202.2 t/s.
  House battery **37/37** (easy 19/19, hard 18/18); hard arc 77.0% / gsm8k 93.5% (n=200 each);
  `standard-suite` profile (tool-eval-bench) **97** — 15 scenarios, 14 pass, 1 partial; deployability
  84, responsiveness 54; bfcl **73.5%** (911/1240, no transport errors — audited). The loss is
  category-shaped, not noise: `parallel` 46.5% and `parallel_multiple` 41.0% carry it, and **179 of
  their 400 questions returned no tool call at all** — bare `content: ''` plus a think block whose
  median is ~2.0k chars against the valid records' 826 (`bfcl-eval.py` sends `max_tokens=512` by
  default; a no-call reply is scored FAIL by design, `tools/bfcl-eval.py:55-56`). LIKELY the same
  think-block budget shape as the needle cells below — the run records no `finish_reason`, so this is
  inferred, not proven, and the fix-probe (one parallel question at a raised `--max-tokens`) is unrun.
  A further 26 failures did emit exactly one call; that minority is not the mechanism.
- **Needle:** 131k rung **3/3 PASS** at `paced_target` 128,451 (completions 123–186). 32k rung: 1/3 at
  the suite's 256-token default — the two empty cells are the thinking-budget class below, not
  retrieval; re-probes reach **3/3 by union** (depth 50 PASS at `--max-tokens 4096` — 722 completion
  tokens; depth 90 PASS with `chat_template_kwargs: {"enable_thinking": false}` — 9 tokens, 0.74 s).
  `n_ctx` 131,072 is honored end to end (contract check reads it after the fix below).
- **The thinking-budget trap, this engine's form:** with thinking on (the template's default) a hard
  32k prompt can spend an arbitrary budget inside the think block — empty `content` at
  `finish_reason: length`. Raise `max_tokens` or send `enable_thinking: false`. Found here: the needle
  leg scored that shape FAIL, and llama.cpp's window lives at `meta.n_ctx` (no top-level
  `max_model_len`), so the 2 % clamp never ran and the 131k rung overflowed the window. Both tool-side
  false-FAIL classes are fixed in `590b9b2` (`tools/needle-haystack.py` records `finish_reason` and
  marks the shape TRUNCATED; both tools read the nested window) — receipt note
  `NOTE-needle-tool-fix.md`.
- **Licence:** Apache-2.0.
- **Details:** [`mad-science/LLAMACPP-GGUF.md`](../../mad-science/LLAMACPP-GGUF.md) §5 (bring-up +
  suite) and §4 (standing policy: a GGUF sibling must beat the lane battery, not the uploader's table).

## LTX-2.5 ComfyUI runbook (not a recipe)

`Lightricks/LTX-2.5` (video+audio world model, 22B distilled DiT + Gemma-4-12B encoder) ships as a
**runbook, not a recipe** — the runtime is ComfyUI (no `sglang`/vLLM engine) and the repo is `gated: auto`
(a per-node `HF_TOKEN` + accepted terms is a prerequisite sparkrun cannot assume). See
[`ltx-2.5-runbook/README.md`](ltx-2.5-runbook/README.md). Weights ≈36.9 GB; two-stage T2V (8-step @
672×384 → upscale → 3-step refine @ 1344×768, 121 frames + audio): cold 90–100 s, warm 80 s, peak
83.6 GiB. Licence `ltx-2.x-community-license-agreement` (free below a $10M-revenue Commercial Entity
threshold). Lane notes: [`attic/explore/LTX-25.md`](../../attic/explore/LTX-25.md).

## Attic index

Everything that is not a shipped recipe lives in [`attic/explore/`](../../attic/explore/) — lane working
state, measured histories, selection receipts, serving traps, and the candidate research.

| file | what it holds / the question it answers |
|---|---|
| [`AGENTS.md`](../../attic/explore/AGENTS.md) | The lane's working notes: the full previous README — per-arm measured histories (Ling, Kolibri, Nemotron, the Laguna pair, humanizer, Qwen-Image, LTX-2.5), the selection record, and the serving/measurement traps 1–6. Start here for "why did this lane pick what it picked?" |
| [`EXPLORE-MODELS-RESEARCH.md`](../../attic/explore/EXPLORE-MODELS-RESEARCH.md) | The read-only research pass: 8 candidate families (§1), top-3 sequencing (§2), corrections to `mad-science/EXPLORE-CANDIDATES.md` (§3), the battery note (§4), per-arm GB10 evidence + verification checklists for the Laguna family (§5), the media-gen arms (§6) and `humanizer` (§7), and the 2026-10-16 `tfwnotops/…-ConstantKV` Kolibri-1M research queue entry (§8). Answers "what else could this lane serve, and on what precedent?" |
| [`LTX-25.md`](../../attic/explore/LTX-25.md) | LTX-2.5 bring-up notes: access/prerequisite, the pinned ComfyUI unit, weights, the two-stage measurement table, the traps re-learned. Answers "how was the LTX-2.5 runbook measured, and what did it cost?" |
| [`QWEN-IMAGE.md`](../../attic/explore/QWEN-IMAGE.md) | Qwen-Image-2.1-Turbo bring-up notes: the licence banner, engine/venv design decisions, the §6 acceptance table, and the two mod defects found. Answers "how was the eval-only image arm built and verified?" |
| [`MELLUM-21.md`](../../attic/explore/MELLUM-21.md) | Mellum2.1-12B bring-up: the owner-added collection provenance, the checkpoint/chat-template facts read at the pin, why vLLM 0.29 needs no mod, the revision resolution, the **GGUF/llama.cpp route decision (recorded, not shipped)** and the six open boot questions. Answers "why does a JetBrains model use the `qwen3` reasoning parser, and what must the first boot prove?" |
| [`ARMS-MANIFEST.md`](../../attic/explore/ARMS-MANIFEST.md) | Manifest of the archived (measured-but-not-selected) Explore recipes with the selection ranking and the archive criterion/policy. |
| [`nemotron-3.5-lightning-30b-nvfp4-dspark-vllm.yaml`](../../attic/explore/nemotron-3.5-lightning-30b-nvfp4-dspark-vllm.yaml) | Archived recipe — the lane's original shipped default (262k, util 0.80), the fastest measured arm (77.7 t/s) and the smallest (21 GB), but the lane's lowest accuracy (33/37). Frozen provenance — do not retune. |
| [`nemotron-3.5-lightning-30b-nvfp4-dspark-1m-vllm.yaml`](../../attic/explore/nemotron-3.5-lightning-30b-nvfp4-dspark-1m-vllm.yaml) | Archived recipe — a variant of the 262k arm testing the card's 1M-context claim at util 0.91. Frozen provenance — do not retune. |
