# InstantTensor hybrid speculative-draft loader

Vendored from `eugr/spark-vllm-docker`
(`mods/instanttensor-hybrid-draft-loader/`, Apache-2.0). Upstream README below,
retrieved 2026-09-25. `patch_model_loader.py` in this directory is the upstream
file VERBATIM except for its SPDX header; its md5 is in `MD5SUMS.txt` and
`../run.sh` verifies it. `../run.sh` is rewritten in this repo's mod style
(fail-closed, md5-verified, backed up once, idempotent).

---

# InstantTensor hybrid speculative-draft loader

This opt-in mod keeps InstantTensor for the primary model while allowing a
speculative draft model to use lazy safetensors. It avoids a second
InstantTensor GPU-streaming pass over a large checkpoint when an embedded MTP
or other same-checkpoint draft needs only a small subset of its tensors.

The mod patches vLLM's central `get_model()` entry point. It identifies a real
speculative draft by comparing the `ModelConfig` object with
`speculative_config.draft_model_config`; target and unrelated model loads are
left unchanged.

## Modes

Set `INSTANTTENSOR_DRAFT_LOADER` on the containers:

- `auto` (default): use lazy safetensors only when the draft and target have
 the same model path and revision.
- `safetensors`: use lazy safetensors for every speculative draft whose
 effective loader would otherwise be InstantTensor.
- `instanttensor`: preserve InstantTensor for drafts. This disables the hybrid
 behavior without removing the mod.

If the primary/effective loader is not InstantTensor, the mod does nothing.
An explicitly configured non-InstantTensor draft loader is also preserved.

## Usage

The default `auto` mode is appropriate for embedded MTP weights:

```bash
./launch-cluster.sh \
 --apply-mod mods/instanttensor-hybrid-draft-loader \
 exec \
 vllm serve /model \
 --load-format instanttensor \
 --speculative-config '{"method":"mtp","num_speculative_tokens":1}' \
 ...
```

To force lazy safetensors for a standalone speculative draft too:

```bash
./launch-cluster.sh \
 --apply-mod mods/instanttensor-hybrid-draft-loader \
 -e INSTANTTENSOR_DRAFT_LOADER=safetensors \
 exec \
 vllm serve ...
```

At runtime, a switched draft logs:

```text
Hybrid draft loading: using lazy safetensors for speculative draft weights
while preserving InstantTensor for the target model
```

## Scope and limitations

This is a vLLM integration workaround, not a selective-loading implementation
inside InstantTensor. Lazy safetensors still scans checkpoint metadata, but
weights rejected by the draft model remain CPU memory-mapped views instead of
being staged and cloned on the GPU.

Remove the mod once vLLM exposes a supported per-draft load-format option or
InstantTensor and vLLM can plan and selectively stream only requested tensor
names.

---

## Local notes (Little Cedar)

- **Verified portable to `littlecedar/dgx-spark-dsv41:exl3a` on 2026-09-25.**
  The image's `vllm/model_executor/model_loader/__init__.py` `get_model()`
  matches the vendored anchor byte-for-byte, so the patcher's `--check` reports
  `compatible`, applies, and then reports `already patched` (idempotent).
  Reproduced against the real image file, not a copy of the repo.
- **It is a no-op on the DS4.1 EXL3 recipes as shipped.** The DSpark drafter is
  a separate model path/revision, so `auto` mode does not flip and the boot is
  identical to InstantTensor alone. Listed for parity so a future
  same-checkpoint draft benefits without a recipe change.
- **`INSTANTTENSOR_DRAFT_LOADER` must be sprayed into the serve process** via
  the recipe `env:` block; the patched vLLM reads it at runtime, not build time.
