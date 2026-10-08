# COOP — `recipes/ifm/` (IFM K2-Horizon family: 0.9B / 7B-FP8 / 36B-A4B)

Cross-agent coordination ledger for the K2-Horizon lanes. Its job, per
`K2-09B-MODEL-OPTIMIZATION-WORK.md`: hold the **family-wide findings the 7B and 36B-A4B agents
need**, so two agents never spend a boot answering the same question. Narrative belongs in the
`K2-*-JOURNAL.md` files; durable evidence belongs in the `K2-*-MODEL-OPTIMIZATION-WORK.md` files.

> **This file is a 2026-10-07 reconstruction.** The original was lost from the working tree — it is
> cited by `k2-horizon-36b-a4b-*.yaml` as "COOP item 3/8/9", by `tests/test_ifm_recipes.py` as a
> source, and by `tests/test_ifm_36b_recipes.py` ("see COOP 2026-09-21 correction"), and no copy
> survived anywhere on disk. Everything below is transcribed from those citations and from the
> lane's own documents; nothing is invented. Items whose numbers are cited nowhere were not
> recoverable — **do not renumber the anchors**; add new items at the next free numbers.
>
> Like the sibling lanes' ledgers, this file is **not to be `git add`ed** (it may carry live node
> state). Keep hostnames and addresses out of anything tracked.

## Live state — update every session

| field | value |
|---|---|
| Session date | *(no session claimed in this tree)* |
| Assigned pair | node assignment lives node-side; resolve hostnames before acting |
| Bench lock | none — write `BENCH LOCK: <agent> <arm> <nodes> <eta>` here before launching, remove it when the job ends |

## Items cited by name elsewhere in this lane

- **Item 3 — `--attention-backend fa3` cannot be constructed on GB10.**
  `create_flashattention_v3_backend` asserts `(major == 8 and not use_mla) or major == 9`
  (`layers/attention/attention_registry.py:227-235`, VERIFIED at v0.5.20); GB10 reports `(12, 1)`
  (`utils/common.py:332-333`, `is_sm121`). Both the HF cards and the SGLang cookbook pass `fa3`
  because both were written on Hopper — copying them is the single most likely way to ship a recipe
  that cannot boot. `flashinfer` is sglang's own auto-default for major 12; name it explicitly.
  Citing sites: `k2-horizon-36b-a4b-bf16-tp1-sglang.yaml:178`,
  `k2-horizon-36b-a4b-fp8-tp1-sglang.yaml:157,290`.
- **Item 8 — a declared `dtype` in `config.json` is not the tensor dtype.**
  `--dtype auto` resolves through the *declared* config dtype
  (`configs/model_config.py:2078-2124`) and quietly maps a declared `float32` onto float16 for any
  non-gemma `model_type`; the 0.9B checkpoint declares `float32` while `validation.json` says its
  tensors are BF16, so `auto` can load 6.5 GB where 2.16 GB was intended
  (`k2-horizon-0.9b-bf16-sglang.yaml:67-74`). Every recipe here pins `dtype: bfloat16`.
  **Open discrepancy:** the citing comment at `k2-horizon-36b-a4b-fp8-tp1-sglang.yaml:149-151` says
  *this* (36B FP8) checkpoint advertises float32, while the BF16 sibling
  (`k2-horizon-36b-a4b-bf16-tp1-sglang.yaml:108-109,203-206`) and
  `tests/test_ifm_36b_recipes.py` I4 say the 36B declares bfloat16 honestly and the 0.9B sibling is
  the liar. Resolve which checkpoint the item refers to before quoting it.
- **Item 9 — the vendor card's `--revision` is an sglang commit-ish and 404s.**
  The cards pass `--revision 9b9ec1f7e17f…`, which does not exist in any `IFM/K2-Horizon-*` repo;
  each recipe pins the checkpoint SHA the analysis was done against instead.
  Citing sites: `k2-horizon-36b-a4b-fp8-tp1-sglang.yaml:10,291`; guard I6 in
  `tests/test_ifm_36b_recipes.py`.

## Family-wide findings (each with its source)

- **SGLang >= v0.5.20 or nothing.** `models/xllm.py` (which registers `K2HorizonForCausalLM`) does
  not exist at v0.5.19, and vLLM's support PR is closed-unmerged, so vLLM is not a fallback.
  (`K2-09B-MODEL-OPTIMIZATION-WORK.md` TL;DR 1; `tests/test_k2_7b_recipes.py` header.)
- **The model cards' launch snippets do not boot on a Spark, for three independent reasons:** fa3
  (item 3), `--revision` (item 9), and a vLLM block that is not valid JSON. Both cards also serve
  the BF16 model rather than the FP8 one they document.
  (`K2-09B-MODEL-OPTIMIZATION-WORK.md` TL;DR 2; `tests/test_k2_7b_recipes.py` header.)
- **The 36B-A4B FP8 checkpoint cannot load without `mods/patch-sglang-k2-horizon-fp8`**
  (`models/xllm.py:664` accepts only `compressed_tensors`/`fp8`; `:1229` raises on a non-None
  quant_config on a MoVA layer), and the BF16 sibling must **not** mount it: both gates pass on
  their own terms, and patching a runtime you do not need is exactly what the `patched` tag exists
  to expose. (`tests/test_ifm_36b_recipes.py` I2.)
- **FP8 TP is 1 or 2, never 4 or 8** — `layers/quantization/fp8.py:1368-1390` requires
  `moe_intermediate_size / TP % block_n == 0`, and 768 with `weight_block_size [128,128]` fails at
  4 and 8. It raises at model build, after a 48 GB sync to every node. (Same file, I5.)
- **`fp8_gemm_backend` is `cutlass`, spelled.** `auto` prefers DeepGEMM, whose scale layout gates on
  `get_device_sm() == 120` exactly and so excludes SM121.
  (`tests/test_k2_7b_recipes.py` header, sec 4.3.)
- **7B UNO cannot boot on SM121**: `_handle_uno` requires the `(fa3, fa3)` pair, so the Uno arm is a
  probe (`mods/probe-uno-fa4-sm121` + `mods/provide-uno-lora-k2-horizon-7b`), not a production
  recipe. (`tests/test_k2_7b_recipes.py` header, sec 6.7.)
- **Pin the fast-core mask.** `taskset -c 5-9,15-19` (the X925 clusters; A725 is 0-4 and 10-14) is a
  measured win carried into every 36B command. (`tests/test_ifm_36b_recipes.py`
  `I10CommandShape.test_taskset_fast_core_mask`.)
- **KV sizing is the binding constraint on this family.** 7B FP8 is 144 KiB/token (a 512K sequence
  would be 72 GiB of bf16 KV — `k2-horizon-7b-fp8-sglang.yaml:59-62`); the 36B is 192.0 KiB/token
  and its `max_position_embeddings` of 524 288 implies 103.1 GB for one sequence, 80 % of a Spark's
  unified memory. Size by bytes, not by parameter count.
  (`K2-36B-A4B-MODEL-OPTIMIZATION-WORK.md` "The three numbers that matter".)

## Dated corrections

- **2026-09-20 (late)** — a cross-agent fetch overwrote `config.json` in the shared scratch cache
  (`.scratch/ifm/`, parent of the per-model `09b/` directory). Keep each model in its own
  subdirectory and re-verify `total_size` before trusting a local copy.
  (`K2-09B-MODEL-OPTIMIZATION-WORK.md` header.)
- **2026-09-21** — the `rewrap-k2-horizon` mod was **abandoned**; do not resurrect it.
  (`tests/test_ifm_36b_recipes.py`, "that mod was abandoned; see COOP 2026-09-21 correction".)

## Protocol

1. **Claim before you work** — add a row with your agent id, workstream and date. One owner per
   workstream per session; the deliverable is a committed file, a `bench_*` id, or a `§N` section —
   never a chat sentence.
2. **One bench job at a time** — the assigned pair supports exactly one arm; put a `BENCH LOCK:` line
   in Live state before launching and remove it when the job ends.
3. **Post failures too** — a boot that dies, a flag that does not reach the server, a node with low
   `MemAvailable`: one line here saves the next agent a boot.
4. **Every entry carries an evidence pointer** — a `bench_*` id, a `§N` cite, or `file:line`.