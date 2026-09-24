# mount-dsv41-exl3-patches

Installs **tonyd2wild's DeepSeek-V4.1-Flash vLLM patch set** into the container,
in place, before `vllm serve` runs. Run it on every rank (sparkrun applies mods
per node).

| | |
|:--|:--|
| Source | [tonyd2wild/DeepSeek-V4.1-Flash-vLLM-DGX-Spark](https://github.com/tonyd2wild/DeepSeek-V4.1-Flash-vLLM-DGX-Spark) `patch/exl3-tp3/` @ `d45538f67366c62da668c35ec1afd4fcd0e4c8b4` |
| License | Repo MIT; the vendored `vllm/`-derived files are `SPDX: Apache-2.0` (vLLM upstream). See `files/` headers. |
| Verified against | image `littlecedar/dgx-spark-dsv41:exl3a` (probe 2026-09-23: vLLM `0.28.1rc1.dev388+g8a728663c`, `cuda_exl3` 1.0.x) |

## Why it exists

The image ships the `deepseek_v4_1` model tree and the `cuda-exl3` plugin, but
**not** the Engram-on-disk reader. Its
`models/deepseek_v4_1/common/engram.py` (md5 `27f27c33328a023b2df7d62210ae97b3`)
has none of `DSV41_ENGRAM_DISK`, `preadv`, `O_DIRECT`. Without the replacement the
two 203 GB Engram tables cannot leave unified RAM, and a 4× Spark TP=4 boot
exhausts node memory ~25 minutes in during the checkpoint read — the failure mode
§6.5 of the DS4 work doc calls out.

The patch set is **whole-file replacement**, not diffs: 13 targets, mapped in
`files/mounts.txt`. Twelve replace existing files; one
(`models/deepseek_v4_1/virtual_heads.py`) is new and is only exercised at TP=3.

## Mechanics (fail-closed)

1. Every vendored file is **md5-verified** against `files/MD5SUMS.txt` before
   anything is installed. One mismatch aborts the whole mod.
2. The installed `vllm` package dir is resolved at runtime
   (`python3 -c 'import vllm'`), never hardcoded.
3. Each replaced file is backed up once to `<target>.sparkrun-orig`; the backup's
   existence is the idempotence key, so re-runs are cheap and a debug can diff
   what changed.
4. Targets that do not exist in the image must be listed in `NEW_TARGETS`
   (currently just `virtual_heads.py`); anything else is an error.
5. After install, the mod asserts `DSV41_ENGRAM_DISK` is present in the installed
   `engram.py`. If not, it dies — better a failed launch than a slow OOM.

## Knobs

None. `MOD_TIMEOUT`, `MOD_CACHEDIR`, `MOD_LOGDIR` come from the shared harness.

## Caveat

This vendors third-party code we have not executed. The checksums prove the
files are the ones we fetched; they do not prove the patch set is correct for
our image. `virtual_heads.py` needs a TP=3 model copy whose `config.json`
declares 72 heads / 9 groups — a plain 64-head checkpoint at `--tp 3` will load
the patch and then fail in attention.
