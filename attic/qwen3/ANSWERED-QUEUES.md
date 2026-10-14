# Answered queues — what has already been paid for, with the answer

Split out of `QWEN3-MODEL-OPTIMIZATION-WORK.md` §6 on 2026-09-21. **This file exists so that
"Open, in priority order" in the main document means exactly what it says.** Before the split §6 was
5,619 words and **61 % of it was closed items** — a queue section that was majority not-a-queue. The
reason it accumulated is defensible: every answer is load-bearing evidence, and deleting one invites
someone to re-run it. So nothing here is deleted; it is relocated, and the live queue keeps the
deferred items (digest pinning, `cluster_only`, the README column) because deferred is not answered.

**The failure this file is built to prevent is documented in the main doc and recurred twice:** an
experiment was re-run — once at **8 boots' cost** — because the closed record named the driver and the
analyzer but **not the profile**, and searching the doc by profile name was therefore impossible.
**Before queueing anything, search this file for the profile name, not just the question.**

## Reading order

1. `QWEN3-MODEL-OPTIMIZATION-WORK.md` §6.1 for what to do next.
2. Here for whether it has already been done, and what the answer was.
3. The cited section for the derivation. This file carries verdicts, not proofs — a verdict
   without its section reference is not usable, so every entry names one.

## Closed items relocated from §6

**Closed by phase 9 (do not re-run these expecting a different answer):**

0. ~~Grep the logs that already exist.~~ **Cost six boots instead.** No server log survived on
   `node-restricted-2`/`node-restricted-3` (14 `/tmp/*.log` files inspected, zero hits), because `/tmp/sparkrun_serve.log` lives
   *inside* the container and dies with it. `run_phase9.sh`'s `grab_mem` step exists for this reason.
   The standing advice "just grep the old logs, it is free" is retracted — see §7.
1. ~~Is `max_num_seqs: 48` real?~~ **No. Granted 21** at `D = 8` (`capped to 21`, `K` = 85–86) on
   22 of 23 archived boots; the one 20/82 is phase 9's first boot at `T` = 24.31, i.e. below the
   `cap`-step boundary at `T` = 24.50 — a `T` effect, **not** container age (§12.21 retracts the age
   attribution this item previously carried). 32 at `D = 4`; unbound 48 on the no-spec control
   (§12.8). The ceiling is **26 at any ratio** — §12.3's "~31" was wrong, its direction was right, and
   §9's `48` label is wrong.
2. ~~Does `--mamba-ssm-dtype bfloat16` reach the pool?~~ **Yes.** `K` 82 → 42 (÷1.95) and
   `conv_state` 0.23 → 0.12 GB (÷1.92) while `ssm_state` barely moves (§12.8; on fresh boots
   21 → 10 slots, `K` 85 → 42). That promotes the
   accuracy question in item C from hypothetical to live: the flag demonstrably overrides the value
   the checkpoint declares.
3. ~~What does `3.51` buy?~~ **It is a trade, and the answer depends on context depth.** At depth 0
   it buys slots (12 → 20 going 0.9 → 3.51) and costs 2.3× of the token pool. At depth 8192 the
   **token pool is the binding limit** (14 requests, usage 0.99) and the slots are slack — so the same
   knob may be spending the resource that actually matters. See item A. §11's guess is reversed on
   both halves at depth 0 and needs re-testing at depth.
 4. ~~Re-confirm block 4 → 8 with an interleaved design.~~ **DONE (phase 11, 2026-09-20) — the
    change is confirmed, and it is smaller than shipped.** Driver `.scratch/qwen3-27b/run_phase11.sh`,
    profile `benchmarking/confirm-blocksize.yaml` (depth 0, pp 2048, tg 128, c = 1, runs 7 — name
    the profile here because searching the doc by profile name is how someone checks whether this
    was already run, and it used to be absent, which is how this very experiment got run twice),
    analysis `analyze_phase11.py` with the decision bands committed **before** the data, artifacts
    `.scratch/qwen3-27b/p11-0920/`. Eight boots: `b4 b8 b4 b8` on `node-free-1` mirrored on `node-free-2`, `--fresh`
    per boot. Every boot passed a validity gate that checks the **draft-token count the server
    logged** (not the one the driver requested) plus grant and `#tokens` bands, so a silently-dropped
    `-o` cannot masquerade as a replicate.

   | | value |
   |---|---|
   | PRIMARY — within-node paired, median of 6 adjacent pairs | **1.213** |
   | SECONDARY — pooled, ignoring node | 1.221, boot-level 95 % CI **[1.156, 1.279]** |
   | per-pair spread | 1.085–1.293; `node-free-1` pairs 1.293/1.235/1.255, `node-free-2` pairs 1.085/1.148/1.191 |
   | pre-registered verdict | **CONFIRMS** (band [1.15, 1.45]); refutation band [0.90, 1.10] not hit |

    So we did **not** ship a regression as a win — that was the live risk, and the pre-registered
    refutation band is what made it checkable rather than a matter of opinion. But every pair sits
    below the claimed 1.290 and the CI's upper bound is under it, so **the honest figure is +21 %,
    not +29 %**. This is §3's rule paying off again: separate-phase arms overstate, and here they
    overstated the shipped headline by a third of the effect size. Note also that the pairing was
    load-bearing — the two nodes differ by ~10 % on the same comparison, so a pooled design on this
    recipe would have been dominated by which node ran which arm.

    **Replicated independently (phase 25 at 18:39, again 09-21 at 01:29) — quote +22.5 % now.**
    Phase 25 was *meant* to be a first confirmation and turned out to be a duplicate: the DONE
    record above named the driver and the analyzer but not the **profile**, so searching this
    document by profile name found nothing and the experiment got re-run. That is a documentation
    bug, now fixed (the profile is named above for exactly that reason), and the honest summary is
     that 8 boots were spent re-measuring something already answered. They were not wasted: a third
     replication 7 h after phase 25, on a different orchestrator host, and its ratio is the closest
     of the three to the phase-11 value — which is what makes the pooled number worth quoting.
     All **24 boots** pooled, same estimator:

    | phase | boots | ratio-of-means |
    |---|---|---|
    | p11 (09-20 02:25) | 8 | 1.2208 |
    | p25 (09-20 18:39) | 8 | 1.2349 |
    | p25 replication (09-21 01:29) | 8 | 1.2198 |
    | **pooled ratio-of-means, boot-level CI** | **24** | **1.225 [1.188, 1.262]** |
    | pooled ratio-of-medians (robustness) | 24 | 1.249 |
    | within-node adjacent pairs | 18 | median 1.231, range [1.085, 1.350], cv 5.4 % |

    **The replication check now passes with margin: the three phases span 1.2 %** (1.2208 /
    1.2349 / 1.2198), far inside the 5.4 % *within*-phase pair spread, so pooling is legitimate and
    one number is fair. **Quote +22.5 %.** The CI excludes both 1.0 and, more usefully, the old
    1.303 headline. Phase 11 alone supported +21 %, phase 25 +23 %; the difference between those two
    was replication noise, which is the clearest possible argument for why a single phase of 8 boots
    cannot settle this knob.
    Verified before pooling that the three phases are comparable: all 24 benchlogs record the same
    profile (`confirm-blocksize.yaml`), `depth 0`, `pp 2048`, `tg 128`, `c 1`, `runs 7`,
    `prefix_caching True`, and the same two server command lines differing only in
    `--speculative-num-draft-tokens 4` vs `8`. That check matters because the profile's own text
    warns that prompt/generation length moves reported throughput by ~47 % on this model, so pooling
    across a silent shape change would have manufactured a number.

    **Mechanism, from phase 25's server logs (new; phase 11 reported only throughput).** Across the
    8 boots, `accept len` is **2.795** at `D = 4` (n=41 rows) and **3.581** at `D = 8` (n=32) — a
    ratio of **1.281**, against the measured throughput ratio 1.235. So acceptance more than
    accounts for the gain, and the shortfall is exactly what §2 predicts: `t_verify/t_decode`
    rises only 1.43 → 1.48 from block 4 to 12 (§2, paired measurement), so a bigger block stays nearly free per step and a
    little of the acceptance gain is absorbed rather than converted. The identity from §10.1 also
    holds here despite every row being `#running-req = 1` — `1 + (D−1)p` gives 2.793 vs 2.795
    measured (0.1 %) — because these are means over 32–41 rows, and it is the *single-line* ratio
    that is noisy (sd 1.39), not the mean. **The +22.5 % is an acceptance effect, not a pool or
    scheduling effect**, which is the reassuring answer: nothing about the shipped change is
    exploiting an artifact of this benchmark window.

   **Why the estimate moved and the old CI did not.** The 20-control-boot CI [1.197, 1.408] was
   honest for its design (controls and arms in different phases, so it captured control-to-control
   spread but not phase drift). The paired design removes phase drift by construction, and what
   remains after removal is smaller. Both statements are defensible; the paired one is the one to
   quote, because the confound it removes is the one §3 already documented on this recipe.
5. ~~Decode throughput at c = 1…40.~~ **Ran, and it changed conclusions.** Aggregate saturates
   ~145 tok/s by c ≈ 30; the server never exceeds 20 running at depth 0 (the cap) or 14 at depth 8192
   (the pool). §12.8. Note the harness's `max_concurrency` does **not** clamp the server — read
   `#running-req` from the log, never the profile's field.

---

## §6.2 item detail, relocated 2026-09-21

Moved **verbatim** from `QWEN3-MODEL-OPTIMIZATION-WORK.md` §6.2. The live queue there is now
§6.1 plus item B only — the one item that is genuinely open, and open because it is blocked
on a product decision rather than on a measurement. Nothing here is summarised or trimmed:
the wrong predictions are the payload, and shortening them is what lets an experiment get
queued a third time.


Status is **per item**; the markers inside each entry and the list in §6.1 are authoritative, and
several entries below are DONE. They are kept in full — including the wrong predictions and the
reasons they were wrong — because that is what stops the same experiment being queued a third time.
If §6.1 does not list an item, it is answered.

A. **Measure the ratio knob *at depth 8192*. DONE — measured (phase 9, §12.9) and replicated
   same-node (phase 10, §12.10). Result: ratio 2.3 raises usable 8k concurrency 14 → 18; the default
   is deliberately NOT changed, for the reason in item B.** Every ratio measurement taken before this
   was at depth 0, where the **slot cap** binds; at depth 8192 the **token pool** binds
   (measured: `#running-req` tops out at 14 with pool usage 0.99, and `117,571 / 8,192 = 14.4`). The
   two regimes want opposite settings, so 3.51 cannot be judged from depth-0 data.

   **The mistake this item contained, and why it matters more than the answer.** An earlier revision
   queued the `R09` arm (`ratio = 0.9`) on the reasoning "at depth the pool binds, so buy tokens".
   That is wrong, and wrong in a way that is easy to fall into when you have a `#tokens` column
   staring at you: **usable concurrency is `min(slot cap, #tokens // L)`, not `#tokens // L`.** Cutting
   the ratio buys tokens *by spending slots*, and at `D = 8` the slot cap is `K // 4` — it falls fast.
   Sweeping `r` through the same model that produced the wall (`predict_capacity.py`, `T = 24.31`):

   The full sweep is the `usable = min(cap, #tokens/L)` table in §12.8; the three rows that
   matter here are `r = 0.9` → **12** usable at 8k (slots bind), `r = 2.3` → **18** (balanced),
   and the shipped `r = 3.51` → **14** (token pool binds, ~7 slots idle).

   **So `r = 0.9` — the arm I had queued — gives 12 usable at 8k, *worse* than the shipped 14.**
    That 12 is not merely modelled: `R09` was booted in phase 9 and granted exactly 12 slots with
    274,628 tokens (the model said 12 and 263,382). What was unmeasured was the *depth*, not the
    grant — a distinction worth keeping, because it is why the error survived a real boot.
   The optimum is an interior point, **r ≈ 2.3**, worth **18 vs 14 concurrent 8k contexts**,
   and it is a genuine optimum rather than a monotone trend because the two limits cross there: below
   it the slots bind, above it the pool binds. Note the shape of the whole table — **each context
   length has its own optimum, so there is no single best ratio and "what should 3.51 be" is
   unanswerable without item B.

   **The per-context-length trade-off is now MEASURED, not modelled** — computed from the eight
   phase-10 boots' own `capped to` / `#tokens` lines (`cap` 21 / 118,721 tokens at 3.51; 19 /
   154,649 at 2.3; every boot of an arm agreeing within 1.2 %), so it needed no boot:

   | context | usable @3.51 | usable @2.3 | winner | what that means |
   |---|---|---|---|---|
   | 2048 | **21** (slots) | 19 (slots) | **3.51, +2** | both above any c worth testing — see caveat |
   | 4096 | **21** (slots) | 19 (slots) | **3.51, +2** | same |
   | 6144 | 19 | 19 | tie | the crossover |
   | **8192** | 14 (pool) | **18** (pool) | **2.3, +4 (29 %)** | measured throughput +36.7 % at c=16 |
   | 12288 | 9 | **12** | 2.3, +3 | |
   | 16384 | 7 | **9** | 2.3, +2 | |
   | 32768 | 3 | **4** | 2.3, +1 | both are pool-starved; a different problem |

   **Caveat that stops this table being read as a ranking: capacity is not throughput.** `usable` is
   how many contexts *fit*; below that ceiling both arms run identically. So 3.51's two-slot edge at
   2–4k is only observable if offered concurrency lands in **19 ≤ c ≤ 21** — outside that window the
   arms are indistinguishable at short context, and the +36.7 % at 8k was measured precisely because
   c = 16 sits *above* the shipped 14-context wall and *below* 2.3's 18. The honest summary: **the
   two settings differ materially only near 6k and above, where 2.3 wins, and at c in [19,21] for
   short context, where 3.51 wins by 2 slots.** Everything else is a tie.

   **Design notes on the experiment as run.** `ship` and `r = 2.3` at depth 8192, `c = 8` and `c = 16`
   (16 sits above the 14 wall and below the 18 grant, so a real gain shows up as `#running-req`
   reaching 16 where the shipped config cannot pass 14), `runs: 5`, `prefix_caching: true`. Judge on
   **`#running-req` and `full token usage` from the server log, and `capped to N`** — *not* on offered
   concurrency, because the harness's `max_concurrency` does not clamp the server (c=40 earlier
   produced `#running-req` 20). The two arms are on different nodes (`node-free-1` ships `ship`, free via
   `--skip-run`; `node-free-2` boots `r = 2.3`), which is the wrong way round for a ratio test — see the
   co-tenancy warning in §12.8 — so treat absolute `K`/`#tokens` as indicative and the *throughput at
   matched `#running-req`* as the finding.
   **Refutation condition:** if `r = 2.3` grants fewer than 18, or grants 18 but aggregate at c = 16
   does not exceed the shipped c = 16 value, then the `min(cap, tokens/L)` model is missing something
   (most likely candidate: preemption or a chunked-prefill interaction the model does not price) and
   §12.8's table is not a capacity oracle, only an arithmetic bound.

A2. **Establish whether the c = 8 depth cost is real before trying to explain it.** Two boots put it
   at 25 % and 32 % against a ±15 % spec-arm noise floor (§3) — so the first job is a **same-window
    interleaved control**, not an attribution. Design: c = 8 at both depths, alternating, n ≥ 5 in one
    window on one booted server (`--skip-run`, so free of boot cost), bootstrap CI on the *ratio*.
    Only if it survives should it be explained. What is ruled out is narrower than this item used to
    claim: **not** retraction (two single-request retractions in six hours — but see §9 item 3, this
    does *not* exclude silent radix eviction), **not** acceptance collapse (3–8 %), **not** bandwidth
    at c = 1 (1 % of budget, where depth is a 3 % *gain*). The 4 % acceptance comparison also rests on
    mismatched 20-deep vs 14-deep windows and should be re-taken depth-matched. **Do not spend a new
    boot on this until the same-window control says it is real.**
 A3. **DONE (phase 26, §12.15): the 16k capacity test.** `benchmarking/capacity-at-16k.yaml`,
     `ship` vs `-o mamba_full_memory_ratio=1.2`, interleaved on both nodes. Pre-registered **13**
     usable 16k contexts at r = 1.2 against the shipped **7**; measured **14 vs 7**, and the one-context
     gap is the stale `T` the profile carried (solved at 24.31, boots ran at 25.14–25.18 — re-solved at
     each boot's own `T` the prediction is 14, and `#tokens` lands within 1.5 %). Peak `#running-req` at
     c = 12 was **7** (ship, pool usage 0.98, holding 21 granted slots) against **12** (r12, clipped by
     the experiment rather than by the pool). Aggregate at c = 12: **43.86 vs 28.15 t/s = 1.558×**, with
     the c = 1 null at 0.95. Because r12's ceiling (14) exceeded the offered c (12), **1.558× is a lower
     bound**; the capacity ratio is 14/7 = **2.00×**. Also refuted in the same run: my prediction that
     pool exhaustion would cause retractions — there were **zero**, the scheduler queues instead
     (`#queue-req` reached 11), so the cost of the wall is latency (TTFT 50.5 → 29.2 s), not recompute.
  A4. **DONE (phase 27, §12.16): offering `c = 16, 20` falsified the throughput claim, as the
      pre-written falsifier anticipated.** The capacity model holds exactly — peak `#running-req` equals
      each arm's ceiling (ship 7 of 7, r12 13 of 14), zero retractions again, acceptance identical
      (3.152 vs 3.163). But aggregate decode was **1.33× at c = 16 and 1.21× at c = 20**, not the ~2.0×
      the capacity ratio implies, and `r12`'s aggregate *fell* with more offered load. Cause, in
      arithmetic (`.scratch/qwen3-27b/kv_dilution_model.py`): KV read per verify step scales with
      streams (6.19 → 11.49 GB at 16k) while the 17.61 GB weight read does not, predicting 1.52× —
      most but not all of the shortfall. **This corrects §12.8**, where I ruled out KV bandwidth from a
      `c = 1` null; that was right at one stream and wrong as a general statement, since the quantity
      scales with the variable I held fixed. Residual is `LIKELY` real saturation and `LIKELY` partly
      within-boot drift (thermal / page cache — a *throughput* effect, not the pool-figure effect that
      §12.21 retracts as "container age"), so **phase 28**
      (`attic/benchmarking/same-boot-concurrency-16k.yaml`, `c = 8,12,16,20,8` with the repeated point as a
      drift meter, `--skip-run` on the live containers, zero boots) settles it. Quote capacity as
      1.86–2.00× and throughput as 1.21–1.56×, never one as the other.
 A5. ~~Acceptance vs depth has never been measured in one boot~~ — **DONE (phase 38, §12.23), and it
    needed no boot at all**: `depth-scaling-c8.yaml` happened to cover five depths on one already-running
    server with `tg` held, so the depth-matched + concurrency-matched comparison this item asked for came
    out of a throughput sweep for free. **Result: acceptance is flat** — −2.1 % from depth 1024 to 12288,
    inside a ±4.7 % single-point CI, `#running-req = 8` and `#queue-req = 0` throughout. The cross-phase
    **−10 %** figure quoted below was an artefact of comparing `tg` 128 against `tg` 256, exactly the
    confound this item was written to avoid; it is refuted, and `acceptance-vs-depth.yaml` should not be
    run. The paragraph below is kept because the *reasoning* about why flat acceptance + falling t/s
    implies a slower step is the part that feeds §12.23. Original text follows.
     §12.8's "depth costs a single stream nothing" is a statement about *t/s*, and decode t/s is
     `accept_len / step_time`, so it does not establish that acceptance is depth-independent. The
     cross-phase numbers on hand (depth-0 from phase 25 at `tg: 128`, n = 8; depth-16k from phase 26 at
     `tg: 256`, n = 44) give **3.49 vs 3.14, about −10 %**, which is nominally significant (z ≈ 2.9) but
     **the two profiles differ in generated-token count**, and `tg` changes the early/late decode mix —
     so this is `LIKELY AT BEST` and the sign of the error is unknown. It matters beyond tidiness: if
     acceptance really falls 10 % at 16k while t/s holds, the decode *step* must be ~10 % faster at long
     context, which is the wrong sign for the KV-bound regime §12.8 leans on. One boot, both depths,
     `c = 1`, `tg` held fixed, `accept len` bucketed by `#running-req` so the comparison is
     depth-matched *and* concurrency-matched — the mistake the earlier window-mismatched reads made.

 A6. ~~Is the depth-2048 throughput bump real, or in-container drift?~~ **NOT REAL — and this entry
    exists because its absence from this file caused a redundant re-run on 2026-09-22.**
    **Profiles: `attic/benchmarking/q0-d1024.yaml` + `attic/benchmarking/q0-d2048.yaml`** — run by
    `run_phase39.sh`, five randomised blocks (`$RANDOM` order per block), same live container via
    `--skip-run --fresh`, **zero boots**, artifacts `.scratch/phases/p39-q0/` (10/10 distinct md5s, pool
    identity `capped to 14` / `#tokens 239,346` unchanged across the run).
    **Result: mean ratio 0.950, median 0.929, d2048 slower in 4 of 5 blocks.** Under the rule
    pre-registered in the profile (REAL requires mean > 1.05 **and** ≥ 4/5 sign agreement):
    **NOT REAL. Depth is monotone decreasing. Do not quote a sub-4k depth bump.** See §12.23.
    **Why it looked real in the first place:** the original (phase 38) d1024 anchor was depressed
    because it ran *first* after a ~4-hour-old container had served another phase — the bump was
    never d2048 being fast, it was the first cell of a blocked run being slow. Re-anchoring on
    phase 39's d1024 gives a monotone curve. **A blocked (non-interleaved) depth sweep inherits
    first-cell depression into every ratio.**
    **Cost of not recording this:** five more cells of load on `node-free-1` and ~25 minutes, spent
    rebuilding profiles and a driver for a question that had been closed. The run was "free" of
    boots, which is exactly why it was launched without checking — but cheap-and-redundant is
    still redundant. **If you are about to write a profile, grep this file for that profile's name
    first; this file's whole purpose is to make that search possible.**

## §6.2 items C and 10, relocated verbatim 2026-09-22

Both were sitting inside a section titled "open, in priority order" while their own
first line said CLOSED. That is the pattern this file exists to remove: reading the
queue to find the next action should not cost 1,200 words of closed material. Moved
**verbatim** — including the failed instruments, the retracted headline in 12.14, and
the cost correction in item 10 — because the wrong turns are what stop an experiment
being queued a third time. Addressable as §6 item C / §6 item 10, and stubs remain in
WORK.md §6.2 so the inbound references from SSM-STATE-DTYPE.md keep resolving.

C. ~~`mamba_ssm_dtype` accuracy~~ — **closed as far as logprobs can close it (§12.12).** Three
instruments failed for three different reasons before one was valid: greedy text (no power — the
node null diverged more than the dtype pair), teacher-forced prefill (**structurally blind**, the
`gdn_backend.py:721` gate), and two analyzer bugs (`nan` matrices that looked like results;
averaging where per-rep exactness was the claim). The valid arm scores logprobs of a
**cached-prefix continuation** — the `has_initial_states = extend_prefix_lens > 0` branch, i.e.
where stored state is actually consumed — and reports **0.00e+00 across 495 tokens**, 6/6 per-rep
pairs exact, on one node, with `cached_tokens` byte-identical across arms. It is not a dead
probe: the same instrument on the same construction moves **1.0–5.1 nats** between full-reuse and
cold (§12.12's positive control, which cost no boot), and the dtype change visibly doubled
`ssm` MiB/slot in the very boots being compared.
**What is deliberately NOT claimed.** (i) *Mechanism*: unestablished; `LIKELY` that the kernels
upcast the stored state in a way that round-trips, `UNVERIFIED`, and the simpler alternative
(a state buffer pinned independently of the flag) is **disconfirmed by the allocation numbers**.
(ii) *Horizon*: every measurement is over 100–175 scored tokens from a 64–187 token prefix, and
**this limit is now partly tested, not just asserted** (`position_dlogprob.py`, run on phase 22's
transcripts, free). Two results, one of which is a limitation of the test itself:
- **On the dtype pair, an accumulation test is undefined.** Every delta is exactly `0.00e+00`, so
 there is no trend to fit — you cannot detect growth in a quantity that is identically zero. A
 null of this shape answers "does the stored dtype move the logits at the positions measured" and
 is silent on everything beyond them.
- **On the null, where there IS signal, the within-prompt trend is flat.** Bucketing by position
 *pooled across prompts* first reported `ratio inf -> GROWS`, which was wrong twice: `inf` came
 from dividing by a zero early median, and the 100+ bucket can only be populated by prompts over
 100 tokens, so it was a single prompt (`long-derive`, 175) in disguise — a content confound
 wearing a position costume. Held to within-prompt comparisons, that prompt goes
 `1.54e-01 -> 1.71e-01`, **ratio 1.11 = flat**, and the other three prompts are all-zero in both
 halves. So no evidence of accumulation, and also only **one of four prompts was long enough to
 test it** — a pooled position claim is unavailable at this corpus length regardless of outcome.
Practical bound this does give: the null's per-position noise is ~**1.5e-1 nats** on the one
prompt that carries signal, so a dtype effect accumulating at less than about that per position
would not have shown up in 175 positions. That is a real sensitivity limit, and it is the honest
form of "not proven safe" — not a claim that accumulation happens. (iii) *Quality*:
identical logits ⇒ identical output, so no eval is needed for greedy decoding, but a
sampling/low-temperature deployment or a downstream benchmark is the only thing that could show a
practical difference, and none has been run. **Bottom line for the recipe: bf16 state is free of
detectable numerical cost on the read path and buys 11 concurrency slots. Do not revert it.**
**Do not let the phrase "bit-identical" travel further than (ii) and (iii) allow.**
**That "next experiment" has since been run -- do not queue it again.** Reading the stored state
pool directly cost **no boot at all**: `docker create` + `docker cp` extract the kernel tree from
the image (no container start, no GPU), then one `--gpus all` run on a trial node executes the real
installed kernel on synthetic tensors. Result in **SSM-STATE-DTYPE.md 12.14**: the flag reaches the
*values*, not merely the allocation -- a bf16-stored state versus the same state stored fp32
changes **100 %** of kernel output elements, and the relative-L2 effect is **~1.7e-3, exactly one
bf16 quantum, in every condition** (`VERIFIED`). So the "the perturbation never happened" branch is
**refuted**, and the server-level exact zero is *not* explained at that boundary: it must be
absorbed downstream, between the kernel and the logits. 12.14 also retracts its own probe-3
headline, which was built on `frac-differ` -- that metric read ~100 % for a 1x **and** for a 1000x
perturbation, so it could not support any magnitude claim. **What remains open is mechanism only.
It is narrow and it is not on the critical path:** the recipe decision (keep bf16; it buys 11
concurrency slots) does not depend on it. Two lessons worth keeping from that sequence, both of
which cost probes: a metric that saturates across the range of the perturbation cannot size it, and
`a != b` on fp32 outputs is bit-exactness, not magnitude.


10. **`--enable-linear-replayssm-spec` is unreachable on this model — CLOSED ON HARDWARE
    (phase 50, 2026-09-22).** Booted it deliberately on `node-free-2` with
    `-o extra_args=--enable-linear-replayssm-spec`. The scheduler raised, verbatim:
    `ValueError: --enable-linear-replayssm-spec with DSPARK/DFLASH requires a KDA (kimi_linear)
    model; got a non-KDA model.` — character-for-character the prediction in §12.5, at the predicted
    file (`kv_cache_configurator.py:1106-1114`), and **after both weight loads but before the pool
    was built**: `Load weight end` appears twice (target, then `DFlash2DraftModel`), while
    `capped to` and `KV Cache is allocated` never appear — `_build_hybrid_req_pool` runs earlier in
    the sequence than the pool arithmetic §12.3 is about. **Cost correction, stated because the first
    version of this paragraph got it wrong and said "seconds rather than a boot":** the guard sits
    *downstream of weight loading*, so this test costs a full boot — measured 04:00:36Z container
    start to 04:02:14Z exception, ~100 s plus teardown. It is cheap for a boot, not free, and it is
    emphatically not something to re-run casually. Provenance:
    `.scratch/phases/p50-replayssm/p50_serve.log`, and the flag genuinely reached the config —
    `server_args` shows `'enable_linear_replayssm_spec': True`, so the guard fired at the right place
    and not merely because the flag was dropped somewhere upstream. **This retires the last open
    §12.5 prediction and it means §12 is NOT suspect** — that was the point of running it, since a
    boot would have invalidated the whole section's guard-chain reasoning.
    The prize it was worth chasing is also gone: `replayssm` would have removed the
    `D`-proportional `intermediate_ssm` that §12.6 measures at **12.27 GiB — half the entire
    leftover pool at the shipped `D = 8`** (the earlier "~18.7 GiB" was the bad-anchor value).
    It cannot be had on this model. **Do not re-queue it as a lever.**

    **But there is a genuine upstream inconsistency here, and it is worth a bug report.** The
    feature's own help text says it supports "**GDN** or KDA hybrid linear-attn models"
    (`server_args.py:2740-2745`), its deprecated alias is literally
    `--enable-gdn-replayssm-spec` (`server_args.py:4062-4067`, `new_flag` = the current name), and
    its description says "GDN sizes the window to the draft maximum" — i.e. three places treat GDN,
    which is exactly what `Qwen3_5` is, as a supported target. Yet the pool guard
    (`kv_cache_configurator.py:1104-1114`) rejects `DFLASH + non-KDA` outright, and
    `kimi_linear_config` (`configs/hybrid_arch.py:104-113`) returns `None` for `Qwen3_5Config`. So
    either the help text is aspirational and the guard is a deliberate safety rail, or the guard is
    too narrow and this recipe is being denied a feature its own documentation claims it can have.
    **Which of those is true is UNVERIFIED and not determinable from the pinned tree** — the guard's
    comment argues the former ("a non-KDA model there would scatter a `None` intermediate_ssm and
    crash"), which is a plausible reason for the rail, but the comment is in the same function as the
    code it justifies. **What would settle it:** ask upstream, or read the GDN backend's
    intermediate-state handling (`kda_backend.py`, `attention_hook.py`) to see whether GDN can
    actually populate the field the fold needs. Do not boot this again to find out — the guard is
    unconditional and pre-pool, so a boot can only reproduce this error.
