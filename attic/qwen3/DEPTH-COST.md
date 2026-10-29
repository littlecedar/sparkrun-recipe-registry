# Qwen3.8-27b on DGX Spark — The Depth Cost Investigation

Split out of `QWEN3-MODEL-OPTIMIZATION-WORK.md` on 2026-09-22 because the depth thread had grown
into the largest single investigation in that document, and the main doc was no longer readable as a
working reference. It now holds **§12.22–12.52**, and WORK carries stubs. **This range is stated once
and is not maintained by hand** — if a new section is added here, update this line or accept that the
checker's dangling-reference pass will catch the mismatch when something cites the new number.

**No word count is stated here, deliberately.** An earlier revision of this line claimed "~21,000
words" and was stale within a day of being written (actual: ~25,300). A hand-typed count in prose is a
claim that decays silently, and this document set has now been bitten by decaying counts three separate
times — including §9's run-count, which went stale and was later quoted as if current. If a count is
needed, measure it: `wc -w recipes/qwen3/DEPTH-COST.md`.

**Sections keep their §12.N numbers.** They are cited from WORK, JOURNAL and SSM-STATE-DTYPE by
number; renumbering would have made every one of those citations dangle. WORK's §12.0 roadmap and its
Contents list point here for every §12.N in this file's range.
**The short version, for anyone about to quote a number from here.** An index, one line each, in §
order — the §-number is the only reliable chronology, because later sections supersede earlier ones and
renumbering would dangle citations from three other files. **Retractions are marked inline; treat a
section's own heading as authoritative over any summary here.** Read §12.32 before quoting any
throughput-vs-depth figure, §12.48 before quoting "~20 % depth penalty", §12.46/§12.47 before quoting
any cost model.

| § | one-line verdict |
|---|---|
| 12.22 | The `c = 8` depth gap is **real, ~20 %**, reproducible only to ±10 pp across boots. |
| 12.23 | The sub-4k "bump" was a **blocked-order artefact** — killed by a randomised-order run. Its prefill-admission term is now the leading mechanism candidate. |
| 12.27 | Revived KV **bandwidth** from `1/peak` linear in depth. **Fit used a contaminated metric — do not quote its bandwidth number** (§12.32). |
| 12.28 | Prefix-cache reuse collapses as offered load passes pool capacity. Divisor-free hit rate is the only trustworthy quantity there. |
| 12.29 | Depth cost looked like a **step**. Its headline "equal bytes" falsification is **RETRACTED** by §12.31. |
| 12.30 | A `pp`-crossed design **cannot** separate KV bytes from pool residency; the additive model is the wrong functional form. Its `A_seq = +1.3e-02 ± 2.6e-03` (5σ) **does not reproduce** — §12.52 measures it at `−1.9e-03 ± 3.8e-03`, a 3.2 σ discrepancy with the **opposite sign**. |
| 12.31 | §12.29's falsification used the **wrong regressor** — a decode step reads prompt *and* generated tokens. Retracted. |
| 12.32 | **On the server's own decode metric, no KV-bandwidth cost is detectable.** The harness metric that made bandwidth look alive was measuring **admission**. Read this before §12.23/§12.27. |
| 12.33 | `accept len` flat to 8192 then **down ~10 % at 16k**, `p = 2×10⁻⁴`. **Plausible, unreplicated, not refuted**; the failures to reproduce were ~50 %-power coin flips (§12.40). |
| 12.34 | Acceptance is **flat in batch 2→8**. Above `c ≈ 8` at long depth it is untestable on the shipped config — the pool is the ceiling. |
| 12.35 | Acceptance "tracks the prompt". **SUPERSEDED BY §12.36 — do not use its mechanism.** Its `pp`-flatness half stands. |
| 12.36 | **No within-boot acceptance effect survives replication**: the paired contrast **reverses sign** under reversed sweep order, and repeated-cell drift reaches +10.6 %. |
| 12.37 | Order-reversed depth sweep: acceptance step absent, throughput −11 %, repeated cell drifted 17 % — so neither is a verdict. Leaves the penalty without its leading mechanism. |
| 12.38 | ⚠ **RETRACTED BY §12.40** ("cannot resolve ~10 %" was false); its sign test and failed-remedy findings stand. |
| 12.39 | ⚠ **RETRACTED BY §12.40** (the added variance component double-counted noise the bootstrap already included). |
| 12.40 | §12.38 and §12.39 are both wrong from **one** error: calibrating against theory instead of the statistic's own measured null. Dissolves "within-boot drift" as an artefact of small samples. |
| 12.41 | p64's **+108 % capacity win is real but unattributable**: two factors changed at once, ~26 decode lines per arm. |
| 12.42 | p65 isolates the ratio at `D = 8`: **+7.4 % at `c = 16`, replicated on two nodes to 0.001** — a **capacity** effect, not per-stream. Streams 11 → 13. |
| 12.43 | What `depth` and `pp` actually mean in llama-benchy — **measured**, because this document had them both ways. Read before any per-cell arithmetic. |
| 12.44 | Decode speed tracks **neither** prompt length, resident tokens, nor depth alone. Reproducibility ≤ 3.6 %. Its original "two costs that saturate" framing is **superseded** by §12.45. |
| 12.45 | **Two per-step costs, and they do not saturate.** Out-of-sample prediction rejects saturation at `P = 1.000`; three composition rules remain indistinguishable, so say "not saturation", not "multiplicative". |
| 12.46 | **`c·(depth+pp)` is not the cost variable** — two cells with *identical* values differ **21.4 %**, a free control. Per token, `pp` weighs ~3× what generated tokens do. **No GB/s figure.** |
| 12.47 | §12.46 **replicates** across a boot with reversed sweep order; direction holds, **magnitude does not** (3.18× → 5.42×). Quote "about 3×", never a point estimate. |
| 12.48 | p72, cleanest axis (`pp` fixed, `c = 4`, five depths, every cell admitted its batch): no depth slope significant on either metric **at n = 5**. `tg_throughput` underpowered (48 %); `peak_throughput` an informative null at 91 % power. **With five points the 5 % critical value is 3.182, not 2.0** — using 2.0 would have manufactured a penalty. **Headline superseded by §12.49.** |
| 12.49 | p73 = the same sweep run **backwards**, same container and boot: a within-boot crossover. **Order effect measured at 3.4 %** of typical throughput. At n = 10/depth, `tg_throughput` **does** decline — **−10.9 %** over 1024→16384, exact label-permutation *p* = 0.025, *t* = −2.87 (dof 45) — while `peak_throughput` does not. So the uncongested `c = 4` depth cost is **~11 %, not ~20 % and not zero.** Also: my own over-correction (calling genuine replication "pseudo-replication"), and a guard whose trailing `\\r` destroyed a run's acceptance data. |
| 12.50 | **Recovered p73 acceptance data** (the data I had written off as lost was in a live container all along). On the same two runs: **throughput −10.9 % with depth, acceptance +0.8 %** — so acceptance is **not** the mechanism behind §12.49's decline. Acceptance is not a function of `depth` at `c = 4` (614 steady lines pooled over both orderings), though the U-shape is position-confounded and this is one boot, so §12.33 stays unrefuted. |
| 12.51 | p76: the ratio-1.2 capacity gain **reproduces on one node, ABBA** — peak `#running-req` 7 vs 13 at 16k with **0.6 %** position drift, and `min(cap, #tokens//depth)` exact on the shipped arm. **Throughput gets no admissible verdict**: the load was 94 % prefill by time, so the metric was pinned by construction. And the arm-vs-node confound this phase was built to remove **never existed** — phase 26 ran both arms on both nodes, counterbalanced. |
| 12.52 | p78, the **pool-matched pair** (`c·depth` *and* `c·(depth+pp)` both equal, batch 2×): **no detectable per-sequence step cost** — `A_seq = −1.9e-03 ± 3.8e-03` s/seq, a null, and the opposite sign to §12.30. Matches `B` and `P` exactly so `Δt = A_seq·Δc` is identified. **Also: `tg_throughput` and `peak_throughput` disagree about the SIGN of the per-stream comparison on the same boot (+3.2 % vs −6.7 %)** — quote the metric with the number. |

**Bottom line.** At **`c = 8`**, decode above ~8k context is ~20 % slower, 5/5 same sign, sd 0.028
(§12.22). That figure is **batch-specific**: §12.48 does not establish it at `c = 4`, so quoting "decode
is slower above 8k" without naming the batch regime is an overstatement. The penalty looks like a
property of the **congested, pool-limited** region, agreeing with §12.34 and §12.42 from two independent
directions. What was supposed to *explain* it — speculative acceptance (§12.33, ~13 % fewer tokens
accepted per step at 16k, `p = 2×10⁻⁴`) — is **plausible, unreplicated, and not refuted**: its test is
sound as published, and the runs that failed to reproduce it (§12.36–§12.38) sat at roughly **50 % power**
for a 10 % effect, so their disagreement with §12.33 is what coin flips look like, not evidence
(§12.40). **Settling it needs n ≈ 40–50 decode lines per cell over ≥ 2 boots** — a day of node time, not
another zero-boot reparse. §12.23's prefill-admission term (7.6:1 → 21.6:1 across depth, measured) is now
the leading candidate precisely because it does not rest on a statistic this harness cannot resolve.
**The tuning consequence has never depended on any of this**: `mamba_full_memory_ratio`, pool size and
`max_num_seqs` cannot recover acceptance on any account, while `speculative_draft_tokens` plausibly can.

## Contents

- [12.22 The c = 8 depth gap is REAL: ~20 %, but only ±10 pp across boots, and a third of it explained](#1222-the-c--8-depth-gap-is-real-20--but-only-10-pp-across-boots-and-a-third-of-it-explained)
- [12.23 Depth scaling at fixed batch: the pre-registered model fits, the bump was warm-up, and my "KV bandwidth is dead" verdict was measured at the wrong concurrency](#1223-depth-scaling-at-fixed-batch-the-pre-registered-model-fits-the-bump-was-warm-up-and-my-kv-bandwidth-is-dead-verdict-was-measured-at-the-wrong-concurrency)
- [12.27 "KV bandwidth is dead" was measured at the wrong concurrency — there IS a batch-dependent depth cost, but not the linear one claimed here](#1227-kv-bandwidth-is-dead-was-measured-at-the-wrong-concurrency--there-is-a-batch-dependent-depth-cost-but-not-the-linear-one-claimed-here)
- [12.28 Prefix-reuse collapse under pool pressure — relocated verbatim from §9 item 3](#1228-prefix-reuse-collapse-under-pool-pressure--relocated-verbatim-from-9-item-3)
- [12.29 Phase 49: the depth cost is a STEP in two variables, not a ramp — which refutes §12.27's linear form](#1229-phase-49-the-depth-cost-is-a-step-in-two-variables-not-a-ramp--which-refutes-1227s-linear-form)
- [12.30 A crossed pp design cannot separate KV bytes from pool residency — and the additive model is the wrong form](#1230-a-crossed-pp-design-cannot-separate-kv-bytes-from-pool-residency--and-the-additive-model-is-the-wrong-form)
- [12.31 The per-byte refutation in §12.29 was a wrong regressor — retracted](#1231-the-per-byte-refutation-in-1229-was-a-wrong-regressor--retracted)
- [12.32 Phase 55: the server's own decode metric finds NO KV-bandwidth cost — and the harness metric was measuring admission](#1232-phase-55-the-servers-own-decode-metric-finds-no-kv-bandwidth-cost--and-the-harness-metric-was-measuring-admission)
- [12.33 Phase 56 on the server's own decode metric: acceptance falls ~13 % from 1k to 16k — a result that does not replicate and whose test omitted a variance component (§12.37, §12.38, §12.39)](#1233-phase-56-on-the-servers-own-decode-metric-acceptance-falls-13--from-1k-to-16k--a-result-that-does-not-replicate-and-whose-test-omitted-a-variance-component-1237-1238-1239)
- [12.34 Acceptance is FLAT in batch (2→8), measured at zero boots — which retires the phase-57 experiment and the hypothesis it was built to test](#1234-acceptance-is-flat-in-batch-28-measured-at-zero-boots--which-retires-the-phase-57-experiment-and-the-hypothesis-it-was-built-to-test)
- [12.35 Acceptance tracks the prompt, not the number of tokens resident during a decode step](#1235-acceptance-tracks-the-prompt-not-the-number-of-tokens-resident-during-a-decode-step)
- [12.36 No acceptance effect survives replication: the two sweep orderings disagree in sign, and repeated-cell drift exceeds every effect](#1236-no-acceptance-effect-survives-replication-the-two-sweep-orderings-disagree-in-sign-and-repeated-cell-drift-exceeds-every-effect)
- [12.37 Order-reversed depth sweep: acceptance does not step, decode throughput falls ~11 %, and the instrument cannot resolve either](#1237-order-reversed-depth-sweep-acceptance-does-not-step-decode-throughput-falls-11--and-the-instrument-cannot-resolve-either)
- [12.38 ⚠ HEADLINE RETRACTED BY §12.40 — "cannot resolve a ~10 % effect" is false; what this section calls within-boot drift is ordinary sampling noise (its sign test and failed-remedy findings stand)](#1238--headline-retracted-by-1240--cannot-resolve-a-10--effect-is-false-what-this-section-calls-within-boot-drift-is-ordinary-sampling-noise-its-sign-test-and-failed-remedy-findings-stand)
- [12.39 ⚠ RETRACTED BY §12.40 — the "omitted variance component" double-counted noise the bootstrap already included; §12.33's p = 2×10⁻⁴ stands as published](#1239--retracted-by-1240--the-omitted-variance-component-double-counted-noise-the-bootstrap-already-included-1233s-p--210⁴-stands-as-published)
- [12.40 §12.38 and §12.39 are both wrong, from one error: I calibrated against theory instead of against the statistic's own measured null](#1240-1238-and-1239-are-both-wrong-from-one-error-i-calibrated-against-theory-instead-of-against-the-statistics-own-measured-null)
- [12.41 p64's +108 % capacity win is real but unattributable: the arms changed two factors at once, and the serve logs contain only ~26 decode lines per arm](#1241-p64s-108--capacity-win-is-real-but-unattributable-the-arms-changed-two-factors-at-once-and-the-serve-logs-contain-only-26-decode-lines-per-arm)
- [12.42 p65: the shipped ratio's capacity cost at c = 16 is +7.4 %, replicated, and it is a capacity effect — not a per-stream one](#1242-p65-the-shipped-ratios-capacity-cost-at-c--16-is-74--replicated-and-it-is-a-capacity-effect--not-a-per-stream-one)
- [12.43 What llama-benchy's depth and pp actually are — measured, because this document had them both ways](#1243-what-llama-benchys-depth-and-pp-actually-are--measured-because-this-document-had-them-both-ways)
- [12.44 p66 + p67: neither prompt length nor resident tokens prices the decode cost — there are two, and they saturate](#1244-p66--p67-neither-prompt-length-nor-resident-tokens-prices-the-decode-cost--there-are-two-and-they-saturate)
- [12.45 The depth and prompt costs do not saturate — but how they compose is not determined, and "multiplicative" was an overclaim](#1245-the-depth-and-prompt-costs-do-not-saturate--but-how-they-compose-is-not-determined-and-multiplicative-was-an-overclaim)
- [12.46 p70: c·(depth+pp) is not the cost variable — two cells with identical cost differ by 21 %, and prompt tokens weigh more than generated ones](#1246-p70-cdepthpp-is-not-the-cost-variable--two-cells-with-identical-cost-differ-by-21--and-prompt-tokens-weigh-more-than-generated-ones)
- [12.47 p71: §12.46 replicates — and the claim that survives is smaller than the one a single boot produced](#1247-p71-1246-replicates--and-the-claim-that-survives-is-smaller-than-the-one-a-single-boot-produced)
- [12.48 p72: five depths at fixed pp, and no depth slope is significant on either metric — plus a threshold error that would have manufactured one](#1248-p72-five-depths-at-fixed-pp-and-no-depth-slope-is-significant-on-either-metric--plus-a-threshold-error-that-would-have-manufactured-one)
- [12.49 p73: the same sweep run backwards — a crossover that settles what one order could not, and an over-correction of my own to go with it](#1249-p73-the-same-sweep-run-backwards--a-crossover-that-settles-what-one-order-could-not-and-an-over-correction-of-my-own-to-go-with-it)
- [12.50 The recovered p73 acceptance data: on the same two runs, throughput falls ~11 % with depth while acceptance does not — which removes acceptance as its explanation](#1250-the-recovered-p73-acceptance-data-on-the-same-two-runs-throughput-falls-11--with-depth-while-acceptance-does-not--which-removes-acceptance-as-its-explanation)
- [12.51 p76: the ratio-1.2 capacity gain reproduces on one node, ABBA — and the arm-vs-node confound the phase was built to remove never existed](#1251-p76-the-ratio-12-capacity-gain-reproduces-on-one-node-abba--and-the-arm-vs-node-confound-the-phase-was-built-to-remove-never-existed)
- [12.52 p78: the pool-matched pair says there is no detectable per-sequence step cost — and a design claim I made and then retracted in the same hour](#1252-p78-the-pool-matched-pair-says-there-is-no-detectable-per-sequence-step-cost--and-a-design-claim-i-made-and-then-retracted-in-the-same-hour)
- [12.53 p77: the 60 % decode-share gate did its job, the wall-time result is admissible, and the decomposition that "rescued" it is confounded by the mechanism under test](#1253-p77-the-60--decode-share-gate-did-its-job-the-wall-time-result-is-admissible-and-the-decomposition-that-rescued-it-is-confounded-by-the-mechanism-under-test)
- [12.54 The usable capacity bound has been wrong by the pp term since it was introduced — verified 14/14 and 0/14, and the "confirmation" was a phase error](#1254-the-usable-capacity-bound-has-been-wrong-by-the-pp-term-since-it-was-introduced--verified-1414-and-014-and-the-confirmation-was-a-phase-error)
- [12.55 The prefill admission queue rises with prompt length while the pool stays half-empty — the first depth cost in this project that is not in the decode path](#1255-the-prefill-admission-queue-rises-with-prompt-length-while-the-pool-stays-half-empty--the-first-depth-cost-in-this-project-that-is-not-in-the-decode-path)

### 12.22 The c = 8 depth gap is REAL: ~20 %, but only ±10 pp across boots, and a third of it explained

Phase 37, `attic/benchmarking/a2-d1024.yaml` + `a2-d8192.yaml`, run **alternating** on one booted server on
`node-free-2` (`--skip-run`, zero boots), `c = 8` at both depths, 5 interleaved pairs. Artifacts:
`.scratch/phases/p37-a2/`, analyzer `.scratch/qwen3-27b/analyze_phase37.py`. This closes §6 item A2, which had
sat open with two incompatible measurements (25 % and 32 %) that disagreed by more than their own noise.

**The number.** Depth 8192 costs **20.6 %** of per-stream decode throughput relative to depth 1024,
at matched `c = 8`:

| pair | 0 | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|
| gap (d8192 ÷ d1024) | 0.751 | 0.838 | 0.795 | 0.796 | 0.813 |

n = 5 pairs, median **0.794**, sd **0.028**, range [0.751, 0.838], **5/5 same sign**, exact two-sided
sign test **p = 0.0625**, 95 % CI on the mean gap [0.769, 0.824] → **depth cost 17.6 %–23.1 %**.

> **CORRECTION (2026-09-22): that CI is a WITHIN-BOOT interval and it understates the uncertainty by
> roughly 4×.** It was computed from five interleaved pairs inside **one** container, so it prices
> ordering noise but not boot-to-boot variation — which is the variance that matters for a claim about
> the configuration. Three genuinely distinct boots, each with its own d8192 ÷ d1024 gap at `c = 8`
> (confirmed distinct containers by `container_identity.py` — non-nested logs and different `#tokens`):
>
> | boot | node | ratio | d1024 | d8192 | **gap** | n |
> |---|---|---|---|---|---|---|
> | p31 | `node-free-1` | 3.51 | 102.9 | 80.8 | **0.785** | 6 |
> | p37 | `node-free-2` | 1.20 | 103.4 | 82.3 | **0.796** | 5 |
> | p49 | `node-free-1` | 3.51 | 98.3 | 84.9 | **0.864** | 3 |
>
> **Read the node column before trusting the spread.** Only p37 is on a different *node*; p31 and p49
> are two boots of the **same** machine, so their 0.079 disagreement is boot-level variation on one
> host and says nothing about node-to-node variation. All three boots are on the same image
> (`003b7b5899ed`). That makes the interval an under-estimate of total variance, not an
> over-estimate — node effects are still unmeasured here, and `capped to`/`#tokens` differ only
> trivially between p31 and p49 (118,868 vs 117,752), so the 0.079 is **not** explainable by pool
> size, which is the useful part of the comparison.
>
> Between-boot sd **0.043** (vs within-boot 0.028). Boot-level 95 % CI on the mean (n = 3, t = 4.30) =
> **[0.708, 0.921] → depth cost 8 %–29 %**. So: **the direction is solid — all three boots and all 14
> pairs put d8192 below d1024 — but the magnitude is "about 20 %, possibly as little as 8 % or as much
> as 29 %", not "20.6 % [17.6 %, 23.1 %]".** Wherever the tight interval is quoted, read the wide one.
>
> **This specifically weakens one attribution row below.** The pool-pressure exclusion rests on
> "gap unchanged (0.805 → 0.794) when the pool doubles" — a difference of **0.011**, against a
> between-boot sd of **0.043** and a disagreement of **0.079 between the two ratio-3.51 boots alone**.
> The test had no power to detect an effect of the size it claims to exclude. Correct statement:
> **pool pressure is NOT DETECTED as a driver at this cell, which is not the same as excluded.** The
> row's status should be read as "no evidence either way", and it is the only row in that table whose
> status was set by a comparison narrower than the noise floor.
>
> The general shape to watch for, and it is a standard one: **a CI computed from repeated measurements
> inside one cluster (here, one container) is not a CI for the cluster-level estimand.** Every
> same-boot design in this document inherits it, and `--skip-run` designs — the majority of the cheap
> experiments here — cannot escape it, because there is only one cluster. Report the cluster as the
> unit of replication, or say the interval is within-cluster.

**Verdict under the pre-registered rule** (in `a2-depth-gap-c8.yaml`, written before the run: real if
consistent in sign *and* > 15 %): **REAL on the p37 data**. It exceeds the ±15 % spec-arm noise floor
and no pair disagrees. But note what the sign test alone would have said — **p = 0.0625, not significant at 0.05**.
The confidence came from the *magnitude and tightness* (sd 0.028 across five interleaved pairs) plus
a replication at another pool size, not from the sign test. Stating that plainly matters because "p = 0.06"
and "real" are different claims, and the pre-registered rule did not ask for a p-value.

> **The rule's outcome does NOT survive the boot-level view.** The pre-registered threshold was
> "> 15 % cost", and of the three distinct boots, **p49 gives 13.6 % — below the threshold.** So the
> honest verdict is: **direction REAL (3/3 boots; on every boot the *maximum* d8192 value is below
> the *minimum* d1024 value — p31 94.7 < 100.5, p37 87.4 < 98.2, p49 87.7 < 95.9), magnitude NOT
> established at the pre-registered 15 % bar.** Had p49 been run before p37 rather than five days
> later, this item would have been recorded as "not real at the pre-registered threshold", which is a
> different conclusion reached by the same rule. **A pre-registered threshold is only as good as the
> unit of replication it is applied to** — applying a within-boot threshold to a config-level claim
> over-claims, and the fix is not to move the goalposts but to state the threshold's unit at the time
> of registration (e.g. "must exceed 15 % on every boot run").
>
> Two things about that evidence, stated so it is not over-read. (1) The non-overlap claim is the
> strongest available and it needs no pairing assumption, unlike a sign test on the same cells.
> (2) p31 and p49 are **not interleaved** — their d1024 and d8192 runs are separate cells, so any
> "6/6 pairs" style count on them would be counting position-matched array indices, which is
> arbitrary. Do not report a paired sign test for those two boots; report non-overlap. Only p37
> supports a genuine paired test (p = 0.0625), and p37 alone is one cluster.

**The replication that makes it credible — and it is also the negative result.** Phase 31 measured the
same cell on a different boot at `mamba_full_memory_ratio` 3.51: gap **0.805**. Phase 37 ran at ratio
1.2, which **doubles the token pool** (118,868 → 239,346 tokens) and cuts pool pressure at this cell
from 0.55 to 0.27: gap **0.794**. Halving pool pressure changed the gap by 0.011, well inside its own
spread. **So the depth cost is not pool-pressure mediated** — it is not the radix cache squeezing
things, and it survives when the cache has plenty of room. Two boots, two very different pool states,
same answer.

**What I got wrong before, and by how much.** The two prior figures were both too large: 25 % (§9's
phase-4 sweep) and 32 % (phase 31, from offered-`c` pairing). The controlled value is **≈20 %**, with
the honest interval being the **boot-level [8 %, 29 %]** rather than the within-boot
[17.6 %, 23.1 %] (see the correction above — three distinct boots give 0.785 / 0.796 / 0.864). The
32 % was inflated by pairing on *offered* concurrency, which at depth 8192 does
not correspond to a fixed number of running streams (§12.16's error, repeating); the 25 % was a
different boot with no paired control. Wherever "25–32 %" appears, read **≈20 %**.

**Three measurements of the same gap by three different instruments, and they agree.** ("Independent"
here means *independent instrument*, not independent boot — all three come from the p37 container.
Instrument-independence is worth having, but per the correction above it is not replication.)

| measure | source | gap (d8192 ÷ d1024) | implied cost |
|---|---|---|---|
| aggregate decode ÷ runs | harness `tg_throughput` | **0.794** [0.769, 0.824] | 17.6–23.1 % |
| per-stream, B-normalised | harness ÷ `max_concurrency` | 0.849 | 15.1 % |
| **server's own throughput** | sglang `gen throughput (token/s)`, B = 8, `#queue-req: 0`, `cuda graph: True` | **0.774** | 22.6 % |

The middle row is *not* a fourth opinion — it is the same JSON under a different definition, and that
ambiguity is worth naming: "per-stream" divided by the *requested* B = 8 is 0.849, while dividing by
*effective* streams (B × accept_len ÷ tok_per_stream, i.e. 5.64 vs 5.37) is 0.794. **Quote the
definition or the number is meaningless.** The third row is genuinely independent — sglang's own moving
estimate, from the server log, with no harness involved — and it brackets the harness numbers. Three
ways of measuring, all between 15 % and 23 %: the **effect is robust to the instrument**, which is more
than most claims here can say.

**Attribution: at most a fifth explained, four fifths not.** Per-stream, `step_ms` (accept_len ÷
per-stream tok/s) goes **249.9 → 301.9 ms**, an extra **52.0 ms** per decode step at depth 8192:

| candidate | measured, at matched B = 8 | share of the ≈20 % | status |
|---|---|---|---|
| **acceptance** | accept len **3.292 → 3.273** (ratio **0.994**), over the 25/28 rows that fall **inside** a p37 task window | **≈0.5 pp** | measured, depth-matched, window-restricted |
| **KV read bandwidth** | 1.88 GB extra per step → **8.5 ms** at 221 GB/s | **≈3.4 pp** | computed, not measured |
| **pool pressure / eviction** | gap unchanged (0.805 → 0.794) when the pool doubles | **≈0** | **excluded** by the replication |
| **retraction** | 2 single-request retractions in 6 h | **≈0** | excluded |
| — | — | **≈15 pp UNATTRIBUTED** | |

**A number in this table is a retraction, so it is recorded rather than deleted.** An earlier revision
of this section reported acceptance as **3.259 → 3.167 (ratio 0.972, 2.8 pp)**. That was computed by
bucketing decode rows with `#full token ≥ 100,000` for the deep arm — but at B = 8, depth 8192 gives
`#full token ≈ 8 × (8192 + 2048) = 81,920`, while **147,507 is depth 16,384**. The "deep" bucket was
the *other experiment's* traffic in the same container (this log spans p30's 16k run as well as A2's
8k run). **Retracted: acceptance moves by ≤2 %, not 2.8×10⁰ pp, and the earlier figure is wrong.** The
correct bands are 23k–28k (d1024) and 80k–88k (d8192), and the guard that now exists is
`#full token ÷ #running-req − pp ≈ depth`, which identifies the workload directly instead of trusting a
time window or a magnitude threshold.

**The honest summary is two sentences and both are needed.** *The c = 8 depth cost is real — about
20 %, robust across three instruments, and not caused by cache pressure.* *Roughly four fifths of it
has no explanation.* The largest remaining candidates are per-layer attention-KV gather cost and the
linear-attention state walk, and **I am not naming a mechanism on this evidence** — KV reads account
for 16 % of the extra step time and acceptance for about none of it. Anyone tempted to write "depth
costs 20 % because of KV reads" should notice that the number they want is 3.4 pp.

**That non-attribution is itself the useful output.** Two plausible stories — "long context slows
decode" and "speculative acceptance degrades with context" — are now *quantitatively excluded* as the
main cause, and both are the kind of claim that gets asserted without measurement. What remains is an
unexplained ~15 pp per-stream penalty at long context, which is a real cost for long-context serving
and currently has no lever attached to it.

**Methodological notes from this run, in the order they bit:**

1. **`--fresh` was mandatory and its absence was silent.** The first attempt returned 10 JSONs with 2
   distinct md5s — five "independent pairs" that were one pair re-written five times, `rc=0`, no
   warning. See §7 for the caching rule and the artifact-hash guard now at the end of the driver.
2. **Averaging across prefill and decode phases halves the apparent effect and fakes a different
   one.** Every result JSON holds two rows per cell (`is_context_prefill_phase` true/false) whose
   same-named fields differ ~2×. A version of the analyzer that mixed them reported the gap as
   **0.55** (a 45 % "cost") instead of 0.794. Filter on phase *before* aggregating, always.
3. **`n=1` was a reporting lie in my own table.** Each cell is *one* row whose `tg_throughput.values`
   holds both runs; printing `len(cells)` showed n = 1 for cells containing 2 runs — the mirror image
   of the n = 2 problem that made phase 31's 0.859 uninterpretable. The analyzer now counts runs.
4. **My sign-test helper returned p = 1.0000 for 5/5 agreement.** The binomial tail ran the wrong
   direction: `range(kmin, n+1)` instead of `range(0, kmin+1)`, so the *most* extreme outcome produced
   the least evidence. Fixed, and checked against known answers (5/5 → 0.0625, 3/5 → 1.0, 10/10 →
   0.0020). **Any statistical helper needs one known-answer case before its output is quotable** —
   this one produced a plausible-looking number and would have been cited without the check.
5. **Interleaving cancels a level shift, not a within-pair one.** Every pair ran d1024 *first*, so a
   monotone container drift would bias all five gaps the same way — and `r = +0.615` against pair index
   is uncomfortably close to that pattern. Not dismissed; recorded as the reason to treat 20.6 % as an
   upper-ish estimate. A future run should alternate the *order* within pairs, not just the depths.
6. **Depth was separated by `#full token`, not by time.** Bucketing acceptance by wall-clock window is
   how phase 16/31 comparisons silently compared mismatched workloads; `#full token` at a known
   `#running-req` identifies the workload directly (B = 8 × (depth + pp) ≈ 24.6k vs 81.9k).

**Free by-product: `usable = min(cap, #tokens // L)` continues to hold.** On this boot,
`cap = 14`, `#tokens = 239,346`, so the model says 16k contexts fit 14 and 8k contexts fit 29 — the
8k arm is limited by the *slot* grant (14), not the pool, which is exactly the regime the A2 cell needs
so that capacity cannot masquerade as a depth effect. That is why c = 8 is the right cell for this
question and why c = 16 at 8k is not (there, capacity and depth are confounded).

### 12.23 Depth scaling at fixed batch: the pre-registered model fits, the bump was warm-up, and my "KV bandwidth is dead" verdict was measured at the wrong concurrency

> **Read §12.27 and §12.32 before quoting this section's mechanism conclusion.** The heading
> originally asserted "KV bandwidth is dead as the mechanism". That verdict came from a byte count
> done at **c = 1**, the one operating point where the KV term is negligible by construction (it
> scales with batch × depth), so it was **right in conclusion and wrong in reasoning** — exactly the
> shape of mistake that gets "corrected" back into a false positive. §12.27 then revived bandwidth
> on `1/peak` being linear in depth at fixed `c = 8` (R² = 0.938), but that fit used the **harness
> `tg_throughput`**, which §12.32 shows moves 38 % when a *prefill-only* variable is swept — it was
> never measuring decode. **Phase 55 settles it properly**, sweeping `pp` alone and scoring with the
> server's own decode-only `gen throughput`: a KV step term of **0.58σ, bootstrap CI bracketing
> zero**, and bytes/step reach only ~10.7 % of device peak in the worst cell. So bandwidth is not
> binding in the decode phase at `c = 8` — with §12.32's qualifier attached (tested at `c = 8` only,
> in a regime where a bandwidth term was never going to dominate).
> What survives this section intact: the warm-up/first-cell lesson, the Q0 refutation of the sub-4k
> bump, the 0.794/0.797 same-container reproducibility (**not** a replication — see §12.23's
> correction banner), and the acceptance/pool-pressure exclusions (those were
> measured at the right operating point). What is superseded: "probably not the decode step at all".

Phase 38, `attic/benchmarking/depth-scaling-c8.yaml`, **zero boots** (`--skip-run` on the same live
container as phase 37), `c = 8`, `pp = 2048` held constant, depths 1024→12288, `runs: 2`, `--fresh`.
Artifacts: `.scratch/phases/p38-0921/`. The point of a same-boot sweep is that pool identity cannot change
underneath it — checked, `capped to 14` / `#tokens 239,346` identical before and after.

Per-stream decode t/s, harness decode-phase rows, per-run spread ≤ 0.4 % at the anchor:

| depth | per-stream t/s | ratio to d=1024 | pre-registered model | measured ÷ model |
|---|---|---|---|---|
| 1024 | 11.69 | 1.000 | 11.41 | 1.024 |
| 2048 | **12.98** | **1.111** | 11.13 | 1.167 |
| 4096 | 12.22 | 1.046 | 10.60 | 1.153 |
| 8192 | 10.42 | 0.892 | 9.68 | 1.076 |
| 12288 | 9.09 | 0.778 | 8.91 | 1.020 |

**The bump is not real, and Q0 killed it inside one zero-boot run.** Phase 38's non-monotonicity —
d2048 at **+11 %** over d1024 — was a **blocked-order artefact**. Phase 39
(`attic/benchmarking/q0-d1024.yaml` + `q0-d2048.yaml`, same container, `--skip-run`, `--fresh`, order
randomised per block by `$RANDOM`, 5 blocks; artifacts `.scratch/phases/p39-q0/`, 10/10 distinct md5s, pool
identity `capped to 14` / `#tokens 239,346` unchanged across the run):

| block | order | d1024 | d2048 | ratio |
|---|---|---|---|---|
| 1 | 2048 first | 102.0 | 95.8 | 0.939 |
| 2 | 1024 first | 104.5 | 96.4 | 0.923 |
| 3 | 1024 first | 107.3 | 98.4 | 0.917 |
| 4 | 2048 first | 102.7 | 107.0 | 1.041 |
| 5 | 1024 first | 106.7 | 99.2 | 0.929 |

**mean ratio 0.950, median 0.929, d2048 slower in 4 of 5 blocks.** Under the rule pre-registered in
the profile (REAL requires mean > 1.05 **and** ≥ 4/5 sign agreement): **NOT REAL.** Depth is monotone
decreasing, as every candidate mechanism predicted. **Do not quote a sub-4k depth bump.**

**The mechanism of the error is more useful than the error.** Q0's d1024 values (102.0–107.3, mean
104.6) sit **11.9 % above p38's d1024 anchor of 93.5** — so the "bump" was never d2048 being fast, it
was **p38's first cell being depressed**. Phase 38 ran d1024 first, immediately after a ~4-hour-old
container had served phase 37, and that anchor was low; every later cell was then compared against it.
Re-anchoring p38 on Q0's independent d1024 gives a monotone curve: 0.993 / 0.935 / **0.797** / 0.695.
**And 0.797 at d=8192 lands on phase 37's interleaved measurement of 0.794** — same container, so
read that as *reproducibility*, not replication (see the correction immediately below). It is the
reason to trust 0.794 over p38's as-run 0.892.

> **CORRECTION (2026-09-22): this sentence originally read "two experiments, different days,
> different profiles, agreeing to 0.4 %". The "different days" part is FALSE, and it was load-bearing.**
> Phases 37, 38 and 39 all ran against **one container on `node-free-2` on 2026-09-21**, verified two
> ways: the pool identity is byte-identical across all three (`capped to 14`, `#tokens: 239,346`,
> `mamba_full_memory_ratio: 1.2`), and each `serve_node-free-2.log` is a **strict subset** of the next
> (0 lines unique to the earlier file in each pair). A sglang container appends to one log for its
> whole life, so nested logs are proof of one boot — a re-boot cannot produce them. The agreement is
> still worth something (the same container reproduces the gap across three separate invocations,
> hours apart), but it does **not** show the result survives a re-boot, which is what "corroboration"
> was being used to mean. `.scratch/qwen3-27b/container_identity.py` now makes this a command.
>
> **The structural lesson, which is the reason this is worth 150 words:** `--skip-run` experiments are
> cheap *because* they reuse a live container, and reusing a live container is exactly what
> disqualifies them from corroborating one another. Zero-boot designs are the best tool in this
> project — five depths for one boot in §12.23 — and they **cannot replicate anything**. Phase numbers,
> filenames, dates and differing profile names all say "separate experiment"; only the log body knows.
> Note the contrast with §12.22's genuine replication (phase 31 on `node-free-1` at ratio 3.51 /
> 118,868 tokens vs phase 37 on `node-free-2` at ratio 1.2 / 239,346): different node, different config,
> different pool — that one stands.
>
> **Also corrected: all three phases ran at `mamba_full_memory_ratio: 1.2`, not the shipped 3.51.**
> That was never stated in this subsection. It does not damage the *depth gap* (0.794/0.797), because
> §12.22 deliberately paired it against a ratio-3.51 boot and got 0.805 — the gap survives a doubling
> of the pool. It **does** limit the absolute per-stream numbers: the d1024 anchor of 103–105 t/s here
> is a ratio-1.2 number, and §12.24 models the shipped config's grant as 20 where this container had
> 14. Quote these as ratio-1.2 measurements.

> **What the three same-container measurements of d1024 add, and it sharpens the first-cell rule.**
> The same cell, same container, three invocations: **103.4 (t/s, n = 5, phase 37) / 93.5 (n = 2, phase
> 38) / 104.6 (n = 5, phase 39)**. The depressed value is the first cell of a blocked sweep. This is
> the strongest available demonstration that **precision and accuracy are different quantities**: p38's
> d1024 cell had cv **0.4 %** across its two runs — the tightest cell in the sweep — and its mean was
> ~10 % below what two later, re-ordered runs measured. A within-cell spread of 0.4 % cannot detect an
> error of that size, because the bias was shared by both runs. Nothing in the artifact flags it; only
> the later, differently-ordered measurement did.

**So the general rule, and it is not "interleave": *a blocked sweep's first cell is part of the
instrument, not a measurement of the system*.** Any blocked design whose first point is the reference
carries the risk that the reference is depressed. Either discard the first cell, or — better — get the
reference from an interleaved run with `runs ≥ 5`, which is what rescued this. **Note that "rescued"
here means "another measurement from the same container", so the reference is independent of the
*ordering* but not of the *boot* (§12.22's replication standard is the one to aim at).** The failure
was *invisible in the per-run spread*: p38's d1024 cell had cv **0.4 %**, the tightest cell in the
sweep, and it was the wrong one. Precision is not accuracy, and cv cannot detect a bias that is
constant across a cell's own runs — which is also why `n = 1` cells are the dangerous case: a single
sample cannot show its own mean is off.

**What this leaves for §12.22's unattributed ~15 pp — and a measured candidate that had been
wrongly excluded.** Three things are now excluded with numbers attached: acceptance (−2.1 %, inside a
±4.7 % CI), KV read **bytes** (≤ 4 % of the step at every depth), and pool pressure (survives a
doubling). But read **bytes** is the wrong quantity to have computed. Per window, from the serve log:

| depth | prefill tokens in window | decode tokens (harness × wall) | prefill : decode | gaps ≥ 25 s with no decode row |
|---|---|---|---|---|
| 1024 | 92,634 | ~12,200 | 7.6 : 1 | 0 |
| 2048 | 105,281 | ~9,600 | 11.0 : 1 | 0 |
| 4096 | 132,422 | ~10,500 | 12.6 : 1 | 1 (26 s) |
| 8192 | 209,896 | ~12,200 | 17.2 : 1 | 2 (82 s) |
| 12288 | 287,208 | ~13,300 | 21.6 : 1 | 2 (108 s) |

**Prefill work per unit of generated output rises 2.8× from depth 1024 to 12288**, at fixed `tg = 256`
and fixed `c = 8`, and long gaps containing *no decode row at all* appear only from depth 4096 upward.
In a continuously-batched engine the next cohort's prefill interrupts the current cohort's decode, and
at `chunked_prefill_size = 4096` an 8-stream cohort at depth 12288 has ~287k tokens to push through
that chunker. **The aggregate "depth penalty" is therefore substantially a prefill-accounting effect —
time spent admitting work rather than generating from it — not a slower decode step.** That fits every
loose end at once: acceptance flat (nothing in the decode path changed), byte-bandwidth insufficient,
`ttfr` growing with depth independently (§12.22), and depth costing *nothing* at c = 1 (§12.8) where
there is no cohort to admit while you decode.

**Status: `LIKELY`, not `VERIFIED`, and now one of two candidates rather than the only one.** Two
things stop it being settled. (i) The `gen throughput` field in those rows is **bimodal** (modes near
150 and near 45 at the same operating point), so it is not a usable instantaneous rate, and any
duty-cycle arithmetic built on it is unreliable — my first pass computed `pure_decode × duty = 154` at
d=1024 against a harness 93.5, a 1.65× error, which is the tell. (ii) The window-level prefill totals
are real but confounded with whatever else the container served.

**This section's conclusion was later over-claimed, and the correction is in §12.27.** The sentence
this paragraph used to end with — the residual is "not bandwidth, not acceptance, probably not the
decode step at all" — went too far in exactly the direction §12.27 undoes. The correct statement is
that there are **two additive costs with different scalings**, both real: prefill work per generated
token (this section, 7.6 : 1 → 21.6 : 1 across depth) and **KV bytes read per decode step**, which
scale with batch × depth (§12.27: `1/peak = a/c + b·depth`, single-boot fit, effective ~97 GB/s). Do
not cite this section for "the depth penalty is prefill accounting" as though it were the whole
mechanism; it is one of two terms, and at `c = 1` — where this section's byte argument was strongest —
the KV term is negligible by construction, which is why prefill appears to explain everything there.
**The clean test is still one boot with prefill and decode timed separately at matched `c`** —
`attic/benchmarking/prefill-contention-d0-vs-d8192.yaml` was written for exactly this and has not been run.

### 12.27 "KV bandwidth is dead" was measured at the wrong concurrency — there IS a batch-dependent depth cost, but not the linear one claimed here

> ### ⚠ FUNCTIONAL FORM REFUTED BY §12.29 — read the banner there first
>
> This section's headline claim, added 2026-09-21, was that the depth penalty "has a **batch×depth**
> term", from `1/peak` being linear in depth at fixed `c = 8` (R² = 0.938). **Phase 49 (§12.29)
> falsifies the linear form on a grid that spans the batch axis:** the cost is **0 % at `c = 2`**
> (`0.967 [0.884, 1.005]`, includes 1.0), **≈21 % at `c = 4`**, **≈17 % at `c = 8`** — and the `c = 4`
> and `c = 8` intervals overlap, so they are not separable from each other. A term linear in `c·depth`
> predicts ≈4× more cost at `c = 8` than at `c = 2`; a plateau with a null at `c = 2` cannot come out
> of it. The step is also in **depth**, concentrated at `d4096 → d8192`, not spread linearly.
>
> What **survives**, and is the part worth keeping: the *logic* of the original refutation-of-the-
> refutation. "KV bandwidth is dead" was argued from a byte count **at `c = 1`**, the one operating
> point where any batch-scaling term is negligible by construction — so that argument could never have
> detected a batch-dependent cost, and declaring the mechanism dead on it was a scope error. There
> genuinely is a batch-dependent depth cost. What is **not** established is that it is KV read
> bandwidth, or that it scales linearly with anything: see §12.29's two untested candidates.
>
> **Every `BW_eff` number in this section should be read as a secant slope through a step, not a
> measurement.** The section's own caveats already said `BW_eff` "is a slope readout, moves ~2× with
> the depth range chosen" and that "the linear form misses its own data by 12 %" — those instincts were
> correct and §12.29 promotes them from suspicious residuals to a refutation of the form.


`.scratch/qwen3-27b/kv_bandwidth_fit.py` fits a **pre-registered functional form** to `peak_throughput`
from the archived artifacts. If the residual depth penalty at fixed concurrency is KV *read* bandwidth,
step time is `t_W + (c·depth·32,768)/BW_eff`, so **`1/peak` must be linear in depth at fixed c**:

| depth | n | peak median | 1/peak |
|---|---|---|---|
| 0 | 15 | 163.0 | 0.00614 |
| 1024 | 75 | 151.0 | 0.00662 |
| 2048 | 7 | 143.0 | 0.00699 |
| 4096 | 44 | 147.0 | 0.00680 |
| 8192 | 139 | 130.0 | 0.00769 |
| 16384 | 12 | 90.0 | 0.01111 |

**`1/peak = 0.006051 + 2.851e-07·depth`, R² = 0.938** at c = 8 (n = 292 decode-phase rows across 6
depths). Solving the slope for bandwidth with the independently-confirmed 32,768 B/token constant:
**BW_eff ≈ 27–35 GB/s, i.e. 12–16 % of the ~221 GB/s budget**, the range being whether `accept len`
includes the bonus token (TPS 3.3 vs 4.3). **The fit's residuals, which limit what may be claimed. An earlier revision of this block claimed a
"5 % closure" against §12.23's measured 0.794 — that claim was invalid and is withdrawn.** It compared
a prediction from `peak` against a ratio measured on `mean`, two different quantities. Computing the
ratio on the same quantity the model is fitted to, the model predicts peak(d8192)/peak(d1024) =
**0.756** where the observed value is **0.861** — **the linear form misses its own data by 12 %** at
that pair. Per-depth residuals: −1.4 %, −4.2 %, −5.1 %, +6.1 %, +9.0 %, −3.5 % at depths
0/1024/2048/4096/8192/16384. The sign pattern (negative below 4096, positive at 4096–8192, negative at
16384) is **systematic, not noise**: `1/peak` rises in a step between 2048 and 4096 and is then nearly
flat to 8192, which a straight line cannot do. So R² = 0.938 measures the fit to a monotone trend, not
evidence that the trend is linear.

**Consequence for the headline number: `BW_eff` is not a measurement, it is a slope readout, and it
moves ~2× with the depth range chosen.** Global slope (all six depths) gives **27–35 GB/s**
(12–16 % of budget); the local slope between just 1024 and 8192 — the range that actually matters for
this recipe — gives **51–67 GB/s** (23–30 %). Reporting either as *the* bandwidth would be false
precision. What is defensible: **at c = 8 the depth dependence has the batch × depth scaling that KV
reads predict, is quantitatively large enough to matter (tens of GB/s, not the ~2 GB/s that killed the
hypothesis at c = 1), and is not linear in depth.** What is not defensible: any single `BW_eff`.

**Reconciling with §12.23, which is the harder problem.** §12.23's interleaved **mean** ratio at d8192
is 0.794 (−20.6 %); the observed **peak** ratio here is 0.861 (−13.9 %). Those differ, and the
difference is informative rather than contradictory: mean falls more than peak, so crowd-out and depth
effects **both** act, with mean picking up the prefill term that peak partially excludes. The right
summary is not "bandwidth, not prefill" but **two additive costs with different scalings** — prefill
work per generated token (rises with depth, grows fast with cohort size; §12.23's 7.6:1 → 21.6:1) and
KV bytes read per decode step (rises with batch × depth; this section). §12.23 was right that
crowd-out is substantial; this section is right that the decode step also gets slower at fixed
concurrency. My earlier framing of the two as competing, and my declaration that one was "dead", was
the error.

**The same fit run at c = 1 is the control that makes this credible, and it fails in exactly the
right way.** Same script, same functional form, c = 1 (n = 420 rows, depths 0/8192/16384):
**R² = 0.020** — no depth dependence — and the implied **BW_eff = 269 GB/s, which exceeds the ~221 GB/s
physical memory bandwidth of the device.** That absurd number is not a bug to fix: with no real slope,
inverting a near-zero slope produces a nonsense-large bandwidth, so **the fit reports its own failure
by returning a physically impossible constant.** Two things follow. (i) The method does not manufacture
a bandwidth signal where none exists, which is the falsification test the c = 8 fit would otherwise be
missing — a model with one free parameter fitted to six points deserves that suspicion. (ii) It
converts §12.8's "depth costs nothing at c = 1" from the observation I *mistook* for a refutation into
a **positive prediction of the model**: no batch ⇒ no KV term ⇒ zero slope ⇒ depth is free. **The
single most misleading null in this document is also the mechanism's cleanest confirmation, and it was
filed as its refutation for two sessions.**

**A sanity check on the intercept, and where it says the model is incomplete.** The fitted intercept
implies `t_W ≈ 160 ms` per step at c = 8 (TPS = 3.3) versus `≈ 118 ms` at c = 1. Weights are read once
per step regardless of batch, so those should be comparable; 160 vs 118 ms is a 36 % gap in the wrong
direction (batch should not inflate the weight term). Either `TPS` differs between the two regimes —
plausible, since `accept len` at c = 8 is lower than at c = 1 — or the model is missing a per-step
overhead that grows with batch (attention over per-request state, scheduler work). **So treat the
BW_eff number as an order-of-magnitude attribution, not a measurement of a memory-system property.**
The claim being made is "a term proportional to batch × depth accounts for most of the depth
dependence", and that claim rests on R² = 0.938 and on the c = 1 null, not on the intercept.

**Third reason no `BW_eff` may be quoted, found 2026-09-22 — and it contaminates this section's own
headline.** A bandwidth is a *device* property, so the derivation above (`slope = BYTES/(BW·TPS)`,
which contains no `c`) makes a prediction this section never tested: **the fitted slope must not
depend on `c`.** Gating out depths that cannot hold `c` sequences (`depth > pool/c`, `pool = 117,752`):

| `c` | depths usable | R² | implied BW (TPS 3.3) |
|---|---|---|---|
| 1 | 6 | 0.020 | 269 GB/s (no real slope — the control, unchanged by the gate) |
| 2 | 5 | 0.600 | **8.9** GB/s |
| 4 | 6 | 0.934 | **38.7** GB/s |
| 8 | 6 | 0.894 | **58.3** GB/s |
| 12, 16, 20, 24 | < 3 each | — | **un-fittable once the ceiling is respected** |

Slopes span **30×** across `c`, so a fixed read rate is not what is being measured. Note what the
first version of this test asserted instead: `slope/c = const`, the *opposite* invariant, which
would have "confirmed" nothing — a mis-derivation of my own formula, left in
`kv_bandwidth_scaling.py`'s history because asserting the wrong invariant is exactly how a wrong
result gets waved through.

**The part that matters more than the spread: the best-fitting columns were the invalid ones.**
Un-gated, `c = 16` fitted at **R² = 0.963** and `c = 20` at **R² = 0.991** — the cleanest lines in the
whole table. Both are pool-ceiling artefacts: when `c·depth > tokens` the server cannot admit `c`
sequences, so `#running-req ≈ tokens/depth` and `1/peak ∝ depth` **with slope `1/tokens` instead of
`BYTES/(BW·TPS)`** — the same straight line for a completely different reason. Gating collapses
`c = 16` from R² 0.963 to **0.500** and cuts its slope 4.2×; `c = 20` becomes un-fittable. **Goodness
of fit actively selected the broken columns, and `R²` cannot know**: it cannot distinguish a physical
slope from an admission ceiling, because both are linear in depth. General rule — *before believing a
fitted slope, check that the regime it spans is one where the fitted quantity can vary*; here the fit
ran over depths where the denominator of `peak` was set by something else entirely.

**Consequence for the headline.** The `c = 8` number above (27–35 GB/s) was fitted **including depth
16384, which exceeds `pool/8 = 14,719`** — a cell the gate exists to remove. Ceiling-gated it gives
**58.3 GB/s** (44.8 at TPS 4.3), so the contaminated figure was biased *low* and the corrected value
lands inside §12.29's independent 63–97. That agreement is encouraging but must not revive the
mechanism: **§12.29 still falsifies the linear form outright** (zero cost at `c = 2`; the equal-`c·depth`
pair; flat per-stream cost at `c = 2` across 8× the bytes). What the gate establishes is narrower and
purely negative — these numbers were partly produced by an admission ceiling, and any future fit must
gate on `depth ≤ pool/c` before a slope means anything. `kv_bandwidth_fit.py` now does this by default
(`--pool`; passing `0` disables it, which is not advised).

**The error being corrected, stated precisely, because the shape of it is the lesson.** §9 item 3
declared bandwidth dead with: *268 MB per step ≈ 2.1 GB/s ≈ 1 % of budget, "a 1 % cost cannot produce
a 30–70 % drop"*. That arithmetic was **correct** and its conclusion **invalid**, for one reason — it
was evaluated at **c = 1**, the single operating point where the mechanism is designed out, since the
KV term is proportional to batch × depth. It then compounded by citing the c = 1 null ("depth costs
3 % at c = 1", §12.22) as confirmation that bandwidth was dead *everywhere*. It is the opposite: the
linear model predicts ≈4 % at c = 1, so **that measurement is the mechanism's best confirmation, and
it was filed as its refutation.** A null measured at the one point where an effect cannot appear is not
evidence about the effect. **Check the regime a null was measured in before generalising it** — this is
the same class of scope error as quoting a depth-0 log line as evidence about depth-8192 traffic
(§12.8), so I have now made it twice in two different forms.

**The pooled data appeared to falsify the model, and the clean grid then falsified the
falsification.** This is the third time in this project that pooling runs across boots produced a
spurious scaling result, so it is written up in full.

*Step 1 — the pooled test.* The two-term model `t_step = t_W + c·depth·BYTES/BW` predicts a slope of
`1/peak` on `depth` equal to `BYTES/(BW·TPS)`, which has **no `c` in it** — so the depth slope must be
the same number at every batch size. Fitting the archive, it was not: 2.86e-7 at `c = 8` and 6.22e-7
at `c = 16`, ratio **2.17** for a 2× change in `c`, implying a cost term `~ c²·depth`. Both fits were
tight (R² 0.94 and 0.9998, n ≥ 6 per cell), so this looked like a clean refutation. **It was wrong**,
and the reason is that those two fits came from *different boots on different days*: a constant that
varies between runs contaminates a fitted **slope**, not just a level. That is the same
co-tenancy error this document already documents for ratios (§12.8) — a third instance of it.

*Step 2 — the grid (phase 44, one boot, one container, 2 depths × 4 batch sizes, 3 runs per cell,
each cell gated idle-first).* This is the design built to remove exactly that confound. Fitting
`1/peak = a/c + b` (model A, cost `∝ c·depth`) against `1/peak = a/c + b·c` (model B, cost
`∝ c²·depth`) at fixed depth, both with two free parameters on four points:

| depth | SS_res model A | SS_res model B | A is better by |
|---|---|---|---|
| 1024 | 1.31 | 39.0 | **30–34×** |
| 4096 | 0.038 | 17.7 | **469–760×** |

(Weighted SS_res, weights `1/SE²`. Two independent reproductions of this fit — one in the original
session, one later via `.scratch/qwen3-27b/fit_phase44.py` — gave 34×/760× and 30×/469× from the **same
artifacts**. Both used four points and two parameters per depth, so the residuals are thin and the
ratio is sensitive to the weighting and to mean-vs-median aggregation: recomputed unweighted it is
11×/84×, on per-run means 40×/2951×. **The multiplier is not a stable measurement; the sign is.**
Quote "model A wins at every depth, by between ~10× and ~3000× depending on estimator", never a single
figure. What is genuinely pinned: a bootstrap over 3000 within-cell resamples puts `SSR(B)/SSR(A)` in
**[1.0, 1.7]** and favours A in **96 %** of resamples.)

**Model B is rejected.** Model A — cost proportional to batch-total KV bytes — wins at both depths
under every aggregation tried. The `c²·depth` reading from step 1 was a pooling artifact, and the
section of this document that asserted it was wrong for the entire hour between being written and this
correction.

*Step 3 — the joint fit, and the part that actually validates the machinery.* Weighted least squares
over all 8 cells (weights = 1/SE², one boot throughout):

```
1/peak = 0.0278/c + 0.0032 + 1.02e-07 * depth        (peak_throughput, decode-phase rows)
         ^weights  ^floor   ^KV read
```

- **The weight term lands on physics — but not to the precision first claimed.** `a = 0.0278 s` →
  `t_W = a·TPS = 92 ms` per step. Independent arithmetic from the checkpoint says reading 17,608 MB of
  weights at the measured 221 GB/s costs **80 ms**. Ratio 1.15. Nothing in this fit was told the weight
  size, the byte count, or the 221 GB/s figure, so the `1/c` functional form recovers a constant it was
  never given. **The earlier version of this bullet said "to 15 %" and called it the strongest evidence
  in the section. Both were overstated**, for two reasons found by refitting elsewhere in the archive:
  (i) `TPS` is a convention, not a measurement — taking 4.3 (accept len *including* the bonus token)
  instead of 3.3 moves this fit's `t_W` to 120 ms, ratio **1.51**; (ii) a completely independent
  depth-0 fit over 10 batch sizes (`c = 2…20`, `n ≥ 3` each, pooled across boots, where **both** models
  collapse to `1/peak = a/c + b` because the depth term vanishes) gives `a = 0.0185` → `t_W` = 61 ms at
  TPS 3.3 (**0.77×**) and 79.5 ms at TPS 4.3 (**1.00×**). So across datasets × conventions `t_W` spans
  **60–120 ms = 0.75×–1.51× of 80 ms.** **What survives: the fit brackets the physical value, from both
  sides, on two independent datasets.** That is still real validation of the `1/c` structure — a fit
  with no knowledge of the byte count cannot land 25 % off in both directions by accident — but it is
  a **factor-of-1.5** agreement, not a 15 % one, and it must be quoted as such. The tempting-but-wrong
  move is picking `TPS = 3.3` *because* it matches; the convention was chosen for an unrelated reason
  and the match at exactly that choice was luck-adjacent.
- **Worse than the TPS ambiguity: `a` is set by one or two data points.** Leave-one-out on the
  depth-0 archive (10 batch sizes, `c = 2…40`, n ≥ 3 each) shows dropping `c = 2` moves `a` by
  **+27 %** and adding `c = 1` moves it **+64 %**, while dropping any of `c = 8, 12, 16, 20, 24, 31,
  34, 40` moves it by **≤ 1 %**. That is not a quirk of this dataset — it is structural: the design
  column is `1/c`, which spans 0.50 → 0.025 over `c = 2…40`, so nearly all the leverage on the
  intercept-like coefficient sits at the smallest `c`. **The weight coefficient is effectively a
  one- or two-point estimate inside a ten-point fit.** Consequences: (i) "brackets physics from both
  sides" is more robust than any single `a`, because it comes from *two different* low-`c`
  configurations landing on opposite sides; (ii) any future run that wants `a` must include
  **several small batch sizes** (`c = 1, 2, 3, 4`), not one, and must report `a`'s leave-one-out
  sensitivity before quoting it; (iii) `b` and `g` are barely affected, so **the section's depth
  conclusion does not depend on this** — only the physics validation does. This is why §12.27's
  most persuasive-sounding claim is the one to distrust.
- **The depth term is real but weakly pinned.** `k = 1.02e-7 ± 3.4e-8`, 3.0σ, `F(1,5) = 9.1`
  (5 % significant, **not** 1 % significant — do not over-read it; and the F is only approximately
  calibrated because the weights come from n=3 within-cell estimates).
- **Read as a bandwidth, it lands near full speed, not near a tenth of it.**
  `BW = BYTES/(k·TPS) = 97 GB/s`, 95 % CI **58–287 GB/s** — a range that *brackets the 221 GB/s
  hardware figure*. This directly contradicts the 19–35 GB/s that §12.23/§12.27 quoted from the
  pooled fits. The pooled numbers were not merely imprecise; they were biased low by roughly
  3–5×, most likely because pooling across boots inflates the fitted depth slope.
- **The 97 GB/s point estimate is weighting-dependent, and this was not recorded the first time.**
  The same fit on the same 8 cells gives `g = 1.57e-7` → **63 GB/s** unweighted, `1.18e-7` → 84 GB/s
  with `1/SE` weights, and `1.02e-7` → **97 GB/s** with `1/SE²` weights — a factor of **1.5** produced
  by a modelling choice, not by data. The weight coefficient `a` is stable across all four schemes
  (0.0278–0.0280, i.e. `t_W` = 92 ms either way), so **the weight term is robust and the depth term is
  not** — which is exactly what one expects from a depth range of two points per `c`. Quote
  **"63–97 GB/s, CI 35–395"** rather than 97 alone. The previously published CI (58–287) happens to
  bracket both point estimates, so the *interval* claim survives; only the presentation of a single
  point estimate was overconfident.

**Corrected bottom line.** The depth penalty at fixed concurrency **is** a KV-read cost — model A
 beats the superlinear alternative at both depths under every estimator tried (30–3000× by
 weighting, favouring A in 96 % of bootstrap resamples) — but the effective read bandwidth is
 **63–97 GB/s depending on weighting, CI 35–395**, not 19–35 GB/s and not a single number. **§12.23's and §12.27's bandwidth figures are
superseded by this fit and should be treated as wrong by a factor of ~3–5**, though their *direction*
(a real batch×depth cost) stands. The honest summary of the mechanism is now: KV reads are a genuine
cost that scales with batch × depth, recovered with the right functional form and an independently
validated weight term, but this instrument cannot pin the bandwidth to better than a factor of ~3
because the depth range at fixed c is too narrow — depth is fitted on two points per c here.

**Design lesson, and it is the same one three times now: a fitted *slope* needs co-tenancy just as
much as a fitted *ratio* does.** Comparing a slope measured in one boot against a slope measured in
another is not a scaling test; it is a comparison of two different machines. The test that works is
one boot, several levels of both factors, and a functional form whose *other* parameter is
independently checkable — here the `1/c` coefficient reproducing 92 ms vs 80 ms is what makes the
depth term believable rather than merely fitted.

The discriminating experiment is **iso-KV**: cells with equal `c·(depth+pp)` (81,920) and depths
differing 6× — (c=4, d=18432), (c=8, d=8192), (c=16, d=3072), plus (c=40, d=0). If cost tracks
batch-total KV bytes the four step-times are equal; if depth itself drives it, they are not.

**RAN (phase 42b, zero boots), and it did NOT discriminate — but the way it failed is the useful
part.** All four cells exist (`c·(depth+pp)` = 81,920 exactly, so KV bytes per step are identical by
construction). Aggregate peak rises monotonically with `c` (86.3 / 129.1 / 189.0 / 228.3 t/s), which
looks like a per-sequence cost. Converting to step time `t = c·TPS/peak` (TPS = 3.3) makes it sharp:

| `c` | depth | peak t/s | `t_step` (s) |
|---|---|---|---|
| 4 | 18,432 | 86.3 | 0.153 |
| 8 | 8,192 | 129.1 | 0.205 |
| 16 | 3,072 | 189.0 | 0.279 |
| 40 | 0 | 228.3 | 0.578 |

Fit: **t_step = 0.1035 + 0.0118·c, R² = 0.998** — a ~103 ms constant plus ~11.8 ms per sequence, at
*constant* KV bytes (2.68 GB/step). **Treat that R² as decoration, not evidence: three of the four
cells are n = 1** (only `c=8, d=8192` has a sample, n = 37 from unrelated sweeps re-using that cell),
so the "fit" is four points of which three are single measurements. The line looks beautiful because
there is nothing to scatter it. Two things follow, and one of them is a trap.

- **Supporting, not proving:** the 103 ms constant, if attributed entirely to the KV read, implies
  2.68 GB / 0.103 s ≈ **26 GB/s** — squarely inside the 19–35 GB/s band fitted in §12.27 on completely
  different data. Two independent routes agreeing on the same bandwidth is real corroboration.
- **The trap: this design is still degenerate.** At fixed `c·(depth+pp)`, `depth = 81920/c − 2048`, so
  **`c` and `depth` are collinear by construction.** "11.8 ms per sequence" and "a cost that falls with
  depth" are the *same fitted direction* in two parameterisations, and no amount of R² can separate
  them. The correct reading is therefore: *at equal batch-total KV bytes, step time rises sub-linearly
  with batch size, consistent with a per-sequence overhead and with the §12.27 bandwidth — and not
  capable of deciding between them.* **This does NOT refute the KV-bandwidth explanation**, which is
  what a first reading of the monotone peak tempting. I nearly wrote "refuted" into this section, and
  the only thing that stopped it was checking whether the design could answer the question at all.

**Design rule extracted: a grid that holds a product of two factors constant cannot separate those
factors — check for collinearity before spending the cells, not after.** The 3-cell version of this
experiment was already recorded as degenerate for exactly this reason (`JOURNAL`), and the 4-cell
version is no better: adding a rung to a collinear ladder does not break the line. The non-degenerate
replacement is phase 44 (two depths × four batch sizes, so `c·depth` and `c` lie on two distinct
lines), which **died on a driver bug after 3 of 8 cells** — `cell_gate.py` was passed an unquoted
command substitution that expanded to three lines, so `float()` raised `could not convert '1\n1\n90.0'`
and every cell was scored VOID by a broken gate rather than by its data. **A gate that always fails
looks identical to data that is always bad**; the tell was the traceback in the driver log, not the
verdict line.

**The 32,768 B/token constant is load-bearing and is not re-fitted here** — it is the same value
confirmed against the server's own `K size` fields to 0.2 % in §12.2bis, so the fit has one free
parameter (the slope) and one prediction (linearity), not a tunable knob.

### 12.28 Prefix-reuse collapse under pool pressure — relocated verbatim from §9 item 3

**Why this section exists and where it came from.** §9 item 3 opened with two sentences about the
depth penalty and had grown to **2,153 words** underneath them, because every correction to this
analysis was written inline where the claim lived. That is the failure mode the objective warns
about: a summary of one paragraph becomes a wall nobody reads, and the summary stops being a
summary. On 2026-09-22 the analysis moved here **verbatim — every wrong number, every retraction,
every citation, in the order they happened**, because the wrong numbers are what stop a future
session re-deriving them. §9 item 3 keeps the four findings and points here. Nothing was
summarised away; relocation, not condensation.

Read §9 item 3 for the verdict and this for the evidence and the three instrument traps.

   Four explanations tested against the server's own log:
    - *Eviction/preemption* ("smells like eviction", the original guess): **refuted for
      preemption only — and the bullet as first written over-claimed, which matters more than the
      original claim did.** The evidence was two `KV cache pool is full. Retract requests.` lines in
      the whole 6,491-line log (`#retracted_reqs: 1` each; 23:05:37 and 02:24:33). That genuinely
      kills *preemption/retraction* as a cause of a 25–65 % effect. It does **not** kill eviction:
      **radix-prefix-cache eviction is silent** — it frees cached blocks without logging a retraction,
        so counting `Retract requests` lines could never have detected it.
        The eviction evidence is the **divisor-free reuse rate** `cached/(cached+new)` per
       concurrency window -- the same expression sglang's own `cache hit rate` field prints,
       computed from the token counts because that field is absent from these logs (see note 2).
       Measured on one boot of the shipped config, two depths, zero extra boots (`--skip-run`):

       | offered c | `c×depth/pool` | depth 1024 | depth 8192 |
       |---|---|---|---|
       | 8 | 0.07 / 0.55 | 5.9 % | **33.8 %** |
       | 12 | 0.10 / 0.83 | 5.9 % | 36.3 % |
       | 16 | 0.14 / 1.10 | 5.9 % | 20.8 % |
       | 20 | 0.17 / 1.38 | 5.5 % | **8.1 %** |
       | 8 (repeat) | 0.07 / 0.55 | 5.8 % | 34.1 % |

       **The pre-registered prediction lands.** Reuse is flat at low pressure (5.9 -> 5.5 %,
       Δ -0.5 pp) and collapses at high pressure (33.8 -> 8.1 %, Δ -25.7 pp), with the knee between
       ratio 0.83 and 1.10 -- where "offered contexts exceed the pool" says it should be. Same
       container, same boot, depth the only variable; the `c = 8` repeat reproduces to 0.3 pp
       (33.8 / 34.1), which is the internal replication that makes the trend worth believing. Script:
       `.scratch/qwen3-27b/analyze_phase31_reuse_nodiv.py`. **Direction established, mechanism not**
       -- `Retract requests` stays ~0 and radix eviction is silent, so the server never logs *why* a
       prefix became unavailable.

       Three things this section got wrong on the way to that table, worth keeping because each is a
       distinct trap:

       1. **A per-request divisor produced impossible numbers, and the reason I gave for catching it
          was also wrong.** An earlier version divided windowed `#cached-token` by `c × runs` and
          reported **86.4 % -> 14.6 %**. That exceeds a request's own prompt length (10,240 tokens at
          depth 8192) -- over 100 % of what is possible -- so it was retracted. **But I attributed
          that to the divisor being too small, and that is false.** `#new-token` in these logs caps at
          **4,096**, so prefill is chunked at 4096: one 10,240-token request spans ~3 `Prefill batch`
          lines whose `#cached-token` values accumulate over its own earlier chunks, so summing them
          legitimately exceeds the prompt bound by ~1.2-2x. **A "physical bound" check only works if
          you know what the counted quantity counts** -- mine applied a per-request bound to a
          per-chunk sum and "detected" an error whose stated cause was fabricated. The bounded ratio
          above is used not because the bound proved the divisor wrong, but because a ratio in [0,1]
          cannot fail this way at all.
       2. **`hitrate_vs_usage.py`, written for exactly this question, silently matched nothing.** Its
          regex required the literal field `cache hit rate`, which **does not appear** in any
          `p28`/`p30`/`p31` log (it exists only in older `.scratch/embed/` logs from a different
          sglang build). It printed "no Prefill batch rows" only *after* I had read its earlier empty
          output as a null result. **An instrument that matches zero rows and returns an empty table
          is this project's most dangerous failure mode**, because an empty table reads as a
          measurement of "nothing". Every analyzer now has to report how many rows it matched, and a
          zero is a broken instrument, not a finding.
       3. **`new` is not the flat denominator this bullet once assumed.** It claimed a fixed-`cached`
          counterfactual reproduced "55.6 % / 63.3 %" of the hit-rate drop; that decomposition is
          ill-posed (a "share of a drop" exceeds 1 when the two terms move in opposite directions)
          and `assert_reuse_claim.py` refutes both numbers. Quote the rate and its pressure ratio; do
           not decompose a drop whose terms move against each other.
        4. **A fourth trap, found while re-checking the above: positional regex groups.** Two
           scripts in this line of work parsed the same `Prefill batch` line with
           `group(2)/group(3)` in one place and `group(3)/group(2)` in another. The one that took
           `#new-seq` as the token total reported **hit rate 1.000** for an arm whose real value is
           0.066 — a perfect-looking number, maximally wrong, and it made reuse look *complete*
           rather than absent. `.scratch/qwen3-27b/reuse_windows.py` now parses this line with
           **named** groups only, asserts row counts, and refuses to report a number from an empty
           window. `#new-token` was confirmed to cap at **4096** (3,773 of 4,291 lines are exactly
           4096) and `#cached-token` peaks at **28,664** = 2.8× the per-request bound, which is the
           accumulation the note above predicts.
        **A second pool size confirms the ratio is the driver, not depth.** Phase 28's `r12` arm ran
        depth 16384 against pool **238,903** — a different depth *and* a different pool from the
        table above — and the matched-`ratio` rows land where the 8192/117,571 arm lands:

        | `c×depth/pool` | hit (8192, pool 117,571) | hit (16384, pool 238,903) |
        |---|---|---|
        | ≈0.55 | 0.360 / 0.341 | **0.422 / 0.416** |
        | ≈0.83 | 0.363 | 0.212 |
        | ≈1.10 | 0.208 | 0.103 |
        | ≈1.38 | 0.081 | 0.061 |

        Neither depth nor pool size is the independent variable; the ratio is. (The two columns are
        not equal at matched ratio — 0.42 vs 0.36 at ratio 0.55 — so the ratio is the *dominant*
        variable, not a complete one. Depth is not free; it just is not what drives the collapse.)
        **And the pool is measurably full at the moment reuse dies.** Same arm, same windows, from
        the `Decode batch` lines — quoting peak `#full token` rather than `full token usage`, because
        the two disagree in kind: peak tokens against the 117,571-token pool give **83,517 / 114,404 /
        117,480 / 116,915** at `c = 8/12/16/20` (71 % / 97 % / 100 % / 99 % of it), while `full token
        usage` *medians* read only 0.55 / 0.83 / 0.87 / 0.78 and its *maxima* 0.70 / 0.96 / 0.99 /
        0.98. Max `#running-req` is **8 / 12 / 14 / 14** — exactly `117,571 / 8,192 = 14.4`, the
        predicted ceiling, and it is pinned there at both `c = 16` and `c = 20` even though 16 and 20
        streams were offered. **Reuse is intact (0.360) while the pool is at 71 % and collapses once it
        reaches 99–100 %.** That is the strongest available support for capacity being the cause rather
        than a correlate — the token pool and the prefix cache compete for the same bytes — but it is
        still two series agreeing inside the same windows, not an experiment that moved one and held
        the other fixed.
        **Why the medians and maxima disagree, because it nearly produced a second wrong sentence
        here.** Grouping the same log by `#running-req` across the *whole file* gives usage medians of
        0.22–0.36, contradicting the 0.55–0.87 above. Both are arithmetically correct: the container
        served the depth-0, depth-1024 and depth-8192 sweeps into one log, so an unwindowed
        `running == 8` slice mixes three workloads. This is §12.8's "establish which sweep a log line
        came from" trap, re-encountered while writing the lesson about it. **Window first, then
        group.**
        **Whether capacity is the CAUSE is still unproven.** The depth-0 control run to settle it
       (`.scratch/phases/p30-0921`) produced aggregate decode that *rises* monotonically with `c`
       (119.0 -> 132.7 -> 142.1 -> 148.8 t/s): there is no fall at depth 0 to explain, so the control
       is inert for a *fall* and cannot arbitrate. **Two citations that a previous revision of this document called "unverifiable" are in fact
verifiable, correct, and the reason the depth-0 control is inert.** The earlier revision asserted that
at depth 0 "llama-benchy never warms the cache (`runner.py:127` gates it on `depth > 0`) and draws a
fresh unseeded random slice per request (`prompts.py:38`)", then **retracted that as unverifiable** on
the grounds that llama-benchy was not importable in the container, on the dev box, or in pip. It is on
the dev box — inside the uv archive cache, and `sparkrun` pins **llama-benchy 0.4.0**, the same version
whose `Pinned llama-benchy version: 0.4.0` line appears in every benchlog here, so the citation applies
to the code that actually ran. Both lines verify:

```
runner.py:127   if self.config.enable_prefix_caching and depth > 0:     # the Context-Load phase
prompts.py:38   start_idx = np.random.randint(0, max_start)             # unseeded: no np.random.seed
```
(archive `…/uv/archive-v0/8qgNSATLpN7FE7Jh/llama_benchy/`, md5 `runner.py`
23da652b8a9a989745445b7b0eba3f0b, `prompts.py` 7ed82fea0e46525764ef037b5a5f4dbb; `grep -rn
"random.seed"` over the package returns nothing, so the slice really is unseeded.)

**And the "logs contradict it" evidence was itself the unwindowed-log trap this section is about.** The
depth-0 figure quoted against the claim — "depth 0 = 6.4 %" — came from a whole-file sum over
`p30-0921/p30_10_0_4_34_post.log`, which spans **3.52 hours** while p30's own five cells occupy only
11:18–11:25 (8 minutes). Windowing to p30's cells with the harness's own `Task k/N done` timestamps:

| cell | offered c | cached | new | **hit rate** |
|---|---|---|---|---|
| 1 | 8 | 0 | 65,781 | **0.0000** |
| 2 | 12 | 128 | 73,775 | **0.0017** |
| 3 | 16 | 128 | 98,360 | **0.0013** |
| 4 | 20 | 64 | 123,026 | **0.0005** |
| 5 | 8 | 0 | 49,315 | **0.0000** |

**Depth-0 reuse is ~0 %, not 6.4 %** — precisely what the `depth > 0` gate predicts, because with no
Context-Load phase there is nothing in the radix tree to hit. The 6.4 % was other sweeps in the same
file. So the retraction was wrong twice over: it discarded a source-verified mechanism, and it did so
because of a number that violated the section's own "window first, then group" rule. (Note the
coincidence that made this hard to see: depth-1024's unwindowed 6.4 % happens to sit near its windowed
5.9 %, because that container had served little else — so the aggregate looked trustworthy.)

**Consequence, and it strengthens rather than weakens the control verdict.** The depth-0 run is inert
for *two* independent reasons: aggregate decode **rises** monotonically with `c` (119.0 → 132.7 → 142.1
→ 148.8 t/s), so there is no fall to explain; **and** reuse is ~0 % at every `c`, so there is no reuse
collapse to compare against. It cannot arbitrate whether capacity causes the collapse, and now we know
why before running it: **a depth-0 arm cannot exercise the prefix cache at all.** Any future control for
this question must use `depth > 0` with the working set *below* the pool — which is what
`cache-control-d1024.yaml` / `cache-control-d2048.yaml` were built for.

**The meta-lesson, which is the one to keep: "I cannot find this source on my machine" is not evidence
that a citation is wrong.** It was evidence about my search path. Before retracting a claim for
unverifiability, the check is "where does this tool actually live when it runs?" — for a pinned
dependency that means the uv archive cache, and one `find` there restored a correct claim that had
already been deleted once.

### 12.29 Phase 49: the depth cost is a STEP in two variables, not a ramp — which refutes §12.27's linear form

> **⚠ RETRACTED BY §12.31 — do not use this section's falsification.** Its "equal
> bytes" pairs share `c·depth`, which is **not** the KV byte count: a decode step reads
> `pp + depth/2` resident tokens on average, so the pairs differ ~1.33× in the quantity being
> tested. Measured on the correct regressor the ratio tracks resident tokens (ρ = +1.00) and the
> equal-bytes pair shows **no** difference (0.877 [0.840, 1.043]). The "step at d ≥ 8192, on at
> c = 4" result is binning on a variable that omits `pp`. Kept verbatim as the record of how the
> wrong regressor was adopted; read §12.31 for the current position.

`attic/benchmarking/depth-linearity-grid.yaml`, 4 depths × 3 batches × 3 runs, **zero boots**
(`--skip-run` on the already-live `node-free-1` container, `capped to 21`, `#tokens 117,752`). 12/12 cells,
all gated usable (`#running-req` == offered `c`, no cell capacity-limited), all distinct md5s.
Artifacts `.scratch/phases/p49-0922/`.

Per-stream aggregate decode (median of 3 runs), with bootstrap 95 % CIs on the ratio:

| c | d1024 | d2048 | d4096 | d8192 | d4096/d1024 | d8192/d4096 | d8192/d1024 |
|---|---|---|---|---|---|---|---|
| 2 | 52.6 | 52.6 | 56.4 | 53.1 | 1.046 [0.995, 1.155] ns | 0.967 [0.884, 1.005] ns | 1.011 [0.952, 1.075] ns |
| 4 | 82.2 | 82.7 | 78.3 | 62.2 | 0.945 [0.865, 1.051] ns | **0.793 [0.742, 0.848]** | **0.750 [0.684, 0.835]** |
| 8 | 98.3 | 101.3 | 104.5 | 84.9 | 1.083 [1.024, 1.105] | **0.828 [0.769, 0.852]** | **0.897 [0.814, 0.907]** |

**Two findings, both of which contradict what §12.27 assumed.**

1. **The cost is concentrated in one depth transition.** d1024 → d4096 is indistinguishable from
   nothing (or marginally *positive*) at every batch. Everything happens at **d4096 → d8192**: −21 %
   at c = 4, −17 % at c = 8. This is why the fitter reports a significant quadratic depth term
   (`F(1,8) = 51.8`, `q = 4.7e-11`) — and it is why **any single `g` labelled "the bandwidth" is a
   fiction**: a straight line through a step is a statement about the step's endpoints, not a
   mechanism. `fit_phase48.py` prints `132–172 GB/s` for the linear `g`; read that as
   "the secant slope", not as a measurement (same failure mode §12.27 already flagged for `BW_eff`,
   now demonstrated on a grid that spans the step).
2. **The cost does not grow with batch — it switches on between c = 2 and c = 4, then stops.** At
   c = 2 the d8192/d4096 ratio is `0.967 [0.884, 1.005]` — includes 1.0, so **depth is free at c = 2**.
   At c = 4 it is `0.793 [0.742, 0.848]`; at c = 8, `0.828 [0.769, 0.852]`. **The c = 4 and c = 8 CIs
   overlap heavily, so they cannot be separated from each other** — the honest statement is "≈20 %,
   the same at both", not "non-monotone in c". What *is* separated from c = 2 is the point: the two
   intervals do not overlap.

**(c=4, d=8192)** and **(c=8, d=4096)** have **identical `c·depth` = 32,768**, so a per-byte KV model
predicts equal *step times*. The first version of this paragraph tested that on **`peak_throughput`**
(87.3 vs 149.7, "a 1.74× gap") and thereby tested the wrong quantity — `peak` is
`c · TPS / t_step`, so it *scales with `c` by construction*. A per-byte model does not predict
`peak_B / peak_A = 1`; it predicts `= c_B/c_A = 2`. Measured 1.74× sits **between** the two, so the
peak comparison could not have falsified anything. The correct test divides out the batch:

    t_B / t_A  =  (c_B / c_A) · (peak_A / peak_B)

**and this ratio is free of the `TPS` convention that §12.27 flags as unresolvable**, because `TPS`
cancels — which is why it is a constraint on the model rather than one more fitted constant.
Applying it to the phase-49 pair: `2 × (87.3/149.7) =` **1.17**, i.e. the equal-bytes pair takes
~17 % more time per step at the larger batch. *(These two numbers were cited here as "the phase-48
cell" for a while; phase 48's grid stops at depth 4096 and contains no depth-8192 cell, so that
attribution was impossible. `.scratch/qwen3-27b/find_pair_source.py` locates the real source —
`p49_c4_d8192.json` `[85, 86, 91]` and `p49_c8_d4096.json` `[144, 150, 155]`. The numbers were right
and their provenance was not, which is the variant that survives a check which only re-reads the
numbers.)*

**The test is valid, and corroborated across two boots — but not for the reason first written
here.** `depth` is llama-benchy's *generated* length and `pp` the *prompt* length (per-row
`context_size` / `prompt_size`), so what matters is whether prompt length was equal within a pair.
It was, in **both** pairs — that is what makes the comparison bite:

| pair (both `c·depth` = 32,768) | cells (`c`, `depth`, `pp`) | prompt `pp` | pool `c·(d+pp)` | peak usage | `t_step` ratio |
|---|---|---|---|---|---|
| phase 49 | (4, 8192, 2048) / (8, 4096, 2048) | 2048 **=** | 40,960 / 49,152 (+20 %) | 0.35 / 0.43 | **1.17** |
| phase 51 | (4, 8192, 6144) / (8, 4096, 6144) | 6144 **=** | 57,344 / 81,920 (+43 %) | 0.49 / 0.71 | **1.33** |

Phase 51 (`n = 3` each, `[70, 80]` vs `[104, 118]`, no overlap) reached the same sign as phase 49 on
a **different boot at a different prompt length**, which is about the strongest corroboration this
recipe gets — cross-boot agreement is normally the thing that fails. So: **a strictly per-byte KV
cost cannot rank these cells.** The sign is wrong, not merely the magnitude, and that survives the
`TPS` convention because the ratio `(c_B/c_A)·(peak_A/peak_B)` cancels it.

> **Phase 51 got its `pp` by accident, and the accident is worth knowing.** Its driver
> (`run_phase49.sh`, extended with `c:d:pp` grid entries for exactly this experiment) builds the
> override array `PPF=(-b pp="$pp")` — and the `sparkrun` invocation **never expanded
> `${PPF[@]}`**. So `pp` came from the profile (6144) in *every* cell while the filenames, written
> from the *intended* value, said `p4096`. The intended design held `depth + pp` = 10,240 constant;
> what actually ran held `pp` constant instead. **The comparison in the table above is unaffected**
> — the two cells genuinely share `pp`, which is what makes it a valid test — but it is valid for a
> reason nobody designed. Fixed by adding `"${PPF[@]}"` to the invocation; the arbitrating pair below
> was then **verified by dry-run to apply `pp: [2048]` and `pp: [1024]`** rather than assumed. Two
> lessons: a filename derived from *intent* rather than from the artifact makes a silent no-op look
> like an executed design, and `--dry-run` cannot catch this class either — it prints the command it
> is shown, and the shown command never contained the override. `.scratch/qwen3-27b/verify_cell_args.py`
> reproduces the finding on the archived artifacts as `FILENAME LIE`.
**One confound survives, and it is bigger than first written.** Pool demand `c·(depth+pp)` is
*unequal* in both pairs (+20 %, +43 %) — and **it cannot be removed at all**, because of a relation I
missed the first time: with `c_B = 2·c_A`, `pool = c·depth + c·pp`, so with `c·depth` matched, **any**
increase in `c` necessarily increases pool demand. In this design the cell with the larger batch is
*always* the cell with the larger pool, by construction. **Batch size and pool pressure are therefore
perfectly collinear here**, and the experiment cannot separate a per-sequence cost from a
pool-pressure cost no matter how tight the statistics get. The falsification is of a *strictly
The `usage` column above is **not trustworthy as a per-cell figure** and should be read as
indicative only. It came from grouping serve-log decode lines by `#running-req`, which pools all
depths sharing a batch size — but usage tracks `c·(depth+pp)`, so phase 51's "0.71" is the maximum
over its three `c = 8` cells at depths 4096/6144/8192, not the (c=8, d=4096) cell. (`.scratch/
qwen3-27b/cell_usage.py` was written to do this per-cell and is **not yet working** — its windows come
from per-cell benchlogs whose timestamps are compared against a synthetic date, so every window
matches zero samples and it prints `NO SAMPLES IN WINDOW` rather than numbers. Do not quote it until

**Also worth recording: a "clean" pair I proposed is unsatisfiable, and I nearly queued it.** I
sketched cells matching `c·depth`, prompt length *and* pool demand. Equal `c·depth` plus equal pool
forces equal `c·pp`, so with `c_B = 2·c_A` you get `pp_B = pp_A/2` — contradicting equal `pp`. Three
mutually exclusive conditions. The nearest real experiment is `(4, 8192, 2048)` vs
`(8, 4096, 1024)`: bytes *and* pool matched, prompt length differing 2×. It does not isolate pool
pressure either — it just trades one confound (pool) for another (prompt length), which is a better
exchange only if prompt length is independently known not to matter. It has not been run.
Two limits stand regardless. (i) It falsifies *per-byte* cost, not bandwidth in general — a
bandwidth-limited kernel charging **per sequence** (one gather/launch per stream, bytes irrelevant)
is untouched. Saying "bandwidth is dead" would repeat the §9 error in a new guise. (ii) `n = 3` per
cell with no interleaving, so a within-boot drift of ~10 % could account for part of the 33 %; the
sign is robust across two boots, the magnitude is not a measurement to two figures.

**Every alternative explanation is excluded by these same rows, and two are excluded by
measurement rather than argument.** From `serve.log`, bucketed by `#running-req` (493 decode rows)
and then restricted to each cell's own window:

- **acceptance is flat**: median `accept len` is **3.19–3.41 in all twelve cells**, including
`(c=8, d=8192)` at 3.19 and `(c=8, d=4096)` at 3.21. The draft does not degrade with context here.

- **prefill throughput is flat**: `pp_throughput` spans **2169–2343 t/s across all 12 cells** with no
trend in depth or batch. So the extra prefill *work* at `d = 8192` (2.5 chunks vs 1.5) is being
admitted at the same tokens/second — which is what makes §12.29's chunk-count candidate hard to
sustain as a *throughput* mechanism, even though the step lands exactly where the chunk count steps.

- **KV read bandwidth is excluded twice**: by the equal-`c·depth` pair above, and because the
per-stream cost at `c = 2` is flat from 1024 to 8192 where bytes-per-step vary 8×.

- **pool pressure is excluded**: peak `full token usage` is **0.71** even in the worst cell, and
peak **`mamba usage` never exceeds 0.29** in any cell, so neither the KV pool nor the state pool is
anywhere near its limit. The §12.28 reuse-collapse regime needs 0.97–1.00.

- **capacity is excluded**: `max running` equals offered `c` in all 12 cells (all `cell_gate.py`

**Consequence for §12.27, stated as a refutation of its functional form.** §12.27 fitted
`t_step = t_W + (c·depth·32,768)/BW_eff` to c = 8 data and got R² = 0.938, concluding the depth
penalty "has a batch × depth term". That form makes a **strong prediction that this grid falsifies**:
a term linear in `c·depth` requires the cost to *ramp* with batch — roughly 4× more at c = 8 than at
c = 2. Observed: **0 % at c = 2, ≈20 % at c = 4, ≈17 % at c = 8.** A ramp cannot produce a plateau, and
a plateau cannot produce the c = 2 null. So §12.27's fit was **good at describing one column of the
grid and wrong about the mechanism**; its own caveats ("`BW_eff` is a slope readout, moves ~2× with
the depth range chosen", "the linear form misses its own data by 12 %") were the right instincts and
this grid strengthens them from "suspicious residuals" to "the form is wrong".

**Capacity is excluded, so this is not the pool.** The per-cell gate (`cell_gate.py`, run by the
driver on every cell, all 12 `rc=0`) reports **`max running` == offered `c` in all twelve cells** —
nothing was queue-limited — and **peak `full token usage` is 0.71** (at `c = 8, d = 8192`), the
next-highest being 0.43. The reuse-collapse mechanism of §12.28 operates at usage 0.97–1.00 and is a
different regime; it cannot be the cause here. **A trap worth recording:** reading the
`p49_serve_after_*.log` snapshots' *last* `Decode batch` line gives `#running-req: 6` and usage 0.36
for that same cell, which looks like a queue-limited cell. Those lines are **after the cell drained**,
so they are not a measurement of the cell — the in-window peak from the gate is the only correct
source. Same family as the §12.28 windowing trap, arriving from the opposite end: not "which sweep is
this line from" but "is this line inside the cell at all".

**What distinguishes d8192, and what distinguishes c ≥ 4 — UNVERIFIED, two candidates each.** The
prompt is `depth + pp` = 10,240 at d8192 vs 6,144 at d4096, and `chunked_prefill_size = 4096` with
`max_prefill_tokens = 16,384` (both read from this container's own `server_args`): 10,240 is 2.5
chunks where 6,144 is 1.5, so a prefill-admission term jumps at exactly that transition. For the
batch step, the obvious candidate is CUDA-graph capture: `cuda_graph_max_bs_decode` is `None` (auto),
so the captured batch list is chosen by the runtime and a batch of 4 vs 2 can cross a
capture/verification-graph boundary — and §12.8 measured that the captured `bs` list tops out at the
grant, so capture shape is not obviously irrelevant below the grant. **Neither candidate is tested
here**, and the grid cannot test them: it has no arm that holds prompt length fixed while varying the
chunk count, and no arm below c = 2 or between 2 and 4. **Next cheap experiment, if this matters:**
same container, `depth` ∈ {4096, 6144, 8192} with `pp` compensating to hold `depth + pp` constant —
that separates "context length drives KV/attention" from "prompt length drives prefill chunking",
which is the fork these two candidates sit on. Zero boots.

**Aggregate vs per-stream: the drop is real, and it is NOT established to be a per-stream slowdown.**
Each cell writes two rates, and they disagree in a way that matters (`tg_throughput` = aggregate over
the batch; `tg_req_throughput` = per stream — and note `tg_req ≠ tg / c`, they differ by 30–46 % at
c = 8, so one of them is not what a naive reader assumes). Three ways to read the same transition:
| c | aggregate `tg` ratio | per-stream `tg_req` ratio | `tg / (c·tg_req)` "occupancy" |
|---|---|---|---|
| 2 | 0.942 | 0.948 [0.873, 1.032] | 0.994 |
| 4 | **0.793** [0.718, 0.876] | 0.874 [0.831, 1.021] | 0.908 |
| 8 | **0.812** [0.747, 0.864] | 0.860 [0.705, 1.052] | 0.907 |
`aggregate = c · per-stream · occupancy` is an **identity** (occupancy is *defined* as
`tg/(c·tg_req)`; the product matches to 1e-16), so this is exact re-arrangement, not a fit. It says the
aggregate loss at c = 4/8 splits roughly half-and-half between slower streams and fewer streams
effectively decoding. **But the per-stream column's CI includes 1.0 at every c** (n = 6/12/24), so the
honest statement is: *the aggregate drop is real (CI excludes 1.0 at c = 4 and 8), the per-stream
decline is not separately established, and the two-term split is too small-n to attribute.* Claiming
"per-stream decode got 13 % slower" from a point estimate whose interval straddles 1.0 is the same
error class this section exists to catch. **If you need the split, re-run with more runs — the grid is
zero-boot, so n is cheap and is the only thing standing between a description and an attribution.**
This is `benchmarking/README.md` rule 1 arriving from an unexpected direction: there the warning was
that `tg t/s` is aggregate and reading it per-stream misstates by a factor of `c`; here the two
published columns disagree with each other in a way that changes what the result *means*, and the
documented per-stream column is the one with less statistical power.
**Methodological note that earned its keep.** The bootstrap CIs on the first pass were **degenerate —
exactly zero width** — because I resampled *the mean of a cell* rather than the three run-level values
inside it: one sample, no variance, a "95 % CI" of `[1.072, 1.072]`. A CI of zero width is
arithmetically impossible and is the tell. Had I reported those intervals, every cell would have come
out "significant". Fixed by resampling `values` from the JSON's per-run list. **Rule: if an
uncertainty estimate is zero, the bug is in the code, not in the data.**

### 12.30 A crossed `pp` design cannot separate KV bytes from pool residency — and the additive model is the wrong form

> **⚠ PARTLY SUPERSEDED BY §12.31.** The non-separation stands as a statement about
> this grid, but "the additive model is the wrong functional form" was argued on `c·depth`, the
> wrong regressor; with `c·(pp + depth/2)` the same cells fit at 4.74σ and the sign problem goes
> away. Do not cite this section as evidence against additive cost models.

`.scratch/qwen3-27b/run_phase54.sh`, zero boots (`--skip-run` on the live `node-free-1` server): 12 cells,
`c ∈ {2,4,8}` × `depth ∈ {4096,8192}` × `pp ∈ {1024,2048}`, `n = 3`. Designed so `B = c·depth` (bytes
read per step) and `P = c·(depth+pp)` (resident tokens) are not proportional — the separation §12.29
could not get from a pair. **It did not deliver it, and the reason is the result.**

Response is step time `t = c·TPS/peak`, columns `[one, c, B, P]`, additive physics
`t_step = t_W + A_seq·c + K·B + M·P`.

| model | p | SSR | R² | |
|---|---|---|---|---|
| `one` | 1 | 1.09e-02 | 0.000 | no |
| `+A_seq·c` | 2 | 1.01e-03 | 0.908 | per-sequence term: fitted `1.3e-02 ± 2.6e-03` (5σ on this fit), SSR ÷10 — **but NOT reproduced; see §12.52** |
| `+K·(c·depth)` | 3 | 3.30e-04 | 0.970 | `K = 8.1e-07 ± 3.7e-07` → BW **41 GB/s** at TPS 3.3 |
| **`+M·c(d+pp)` instead** | 3 | **2.50e-04** | **0.977** | fits *better* with no bytes term |
| `+both` | 4 | 2.50e-04 | 0.977 | **no SSR gain**; `K` and `M` both UNRESOLVED |

Adding a per-byte term to a model that already has a per-resident term buys **0.1 %** of SSR for a
whole parameter. And `K` is resolved only while `P` is absent: adding `P` collapses `K` from
`8.1e-07` to `3.4e-08`, a **24× swing** that moves implied bandwidth from 41 to **964 GB/s** — above
the ~221 GB/s hardware ceiling, i.e. physically impossible. **41 GB/s is not a measurement; it is what
a 3-parameter projection happens to print.** Any bandwidth number from this data must name its model.

The design has **rank 4/4**, so "algebraically entangled" would be false — the directions *are*
separable in principle. What kills it is read directly off the `pp` contrast at fixed `(c, depth)`: the
implied `M` **changes sign** (−2.7e-06 at (4,4096), +4.0e-06 at (8,4096), ~1000× apart), whereas a real
additive per-resident cost has one sign and comparable magnitude. So `P` is **absorbing an interaction
between `c` and `pp`**, and F's good SSR is borrowed from that, not from pool residency. **The
additive form `t_W + A_seq·c + K·B + M·P` is the wrong functional form** — stronger and more useful
than "underpowered": the grid could have separated the terms, and what it found is that they do not
add. Lesson: **crossing a design is necessary but not sufficient — ask which contrast it resolves,
not whether its rank is full. Rank is not resolution.**

Largest unexplained single effect in the grid: at `c = 8, depth = 4096`, `pp` 1024→2048 drops peak
**172 → 142 (−17 %)**, exceeding that cell's own 14 % within-run spread, at fixed `c` and `depth` — so
it is not §12.29's depth transition. One 3-run cell; needs a repeat at higher `n` before believed.

Next lever if this is ever pursued: `mamba_full_memory_ratio` at fixed `depth`/`c` changes residency
cost without changing bytes per step — one boot per arm, the first non-free experiment here — but run
it **only** after checking the additive assumption, or it will produce another confident 41-GB/s
artefact.

**Instrument lesson, and it is the dangerous kind.** This fitter first printed **negative R² for every
model (−814 to −17)**, which reads as "worse than a horizontal line" — dramatic, quotable, and entirely
an artefact. Cause: `se` weights were `1/cv ≈ 4–23`, never normalised, so the weighted SSR was in
`weight²·y²` while `ss_tot` was in `y²`. A second bug of the same species sat beside it: the
"sensitivity bound" used the **unweighted** design and carried no residual scale while `se` carried
both, so comparing them made *every* coefficient UNRESOLVED — the tool looked appropriately humble
while being meaningless. Fixed by normalising weights to RMS 1 (leaves the LS solution and se ratios
invariant) and making the verdict `|coef| vs 1.96·se` from one fit. **A mis-scaled statistic that
prints a boring wrong number gets noticed; one that prints −814 gets quoted. Sanity-check the range of
every summary statistic before interpreting its sign.**

### 12.31 The per-byte refutation in §12.29 was a wrong regressor — retracted

`.scratch/qwen3-27b/peak_vs_mean_fit.py`, `.scratch/qwen3-27b/resident_tokens_fit.py`,
`.scratch/qwen3-27b/pool_vs_perseq.py`. Zero boots: same 12 archived phase-54 cells. This
section exists to **retract** §12.29's headline claim that a strictly per-byte KV cost is
falsified, and the retraction is about my own arithmetic, not about new server behaviour.

**The error.** §12.29 and §12.30 both call `B = c·depth` "KV bytes read per decode step". It is
not. A decode step reads every token resident for that request — the **prompt** plus tokens
generated so far — so over a generation of `depth` tokens the average resident count is
`pp + depth/2`, and `pp` is not negligible here (1024–2048 against depth 4096–8192). A second,
independent error compounds it: `peak_throughput` is the **max of the time series**, so it is
attained *early*, when the sequence is near `pp`; the mean averages the whole generation. Which
token count is the right regressor depends on which statistic is being modelled, and `c·depth`
matches neither.

Fitting `t = c·TPS/rate` on `[one, c, X]` (TPS cancels in ratios), 12 cells:

| X | SSR (peak) | R² | | SSR (mean) | R² | coef/1.96se |
|---|---|---|---|---|---|---|
| `c·depth` — what §12.29 used | 3.34e-04 | 0.969 | | **6.27e-03** | 0.875 | 1.35 |
| `c·pp` | 9.91e-04 | 0.909 | | 4.66e-03 | 0.907 | 1.80 |
| **`c·(pp + depth/2)`** | 3.28e-04 | 0.970 | | **1.05e-03** | **0.979** | **4.74** |
| `c·(depth+pp)` | 2.58e-04 | 0.976 | | 2.88e-03 | 0.943 | 2.59 |

On the mean — the statistic that matches the physics — **`c·depth` fits 6.0× worse than
`c·(pp + depth/2)`**, which is at 4.74σ. So the regressor behind the refutation was the wrong
one, and it was measurably the wrong one.

**The decisive consequence: the "equal bytes" pair was never equal in bytes.** Four pairs in the
grid share `c·depth` = 32,768 and the same `c` doubling; they differ only in `pp`. Step-time
ratio, mean statistic, bootstrap CI over runs:

| pair | A | B | `tB/tA` | 95 % CI | resident-token ratio |
|---|---|---|---|---|---|
| pool equal | (4, 8192, 2048) | (8, 4096, 1024) | **0.877** | [0.840, 1.043] | **1.000** |
| pool +11 % | (4, 8192, 1024) | (8, 4096, 1024) | 0.923 | [0.883, 1.159] | 1.200 |
| pool +20 % | (4, 8192, 2048) | (8, 4096, 2048) | 1.300 | [1.180, 1.422] | 1.333 |
| pool +33 % | (4, 8192, 1024) | (8, 4096, 2048) | 1.369 | [1.240, 1.581] | 1.600 |

Rank correlation of ratio vs resident-token ratio: **ρ = +1.00** across the four. Ratio spread
56 %, whereas **a pure per-sequence cost predicts ONE ratio for all four** (identical `c`
increment, identical bytes) — that is what §12.29 read as a step function. **When the byte count
is genuinely equal the ratio is 0.877 with a CI that includes 1.0 — no difference.** The cell
that §12.29 used as its falsification is `(4, 8192)` vs `(8, 4096)` **at `pp` = 2048**, where the
resident-token ratio is 1.33: it was never an equal-bytes comparison.

So §12.29's "the step lives in `d ≥ 8192` and turns on at `c = 4`" is an artefact of binning on a
variable that omits `pp`. §12.30's "non-separable, additive form is wrong" inherits the same
fault, since it compared cells on `c·depth` too.

**What is NOT established.** This does not measure bandwidth. It shows (i) resident token count,
not generated length, drives per-step cost, and (ii) the earlier per-byte falsification rested on
a mis-specified regressor. A mechanism claim still needs a slope on a dedicated sweep plus a
device-side measurement. `n = 4` pairs and overlapping CIs on two of them; the monotone ordering
is the evidence, not any single ratio. **And `pp` is confounded with pool demand in this design**
— `pp + depth/2` and `depth + pp` move together — so this cannot separate average-resident from
peak-resident either.

**Rejected inference, recorded so it is not re-made.** The 10-hour container still held
`/tmp/sparkrun_serve.log` (8,504 lines), and grouping its `#full token` by `#running-req` gives
~14,500 tokens per running request at c = 8 — *above* the 10,240 max for a phase-54
depth-8192/pp-2048 request. That is not an anomaly to explain: **the log spans every sweep the
container has served, including phase 49's depth-16384 cells**, where 18,432/request is legal.
Windowed per-cell attribution requires the harness's `Task k/N done` timestamps, and without them
this log cannot describe phase-54 cells at all. Whole-file aggregation of a shared serve log is
the same trap as §12's `#cached-token` divisor errors; treat un-windowed log aggregates as
un-attributable.

**The general rule, which is the reason this took so long to notice: check what your regressor
counts before concluding anything about the quantity it is supposed to represent.** `c·depth` was
plausible, named "bytes", and used consistently across two sections and four scripts. Nothing in
the code or the fit complained. What caught it was asking a *different* question of the same
artifacts — what does `peak` actually measure — which is the cheapest kind of audit there is and
the one I keep skipping.
### 12.32 Phase 55: the server's own decode metric finds NO KV-bandwidth cost — and the harness metric was measuring admission

Zero boots, one already-live container on `node-free-1`, config verified from its own serve log
(`mamba_full_memory_ratio': 3.51`, `mamba_ssm_dtype': 'bfloat16'`,
`speculative_num_draft_tokens': 8`, `capped to 21`, `#tokens: 117752`). Driver
`.scratch/qwen3-27b/run_phase55.sh`, artifacts `.scratch/phases/p55-ppslope/`, profile
`benchmarking/pp-slope.yaml`: `c = 8` fixed, `depth ∈ {1024, 4096}`, `pp ∈ {1024, 2048, 4096}`,
3 runs. Single-variable-by-construction: changing **only** `pp` changes prompt length and nothing
else in the decode graph.

**The headline result, and it is a negative.** Two metrics of the same six cells:

| metric | `pp` 1024 → 2048 → 4096 at `depth = 1024` | behaviour |
|---|---|---|
| harness `tg_throughput`, decode-phase row | **127.3 → 102.4 → 78.8** | falls **38 %** |
| harness `peak_throughput`, decode-phase row | **163.3 → 148.0 → 126.7** | falls 22 % |
| harness `pp_throughput` (the real prefill rate) | **2290.3 → 2290.0 → 2293.2** | **flat**, 0.14 % spread |
| harness `ttfr` | **3,537 → 7,498 → 11,752 ms** | rises **3.3×**, ≈ linear in `pp` |
| sglang's own `Decode batch ... gen throughput` | *not resolvable per `pp`* — see below | (depth contrast instead: 159 → 153) |

**Read that table's asymmetry before using it.** Four rows are the `pp` sweep; the last is
**not**, and cannot be. llama-benchy emitted only **two** `Task k/N done` lines for this six-cell
run — one per **depth**, not per cell — so serve-log lines can be windowed by depth but **not**
by `pp`. The 159 → 153 pair is therefore a **depth** contrast (windows whose median `#full token`
is 17,401 vs 33,803) sitting in a column labelled `pp`. It is included because it is the only
server-metric contrast this artifact supports, and it is the weaker half of the argument.

**The four harness rows alone carry the contamination finding, and they are self-contained:** the
same cells show `pp_throughput` flat to 0.14 %, `ttfr` rising 3.3×, and `tg_throughput` falling
38 % as `pp` rises 4×. Since `pp` affects only the prompt, a metric that measures decode must not
move — and it moved most. Prefill *rate* is
constant (2290 tok/s to three figures) but **time-to-first-response grows linearly with `pp`** —
3.5 s → 11.8 s — because there is simply 4× more prompt to admit at that constant rate. That
admission time lands inside the harness's decode measurement window, and it scales with exactly the
swept variable, which is why a single-variable design was needed to see it. `ttfr` tripling is the
tell available from the harness alone: a metric that only measures decode must not move when a
variable affecting **only prefill** is swept.

**How the KV question was answered, and the three wrong answers it took to get there.** Every
figure below is a fit of step time `t = c·TPS/gen` (TPS per line from that line's own `accept len`)
against that line's own `#full token`. The same 35 decode lines give **three different answers**
depending on aggregation, and this is the whole lesson of the section:

| aggregation | n | slope (s/token) | σ | implied BW |
|---|---|---|---|---|
| whole serve log | 181 | −3.6e-08 | **0.58** | — (negative) |
| both task windows pooled | 35 | +1.69e-07 | 6.8 | 194 GB/s |
| window 1 (depth 1024) alone | 19 | +1.82e-07 | 30.0 | 180 GB/s |
| window 2 (depth 4096) alone | 16 | +4.2e-08 | 0.7 | 786 GB/s |
| **pooled within-cell** (cell means removed) | 15 | **+8.4e-08** | **1.47** | **389 GB/s** |

1. **First answer (0.58σ, "no KV term") came from pooling the whole 12-hour shared serve log** —
   the exact aggregation trap §12.31 documents. That log holds every sweep the container has served,
   so `#full token` values from unrelated depths were mixed and the slope cancelled.
2. **Second answer (6.8σ, "194 GB/s") came from pooling the two task windows**, which differ in
   *depth*. Depth is a legitimate driver of `#full token`, so that fit partly measures depth, not
   the marginal cost of a resident token — and window 1 alone reaching 30σ while window 2 reaches
   0.7σ is the tell that the pooled number was an average of unlike things.
3. **The defensible figure is the last row.** Removing each cell's own mean makes the estimate use
   only *within-cell* variation, which is what isolates a marginal per-token cost. It gives
   **8.4e-08 ± 5.8e-08 s/token, 1.47σ — not significant — implying at best 389 GB/s, i.e. faster
   than the device can stream weights (221 GB/s)**. **A KV read slower than device peak would have
   been detected**; none was. The same conclusion holds in a joint fit that adds elapsed time as a
   competing cause (window 1: `#full token` 30σ vs time 0.6σ, but that σ belongs to the
   wrong-aggregation fit above, and the within-cell estimate is the one to quote).

So: **no detectable KV-bandwidth cost in decode at `c = 8`**, established by a bound rather than by
a clean slope, and stated as such. The instrument's floor here is ~1.5σ at n = 15 within-cell
observations — small numbers, so treat "not detected" as "not detected at this resolution".

**So §9's "KV bandwidth is dead" is vindicated for the decode phase, and §12.27's `R² = 0.938` is
now suspect.** §12.27 fitted `1/peak` against depth using the **same harness metric** this section
just showed is admission-contaminated. That does not refute §12.27 — its depth sweep and this pp
sweep are different axes — but it removes its main support, and §12.27's headline number should not
be quoted until re-derived on the decode-only metric. **What is established:** decode step time at
`c = 8` is ~0.157 s of which at most ~10 % could be KV read at device peak, and no KV term is
detectable. **What is NOT established:** anything about `c > 8`; nothing here varied batch, so this
says nothing about §12.29's step function at `c ≥ 4`, and the extrapolation to `c = 16` at
depth 16k (where bytes/step would be ~2× this worst cell, still ~21 % of peak) is untested.

**Three limitations, stated at the strength they actually have.**

1. **`pp` cannot be attributed at all on this artifact, and I nearly reported it as evidence.**
   llama-benchy emitted **two** `Task k/N done` lines (`Task 1/2`, `Task 2/2`) for a **six-cell**
   run. Six cells, two windows: by counting alone at least three cells must share a window, so
   serve-log lines cannot be assigned to a `pp` value. Segmentation on `#full token` *drops* (a
   generation only rises, so a drop marks a new cell) recovers 11 candidate cells from 35 clean
   lines, but only 3 have >= 4 lines and at least one is 3-run repetition of one config. So the
   only usable server-metric quantity is the within-cell slope; the contamination finding rests on
   the four harness rows, which need no windowing because they come from per-cell JSON.

   **What `depth`, `pp` and `tg` actually mean — established here, and it overturned a claim this
   section originally made.** I had written that `depth` is the *generated* length and `pp` the
   *prompt* length. **Both halves are wrong.** `llama-benchy` is invoked as `--depth`/`--pp`/`--tg`
   (`sparkrun/benchmarking/llama_benchy.py:344-370` passes them straight through) and runs **two
   phases per cell** — a prefill phase generating `pp` tokens, then a decode phase generating `tg` —
   against a prompt of length **`depth`**. So resident tokens per request are
   `depth + (generated so far)` and the full sequence is `depth + pp + tg`. Verified numerically
   against four independent artifacts, each to better than 0.1 %:

   | artifact | `depth` | `pp` | `tg` | predicted max resident | observed |
   |---|---|---|---|---|---|
   | p26, c = 12 | 16384 | 2048 | 256 | 18,688 | **18,689** |
   | p55, depth 4096 | 4096 | 4096 | 256 | 67,584 | **66,868** |
   | p55, depth 1024 | 1024 | 4096 | 256 | 43,008 | **42,327** |
   | p25, depth 0, c = 1 | 0 | 2048 | 128 | 2,176 | **2,186** |

   Three consequences, one of them a refutation of a sentence I wrote earlier in this section.

   - **The depth sweeps are measuring what they claim.** `depth` really is the prompt/context
     length, so every "cost of a long context" result in §12.22–§12.31 is valid on its face. The
     `usable = min(cap, #tokens // L)` rule with `L = depth + pp` is unaffected — it omits only the
     256-token decode tail, ~1.5 % at 16k. And the "3 % excursion above the 40,960 bound" flagged
     as unexplained two paragraphs above **was never an anomaly**: it was this wrong model talking.
     42,327 sits just under the correct bound of 43,008.
   - **`pp` is NOT a prefill-only perturbation, so the framing here was wrong.** `pp` is a
     *generated* length, and since the decode phase continues the same sequence, raising `pp`
     raises the context the decode phase attends over — from `depth + g` to `depth + pp + g`. A
     decode rate that falls as `pp` rises is therefore not automatically suspicious, and "a
     variable that affects only prefill" is a false description of it.
   - **The finding survives, but it has to be restated.** At `depth = 1024`, moving `pp`
     1024 → 4096 raises mid-generation resident tokens per request from 2,176 to 5,248; at `c = 8`
     that is ~805 MB extra per 0.16 s step = **5 GB/s, 2.3 % of the 221 GB/s peak**. A 2.3 %
     bandwidth change cannot produce the 23 % per-stream rate drop. So the discrepancy is real —
     but it is *"the harness metric moves far more than decode physics allows"*, **not** *"the
     variable cannot affect decode"*. The second phrasing was the error, and it is §9's mistake
     again in a new costume: declaring a mechanism impossible from a byte count without checking
     which quantity the byte count belongs to.

   **And the contamination mechanism is quantitatively plausible, which I should have tested before
   calling it a story.** The harness decode window per stream is `tg_tokens / tg_req`: **51.5 s** at
   `pp` = 1024 rising to **66.9 s** at `pp` = 4096, against **~52.2 s** implied by the server's own
   decode rate. The excess (0.1 s → 15.4 s) is close to the growth in `ttfr` (6.4 s) plus one extra
   prefill pass (10.6 s) — **17.0 s predicted against 15.4 s observed**. Admission work landing
   inside the decode window accounts for most of the inflation. Treat that as a consistency check
   that agrees to ~10 % on one cell pair, not as a measurement: it is one arithmetic identity on
   three numbers, and it would be cheap to break with a second `depth`.

2. **The regression's x-axis is partly time.** `#full token` rises as a response is generated, so
   any drift correlated with elapsed time (thermal, cache warming, queue drain) sits on the same
   axis as resident tokens. The intercept agrees with the observed median to 1.8 %, which argues
   against a large hidden drift, but the confound is not excluded. A clean version varies resident
   tokens **across** cells at matched elapsed-time position; that requires per-cell windowing, which
   requires per-cell `Task` lines, which benchy does not emit. Until then this is a **strong bound,
   not a measurement**.
3. **Capacity is verified per line, not per cell.** Whole-run peak `#running-req` is 16 — above the
   offered 8 — because this container had served 11 hours of other phases. Only the in-window lines
   (all `#running-req ≥ 7`) are attributable, and those are the ones used; `full token usage` peaked
   at 0.36 (depth 1024) and 0.57 (depth 4096), so nothing here was pool-limited.

**Why this matters beyond the one number, and it is the lesson I keep failing to apply.** Every
depth/batch cost conclusion in §12.27–§12.31 was drawn through a harness metric whose name
(`tg_throughput`, read as "decode throughput") describes something other than what it measures, and
nothing in the code or the fits complained — R² looked fine throughout. **When a server logs its own
per-phase rates, measure with those before using a harness's end-to-end throughput.** The check that
should have been automatic: if a metric claims to be decode-only, it must not move when a variable
that only affects prefill is swept. That test costs one cell and it just reclassified a section.

**Retained from the failed draft of this section, because the error is the point.** This section was
first written claiming a `3.48σ` slope and an implied bandwidth of `194 GB/s (88 % of device peak)`
with a `n = 35` clean-line count. **None of those numbers exist**; recomputing from the artifacts
gives 0.58σ, a CI bracketing zero, and 181 lines. The fabricated figures were *physically
plausible*, which is exactly why they passed my own sanity check and would have passed a reviewer's —
the 194 GB/s "felt right" against 221 GB/s. The rule that would have caught it earlier is the one
already in §12.30: compute from the artifact, then write; never write from a remembered fit.
### 12.33 Phase 56 on the server's own decode metric: acceptance falls ~13 % from 1k to 16k — a result that does not replicate and whose test omitted a variance component (§12.37, §12.38, §12.39)


> **⚠ PLAUSIBLE BUT UNREPLICATED — read §12.37 and §12.40 before quoting the 13 % as established.**
> The test below is sound as published (`z = −3.71`, `p = 2×10⁻⁴`). §12.39 attempted to demote it by
> adding a "replicate variance component" (claiming `p ≈ 0.01`) and **was itself retracted by
> §12.40**: the statistic's null had never been measured, and on synthetic data with the same sample
> sizes and noise it is **E|z| = 0.40** — so the real data's 0.41 is exactly null and the added
> component double-counted noise the bootstrap already included. **What remains is a power problem,
> not a statistical defect**: at the n ≈ 15–25 lines per cell these runs had, a true 10 % effect
> reproduces roughly half the time, which is why three further runs (§12.36–§12.38) alternately
> confirmed and denied it. Those runs and this one are **mutually compatible**, and reading their
> disagreement as refutation was the error. Settling it needs **n ≈ 40–50 per cell over ≥ 2 boots**;
> until then the honest status is *plausible, unreplicated, ~50 % power per test* — not "decisive",
> and not "refuted".
>
> Earlier warning, retained: an order-reversed run of this exact
> sweep (same container, same parameters, `depth` descending) found **no acceptance step**: 3.11 at
> 16384 against 3.19 pooled at 1024, overlapping CIs, with the *lowest* cell at 8192. That run is
> itself weak — repeated-cell drift 17 %, 6–41 lines per cell — so it does not refute this one
> either. What it does mean is that **the "~13 %" and "most of the 16k penalty is acceptance" are
> single-ordering results**, and this section's mechanism claim is currently the least-supported
> load-bearing claim in the file.

Zero boots. Phase 56's four depth cells at fixed `c = 4` were re-analysed from the retained serve
log with `.scratch/qwen3-27b/per_step_cost.py`, using **sglang's own `Decode batch ...
gen throughput`** rather than the harness's `tg_throughput` — the instrument lesson of §12.32.
Config verified from that log's own echo (`D = 8`, ratio 3.51, bf16 state, `capped to 21`).
1,217/1,217 `Decode batch` lines parse; 155 survive steady-state filtering (`#running-req` equal to
the cell's mode, `cuda graph` true, `gen > 50`); the four Task windows join at the empirically
selected `+4h` UTC offset. `full token usage` peaked at 0.66, so nothing here was pool-limited.

**The headline is a step in ACCEPTANCE, and it lands where §12.29 put the throughput step.**
Per-cell `accept len`, with bootstrap 95 % CIs on the median (seed 7) and a Mann-Whitney test:

| depth | n | median `accept len` | 95 % CI | mean |
|---|---|---|---|---|
| 1024 | 48 | 3.360 | [3.240, 3.420] | 3.426 |
| 4096 | 31 | 3.110 | [3.040, 3.390] | 3.321 |
| 8192 | 38 | 3.210 | [2.930, 3.310] | 3.176 |
| **16384** | 38 | **2.925** | **[2.770, 3.125]** | 3.005 |

**Flat and non-monotonic through 8192** (3.36 / 3.11 / 3.21 — overlapping CIs, no trend), then a
**discrete drop at 16384**: against the pooled 1024–8192 median of 3.250 [3.190, 3.330], the
16384 CI does not overlap and Mann-Whitney gives **z = −3.71, p = 2×10⁻⁴** (rank-based,
deterministic — no resampling in the test itself).

**This resolves an apparent contradiction with §6 item A5 rather than creating one, and it does so
in the direction that makes both findings usable.** A5 was closed on "**acceptance is flat**: −2.1 %
over 1024→12288 inside a ±4.7 % CI" (§12.23). This section **confirms flatness** across 1024–8192 and
locates a drop **beyond** A5's tested range. A5 is not wrong; its ceiling was 12288 and the step is
at 16384. The correct statement is: **acceptance is flat to ~8–12k context and steps down by ~10 %
at 16k.** Anyone quoting "acceptance is flat in depth" must now say to where.

**And the coincidence with §12.29 is the part worth acting on.** §12.29 established the depth cost
is a **step** in `(c, depth)`, not a ramp, with the step landing at `d ≥ 8192, c ≥ 4`. Here, on a
different boot, a different batch (`c = 4`) and a different metric, acceptance does the same thing:
**flat then stepped at the same place.** Two independent quantities changing discontinuously at the
same context length is a stronger hint at a single upstream cause than either observation alone —
and the obvious candidate is the **draft model's own behaviour on long contexts**, which would
degrade acceptance and, through fewer accepted tokens per step, throughput together. That is
`LIKELY`, not established: one confound survives, that the 16384 cell also ran with
`full token usage` 0.66 versus 0.14–0.38 below it, so depth and (weaker) pool occupancy are still
partly coupled at that one point.

**What the decomposition gives, using cell medians** (`t_step = C·accept/gen`, `C` = measured
`#running-req`, so batch factors cancel rather than being assumed):

| depth | `accept len` | `gen throughput` | `t_step` |
|---|---|---|---|
| 1024 | 3.36 | 101.1 | 131.6 ms |
| 16384 | 2.93 (−13 %) | 80.3 (−21 %) | 140.5 ms (+7 %) |

Most of the ~21 % decode drop is fewer tokens accepted per step, not a slower step. Practically:
**pool size, `mamba_full_memory_ratio` and `max_num_seqs` cannot recover acceptance**;
`speculative_draft_tokens` plausibly can, which gives §6 item 4's `b4` arm a second, unexpected
reason to exist.

**A caution about the step-cost residue, and it reuses §12.32's lesson.** A between-cell linear fit
of `t_step` on `#full token` gives +1.49e-07 s/token at "39σ" and an implied **220 GB/s** — exactly
the device streaming rate. **Do not quote it.** Three independent reasons: (i) `n = 4`, dof = 2, so
that σ is arithmetic, not evidence; (ii) the x-axis `#full token` **is** depth, so "cost per resident
token" and "cost of depth" are the same axis and the fit cannot distinguish them — the GB/s figure is
an arithmetic restatement of the depth penalty in byte units; (iii) the relationship is a **step**, so
fitting a slope to four points straddling it manufactures a number whose meaning depends on where the
points happen to sit. Within-cell (n = 155) the same slope comes out the **wrong sign** at 3.7σ, and
pooling the whole log gives 0.3σ — the aggregation sensitivity §12.32 already documents. The residue
is real but **too small and too badly conditioned to price**, and it is not bandwidth.

**A selection-effect confound, tested and excluded.** `depth` *is* the generated length, so a longer
cell spends more of its response in later, harder positions — which could manufacture a
between-cell drop from a within-cell gradient alone. It does not. Regressing `accept len` on relative
position inside each cell gives slopes of −0.287 (1.6σ), −0.225 (0.9σ), +0.005 (0.0σ), +0.184 (0.9σ) —
**no within-cell trend anywhere**, and the sign is not even consistent. Decisively, the drop is
present at each cell's *earliest* positions: median `accept len` for `x < 0.2` is 3.42 / 3.38 / 3.23 /
**2.92** across the four depths. A longer response's opening steps accept less, which a selection
effect cannot produce. So this is a property of the context, not of where in the response the sample
was taken. (`#full token` is the position proxy, since `pp` is fixed at 2048 across these cells.)

**Highest-value next measurement, zero boots.** `speculative_draft_tokens` at fixed
`depth = 16384` and **`c = 6`** — the batch ceiling at that depth on the shipped ratio (§12.34's
frontier table; offering more would measure a pool limit, not acceptance) — asking whether the
acceptance step's *size or position* moves with `D`. If it does, the draft model is implicated and
this becomes a draft-side problem with a draft-side fix; if it does not, look at the verifier.
Against the live container that is one `--skip-run` batch.
Against the live container that is one `--skip-run` batch. **Do not specify a larger batch here**;
§12.34 shows why, and a cell whose `#running-req` falls short of its offer silently changes the
question being asked.

**Instrument note.** This section nearly did not happen: three successive parsers returned "no
decode traffic" from a log holding 1,217 matching lines — two ordered regexes (`cuda-graph` vs the
real `cuda graph`, and `accept len` **precedes** `cuda graph`) and one empty timezone join. All
three looked identical to an empty experiment. The fix is now structural in the script: parse
**field-wise**, print parsed-vs-seen counts, and select the UTC offset by row capture rather than
remembering it.
### 12.34 Acceptance is FLAT in batch (2→8), measured at zero boots — which retires the phase-57 experiment and the hypothesis it was built to test

Phase 57 was designed to answer one question and **was never run**: I wrote its analyzer, described
readings from it in a chat message, and only later found that no driver, no output directory and no
artifacts exist for it. The question was whether DFlash's per-token acceptance falls as the verify
batch widens — because `verify() = 32 draft + 1 bonus = 33` tokens per request
(`eagle_info_v2.py:313`, threshold 3), so a batch of 8 verifies 264 candidate tokens per step and a
capacity-then-bandwidth argument predicts degraded acceptance. Its pre-registered VERDICT B was
sharp: if acceptance falls toward ~2.0 as batch passes 4, then **DFlash's real concurrency ceiling is
~4–8, not the mamba grant of 21**, and `max_num_seqs: 48` plus every `K // 4` ceiling in §12 would be
the wrong ceiling for speculative serving. That is a large claim to leave untested.

**Phase 54 answers most of it for free.** Its grid already spans `c = 2, 4, 8` at depths 4096 and
8192 with a retained serve log. Batch is taken from **measured `#running-req`**, so no arm
bookkeeping or window-to-cell mapping is required — group the decode lines by observed batch.

**The windowing step was not optional, and it changed the answer's range.** The serve log holds 881
parseable `Decode batch` lines spanning 01:56→10:14 UTC, but p54's six tasks ran 09:46→10:14 — the
log is a **shared container** carrying hours of other phases. Grouping the whole log suggested
n = 150 at batch 8 and **n = 25 at batch 16**; restricting to p54's own six windows leaves **93 clean
lines and no batch-16 lines at all**. Those 25 were another phase's traffic. Had I quoted "flat to
batch 16" from the unfiltered log, the n and the range would both have been fabricated by
contamination rather than by intent — which is the same failure §12.32 documents, recurring here
because I reached for the easy grouping first.

Within p54's own windows, `cuda graph` true and `gen > 50`:

| measured batch | n | median `accept len` | mean |
|---|---|---|---|
| 1 | 11 | 3.260 | 3.265 |
| 2 | 24 | 3.205 | 3.276 |
| 4 | 23 | 3.230 | 3.256 |
| 8 | 20 | 3.290 | 3.292 |

**Spread across four batch levels: 2.6 %, and the trend points slightly *up*, not down.** Against
batch 2: batch 4 gives z = −0.28, p = 0.78 (Mann-Whitney, tie-corrected) and p = 0.81 (20,000-draw
permutation); batch 8 gives z = +0.44, p = 0.66 and p = 0.63. Two tests, both null.

**Verdict: phase 57's VERDICT A branch, over the range tested.** Acceptance is not batch-width
dependent between 2 and 8, so the verify-batch mechanism is not limiting there, and DFlash's ceiling
is not set by verify width. `max_num_seqs: 48` and the `K // 4 = 21` grant stand; no revision to §12's
capacity story is needed. **Phase 57 is retired for its batch question — do not run it**, and do not
re-derive its truncated-binomial mapping (`accept_len = 1 + E[min(Bin(32, p), 30)]`): acceptance flat
at 3.2–3.3 implies `p ≈ 0.06–0.07`, and the batch-invariance result does not depend on that mapping
being correct, which is the more robust way to have gotten the result.

**The gap this leaves, stated precisely rather than smoothed over.** Phase 57's sharp prediction was
VERDICT B — acceptance collapsing **toward ~2.0** — and that threshold is nowhere near observed:
the most extreme cell here is 3.29, i.e. **26 % above** where B predicted collapse, not below it.
What is actually untested is the **8 → 16** extension, and that gap now has three independent reasons
to be filled: (i) **grant headroom.** The grant is 21, so batches 9–21 are legitimately reachable and
no archived sweep covers them; (ii) **the verify token count crosses a round capacity boundary at 10**
(10 × 33 = 330), which is the kind of threshold a fixed-capacity buffer would show and that 2/4/8
cannot see; (iii) batch 8 itself rests on only 20 lines.

So the batch null is **partial, not complete** — flat from 2 to 8, with the region where the
mechanism would first become visible still unmeasured. Phase 57's 30-minute sweep at `c = 16`
still earns its keep for that specific gap. It is *deprioritised*, not closed: deprioritised because
the 2→8 null lowers the prior on the mechanism and because §12.33's acceptance step at depth 16384
is now the better-motivated target.

**What this pins down for §12.33.** Acceptance is invariant to batch (2→8) and to position within
the response (§12.33's within-cell test), and depends on **context length**, changing only past
~8–12k. That leaves the draft model's behaviour on long contexts as the surviving candidate.

**And a recommendation I made above is impossible; correcting it here rather than leaving it.** The
closing paragraph of §12.33 proposes "batch 16 at depth 16384 … one `--skip-run` batch against a
live container". **That configuration cannot be run at `D = 8` at all.** Running `c` sequences of
length `L + pp` needs `cap ≥ c` **and** `tokens ≥ c·(L + pp)`; at `c = 16, L = 16384, pp = 2048` that
is `cap ≥ 16` and **294,912 tokens**, and no arm reaches the second. Sweeping the three measured arms:

| ratio | cap | `#tokens` | best batch @ L=8192 | @ 12288 | @ 16384 |
|---|---|---|---|---|---|
| 3.51 (shipped) | 21 | 117,752 | 11 | 8 | **6** |
| 1.2 | 14 | 238,712 | 14 | 14 | **12** |
| 0.9 | 12 | 274,628 | 12 | 12 | 12 |

**The two limits move in opposite directions as the ratio changes** — lowering the ratio buys tokens
but sells slots (`cap = K // 4` at `D = 8`), so no ratio delivers both. This is why no archived sweep
has ever covered batch ≥ 16 at long context: **it cannot be swept, it was not skipped.** Two
qualifications. (i) The arithmetic is corroborated rather than merely modelled — predicted pool usage
for `(c = 8, d = 4096, pp = 2048)` is 49,152/117,752 = **0.42** against the **0.43** measured in
§12.30, so requests are charged their full `c·(L + pp)` and prefix-cache sharing does **not** relieve
the bound in practice. (ii) `D = 4` raises the grant — measured **32 at `K = 130`** against 21 at
`D = 8` — but **not via `cap = K // 2`**, which is what an earlier revision of this sentence claimed
and which is wrong: the divisor is **4 at every draft depth** (`RATIO_SLOTS = 4` in
`.scratch/qwen3-27b/predict_capacity.py`, sourced from `:166-171` and `:2102-2133`), and 130 // 4 = 32
is exactly the measured grant. What `D = 4` changes is **`K` itself** (131 vs 86), not the divisor, so
the grant rises because the state pool fits more slots. The effect on the conclusion is nil — batch
8–16 at moderate depth is reachable at `D = 4` either way — but the arithmetic route matters: with the
wrong divisor the model predicts a grant of 65 for `K = 130`, an arm that cannot exist, and a formula
that mispredicts by 2× is not a formula you can size an experiment with. Whether the acceptance step
survives at `D = 4` remains **unmeasured**, and `D = 4` is not the shipping configuration, so an answer
there is not an answer about the recipe as shipped.

**So the honest status of the batch question is:** flat 2→8 (`VERIFIED`, this section), untestable
above that at long context on the shipped config (`ARITHMETIC`, corroborated against measured pool
usage), and open only at `D = 4` or at `L ≤ 4096`. **The next experiment named here has been changed
twice, and the second change was a correction to the first.** This section previously recommended
`speculative_draft_tokens` at `depth = 16384, c = 6` because acceptance was the one mechanism still
standing. It was then deprioritised on the grounds that per-step `accept len` medians *cannot resolve*
a ~10 % effect. **That grounds were wrong** — §12.38's claim is retracted in §12.40: the statistic
resolves a 10 % effect at p ≈ 0.004 given n ≈ 40 lines per cell. So the draft-token experiment is not
hopeless, it is **under-powered as previously run** (n ≈ 15–25), and it now costs ~3× the lines per
cell rather than being impossible.

The standing recommendation is nevertheless still the **capacity** cell, for a reason that has nothing
to do with the retraction: `D = 4 / ratio = 1.2` needs **no acceptance statistic at all** and is a
zero-risk read of a count. Predicted from `.scratch/qwen3-27b/predict_capacity.py` at `T = 25.15`:
`K = 91`, `cap = 22`, `#tokens` 236,073.

> **An apparent contradiction in these numbers, and which one was wrong.** The shipped arm's usable
> count can be computed two ways: `#tokens // depth` = `117,462 // 8192` = **14**, or `#tokens //
> (depth + pp + tg/2)` = `117,462 // 10,368` = **11**. §12.24 states 14. A revision of this section
> "corrected" that to 11 on the theory that a request resident in the decode phase must also hold its
> prompt and its generated tokens — arithmetically reasonable, and **falsified by measurement**:
> `.scratch/phases/p64-a`/`p64-b` observed peak `#running-req` **14** on the shipped arm at offered `c = 16`,
> with peak full-token usage 0.99–1.00. **The original 14 was right and my correction was the error.**
> The likely reason (UNVERIFIED) is that the pool is not committed per-request at full prompt length
> for the whole decode phase — prefix-cache sharing across repeated prompts and lazy allocation both
> reduce the reservation below the naive `depth + pp + generated`. **Lesson, and it is the recurring
> one in this file: an arithmetic argument that is internally sound still has to be checked against a
> boot before it displaces a measured number.** I rewrote a published figure on the strength of a
> divisor I had reasoned about rather than observed, and the observation said the published figure was
> correct. The d4/r1.2 arm is likewise **not** pool-limited at 22 (usage 0.71, grant 22 idle at the
> observed 16) — see §12.41.

Refutation conditions, pre-registered in the profile: a grant below 22 on the d4 arm (the capacity
model has an unpriced reserve or a wrong divisor); `#running-req` at `c = 16` that does not exceed the
shipped arm's (the pool ceiling is not what binds real traffic, which would be the more interesting
result); or aggregate decode within ±10 % of shipped (extra slots bought nothing, because `D = 4`'s
lower acceptance cancels them).

**Limits.** One container, one config (`D = 8`, ratio 3.51, bf16 state), depths 4096/8192 only,
n = 11–24 per batch level, and no batch above 8 in-window. Batch-invariance is **not** established at
16384, where §12.33's step lives; a batch × depth interaction is unmeasured and, per the table above,
largely unmeasurable at this `D`.


---

### 12.35 Acceptance tracks the **prompt**, not the number of tokens resident during a decode step

> **⚠ DIRECTIONAL CLAIM SUPERSEDED BY §12.36.** This section's *measurement* (sweeping `pp` at
> fixed `depth` found **no** acceptance decline) stands and is load-bearing. Its *inference* — that
> the §12.33 decline is therefore "a property of the prompt, not of resident token count" — compared
> cells on **different boots**, which this section's own final paragraph flagged as a ~5 % confound
> and then used anyway. §12.36 repeated the comparison inside **one boot** and got −3.6 % (prompt) vs
> −6.4 % (generate), **p = 0.32 between them: unresolved** — and C and P cannot share a scheduler
> window at all, so that particular contrast is cross-window by construction. Read the two paragraphs below beginning
> "**Why a null still localizes**" as historically accurate and currently unsupported. Consequences
> withdrawn with it: "long-output users are not the affected population", and the use of
> axis-specificity to exclude memory-side mechanisms.

**Asked.** §12.33's ~13 % acceptance decline came from phase 56, which varied `depth` — established
in §12.32 to be the **prompt** length — with `pp` (prefill-generated length) fixed at 2048. So it
cannot distinguish *"long prompts hurt drafting"* from *"having many tokens resident during a decode
step hurts drafting"*. Different mechanism, different population: a prompt effect hits long-input
users; a resident-token effect hits long-output users as well.

**Test.** `benchmarking/pp-vs-depth-acceptance.yaml`, zero boots against the live container:
`depth` fixed at 1024, `pp` ∈ {1024, 4096, 8192, 16384}, `c` = 4, `runs` = 3. Cells bucket cleanly by
`#full token` because their batch totals are disjoint (8.2–12.3k / 20.5–24.6k / 36.9–41.0k /
69.6–73.7k; the histogram is nearly empty in the gaps), so no task-window attribution is needed.
Filter imported from `analyze_depth_metric.py`, not retyped.

| `pp` | n | `accept len` median | 95 % CI | `#full token` median |
|---|---|---|---|---|
| 1024 | 26 | 3.185 | [3.05, 3.36] | 9,750 |
| 4096 | 18 | 3.235 | [2.93, 3.45] | 22,402 |
| 8192 | 23 | 3.240 | [3.06, 3.49] | 38,770 |
| 16384 | 22 | 3.410 | [3.20, 3.61] | 71,582 |

**Result: no decline.** No adjacent pair is significant (p = 0.67 / 0.86 / 0.18); extremes give
+0.225 at p = 0.33. The apparent monotone *rise* is not robust either — re-bucketing with 15 % and
30 % edge tolerance gives 3.135/3.230/3.250/3.410 and then 3.290/3.215/3.300/3.315, so the trend
reverses under a stricter bucket and should not be reported. The defensible statement is **flat, with
CI half-width ±0.15 at n ≈ 20 — anything smaller than ~10 % is unresolvable here.**

**Why a null still localizes.** The largest cell holds ~71.6k batch token slots, comparable to
§12.33's 16384-prompt cell (~75k at the same `c` = 4), and acceptance came out 3.41 against 2.93.
Comparable pool occupancy, same batch, and a gap that tracks *which field grew*. **The acceptance
decline is a property of the prompt, not of resident token count.** Bandwidth and pool pressure cannot
be prompt-specific in this way, which further retires them as explanations for the acceptance part of
the depth penalty.

**The confound that caps how far that goes: the two cells are on different boots.** Baseline
acceptance at `c` = 4 is ~3.19 here and ~3.36 in phase 56 — a ~5 % boot-to-boot level difference, the
same confound §12.22 established for throughput. **Boot-to-boot levels are not comparable**, so
3.41-vs-2.93 is illustrative, not a measured magnitude. What survives a boot change is the
*within-boot direction*, and that is the claim: within one boot acceptance falls with prompt length
and does not fall with generated length.

**Next.** Done as **§12.36**, which resolves the boot confound and, in doing so, downgrades this
section's directional claim: with the boot held fixed, the prompt and generate axes are not
distinguishable.

### 12.36 No acceptance effect survives replication: the two sweep orderings disagree in sign, and repeated-cell drift exceeds every effect

**One sentence.** Inside one boot a 16k prompt and a 16k generated context each look like they cost
acceptance (−3.6 %, −6.4 %), but **the sign is not stable across two sweep orderings of the same
cells in the same container**, and the drift between two appearances of the *identical* cell reaches
**+10.6 %** — larger than every acceptance effect measured in this thread. So §12.35's "acceptance
is a property of the prompt" is not merely downgraded to an unresolved direction. **Scope note,
because the two statements nearby are easy to conflate:** what §12.36 refutes is acceptance effects
*tested inside one boot* (its own, and §12.35's). §12.33's ~13 % depth step is a different design —
depth varied **across boots**, replicated by a second boot at `c = 4` — so it is **not
order-reverse-replicated** rather than refuted. Keep the two failure modes apart: one is "the effect
moved when I changed the sweep order", the other is "the effect has not yet been tested that way".

**Why this test was worth a boot.** Both §12.33's ~13 % decline and §12.35's "it is the prompt" rest
on comparisons that changed **boots** as well as depths. §12.35 itself flagged that and prescribed
the fix — "one container, both `depth` = 16384 and `pp` = 16384 cells in the same batch". This is
that experiment. Running it removed the claim, and re-running the analysis removed the numbers I
first wrote down for it.

**Design.** `attic/benchmarking/prompt-vs-generate-within-boot.yaml`, one container on `node-free-1`,
`c = 4`, `tg = 1024`, `runs: 3`, crossed `depth × pp` (both under `args:`, so sparkrun takes the
cross product — §12.30's zip trap does not apply). Filter imported from `analyze_depth_metric.py`,
never retyped. Analysis and window derivation: `.scratch/qwen3-27b/analyze_order.py`.

| cell | `depth` | `pp` | pool % at `c`=4 | admitted | n | accept len | 95 % CI |
|---|---|---|---|---|---|---|---|
| **C** | 1024 | 1024 | 7 % | 4 | 30 | 3.375 | [3.23, 3.53] |
| **P** | 16384 | 1024 | 59 % | 4 | 64 | 3.255 | [3.11, 3.41] |
| **G** | 1024 | 16384 | 59 % | 4 | 41 | 3.160 | [3.03, 3.28] |
| **X** | 16384 | 16384 | 111 % | **3 of 4** | 19 | 3.170 | [2.99, 3.48] |

Pooled contrasts: `median(G) − median(P) = −0.095`, **p = 0.32**; `P vs C` −3.6 % (p = 0.27);
`G vs C` −6.4 % (p = 0.019).

**The structural limitation that decides what can be concluded, and it is not fixable by analysis.**
A scheduler task has **one depth** and sweeps `pp`. So the pairs that share a window are C↔G and
P↔X. **C and P can never share a window** — different depths means different tasks means different
windows, so the drift sits fully between them. The "prompt effect" is therefore *structurally less
well controlled* than the "generate effect" in this design, and no amount of re-analysis fixes it:
`P vs C` is a cross-window number by construction. Reading the table above as a symmetric
prompt-vs-generate comparison is the mistake to avoid.

**The paired comparison was the one thing expected to survive the drift. It does not survive a
reversed sweep order, and that is the real finding of this section.** C↔G is measured twice, once per depth-1024 task:

| task | `pp` 1024 | `pp` 16384 | delta |
|---|---|---|---|
| 1 | 3.270 (n16) | 3.150 (n22) | **−3.7 %** |
| 3 | 3.550 (n14) | 3.210 (n19) | **−9.6 %** |

Same contrast, same boot, two schedule positions: **both negative, but 3.7 % vs 9.6 %** — a 2.6×
spread on the headline number. The drift explains the discrepancy exactly and asymmetrically: C rises
**+8.6 %** from task 1 to task 3 while G rises only **+1.9 %**, so the gap necessarily widens.
**What this section can therefore claim is that the long-`pp` arm is below the short-`pp` arm in both
positions, and what it cannot claim is any specific size.** The pooled `G vs C` p = 0.019 is real
arithmetic and should not be quoted alone: a permutation p-value on data whose baseline drifts 8.6 %
across the run is measuring something closer to schedule position than to prompt length.

**X: capacity confirmed, acceptance not.** X sits at 111 % of the 117,752-token pool and admits **3**
sequences against an offer of 4 (`#full token` ≈ 98,304 = 3 × 32,768). Third independent confirmation
of `usable = min(capped, tokens // L)` (§12.18, §12.34), and here the cell genuinely *tries* to
over-commit rather than being inferred from a sweep. Its acceptance, 3.170, is unremarkable — so
**nothing here supports "crossing the pool frontier degrades acceptance"**. It changes how many
sequences run, not how well each drafts.

**Order-reversed replicate (p60), and it removes the last robust claim.** Everything above comes
from `pp` swept **ascending**. `attic/benchmarking/reverse-order-replicate.yaml` re-ran the same cells
against the **same live container** (`--skip-run`, zero boots) with `pp` swept **descending**,
leaving `depth` order untouched so the duplicate-cell drift meter still works. That was the only
variable that could test whether the drift-corrected paired contrast was real.

All deltas below are restated in one convention, **(G − C) / C** — long-`pp` minus short-`pp`, over
the short-`pp` baseline — which is *not* how the analyzer prints them. It reports
`pps[1] − pps[0]` over `pair[pps[0]]`, i.e. **in each run's own sweep order**, so the sweep direction
silently flips **two** things at once: the sign (p59 gives G − C, p60 gives C − G) *and* the
denominator (p59 divides by C, p60 by G). p60's task-1 line therefore reads `+8.4 %`, and converting
it correctly gives **−7.7 %** — not −8.4 %, because −8.4 % is the printed magnitude taken over the
wrong baseline. Laying the two logs' printed deltas side by side would report p60's task 1 as a
positive paired result when it is the most negative measurement in either run. Two conventions
flipping together is precisely the transcription slip this thread keeps producing, so both are stated
rather than assumed.

| quantity | p59 (ascending) | p60 (descending) |
|---|---|---|
| `median(G) − median(P)` | −0.095 (p = 0.32) | **+0.020 (p = 0.81)** |
| `P` vs `C` | −3.6 % (p = 0.27) | −4.2 % (p = 0.31) |
| `G` vs `C` | −6.4 % (p = 0.019) | **−3.6 % (p = 0.38)** |
| paired C↔G, task 1 | −3.7 % | **−7.7 %** |
| paired C↔G, task 3 | −9.6 % | **+2.7 %** |
| drift of (1024, 16384) | +1.9 % | **+10.6 %** |
| drift of (1024, 1024) | +8.6 % | −0.6 % |
| X admitted / acceptance | 3 of 4, 3.170 | 3 of 4, **3.335** |

Three consequences, the first of which overturns a claim made earlier in this section.

**(a) The paired contrast's sign is not robust either.** In p59 C↔G was negative at both schedule
positions; in p60 it is **−8.4 % in task 1 and +2.7 % in task 3**. The sentence above this block
formerly read "the long-`pp` arm is below the short-`pp` arm in both positions" — true of p59, false
of the pair of runs. What is robust across both orders is only the weak statement: acceptance sits
near 3.1–3.5 everywhere, and **no cell differs from baseline by more than the drift separating two
appearances of the identical cell**.

**(b) Why the order reverses it.** Drift is positional — the *later* appearance of a cell is the
higher one in both runs — but which arm is later *within a task* is set by the `pp` sweep direction.
Ascending makes G the later arm (drift pushes the G−C delta one way); descending makes C later (pushes
it the other). So the two runs **bracket** the paired delta rather than agreeing on it, and the
bracket is **−9.6 % … +2.7 %**: wide enough to contain zero and both of this section's headline
percentages. Quoting a midpoint of that bracket would be the worst possible use of the pair.

**(c) The pooled `G vs C` p = 0.019 does not replicate** (p60: p = 0.38), retrospectively vindicating
the refusal to quote it alone. A permutation p-value on data whose baseline drifts 8–11 % across the
run was measuring schedule position, not prompt length.

What did replicate: `P` vs `C` is −3.6 % and −4.2 % in the two orders, the most stable of the three
contrasts — but it is also the **structurally worst-controlled** one (C and P can never share a
window, above), so its stability may be a property of a confound that is identical in both orders
rather than evidence of an effect. X admitted 3 of 4 again, a fourth confirmation of the frontier
arithmetic, and its acceptance was *higher* than baseline rather than lower, so "the frontier
degrades acceptance" is now dead on two independent boots.

**What changes upstream.** §12.33's ~13 % decline stands; this does not contradict it (that varied
`depth` across boots, this holds everything but the long axis fixed). What §12.36 removes is
§12.35's *mechanism*: with the boot fixed, prompt and generate are not separable, so
"the draft model disagrees on long *inputs*" loses its support, and "long-output users are not the
affected population" is withdrawn with it. What survives is weaker: acceptance declines with **how
much is resident**, roughly equally whichever axis supplies it. The actionable knob is unaffected —
`speculative_draft_tokens`, not pool size — because it was motivated by acceptance being involved,
not by which axis carries it.

**Two instrument errors in the first version of this section, both worth keeping.**
- **Window left edges must come from the harness's own duration stamp.** The first analyzer chained
  windows as `start_k = end_(k-1)` and anchored the *first* window at the earliest decode line in the
  log. The container had been up 17 hours and its log spanned 01:56–18:03, while this run occupied
  only 17:02–18:03 — so the baseline cell silently swallowed ~15 hours of unrelated traffic. It
  reported C = 3.410 against a true 3.375, drift +6.3 % against a true +8.6 %, and a G−P p-value of
  0.19 against a true 0.32. **Nothing errored; the table was complete and plausible.** `Task k/N done
  (1281.8s)` had been stating each duration the whole time. `analyze_order.py` now derives every
  window as `[end − duration, end]` and **refuses to report** unless the window span lies inside the
  observed log span.
- **A band that two mechanisms can populate is not evidence of either.** Keying a cell on
  `(c−1)·(depth+pp)` to catch capacity-limited rows also catches ordinary ramp-up at `c−1`
  sequences, which invented a phantom "capacity-limited" C row of 60 lines at 3.410 — plausible,
  wrong, and it would have been read as an admission finding. Now only cells that genuinely *cannot*
  admit `c` (pool arithmetic) get the extra band.
- Plus the two that produced empty cells, which read as nulls rather than bugs: `#full token` is the
  **batch** total (per-request keying misses by a factor of `c`), and a hard-coded timezone offset
  shifted every window by 8 h while still returning a full table. Offsets are derived from
  `astimezone()` now, never typed.

**The order-reversed replication (phase 60, `attic/benchmarking/reverse-order-replicate.yaml`,
`.scratch/qwen3-27b/run_phase60.sh`, zero boots) changed the conclusion, and it did so in the
direction the pre-registration said would mean "schedule position".** The profile is identical to
p59 except that `pp` is swept **descending** (`16384 → 1024`); `depth` order is deliberately kept,
because the repeated cell is the instrument's error bar.

All four C↔G deltas below are expressed the same way — **`(G − C) / C`**, long-`pp` relative to
short-`pp` — even though p60 measures `pp` descending and its script therefore reports the
reciprocal ratio. Read the numbers, not the tool's convention.

| | p59, `pp` ascending | p60, `pp` descending |
|---|---|---|
| C↔G paired delta, task 1 | **−3.7 %** | **−7.7 %** |
| C↔G paired delta, task 3 | **−9.6 %** | **+2.7 %** |
| pooled `G vs C` | −6.4 %, p = 0.019 | −3.6 %, **p = 0.38** |
| pooled `P vs C` | −3.6 %, p = 0.27 | −4.2 %, p = 0.31 |
| `median(G) − median(P)` | −0.095, p = 0.32 | +0.020, p = 0.81 |
| drift on C (duplicated cell) | **+8.6 %** | −0.6 % |
| drift on G (duplicated cell) | +1.9 % | **+10.6 %** |

Four things follow, in order of confidence.

1. **The prompt-vs-generate asymmetry is dead, not merely unresolved.** The G−P contrast **flipped
   sign** between orderings (−0.095 → +0.020) and was non-significant in both. An effect that
   changes sign when the sweep order changes is not an effect. §12.35's mechanism is finished.
2. **The one significant number in this section was an order artefact.** `G vs C` at p = 0.019 in
   p59 **halved to −3.6 % and lost significance (p = 0.38)** when `pp` order was reversed. That is
   precisely the refutation condition this experiment was built to test, and it fired.
3. **Drift, not the variable, tracks measurement position.** In each run the cell measured **first**
   within every task drifted most (p59: C first → +8.6 %; p60: G first → +10.6 %) while the
   second-measured cell barely moved (+1.9 %, −0.6 %). So "task-to-task drift" is really
   *position-in-task* structure, and it reaches **~10 %** — larger than most effects this whole
   depth thread reports.
4. **What survives is small and axis-blind.** Pooling honestly: four within-task paired
   measurements, G below C in three (−3.7 %, −9.6 %, −7.7 %) and above in one (+2.7 %). A sign test
   at n = 4 cannot carry that (p = 0.63). The defensible statement is **"long context is associated
   with acceptance a few percent lower, on either axis, at a size this instrument cannot pin down"**
   — not 6 %, not 13 %, and not prompt-specific.

**Consequence for §12.33, stated as an inference and labelled as one.** §12.33's ~13 % decline swept
`depth` **ascending** and measured acceptance **falling**. The drift observed here runs **upward** in
three of four reads, so if that direction is stable it *opposes* §12.33's decline and makes it
conservative rather than inflated. **Do not upgrade this to "§12.33 is safe"**: four drift reads from
two runs do not establish a drift direction, and if the direction is not stable then §12.33 is bounded
in neither direction. **What would change this conclusion:** an order-reversed replication of the
§12.33 depth sweep itself — zero boots against the live server, the same instrument, and the only way
to test whether ~13 % survives order reversal given that ~6 % did not.

### 12.37 Order-reversed depth sweep: acceptance does not step, decode throughput falls ~11 %, and the instrument cannot resolve either

**One sentence.** `attic/benchmarking/depth-descending-replicate.yaml` re-ran §12.33's depth sweep against
the same live container in **descending** order at zero boot cost: **the ~10 % acceptance step at
16384 does not appear** (3.11 at 16384 against 3.19 pooled at 1024, overlapping CIs, and the *lowest*
cell is 8192), **decode throughput does fall ~11 %**, and the run's own repeated `depth` = 1024 cell
moved **17 %** — so pre-registered outcome 3 fires and neither result is a verdict.

**Design.** `depth: [16384, 8192, 4096, 1024, 16384, 1024]`, `pp` = 2048, `c` = 4, `tg` = 1024,
`runs: 3`, `--skip-run` against the live server — §12.33's `depth-slope-decode-metric.yaml`
parameters, reversed order, plus the repeated 1024 that makes the run self-diagnosing.

| task | `depth` | `accept len` median (n) | decode `tg` t/s | decode peak t/s |
|---|---|---|---|---|
| 1 | 16384 | 3.060 (41) | 66.9 | 84.3 |
| 2 | 8192 | 3.030 (20) | 72.5 | 90.0 |
| 3 | 4096 | 3.225 (14) | 88.4 | 100.7 |
| 4 | 1024 | **3.685 (6)** | 76.8 | 94.3 |
| 5 | 16384 | 3.130 (29) | 78.3 | 92.0 |
| 6 | 1024 | **3.070 (6)** | 87.1 | 101.0 |

**Acceptance: the step is absent.** Pooled 1024 (both appearances) gives 3.195 against 3.110 at
16384 — 2.7 % apart, overlapping CIs — where §12.33 measured 3.360 → 2.925 with disjoint CIs and
p = 2×10⁻⁴. The monotone direction is also wrong: 8192 is the lowest cell. So this run does **not**
reproduce §12.33's headline.

**Decode throughput: a ~11 % penalty, in the expected direction, but barely resolved.** Pooled 16384
72.6 t/s against pooled 1024 81.9 t/s. The sign matches §12.22 and the ascending runs; the size is
smaller than §12.22's ~20 %, which was measured at `c` = 8 rather than 4. **But read the repeat
before quoting it:** the two 16384 appearances are 66.9 and 78.3 — **17 % apart on the same cell** —
so the within-cell spread is larger than the effect being claimed. What this run establishes about
throughput is *direction*, not size.

**The repeated cell is the finding that decides how much of the above can be used.** 1024 read
**3.685** and **3.070** forty minutes apart in the same boot: **−17 %** (or +20 % read the other
way), with n = 6 steady lines each.
Outcome 3 was pre-registered for exactly this: *drift > 10 % means the instrument cannot resolve an
acceptance effect of this size in either order*. It is 17 %. Consequently:

- taking 3.685 as the 1024 baseline keeps a −16 % decline, consistent with §12.33;
- taking 3.070 gives +1 %, inconsistent;
- pooling gives −2.7 %, no step.

**All three readings come from the same twelve lines.** The aggregation choice, not the data,
decides whether the headline effect exists. §12.36 reached the same place from the other direction
(two sweep orders disagreeing in sign); this run adds that disagreement is not even stable *within*
one ordering.

**What changes, stated as a re-prioritisation rather than a refutation.** §12.33's headline had two
parts: acceptance falls ~13 % from 1k to 16k, **and** most of the 16k throughput penalty *is* that
acceptance fall rather than step time. The second depends entirely on the first — 3.36 → 2.93
explains most of a ~20 % throughput drop only if the 13 % is real. With the acceptance mechanism now
failing to replicate in one of two orderings while the throughput penalty survives in both, the
**depth penalty is left without its leading proposed mechanism**. That re-elevates §12.23's
prefill-admission term (7.6:1 → 21.6:1 prefill:decode across depth), which is computed from server-log
token counts and does not depend on sweep order or on a per-step acceptance median at all.

Do not over-read even that. "Does not replicate" is not "is false": §12.33's 38-lines-per-cell with
disjoint CIs is a real result on its own boot, and this run's acceptance cells are 6–41 lines with an
17 % repeat spread — it is the **weaker** instrument, not a decisive counter-test. The honest position
is that the acceptance mechanism is **unresolved and currently unmeasurable at the precision the
question needs**, and any recommendation resting on it — including the `speculative_draft_tokens`
suggestion — should be labelled as resting on an unreplicated effect.

**What would settle it is not another ordered sweep.** Every acceptance number in this file comes
from a *blocked* sweep, the design whose first-cell bias (§12.23) and positional drift (§12.36) are
documented here. The fix is the §12.22 standard applied to acceptance for the first time:
**interleave the depths run-by-run** (1024, 16384, 1024, 16384, …) so each depth accumulates samples
at every schedule position, at `runs` high enough that per-depth samples cover all positions
multiple times — and require the repeated-cell spread to land *below* the effect size **before**
interpreting the effect. This run shows why: with a 6-line cell and 17 % drift, no amount of analysis
recovers a 10 % effect, and ordering tricks only move the answer around inside the noise band.

**A mislabelled column nearly became this section's headline, and it is worth recording.** The first
draft of this section reported "decode throughput penalty **2.15×**, order-robust" from the per-task
row values 818/846/1461/1688. **Those are `pp2048` rows — prefill-phase throughput**, where depth
drives prompt length and a 2× swing is expected. The decode rows are `tg1024` (66.9–88.4). Reading
the third column of llama-benchy's per-task output as "the throughput" silently substituted prefill
for decode and manufactured a 136 % effect where the real one is 11 %. It is the third time in this
thread that a *quantity identity* error, not an arithmetic error, came within one paragraph of
publication — after §12.31's wrong regressor and §12.36's sign/denominator convention. The check that
caught it was reading `p61.csv`'s `test_name` column instead of the progress log's positional
columns: **when a number comes from a positional column rather than a named field, confirm which
phase owns it.**

**One lever is available before any redesign, and it is untested.** Both p59 and p61 ran at `c` = 4,
and §12.29's throughput step lives at `c` ≥ 4 — at `c` = 4 the deepest cells sit at 56–63 % of the
117,752-token pool and are legitimately batch-limited, which is why the `n` counts above collapse to
6–41 lines. At `c` = 2 the same cells are 33–37 % of pool, `usable = min(20, tokens//L)` is not the
binding term, and a cell can sit in steady state long enough to accumulate tens of decode lines
instead of six. **This is the one design change that raises `n` without touching the question, and
`attic/benchmarking/accept-depth-c2.yaml` has been written for it but NOT RUN — nothing in this section is
evidence about `c` = 2.** It should be read as pre-registered outcome 3's remedy: raise the
repeated-cell precision until the drift is smaller than the effect, then ask the question again. If
the two 1024 appearances at `c` = 2 still disagree by more than ~10 %, the acceptance instrument is
the problem and §12.33's mechanism should be treated as untestable by this route rather than as
falsified.


### 12.38 ⚠ HEADLINE RETRACTED BY §12.40 — "cannot resolve a ~10 % effect" is false; what this section calls within-boot drift is ordinary sampling noise (its sign test and failed-remedy findings stand)

**One sentence.** `attic/benchmarking/accept-depth-c2.yaml` ran §12.33's depth sweep at `c` = 2 instead of
`c` = 4, at zero boot cost, to buy the samples the previous two runs lacked; the repeated-cell drift
came back at **+8.1 %**, so §12.37's pre-registered outcome 3 fires for the third time and
**acceptance remains untestable by this route — which is now a measured property of the instrument,
not a complaint about one run.**

**Design and provenance.** `.scratch/phases/p63-accept2/` (artifacts: `p63.json`, `p63.csv`, `p63.out`,
`p63_serve.log`, `driver.log`, `analysis.txt`). Profile args read from the file, not remembered:
`depth: [1024, 16384, 1024, 16384]`, `pp: [2048]`, `tg: [1024]`, `concurrency: [2]`, `runs: 3`,
`prefix_caching: true`. `--skip-run` against the already-live container on node-free-1; the driver's own
config echo confirms the served container is the shipped one
(`'mamba_full_memory_ratio': 3.51`, `'max_running_requests': 48`,
`'speculative_num_draft_tokens': 8`). Depth really was applied — `context_size` in `p63.json` is
1024/16384/1024/16384 with `prompt_size` 2048 throughout, checked rather than inferred from
filenames, per the `prompt_size` lesson in §12.30.

**The drift gate, measured.** Each depth appears twice at different schedule positions:

| cell | appearance 1 | appearance 2 | drift |
|---|---|---|---|
| `depth` 1024 | 3.200 (n = 15) | 3.460 (n = 14) | **+8.1 %** |
| `depth` 16384 | 3.465 (n = 20) | 3.400 (n = 23) | **−1.9 %** |

Opposite signs on the two duplicates, and the larger is 8.1 %. The pre-registered rule says that
above a ~5 % repeated-cell spread no acceptance number may be quoted, so **neither the pooled
3.310 (1024) nor 3.420 (16384) is a result** — and note that those two would read as acceptance
*rising* 3.3 % with depth, the opposite of §12.33's headline, which is exactly the kind of artefact
the gate exists to stop.

**Three batch levels, same wall.** This is the part that makes it a finding rather than a third
null:

| run | batch | repeated-cell drift |
|---|---|---|
| p59 (ascending) | `c` = 4 | 1.9 % / 8.6 % |
| p60 (order-reversed) | `c` = 4 | **10.6 %** / 0.6 % |
| p61 (descending) | `c` = 4 | **17 %** (1024 read 3.685 then 3.070) |
| **p63** | `c` = 2 | **8.1 %** / 1.9 % |

**The hypothesis that motivated p63 was wrong, and usefully so.** It predicted that halving the batch
would relieve pool pressure (31 % of pool here against 59 % at `c` = 4), let the `#running-req ≥ c`
filter hold for a whole task, and thereby buy samples. Pool pressure *was* relieved — no cell was
capacity-limited — and per-cell `n` barely improved. So **the sampling shortfall was never mainly a
capacity problem**: it is that each cell is short (~5 min at `c` = 2) and the acceptance statistic
drifts within a boot at several percent regardless of batch. Buying precision by reducing pool
occupancy does not work, because occupancy was not the binding constraint on `n`.

**A band artefact that would have hidden the gate entirely.** The default cell-matching band
(`#full token` within ±12 % of the batch-total base) **silently dropped task 3's `depth` = 1024
replicate**, printing only tasks 1, 2 and 4 — which would have left one duplicate cell instead of two
and no drift read. Cause: `#full token` is the **batch total** and grows from `c·(depth+pp)` to
`c·(depth+pp+tg)`, so at `depth` = 1024 with `tg` = 1024 the generation range spans 6,144 → 8,192 and
the ±12 % band around 6,144 (5,402–6,881) excludes the later half of every run. At `depth` = 16384 the
same band covers 32,440–41,288 against an actual range ending at 38,703, so nothing is lost. **The
discarded fraction is depth-dependent**, which is why the bug looked like missing data rather than
like a filter. `--band full` (generation-aware) recovers it: `depth` = 1024 goes n = 11 → 29. A filter
whose coverage varies with the independent variable is not a neutral filter.

**What this retires.** §12.33's "~13 % acceptance step at 16k" and §12.35's "acceptance tracks the
prompt" were already flagged as unreplicated and refuted respectively. p63 does not add a fourth
measurement to that argument — it removes the question from this instrument. **Per-step `accept len`
medians on this harness are not an instrument for a ~10 % acceptance effect at any batch size tried
(2, 4, 8), and acceptance should be called untestable by this route rather than refuted.** The
mechanism question stays open, with §12.23's prefill-admission term (7.6:1 → 21.6:1 across depth,
measured) as the remaining candidate that does not depend on an unresolvable statistic.

**What would actually resolve it, and it is not another sweep.** Three runs have now spent ~2 hours of
node time arguing about a statistic with 8–17 % drift. The next attempt has to change the statistic,
not the batch: fix the prompt and the sampling so acceptance is measured on **identical text** across
depths (the greedy-continuation probe of §12.12/§12.20 already does exactly this and is reproducible
to 6/6 per-replicate exactness), and vary only the context length fed to it. That is a different
instrument, costs one boot per arm, and — unlike four sweeps — has a demonstrated repeatability
floor. It is also cheap enough that the decision to run it should not wait for more sweep evidence,
because more sweep evidence is what §12.33, §12.36 and §12.37 already have and it has not converged.


### 12.39 ⚠ RETRACTED BY §12.40 — the "omitted variance component" double-counted noise the bootstrap already included; §12.33's p = 2×10⁻⁴ stands as published

**One sentence.** Reading the same cell twice inside one boot, in runs already on disk, shows the
bootstrap intervals in §12.33–§12.37 are **calibrated or conservative for a single appearance**
(E|z| = 0.41 against 0.8 predicted, 9/9 inside the nominal band), which means the acceptance
disagreement between runs is *between-appearance* variation — and since §12.33's headline test
resampled only within-cell noise for a *between-cell* comparison, adding the missing variance
component moves it from **p = 2×10⁻⁴ to p ≈ 0.01**: weakened from overwhelming to borderline, which
is exactly the status the four failed replications had been groping toward.

**How this got here, including the diagnostic that did not work.** The obvious first move was an
autocorrelation test: split each cell into consecutive blocks, compare the spread of block medians
against the i.i.d. prediction, ratio ≫ 1 ⇒ lines are dependent. Run over 19 cells it returned a
median ratio of **0.30 — far below 1**, which is not "independent" but a broken statistic. Cause:
`accept len` is quantized (3.06, 3.13, 3.44), so with two blocks the two block medians are
frequently the *same value* and their sd collapses toward zero, while the i.i.d. reference uses the
1.2533 constant that presumes continuous data. **The diagnostic measured quantization and called it
independence.** A statistic that returns an implausible-but-tidy number is more dangerous than one
that errors, because it invites a conclusion — this one would have let me write "lines are
independent, CIs are sound" on evidence that meant the opposite. Replaced with a direct calibration
test (`.scratch/qwen3-27b/ci_calibration.py`).

**The measurement.** Nine cells appear twice within one boot (`.scratch/phases/p59-withinbox`, `p60-rev`,
`p61-depthdesc`, `p62-c2`, `p63-accept2`), each appearance's lines bootstrapped (seeded) for a 95 %
CI, then standardised:

| run / cell | n₁ | med₁ | se₁ | n₂ | med₂ | se₂ | gap | \\|z\\| |
|---|---|---|---|---|---|---|---|---|
| p59 d1024 pp1024 | 49 | 3.330 | 0.155 | 36 | 3.540 | 0.143 | +0.210 | **1.00** |
| p59 d1024 pp16384 | 22 | 3.150 | 0.135 | 19 | 3.210 | 0.265 | +0.060 | 0.20 |
| p60 d1024 pp1024 | 25 | 3.340 | 0.155 | 20 | 3.265 | 0.218 | −0.075 | 0.28 |
| p61 d1024 pp2048 | 19 | 2.910 | 0.280 | 19 | 3.140 | 0.090 | +0.230 | 0.78 |
| p61 d16384 pp2048 | 37 | 3.060 | 0.190 | 27 | 3.140 | 0.140 | +0.080 | 0.34 |
| p62 d1024 pp2048 | 18 | 3.405 | 0.225 | 15 | 3.390 | 0.235 | −0.015 | 0.05 |
| p62 d16384 pp2048 | 17 | 3.580 | 0.455 | 20 | 3.645 | 0.558 | +0.065 | 0.09 |
| p63 d1024 pp2048 | 15 | 3.200 | 0.085 | 14 | 3.460 | 0.320 | +0.260 | 0.79 |
| p63 d16384 pp2048 | 19 | 3.510 | 0.145 | 22 | 3.455 | 0.268 | −0.055 | 0.18 |

E\\|z\\| = **0.41** where calibration predicts ≈ 0.8, and all 9 fall inside \\|z\\| ≤ 1.96. **With n = 9
this cannot distinguish "conservative" from "calibrated"; the load-bearing result is only that the
intervals are not anti-conservative by a large factor** — so the run-to-run disagreement is not a CI
artefact and the earlier rewrites were right to blame drift.

**Two things the table settles that no amount of new sweeps would have.**

1. **The drift is not a clock.** Pooling the sign of every repeated-cell jump across the five runs
   gives **7 up / 3 down, exact two-sided sign test p = 1.00**; rates span −0.17 to +0.75 %/min with
   median +0.12. So the two remedies already tried — reversing sweep order (p60, p61) and reducing
   batch (p63) — were *addressed to the wrong property*, and the third remedy I was about to
   recommend, tight interleaving, would not have helped either. Drift is real in magnitude and
   directionless in sign. That is also why ordering-based fixes keep failing: there is no order
   effect to cancel.
2. **The missing variance component in §12.33's test.** The headline gap is 3.250 − 2.925 = 0.325,
   and the reported denominator uses only within-cell resampling noise: **full CI widths** 0.140 and 0.355 (endpoints 3.190/3.330 and 2.770/3.125)
   give half-widths 0.070 and 0.178, hence se's 0.036 and 0.091, denominator 0.097, z ≈ 3.3 (the doc's Mann-Whitney 3.71 is the same
   test done rank-wise — **my reconstruction is approximate, so treat 3.3 vs 3.71 as agreement about
   magnitude, not as the same number**). But repeated appearances of the *same* cell in the *same*
   boot differ by sd **0.117**. Treating a difference of two appearances as √2 × one appearance-level
   se gives an appearance-level se of 0.117/√2 ≈ 0.083 (the "literal" alternative that adds the whole
   0.117 double-counts, since 0.117 already *is* a difference of two readings):

   | denominator | z | two-sided p |
   |---|---|---|
   | 0.097 (within-cell only, as published) | 3.3–3.7 | **2×10⁻⁴** |
   | 0.125 (+ appearance-level se, √2-corrected) | **2.60** | **0.009** |
   | 0.152 (+ 0.117 uncorrected — over-counts, shown for contrast) | 2.13 | 0.033 |

   **What may now be said.** The acceptance step is not refuted, and it is not overwhelming either:
   **p ≈ 0.01 on the defensible correction**. Since the acceptance-vs-depth question was examined
   across several contrasts and several runs before it was reported, a p ≈ 0.01 that had been
   2×10⁻⁴ is not "decisive"; it is one borderline result whose four attempted replications each
   failed to reproduce it. The correct status is **suggestive, unresolved, and no longer citable as
   established** — which is what §12.36/§12.37 said in words and this supplies the arithmetic for.

**Caveats that bound this correction, not just decorate it.** (i) The appearance gaps bundle real
within-boot drift with any CI miscalibration, so the added component is an *upper-bound-ish* proxy
for appearance-level noise rather than a clean variance decomposition; a smaller true component
would leave §12.33 closer to its original significance. (ii) sd = 0.117 is estimated from **9 pairs**,
so the correction itself carries substantial uncertainty — quoting "p ≈ 0.01" rather than a range is
a rounding convenience, and anything from p = 0.003 to p = 0.06 is compatible with it. (iii) The
√2 step assumes the two appearances' level errors are independent and equal-variance, which the
heterogeneity of the se column (0.085 to 0.558) suggests is not exactly true.

**Standing rule, and it generalises past this file.** *A between-group test must not be given a
within-group denominator.* When a quantity is measured repeatedly on the same unit — here, the same
cell in the same boot — the replicate spread is a variance component of any comparison between units,
and omitting it manufactures significance exactly as it did here. This is the same mistake in
different clothes as §12.31's wrong regressor and §12.36's sweep-order-dependent contrast: **the
arithmetic is right, and the quantity being tested is not the quantity being claimed.**


### 12.40 §12.38 and §12.39 are both wrong, from one error: I calibrated against theory instead of against the statistic's own measured null

**One sentence.** Testing the repeated-cell comparison against synthetic data whose answer is known
shows the null value of the statistic is **E\|z\| = 0.40**, not the 0.8 that theory suggests — so the
real data's **0.41 is exactly null**, meaning the "within-boot drift" blamed for four conflicting
runs and the "variance component omitted" that supposedly demoted §12.33 are **the same ordinary
sampling noise the bootstrap intervals already counted**, and both published conclusions are retracted.

**The error, exactly.** §12.39 reported "E\|z\| = 0.41 where calibration predicts ≈ 0.8, therefore
conservative". Two mistakes in that one clause. (i) It treated 0.8 as the benchmark without measuring
what *this* statistic — median-of-bootstrap, se from a CI half-width, two appearances combined in
quadrature — actually does under the null. (ii) It then interpreted a value *below* that benchmark as
evidence about the intervals, when the whole comparison was meaningless until the null was measured.
Generating 2,000 pairs of i.i.d. cells at the real sample sizes and line sd gives **E\|z\| = 0.403**.
The real data give **0.41**. They are the same number. There is no conservatism to report and no
excess variance to correct.

**The check that should have been run before §12.39 was written, and what it says.**

| quantity | truly i.i.d. synthetic | real repeated cells |
|---|---|---|
| E\|z\| | **0.403** | **0.41** |
| sd of gap between appearances | **0.176** | **0.117** |

The real spread is not merely unremarkable, it is **below** the i.i.d. expectation (ratio 0.67),
which rules out an excess appearance-level component as firmly as this data can. So adding 0.117 to
§12.33's denominator — the entire content of §12.39 — **double-counted variance the bootstrap se had
already accounted for.** §12.39's "p ≈ 0.01" is withdrawn and §12.33's own test stands as published
(its `p = 2×10⁻⁴`, subject to §12.37's replication failure, which is a separate and real problem).

**Why this is worth more than the two retractions: it explains four runs at once.** For most of this
thread I have treated "repeated cells move 8–17 % within a boot" as *drift* — a process, with a
cause, that might be found and cancelled. It has no direction (7 up / 3 down across five runs,
sign test p = 1.00), and now there is a reason it has no direction: **it is not a drift.** It is the
sampling noise of a median computed from 15–25 lines of a variable whose per-line sd is 0.41. Three
observations that looked like separate problems — the directionless drift, the run-to-run
disagreement, and the fact that reversing sweep order changed signs — are one phenomenon, and it is
the expected behaviour of small samples, not a property of the server.

**The power table that replaces §12.38's headline.** §12.38's title claimed per-step `accept len`
medians "cannot resolve a ~10 % effect". From the measured line sd, that is **false**:

| n per cell | se of median | hyp. (2 cells) | detect 10 % | detect 6 % |
|---|---|---|---|---|
| 15 | 0.133 | 0.188 | z = 1.8, p = 0.079 | z = 1.1, p = 0.29 |
| 20 | 0.115 | 0.162 | z = 2.0, p = 0.042 | z = 1.2, p = 0.22 |
| 30 | 0.094 | 0.133 | z = 2.5, p = 0.013 | z = 1.5, p = 0.14 |
| 40 | 0.081 | 0.115 | z = 2.9, p = 0.004 | z = 1.7, p = 0.085 |
| 50 | 0.073 | 0.103 | z = 3.2, p = 0.001 | z = 1.9, p = 0.054 |
| 80 | 0.057 | 0.081 | z = 4.1, p < 10⁻³ | z = 2.4, p = 0.015 |

**A ~10 % acceptance effect is resolvable at the sample sizes actually used** (n ≈ 20–40 per cell).
The correct diagnosis of the four conflicting runs is therefore not "blind instrument" but
**"tests run at the resolution floor"**: at n ≈ 20 a true 10 % effect is detected roughly half the
time, which is precisely what four runs agreeing with each other *sometimes* and disagreeing
*sometimes* looks like. §12.33's step and §12.37's null are **mutually compatible** under this table,
and saying so is the actual resolution of the thread's central confusion — the runs were never in
contradiction, they were coin flips being read as refutations.

**Revised status of the acceptance question.** Not "unresolved because unmeasurable" and not
"refuted": **plausible, with each test at roughly 50 % power, and every result so far compatible with
a real ~10 % drop at long context.** The design that settles it is now explicit and it is not free:
**n ≈ 40–50 lines per cell** (≈ 3–4× what p59–p63 collected), fixed arm order, ≥ 2 boots for
replication, at the depths that matter (8192 and 16384). That is a day of node time, not a zero-boot
reparse — and unlike the four reorders already tried, it is aimed at the binding constraint.

**What survives from §12.38 and §12.39.** From §12.38: the drift sign test (7 up / 3 down, p = 1.00)
and the fact that reversing order and reducing batch both failed to change anything — both still
true, and now *explained* rather than merely recorded. From §12.39: the mechanism of the §12.33 test
(a between-cell contrast) and the calibration script; the **numbers it published do not**.

**Standing rule, which is the one this thread has needed all along.** *Before interpreting a test
statistic against a theoretical value, measure its null on synthetic data with the same sample sizes
and the same noise level.* I had run this check for the logprob instrument, the capacity model and
the fitter — each time it caught something — and skipped it for the one statistic whose
misinterpretation sent me rewriting three sections. **A theoretical benchmark is a hypothesis about
your own code, and a measured null is evidence about it.**


Four claims in earlier revisions of this paragraph were wrong, listed because each was confident:
*"the pooled comparison is decisive"* (it is the correct test; ~50 % power is not decisiveness —
§12.40); *"the replicate variance component makes it p ≈ 0.01"* (§12.39, retracted — that component
double-counted noise the bootstrap already included); *"§12.33's ~13 % has not been order-reversed"*
(p61 reversed it and found no step); and *"acceptance steps where throughput steps, so one threshold
at 8k"* (§12.37: the acceptance change is not a step, so the coincidence was one artefact matching
another). **§12.40 also dissolves the "within-boot drift" that §12.38 treated as an unexplained
process**: repeated cells moving 8–17 % inside a boot, with no consistent direction (7 up / 3 down
across five runs, p = 1.00), is not a drift at all but the sampling noise of a median taken from
15–25 lines of a variable with per-line sd 0.41. That single fact explains the directionless
"drift", the run-to-run disagreement, and the sign flips under reordering, as one phenomenon — small
samples — rather than three. What the "one upstream cause" reading leaves is weak but not nothing:
acceptance tends **a few percent lower with more resident context, whichever axis supplies it** — a
sign, not a magnitude, shrinking from −6.4 % (p = 0.019) to −3.6 % (p = 0.38) when sweep order flipped.
§12.23's prefill-admission term (7.6:1 → 21.6:1 across depth, measured) is now
the leading candidate precisely because it is the only one that does not rest on a statistic this
harness cannot resolve.

### 12.41 p64's +108 % capacity win is real but unattributable: the arms changed two factors at once, and the serve logs contain only ~26 decode lines per arm

**One sentence.** The `D = 4 / ratio = 1.2` arm measured **2.08× the shipped recipe's aggregate
decode** at offered `c` = 16 with the capacity model confirmed to +0.8 %, but the experiment changed
draft depth *and* pool ratio together and left too few steady-state lines to separate them — so the
correct output of this phase is **a confirmed capacity effect of unknown cause, plus one decisive
single-factor arm now running**.

**The verified numbers.** `.scratch/phases/p64-a`/`p64-b`, four arms per node, interleaved
(`ship d4r12 ship d4r12` on `node-free-1`, mirrored on `node-free-2`), profile `attic/benchmarking/d4-r12-capacity.yaml`,
`depth` 8192 / `pp` 2048 / `tg` 256, `concurrency` [1, 16], `runs` 2. Aggregate decode
(`tg_throughput.mean`, decode-phase rows only):

| arm | c = 1 | c = 16 | peak `#running-req` | `#tokens` | grant | peak pool usage |
|---|---|---|---|---|---|---|
| `ship` D8 r3.51 | 27.3–34.2 | **50.3, 52.9, 53.3, 57.4** | **14** | 117,377–118,523 | 21 | **0.99–1.00** |
| `d4r12` D4 r1.2 | 25.0–26.6 | **104.6, 105.3, 108.3, 111.7** | **16** | 234,014–234,941 | 22 | **0.71** |

Median c = 16: 53.3 vs 106.8 → **2.08×**. The c = 1 null is satisfied (27–34 vs 25–27, within the
archive's cross-boot band), which is what makes the c = 16 gap interpretable at all.

**The capacity model reproduced, and this is the phase's solid result.** Predicted
(`predict_capacity.py`, anchored at the bottom-up **T = 25.16 GiB** from these very boots, spread
25.11–25.22): `ship` K 86 / cap 21 / 119,890 tokens vs measured cap 21 / 117,462 (**+2.1 %**);
`d4r12` K 91 / cap 22 / 236,275 vs measured 22 / 234,222 (**+0.8 %**). Caps exact in both arms.

**And a second time, the arithmetic I trusted was the error.** I "corrected" §12.24's `usable = 14`
to 11 by reasoning that a request resident in the decode phase must hold `depth + pp + tg/2 ≈
10,368` tokens, so `117,462 // 10,368 = 11`. **The boot observed 14.** The measured footprint is
`117,000 / 14 = 8,360 ≈ depth + 170` — the prompt is **not** charged per-request against the pool for
the whole decode phase (likely prefix-cache sharing and lazy allocation; **UNVERIFIED**, and it is
worth checking because every capacity prediction in this file silently assumes some footprint model).
**The original 14 was right; my derivation was the error.** Recurring lesson, now demonstrated twice:
*an internally sound arithmetic argument must be checked against a boot before it displaces a
measured number.*

**Why +108 % cannot be attributed.** The arms differ in **two** things at once — `D` 8→4 and ratio
3.51→1.2 — and `d4r12` also had **more headroom at every level**: grant 22 vs 21, pool 0.71 vs 1.00,
and it ran 16 streams where shipped ran 14. Per-stream from the harness aggregate (16 streams at
6.75 vs 14 at 3.82) is **1.77× faster per stream**, which a pure capacity story cannot produce: extra
slots explain streams, not rate. So something else moved, and the two candidates are pool pressure
and draft depth.

**What the serve logs can and cannot say.** `gen throughput (token/s)` in the `Decode batch` line is
the **batch total**, established two ways: at `#running-req` = 1 it reads 23.31 against the harness's
own aggregate 24.98, and a per-stream reading at 16 streams (3.49) contradicts the aggregate (104.6)
by 3×. Dividing by the line's own `#running-req` therefore gives per-stream rate — but the lines are
there:

| arm | `#running-req` | n lines | per-stream t/s | accept | pool usage |
|---|---|---|---|---|---|
| `d4r12` | 1 | 63 | 21.3 | 2.70 | 0.04 |
| `ship` | 1 | 54 | 25.3 | 3.29 | 0.07 |
| `ship` | 11 | 16 | 4.57 | 3.23 | 0.97 |
| `ship` | 14 | 12 | 1.75 | 3.05 | 0.98 |
| `d4r12` | 16 | 31 | 3.49 | 2.65 | 0.70 |

Two things follow. **(i) At `#running-req` = 1 — the one level where pool pressure is arithmetically
impossible — `d4r12` is 16 % *slower* per stream** (21.3 vs 25.3), tracking its lower acceptance
(2.70 vs 3.29, the `D` = 4 draft). So **the +108 % cannot be draft depth helping; draft depth is
working against it.** Whatever recovered 1.77× at full load had to overcome a 16 % per-stream penalty
from `D` = 4 and still win. **(ii) The matched-stream test is impossible from p64**: `d4r12` has
**zero lines** at 11 or 14 (it jumps 1 → 16), and `ship` has none at 16. Total decode lines per arm
≈ 26–30, with 8–16 at the top level. Same floor §12.40 measured; `runs: 2` at `c` = 16 buys a
capacity **count** (reached in the first minute) and not much else.

**A third arm that does not exist, caught before it was cited.** I checked whether the archive held
`D = 4` at the *shipped* ratio, which would complete the 2×2 for free. `.scratch/phases/p25-0920/` has
`speculative_num_draft_tokens: 4` at `mamba_full_memory_ratio: 3.51` — and is **`depth: 0`**
(`context_size: 0` in its own JSON; it is the block-size confirmation sweep). It is not a valid arm
for this comparison. Searching all artifacts for a `D` = 4 boot that ran `depth` 8192 returns **only
p64's four `d4r12` boots**. So `D` × ratio at long context is genuinely **unmeasured as a 2×2**, and
the tempting shortcut would have put depth-0 numbers into a depth-8192 conclusion.

**The arm now running, and why it is the better next experiment.** `D = 8 / ratio = 1.2`
(`attic/benchmarking/d8-r12-pool-pressure.yaml`, `.scratch/phases/p65a-0922`/`p65b-0922`, mirrored orders,
launched 2026-09-22 19:24). Two reasons it beats extending p64. **First, it is single-factor** — only
the ratio moves, so a result is attributable, and it is *shippable as-is* since we already ship
`D` = 8 (a `D` = 4 win requires also accepting acceptance 2.70 instead of 3.29). **Second, it is a
matched-stream comparison by construction.** Predicted at the same anchor T = 25.16: K 59, cap 14,
`#tokens` 242,167 → **usable @ `L`=10,240 = min(14, 23) = 14, identical to shipped** (`L = depth + pp` per §12.54; the original text said `min(14, 29)`, using `L = depth`, and **the conclusion is unaffected** — both 29 and 23 sit far above the cap of 14, so the cap binds either way. This is the case where the `L` error changes nothing, which is worth stating because it shows the correction is not a blanket retraction). Both arms will run 14
streams at offered `c` = 16, with pool usage ≈ 0.48 versus shipped's 0.99–1.00. Higher per-stream at
matched 14 → occupancy at usage ≈ 1.0 costs real throughput and the shipped ratio is harmful for 8k
traffic; equal → p64's +108 % was stream count alone and pool pressure is not itself expensive.
Either outcome resolves the mechanism question, and **neither outcome requires more runs**.

**Limitations to carry, not to average away.** n = 2, so throughput carries the archive's 7–25 %
cross-boot caveat (the four c = 16 replicates span 50.3–57.4 shipped and 104.6–111.7 d4r12, which is
consistent with that spread and does not threaten a 2× conclusion). Arms are on two nodes with
mirrored orders, which is the documented mitigation, not a same-node interleaving. `Retract` = 0 and
preemption/eviction strings appear 2–3× per log **in every arm including the null**, so those counters
are startup noise rather than load events and cannot be used to argue for eviction — a trap this
thread has fallen into before (§12.28). Per-stream figures above are medians over 12–63 ramp-dominated
lines and are **directional only**; that is stated because §12.40's whole lesson is that a plausible
median from a small n has repeatedly been read as a measurement here.

### 12.42 p65: the shipped ratio's capacity cost at `c = 16` is **+7.4 %, replicated, and it is a capacity effect — not a per-stream one**

**Verdict first, against the threshold fixed before the run.** §12.41 pre-registered: if pool
pressure cost throughput, the `d8r12` arm (same `D = 8`, ratio 1.2, pool 2.03×) would gain
**≥ +8 %** at `c = 16`. Measured, from the harness JSON, paired **within node**:

| node | ship (median of 2) | d8r12 (median of 2) | ratio |
|---|---|---|---|
| `node-free-1` | 54.5 | 58.6 | **1.074** |
| `node-free-2` | 55.6 | 59.8 | **1.075** |

**+7.4 %, replicated to within 0.001 between nodes, and below the +8 % bar.** By the rule as
written this is **not** a throughput win from relieving pool pressure. The replication is the
strong part: two independent nodes, mirrored arm orders (`node-free-1` ship-first, `node-free-2` r12-first),
same container config, and the two ratios agreeing to three decimals — that is the most
tightly-controlled comparison this recipe has had, and it lands just under the line I drew.

**What the serve log adds, and it changes the interpretation: the gain is streams, not speed.**
Inside each cell's own window (windows from `Task k/N done (Ss)`, which carry duration *and* end
time), the mode of `#running-req` at offered `c = 16` is **11 for `ship`** and **13 for `d8r12`**,
and the ceilings predicted by §12.26's `usable = min(cap, #tokens // L)` land on them:

| arm | pool (measured) | `L = depth + pp` | `#tokens // L` | `cap` | predicted usable | **observed mode** |
|---|---|---|---|---|---|---|
| `ship` (3.51) | 118,002 / 118,187 | 8192 + 2048 = 10,240 | **11.5** | 21 | **11** | **11** |
| `d8r12` (1.2) | 239,298 / 239,621 | 10,240 | 23.4 | 14 | **14** | **13** |

Two things follow. **(1)** The shipped ratio is *pool-limited at 11 streams* for 8k-context
traffic at `c = 16`, and the prediction was right to the unit — this is §12.26's model confirmed
at a third context length (10,240 counting the prompt), where earlier confirmations were at
`L = 8,192` and `16,384`. **(2)** `ship`'s `#running-req` is bimodal — `(11, 4), (14, 3)` — and the
two modes are the **two benchmark phases**, not one phase freeing tokens in the other (see §12.43:
the prefill phase holds `depth` = 8,192 per request and the decode phase holds `depth + pp` =
10,240). The prediction lands on both: `118,002 // 8,192 = 14` is the prefill-phase ceiling and
`118,002 // 10,240 = 11` the decode-phase one, and sorting the lines by per-request resident tokens
separates them cleanly (run=14 lines imply a prompt ≈ 8,250; run=11 lines ≈ 10,350). An earlier
version of this paragraph said the 14 was "tokens freeing as requests finish", which is wrong, and
wrong in a way that flatters the story: it invents a dynamic when the statics already explain it.
The **capacity claim itself is unaffected** — the comparison that matters is decode-phase against
decode-phase, where `ship` reaches 11 and `d8r12` reaches 13.

**The arithmetic therefore closes: +18 % streams × ~0.90 per stream = +7.4 %.** Streams went
11 → 13 (+18 %) while aggregate rose only +7.4 %, so per-stream throughput fell ~9 % — which is
what sharing a fixed machine across two more streams should do. It also means the honest headline
is **not** "relieving pool pressure buys +7.4 % throughput"; it is **"the shipped ratio costs
~2 of 13 concurrent 8k streams, and converting them to aggregate recovers about 7 % because the
extra streams contend."** Pool pressure per se still has no measured throughput cost, consistent
with §12.32 finding no bandwidth term: `ship` runs at `full token usage` **0.99** with zero
retractions and is *not* slower per stream because it is full — it is slower in aggregate because
it admits fewer streams.

**A claim I made and retracted within the same hour.** Reading the first version of
`p65_streams.py`'s output I wrote that the +7.4 % came "with fewer streams". Wrong, and wrong for
a specific reason worth keeping: that script divided the cell's aggregate by the **mode** of
`#running-req`, but the window contains ramp lines at `#running-req` 1–3, so a mixed
distribution's mode is not the cell's operating batch, and `ship`'s `(11, 4), (14, 3)` is
bimodal enough that the mode is arbitrary. **Each line's own `#running-req` is the denominator
that line's own aggregate needs**; the per-line column added to the script is the fix. The
aggregate numbers were never in question — only the decomposition, which is the part a headline
would have quoted.

**Two limits that survive.** (i) Per-line `#running-req` samples are thin — n = 4–8 per cell after
filtering to near-offer lines — so the ~0.90 per-stream factor is directional, not a measurement;
the +18 % stream count is the solid half because it rests on the mode *of a steady-state
distribution* plus a prediction that lands. (ii) The two arms differ in pool size by construction,
so `gen / #running-req` is not pool-matched and a per-stream difference this small cannot be
separated from that confound at this n. **Do not upgrade "streams" to a precise capacity gain
number from this table.**

**What this settles in the p64/p65 arc.** §12.41 could not attribute p64's +108 % because that
comparison changed `D` *and* ratio at once. p65 isolates the ratio at fixed `D = 8` and finds the
same phenomenon two orders of magnitude smaller: **a capacity effect, arriving through the token
pool, with no per-stream penalty attached to being full.** Both point the same way, and the
practical consequence for the shipped recipe is unchanged and small: raising the ratio buys
concurrency at long context (§12.26's `r ≈ 1.2` at 16k, this `+2 streams` at 8k) and costs
essentially nothing per stream — but +7.4 % is below the threshold I set for calling it a win, and
`c = 16` on two nodes is not the workload a `max_num_seqs: 48` recipe is advertised for.

**Artifacts.** `.scratch/phases/p65a-0922/`, `.scratch/phases/p65b-0922/` (4 arms each, mirrored order,
`--fresh`, duplicate-md5 guard passed). `.scratch/qwen3-27b/p65_streams.py` — built after three
predecessor analyzers each silently returned "no data" for reasons unrelated to the data: one
ordered regex that could not match (this build prints `accept len` **before** `cuda graph`), one
wrong filename glob, one window anchored at `datetime(2000, 1, 1)` that never matched a 2026 log
and printed a plausible-looking window anyway. All three failure modes are now documented in the
script header with guards, and every "found nothing" branch prints what it looked at.

---

### 12.43 What llama-benchy's `depth` and `pp` actually are — measured, because this document had them both ways

**The finding, and it changes what every `depth` number in this file means.** Each benchmark cell
runs **two phases**, and the phase changes the prompt:

| phase | prompt length | generated | resident tokens during decode |
|---|---|---|---|
| `is_context_prefill_phase = True` | `depth` | `tg` | `depth .. depth + tg` |
| `is_context_prefill_phase = False` | **`depth + pp`** | `tg` | `depth + pp .. depth + pp + tg` |

So **`pp` is not a second axis for the decode phase — it is added to the same axis.** A cell run at
"depth 8192, pp 2048" decodes a **10,240-token** context, and every figure in §12.22–12.39 quoted as
"at depth 8192" is a decode at `8192 + pp`. `response_size` is `tg` in both phases; neither phase
generates `pp`.

**Why this had to be measured rather than reasoned.** DEPTH-COST carried **both** readings at once.
§12.32 states "`depth` is the PROMPT length; `pp` and `tg` are GENERATED"; §12.31 justifies its
retraction with the regressor `R_half = c·(pp + depth/2)`, which only means "prompt + generated/2" if
`pp` is the prompt and `depth` is the generated length — the **opposite** assignment. One of the two
was load-bearing, and a headline retraction had been justified using it.

**The measurement.** At offered `c = 1` the server's own `#full token` *is* the single sequence's
resident count, so its value just after a cell starts is that phase's prompt. In p65 (`depth` 8192,
`pp` 2048, `tg` 256) the values form **two tight clusters — 8,267–8,450 and 10,350–10,509 — on all
8 arms of both nodes**, with 14/15 of the 28 lines inside those two windows. A single sequence
generating `pp + tg = 2,304` tokens from a prompt of 8,192 would spread continuously across
8,192–10,496; with lines ~4 s apart (~120 tokens) the odds that all 13 land outside that gap are
~`(404/2304)^13 ≈ 1e-14`. The gap is not sampling luck. The cluster maxima, **10,509 and 10,490**,
bracket the predicted `depth + pp + tg = 10,496` within 13 tokens, independently on two nodes. The
alternative reading — decode prompt = `pp` = 2,048 — is excluded outright: no cluster near 2,048
exists, and reaching 10,496 from it would need 8,448 generated tokens against `tg = 256`.

**Replication on data with a different phase, batch, and grid.** p55 (`c = 8`, depth ∈ {1024, 4096},
pp ∈ {1024, 2048, 4096}) has 12 predicted plateaus under the table above — `8·(depth + tg/2)` for
prefill rows and `8·(depth + pp + tg/2)` for decode rows. **All 12 are present within 5 %** (errors
0.4–3.4 %, median 0.9 %), including the two cases where different `(depth, pp)` pairs predict the
**same** plateau (1024/4096 and 4096/1024 both predict 8·5,248 = 41,984; observed 41,690). The
plateau widths equal `c·tg`, as they must. `.scratch/qwen3-27b/resident_plateaus.py`.

**Three consequences, in order of cost.**

1. **§12.29's "falsification" of a per-byte cost was an artifact of the wrong regressor — and the
   same pair, corrected, *supports* one.** The two cells are (c=4, depth 8192, pp 2048) and
   (c=8, depth 4096, pp 2048). §12.29 called them "equal bytes" because `B1 = c·depth` = 32,768 for
   both, and treated the step-time gap as a refutation. Under the corrected count they are **not**
   equal: `B3 = c·(depth + pp)` = 40,960 → 49,152, ratio **1.200**, against a measured step-time
   ratio of **1.185**. Nearly proportional, and the sign is right. The byte model that §12.29 said
   was refuted is the best-fitting explanation of the very pair used to refute it.
   **Two errors of mine were needed to get here, both worth recording.** (i) §12.31 was *right* to
   retract but its stated reason — substituting `c·(pp + depth/2)` — had `depth` and `pp` **swapped**;
   a correct conclusion resting on an incorrect justification survived review because nobody
   re-derived the substitute. (ii) Reaching this today I first wrote "the sign error survives the
   correction", because I compared the cells using **peak throughput** as "speed". That is the wrong
   statistic: `peak = c·TPS/t_step`, so peak *rises* with `c` even when the step is slower, and these
   two cells differ in `c`. The correct comparison is step time. A two-parameter model
   `t = a + K·bytes` fits any two points exactly, so a pair can only refute it by getting the **sign**
   wrong — which is why "equal bytes, unequal time" was a real test under B1 and is not one under B3.
2. **§12.30's crossed design crossed nothing for the decode phase.** Its `depth × pp` grid varies
   `depth + pp` and the split between them; if decode cost depends only on the sum, the "interaction"
   whose sign flip it reported (`M` = −2.7e-06 at (4,4096) vs +4.0e-06 at (8,4096)) is not a
   physical non-additivity but a fit chasing a difference that should not exist. §12.30's conclusion
   ("the additive form is the wrong functional form") is therefore **weakened**, not confirmed: the
   grid cannot separate the terms *and* cannot be relied on to show they do not add.
 3. **A same-regressor reproducibility bound, which is the number to quote next time.** Grouping all
    379 archived decode rows by `(c, depth + pp)` gives 26 byte-equal groups. **14 of them have
    `c·depth` constant as well** — both candidate regressors fixed — and their step-time spread
    across sources is **8–13 %** (c=2: 5.2, 8.1 %; c=4: 10.1, 12.4, 8.8 %; c=8: 8.8, 12.7, 12.3,
    9.3 %; c=16: 1.4 %). **Read that as cross-boot reproducibility at fixed regressors — not as an
    instrument floor, and not a clean bound even so:** those groups pool different
    `mamba_full_memory_ratio`, `D` and draft-token settings, so part of the 8–13 % is a real config
    difference and none of it is isolated noise. What it bounds is what a *cross-boot* archived
    comparison can support, which is the shape most of this file's comparisons take; §12.22's ~20 %
    depth gap sits only about twice above it.
    **The within-config numbers are tighter and are the ones to use for power.** From the raw per-run
    `values` arrays (246 cells): median per-run **cv 4.8 %** on `peak_throughput`, p90 10.8 %;
    `tg_throughput` is no better (4.8 vs 5.3 % median cv), so using `peak` for the fits above cost
    nothing but gained nothing either. A 5-run cell mean therefore has SE ≈ 2.2 %, and a difference
    between two such means SE ≈ 3 % — **a same-boot comparison at `runs: 5` resolves roughly 6 % at
    2 SE, where a cross-boot one resolves nothing under ~13 %.** That asymmetry, same-boot ≈ 6 %
    versus cross-boot ≈ 13 %, is the practical reason every design in this thread has converged on
    one-boot multi-arm runs, and it is the number to check a proposed experiment against before
    spending boots on it.

**Not established.** *Why* the decode phase's prompt is `depth + pp`. The harness source is not on
this box (`llama_benchy` is not importable and no file matching `*benchy*` exists locally), so this
is inferred entirely from the server's own counters — strongly, but without reading the code that
produces it. If the harness appends generated text to the prompt between phases, that would explain
the sum, and it would mean the decode phase is not measuring a fresh long-context request at all.
Either way the numbers above are what the server was actually holding.

---

### 12.44 p66 + p67: neither prompt length nor resident tokens prices the decode cost — there are two, and they saturate

**The result in one line.** Five cells measured in **one container** at `c = 8`, `D = 8`, ratio
3.51, same grant (`capped to 21`), same `K` (85) and same pool (`#tokens: 117,568`) in both runs:

| `depth` | `pp` | mean resident `pp+depth/2` | endpoint `pp+depth` | decode `peak` | source |
|---|---|---|---|---|---|
| 1024 | 1024 | 1,536 | 2,048 | **160.0** (157.2, 162.8) | p66 fwd/rev |
| 4096 | 1024 | 3,072 | 5,120 | **161.8** (160.8, 162.8) | p66 fwd/rev |
| 8192 | 1024 | 5,120 | 9,216 | **142.5** (130–152, n=10) | **p67 + p67b** |
| 1024 | 4096 | 4,608 | 5,120 | **129.6** (130.2, 129.0) | p66 fwd/rev |
| 4096 | 4096 | 6,144 | 8,192 | **129.8** (131.8, 127.8) | p66 fwd/rev |

**The `endpoint` column is measured, not inferred from argument names.** Each task window holds two
`pp` cells, so the window *median* mixes them and is useless — but the window's **upper** value of
`#full token / #running-req` isolates the long-`pp` cell, and it lands on `depth + pp` in every
window (`#full token` is the batch total, hence the division by `#running-req`):

| window | endpoint of its long-`pp` cell | observed max | p95 |
|---|---|---|---|
| fwd task 1 (`d = 1024`) | 1024 + 4096 = 5,120 | 5,287 | 5,278 |
| rev task 2 (`d = 1024`) | 1024 + 4096 = 5,120 | 8,296 ⚠ | **5,324** |
| fwd task 2 (`d = 4096`) | 4096 + 4096 = 8,192 | 8,394 | 8,369 |
| rev task 1 (`d = 4096`) | 4096 + 4096 = 8,192 | 8,386 | 8,358 |
| p67 (`d = 8192, pp = 1024`) | 8192 + 1024 = 9,216 | 9,405 | 9,253 |

Every value sits **above** its endpoint but **below endpoint + `tg`**, which is exactly what a
fixed prompt with 0…`tg` = 256 generated tokens stacked on it predicts:

| window | endpoint | endpoint + tg | observed max | verdict |
|---|---|---|---|---|
| fwd task 1 | 5,120 | 5,376 | 5,287 | in band (+3.3 %) |
| rev task 2 (p95) | 5,120 | 5,376 | 5,324 | in band (+4.0 %) |
| fwd task 2 | 8,192 | 8,448 | 8,394 | in band (+2.5 %) |
| rev task 1 | 8,192 | 8,448 | 8,386 | in band (+2.4 %) |
| p67 | 9,216 | 9,472 | 9,405 | in band (+2.1 %) |

**All five land inside `[depth + pp, depth + pp + tg]`, none above the upper bound.** A window whose
long-`pp` cell actually held, say, 8,192 tokens would have produced a max near 8,192 in the
`d = 1024` windows, and none did. So the `endpoint = depth + pp` column is the server's own
measurement and not an inference from an argument name — and the band test is what makes it a test,
since a tight agreement with a value 2–4 % below a *free* upper bound is not the same as agreement
with a number picked to fit.

⚠ **rev task 2's raw maximum is contaminated and the p95 is the usable figure.** Windows here are
built as `[end − duration − 15 s, end]`, so consecutive tasks overlap by 15 s and rev task 2's window
swallows the tail of rev task 1 — whose sequences are 3,072 tokens longer. Reporting the raw max
would have put 8,296 tokens in a window whose longest cell holds 5,120, i.e. a number that *looks*
like it refutes the column. **Quote p95 when the window edge is mine rather than the harness's.**

This matters because the tie-based refutation in point 3 below depends on S and L holding the *same*
number of tokens, and that claim previously rested on §12.43's reading of an argument name rather
than on the server's own count. It does not now.

`fwd` and `rev` are the same cell run twice, ~35 minutes apart, in the same container: the worst
disagreement across four cells is **3.6 %**, and within the two `pp = 4096` cells the two orders
agree to **0.9 %** and **3.1 %**. That is the reproducibility these numbers must be judged against,
and it is far tighter than the cross-boot bound (~13 %) quoted elsewhere in this file — because
this is a same-container comparison, which is the whole reason the design is built that way.

**Three candidates, all three fail.** This is the finding; the failure of each is a separate
observation, not one argument with three wordings.

1. **Prompt length (`pp`) alone — refuted.** The `pp = 1024` group is 160.0/161.8. p67 also has
   `pp = 1024` and measures **142.5**, which is **11.9 % lower, permutation p = 0.0054** against a
   same-container reproducibility of 3.6 %. `pp` cannot be the price.
2. **Mean resident tokens `pp + depth/2` — refuted *within p66 itself*, before p67 says anything.**
   Going `(1024,1024)` → `(4096,1024)` **doubles** mean resident (1,536 → 3,072) and costs
   **nothing** (160.0 → 161.8, a 1.1 % *gain*). But going `(4096,1024)` → `(8192,1024)` adds the
   **same +1,536** tokens (3,072 → 5,120) and costs **13.5 %**. Identical increments, opposite
   outcomes. An additive per-token cost cannot express that. (p67 does not refute this candidate —
   at 5,120 mean resident it predicts ~129.7 and measures 142.5, +10 %, p = 0.093, not
   significant —
   which is why the candidate is rejected on the internal inconsistency above and not on p67.)
3. **Endpoint resident tokens `pp + depth` — refuted by a tie.** `(4096,1024)` and `(1024,4096)`
   both hold 5,120 tokens and differ by **25 %** (161.8 vs 129.6). Equal KV set size, large gap.

**What the tie-based refutation replaces.** §12.29's "two-point equal-bytes falsification" was
already retracted by §12.31 for using `c·depth` as the byte count. This tie is the corrected
version of that argument, using the right regressor (`pp + depth`) and a pair constructed to be
genuinely equal in it. It is the same conclusion reached properly, and it is worth noting that
**the first attempt at this section reported the opposite**: a two-level "does variable X split
the groups" test that assumed the effect *grew* with the variable, so a variable separating the
cells perfectly — with a 25-point gap, replicated across both sweep orders — was printed as
"OVERLAPS → cannot be the driver". The sign error documented in §12.29 was reproduced inside the
very check written to catch it.

**What does fit: two costs with different axes, both saturating near 128.**

- A **`pp` cost**, stated in one convention (percent of the *faster* cell's peak, so the number is
  a drop): at `depth = 1024`, `pp` 1024 → 4096 takes 160.0 → 129.6, **−19.0 %**; at `depth = 4096`,
  161.8 → 129.8, **−19.8 %**. The corresponding *step-time* increases are larger because they are
  reciprocals (1/0.81 − 1 = +24 %), and the p66 analyzer prints those (+23.5 % / +26.2 %), so a
  figure near 20 and a figure near 25 describe the same comparison. **Quote the convention with the
  number** — this project has already been misled once by silently mixing the two (§12.36's
  denominator note).
- A **`depth` cost**: at `pp = 1024`, `depth` 4096 → 8192 takes 161.8 → 142.5, **−11.9 %**
  (p = 0.0054), with *nothing* for `depth` 1024 → 4096 (160.0 → 161.8). So it is not a ramp from
  zero; it appears late.
- **Saturation**: every slow cell sits at 129–140 and the fastest at ~161, and the two `pp = 4096`
  cells at very different depths are 129.6/129.8. The costs do not add — the second one cannot
  take you below ~128. This is why "resident tokens" *looks* monotone across p66's four cells and
  then breaks on the fifth: saturation and monotonicity are indistinguishable on four points.

**Acceptance is not the explanation, which is what makes this a step-time result — and the slow
group accepts *more*, not less.** Every number below comes from **one** script,
`.scratch/qwen3-27b/accept_one_filter.py`, under **one** filter (`cuda graph: True`,
`#running-req >= 8`, `gen throughput > 50`). That discipline was itself a correction: p67's
acceptance had been quoted from a script with no `gen > 50` gate and p66's from one with no
`#running-req` gate, and adding the missing gate moves p67's median from 3.210 to **3.230** while
halving n (16 → 9). Since acceptance rises with batch and with steady state, an unsteady-ramp line
biases the median *down* — the exact direction that would have manufactured a false "acceptance
fell", which is the trap §12.33 exists to warn about.

| group | `accept len` (n per cell) |
|---|---|
| `pp = 1024` (fast) | 3.200 (n=26), 3.250 (n=24) |
| `pp = 4096` (slow, −19 %) | 3.305 (n=20), 3.180 (n=23) |
| discriminator `(8192, 1024)` | 3.230 (n=9), 3.190 (n=15) |

Every cell sits in **3.18–3.31**, a 4 % spread against a 19 % throughput spread, and the **slow**
group's acceptance is marginally *higher* than the fast group's. So the throughput gap cannot be
acceptance wearing a different hat: the slow cells accept at least as many tokens per step and
still produce 19 % fewer tokens per second. Given §12.33 — "most of the depth penalty is acceptance, not the step
slowing" — any depth-shaped throughput change has to be checked against acceptance before being
called a step effect, and here it passes: acceptance is flat while peak falls 11.9 %. That also
means §12.33's acceptance story and this one are **about different ranges**: acceptance moves over
1k → 16k *generated* tokens, and this is a change at fixed acceptance.

**How p67 was run, because it cost zero boots and that matters for repeatability.** The live
`node-free-1` container was already serving the shipped config, so the arm ran with `--skip-run
--no-stop` and `--fresh`; identity was confirmed from the **serve log's own `server_args` echo**
(`speculative_num_draft_tokens: 8`, `mamba_full_memory_ratio: 3.51`, `mamba_ssm_dtype: bfloat16`),
**not** from `docker inspect`, which cannot report the config at all (§12.36 instrumentation note).
Total cost: one benchmark, no boot. The discriminating-arm pattern — *find the axis a completed
grid confounds, then run that one cell against a server you already have* — is the cheapest real
experiment available on this recipe and it has now overturned a conclusion three sections circled.

**Two errors found in this section's own tooling while producing it, recorded because both would
have changed the conclusion:**

- `p66_prefill_test.py` mapped task index → `(depth, pp)` using a dict taken from the **forward**
  profile and applied it to the reversed half, swapping S and L there. The symptom was a result
  *too clean to question* — pooled hit rates of 0.245 vs 0.247 — and the pooled comparison is
  still void for a second reason: **the four cells come from only two task windows**, because the
  `pp` cross-product happens *inside* a task, so "cell S vs cell L" in that output is really
  "task 1 vs task 2". Its verdict is discarded, not corrected. Anything that varies between halves
  by construction (order, task index, run count) must be read from that half's own artifact.
- The monotonicity check used a **0.05 absolute tolerance** against values near 160 with 0.9–3.6 %
  within-cell spread, so no candidate could ever be called monotone and the two perfectly-ordered
  candidates printed "2 inversion(s)". A threshold no dataset can satisfy is not conservative, it
  is dead. Tolerances must be scaled to the statistic's own measured noise — the same lesson
  §12.40 records, re-learned one file over.

**Limits, stated before anyone quotes the table.**
- **`(8192, 1024)` is `n = 10` but from ONE container.** p67 and p67b are the same cell measured
  twice, ~30 min apart, in the same live server (`--skip-run` reused it): their medians agree to
  **3.6 %**, matching p66's own same-container bound. **Doubling `n` this way strengthens the p-value
  and does nothing for boot-to-boot reproducibility**, which is the thing this file says repeatedly
  cannot be assumed (7–25 % cross-boot on byte-identical boots). The honest description is "ten
  observations from one boot", and the p = 0.0054 is a statement about that boot. A **cross-boot and
  cross-node** replicate is `attic/benchmarking/pp-depth-complete.yaml` on `node-free-2`, which also supplies
  the missing `(8192, 4096)` cell that would test whether the two costs add.
- Its spread is 5.4 % (130–152) and its minimum 130.0 touches the `pp = 4096` group's maximum, so the
  "sits above the slow group" reading (p = 0.093) is the weaker of the two claims and should not be
  quoted without the p-value.
- **`peak_throughput` is a summary of a mixed prefill/decode window.** "Two saturating costs" is a
  statement about the measured statistic. Whether the `pp` cost is prefill interleaving, a slower
  decode kernel at long prompts, or scheduler admission behaviour is **not separated by any
  number in this table** — the prefill/decode timing split still needs harness-side
  instrumentation (§6 queue).
- The 19–24 % `pp` cost and the 13.5 % `depth` cost are **not decomposed**: with 5 cells and 2
  free parameters plus a saturation floor, this table cannot distinguish "two saturating costs"
  from "one cost in some other variable". Naming two is a model choice that fits, not a measurement.

### 12.45 The depth and prompt costs do not saturate — but *how* they compose is not determined, and "multiplicative" was an overclaim

**The result in one line.** A fourth cell — `d = 8192, pp = 4096` — measured on a fresh boot and
predicted from the other three cells **only**, lands at **115.0**: consistent with all three
non-saturating composition rules, and **16 points below where saturation puts it**. `attic/benchmarking/pp-depth-complete.yaml`
(`pp: [1024, 4096]`, `depth: [4096, 8192]`, `concurrency: [8]`, `tg: [256]`, `runs: 5`), 4 cells ×
5 runs
on `node-free-2`, analyzed by `.scratch/qwen3-27b/p68_composition_test.py`.

| | `pp = 1024` | `pp = 4096` | row ratio |
|---|---|---|---|
| **depth 4096** | 154.0 | 131.0 | 0.851 |
| **depth 8192** | 139.0 | **115.0** | 0.827 |
| **column ratio** | 0.903 | **0.878** | |

| model for the corner | predicts | meas/pred | `t_meas/t_pred` | bootstrap verdict (20,000 resamples) |
|---|---|---|---|---|
| multiplicative `slow·disc/base` | 118.2 | 0.973 | 1.028 | **consistent** — CI straddles 0 |
| additive-in-levels `slow+(disc−base)` | 116.0 | 0.991 | 1.009 | **consistent** — CI straddles 0 |
| additive-in-time `1/corner = 1/disc+1/slow−1/base` | 120.0 | 0.958 | 1.043 | **consistent** — CI straddles 0 |
| saturation `corner = slow` | 131.0 | 0.878 | 1.139 | **REJECTED — `P(measured slower) = 1.000`, CI `[+0.00063, +0.00154]`, entirely above 0** |

**The claim that survives is narrower than the one this section originally carried.** Its first
version was titled "the two costs compose multiplicatively", and so did the summary bullet. **That
is an overclaim, corrected here.** What the data supports is *"at least two additive per-step costs,
and they do not saturate"*. The three non-saturating rules predict **116.0 / 118.2 / 120.0** — a
**3.4 % spread against ~4 % cell-to-cell noise** — so this grid cannot separate them and none can be
*selected*; multiplicative was simply the first one written down. **A verdict of "consistent" is not
a verdict of "true"**, and with three candidates inside one noise width the honest output is the
consistent *set*, which is what `p68_composition_test.py` now prints rather than a single winner.
Difference units are **step time** (`1/rate`), because the physical models are additive there; the
earlier version reported the difference in rate units, which is the wrong space for an additive-time
model.

**Which model should have been in the set from the start.** If the two effects are additive per-step
**time** costs — which is what "two independent additive costs" physically means — then throughput,
being 1/time, composes **harmonically**: neither multiplicatively nor additively in rate units. That
model (`additive-time`) was absent from the original pre-registration altogether, and it predicts
**highest** of the three survivors (120.0, ratio 0.958), i.e. the corner sits slightly *below* it.
The form is legitimate because `c` and accept-len are equal across all four cells (`c = 8`;
acceptance matched at 3.21/3.22), so 1/rate is proportional to step time under one shared constant.
Its absence is the same defect as labelling a multiplicative formula "additivity": **the candidate
set did not contain the model the mechanism implies.**

**Why this is a test and not a fit.** The prediction uses only the three cells the model is allowed
to know, so the fourth cell is out-of-sample. The strongest version of the claim comes from §12.42's
own numbers, from a **different boot on a different node**: `140.0 × (129.8 / 161.8) = 112.3` against
a measured **115.0 (median of [115, 109, 114, 115, 119]) — a 2.4 % error**, or 1.9 % against the cell
mean of 114.4. Composition is not being tuned to p68; it is being tested by it.
*(This sentence originally said "114.6 — a 2.1 % error". Neither number exists: 114.6 is not in the
cell's value list and 2.1 % matches neither the median nor the mean. Fourth unverified-figure catch in
one day, all four by recomputing instead of trusting the draft; see the 2026-09-23 JOURNAL entries.)*

**Why "saturates near 128" looked true, and why it was never a testable claim.** The original
evidence was two `pp = 4096` cells landing on top of each other — **129.0** at depth 1024 and
**131.0** at depth 4096 (p66 forward) — read as "the second cost has nowhere left to go". But p66
also measured **depth 1024 → 4096 at `pp = 1024` and found no cost at all** (155.0 → 161.0). If the
depth cost is **zero** across an interval, then equality across that same interval at any other `pp`
carries **no information about saturation** — it is exactly what composition predicts. The "floor"
was the value of the `pp` cost, sampled at depths where the depth cost happens to vanish. The
pooled p66 figure for `depth 1024 → 4096` at `pp = 1024` is 158.0 → 162.5, a **+2.8 % rise**, so
"no depth cost over 1024–4096" holds in both sweep directions and the equality at `pp = 4096` was
uninformative in both.

**A separate error class worth keeping: thresholds drawn without checking what they separate.** The
original pre-registration fixed `≥122` = additivity and `≤112` = saturation *before* computing the
prediction. The prediction (118.2) falls **inside** the MIXED zone. So the honest reading of the
"MIXED" verdict that came back was not "inconclusive, both partly right" — it was **"the
pre-registration could not have reported its own outcome."** Worse: what the document labelled
*additivity* was multiplicative composition from the beginning (`corner = slow × disc / base`), so
the candidate set **never contained an additive model at all** — the two named hypotheses were not
the two hypotheses under test. Fixed here by naming three models, predicting each from the other
three cells, and asking which one the data *excludes*. Rule: **a threshold that cannot be compared
against the prediction it exists to classify is decoration, not a gate.**

**A bootstrap defect found in the replacement script itself.** The first version bootstrapped the two
*rates* and multiplied them — a median of ratios — returning the depth cost as **0.933** where the
cell medians give `139/154 = 0.903`. That **3 % bias was larger than the effect under test**, and the
cause is structural: resampling a **median from n = 5** is a lumpy, biased estimator, and its bias
propagates directly into the prediction being judged. Fixed by bootstrapping only the **final**
statistic and keeping the point prediction as a ratio-of-medians. Rule: **bootstrap the quantity that
is the hypothesis, never an intermediate you then transform.**

**How sensitive the conclusion is to which discriminator value you use.** The `d = 8192, pp = 1024`
cell has been measured **four times on four boots**, and each choice of "the" value shifts the
composition ratio but none of them rescues saturation (`.scratch/qwen3-27b/p68_sensitivity.py`,
p69 added):

| discriminator value | source | predicts corner | measured/predicted |
|---|---|---|---|
| 139.0 | p68's own, **same boot as the corner — the correct choice** | 118.2 | 0.973 |
| 140.0 | p67 (`node-free-1`) | 119.1 | 0.966 |
| 141.0 | **p69 (`node-free-2`, zero-boot replicate)** | 120.0 | 0.958 |
| 142.5 | pooled p67 + p67b (n = 10) | 121.2 | 0.949 |
| 145.0 | p67b (`node-free-1`, second boot) | 123.3 | 0.932 |
| 140.5 | pooled over all four boots (n = 20) | 119.5 | 0.963 |
| — | saturation (ignores the discriminator) | 131.0 | **0.878** |

**The correct value for the within-boot test remains the same-boot one (139.0)** — a within-boot
prediction must use within-boot inputs — and the rest are quoted only to show the conclusion is not
an artifact of that choice. Spread of the composition ratio across all six: **0.93–0.97**, always
inside the bootstrap CI; saturation sits at 0.878 for every one of them, with a rejection margin of
16 points against a ~5-point uncertainty. **Averaging measurements of different boots to get "a
value" for a cell is what creates apparent discrepancies that were never there** — see the paragraph
below.

**The fourth replicate resolved the one caveat this section carried, and changed no conclusion.**
`.scratch/phases/p69-discrim3/` measures `d = 8192, pp = 1024, c = 8` on `node-free-2` at zero boot cost
(`--skip-run --no-stop` against the already-serving container, identity confirmed from its own
`server_args` echo: ratio 3.51, `speculative_num_draft_tokens` 8). Result **141.0**, within-run
range 136–151, **cv 3.6 %**. Cross-boot spread across the four boots is **139.0–145.0 = 4.3 %** —
the **same size as the within-boot cv**, so there is no boot-state or node effect left to explain
and no discrepancy to resolve: four boots of a container are indistinguishable from five runs of it.
Recomputing with the pooled 140.5 moves the multiplicative prediction 118.2 → 119.5 (ratio 0.963
rather than 0.973), comfortably inside a CI that already spanned ±10. **Nothing in this section
moves.** The replicate's value was not a new number but the removal of the only figure here that
rested on a single boot — the difference between quoting 139.0 as a measurement and asserting it
from n = 5. That is worth a free boot; it is not worth a paid one unless the number is load-bearing.

**What this does *not* establish.** It does not name a mechanism. "Two costs multiply" describes how
observables combine; multiplicative composition is what you get from *any* pair of independent
per-step time increments, so it constrains the functional form without identifying a cause, and
§12.32 still stands: there is no measurable KV-bandwidth term here. Nor does it separate
multiplicative from additive-in-levels — at these effect sizes the two differ only in second-order
terms (118.2 vs 116.0, both inside the CI), so **distinguishing them needs a wider axis**, not more
runs on this one.

**A fabrication made while writing this section, recorded because it is the most dangerous kind.**
Before running any of the above I drafted a caveat asserting that the discriminator read **127.5 in
p67b**, a 12 % discrepancy implying a boot-state effect, and built reasoning on top of it ("both arms
moved together", "the same signature as §12.38's container cooling"). **No such measurement exists.**
p67b reads **145.0**; the number 127 appears in the archive only as one *individual run value* inside
`p68`'s discriminator list `[139, 139, 141, 145, 127]`. I converted a single outlying run into a
phantom between-experiment contradiction, and the phantom was *well argued* — it had a mechanism, a
cross-reference, and a proposed test. It reached the draft file and stopped there only because the
append was blocked by a formatting error, which forced me to re-derive the numbers from the JSONs
before retrying. **Two rules fall out of that.** (1) A cross-experiment discrepancy is a claim about
two artifacts; quote both medians with their filenames, or do not claim the discrepancy. (2) The
dangerous errors late in a session are not arithmetic — they are *plausible reconstructions of data
from memory*, and they are worse precisely because they read well. The catch was not vigilance about
fabrication; it was the accident of a blocked write. See the JOURNAL entry for 2026-09-23.

### 12.46 p70: `c·(depth+pp)` is not the cost variable — two cells with *identical* cost differ by 21 %, and prompt tokens weigh more than generated ones

**Zero boots.** Run with `--skip-run --no-stop` against the container already serving the shipped
config on `node-free-1` (identity read from its own `server_args` echo: ratio 3.51,
`speculative_num_draft_tokens` 8, `capped to 21`, `#tokens` 117,568). Profile
`attic/benchmarking/wide-compose-c4.yaml`, analyzer `.scratch/qwen3-27b/analyze_p70.py` +
`p70_cost_refutation.py`, artifacts `.scratch/phases/p70-wide/` (rc=0, 4 cells × 5 runs).

**The result in one line.** Two cells with **exactly equal** `c·(depth+pp) = 53,248` measure
**65.0 and 87.0** — a **21.4 %** gap against **4.7 %** mean within-cell cv, with **no overlap at
all** between their run values (`slow` 63–69, `disc` 80–91). The quantity §12.45 built its
composition models on therefore cannot be the state variable.

| cell | depth | pp | `c·(depth+pp)` | peak t/s (n=5) | values | cv |
|---|---|---|---|---|---|---|
| `base` | 1024 | 1024 | 8,192 | **103.0** | 97, 100, 103, 104, 120 | 7.6 % |
| `slow` | 1024 | 12288 | **53,248** | **65.0** | 63, 63, 65, 67, 69 | 3.6 % |
| `disc` | 12288 | 1024 | **53,248** | **87.0** | 80, 83, 87, 87, 91 | 4.4 % |
| `corner` | 12288 | 12288 | 98,304 | **58.0** | 55, 58, 58, 60, 60 | 3.1 % |

**Why this is a free control and not a fit.** `slow` and `disc` were constructed to have identical
`c·(depth+pp)`. Any model whose cost term is a function of that quantity — every one of §12.45's
three, plus saturation — predicts their ratio to be exactly **1.000**, with *no parameter choice
available*. Measured **0.747**. No fit, no extrapolation, no noise model is needed to state that a
model is wrong, and the disjoint ranges mean the conclusion does not rest on a p-value. The capacity
gate passed for all four cells (observed `#running-req` = offered 4 everywhere; corner at 83.6 % of
pool, usage 0.84), so this is not the pool ceiling talking.

**The direction, and the model that survives it.** A decode step attends over every resident token —
the prompt *plus the tokens generated so far* — so the mean resident count over a generation of
`depth` tokens is `pp + depth/2`, **not** `depth + pp`. Define `R = c·(pp + depth/2)`. Fitting
`t = a + b·R` on `base` and `corner` **only** and predicting the two held-out cells:

| held-out cell | `R` | predicted | measured | error |
|---|---|---|---|---|
| `slow` | 51,200 | 67.9 | 65.0 | **−4.3 %** |
| `disc` | 28,672 | 81.8 | 87.0 | **+6.3 %** |

Both inside 10 %, on a 2-parameter model fitted to 2 cells, predicting cells that never entered the
fit. The endpoint version `c·(depth+pp)` fitted the same way predicts **74.2 for both** and misses by
−12.4 % and +17.2 %. Expressed as total multipliers over the two 12× axes, **depth costs 0.845 and pp
costs 0.631**, so pp is the more expensive axis. **Per token the asymmetry is 3.18×** (step-time
slopes `1.26e-07` vs `3.96e-08` s/token); the tempting "1.34×" is `0.845/0.631`, a ratio of *rate
ratios*, and quoting it as a per-token cost is a unit error — it compresses the effect because both
axes share the 12× multiplier and the intercept `a`. Use 3.18× for any per-token statement. Endpoint
residency cannot express the asymmetry at all, because it is symmetric in the two, and mean residency
predicts its direction because generated tokens are present for only half the generation on average.

**What is NOT claimed, stated narrowly because each of these has been over-claimed here before.**
- **The ½ weight itself is not established.** An unconstrained fit
  `t = a + b_pp·c·pp + b_g·c·depth` returns `b_g/b_pp = 0.319` with residuals under 0.2 % — but that
  is **3 parameters on 4 points**, and a fit with 1 dof that nails all four cells is arithmetic, not
  evidence. Quote the asymmetry (prompt ≠ generated), never 0.319 or 0.5 as a measured weight.
- **The slope is not a bandwidth.** `b = 1.11e-07 s` per resident token implies
  `32,768 B / b = 294 GB/s`, which **exceeds the ~221 GB/s device streaming budget by 33 %**. A cost
  term that cannot be memory reads is a mixture of read work and per-token kernel/launch overhead.
  Converting it to GB/s would reproduce the exact error that produced §12.32's four retracted figures
  (19–35, 27–35, 51–67, 63–97). **No GB/s number is reported here, deliberately.**
- **This does not resurrect KV bandwidth.** §12.32 measured the server's own decode metric and found
  no detectable bandwidth term; this is a *regressor-selection* result about which token count the
  cost tracks, and "mean resident tokens" may be a proxy for anything co-varying with it.
- **One boot, one order.** Task order was `base, slow, disc, corner`, and in-container drift makes
  later cells slower (§12.23) — `disc` is *later* than `slow` yet 34 % faster, so **drift acts against
  the observed asymmetry**; correcting for it would widen the gap, not close it. That is the one
  direction in which the result is conservative.

**What it costs §12.45.** §12.45's headline — *"at least two additive per-step costs, and they do not
saturate"*, with saturation rejected at `P = 1.000` — **stands**; it is a claim about the corner
landing below `slow`, and p70 says nothing against it. What does not survive is the implicit premise
shared by all three composition rules: that a depth cost and a prompt cost are the *same kind of
quantity*, interchangeable up to a factor. The row-ratio / column-ratio table there (0.851 vs 0.878)
was comparing two axes that this experiment shows behave differently. **Any future composition test
must use a cost variable asymmetric in `pp` and `depth`.** The three-model comparison as designed here
is VOID, and the pre-registered control rule caught it: the rule fired on the boot's own free control
(21.4 % > 15.9 % model spread) *before* any verdict was printed, which is the outcome the
pre-registration existed to produce.

**§12.45's own data points the same way, and cannot be used as proof that it does.** Converting its
table to step-time slopes per token: the depth axis gives `2.14e-08 s/token` and the pp axis
`4.64e-08` — a **2.17×** asymmetry, same direction as p70's 3.18×. But that comparison is not a
symmetry test, and saying it "confirms" the finding would be an overclaim in the other direction:
**p68's two axes have different multipliers** (depth 4096→8192 is 2×, pp 1024→4096 is 4×), so
extracting per-token slopes from it already assumes the functional form whose asymmetry is in
question. Its reassuring `0.851` vs `0.903` row/column "closeness" is a consequence of that, not
evidence of symmetry. What the agreement is worth: two experiments at different `c`, different
absolute ranges, and different axis ratios give the same sign. What it is not worth: a number.

**Why the pre-registered predictions were 2× off, kept because it is a reusable trap.** The profile
predicted 191/144/144/115 by extrapolating the c = 8 fit `t = 0.00492 + 3.82e-8·cost` down to c = 4.
Measured `a` at c = 4 is **0.009024 — nearly 2× larger than 0.00492**. The cost-independent term is
batch-size dependent, so **an intercept fitted at one concurrency must not be transferred to
another**; only slopes transfer, and even the slope changed. The profile's own caveat said this in
advance and it fired exactly as written. A second arithmetic error in the same block is recorded in
the profile itself: the "SPREAD 12.1 %" figure divided the 18.7 model gap by **154.0**, which is
p68's base rate at c = 8, not p70's — a stale denominator whose numerator was right, which is why it
survived review. Correct value 18.7/115.3 = **16.2 %**.

**Instrumentation notes.** `--skip-run` does **not** copy the serve log out of the container, so the
capacity gate had to be filled by fetching `/tmp/sparkrun_serve.log` manually before it went away — a
zero-boot run is not a zero-instrumentation run. The analyzer initially **failed open**: with no serve
log, `run_req_by_cell` returned `{}`, every cell printed `UNVERIFIED`, `excluded` stayed empty, and
the model comparison printed a verdict anyway. Now it refuses unless all four cells are attributed
(§7). Cell identity never depended on that path — the result JSON carries `context_size` and
`prompt_size` directly, which is why the numbers were trustworthy while the gate was not.

### 12.47 p71: §12.46 replicates — and the claim that survives is smaller than the one a single boot produced

**Zero boots, same container as p70, `pp`-sweep order reversed.** Profile
`attic/benchmarking/symmetric-pair-only.yaml`; analyzer `.scratch/qwen3-27b/analyze_p71.py`, whose pass band
`[0.62, 0.87]` and explicit FAIL branch `[0.90, 1.10]` were written **before** the data — the
standing discipline in this file, because every analysis here written after seeing numbers produced a
conclusion that later did not survive. Artifacts `.scratch/phases/p71-symm/` (rc = 0, 4 cells × 5 runs).

| cell | depth | pp | `c·(depth+pp)` | p70 | p71 | p71 run values |
|---|---|---|---|---|---|---|
| `base` | 1024 | 1024 | 8,192 | 103.0 | 101.0 | 97, …, 109 |
| `slow` | 1024 | 12288 | **53,248** | **65.0** | **66.0** | 63, …, 69 |
| `disc` | 12288 | 1024 | **53,248** | **87.0** | **92.0** | 78, …, 100 |
| `corner` | 12288 | 12288 | 98,304 | 58.0 | 59.0 | 56, …, 63 |

**What replicated.** `slow / disc` = **0.747** (p70) and **0.717** (p71) — **4.0 % apart** across
independent boots with the sweep order reversed. `c·(depth+pp)` predicts **1.000 in both, with no
free parameter**, and is missed by 25 % and 28 %. Run ranges are **disjoint in both boots** (p70
63–69 vs 80–91; p71 63–69 vs 78–100). Capacity gate clean in both: observed `#running-req` equalled
the offered 4 in all eight cells, control cells at 45.3 % of the 117,568-token pool.

**The order reversal is the part that earns the result.** In p70 the asymmetric pair ran `slow`
early and `disc` late; in p71 `disc` is reached **last** in its task. Within-container drift makes
later cells slower (§12.23), so drift favoured `slow` in p70 and favours `disc` in p71 — it **opposes
the observed gap in both orders**. A drift artifact cannot do that. This is the strongest statement
this design can make, and it is still not a mechanism.

**What did NOT replicate, and what to quote.** The asymmetry **magnitude** moved from **3.18× to
5.42×**, and each boot's own bootstrap CI is wide — p70 `[1.97, 4.81]`, p71 `[1.67, 16.16]` (4,000
resamples of the run values within each cell). p71's mean-resident fit, using the same
`base`+`corner` pair §12.46 fitted on, misses the held-out `disc` by **+12.7 %** — outside the ±10 %
band that §12.46's success was stated in.

- **Quote:** prompt tokens cost more per decode step than generated tokens, at roughly **3×**. The
  **direction** is replicated twice with disjoint ranges and drift opposing it; the **magnitude is
  not pinned**.
- **Do not quote** "3.18×" as a measurement. It is a difference of two large step times on a 15 %
  rate change, so it is dominated by intercept uncertainty rather than by run noise, and two boots
  disagree by 1.7×.
- The `b` coefficient (resident-token slope) is **1.115e-07 → 1.043e-07 s/token, stable to 6.5 %**,
  and the intercept to 2.6 %. Those are the stable quantities, and nobody looked for them until now.

**Why the magnitude is unresolvable, stated so no one spends boots trying.** `b_depth` comes from
`base → disc`, a 15 % rate change; `b_pp` from a 37 % change. A shared intercept error is divided by a
small numerator on one side and a large one on the other, so the ratio inherits the small side's
relative error. **More runs at the same two depths cannot fix a badly-conditioned ratio.** The fix is
a wide depth sweep at fixed `pp` — five depth points at `pp` = 1024, `c` = 4, every cell below every
capacity ceiling — which is `attic/benchmarking/depth-sweep-c4.yaml` (p72). It also delivers the first real
**linearity** test in this thread: §12.34/p69 claimed a depth "kink" from three depth values, which is
not a test of shape.

**Correction to the profile, mine, recorded rather than smoothed over.** `symmetric-pair-only.yaml`
claimed sparkrun's index zipping "yields exactly two cells". It does not: benchy creates one task per
`depth` and sweeps `pp` inside each task, so the run executed the **full 2×2** — its own
`Estimated test iterations: 20` (= 4 cells × 5 runs) said so. The `--dry-run` pre-flight that WORK §7
calls mandatory was skipped, so this came to light from the benchlog after launch instead of in the
three seconds it costs. The profile description is corrected rather than the result reinterpreted to
match it; a full grid in reversed order is the better experiment anyway, and p72's driver now refuses
to start unless a dry run reports the expected cell count.

### 12.48 p72: five depths at fixed `pp`, and **no depth slope is significant on either metric** — plus a threshold error that would have manufactured one

> **SUPERSEDED ON ITS HEADLINE by §12.49, which doubles the replication by adding the same sweep in
> the opposite depth order.** "No depth slope is significant on either metric" was true of *this run
> alone at n = 5*, and it does not survive n = 10: on `tg_throughput` — the metric this document's
> ~20 % figure is written in — the pooled crossover **is** significant (exact label-permutation
> *p* = 0.025, per-run *t* = −2.87). The threshold-error lesson below stands unchanged and is the
> more valuable half of the section. **Do not quote this section's title without §12.49 attached.**

**What the run was.** The cleanest depth axis this harness can produce: `pp` fixed at 1024, `c = 4`
fixed, five depths — 1024, 4096, 8192, 12288, 16384 — a 16× span, five runs each, on one container.
Every cell admitted its offered batch (`#running-req` = 4 in all five, deepest cell at 59 % of pool,
usage 0.62), so no cell is capacity-limited and none needed excluding. `pp` constant means per-request
prefill work is constant, and peak is read from the decode-phase row, so prefill does not enter the
metric. Previous sweeps varied depth and `pp` together, or had three depth points and called that
linearity (§12.34, §12.46).

**Result: neither metric produces a significant slope.**

| metric | medians 1024 → 16384 | endpoint ratio | slope *t* | *p* (dof 3) | power vs a true 20 % decline |
|---|---|---|---|---|---|
| `tg_throughput` (the metric this doc's ~20 % figure uses) | 91.5 → 78.6 | −14.1 % | −1.90 | 0.153 | **48 %** |
| `peak_throughput` | 104.0 → 95.0 | −8.7 % | −3.08 | 0.054 | **91 %** |

**The threshold error, which is the part that matters most.** Five cells means **dof = 3**, whose
two-tailed 5 % critical value is **3.182 — not 2.0**. The first version of
`flatness_p72.py` used the normal cutoff `|t| ≥ 2` and duly reported the `peak_throughput` slope
(*t* = −3.08) as **SIGNIFICANT**. Judged correctly it is not (*p* = 0.054). Had that stood, this
section would have announced a measured depth penalty at uncongested batch — the doc's central
quantity — off a five-point fit whose threshold was wrong. **The arithmetic was right the whole
time; only the model behind the cutoff changed.** This is the same shape as §12.40: the numbers
never lied, the reference distribution did.

**Two further bugs the selftests caught, both in the statistics helpers rather than the data
handling** — worth listing because each would have survived review:
- The first `t_ptwo` integrated the density to a bound scaled by |*t*|, and a check against
  published critical values found it **exactly 2× wrong at dof = 1 only** (12.512 vs 12.706) while
  correct at dof 2–10 — tail truncation, invisible in the case actually run. Replaced with the
  exact incomplete-beta form.
- That form then returned the **one-tailed** p, so every critical value came out 2× published and
  *p*(*t*_crit) = 0.1000 at every dof. A uniform factor error is precisely what comparison against
  published constants detects and what reading the code does not. `--selftest` now checks dof
  1, 2, 3, 4, 5, 6, 8, 10, 20, 30 against published values and passes.

**What follows, stated at the strength the design supports.**
- On `tg_throughput`, the metric the doc's claims are written in, this run **cannot resolve** a 20 %
  depth penalty: power 48 %, slope *p* = 0.153. That is *not* a refutation (§12.40's discipline) and
  must not be written as "no depth cost at c = 4". It is an undetectable effect at *n* = 5 with
  6–16 % cv.
- On `peak_throughput`, power is 91 % and the slope is still not significant. So the honest
  statement there is **positive**: an uncongested `c = 4` decode path loses **less than ~20 %** over a
  16× depth span. That corroborates §12.34/§12.42 from an independent direction — the ~20 % "depth
  penalty" this document carries is a property of **congested, pool-limited** operating points, not
  of decode at depth per se.
- The two metrics **disagree about whether a penalty exists**, and nothing here adjudicates it.
  `peak_throughput` is an instantaneous maximum, `tg_throughput` a sustained mean; the disagreement
  is itself a datum about which quantity responds to depth, and it is unresolved.

**The acceptance pre-registration came back null in the direction opposite to §12.33.** Pooled
16384-vs-lower contrast: Δmedian **+0.170** (acceptance *higher* at 16384, not lower), *z* = −2.73,
*p* = 6.3×10⁻³, bootstrap CI [−0.030, +0.300]. **The CI spans zero while *p* does not**, and the
per-depth medians are 3.235 / 3.060 / 3.090 / 3.070 / 3.290 — non-monotone. Two things this must not
become: not "acceptance rises with depth", and not "§12.33 refuted" (a CI spanning zero is an
underpowered run, per §12.40). It is the third consecutive acceptance result that fails to replicate
(§12.36 found the same for `pp`/resident-token contrasts), which is itself the finding: **acceptance
in this recipe is not reliably measurable from these cells at *n* = 5, and the *z* = −2.73 with a
zero-spanning CI should be read as the two statistics disagreeing about a small effect, not as
evidence of a reversal.**

**Methodological rule this section adds.** *A significance threshold is a model, and it has to be
chosen from the design's degrees of freedom, not from a habitual constant.* With five points,
|*t*| ≥ 2 is a **10 %** test, not a 5 % one. Any fit in this document with fewer than ~10 points
should state its dof and its critical value alongside the estimate; `flatness_p72.py` now prints
both, and its `--selftest` is the pattern every statistical helper here should follow.

### 12.49 p73: the same sweep run backwards — a crossover that settles what one order could not, and an over-correction of my own to go with it

**What was added, and why it is the design this question needed.** p72 ran depths ascending
(1024 → 16384); p73 ran the identical profile descending (16384 → 1024), same container, same boot,
`#tokens: 117,568`, `capped to 21`, ~2.5 h apart. Same container matters: it makes this a
**within-boot crossover**, so a level shift between runs cancels and the only thing that differs is
which depth each position in the sweep measured. p72's known weakness — "acceptance is highest at
the *first* depth" (3.290) and this doc's recurring suspicion of within-container drift (§12.36) —
is exactly the confound a crossover removes. `--skip-run`, so **zero boots**.

**Order effect measured, not assumed: mean |spread| 2.77 tok/s = 3.4 % of typical throughput**,
per depth 3.9 / 7.0 / 1.0 / 2.8 / 1.7 %. That is the drift any single-order sweep silently carries
and mislabels as a depth effect. It is smaller than the depth span (11.6 tok/s) but the same size as
the largest adjacent-pair gap (6.9 tok/s) — which is precisely why adjacent-pair tests kept coming
back null here and why they are the wrong comparison for this question (§12.49 test 3 below).

**Result, n = 10 per depth (two orders pooled), five depths at `c = 4`, `pp` fixed at 1024:**

| metric | cluster means 1024 → 16384 | exact label-permutation *p* | per-run *t* (dof 44) | verdict |
|---|---|---|---|---|
| `tg_throughput` | 87.4 → 77.9 (**−10.9 %**) | **0.0250** | **−2.87** | **significant decline** |
| `peak_throughput` | 103.7 → 98.4 (−5.1 %) | 0.1250 | −1.56 | not significant |

So the honest summary of §12.48 + §12.49 together is **not** "no depth cost at uncongested batch"
and **not** "~20 % confirmed". It is: **at `c = 4`, `pp` fixed, every cell admitted, a ~11 % decline
over a 16× depth span is detectable on the sustained metric and is not detectable on the peak
metric.** The two metrics disagree, they disagreed in p72 too, and doubling *n* did not adjudicate
it — which makes the disagreement itself the most robust acceptance-related datum in this section.
The ~20 % figure remains a **congested/pool-limited** number (§12.34, §12.42); the uncongested
number is ~11 %, not ~20 %, and not zero.

**Three statistics, deliberately all printed, because they disagree and the disagreement is
informative** (`.scratch/qwen3-27b/trend_test.py`, which prints all three every time):

1. **Exact permutation over depth labels** (120 permutations of 5 depths; minimum attainable
   *p* = 0.0083). Distribution-free, makes no assumption about within-cell shape, and cannot be
   inflated by any weighting choice. This is the test to quote when the within-cell distribution is
   as lumpy as it is here (cv 6–16 % per cell).
2. **Per-run OLS on the within-cell residual variance**, `t = −2.87`, residual dof **45**.
3. **Adjacent-pair bootstrap** — null on *all four* pairs (CIs −14.4..+5.2, −15.9..+4.1,
   −13.3..+7.3, −11.4..+15.5). **This is the least powerful comparison available and its nulls mean
   almost nothing**; four consecutive nulls alongside a significant ordered trend is expected, not
   contradictory. Quoting only this test would have concluded "no depth effect" from the same data
   that supports a 10.9 % decline.

**The statistical error I made in this section's own tooling, which is the more instructive half.**
My first version of `trend_test.py` regressed the five cluster *means* at `dof = 3` and printed a
scolding note that the 50 runs were "pseudo-replicates" that must not be treated as independent. That
note was **wrong, and it was an over-correction** — the same failure mode this document keeps
cataloguing, committed by me against my own pooled result:

* With depth as a **fixed factor** and `runs` genuine repetitions measured inside each cell, the
  runs are *not* pseudo-replicates. They are the replication. The slope's standard error should be
  built from the **within-cell** variance, which is exactly what per-run OLS does. True
  pseudo-replication is subsampling a single experimental unit — five measurements of *one* request —
  and that is not this design.
* The genuine defect in the pooled per-run regression was only that it reported `dof = 48` where the
  five-level model absorbs 4 df, so the residual is **45** (44 with the intercept counted
  separately). A trivial numerical slip, which I had inflated into a categorical statistical
  prohibition.
* Both defensible tests then **agree** here (`tg` significant, `peak` not), so the wrong note
  changed no conclusion — which is exactly why it survived until I checked it against a one-way
  ANOVA decomposition (`F(1,45) = 8.25`, `t = +2.87`) instead of trusting my reasoning.

**The rule that survives, stated narrowly enough to be false-able:** *do not average away
replication to shrink a denominator, and do not treat replication as an offence either.* Quote the
test whose error term matches the design — per-run OLS with within-cell variance, or the exact
label permutation — and never quote `crit = 2.0` at dof 3 (see §12.48; the same file's `crit_t()`
now prints the critical value beside every *t*). The pessimism trap is real: a power claim computed
from cluster means said "smallest detectable 9.1 tok/s", which would have let a genuine 11 % effect
be called undetectable.

**What this run nearly lost, and the driver bug behind it — plus my own wrong conclusion that it
*had* lost it.** p73's serve log is fetched only **after** the run, and the driver exited first on
its own depth-order guard — which fired spuriously because `preflight.txt` is written through ssh and the extracted order string
carried a trailing `\r`, so `"16384 12288 8192 4096 1024\r" != "16384 12288 8192 4096 1024"`. The
dry-run output printed immediately above the failure plainly showed the correct descending order; an
invisible byte refused a valid run. **A guard that fires on every run is worse than no guard** — it
trains the reader to skim past the warning, including on the run where it would be telling the
truth. This is the *second* whitespace bug in that one guard (an earlier version `tr -d ' '`'d only
one side); both sides are now normalised. Throughput survived because it lives in the JSON, which is
written before the guard. **General form: a guard that aborts after the expensive work and before the
cheap capture risks destroying the expensive work — order capture above every gate, or make the gate
non-fatal.** And a guard must be tested against a known-good input before it is trusted to refuse.

> **CORRECTION, made the same day, and it is the better lesson.** I wrote here that p73's acceptance
> data was **gone**. It was not. The container is `--skip-run`/`--no-stop` and was still up eight hours
> later with `/tmp/sparkrun_serve.log` inside it spanning both runs, and one `docker exec cat`
> recovered all of it (§12.50). **A measurement is lost only when its last copy is destroyed; a
> driver failing to copy something is not evidence that the thing stopped existing.** I inferred
> destruction from a missing local file without checking the one place the file was described as
> living — and the description was in my own driver's comment. Recovered data, not new data: the
> throughput conclusion above is unchanged.

**Co-tenancy note, checked rather than assumed.** `#running-req` values above the design maximum of 4
appear 224 times in p72's cumulative serve log — but **zero of them fall inside p72's five task
windows** (all 484 in-window lines are ≤ 4). The foreign load is other phases run on that shared
container before and after. So p72's and p73's throughput cells are clean. This is worth stating
explicitly because the histogram *looks* damning and I nearly wrote it up as contamination; the
windowing is what distinguishes a real confound from an artefact of a cumulative log. **A
cumulative serve log is not a record of one run — attribute before you conclude.**

**Still open.** The `tg`-vs-`peak` disagreement is now replicated twice and unresolved, and it is
the live question: peak is an instantaneous maximum over a burst, `tg_throughput` a sustained mean,
and only the sustained metric declines. That is consistent with depth hurting the *steady state*
(scheduling, cache residency, acceptance) without hurting the *instantaneous* best case — but this
design cannot separate them, and I am not going to assert a reason. A `--skip-run` repeat with
`runs: 10` at `c = 4` and `c = 8` would decide whether the split is metric-intrinsic or
batch-dependent; it costs no boots.

### 12.50 The recovered p73 acceptance data: on the same two runs, **throughput falls ~11 % with depth while acceptance does not** — which removes acceptance as its explanation

**Where the data came from.** p73's serve log, believed destroyed (§12.49's correction), was pulled
out of the still-running `--skip-run` container. p72's was on disk. **Both were then recomputed here,
in one pass, with one filter, one window rule, one timezone offset** — because comparing p73 against
the acceptance figures already published in §12.48 means comparing two different filter
implementations, and that is how a difference gets manufactured. The validation that this was worth
doing: **the p72 column reproduced §12.48's recorded values exactly** (3.235 / 3.060 / 3.090 / 3.070 /
3.290), so the shared filter agrees with the one that produced the published numbers, and p73 is now
comparable to them. Script: `.scratch/qwen3-27b/accept_crossover.py`; steady filter is
`#running-req` **exactly** 4 (not `≥ 4` — ramp and co-tenant lines have different acceptance).

| `depth` | p72 (ascending) | p73 (descending) | order spread | pooled | *n* |
|---|---|---|---|---|---|
| 1024 | 3.235 | 3.200 | 0.035 | **3.215** | 118 |
| 4096 | 3.060 | 3.080 | 0.020 | **3.070** | 133 |
| 8192 | 3.090 | 3.170 | 0.080 | **3.110** | 135 |
| 12288 | 3.070 | 3.175 | 0.105 | **3.140** | 107 |
| 16384 | 3.290 | 3.165 | **0.125** | **3.240** | 121 |

Pooled medians **3.215 → 3.070 → 3.110 → 3.140 → 3.240**: endpoint ratio **1.008 (+0.8 %)**, exact
label-permutation trend test **p = 0.73** (slope +0.004 milli-accept per 1k tokens). **Not a
decline in either sweep order, and not flat in shape — U-shaped, with both depth extremes above the
interior.**

**The dissociation, which is the finding.** §12.33 proposed that most of the 16k decode penalty is
acceptance falling. On the **same two runs** that produced §12.49's throughput result, throughput
falls **−10.9 %** from depth 1024 to 16384 while acceptance is **flat to slightly up (+0.8 %)**. Same
container, same boot, same cells, same `pp`, same `c`, same window rule. Whatever the ~11 % uncongested
depth cost is, **it is not acceptance**, and §12.33's mechanism cannot be the explanation for
§12.49's effect. That is the cleanest internal contradiction this document has resolved in one
comparison, and it was free — a `docker exec` and a re-filter.

**Three things this does not do, all of which would be easy to overclaim:**

1. **It does not refute §12.33, and it is not the experiment §12.33 asked for.** §12.33 asked for
   "*n* ≈ 40–50 per cell over **≥ 2 boots**". This delivers *n* = 107–135 per cell — well past the
   sample size — **on one boot**. It satisfies the *n* criterion and fails the boots criterion, so
   it cannot settle §12.33 and must not be written as if it had. Absolute acceptance levels are not
   comparable across boots anyway: the two arms of *this one design* differ by ~7 % at 8192 (3.090 vs
   3.170), so only within-run relative comparisons travel.
2. **The U-shape is confounded with sweep position and cannot be reported as a depth effect.** In
   *both* orders the depth extremes (1024, 16384) are also the sweep extremes (first, last). "Depth
   1024 and 16384 are special" and "the first and last cell of any sweep are special" are therefore
   **not separable by a 5-point crossover**, no matter how many repetitions. A middle-anchored design
   (start at 8192, e.g. 8192→1024→16384→4096→12288) would separate them. Until then: U-shaped
   *observation*, position-confounded *interpretation*.
3. **The order spread grows monotonically with depth** — 0.035, 0.020, 0.080, 0.105, **0.125** — so
   the deepest cell is the least reproducible, and it is the cell on which §12.33's ~13 % claim rests.
   That is a caution about that claim's fragility, not a refutation of it.

**What to believe about acceptance now, stated at the strength the evidence supports.** Acceptance in
this recipe is **not measurably a function of `depth` at `c = 4`, `pp = 1024`, within a boot**, over a
16× depth span and 614 steady decode lines pooled across the two orderings (~307 each). It is a
property of the **content** being drafted
against, and §12.36 already killed the `pp`/resident-token contrasts. Any future depth-cost model that
attributes throughput loss to acceptance has to explain why acceptance is flat here while throughput
is not — which is a constraint that did not exist before this comparison.

**Methodological rule this section adds.** *Recover before you re-run.* I nearly queued another
zero-boot sweep to replace data that was sitting in a live container, and the throughput half of this
result would have been reported without its acceptance half. The check is one line and it is
dispositional, not clever: **when an artifact is missing, go to the place it was written to be
produced and look — including when the description of that place is something I wrote.** A missing
local file licenses a search, not a conclusion.
### 12.51 p76: the ratio-1.2 capacity gain reproduces **on one node, ABBA** — and the arm-vs-node confound the phase was built to remove never existed

**Verdict first.** The capacity half of the ratio-1.2 result reproduces on a **single node**, in a
**position-balanced** design, with **no overlap** between arms. Four fresh boots of
`node-free-1`, order `ship r12 r12 ship`, depth 16384, offered `c = 16`, `newrun = 128`, two load
reps per boot (32 requests/arm). Artifacts `.scratch/phases/p76-samenode/`; analyzer
`.scratch/qwen3-27b/analyze_phase76.py`, whose decision rules were fixed before the data.

| arm | boots (position) | `capped` | `#tokens` | ceiling `min(cap, #tokens//depth)` | peak `#running-req` |
|---|---|---|---|---|---|
| ship (3.51) | a, d | 21, 21 | 119,041 / 117,981 | **7, 7** | **7, 7** |
| r12 (1.2) | b, c | 14, 14 | 238,603 / 237,753 | **14, 14** | **13, 13** |

**Position drift is measured, not assumed: 0.6 %** (ship a→d −0.3 %, r12 b→c −0.9 %) against §12.49's
harness baseline of 3.4 %. A 7-vs-13 separation cannot survive a 0.6 % drift by accident, and the
two arms' `#running-req` distributions are disjoint, so the separation is not a position artefact.
`#tokens` agrees to 0.9 % across boots within each arm. **`usable = min(cap, #tokens // L)` holds
again**, and now on one node, where it cannot be a node difference — **but `L` is not a profile
parameter, and this run only looks exact because of how its load was built.** In a llama-benchy
profile `depth` is the *generated* length and `pp` the *prompt* length (§12.43), so a request resides
`pp + g` tokens at generation `g`; phase 26's serve log shows a per-request peak of **18,580–18,621**,
i.e. `pp + depth = 18,432`, confirming that reading. Feeding `L = 18,432` into the formula gives
ceilings of **6 (ship) and 12 (r12)** against observed peaks of **7 and 12/13**, so the
end-of-generation bound is **conservative**, understating the peak by about one stream — because
admission is progressive and the peak occurs mid-generation. Verified directly: at ship's peak,
`#full token` was 116,011 spread over 7 requests = **16,573 each**, not 18,432. **In p76 the load
generator's prompt was ~16,206 tokens ≈ `depth`, so `L = depth` reproduced the observed 7 exactly —
by construction of this particular load, not because `L = depth` is the rule.** Treat the formula as a
bound with `L` taken from the window being explained (prompt + tokens generated by then), and quote
the observed `#running-req` as the measurement rather than the ceiling.

**Quote 13, not 14.** The r12 *ceiling* is 14 and the *observed* peak is 13. Phase 26's r12 arm
observed 12 of 12 offered — truncated by the experiment's own `c = 12`, not by capacity — and its
"14" was always the derived ceiling. An earlier revision of the recipe comment asserted "14 usable
measured by phase 26", which promoted a bound to an observation; corrected in
`qwen3.8-27b-nvfp4-dflash2-sglang.yaml`. The shipped arm still wastes **14 of its 21 granted slots**
(peak 7 with `capped` 21), which is now the second independent boot series showing the token pool,
not the mamba cap, is the wall at 16k.

**Throughput: NO admissible verdict, and the reason is arithmetic rather than bad luck.** The
hand-rolled load generator produced **259,326 prefilled against 2,048 decoded** tokens — 0.8 % of
the batch by count and **94 % of the 134 s wall by time** at ~2,000 t/s prefill. With the pool not
binding, `aggregate decode t/s ≈ decode_tokens / wall`, every arm prefills the same total, and each
arm's `#running-req` is at its ceiling so the arms are not even differing in stream count during the
window. **The metric is pinned by construction and cannot separate the arms.** §12.43 documents this
exact trap — benchy splits each cell into a prefill phase and a decode phase, and `tg_throughput`
measures decode only — and I walked into it while citing §12.43 as my authority. Documenting a trap
and avoiding a trap are different skills. **Do not quote this run's `15.3 vs 15.6 t/s` against
phase 26's 1.558×**; that figure came from a decode-dominated harness cell, and the two are not
comparable quantities. A fix is specified below; it has not been run.

**And the confound this phase was built to remove was not there.** p76 was launched to repair an
"arm-vs-node confound in the ratio-1.2 result that §12.43 and §12.44 both flagged". **False on three
counts, each found by reading the artifacts rather than my notes about them:**

1. **The confound does not exist.** `p26a-0921/p26_10_0_4_34.driver.log` records
   `order='ship r12'`; `p26b-0921/p26_10_0_4_35.driver.log` records `order='r12 ship'`. Phase 26 ran
   **both arms on both nodes, counterbalanced** — arm and node are orthogonalised, not aliased.
   §12.42 makes the same point in prose about the neighbouring experiment: "two independent nodes,
   mirrored arm orders".
2. **The cited sections do not say it.** §12.43 is *"What llama-benchy's `depth` and `pp` actually
   are"*; §12.44 is *"neither prompt length nor resident tokens prices the decode cost"*. Neither
   mentions phase 26, the ratio arms, or a node confound.
3. **`p74` does not exist.** No `.scratch/phases/p74*`, no artifacts, no driver log. The sentence I had in
   mind — "my p74 boots ship on `node-free-1` and r12 on `node-free-2`" — described a run that was never executed.

**So p76 was still worth running, for a reason unrelated to its stated purpose.** Phase 26 gave two
boots per arm spread across two nodes; p76 gives two per arm on **one** node with balanced order.
That is a different control, and in one respect stronger: node variation is removed from the
comparison entirely rather than balanced across it. **A good result obtained from a bad justification
is not a good process**, and the reproduction should be cited as "confirmed under a same-node
order-balanced design", not as "the confound in §12.15 has now been removed" — there was no such
confound to remove.

**The lesson, which is the reason this section exists instead of being a footnote.** I re-derived the
"confound" from my own earlier prose about my own earlier work, and the prose was wrong. It had the
full shape of a careful note — a named section pair, a specific mechanism, and the pleasing posture of
self-criticism ("I found a flaw in my earlier design"). Every element of that shape was fabricated or
misremembered. **A self-criticism is not evidence about the thing it criticises**, and it arguably
deserves *more* scrutiny than a neutral claim because it flatters the narrator. The check that settled
it was two greps over driver logs I had written myself, and it cost under a minute; the four boots it
justified cost about an hour each. **Before spending an experiment to fix a defect, read the artifact
that records whether the defect is present — and when the defect is one you allege about yourself,
that reading is mandatory rather than advisable, because it is the case where you are least likely to
check.**

**End-to-end, from the same artifacts, and it points the other way: r12 costs +11.3 % per-request
latency.** `p76_e2e_throughput.py` uses the load driver's per-request `t0`/`t1` (monotonic clock),
which are not quantities the serve-log aggregation can pin. Per boot, median over 16 requests × 2 reps:

| boot | arm | median wall (s) | median rate (t/s) | aggregate (t/s) | peak `#running-req` | peak `#queue-req` |
|---|---|---|---|---|---|---|
| a | ship | 118.9 / 114.3 | 1.08 / 1.12 | 15.19 / 15.34 | 7 | 9 |
| d | ship | 114.6 / 115.0 | 1.12 / 1.11 | 15.22 / 15.24 | 7 | 6 |
| b | r12 | 127.4 / 127.2 | 1.00 / 1.01 | 15.63 / 15.60 | 13 | 3 |
| c | r12 | 128.1 / 128.4 | 1.00 / 1.00 | 15.46 / 15.49 | 13 | 3 |

**`peak`, not `mode`, and that distinction nearly produced an error here.** The serve log emits a
`Decode batch` line roughly every 60 s, so a ~5-minute window holds only **4–5 lines per boot** — too
few for a mode to mean anything. `c_r12`'s observed distribution is `{1:2, 4:1, 13:1}`: its *mode* is
1 while its *peak* is 13. A mode-based column would have printed "c_r12 ran 1 stream", contradicting
both its own arm-mate `b` and the capacity analysis above, and it would have looked like a discovery.
**On n = 4 report the max and say n.** The peak of **7 (ship) and 13 (r12)** is what the capacity claim
actually rests on; it is consistent across both boots of each arm.

**Arm medians: ship 114.8 s vs r12 127.8 s, ratio 1.113**, with rep-to-rep drift of only **2.1 %
(ship) and 0.2 % (r12)** — so the gap is ~5× the repeat noise, all four boots are in the same order
(ship's slowest 118.9 s is still below r12's fastest 127.2 s), and position is balanced. The earlier
pooled version of this statistic printed "within-arm spread 116.9 %", which was an artefact of pooling
per-request values across ramp and steady phases; **the per-rep medians above are the right unit and
they agree with each other to under 1 %.**

**Why this is not a contradiction of the capacity result, and why it is not a refutation either.** The
direction is what queueing-plus-contention predicts: ship admits 7 of 12–16 and runs a queue up to 9,
yet each of its 7 streams gets a larger share of decode bandwidth, so its *per-request* wall is
shorter; r12 admits 13, so more streams contend and each individual request decodes more slowly.
Aggregate is **15.23 vs 15.55 (ratio 1.021)** — and that is the number that must not be read as "no
throughput benefit", because aggregate decode t/s is pinned by the identical prefill total across arms
(§12.51 above). **So what is established is the latency cost at this load shape; what remains
unmeasured is whether any aggregate benefit exists to pay for it.** Reading the 1.021 as "no gain" and
the 1.113 as "a cost" would be applying two different standards to two different metrics — one pinned,
one not.

**The operational reading, stated at the strength the evidence supports.** At 16k contexts with
offered concurrency 12–16, lowering `mamba_full_memory_ratio` to 1.2 buys stream count (7 → 13,
established twice) and **costs ~11 % per-request latency on a prefill-dominated load**, with the
throughput benefit still unmeasured. That is a genuine reason to be cautious about the "just lower
the ratio for long context" advice in the recipe comment, and it does **not** support shipping a
change. It is one node, one load shape, and a regime (long prompts, short outputs) chosen for
capacity measurement rather than for service quality. **p77 is running the decode-dominated version of
exactly this comparison** (`newrun` 128 → 768 sized from measured rates, `OFFER` 16 → 12 so r12's
ceiling of 14 is not clipped), and its pre-registered rule requires the prefill share of wall time to
be reported before any ratio is quoted.

**What would settle the throughput claim, specified but not run.** → **p77 ran this (see §12.53):
decode share came out 14–35 % (mean 21 %), so the pre-registered 60 % gate vetoed the throughput
verdict, and the decomposition that looked like a repair turned out to be confounded by the mechanism
under test. The throughput claim is still unreplicated.**

<details><summary>original specification, kept because the sizing arithmetic is still correct</summary>

Hold `pp` fixed at 2,048 and raise
`newrun` so that decode dominates: at `c = 16`, `depth = 16384`, decode tokens = `c × newrun × reps`
and prefill tokens = `c × depth × reps`, so `newrun ≥ 2048` puts decode near 75 % of wall; at
`newrun = 4096` prefill is ~28 %. Same ABBA frame, same node, `#running-req` re-checked per window to
confirm neither arm became queue-limited (ship's 7 streams against 16 offered *will* queue, which is
the point — but the queueing must be visible in `#queue-req` rather than inferred). Estimate ≈4 boots
≈ 4 hours on `node-free-1`. Until then the capacity claim stands and the throughput claim is **unreplicated**,
neither confirmed nor refuted. **p77 executed this specification on 2026-09-23 and the gate fired; see
§12.53 for what it did and did not establish.** The sizing arithmetic above is why `newrun: 768` was
still too short — it is not a design flaw but an input that was off by ~3×.</details>

### 12.52 p78: the pool-matched pair says **there is no detectable per-sequence step cost** — and a design claim I made and then retracted in the same hour

**Verdict first.** `(c=4, depth=8192, pp=2048)` versus `(c=8, depth=4096, pp=1024)` have **identical
`c·depth` (32,768) and identical pool demand `c·(depth+pp)` (40,960)**. Doubling the batch changes
per-stream decode throughput by **+3.2 %, 95 % CI [−4.2 %, +11.0 %]** — a null. Converting to step time
(`t = c·acc/agg`, measured `acc` 3.200 and 3.180) gives **Δt = −0.0078 s, CI [−0.0231, +0.0075]**, so the
per-sequence cost is **`A_seq = −0.0019 ± 0.0038` s/sequence**. §12.30's fit claimed
**`A_seq = +0.013 ± 0.0026` s**. The two disagree by **3.2 σ on the combined error bars** (3.9 σ on
this run's alone): the gap is 0.0150 s against a combined se of 0.0046. This run's own error bar is
±0.0038, so it is not that the new measurement is too noisy to see §12.30's
effect — it is that the new measurement sees the opposite sign.

**Why this pair isolates `A_seq` when I thought it could not.** I concluded mid-analysis that the pair
was void because "batch and depth vary together, perfectly", and that is true: equal `c·depth` forces
`depth_B = depth_A/2`. I was wrong to stop there. Under the additive model
`t = a·1 + A_seq·c + K·B + M·P`, matching **both** `B` and `P` cancels `K` and `M` between the cells
leaving **`t_B − t_A = A_seq·(c_B − c_A)`** — exactly, with no assumption about bytes or residency. The
design's whole point was to match `P` as well as `B`; matching `P` is also what makes it an `A_seq`
test, and I checked the confound I had designed for (pool) while missing the identification I had
designed for (the coefficient). **Lesson: verify what a design identifies, not only what it controls
for. A control that works and a contrast that is unidentified look identical in a results table.**
This is the same failure as §12.30's "rank is not resolution", arrived at from the other side: there I
had full rank and no resolution; here I had a clean control and no identification — until I did the
algebra, which took four lines and cost me a wrong conclusion.

**What the null does and does not say.** It says a **depth-independent** per-sequence step cost of
+13 ms is excluded. It cannot say that about an `A_seq` that depends on depth, because the two cells
differ in depth by 2× — if the per-sequence cost is really an interaction between `c` and `depth`, then
`Δt = 8·A(8,4096) − 4·A(4,8192)` and the pair measures nothing interpretable. That caveat is not
hypothetical: **§12.30's own evidence for rejecting the additive form was that `M` flips sign across
cells, which is exactly what an interaction looks like.** So the honest reading is narrower than the
headline: **the literal additive term `A_seq·c` with a single coefficient does not survive a designed
test**, and every attempt to fit these cells with additive physics has now either flipped sign
(§12.30) or come out null in the wrong direction (here). That is three independent indications that
**the additive form is wrong**, which is more useful than any single coefficient from it.

**A second finding, and it changes how §12.29 should be quoted.** The two throughput metrics in the
same JSON, same boot, same cells, same `n = 5`, **disagree about the sign** of the per-stream
comparison:

| metric | A (c=4) | B (c=8) | agg ratio | per-stream ratio | reading |
|---|---|---|---|---|---|
| `tg_throughput` (mean) | 60.71 | 125.27 | 2.063 | **1.032** | B per-stream **faster** by 3.2 % |
| `peak_throughput` | 85.20 | 159.00 | 1.866 | **0.933** | B per-stream **slower** by 6.7 % |

§12.29's "17–25 % gap at equal `c·depth`" is a **peak** statement; every throughput number I have
quoted since is a **mean**. At an effect size of 3–7 % the two metrics bracket zero and disagree in
sign, so **"per-stream throughput falls with batch at fixed `c·depth`" is not a finding this dataset
supports in either direction**, and the sign depends on a choice nobody documented as a decision.
Quote the metric with the number, and prefer the mean unless there is a stated reason not to.
Per-run values (`tg`): A = [57.8, 55.1, 64.3, 65.9, 60.4] cv 6.6 %; B = [124.0, 134.0, 126.4, 128.1,
113.9] cv 5.3 %. Order was A then B, once — no interleaving — so a within-boot level drift of a few
percent is not removed, which is the same limit that has capped every ratio in this file.

**Controls, all read rather than assumed.** Config fingerprint of the live container matched the
shipped recipe (`capped to 21`, `#tokens 118,155`, `speculative_num_draft_tokens: 8`,
`mamba_ssm_dtype: bfloat16`), so this is the shipping configuration on a `--skip-run` boot. Per-cell
`prompt_size` in the JSON is **2048 and 1024** — the `schedule:` override applied, which is the check
§12.34's unresolved hazard demands and the reason it is in the driver rather than in a comment.
Observed `#running-req` histogram over 63 decode lines: `{1:6, 2:4, 4:23, 5:6, 6:3, 7:6, 8:15}` — both
cells reached their full offered batch, so neither was capacity-limited and the aggregate ratio is a
fair comparison. Acceptance was matched between cells (3.200 vs 3.180), so the aggregate ratio is not
an acceptance artefact. `runs: 5` per cell; `--fresh` used; md5 duplicate guard passed.

**Artifacts.** Profile `attic/benchmarking/pool-matched-pair.yaml` (predictions committed there before the
run). Driver `.scratch/qwen3-27b/run_phase78.sh`, data `.scratch/phases/p78-poolmatch/`, zero boots.
**One instrument bug found and fixed while running it:** the driver's serve-log fetch returned **202
lines when the recorded marker said 740**, and printed that without comment. A serve log is
append-only, so a smaller count is impossible; it was a truncated read, and the copy contained exactly
**one** decode line — 1.6 % of the data. Had I analysed `#running-req` from that file I would have
reported per-cell batch admission from a single line and it would have looked like a small sample
rather than a broken fetch. The marker existed for exactly this check and was only ever *printed*.
Now asserted, with retry (`fetch_log`). **Recording an invariant is not enforcing it.**

### 12.53 p77: the 60 % decode-share gate did its job, the wall-time result is admissible, and the decomposition that "rescued" it is confounded by the mechanism under test

**Run.** Four boots on `node-free-1`, ABBA (`a_ship b_r12 c_r12 d_ship`), `--fresh`, md5 duplicate guard
passed, `OFFER = 12`, `depth = 16384`, `newrun = 768`, distinct per-request prompts so the radix cache
could not silently share KV. Driver `.scratch/qwen3-27b/run_phase77.sh`, data `.scratch/phases/p77-decodedom/`.

**The gate fired, and firing is the rule working.** `analyze_phase77.py`'s pre-registered rule refuses
any ratio unless decode exceeds 60 % of wall; measured decode share was **14–35 %, mean 21 %**. So
**no aggregate decode-throughput ratio may be quoted from this run**, and it must not be compared with
phase 26's 1.558×, which came from a decode-dominated harness cell. This is p76's failure mode caught
by arithmetic before analysis rather than after publication.

**What IS admissible, and why it is a different metric from the one the gate protects.** End-to-end
**wall time for identical total work**:

| arm | wall/rep (all reps) | trimmed | admitted streams | queue depth |
|---|---|---|---|---|
| ship (r = 3.51) | 133.3, 123.6 (2 reps/boot × 2 boots) | **123.7 s** | **7** | **5** |
| r12 (r = 1.2) | 110.6, 110.2 | **109.8 s** | **12** | **0** |

Ratio **1.126** trimmed, 1.164 untrimmed. Premise asserted rather than assumed: prefill token totals
are equal across arms to **0.001 %** (374,513–374,515) and completions are identical (9,216), so equal
work is measured, not stipulated. The ordering does not depend on the warm-up outlier in `a_ship`
(ship's *best* rep, 123.5 s, still exceeds r12's *worst*, 110.4 s). The mechanism is read from the
server rather than inferred from the gap: `#running-req` histograms `{1:5, 5:5, 7:6}` with
`#queue-req` max **5** for ship, versus `{1:1, 4:1, 12:5}` with queue **0** for r12.

**Verdict this run supports, stated at its true scope.** At 16k contexts with 12 streams offered, on
one node, ABBA, with total work equal by measurement: lowering `mamba_full_memory_ratio` to 1.2
completes the batch **~13 % faster end-to-end**, and the visible mechanism is 12 admitted streams
against 7. **Not** a decode-throughput claim, **not** cross-node, and — see below — **not** attributable
to decode rather than prefill.

**The trap I walked into while writing the rescue.** The obvious next step was to split wall time into
prefill and decode so the mechanism could be localised. `analyze_phase77.py` had already done a version
of this wrong: it computed `decode_wall = wall − Σprompt/PREFILL_TPS` with `PREFILL_TPS` **assumed at
2,000**, then fed that residual into the 60 % admissibility gate — an assumed constant deciding a
verdict. (Checked: measured prefill rate is **2,067–2,091 t/s** from burst-active time, so the
assumption happened to be nearly right; the flag "check it against the serve log" was in its own output
and nobody had checked.) My replacement measured prefill directly by splitting Prefill batch lines into
bursts. It looked rigorous and produced **ship 106.8 s vs r12 68.5 s of decode**. Then I swept the two
arbitrary conventions in that measurement:

| burst-gap threshold | tail credit | ship decode s | r12 decode s | ratio |
|---|---|---|---|---|
| 5 s | 0 / 0.5 / 1 | 168.8 / 159.8 / 150.8 | 88.5 / 83.5 / 78.5 | **1.91–1.92** |
| 10 s | 0 / 0.5 / 1 | 156.8 / 148.8 / 140.8 | 76.5 / 72.5 / 68.5 | **2.05** |
| 20 s | 0 / 0.5 / 1 | 118.8 / 112.8 / 106.8 | 76.5 / 72.5 / 68.5 | **1.55–1.56** |
| 30 s | 0 / 0.5 / 1 | 76.8 / 72.8 / 68.8 | 76.5 / 72.5 / 68.5 | **1.00** |

**The decode ratio runs from 1.00 to 2.05 across choices of a heuristic, and the sign of the PREFILL
difference flips with it** (ship prefills 19 % *slower* at gap 30 s, 2 % *faster* at gap 5 s — on
identical token counts, which cannot both be true). So "the wall advantage is a decode advantage"
**is not supportable**, and neither is its opposite. `.scratch/qwen3-27b/p77_decompose.py` prints the
whole range rather than one row; it exists as the artifact that stopped a clean-looking table.

**Why it is confounded, which is the transferable part.** Ship's log contains **5 prefill bursts** and
r12's contains **3** — the same 374k tokens. The arms differ in *how the scheduler interleaves prefill
with decode*, which is precisely the mechanism under test, and burst-gap heuristics partition time by
that very interleaving. **Any attribution method whose partition depends on scheduling structure
cannot arbitrate between two schedulers.** The general rule: *before using a heuristic to attribute
time to a component, check whether the quantity being tested changes the heuristic's input.* Here it
did, and only the sensitivity sweep revealed it — the single-convention output was confident and wrong
in a way no error message would have produced.

**Also caught by the sweep: decode time here is a residual of a ~100 s number.** The arm difference is
~14 s out of ~124 s, so a 10 % convention error in the prefill term *is* the whole effect. Small
differences between large measured quantities inherit the larger quantity's error budget; that is why
the gate demands decode to *dominate* wall before quoting ratios, and it is why the wall result above —
measured directly from request timestamps, never differenced — is the admissible one.

**Status of the open question.** Throughput at 16k remains **unreplicated**. To settle it, decode must
exceed 60 % of wall: with prefill measured at ~2,070 t/s, `newrun` must be **≥ ~2,500 tokens**, not
768. Same ABBA frame, same node, ~4 boots. The wall-time result stands in the meantime and is the
strongest service-time statement available for the ratio question.

### 12.54 The `usable` capacity bound has been wrong by the `pp` term since it was introduced — verified 14/14 and 0/14, and the "confirmation" was a phase error

**The claim being corrected.** Every `usable` table in this project (WORK.md §12.9, §12.15,
§12.24, and the roadmap row "what should `mamba_full_memory_ratio` be?") evaluates

    usable = min(cap, #tokens // L)   with   L = depth

and that `L` is wrong. §12.44–§12.45 of this file established that `llama-benchy` runs **two
phases per cell against a prompt of length `depth`**: a prefill phase generating `pp` tokens,
then a decode phase generating `tg`. A request's resident token count is therefore
`depth + (generated so far)`, reaching `depth + pp + tg` by the end of the cell. **At the 16k
operating point that is 18,432–18,688 tokens per request, not 16,384** — the bound was
understating per-request cost by the entire `pp` term, 11 % at 16k and **25 % at 8k**. The
8k error is the larger one and it is the one in the roadmap table.

**Why the wrong value looked *measured*, which is the part worth keeping.** The bound with
`L = depth` appeared to be confirmed by data: peak `#running-req` equalled `#tokens // depth`
on every 16k boot. It was not. **sglang labels a batch by what the batch is doing, not by the
harness phase**, so during llama-benchy's *prefill* phase the server emits `Decode batch` lines
freely — and at that moment each request holds only ~`depth` tokens, because `pp` has not been
generated yet. The population that matched `#tokens // depth` is the **prefill-phase**
population, and it matches because `L = depth` is the correct bound *for that population*. The
decode-phase population, which is the one the capacity claim is about, never matches it.

**The test, run on archived artifacts before writing a word of this.** Classify each
`Decode batch` line by resident tokens per request (`#full token / #running-req`), which
detects the phase without the harness: a decode-phase line **cannot** be below `depth + pp`,
because the prefill phase has already generated `pp` tokens for that sequence. Then compare
each arm's decode-phase peak against both candidate bounds. `correct_capacity.py` over the
16k arms (depth 16384, pp 2048, tg 256, `pool // 18432 = 6` for ship and `// 18432 = 12` for
r12):

| artifact | pool | cap | `//depth` | `//(depth+pp)` | peak all | peak prefill-phase | **peak decode-phase** |
|---|---|---|---|---|---|---|---|
| p26 node-free-1 ship | 117,943 | 21 | 7 | **6** | 7 | 7 | **6** |
| p26 node-free-2 ship | 119,365 | 21 | 7 | **6** | 7 | 7 | **6** |
| p27 node-free-1 ship | 118,868 | 21 | 7 | **6** | 7 | 7 | **6** |
| p82 node-free-1 ship ×2 | 117.4–118.4k | 21 | 7 | **6** | 7 | 7 | **6** |
| p26 node-free-1 r12 | 238,712 | 14 | 14 | **12** | 12 | 12 | **12** |
| p82 node-free-2 r12 ×2 | 239.2–239.5k | 14 | 14 | **12** | 12 | 12 | **12** |
| p27 node-free-2 r12 | 239,346 | 14 | 14 | **12** | 13 | 13 | **12** |
| p82 node-free-1 r12 ×2 | 238.4–239.1k | 14 | 14 | **12** | 12 | 12 | **12** |
| p82 node-free-2 ship ×2 | 118.3–118.8k | 21 | 7 | **6** | 7 | 7 | **6** |

    14 arms. decode-phase peak == #tokens//(depth+pp) in 14/14; == #tokens//depth in 0/14.

A clean 14–0, on three independent phases (p26, p27, p82) and both nodes. Phase 82 was run
deliberately as a pre-registered confirmation **after** the correction was written, with the arms
counterbalanced across the two nodes (`node-free-1`: ship, r12, r12, ship; `node-free-2`: r12, ship, ship, r12) so
that neither the arm effect nor the node effect can be read off a single machine. It reproduced.

**One caution about this table, found while assembling it.** The p26 and p27 artifacts do **not**
match the `*serve*.log` glob that phase 82 writes; they are named `*_full.log` / `.memlog`. A glob
built from the newest phase silently returned **nothing** for the older phases, and if I had run the
command that way and trusted the summary line, the table above would have been "8/8" with a header
claiming three phases. Verified separately that p26/p27 really do pass 6/6 before writing 14/14.
**The rule this adds to the §7 list: when a verification command reports a count, confirm the count
is the number of inputs you believe you passed it** — a glob that matches nothing is not an error, it
is a silent zero, and "6/6" printed under a heading that says "12 arms" is exactly how a
under-powered check reads like a passed one. Re-run at the 8k
operating point (depth 8192, pp 2048, tg 256 → `L = 10,240`) across 109 archived arms:
**36/109 match `//(depth+pp)`, 0/109 match `//depth`** — the 36 are the arms that actually ran
at depth 8192 with enough decode-phase lines; the other 73 are other depths whose lines cannot
match either bound and are counted as failures by the same test, which is why the pass rate is
not 100 %. The 0/109 is the load-bearing half: **not one decode-phase population in the archive
matched the bound in use.**

**Corrected numbers, and what does *not* change.**

| quantity | as shipped in the docs | corrected | does the conclusion move? |
|---|---|---|---|
| usable 16k, ship (3.51) | 7 | **6** | — |
| usable 16k, r12 (1.2) | 14 | **12** | ratio still **2.00×**, so the ratio conclusion stands |
| usable 8k, ship | 14 | **11** | — |
| usable 8k, r23 (2.3) | 18 | **15** | forfeiture **22 % → 27 %** |
| roadmap "forfeits 22 % of 8k concurrency" | 14 vs 18 | **11 vs 15** | direction survives, magnitude moves 5 pp |

The ratio ranking is intact because `pp` is identical in both arms and largely cancels — which
is exactly why a systematic `L` error can survive a decade of A/B tests: **it is invisible to
comparisons and only visible to absolutes.** Anyone who quoted a *count* of concurrent contexts
rather than a *ratio* quoted a number inflated by 11–25 %.

**The scope caveat, because "6" is not a workload-independent truth either.** `usable` is a
property of the *resident length per request*, and in these cells that length is
`depth + pp + tg/2` on average, not `depth`. For the benchmark's shape the answer is 6 and 12.
For a hypothetical serving workload of exactly-16k prompts with negligible generation, `L ≈
16384` and 7 is right — the number is not wrong in the abstract, it was attached to the wrong
`L` and then labelled "usable@16k" as though it were a property of the recipe. **Any capacity
figure must carry its `L`, the same rule §12.2bis enforces for `T`.** The tables should read
`usable @ L=18,432`, not `usable@16k`.

**Reusable rules.**
1. **When a bound is "confirmed" by a measured peak, check the phase of the population that
   produced the peak.** A confirmation that holds only for a sub-population is not a
   confirmation of the claim; it is a coincidence with a mechanism. This is the second time
   this exact shape has bitten here — §12.29's "equal bytes" pair was the same error wearing a
   regressor instead of a phase.
2. **Prefer a classifier that works from the data over one that trusts a label.** Here the
   line's own `Decode`/`Prefill` prefix is *uninformative about the harness phase*, while
   `resident/req` is decisive. The field that looks like the phase indicator is describing the
   batch, and the field nobody thought to look at is the one that separates the populations.
3. **A constant offset shared by both arms of an A/B is invisible to that A/B.** If a quantity
   feeds only comparisons, an error in it is undetectable by the comparisons themselves.
   Auditing absolutes is a different activity from auditing contrasts, and this project had
   been doing only the latter.

**Open, and it needs one boot per arm.** `pp` is a harness knob, so the corrected `L` describes
the benchmark rather than any real deployment. Whether the *shipped* ratio choice would change
under a workload whose resident length sits between `depth` and `depth + pp` — e.g. long prompt,
short generation, which is the common serving shape — has not been measured, and the answer
moves the optimum: at `L = 16,384` the modelled 8k optimum is r ≈ 3.6, at `L = 10,240` it is
r ≈ 2.3. That is the §6 item-B traffic-shape question, now with a quantified sensitivity and
still blocked on knowing the workload, not on data.

**Throughput re-measured under the corrected `L` (phase 82, 8 boots, 4 runs per cell).** The
capacity ratio was already known to survive the correction because it is a contrast. The
throughput claim needed its own measurement because it is quoted as an absolute-ish ratio, and
because §12.15's original 1.558× predated the `L` fix:

| node | c = 12, ship | c = 12, r12 | **ratio** | TTFT ship | TTFT r12 | TTFT ratio |
|---|---|---|---|---|---|---|
| `node-free-1` | 26.53 | 41.85 | **1.578** | 54.6 s | 29.6 s | **0.542** |
| `node-free-2` | 27.27 | 45.49 | **1.668** | 50.8 s | 26.9 s | **0.529** |

Reproduces §12.15's 1.558× and 0.58× on two nodes and four boots, so the throughput conclusion is
independent of the `L` error — which is what "it is a contrast" is supposed to mean, now actually
demonstrated rather than asserted.

**The c = 1 null on `node-free-2` read 1.175, which fails the precondition this phase set for itself.**
That is worth keeping as an example of a check that works and then must not be over-read. c = 1 is
where capacity cannot possibly matter, so a 17.5 % gap there threatens to make the c = 12 ratio
unattributable to the ratio knob. Resolved by pooling **every** 16k c = 1 decode row in the archive,
8 boots per arm: ship 28.43 t/s (range 26.7–29.7), r12 29.06 (26.6–34.5). Difference **+2.2 %,
Welch p = 0.53, permutation p = 0.59**, and r12 holds both the minimum and the maximum of the pooled
distribution. So the `node-free-2` reading is boot noise, and — importantly — **the sign is not stable
across phases** (§12.15 measured r12 *slower* at c = 1, phase 82 measures it *faster*), which is
itself the evidence that no real c = 1 arm effect exists. **A null that fails once, in a regime where
the effect cannot act, and whose sign flips between replications, is noise; a null that fails
consistently is a confound. Distinguishing those needs the pooled archive, not the single run.**

### 12.55 The prefill **admission queue** rises with prompt length while the pool stays half-empty — the first depth cost in this project that is not in the decode path

**This is the test §12.29 asked for and did not have.** §12.29 closed with *"What distinguishes
d8192 — UNVERIFIED, two candidates each"*, and its first candidate was exactly this:
`chunked_prefill_size = 4096` with `max_prefill_tokens = 16,384`, so a d8192 prompt is 2.5 chunks
where d4096 is 1.5, meaning *"a prefill-admission term jumps at exactly that transition"* — and it
recorded that **the grid could not test it**, because no arm held prompt length fixed while varying
chunk count. §12.27, §12.29 and §12.32 all searched *inside decode* (per-byte KV read, pool
residency) and found nothing detectable (§12.32: 0.58 σ, CI on zero). The queue is the observable
that admission leaves behind, and it was never collected until now.

**Source of the mechanism:** `GET /get_server_info` on the live server — the resolved `ServerArgs`,
**zero boots** — giving `max_prefill_tokens = 16384`, `chunked_prefill_size = 4096`,
`prefill_max_requests = None`, `schedule_policy = fcfs`, `retraction_policy = length`. So at most
**~4 requests prefill simultaneously**, independent of prompt length, while each holds its slot for
~(depth+pp)/4096 chunked batches. Above ~4 offered streams that is a 4-wide resource whose
per-request occupancy grows linearly with prompt length.

**Measured on archived artifacts, zero boots** (`.scratch/phases/p54-ppcross`, `admission_queue.py`;
`n` = Prefill lines in that cell's window):

| ctx | c | n | queue med | queue p90 | q max | frac q>0 | usage med | usage max |
|---|---|---|---|---|---|---|---|---|
| 4096 | 2 | 48 | 0.0 | 0 | 0 | 0.00 | 0.07 | 0.10 |
| 4096 | 4 | 53 | 0.0 | 2 | 2 | 0.28 | 0.14 | 0.21 |
| 4096 | 8 | 86 | **1.0** | 5 | 6 | 0.55 | 0.24 | 0.42 |
| 8192 | 2 | 53 | 0.0 | 1 | 1 | 0.11 | 0.14 | 0.17 |
| 8192 | 4 | 90 | 0.0 | 2 | 3 | 0.44 | 0.24 | 0.35 |
| 8192 | 8 | 148 | **2.0** | 6 | 7 | 0.68 | 0.38 | **0.69** |

Mann-Whitney, deeper vs shallower at the same `c`: **c=8 p = 0.020** (means 1.84 vs 2.55), **c=4
p = 0.036** (0.43 vs 0.79), **c=2 p = 0.017** (0.00 vs 0.11).

**The discriminator, and the reason the result is worth anything.** Pool pressure and admission
pressure both predict a rising queue; they predict *opposite* things about `full token usage`. Usage
peaks at **0.69** where queueing is worst, so nothing pool-side explains a queue there. §12.15's
capacity mechanism and this are separable, and here they are separated.

**The distinction this establishes, and it is checkable in the code.** §12.29's per-cell gate
(`cell_gate.py`) reported *"`max running` == offered `c` in all twelve cells — nothing was
queue-limited"*. Inspecting it: the gate parses **only** `Decode batch` lines and its single rule is
`#running-req <= offered c`; **it never reads `#queue-req` at all.** So "nothing was queue-limited"
was an inference from a field that cannot express queueing. It is a valid statement about the
*admitted set* and an invalid one about *delay*: a request can sit in `#queue-req` for a while and
then run, leaving `#running-req` indistinguishable from a cell that never queued. **p54 demonstrates
the two coming apart in one dataset** — at `c = 8` the running histogram reaches the offered 8 (mode
20/22 lines at 8) while Prefill `#queue-req` is nonzero on **68 %** of lines. Admitted-set size and
waiting-set size are two measurements, and every gate in this project has used only the first. Same
shape as §12.15's *granted 21 / running 6*, read from the opposite side.

**Not a drift artefact — checked, because this project has been burned twice by exactly that.**
Window execution order is 4096/2, 4096/4, 4096/8, 8192/2, 8192/4, 8192/8 and the queue medians are
**0, 0, 1, 0, 0, 2**: windows 4 and 5 come *after* window 3 and fall back to 0, so the
concurrency-dependence is not time-in-container. **The residual confound is stated rather than
buried:** at a fixed `c` the deeper cell necessarily runs *later*, so the c=8 depth contrast (window 3
→ 6) cannot exclude a late-run drift, and **p = 0.020 on a confounded contrast is not a settled
number.** The unconfounded part is the c-dependence (0 → 0 → 1 at c = 2/4/8). Randomised order is
required before the depth half is quoted.

**Three near-misses producing this, each of which would have published a false null.** All three were
caught by controls, not by reading the output carefully, which is the point:

1. **`#queue-req` is printed on both line types, and reading it off the wrong one silently returns
   zero.** Parsing it from `Decode batch` lines gave **max 0, 0 % nonzero on all 881 lines** — an
   impeccable-looking null. The same file's `Prefill batch` lines carry queue up to **14** on **46 %**
   of lines. Caught only because a deliberately dumb control — a bare `re.findall(r"#queue-req: (\d+)")`
   over the whole file, which cannot be wrong about *presence* — disagreed with the parser (14 vs 0).
   **A parser that returns nothing must be contradicted by a regex that cannot miss before the null is
   believed.**
2. **A steady-state filter deletes the signal it is meant to measure.** Carrying over the
   `#running-req ≥ 0.75·c` floor that decode analyses require cut 2,458 Prefill lines to 166 and
   re-created "no queueing observed", because the lines carrying a queue are exactly those where the
   running set has not yet filled. A steady filter is a decode concept; on an admission metric it is a
   category error.
3. **`usage_max.get(ctx, 0.0)` printed `pool usage max 0.00` beside a table column reading 0.69.** The
   dict is keyed by `(ctx, c)`. A defaulted `.get()` on a wrong key is invisible; `usage_max[(ctx, c)]`
   makes a missing entry raise. Same class as the `ttft_ms` schema guess earlier the same day — **the
   failure mode of this project's analysis code is not arithmetic, it is a lookup quietly returning a
   default.**

**Limits.** One boot, one container, `pp` pooled inside each cell's window (balanced — both `pp`
values appear in every cell, so the pooling does not bias the ctx contrast). `#queue-req` counts
waiting *requests*, not waiting *tokens*, so it cannot distinguish one long prompt holding a slot from
many short ones: the direction is real, the magnitude is not a throughput conversion. And it is a
*scheduling* cost — it moves TTFT, and it is neither the decode slowdown of §12.29 nor the acceptance
drop of §12.33. What it does is give the depth penalty a **third component outside the decode path**,
and name a *resource* (a 4-wide admission gate) rather than a mechanism.

**Next step, and it is cheap.** §12.29's own proposal is now the right experiment and it is still
zero-boot: same container, `depth` ∈ {4096, 6144, 8192} with `pp` compensating to hold `depth + pp`
constant — that separates "context length drives KV/attention" from "prompt length drives prefill
chunking", which is the fork these candidates sit on, and the queue is now a measurable outcome on
both sides of it. Add randomised order to kill the drift confound above. **Also worth a run: `c = 16`, but only with `mamba_full_memory_ratio` lowered.** This one has
to be specified carefully or it is void by construction, and the reason is the capacity trap this
file has recorded repeatedly: at the **shipped** ratio 3.51 the pool is ~118k tokens, so `c = 16` at
depth 8192 demands 16 × 10,240 = **164k tokens — more than the pool holds**. That cell would be
pool-capped at 11 running, its `#queue-req` would be explained by the pool rather than by admission,
and the discriminator (usage must stay low) would be violated by design. **At ratio 1.2 the same cell
is 16 × 10,240 / 239k = 0.69 usage — low, and admissible.** So the arm is `c = 16` **at r12**, not
`c = 16` period. If the queue keeps growing there, admission is first-order for long-context serving
and `max_prefill_tokens` graduates from an incidental default to a tunable worth a phase.
