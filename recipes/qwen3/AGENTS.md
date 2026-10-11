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
  `Loading safetensors 0%`. A fix mod exists (`mods/fix-fastsafetensors-tp2-sglang`) but has never
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
- Guard: [`tests/test_qwen3_vl_embeddings.py`](../../tests/test_qwen3_vl_embeddings.py) (embed/rerank
  lanes only — there is no guard for the 27B lane yet)
- Archive: [`attic/qwen3/`](../../attic/qwen3/) (control recipe, DSpark arm, research docs, manifest)