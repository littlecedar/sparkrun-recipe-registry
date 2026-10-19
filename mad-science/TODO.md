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

- **#43 — The superseded `deepseek-ai/DeepSeek-V4.1-Flash` base (510.3 GB, head cache) — reclaim or keep?**
  Nothing shipped serves it: both ds4 arms moved to the `-1017` refresh and both Engram builders default
  to `-1017`. But `tools/build-dsv41-combined.py` and the unmounted `dsv41-engram-fetch` mod still name
  it, so a future combined-pack build would re-fetch 510 GB. The head sits at ~300 GiB free after today's
  263 GiB reclaim; taking this puts it at ~783 GiB. → Answer:

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

## ds4
DeepSeek V4.1
*(The v2.4 serve line is settled and carries no runnable work: with
`PREFILL_DECODE_INTERVAL: "0"` it beats v2.3 at C5/C10 (`recipes/ds4/README.md` §(b)–(d)); the one
unrun cell, an interleaved C1 re-take on the shipped line, needs `.30`–`.33` and was **dropped, not
deferred**, by the 19:15 policy above. Measurement, launcher pins and the correction to the earlier
"slower on every cell" reading are archived in `../attic/DONE.md`.)*

- [ ] **Deep web search for unexplored DeepSeek-V4.1-Flash-1017 speedups on GB10** *(Owner directive
  2026-10-19.)* — survey what the lane has not tried: upstream SGLang/vLLM release notes and PRs that
  touch Blackwell/sm_121 (attention and MLA kernels, MoE GEMM paths, graph capture, DCP/DP),
  FlashInfer/CUTLASS/DeepGEMM/DeepEP builds and their GB10 support, NVFP4/FP8/EXL3 releases of the
  1017 base, MTP/DSpark/spec-decode work, prefix-cache and scheduler features, CUDA 13.x image
  builds, and any published DeepSeek-V4.1 tuning or DGX Spark benchmark. Deliverable: a shortlist
  where each candidate names the mechanism, the expected effect, the flag or artifact that carries
  it, and a same-boot A/B plan the `.34`/`.35` pair can actually run — the TensorFold TP=2 arm is the
  runnable shape, plus one-node probes; a TP=4-only find is written into `recipes/ds4/README.md` as
  an upgrade candidate, not queued as a boot (the 19:15 policy froze `.30`–`.33`). Exclude the knobs
  the lane already measured
  (`--prefill-decode-interval`, `--swa-prefix-tails`, `DSV41_FAST_LOAD`, the DSpark block size, the
  KV/token pins; `recipes/ds4/README.md` §(b)–(d) and the launcher-knob bullets), and re-derive any
  claimed win with its own receipt under `~/benchmarks/`. *(effort: medium)*

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
- [ ] **Re-verify the 35B serve line on the SGLang 0.5.18→0.5.21 bump** — a named perf lead (DFlash-reranker + GDN fusion wins) that currently breaks the lane (`attic/ornith/AGENTS.md:883-886`). *(effort: medium)* *(Owner approval required: the bump changes the engine image/digest, which the 2026-10-18 19:15 policy reserves for the owner.)*

## qwen3
Qwen 3.x
*(all items completed — archived in `../attic/DONE.md`)*

## qwen4
Qwen 4.x (and 3.8 Flash Next)
- [ ] **Clear the remaining qwen4 measurement backlog** — TP=4 (W6) re-boot after the `port_timeout_s` fix; the W12 cross-runtime vLLM same-checkpoint bench; the `--fp4-gemm-backend` A/B (the shipped `flashinfer_cutlass` was inherited without justification); `--enable-int8-mamba-checkpoint`; and the bs>1 cost of `--cuda-graph-backend-prefill disabled` (`attic/qwen4/AGENTS.md` §10.1). *(effort: medium)*
  *(2026-10-18: **none of this backlog ran** — the TP=2 block closed after one arm. Two facts to carry into the next window: the `--fp4-gemm-backend` A/B's first alternative arm is refused **before weights load** (`flashinfer_cudedsl` is listed in `--help` and in the error's own `choose from` set, yet argparse rejects the token verbatim — `~/benchmarks/qwen4-tp2-20261018/b2-cudedsl-refusal-arm.log`), so probe the accept-spelling first; and `--enable-linear-replayssm-spec` is now measured as a capacity lever (+11.5 % KV pool) whose remaining question is accuracy, not memory. TP=4 (W6) and the W12 cross-runtime vLLM bench need four/two nodes and are out of this session's scope.)*
  *(progress 2026-10-19 — the `--fp4-gemm-backend` probe's spelling question is answered: the engine accepts **`flashinfer_cutedsl`** (the 2026-10-18 `flashinfer_cudedsl` refusal was a typo). One boot with it: `load_weight` 485 s, house **37/37**, ladder 39.02 / 70.22 / 98.38 / 106.13 t/s against the control's 41.22 / 72.88 / 95.18 / 108.13 — mixed, at or below the 7-25 % inter-boot floor, so `flashinfer_cutlass` stays. Still unprobed: `--enable-int8-mamba-checkpoint` and the prefill-graph bs>1 cost. Receipt `~/benchmarks/qwen4-knobs-20261019/b1-cutedsl/REPORT.md`.)*
  *(progress 2026-10-19, later — **`--enable-int8-mamba-checkpoint` is a hard negative.** The default 224-slot pool needs 3.24 GB against 2.15 GB free at the shipped `gpu_memory_utilization: 0.80`; a 112-slot retry then dies with `ValueError: --enable-int8-mamba-checkpoint is incompatible with Qwen4-Exp PLE side states` (`memory_pool.py:1337`), so no size fits. Receipts `~/benchmarks/qwen4-knobs-20261019/b2-int8mamba/` and `b2b-int8mamba-112/`. The prefill-graph bs>1 cost is the only unprobed item left.)*
  *(progress 2026-10-19, last — **the prefill-graph flag is a no-op on this image.** Removing `--cuda-graph-backend-prefill disabled` leaves the default `disabled`, and an explicit `--cuda-graph-backend-prefill full` is accepted by args parsing then disabled by the engine for the EAGLE target ("Disable prefill CUDA graph for EAGLE target on tc_piecewise…"), with the multimodal rule as the companion reason. There is no bs>1 graph cost to recover. Three same-config boots span **8.6 % at C2** (67.1-72.9) and ≤4.6 % elsewhere — the inter-boot floor measured directly. Receipts `~/benchmarks/qwen4-knobs-20261019/b3-prefillgraph{,-full}/`. **All TP=2 knobs in this item are now answered**; it stays open only for TP=4 (W6) and the W12 cross-runtime bench, both needing a window outside this session.)*
- [ ] **Retire or resolve the shipping diagnostic** — `diag-qwen4-unplaced-scales` ships only because the shared-expert scale blocker is unexplained, and the `demote-labquant-narrow-mxfp8-to-bf16` `EXTRA_LEAVES` knob stays for an unresolved QSA-prefill CUDA-graph crash (`attic/qwen4/AGENTS.md` §10.1; `recipes/qwen4/mods/demote-labquant-narrow-mxfp8-to-bf16/README.md`). *(effort: medium)*
  *(Owner decision 2026-10-18 [#40]: chase both explanations — root-cause the shared-expert scale blocker and the QSA-prefill crash rather than declaring the workarounds permanent.)*

## ifm
IFM K2-Horizon
- [ ] **Attempt 7B tree-mode UNO (topk>1)** — a second UNO geometry, never booted (linear is shipped) (`attic/ifm/NOTES.md` "Still open"). *(effort: medium)*

## embed
Any embed model
*(all items completed — archived in `../attic/DONE.md`)*

## rerank
Any rerank model
*(all items completed — archived in `../attic/DONE.md`)*
  *(closed sub-item 2026-10-18 — the shipped 8B reranker was **unbootable** and is fixed: `Qwen/Qwen3-VL-Reranker-8B` declares `tie_word_embeddings` only at the top level while vLLM's `seq_cls_model_loader` reads `config.text_config.tie_word_embeddings`, so engine init died with `AttributeError`; the recipe now passes a nested `"text_config": {"tie_word_embeddings": false}` in `--hf-overrides`. Boots as shipped with no overrides (health 200 at 280 s) and its c1 cell is unchanged: **17.94 vs 18.03 u/s**. Receipt `~/benchmarks/embed-fix-20261018/`; full record in `../attic/DONE.md`.)*

## decision
Any decision model
- [ ] **Build the named decision candidates** — `Decision-2.0-Nox-4B` (best-scoring 4B, never booted), `laya` (CPU-real, zero-GPU), `kev-0.8b`, `GLiNER2.5-Decide`, `d3-edge`, `JEV-27B`, and the Sol-2B GGUF/llama.cpp CPU path (avoids the vllm-srun kill-shim workaround) (`attic/decision/DECISION-MODELS-RESEARCH.md`). *(effort: medium)*
  *(progress 2026-10-18 — `laya` is built, scored and ladded; the item stays open for four (`Nox-4B`, `GLiNER2.5-Decide`, `JEV-27B`, the Sol-2B GGUF path). **Decision accuracy 36.1 % (723/2000)**, KL 0.576 / Brier 0.316 / ECE 0.175, p50 4.29 s per request on 5 A725 cores (CPU-only, 1.6 GiB of the unified pool) — the vendor's near-chance expectation (0.362 zero-shot against a 0.461 majority baseline; the card's 0.766 belongs to the separate `laya-typed-decisions` checkpoint). The shipped recipe did not launch (`serve command does not identify the validated model`: the snapshot path reached the guard as `<path>)` inside a `printf` substitution); it now exports `LAYA_MODEL_PATH='{model}'` and builds the JSON from that variable, with a guard test (`test_model_path_is_a_whole_token_or_key_value`). Ladder **c1 0.449 req/s / 2.25 decisions/s**, c2 0.447 / 2.24 at doubled p50 — `/v1/systemone` is serial and does not batch. Receipt `~/benchmarks/decision-arms-20261018/`. `kev-0.8b` and `d3-edge` were booted in the next window — results below.)*
  *(closed sub-item 2026-10-18 — `kev-0.8b` is built and measured; `d3-edge` is closed as not bootable here. Receipt `~/benchmarks/decision-arms2-20261018/` (`REPORT.md`, `logs/`, `kev-evidence/`, `d3-evidence/`); lane record in `recipes/decision/README.md` §kev-0.8b-decision-serve and §d3-edge-decision-vllm-srun. **kev: Decision accuracy 46.0 % (919/2000)**, ★, KL 0.349 / Brier 0.196 / ECE 0.046, 0 decision errors, p50 5403.4 ms per request; per type noul 52.5 / choice 50.5 / score 37.6, per workflow customer_service 55.0 → agent_trace_observability 34.6; ladder c1 0.234 req/s / 1.17 decisions/s, c2 0.235 / 1.18 at doubled p50 — +9.9 pts over laya on the same 400 cases, at 1.9× laya's per-case latency. The serve is healthy but **the launch gate can never pass**: sparkrun's startup probe requires HTTP 200 on `/health` (`startup_probe.py:246-265`) and kev has no such route (404 forever), `readiness.inference: false` skips only the inference stage, and `health_path` is runtime-owned (`_vllm_common.py:24` → `/health`), so the score was taken against the detached container. **d3-edge: not booted** — (1) as shipped `/health` 503 `OfflineModeIsEnabled`, because sparkrun stages with `HF_HUB_OFFLINE=1` while the decision3 loader resolves through the Hub tree API even with `--cache-dir` pointed at the staged snapshot; (2) with `-e HF_HUB_OFFLINE=0` it loads 594,582,720 params then fails the golden gate: `GoldenResult(status='failed', checked=3, matched=1, reference='cpu')`, deltas confidence 3.70e-3 / P0 2.15e-3 / P1 2.22e-3 / score 2.09e-3 / noul 3.83e-3 / domain 8.8e-5 against `CPU_TOLERANCE = 1e-3`, identical across 5 attempts — so no score and no ladder. Both fixes are image-side (an aarch64-recorded CPU reference or a per-ISA tolerance; an offline-capable decision3 loader), not recipe edits.)*
- [ ] **Build the TTS fourth co-tenant** (Kokoro-82M, 0.305 GiB on the A725 cores) — the co-location budget is quoted net of it, but it was never built (`attic/decision/DECISION-MODELS-RESEARCH.md`). *(effort: medium)*

## explore
Any model with reasoning and tool-calling capabilities
- [ ] **Build the top-ranked unbuilt reasoning candidates** — `Muse-Glimmer-30B` (rank 2; blocked on unmerged vLLM PR #51655); license/availability-blocked: MiniMax-M3 (non-commercial), MiMo-V2.6-Flash-RL (no quant), Inkling-Small (unpublished active params); plus `IFM/K2-Horizon-375B-A23B` (`mad-science/EXPLORE-CANDIDATES.md:16-57`; `attic/explore/EXPLORE-MODELS-RESEARCH.md`). *(Mistral-Small-4 is **not** unbuilt: its recipe exists and it is measured-rejected at 28.9 t/s C1 (`attic/explore/ARMS-MANIFEST.md`) — the sweep item above owns it.)* *(effort: long)*
  *(closed sub-item 2026-10-18 — **`Nemotron-3-Super-120B-A12B-NVFP4` is built and measured, and does not ship.** C1 **15.83 ± 0.19 t/s** @ d0 (15.91 ± 0.12 @ d8192, depth-free) is 45 % below the already-rejected Mistral-Small-4 (28.9) and 66 % below Kolibri-1 (47.3); batching does not close it (c2/c5/c10 25.52 / 26.94 / 30.60 = 1.93× for 10× concurrency). Quality is the lane's best — house **37/37**, ties ling and mellum GGUF — and it is the only measured single-node arm serving the full **262,144** window (KV pool 7,659,632 tokens, 29.22× concurrency), which is why it is archived rather than deleted. **Params corrected: 123.6B true total (112.74B 4-bit experts + 4.83B FP8 + 6.02B BF16) / ≈12.2B active (22/512 experts); the Hub's 67.2B counts packed U8 NVFP4 expert bytes (2 values/byte) as parameters.** The as-authored recipe cannot boot: `--swap-space 0` is unrecognized in vLLM 0.29.0 (hard abort, which under `readiness.inference: false` shows as a hang, not a failure), and `VLLM_NVFP4_GEMM_BACKEND` / `VLLM_USE_FLASHINFER_MOE_FP4` are also unknown to 0.29.0, so its metadata describes behaviour that does not happen. Archived frozen at `attic/explore/nemotron-3-super-120b-a12b-nvfp4-vllm.yaml`; receipt `~/benchmarks/nemotron-120b-20261018/REPORT.md`.)*
- [ ] **Build the Laguna-M.1 2-node ceiling reference** — named then dropped; the family's only 2-node datapoint is third-party (`attic/explore/EXPLORE-MODELS-RESEARCH.md`). *(effort: medium)*
  *(Owner decision 2026-10-18 [#41]: build it this window (the `.34`/`.35` pair is the right shape for a TP=2 boot).)*
  *(2026-10-18, 21:45: the window closed at 19:15 without it. It needs only the `.34`/`.35` pair, which
  stayed idle, so the directive carries to the next window rather than expiring.)*
- [ ] **Exercise the media-gen cells left unrun** — LTX-2.5's I2V + FLF2V templates and the 4K/50 fps preset; Qwen-Image non-8-step schedules and 2048²; and the faster vLLM-OMNI engine route (40 vs 54 s on the base model) (`attic/explore/EXPLORE-MODELS-RESEARCH.md`). *(Owner decision 2026-10-15: next-window scope, on the free `.34`/`.35`.)* *(effort: medium)*
  *(progress 2026-10-18 — the Qwen-Image 2048² cell is **CLOSED**: **53.24 s/image** (σ 0.20, n=3) against a same-boot **11.240 s** at 1024² (n=3, σ 0.008), tiling off, the three 2048² PNGs byte-identical (`sha256 86973bfb…`) and decoded at 2048×2048; peak 56.505 GiB torch alloc / 59.779 GiB reserved, node `MemAvailable` floor 53.8 GiB. The lane's ~26 s prediction is **falsified 2.04×** (+18.4 % per-pixel cost at 2048²). A non-null `num_inference_steps` is **silently ignored** — `12` was accepted and the pipeline ran the checkpoint's saved 8-step sigmas at the same 11.23 s — so a non-8-step schedule needs a `sigmas`-accepting mod, not a knob. Receipt `~/benchmarks/media-gen-20261018/` (`REPORT.md`, `cells.json`, `proof.json`). The non-8-step schedule and the vLLM-OMNI engine route stay **OPEN**; LTX-2.5's cells were closed late the same day — next bullet.)*
  *(closed 2026-10-18, late — **LTX-2.5 I2V + FLF2V + 4K/50 fps are measured.** Warm on `.34` (clock cap 2200 MHz, 1344×768 / 121 f / 24 fps): T2V **78.1 s / 83.70 GiB** (−2.5 % on the recorded 80.1 s), I2V **84.3 s (+7.9 %) / 83.79 GiB**, FLF2V **120.2 s (+54 %) / 81.94 GiB**. FLF2V is slower by mechanism, not regression: its template has no `LTXVLatentUpsampler`, so one full-res 8-step pass (76.9 s @ 9.6 s/it at 1344×768) replaces half-res 8-step + 3-step refine. Conditioning proven by decoded-frame MAD, not by a file existing: I2V frame 0 **4.1** vs the start image; FLF2V frame 0 **7.8** vs start / 59.5 vs end, frame 120 **16.9** vs end / 59.1 vs start. **4K/50 (3840×2160, 249 f) is OOM — a measured ceiling, not an untried preset:** stage 1 fine (8/8, 461.3 s @ 57.7 s/it at the 1920×1080 latent), killed at the ×2 latent upscale with 590 `NV_ERR_NO_MEMORY` kernel lines at **121.16 of 121 GiB** (85.0 GiB steady in stage 1, weights-only baseline 78.4 → not co-tenancy); the node stayed up, a process kill rather than a node loss. A smaller 4K cell at that output size is the only open question there and no register asks for one. Cold rep **204.3 s is an upper bound** (it overlapped a peer's serve; model load 25 s, first sampler step 12 s, cold tiled VAE decode 82.7 s vs 43.5 s warm). Receipt `~/benchmarks/ltx25-20261018/` (`REPORT.md`, 7 frames, 7 mp4s, per-rep `api/err/out`, `receipts{,_warm}`, and the fixed `expand2.py`/`run_cell2.py`; the runbook's expander is T2V-only — four defects listed in `attic/explore/AGENTS.md`).)*

- [ ] **Select the lane's keepers and sweep the rest to `attic/explore/`** *(Owner directive 2026-10-19:
  top candidates optimized for generation speed, concurrency, accuracy and small size; the remainder
  moves to the attic.)* — score the **14 measured root-index rows** on those axes from their own
  receipts: C1 and the ladder shape (decode and aggregate), the concurrency ceiling (KV pool,
  `max_num_seqs` clamps), the accuracy cells (house / needle / ARC / GSM8K / BFCL / TEB), and size
  plus peak memory. Keep the Pareto set — fastest decode, best aggregate at high concurrency, the
  accuracy leaders, the smallest arm with real headroom, and any media-gen arm whose own cells are
  closed — and retire the rest with `attic/explore/ARMS-MANIFEST.md`, the lane `README.md` section,
  the root index row, the `tests/test_explore_new_arms.py` / `tests/test_explore_llamacpp_arm.py`
  assertions, any lane-only mod, and a re-measured recipe count
  (`retire-sparkrun-recipe-to-attic`). The two YAMLs with no index row are **not** sweep candidates:
  `mistral-small-4-119b-nvfp4-vllm` is measured-rejected at **28.9 t/s C1** in
  `attic/explore/ARMS-MANIFEST.md` (archive it as measured-rejected after re-reading its receipt),
  and `poolside-laguna-m1-nvfp4-vllm-tp2` is authored but unbooted, so the Laguna-M.1 item above
  governs it until its TP=2 boot produces a receipt; classify both from artifact state, not from the
  stale "unbuilt" label in the build item. The three unrun Kolibri GGUF tiers (`Hob-forge` /
  `webmp3` / `aparusel`) cannot win on measurement; build them first or archive them as unmeasured
  with the reason. The owner's 2026-10-11 weighting (node count, accuracy, speed, memory) governs
  ties. *(effort: medium)*
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

**Other surfaced arms (not queued):** `orcarouter/GLM-5.3-Flash-Uncensored-NVFP4` (321B, **205.1 GB** —
2-node-heavy/3-node; inherits the archived glm5 Flash serve blocker),
`orcarouter/DeepSeek-V4-Flash-Vision-Uncensored` (304B, `deepseek_v4`),
`drowzeys/keys-Qwen3.8-Flash-Next-NVFP4-dual-ablit-house-qsa-L3-47` (dual 180B ablit, **132.7 GB**; base
`nvidia/…` → license `other`), `drowzeys/keys-GLM-5.3-Flash-NVFP4-ablit-l15-43-mtp-l45` (169B, MIT),
`drowzeys/MiMo-V2.6-Flash-RL-Abliterated` (310B, FP8/MXFP4). **Over the 1–2-node bar, so recorded but NOT
queued:** `drowzeys/keys-MiMo-V2.6-Pro-RL-Jarrelscy-ARVQ-Abliterated` (`nvfp4_arvq_hybrid`, MIT, gated —
**315.7 GB** on-disk ⇒ ≥3 nodes; owner asked to add it only if it fit 1–2).

## Recipe schema & documentation (registry-level)
- [ ] **Update the recipe-schema docs for sparkrun 0.4.0** *(Owner directive 2026-10-19; priority:
  high.)* — the authority is the installed 0.4.0 package, cited at `file.py:line`, never these docs
  themselves: `_KNOWN_KEYS` (41 accepted top-level keys) and the `Recipe` constructor in
  `sparkrun/core/recipe.py`, `core/validation.py`, `sparkrun recipe validate/show/vram`, and the
  runtime modules under `sparkrun/runtimes/` (`sglang`, `vllm_ray`, `vllm_distributed`, `trtllm`,
  `atlas`, `modular_max`, `tokenary`, `llama_cpp`, plus the `eugr_vllm_ray` alias). Schema facts to
  record: name from the filename, `recipe_version` default `"2"`, top-level `description:`,
  metadata-only `maintainer:`, unknown keys swept into `runtime_config`, plugin-owned keys,
  `capabilities`/`unsupported_capabilities` outside the workload fingerprint, `readiness`,
  `distribution_config`, `layout`, `include`/`overrides`, `solo_only`, and `cluster_only` (deprecated
  for v2). Bring
  `recipes/MECHANICS.md` in line first (the full key set and the per-key rules, especially "a
  `defaults:` value reaches the engine only through a `{placeholder}`, a runtime flag map or an
  internal key"), then the root `AGENTS.md` (the same rules, plus the stale facts re-measured
  2026-10-19: 58 recipes after the W4A16 archive, 780 tests, `recipes/glm` now two arms — re-measure
  the module and strict-validate counts instead of carrying the 38/648 snapshot), then the schema
  rules restated in `.omp/skills/sparkrun-recipe-edit-to-boot/` and
  `.omp/skills/sparkrun-recipe-launch-debugging/`; keep `attic/` frozen. Verify every shipped recipe
  validates and the repo gate passes. *(effort: medium)*

## Runtimes (registry-level)
Engine families the registry has not exercised. sparkrun 0.4.0 ships more runtimes than the two in use —
`sparkrun/runtimes/` holds `sglang`, `vllm_ray`, `vllm_distributed`, `trtllm`, `atlas`, `modular_max`,
`tokenary` and **`llama_cpp`** — while at the 2026-10-16 count every shipped recipe here was `runtime: vllm` or `sglang`
(0 llama.cpp arms in `recipes/` — **the first shipped 2026-10-17, `recipes/explore/mellum2.1-12b-a2.5b-q4km-thinking-llamacpp.yaml`, boot-verified**).

- [ ] **Explore sparkrun's llama.cpp runtime on GB10, and the viability of GGUF arms** *(Owner directive 2026-10-16.)* — the runtime is first-class and **its GB10 tier already exists**; what has never happened is a pull on our nodes, a digest pin, or a recipe that uses it. Facts read from the installed 0.4.0 tree (2026-10-16): `LlamaCppRuntime`, `runtime_name = "llama-cpp"`, `default_image_prefix = scitrera/dgx-spark-llama-cpp`; `runtime:` is even **auto-inferred** from a `command:` beginning with `llama-server` (`core/recipe.py:54` `_CMD_LLAMA_CPP_RE`, `_infer_runtime`); **`platforms/dgx_spark.py` maps `llama-cpp → scitrera/dgx-spark-llama-cpp:latest`** (beside sglang/trtllm/modular-max/atlas) **and forces `{"mmap": False}` on GB10** — memory-mapped GGUF loading performs poorly on unified memory — unless a recipe opts back in with `mmap: true`, while the generic-NVIDIA tier maps `ghcr.io/ggerganov/llama.cpp:server-cuda`. Both first-party images float: `scitrera/dgx-spark-llama-cpp:latest` (Docker Hub: **458 tags**, `latest` = 2026-08-21, digest `sha256:ad14055470c2b…`, 1.69 GB) and `ghcr.io/spark-arena/dgx-llama-cpp:b<build>-cu131` — and **the runtime source carries a TODO to pin them**. What it already gives us (so this is bring-up + pinning, not invention): `-hf <repo>:<quant>` or `-m <file>`, automatic `max_model_len → --ctx-size` translation, a flag map (`n_gpu_layers`, `parallel`, `threads`, `chat_template`, `reasoning_format`, `split_mode`, `--alias`, sampling, valued `flash_attn` on/off/auto, bools `cont_batching`/`--jinja`/`--no-webui`, inverted `webui`/`mmap`, `mmproj` for vision), and **experimental multi-node RPC** (`cluster_strategy() == "native"`; `rpc-server` workers on :50052, head `llama-server --rpc ip:port,…`, preferring IB IPs for the data path, model distributed to the head only, heterogeneous images allowed, TP→`--split-mode row` / PP→`layer` and mutually exclusive, `data_parallel > 1` rejected). GGUF distribution is a real pipeline, not an afterthought: `repo:quant` colon syntax, a selective `model_sync_gguf.sh` fetch that checks multipart shard completeness, a `gguf-v1:<quant>:<selector>` manifest selection, an `mmproj` auto-selection with a `projector:` override, a remote GGUF header reader for quant detection, and a GGUF bytes-per-weight table in the VRAM estimator. Deliverables: (a) **verify that tier end to end and pin it** — digest *and* per-build tag — recording what the image actually contains (`llama-server --version` + build number, CUDA arch support incl. sm_121, whether RPC is compiled in, whether `--jinja` is present), since the platform layer picks it for us silently; (b) the **arch-level viability map**, measured today by reading each wrapper's GGUF header and matching upstream master's `LLM_ARCH_NAMES` (160 archs): a **stock** first-party image can load `mellum` (`JetBrains/Mellum2.1-12B-A2.5B-Thinking-GGUF` — Q4_K_M 7.52 GiB, MXFP4_MOE 6.55 — i.e. the very route `attic/explore/MELLUM-21.md` §5 deferred), `gemma4` (`humanizer-12b` Q4_K_M 7.10 GiB) and **`laguna`** (`poolside/Laguna-XS-2.1-GGUF` Q4_K_M 18.88 GiB — `EXPLORE-MODELS-RESEARCH.md` assumed a poolside fork; upstream now carries the arch), while `kolibri1` (Myric/Kolibri APEX) and `k2-horizon` (IFM 0.9B) need a fork-built image — upstream master has no such arch (0 hits in `llama-model.cpp` / `llama-arch.cpp` / `convert_hf_to_gguf.py`, checked 2026-10-16), which is the boundary the Kolibri and IFM GGUF items run into; (c) the **standing policy for GGUF arms** — when a GGUF sibling should replace a safetensors arm, how its numbers may be compared to the arm it shadows (llama.cpp sampler defaults and `n_ctx` are not vLLM's, so the lane battery is the arbiter, not the uploader's KLD table), and how 7–80 GiB single-file downloads ride the 200 GbE fabric and the per-node HF cache (sparkrun's GGUF path ignores `auto`/`all`/`safetensors` and errors on any repo whose files do not identify exactly one model, so a `:quant` suffix is mandatory). First-boot questions to answer rather than guess: does `--jinja` carry our checkpoints' own `chat_template.jinja`; how does `reasoning_format` map onto each lane's parser habit (`qwen3`, `deepseek`, `kolibri1`); does the forced `mmap: false` cost anything at load time on unified memory; what do `--parallel`/`--cont-batching` really grant on one Spark (the C2/C5/C10 cells of the ladder section are exactly this); and the **CPU-only build** is the route `## decision` already wants for the Sol-2B GGUF path. Note the images are ~8 weeks old at write time, so re-check the upstream build number for arch coverage before pinning. *(effort: medium)*
  *(Correction 2026-10-18: the `mmap: true` opt-back-in above does not work on a `command:`-template arm — a `defaults:` flag-map key is silently dropped there (`build_flags_from_map` / `_special_flags` run only on the command-less path), and the shipped arm proves it by passing `--no-mmap` literally, so an mmap A/B needs a variant recipe rather than a key (`mad-science/LLAMACPP-GGUF.md` §3). The image pin is **DONE 2026-10-17**: `scitrera/dgx-spark-llama-cpp:b10549-cu131@sha256:ad14055470c2bd5c2b4c088dc5727d950da00f62408f438f4f3833c704af0dca` — build `b2e5e9b`, CUDA 13.1.1, `llama-server` only (**no `rpc-server`**, so the experimental RPC path cannot be exercised on this tier); tier contents in `mad-science/LLAMACPP-GGUF.md` §1.)*
  *(Owner decision 2026-10-16: also ship one stock-image GGUF arm this window, so the runtime is proven by an index row rather than by a pin alone. **Done 2026-10-17:** `recipes/explore/mellum2.1-12b-a2.5b-q4km-thinking-llamacpp.yaml` — booted on `.34` (TTR ≈ 100 s, `--alias` intact), full suite landed (house 37/37, needle 3/3 @32k+131k, arc 77.0% / gsm8k 93.5%, TEB 97, bfcl **73.5 % at the 512 default → 88.3 % at 4096** once `tools/eval-suite.py` learned `--bfcl-max-tokens` (`3ac9581`); the split — 179 of the parallel categories' 400 questions cut to no call at 512 vs 6 at 4096, the residual loss multi-call shape — is measured in the second receipt), index row + `recipes/explore/README.md` + `mad-science/LLAMACPP-GGUF.md` §5; receipts `~/benchmarks/mellum-gguf-20261017/` and `~/benchmarks/mellum-gguf-tools4096-20261017/`. The remaining GGUF routes for other lanes (Kolibri fork build, humanizer/laguna siblings) stay live in their own lane items.)*

## Concurrency ladder (registry-level)
**The census below is the 2026-10-15 snapshot and is stale:** most text arms now carry a full ladder — ds4 (TP=2 and TP=4), ornith 35B/9B, all three qwen3 arms, IFM 0.9B/7B, explore laguna-XS and both mellum arms (bf16 + llama-cpp), cybersec arm 2 — and only these still read `—` for C2/C5/C10 in `README.md`: qwen4's TP=1 solo arm, explore ling / kolibri / laguna-S, and cybersec arm 1 (orcarouter). `humanizer` needs no ladder — its `—` is by design, because the arm serves `/v1/completions` only and the ladder profile drives `/chat/completions` (`recipes/explore/README.md:148-151`). **Do not fill cells from the wrong receipt:** `attic/ds4/PERF-ISSUES.md:49-52`'s c1/c2/c5/c10 table is a cold-prefill triage on a different harness (its d0 c1 is 36.2, not the index's 46.5) and `attic/ifm/NOTES.md`'s c=2 53.697 belongs to the withdrawn 36B arm.
- [ ] **Fill C2/C5/C10 for the single-node text arms** *(ornith 35B done 2026-10-15: C2 158.2 / C5 220.4 / C10 249.9 t/s @ d0, σ 6.2/10.0/4.6, `bench_8c7486cad451`; 9B done 2026-10-15: C2 101.1 / C5 159.0 / C10 148.9 t/s @ d0, σ 8.3/7.8/4.8, `bench_92725c90d298`)* — the 14 that fit one Spark (ornith 35B/9B, qwen3 dflash2/coder-next/mlx4bit-TensorFold, IFM 0.9B/7B, explore ling/kolibri/laguna-XS/laguna-S/humanizer, cybersec arms 1/2) on the free `.34`/`.35`; per cell quote the **decode** row of the `--output` file (never the printed table, which shows only that row and no header) and cite the receipt beside the number in `README.md` and the lane doc. *(effort: long)* *(progress 2026-10-15: IFM 0.9B (C1 80.4 / C2 181.6 / C5 317.6 / C10 503.9) and 7B (31.3 / 56.1 / 94.0 / 126.0) done — receipts `~/benchmarks/ifm-{09b,7b}-ladder-20261015/`, docs in `recipes/ifm/README.md` + `attic/ifm/NOTES.md` (commit `84aa52f`); **2026-10-16: qwen3 coder-next done** — C1 70.4 / C2 114.0 / C5 177.1 / C10 249.5 t/s @ d0, σ 0.2/2.6/14.9/3.9, decode rows read from `benchmarking/concurrency-ladder.yaml`'s `--output`; receipt `~/benchmarks/pins-20261016/qwen3coder-ladder.yaml`; index row filled and the lane README carries the ladder plus the shape note. Remaining: qwen3 dflash2, explore ×5, cybersec ×2. **2026-10-17: the qwen3 mlx4bit-TensorFold arm done** — C1 44.8 / C2 57.7 / C5 64.4 / C10 65.6 t/s @ d0, σ 3.5/2.8/2.3/1.3, `bench_b10e422bb046`; the index row now carries all four cells and the lane README the ladder plus the scale shape (per-request decode falls 44.8 → 16.0, so the aggregate flattens past c5). **2026-10-17: the llama-cpp arm done** — C1 111.9 / C2 151.1 / C5 208.0 / C10 146.4 t/s @ d0, σ 0.3/2.6/2.8/1.5, `bench_4247926b7b9a`; the index row + lane README carry the four cells and the shape note (c10 runs 10 streams over the arm's 8 slots, so per-request decode spreads to 32.9 ± 16.1 and the aggregate falls past c5). Remaining single-node text arms: explore ling/kolibri/laguna-S, cybersec arm 1 (orcarouter), humanizer (needs the documented `—`: `/v1/completions` only, so llama-benchy cannot drive it). **2026-10-17: the qwen3 dflash2 arm re-measured and cybersec arm 2 (AEON) measured** — on `.35`, one boot each, `benchmarking/concurrency-ladder.yaml` with `--output`: dflash2 C1 29.6 ± 2.6 / C2 57.4 ± 3.3 / C5 89.5 ± 6.5 / C10 100.9 ± 3.4 t/s @ d0, `bench_355eee9f476f`; AEON C1 30.2 ± 1.5 / C2 49.4 ± 6.8 / C5 84.6 ± 9.1 / C10 92.9 ± 5.1 t/s @ d0, `bench_3ee8fda63ada`; receipt `~/benchmarks/ladders-solo-20261017/` (decode rows read from the `--output` JSON; values, per-request fall-off and the two-boot spread are in the rows and lane docs).)*
  *(Correction 2026-10-18 — the arm list above and its closing "Remaining" sentence are superseded: strike `humanizer` from both (its `—` is by design and already documented, `recipes/explore/README.md:148-151`), and add the two arms the list omits — qwen4's TP=1 solo arm and the mellum bf16 arm. Measured already: mellum bf16 ladder 2026-10-15 (C1 42.3 / C2 67.2 / C5 99.9 / C10 135.6 t/s @ d0) and the mellum llama-cpp arm 2026-10-17 (`bench_4247926b7b9a`), so neither is outstanding. Still lacking a ladder: qwen4's TP=1 solo arm, explore ling / kolibri / laguna-S, and cybersec arm 1 (orcarouter).)*
  *(Correction 2026-10-18, late — **that remaining list is itself stale; verified against the index rows, not against this register.** Measured since: qwen4 TP=1 solo (`bench_6b35f675861a`), explore ling (`bench_7c46291e9bbb`), kolibri FP8 (`bench_b0d57361b7d7`) plus each of the six pack/tier arms' own ladders, laguna-S (`bench_e3fdefdc2491`), and cybersec arm 1 plain (`bench_4c30a992c771`). What actually remains is two arms: the **cybersec NEXTN sibling** (`qwen3.8-27b-uncensored-nvfp4-nextn-sglang`, C1 14.72 only — one boot, `~/benchmarks/cybersec-nextn-20261018/`) and **qwen4 labquant-highcon**, whose `—` is deliberate: it is the aggregate regime, measured at d8192 k=16/24 rather than on the standard d0 ladder. `humanizer` stays `—` by design.)*
- [ ] **Give the two non-t/s lanes a ladder or a documented `—`** — the decision arms report `req/s` from a *serial* instrument (`tool-eval-bench`), so filling C2/C5/C10 there needs a concurrent harness; the image arm serves one request at a time, so its `—` should be written down as by-design in the lane doc. (`recipes/decision/README.md`; `recipes/explore/README.md`; `tools/README.md`) *(effort: medium)*

## Standard evaluation suite (registry-level)
- [ ] **Run the standard suite against every shipped arm** — the SOP pass (`tools/eval-suite.py`, then the `benchmarking/concurrency-ladder.yaml` leg `--skip-run` on the same boot, then `benchmarking/standard-suite.yaml` where the arm serves tool calls) for each shipped recipe; receipts under `~/benchmarks/<lane>-<date>/`, numbers into the lane docs and the index with their receipt/bench id. This is the sweep that fills the C2/C5/C10 cells above and each lane's unmeasured accuracy cells; start with the ornith 35B and work the free `.34`/`.35` window. *(effort: long)* *(progress 2026-10-15: ornith 35B done; IFM 0.9B/7B ladders measured; the decision-lane ensemble + ladder and the qwen3 27B headline suite both landed. **2026-10-16: the ornith 35B re-run in full** — eval-suite 1.0.1 `ok` (house 37/37; needle 3/3 at each of 32k/131k/262k), same-boot ladder C1 101.8 / C2 153.1 / C5 217.4 / C10 244.2 t/s, tool-eval-bench v2.6.0 **100** (15/15); receipts `~/benchmarks/ornith-35b-suite-20261016/`, rows in `recipes/ornith/README.md` + the index. **And the qwen3 coder-next arm** — one boot: pin + ladder (C1 70.4 / C2 114.0 / C5 177.1 / C10 249.5) + tool leg **90/100 (27/30)**, deployability 89, responsiveness 87, engine `vLLM 0.32.0rc1.dev301`; receipts `~/benchmarks/pins-20261016/`. **2026-10-17: the laguna-XS-2.1 arm's suite landed** — same-boot ladder C1 55.3 / C2 83.1 / C5 133.7 / C10 141.3 t/s (`bench_9b207347ec3b`), `tools/eval-suite.py` 3 ok / 2 fail (the fails: contract, all-empty reply at the 262,144 window; needle 2/3 at 32k and 131k but **3/3 at 262k** — the rope caveat's predicted long-window miss did not appear), TEB **97**; receipts `~/benchmarks/explore-laguna-xs-20261017/`, the index row + `recipes/explore/README.md` carry the numbers. **And the qwen3 mlx4bit-TensorFold arm** — one boot on `.35`: ladder C1 44.8 / C2 57.7 / C5 64.4 / C10 65.6 t/s (`bench_b10e422bb046`), house 37/37, needle 3/3 at 32k and 131k (the engine reports no `max_model_len`, so the auto depths stop at 128k), arc 94.0% / gsm8k 96.5%, TEB **100** (15/15); receipts `~/benchmarks/qwen3-tf-suite-20261017/` (+ `NOTES.md`). Its `tools` leg was killed at 3,878 s because the leg's Python-block-buffered log read as a hang; the fix (`678cb0c`, `PYTHONUNBUFFERED` in `tools/eval-suite.py`'s child env) landed mid-sweep; the leg re-ran unbuffered (4,487 s) and landed **85.7% (1063/1240)** in `~/benchmarks/qwen3-tf-tools-20261017/` (`parallel` 85.5%, `parallel_multiple` 72.0%). In the same window the first llama-cpp arm (mellum Q4_K_M, `recipes/explore/mellum2.1-12b-a2.5b-q4km-thinking-llamacpp.yaml`) booted in ~100 s with its `--alias` intact and ran the same legs on `.34` (results at the end of this paragraph). One operational trap worth carrying: a legs-runner waiting on `pgrep -f "tools/eval-suite.py"` never exits, because a peer's day-old watcher loop carries that string in its own command line — match a pid file or a unique marker, not a substring of a command line. **2026-10-17: the first llama-cpp arm (mellum Q4_K_M, `.34`) ran the full legs** — house 37/37 (easy 19/19, hard 18/18); needle 131k 3/3, and 32k 3/3 after two manual re-probes of the thinking-budget class (depth 50 PASS at `--max-tokens 4096`; depth 90 PASS with `enable_thinking:false`, 9 completion tokens); hard arc 77.0% / gsm8k 93.5% (n=200 each); tool-eval-bench **97** (15 scenarios, 14 pass, 1 partial); bfcl **73.5 % at the 512 default → 88.3 % at 4096** (`~/benchmarks/mellum-gguf-tools4096-20261017/`: 179 → 6 no-call in the two parallel categories, all six `finish_reason: length`, the residual loss multi-call shape); ladder `bench_4247926b7b9a`; receipt `~/benchmarks/mellum-gguf-20261017/`. **Queued:** a `--bfcl-max-tokens 4096` re-run of the qwen3-TensorFold tools leg — its 85.7 % came from the 512 default, so its row and lane doc carry a `‡` budget annotation meanwhile.)*
  *(progress 2026-10-18 — two legs landed. **ds4 knapcio TP=4, 1017 weights** (task `a2e141223b52793c_7afff0589a33`): house **36/37** (easy 19/19, hard 17/18; the miss is `hard-rev`), needle **3/3 at each of 32,768 / 131,072 / 983,040** (top rung 981,950 prompt tokens), tool-eval-bench **90** (15 scenarios: 13 pass, 1 partial, 1 fail `TC-03 wrong_args`, `benchmarking/standard-suite.yaml`), same-boot ladder C1 69.28 / C2 86.40 / C5 108.78 / C10 116.27 t/s; receipts `~/benchmarks/tp4-20261018/` — `REPORT.md` §4, `knapcio-suite/`, `knapcio-teb.{yaml,json,csv}`. **qwen3 coder-next re-run** (`.30`, job `3d9fbe520b47c3a3_2d38dfc4605e`), all four legs `ok`: house 36/37 (easy 19/19, hard 17/18, the same `hard-arith-2` miss), needle 3/3 at 32k/128k/**256k** (262k rung filled 97.7 %, the tool's calibrated target, no `TRUNCATED`), ARC-Challenge 92.0 % (184/200) / GSM8K 96.0 % (192/200); `--timeout 3000 --needle-max-tokens 512` were applied proactively and never needed (256k prefill ~129 s, suite 1,319 s); the `tools` leg skipped on purpose (TEB already 90/100 on this arm); receipt `~/benchmarks/qwen3-coder-next-suite-20261018/`.)*
  *(progress 2026-10-18, late — **IFM 0.9B: PARTIAL, not a pass.** One serve on `.31` (cluster `e2b91b75cf01d3ab_68907e0cb1d8`, TTR 74.6 s, served `IFM/K2-Horizon-0.9B` @ 131,072, recipe sha256 `3c93459e…`): **contract ok**; **house ok** — easy **17/19** (`fmt-2`, `needle-1`), hard **15/18** (`hard-rev`, `trick-1`, `trick-2`); **needle FAIL** — 0/9 cells answered, every reply `finish_reason=length` with all 256 tokens spent inside `reasoning_content` and empty content, i.e. the SOP's 256-token cap and **not** a retrieval result (the 32k ladder's own calibration probes truncated too, so `chars_per_token` fell back to 4.6 and it filled 46.5k for a 32,768 target — a 42 % overshoot); **hard ok but floors** — gsm8k 86.0 % (172/200, 11 `length` + 11 empty replies) and arc 68.5 % (137/200, 18 `length` + 18 empty), the reasoning block eating the budget; **tools CUT** — SIGTERM'd when `.31` was reclaimed for a TP=4 boot, **585/904 logged (64.7 %)** with `irrelevance` never started and no `bfcl.json`, so that tally is **not** this arm's BFCL score. No ladder on this boot (the arm's stands at `edd4029e004f`). A valid re-take needs `--needle-max-tokens >= 512` and a completed tools leg. Receipt `~/benchmarks/ifm-09b-suite-20261018/` (`REPORT.md`, `house.json`, `needle-*.json`, `hard/`, partial `bfcl.log`, 0-byte `suite.log`).)*

*(progress 2026-10-19 — **qwen4 labquant TP=2** landed both legs on one boot: eval-suite `ok` — contract `max_model_len=262144` / ready / `finish=stop`, house 19/19 + 18/18, needle 3/3 at 32k / 128k / 262k, hard ARC 95.5 % and GSM8K 95.5 % (n=200 each) — and tool-eval-bench **100** (15/15 scenarios, 0 partial, 0 fail, `bench_eff75293e461`, 91.6 s); receipt `~/benchmarks/qwen4-labq-suite-20261018/`, rows in `recipes/qwen4/README.md`. The needle leg needs `--needle-max-tokens 512` on this export: at the 256 default every cell is reasoning-only, the same trap the IFM 0.9B pass hit.)*

## Image pins and advisories (registry-level)

**Advisory pass 2026-10-15 — what was checked and found clean** (method: `api.osv.dev` package queries per version, then a version bisect against upstream release dates; only public upstreams are covered — the `littlecedar/*`, TensorFold and miaai-lab images are forks with no advisory feed). **sglang: clean, and the version string lies.** Our pinned build reports `0.0.0.dev1+g4ccff141d`, whose source commit `4ccff141db` is 2026-09-07; PEP 440 sorts that *below* every release, so OSV matches 14 of the 20 sglang advisories against it (the 6 it misses have ranges starting above a dev build — `introduced` 0.4.1.post7 or 0.5.5) and a version-based audit would report 14 false positives (those 14 are not merely unrated records: 2 are database-rated CRITICAL and 1 HIGH). The decidable side is the fix side: **`0.5.13` (released 2026-06-11) carries zero advisories** (the first clean 0.5.x release is `0.5.12.post1`, 2026-05-23), ~3 months before our source, so none of them is live in our tree. **vLLM nightly (cybersec route): clean.** `ghcr.io/spark-arena/dgx-vllm-eugr-nightly@sha256:7717585a…` carries `vLLM 0.32.0rc1.dev161+g660bd051d`, past the 0.30.0 fix line, 0 advisories. **Unreachable surfaces do not apply:** no recipe passes `--enable-custom-logit-processor`, none runs disaggregated/router mode with a public ROUTER socket, and the three cybersec `dev-cu13` arms sit on the same >0.5.13 source (the qwen3 27B arm was pinned by `4ef53ad`; `dev-cu13` as pulled today reports `0.0.0.dev1+ga6a8c5601`).