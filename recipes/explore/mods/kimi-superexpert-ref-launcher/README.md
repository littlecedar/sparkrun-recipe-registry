# kimi-superexpert-ref-launcher

Reference serve for `shashanth-27xA9/Kimi-K3.1-Pro-SuperExpert-12GB` (probe arm
`recipes/explore/zz-kimi-k3.1-pro-superexpert-24b-q4p-ref-vllm.yaml`).

## What the artifact actually is (probed 2026-11-08)

| claim (card) | probe |
|:--|:--|
| "2.8T MoE, 104B active, consolidated by AW-SECD" | 581 tensors with dense llama-style names (`self_attn.{q,k,v,o}_proj`, `mlp.{gate,up,down}_proj`, `embed_tokens`, `lm_head`) and **no expert/router tensors**. 12,008,815,872 U8 elements + F16 per-tensor scales: 4-bit nibble packing, ~24B logical parameters in 12 GB. |
| "Gated DSA + KDA attention" | `modeling_kimi_k31_superexpert.py` uses plain `scaled_dot_product_attention`, causal mask, no sparse/mixed attention — and **no positional scheme at all** (no RoPE, no position ids) while `config.json` declares `max_position_embeddings` 1048576. A NoPE design is legitimate long-context (the Ripple arm in this tree is NoPE at 1M), so the right claim is *unverifiable from the shipped artifacts*, not impossible. |
| tag `8-bit` | the shards are U8 **4-bit** nibbles with one F16 scale per tensor; `config.json` says `float16` (a compute dtype, not storage). |
| tag `gguf` | `kimi-k3.1-pro-superexpert-12gb-q4_k_m.gguf` is 623 B: valid GGUF v3 magic, **tensor_count 0**, 11 metadata pairs, arch `kimi_k31_moe` (not a llama.cpp architecture). Filename says q4_k_m; there are no weights. |
| "94.8 % retention on ARC/GSM8K/HumanEval/MMLU/IFEval" | no eval harness, fixtures or receipt in the repo; a 12 GB checkpoint cannot be validated against a 2.8T base from this artifact. Treated as unverified. |
| `license: apache-2.0` | base `moonshotai/Kimi-K3.1-Pro` ships the **Kimi K3.1-Pro License** (`license: other`): derivative use is granted, but condition 1 requires the copyright notice in copies/sublicenses, and §2–§3 attach Model-as-a-Service/scale conditions. The derived repo carries **no LICENSE file** and relicenses as Apache-2.0. Internal research use is exempt from §2/§3, but the notice obligation and the relicensing claim are defects to record, not to fix. |
| `endpoints_compatible` | no engine loads the architecture (below), so no compatible endpoint exists until a loader exists. |

Other measured facts: config declares 36 layers, hidden 7168, 96 heads (MHA, no GQA), vocab 163840,
`max_position_embeddings` 1048576 and `moe_intermediate_size` 3072; tokenizer is a custom
`TikTokenTokenizer` over a 2.8 MB `tiktoken.model` and `tokenizer_config.json` has **no
`chat_template`**; `Modelfile` points at a filename that does not exist, uses literal placeholder
markers in its template, and claims sub-10GB. Two plain config-vs-code gaps sit in the artifact:
`moe_intermediate_size` 3072 is declared while the modeling code builds one dense
`KimiSuperExpertMLP` per layer (the cleanest evidence, and it does not depend on interpreting a
missing positional scheme), and the `KimiK31SuperExpertConfig` class default
`compressed_footprint_gb` is **9.2** where `config.json` and the card say **12.0**.

## Engine decision

- **vLLM / SGLang — cannot load.** Both resolve `architectures` against their own model registries;
  `auto_map` remote modeling is not a serving path, and neither engine has a kernel for a U8
  nibble-packed linear dequantized inside `forward()`. A launch fails at model resolution.
- **llama.cpp — cannot load.** The only GGUF carries zero tensors, and `kimi_k31_moe` is not an
  architecture the engine knows.
- **transformers reference — the only constructible route**, which is what this mod runs.

Discriminator: architecture present only in the repo's `auto_map` + zero-tensor GGUF + custom
tokenizer. Not verified: numerics/quality of the weights; whether a vLLM model-registry extension
could add the arch (out of scope for a probe).

## What a boot would test

1. the 18 shards load through the repo's own `_load_from_state_dict` (U8 weight + `weight.scale`);
2. a greedy completion returns coherent text at all — i.e. whether the "consolidated" weights are
   real or noise;
3. head/embedding consistency under `lm_head` dequant;
4. cost of the reference route (Python dequant per forward) — a correctness probe, never a
   serving benchmark.

Until 2026-11-08 this arm is **authored-not-booted** — and it was attempted twice in that window
without producing a measurement, for a recipe reason now identified and fixed.

- **Attempts.** Both launches in the `campaign-queue` window failed; the retained second attempt's
  log names the cause: `serve.py: error: unrecognized arguments: --served-model-name
  shashanth-27xA9/Kimi-K3.1-Pro-SuperExpert-12GB`, followed by `head container not running`. The
  receipt (`zz-kimi-k3.1-pro-superexpert-24b-q4p-ref-vllm/`) carries a
  241 B reaped serve log with that usage text and a `launch.log` whose timings total 34.4 s
  (run 16.8 s + launch 14.7 s); the watchdog's line is `verdict=dead serve_pid=gone` at 11 s.
  Nothing loaded, so there is no cell and no quality number.
- **Cause and fix.** sparkrun's vllm runtime appends `--served-model-name <model id>` to *any* vllm
  command it renders (it cannot know a free-form `command:` scripts its own server), and this
  launcher's argparse did not accept the flag. `serve.py` now takes `--served-model-name` and reports
  that value from `/v1/models` (falling back to `SERVED_MODEL_NAME`, then the default). The fix is
  **unretested**; the arm stays authored-not-booted until a launch reaches a token.
- **What a boot must not be read as.** Whatever the house battery says on this arm is a ~24B dense
  artifact's number. It is not a measurement of `moonshotai/Kimi-K3.1-Pro` and must never be quoted
  as a 2.8T result; the probe's job is coherence of the dequant path, not capability ranking.
