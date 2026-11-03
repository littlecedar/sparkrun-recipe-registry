# Fine-tuning LFM3

Toolkit survey for training `lfm3` / `lfm3_vl` / `lfm3_audio` / `lfm3_omni` checkpoints on the
fleet. Survey row `liquidai-finetune-toolkits`, read through 2026-11-03. Seven candidates checked;
**two usable**, one of those measured end to end here; five rejected on a gate that was actually
exercised. Receipts: `~/benchmarks/liquidai-finetune-20261103/`.

No node was booted for this survey (`.30` research sweep, `.31`–`.34` production, `.35` not needed
— nothing here is a speed question). What ran instead: the reference stack trained on CPU
(`.35`-shaped recipe, x86 host) and every toolkit was read at source and at wheel-metadata level
for aarch64 + `sm_121`. Gates 2 and 3 therefore carry wheel/arithmetic evidence, not node numbers,
and each entry says which.

Receipt layout under `~/benchmarks/liquidai-finetune-20261103/`: `*.json` for run results
(`reference-path`, `grad-flow`, `load-transformers-<ver>`, `unsloth-cpu`), `pypi/<dist>.json` for
the version, file list and pins read off PyPI, `source/<toolkit>.txt` for the exact source lines
quoted below, `logs/` for run logs and the probe scripts, plus the `adapter/` and `merged-bf16/`
artifacts.

## What actually decides it: the `transformers` floor

Two measured facts reorder this whole survey; both were assumed wrong before they were checked.

**1. `lfm3` is not in `transformers` at all, up to and including 5.22.1** (no `models/lfm3` in the
5.6.0, 5.12.1 and 5.22.1 wheels; `lfm2` is there, `lfm3` is not). So `trust_remote_code=True` plus
the repo's own `modeling_lfm3.py` is mandatory for every toolkit — none of them "supports LFM3"
natively, the question is only whether they tolerate a model class they have never seen.

**2. The runnable floor is `transformers>=5.18.0`** — and it was measured at the model, not inferred
from imports. `modeling_lfm3.py` imports three late helpers (`create_recurrent_attention_mask` and
`force_accelerate_hooks` from 5.13.0, `use_kernel_func_from_hub_with_fallback` from 5.15.0), but
having the symbols is not enough: the code binds `lfm3`'s per-layer vocabulary (`conv`,
`sliding_attention`, `full_attention`) against internals that moved. Real checkpoint, SDPA, one
forward + backward per version:

| `transformers` | config | model binds | forward + backward |
|---|---|---|---|
| 5.6.0 / 5.12.1 | — | — | modeling module cannot import (symbols absent) |
| 5.15.0 | OK | `Lfm3ForCausalLM` | **`KeyError: 'linear_attention'`** |
| 5.16.0 | OK | `Lfm3ForCausalLM` | **`KeyError: 'linear_attention'`** |
| **5.17.0** | **`KeyError: 'conv'`** | — | — |
| 5.18.0 | OK | `Lfm3ForCausalLM` | **trains**, 13/13 conv `in_proj` grads, loss 5.7402 |
| 5.19.0 | OK | `Lfm3ForCausalLM` | **trains**, same |
| 5.20.1 | OK | `Lfm3ForCausalLM` | **trains**, same |
| 5.22.1 | OK | `Lfm3ForCausalLM` | trains (LoRA SFT run, `reference-path.json`) |

The 5.15/5.16 failures are the trap: config parses, weights load, and only the first forward
reveals the mismatch. 5.17.0 is worse — it fails a release earlier, at config load. So a toolkit
pinned anywhere in 5.15–5.17 is out, which is exactly where Unsloth's `<=5.17.0` cap sits, and
anything capping below 5.18 is out regardless of every other quality it has (that single fact
rejects LLaMA-Factory below, before its model list is consulted).

The vendor corroborates the window from the other direction: the cookbook's own
`finetuning/notebooks/lfm3_sft_with_trl.ipynb` pins `torch==2.14.1`, `transformers==5.20.2`,
`trl==1.16.0`, `peft==0.21.2` — inside the working band (5.20.1, its neighbour, was measured here;
5.20.2 was not).

## The conv layers are not where it breaks (measured)

The expected failure — "training kernels assume built-in attention, conv state breaks under
gradient" — does not happen, because the shipped code refuses its own kernels during training:
`lfm3_conv.can_use_lfm3_conv()` returns `False` whenever `torch.is_grad_enabled()`, so the Triton
width-7 path is inference-only and training runs `nn.Conv1d` / `F.conv1d`
(`modeling_lfm3.py:380,410,416,427`). Attention goes through
`ALL_ATTENTION_FUNCTIONS.get_interface(...)` with an eager fallback, so SDPA is enough and
`flash-attn` is never required to train.

Measured on the real `LFM3-1.7B-Base` checkpoint, SDPA, one forward/backward, vendor LoRA target
list (`q_proj k_proj v_proj o_proj in_proj out_proj w1 w2 w3`), r=16:

- 13 `nn.Conv1d` modules (one per `conv` layer), all frozen (`requires_grad False`, `grad None`);
- 52 LoRA tensors inside those conv blocks, 26 with a nonzero gradient at step 1 — the 26 zeros are
  the `lora_A` halves, which are zero by construction while `lora_B` is zero-initialised;
- 88 attention LoRA tensors, 44 nonzero, same pattern; 16,105,472 trainable of 1,744,907,008 total.
- The depthwise 7-wide `nn.Conv1d` kernels themselves cannot be LoRA'd at r=16: `peft` 0.21.2
  requires `rank % groups == 0` (64 groups here) and refuses (`ValueError: Targeting a Conv1d with
  groups=64 and rank 4`), and even at a matching rank it warns that merging is unsupported. Keep them
  frozen and adapt `in_proj`/`out_proj` around them, as the vendor notebook does.

What does break is **sequence packing**: conv state is per-layer and fixed-width, so a packed row
without a document-boundary signal trains through the previous document's conv state. LFM3's own
modeling code can do this correctly (it threads `seq_idx` and `create_recurrent_attention_mask`),
but each toolkit has to feed it boundaries; the ones that keep a hardcoded "recurrent model types"
list do not know `lfm3` and fail silently. That is Axolotl's exact hole, below.

## Entry gates

Record a toolkit only when all four pass, and record the failing one when it does not — a rejected
entry with its blocker is worth more than a missing entry, because it stops the sweep being re-run:

1. **Architecture** — loads the custom-code `lfm3*` class (`trust_remote_code=True` from
   `auto_map`) and trains *LoRA/QLoRA* without hand-patching attention. Measured against
   `transformers>=5.18.0`; 5.15–5.17 all fail, see the floor table.
2. **Hardware** — runs on GB10: aarch64 plus Blackwell (`sm_121`). The usual killers are
   `bitsandbytes` (4-bit/8-bit, needs an `sm_121` build), `flash-attn` wheels, and a toolkit
   pinning a `torch`/CUDA floor the node cannot meet. CPU-offload-only "support" is a rejection.
3. **Memory** — 1.7B/2.2B bf16 full fine-tune plus optimizer state fits one 128 GB unified node; if
   only QLoRA fits, say so with the measured resident figure.
4. **Artifact** — exports something the registry can serve: merged bf16 checkpoint, LoRA adapter
   with a `peft` config, or a GGUF conversion chain.

## Entry format

One `##` section per toolkit, same facts every time so two entries compare. `Gates:` is one line
carrying the four verdicts with the evidence grade in brackets — `[run]` receipt-backed,
`[wheel]` PyPI/index metadata, `[source]` code read at a named version, `[INFERENCE]` arithmetic.

```markdown
## <name> (<version or commit>)
- **License:** …
- **Verdict:** usable / usable patch / rejected
- **Load:** does it take `lfm3` (custom code) as-is, and which class binds
- **Hardware blocker:** the measured one, or "none on `.35` (aarch64, sm_121)"
- **Memory:** measured resident smallest working config
- **Export:** merged / adapter / GGUF, and the command that produced it
- **Receipt:** `~/benchmarks/liquidai-finetune-<date>/…`
- **Gates:** 1 … [grade] · 2 … [grade] · 3 … [grade] · 4 … [grade]
```

## transformers + peft + trl (transformers 5.22.1 / peft 0.21.2 / trl 1.17.1)
- **License:** Apache-2.0 (all three). Train weights under LFM Open License v1.0.
- **Verdict:** usable — the reference path, and the vendor's own recommendation.
- **Load:** yes, unmodified. `AutoConfig` → `Lfm3Config`, `AutoModelForCausalLM` →
  `Lfm3ForCausalLM`, 24 layers, tied embeddings, SDPA, 1,728,801,536 params. `SFTTrainer` trains,
  `save_pretrained` writes the adapter, `merge_and_unload` writes bf16. No attention patching.
- **Hardware blocker:** none known, **not node-verified**. Wheel floor checked 2026-11-03:
  `transformers`/`peft`/`trl`/`accelerate` are `py3-none-any`; `torch` has cp312 aarch64 `+cu130`
  wheels for 2.10.0–2.14.x on `download.pytorch.org/whl/cu130`; `triton` 3.9.0 ships cp312 abi3
  aarch64 (only needed for the inference kernels, not for training). QLoRA additionally needs
  `bitsandbytes` — see that row below.
- **Memory:** LoRA r=16 at bs1×96 tokens on CPU: 4.3 GB RSS process-wide, 0.59 GB after a mmap'd
  load. Full FT arithmetic — bf16 weights + bf16 grads + fp32 master + AdamW m/v = 16 B/param ⇒
  **27.7 GB** at 1.73B, **34.7 GB** at 2.17B, plus activations; fits 128 GB unified with room for a
  4k-token batch. `[INFERENCE]`, unmeasured on a node.
- **Export:** merged bf16 (written, reloadable — the merge dir carries `config.json`,
  `configuration_lfm3.py`, `modeling_lfm3.py`, `lfm3_conv.py` alongside `model.safetensors`) and a
  `peft` adapter. GGUF: llama.cpp master carries `conversion/lfm3.py`, `src/models/lfm3.cpp` and
  `LLM_ARCH_LFM3`, plus `convert_lora_to_gguf.py` (read 2026-11-03), so merged bf16 → GGUF is a
  first-party converter route; whether the fleet's pinned llama.cpp image ref has `conversion/lfm3.py`
  was not checked.
- **Receipt:** `~/benchmarks/liquidai-finetune-20261103/reference-path.json` (load, 2-step SFT,
  loss 4.603 → 4.096, adapter + merge), `grad-flow.json` (conv/attention LoRA gradients),
  `load-transformers-{5.15.0,5.16.0,5.18.0,5.19.0,5.20.1}.json` (the floor table),
  `adapter/`, `merged-bf16/`, `logs/`, and the wheel metadata in `pypi/`.
- **Gates:** 1 pass `[run]` · 2 no known blocker, wheels only `[wheel]` · 3 arithmetic `[INFERENCE]`
  · 4 adapter + merged bf16 `[run]`, GGUF route `[source]` on llama.cpp master.

## Liquid `liquid-finetune` (0.1.0, `d9cc23d`, 2026-10-07)
- **License:** MIT (code). Exported weights inherit LFM Open License v1.0.
- **Verdict:** **rejected as shipped** — it is an LFM2/LFM2.5 trainer and predates LFM3. Best
  re-check target in the survey: bumping its pin is the shortest path to a first-party LFM3 trainer.
- **Load:** no. `pyproject.toml` pins `transformers>=5.3.0,<5.4.0`, far below the runnable floor
  (5.18.0), and the text path calls
  `AutoConfig.from_pretrained(model_id)` / `AutoModelForCausalLM.from_pretrained(...)` **without**
  `trust_remote_code` (`checkpointing/model_loading.py`), so the `auto_map` class never resolves.
  Its knowledge is LFM2-shaped: `LFM_TIED_WORD_EMBEDDING_MODEL_TYPES = {"lfm2", "lfm2_moe"}`,
  chat-template overrides for `lfm2_5`. No branch carries an LFM3 pin (`main`,
  `feat/trl-modernization` both 5.3–5.4; `24b-support` is `transformers>=5.0.0`).
- **Hardware blocker:** none specific — its `flash-attn` extra is marked `x86_64` only and the
  loader falls back to SDPA, which is the right shape for GB10. `torch>=2.10,<2.12` has aarch64
  cu130 cp312 wheels (2.10.0/2.11.0 verified).
- **Memory:** not measured (never loaded LFM3).
- **Export:** the strongest in the survey by design — `liquid-export-gguf` CLI drives llama.cpp's
  own converter, plus `liquid-export-manual-sharded-checkpoint`, and QAT manifests.
- **Receipt:** `source/liquid-finetune.txt` (quoted lines from `pyproject.toml`,
  `checkpointing/model_loading.py`, `model_info.py` at `d9cc23d`), `cli/export_gguf.py` read; no run
  — gate 1 fails before a model load.
- **Gates:** 1 fail `[source]` (transformers pin below the floor, no `trust_remote_code` on the text
  path) · 2 not reached, no blocker seen `[wheel]` · 3 not reached `[INFERENCE]` · 4 pass by design
  `[source]`.

## Unsloth (2026.11.1 / unsloth-zoo 2026.11.1)
- **License:** Apache-2.0 (unsloth, unsloth-zoo).
- **Verdict:** **rejected for `lfm3`** — no LFM3 path exists, and its own `transformers` cap
  (`<=5.17.0`) sits entirely below the 5.18.0 floor, so there is no version at which it could work.
- **Load:** no. `unsloth/models/loader.py` dispatches on a hardcoded `model_type` chain
  (`llama`, `mistral`, `gemma`, `gemma2`, `qwen2`, `qwen3`, `qwen3_moe`, …) and `lfm3` falls to the
  generic `FastModel` branch; there is no `lfm2`/`lfm3` fast model anywhere in `unsloth/models/`,
  and the only `lfm3` string outside `unsloth/studio/` is an inference comment in
  `unsloth/models/vision.py` about custom-code `generate` cache fields. Unsloth-Zoo knows
  LFM2 well (MoE LoRA extractors, LFM2-VL projector patch, LFM2 conv naming in `packing.py`) — LFM3
  appears only as an MLX inference version table. Attempted for real on CPU with the 1.7B
  checkpoint: at `transformers==5.17.0` it dies in its config probe (`'conv'` — the 5.17.0
  regression, not Unsloth's fault); at 5.16.0 it gets past the config and stops at
  `AssertionError: Torch not compiled with CUDA enabled`, i.e. it needs a CUDA-build `torch` even
  with `UNSLOTH_ALLOW_CPU=1`.
- **Hardware blocker:** none for install — wheel is `py3-none-any`, `transformers<=5.17.0,>=4.52.4`,
  `torch<2.15.0`, `bitsandbytes>=0.45.5` (aarch64 wheel with `sm_121` kernels exists, below),
  `triton>=3.0.0` (aarch64 abi3 exists). The blockers are architectural: its `transformers` cap
  confines it to the 5.15–5.17 window, and **every version in that window fails at the first
  forward** of an `lfm3` checkpoint (`KeyError: 'linear_attention'` at 5.15.0/5.16.0, `KeyError:
  'conv'` at config load on 5.17.0) — measured, see the floor table above. On top of that its kernels
  have never been compiled for `sm_121`, and its value proposition is speed, so even a successful
  generic-path load would deliver none of it.
- **Memory:** not measured (never loaded LFM3 on CPU).
- **Export:** `save_pretrained` adapter / merged bf16 would apply if it loaded; `_EXPORT_LLM_MODEL_TYPES`
  covers `llama/qwen2/qwen3/qwen3_5/phi3/lfm2` — `lfm3` not in it (executorch export route).
- **Receipt:** `~/benchmarks/liquidai-finetune-20261103/unsloth-cpu.json`, `source/unsloth.txt`,
  `pypi/unsloth.json`. No GPU-free path exists to go further.
- **Gates:** 1 fail `[run]`+`[source]` · 2 installable on paper `[wheel]`, kernels unproven · 3 not
  reached `[INFERENCE]` · 4 partial `[source]`.

## Axolotl (0.21.1)
- **License:** Apache-2.0.
- **Verdict:** **usable patch** — structurally the most open of the non-reference toolkits, with one
  silent hazard to switch off. Not run (no node this session).
- **Load:** yes in principle, and the wiring was read end to end: `load_model_config` passes
  `trust_remote_code=cfg.trust_remote_code is True` to `AutoConfig`; `cfg.model_config_type` comes
  straight from `config.model_type`, with no whitelist, so `lfm3` is accepted; the model loader
  forwards `trust_remote_code` to `AutoModelForCausalLM`; `attn_implementation` defaults to `None`
  (SDPA), so no `flash-attn` dependency; LoRA targets are auto-derived from every linear name, which
  covers `in_proj`/`out_proj`/`w1`/`w2`/`w3`/`gate_proj` without a list. Its `lfm` knowledge stops at
  `lfm2`/`lfm2_moe`/`lfm2-vl` (causal-conv1d removal warning, `MULTIMODAL_AUTO_MODEL_MAPPING`,
  sparsemoe block name).
- **Hardware blocker:** none measured. `transformers==5.20.1` — **measured**: that exact version
  loads the checkpoint and backprops a full fine-tune (loss 5.7402, 13/13 conv `in_proj` grads) —
  `torch>=2.13,<2.15` (fleet 2.14.1 ✓, aarch64 cu130 cp312 wheel exists),
  `bitsandbytes==0.50.2` (aarch64 wheel, `sm_121` kernels), `python>=3.12` ✓ fleet 3.12.15.
  `torchao` is deliberately skipped on aarch64; `flash-attn-4[cu13]==4.0.0b35` only arrives via the
  `blackwell` extra, so the default install never touches FA.
- **Hazard to switch off:** `lfm3` is missing from `monkeypatch/models/recurrent_support.py`
  `RECURRENT_MODEL_TYPES` (which lists `lfm2`, `lfm2_moe`), and that guard's own docstring says the
  failure mode is silence — "Neither failure raises: the loss just quietly trains on cross-document
  state." Set `sample_packing: false` and `batch_flattening: false` for any `lfm3` config, or add
  `lfm3` to the patched set before trusting a packed run.
- **Memory:** not measured; same 16 B/param arithmetic as the reference entry.
- **Export:** `peft` adapter + Axolotl's merge CLI (`cli/merge_lora.py`, `trust_remote_code` aware).
- **Receipt:** `source/axolotl.txt` (quoted lines from `loaders/utils.py`, `loaders/model.py`,
  `loaders/adapter.py`, `utils/config/__init__.py`, `utils/schemas/config.py`,
  `monkeypatch/models/recurrent_support.py`) and `pypi/axolotl.json`, both from the 0.21.1 wheel;
  plus `load-transformers-5.20.1.json` for the pinned-version load/backward. No Axolotl process
  was run.
- **Gates:** 1 pass on source `[source]`, pin verified by a direct load `[run]` · 2 no known blocker
  `[wheel]` · 3 arithmetic `[INFERENCE]` · 4 adapter/merge `[source]`.

## LLaMA-Factory (0.9.5)
- **License:** Apache-2.0.
- **Verdict:** **rejected** — gate 1, on the `transformers` cap alone.
- **Load:** no. Requires `transformers>=4.55.0,<=5.6.0`, which is far below the measured runnable
  floor of 5.18.0 — `modeling_lfm3.py` cannot even import at 5.6.0 (missing
  `use_kernel_func_from_hub_with_fallback`, `create_recurrent_attention_mask`,
  `force_accelerate_hooks`). Its Liquid support is LFM2.5 only
  (`LFM2.5-1.2B`, `LFM2.5-1.2B-Instruct`, `LFM2.5-VL-1.6B` in `extras/constants.py`, templates
  `lfm2`/`lfm2_vl`); no `lfm3` string in the wheel, and `patcher.py`'s LFM branch is a
  `transformers<4.58` workaround for LFM2.5-VL.
- **Hardware blocker:** none — pure-Python wheel; the cap is the blocker.
- **Memory:** not reached.
- **Export:** export CLI exists (`llamafactory-cli export`) but is unreachable for `lfm3`.
- **Receipt:** `source/llamafactory.txt`, `pypi/llamafactory.json` (0.9.5 wheel). No run.
- **Gates:** 1 fail `[wheel]`+`[source]` · 2 n/a · 3 n/a · 4 unreachable.

## ms-swift (4.6.0)
- **License:** Apache-2.0.
- **Verdict:** **rejected as shipped** — gate 1. One-line registration is the port, but that is a
  patch to Swift's own registry, so it does not count as "loads it out of the box".
- **Load:** no. Model resolution goes `model_info.model_type` → `MODEL_MAPPING[model_type]` in
  `swift/model/model_meta.py`, so an unregistered `lfm3` raises `KeyError` rather than falling back
  to a generic loader; the wheel contains **zero** `lfm` strings across 538 modules, so there is no
  LFM2 entry to lean on either. `transformers<5.20.0,>=4.33` is wide enough (5.19 works), and
  `ModelLoader.default_trust_remote_code = True`, so the registration is genuinely all that is
  missing.
- **Hardware blocker:** none specific; `ms-swift` is `py3-none-any`.
- **Memory:** not reached.
- **Export:** has merge/export tooling for registered types only.
- **Receipt:** `source/ms_swift.txt`, `pypi/ms-swift.json` (4.6.0 wheel). No run.
- **Gates:** 1 fail `[source]` · 2 n/a · 3 n/a · 4 unreachable.

## torchtune (0.6.1)
- **License:** BSD-3-Clause.
- **Verdict:** **rejected** — gate 1, and this is the hardest reject in the list.
- **Load:** no, by design. torchtune builds models from its own in-tree `ModelBuilder` components;
  `torchtune/models/` contains no `trust_remote_code` and no `AutoModelForCausalLM` reference at
  all, so an `auto_map` custom-code `lfm3` class has no entry point. There is nothing to pin or
  patch — an `lfm3` port means reimplementing the architecture as tune components (13 conv layers,
  hybrid mask, partial-RoPE per layer type).
- **Hardware blocker:** none — the architecture gate comes first.
- **Memory:** not reached.
- **Export:** `torchtune.training` checkpoint conversion only, no `peft` adapter.
- **Receipt:** `source/torchtune.txt` (`torchtune/models/__init__.py`, whole `torchtune/models/`
  scanned for `trust_remote_code`/`AutoModelForCausalLM`), `pypi/torchtune.json`. No run.
- **Gates:** 1 fail `[source]` · 2 n/a · 3 n/a · 4 n/a.

## Hardware facts both usable entries rest on (read 2026-11-03)

- **`torch` aarch64 cu130:** cp312 wheels exist for 2.10.0 → 2.14.x on
  `download.pytorch.org/whl/cu130`; the fleet already runs `2.14.1+cu130` on aarch64.
- **`bitsandbytes` 0.50.2:** publishes `py3-none-manylinux_2_24_aarch64` (23.8 MB) shipping
  `libbitsandbytes_cuda130.so` (4.1 MB) whose fatbin carries `sm_100`, `sm_110`, `sm_120`, **`sm_121`**
  and `compute_121` — so QLoRA has a real `sm_121` build to load, unlike previous versions that
  capped at `sm_120`. Whether a 4-bit step *runs* on GB10 is unproven here (no node), but the usual
  "no `sm_121` build" blocker is gone.
- **`flash-attn` 2.8.3.post2** is sdist-only on PyPI (1 file, no wheel of any kind) — do not put it on
  the critical path. `flash-attn-4` 4.0.0b37 is `py3-none-any` and compiles for the device at import,
  which is why Axolotl ships it only behind the `blackwell` extra.
- **`triton` 3.9.0** has cp312 abi3 aarch64 wheels; `kernels` 0.18.1 has aarch64 (cp38-abi3) wheels
  for the `use_kernel_*_from_hub` path in LFM3's modeling code.

## License and redistribution

Weights are **LFM Open License v1.0** (`license: other`), not Apache/MIT — all seven rows.

The shipped serving ruling (`mad-science/QUESTIONS.md` `#56`, settled 2026-11-02) says these models
ship as ordinary arms with no eval-only banner. **That ruling is about serving a downloaded
checkpoint and does not cover republishing derived weights.** A *published* fine-tune — merged
checkpoint, adapter, or GGUF on a Hub repo — is a redistribution under Liquid's own terms and needs
its own read before it leaves a node, per the "new license class goes to the register first" rule.
Nothing in this directory grants that; a trained adapter on a node is node-local evidence, not a
shippable artifact.

## Rules

- **No toolkit is recorded from its README.** Every entry above points at a wheel, a source file at
  a named version, or a run — and says which gates that evidence covers and which are inferred.
- A rejected entry is kept with its failing gate, so the sweep is not re-run.
- Re-check order, if this ever gets a node window: `transformers+peft+trl` (confirm gate 2/3 with a
  real bf16 full FT on `.35`), then Axolotl with `sample_packing: false`, then
  `liquid-finetune` once the vendor bumps its `transformers` pin past 5.18.
- A converted GGUF or merged checkpoint is node-local evidence, never something committed here.
- `tools/` + `tests/` stay stdlib-only; nothing in this survey needs a repo-side dependency.

## Candidate status at a glance

| candidate | gate 1 load | gate 2 GB10 | gate 3 memory | gate 4 export | verdict |
|---|---|---|---|---|---|
| `transformers`+`peft`+`trl` | pass `[run]` | chk `[wheel]` | `[INFERENCE]` | pass `[run]` | **usable** |
| Axolotl 0.21.1 | pass `[source]`+`[run]` pin | chk `[wheel]` | `[INFERENCE]` | `[source]` | usable patch (packing off) |
| Liquid `liquid-finetune` | fail `[source]` | n/a | n/a | pass `[source]` | rejected (pin) |
| Unsloth 2026.11.1 | fail `[run]` | n/a | n/a | n/a | rejected (no lfm3) |
| LLaMA-Factory 0.9.5 | fail `[wheel]` | n/a | n/a | n/a | rejected (cap) |
| ms-swift 4.6.0 | fail `[source]` | n/a | n/a | n/a | rejected (registry) |
| torchtune 0.6.1 | fail `[source]` | n/a | n/a | n/a | rejected (no HF classes) |

`chk` = no blocker found in wheel/source evidence, not node-verified. The one measured training run
in this directory is CPU-only on an x86 host — it settles the architecture gates and nothing about
GB10 throughput.