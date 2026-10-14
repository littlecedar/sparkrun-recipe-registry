# Qwen3 — `recipes/qwen3/` agent & developer guide

**RadixArk/Qwen3.8-27B-NVFP4** on a single NVIDIA DGX Spark (GB10, SM121, 128 GB unified
LPDDR5X), TP=1, SGLang. Read this before touching a recipe in this directory, its mods, or the
guards. Sources for every number here are in the archived research docs (§9); where this file and a
`§N` section of the archive disagree, the section holds the raw evidence and this file has a bug —
fix this file and say so in the lane notes.

**Scope of this directory.**

| recipe | role |
|---|---|
| `qwen3.8-27b-nvfp4-dflash2-sglang.yaml` | **shipping** — DFLASH2 spec decode, block 8 |
| `qwen3-coder-next-int4-autoround-vllm.yaml` | a different family (Intel/Qwen3-Coder-Next, vLLM) sharing the lane dir only |
| `qwen3.8-27b-mlx4bit-tensorfold-sglang.yaml` | **booted + measured 2026-10-14** — a foreign engine (TensorFold v0.6.0 + MiaAI-Lab patches) behind the `runtime: sglang` shim (§12, §13); C1 **41.3 t/s** @ d0, house battery **37/37** |

The **no-spec control** and the **DSpark arm** (measured, rejected: −16 % vs DFlash2; DSpark requires
`speculative_num_draft_tokens == gamma + 1`, i.e. 8 not 7) live in [`attic/qwen3/`](../../attic/qwen3/)
with everything else the lane used to carry — see the manifest there.

The four **Qwen3-VL embedding/reranking** recipes moved to [`recipes/embed/`](../embed/README.md)
and [`recipes/rerank/`](../rerank/README.md) on 2026-10-10; `tests/test_qwen3_vl_embeddings.py`
guards those lanes, **not** the recipes here.

**Evidence vocabulary (repo convention).** **VERIFIED** — read from a primary artifact (a boot log,
a pinned image, source at a pinned commit) or measured on our devices. **LIKELY** — strong secondary
evidence. **SPECULATIVE** — reasoning without a source; do not build on it. Never promote `LIKELY`
into unlabelled fact. **Many numbers in the archived docs were retracted** — check a section's
retraction banner before quoting it.

---

## 1. The model in one paragraph

The checkpoint is a **dense hybrid, not an MoE**: 64 layers = 48 GDN (linear-attention) + 16
full-attention, no experts. Every weight is read on every token, so this is a **streaming-bandwidth
problem, not a gather problem**: **17,608 MB/token** of weights against ~**221 GB/s** effective read
implies a plain-decode ceiling of **~14 tok/s at TP=1**. Every published throughput is that ceiling
times speculative amplification:

```
tok/s ≈ A_eff × BW / B_token        A_eff = accepted tokens per verify step
```

Consequence: a benchmark alone cannot separate better bandwidth use from simply accepting more
draft tokens per step — which is why the **no-spec control** existed as the denominator.

## 2. Best measured state

| quantity | value | note |
|---|---|---|
| plain decode (no-spec, d=0, c=1) | **12.56 ± 0.02 tok/s** | 10 runs / 2 containers; ±0.25 % across boots |
| shipping decode (block 8, d=0, c=1) | **33.76 tok/s** | the *ratio* from the block A/B is the durable number, not this absolute |
| block 8 vs block 4 | **+22.5 %** (95 % CI [1.188, 1.262]) | pooled ratio-of-means over 3 same-node interleaved phases, 24 boots |
| granted concurrency | **21** (`K=85`) at `D=8`, fresh container | mamba pool clamp; 26-slot ceiling at any ratio |
| implied weight bandwidth | **221 GB/s** | = 17.608 GB × 12.56 tok/s |
| accepted tokens/step `A_eff` | **3.265** pooled (1,481 log lines) | 3.99 is a single probe; quote 3.265 for capacity math |
| c=8 depth cost (8k→) | **~20 %** (boot-level 8–29 %) | congested/pool-limited; uncongested c=4 is **~11 %** |
| bench at c=2 (tg=128, pp=256) | ~71 t/s aggregate | the `recipes/README.md` "50 t/s" headline is this family of shape — not comparable to 33.76 (per-stream 35.4) |

**Estimator warning:** ratio-of-means vs ratio-of-medians differ by ~2 % on this lane — the size of
effect several claims turn on. Quote a ratio with its estimator or it is ambiguous.

## 3. Load-bearing constraints and traps

1. **Node assignment is per-session.** The free pair is the benchmark target; the head and the
   restricted nodes serve the DS4 job. Concrete addresses live in `.local/CONFIDENTIAL.md`
   (untracked) and any lane `COOP.md`; re-check and re-resolve hostnames before acting.
2. **Run recipes by name from the head's run-from dir** with `mods` symlinked in; running by
   absolute path breaks `mods/<name>` resolution.
3. **One boot/arm at a time** on the free pair. Co-resident jobs recreate each other's containers.
4. **`-o` overrides `defaults:` only through a consumed `{placeholder}`.** Verify on the rendered
   line (`sparkrun run <recipe> -H <node> -n`), then on the live argv for load-bearing flags.
5. **Mods run as root** in the persisted runtime cache; reown anything under `/cache/runtime` to
   `stat -c '%u' /cache/runtime`, or later launches die with a root-owned `PermissionError`. Never
   `import sglang` from a `pre_exec` mod (flashinfer JIT writes root-owned files).
6. **This tree is syncthing-shared with a live second writer.** Never `git add -A`, directory adds,
   or bare globs. Use explicit pathspecs and review `git diff --cached --stat`.
7. **Mods fail closed**; a launch log is not the server log — the crash text lives in the container.
8. **`sparkrun show/run <name>` off the sandbox registry cache can lie** (stale clone). Validate a
   recipe **by path**; `sparkrun recipe validate <path>` reads the file directly and is correct.
9. **Read the grant from the server's own log**, never from a restated number. `grep -F 'capped to'
   /tmp/sparkrun_serve.log` inside the container: that warning's first field *is* the granted
   `max_running_requests` (`mem_cache/kv_cache_configurator.py:2177-2193`). The log dies with the
   container — grab it before teardown.
10. **Search the archive by benchmark PROFILE name before queueing an experiment.** One was re-run
    at 8 boots' cost for lack of a recorded profile name (`ANSWERED-QUEUES.md`).
11. **Never write `--served-model-name {model}` (27B).** sparkrun binds every `{model}` occurrence —
    including one inside `--served-model-name` — to the prepared snapshot path on a real launch
    (`models/runtime.py::bind_runtime_models`), so the engine advertises `/cache/huggingface/hub/…`
    as its model id while `-n` still prints the repo id. The 27B arm declares
    `served_model_name: RadixArk/Qwen3.8-27B-NVFP4` and renders the flag from it; fixed and
    live-verified 2026-10-13 (boot `3b78f3ef7df2980b_64af2f7668b6`, `.35`: `GET /v1/models` →
    `RadixArk/Qwen3.8-27B-NVFP4`, 262144 ctx, TTR port-open 119.8 s). Guard:
    `tests/test_recipe_placeholder_resolution.py::ServedModelNameNotRebound`.

## 4. Why each shipped value is what it is

| knob | value | why / what breaks if moved |
|---|---|---|
| `max_num_seqs` | `48` | **Not the granted concurrency.** The mamba/GDN state pool silently clamps it to **21** (`capped to 21`, `K=85`; one low-`T` boot logged 20/82 — node state, not container age). Deliberately left at 48: harmless, and changing it would hide the discrepancy. It **cannot** reach 48 while `speculative_draft_tokens=8`, at any ratio (26-slot ceiling). |
| `mamba_full_memory_ratio` | `3.51` | Highest-leverage knob, **context-length dependent**. Usable long-context concurrency is `min(granted slots, #tokens // (depth+pp))` — the `pp` term is load-bearing (§5). Measured 8k: ratio 2.3 fits **15** concurrent 8k contexts vs **11** at 3.51. **Deliberately still 3.51**: flipping it is a claim about expected traffic shape and this recipe has no stated target mix — the evidence is not the blocker, **ask before changing it**. Do **not** "just lower it for long context": the optimum is interior (≈3.6 at 4k, ≈2.3 at 8k, ≈1.2 at 16k) and below the crossing point slots collapse. |
| `mamba_ssm_dtype` | `bfloat16` | **Deliberate override of the checkpoint's declared float32** — it **doubles granted concurrency (21 vs 10 slots)** and is bit-identical to fp32 on the path that READS stored state (6/6 rep-pairs, worst `|dlogprob| = 0.00e+00` over 495 tokens, with a 1.0–5.1-nat positive control proving the instrument is sensitive). The perturbation is real (~1.7e-3 relative, one bf16 quantum) but absorbed before the logits. **Do not "restore float32 for safety"**: that surrenders 11 of 21 slots on evidence nobody has produced. Still untested: long-distance state accumulation, free-running generation, any downstream quality metric. |
| `mamba_radix_cache_strategy` | `extra_buffer_lazy` | Reuse is non-obvious: `cached_tokens` GROWS with repeat visits (1 absorb → 0, 2 → 64, 3 → 64, 4 → 128 for a 128-token prefix). Any warm-up that needs the kernel to read stored state must absorb the shared prefix **several** times; and `prefix_caching: true` in a benchmark does **not** mean prefixes are shared on the first pass. |
| `speculative_draft_tokens` | `8` | The draft checkpoint declares `dflash_config.block_size = 8`; passing any other number wins **silently**. 8 is what the draft was trained for — do not raise past it (the mismatch guard only fires when both flags are set explicitly). |
| `speculative_draft_model` | `incoai/…DFlash2` | `incoai` and `z-lab` are the SAME weights (same blob hash, verified with `stat`) — a draft-provider A/B cannot measure anything. Do not spend an arm on it. |
| `kv_cache_dtype` | `auto` | Left `auto` so the **checkpoint keeps ownership** of the KV dtype; it resolves to `fp8_e4m3` because the checkpoint's `hf_quant_config` ships `"kv_cache_quant_algo": "FP8"` (read the server's allocation line, not the `--help` text — `metadata.kv_dtype: fp8_e4m3` is VERIFIED and correct). Pinning the string would silently diverge if the checkpoint were re-quantised. |
| `chunked_prefill_size` | `4096` | Scheduler token budget per prefill batch — **NOT related to draft length** (a former comment here claiming "Max new tokens" was false; the two are uncoupled). Safe for the mamba extra-buffer path; raising it cannot speed up GDN (that path's internal chunk is fixed at 64, verified from the installed module). |
| `mods:` | `drop-caches`, `pip-install-fastsafetensors` | Order matters; the same pair is mounted by the archived control and DSpark arms on purpose — a mod difference makes a comparison two variables. **TP=2 cannot boot this model** (see §7); do not mount the tp2 fix mod expecting a different result. |

## 5. The capacity model, and the divisor it used to get wrong

Usable concurrency at any context length is:

```
usable = min(granted slots, #tokens // (depth + pp))
```

The `pp` term is the whole point of §12.54 in the archive: llama-benchy runs a prefill phase
(generating `pp` tokens) then a decode phase, so a request's resident token count is
`depth + pp + tg`, **not** `depth`. Every older `usable` table used `L = depth` and understated
per-request cost by 11 % at 16k and **25 % at 8k**. Verified on archived artifacts: each arm's
**decode-phase** peak `#running-req` equals `#tokens // (depth+pp)` in **14/14** arms and
`#tokens // depth` in **0/14** (three phases, both nodes). Reading the prefill-phase peak instead
is the trap — the prefill-phase population does match `L = depth`, because `pp` has not been
generated yet, and sglang labels a batch by what it is doing, not by the harness phase.

| context | shipped (r=3.51) | lowered ratio | measured |
|---|---|---|---|
| 8192 + pp 2048 | 11 usable (118,002 tokens) | 15 at **r=2.3** (239,298) | +7.4 % aggregate at c=16, streams 11 → 13, replicated to 0.001 across two nodes |
| 16384 + pp 2048 | 6 usable (117.9–119.4k tokens) | 12 at **r=1.2** (238.4–239.5k) | +55.8 % aggregate at c=12 (1.558×) — below the 2.00× capacity ratio; **throughput at 16k remains unreplicated** |

The measured 16k arm is **r=1.2, not r=2.3** — the booted pair was `ship` vs `-o
mamba_full_memory_ratio=1.2` (phase 26, replicated p27/p82). Ratios move the two pools against each
other, so a usable-count comparison is only valid at the ratio that was actually run: the 8k pair is
3.51 vs 2.3, the 16k pair is 3.51 vs 1.2. **At 16k, r=2.3 (8 usable) beats r=1.2 under the
corrected divisor too** (archive `WORK §12.24`: r=1.2 is 12 there), so r=1.2 is the *booted* arm,
not the *optimal* one — do not read this table as a recommendation to run r=1.2.

**The trade this table hides, read before recommending a change:** at 16k with offered concurrency
12–16, lowering the ratio to 1.2 buys stream count (7 → 13, established twice) and **costs ~11.3 %
per-request latency** on a prefill-dominated load (wall 114.8 s vs 127.8 s). That is a capacity and
latency trade, not a free throughput win, and the aggregate benefit is still unmeasured. The wall-time
result is the admissible one; do not read the pinned aggregate (15.23 vs 15.55) as "no gain".

## 6. The archived control — what it supplied, and the pairing rule

`attic/qwen3/qwen3.8-27b-nvfp4-nospec-control-sglang.yaml` supplies the plain-decode term the DFLASH
recipe cannot provide on its own (12.56 t/s, above). **To repeat a spec-vs-nospec comparison, copy it
back into this lane first** — while it sits in `attic/`, the lane's validation script skips it.

- **The ratio is PART of the pairing.** The control ships `mamba_full_memory_ratio: 3.51` to **match
  the treated recipe**, not because it is optimal for a no-spec run. Optimising one arm's ratio while
  the other stays at 3.51 silently turns a controlled comparison into two different configurations.
  If the treated recipe's command changes, the control needs the same change before it can be used
  again. Value parity last checked 2026-10-10: comment-stripped, the two commands differ in exactly
  the three `--speculative-*` keys/flags.
- **Granted concurrency differs: 48 on the control vs 21 on the shipping recipe** (no `(1+D)`
  reservation, no D-proportional verify scratch). Do not run a spec-vs-nospec comparison above c=21
  without accounting for this.
- **Do not set `speculative_algorithm: NONE`** on a no-spec recipe — that string is truthy where
  `None` is falsy, which routes the server into spec-decode metrics and crashes it. Omit the flags.

## 7. Negative results — do not re-derive / re-run

- **TP=2** — **cannot boot** this model. Rank 1 dies in ~3 s with `CUDA error: invalid device ordinal`
  (SGLang derives the CUDA device from the **global** rank on a 1-GPU box); rank 0 then hangs at
  `Loading safetensors 0%`. A fix mod exists (`recipes/cybersec/mods/fix-fastsafetensors-tp2-sglang`) but has never
  been run; either mount it deliberately as an experiment or leave TP=1.
- **`--enable-linear-replayssm-spec`** — rejected; the scheduler raises
  `ValueError: --enable-linear-replayssm-spec with DSPARK/DFLASH requires a KDA (kimi_linear) model;
  got a non-KDA model` **after both weight loads** (`kv_cache_configurator.py:1106-1114`) — a full
  boot, so do not re-run it casually.
- **`dev-qwen38-27b-dflash2` container** — not load-bearing; `dev-cu13` already ships DFLASH +
  `qwen3_5.py` + `qwen3_5_mtp.py`.
- **`z-lab` vs `incoai` draft A/B** — same weights, same blob; not an experiment.
- **`kv_cache_dtype=fp8_e4m3` vs default** — not a variable; `auto` already resolves to
  `torch.float8_e4m3fn` (the explicit flag differed only in spelling).
- **Raising benchmark `runs` to fix spec-arm variance** — wrong remedy; the variance is *acceptance*
  variance, not measurement noise.
- **The sub-4k depth bump** — a blocked-order artefact (first cell of a blocked sweep is depressed,
  not depth 2048 being fast); depth is monotone decreasing. **KV-bandwidth GB/s figures** — four were
  retracted; do not quote one.
- **`max_num_seqs: 48`** — never granted; the mamba pool is the ceiling (21 at `D=8`).
- **The DSpark draft** — boots on GB10 but loses ~16 % to DFlash2 (28.46 vs 33.76 t/s, decode-triage,
  2026-10-10); the card's GB300/H200 numbers do not transfer to SM121. Archived with its receipt
  pointers in `attic/qwen3/`.

## 8. Open items (deliberately not closed)

- **The ratio decision is a traffic-shape question, not a data question.** Pick a target mix
  ({4k, 8k, 16k} heavy) or leave 3.51.
- **16k ratio throughput remains unreplicated.** New depth/ratio arms need the pre-registered length
  rule: **≥ ~2,500 generated tokens** per cell, or the load is prefill-dominated by construction and
  `tg` is pinned. The depth-cost frontier's acceptance instrument is also unresolved (n ≈ 40–50
  decode lines per cell over ≥ 2 boots).
- **Image/manifest digest pinning** and **dropping `cluster_only:`** were queued, never done.
- **Qwen3-VL embed/rerank sizing** — correctness shipped, the colocation cost is open
  (`recipes/embed/`).

## 9. Where the evidence lives

All of the lane's research docs were archived on 2026-10-11 to [`attic/qwen3/`](../../attic/qwen3/)
(manifest: [`attic/qwen3/ARMS-MANIFEST.md`](../../attic/qwen3/ARMS-MANIFEST.md)):

| doc | cite form | use for |
|---|---|---|
| [`attic/qwen3/QWEN3-MODEL-OPTIMIZATION-WORK.md`](../../attic/qwen3/QWEN3-MODEL-OPTIMIZATION-WORK.md) | `WORK §N` | decision record: what we believe, at what confidence, and why |
| [`attic/qwen3/DEPTH-COST.md`](../../attic/qwen3/DEPTH-COST.md) | `DEPTH-COST §12.NN` | the depth/ratio thread, retractions marked inline — **read its bottom-line before quoting any depth figure** |
| [`attic/qwen3/SSM-STATE-DTYPE.md`](../../attic/qwen3/SSM-STATE-DTYPE.md) | `SSM §12.NN` | the bf16-vs-fp32 dtype probes and their sensitivity limits |
| [`attic/qwen3/ANSWERED-QUEUES.md`](../../attic/qwen3/ANSWERED-QUEUES.md) | `AQ item N` | **search by profile name before running anything** |
| [`attic/qwen3/NOTES.md`](../../attic/qwen3/NOTES.md) | — | the lane's action-plan snapshot and drift list at archive time |

Sections did **not** get renumbered when archived; `§N` cites in any surviving artifact still
resolve. The attic copies are **frozen provenance** — do not tidy or re-edit them; correct a fact by
noting it in this file (or, for a retraction of something load-bearing, in the attic doc beside the
claim it retracts).

**A result has no provenance without its `bench_*` id**, and a boot's config comes from **that boot's**
`state.yaml`, never a sibling's or from memory. Cite `bench_*` + `§N`, never the printed sparkrun
table. Internal addresses and hostnames stay out of tracked files — the archived docs are masked
(node shorthand as `[.NN]`, operator paths as `/home/<operator>/…`).

## 10. Validation ritual (after every edit)

```bash
set -e
H=$PWD/.local/sparkrun-home
uv run python -B -m unittest discover -s tests
for f in recipes/*/*.yaml; do HOME="$H" sparkrun recipe validate "$f" >/dev/null; done
for s in mods/*/*.sh; do bash -n "$s"; done
for p in mods/*/*.py tools/*.py; do uv run python -m py_compile "$p"; done
find mods tools tests -name __pycache__ -type d -exec rm -rf {} +
```

Use **plain** `validate`, not `--strict` (accepted warnings exist on shipped recipes).
`py_compile` leaves untracked `__pycache__/` — clean it and **never stage it**. `recipe validate`
does **not** check mod existence; only a real launch (or `-n`, which resolves mods when a `command:`
template is present) surfaces a resolution failure.

## 11. References

- Checkpoint: [RadixArk/Qwen3.8-27B-NVFP4](https://huggingface.co/RadixArk/Qwen3.8-27B-NVFP4)
- Draft (DFlash2): [incoai/Qwen3.8-27B-DFlash2](https://huggingface.co/incoai/Qwen3.8-27B-DFlash2)
- Draft (DSpark, archived arm): [RadixArk/Qwen3.8-27B-DSpark](https://huggingface.co/RadixArk/Qwen3.8-27B-DSpark)
- vLLM coder model: [Intel/Qwen3-Coder-Next-int4-AutoRound](https://huggingface.co/Intel/Qwen3-Coder-Next-int4-AutoRound)
- Base image: [`lmsysorg/sglang:dev-cu13`](https://hub.docker.com/r/lmsysorg/sglang)
- Guard: [`tests/test_qwen3_vl_embeddings.py`](../../tests/test_qwen3_vl_embeddings.py) (the
  embed/rerank lanes) and [`tests/test_qwen3_recipes.py`](../../tests/test_qwen3_recipes.py) (the
  TensorFold arm); the lane's SGLang arms are covered by
  [`tests/test_recipe_placeholder_resolution.py`](../../tests/test_recipe_placeholder_resolution.py)
- Archive: [`attic/qwen3/`](../../attic/qwen3/) (control recipe, DSpark arm, research docs, manifest)
- TensorFold arm — upstream [MiaAI-Lab/Qwen3.8-27B-DGX-Spark-TensorFold](https://github.com/MiaAI-Lab/Qwen3.8-27B-DGX-Spark-TensorFold)
  (engine [ashhart/TensorFold](https://github.com/ashhart/TensorFold) v0.6.0 @ `c464617`), checkpoint
  [TensorFold/Qwen3.8-27B-MLX-4bit](https://huggingface.co/TensorFold/Qwen3.8-27B-MLX-4bit), drafter
  [z-lab/Qwen3.8-27B-DFlash2](https://huggingface.co/z-lab/Qwen3.8-27B-DFlash2), image
  `ghcr.io/miaai-lab/qwen3.8-27b-dgx-spark-tensorfold@sha256:043d192b…` (patch set `fb91a0019fdc`)

## 12. The TensorFold arm — the one strict warning, and why it is not the trap it names

`qwen3.8-27b-mlx4bit-tensorfold-sglang.yaml` pins `model_revision:` and its `command:` passes no
`--revision` — the engine has none — so `sparkrun recipe validate --strict` reports
**`unpinned-model-revision`**. Plain `validate` passes and is the repo's gate; this is the same
strict-only class as the three `recipes/qwen4/*labquant*` arms.

**The warning's failure story cannot happen here.** It describes an engine handed a bare repo id
finding no `refs/` entry (a SHA-keyed download writes none) under `HF_HUB_OFFLINE=1` and dying with
`LocalEntryNotFoundError`. This engine is never handed a repo id: sparkrun rewrites `{model}` to the
**prepared snapshot path** (`models/runtime.py::bind_runtime_models`), and `tensorfold serve` takes a
directory or a repo id, never a revision (`src/tensorfold/cli_args.py` at `c464617` has no
`--revision`). The pin therefore governs **distribution** — which is the only thing it can govern
here. Do not "clear" the warning by dropping the pin (that unpins what gets downloaded) or by adding
a flag the pinned engine does not parse (that is an argparse death at the engine, after the ~19 GB
download).

### 12.1 The flag that killed the first boot, and how it is suppressed

First boot, 2026-10-14, one node (`.30`), job `fe3054ad67464c54_2d38dfc4605e`: `GET /v1/models` →
`{"id": "Qwen3.8-27B", "owned_by": "tensorfold"}`, TTR port-open **71.5 s**, TTFT 98.7 s; serve log
`startup estimate 37.77 GiB within 116.72 GiB` and `drafts: on`. Measurements are in the lane README.

**As authored the launch could not boot.** The engine died on its own argv:
`tensorfold: error: unrecognized arguments: --served-model-name Qwen3.8-27B`. sparkrun's `sglang`
runtime appends its own `--served-model-name` to *any* rendered `command:` template whose config chain
carries a `served_model_name` (`runtimes/base.py::_augment_served_model_name` →
`reconcile_flag_in_command`), and TensorFold parses no such flag — it spells the served id `--name`.
That helper is a **substring** test, so the append is skipped when the flag text already appears in the
rendered command. The recipe therefore names the flag in a trailing `#` comment in `command:`; the
serve command runs as a bash script (scripts/exec_serve_detached.sh → bash /tmp/sparkrun_serve.sh), so
the comment is discarded before the engine sees it, while sparkrun still sees the token and skips the
append. **Do not "tidy" that comment away — removing it re-arms the append and the arm stops booting.**
(A future sparkrun that stops appending makes it inert, not wrong.) The ds4 lane's launcher shim is the
alternative route if a second engine-mismatched flag ever appears.

## 13. TP=2 on this engine is a runbook, not a recipe (the glm-lane precedent)

TensorFold does multi-node through its own spelling — `--tp 2 --rank R --master HOST
--master-port PORT` (`src/tensorfold/cli_args.py`: `--tp` has choices `(1, 2)`, plus `--rank`,
`--master`, `--master-port`, default 29551). sparkrun's sglang runtime declares the rendezvous flags
it manages as `--dist-init-addr/--nnodes/--node-rank` (`runtimes/sglang.py:250`) and appends
`--dist-init-addr HOST:25000 --nnodes N --node-rank R` for any world above one node
(`runtimes/sglang.py:481-486`) — three flags this engine does not parse. Worse, the launch path gates
its readiness wait on the port inside `--dist-init-addr`, so a wrong mapping turns into a head that
opens 29551 while sparkrun polls 25000 (the failure the ds4 shim documents).

So a TP=2 arm needs a **launcher shim** that consumes sparkrun's three flags and `exec`s
`tensorfold serve` with the mapped ones — the route `mods/tensorfold-dsv41-launcher` already ships
for the ds4 lane (`launcher.py`, whose docstring is the reference for the port/rank contracts). The
shipped arm is deliberately **TP=1 only** and declares no `tensor_parallel` default and no `--tp`
flag, so `-o tensor_parallel=2` cannot render a half-broken TP=2 (guarded by
`tests/test_qwen3_recipes.py::TensorFoldArm::test_no_tensor_parallel_flag`). TP=2 stays a runbook
note, as the GLM-5.3 TensorFold lines did ([`recipes/glm/README.md`](../glm/README.md)).

Two sizing facts: the startup estimate is **37.77 GiB within 116.72 GiB**, measured here on `.30`
(the upstream project's own figure is ~45 GiB at the serving defaults); and its `KV_POOL_GB=auto` (up
to 78 GiB pinned) is a host-side computation in its `start.sh` that a static recipe cannot run — the
arm leaves the pool to the engine and takes `-e TENSORFOLD_KV_POOL_GIB=<n>` at launch (the pinned image
reads that variable: `tensorfold/cuda/kv_fp8.py`).

## From recipes/qwen3/README.md (2026-10-14)

_The lane README body as it stood before the 2026-10-14 consolidation, verbatim: lane state, measurement histories, boot receipts, A/B and quality-battery tables, per-knob campaign notes, negative results and the notes block — i.e. everything the rewritten `recipes/qwen3/README.md` (shipped recipes only) no longer carries. Links inside are as authored (README-relative)._

# Qwen3 lane — `recipes/qwen3/`

_Brought to you by Little Cedar Group._

Shipped `sparkrun` recipes for the **Qwen3.8-27B** (SGLang, single DGX Spark) family.
All run on NVIDIA DGX Spark (GB10, 128 GB unified memory), TP=1 unless stated. The four
Qwen3-VL embedding/reranking recipes moved to their own lanes on 2026-10-10:
[`recipes/embed/`](../embed/README.md) and [`recipes/rerank/`](../rerank/README.md).

> Working here? Read [`AGENTS.md`](AGENTS.md) first — it is the lane's durable guide (traps,
> knob rationale, negative results, validation ritual). The deep research record is archived in
> [`attic/qwen3/`](../../attic/qwen3/) with a manifest. This README is the human-facing summary.

## Recipes

| recipe | runtime | model | flags | C1 t/s | notes |
|---|---|---|---|---|---|
| `qwen3.8-27b-nvfp4-dflash2-sglang` | sglang | [RadixArk/Qwen3.8-27B-NVFP4] + [incoai/Qwen3.8-27B-DFlash2] draft | 🌲🚀👀 | **33.8** | **shipping.** DFLASH2 spec decode, block 8. Decode-only, d=0, c=1. |
| `qwen3-coder-next-int4-autoround-vllm` | vllm | [Intel/Qwen3-Coder-Next-int4-AutoRound] | 🌲🚀 | **71.7** | Measured 2026-10-11, `benchmarking/decode-triage.yaml`: **71.7 t/s @ d0** (σ 0.2, n=5) and 67.8 @ d8k (σ 0.1) — **2.1× the DFlash2 lane's C1**, the lane's fastest decode by a wide margin. Serve line pinned to the prepared snapshot (`79c8a6bb`, `--revision=79c8a6bb` literal — see the recipe for why). No accuracy measurement yet; the keep call follows the quality pass. |
| `qwen3.8-27b-mlx4bit-tensorfold-sglang` | sglang (TensorFold shim) | [TensorFold/Qwen3.8-27B-MLX-4bit] (MLX 4-bit) + [z-lab/Qwen3.8-27B-DFlash2] draft | 👀 | **41.3** | **booted + measured 2026-10-14** on `.30`, boot `fe3054ad67464c54_2d38dfc4605e`. A foreign engine behind the `runtime: sglang` shim (the ds4 lane's pattern); house battery **37/37**. Decode-only, d=0, c=1. |

Flags: 🚀 fast (≥ 50 t/s) · 🌲 lcg_favorite · 👀 vision.

### The TensorFold arm (`qwen3.8-27b-mlx4bit-tensorfold-sglang`, added 2026-10-14)

[TensorFold](https://github.com/ashhart/TensorFold) is **not** an SGLang or vLLM route: it is its own
engine, and the recipe's `runtime: sglang` is only the declaration that makes sparkrun render a
`command:` template (on one node it appends no rendezvous flags, so the template reaches the engine
unchanged). The upstream project is Mia's AI Lab's
[Qwen3.8-27B-DGX-Spark-TensorFold](https://github.com/MiaAI-Lab/Qwen3.8-27B-DGX-Spark-TensorFold):
TensorFold v0.6.0 (`c464617`) plus five patches — up to 50 images and video input, opt-in YaRN,
an FP8 attention cache, a 0 GiB memory reserve, and a KV pool pinned at startup — baked into the
public image `ghcr.io/miaai-lab/qwen3.8-27b-dgx-spark-tensorfold` (patch set `fb91a0019fdc`,
digest-pinned in the recipe). One DGX Spark, TP=1: MLX affine-4-bit weights (~15 GB), the DFlash2
drafter (~3.6 GB), a 262,144-token window, FP8 KV, and image/video input.

What the registry changed from the upstream launcher, and why:

- **Checkpoint id**: the upstream card names `Vontra/Qwen3.8-27B-MLX-4bit`; the Hub repo has moved to
  the **`TensorFold`** org (the old id 307-redirects), so the recipe pins the canonical id at the
  same commit.
- **Port 8000**, the lane's convention, where upstream serves 8888.
- **`TORCH_EXTENSIONS_DIR`** is moved into sparkrun's runtime cache (`/cache/runtime/…`): the image
  bakes `/cache/torch_extensions`, but `/cache` is a mount parent docker creates as root while
  sparkrun runs the container as the invoking uid, so the engine's `sm_121a` kernel compile could not
  write there. As set, the compile is paid once a node instead of once a boot.
- **The drafter is declared** (`speculative_draft_model` + its own revision) so sparkrun stages it in
  the node's HF cache the way it stages the checkpoint. `TensorFold --drafter` reads it from there;
  an undeclared drafter leaves the offline engine without one.
- **The KV pool is left to the engine** (caches grow on demand). Upstream's `KV_POOL_GB=auto` is a
  host-side computation in `start.sh` — free memory at start minus ~31 GiB, capped at 78 — which a
  static recipe cannot run. To pin it, pass it at launch:
  `sparkrun run … -e TENSORFOLD_KV_POOL_GIB=78` (the engine refuses a pool that does not fit).

Upstream's own measurements (its `sparkDash` benchmark, one Spark): **58.3 t/s** decode single-stream
on prose and **136.9** on code, **220.6 / 323.2 t/s aggregate at 8 clients**, and 1,793 tok/s prefill
at 8k. Those are the upstream project's numbers, not this registry's, and its own fixed-seed rerun
reads lower on a different prompt/counting setup — so do not put them beside this lane's
`decode-triage` C1 column. This arm's own boot and measurements are below.

### Measured 2026-10-14 — boot, C1, and house battery

First registry boot of the arm, one node (`.30`), the recipe as shipped except for the one required
correction below. **Boot receipt** `fe3054ad67464c54_2d38dfc4605e`: `GET /v1/models` →
`{"id": "Qwen3.8-27B", "owned_by": "tensorfold"}` (not a `/cache/…` path), TTR port-open **71.5 s**,
TTFT 98.7 s. The serve log shows the TensorFold startup estimate (**37.77 GiB within 116.72 GiB**),
the `sm_121a` kernel builds (`tensorfold_qmm_v3`, `tensorfold_gdn_v2`,
`tensorfold_prefill_attention_v1`), and `serving Qwen3.8-27B at http://0.0.0.0:8000/v1 … drafts: on;
context: 262144; loaded in 70.2s`. The drafter `z-lab/Qwen3.8-27B-DFlash2` was staged at its pinned
commit `50307d4c…`, and the serving line reports **`drafts: on`**. The KV pool was left to the
engine (the recipe default; `TENSORFOLD_KV_POOL_GIB` is unset → grow on demand, "up to 8 streams");
`-e TENSORFOLD_KV_POOL_GIB=<n>` pins it (`tensorfold/cuda/kv_fp8.py` in the pinned image reads it).

`benchmarking/decode-triage.yaml` — bench `30c35dc7ade7`, `--skip-run --no-stop`, c=1, runs=5, the
served name resolved to `Qwen3.8-27B`:

| depth | tg t/s (decode-phase mean ± σ) | ttfr |
|---|---|---|
| 0 | **41.3 ± 4.0** | 6.2 ms |
| 8192 | **41.7 ± 2.4** | 23.5 ms |

Read the decode-phase records only: the d=8192 cell also emits a context-prefill record (tg 37.5,
`is_context_prefill_phase: true`) that must not be pooled. **At c=1 this arm out-decodes the
DFlash2 arm (41.3 vs 33.8 t/s) at no depth penalty from 0→8k** — the mirror image of the coder arm's
trade (41.3 here is *below* coder-next's 71.7, so the lane's speed arm is unchanged). One boot only,
σ 4.0 > the DFlash2 arm's spread, so treat 41.3 as provisional until a second boot.

House battery (`tools/quality-battery.py --tier both --max-tokens 2048`, n=1, thinking on):
**37/37** (19/19 easy + 18/18 hard) — ties the DFlash2 reference arm. The server returns the answer
in `content` and the think block in `reasoning_content`, so the battery's `content` read is not the
empty-content trap; the tool's 384-token default is nonetheless too small for a thinking model.

**The one correction the boot required.** As authored the first boot died instantly with
`tensorfold: error: unrecognized arguments: --served-model-name Qwen3.8-27B`: sparkrun's `sglang`
shim appends its own `--served-model-name` to any `command:` template that declares
`served_model_name` (`runtimes/base.py::_augment_served_model_name`), and TensorFold has no such flag
(it spells the id `--name`). The command now names the flag in a trailing comment — the helper's
substring check then skips the append, and the line is a shell comment so the engine never sees it.
See [`AGENTS.md`](AGENTS.md) §12.

Staged boot (one free node; render first, then launch):

```bash
H=$PWD/.local/sparkrun-home
HOME="$H" sparkrun run @littlecedar/qwen3.8-27b-mlx4bit-tensorfold-sglang -H .34 -n
HOME="$H" sparkrun run @littlecedar/qwen3.8-27b-mlx4bit-tensorfold-sglang -H .34
```

The first boot builds the `sm_121a` CUDA extensions and loads ~19 GB of weights — measured TTR
port-open **71.5 s** on `.30`, so the kernel build is not the slow part. `readiness` gives it 3600 s
before the port has to open. Three knowns: plain `validate` passes with the strict-only
`unpinned-model-revision` warning (this engine has no revision flag — it is handed the prepared
snapshot path; see [`AGENTS.md`](AGENTS.md) §12); **TP=2 is not expressible** in this recipe (§13);
and the launch logs a non-fatal `Could not install SGLang FP8 tuning configs` (the sglang runtime's
tuning-sync step against a non-SGLang image) — it does not block the serve.

Guard: [`tests/test_qwen3_recipes.py`](../../tests/test_qwen3_recipes.py).

### Paired house-battery quality (2026-10-11, `tools/quality-battery.py`, n=1)

The lane had **no quality numbers at all** before this pass. Same instrument, same window, one paired
boot per arm:

| arm | easy | hard | total | C1 t/s |
|---|---|---|---|---|
| `qwen3.8-27b-nvfp4-dflash2-sglang` (shipping) | 19/19 | **18/18** | **37/37** | 33.8 |
| `qwen3-coder-next-int4-autoround-vllm` | 19/19 | 16/18 | 35/37 | **71.7** |

coder-next's two misses are `hard-arith-1` and `hard-arith-2` — both multi-step arithmetic; everything
else, including the format/trick/code tiers, is clean on both arms. 35/37 at 2.1× the decode speed is a
**role split, not a loser**: DFlash2 stays the quality reference (37/37), coder-next is the speed/coder
arm. Both keep their place — no attic move is warranted (nothing is dominated on both axes).

Flags note: `no accuracy evaluation yet` on the coder row is now discharged.

### Archived to [`attic/qwen3/`](../../attic/qwen3/)

- `qwen3.8-27b-nvfp4-nospec-control-sglang.yaml` — the plain-decode control (12.56 t/s at c=1).
  Copy it back into this lane to re-run a spec-vs-nospec comparison; the pairing rule is in
  [`AGENTS.md`](AGENTS.md) §6.
- `qwen3.8-27b-nvfp4-dspark-sglang.yaml` — the DSpark draft arm, measured 2026-10-10 and **not an
  upgrade** (28.5 vs 33.8 t/s).
- `QWEN3-MODEL-OPTIMIZATION-WORK.md`, `DEPTH-COST.md`, `SSM-STATE-DTYPE.md`,
  `ANSWERED-QUEUES.md`, `NOTES.md` — the research record. Cite by `§N`; the section numbers were
  not renumbered.

## Qwen3-Coder-Next — the empty-`content` trap (2026-10-11)

Measured on the pinned eugr vLLM: with the model's native thinking ON, a short reply comes back
in the **reasoning** channel and `content` stays `null` — the `qwen3` reasoning parser never sees a
closing think tag. A client that reads `content` (the house battery, most OpenAI SDK callers) sees an
empty reply: the house battery scored **0/19 + 0/18 on empty strings** while `/v1/completions`
answered the same prompt correctly (`391`). The recipe now ships
`--default-chat-template-kwargs '{"enable_thinking": false}'`, so the default surface answers in
`content`; a caller wanting the scratchpad opts back in per request with
`chat_template_kwargs {"enable_thinking": true}`. **Do not measure this lane without that knob** —
and record the `finish_reason` + `reasoning` histogram beside any score (repo rule G3/G4).

## Qwen3.8-27B — what the numbers mean

- **The model is dense, so it is a streaming-bandwidth problem, not a gather problem.** 64 layers = 48
  GDN (linear-attention) + 16 full-attention, no experts. Every weight is read every token:
  **17,608 MB/token** of weights, against ~**221 GB/s** effective read → a plain-decode ceiling of
  **~14 tok/s** at TP=1 (`VERIFIED`). Every published throughput is that ceiling times speculative
  amplification (`tok/s ≈ A_eff × BW / B_token`).
- **Speculative decoding is where the speed is.** The DFLASH2 draft raises decode to **33.8 t/s** at
  block 8 (d=0, c=1). Block 8 vs block 4 is **+22.5 %** ([1.188, 1.262]), pooled over 24 boots — the
  recipe ships block 8 because the draft was *trained* at 8.
- **`max_num_seqs: 48` in the recipe is a deliberate artifact.** The mamba/GDN state pool silently
  clamps it to **21** on a fresh container (`K=85`) — the clamp is logged, not an error. Read the grant
  from the server log (`grep -F 'capped to'`) rather than trusting the literal.
- **Long context costs decode.** At `c=8`, depth above ~8k is **~20 %** slower (congested/pool-limited;
  boot-level 8–29 %); uncongested at `c=4` the cost is **~11 %**. Do not quote a KV-bandwidth figure
  (four were retracted).
- **`mamba_ssm_dtype: bfloat16` doubles granted concurrency** (21 vs the checkpoint's declared
  `float32`'s 10) and is bit-identical on the state-read path. This is a deliberate override of the
  checkpoint; see [`AGENTS.md`](AGENTS.md) §4. Do not "restore float32 for safety".

## Notes

- **Evidence docs are archived** at [`attic/qwen3/`](../../attic/qwen3/) (2026-10-11; manifest in the
  same directory — search `ANSWERED-QUEUES.md` by profile name before running anything).
- **Guards:** `tests/test_qwen3_vl_embeddings.py` covers the moved VL recipes in the
  `embed`/`rerank` lanes; `tests/test_qwen3_recipes.py` guards the TensorFold arm (engine identity,
  digest pin, drafter, served id). The lane's SGLang arms are covered by
  `tests/test_recipe_placeholder_resolution.py` (served-name rebinding, inert defaults).
- **Raising a bug upstream?** Name the pinned container commit you read and cite `file.py:line`
  (`AGENTS.md` and the archived docs do this throughout).

<!-- Links -->
[RadixArk/Qwen3.8-27B-NVFP4]: https://huggingface.co/RadixArk/Qwen3.8-27B-NVFP4
[incoai/Qwen3.8-27B-DFlash2]: https://huggingface.co/incoai/Qwen3.8-27B-DFlash2
[Intel/Qwen3-Coder-Next-int4-AutoRound]: https://huggingface.co/Intel/Qwen3-Coder-Next-int4-AutoRound

[TensorFold/Qwen3.8-27B-MLX-4bit]: https://huggingface.co/TensorFold/Qwen3.8-27B-MLX-4bit
[z-lab/Qwen3.8-27B-DFlash2]: https://huggingface.co/z-lab/Qwen3.8-27B-DFlash2

## Recipe comment archive (2026-10-14)

Verbatim `#` comments removed from the lane's shipped recipes on 2026-10-14 under the owner rule that a
shipped recipe carries only comments crucial to a surprising/novel/confusing property of *that* recipe
(everything else lives in this file or in `recipes/qwen3/README.md`). Organised per recipe filename.
Anything an operator would get WRONG without was KEPT in the YAML; the rest is below.

### qwen3.8-27b-nvfp4-dflash2-sglang.yaml

Above `kv_dtype: fp8_e4m3`:

```
# sglang's --help says "auto will use model data type", which would suggest bf16, but
# for this checkpoint auto resolves to fp8_e4m3 because mem_cache/kv_cache_dtype.py
# checks the parsed quant config's kv_cache_quant_algo first and this hf_quant_config
# ships "kv_cache_quant_algo": "FP8". Reading the docstring alone produced a wrong
# metadata value here once already; read the allocation line.
```

Above `tags: lcg_favorite, fast, vision`:

```
# vision: Qwen3.5 multimodal checkpoint (image-text-to-text; config carries a vision_config).
```

Above `max_num_seqs: 48` (the clamp fact is kept in the recipe, trimmed):

```
# NOT the granted concurrency. MEASURED on hardware 2026-09-19: the mamba state pool
# silently clamps this (mem_cache/kv_cache_configurator.py:2177-2193) -- read the grant
# from the server log (`capped to 21`, K=85), never from this literal. Details and the
# 26-slot ceiling are in AGENTS.md section 4.
```

Above `mamba_full_memory_ratio: 3.51`:

```
# How the leftover pool splits between GDN state and the token pool. THIS IS THE
# HIGH-LEVERAGE KNOB on this recipe, and it is context-length dependent.
# Usable long-context concurrency is min(granted slots, #tokens // context_length),
# NOT #tokens // context_length: raising the ratio buys slots by spending tokens and
# lowering it does the reverse, so the optimum is an interior point that MOVES with
# context length (modelled at D=8, T~25 GiB: ~3.6 at 4k, ~2.3 at 8k, ~1.2 at 16k).
# DELIBERATELY STILL 3.51: flipping it is a claim about expected traffic shape, not a
# free win (2.3 gives up capacity headroom near 4k), and this recipe has no stated
# target traffic mix. The evidence is not the blocker; ask before changing it -- the
# measured 8k/16k trade is tabulated in AGENTS.md section 5.
```

Above `mamba_ssm_dtype: bfloat16`:

```
# CHECKPOINT-DERIVED and load-bearing -- do not "restore float32 for numerical
# safety": the override DOUBLES the granted concurrency (bfloat16 -> "capped to 21",
# max_mamba_cache_size=85; float32 -> "capped to 10", K=42) and is bit-identical to
# float32 on the state-read path. Evidence and its untested limits: AGENTS.md section 4.
```

Above `mamba_radix_cache_strategy: extra_buffer_lazy`:

```
# Reuse behaviour of this strategy is non-obvious and cost a wasted session:
# under extra_buffer_lazy, cached_tokens GROWS with the number of times the server has
# seen the prefix (measured ladder, flushed first, 128-token prefix: 1 absorb -> 0,
# 2 -> 64, 3 -> 64, 4 -> 128 = full reuse; a 64-token prefix needs 3 absorbs). Two
# consequences: (1) any warm-up that needs the kernel to READ stored state must absorb
# the shared prefix several times, not once -- a single absorb yields cached=0 and any
# such probe is blind; (2) `prefix_caching: true` in a benchmark does NOT mean prefixes
# are shared on the first pass, so early runs of a sweep see less sharing than the
# setting implies. Consequences and reasons: AGENTS.md section 4.
```

Above `kv_cache_dtype: auto`:

```
# Left at 'auto' rather than spelled fp8_e4m3 so the checkpoint keeps ownership of the
# KV dtype: auto resolves to fp8_e4m3 today (see metadata.kv_dtype) *because* the
# checkpoint says so, and pinning the string here would silently diverge from the
# checkpoint if it were ever re-quantised. Passing auto explicitly is identical to the
# previous behaviour, where the flag was commented out entirely.
```

Above `chunked_prefill_size: 4096`:

```
# Scheduler token budget per prefill batch -- NOT related to draft length. The previous
# comment here ("Max new tokens for incoai/Qwen3.8-27B-DFlash2") was FALSE and is refuted:
# DFLASH block size *is* speculative_draft_tokens below, and `grep chunked_prefill_size`
# over arg_groups/speculative_hook.py returns nothing, so the two are uncoupled in that
# direction. The only real coupling runs the other way --
# arg_groups/mamba_hook.py:119-120 asserts mamba_track_interval >= speculative_num_draft_tokens.
# 4096 is safe for the mamba extra-buffer path (VERIFIED): the warning at
# arg_groups/mamba_hook.py:129-140 fires only when chunked_prefill_size <
# mamba_cache_chunk_size, which resolves to max(64, page_size) = 64 here
# (arg_groups/overrides.py:1888-1897). Note raising it cannot speed up GDN -- that path's
# internal chunk is fixed at 64 and is not derived from this value (AGENTS.md section 4).
```

Above `speculative_draft_tokens: 8`:

```
# 8, not 4. The draft checkpoint declares dflash_config.block_size = 8, and
# arg_groups/speculative_hook.py only infers that value when
# speculative_num_draft_tokens is LEFT UNSET; passing any number wins silently, with
# no warning, so this recipe was running the draft at half its trained block size.
# Do not raise this past 8: 8 is what the draft was trained for, and DFLASH's
# block_size mismatch guard only fires when both flags are set explicitly.
```

Above `extra_args: ""`:

```
# Escape hatch for one-off experimentation, mirroring the qwen4 recipes.  Appended
# last so argparse resolves a repeated flag in favour of the override.  Empty
# string is the no-op default; quoted so YAML keeps it a str.
```

### qwen3-coder-next-int4-autoround-vllm.yaml

Above `default_chat_template_kwargs` (the empty-`content` trap; the mechanism is kept in the recipe,
trimmed):

```
# Native thinking ON leaves a short reply inside the reasoning channel with
# `content: null` (measured 2026-10-11: a 4-token answer to "17*23?" came
# back as `reasoning: '391'`, `content: None`), which every client that
# reads `content` sees as an empty reply. Default it OFF so the served
# surface is usable; a client that wants the scratchpad passes
# chat_template_kwargs {"enable_thinking": true} per request.
```

### qwen3.8-27b-mlx4bit-tensorfold-sglang.yaml

Above `model_revision:`:

```
# Pinned for distribution determinism (a SHA download writes no refs/ entry). This
# engine has no revision flag: {model} reaches it as the prepared snapshot *path*,
# so the pin governs which bytes are downloaded, not a serve argument.
```

Above `executor_config:`:

```
# The image inherits the NVIDIA PyTorch base's ENTRYPOINT
# (/opt/nvidia/nvidia_entrypoint.sh, read from the pinned image's config); clear it
# so the recipe's own serve line runs instead of being appended to the entrypoint.
```

Above `TORCH_EXTENSIONS_DIR`:

```
# The image bakes TORCH_EXTENSIONS_DIR=/cache/torch_extensions, but /cache is a
# mount parent docker creates as root and sparkrun runs the container as the
# invoking uid — the TensorFold kernels (torch cpp_extension, no build_directory
# of its own) cannot create it. Point it at sparkrun's persistent, user-owned
# runtime cache: the sm_121a compile is then paid once a node, not once a boot.
# (Triton's cache needs no line here: the sglang runtime already places it in that mount.)
```

Above `TENSORFOLD_NO_UPDATE_CHECK: '1'`:

```
# The engine's update check writes into HOME and calls GitHub; the upstream serving line disables it.
```

Above `TENSORFOLD_KV_DTYPE` / `TENSORFOLD_MEMORY_RESERVE_GIB`:

```
# Upstream's serving settings: the FP8 attention cache (patch 0003; opt-in in the
# engine, 32 KiB a token instead of 64) and a 0 GiB startup reserve (patch 0004;
# TensorFold's own default is a tenth of RAM). Raise the reserve if the node is shared.
```

Above `parallel: 8`:

```
# Streams decoded together. Upstream measures no single-request cost up to 8.
```

Above `speculative_draft_model`:

```
# The DFlash2 drafter is a second repo: sparkrun's sglang draft hook adds it to the
# distribution set, and the engine serves it from the cache. Its own revision is a
# distribution-only key — TensorFold has no revision flag to render it into.
```

The `command:` served-name comment (KEPT truncated in the recipe; full text here):

```
# A REAL LAUNCH FAILURE, AND WHY THIS LINE IS HERE: sparkrun appends its own --served-model-name
# to any command template that declares served_model_name
# (runtimes/base.py::_augment_served_model_name), and this engine parses no such flag: the
# first boot died with tensorfold: error: unrecognized arguments: --served-model-name Qwen3.8-27B.
# That helper skips the append when the flag text is already in the rendered command, and the
# serve command runs as a bash script, so naming the flag in this comment both skips the append
# and would be swallowed by the shell if sparkrun ever appended anyway. The id reaches the
# engine through --name above.
```

Above `port_timeout_s: 3600`:

```
# The first boot builds the sm_121a CUDA extensions and loads ~19 GB of weights before the
# port opens; that was 71.5 s on a warm node, so 3600 s is generous headroom for a cold one.
```
