# provide-uno-lora-k2-horizon-7b

Fetch and verify the `IFM/K2-Horizon-7B-Uno` conditional-LoRA adapter at a fixed
in-container path, so a recipe can pass it to `--uno-lora-path`.

## Why a mod is needed at all

A recipe distributes exactly **one** artifact: its `model:` field. SGLang's native
UNO speculative algorithm needs a **second** one — the draft LoRA — and there is
no recipe field for it. So it is placed here.

## Why not the HF cache

The container runs with `HF_HOME=/cache/huggingface`,
`HF_HUB_CACHE=/cache/huggingface/hub`, `HF_HUB_OFFLINE=1`. Writing into the HF
cache looks tidier but is the wrong place: sparkrun owns that tree's layout and
its `snapshots/` + `refs/` bookkeeping, and a hand-written snapshot directory can
be pruned or can confuse the sync. This mod writes under `/cache/runtime`, which
is persistent across launches, ours to own, and invisible to the sync.

The `HF_HUB_OFFLINE=1` that the runtime sets for the **served model** is
intentionally un-set inside this mod's single `python3` process and nowhere else,
so the fetch cannot leak into the server or make main model resolution online.

## Pinned artifact

| | |
|---|---|
| repo | `IFM/K2-Horizon-7B-Uno` |
| revision | `669f041aab04fad836e757ede9a028058b064996` |
| `adapter_model.safetensors` | `1,396,763,616` B |
| sha256 | `cfef2bbff2802f2fb77d25d279af49b11746fc0a4de06f306f745c7bbe4e00ad` |
| in-container path | `/cache/runtime/uno-lora/K2-Horizon-7B-Uno` |

Both pins were re-derived from the HF API on 2026-09-20, and the file's own
safetensors header was parsed by ranged read to confirm the contents: **504
tensors, all F32**, `8 + 60,376 (header) + 1,396,703,232 (data) = 1,396,763,616`
exactly. Layout is `model.layers.<N>.<module>.lora_{A,B}.weight` over the seven
target modules with `r=128`.

Re-derive if the pin moves:

```sh
curl -s 'https://huggingface.co/api/models/IFM/K2-Horizon-7B-Uno?blobs=true'
```

Update `UNO_LORA_REVISION`, `UNO_LORA_SIZE` **and** `UNO_LORA_SHA256` together.
Do not relax verification to size-only — the point of the check is knowing which
weights a measured result came from.

## Behaviour

- **Idempotent.** An existing file is checked by size, then sha256, and kept.
  A truncated copy from an interrupted download fails the size check and is
  re-fetched.
- **Fails closed.** Missing fetch, missing `adapter_config.json`, or a failed
  post-download verification each `exit 1`. The recipe cannot boot into a
  half-provisioned adapter.
- **Records what it loaded.** Prints `base=... r=... alpha=... targets=...` from
  `adapter_config.json` into the mod log, so a launch log shows which adapter a
  result came from without re-fetching.
- **Ownership handed back.** Every path created is passed to `reown`; mods run as
  root and root-owned leftovers under `/cache/runtime` break downstream user
  processes.

## Why `adapter_config.json` is mandatory

SGLang reads `r`, `lora_alpha`, and `target_modules` from it. A directory holding
only the weights is not a usable adapter, so its absence is fatal rather than a
warning.

Note `lora_alpha: 8192` at `r: 128` (scaling 64) looks like a typo and is not
one — it is the conditional-LoRA formulation from arxiv:2609.04010.

## Knobs

| Var | Default |
|---|---|
| `UNO_LORA_REPO` | `IFM/K2-Horizon-7B-Uno` |
| `UNO_LORA_REVISION` | `669f041aab04fad836e757ede9a028058b064996` |
| `UNO_LORA_DIR` | `/cache/runtime/uno-lora/K2-Horizon-7B-Uno` |
| `UNO_LORA_SIZE` | `1396763616` |
| `UNO_LORA_SHA256` | `cfef2bbf…e00ad` |
| `MOD_TIMEOUT` | `900` |

## Ordering

Mounted **before** `probe-uno-fa4-sm121` in the recipe's `mods:` list. The `mods:`
list is an ordered dependency chain, not a set: the adapter must exist on disk
before sglang reads `--uno-lora-path`.

## Provenance

Written from source reading of SGLang `v0.5.20` plus the HF API, **not** from a
hardware trial. Derivation in
`recipes/ifm/K2-7B-MODEL-OPTIMIZATION-WORK.md` §2.4 and §6.
