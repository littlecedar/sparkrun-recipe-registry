# kimi-superexpert-ref-launcher

Reference serve for `shashanth-27xA9/Kimi-K3.1-Pro-SuperExpert-12GB` (probe arm
`recipes/explore/zz-kimi-k3.1-pro-superexpert-24b-q4p-ref-vllm.yaml`).

## What the artifact actually is (probed 2026-11-08)

| claim (card) | probe |
|:--|:--|
| "2.8T MoE, 104B active, consolidated by AW-SECD" | 581 tensors with dense llama-style names (`self_attn.{q,k,v,o}_proj`, `mlp.{gate,up,down}_proj`, `embed_tokens`, `lm_head`) and **no expert/router tensors**. 12,008,815,872 U8 elements + F16 per-tensor scales: 4-bit nibble packing, ~24B logical parameters in 12 GB. |
| "Gated DSA + KDA attention" | `modeling_kimi_k31_superexpert.py` uses plain `scaled_dot_product_attention`, causal mask, no sparse/mixed attention. |
| tag `8-bit` | the shards are U8 **4-bit** nibbles with one F16 scale per tensor; `config.json` says `float16` (a compute dtype, not storage). |
| tag `gguf` | `kimi-k3.1-pro-superexpert-12gb-q4_k_m.gguf` is 623 B: valid GGUF v3 magic, **tensor_count 0**, 11 metadata pairs, arch `kimi_k31_moe` (not a llama.cpp architecture). Filename says q4_k_m; there are no weights. |
| "94.8 % retention on ARC/GSM8K/HumanEval/MMLU/IFEval" | no eval harness, fixtures or receipt in the repo; a 12 GB checkpoint cannot be validated against a 2.8T base from this artifact. Treated as unverified. |
| `license: apache-2.0` | base `moonshotai/Kimi-K3.1-Pro` ships the **Kimi K3.1-Pro License** (`license: other`): derivative use is granted, but condition 1 requires the copyright notice in copies/sublicenses, and §2–§3 attach Model-as-a-Service/scale conditions. The derived repo carries **no LICENSE file** and relicenses as Apache-2.0. Internal research use is exempt from §2/§3, but the notice obligation and the relicensing claim are defects to record, not to fix. |
| `endpoints_compatible` | no engine loads the architecture (below), so no compatible endpoint exists until a loader exists. |

Other measured facts: config declares 36 layers, hidden 7168, 96 heads (MHA, no GQA), vocab 163840,
`max_position_embeddings` 1048576; tokenizer is a custom `TikTokenTokenizer` over a 2.8 MB
`tiktoken.model` and `tokenizer_config.json` has **no `chat_template`**; `Modelfile` points at a
filename that does not exist, uses literal placeholder markers in its template, and claims sub-10GB.

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

Until 2026-11-08 this arm is **authored-not-booted**: `.local/fleet-window.lock` names all six nodes
for session `campaign-queue` (`window_stamp 2026-11-08T03:37Z`), and this session does not own that
window.
