# Protocol — how this planning file works (owner ↔ agent)

This file is the interface for planning rounds:

1. **Questions for the owner live only under `# DECISIONS`**, one per item, each ending with a
   `→ Answer:` line. **To answer: edit that line** — a word is enough ("defer", "skip", or a full
   call; replacing the ask with the answer is fine). Replying in chat or a numbered questionnaire
   works too. No special format needed.
2. **The agent folds answered items** into the work item(s) they govern as advisory notes tagged
   *"(Owner decision YYYY-MM-DD: …)"*, removes them from `# DECISIONS`, and restates whatever is
   left. Verbatim history is always in git (`git log -- mad-science/TODO.md`).
3. **Everything outside `# DECISIONS` is agent-maintained** — statuses, measurements, lane scope,
   the session record. State claims carry dates or commit hashes.

**Where things live:** this file holds **open work only** — completed items are archived in `../attic/DONE.md` as they close; dated session records live in `SESSION-RECORD.md` (same directory).

# DECISIONS — 0 open (2026-10-22)

New owner questions land here, one per numbered item, each ending with an answer line the owner edits in place. Numbered decisions cited elsewhere —
#6 in `attic/qwen4/SELECTION-RANKING.md`, #11 in `attic/decision/DECISION-MODELS-RESEARCH.md`,
#10/#11/#14 in `attic/explore/EXPLORE-MODELS-RESEARCH.md` — live in git history: the 2026-10-11
register is `git show 8a98379:mad-science/TODO.md`; the 2026-10-14 registers (#16–#23, #24–#27) are
the pre-fold states, `git show baecfa8:mad-science/TODO.md` and `git show c7c7a81:mad-science/TODO.md`;
the #28–#33 register is the pre-fold state `git show 0d8014d:mad-science/TODO.md`; the #34/#35 register
(2026-10-15, answered the same day) is `git show 043fbae:mad-science/TODO.md`; the #36–#42 register
(2026-10-17, answered the same day) is the pre-fold state `git show ebb7e80:mad-science/TODO.md`.

*(Answered 2026-10-19 — no open questions. The three asks are folded into the work items they
govern, per the protocol; the verbatim asks remain in git.)*

- **#43 — superseded `deepseek-ai/DeepSeek-V4.1-Flash` base.** *Owner decision 2026-10-19: reclaim.*
  It is already absent from the head cache (only the load-bearing `-1017` base and a 5.4 MB
  `V4-Flash-0731` remain), so the answer is satisfied and the 510.3 GB line is retired from the
  register.
- **#44 — unblock `qwen3.8-flash-next-uncensored` on vLLM.** *Owner decision 2026-10-19: bump the
  image.* The lane's next step is to identify a vLLM build whose compressed-tensors mapping excludes
  ignored shards (or whose qwen4_exp model applies the three-shard mapping before `get_quant_config`),
  validate it against the two shipped vLLM lanes first, then re-boot this arm.
- **#45 — prune the attic-only weight caches.** *Owner decision 2026-10-19: prune all six.* Done the
  same day: 430 GB freed (Laguna-S 99.7 + humanizer 87.6 + Nemotron 80.4 + Mistral 70.8 + two
  Kolibri packs 45.8 + 45.8), head now **493 GB free (87 %)**; the load-bearing 1017 base and both
  GLM EXL3 packs untouched. Laguna-M.1's retry is unblocked.

*(Answered 2026-10-22 — no open questions. `#47` is folded into the TP=4 work items as the
run-everything directive; the verbatim ask and answer stay in git (`git log -- mad-science/TODO.md`).)*

**Storage (2026-10-19, late).** Cache audit and prune across the head and the test pair, after `#45`'s
head-only pass: the node copies of the attic-only weights had never been pruned. **HF, by `hf cache rm`
only** (never `rm -rf`): head **218.2 GB** (MoVA-36B pair 123.3, Kolibri MXFP4-MxWave 44.0, Mellum
bf16 24.3, r0b0tlab 35B 23.6, Laguna-S DFlash 2.2, Kolibri block-drafter 0.8), `.34` **149.8 GB**
(Mellum bf16, r0b0tlab, Laguna-S DFlash, **Laguna-S NVFP4 99.7**), `.35` **431.0 GB** (MoVA pair,
Kolibri MXFP4, Mellum bf16, block-drafter, **humanizer 87.6, Mistral-Small-4 70.8, Nemotron-120B
80.4**). Free space: head 493 → 721 GB, `.34` 730 → 893 GB, `.35` 305 → 753 GB. **Kept because a
shipped recipe names it:** all 24 pinned digests' repos — notably the 397B graft (its recipe still
ships), both DeepSeek EXL3 bodies (cybersec arm 5 and ds4 TensorFold), `local-inference-lab/…
Flash-Next`, RadixArk, and the production `-1017` base. **Docker:** removed only images no recipe
digest, no tracked doc and no container names — head **3** (24.6 GB relay-only, a dsv41 variant, a
stale TensorFold-GLM alias), `.34` **3** (25 GB), `.35` **2** (55 GB); ~94 GB total. Kept every image
whose full RepoDigest is in the 24-entry pin set, every image a doc names (`kolibri1-drafter`,
`dgx-vllm-eugr-nightly`), and both nodes' live serve image. **`.30`–`.33` were audit-only** — the
production TP=4 serve was not touched. Both test serves answered `/v1/models` 200 after the prune.
**Fleet extension (same day).** `.30`–`.33` audited read-only against the same test — they hold no
attic-only bulk, only shipped repos plus three strays: the two **49.6 GB** and **45.8 GB** Kolibri
NVFP4 pack repos on `.32`/`.33` and a retired `incoai/Qwen3.8-27B-DFlash2` draft (the shipped draft is
`z-lab/…`), pruned with `hf cache rm` (`.32` 950 → 996 GB free, `.33` 925 → 967); `.31` had nothing
unreferenced and `.30` only empty shells. The production TP=4 serve answered `/v1/models` 200 on rank 0
afterwards. **No `docker image prune -a` was used anywhere** — every removal was an explicit tag or ID,
so a queued ladder still finds its image.
*The `sparkrun/tensorfold-glm53-exl3-3bpw:0.6.0-ddfad35` tag was removed with its stale build: it is
named only in a launcher comment and it pointed at manifest `25bb6806`, whereas the recipe pins
`366c2d4e` under `littlecedar/…` (kept). It was a local build tag that disagreed with the pin, so it
was deliberately not restored — restoring it would have aliased a different engine than the gate
asserts.*
*A join that truncates digests to 12 hex chars silently matches nothing — the first classification
listed two recipe-pinned sglang images as deletable for exactly that reason; match full RepoDigests
and the `oci-relay/pinned:<hex>` tag suffix before deleting.*

# TODO list

*(2026-10-14 documentation sweep — six parallel lane/registry scouts over `recipes/**`, `attic/**`,
`benchmarking/`, `tools/`, and the `mad-science/` memos. Every item below carries `path:line` evidence
and an effort tag; boot-requiring work is the long tail. The per-lane "all items completed" stubs were
dropped where the sweep opened new work.)*

*(Owner decision 2026-10-15: the sweep runs with no timebox — multi-day, group by group, stopping
only at a gate; the register is the scope, not a plan.)*

**Resourcing (2026-10-15).** `.34`/`.35` only for this sweep *(Owner decision 2026-10-15: no TP=4 window
this session, so the multi-node items in the lanes below and the ornith 397B re-run stay deferred;
`.30`–`.33` are busy with the ds4 TP=4 job)*. Every `sparkrun` call runs from
the head with the HOME override and `--transfer-mode local`, and **the registry clone must be
refreshed first** (`sparkrun registry update littlecedar`) after any recipe or lane-mod change: the clone
sat two commits behind and carried no lane-local `mods/`, which made an `@littlecedar/…` launch of the
ornith 35B die with `Could not resolve mod 'mods/ornith-honed-chat-template'` (2026-10-15). It was
refreshed that day and now materializes the lane mod — re-check after each push. For the same reason, launch a recipe by its
real path — never a flattened `~/development/<name>.yaml` symlink. Only two orderings are asserted: the
RadixArk reclaim on `.34` is tagged *immediate* (126 GiB resident against the owner's cache policy), and
the ornith 35B is the first arm of the standard-suite sweep.
**Resourcing (2026-10-18).** The session opened on `.34`/`.35` only; **mid-session (~10:15 ET) the owner
released `.30`–`.33`** — the peer DS4.1 TP=4 job had ended — so all six nodes are in scope. TP=4 work runs
on `.30`–`.33`, TP≤2 work on `.34`/`.35`; never put `.34`/`.35` into a four-node launch while their queues
run. The budget is unlimited *(Owner decision 2026-10-18: no timebox, stop only at a gate)*. Registry-level
sweeps first (the standing 2026-10-16 order below), then lane builds, cheapest-effort first. One serve per
node; at most one TP=2 job on the `.34`/`.35` pair and at most one TP=4 job on `.30`–`.33` at a time. Every
`sparkrun` call runs from the head with `--transfer-mode local`, and the registry clone is refreshed first.
*(This supersedes the [#42] deferral written earlier the same day — no TP=4 window — which the release
lifted; the TP=4 lane items below are in scope again.)*
**Node discipline (Owner directive 2026-10-19).** Both test nodes are kept busy: the pair
`.34`/`.35` runs **two independent single-node lanes** (one serve per node) and collapses to one
lane only for a TP=2 boot. When a lane frees, the next staged arm boots immediately — the tail is
ordered cheapest-window-first in the suite item, and each lane's boot+suite commands are prepared
before the previous leg ends. Current occupancy is recorded in the session record; the pair's
node-hours are the binding cost, so an idle node is the defect. **Long suite legs run under
`setsid` + `stdbuf -oL` writing to a file.** Measured 2026-10-19: a wrapper timeout kills only the
wrapper — both "timed-out" suite parents were still alive and sequencing their children an hour
later, while their 0-byte redirected logs looked like failure. The rule is therefore: verify pids
(`ps -eo pid,etime,cmd`) before any restart, treat an empty redirected log as buffering, and never
start a second leg on a node that already has one — two duplicate pairs were created that way and
had to be killed.

**Resourcing (2026-10-19).** **Sessions are unlimited** *(Owner decision 2026-10-19)*: agent runs are
no longer bounded by a session window, so the register's content work can continue continuously until
it closes. The local **DeepSeek-V4.1-Flash-1017 TP=4 serve is stable and hosts the agent sessions**
(it is what makes the unlimited budget possible), so `.30`–`.33` are **production, not a test lane**:
never disturb that serve for a registry boot. The only manual owner engagement now is **switching to
an offsite API endpoint when TP=4 tests must run** — batch every TP=4 measurement behind one switch
rather than asking per boot. Local `.34`/`.35` remain the registry's GPU pair: one serve at a time,
TP≤2 boots only. The binding constraints are therefore (a) serialized boot time on `.34`/`.35` and
(b) one owner action per TP=4 offsite switch, not calendar days.

**Ordering (Owner decision 2026-10-16).** Registry-level sweeps first — image pins, the advisory bump, the standard suite — then the lane builds; inside a group, cheapest-effort first.
*(Owner decision 2026-10-18 [#36]: a same-window win by the lane's bar (>= 2 % or outside the cell's σ) may flip a shipped perf value, including an accuracy-neutral engine flag, with a boot receipt plus a lane-doc/recipe-comment record; engine/container/digest changes and anything that moves accuracy semantics still come to the owner first.)*

**Session progress (2026-10-18).** Receipts under `~/benchmarks/` on the head; the narrative lives in
`SESSION-RECORD.md`. Registry: ds4 knapcio TP=4 ladder **C2 89.9 / C5 113.4 / C10 115.4** t/s (C1 pooled
**67.18 ± 6.97**, n=25) and its standard suite **house 36/37, needle 3/3 @983k, TEB 90** (`tp4-20261018`);
ds4 TensorFold TP=2 ladder **C1 68.6 / C2 48.1 / C5 44.6 / C10 42.1** and house 37/37
(`ds4-tp2-ladder-20261018`); qwen3 coder-next suite **house 36/37, needle 3/3 @256k, ARC 92.0 / GSM8K 96.0**
(`qwen3-coder-next-suite-20261018`). ds4: DSpark **γ=3 proven non-bootable** (checkpoint block size 5 only;
the knob is now reachable as `defaults.dspark_block_size`). glm5: the 4bpw TP=4 recipe's **first boot** — TTR
309.6 s, 1M ctx, 5,834,752-token pool, C1 83.0 t/s (98.4 does not reproduce). ifm: the 7B `fp8_e4m3` KV gate
**PASSES on triton** (36/37, 188/200, 179/200, no length inflation; `fa4` cannot carry fp8 KV). explore/Kolibri:
GGUF APEX-2.4bpw **63.24/60.79 t/s, 37/37, 79 GiB free**; MTP drafter **55.6 t/s (+18 %), acceptance 1.91,
37/37**; three 4-bit vLLM quants at **52.48 / 52.0 / 51.60** t/s on **4.61–4.79 M-token** KV pools; the
constant-state 1M eval arm answers a **999,155-token request in 829.7 s** at **10.44 GiB of host archive per 1M
request** (0.208 GB claimed), so 1M concurrency is **1**. cybersec: NEXTN on the 27B arm **C1 14.72 (+44 %)**,
acceptance 2.774 — and the served context is really **167,985 tokens**, not the advertised 262,144. storage:
**263 GiB reclaimed** on the head (39.4 → 302.4 GiB free); `#43`'s 510.3 GB base is still flagged. Still open at
that point by lane: glm5 3.0bpw (recipe + 1M arm); ornith 397B, 0.5.21 bump, marlin pairs, r0b0tlab;
qwen4 (W4 soak, linear-replayssm, backlog, diagnostics); ifm UNO 0.9B / 7B tree / 36B
D2+E6; embed co-location; decision candidates + TTS; explore reasoning candidates, Laguna-M.1, media-gen and the
three unrun Kolibri GGUF tiers (Hob-forge / webmp3 / aparusel); cybersec arm 4; llama.cpp residuals; ds4
v2.4 serve line (in flight).
*(Superseded the same day: the glm5, qwen4-linear-replayssm and ifm-36B entries closed, and ornith's 397B retry was dropped by owner policy — read the late roll-up below, not this list, for what is open.)*

**Session progress (2026-10-18, late).** Two registry-level items closed: the **pooling ladders** — embed-8B
**16.39 / 18.10 / 21.54 / 23.01**, rerank-8B **18.03 / 18.58 / 21.24 / 21.23**, embed-2B **38.82 / 46.51 /
85.63 / 104.07**, rerank-2B **74.06 / 81.57 / 85.08 / 85.00** units/s at c1/2/5/10, with an **idle co-resident
engine free (≤1.7 % everywhere)** and a **busy one costing ~2× on the encoder** (8B 2.19×, 2B 2.12× at c1)
(`sweep3-20261018`) — and the **qwen3 ratio re-sweep** (3.51 kept: nothing clears the ≥2 % bar; with the fixed
loader **48 slots × 8,192 bind before the 493k pool**, so the ratio only redistributes headroom;
`qwen3-ratio-20261018`). Both shipped 8B embed/rerank arms were **unbootable and are fixed** (embed
`load_format: auto`, rerank nested `text_config.tie_word_embeddings: false`), booting as shipped with their c1
cells unchanged (16.25 vs 16.39, 17.94 vs 18.03; `embed-fix-20261018`). ifm 0.9B's standard-suite pass is
**PARTIAL** (contract ok, house 17/19 + 15/18, needle FAIL on the 256-token cap — every reply reasoning-only,
hard floors length-limited, tools cut at 585/904; `ifm-09b-suite-20261018`). explore: Qwen-Image **2048² at
53.24 s/image** (σ 0.20, n=3) against 11.240 s at 1024² on the same boot, tiling off, images byte-identical —
the lane's ~26 s is **falsified 2.04×**, and a non-null `num_inference_steps` is **silently ignored** (the
checkpoint's sigmas win); LTX now measured too — I2V **84.3 s (+7.9 %)** / FLF2V **120.2 s (+54 %)** warm,
4K/50 fps **OOM at 121.16 of 121 GiB** (`ltx25-20261018`). decision: **laya** at
**36.1 % (723/2000)** — the vendor's near-chance expectation — its recipe now satisfying the sparkrun
model-identity contract via `LAYA_MODEL_PATH=<path>` (guarded), ladder c1 **0.449 req/s / 2.25 decisions/s**,
flat at c2 with doubled latency (`decision-arms-20261018`). ds4: the carried **v2.4 serve line** was
read on its `--prefill-decode-interval 2` arm — C1 60.2 / C2 73.2 / C5 95.1 / C10 101.5 against the
v2.3 line's 67.2 / 88 / 111 / 116 — and **the flag, not the line, is what is slow**: the isolation
boot then ran (C2 88.35 / C5 131.83 / C10 123.49 with it off) and the launcher ships `0`
(`c59f00d`), with the pin re-derived to 6,850,000 (`ds4-v24-line-20261018`).

**Policy (2026-10-18, 19:15).** **DeepSeek and TP>2 work was expedited and is now CLOSED by owner
instruction**: `.30`–`.33` return to their normal workloads, `.34`/`.35` remain available. Anything
still wanting four nodes (the ds4 C1 re-take, the GLM 1M arm, the ornith 397B retry) is **dropped,
not deferred**. The GLM-5.3 EXL3 3.0bpw arm is promoted, booted and receipted to the end of its
bounded pass — see `## glm5`.
*(2026-10-19: `.30`–`.33` now host the stable local TP=4 serve that carries the agent sessions.
The four-node *node window* remains closed, but TP=4 **measurement** is no longer blocked — it runs
against an offsite API endpoint, and the owner's only action is the endpoint switch. The three
dropped items above stay dropped; re-file one only if the owner asks for it by name.)*

**Cluster state (2026-10-19 00:00 ET).** `.34`/`.35` run the **qwen4 labquant TP=2** serve for this
campaign (`1895030211ea0500_3510a5e0d37d`, 2 containers, healthy since 23:01): eval-suite and
tool-eval-bench are done, the W4 90-minute soak is in flight. `.30`–`.33` remain the owner's ds4 TP=4
job (`a2e141223b52793c_de0b14250a90`). The head's `a2e14…` control container is that job's, not litter.
**Checked 00:43 ET:** soak pid 284384 alive (55 min elapsed); `gate-37111.json` is not written yet — the
gate writes it on completion, 01:18:10. **Closed 01:20 ET:** soak **PASS** (708 turns, 0 degeneration
/ 0 truncation findings, 0 transport errors, canary warm==cold) — the same-boot ladder reads 41.22 /
72.88 / 95.18 / 108.13 t/s, receipt `REPORT.md`. Serve stopped and `.34`/`.35` verified idle (0
containers, no `/tmp` leftovers). The owner's ds4 TP=4 job now reports as
`a2e141223b52793c_e11d626ec2c6` on `.30`–`.33`, still healthy (the `de0b14250a90` id above is gone).
**2026-10-19 ~05:10 ET:** `.34`/`.35` idle (0 containers, `pgrep -af "[s]parkrun"` clean) after the
marlin and r0b0t campaigns — the next window can start immediately.

**Cluster state (2026-10-18 21:52 ET) — superseded by the 2026-10-19 00:00 entry above; keep for the
job history only.** A **new owner-launched ds4 TP=4 job** takes the four-node slot
again — `a2e141223b52793c_de0b14250a90`, `.30`–`.33`, `littlecedar/dgx-spark-dsv41:canary-roce@acfc331a`,
**healthy** at 21:52. `.34`/`.35` are idle (0 containers, 0 `sparkrun` processes, `pgrep -af "[s]parkrun"`);
the head carries that job's control container plus the always-on `sparkroute` gateway, its autodiscover
and a `sparkrun cluster monitor` — infrastructure, not session leftovers. Treat the `.34`/`.35` pair as
the only free resource.

Selection priorities:
- Node count (lower is better)
- Accuracy (higher is better)
- Speed (higher is better)
- Memory footprint (lower is better)
- *(Owner decision 2026-10-11: this weighting is confirmed; attic moves only if warranted, folded into each lane's quality/selection pass — no global end-of-session sweep.)*

**Closed 2026-10-19 (three no-boot items).** The deep web search, the sparkrun 0.4.0 schema-docs pass
and the explore keeper sweep landed as separate commits. The sweep left the lane at **6 arms** (5
measured keepers + the authored Laguna-M.1 pair) and retired **10** to `attic/explore/`, so the
registry now stands at **48 recipes in 11 lane dirs, 752 tests, 12/48 strict failures** — re-measure
before quoting any of those numbers. All three items are archived in `../attic/DONE.md`. `.34`/`.35`
stayed idle throughout.

## ds4
DeepSeek V4.1
*(The v2.4 serve line is settled and carries no runnable work: with
`PREFILL_DECODE_INTERVAL: "0"` it beats v2.3 at C5/C10 (`recipes/ds4/README.md` §(b)–(d)); the one
unrun cell, an interleaved C1 re-take on the shipped line, needs `.30`–`.33` and was **dropped, not
deferred**, by the 19:15 policy above. Measurement, launcher pins and the correction to the earlier
"slower on every cell" reading are archived in `../attic/DONE.md`.)*

- [ ] **Run the now-runnable arms of the deep-search shortlist** *(delivered 2026-10-19; the two
  runnable arms were measured 2026-10-21 — see the closed item below.)* — the ranked note is
  `mad-science/DS4-SPEEDUPS.md` (11 candidates + a precondition, each with mechanism,
  expected effect, carrying flag/artifact, dated source, and a pre-registered interleaved A/B); the
  lane README now lists them under §"Upgrade candidates". The **P0 GPU
  clock-latch audit is closed negative** (2026-10-19: both nodes idle at 208 MHz, but ramp to
  2171-2190 MHz under load against a 3003 MHz max, with SW Power Cap the only active throttle
  reason — no latch; receipt `~/benchmarks/ds4-p0-clock-20261019/`). The TP=4-only
  eight stay upgrade candidates while `.30`-`.33` are frozen. Re-derive any win with its own receipt
  under `~/benchmarks/`; the A/B rules are `recipes/ds4/README.md` §(b)-(d) plus the note's §"The
  baseline these A/B plans assume". *(effort: medium)*

  *(Owner decision 2026-10-22: keep the quartet on measurement duty — production stays stopped, the quartet
  serves the TP=4 queue.)*
  *(Owner decision 2026-10-22: run the full 20–28 h block — qwen4 W6 then W12, the ds4 TP=4 candidates,
  then the four-node suite legs; the block is resumable, so a pause is never a loss.)*

- [X] **The two runnable shortlist arms, measured and closed 2026-10-21.** Six interleaved boots on
  `.34`/`.35` (A/B/A/B/A/B, `--fresh`, `/v1/models` + the container's own `tensorfold --version`
  asserted per boot) settled the **TensorFold v0.6 engine bump**: control `fabbe861…` is engine
  `0.6.3` (built 2026-10-05 from `d5d7bb3`), treatment `d6e4c10d…` is `0.6.6` at `3825f62`, and on
  the depth-0 ladder (3 runs/cell, n=9/cell) the treatment reads c1 64.47 (flat), c4 51.15
  (+10.9 %, ranges overlap), c8 **52.45 (+26.5 %)**, c16 **53.21 (+25.7 %)**, with cold prefill
  **2,077 t/s @ 32k (+24.6 %)** and **2,073 @ 131k (+39.5 %)**. The treatment's worst single run
  beats the control's best at c8 and c16, so the falsifier is not met: **adopted**, and the shipped
  recipe now pins `d6e4c10d…` (one-time 264 s JIT on the first v0.6 start; later launches 80.3-80.9 s
  vs the control's 80.1-81.5 s). **`reasoning_effort: high`** was measured request-level on that
  serve: paired same-task A/B (10 tasks × 2 rounds × 2 arms, arm order flipped per round) gives a
  **10.6 % reasoning-token saving** at house 37/37 on both arms with no pass→fail flip — but
  `hard-rev` (128 → 43) carries most of it and the bar is cleared by 0.6 points, so it is recorded
  as "clears, not a headline". Receipts `~/benchmarks/ds4-v06-ab-20261021/` (`REPORT.md`) and
  `~/benchmarks/ds4-v06-build-20261021/` (build log, digest); the note's §4/§6 now carry the tables.

- [ ] **Make the ds4 knapcio image byte-reproducible** — the 2026-10-22 rebuild is behavior-identical but not reproducible: config identical (entrypoint, cmd, env, healthcheck, labels; 91 layers, layers 0–69 identical) and the content diff is four recompiled `__pycache__/*.pyc` plus 6,707 hash-equal files, so `littlecedar/dgx-spark-dsv41:canary-roce-20261022` = `sha256:0cbe228a…` is not the shipped `acfc331a…`, which stays pinned. Unblocker: a deterministic build step (bytecode off, `SOURCE_DATE_EPOCH` set). *(effort: medium; recorded 2026-10-22 01:10 ET)*

- [ ] **Research `kaushikvira/DeepSeek-V4.1-Flash-1017-GSQ-agentic-strata`** — a 382.8 GB "GSQ"
  mixed-precision export of the 1017 body in a *strata*-format GGUF that no engine this lane ships
  can open. **Research only, not queued for a boot** — the four-node window is closed and a TP=4
  measurement needs the owner's offsite switch.
  *(facts:* open (`gated: false`), card `license: mit`, one branch `main` @ `7aa29158…`, Hub
  `usedStorage` **382,778,487,408 B = 382.78 GB / 356.5 GiB**: `V41-GSQ-1017.gguf.part-00`
  96,636,764,160 + `.part-01` 77,722,075,136 (one **174.36 GB / 162.4 GiB** GGUF, `cat`-recombined,
  and the card's "153 GiB" budget and "90 GiB + 73 GiB" parts describe a build that is not what
  shipped), `V41-MTP-Vision-1017.Q2_K.gguf` 5,661,492,320,
  `engram-layers.{1,14}/engram-L{1,14}.safetensors` 101,377,628,584 + 101,380,404,328 (**188.8 GiB**
  of Engram, the same L1/L14 tables the lane already stages per node),
  `V41-GSQ-1017.gguf.experts.json` 1,226,894, `rank.bin` 122,880, `tokenizer/` 5.8 MB. **Weights, not
  an overlay** — unlike the `drowzeys/…` overlays (no weights; 683 MB + 1.09 GB sidecars grafted by a
  mod), this repo ships the whole quantized body plus its own Engram tables. `config.json` is only
  the base declaration: `quantization_config` = `{"quant_method": "fp8", "activation_scheme":
  "dynamic", "weight_block_size": [32, 32], "scale_fmt": "ue8m0", "expert_dtype": "fp4"}` and **no
  `kv_cache_scheme` key** (the card's FP4 KV is a serve-time `--kv-fp4` flag). The scheme is in the
  GGUF header instead: `deepseek41.quantization` = "routed experts: per-expert Q3_K / Q2_0 / PTQ1_0
  (gate+up share a type, down its own); Q8_0 attention / shared / head; F16 embedding";
  `strata.v41.expert_tiers` = `{"down:PTQ1_0": 4447, "down:Q2_0": 6682, "down:Q3_K": 4231,
  "gu:PTQ1_0": 5750, "gu:Q2_0": 5113, "gu:Q3_K": 4497}`; `strata.v41.expert_layout` = "uniform role:
  ffn_<role>_exps.weight; mixed: ffn_<role>_exps.<type>.weight per type (experts in id order) + I32
  ffn_exps_{gu,down}_type[384]"; `strata.v41.expert_source` = `inplace:rtn:q2_0:268d4652…`; Engram
  `e4m3_e8m0_32_row264`. Those tier counts are exactly the `experts.json` code census over 40 layers
  × 384 experts × 2 projections (10,197 / 11,795 / 8,728), so **143 = PTQ1_0 (the card's "ternary"),
  42 = Q2_0, 11 = Q3_K**. "GSQ" is the card's "GSQ (Gumbel-Softmax Quantization) + per-expert
  mixed-precision tier allocation" (method credited to antirez); "agentic" is the *calibration*
  weighting, not a layer mix and not a pruned expert set — "Every routed-expert projection is
  assigned its own precision tier (Q3_K / Q2_0 / ternary) from activation calibration on an agentic
  + coding corpus" (32 × 8,192-token sequences: agentic_long 10, code 10, agent 5, reasoning 3, web
  2, chat 1, multi 1), allocated to a fixed 153 GiB budget; "strata" is the engine
  (`library_name: strata`). **Provenance contradicts the card:** the GGUF's own `general.name` is
  "DeepSeek V4.1 Flash UNCENSORED (Strata v41 GSQ-RCO mixed tier)" and `general.source.url` is
  `dealignai/DeepSeek-V4.1-Flash-UNCENSORED-FP8` (510.3 GB, tags `abliterated`/`uncensored`, its own
  base `deepseek-ai/DeepSeek-V4.1-Flash`, not the 1017 refresh), while the card claims
  `base_model: deepseek-ai/DeepSeek-V4.1-Flash-1017` and "no abliteration".*)
  *(why it matters:* weight-only it is the smallest ds4 body measured against — weights + sidecar
  **180.0 GB / 167.7 GiB** vs 510.3 GB (official), 210.8 GB (EXL3 2.9 bpw), 413.4 GB (Engram pack) —
  and two 128 GB nodes (238.4 GiB) would hold it resident, but **the loader question is closed, not
  open**: `recipes/ds4/README.md:25` (SGLang through `mods/dsv41-sglang-overlay`) and `:349`
  (TensorFold `deepseek_v41`, EXL3 mul1) are the only engines this lane ships, neither reads GGUF,
  and the card says so outright — "Not runnable on vanilla llama.cpp, Ollama, vLLM, or SGLang
  without a strata-compatible loader". Its engine is `strata`/`ds41_generate` from
  `Indras-Mirror/Xolotl` (public, MIT, a heavily extended fork of Strata): one host, three tiers
  (VRAM / pinned RAM / NVMe), Linux-only, reference machine 24 GB VRAM + 90 GB RAM + NVMe at ~27
  tok/s — weaker than one Spark, which is why size does not rule a single node out; the engine's
  missing arm64/GB10 build and its lack of any multi-node path do.*)
  *(blockers/unknowns:* nothing to boot on — a strata port is a new engine family for this registry,
  not a recipe re-point; arm64 + CUDA 13 support is unknown; the card's quality gate is unfinished
  ("Full evaluation is coming"; 21 HumanEval + 10 tool calls only); the shipped 174.36 GB GGUF does
  not match the card's 153 GiB arithmetic; the abliteration-provenance mismatch must be settled
  before the id is quoted as an official-weights variant; `tokenizer.ggml.pre` is `joyai-llm` and
  `tokenizer/chat_template.jinja` is a 91-byte stub pointing at `serve_ds41.py`, so a loader port
  inherits the lane's template-less problem. All sizes are Hub `usedStorage`/`tree` bytes; no node
  cache was read.*) *(effort: research only — a boot needs a strata/GB10 port first.)*

- [ ] **Research `local-inference-lab/DeepSeek-V4.1-Flash-1017-FLARE`** — a publisher-signed Flare
  *runtime package* whose `gb10` branch targets **four DGX Sparks at TP4/c16**, served only by a Rust
  runtime installed from a third-party APT repo on every host. **Research only, not queued for a
  boot** — the four-node window is closed and a TP=4 measurement needs the owner's offsite switch.
  *(facts:* open (`gated: false`), `license: mit` (the file is DeepSeek's own MIT text),
  `publisher.json` carries Local Inference Lab's Ed25519 key with `"development": false`, and the
  runtime enforces a `--trust-store` acceptance. Three branches, three packages: `main` @
  `5f4fd653…` is card + license + publisher only (**4 files, 11,589 B** — no weights on `main`);
  `gb202` @ `30b3987c…` = **513.48 GB** for one host with four SM120 96 GB GPUs; `gb10` @
  `975f72da…` = **511.27 GB / 476.2 GiB** in 22 files — a 10,470,346 B metadata-only primary
  `deepseek-v41-flash-1017-tp4-c16-dspark5.safetensors`, 12 weight shards (eight of 58.6–63.9 GB,
  four of ~5.4 GB), and five graph/support shards (4 × ~490 MB + 6.4 MB); every shard is under 64 GB
  and named by its sha256. Repo `usedStorage` **1,845,031,706,350 B** (all three revisions' LFS).
  **No `config.json` at any branch**, so there is no `quantization_config` to read: the scheme is
  stated only on the card — "MXFP4 expert weights retain losslessly compressed CSF scales, attention
  uses BF16 arithmetic, and KV storage uses FP8 compression" (frontmatter tags `flare`, `mxfp4`,
  `csf`, `gb10`, `tensor-parallel`). "FLARE" is the engine's and the format's product name, never
  expanded on either card, and **not a quantization scheme**. It does **not** follow the
  `local-inference-lab` labquant conventions this registry already consumes:
  `local-inference-lab/Qwen3.8-Flash-Next-NVFP4` (pinned by
  `recipes/qwen4/qwen3.8-flash-next-nvfp4-labquant-sglang.yaml`) is an ordinary sharded HF checkpoint
  — `model-000NN-of-00041.safetensors` + a `config.json` carrying
  `quantization_config.quant_method: modelopt` (plus `hf_quant_config.json`, `HYBRID.json`,
  `export-manifest.json`, `chat_template.jinja`) — loaded by SGLang as `quantization:
  modelopt_mixed` behind four config-patching mods. FLARE ships no HF checkpoint, no shard index and
  no template at any revision: weights plus compiled kernels plus captured execution graphs.*)
  *(why it matters:* `gb10` is the first artifact this lane has seen whose target *is* four Sparks —
  "A signed Flare package for four DGX Sparks", TP4, 16 concurrent requests, DSpark with up to five
  adaptive draft tokens, 4096-token prefill chunks, a 1,048,576-token per-request context, and Engram
  read from disk with `--embedding-table-cache-size 1GiB` plus ~1.4 GiB resident scales per host —
  the lane's own shape. The loader answer is still no for both shipped arms, in the card's words:
  "It requires the Flare image below; Transformers, vLLM, SGLang and llama.cpp cannot load this
  runtime format." Neither `recipes/ds4/README.md:25` (SGLang) nor `:349` (TensorFold EXL3) reads it,
  and `gb10` serves from `flare-inference` installed by `apt` on each host plus `flare orbit` pairing
  over RoCE (TCP 29900 host-to-host, 29800 on the controller) — a `runtime:` sparkrun does not ship
  (it has `sglang`, `vllm_ray`, `vllm_distributed`, `trtllm`, `atlas`, `modular_max`, `tokenary`,
  `llama_cpp`). Node arithmetic: 511.27 GB / 476.2 GiB against 4 × 128 GB = 512 GB nominal (476.8
  GiB) leaves ~0.6 GiB before KV, runtime reserve and the 1 GiB row cache, so the vendor's c16 and
  1M-context claims rest on KV headroom this cluster has not measured — the card itself defers to
  "subject to available KV memory", and the gb202 figure (21,160,832 logical KV tokens on 4 × 96 GB)
  does not transfer. Disk is the easy part: "over 515 GB free on the first Spark" plus each rank's
  data on the peers.*)
  *(blockers/unknowns:* engine acquisition — a third-party APT repo plus a per-host
  `flare agent install --accept-first` service on four nodes is an owner supply-chain decision, not a
  bench step; the package is version-locked to the runtime (`83d582e2-amd64` on the discrete-GPU
  package, and `gb10` names no architecture; nothing verifies it on GB10's arm64 + CUDA 13); no
  accuracy evaluation exists ("Comprehensive model-accuracy evaluation has not been run"), so nothing
  can be claimed against the lane's 36/37 house baseline; per-rank weight residency and KV headroom
  at c16 are unmeasured; the trust-store acceptance is interactive on first run, which a headless
  launch must solve.*) *(effort: research only — owner decisions first.)*

## glm5
GLM 5.3
*(No open item — the ≥1M probe and four-way 1M concurrency were **dropped unrun**, not deferred, by the
2026-10-18 19:15 policy above (they need `.30`–`.33`). The arm's measured envelope is the 100,559-token
TTFT of 258.4 s on the 2026-10-18 boot; the record is archived in `../attic/DONE.md`.)*

## ornith
Ornith 1.5
- [ ] **Name the intermittent 1M prefill serve exit on the YaRN arm (depth 90 % now passes)** — at 1M the serve
  process exits mid-prefill (43.7 % in, 551,863 tokens pending at 592 t/s, `RemoteDisconnected` at
  398 s of a 3,000 s budget) with host OOM, driver fault and client timeout all excluded; the
  traceback dies with the container because `--no-rm` does not preserve it (`auto_remove: false` in
  the job file, yet dockerd task-deleted it). Needs the serve log **streamed** to the host for the
  whole request plus the exit code / `OOMKilled`, or a `docker events` capture
  (`recipes/ornith/README.md` §"The YaRN 1M arm"; `attic/ornith/AGENTS.md` §9.1). *(effort: short)*
  *(progress 2026-10-19 — **the rung passed, so the exit is intermittent**: the third attempt (full
  pool 1,205,530, no co-tenant) retrieved the key at depth 90 % with 97.8 % fill in 1,891 s, crossing
  the same 11 GiB-available regime that killed the two 2026-10-18 boots. The gate is now 6/6 on one
  boot; the mechanism of the two exits is still unnamed, so this item stays open for the next failing
  boot. The capture that actually holds the traceback is `docker exec <c> tail -F
  /tmp/sparkrun_serve.log` streamed to a host file — NOT `docker logs -f`, which on this arm yields
  only the 523-byte CUDA banner — while `docker events --filter event=die` preserves the exit code
  past the task-delete. Receipt `~/benchmarks/ornith-yarn-d90-20261019/`.)*
  *(progress 2026-10-20 — **the d90 rung passed again with the capture armed, so there is still no
  failure to name.** One needle at depth 90 % of a 1,000,000-token request retrieved the key (1/1),
  prompt counted **977,975 tokens**, **1,885.7 s**; the serve answered `/v1/models` 200 afterwards and
  the container was healthy 34 min after boot. The register's capture ran for the whole request —
  `docker exec <c> tail -F /tmp/sparkrun_serve.log` streamed to `serve-stream.log` (**119,827 B** kept)
  and `docker events --filter event=die` into `docker-events.log` (**empty**) — which is the null result
  this item owes: nothing died, nothing was written. That is **2 of 2 d90 passes since the two
  2026-10-18 exits**, so the item stays open for the next failing boot, not for a retry. Receipt
  `~/benchmarks/ornith-yarn-d90-20261020/`; paragraph in `recipes/ornith/README.md` §The YaRN 1M arm.)*
- [x] **Re-verify the 35B serve line on the SGLang 0.5.18→0.5.21 bump** — a named perf lead (DFlash-reranker + GDN fusion wins) that was recorded as breaking the lane (blocker text at `attic/ornith/AGENTS.md:1203-1206`; the `:883-886` pointer carried here was stale). *(effort: medium)* *(Owner decision 2026-10-19: **approved** — test the bump; it changes the engine
image/digest, so validate the other ornith arms on the new digest before shipping.)*
  *(progress 2026-10-21 — **the recorded blocker is refuted at the target tag: the bump is testable, not blocked.** "The Mamba/SWA radix-cache args were removed upstream" is false. `mamba_radix_cache_strategy` and `mamba_full_memory_ratio` are still declared fields at v0.5.21 (`python/sglang/srt/arg_groups/fields/exec_.py:450-457`, `arg_groups/fields/schedule.py:214-218`), still register as `--mamba-radix-cache-strategy` / `--mamba-full-memory-ratio` (`arg_groups/arg_utils.py:290`), and `extra_buffer_lazy` remains a legal choice with the DFLASH lazy-verify hook wired (`arg_groups/mamba_hook.py:113-120`). sglang#40313 (merged 2026-09-20, shipped in v0.5.21) removed the `MambaRadixCache` and `SWARadixCache` *classes*, which no recipe or mod imports; the LIKELY origin of the misread is the v0.5.20 move of every field declaration out of `server_args.py` into `arg_groups/fields/`, so a grep of the old file finds nothing. Of the two named wins only one reaches this lane: the DFlash reranker (LiLiCorr, sglang#37462) engages only for a draft checkpoint carrying `lilicorr_*` geometry, which the `jzinno` DFlash2 and first-party DFlash heads do not, while the GDN QKV materialization removal (sglang#33778, also v0.5.21) applies on the Triton linear-attention verify path these arms resolve to. **Target:** `lmsysorg/sglang:v0.5.21@sha256:b1259f3e…` (tag 2026-10-01, release 2026-10-02), a multi-arch index with a native `linux/arm64` manifest (`sha256:1f176b3a…`, 14.8 GB); the current pin is a 2026-09-08 arm64 nightly whose serve log reports `0.0.0.dev1+g20ca564bf`. **The change:** one-line digest edits in the three SGLang arms (`tests/test_ornith_recipes.py` asserts a shared digest-pinned container, not a literal). **Pass bar per arm:** contract ok, house **37/37**, needle **3/3** at 32k / 131k / 262k, and the on-file ladder bands — 35B C1 100.8-101.8 · C2 153.1-158.2 · C5 217.4-220.4 · C10 244.2-249.9 t/s at d0, 9B C1 52-59 · C2 101.1 · C5 159.0 · C10 148.9 — with the YaRN arm gated on its needle rungs (262k / 512k / 768k 3/3, 1M at depths 10/50/90 % each at ≥95 % fill, d90 retry rule declared before the run) and on reading its `max_total_num_tokens` grant first. **Estimated 3.5-5.5 h** against this item's 6-9 h; BFCL is out of the bar and would add ~2.5 h per arm. Evidence table with commit-level citations in `attic/ornith/AGENTS.md` §"Engine-bump adjudication — SGLang 0.5.18 → 0.5.21 (2026-10-21, repo-side)"; operator plan, staged diff, and pass-bar table in `recipes/ornith/README.md` §"Engine bump to SGLang 0.5.21". Note for the run: `sparkrun` is not on PATH on the local workstation — validate and render on the head node.)*
  *(CLOSED 2026-10-21 — **all three arms validated on the new digest; the bump ships.** The pins are
  applied to all three SGLang ornith recipes
  (`lmsysorg/sglang:v0.5.21@sha256:b1259f3e…`, a multi-arch index with a native `linux/arm64`
  manifest; the container labels record upstream build commit `e00930c5…`), `tests/test_ornith_recipes`
  passes 29/29, and the pass ran on a free `.34`/`.35` pair in ~4 h against this item's 6-9 h. 35B on
  `.34`: contract ok, house **37/37**, needle **3/3** at 32k/131k/262k, ladder d0 n=5 **C1 96.5 / C2
  148.3 / C5 213.9 / C10 244.1** — every cell inside the on-file band's σ; accept len 2.52-2.64. 9B on
  `.35`: house **37/37**, needle **3/3** ×3; its ladder read C2 89.6 (11.4 % low), then a ladder-only
  re-boot **on `.34`** — the node the on-file band was measured on — read **C1 60.6 / C2 97.8 / C5
  156.1 / C10 147.8**, so the dip was a cross-node artifact, not an engine shift. YaRN on `.34`:
  pool 1,192,993 tokens, needle gate **6/6 rungs PASS** (1M depths 10/50/90 at fills 97.74/97.75/97.80
  %), **the d90 intermittent did not reproduce — first-attempt pass, retry rule unused, no die event**
  (streamed serve-log capture + `docker events` armed throughout; 4 of 4 d90 passes now, on two
  builds). Of the two named wins, LiLiCorr (#37462) is unreachable for this lane (no `lilicorr_*`
  draft exists) and the GDN target-verify change (#33778) produced **no measured gain** — the ladders
  read at or slightly below the prior bands; the bump's value is escaping the dead-end 2026-09-08
  nightly plus 0.5.21's fixes. Receipts `~/benchmarks/ornith-0.5.21-bump-20261021/`; the full
  evidence table is `attic/ornith/AGENTS.md` §"Engine-bump adjudication — SGLang 0.5.18 → 0.5.21
  (2026-10-21, repo-side)", the operator summary is `recipes/ornith/README.md` §"Engine bump to
  SGLang 0.5.21". Ops learned: render/launch from `/<home-dir>/src/sparkrun-recipe-registry`, not
  `/<home-dir>/development` (the lane-local mod resolves relative to the symlink and fails); stop with
  `sparkrun stop <cluster-id> -H <node>` and `docker cp` the serve log first — `stop --all` deleted
  the `--no-rm` 9B container on `.35` and its serve log.)*
- [x] **Re-pin all six SGLang arms to `v0.5.22` and re-validate each on the new digest** — one patch past the ornith lane's 0.5.21, two past the ifm lane's 0.5.20, so the ifm UNO arms put the FA4 anchor patch on trial as well. *(effort: medium)*
  *(CLOSED 2026-10-22 — **all six arms booted and held their bars on the new digest; the pins ship**
  (commit `20da8f2`). Pin: `lmsysorg/sglang:v0.5.22@sha256:e3a4f06001a29542fc4a8638536d9ffc5eb9c9942b08603c09b19a56eae4a1ae`
  — a published multi-arch index (`docker buildx imagetools inspect`, not a local image id) with a
  native `linux/arm64` child `06441be3…`; `v0.5.22-cu130` and `latest` resolve to the same index. The
  three ifm arms are pinned to the `-cu130` spelling of that digest. Runtime moved to torch
  `2.14.1+cu130`, python `3.12.15`, cuDNN `9.14.0.64`, `nccl_torch 2.30.7`. **OSV: 0 vulns** for PyPI
  `sglang` 0.5.22. Six sequential single-node serves on `.35` (receipts
  `~/benchmarks/sglang-0522-20261022/`), `TTR / pool / house`: 35B DFlash2 **238 s / 1,133,804 /
  37/37** (needle 3/3 at 32k/131k/262k, mamba 614, mrr 48); 9B DFlash **251 s / 1,531,959 / 37/37**
  (mamba 273); YaRN 1M **129 s / 1,187,727** with `max_model_len` 1000000 confirmed in `/v1/models`
  (mamba 1293, 11.11 GB free); 0.9B **94 s / 1,764,610 / 32/37**; 0.9B-UNO **94 s / 1,690,881 /
  33/37**; 7B-FP8-UNO **240 s / 574,698 / 36/37**. The ifm scores reproduce their on-file baselines
  **item for item** (`fmt-2`, `needle-1` / `hard-rev`, `trick-1`, `trick-2`) — 37/37 is the ornith
  lane's ceiling, not this one's, so the gate was no regression against each arm's own recorded score.
  The FA4+UNO mod still applies: its probe logged `anchor count = 1` on 0.5.22 and the arms served
  `--attention-backend fa4` + `UNO`, which stock 0.5.22 refuses at argument validation. **Arm A's
  ladder, n=5 (the recorded reading — the `runs=3` triage read 94.3/146.0/207.1/247.7): C1 97.6 ± 8.8
  / C2 152.1 ± 7.4 / C5 228.7 ± 16.0 / C10 242.3 ± 5.0**, every cell inside the on-file band's σ
  (100.8-101.8 / 153.1-158.2 / 217.4-220.4 / 244.2-249.9) with the direction stated: C1 −3.2 %,
  C2 −0.7 %, C5 +3.8 %, C10 −0.8 %; against the 0.5.21 n=5 readings +1.1 / +2.6 / +6.9 / −0.7 %. Zero
  `WARNING`/`ERROR` lines in all six serve logs, same as the 0.5.20/0.5.21 boots. Gate: 894 tests OK
  (2 skipped); `sparkrun recipe validate` clean on all six (suggestions only). Lane records:
  `recipes/ornith/README.md` §"Engine bump to SGLang 0.5.22", `recipes/ifm/README.md` §"Engine bump to
  SGLang 0.5.22", evidence tables `attic/ornith/AGENTS.md` + `attic/ifm/AGENTS.md` §"Engine-bump
  adjudication". **Registry trap found and recorded:** `@littlecedar/<name>` resolves the *published*
  registry, so a bump boot through it silently served the previous pin (it booted v0.5.21 while the
  worktree was at v0.5.22) — boot by recipe **file path**, and `grep -q <new digest> <recipe> || exit 3`
  before each boot after a shared-tree checkout. **Not done, deliberately:** no ladder re-take for arms
  B-F (only the `container:` line changed, the recorded ladders stand), no 1M needle on the YaRN arm
  (the pass's bar was boot + grant; the 6-rung ladder is ~3.5 h), and 0.9B / 0.9B-UNO were run as
  **probes** of the lane baseline and the FA4 mod rather than as candidates.)*
  *(follow-up 2026-10-22 — the only verification this pass left unspent: a **1M needle on the YaRN arm
  at the 0.5.22 pin**, ~3.5 h, worth doing only if a long-context need appears; the 0.5.21 pass's 6/6
  rungs and its non-reproducing d90 exit are the standing evidence. Re-take it before quoting a 1M
  quality claim on 0.5.22.)*

## qwen3
Qwen 3.x
*(all items completed — archived in `../attic/DONE.md`)*

## qwen4
Qwen 4.x (and 3.8 Flash Next)
- [ ] **Clear the remaining qwen4 measurement backlog** — TP=4 (W6) re-boot after the `port_timeout_s` fix; the W12 cross-runtime vLLM same-checkpoint bench; the `--fp4-gemm-backend` A/B (the shipped `flashinfer_cutlass` was inherited without justification); `--enable-int8-mamba-checkpoint`; and the bs>1 cost of `--cuda-graph-backend-prefill disabled` (`attic/qwen4/AGENTS.md` §10.1). *(effort: medium)*
  *(2026-10-18: **none of this backlog ran** — the TP=2 block closed after one arm. Two facts to carry into the next window: the `--fp4-gemm-backend` A/B's first alternative arm is refused **before weights load** (`flashinfer_cudedsl` is listed in `--help` and in the error's own `choose from` set, yet argparse rejects the token verbatim — `~/benchmarks/qwen4-tp2-20261018/b2-cudedsl-refusal-arm.log`), so probe the accept-spelling first; and `--enable-linear-replayssm-spec` is now measured as a capacity lever (+11.5 % KV pool) whose remaining question is accuracy, not memory. TP=4 (W6) and the W12 cross-runtime vLLM bench need four/two nodes and are out of this session's scope.)*
  *(progress 2026-10-19 — the `--fp4-gemm-backend` probe's spelling question is answered: the engine accepts **`flashinfer_cutedsl`** (the 2026-10-18 `flashinfer_cudedsl` refusal was a typo). One boot with it: `load_weight` 485 s, house **37/37**, ladder 39.02 / 70.22 / 98.38 / 106.13 t/s against the control's 41.22 / 72.88 / 95.18 / 108.13 — mixed, at or below the 7-25 % inter-boot floor, so `flashinfer_cutlass` stays. Still unprobed: `--enable-int8-mamba-checkpoint` and the prefill-graph bs>1 cost. Receipt `~/benchmarks/qwen4-knobs-20261019/b1-cutedsl/REPORT.md`.)*
  *(progress 2026-10-19, later — **`--enable-int8-mamba-checkpoint` is a hard negative.** The default 224-slot pool needs 3.24 GB against 2.15 GB free at the shipped `gpu_memory_utilization: 0.80`; a 112-slot retry then dies with `ValueError: --enable-int8-mamba-checkpoint is incompatible with Qwen4-Exp PLE side states` (`memory_pool.py:1337`), so no size fits. Receipts `~/benchmarks/qwen4-knobs-20261019/b2-int8mamba/` and `b2b-int8mamba-112/`. The prefill-graph bs>1 cost is the only unprobed item left.)*
  *(progress 2026-10-19, last — **the prefill-graph flag is a no-op on this image.** Removing `--cuda-graph-backend-prefill disabled` leaves the default `disabled`, and an explicit `--cuda-graph-backend-prefill full` is accepted by args parsing then disabled by the engine for the EAGLE target ("Disable prefill CUDA graph for EAGLE target on tc_piecewise…"), with the multimodal rule as the companion reason. There is no bs>1 graph cost to recover. Three same-config boots span **8.6 % at C2** (67.1-72.9) and ≤4.6 % elsewhere — the inter-boot floor measured directly. Receipts `~/benchmarks/qwen4-knobs-20261019/b3-prefillgraph{,-full}/`. **All TP=2 knobs in this item are now answered**; it stays open only for TP=4 (W6) and the W12 cross-runtime bench — neither needs a node window:
per the 2026-10-19 directive they run against the **offsite API endpoint**, batched behind the one
owner switch. *(Owner decision 2026-10-19: that switch happens **after** the `.34`/`.35`
single-node tail closes, not now — the tail's estimates assume local boots through then.)* )*

  *(Owner decision 2026-10-22: keep the quartet on measurement duty — production stays stopped, the quartet
  serves the TP=4 queue. The offsite framing in the notes above is obsolete: there is no offsite endpoint,
  and the block runs locally on `.30`–`.33`.)*
  *(Owner decision 2026-10-22: run the full 20–28 h block — qwen4 W6 then W12, the ds4 TP=4 candidates,
  then the four-node suite legs; the block is resumable, so a pause is never a loss.)*

  *(progress 2026-10-22 01:55 ET — **TP=4 W6 is blocked at the engine, not the arm and not memory.** The boot loaded 41/41 shards on four ranks and died in `modelopt_quant.py:2624` (gated-activation MoE padding) on every rank, so TP=4 is an engine limit on this build. `e8d34fc`; `attic/qwen4/AGENTS.md`.)*
  *(progress 2026-10-22 03:44 ET — **the v0.5.22 follow-up closes it as a checkpoint limit, not a build defect.** One boot of the same arm on `lmsysorg/sglang:v0.5.22-cu130@sha256:e3a4f060…` (task `08acf79cd757a666_7afff0589a33`, quartet `.30`/`.31`/`.32`/`.33`) loaded 41 shards and asserted identically on **all four ranks**: `modelopt_quant.py:2942` (`:2624` on v0.5.20 — same message, `The intermediate size required padding, but padding is also implemented for gated activations`). So TP=4 stays closed for this NVFP4 export on both builds; do not re-try another nightly expecting a different answer. By-products: the relay reports the pinned image `already verified on all 4 receiver(s)` and the model distributes in 18.3 s from a node-local HF cache (the 2-5 MiB/s leg only exists cold). Receipt `~/benchmarks/tp4-20261022/w6-tp4-v0522/REPORT.md` §Verdict, MANIFEST row.)*
  *(progress 2026-10-22 03:31 ET — **W12 served**, so the cross-runtime column has its vLLM number. TP=2 on `.31`/`.32` (`6a76d7f90a79f4f4_6eb961eae222`), `RadixArk/Qwen3.8-Flash-Next-NVFP4` @ `7b71922`, b12x `cf5a2a53`, `max_model_len` 262144 accepted, KV 1,757,475 tokens (6.70x). Decode 42.8/51.2/40.1 t/s over three 256-token samples at temp 0 (median 42.8). Two engine-side traps recorded: the restored PLE mod cannot run in-container (`docker` absent) and is inert on this image anyway (its PLE layer is `qwen4_exp/nvidia`, b12x-aware, no `Fp8Config` guard — vLLM flags `VLLM_PLE_FP8_CHECKPOINT` as unknown), and `load_format: instanttensor` dies at `weight_utils.py:1679` because the image's instanttensor has no `_determine_buffer_size` (TP=1 never takes that path, TP>1 always does) — the arm now loads safetensors. Cold boot to first 200: ~19 min, mostly b12x autotune. Receipt `~/benchmarks/tp4-20261022/w12-vllm-b12x/REPORT.md`.)*

- [ ] **Finish the TP=4 block after W6** — W12's cross-runtime vLLM same-checkpoint bench first (its arm now pins the b12x build by digest, `cf5a2a53…`, the build the shipped TP=1 solo arm already pins), then the ds4 TP=4 upgrade candidates, then the four-node suite legs. The knapcio four-node arm already closed the two accuracy cells the 2026-10-18 suite left open: **ARC 93.5 % / GSM8K 97.5 %** (n=200 each, seed 1234). Evidence: `recipes/qwen4/README.md`, `recipes/ds4/README.md`, `attic/qwen4/AGENTS.md`, `~/benchmarks/tp4-20261018/`. *(effort: long; resumable — Owner decision 2026-10-22: run the full block, a pause is never a loss)*

- [ ] **Retire the restored highcon diagnostic** — `diag-qwen4-unplaced-scales` is mounted in the **highcon** labquant arm only, as insurance now that the shared-expert scale blocker is explained (the rename mod fixes it, and the diagnostic changes no control flow). The `demote-labquant-narrow-mxfp8-to-bf16` `EXTRA_LEAVES` knob is **not shipping**: it was removed 2026-10-19 once its only stated purpose — the QSA-prefill CUDA-graph crash — was falsified, machinery deleted rather than shipped empty (`recipes/qwen4/mods/demote-labquant-narrow-mxfp8-to-bf16/README.md` §2; `mad-science/QWEN4-DIAGNOSTICS.md`; `attic/qwen4/AGENTS.md` §10.1). Only open work: the highcon boot that retires the diagnostic. *(effort: medium)*
  *(Owner decision 2026-10-18 [#40]: chase both explanations — root-cause the shared-expert scale blocker and the QSA-prefill crash rather than declaring the workarounds permanent.)*
  *(**Both are root-caused 2026-10-19** — `mad-science/QWEN4-DIAGNOSTICS.md` carries the mechanism
  with `file.py:line`. The shared-expert blocker is the checkpoint's `.weight_scale` suffix vs the
  engine's `.weight_scale_inv` registration plus gate/up stacking; the rename mod fixes it and the diag
  is now insurance, not a workaround. The QSA-prefill crash is `get_prefill_mqa_inputs`' host sync and
  data-dependent buffer shape during capture; `EXTRA_LEAVES` is **falsified** (the demoted-projection
  boot crashed identically) and the path is unreachable today because the engine disables prefill
  graphs for this multimodal checkpoint. Remaining work shrank to: boot `zz-labq-no-diag` (retire the
  diag control) and delete `EXTRA_LEAVES` (code + docs, no boot). **Correction 2026-10-21: both of
  those are done** — the balanced probe booted clean (next bullet) and `EXTRA_LEAVES` was removed
  2026-10-19, machinery deleted rather than shipped empty (`recipes/qwen4/mods/demote-labquant-narrow-mxfp8-to-bf16/README.md`
  §2; `run.sh` says the same at the floor test). What is left of this item is one boot: the **highcon**
  arm, where the diagnostic is now restored and re-mounted, retiring it only if that boot is clean.)*
  *(progress 2026-10-20 — **`zz-labq-no-diag` booted clean, so the diag control can be retired.** TP=2 on
  the `.34`/`.35` pair (job `1895030211ea0500_3510a5e0d37d`), ready at `/v1/models` 200 in **≈670 s**
  from launch (mods + a 6 m 37 s sharded load), a `/v1/chat/completions` 200, and the house battery
  **37/37** (easy 19/19, hard 18/18). The serve log's only `_scale` activity is the *other* mods' benign
  `[remap] …weight_scale -> …weight_scale_inv` lines — **no `unplaced`/`AssertionError`** — so the assert
  the diagnostic was insuring against does not fire without it. Receipt
  `~/benchmarks/qwen4-nodiag-20261020/` (`boot.log`, `house.log`, `house.json`). **Scope correction
  (same hour):** the first pass deleted the mod outright and stripped it from both labquant recipes; the
  probe proves only the **balanced** config, so the mod is restored and re-mounted in **highcon only**,
  with the recipe comment naming the pending boot. The balanced arm stays diag-free (probe = its own
  receipt). **What the mod does, read from its own README/run.sh:** it is logging-only — it inserts a
  `_log.error(...)` statement as the first branch of the `_scale` check and changes no control flow (the
  assert still fires; it deliberately does not relax it), plus it reowns the runtime cache because
  importing sglang as root triggers flashinfer's JIT. So keeping it in highcon costs one anchored patch
  and a cache reown, no engine behaviour — which is why it stays as insurance rather than as a
  workaround. The item stays open until the **highcon arm boots clean without it**; that boot is the
  queued retirer.)*
  *(**CLOSED 2026-10-21 — the highcon arm booted clean without it, and the mod is retired.** The
  control boot ran the mod with its payload never firing (`[diag] UNPLACED _scale` = 0 on both ranks)
  and every bs-sweep cell inside 3.4 % of its control — **86.8 / 87.5 / 89.5 / 75.4 t/s** at
  k=8/12/16/24 against 84.9 / 89.1 / 89.1 / 72.9, TTR **9.6 min** (`scheduler_e2e=571.22`),
  admission unclamped (`max_total_num_tokens=1587072`, `max_running_requests=32`, mamba 128) — so the
  restore moved nothing and the mod had no work left. It then came out of the recipe's `mods:` chain
  and the two "pending boot" comment lines, moved to `attic/qwen4/mods/diag-qwen4-unplaced-scales/`
  (directory and README kept as provenance), and the recipe was re-booted diag-free to prove the
  edit: `/v1/models` 200 at 262144, `max_total_num_tokens=1597376`, no `AssertionError`, and
  `_diag_unplaced_scales` **absent** from the patched engine file. The `_scale` failure mode it
  watched for is preserved in `recipes/qwen4/README.md` rather than lost with the comment lines.
  Receipts `~/benchmarks/qwen4-highcon-20261021/{REPORT.md,serve-*.log.gz}`.)*

## ifm
IFM K2-Horizon
## embed
Any embed model
*(all items completed — archived in `../attic/DONE.md`)*

## rerank
Any rerank model
*(all items completed — archived in `../attic/DONE.md`)*
  *(closed sub-item 2026-10-18 — the shipped 8B reranker was **unbootable** and is fixed: `Qwen/Qwen3-VL-Reranker-8B` declares `tie_word_embeddings` only at the top level while vLLM's `seq_cls_model_loader` reads `config.text_config.tie_word_embeddings`, so engine init died with `AttributeError`; the recipe now passes a nested `"text_config": {"tie_word_embeddings": false}` in `--hf-overrides`. Boots as shipped with no overrides (health 200 at 280 s) and its c1 cell is unchanged: **17.94 vs 18.03 u/s**. Receipt `~/benchmarks/embed-fix-20261018/`; full record in `../attic/DONE.md`.)*

## decision
Any decision model
- [ ] **Build the named decision candidates** — `Decision-2.0-Nox-4B` (best-scoring 4B, never booted), `GLiNER2.5-Decide`, and `JEV-27B` (`attic/decision/DECISION-MODELS-RESEARCH.md`). *(effort: medium)*
  *(progress 2026-10-18 — `laya` is built, scored and ladded; the item stays open for four (`Nox-4B`, `GLiNER2.5-Decide`, `JEV-27B`, the Sol-2B GGUF path). **Decision accuracy 36.1 % (723/2000)**, KL 0.576 / Brier 0.316 / ECE 0.175, p50 4.29 s per request on 5 A725 cores (CPU-only, 1.6 GiB of the unified pool) — the vendor's near-chance expectation (0.362 zero-shot against a 0.461 majority baseline; the card's 0.766 belongs to the separate `laya-typed-decisions` checkpoint). The shipped recipe did not launch (`serve command does not identify the validated model`: the snapshot path reached the guard as `<path>)` inside a `printf` substitution); it now exports `LAYA_MODEL_PATH='{model}'` and builds the JSON from that variable, with a guard test (`test_model_path_is_a_whole_token_or_key_value`). Ladder **c1 0.449 req/s / 2.25 decisions/s**, c2 0.447 / 2.24 at doubled p50 — `/v1/systemone` is serial and does not batch. Receipt `~/benchmarks/decision-arms-20261018/`. `kev-0.8b` and `d3-edge` were booted in the next window — results below.)*
  *(2026-10-19 — the two remaining builds are **blocked with evidence, not unbuilt by neglect**:
  **GLiNER2.5-Decide** (`fastino/GLiNER2.5-Decide`, open) has no serving contract — the `gliner2`
  wheel has no entry point or server module, the repo ships no HTTP surface, and the card's only API is
  Fastino's hosted endpoint; its 512-position encoder also cannot express the lane instrument's
  ~870-token `/v1/systemone` cases, so a hand-written server would invent the endpoint and the scoring
  semantics. **Sol-2B GGUF** exists (`vllm-sr/Decision-2.0-Sol-2B-GGUF`, Q8_0) but needs the fork
  `Xunzhuo/llama.cpp` @ `c9f5974` (`decision2-gguf`, 959 commits ahead of the registered tier's
  `b2e5e9b`; never merged — upstream merged a different design instead). Three builds fail identically:
  `wrong number of tensors; expected 330, got 320`. Unblock is image-side: build the fork into a
  digest-pinned arm64 image, or have the vendor re-convert to upstream's `vllm-decision2` arch.
  *(Owner decision 2026-10-19: **build the image on `.34` or `.35`**, not the local workstation — so
  it is a node-window step: fork build into a digest-pinned arm64 image, then the Sol-2B boot and the
  decision-instrument score.)*
  *(progress 2026-10-20 — **the image is built, the GGUF loads, and the arm scores the CPU arm's
  number on GPU.** `Xunzhuo/llama.cpp@c9f597487` cloned on `.34` and built there into
  `littlecedar/dgx-spark-llama-cpp-decision2:c9f5974` (id `sha256:1bb250bf…`, 2.68 GB, arm64) on the
  registry's CUDA 13.0.1 devel/runtime digests with `-DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=
  121a-real`; two builds, 184 s and 134 s, the second one keeping `.git` so `llama-server --version`
  reports `0.6.0-dev (build 11508, commit c9f597487)` (the first printed `commit unknown` — provenance
  is worth the rebuild). The `expected 330, got 320` blocker was **the registered engine tier, not the
  file**: on the fork image the Q8_0 pack loads in 1.6 s and the server logs `decision model type:
  decision2`. `tool-eval-bench@2.8.0 --decision-bench-only`: **55.0 % (1101/2000), ★★, KL 0.351,
  Brier 0.189, ECE 0.054, 0 errors, 79.9 s** — the CPU `vllm-srun` arm's 55.0 % (1100/2000) within one
  decision — at p50 195.3 ms/case against its 15.0 s. Ladder `tools/decision-ladder.py --runs 5`:
  **c1 5.228 / c2 5.439 / c5 5.422 / c10 5.413 req/s** (26.14 / 27.20 / 27.11 / 27.06 decisions/s) with
  p50 193.0 → 375.8 → 955.0 → 1941.3 ms — flat throughput, latency scaling with concurrency, because the
  vendor's run line is `-np 1`. Receipt `~/benchmarks/sol2b-20261020/`; rows in
  `recipes/decision/README.md` §`sol-2b-gguf-llamacpp`. **Still open:** the image has no `RepoDigest`
  (local-only), so shipping a recipe that pins a digest needs a registry push first.)*
  *(boot proof 2026-10-20 — **the recipe is the verified artifact, not just the image.** `sparkrun run`
  pulled the published digest, came up in **26.8 s** (port open 0.7 s), served
  `vllm-sr/Decision-2.0-Sol-2B-Q8_0`, and the same instrument scored **55.0 % (1101/2000)**, KL 0.351,
  Brier 0.189, ECE 0.054 over 80.5 s — decision-for-decision the manual boot. Receipt
  `~/benchmarks/sol2b-recipe-20261020/`; lane row now BOOT-VERIFIED.)*
  *(progress 2026-10-20, later — **shipped: the image is published and the recipe pins its digest.**
  `docker save | docker load` onto the head (the only host holding the `docker.io` credential) then
  `docker push littlecedar/dgx-spark-llama-cpp-decision2:c9f5974` gave
  **`@sha256:b4808c9a6ef81775f7e05c91670f1f8853aa3d97c14f47cce3f21627cd3ba1f3`**; the head's loaded id is
  the node's build id (`sha256:1bb250bf…`), so the digest pins the measured content. Landed
  `recipes/decision/Dockerfile.llama-cpp-decision2` (fork pin, the exact cmake line with
  `-DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=121a-real`, the `cuobjdump` sm_121 gate, `.git` kept so
  `--version` reports the commit, published digest in the header) and
  `recipes/decision/sol-2b-decision2-gguf-llamacpp.yaml` (vendored run line, `readiness.inference: false`,
  `{served_model_name}` not `{model}`, digest-pinned), plus the root index row (C1–C10 **5.2 / 5.4 / 5.4 /
  5.4 req/s**). The recipe validates plain and renders the vendor line; **the boot through
  `sparkrun run` landed the same day** (ready in 26.8 s, the same **55.0 % (1101/2000)** in 80.5 s;
  the score is the recipe's, the ladder still the manual boot's). Manual-boot
  trap recorded in the lane doc: the HF cache's `snapshots/…gguf` is a two-level symlink into `blobs/`, so
  mounting the snapshot dir alone fails with `failed to open GGUF file`.)* )*

  *(closed sub-item 2026-10-18 — `kev-0.8b` is built and measured; `d3-edge` is closed as not bootable here. Receipt `~/benchmarks/decision-arms2-20261018/` (`REPORT.md`, `logs/`, `kev-evidence/`, `d3-evidence/`); lane record in `recipes/decision/README.md` §kev-0.8b-decision-serve and §d3-edge-decision-vllm-srun. **kev: Decision accuracy 46.0 % (919/2000)**, ★, KL 0.349 / Brier 0.196 / ECE 0.046, 0 decision errors, p50 5403.4 ms per request; per type noul 52.5 / choice 50.5 / score 37.6, per workflow customer_service 55.0 → agent_trace_observability 34.6; ladder c1 0.234 req/s / 1.17 decisions/s, c2 0.235 / 1.18 at doubled p50 — +9.9 pts over laya on the same 400 cases, at 1.9× laya's per-case latency. The serve is healthy but **the launch gate can never pass**: sparkrun's startup probe requires HTTP 200 on `/health` (`startup_probe.py:246-265`) and kev has no such route (404 forever), `readiness.inference: false` skips only the inference stage, and `health_path` is runtime-owned (`_vllm_common.py:24` → `/health`), so the score was taken against the detached container. **d3-edge: not booted** — (1) as shipped `/health` 503 `OfflineModeIsEnabled`, because sparkrun stages with `HF_HUB_OFFLINE=1` while the decision3 loader resolves through the Hub tree API even with `--cache-dir` pointed at the staged snapshot; (2) with `-e HF_HUB_OFFLINE=0` it loads 594,582,720 params then fails the golden gate: `GoldenResult(status='failed', checked=3, matched=1, reference='cpu')`, deltas confidence 3.70e-3 / P0 2.15e-3 / P1 2.22e-3 / score 2.09e-3 / noul 3.83e-3 / domain 8.8e-5 against `CPU_TOLERANCE = 1e-3`, identical across 5 attempts — so no score and no ladder. Both fixes are image-side (an aarch64-recorded CPU reference or a per-ISA tolerance; an offline-capable decision3 loader), not recipe edits.)*
  *(2026-10-22 — **the head revision was probed and reverted; the pin stays at `18d61df7`.** Both pin
  sites (`model_revision:` line 3 and the literal `--revision=` in `command:` line 50) were moved to
  `c454ee39…`, booted twice — `.31` as shipped, `.35` with `-e HF_HUB_OFFLINE=0` — and reverted. At the
  new pin `/health` answers 503 `{"status":"failed","reason":"VerificationError: golden answers differ
  from the reference"}` with `/v1/models` reporting `ready:false` and golden
  `{checked:3, matched:1, reference:"cpu"}` — **the same 3-checked / 1-matched result the lane README
  recorded at the old pin on 2026-10-18**, so the aarch64-vs-x86 golden-reference divergence is
  revision-independent and the bump is not a regression either way. No `/v1/systemone` round-trip exists
  in either boot (`503 not_ready`). **Label correction:** `18d61df7` is the `d3-edge v3.1.0` release
  commit (2026-10-11) and `c454ee39` is "Add Typed Decisions benchmark eval results (#2)" (2026-10-17),
  a post-release card/eval commit — so the earlier "vendor runtime moved" framing was wrong. The ten
  commits do touch `d3_format.py`, `d3_runtime.py`, `d3_server.py`, `requirements.txt` and
  `MODEL_MANIFEST.json`, and the repo's two safetensors (1,215.7 MB) are byte-identical across both
  revisions. Receipt `~/benchmarks/decision-d3-repin-20261022/`; lane record
  `recipes/decision/README.md` §`d3-edge-decision-vllm-srun`; commit `df2c259`.)*

## explore
Any model with reasoning and tool-calling capabilities
- [ ] **Build the top-ranked unbuilt reasoning candidates** — `Muse-Glimmer-30B` (rank 2; blocked on unmerged vLLM PR #51655); license/availability-blocked: MiniMax-M3 (non-commercial), MiMo-V2.6-Flash-RL (no quant), Inkling-Small (unpublished active params); plus `IFM/K2-Horizon-375B-A23B` (`mad-science/EXPLORE-CANDIDATES.md:16-57`; `attic/explore/EXPLORE-MODELS-RESEARCH.md`). *(Mistral-Small-4 is **not** unbuilt: it was measured-rejected at 28.9 t/s C1 and archived by the 2026-10-19 sweep — `attic/explore/ARMS-MANIFEST.md`.)* *(effort: long)*
  *(recheck 2026-10-21 on both names blocked on time-sensitive facts — **`Muse-Glimmer-30B` is UNBLOCKED and cheaper than the dossier assumed; `MiMo-V2.6-Flash-RL` changed its blocking reason but stays out of the 1-node brief.** Neither is authored; the owner queues it.*
  *Muse Glimmer: vLLM PR #51655 merged 2026-08-14 (merge commit `6adad087`), and support landed in **v0.28.0** — `registry.py:186` `MuseGlimmerForCausalLM`, `:534` the conditional-generation alias, and `:635-636` both the drafter and the `DFlash{MuseGlimmerAssistantModel}` key the `EAGLEConfig` rewrite needs. A GB10 (`sm_121`) datapoint in the PR thread boots it with `--max-num-batched-tokens 4096` and `TRITON_ATTN`. The cheaper route needs **no new image**: the lane's pinned **SGLang v0.5.21** already ships `srt/models/muse_glimmer.py`, its configs, processor, and function-call detector, plus `test/registered/spec/dflash/test_muse_glimmer_dflash_assistant_gsm8k.py`, and the third-party GB10 run used that shape (11.16 → 23.74 t/s single-stream with the drafter). Size arithmetic from Hub `blobs=true` sums, not estimates: `meta-models/Muse-Glimmer-30B` bf16 **55.5 GiB** (`7af58019`), `RadixArk/Muse-Glimmer-NVFP4` **18.3 GiB** (`1416629950`) — the dossier's "NVFP4 24.7 GB" is 34 % high — and the drafter `meta-models/Muse-Glimmer-30B-assistant` **4.8 GiB** (`c676cce9`), so 23.1 GiB of weights with ~95 GiB left on one node. Geometry from `text_config`: 52 layers, 2 KV heads × 128 head_dim = 1 KiB per layer per token at bf16, and 13 of the 52 layers are full-attention (the other 39 sliding at 2048), so ~13 KiB/token ⇒ **~50 concurrent 131k sequences** in that headroom. Apache-2.0, 128k window, tool calling via `--tool-call-parser muse_glimmer` plus `--reasoning-parser muse_glimmer` (the latter forces `skip_special_tokens=False`).*
  *MiMo-V2.6-Flash-RL: "no quant" is stale — the base repo already ships at **165.5 GiB** for 310.8B params (≈4.6 bit per param, `fp8`/`8-bit` tags, 90 files), and the gated derivative `drowzeys/MiMo-V2.6-Flash-RL-Abliterated` (2026-09-23, `fp8`/`mxfp4`, tagged `dgx-spark`/`gb10`) is byte-identical at **165.6 GiB**. A quant exists; it is a **2-node** artifact either way, so the 1-node brief still excludes it and nothing is queued.)*
  *(closed 2026-10-21 — **`Muse-Glimmer-30B` is booted, measured, and does not ship.** One Spark on the ornith lane's own `sglang:v0.5.21` digest, no fork: contract PASS including a populated-argument `tool_calls` reply (the lane's first native channel-format arm), needle **10/10 at 32,768 and 10/10 at 131,072**, but **house 36/37** (`hard-rev`, `nurkrpas`, deterministic 4/4, no truncation) and **C1 20.2 t/s** — the slowest single-node arm measured here, against Laguna-XS's 57.4 at the same 36/37. 37/37 is a tie-break, not a gate, so the arm loses on the speed axis rather than on the bar. The recipe was removed; the route, flags, KV pool (235,556 tokens at mem-fraction 0.38), acceptance (C1 mean 3.19) and ladder are in `attic/explore/AGENTS.md` §"Muse-Glimmer-30B NVFP4 + DFlash — boot-verified 2026-10-21", receipt `~/benchmarks/explore-muse-glimmer-20261021/`. Worth revisiting only against the **bf16 export** (55.5 GiB, still one node), which separates pack from checkpoint on both the reversal and the decode rate.)*
  *(closed 2026-10-21, late — **the bf16 control ran and the answer is the CHECKPOINT, not the pack.** `meta-models/Muse-Glimmer-30B` @ `7af58019` (59.58 GB) on `.35` with the same drafter, the same `sglang:v0.5.21` digest and the same flag line (only `mem_fraction_static` 0.38 → 0.80, because 59.6 GB of bf16 weights do not fit the pack's fraction) reproduces the miss **exactly**: house **36/37**, `hard-rev` → **`nurkrpas`**, same item, same string, easy 19/19. bf16 load proven by the engine's own line (`MuseGlimmerForConditionalGeneration`, `mem usage=52.21 GB`, snapshot `7af58019…`), not by a file existing. C1 **12.1 t/s** (prefill 1206.7, ttfr 1,700 ms), DFLASH accepted on bf16 at block size 5 with acceptance 2.27-4.47. So both exports of the same weights fail the same word deterministically: **the Muse Glimmer line closes for good and no repack is worth trying.** Note for anyone reading serve logs later: the `marlin as FP4 GEMM runner … on SM120` line is a model-name-keyed engine branch and prints on a bf16 load with zero FP4 tensors. Receipt `~/benchmarks/explore-muse-glitter-bf16-20261021/`; detail in `attic/explore/AGENTS.md` §"Muse-Glimmer-30B bf16 control".)*
  *(closed sub-item 2026-10-18 — **`Nemotron-3-Super-120B-A12B-NVFP4` is built and measured, and does not ship.** C1 **15.83 ± 0.19 t/s** @ d0 (15.91 ± 0.12 @ d8192, depth-free) is 45 % below the already-rejected Mistral-Small-4 (28.9) and 66 % below Kolibri-1 (47.3); batching does not close it (c2/c5/c10 25.52 / 26.94 / 30.60 = 1.93× for 10× concurrency). Quality is the lane's best — house **37/37**, ties ling and mellum GGUF — and it is the only measured single-node arm serving the full **262,144** window (KV pool 7,659,632 tokens, 29.22× concurrency), which is why it is archived rather than deleted. **Params corrected: 123.6B true total (112.74B 4-bit experts + 4.83B FP8 + 6.02B BF16) / ≈12.2B active (22/512 experts); the Hub's 67.2B counts packed U8 NVFP4 expert bytes (2 values/byte) as parameters.** The as-authored recipe cannot boot: `--swap-space 0` is unrecognized in vLLM 0.29.0 (hard abort, which under `readiness.inference: false` shows as a hang, not a failure), and `VLLM_NVFP4_GEMM_BACKEND` / `VLLM_USE_FLASHINFER_MOE_FP4` are also unknown to 0.29.0, so its metadata describes behaviour that does not happen. Archived frozen at `attic/explore/nemotron-3-super-120b-a12b-nvfp4-vllm.yaml`; receipt `~/benchmarks/nemotron-120b-20261018/REPORT.md`.)*
  *(closed 2026-10-21, late — **`Nemotron-3.5-Lightning-30B-A3B-NVFP4` is booted, measured and SHIPPED**, and it
  empties this item for single-node work: it booted on `.35` through the shipped
  `ghcr.io/spark-arena/dgx-vllm-eugr-nightly@sha256:cc47adc1…` (vLLM 0.32.0rc1.dev301+g1ac942555, no new image)
  with the checkpoint quant auto-detected as `modelopt_mixed` (MARLIN NVFP4 MoE, FlashInfer attention + Mamba
  SSU), 20.10 GiB of weights, TTR ≈ 6 min in, `max_model_len 32768`, KV 10,703,667 tokens = 326.65×. House
  **37/37** at `--max-tokens 2048`, C1 **63.27 ± 0.65 t/s** (peak 65.67) and ladder **63.27 / 90.81 / 122.27 /
  144.15** at c1/2/5/10 with prefill flat at ~6.2k — the fastest single-node chat arm this lane has measured.
  Tool calling passes (`get_weather` with populated arguments). Thinking-off is decode-identical (62.73 vs
  62.74) but costs **five** house items (32/37), so the shipped numbers are thinking-on and the reasoning
  channel is load-bearing. This closes the ranked table for 1-node work: ranks 1–5 are all closed and 6–10
  are 2+ nodes (MiniMax-M3 is 795.5 GiB on the Hub, Inkling-Small 495.4). Recipe
  `recipes/explore/nemotron-3.5-lightning-30b-a3b-nvfp4-vllm.yaml`; commit `3800002`; receipt
  `~/benchmarks/reasoning-candidates-20261021/REPORT.md`.)*

- [ ] **Exercise the media-gen cells left unrun** — LTX-2.5's I2V + FLF2V templates and the 4K/50 fps preset; Qwen-Image non-8-step schedules and 2048²; and the faster vLLM-OMNI engine route (40 vs 54 s on the base model) (`attic/explore/EXPLORE-MODELS-RESEARCH.md`). *(Owner decision 2026-10-15: next-window scope, on the free `.34`/`.35`.)* *(effort: medium)*
  *(progress 2026-10-18 — the Qwen-Image 2048² cell is **CLOSED**: **53.24 s/image** (σ 0.20, n=3) against a same-boot **11.240 s** at 1024² (n=3, σ 0.008), tiling off, the three 2048² PNGs byte-identical (`sha256 86973bfb…`) and decoded at 2048×2048; peak 56.505 GiB torch alloc / 59.779 GiB reserved, node `MemAvailable` floor 53.8 GiB. The lane's ~26 s prediction is **falsified 2.04×** (+18.4 % per-pixel cost at 2048²). A non-null `num_inference_steps` is **silently ignored** — `12` was accepted and the pipeline ran the checkpoint's saved 8-step sigmas at the same 11.23 s — so a non-8-step schedule needs a `sigmas`-accepting mod, not a knob. Receipt `~/benchmarks/media-gen-20261018/` (`REPORT.md`, `cells.json`, `proof.json`). The non-8-step schedule and the vLLM-OMNI engine route stay **OPEN**; LTX-2.5's cells were closed late the same day — next bullet.)*
  *(closed 2026-10-18, late — **LTX-2.5 I2V + FLF2V + 4K/50 fps are measured.** Warm on `.34` (clock cap 2200 MHz, 1344×768 / 121 f / 24 fps): T2V **78.1 s / 83.70 GiB** (−2.5 % on the recorded 80.1 s), I2V **84.3 s (+7.9 %) / 83.79 GiB**, FLF2V **120.2 s (+54 %) / 81.94 GiB**. FLF2V is slower by mechanism, not regression: its template has no `LTXVLatentUpsampler`, so one full-res 8-step pass (76.9 s @ 9.6 s/it at 1344×768) replaces half-res 8-step + 3-step refine. Conditioning proven by decoded-frame MAD, not by a file existing: I2V frame 0 **4.1** vs the start image; FLF2V frame 0 **7.8** vs start / 59.5 vs end, frame 120 **16.9** vs end / 59.1 vs start. **4K/50 (3840×2160, 249 f) is OOM — a measured ceiling, not an untried preset:** stage 1 fine (8/8, 461.3 s @ 57.7 s/it at the 1920×1080 latent), killed at the ×2 latent upscale with 590 `NV_ERR_NO_MEMORY` kernel lines at **121.16 of 121 GiB** (85.0 GiB steady in stage 1, weights-only baseline 78.4 → not co-tenancy); the node stayed up, a process kill rather than a node loss. A smaller 4K cell at that output size is the only open question there and no register asks for one. Cold rep **204.3 s is an upper bound** (it overlapped a peer's serve; model load 25 s, first sampler step 12 s, cold tiled VAE decode 82.7 s vs 43.5 s warm). Receipt `~/benchmarks/ltx25-20261018/` (`REPORT.md`, 7 frames, 7 mp4s, per-rep `api/err/out`, `receipts{,_warm}`, and the fixed `expand2.py`/`run_cell2.py`; the runbook's expander is T2V-only — four defects listed in `attic/explore/AGENTS.md`).)*

  *(closed 2026-10-21 — **the Qwen-Image non-8-step schedule works, and the path is guarded.** `num_inference_steps`
  was silently ignored because the pipeline re-read the checkpoint's saved 8-step sigmas; the launcher mod now
  accepts a `sigmas` list and passes it through (`f610cba`). The guard that came with it asserted behaviour it
  could not be shown to catch, so schedule selection moved into a pure `schedule_kwargs(req, shipped)` and the
  tests exercise it directly — sigmas pass-through, the shipped count and the absent count both leaving the
  saved schedule alone, the resample's endpoints and monotonicity, and both `ValueError`s — with three
  negative controls that must go red (the pre-fix forwarded-field function, index rounding instead of value
  interpolation, a dropped `sigmas` kwarg), run against temp-dir shadow copies so nothing on disk moves
  (`75fb9fc`). 13 cases; the suite reads 752 with the file moved aside and **765** with it present. The 8-step
  control still takes the saved schedule, so no shipped number changed.)*
  *(closed 2026-10-21, latest — **the vLLM-OMNI route works and is ~24 % faster, and it stays
  unshipped on a quality caveat.** `vllm/vllm-omni:nightly` (0.32.0rc2.dev29) serves
  `Qwen/Qwen-Image-2.1-Turbo` natively through its own `QwenImage21Pipeline` on one GB10: TTR ≈ 4 min,
  `CUDNN_ATTN` auto-selected for sm_121/cuDNN 92000/head_dim 128, `POST /v1/images/generations`.
  **8.66–8.75 s warm / 11.19 s cold** per 1024² 8-step image against the Diffusers arm's 11.49 / 12.64
  s — 1.08 vs 1.43 s per step — at the **same** peak (36.84 vs 36.82 GiB). Two probes saved a dead
  boot and are worth not repeating: **`:latest` is 0.31.0rc1 and cannot load this checkpoint** (its
  registry has `QwenImagePipeline` only, while `model_index.json` declares `QwenImage21Pipeline`), and
  **sm_121 has no cubin in torch's arch flags yet bf16 matmul runs through PTX JIT**, so arch was never
  the blocker. **Not an arm:** no recipe was written; `num_inference_steps` is inert *and* the engine
  divides one total by the requested count (4/8/12 all wrote the byte-identical PNG in ~8.7 s while
  `denoise_step_latency_ms` read 2164/1086/721 — asking for more steps claims each step got faster); and
  same seed ≠ same picture (OMNI `38ce554a…`, Diffusers `e24f6e3a…`). **Operator review 2026-10-21
  (corrected the same evening), both PNGs at full resolution and read against the prompt** — which says
  `two-color screenprint`: Diffusers **honors it** (two-line `SPARK` / `RUN`, exactly two inks, blue over
  orange on cream, heavy grotesque, correct spelling, crisp edges); OMNI **violates it** (single-line
  `SPARKRUN` as a rainbow of many hues on white — correctly spelled and crisply edged, but not two
  inks). **That is a prompt-adherence defect, not a style difference**, and an earlier note here calling
  it "composition, not merely palette" with "no gross defect in either" read the rainbow as aesthetics
  and was wrong about the constraint. What still stands: no smearing, no blended or doubled glyphs, no
  gibberish letterforms, no step-count starvation artifacts, so the ~24 % win is real and defect-free — it
  is just spent on the wrong instruction. Scoped: one prompt, one seed, one image per route, so this is
  evidence against swapping on latency alone, **not** a measured general quality gap (no multi-prompt
  adherence battery was run). **Conclusion for the lane, settled by the owner on 2026-10-21:** the shipped
  Diffusers arm stays the only route the registry ships; an OMNI variant was offered as a *different look*
  the owner likes and **declined**, so no recipe is pending and none will be written unless that is
  reversed. §6 "which look ships" remains the owner's call for **both** routes (`recipes/explore/README.md`
  §6, `attic/explore/QWEN-IMAGE.md`). Receipt `~/benchmarks/media-gen-20261021/vllm-omni/`
  (`REPORT.md`, `omni.json`, `omni-warm8.json`); the two 8-step PNGs are **not tracked** (owner decision:
  the registry ships as text) and live only in the head receipt as
  `~/benchmarks/media-gen-20261021/eight-step-{diffusers,omni}.png`, identified by
  `e24f6e3a…24ee24a` and `38ce554a…45704690`.)*

- [ ] **Probe MOSS-Image (Base/SFT) — the lane's first Apache-2.0 image pair — on one free GB10** —
  research-only so far: **no recipe, no download, no boot**. `OpenMOSS-Team/MOSS-Image-SFT` (`f972bd4b`)
  and `OpenMOSS-Team/MOSS-Image-Base` (`85975793`) are both `pipeline_tag: text-to-image`,
  `library_name: diffusers`, `_class_name: MOSSImagePipeline` (`model_index.json`), `gated: false`, and
  **`license: apache-2.0` with the full Apache text in the repo's `LICENSE`** on both cards (vendor words:
  "The model weights and bundled inference code are released under the Apache License, Version 2.0").
  **That is the licence position: no banner, no revenue threshold, no non-commercial clause** — unlike
  `qwen-image-2.1-turbo` (qwen-research, non-commercial, banner) and `ltx-2.5` (community agreement, $10M
  threshold, gated, banner), so this pair needs **no banner decision** and is the first image arm the registry
  could ship to a third party without a licence caveat. *(checked 2026-10-22; counts and likes drift, do not
  freeze them.)*
  *What they are — bytes, not names.* Both repos are **27.229 GB** and byte-identical in layout:
  `transformer/` 10.165 GB (`MOSSImageTransformer`, **5.08B** params per `safetensors.total` — dim 3072,
  42 layers, 24 heads, `ffn_dim` 8192, `latent_channels` 128, `text_dim` 4096, RoPE base 10000),
  `text_encoder/` **16.786 GB** bf16 (`Qwen3_5Model` — a hybrid linear-attention + full-attention 32-layer
  text model, `head_dim` 256, `mrope_interleaved`, vocab 248,320, `transformers_version` 5.12.1 in its
  config), `vae/` 0.250 GB (`AutoencoderKLFlux2`, FLUX.2 *small* decoder, `latent_channels` 32, force_upcast),
  `tokenizer/` 0.020 GB. The text encoder's bytes count against the node budget and are the **larger half** of
  this arm. Its ~8.4B-by-bytes size is ~2.5 GB under the Comfy repack's 9.65B `qwen3.5_9b_bf16.safetensors`;
  the arithmetic fits a base `Qwen3_5Model` export with no `lm_head` (vocab×hidden = 1.02B params = 2.03 GB)
  *[INFERENCE — no doc states it]*. Sampling is **not** Qwen-Image's distilled 8-step path: flow-matching
  Euler, shift 5.0, **≥50 steps**, **CFG 3.0 = two transformer forwards per step**, negative-branch skip layer
  22 (`uncond_skip_layers=(22,)`, `scheduler/scheduler_config.json` + `pipeline_moss_image.py:344`).
  Resolution: 1M / 1.5M / 2M total pixels recommended, extrapolable **0.25M (512²) to 4M (2K)**, multiples of
  16 (`USERGUIDE.md:7-9`, vendor prose).
  *Base vs SFT — one engine, one serving path.* SFT carries `base_model: OpenMOSS-Team/MOSS-Image-Base` with
  `base_model_relation: finetune`, and the two repos share the architecture, `model_index.json` and every file
  size above, so **they are not two pipelines**: the same `MOSSImagePipeline` serves both and only the
  `transformer/` bytes differ. **SFT is the serving candidate**; Base is the reference/finetune source and is
  explicit that it was *not* tuned for inference ("has not undergone any post-training or distillation of
  inference parameters such as CFG", `USERGUIDE.md:5`), so comparing them is a checkpoint A/B on one boot, not
  a second arm.
  *Quantisations — re-censused 2026-10-22 and split by **runtime format**, because the format, not the bit
  width, decides the route.* Union of `base_model:quantized:` on both checkpoints (27 SFT-derived, 10
  Base-derived), `base_model:` on both (68 / 63), `?search=MOSS-Image` (154), the `moss-image` tag (126) and
  `?search=moss&full=true` (847) = **181 repos**, of which ~60 are LoRAs/finetunes rather than quants. Gated:
  only two, both plain mirrors (`modelarchive/MOSS-{SFT,Base}`, `gated: manual`). Licence: apache-2.0 on
  essentially all of them, with three exceptions named below. Sizes are tree-API bytes.
  **(a) diffusers-loadable — can ride the qwen-image launcher pattern with no new runtime.**
  `Rin247/MOSS-Image-SFT-{INT4,FP4,INT8,FP8}` — 11.60 / 11.82 / 13.91 / 13.90 GB, **complete diffusers trees**
  (`model_index.json` + `pipeline_moss_image.py`, DiT 3.10-5.41 GB, TE 8.40, VAE 0.06, per-component
  `quantization.json`); **licence gap: no `license:` tag on any of the four** — the only quant repos here
  without one, so no path may ship through them until the author states terms.
  `OzzyGT/MOSS_Image_SFT_sdnq_dynamic_{4,8}bit` (and the Base pair) — 9.12 / 14.37 GB, DiT 2.92 / 5.13 + TE
  5.93 / 8.97 + VAE 0.25, `modular_model_index.json` + `transformer/transformer_moss_image.py`; SDNQ dynamic
  quant loads through diffusers but needs the `sdnq` package in the venv — a dependency, not a runtime.
  `WaveCut/MOSS-Image-SFT-OrbitQuant-W4A8` — 8.81 GB, DiT 3.03 + TE 5.51, ships its own
  `moss_orbitquant.py` + `run_moss.py`. `AcademiaSD/MOSS-Image-NF4-for-LoRA-Training` — 40.89 GB, **Base**
  bitsandbytes NF4 with bf16/int8/nf4 text-encoder variants plus the 4-step adapter; training-oriented.
  `unsloth/MOSS-Image-{SFT,Base}-FP8` — 54.95 / 43.47 GB repos: the unchanged bf16 diffusers tree **plus**
  single-file DiT `FP8` 5.41 / `INT8-ConvRot` 5.42 / `INT8` 5.42 and TE `INT8-ConvRot` 11.49, and those roots
  load **only** in Unsloth Studio (vendor LPIPS 0.058 INT8-ConvRot / 0.111 INT8 / 0.163 FP8). Also in this
  class but loader-specific: `fal/MOSS-Image-SFT-flashpack` 27.23 GB (`*.flashpack`, fal's loader) and
  `KBlueLeaf/MOSS-Image-FP16-fixed` 40.69 GB (fp16 fix for both).
  **(b) ComfyUI / single-file / GGUF — a runtime this lane does not ship yet.** ConvRot-INT8:
  `Comfy-Org/MOSS-Image` (`24147db8`, 68.45 GB, ~1.29 M downloads; DiT bf16 10.16 / int8 5.41 each, TE
  `qwen3.5_9b` bf16 19.31 / int8 9.75 / w4a8 7.34, VAE 0.25 + 0.34), `Abiray/…-INT8-convrot` 14.12 GB (vendor
  mean rel. error 0.868 %), `a2815742427/…`, `SumomoLee/MOSS-Image-Base-ConvRot-ComfyUI` 17.15 GB (Base int4
  3.04 + int8 5.41 + TE 8.45, workflows + `quantize_moss.py`), `nif0/MOSS-Image-SFT-ComfyUI` 10.97 GB (int8 DiT
  5.41 + TE w4a8 5.43 + VAE 0.12), `Epyan/…`, `MATLOWAI/MOSS-Image-SFT-DeBand-int8`. INT6/INT4-GPTQ:
  `tsolful/MOSS_Image_INT6_INT4GPTQ` 31.84 GB (W6A8 4.37 / mixed W4A8-GPTQ 3.84 / RTN 3.33, DiT-only both
  checkpoints; vendor error 0.020), `Andylinux/…-W5A8-W6A8` 7.85 GB (DiT-only), and
  `DiffSynth-Studio/MOSS-Image-EntroPack` 43.97 GB (DiT 3.5/4.5/6-bit 2.24-3.85 + TE 4.5-bit 5.97) which needs
  **DiffSynth's own loader — a third runtime**. GGUF: `leejet/…` 25.74 GB (+ Base 730 dl), `realrebelai/…`
  88.11 GB (all tiers + W4A8-ConvRot, `other` licence on its `MOSS-Imagine_ComfyUI` sibling), `molbal/…`
  52.86 GB, `unsloth/…-GGUF` 23.42 GB (Q3_K_XL 2.84 → Q8_0 5.48), `axiomofmind/*` (DiT GGUFs + 7 GGUF LoRAs),
  `gguf-org` 3.47 GB, `AbrahamPJ/nightmare-moss-image`; plus Comfy split/repack repos (`RunningHubAI/rh-*`
  unet-only, `MOSSImagefok`, `taurusduan`, `mingyi456`, `Ateeph`, `TenStrip/MOSSkr2`, `nynxz`,
  `DeepBeepMeep/Moss`, `Kijai/MOSS-image_experimental`) and TE-only files (`sorryhyun/…-Qwen3.5-9B-{fp8,int8}`
  9.87 GB fp8_e4m3fn, `synta/…w4a8_gptq` 5.43 GB). **NVFP4**: `BennyDaBall/MOSS-Image-SFT-NVFP4` 4.52 GB — the
  only tier tagged **`blackwell`**, still DiT-only with no loader that claims the format — and
  `shayudabiaoge/MOSS-Image-SFT-NVFP4` (licence `unknown`).
  **(c) Apple-only — cannot run on a GB10 at all**: `mlx-community/MOSS-Image-{Base,SFT}-bf16`,
  `vanch007/…-mlx-{bf16,8bit,4bit}`, `VisualInference/…-MX-{8bit,compact}`,
  `mflux-community/moss-image-sft-mflux-{bf16,q8,q6,q5,q4,q3}`, `ddalcu/…-MLX-Serve-8bit`,
  `LocalMuseAI/mlx-moss-image-sft-dmd-4bit`, `Ouinche/…-te-mlx-q8g64`.
  **Not quants at all, and the only real latency lever:** the distillations — `lodestones/MOSS-Image-SFT-8-steps-dmd`
  (fp32 merged transformer 20.33 GB + LoRA, **no TE/VAE/pipeline**), its Base sibling `lodestones/MOSS-Image-Base-8-steps-dmd`
  and finetune `lodestones/Kromoss`, `akhaliq/MOSS-Image-SFT-4-steps` (LoRA steps + full pipeline tree, 120 GB
  repo) with its `moss-image-turbo-{2step,v2,v3,v3b,3step}` LoRA-only siblings, `darask0`/`Epyan` 4-step
  adapter, `p1atdev` KV-cache LoRA, `congruency/MOSS-Image-Turbo-MFD`, `Coffmeteor/MOSS-Image-Turbo` (bf16 10.16
  / FP8 5.41 / LoRA 0.59), `Kijai` rank-512 LoRAs, `BassionAI/…4steps-turbo-merged`, `toxicdog/…Turbo-INT8-ConvRot-AIO`
  (15.50 GB single file, format asserted by nobody but its card).
  **This table is a census, not a recommendation: the bf16 pair is still rank 1, and no quant row above is
  queued.** What (a) buys the lane is optionality, not speed: a diffusers-loadable 4-bit tier (Rin247 INT4
  11.60 GB, OzzyGT SDNQ-4bit 9.12 GB) is the only quant shape that could become an arm **without adding a
  runtime**, since this lane's only image precedent is a Diffusers script.
  **The cheapest honest speed lever is the step count, not quantisation** — 50 steps at CFG 3 is 100 DiT
  forwards per 1024² image, so an unmeasured 4-/8-step DMD or turbo LoRA above is a ~6-12× lever where a
  weight quant is a 0× lever on latency unless int8/fp8 GEMM happens to be faster on this silicon, which
  nothing here measured. A future session reaching for a quant first is reaching for the wrong knob.
  *Engine gate — decided against the package/registry, not memory.*
  **diffusers: real, but as a repo-shipped custom pipeline.** `MOSSImagePipeline` is **not upstream** —
  `diffusers` v0.41.0's `pipelines/__init__.py` has no MOSS symbol — and the repo ships
  `pipeline_moss_image.py` (440 lines) that defines `MOSSImageTransformer` and `MOSSImageScheduler` **itself**,
  with `model_index.json` binding both components to that module; the card's call is
  `DiffusionPipeline.from_pretrained(..., custom_pipeline="pipeline_moss_image", trust_remote_code=True)`.
  Upstream is needed only for `AutoencoderKLFlux2` (`from .autoencoder_kl_flux2 import AutoencoderKLFlux2` in
  `models/autoencoders/__init__.py` — line 7 at v0.36.0, line 8 at v0.41.0, so it exists at every tag
  v0.36.0…v0.41.0) and `transformers` for `Qwen3_5Model` (`models/qwen3_5/modeling_qwen3_5.py:1404`, present at
  tag **v5.3.0** — the card's stated floor). **The qwen-image launcher's venv (diffusers 0.41.0 /
  transformers 5.19.0 / torch 2.13.0+cu130) already clears every floor**, so this route costs a new server mod,
  not a new image and not a venv bump.
  **vLLM-OMNI: real and native.** `vllm_omni/diffusion/registry.py` maps
  `"MOSSImagePipeline" → ("mossimage", "pipeline_mossimage", "MOSSImagePipeline")` with
  `get_mossimage_{pre,post}_process_func` hooks; landed 2026-10-19 (`2c72dea3aa`, PR #8926, *with SLG*) and
  present at tag `v0.32.0rc1`. It refuses ring attention and any cache backend, and
  `_NATIVE_SINGLE_FILE_MODELS` holds Anima only, so **no quant repack above is loadable there**.
  **ComfyUI: real and native since v0.42.0** — `comfy/supported_models.py:2038 class MOSSImage`
  (`latent_format` Flux2, `shift` 5.0, `memory_usage_factor` 14.6) with `comfy/ldm/moss_image/model.py` and
  `comfy/text_encoders/moss_image.py`, from commit `e087d8f6cb` (2026-10-16). The lane's ComfyUI pin for LTX
  is **v0.34.0, which has none of it** (class absent at every tag v0.34.0–v0.41.0), so a Comfy route needs a
  new ComfyUI pin. **sglang / the vLLM text engine: no.**
  *GB10 ranking (128 GB unified, arm64 sm_121, one node), reasoning shown.*
  1. **`MOSS-Image-SFT` bf16 through diffusers** — 27.23 GB of weights; expect ~30–36 GiB peak *[INFERENCE:
  scaled from the Qwen arm's 32.5 GB → 36.85 GiB peak + ~8.7 GiB transient]*, i.e. ~90 GiB of headroom. The
  one untested cost is denoise: 50 steps × CFG 3 = **100 DiT forwards** against Qwen-Image's 8 → ~1.5–2
  min/image at 1024² *[INFERENCE, 1.0–1.2 s/forward from Qwen's measured 1.43 s at a 7B DiT]*. Fits.
  2. **Same bytes on vLLM-OMNI nightly** — the Qwen A/B measured OMNI ~24 % faster per denoise step at equal
  peak, so the same 100 forwards should cost less; blocked on a **digest-pinned nightly** (the lane recorded a
  floating tag only) and inherits the OMNI prompt-adherence caveat above.
  3. **SFT bf16 through ComfyUI ≥ v0.42** — same bytes, needs a new ComfyUI pin and its output parity with the
  reference pipeline is unmeasured.
  4. **diffusers-loadable 4/8-bit (Rin247 INT4 11.60 GB, OzzyGT SDNQ-4bit 9.12 GB, WaveCut W4A8 8.81 GB)** —
  these ride the same launcher, so they are the only quant shape that could become an arm without a new
  runtime; they halve the footprint and buy ~13-18 GB **this node does not need**, and Rin247 states no licence
  at all. A headroom/quality experiment for *after* a bf16 cell, never a first boot.
  5. **ComfyUI / GGUF / NVFP4 / Apple-only tiers** — INT8-ConvRot (14.20 GB), the GGUF and INT6-W6A8 sets and
  the only `blackwell`-tagged NVFP4 file all need a runtime this lane does not ship, or are DiT-only; MLX is
  Apple silicon. **Nothing in the bf16 pair fails to fit, and no quant tier is needed for fit.**
  *Pre-registered measurement (nothing ran).* Cells: **TTR** (container start → port open → `/health`, plus
  the pipeline-load seconds), then the lane's fixed prompt (`poster-typography: a bold sans-serif poster
  reading SPARKRUN, two-color screenprint, centered`) at **1024², seed 42, 50 steps, guidance 3.0, shift 5.0,
  `uncond_skip_layers=[22]`, n=3** → wall s (mean±σ), torch peak alloc/reserved, node `MemAvailable` floor,
  **PNG sha256**; a same-seed repeat for the determinism cell; and **2048² at the same knobs** for the
  resolution ceiling. Non-degeneracy: **Pillow in the engine venv** — mode/size, distinct gray levels, channel
  extrema, stddev (a flat, all-black or noise-only image falsifies the cell); PNGs are never read as text.
  Falsifiers: the two same-seed runs differ → the determinism cell is dropped rather than reported; a step
  change that yields a **byte-identical PNG** → the knob is inert on this pipeline (the Qwen/OMNI trap) and is
  reported as inert, not as a schedule; 2048² OOM inside the 0.85 budget → a measured ceiling, receipted as
  one; two boots disagreeing beyond the inter-boot spread → no number is quotable. **Quality against the vendor
  gallery is the owner's eye from the saved PNGs** — this pre-registration measures latency, memory,
  determinism and non-degeneracy only, and says so.
  *Unblocker — a free node, not research.* Phase 2 did not run: `.34`/`.35` belong to the ds4 worker's queue
  (`.local/BOOT-QUEUE-20261022.md` §Reduced-capacity fallbacks) — `.35` carried a foreign container at check
  time (`sparkrun_78c7e2fa…solo`, up 5 min) and `.34` is that queue's next TP=2 target — while `.30`–`.33` are
  the TP=4 block with items 1–2 still outstanding. When one node frees: author `recipes/explore/mods/moss-image-launcher`
  as a copy of the qwen-image launcher (same fail-closed venv gate, `MOSSImagePipeline` via `custom_pipeline` +
  `trust_remote_code` instead of `QwenImage21Pipeline`), pin the checkpoint by `model_revision:` (a bump boot
  passes the recipe file path, never `@littlecedar/…`), boot, run the cells, `docker cp` the serve log, stop by
  task id, re-assert 0 containers, receipt under `~/benchmarks/moss-image-20261022/`. *(effort: medium)*

- [ ] **Probe `fishaudio/drama-3` — a 35B/A3B TTS with a 10-codebook decoder — on one free GB10** — new
  release (checked 2026-10-22 on the Hub API: revision `b2b5ee998034b2975720906c815e7fb0e9f007bd`,
  `lastModified` 2026-10-17T05:06Z, `pipeline_tag: text-to-speech`, **ungated**, 15,274 downloads / 896 likes —
  live counts, do not freeze them).
  *What it is — bytes, not names.* One repo holding `FishOmniModel` (`model_type: fish_omni`) with three
  parts: a **`fish_omni_text`** MoE backbone (40 layers, hidden 2048, **256 experts top-8**,
  `moe_intermediate_size` 512, hybrid attention — 30 `linear_attention` gated-delta-net layers (16 key / 32
  value heads × 128) and 10 `full_attention` layers (16 Q / **2 KV** heads × 256) — `max_position_embeddings`
  **262,144**); a **`fish_qwen3_audio_decoder`** (`decoder_type: codebook_mtp_shared`, 4 layers, **10
  codebooks**, `vocab_size` 4096, per-frame window `max_seq_len` 11); and a separate **1.87 GB `codec.pth`**
  vocoder (vLLM-Omni's recipe: the "same Fish DAC codec as Fish Speech S2 Pro"). Dtype `bfloat16` with the
  routed experts in **FP8 block-128** — `quantization_config.quant_method: **bsgemm-moe**`, not a standard
  compressed-tensors label; vLLM-Omni maps it to its block-FP8 MoE kernels. Vendor claim, not measured here:
  **35B total / 3B active**. **The published base is already quantized and there is no bf16 route**: the
  `quantization_config` and the card agree — "FP8 MoE experts with the
  remaining weights in bf16" — 39.6 GB for 35B params is ≈1.13 B/param, the arithmetic of bf16-everything-else
  with 8-bit experts, so an operator cannot downgrade to a plain bf16 reference (which is also why the
  publishers' tables call this checkpoint "FP8 original"). Bytes: 39.60 GB of safetensors in 8 shards (index `total_size`
  39,594,895,616) + 1.87 GB codec + 20.8 MB tokenizer = **41.50 GB repo** (tree API). Audio contract:
  **44.1 kHz mono**, **~21.5 codec frames/s** (46.4 ms per frame, `vllm_omni/deploy/fish_omni.yaml`), long
  text chunked automatically and streamable per chunk (card); `<|speaker:0|>`…`<|speaker:15|>` carry up to 16
  characters, and the `[sighs]`/`[laughs]` "tags" are **plain text, not special tokens** (vLLM-Omni
  `recipes/fishaudio/Drama-3.md` — which also records that a line *starting* with a tag more often renders the
  tag and then silence until `max_new_tokens`: model behaviour, not a bug to tune away).
  *License position — a banner decision, not a footnote.* Card frontmatter reads **`license: other`,
  `license_name: fish-audio-research-license`, `license_link: LICENSE.md`**, while the card body and that
  `LICENSE` file are the **FISH AUDIO COMMUNITY LICENSE AGREEMENT, Version 1.0 — Last Updated: October 13,
  2026** (verbatim: "This Agreement is intended to allow, free of charge, research and non-commercial uses of
  the Fish Audio Materials and, as set out in Section III, limited uses for a Commercial Purpose by Licensees
  whose Annual Revenue is less than the Revenue Threshold"; threshold **USD 500,000**; and "**any Hosted
  Service, requires a separate written license agreement from Fish Audio**" — a Hosted Service being "an
  application programming interface, software development kit, **model-inference or model-hosting service**,
  or a website, application, or feature whose primary purpose is text-to-speech"; outputs must not be used to
  "create, train, distill, or improve any foundational generative AI model or any speech, audio, or voice
  generation model"; distribution requires the Agreement plus a Notice and "**Built with Fish Audio**"
  attribution). So the `license_name` field is **stale against the text it links** — the text is
  authoritative. Classification: **custom community license — research/non-commercial free, commercial only
  under the revenue cap, hosted service prohibited**. That is the `qwen-image-2.1-turbo` class (banner, and a
  third party receiving this recipe cannot offer it as a TTS service), *not* the `ltx-2.5` class (gated,
  $10M threshold) and not the Apache-2.0 MOSS pair; and the derivatives that re-tag themselves Apache-2.0
  (`AMAImedia/…`, `robertbschuette/…`) or invent a model type (`mlx-community/…`, `model_type:
  fish_drama3`) do not change that.
  *Quantizations — 43 `base_model:quantized:` repos enumerated* (`base_model:quantized:fishaudio/drama-3`
  filter + `?author=fishaudio`, whose 11 repos include the owner's own `drama-3-int4`). **None is gated.**
  Repo bytes are tree-API; "complete" = carries `codec.pth`/`codec.safetensors` + tokenizer + chat template, so
  it can synthesize without the base repo:
  - `fishaudio/drama-3` — **FP8 block-128 experts + bf16 rest** (the base itself; already quantized, so it is
    the reference, not a bf16 fallback) — **41.50 GB** — complete — vLLM-Omni or SGLang-Omni, both named on the
    card.
  - `fishaudio/drama-3-int4` — hybrid **W4A16**, routed experts + selected attention projections int4, shared
    expert and audio decoder bf16 (GPTQ-Marlin) — **24.03 GB** (22.1 GB of weights; the rest is 8 eval wavs,
    `eval.py`, `eval/eval_results.json`, `apply_patch.py`, `UPSTREAM_PR.md`) — complete — **its stated runtime
    is SGLang-Omni, and it needs a loader patch on top of it**: tags `int4`/`w4a16`/`sglang`/`sglang-omni`, and
    `UPSTREAM_PR.md` states the case — the quant_method is a *new* `drama3-int4` config that
    `apply_patch.py` appends to `sglang_omni/models/fishaudio_drama3/quantization.py` plus two registration
    lines in `engine_builder.py` (routed experts → `MoeWNA16Method` int4 group-128, dense targets →
    `GPTQMarlinLinearMethod`, everything else bf16). **Not our `v0.5.22`, and not even stock SGLang-Omni.**
    The owner's own warning is the silent-failure mode to watch: without the fused-prefix mapping the int4
    weights are missed and generation "returns zero audio frames". Serving memory 57.3 GiB on A100-80GB at
    `--tts_engine.gpu_memory_fraction 0.62 --vocoder.gpu_memory_fraction 0.2` (vendor). Card numbers: Seed-TTS
    English WER 1.63 % corpus (1.42 % trimmed) vs 1.99 % / 1.32 % for the FP8 base, +8 % per-request latency.
    `akhaliq/drama-3-int4` is the same quantization under the quantizer's own account — **one candidate, not
    two**.
  - `dangvansam/drama-3-nvfp4` — experts FP8 → **NVFP4** W4A16 (ModelOpt-style layout, group 16, FP8 block
    scales, no calibration), everything else bf16 — **27.42 GB** — complete, plus
    `examples/{sglang_omni.yaml, vllm_omni_deploy.yaml}`, so **both Omni forks** are its stated runtimes.
    Publisher numbers on **RTX PRO 6000, sm_120**: 36.3 GiB VRAM on SGLang-Omni / **30.9 GiB on vLLM-Omni**,
    CER 6.6 % hard / 2.9 % plain, speaker sim 0.844.
  - `dangvansam/drama-3-pruned-192e-nvfp4` **22.87 GB** (publisher 31.7 / 27.2 GiB) and
    `…-pruned-128e-nvfp4` **18.33 GB** (27.0 / 23.6 GiB) — 192 of 256 and 128 of 256 experts kept; 128E pays
    for its size in quality (CER 5.2 % plain vs 2.9 %).
    `dangvansam/drama-3-pruned-128e-fp8` **25.37 GB**, `…-192e-fp8` (publisher 29.4 GiB checkpoint) — same
    prune, experts still FP8. All complete, all with both engines' example configs.
  - `Reza2kn/drama-3-nvfp4` **27.42 GB** (25.49 GB tensor payload, per-layer `layer-NN.safetensors` + codec) —
    complete, and **a third engine variant, not a drop-in**: tags are `modelopt_fp4`, `blackwell`,
    `sglang-omni`, `experimental`, `library_name: sglang`; it pins **SGLang `v0.5.21` (`e00930c5`) + SGLang-Omni
    `00ac898e`** and ships a launcher that keeps only a **64-expert GPU cache, streaming the rest from disk**,
    validated on **sm_120 (RTX 5080 Laptop, 16 GB)** — no WER claimed, a 3-clip listening review. GB10/sm_121 is
    a *different* compute capability from its validated sm_120, and our SGLang pin is v0.5.22.
    `darioooooo0o/drama-3-w4a16` **25.89 GB** and `…-w4a16-32gb` **24.52 GB** (+ `apply_patch.py`),
    `asfberlin`/`Tintler` 128E w4a16 — complete, engine unstated beyond "w4a16", unmeasured by anyone but
    their cards.
  - `mlx-community/fish-audio-drama-3-{3bit,4bit,8bit}` **19.75 / 23.78 / 42.18 GB** — complete but the codec
    is `codec.safetensors` and the runtime is **MLX: Apple silicon only, cannot run on a GB10 at all**.
  - **GGUF family — none loadable by an engine this registry runs** (see the engine gate): `Jmica/Drama-3-GGUF`
   135.66 GB repo, six files 17.05–25.63 GB (Q2_K→Q4_K_S experts × Q8/Q4 backbones; **tagged `audio.cpp`**,
    card: "native audio.cpp conversions … built with … the converter in my llama.cpp branch") —
    **`audio.cpp` is an audio-side llama.cpp fork, not our `b2e5e9b` and not upstream**;
    `sakasegawa/drama-3-GGUF` 185.97 GB repo, Q4_K **20.79** → Q8_0 38.47 → F16 **71.61 GB** (engine unstated,
    same GGUF layout);
    `EryriLabs/drama-3-llamacpp-GGUF` **20.82** GB + `mmproj` 1.67 GB (card: built with **its own llama.cpp
    branch**, run through `dwain-barnes/mara-drama3`); `AMAImedia/…-FP8-BF16-GGUF` 65.09 GB (23.39 GB GGUF +
    the whole bf16 tree, Apache-2.0 mis-tag); `thetom-ai/Drama-3-ConfigI-GGUF` 57.64 GB (one 28.94 GB file +
    427 profiling artefacts); `pentacoxian-dev/drama3-small-GGUF` **10.46 GB** single IQ3_XXS (**a pruned
    "small" derivative**, not this checkpoint's bytes); `Frosty40…B70-Turbo`, `Harsha001…ROCmFPX`,
    `UltimateIntent…Q2-Q3`, `t8star`/`PedroMarinhoDev` Comfy packs, `Eng-Ahmd…Windows` — enumerated, none a
    route. (`WaveCut/Drama-3-OrbitQuant-{W2A2,W4A4}` 25.44 GB W4A4 and the `fcmeyer`/`cguldogan`/`Nav8ha`
    MLX mixes are enumerated and unwrapped: format asserted only by their cards.)
  *Engine gate — read off the registries and the image, not memory. **No candidate quant rides a resident
  image**: each one names a different runtime (base → vLLM-Omni/SGLang-Omni; int4 → patched SGLang-Omni;
  dangvansam → either Omni fork; Reza2kn → SGLang v0.5.21 + SGLang-Omni `00ac898e` + its own disk-backed
  launcher; GGUF → `audio.cpp` or a personal branch; MLX → Apple).*
  **vLLM (our pin, `vllm/vllm-openai:v0.32.0@sha256:befccf0e…`): NO** — `vllm/model_executor/models/registry.py`
  at tag `v0.32.0` has **no `FishOmni` symbol**.
  **SGLang (our pin, `v0.5.22`): NO** — `python/sglang/srt/models/` at that tag has no fish/drama module (its
  only `*_omni` file is `qwen3_omni_moe.py`).
  **vLLM-Omni: YES, and it is the no-build route.** `vllm_omni/model_executor/models/fish_omni/` is present at
  tag **`v0.32.0rc1`** and **absent at `v0.31.0rc1`**; `docs/models/supported_models.md:116` maps
  `FishOmniForConditionalGeneration → fishaudio/drama-3`. The image
  `vllm/vllm-omni:nightly-15bce345863c6e2db882534876b8977f5b1ae1e3` (manifest `sha256:f3473cb3…`, **arm64
  child `sha256:9c155dff…`, 11.23 GB**) is already resident on `.34`, and inside it `vllm 0.32.0` +
  `vllm_omni 0.32.0rc2.dev29+g15bce3458` with the `fish_omni` and `fish_speech` model dirs (verified by
  `docker run … python -c "import vllm, vllm_omni"`). **Trap: the vendor's own line is `vllm serve … --omni`,
  but this image's `/usr/local/bin/vllm` is plain vLLM** (`vllm.entrypoints.cli.main`) and its
  `serve --help=all` contains no `--omni`; the omni CLI is the separate **`vllm-omni`** console script
  (`vllm_omni.entrypoints.cli.main:main`, which takes the omni path only when `--omni` is in argv). Two stages
  share GPU 0 through a private MPS daemon on CUDA (`deploy/fish_omni.yaml` `platforms.cuda.cuda_mps: true`),
  and the default budgets are stage 0 `0.78` + stage 1 `0.1`.
  **SGLang-Omni: YES, and it is what the owner's int4 checkpoint documents**, but **no published image**:
  `docker/Dockerfile` builds `FROM lmsysorg/sglang@sha256:5fc09edb…` and **clones sglang-omni at container
  start**; `install.sh` defaults `SGLANG_REF=v0.5.22`; the model lives in
  `sglang_omni/models/fishaudio_drama3/` (30 modules, `vocoder.py` + `quantization.py` among them). A route,
  not a recipe — it costs a build.
  **llama.cpp: NO.** Upstream master `src/models/` (168 files) carries no fish/omni/drama architecture — only
  `pockettts.cpp` and `qwen3tts.cpp` — and at our pin `b2e5e9b` the same two among 150. Every GGUF above
  therefore targets `audio.cpp` or a personal fork, so "GGUF ⇒ runs on llama.cpp" is card optimism here.
  **transformers/torch and the `fish-speech` package: NO** — the config declares `FishOmniModel` but the
  implementation lives in the two Omni engines, and the card links only those.
  Verdict: **two real routes, both Omni forks of engines this registry already runs, neither at our pins.**
  *GB10 ranking (128 GB unified, arm64 sm_121, one node), reasoning shown.*
  1. **Base checkpoint on vLLM-Omni nightly** — 41.50 GB of weights, ~79 GB of the 121 GB pool left before KV,
     graph pools and activations. The vendor budgets (0.78 + 0.1) would claim **104 GB** of a ~119 GB device
     and squeeze the host, so the arm must declare its own stage budgets (`--stage-overrides
     '{"0":{…0.55},"1":{…0.06}}'` ≈ 71 GB) — the knob exists and parses (`vllm_omni/entrypoints/utils.py:61`
     `parse_stage_overrides`). This is also the pairing the vendor measured (H200: TTFA p50 88.9 ms, RTF 0.131
     at c1) — the only row with a vendor number to falsify.
  2. **`dangvansam/drama-3-nvfp4`, 27.42 GB** — the cheapest *measured* fit (publisher: **30.9 GiB** on
     vLLM-Omni), NVFP4 is Blackwell-native which is exactly sm_121, ~90 GB headroom. Its numbers are sm_120 on
     an unknown engine build, so it still needs its own boot.
  3. **`fishaudio/drama-3-int4`, 24.03 GB** — the only quant with the owner's name and published Seed-TTS
     WER (1.63 % vs 1.99 %), and it fits with room (57.3 GiB on an 80 GB A100, so ~60 GiB here); but it
     inherits **both** an SGLang-Omni build *and* its loader patch, and its documented flags
     (`--tts_engine.gpu_memory_fraction`, `--vocoder.gpu_memory_fraction`) are that fork's, not ours.
  4. **`dangvansam/drama-3-pruned-128e-nvfp4`, 18.33 GB** — smallest real fit, and measurably worse (CER
     5.2 % vs 2.9 %): a headroom experiment after a full-size cell, never a first boot.
  5. **MLX (19.75–42.18 GB) and GGUF (10.46–71.61 GB)** — cannot run: no CUDA backend, or no engine arch.
  **Nothing here fails to fit** — even the 71.61 GB F16 GGUF would fit 121 GB. The engine is the constraint,
  and on a GB10 the open question is not bytes but whether the FP8 block-MoE kernels, the GDN linear-attention
  path, the two-stage MPS co-tenancy and the CUDA-graph capture all survive sm_121 [SPECULATIVE — no vendor
  claim for GB10 exists; their table is H200 and the nvfp4 publisher's is sm_120].
  *Pre-registered measurement (nothing ran).* Cells: **TTR** container start → `/v1/models` **200 naming
  `fishaudio/drama-3`** (identity assert first: the 2026-10-22 attempt below shows port-only readiness is
  satisfiable by a foreign listener, so a bare port check is not a cell) plus the weight-load seconds from the
  serve log; the **fixed script** `The quarterly report is due on Thursday, so please finish it by noon.`,
  non-streaming `POST /v1/audio/speech`, **n=3**, → wall s (mean±σ) and **RTF = wall / audio duration**;
  **output integrity** — RIFF/WAVE parses, **44,100 Hz mono 16-bit**, duration > 0.5 s, peak > 0.01 full scale
  (a silent or truncated take falsifies the cell), sha256 per run; **cloning** with the card's own `en0`
  reference (`common_voice_en_10119832.wav` + its transcript) and **tag rendering** on
  `[sighs] Fine. If we miss it, it's on you. [laughs] Well, maybe that's fair.`; and one streaming `pcm`
  request for **TTFA**. Quality instrument — **named, not invented**: the owner's int4 repo ships the exact
  instrument, `eval/eval_results.json` + 16 reference wavs (`eval/theirs32/`, `eval/int4/`, one per prompt:
  plain×3, long, tags, zh, ja, clone) — **ASR round-trip WER per prompt plus speaker-embedding cosine
  similarity** (vendor-measured on the FP8 base vs int4: `mean_wer` **0.2593 → 0.1968**, `mean_speaker_sim`
  **0.8458 → 0.8456**, and the per-row numbers show why that mean is not a clean comparison: the FP8 `long1`
  row truncated to WER 0.6667 and `zh1` scores 1.0 on *both* because the reference uses full-width
  punctuation — so quote a row, never the mean, and never compare across a truncated take). **Reproducing it
  on a GB10 needs an ASR model and a speaker encoder, and no node here has either resident**, so the first GB10
  cell is honest about its limits: **WAV integrity cells (above) + a listener check by the owner** on two
  saved clips (intelligibility, and whether `[sighs]`/`[laughs]` land), scored against the same prompts'
  shipped reference wavs — with the vendor's Seed-TTS and FP8-vs-int4 tables cited as the only comparable
  published numbers. A later cell can reproduce the WER/similarity pair once an ASR model is staged.
  Falsifiers: no `/v1/models` naming drama-3 within the port timeout (3600 s); a POST that returns
  non-RIFF/empty; **single-stream RTF > 1.0** (slower than playback — the arm's practical bar); or audio the
  listener calls unintelligible.
  Receipt: `~/benchmarks/drama-20261022/` on the head (`drama-cells.py` — the client, whose `wav_stats`
  self-check was verified against a synthetic 0.5 s 44.1 kHz WAV; `retry.sh` — the guarded launch/reap driver;
  `sparkrun_serve.log` — the killed boot, 327 lines).
*Phase 2 — attempted; a port false green, then a real load that died on a deadline.* First attempt (02:20
EDT): `.34` was at 0 containers, but `humanizer-probe` took it at 02:26:31Z, and my container died at
`sock.bind` with `OSError: [Errno 98] Address already in use` **while sparkrun still printed "TTR
HTTP-ready 14.707s"** — with `readiness: inference: false` the probe is port+HTTP only and the foreign
server answered it, so that 14.7 s is a measured **false green**, not a load time (no weight had loaded).
Second attempt (02:35, node genuinely free — 0 containers, 99 GiB available, port 8000 clear; task
`c8829c3570d86002_8ed3ce77d78f`, boot log 06:36:06Z): **the checkpoint loads on the pinned nightly.** vLLM
0.32.0 resolved `FishOmniForConditionalGeneration` plus a stage-1 `FishSpeechDACDecoder`, started a private
CUDA MPS pipe, took the `bsgemm-moe` FP8 experts through **DEEPGEMM** (`Using DEEPGEMM Fp8 MoE backend out of
['AITER', 'FLASHINFER_TRTLLM', 'FLASHINFER_CUTLASS', 'DEEPGEMM', 'TRITON', 'MARLIN', 'HUMMING']`), read 8
shards at **29.6 s each / 242.84 s total** (36.88 GiB checkpoint, 78.11 GiB RAM available), and reported
**37.69 GiB** resident with the DAC encoder loaded — then vllm-omni killed it **2 s after torch.compile
finished** (`[backbone] torch.compile took 34.66 s`, 06:41:18) on its default budget:
`LLM stage-0 replica-0 did not become ready within 300s (stage_init_timeout)` at 06:41:20. Cold load 242.8 s
+ compile 34.7 s ≈ **298 s against a 300 s deadline**, so this arm was one flag from serving and its engine
question is answered: **the pinned `vllm/vllm-omni` nightly can hold drama-3; only the stage deadline is in
the way** (`--stage-init-timeout`, default 300, `vllm_omni/entrypoints/cli/serve.py`). Two side facts: the
log says DeepGemm is "auto-disabled … on Blackwell … Falling back to CUTLASS" at config time *and* selects
DEEPGEMM as the FP8 MoE backend later — same run, so read the backend line, not the gate. And the second
`/v1/models` check answered **empty**, which is the identity gate that the port probe is not.
*Unblocker — one free node once the TP=4 quartet (`.30`–`.33`) frees; no boot before that.* Exact command, no
override — the recipe now ships `stage_init_timeout: 1800` in `defaults:` and renders it into the serve
command (verified with `sparkrun run <recipe> -n`, which printed
`--stage-init-timeout 1800` verbatim):
`HOME=$PWD/.local/sparkrun-home sparkrun run recipes/explore/drama-3-35b-a3b-fp8-vllm-omni-tts.yaml -H <node>`;
**first assertion is `/v1/models` naming `fishaudio/drama-3`** — not a port-open, which is what lied on the
first attempt (the second boot reuses `/cache/runtime/vllm/torch_compile_cache`, so ~250 s is the floor, not
~10 min), then run the five pre-registered cells above, `docker cp /tmp/sparkrun_serve.log` into
`~/benchmarks/drama-20261022/`, stop by task id, re-assert 0 containers. Cleanup after this attempt: container
stopped, `.34` re-censused to **0 containers**,
job row gone, serve log (327 lines) archived at `~/benchmarks/drama-20261022/sparkrun_serve.log`. *(effort:
medium)*

- [ ] **Re-boot Laguna-M.1 on vLLM `v0.32.0`** — the pin moved for the CVE on 2026-10-22 (`9bce38b`, index digest `befccf0e…` / arm64 child `6ff5ff0d…`) and the arm in `recipes/explore/poolside-laguna-m1-nvfp4-vllm-tp2.yaml` is labelled **BUMPED, NOT RE-BOOTED**: its TTR, KV pool and suite numbers stay 2026-10-20 v0.29.0 measurements until a boot replaces them. Blocked on a free node pair — `.34` carries the vLLM re-pin and `.35` the SGLang `v0.5.22` re-pin. Expect the thinking contract to read differently on `v0.32.0`: thinking arrives at `message.reasoning`, and `usage.completion_tokens_details.reasoning_tokens` reads 0 while emitting characters. *(effort: short)*

- [ ] **Build the stock-upstream llama.cpp image and run the Mellum MTP A/B** — `recipes/explore/Dockerfile.llamacpp-upstream` is ready (pinned CUDA base digests, required `LLAMA_REF` with no default, gates against the `b2e5e9b` failure mode, `docker build --check` clean) and stock upstream `9df0b73c` (2026-10-20) carries Mellum MTP, `kolibri1` and `121a-real`/sm_121 upstream-native; only the decision2 pack still needs its fork (`qwen35`, 330 tensors where upstream expects 320). Unblockers: a build host window, and the arm64 self-hosted runner for the weekly CI report (`vars.ARM64_RUNNER_ENABLED`). Pre-registered A/B: existing Q4_K_M main + `mtp-Mellum2.1-12B-A2.5B-Thinking-BF16.gguf --spec-type draft-mtp --spec-draft-n-max 1`; falsifier C1 > 114 t/s n=5 vs 111.9 ± 0.3, accept-len recorded, no C2/C5 regression, house 37/37 and bfcl 88.3 % held. *(effort: medium; recorded 2026-10-22 01:22 ET)*

- [ ] **Probe the `RecursiveSI` org's flagship `flint` — a 39.8B-A2.5B agentic-coding MoE — for a GB10 arm** — new release
  (org `RecursiveSI`, checked 2026-10-22: **one model family only** — `flint` plus three same-day quantizations, no
  datasets, no spaces; model updated 2026-10-21T14:24Z, Apache-2.0, **307** likes — a live count, it drifts, so
  do not freeze a number): `FlintForCausalLM` /
  `model_type: flint`, i.e. a **custom architecture**; 49 layers (2 dense then 47 MoE — `mlp_only_layers [0,1]`), 256
  routed experts with 6 selected per token plus an always-active shared expert (`shared_expert_intermediate_size`
  1024), 32 query / 4 KV heads at head_dim 128, 35 sliding-window layers (513-token window) and 14 full-attention
  layers — the same 14 are `no_rope_layer_indices`, i.e. no positional encoding (verified set-equal) — vocab
  150,144, documented context **262,144**. **Vendor claims, not measurements:** the card reports 54.9 %
  Terminal-Bench 2.1, 89.7 % SWE-bench Pro v2 and 74.2 % SWE-bench Verified at temperature 1.0 / top-p 0.95 /
  top-k 20, as **pass@1 averaged over ≥5 attempts**, with Terminal-Bench counting web-retrieval solutions as
  unsuccessful. Weights **79,575,138,056 B = 79.58 GB across 15 BF16 shards** (repo `usedStorage` 79.59 GB is
  the whole repo, SGLang kit and card included).
  **Org scope (checked 2026-10-22):** the other three repos are derivations, not probes: `flint-int4` (MLX 4-bit,
  22.58 GB, 6 likes), `flint-nvfp4-gguf` (single `flint-nvfp4.gguf`, 22.86 GB, 3 likes) and `flint-int4-gguf`
  (single `flint-int4-q4_1.gguf`, 25.99 GB, 5 likes); all Apache-2.0, ungated, `text-generation`, newest
  2026-10-21T15:54Z. None is a second architecture or size class and none needs its own item: MLX runs on Apple
  silicon only, and the two single-file GGUFs are 22.86 / 25.99 GB — *larger* than Unsloth's 3-bit 18.49 GB tier —
  so they are an accuracy fallback for this arm, not a separate lane candidate. (`NVIDIA/…` and `MLX-Community/…`
  carry no flint repo; the whole quant family lives under `RecursiveSI/`.) No second family exists to probe.
  **Engine verdict, folded in as the decisive fact: the SGLang route is blocked, on three independent locks.**
  The kit targets **SGLang v0.5.16-cu130**, not a range: the wheel (`flint_sglang-0.1.4-py3-none-any.whl`)
  declares no `Requires-Dist` at all, so the real pin is `sglang/Dockerfile`'s
  `FROM lmsysorg/sglang@sha256:7b6a35df…` plus `install.sh`'s header. (1) The plugin does
  `from sglang.srt.server_args import ServerArgs, add_grammar_backend_choices`, and
  `add_grammar_backend_choices` is present at v0.5.16 but **absent at our pinned v0.5.22** → ImportError at
  plugin load. (2) `install.sh` sha256-verifies `sglang/jit_kernel/flash_attn/cute/flash_fwd_sm100.py` before
  *and* after applying `fa4-learned-sink-fix.patch`, so the patch is anchored to that one image's file.
  (3) The kit's own envelope excludes us: its README requires "One GPU with >=141 GB per replica: B300/B200
  or H200. 80 GB GPUs are not supported", and `serve_b300.sh` says validated on B300 x86_64 — a GB10 is
  128 GB unified and sm_121. So the **only plausible route is llama.cpp + Unsloth's GGUF**, plausible tier
  **UD-Q3_K_XL (18.49 GB)**, gated by **`LLAMA_REF >= a37cc4610`**. That makes the stock-upstream image
  (`recipes/explore/Dockerfile.llamacpp-upstream`) **the gate for any flint cell, not an optional upgrade**;
  the Unsloth item below carries the tier list, the vendor t/s claims and the open questions. 79.58 GB of
  BF16 still leaves no room for a 262k KV cache on one 128 GB GB10, so the BF16 route stays out of scope.
  Research only — no download, no boot, no receipt yet. *(effort: medium)*

- [ ] **Leverage the Unsloth runtime for GB10 arms, Flint first** — Unsloth publishes pre-quantized
  **Dynamic v3 GGUFs** and documents both an engine path (their llama.cpp build) and a GUI runtime
  (Unsloth Studio / Desktop), which is exactly the gap our llama.cpp route has: our publisher is stalled
  at `b10549-cu131` (2026-08-21) and our pinned engine is `b2e5e9b`. The first target is
  `unsloth/flint-GGUF` (Apache-2.0, `base_model: RecursiveSI/flint`, repo 283.2 GB) — published tier sizes (Hub
  tree, 2026-10-22; all nine verified to 2 dp):
  UD-IQ1_M **11.35 GB**, UD-IQ2_XXS 11.86, UD-Q2_K_XL 13.56, UD-IQ3_XXS 14.54, UD-Q3_K_XL **18.49 GB**,
  UD-Q4_K_XL 25.05, UD-Q5_K_XL 29.92, UD-Q6_K_XL 36.32, Q8_0 42.30 — so every tier from Q3_K_XL down
  fits one GB10 with room for KV. Their guide claims the 3-bit tier fits 24 GB setups at 125+ t/s on an
  M4 Pro and 150+ on a 64 GB RTX Spark (their numbers, not ours; the guide is
  `unsloth.ai/docs/models/flint`, quant scheme `unsloth.ai/docs/basics/unsloth-dynamic-v3.0-gguf`, and
  they keep a "DGX Spark and Unsloth" page). **The engine gate is already answerable:** upstream
  llama.cpp gained `src/models/flint.cpp` in **`a37cc4610` (2026-10-21 21:26Z, PR #30928)** — and it is
  still the **only** commit touching that file at master `e3797b18` (2026-10-22T05:30Z; seven commits
  since, none mentioning flint), so `≥ a37cc4610` is the whole floor and no follow-up fix has moved it.
  `flint` is upstream-native but *newer* than both our pin and the `9df0b73c` (2026-10-20) ref the
  stock-upstream task queued — that Dockerfile's `LLAMA_REF` must be ≥ `a37cc4610` for any Flint GGUF.
  Open questions to settle before a recipe: whether Unsloth Studio/Desktop exposes an OpenAI-compatible
  server sparkrun could drive (or whether this is a llama.cpp-leg only), and whether their fork carries
  anything upstream `a37cc4610` lacks. Then the usual bar: ladder at d0 plus the house battery and the
  coder-agent legs on UD-Q3_K_XL, with the same arm rules as the shipped Mellum llama-cpp arm
  (`recipes/explore/mellum2.1-12b-a2.5b-q4km-thinking-llamacpp.yaml`). Research first — no download, no
  boot, no receipt. *(effort: medium)*

- [ ] **Probe Indra OCR — the registry's first document-AI arm, and its first non-LLM serve** — research-only so
  far: **no recipe, no download, no boot, no receipt.** `datalab-to/indra-ocr` (checked 2026-10-22) is
  `pipeline_tag: image-to-text`, `library_name: onnx`, **ungated**, 3,588 downloads, `lastModified`
  2026-10-19T14:36Z. **It is not a GPU LLM and it is not a transformer**: `config.json` declares
  `model_type: indra-ocr`, `framework: onnxruntime`, `install: pip install indra-ocr`, `library: indra-ocr`,
  16 model files, no `architectures`. It is a **det → line-classify → four-CTC-recognizer → reading-order**
  ONNX stack over grayscale page images: `det.onnx` 0.39 MB, `script.onnx` 0.19 MB (routes each line to
  base/cjk/rtl/world), recognizers `rec.onnx` **5.04 MB** (Latin ~50 languages + Latin handwriting, plus
  Cyrillic and Greek), `rec_cjk` 10.18, `rec_rtl` 4.81, `rec_world` 5.63, `order.onnx` 2.97 (layout label +
  reading order), `orient.onnx` 0.37, optional math (`math_enc` 9.89 / `math_dec_step` 8.43 /
  `math_dec_init` 1.36 / `mathcls` 0.19, fetched only with `--math`), and three n-gram LMs (`lm.npz` 15.70,
  `lm_cjk` 18.96, `lm_world` 11.64) that only rescore lines the classifier was unsure of (`meta.json`
  `lm_params` gate 0.95). **Parameters: 1,250,566 F32 in `model.safetensors`** (Hub `safetensors.total`) —
  `config.json` says that file is *only* the float weights of the Latin recognizer, published "for the Hub
  parameter count; the package does not use it". Vendor claim, not measured here: 7.3M params across all
  default models, "1M-parameter OCR model". **Bytes: 102.01 MB in 27 files** (tree API at main `bd02167f`),
  of which the default download is **76 MB** (30 MB of networks + 46 MB of LMs); an external note put the
  repo at ~127 MB, the tree sum does not support that, so the number used here is the measured one. There
  are **no tokenizer files** — the vocabulary is a JSON char list in `meta.json` (`vocab`, `vocab_cjk`,
  `vocab_rtl`, `vocab_world`; `script_groups: [base, cjk, rtl, world]`), and the `lm*.npz` are the only
  language-model-shaped artifacts. **Complete for OCR** means det + recognizers + `order` + `orient` +
  `script` + `meta.json` + the three LMs + `math_meta.json`; a set missing the LMs still runs (the code
  treats them as optional, `pipeline.py:352-368`), it just loses unsure-line rescoring.
  *Input contract.* One **page image** at a time — grayscale preferred, PNG/JPEG/TIFF/BMP/WebP, one page per
  TIFF frame, or a PDF rasterised by `pypdfium2` at `--dpi` **200** default (`pipeline.py:1015-1027`); an
  in-memory `uint8` gray array via `conv.ocr(gray)`. Detector at `meta.json det_long_side` **1024**, with a
  second pass up to `ADAPTIVE_MAX_SIDE` **2048** when the median line height falls under 9 px
  (`pipeline.py:43-55, 381-397`); recognizers read **32-px**-high line crops (`rec_height: 32`) in batches
  of **64**, the base recognizer through a 3-line tall window (`rec_window: 3`).
  *Output contract.* Per page: `markdown` (headings, lists, tables as HTML), `text` (one line per detected
  line), `lines` = `Line(box, text, conf)` with pixel boxes, `blocks` = `{label, bbox, text}` in reading
  order over 10 labels (`Text`, `Section-Header`, `Page-Header`, `Page-Footer`, `List-Group`, `Table`,
  `Caption`, `Footnote`, `Table-Of-Contents`, `Form`), `source` (`text` layer / `ocr` / `hybrid` /
  `error`), `rotation`, `skew`, `vertical`, `timings` with `total_ms`, `note`; `--format json` writes one
  JSON object per page. **Boxes and confidences are in the output** — that is what makes an OCR cell
  machine-checkable rather than a matter of taste.
  *Accuracy — everything below is the card's own benchmark, i.e. a **vendor claim**, and none of it is
  reproduced here.* OmniParseBench (16,288 pass/fail tests, 2,937 pages): headline **66.7** (text 46.7,
  tables 61.1, layout 92.2), **71.4** with `--math` (text 62.7, math tests 14.0 → 55.8); PaddleOCR
  PP-StructureV3 58.4 on the same scorer. OmniDocBench v1.5 (OCR only, 1,651 pages): text edit distance
  **0.114 EN / 0.237 zh-CN**, table TEDS 0.47. olmOCR-bench: multi_column 70.0, long_tiny_text 67.9,
  table_tests 60.5, **old_scans 20.0**. Per-script OmniParseBench: Latin 61.6 (9,406 tests), Chinese 64.0,
  Korean 79.2, Japanese kana 57.9, Arabic 69.2, Devanagari 69.6, Thai 87.2 — with the card's own caveat that
  most scripts have 13–60 tests, so one test moves a score by 2–8 points. **57** declared language tags in
  `cardData.language`. **The capability delta against a GPU OCR candidate is handwriting and degraded
  scans**: **25.2 %** on the OmniParseBench handwriting tests (about a third of words on held-out cursive
  pages) and **29.5 %** on degraded scans, against a transformer VLM OCR arm (the vendor's own
  `surya-ocr-2` / `chandra-ocr-2` line, or vLLM's `dots_ocr`/`paddleocr_vl` family) — so this is a *fast
  clean-print* arm, not a hard-document arm, and any future GPU OCR probe is a different capability, not a
  faster version of this one.
  *Licence position — the decisive shipping fact, and it is stricter than the `openrail` tag suggests.* The
  card frontmatter says `license: openrail`, but the repo's `LICENSE` is the **AI PUBS OPEN RAIL-M LICENSE
  (MODIFIED), Version 0.1, March 2, 2023 (Modified)** — an AI Pubs OpenRAIL-M text, not the bigscience
  OpenRAIL-M that `openrail` normally denotes, so **read the file, not the tag**. Verbatim from Attachment A:
  no use "for any purpose if You (your employer, or the entity you are affiliated with) generated more than
  twenty million US Dollars ($20,000,000) in gross revenue in the prior year, except where Your Use is
  limited to personal use or research purposes", the same "raised more than twenty million US dollars"
  threshold, and no use "for any purpose if You … provides or otherwise makes available any product or
  service that competes with any product or service offered by or made available by Licensor". §4(a)–(d)
  makes those restrictions flow through any redistribution; §7 requires attribution plus a copy of the
  licence. **§8 is a share-alike on the Output**: "You agree to apply this License (to the exclusion of all
  others) to any and all copies of the Model, Derivatives of the Model, … and to the Output and any
  derivatives, changes or improvements to or of the Output." For a registry shipped to third parties that is
  the load-bearing clause: **every page this arm transcribes inherits a use-restricted licence**, so OCR
  output cannot be passed downstream as unrestricted text. Code (`datalab-to/indra`, 901★) is Apache-2.0 and
  separate from the weights. **Banner decision — owner's, and stricter than the Qwen-Image one**: a recipe
  carries a top-of-file LICENSE BANNER naming the $20M revenue/funding cap, the no-competing-service clause,
  attribution, and the output share-alike; without it the arm ships to nobody. An operator needing
  commercially unrestricted OCR text swaps the checkpoint (or buys a Datalab licence).
  *Engine gate 1 — no engine serves it, and both pinned registries say so.* **vLLM `v0.32.0`: no.** Its
  registry carries autoregressive OCR *VLMs* — `DeepseekOCR{2}ForCausalLM` (`registry.py:366-368`),
  `UnlimitedOCRForCausalLM`/`DotsOCRForCausalLM` (`:381-382`), `GlmOcrForConditionalGeneration` (`:422`),
  `LightOnOCRForConditionalGeneration` (`:483-486`), `PaddleOCRVLForConditionalGeneration` (`:548-551`),
  `QianfanOCRForConditionalGeneration` (`:560-563`) — and **zero hits for indra or surya**. That family is
  precisely what Indra is not: no vision tower feeding an LM head, no autoregressive decode, so vLLM's
  multimodal path has nothing to carry. **SGLang `v0.5.22`: no** — 0 hits for indra/surya/ocr/donut in
  `python/sglang/srt/models/registry.py`. **transformers: no** — no `architectures`, no modelling file.
  **ONNX Runtime: yes, and it is the only route.** `pip install indra-ocr` (PyPI **1.1.2**, 2026-10-20
  01:41Z) pulls `numpy`, `opencv-python-headless`, `onnxruntime`, `pypdfium2`, `huggingface_hub`, and **all
  four publish aarch64 wheels** (onnxruntime 1.31.0, opencv-python-headless 5.0.0.93, pypdfium2 5.14.0,
  numpy 2.5.4) — a wheel install with no build step on any arm64 host. Execution providers:
  `OrtOCR(providers=…)` defaults to `["CPUExecutionProvider"]` (`pipeline.py:258-294`) and
  `load(providers=…)` is public API (`__init__.py:25-49`) but not on the CLI; `onnxruntime-gpu` 1.31.0 does
  ship a `manylinux_2_34_aarch64` wheel, so a CUDA EP is *installable* — untested by the vendor ("no
  PyTorch, no GPU" is its selling point). That is a knob, not a route, and not a reason to call this a GB10
  arm.
  *Engine gate 2 — can sparkrun exec a non-LLM ONNX server at all? Yes; this is the `vllm-srun` class of
  arm, not a model route.* Precedent: `recipes/decision/kokoro-82m-tts-cpu.yaml` states it outright —
  "sparkrun has no runtime family for a third-party Python server: `runtime: vllm` is the launcher/
  distribution contract this command satisfies" — with `readiness.inference: false`,
  `executor_config.entrypoint: ""`, and `distribution_config.models.enabled: false` when the image bakes the
  weights; `kev-0.8b-decision-serve.yaml`/`laya-decision-serve.yaml` are the same shape as inline scripts.
  What an Indra arm needs, concretely: (a) **no `--revision` fanfare and no KV story** — the package resolves
  its own model tag (`models.py:10 HF_REVISION = "v1.1.0"` = `a1283c4b…`) but also takes a local folder via
  `INDRA_OCR_MODEL_DIR`/`--model-dir`, so the mod points it at sparkrun's staged `{model}` snapshot and the
  Hub is never contacted; (b) **a mod that pins `pip install indra-ocr==1.1.2`** into a small base image —
  five wheels, no torch, no CUDA — and a ~60-line server exposing `POST /ocr` + `GET /health` with a
  documented status-code contract (the qwen-image launcher's shape, `recipes/explore/mods/
  qwen-image-2.1-turbo-launcher/`); (c) the lane's `/bin/kill` trap: sparkrun's detached-launch liveness
  check runs `docker exec <c> kill -0` and `python:*-slim` ships no `/bin/kill`, so the base must carry it or
  the serve is declared failed while healthy (recorded verbatim in `kev`/`laya`); (d) a core pin — the
  decision lane's CPU slot is `taskset -c 0-4,10-14` (A725), and `usable_cores()` honours it via
  `sched_getaffinity` (`parallel.py:24-29`), so `convert_many` fans out to exactly 5 workers. Model tags are
  **not ordered by name**: `v1.1.0` (`a1283c4b…`) is the full 102 MB set, while `v3.1`/`v3.1.1` are a
  **43.2 MB two-recognizer set** (base + cjk only, no `rec_rtl`/`rec_world`, no LMs, `meta.json` lacks the
  `vocab_rtl`/`vocab_world` groups) — a mirror card calls those "Indra OCR 1.0" and v1.1.0 "1.1", so a
  recipe pins the **sha**, never a tag's apparent order.
  *Fit — not a GB10 question, and the ranking a GPU arm would get is n/a.* There is nothing to size: 76 MB
  of weights and 5–7.5 GB of worker memory cannot fail to fit 128 GB, so **no quant table, no memory
  column, no CUDA ranking**. Quantisation effectively does not exist for this model either. That matters on
  two counts: the *only* quantised derivative is a half-precision conversion, and the risk a quant tier
  normally buys down is inverted here — the recognizer is a **1.25M-parameter CTC model over characters**,
  so narrowing it eats the logit margin that decides a single glyph (the card's own limitation list shows
  the failure mode: `ñ` for `ň`, `ú` for `ů`), and CER punishes a substituted character as hard as a dropped
  word. **The real deployment fact is the opposite of a fit question: CPU-only means this arm runs
  anywhere** — a GB10 node, the head, or a laptop — and displaces no GPU tenant. The binding constraint is
  cores, not bytes: work is line-level (a US-Letter page at 200 dpi is 1700×2200 = 3.74 MP = 3.74 MB as
  `uint8`; the adaptive re-detect ≤2048 long side is 5.4 MP), the package budgets `WORKER_MEMORY = 1.5e9`
  per worker for giant scans and caps the pool at `RAM // 1.5 GB` (`parallel.py:16-18, 32-37`), and a vendor
  code comment records a 40-page scan peaking at **4.9 GB** with the ORT CPU arena off
  (`pipeline.py:290-293`). `THREADS_PER_WORKER = 1`, one page per task: **pages/s scales with cores**
  (vendor: 6.2 pages/s on 4 EPYC cores, 43.9 on 32; on the lane's 5 pinned A725 cores expect single digits
  *[INFERENCE]*, and the lane's CPU precedent is that concurrency buys nothing there — Kai loses 32 % at c10,
  `recipes/decision/README.md:485-489`).
  *Quantisations, derivatives and mirrors — enumerated from `base_model:quantized:datalab-to/indra-ocr`, the
  `search=indra-ocr` index and `author=datalab-to&limit=100` (17 repos).* **None is gated; no GGUF, no int4,
  no int8, no ONNX Runtime int8 file exists.** `datalab-to/indra-ocr`: float32 ONNX + npz LMs, 102.01 MB,
  `openrail` tag over the modified OpenRAIL-M `LICENSE`, complete. `CharlZKP/indra-ocr-fp16`: **mixed fp16
  ONNX, 56.84 MB**, `base_model_relation: quantized`, built for **onnxruntime-web/WebGPU** per its own tags,
  `license: other`/`openrail-m-modified`, complete (all four recognizers + the LMs). The only lever the code
  itself looks for is `rec.int8.onnx`, auto-detected at load (`pipeline.py:303`) and **shipped by nothing in
  the search** — an int8 tier would be a build, not a download. `snowfluke/ppu-indra-ocr-models` is an
  **unmodified 134.17 MB mirror** of both generations (`v1.1/` = `a1283c4b…`, root = `d7c839c8…` tag
  `v3.1`), and `Jinstudio/indra-ocr` is a byte-for-byte copy of the 102.01 MB set — copies, not variants.
  The remaining four are **fine-tunes, not quants**: `wjbmattingly/comma-indra-ocr-1k`, `…-10k` and
  `nara-indra-ocr-r2` (18th–19th-century NARA handwriting) at 18.3 MB each, and `johnlockejrr/
  ocs-mix-indra-ocr` (39.96 MB, Church Slavonic / Old Cyrillic), each shipping det + recognizer + order +
  orient + script + `meta.json` with **no LMs and no math models** — complete for OCR, degraded at the
  unsure-line margin. All `openrail`.
  *Pre-registered measurement (nothing ran).* **Page set: text-only and committed.** This tree tracks no
  binaries (`git ls-files '*.png|*.jpg|*.pdf|*.tif'` is empty, and the owner's rule is that the registry
  ships as text), and `tools/synthetic_png.py` cannot substitute: its only generator is `solid_png_b64`,
  flat-colour PNGs for vision-token cost, with no text rendering. So the fixture is **reference text** plus a
  builder: `tools/ocr-bench.py` (**to be written, stdlib-only**) emits base-14 Helvetica PDFs from the
  committed reference (exact strings, one text object per reference line), the engine's own `pypdfium2`
  rasterises them at `--dpi 200`, `indra-ocr` runs, and the emitted JSON is scored against the reference.
  **Instrument — the objective one, named:** **CER** = `(S+D+I)/N` over characters after NFKC and per-line
  whitespace collapse, **WER** over whitespace tokens, per page and pooled; **TTR** (distinct ÷ total
  whitespace tokens) as the repetition check; **seconds/page** from the engine's own `timings.total_ms` plus
  wall clock; **peak RSS per worker** and the node `MemAvailable` floor; and a **`--mode text` vs `--mode
  ocr` pair** on the same pages, because the text-layer path is a different capability from OCR and the
  registry should not quote one as the other. **Two traps to pre-register, each of which voids a cell:**
  (a) `--mode auto`, the default, **reads a generated PDF's own text layer** and would score ~100 % for
  free — every OCR cell passes **`--mode ocr`**, and a cell whose `timings` show no detection stage is
  discarded as a text-layer read; (b) a rendered-print page is not a scan — no skew, no noise, no
  degradation — so the clean cell measures the recognizer only and the vendor's 29.5 % degraded-scan and
  25.2 % handwriting figures stay unmeasured claims. Robustness cells, same references, scored separately
  and never pooled: one page rotated 90°, one 180°, one light-on-dark (the card claims all three).
  **Falsifier:** pooled **CER > 0.02** on clean rendered Latin text falsifies "ships as a text-extraction
  arm" — a 1.25M-param model may be fast, not wrong one character in fifty; a rotation/light-on-dark cell
  returning non-empty text at **CER > 0.10** downgrades the orientation claim to a demo. Two boots
  disagreeing beyond the inter-boot spread → no number quotable. **If a real scanned page set cannot be
  committed under a licence that permits it**, that cell is cited from an external receipt under
  `~/benchmarks/ocr-20261022/` and no subjective quality claim substitutes for CER. Receipt:
  `~/benchmarks/ocr-20261022/` (`REPORT.md`, `cells.json`, per-page `jsonl`, the reference set's sha256).
  *Unblocker — a free node, not research, and this is the cheapest arm in the queue.* Phase 1 (this item) is
  the whole deliverable this window: `.30`–`.33` are the TP=4 block and `.34`/`.35` belong to other workers
  (`.local/BOOT-QUEUE-20261022.md`). Because it needs **no GPU**, a single node with five pinned cores is
  enough and no co-tenant is displaced — and, uniquely here, the first cells could be run on the head or a
  laptop and receipted the same way. When a node frees: write `tools/ocr-bench.py` + the reference set;
  author `recipes/explore/mods/indra-ocr-launcher` (server + `pip install indra-ocr==1.1.2` + `INDRA_OCR_
  MODEL_DIR` at the staged snapshot + a `/bin/kill`-bearing base) and the recipe on `runtime: vllm` with
  `entrypoint: ""`, `readiness.inference: false`, `model_revision:` `a1283c4b42a273c09480ad50e71461daff50fcc7`;
  boot, run the cells, `docker cp` the serve log, stop by task id, re-assert 0 containers. **And the licence
  banner lands with the recipe, not after it.** If the lane later wants OCR *on the GPU* that is a different
  probe with a different licence: the vendor's transformer line (`datalab-to/surya-ocr-2`, 1.48M downloads,
  and its `surya-ocr-2-gguf` sibling, `image-text-to-text` with its own code — vLLM `v0.32.0` has no
  `surya` entry either, so it is a `trust_remote_code` transformers arm). *(effort: medium)*

- [ ] **Timestral (Mistral AI) time-series family — a CPU-class arm whose runtime is a pip package, and the registry has no instrument that can score it** — the whole [`mistralai/timestral` collection](https://huggingface.co/collections/mistralai/timestral) is four F32 checkpoints of one bespoke forecaster (5M / 28M / 123M / 209M parameters; `pipeline_tag: time-series-forecasting`, `library_name: timestral`), and none of them is a language model: the cards describe **zero-shot probabilistic forecasting**, with no tokenizer, no chat template and no `model_type` or `architectures` key in `config.json`. **It is a CPU arm, not a GPU one** — the largest member is 837 MB F32 and the library runs on `device="cpu"` — so the shape is the decision lane's CPU serve, precedent [`recipes/decision/kokoro-82m-tts-cpu.yaml`](../../recipes/decision/kokoro-82m-tts-cpu.yaml): `runtime: vllm` is only the launcher/distribution contract (no runtime family exists for a third-party Python server), the engine is a script behind a mod, readiness is port + `/health`, and **the arm's gate is a forecasting instrument this registry does not have yet** — pre-registered below rather than inherited from the chat cells. Serving candidate **`mistralai/Timestral-209M` @ `9874d252ab0a`** (209,312,256 params, 837.3 MB F32); route-settling smoke **`Timestral-5M` @ `bdd20cfc15a3`** (5,208,960 params, 21 MB, so the first cell needs no node at all). *(effort: medium)*
  *(research 2026-10-22 — family and ranking, read from the four cards and the upstream repo. All four repos are ungated and ship **F32 only** (`model.safetensors`: 20.8 / 111.3 / 490.4 / 837.3 MB) with just `config.json` + `model.safetensors` + `LICENSE`; no upstream GGUF and no upstream quant. One architecture at four widths: a patch-based transformer over **32-step patches** with alternating time and variate attention (209M = 24 layers, d_model 768, 12 heads, mlp 2048, 6 of 24 blocks `time_variate`; 5M = 8 layers, d_model 192, 3 heads, 2 variate blocks), `rope_theta 10000` / `rope_partial_factor 0.5`, `use_asinh` scaling, `attend_missing_patches`, 21 quantile knots 0.01…0.99, context up to **32,768 steps**, horizon up to **1,024 steps** per pass with longer horizons rolled block by block on the running median. Card accuracy, 5M/28M/123M/209M — **vendor claims, nothing independently reproduced**: GIFT-Eval MASE 0.705 / 0.678 / 0.659 / **0.658** and CRPS 0.479 / 0.461 / 0.448 / **0.446**; TIME MASE 0.652 / 0.638 / 0.628 / **0.626**; fev-bench SQL skill 46.19 / 48.42 / 50.18 / **50.39**; the card also places 209M ahead of t0-gamma (0.661), TimesFM-3 (0.667), Toto-2.0-2.5B (0.696) and Chronos-2 (0.698) on GIFT-Eval MASE. **The ranking is an accuracy choice, not a fit choice:** 209M tops all three boards and 123M→209M costs 347 MB for 0.001 MASE; 28M is the throughput pick if 209M CPU forecasts are too slow for a useful cell rate; 5M is the smoke only. **The engine question is closed, in one sentence:** no vLLM / SGLang / llama.cpp arch exists for it (vLLM `v0.32.0`'s model registry has no time-series entry at all, SGLang `v0.5.22`'s 291 model files none, llama.cpp `master`'s 247 archs none) and `trust_remote_code` is not a lever because there is no `model_type` to dispatch on — the pip package *is* the runtime, and the derivative formats inherit the same gap (a lossless F32 GGUF with a published Rust harness at `gouzil/rust-model-inference@cc72a61f`; K-quant GGUFs whose own `timestral.cpp` link is 404 and whose own card admits 28M/123M inference pending; ONNX exports; MLX repacks, not quants).)*
  *(research 2026-10-22 — **the two real gates.** (a) **Can sparkrun exec a non-LLM forecasting server at all?** This is the same question the OCR probe answers for ONNX, and the Kokoro arm is the working template of the answer: `distribution_config.models.enabled: false` (a server that does not name the validated model in its command is otherwise rejected at launch with "serve command does not identify the validated model"), `readiness.inference: false` with port + `/health` only — though sparkrun's readiness still asks `/v1/models`, so the server must answer that path with the repo id — an empty `served_model_name` where the server takes no such flag, and a `/bin/kill` shim because the detached-launch liveness check runs `docker exec <c> kill -0` on images that may ship none. A **`timestral` mod** then has to stage `pip install git+https://github.com/mistralai/timestral@<pinned commit>` (Python ≥3.10, **torch ≥2.4** — a ~1 GB wheel, so the stage is the TTR risk Kokoro avoided by baking its model into the image) and run a stdlib server exposing `POST /forecast` (context ± covariates in, 21 quantiles out), pinned onto the lane's spare cores with `taskset`. There is no KV story and no distribution question: the 837 MB checkpoint is smaller than the venv that serves it. (b) **The licence is an owner decision, not a footnote.** `license: other` with no `license_name` on the Mistral repos; the LICENSE file is verbatim a **"Modified MIT License"**, attribution "2026 - Mistral AI", and its condition 2 withholds every right from anyone whose *"global consolidated monthly revenue … exceeds $20 million … for the preceding month"*, explicitly reaching *"the Model and any derivatives, modifications, or combined works based on it, whether provided by Mistral AI or by a third party"* — **threshold-community on a MONTHLY measure**, a stricter cadence than LTX-2.5's $10M *annual* bar. The **code repo is Apache-2.0 while the weights are Modified MIT**, so the banner must not conflate them. Ship-blocker call for the owner: if the registry's third-party distribution posture forbids a revenue-capped arm, the item ends here; if not, the banner lands **with** the recipe, quoting the clause and naming Mistral's commercial channel, in the Qwen-Image / LTX-2.5 style.)*
  *(research 2026-10-22 — **the missing instrument, pre-registered.** The lane has no probabilistic-forecast instrument: `tools/quality-battery.py` is 37 chat items, the ladder is pp2048/tg128 decode, needle is a haystack, and the TTS arm's answer ("a wav round-trip plus real-time factor") does not transfer. **Series set:** synthesised, committed, licence-free — `tools/forecast-fixtures.py`, stdlib only, fixed seed, six series of 4,096 steps with a fixed context/horizon split: (1) a **Gaussian random walk**, the important one, because its h-step predictive law is analytic (N(0, h·σ²)) and therefore gives exact quantiles to score against; (2) trend + weekly seasonality + AR(1) noise; (3) the same with a level shift; (4) one with a missing block (NaN) to exercise `attend_missing_patches`; (5) a 2-variate pair with a known-future covariate; (6) a constant series for the degenerate case. **No third-party series is redistributed** — GIFT-Eval / TIME / fev-bench licences differ and their published numbers are leaderboard aggregates over hundreds of series that a handful of committed series cannot reproduce; a committed generator plus seed is byte-reproducible and yields an oracle the leaderboards cannot. **Outputs a cell must produce:** the 21 quantiles 0.01…0.99 for a fixed horizon (h = 96) on every series, as JSON. **Metrics, `tools/forecast-bench.py` (stdlib):** mean CRPS computed from the quantile grid as `(2/K)·Σ_τ pinball_τ` with K = 21, mean pinball loss per level, MASE against a seasonal-naive baseline on the same split, a **quantile-ordering check** (non-decreasing across the 21 levels at every step), and PICP at the 80 % interval. **Cells:** load time, **seconds per 1,024-step forecast at the 32,768-step context**, **peak RSS on CPU** (`resource.getrusage`), and **determinism** (same input twice → byte-identical quantile JSON). **Falsifiers, pre-registered:** any **non-monotone quantile** is a hard fail — it is the failure mode these models actually exhibit and it invalidates the whole 21-quantile claim; CRPS worse than the seasonal-naive baseline on the oracle series does not ship; and **CRPS more than 25 % above the card's 0.446 GIFT-Eval figure** on the analytic-oracle series is a reproducibility failure to re-run before anything is quoted — stated as a sanity band, not parity, because a six-series subset is not that leaderboard. Receipt `~/benchmarks/timestral-2026102X/` (REPORT.md with the fixture hash and scorer version, per-cell JSON, coverage table). Order: fixtures and scorer first (both CPU-only and node-free), then the mod + recipe, with the licence banner landing with the recipe.)*

- [ ] **Probe Spark-X2.6-4B — a 4B dense hybrid-window agent model whose engine is *already resident*** —
  research-only so far: **no recipe, no download, no boot, no receipt.** `XHToken/Spark-X2.6-4B` (`66e3ae7b`,
  created 2026-10-19, **ungated**, 195 likes / 85 downloads at the check — counts drift, do not freeze them)
  is `pipeline_tag: text-generation`, `library_name: transformers`, and — the part that decides the arm —
  `model_type: spark2_5`, `architectures: [Spark2_5ForCausalLM]`, with `auto_map` custom code
  (`configuration_spark.py` 4.3 KB + `modeling_spark.py` 19.4 KB), i.e. `trust_remote_code` is mandatory.
  **Bytes, not names:** **4,112,079,360 params BF16** (`safetensors.total`), dense (no MoE keys anywhere in
  `config.json`), `tie_word_embeddings: true`, **8.224 GB across 5 shards** (`1.982 + 1.993 + 1.993 + 1.993 +
  0.262` GB = 7.66 GiB). hidden 2560, **36 layers**, 16 query / **4 KV heads at head_dim 256**, intermediate
  10240, vocab 131,072, `hidden_act: gelu`, `rms_norm_eps` 1e-6. The attention is a **hybrid window stack**:
  `layer_types` is 27 `sliding_attention` (window 512) + 9 `full_attention` (every fourth layer, the first at
  index 3), with **per-type rope** — full: `rope_theta` 5,000,000 at `partial_rotary_factor` 0.25; sliding:
  10,000 at 1.0 — and `headwise_attn_output_gate: true` (`gate_attn_act_mode: sigmoid`) on the q path.
  Tokenizer: fast BPE, 131,072 entries (`tokenizer.json` 10.1 MB + `vocab.json` + `merges.txt`), bos 0 / eos 1 /
  pad 2. Context: `max_position_embeddings` **1,048,576** in `config.json`, but `tokenizer_config.model_max_length`
  is **131,072** — the two disagree, and the KV arithmetic below says 131,072 is the single-node window.
  **Vendor claims, not measurements:** "retains exactly the same architecture" as Spark-X2.5-4B with gains
  "through improved post-training"; SOTA-among-4B on agent/code/long-context; and a **controllable thinking budget
  with three levels (none / low / high)**. The last is real and visible in the template, not just prose:
  `enable_thinking` (default `true`) plus `reasoning_effort` ∈ {`high` (default), `low`}, and anything else
  **raises** (`raise_exception('Unexpected reasoning effort …')`) — so "none" is `enable_thinking=false` and there
  is no third effort value.
  *Licence — the position, plainly, because this tree ships to third parties.* Card front-matter
  `license: apache-2.0`; the card body says "The Spark-X2.6 model series is licensed under the [Apache 2.0
  License](LICENSE)", and the repo's `LICENSE` is the **verbatim Apache-2.0 text** (11,338 B, "Apache License
  Version 2.0, January 2004") with no banner, no revenue threshold, no acceptable-use annex and no separate NOTICE
  clause. **That is a clean ship** — the same licence class as MOSS-Image, and the opposite of the qwen-research /
  community-agreement arms this lane already carries caveats for. Every X2.6 sibling and every derived quant repo
  below carries the same `license: apache-2.0` tag and is ungated — checked per repo, not inherited from the card.
  *Family — one item, and why.* `?author=XHToken&limit=100` returns **16 repos**: the X2.6 generation is
  `Spark-X2.6-4B` (this), `-Base` (17 likes), `-FP8`, `-INT8`, `-INT4` and `-GGUF`, all created 2026-10-19/20; the
  previous generation `Spark-X2.5` is `-4B` (36,890 downloads), `-1.7B`, `-Base`, `-FP8`, `-INT8`, `-GGUF` (the
  GGUF pair at 241k–420k downloads). **Scope decision: a single-model item on the 4B chat checkpoint, with the
  quant repos folded in as the quant table.** X2.6 has **no other size** (the 1.7B is X2.5-only), `-Base` is a
  finetune source with no serving decision of its own, and FP8/INT8/INT4/GGUF are the same bytes in other formats —
  rows in one table, not arms. X2.5 earns a mention only as a **same-arch control** (identical `model_type`,
  identical file layout, one generation older), so a boot that misfires can be diffed against a checkpoint the
  engines also claim to serve.
  *Engine gate — decided against the package/registry source, and it decides the arm.*
  **SGLang: YES, at the pin we already ship.** `python/sglang/srt/models/spark2_5.py` exists at **both** `v0.5.21`
  and `v0.5.22` (560 lines, `EntryClass = [Spark2_5ForCausalLM]`) and implements *this* config, not a lookalike:
  per-layer `layer_types` become per-layer `RadixAttention(sliding_window_size=…)` (`:174-185`, and an unknown
  layer_type **raises**), `head_dim` comes from config (`:232`), the gate projection is pinned
  `quant_config=None  # g_proj keeps bf16.` (`:145-153`), and per-type rope is read from
  `config.rope_parameters[layer_type]` (`:233-247`) so the 5e6/0.25 full-layer rope and the 10k/1.0 sliding rope
  both land. The qkv projection is named **`q_k_v_proj`** (`:135`) — the same name the vendor's compressed-tensors
  configs target, which is what makes the official quants plausible. Tool calling and reasoning are registered at
  both tags too: `function_call/function_call_parser.py` carries `"spark25": Spark25Detector` (the card's
  `--tool-call-parser spark25`) and `parser/reasoning_parser_names.py` carries `"qwen3"` (the card's
  `--reasoning-parser qwen3`). The card's own example names a nightly `lmsysorg/sglang:nightly-dev-cu13-…` image,
  but **nothing here needs it**: the module is in the release tags this registry pins
  (`lmsysorg/sglang:v0.5.21@sha256:b1259f3e…` on the tracked ornith arms).
  **vLLM: NO at `v0.32.0`.** `vllm/model_executor/models/registry.py` at that tag has no `spark2_5` /
  `Spark2_5ForCausalLM` entry — every "Spark" key in it is a **DSpark draft** model for DeepSeek-V4 / Qwen3 /
  Kimi-K3 / Gemma4, a different architecture — and no module of that name exists (`spark2_5.py`, `spark25.py`,
  `spark.py`, `spark2.py` all 404 at the tag). A vLLM route would be a `--model-impl transformers` /
  `trust_remote_code` fallback experiment on a custom hybrid arch, not a route.
  **transformers: the repo's own code, only.** No `spark` model dir at `v4.57.1` (384 model dirs) and `main` has
  only `muse_spark` (a different arch), so the card's `transformers==4.57.1` + `trust_remote_code=True` is the
  whole transformers story — good for a sanity forward, useless as a serve.
  **llama.cpp: YES above build b10828, NO at our pin.** `src/models/spark2-5.cpp` (144 lines,
  `llama_model_spark2_5::load_arch_tensors` / `build_arch_graph`) landed **2026-09-06 in `3ad1ba7336`** ("[Model]
  Support for Spark2_5ForCausalLM", PR #27868), is present at `a37cc4610` (2026-10-21) and **absent at our pinned
  `b2e5e9b`** (2026-08-21; 150 files under `src/models/`, no spark), which is engine `b10549` — 279 builds short of
  the card's floor. The GGUF side is otherwise clean: a range-read of the official Q4_K_M header gives
  `general.architecture = spark2_5` with an inline `tokenizer.chat_template` at byte 5,365,658.
  **Verdict: an SGLang arm on the image already pinned — no new image, no fork, no mod-staged template, no engine
  work.** That is the cheapest engine gate this lane has seen for a new arch.
  *Chat template — present, so this is not the usual 4B failure mode.* `chat_template.jinja` is in the snapshot
  (5,629 B) **and** embedded in `tokenizer_config.json` (4,766 chars): no mod has to stage one. It takes
  `enable_thinking` (default `true`), `reasoning_effort` (`high`/`low`), tool definitions and a
  `reasoning_content` field, so both the thinking channel and function calling are template-level.
  *Quantisations and derivatives — enumerated from `filter=base_model:quantized:` (22 repos), the author listing
  and per-repo tree APIs. Every one is **ungated** and `license: apache-2.0`. Sizes are tree-API bytes.*
  **Official, complete (weights + config + tokenizer + template + `auto_map` code):** the bf16 parent, 5 shards,
  **8.224 GB**; `-FP8` — compressed-tensors `float-quantized` W8A8, dynamic token-strategy activations, targets
  `self_attn.q_k_v_proj` + the MLP set, **4.452 GB** (one shard); `-INT8` — `int-quantized` W8A8 symmetric, targets
  `Linear` (everything), **4.454 GB**; `-INT4` — **`pack-quantized` W4A16, group_size 32**, `memoryless_minmax`
  static scales, targets `q_k_v_proj` + MLP, **3.412 GB** (the repo carries no `4-bit` tag — the scheme is read
  from `config.json`, not the tags). **Official GGUF, complete for llama.cpp only** (tokenizer + template embedded,
  no separate config): `XHToken/Spark-X2.6-4B-GGUF`, 16.15 GB repo — bf16 **8.230**, Q8_0 **4.375**,
  **Q4_K_M 3.543** GB, i.e. larger than every third-party Q4_K_M below, so the official build keeps more of the
  embedding/head at higher precision. **Third-party GGUF re-quants, complete-as-GGUF:**
  `bartowski/Spark-X2.6-4B-GGUF` 62.60 GB (bf16 8.230 → Q2_K; **Q4_K_M 2.621**, Q5_K_M 3.165, Q6_K 3.611),
  `mradermacher/Spark-X2.6-4B-i1-GGUF` 50.41 GB (imatrix; i1-Q4_K_M **2.600**, i1-Q5_K_M 2.978),
  `mradermacher/Spark-X2.6-4B-GGUF` 37.51 GB (Q4_K_M 2.600, Q2_K 1.787), `prithivMLmods/XHToken-Spark-X2.6-4B-GGUF`
  31.42 GB (Q4_K_M 2.600). **Incomplete or unusable here:** `WhiskyAKM/Spark-X2.6-4B-NVFP4-GGUF` (nvfp4 **2.487** +
  "small-nvfp4" 2.319 GB, four files total, format asserted only by the filename),
  `abenzerps/Spark-X2.6-4B-Quantized` (bf16 GGUF 8.230 + **single-file** `fp8.safetensors` 4.448 +
  `NVFP4.safetensors` 2.796 + four GGUFs, **no config and no tokenizer** — nothing loads those safetensors as a
  model), `UnstableLlama/Spark-X2.6-4B-exl3` (**no weights at all**: 0.01 GB of `selfcal/` traces and 2/3/4bpw
  recipes, an EXL3 build input). **Cannot run on a GB10:** every MLX repo (`abenzerps -4/6/8bit`, `0x36 -4/8bit`,
  `Jakevin` mixed/gptq, `pgmharikrishnan` mixed 4-8bit). Not quant tiers: `cinnybun02` and `SC117` (abliterated),
  `Harsha001` (ROCmFPX, AMD).
  *GB10 ranking (128 GB unified, arm64 sm_121, one node = the lane's **108 GB usable at util 0.85**, 273 GB/s
  LPDDR5X), reasoning shown.* Two numbers decide everything. **KV is 144.0 KiB/token** — 2 × 4 KV heads × 256
  head_dim × 2 B × 36 layers = 147,456 B/token — so 4.50 GiB at 32k, **18.00 GiB at 131,072**, 36.00 GiB at
  262,144, and **144.00 GiB at the card's 1,048,576**: the vendor's window is a **>1-node artifact** (weights + KV
  = 151.7 GiB; even fp8 KV at 72.00 GiB leaves no headroom). **131,072 is the honest single-node window at 25.7 GiB
  of weights+KV — 4.2× under the 108 GB budget — and 262,144 also fits at 43.7 GiB** if a long-context cell is
  wanted. Second: **decode is bandwidth-bound.** 8.224 GB of bf16 over 273 GB/s caps single-stream decode at **≈33
  t/s** ([INFERENCE] roofline; this lane's 0.9B precedent reached ~145 GB/s of spec, so ~53 % is the realistic
  haircut), and the same arithmetic gives ≈61 t/s at FP8/INT8 (4.45 GB), ≈80 t/s at INT4 (3.41 GB), ≈77 t/s at
  Q4_K_M (3.54 GB). So the bf16 4B lands **below every shipped chat arm here** (Laguna-XS 57.4, Nemotron-3.5
  63.3): its case is context-per-GiB, licence clarity and 4B tool calling — never speed.
  1. **SGLang bf16 on the pinned v0.5.21/v0.5.22 image, 131,072 window** — 8.22 GB weights, 18.00 GiB KV, zero new
     infrastructure. The control that must exist before any quant tier is credited, and the only route that costs
     nothing to try.
  2. **Same image, official FP8 W8A8, same window** — 2.6 GiB less weight and a ~1.8× decode ceiling (≈61 t/s);
     KV unchanged unless `--kv-cache-dtype fp8_e4m3` (then 9.00 GiB at 131,072). One flag
     (`--quantization compressed-tensors`), and the vendor's target names match the SGLang module names. **The
     shipping candidate if the battery holds.**
  3. **Same image, official INT4 W4A16, same window** — fastest ceiling (≈80 t/s), smallest weights (3.41 GB), but
     two extra risks: group-32 W4A16 on a 4B dense model, and `g_proj` deliberately stays bf16 (`spark2_5.py:150`),
     so the quant is not uniform. Only after 2 clears.
  4. **GGUF Q4_K_M on llama.cpp ≥ b10828** (official 3.543, bartowski 2.621, i1 2.600 GB) — same speed class as 3
     and the lane's existing llama.cpp harness applies, but it needs a **new image build** (our `b10549`/`b2e5e9b`
     has no `spark2-5.cpp`), which is real bring-up cost for a model that already fits bf16.
  5. **NVFP4 GGUF / `abenzerps` single files / EXL3 / MLX — not viable here**: an unverified llama.cpp NVFP4 path,
     single files with no config or tokenizer, no weights shipped, and Apple-only respectively.
  Nothing is too big to fit one node; the constraint is bandwidth, not capacity.
  *Pre-registered measurement (nothing ran).* Pin `model_revision: 66e3ae7bee54e0a523d692cb8ef841f35409807b`
  (`main` at the check), container `lmsysorg/sglang:v0.5.21@sha256:b1259f3e…` (the digest tracked arms already pin;
  a v0.5.22 re-pin carries the same module).
  **Boot cells:** TTR = launch → `/v1/models` 200; **served id = the HF repo id `XHToken/Spark-X2.6-4B`** unless a
  recipe alias intervenes; the serve log must name `Spark2_5ForCausalLM` and report `max_model_len` **131072**
  (pre-registered — the card's 1,048,576 is not a single-node cell, and a boot advertising it is a
  misconfiguration, not a result).
  **Ladder at d0:** `benchmarking/concurrency-ladder.yaml` (depth 0, pp 2048 / tg 128, c 1/2/5/10, 5 runs) via
  `sparkrun benchmark performance <recipe> -H <node> --profile benchmarking/concurrency-ladder.yaml --output
  <out>.yaml`, **decode rows only**, `--skip-run` against the boot the battery used so speed and quality share one
  window.
  **House battery, 37 items (19 easy + 18 hard):** `python3 tools/quality-battery.py http://<node>:<port> --tier
  both --repeat 3 --max-tokens 4096 --json quality-battery.json` — 4096 because a thinking arm at a smaller budget
  returns `finish_reason: length`, which is a budget miss and not a capability miss (`tools/README.md:313-317`).
  **Contract cells:** one `get_weather`-shaped tool call with populated arguments through `--tool-call-parser
  spark25` + `--reasoning-parser qwen3`; and a thinking control (`enable_thinking=false` via
  `--chat-template-kwargs`) — thinking-off is a quality claim with its own number, not an assumption
  (Nemotron-3.5 pays five house items for it).
  **Falsifier:** bf16 **C1 < 25 t/s** (under the roofline's ≈33 at ~75 % efficiency, and below the archived
  Mistral-Small-4 reject at 28.9) means the bf16 cell survives only as a control and the arm ships quantised or not
  at all; and pooled house **≤ 34/37** on whichever tier wins the ladder kills it, because 37/37 is this lane's
  tie-break rather than its gate — 35–36/37 only ships alongside a ladder that beats Laguna-XS's 57.4 at 36/37.
  **Receipt:** `~/benchmarks/spark-x2.6-20261022/` (`REPORT.md`, `ladder.json`, `quality-battery.json`,
  `serve.log`).
  *Unblocker — one free single GB10, nothing else.* `.30`–`.33` are the TP=4 block and `.34`/`.35` belong to other
  workers (`.local/BOOT-QUEUE-20261022.md`). No other gate: the arch is in the engine we already pin, the weights
  are 8.22 GB and ungated, the licence needs no banner, and no mod is required (the template is in the snapshot).
  Run cell 1 (bf16) first, with cells 2 and 3 as same-image follow-ups; the GGUF route is a separate image build and
  belongs to a `## Runtimes` decision, not this item. *(effort: medium)*

  *(progress 2026-10-22 — **cell 1 measured and the falsifier fired: bf16 is a control, not a ship candidate.** On `.30` (task `sparkrun_31a011c489646cf6_2d38dfc4605e`, 0 containers before and after): C1 **20.38 ± 0.09 t/s** (20.24–20.51, n=5 decode rows) and ladder **20.38 / 46.38 / 99.27 / 156.20** at c1/2/5/10, still rising at the cap because `max_num_seqs: 32` clamps it, not the pool; that is **61 % of the ~33 t/s roofline**, so bf16 survives only as the control the tier A/B is measured against. Contract confirmed on the wire: default → `reasoning_content` populated (`reasoning_tokens: 18`), `enable_thinking: false` → 0 reasoning tokens, one tool definition → `finish_reason: tool_calls` with `get_weather({"city":"Lisbon"})` parsed by `spark25`. House **37/37 thinking-on vs 30/37 (90/111)** thinking-off, so the reasoning channel is load-bearing. Memory: the hybrid split pools **84.48 GB** of KV (723,730 full + 578,984 sliding) = **5.52×** the 131,072 window, against the estimator's all-36-layers 18.0 GiB. Commits `6b82a39` + `6a1129d` (which added `--thinking on|off` to `tools/quality-battery.py`); receipt `~/benchmarks/spark-x2.6-20261022/`. **Open cells:** the **FP8 W8A8 and INT8 tiers** (2.6 GiB less weight, ≈2× the ceiling) — `recipes/explore/spark-x2.6-4b-fp8-sglang.yaml` is authored and its boot was **live on `.33` from 03:18:56 ET** (`max_total_num_tokens` 779,390, `max_running_requests` 32, 131,072 window), so that receipt is the open one; a ladder **above c10** needs `max_num_seqs` raised past 32 first; needle, ARC/GSM8K and BFCL/TEB are unmeasured.)*

- [x] **Ship the humanizer-12B rewrite arm at Q6_K, the smallest tier that passes its own instrument** — measured 2026-10-22 on `.33` (`sparkrun_7b0a21d0dbeb323d_80fa71eb085e`), commit **`475d07f`**: C1 **17.92 ± 0.04 t/s** @ d0 and 17.87 ± 0.05 @ d8192 (pp 999 / 1,366 t/s) — **2.36× the archived bf16 arm's 7.6** at 10 GB instead of an 88 GB repo; TTR **10.8 s**; **`/v1/completions` only**, because the checkpoint defines no chat template; **0 genuine fact errors across 40 rewrites vs the bf16 baseline's 1** (69 flags, all notation). Q4_K_M is recorded **measured-rejected**: 23.18 ± 0.19 t/s but 2 genuine fact errors ("about 90 minutes" → "A couple hours"; year 2026 → 2006), so it lost the only variable under test. Receipt `~/benchmarks/humanizer-20261022-q6k/`; lane row + tier reasoning `recipes/explore/README.md`. *(no ladder by design — a single-request rewriter has no C2/C5/C10 cell.)*

- [ ] **Bisect llama.cpp's ~12 % decode regression — only when a current-ref arm's 12 % is worth ~6 h** —
  measured 2026-10-22 on one node with the same bytes and flags: `b2e5e9b` (2026-08-21) **114.2 / 113.9 t/s**
  against `a37cc4610` (2026-10-21) **100.3 / 98.7**. The delta is **1254 upstream commits**, not the
  `scitrera` build: that image carries no patches (its Dockerfile clones `ggml-org/llama.cpp` at the tag),
  and its tree rebuilt through our own Dockerfile and flags reproduces **114**, while a CUDA-13.1.1 rebase
  (99.4 / 100.6), `GGML_CUDA_FA_ALL_QUANTS` (97.1 / 101.7), arch `121` and the RPC/CURL flags all measure
  irrelevant. **Decision rule:** a *fast + current* image needs the regression located — ~12 min build plus
  one 128-token probe per first-parent commit, so a **~6 h ceiling** at ~30 steps — therefore do it only
  when a new-arch arm's 12 % becomes worth that cost, and start from the suspects already recorded
  (`ggml-backend-meta.cpp`, `ggml-cuda/top-k-mask.{cu,cuh}`, `llama-graph.cpp` +100/−24, `ggml-cuda.cu` +6)
  rather than blindly. Separate and unrepaired: the `9df0b73c7` 8 t/s window reproduces from a clean
  context too. Tables, per-flag elimination and receipts: `attic/explore/AGENTS.md` §"The residual ~15 % is
  the upstream ref era"; the one-line policy is `mad-science/LLAMACPP-GGUF.md` §1. *(effort: long)*

- [ ] **Spark-X2.6-4B: three pre-registered cells left, one boot each (needs 1 free node; nothing
  running)** — the bf16 control (`recipes/explore/spark-x2.6-4b-bf16-sglang.yaml`, C1 **20.38 ± 0.09**,
  house 37/37 thinking-on / 30/37 off, 5.52× pool) and the FP8 tier
  (`recipes/explore/spark-x2.6-4b-fp8-sglang.yaml`, C1 **40.80 ± 0.09** = +100 %, house **36/37**) are
  both measured; receipts `~/benchmarks/spark-x26-20261022/` on the head. The three cells below are
  written out so a later session needs no re-derivation. **(1) Is the FP8 rejection a budget miss?**
  `trick-2` (prompt: *"If it takes 5 machines 5 minutes to make 5 widgets, how long would 100 machines
  take (in minutes)? Reply with just the number."*) returns `finish_reason=length`, **4,096
  `reasoning_tokens` and `content: ''`** at `--max-tokens 4096`, where bf16 answers it 3/3. Re-run
  `tools/quality-battery.py http://<node>:8000 --tier both --repeat 3 --max-tokens 8192 --thinking on
  --json fp8-mt8192.json` **plus** a direct re-ask of that one prompt recording `finish_reason` /
  `reasoning_tokens` / `content`. If 8192 answers it, FP8's verdict becomes "needs a bigger budget" and
  the ≥37/37 bar is re-read **with the budget stated**; if it still loops, the loop is a tier property.
  **(2) INT8 tier** — the last untried sibling (4.45 GB per the card). Author it as a copy of the FP8
  recipe with `model:`/`model_revision:`/`served_model_name:` swapped (**check the Hub repo id first**;
  no `--quantization` flag), then the same pre-registered bar as FP8: loads AND house ≥ 37/37
  thinking-on @4096 AND C1 ≥ **20.38 ± 0.09**, else measured-rejected. **(3) The clamp cell the ladder
  never reached** — `--max-running-requests 96` vs `32` measured **no delta at c ≤ 10** (c1 20.75 ± 0.40,
  c2 48.46 ± 1.22, c5 96.31 ± 6.57, c10 156.94 ± 0.47; every delta inside 1σ, c10 +0.5 %), because ten
  streams never approached the clamp. To justify 96 at all, run a ladder profile with
  `concurrency: [32, 48, 64, 96]` at pp 2048 / tg 128 / n=5 / decode rows only, and quote the pool
  arithmetic: **723,730 pooled tokens ÷ 96 ≈ 7.5k per sequence at full occupancy** (743,780 measured at
  96). Nothing here blocks the TP=4 block — all three wait for a free node. *(effort: short each;
  pre-registered 2026-10-22)*

## cybersec
Cybersecurity-research (red-team) abliterated / uncensored models
- [ ] **Unblock the two cybersec negatives via their card-documented vLLM routes** *(2026-10-15: both routes now ship as recipes — `nex-n2.5-mini-uncensored-nvfp4-vllm.yaml` and `qwen3.8-flash-next-uncensored-nvfp4-vllm.yaml`, pinned `9f11be0e`/`cd56f6c1`, `--quantization compressed-tensors` on the resident `dgx-vllm-eugr-nightly@sha256:7717585a…`; commit `202f482`. The distribution gate that blocked them is superseded (direct pull measured 76–142 MB/s). Weights pre-staged on `.34`/`.35` 2026-10-15 (`~/benchmarks/_prefetch-20261015/`, 23.95 GB + 183.54 GB on **both** `.34` and `.35`, verified complete; index rows still gated on a boot receipt.)* — arm 3 (`nex-n2.5-mini-uncensored-nvfp4-sglang`; SGLang NaN sample-time logits) via its image-distribution route; arm 4 (`qwen3.8-flash-next-uncensored-nvfp4-sglang`; SGLang's compressed-tensors loader refuses the export's scheme) via the `qwen4_exp` route, whose sole measured obstacle is the ~0.3 MB/s OCI relay. **Their index rows return only on a boot receipt** — they were dropped on 2026-10-14 when the index adopted *shipped = bootable and usable*, while the files stayed in `recipes/cybersec/` *(Owner decision 2026-10-15: unblock both; retirement to `attic/cybersec/` rejected — the reconcile item folded in here.)* (`recipes/cybersec/README.md:86-122`; `attic/cybersec/AGENTS.md` §8; `README.md` §Cybersec; precedent `recipes/glm/README.md:18-24`) *(effort: long)* *(nex vLLM booted 2026-10-15, four bounded boots, receipt `~/benchmarks/cybersec-nex-20261015/`: the card's route works — HTTP ready at TTR 257.6 s, `/v1/models` = repo id, engine `0.32.0rc1.dev161` — but generation degenerates to a single repeated token in every probe (greedy and sampled, thinking-on and answer-channel, `reasoning_tokens` 96/96 and the trace never closing at 800 tokens), so the route gate is closed and the *checkpoint* is what blocks the arm: recipe stays as the route record, no index row. The recipe's documented `reasoning_effort: none` is inert on this route and `enable_thinking: false` is the working switch, now shipped. `qwen3.8-flash-next-uncensored-nvfp4-vllm` is still unbooted.)*

  *(progress 2026-10-19 — **the vLLM route is measured NOT BOOTABLE on the pinned image.** Two
  launches on the `.34`/`.35` pair, ~31 min each: both die at model load with
  `ValueError: Found different quantization schemes for the shards of
  language_model.model.layers.3.self_attn.qkv_proj` (compressed-tensors `should_ignore_layer`).
  Mechanism: `vllm/models/qwen4_exp/nvidia/model.py:703` maps `qkv_proj` onto four shards including
  the bf16 `indexer.index_qk_proj`, which the export keeps unquantized (no `weight_scale` in the
  tensor map), and a fused linear cannot carry two schemes. The LoRA escape is written but does not
  work — `model.py:726`/`qsa.py:508` swap the mapping after `get_quant_config` has captured it, and
  `-o extra_args="--enable-lora"` (confirmed in the engine's non-default args) fails identically.
  Unblocking is image-side, and *Owner decision 2026-10-19 chose the image bump*: find a vLLM build
  whose mapping excludes ignored shards, validate it on the two shipped vLLM lanes first, then re-boot
  this arm. **Done:** upstream PR **#62318** is the fix and is still unmerged (checked 2026-10-19);
  the regression is **#59533** (merged 2026-10-05, first released in v0.32.0). The recipe now pins the
  **b12x build** (`sha256:cf5a2a53…`), whose source predates #59533 (three-shard mapping, indexer a
  separate BF16 GEMM) and which the qwen4 lane's solo arm already runs with a full suite; a
  `vllm-openai:v0.31.0` aarch64 digest is the fallback. The retry is pair-bound and waits for both
  nodes. Receipt
  `~/benchmarks/cybersec-flashnext-20261019/REPORT.md`; lane note in `recipes/cybersec/README.md`.
  No index row.)*

  *(progress 2026-10-21 — **both candidate engines are refuted, on two different gates.** Weights:
  verified complete on both nodes (18/18 shards, 183.48 GB `.34` / 183.43 GB `.35`), so staging cost
  nothing and the boot's distribution read `done (10.6s)`. The two shipped b12x pooling lanes
  (embed 2048-dim smoke, rerank `--fail-on-uniform`) pass on `cf5a2a53…`. Then: **(1) b12x
  `cf5a2a53…` = vLLM `0.1.dev21830+g8244d1c44.d20261015` cannot construct the model config at all** —
  `ModelConfig` `ValidationError: The layer_types entries must be in (…, 'linear_attention') but got
  [… 'qwen_sparse_attention' …]`; the checkpoint is 48 layers over exactly `{linear_attention,
  qwen_sparse_attention}` (`qwen4_exp`). No weight read, no quantization-mapping question reached.
  **(2) `vllm/vllm-openai:v0.31.0@sha256:c1c9f6fd…` (local ID `bbe70450…` on both) clears ModelConfig**
  — multi-modal warmup and NCCL `world_size=2` run — **then dies at worker init**:
  `NotImplementedError: Qwen4Exp PLE embedding does not support quantization config
  CompressedTensorsConfig`. Also new: `vllm-openai` declares `ENTRYPOINT ["vllm","serve"]`, so this
  image needs `executor_config: {entrypoint: ""}` (one-off `-o entrypoint=`) — the b12x image did not.
  Verdict: the re-route is refuted for **both** named builds; what is needed is an image with
  `qwen_sparse_attention` *and* a PLE-embedding-aware compressed-tensors path, i.e. an image search,
  not a recipe knob. Scratch variant lives git-ignored at
  `.scratch/flashnext-v0310/…` (shipped recipe untouched); receipts
  `~/benchmarks/cybersec-flashnext-b12x-20261021/{boot.log,boot-v0310.log,v0310-serve.log}`; both
  attempts stopped by task id and the pair returned to 0 containers each time.)*

- [ ] **Research `IndrasMirror/DeepSeek-V4.1-Flash-1017-XQ-Uncensored`** — a *strata*-format GGUF
  mixed-tier quant of the 1017 body, the XQ rename of the same pipeline as the
  `kaushikvira/…-GSQ-agentic-strata` item above (identical header `general.name`), which ships **no
  Engram tables** — only two placeholders that send you to the 1017 base for **203 GB** of shards.
  **Research only, not queued for a boot** — 1017-class work needs the four production nodes, which
  are frozen, and a TP=4 measurement needs the owner's offsite switch.
  *(facts:* open (`gated: false`), card `license: mit`, one branch `main` @ `9d3c01d8…`, no tags,
  created 2026-10-18T10:14:56Z (initial commit `c3cf92c7…`), last write 2026-10-19T18:17:06Z, card
  headed "Builds in this repo (20 Oct)". Hub `usedStorage` **329,277,851,840 B = 329.28 GB /
  306.7 GiB** over 49 files, in **two complete builds** that are plain byte-split parts —
  `v3/V41-XQ-1017-v3.gguf.part-01..16-of-16` **162,954,903,552 B = 162.95 GB / 151.76 GiB** (15 ×
  10 GiB + 1.89 GB) and `v2/…part-01..15-of-15` **152,239,341,568 B = 152.24 GB / 141.78 GiB** (14 ×
  10 GiB + 1.92 GB), rejoined by `v*/reassemble.sh`, which states they are "plain byte ranges of the
  original file (`cat` order = part number), **not llama.cpp gguf-split shards**" and checks
  `SHA256SUMS` before joining; plus `V41-MTP-Vision-1017.gguf` 8,421,868,640 and its `.Q2_K.gguf`
  5,661,492,320. **Not an overlay, and not self-contained:** it carries no safetensors of its own,
  and `model-00047/00048-of-00048.safetensors.NEED-TO-DOWNLOAD-ENGRAM.txt` (1,109 B each) are
  placeholders for the two **101.5 GB** Engram table shards, "unchanged from the original
  checkpoint", to be pulled from `deepseek-ai/DeepSeek-V4.1-Flash-1017` (open) and extracted with the
  author's tool — the lane's own `tools/build-dsv41-engram.py` builds the same tables at **188.8 GiB**
  (2 × 94.4 GiB). **No `config.json` at any path**, so the only `quantization_config` is the one
  embedded in the GGUF KV — and it describes the *teacher*, not these weights: `{"activation_scheme":
  "dynamic", "expert_dtype": "fp4", "quant_method": "fp8", "scale_fmt": "ue8m0",
  "weight_block_size": [32, 32]}`, **no `kv_cache_scheme`**, beside `architectures:
  ["DeepseekV41ForCausalLM"]` and `model_type: "deepseek_v41"` (GGUF `general.architecture` =
  `deepseek41`, `alignment` 16384, ctx 1,048,576, `rope_scaling.factor` 16.0 over
  `original_max_position_embeddings` 65,536). The shipped scheme is the KV string
  `deepseek41.quantization` = "routed experts: per-expert Q3_K / Q2_0 / PTQ1_0 (gate+up share a type,
  down its own); Q8_0 attention / shared / head; F16 embedding", with `strata.v41.expert_tiers` =
  `{"down:PTQ1_0": 5603, "down:Q2_0": 7060, "down:Q3_K": 2697, "gu:PTQ1_0": 6942, "gu:Q2_0": 5665,
  "gu:Q3_K": 2753}` (15,360 + 15,360 = 40 layers × 384 experts) and `strata.v41.expert_layout` =
  "uniform role: ffn_<role>_exps.weight; mixed: ffn_<role>_exps.<type>.weight per type (experts in id
  order) + I32 ffn_exps_{gu,down}_type[384]" — the header's own census is 1,329 tensors, **120 each**
  of ggml type 11 / 42 / 143 (9 per layer: gate, up, down × 3 tiers, so **42 = Q2_0 and 143 = PTQ1_0
  are ids outside ggml's table**), 493 F32, 321 Q8_0, 110 F16, 80 I32. "XQ" is the card's own rename:
  "the codes themselves come from **GPTQ**, not from GSQ's Gumbel-softmax optimisation. So it is
  renamed **XQ** (Xolotl Quant), our own method: this build is XQ's first stage (GPTQ + our
  budget-exact 'RCO-lite' tier allocation)" — though the header records
  `strata.v41.expert_source` = `inplace:rtn:q2_0:491a0b0a…`, i.e. an RTN q2_0 seed, not a GPTQ fit;
  unexplained, recorded as-is. **"Uncensored" rests on one sentence:** "We applied a
  **mrfakename-style rank-2 refusal-direction edit** to the 1017 checkpoint, on the attention output
  projection and the shared-expert down projection (experts untouched). The manifest id is
  `adea0515bbf69a0b`. The edit is applied before quantization to the dense half in full precision. A
  refusal-direction probe on the served quantized model is **to be measured**; this card does not
  claim a refusal rate until that probe is run." The artifact agrees
  (`strata.v41.ablate` = `adea0515bbf69a0b`) — but the card's own Quality section then reports
  "chat mode **0/100 harmful refused, 0/100 safe refused**; think mode **0/50 harmful, 0/50 safe**"
  from an opening-phrase classifier, which is the claim the edit section says it is not making.*)
  *(why it matters:* it is the **smallest 1017-class body** on the Hub — 162.95 GB at 2.093 expert
  bpw against 210.8 GB (EXL3 2.9 bpw), 382.8 GB (the GSQ sibling) and 510.3 GB (official) — and the
  arithmetic per node (128 GB unified, the lane's **108 GB usable** at util 0.85): weights alone are
  **40.74 GB / 37.94 GiB per rank at TP=4** and **81.48 GB / 75.88 GiB at TP=2**, both inside the
  budget, while TP=1 needs **151.76 GiB** and therefore the engine's VRAM/pinned-RAM/NVMe tiering
  rather than a bigger node. Add the tables and it stops fitting: **+47.2 GiB/rank at TP=4** (the
  knapcio arm's per-rank layout, 2 × 23.6 GiB) or **+94.4 GiB/rank at TP=2** — 170.3 GiB/rank at
  TP=2, 1.7× the 100.6 GiB pool, so the tables would stay on disk exactly as the ds4 arms keep them,
  at ~366 GB/node staged against the TP=2 EXL3 arm's ~385 GB/node and knapcio's 510 GB over four.
  So node count is not the constraint; a **loader is**. *(blockers/unknowns:* **no loader in either
  engine this lane ships.** The SGLang side reads safetensors trees through compressed-tensors
  (`recipes/ds4/README.md:25-28`, the knapcio overlay) and the TensorFold side loads EXL3 mul1
  through `mods/tensorfold-dsv41-launcher` (`recipes/cybersec/…-tp2-tensorfold-sglang.yaml` +
  `mods/graft-dsv41-ablit-wo-b`); there is **no `gguf` string anywhere in `mods/`,
  `recipes/cybersec/` or `recipes/ds4/`** (grep, 2026-10-20), and the registry's only GGUF runtime is
  `runtime: llama-cpp` (`recipes/explore/mellum2.1-12b-a2.5b-q4km-thinking-llamacpp.yaml:4`), which
  the card excludes outright: "This file is **not** a llama.cpp / Ollama / LM Studio GGUF. It uses
  per-expert quant types those runtimes don't load. Use it with Xolotl." Its engine is
  `Indras-Mirror/Xolotl` (MIT, C++, 225★, pushed 2026-10-20; it absorbs `Strata-DSV4.1`) and its
  README states one host, "Linux, an NVIDIA GPU with 24 GB, CUDA 12.x/13.x, and RAM for the arena",
  measured on one RTX 4090 — **no TP flag, no sharding, no aarch64/GB10 build named**: a new engine
  family for this registry, not a recipe re-point. Same class of gap the GSQ item records. Other
  unknowns: the Engram **download is not shipped**, so the arm is not runnable from this repo alone
  (+203 GB); `base_model` is tagged 1017 but the GGUF's `general.source.url` is
  `dealignai/DeepSeek-V4.1-Flash-UNCENSORED-FP8` (open, 510.3 GB) whose own base tag is the
  superseded `DeepSeek-V4.1-Flash` — the same provenance wrinkle as the GSQ build; the card's own
  quality gates are unfinished ("Per-layer … error … **to be measured**" rows, "First-token KL
  against the unedited base is not measured"), and it self-reports a **regression** on the short
  Gauntlet (2/5 against the V4.1 v2 build's 4/5, "03 at 0.00"); `tokenizer/chat_template.jinja` is a
  91-byte comment stub with `tokenizer.ggml.pre` = `joyai-llm`, so a port inherits the lane's
  template-less problem. All sizes are Hub `tree`/`usedStorage` bytes and GGUF header KV read by
  HTTP range; no node cache was read and no node was touched.)* *(effort: research only — a boot
  would need an aarch64/GB10 port of a new engine family first.)*

**Other surfaced arms (not queued):** `orcarouter/GLM-5.3-Flash-Uncensored-NVFP4` (321B, **205.1 GB** —
2-node-heavy/3-node; inherits the archived glm5 Flash serve blocker),
`orcarouter/DeepSeek-V4-Flash-Vision-Uncensored` (304B, `deepseek_v4`),
`drowzeys/keys-Qwen3.8-Flash-Next-NVFP4-dual-ablit-house-qsa-L3-47` (dual 180B ablit, **132.7 GB**; base
`nvidia/…` → license `other`), `drowzeys/keys-GLM-5.3-Flash-NVFP4-ablit-l15-43-mtp-l45` (169B, MIT),
`drowzeys/MiMo-V2.6-Flash-RL-Abliterated` (310B, FP8/MXFP4). **Over the 1–2-node bar, so recorded but NOT
queued:** `drowzeys/keys-MiMo-V2.6-Pro-RL-Jarrelscy-ARVQ-Abliterated` (`nvfp4_arvq_hybrid`, MIT, gated —
**315.7 GB** on-disk ⇒ ≥3 nodes; owner asked to add it only if it fit 1–2).

## Recipe schema & documentation (registry-level)
- [ ] **Sweep every recipe through `sparkrun run -n`** *(done 2026-10-21 for all 53 files: 46 renders clean, 7
  flagged — four are the launcher refusing TP=4 on a one-GPU host list (all four render clean on four hosts) and
  three are checker artifacts (two `pip install` chains in one command line; flags inside a load-bearing `#`
  comment). One genuine note recorded in `recipes/qwen3/README.md`: the mlx4bit arm's
  `speculative_draft_model_revision` pins the drafter for distribution while its own template means sglang's
  `--speculative-draft-model-revision` never renders — `unpinned-model-revision`-adjacent, not a boot risk. No
  recipe was edited on the sweep's strength. Receipt `~/benchmarks/render-sweep-20261021/REPORT.md` +
  `render-sweep.json`; the sweep itself re-runs from `.scratch/render_sweep.py`, which needs `sparkrun` on PATH
  and therefore can never become a `tests/` guard. Still open: repeat it after any render-affecting change.)*
- [ ] **Audit the house-battery budget behind every recorded score** *(done 2026-10-21: 42 of the 43
  `~/benchmarks/**/house*.json` receipts were taken at `--max-tokens 4096`; the only 1024 pass was the first
  Lightning run, and its single miss was a truncation (`11111` for `1111111110`, `finish=stop` at 2048). Every
  shipped arm's bar is a non-empty wrong-string miss, so nothing needs re-checking. Two durable findings: **the
  budget convention now lives in `tools/README.md` §`quality-battery.py`**, and **`hard-rev` is the near-universal
  discriminator** — `nurkrpas` / `nurkraps` / `nrukraps` / `nurkrasp` across seven-plus arms including both
  DeepSeek lines — so 37/37 in practice means "clears `hard-rev`", stated in `recipes/explore/README.md`. Seven
  empty-reply cases at 4096 are classified as indeterminate in that audit; the cheapest fix is to have the
  instrument record `finish_reason`, which is not yet done.)*

- [ ] **Register an arm64 self-hosted runner so the llama.cpp build job can run** — `.github/workflows/llamacpp-engine.yml` builds only when `vars.ARM64_RUNNER_ENABLED == 'true'`, and no such runner is registered, so the weekly job currently reports ref drift and feature gates without ever building; `tests/test_ci_workflows.py` guards the gate. This is the prerequisite for the stock-upstream image work (`recipes/explore/Dockerfile.llamacpp-upstream`, `5ce1d02`) and for the Mellum MTP A/B. *(effort: short, owner-side infrastructure)*

## Runtimes (registry-level)
Engine families the registry has not exercised. sparkrun 0.4.0 ships more runtimes than the two in use —
`sparkrun/runtimes/` holds `sglang`, `vllm_ray`, `vllm_distributed`, `trtllm`, `atlas`, `modular_max`,
`tokenary` and **`llama_cpp`** — while at the 2026-10-16 count every shipped recipe here was `runtime: vllm` or `sglang`
(0 llama.cpp arms in `recipes/` — **the first shipped 2026-10-17, `recipes/explore/mellum2.1-12b-a2.5b-q4km-thinking-llamacpp.yaml`, boot-verified**).

## Concurrency ladder (registry-level)
**The census below is the 2026-10-15 snapshot and is stale:** most text arms now carry a full ladder — ds4 (TP=2 and TP=4), ornith 35B/9B, all three qwen3 arms, IFM 0.9B/7B, explore laguna-XS and both mellum arms (bf16 + llama-cpp), cybersec arm 2 — and only these still read `—` for C2/C5/C10 in `README.md`: qwen4's TP=1 solo arm, explore ling / kolibri / laguna-S, and cybersec arm 1 (orcarouter). `humanizer` needs no ladder — its `—` is by design, because the arm serves `/v1/completions` only and the ladder profile drives `/chat/completions` (`recipes/explore/README.md:148-151`). **Do not fill cells from the wrong receipt:** `attic/ds4/PERF-ISSUES.md:49-52`'s c1/c2/c5/c10 table is a cold-prefill triage on a different harness (its d0 c1 is 36.2, not the index's 46.5) and `attic/ifm/NOTES.md`'s c=2 53.697 belongs to the withdrawn 36B arm.
- [ ] **Fill C2/C5/C10 for the single-node text arms** *(ornith 35B done 2026-10-15: C2 158.2 / C5 220.4 / C10 249.9 t/s @ d0, σ 6.2/10.0/4.6, `bench_8c7486cad451`; 9B done 2026-10-15: C2 101.1 / C5 159.0 / C10 148.9 t/s @ d0, σ 8.3/7.8/4.8, `bench_92725c90d298`)* — the 14 that fit one Spark (ornith 35B/9B, qwen3 dflash2/coder-next/mlx4bit-TensorFold, IFM 0.9B/7B, explore ling/kolibri/laguna-XS/laguna-S/humanizer, cybersec arms 1/2) on the free `.34`/`.35`; per cell quote the **decode** row of the `--output` file (never the printed table, which shows only that row and no header) and cite the receipt beside the number in `README.md` and the lane doc. *(effort: long)* *(progress 2026-10-15: IFM 0.9B (C1 80.4 / C2 181.6 / C5 317.6 / C10 503.9) and 7B (31.3 / 56.1 / 94.0 / 126.0) done — receipts `~/benchmarks/ifm-{09b,7b}-ladder-20261015/`, docs in `recipes/ifm/README.md` + `attic/ifm/NOTES.md` (commit `84aa52f`); **2026-10-16: qwen3 coder-next done** — C1 70.4 / C2 114.0 / C5 177.1 / C10 249.5 t/s @ d0, σ 0.2/2.6/14.9/3.9, decode rows read from `benchmarking/concurrency-ladder.yaml`'s `--output`; receipt `~/benchmarks/pins-20261016/qwen3coder-ladder.yaml`; index row filled and the lane README carries the ladder plus the shape note. Remaining: qwen3 dflash2, explore ×5, cybersec ×2. **2026-10-17: the qwen3 mlx4bit-TensorFold arm done** — C1 44.8 / C2 57.7 / C5 64.4 / C10 65.6 t/s @ d0, σ 3.5/2.8/2.3/1.3, `bench_b10e422bb046`; the index row now carries all four cells and the lane README the ladder plus the scale shape (per-request decode falls 44.8 → 16.0, so the aggregate flattens past c5). **2026-10-17: the llama-cpp arm done** — C1 111.9 / C2 151.1 / C5 208.0 / C10 146.4 t/s @ d0, σ 0.3/2.6/2.8/1.5, `bench_4247926b7b9a`; the index row + lane README carry the four cells and the shape note (c10 runs 10 streams over the arm's 8 slots, so per-request decode spreads to 32.9 ± 16.1 and the aggregate falls past c5). Remaining single-node text arms: explore ling/kolibri/laguna-S, cybersec arm 1 (orcarouter), humanizer (needs the documented `—`: `/v1/completions` only, so llama-benchy cannot drive it). **2026-10-17: the qwen3 dflash2 arm re-measured and cybersec arm 2 (AEON) measured** — on `.35`, one boot each, `benchmarking/concurrency-ladder.yaml` with `--output`: dflash2 C1 29.6 ± 2.6 / C2 57.4 ± 3.3 / C5 89.5 ± 6.5 / C10 100.9 ± 3.4 t/s @ d0, `bench_355eee9f476f`; AEON C1 30.2 ± 1.5 / C2 49.4 ± 6.8 / C5 84.6 ± 9.1 / C10 92.9 ± 5.1 t/s @ d0, `bench_3ee8fda63ada`; receipt `~/benchmarks/ladders-solo-20261017/` (decode rows read from the `--output` JSON; values, per-request fall-off and the two-boot spread are in the rows and lane docs).)*
  *(Correction 2026-10-18 — the arm list above and its closing "Remaining" sentence are superseded: strike `humanizer` from both (its `—` is by design and already documented, `recipes/explore/README.md:148-151`), and add the two arms the list omits — qwen4's TP=1 solo arm and the mellum bf16 arm. Measured already: mellum bf16 ladder 2026-10-15 (C1 42.3 / C2 67.2 / C5 99.9 / C10 135.6 t/s @ d0) and the mellum llama-cpp arm 2026-10-17 (`bench_4247926b7b9a`), so neither is outstanding. Still lacking a ladder: qwen4's TP=1 solo arm, explore ling / kolibri / laguna-S, and cybersec arm 1 (orcarouter).)*
  *(Correction 2026-10-18, late — **that remaining list is itself stale; verified against the index rows, not against this register.** Measured since: qwen4 TP=1 solo (`bench_6b35f675861a`), explore ling (`bench_7c46291e9bbb`), kolibri FP8 (`bench_b0d57361b7d7`) plus each of the six pack/tier arms' own ladders, laguna-S (`bench_e3fdefdc2491`), and cybersec arm 1 plain (`bench_4c30a992c771`). What actually remains is two arms: the **cybersec NEXTN sibling** (`qwen3.8-27b-uncensored-nvfp4-nextn-sglang`, C1 14.72 only — one boot, `~/benchmarks/cybersec-nextn-20261018/`) and **qwen4 labquant-highcon**, whose `—` is deliberate: it is the aggregate regime, measured at d8192 k=16/24 rather than on the standard d0 ladder. `humanizer` stays `—` by design.)*
## Standard evaluation suite (registry-level)
- [ ] **Run the standard suite against every shipped arm** — the SOP pass (`tools/eval-suite.py`, then the `benchmarking/concurrency-ladder.yaml` leg `--skip-run` on the same boot, then `benchmarking/standard-suite.yaml` where the arm serves tool calls) for each shipped recipe; receipts under `~/benchmarks/<lane>-<date>/`, numbers into the lane docs and the index with their receipt/bench id. This is the sweep that fills the C2/C5/C10 cells above and each lane's unmeasured accuracy cells; start with the ornith 35B and work the free `.34`/`.35` window. *(effort: long)* *(progress 2026-10-15: ornith 35B done; IFM 0.9B/7B ladders measured; the decision-lane ensemble + ladder and the qwen3 27B headline suite both landed. **2026-10-16: the ornith 35B re-run in full** — eval-suite 1.0.1 `ok` (house 37/37; needle 3/3 at each of 32k/131k/262k), same-boot ladder C1 101.8 / C2 153.1 / C5 217.4 / C10 244.2 t/s, tool-eval-bench v2.6.0 **100** (15/15); receipts `~/benchmarks/ornith-35b-suite-20261016/`, rows in `recipes/ornith/README.md` + the index. **And the qwen3 coder-next arm** — one boot: pin + ladder (C1 70.4 / C2 114.0 / C5 177.1 / C10 249.5) + tool leg **90/100 (27/30)**, deployability 89, responsiveness 87, engine `vLLM 0.32.0rc1.dev301`; receipts `~/benchmarks/pins-20261016/`. **2026-10-17: the laguna-XS-2.1 arm's suite landed** — same-boot ladder C1 55.3 / C2 83.1 / C5 133.7 / C10 141.3 t/s (`bench_9b207347ec3b`), `tools/eval-suite.py` 3 ok / 2 fail (the fails: contract, all-empty reply at the 262,144 window; needle 2/3 at 32k and 131k but **3/3 at 262k** — the rope caveat's predicted long-window miss did not appear), TEB **97**; receipts `~/benchmarks/explore-laguna-xs-20261017/`, the index row + `recipes/explore/README.md` carry the numbers. **And the qwen3 mlx4bit-TensorFold arm** — one boot on `.35`: ladder C1 44.8 / C2 57.7 / C5 64.4 / C10 65.6 t/s (`bench_b10e422bb046`), house 37/37, needle 3/3 at 32k and 131k (the engine reports no `max_model_len`, so the auto depths stop at 128k), arc 94.0% / gsm8k 96.5%, TEB **100** (15/15); receipts `~/benchmarks/qwen3-tf-suite-20261017/` (+ `NOTES.md`). Its `tools` leg was killed at 3,878 s because the leg's Python-block-buffered log read as a hang; the fix (`678cb0c`, `PYTHONUNBUFFERED` in `tools/eval-suite.py`'s child env) landed mid-sweep; the leg re-ran unbuffered (4,487 s) and landed **85.7% (1063/1240)** in `~/benchmarks/qwen3-tf-tools-20261017/` (`parallel` 85.5%, `parallel_multiple` 72.0%). In the same window the first llama-cpp arm (mellum Q4_K_M, `recipes/explore/mellum2.1-12b-a2.5b-q4km-thinking-llamacpp.yaml`) booted in ~100 s with its `--alias` intact and ran the same legs on `.34` (results at the end of this paragraph). One operational trap worth carrying: a legs-runner waiting on `pgrep -f "tools/eval-suite.py"` never exits, because a peer's day-old watcher loop carries that string in its own command line — match a pid file or a unique marker, not a substring of a command line. **2026-10-17: the first llama-cpp arm (mellum Q4_K_M, `.34`) ran the full legs** — house 37/37 (easy 19/19, hard 18/18); needle 131k 3/3, and 32k 3/3 after two manual re-probes of the thinking-budget class (depth 50 PASS at `--max-tokens 4096`; depth 90 PASS with `enable_thinking:false`, 9 completion tokens); hard arc 77.0% / gsm8k 93.5% (n=200 each); tool-eval-bench **97** (15 scenarios, 14 pass, 1 partial); bfcl **73.5 % at the 512 default → 88.3 % at 4096** (`~/benchmarks/mellum-gguf-tools4096-20261017/`: 179 → 6 no-call in the two parallel categories, all six `finish_reason: length`, the residual loss multi-call shape); ladder `bench_4247926b7b9a`; receipt `~/benchmarks/mellum-gguf-20261017/`. **Queued:** a `--bfcl-max-tokens 4096` re-run of the qwen3-TensorFold tools leg — its 85.7 % came from the 512 default, so its row and lane doc carry a `‡` budget annotation meanwhile.)*
  *(progress 2026-10-18 — two legs landed. **ds4 knapcio TP=4, 1017 weights** (task `a2e141223b52793c_7afff0589a33`): house **36/37** (easy 19/19, hard 17/18; the miss is `hard-rev`), needle **3/3 at each of 32,768 / 131,072 / 983,040** (top rung 981,950 prompt tokens), tool-eval-bench **90** (15 scenarios: 13 pass, 1 partial, 1 fail `TC-03 wrong_args`, `benchmarking/standard-suite.yaml`), same-boot ladder C1 69.28 / C2 86.40 / C5 108.78 / C10 116.27 t/s; receipts `~/benchmarks/tp4-20261018/` — `REPORT.md` §4, `knapcio-suite/`, `knapcio-teb.{yaml,json,csv}`. **qwen3 coder-next re-run** (`.30`, job `3d9fbe520b47c3a3_2d38dfc4605e`), all four legs `ok`: house 36/37 (easy 19/19, hard 17/18, the same `hard-arith-2` miss), needle 3/3 at 32k/128k/**256k** (262k rung filled 97.7 %, the tool's calibrated target, no `TRUNCATED`), ARC-Challenge 92.0 % (184/200) / GSM8K 96.0 % (192/200); `--timeout 3000 --needle-max-tokens 512` were applied proactively and never needed (256k prefill ~129 s, suite 1,319 s); the `tools` leg skipped on purpose (TEB already 90/100 on this arm); receipt `~/benchmarks/qwen3-coder-next-suite-20261018/`.)*
  *(progress 2026-10-18, late — **IFM 0.9B: PARTIAL, not a pass.** One serve on `.31` (cluster `e2b91b75cf01d3ab_68907e0cb1d8`, TTR 74.6 s, served `IFM/K2-Horizon-0.9B` @ 131,072, recipe sha256 `3c93459e…`): **contract ok**; **house ok** — easy **17/19** (`fmt-2`, `needle-1`), hard **15/18** (`hard-rev`, `trick-1`, `trick-2`); **needle FAIL** — 0/9 cells answered, every reply `finish_reason=length` with all 256 tokens spent inside `reasoning_content` and empty content, i.e. the SOP's 256-token cap and **not** a retrieval result (the 32k ladder's own calibration probes truncated too, so `chars_per_token` fell back to 4.6 and it filled 46.5k for a 32,768 target — a 42 % overshoot); **hard ok but floors** — gsm8k 86.0 % (172/200, 11 `length` + 11 empty replies) and arc 68.5 % (137/200, 18 `length` + 18 empty), the reasoning block eating the budget; **tools CUT** — SIGTERM'd when `.31` was reclaimed for a TP=4 boot, **585/904 logged (64.7 %)** with `irrelevance` never started and no `bfcl.json`, so that tally is **not** this arm's BFCL score. No ladder on this boot (the arm's stands at `edd4029e004f`). A valid re-take needs `--needle-max-tokens >= 512` and a completed tools leg. Receipt `~/benchmarks/ifm-09b-suite-20261018/` (`REPORT.md`, `house.json`, `needle-*.json`, `hard/`, partial `bfcl.log`, 0-byte `suite.log`).)*

*(2026-10-19: the explore keeper sweep retired 10 arms, so the "~20 arms" tail above shrank —
re-count the survivors from the index before scheduling the sweep.)*

*(Owner decision 2026-10-19 — **the tools leg runs in full only where the lane's product needs tool
calling** (cybersec, qwen4, ds4, explore, ornith, qwen3, ifm, llama.cpp text arms); embed, rerank,
decision, media-gen and TTS arms carry "tools: not applicable" with that reason, which is what the
audit already recorded. The policy's practical effect is to confirm the N/A set rather than to shrink
the queue: every remaining suite arm in the tail is a text arm that qualifies, so BFCL's ~1.8 h per arm
(91 % of its per-check cap) still stands in the budget.)*

*(2026-10-19 audit — all 48 shipped recipes checked against their cited receipts: **7 COVERED ·
14 PARTIAL · 7 UNCOVERED · 20 N/A** (11 decision arms + 4 pooling + 1 media-gen + 4 documented
cybersec negatives, each with its own documented reason). Every cited receipt except one exists on
the head; the exception is the Ornith YaRN 1M arm's 2026-10-18 rung directory, whose five passing
rungs are therefore prose-only (the lane README concedes it; only the d90 negative is receipted).
Ordered tail, cheapest window first — the first three are 131k single-node: (1) `k2-horizon-0.9b`
needle re-take at `--needle-max-tokens 512` + tools; (2) `k2-horizon-0.9b-uno` contract+needle;
(3) `k2-horizon-7b-fp8-uno` contract+needle **on the shipped fa4/bf16 line** (the 36/37 on file is a
triton+fp8-KV override); (4) cybersec 27B uncensored · (5) cybersec 27B ablit · (6) cybersec 27B
NEXTN — contract/needle/ARC/GSM8K/TEB; (7) kolibri APEX-24bpw needle/hard/TEB; (8) laguna-XS
contract+needle (fix the empty-`content` shape first); (9) qwen3 MLX4bit needle at 262k (explicit
`--needle-lengths`; the engine reports no `max_model_len`); then the two-node arms (laguna-M.1 after
`#45`, qwen4 highcon, the two qwen4 probes) and the four-node arms (ornith 397B, both GLM quality
batteries, ds4 knapcio's ARC/GSM8K leg). Doc corrections from the same audit: qwen3-coder-next's
house number is **36/37** (receipt), not 35/37 — fixed; qwen4 highcon's "no accuracy evaluation
exists for this export" was stale — fixed to name the base arm's suite; ds4 TensorFold's "17/18
house hard" is the gateway harness, not `eval-suite` — the register now distinguishes them.)*

*(progress 2026-10-19 — the tail started with the cheapest arm, `k2-horizon-0.9b-bf16-sglang`
(131k, one node, TTR 75.6 s). Needle re-take at `--needle-max-tokens 512` improved the 0/9 the
256-token cap produced to **32,768: 3/3 · 131,072: 2/3** — still one miss at the arm's edge, so the
needle leg remains FAIL and the 0.9B arm stays PARTIAL. The tools leg first 404'd because it was
invoked with `--base-url .../v1`: the suite's documented convention is the endpoint **root**, and its
contract check appends `/v1/...`, so the `/v1` spelling built `/v1/v1/models`. That was a caller error,
not a latent defect - the receipts' tools legs had only ever been *skipped* for a missing
`--bfcl-data-dir`. The tools now accept either spelling (`api_root`, with a selftest control) so a
caller following the lane docs cannot hit it again, and the leg is re-running against the live arm;
receipt `~/benchmarks/ifm-09b-suite2-20261019/`. **Its BFCL leg then hit the suite's own 2 h
per-check cap** (`[suite] TIMEOUT after 7200s`): simple/multiple/parallel completed and it was still
in `irrelevance` at the cap, so this arm's tools leg is *measured-unmeasurable within the cap* at
`--bfcl-max-tokens 4096` — record that rather than a score; a reduced-category or lower-budget run
would answer a different question. .35's 7B tools leg runs the same profile and will settle whether
the cap or the model is the binding constraint.)*

*(progress 2026-10-19, later — **the 7B narrows it: the cap is marginal for this class of arm, not
free.** `k2-horizon-7b-fp8-uno-sglang` ran all five legs to `ok` on the shipped fa4/bf16 line:
contract 131072, house **36/37** (19/19 + 17/18), needle **3/3 at 32k and 131k**, ARC **181/200** and
GSM8K **189/200**, tools **1079/1239 (87.1 %, 1 transport error)** — but the BFCL leg took **6,555 s
of the 7,200 s per-check cap (91 %)** and the suite 9,805 s, so the cap nearly bound this arm too. Against the fp8-KV override's 36/37 · 188/200 · 179/200 the shipped line is +0/+1/+2, so the
triton+fp8 detour bought no accuracy and the shipped bf16 configuration is the measured one; the
lane README carries the paragraph and the index row its pointer, receipt
`~/benchmarks/ifm-7b-uno-shipped-20261019/`. Tail item 3 closed. **Tail item 4 (27B uncensored) and
item 5 (27B ablit) are booted and running one suite each**, on `.34` and `.35` respectively.
*(Interruption 2026-10-19 18:25 ET — **the 27B-uncensored arm cannot finish BFCL inside a 3 h cap.** Its
phase timings: suite start 14:55, house+needle+hard 2 h 41, then BFCL at **17.8 s/question** (155 in
46 min) — 1,239 questions is ≈6.1 h, so the 10,800 s cap I launched it with would have killed the leg at
~600. Killed deliberately at 46 min and restarted as a tools-only run on the same live serve with **no
job cap** (`bfcl-eval` under `setsid`, `--max-tokens 4096`, outdir
`~/benchmarks/cybersec-27b-unc-tools-20261019/`); the arm's other four legs are already on disk in
`cybersec-27b-unc-suite-20261019/` and are merged into one record at the end. The 27B-ablit sibling is
**not** at risk: it runs 5.2 s/question (dflash2) and finishes its 1,239 inside 1.8 h. Lesson for the
tail: price BFCL at the arm's measured rate before setting `--job-timeout`, not at the 7B's.)*

*(Suite results 2026-10-19 — **27B-ablit (arm 2) closed four of five legs**: house 37/37, ARC
184/200 (92.0 %), GSM8K 187/200 (93.5 %), tools 1064/1240 (85.8 %) in 8,978 s; needle is submitted
as `fail` because the 262,144 rung truncated inside the 512-token answer budget while answering 3/3 at
32,768 and 131,072 — an instrument verdict, recorded as such in the lane README. The 27B-uncensored
(arm 1) sibling finished house 37/37, needle 3/3 including 262,144, ARC **187/200 (93.5 %)** and GSM8K
**194/200 (97.0 %)**; its tools leg is the cap-free re-run described above. Both arms' ladders (NEXTN's
C2/C5/C10 and highcon aside) are the last registry gap for the pair.)*

**Correction (same day):** the BFCL leg took 6,555 s, not the "1,383 s / a quarter of the cap" first
written here — the per-check cap was at 91 %, so a 4096-token BFCL run sits close to its budget on this
arm family, and a larger thinking model would exceed it.)*


*(progress 2026-10-19 — **qwen4 labquant TP=2** landed both legs on one boot: eval-suite `ok` — contract `max_model_len=262144` / ready / `finish=stop`, house 19/19 + 18/18, needle 3/3 at 32k / 128k / 262k, hard ARC 95.5 % and GSM8K 95.5 % (n=200 each) — and tool-eval-bench **100** (15/15 scenarios, 0 partial, 0 fail, `bench_eff75293e461`, 91.6 s); receipt `~/benchmarks/qwen4-labq-suite-20261018/`, rows in `recipes/qwen4/README.md`. The needle leg needs `--needle-max-tokens 512` on this export: at the 256 default every cell is reasoning-only, the same trap the IFM 0.9B pass hit.)*

*(progress 2026-10-20 — **27B-NEXTN (arm 1's spec-decode sibling) closed all five checks and its
ladder.** Suite verdict `fail` on the needle leg only, 23,600 s (sum of the per-check `seconds`;
23:32:04Z→06:05:25Z): contract ok 2.1 s (`max_model_len=262144`), house **37/37** 129.6 s, needle
**32k 3/3 · 131k 3/3 · 262k 3/3** 1,421.2 s with the 262k rung **TRUNCATED** at a 163,455–164,153-token
prompt against the arm's **167,985**-token pool, hard **ARC 187/200 (93.5 %) · GSM8K 194/200 (97.0 %)**
3,383.6 s, tools **1073/1240 = 86.5 %** in **18,663.6 s = 15.05 s/question**; same-boot ladder
`bench_e66cbef09760` **C1 15.39 ± 0.90 · C2 28.81 ± 1.24 · C5 60.35 ± 3.54 · C10 102.82 ± 7.77 t/s**
@ d0, pp 2048, tg 128, n=5 (means from the `ladder.csv`/`ladder.json` sidecars). Receipts
`~/benchmarks/cybersec-27b-nextn-suite-20261019/` and `~/benchmarks/cybersec-nextn-20261020/`. That
serve was then stopped and **kolibri APEX-24bpw booted on `.35`** (`bc1ee4356daa935d_64af2f7668b6`,
`n_ctx_slot=262144`, `kv_unified=true`, model loaded 22.8 s per `boot.log`) with the suite
(contract/house/needle/hard/tools, `--needle-max-tokens 512`, `--job-timeout 21600`) writing
`~/benchmarks/kolibri-apex-suite-20261020/`. Per-arm tools cost now measured — plain 22.5 s/q, NEXTN
15.05, dflash2 7.2, 7B UNO 5.3 — which is what a suite's `--job-timeout` is priced from.)*

*(progress 2026-10-20, later — **27B-uncensored (arm 1) closed its tools leg, and kolibri APEX landed
four of five checks.** Arm 1 BFCL **1072/1240 = 86.5 %, 0 transport errors**, 1,240 records; the leg ran
18:24:02→04:46:48 = **37,366 s = 30.1 s/question**, so the plain-decode arm's real cost is ~10.4 h, not
the 7.7 h extrapolated from its first 907 questions (a buffered log read at 22.5 s/q under-called it by
~50 min). Category split: simple 369/400 · multiple 187/200 · parallel 183/200 · parallel_multiple
168/200 · irrelevance 165/240. **Its `--json` target directory did not exist**; `bfcl-eval` writes with
a bare `open()` (`tools/bfcl-eval.py:1068`), so the score would have printed and then raised
`FileNotFoundError` — the directory was created at 00:58 and the JSON landed. Receipt
`~/benchmarks/cybersec-27b-unc-tools-20261019/bfcl.json` (legs in `cybersec-27b-unc-suite-20261019/`).
That serve was stopped and **laguna-XS 2.1 NVFP4 booted on `.34`** (`a20dad9f9e2c72ca_8ed3ce77d78f`,
`poolside-laguna-xs-2.1-nvfp4-dflash-vllm.yaml` — the `-sglang` name does not exist; READY 04:53:09,
served id `poolside/Laguna-XS-2.1-NVFP4`, `max_model_len` 262144) with its suite at
`--job-timeout 28800` writing `~/benchmarks/laguna-xs-suite-20261020/`. **Kolibri APEX-24bpw** on `.35`:
house **37/37**, needle **3/3 at 32,768 / 131,072 / 262,144** — the 262k rung is a *real* pass at
`n_ctx_slot=262144`, the first top rung tonight that is not truncated — hard **GSM8K 176/200 (88.0 %)**
with 21 `length` finishes and **ARC 171/200 (85.5 %)** with 23, both floor-limited by the answer budget;
tools measured at **3.63 s/question** over its first 513 questions (≈4,501 s for 1,240, well inside the
21,600 s cap). Its `/v1/models` advertises `capabilities: ["completion"]` only, yet it emits structured
`tool_calls` (861 pass / 98 fail at 959 questions, every failure an argument error — none a missing
call): that listing field is cosmetic in llama-server and is **not** evidence of absent tool support.)*

*(progress 2026-10-20, 05:32 ET — **kolibri APEX-24bpw closed all five legs `ok`, 11,878 s total**, and
the qwen3 MLX needle re-take is booted. `summary.json`: contract 1.4 s (`max_model_len=262144`, but its
own readiness probe returned `ready=False finish=length` — the reply spent the budget in reasoning, so
that leg's `ok` is the length check and not a readiness proof), house 133.4 s **37/37**, needle 1,377.7 s
**3/3 at 32,768, 131,072 and 262,144** (**a real top rung** at `n_ctx_slot=262144` — the first arm
measured here whose 262k cell is not truncated), hard 3,939.8 s **ARC 171/200 = 85.5 %** and **GSM8K
176/200 = 88.0 %** (both **floor-limited**: 23 and 21 `length` finishes at the 512-token answer budget),
tools 6,425.7 s **1056/1240 = 85.2 %** (5.2 s/question). Receipt
`~/benchmarks/kolibri-apex-suite-20261020/`; lane rows in `recipes/explore/README.md`. No ladder: the
arm's is already receipted (`bench_d165fa4b0bea`). That serve was stopped (0 containers verified) and
**qwen3.8-27b-mlx4bit-tensorfold booted on `.35`** (`fe3054ad67464c54_64af2f7668b6`, READY 05:37:28)
with a needle-only run at 262,144 (`--needle-lengths 262144 --needle-max-tokens 512`, the engine
publishes no `max_model_len`) writing `~/benchmarks/qwen3-mlx-needle-20261020/`.)*

*(progress 2026-10-20, 05:56 ET — **laguna-XS's 59.8 % tools score is a capability result, not a parser
bug**, and the qwen3 MLX needle rung truncates below its advertised window. Laguna-XS re-take
(`~/benchmarks/laguna-xs-suite-20261020/`, 3,273 s, suite verdict `fail` on contract only): house
36/37, needle 3/3 at 32k/131k/262k, hard ARC 62.0 % / GSM8K 93.5 %, tools **742/1240 = 59.8 %** in
1,673 s with 0 transport errors. The loss is concentrated: **`parallel` 0/200 and
`parallel_multiple` 0/200, every one `parallel_function_checker_no_order:wrong_count`**, while simple is
369/400 and multiple 189/200. The records settle the mechanism — each of those 398 responses carries
**exactly one** `calls` entry (histogram over the two multi-call categories: 1 → 398, 0 → 2) with
`error: ['Wrong number of functions.']`, and the visible `content` acknowledges both requests while
emitting only the first call. Structured calls parse fine on this arm (558 single-call questions passed)
and the serve line carries `--tool-call-parser poolside_v1`, `--reasoning-parser poolside_v1`,
`--enable-auto-tool-choice` and `--default-chat-template-kwargs '{"enable_thinking": true}'`, so no flag
is missing: the arm emits one tool call per turn and a re-run would reproduce it. Its contract leg fails
with `finish=length`, `content_len 0`, `reasoning_len 0` over 64 tokens — the empty-`content` shape the
arm has shown since 2026-10-17. **qwen3.8-27b-mlx4bit-TensorFold needle at 262,144** (needle-only,
`--needle-lengths 262144 --needle-max-tokens 512`, 916.8 s): **3/3 needles retrieved but verdict
TRUNCATED** — the server counted 222,453 and 222,514 tokens for the 262,144-token request at depths 10 %
and 90 % (only the 50 % depth reached 261,527 and PASSed), so this arm's real window is ~222.5k and the
262k cell is an instrument verdict, not a retrieval miss (`~/benchmarks/qwen3-mlx-needle-20261020/`).
That serve was stopped (0 containers verified) and **ornith-1.5-35b-a3b-nvfp4-yarn-1m booted on `.35`**
(`dadfb04b5145d956_64af2f7668b6`, READY 05:55:54, served id `ornith-ai/Ornith-1.5-35B-A3B-NVFP4`,
`max_model_len` 1,000,000) for the depth-90 % 1M re-take, with the register's failing-boot capture armed
this time: `docker exec <c> tail -F -n +1 /tmp/sparkrun_serve.log` → `serve-stream.log` and
`docker events --filter event=die` → `docker-events.log`, both inside the receipt dir.)*

## Image pins and advisories (registry-level)

- [ ] **Sanitize cluster-internal addresses out of tracked files** — a history-wide audit on 2026-10-20
  scanned `git log -p --all` and `git log --all --format='%h %s%n%b'` for fabric IPs, the CX7 RoCE
  subnets and `spark-*.<internal-domain>` names. It found **221 patch-body lines across history and 8
  commit-message lines**, and confirmed the two by-design-ignored paths (`mad-science/REPORT.md`,
  `.local/`) were **never tracked**. The live exposure is the *current tree*, not only history: attic
  lane docs, the ds4 benchmark harness under `recipes/ds4/benchmarks/`, one glm launcher README, and
  fixture/docstring uses in `tests/`+`tools/`. Pushed history is deliberately **not** rewritten (no
  force-push); the non-rewriting fix is one sanitizing commit over the working tree, with the history
  rewrite a separate owner decision. *(effort: short)*
  *(progress 2026-10-20 — **the tree is clean; history is not, and is left alone.** Masked with the
  repo's own rule (`.omp/skills/sparkrun-tracked-file-ip-hygiene/SKILL.md`): RFC1918 literals become the
  `.30`-`.35` node shorthand, fabric words become "the CX7 plane-A/B subnet", the internal head hostname
  becomes `<head-node>`, upstream-template placeholders become `<master-ip>`, and the four hostnames in
  the identity map and in a tuning `metadata.json` become their shorthand nodes. **71 lines across 22
  tracked files held a literal; 0 do now** (per file: the two ds4 benchmark raw logs 12 each, the ds4
  lane AGENTS.md 5, `tests/test_cache_audit.py` 10, `tools/cache-audit.py` 5,
  `tests/test_glm_launcher_shim.py` 5, the ds4 benchmark README 4, and one to three each in 15 further
  files: attic lane docs, a glm launcher README, the ds4 harness scripts, `tools/decision-ladder.py`).
  **One exemption, decided by evidence:** `recipes/ds4/benchmarks/data/hle_test.jsonl:121` is a
  benchmark question that happens to discuss a private network in its prompt — it is data, not our
  fabric, and masking it would corrupt the eval. **Two coupled fixture changes:** the census fixtures in
  `tests/test_cache_audit.py` + `tools/cache-audit.py` could not take the `.NN` shorthand because the
  parser rejects a leading-dot token as a host (the merge test then produced 3 rows instead of 2), so
  they carry `host-30`-style names instead, assertion and fixture changed together; the glm shim fixture
  takes `.30:25000` unchanged in behaviour. Gate after the change: **752 tests OK** (2 skipped), **51/51**
  plain validate, `bash -n` clean. **History:** the earliest commit that already carried a literal is
  `ee973cd` (2026-09-18, "Close labquant blocker (e)…", first `10.0.4.`); the CX7 subnet form enters at
  `c441141` (2026-10-02, ds4 knapcio). Both are published; rewriting them needs a force-push, which is
  **not** done — the exposure record ends here unless the owner elects a rewrite.)*

**Advisory pass 2026-10-15 — what was checked and found clean** (method: `api.osv.dev` package queries per version, then a version bisect against upstream release dates; only public upstreams are covered — the `littlecedar/*`, TensorFold and miaai-lab images are forks with no advisory feed). **sglang: clean, and the version string lies.** Our pinned build reports `0.0.0.dev1+g4ccff141d`, whose source commit `4ccff141db` is 2026-09-07; PEP 440 sorts that *below* every release, so OSV matches 14 of the 20 sglang advisories against it (the 6 it misses have ranges starting above a dev build — `introduced` 0.4.1.post7 or 0.5.5) and a version-based audit would report 14 false positives (those 14 are not merely unrated records: 2 are database-rated CRITICAL and 1 HIGH). The decidable side is the fix side: **`0.5.13` (released 2026-06-11) carries zero advisories** (the first clean 0.5.x release is `0.5.12.post1`, 2026-05-23), ~3 months before our source, so none of them is live in our tree. **vLLM nightly (cybersec route): clean.** `ghcr.io/spark-arena/dgx-vllm-eugr-nightly@sha256:7717585a…` carries `vLLM 0.32.0rc1.dev161+g660bd051d`, past the 0.30.0 fix line, 0 advisories. **Unreachable surfaces do not apply:** no recipe passes `--enable-custom-logit-processor`, none runs disaggregated/router mode with a public ROUTER socket, and the three cybersec `dev-cu13` arms sit on the same >0.5.13 source (the qwen3 27B arm was pinned by `4ef53ad`; `dev-cu13` as pulled today reports `0.0.0.dev1+ga6a8c5601`).