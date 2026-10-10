# Qwen3 — `recipes/qwen3/` agent & developer guide

**RadixArk/Qwen3.8-27B-NVFP4** on a single NVIDIA DGX Spark (GB10, SM121, 128 GB unified
LPDDR5X), TP=1, SGLang. Read this before touching a recipe in this directory, its mods, or the
guards. It was created 2026-10-10 to absorb the measurement history that had accumulated in the
recipe comments; the recipes now carry only non-obvious-tunable notes.

**Scope of this directory.** Three shipped recipes off one checkpoint, plus one unrelated vLLM
coder model:

| recipe | role |
|---|---|
| `qwen3.8-27b-nvfp4-dflash2-sglang.yaml` | **shipping** — DFLASH2 spec decode, block 8 |
| `qwen3.8-27b-nvfp4-nospec-control-sglang.yaml` | **control only** — same bytes, no `--speculative-*`; supplies the plain-decode denominator. Not for serving. |
| `qwen3.8-27b-nvfp4-dspark-sglang.yaml` | **documented arm** — the DSpark draft path; measured and **rejected** as an upgrade (§7) |
| `qwen3-coder-next-int4-autoround-vllm.yaml` | a different family (Intel/Qwen3-Coder-Next, vLLM) sharing the lane dir only |

The four **Qwen3-VL embedding/reranking** recipes moved to their own lanes on 2026-10-10:
[`recipes/embed/`](../embed/README.md) and [`recipes/rerank/`](../rerank/README.md); the guard
`tests/test_qwen3_vl_embeddings.py` reads those lanes, **not** the four files above.

> **Reading order for a new agent:** this file → [`NOTES.md`](NOTES.md) (current state, action plan,
> constraints) → `COOP.md` (live node/bench claims, untracked) → [`README.md`](README.md) (the
> human-facing recipe summary) → the `§N` section named next to your workstream. Do **not** re-read
> the WORK/DEPTH docs front-to-back — `QWEN3-MODEL-OPTIMIZATION-WORK.md` is ~3,300 lines and
> `DEPTH-COST.md` ~3,800, both written for targeted lookup.

**Evidence vocabulary (repo convention).** **VERIFIED** — read from a primary artifact (a boot log,
a pinned image, source at a pinned commit) or measured on our devices. **LIKELY** — strong secondary
evidence. **SPECULATIVE** — reasoning without a source; do not build on it. Never promote `LIKELY`
into unlabelled fact, and never write a confident unsourced sentence — that is a defect. **Many
numbers in the docs were retracted**; check a section's retraction banner before quoting it.

**Tracked = shipped to nodes and third parties.** Internal IPs and hostnames stay out of tracked
files (this file included) — refer to nodes by role (`the free pair`, `node-free-N`) or by a
bench id, never by octet.

---

## 1. Mission and current state

Produce and defend the highest-quality, highest-throughput `sparkrun` recipe for the RadixArk
Qwen3.8-27B checkpoint on a **single** DGX Spark (TP=1).

**Best measured state** (`VERIFIED` unless noted; sources in the WORK doc):

| quantity | value | note |
|---|---|---|
| plain decode (no-spec, d=0, c=1) | **12.56 ± 0.02 tok/s** | 10 runs / 2 containers; ±0.25 % across boots |
| shipping decode (block 8, d=0, c=1) | **33.76 tok/s** | absolute is the reference; the *ratio* is not |
| block 8 vs block 4 | **+22.5 %** (95 % CI [1.188, 1.262]) | pooled over 3 same-node interleaved phases, 24 boots |
| granted concurrency | **21** (`K=85`) at `D=8`, fresh container | not the requested 48; ceiling 26 at any ratio |
| implied weight bandwidth | **221 GB/s** | = 17.608 GB × 12.56 tok/s |
| accepted tokens/step `A_eff` | **3.265** pooled (1,481 log lines); 3.99 is a single probe | quote 3.265 for capacity math |
| c=8 depth cost (8k→) | **~20 %** (boot-level 8–29 %) | congested/pool-limited; uncongested c=4 is **~11 %** |

---

## 2. Where the evidence lives

| artifact | location | tracked? | cite form |
|---|---|---|---|
| Decision record (current answer + open queue) | `QWEN3-MODEL-OPTIMIZATION-WORK.md` | no (git-ignored) | `WORK §N` |
| Depth-cost thread | `DEPTH-COST.md` | **yes** | `DEPTH-COST §12.NN` |
| SSM/gdn dtype thread | `SSM-STATE-DTYPE.md` | **yes** | `SSM §12.NN` |
| Answered queues (search by PROFILE name before re-running) | `ANSWERED-QUEUES.md` | **yes** | `AQ item N` |
| Narrative log | `JOURNAL.md` | no (git-ignored) | — |
| Qwen3-VL embeddings work | `QWEN3-EMBED-OPTIMIZATION-WORK.md` | no (git-ignored) | `EMBED §N` |
| Coordination ledger (live) | `COOP.md` | **no — never `git add`** | — |
| Benchmark profiles | `benchmarking/*.yaml`; dead arms in `attic/benchmarking/` | yes | profile filename |
| Bench results | `~/.cache/sparkrun/benchmarks/bench_<id>/` on head | scratch (reaped) | `bench_*` id |
| Scratch drivers/analyzers | `.scratch/qwen3-27b/` (~269 files) | no (git info/exclude) | `file:line` |

**A result has no provenance without its `bench_*` id**, and a boot's config comes from **that boot's**
`state.yaml`, never a sibling's or from memory. Cite `bench_*` + `§N`, never the printed sparkrun table.

---

## 3. Hard constraints and traps

1. **Node allowlist.** The free pair is the benchmark target; the head and the restricted nodes serve
   the DS4 job. Concrete addresses live in `COOP.md` (untracked); re-check it each session and
   re-resolve hostnames before acting.
2. **The head is the run-from host.** Run recipes **by name** from `$WOPR_RUN_FROM_DIR` with `mods`
   symlinked in; running by absolute path breaks `mods/<name>` resolution.
3. **One boot/arm at a time** on the free pair. Co-resident jobs recreate each other's containers.
4. **`-o` overrides `defaults:` only through a consumed `{placeholder}`.** Verify on the rendered line
   (`sparkrun run <recipe> -H <node> -n`), then on the live argv for load-bearing flags.
5. **Mods run as root** in the persisted runtime cache; reown anything under `/cache/runtime` to
   `stat -c '%u' /cache/runtime`, or later launches die with a root-owned `PermissionError`. Never
   `import sglang` from a `pre_exec` mod (flashinfer JIT writes root-owned files).
6. **This tree is syncthing-shared with a live second writer.** Never `git add -A`, directory adds,
   or bare globs. Use explicit pathspecs and review `git diff --cached --stat`.
7. **Mods fail closed**; a launch log is not the server log — the crash text lives in the container.
8. **`sparkrun show/run <name>` off the sandbox registry cache can lie** (stale clone). Validate a
   recipe **by path**; `sparkrun recipe validate <path>` reads the file directly and is correct.

---

## 4. The model in one paragraph

The checkpoint is a **dense hybrid, not an MoE**: 64 layers = 48 GDN (linear-attention) + 16
full-attention, no experts (WORK §1). Every weight is read on every token, so this is a
**streaming-bandwidth problem, not a gather problem**: 17,608 MB/token of weights against ~221 GB/s
effective read predicts a plain-decode ceiling of **~14 tok/s at TP=1**. Every published throughput
is that ceiling times speculative amplification:

```
tok/s ≈ A_eff × BW / B_token        A_eff = accepted tokens per verify step
```

Consequence: a benchmark alone cannot say how much of a speed-up came from better bandwidth use vs.
simply accepting more draft tokens per step — which is why the **no-spec control** recipe exists
(§6).

---

## 5. The knobs — why each value is what it is

Every fact below was previously a comment in `qwen3.8-27b-nvfp4-dflash2-sglang.yaml`. The recipe
now keeps only the one-line note beside the value; the history lives here.

### 5.1 `max_num_seqs: 48` — granted concurrency is ~21, not 48

**The mamba/GDN state pool silently clamps this** (`mem_cache/kv_cache_configurator.py:2177-2193`);
the clamp is logged, not an error. Measured (WORK §12.8): over every archived boot log, **26 distinct
boots logged `capped to 21` (K=85/86) and exactly one logged `capped to 20` (K=82** — phase 9's first
`--fresh` boot, bottom-up T=24.31 GiB, just under the ~24.50 GiB boundary where `floor()` drops a
slot). So **21 is the value to quote**; 20 is the one-observation low-T outlier. An earlier revision
of the recipe asserted "capped to 20" as THE measured value, which is why WORK's headline and the
comment disagreed — both numbers are honest observations, but only one is typical.

Counting method (so it reproduces): boots are identified by their `avail mem` trajectory, **not** by
log-file name (one boot is copied into many files; deduping on `(cap,K)` instead collapses genuinely
distinct boots — that mistake undercounted 26 as 3). The grant moves by **one slot with T**, and T is
node state, so always read it per boot: `grep -F 'capped to' <serve log>` — that warning's first
field *is* the granted `max_running_requests` (`kv_cache_configurator.py:2183-2192`). Do not reach
for the `[unified-memory-pool]` line: it is gated on `--enable-unified-memory` (default off, and its
help excludes speculative decoding — `mem_cache/unified_memory_pool.py:1379-1387`,
`server_args.py:888-896`), so it cannot appear here.

**Effective ceiling is ~21, not 48; it CANNOT reach 48 while `speculative_draft_tokens=8`, at any
`mamba_full_memory_ratio`.** The binding term is the D-proportional verify scratch
(`p·(K+1)·(1+D/R) + p·(capped+1)·D`); lifting the ratio to fund 192 slots starves the KV pool instead
(at D=8, the `r→∞` ceiling is 26; 3.51→12 buys ~3 slots and costs ~60 % of the token pool — WORK
§12.3, §12.8). The "cannot reach 48" part is **node state, not recipe state**: it holds while the
leftover pool T < 42.74 GiB (bottom-up T measured 24.3–25.3 GiB; do **not** invert another config's
`#tokens` line, which got this wrong once — WORK §12.2bis). A less-loaded node can clear the bound.
If the grep ever shows `max_num_reqs=48`, this section is wrong and WORK §12.3 is refuted — say so
there rather than editing the recipe. **Deliberately left at 48**: harmless, and changing it would
hide the very discrepancy that needs measuring.

### 5.2 `mamba_full_memory_ratio: 3.51` — the high-leverage knob, left deliberately

How the leftover pool splits between GDN state and the token pool. **This is the highest-leverage
knob on this recipe, and it is context-length dependent.** Usable long-context concurrency is
`min(granted slots, #tokens // context_length)`, **not** `#tokens // context_length`: raising the
ratio buys slots by spending tokens and lowering it does the reverse, so the optimum is an interior
point that **moves with context length** (modelled at D=8, T~25 GiB: ~3.6 at 4k, ~2.3 at 8k, ~1.2 at
16k).

**Measured at depth 8192 on GB10, 8 boots same-node interleaved** (WORK §12.9 first measurement,
§12.10 the replication):

| ratio | slots | tokens | usable 8k contexts |
|---|---|---|---|
| 3.51 | 21 | 118 k | **14** (pool-bound at 0.96 usage, ~7 slots idle) |
| 2.3 | 19 | 155 k | **18** |

Effect at c=16: usable 8k concurrency 14 → 18, aggregate decode ratio **1.386**, TTFT ratio **0.633**
(1.58× lower). **How to state this honestly:** prefill rose by the *same* ratio (1.387) and
per-request decode rose only 1.077, so the aggregate gain is mostly a shorter benchmark window (less
queueing) — the same physical effect as the TTFT win, **not a second independent win**. Do not quote
"+36 % decode AND 1.58× TTFT" as a combined benefit; it double-counts. The claim is: *more concurrent
long contexts fit, and they wait less*; decode speed per stream is essentially unchanged (a
weights-bound model, §4). The c=8 null holds at 1.008 [0.94,1.04] — neither config is
capacity-limited there, which rules out "faster node" as the explanation.

So **3.51 is near-optimal for ~4k traffic and forfeits 22 % of grantable 8k concurrency** (14 of 18
usable contexts; equivalently 2.3 is a +29 % uplift). **DELIBERATELY STILL 3.51**: flipping it is a
claim about expected traffic shape, not a free win (2.3 gives up near-4k headroom), and this recipe
has no stated target traffic mix — see WORK §6 item B. The evidence is no longer the blocker; **ask
before changing it.**

The optimum moves with L, so there is no single "long-context" value; **do NOT lower this below ~1.5
for 8k traffic** — past the crossing point the slots collapse (`cap = K//4` at D=8) and you end up
WORSE than 3.51. At 16k the crossing is ~1.2, and 0.9 is still dominated (12 usable vs 14 at
r=1.2), so "just lower it for long context" is wrong in both directions: the optimum is interior and
its location depends on L.

**CEILING vs OBSERVED — read before quoting any 16k number.** "14 usable" is
`min(cap, #tokens//depth) = min(14, 238712//16384 = 14)`, a **DERIVED CEILING**, not a measurement.
What was OBSERVED differs: phase 26 offered c=12 and peaked 12/12 (truncated by the experiment, not
by capacity), and phase 76 offered c=16 with ABBA order and peaked at 13 against the ceiling of 14.
**Quote 13 observed / 14 ceiling, never "14 measured"** — a 14.5 % claim built on the ceiling is not
a measurement (DEPTH-COST §12.51).

**At 16k this is now BOOTED, not merely modelled:** phase 26 ran r=1.2 at depth 16384 and measured
capped 14, #tokens 238,712 = 14 usable 16k contexts against 7 shipped, with 1.558× aggregate decode
at c=12 and TTFT 50.5 s → 29.2 s (WORK §12.15). At 8k the equivalent claim was measured too (18
usable at r=2.3 vs 14). Only the ~3.6-at-4k figure is still model-only.

**Measured at the benchmark's own shape** (phase 65, two nodes, mirrored arm order,
`.scratch/p65[ab]-0922`): with depth 8192 + pp 2048, so L = 10,240, the shipped 3.51 sustains
`#running-req = 11` (pool 118,002 // 10,240 = 11.5 → 11, full token usage pegged at 0.99 with **zero
retractions**) while r=1.2 sustains 13 (pool 239,298, usage only 0.57, so it is grant-bound not
pool-bound). Aggregate decode rose just **+7.4 %** (1.074 and 1.075 on the two nodes — replicated to
0.001) against +18 % streams: capacity improves and the throughput gain is **sub-linear** because the
extra streams contend. Do not quote that as "the ratio is worth 7 %": it is a capacity gain of ~2
concurrent 8k streams whose throughput conversion is small and **below the +8 % bar set before the
run**. The theory error to avoid: usable concurrency is `min(granted slots, #tokens // L)`, NOT
`#tokens // L` — cutting the ratio buys tokens by spending slots, and at D=8 slots fall fast (WORK §6
item A records the ratio-0.9 arm being dominated by shipping).

### 5.3 `mamba_ssm_dtype: bfloat16` — a deliberate override of the checkpoint

**CHECKPOINT-DERIVED and load-bearing — do not "restore float32 for numerical safety"** without
reading `SSM-STATE-DTYPE.md` §12.11/§12.12. The checkpoint declares `mamba_ssm_dtype` float32; this
recipe overrides it to bfloat16, and the override **measurably reaches the pool** (server-reported:
bfloat16 → `capped to 21`, `max_mamba_cache_size=85`, conv_state 0.24 GB; float32 → `capped to 10`,
K=42, conv_state 0.12 GB). So bfloat16 **doubles the granted concurrency (21 vs 10 slots)** —
reverting it "to be safe" surrenders 11 of 21 concurrent requests on evidence nobody has produced.

**What is measured** (WORK §12.12, 2026-09-20): bf16 vs fp32 is **bit-identical on the path that
READS the recurrent state**, not merely on prefill. Two measurements, covering different weaknesses:

- **phase 23 — FULL prefix reuse** (`cached_tokens == prefix tokens`, so the prefix is entirely
  skipped and only the stored state can carry it): 6/6 rep-pairs bit-identical, worst
  `|dlogprob| = 0.000e+00`, 0 token-id mismatches, 491 distinct logprob values per arm (so agreement
  is not a constant array), identical absorb counts in both arms (4/3/4/4) so neither recomputed more
  prefix than the other. Closes phase 22's dilution objection.
- **phase 22 — same-node three-arm pair (aged-bf16 / fresh-fp32 / fresh-bf16)**: 495/495 identical,
  and it is the run that establishes **SENSITIVITY** — its own same-node NULL (same config, different
  boot age) moved logits up to 4.27 nats on 175/495 tokens. Without that null the zero would be
  uninterpretable.

Phase 22 alone would be the weaker claim: its reuse was only **PARTIAL** (prefixes 118–187 tokens,
cached 64/128), so 40–123 prefix tokens were recomputed per request — recomputation runs at the
kernel's internal precision regardless of stored dtype, which dilutes any real stored-precision
effect. Crucially the allocation really did change in every comparison: ssm bytes per slot went
72.04 → 144.07 MiB (exactly 2.00×), so this is not a no-op.

**Why that zero is believable when phase 16's was not:** phase 16 measured PREFILL, and
`gdn_backend.py:721` sets `has_initial_states = extend_prefix_lens > 0`, so prefill only WRITES the
state buffer and never reads it — that instrument was structurally blind to the bytes under test.
Phase 22 is backed by a positive control that cost no boot (`.scratch/qwen3-27b/full_reuse_control.py`):
with the prefix FULLY cached vs cold, the same scored logits differ by 1.0–5.1 nats. So the read path
is live and sensitive at the 1-nat level, and it still reported zero for a 2× change in stored
precision.

**What the zero still does NOT license:** "bf16 is safe" full stop. Untested: state accumulated over
long distances (the control used 64–128 token prefixes), free-running generation (everything here is
teacher-forced), and any downstream quality metric — WORK §6 item C. "Undetectable by an instrument
with 1-nat sensitivity on a 128-token prefix" is the accurate claim.

### 5.4 `mamba_radix_cache_strategy: extra_buffer_lazy`

The reuse behaviour is non-obvious and cost a wasted session: under `extra_buffer_lazy`,
`cached_tokens` **GROWS with the number of times the server has seen the prefix** (measured ladder,
flushed first, 128-token prefix: 1 absorb → 0, 2 → 64, 3 → 64, 4 → 128 = full reuse; a 64-token
prefix needs 3 absorbs). Two consequences: (1) any warm-up that needs the kernel to READ stored state
must absorb the shared prefix **several** times, not once — a single absorb yields `cached=0` and any
such probe is blind; (2) `prefix_caching: true` in a benchmark does **not** mean prefixes are shared
on the first pass, so early runs of a sweep see less sharing than the setting implies. See WORK §12.12.

### 5.5 `speculative_draft_tokens: 8` — block size, and the +22.5 % claim

**8, not 4.** The draft checkpoint declares `dflash_config.block_size = 8`, and
`arg_groups/speculative_hook.py` only infers that value when `speculative_num_draft_tokens` is **LEFT
UNSET**; passing any number wins silently, with no warning, so this recipe was running the draft at
**half its trained block size**.

Measured on a GB10 node, decode-triage profile (d=0, c=1), n=5 per arm against 3 byte-identical
controls:

| arm | decode | ratio | 95 % CI |
|---|---|---|---|
| block 4 | 26.16 tok/s mean | — | (control pool, spread 21.2–30.2) |
| block 6 | 29.80 tok/s | 1.139 | [1.078, 1.210] |
| block 8 | 33.76 tok/s | 1.290 | [1.180, 1.401] |

Those arms ran in a DIFFERENT PHASE from their controls (the design flaw WORK §3 documents).
Re-measured same-node INTERLEAVED (b4 b8 b4 b8 per node, mirrored across two nodes, `--fresh` per
boot, 8 boots, all 8 passing a gate that checks the draft-token count the SERVER LOGGED):
**block 8 / block 4 = 1.213, boot-level 95 % CI [1.156, 1.279]**. The change is CONFIRMED but the
honest magnitude is well below +29 %.

**UPDATE (2026-09-23): the +21 % is SUPERSEDED, not wrong** — it predates two further same-node
phases. Recompute that phase from its own driver logs and you get 1.2218 (ratio of arm means),
1.2226 (mean of per-occurrence pair ratios), 1.2471 (ratio of arm medians). The **pooled figure
across three same-node interleaved phases (24 boots) is +22.5 %**, boot-level CI [1.188, 1.262];
WORK TL;DR item 4 is authoritative. **Quote +22.5 %.** The paired design is the one to quote because
removing phase drift shrinks the estimate. Per-node pair ratios differed by ~10 % (recomputed 1.274
and 1.171; n=2 per arm per node, so the ~10 % spread is the finding and ±3 % of it is n=2 wobble) —
on this recipe a non-paired design is dominated by which node ran which arm.

**ESTIMATOR WARNING:** ratio-of-MEANS gives 1.222, ratio-of-MEDIANS 1.247 — a 2 % spread, the size of
effect several claims here turn on. Quote a ratio with its estimator or it is ambiguous.

**Acceptance probes** (`.scratch/.../probe_accept.py`): `A_eff 3.99`, acceptance rate 0.429 over
1792 tokens / 449 verify steps — a **SINGLE-PROBE value on one server**. The only estimate pooling
across boots is **3.265** (1,481 serve-log accept-len lines). The two are unreconciled — a corpus
effect of the size WORK §3 measured (+28 % synthetic vs natural) could account for the whole gap. Do
**not** use 3.99 for capacity/headroom arithmetic; see WORK §10, which also explains why "satisfies
the identity to 0.5 %" validated nothing.

**Do not raise this past 8:** 8 is what the draft was trained for, and DFLASH's block_size mismatch
guard only fires when both flags are set explicitly.

### 5.6 `kv_cache_dtype: auto`

Left at `auto` rather than spelled `fp8_e4m3` so the **checkpoint keeps ownership of the KV dtype**.
`metadata.kv_dtype: fp8_e4m3` describes the *shipping* configuration and is **VERIFIED from the
server's own allocation line**, not inferred from `--help`:

```
KV Cache is allocated. dtype: torch.float8_e4m3fn, #tokens: 117125,
                     K size: 1.79 GB, V size: 1.79 GB
```

(measured 2026-09-19 on a DFLASH boot, WORK §12.8; the fp8_e4m3 dtype re-confirmed on six more boots
since). An earlier revision of the comment quoted `#tokens: 268343, K 4.09 GB` — a real line, but
from the **NO-SPEC control**, which buys tokens ~1.8× more cheaply. **Do not quote a `#tokens` line
across configs.**

`--help` says "auto will use model data type" (which would suggest bf16), but for this checkpoint
auto resolves to fp8_e4m3 because `mem_cache/kv_cache_dtype.py` checks the parsed quant config's
`kv_cache_quant_algo` first and this `hf_quant_config` ships `"kv_cache_quant_algo": "FP8"`. Reading
the docstring alone produced a wrong metadata value here once already; read the allocation line.
Pinning the string in the recipe would silently diverge from the checkpoint if it were ever
re-quantised; passing `auto` explicitly is identical to the previous behaviour where the flag was
commented out entirely. The flag is wired through with an explicit default (rather than living in a
trailing comment) so the metadata and the command cannot drift apart again.

### 5.7 `chunked_prefill_size: 4096`

Scheduler token budget per prefill batch — **NOT related to draft length**. A previous comment here
("Max new tokens for incoai/Qwen3.8-27B-DFlash2") was **FALSE and is refuted**: DFLASH block size
*is* `speculative_draft_tokens`, and `grep chunked_prefill_size` over
`arg_groups/speculative_hook.py` returns nothing, so the two are uncoupled in that direction. The
only real coupling runs the other way — `arg_groups/mamba_hook.py:119-120` asserts
`mamba_track_interval >= speculative_num_draft_tokens`.

4096 is safe for the mamba extra-buffer path (VERIFIED): the warning at
`arg_groups/mamba_hook.py:129-140` fires only when `chunked_prefill_size < mamba_cache_chunk_size`,
which resolves to `max(64, page_size) = 64` here (`arg_groups/overrides.py:1888-1897`). Raising it
cannot speed up GDN — that path's internal chunk is fixed at 64 and is not derived from this value
(WORK §12.7).

### 5.8 `speculative_draft_model: incoai/Qwen3.8-27B-DFlash2`

`incoai` and `z-lab` are the **SAME weights**: both HF caches resolve `model.safetensors` to blob
`67fc76d68dc5a9415511a4f394ef744d67510cd20e93b37cc2cc7d28e4bab65c`, 3,848,817,896 bytes, verified
with `stat` on the blobs the snapshots point at (2026-09-18, a free node). Only the revision pointers
differ. A draft-provider A/B therefore **cannot measure anything**, and switching provider is a
cosmetic change — **do not spend an arm on it** (also `AQ`/WORK §5, NOTES §4).

### 5.9 `extra_args: ""`

The escape hatch for one-off experimentation, mirroring the qwen4 recipes. Appended **last** in the
command so argparse resolves a repeated flag in favour of the override; quoted so YAML keeps it a
`str`; empty string is the no-op default.

---

## 6. The no-spec control recipe

`qwen3.8-27b-nvfp4-nospec-control-sglang.yaml` is **not a shipping recipe** — it supplies the plain
decode term the DFLASH recipe cannot provide on its own.

**Why it exists.** This model is dense (64 layers, no MoE), so every weight is read on every token.
Summing safetensors headers gives **17,608 MB read per token**, which against the **246 GB/s**
streaming read measured on GB10 predicts **71.6 ms/token**, i.e. a ceiling of **~14 tok/s** for plain
decode at TP=1. The DFLASH recipe measures ~26 tok/s at block 4 and ~34 at block 8, both far above
that ceiling, so every throughput number for this model is a product (`tok/s ≈ A_eff × BW / B_token`)
and a benchmark alone cannot separate better bandwidth use from accepting more draft tokens per step.
This recipe supplies the plain-decode term, turning those numbers into a **measured `A_eff`** instead
of an inferred one.

**Falsifiable prediction stated before running it:** d=0 decode here should land near **14 tok/s**
(measured: 12.56 — see §1). If it lands materially higher, the byte model is wrong — most likely the
effective streaming bandwidth exceeds 246 GB/s, or some bytes are not read per token — and the
framing needs rebuilding, not re-tuning.

**The ratio is PART of the pairing.** `mamba_full_memory_ratio: 3.51` here is chosen to **match the
treated recipe**, not because 3.51 is optimal for a no-spec run (it is not — with no D term to fund,
this arm would sit nearer its own optimum near 1). "Optimising" the control's ratio while the treated
arm stays at 3.51 silently turns a controlled comparison into two different configurations and
destroys the only clean read on what speculation costs. **If the treated recipe's ratio changes, this
one MUST change with it.** Validate with `.scratch/qwen3-27b/validate_recipes.py`, which diffs the two
commands and fails if they ever differ outside `--speculative-*` flags. **The command is
byte-identical to the DFLASH recipe's minus the three `--speculative-*` flags** — do not "tidy"
anything else there; every difference is a confound in the one number this recipe exists to produce.

**Granted concurrency is 48 here vs 21 on the DFLASH recipe** (MEASURED 2026-09-19, WORK §12.8): this
boot logs `Mamba Cache is allocated. max_mamba_cache_size: 389 (#tokens: 267301)` with **no** "capped
to" warning, so `max_running_requests` stays 48. That is the point of the control: with no speculative
draft there is no `(1+D)` reservation and no D-proportional verify scratch, so K reaches
~budget/p and the mamba cap (`K//4 = 97`) sits far above 48 and cannot bind. The DFLASH recipe at the
same ratio gets K=85 / capped 21. So the two recipes differ in **granted concurrency (48 vs 21)**
while their command text looks clean — **do not run a spec-vs-nospec comparison above c=21 without
accounting for this.**

**Mods are the same as the DFLASH recipe, deliberately** — every byte this recipe loads must match
the arm it controls for; a mod difference would make the control's load path a second variable.
`mods/fix-sglang-spec-metrics-empty-verify` is NOT mounted: with no `--speculative-algorithm` flag at
all, `get_spec().speculative_algorithm` is `None`, the spec-metric gate is falsy, and the upstream
`IndexError` is never reached. **Do not set `speculative_algorithm: NONE`** on this recipe — that
string is truthy where `None` is falsy, which routes a no-spec server into spec-decode metrics and
crashes it (see that mod). Omit the flags instead.

---

## 7. The DSPARK arm — measured and REJECTED

`qwen3.8-27b-nvfp4-dspark-sglang.yaml` exists because the lane's WORK doc concluded "the lever that
remains is the draft model, not the flag" / "anything above ~32 tok/s needs a better draft" (the
DFlash2 sibling ships 33.8 t/s at block 8). `RadixArk/Qwen3.8-27B-DSpark` is a SpecForge-trained
DSpark speculative decoder (1.86 B BF16, 5 full-attention layers) for exactly this NVFP4 target. Its
card (v2, updated 2026-08-29) publishes aggregate acceptance 3.43 (+26 % over its v1), C=1 throughput
3.16× (GSM8K) / 2.25× (MT-Bench) over autoregressive, beating EAGLE — **measured on GB300/H200, NOT
SM121**.

**Result (MEASURED, REJECTED 2026-10-10, decode-triage profile d=0/c=1 and d=8192/c=1, runs=5, one
free node):** 28.46 / 28.43 t/s vs the shipping DFlash2 arm's 33.76 (same profile) — a **~16 %
LOSS**. The card's numbers do not transfer to SM121/GB10, the same pattern as the ds4 gamma finding.
The DSPARK path **DOES boot** for this Qwen3_5 hybrid on GB10 (the open question, now answered), but
the draft is **not a shipping upgrade**. Receipts: `~/benchmarks/qwen3-dspark-20261010/decode-triage.{json,yaml}`.
The recipe is kept as an experimental arm; **rollback = the DFlash2 sibling**, which stays the
shipping lane.

**`speculative_num_draft_tokens: 8`, not 7.** SGLang's DSpark hook requires
`speculative_num_draft_tokens == gamma + 1` (`arg_groups/speculative_hook.py:650` raises otherwise;
captured live on the first boot 2026-10-10). The card's "gamma 7" is the window-minus-one — the same
gamma+1 semantics as ds4's DSPARK_BLOCK_SIZE. `speculative_num_steps: 1` accompanies it.

---

## 8. Negative results — do not re-derive / re-run

- **`dev-qwen38-27b-dflash2` container** — **not load-bearing.** `dev-cu13` already ships DFLASH +
  `qwen3_5.py` + `qwen3_5_mtp.py`; the commented container line changed nothing (WORK §5, `AQ`).
- **`z-lab` vs `incoai` draft A/B** — not an experiment: same blob (§5.8).
- **`kv_cache_dtype=fp8_e4m3` vs default** — not a variable: `auto` already resolves to
  `torch.float8_e4m3fn` for this checkpoint, so the explicit flag differed only in spelling (§5.6).
- **Raising `runs` to fix spec-arm variance** — the wrong remedy: the variance is *acceptance*
  variance, not measurement noise (WORK §3).
- **`--enable-linear-replayssm-spec`** — rejected; the scheduler raises
  `ValueError: --enable-linear-replayssm-spec with DSPARK/DFLASH requires a KDA (kimi_linear) model;
  got a non-KDA model` character-for-character as predicted (`kv_cache_configurator.py:1106-1114`),
  after both weight loads and before the pool was built (`AQ`).
- **The sub-4k depth bump** and **KV-bandwidth GB/s figures** — the depth-bump was a blocked-order
  artefact, and four KV-bandwidth figures were retracted (`DEPTH-COST`, NOTES §4).
- **`max_num_seqs: 48`** — never granted; the mamba pool is the ceiling (§5.1).
- **The DSPARK draft** — boots but loses ~16 % (§7).

---

## 9. Validation ritual (after every edit)

```bash
set -e
H=$PWD/.local/sparkrun-home
uv run python -m unittest discover -s tests
for f in recipes/*/*.yaml; do HOME="$H" sparkrun recipe validate "$f" >/dev/null; done
for s in mods/*/*.sh; do bash -n "$s"; done
for p in mods/*/*.py tools/*.py; do uv run python -m py_compile "$p"; done
find mods tools -name __pycache__ -type d -exec rm -rf {} +
```

Use **plain** `validate`, not `--strict` (accepted warnings exist on shipped recipes).
`py_compile` leaves untracked `__pycache__/` — clean it and **never stage it**. `recipe validate`
does **not** check mod existence; only a real launch (or `-n`, which resolves mods when a `command:`
template is present) surfaces a resolution failure.

---

## 10. References

- Checkpoint: [RadixArk/Qwen3.8-27B-NVFP4](https://huggingface.co/RadixArk/Qwen3.8-27B-NVFP4)
- Draft (DFlash2): [incoai/Qwen3.8-27B-DFlash2](https://huggingface.co/incoai/Qwen3.8-27B-DFlash2)
- Draft (DSpark, arm): [RadixArk/Qwen3.8-27B-DSpark](https://huggingface.co/RadixArk/Qwen3.8-27B-DSpark)
- vLLM coder model: [Intel/Qwen3-Coder-Next-int4-AutoRound](https://huggingface.co/Intel/Qwen3-Coder-Next-int4-AutoRound)
- Base image: [`lmsysorg/sglang:dev-cu13`](https://hub.docker.com/r/lmsysorg/sglang)
- Guard: [`tests/test_qwen3_vl_embeddings.py`](../../tests/test_qwen3_vl_embeddings.py) (covers the
  embed/rerank lanes, not this directory's four recipes)
- Deep narrative record: `QWEN3-MODEL-OPTIMIZATION-WORK.md`, `DEPTH-COST.md`, `SSM-STATE-DTYPE.md`,
  `ANSWERED-QUEUES.md`, `JOURNAL.md` (see §2)
