# Cybersec lane — `recipes/cybersec/`

_Brought to you by Little Cedar Group._

Red-team / security-research arms: **abliterated (refusal-removed) and cybersecurity-unlocked**
checkpoints served on DGX Spark (GB10). This is a *capability* lane, not a defence one — every
arm here will answer prompts its base model refuses, and the operator supplies the guardrails.

> Working here? Read [`AGENTS.md`](AGENTS.md) first — it is the lane's durable guide (gating,
> token prerequisite, traps, receipts). This README is the human-facing summary.

## Gating: read this before filing an issue

**All five arms are gated on the Hub (`gated: auto`).** A distributed registry cannot assume an
`HF_TOKEN`, so the prerequisite is explicit here and in every recipe's `metadata.caveats`:

- each runner node needs an `HF_TOKEN` whose user has **accepted that repo's release**, and
- two arms (2 and 5) pull *two* gated repos each (the body/stock pack and the overlay).

Without the token the model acquisition fails at launch, with the exact repo id named. No weights
are redistributed by this registry; recipes ship repo ids, revisions, and wiring only.

**Use.** These checkpoints are released for interpretability / refusal-mechanism study,
red-teaming, and robustness evaluation. They will produce harmful or illegal content on request.
Do not deploy them to end users, and do not point them at anything you do not own.

## The arms

| # | recipe | runtime | model | TP | C1 t/s (d0 / d8192) | battery | status |
|---|---|---|---|---|---|---|---|
| 1 | `qwen3.8-27b-uncensored-nvfp4-sglang` | sglang | [orcarouter/Qwen3.8-27B-Uncensored-NVFP4] (mixed NVFP4+FP8, `qwen3_5`, vision) | 1 | **10.2 / 9.7** | 37/37 | boots, `GET /v1/models` = repo id |
| 2 | `qwen3.8-27b-ablit-cyber-unlock-nvfp4-dflash2-sglang` | sglang | [sakamakismile/Qwen3.8-27B-AEON-ULTIMATE-UNCENSORED-NVFP4] **+ the [drowzeys keys overlay]** (chat template) + [incoai/Qwen3.8-27B-DFlash2] draft | 1 | **33.3 / 26.2** | 37/37 | boots, `GET /v1/models` = repo id; uncensored template confirmed in the serve log |
| 3 | `nex-n2.5-mini-uncensored-nvfp4-sglang` | sglang | [orcarouter/Nex-N2.5-mini-Uncensored-NVFP4] (`qwen3_5_moe`, 256E top-8, vision) | 1 | — | — | **negative** under SGLang (NaN sample-time logits → CUDA device-side assert); the vLLM route its card documents is blocked on image distribution — see AGENTS.md |
| 4 | `qwen3.8-flash-next-uncensored-nvfp4-sglang` | sglang | [orcarouter/Qwen3.8-Flash-Next-Uncensored-NVFP4] (`qwen4_exp`, NVFP4 experts / FP8 attention) | 2 | — | — | **negative** — SGLang's compressed-tensors loader refuses the export's scheme (`CompressedTensorsW4A16Sparse24` unsupported); the card's vLLM route is the next step — see AGENTS.md |
| 5 | `deepseek-v4.1-flash-abliterated-cyber-tp2-tensorfold-sglang` | sglang shim → TensorFold | stock [Mia-AiLab/DeepSeek-V4.1-Flash-EXL3-2.9bpw] **+ the [drowzeys wo_b sidecar]** | 2 | **63.7 / 67.7** | 36/37 | boots, `GET /v1/models` = the overlay repo id (1M ctx); graft measured at 269 s / 284 s per node, inside the 600 s hook budget; refusal probe 0/8 explicit refusals (1/8 completed; 7/8 truncated-empty at the cap) — see AGENTS.md |

`[bracketed]` links resolve at the bottom of this file. Every arm is one recipe; the measured
receipts (boot id, `GET /v1/models` answer, `decode-triage` run, house battery) live in
[`AGENTS.md`](AGENTS.md) so this table stays readable.

## Two of the five arms are overlays

Arms 2 and 5 are *not* checkpoints. The upstream repos ship **no weights** — they are a chat
template / a config / a small `attn.wo_b` sidecar plus wiring. Both are handled by a mod that
builds the arm's real artifact inside the container, from the container's own HF cache, and never
writes the source snapshot:

| arm | overlay repo | body / stock | what the arm adds | mod |
|---|---|---|---|---|
| 2 | [drowzeys keys-Qwen3.8-27B…Single-DGXSpark] | `sakamakismile/…-AEON-ULTIMATE-UNCENSORED-NVFP4` | the cybersecurity-unlock **chat template** (+ the YaRN rope overlays for the 1M route) | `mods/provide-uncensored-chat-template` |
| 5 | [drowzeys DeepSeek-V4.1-Flash-Abliterated…Unleashed] | `Mia-AiLab/DeepSeek-V4.1-Flash-EXL3-2.9bpw` | the `layers.10-35 attn.wo_b` **EXL3 mul1 K=5 sidecar**, grafted | `mods/graft-dsv41-ablit-wo-b` |

For arm 5 the author's `INSTALL.md` pairs a stock pack with a sidecar and forbids mixing them —
the Mia 2.9bpw pack takes the **EXL3** sidecar and the EXL3 graft script; native / Pollard / TR3
take the FP8 pair. The lane ships the EXL3 pair because the Mia pack is what our 2-node EXL3
engine serves.

## Served model id — the convention

Every arm renders `--served-model-name {served_model_name}`, never `{model}`. On a real launch
sparkrun rebinds `{model}` to the prepared on-disk snapshot, so a `{model}`-derived id would make
the server advertise a `/cache/huggingface/hub/models--…` path to every client, the proxy, and any
benchmark that sends the id. `served_model_name` is the arm's repo id:

| arm | served id |
|---|---|
| 1 | `orcarouter/Qwen3.8-27B-Uncensored-NVFP4` |
| 2 | `sakamakismile/Qwen3.8-27B-AEON-ULTIMATE-UNCENSORED-NVFP4` |
| 3 | `orcarouter/Nex-N2.5-mini-Uncensored-NVFP4` |
| 4 | `orcarouter/Qwen3.8-Flash-Next-Uncensored-NVFP4` |
| 5 | `drowzeys/DeepSeek-V4.1-Flash-Abliterated-Cybersecurity-Unleashed` |

For the two overlay arms the served id is the **arm's identity** (what the registry ships and
what a client should ask for), not the body pack: arm 2 serves the AEON body through the cyber
template, and arm 5 serves a graft tree that exists only on the node.

## Reproduce

```bash
# from the run-from dir on the head node, recipes symlinked by basename
sparkrun run qwen3.8-27b-uncensored-nvfp4-sglang -H <node>
curl -s http://<node>:8000/v1/models        # id == the arm's repo id

sparkrun benchmark performance qwen3.8-27b-uncensored-nvfp4-sglang -H <node> \
  --profile benchmarking/decode-triage.yaml --output runs/<arm>.yaml
python3 tools/quality-battery.py http://<node>:8000/v1 --tier both --json runs/<arm>.battery.json
```

Arm 5's graft (a large on-node rewrite of the stock EXL3 shards) runs **synchronously and
fail-closed** in the mod — the serve command does not wait on a background step; see [`AGENTS.md`](AGENTS.md) §6.

## Other surfaced arms (not shipped)

Recorded, over the 1–2-node bar or licence-blocked; see `mad-science/TODO.md` §cybersec:
`orcarouter/GLM-5.3-Flash-Uncensored-NVFP4` (205.1 GB), `drowzeys/keys-MiMo-V2.6-Pro-RL-Jarrelscy-ARVQ-Abliterated`
(315.7 GB ⇒ ≥3 nodes), `drowzeys/MiMo-V2.6-Flash-RL-Abliterated` (310B), `orcarouter/DeepSeek-V4-Flash-Vision-Uncensored` (304B).

<!-- Links -->
[orcarouter/Qwen3.8-27B-Uncensored-NVFP4]: https://huggingface.co/orcarouter/Qwen3.8-27B-Uncensored-NVFP4
[sakamakismile/Qwen3.8-27B-AEON-ULTIMATE-UNCENSORED-NVFP4]: https://huggingface.co/sakamakismile/Qwen3.8-27B-AEON-ULTIMATE-UNCENSORED-NVFP4
[incoai/Qwen3.8-27B-DFlash2]: https://huggingface.co/incoai/Qwen3.8-27B-DFlash2
[drowzeys keys-Qwen3.8-27B…Single-DGXSpark]: https://huggingface.co/drowzeys/keys-Qwen3.8-27B-NVFP4-DFlash2-Ablit-Cybersecurity-Unlock-1M-Context-YARN-Single-DGXSpark
[orcarouter/Nex-N2.5-mini-Uncensored-NVFP4]: https://huggingface.co/orcarouter/Nex-N2.5-mini-Uncensored-NVFP4
[orcarouter/Qwen3.8-Flash-Next-Uncensored-NVFP4]: https://huggingface.co/orcarouter/Qwen3.8-Flash-Next-Uncensored-NVFP4
[Mia-AiLab/DeepSeek-V4.1-Flash-EXL3-2.9bpw]: https://huggingface.co/Mia-AiLab/DeepSeek-V4.1-Flash-EXL3-2.9bpw
[drowzeys DeepSeek-V4.1-Flash-Abliterated…Unleashed]: https://huggingface.co/drowzeys/DeepSeek-V4.1-Flash-Abliterated-Cybersecurity-Unleashed
