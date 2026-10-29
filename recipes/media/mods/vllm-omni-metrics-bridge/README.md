# vllm-omni-metrics-bridge

Metrics-bridge wrapper for the media lane's Qwen-Image-2.1-Turbo vLLM-Omni arm
([`recipes/media/qwen-image-2.1-turbo-7b-bf16-vllm-omni.yaml`](../../qwen-image-2.1-turbo-7b-bf16-vllm-omni.yaml)).

## Contents

- [Why this exists](#why-this-exists)
- [What it does and does not report](#what-it-does-and-does-not-report)
- [Gates and failure modes](#gates-and-failure-modes)
- [Why a copy, not a shared module](#why-a-copy-not-a-shared-module)

## Why this exists

The sparkrun monitor reads a serve's **log**, not an endpoint: `sparkrun/cli/_monitor_metrics.py`
matches four shapes — `Avg generation throughput: N tokens/s`, `Avg prompt throughput: N tokens/s`,
`Running: N reqs`, `Waiting: N reqs` — plus the SGLang variants. An SGLang or vLLM *LLM* serve prints
them itself; a vLLM-Omni **diffusion** serve prints none of them, so this arm's monitor cells stayed
blank even though its `/metrics` endpoint answers (the 2026-10-22 receipt captured
`vllm_omni:peak_memory_mb{stage="0"}` from it).

`launcher.py` is a transparent wrapper: it runs the recipe's own `vllm-omni` command verbatim as a
child process, then republishes `/metrics` in the scraper's shapes. The recipe's `command:` names it —

```
python3 /workspace/mods/vllm-omni-metrics-bridge/launcher.py serve {model} --omni …
```

— because sparkrun mounts a mod's own directory at `/workspace/mods/<name>`; that mount is all this
mod ships. It patches no image file and installs nothing.

## What it does and does not report

| series suffix (any prefix) | cell it fills |
|---|---|
| `:num_requests_running` | `Running: N reqs` |
| `:num_requests_waiting` | `Waiting: N reqs` |
| `:generation_tokens_total` | `Avg generation throughput: N tokens/s` (+ the SGLang spelling), from two samples |
| `:prompt_tokens_total` | parsed, not printed: a diffusion arm reports no prefill rate |

**The namespace is not hardcoded.** This arm publishes `vllm_omni:` families while the vLLM engine
underneath publishes `vllm:` ones, and which of these series a diffusion serve actually carries was
never observed before this wrapper shipped — so the parser matches the vLLM-family *suffix* and
prints **nothing** for a series the body does not carry. Invented zeros would corrupt accounting; a
blank cell reads as "not reported", which is the truth. A diffusion arm normally has no token
counter at all, so its contribution is the two request gauges (concurrency) and nothing else.

The first `/metrics` body of a boot logs the evidence, once:

```
[vllm-omni-metrics-bridge] metrics bridge: matched ['running', 'waiting'] families [...]
```

with the matched canonical names, or — when nothing matched — every family the body does carry. That
line is what fixes this image's naming for good: the next boot either confirms the suffixes or names
the series to add, no guessing.

## Gates and failure modes

Fail-open by construction — the bridge never touches the serve:

- `OMNI_METRICS_BRIDGE=0` disables it without a repo edit (`-o env.OMNI_METRICS_BRIDGE=0`).
- `OMNI_METRICS_BRIDGE_DEADLINE_S` (default `3600`) bounds the pre-ready wait; the omni HTTP listener
  binds only after the stage load (TTR 251 s cold on this arm), so connection refusals are the
  expected state for most of the boot. After first contact, three consecutive failures end the thread.
- The wrapper forwards `--port` (or `--port=N`) to the bridge and defaults to 8000; a port it cannot
  read only means it never contacts anything.
- SIGTERM/SIGINT are relayed to the child and the wrapper exits with the engine's code, so
  `sparkrun stop` semantics are unchanged.
- Fail-closed where a launch would otherwise be wrong: an empty argv returns 2 instead of starting
  `vllm-omni` with no subcommand.

`run.sh` gates the launch on `vllm-omni` being on PATH, `python3` existing, and `launcher.py` parsing
— the two ways this `command:` line can be a dead boot.

## Why a copy, not a shared module

There is no shared library across mods: sparkrun ships only the mod's own directory, so a
`mods/common.sh` or a sibling import would not exist at launch. The three bridge implementations in
this registry (`tensorfold-glm53-3bpw-launcher`, `tensorfold-glm-exl3-launcher`, and this one) are
bundled copies by design — `tests/test_tensorfold_glm_metrics_bridge.py` pins the two GLM copies
byte-identical, and `tests/test_qwen_image_omni_metrics_bridge.py` pins this one, so a fix lands in both.