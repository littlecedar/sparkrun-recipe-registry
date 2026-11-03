# Fine-tuning LFM3

Toolkit survey for training `lfm3` / `lfm3_vl` / `lfm3_audio` / `lfm3_omni` checkpoints on this
fleet. **Nothing here is verified yet** — the survey row `liquidai-finetune-toolkits` fills this
directory, and an entry appears only after its gates were actually run.

## Why this is not a generic LoRA question

An `lfm3` checkpoint is a `transformers` **custom-code** architecture: `auto_map` points at
`configuration_lfm3.py` / `modeling_lfm3.py` in the repo, and the stack is hybrid — 13 `conv`
layers (7-slot cache), 6 `full_attention` layers, 5 `sliding_attention` layers (window 256). A
training toolkit that assumes `transformers`' built-in attention classes has to be taught this
model, and one that pads sequences for bucketing flatly breaks the conv state. Expect the failures
to be at load and at gradient-checkpointing boundaries, not at the loss curve.

## Entry gates

Record a toolkit only when all four pass, and record the failing one when it does not — a rejected
entry with its blocker is worth more than a missing entry, because it stops the sweep being re-run:

1. **Architecture** — loads the custom-code `lfm3*` class (or a port of it) and trains *LoRA/QLoRA*
   without patching attention by hand. `trust_remote_code=True` acceptance is the first tell.
2. **Hardware** — runs on GB10: aarch64 plus Blackwell (`sm_121`). The usual killers are
   `bitsandbytes` (4-bit/8-bit optimizers, no `sm_121` build), `flash-attn` wheels, and any toolkit
   pinning a `torch`/CUDA floor the node cannot meet. CPU-offload-only "support" is a rejection.
3. **Memory** — a 1.7B/2.2B bf16 full fine-tune plus optimizer state fits one 128 GB unified node;
   if only QLoRA fits, say so with the measured resident figure.
4. **Artifact** — exports something servable by this registry: a merged bf16 checkpoint, a LoRA
   adapter with its `peft` config, or a GGUF conversion chain. An adapter nothing can load is not a
   deliverable.

## Entry format

One `##` section per toolkit, in this shape — the same facts every time, so two entries compare:

```markdown
## <name> (<version or commit>)
- **License:** …
- **Verdict:** usable / usable with patch / rejected
- **Load:** does it take `lfm3` (custom code) as-is, and which class it binds
- **Hardware blocker:** the measured one, or "none on `.35` (aarch64, sm_121)"
- **Memory:** measured resident for the smallest working config
- **Export:** merged / adapter / GGUF, with the command that produced it
- **Receipt:** `~/benchmarks/liquidai-finetune-<date>/…`
```

## Candidates to check first (unverified — the survey confirms or rejects each)

- **Liquid's own tooling** — the vendor's `leap` quantization metadata ships inside the GGUF mirrors
  (`leap/Q4_K_M.json` …), which implies a first-party pipeline behind it; the vendor's cookbook and
  `liquid-llm`-family repos are the first place an `lfm3` recipe will exist at all.
- **`transformers` + `peft` + `trl`** — the reference path: the repo already ships the modeling code,
  so plain `Trainer`/`SFTTrainer` with a LoRA config is the baseline every other toolkit is measured
  against.
- **Unsloth**, **Axolotl**, **LLaMA-Factory**, **ms-swift**, **torchtune** — each has to clear gate 1
  and gate 2 above; Unsloth and Axolotl historically ship their own kernels, which is exactly where
  `sm_121` bites.

## Rules

- **No toolkit is recorded from its README.** A row without a receipt path is not an entry.
- The vendor's license is **LFM Open License v1.0** (not Apache/MIT): a *published* fine-tune is a
  redistribution, which is `mad-science/QUESTIONS.md` `#56`, not a local decision. Training for
  internal evaluation is not gated.
- Keep the registry tidy at the edge: a converted GGUF or merged checkpoint is node-local evidence,
  never something committed here.