# Owner survey — 2026-10-25

Temporary register of blocking questions; answers fold into TODO/QUESTIONS per protocol and the file is deleted after the fold.

## 1. Session endgame vs the unpark ruling

When the TP=4 queue (Retry-queue items 1–4) drains, does this session still drain and close with TP≤2 items possibly unfinished, or does it now run until both queues drain?

Context: the 2026-10-24 ruling (`QUESTIONS.md` `#3`) said "when TP=4 session is complete, this session drains and closes. Another session will complete the TP≤2 queue when production inference restarts", and the session record states no post-window TP≤2 session is authorized. The owner has since unparked the TP≤2 items into this same session and restated "no idle nodes while automated research runs".

Decision needed: which instruction governs at the drain point — close on the TP=4 queue, or hold the session open for the TP≤2 queue.

## 2. Ship/no-ship on the three `zz-` probe recipes

Decide now on the ship status of Ternary-Bonsai-2-9B Q2_0, Kromoss and Timestral-209M, or keep all three as `zz-` probes until more cells exist?

Context: Bonsai Q2_0 clears its full easy-traffic gate on a quiet node (C1 75.51 ± 1.38 vs bar 69.28, C10 129.79 ± 0.90 vs bar 116.27, house 36/37); Kromoss has a measured one-node image cell with the step knob proven live (control 143.884 s, 8-step LoRA 18.341 s); Timestral-209M passes every pre-registered runtime cell on CPU (load 1.9 s, peak RSS 2.26 GiB, all six quantile grids monotone). All three sit in `recipes/` as `zz-` non-shippable probes, and the ship call is parked as an owner decision.

Decision needed: ship, or hold as probes — and if ship, which of the three.

## 3. KV-pool rule for chunk-size arms

Is "keep `mem_fraction_static` pinned, record the shrunken pool as-is" the standing rule for the next chunk-size arm?

Context: the 32768 probe already ran on 2026-10-25 and lost — mean cold prefill 263.6 s / ~3.79k t/s against the 16384 bar's 245.0 s / 4.09k t/s, a 7.6 % regression, with `max_total_num_tokens` collapsing 3,042,304 → 1,356,288 at the same 0.78 fraction. The pin was not moved and the pool loss was recorded in the receipt, so `DEEPSEEK.md` §9's margin arithmetic has one empirical point rather than a ruling.

Decision needed: confirm that precedent as the rule (pin holds, pool shrink reported, no `mem_fraction_static` compensation), or allow a flagged fraction adjustment on a future arm.

## 4. Adoption bar for the self-built main image

Is C1-vs-control within noise enough to adopt `sglang-main-arm64:6563312` as the base for future arm work, or does it need a full ladder plus house pass first?

Context: the boot-gate ran one cell — C1 21.336 ± 0.011 t/s (n=3) against the `v0.5.22` control's 20.38, i.e. inside the gate's tolerance but roughly a 4.7 % delta — with no concurrency ladder and no house battery on that image. The board row records it as PASSED and notes a re-queue is owed only if the bar is revisited.

Decision needed: name the adoption bar — C1-only pass, or ladder + house required before it becomes a candidate base.

## 5. OrcaCyber tier A/B open cells

Are the quality/refusal/vision cells for the 13G control still owed, or is the item closed as landed?

Context: the lane README now records those cells as measured on the same 2026-10-24 boot — house 37/37 thinking-on, 0/4 refusals, vision 2/2 exact, receipts in `~/benchmarks/tp2-queue-20261024/` — for both the 13G control and the 15.7G default, so the earlier "cells open" note is stale rather than unfulfilled. The 15.7G section still says the 13G arm "has not been booted", which the control's own ladder and battery rows now contradict.

Decision needed: close the item as landed (and the stale sentence gets corrected), or re-run something before it is closed.
