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
- [`qwen3.8-27b-ablit-cyber-unlock-nvfp4-dflash2-sglang`](#qwen38-27b-ablit-cyber-unlock-nvfp4-dflash2-sglang) — arm 2, positive (TP=1), overlay
- [`nex-n2.5-mini-uncensored-nvfp4-sglang`](#nex-n25-mini-uncensored-nvfp4-sglang) — arm 3, negative under SGLang; vLLM route unblocked (+ `nex-n2.5-mini-uncensored-nvfp4-vllm`)
- [`qwen3.8-flash-next-uncensored-nvfp4-sglang`](#qwen38-flash-next-uncensored-nvfp4-sglang) — arm 4, negative under SGLang; vLLM route unblocked (+ `qwen3.8-flash-next-uncensored-nvfp4-vllm`)
- [`deepseek-v4.1-flash-abliterated-cyber-tp2-tensorfold-sglang`](#deepseek-v41-flash-abliterated-cyber-tp2-tensorfold-sglang) — arm 5, positive (TP=2), graft
- [Attic index](#attic-index)

## Gating and the token prerequisite

**All five arms are gated on the Hub (`gated: auto`).** A distributed registry cannot assume an
`HF_TOKEN`, so the prerequisite is explicit here and in every recipe's `metadata.caveats`:

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

- `mamba_full_memory_ratio: 3.51` splits the leftover pool between GDN state and the token pool —
  the same interior-point trade documented for the qwen3.8-27B lane (`attic/qwen3/AGENTS.md` §5);
  left un-retuned here (no stated traffic mix for this checkpoint).
- `kv_cache_dtype: auto` is left at `auto` so the checkpoint keeps ownership of the KV dtype: this
  export ships a static FP8 `kv_cache_scheme`, and `auto` resolves from it.

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

- `chat_template_path` is the file `recipes/cybersec/mods/provide-uncensored-chat-template` writes into the managed
  runtime cache (`/cache/runtime/uncensored-template/chat_template.jinja`); the command consumes it
  via `--chat-template`.
- `max_num_seqs: 48` is a clamp, not the granted concurrency: the dense 27B body (48 GDN + 16
  full-attention layers) hits the same mamba-state-pool clamp as the qwen3.8-27B NVFP4 recipe —
  read `capped to` in the serve log for the real number.
- `speculative_draft_tokens: 8` is the block size the z-lab draft was trained for (the overlay's
  own seat used n=7).

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
  **Route evidence is loader-level, not measured serving behaviour**, and this checkpoint (183.5 GB
  per node) was reclaimed from every node's cache on 2026-10-14 — so the remaining cost is a
  183.5 GB-per-node re-fetch, which the index rows wait on along with a boot receipt. Pinning
  `--quantization` to another value is **not** a fix: arm 1 shows SGLang reads the right scheme from
  `config.json` when the export is one it implements.

## `deepseek-v4.1-flash-abliterated-cyber-tp2-tensorfold-sglang`

**Arm 5 — POSITIVE (TP=2).** Graft arm: the overlay repo ships **no weights**.

- Stock: [Mia-AiLab/DeepSeek-V4.1-Flash-EXL3-2.9bpw] — ~197 GB, EXL3 mul1 K=5, 39 shards, TP 2.
  The overlay [drowzeys DeepSeek-V4.1-Flash-Abliterated…Unleashed] is a 682 MB
  `layers.10-35 attn.wo_b` **EXL3 mul1 K=5 sidecar** that `recipes/cybersec/mods/graft-dsv41-ablit-wo-b` grafts
  onto the stock pack under `/cache/runtime/dsv41-ablit` (104 tensors edited; L0-9, L36-39, MTP,
  embed/head, experts stay stock), synchronously and fail-closed inside the 600 s pre-exec hook
  budget (measured 269 s / 284 s per node).
- Runtime sglang shim → `mods/tensorfold-dsv41-launcher` (reused unchanged from the ds4 lane).
  The command carries `--stock-model {model}` (the validator's identity token) instead of
  `--revision {model_revision}`. Served id:
  `drowzeys/DeepSeek-V4.1-Flash-Abliterated-Cybersecurity-Unleashed` — the graft tree's identity,
  not the body pack. Engram tables (~95 GiB each) are **not** in the EXL3 checkpoint and are
  provisioned detached by `recipes/cybersec/mods/dsv41-engram-fetch`; GPU memory utilisation stays ≤ 0.85.
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
[drowzeys DeepSeek-V4.1-Flash-Abliterated…Unleashed]: https://huggingface.co/drowzeys/DeepSeek-V4.1-Flash-Abliterated-Cybersecurity-Unleashed
