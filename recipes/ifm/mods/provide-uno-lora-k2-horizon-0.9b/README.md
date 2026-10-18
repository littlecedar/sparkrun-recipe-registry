# provide-uno-lora-k2-horizon-0.9b

Fetch and verify the `IFM/K2-Horizon-0.9B-Uno` conditional-LoRA adapter at a fixed
in-container path, so a recipe can pass it to `--uno-lora-path`.

The 0.9B sibling of [`../provide-uno-lora-k2-horizon-7b`](../provide-uno-lora-k2-horizon-7b/README.md);
same mechanism, same harness (`mods/mod-template/run.sh`), different artifact.

## Pinned artifact

| | |
|---|---|
| repo | `IFM/K2-Horizon-0.9B-Uno` |
| revision | `cbb5d835689a1e809e06ce1a3efff35bab0c86eb` |
| `adapter_model.safetensors` | `223,917,616` B |
| sha256 | `5a499229d19ef4a69eb0b21884819d1b67cd983ba02b7ee2031ba8567dedfe4e` |
| `adapter_config.json` | `r=128`, `lora_alpha=2048` (scaling 16), 7 target modules |
| in-container path | `/cache/runtime/uno-lora/K2-Horizon-0.9B-Uno` |

Both pins were derived from the HF API on 2026-10-18 (`?blobs=true`), and
`adapter_sha256` in the repo's own `conversion_summary.json` reports the same hash
(`392` adapter tensors, `lossless_exact_tensor_compare: true`). Re-derive with:

```sh
curl -s 'https://huggingface.co/api/models/IFM/K2-Horizon-0.9B-Uno?blobs=true'
```

Update `UNO_LORA_REVISION`, `UNO_LORA_SIZE` **and** `UNO_LORA_SHA256` together.

## Which base revision this adapter pairs with

`adapter_config.json` names `base_model_name_or_path: IFM/K2-Horizon-0.9B` and
`"revision": null`, i.e. **no base commit**; the card's prose ("the base used for
training") names none either. The pairing is decidable from the adapter's own
`conversion_summary.json`, which pins
`base_weight_sha256: 6392cc67c8dcc7aef1575f94ecdf3c7113b7d0e8f4e7058c4c3c74d4d876c365`
and asserts `base_weight_matches_public_repository: true`. The base repo's single
weight shard carries that exact LFS sha256 at **`9fa6faa5` (rl_stem), `76db896c`
and `383cb663`** — every commit after `9fa6faa5` touches only chat templates — so
the recipe's `383cb663` pin serves the weights the adapter was trained against.
An earlier note that "the adapter pairs with `9fa6faa5`" is describing the
revision that was `main` when the adapter was published, not a different weight
set; there is no older-base pairing to honour.

## Behaviour

- **Idempotent.** An existing file is checked by size, then sha256, and kept.
- **Fails closed.** A failed fetch, a missing `adapter_config.json`, or a failed
  post-download verification each `exit 1`.
- **Records what it loaded.** Prints `base=… r=… lora_alpha=… scaling=… targets=…`
  from `adapter_config.json` into the mod log.
- **Ownership handed back.** Every path created is passed to `reown`, and the log
  directory is rotated and re-owned like the rest of the harness.

## Ordering

Mounted **before** `probe-uno-fa4-sm121` in `k2-horizon-0.9b-bf16-uno-sglang`:
the `mods:` list is an ordered dependency chain, and the adapter must exist on disk
before sglang validates `--uno-lora-path`.
