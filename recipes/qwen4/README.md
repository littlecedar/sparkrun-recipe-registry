# Qwen3.8-Flash-Next (`qwen4`) — serving recipes

Serving recipes for **Qwen3.8-Flash-Next**, a 180B MoE with hybrid GDN + full attention and a PLE
n-gram table, on DGX Spark (GB10). This directory is the `qwen4` model family (`model_symbol: qwen4`).

The lane ships **exactly two production recipes** after the 2026-10-14 cut: the fastest **TP=1** and
the fastest **TP=2** arm of the six that used to live here, all measured in one window on the
benchmark pair with [`benchmarking/decode-triage.yaml`](../../benchmarking/decode-triage.yaml)
(d=0/d=8192, C=1, 5 runs, decode-phase rows only). Everything else is archived under
[`../../attic/qwen4/arms/`](../../attic/qwen4/arms/) with a provenance row in
[`../../attic/qwen4/ARMS-MANIFEST.md`](../../attic/qwen4/ARMS-MANIFEST.md).

| recipe | nodes | checkpoint | runtime | role |
|---|---|---|---|---|
| [`qwen3.8-flash-next-nvfp4-solo-vllm-b12x.yaml`](qwen3.8-flash-next-nvfp4-solo-vllm-b12x.yaml) | **1** | local-inference-lab | vLLM | TP=1 — one Spark, PLE table streamed from disk (`VLLM_PLE_TABLE_MEMORY=disk`) |
| [`qwen3.8-flash-next-nvfp4-labquant-sglang.yaml`](qwen3.8-flash-next-nvfp4-labquant-sglang.yaml) | **2** | local-inference-lab | SGLang | TP=2 — the pair, 262k context, the lane's balanced config |

> **This directory runs as a git-distributed artifact.** Read [`AGENTS.md`](AGENTS.md) before editing
> anything here — it is the condensed operating guide (constraints, traps, runbook, validation
> ritual). Long-form evidence lives in the lane record,
> [`../../attic/qwen4/QWEN4-MODEL-OPTIMIZATION-WORK.md`](../../attic/qwen4/QWEN4-MODEL-OPTIMIZATION-WORK.md)
> (`§N` cite-target, git-ignored).

---

## What was measured, and the cut

Decode-phase C1 throughput (tok/s, mean ± std of 5), one boot per arm. Five arms were measured in one
2026-10-14 window on the benchmark pair; the sixth (`…-solo-sglang`) failed readiness there and was
re-measured later the same day on `.34` (see below). Receipts on the head:
`~/benchmarks/q4-*-triage_1014_*.{json,yaml}` and `~/benchmarks/q4-solo-sglang2-triage_1014.*`.

| arm | nodes | d=0 | d=8192 | verdict |
|---|---|---|---|---|
| `…-labquant-sglang` (pre-cut pin `7c4f1bc1`) | 2 | 41.32 ± 4.16 | 38.58 ± 2.37 | **kept — TP=2 survivor** |
| `…-labquant-sglang` (re-pinned `6c01ac37`) | 2 | 40.32 ± 1.94 | 43.29 ± 2.68 | same arm after the re-pin; the shipped receipt |
| `…-labquant-longctx-sglang` | 2 | 42.47 ± 3.03 | 39.04 ± 3.15 | tied at C1; 1M quality unverified → attic |
| `…-labquant-highcon-sglang` | 2 | 40.10 ± 2.44 | 41.92 ± 5.28 | tied at C1; larger pool for a regime not shipped → attic |
| `…-nvfp4-sglang` (RadixArk) | 2 | 36.84 ± 3.42 | 34.44 ± 1.19 | ~12% slower at C1 → attic |
| `…-solo-vllm-b12x` | 1 | 33.92 ± 1.73 | 34.35 ± 1.26 | **kept — TP=1 survivor** |
| `…-solo-sglang` | 1 | 19.82 ± 2.06 | 20.97 ± 1.02 | ~42% below the TP=1 pick → attic |

The three labquant TP=2 arms are **statistically indistinguishable** at C1 (means 40.1–42.5 with
overlapping 2–4 tok/s stds). The balanced base is kept because at equal speed the owner's priority
order breaks the tie on memory and accuracy-safety: it carries the smallest mamba pool (112 vs 128)
and no unverified 1M extrapolation. Read the whole table as a *triage*: a 5-run C1 cell on this
hardware has a multi-percent boot-to-boot floor (WORK §4b), so a rank here is decisive only when the
gaps are ≫ the std.

The TP=1 arm is ~18% slower than TP=2 at C1 but uses **one node instead of two** — which is the
owner's first priority. That trade is the reason both survive the cut.

---

## The TP=2 recipe — labquant balanced base (SGLang, 2 nodes)

All defaults are in the recipe; the couplings that matter:

- **Pin.** `model_revision: 6c01ac378d22…` — the step-5500 QAD revision (`main` since 2026-10-06),
  43 shards / ~106.3 GB. **The pin key is `model_revision:`, not `revision:`** — a bare `revision:`
  is silently ignored (§1 fact 1 in `AGENTS.md`). Do not unpin: `main` has twice moved under us.
- **The mod chain (6 mods).** `drop-caches` → `fix-labquant-modelopt-mixed-flat-schema` (builds the
  `/cache/runtime/labq-patched` tree) → `unpack-labquant-ple-nvfp4-to-fp8` → `diag-qwen4-unplaced-scales`
  → `fix-labquant-mxfp8-weight-scale-name` → `demote-labquant-narrow-mxfp8-to-bf16`. **`mods:` is an
  ordered dependency chain, not a set** — the config mod must stay first and the demote mod last.
  A 7th mod, `skip-labquant-vision-tower`, was **dropped on this revision**: it existed to work around
  the OLD export's NVFP4-quantised vision tower, and the step-5500 revision ships that tower **BF16**
  and already lists `model.visual.*` in `quantization_config.ignore`. This export therefore serves
  **vision as well as text** now (the old recipe was text-only).
- **Two mandatory engine flags**, not tunables: `--moe-runner-backend flashinfer_cutlass` (with `auto`
  the NVFP4 MoE resolves to FLASHINFER_TRTLLM, dead on SM121) and
  `--cuda-graph-backend-prefill disabled` (else prefill CUDA-graph capture raises). They live in
  `defaults.extra_args` so the recipe carries them.
- **Knobs that are answered — do not re-litigate.** `kv_dtype: fp8_e4m3` is a config-level NO (boots,
  allocates, then dies in SM121 QSA decode: `unsupported SM121 QSA call`). `chunked_prefill_size 8192`
  regresses k=8/k=16 on this checkpoint; keep 4096. `max_num_seqs` must stay strictly above every
  served `k`, and the real admission ceiling is the **mamba pool** (`max_mamba_cache_size // 4` on the
  lazy strategy: 112 → 28).

A full 1M-token route (YaRN) existed as the archived `…-longctx-` arm; it is **quality-unverified above
~262k** (the checkpoint declares `max_position_embeddings = 262144` with no YaRN config, and a
neighbouring needle test failed at 300k), so the shipped recipe keeps `max_model_len: 262144`.

## The TP=1 recipe — vLLM solo (1 node)

The ~47.7 GiB FP8 PLE n-gram table, not weights+KV, is what does not fit one Spark; keep it **off the
device** and the rest of the server config is the TP=2 shape at `--tp 1`. This recipe does that with
`VLLM_PLE_TABLE_MEMORY=disk` (mmap/pread per step). The image is a floating
`ghcr.io/spark-arena/dgx-vllm-eugr-nightly-b12x:latest` (the b12x build publishes no digest-pinnable
alias), so any measured number is tied to whatever that tag resolved to. Boot-verified; W3 battery
**38/38** (n=1, 2026-10-10).

The SGLang single-Spark route (`--ple-offload-embedding --ple-offload-backend file`) is **archived**:
in the 2026-10-14 window it first failed readiness, and the re-measurement (`bench_253dd84c9a78`)
shows why it was never a contender — **19.82 ± 2.06 t/s d=0 / 20.97 ± 1.02 d=8192**, ~42% below the
vLLM solo arm and far outside its σ. The failure was a **port timeout, not an architectural
negative**: with `readiness.port_timeout_s: 3600` the port opened at **TTR 3477 s**, i.e. past
sparkrun's default 1800 s (which is what killed the first attempt). Its cookbook speed figures are
the cookbook's hardware and were never reproduced here.

---

## Performance (measured, both survivors)

Read aggregate **and** per-request together, and read your cell's noise floor before comparing
(WORK §3c, §4b).

| quantity | TP=2 (labquant base) | TP=1 (solo vLLM) |
|---|---|---|
| C1 decode d=0 | **40.3 ± 1.9** tok/s | 33.9 ± 1.7 tok/s |
| C1 decode d=8192 | **43.3 ± 2.7** tok/s | 34.4 ± 1.3 tok/s |
| TTFT d=0 / d=8192 | 853 / 2108 ms | 1145 / 1220 ms |
| W3 quality battery (38 tasks) | **stable-pass 37/38**, 113/114 across `--repeat 3` (2026-10-14) | 38/38 (2026-10-10, n=1) |


The TP=2 survivor's battery receipt is `~/benchmarks/q4-w3-repin-20261014/w3-repin.json` on the head;
one task (`qa-code-06`) flips across repeats and is reported as flaky, not as a score. This is the
same instrument that read labquant 37/38 and RadixArk 35/36 on 2026-10-04.

Two structural facts worth internalising: decode is **not** purely byte-bound — `t_step = F +
bytes/B` with `B ≈ 145.5 GB/s` and a fixed per-step cost `F ≈ 8.4 ms` that no quantisation removes
(WORK §3); and there is **no single noise floor** — per-cell inter-boot spreads here span ~0.6–35%.

The labquant checkpoint is the more aggressively quantised export (MXFP8 attention/GDN, FP8 PLE,
packed-NVFP4 PLE unpacked to fp8 by a required mod). Its W3 battery reads essentially equal to the
RadixArk reference's on the tasks both ran, which is what promoted it to the lane's only checkpoint —
but the battery is a gross-regression instrument, not an accuracy certificate
(`attic/qwen4/status/W3-QUALITY-EVAL-STATUS.md`).
