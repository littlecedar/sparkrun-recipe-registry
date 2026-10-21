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

# DECISIONS — 1 open (2026-10-18)

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

- [ ] **Run the now-runnable arms of the deep-search shortlist** *(delivered 2026-10-19.)* — the
  ranked note is `mad-science/DS4-SPEEDUPS.md` (11 candidates + a precondition, each with mechanism,
  expected effect, carrying flag/artifact, dated source, and a pre-registered interleaved A/B); the
  lane README now lists them under §"Upgrade candidates". Two can still run on the `.34`/`.35`
  pair: the **TensorFold v0.6 engine bump** (prefill-heavy, unquantified) and client-side
  **`reasoning_effort: high`** (0.55-0.8x reasoning cost at equal reported quality). The **P0 GPU
  clock-latch audit is closed negative** (2026-10-19: both nodes idle at 208 MHz, but ramp to
  2171-2190 MHz under load against a 3003 MHz max, with SW Power Cap the only active throttle
  reason — no latch; receipt `~/benchmarks/ds4-p0-clock-20261019/`). The TP=4-only
  eight stay upgrade candidates while `.30`-`.33` are frozen. Re-derive any win with its own receipt
  under `~/benchmarks/`; the A/B rules are `recipes/ds4/README.md` §(b)-(d) plus the note's §"The
  baseline these A/B plans assume". *(effort: medium)*

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
  *(progress 2026-10-21 — **the recorded blocker is refuted at the target tag: the bump is testable, not blocked.** "The Mamba/SWA radix-cache args were removed upstream" is false. `mamba_radix_cache_strategy` and `mamba_full_memory_ratio` are still declared fields at v0.5.21 (`python/sglang/srt/arg_groups/fields/exec_.py:450-457`, `arg_groups/fields/schedule.py:214-218`), still register as `--mamba-radix-cache-strategy` / `--mamba-full-memory-ratio` (`arg_groups/arg_utils.py:290`), and `extra_buffer_lazy` remains a legal choice with the DFLASH lazy-verify hook wired (`arg_groups/mamba_hook.py:113-120`). sglang#40313 (merged 2026-09-20, shipped in v0.5.21) removed the `MambaRadixCache` and `SWARadixCache` *classes*, which no recipe or mod imports; the LIKELY origin of the misread is the v0.5.20 move of every field declaration out of `server_args.py` into `arg_groups/fields/`, so a grep of the old file finds nothing. Of the two named wins only one reaches this lane: the DFlash reranker (LiLiCorr, sglang#37462) engages only for a draft checkpoint carrying `lilicorr_*` geometry, which the `jzinno` DFlash2 and first-party DFlash heads do not, while the GDN QKV materialization removal (sglang#33778, also v0.5.21) applies on the Triton linear-attention verify path these arms resolve to. **Target:** `lmsysorg/sglang:v0.5.21@sha256:b1259f3e…` (tag 2026-10-01, release 2026-10-02), a multi-arch index with a native `linux/arm64` manifest (`sha256:1f176b3a…`, 14.8 GB); the current pin is a 2026-09-08 arm64 nightly whose serve log reports `0.0.0.dev1+g20ca564bf`. **Staged, not applied:** one-line digest edits in the three SGLang arms (`tests/test_ornith_recipes.py` asserts a shared digest-pinned container, not a literal). **Pass bar per arm:** contract ok, house **37/37**, needle **3/3** at 32k / 131k / 262k, and the on-file ladder bands — 35B C1 100.8-101.8 · C2 153.1-158.2 · C5 217.4-220.4 · C10 244.2-249.9 t/s at d0, 9B C1 52-59 · C2 101.1 · C5 159.0 · C10 148.9 — with the YaRN arm gated on its needle rungs (262k / 512k / 768k 3/3, 1M at depths 10/50/90 % each at ≥95 % fill, d90 retry rule declared before the run) and on reading its `max_total_num_tokens` grant first. **Estimated 3.5-5.5 h** against this item's 6-9 h; BFCL is out of the bar and would add ~2.5 h per arm. **Boot pending: needs a free pair node.** Evidence table with commit-level citations in `attic/ornith/AGENTS.md` §"Engine-bump adjudication — SGLang 0.5.18 → 0.5.21 (2026-10-21, repo-side)"; operator plan, staged diff, and pass-bar table in `recipes/ornith/README.md` §"Engine bump to SGLang 0.5.21". Note for the run: `sparkrun` is not on PATH on the local workstation — validate and render on the head node.)*
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
- [ ] **Retire or resolve the shipping diagnostic** — `diag-qwen4-unplaced-scales` ships only because the shared-expert scale blocker is unexplained, and the `demote-labquant-narrow-mxfp8-to-bf16` `EXTRA_LEAVES` knob stays for an unresolved QSA-prefill CUDA-graph crash (`attic/qwen4/AGENTS.md` §10.1; `recipes/qwen4/mods/demote-labquant-narrow-mxfp8-to-bf16/README.md`). *(effort: medium)*
  *(Owner decision 2026-10-18 [#40]: chase both explanations — root-cause the shared-expert scale blocker and the QSA-prefill crash rather than declaring the workarounds permanent.)*
  *(**Both are root-caused 2026-10-19** — `mad-science/QWEN4-DIAGNOSTICS.md` carries the mechanism
  with `file.py:line`. The shared-expert blocker is the checkpoint's `.weight_scale` suffix vs the
  engine's `.weight_scale_inv` registration plus gate/up stacking; the rename mod fixes it and the diag
  is now insurance, not a workaround. The QSA-prefill crash is `get_prefill_mqa_inputs`' host sync and
  data-dependent buffer shape during capture; `EXTRA_LEAVES` is **falsified** (the demoted-projection
  boot crashed identically) and the path is unreachable today because the engine disables prefill
  graphs for this multimodal checkpoint. Remaining work shrinks to: boot `zz-labq-no-diag` (retire the
  diag control) and delete `EXTRA_LEAVES` (code + docs, no boot).)*
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
## explore
Any model with reasoning and tool-calling capabilities
- [ ] **Build the top-ranked unbuilt reasoning candidates** — `Muse-Glimmer-30B` (rank 2; blocked on unmerged vLLM PR #51655); license/availability-blocked: MiniMax-M3 (non-commercial), MiMo-V2.6-Flash-RL (no quant), Inkling-Small (unpublished active params); plus `IFM/K2-Horizon-375B-A23B` (`mad-science/EXPLORE-CANDIDATES.md:16-57`; `attic/explore/EXPLORE-MODELS-RESEARCH.md`). *(Mistral-Small-4 is **not** unbuilt: it was measured-rejected at 28.9 t/s C1 and archived by the 2026-10-19 sweep — `attic/explore/ARMS-MANIFEST.md`.)* *(effort: long)*
  *(closed sub-item 2026-10-18 — **`Nemotron-3-Super-120B-A12B-NVFP4` is built and measured, and does not ship.** C1 **15.83 ± 0.19 t/s** @ d0 (15.91 ± 0.12 @ d8192, depth-free) is 45 % below the already-rejected Mistral-Small-4 (28.9) and 66 % below Kolibri-1 (47.3); batching does not close it (c2/c5/c10 25.52 / 26.94 / 30.60 = 1.93× for 10× concurrency). Quality is the lane's best — house **37/37**, ties ling and mellum GGUF — and it is the only measured single-node arm serving the full **262,144** window (KV pool 7,659,632 tokens, 29.22× concurrency), which is why it is archived rather than deleted. **Params corrected: 123.6B true total (112.74B 4-bit experts + 4.83B FP8 + 6.02B BF16) / ≈12.2B active (22/512 experts); the Hub's 67.2B counts packed U8 NVFP4 expert bytes (2 values/byte) as parameters.** The as-authored recipe cannot boot: `--swap-space 0` is unrecognized in vLLM 0.29.0 (hard abort, which under `readiness.inference: false` shows as a hang, not a failure), and `VLLM_NVFP4_GEMM_BACKEND` / `VLLM_USE_FLASHINFER_MOE_FP4` are also unknown to 0.29.0, so its metadata describes behaviour that does not happen. Archived frozen at `attic/explore/nemotron-3-super-120b-a12b-nvfp4-vllm.yaml`; receipt `~/benchmarks/nemotron-120b-20261018/REPORT.md`.)*
- [ ] **Exercise the media-gen cells left unrun** — LTX-2.5's I2V + FLF2V templates and the 4K/50 fps preset; Qwen-Image non-8-step schedules and 2048²; and the faster vLLM-OMNI engine route (40 vs 54 s on the base model) (`attic/explore/EXPLORE-MODELS-RESEARCH.md`). *(Owner decision 2026-10-15: next-window scope, on the free `.34`/`.35`.)* *(effort: medium)*
  *(progress 2026-10-18 — the Qwen-Image 2048² cell is **CLOSED**: **53.24 s/image** (σ 0.20, n=3) against a same-boot **11.240 s** at 1024² (n=3, σ 0.008), tiling off, the three 2048² PNGs byte-identical (`sha256 86973bfb…`) and decoded at 2048×2048; peak 56.505 GiB torch alloc / 59.779 GiB reserved, node `MemAvailable` floor 53.8 GiB. The lane's ~26 s prediction is **falsified 2.04×** (+18.4 % per-pixel cost at 2048²). A non-null `num_inference_steps` is **silently ignored** — `12` was accepted and the pipeline ran the checkpoint's saved 8-step sigmas at the same 11.23 s — so a non-8-step schedule needs a `sigmas`-accepting mod, not a knob. Receipt `~/benchmarks/media-gen-20261018/` (`REPORT.md`, `cells.json`, `proof.json`). The non-8-step schedule and the vLLM-OMNI engine route stay **OPEN**; LTX-2.5's cells were closed late the same day — next bullet.)*
  *(closed 2026-10-18, late — **LTX-2.5 I2V + FLF2V + 4K/50 fps are measured.** Warm on `.34` (clock cap 2200 MHz, 1344×768 / 121 f / 24 fps): T2V **78.1 s / 83.70 GiB** (−2.5 % on the recorded 80.1 s), I2V **84.3 s (+7.9 %) / 83.79 GiB**, FLF2V **120.2 s (+54 %) / 81.94 GiB**. FLF2V is slower by mechanism, not regression: its template has no `LTXVLatentUpsampler`, so one full-res 8-step pass (76.9 s @ 9.6 s/it at 1344×768) replaces half-res 8-step + 3-step refine. Conditioning proven by decoded-frame MAD, not by a file existing: I2V frame 0 **4.1** vs the start image; FLF2V frame 0 **7.8** vs start / 59.5 vs end, frame 120 **16.9** vs end / 59.1 vs start. **4K/50 (3840×2160, 249 f) is OOM — a measured ceiling, not an untried preset:** stage 1 fine (8/8, 461.3 s @ 57.7 s/it at the 1920×1080 latent), killed at the ×2 latent upscale with 590 `NV_ERR_NO_MEMORY` kernel lines at **121.16 of 121 GiB** (85.0 GiB steady in stage 1, weights-only baseline 78.4 → not co-tenancy); the node stayed up, a process kill rather than a node loss. A smaller 4K cell at that output size is the only open question there and no register asks for one. Cold rep **204.3 s is an upper bound** (it overlapped a peer's serve; model load 25 s, first sampler step 12 s, cold tiled VAE decode 82.7 s vs 43.5 s warm). Receipt `~/benchmarks/ltx25-20261018/` (`REPORT.md`, 7 frames, 7 mp4s, per-rep `api/err/out`, `receipts{,_warm}`, and the fixed `expand2.py`/`run_cell2.py`; the runbook's expander is T2V-only — four defects listed in `attic/explore/AGENTS.md`).)*

- [ ] **Ship the LTX-2.5 runbook as a sparkrun recipe** *(Owner directive 2026-10-19.)* — convert
  `recipes/explore/ltx-2.5-runbook/` (ComfyUI v0.34.0, `Lightricks/LTX-2.5`, ~36.9 GB of explicit
  files) into a shipped arm on the qwen-image pattern: `runtime: vllm` only as the
  distribution/launcher contract, `executor_config.entrypoint: ""`, `readiness.inference: false`, and
  a `recipes/explore/mods/ltx-25-launcher` mod that stages the ComfyUI venv, expands the native T2V
  graph headlessly and serves `POST /generate` + `GET /health`. Resolve the gated-distribution
  question first: sparkrun's anonymous distribution cannot fetch a `gated: auto` repo, so either the
  mod downloads with the node's accepted `HF_TOKEN` (documented prerequisite, as the 2026-10-14 owner
  call allows) or the launch refuses with a clear message — do not ship a recipe that hangs on
  distribution. Use the fixed `expand2.py` / `run_cell2.py` from `~/benchmarks/ltx25-20261018/` — the
  repo expander has four defects (`attic/explore/AGENTS.md` §"the three unrun cells + the expander
  defects", 2026-10-18) — keep `frames % 8 == 1`, the `SaveVideo` output node, the explicit-filename
  download rule and the 2200 MHz clock cap as documented prerequisites; carry the
  `ltx-2.x-community-license-agreement` banner (free below the $10M threshold; third parties read the
  text). Land the recipe, root index row and lane section only on a boot receipt with the measured
  cells (T2V 78.1 s / I2V 84.3 s / FLF2V 120.2 s; 4K/50 OOM at 121.16 GiB). *(effort: long)*

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