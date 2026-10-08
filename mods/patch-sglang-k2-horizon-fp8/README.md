# patch-sglang-k2-horizon-fp8

Relax the two `if` statements in SGLang's native K2-Horizon implementation that
refuse the published `IFM/K2-Horizon-MoVA-36B-A4B-FP8` checkpoint, so the FP8
export can be served on the native path at all.

```
mods/patch-sglang-k2-horizon-fp8/
  run.sh                   patch, in place, inside the container (idempotent, fail-closed)
  unpatch.sh               restore the stock file from the mod's own backup copy
  test_k2_fp8_guard.py     self-contained verifier: 0 patched, 1 unpatched, 2 harness-failed
  README.md                this file
```

No `REQUIREMENTS.txt`: stdlib and coreutils only. `pyyaml` is not needed because the
mod never parses the checkpoint — it edits one Python file.

## What it patches

Both sites are in `python/sglang/srt/models/xllm.py` (line numbers at
`sglang main @ 95521da`, 2026-09-20; also verified present at tag `v0.5.20`).

| anchor | line | stock behaviour |
|---|---|---|
| gate 1 | `:664`, inside `_validate_mova_config()` | `get_name() != "compressed_tensors"` → `ValueError`. This checkpoint resolves to `Fp8Config` (`get_name() == "fp8"`), so it dies here. |
| gate 2 | `:1229`, inside `_XllmMoVAAttentionBase.__init__()` | `quant_config is not None` → `ValueError("K2 Horizon MoVA supports unquantized bf16/fp16 weights only")`. Reached once per layer, **48 times**: both `XllmMoVAAttention` (layers 3-47) and `XllmGatedAttention` (the dense prefix, layers 0-2) subclass this base, and `XllmDecoderLayer` hands the live `quant_config` to both (`xllm.py:1470-1487`). |

`_validate_mova_config` is called from `XllmForCausalLM.__init__` at `xllm.py:1707`,
so gate 1 fires during model construction — **after** the 48 GB has synced to every
host, seconds before anything else happens. That timing is what makes the E0
falsification probe cheap: the failure is fast and its message is unambiguous.

## Why relaxing them is safe rather than hopeful

The whole argument, in the order that matters. It is a claim about **construction
sites**, which is why `run.sh` re-checks it on every run instead of trusting it.

1. **MoVA's value path cannot be quantised no matter what we pass down.**
   `q_proj`, `k_proj`, `gate_proj`, `o_proj` are constructed with a literal
   `quant_config=None` (`xllm.py:1264-1298`). So is `v_router` (`xllm.py:1394-1399`),
   whose bias is force-cast to fp32 (`xllm.py:1400-1406`). The value experts are
   `RoutedValueExperts` (`xllm.py:1407-1413`), a class that takes no `quant_config`
   argument at all. So all 2,880 `self_attn.v_experts.N.weight` tensors — **15.1 GB**,
   31 % of the checkpoint — plus both routers and all of MoVA attention stay BF16.
   This holds even if a future checkpoint drops them from `ignored_layers`.
2. **Only two module families receive the live `quant_config`:** `FusedMoE`
   (`xllm.py:936-944`) and the shared-expert `XllmMLP` (`xllm.py:951-957`).
3. **The shared expert stays BF16** because `ignored_layers` lists
   `model.layers.N.mlp.shared_experts.gate_proj`, which is the SGLang module name; the
   fused `gate_up_proj` prefix is expanded back to `{gate_proj, up_proj}` by
   `_FALLBACK_FUSED_SHARDS` (`srt/layers/quantization/utils.py:61-66`). The `mlp.gate`
   router entry cannot collide with `mlp.gate_up_proj` because `_module_path_match`
   (`utils.py:47-59`) matches on dotted boundaries precisely so that it cannot.
4. **So exactly the routed experts become FP8 — and the scale names already match.**
   `FusedMoE.make_expert_params_mapping` rewrites
   `experts.7.gate_proj.weight_scale_inv → experts.w13_weight_scale_inv`
   (`srt/layers/moe/fused_moe_triton/layer.py:1650-1675`), and `Fp8MoEMethod`
   registers `w13_weight_scale_inv` / `w2_weight_scale_inv` for block-quant
   (`srt/layers/quantization/fp8.py:1509-1536`). `weight_scale_inv` **is** SGLang's
   native block-FP8 name. Nothing is left at an initialiser value.

## Why not just rewrite the checkpoint's metadata instead

The tempting alternative is a mod that rewrites `config.json`'s
`quantization_config` from `quant_method: "fp8"` into a compressed-tensors descriptor,
walking past gate 1 without touching engine code. It was drafted and rejected, for
one reason:

**The compressed-tensors scheme registers the block-scale buffer as `weight_scale`
(`srt/layers/quantization/compressed_tensors/schemes/compressed_tensors_w8a8_fp8.py:106-113`)
while this checkpoint stores `weight_scale_inv`.** The native-fp8 scheme registers it as
`weight_scale_inv`, which matches. Under a re-wrap, if the name correspondence is
missed, the buffer keeps its `torch.finfo(torch.float32).min` initialiser and the
dequantisation silently multiplies every expert block by that constant. The symptom is
plausible-looking text with a clean startup log — the worst class of failure on a
benchmark rig, because it produces numbers instead of an error.

Two additional reasons: rewriting metadata is editing the artifact under test, and a
re-wrap must reproduce compressed-tensors' full schema (`format`, `config_groups`,
`targets`, `weights.strategy: block`, `input_activations.dynamic`, and all 3408
`ignore` patterns) correctly, any single mismatch of which is a fresh failure mode.
Editing two guards keeps the artifact intact and keeps the failure loud.

## Failure modes and what they mean

| observed | meaning |
|---|---|
| `FATAL anchor mismatch {'gate1': 0, ...}` | The container's sglang moved off `95521da`. **Do not widen the anchors.** Re-read `srt/models/xllm.py` around lines 664 and 1229 and update the mod, or the recipes using it lose their claim to have been reasoned about. |
| `SELF-CHECK FAILED: q_proj stays unquantised` | Upstream started threading `quant_config` into the MoVA value path. The mod's safety argument no longer holds. Stop; re-read `xllm.py:1264-1298` and `1394-1413`. |
| `FATAL patched file does not compile` | Anchor substitution produced invalid Python. Nothing was written (temp + `os.replace`), so the container is still stock. |
| `FATAL cannot write …` | site-packages is not writable in this container. Nothing to do but choose an image where it is, or carry the change in a forked image. |
| `already patched` | Idempotent no-op. This is the correct output on a second boot. |
| boot succeeds, text is wrong | This mod cannot rule that out. It is a static argument about method selection, not a numerical test. Run the BF16-vs-patched greedy continuation (D2) in the worklog before believing any throughput from the patched recipe. |

## Escape hatches

| variable | effect |
|---|---|
| `SPARKRUN_SKIP_MOD=1` | skip entirely, exit 0 |
| `SPARKRUN_K2_FP8_GATE_ONLY=1` | relax gate 1 only. The build then dies at gate 2 with upstream's own message — that **is** the falsification arm (`zz-k2-36b-a4b-fp8-unpatched-probe-sglang.yaml`), it is supposed to fail. |
| `SPARKRUN_SGLANG_PKG=<dir>` | override package discovery |
| `SPARKRUN_K2_FP8_ALLOW_DRIFT=1` | anchor mismatch becomes a warning and only the matched anchors are applied. **Triage only**: the resulting tree is not certified and every numeric claim in the recipe that used it is void. |
| `SPARKRUN_K2_FP8_BACKUP=<dir>` | where the stock copy is kept (default `<mod_root>/patch-sglang-k2-horizon-fp8/.backup`) |

## Verifying

```
uv run python mods/patch-sglang-k2-horizon-fp8/test_k2_fp8_guard.py \
    "$(python3 -c 'import sglang,os,pathlib;print(pathlib.Path(sglang.__file__).parent/"srt/models/xllm.py")')"
```

Exit codes follow the precedent set by
`mods/fix-sglang-spec-metrics-empty-verify/test_spec_metrics_guard.py`: **0** patched,
**1** unpatched, **2** harness failure (missing file, unreadable). A bare run with no
argument exits 2, which is never a verdict on the patch.

Local verification performed 2026-09-21 against two independent trees, both patched,
compiled and self-checked clean: `sglang main @ 95521da`, and `v0.5.20` fetched from
GitHub raw. Both anchor sets match exactly once in each.

## Scope

Applied by:
- `recipes/ifm/k2-horizon-36b-a4b-fp8-tp1-sglang.yaml`
- `recipes/ifm/k2-horizon-36b-a4b-fp8-tp2-sglang.yaml`

Deliberately **not** applied by `k2-horizon-36b-a4b-bf16-tp1-sglang.yaml` (the BF16
checkpoint has no `quantization_config`, so `quant_config` is `None` and both gates
pass on their own terms) nor by `zz-k2-36b-a4b-fp8-unpatched-probe-sglang.yaml`
(whose entire purpose is to observe the unpatched failure).

Never put this mod in a **vLLM** recipe chain. vLLM registers
`K2HorizonForCausalLM` natively (`vllm/model_executor/models/registry.py`, merged as
vllm-project/vllm#55063, in the registry since tag `v0.29.1rc0` and stable-numbered from
`v0.30.0` — eight days old, and with no GitHub release object yet for `v0.30.0`), has no
equivalent arch gate,
and its `Fp8Config` already reads `quant_method: "fp8"` + `weight_block_size` +
`ignored_layers` (`vllm/model_executor/layers/quantization/fp8.py:96-184`). `run.sh`
fails loudly rather than silently no-op'ing if it is pointed at a tree with no
`xllm.py`, because the more dangerous mistake is a chain that looks applied and is not.
