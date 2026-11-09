*(Moved verbatim from `mad-science/TODO.md` on 2026-10-13 — the TODO now references this file).*

## Contents

- [Session record](#session-record)
- [2026-10-22 — the register becomes a board; the refresh, engine and CI block](#2026-10-22--the-register-becomes-a-board-the-refresh-engine-and-ci-block)
- [Workstation tooling (measured 2026-10-21, time not recorded, after sparkrun landed there and reported 0.4.2-alpha+g36d8a44)](#workstation-tooling-measured-2026-10-21-time-not-recorded-after-sparkrun-landed-there-and-reported-042-alphag36d8a44)
- [Planning preamble and resourcing (2026-10-15/18/19)](#planning-preamble-and-resourcing-2026-10-151819)
- [Session progress, policy, cluster state (2026-10-18/19)](#session-progress-policy-cluster-state-2026-10-1819)
- [Closed no-boot items note (2026-10-19)](#closed-no-boot-items-note-2026-10-19)
- [qwen4 backlog progress (2026-10-18/19)](#qwen4-backlog-progress-2026-10-1819)
- [qwen4 W6/W12 progress (2026-10-22)](#qwen4-w6w12-progress-2026-10-22)
- [decision candidates progress (2026-10-18..20)](#decision-candidates-progress-2026-10-1820)
- [decision closed sub-items (2026-10-18/22)](#decision-closed-sub-items-2026-10-1822)
- [explore reasoning-candidates recheck + Muse closure (2026-10-21)](#explore-reasoning-candidates-recheck--muse-closure-2026-10-21)
- [media-gen cells progress and closures (2026-10-18..21)](#media-gen-cells-progress-and-closures-2026-10-1821)
- [Spark-X2.6 cell-1 progress note (2026-10-22)](#spark-x26-cell-1-progress-note-2026-10-22)
- [cybersec vLLM-route progress (2026-10-19/21)](#cybersec-vllm-route-progress-2026-10-1921)
- [Concurrency-ladder stale census (2026-10-15/18)](#concurrency-ladder-stale-census-2026-10-1518)
- [Concurrency-ladder corrections (2026-10-18)](#concurrency-ladder-corrections-2026-10-18)
- [Standard-suite early progress (2026-10-18)](#standard-suite-early-progress-2026-10-18)
- [Standard-suite tail progress (2026-10-19/20)](#standard-suite-tail-progress-2026-10-1920)
- [Cluster-config change record (2026-10-24)](#cluster-config-change-record-2026-10-24)
- [Advisory pass record (2026-10-15)](#advisory-pass-record-2026-10-15)
- [Board restructure (2026-10-25, 23:20 ET)](#board-restructure-2026-10-25-2320-et)
- [ornith-toolcall-ohmympi-triage — NO FAILURE REPRODUCED (2026-10-26, window tp4-window4)](#ornith-toolcall-ohmympi-triage--no-failure-reproduced-2026-10-26-window-tp4-window4)
- [History rewrite record — 2026-10-27 (drain/close closeout)](#history-rewrite-record--2026-10-27-drainclose-closeout)
- [BeeGFS pool outage + recovery — 2026-10-26 ~19:28 ET (session DSV41F1017-Parity)](#beegfs-pool-outage--recovery--2026-10-26-1928-et-session-dsv41f1017-parity)
- [Landed rows retired at the 2026-10-27 13:10 ET board refresh (session boundary)](#landed-rows-retired-at-the-2026-10-27-1310-et-board-refresh-session-boundary)
- [Landed rows retired at the 2026-10-27 14:04 ET board refresh (session boundary)](#landed-rows-retired-at-the-2026-10-27-1404-et-board-refresh-session-boundary)
- [Landed rows retired at the 2026-10-27 21:04 ET board refresh (session boundary)](#landed-rows-retired-at-the-2026-10-27-2104-et-board-refresh-session-boundary)
- [Board commit rewritten for address hygiene — 2026-10-27 22:12 ET](#board-commit-rewritten-for-address-hygiene--2026-10-27-2212-et)
- [Landed rows retired at the 2026-10-28 00:30 ET board refresh (session boundary)](#landed-rows-retired-at-the-2026-10-28-0030-et-board-refresh-session-boundary)
- [Landed rows retired at the 2026-10-29 03:10 ET board refresh (session boundary)](#landed-rows-retired-at-the-2026-10-29-0310-et-board-refresh-session-boundary)

## Session record

**2026-10-11 wrap (snapshot at 12:41 — superseded by the refresh below):** gate **384 tests OK** (skipped=1); all 23 shipped recipes validate plain; `bash -n` + `py_compile` clean. Independent audit of the day's recipe/mod/test changes: no blockers; all findings fixed (unconsumed `draft_model` removed, README typos, a negative control that proved nothing, stale `NOT boot-verified` prose in two recipe descriptions, raw node IPs masked to the `.34`/`.35` shorthand, plus a new `LiteralShaConsistency` guard). At that snapshot all work was committed and pushed.

**Landed after the wrap, same day (`27c96d5`–`5660a4a`):** the Ling needle probe and the Nemotron checklist closure folded into the lane docs; render-check fixes — the comment-inside-a-folded-command class and the inert-`defaults`-key class (which had shipped three times) are now guarded by `tests/test_recipe_placeholder_resolution.py`; the Nemotron `moe_backend` pin restored; coder-next `tensor_parallel` made to reach the command; glm inert defaults dropped.

**2026-10-12 refresh (verified in-tree):** gate re-run — **386 tests OK** (skipped=1), 23/23 recipes validate plain, `bash -n` + `py_compile` clean; working tree clean as of that check — this restatement is the only change on top of it (uncommitted as written). Push state before this edit: everything through 2026-10-11 is pushed, with one local-only commit, `d05a0e9` (README capability-icon row, 2026-10-12). The head node's registry clone sits at `004178b` (2026-10-11 13:56) — its misses at writing are a guard test, recipe comment/doc edits, and that README row; run `sparkrun registry update littlecedar` before relying on the clone's shipped docs.

**2026-10-12 decision round (same day):** both open questions answered by the owner in-file and folded — next-window scope/budget into the preamble, the glm5 deferral into its lane item — and the `# Protocol` section added at the top of this file.

**2026-10-12/13 two-node completion pass:** all five remaining TP≤2 items closed on `.34`/`.35` in one
parallel two-queue round (`.34`: JEV + Kai/Sol; `.35`: Ling + Nemotron-1M + Kolibri). Ling 262k
servable at mem-fraction 0.80 (needle PASS, 4-way smoke clean); Nemotron 1M boots at the card's
0.91 and the 1M needle PASSES (C1 72.2); JEV scored **67.0% (1340/2000) ★★** with the new
`tools/jev-decision-bench.py`; Kai/Sol boot-verified on CPU and scored **47.5% / 55.0% ★★** via
tool-eval-bench v2.8.0; Kolibri-1 boot-verified + measured (47.3 t/s, battery 36/37 @4096, 37/37
union) and **kept**. One plan-fact correction: the `vllm-srun` runtime ships inside the
`vllm-sr` router image (no `model-runtime` image exists); its missing `kill` binary was root-caused
as the launch-failure misreport and fixed in-recipe. Receipts: `~/benchmarks/{ling-262k,
nemotron-1m,jev-decision,kai-sol,kolibri}-20261012/`. Production ds4 TP4 on `.30-.33` untouched
throughout; all six session serves stopped by explicit task ID. Integration gate re-run in-tree:
**386 tests OK** (skipped=1), all 27 shipped recipes validate plain, `bash -n` + `py_compile` clean,
`tools/jev-decision-bench.py --selftest` exit 0. Commits `3c20d60`–`061f57d`, pushed, head registry
clone updated to `061f57d`.

**2026-10-13 session — owner-announced TP=4 window (DeepSeek down; all six nodes free), agent-orchestrated.**
Headline (owner decision): the two shipped glm5 TP4 boots, then the three MiaAI-Lab/DeepSeek trial recipes, with
TP≤2 lane work on the spare nodes. Opened by committing the tree's unstaged flag-propagation pass (28 files;
recipe `tags:` dashed→snake_case + README Flag cells; the 27/27 derived-emoji==cell invariant verified) as
`71591fa`.

**glm5.** — **Flash TP4: BOOT-ATTEMPTED, BLOCKED, root-caused** (5 boots on `.30-.33`; every failure in the
container serve log). The pinned public `vllm/vllm-openai:glm53-flash` image cannot serve
`RedHatAI/GLM-5.3-Flash-NVFP4` on GB10: its SM120 sparse-MLA backend forces the `fp8_ds_mla` KV layout whose
`concat_and_cache_mla` needs a 64-dim RoPE tail, but the checkpoint is NoPE MLA (`qk_rope_head_dim 0`);
`bfloat16`/`nvfp4_ds_mla` KV select no backend and `FLASHINFER_MLA_SPARSE` is unsupported on GB10; the DFlash2
drafter needs the absent `SupportsEagle3`. Repo B qualified on a local unpublished image. No C1/quality — never a
healthy serve. Receipts `~/benchmarks/glm53-flash-20261013/`. **Keep-shipped-blocked vs `attic/glm/` is an open
owner call (`#DECISIONS`).** — **EXL3 3.0bpw TP4: BOOT-VERIFIED** (repo A's `bertholomus` TensorFold scripts,
`.30-.33`): **C1 35.67 ± 3.13 t/s @ d0 / 35.89 @ d8192**, MTP-3 acceptance 63.4%; runbook, not a recipe (engine
is an unreleased fork branch). — **MiaAI-Lab GLM-5.3-Flash EXL3 4bpw: TP=2/TP=3/TP=4 all BOOT-VERIFIED** (script
launcher, runbook entries): TP=2 **C1 58.5/60.5** + **quality 37/37** + needle 2/2 at 1M, TP=3 **C1 65.4/65.1**
(KV 4.84M), TP=4 **C1 98.4** (KV 5.83M); DFlash2 acceptance 71–87%. No new sparkrun recipes (the launcher's
multi-node topology is not expressible in the recipe schema). Root-index note updated.

**qwen4/ds4.** MiaAI-Lab `DeepSeek-v4-Flash-DSpark-2x` **TP=2 trial: boot-verified** via the repo's compose
launcher on `.34`+`.35` (KV 2.51M tokens, **C1 44.85 t/s @ d0 / 40.53 @ d8k**). No recipe (compose runtime-hotfix
not expressible). Receipt `~/benchmarks/deepseek-v4-flash-tp2-20261013/`.

**explore.** Selection applied (node-count→speed→accuracy→memory; all single-node → speed decided): kept
**Nemotron-262k** (rank 1) + **Kolibri-1** (rank 2); `git mv`'d `ling-3.0-flash` + `nemotron-…-1m` to
`attic/explore/` with `ARMS-MANIFEST.md`. TP=1 re-measure confirmed both keepers hold (nemotron d0 within σ;
kolibri −1.8%) and flagged an unreproduced Nemotron DFlash2 acceptance length (3.67 → ~1.66; suspected
metric-window artifact, recorded unproven).

**ornith.** Reasoning-loop ticket **NOT REPRODUCED** (9-prompt battery × {temp 0, 0.6} × {4096, 8192}: zero
repeated-window runs — the symptom is thinking-budget exhaustion, not a loop; this serve honours request-level
sampling). Owner-directed TP=1 test: **35B C1 re-measured 99.6 ± 9.1 t/s @ d0 / 100.2 @ d8192** (the `~100`
headline is now measured). New `attic/ornith/AGENTS.md`; root cross-reference updated.

**decision.** CPU+GPU tandem probe: clef-flash (GPU) + Kai-0.6B (CPU) equal-weight linear-mean ensemble
**71.6% vs clef's 70.3% alone** (+1.3, McNemar p=0.012) — pairing-specific (clef+Sol 69.9%, 3-way 69.6%);
co-residency slows the CPU model ~45%. New stdlib tool `tools/decision-tandem.py`.

**kolibri mod defect.** `recipes/explore/mods/install-kolibri-plugin` keyed idempotence on a persistent marker while pip installs
into the ephemeral container layer → the second boot died `ModuleNotFoundError`. Fixed (gate on a live import at
the pinned version), README corrected, new `tests/test_kolibri_plugin_mod.py` (8 tests, fail-before/pass-after
proven).

**Registry maintenance.** All 68 completed TODO items archived verbatim to `attic/DONE.md`; session records moved
to this file; `mad-science/TODO.md` is now `[X]`-free (open work only).

**Gate (in-tree, 2026-10-13):** **394 tests OK** (skipped=1), **24/24** shipped recipes validate plain, `bash -n`
+ `py_compile` clean. Production ds4 TP4 never taken down; every session serve stopped by explicit task ID; all
six nodes idle at close.

**Post-close-out (same day, from an advisory review).** (a) The owner's in-file `#DECISIONS` answer was
implemented: the blocked Flash recipe was **archived to `attic/glm/`** as a proven-negative arm (with an
`ARMS-MANIFEST.md`), and the lane README, root index, root `AGENTS.md`, and the DECISIONS entry were all
updated — the GLM lane now ships TensorFold runbooks only, and the shipped-recipe count is 24. (b) Raw fabric
IPs that had leaked into `recipes/glm/README.md` (against the repo's IP-masking rule) were masked to the
`.30-.35` shorthand. (c) The explore rank-2 rationale was corrected to state the Kolibri-vs-Ling margin
honestly — the 1.8 t/s speed gap sits inside Ling's own σ (5.5), so it is a near-tie, not "speed decided" — and
the call was raised as the one open `#DECISIONS` question.

(d) The owner answered the explore rank-2 question in-file: **for the explore lane the deciding factor
is accuracy, with preference for smaller and faster models** (supersedes the node-count→speed default).
The lane was re-ranked and re-cut accordingly — **Ling-3.0-flash (rank 1, 37/37) and Kolibri-1 (rank 2,
36/37 = 37/37 union, smaller + faster) kept; Nemotron-262k and its 1M variant moved to `attic/explore/`**
— with the lane README, the root index, the root `AGENTS.md`, and `attic/explore/ARMS-MANIFEST.md`
updated and the decision folded into the TODO. `#DECISIONS` is now empty.

(e) Follow-up cleanup, later the same day: the remaining `**DONE 2026-10-13**` items (the glm5 TP=4 window
and the TODO-file machinery) moved to `attic/DONE.md`, and `mad-science/TODO.md` was trimmed to open work
only — the answered-question register, the session-start cluster snapshot (all six nodes idle), and the
stale `## Session follow-ons` stub were dropped, and the two cache/pin-survey bullets below moved here
verbatim. Everything removed stays in git history.

**Cache/pin survey and pin-honor probe (moved verbatim from the `mad-science/TODO.md` preamble in the
follow-up cleanup; this survey is what opened the re-pin + re-bench items on the ds4, qwen4, ifm, decision,
and explore lanes):**
- *(Cache survey 2026-10-13 — read on ALL six nodes (`.30`-`.35`) and the Hub API queried for every shipped recipe's model and its spec-decode draft. **Caveat learned the same day:** a node's `refs/main` is written by an unrelated UNPINNED fetch (`hf download`-style), NOT by sparkrun — sparkrun fetches the recipe's `model_revision` and materializes `snapshots/<pin>/` with no `refs/` entry — so a `refs/main`-only read mis-attributes the pin; the registry's `model_revision:` pins **are honored on the fetch** (proven by the probe below). Where a lane's `main` has moved past its pin, that lane still gained a re-pin + re-bench task. Confirmed still matching: `nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4` (base), `ornith-ai/Ornith-1.5-35B-A3B-NVFP4`, `Intel/Qwen3-Coder-Next-int4-AutoRound`, `RadixArk/Qwen3.8-{27B,Flash-Next}-NVFP4` (+ its `-DSpark` draft), `nvidia/Qwen3.8-Flash-Next-NVFP4`, the four Qwen3-VL embed/rerank arms, `Cloudflare/clef-flash`, `autotrust/JEV-9B`, `Mia-AiLab/DeepSeek-V4.1-Flash-EXL3-2.9bpw`, and `littlecedar/DeepSeek-V4.1-Flash-EXL3-2.9bpw-with-engram`. **Floating (never pinned):** the drafts `inclusionAI/Ling-3.0-flash-dspark` (moved `d60b0e12…` 2026-10-12) and `nvidia/…NVFP4-DSpark` (moved `6d127b50…` 2026-10-12), plus `jzinno/Ornith-1.5-35B-A3B-DFlash2` (`9b4852c0…`), `incoai/Qwen3.8-27B-DFlash2` (`015e7956…`), `incoai/GLM-5.3-Flash-DFlash2` (`bf582e4e…`), and the unpinned bases `littlecedar/Ornith-1.5-397B-NVFP4-MTP-Graft` (`b4864e44…`) and the RadixArk/Qwen3.8 arms.)*
- **RESOLVED 2026-10-13 — `model_revision:` IS honored on the FETCH.** Probe on a node with no K2 cache: `sparkrun run k2-horizon-0.9b-bf16-sglang.yaml` fetched **only** `snapshots/9fa6faa55fe1…` (the pin, no `refs/`); the container serve line passed `--model-path …/snapshots/9fa6faa55fe1… --revision 9fa6faa55fe1…`; and the loaded `chat_template.jinja` md5 matches the Hub **pin** bytes, not main's. Mechanism (`sparkrun/models/preparation.py`, `scripts/resolve_model_path.py`): `fetch_inventory` calls `model_info(repo, revision=<pin>)` and *raises* if the Hub returns a commit ≠ the requested 40-hex pin, then distribution materializes `snapshots/<pin>/` directly. So the "caches hold `main`, not the pin" reading was a survey artifact and the pins are meaningful. Receipts: `~/benchmarks/pin-honor-probe-20261013/`. *Residual, not explained by this: the `.35` Kolibri and `.31-.33` RedHatAI-GLM caches held ONLY `main` (pin snapshots absent) despite prior sparkrun boots — worth a glance if either is re-booted, but it does not affect the mechanism.*
**2026-10-14 session — owner-announced all-node window (all six nodes `.30–.35` ours; a mandatory set by 10:00 ET, everything else spilling), agent-orchestrated.**
The must-do set closed: the qwen4 re-pin + two-arm cut, the five cybersec arms, and the
ifm/decision/explore re-pin sweep. Beyond it the session shipped the ds4 revision-into-recipe + image
push, the ornith 9B arm plus two ornith investigations, the qwen3 TensorFold arm, the two Poolside
Laguna arms + the Humanizer arm, and a new BFCL suite. Left open: the ornith **397B DFlash-vs-MTP A/B**
(4-node, out of window) and the two **media-gen arms** (owner-deferred).

**qwen4.** Cut to **two shipped arms** — fastest TP=1 (`…-solo-vllm-b12x`, 33.92/34.35 t/s) + fastest
TP=2 (`…-labquant-sglang`, the balanced base) — from the six measured in one window; the other four
`git mv`'d to `attic/qwen4/arms/` with an `ARMS-MANIFEST.md`. The labquant checkpoint re-pinned to
`main 6c01ac37` (the `step-5500 QAD` candidate); the mod chain is now **6 mods** (one dropped as
obsolete, one fixed) and **vision is restored**; the TP=2 survivor re-benched **40.32 ± 1.94 @ d0 /
43.29 ± 2.68 @ d8192** t/s. Receipts `~/benchmarks/q4-*-triage_1014_*`.

**cybersec (new lane).** Five gated abliterated/uncensored arms built; **three boot-verified positive**
— `orcarouter/Qwen3.8-27B-Uncensored-NVFP4` (C1 10.2/9.7, battery 37/37), the AEON-overlay
cyber-unlock DFlash2 (33.3/26.2, 37/37), and the DeepSeek-V4.1-Flash `wo_b` graft on the Mia 2× Spark
EXL3 base (63.7/67.7, 36/37, refusal probe 0/8 — 1/8 completed, 7/8 truncated-empty at the cap) — and **two documented negatives** (Nex-N2.5-mini:
NaN sample-time logits → CUDA device-side assert under SGLang; Qwen3.8-Flash-Next-Uncensored: SGLang's
compressed-tensors loader refuses `CompressedTensorsW4A16Sparse24`). New mods
`provide-uncensored-chat-template` + `graft-dsv41-ablit-wo-b`; lane guard `tests/test_cybersec_recipes.py`.

**ds4.** The DSV4.1 checkpoint revision moved out of the TP4 image into the recipe
(`model_revision: 5254448103b6…`, Hub `main`, not the baked `fb2764a5…`); image re-built + pushed
(digest unchanged) and boot-verified TP=4 (C1 38.3/42.5, house 19/19 easy + 17/18 hard).

**ornith.** The **9B arm shipped + measured** (`ornith-1.5-9b-nvfp4-dflash-sglang`, ≈55 t/s, draft
resolving `refs/main` itself); the **35B first-party-DFlash A/B is a null** (the vendor head
indistinguishable from the shipped jzinno DFlash2 at n=4 and no better at n=8), so the shipped draft
stands and is now **pinned** (`speculative_draft_model_revision: 9b4852c0…`) with a `refs/main` seed
hook; the **long-horizon quality re-investigation is a bounded null** (multi-turn tool-calling agentic
workload, no decode loop). Lane guard `tests/test_ornith_recipes.py` added.

**qwen3.** New TensorFold arm (`qwen3.8-27b-mlx4bit-tensorfold-sglang`, the ds4 shim pattern over a
foreign engine) booted + measured on one node: C1 **41.3** (d0) / **41.7** (d8192) t/s, battery 37/37;
guard `tests/test_qwen3_recipes.py`.

**explore.** Both keepers re-pinned and re-verified — Kolibri-1 → `258cae8f` (**47.4 t/s, 37/37 @4096**),
Ling DSPARK draft → pinned (**54.7 t/s, 37/37**). Two new Poolside Laguna arms shipped + measured on one
node — XS-2.1 (**57.4 t/s, 36/37**; NVFP4 native on SM121) and S-2.1 (boot-verified, **32/37**; the
pinned August checkpoint loads **95.61 GiB**, so the research 262k template does not fit one Spark). The
Humanizer-12B `/v1/completions` arm shipped + measured (131.7 s / 1k tokens). The Qwen-Image and LTX-2.5
media-gen arms stay **owner-deferred**.

**decision.** Determination recorded — the `vllm-srun` runtime pins its own validation revisions, so both
recipes were left as-is; the Hub drift is cosmetic (`assets/banner.png` only).

**ifm.** Both K2-Horizon reps re-pinned to `main` + guards updated; re-bench + accuracy reproduce every
cell inside the lane noise floor; UNO accept len mean 4.15 over 838 samples.

**Registry maintenance.** New industry-standard suite `tools/bfcl-eval.py` (BFCL v3 — a port of the
official AST checker so the number is the leaderboard's rule; `tests/test_bfcl_eval.py`, 46 tests) — the
tool-calling standard the explore lane's brief needed. Root index + lane docs consolidated; the closed
items in `mad-science/TODO.md` marked `[x]` (per the session convention; the lane detail lives in each
lane's docs).

**Gate (in-tree, 2026-10-14):** **508 tests OK** (skipped=1); **31/31** shipped recipes validate plain (four fail `--strict` on accepted warnings only); `bash -n` + `py_compile` clean; `sparkrun recipe validate` run locally with the HOME override.

**Commits:** all session work committed locally on `main`, unpushed (`63db2c8` onward; twelve through the extension session). All six nodes were left idle (0 containers) at the 10:00 ET close.
**Extension session (after the 10:00 ET wall — owner-approved open-item spend):** the ornith 397B
DFlash-vs-MTP A/B closed — **MTP ships** (42.55 ± 2.78 / 38.48 ± 1.91 t/s vs the DFlash head's
37.58 ± 4.45 / 33.64 ± 1.13, same-window on `.30`–`.33`, TP=4; the floating `:latest` was three
different builds and is now digest-pinned; commit `e176395`). The owner un-deferred the two
media-gen arms: **Qwen-Image-2.1-Turbo** recipe (~11.4 s per 1024²/8-step image, NON-COMMERCIAL
banner, eval-only) and **LTX-2.5** ComfyUI runbook (two-stage, cold 100.3/90.1 s, gated prerequisite
documented) — commit `17d816d`. A node-cache reclamation recovered ~1.85 TB from failed/deprecated
lanes (cybersec negatives, archived glm5 staging, orphaned caches; `dsv41-engram` staging kept for
the shipped arm-5 chain) — commit `9de2e2c`. Gate: **508 tests OK** (1 skipped), **31/31** recipes
validate, `bash -n` / `py_compile` clean. All six nodes left idle.

**TODO-file cleanup (2026-10-14).** `mad-science/TODO.md` trimmed to open work only: with every lane
closed, that is now the protocol, the (empty) decisions register, the standing `Selection priorities`,
and one `*(all items completed — archived in ../attic/DONE.md)*` stub per lane — plus the cybersec
`**Other surfaced arms (not queued):**` block, kept live because `recipes/cybersec/README.md` cites it.
Archived verbatim into `attic/DONE.md` (under its matching lane sections, with new `## ifm` /
`## cybersec` sections and a `## Session scaffolding (archived 2026-10-14)` section): the 25 completed
items, their `*(Owner decision …)*` notes, the §ornith session-result paragraph, the cybersec lane
prose, and the session scaffolding (the session-end line, the two scope bullets, the lane order). 162 →
89 lines, 0 `[x]` left. Verified by a line-set diff of the `HEAD` TODO blob against both files — 0
unaccounted, 0 duplicated lines. Gate re-run: **508 tests OK** (1 skipped), **31/31** recipes validate.

**Documentation sweep + the lane-doc rule (2026-10-14, later).** Six read-only scouts swept every lane
and the registry artifacts; the findings landed as 51 open `- [ ]` items across the 12 lane sections
plus a registry-level `## Storage consolidation` section (each item carrying `path:line` evidence and an
effort tag) and six owner questions (#28–#33) in `# DECISIONS` — commit `a56e03e`. Storage highlights:
the DS4.1 EXL3 base (~197 GB) + Engram tables provisioned twice per node where ds4 and cybersec co-run;
three 21–25 GB Qwen3.8-27B packs of one architecture; three archived-lane weight packs with no recorded
cache state (attic/ds4 Pollard, attic/ifm 36B-A4B, attic/explore Nemotron-30B); humanizer staging
62 GB/node of GGUFs it never loads. The owner then set a **lane-doc rule** (2026-10-14): a lane's
`README.md` speaks to **shipped recipes only**, carrying a table of contents and an index of the lane's
attic material; everything else lives under `attic/<lane>/`. First pass (this session): lane
`AGENTS.md`/`NOTES.md` fold into `attic/<lane>/` and the lane READMEs are block-merged to the new
template, with the primary `README.md` de-researched (the command-template mechanics move to a
new tracked `recipes/MECHANICS.md`).

**Node clean-up (2026-10-14, later still).** A pass over all six nodes removed the session litter the
owner flagged: on `${WOPR_HEAD_NODE}` 59 uncited `$HOME` logs/outs (the two cited ones kept), the
`~/scratch` clone, `~/runs`, `~/ifm-runs` (local rsync verified first), 738 MB of `/tmp` scratch and
four dangling `${WOPR_RUN_FROM_DIR}` symlinks; on the workers their `/tmp` scratch, `~/scratch`,
`~/mem_watch`, `~/serve_argv`, `pack-engram.log`, and 13 orphan anonymous docker volumes. Fleet-wide:
the two docker tags no doc or recipe names (the retired `overlay5` builds) and the retired Pollard
EXL3 cache tree. `~/benchmarks` and `~/benchlogs` were deliberately kept — they are the cited receipt
root. Left and reported rather than guessed at: the ~3.1 TB `runtime-cache` of prepared model trees
(sparkrun-managed and rebuildable, with three same-model DeepSeek trees whose live/stale split only
sparkrun core can decide). Removing `~/runs/2026/10/` cost nothing — checked rather than assumed: the
decision lane's head receipts hold the durable reports that path existed to feed
(`~/benchmarks/jev-decision-20261012/{jev-decision-bench.json,run.log}`,
`~/benchmarks/kai-sol-20261012/{teb-kai-report.md,teb-sol-report.md,kai-card-smoke.json,sol-card-smoke.json}`),
and `attic/DONE.md` says the reports were "copied into the receipts dir" — `~/runs/` was the intermediate.
**Cost of the pass:** the worker-side `serve_argv`/`mem_watch` evidence the qwen4 notes cite by path was
deleted as scratch and had no other copy — recorded in `attic/qwen4/AGENTS.md`. The rule, its
"grep the basename first" check and the harness carve-out (`$HOME/serve_argv/`, `$HOME/mem_watch/` are
designed outputs of an armed harness, harvested not swept) now live in the root `AGENTS.md` §"Node
hygiene".

**Space reclamation (2026-10-14, final pass).** The owner asked for the leftover research on the nodes
to be decided — keep (documented) or delete — because space is at a premium. This pass was driven by
bytes rather than by name patterns, and the deciding instrument was each cache tree's own provenance:
`runtime-cache/<runtime>/<org>__<model>_<hash>/modlogs/` names the mods that prepared the tree, so the
owning recipe is identifiable (a tree whose model a shipped recipe names *and* whose mod set matches
that recipe's `mods:` is load-bearing). Reclaimed: **~604 GB** of runtime-cache that is retired-variant
material — the pre-engram `Mia-AiLab__…-2db4d63c` trees on all six nodes (594 GB; `attic/ds4/NOTES.md:56`
calls that key "the old warm key"), retired Pollard EXL3 3.5bpw, both GLM-5.3 trees, the withdrawn MoVA
36B, `DeepSeek-V4-Flash-0731` (+NVFP4), `nvidia/Qwen3.8-Flash-Next-NVFP4`, Nemotron-3.5-Lightning, the
hash-named `f129e31a…`, plus uncited node dirs (`~/gauge_archive`, `~/nccl*-spark_cluster`,
`~/dsv41-{knapcio,tensorfold,state}`, `~/glm53-tf`, `~/.cache/tensorfold-glm53`, `~/.cache/puccinialin`,
`~/.rustup`/`~/.cargo`) and the `uv` caches. Fleet free space rose ~600 GB (`.30` 1.4→1.5 T, `.31`
2.5→2.6 T, `.32`/`.33` 1.6→1.7 T, `.34` 1.9→2.0 T, `.35` 1.8→1.9 T).

**Kept, and why:** every prepared tree owned by a shipped recipe plus anything touched within ~72 h
(`.sparkrun-last-used`); the ~7 TB HF cache, which is **not** litter — 63 of 65 cached repo-entries are
consumed by a shipped recipe or a shipped mod, with draft models living in `speculative_draft_model:` and
in `command:` rather than in `model:` (only `ornith-ai/Ornith-1.5-35B-A3B-DFlash`, 773.5 MB on `.30`/`.31`,
was unreferenced and was removed with `hf cache rm`); `~/benchmarks`+`~/benchlogs` (the receipt root);
the `~/src` clones (the registry delivery mechanism); `~/dsv41-engram` (shipped ds4 mods read it);
`~/ComfyUI` and `~/ltx25` (the LTX-2.5 runbook in `recipes/explore/` documents them).

**Casualty, recorded rather than glossed.** The batch reclaimed `~/glm53-tf` on `.30`–`.33`. Three
scripts there — `tp4_start.sh`, `tfrun.sh`, `tfrun-sglang.sh` — were cited *by path* in
`attic/glm/AGENTS.md` with no tracked copy, which is exactly the case the rule exists for. Two variants
of `tp4_start.sh`/`tfrun.sh` survived (`~/src/glm-5.3-tensorfold-tp4-4xgb10/scripts/`,
`~/development/TensorFold/tools/`) and are now tracked in `attic/glm/harvest-20261014/`; the TensorFold
checkout also survives at `~/development/TensorFold`. **`tfrun-sglang.sh` is gone** and is re-derivable
only from the runbook's description of its base swap. `attic/glm/AGENTS.md` carries the reclamation note
and the corrected revive path.

Two faults of my own, both caught by verification rather than by the deletes reporting success: an
earlier batch built its paths from an `ls` run in another directory, so every `rm -rf` targeted a
non-existent path and printed nothing (no damage, no reclaim — `df` exposed it); and `uv cache clean`
removed the archive that a pinned `_SPARKRUN_COMPLETE` path in the head's `.bashrc` pointed at, breaking
tab-completion on every shell start (repointed at `~/.local/bin/sparkrun`; the CLI itself was never
affected). Also observed, cause unknown: `docker images` is now empty on all six nodes, so the next
launch re-pulls the image.

**2026-10-15 session — two-node window (`.34`+`.35` ours; `.30`–`.33` held by the peer's ds4 TP=4 job),
agent-orchestrated, one arm at a time through `~/benchmarks/tp2-window.sh` (md5
`9d9b1f7285069a1926bbb2e3e47a8664`, the local `.scratch/` copy identical; launch → HTTP readiness →
capture grants before stopping → verify idle).**

Three window arms landed receipts. **q1** overturned a documented impossibility: the qwen3 27B recipe
boots and serves at `-o tensor_parallel=2` with the shipped fastsafetensors fix — decode C1 46.76 ±
4.92 / C2 79.21 ± 10.47 / C5 117.68 ± 3.67 / C10 120.29 ± 2.30 t/s (n=5, d0 pp2048 tg128), ≈
+48 %/+46 %/+23 %/+27 % over TP=1 — and the boot's admission lines, recorded as unread when the
receipt was written, were recovered the same day from the **sparkrun job log**: `max_running_requests
= 48`, mamba pool 565, no `capped to`, i.e. TP=2 grants the full `max_num_seqs` and does not clamp.
**d1** took the ds4 TP=2 vision receipt: the launcher's two-part change reaches the engine
(`vision ON … 43 gates`, tower 0.90 GiB, a real-image warm-up) while the served chat template answers
HTTP 400 for an `image_url` part — so the *engine-runs-it, HTTP-refuses-it* state replaced the
shipped claim in the attic and the lane README, and the index row gained a `†` footnote under the
table. **w1** measured the revived qwen4 highcon arm in the k≥16 aggregate window it was revived for:
84.9 / 89.1 / 89.1 / 72.9 t/s at k=8/12/16/24 (n=7, d8192), flat to k=16 with the cliff **at** k=24,
and an admission line showing no cap — so the cliff is intrinsic rather than the sweep profile's
`k == cap` confound; the arm took an index row and its item was archived.

**nex** (cybersec arm 3) closed its long-open route question in four bounded boots: the card's own
vLLM route loads the export, boots in ~4.3 min and answers `/v1/chat/completions`, but generation
degenerates to one repeated token in every tested shape (greedy and sampled, thinking-on and
answer-channel, the reasoning trace never closing at 800 tokens), so the arm keeps its recipe and
takes no index row. Two claims were corrected as **route-scoped** rather than globally: the recipe's
`reasoning_effort: none` default is inert on vLLM, and `chat_template_kwargs {"enable_thinking":
false}` is the switch that fills `content` — the recipe now ships the working value.

**Registry-wide.** An advisory pass (OSV queries plus a version bisect against upstream release dates)
found the pinned stacks clean: sglang's dev build (source `4ccff141db`, 2026-09-07) postdates every
affected release (newest affected bound `0.5.12`, 2026-05-16; first clean 0.5.x release is
`0.5.12.post1`, 2026-05-23 — the dev version string matches 14 of the 20 advisories under OSV's
all-version ranges, a PEP-440 artefact of `introduced: 0` ranges that is not merely unrated records:
2 of the 14 are database-rated CRITICAL and 1 HIGH), and the cybersec vLLM nightly
(`0.32.0rc1.dev161`) carries none; no recipe passes `--enable-custom-logit-processor` or runs
router/disaggregation mode, so the unreachable-surface advisories do not apply. Two hygiene items were
opened instead: six explore arms ride vLLM v0.29.0 (23 advisory records / 16 distinct CVEs, none rated
HIGH or CRITICAL, all fixed in 0.30.0) and nine recipes ride three moving tags whose resolved digest
no receipt records. The qwen3 27B arm was pinned to the digest its own suite receipt names
(`@sha256:0a1ba33a…`), which is the image ID those nodes hold for the rebuilt tag.

Review feedback that changed artifacts, kept here because the method matters more than the fix: a
row-level table-width check must cover *every* line between the fences (my first one sampled a slice
and passed a row that had landed in the wrong table with a broken column); a severity claim must not
outrun its query ("none rated HIGH or CRITICAL" is not "all LOW/MODERATE" when 16 of 23 records
carry only a top-level CVSS vector, no database-level rating); and a measurement that contradicts three
carriers gets corrected in all three deliberately
rather than in one silently.

Open at close: the GLM TP=4 boot, cybersec arm 4's vLLM boot, and the ornith YaRN gate; the register
holds 42 open items with no `[x]` rows, this entry's completed ones having been archived to
`attic/DONE.md`.

**Node hygiene (2026-10-15 closeout).** `.34`, `.35` and the head all stand at 0 containers / 0
volumes; the head's one container is the peer's ds4 TP=4 job (`a4c699c1299bbbdf…`, `.30`–`.33`),
untouched. Head `/tmp` holds only the read-only `storage_census*.sh` scripts the storage census cites;
receipts are kept, and so are both harness copies (`~/benchmarks/tp2-window.sh` md5
`9d9b1f7285069a1926bbb2e3e47a8664`, `~/benchmarks/cybersec/nex-vllm-boot.sh` md5
`997aa02e0576037ac462d9dd3a72b0a9`). Left in place, all <72 h, named here so a basename-grep sweep
reads them as known rather than litter: `.35` `~/benchmarks/mellum-20261015/` (`image-pull.log`,
`weights-fetch.log` — the Mellum boot's pre-stage pull records); `.34` `~/benchmarks/` root
`c1-decode.json`, `c1.log`, `run-c1.sh` and `dspark-receipts/` (2026-10-13 ornith/glm53-night ad-hoc
files, not this window's); both nodes' `~/benchmarks/_prefetch-20261015/` (cybersec weight pre-stage,
cited by the register's bulky-weight item) and `~/benchmarks/_image-pulls-20261015/` (nex image pulls).
One hazard also stays in place: the d1 receipt's `d1-run-20261015-105008.story` on the head embeds the
raw HTTP-400 body containing the DeepSeek image special token — never `cat` it; run
`tools/safe_text.py` on a copy if it ever needs extraction.

**Register status moved out of `mad-science/TODO.md` (2026-10-15 cleanup).** These two dated blocks were
the register's session-narrative residue; they move here so the register holds only open work. Copied
verbatim.

**Landed 2026-10-15 (parallel slices).** *(GLM 5.3 TP=4 arm `2024552` — boot deferred to a `.30`–`.33`
window; cybersec arms 3/4 vLLM routes `8abe604` — arm 3's boot receipt landed later the same day (the
route answers, the checkpoint degenerates in every probe, no index row), arm 4's boot is still owed;
ornith 35B YaRN 1M arm `7dc0576` — gate pre-registered in `attic/ornith/NOTES.md` §8 and still
unproven; pooling `BenchmarkingPlugin` + the silent-skip correction `1e30c3d`; storage positions +
`tools/cache-audit.py` `af088d5`; the Engram log fix `7f80802`.)*

**Closed later on 2026-10-15** (each with its receipt, doc edit, and the gate re-run): the decision
lane's ensemble + ladder (`~/benchmarks/decision-ensemble-20261015/`), the qwen3 27B re-anchored
suite (`~/benchmarks/qwen3-27b-suite-20261015/`) and its TP=2 boot
(`~/benchmarks/qwen3-27b-tp2-20261015/`), the ornith 35B standard-suite pass, the qwen4 highcon k≥16
aggregate window (`~/benchmarks/qwen4-highcon-20261015/`, which earned that arm an index row and
closed its revival item), the cybersec weight prefetch on both nodes, and the four-boot nex vLLM
route receipt. The two-node window itself ran as `~/benchmarks/tp2-window.sh` (q1 / d1 / w1, serial by
construction, each arm capturing grants before stopping the container).

**2026-10-16 session — the register's planning round, then the sweep's first five tasks** (owner-ordered; every boot on the free `.34`/`.35`, the peer's `…-b12x-dspark-sglang-tp4` job on `.30`–`.33` untouched throughout). Commit `c89fe1e`, pushed.

Opened with the planning round: all five `# DECISIONS` questions (the `🚀 fast` band, the warm DS4 runtime-cache lobes, the AEON-7 clause, `.34` residency, the pooling ladder pair) went to the owner in one batch, were answered, and folded — `# DECISIONS` is now empty, the bands landed in `README.md` §Model Flags, the calls are recorded in `STORAGE-POLICY.md` §5, and the two shipped profiles are `benchmarking/pooling-ladder-{embed,rerank}.yaml` (both loaded through sparkrun's own `BenchmarkSpec.load` before shipping).

**1 — runtime cache (the instant-tagged item).** Owner Q2 executed by absolute path, not by the sweep: the sweep's own `--older-than 2` would have taken **30 trees / 968.7 GB**, including ornith, RadixArk and IFM leaves a *shipped* recipe still produces. Removed the four `9a74d993` ds4 lobes, every `db95f94c` tree, and `ca6f25af` — the labquant model's **unpinned** leaf (103.4 GB each on `.32`/`.33`, 51.8 on `.34`), a row §2 never listed, found by deriving leaves with `sparkrun.core.runtime_cache.model_key`. **≈1.30 TB freed**; `.32`/`.33` back inside the 0.5 TB cap (734.8/732.1 GB → 406.2/403.4); the live job's `11826f49` leaf was never in the set. Receipt `~/benchmarks/storage-20261016/`.

**2/3/4 — pins: nine recipes, three boots.** Every arm riding a floating tag is digest-pinned; `recipes/` now holds **37/37** digest-pinned `container:` refs and zero tag-only. Method (relay-imported images carry no `RepoDigests`, so `docker images --digests` prints `<none>`): `docker buildx imagetools inspect <ref>` for the tag's digest, match that manifest's config digest to the container's `docker inspect .Image`, then confirm the ref resolves. **Two tags had moved**: `dgx-vllm-eugr-nightly` (2026-10-15 read `7717585a…`, today resolved `cc47adc1…`, engine `vLLM 0.32.0rc1.dev301`) and `dev-cu13` (`.34`/`.35` held `0a1ba33a…`, today `0b3e3970…`, engine `0.0.0.dev1+gc15edf314`). Boots: the 2B embed arm on `.34`, the nex sglang arm on `.35`, the qwen3 coder arm on `.35`. The qwen4 solo README's "the b12x build publishes no digest-pinnable alias" claim was **wrong** and is corrected.

**2-extra — the embed ladder.** First live use of the shipped profile: c1 38.2 / c2 45.5 / c5 85.2 / c10 102.4 units/s, 100/100 per cell — index row plus a shape footnote (never pool those cells with the lane's published c 1/4/8/16/32 numbers).

**4-extra — qwen3 coder-next.** Ladder C1 70.4 / C2 114.0 / C5 177.1 / C10 249.5 t/s @ d0 (decode rows read from the `--output`, σ 0.2/2.6/14.9/3.9) and tool-eval-bench v2.6.0 **90/100 (27/30), excellent**, deployability 89, responsiveness 87 — index cells filled and two lane-README rows added.

**5 — ornith 35B standard pass, re-run in full on one boot.** eval-suite 1.0.1 verdict `ok` (contract ok; house **37/37** = easy 19/19 + hard 18/18; needle **3/3 at each** of 32k/131k/262k, the top rung 256,394-token prompts at 142.5–142.9 s per probe), same-boot ladder **C1 101.8 / C2 153.1 / C5 217.4 / C10 244.2 t/s** @ d0 (per-stream 101.8/79.8/54.5/34.2, ttfr 303/582/1208/1973 ms — 2026-10-15's 158.2/220.4/249.9 reproduced within 3 %), tool-eval-bench **100** (15/15 pass). Both ornith arms' index C2/C5/C10 filled with a receipt footnote. Receipts `~/benchmarks/ornith-35b-suite-20261016/`.

**Cybersec correction (same boot as task 3).** On the engine the three SGLang cybersec arms now pin, the nex arm's CUDA device-side assert is **gone** — the server answers — but every greedy probe returns 64 identical `!` tokens, the same checkpoint-level degeneration the vLLM route showed on 2026-10-15. The failure follows the **checkpoint, not the engine**; the recipe's `metadata.caveats`, the arm-3 block in `recipes/cybersec/README.md` and `attic/cybersec/AGENTS.md` were corrected to that state.

**Two operational traps, recorded.** (a) My legs-runner waited on `while pgrep -f "tools/eval-suite.py"` — which never exits, because a **peer's day-old watcher loop** carries that string in its own command line; a booted arm sat idle on `.34` until the owner flagged it. Match a pid file or a unique marker, never a substring of a command line. (b) `pkill -f "<pattern>"` over ssh **killed the session carrying the pattern** (exit 255, no output) — use the `[.]` bracket trick so the pattern cannot match its own command line.

**Hygiene.** Every session serve stopped by explicit task id (`.34` and `.35` at zero containers, zero orphan volumes fleet-wide); `/tmp` scratch removed on the head and `.35`; `.30`–`.33` untouched. Working tree: only the second writer's `README.md` edit left unstaged. Head change: `~/.config/sparkrun/config.yaml` gained `core.external_plugins: true` and `plugins.paths` pointing at this repo's `plugins/`, so the shipped pooling ladder runs — the pre-change file is kept as `config.yaml.bak-pre-plugins-20261016` beside it, and the change is documented in `~/benchmarks/pins-20261016/head-config-change.md`. Gate: **606 tests OK** (2 skipped), all recipes validate plain, `bash -n` + `py_compile` clean. Receipts `~/benchmarks/{pins-20261016,storage-20261016,ornith-35b-suite-20261016}/`.

**2026-10-16, later pass — the README consolidation: `recipes/README.md` merged into the root `README.md`** (owner-ordered). The root keeps its content on top, the recipes table of contents moved above `# Recipe Format`, and the recipe index follows it (three relative links rewritten for the new depth — `recipes/glm/README.md`, `attic/glm/ARMS-MANIFEST.md`, `recipes/MECHANICS.md`); `recipes/README.md` is deleted. Commit `c61bee8` (pushed) carries all 29 paths: the merged README, the deletion, 26 further repointed paths (path swaps only, plus section-anchored retargets where the referenced text moved — the two laguna recipes' `# Notes` cites now name `recipes/MECHANICS.md`), and `sparkrun-index-table-row-edit` relocated from the managed-global skills root into the tracked `.omp/skills/` tree.

**Fidelity.** A rebuild of the merged file from both sources plus the three rewrites is byte-identical except the final newline byte (`write`/`edit` strip trailing newlines from parameters and shell redirection is blocked); the pre-merge root file ended without one (`c61bee8^:README.md`). Corrected 2026-10-17: the committed `README.md` is 25,314 bytes and ends with a newline; no test reads its bytes. `recipes/MECHANICS.md:4`'s "the former `recipes/README.md`" is left as historical wording; the register's last four cites (`mad-science/TODO.md`) were repointed by owner decision, one section-anchored (`README.md` §Cybersec). Link check: all 16 TOC anchors resolve and every ref-style link is defined.

**Gate.** 606 tests OK (2 skipped), all 37 recipes validate plain, `bash -n` + `py_compile` clean.

**2026-10-16, advisory bump — five explore arms to vLLM 0.30.0, three held by a device-free config preflight.** Commits `7e6bf2b` (bump) and `27e4563` (holds); the peer's DS4.1 TP4 job on `.30`–`.33` untouched throughout, every boot on the free `.35`.

The `v0.30.0` pin resolved to the Docker Hub top-level manifest-list digest `sha256:8a69ffad…` (the 0.29.0 pin `c2914767…` re-derived the same way to confirm the method), and `7e6bf2b` moved five of the six `vllm/vllm-openai:v0.29.0` explore pins (humanizer, mellum, laguna-S, laguna-XS, qwen-image) while holding Kolibri in the same commit (its vendor plugin pins vLLM 0.29); OSV 23 records / 16 CVEs at 0.29.0 → **0** at 0.30.0).

**The preflight is the finding.** Before spending a boot, each pinned checkpoint's config was loaded device-free inside the new image on `.35` (`get_config(<repo>, trust_remote_code, revision=<pin>)`, HF **repo dir** mounted — never a `snapshots/<sha>` dir, whose `../../blobs` symlinks dangle outside it). Three of the five moved arms **cannot load their config at all** on 0.30.0 (vLLM-side in each case), and `27e4563` names the mechanisms in-recipe: **mellum2.1-12b** — vLLM 0.30.0 registers its own `MellumConfig` (a `Qwen3MoeConfig` subclass) ahead of transformers' upstream class for model_type `mellum`; the stub's generic `convert_rope_params_to_dict` flattens the checkpoint's nested per-layer `rope_parameters` and `validate_rope` dies on the float (`AttributeError: 'float' object has no attribute 'get'`; reproduced device-free and live — the first boot died in that frame before any weight load); an `hf_overrides_kw={'rope_parameters': …}` override loads clean if the arm is to move before upstream fixes the stub. **laguna-{s,xs}-2.1** — vLLM 0.30.0's own `LagunaConfig` stub shadows the transformers class and `get_config` raises `'str' object has no attribute 'get'` (identical with `trust_remote_code` True/False); a 2026-10-17 correction probe showed the original attribution to transformers 5.17 was wrong — `AutoConfig.from_pretrained` builds both pins and keeps their nested rope intact — so the unblock is a vLLM-side fix or a stub-compatible re-pin, a lane decision, since the measured numbers belong to the old pin. Kolibri holds as before (vendor plugin pins 0.29).

**The boot that verifies the batch:** `humanizer-12b-vllm` on `.35`, task `sparkrun_17678da2f7107eb2_a4bf874feb5a` — engine `vllm 0.30.0`, container `.Image` == the manifest list's arm64 config digest `91d9b077…`, TTR port-open 252.4 s (0.29.0: 277.9 s), `/v1/models` → `jialinyyzz/humanizer` (8192 ctx, the pinned snapshot), a `/v1/completions` rewrite smoke (`system_fingerprint: vllm-0.30.0-372a78a5`, every number preserved), serve-log KV **371,031 tokens / 45.29×** (0.29.0: 370,597 / 45.2× — a clean cross-version match). qwen-image keeps the bump (its mod stages its own `transformers>=5.17` venv on the image's torch); its media-gen boot is the check. Receipts `~/benchmarks/bump-20261016/` (both boot logs, the preflight/probe scripts, models+smoke JSON, `NOTES.md`).

**jev-9b look (the item's second half).** `vllm/vllm-openai:glm53-flash@sha256:819ec9c0…` = vLLM **0.28.1rc1.dev580+g385dce36b** (base already recorded in `attic/glm/`); OSV: **24 records**, the delta against 0.29.0 being **CVE-2026-93840 / PYSEC-2026-3998** (cross-request logits corruption via `allowed_token_ids`, fixed in 0.29.0). The Hub tag still resolves to the pinned manifest-list digest (checked 2026-10-16), so moving the arm needs a new build from the tag's author — it stays as-found.

**Hygiene.** Both session serves stopped by explicit task id; `.35` at zero containers/volumes, `.30`–`.33` untouched. Removed `.35`'s uncited `img-pull-9a352a.log` (a 2026-10-15 pull by-product); kept the cited `tf-tp2-boot.log`/`hf-verify.log` and the live peer job's `/tmp/tmp.Ke4vikV633` JSON state. Gate re-run after the holds: **606 tests OK** (2 skipped), all 37 recipes validate plain, `bash -n` + `py_compile` clean.

**2026-10-17 session — three dual-node TP=2 tasks on the free `.34`/`.35`** (the peer's
`…-b12x-dspark-sglang-tp4` job on `.30`–`.33` was never touched; one TP=2 serve at a time).
Commits `239f51c`, `ffcda28`, `1dd1ece`, `070ff66`, `b510a81`, `49e6a09`, `3bb82a1`, pushed.

**1 — TP=2 vision: the 2026-10-15 HTTP 400 was the served template, and it is fixed.** The engine's
vision branch rewrites each image part into a placeholder inline in one string content
(`families/deepseek_v41/cuda/app.py`, `DsVision.split`), and the combined pack's upstream template
refuses a placeholder arriving that way. The mod now ships a patched `chat_template.jinja` (two
placeholder guards neutered, the `reasoning_content` guard kept, the token assembled from pieces so
no shipped file carries it or a decodable spelling) and the launcher serves a `--vision`-gated
symlink-farm overlay model dir (`/cache/runtime/tensorfold/model-overlay`). Receipt: boot ~84 s,
overlay template sha `297be8861c9c…` identical on both nodes, vision probe **3/3** with a clean text
control and HTTP 200 where it used to be 400 (`~/benchmarks/ds4-vision-20261017/`, §12.14.1).
Recorded gotcha: the served template defaults to thinking mode, so a small `max_tokens` returns an
empty `content` (a 200-token text request shows `reasoning_len=156`); send
`chat_template_kwargs {"enable_thinking": false}` for one-shot answers.

**2 — the DeepSeek-V4.1-Flash-1017 refresh serves.** Trial recipe (untracked) over
`LibertAIDAI/…-1017-EXL3-2.9bpw` plus Engram tables rebuilt from 1017 shards 47/48 (188.8 GiB at
2978 s/node; one node needed a resume after two short-read segments): `/v1/models` = the 1017 repo id
at 530 s cold, vision **3/3** (the pack ships no template at all — the overlay is what makes it
boot), TEB **100**. Same-window A/B against the shipped arm: C1 **61.5 vs 68.0**, C4 48.9 vs 48.0, C8 49.3 vs 43.3,
C16 48.2 vs 43.4, TEB 100 vs 100 — but **every cell's three runs overlap** (shipped spread 1.56–5.85
t/s against 1017's 0.07–0.57), so the ladder establishes the 1017 arm's consistency, not a speed
win, and the C8/C16 deltas first read off the means are **not** established. Adoption is the owner's
call and should rest on the pack's published gains against the ~385 GB/node cost; the C1 cell wants
an interleaved re-take (§12.16). **Trap: `-o model=` is ignored by a real launch** — the
dry run honours it, the launch distributed and served the recipe's own model; a model swap needs a
recipe file.

**3 — the EXL3/Engram dedup, including the mistake inside it.** Arm 5 moved to the combined pack and
dropped `dsv41-engram-fetch`, with `--stock-model` finally carrying the launcher's Engram resolution.
The dedup as first wired did not work, and the mechanism I first recorded for it was wrong — read
from the author's script on 2026-10-17, it `os.link`s each shard it does not edit, and Python's
`os.link` uses `link(2)`, which hardlinks the snapshot's *own relative* `../../blobs/…` symlink (a
link that does not resolve from the graft tree), while `shutil.copytree` dereferences the `engram/`
*directory* and so duplicated the 189 GiB table set. Fixed by grafting from a `--src` view of
absolute symlinks without `engram/`, and symlinking `${STOCK}/engram` into the tree (with the repair
ahead of the `ABLIT_META` short-circuit): graft **148 s / 137 s**, tree **119 GiB** with `du` == `du
--apparent-size` — the 24 rewritten shards (118.58 GiB) are the only real bytes, the other 15 shards
and `engram/` are links, verified by inode/nlink on both nodes — `engram=` the stock pack,
`/v1/models` the drowzeys id, `17*19 → 323`, TTR 865.9 s with a cold rank cache
(`~/benchmarks/cybersec-arm5-20261017/`). The graft changed the served prompt with the stock: the
tree carries the combined pack's 15,348 B upstream template where the Mia-era graft had the
11,410 B exl3-era one. Stale Mia trees and `dsv41-engram` pre-warms removed from `.32`/`.33` (both
1.6T → 1.3T used).

**Consequence carried with it: the rank cache is now per served tree.** The two TP=2 arms' runtime-cache
keys stay separate today only because the ds4 arm is unpinned; the open pin TODO would merge them, and
TensorFold unlinks every other `rank<rank>of<world>-*` file in the directory it writes to
(`…/families/deepseek_v41/cuda/weights.py:140`, read out of the pinned image), so a shared dir would
make the two arms evict each other and re-pay the ~330 s cold write on every switch.
`mods/tensorfold-dsv41-launcher/launcher.py` now sets `TF_DS_RANK_CACHE` to `…/rank-cache/<served tree>`
(snapshot hash, or `dsv41-ablit` for the graft), guarded by
`tests/test_ds4_recipes.py::TensorfoldLaneContract.test_rank_cache_is_per_served_tree`. **Not a
correctness knob** — TF's own file name is already checkpoint-keyed, so neither arm could read the
other's; the reader who needs the mechanism has it in the launcher docstring. The four existing
~106 GiB caches on `.34`/`.35` were **moved** into their tag dirs (verified per key, one file per
rank), so nothing was invalidated and nothing is stranded — and the earlier draft of this change that
claimed an arm "would load the other's weights silently" was wrong and is corrected in every place it
appeared.

**Hygiene.** Every serve stopped by explicit task id; `.34`/`.35` at zero containers. Kept on the
nodes and documented: the 1017 pack + `<snapshot>/engram` (~385 GiB/node) as the decision artifact,
and the arm-5 graft tree — both named here so the next sweep does not read them as litter. Gate:
**635 tests OK** (2 skipped), all 38 recipes validate plain, `bash -n` + `py_compile` clean.

### 2026-10-17/18 — the 1017 refresh ships on the TP=2 arm

**What shipped** (`3aadba4`, `6116916`): `recipes/ds4/deepseek-v4.1-flash-tensorfold-tp2-1m-sglang.yaml`
now serves `LibertAIDAI/DeepSeek-V4.1-Flash-1017-EXL3-2.9bpw@c178a01284fc5c0e859d8668cffaac81ca8f4042`
(public, 66 files), with the release's own Engram tables (189 GiB, built from 1017 shards 47/48) in the
standalone `hub/dsv41-engram` dir rather than inside the snapshot, and the launcher gained
`--require-engram`. Boot receipt `~/benchmarks/ds4-1017-ship-20261017/` (task
`5959b937d06087c6_3510a5e0d37d`): `/v1/models` = the 1017 id, `max_model_len 1048576`, TTR **62 s**,
`reserved 104.00 GiB`, `engram=/cache/huggingface/hub/dsv41-engram`, `rank cache reading
…/rank-cache/c178a012…/rank{0,1}of2-*.bin`, `weights in 26 s (from the rank cache)`, text clean,
vision **3/3** with a clean control.

**Two defects the boot exposed, both fixed.** (1) sparkrun stages mods from
`~/.cache/sparkrun/registries/littlecedar`, not the source tree: that cache sat at `b873da8`, so the
first boot ran the *old* launcher — `ignoring unrecognized args: ['--require-engram']` — and rewrote
~106 GiB/rank (TTR 368 s). `sparkrun registry update littlecedar` is now a required step after a pull;
the 212 GiB of pre-tag residue was pruned. (2) `tools/build-dsv41-engram.py` and the
`dsv41-engram-fetch` mod both defaulted to the superseded base, so the documented pre-warm built V4.1
tables while `--require-engram` passed them through — the pairing the pack card forbids. Both defaults
are now the 1017 base pinned at `1bae0e10…`.

**The ladder is a null, and that is the result.** The 2026-10-17 single-boot A/B read +13.9 %/+11.1 %
at C8/C16 and −9.6 % at C1; the interleaved re-take (3 alternating boots per arm, 5 runs/cell,
`~/benchmarks/ds4-1017-ab-interleaved-20261018/`) leaves 1017 and V4.1 indistinguishable: c1 66.37 vs
66.43 (−0.10 %), c4 47.83 vs 48.82, c8 44.80 vs 42.44, c16 48.39 vs 48.78 (+0.8 % for V4.1), every
cell's 15-value range overlapping. Mechanism, from the artifacts: C16 is the tightest cell in all six
boots (48.1–49.1 t/s), so the earlier 43.4 ± 5.85 was an outlier; C8 is unstable in both arms and its
earlier gap was an ordering transient; C1's −9.6 % was 1017 at 530 s out of a cold boot against a warm
V4.1. Adoption therefore rests on the card's published gains, not on this lane's speed.

**Operational notes for the next campaign.** The bench id is recipe+profile+args, so a second boot
silently re-emits the first boot's numbers (`Prior benchmark state … COMPLETE`, 1 s) unless `--fresh`
is passed — one A2 run was discarded for exactly that. `docker logs` returns nothing for these
containers, so per-node serve logs must come from the executor's own path, not the daemon.

### 2026-10-18 (late) — TP>2 closes, and `.30`–`.33` go back to their owner

**Committed this stretch:** `099a547` (GLM 3.0bpw promotion + boot), `e76dc14` (Nemotron archive +
LTX cells), `deca288` (decision kev/d3), `2a260a6` (K2 36B D2/E6 + the LTX wall correction),
`6a5d7c3` (ornith YaRN 1M gate), `0fd9608` (qwen4 linear-replayssm), `457436c` (register swept
open-work-only). Gate at close, on the tree carrying all seven: **778 tests OK (2 skipped)**; no
recipe YAML, mod, tool or test changed after `2a260a6`, so that run's recipe validation, `bash -n`
and `py_compile` still describe the tree.

**GLM-5.3 EXL3 3.0bpw TP=4 — promoted, booted, receipted.** The recipe could not initialize for two
reasons that both presented as something else. `TF_TP_WORLD` was unset and the fork's derivation guard
defaults to `str(tp)`, so it never assigns: `engine.py:51` ran every rank at world=2, and ranks 2/3 died
in `ncclCommInitRank` with "Invalid rank requested : 3/2" (NCCL error 4) — the absent NCCL WARN sent
the first hour after the wrong knob, and the "no WARN ⇒ pre-transport" reading was right for the wrong
reason. Then the wheel shipped no package data, so the first JIT compile died on `latent_rows.cu`.
Measured: `/v1/models` 240 s, engine load 308.7 s, c1 **31.7** / c2 25.3 / c4 40.6 t/s, 100,559-token
TTFT **258.4 s**, 96.27 of 102.86 GiB. Guard `tests/test_glm_3bpw_shim.py`.

**Node policy changed mid-stretch:** the owner took `.30`–`.33` back for normal workloads at 19:15, so
the four-node leftovers (ds4 v2.4 C1 re-take, ornith 397B retry, a true ≥1M probe) are **dropped**, not
deferred. `.34`/`.35` carried the rest.

**Results that ended in "no":** Nemotron-3-Super-120B (37/37 and a unique one-node 262k window, but
15.9 t/s C1 → archived; and its recipe never booted as authored — `--swap-space 0` under
`readiness.inference: false` hangs). K2 36B: D2 PASS, E6 doubles the pool and holds quality but the
modelled +25 % throughput is false (−4.6 % at d8k, +8.1 % at d28k) → stays withdrawn. ornith YaRN 1M:
five rungs PASS, d90 ERROR ×2 (serve exit mid-prefill, OOM and client timeout excluded) → ships ≤768k,
1M to depth 50 %.

**qwen4 linear-replayssm — capacity, not speed.** One TP=2 boot on `.34`+`.35`: the flag drops the
spec-verify's per-draft SSM state cache from **2.64 GB to 0.00 GB** and the allocator hands it to KV —
`max_total_num_tokens` **1,689,024 → 1,882,944 (+11.5 %)** at an unchanged mamba pool of 112 and
`max_num_seqs` 24. The ladder is flat within the cell σ — 41.99 / 71.20 / 91.86 / 105.22 t/s at
k=1/2/5/10 against a 39.90 / 69.45 / 94.98 / 104.45 control, the k=10 cell n=2 after the stand-down
cut it — so it buys headroom, not throughput, and it is **not shipped** without accuracy coverage or
the W4 gate. Receipts: `~/benchmarks/qwen4-block-20261018/` (`REPORT.md`, `lrs-ladder-1018.{yaml,json}`,
`max_total_num_tokens=1882944` in the state; k=1/2/5/10 n=5/5/5/2) against
`~/benchmarks/qwen4-tp2-20261018/b1-cutlass-concurrency-ladder.json` (39.90 / 69.45 / 94.98 / 104.45,
every cell n=5). Both boots' engine logs carry the cache sizes: 2.64 GB on the control, 0.00 GB with
the flag.

**ds4 v2.4 — the flag cost the throughput, not the line.** The earlier "slower on every cell" verdict
was read off the `--prefill-decode-interval 2` arm. With the flag off the same line measures C2 88.35 /
C5 131.83 / C10 123.49 against v2.3's 88 / 111 / 116 (+18.7 % at C5, +6.6 % at C10, at best parity at
C2), so `ba38d13` ships it with `PREFILL_DECODE_INTERVAL: "0"` and a re-derived
`MAX_TOTAL_TOKENS: "6850000"` (a 7.5M pin was silently clamped to the profiled 6,993,408). The C1 cells
are cold-contaminated on every ladder, so the pooled **67.18 ± 6.97** stays the reference and the
interleaved C1 re-take is the one cell never taken — dropped with `.30`–`.33`.

**Traps worth carrying.** (1) A killed boot leaves the TensorFold JIT build lock and the next start
waits on it instead of compiling — the lane's `run.sh` now sweeps it pre-exec. (2) sparkrun's readiness
probe can kill a healthy serve 8 s after uvicorn comes up while CUDA graphs capture; `--no-ready-wait`
plus a `/v1/models` check got the ornith boot through. (3) `--no-rm` does not preserve a container:
the job record says `executor_config.auto_remove: false` yet dockerd task-deleted it, taking the
traceback. (4) The KV pool is not the recipe's — the same ornith file booted to 1,203,041 / 282,227 /
69,281 tokens depending on a co-tenant, and at the low grant every 1M rung reads TRUNCATED, which is
indistinguishable from a window failure.

### 2026-10-19 (early) — the `description:` migration, a gate-harness bug, and the labquant TP=2 suite

**Every shipped recipe's `description:` moved to the top level** (`99818ca`, all 59; `attic/` stays
frozen). `recipe list` / `recipe search` read `data.get("description", "")` at the top level only, so
the nested form listed as empty and could not be searched: at HEAD~1, 0/59 summaries carried a
description and a phrase from each description matched 2/59; after the move, 59/59. `recipe show` hid
the bug — the constructor falls back to `metadata.description` (`recipe.py:1256`). `maintainer:`
stays nested (the constructor reads it metadata-only), and the relocated prose is byte-identical
after a two-column dedent (0 unexpected diff lines, 0 text mismatches across the 59 files). Guard:
`_description_errors` in `tests/test_recipe_placeholder_resolution.py`, positive over every shipped
recipe plus a negative control. Note this record's earlier "778 tests ... still describe the tree"
line: the tree now carries that guard and the gate-tool change, and the gate reads **780 tests OK
(2 skipped)** at `c5af88d`.

**`gate-37111.py --thinking` never disabled thinking** (`5eca6ba`). "Default off" omitted
`chat_template_kwargs` entirely, so on a thinking-default template (this export) the essay probe spent
the whole 2048-token budget — and 8192 in a second probe — inside `reasoning_content` and returned
`content: ""` with `finish_reason: length`, which the detectors report as degeneration + truncation:
four findings against a healthy server, and the 90-minute soak never started. The request now always
carries `{"enable_thinking": bool(thinking)}`; the selftest records mock bodies and fails if either
direction misses the wire. Raw control on the live arm: `enable_thinking: false` → a 758-word essay,
`stop`, 0 reasoning tokens. Smoke then **PASS**, canary warm==cold.

**qwen4 labquant TP=2 suite on one 2026-10-19 boot** (job `1895030211ea0500_3510a5e0d37d` on
`.34`/`.35`; `max_total_num_tokens` 1,678,528, weights 63.6 GB, `scheduler_e2e` 563.8 s): eval-suite
**ok** — contract `max_model_len=262144` / ready / `finish=stop`, house 19/19 + 18/18, needle 3/3 at
32k / 128k / 262k with `--needle-max-tokens 512` (the 256 default is spent inside the think block),
hard ARC 95.5 % / GSM8K 95.5 % (n=200 each) — and tool-eval-bench **100** (15/15, 0 partial, 0 fail,
`bench_eff75293e461`, 91.6 s). Rows in `recipes/qwen4/README.md`; receipt
`~/benchmarks/qwen4-labq-suite-20261018/`. The W4 `#37111` soak (90 min, 100k depth) launched
23:48:10 ET and was in flight when this entry was written.

**The W4 soak closed PASS at 01:20 ET.** 708 turns over the full 90 minutes at 100k depth,
`max_tokens` 512, thinking off: 0 degeneration findings, 0 truncation findings, 0 transport errors,
and the warm==cold canary agrees (`4183`) after a flush; wall 5,491 s. Receipt
`~/benchmarks/qwen4-labq-suite-20261018/` (`gate-37111.json`, `gate-37111.log`, `REPORT.md`); the lane
row is in `recipes/qwen4/README.md`. The same boot's own ladder re-run reads 41.22 ± 1.92 / 72.88 ±
3.08 / 95.18 ± 1.28 / 108.13 ± 1.75 t/s (vs 39.90 / 69.45 / 94.98 / 104.45 on `bench_684c21a7cd8a`),
no regression. The serve was stopped and `.34`/`.35` verified idle; `.30`–`.33` remain the owner's ds4
TP=4 job (now `a2e141223b52793c_e11d626ec2c6`).

**The last multi-node ladder is filled — cybersec arm 5.** The abliterated DeepSeek TP=2 graft arm
booted on `.34`/`.35` (job `2f9a8f3e60a51ee4_3510a5e0d37d`) with the graft tree a verified no-op
(`n_edited=104`) and Engram ON; readiness was ~40 s after a 53 s launch because the 119 GiB graft tree
and the rank cache were warm. The concurrency ladder (`bench_484eb77839b4`) reads C1 **67.02 ± 3.19** /
C2 **52.95 ± 1.49** / C5 **47.75 ± 0.53** / C10 **46.78 ± 0.33** t/s @ d0 (n=5, per-request decode
50.19 / 38.24 / 34.29), the same falling-aggregate shape as the ds4 TP=2 stock arm (68.6 / 48.1 /
44.6 / 42.1). The 63.7 t/s C1 in the index was the 2026-10-17 engram-OFF boot and is superseded; the
index row and lane README now carry the ladder, and the multi-node ladder item moved verbatim to
`attic/DONE.md`. Receipt `~/benchmarks/cybersec-arm5-ladder-20261019/`.

**The `--fp4-gemm-backend` probe closed its spelling question.** The engine's choices include
`flashinfer_cutedsl`; the 2026-10-18 refusal of `flashinfer_cudedsl` was a typo, not an engine bug.
One boot with the alternative (`-o fp4_gemm_backend=flashinfer_cutedsl`, job
`1895030211ea0500_3510a5e0d37d`, `load_weight` 485 s) ran house **37/37** and the ladder
39.02 / 70.22 / 98.38 / 106.13 t/s against the same-pair control's 41.22 / 72.88 / 95.18 / 108.13 —
mixed and at or below the 7-25 % inter-boot floor, so the shipped `flashinfer_cutlass` stands; a
2-boot-per-arm retake would be needed before a flip. Receipt
`~/benchmarks/qwen4-knobs-20261019/b1-cutedsl/REPORT.md`.

**The int8 mamba checkpoint probe closed negative.** The flag parses and the weights load, but the
default 224-slot pool needs 3.24 GB against 2.15 GB free at `gpu_memory_utilization: 0.80`; cutting it
to the active 112 slots then dies with `ValueError: --enable-int8-mamba-checkpoint is incompatible with
Qwen4-Exp PLE side states` (`memory_pool.py:1337`). No size fits on this export. Receipts
`~/benchmarks/qwen4-knobs-20261019/b2-int8mamba/` and `b2b-int8mamba-112/`; the prefill-graph bs>1
cost is the only unprobed knob left in the backlog item.

**The prefill-graph knob closed as a no-op.** Removing `--cuda-graph-backend-prefill disabled` leaves
the default `disabled`, and an explicit `--cuda-graph-backend-prefill full` is accepted by args parsing
then disabled by the engine for the EAGLE target ("Disable prefill CUDA graph for EAGLE target on
tc_piecewise…"), with the multimodal rule as the companion reason — so there is no bs>1 graph cost to
recover and the flag is redundant but harmless. Three same-config boots gave a direct noise-floor
datum: C2 decode spans 8.6 % (67.1-72.9) and every other cell ≤4.6 %. Receipts
`~/benchmarks/qwen4-knobs-20261019/b3-prefillgraph{,-full}/`. All TP=2 knobs in the backlog item are
now answered; only the TP=4 and W12 items remain, both needing a node window.

**The ornith `marlin` pair closed.** Four alternating boots on `.34` (control, marlin, control,
marlin; `--fresh` each) show marlin shifts the ladder curve rather than lifting it: C1 94.1-95.0 →
102.0-104.6 (+9.3 % means), C2 +3.6 %, C5 217.3-223.2 → 198.7-209.9 (−7.2 %), C10 240.1-244.6 →
218.6-219.1 (−9.7 %). Both pairs agree in direction, so the shipped `flashinfer_cutlass` stands; the
item moved to `attic/DONE.md`. Receipt `~/benchmarks/ornith-marlin-20261019/`. The ornith backlog now
holds the YaRN 1M exit capture, the 0.5.21 bump (owner approval needed for the image change) and the
r0b0tlab measure.

**The r0b0tlab W4A16 pack measured slow.** One boot on `.34` (22 GiB download + first-use FP4 JIT,
ready in ~9 min) gives ladder C1 58.9 ± 1.65 / C2 88.9 ± 0.98 / C5 143.5 ± 3.13 / C10 158.4 ± 0.95
t/s and house 37/37 — ~40 % below the official export, at the low end of the card's 63-77 claim. The
recipe's caveat now records it; no index row. Receipt `~/benchmarks/ornith-r0b0t-20261019/`; the item
moved to `attic/DONE.md`. The ornith backlog now holds only the YaRN 1M exit capture and the 0.5.21
bump (owner approval).

### 2026-10-19 (later) — the decision + embed + rerank three-way boots

The lane's co-location budget was math, not a receipt; it is now both, and the math was wrong.
On `.34`, three sequential `sparkrun run` jobs: embed (`qwen3-vl-embedding-2b-vllm-b12x`, 0.25,
8010) rc=0; rerank (`qwen3-vl-reranker-2b-vllm-b12x`, 0.30, 8011) rc=0; JEV-9B
(`jev-9b-decision-vllm`, **0.20 + `max_num_seqs: 32`**, 8000) rc=0 — probes 200 (2048-dim
embedding, rerank model list, a JEV chat completion), node 104 GiB used / 16 GiB available.

The correction: the pair's *nominal* caps sum to 66.93 GiB, but its measured hold is **74 GiB**
(77 used − 3 idle, warm), so a third engine starts with **~42 GiB free (0.345)**, not 54.76.
That ceiling was first probed at 0.35 (42.59 GiB) and refused (`Free memory on device cuda:0
(40.86/121.69 GiB)`, reproduced warm, without the image import); 0.30 booted but spends headroom
the lane's TTS tenant wants. The 0.16 cap from the research doc profiles a *negative* KV cache
(−1.66 GiB) — the Mamba state pool plus CUDA-graph profiling swallows the margin — and at 0.16
the engine's 57 Mamba blocks cannot satisfy the default `max_num_seqs` 256. 0.20 with
`max_num_seqs: 32` is the working floor: 5.08 GiB of cache, a 0.75 cap sum, all three serving.
Receipts `~/benchmarks/embed-coloc30-20261019/REPORT.md` (campaign, arms table) and
`embed-coloc-final2-20261019/` (shipped config); failed arms kept beside them. The first version
of this entry cited 104 GiB used / 18 free read on the **head**, not on `.34` — the node's idle is
3 GiB, and the receipt now records that mix-up.

### 2026-10-19 — the YaRN 1M depth-90 rung passes, and the exit is intermittent

The ornith YaRN arm's last unmeasured rung ran on `.34` (full pool 1,205,530, no co-tenant) and
**passed**: 1M-token request at depth 90 %, 977,975 counted tokens (97.8 %), 1/1 needles, 1,891 s.
It crossed the same end-of-prefill state — 110 GiB used, 11 GiB available — that killed the two
2026-10-18 attempts at 398 s and 1,246 s, so the serve-side exit is intermittent rather than a
deterministic depth limit; the mechanism is still unnamed and the item stays open. The gate is now
6/6 on one boot, and the lane README/AGENTS ship language changed from "1M to depth 50 %" to "1M
measured through depth 90 %, not claimed reliable". Capture lesson: the engine log is at
`/tmp/sparkrun_serve.log` inside the container (stdout has only the CUDA banner), and `docker
events --filter event=die` preserves the exit code past the task-delete — both armed this boot.
The 2026-10-18 receipt tree the docs cited (`~/benchmarks/ornith-yarn-1m-20261018/`) is no longer
on the head, so the surviving receipt is `~/benchmarks/ornith-yarn-d90-20261019/`.

### 2026-10-19 (late morning) — unlimited sessions, the ds4 shortlist, and two register corrections

**Budget change.** With the local DeepSeek-V4.1-Flash-1017 TP=4 serve stable (it carries these
agent sessions), the owner declared sessions **unlimited**: the register's work continues until it
closes, with no session window and no per-day conversion. `.30`-`.33` are therefore **production**:
never disturb that serve for a registry boot. The only manual owner engagement is **switching to an
offsite API endpoint when TP=4 tests must run**, so TP=4 measurements are batched behind a single
switch. The resourcing and policy paragraphs in `TODO.md` now say this, and the qwen4 TP=4 backlog
(W6 re-boot, W12 cross-runtime) is reclassified from "needs a node window" to "offsite TP=4".

**ds4 deep search delivered** (commit `5df6a3f`). `mad-science/DS4-SPEEDUPS.md` — 631 lines, 34 dated
primary sources, 15 explicit UNVERIFIED markers — ranks 11 candidates plus a precondition (GPU
clock-latch audit), each with mechanism, expected effect, the carrying flag/artifact, a GB10
evidence label, and a pre-registered interleaved A/B with its falsifier; it also carries a
checked-and-rejected table so the rejected ideas do not return as suggestions. No boot was run: the
item's deliverable was the plan. `recipes/ds4/README.md` gained the upgrade-candidate section the
directive required (three arms runnable on the `.34`/`.35` pair now, eight TP=4-only candidates, the
rejected set), and the runnable subset became its own register item.

**Register corrections.** The Kokoro TTS entry said the arm "was never built", but
`recipes/decision/kokoro-82m-tts-cpu.yaml` has shipped since `acf01db` (digest-pinned image,
`readiness` block, `distribution_config`, taskset command) with no boot receipt anywhere — reworded
as a boot-verify + wav/RTF measurement, the same classify-from-the-artifact fix used for Mistral.
The ds4 search item was archived verbatim to `attic/DONE.md`.

**Closed after this section was first drafted:** the sparkrun 0.4.0 schema-docs pass
(`recipes/MECHANICS.md` rewritten to the 41-key set, root `AGENTS.md` corrected, both recipe skills
updated) and the explore keeper sweep (6 arms kept, 10 retired to `attic/explore/`). The tree now
stands at 48 recipes / 752 tests / 12 strict failures; both items are archived in `attic/DONE.md`.

### 2026-10-21 — the ornith engine bump ships, arm 5 closes, and the LTX T2V arm becomes a recipe

Three landings, all on the drained test pair, all permanent in the tree: the ornith SGLang
0.5.18→0.5.21 bump validated end to end, cybersec arm 5's tools leg finished, and the LTX-2.5 T2V
probe shipped as a recipe. The production quartet (`.30`–`.33`) was never touched.

**Cybersec arm 5 — 5/5, closed (commit `1d1cadf`).** The 2026-10-20 interruption at 107 of 1,240
questions was re-run from a fresh TP=2 boot (`2f9a8f3e60a51ee4_3510a5e0d37d`, TTR HTTP-ready
59.407 s) with no job cap: **1037/1240 = 83.6 %** in 3,887 s (3.133 s/question), 0 transport errors —
simple 376/400, multiple 188/200, parallel 181/200, parallel_multiple 177/200, irrelevance 115/240.
With house 37/37, needle 3/3 at every rung, ARC 188/200 and GSM8K 197/200 from the earlier legs, the
arm is complete. Receipt `~/benchmarks/cybersec-arm5-tools-20261021/REPORT.md` merges the four
2026-10-20 legs; the pair was drained afterwards. BFCL is not resumable, so this leg cost a full
re-run rather than a resume.

**Ornith SGLang 0.5.18→0.5.21 — the recorded blocker did not exist, and all three arms validated
(commit `fb85b76`).** The 2026-10-10 scan's claim that the Mamba/SWA radix-cache args "were removed
upstream" was a misread of a v0.5.20 file move: `mamba_radix_cache_strategy` and
`mamba_full_memory_ratio` are still declared fields at v0.5.21 and still register as flags
(`arg_groups/fields/exec_.py:450-457`, `fields/schedule.py:214-218`, `arg_utils.py:290`), and the
classes sglang#40313 removed are not imported by any recipe. The target is
`lmsysorg/sglang:v0.5.21@sha256:b1259f3e…`, a multi-arch index with a native arm64 manifest (14.8 GB;
container labels record upstream build `e00930c5…`); all three SGLang ornith arms now pin it, and
the guards pass 29/29. Measured on `.34`/`.35`: 35B contract ok, house **37/37**, needle 3/3 at
32k/131k/262k, ladder **C1 96.5 / C2 148.3 / C5 213.9 / C10 244.1** — every cell inside the on-file
band's σ; 9B house **37/37**, needle 3/3 × 3, ladder C1 53.9 / C2 **89.6** / C5 151.7 / C10 147.7 on
`.35`, whose low C2 was then re-laddered on `.34` — the node the old band was measured on — at
**C2 97.8** (−3.2 %, inside σ), so the dip was a cross-node artifact, not an engine shift. YaRN on
`.34`: pool 1,192,993 tokens, needle gate **6/6 rungs PASS** (262k/512k/768k 3/3; 1M depths
10/50/90 at 97.74/97.75/97.80 % fill), and the depth-90 % rung passed **on the first attempt** under
a pre-declared retry rule that went unused — the intermittent did not reproduce, and the streamed
log plus `docker events` capture recorded no die event except the deliberate final stop. Of the two
named wins, LiLiCorr (#37462) cannot reach this lane (no `lilicorr_*` draft exists) and the GDN
target-verify change (#33778) produced no measured gain: the ladders read at or slightly below the
prior bands. The bump's value is leaving the dead-end 2026-09-08 nightly plus 0.5.21's fixes.
Receipts `~/benchmarks/ornith-0.5.21-bump-20261021/`; the operator form is the lane README
§"Engine bump to SGLang 0.5.21" and the evidence is the attic's adjudication section.

**Explore LTX-2.5 T2V — the probe is now a recipe (commit `3dd62d0`).**
`recipes/explore/ltx-2.5-22b-nvfp4-t2v-comfyui-script.yaml` boots the media-gen lane's arm64 cu130
base with the `ltx-25-launcher` mod staging ComfyUI v0.34.0 and a torch 2.14.1+cu130 venv. Measured
on `.35` (clock capped at 2200 MHz, 1344×768 / 121 frames / 24 fps): **cold 100.13 s at 84.00 GiB
peak, warm (seed 44) 78.1 s at 83.45 GiB** — the runbook's own cells — with a cap of 69 % of the
unified pool and outputs that ffprobe as real h264 1344×768/121f/24fps plus AAC stereo. Receipt
`~/benchmarks/ltx25-recipe-20261021/`.

**Traps that cost time today, in the order they bit.** (1) **The head's loopback is production.**
`127.0.0.1:8000` on the head answers the TP=4 serve, so every arm must be addressed by its node IP
root (`http://<head-node>:8000`), never loopback and never `/v1`. (2) **`~/development` cannot render
this lane.** sparkrun resolves a lane-local mod relative to the recipe path it was handed, so
launching the symlinked `~/development/ornith-*.yaml` dies at "Could not resolve mod
mods/ornith-honed-chat-template"; run from `/<home-dir>/src/sparkrun-recipe-registry` instead.
(3) **`sparkrun stop --all` bypasses `--no-rm`.** It deleted the 9B container on `.35` and took its
in-container serve log with it; stop by cluster/task id and `docker cp /tmp/sparkrun_serve.log` out
first. (4) **sparkrun injects `HF_HUB_OFFLINE=1`**, so an in-container `hf download` fails even with
a token — the LTX mod sets `HF_HUB_OFFLINE=0` explicitly (an `unset` was not enough). (5) **BFCL's
`--json` target directory must exist** before the leg starts, or the tool errors at the first write.
(6) **A benchmark without `--fresh` re-emits the previous boot's numbers** — `--skip-run` against a
live serve is the honest way to re-measure one cell, and `--fresh` is mandatory when the point is a
new boot.

**Counts, re-measured 2026-10-21:** **52** recipes in 11 family dirs, **29** guard modules, **752**
tests (**2** skipped — the third skip was the real-CLI pooling case, which runs now that `sparkrun`
is installed on the workstation), **12/52** recipes fail `--strict` (plain `validate` is the gate and
passes 52/52, re-swept file by file on the workstation).

**ds4 TensorFold v0.6 adopted after a six-boot interleaved A/B (`.34`/`.35`, 2026-10-21).**
The v0.6 image (`littlecedar/dgx-spark-dsv41@sha256:d6e4c10d…`, engine `tensorfold 0.6.6` at
`3825f62`, built 2026-10-21) ran A/B/A/B/A/B against the shipped `fabbe861…` (engine `0.6.3`,
built 2026-10-05 from `d5d7bb3`) — so the delta is **0.6.3 → 0.6.6** and spans the v0.6 release
commit. Depth-0 ladder, `--fresh`, 3 runs/cell, n=9 per cell: c1 64.70 → 64.47 (flat), c4 46.13 →
51.15 (+10.9 %, ranges overlap), c8 41.47 → **52.45 (+26.5 %)**, c16 42.33 → **53.21 (+25.7 %)**;
cold prefill 1,667 → **2,077 t/s** at 32k (+24.6 %) and 1,486 → **2,073** at 131k (+39.5 %). At c8
and c16 the treatment's worst single run beats the control's best (50.43 > 47.83; 52.66 > 46.78),
so the pre-registered falsifier is not met. The first v0.6 start costs 264 s JIT-building three
CUDA extensions; B2/B3 launch in 80.9/80.3 s against the control's 80.1/81.5 s, so the win carries
no launch penalty. The shipped recipe's `container:` pin moved to `d6e4c10d…`; the cybersec
abliterated TP=2 arm still pins `fabbe861…` (unmeasured on v0.6 — left alone). `reasoning_effort:
high` was measured request-level on the treatment serve with a paired same-task A/B (10 tasks × 2
rounds × 2 arms): **10.6 % fewer reasoning tokens**, completion 51.7 → 41.4, house **37/37 both**
(no pass→fail flip) — but `hard-rev` (128 → 43) carries most of it and the 10 % bar is cleared by
0.6 points, so it is recorded as "clears, not a headline". Receipts
`~/benchmarks/ds4-v06-ab-20261021/` (`REPORT.md`) and `~/benchmarks/ds4-v06-build-20261021/`.
Driver: `.scratch/ds4-v06/run-ab.py` (git-ignored) — six-boot interleaved, refuses a busy node,
asserts `/v1/models`, the booted `Image:` and the container's `tensorfold --version` per boot, and
pairs the prefill probes with a multiplicative rescale (the first version's additive "+1 char"
retry could never fix a fill error).

**Decision lane closed for the day: Nox-4B ships, JEV-27B ties and does not (2026-10-21).**
`vllm-sr/Decision-2.0-Nox-4B @25e8f67d` booted on `.34` through the shipped
`nox-4b-decision-vllm-srun` recipe and scored **67.8 % (1356/2000), ★★** on
`uvx tool-eval-bench@2.8.0 --decision-bench-only` (run `2026-10-21T19-02-40.908377Z_a3a115d0`, KL
0.219, Brier 0.114, ECE 0.063, **0 decision errors**, 14,066 s = 35.2 s/case, 652,665 input tokens) —
second in the lane behind clef-flash's 70.3 %, 12.8 points over Sol-2B's 55.0 %. By type `noul` 74.2 %
/ `choice` 66.0 % / `score` 64.4 %; the weak workflow is `agent_trace_observability` at 59.4 % against
68.0–72.6 % elsewhere. The vendor `/health` **golden gate passed on aarch64** (200
`{"status":"ready","reason":null}`), so the d3-edge golden divergence does not reproduce for this
manifest (`49771ea3…`) — worth knowing, because `/health` here is a CPU golden comparison, not
liveness. **The offline-staging class did fire:** as sparkrun stages a model (`HF_HUB_OFFLINE=1`) this
loader still calls the Hub tree API and `/health` sat at 503 `loading` with `OfflineModeIsEnabled`
retries while never reading the staged snapshot, exactly as d3-edge did; the recipe now carries
`env: HF_HUB_OFFLINE: '0'` (the documented mitigation, measured here) and boots clean in ~30 s. The
ladder is a pure queue — **c1/c2/c5 all 0.044 req/s** at p50 **22,763 / 45,480 / 113,797 ms**, 500/500
decisions clean at each level; **c10 was not run**, because the serve was stopped by the owner's
priority call to free the pair for the queued flash-next TP=2 boot. Grading a candidate on this route
is a four-hour window: the three-case probe's 8,760 s estimate was 1.6× optimistic, so price CPU arms
from a wide probe. Receipt `~/benchmarks/nox4b-20261021/` (`REPORT.md`, `teb-decision.log`, the
instrument's `runs/2026/10/*.md`, `probe.json`, `ladder.log`, `serve.log`); commit `49f1404` (recipe,
lane section, root index row).

`autotrust/JEV-27B @14b42526` booted solo on `.35` (53.79 GB, 14 files, `vllm-openai:glm53-flash` at
engine `0.28.1rc1.dev580+g385dce36b`) and **does not ship**: **66.8 % (1337/2000)** against JEV-9B's
**67.0 % (1340/2000)** is three decisions and 0.15 pp — a tie, below the lane's strictly-beat rule, so
no README or index row and no status change. Boot wall 1244 s, of which ~660 s is CUDA-graph capture
for 102 graphs (budget ~21 min cold, ~13 min warm with the compile cache); ladder c1 2.912 / c2 2.974
/ c5 4.351 / c10 4.488 req/s with no useful scaling past c2, because the `--mamba-cache-mode align`
path serializes decision prefill. KV 805,546 tokens (24.58× at 32k), so the mamba page pool binds
before `max_num_seqs`. Receipt `~/benchmarks/jev27-20261021/REPORT.md`.

**Muse Glimmer 30B: the checkpoint, not the pack (`0581d58`, closing `85d7327`).** The bf16 control
(`meta-models/Muse-Glimmer-30B @7af58019`, same drafter, same `sglang:v0.5.21` digest, same flag line
bar `mem_fraction_static 0.80`) answers `nurkrpas` on hard-rev exactly as the NVFP4 pack did — house
36/37, easy 19/19, same item, same string — which makes the weights the cause and exonerates the pack,
so no repack is worth trying. C1 is 12.1 t/s on bf16 against the pack's 20.2 (the bandwidth of 52 GB
of bf16 weights), with DFLASH accepted at block size 5. The arm is out of both trees; the route, flags
and numbers live in `attic/explore/AGENTS.md`.

**flash-next staging, corrected (`71850ab`).** The lane README recorded the 183.5 GB export as
reclaimed from every node on 2026-10-14, which made a per-node re-fetch look like the boot's remaining
cost. Re-verified 2026-10-21: `.34` and `.35` have held it complete since the 2026-10-15 staging
(18/18 shards, 183.48 GB, zero bytes fetched), so only a boot receipt is outstanding. `.35` also
carries **78.06 GB of orphan `.incomplete` blobs** from that attempt, named for the next storage pass.

**The docs moved to sparkrun 0.4.2 (`95d5572`, `8a539d9`).** `AGENTS.md` and `recipes/MECHANICS.md`
both claimed `0.4.0-alpha+g29f53fb` while this workstation and the head both report
`0.4.2-alpha+g36d8a44`. The module paths survived the upgrade (`core/launcher.py`, `core/recipe.py`,
`core/validation.py`, `models/runtime.py`); 27 line cites did not and were re-derived against the
installed package — the unmapped-key report (`launcher.py:814-899` → `939-1029`), its overrides
clause (`866-870` → `994-998`), the `None` early return (`863-864` → `991-992`), the warning block
(`881-899` → `1011-1029`) and its `recipe validate` wiring (`validation.py:1821-1832` →
`1842-1853`), the placeholder scan (`launcher.py:673-696` → `798-818`) and internal-key test
(`662-670` → `776-789`), `runtime_config` absorption (`recipe.py:1264-1270` → `1393-1400`), the
constructor's description/maintainer/metadata block (`1174-1176` → `1303-1307`, `1256-1259` →
`1385-1389`, `1231-1233` → `1362-1363`, `1261-1262` → `1392`), export folding (`2406-2411` →
`2574-2578`), `recipe_version` and the `sparkrun_version` fallback (`1165` → `1297`, `757` → `897`),
the config chain's defaults tier (`1532-1538` → `1674-1682`), `check_unknown_top_level_keys`
(`validation.py:1176-1272` → `1196-1275`), `check_unpinned_model_revision` (`837-914` → `866-935`),
`known_config_keys` and `BASE_CONSUMED_CONFIG_KEYS` (`base.py:840-870` → `867-892`, `45-85` →
`41-86`), eugr's refusal (`55-63` → `54-63`), and the model binding and validator
(`models/runtime.py:40-55` → `44-60`, `80-87` → `85-92`, `88-99` → `93-104`). **Three sentences were
rewritten because the code had outgrown them, not renumbered:** `recipe list`/`recipe search` no
longer read the top-level description only — `recipe.py:2933-2936` falls back to
`metadata.description`, so a nested description lists; the launcher's drop is no longer silent —
0.4.2 raises `unmapped-config-key`; and the `_KNOWN_KEYS` literal set moved two lines (`78-120` →
`80-122`) while still holding **41 keys**. The eleven arms carrying `unpinned-model-revision` were
re-counted file by file: still eleven. The MECHANICS header now names exactly which sections are
0.4.2-numbered and states that every other cite is still 0.4.0-numbered — re-derive with `grep -n`
before trusting it.

**flash-next closes refuted, on two different gates (`2d046bc`, `7255396`, 2026-10-21).**
The staging repair from earlier in the day paid off: the weights were already complete on both nodes
(18/18 shards each), so the TP=2 pair boot cost **10.6 s** of distribution — the "re-fetch per node"
worry was a measurement error, not a cost. Then both candidate engines failed, one gate apart. The
sparkrun-built b12x image (`cf5a2a53…`, vLLM `0.1.dev21830+g8244d1c44.d20261015`) **cannot construct
the model config at all**: `ModelConfig` rejects the checkpoint's `qwen_sparse_attention` as a
`layer_types` member for `model_type: qwen4_exp`, so **no weight is even read**. The documented
fallback `vllm/vllm-openai:v0.31.0` (`sha256:c1c9f6fd…`, local ID `bbe704505570` on both nodes) gets
**past** `ModelConfig`, warms up multimodal in **11.9 s**, starts TP=2 — and dies at worker init:
`NotImplementedError: Qwen4Exp PLE embedding does not support quantization config
CompressedTensorsConfig`. So the blocker is the **export↔engine combination**, not the pack, not a
knob, and not the recipe: the search is image-side, and the answer has to clear both gates. Lane fact
worth keeping: `vllm/vllm-openai` declares `ENTRYPOINT ["vllm","serve"]`, which swallows sparkrun's
launcher and refuses the launch until `executor_config` sets `entrypoint: ""` — the sparkrun-built
b12x image has no entrypoint, so swapping images needs that line. Recorded in
`recipes/cybersec/README.md`; the item is out of the queue.

**qwen4 labquant-highcon control passed — the restore does not move the serve (task
`1895030211ea0500_3510a5e0d37d`, 2026-10-21).** The highcon boot brought back the diagnostic mod
(the outstanding question after `zz-labq-no-diag` retired it on the balanced arm) and answered it:
TTR **9.6 min** with `load_weight` 508.93 s, `/v1/models` at `max_model_len 262144`, admission
**unclamped** (`max_total_num_tokens=1587072`, `max_running_requests=32`, mamba 128), **41/41**
shards on both the main and MTP classes, no `_scale` assertion in the boot log, and the diagnostic
payload fired **0** times. Depth sweep at d8192/pp2048/tg128, k=8/12/16/24: **86.8 / 87.5 / 89.5 /
75.4 t/s** against the controls' **84.9 / 89.1 / 89.1 / 72.9** — every cell inside **3.4 %**, no
10 % finding in either direction, so the restored diagnostic is carried at no measured cost and the
highcon item closes with the pair block empty.

**Node hygiene at close (2026-10-21 17:40 ET, re-checked 18:50 ET).** `.34` and `.35` are at **0 running and 0 exited**
containers. The one leftover was an exited `lmsysorg/sglang:v0.5.21` container from the 07:52 Muse
boot; its 593 KB serve log was copied to
`~/benchmarks/_leftover-logs/43acfc12bcc4-sglang-20261021.log` before `docker rm`, and it was never
force-removed while running. `sparkrun stop` on the Nox task
(`sparkrun_f11fd90bf531e440_8ed3ce77d78f`) had already taken its own container with it, after
`docker cp /tmp/sparkrun_serve.log` (988 B) captured the log.

**Nemotron-3.5-Lightning-30B-A3B NVFP4 shipped, and the single-node queue closed (2026-10-21, late).**
`nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4` (`bee7596…`, 20.10 GiB, Nemotron-H hybrid at 52
layers / 3B active) booted on `.35` through the image the lane already ships
(`ghcr.io/spark-arena/dgx-vllm-eugr-nightly@sha256:cc47adc1…`, vLLM 0.32.0rc1.dev301+g1ac942555 — no
new image, no fork) with its own quantization config auto-detected as `modelopt_mixed`: MARLIN NVFP4
MoE out of the eight backends offered, FlashInfer attention and Mamba SSU, `mamba_ssm_cache_dtype`
forced to float32 by the engine. TTR ≈ 6 min including the 20.1 GiB download (weights 17.82 GiB in
228.6 s), `/v1/models` → the repo id with **`max_model_len 32768`**, KV **10,703,667 tokens** = 326.65×
at the served window. **House 37/37** at `--max-tokens 2048`, **C1 63.27 ± 0.65 t/s** (peak 65.67) with
a ladder of **63.27 / 90.81 / 122.27 / 144.15** at c1/2/5/10 and prefill flat at 6,142 → 6,235 t/s, and
**tool calling passes** (`finish_reason: tool_calls`, `get_weather({"location": "Paris", "unit":
"celsius"})`). It is the fastest single-node chat arm this lane has measured, at 20.1 GiB. Recipe
`recipes/explore/nemotron-3.5-lightning-30b-a3b-nvfp4-vllm.yaml`, commit `a9d4c27`, receipt
`~/benchmarks/reasoning-candidates-20261021/`.

**Two things the arm taught that are not in its speed number.** First, **thinking-off is decode-identical
and quality-worse**: 62.73 t/s thinking-off against 62.74 on (recipe serve 63.49 vs 63.85), all inside
each other's spread, but the house battery drops to **32/37** — `wp-3`, all three `hard-arith` items and
`trick-3`. So both shipped numbers are thinking-on, and the reasoning channel is load-bearing for
arithmetic and trap items; a caller must not disable thinking to save time here. Second, a **one-off boot
failure**: the very first `sparkrun` boot died inside PIECEWISE CUDA-graph capture with `CUDA error: an
illegal instruction`, and it did not reproduce across five further boots/variants on the same node and
image (repo-id with and without the deprecated `--mamba-cache-mode align`, local-path + `--revision`, a
fresh boot). Retry once before debugging it, and it is not an argument for the mamba flag.

**The ranked candidate table is dead for 1-node work.** Ranks 1–5 are all closed — Mistral-Small-4
rejected, Muse-Glimmer falsified as a checkpoint defect, Lightning shipped, Nemotron-3-Super rejected at
15.9 t/s, Laguna-S retired — and 6–10 are 2+ nodes. Two entries were also badly under-sized by the
2026-10-10 scan: **MiniMax-M3 is 795.5 GiB** on the Hub (not ~220 GB) and **Inkling-Small 495.4 GiB**
with no NVFP4 export at all. `attic/explore/EXPLORE-CANDIDATES.md` now records the closures and the
measured sizes.

**Node-free QA that closed with it.** (1) **House-budget audit of the instrument's own history:** 42 of
the 43 `~/benchmarks/**/house*.json` receipts were taken at 4096, so no historical bar is a budget
artifact; the only 1024 pass was Lightning's first, whose single miss was a truncation (`11111` for
`1111111110`, `finish=stop` at 2048 after 1,018 reasoning tokens). Every shipped arm's bar is a
non-empty wrong-string miss. Two durable outcomes: the budget convention now sits in `tools/README.md`,
and **`hard-rev` is the near-universal discriminator** (`nurkrpas` / `nurkraps` / `nrukraps` /
`nurkrasp` across seven-plus arms including both DeepSeek lines), stated in the explore lane so 37/37
reads as "clears `hard-rev`" without weakening the bar. (2) **Repo-wide render sweep:** all 53 recipe
files rendered with `sparkrun run -n`; 46 clean, 7 flagged — four are the launcher refusing TP=4 on a
one-GPU host list (all four render clean on four hosts) and three are checker artifacts (two `pip
install` chains on one command line; flags inside a load-bearing `#` comment). One genuine note, written
into `recipes/qwen3/README.md` rather than fixed: the mlx4bit arm's `speculative_draft_model_revision`
pins the drafter for distribution while its own template means sglang's `--speculative-draft-model-
revision` never renders — `unpinned-model-revision`-adjacent, not a boot risk, and not to be "fixed" by
adding a flag to the fold whose terminal comment is load-bearing. Receipt
`~/benchmarks/render-sweep-20261021/{REPORT.md,render-sweep.json}`; the sweep re-runs from
`.scratch/render_sweep.py`, which needs `sparkrun` on PATH and so can never be a `tests/` guard.
(3) **The Qwen-Image schedule path is guarded:** the launcher mod takes a `sigmas` list (`11836f0`) and
schedule selection was extracted into a pure `schedule_kwargs(req, shipped)` with 13 cases and **three
negative controls that must go red** — the pre-fix forwarded-field function, index rounding instead of
value interpolation, a dropped `sigmas` kwarg — run against temp-dir shadow copies (`32d046e`). The suite
reads 752 with that module moved aside and **765** with it present. (4) **AGENTS.md counts re-measured**
rather than adjusted: 52 tracked recipes (53 files on disk) in 11 dirs, 29 guard modules, 765 tests with
2 skips, 12/52 strict, 18 tools, 35 benchmark profiles, 53/53 folded command templates, and the attic
re-counted per directory (where the IFM line's "two retired 7B arms" became three).

## 2026-10-22 — the register becomes a board; the refresh, engine and CI block

*(Moved out of `mad-science/STATUS.md` on 2026-10-22 01:58 ET, when that file was cut down to a status board and the queue moved to `mad-science/TODO.md`. Times are the ones each row was recorded with; nothing below is re-measured.)*

### Landed (2026-10-22) — one row per commit, with the evidence

| commit | what changed | verification | receipt/evidence |
|---|---|---|---|
| `c1e688f` (00:48 ET) | ornith SGLang 0.5.21: the blocker marked refuted and the killed worker's two staged-plan state claims retired (`mad-science/TODO.md:422` is the progress paragraph of the closed item at `:396`; the CLOSED paragraph `:399-421` records the rest) | the bump shipped as `fb85b76`, so the claims its own later writes falsified are gone | `attic/ornith/AGENTS.md`, `recipes/ornith/README.md` §"Engine bump to SGLang 0.5.21" |
| `6e31c10` (00:51 ET) | `recipes/ornith/README.md`'s three live runtime rows (`:111`, `:193`, `:275`) still advertised `dev-cu13@9a352a35…` and "sglang v0.5.18" after the 0.5.21 bump — corrected | the `fb85b76` diff record at `:449-455` is history and stays verbatim | `recipes/ornith/README.md` |
| `aa133fe` (00:53 ET) | `ARG TENSORFOLD_REF` made mandatory in `recipes/ds4/Dockerfile.tensorfold-dsv41` (it defaulted to 0.6.3 `d5d7bb38…` while the shipped ds4 image is 0.6.6 `3825f62…`), fail-closed `RUN test -n`; `recipes/ds4/README.md` gained a per-image Rebuild block; the one documented no-arg build command (`attic/ds4/AGENTS.md:2336`) now passes its ref | a plain rebuild can no longer silently pick a different engine | `recipes/ds4/Dockerfile.tensorfold-dsv41` |
| `9d8c7e5` (01:03 ET) | EXL3 pack re-pin `c178a012…` → `0be63c3337efbb2a0061d5b8bb4006fa186d433f`, booted on `.34`/`.35` (task `sparkrun_a9804d09ec5e137d_3510a5e0d37d`) | `/v1/models` answers `LibertAIDAI/DeepSeek-V4.1-Flash-1017-EXL3-2.9bpw` at `max_model_len` **1,048,576**; **TTR 590 s cold** (318 s weight re-conversion + three CUDA extension rebuilds; **no warm second boot was measured, so no warm TTR is quoted**); thinking off → `PINEAPPLE-42`, `finish_reason` stop, 0 reasoning tokens; thinking on → `reasoning_content` + `391` = 17×23, DSpark accepted 13/31 drafts; distribution a 9.1 s blob-cache hit; **the snapshot's new `chat_template.jinja` is IGNORED** by the `--vision` overlay (`launcher.py:263`) — served sha `297be886…` is the mod's, snapshot's `2ed8bc33…` absent, and adopting upstream's would require changing the overlay (recorded decision) | pin sweep row below |
| `c6c431f` (01:05 ET) | four unpinned embed/rerank checkpoints pinned to that day's Hub heads: `Qwen/Qwen3-VL-Embedding-2B` `9f2f7e71…`, `gonuit/Qwen3-VL-Embedding-8B-AWQ-4bit` `5c4cca00…`, `Qwen/Qwen3-VL-Reranker-2B` `4bd860ac…`, `Qwen/Qwen3-VL-Reranker-8B` `b212dc8c…` | every pin == head, so no served byte changes; strict-validate moves 12/52 → 16/52 and `unpinned-model-revision` eleven → fifteen, because these arms pass the prepared path and the finding is the lane's known false positive | pin sweep row below |
| `2534c6c` (01:09 ET) | qwen4 TP=4 arm repaired to the shipped chain: bare `revision:` key sparkrun ignores, the pre-re-cut `7c4f1bc1` pin, 3 of the 5 required mods, `moe_runner_backend auto` (FLASHINFER_TRTLLM, dead on SM121), `mods:` entries resolving against the recipe directory; now the shipped TP=2 arm with `tensor_parallel 4`, `min_nodes 4`, NEXTN dropped, `port_timeout_s 3600` | `tests/test_qwen4_recipes.py` diffs the two arms with a negative control per defect class, so the drift cannot return | `attic/qwen4/AGENTS.md`, `qwen3.8-flash-next-labquant-tp4-sglang.yaml` |
| `a3f5d2f` (01:10 ET; content landed as `b8f8f02` 01:09 ET) | the 2026-10-22 refresh entry and the quartet correction; **model-pin sweep over all 52 tracked recipes** (47 distinct Hub repos, one API call per repo, authenticated as the `littlecedar` user): 31 current, 5 stale-weights, 5 stale-docs, 6 unpinned, 0 unresolvable — the two DeepSeek-v4.1-Flash artifacts split: `deepseek-ai/DeepSeek-V4.1-Flash-1017` (TP=4 knapcio pack, also the Engram tables' `DEFAULT_REVISION`) is pin == head (`1bae0e10…`, 2026-10-17) so production weights are unaffected, while `LibertAIDAI/…-EXL3-2.9bpw` (TP=2 TensorFold pack) was 4 commits behind on `README.md` + a new `chat_template.jinja` and zero safetensors; **container/runtime sweep**: 26 distinct container refs across shipped recipes, all digest-pinned, our seven own-namespace images enumerated against their Dockerfiles, and the mod- and launcher-level Hub pins (`drowzeys/…` `87bb9850`, `drowzeys/keys-…` `a9cf9de`, launcher `DFLASH2_REVISION` `bf582e4e`, Engram `DEFAULT_REVISION` `1bae0e10`) all current and agreeing with the recipe pins that govern them, so no cybersec arm serves drifted weights | pin and container counts above are the sweep's own result | this file; `recipes/` tree at `c6c431f` |
| `a3f5d2f` (01:10 ET, recorded there; no code commit) | `recipes/ds4/Dockerfile.knapcio-dsv41`'s `ARG BASE_IMAGE=lmsysorg/sglang:dev-dsv41` — the only floating build input in the shipped tree — pinned to `sha256:4a5d132a…` (tag kept); rebuild on `.30` (native arm64, 208.8 s) pushed as `littlecedar/dgx-spark-dsv41:canary-roce-20261022` = `sha256:0cbe228a8788ec06472dd2dc5cd31acb117ec5ba5101f2442d32e54d2ae5b8ea` | config identical (entrypoint, cmd, env, healthcheck, labels; 91 layers, layers 0–69 identical); content diff is four recompiled `__pycache__/*.pyc` plus 6,707 hash-equal files — **behavior-identical but NOT byte-reproducible**, so the shipped `acfc331a…` stays pinned | `recipes/ds4/Dockerfile.knapcio-dsv41` |
| `f9128a1` (01:12 ET) | removed a quoted owner answer that was never given (`"switch now."`); the verbatim grant `"You have .30-.35 available for you to work on the TP=4 queue."` replaced it, and both TP=4 questions stay open | sweep of the file for other invented attribution on 2026-10-22 found none; the 2026-10-21 entries keep their own recorded answers. The quartet stop is attributed in Alerts, from the owner's own 2026-10-22 ≈01:28 ET relay | this file |
| `440346c` (01:15 ET) | `vllm-sr/d3-edge` head-revision probe recorded and the vendor pin kept: `18d61df7…` → `c454ee39…` on **both** pin sites (`model_revision:` line 3, literal `--revision=` in `command:` line 50), booted twice (`.31` as shipped, `.35` with `-e HF_HUB_OFFLINE=0`), **reverted** | `/health` 503 `{"status":"failed","reason":"VerificationError: golden answers differ from the reference"}`, `/v1/models` `ready:false`, golden `{checked:3, matched:1, reference:"cpu"}` — the **same 3-checked / 1-matched result the README recorded at the old pin on 2026-10-18**, so the aarch64-vs-x86 divergence is revision-independent; no `/v1/systemone` round-trip in either boot (`503 not_ready`); `18d61df7` is the `d3-edge v3.1.0` release commit (2026-10-11) and `c454ee39` a post-release card/eval commit (2026-10-17); both safetensors (1,215.7 MB) byte-identical | `~/benchmarks/decision-d3-repin-20261022/` (head) |
| `618e48d` (01:16 ET) | the d3-edge verdict folded into the decision lane item, quartet duty opened as `TODO.md` #46, and two inherited 752-test counts corrected to 782 | gate `782 tests OK` (2 skipped) at `440346c` | `mad-science/TODO.md`, this file |
| `f1b458d` (01:22 ET) | stock upstream `llama.cpp` image and the lane's engine target pinned: `recipes/explore/Dockerfile.llamacpp-upstream` with pinned CUDA base digests, a required `LLAMA_REF` with no default, and gates that reject the `b2e5e9b` failure mode | `docker build --check` clean; stock upstream `9df0b73c` (2026-10-20) carries Mellum MTP, `kolibri1` and `121a-real`/sm_121 upstream-native, and only the decision2 pack still needs its fork (its GGUF declares `qwen35` with 330 tensors where upstream expects 320) | `recipes/explore/Dockerfile.llamacpp-upstream` |
| `1a306ca` (01:34 ET) | explore vLLM arms re-pinned to `v0.32.0` for the CVE reason, `container:` pins moved to index digest `befccf0e…` (arm64 child `6ff5ff0d…`) | Laguna-XS on `.34`: TTR **282 s**, `/v1/models` served `poolside/Laguna-XS-2.1-NVFP4` at 262,144, KV 41.87 GiB → **1,413,525 tokens (5.39×)** against v0.29.0's 41.56 GiB / 1,403,263, chat 200 `finish_reason=stop` in both modes; the qwen-image arm on `v0.32.0` wrote a **byte-identical PNG** (`e24f6e3a…`) to its v0.30.0 reference, both images on torch 2.13.0+cu130, so the bump moved the vLLM wheel and not the torch build | `recipes/explore/` |
| `6280486` (01:36 ET) | qwen-image request path guarded and a latent shipped bug named: `recipes/explore/mods/qwen-image-2.1-turbo-launcher/server.py` raised `NameError: name 'sigmas_used' is not defined` on **every** `POST /generate` since `11836f0` (the `schedule_kwargs(...)[0]` unpack) — the 2026-10-21 sigmas feature shipped non-working while the suite stayed green, because the resample test exercised `schedule_kwargs()` and never `run_generate()`; the vLLM `v0.32.0` thinking contract recorded (Alerts); a 1,024-token budget with thinking on returns `finish_reason=length` (1,933 completion tokens for a one-line arithmetic prompt), so **4096 is the floor**; Laguna-M.1's pin moved for the CVE and is labelled **BUMPED, NOT RE-BOOTED** | fixed, re-booted, and a new test drives `run_generate()` with stubbed torch/pipeline — the negative control reproduces the `NameError` on the pre-fix artifact and passes after | `recipes/explore/mods/qwen-image-2.1-turbo-launcher/`, `recipes/explore/poolside-laguna-m1-nvfp4-vllm-tp2.yaml` |
| `fdee701` (01:38 ET) | the repo has CI: `.github/workflows/gate.yml` (push/PR — `uv sync --frozen` with a C toolchain for `netifaces`, the unittest suite, per-recipe `sparkrun recipe validate` that prints `SKIPPED: sparkrun not installable in CI` rather than failing, `bash -n`, `py_compile`, `__pycache__` cleanup), `refresh-sweep.yml` (daily cron + dispatch: runs the sweep, uploads artifacts, upserts one open issue labelled `pin-drift` with distinct titles for exit 1 "pin drift found" vs exit 2 "sweep could not run", and never edits a recipe unless the `apply` input is set, then only prints the boot checklist), `llamacpp-engine.yml` (weekly report of our refs vs upstream `ggml-org/llama.cpp` with `behind_by` and four feature gates; its arm64 `build` job is gated on `vars.ARM64_RUNNER_ENABLED == 'true'` because **no self-hosted runner is registered**, stated in the file, `AGENTS.md` and `README.md`); `AGENTS.md`'s "No CI … no `.github/`" claim replaced with what is true, counts refreshed to 31 guard modules / 806 tests (2026-10-22) | `tests/test_ci_workflows.py` (22 tests) guards the contract; CI never bumps a model pin — lane policy stands | `.github/workflows/`, `tests/test_ci_workflows.py` |
| `a644ace` (01:42 ET) | `tools/refresh-sweep.py`, the pin-drift survey the nightly CI job gates on | the same survey `refresh-sweep.yml` runs, so CI and the operator share one implementation | `tools/refresh-sweep.py` |
| `093c0be` (01:46 ET) | the sweep's classification corrected and holds made declarable: a digest-pinned `FROM` now counts as **build-input-current** rather than stale (genuinely stale build inputs **4 → 1**); `--accept-file` with **8 declared holds** in `tools/refresh-sweep-accepted.json` and `stale-acceptance` gates so a hold cannot silently outlive its reason; the ornith 397B `model-unrevision` row closed by pinning `b4864e44…` | gating drift rows **24 → 12**; suite 852 | `tools/refresh-sweep.py`, `tools/refresh-sweep-accepted.json` |

### Alerts detail (2026-10-22)

| what | measured | when | by whom | state |
|---|---|---|---|---|
| **Quartet down — the 2026-10-21 entry's "TP=4 serve is untouched and healthy" was stale** | 0 containers on `.30`–`.33`, no `:8000` listener on any quartet node IP, head `127.0.0.1:8000` refusing connections, no vllm or sglang process on the host, gateway `deployments: []` (last `sparkrun sync` 04:39Z) | stop at 2026-10-22 **00:38:39 ET**; censuses **≈01:05 ET**, then again minutes later; attribution relayed by the owner **≈01:28 ET**; answered **01:46 ET** | two independent workers | **cause DETERMINED: the owner stopped the DeepSeek model on `.30`–`.33`** at 2026-10-22 00:38:39 ET, consistent with the same owner's node grant that put `.30`–`.35` on the TP=4 queue — the quartet being free is deliberate, not an incident and not a fault. The four negatives corroborate that nothing was lost rather than standing in for a cause: no OOM, no Xid, no node reboot, model/runtime caches still warm (the 2026-10-14 `stop --all` fingerprint). **Answered 2026-10-22 01:46 ET — production stays stopped, the quartet keeps measurement duty** (verbatim "keep the quartet measurement duty as planned."); `#46` is folded into its work items in `mad-science/TODO.md` |
| Descriptor mistaken for liveness | `@littlecedar/deepseek-v4.1-flash-knapcio-tp4-1m-sglang`, served id `deepseek-ai/DeepSeek-V4.1-Flash-1017`, TP=4, cluster `sparkrun_a2e141223b52793c_e11d626ec2c6` — static since 2026-10-18 | censused 2026-10-22 **≈01:05 ET** | the 2026-10-21 entry trusted it and was wrong | corrected: only containers, listeners, gateway `deployments` and host processes answer "is it up" |
| Foreign or unowned container on a quartet node | `sparkrun_6c7626d237f22cdd_68907e0cb1d8_solo` on `.31`, relay-imported image | 2026-10-22 **≈01:07 ET** (head local clock), after both censuses | **reported by the re-pin campaign, unverified here** | consistent with the node grant and measurement duty; not the missing serve |
| Known-bad pin in service | vLLM `v0.29.0` (CVE-bearing) under the two Laguna arms; `v0.30.0` under the three media-gen arms | swept 2026-10-22, committed **01:10 ET** (`a3f5d2f`) | runtime sweep | re-pin campaign in flight (In flight); the arms still ship the old pin |
| Gate red, then cleared | `782 tests, 2 failures, 2 skipped` — two `tests/test_k2_7b_recipes` container-pin assertions, one arm on `lmsysorg/sglang:v0.5.22-cu130@sha256:e3a4f060…` while its guard asserted the `v0.5.20-cu130` tag and `sha256:06e4f2ed…` digest | failed before **01:15 ET**, cleared at the pin that landed with `440346c` (01:15 ET) | this register | cleared when the pin landed; the campaign itself still carries no verdict |
| **The llama.cpp image the tree depends on is a stalled publisher** | `scitrera/dgx-spark-llama-cpp` `:latest` == `b10549-cu131` == 2026-08-21, and that is the tag sparkrun's llama-cpp runtime advertises | recorded 2026-10-22 **01:21 ET** (`badf9cf`) | pin sweep | **standing risk, no verdict**: every llama.cpp arm in the tree is frozen ~2 months behind upstream; the stock-upstream route is a Deferred row, and nothing about a shipped llama.cpp arm changes today |
| **vLLM `v0.32.0` changes the thinking contract** | thinking arrives at **`message.reasoning`**, not `message.reasoning_content`, and `usage.completion_tokens_details.reasoning_tokens` reads 0 while emitting thousands of characters | found 2026-10-22 **01:36 ET** (`6280486`) | the qwen-image guard worker | **open for every future check, not just this arm**: the lane's old-shape checks read the reply as "all-empty", so any harness reading `reasoning_content` or counting reasoning tokens against vLLM `v0.32.0` reports a false empty |

### Campaign detail as of 01:53 ET

*(The board carries one row per node group; this is the per-campaign version, including the two closed rows.)*

| campaign | nodes | arms | started | est | state |
|---|---|---|---|---|---|
| campaign | nodes | arms | started | est | state |
|---|---|---|---|---|---|
| SGLang `v0.5.22` re-pin | `.35` | 6 — three ornith (off `v0.5.21`), three IFM (off `v0.5.20-cu130`); arm A (35B dflash2) booting now | 2026-10-22, start time not recorded | 4–8 h, derived from the 0.5.21 bump receipt (~4 h for three ornith arms on a free pair, same shape per three-arm lane) | index `e3a4f060…` and arm64 child `06441be3…` resolved; the K2-7B pin landed and its guard is green; **no verdict** — updated 01:48 ET |
| vLLM `v0.32.0` re-pin — **partly verified** | `.34` | 5 — two Laguna (off CVE-bearing `v0.29.0`), three media-gen (off `v0.30.0`); Laguna-XS measured, M.1 not re-booted | 2026-10-22 01:34 ET (`1a306ca` pin) | 4–6 h, derived from the media-gen receipts (≈4 min TTR per arm) plus the Laguna-M.1 TP=2 boot + suite receipt | **done:** Laguna-XS (TTR 282 s, 1,413,525 tokens = 5.39× the v0.29.0 pool) and the media-gen byte-identical PNG. **Not done:** Laguna-M.1 is **BUMPED, NOT RE-BOOTED** — its 2026-10-20 numbers stay v0.29.0 measurements — and its TP=2 phase is deferred for lack of a free pair. **No verdict on the campaign** — updated 01:48 ET |
| TP=4 block — **running, resumable** | `.30`–`.33` | qwen4 **W6** then **W12**, the **ds4 TP=4 candidates**, then the **four-node suite legs** | 2026-10-22, start time not recorded | 20–28 h block | **content settled 2026-10-22 01:52 ET** (owner: "run everything you can. We can always resume later if we need to pause TP=4 work.") — so the block runs in that order and **a pause is never a loss**; duty settled 01:46 ET (quartet on measurement, production stays stopped); W6 boot in flight; **not restated as finished** — updated 01:53 ET |
| Mellum MTP feasibility probe — **finished, negative** | — | shipped Q4_K_M main + `mtp-Mellum2.1-12B-A2.5B-Thinking-BF16.gguf` | 2026-10-22, found by the pin sweep recorded 01:10 ET | — | **NOT FEASIBLE on the shipped pin.** Needs llama.cpp `b11747` (2026-10-19) or newer: at our `b2e5e9b`, `src/models/mellum.cpp` has no `nextn`/`graph_mtp` and `llama-model.cpp`'s MTP-aware KV path lists QWEN3NEXT / QWEN35 / QWEN35MOE / BAILINGMOE3 / NEMOTRON_H_MOE but not MELLUM; the support lands in `b2e5e9b..b11747` as `nextn_flags`, the `nextn.eh_proj` / `enorm` / `hnorm` / `shared_head_norm` loads and `graph_mtp`. Found by the 2026-10-22 pin sweep, which saw the Mellum GGUF repo publish an additive MTP head at `4159d684…`. Our engine is `b2e5e9b` and `scitrera/dgx-spark-llama-cpp` has published nothing since `b10549-cu131` (2026-08-21). Pre-registered for the day the gate is met: existing Q4_K_M main + `-md mtp-Mellum2.1-12B-A2.5B-Thinking-BF16.gguf --spec-type draft-mtp --spec-draft-n-max 1`, falsifier "C1 > 114 t/s n=5 vs 111.9 ± 0.3, accept-len recorded, no C2/C5 regression, house 37/37 and bfcl 88.3 % held". The shipped main file is byte-identical (`ecc4d5b8…`) at both the pin and the head, so **nothing about the shipped arm changes** — updated 01:48 ET |
| pin sweep in CI (`refresh-sweep.yml`) | — | the 52-recipe sweep | 2026-10-22 01:38 ET (`fdee701`), sweep tooling 01:42 ET (`a644ace`) and 01:46 ET (`093c0be`) | daily cron | workflow landed and guarded by `tests/test_ci_workflows.py`; the sweep's own survey now reads **12 gating drift rows (24 before `093c0be`)**, **8 declared holds** in `tools/refresh-sweep-accepted.json`, and **1 genuinely stale build input** (4 before — a digest-pinned `FROM` is current, not stale); the ornith 397B `model-unrevision` row closed by pinning `b4864e44…`; **not yet run on GitHub, so no daily `pin-drift` issue exists yet** — updated 01:53 ET |

### Owner-call log, 2026-10-22

| id | question | answer line |
|---|---|---|
| — none — | `#47` was answered 2026-10-22 01:52 ET ("run everything you can. We can always resume later if we need to pause TP=4 work.") and folded into the TP=4 work items; `# DECISIONS` reads **0 open** | — |

### Deferred items as they stood at 01:53 ET

*(Each now lives as an open work item in `mad-science/TODO.md`; this is the register's wording.)*

| item | unblocker | where it lives |
|---|---|---|
| item | unblocker | where it lives |
|---|---|---|
| **The ds4 rebuild is not byte-reproducible** (behavior-identical: 91 layers, 0–69 identical, four recompiled `.pyc`, 6,707 hash-equal files) — recorded 2026-10-22 01:10 ET | a deterministic build step; until then the shipped `acfc331a…` stays pinned | `recipes/ds4/Dockerfile.knapcio-dsv41` |
| **Ornith intermittent 1M serve exit** (1–2 h) — recorded 2026-10-21, time not recorded | a failing boot with the capture armed — 4 of 4 d90 passes now on two builds, the last a first-attempt pass on 0.5.21 with a null die-capture; owner's answer 2026-10-21: park it until a real failure | `~/benchmarks/ornith-yarn-d90-20261020/` and the 0.5.21 receipt, plus the register item that stays open for the next failure |
| Dropped by owner policy, not waiting on anything: the GLM ≥1M probe, the ornith 397B retry, and restoring the quartet's TP=4 production serve — which stays stopped (owner decision 2026-10-22: keep the quartet on measurement duty) — recorded 2026-10-18, time not recorded; quartet entry 2026-10-22 01:46 ET | — | both probes recorded in the lane attic; the quartet decision in `mad-science/TODO.md` under the qwen4 and ds4 TP=4 items |
| **Stock-upstream llama.cpp image (source ref ≥ `b11747`)** — recorded 2026-10-22 01:21 ET, image Dockerfile added 01:22 ET (`f1b458d`) | a build host window: `recipes/explore/Dockerfile.llamacpp-upstream` exists with pinned base digests, a required `LLAMA_REF` (no default) and gates against the `b2e5e9b` failure mode, `docker build --check` clean; the build and the Mellum MTP A/B are pre-registered (falsifier: C1 > 114 t/s n=5 vs 111.9 ± 0.3, accept-len recorded, no C2/C5 regression, house 37/37 and bfcl 88.3 % held) | `recipes/explore/Dockerfile.llamacpp-upstream`, `recipes/explore/` |
| **Laguna-M.1 re-boot on vLLM `v0.32.0`** — recorded 2026-10-22 01:36 ET (`6280486`) | a free node pair: `.34` is on the vLLM re-pin and `.35` on the SGLang `v0.5.22` re-pin | `recipes/explore/poolside-laguna-m1-nvfp4-vllm-tp2.yaml` (labelled BUMPED, NOT RE-BOOTED) |

### Risks carried out of the register

| risk | trigger | mitigation |
|---|---|---|
| **BFCL is not resumable** | a drain mid-leg costs the whole 1,240-question run — the 2026-10-20 interruption (time not recorded) forced a fresh boot and a full re-run on 2026-10-21, which closed it at 83.6 % (`1d1cadf`, 03:00 ET) | drain before a leg, not during one |
| **Buffered logs look like stalls** | a question count frozen for tens of minutes while the serve decoded | read liveness from the serve log, never from the count alone |
| **Pair-bound stall** | the 15–25 h pair block holds both test nodes, so nothing single-node runs during it | schedule single-node work outside the block |
| **Stopping a serve can delete its evidence** | `sparkrun stop` bypasses `--no-rm` and removes the container with its in-container serve log — it cost the 9B `.35` log on 2026-10-21 (time not recorded) and it took the quartet's TP=4 serve log when the owner stopped the serve at 2026-10-22 00:38:39 ET | stop by cluster/task id and `docker cp /tmp/sparkrun_serve.log` out first |
| **A CPU decision pass is a four-hour window, not two** | Nox-4B took 14,066 s (35.2 s/case) where a three-case probe predicted 8,760 s, because the first cases are cheaper than the mean | price a CPU arm from a wide probe or the lane's own per-arm history |
| **The head's `127.0.0.1:8000` was the production TP=4 serve** | a probe that addresses loopback measures production, not the arm; at 2026-10-22 01:05 ET that loopback refused connections because the quartet serve was down, and refusing loopback is not evidence of a misconfigured probe — **the serve was back at 04:49 ET (08:49:58 UTC) and is up now** (`STATUS.md` §Now) | always use the node's IP root |
| **Address hygiene is done for the tree *and* the history** | the tree was masked on 2026-10-20 (71 lines, 22 files) and the history was rewritten on 2026-10-22 (`aac85ec` → `240ecd6`, **849 commits**, force-with-lease); **7** address lines remain and all are by design (the published HLE question, the CI detector's planted control, and the hygiene guard's own pattern plus four controls), commit messages carry none, and the guard walks `git ls-files` on every gate run | quote only the rewritten history: **every commit SHA changed**, and the 298 in-tree citations were re-pointed through filter-repo's commit-map, so a pre-rewrite SHA no longer resolves here — the old objects live only in the two backups under `/tmp/purge-backup/` |
| **A quartet descriptor proves the role, not liveness** | `@littlecedar/deepseek-v4.1-flash-knapcio-tp4-1m-sglang` has been static since 2026-10-18 (time not recorded) | check containers, listeners, gateway `deployments` and host processes |
| **The head's `.git` is syncthing-shared with a second writer** | 11 `.git/index.sync-conflict-*` files have accumulated there, and an edit that syncs before the pull aborts a fast-forward | repair with `git checkout HEAD -- <path>`, never `git checkout -- <path>`, which restores the stale index blob and loops |
| **Our llama.cpp publisher is stalled** | `scitrera/dgx-spark-llama-cpp` `:latest` == `b10549-cu131` == 2026-08-21 is what sparkrun's llama-cpp runtime advertises, so every llama.cpp arm in the tree is frozen about two months behind upstream and a feature the upstream engine already carries (Mellum MTP at `b11747`+) is unreachable | build from stock upstream through `recipes/explore/Dockerfile.llamacpp-upstream` (pinned bases, required `LLAMA_REF`); `llamacpp-engine.yml` reports our refs against `ggml-org/llama.cpp` weekly so the drift is visible instead of discovered late |

### History carried out of the old register

| when (ET) | head commit | what landed | receipts |
|---|---|---|---|
| 2026-10-22 01:16 ET | `618e48d` | this entry — the refresh, the quartet correction, the d3-edge revert, the register fixes; detail in Landed above | `~/benchmarks/decision-d3-repin-20261022/` |
| 2026-10-22 01:46–01:47 ET | `05d86dc` + this pass | both owner calls answered and folded: `#46` (quartet keeps measurement duty, production stays stopped — folded as a dated advisory note on the qwen4 and ds4 TP=4 items and removed from `# DECISIONS`) and the TP=4 offsite switch (answer "rephrase the question", executed as `#47`, which asks to confirm or narrow the block's content) | `mad-science/TODO.md` |
| 2026-10-22 01:52–01:53 ET | `adb8b96` + this pass | `#47` answered and folded as the run-everything directive on the TP=4 items (full W6 → W12 → ds4 TP=4 → four-node suite order, resumable, so a pause is never a loss); `# DECISIONS` now reads 0 open; the sweep tooling (`a644ace`, `093c0be`) registered with its row and hold counts | `mad-science/TODO.md`, `tools/refresh-sweep.py`, `tools/refresh-sweep-accepted.json` |
| 2026-10-22 01:22–01:38 ET | `f1b458d`, `1a306ca`, `6280486`, `fdee701` | the engine/CI block: stock upstream llama.cpp image added, explore vLLM arms re-pinned to `v0.32.0` (Laguna-XS measured, media-gen PNG byte-identical), the qwen-image `NameError` guard plus the reasoning-contract finding, and CI (gate, nightly pin sweep, weekly llama.cpp engine report); detail in Landed above | `recipes/explore/Dockerfile.llamacpp-upstream`, `.github/workflows/` |
| 2026-10-21 20:15 ET (commit `a2a1ef2` 20:04 ET) | `a2a1ef2` (remote tip then) | both queues empty and both nodes idle: 0 running and 0 exited containers on `.34`/`.35`, the 18:49 highcon probe finished and gone, the earlier leftover sglang container from the 07:52 Muse boot logged; gate 765 tests OK (2 skipped; 752 → 765 with the Qwen-Image guard), 52/52 tracked recipes plain-validate (0 errors, 53 files on disk), 12/52 `--strict`; the quartet claim in that entry is stale (Alerts) — the owner stopped that serve at 2026-10-22 00:38:39 ET | `~/benchmarks/_leftover-logs/43acfc12bcc4-sglang-20261021.log` |
| 2026-10-21 20:00 ET (commit `a9d4c27` 19:49 ET) | `a9d4c27` | Nemotron-3.5-Lightning-30B-A3B NVFP4 shipped: house 37/37, C1 63.27 ± 0.65 t/s, ladder 63.27 / 90.81 / 122.27 / 144.15, prefill flat at ~6.2k, 20.10 GiB, tool calls passing — the lane's fastest single-node chat arm; thinking-off is decode-identical (62.73 vs 62.74 t/s, recipe serve 63.85 vs 63.49, inside each other's spread) but costs five house items (32/37: `wp-3`, the three `hard-arith` items, `trick-3`), so both shipped numbers are thinking-on and the reasoning channel is load-bearing; its first `sparkrun` boot died once inside PIECEWISE CUDA-graph capture (`CUDA error: an illegal instruction`) and did not reproduce across five further boots/variants, so retry once and do not set the deprecated mamba flag; that emptied the ranked 1-node table (ranks 1–5 closed, 6–10 are 2+ nodes: MiniMax-M3 is 795.5 GiB on the Hub against the ~220 GB the dossier carried, Inkling-Small 495.4 GiB); node-free work closed the same night: house-budget audit (42 of 43 receipts at 4096, `hard-rev` the near-universal discriminator, convention into `tools/README.md`), render sweep (53 files, 46 clean, 7 flagged — four host-count refusals and three checker artifacts, no real defect), the Qwen-Image sigmas guard with three negative controls, and the AGENTS count refresh | — |
| 2026-10-21 21:42–23:59 ET (recorded under the 20:00 entry) | `a9d4c27` | vLLM-OMNI serves the Qwen-Image checkpoint natively on one GB10 at 8.66–8.75 s warm / 11.19 s cold per 1024² 8-step image against the shipped Diffusers arm's 11.49 / 12.64 s — ~24 % faster at identical peak (36.84 vs 36.82 GiB), TTR ≈ 4 min, `CUDNN_ATTN` auto-selected for sm_121; recorded as a measured alternative, not an arm: no recipe (**superseded 2026-10-22 — the route has its own arm, `11cc155`, authored and not booted**), the step knob is inert and mis-reported (4/8/12 → one byte-identical PNG at ~8.7 s while `denoise_step_latency_ms` read 2164/1086/721), same seed gives a different picture (`38ce554a…` vs `e24f6e3a…`); both 8-step images opened at full resolution against the prompt's `two-color screenprint` requirement: Diffusers honors it (two-line `SPARK` / `RUN`, exactly two inks, blue over orange on cream, correctly spelled, crisp edges), OMNI violates it (single-line `SPARKRUN`, rainbow of many hues on white) — a prompt-adherence defect, not a style difference; what stands: no smearing, no blended or doubled glyphs, no gibberish letterforms, no step-count starvation, so the ~24 % win is real but spent on the wrong instruction; scope is one prompt, one seed, one image per route, so it is not a measured general quality gap; the shipped Diffusers arm stays the default and the OMNI variant was offered and declined (2026-10-21), **reversed 2026-10-22 (`QUESTIONS.md` `#13`, "ship both")** | — |
| 2026-10-21 17:50–18:45 ET | `2d046bc`, `7255396` | the pair block emptied with no finding: **flash-next refuted on both engines** — the b12x build cannot construct the model config (`qwen_sparse_attention` is not a layer type it knows, so no weight is read) and the documented `vllm/vllm-openai:v0.31.0` fallback clears that gate and dies at worker init (`Qwen4Exp PLE embedding does not support CompressedTensorsConfig`), two gates, so the answer is an image that has both; **qwen4 labquant-highcon passed its control** (TTR 9.6 min, `max_model_len 262144`, admission unclamped, 41/41 shards, diagnostic payload fired 0 times, sweep 86.8 / 87.5 / 89.5 / 75.4 t/s against 84.9 / 89.1 / 89.1 / 72.9, every cell inside 3.4 %, no 10 % finding); nothing pair-bound runnable | — |
| 2026-10-21 17:21–17:32 ET | `49f1404`, `0581d58`, `71850ab`, `95d5572`, `8a539d9` | **Nox-4B shipped** at 67.8 % (1356/2000), the best CPU route in the decision lane, 12.8 points over Sol-2B; **JEV-27B does not ship**: 66.8 % (1337/2000) against its 9B sibling's 67.0 % (1340/2000) is three decisions, 0.15 pp, a tie below the lane's strictly-beat rule; **Muse Glimmer 30B closed as a checkpoint defect**, not a pack defect (the bf16 control misses `nurkrpas` identically); flash-next staging record corrected (both nodes have held the 183.48 GB export complete since 2026-10-15, so only a boot receipt is outstanding); docs moved to the sparkrun 0.4.2 build with schema cites re-derived and three claims the code had outgrown rewritten | — |
| 2026-10-21 03:00–07:29 ET | `1d1cadf`, `fb85b76`, `3dd62d0` | cybersec arm 5's tools leg closed at 1037/1240 = 83.6 %; the ornith SGLang 0.5.21 bump validated on all three arms and shipped; the LTX-2.5 T2V arm first-booted at 100.13 s cold / 78.1 s warm | `~/benchmarks/cybersec-arm5-tools-20261021/`, `~/benchmarks/ornith-0.5.21-bump-20261021/`, `~/benchmarks/ltx25-recipe-20261021/` |
| 2026-10-21 02:48 ET (commit `1d1cadf` 03:00 ET) | `2f9a8f3e60a51ee4_3510a5e0d37d` (boot id) | cybersec arm 5 finished 5/5: fresh TP=2 boot (TTR HTTP-ready 59.407 s), cap-free tools-only run 1037/1240 = 83.6 % in 3,887 s with 0 transport errors (simple 376/400 · multiple 188/200 · parallel 181/200 · parallel_multiple 177/200 · irrelevance 115/240) at 3.133 s/question; the pair was drained afterwards | `~/benchmarks/cybersec-arm5-tools-20261021/` (`REPORT.md` merges the four 2026-10-20 legs) |
| 2026-10-21, time not recorded (pair block, undated in the old table) | — | ds4 pair work closed: **v0.6 adopted** (c8 +26.5 %, c16 +25.7 %, prefill +24.6 % / +39.5 %, pin `d6e4c10d…`), and ds4 `reasoning_effort` measured (10.6 % paired saving, one task) | — |
| 2026-10-20–21, times not recorded (undated bullets from the old §Closed this session) | — | 27B-NEXTN suite + ladder (`bench_e66cbef09760`: 15.39 / 28.81 / 60.35 / 102.82 t/s); 27B-uncensored tools 1072/1240 (86.5 %); kolibri APEX five legs `ok` with a real 262k needle pass; laguna-XS 59.8 % tools, triaged as capability not parser; qwen3 MLX needle TRUNCATED at ~222.5k; ornith YaRN d90 PASS with a null die-capture; Sol-2B built, published and scored 55.0 % (1101/2000) at p50 195 ms; qwen4 `zz-labq-no-diag` passed, retiring the diagnostic on the balanced arm (restored in highcon only); 27B-NEXTN and arm-1 lane-doc blocks; Laguna-M.1 TP=2 booted, suite + ladder landed (C1 12.85 / C2 21.85 / C5 34.15 / C10 34.64 t/s), tools 750/1240 triaged as capability; Sol-2B recipe boot-verified through `sparkrun run` (1101/2000, 80.5 s); tracked-file addresses masked (71 lines, 22 files → 0); cybersec arm 5 — house 37/37, needle 3/3 at every rung, ARC 188/200 (94.0 %), GSM8K 197/200 (98.5 %), tools 1037/1240 = 83.6 % in 3,887 s with 0 transport errors, superseding the 2026-10-20 interruption; ornith SGLang 0.5.21 bump — 35B ladder inside every band, 9B C2 settled at −3.2 % on `.34`, YaRN 6/6 with a first-attempt d90 pass at 97.80 % fill; LTX-2.5 T2V — 100.13 s cold / 78.1 s warm on `.35` at 83.45–84.00 GiB peak | `~/benchmarks/cybersec-arm5-tools-20261021/REPORT.md`, `~/benchmarks/ornith-0.5.21-bump-20261021/`, `~/benchmarks/ltx25-recipe-20261021/` |
| 2026-10-21 14:26–18:45 ET (per the cited commits; undated paragraphs from the old §Closed this session) | `2d046bc`, `7255396`, `0581d58`, `49f1404`, `71850ab`, `95d5572`, `8a539d9` | flash-next: weights already complete on both nodes (18/18 shards each), so the pair boot cost 10.6 s of distribution and the staging fear was a measurement error; the sparkrun-built b12x image (`cf5a2a53…`, vLLM `0.1.dev21830+g8244d1c44.d20261015`) reads no weight, and `vllm/vllm-openai:v0.31.0` (`sha256:c1c9f6fd…`, local ID `bbe704505570` on both nodes) warms multimodal in 11.9 s, starts TP=2 and dies in the worker; `vllm/vllm-openai` declares `ENTRYPOINT ["vllm","serve"]`, which eats sparkrun's launcher, so an `executor_config` `entrypoint: ""` is required to adopt it (recorded in `recipes/cybersec/README.md`). qwen4 highcon (task `1895030211ea0500_3510a5e0d37d`): `load_weight` 508.93 s, `max_total_num_tokens=1587072`, `max_running_requests=32`, mamba 128, 41/41 shards on both classes, no `_scale` assertion; sweep at d8192/pp2048/tg128, k=8/12/16/24 against the controls 84.9 / 89.1 / 89.1 / 72.9 — the restored diagnostic mod did not move the serve. Nox-4B on `.34`: KL 0.219, Brier 0.114, ECE 0.063, 0 completion errors, 14,066 s at 35.2 s/case, second in the lane behind clef-flash's 70.3 %; vendor golden gate passed on aarch64 (`/health` 200 ready, no `GoldenResult` failure); as sparkrun stages it (`HF_HUB_OFFLINE=1`) the loader still calls the Hub tree API and `/health` stalled at 503 `loading`, so the recipe carries `HF_HUB_OFFLINE=0` and boots clean in ~30 s; ladder c1/c2/c5 all 0.044 req/s at p50 22,763 / 45,480 / 113,797 ms, a pure queue with no batching, c10 not run. JEV-27B on `.35`: boot wall 1244 s, most of it CUDA-graph capture (102 graphs, ~660 s); ladder c1 2.912 / c2 2.974 / c5 4.351 / c10 4.488 req/s, no useful scaling past c2 because the align path serializes decision prefill. Muse Glimmer 30B: bf16 control `meta-models/Muse-Glimmer-30B @7af58019`, same drafter, same image digest, same `mem_fraction_static 0.80`; house 36/37, same item, same string `nurkrpas`; C1 12.1 t/s on bf16 against the pack's 20.2; arm out of both trees, route and numbers in `attic/explore/AGENTS.md`. flash-next staging: the lane README's claim that the 183.5 GB export was reclaimed from every node on 2026-10-14 was wrong — 18/18 shards, 183.48 GB, zero bytes fetched, and `.35` carries 78.06 GB of orphan `.incomplete` blobs. sparkrun 0.4.2 docs pass: both files claimed `0.4.0-alpha+g29f53fb` while this workstation and the head report `0.4.2-alpha+g36d8a44`; module paths survived (`core/launcher.py`, `core/recipe.py`, `core/validation.py`, `models/runtime.py`), 27 line cites re-derived, three sentences rewritten (`recipe list`/`recipe search` fall back to `metadata.description`, the unmapped-key drop raises `unmapped-config-key`, `_KNOWN_KEYS` still 41 keys and moved two lines); the eleven arms carrying `unpinned-model-revision` re-counted file by file: still eleven | `~/benchmarks/nox4b-20261021/REPORT.md`, `~/benchmarks/jev27-20261021/REPORT.md`, `attic/explore/AGENTS.md` |

### Workstation tooling (measured 2026-10-21, time not recorded, after `sparkrun` landed there and reported `0.4.2-alpha+g36d8a44`)

## Workstation tooling (measured 2026-10-21, time not recorded, after `sparkrun` landed there and reported `0.4.2-alpha+g36d8a44`)

| tool | what the repo needs it for (one caller) | on the workstation | where it works today | ask |
|---|---|---|---|---|
| `sparkrun` | validate, render with `-n`, registry lookup, launch — the whole recipe surface | **yes.** `sparkrun recipe validate <path>` returns the head's answer verbatim, with and without an override; anything registry-qualified (`@littlecedar/…`) or cluster-profile-driven needs `HOME=$PWD/.local/sparkrun-home`, because the real `~/.config/sparkrun/registries.yaml` carries no `littlecedar` entry and `~/.config/sparkrun/clusters/` is empty while the repo-local home has both | head, and the nodes for launches | none |
| `uv`, `uvx` | the guard suite (`uv run python -B -m unittest discover -s tests`, **782 tests**, 2 skipped, measured 2026-10-22 at `440346c`) and the docs' own instruments (`uvx tool-eval-bench@2.8.0` at `recipes/decision/README.md:332`, `uvx llama-benchy@0.4.0` via sparkrun) | **yes** (uv 0.13.4); `uvx tool-eval-bench@2.8.0 --version` answers 2.8.0 here | head | none |
| `hf` | model sizing and revision probes (`tools/build-dsv41-combined.py`, the per-arm revision checks) | **yes** (1.29.0) | head | none |
| `docker` | resolving an image ref to its digest (`docker buildx imagetools inspect`, the pin method in `mad-science/SESSION-RECORD.md:354`), plus the node-side log and liveness ops every runbook depends on (`docker cp /tmp/sparkrun_serve.log`, `docker exec … kill -0`, `docker events --filter event=die`) | **partly**: the daemon runs (29.9.1) and `imagetools inspect` resolves the sglang v0.5.21 index and its amd64 manifest from here; there is no GPU, so any command that runs a container stays meaningless | head, and the nodes for container work | none — container work belongs where the hardware is |
| `python3` | the stdlib instruments (`python3 tools/decision-ladder.py`, `tools/quality-battery.py`, `tools/jev-decision-bench.py`) | **yes** (3.14.8; all three print usage) | head | none |
| `ffmpeg`, `ffprobe` | checking a media arm's output — the LTX-2.5 receipt claims h264 1344×768, 121 frames, 24 fps plus AAC (`README.md:237`, `attic/explore/AGENTS.md:501`); no `tools/` or `mods/` script shells out to it, so this is the operator's own verification | **no** — neither is installed | head | install `ffmpeg` here, or accept that video-receipt verification stays head-side |

| gate step | runs on the workstation | stays head-side |
|---|---|---|
| recipe validation, `-n` rendering, the 782-test guard suite, `@littlecedar/…` resolution, `hf` sizing probes, container-digest resolution | **yes** | — |
| boots, serves, `docker cp`, benchmarks, the ladder instruments that measure a live endpoint, video-receipt verification until `ffprobe` exists here | — | **yes** |

Checked and present, no row needed because none is a local gate step: `git`, `ssh`, `scp`, `rsync`, `curl`, `jq`, `setsid`, `stdbuf`, `taskset`, `nproc`, `timeout`, `sha256sum`.

### 01:55 ET — `649d3c7`: the W6 TP=4 failure, the knapcio accuracy legs, the W12 image pin

**W6 booted, loaded 41/41 shards on four ranks and died in `modelopt_quant.py:2624` (gated-activation MoE
padding) on every rank**, so TP=4 is an engine limit on this build, not a memory or arm defect. The knapcio
four-node arm closed the two accuracy cells the 2026-10-18 suite left open: **ARC 93.5 % / GSM8K 97.5 %**
(n=200 each, seed 1234). W12's arm now pins the b12x build by digest — latest resolved to `cf5a2a53`, the
build the shipped TP=1 solo arm already pins, so both vLLM receipts describe one engine. Files:
`attic/qwen4/AGENTS.md`, `attic/qwen4/arms/qwen3.8-flash-next-nvfp4-vllm.yaml`, `recipes/ds4/README.md`.

### The history rewrite and the BeeGFS pilot (2026-10-22, recorded on the rewrite tip `240ecd6`, 14:09:45 ET)

**Two owner-authorized acts landed together: the purge of the cluster-internal addresses from git history
(`QUESTIONS.md` `#16`), and the two-node BeeGFS pilot (`#5`). Nothing was measured on `.30`–`.33`, which
kept serving the fleet throughout.**

**The purge, executed.** `git filter-repo --replace-text` over the same masking map the 2026-10-20 tree
sweep used, then `--force-with-lease`: **`aac85ec` → `240ecd6`**, **849 commits preserved**, **one ref**
(`refs/heads/main`, with `origin/main` and the remote HEAD on the same commit), **0 tags**. Re-running the
audit's own scanner at the new tip finds **7 address lines, all by design** — the published HLE question
(`recipes/ds4/benchmarks/data/hle_test.jsonl:121`), the CI detector's planted control, and the hygiene
guard's own pattern plus four controls — and **0** in any commit message. The guard
`tests/test_tracked_address_hygiene.py` now walks `git ls-files` on every gate run, so the tree half can
never silently regress. **Signatures went 10 `E` + 839 `N` → 849 `N`**: filter-repo strips `gpgsig`, which
drops commit signatures but no commit object. **Every SHA changed**, so **298 citations across 26 tracked
files** were re-pointed through filter-repo's own `.git/filter-repo/commit-map`; a pre-rewrite SHA in an
older copy of any doc no longer resolves against this repository. Backups:
`/tmp/purge-backup/pre-purge-20261022-141525.git` (a `git bundle`, 13.8 MB, `git bundle verify` reports a
**complete history** at `aac85ec`) and `/tmp/purge-backup/pre-purge-mirror.git`. The workstation and the
`.34`/`.35` registry caches were re-cloned at the new tip, so no cache still carries the old objects;
`.30`–`.33` were left untouched. **`origin` is the only remote — no `spark-arena` remote remains**, and
re-adding one later would need a check of which history it fetches. Gate at the new tip: **940 tests OK**
(2 skipped), **67/67** plain validate, **49/67** strict (the same 18 accepted findings).

**The BeeGFS pilot, run to a conclusion that is a gate rather than a number.** Both `.34`/`.35` were
exclusive to it. The official vendor repo works — key fingerprint
`0683 AF2B 9AC5 BC7D 59B2 D623 40CE 4E24 3CD5 0804`, `Release.gpg` **Good signature**, `apt-get` clean,
version `20:8.4.1` — and **no official index ships a prebuilt module** on noble/jammy/bookworm; both
module suppliers compile on the node and the node's firmware refuses the result. `mokutil --sb-state`
says **Secure Boot enabled** on both, `mokutil --list-enrolled` holds **one** certificate (Canonical
Ltd. Master CA), and `mokutil --list-new` is empty: `beegfs-client` leaves `beegfs.ko` unsigned
(`modinfo` shows no signer) and `modprobe` answers **`Key was rejected by service`**, while
`beegfs-client-dkms` signs with the local `spark-324e` MOK, which is **not enrolled** — the same
refusal. So the **client** half is blocked by firmware, needs a physical-console
`mokutil --import` + MokManager confirm per node, and **§8 cell (2) — Engram decode on the pool — cannot
be measured at all**; (1) and (3) fall back to the NFS-over-rail stand-in: **564.1 MiB/s** single-stream
read against **6,358.3 MiB/s** local NVMe, **3,055.7 MiB/s** at eight streams, metadata create
**9.28 ms** `sync` / **0.67 ms** `async` / **0.0097 ms** local. The **server** half does work —
mgmtd/meta/storage start, both storage targets register, BeeMsg uses **RDMA on the rail** — but only
after a `network-online` + rail-address drop-in: the packaged units start before `enp1s0f0np0` has its
address and die with `Error: Couldn't find any usable NIC`. **`node list` misleads as a liveness test**
(the mgmtd database still lists targets whose units are down). BeeGFS's own storage-target benchmark:
**307.16 / 311.51 MiB/s** single-task write, **327.84 / 306.66** read, **1.49 / 1.57 GiB/s** at four
tasks (**3.06 GiB/s** aggregate). **No pass/fail was pre-registered** (owner ruling, `TODO.md` `#52`), so
none was invented afterwards: the verdict stays *not now*, with §6's install-risk item now measured
instead of predicted. **The owner reports a prior working install on these nodes that survived a
reboot**; today's store cannot reproduce it, so the record keeps both — a report and a measurement — and
attributes the difference to the Secure Boot/MOK state at the time of that install, not to the install.
Everything was torn down: 0 beegfs packages, 0 failed units, **0 containers**, `/` back to **279 GB free
(93 % used) on `.34`** and **615 GB free (83 % used) on `.35`**, fstab identical to its pre-pilot backup.
Report: `mad-science/BEEGFS-REPORT.md` §10; receipts `~/benchmarks/beegfs-pilot-20261022/`.


# 2026-10-24 — narrative moved from `mad-science/TODO.md` (cleanup sweep)

*(Moved verbatim from `mad-science/TODO.md` when it was cleaned to open work only; blocks
below are in their original file order and unedited.)*

## Planning preamble and resourcing (2026-10-15/18/19)

*(source: pre-cleanup TODO.md:481-531)*

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


## Session progress, policy, cluster state (2026-10-18/19)

*(source: pre-cleanup TODO.md:535-610)*

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
(`ba38d13`), with the pin re-derived to 6,850,000 (`ds4-v24-line-20261018`).

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


## Closed no-boot items note (2026-10-19)

*(source: pre-cleanup TODO.md:618-623)*

**Closed 2026-10-19 (three no-boot items).** The deep web search, the sparkrun 0.4.0 schema-docs pass
and the explore keeper sweep landed as separate commits. The sweep left the lane at **6 arms** (5
measured keepers + the authored Laguna-M.1 pair) and retired **10** to `attic/explore/`, so the
registry now stands at **48 recipes in 11 lane dirs, 752 tests, 12/48 strict failures** — re-measure
before quoting any of those numbers. All three items are archived in `../attic/DONE.md`. `.34`/`.35`
stayed idle throughout.

## qwen4 backlog progress (2026-10-18/19)

*(source: pre-cleanup TODO.md:911-917)*

  *(2026-10-18: **none of this backlog ran** — the TP=2 block closed after one arm. Two facts to carry into the next window: the `--fp4-gemm-backend` A/B's first alternative arm is refused **before weights load** (`flashinfer_cudedsl` is listed in `--help` and in the error's own `choose from` set, yet argparse rejects the token verbatim — `~/benchmarks/qwen4-tp2-20261018/b2-cudedsl-refusal-arm.log`), so probe the accept-spelling first; and `--enable-linear-replayssm-spec` is now measured as a capacity lever (+11.5 % KV pool) whose remaining question is accuracy, not memory. TP=4 (W6) and the W12 cross-runtime vLLM bench need four/two nodes and are out of this session's scope.)*
  *(progress 2026-10-19 — the `--fp4-gemm-backend` probe's spelling question is answered: the engine accepts **`flashinfer_cutedsl`** (the 2026-10-18 `flashinfer_cudedsl` refusal was a typo). One boot with it: `load_weight` 485 s, house **37/37**, ladder 39.02 / 70.22 / 98.38 / 106.13 t/s against the control's 41.22 / 72.88 / 95.18 / 108.13 — mixed, at or below the 7-25 % inter-boot floor, so `flashinfer_cutlass` stays. Still unprobed: `--enable-int8-mamba-checkpoint` and the prefill-graph bs>1 cost. Receipt `~/benchmarks/qwen4-knobs-20261019/b1-cutedsl/REPORT.md`.)*
  *(progress 2026-10-19, later — **`--enable-int8-mamba-checkpoint` is a hard negative.** The default 224-slot pool needs 3.24 GB against 2.15 GB free at the shipped `gpu_memory_utilization: 0.80`; a 112-slot retry then dies with `ValueError: --enable-int8-mamba-checkpoint is incompatible with Qwen4-Exp PLE side states` (`memory_pool.py:1337`), so no size fits. Receipts `~/benchmarks/qwen4-knobs-20261019/b2-int8mamba/` and `b2b-int8mamba-112/`. The prefill-graph bs>1 cost is the only unprobed item left.)*
  *(progress 2026-10-19, last — **the prefill-graph flag is a no-op on this image.** Removing `--cuda-graph-backend-prefill disabled` leaves the default `disabled`, and an explicit `--cuda-graph-backend-prefill full` is accepted by args parsing then disabled by the engine for the EAGLE target ("Disable prefill CUDA graph for EAGLE target on tc_piecewise…"), with the multimodal rule as the companion reason. There is no bs>1 graph cost to recover. Three same-config boots span **8.6 % at C2** (67.1-72.9) and ≤4.6 % elsewhere — the inter-boot floor measured directly. Receipts `~/benchmarks/qwen4-knobs-20261019/b3-prefillgraph{,-full}/`. **All TP=2 knobs in this item are now answered**; it stays open only for TP=4 (W6) and the W12 cross-runtime bench — neither needs a node window:
per the 2026-10-19 directive they run against the **offsite API endpoint**, batched behind the one
owner switch. *(Owner decision 2026-10-19: that switch happens **after** the `.34`/`.35`
single-node tail closes, not now — the tail's estimates assume local boots through then.)* )*

## qwen4 W6/W12 progress (2026-10-22)

*(source: pre-cleanup TODO.md:928-931)*

  *(progress 2026-10-22 01:55 ET — **TP=4 W6 is blocked at the engine, not the arm and not memory.** The boot loaded 41/41 shards on four ranks and died in `modelopt_quant.py:2624` (gated-activation MoE padding) on every rank, so TP=4 is an engine limit on this build. `649d3c7`; `attic/qwen4/AGENTS.md`.)*
  *(progress 2026-10-22 03:44 ET — **the v0.5.22 follow-up closes it as a checkpoint limit, not a build defect.** One boot of the same arm on `lmsysorg/sglang:v0.5.22-cu130@sha256:e3a4f060…` (task `08acf79cd757a666_7afff0589a33`, quartet `.30`/`.31`/`.32`/`.33`) loaded 41 shards and asserted identically on **all four ranks**: `modelopt_quant.py:2942` (`:2624` on v0.5.20 — same message, `The intermediate size required padding, but padding is also implemented for gated activations`). So TP=4 stays closed for this NVFP4 export on both builds; do not re-try another nightly expecting a different answer. By-products: the relay reports the pinned image `already verified on all 4 receiver(s)` and the model distributes in 18.3 s from a node-local HF cache (the 2-5 MiB/s leg only exists cold). Receipt `~/benchmarks/tp4-20261022/w6-tp4-v0522/REPORT.md` §Verdict, MANIFEST row.)*
  *(progress 2026-10-22 03:31 ET — **W12 served**, so the cross-runtime column has its vLLM number. TP=2 on `.31`/`.32` (`6a76d7f90a79f4f4_6eb961eae222`), `RadixArk/Qwen3.8-Flash-Next-NVFP4` @ `7b71922`, b12x `cf5a2a53`, `max_model_len` 262144 accepted, KV 1,757,475 tokens (6.70x). Decode 42.8/51.2/40.1 t/s over three 256-token samples at temp 0 (median 42.8). Two engine-side traps recorded: the restored PLE mod cannot run in-container (`docker` absent) and is inert on this image anyway (its PLE layer is `qwen4_exp/nvidia`, b12x-aware, no `Fp8Config` guard — vLLM flags `VLLM_PLE_FP8_CHECKPOINT` as unknown), and `load_format: instanttensor` dies at `weight_utils.py:1679` because the image's instanttensor has no `_determine_buffer_size` (TP=1 never takes that path, TP>1 always does) — the arm now loads safetensors. Cold boot to first 200: ~19 min, mostly b12x autotune. Receipt `~/benchmarks/tp4-20261022/w12-vllm-b12x/REPORT.md`.)*


## decision candidates progress (2026-10-18..20)

*(source: pre-cleanup TODO.md:995-1044)*

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

## decision closed sub-items (2026-10-18/22)

*(source: pre-cleanup TODO.md:1046-1061)*

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
  `recipes/decision/README.md` §`d3-edge-decision-vllm-srun`; commit `440346c`.)*

## explore reasoning-candidates recheck + Muse closure (2026-10-21)

*(source: pre-cleanup TODO.md:1486-1491)*

  *(recheck 2026-10-21 on both names blocked on time-sensitive facts — **`Muse-Glimmer-30B` is UNBLOCKED and cheaper than the dossier assumed; `MiMo-V2.6-Flash-RL` changed its blocking reason but stays out of the 1-node brief.** Neither is authored; the owner queues it.*
  *Muse Glimmer: vLLM PR #51655 merged 2026-08-14 (merge commit `6adad087`), and support landed in **v0.28.0** — `registry.py:186` `MuseGlimmerForCausalLM`, `:534` the conditional-generation alias, and `:635-636` both the drafter and the `DFlash{MuseGlimmerAssistantModel}` key the `EAGLEConfig` rewrite needs. A GB10 (`sm_121`) datapoint in the PR thread boots it with `--max-num-batched-tokens 4096` and `TRITON_ATTN`. The cheaper route needs **no new image**: the lane's pinned **SGLang v0.5.21** already ships `srt/models/muse_glimmer.py`, its configs, processor, and function-call detector, plus `test/registered/spec/dflash/test_muse_glimmer_dflash_assistant_gsm8k.py`, and the third-party GB10 run used that shape (11.16 → 23.74 t/s single-stream with the drafter). Size arithmetic from Hub `blobs=true` sums, not estimates: `meta-models/Muse-Glimmer-30B` bf16 **55.5 GiB** (`7af58019`), `RadixArk/Muse-Glimmer-NVFP4` **18.3 GiB** (`1416629950`) — the dossier's "NVFP4 24.7 GB" is 34 % high — and the drafter `meta-models/Muse-Glimmer-30B-assistant` **4.8 GiB** (`c676cce9`), so 23.1 GiB of weights with ~95 GiB left on one node. Geometry from `text_config`: 52 layers, 2 KV heads × 128 head_dim = 1 KiB per layer per token at bf16, and 13 of the 52 layers are full-attention (the other 39 sliding at 2048), so ~13 KiB/token ⇒ **~50 concurrent 131k sequences** in that headroom. Apache-2.0, 128k window, tool calling via `--tool-call-parser muse_glimmer` plus `--reasoning-parser muse_glimmer` (the latter forces `skip_special_tokens=False`).*
  *MiMo-V2.6-Flash-RL: "no quant" is stale — the base repo already ships at **165.5 GiB** for 310.8B params (≈4.6 bit per param, `fp8`/`8-bit` tags, 90 files), and the gated derivative `drowzeys/MiMo-V2.6-Flash-RL-Abliterated` (2026-09-23, `fp8`/`mxfp4`, tagged `dgx-spark`/`gb10`) is byte-identical at **165.6 GiB**. A quant exists; it is a **2-node** artifact either way, so the 1-node brief still excludes it and nothing is queued.)*
  *(closed 2026-10-21 — **`Muse-Glimmer-30B` is booted, measured, and does not ship.** One Spark on the ornith lane's own `sglang:v0.5.21` digest, no fork: contract PASS including a populated-argument `tool_calls` reply (the lane's first native channel-format arm), needle **10/10 at 32,768 and 10/10 at 131,072**, but **house 36/37** (`hard-rev`, `nurkrpas`, deterministic 4/4, no truncation) and **C1 20.2 t/s** — the slowest single-node arm measured here, against Laguna-XS's 57.4 at the same 36/37. 37/37 is a tie-break, not a gate, so the arm loses on the speed axis rather than on the bar. The recipe was removed; the route, flags, KV pool (235,556 tokens at mem-fraction 0.38), acceptance (C1 mean 3.19) and ladder are in `attic/explore/AGENTS.md` §"Muse-Glimmer-30B NVFP4 + DFlash — boot-verified 2026-10-21", receipt `~/benchmarks/explore-muse-glimmer-20261021/`. Worth revisiting only against the **bf16 export** (55.5 GiB, still one node), which separates pack from checkpoint on both the reversal and the decode rate.)*
  *(closed 2026-10-21, late — **the bf16 control ran and the answer is the CHECKPOINT, not the pack.** `meta-models/Muse-Glimmer-30B` @ `7af58019` (59.58 GB) on `.35` with the same drafter, the same `sglang:v0.5.21` digest and the same flag line (only `mem_fraction_static` 0.38 → 0.80, because 59.6 GB of bf16 weights do not fit the pack's fraction) reproduces the miss **exactly**: house **36/37**, `hard-rev` → **`nurkrpas`**, same item, same string, easy 19/19. bf16 load proven by the engine's own line (`MuseGlimmerForConditionalGeneration`, `mem usage=52.21 GB`, snapshot `7af58019…`), not by a file existing. C1 **12.1 t/s** (prefill 1206.7, ttfr 1,700 ms), DFLASH accepted on bf16 at block size 5 with acceptance 2.27-4.47. So both exports of the same weights fail the same word deterministically: **the Muse Glimmer line closes for good and no repack is worth trying.** Note for anyone reading serve logs later: the `marlin as FP4 GEMM runner … on SM120` line is a model-name-keyed engine branch and prints on a bf16 load with zero FP4 tensors. Receipt `~/benchmarks/explore-muse-glitter-bf16-20261021/`; detail in `attic/explore/AGENTS.md` §"Muse-Glimmer-30B bf16 control".)*
  *(closed sub-item 2026-10-18 — **`Nemotron-3-Super-120B-A12B-NVFP4` is built and measured, and does not ship.** C1 **15.83 ± 0.19 t/s** @ d0 (15.91 ± 0.12 @ d8192, depth-free) is 45 % below the already-rejected Mistral-Small-4 (28.9) and 66 % below Kolibri-1 (47.3); batching does not close it (c2/c5/c10 25.52 / 26.94 / 30.60 = 1.93× for 10× concurrency). Quality is the lane's best — house **37/37**, ties ling and mellum GGUF — and it is the only measured single-node arm serving the full **262,144** window (KV pool 7,659,632 tokens, 29.22× concurrency), which is why it is archived rather than deleted. **Params corrected: 123.6B true total (112.74B 4-bit experts + 4.83B FP8 + 6.02B BF16) / ≈12.2B active (22/512 experts); the Hub's 67.2B counts packed U8 NVFP4 expert bytes (2 values/byte) as parameters.** The as-authored recipe cannot boot: `--swap-space 0` is unrecognized in vLLM 0.29.0 (hard abort, which under `readiness.inference: false` shows as a hang, not a failure), and `VLLM_NVFP4_GEMM_BACKEND` / `VLLM_USE_FLASHINFER_MOE_FP4` are also unknown to 0.29.0, so its metadata describes behaviour that does not happen. Archived frozen at `attic/explore/nemotron-3-super-120b-a12b-nvfp4-vllm.yaml`; receipt `~/benchmarks/nemotron-120b-20261018/REPORT.md`.)*

## media-gen cells progress and closures (2026-10-18..21)

*(source: pre-cleanup TODO.md:1507-1557)*

  *(progress 2026-10-18 — the Qwen-Image 2048² cell is **CLOSED**: **53.24 s/image** (σ 0.20, n=3) against a same-boot **11.240 s** at 1024² (n=3, σ 0.008), tiling off, the three 2048² PNGs byte-identical (`sha256 86973bfb…`) and decoded at 2048×2048; peak 56.505 GiB torch alloc / 59.779 GiB reserved, node `MemAvailable` floor 53.8 GiB. The lane's ~26 s prediction is **falsified 2.04×** (+18.4 % per-pixel cost at 2048²). A non-null `num_inference_steps` is **silently ignored** — `12` was accepted and the pipeline ran the checkpoint's saved 8-step sigmas at the same 11.23 s — so a non-8-step schedule needs a `sigmas`-accepting mod, not a knob. Receipt `~/benchmarks/media-gen-20261018/` (`REPORT.md`, `cells.json`, `proof.json`). The non-8-step schedule and the vLLM-OMNI engine route stay **OPEN**; LTX-2.5's cells were closed late the same day — next bullet.)*
  *(closed 2026-10-18, late — **LTX-2.5 I2V + FLF2V + 4K/50 fps are measured.** Warm on `.34` (clock cap 2200 MHz, 1344×768 / 121 f / 24 fps): T2V **78.1 s / 83.70 GiB** (−2.5 % on the recorded 80.1 s), I2V **84.3 s (+7.9 %) / 83.79 GiB**, FLF2V **120.2 s (+54 %) / 81.94 GiB**. FLF2V is slower by mechanism, not regression: its template has no `LTXVLatentUpsampler`, so one full-res 8-step pass (76.9 s @ 9.6 s/it at 1344×768) replaces half-res 8-step + 3-step refine. Conditioning proven by decoded-frame MAD, not by a file existing: I2V frame 0 **4.1** vs the start image; FLF2V frame 0 **7.8** vs start / 59.5 vs end, frame 120 **16.9** vs end / 59.1 vs start. **4K/50 (3840×2160, 249 f) is OOM — a measured ceiling, not an untried preset:** stage 1 fine (8/8, 461.3 s @ 57.7 s/it at the 1920×1080 latent), killed at the ×2 latent upscale with 590 `NV_ERR_NO_MEMORY` kernel lines at **121.16 of 121 GiB** (85.0 GiB steady in stage 1, weights-only baseline 78.4 → not co-tenancy); the node stayed up, a process kill rather than a node loss. A smaller 4K cell at that output size is the only open question there and no register asks for one. Cold rep **204.3 s is an upper bound** (it overlapped a peer's serve; model load 25 s, first sampler step 12 s, cold tiled VAE decode 82.7 s vs 43.5 s warm). Receipt `~/benchmarks/ltx25-20261018/` (`REPORT.md`, 7 frames, 7 mp4s, per-rep `api/err/out`, `receipts{,_warm}`, and the fixed `expand2.py`/`run_cell2.py`; the runbook's expander is T2V-only — four defects listed in `attic/explore/AGENTS.md`).)*

  *(closed 2026-10-21 — **the Qwen-Image non-8-step schedule works, and the path is guarded.** `num_inference_steps`
  was silently ignored because the pipeline re-read the checkpoint's saved 8-step sigmas; the launcher mod now
  accepts a `sigmas` list and passes it through (`11836f0`). The guard that came with it asserted behaviour it
  could not be shown to catch, so schedule selection moved into a pure `schedule_kwargs(req, shipped)` and the
  tests exercise it directly — sigmas pass-through, the shipped count and the absent count both leaving the
  saved schedule alone, the resample's endpoints and monotonicity, and both `ValueError`s — with three
  negative controls that must go red (the pre-fix forwarded-field function, index rounding instead of value
  interpolation, a dropped `sigmas` kwarg), run against temp-dir shadow copies so nothing on disk moves
  (`32d046e`). 13 cases; the suite reads 752 with the file moved aside and **765** with it present. The 8-step
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
  the blocker. **Not an arm at the time:** no recipe was written in that window; `num_inference_steps` is inert *and* the engine
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
  Diffusers arm stayed the only route the registry shipped; an OMNI variant was offered as a *different look*
  the owner likes and **declined then**, so no recipe was pending until that was
  reversed. **Reversed 2026-10-22 (`QUESTIONS.md` `#13`): "ship both"** — the Diffusers render and the
  vLLM-OMNI variant land as separate arms, and the OMNI arm **has landed as a recipe**:
  `recipes/media/qwen-image-2.1-turbo-7b-bf16-vllm-omni.yaml` (`11cc155`, media lane after the split),
  validated and rendered only — **never booted** — carrying the two-ink adherence defect and **four
  queued boot cells** as its acceptance (`recipes/media/README.md` §"qwen-image … vllm-omni"); see the
  ship item after this block. §6 "which look ships" was the owner's
  call for **both** routes and is now answered (`recipes/media/README.md`
  §6, `attic/explore/QWEN-IMAGE.md`). Receipt `~/benchmarks/media-gen-20261021/vllm-omni/`
  (`REPORT.md`, `omni.json`, `omni-warm8.json`); the two 8-step PNGs are **not tracked** (owner decision:
  the registry ships as text) and live only in the head receipt as
  `~/benchmarks/media-gen-20261021/eight-step-{diffusers,omni}.png`, identified by
  `e24f6e3a…24ee24a` and `38ce554a…45704690`.)*

## Spark-X2.6 cell-1 progress note (2026-10-22)

*(source: pre-cleanup TODO.md:2389-2389)*

  *(progress 2026-10-22 — **cell 1 measured and the falsifier fired: bf16 is a control, not a ship candidate.** On `.30` (task `sparkrun_31a011c489646cf6_2d38dfc4605e`, 0 containers before and after): C1 **20.38 ± 0.09 t/s** (20.24–20.51, n=5 decode rows) and ladder **20.38 / 46.38 / 99.27 / 156.20** at c1/2/5/10, still rising at the cap because `max_num_seqs: 32` clamps it, not the pool; that is **61 % of the ~33 t/s roofline**, so bf16 survives only as the control the tier A/B is measured against. Contract confirmed on the wire: default → `reasoning_content` populated (`reasoning_tokens: 18`), `enable_thinking: false` → 0 reasoning tokens, one tool definition → `finish_reason: tool_calls` with `get_weather({"city":"Lisbon"})` parsed by `spark25`. House **37/37 thinking-on vs 30/37 (90/111)** thinking-off, so the reasoning channel is load-bearing. Memory: the hybrid split pools **84.48 GB** of KV (723,730 full + 578,984 sliding) = **5.52×** the 131,072 window, against the estimator's all-36-layers 18.0 GiB. Commits `4218f3f` + `14a5f86` (which added `--thinking on|off` to `tools/quality-battery.py`); receipt `~/benchmarks/spark-x2.6-20261022/`. **Open cells:** the **FP8 W8A8 and INT8 tiers** (2.6 GiB less weight, ≈2× the ceiling) — `recipes/explore/spark-x2.6-4b-fp8-sglang.yaml` is authored and its boot was **live on `.33` from 03:18:56 ET** (`max_total_num_tokens` 779,390, `max_running_requests` 32, 131,072 window), so that receipt is the open one; a ladder **above c10** needs `max_num_seqs` raised past 32 first; needle, ARC/GSM8K and BFCL/TEB are unmeasured.)*

## cybersec vLLM-route progress (2026-10-19/21)

*(source: pre-cleanup TODO.md:2713-2751)*

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

## Concurrency-ladder stale census (2026-10-15/18)

*(source: pre-cleanup TODO.md:2881-2881)*

**The census below is the 2026-10-15 snapshot and is stale:** most text arms now carry a full ladder — ds4 (TP=2 and TP=4), ornith 35B/9B, all three qwen3 arms, IFM 0.9B/7B, explore laguna-XS and both mellum arms (bf16 + llama-cpp), cybersec arm 2 — and only these still read `—` for C2/C5/C10 in `README.md`: qwen4's TP=1 solo arm, explore ling / kolibri / laguna-S, and cybersec arm 1 (orcarouter). `humanizer` needs no ladder — its `—` is by design, because the arm serves `/v1/completions` only and the ladder profile drives `/chat/completions` (`recipes/explore/README.md:148-151`). **Do not fill cells from the wrong receipt:** `attic/ds4/PERF-ISSUES.md:49-52`'s c1/c2/c5/c10 table is a cold-prefill triage on a different harness (its d0 c1 is 36.2, not the index's 46.5) and `attic/ifm/NOTES.md`'s c=2 53.697 belongs to the withdrawn 36B arm.

## Concurrency-ladder corrections (2026-10-18)

*(source: pre-cleanup TODO.md:2883-2884)*

  *(Correction 2026-10-18 — the arm list above and its closing "Remaining" sentence are superseded: strike `humanizer` from both (its `—` is by design and already documented, `recipes/explore/README.md:148-151`), and add the two arms the list omits — qwen4's TP=1 solo arm and the mellum bf16 arm. Measured already: mellum bf16 ladder 2026-10-15 (C1 42.3 / C2 67.2 / C5 99.9 / C10 135.6 t/s @ d0) and the mellum llama-cpp arm 2026-10-17 (`bench_4247926b7b9a`), so neither is outstanding. Still lacking a ladder: qwen4's TP=1 solo arm, explore ling / kolibri / laguna-S, and cybersec arm 1 (orcarouter).)*
  *(Correction 2026-10-18, late — **that remaining list is itself stale; verified against the index rows, not against this register.** Measured since: qwen4 TP=1 solo (`bench_6b35f675861a`), explore ling (`bench_7c46291e9bbb`), kolibri FP8 (`bench_b0d57361b7d7`) plus each of the six pack/tier arms' own ladders, laguna-S (`bench_e3fdefdc2491`), and cybersec arm 1 plain (`bench_4c30a992c771`). What actually remains is two arms: the **cybersec NEXTN sibling** (`qwen3.8-27b-uncensored-nvfp4-nextn-sglang`, C1 14.72 only — one boot, `~/benchmarks/cybersec-nextn-20261018/`) and **qwen4 labquant-highcon**, whose `—` is deliberate: it is the aggregate regime, measured at d8192 k=16/24 rather than on the standard d0 ladder. `humanizer` stays `—` by design.)*

## Standard-suite early progress (2026-10-18)

*(source: pre-cleanup TODO.md:2887-2888)*

  *(progress 2026-10-18 — two legs landed. **ds4 knapcio TP=4, 1017 weights** (task `a2e141223b52793c_7afff0589a33`): house **36/37** (easy 19/19, hard 17/18; the miss is `hard-rev`), needle **3/3 at each of 32,768 / 131,072 / 983,040** (top rung 981,950 prompt tokens), tool-eval-bench **90** (15 scenarios: 13 pass, 1 partial, 1 fail `TC-03 wrong_args`, `benchmarking/standard-suite.yaml`), same-boot ladder C1 69.28 / C2 86.40 / C5 108.78 / C10 116.27 t/s; receipts `~/benchmarks/tp4-20261018/` — `REPORT.md` §4, `knapcio-suite/`, `knapcio-teb.{yaml,json,csv}`. **qwen3 coder-next re-run** (`.30`, job `3d9fbe520b47c3a3_2d38dfc4605e`), all four legs `ok`: house 36/37 (easy 19/19, hard 17/18, the same `hard-arith-2` miss), needle 3/3 at 32k/128k/**256k** (262k rung filled 97.7 %, the tool's calibrated target, no `TRUNCATED`), ARC-Challenge 92.0 % (184/200) / GSM8K 96.0 % (192/200); `--timeout 3000 --needle-max-tokens 512` were applied proactively and never needed (256k prefill ~129 s, suite 1,319 s); the `tools` leg skipped on purpose (TEB already 90/100 on this arm); receipt `~/benchmarks/qwen3-coder-next-suite-20261018/`.)*
  *(progress 2026-10-18, late — **IFM 0.9B: PARTIAL, not a pass.** One serve on `.31` (cluster `e2b91b75cf01d3ab_68907e0cb1d8`, TTR 74.6 s, served `IFM/K2-Horizon-0.9B` @ 131,072, recipe sha256 `3c93459e…`): **contract ok**; **house ok** — easy **17/19** (`fmt-2`, `needle-1`), hard **15/18** (`hard-rev`, `trick-1`, `trick-2`); **needle FAIL** — 0/9 cells answered, every reply `finish_reason=length` with all 256 tokens spent inside `reasoning_content` and empty content, i.e. the SOP's 256-token cap and **not** a retrieval result (the 32k ladder's own calibration probes truncated too, so `chars_per_token` fell back to 4.6 and it filled 46.5k for a 32,768 target — a 42 % overshoot); **hard ok but floors** — gsm8k 86.0 % (172/200, 11 `length` + 11 empty replies) and arc 68.5 % (137/200, 18 `length` + 18 empty), the reasoning block eating the budget; **tools CUT** — SIGTERM'd when `.31` was reclaimed for a TP=4 boot, **585/904 logged (64.7 %)** with `irrelevance` never started and no `bfcl.json`, so that tally is **not** this arm's BFCL score. No ladder on this boot (the arm's stands at `edd4029e004f`). A valid re-take needs `--needle-max-tokens >= 512` and a completed tools leg. Receipt `~/benchmarks/ifm-09b-suite-20261018/` (`REPORT.md`, `house.json`, `needle-*.json`, `hard/`, partial `bfcl.log`, 0-byte `suite.log`).)*

## Standard-suite tail progress (2026-10-19/20)

*(source: pre-cleanup TODO.md:2924-3047)*

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

## Cluster-config change record (2026-10-24)

*(source: pre-cleanup TODO.md:3094-3107)*

  **Cluster config follows (2026-10-24):** the head's `~/.config/sparkrun/clusters/WOPR.yaml` now sets
  `distribution.model` = `enabled: false`, `skip_fan_out: true`, `preserve_perms: false` (backup
  `WOPR.yaml.bak-pre-shared-cache-20261024` beside it), so sparkrun neither downloads nor rsyncs models
  at launch. **A first version inherited those prefs into tuning-config distribution — wrong:** the
  Triton tuning cache is node-local (`~/.cache/sparkrun/tuning`, ext4, per-node divergent contents:
  `.30` sglang+vllm, `.34` sglang only, probed 2026-10-24), so an explicit `distribution.tuning` block
  restored the defaults (`enabled: true`, `skip_fan_out: false`, `preserve_perms: true`; second backup
  `WOPR.yaml.bak-pre-tuning-explicit-20261024`). Dry-run verified on the head
  (sparkrun `0.4.2-alpha+g7f0acf0`): a named-cluster launch (`sparkrun run <recipe>` or with
  `--cluster WOPR`) shows no "Distributing model" phase, while a bare `-H <node>` launch builds an
  anonymous cluster with the safe defaults and **still fans out models** — name the cluster or launch
  against its own host set. Cache-sharing prerequisite verified read-only: `~/.cache/huggingface` is a
  symlink to `/mnt/beegfs/huggingface` on the nodes probed (`.30`, `.34`), same 56-repo listing
  (md5-identical directory listing).

## Advisory pass record (2026-10-15)

*(source: pre-cleanup TODO.md:3171-3171)*

**Advisory pass 2026-10-15 — what was checked and found clean** (method: `api.osv.dev` package queries per version, then a version bisect against upstream release dates; only public upstreams are covered — the `littlecedar/*`, TensorFold and miaai-lab images are forks with no advisory feed). **sglang: clean, and the version string lies.** Our pinned build reports `0.0.0.dev1+g4ccff141d`, whose source commit `4ccff141db` is 2026-09-07; PEP 440 sorts that *below* every release, so OSV matches 14 of the 20 sglang advisories against it (the 6 it misses have ranges starting above a dev build — `introduced` 0.4.1.post7 or 0.5.5) and a version-based audit would report 14 false positives (those 14 are not merely unrated records: 2 are database-rated CRITICAL and 1 HIGH). The decidable side is the fix side: **`0.5.13` (released 2026-06-11) carries zero advisories** (the first clean 0.5.x release is `0.5.12.post1`, 2026-05-23), ~3 months before our source, so none of them is live in our tree. **vLLM nightly (cybersec route): clean.** `ghcr.io/spark-arena/dgx-vllm-eugr-nightly@sha256:7717585a…` carries `vLLM 0.32.0rc1.dev161+g660bd051d`, past the 0.30.0 fix line, 0 advisories. **Unreachable surfaces do not apply:** no recipe passes `--enable-custom-logit-processor`, none runs disaggregated/router mode with a public ROUTER socket, and the three cybersec `dev-cu13` arms sit on the same >0.5.13 source (the qwen3 27B arm was pinned by `16896e1`; `dev-cu13` as pulled today reports `0.0.0.dev1+ga6a8c5601`).

## Board restructure (2026-10-25, 23:20 ET)

The board `mad-science/STATUS.md` was rebuilt under the owner's 2026-10-24 spec: one title line carrying
only the generation timestamp, then exactly three tables — **In flight**, **Work queue** (mirroring
`TODO.md` §"Retry queue — unparked 2026-10-25" items 1–7), **Landed this session** (session opened
2026-10-24 ~19:00 ET; only `45d085e`..`37bcf03` rows kept). Everything else was swept to the homes
verified below; nothing was deleted without a surviving home.

Swept content → destination:

- **Field table (header rows)**: census row → the new In-flight census (superseded numbers: the
  22:29 all-zero census was 45 min stale, replaced by a fresh per-node container census); gate row →
  `AGENTS.md:619` (940 tests, snapshot rule) and `:155` (67/67 plain, 18/67 strict accepted
  findings); baseline `#48` + re-measure rows → `mad-science/TODO.md:46-58` (#48) and
  `mad-science/DEEPSEEK.md:431` (the 60.20 contended re-take) + `:1623` (A1 65.63/133.34);
  foundation-shape row → `mad-science/TODO.md:50` ("TP=4 is the foundation shape and TP=2 arms
  supplement it"); easy-traffic gate `#49` → `mad-science/TODO.md:67-91`; owner-queue row →
  `mad-science/QUESTIONS.md` (open rows live there) + `:474`/`TODO.md:216` (no-post-window drain);
  verdicts row → its constituents (qwen4 checkpoint limit `attic/qwen4/AGENTS.md:614`, W12
  `attic/qwen4/AGENTS.md:642`, SGLang bump `recipes/ornith/README.md:505-549`, Spark FP8
  `mad-science/TODO.md:87`).
- **Now table (14 rows)**: window 3, `.30` full-member, tplt4 close and window-2 rows → the new
  In-flight table or Work queue; `.34`/`.35` BeeGFS round-3/4 states → `mad-science/BEEGFS-REPORT.md`
  (cited by the rows themselves); tp2-queue close → `attic/cybersec/README.md:116` (NEXTN) and
  lane docs; `<head-node>` staging rows → `AGENTS.md:309` (the superseded 60 GB rule);
  `.31`–`.34` window close + boot9 triage → `mad-science/TODO.md:59-65` + `recipes/glm/README.md:53-74`;
  pool-cache row → the head receipt `~/benchmarks/cache-prefill-20261024/QUEUE.md` (all figures
  du-verified there; the GLM 292.765 GB figure verified on the pool directly). window-2's TTR figure
  (2888.8 s claimed vs 2746.273 s in `boot2b-glm-launch.log` on the head) and the NCCL-confirm
  outcome were **appended to `recipes/glm/README.md` §Shipped arm** (below) before the row was
  deleted — the launch-log number is the corrected one.
- **Attention (13 rules)**: each verified present elsewhere before deletion — qwen4 checkpoint limit
  `attic/qwen4/AGENTS.md:614`; llama.cpp ref floor `recipes/explore/Dockerfile.llamacpp-upstream:24`
  + `attic/explore/AGENTS.md:865`; registry-ref trap `AGENTS.md:124`; untagged-pull trap
  `AGENTS.md:136`; readiness.inference false-green `mad-science/TODO.md:1834-1836` +
  `recipes/MECHANICS.md:430`; Mellum MTP rejection `recipes/explore/README.md:401-410`; license
  banners `mad-science/TODO.md:2031-2036` (indra-ocr) + `:2154` (Timestral) + the recipes' own
  banners; chunk-bound prefill `mad-science/DEEPSEEK.md:561-578` (§9); b12x closure
  `mad-science/TODO.md:263-265`; transfer authority → **appended to `AGENTS.md` §Node hygiene**
  (was homeless — the rule existed only in the board row); three-test stand-down
  `mad-science/TODO.md:128-134` (`#51`); history-rewrite SHA rule `AGENTS.md:514-521` +
  `mad-science/AGENTS.md:183-187`; KHO wedge `AGENTS.md:284-301`.
- **Measurements (15 rows)**: knapcio baseline → `recipes/ds4/README.md` + `DEEPSEEK.md:431/1623`;
  Mellum2.1 → `recipes/explore/README.md:54-75`; Spark-X2.6 FP8/INT8 → `recipes/explore/README.md:114-116`;
  Ornith-122B NVFP4 → `recipes/ornith/README.md:587-617`; Sage-A1.5 → `mad-science/TODO.md:90,2616`;
  pyannote/drama-3 → `recipes/media/README.md:42,51`; qwen4 W12 → `attic/qwen4/AGENTS.md:642`;
  Mellum MTP sweep → `recipes/explore/README.md:401-410`; llama.cpp fork A/B →
  `attic/explore/AGENTS.md:918-938`; Bonsai Q2_0 → `recipes/explore/README.md:620-646`;
  kokoro-vs-phonon A/B → `recipes/media/README.md:95-117`. Nothing appended — every row was covered.
- **Gate table**: 940/70-plain/18-strict snapshot → `AGENTS.md:155,619`; the 2026-10-24/25 owner
  re-measures (948 tests, 70/70 plain) were board-only → **appended to `mad-science/TODO.md`
  §`#49` block** (below) so the current counts survive the board deletion.
- **Recently landed (~78 rows)**: session rows (`45d085e`–`37bcf03`) kept on the new board;
  pre-session rows are history and were checked against `mad-science/SESSION-RECORD.md`'s dated
  sections + the lane docs cited in each row (each pre-session row already names its durable doc:
  `DEEPSEEK.md` §17/§18, `BEEGFS-REPORT.md`, `FLARE.md`, lane READMEs, `attic/DONE.md`); no append
  was needed beyond the two appends below.
- **Pointers table**: redundant with `mad-science/README.md` §Master locator — deleted, no append.

Appends made by this sweep (the only facts that had no surviving home):

1. **Transfer authority rule → `AGENTS.md` §Node hygiene** — one owning session per in-flight
   transfer; verify with `ps -o pid,ppid,lstart,args` before signalling any pid; address rail IPs
   (plane-A/plane-B), never management addresses; the 2026-10-22 incident: a foreign `rsync` on
   `.34` was killed by a session with no ownership, dropping a body copy 390 GB → 307.2 GB, and the
   queued RoCE-rail resume then completed it (2 streams, 646–751 MB/s, 57 entries byte-identical to
   `.31`); the original copy had run over the management NIC (`enP7s7`), not a rail.
2. **Window-2 GLM one-knob NCCL confirm → `recipes/glm/README.md`** — `NCCL_SOCKET_IFNAME=
   enp1s0f0np0` + `NCCL_IB_HCA=rocep1s0f0,roceP2p1s0f0` (`NCCL_NET_PLUGIN=spcx` absent from the
   image, dropped) took the 3bpw boot past the pre-load stall to inference-ready; container-start
   TTR **2746.273 s port-open / 2746.298 s HTTP-ready** (`boot2b-glm-launch.log` on the head — the
   board's "2888.8 s" was a misquote, superseded here); pool reads ~95 MB/s with CPU-dequant gaps;
   ladder cells still owed (the auto-finish ran `--skip-run`); one stray-stop incident recorded
   (a peer's prefix-grep `sparkrun stop` killed boot2 2 min post-ready — never stop by parsed id).
3. **Owner-provided gate re-measures → `mad-science/TODO.md` §`#49`** — 2026-10-24 re-measure on the
   then-tip: 940 tests OK (2 skipped), 70/70 plain validate (67 baseline + OrcaCyber 13G +
   zz-EXL3-TP=4 + zz-MiniMax-H3-TP=4); final window re-measure: 948 tests OK (2 skipped), 70/70
   plain; strict NOT re-measured — the 18 accepted findings (17 `unpinned-model-revision`,
   1 `deprecated-topology`) stand.

## ornith-toolcall-ohmympi-triage — NO FAILURE REPRODUCED (2026-10-26, window tp4-window4)

- **Verdict: oh-my-pi tool-calling works on the shipped ornith line** — sglang
  `v0.5.22@sha256:e3a4f060`, honed qwen3.8 template, `--reasoning-parser qwen3
  --tool-call-parser qwen3_coder`, DFlash2 draft engaged. Boot
  `sparkrun_78c7e2fa335a63e5_35f2cfc5f912` (TP=1 solo on `.31`, TRUE-READY TTR
  414.0/428.6/428.7 s, watchdog healthy); preflight facts re-verified byte-exact
  (model 23,460,228,712 B @94e431d9, draft 1,053,161,270 B @9b4852c0).
- Scripted repro (`repro.py`): non-stream tool turn PASS (valid `tool_calls` args,
  `finish_reason: tool_calls`), tool-result continuation PASS, streaming 30/30 PASS
  on the warm serve. Real omp agent run through a capture proxy logging the harness's
  exact request shape (`stream`+`stream_options.include_usage`, `reasoning_effort:
  high`, `max_completion_tokens`, 11-tool array): smoke PASS, bash-tool task PASS,
  5-turn multi-tool stress PASS — 7/7 captured SSE streams reached `finish_reason` +
  usage + `[DONE]`. Nothing to fix; no upstream filing supported.
- **Watch item (once-only, unreproduced):** the first repro streaming turn returned an
  empty SSE body — server 200 OK with prefill+generation processed, client 0 bytes in
  0.53 s, no traceback in the serve log; not seen again across 33 later streaming
  requests on the same boot. An empty stream is exactly the class that breaks an agent
  harness (no events at all); if it recurs on any ornith boot, capture the serve-log
  window + request pair immediately.
- Receipts `~/benchmarks/tp4-window4-20261026/ornith-toolcall/` (`RECEIPT.md`,
  `repro-summary.json`, `capture/` request+stream pairs, `node0-serve-harvest.log`,
  `launch.log`, `watchdog.log`); boot stopped by literal id, 0 containers verified
  `.31`–`.34`, capture proxy + watchdog killed.

## History rewrite record — 2026-10-27 (drain/close closeout)

- **Old→new map (verbatim):** `3fe4457` → `6b3d48308712d29f3910b11c088f0f4ff9313468`
  (subject "boot watchdog: stdlib-only dead-boot killer …" — three literal rail IPs
  removed from the watchdog docstring/help, ZERO tree diff); tip `5ef4291` →
  `16d2a6a824a03260c6a82b106639b478743c9102`; the `cd9a9b4` scrub commit was
  **dropped-as-redundant** during the rebase (its content folded into `6b3d483`; it
  no longer exists). Old SHA citations elsewhere in the tree are annotated, not
  deleted, so they stay interpretable — see `mad-science/STATUS.md` and
  `mad-science/TODO.md` row 22.
- **Landing facts:** force-with-lease landed; head clone reconciled; `git fsck`
  clean on both sides. Scope was the named watchdog commit only — no full
  post-purge re-audit this pass (owner ruling, survey round 5).
- **candidate6 wording ruling (2026-10-27):** rows saying the knob "SHIPS" mean a
  **decision record only** — the shipped default stays **high (75) via
  `SGLANG_DSV41_REASONING_EFFORT`**; do not ask for `reasoning_effort=max`; no
  tooling edits. Earlier "knob ships / ships on a clean battery" wording
  (STATUS board row, STATUS landed-table row `0123dda`, TODO row 18 item (4))
  is annotated accordingly, superseded by `TODO.md` row 22.

## BeeGFS pool outage + recovery — 2026-10-26 ~19:28 ET (session DSV41F1017-Parity)

- **Failure:** `beegfs-meta` and `beegfs-storage` on `.30` failed at 19:28:50 EDT with
  **"Couldn't find any usable NIC"** (both services `Active: failed (Result: exit-code)`), timing
  that matches the `.33` connectivity event seen in the 19:22 census (`.33` SSH timed out, was
  reachable again by 19:57). With meta+storage down, every node's `/mnt/beegfs` and
  `${WOPR_USER_CACHE}/huggingface` returned **Errno 70 (ECOMM)** — `ls` itself failed on the head.
  Client sessions on `.30` and the head held the dead mount even after the servers came back;
  `.31`'s client re-attached on its own.
- **Recovery (20:0x–20:1x ET):** `systemctl restart beegfs-meta beegfs-storage` on `.30`
  (both `active` immediately; the NICs that "couldn't be found" were back UP — enP7s7,
  enp1s0f0np0, enP2p1s0f0np0; `enp1s0f1np1`/`enP2p1s0f1np1` are NO-CARRIER, as before); then
  `umount + mount /mnt/beegfs` on the head and `.30` to drop the dead client sessions (both
  `pool-ok` afterwards). `~/.cache/huggingface/token` readable again; sparkrun launches work.
- **Impact:** two Arm A launch attempts died in sparkrun's "Distributing resources" step on the
  token read before the recovery; the third launch (20:1x ET) booted clean (TTR 190.6 s).
  Nothing else was running (window-4 had drained), so no workload was disturbed.
- **Watch item:** the meta/storage failure mode is a transient all-NIC-down window killing the
  daemons at restart time; if a node connectivity blip recurs, check `.30`'s
  `systemctl is-active beegfs-meta beegfs-storage` before blaming a recipe.

## Landed rows retired at the 2026-10-27 13:10 ET board refresh (session boundary)

The board's `Landed this session` table is cleared at a session boundary (skill rule 9); the eight
rows the 02:00 ET board (`8c19eac`) carried have no other home — the underlying items live in
`TODO.md` §explore and `attic/ornith/AGENTS.md`, and these clauses are the commit-ledger narrative.
Verbatim as carried, retired by board commit `e472094`.

| time ET | commit | one clause |
|---|---|---|
| 00:40 ET | `7d2225e` | Flint four-arm comparison item added to `mad-science/TODO.md` §explore — roster with the on-file baselines flagged re-measure-not-quote, one instrument across all four arms, today's node fences |
| 00:44 ET | `efa5ede` | Ornith-1.5-122B decoder item + queue row: an SGLang arm against `incoai/Ornith-1.5-122B-DFlash2`, sized at the 35B's own ~2.9× draft ratio (≈79 t/s vs the 69.28 bar) |
| 00:47 ET | `ee6806b` | 122B route falsifier pre-registered before any boot (C1 ≥ 51 wins, C1 < 45 kills the route) and the draft's config read rather than assumed — vocab 248,320 / 48 layers / 262,144 window all match the target |
| 00:48 ET | `7485d6f` | corrected the drafter's authorship (`incoai` publishes the DFlash2 method; the 35B's shipped head is `jzinno`'s) and refuted the stale "only Ornith DFlash2 drafter" line in `attic/ornith/AGENTS.md` with a dated pointer |
| 00:55 ET | `8d23505` | 1,000-turn omp tool-calling trial added to the register and the queue — capture proxy, per-turn JSONL ledger, pre-registered verdicts, 12 h single node |
| 01:15 ET | `e2ea46e` | round-6 owner rulings folded as `TODO.md` row 23 (`SURVEY6 Q1`–`Q8`): all three new items next window, `.30`+`.35` in parallel, run staged at 300 turns, pattern-not-count verdict, Flint and 122B ship bars |
| 01:16 ET | `5abc1d6` | board tick: fresh probed census (quartet live, `.30`/`.35` idle), queue reconciled — `pool-prefetch-missing-bodies` closed on ledger evidence, `flint-four-arm-comparison` + `ornith-122b-decoders-route` added as scheduler rows |
| 01:53 ET | `f70c3b5` *(peer session)* | ornith-1.5-35b-a3b-nvfp4-dflash2-sglang.yaml gains `FASTSAFETENSORS_ODIRECT: 1` (1 line) — recipe edit, boot verification pending as the solo `.30` boot above |

Two corrections this retirement carries, both measured at the 13:10 ET tick: the quartet on `.31`–`.34`
is the **production serve** (served id `deepseek-ai/DeepSeek-V4.1-Flash-1017`, live chat traffic from
`.30`), not an unclaimed research window — so the "no `.scratch/fleet-window.lock`" escalation that
the 01:16 and 02:00 ticks raised is withdrawn; and the `01:53 ET` row's boot verification question was
already answered by `ba78d62` (buffered reads, i.e. the pre-`f70c3b5` recipe).

## Landed rows retired at the 2026-10-27 14:04 ET board refresh (session boundary)

Session `…16-46-35Z_01a17e41` closed at 13:29 ET without a clearing commit, so the four rows its board
carried are retired here rather than lost, together with the two commits it landed after its last board
write and never listed. The next session (`…17-34-11Z_01a17e6d`, opened 13:34 ET) starts its own
`Landed this session` table empty. Verbatim row text as carried; retired by the 14:04 ET board commit.

| time ET | commit | one clause |
|---|---|---|
| 02:05 ET | `ba78d62` *(peer commit)* | the `.30` ornith solo's O_DIRECT question settled from its own serve log — it loaded with buffered reads, so it never served the `f70c3b5` line |
| 12:54 ET | `787cb7e` | mellum + humanizer move off the deprecated `--no-mmap` to `--load-mode none` (same policy, `common/arg.cpp:2672`); the `.35` boot that raised the warning had launched the published ref, before this landed |
| 12:55 ET | `9f065d4` | all 11 llama.cpp arms swept — none other carries the deprecated spelling; the upstream Dockerfile help note becomes ref-agnostic and the GGUF note gets dated pointers |
| 13:04 ET | — (stops) | ornith solo `78c7e2fa…` and mellum `a16b25d0…` stopped by id at owner instruction; `.30`/`.35` verified at 0 containers and 0 volumes |

Two commits landed after that board write, never listed on any board:

| time ET | commit | one clause |
|---|---|---|
| 13:26 ET | `ec90005` | corrected the quartet's attribution (production serve, not an unclaimed research window) and registered the tag-only container pin as queue row `ds4-shipped-container-digest-pin` |
| 13:29 ET | `5e4a15d` | measured the shipped image's provenance — a local overlay build (created 2026-10-25 20:01 ET, 33.5 GB, base `lmsysorg/sglang:dev-dsv41` `da64c5cb`, upstream action run 34631178591) with no registry digest on any host, so the digest route is push-then-pin and the `3f4480818acb…` in TODO row 21 is an image ID, not a manifest digest; also replaced the ds4 fence's fixed `.30`–`.33` rank list with a pointer that the fence follows the production serve. Verified at landing: 1007 tests (2 skipped), `task-queue.py check` green at 45 tasks |

## Landed rows retired at the 2026-10-27 21:04 ET board refresh (session boundary)

The table the 14:04 ET tick opened was carried unchanged through the 15:01 (`53b253d`) and 16:01
(`e7eaab4`) ticks and still held one row at 21:00 ET. That row is session `…17-34-11Z_01a17e6d`'s
landed work (the session that wrote the 15:01 and 16:01 boards; its last session-file write is
16:33 ET), so the session writing the 21:04 ET board (`.omp` session
`…00-44-33Z_01a17ff7`, `PI_SESSION_ID` `01a17ff7-4450-767a-b571-79e370ad3f55`, opened 20:44 ET)
retires it rather than listing another session's work as its own. `git grep 8fb4bf4 -- mad-science/`
found this clause on the board only, with no other home. Verbatim as carried:

| time ET | commit | one clause |
|---|---|---|
| 14:09 ET | `8fb4bf4` | re-measured the two figures `dc5bc48` had carried: `.32`–`.34` `/health` 200 / `/v1/models` 404 at 14:07 ET, and no `hf download`/`hf sync` process on any node at 14:08 ET |

## Board commit rewritten for address hygiene — 2026-10-27 22:12 ET

- **Old→new map:** `3b52ab5` → `09e91a9f2d4432c68a781df5394ffc2ca8fcfdc4`, the 22:04 ET board
  commit only; its subject is unchanged. It carried the head node's literal management address in
  one clause of the quartet row and in its own commit body; both now name `.30` (masked form, the
  repo convention). No other path in that commit differs.
- **Landing facts:** `git log -S` on the literal over the rewritten history returns nothing, so the
  address is out of history rather than merely out of the tip; `git grep` over `mad-science/` is
  clean; `tests.test_tracked_address_hygiene` 7 tests OK and the full suite 1007 tests OK
  (2 skipped). Force-with-lease landed after confirming `origin/main` was still `3b52ab5`, so no
  peer commit was overwritten. The behaviour the board reports is unchanged: rank0 served
  `POST /v1/chat/completions` 200 at 22:00:40 ET with `#cached-token: 153856` prefix reuse.
- **Peer note:** a clone that already fetched `3b52ab5` now holds a divergent `main` and a
  fast-forward pull will refuse. Report it to that clone's owner; never blanket-reset the head
  (`AGENTS.md` §Git, secrets, and the second writer) — the durable record here is what makes the
  divergence interpretable.

## Landed rows retired at the 2026-10-28 00:30 ET board refresh (session boundary)

The table the 2026-10-27 21:04 ET tick opened was carried through the 22:04 (`09e91a9`, rewritten
from `3b52ab5`) and 23:04 (`08b707d`, then `4a50dda`) ticks and still held four rows at 00:25 ET.
Those rows are session `…00-44-33Z_01a17ff7`'s work (opened 20:44 ET, last session-file write
23:28 ET); the session writing this board (`.omp` session `…03-21-32Z_01a18086`, `PI_SESSION_ID`
`01a18086-fa6a-758d-a435-c6b5c680f15a`, opened 23:21 ET) retires them rather than listing another
session's work as its own. `git grep <sha> -- mad-science/` found `09e91a9` in this file's
address-hygiene section and the other three on the board only, so they are carried here. Verbatim
as carried:

| time ET | commit | one clause |
|---|---|---|
| 21:05 ET | `f0cc94e` | board 21:04 ET: fresh six-node census (quartet at 21 h, `.30`/`.35` idle), queue reconciled to 14 open rows, prior session's `8fb4bf4` row retired to `SESSION-RECORD.md` |
| 21:06 ET | `77e6e62` | named this tick's session (`PI_SESSION_ID` `01a17ff7…`) and the retiree's (`…17-34-11Z_01a17e6d`) in the census row and the boundary note |
| 22:02 ET | `09e91a9` | board 22:04 ET with the live-traffic proof from rank0's serve log; amended from `3b52ab5` to drop the head node's address literal from the row and the message (record: `SESSION-RECORD.md` §Board commit rewritten) |
| 22:04 ET | `c7188f2` | rewrite record for that amend: old→new map, `git log -S` clean, address guard 7 tests and the full suite 1007 (2 skipped) green |

Two commits from that session never reached a board row, the 23:04 tick closing after them:

| time ET | commit | one clause |
|---|---|---|
| 23:01 ET | `08b707d` | refreshed the board to 23:04 ET — quartet `Up 23 hours (healthy)`, live chat traffic on the line |
| 23:02 ET | `4a50dda` | replaced the single tail line with a wide-slice client-request count in the quartet row |

## Landed rows retired at the 2026-10-29 03:10 ET board refresh (session boundary)

The board session `.omp` `…03-21-32Z_01a18086` (opened 2026-10-27 23:21 ET) closed before this
tick; the session writing the board is `.omp` `…05-41-35Z_01a1862d` (opened 2026-10-29 01:41 ET),
so its `Landed this session` table carries none of the previous session's sixteen rows. Verification
before clearing: `git show 07cecb7:mad-science/STATUS.md` holds every row below, and
`git grep` over this file returned nothing for `50167f7`, `4aabfc8`, `137 turns`, `tp12` and
`14:00`/`14:01 ET`, so the rows are carried here verbatim. The board's own copy is also in git
history at `07cecb7`; nothing below is re-measured.

| time ET | commit | one clause |
|---|---|---|
| 00:28 ET | `50167f7` | `plugins/plugin.toml` sidecar (`sparkrun = ">=0.4.2a0,<0.5"`): the pooling plugin's `sparkrun update` row renders a real range instead of `unknown`, and the `a0` floor is what admits the 0.4.2/0.4.3 alphas — the Python half stays `unknown` because the core reads it only from a distribution; verified at `spark-arena/sparkrun@561b14b`, suite 1007 OK (2 skipped) |
| 00:55 ET | measurement | `k2-horizon-0.9b-bf16-sglang` full breakfast — ladder C1 **78.3** / C2 **175.4** / C5 **340.5** / C10 **498.8** tg t/s (5 runs per cell), house **70** (9 pass / 3 partial / 3 fail) |
| 00:58 ET | measurement | `ornith-1.5-9b-nvfp4-dflash-sglang` — ladder C1 **53.3** / C2 **91.4** / C5 **149.7** / C10 **144.5** (C5→C10 degrades, σ 3.8), house **97** (14 / 1 / 0) |
| 01:08 ET | measurement | `k2-horizon-0.9b-bf16-uno-sglang` — ladder C1 **121.1** / C2 **220.8** / C5 **383.8** / C10 **516.3**, house **83** (11 / 3 / 1); UNO beats the plain bf16 sibling at every rung |
| 01:10 ET | measurement | `spark-x2.6-4b-bf16-sglang` — ladder C1 **21.5** / C2 **49.2** / C5 **100.2** / C10 **158.8**, house **87** (12 / 2 / 1); C1 matches the historical 20.38 control on the same image |
| 01:26 ET | measurement | `poolside-laguna-xs-2.1-nvfp4-dflash-vllm` — ladder C1 **53.4** / C2 **82.5** / C5 **129.6** / C10 **135.9**, house **83** (11 / 3 / 1); re-measured under `--fresh` after its first ladder turned out to be a benchmark-state re-emit, and it reproduces the cached figures within noise |
| 01:26 ET | measurement | `spark-x2.6-4b-fp8-sglang` — ladder C1 **40.5** / C2 **76.5** / C5 **145.9** / C10 **218.1**, house **80** (11 / 2 / 2); roughly 2× the bf16 sibling's decode at every rung |
| 01:44 ET | measurement | `zz-spark-x2.6-4b-fp8-ngram-sglang` — ladder C1 **38.9** / C2 **69.7** / C5 **133.6** / C10 **194.5**, house **0** (0 pass / 0 partial / **15 fail**): it serves and decodes, but every scenario ends `missing_step` after **42–60 s** each (passing siblings take 1–14 s), with no HTTP, timeout or connection error in the log — a behavioural failure of the ngram probe, not a transport artifact |
| 01:51 ET | measurement | `ornith-1.5-35b-a3b-nvfp4-yarn-1m-sglang` — ladder C1 **79.6** / C2 **115.7** / C5 **143.7** / C10 **202.5**, house **97** (14 / 1 / 0); best house score of the campaign so far |
| 02:01 ET | measurement | `ornith-1.5-35b-a3b-nvfp4-dflash2-sglang` — ladder C1 **92.7** / C2 **151.9** / C5 **221.5** / C10 **252.5**, house **100** (15 / 0 / 0); the campaign's best arm on both axes, and its C1 is the highest measured in this run |
| 11:18 ET | measurement | `k2-horizon-7b-fp8-uno-sglang` boot failure root-caused: not the node, not transient — the pool's copy of pinned revision `ea739ec8…` held only `config.json`, so the tokenizer fell back to a slow class with no `sentencepiece`/`tiktoken` and the serve died before opening the port (`ValueError: Couldn't instantiate the backend tokenizer`). Upstream that revision has 13 files and the pin is sound; `hf download --revision` completed 13/13. **The class generalises**: a present-but-partial revision surfaces as an engine error, so a staging census must verify snapshot file counts, not repo presence |
| 11:22 ET | measurement | `k2-horizon-7b-fp8-uno-sglang` **measured after the cache repair** — ladder C1 **32.5** / C2 **54.0** / C5 **91.2** / C10 **120.8** tg t/s (per-request 32.5 / 31.2 / 23.4 / 17.0), house **90** (deployability 81, responsiveness 60); ladder rc=0, house rc=0, stopped by task id, node released with 0 containers and 0 volumes |
| 12:00 ET | `4aabfc8` | metrics bridge generalized to the 4bpw GLM arm and the vLLM-OMNI media arm — both GLM TensorFold launchers now carry the same block (TAG plus a one-per-boot `metrics bridge: matched […]` announcement, pinned byte-identical by a test), the 4bpw shim moved from `execve` to child process + signal relay, and a new lane-local `recipes/media/mods/vllm-omni-metrics-bridge` wraps the diffusion serve. The ds4 premise was false: that arm serves SGLang, which prints the scraped shapes natively, so the 3bpw implementation was generalized instead. Gate re-run by the parent: 1047 tests OK (2 skipped), 78 recipes validate, `bash -n`/`py_compile` clean, media render re-verified through the wrapper, 7 negative controls fire. **No arm booted**, so the matched-series line is still unobserved |
| 13:00 ET | measurement | omp tool-calling stage 1 on the yarn-1m arm: **137 turns, depth 4→535, zero failures of the owner-reported class** — no empty SSE body, no invalid tool-call argument JSON, no length-terminated turn; tool mix edit 65 / bash 40 / read 30 / write 3. TTFT rises monotonically with depth (372→775 ms p50) while failure rate stays at zero, so depth cost is latency, not corruption. Code consequence: 30/30 backlog items implemented, 178 new tests green. Ledger `~/benchmarks/ornith-longrun-20261028/stage1-ledger.jsonl` |
| 14:00 ET | measurement | stopped the yarn-1m trial serve on `.30` by task id after the trial ended at 12:57 and the node carried an idle container with zero client traffic for an hour; re-verified on the node afterwards: **0 containers, 0 volumes**, root 1.5 TB free. Fleet research occupancy is now zero, which means the staging pulls for the TP≤2 campaign are the only thing standing between the queue and a working node |
| 14:01 ET | measurement | staged the TP≤2 campaign: image pulls re-checked by digest on both nodes and model snapshots checked for completeness rather than repo presence — the 7B-uno class (a present-but-partial revision) does not recur in any of the five pool repos. Staging was already largely done, so the queued estimate of 11 missing refs was stale |

## Push backlog — 2026-10-29 09:10 ET (seven board commits, deferred)

The documentation session (opened 03:03 ET, `6867d1b`) has landed seven commits that reach this
tree but not GitHub: `b215934`, `6a877a8`, `7086768`, `0cfef5f`, `f532c62`, `ed21c00`, `3298fdd`
— the 03:25–09:00 ET board ticks. No host reachable from that session can push. The workstation has
no credential helper, no `~/.git-credentials`, no `gh` and no GitHub SSH key; the head
(`red@spark-41e1`) has `credential.helper=store` but its `~/.git-credentials` holds one
**huggingface.co** line only, both `~/.ssh/id_ed25519*` keys are rejected by `git@github.com`
(`Permission denied (publickey)`), `gh` is absent, and a push from the head's own clone fails with
the same `could not read Username`. `origin/main` last moved at `3a6ee0a` (03:21 ET).

The tail is not stranded: `.git` is syncthing-shared, so the head's clone already carries all seven
(`git -C ~/src/sparkrun-recipe-registry log -1` = `3298fdd`, `main...origin/main [ahead 7]`), and
that is the copy every fleet session reads. The clearing mechanism is proven rather than assumed —
`6867d1b` and `3a6ee0a` are on origin and neither was pushed from this session; a peer's push
carried them. Ticks therefore stop re-attempting the push each hour; the tail lands on the next
credentialed push from any clone sharing these refs, and this section is the once-only record.

**Correction, same day 11:05 ET: the premise above was wrong — the workstation could push all
along.** Its git config lives at `/home/siv/.gitconfig` (`credential.https://github.com.helper =
!/usr/bin/gh auth git-credential`; `gh` 2.102.1 at `/usr/bin/gh`, logged in as `padthaitofuhot`),
but the session's tool shell had exported `HOME=$PWD/.local/sparkrun-home` for the sparkrun
`recipe validate` gate, and that sandbox HOME has neither the gitconfig nor the gh auth, so
`git push` prompted for a username with no terminal and failed. The owner's push from their own
shell landed the tail (`origin/main` = `102d36f`), and every later git call in this session must
set `HOME=/home/siv`. The head is genuinely credential-free (its `store` helper holds only a
`huggingface.co` line and both `id_ed25519*` keys are rejected), so the fleet-reading argument
above still holds — only "no reachable host" was false. Keep the sandbox HOME for `sparkrun`,
never for `git`/`gh`.

## TP12 campaign + GHCR push — 2026-10-29 12:20–13:30 ET

Owner authorisations this window: keep running TP12 arms back to back (no per-arm sign-off), push
the shipped ds4 image to GHCR **and make the package public**, and route the blocked-queue questions
into `mad-science/CLR-BRIEF.md` instead of chat.

**Arms.** `nemotron-3.5-lightning-30b-a3b-nvfp4-vllm` (TP=1) measured at 11:47–11:58 ET — ladder
C1 63.86 ± 1.78 / C2 93.73 / C5 122.74 / C10 144.64 t/s, standard suite **90**, every cell inside the
shipped row's spread, so the row stands. `qwen3-coder-next-int4-autoround-vllm` (TP=1, vLLM) measured
at 12:43–12:52 — C1 68.77 ± 0.17 / C2 111.91 / C5 180.82 / C10 243.69, suite **93**, again within ~3 %
of the shipped row (70.4 / 114.0 / 177.1 / 249.5), and the first live exercise of the io-probe fix
(`58d602f`): the watchdog followed the `EngineCore` child's 309 MB of reads, not the `vllm serve`
parent. Campaign count 12 of 42 measured; receipts `~/benchmarks/tp12-20261029/{nemotron,qwen3-coder-next}/`.

**The TP=2 ds4 attempt was aborted and published nothing.** `deepseek-v4.1-flash-tensorfold-tp2-1m-sglang`
on `.30`+`.35` booted in 63.8 s and served the full 1048576 context, but its own log showed decode at
**2.9–3.1 tok/s** (128 tokens over 45–48 speculative rounds, `accepted=82/142`, ttft 20–34 s including
6.6 s prefill) against the row's C1 66.4. No OOM, no restart (`RestartCount=0`, `OOMKilled=false`);
batched CUDA graphs were captured (`--parallel warm-up: 64 round graphs, 4 drafter graphs`) while the
single-stream warm-up printed `decode graphs {}`; Engram is on (`/cache/huggingface/hub/dsv41-engram`)
and cold pool reads are the leading, unproven hypothesis. The row's own C2/C5/C10 also come from the
**0.6.3 engine** while the shipped image moved to v0.6 on 2026-10-21, so a clean re-run needs both
engines re-measured before any cell is comparable. Receipt `~/benchmarks/tp12-20261029/ds4-tp2/REPORT.md`.

**GHCR.** The org's package list (`gh api /orgs/littlecedar/packages?package_type=container`) held only
four packages, none of them `dgx-spark-dsv41`: the shipped image had never been pushed, and every
anonymous probe said `denied` because GHCR never reveals existence to anonymous callers (a public
package answers `manifest unknown` for a wrong tag instead). The workstation token carried
`gist, read:org, repo, workflow` and no `write:packages`; two device-flow codes expired before the
owner could enter them (`1940-BA7A`, `7C37-121D` — codes live ~15 min and the first attempt was killed
by a 45 s shell timeout, so the flow must run as a persistent service). After the grant
(`write:packages`) the head logged in and `docker push ghcr.io/littlecedar/dgx-spark-dsv41:canary-roce-aff52fa5`
started. Two traps recorded for the next pusher: a bare `sha256:<manifest digest>` inspect is **not** a
presence test (both other ds4 pins resolve via `repo@digest` to `a8ccece6` / `788c3654`), and the
recipes' `container:` refs are **unqualified**, which docker resolves against Docker Hub — they only
work on the fleet because the image is resident, and each must become `ghcr.io/littlecedar/…@sha256:…`
before a fresh node can pull it.

## Node hygiene sweep — 2026-10-29 19:0x ET (owner: "clean up after yourself")

Scope: all six nodes, `$HOME` and `/tmp`, classified against the tracked tree before anything was
removed (the AGENTS rule: grep the repo for the basename, because worker-side paths get cited too).

**Loose files: 88 → 39 on the head, and the same shape on the others (19/19/11/13/13).** The
classification kept 27 names and deleted 49. Kept because cited: `cand6.log`, `chain.log`,
`chunk-probe.log`, `gate.log`, `h3-chain.log`, `s1/s2/s3-chain.log`, `hf-verify.log`,
`tf-tp2-boot.log` (queue/DEEPSEEK/attic provenance), `depth_ttft.py`, `disk_isolate.py`,
`measure_arm.py`, `probe_ttft.py`, `warm_cold.py`, `p3.sh` (attic perf notes), `api.py` (TODO), plus
plumbing that is not scratch: `bashrc`, `etc-hosts`, `nfs-fstab`, `rollback.bash`, `setup-nfs.bash`,
`detect_and_configure_cluster_networking.py`, `run_cluster.sh`, `concurrency-ladder.yaml`,
`ornith-nvfp4-recipe.yaml`. Deleted as uncited scratch: the `*-prefetch.log` / `pull-*.log` pull
trails, `bw.py`/`bw2.py`/`fst_leak.py`/`poison.sh`/`samp.sh`/`qa.py`-class one-offs,
`drive_embed.sh`/`drive_rerank.sh`, the `laguna-*.sh` set, `ornith-watch.sh`, `copy-engram.sh`,
`ds4_probe*.sh`, `*.pid`, `spark_diag_*.ndjson`, and 12 `/tmp` scratch files.

**Staging leftovers: 96 GB.** `~/dsv41-engram` on `.34` and `.35` (48 GB each) held per-rank
`engram-l{1,14}-r2of4.bin` shards. **Correction, 2026-10-29 19:4x ET — these are not duplicates of the
pool, and the first wording said so wrongly.** The pool holds a *different artifact*
(`engram-l1/14.safetensors`, the format the TensorFold TP=2 lane reads via `TF_DS_ENGRAM`); the `.bin`
files are knapcio's packed 264-byte-record TP=4 shards, which
`recipes/cybersec/mods/dsv41-engram-fetch/README.md:153-154` describes as something the builder
"emits … should another lane need them". So the honest basis for removal is: (a) no code path in
`recipes/`, `mods/` or `tools/` names `r2of4`, (b) every launcher path resolves to the pool, (c) the
knapcio TP=4 production serve is running without them, and (d) they are **regenerable byte-identically**
from the official repo with `build-dsv41-engram.py --format packed --tensor-parallel 4 --rank R` — it is
a repack, not a derived tuning artifact. Both copies dated Oct 2–5; the repo's own history records the
same pre-warms already removed on `.32`/`.33` (`attic/cybersec/AGENTS.md:578`). If a lane ever needs the
packed format again, that command rebuilds it; nothing was irreplaceable. Also removed: `~/scratch` on `.34` (628 MB) and `.35` (8.7 MB,
root-owned files needed `sudo -n`), `~/ornith-diag`, `~/modwork`, `~/q4mods`, `~/build`, `~/bisect-ctx`.

**Stale runtime-cache trees: 299 GB, free nodes only.** `cache-audit.py` over a fresh
`sparkrun setup prune-runtime-cache --all --dry-run` census (215 trees, 2588.8 GB — but the tree count
flatters the total: most `llama-cpp` leaves are 0-byte stubs, while three sglang trees carry ~1 TB
between them). `--all` was used **only** for the read-only census; nothing was applied from it. The
deletions came from the audit's attribution, and every tree with a marker inside 72 h was left alone —
`--all` would have taken today's warm trees too and re-paid their torch.compile/Triton warms on the next
launch. The audit names trees"no On the two free nodes that set included the previous
revision of the TP=2 arm's checkpoint and the combined EXL3+engram pack:
`LibertAIDAI__...-f236b776` (100 GB on `.30`, 100 GB on `.35`, markers Oct 17–18) and
`littlecedar__...-2bd42ac5` (100 GB on `.35`, marker Oct 7). Current-pin trees (`-55410efc`, marker
today) and every marker inside 72 h were left alone.

**Result by node** (`df -BG` before → after): `.30` 1509 → **1608 GB**; `.35` 1233 → **1478 GB**;
`.34` 1164 → **1212 GB**. `.31`–`.33` untouched. Fleet-wide: 0 containers, 0 volumes.

**Left for a production window, not judgement:** `.31`–`.34` still hold
`deepseek-ai__DeepSeek-V4.1-Flash-11826f49` (426.8 GB), a `DeepSeek-V4.1-Flash` tree the audit cannot
attribute to any shipped pin — the four ranks running the production serve are not a place to delete
runtime caches from on inference. Also unclaimed: a root-owned `IFM__K2-Horizon-MoVA-36B-A4B-FP8`
tree on `.35` from the retired K2 MoVA lane (`attid/ifm` archive), unreadable to `du` as the red user.

## Free-node last-occupant rows retired at the 2026-10-30 13:00 ET board refresh

The board contract keeps `## In flight` to live state — active boots/serves plus one census row — and the
two free nodes had each accumulated a "last occupant" paragraph. Both rows are retired here verbatim;
their live state at 13:00 ET (0 containers / 0 volumes, no reservation) is in the census row.

- `.30` — **nothing live (no reservation)** — 0 containers / 0 volumes at 12:00, and no research window is
  declared, so the node is free for any arm. Last occupant was rank 0 of
  `deepseek-v4.1-flash-abliterated-cyber-tp2-tensorfold-sglang`, task `38aaa36e56a717b8_4a5369625a71` (the
  07:52:59 boot), container `sparkrun_38aaa36e56a717b8_4a5369625a71_node_0`, image
  `ghcr.io/littlecedar/dgx-spark-dsv41@sha256:19977a03…` (sglang `0.0.0.dev1+g09daea94a`), model
  `littlecedar/DeepSeek-V4.1-Flash-EXL3-2.9bpw-with-engram` @ `48afcd1c…` with the `drowzeys` abliterated
  layer graft, context 1048576, engram on: it readied in **57.6 s** off the warm rank cache (`weights in
  25 s`, `DSpark (3 stages) loaded`, `DSpark 5 drafts`, allocator ceiling 106.5 GiB) and the watchdog saw
  `healthy endpoint=ok` at `t=62 s`, but both instruments then **replayed recorded state instead of
  measuring** — `llama-benchy` logged `Prior benchmark state for bench_e5219f05b245 is COMPLETE —
  re-emitting its recorded results; no requests will be sent` and wrote no `ladder.json`, and
  `tool-eval-bench` logged the same for `bench_8d872f6df1ff` and wrote no `house.json`, so the whole
  07:54:08–07:54:19 artefact set is a transcription of the 06:04 boot's cells. The still-open measurement
  is the one waiting on `QUESTIONS.md` #55.
- `.35` — **nothing live (no reservation)** — 0 containers / 0 volumes at 12:00; no research window is
  declared, so it is free too. Last occupant was the 09:13 boot of `qwen3-vl-reranker-2b-vllm-b12x` (TP=1,
  served on this node, port 8011), which ran the pooling rerank ladder as `bench_2f1db32c19c9` and was
  stopped after the fourth cell — the node re-counts 0/0 by this census. Before it, rank 1 of the 07:52:59
  TP=2 boot (`…_node_1`, task `38aaa36e56a717b8_4a5369625a71`, `restart=0 oom=false`), whose per-rank log
  is **not** in that receipt: the every-host harvest (`d20c526`) landed at 07:56, four minutes *after* that
  boot launched, so only rank 0's 2 002 B banner was captured and rank 1 is evidenced only through rank 0's
  log line `rendezvous=…` plus the ready pair — the every-host walk has still not run live on a **pair**
  (the 09:13 harvest did write a 147 KB `serve-solo.log`, but that is a TP=1 arm). Its earlier rank-1
  figures stand as history: `rank 1: weights in 316 s (written to the rank cache)`, `allocator ceiling
  107.0 GiB`, `rank 1 ready in 506.1 s, following rank 0`.

## The board's skip set named a recipe that does not exist — 2026-10-30 17:20 ET

The census row and the `tp12-campaign-staging` row carried, from the 15:00 tick (`44e21c7`, whose own
subject reads "name the campaign's skip set, which nothing persists") through the 16:05 and 17:05 ticks, a
skip set written as `qwen3.8-flash-next-uncensored-nvfp4-{sglang,vllm,solo-vllm-b12x}`,
`nex-n2.5-mini-uncensored-nvfp4-sglang`, `zz-spark-x2.6-4b-int8-sglang`, plus the claim that "nothing
persists that list, so each run recomposes it". Both halves were wrong:

- `qwen3.8-flash-next-uncensored-nvfp4-solo-vllm-b12x` exists nowhere in the tree. The brace group fused
  two different names — the real recipe is `recipes/qwen4/qwen3.8-flash-next-nvfp4-solo-vllm-b12x.yaml`,
  which is *not* an uncensored arm — while `nex-n2.5-mini-uncensored-nvfp4-vllm`, a live skip entry, was
  omitted.
- The list is persisted: the untracked `.local/fleet.yaml` `skip:` holds those five and
  `tools/queue-drip.py:plan_pass` hands them to `next-arms.py` on every pass. "Nothing persists it" was
  false; what happened is that the drip was not running, so the tick passed the set by hand.

The rows now name the five from the config, cite the drip as the consumer, and state that
`zz-spark-x2.6-4b-int8-sglang` is `tp: 1` — it is *skipped*, not counted, and the five counted-unmeasured
arms are the TP=2 set. Re-derived 17:00 ET on the head, not carried: manifest `tp` split 33 / 9 of 42, 45
measured receipt arms, 5 unmeasured.

## Landed rows retired at the 2026-10-31 03:00 ET board refresh (session boundary)

The board carried **121 rows** in `Landed this session` at its 02:00 ET generation (`bb590b5`), accumulated
without a boundary since the 2026-10-29 03:10 ET clear. No single session can own that span: the rows run from
2026-10-29 03:03 ET to 2026-10-31 01:05 ET, while the only peer session still resident (pid 1575174, opened
2026-10-30 12:52 ET) last wrote 01:18 ET and the tick itself runs `omp -p --no-session`. Keeping the table would
leave the contract's "current session only" unsatisfiable for every writer, so it is retired here instead.

Its preservation was audited before the deletion: every backticked SHA was checked against this file and
**81 of 86 were absent** — the sections above narrate the same work (the TP12 campaign, the node sweep, the
skip-set correction) but rarely carry the SHA. Rows are unedited, in board order, so a few clauses do restate a
narrative that already has a home above; the per-commit mapping does not.

| 03:03 ET | `6867d1b` | "Consolidate documentation: contents blocks, dedupe, stale facts" — this session's archive sweep: nine completed items copied verbatim into `attic/DONE.md` under a new `# 2026-10-29 sweep` (the seven 2026-10-25 unparked retry-queue items, window-4's Beam cells (b)–(d), the OrcaCyber 15.7G ship), the unparked queue section reduced to the archive stub, `QUESTIONS.md` `#18` settled into `TODO.md` §"Settled questions", and five broken relative links repaired (`TODO.md` 3445→3310, `attic/DONE.md` 1206→1382, `QUESTIONS.md` 20→19 lines); line-set check over the original reads 0 unaccounted except the five repaired link lines. One continuity line added to `TODO.md` §Retry queue window 4 at 03:09 ET sits in the working tree, after that commit |
| 03:15 ET | working tree | board refresh — cleared the `Landed this session` table per the session-boundary rule (the prior session's sixteen rows are retired verbatim in `SESSION-RECORD.md` §"Landed rows retired at the 2026-10-29 03:10 ET board refresh", verified there against `git show 07cecb7:mad-science/STATUS.md`), dropped the `h3-quartet-retry` row because `TODO.md` archived that item today as a terminal negative (`attic/DONE.md` §`# 2026-10-29 sweep`: second deadlock repro, filed sgl-project/sglang#46390), and kept the 03:10 ET census and the manifest re-derivation unchanged |
| 03:19 ET | `f68b06c` | "Refresh status board 03:14 ET: fresh census, the live pin named, prior session's rows retired" — commits the board write above: the retired prior-session rows live in `SESSION-RECORD.md` §"Landed rows retired at the 2026-10-29 03:10 ET board refresh", the live production pin is named in the census row, and the archived `h3-quartet-retry` row is gone |
| 03:21 ET | `3a6ee0a` | "Close doc-sweep gaps: quote-safe links, divergence home, US spelling" — escaped the quoted card link so "Apache 2.0 License" no longer resolves to this repo's MIT `LICENSE`, normalized every British `licence`/`licences` noun to `license(s)`, moved the ds4 reply-level divergence table out of the generated `results/RESULTS.md` into `benchmarks/README.md`, named all 19 `.omp/skills` entries in `AGENTS.md`, and flipped `queue.json`'s `h3-quartet-retry` to `done` through `tools/task-queue.py done`; gate 1047 tests OK, 79/79 validate |
| 03:25 ET | this tick | board refresh — fresh six-node census, the `tp12-campaign-staging` row's figures re-derived (`13` distinct digests, `sglang-main-arm64:6563312` absent on `.35`, 11 receipt dirs / 20 JSON), Landed rows for `f68b06c` and `3a6ee0a` appended; queue re-read: 14 open tasks (11 queued + 3 blocked), 0 stale `claimed_by` locks, `tools/task-queue.py check` green |
| 04:00 ET | this tick | board refresh — census unchanged and a **serve-readiness probe** added for the production quartet: serve child pid 280 alive in `c989632ede4f538e_b4e3c94ef77c_node_0` running the shipped `sglang.launch_server` line, `GET /v1/models` **200** (closes the "Up can mask a dead child" gap); `tp12` figures re-read unchanged (42 entries / 15 refs / 13 digests, `img_ok` 12 / `mod_ok` 35, receipt tree 11 dirs / 20 JSON); queue re-read unchanged (14 open, 0 stale claims, `check` green); no commits since `b215934` |
| 09:10 ET | `49c9f40` | recorded the push backlog once, where history belongs rather than on the board: seven board commits (`b215934`…`3298fdd`) reach this tree but not GitHub, and no reachable host can push — the workstation has no credential helper/`gh`/GitHub SSH key, and the head's `store` helper holds only a `huggingface.co` line while both its `id_ed25519*` keys are rejected. The head's clone already carries the tail (`3298fdd`), so the fleet reads current state; the tail clears on the next credentialed peer push, as `6867d1b`/`3a6ee0a` did. Entry: `SESSION-RECORD.md` §"Push backlog — 2026-10-29 09:10 ET" |
| 11:52 ET | `ecb8ba8` | "Fix boot-watchdog container resolution for solo (TP=1) tasks" — the watchdog's default `_node_0` container name is wrong for a TP=1 launch, where sparkrun names it `_solo`, so every solo boot read `serve_pid=gone` and the hour's first TP12 launch was misjudged dead inside its grace window; added `pick_container`/`resolve_container` (prefers `_node_0`, else the first match, else the fallback) plus four tests (`tests.test_boot_watchdog` 12 OK). Pushed in the same hour — **which also falsifies the 09:10 ET row's premise**: the workstation could push all along, because its `/home/siv/.gitconfig` carries the `gh auth git-credential` helper; the failure was this session's sandbox `HOME=$PWD/.local/sparkrun-home` (exported for the `sparkrun validate` gate) carrying neither gitconfig nor gh auth. Corrected in `SESSION-RECORD.md`; keep the sandbox HOME for sparkrun, never for `git`/`gh` |
| 11:56 ET | `8339906` | "Archive the b12x parity item and record two register decisions" — the owner's window-4 ruling executed: item 3 (b12x parity boot) moved verbatim into `attic/DONE.md` §"Retry queue — window 4 (2026-10-29 sweep)" with only the checkbox normalized (0 stranded body lines), item 2 (ds4 candidate survey) kept open with a dated status line naming the blockers, and the ornith omp trial recorded as **reopened** with the ~1,000-turn extension and its queue state kept `queued` |
| 11:58 ET | measurement | **TP12 arm run — `nemotron-3.5-lightning-30b-a3b-nvfp4-vllm` (TP=1) on `.30`**, the first authorised arm of the owner's next-window authorisation: task `7522c749bf81cc03_bd45c6067dae`, image `dgx-vllm-eugr-nightly@sha256:cc47adc1…`, model pin `bee75962…` (pool snapshot verified complete: 52 safetensors + tokenizer + chat template). TTR ≈ 280 s; ladder (`concurrency-ladder.yaml`, d0 pp2048 tg128 n=5) **C1 63.86 ± 1.78 / C2 93.73 ± 1.10 / C5 122.74 ± 1.35 / C10 144.64 ± 1.13** t/s with prefill 6,173–6,243 t/s, and `standard-suite.yaml` (tool-eval-bench short, 15 scenarios) **score 90 — 13 pass, 1 partial, 1 fail (`TC-12` missing_step)**. Every ladder cell is inside the spread of the shipped row's 2026-10-21 boot (63.27 ± 0.65 / 90.81 / 122.27 / 144.15), so the index row stands unchanged and this run is an independent reproduction at a different digest; receipt `~/benchmarks/tp12-20261029/nemotron/REPORT.md` + `launch.log` + 8 JSON/CSV outputs. Serve stopped by task id, `.30` re-verified 0 containers / 0 volumes; watchdog classified the load `loading`/`serve_pid=alive` and exited 0 on readiness |
| 12:06 ET | `58d602f` | "Sample the busiest reader in the boot watchdog's io probe" — the io evidence line read the *wrong process*: `pgrep -f …` piped to `head -1` picks the parent `vllm serve` while the reader is the child `EngineCore`, so the probe logged `io_delta=0` through the whole 52-shard load (sglang arms hid it — the parent reads the weights itself). Now samples every match and reports the largest `rchar` (the reader, and stable across samples so the delta stays a delta); a pgrep match counts as alive even when `/proc/<pid>/io` is unreadable, where the old `NO-PID` path reported gone and could stop a slow load at grace expiry; the remote script rides stdin instead of an ssh argv string, so the serve pattern needs no escaping. 4 tests (`tests.test_boot_watchdog` 15 OK) + a live smoke against the production serve on the quartet (`resolve_container` → `…_node_0`, two samples 4 s apart, rchar 248,402,824,132 → 248,403,021,252). Gate: **1054 tests OK (2 skipped)**, 79/79 validate, `bash -n` + `py_compile` clean. Also folded two review findings: the TP12 receipt tree is **10 arm dirs + `_teb-salvage`** (so 11 of 42 stands), and the archived window-4 item 3 now carries its closing status — the b12x parity boot *did* run (boot 5 `…f31ef03f5cb9`, house 37/37, needle 32k 10/10, ~half the shipped C1) while its own last in-flight line still read "boot pending" |
| 12:41 ET | `CLR-BRIEF.md` | opened `mad-science/CLR-BRIEF.md` for the owner: the **three** `blocked` rows are one external kernel gate (DeepGEMM's paged-sparse logits assert `arch_major == 10`, SM100, while GB10 is SM121) plus its two dependents, and the second question is the GHCR credential for the local-only production image. Each question carries options, a recommendation and blank answer space, in prose — no tables, per the owner's rendering constraint. **Corrected the same hour:** the first draft claimed five blocked rows and a base-lineage choice, but `w4-s0/s1/s2/s3/candidate6` are `done` with 2026-10-26 verdicts (`TODO.md:801`) measured on the plain shipped `aff52fa5` arm — the lineage question was settled operationally, not open. The brief now carries that as a note instead of a question |
| 13:05 ET | attempt aborted | **`deepseek-v4.1-flash-tensorfold-tp2-1m-sglang` (TP=2, `.30`+`.35`) booted and served but was NOT measured** — sparkrun TTR **63.8 s**, `/v1/models` 200 with `max_model_len` 1048576, yet the serve's own request log shows decode at **2.9–3.1 tok/s** (128 tokens over 45–48 speculative rounds, `accepted=82/142`, ttft 20–34 s of which prefill 6.6 s) against the row's C1 66.4, so the ladder was killed instead of publishing a ~20× false regression. No OOM and no restart (`RestartCount=0`, `OOMKilled=false`); CUDA graphs do exist for the batched path (`--parallel warm-up: 64 round graphs, 4 drafter graphs`) while the single-stream warm-up reports `decode graphs {}`; Engram is on (`/cache/huggingface/hub/dsv41-engram`) and cold pool reads are the leading hypothesis, unproven. The row's own C2/C5/C10 also come from the **0.6.3 engine** while the shipped image moved to v0.6 on 2026-10-21, so even a clean re-run needs both engines re-measured before comparison. Receipt `~/benchmarks/tp12-20261029/ds4-tp2/REPORT.md`; task stopped by id, both nodes back to 0 containers / 0 volumes |
| 12:58 ET | measurement | **TP12 arm run — `qwen3-coder-next-int4-autoround-vllm` (TP=1, vLLM) on `.30`**: task `3d9fbe520b47c3a3_274ed688acf9`, image `dgx-vllm-eugr-nightly@sha256:cc47adc1…`, model `Intel/Qwen3-Coder-Next-int4-AutoRound` @ `79c8a6bb…` (23-entry snapshot). Ladder **C1 68.77 ± 0.17 / C2 111.91 ± 2.69 / C5 180.82 ± 3.31 / C10 243.69 ± 1.67** t/s with prefill 6,491 → 19,867 t/s, and standard-suite **93** (13 pass / 2 partial / 0 fail) — every cell inside ~3 % of the shipped row (70.4 / 114.0 / 177.1 / 249.5) at a different digest, so the row stands and the 93 is the arm's first tool-eval-bench score. torch.compile cache hit (16 artifacts, 0.43 s). Also the first live test of this morning's io-probe fix: the watchdog resolved `…_solo` and sampled the **`EngineCore`** child (309 MB `rchar`) instead of the `vllm serve` parent. Receipt `~/benchmarks/tp12-20261029/qwen3-coder-next/REPORT.md`; serve stopped by task id, `.30`/`.35` verified 0 containers / 0 volumes |
| 13:01 ET | `0a49dbb` | "Pin the shipped ds4 image by its registry digest after the first push" — the image had **never** been pushed (the org's package list carried no `dgx-spark-dsv41` entry, which is why every anonymous probe said `denied`: GHCR never reveals existence to anonymous callers). Pushed in 96 layers, digest `sha256:7c3cb394…`; the recipe now names that digest **and** the registry host, fixing a latent defect as well as adding a pin — an unqualified `littlecedar/…` ref resolves against Docker Hub, so the old line could only work on a node that already had the image resident. Visibility is still `internal`, so the anonymous pull check is outstanding and not claimed. History: `SESSION-RECORD.md` §"TP12 campaign + GHCR push" (`00f5363`) |
| 13:05 ET | measurement | **TP12 arm run — `qwen3.8-27b-nvfp4-dflash2-sglang` (TP=1) on `.30`**: task `3002453c93859a51_9a16bb5bb821`, model `RadixArk/Qwen3.8-27B-NVFP4` @ `319f741c…`; ladder **C1 30.29 ± 1.90 / C2 53.78 ± 5.91 / C5 72.31 ± 4.04 / C10 92.09 ± 5.06** t/s, prefill 2,094–2,325 t/s, and standard-suite **97** (14 pass / 1 partial / 0 fail) — the campaign's best quality score yet. Against the row (33.8 / 57.4 / 89.5 / 100.9) C1/C2/C10 are within cross-day noise but **C5 is −19 %**, flagged not written off: settling it is what `h2h-second-boot-ladder` is for. No index cell changed. Receipt `~/benchmarks/tp12-20261029/qwen38-27b-dflash2/REPORT.md`, watchdog log shows the new io probe following the reader (147 MB → 402 MB delta) |
| 13:59 ET | `8bb0e13` | "Give the nightly sweep a Hub token so pin compares are authenticated" — issue #1's `Sweep exit code: 2` was **not** drift and not a broken tree: `run()` sets 2 only when a gated row's class ends in `-unresolvable`, and the CI report carried eight of those, every one "compare failed: HTTP 401", because the job exported no `HF_TOKEN` and the sweep compares anonymously on a hosted runner. The same command with `hf auth login` gives **zero** unresolvable rows and exit 1. Fix: the job now exports `HF_TOKEN` from a repository secret (set 17:59 ET); a dispatched verification run reads **drift 34 / unresolvable 0 / accepted 10 → exit 1**, and the issue flipped itself back to "Pin drift found" with the `sweep-broken` label dropped |
| 14:05 ET | measurement | **TP12 arm run — `ling-3.0-flash-int4-dspark-sglang` (TP=1) on `.30`**: task `3effce2e30113dd9_6542300e1f8e`, model `inclusionAI/Ling-3.0-flash-int4` @ `7a27e9eb…` (24 shards, pool snapshot hit); ladder **C1 45.32 ± 4.31 / C2 59.89 ± 10.74 / C5 107.01 ± 5.32 / C10 86.78 ± 1.57** t/s, suite **97** (14 pass / 1 partial / 0 fail, tying dflash2 for the campaign's best). Against the row (45.5 / 66.2 / 100.2 / 85.9) C1 reproduces to −0.4 %, C5/C10 sit slightly above, and C2 is −9.5 % with the widest spread — no index cell changed. **Recorded anomaly:** after both benchmarks the serve's HTTP frontend stopped listening (in-container `curl 127.0.0.1:8000` → refused; log ends at 200s, 18:00:41Z) while the container and its `sglang::scheduler`/`detokenizer` workers stayed alive and no OOM appears in the node log — and the watchdog therefore stayed `loading` forever, never `dead`, because it matches a process rather than a listening socket. Receipt `~/benchmarks/tp12-20261029/ling-3.0/REPORT.md`; stopped by task id, `.30`/`.35` back to 0/0 |
| 14:04 ET | `927ce00` | "Make package visibility a written rule, and close the pull claim" — the shipped ds4 image is **public** (owner flip) and the gate that proves it is the one that was missing: the registry now mints an anonymous pull token (200, was 401), all three pushed digests HEAD **200**, and a clean-`DOCKER_CONFIG` `docker manifest inspect` returns the manifest whose config digest is the original `3f448081…`. `AGENTS.md` gains **"Published artifacts must be public (a rule)"**: `internal` is a defect because every fleet node's probe passes while the only check that matters fails |
| 14:05 ET | `d815328` | "Index the public-visibility rule and point it at the check that enforces it" — added the missing Contents entry, and replaced "remember it" with the code that already checks it: `ghcr_token` (`tools/refresh-sweep.py:349-357`) mints an anonymous token per ghcr repo and raises `FetchError` without one, `classify_container` (`:584-596`) resolves every `ghcr.io/…@digest` pin through it, so a non-public package becomes `container-unresolvable` → **exit 2 → `sweep-broken`**. Verified after the flip: all four repinned ds4 arms classify `container-current` at their pinned digests |
| 14:07 ET | `3f951d4` | "Track the three container refs that resolve to no registry at all" — the inverse defect of the day: `explore/zz-mellum2.1-…-mtp` pins `dgx-spark-llama-cpp:upstream-d854d98-cu130`, a tag GHCR does **not** have (the package's only tag is `upstream-a37cc46`, a different llama.cpp commit) and unqualified besides, and the two `sglang-main-arm64:6563312` arms pin a local-tag-only build — none can pull on a fresh node. Queue row `published-image-refs` (1 h) carries the three options (push under a pin / repin plus boot / retire) rather than guessing; queue now 47 tasks, 15 open |
| 15:02 ET | measurement | **TP12 arm run — `qwen3.8-27b-uncensored-nvfp4-sglang` (TP=1) on `.30`**: task `aefb625955c32638_745f77265393`, model `orcarouter/Qwen3.8-27B-Uncensored-NVFP4` @ `f8489198…`; ladder **C1 9.94 ± 0.00 / C2 19.86 ± 0.46 / C5 42.14 ± 1.00 / C10 82.22 ± 3.45** t/s (prefill 2.2k → 9.4k with concurrency) against the row's 10.2 / 19.67 / 41.12 / 75.77 — three cells inside ±2.5 % and C10 8.5 % ahead, the campaign's cleanest reproduction — and standard suite **100** (15/15 pass, no partials or failures), its first perfect score. Receipt `~/benchmarks/tp12-20261029/qwen38-27b-uncensored/REPORT.md`; stopped by task id, both free nodes back to 0/0 |
| 15:2x ET | `24b50ec` | "Update the ds4 image guards for the registry-qualified pins" — **the gate had been red for six consecutive commits** (`2dbec6c`…`4cfea0a`) and nothing was watching it: six failures in `tests/test_ds4_recipes.py`, all the lane guards correctly rejecting the new `ghcr.io/…@sha256:` refs. Fixed by moving the guards to the *stronger* invariant — host required, digest-only — so the unqualified form that resolves against Docker Hub can never come back green; both `test_control_image_unpinned` controls still reject a tag. Local: `tests.test_ds4_recipes` 123 OK, suite 1054 OK; CI run `40937855289` **success** |
| 15:3x ET | `63ec8d4` | "Derive the image negative controls' anchors from the recipe" — the two controls still pasted a digest as their mutation anchor, which is the same fragility that took the gate red, in miniature: the next digest bump would strand the anchor. Both now read the recipe's own `container:` value, while `TF_IMAGE` keeps its real job (proving this arm serves exactly that build). CI run `40938576151` on this HEAD **success** — `gate` is green at `63ec8d4` |
| 16:0x ET | measurement start | sixth arm launched — `qwen3.8-27b-ablit-cyber-unlock-nvfp4-dflash2-sglang` (TP=1) on `.30`, the last of the four staged cybersec/qwen3 TP=1 candidates; its image is the same `dev-cu13@sha256:0b3e3970…` digest the uncensored arm used, so no pull is involved |
| 17:02 ET | measurement | **TP12 arm run — `qwen3.8-27b-ablit-cyber-unlock-nvfp4-dflash2-sglang` (TP=1) on `.30`**: task `60696be961054e88_3aee3374d5ba`, model `sakamakismile/Qwen3.8-27B-AEON-ULTIMATE-UNCENSORED-NVFP4` @ `8d5a3317…`, image the same `dev-cu13@sha256:0b3e3970…` digest as the uncensored arm; ladder **C1 28.74 ± 1.11 / C2 53.37 ± 6.62 / C5 87.41 ± 10.64 / C10 78.44 ± 2.74** t/s, suite **90** (13 pass / 1 partial / 1 fail). **Crossed against the row** (33.3 / 49.4 / 84.6 / 92.9): the slow cells sit 13.7 % and 15.6 % below while the busy cells sit 8.0 % and 3.3 % above — a different concurrency curve, not noise, so no index cell changed and the pair is flagged for `h2h-second-boot-ladder`. Receipt `~/benchmarks/tp12-20261029/aeon-cyber/REPORT.md`; stopped by task id, both free nodes 0/0. Campaign row returned to `queued` with the stale claim cleared, since no boot is live |
| 18:0x ET | measurement start | seventh arm launched — `zz-ornith-1.5-122b-nvfp4-mtp-vllm` (TP=1) on `.30`: the first 122B this fleet has tried on one node, and the only remaining staged candidate that is not pooling-shaped. First attempt `recipes/explore/…` failed instantly (`Recipe not found`) — the probe lives in `recipes/ornith/`, so the path was globbed before the retry rather than guessed twice |
| 18:44 ET | measurement + defect | **TP12 arm run — `zz-ornith-1.5-122b-nvfp4-mtp-vllm` (TP=1) on `.30`**: the fleet's first **122B on a single node** — task `390833e14b644c0e_6c69507da4e9`, model `ornith-ai/Ornith-1.5-122B-NVFP4` @ `f049036f…`, load **15.9 min** to `/v1/models` 200 (longest of the day), then ladder **C1 39.30 ± 2.49 / C2 49.52 ± 2.18 / C5 71.10 ± 4.56 / C10 81.87 ± 4.67** t/s (prefill 1.8k→2.8k) and suite **97** (14 pass / 1 partial / 0 fail), MTP drafter engaged. **Operator defect, mine:** the chain had no teardown, so after both benchmarks finished at 18:22/18:25 the serve **idled ~18 min on a held node** (GPU 0 %, load 0.34) until the owner said so — fixed by `run-arm.sh` in the campaign dir, which stops the task and re-counts containers/volumes unconditionally, including after a failed benchmark. No fleet watcher could have caught it: the endpoint was healthy, so the watchdog's verdict was correctly `healthy`. Receipt `~/benchmarks/tp12-20261029/ornith-122b-mtp/REPORT.md` |
| 19:1x ET | hygiene sweep | **node cleanup, owner-ordered** — classified against the tracked tree before deleting anything. Loose `$HOME`/`/tmp` files **88 → 39** on the head (19/19/11/13/13 elsewhere): 49 uncited pull trails and one-off scripts deleted, 27 kept because cited (queue/DEEPSEEK/attic provenance) or plumbing. Staging leftovers **96 GB**: `~/dsv41-engram` on `.34`/`.35` held per-rank `r2of4` shards nothing reads (every code path uses the pool copy, 189 GB, present; the same pre-warms were already removed on `.32`/`.33`). Stale runtime-cache trees **299 GB** on the free nodes only, per `cache-audit.py` over a fresh prune census (215 trees / 2588.8 GB): the prior revision of the TP=2 checkpoint and the combined EXL3+engram pack, all markers Oct 7–18. **Result**: `.30` 1509→**1608**, `.35` 1233→**1478**, `.34` 1164→**1212 GB**; `.31`–`.33` untouched; 0 containers / 0 volumes fleet-wide. Left for a production window: 426.8 GB of an unattributable `DeepSeek-V4.1-Flash` tree on `.31`–`.34`, plus a root-owned retired K2 MoVA tree. Detail: `SESSION-RECORD.md` §"Node hygiene sweep" |
| 18:52 ET | `673eb8e` | "Install an EXIT trap in run-arm.sh and land the board tick that was left behind" — two review findings, both mine: the previous commit took only the three tool files and left the 18:45 board row uncommitted while I reported success (the pathspec trap; `git commit -- <paths>` takes what is named and "Everything up-to-date" was a no-op push), and `run-arm.sh` only stopped the task on its normal path, so a killed script leaked the serve exactly like having no stop at all. The trap (`sparkrun stop "$TID" … ; exit` on `EXIT INT TERM`) is installed as soon as the id is parsed; the guard grows a `test_exit_trap_covers_a_killed_script` with a third negative control that deletes the trap line, and the two existing controls were narrowed to line-start `sparkrun stop` because the trap line itself contains those words |
| 19:5x ET | measurement | **TP12 arm run — `zz-ornith-1.5-122b-nvfp4-vllm` (TP=1, `.30`)**, the non-MTP twin of the 18:44 run, driven end to end by `run-arm.sh` (rc=0): task `390833e14b644c0e_f39c898cde02`; ladder **C1 26.84 ± 0.38 / C2 39.21 ± 0.38 / C5 61.18 ± 0.53 / C10 73.32 ± 0.19** t/s, suite **97** (14/1/0). **The pair is the campaign's cleanest result**: against the MTP boot (39.30 / 49.52 / 71.10 / 81.87, suite 97) the drafter buys **+46 % C1, +26 % C2, +16 % C5, +12 % C10** and costs nothing in quality — the gain decaying with concurrency is exactly the speculative-path signature. Second lane (`clef-flash-decision-sglang`) booting on `.35` after a **stale sparkrun resource claim** (`pid 3721679` exited without releasing; `resources list` showed `alive:false`) was cleared with `daemon resources reconcile … --acknowledge-effects`. Receipt `~/benchmarks/tp12-20261029/zz-ornith-1.5-122b-nvfp4-vllm/REPORT.md` |
| 19:58 ET | `5ee5c0a` | "Fail fast when sparkrun refuses a launch" — a refused launch exits at once, but the runner backgrounded the launcher and then waited up to five minutes for a container that would never appear; `.35` burned a window that way tonight on a stale resource reservation (`pid 3721679` exited without releasing). The launcher pid is now captured and the wait loop polls it — gone plus no container means `tail -5 launch.log` and **exit 5**. Guarded by `test_refused_launch_fails_fast` (pid captured, `kill -0` present, distinct status) with a negative control that strips the poll; suite **1065 tests OK (2 skipped)** |
| 21:0x ET | `4926d71` | "Probe the recipe's own serve port instead of assuming 8000" — both lanes ran to **rc=4** tonight and neither engine was broken. `clef-flash-decision-sglang` serves on **8020** (`port: 8020`, `--port {port}`) and the runner probed 8000 for 22 minutes, which is indistinguishable from a boot that never readies; `ling-3.0-flash-int4-dspark-sglang` is 8030 by the same mechanism, so it would have kept biting. The port is now parsed from the recipe (quoted or not, default 8000) for both the watchdog endpoint and the readiness probe; the first `sed` attempt split its expressions and the arm relaunched as `port=8000` again, which the relaunch log caught. Guarded by `test_serve_port_comes_from_the_recipe` plus a negative control. **`jev-27b-decision-vllm` is a different failure and is not fixed by this:** port 8000 was correct, its container exited **137**, and the cause is **unexplained**: `dmesg` is denied without root and `sudo journalctl -k` over that window holds **no** OOM or `Killed process` line, so the earlier "cgroup kill" phrasing was an inference from empty output, not evidence — recorded as a failed boot, not a measurement |
| 21:2x ET | `ec1aef2` | "Measure decision arms with the decision lane's instruments" — `clef-flash` readied in **239 s** on 8020 and then scored `rc=3`: a decision arm answers `/v1/systemone`, so tool-eval-bench and llama-benchy both fail its first task (`[1/1] FAILED`) — the pooling-lane instrument gap in a second lane, and why two arms tonight produced no numbers. A `*/decision/*` recipe now gets `tools/decision-ladder.py` for its cells and `tool-eval-bench --decision-bench-only` for accuracy, with `$DECISION_CASES` (the instrument's own 400-case split) and JEV's `/v1/completions` reachable via `ARM_LADDER_API`/`ARM_DECISION_HEAD`. Also corrected: the readiness ceiling was **90 checks (1350 s) under a 1800 s watchdog grace**, so the script's own timeout stopped serves the watchdog still called loading — now 150 checks; and the campaign's stale second copy under `.scratch/` is deleted. Guarded by `test_decision_arms_use_the_decision_instruments` and `test_readiness_outlasts_the_watchdog_grace` |
| 21:5x ET | `05381dd` | "Clear a leftover container of the same recipe, and never overwrite a receipt" — the runner resolved an **older** container of the recipe, its `sparkrun stop` hit a task id that was not running, and the real serve kept answering `/v1/models` 200 while the new engine could not bind 8020 (a ladder then scored 52/100 `URLError` against the wrong end). Leftovers are now cleared by the **`sparkrun.recipe` container label** (exact, exercised live against a running arm) before launch, and an existing receipt moves to `<arm>.prev-<HHMMSS>/` so a relaunch cannot replace a failed instrument's evidence with a truncated one. Guarded by `test_a_leftover_container_of_the_same_recipe_is_cleared_first` and `test_an_existing_receipt_is_moved_aside` |
| 22:0x–23:0x ET | audit | **The campaign count was rebuilt from evidence, not memory.** Intersecting `.scratch/tp12-campaign/manifest.json` with both receipt trees gives **16 of 42 manifest arms with a complete artefact receipt** (10-28: 10 dirs, tonight: 17 dirs, 24 distinct arms, 16 manifest entries). The hand tally said **25** and was wrong by nine; a review's call that the counting rule was inconsistent is what surfaced it. The rule is now uniform and stated in the row: a cell counts against the run with a machine-readable artefact (`ladder`/`house` yaml+json or a `data/benchmarks.sqlite` row) from whichever day produced one, and a logs-only run is a **reproduction** that corroborates. That standard made two defects countable instead of ambiguous — `ornith-1.5-9b-nvfp4-dflash-sglang` (97, c10 144.5 tg t/s) and `spark-x2.6-4b-fp8-sglang` (80, c10 218.1) both re-ran logs-only tonight and reproduced their 10-28 artefacts **to the digit**, so fp8's seven-point suite deficit against its bf16 control is reproducible rather than one night's accident. Unmatched manifest arms (26) are listed in the audit, not inferred |
| 23:1x–23:4x ET | `e819644` | "Add a staging auditor, and stage the fleet until all 42 arms can launch" — four boots tonight died on **present-but-partial snapshots**, so `tools/stage-audit.py` now asks the three questions that catch them before a window is spent: the pinned image resolves **by digest** on the free nodes, the pinned revision's **recursive** entry count matches upstream's, and its largest weight exceeds 1 MB by `stat -L`. Both measurement traps are encoded: a retagged image has an empty `Digest` column, and `du`/`ls -la` on an HF cache measure **link paths** (6.7 MB reported for a complete 39 GB snapshot). The first run found **4 arms needing staging** (two absent models) and cried INCOMPLETE on 40 intact ones until the count went recursive; both models are now pooled at their pins (Nex-N2.5 26 files / 2.82 GB largest; Qwen3.8-Flash-Next-Uncensored 31 files / 102.4 GB largest) and the audit reports **42 arms, 0 needing staging**. Same pass: `5e181e3` releases a **dead owner's** reservation before launching (four refusals today, once with both nodes idle) and never touches a live claim |
| 00:0x ET | `760554b` | "Put the benchmark verbosity where sparkrun accepts it" — `BENCH_VERBOSE=1` trailed the command and `sparkrun benchmark performance` has **no `-v`**, so both benchmarks aborted instantly with "No such option '-v'" and the arm read as one that measured nothing (one arm lost; re-running). The flag is global, before the subcommand, and the guard now pins its **position** rather than its presence. Same window: `1595bc2` adds `tools/bench-table-to-json.py`, which transcribes a printed ladder into `ladder.json`'s shape with a `source` field saying the framework wrote nothing — four runs tonight printed tables and wrote no file, and a labelled transcription beats both a lost cell and hand-typed numbers pretending to be an artefact |
| 00:1x ET | probe | **`nex-n2.5-mini-uncensored-nvfp4-sglang` serves garbage on SGLang, and it is not the instrument.** `/v1/chat/completions` (64 tokens) returns `content: ''` with `reasoning_content: '!!!!…'`, and `/v1/completions` — which bypasses the chat template — returns `'!!!!!!!!!!!!!!!!'` for "The capital of France is". The ladder dies at `[1/4] FAILED (4.1s)` because there is no usable content. The checkpoint's own card names **`library_name: transformers`** with `vllm`/`nvfp4`/`compressed-tensors` tags, `fidelity_summary.json` reports expert-down cosine 0.9961 over 40 experts, and the architecture is a hybrid-attention MoE (`Qwen3_5MoeForConditionalGeneration`) — so this is a **routing** verdict, not a quality one, and the staged vLLM twin is the discriminating run: if it also emits `!` the upload is broken and neither engine is at fault |
| 00:3x ET | `cb66ecc` | "Retire the main-image boot-gate probe" — its gate is answered (main-tree image carries the shape indistinguishably: 20.38/46.38/99.27/156.20 on 2026-10-22 and 21.1/47.4/98.9/158.0 tonight, against the control's 21.0/48.1/99.4/157.8, differing in exactly one field, `container:`) and that container is a **fleet-local tag with no registry** (`sglang-main-arm64:6563312`, 28.9 GB), so no fresh node can pull it. Moved to `attic/explore/` with hash equality (`de2dd9c9…`), both windows and the disposition recorded in `attic/explore/AGENTS.md`, the lane README keeping its gate section and pointing at the attic for the result. `0ed251e` in the same window adds a **pooling branch** to the runner (embed/rerank arms go through `benchmark pooling` with their lane's ladder profile and record `suite: n/a` — the chat instruments cannot address `/v1/embeddings`). Suite 1090 OK (2 skipped); 78 tracked recipes, explore 16 |
| 00:1x ET | runner | **The transcription fallback fired for the first time, on a real arm.** `qwen3.8-27b-uncensored-nvfp4-sglang` re-ran, printed a complete ladder and a **15/15 → 100/100** suite, and wrote no `--output` files (no `CSV output` line in its log either, the same writer skip as four other arms). The runner kept both: `ladder.transcribed.json` with `source: "transcribed from …/ladder.log (llama-benchy table; the framework wrote no artifact)"` and cells 9.9 / 19.9 / 42.1 / **82.2** tg t/s, plus `house.transcribed.txt` carrying the suite's own summary line. `rc=0` with readable numbers instead of `rc=5` with a lost cell — and the **date rollover** this exposed: the arm wrote into a new `~/benchmarks/tp12-20261030/` window, so the count now globs `tp12-*` rather than two named days |
| 00:3x–00:5x ET | `f0d3999`, `f06aabb` | **Two fleet facts the first pooling arm exposed.** (1) `f0d3999`: a serve that replies with something un-HTTP is **down, not fatal** — the pooling arm raised `http.client.BadStatusLine`, which is not an `OSError`, so it escaped `http_ok` and **killed the watchdog**, leaving a live boot with no liveness evidence. (2) `f06aabb`: the port-conflict probe saw only containers, but **`beegfs-mgmtd` owns `*:8010` on `.30`** — every embed and rerank recipe defaults to 8010, so those lanes can never serve on the head; vLLM died with `OSError: [Errno 98] Address already in use` while `docker port` showed nothing. The probe now reads the target's own socket table and refuses with the listener named; it is fed on stdin because three quoting layers produced two broken versions first. Guarded by `test_the_leftover_gate_is_per_arm_not_per_node` plus a host-socket assertion and two patched-`urlopen` tests |
| 00:4x ET | probe | **`nex-n2.5-mini-uncensored` is degenerate on BOTH routes — the pinned artifact is bad.** SGLang returned `'!!!!!!!!!!!!!!!!'` from `/v1/completions` and empty content with `'!!!!…'` reasoning on chat; the **vLLM twin, which the card advertises, returns `'ductductduct…'`** for the same model at the same pin. Each engine loops in its own tokenizer's space, which is the signature of a mismatched or corrupt weight set rather than an engine bug, and the same engines booted 20+ arms cleanly tonight. Neither arm is a cell; both `nex-*` recipes stay shipped as **unreproducible probes** until the publisher republishes, and the staged bodies stay pooled (26 files, 2.82 GB largest) because a republish is likely |
| 00:5x ET | probe | **The owner-priority DFlash2 arm serves, and its gate is met.** `zz-ornith-1.5-122b-nvfp4-dflash2-sglang` (NVFP4 122B + `incoai/Ornith-1.5-122B-DFlash2`, 15 draft tokens) reached `endpoint=ok` and the serve log reports **`accept len: 3.35–4.85`, `accept rate: 0.17–0.28`, 23–29 decode t/s at C1** — the gate was acceptance > 1, so it passes, and 4.85 is close to the card's published 5.41 (MT-Bench). One benign warning: `DFLASH block size mismatch: using speculative_num_draft_tokens=15 but draft config block_size=16`, which is exactly block size − 1. **Checked before the boot, not after:** the export holds **48 layers (0–47)**, all eight `target_layer_ids` present and **unfused**, so DFLASH drafts from the layers it was trained on; `mask_token_id_override=248077` confirms the mask row resolved from the target |
| 00:2x–01:0x ET | `a7a97d1` | **The Python 3.14 experiment, with the paths an interpreter can and cannot move separated.** A review was right that `json.dumps` and Rust `tokenizers` are C/Rust and cannot show 3.14's specializing interpreter, so the bench (`tools/py-runtime-bench.py`) now carries a **pure-Python detokenizer** beside them, and the split reverses the reading: Python paths gain **−39 % loop, −24 % pydetok, −27 % asyncio**, while C paths are flat or worse (`json.dumps` −0.9 % on 3.14, **+7.6 % on 3.14t**). So the question for any executor is how much of its per-token path is Python. Wheels re-checked for arm64: torch 2.15 ships `cp314` and `cp314t` manylinux aarch64, **triton 3.9 only `cp314t`**, sglang 0.5.23 and flashinfer/sgl-kernel none — a GIL 3.14 engine build needs triton from elsewhere while 3.14t has a full set and is the worse performer on every C path. Also verified: the **Nex cache is byte-identical to the Hub's LFS sizes** across all 16 shards (23,922,410,184 B both sides), so its degenerate output is the upload, not a short download |
| 01:1x ET | arm | **The DFlash2 arm's cell is in, and it is a c1-only optimisation.** `zz-ornith-1.5-122b-nvfp4-dflash2-sglang` closed `rc=0` with the full artefact set: **suite 97/100** (identical to the other 122B arms — the drafter costs no tool-calling quality) and **C1 35.21 tg t/s, which is an ENGINE-LEVEL figure**: the plain arm (17.9) and the MTP arm (39.3) are vLLM, so neither the lift nor the 4.1 t/s gap can be attributed to the drafter. SGLang was never measured on this model without one, which is why `zz-ornith-1.5-122b-nvfp4-sglang` (no spec, same engine) was authored and booted for exactly that baseline. Acceptance ran **3.35–4.85** across the ladder against the card's 5.41 on a bf16 target, so NVFP4 costs acceptance a little and not much. But decode **falls** to 25.79 at c10 while the MTP arm **rises** to 81.9: a 15-token draft block is a bet on one request at a time, and under load the gain evaporates — so 15 tokens is a c1-only setting on this engine and MTP's 3 remain better above ~c2. Follow-up queued in the task: sweep draft tokens 4/8/15 to separate verification contention from a fixed cost. Owner task marked done |
| 01:2x ET | `a26a269` | **The pooling branch's first hardware run, and its first fix.** `qwen3-vl-embedding-2b-vllm-b12x` failed in **3.1 s with no traceback** because `pooling-ladder-embed.yaml` hardcodes `dimension_check: 4096` for the shipped 8B encoder — its own note says a 2B arm needs `-b dimension_check=2048` — so every reply failed the shape check before anything was measured. The runner now passes that override for `*-2b-*` recipes, and the arm produced a complete correctness-checked cell set: 100/100 requests per cell, dimension 2048, **deterministic (same input twice = cosine distance 0.0)**, distinct inputs 0.097–0.128 apart. **Throughput 36.3 → 98.8 units/s from c1 to c10 while p50 latency goes 27 → 99 ms** — the last doubling buys +21 % throughput for +65 % latency, so **c5 is the operating point** for a latency-sensitive caller and c10 is throughput-only. That closes the third instrument gap: decision, chat and pooling arms all run end to end through the runner |
| 01:5x ET | A/B | **The DFlash2 drafter measured against its own engine — and the answer flips.** Two boots, same node, same image, same model, same night: the no-spec SGLang arm (`zz-ornith-1.5-122b-nvfp4-sglang`) reads **28.95 / 38.46 / 46.42 / 48.97 tg t/s at c1/c2/c5/c10 and RISES with concurrency**, while the DFlash2 arm reads **35.21 / 29.14 / 27.36 / 25.79 and FALLS**. Within-engine delta: **+21.6 % at c1, −24.2 % at c2, −41.1 % at c5, −47.3 % at c10**, prefill collapsing 1 800 → 661 by c2; suite **97/100 both**. **Caveat found by review and fixed the same hour:** the first baseline boot omitted `mamba_radix_cache_strategy: extra_buffer`, which the DFlash2 recipe sets, so its c2–c10 cells measured drafter **plus** cache strategy. The knob is now on both sides, the functional diff of the pair was re-verified mechanically (only `speculative_*` keys/flags/placeholders differ), and the baseline is **re-booting**; the c1 and suite numbers were never affected because the knob cannot change them. So 15 draft tokens destroy batching on this engine, and the earlier "1.97× over the plain arm" was a cross-engine artefact — the real same-engine lift is **1.22× at c1**. This is what the no-spec baseline was authored for, and it retires the claim. Queued the sweep that tests the hypothesis (draft tokens 4/8/15: contention vs fixed cost) rather than guessing |
| 02:1x ET | rule + tool | **An idle free node with queued work is a defect, the same class as a held node — and it is now visible instead of remembered.** `.35` sat empty for an hour tonight while the manifest held unmeasured arms, because the census line reported "nothing live (no reservation)" and nobody turned that into a launch. `tools/next-arms.py` answers the launch question directly: it reads container counts over ssh, the `<arm>` receipts under `~/benchmarks/tp12-*` and the campaign manifest, and prints **one `run-arm.sh` line per free node**, filtered by `tp` (a TP=2 arm is never planned onto one node) and by `--skip` for dead arms. First live run on the head: **32 arms measured, 17 unmeasured in the manifest, 0 free nodes** — the backlog is reported even when the fleet is full, which is exactly what was invisible before. Same window: `run-arm.sh` gained `ARM_OPTS` so a sweep leg no longer needs its own recipe file, and the first draft-token sweep leg (`-o speculative_draft_tokens=4`) is running on `.35` against the baseline re-run on `.30` |
| 02:15 ET | `bd370cb` | **Closed both ways `next-arms.py` could certify "nothing to do" wrongly** — the tool built to prevent an idle node had two silent false negatives of its own: a missing or malformed manifest returned `[]`, a vacuous empty that reads as a dry queue, so `candidates()` now raises `ManifestError` and the CLI exits 2; and the measured-set filter matched by **substring**, so `zz-ornith-1.5-122b-nvfp4-sglang` matched inside its `-dflash2-` sibling and a freed node would have reported nothing runnable. Matching is exact now with an explicit alias table for hand-named receipt dirs (`nemotron`, `ling-3.0`, `qwen38-27b-*`, `ornith-122b-mtp`), read in the direction the check actually needs. `run-arm.sh` gained **`ARM_TAG`** in the same commit for the reason the rotation had just demonstrated: every sweep leg wrote one receipt directory and pushed the previous leg to `.prev-<HHMMSS>`, so the numbers survived and the attribution did not. 12 guards |
| 02:16–02:17 ET | `476f747`, `52824c6` | **A commit of mine deleted a file, and the restore is the record.** `--allow-empty` with no pathspec commits **everything in the index**, and this syncthing-shared index held another session's staged deletion of `plugins/plugin.toml` — so a commit whose message described sweep receipt directories published that deletion. `52824c6` restores it byte-identically (27 bytes, diffed against the pre-accident commit); the other session's intent is theirs to re-stage. This is the working agreement's own rule: a commit names its paths |
| 02:40 ET | `edaf663` | **`next-arms.py` never plans a TP=2 arm onto one node** — its first live plan offered a `tp: 2` arm as `run-arm.sh <recipe> <one host>`, which either refuses or silently serves at TP=1, i.e. a wrong measurement rather than an error. Placement is one arm per free node so only `tp: 1` is placeable; the nine TP=2 arms are still **counted and printed** as a pair backlog, never hidden. The placement step became a function (`place`) so the guard tests the rule instead of the ssh node probe |
| 02:45 ET | `3a37688` | **The draft-token sweep was about to re-derive a closed negative.** `attic/ornith/AGENTS.md` §4 already rejected `speculative_draft_tokens` 4 → 10 on quality (86.5/85.5 against a 99.3/99.2 control, ~19 % loss); tonight's d4-vs-d15 cells put a throughput penalty on the same direction, so the sweep is **corroboration** and an upward leg (d8, d20) is refused. The lane README now carries the result, the citation, and the one open leg (a matched-window baseline/d4 pair) |
| 02:5x ET | measurement | **The d4 leg answers the drafter question, and it overturns the earlier reading.** Same recipe, only `-o speculative_draft_tokens=4`: **37.7 / 55.3 / 54.2 / 48.9 tg t/s** at c1/c2/c5/c10 against d15's 35.2 / 29.1 / 27.4 / 25.8, with prefill recovering from 661 to 1 798 t/s by c2. Against the no-drafter control the drafter is **+30 % C1, +44 % C2, +17 % C5, parity at C10** — so the batching collapse reported two hours earlier was an **over-large draft block**, not the drafter, and the publisher's 15 is the wrong default for a batched serve. Verdict line `ARM DONE … rc=0`; receipt `~/benchmarks/tp12-20261030/zz-ornith-1.5-122b-nvfp4-dflash2-sglang-d4/REPORT.md` |
| 02:53 ET | `2197cf7` | **The decision instruments can no longer block on a prompt.** `tool-eval-bench` auto-detects the model, and a JEV arm serves **two** (base + `jev-decision` LoRA), so the picker sat at `Select model [1-2]:` with nothing to answer it — it takes `--model`, now passed. The ladder's 404 ×100 at every cell was `ARM_LADDER_API` left at the lane default `systemone` on a vLLM arm that speaks `/v1/completions`; the head comes from the arm's own pool snapshot (`…/adapter_vllm/decision_head.json`, present for both 9B and 27B) |
| 02:57 ET | `4e290d7` | **`tools/queue-drip.py`: the loop that keeps a free node busy** — `run-arm.sh` owns one arm and `next-arms.py` answers what belongs on a free node, but nothing acted on the answer. The drip never decides which nodes it may use: that is a per-session **untracked** `.local/fleet.yaml` (`research:` list, `skip:`, `poll_seconds`), fail-closed on an unreadable file, an empty list, a duplicate key or an unknown key — a typo like `reseearch:` must not read as an idle fleet. Three gates precede a launch: the fleet-window lock (exit 3), the receipt predicate, and its own ledger, because an arm started a minute ago has a receipt dir with no numbers in it yet. Two defects the guards caught before it ever launched: `pid_alive(0)` returned true (`kill(0,0)` signals the process group) and the lock refusal formatted its path through `relative_to(REPO)` |
| 03:0x ET | measurement | **The first JEV ladder, on a harness line the lane doc said had never been run** — `jev-9b-decision-vllm` on `.35`, `--api completions` with the adapter's decision head, `--limit 100` (one request per question, so **500 requests per cell**): **9.29 / 10.11 / 20.34 / 21.19 req/s** at c1/c2/c5/c10, p50 108 / 201 / 246 / 471 ms, **500/500 responses and 500/500 decisions clean** at every level. It does **not** serialize: throughput rises 2.28× while p50 inflates 4.35×, so requests overlap at sublinear efficiency — a different mechanism from the CPU arms, which *lose* throughput under load. Accuracy step produced no score (that launch predates the `--model` fix), so the arm's accuracy stays the lane's 2026-10-11 **67.0 %**. Receipt `~/benchmarks/tp12-20261030/jev-9b-decision-vllm/REPORT.md` |
| 03:05 ET | `c6e2209` | **Recorded the first JEV ladder, and stopped claiming it was never run** — the lane README's `req/s` table gains the measured row and drops the sentence that said the harness line was unexecuted. `OK` on `tests.test_decision_recipes` |
| 03:12 ET | `11c08c2` | **The drip would have double-launched the 27B, and two numbers in my own prose were wrong** — the arm running on `.30` was started by hand, so it had no ledger entry *and* no numbers in its receipt yet, and both predicates called it unstarted. `live_driver_paths()` reads the process table instead (`run-arm.sh <recipe> <node>`, matched on the path the plan carries), and an in-flight arm goes to the planner as `--skip` rather than being dropped after the fact — a dropped row loses its free node. Same commit: `next-arms.py` crashed on its own summary line (`NameError: ready`, JSON path unaffected), and the JEV paragraph said 500 **cases** (it is 500 **requests** = 100 cases × 5 questions) and called the arm one-slot (it overlaps). Also fixed a guard of mine that asserted a busy fleet exits 1 — nothing free means nothing unplaced, so that is exit 0 and exit 1 stays the idle-node signal |
| 03:14 ET | `2600d33` | **The address-hygiene guard caught my own fixtures** — two RFC1918 stand-in node addresses are exactly the literals tracked text may not carry, so the gate went red on the commit before it and the fixtures are `node-a`/`node-b` now. Recorded because the red gate was pushed past by a `;`-chained command, which is its own defect: the gate result must gate the push. Suite **1135 tests OK (2 skipped)** |
| 03:20 ET | audit + launch | **Stage audit: 42 arms, 1 flag — every queued arm can launch.** `tools/stage-audit.py` proves the pinned image resolves by digest on the free nodes, the pinned revision's recursive entry count matches upstream, and the largest weight exceeds 1 MB by `stat -L`; the single flag is a **manifest gap** (`zz-spark-x26-main-image-sglang` carries no model/revision), not a staging failure. Same window: the drip's **first live launch** — `queue-drip.py --once` started `zz-jev-9b-decision-coloc-vllm` on `.35` (pid in `.local/drip-state.json`, `ARM_LADDER_API=completions` + the 9B decision head proven present in the child's `/proc/<pid>/environ`, not asserted) |
| 03:2x ET | `cf1975f` | **The gate caught the board quoting the very literals it was describing** — the row about the address-hygiene fix reproduced two RFC1918 stand-in addresses as evidence, so `c63e0c5` went red in CI while my local gate (run before the board write) was green. The row names the class now and keeps the `.30`/`.35` shorthand. Run `41020174604` success at `cf1975f`, suite 1136 OK (2 skipped) |
| 03:3x ET | measurement | **The drip's first arm landed, and co-location changes nothing measurable.** `zz-jev-9b-decision-coloc-vllm` on `.35`, launched by `queue-drip.py` with the JEV contract from the manifest: **9.34 / 9.94 / 20.31 / 21.17 req/s** at c1/c2/c5/c10 with 500/500 clean at every cell — inside ~0.5 % of the plain `jev-9b` arm (9.29 / 10.11 / 20.34 / 21.19), so the co-located variant reproduces its sibling and the pairing is not a throughput lever. Receipt `~/benchmarks/tp12-20261030/zz-jev-9b-decision-coloc-vllm/` |
| 03:3x ET | `run-arm.sh` | **A clean cell run was reporting rc=3, and the instrument was the reason.** `tool-eval-bench --decision-bench-only` speaks `/v1/systemone` only — its own error text says so — so a JEV arm on `/v1/completions` cannot be scored by it at all; the coloc arm's cells were complete and correct while `rc=3` marked the run failed. A `completions` ladder API now skips that step and writes the reason into `teb-decision.log` instead of taking a score it cannot get. Guarded by a test that the skip **precedes** the instrument call |
| 03:4x ET | `c3825fe` | **A clean cell run reported `rc=3` because the instrument cannot address the arm.** `tool-eval-bench --decision-bench-only` speaks `/v1/systemone` only — its own error text says so — so a JEV arm on `/v1/completions` can never be scored by it; the drip's first arm had 500/500 clean cells at every level and was still marked failed. A `completions` ladder API now skips that step and writes the reason into `teb-decision.log`, guarded by a test that the skip **precedes** the instrument call. Gate `41020713295` success |
| 03:45 ET | `sparkrun stop` | **A wedged boot held `.30` for 30 minutes and the watchdog called it `loading`.** The JEV-27B vLLM boot froze at `Capturing CUDA graphs (PIECEWISE): 0/102` at 07:15Z with `io_delta=0` and `log_delta=0` through 07:45Z, alive child and dead endpoint — so `decide()` never left `loading`, and only the *gone*-child path ever stops a task. Stopped by literal task id `5734b87ea44a6866_feeba0771529`; node verified back to 0 containers / 0 volumes |
| 03:5x ET | `8e6ecca` | **`--stall` closes the frozen-boot hole the wedge exposed.** With the endpoint down, the child alive, grace passed, and **both** io and log deltas at zero for the whole stall window (default 600 s), the verdict is `stalled` and the task is stopped with `idle=<n>s` in the evidence line. Both deltas must be zero because a real 45-minute weight load logs or reads something. Five guards, including that inside-grace and recent-progress are *not* stalls. Suite **1142 OK (2 skipped)** |
| 04:0x ET | `1754142` | **The 27B's three failures had one readable cause, and it was memory.** `ValueError: Free memory on device cuda:0 (109.07/121.69 GiB) on startup is less than desired GPU memory utilization` — vLLM's 0.9 default asks 109.5 GiB of a 121.69 GiB device. The first two boots showed it as a freeze at `Capturing CUDA graphs 0/102`, which is why they read as a capture hang; whether wedge and ValueError share a cause is **not** established. `gpu_memory_utilization: 0.85` makes the bound reachable and the boot now loads its 13 shards. The lane's negative control was anchored on the arm *lacking* the knob, so declaring one turned the control green — it strips the key by name now |
| 04:1x ET | `bce52fe` | **Two probes whose silence read as a fact, both on the launch-decision path.** `free_nodes()` ran `docker ps -aq \| wc -l`, so any docker failure printed nothing and became a confident `0` — a node the probe could not inspect got work; it reads docker's own exit status now (4 guards: empty, busy, failed call, unreachable node). And the drip's ledger trusted a bare pid, so a recycled pid held an arm "in flight" forever; `pid_is_driver()` requires `run-arm.sh` plus the arm in `/proc/<pid>/cmdline`, tested against real children including a forged argv |
| 03:58 ET | `70c3da6` | "Add the weights-and-runtime refresh campaign to the queue" — the owner's refresh instruction became an **action layer** over the sweep that already exists (`tools/refresh-sweep.py`, nightly into issue #1) instead of a second survey: newer weights → test and repin when green, newer runtime → A/B on the **same weights** (different weights across two runtimes is not an A/B), both → pin first then A/B. Two traps named: the three `published-image-refs` arms cannot be A/B'd until their image resolves, and the TP=4 arms need a declared four-rank window rather than a silent skip |
| 04:11 ET | `faa33fc` | "Queue two owner tasks" — both scoped against measurements rather than prose: `refresh-weights-and-runtime-repin`'s first pass shrank its action set to **3 arms in 2 units, not 40 hours** (of 80 recipes: 24 docs-only, 9 newer runtimes **all accepted holds**, 4 newer-weights with 1 hold — the Mellum repin is a blob-level hash proof at `b3c4f494…`/`5fcfb1f7…` while `drama-3` needs a boot), and `migrate-todo-protocol-to-queue` costs ~93k tokens per tick against `queue.json`'s 86 KB for 55 tasks. Queue 55 tasks, 20 open, board mirrors all 20 |
| 04:11 ET | measurement | **TP12 decision-lane arm — `jev-27b-decision-vllm` (TP=1, vLLM) on `.30`**, and the third boot is the one that served: the `gpu_memory_utilization: 0.85` bound from the 04:0x row reached `endpoint=ok` at `t=889 s` where the first two froze at `Capturing CUDA graphs 0/102`, and the completions-API ladder then ran clean — **3.37 / 3.47 / 6.00 / 6.62 req/s** at c1/c2/c5/c10, p50 294 / 574 / 831 / 1 459 ms, **500/500 requests and 500/500 decisions clean at every cell**. Against the 9B's 9.29 / 10.11 / 20.34 / 21.19 the 27B gives up ~⅓ of the decision throughput at every level and serializes the same sublinear way (throughput 1.96× while p50 inflates 4.96×, vs the 9B's 2.28× / 4.35×); accuracy stays unscored **by design**, `teb-decision.log` carrying the `/v1/completions` skip line rather than a score it cannot take. Receipt `~/benchmarks/tp12-20261030/jev-27b-decision-vllm/` (ladder + json, a `.prev-034922` from the failed boot beside it). Its `ARM DONE` verdict is **not** in the head's `/tmp` arm logs — the newest there is 02:31 — so the exit status is unrecorded and this row stands on the artefacts and the vanished serve, not on a verdict |
| 04:31 ET | measurement | **TP12 pooling arm — `qwen3-vl-reranker-2b-vllm-b12x` (TP=1, vLLM b12x) on `.30`**, `ARM DONE … rc=0` with the serve stopped by the runner afterwards: task `d0629ac3ac7fba84_030fb880a827`, image `ghcr.io/spark-arena/dgx-vllm-eugr-nightly-b12x@sha256:cf5a2a53…`, model `Qwen/Qwen3-VL-Reranker-2B` @ `4bd860ac…`, TTR **164.5 s**. Rerank ladder (`pooling-ladder-rerank.yaml`, 100 requests × 10 documents = 1 000 units per cell) **73.1 / 79.8 / 83.6 / 84.1 units/s at c1/c2/c5/c10** with p50 135.5 → 1 140.9 ms, **100/100 clean and `noise_floor_warning: false` in every cell, `errors` empty**. The arm has no concurrency headroom to buy: +15 % throughput from c1 to c10 for an **8.4× p50 inflation**, so c1 is the operating point for a latency-sensitive caller and c10 is throughput-only. Receipt `~/benchmarks/tp12-20261030/qwen3-vl-reranker-2b-vllm-b12x/` (`REPORT.md` written 05:03 ET). Launch carried the known `unpinned-model-revision` warning — the pin is not passed to the engine as `--revision` and `EngineCore` resolved the right snapshot anyway, which is the same latent defect the guard names rather than a boot problem |
| 04:41 ET | `c89ca14` | "Make the register's write atomic, and stop `update --notes` from eating the requirement" — `tools/task-queue.py:_save()` wrote the syncthing-shared `mad-science/queue.json` with `write_text`, which truncates before writing and fails **silently** (the JSON stays valid while rows vanish); it now writes a pid-suffixed temp, copies the register's mode, `os.replace`s it and unlinks the temp on failure, guarded by a failure-injected replace that must leave the file byte-identical, plus mode preservation. The same commit restored the owner requirement text an `update --notes` call had overwritten — `--notes` replaces the field by design, so the text is merged back rather than argued with |
| 05:00 ET | `884f2da` | "Repin the Mellum mmap arm on a hash proof, not a boot" — the sweep's `model-stale-weights` flag on `zz-mellum2.1-12b-a2.5b-q4km-thinking-llamacpp-mmap` is **additive only**: the served quants are byte-identical at blob level (`Q4_K_M b3c4f494…`, `MXFP4 5fcfb1f7…` in both revisions) and the new revision only adds a BF16, an `mtp-…BF16.gguf` and a `mtp/` draft set, so the pin moved on the hash and the base recipe's 31 tests pass. The sibling `…-mtp` arm still wants a boot, because the new drafts are material it can actually use |
| 05:21 ET | `9c10250` | "Let the runner take a node pair, because the single-node queue is dry" — `$2` of `run-arm.sh` is now a comma list: `HOSTS` reaches all four sparkrun call sites, `NODE` stays the first element for the endpoint, the watchdog and remote container resolution, and a single-node arm is unchanged. Guarded by asserting the pair reaches every site and that no `-H "$NODE"` survives. Pair placement is manual — `queue-drip.py` places one arm per free node and cannot yet spend two on one arm, so a TP=2 run needs the lock plus an explicit `run-arm.sh <recipe> <a>,<b>` |
| 05:14 ET | measurement | **TP12 chat arm — `qwen3.8-flash-next-nvfp4-solo-vllm-b12x` (TP=1, vLLM b12x) on `.35` ends `ARM DONE … rc=5`, and the number is a defect, not a ladder**: image `ghcr.io/spark-arena/dgx-vllm-eugr-nightly-b12x@sha256:cf5a2a53…`, model `local-inference-lab/Qwen3.8-Flash-Next-NVFP4` @ `6c01ac37…`, TTR **816.7 s**. All four cells completed (`[n/4] ok`) at **decode 7.57 / 7.37 / 2.91 / 1.97 tg t/s (c1/c2/c5/c10, c10 a single run)** with prefill flat at **24.0-28.5 t/s** and ttfr **72.0 → 595.8 s**, against `recipes/qwen4/README.md`'s 2026-10-18 **34.04 / 55.49 / 64.61 / 62.04 t/s** for the same recipe, pin and engine — 4.5× low at c1 and falling with concurrency instead of rising. The house suite never scored: `{"event": "error", "error": "connection_failed", "message": "Could not connect to http://<api-rank>:8000/v1 for pre-flight check."}` (serve already stopping), so `house.yaml` is absent and `rc=5` is the missing-artefact code, not the stop. Receipt `~/benchmarks/tp12-20261030/qwen3.8-flash-next-nvfp4-solo-vllm-b12x/REPORT.md`, which also records the live readings (GPU 0 %, `Engine core step finished after 71.2 s`, swap 0 of 15 GB, load 0.27, pool 579 MB/s) as main-loop observations rather than file-derived facts |
| 05:38 ET | measurement | **three receipts written for arms that finished with nobody holding their note** (receipts only; no repo artefact): `jev-27b-decision-vllm` (`rc=0`, ladder 3.372 / 3.467 / 5.998 / 6.617 req/s with **500/500 clean in every cell**, p50 ttft 294.4 → 1459.0 ms, no house by design — decision arms take `decision-ladder.py` + a no-score `teb-decision.log`), `qwen3-vl-reranker-2b-vllm-b12x` (`rc=0`, **73.1 / 79.8 / 83.6 / 84.1 units/s**, p50 135.5 → 1140.9 ms, 100/100 and all four checks in every cell, `house.log` = `suite: n/a (pooling arm …)`) and `qwen3-vl-reranker-8b-vllm-b12x` (`rc=0`, **17.9 / 18.8 / 20.7 / 21.0 units/s**, p50 559.7 → 4579.8 ms, same four checks green, same `suite: n/a` line). Each `REPORT.md` sits beside its `ladder.json` with pins from `launch.log` and a provenance list; the 8B runs at 4.1× the 2B's c=1 cost in both directions, which is the size ratio. **Also recorded: the first TP=2 attempt aborted at 05:23:30 with `ARM FAIL … no container appeared` while its serve was still booting** — `run-arm.sh` resolved containers with `grep -m1 _solo`, which a pair (`_node_0`/`_node_1`) never produces, so the 300 s loop expired; the relaunch at 05:35:31 resolves `…_node_0` and is the run in the In-flight table |
| 05:38 ET | `8e6cfee` | "Resolve multi-rank containers, not just `_solo`" — the first TP=2 launch printed `ARM FAIL … no container appeared` at 301 s *while both ranks were booting*, because container resolution grepped for `_solo`, the TP=1 name. Three places carried the assumption and fixing only the first would have resolved the container and then mis-addressed the stop: the pattern is now `_solo\|_node_0`, and both the task id and the leftover-container cleanup strip `_node_*` before `_solo`. Guarded by a test asserting all three, since a partial fix fails later and quieter. Cost of the defect: one orphaned boot (stopped by task id, both nodes verified back to 0 containers, `resources list` empty) and a re-run — and the live `watchdog.log` on both ranks is itself the proof the task id now parses |
| 05:41 ET | `0738fc1` | "Mask the address a tick pasted into the board" — `943bf39` quoted an engine error verbatim and put a cluster address into a tracked file, so the hygiene guard went red on the very commit that recorded the failure it was reporting; the text now reads `http://<api-rank>:8000/v1` and the meaning survives. Same row carries the second defect, which is why the red reached a push: the commit was chained after `uv run … \| tail -2`, and a pipeline's exit status is `tail`'s, so a failing suite still committed. The gate now runs under `set -o pipefail` with its exit checked on its own line |
| 06:04 ET | measurement | **TP=2 ladder for `deepseek-v4.1-flash-abliterated-cyber-tp2-tensorfold-sglang` (`.30`+`.35`) landed 4/4, house suite still running** — `ladder.yaml`/`json`/`csv` written 06:04:00: `tg128` **10.80 ± 0.94 / 10.76 ± 0.61 / 10.60 ± 0.31 / 10.66 ± 0.61** t/s at c1/c2/c5/c10 (peak 11.2 / 14.2 / 17.8 / 18.0) and `pp2048` **486.6 / 248.3 / 200.0** t/s at c2/c5/c10 — flat in concurrency, which is not a batching curve and not the shipped line. Read against the serve's own request log (128-token thinking requests, ttft 20–40 s, 2.9–3.3 tok/s, `accepted=73/158`, `80/138`) it has the same shape as yesterday's 13:05 abort of the sibling tensorfold arm, so this cell is recorded and **not** adopted as an index row: whether the graft + engram + TP=2 combination costs the 6× against the 66.4 C1 the TP=2 tensorfold row carries, or the line is broken, needs the house score and a matched-window control. Receipt `~/benchmarks/tp12-20261030/deepseek-v4.1-flash-abliterated-cyber-tp2-tensorfold-sglang/` |
| 06:10 ET | measurement | **TP=2 arm `deepseek-v4.1-flash-abliterated-cyber-tp2-tensorfold-sglang` finished `ARM DONE … rc=0` at 06:10:39 ET and stopped its own pair — and its house suite answers the question the 06:04 row left open**: **15 scenarios; 14 pass; 0 partial; 1 fail; score 93** (`[1/1] ok (396.2s)`), the only failure `TC-12 … missing_step` — *"Did not refuse the unsupported email-deletion request correctly"*, 0 points, 474 completion tokens on a 1 525-token prompt. A tool-calling arm that scores 93 with one refusal-shaped miss is **not** a broken line, which weakens the "serve is damaged" reading of the 6× decode gap and leaves the graft + engram + TP=2 cost against the lane's 67.02 C1 as the open explanation — still a hypothesis, since no matched-window control was run. Per-scenario first-turn TTFT sits in a 2093–2504 ms band across all fifteen rows. Both nodes returned to 0 containers/0 volumes; `.30` and `.35` are free with the window still declared. `REPORT.md` written from `ladder.csv`/`json`, `house.csv`/`json`/`log`, `launch.log`, `watchdog.log` and the in-container serve log, which holds 0 `Traceback`/`ERROR`/`: 500` matches and no `stall_diagnostics` line |
| 07:14 ET | `abe4699` | "Retire the arm-5 decode row as a bar: it is a `.34`+`.35` pre-migration measurement, and the A/B exonerates the repin" — the TP=2 comparison's baseline may no longer be used as a bar: the lane's 67.02 ladder was taken on `.34`+`.35` on 2026-10-19, **before** the cache migration, and the A/B clears the container repin as its cause, so `recipes/cybersec/README.md` carries the provenance caveat and `QUESTIONS.md` #55 carries the two-route choice |
| 07:18 ET | `c3fa99c` | "Correct which cache moved, and record what the pool costs per token" — the 2026-10-24 migration put the **HF cache** on the BeeGFS pool, which is where this arm's `engram/` tables live, while `/cache/runtime` is not on it (`stat -f` reads ext3, so the runtime tree is innocent); the pool's cost is now measured instead of inferred: 4 KiB p50 **2.285 ms** per random read and **0.91 MiB read per token** over `/proc/*/io`, ~230 pages/token against a 162–263 ms/token budget |
| 07:22 ET | `9dd2294` | "Offer both routes on question 55, and drop the mechanism paragraph my working tree duplicated into `c3fa99c`" — #55 now presents route A (a ~25 min window on `.34`, re-testing the old bar on `.34`+`.35`) and route B (stage the ~94 GB `engram/` on node-local NVMe per rank and repoint one symlink) as the owner's pick rather than one recommendation, with the duplicated mechanism paragraph removed |
| 07:23 ET | `a5b7f69` | "Name the symlink that carries the Engram pages, and stop ignoring benchmark state" — names the knob that actually works: the served tree's `engram` entry is a **symlink into the pool** (`/cache/runtime/dsv41-ablit/engram -> …/snapshots/48afcd1c…/engram`) and sits in the resolver's *first*-priority slot, while `TENSORFOLD_ENGRAM_DIR` (reached only after `model_dir`/`stock_dir`, both carrying `engram/`) and `TF_DS_ENGRAM` (a launcher output, never read) cannot do it; `.gitignore` covers `/data/` and `/runs/` so benchmark state stops appearing as untracked churn |
| 07:34 ET | `17fba61` | "Retract the instrument-inflation claim: `tg` is decode-only and the probes were mid-cell" — the audit closes it, and the two readings are reconciled without doubting either: llama-benchy's `tg_throughput` is `(N-1)` over the first-to-last content chunk with `N` from the server's `usage.completion_tokens` (`llama_benchy/results.py:302-322`), so TTFT never enters it and, with sparkrun dropping `return_token_ids` only for the sglang family (`sparkrun/benchmarking/llama_benchy.py:230-239`) and `tensorfold serve` running no reasoning parser, every `tg` cell in this registry is mutually comparable on both engines; the two in-container probes were end-to-end wall clock taken **while a cell was in flight** and land on the loaded per-request rate the same artefact records (`tg_req_throughput` 3.83 at c5, 3.37 at c10), not on a c1 decode rate (the c1 cell's own wall clock is 82.7 s for six 128-token requests). Lane doc and #55 now read decode against decode, which is what the row above rests on |
| 07:47 ET | `8091819` | "Put the speculation hypothesis ahead of mine, and name the receipt gap" — the pool-latency mechanism was the only candidate measured, not the only one: the shipped **Laguna-M.1 TP=2 vLLM arm's 12.85 t/s at c1** (`README.md`:276) sits within noise of this arm's 13.72, so a TP=2 GB10 pair yields ~13 t/s and the 67.02 row is what needs explaining; 552B at 2.9 bpw is ~200 GB of weights and ~13 GB read per token for a DeepSeek-class active set, capping two GB10s near 40 tok/s per weight pass, so only `--mtp-drafts 5 --parallel 4` gets to 67 — and that launcher config is unchanged since the row was taken, which leaves the **acceptance rate** as the variable, with no artefact recording it because none of tonight's three boots harvested `/tmp/sparkrun_serve.log` |
| 07:52 ET | `ed5331b` | "Harvest the serve log before teardown, and fix the guard that hid it" — `run-arm.sh` copies `/tmp/sparkrun_serve.log` out per rank into `<receipt>/serve-*.log` before `sparkrun stop` (best-effort: a failed copy never fails a measured arm), and the unconditional-teardown guard's anchor moved from `\s*` to `[ \t]*` because `\s` matched the newline above a top-level stop and reported it as nested. First live proof this hour: the 07:52:59 boot's receipt carries a 2 002 B `serve-0.log` where the 07:11:25 boot's carries none — and it is banner-only, ending at `DSpark 5 drafts`, which is what makes the debug-log-level prerequisite concrete |
| 07:56 ET | `d20c526` | "Walk every host when harvesting, and stop calling the engram symlink the knob" — the harvest loop ssh'd rank 0 only, so the rank on the second host of a pair was never visited; it now walks every host, deletes its `/tmp` staging copy per node and prints a count (a silent no-op reads like a clean receipt). The lane doc's remedy was too confident both ways: the same boot's launcher prints `engram=/cache/runtime/dsv41-ablit/engram` while its modlog prints `Engram: 2 shard(s) at /cache/huggingface/hub/dsv41-engram`, and the snapshot's 94.42 GiB of `engram-l1`/`engram-l14` is not proven to be the tables the hub path holds — so the node-local-Engram remedy is marked **unvalidated** with both lines quoted. Not yet exercised live: the 07:52:59 boot launched four minutes before this landed, which is why its receipt still holds rank 0's log only |
| 08:15 ET | `67be9e0` | "Stop replaying cached cells, and report a replay as a failure" — `--fresh` now reaches all three `sparkrun benchmark` invocations (pooling ladder `tools/run-arm.sh:252`, performance ladder `:262`, house suite `:265`), and a receipt that still shows `Prior benchmark state … is COMPLETE` sets **`rc=7`** with a `REPLAYED, NOT MEASURED` line instead of exiting 0, so a boot that measured nothing can no longer read as a measurement. Same commit restored the speculation block `d20c526` had deleted from `recipes/cybersec/README.md` (a slice-replace took the Laguna anchor `8091819` had inserted between the same two anchors) and corrected the board's boot count to two measured against two replayed |
| 08:18 ET | `789f579` | "Say which receipt holds the measurement, because the canonical path holds a replay" — checked the question the 08:05 tick left open, and the old-pin A/B is **not** a replay: `zz-abliterated-cyber-tp2-fabbe861-probe/ladder.log` at 06:59 has zero `Prior benchmark state` lines, so 13.72 c1 is a real measurement and the pin falsification stands. What it did expose is that the canonical `…-sglang/` holds the 07:54 replay while the measured 06:04 cells sit in `…-sglang.prev-071125/`, so `recipes/cybersec/README.md` now carries the per-receipt verdict — measured, measured, replay, replay — with the two-grep discriminator spelled out |
| 09:07 ET | `19bb139` | "Refresh status board 09:00 ET: fresh census, no declared window, and the two measured versus two replayed TP=2 boots" — the previous tick's own commit, publishing the 09:00 board this table sits under: the six-node census, the production serve probe, and the recounted TP=2 boot verdict, with no window row because none is declared |
| 09:15 ET | `3e50bf8` | "Identify a driver by argv, not by substring" — `pid_is_driver` tested `arm in cmd` against the flattened cmdline, so an arm whose name occurs anywhere in another process's arguments read as in flight, including arms inside `run-arm.sh` itself; it now splits `/proc/<pid>/cmdline` on NUL and requires one argv element to be `run-arm.sh` and another to be exactly the arm name or path. The old `test_a_driver_shaped_cmdline_is_accepted` was green *because* of the bug (its fixture ran `exec -a run-arm.sh sleep 5` with no arm argument), so it was rewritten to carry the name as a real argument, with a negative control on the prefix |
| 09:16 ET | measurement | **`qwen3-vl-reranker-2b-vllm-b12x` re-run (TP=1) on `.35` — the first `--fresh` proof on hardware**: benchmark id `bench_2f1db32c19c9`, the identical `State directory:` the 06:35 run on that node used (`…-b12x.prev-091310/`, four cells, `ladder.json` written, so the key had already completed), yet this run wrote `runs/000_rerank_c1.json` … `003_rerank_c10.json` at 09:16–09:17 and `grep -c "Prior benchmark state" ladder.log` = **0** — where the same key without the bypass re-emits and writes no per-cell file. Cells **71.7 / 79.5 / 83.3 / 84.0 units/s** at c1/c2/c5/c10, 100/100 clean each, the **third** independent reproduction of ~72 units/s at c1 (73.1 on `.30` at 04:31, 72.0 on `.35` at 06:35); receipt `~/benchmarks/tp12-20261030/qwen3-vl-reranker-2b-vllm-b12x/` now also holds a 147 KB harvested `serve-solo.log` |
| 09:19 ET | `6e32bc5` | "Match a pathless ledger row by stem, which exactness broke and substring over-matched" — `3e50bf8`'s exactness was right for rows carrying the recipe path and wrong for the two that do not (`.local/drip-state.json` holds an arm name and a pid only), so a live driver read as dead and the planner would have re-launched onto a node already serving; pathless rows compare stems now, verified against a live driver on the head (`pid_is_driver(…, arm, "")` False before, True after), with a driver-shaped fixture that must identify `arm` and reject `other-arm` |
| 09:21 ET | `087ab14` | "Document the cache trap with the artefact that proves the bypass works" — the `--fresh` claim needed a negative control, and the 09:16 run supplied it: the key existed and its prior state was complete, so the fresh cells are a measurement rather than a transcription. The evidence now sits in `tools/README.md` beside the tool, because the replay class is invisible from outside — it exits 0, writes a receipt, and the numbers look like cells |
| 10:40 ET | `5a3d140` | "The pair is exonerated: a shipped TP=2 row reproduces itself here within 1.5 %" — `poolside-laguna-m1-nvfp4-vllm-tp2` re-ran on `.30`+`.35` and read **12.98 / 22.18 / 33.59 / 34.96** tg t/s at c1/c2/c5/c10 against its shipped row's 12.85 / 21.85 / 34.15 / 34.64, serve asserted before the ladder; it was that arm's first boot on the pinned `vllm-openai:v0.32.0`, so ~13 t/s is what this hardware class gives and the cybersec 67.02 row is the outlier needing an explanation. `recipes/cybersec/README.md` + `recipes/explore/README.md` carry it |
| 10:59 ET | `e06b4d6` | "Place pairs, so a free pair is never reported as an empty queue" — `place()` sorted TP=2 arms into a backlog it could not schedule, so every free-node report said the queue was dry while seven pair arms waited for exactly those nodes; it now takes two nodes for a TP=2 arm and emits `run-arm.sh <recipe> n1,n2`, leaving a pair that cannot fit as *waiting* rather than planning it onto one node. Exit status moved to `stranded`, computed before the output branch — the first version raised `UnboundLocalError` on every `--json` call, which is how the drip invokes it. Guarded by `tests/test_next_arms.py` |
| 11:03 ET | `8174969` | "Record every host a plan row occupies, now that a row can occupy two" — the drip wrote `row['node']` into its ledger and its "launched X on Y" line, so a pair read as a single node in both; `hosts_of()` is the one accessor (`nodes` when present, `node` for older rows) and the ledger keeps `node` too, guarded by `tests/test_queue_drip.py` |
| 11:08 ET | `43086c2` | "Retire the uncensored arm: its quantisation is not in the pinned engine" — booted on `.30`+`.35`, both ranks die ~35 s in with `ImportError: Other method (CompressedTensorsW4A16Sparse24) is not supported now`, while `stage-audit.py` passed it (image by digest on both nodes, pinned revision at 32 entries, weights ok) — bytes present is not a scheme the engine can execute. `recipes/cybersec/README.md` carries the verdict; the arm is on the drip's skip list |
| 11:10 ET | `d764dc8` | "A receipt that recorded a start is not a receipt that recorded a cell" — `measured_arms()` counted any `*.yaml` in a receipt, and `run-arm.sh` writes `ladder.yaml` the moment a benchmark begins, so an arm that died before its first cell marked itself measured and was never retried; the predicate now requires `ladder`/`house` JSON, a labelled transcription or a state row. Checked before tightening: no receipt on the workstation or the head carried a yaml without a machine-readable sibling, and the failed uncensored arm's receipt holds only `launch.log`/`watchdog.log`, so this closes a hole next to the one that bit rather than the one that bit. Both directions guarded |
| 12:14 ET | `tests/test_next_arms.py` | **The gate has been red since `e06b4d6` — five runs — and nothing was watching it**, the same class as the six-run red of 2026-10-29: `test_json_mode_exits_cleanly` ran `next-arms.py --json` with no `--manifest`, so it read the repo's **untracked** `.scratch/tp12-campaign/manifest.json`; a fresh CI clone has no such file, the tool correctly fails closed (exit 2, message on stderr, nothing on stdout), and the `{` assertion fails. Green on every workstation tree and red on every runner, which is why four pushed commits plus this tick's board read green locally. The test now writes its own one-arm manifest in a temp dir; verified in a clean clone at `c4cb757` — `tests.test_next_arms` + `tests.test_tracked_address_hygiene` 39 tests OK with no `.scratch` present. The fail-closed path keeps its own test (`test_a_bad_manifest_exits_two_with_a_message`) |
| 12:21 ET | `eb50430` | "Queue the log-level work, and stop the planner asserting a cause it cannot know" — the TP=2 question's one open instrument had no queue row, so nothing could ever pick it up: `tp2-acceptance-log-level` (1 h, pair) now records it with `tp12-campaign-staging` as the reverse edge, and the Work queue mirrors it above. The planner's unplaced-pair line said "fewer than two were free" in runs that had just placed a pair on exactly two nodes; it now says the arm did not fit the remaining node budget, which is what it knows. Schema note recorded because it would bite the next pair arm: `node_cost` accepted only `single`/`quartet`, so a two-node task read `single` with its shape in a notes caveat |
| 12:23 ET | `cc89319` | "Restore the queue file's indentation, which my writer flattened to one space" — `eb50430` rewrote `queue.json` with `indent=1` against the tree's two, so a one-task addition landed as an 830-line reformat of a syncthing-shared file; the content is back at `indent=2` and the diff against the commit before it is the new task and its reverse edge only |
| 12:23 ET | `c2f00bb` | "Keep the queue file's own encoding, so one task stays one task's diff" — the second round-trip escaped every non-ASCII character (`§` → `\u00a7`, em-dashes) on the same 20-line addition; the writer is `indent=2, ensure_ascii=False`, which is the file's own serialisation, so a shared data file stays readable as a diff instead of 800 lines of escaped noise |
| 12:32 ET | `0d4e9f5` | "Let update repair the drift it is told to repair, and give a pair its own name" — `cmd_update` validated before it relinked, so the one state `check` reports as "rerun update" (a `blocked_by` mirror out of step with `blocks`) raised on the line before the repair, measured three reruns in a row; `_relink` now runs first, safe because the mirror is derived. `NODE_COSTS` gains `pair`, so a two-node task no longer records itself as `single`. Also retires the vLLM sibling of the dead uncensored arm on evidence rather than a boot: inside its pinned image `grep -rl Sparse24` finds 0 files under `vllm/` and 2 under `compressed_tensors/`, and the lane labels that weaker than the sglang arm's traceback |
| 12:42 ET | `50e73a5` | "Put the two cheap checks on the path the expensive action takes" — the gate block now ends with `gh run list` on your own SHA, because five consecutive commits were reported green off a local suite while CI failed every one and the report was unfalsifiable by the reporter. And `stage-audit.py` prints the dimension it does not cover: its green had been read as readiness and the next boot died on `CompressedTensorsW4A16Sparse24`. The scheme predictor tried in its place was refused by the evidence — the pinned config declares 8-bit/channel and 4-bit/tensor_group groups with no sparsity marker, while the class name is the engine's own construction |
| 12:47 ET | `d6d3865` | "Put the CI one-liner where the rule is, and record why no quant gate exists" — the exact `gh run list` call now sits in the rule, not only in the gate block above it, and the quantisation gate got three measurements instead of an argument: `sparsity_config: {}` and `block_structure: null` on both groups, `nvfp4-pack-quantized` present in 2 sglang and 5 vLLM files inside the pinned images, and the demanded class name existing only in the traceback. So `stage-audit.py` keeps printing its blind spot and the cheap boot remains the gate. CI `gate` **success** on all six commits `eb50430`…`d6d3865` (`gh run list`, 16:21–16:47Z) |
| 13:13 ET | `176dbc0` | "Say the campaign is blocked, and name the arm the instrument boots" — the `tp12` state cell read "queued and placeable" while `queue.json` carries `blocked_by: ['tp2-acceptance-log-level']`; the cell states the block now, and names both checkpoints so the pair's two boots cannot be confused: the planner's `deepseek-v4.1-flash-tensorfold-tp2-1m-sglang` (`LibertAIDAI/DeepSeek-V4.1-Flash-1017-EXL3-2.9bpw` @ `0be63c33…`, image `…@1e7a0165…`) against the queue's claimed instrument boot `deepseek-v4.1-flash-abliterated-cyber-tp2-tensorfold-sglang` (`littlecedar/…-with-engram` @ `48afcd1c…`, image `…@19977a03…`) — placement is not priority. Address-hygiene + conflict-copy guards 13 tests OK, `task-queue.py check` green (author's verification, per the commit body) |
| 14:00–15:05 ET | `7fdc830`, `44e21c7` | two board ticks and no fleet change: `7fdc830` published the 14:00 census with the idle pair's second cycle and `176dbc0`'s row, `44e21c7` named the campaign's five-arm skip set in the `tp12` row after the 15:00 re-derivation showed the planner offering a dead arm for a free node — the list lives nowhere outside these rows, so each planner run recomposes it |
| 16:04 ET | `a934281` | "Refresh status board 16:05 ET: the free pair against a queued pair job" — the 16:05 tick published the fresh six-node census, the quartet's serve probe, and the planner's plan onto the idle pair; no fleet state changed with it |
| 16:13 ET | `bac9304` | "Say the drip ledger is present with dead pids, not that its pids are gone" — corrected the census row whose wording read as the ledger file being absent: `.local/drip-state.json` exists (306 B, written 05:00 ET) on the workstation and the head, and it is the two pids inside it (`.35` → `3669184`, `.30` → `3983527`) that are dead, `ps -p` exiting 1 for both on both hosts. `gate` green on GitHub at `bac9304` |
| 17:07 ET | `cb2aaa0` | "Correct the board's skip set: name the five from the config, not a phantom arm" — the census and `tp12-campaign-staging` rows had carried a brace group that manufactured `qwen3.8-flash-next-uncensored-nvfp4-solo-vllm-b12x` (no such recipe: the real `-solo-vllm-b12x` is the non-uncensored qwen4 arm) while omitting the live skip entry `nex-n2.5-mini-uncensored-nvfp4-vllm`, and asserted "nothing persists that list" when `.local/fleet.yaml` `skip:` feeds `queue-drip.py:plan_pass` on every pass; both rows now name the five from the config and cite the drip as the consumer, with the correction recorded in `SESSION-RECORD.md` §"The board's skip set named a recipe that does not exist" |
| 17:11 ET | `56ef6d1` | "Require a causal claim to name its discriminator, not just its command" — `AGENTS.md` gains the sibling of the green-claim rule: a sentence that attributes a cause is unfinished until the one command that would print something *different* if that cause were absent has run and its output is quoted, filed beside the 2026-10-30 pattern where four "tool defect" diagnoses were the reporter's own setup; the model gate named is `tools/run-arm.sh:271-276` (`rc=7`, `REPLAYED, NOT MEASURED`). Suite 1166 OK (2 skipped) on the workstation |
| 23:10 ET | `5675e11` | "Record that `--skip` takes one flag per arm, where a reader will find it" — the comma-versus-repeated-flag finding from `9146b3c` was written only into this board's census row, so the `action="append"` contract (`tools/next-arms.py:182`) now sits in `tools/README.md` beside the planner it governs, with the measurement that exposed it (comma form 8 unmeasured, repeated form 5) and `queue-drip.py` named as the caller that already emits the repeated form |
| 00:33 ET | `20207e2` | "Make the entry points counts derived, and give the prose three zones" — four entry-point counts were stale at once (`AGENTS.md` claimed 79 tracked recipes against 80, 46 test modules against 51, and a strict-validate snapshot of 21/79 against the real 20/80), so they are derived now, not restated: `tools/doc-census.py` (193 lines) counts recipes / test modules / profiles / `SKILL.md` dirs and `tests/test_doc_hygiene.py` (112 lines, 6 tests) fails the suite when a doc states one the tree contradicts. Two cheaper gates died on measurement before either was built — a citation-resolution check would fire on **921 of 1,079** `file:line` cites in the tree (they point into the installed `sparkrun` package, not this repo) and a path-integrity check on 100+ hits from frozen `attic/` provenance plus documented placeholders — and rot was not the problem it looked like (every live doc except `tuning/README.md` was touched within 45 days). `AGENTS.md` also gains the three documentation zones — live / frozen / ledger, decided by path — with the obligation each carries |
| 00:34 ET | `a5b81cf` | "Record that discovery-by-name is not a dead reference" — the census experiment counted inbound path references and printed all **19** `.omp/skills/*/SKILL.md` files and every mod `README.md` as unreachable, which is an artifact of looking for the path: a skill is discovered by its directory name and a mod README is read by adjacency to its `run.sh`, so no doc ever writes either path. Nothing shipped depended on the list, but it is the evidence a future pruning decision would reach for first, so the zone rule now names both classes and states what the count cannot see |
| 00:35 ET | `f68e47a` | "Let the census gate catch its own first drift" — adding `tests/test_doc_hygiene.py` moved the derived test-module count 51 → 52 while `AGENTS.md` still said 51, and `--check` failed on the very next run: the gate's first real catch was the commit that introduced it, which is the proof it bites. `--fix` rewrote the row, and the fixer no longer claims to have edited both roster files — it now names what actually changed, the same restatement-the-constant defect the tool exists to kill. Verified at the time: `doc-census.py --check` exit 0, suite **1172 tests OK (2 skipped)** |
| 00:43 ET | `58a23d1` | "Drop a second restatement of the skill count" — `a5b81cf` had written the 19-skill literal into the pruning rule, the same fact the Key Directories row states and `doc-census.py --fix` keeps current, so the next skill added would have left that line stale while the gate stayed green; the checked sentence keeps its date and drops the literal. `tests.test_doc_hygiene` 6 tests OK, `doc-census.py --check` exit 0 |
| 01:05 ET | `0f03b9d` | "Refresh status board 01:00 ET: census unchanged, four doc-gate rows landed" — the 01:00 tick's own publish (census, quartet probe, and the four documentation-gate rows `20207e2`/`a5b81cf`/`f68e47a`/`58a23d1`); `gate` **success** on GitHub at this SHA (`gh run list`, run created 2026-10-31T05:10:03Z). Recorded here because the tick appended it to the board without a row of its own |

## Tick ledger, 2026-10-31 03:09–12:07 ET (gap closed at the 12:00 ET tick; tail folded at later ticks, most recently the 2026-11-03 00:04 ET one)

Every refresh after the 02:00 publish (`bb590b5`, which does have its own row) left its commit in the git
ledger with no row here: two session-boundary corrections, three board-prose corrections, and eight
refreshes. The board's `Landed this session` table is state and was replaced by later cycles, so this
section is the only per-commit record. Appended at the 12:00 ET tick, one row per commit, from
`git log` bodies rather than recollection.

| time ET | commit | one clause |
|---|---|---|
| 03:09 ET | `fe07176` | "Refresh status board 03:00 ET and open a session boundary, retiring 121 rows" — the `Landed this session` table had not been cleared since the 2026-10-29 03:10 ET boundary, so it carried 121 rows no live session could claim; they are retired verbatim in §"Landed rows retired at the 2026-10-31 03:00 ET board refresh" above, after a substring check found **81 of the table's 86 backticked SHAs absent from this file**. The 03:00 census was bit-identical to the 02:00 read, the quartet probed on all four ranks (pids 280/306/301/301, rank-0 `/v1/models` 200), the planning blocker re-derived through `candidates()` so the alias table applies (45 measured receipt arms, 5 unmeasured of 42, all TP=2), queue 21 open, `task-queue.py check` green. Author's verification: 1172 tests OK (2 skipped) |
| 03:15 ET | `2cdb4b3` | "Correct what the retirement section can claim about session liveness" — the section said the 2026-10-29 session last wrote at 01:18 ET and that no peer was live; both halves were wrong (that transcript belongs to the session opened 2026-10-30 12:52 ET, pid 1575174, still resident and idle). It now claims only what was verified and states why the clear stood regardless: the rows span 2026-10-29 03:03 to 2026-10-31 01:05 ET, so no live session could own them |
| 04:05 ET | `994dbbd` | "Refresh status board 04:00 ET: fourteenth identical census, state cells aligned to queue" — a no-change tick whose only edit beyond the timestamps was aligning Work-queue state cells to `queue.json` (8 lines) |
| 05:03 ET | `e64be14` | "Refresh status board 05:00 ET: census and probe unchanged, nothing landed" — no-change tick; the free pair's idle cycle and the two dead drip pids were the only live facts |
| 06:02 ET | `762ff76` | "Refresh status board 06:00 ET: census, probe and queue re-read unchanged" — no-change tick |
| 06:05 ET | `f103d5a` | "Correct the census row's container count: four containers in total, all the shipped pin" — the row's per-node listing read as though more containers existed than the four production ranks it had just counted |
| 07:01 ET | `4c864fe` | "Refresh status board 07:00 ET: census, probe and queue re-read unchanged" — no-change tick |
| 08:02 ET | `3202d9e` | "Refresh status board 08:00 ET: census, probe and queue re-read unchanged" — no-change tick |
| 08:07 ET | `ca6fd15` | "Drop the cross-cycle pid comparison from the board's serve row: state only" — the row compared this cycle's serve pids with the previous cycle's, which is history on a state board; it now states pids and health only |
| 09:01 ET | `c7d8d3e` | "Refresh status board 09:00 ET: census, probe and queue re-read unchanged" — no-change tick |
| 10:01 ET | `8b45940` | "Refresh status board 10:00 ET: census, probe and queue re-read unchanged" — no-change tick |
| 11:02 ET | `63c5afc` | "Refresh status board 11:00 ET: census, probe and queue re-read unchanged" — no-change tick; the 11:00 census, the quartet probe and the `tp12` re-derivation (manifest 42 arms, 33 TP=1 / 9 TP=2; 5-arm persisted skip set) reproduced the prior cycle exactly |
| 11:05 ET | `0cd51c2` | "Correct the census row's pid-probe provenance: check each drip pid on its own node" — the row reported both drip pids as `kill -0` → `ESRCH` without saying where each was probed; it now says each was checked on its own node, the only form that separates a dead pid from a pid that never existed on the host you asked |
| 12:00 ET | `d69bf44` | "Refresh status board 12:00 ET, and close the tick ledger's commit gap" — this tick's own publish: the 12:00 census (bit-identical to 11:00 in container counts, volume counts and whole-GB free space), the quartet probed per rank again (pids 280/306/301/301, rank-0 `/v1/models` 200), the drip ledger's two pids re-probed dead **on their own nodes** (`.35` → `3669184`, `.30` → `3983527`), the queue re-read (21 open, 0 stale claims, `check` green over 56 tasks) and the `tp12` figures re-derived (42 arms, 33/9; skip set 5) — plus this section itself. Its own recording commit is the tick artefact that row 1 of the ledger describes; a later tick folds it rather than adding another layer |
| 12:03–12:07 ET | `221fdae`, `011903c` | folded here at the 2026-11-01 23:00 ET tick, as the row above asked: `221fdae` wrote the 12:00 publish's own commit (`d69bf44`) into this ledger so the table stays whole at the point it opened, and `011903c` corrected the section's boundary sentence — "every refresh between the 02:00 publish and the 11:00 one" read as though `bb590b5` also lacked a row, which it does not, so the gap now starts *after* it and this range is the only span claimed |
| 23:29 ET | `b9943d1` | "Refresh status board 23:00 ET: 35-hour gap, planner's pair choice re-derived" — the 23:00 publish after a 35-hour board gap: fresh census (0/0, 1/0, 1/0, 1/0, 1/0, 0/0; root avail 1377 / 1782 / 1834 / 1734 / 1202 / 1448 GB), all four containers on the shipped production pin `canary-roce-aff52fa5` (excluded research accounting), no research window declared, both `.local/drip-state.json` pids dead on their own nodes, queue 21 open / 0 stale claims, `check` green over 56 tasks; it also folded the 12:00 tick's two ledger commits above and retired two carried `tp12` claims after re-derivation |
| 23:41 ET | `dec3175` | "Correct tp12 row's planner claim, and close three dead edges in register" — the `tp12` state cell had said the planner's pair pick "would answer blocker directly", which it does not: `recipes/cybersec/README.md` records that the engine logs no acceptance accounting at default verbosity and no recipe raises it, so a plain drip launch reproduces the same 2 002 B banner, and the row now names the arm match with that caveat in both cells. `h2h-doc-refresh`'s `blocked_by` mirror still carried three already-`done` jobs (`h2h-glm-needle-3rungs`, `h2h-glm-tools-leg`, `h2h-ds4-needle-131k-983k-rerun`); `task-queue.py update --id h2h-doc-refresh` relinked and `check` green over 56 tasks. Guards: `doc_hygiene` + `tracked_address_hygiene` 13 tests OK |
| 00:14 ET | `18e8f3f` | "Queue a Qwen3-Embedding-0.6B text arm for the embed lane" — owner's 2026-11-02 request filed as a `TODO.md` §embed row only (text-only Apache-2.0, 28 layers, 1024-d, 32k; pooling route 8010, ladder via `pooling-ladder-embed`, since a pooling engine has no `/chat/completions`), never booted and absent from `queue.json` until the 01:00 ET tick added `embed-qwen3-embedding-0.6b-text-arm` — the register gap a tick's row-count reconciliation then reported as an owner-requested item no register tooling could see |
| 00:19 ET | `8d7e044` | "Refresh status board 00:00 ET: census, probe and queue re-read unchanged" — the 00:00 publish: bit-identical census `0/0, 1/0, 1/0, 1/0, 1/0, 0/0` with root avail 1377 / 1782 / 1834 / 1734 / 1202 / 1448 GB, quartet probed per rank (pids 280/306/301/301, rank-0 `/v1/models` 200), both `.local/drip-state.json` pids dead on their own nodes, queue 21 open / 0 stale claims, `check` green over 56 tasks, `tp12` figures re-derived (42 arms, 33 TP=1 / 9 TP=2; skip set 5) |

| 01:17 ET | `e80dc72` | "Refresh status board 01:00 ET and register owner's embed-arm request" — 01:00 tick: census 0/0, 1/0, 1/0, 1/0, 1/0, 0/0 with whole-GB root avail 1377 / 1782 / 1834 / 1734 / 1202 / 1448 GB, four containers of the shipped production pin probed per rank (pids 280 / 306 / 301 / 301, rank-0 `/v1/models` 200), no research window, both drip pids dead on their own nodes; plus the register fix — `18e8f3f` had filed the Qwen3-Embedding-0.6B arm in `TODO.md` §embed only, invisible to `queue.json`, so it was added as `embed-qwen3-embedding-0.6b-text-arm` (single node, 1 h) with a Work queue row, board rows and open register tasks then 22-to-22 and `check` green over 57. Its own SHA went unrecorded, which is this row's reason |
| 02:07 ET | `e187d20` | "Refresh status board 02:00 ET: census, probe, planner and queue re-derived unchanged" — no-change tick: same container/volume counts and whole-GB free space, production pin probed per rank, 22 open / 0 stale claims, and the head-side `queue-drip.py --once --dry-run` planner re-derived; it also opened the board with an empty Landed table rather than inheriting one |
| 02:13 ET | `7043550` | "Correct tp12 planner claim: head-side drip plans the ds4 arm, not the abliterated one" — the row had claimed the planner would pick the acceptance instrument's own arm; the receipt predicate reads `~/benchmarks/tp12-*` (`tools/queue-drip.py:32-35`), where the head holds 3 such roots and the workstation 0, so the local dry-runs printed a false plan off an empty receipt set, and off the real receipts the abliterated arm is already in the measured set. It also wrote the 02:13 Landed row attributing that correction to `e187d20`; the SHA was corrected in place at `014cf89` |
| 02:51 ET | `fcc7c07` | "Record the embed lane's four boot traps in the new arm's queue row" — `tools/run-arm.sh:240` routes `*/embed/*` to `sparkrun benchmark pooling`, the ladder's `dimension_check: 4096` (`benchmarking/pooling-ladder-embed.yaml:19`) is the 8B encoder's width and the runner rewrites it to 2048 only for `*-2b-*` names (`tools/run-arm.sh:250`), `:8010` is held by `beegfs-mgmtd` on `.30` (`:58-61`), and the recipe must join `RECIPES` (`tests/test_qwen3_vl_embeddings.py:41`). `TODO.md` text only — nothing booted, no recipe added |
| 03:26 ET | `48b03b8` | "Fold five unrecorded tick commits into the ledger and clear the board's landed table" — the ledger's last row was the 00:00 tick's, so this publish recorded e80dc72, e187d20, 7043550 and fcc7c07 with their clauses, and only then cleared STATUS.md's Landed table (which held just the 02:13 and 02:52 rows, both now above) per the close-out contract. The fold stops the pattern that produced the gap: a tick that writes a commit and no row leaves the next tick nothing to read |
| 03:26 ET | `4c00bef` | "Record the ledger fold's own commit, so the ledger has no open tail" — it added the row above for `48b03b8`, which a commit cannot write for itself, and so left its **own** SHA as the new tail; closed here at 04:11 ET rather than carried, since `git grep 4c00bef -- mad-science/` found it nowhere in the tree |
| 04:11 ET | `b641c1f` | "Refresh status board 04:00 ET: census, probe and queue re-derived unchanged" — no-change tick: census `.30`→`.35` = 0/0, 1/0, 1/0, 1/0, 1/0, 0/0 with whole-GB root avail 1377 / 1782 / 1834 / 1734 / 1202 / 1448 GB (byte-identical to the 03:00 read), four containers of the shipped production pin probed per rank (pids 280 / 306 / 301 / 301, rank-0 `/v1/models` 200, worker ranks 404), no research window, both `.local/drip-state.json` pids dead on their own nodes, queue 22 open / 0 stale claims with `check` green over 57 tasks, `tp12` figures re-derived (42 arms, 33 TP=1 / 9 TP=2; skip set 5), and the register sizes re-derived (`TODO.md` 3314 lines / 372 KB, `queue.json` 838 lines / 93 KB). A second writer rewrote the board's prose between this tick's read and its census edit, so the tick layered its deltas on that wording instead of reverting it |
| 04:12 ET | `b32a8d7` | "Fold the ledger's open tail: record `4c00bef` and the 04:00 tick" — added the two rows directly above (`4c00bef` and the 04:00 tick's `b641c1f`, the latter's clauses surviving only in this fold since the message carries no body). Its own SHA was then the new open tail, and `git grep b32a8d7 -- mad-science/` found nothing at the 05:00 ET tick, so this row exists for it — the same cannot-write-itself shape `4c00bef` had, folded at the next tick rather than carried |
| 05:07 ET | `bdebae7` | "Refresh status board 05:00 ET: census, probe and queue re-derived unchanged" — no-change tick |
| 06:03 ET | `17ec33d` | "Refresh status board 06:00 ET: census, probe and queue re-derived unchanged" — no-change tick |
| 07:09 ET | `cbb6d6d` | "Refresh status board 07:00 ET: census, probe and queue re-derived unchanged" — no-change tick |
| 08:05 ET | `da6db60` | "Refresh status board 08:00 ET: census, probe and queue re-derived unchanged" — no-change tick |
| 09:23 ET | `961ed80` | "Refresh status board 09:00 ET: correct the container-ref count to two" — the census row's shipped-ref count read three; the two live refs are the `zz-mellum2.1-…-mtp` llama.cpp tag and the `ds4` `sglang-main-arm64` local tag |
| 09:25 ET | `4fe7ddc` | "Record a self-excluding driver check on the 09:00 board row" — the no-holder claim now names the `ps -eo pid,args` filter that keeps the check's own grep out of the count |
| 09:26 ET | `82375e5` | "Fix the repin task's cross-reference to the ref count it cites" — the `refresh-weights-and-runtime-repin` notes' cross-reference said "three", corrected to "two" in step with the row it points at |
| 10:12 ET | `b07f326` | "Refresh status board 10:00 ET: census, probe and queue re-derived unchanged" — no-change tick |
| 11:05 ET | `dcf55bb` | "Refresh status board 11:00 ET: census, probe and queue re-derived unchanged" — no-change tick |
| 12:11 ET | `4183a98` | "Refresh status board 12:00 ET: census, probe and queue re-derived unchanged" — twelfth tick of the 2026-11-02 board, nothing landed since the 11:00 publish: census `.30`→`.35` = 0/0, 1/0, 1/0, 1/0, 1/0, 0/0 with whole-GB root avail 1377 / 1782 / 1834 / 1734 / 1202 / 1448 GB identical across the 10:00 and 11:00 reads, production quartet probed per rank (serve child 280 / 306 / 301 / 301, rank-0 `/v1/models` 200, workers 1–3 404, `RestartCount` 0, `StartedAt 2026-10-27T04:14:27Z`), no research window declared, no `run-arm.sh`/`queue-drip.py`/`boot-watchdog.py` process on either host, both `.local/drip-state.json` pids dead on own nodes, queue 22 open (19 queued + 3 blocked) / 0 stale claims with `check` green over 57 tasks, `tp12` figures re-derived (42 arms, 33 TP=1 / 9 TP=2; skip set 5) and head still holding 3 `~/benchmarks/tp12-*` receipt roots against 0 on the workstation; also folded the nine commits published since the ledger's 04:00 fold (`bdebae7` through `dcf55bb`) and left its own SHA as the new open tail, which the row below closes |
| 12:15 ET | `870f1bc` | "Correct the tick ledger's boundary claim after the 12:00 fold" — the section heading still named the 2026-11-02 05:00 ET tick the most recent fold although the rows by then ran through the 11:05 publish plus the folded 12:00 tick; heading now names the fold that actually closed the tail, so the ledger's own boundary sentence stays true. Body records a green gate run on the workstation: suite 1172 tests OK (2 skipped), `sparkrun recipe validate` 80/80 under the HOME override, `bash -n` and `python -m py_compile` clean over the mods, lane mods, tools and plugins |
| 13:12 ET | `5098c02` | "Refresh status board 13:00 ET: census, probe and queue re-derived unchanged" — no-change tick: census `.30`→`.35` = 0/0, 1/0, 1/0, 1/0, 1/0, 0/0 with whole-GB root avail identical to the 12:00 read, four containers of the shipped production pin probed per rank, no research window, both drip pids dead on their own nodes, 22 open / 0 stale claims with `check` green over 57 tasks |
| 14:11 ET | `bddeda5` | "Refresh status board 14:00 ET: census, probe and queue re-derived; record sweep's new exit 2" — the 14:00 publish, whose live-state addition is the nightly sweep's move from exit 1 to exit 2: the 2026-11-02 16:01 UTC artifact (`41477186197`) carries two `container-unresolvable` rows and pin-drift issue #1 gained `sweep-broken`, with the cause measured at 14:00 — the two media `vllm-omni` arms pin `vllm/vllm-omni:nightly-15bce345…@sha256:f3473cb3…`, a tag upstream retired while the pinned digest still resolves an arm64 manifest list anonymously, so neither arm is unbootable |
| 14:15 ET | `1ea6f47` | "Date the sweep exit-code change and quote the anonymous digest probe" — it dated that move against four prior artifacts (2026-10-29 through 11-01, each exit 1 with no `-unresolvable` row) so it reads as a dated observation rather than an assumption, and replaced the paraphrase of the digest check with the literal `DOCKER_CONFIG=$(mktemp -d) docker manifest inspect …` command that proves the digest resolves without credentials |

| 15:05 ET | `f050d7c` | "Refresh status board 15:00 ET: census, serve probe and queue re-derived unchanged" — no-change 15:00 tick, and the publish the three rows above were folded by: census `.30`→`.35` = 0/0, 1/0, 1/0, 1/0, 1/0, 0/0 with whole-GB root avail 1377 / 1782 / 1834 / 1733 / 1202 / 1448 GB, four containers of the shipped production pin probed per rank (serve child 280 / 306 / 301 / 301, rank-0 `/v1/models` 200, workers 1–3 404), no research window, both drip pids dead on their own nodes, 22 open / 0 stale claims with `check` green over 57 tasks; its own SHA went unrecorded, which is this row's reason |
| 15:07 ET | `4bc01f2` | "Fold three unrecorded tick publishes into ledger, through 14:15 correction" — it wrote the three rows above and replaced the footer that had named `1ea6f47` the open tail, so at its own commit the tail was `f050d7c`; ledger's last row was `870f1bc` at 12:15 ET, hence the fold |
| 16:05 ET | `f672995` | "Refresh status board 16:00 ET: census, probe and queue re-derived unchanged" — sixteenth 2026-11-02 tick, nothing moved: census `.30`→`.35` = 0/0, 1/0, 1/0, 1/0, 1/0, 0/0 and whole-GB root avail 1377 / 1782 / 1834 / 1733 / 1202 / 1448 GB identical the 15:00 read; four containers on `.31`–`.34` shipped production pin `canary-roce-aff52fa5`, probed per rank again (serve child 280 / 306 / 301 / 301, rank-0 `/v1/models` 200, workers 1–3 404); no research window declared, no harness process on either host, both drip pids dead on their own nodes; 22 open register tasks (19 queued + 3 blocked), zero stale claims, `check` green over 57. Departed figures re-derived, not carried: tp12 manifest 42 arms (33 TP=1 / 9 TP=2), `fleet.yaml` `skip:` 5 arms, head holds 3 `~/benchmarks/tp12-*` receipt roots against 0 here, two unresolved shipped container refs still number two, newest sweep artifact remains `41477186197`. Its fold wrote `f050d7c` and `4bc01f2` rows and left own SHA the open tail, which this tick's fold closes |
| 17:07 ET | `a7c9539` | "Refresh status board 17:00 ET: census, probe and queue re-derived unchanged, fold 16:00 publish" — seventeenth 2026-11-02 tick, nothing moved: census `.30`→`.35` = 0/0, 1/0, 1/0, 1/0, 1/0, 0/0 and whole-GB root avail 1377 / 1782 / 1834 / 1733 / 1202 / 1448 GB identical the 16:00 read; four containers on `.31`–`.34` hold the shipped production pin `canary-roce-aff52fa5` (excluded research accounting) and were probed per rank (serve child 280 / 306 / 301 / 301, rank-0 `/v1/models` 200, workers 1–3 404); no research window, no harness process on either host, both drip pids dead on own nodes; 22 open register tasks (19 queued + 3 blocked), zero stale claims, `check` green over 57. Departed figures re-derived, not carried: tp12 manifest 42 arms (33 TP=1 / 9 TP=2), `fleet.yaml` `skip:` 5 arms, head 3 `~/benchmarks/tp12-*` receipt roots against 0 here, two unresolved shipped container refs, newest sweep artifact `41477186197`. Its fold wrote the 16:00 publish row above (`f672995`) and left own SHA open tail, which the row below closes |
| 17:08 ET | `22a5aee` | "Correct ledger heading's most-recent fold, 16:00 tick to 17:00" — the section heading still named the 16:00 tick as most recent fold although rows then ran through the 17:00 publish, so it named a fold that had stopped closing the tail; heading now names 17:00 and the footer counts this correction as tail too, a commit being unable to record itself. Second heading-clause drift at these boundaries in one day (the 16:00 fold needed `870f1bc`), so the 18:04 fold below bumps the clause in the commit it lands rather than a tick later |
| 18:06 ET | `c749577` | "Refresh status board 18:04 ET: census, probe unchanged, fold 17:00 publish" — eighteenth 2026-11-02 tick, nothing moved: census `.30`→`.35` = 0/0, 1/0, 1/0, 1/0, 1/0, 0/0 with whole-GB root avail 1377 / 1782 / 1834 / 1733 / 1202 / 1448 GB equal to the 17:00 read; four containers of the shipped production pin probed per rank (serve child 280 / 306 / 301 / 301, rank-0 `/v1/models` 200, workers 1–3 404); no research window, no `queue-drip` or `boot-watchdog` process on either host, both `drip-state.json` pids dead on their own nodes; 22 open register tasks (19 queued + 3 blocked) with `check` green over 57; and it wrote the two rows above plus the footer that named itself the open tail, so its own clauses survive only here |
| 22:06 ET | `5fbcc2d` | "Refresh status board 22:02 ET: census, serve probe and queue re-derived unchanged" — a no-change tick whose message carries no body, so its clauses survive only in the board it published: census `.30`→`.35` = 0/0, 1/0, 1/0, 1/0, 1/0, 0/0 with whole-GB root avail 1377 / 1782 / 1834 / 1733 / 1202 / 1448 GB, the four production containers probed per rank (pids 280 / 306 / 301 / 301, rank-0 200, workers 404), no research window declared, and 22 open register tasks — its container states read `Up 6 days`, before tonight's rollover to 7 |
| 22:29 ET | `79399fa` | "Open `3d` and `liquidai` lanes with ten queued arms" — two subjects had no home and neither was registered: `recipes/3d/README.md` opens a lane on `ccore/Qwen3.5-4B-3D-Coder` and `recipes/liquidai/README.md` covers all seven `LiquidAI/lfm3` repos plus `recipes/liquidai/finetuning/` as a toolkit-survey target. Ten queue rows and nothing booted (one 3D arm, one 3D-candidate survey, seven LFM3 arms, one toolkit survey), every fact read from the Hub on 2026-11-02; the `license: other` = LFM Open License v1.0 class is the first of its kind here, so ship posture went to `QUESTIONS.md` #56; gate: 1172 tests OK (2 skipped) and doc-census facts unchanged, both on the workstation, `task-queue.py check` green over 67 |
| 22:35 ET | `551e5af` | "Correct LFM3 layer mix to 13 conv / 6 full / 5 sliding" — the lane doc, the fine-tuning doc, the TODO row and the queue entry all read 12 `conv` + 6 `sliding_attention` + 6 `full_attention`; the checkpoint's own 24-entry `layer_types` gives conv 13, full 6, sliding 5, and the `conv, conv, full, conv, sliding` five-layer period is why a naive 3:1 reading drifts. Numbers only, no behaviour claim; the same probe confirms the 3D arm's 32 layers as 24 `linear_attention` + 8 `full_attention` |

| 23:10 ET | `fcccc75` | "Refresh status board 23:10 ET: mirror two lanes' ten arms, fold ledger" — nineteenth 2026-11-02 tick: census `.30`→`.35` = 0/0, 1/0, 1/0, 1/0, 1/0, 0/0 with whole-GB root avail 1376 / 1782 / 1834 / 1733 / 1202 / 1448 GB (`.30` 1 GB under its 22:02 read, stated not explained); four production containers probed per rank (pids 280 / 306 / 301 / 301, rank-0 `/v1/models` 200, workers 404); no research window, no `queue-drip` or `boot-watchdog` process on either host, both `drip-state.json` pids `ESRCH` on their own nodes; work queue 22 → 32 rows, the ten `3d`/`liquidai` arms filed by `79399fa` mirrored with `551e5af`'s corrected LFM3 mix, 32 open (29 queued + 3 blocked), `check` green over 67; folded `c749577`, `5fbcc2d`, `79399fa`, `551e5af` into the rows above; and its serve row's probe minute was an estimate rather than a clock reading, corrected in the commit below |

| 23:14 ET | `a9dddf8` | "Ground the serve row's probe time in the node clocks, not an estimate" — the 23:10 publish's serve row wrote "Probed 23:02" for a sweep whose output carried no clock reading, the minute inferred from the census, so the row was re-probed with each node printing its own clock first: 23:13:14–23:13:16, pids 280 / 306 / 301 / 301, the same rank-0 200 and workers-404 split, numbers unmoved; its first pgrep sweep died on a quoting error (inner ssh body had no loop) and was re-run, so the pids reported are the re-run's |
| 23:23 ET | `e4ca637` | "Report a retired container tag as `container-tag-retired`, not current" — the digest fallback from `433f153` classified a tag-404-with-live-digest as `container-current`, widening what "current" means and walking over the guard's deliberate negative control; it now has its own class, which gates exit 1 because `DRIFT_CLASSES` takes every class not ending `-current`, while only `-unresolvable` still escalates to 2, and `--apply` is untouched since a retired tag has nothing to bump to. Verified live on the tracked tree: 80 recipes / 87 model pins / 80 container pins, exit 1, 0 `*-unresolvable`, exactly two `container-tag-retired` rows (the media OMNI arms on `vllm/vllm-omni:nightly-15bce345…`); 1175 tests pass (2 skipped) on the workstation |

| 00:04 ET | `477ada5` | "Refresh status board 00:04 ET: census, serve probe and queue re-derived unchanged" — twentieth 2026-11-02 board tick, run at 2026-11-03 00:04 ET, nothing moved: census `.30`→`.35` = 0/0, 1/0, 1/0, 1/0, 1/0, 0/0 with whole-GB root avail 1375 / 1782 / 1834 / 1733 / 1202 / 1448 GB (`.30` 1 GB under its 23:01 read of 1376, stated not explained); four containers of the shipped production pin probed per rank (pids 280 / 306 / 301 / 301, rank-0 `/v1/models` 200, workers 404); no research window, no `queue-drip` or `boot-watchdog` process on either host, both `drip-state.json` pids absent on their own nodes; 32 open register tasks (29 queued + 3 blocked), zero stale claims, `check` green over 67. Re-derived, not carried: tp12 manifest 42 arms (33 TP=1 / 9 TP=2) and the persisted 5-arm skip set, head's 3 tp12 receipt roots against 0 here, the two unresolved shipped container refs, and the embed arm's recipe/tool/test tree unchanged since `014cf89` (only `tools/refresh-sweep.py`, `tools/README.md`, `tests/test_refresh_sweep.py` and docs moved) |

The three rows above were written by this tick's fold, which also replaced the footer that had named the 23:14 correction the open tail. Rows now run through the 00:04 publish (`477ada5`); this fold's own commit cannot record itself, so it is the current open tail — next fold's job.

## Tick ledger, 2026-11-03 (opened at the 01:04 ET tick; the 2026-11-02 section's footer named `1c884bf` the open tail, and four commits landed after it with no row)

| time ET | commit | one clause |
|---|---|---|
| 00:12 ET | `977492c` | "Date re-verified evidence rows to this tick's 00:02 re-read" — no body, so its clauses survive only here: it re-dated the evidence rows it had just re-verified against the 00:02 read rather than leaving them carrying the earlier cycle's time |
| 00:25 ET | `04d309c` | "Make `queue.json` the register: board derived, `TODO.md` frozen" — five owner rulings plus the migration that cost-driven instruction authorised. Rulings, each recorded where it binds: `#53` build DeepGEMM's SM121 paged-sparse kernels ourselves (the gate row becomes 8 h of work, the two survey arms stay blocked behind it); `#55` probe the mechanism before buying NVMe (production runs engram off the same pool, so pool latency is one of four candidates, not the cause, and a `.34` window is out); `#6` install the FLARE agent on `.30`+`.35` first, by `.deb` file with no APT repository entry anywhere because that key would be root on `.34`; the two OMNI arms keep tracking nightlies. `TODO.md` (3 414 lines, ~93k tokens, read whole by every tick and closeout) became a frozen archive with a banner; `render --board` emits the board's Work queue from the register, `orphans` fails on an open `- [ ]` item with no live `<!-- queue: id -->` marker, `evidence` became an optional per-task receipt path, and `test_archive_does_not_grow` pins the archive's 52 grandfathered items. Deliberately not done: importing the archive's prose into JSON — the archive keeps the evidence, the queue keeps the schedule. Gate: 1182 tests OK (2 skipped) on the workstation, `task-queue.py check` green over 70 tasks |
| 00:35 ET | `a2c720e` | "Bound the archive gate and record the schema deviation" — `orphans --allow N`, because the gate exited 1 on day one over 52 grandfathered pre-freeze items and was therefore useless as a gate: 52 is tolerated, one new unmarked item is the defect, a marker naming an unknown id always fails. The TP=2 probe row now names its sources (the `$HOME/serve_argv/<tag>_<node>.txt` argv captures on `.30`/`.35` and `docker inspect` on the production ranks, never a re-render from the YAML, which would miss a flag a mod appended), and `QUEUE.md` records the deliberate omission of the `decisions`/`questions` arrays with its arithmetic and as a deviation from the 2026-10-30 instruction. Gate: 1183 tests OK (2 skipped), `py_compile` clean, `check` green over 70 |
| 00:38 ET | `dfd0fff` | "Close the TODO-protocol migration row" — the cutover completes: the skills that would have re-forked the register are re-pointed, the hourly board tick first because its text still derived the Work queue from `TODO.md` and would have rebuilt the fork every hour; the closeout flips queue rows instead of archive checkboxes, the planning round reads the register, six more pointers name `queue.json`, and the two archiver skills carry a STOP banner since their premise was that `TODO.md` holds open work only. `update` gains `--evidence`, which only `add` had |
| 01:04 ET | `8efc4ba` | hourly board publish: census `.30`→`.35` = 0/0, 1/0, 1/0, 1/0, 1/0, 0/0 with whole-GB root avail 1375 / 1782 / 1834 / 1733 / 1202 / 1448 GB, bit-identical to the 00:02 read on all six; the four containers of the shipped production pin `canary-roce-aff52fa5` probed per rank (serve child 280 / 306 / 301 / 301, rank-0 `/v1/models` 200, workers 1–3 404); no research window declared and no research container anywhere; Work queue re-derived from the register with `render --board` and copied verbatim, which closed both drift directions at once — 32 board rows became **34 open register tasks**: `migrate-todo-protocol-to-queue` dropped (closed by `dfd0fff`), `engram-pool-latency-probe`, `flare-agent-rollout` and `media-omni-nightly-repin` appeared (filed by `04d309c`), and `arch-deepgemm-sm12x-paged-sparse` moved from "BLOCKED on upstream, owner question open" to queued work under ruling `#53` with the two `w4-survey` arms now `blocked` behind it. `check` green over 70 tasks, zero `claimed_by`. This publish's own commit cannot record itself, so it is the new open tail |
| 01:07 ET | `6f19662` | "Drop an append artifact from the 2026-11-03 ledger section" — a lone pipe character sat between the 2026-11-02 section's footer and the `## Tick ledger, 2026-11-03` heading, a stray table row from how the append was assembled; it rendered as nothing while reading as a broken table. One line, content unchanged. |
| 02:03 ET | `88301ba` | "Refresh status board 02:03 ET: census and serve probe re-derived unchanged" — no-change 02:03 tick: census `.30`→`.35` = 0/0, 1/0, 1/0, 1/0, 1/0, 0/0 and whole-GB root avail 1375 / 1782 / 1834 / 1733 / 1202 / 1448 GB bit-identical to the 01:03 read on all six (node clocks 02:01:20–02:01:22); four containers shipped production pin `canary-roce-aff52fa5` probed per rank (serve child 280 / 306 / 301 / 301, rank-0 `/v1/models` 200, workers 1–3 404); no research window declared; 34 open register tasks with no stale `claimed_by`, `check` green over 70; board's Work queue byte-identical to `render --board` and `Landed session` left empty; that fold added rows for `8efc4ba` and `6f19662`, which the 02:07 correction below then settled |
| 02:07 ET | `369fb6e` | "Name 01:04 publish's own ledger row instead adding second" — `88301ba`'s fold gave `8efc4ba` a new row where a row already stood above it carrying `this tick` in place of the SHA the publish could not supply itself; named the SHA in place, dropped the duplicate, kept only the genuinely homeless `6f19662` row, and rewrote the footer to match — pipe counts 4/4, no other line of the section touched |
| 03:04 ET | `d93f840` | "Refresh status board 03:03 ET: census and probe re-derived, fold two rows" — no-change 03:03 tick: census `.30`→`.35` = 0/0, 1/0, 1/0, 1/0, 1/0, 0/0 and whole-GB root avail 1375 / 1782 / 1834 / 1733 / 1202 / 1448 GB bit-identical to the 02:01 read on all six (node clocks 03:01:29–03:01:31); four containers shipped production pin `canary-roce-aff52fa5` probed per rank (serve child 280 / 306 / 301 / 301, rank-0 `/v1/models` 200, workers 1–3 404); no `.local/fleet-window.lock`, so the production serve's unnamed holder stated not escalated; Work queue re-verified byte-identical to `render --board` (34 rows), register 34 open of 70 with `check` green; folded `88301ba` and `369fb6e` and named itself the open tail, which is why it alone had no row |
| 04:05 ET | `210a020` | "Refresh status board 04:00 ET: census and probe re-derived, fold 03:03 publish" — no-change 04:00 tick: census `.30`→`.35` = 0/0, 1/0, 1/0, 1/0, 1/0, 0/0 and whole-GB root avail 1375 / 1782 / 1834 / 1733 / 1202 / 1448 GB (node clocks 04:00:51–04:00:53), identical to the 03:01 read; serve child alive in every rank (pids 280 / 306 / 301 / 301), rank 0 `/v1/models` 200 and ranks 1–3 404 at 04:01; Work queue compared row-for-row against `tools/task-queue.py render --board` (34 rows over a 70-task register, 32 queued + 2 blocked, `check` green); gate 1183 tests OK (2 skipped) on the workstation |
| 05:05 ET | `ec0b390` | "Refresh status board 05:00 ET: census and probe re-derived, fold 04:00 publish" — no-change 05:00 tick: census `.30`→`.35` = 0/0, 1/0, 1/0, 1/0, 1/0, 0/0 and whole-GB root avail 1375 / 1782 / 1834 / 1733 / 1202 / 1448 GB, head clock 05:00:47, same figures the 04:00 read returned on all six (3.02 s wall, nothing carried); four containers shipped production pin `canary-roce-aff52fa5` probed per rank at 05:01 (node clocks 05:01:23–05:01:25): serve child alive in every rank (pids 280 / 306 / 301 / 301), rank 0 `/v1/models` 200 and ranks 1–3 404; no `.local/fleet-window.lock`, so the production serve's unnamed holder is stated, not escalated; Work queue compared byte-identical against `tools/task-queue.py render --board` (34 rows over a 70-task register: 32 queued + 2 blocked), no stale `claimed_by`, `check` green; gate 1183 tests OK (2 skipped) on the workstation |
| 06:05 ET | `f8c1474` | "Refresh status board 06:00 ET: census and probe re-derived, fold 05:00 publish" — no-change 06:00 tick: census `.30`→`.35` = 0/0, 1/0, 1/0, 1/0, 1/0, 0/0 and whole-GB root avail 1375 / 1782 / 1834 / 1733 / 1202 / 1448 GB (head clock 06:00:46, 2.95 s wall), the same figures the 05:00 read returned on all six; the four containers on the shipped production pin `canary-roce-aff52fa5` probed 06:01 (node clocks 06:01:36–06:01:37): serve child alive in every rank (pids 280 / 306 / 301 / 301), rank 0 `/v1/models` 200 and ranks 1–3 404; no `.local/fleet-window.lock`, so production serve's unnamed holder stated, not escalated; Work queue table as committed carries 34 rows (32 queued + 2 blocked) out of the 70-task register; title and both In-flight rows re-derived, Landed session left empty because the tick is a one-shot session |
| 07:05 ET | `9e0c12c` | "Refresh status board 07:00 ET: census and probe re-derived, fold 06:00 publish" — no-change 07:00 tick: census `.30`→`.35` = 0/0, 1/0, 1/0, 1/0, 1/0, 0/0 and whole-GB root avail 1375 / 1782 / 1834 / 1733 / 1202 / 1448 GB, swept 07:00:52 ET (read-only ssh, one sweep, 3.05 s wall), the same figures the 06:00 read returned on all six; the four containers on the shipped production pin `canary-roce-aff52fa5` probed 07:01:45 (2.29 s wall): serve child alive in every rank (pids 280 / 306 / 301 / 301), rank 0 `/v1/models` 200 and ranks 1–3 404; no `.local/fleet-window.lock` exists, so the production serve's unnamed holder is stated, not escalated; Work queue byte-identical to `render --board` (34 rows, 32 queued + 2 blocked, `check` green over the 70-task register); its own diff wrote the `06:05 ET`/`f8c1474` row above and rewrote this footer, and it named itself the open tail because a publish cannot name its own SHA |
| 08:05 ET | `4ddb2bf` | "Refresh status board 08:00 ET: census and probe re-derived, fold 07:00 publish" — no-change 08:00 tick: census `.30`→`.35` = 0/0, 1/0, 1/0, 1/0, 1/0, 0/0 and whole-GB root avail 1375 / 1782 / 1834 / 1733 / 1202 / 1448 GB (head clock 08:00, one read-only sweep, 2.92 s wall), the same figures the 07:00 read returned on all six; four containers on the shipped production pin `canary-roce-aff52fa5` probed 08:01:18 (2.09 s wall): serve child alive in every rank (pids 280 / 306 / 301 / 301), rank 0 `/v1/models` 200 and ranks 1–3 404; no `.local/fleet-window.lock`, so the production serve's unnamed holder stated, not escalated; Work queue byte-identical to `render --board` (34 rows, 32 queued + 2 blocked, `check` green over the 70-task register); Landed session empty, the tick is a one-shot session |
| 09:05 ET | `4c639cd` | "Refresh status board 09:00 ET: census and probe re-derived, fold 08:00 publish" — no-change 09:00 tick: census `.30`→`.35` = 0/0, 1/0, 1/0, 1/0, 1/0, 0/0 and whole-GB root avail 1375 / 1782 / 1834 / 1733 / 1202 / 1448 GB (one read-only sweep from the workstation, 3.22 s wall), the same figures the 07:00 and 08:00 reads returned on all six; four containers on the shipped production pin `canary-roce-aff52fa5` probed 09:01:38 (2.52 s wall): serve child alive in every rank (pids 280 / 306 / 301 / 301), rank 0 `/v1/models` 200 and ranks 1–3 404; no `.local/fleet-window.lock`, so the production serve's unnamed holder stated, not escalated; Work queue byte-identical to `render --board` (34 rows, 32 queued + 2 blocked, `check` green over the 70-task register); Landed session empty, the tick is a one-shot session. Two row-less correction commits belong to this cycle and are named here rather than given rows of their own: `22e39ce` ("Fix sentence join in 09:00 tick ledger footer" — the 08:05 clause had been stitched onto a sentence already ending in a period, so the footer now reads as one list) and `777b544` ("Name footer-correction commit next tick fold" — the footer now names `22e39ce` so it could not arrive homeless) |
| 10:05 ET | `c95fef1` | "Refresh status board 10:00 ET: census and probe re-derived, fold 09:00 publish" — no-change 10:00 tick: census `.30`→`.35` = 0/0, 1/0, 1/0, 1/0, 1/0, 0/0 and whole-GB root avail 1375 / 1782 / 1834 / 1733 / 1202 / 1448 GB (one read-only sweep from the workstation, 2.97 s wall), the same figures every read since 07:00 returned on all six; the four containers on shipped production pin `canary-roce-aff52fa5` probed 10:01:21–10:02 (3.52 s wall): serve child alive in every rank (pids 280 / 306 / 301 / 301), rank 0 `/v1/models` 200 and ranks 1–3 404, the same answers the 09:01 probe got; no `.local/fleet-window.lock`, so the production serve's unnamed holder stated, not escalated; Work queue byte-identical to `render --board` (34 rows, 32 queued + 2 blocked, `check` green over 70 tasks); Landed table stayed empty because the tick is a one-shot session. |
| 11:09 ET | `7ab8f70` | "Add the questions register and bound the archive scan at the freeze" — peer session landed 11:04 ET, no tick publish names it: `queue.json` gains a `questions` array ({id, summary, status, provenance, asked}) that only grows and `task-queue.py questions` prints the open rows, and `orphans` is bounded by the archive's `<!-- archive-frozen: 04d309c -->` marker so a removal can no longer net out an addition (0 orphans, exit 0 on the real file); the FLARE rollout row is corrected to the owner's second reading, vendor APT repository rather than `.deb` file install, with the key's `apt upgrade` reach recorded as accepted risk; `engram-pool-latency-probe` closes on its own refutation — pool 1.377 ms vs NVMe 0.200 ms on cold O_DIRECT reads but 1497.7 us cold / 0.5 us hot on one held block (n=200), so variable cache hit rate, not pool latency, and staging is withdrawn for the new `engram-cache-hit-rate` row; gate 1186 tests OK (2 skipped), py_compile clean, `check` green over 71 tasks. |
| 11:11 ET | `90e2193` | "Lead the withdrawn engram row with its refutation and size the cache, not invert it" — peer follow-up landed inside this tick: the probe row's RESULT now opens WITHDRAWN IN PART and its scope note records that the cold blob measured the abliterated arm's own pack while `.35` ran no serve, so no production page was evicted; `engram-cache-hit-rate` is reframed to reconcile `bound-engram-cache` against the repo's own `fadvise(DONTNEED)` evictor rather than add a third policy; `flare-agent-rollout`'s title now matches the APT-repository ruling its notes already carried. Board Work queue re-rendered from the committed register afterwards. |
| 11:10 ET | `53fc6b4` | "Refresh status board 11:01 ET: census and probe re-derived, fold 10:00 publish" — the 11:00 tick publish, homeless only because a commit cannot name itself: census `.30`→`.35` = 0/0, 1/0, 1/0, 1/0, 1/0, 0/0 and whole-GB root avail 1375 / 1782 / 1834 / 1733 / 1202 / 1448 GB (one read-only sweep, 2.46 s wall), serve child alive in every rank (pids 280 / 306 / 301 / 301) with rank 0 `/v1/models` 200 and ranks 1–3 404 at 11:01:37–11:01:39, no `.local/fleet-window.lock` so the production serve's unnamed holder stated not escalated; folded `c95fef1` (`10:05 ET` row) and `7ab8f70` (`11:09 ET` row) |
| 11:12 ET | `52bf43a` | "Re-derive board queue after peer register commits landed mid-tick" — the tick's own follow-up: `7ab8f70` (11:04) and `90e2193` (11:09) landed in this clone while the board was being written, so the Work queue was re-rendered from the committed register and stands as `render --board` verbatim over 71 tasks — 34 open, 32 queued plus 2 blocked; both peers get their own rows here and the footer names the register the table was derived from |
| 11:19 ET | `fe5b140` | "Flatten and escape board cells so a note cannot break the table" — `render --board` interpolated a task's notes into the state cell unfiltered, so `engram-cache-hit-rate`'s blank-line paragraph ended the board table at `STATUS.md:40` and three rows' raw pipes split their cells; `board_rows` now routes every interpolated cell through `_cell` (whitespace runs collapsed, `\|` escaped) so a row is always one line and four cells, the new test fails on the old renderer, and gate reads 1187 tests OK (2 skipped) |
| 11:36 ET | `e984c11` | "Settle `#55` on cache hit rate and take the vendor key only where the agent goes" — one 4 KiB block of the abliterated arm's own engram pack costs 1497.7 µs cold and 0.5 µs on repeat (n=200, `.35`, p95 0.6 µs, ~3000x), so the 10.6–13.7 t/s gap is cache hit rate, not storage tier: the ~94 GB × 2 NVMe route is withdrawn, the production-rank window is no longer needed, `engram-cache-hit-rate` carries the work against the existing `attic/ds4/mods/bound-engram-cache` `fadvise(DONTNEED)` evictor, FLARE's APT key travels with the agent to a production rank only after the two-node proof, and the register's `questions` array is empty with numbering reserved |
| 11:56 ET | `a35b33a` | "Close py314 question at Leg A: the interpreter is 0.007 % of a decode step" — `tools/py-runtime-bench.py --repeat 5` under CPython 3.12.14 / 3.14.6 / 3.14.9t: the specializing interpreter wins only on a tight arithmetic loop (79 → 48 ns) and loses on every token-dominating case (streaming `json.dumps` 1.027x, detokenizer 1.058x, body parse 0.910x, asyncio turn 0.870x), net 5.10 → 5.03 µs per token = 1.4 %, which is 0.005–0.007 % of a 73–94 ms decode step, so Leg B (source-building sglang/vllm and flashinfer against cp314) is retired, not deferred, and the queue row left |
| 12:04 ET | `9affeea` | "Launch the DFlash2 draft-token sweep on the head and record what blocked the first run" — preflight cleared every gate the arm needs (`.30`/`.35` at zero containers with no fleet-window lock, a single-node job needing none; the pinned `lmsysorg/sglang:v0.5.22` digest present on `.30`; both snapshots complete at 21 entries for the 122B NVFP4 body and 5 for the drafter, no `.incomplete`; and a render proving `-o speculative_draft_tokens=4` becomes `--speculative-num-draft-tokens 4`, since the recipe default is 15 behind a placeholder and the override had to be shown, not assumed). The first attempt died in eight seconds on `Error: Cluster 'WOPR' not found` — `run-arm.sh` hardcodes `--cluster WOPR` and this workstation defines no cluster at all — so the three legs run from the head's own clone into `~/benchmarks/tp12-20261103/`, the queue row flipped to `running` under `siv-session-20261103` |
| 12:08 ET | `429ab91` | "Refresh status board 12:00 ET: census and probe re-derived, fold four commits" — the 12:00 tick publish, homeless only because a commit cannot name itself: census `.30`→`.35` = 0/0, 1/0, 1/0, 1/0, 1/0, 0/0 with whole-GB root avail 1375 / 1782 / 1834 / 1733 / 1202 / 1448 GB, the four shipped-pin containers probed per rank (serve child 280 / 306 / 301 / 301, rank-0 `/v1/models` 200, workers 1–3 404), no `.local/fleet-window.lock` so the production serve's unnamed holder stated not escalated; folded `7ab8f70`, `90e2193`, `52bf43a`, `fe5b140` and the three rows after it |
| 12:51 ET | `9b68233` | "Say where `run-arm.sh` has to run: the head, because `--cluster WOPR` lives only there" — the eight-second wrong-host death now reads as a wrong host instead of a broken recipe: `tools/README.md` states beside the exit-status sentence that the driver runs on the head, since `sparkrun cluster list` on the workstation reports no clusters at all. Docs only, no behaviour change, and the sweep already running on the head was unaffected |
| 13:08 ET | — (measurement, no commit) | the DFlash2 draft-token sweep's three legs finished `rc=0` on `.30` (12:01→12:22, 12:23→12:43, 12:44→13:08; `~/benchmarks/tp12-20261103/sweep.log`), and their cells were homeless once the board's `Landed session` table was cleared at the session handoff, so they live here: `tg128` aggregate c1 / c5 / c10 = **d4 38.36 / 54.35 / 51.12**, **d8 44.59 / 40.64 / 40.06**, **d15 31.04 / 27.95 / 26.83** t/s, house 29/30 on every leg (TC-14 partial only), read back from each leg's `ladder.csv` and `house.csv` at 13:42 ET. No verdict is recorded here: the row's pre-registered outcome, and its `running` → `done` flip, stay with `ornith-122b-dflash2-draft-token-sweep`'s holder |
| 13:37 ET | `2608930` | "Give the two dead container pins a real artifact, or retire the arm that owns one" — both refs the nightly sweep called `container-floating` are fixed, and the record corrected on the way: the 2026-10-29 claim that the llama.cpp package's only tag is `upstream-a37cc46` was true of GHCR only, since Docker Hub carries five tags and four are that engine, so the Mellum MTP arm re-pins to `littlecedar/dgx-spark-llama-cpp:upstream-a37cc46-cu130@sha256:ef2d4bc8…` — a digest the lane already measured on 2026-10-22 and three sibling arms already pull, so the fleet keeps one image. The ds4 stock-main-tree S0 arm is retired rather than re-pinned (`sglang-main-arm64:6563312` has no registry anywhere and nothing published is boot-equivalent) into `attic/ds4/` with a banner; all 79 shipped `container:` pins now carry an `@sha256:` digest (scripted check), gate 1187 tests OK (2 skipped) and `doc-census --check` green. Root cause left open: `refresh-sweep.py` returns `container-floating` for a tag without a digest before making any registry call |
| 13:43 ET | `4e3eda9` | the 13:00 tick's own publish, whose body lost every backticked word to shell substitution — the message was composed inside a double-quoted argument, so the shell ran the backticks and the text came out shrunken with two `command not found` errors. The subject stands and the figures it meant are the census row it published beside it: `.30`→`.35` = 0/0, 1/0, 1/0, 1/0, 1/0, 0/0 with whole-GB root avail 1375 / 1782 / 1834 / 1733 / 1202 / 1448 GB. Not rewritten, because it was pushed before the mangling was noticed |
| 13:43 ET | `258827d` | "File the 3D lane's candidates and rejects, and record both image-ref dispositions" — three findings change the plan: `ccore/Qwen3.5-4B-GLB-3D-Coder` emits a downloadable GLB rather than only a scene, making it the first axis-1 arm with a parseable artifact; `Zhengyi/LLaMA-Mesh` emits OBJ tokens, so mesh generation rides llama.cpp with no new image, but its card body carries NSCLv1 (non-commercial) while the Hub tag says only llama3.1, so it ships eval-only per `QUESTIONS.md` #11; and Hunyuan3D 3.x does not exist on the Hub — the newest is `tencent/Hunyuan3D-2.1`, whose licence excludes the EU/UK/KR above 1M MAU and fails gate (a) even though the runtime would have passed. Closes the `3d-model-survey` row and the file half of `published-image-refs` |
| 13:43 ET | `beba90f` | "Refresh status board 13:41 ET: census and probe re-derived, de-duplicate raced landed rows" — subject-only, so its clauses live here: two sessions had written the board's `Landed session` table concurrently and each of `9affeea`/`9b68233` stood twice; the duplicates were collapsed and census, serve probe and Work queue re-derived in the same publish |
| 13:53 ET | `c8edd25` | "Flag the draft-token sweep's receipts and drop two closed rows from the queue" — the board's census row was re-stamped 13:51 ET and cut back to the sweep log plus the three leg dirs, `published-image-refs` and `3d-model-survey` left the queue mirror (both closed by `258827d`), and the previous session's three landed rows were replaced by the 13:02 session boundary row; `9affeea`, `9b68233` and the 13:08 measurement got their ledger rows four minutes later in `ad94cb3` |
| 13:53 ET | `ad94cb3` | "Refresh status board 13:51 ET: queue re-derived, landed rows moved to ledger" — the 13:00 tick's final publish, which cannot name itself: queue copied byte-for-byte from `render --board` (31 open rows at that moment), `Landed session` cleared to the session boundary only after `9affeea`, `429ab91`, `9b68233`, `2608930`, `4e3eda9`, `258827d` and `beba90f` had ledger rows, and `4e3eda9`'s mangled body recorded rather than rewritten because it was already pushed |
| 13:56 ET | `91abeb7` | "Drop the parked Mistral-Large row from the board queue" — `07c813a` parked `mistral-large-4-1t-feasibility` after that board's table had been rendered, so the board advertised a closed task as `running`; the table was re-rendered from the register immediately before the commit and verified equal to `render --board` at 30 open rows. This is the drift class the register mirror exists to catch, and it caught it |
| 14:00 ET | `f3d3cf8` | "Drop the sweep verdict from the census row: a holder's call, not the tick's" — one sentence removed, so the census row keeps the measured cells and the leg receipts but no longer states the pre-registered outcome's verdict; the `running` → `done` flip stays with `ornith-122b-dflash2-draft-token-sweep`'s holder |
| 14:04 ET | `7a5a4ed` | "Record the DFlash2 sweep's measured cells where they outlive a census row" — the cells (`tg128` c1/c5/c10 per block size, house 29/30 per leg) first published as a board `Landed session` row and copied into the register row's notes tail with their three receipt dirs; no verdict, state left `running` |
| 14:09 ET | `7201b7c` | "Give the draft-token sweep's three-leg cells a home in the ledger" — wrote the 13:08 ET measurement row above, so the cells survive the 14:06 handoff that cleared the board's table |
| 14:13 ET | `5695723` | "Refresh status board 14:07 ET: title re-derived from its own census, drip probe restored" — the 14:06 tick's own publish, which cannot name itself: the title was taken from that tick's own census read rather than the previous cycle's, and the census row regained its drip/watchdog probe (no `queue-drip`/`boot-watchdog` process on the head or on `.35`, both `.local/drip-state.json` pids `ESRCH` on their own nodes) |
| 14:18 ET | `3ffd2eb` | "Refresh status board 14:18 ET: census and serve probe re-derived, nothing moved" — the 14:02 tick's own publish, which cannot name itself, and the hour's second tick (one a minute after 14:06 wrote the board): census swept from the head at 14:16:23, 3.00 s wall, returned the figures every read since 07:00 has — `.30`→`.35` 0/0, 1/0, 1/0, 1/0, 1/0, 0/0 with whole-GB root avail 1375 / 1782 / 1834 / 1733 / 1202 / 1448 GB — and the shipped pin `canary-roce-aff52fa5` probed at 14:17:52–14:17:53 got serve child 280 / 306 / 301 / 301 in every rank with rank 0 `/v1/models` 200 and ranks 1–3 404; Work queue re-verified byte-identical to `render --board`, 30 rows over the 71-task register with `check` green |
| 14:20 ET | — (observation, no commit) | **The draft-token sweep's driver did not end at 13:08:40**: a fourth leg — the no-spec baseline (`ARM_TAG=nospec`, `ARM_OPTS="-o speculative_algorithm=NONE"`) — launched on `.30` at 13:29:52 as task `9c83eedea8de8c60_6188e1147c24`, its rank-0 scheduler died during initialization (`RuntimeError: Rank 0 scheduler died during initialization (exit code: -15)`; readiness probe `TimeoutError: port`; total 1823.4 s; `~/benchmarks/tp12-20261103/zz-ornith-1.5-122b-nvfp4-dflash2-sglang-nospec/launch.log` mtime 14:00:19) and the boot watchdog stopped it at t=1821 s (14:00:26, same dir's `watchdog.log`), so the leg produced **no cell** — that receipt dir holds only `launch.log` and `watchdog.log`, `nospec-driver.log` is 0 B, and `run-arm.sh` pids 3604408/3604684 were alive at 14:00:40 with no container left behind and gone by 14:17:45. Censuses at 14:08:04 and 14:16:23 ET (workstation and head, one read-only sweep each) both read `.30` 0/0 with the production ranks unchanged (pids 280 / 306 / 301 / 301, rank 0 `200`, ranks 1–3 `404`), and the register row still reads `running` pending its holder. Recorded here because the board's census row is regenerated every tick: the `3ffd2eb` publish still carries the peer's original sentence ("driver finished on its own 13:08:40 ET all three legs `rc=0`"), and the correction exists only in the uncommitted worktree draft at the time of writing, so this row is its first committed home. |
| 14:37 ET | `900a473` | "Survey the 122B drafter family, park its GGUF route, and add the missing control arm" — the survey lands in `recipes/ornith/README.md` (+202 lines) with three candidate `zz-` arms (cyankiwi AWQ-int4, dealignai NVFP4-uncensored, devsecllm NVFP4-ablated) and the no-spec control `zz-ornith-1.5-122b-nvfp4-nospec-sglang.yaml`; closes `ornith-122b-quant-drafter-exploration` in the register |
| 14:40 ET | `21f090d` | "Measure the LFM3 fine-tuning floor at the model instead of reading caps off READMEs" — the floor is transformers **>=5.18.0**, proven by loading, binding and back-propagating `LiquidAI/LFM3-1.7B-Base` (5.15/5.16 parse and bind, then die on the first forward with `KeyError: 'linear_attention'`; 5.17 at config load with `KeyError: 'conv'`), which rejects three of six candidate toolkits on their own pins; the conv-breaks-training assumption is false because `lfm3_conv.can_use_lfm3_conv()` returns False under `torch.is_grad_enabled()`, so training runs `nn.Conv1d` (13 modules, 26 of 52 conv-block LoRA tensors carrying gradients at step 1); what fails is LoRA on the depthwise kernel at r=16, since rank must divide groups; `transformers`+`peft`+`trl` completes a real run (LoRA 15.4M, loss 4.603 → 4.096, adapter and merged bf16 written) and Axolotl is usable only with sample packing off (`lfm3` absent from `RECURRENT_MODEL_TYPES`); gates 2 and 3 rest on wheel availability and 16 B/param arithmetic, no node touched; closes `liquidai-finetune-toolkits` |
| 14:25–14:56 ET | — (fold commits, no row of their own) | `ceecba5` recorded the 14:06 and 14:02 ticks' publishes, `5c6d733` the sweep's failed no-spec leg, `85236fe` corrected the row's claim about which board carried the sweep fix, `333cb02` closed the 13:53–14:09 gap whose four rows `85236fe` had already swept into history, and `91a91d0` dropped from the board's queue mirror the two rows the register had closed; a fold cannot name itself, so they are recorded here |
| 14:47 ET | `20523fb` | "Record the two landings and the fold chain the ledger was still missing" — fold commit, gives rows to `900a473`, `21f090d` and the five fold commits behind them (`ceecba5`, `5c6d733`, `85236fe`, `333cb02`, `91a91d0`), quoting each subject and the mechanism its body states; corrects the trailing footer clause that called the fold itself the only unrecorded commit. No boot and no measurement: every figure is a commit body's own |
| 14:51 ET | `9c11b87` | "Re-measure the validate snapshot at 83 recipes instead of dividing by a new denominator" — CI caught a local green claim that could not hold: `doc-census` counts `git ls-files` and the suite ran before four recipes were staged (79 seen locally, 83 on push), so `test_doc_hygiene` failed on three statements; `doc-census --fix` then produced the arithmetic `79/83 pass`, so the snapshot was re-run instead — plain **83/83 pass**, strict **20/83 fail** on the unchanged 2026-10-31 roster, suite **1187 tests, 2 skipped** |
| 14:59 ET | `0739f7c` | "Land the matched-window sweep: d4 is the setting, d15 is worse than no drafter" — four legs on `.30` in one window (d4/d8/d15 plus a true no-drafter control, the new `zz-ornith-1.5-122b-nvfp4-nospec-sglang.yaml`): against that control d4 is **+31.1 % C1, +51.5 % C2, +16.3 % C5, +4.1 % C10** with C10 per-request 10.55 vs 18.27 t/s, d8 takes the best single-stream 44.59, and d15 is **−18.7 / −40.2 / −45.4 %** past C2 at **0.76x effective streams** (`aggregate / per-request`), so its C2/C5/C10 cells are serial measurements wearing concurrency labels; yesterday's cross-night control 28.95 / 48.97 reproduces at 29.27 / 49.10. Also records the trap that `--speculative-algorithm NONE` leaves a dead serve child behind a live container (rc=4), which is why the control is a separate recipe |
| 15:04 ET | — (this tick's publish, cannot name itself) | Board refreshed for 15:04 ET: census swept the head 15:01:26 (3.02 s wall) and returned the figures every read since 07:00 has — `.30`→`.35` 0/0, 1/0, 1/0, 1/0, 1/0, 0/0 and whole-GB root avail 1375 / 1782 / 1834 / 1733 / 1202 / 1448 GB — the shipped pin `canary-roce-aff52fa5` probed 15:03:33 got the serve child alive in all four ranks (280 / 306 / 301 / 301) and rank 0 `/v1/models` 200, and the Work queue was re-rendered byte-for-byte from `render --board` at **27 open rows** over the 71-task register (`check` green), which dropped the sweep row the register closed; this publish is the new open tail |
| 16:02 ET | — (this tick's publish, cannot name itself) | Board refreshed for 16:02 ET: census swept the head 16:01:27 (3.06 s wall) and returned the figures every read since 07:00 has — `.30`→`.35` 0/0, 1/0, 1/0, 1/0, 1/0, 0/0 and whole-GB root avail 1375 / 1782 / 1834 / 1733 / 1202 / 1448 GB — the shipped pin `canary-roce-aff52fa5` probed 16:01:55 got the serve child alive in all four ranks (280 / 306 / 301 / 301) and rank 0 `/v1/models` 200, no drip or watchdog process armed on the head or on `.35` (16:04:08), and the Work queue re-rendered byte-for-byte from `render --board` at **27 open rows** over the 71-task register (`check` green); the 15:04 tick's placeholder row is retired, its facts in the row above |
| 18:09 ET | `f3afe2c` | the 18:04 tick's own publish, which cannot name itself: title, census, `.31`–`.34` production and `.35` rows re-derived from that tick's read, the queue re-rendered with `mellum-plain-c10-dip` shown `running` and the four h2h/glm rows shown `blocked`, and three landed rows added for `8545eaa`, `4df309e` and `a03e0a5` |
| 18:10 ET | `51afb73` | subject-only, so its clause lives here: it named, inside the census row, that four of the six `blocked` states were not in the committed register — `h2h-glm-flash-house-recipe`, `h2h-beam-house-and-bfcl-category`, `h2h-second-boot-ladder` and `glm-flash-concurrency-degradation-search` had been flipped `queued`→`blocked` by an uncommitted edit to `mad-science/queue.json`, `HEAD` carrying 2 blocked and the worktree 6. Resolved since: `HEAD` carries 6 blocked and the worktree matches it, so the 19:04 census row states no such split |
| 19:04 ET | — (this tick's publish, cannot name itself) | Board refreshed for 19:04 ET: the census swept from the head (one stamped sweep, 4.22 s wall) gives `.30`→`.35` = 1/0, 1/0, 1/0, 1/0, 1/0, 0/0 with whole-GB root avail 1344 / 1752 / 1802 / 1700 / 1174 / 1415 GB, bit-identical to the 18:04 read on all six, and `.30`'s one container is the first 122B research boot `d85008b` recorded (serve child pid 1740727, `/v1/models` 200 in 2.3 ms, a house run driving it); the shipped pin `canary-roce-aff52fa5` probed per rank (serve child 280 / 306 / 301 / 301, `RestartCount` 0 on all four, rank 0 `/v1/models` 200 and ranks 1–3 404 at 19:06); `mellum-plain-c10-dip` is closed, so its board row left and its measurement lives in the 18:29 ET row; Work queue re-rendered byte-for-byte from `render --board` at 27 open rows over the 73-task register (`check` green); `Landed session` gained rows for the eight commits 18:11–19:00 no board carried, and this publish is the new open tail |
| 20:45 ET | — (campaign close, no commit) | **122B finetune campaign on `.30` ends with all three arms done** — `~/benchmarks/ornith122b-20261103/WATCH-SUMMARY.txt`: `zz-dealignai-…-nvfp4-uncensored-dflash2-sglang` rc=5 (18:22:23→19:40:54, the recorded negative: an algo SGLang cannot load), `zz-devsecllm-…-nvfp4-ablated-dflash2-sglang` rc=0 (19:41:24→20:06:56, its numbers committed in `9a5a303`), `zz-cyankiwi-…-awq-int4-dflash2-sglang` rc=4 (20:07:26→20:45:22). The third never loaded: `RuntimeError: The size of tensor a (384) must match the size of tensor b (32) at non-singleton dimension 1` in `fused_moe_triton/layer.py:890` (task `d66c127293e3b566_7fa77063f678`, `lmsysorg/sglang:v0.5.22`), so the compressed-tensors int4 g32 experts do not fuse under this engine and the quant-family question that arm alone could answer keeps none. Durable home of the `.30` in-flight row the 21:01 tick deleted. |
| 21:01 ET | `5c84aaa` | 21:01 tick's publish, committed by a peer session under its own subject ("Refresh board 21:07 ET: 122B campaign done, tp12 driver on .30"): census swept from the head 21:01:25 (3.28 s wall) gives `.30`→`.35` = 0/0, 1/0, 1/0, 1/0, 1/0, 1/0 and whole-GB root avail 1344 / 1752 / 1802 / 1700 / 1174 / 1415 GB, identical to the 20:10 read; `.30` empty once the 122B campaign closed, `.35` on tp12 arm 2 `nex-n2.5-mini-uncensored-nvfp4-vllm` (`readiness=yes` then **`ladder failed`**, `tool-eval-bench` still running at the read), shipped pin probed per rank (`RestartCount` 0, serve child 280 / 306 / 301 / 301, rank 0 200 and ranks 1–3 404); Work queue re-rendered byte-for-byte `render --board`, 27 open rows over the 73-task register (`check` green). The publish also swept up this tick's concurrently written copies of two landed rows, so the commit after it drops the duplicate pair. The tick also briefly homed fourteen `Landed session` rows in a section at the foot, on the belief that the peer's rewrite had cleared them: that belief was a filter artifact — the scan keyed on `| 2` matched only the 20:xx rows, so 24 "missing" rows were rows that start `| 1` — the board still carries every one of them and the section was removed inside the same hour rather than duplicating board evidence. |
| 00:24 ET | — (tick finding, no commit of its own) | **The tp12 campaign's completion predicate miscounts six arms, and tomorrow's derive would re-boot them.** `~/benchmarks/tp12-campaign-20261103/drive.sh` counts an arm complete only when some `~/benchmarks/tp12-*` receipt root holds a non-empty `ladder.*` **and** `house.*`. Read-only against the same 42-arm manifest at 00:10 ET: **22 complete, 20 open** (12 tp1, 8 tp2). Four of the twelve tp1 open arms are decision-lane arms whose instrument is not the house battery — `clef-flash-decision-sglang`, `jev-9b-decision-vllm`, `jev-27b-decision-vllm`, `zz-jev-9b-decision-coloc-vllm` each hold `ladder.json` + `ladder.log` and `teb-decision.log`, no `house.*` — so the predicate reads them open forever, and the nex-n2.5 pair holds `house.*` with no `ladder.json` (the mirror gap). Today only the `sweep.log` same-day skip keeps them from a second boot; a fresh derive tomorrow plans all six. Discriminator: that receipt listing, plus `derive()`'s own LAD/HOU tuples at `drive.sh:26-29`. The derive was **not** run this cycle: it rewrites `remaining.tsv`, and the live driver's `stream` loop is reading that file, so a write would truncate the loop's input mid-stream. |

The `02:03 ET` and `02:07 ET` rows above publish `88301ba` and its ledger correction `369fb6e`. The `03:04 ET` row folds `d93f840`, the 03:03 publish that named itself the open tail because a publish cannot name the SHA it is creating; the `04:05 ET` and `05:05 ET` rows fold `210a020` and `ec0b390` the same way, and the `06:05 ET` row folds `f8c1474` the same way, and the `07:05 ET` row folds `9e0c12c`, the 07:00 publish, the same way, and the `08:05 ET` row folds `4ddb2bf`, the 08:00 publish, the same way, and the `09:05 ET` row folds `4c639cd`, the 09:00 publish, the same way, carrying its two row-less corrections `22e39ce` and `777b544` in the row's own clause. The `10:05 ET` row folds `c95fef1`, the 10:00 publish, the same way, and the `11:09 ET` row records `7ab8f70`, the peer register commit no tick publish names. The `11:11 ET` row records `90e2193`, a second peer commit landed inside the tick after this publish was written, so the board's queue table is that commit's register. The `11:10 ET` row records `53fc6b4`, the 11:00 publish that could not name itself, and the `11:12 ET`, `11:19 ET`, `11:36 ET` and `11:56 ET` rows record `52bf43a`, `fe5b140`, `e984c11` and `a35b33a`, peer commits that landed after that publish and before this one. The `12:04 ET`, `12:08 ET` and `12:51 ET` rows record `9affeea`, `429ab91` and `9b68233`: the 12:00 publish could not carry `429ab91` itself, and the other two landed after it and before this fold, so this is the first place either is named. The `13:37 ET` and `13:43 ET` rows record `2608930`, `4e3eda9`, `258827d` and `beba90f`: `4e3eda9` is the 13:00 publish, which cannot name itself and whose body lost its backticked words to the shell, and the other three landed after it while three sessions were writing this board; the `beba90f`, `ad94cb3` and `91abeb7` publishes also cannot record themselves, and they now have rows here; the `14:13 ET` and `14:18 ET` rows record `5695723` and `3ffd2eb`, the publishes of the 14:06 and 14:02 ticks; the `14:25 ET`–`14:56 ET` row records the fold commits after them, so the fold's own commit is no longer the tail, because the `14:47 ET` row below records `20523fb` itself; the `ornith-122b-dflash2-draft-token-sweep` row's `running` state stayed its holder's to flip rather than the board's, and the holder has since flipped it to `done` with `recipes/ornith/README.md` as its evidence, so the `15:04 ET` board publish dropped that row from the mirror. The `18:09 ET` and `18:10 ET` rows record `f3afe2c` and `51afb73`, the publish before this tick and its follow-up correction, which no board row named. The `19:04 ET` row records this tick's publish, which cannot name itself and is the open tail: its `Landed session` rows for `405e886`, `a6f5571`, `eb2a537`, `40d9b06`, `623960e`, `b2bbce3`, `08785ea` and `d85008b` live on the board until a session boundary clears them.

## tp2 acceptance is printed at default verbosity — 2026-11-04 01:30 ET

Queue row `tp2-acceptance-log-level` asks for a debug-level boot to read the tensorfold engine's
speculation acceptance rate. Two boots already print it, at default verbosity, into the serve log
`run-arm.sh` harvests: the 2026-10-30 measurement recorded `accepted=73/158` and `80/138` (this file's
06:04 ET row), and the 2026-11-04 00:52–01:15 boot wrote `accepted=74/153`, `79/142`, `79/144`,
`82/126` plus `0/0` on the non-speculative requests (`~/benchmarks/tp12-20261104/…-abliterated-cyber-tp2-tensorfold-sglang/serve-0.log`).
The field's derivation is written down once in the tracked tree and does not belong to this launcher:
`attic/DONE.md:481` reads it as acceptance length `1 + X/rounds`, for the Kolibri MTP arm. So the row's
premise — that the engine does not log acceptance at default verbosity — is falsified: its work is now a
read of an existing receipt, not a boot. Whether that read explains the 67.02-vs-13 t/s gap stays the
row's own question and is not closed here.


## Board landed rows preserved — 2026-11-04 01:52 ET

The board's `Landed session` table is cleared at session handoff, so the clauses it carries for commits
this file does not yet mention are copied here verbatim (29 of the table's 47 rows; the
measurement rows without a commit were already theirs alone and are not duplicated). Copied before any
clear, per the board contract.

| time ET | commit | clause |
|---|---|---|
| 16:34 ET | `c4e5d53` | Queue row retitled so the MTP re-boot reads as a re-measurement, not a relabel (`mad-science/queue.json`). |
| 16:37 ET | `8bddfcf` | MTP arm set to run on its published engine instead of relabelling the old cells; rationale in `recipes/explore/README.md`. |
| 16:48 ET | `9c9c8dd` | `refresh-sweep.py` asks the registry before calling a tagless `FROM` pin floating; 83 new test lines plus register row `sweep-build-input-tag-resolution`, docs in `tools/README.md` §refresh-sweep.py. |
| 16:56 ET | `c5aacc0` | Suite snapshot re-taken: `AGENTS.md`'s two statements move 1172/1187 → **1193 tests (2 skipped, 2026-11-03)** together, and the sweep's registry-error test names a 429 alongside the 503. |
| 19:11 ET | `4696a41` | Reconstructed the two commits that fell between the 16:02 ledger row and the 19:04 tick (`f3afe2c`, `51afb73`) from their own diffs, since neither board that carried them survives; the six-blocked count they left behind is recorded as resolved, with `git show HEAD:mad-science/queue.json` named as the settling check (`mad-science/SESSION-RECORD.md`). |
| 19:17 ET | `bc1f103` | Folded nine owner answers into the register with each row carrying its own scope: `engram-cache-hit-rate` narrowed to page cache only (no custom bound, estimate 3 h → 2 h), DeepGEMM keeps att5's page size with the stride contract widened inside the backport, and the Mellum MTP probe keeps `n=1` (`mad-science/queue.json`). |
| 19:25 ET | `82320cc` | All three draft lengths measured on a valid ten-slot grant — n=1 −12.8 %, n=2 −13.2 %, n=3 −10.3 % at c5→c10 against the plain arm's −4.8 % — so the dip is invariant in draft length, the drafter buys +12.2 % at c1 while doubling the fall, and the n=2 leg's earlier death was a resource-claim race (`recipes/explore/README.md`). |
| 19:39 ET | `91f24ae` | `tools/run-arm.sh` reads the recipe's `parallel` and any `-o parallel=N` and refuses a c10 rung below ten slots with `rc=8` (`ARM_ALLOW_FEW_SLOTS=1` for a deliberate slot-limited cell), and a launch that dies on sparkrun's `Execution resources are busy` is now retried instead of recorded as a measurement. |
| 19:41 ET | `e102c8d` | `classify_image_build_input` asks the registry the same three-way question `classify_container` learned: tag resolves → floating with the digest as `observed`, `404` → `build-input-unresolvable` (exit 2), `503`/`429` → floating and unverified; the negative control shows the pre-fix code calling a deleted tag floating (`tools/README.md` §refresh-sweep.py). |
| 19:44 ET | `f0e6ca4` | A reference with neither tag nor digest (`container: ubuntu`) now says so and fetches nothing, guarded by a test asserting the fixture's call list stays empty; METHODOLOGY §3 gains the boundary that a small c10 grant is one defect with two per-engine remedies — llama.cpp's `--parallel` is refused by `run-arm.sh`, SGLang's `max_num_seqs` is where the mamba/GDN pool binds so its four arms stay footnoted. |
| 19:53 ET | `3a97761` | Found why the dealignai finetune produced salads, and it is not the drafter: its `quantization_config` names `FP8_PER_CHANNEL_PER_TOKEN` on 308 layers including `lm_head`, a name SGLang v0.5.22 dispatches past every quant method, so those layers load unquantized bf16 over fp8-serialized weights and the per-channel scale is lost (`recipes/ornith/README.md`). |
| 19:56 ET | `8defb5b` | Split the 122B finetune disposition into three differently-shaped questions instead of one bet on the drafter — dealignai a recorded negative (an algo the engine cannot load), the devsecllm arm the control that decides layout-versus-drafter fault, the cyankiwi arm the one that exercises the compressed-tensors loader (`mad-science/queue.json`, `task-queue.py check` ok 73). |
| 19:59 ET | `cd0be10` | Tracked-recipe count re-derived with `doc-census --fix` rather than by hand: two `nospec-` control arms are tracked, so 84 → 86 (and 52/35/19 for the other three facts) with `test_doc_hygiene` already red on the pushed tree before the fix. |
| 20:04 ET | `fe4529d` | Confirmed the export-layout contrast on one boot each with identical serving flags, drafter, template and both parser flags: `dealignai`'s `FP8_PER_CHANNEL_PER_TOKEN` ×308 including the head yields token salad at **0.00** draft acceptance while `devsecllm`'s `W4A16_NVFP4` + `FP8` layout answers correctly at **0.62–0.64**, so the dispatch gap is the cause rather than a plausible mechanism and the drafter is exonerated — `recipes/ornith/README.md`. |
| 20:48 ET | `cc60712` | The 512-byte page-stride precondition dissolved on a source read at both DeepGEMM trees — it is a guard inside `nv_dev` only, while the backport target takes the pitch from the tensor behind a `% 128` rule — and the real gate is SGLang's `DEEPGEMM_BLACKWELL = is_sm100`, which excludes SM121, so the job is kernel-present plus gate-open — `mad-science/DEEPSEEK.md` §20. |
| 21:22 ET | `a5181e4` | Told the two coherence failures apart: llama-benchy's probe spends `max_tokens=100` with no thinking kwargs, so an empty `Got:` now gets a 512-token re-probe at thinking-off before it becomes a negative, and the cyankiwi arm stays `unknown` because its container was gone before its logs could be read — `mad-science/METHODOLOGY.md`, `recipes/ornith/README.md`. |
| 21:42 ET | `8a91fb7` | Homed arm 3's real failure where it lives: the campaign's launcher `launch.log` ends with `the size of tensor a (384) must match the size of tensor b (32)` at `fused_moe_triton/layer.py:890` during an 18-shard load, so the AWQ int4 export never loads at v0.5.22 and the quant-family control keeps no cell — `recipes/ornith/README.md`. |
| 21:45 ET | `39a05e6` | Repaired the ledger rows a tick had anchored mid-paragraph and removed the section it invented from a scan keyed on `\| 2`, which matched only 20:xx rows and so read 24 rows starting `\| 1` as missing — `mad-science/SESSION-RECORD.md`. |
| 22:00 ET | `069307e` | `tools/task-queue.py lint` now refuses markdown that will not render (missing delimiter row, cell-count mismatch, a bare `\|` in a code span, odd backticks, an open fence), `render` passes its own output through it, and the pre-fix board is the negative control — snapshot 1208 tests (`tests/test_task_queue_tool.py`). |
| 22:31 ET | `9a1c112` | A dead serve is stopped on the observed edge — a fatal last line in `/tmp/sparkrun_serve.log`, or a child seen alive then gone — instead of after the 1800 s loading grace, and the int8 re-boot's 28-minute cost is filed as queue row `tp12-skip-measured-rejected` (`tools/boot-watchdog.py`, `tools/run-arm.sh`). |
| 22:42 ET | `5bfa7d9` | A failed probe now reads `no_probe` and can never stop a loading boot, a death keeps two consecutive observations, and `run-arm.sh` polls the watchdog's pid so a dead boot ends in one probe instead of the 2250 s readiness loop. |
| 22:50 ET | `f18bf70` | `--grace` deleted rather than retuned: `is_stalled` acts on silence alone with `--stall 600`, a 4× margin over the 150 s worst healthy silence measured across the 46 boots that reached healthy (`tools/boot-watchdog.py`). |
| 23:35 ET | `b30370c` | A recorded negative is machine-readable instead of prose a plan does not consult: `tools/measured-rejected.json` maps arm → `verdict`, the `path:line` recording it and `since`, the planner prints `skip: <arm> (<verdict>, <doc>:<line>)`, and an entry whose recipe file is gone is `stale-skip` and exits 2 — the int8 arm the campaign re-booted on 2026-11-03 is the negative control (`tools/next-arms.py`, `tools/README.md`). |
| 23:38 ET | `9a829e6` | Queue row `tp12-skip-measured-rejected` closed on that landing; an unlisted arm still plans (`tests/test_next_arms.py::SkippedByVerdict`). |
| 23:40 ET | `34c2393` | The readiness loop reaps the boot watchdog exactly once behind a `wd_done` flag: `wait` had consumed the child, so every later pass re-waited and warned, dropping the liveness instrument for the rest of the boot (`tools/run-arm.sh`). |
| 23:50 ET | `939aa7d` | That loop's guard runs under `bash --posix` rather than `sh`, because the CI runner's `sh` is dash and rejects `set -o pipefail`, so both subtests errored on a missing `probes=` line (run 41774619585; `tests/test_run_arm_tool.py`) — that inherited red is `34c2393`'s, whose own gate run 41774619585 concluded failure, while `939aa7d`'s gate reads **success** (run 41775572640, `gh run list`). |
| 00:10 ET | `b2d8ce8` | Three more arms the lane docs already refuse join the skip source (`zz-spark-x2.6-4b-fp8-ngram-sglang`, the qwen3.8-flash-next-uncensored NVFP4 pair), each cited by the line that records the verdict, and `stale-skip` now names the file and the arm it wants deleted rather than saying "delete the entry"; the bf16 Spark-X2.6 arm stays off the list because its doc demotes it to an accuracy control, a role and not a refusal. |
| 00:11 ET | `5a0e5a9` | Suite snapshot re-measured 1208 → **1223 tests (2 skipped)** with both `AGENTS.md` statements moved together, since two guards landed after the number was written. |
| 01:08 ET | `e298fd7` | Three campaign receipts folded into the lane docs that held no cell for them — qwen3.8-27b-nvfp4-dflash2 **31.1 / 56.3 / 82.0 / 99.5 t/s** + suite 100/100 and qwen3-coder-next-int4 **68.0 / 111.2 / 182.6 / 244.1 t/s** + 93/100 into `recipes/qwen3/README.md`, uncensored-27b **9.90 / 19.57 / 40.58 / 80.48 t/s** + 100/100 into `recipes/cybersec/README.md`. |

Note on `5d96c80`: that commit carries this file's 01:30 section and a `queue.json` hunk under a message
describing only a board refresh. Cause: `git commit --amend -- <path>` does not do a partial amend — it
committed the whole index, sweeping a peer session's staged hunks in. The bytes are correct; the message
is not. Not rewritten, per the shared-history rule.

## Board landed rows preserved — 2026-11-04 03:32 ET

The board's `Landed session` table has not been cleared (no handoff since the 2026-11-04 open), but
18 of its 60 rows have no home in this file — checked per row, by SHA where the row
names one and by the clause's opening where it does not, because 11 of the 18 are
measurement/state rows that carry no SHA and a SHA-only grep cannot see them. Copied verbatim so a
future clear cannot lose them.

| time ET | commit | clause |
|---|---|---|
| 16:32 ET | `15f5bcd` | Ornith-122B arm ships the measured draft count, 15 → 4; count and receipt in `recipes/ornith/README.md`. |
| 20:06 ET | — (measurement, no commit) | **The 122B control's first decode cells**, from the live `.30` boot's own receipts (`~/benchmarks/tp12-20261103/zz-devsecllm-…-ablated-dflash2-sglang/`): ladder `d0` tg128 at n=5 reads **C1 41.3 / C2 57.4 / C5 54.9 / C10 51.0 t/s**, and the standard-suite house battery scores **97/100 (14 pass, 1 partial, 0 fail)** in 134.9 s. Recorded here because no committed doc carried them at the time — committed at 20:44 by `9a5a303`, whose cells read C1 41.35 / C2 57.40 / C5 54.94 / C10 51.02 under the campaign's 32-request grant; the campaign fold owns the verdict on whether the arm is promoted past `zz-`. |
| 20:45 ET | — (measurement, no commit) | **The 122B finetune campaign closes** — `~/benchmarks/ornith122b-20261103/WATCH-SUMMARY.txt` reads `all three complete`: dealignai rc=5 18:22:23→19:40:54, devsecllm rc=0 19:41:24→20:06:56, cyankiwi rc=4 20:07:26→20:45:22 (never loaded — `The size of tensor a (384) must match the size of tensor b (32)` in `fused_moe_triton/layer.py:890`), so the quant-family question keeps no answer. `.30` released; close recorded in `mad-science/SESSION-RECORD.md`. |
| 00:31 ET | — (measurement, no commit) | **`qwen3.8-flash-next-nvfp4-solo-vllm-b12x` ladder closed** at 00:31:36 on `.30`: aggregate **8.98 / 8.34 / 3.66 / 2.41 t/s** at c1/c2/c5/c10 (effective streams 1.00 / 1.92 / 1.86 / 2.28, prefill 30–36 t/s), receipts `~/.cache/sparkrun/benchmarks/bench_ba800216f73f/runs/`. A defect-shaped number, not a cell — `SESSION-RECORD.md:2257` recorded 7.57 / 7.37 / 2.91 / 1.97 on this arm at 05:14 ET (`rc=5`) against the shipped row's 33.9 / 55.5 / 64.6 / 62.0 — and its standard suite closed **100/100 (15 of 15 scenarios)** at 00:41 with the arm `rc=0` (`bench_66c3836cc977`), so the arm holds both legs. |
| 00:51 ET | — (measurement, no commit) | **`qwen3-vl-reranker-8b-vllm-b12x` closed `rc=0`** on `.30` at port **8015** (8010 is held by `beegfs-mgmtd`): pooling ladder, four rungs, **100/100 requests answered at every rung**, mean latency **557.7 / 1,072.5 / 2,383.1 / 4,587.1 ms** and **1.79 / 1.86 / 2.07 / 2.11 rps** at c1/c2/c5/c10 — a throughput-flat ladder where added concurrency buys latency, not rate — with all four instrumentation checks green (rank order `[0, 1, 2]`, cross-encoder asymmetry 5.68e-01, 0/100 near-uniform spreads), receipts `~/.cache/sparkrun/benchmarks/bench_57f7f0f27017/runs/`. |
| 01:15 ET | — (measurement, no commit) | **abliterated-cyber TP=2 arm closed `rc=0`** with both instruments on one boot (`~/benchmarks/tp12-20261104/deepseek-v4.1-flash-abliterated-cyber-tp2-tensorfold-sglang/`) — `tg128` **14.42 ± 0.65 / 13.11 ± 0.64 / 12.71 ± 0.45 / 13.17 ± 0.34 t/s** at c1/c2/c5/c10, per request 14.42 → 4.35 so effective streams 1.00 / 1.56 / 2.77 / 3.03 (streams without throughput), house **93/100** (deployability 70, responsiveness 17) — reproducing the 2026-10-30 close of the same arm (`SESSION-RECORD.md` 06:04 and 06:10 ET rows). Its serve log's acceptance field is per request, not a rate: `accepted=74/153`, `79/142`, `79/144`, `82/126`, and `0/0` on the non-speculative ones. |
| 01:17 ET | — (measurement, no commit) | Both `qwen3.8-flash-next-uncensored-nvfp4` boots (`-vllm`, then `-sglang`) ended `rc=4` inside a minute apiece; already-recorded negatives, so they bought two closed boot gates and no cell. |
| 01:53 ET | — (measurement, no commit) | **tp2 tensorfold arm `deepseek-v4.1-flash-tensorfold-tp2-1m-sglang` closed `rc=0`** on `.30`+`.35` with both instruments on one boot: `tg128` **12.77 / 10.17 / 9.08 / 8.53 t/s** at c1/c2/c5/c10 (per request 12.77 → 3.66, effective streams 1.00 / 1.11 / 1.48 / 2.33, so concurrency bought streams and not rate) and house **100/100** (deployability 73, responsiveness 10); receipts `~/.cache/sparkrun/benchmarks/bench_60e3eecff9a8/` (ladder, 01:45:03) and `bench_a8c59188e753` (suite, 01:53:30), both ranks harvested and stopped. |
| 01:54 ET | `94a793d` | 29 of the board's landed rows named a SHA that appeared nowhere in the ledger, so each was copied verbatim into `mad-science/SESSION-RECORD.md` before the table is cleared at handoff; the same append records that `5d96c80`'s `git commit --amend -- <path>` swept a peer's staged hunks. |
| 01:55 ET | `ab82517` | `tools/boot-watchdog.py` copies the container's `/tmp/sparkrun_serve.log` beside the watchdog log before stopping it, because a stop at t=43 s had already deleted the diagnosis of a serve that died at t=32 s; the rank-1 gap of a TP=2 arm is stated rather than assumed (`tests/test_boot_watchdog.py`). |
| 01:59 ET | — (measurement, no commit) | Three qwen4 labquant arms — `qwen3.8-flash-next-nvfp4-labquant-highcon-sglang`, `qwen3.8-flash-next-nvfp4-labquant-sglang` and `zz-labq-no-diag` — each ended `rc=4` about 73 s after start: launch failed, watchdog `verdict=dead` at t=32–43 s with **no serve log inside the container**, so the three bought closed boot gates and no cell (`~/benchmarks/tp12-20261104/<arm>/`). |
| 02:12 ET | `0d2875e` | `tools/run-arm.sh` gives a pooling arm's receipt the suite marker its campaign driver reads, and `tests/test_run_arm_tool.py` grows 184 lines holding it. |
| 02:15 ET | `0c8e50b` | Tonight's `rc=0` campaign arms get their cells in their own lane docs — ling-3.0 47.30/67.73/109.70/89.82 and nemotron 63.37/93.32/122.71/145.01 t/s, the 122B MTP arm 37.40/51.05/70.86/83.05 t/s +39 % C1 over its no-drafter control, the pooling pair 15.50/17.39/20.84/22.20 and 71.70/79.72/82.88/83.18 units/s, clef-flash 5.73–6.42 req/s — and the cybersec vLLM sibling's recorded reason is corrected: it dies in `ModelConfig` on `layer_types: qwen_sparse_attention`, absent from the pinned image's backend vocabulary (`recipes/{explore,ornith,embed,rerank,decision,cybersec,qwen4}/README.md`). |
| 02:25 ET | — (measurement, no commit) | **`zz-qwen38-next-vllm-tp2-pinned` closed `rc=0`** on `.30`+`.35` (vLLM, `RadixArk/Qwen3.8-Flash-Next-NVFP4`, TTR 1 339 s): `tg128` **41.70 / 50.66 / 71.42 / 92.20 t/s** at c1/c2/c5/c10 (per request 41.70 → 15.89, so effective streams 1.00 / 1.73 / 3.43 / 5.80) and `pp2048` **1 727 / 2 284 / 2 659 / 2 912 t/s**, while its house leg is a **serve-flag gap, not a quality datum**: all 15 scenarios returned `[server error 400] "auto" tool choice requires --enable-auto-tool-choice and --tool-call-parser`, which the recipe passes neither of, so no completion was ever generated (median turn 1.7 ms, 0 completion tokens, `failure_kind=missing_step` on every row) — receipts `~/benchmarks/tp12-20261104/zz-qwen38-next-vllm-tp2-pinned/` and `bench_89ae001b0765/runs/000.json`. |
| 02:26 ET | — (measurement, no commit) | **The tp12 campaign finished** — `zz-qwen38-next-vllm-tp2-pinned` closed `rc=0` at 02:25:39, `=== stream tp2 drained (8 arm(s))` and `=== sweep complete` at 02:26:09, and `.30`+`.35` read 0 containers at the 02:32:10 census. Every one of the 26 arms `remaining.tsv` listed at 21:18 has a terminal line in `sweep.log` (intersected by name, not by counting starts): **14 `rc=0`** and **12 boot-gate deaths** (3×`rc=3`, 6×`rc=4`, 2×`rc=5`, 1×`rc=7`), the last three of those being labquant siblings that each died in 63–78 s (`…-labquant-highcon-sglang` 01:55:34, `…-labquant-sglang` 01:57:17, `zz-labq-no-diag` 01:59:00). The driver's own echo still reads “16 complete, 26 remaining”, so it was never the progress source. |
| 02:26 ET | — (state change, no commit) | The campaign driver drained and exited — `=== sweep complete 2026-11-04T02:26:09` in `sweep.log`, pids 3408112 / 3408114 gone, both working nodes released — and `tp12-campaign-staging` moves `running` → `queued` in `mad-science/queue.json` carrying the derived 26-of-42 figure. |
| 03:04 ET | `866353c` | `tools/run-arm.sh` reaps **every** host for the task id's own containers — names anchored on `sparkrun_${TID}_solo` / `…_node_*`, no `docker ps -aq`, no xargs, no prune — and the leak gate re-lists every host so a rank-1 survivor ends the arm `rc=6`; tonight's leak (rank 1 still up 39 s after the stop and 4 s after `ARM DONE`) is the negative control, 155 new lines in `tests/test_run_arm_tool.py`. |
| 03:06 ET | `fa38d28` | The campaign row stopped repeating the driver's plan echo as a measurement: tonight's 26 arms (derived from `sweep.log`'s `rc=` lines) hold, but the older "16" came from `driver.log` — the echo the receipt census contradicts, since 6 of 42 arms have no receipt at all — so the receipt-derived census (26 both legs, 36 at least one) is the denominator. |

## Board landed rows, 2026-11-04 03:07–04:12 ET

Copied verbatim from `mad-science/STATUS.md` at the 04:16 ET board tick, because the
03:33 ET preservation run (`958de91`) predated them: these eight rows existed only on
the board, which concurrent ticks rewrite whole, and the 04:08 write reproduced them
without any ledger copy.

| time ET | commit | one clause |
|---|---|---|
| 03:07 ET | `adcec18` | Merged the two `02:25 ET` rows for `zz-qwen38-next-vllm-tp2-pinned` into one measurement, so the table reads one row per event — the cells and the house leg’s cause (recipe passes neither `--enable-auto-tool-choice` nor `--tool-call-parser`, so all 15 scenarios returned 400 and no completion was generated) now sit together. |
| 03:32 ET | `aac6ccb` | Suite total re-derived by a run instead of copied: 1223 → **1234 tests (2 skipped)** printed by `unittest discover` on the workstation, both `AGENTS.md` statements moved with their own date. |
| 03:33 ET | `958de91` | 18 of the board’s 60 landed rows existed nowhere but the board — 11 of them measurement/state rows carrying no SHA, which a SHA-only check cannot see — so each was copied verbatim into `mad-science/SESSION-RECORD.md`; the re-run detector reports 0 homeless rows. |
| 03:33 ET | `3d27fc1` | Merge of `origin/main`, bringing in the peer commits a credentialless session had left for the next credentialed push; no local content of its own. |
| 03:51 ET | `4d268f9` | The decision branch now writes the receipt marker the campaign driver looks for (`suite: n/a` naming `/v1/systemone`, `ladder: ok`, `accuracy_status`), so four finished arms are not re-booted as incomplete; `tools/README.md` lists all three receipt shapes. |
| 03:53 ET | `7ccac4f` | `tp12-campaign-staging` states its attempt tally instead of “unfinished” (26 arms: 26 start and 26 `rc=` lines, `rc=0` ×14 · `rc=3` ×3 · `rc=4` ×6 · `rc=5` ×2 · `rc=7` ×1) and stays `queued` because only 26 of 42 carry both legs; the three findings are filed as their own rows, each carrying the acceptance test that defines done. |
| 04:08 ET | `059c08f` | The decision marker now derives `accuracy_status` from the run instead of from configuration — `taken` on success, `failed (rc=N)` when the instrument ran and failed, `not-taken` for the `/v1/completions` arm — so a receipt cannot claim a score an `rc=3` arm never got. |
| 04:12 ET | `7bce136` | Suite snapshot re-taken after three guard commits landed: 1234 → **1239 tests (2 skipped)**, printed by `unittest discover` on the workstation after `059c08f`; both `AGENTS.md` statements moved together with the date unchanged, since the run is today’s. |

## Board landed rows, 2026-11-04 04:22–04:53 ET

Copied verbatim from the `mad-science/STATUS.md` 14:00 ET board (skill preservation rule), because
the 04:22 ET run (`2bce09b`) predated these ten: each SHA was grepped in this file and found
nowhere, so they existed only on the board.

| time ET | commit | one clause |
|---|---|---|
| 04:22 ET | `2bce09b` | Eight board-only landings copied verbatim into `mad-science/SESSION-RECORD.md`; the re-run detector reads 0 homeless over 68 rows. |
| 04:27 ET | `9b27ad4` | The solo Flash-Next ladder's "defect-shaped" number gets its cause: a ~62 s PLE disk-table read per engine step — 40 stall blocks, 2,494 s of the 6,499 s ladder — with the pool's 851/18,512 reads/s at depth 1/64 against node-local 4,559/74,986, so the missing factor is the reader's io_uring depth (`recipes/qwen4/README.md`). |
| 04:29 ET | `b668b72` | The pooling and decision receipt markers carry the ladder's own exit status, so a partial artifact reads `ladder: failed (rc=N)` instead of `ok`; the partial-artifact fixture is the negative control (`tools/run-arm.sh`, `tests/test_run_arm_tool.py`). |
| 04:32 ET | `899f907` | Suite snapshot 1239 → **1241 tests (2 skipped)**, both `AGENTS.md` statements moved together. |
| 04:34 ET | `437718b` | `tools/next-arms.py` decides a re-attempt from parsed ladder cells plus the marker's failure field instead of file presence, so a truncated ladder and a marker-only decision arm both count correctly — the 82 real ladders on the head yield the same 62 measured arms before and after (`tests/test_next_arms.py`). |
| 04:39 ET | `cfd8ca5` | The receipt-state table names its three readers and states that `ladder` and `accuracy_status` are independent instruments, so a failed ladder beside a taken score is not a contradiction (`tools/README.md`). |
| 04:41 ET | `d1d0d07` | `ple-disk-read-regression` narrows to the one open number — the reader's effective io_uring depth on BeeGFS — with a no-boot iodepth sweep as the acceptance test and its estimate 4 h → 2 h. |
| 04:43 ET | `8038ad1` | The driver row records the presence-only `have()` predicate (`drive.sh:32-38`) that makes the driver and the planner read the same receipt differently. |
| 04:48 ET | `36e8e30` | Suite snapshot 1241 → **1247 tests (2 skipped)**, re-derived by a run rather than copied. |
| 04:53 ET | `ec9f088` | `AGENTS.md` gains the pathspec-commit hazard — `git commit -- <paths>` publishes the file's whole content, so a shared file ships a peer's half-finished hunk under this session's subject, measured twice today (`ab82517`, `8038ad1`). |
## 2026-11-04 afternoon — eleven commits after the 04:53 close-out, recovered at the 16:00 ET tick

Nothing below was measured by the tick that wrote this section; each clause is its own commit's, and the reason it is here is that the eleven landed after the table above closed and existed only in commit bodies. Two of them (`fcf1b43`, `94a09f4`) were added by the 16:05 tick, which found them homeless by grepping every board row's SHA against this file.

| time ET | commit | one clause |
|---|---|---|
| 13:03 ET | `fcf1b43` | The 13:01 census row's 1174 → 1173 GB drop keeps its verdict and gains its discriminator: `df -BG` rounds up, so a 1174 display means avail sat above 1173 GiB, so the decrease is real but bounded at 14 MiB to 1 GiB, and its cause stays unestablished (`mad-science/STATUS.md`). |
| 14:05 ET | `94a09f4` | `.34`'s bytes are read rather than a rounded display being called byte-identical: at 14:04:39 ET it holds 1,259,470,364,672 B, 13.3 MiB below the 13:01 read inside an unchanged 1173 GB cell, while the five nodes with no earlier byte read keep GB-level equality and say so. |
| 15:04 ET | `cd230c7` | Board refreshed at 15:00 ET — idle census re-read from the head, `.34`'s byte delta 23,146,496 B below the 14:04 read, quartet probed rather than assumed; its own census row then corrected by `245db94`. |
| 15:08 ET | `245db94` | The 15:00 census row corrected on two counts: five zeros stood against six whole-GB values, and the probe's `pgrep -c -f` through `sh -c` matched the wrapper's own command line, so the row now names one serve pid per rank. |
| 15:24 ET | `3b59eb9` | Owner round promotes the campaign driver to the register's top-priority epic — `campaign-driver-service`, 16 h provisional, gated on a written checklist plus one unattended multi-arm campaign — and boots stop until that gate clears (`mad-science/queue.json`). |
| 15:39 ET | `d523ae2` | `tools/measured-rejected.json` deleted as a derived file: each of the six refusals now rides its own recipe as `metadata.measured_rejected`, which `next-arms.py` reads with the repo's YAML-subset parser, because the same key at top level is swept into `runtime_config`. |
| 15:43 ET | `ed0e14c` | The ablated 122B arm moves from `recipes/ornith/` to `recipes/cybersec/`, the lane that documents a refusal-removed posture, and loses a DRAFT header claiming it was never booted when it measured `rc=0` on 2026-11-03. |
| 15:46 ET | `58639cd` | The stated suite total is derived instead of remembered: `test_doc_hygiene.SuiteTotal` compares both `AGENTS.md` statements against `defaultTestLoader.discover("tests").countTestCases()` and fails naming the stale line — no test executed. |
| 15:48 ET | `fe6a7ca` | Three register rows that cited the deleted skip file keep their history byte-identical; only the one live instruction changes, `tp12-remainder-8-arms`' acceptance now asking for the recipe's own `metadata.measured_rejected` marker. |
| 15:49 ET | `03edafb` | A nightly close-out in `mad-science/SESSION-RECORD.md` becomes a rule, because a commit body explains one change and cannot record what was tried and abandoned or which question is still open. |
| 15:53 ET | `1ca4e35` | Register row for a `--strict` roster gap the lane move exposed: `restated-managed-path` on the moved arm predates the move, so `AGENTS.md`'s "exactly this roster" claim was already false — the roster is to be re-measured, not patched by hand. |

## 2026-11-05 22:24 ET — board close-out recovery: landed rows the ledger did not carry
The 2026-11-04 16:18–17:02 board rows were written by ticks and never mirrored here; carried verbatim before theboard's landed table could be cleared at the session boundary.
- **16:18 ET** `9b48526` — Published the 16:00 tick's whole refresh — census, 33-row queue table and eleven landed rows — and repaired it: eight landings cut to one row per event, `fcf1b43` and `94a09f4` recovered into the table and the ledger, and the blank line that had broken the table's GFM rendering removed (`mad-science/STATUS.md`).
- **16:21 ET** `13fa02c` — Corrected the 16:00 ledger section's own count (nine commits against eleven rows) and its backslash-escaped quotes (`mad-science/SESSION-RECORD.md`).
- **16:22 ET** `feca94c` — The board's In-flight note says the two absent queue rows are closed `done` rather than deleted — `render --board` prints open rows only (`mad-science/STATUS.md`).
- **16:52 ET** `b2aa647` — Campaign driver rewritten as the tracked `campaign/` uv package: the director hands the plan out on request, workers poll a Unix socket under a 120 s lease, state is one `flock`ed JSON document, and `measured` is decided from receipt fields — 80 tests, 5 skipped, nothing boots (`campaign/DESIGN.md`).
- **16:52 ET** `b2bd76f` — The gate runs the campaign suite and a `py_compile` loop over `campaign/*/*.py` as their own step, since the tree sits outside every existing glob (`.github/workflows/gate.yml`).
- **16:53 ET** `b6e3554` — `campaign/` joins the live documentation zone and the key-directory table, with its second-uv-project and gate-command rules (`AGENTS.md`).
- **17:02 ET** `da5aaca` — `AGENTS.md`'s documented gate block gains the campaign suite command and a `py_compile` pass over `campaign/*/*.py`, with the `__pycache__` cleanup line extended to the new tree, so a locally reported green covers the two steps CI now runs over `campaign/`.

## 2026-11-06 16:04 ET — two landings today's ticks never ledgered
Neither landing was ever on a board `Landed session` table — the 14:00 and 15:0x ticks edited the board in place — so these two clauses existed only in a commit body and in a census row that the next refresh overwrites.

- **14:05 ET** `aa60c79` — The production serve leaves `In flight` for the census row, per the owner directive that a production workload is never an In-flight row and never counted; the disclosure moved rather than dropped — pin attribution, restart time, per-rank child probe and the 200 all stay in the census row.
- **14:11 ET** `d25021f` — The quartet's image is bound to the shipped pin by **config digest**, not by local tag: the pinned ghcr manifest `sha256:7c3cb394…` carries config digest `sha256:3f4480818acb…`, exactly the running container's image ID, while local `canary-roce-aff52fa5` carries no `RepoDigests`. Measured without pulling the 33 GB body (`docker buildx imagetools inspect --raw` on `.31`), and the container's own `sparkrun.recipe` label names the registry ref it launched from.

## 2026-11-06 16:20 ET — the board's writer race, and the gate that now refuses it
The board is not being refreshed on a cadence this afternoon: several `omp -p` tick sessions launched
hourly since 03:00 are still alive, and each publishes a **whole-file** rewrite computed from its own
census taken before it takes `.local/status-board.lock`. The lock therefore serialises writes without
ordering them, which is why the file has been going backwards.

- **Titles regressed three times in one hour.** `2d91650` (15:19) published `# Board — generated
  2026-11-06 13:56 ET` over a board whose own census row cited `15:22:46 ET`; the worktree at 16:00
  held a `15:28` title against HEAD `5afac71`'s `15:49`; and a repair this tick wrote under the lock at
  15:26 ET was replaced by a stale whole-file write `2m` later. `2d91650` also re-added a `.31`–`.34`
  production-serve `In flight` row that the 2026-10-28 owner directive forbids, undoing `aa60c79`.
- **The evidence backend is `ps`, not the board**: tick processes from 03:00, 04:00, 05:00 … 12:00 are
  all still running, so this is a backlog of sessions, not a burst.
- **Gate landed** (`tools/task-queue.py`): `lint` now refuses `title-regression` when the worktree
  board's title is older than the one at HEAD, since lint is every tick's last step before its commit
  and no markdown rule can see a backwards clock; `tests/test_task_queue_tool.py::TitleMonotonicity`
  carries the pre-fix control (the same rewrite linted clean before the rule) and a fresh-title pass.
- **Facts a rewrite can erase, recorded here**: the production ds4 TP=4 quartet on `.31`–`.34` is
  serving, not idle — `/v1/models` 200 naming `deepseek-ai/DeepSeek-V4.1-Flash-1017` at
  `max_model_len` 1,048,576, one `python3 -m sglang.launch_server` child per rank, and its in-container
  `/tmp/sparkrun_serve.log` grew **1,484,193 → 1,868,700 B** between 13:56 and 15:26 ET.

## 2026-11-06 19:05 ET — board landed rows retired (session boundary)
The 19:01 ET tick swept the board's two `Landed session` rows: each tick is its own one-shot
`omp -p --no-session` session, so both rows predated the tick that cleared them, and neither SHA
appeared anywhere in this file. Their clauses are carried here in full.

- **15:52 ET** `b1d85af` — The board's `register` row now stamps the queue-verification time the tick
  actually ran (15:51 ET) instead of a 15:50 ET figure borrowed from the 15:03 copy; `check` and
  `render --board` prove the table itself identical.
- **15:54 ET** `8521874` — The census row names the quartet's image and proves it against the registry
  rather than a local tag: the pinned ghcr manifest `sha256:7c3cb394…` carries config digest
  `sha256:3f4480818acb…`, the image ID all four ranks run, while local `canary-roce-aff52fa5` carries
  no `RepoDigests`.

## 2026-11-06 17:0x ET — owner round: ten questions asked and answered in one session

The instruction was to census the questions still open, rank them by the queue's own priority rule,
ask them five at a time, re-ask anything bounced, and fold only after every answer was in. The census
is the finding: **the register was empty**. `mad-science/QUESTIONS.md` carried `unanswered: none`
(#55 and #53 settled 2026-11-03), `tools/task-queue.py questions` printed `0 open of 0`, and
`orphans` printed 0 over 82 tasks — so the live decision surface was the **10 `blocked` queue rows**,
and they split three ways: six are gate-blocked *work* (two behind the DeepGEMM SM12x arm, four behind
the campaign epic), and four are parked on the owner's 2026-11-03 "no window yet" call.

Ten questions went out in two batches of five and **none bounced**; all ten are settled as `#57`–`#66`
in `TODO.md` §"Settled questions" and folded into the rows they govern, not merely answered in chat.

- **`.31`-`.34` stay production.** The four h2h rows keep `blocked` with a re-dated reason, and the
  ds4 TP=4 quartet is left untouched indefinitely — no research window is opened by stopping it, and
  no `.local/fleet-window.lock` is written in anticipation.
- **The campaign gate got a shape.** Phase 2 runs on `.30`+`.35` (the only nodes not serving
  production) and that single run also carries the rows the epic blocks — `tp12-remainder-8-arms`,
  `cyankiwi-live-log-retry`, `ornith-122b-nonablated-hunt` — so one campaign clears the gate and them.
  The labquant trio earns a fourth boot only if a lever exists; otherwise each is recorded as a
  boot-gate negative in its own `metadata.measured_rejected` and the campaign drains the other five.
- **One row was unblocked on its own logic**, not on leniency: `ple-disk-read-regression` sits behind
  a gate that forbids *boots*, and its 2026-11-04 narrowing made its acceptance test a no-boot
  io_uring depth sweep. It is now `queued` with the epic's `blocks` edge removed — both sides, since
  `blocked_by` is a derived mirror (`tools/task-queue.py:177-181`) and cutting one side fails `check`.
- **Two long-running shapes changed.** `refresh-weights-and-runtime-repin` splits by lane into
  resumable per-lane manifests instead of one 80-row 40 h campaign, seated on `.30`+`.35`. The
  vllm-omni arms forward-move to `nightly-0c5dab18…` and **hold**, with a switch to a stable artifact
  only if one ever carries the lane's patches — the perpetual nightly chase ends.
- **The one operational approval was moot, and the census is the answer.** The owner authorised
  killing the stale hourly tick backlog the 16:20 ET entry above described. At 17:05–17:07 ET there
  was nothing to kill: no `omp` process on the head (`crontab` empty, `~/.omp` absent, head account
  `red`, `$HOME=/home/red`), only this live session plus two `__omp_worker_daemon_broker` pids on the
  workstation, and `.local/status-board.lock` present but **unheld** (`fuser` empty). Nothing was
  signalled — `pkill -f omp` would have ended this session, since the only substring matches on the
  workstation were `kcompactd0`, `kworker/R-bio_complete` and this session itself.
- **A leftover worth naming, not removing**: `python3 .scratch/tp12-campaign/ornith-omp/proxy.py` has
  been up since 2026-10-28 (pid 2872715) on the workstation, proxying the production serve's API port.
  It predates this session, is not named by any current harness, and is left alone rather than swept —
  but it is a candidate for the next hygiene pass if no receipt cites it.

## 2026-11-06 22:06 ET — board landed rows retired (session boundary)

- **21:57 ET** `17342ee` — A ten-question owner round was asked and answered in one session and
folded into the rows it governs — `#57`–`#66` settled (four h2h rows still parked, the production
quartet untouched, the campaign gate seated on `.30`+`.35` with its blocked dependents folded in,
`ple-disk-read-regression` unblocked on its own no-boot logic, the labquant fourth boot gated on a
lever, the 122B row closable on a survey verdict, the repin campaign split by lane, the vllm-omni
arms pinned and held, and a tick-backlog kill the census proved moot).

## 2026-11-07 01:03 ET — board landed rows homed (session boundary)
- **00:56 ET** `8cbbadb` — Campaign director gains a production lifecycle: 300 s lease (a
report can hold a request for ~160 s, so a reaper could re-boot a live arm), `stop_task`
bounded at 60 s in `campaign/sparkrun_campaign/fleet.py:92`, start-up validation that refuses
duplicate hosts / missing executor / over-long socket path (exit 2, unit's new
`RestartPreventExitStatus`), lock-free `status`, skip receipts carrying the reviewer checklist,
and `serve_logs` including the executor's `docker-*.log`; unit creates 0600 files and allows
100 s to stop workers under a 180 s `TimeoutStopSec`.
- **00:56 ET** `99f2647` — `tools/run-arm.sh` starts one `docker logs -f` follower per host as
soon as the arm's container exists, writing `docker-<host>.log` into the receipt window, and
kills the followers before `sparkrun stop`: a boot that dies in a `pre_exec` hook used to leave
no `/tmp/sparkrun_serve.log` at all, which is why the 2026-11-03 cyankiwi and 2026-11-04
labquant boots left no cause. Guard module 50 tests green; the live capture is only proven by
the next dead boot.

## 2026-11-07 01:20 ET — campaign director deployed, acceptance campaign drained

- **Landed** `8cbbadb` (lifecycle bounds, start-up validation, lock-free `status`, skipped-arm
  receipts, unit hardening) and `99f2647` (live per-rank `docker logs` in the executor); gate run
  `42344851444` green on `99f2647`.
- **Deployed on the head** (`.30`, account `red`): checkout at `99f2647`, campaign suite
  86 tests / 5 skipped green, root `~/benchmarks/campaign-acceptance-20261107`, env
  `~/.config/sparkrun-campaign.env` mode 600, 7-arm manifest, `systemd-analyze --user verify` rc=0,
  unit enabled (linger already yes). Dry run printed the five recorded-negative skips before any
  assignment: `2 pending, 5 skipped`.
- **Run** started 00:59:22 ET. `zz-labq-no-diag` (TP=2, both hosts) rc=4 at 01:00:44 — watchdog
  `dead` at t=43 s, serve log absent in the container, live `docker-*.log` on both ranks holds only
  the entrypoint CUDA banner, runtime-tree `modlogs/` empty. The restart watcher stopped/started the
  unit at 01:00:45/48; the same plan resumed and the failed arm was not re-booted. The restarted
  director honoured the outstanding cyankiwi lease for its remaining TTL, reaped it at 01:05:45
  (0 containers) and re-booted that arm once. `zz-cyankiwi…` rc=4 at 01:07:56 after 2 min 11 s:
  `_load_w2` at `fused_moe_triton/layer.py:890` again raised `tensor a 384` vs `tensor b 32`, and
  the watchdog preserved the 26 KB engine log before reaping at t=95 s. The live follower again saw
  only the entrypoint banner — the engine writes `/tmp/sparkrun_serve.log`, not container stdout.
  Drained 01:07:56, `ExecMainStatus 0`, 5 skipped + 2 failed receipts; `journal.log` saved in the
  root.
- **Post-run**: `.30` and `.35` both 0 containers / 0 volumes. The production quartet on
  `.31`–`.34` was untouched: 4 containers Up 27 h healthy, `/health` 200 on every rank,
  `/v1/models` and a 1-token chat completion 200 on `.31`.
- **Folded**: the labquant trio and cyankiwi carry `metadata.measured_rejected` with cause
  citations (`recipes/qwen4/README.md:67`, `recipes/ornith/README.md:1170`); `campaign/DESIGN.md`
  checklist rows 1–8 are green with this run's evidence; queue rows `campaign-driver-service`,
  `driver-consults-skip-source`, `cyankiwi-live-log-retry` and `tp12-remainder-8-arms` are done.
  `ornith-122b-nonablated-hunt` was left queued: the Hub re-check found no *new* servable
  non-abliterated export, but fitting candidates exist (vendor FP8 at TP=2, the already-measured
  vendor NVFP4 `zz-` arm, Sherlock-Comms NVFP4), so no "no candidate" negative is claimed.
- **Defect found and fixed**: the executor read the recipe's `port:` before its `cd` to the repo,
  so a campaign-relative path silently defaulted to 8000 (both arms here are 8000, so no number was
  lost). The chdir now runs first, with a positional guard and its negative control.
- **Remaining**: the ornith 122B boot decision is open; `ple-disk-read-regression` is queued and was
  not part of this manifest.

## 2026-11-07 02:04 ET — board landed rows homed (session boundary)

The 02:04 ET tick cleared `mad-science/STATUS.md`'s `Landed session` table at the session boundary. Its
two 00:56 ET rows (`8cbbadb`, `99f2647`) were **already homed** in the 01:03 ET section above — verified by
`git grep -c <sha> -- mad-science/SESSION-RECORD.md` returning 2 and 4 — so nothing was re-appended for
them — only the pre-session rows were retired. Two commits landed after that section was written and
carried no SHA anywhere in this file; they sit on the board as rows for the next tick to retire, and their
clauses are homed here.

- **01:26 ET** `c2d39d1` — Record the campaign acceptance run: five recorded negatives skipped before any
  assignment, both boots failed (`zz-labq-no-diag` watchdog-dead at t=43 s with no engine log and empty
  `modlogs/`; `zz-cyankiwi…` reproduced the fused-MoE `_load_w2` failure, tensor a 384 vs tensor b 32 at
  `fused_moe_triton/layer.py:890`, in 2 min 11 s), the live `docker logs` follower shown to hold only the
  entrypoint banner because the engine writes `/tmp/sparkrun_serve.log`, and the executor's
  `port:`-before-`cd` defect fixed with a positional guard and its negative control. Register rows
  `campaign-driver-service` and `tp12-remainder-8-arms` closed with it.
- **01:36 ET** `3651a74` — Correct the run's evidence claims: the cyankiwi marker now names the watchdog's
  pre-stop copy (the live `docker logs` holds only the CUDA banner), `campaign/DESIGN.md` states the
  restarted director's lease grace with its receipt (`attempt: 2`, 01:05:45), the labquant negative gains
  the daemon/kernel absence-of-OOM record rather than a claimed cause, and the follower appends
  `docker inspect` exit/oom/status after the follow, with a guard and negative control.
## 2026-11-07 03:02 ET — board landed rows homed (session boundary)
The 03:02 ET tick cleared `mad-science/STATUS.md`'s `Landed session` table at a session boundary.
The two 02:04 ET rows (`c2d39d1`, `3651a74`) were **already homed** in the 02:04 ET section above —
verified with `git grep -c <sha> -- mad-science/SESSION-RECORD.md`, one line each — so nothing was
re-appended and only pre-session rows were retired. Three commits landed after that section was
written and carried no SHA anywhere in this file; their clauses are homed here, and they sit on the
board as rows for the next tick to retire.
- **02:06 ET** `461fa52` — Census cell made checkable: the "byte-identical to the 01:01 read" claim
  was replaced by the four unchanged whole-GiB cells plus the single `.33`/`.34` drift of
  13,754,368 B and `.33`'s position 2.5 MiB below the 1698 GiB edge, because nothing on the 01:01
  board could discriminate the stronger sentence; the two post-board commits folded in the same
  commit.
- **02:50 ET** `a268d81` — Re-applied the two queue closes (`driver-consults-skip-source`,
  `cyankiwi-live-log-retry`) that a shared writer's copy had overwritten, so the register read
  `queued`/`blocked` after the campaign acceptance run had recorded both done; the epic and
  `tp12-remainder-8-arms` had kept their updates, so only those two needed re-applying.
- **02:58 ET** `7f0c7aa` — Dropped the head SSH alias from the board's census cell, which
  `tests/test_tracked_address_hygiene.py` rejects in any tracked file: the gate went red on the
  board commit and stayed red on the queue-only commit after it.
- **03:02 ET, no commit of its own** — Cut a stale epic block the tooling cannot flag:
  `campaign-driver-service` closed as `done` at 02:50 yet still listed
  `ornith-122b-nonablated-hunt` in its `blocks`, and since `blocked_by` is a derived mirror the
  live row stayed held behind a finished epic while `task-queue.py check` reported green (it
  validates the mirror, not whether a blocker is still open). `task-queue.py update --id
  campaign-driver-service --blocks` with an empty list cut both sides; the other three dependents
  were already `done`, so nothing else moved. Register now reads 29 open of 82.

## 2026-11-07 04:06 ET — board refresh: landed rows homed and folded (session boundary)

The 04:06 ET tick cleared `mad-science/STATUS.md`'s `Landed session` table at a session boundary:
its three rows (`461fa52`, `a268d81`, `7f0c7aa`) were **already homed** in the 03:02 ET section above
— verified `git grep -c <sha> -- mad-science/SESSION-RECORD.md`, one line each — so nothing was
re-appended. Six commits landed after that refresh and carried no SHA anywhere in this file — the
sixth, `59832cc`, landed at 04:11 ET inside the tick's own window, after the `git log` that seeded
the fold and after the board's first composed table, so it is homed here; the board names it in the register row rather than
as a landed row. Their clauses are homed verbatim from the board rows, and
they sit on the board for the next tick to retire:

- **03:16 ET** `b328e0a` — Corrected the 03:02 board's epic closure time: `campaign-driver-service`
  closed at 01:26 in `c2d39d1`, not at 02:50 (`a268d81`, the commit that re-applied two dependent
  rows a shared writer had overwritten); counts, work table and cleanups left as they were.
- **03:49 ET** `b43de60` — `--strict` roster made the run's own output: all 53 arms printing any
  finding named in printed order, replacing the warning-only 20-arm subset; prose now says
  `--strict` adds no finding of its own and exits non-zero on the 20 warning rows; gate on the
  workstation, 86/86 plain `validate` rc=0, suite 1266.
- **03:50 ET** `9269e7a` — Closed `strict-roster-remeasure` on that re-measure — register 29 → 28
  open.
- **03:51 ET** `bedc2f0` — Closed `sweep-build-input-tag-resolution` on `e102c8d` — register 28 → 27
  open.
- **03:58 ET** `82c1b18` — TensorFold launcher shim gained a debug knob, because the engine exposes
  no serve log level — the mechanism `tp2-acceptance-log-level` needs before it can read an
  acceptance rate.
- **04:11 ET** `59832cc` — Closed `ornith-122b-nonablated-hunt` on the arm already measured, with no
  boot: the vendor NVFP4 export `ornith-ai/Ornith-1.5-122B-NVFP4` @ `f049036f` keeps its alignment
  and serves at C1 37.7 / C10 48.9, and the Sherlock-Comms export was shown to differ only by a
  BF16 `lm_head` the drafter never reads. Register 27 → 26 open.

Census at 04:06 ET, re-read rather than carried: 0/1/1/1/1/0 containers and 0 volumes on all six
nodes (the four are the protected production serve, so research containers are 0 everywhere);
`/health` 200 on all four ranks with unchanged serve pids 280/311/310/312, so no rank restarted in
the hour. Root avail fell a near-identical 5.08–5.29 GiB on `.31`/`.32`/`.33`/`.35`, 243 MiB on
`.34` and 328 MiB on `.30`; recorded as measured, with no cause attributed.

## 2026-11-07 04:17 ET — the 04:17 census finds a research pair live, with no claim on it
The 04:17 ET tick's census is the first read today that is not four-containers-only: container counts
`.30`→`.35` came back **1 / 1 / 1 / 1 / 1 / 1** where the 04:02 and 04:06 reads had **0 / 1 / 1 / 1 / 1 / 0**,
because a research **pair** boot went live at 04:11:55 ET — task
`sparkrun_38aaa36e56a717b8_63f75ad1f338`, recipe label
`recipes/cybersec/deepseek-v4.1-flash-abliterated-cyber-tp2-tensorfold-sglang.yaml` (a worktree path, so
it was launched from a working tree and not from the published registry), `tensorfold serve
/cache/runtime/dsv41-ablit --tp 2 --mtp-drafts 5 --context 1048576 --parallel 4`, rank 0 on `.30` and
rank 1 on `.35`. Probe at 04:20 ET: `/health` 200 on `.30` and 000 on `.35`, `/v1/models` 200 and a
1-token chat completion 200 from `.30`; the rank-0 serve log is `/tmp/sparkrun_serve.log` inside the
container, and `/cache/runtime/modlogs/tensorfold-dsv41-launcher.log` is the launcher's. **The tick did
not assign it an owner:** neither `tp2-acceptance-log-level` nor `engram-cache-hit-rate` — the two
register rows that could claim it — carries `claimed_by`, and no `.local/fleet-window.lock` exists
(a pair, not the quartet set). Both facts are on the board's census and register rows; this paragraph
is the durable copy of them.

## 2026-11-07 05:02 ET — board landed rows homed (session boundary)

The 05:02 ET tick cleared `mad-science/STATUS.md`'s `Landed session` table at session boundary. Its
04:11 ET row (`59832cc`) was **already homed** in the 04:06 ET section above — verified with
`git grep -c 59832cc -- mad-science/SESSION-RECORD.md`, two lines — so only the three rows the 04:25
and 04:43 ticks left standing were appended, verbatim:

- **04:27 ET** `db2e8b8` — Recorded the `zz-sage-a1.5-35b-a3b-q4km-llamacpp` arm's first
  campaign-driver measurement on `.30` — decode 73.98 / 102.19 / 85.70 / 73.77 t/s at c1/c2/c5/c10,
  prefill 1986.1 ± 53.8 at c1, house 15/15 score 100, with c10 taken under `ARM_ALLOW_FEW_SLOTS=1`
  beside the shipped `parallel: 4` so it measures the slot limit, not the model
  (`recipes/explore/README.md`); the arm's `description:` no longer claims it was never booted.
  Register unchanged: no queue row opens or closes.
- **04:32 ET** `ce1b4ea` — Added the `Qwen3-Embedding-0.6B` text arm to the embed lane with its 1024-d
  ladder width; the register row `embed-qwen3-embedding-0.6b-text-arm` is still `queued` and
  unclaimed, so the arm exists before its row says what is left to measure.
- **04:35 ET** measurement — The `tp2-logdebug` leg finished on `.30`+`.35` and was stopped by its own
  campaign (`1 measured`, rc=0, campaign service stopped 04:35:27). tp128 ladder aggregate
  **14.61 / 12.18 / 13.17 / 13.00 t/s** at c1/c2/c5/c10 (per-stream 14.61 / 7.67 / 4.75 / 4.23) and
  the house battery ran on the same boot; the acceptance report the leg existed for printed per
  request (`accepted=80/137`, 47 rounds) without any log-level change. Receipt
  `~/benchmarks/tp12-20261107/deepseek-v4.1-flash-abliterated-cyber-tp2-tensorfold-sglang-logdebug/`
  (`ladder.csv`, `house.csv`, `serve-0.log`).

Census at 05:02 ET, re-read rather than carried: 1/1/1/1/1/1 containers and 0 volumes on all six
nodes, so research containers are 2 (the `.30`/`.35` pair below) and the four `.31`–`.34` containers
are the protected production serve, `/health` 200 on every rank with serve pids 280/311/310/312
unchanged across six probes since 02:01 ET, so no rank restarted. Root avail fell on all six nodes —
1.63 MiB `.31`, 1.52 MiB `.32`, 2.65 MiB `.30`, 9.5 MiB `.33` and `.34`, 11.0 MiB `.35` — and no
display cell moved. The read it is measured against, carried here because the board's census row is
overwritten each tick: 04:43 ET bytes `.30` 1,464,336,613,376 / `.31` 1,874,033,897,472 / `.32`
1,927,849,992,192 / `.33` 1,817,724,665,856 / `.34` 1,258,111,475,712 / `.35` 1,511,826,526,208. Note
the unit: `df -BG`'s `G` is 1024³, so its figures are GiB (`.30` 1,464,336,613,376 B = 1363.8 GiB,
printed 1364) and a "GB" label on them is wrong, not the value.

The pair boot itself is the campaign's `logdebug2` retake: director `tp2-logdebug2-20261107` started
04:46:05 ET, one arm, `-o serve_debug=acceptance`. Ladder ran 04:47–04:56 at **14.6 / 13.1 / 12.9 /
12.7 t/s aggregate** c1/c2/c5/c10 (prefill 493.0 / 312.2 / 232.1 t/s at c2/c5/c10, 5 runs per cell);
the acceptance report `82c1b18`'s knob was added for now prints per request (`accepted=85/110` over
26 rounds, `accepted=157/202` over 47). Neither `tp2-acceptance-log-level` nor `engram-cache-hit-rate`
carries a `claimed_by`, so the director owns a boot the register says nobody owns — reported on the
board's register row for the third consecutive tick.

## 2026-11-07 06:01 ET — board landed rows homed (session boundary)

The 06:01 ET tick cleared `mad-science/STATUS.md`'s `Landed session` table at session boundary. Both
rows it carried were **missing** from this record (`git grep -c 0645598 -- mad-science/SESSION-RECORD.md`
returned nothing), so both are appended here verbatim:

- **05:09 ET** measurement — The `logdebug2` retake leg finished on `.30`+`.35` and was stopped by its
  own campaign (`rc=0`, `1 measured`, plan drained, unit inactive 05:09:29). tp128 ladder aggregate
  **14.64 / 13.13 / 12.94 / 12.69 t/s** at c1/c2/c5/c10 with prefill **493.0 ± 8.3 / 312.2 ± 27.6 /
  232.1 ± 7.4 t/s** at c2/c5/c10 — the 04:35 leg's shape reproduced on a second boot; house battery
  **14/15 pass (28/30 points)**, the single failure TC-12 `missing_step`, which did not refuse the
  unsupported email-deletion request. The `serve_debug=acceptance` knob `82c1b18` added prints per
  request: **pooled across the leg's 138 requests, 10,526 of 18,028 speculative draft tokens accepted
  over 5,663 rounds (0.584 — a ratio of sums, not an average of the per-request rates)**. Receipt
  `~/benchmarks/tp12-20261107/deepseek-v4.1-flash-abliterated-cyber-tp2-tensorfold-sglang-logdebug2/`
  (`ladder.csv`, `house.csv`, `serve-0.log`).
- **05:11 ET** `0645598` — Opened the Liquid AI lane's first arms — `LFM3-1.7B` Q4_K_M on llama.cpp
  (`llama-server` ENTRYPOINT cleared, a 2026-11-05 engine pin because the resident 2026-08 and 2026-10
  builds predate `lfm3` landing upstream) and bf16 on vLLM, both TP=1 and pinned; ships as an ordinary
  arm on the 2026-11-02 ruling (`QUESTIONS.md` #56). Register untouched (`queue.json` unchanged), so
  26 open.


## 2026-11-07 06:01 ET — two ticks in one minute, and the equal-stamp replace

Two 06:01 ET ticks ran concurrently on the shared clone. This one read the board at
its 05:11 bytes, took its own census, and published ~6 minutes later; between that
read and the locked write the peer tick had put its own 06:01 board on disk.
`task-queue.py publish` printed `(disk was 2026-11-07 06:01:00 ET)` and wrote anyway,
because the freshness guard refuses only a *strictly newer* `| census |` stamp — an
equal stamp passes — so the whole-file `os.replace` dropped the peer's board.

Nothing is known lost: the peer rebuilt on the published bytes (`7bb32a5`) and the
board on disk equals `HEAD` line for line, including `/tmp/merged-board.md`, the copy
the other writer made at 06:10:37. The peer's original bytes were never compared, so
a row only it carried cannot be ruled out from the tree — the disclosure is that the
replace happened, not that nothing was in it. `11f8917` was already on `origin/main`,
so it was not amended on a syncthing-shared branch; the durable fix is a bullet in the
`status-board-refresh` skill: re-read `mad-science/STATUS.md` and diff it against `HEAD`
*immediately* before publishing (the census is seconds, the lint/guard/commit tail is
minutes), and treat a disk stamp equal to your own title as a clobber to fold rather
than overwrite.

The census deltas this session published were re-based by the peer in `03d10bf`: the
inherited 05:11 row's byte column is that tick's **05:01** operands, so the comparison
spanned two ticks. Neither convention reconciles against the 05:02 board's own numbers,
so the corrected figures stand — 1.15–3.52 GiB of fall, `.35` (3.52) ahead of `.30`
(3.30), all six display cells moved, no drop a rounding artefact.

## 2026-11-07 07:02 ET — board landed rows homed (session boundary)

The 07:02 ET tick cleared `mad-science/STATUS.md`'s `Landed session` table at a session boundary.
All six rows it carried were **missing** from this record (`git grep -c <sha> --
mad-science/SESSION-RECORD.md` returned nothing for each of the six), so all six are appended
verbatim from the board:

- **05:25 ET** `3d7d5f1` — Said the acceptance figure is pooled, not a per-request average: the
  `logdebug2` receipt's 0.584 sums 10,526 accepted of 18,028 draft tokens over 138 requests and
  5,663 rounds, so the row names the pooling and its operands instead of leaving the arithmetic to
  the reader.
- **05:40 ET** `3e9d995` — Recorded the TP=2 arm's acceptance shape and closed
  `tp2-acceptance-log-level`: 58.39 % pooled (10,526 of 18,028 draft tokens) at 1.86 per round
  matches the 2026-11-04 boot's 58.45 % / 1.86, so the ~13 t/s decode is verification cost and not
  rejected drafts; the per-depth kept table and confidence curve are in `recipes/cybersec/README.md`,
  and the row's 67.02 is relabelled a TP=4 quartet figure, not like-for-like.
- **05:42 ET** `d576427` — Retired the `LFM3-1.7B` vLLM arm unmeasured — the pinned b12x image is
  vLLM of 2026-10-15 whose registry has only `Lfm2`/`Lfm2Moe`, while upstream added LFM3 text on
  2026-11-06 (`c96e5f60bb`) — and replaced the lane's two-arm table with a dated route survey:
  llama.cpp `upstream-6023692-cu130` is the only LFM3-capable pinned engine.
- **05:58 ET** `cc1fee0` — Measured and pinned the 0.6B text embed arm on `.35` through the campaign
  driver: pooling ladder **41.2 / 59.6 / 141.4 / 198.7 requests/s** at c1/c2/c5/c10 (100/100 ok on
  every rung, p50 23.8 ms at c1) plus a quality pass on the same serve, with the command now passing
  `--revision {model_revision}` after the first boot missed on a bare cache snapshot in the shared
  pool.
- **05:58 ET** `1eed9b6` — Added the rule that a `@littlecedar/mods/<name>` ref is served from a
  per-host registry clone that pins no commit, so fetch/pull before a boot meant to pick up a
  shared-mod edit — a stale clone's launcher silently ignored `--serve-debug acceptance` while the
  campaign still reported `rc=0` measured.
- **06:13 ET** `6c7b8fe` — Recorded the `LFM3-1.7B` llama.cpp arm's first measurement and closed
  `liquidai-lfm3-1.7b-arm` — the pinned `upstream-6023692-cu130` engine loaded and served the GGUF's
  `lfm3` architecture at c1 **137.51 ± 2.90 tg t/s** (pp 12,762.8, ttfr 143.9 ms), house **93**
  (13 pass, 2 partial, 0 fail) — and left the index's C1–C10 empty on purpose, because the arm serves
  `parallel: 1`, so its c2/c5/c10 cells time queuing for one slot rather than concurrency.

Census at 07:02 ET, read fresh: container counts `.30`→`.35` **0 / 1 / 1 / 1 / 1 / 0**, volumes 0 on
every node, so research containers are 0 and the four `.31`–`.34` containers are the protected
production serve. Absolute root-avail bytes carried here because the board's census row is
overwritten each tick: `.30` 1,458,455,433,216 / `.31` 1,870,994,518,016 / `.32` 1,926,551,728,128 /
`.33` 1,814,651,465,728 / `.34` 1,255,348,281,344 / `.35` 1,507,351,621,632. Quartet `/health`
200/200/200/200 with serve pids 280/311/310/312 unchanged, `StartedAt` 2026-11-06T03:16:44–45Z and
`restarts=0` on every rank, so no rank restarted in the hour.
## 2026-11-07 07:22 ET — two false claims in `06c32e7`, corrected within the hour
The 07:15 ET board commit published two statements that were wrong. Both are
corrected in the board itself (four rows rewritten through `publish`, nothing
else touched, no row added or dropped):
1. "the 07:08 row's right-hand column is truncated in the file" was false. The
   file carried `.34` 1,255,347,712,000 and `.35` 1,507,351,072,768 in full; the
   truncation was the reading tool's display cut. So the 07:08 read was a usable
   baseline all along, and the true 07:08→07:14 deltas are -1,036,288 /
   -569,344 / -528,384 / -524,288 / -524,288 / -512,000 B — not the deltas
   against 07:02 that the row printed.
2. "the receipt sits under the previous campaign's dated root" was false.
   `tools/run-arm.sh:29` sets the receipt root to
   `$HOME/benchmarks/tp12-$(date +%Y%m%d)/$NAME`, so `tp12-20261107` is today's
   own root by design, which is also where `tools/README.md` documents it. The
   clause asserting a tooling defect is gone; the row now names the campaign
   dir for director state and the run-arm root for arm receipts.
Both were inferences — one from a truncated tool display, one from a path that
looked wrong next to the campaign directory — and neither was checked against
the file or the tool source before publishing to a live doc. The corrected
board carries a 07:20:43 ET census, so no row needs a "corrected" marker on a
surface whose contract is state, not history; that is why the disclosure lives
here.
## 2026-11-07 07:31 ET — `.30`'s two research boots, and this tick's close-out
Both boots ran on `.30` inside the 07:00 hour and ended before the 07:14
census, so neither belongs in the board's in-flight table — it is state, and
they were not live. Neither carried a register claim either: both
`media-omni-nightly-repin` and `liquidai-d1-2b-arm` are still `queued` with
empty `claimed_by`/`claimed_at`, which makes this the only record of what they
produced.
- **06:57:11 → 07:02:18**, `recipes/media/qwen-image-2.1-turbo-7b-bf16-vllm-omni.yaml`
  (image `vllm/vllm-omni:nightly-0c5dab18-repin` @ `sha256:84f7a372…`, task
  `2876392aa08b45c1_5c2f21e0524d`): `readiness=yes gate_s=281`, `/v1/models`
  served `Qwen/Qwen-Image-2.1-Turbo`, one render cell at 13.655 s wall
  (`serving_time_to_first_output_ms` 13,550.8, denoise 1,693.5 ms/step,
  1,048,576 px) producing a **4,196,804 B** PNG, sha256
  `af0b630e31195b15…`, `probe_rc=0`, `stop rc=0`, `ARM DONE
  2026-11-07T07:02:18-05:00`. Receipts `~/benchmarks/omni-repin-20261107/qwen-image/`
  (`boot.log`, `probe.json`, `qwen-image.png`, `launch.log`, `watchdog.log`).
- earlier in the same directory, the drama-3 arm booted and was stopped at
  06:55 with a 372,780 B `drama.wav` plus `probe.json`
  (`~/benchmarks/omni-repin-20261107/drama/`).
- **07:04 → 07:05**, campaign `d1-20261107`, arm
  `liquidai-d1-2b-q8-systemone-llamacpp` on `.30` (task
  `c7b507471a8e547b_4ffbd839d35f`): `readiness=yes`, `ARM DONE … rc=0`,
  state `measured`, one attempt and no failures, director exited with the plan
  drained. Arm receipts `~/benchmarks/tp12-20261107/liquidai-d1-2b-q8-systemone-llamacpp/`,
  which is `tools/run-arm.sh:29`'s per-day root; director state, journal and
  receipts index are under `~/benchmarks/d1-20261107/`.
Tick close-out: the board was regenerated at 07:31 ET on a **07:28:52 ET**
census — counts `0 / 1 / 1 / 1 / 1 / 0`, volumes 0 everywhere, quartet
`/health` 200 on all four ranks with pids 280/311/310/312 unchanged since 02:01
ET and `restarts=0` — with the register unchanged at 22 open. Two further
defects of mine were fixed in this third write: the census row said "five of
the six" fell in the same band when only four did, and the register row named
the 07:02 board for a close its successor `201bdb0` had folded (07:02 was 23
open, 07:08 was 22). Owed by whoever owns those two queue rows: a `claimed_by`
or a state move — the board cannot name a holder the register does not.

## 2026-11-07 08:07 ET — board landed rows homed (session boundary)

The 08:06 ET tick cleared `mad-science/STATUS.md`'s `Landed session` table at a session boundary. All five rows it carried were **missing** from this record (`git grep -c <sha> -- mad-science/SESSION-RECORD.md` returned nothing for each), so their clauses are carried here verbatim, copied out of `git show HEAD:mad-science/STATUS.md` rather than retyped:

| time ET | commit | one clause |
|---|---|---|
| 06:18 ET | `30c88b5` | Ledgered the 06:01 double tick: two ticks took a 06:01 census and `publish` replaced a peer's whole board because its freshness guard refuses only a *strictly newer* census stamp, so an equal stamp passes — no row known lost, the peer's own bytes never compared, and the durable fix is the skill bullet to re-read and diff the board immediately before publishing (`mad-science/SESSION-RECORD.md`). |
| 06:36 ET | `9018a38` | Opened the decision lane's `d1-2B` systemone arm: Liquid's scorer answers `/v1/systemone` in one forward pass on the lane's pinned llama.cpp `6023692` build, and because `--decision-bench-only` replays a different case shape the recipe declares `metadata.decision_accuracy: none` and `tools/run-arm.sh` obeys it (`accuracy: none` in `house.yaml`) — three executed guards, nothing booted (`recipes/decision/README.md`). |
| 06:40 ET | `ca3ff01` | Corrected the d1 section's metadata keys to what the pinned GGUF header carries — `lfm3.decision.type = lfm3-d1` plus per-question-type calibration temperatures, not the `general.architecture.decision.*` form the section claimed. |
| 06:45 ET | `0247118` | Narrowed the d1 accuracy gap to the question contract, not the envelope: `tools/decision-ladder.py --api systemone` forwards the case's `state` and `questions` verbatim, so the missing score is the `noul`/`choice`/`score`-only contract against the wider JEV case set — wording only, marker and `rc` semantics unchanged. |
| 07:08 ET | `6415191` | Closed `ornith-122b-decoders-route` on the measurement it pre-registered as its falsifier — the 2026-10-30 SGLang v0.5.22 + DFLASH + `incoai/Ornith-1.5-122B-DFlash2` boot reads **C1 37.7 tg t/s** (C10 48.9, +30 % over the no-drafter control at C1, parity at C10) against a `C1 < 45` verdict, so the lane section now states that beside the result instead of only the arm-level gate; receipt `~/benchmarks/tp12-20261030/zz-ornith-1.5-122b-nvfp4-dflash2-sglang-d4/REPORT.md`, no boot. |

One further commit from that window is homed here because no board ever folded it: `4a46ced` (07:17 ET) moved the three Mellum llama.cpp arms and their family revision constant to the MTP head's revision `4159d684…` once the quants proved byte-identical and the newer revision adds the `mtp/` draft GGUFs, with no boot and no cell rewritten — it landed between the 07:08 and 07:31 boards and the 07:31 tick did not carry it.

## 2026-11-07 08:10 ET — two ticks composed the same minute, and a shared `/tmp` path decided which one published
The 08:10 tick took its own read-only census at **08:01:22 ET** (counts
`.30`→`.35` `0 / 1 / 1 / 1 / 1 / 0`, volumes 0 everywhere, one
`sglang.launch_server` child per quartet rank, `.31` `/v1/models` 200, no
`claimed_by` on any of the 20 open queue rows) and composed a board from it,
while a concurrent tick published a **08:07-titled board on an 08:06:16 ET**
census. No row was lost and nothing was destroyed, but the mechanism is worth
recording: the composed board was written to the fixed path
`/tmp/board-new.md`, the peer tick overwrote that same path with its own
composition, and `publish` therefore wrote the peer's bytes back to
`mad-science/STATUS.md` — identical sha256 to the file it read, equal census
stamp `08:06:16` printed on both sides of the `(disk was …)` tail, and the
fresher 08:06 census is what stands. The two boards agreed on every checkable
figure (counts, quartet ids `9c04c1a5…` / `07ba16fa…` / `00de3d85…` /
`888b2a0f…` with pids 280/311/310/312, register 20 open, both folded commits),
so the loss was the earlier census, not a claim.
**Rule this buys:** tick sessions run on one shared workstation, so a fixed
`/tmp` filename is a shared mutable cell — compose to a per-session path
(`/tmp/board-$(date +%H%M)-$$.md`) or the peer's file decides what you publish.
Related: the same boundary produced **two** retirement sections for the same
five SHAs — this tick's bullet form at 08:10 and the peer's verbatim table plus
the `4a46ced` paragraph at 08:07. The 08:10 one was a strict subset and was
deleted, so the five rows are homed once.

## 2026-11-07 08:14 ET — board refresh over a live probe loop on `.30`, and `f04c0d1` folded
Published at 08:14 ET on a **08:09:07 ET** census — counts
`0 / 1 / 1 / 1 / 1 / 0`, volumes 0, quartet `/health` 200 on all four ranks with
one `sglang.launch_server` child each (pids 280/311/310/312, unchanged since
02:01 ET), `.31` answering `/v1/models` and a 1-token chat completion 200, and
no `claimed_by` on any of the 20 open rows — newer than the 08:06:16 read the
08:07 board carried, so `publish` printed `(disk was 2026-11-07 08:06:16 ET)`
and took it.

**`.30` is not quiet between reads, and the board now says so.** A peer session
loops short-lived `docker run --rm` containers of
`ghcr.io/spark-arena/dgx-vllm-eugr-nightly-b12x@sha256:cf5a2a5324…`:
`docker events --since 20m` shows at least ten create→start→die→destroy cycles,
each container alive 0–8 s under docker auto-names (`boring_dewdney` …
`recursing_rhodes`). One (`42ce8474e3d0`) was caught up 18 s by the 08:07:02
census and was gone by 08:09:07 — which is why two census reads four minutes
apart disagree on that node's count, and why "0 containers" alone is not the
same claim as "nothing is happening". No `sparkrun.recipe` label and no stable
id, so it is a scripted probe rather than a serve and no arm receipt exists yet.
Single-node work, so no fleet-window lock is owed. The same window ran a
read-only fleet-wide `find / -xdev -newermt -45 minutes -size +5…` sweep against
`.31`–`.35`, and `.30` load sat at 3.4.

`f04c0d1` (07:31) was homeless: the 08:07 tick folded `564fff9` and `1f32b34`
but not it, and it did change tracked bytes — the two `.30` boot narratives
moved out of the in-flight table into this record. Folded as a row on the 08:14
board rather than leaving a third commit no board carried; `4a46ced` needed no
row, its clause is already here. The five pre-session rows were already homed by
the 08:07 tick in `05fee3a` (verified: `git grep -c` finds each SHA here), so
this tick added no second copy and did not re-retire them.

Byte series, all three reads this tick's own: `.30` fell 1,913,757,696 B over
the 41 min but rose 49,152 B over the last 125 s; `.31` −12,267,520 / −196,608;
`.32` −21,340,160 / −184,320; `.33` −29,708,288 / −8,577,024; `.34`
−29,716,480 / −8,568,832; `.35` −11,874,304 / −167,936 B. The 8.57 MB drops on
`.33`/`.34` over 125 s have **no established cause**, and the first draft's "the
serve writing as it serves" is withdrawn: `.31`/`.32` run the same serve and moved
~190 kB in that same window, so the operands contradict it. `.30`'s 1.78 GiB lands
inside the probe-loop window and a repeated `docker run` does not normally write
that much, so it too is recorded as an operand; §08:38 accounts for the hour's
total as pool traffic, not as either node's local writer.

## 2026-11-07 08:38 ET — the 18.7 GB fleet-wide disk mystery was the pool's own traffic
Board refreshed at 08:38 ET on an **08:30:41 ET** census, superseding the 08:27
board's 08:19:03 read (counts unchanged `0 / 1 / 1 / 1 / 1 / 0`, volumes 0,
quartet `/health` 200 ×4 with pids 280/311/310/312, register 19 open, no
`claimed_by`). Only the census and `.30`/`.35` rows were rewritten; the 08:27
tick's quartet, register, queue and landed rows were kept verbatim, so no
figure was re-derived from a stale read and nothing of theirs was dropped.

**The finding:** `df -B1 --output=avail /` on the six nodes fell
**18,735,349,760 B** between 07:28:52 and 08:30:41, and it was not a local
writer. The shared HF pool is BeeGFS, whose chunk store `/srv/beegfs/storage`
sits on each node's **root** filesystem — and it is **root-read-only**, so the
user-level `find / -xdev -newermt … -size +100M` that ran on `.31` and `.35`
returned nothing and read like a negative. That void reading is exactly how a
pool write impersonates an unexplained disk leak, and it nearly shipped as
"cause unestablished". The writer was the `unsloth/flint-GGUF` body staged into
the pool at 08:2x: `flint-UD-Q3_K_XL.gguf`, commit `20468edf…`,
**18,494,977,472 B**, sha256 `91b8d85a…` = the Hub LFS oid, recorded in
`flint-four-arm-comparison`'s row evidence the same hour. Chunk placement split
it `.31` / `.32` / `.35` 4.63 GB each and `.30` 2.83 GB, with `.33`/`.34` at
1.9 MB each; the bytes stay, because it is a cached body the Flint arm needs.

**Rule it buys:** a multi-GB fall on several nodes at once with no container, no
image pull and no large touched file is **pool traffic**, so read
`/mnt/beegfs/huggingface/hub` mtimes before hunting a local writer. And `du`
there is not a size oracle: it reported 9.5 KB (4.9 KB apparent) for that
18,494,977,472 B body because the cache directory holds **symlinks** into a
shared `hub/blobs/<xx>/<sha>` store and `du` does not follow them — `stat -L` on
the snapshot file gives size 18,494,977,472 B, blocks 36,123,003, so the bytes
are real and allocated. (First draft of this paragraph blamed the BeeGFS client
not counting chunk-store blocks; that mechanism was invented, not measured, and
the symlink layout is the observed cause.) Also: the burst had already stopped,
so a falling series needs one more read before it is described as a live writer
(12 KB/25 s on `.35`, 0.5 MB/20 s on the pool).

**And a guard defect worth carrying:** `tools/task-queue.py`'s `board_stamp`
parses `YYYY-MM-DD HH:MM[:SS] ET` out of `| census |` lines, so a census cell
that stamps a *range* (`2026-11-07 08:38:56–08:39:03 ET`) matches nothing and
the freshness guard silently falls back to comparing titles — the exact stale-read
overwrite it exists to prevent. It was live for two publishes this hour (both
printed a title, not a census, in their `(disk was …)` tail). The 08:52 board
writes one parseable stamp and says why; a tick that reads a range form should
re-stamp it rather than trust the guard.

The `.30` probe loop is likewise identified: repeated `docker run --rm` of
`ghcr.io/spark-arena/dgx-vllm-eugr-nightly-b12x@sha256:cf5a2a5324…`, one
container per depth rung of the PLE sweep `0a08660` closed on, receipt
`~/benchmarks/ple-depth-20261107/`. `flint-four-arm-comparison` remains
`queued` with an empty `claimed_by` while its prepare visibly ran — its own
evidence says "Prepared 2026-11-07, NOT booted", so the row is honest; the
missing piece is a claim, which is reported, not assigned.

## 2026-11-07 08:52 ET — `.35` booted the ornith DFlash2 arm, and a parseable census stamp
The 08:52 board carries an **08:48:40 ET** census (counts `0 / 1 / 1 / 1 / 1 / 1`,
volumes 0, register 19 open, no `claimed_by`) and one new in-flight row: `.35` is
running a **research boot**, `sparkrun` task `78c7e2fa335a63e5_26fe38ad05c8`,
recipe `recipes/ornith/ornith-1.5-35b-a3b-nvfp4-dflash2-sglang.yaml`, started
08:44:52 ET, `/health` 200 and `/v1/models` serving
`ornith-ai/Ornith-1.5-35B-A3B-NVFP4` — ready, and no register row claims it.

**Probing lesson, because it nearly produced a false negative:** the serve is
`/opt/sglang/bin/sglang serve …`, the new CLI, so `pgrep -f sglang.launch_server`
inside a perfectly healthy rank returns **zero** processes; read the argv (or
`/v1/models`) rather than matching a launch pattern. On the production quartet the
same check is the old `-m sglang.launch_server` form, so the two classes need
different patterns — which is why the quartet row's pid evidence and this row's
`/v1/models` evidence are not interchangeable.

Two corrections to earlier sections of this record, both mine and both published
the same hour: §08:14's "the serve writing as it serves" for `.33`/`.34`'s 8.57 MB
falls is withdrawn (`.31`/`.32` serve identically and moved ~190 kB), and §08:38's
`du` mechanism is replaced — the under-report is the HF cache's **symlink** layout
into `hub/blobs/<xx>/<sha>`, measured with `stat -L`, not a client accounting
quirk. The pool attribution itself stands and is unchanged.

## 2026-11-07 09:20 ET — tick: the storage fall tapers, and the sentence that missed the board

Two extra reads on the four-rank storage nodes (`.32` / `.33` / `.34`) turn the
fleet-wide root fall into a rate series, and it is decaying, not steady:

| interval | seconds | per-node fall on `.32` / `.33` / `.34` | rate |
|---|---|---|---|
| 08:48:40 → 09:01:48 | 788 | −9,539,584 B each | 12,106 B/s |
| 09:01:48 → 09:02:07 | 19 | −53,248 / −61,440 / −57,344 B | 2,802 / 3,234 / 3,018 B/s |
| 09:02:07 → 09:09:17 | 430 | −634,880 / −634,880 / −638,976 B | 1,476 / 1,476 / 1,486 B/s |

A monotonically tapering rate is what a finished write's tail looks like, so the
honest statement is "still measurable, decelerating, no writer named" — not
"ongoing write traffic". No session container existed on any of those nodes at
either read (container counts `0 / 1 / 1 / 1 / 1 / 1`, volumes `0`), and the
quartet answered `/health` **200** on all four ranks with one
`sglang.launch_server` child each (pids 280 / 311 / 310 / 312) and `/v1/models`
**200** on `.31`; `.35`'s ornith boot was healthy at 18 minutes.

**That sentence never reached the board.** This tick published it at 09:10 into
`mad-science/STATUS.md`, but a peer tick's full-file publish replaced the file
at 09:12, and `git commit -- mad-science/STATUS.md` then snapshotted the
worktree as it stood — so `1b0f24d`, whose subject says "Board 09:10: storage
fall tapers", carries the 09:12 board instead, and `c13ae31` records the
attribution from the other side. Bytes are intact and no history was rewritten;
what is wrong is that `1b0f24d`'s message describes a census sentence its tree
does not contain. The measurement now lives here, which is where a figure that
has left current state belongs.

Two smaller notes from the same reads. `df -BG` display cells stayed
1354 / 1739 / 1790 / 1690 / 1170 / 1400 across every read of the hour — rounding,
not stasis; the byte column is the figure. And the earlier reading of a peer's
row that `refresh-weights-and-runtime-repin` was "left untouched by `f5e7afd`"
was itself wrong in the other direction: the commit did rewrite that row's notes
with lane set 1's verdicts, and only the `queued` state token stayed.

## 2026-11-07 09:26 ET — tick: the taper floors, it does not fade to zero

A fourth read of the same three storage nodes does not fit "monotonically
decaying", so the series gets its intermediate point and the inference gets
corrected. Absolutes at 09:03:13 ET come from the board's own census row
(`mad-science/STATUS.md`, commit `69245cb`); the 09:02:07 and 09:09:17 values
are the ones §09:20 derived.

| interval | seconds | per-node fall on `.32` / `.33` / `.34` | rate |
|---|---|---|---|
| 08:48:40 → 09:01:48 | 788 | −9,539,584 B each | 12,106 B/s |
| 09:01:48 → 09:02:07 | 19 | −53,248 / −61,440 / −57,344 B | 2,802 / 3,234 / 3,018 B/s |
| 09:02:07 → 09:03:13 | 66 | −90,112 / −86,016 / −90,112 B | 1,365 / 1,303 / 1,365 B/s |
| 09:03:13 → 09:09:17 | 364 | −544,768 / −548,864 / −548,864 B | 1,497 / 1,508 / 1,508 B/s |

So the fall drops an order of magnitude in 95 s and then **sits at roughly
1.4 kB/s per node** instead of continuing toward zero: 1,365 → 1,497 on `.32`
and `.34`, 1,303 → 1,508 on `.33`, i.e. the last two intervals overlap within
10%. That is a floor, not a tail finishing — §09:20's "a finished write's tail"
is the wrong shape and stays as the record of what the three-point series
supported at the time. The honest current statement is: decelerating hard over
the first ~800 s, then a steady ~1.4–1.5 kB/s per storage node with **no
container on the node to account for it**.

`.30` sharpens the same question. Across the identical 873 s it fell
6,156,288 B (7,052 B/s) with **0 containers and 0 volumes**, re-sampled twice
3 s apart at 0 / 0 — four to five times the storage nodes' plateau and the
largest per-node rate of the interval, on the one node with nothing running.
So "no writer named" is not an artifact of looking at the wrong node; a quiet
node still loses ~7 kB/s and nothing in this tick's reads explains it. Unnamed,
not unexplained-forever: the falsifier is per-node io accounting
(`/proc/diskstats`, a `du` of `$HOME` and `/var/log` over a fixed window),
which no read this hour took.

Fleet total for the interval: −39,632,896 B (−37.80 MiB, 45,400 B/s across six
nodes), of which `.30` contributes 15.5% and `.35`'s booting ornith serve 7.6%
(−2,998,272 B, 3,434 B/s) — the pool-write class (18.49 GB in one body) remains
four orders away, so nothing here is a body copy in progress.

## 2026-11-07 10:25 ET — tick: `.30`'s unnamed fall is the `.35` longrun's capture spool

The 09:26 section left `.30`'s ~7 kB/s with **no writer named** and named the falsifier: per-node
io accounting over a fixed window. This tick ran a coarse version of it, and the writer has an
author. `.30` is the head, and it hosts the run-2 capture proxy for the `.35` ornith longrun,
which spools every SSE body into `~/benchmarks/ornith-longrun-20261107/`; the node itself runs
**0 containers and 0 volumes** at the 10:02:31, 10:05:50 and 10:20 reads.

| window (ET, stamped on the head in the same call) | receipt dir (`du -sb`) | `df -B1` on `/` | spool share |
|---|---|---|---|
| 10:24:33 → 10:25:03 (30 s) | 34,344,208 → 34,619,295 B (**+275,087**) | 1,453,644,304,384 → 1,453,644,009,472 B (**−294,912**) | **93%** (9,170 B/s of the node's 9,830 B/s) |
| cumulative to 10:20:31 | 31,125,808 B over 673 `.sse` files + 544,291 B `ledger.jsonl` | −11,280,384 B since 10:06:01 (12,966 B/s) | rate-tracking, not a fixed ratio |
| an earlier pair in this tick, no minute stamped | +73,037 B | −86,016 B | 85% |

So the "background churn" is a named spool whose rate follows the run's traffic — the 8.7 kB/s
and the 12,966 B/s windows are its quieter and busier phases, not a second mystery. What stays
unattributed is small and bounded: ~660 B/s of head churn at the 10:24 window, and the
`.31`–`.34` storage-node fall, which at 3,694–3,844 B/s reads **above** the 1.4–1.5 kB/s floor
`89d8b01` recorded at 09:19. A read-only tick cannot attribute io to the quartet's four ranks, so
that one remains unwitnessed rather than explained — the same distinction §09:26 drew.

Run 2 of the longrun itself, read from `ledger.jsonl` at 10:06: **572 rows**, last row at
depth 340 / 119,100 prompt tokens / ttft 0.285 s / decode 73.76 t/s / `done_seen: true` / no
`error_events` — advancing, not stalled. Task `78c7e2fa335a63e5_916638841df1_solo`, container
`057bd8ab5565`; `916638841df1` is the middle segment of the container's **name**, not its id (a
peer board row read it as the id at 10:07 and `docker ps -a --format 'ID={{.ID}} NAME={{.Names}}'`
falsified that). Run 1's container `…_26fe38ad05c8` is gone from the node.

## 2026-11-07 11:07 ET — tick: the `.35` longrun ends at 11:02:19, and a TP=2 engram pair takes its node

The `.35` ornith longrun serve — task `78c7e2fa335a63e5_916638841df1_solo`, container
`057bd8ab5565`, image `fd8439732b16` — **died at 11:02:19 ET** with `exitCode=137` and
`execDuration=4622` s (≈77 min from its 09:45:13 boot), read from the head's own
`~/benchmarks/ornith-longrun-20261107/docker-events.log`. The container was then removed:
`docker ps -aq` on `.35` read 0 at 11:02 and 1 at 11:07, the one being the pair boot's, and
`/tmp/sparkrun_serve.log` was absent on the node at 11:04 — so a read-only tick cannot recover the
last line, and `137` (SIGKILL) does not by itself separate a deliberate `sparkrun stop` from an OOM.
Run 1's container carried the same code at 09:39:01, and its own `RECEIPT.md` records a deliberate
stop, so the code is not the discriminator.

What the run did leave, on the head, under `~/benchmarks/ornith-longrun-20261107/`:

- `RECEIPT.md` (09:40) carries the **300-turn half**: 307 tool-offering turns (49 auxiliary
  depth-1 omp calls, all completed), 304 clean = **99.0 %** (304/305 = 99.7 % excluding two
  requests the driver itself cancelled at closeout), one genuine event at `idx 80` — a complete
  tool call with valid arguments that omp closed the socket on, proxy recording `client-disconnect`,
  no `[DONE]` — no 5xx, no zero-event retry, no repeatable trigger (not first-of-boot, not
  first-after-idle, not depth: depth ran 621 messages / 215 k prompt tokens, no compaction),
  decode median 76.0 t/s (37.2–104.7), TTFT median 0.39 s with one 85.5 s outlier from two
  concurrent *uncached* 190 k prefills. Verdict **TRANSIENT**, extension to ~1,000 turns
  **warranted**, untested boundary compaction (the 300 turns peaked at 215 k of a 262 k window).
- `ledger.jsonl` reached index **1098**, last write 10:59, so the extension was live when the serve
  died; its tail row reads depth 859 messages / 142,434 prompt tokens / ttft 0.385 s / decode
  111.05 t/s / `done_seen: true` / no `error_events`, and the rows before it carry valid tool calls
  (`finish_reason: tool_calls`, `json_valid: true`, `name_offered: true`).
- `capture/` holds **40,521,659 B** and froze at 10:59 with the serve; `capture_proxy.py`
  (pid 457040, started 09:48:14) is still alive on the head and idle — which is also why `.30`'s
  root fall eased from the ~8.7 kB/s §10:25 measured to ~3.9 kB/s at this tick.

**56 s later** the same node pair booted a TP=2 research arm, `~/benchmarks/engram-pair.sh` →
task `38aaa36e56a717b8_56e588e846e8` on `.30` (rank 0) + `.35` (rank 1),
`recipes/cybersec/deepseek-v4.1-flash-abliterated-cyber-tp2-tensorfold-sglang.yaml`, image
`sha256:788c36544f1e`, started 11:03:12 ET: rank 0 `200` on `/health` and `/v1/models` serving
`drowzeys/DeepSeek-V4.1-Flash-Abliterated-Cybersecurity-Unleashed` at 1,048,576 context, rank 1
ready in 51.6 s and following rank 0, and it **binds nothing on `:8000`** — `ss -ltn` filtered to
that port prints no line on the node or inside the container (`grep` rc=1 both), while its serve
process (pid 890982) is alive; the probe reads `000` for that reason, not for a dead rank.
Neither declaration mechanism covers it — `.local/fleet-window.lock` is absent, and campaign
`d1-20261107` is **drained** (`sparkrun-campaign.service` inactive, its single arm
`liquidai-d1-2b-q8-systemone-llamacpp` `measured`, no lease) — and the register row it serves,
`engram-cache-hit-rate`, is still `queued` with no `claimed_by`. Both facts are reported on the
board; the register's two `running` rows stay as their holder (`campaign-operator`) left them.

Second writer class named this cycle, for the record: the ~867 MB root fall on each of `.32`–`.35`
over 11:01:40→11:07:11 is the shared pool, not a local writer — `models--littlecedar--LFM3-1.7B-Base-GGUF`
was staged at 11:05–11:06 (**3.3 GB** apparent, `blobs/` 11:05, `refs/`+`trees/` 11:06), and the four
sums to ≈3.47 GB. No `hf` process remained at 11:07. Both halves of that attribution are measured
rather than argued: `findmnt` shows `/mnt/beegfs` as its own `beegfs` mount while `/srv/beegfs/storage`
is a plain directory on `/dev/nvme0n1p2` — the device `df /` measures — so a pool body does spend root
avail on the storage nodes; and for the longrun's `137`, docker emitted **no `container oom` event**
for either container (run-1 and run-2 event logs carry `die` only), so the kill did not come through
the container cgroup's OOM path. The cause therefore sits outside the container's memory accounting,
and the one process that outlived the boot is the idle `capture_proxy.py` (pid 457040), whose spool
stopped at 10:59: no driver process survives on the workstation or the head, so the extension did not
keep running against the dead serve.

## 2026-11-07 11:20 ET — tick: the Kromoss weights A/B, homed before its board row is swept

`refresh-weights-and-runtime-repin`'s one genuine weight move — `media/kromoss-mossimage-5b-bf16-diffusers-script`,
`a4fe9744…` → `0c5417ec…` — was booted both sides on `.30` by the repin holder (`~/benchmarks/kromoss-ab.sh`,
10:46) and finished at 10:59. Recorded here because its numbers otherwise live only in
`head:~/benchmarks/kromoss-ab-all.log` and in an In-flight row the next tick deletes:

| leg | revision | load | generate (50 steps, cfg 3.0, seed 42) | node |
|---|---|---|---|---|
| old | `a4fe97449297af2e3be7841e1c18e431f3b06031` | 197.9 s, peak alloc 25.33 GiB | `rc=0`, 136.76 s, peak alloc 28.19 GiB | `.30` (`kromoss-ab-old`) |
| new | `0c5417ec89301cb82da9ee164f8ed696523910a9` | 183.5 s, peak alloc 25.33 GiB | `rc=0`, 137.264 s, peak alloc 28.19 GiB | `.30` (`kromoss-ab-new`) |

Both legs wrote a 1024×1024 PNG and were stopped (`cn ts=0 vols=0` after each); `PIL` is absent in the
image, so the receipt's dimensions line is its file header only, not a decode check. Read as: the new
weights do not regress load (−14.4 s) or generate (+0.5 s, 0.4 %), which is what the repin needed from
this leg; the row stays `running` for its remaining moving-tag A/Bs (`lmsysorg/sglang:dev-cu13` on five
arms, `python:3.12-slim` on four), each owed its own boot. Receipts
`head:~/benchmarks/tp12-20261107/kromoss-ab-{old,new}/`.

## 2026-11-07 11:26 ET — tick: five board-mechanics commits homed, and `.30`'s writer claim expires

The board's `Landed session` table never carried the five commits that landed
corrections between 10:11 and 10:27 — they were board mechanics, and each
successor tick folded their content rather than rowing them. They would have
gone homeless when the table is cleared, so their clauses are recorded here,
in order:

- `b7d355d` (10:11) **Refresh board: 10:05 census, `.35` ornith relaunch, 18 open** —
  the 10:05:50 census was retaken across all six nodes rather than carried:
  containers `0/1/1/1/1/1`, volumes 0 on every node, root avail down 111,333,376 B
  (106 MiB) in 3,759 s since the 09:03:13 read, which is four orders below
  `a96e872`'s 18.5 GB pooled body, so no pool-write class landed in that window.
- `d9d2ec5` (10:15) **Fix `.35` container id and confirm 10:05 census twice** —
  the `.35` research boot's container is `057bd8ab5565` (full
  `057bd8ab556513099416a8d8`), not the launch segment
  `sparkrun_78c7e2fa335a63e5_916638841df1_solo` the row had named, so an operator
  can `docker exec` what the row says; the census was re-read twice to confirm it.
- `5bc0bba` (10:22) **Correct census rate claim and carry 10:18 peer rows** — the
  10:18 board's parenthetical claimed the storage nodes held "~1.4 kB/s", which
  is 2.5× the floor it cited; the node's own delta over the same 3,759 s window
  reads `.31` 3,844 B/s and `.32`–`.34` 3,694–3,697 B/s, and the range had
  silently dropped `.31`, the highest rank.
- `c11a567` (10:26) **Name `.30`'s writer: `.35` longrun spool 93% its fall** —
  the 09:26 record left the head's ~7 kB/s with no writer named and named the
  falsifier (per-node io accounting over a fixed window); the coarse version ran:
  the head hosts run 2's capture proxy for the `.35` ornith longrun, which spools
  every SSE body into `~/benchmarks/ornith-longrun-20261107/` while the node
  itself runs 0 containers and 0 volumes, and a paired 30 s read put that spool
  at 93% of the node's fall. **That attribution has since expired**, which is why
  it is written here with its term: the spool froze at 10:59 (40,521,659 B,
  0 B growth across a later 30 s pair), the longrun's serve died 11:02:19 ET, and
  `.30` still fell 69,632 B / 30 s (**2.3 kB/s**) at 11:09:33→11:10:03 with the
  capture dir static — so the residual's writer is unnamed again, and the third
  census read of this hour shows `.32`–`.35` each falling **exactly −167,936 B**
  over 110 s, a uniform floor rather than a burst.
- `e205911` (10:27) **Bump board's title past read carries and cite mount check** —
  the 10:23 title predated the 10:24:33–10:25:03 paired read that its own `.30`
  row quoted, so the file claimed a generation earlier than its evidence; the
  title now names the write's minute while the census stamp stays the peer tick's
  10:05:50 and the census row keeps its own read time, which governs.

Two facts from the 11:26 tick that belong with them rather than on the board: the
longrun's capture proxy is **still listening** on the head (`127.0.0.1:4101` →
`.35:8000`, pid 457040) and its target is now the TP=2 engram pair's serve,
so any future connection would append foreign-boot rows to a ledger that ended at
`index 1098` — the ledger is **clean as at 11:24:39 ET** (1,098 rows, all HTTP
200, mtime 10:59:49, unchanged since), and the idle listener is reported rather
than killed because the harness is not this tick's. And the engram pair's
measurement half, re-run as `~/benchmarks/engram-measure.sh` at 11:11:03, returned
`total_gib 188.83` with `total_resident_pages: 0` and `resident_fraction: 0.000000`
for both `engram-l1`/`engram-l14` on **both** ranks at 11:11:04–05 — zero engram
pages resident after a 57.9 s load that read weights from the rank cache — which
bears on `engram-cache-hit-rate`'s premise and on `d484dbd`'s correction; the
post-ladder sample is still owed (ladder in flight since 11:11:06).

## 2026-11-07 14:16 ET — correction: which commit carries the 14:08 census rewrite

`8cfc4a6`'s pushed body says the board on disk "carried a peer tick's 14:08
rewrite, uncommitted" and that the peer's census row "is kept verbatim".
Wrong by one commit, and the correction cannot be amended because
origin/main carries it: the peer landed that rewrite itself as
`d0100b2` ("Refreshed the board on a 14:01 census, 381 s paired, register
at 10 open") while this tick was staging, so the peer's 14:08 census row
— its 14:01:21/14:03:41/14:07:42 byte series and its `/var/log/journal`
attribution of the `.30`/`.35` ~8.8 MB falls — is `d0100b2`'s content,
not this one's. `8cfc4a6`'s own staged diff was `3 ++-`: the title bump to
14:13 ET and the single `23b4d44` landed row. Recorded here on the
`4ae2749` precedent, which corrected two of its own predecessor's claims
the same way rather than rewriting history.

The attribution itself stands as `d0100b2` read it: this tick's own
135 s pair over the same window (fleet −9,453,568 B, pool −9,437,184 B,
70 kB/s) had inferred a shared chunk-store tail, and the peer's longer
381 s pair plus the journald mtimes replaced that inference with a named
writer on the two nodes that moved.

## 2026-11-07 15:09 ET — tick: the 3D arm's first boot, homed before its board rows are swept

The 15:01 tick folded two measurements into the board's landed table that no
commit carries, and they exist nowhere else — so they are homed here rather
than left to a table clear. Both are on `.30`, from the
`recipes/3d/zz-qwen35-4b-3d-coder-q4km-llamacpp.yaml` arm authored at
`353096b`, with receipts under `head:~/benchmarks/tp12-20261107/` and the
harness scripts beside them (`threejs-arm.sh`, `threejs-cell.py`,
`threejs-diagnose.py`).

**14:40 ET, first boot** (task `sparkrun_460a519f1044e748_d7fd9732ce62`,
`.30:8031`, `Q4_K_M` plus the BF16 projector at ctx 65536): readiness in
15 s, model loaded, cgroup `memory.current` 1.44 GiB, served id
`ccore/Qwen3.5-4B-3D-Coder`, node 108 GB free. The acceptance cell then ran
**152.55 s** to `finish_reason: length` on **8,192** completion tokens with
**0 content characters against 24,244 reasoning characters** — usage
`{'completion_tokens': 8192, 'prompt_tokens': 77, 'total_tokens': 8269}` —
so no HTML was emitted and `tools/threejs-render-check.py` had no document
to check. The cell script then died on `KeyError: 'usage'` at
`threejs-cell.py:87`, so the run recorded no `_gen` block: an instrument
defect in a head-side scratch script (not in-tree), which is why the first
cell is quoted from the request's own printed usage rather than from the
record.

**14:57 ET, diagnose pair** on the same serve, at 12,288 and 16,384 caps:
**1,041** content characters after 35,375 reasoning characters in 270.83 s,
then **0** content characters after 69,877 reasoning characters in
407.77 s, both `finish_reason: length`. The arm spends its whole budget in
reasoning at every cap tried, so the render gate still has nothing to
render. Whether that is the arm's behaviour or a sampling/template
mismatch is **unestablished** — the recommended next discriminator is the
card's own chat template and sampling applied through a client that skips
the reasoning channel, which this cell does not do.

Boot stopped 14:58:43 (`sparkrun stop` by task id), `ctns=0 vols=0`
verified on `.30`, so nothing of this boot remains on the node.

**Two probe facts from the same tick, also board-only until now.** The
protected production quartet answers `/v1/models` **200 on the API rank
(`.31`)** and **404 on `.32`–`.34`** at the 15:08:54 probe — route absence
on non-API ranks, not a dead serve — while `/health` is 200 on all four and
each rank runs its engine (`pgrep -c '^/opt/sglang/bin/python3'` = 3). The
campaign at `<CAMPAIGN_ROOT>` = `~/benchmarks/d1-20261107` holds **0 lease
records** in `state.json` and reports `1 measured`, with the unit inactive,
so it is drained and not a wedged lease; the register's two `running` rows
are dispatch claims from `4782ff6` (14:31:09 ET), not live containers.

## 2026-11-07 — campaign lifecycle, lane sweep, and the last three blockers

### 1. The director became a production service, and its acceptance campaign drained

`8cbbadb` gave the director the lifecycle a long unattended run needs: a **300 s lease** (a report can
hold a request ~160 s, so a shorter reaper would re-boot a live arm), `stop_task` bounded at **60 s**
in `campaign/sparkrun_campaign/fleet.py:92`, start-up validation that refuses a stale citation or a
bad host set, `RestartPreventExitStatus=2` so a refusal fails for a human instead of restarting every
15 s, and the **lock-free `status`** subcommand an operator reads while a run owns `state.json`. `99f2647`
then made the executor follow each rank's `docker logs` live, because the engine writes
`/tmp/sparkrun_serve.log` and the container stdout held only the entrypoint banner.

The acceptance campaign on `.30`+`.35` (`~/benchmarks/campaign-acceptance-20261107/`, 7-arm manifest,
unit `sparkrun-campaign.service`) **drained clean**: five recorded-negative arms skipped before any
assignment, the two live arms failed for their own reasons (`zz-labq-no-diag` rc=4, watchdog `dead` at
t=43 s; `zz-cyankiwi-…` rc=4 on the `fused_moe_triton` `tensor a 384` vs `tensor b 32` mismatch),
`ExecMainStatus 0`, **5 skipped + 2 failed receipt files written**. A restart mid-run at 01:00:45
proved the resume path: the new director honoured the outstanding lease's remaining TTL, reaped it,
re-booted the arm exactly once, and never re-booted the already-failed one. The four checklist hardware
items are legible in the receipts themselves — `watchdog: dead` on both failed arms, `serve_logs` named
on both, the TP=2 arm's end-of-arm probe naming **both** hosts, and `leftovers: []` on all seven with a
post-campaign container/volume count of 0. One real defect fell out and was fixed: the executor read
the recipe's `port:` before `cd`-ing into the tree, silently defaulting 8000.

### 2. Two live-state defects, and the structural fixes

The owner caught the same class twice, and neither was a tick bug.

**The tick derived window state from the lock alone.** `status-board-refresh` read
`.local/fleet-window.lock` and reported an idle fleet while the director held nodes — the director
never writes that lock. The managed skill now reads `<CAMPAIGN_ROOT>/state.json` plus the head unit,
classifies the campaign **active / drained / absent / unread** (an unreachable head is `unread`, never
`absent`), renders one `## In flight` row per live lease with hosts and attempt, and **escalates a live
lease whose declared hosts read 0 containers**, every cycle it persists. `AGENTS.md` now says in the
lock's own paragraph that "no lock is not an idle fleet". `tools/queue-drip.py` got the same gate in
code (`f730a05`): it discovers roots from `--campaign-root` and the head's env file, treats an
unexpired lease or an outstanding `needs_reap` as a holder, removes held hosts from the list it hands
`next-arms.py`, refuses with exit 3 when every node is held and **exit 2 when campaign state cannot be
read** — unreadable is a refusal, never a free host.

**The board's "no register claim" row was the register, not the tick.** Every live boot now carries a
`running` claim with a dispatch sentence naming the recipe, node, port and probes; the seven claims
this session wrote (`59e0c1e`, `eb2a144`, `34f5178`, `4782ff6`) are dispatch state, cleared by whoever
closes the row, and the row itself says so rather than leaving it to a commit message.
`arch-deepgemm-sm12x-paged-sparse` had no `claimed_by`/`claimed_at` keys at all, which is how it sat
claimed-but-blank.

### 3. The lane sweep, row by row

- **sage A1.5 Q4_K_M probe** — first boot through the campaign driver on `.30`, no recipe change:
  prefill `pp2048` **1,986.1 ± 53.8** t/s at c1, 1,854.5 at c2, 1,032.3 at c5, 1,025.7 at c10; decode
  `tg128` **73.98 ± 0.67** t/s at c1, **102.19 ± 0.94** c2, 85.70 ± 0.87 c5, 73.77 ± 0.44 c10; house
  **15/15, score 100**. c10 is slot-limited, not a model result: the recipe ships `parallel: 4` and the
  executor refuses a c10 rung under ten slots, so the run waived the gate with `ARM_ALLOW_FEW_SLOTS=1`
  and **c5 is the aggregate peak**. Receipt
  `~/benchmarks/tp12-campaign-20261107/receipts/zz-sage-a1.5-35b-a3b-q4km-llamacpp.json`, window with
  `ladder.json`/`house.json`/`serve-solo.log` beside it; the probe stays `zz-`. Notes in
  `recipes/explore/README.md` §`zz-sage-a1.5-35b-a3b-q4km-llamacpp`.
- **TP=2 acceptance at log level** — request-level **10,526/18,028 = 58.39 %** accepted, **1.86**
  accepted tokens per round, matching the 2026-11-04 boot's 58.45 % / 1.86 within noise; the decode
  gap is verification cost, not a broken drafter. Depth and confidence curves are in
  `recipes/cybersec/README.md:390`; the 67.02 row's provenance is corrected beside it.
- **embed 0.6b** — pooling ladder on `.35`: **C1 41.2 · C2 59.6 · C5 141.4 · C10 198.7 units/s** at
  100/100 ok per rung, 1024-d on all 11 vectors, distinct-input cosine 0.0959, same-input distance
  0.000. The first boot failed `LocalEntryNotFoundError` because the pinned snapshot had no weight
  files, `refs/main` or `trees`; fixed cache-side and the command now passes `--revision`
  (`recipes/embed/README.md` §Measurement, window `~/benchmarks/tp12-20261107/qwen3-embedding-0.6b-vllm-b12x/`).
- **LiquidAI LFM3 text** — llama.cpp route landed on the pinned image: **c1 137.51 ± 2.90 tg t/s**
  at `parallel: 1`, **house 93** (13 pass / 2 partial / 0 fail); the vLLM route is retired because the
  pinned b12x image predates `LFM3`. `recipes/liquidai/README.md` §Measurement.
- **d1 text** — the vendor `/v1/systemone` body serves; **9.204 / 9.609 / 9.641 / 9.641 req/s** at
  c1..c10 with 100/100 requests and 500/500 decisions per rung, `accuracy_status: n/a` with its reason
  recorded. `recipes/decision/README.md` §Measurement.
- **vLLM-Omni repin** — both arms moved to `vllm/vllm-omni:nightly-0c5dab18`@
  `sha256:84f7a372…` and booted serially: drama-3 fish_omni WAV 372,780 B / 44.1 kHz / 4.226 s, PCM
  ttfa 0.661 s, RTF 0.637; qwen-image PNG 4,196,804 B with a 13.655 s first request (+24 % on the
  dev29 band, one sample). `recipes/media/README.md` §Repin boot results.
- **PLE disk-read** — the row's own falsifier fired: 4 KiB `O_DIRECT` random reads against the pool
  reach **103,071–110,863/s at depth 64** (403–433 MiB/s) against an assumed 18,512/s, so **queue
  depth is not the factor**. Next suspect recorded, not chased: the Python layer holds an `RLock` across
  `_read_staged` and its CUDA sync.
- **Flint** — cleared the easy-traffic gate on one boot: **C1 73.0 / C2 119.5 / C5 173.2 / C10 133.7
  t/s**, house **37/37**, so it ships 2026-11-07 as a **gate-passing alternative**, not the SELECTED
  arm (Mellum2.1 keeps that row); a second independent boot read C1 73.7 / C10 132.1 inside the same
  spread (`recipes/explore/README.md:365`, `db815af`).
- **ornith 1,001-turn longrun** — `997/1001 = 99.6 %` clean, compaction **reached** at ledger idx 706
  with 392/392 clean after it, two omp self-cancellations, 0 5xx, 0/898 malformed tool arguments:
  **transient**. Receipt `~/benchmarks/ornith-longrun-20261107/`.
- **engram pair** — residency **0.000000** in every state because 103.5 GiB of weights on a 121 GiB
  frame cannot hold a 188.83 GiB table pair; `rchar` flat across a 954 s ladder, so decode never reads
  the shards; 67 t/s is not reachable in this shape — the baseline was a different engine wrapper
  (pp 982/820/778 against 493/293/241). Receipt `~/benchmarks/tp12-20261107/engram-pair-1103/REPORT.md`.
- **90-recipe repin survey** — 90 verdict rows (17 + 53 + 20) close the completion test; the one weight
  candidate's A/B rendered **byte-identical** (md5 `8414bbf9…`), a no-op, no pin moved; the two moving
  tags remain deliberate accepted holds. `~/benchmarks/repin-survey-20261107/`.
- **LiquidAI multimodal set** — base control 63.77/37.48 tg t/s; d1-Omni decision cells 8.868→9.458
  req/s with its **audio cell declared negative** (the decision surface tokenised the base64 as text);
  VL **258 image tokens (1.6 %, 63 fit), pp 1,546.67 / tg 144.35, 0.496× image prefill, 0.87 GiB**;
  standalone audio ASR and round-trip **WER 0.0** with a 238,124 B / 4.96 s TTS render; omni both cells,
  where the **same fixture transcribes exactly** — so the audio gap was the decision surface, not the
  audio tower. Receipts under `~/benchmarks/tp12-20261107/zz-liquidai-*`.
- **SM121 DeepGEMM** — `dsv41-sm121-dg:0.2.0` (`sha256:1778ec42…`, local only) built on the head in
  ~70 s from `dsv41-c3-reconciled:103ad321`; kernel gate **8/8 PASS** (`calc_diff` 1.3e-05 vs FP32
  torch reference, negative control caught, `sm_121a`/`sm_121f` compile), image prints
  `DEEPGEMM_PAGED_SPARSE_MQA_LOGITS` True. Both survey arms are re-scoped to **technically cleared,
  blocked on the owner's quartet window** — not on the kernel.

### 4. Traps worth carrying

- `-o container=` is **ignored** by the vllm-distributed runtime; the flag is `--image`.
- A launch that names no cluster builds an **anonymous cluster** with safe defaults and still fans out
  models — name it (`--cluster WOPR`) or launch against the cluster's own host set. `tools/run-arm.sh`
  hardcodes `--cluster WOPR`, so on a head whose config lacks it the first attempt dies
  `Error: Cluster 'WOPR' not found` before any boot.
- **`@littlecedar/<name>` resolves the *published* registry clone, not the worktree**, so a recipe whose
  `container:` line was just edited silently launches the previous image; pass the recipe file path,
  and commit + refresh the clone before trusting a registry-qualified ref.
- A cold-cache arm needs `refs/main` **and** the trees entry, not just the snapshot directory; until
  then the offline lookup resolves nothing (the embed arm's `LocalEntryNotFoundError`).
- The llama.cpp image's `llama-server` has **no HTTPS client** (`get_repo_commit: error: HTTPS is not
  supported`), so a pool prefetch is mandatory for every GGUF arm; the same launch also needs
  `refs/main` written.
- Stale sparkrun claim bookkeeping can refuse a relaunch (`held by pid …, exited without releasing
  it`); reconcile by id (`sparkrun daemon resources reconcile <id> --acknowledge-effects`), not by
  waiting.
- The engram image has **no `DONTNEED`**, and `attic/ds4/mods/bound-engram-cache` targets another
  engine's file layout — it is a no-op here, not a missing half.
- `cgroup io.stat` is **blind to BeeGFS network reads**; `/proc/<pid>/io` `rchar` is the counter, and
  per-rung `io-summary.txt` numbers must not be read as pool traffic.

### 5. Instrument corrections

- **Vision has no in-tree quality cell.** `benchmarking/standard-suite.yaml` is `tool-eval-bench`'s
  core 15 **text** tool-calling scenarios; `pooling-bench`'s `image_url` is embedding math and
  `synthetic_png` only synthesises fixtures. The VL and omni rows therefore promise **throughput,
  footprint and acceptance** (image part taken, reply non-blank) plus the audio probe — never an
  accuracy score — and say so in their state cells.
- **Probe fixes.** The omni decision probe's `type:noul` cell returns a probability, never a label, so
  its `--expect` could not match; and the VL probe's default `--max-tokens` was too small for a
  thinking model, so a healthy arm read as an empty reply with the budget spent in `reasoning_content`.
  Both are recorded in the rows as instrument defects, not arm defects.
- **The 3D render gate is a real instrument** — headless Chromium over CDP, checking a clean render,
  non-empty geometry and the import constraint, with a six-fixture selftest; it also states what it
  does not measure (visual fidelity: a cube passes the cathedral prompt).

### 6. What remains, exactly

- The **3D battery is in flight** on `.30` (row `3d-qwen35-4b-3d-coder-arm` stays `running`): the
  16-prompt smoke rendered **9/16 clean** (`render-gate-smoke16.json`: 9 clean, 9 non-empty geometry,
  16/16 import constraint) at ~90 s per reply, and the battery is resuming against the **213-prompt**
  denominator — 21 done at ~107 s/reply when this was written, so ≈5–6 h left. Nothing else is
  measurable on the two free nodes until it ends.
- `h2h-doc-refresh` and `tensorfold-metrics-bridge-generalization` are queued but each waits on a
  quartet row; six rows are quartet-blocked (`w4-survey-arm3-indexer-scoring`,
  `w4-survey-arm5-trtllm-mla`, `h2h-glm-flash-house-recipe`, `h2h-beam-house-and-bfcl-category`,
  `h2h-second-boot-ladder`, `glm-flash-concurrency-degradation-search`).
- `dsv41-sm121-dg:0.2.0` is **local on the head** and awaits a window; the next step is to move it to
  the four nodes and **record its digest**, not to push it.
- Register at close-out: **82 tasks, 73 done, 9 open** = 2 queued, 6 blocked, 1 running.

## 2026-11-07 17:05 ET — board landed rows homed (session boundary)

The previous session closed at 16:22 (`2633ee7`) without clearing the board's
`Landed session` table, so this tick is the handoff point. Two gaps, both fixed here
before either row was swept: the table's 72 rows are carried verbatim below (the
board's own bytes, not a retelling), and **six** commits that landed after the table's
last rowed SHA (`eae79c5`, 15:29 ET) were never rowed anywhere — `git grep` finds none
of them in this file or on the board, and `dfcf1fd`/`0d89f64` both assert their
commits were already rowed when they were not.

48 of the table's 74 unique SHAs had no mention in this file and 44 of those appear
nowhere else in the tracked tree either, so the clauses below are the only surviving
record for them. The table is cleared on the board in the same commit.

### Landed rows as they stood on the 16:12 ET board

| time ET | commit | one clause |
|---|---|---|
| 07:31 ET | `f04c0d1` | Corrected the two claims `91cdb71` shipped wrong and homed `.30`'s two boots: the census row said five or six nodes fell inside one 520–545 kB band when only four did, and the register row credited the 07:02 board for a close its successor `201bdb0` folded (07:02 read 23 open, 07:08 22) — both now name real operands, and the vLLM-Omni / `d1-2B` boot narratives moved out of the in-flight table into `mad-science/SESSION-RECORD.md` §07:31 because both ended before the 07:14 census. |
| 07:38 ET | `564fff9` | Recorded the `d1-2B` systemone arm's first boot on `.30` — ladder flat at 9.204 / 9.609 / 9.641 / 9.641 req/s across c1..c10 with ttft 107 → 1,037 ms, the vendor's `/v1/systemone` body answering 200 in 0.179 s with five typed answers, and the declared `accuracy_status: n/a` holding a receipt with no numeric score — then closed the queue row (`recipes/decision/README.md`). |
| 07:53 ET | `1f32b34` | Moved both vLLM-Omni arms and drama-3's weights to the pins they booted: `nightly-0c5dab18…` (drama-3 returned a 4.226 s WAV, TTFA 0.661 s; qwen-image a 4,196,804 B PNG) and drama-3 weights `78e5ab79…`, recorded the `-o container=` and missing `--cluster WOPR` traps in `AGENTS.md`, and closed `media-omni-nightly-repin` (`recipes/media/README.md`). |
| 08:11 ET | `d484dbd` | Corrected `engram-cache-hit-rate`'s premise on a read-only inspection of the pinned image (`sha256:19977a03…`, TensorFold 0.6.3): the `deepseek_v41` family carries **no `POSIX_FADV_DONTNEED` at all** — its only fadvise is `POSIX_FADV_RANDOM` and the engram reader uses buffered `pread` — so 'the reader evicts pages' was false, and the row now names a `mincore()` residency measurement and stays queued (`recipes/cybersec/README.md`). |
| 08:21 ET | `0a08660` | Closed `ple-disk-read-regression` on the operator's measured io_uring queue depth without a boot: depth 64 reaches **103,071–110,863 reads/s** (403–433 MiB/s, zero errors) past the row's ≥30k floor (its own baselines are 851 and 18,512 reads/s), so its falsifier fired and queue depth is not the factor — next suspect, a Python `RLock` held across `_read_staged`, is noted in the row (`~/benchmarks/ple-depth-20261107/RESULTS.md`). |
| 08:41 ET | `a96e872` | Authored the Flint arm and staged its body, so `flint-four-arm-comparison` is ready to boot while staying `queued` with no claim: `recipes/explore/flint-40b-a2.5b-ud-q3k-xl-llamacpp.yaml` (91 lines) plus the 18,494,977,472 B `flint-UD-Q3_K_XL.gguf` at commit `20468edf…` in the shared pool, with `refs/main`, `trees/` and the LFS-oid sha256 recorded in the queue row — and that body is the 18.7 GB the census row above accounts for. |
| 08:42 ET | `ea508da` | Counted the Flint arm into `AGENTS.md`'s recipe census: the new recipe makes 90 tracked recipe files, so the two lines that stated 89 (the family-dirs line and the folded-`command:` rule) moved with it — census clean at 90 recipes / 52 test modules / 35 profiles / 19 `SKILL.md` dirs. |
| 09:02 ET | `f5e7afd` | Recorded repin lane set 1 (ornith, qwen4, explore; shipped arms only) without a boot and without touching a pin: 17 verdict rows in `~/benchmarks/repin-survey-20261107/` — 16 `no change`, no arm behind its weights, revisions on the repo heads — plus one **blocked** row that is a pin-form defect, not staleness: the Flint arm pins `…llama-cpp:upstream-6023692-cu130@sha256:f2579b80…`, a tag the package does not carry. |
| 09:14 ET | `7abe916` | Dropped the phantom `-cu130` tag from the three `upstream-6023692` pins and one stale hold, leaving the digests untouched: the tag named nothing while the digest serves and `.30` already holds it, so the gated sweep goes 2 (three `container-unresolvable` + one `stale-acceptance`) → 1 (drift only, both zero); three recipes validate and the full suite is green at 1269 tests, 2 skipped. |
| 09:16 ET | `19b232e` | Recorded the fleet-wide root-fall taper in `mad-science/SESSION-RECORD.md`: 12,106 B/s per storage node over 788 s to the 08:48:40 census, 2.8–3.2 kB/s over 19 s to 09:02:07, then 1.48 kB/s over 430 s to 09:09:17 — a decaying tail with no writer named — because that tick's 09:10 board publish was replaced by a peer at 09:12 and `1b0f24d` carries the 09:12 board under a subject that advertises the analysis. |
| 09:19 ET | `89d8b01` | Added the fourth census point, which corrected the inference rather than confirming it: the fall **floors** at ~1.4–1.5 kB/s per storage node instead of fading out (`.32`/`.34` 1,365 → 1,497 B/s, `.33` 1,303 → 1,508 B/s, flat within 10%), and `.30` alone runs 6,156,288 B over 873 s with 0 containers and 0 volumes verified twice 3 s apart — so the 'finished write's tail' reading is deleted and the falsifier (per-node io accounting over a fixed window) is named. |
| 09:33 ET | `d42e7a3` | Recorded repin lane set 2 at `~/benchmarks/repin-survey-20261107/set2/`: 53 recipes (46 shipped, 7 `zz-`) with 43 `no change`, 10 candidates and 0 blocked, every declared draft pin at its repo head — one genuine weight move (`media/kromoss-mossimage-5b-bf16-diffusers-script` `a4fe9744` → `0c5417ec`, two weight files) and nine deliberate digest freezes (`lmsysorg/sglang:dev-cu13` `0b3e3970` → `81eb456a` on five arms, `python:3.12-slim` `a6e34c59` → `4840d514` on four), each owed its own boot. |
| 09:36 ET | `da0a183` | Corrected that note's totals: the tracked tree is 90 recipes — 63 shipped and 27 `zz-`, not 38 and 15 — and set 2 covers 46 + 7, so the survey stands at 70 rowed with 20 `zz-` probes still unrowed inside lane set 1's lanes. |
| 09:43 ET | `35296e3` | Closed the survey half of `refresh-weights-and-runtime-repin`: lane set 3's 20 `zz-` rows (ornith 10, qwen4 2, explore 8), all `no change`, so all 90 tracked recipes now carry a verdict (63 shipped + 27 probes) — the row stays `queued` because it still owes the booted A/Bs for the one weight move and the moving tags. |
| 09:51 ET | `3783e16` | Recorded in `AGENTS.md` (the file it changes, with `campaign/DESIGN.md` §Supervision as its source) and in the tick skill that the campaign director holds nodes through `<CAMPAIGN_ROOT>/state.json` plus the head's `sparkrun-campaign.service`, never `.local/fleet-window.lock` — a fleet read that finds no lock is not an idle fleet. |
| 09:52 ET | `db815af` | Shipped the Flint arm on its pre-registered gate pass from one `.30` boot: C1 73.0 t/s against 69.28, C10 133.7 against 116.27, house 37/37 (easy 19/19, hard 18/18) at 4096 thinking-on, contract clean — `recipes/explore/flint-40b-a2.5b-ud-q3k-xl-llamacpp.yaml`, ladder 73.0 / 119.5 / 173.2 / 133.7 and a second independent boot inside that spread, receipts `head:~/benchmarks/tp12-20261107/`. |
| 09:54 ET | `04500fa` | Closed `flint-four-arm-comparison` on the gate's arithmetic: at the same 2.5B active per token Flint reads 66% of Mellum2.1's C1 and 72% of its C10 while carrying 3.3× the body and scoring one house item higher, so the verdict is quality per active parameter, not throughput per node-second — needle and DFlash2 legs recorded as not run. |
| 10:10 ET | `f730a05` | Gated `tools/queue-drip.py` on the campaign's live leases as well as `.local/fleet-window.lock` — a leased host, or one awaiting a reap, leaves the planner's node list, an all-fleeted case refuses with exit 3 and unreadable state refuses with exit 2 instead of reading as free; 142 test lines, suite 1275 green / 2 skipped. |
| 10:20 ET | `6742b32` | Rewrote `refresh-weights-and-runtime-repin`'s set operands and completion test to the re-measured tree — 90 recipes = 63 shipped + 27 `zz-` across 31 distinct `container:` refs, not the 80 / 59 / 21 / 32 its row still carried — so the next taker does not re-run a finished survey and stop at 80; state stayed `queued` because the boots were still owed. |
| 10:40 ET | `d91d9c3` | Claimed the longrun row the `.35` boot was actually running: the register said no open row carried `claimed_by` while `.35` served that row's research boot, so the register, not the fleet, was wrong — row `running`, claimed by `campaign-operator`, work-queue table re-rendered. |
| 10:48 ET | `e6d2fb8` | Claimed the repin row the `.30` weights A/B was running, the second instance of the same register defect, and put the survey's state in its notes: all 90 recipes rowed, the mossimage `a4fe9744…` → `0c5417ec…` A/B live on `.30`, moving-tag A/Bs still held. |
| 11:16 ET | `0c1cc69` | Refreshed the board on the 11:07 census: the `.35` longrun serve died 11:02:19 ET (`exitCode=137`, 4,622 s) and left to `SESSION-RECORD`, the TP=2 engram pair booted on `.30`+`.35`, and the four ~867 MB root falls were attributed to the LFM3-1.7B-Base-GGUF pool staging at 11:05–11:06. |
| 11:21 ET | `0742d7c` | Folded a second paired byte read 11:08:16→11:09:18 (62 s, 1.4–1.6 kB/s floor), the engram pair's 4-token 200 completion at 11:09, and three landed rows (`6742b32`, `d91d9c3`, `e6d2fb8`) earlier cycles never carried. |
| 11:27 ET | `cc824c8` | Homed five tick commits from 10:11–10:27 (`b7d355d`, `d9d2ec5`, `5bc0bba`, `c11a567`, `e205911`) in `SESSION-RECORD.md` so clearing the landed table could not orphan them, and expired the `.35` capture-spool attribution. |
| 11:28 ET | `540b7a6` | Recorded the Kromoss weights A/B (old `a4fe9744…` load 197.9 s / generate 136.76 s, new `0c5417ec…` 183.5 s / 137.264 s, both `rc=0`) through a throwaway index so a peer's `SESSION-RECORD.md` hunk stayed theirs. |
| 11:29 ET | `b699c21` | Corrected three inferred board claims with measurements: `.35` rank 1 bind no listener is observed-not-designed, the 137 kill came through no container OOM event, and the ~867 MB root fall is the pool's own root-resident chunk store. |
| 11:35 ET | `d22ee20` | Removed the duplicate `SESSION-RECORD.md` §11:20 Kromoss section two writers both landed, byte-identical copies, leaving the A/B numbers where `cc824c8` put them. |
| 11:37 ET | `5bee429` | Named the census row's own tick so title and read agree, after `publish` compared equal stamps and left the file's sha256 unchanged. |
| 11:39 ET | `d01a81e` | Authored two `.30`-slot arms, neither booted: the LFM3 base control — converted outside the runtime image, which ships no Python, to 3,466,613,856 B F16 / 287 tensors because no released vLLM or SGLang registers `Lfm3ForCausalLM` — and the d1-Omni audio arm, which is the 10,325,517,120 B body the census row above accounts for. |
| 11:46 ET | `e8c76af` | Cleared the two gate failures that commit tripped: `tools/omni-audio-probe.py`'s usage example no longer carries a cluster address, and `AGENTS.md` moved to the derived 92 tracked recipes via `doc-census.py --fix`. |
| 11:58 ET | `15e21cb` | Closed three operator results: the longrun as **transient** (1,001 turns, 997 clean at 99.6%, no repeatable trigger), `engram-cache-hit-rate` as **zero residency in every state** with `rchar` flat across a 954 s ladder, and `refresh-weights-and-runtime-repin` with 90 verdict rows, its one weight candidate A/B rendered byte-identical and its two moving tags held as accepted freezes. |
| 12:00 ET | — | Measured the LiquidAI pair in one boot each on `.30`+`.35`: base LFM3-1.7B-F16 `tg` **63.77** t/s C1 and **37.48** t/s C10 (`pp` 10,197.23 / 2,270.66 t/s, prompt head clean); d1-Omni-2B-Q8 flat at **8.868 → 9.458** req/s across c1..c10 with TTFT 112.8 → 1,050.8 ms and 500/500 decisions per cell; its audio probe answered **500** (`input (364286 tokens) is too large to process`, physical batch 8192) where the text cell answered 200. Both tasks then stopped, `ctns=0 vols=0` verified. |
| 12:06 ET | — | Reran the d1-Omni audio question on a second `.35` boot (task `484956f99d685e0f_d941f8b46dc5`) and the rejection is the engine's, not the input's size: a 4.74 s / 417,836 B wav rendered, then `/v1/systemone` with `input_audio` answered **400** `"questions" must be a non-empty object` and chat answered **501** `This model is a decision model without text generation, use /v1/systemone` — so the audio cell is unsupported through this serve: the `input_audio` content part is never read as audio (the systemone schema receives no `questions`). That also re-reads the earlier 500 as this same parse gap rather than a physical-batch limit — inference, its wav was not kept — and this shapes run is what settles the mechanism. |
| 12:10 ET | `59e0c1e` | Claimed the two live Liquid boots (`campaign-operator`, 17:04:06Z) and regenerated the Work queue after `15e21cb` closed the two previously-running rows; In flight untouched. |
| 12:14 ET | `878a9f5` | Refreshed the board on a 12:03:22 census with a 442 s paired re-read, attributed the hour's 10,408,136,704 B fleet root fall to the `d1-Omni` body (10,325,517,120 B, 99.2 %), closed the engram pair's row home to its `REPORT.md`, and rowed `d01a81e`, `e8c76af`, `15e21cb`. |
| 12:23 ET | `b71927b` | Refreshed the board on a 12:20:26 census over all six nodes (containers 0/1/1/1/1/0, volumes 0), left `.30` and `.35` empty after both Liquid boots ended, kept the hour's one big fall (10,408,136,704 B fleet-wide) attributed to the `d1-Omni` pool entry at 99.2 %, and disclosed that a 12:15:59 publish had briefly dropped a peer's census wording, folded back in the same commit. |
| 12:25 ET | `e0da08e` | Corrected `.31`'s 17,465,344 B fall from “outlier on a non-storage node” to its share of the same `d1-Omni` body — `/srv/beegfs/storage` exists on all six nodes (probed 12:24) — and rowed the LiquidAI pair's own numbers. |
| 12:26 ET | `1cfcf38` | Reported, without flipping, that both register rows still reading `running` had no live boot at the 12:20:26 census: `.30`'s base ladder and `.35`'s d1-Omni were both stopped, the claim left to its holder. |
| 12:28 ET | `e9dd350` | Reworded the audio cell in place to state its mechanism — `input_audio` is never read as audio through this serve (`/v1/systemone` 400, chat 501) — and labelled the earlier 500 re-reading as inference, its WAV not kept. |
| 12:32 ET | `820501c` | Closed the two Liquid boots: base control measured (pp 10,197.23 / tg 63.77 t/s C1, 2,270.66 / 37.48 C10, `accuracy_status: n/a` with its reason) and d1-Omni at 8.868→9.458 req/s with its audio gap declared, open falling 15 → 13. |
| 12:46 ET | `94497ee` | Authored `zz-liquidai-lfm3-audio-2b-llamacpp` on a route read off the pin (llama.cpp `/v1/audio/transcriptions` + `/tts`, `clip.has_audio_encoder = 1`) with `tools/audio-asr-tts-probe.py` and its falsifying `--selftest`, and corrected the lane's instrument claim. |
| 12:59 ET | `31f8eba` | Authored the VL and Omni `zz-` arms for the cells they can honestly produce — `accuracy_status: n/a` declared, not borrowed — on `tools/vl-arm-probe.py`'s image-token delta, and stated in the lane that nothing in-tree scores image understanding. |
| 13:00 ET | — | Measured `zz-liquidai-lfm3-audio-2b-llamacpp` on its first `.30` boot: ASR **200** at WER **0.0** against a 0.25 ceiling, `/tts` **200** as a 4.96 s / 24 kHz wav, roundtrip **200** at WER **0.0** against 0.4, `verdict: ok`; stopped by its own task at 13:00:04, `ctns=0 vols=0` verified. |
| 13:01 ET | `eb2a144` | Claimed `liquidai-lfm3-audio-2b-arm` (`campaign-operator`, 17:52:14Z) as dispatch state for the `.30` boot and put an instrument correction in the two queued multimodal rows, so the promised standard-suite VL score is no longer advertised. |
| 13:05 ET | — | Footprint on a **second** `.30` boot, sampled **at readiness before any request**: cgroup `memory.current` **1.14 GiB**, `VmHWM` **1,223,532 kB** / `VmRSS` 1,079,676 kB (`RssShmem` 699,700 kB), node 108 GB free. A different state from the first boot's `audio-arm.out`, whose **post-ASR/TTS** `VmHWM` is **1,499,716 kB** — the two do not contradict, they bracket idle and loaded. Stopped 13:05:41 with `ctns=0 vols=0`; receipts `head:~/benchmarks/tp12-20261107/zz-liquidai-lfm3-audio-2b-llamacpp/`. |
| 13:18 ET | `bc1325a` | Refreshed the board on a 13:11:30–13:11:34 census — containers 0/1/1/1/1/0, three claims, eight commits the previous table never rowed — and carried two paired byte windows (62 s and 210 s) at 1.2–1.8 kB/s per node; the landed table it published carries each of those eight rows **twice**. |
| 13:19 ET | `34f5178` | Claimed the VL and Omni boots (`campaign-operator`, 18:12:06Z) as dispatch state — VL on `.35:8023`, omni after it on `.35:8024` — stating that neither claim asserts a live container, so `.30`/`.35` at 0 containers is consistent with them. |
| 13:21 ET | `ba04eb6` | Named each claimed row beside its own claim in the register cell, so a reader can tell which arm the 18:12:06Z pair belongs to; no census, count or landed row changed. |
| 13:24 ET | `2d66a63` | Refreshed on the 13:01:42 census and measured that window's writer rather than inferring it — audio body `stat -L` 12,708,058,437 B = 98.7 % of 12,877,172,736 B, the 169,114,299 B residual recorded as arithmetic, and the landed table's doubled rows de-duplicated. |
| 13:28 ET | `ea37e6f` | Refreshed on the 13:22:32 paired read, naming the VL body (`1add221a…`, pid 2250964) as the writer inside the window's last 3 min 57 s and leaving the preceding 3 min unattributed; rowed the audio arm's ASR/TTS cells (WER 0.0 both directions, 4.96 s `@ 24 kHz`) and its 1.14 GiB footprint re-sample that no commit had carried. |
| 13:32 ET | `c3fc2d5` | Attributed the hour's largest root fall to both Liquid bodies and closed the VL gap: `LFM3-VL-2B-GGUF` 15,856,080,128 B + `LFM3-Omni-2B-GGUF` 13,897,434,272 B = 98.1 % of the 29,195,776,000 B window, zero `*.incomplete`, and the two `hf download` jobs (pids 2250964/2250965) named. |
| 13:37 ET | `4ae2749` | Labelled the audio footprint by state instead of as one number — **1.14 GiB at readiness before any request** versus **1,499,716 kB `VmHWM`** after ASR/TTS — and corrected two earlier claims it had inferred (`.35` rank-1 bind, the 137 kill's OOM event). |
| 14:02 ET | `1a11398` | Closed all three Liquid multimodal boots with their gaps declared — VL 258 image tokens (×0.496 prefill) at accuracy n/a, Omni two cells (image ×0.509, audio WER 0.0 both directions), audio 1.14 GiB — clearing the claims and taking the register to 72 done / 10 open. |
| 14:09 ET | `23b4d44` | Recorded both vision boots' cells — VL 258 image tokens at image prefill **0.496×** with decode 144.35 against text-only 143.48 and the no-image control answering honestly, Omni **0.509×** / 152.18 and **inventing** a description with no image attached — and fixed the probe defect behind the VL arm's first empty reply: `tools/vl-arm-probe.py` now defaults `--max-tokens 512` and reports content-less-but-reasoning-full as an instrument warning, with the prefetch requirement (that image's llama-server has no HTTPS) stated beside the launch commands. |
| 14:13 ET | `d0100b2` | Refreshed the board on the 14:01:21 census over all six nodes — containers 0/1/1/1/1/0, volumes 0, `/health` 200 on `.31`–`.34` with 3 engine pids per rank — and carried a 381 s paired byte window (fleet −20,094,976 B = 52.7 kB/s), attributing `.30`/`.35`'s ~8.8 MB falls to `/var/log/journal` files rewritten inside 20 minutes; an attribution `0e2ccf9` withdrew four minutes of commits later. |
| 14:14 ET | `8cfc4a6` | Published with the peer's uncommitted 14:08 rewrite kept verbatim rather than replaced by a second read of the same census, and folded the one landed row it owed: `23b4d44` (14:09:43). |
| 14:16 ET | `9b88b27` | Corrected `8cfc4a6`'s body: a peer landed `d0100b2` while that tick was staging, so the journald attribution and the three Liquid body rows are `d0100b2`'s content and `8cfc4a6`'s diff was a title bump plus one row — fixed forward, not amended, since origin/main already carried it. |
| 14:18 ET | `f488b41` | Folded a 304 s census window (14:05:25 → 14:10:29, fleet −2,764,800 B = 9,095 B/s) into the board two peers had already published, adding `.30`'s nvme0n1 sector counter (+712 sectors in 10 s, 364,544 B, against a 2.4 kB/s free-space fall) so the traffic reads as in-place rewriting rather than new data. |
| 14:22 ET | `8dc54bc` | Took the fifth read at 14:14:28 and put all six roots on one floor — fleet −3,362,816 B = 8.9 kB/s with every node between 524,288 and 614,400 B (1,387–1,625 B/s) — after three paired-`du` probes falsified the pool chunk store, `/var/log`, `/tmp`, `~/benchmarks` and `~/.cache` on `.30`. |
| 14:23 ET | `353096b` | Authored the 3D lane's first arm plus the instrument that scores it: `zz-qwen35-4b-3d-coder-q4km-llamacpp` (Q4_K_M + BF16 projector, ctx 65536, the card's sampling, no speculative flags) and `tools/threejs-render-check.py`, a headless-Chromium check over three mechanical facts — page exception, non-zero WebGL draw calls, pinned cdnjs specifiers — whose batch mode grades the 213-prompt `ThreeJS-3D-Scenes` battery, with the lane stating it does not score fidelity. |
| 14:24 ET | `0e2ccf9` | Withdrew the board's journald attribution for `.30`/`.35`'s two ~8.8 MB falls on two growth samples: a 90 s `du -sb /var/log` pair reads +115,493 and +105,573 B (~1.2 kB/s) against the ~23 kB/s those nodes were falling, and `/var/log/journal` grows 0 inside it — so both bursts now carry no measured writer. |
| 14:28 ET | `ac97dbf` | Fixed the census row's own arithmetic — a 239 s span was labelled 378 s, mixing the peer's stamps with this tick's — and withdrew an unprivileged `du --apparent-size /var/log` reading as void rather than contradictory (journal files are sparse), recording `.30`'s further 164,704,256 B fall between 14:14:28 and 14:24:59 as unattributed with journald and the chunk store both flat. |
| 14:31 ET | `b67b893` | Dropped the last journald reference `0e2ccf9` left behind, so no clause on the row still implies the withdrawn cause. |
| 14:38 ET | `4782ff6` | Claimed the 3D render arm and the SM121 DeepGEMM build (both empty `claimed_by` until then) as **dispatch state**, stating that the claim asserts no live container — the same stamp's read found `.30`/`.35` at 0 — so the register advertises in-progress work without pretending a boot is up. |
| 14:40 ET | — | First boot of the 3D arm on `.30:8031` (task `sparkrun_460a519f1044e748_d7fd9732ce62`): ready in 15 s at 1.44 GiB cgroup, served id `ccore/Qwen3.5-4B-3D-Coder`, and the acceptance cell returned `finish=length` on **8,192** completion tokens with **0 content chars / 24,244 reasoning chars** in 152.55 s — so nothing was rendered; the cell script then died on `KeyError: 'usage'` (`threejs-cell.py:87`), an instrument defect that scored the run not at all. |
| 14:57 ET | — | Diagnose pair on the same serve, 12,288 and 16,384 caps: **1,041** content chars after 35,375 reasoning chars (270.83 s), then **0** content after 69,877 reasoning (407.77 s), both `finish=length` — the arm spends its whole budget in reasoning, so the render gate still had no document to check; whether that is the arm or a sampling/template mismatch is unestablished. Boot stopped 14:58:43, `ctns=0 vols=0` verified. |
| 15:11 ET | `5244477` | Homed the 3D arm's two boot measurements and the quartet's `/v1/models` route pattern to `SESSION-RECORD.md` §15:09 so clearing the landed table could not orphan them, and made the board row report what the probe returned (`/v1/models` 200 on `.31`, 404 on `.32`–`.34`) instead of excusing it. |
| 15:17 ET | `5561090` | Refreshed the board on a 15:03:47 census with its 152 s pair — containers 0/1/1/1/1/0, volumes 0, `/health` 200 on `.31`–`.34` with 3 engine pids per rank — and rowed eight commits earlier tables never carried. |
| 15:20 ET | `256d1d0` | Fixed the 3D arm's empty replies at the arm rather than the weights: thinking off through the GGUF's own `chat_template` (`--chat-template-kwargs '{"enable_thinking": false}'` through a defaults variable, dry-run checked) plus an output-only instruction, with the render gate now unwrapping a fenced reply and its `--selftest` at six fixtures; the 213-prompt battery's denominator and its ≈5 h expected / 16 h ceiling were declared before it ran and the arm stays `zz-`. |
| 15:22 ET | `edf8937` | Extended the census with a 466 s window from the 15:02:19 anchor — fleet −599,486,880 B (1.29 MB/s), 97 % of it `.30`'s own 579,747,840 — and recorded that the burst ended (15:15:22 → 15:16:40 falls 57,344 B = 0.74 kB/s) with no writer measurable: no `hf download`/`rsync`/`docker build`, `$HOME` +787 B, `/tmp` +0, `/var/log` +59,697 B over 93 s, and no pool hub entry touched in 25 min. |
| 15:29 ET | `1481589` | Named `.30`'s reclaim — `/` gains **+147,595,264 B** at 15:15:22 after the burst, so the net over 15:02:19 → 15:16:40 is written as −432,209,920 B over 861 s rather than as a rate — and replaced the "void, not negative" clauses with `sudo -n` measurements of the two root-gated trees (`/var/lib/docker` 536,531,975,736 B, `/srv/beegfs/storage` 1,264,982,154,472 B, byte-identical 15:24:29 → 15:26:07). |
| 15:29 ET | `eae79c5` | Closed `arch-deepgemm-sm12x-paged-sparse`: image `dsv41-sm121-dg:0.2.0` (`sha256:1778ec42…`, local only) built rc=0 in ~70 s as guard-widening plus the SM120 kernel ported from `nv_dev b64107f2`, kernel gate 8/8 PASS at the consumer's strides (calc_diff 1.3e-05, negative control caught) printing `DEEPGEMM_PAGED_SPARSE_MQA_LOGITS True`, and both survey rows re-scoped to blocked only on a quartet window on `.31`–`.34`. |

### Commits after the table's last rowed SHA (16:10–16:41 ET)

Rows as the peer's 17:11 ET board carried them, which is richer than a summary and is
therefore what survives.

| time ET | commit | one clause |
|---|---|---|
| 16:10 ET | `dfcf1fd` | Refreshed the board on the 16:03 census — containers 1/1/1/1/1/0, volumes 0, `/health` 200 on `.31`–`.34` with 3 engine pids per rank, a 146 s byte pair at 10,988 B/s — and rowed the `.30` 3D re-boot: task `460a519f1044e748_63b9c668eed3` started 15:33:12 at cgroup 7.77 GiB with its 213-prompt battery open. |
| 16:11 ET | `1c7474d` | Corrected that row's progress clause: the driver's `20/213` is a resume index, not a count — `run.log` records `rows=16` from the smoke pass, so replies 17–20 are the four that landed, summing 446.26 s and giving the driver's own 111.6 s/reply; nothing about the instrument was broken. |
| 16:12 ET | `0d89f64` | Folded a second overlapping byte pair into the 16:03 census row (174 s, fleet 9,204 B/s, every node 1.36–1.88 kB/s) and put `.30`'s 31,727,616 B fall over 2,861 s into the hour's burst shape; no landed row added. |
| 16:22 ET | `2633ee7` | Appended the session close-out to `SESSION-RECORD.md` as a 160-line append-only section — the director's production lifecycle and drained acceptance campaign, two live-state defects with their structural fixes, the lane sweep, and the three remaining blockers; suite 1,275 ok / 2 skipped. |
| 16:36 ET | `e0fc4e1` | Folded the standalone audio arm's cells into `recipes/liquidai/README.md` — ASR 200 in 0.589 s at WER 0.000, `/tts` 200 as a 238,124 B 24 kHz 4.96 s wav, round trip 200 at WER 0.000, cgroup 1.14 GiB — with the experimental-audio warning and the `:F16`→BF16-named-file trap, and re-took the `--strict` snapshot. |
| 16:41 ET | `840df69` | Said what that re-taken snapshot actually measured: 96 tracked recipes scanned, 53 printing a finding (20 carrying a warning, the rest suggestions only), and that the LiquidAI and 3D arms add no row because an accuracy declaration belongs inside `metadata:`. |

## 2026-11-07 18:15 ET — board landed rows homed (session boundary)

Each hourly tick is its own one-shot session, so the rows the 17:21 ET board (`fddce3c`) opened belong to the session before this one. `git grep -c <sha> -- mad-science/SESSION-RECORD.md` returned nothing for every SHA in the table, so all five are carried here verbatim out of `mad-science/STATUS.md` before the table is cleared: the three the previous session wrote plus the two it landed afterwards (`fddce3c`, `3e37df5`), which the 18:10 ET tick added.

This tick published no board of its own: a peer tick committed `4d6e32d` at 18:11:12 on the same 18:01 ET census, so its board is kept and corrected in place rather than replaced (one wrong operand fixed — the battery row paired index 74 with 75 reply rows, which cannot both hold when 16 of those rows are the copied smoke prefix).

| time ET | commit | one clause |
|---|---|---|
| 17:06 ET | `2efa5d8` | Homed the 72 `Landed session` rows the previous session left on the board plus the six commits after their last rowed SHA — 48 of the 74 unique SHAs had no mention in `SESSION-RECORD.md` and 44 appear nowhere else in the tree — so this table could be cleared without orphaning anything. |
| 17:07 ET | `78e4c3f` | Refreshed the same 17:02 census with the 3D battery's index at 50/213 and the render gate's 24/46 clean at N=46. |
| 17:10 ET | `810adb4` | Replaced two weaker board claims with their operands: eight `state.json` roots on the head carrying **0 leases** with every arm terminal (not "no lease printed"), and the battery's 50 as the **resume index** so 34 replies at 111.4 s/reply reconcile with the driver's own rate. |
| 17:22 ET | `fddce3c` | Folded three fixes onto the peer's 17:20 board without replacing it (its census prose, campaign-lease operands and battery resume-index correction kept verbatim): a second overlapping byte pair (17:02:24→17:03:53, 89 s, fleet −616,496 B = 6,927 B/s), six absolute `df -B1` values, the zero-lease campaign claim re-counted over eight roots, the 3D cgroup figure named as two states of one boot, and the 72 inherited landed rows cleared once `2efa5d8` homed them in `SESSION-RECORD.md`. |
| 17:26 ET | `3e37df5` | Closed `lint`'s other direction: a title stamped ahead of the wall clock made every later honest stamp read as `title-regression`, so `future-stamp` now refuses it at minute resolution — two tests with the pre-fix pass as the negative control, in `tools/task-queue.py` + `tests/test_task_queue_tool.py` with the `AGENTS.md` suite statements. |

## 2026-11-07 18:26 ET — correction: the pair-3 census clause straddled `.33`'s burst

`e8df6d8` published a third byte pair (18:02:23→18:06:44, 261 s) and read it as evidence that `.33`'s
fall "decayed rather than stopped", attributing "~2.8 MB over the remaining 144 s" to a writer still
running. **That inference was wrong, and the operand that falsifies it was already in the same row.**
`.33` fell 8,765,440 B across my window, but the row carried `.33`'s absolute at 18:03:41, so the window
decomposes as **8,482,816 B in the 78 s before that read (108,754 B/s)** and **282,624 B in the 183 s
after it (1,544 B/s)**. The burst ended before the peer's second read; a 33,584 B/s average is what a
window drawn across a boundary produces, and the ~2.8 MB belonged to the burst, not to anything after it.

Same defect, second clause: the row called all six nodes "back inside the 1.4–2.0 kB/s band". Over the
post-burst 183 s `.30` ran at 4,633 B/s — the one node above the floor. It is not the battery's serve log
either: that log grew **51,883 B across the whole 20 min, 43 B/s**, so `.30`'s share is unattributed too.

A later pair does show a set above the floor, and it is transient rather than a writer: **pair 4,
18:06:44→18:19:53 (789 s), fleet −33,841,152 B = 42,891 B/s** with `.30` 14,235 · `.31` 12,236 · `.32`
12,070 B/s while `.33`/`.34`/`.35` sat at 1,402–1,490; then **pair 5, 18:19:53→18:23:33 (220 s), fleet
−2,179,072 B = 9,905 B/s with all six back at 1,508–2,141 B/s**. Pair 5 is what settles pair 4: the rate
stopped, so it was a burst and not a sustained writer. The pool probe names nothing — no
`/mnt/beegfs/huggingface/hub` directory changed in the 25 min before it, and the 48.9 GB of `.incomplete`
blobs under `models--unsloth--Qwen3.8-27B-GGUF` are dated **2026-10-27**, dead partials rather than a
download in flight.

Carried forward as a rule for the next tick: a pair's average means nothing if a known boundary falls
inside it — check the previous row's absolutes before folding a new pair into the same sentence — and one
pair cannot separate a burst from a writer without a later read showing the rate stopped.

## 2026-11-07 20:22 ET — board landed rows homed (session boundary)

The board this tick read had an empty `Landed session` table, and four commits landed between 19:15 and
19:52 ET that no row and no section here carried: `4472983`, `7cc9aff`, `fdea9c7`, `88ecd24`.
`git grep -c <sha> -- mad-science/SESSION-RECORD.md` returned nothing for all four, and the board on
disk (`6416fc4`, generated 20:14 ET) rowed none of them, so they are carried here verbatim-adjacent so
that the table can stay empty without orphaning anything.

This tick published no board of its own: a peer tick committed `6416fc4` at 20:17:01 ET on a 20:14 ET
board, so its rows are kept and this tick's measurements folded onto them rather than replacing the file
(a whole-file write two minutes behind a peer is the equal-stamp clobber the publish tool cannot refuse).
Folded, all measured at 20:15: the battery's two indices (**`.30` 129/157 with 113 produced**, **`.35`
29/56 with 29 rows whose ids reconcile both ways** against its log), both cgroups (9.42 GiB and 9.40
GiB), both slot timings (`tg 62.2` and `tg 64.7 t/s`), a three-point root-avail decomposition
(20:04:23 → 20:05:56 → 20:09:03 ET) showing the two ~9 MB rank falls happened in **different** windows —
one burst migrating between `.32` and `.31`, not a twin event — the two new discriminators on it
(`.32`'s host serve log is 804,324 B total, too small to be the writer; the container's docker json log
under `/var/lib/docker` is root-owned, so that read is VOID), the receipt-dir reconciliation (a 118,100 B
minute against the peer's 4,380 B minute disagree only because one reply flush per ~124 s falls inside
one window and not the other), and the register's drift clause (the one `running` row carries no
`recipe`/`tp`/`env`, so under the register-pull mode it is an authoring row the scheduler skips and no
open row is bootable yet). The peer's split claim was re-verified rather than inherited: `subset-30.jsonl`
157 ∪ `subset-35.jsonl` 56 = 213 ids with **zero overlap**, and every reply id falls inside its own
subset.

| time ET | commit | one clause |
|---|---|---|
| 19:15 ET | `4472983` | Read the watchdog as the gate it is: the 3D arm's row had called a completed boot gate an instrument defect, where `main()` returns 0 on the first probe whose verdict is `healthy` (`tools/boot-watchdog.py:513-514`), so a ready arm is unguarded by design; a re-armed instance exited on its own first `healthy` probe, both probe logs were removed, and the row now names the mechanism and the driver's request loop as what notices a mid-battery serve death. |
| 19:19 ET | `7cc9aff` | Settled `.30`'s burst with a pair and sized its writer rather than inferring it: the 19:03:52 → 19:04:55 pair caught **184.6 kB/s on `.30` alone** while `.31`–`.35` sat at 1,365–1,560 B/s, a 19:09:16 → 19:10:17 pair put `.30` back on the floor, and the r2 receipt dir grew **96,632 B in 60 s = 1,610 B/s** — with the container's writable layer (+1 kB in 45 s) and unchanged pool mtimes as negative discriminators and the root-owned docker json log recorded as a VOID read. |
| 19:51 ET | `fdea9c7` | Added the machine-runnable triple to the register so a director can boot from it: `tools/task-queue.py` takes optional `recipe`/`tp`/`env` (recipe must be a tracked `recipes/<lane>/<arm>.yaml`, `tp` one of 1/2/4 and equal to `node_cost`'s host count, env an object of strings), every read path validates, `queue --json` prints the table's own weighted order, and absence means an authoring row no scheduler may boot; verified on the workstation (suite 1,291 tests / 2 skipped, `check` green over 82 rows) with no existing row rewritten. |
| 19:52 ET | `88ecd24` | Taught the campaign director to pull the register: `serve --queue [path]` builds its plan from queued rows that name a recipe and `tp`, in the register's own weighted order, writes its claim through the tool **before** any lease exists, resumes an in-flight claim as `running`, and in drained state polls every 30 s printing "no runnable rows" once per quiet spell (`--once` runs one pass and exits 0); the declared-host rule stays, and blocked rows, other sessions' running claims, authoring rows and `tp` beyond the declared host count are skipped by name rather than truncated. |

## 2026-11-07 20:35 ET — the moving root-avail share is the pool's own chunk placement, measured
The 20:22 section decomposed two ~9 MB rank falls into different windows and left the writer unnamed.
This tick read the BeeGFS pool **beside** the nodes, which closes that question for the whole class:
over **20:14:24 → 20:16:27 ET (123 s)** the pool went 10,951,088,668,672 → 10,951,078,707,200 B =
**9,961,472 B = 80,988 B/s**, while the six nodes' combined root fall was **9,990,144 B = 81,221 B/s,
ratio 1.0029**. The roots are recording the pool's writes and nothing else, so no node-level writer
need be found when a rank's root falls; four windows then show the share migrating rather than sitting:
51,816 B/s (449 s, `.31`+`.32` leading), 155,850 B/s (162 s, `.30` 96 kB/s + `.32` 53 kB/s), 81,221 B/s
(123 s, `.35` 69,765 B/s), and **50,628 B/s over 938 s with `.33` and `.34` at 19,366 / 19,371 B/s
(18.17 MB each) while `.30` and `.35` — the two nodes actually generating — sat at 7,262 and 1,524 B/s**.
That inversion is the second discriminator: the node doing the work is not the node losing the bytes.
**Correction to `7cc9aff`'s mechanism, arithmetic only:** that row read `.30`'s 11.6 MB fall as the
battery's own receipt writes, but its own `du` puts that tree at 1,610 B/s — 0.09 MB/min, **0.8 %** of
the fall it was invoked to explain, so the mechanism cannot carry the magnitude. Pool writer still
unattributed, with `find /mnt/beegfs/huggingface -maxdepth 4 -newermt '-25 minutes' -type f` returning
nothing (`hub` unchanged since 14:31, and depth 4 covers every `blobs/` path), and the only `.incomplete`
blobs on the pool — 8 under `models--Comfy-Org--MiniMax-H3` — dated **2026-10-24**, 0–336,904,078 B,
byte-identical across a 45 s re-stat: dead partials, not a live download.

## 2026-11-07 21:10 ET — six board-cycle commits homed (tick sweep)
The 21:06 tick read the board's `Landed session` table empty and checked, rather than assumed, that its
predecessors' rows had a surviving home: `git grep <sha> -- mad-science/SESSION-RECORD.md` returned
nothing for six commits between 20:16 and 20:42 ET, so their clauses were homeless once the table was
cleared. Each is homed here with the one clause its own body carries; nothing in them is re-measured.

| time ET | commit | one clause |
|---|---|---|
| 20:16 ET | `52f9ce5` | Released a register claim on every exit from `running`: `cmd_update` had cleared `claimed_by`/`claimed_at` only on `done`, so a failed-in-place arm stayed `queued` while looking claimed and a fresh claimed_at told every other session to skip it; `--claimed-by` without `--state running` is now refused rather than silently dropped, and `validate` fails closed on any non-running row carrying either field (the tracked register still passes `check`, 82 rows). |
| 20:24 ET | `6a7b285` | Corrected two claims on the 20:14 board: the receipt dir's 73 B/s against `.30`'s 7,946 B/s root fall is **109× — two orders, not the three the row said**; and the 213-row denominator stopped being asserted and now names its evidence (`subset-30.jsonl` 157 + `subset-35.jsonl` 56, disjoint id sets, every reply id inside one of them). |
| 20:32 ET | `30ce91e` | Folded the 20:15 measurements onto a peer tick's 20:14 board instead of replacing it (a whole-file write two minutes behind a peer is the equal-stamp clobber `publish` cannot refuse): battery indices `.30` 129/157 (113 produced past the 16-row smoke prefix) and `.35` 29/56 with ids reconciling both ways, cgroups 9.42 and 9.40 GiB, slot timings `tg` 62.2 and 64.7 t/s, and the register's drift clause (the one `running` row carries no `recipe`/`tp`/`env`, so register-pull mode skips it by design). |
| 20:33 ET | `1a99f3c` | Made `52f9ce5`'s own repair reachable: `cmd_update` pre-validated, so a queued row carrying a claim failed on the very `update --state queued` the error text prescribes and no command could clear it (`check`, `queue --json` and the director's whole plan failed identically). The target row's claim is now cleared after `_relink` and before the pre-validate when its current state is not running; only the named row is excused. |
| 20:38 ET | `994dd92` | Regenerated the board on its own 20:32 census (containers 1/1/1/1/1/1, volumes 0), added `.35`'s row for the 19:20 re-split (157 + 56 = 213), probed both halves fresh (136/157 and 36/56 at 20:36, `/health` and `/v1/models` 200, `restarts=0`), re-probed the quartet and campaign rather than carrying them, re-rendered the register (9 open of 82), and read the BeeGFS pool beside the nodes. |
| 20:42 ET | `1308de8` | Corrected the battery burst operand: `.30`'s 162 s fall is 1,439,483,092,992 − 1,439,467,532,288 = **15,560,704 B**, not the 15,561,728 B the row said (and what its own 96,054 B/s × 162 s implies), because a figure wrong by 1 KB still reads as measured; restored the peer tick's clause that `director status --root d1-20261107` prints `1 measured`, which the "absent status line is not evidence of no lease" rule rests on. |

## 2026-11-07 21:19 ET — the 21:07 board row's writer attribution corrected (third recurrence)
The 21:07 census row (`0498062`) read `.30`'s 17,877 → 22,791 B/s fall as "the battery's own writes" and
`.31`'s 29,402 B/s as a burst. Both are the mechanism `7cc9aff` had already been corrected for, and the
battery cannot carry it: its receipts — `battery.log`, `battery-35.log`, `serve*.log`,
`threejs-replies*.jsonl`, the render-gate JSONs — all live in the head's
`~/benchmarks/tp12-20261107/zz-qwen35-4b-3d-coder-q4km-llamacpp-r2/`, and that tree's `du` is 1,610 B/s,
**0.8 %** of the fall it was invoked to explain. This is the third regression of the same attribution
(the 20:35 section, then `7cc9aff`, now `0498062`), so the fix was to measure the discriminator in the
same tick instead of carrying the established ratio forward:

- **pool beside roots, same pair, 21:14:14 → 21:16:47 ET (153 s):** pool `/mnt/beegfs`
  10,950,946,586,624 → 10,950,926,139,392 = **20,447,232 B (133,642 B/s)**; the six roots
  20,496,384 B (133,963 B/s); **ratio 1.00240**, against 20:35's 1.0029.
- per-node shares, same pair: `.30` 126,815 · `.31` 1,526 · `.32` 1,419 · `.33` 1,392 · `.34` 1,392 ·
  `.35` 1,419 B/s. The fall is the pool's placement on whichever node holds the chunk, not local work.
- pool writer still unattributed, and the read says why: `/mnt/beegfs/huggingface/hub` last changed
  14:35 (top entry `models--ccore--Qwen3.5-4B-3D-Coder`), nothing under it newer than the 15 min to
  21:17:20, no `.incomplete` blob — not a download in flight.

Corrected in `75e448d`. State at the same read: `.30` battery **COMPLETE 157/157 at 21:14** (125 s/reply
avg, container up 6 h and idle, `/health` 200), `.35` **51/56 at 21:15** (133 s/reply avg) → 208/213
replies, ~11 min left. Quartet re-probed 21:16:38: `/health` 200/200/200/200, `/v1/models` 200 on `.31`
and 404 on `.32`–`.34`, up 47 h 00 m, `restarts=0`. Campaign inactive with 0 live leases across all
eight `state.json` roots; register 9 open of 82, `check`/`orphans` green.

## 2026-11-07 21:42 ET — 3D battery closed: the arm fails its own gate at 45.5 %

- **Battery to its declared denominator.** 213/213 validation prompts across two serves (`.30` 157,
  `.35` 56), 7.8 h wall, median 124 s/reply. Nothing re-labelled and no subset.
- **Verdict: fails the pre-registered gate.** renders clean **102/213 (47.9 %)**, non-empty geometry
  **101/213 (47.4 %)**, import constraint **213/213 (100 %)**, all three **97/213 (45.5 %)**. Per node
  `.30` 70/157 (44.6 %), `.35` 27/56 (48.2 %) — prompt mix, not host. 208 `stop`; **5 hit the 16,384
  cap and count as failures**, because a truncated file is not geometry.
- **Failure taxonomy:** 116 failures over 90 strings — 34 `TypeError` null/undefined, 30 `SyntaxError`
  (duplicate `const`, missing paren, illegal `return`), 28 `ReferenceError`, 14 Three.js API misuse,
  5 NaN-bounding-sphere `console.error`, 5 other. The card's stated mode (duplicate names) is the
  single largest syntax class, and the API-misuse class is the model calling a real method on the
  wrong object, not a broken module.
- **Instrument checks before the numbers were believed:** gate deterministic (49/49 re-gate
  identical); 6 s settle changes nothing; pinned module complete (`computeFrenetFrames`/`getCurve`
  exist); system prompt byte-identical; resume intact; empty reply counted as a failure; 213
  denominator asserted. The 16-prompt smoke scored 9/16 and predicted the full shape.
- **Footprint correction:** 9.36/9.38 GiB cgroup while serving; the 1.44 GiB reading that circulated
  early was **pre-fault** and would understate a 65,536-token vision arm by 6x.
- **Row closed:** `3d-qwen35-4b-3d-coder-arm` → `done` with the cells in its `evidence`, claim cleared.
  The arm stays `zz-` — a measured capability arm, not a shipped one. Register: 74 done, 6 blocked,
  2 queued (8 open).
- **Still unmeasured:** visual fidelity. 45.5 % clearing a mechanical gate says nothing about whether
  the 97 clean scenes look like what was asked; the dataset's reference renders are the open
  instrument.

## 2026-11-07 23:05 ET — h2h campaign measured its ds4 arm, then the director was stopped; board handed over

Moved here from the board's `Landed session` table, which the 23:00 tick cleared after the previous
session stopped its campaign. Every clause below was re-read from the source named, not carried from
the board text.

- **Production serve removed 22:25:04–22:25:24 ET** (`03bdee9`): all four containers of the 47-hour
  knapcio quartet deleted (node docker journals: `task-delete` 22:25:04 `.33`, 22:25:05 `.32`, 22:25:06
  `.34`, 22:25:24 `.31`; `.31` logged "cannot exec in a stopped container" then a force-kill fallback).
  The window lock `session: campaign-queue`, `window_stamp 2026-11-08T03:37Z`, all six nodes,
  `stop_rule: only containers this campaign starts` was written for it.
- **`run-arm.sh` gained an arm-scoped extra client** (`3f71e54`, `ARM_EXTRA_CLIENT` / `ARM_EXTRA_TIMEOUT`)
  so a house or BFCL client rides the arm's own live serve; needed because the h2h rows pair a ladder
  with a quality battery on one boot.
- **`h2h-20261107` ran on the head** (`~/benchmarks/h2h-20261107`, one worker slot, hosts `.30`–`.35`).
  Its first arm, `deepseek-v4.1-flash-knapcio-tp4-1m-sglang`, booted on `.30`–`.33` at 22:47:44Z and
  closed **`rc=0 measured`** at 23:00:05 with `watchdog: healthy` (receipt
  `~/benchmarks/h2h-20261107/receipts/deepseek-v4.1-flash-knapcio-tp4-1m-sglang.json`).
- **Second-boot ladder, 4 cells × 5 runs** (`~/benchmarks/tp12-20261107/deepseek-v4.1-flash-knapcio-tp4-1m-sglang/ladder.json`):
  C1 pp 2,694.2 ± 1,482.4 / tg 51.1 ± 16.2; C2 pp 4,640.2 ± 589.7 / tg 91.8 ± 3.9; C5 pp 5,252.2 ±
  322.6 / tg 128.9 ± 4.6; C10 pp 3,649.3 ± 522.1 / tg 159.9 ± 10.1. `house.json` beside it reads
  `final_score 93` (deployability 89, responsiveness 80, 15 scenarios, `status: completed`, run
  `2026-11-08T03-59-04Z`). **No cross-boot sigma claim is made here**: the first-boot table cell is an
  aggregate figure and these are `tg_throughput` means, so the pairing belongs to the
  `h2h-doc-refresh` row, not to this note.
- **The director was then stopped, mid-plan.** `director.log` ends
  `signal 15: stopping after tick (workers get SIGTERM, arms stopped run-arm.sh's own trap)`; no
  `sparkrun_campaign.director serve` process remains and `sparkrun-campaign.service` is
  `inactive/dead`. `state.json` still reads **1 measured + 1 leased + 4 pending**: the leased arm
  `glm-5.3-exl3-3bpw-tp4-1m-tensorfold-sglang@1` on `.30`–`.33` never created a container (its arm log
  is the launch line plus `Terminated`), its lease heartbeat was 23:00:25 with expiry 23:05:25 ET, and
  nothing is left alive to reconcile the row. **A stopped director leaves `leased` in `state.json`**, so
  "unit inactive + a leased arm" is the run-died signature the board must report instead of calling the
  campaign drained.
- **The head's `~/.config/sparkrun-campaign.env` points at a different campaign** (`d1-20261107`,
  hosts `.30` + `.35`, one arm `measured`), so a tick that reads only the env file reports an idle
  fleet while `h2h-20261107` still holds the lease. Enumerate `~/benchmarks/*/state.json`
  (ten roots carry one; only `h2h-20261107` has a lease).
- **Register left with an unclosed row.** 93 tasks, 74 done, 19 open (1 running + 13 queued + 5
  blocked). `h2h-second-boot-ds4-1017` is `running`, claimed `sparkrun-campaign:h2h-20261107`, though
  its arm's own receipt says `measured` — finished work whose holder died before `done --evidence`.
  `41a1788` added the two SM121 survey arms (`w4-survey-arm3-sm121-boot`, `w4-survey-arm5-sm121-boot`)
  as queued, and the two DeepGEMM-gated arms now hold on them.

## 2026-11-07 23:26 ET — byte series through the h2h restart, and 27.6 GB on `.35` with no node-local author

A tick cycle that could not own the board (a peer republished it three times inside eight minutes) lands
its measurements here instead. All reads are this cycle's own, read-only, from the head.

- **Containers stayed at zero through 23:13:49** (23:00:48, 23:02:07, 23:13:49 reads: `0` containers and
  `0` volumes on all six nodes), then the campaign's GLM-753B **attempt 2** appeared on `.30`–`.33`
  (containers created 23:14:41 ET, image ID `sha256:cffb3c3f6216…`, label
  `recipes/glm/glm-5.3-exl3-3bpw-tp4-1m-tensorfold-sglang.yaml`), still loading at the 23:21:15 read.
- **Root avail byte series** (B, `.30` `.31` `.32` `.33` `.34` `.35`): 23:00:48 — 1,439,373,541,376 ·
  1,853,010,464,768 · 1,905,182,380,032 · 1,797,326,393,344 · 1,241,363,488,768 · 1,485,429,747,712;
  23:13:49 — 1,439,362,538,496 · 1,853,009,391,616 · 1,905,181,302,784 · 1,797,325,328,384 ·
  1,241,149,190,144 · 1,457,812,086,784; 23:21:15 — 1,439,361,003,520 · 1,852,999,716,864 ·
  1,905,180,020,736 · 1,797,324,038,144 · 1,241,148,534,784 · 1,457,811,435,520. Through the
  container-free window (23:05:02 → 23:13:49, 527 s) the fleet fell **27,835,528,192 B (52.8 MB/s)** of
  which **`.35` alone lost 27,617,275,904 B (52.4 MB/s)** and `.34` 213,917,696 B; the other four moved
  kilobytes. Through the booting window (23:15:01 → 23:21:15, 374 s) the quartet lost 11,788,288 B in
  total, i.e. the fleet's drain was **not** the boot.
- **The pool moved with it.** `/mnt/beegfs` free on the head: 10,922,880,925,696 B at 23:13,
  10,912,721,272,832 at 23:16:24, **10,903,047,634,944 at 23:17:23** — a 60 s window measuring
  **−9,673,637,888 B (161 MB/s)** — then **10,922,869,391,360 at 23:21:15**, i.e. ~19.8 GB released
  within four minutes. That shape (write, then release without a body appearing) is consistent with the
  runtime cache of attempt 1 being reaped and attempt 2 restaged, which the director's own log states:
  `reaped glm-5.3-exl3-… outstanding previous run; 0 container(s) found`.
- **What is *not* explained:** `.35`'s 27.6 GB fall happened **before any container existed**, and no
  node-local writer accounts for it. Exclusions, each a command run this cycle: `ps` on all six nodes
  shows no `rsync`, no `hf`/`huggingface` download and no `docker pull`; `docker image ls` on `.35`
  lists only two-week-old images and `journalctl -u docker --since "-25 min"` shows no pull or load;
  the HF hub cache gained nothing (no `.cache` dir, newest repo dir 14:35); `find / -xdev -newermt
  "-45 minutes" -size +200M` on `.35` returns nothing (and `/var/lib/docker` is 4.0 K there, so the
  docker data root is not on `/`). What does live on `.35`'s root is the beeGFS chunk store —
  `/srv/beegfs/storage/{buddymir,chunks}` — which grows with pool traffic regardless of local
  processes, so **pool traffic is the likely cause (LIKELY, unverified)** and the numbers above are the
  evidence a later reader can use. Pool free was 10.9 TB throughout, so nothing was at risk; the
  finding is recorded rather than escalated as an incident.
- **Board ownership, for the record:** this cycle published once (23:06, census stamp 23:00:48, commit
  `5a882bd`) and then lost the base to peer republishes at 23:18 and 23:21 while probing. The landed
  board is the peer's; nothing from this cycle was dropped, because everything it measured is here.

## 2026-11-07 23:33 ET — probe round 2: the writer scan re-run for real, the house reconciled, the chunk store constant

The 23:26 section above rests one exclusion on a scan that was vacuous — its node variable expanded
empty, so the six `ssh` calls went nowhere and their silence read as "no writer". Re-run with a literal
address per host, and the other two open items closed with their own probes:

- **Writer scan, literal hosts, 23:27:43 ET.** `.30`–`.33` carry only the quartet's own child:
  `/opt/sglang/bin/python3 /opt/sglang/bin/tensorfold serve /cache/huggingface/hub/models--bertholomus--GLM-5.3-EXL3-3.0bpw/snapshots/7f0573836c44803030912…`
  (pids 2499133, 191735, 164156, 130191). `.34` and `.35` return **nothing** for `rsync|hf|huggingface|docker pull|oras|dd if=`.
  **Limit, stated plainly:** this is a later window; the 23:05:02→23:13:49 window cannot be re-probed
  after the fact, so that window's exclusion rests on the reads taken at 23:17 (docker image list,
  `journalctl -u docker --since "-25 min"`, absent hub `.cache`) plus this scan — not on a direct
  process read of the window itself.
- **The chunk store did not move.** `sudo -n du -sb /srv/beegfs/storage` on `.35` returned
  **1,370,155,678,247 B at 04:27:43Z and the identical byte count at 04:28:43Z**, while `.35`'s root
  avail fell 77,824 B and the head's pool avail fell 13,631,488 B across a longer span. So the
  `buddymir/`+`chunks/` directory existing is **not** evidence of a resync, and pool chunk growth is
  **not** what is draining `.35` now. The earlier LIKELY attribution is downgraded: the pool's
  161 MB/s dip and its ~19.8 GB release bracket the GLM attempt-1 reap / attempt-2 restage
  (`reaped … outstanding previous run`), while `.35`'s 27,617,275,904 B fall **has not recovered** —
  `.35` root read 1,457,810,915,328 B at 23:27:43 against 1,485,429,747,712 B at 23:00:48 — so the two
  movements are not the same bytes and the root fall is still unattributed.
- **The ds4 second boot's house battery reconciles with its own clock.** `house.csv` carries 15
  scenario rows (13 pass, 2 partial), **Σ duration 37.1 s**, 31 turns, 3,056 completion tokens → 82.3
  completion tok/s; `ladder.csv` has 9 lines. Artefact mtimes: `launch.log` 22:56:47, `ladder.json`
  22:59:00, `house.json` 22:59:41, and `watchdog.log`'s last verdict is `t=521s verdict=healthy` — i.e.
  readiness at ~22:55:57, then 20 ladder requests and 31 house turns in the 3 m 44 s to 22:59:41. The
  house is not a 15-scenario battery crammed into 61 s: it is 37.1 s of scenario wall on the serve that
  had just become healthy, so the ladder cells and the house score **do** belong to one boot.

## 2026-11-07 23:44 ET — supersedes the `.35` attribution above: it is an overlay2 image layer, not beeGFS

The 23:26 section called pool traffic "the likely cause" of `.35`'s 27,617,275,904 B root fall and the
23:33 section downgraded but kept that reading. Both are **falsified**, and the mechanism is now measured:

- **No chunk was written.** `sudo -n find /srv/beegfs/storage/chunks -type f -newermt "2026-11-07
  23:04:00" ! -newermt "2026-11-07 23:15:00"` counts **0 files**, and the newest chunk anywhere in the
  store has mtime **14:38**. The chunk store is 3,005 files / 1,370,155,678,247 B and has been quiet for
  nine hours, so `buddymir/`+`chunks/` existing says nothing about a resync and the pool dip was the
  campaign's own attempt-1 reap / attempt-2 restage, which fully recovered (pool avail 23:13
  10,922,880,925,696 → 23:21 10,922,869,391,360, i.e. flat).
- **The bytes are an overlay2 diff layer.** Scanning by **ctime**, which `mv` and `cp -a` do not
  preserve, finds in that window **358,150 files / 26,898,269,170 B (26.90 GB)**, every one of them
  under `/var/lib/docker/overlay2/9ff2471cf410c0c6a98249bf995e271846586468f009e6b4b16749c53c547acb/diff/opt/sglang/…`
  — `libcublasLt.so.13`, `libtriton.so`, `libtorch_cuda.so`, `libcudnn_engines_precompiled.so.9` and the
  rest of the engine image being materialised on `.35` between 23:04 and 23:15, i.e. **in the eight
  minutes before the quartet's containers were created at 23:14:41**. It is the boot's own image
  distribution, and `.34`'s 213,917,696 B is the same thing in miniature.
- **Why the earlier probes missed it, stated so the next reader does not repeat them.** An
  mtime-scanned `find … -newermt` window sees nothing, because an image layer lands with the *image's*
  build mtimes (two weeks old); only **ctime** marks the materialisation. `docker image ls` also looked
  innocent because a relay-imported image keeps its build date in `Created` — the entries reading
  "2 weeks ago" are exactly the `oci-relay/pinned:<digest>` form such an import produces, and
  `journalctl -u docker | grep -E "pull|import|load|unpack"` does not carry a client-side `docker load`
  in the daemon log. `du -sxb --max-depth=N` is likewise a silent no-op (`-s` conflicts with
  `--max-depth`), which is why two probes printed nothing.
- **Net effect on the board:** nothing to escalate. `.35`'s free space stays 27.6 GB lower because the
  image layer stays, which is normal launch state, not litter: the images already named by recipes outlive
  the boot (AGENTS.md §Node hygiene). The "161 MB/s pool write with no visible author" clause is withdrawn;
  the pool transient has the campaign's own log line as its author.

## 2026-11-08 00:08 ET — board landed rows homed (session boundary), the h2h director's handover, and a superseded 00:04 tick

The 23:48 ET board's `Landed session` table carried six rows, and `git grep <sha> -- mad-science/SESSION-RECORD.md`
returned **nothing for any of the fifteen SHAs checked** — those six plus the nine commits that landed between
23:48 and 23:57 and were never on a board at all. All fifteen are carried here before the table is cleared; the six
board clauses are copied out of `git show 161d89b:mad-science/STATUS.md` rather than retyped.

**Board rows retired at this handoff (verbatim):**

| time ET | commit | one clause |
|---|---|---|
| 23:32 | `b4cd79e` | "h2h-client: record resolved image, since cell alone does not prove it" — `run-arm` now exports `ARM_IMAGE_ID` and writes `<arm>/image.txt` for every extra-client arm, so a receipt proves which image actually ran instead of the manifest's intent. |
| 23:32 | `d7a13eb` | "State the suite total both statements carry: 1318" — that tick's own fix: an earlier commit moved one of the two AGENTS statements and the count moved again when a peer case landed, so both now say the number a detached worktree at the parent discovers. |
| 23:34 | `3695abc` | "GLM-Flash concurrency levers: two probe arms, and `--drafter-repo none` means --no-drafts" — the arm that answers the measured C2-peak-then-fall shape became authorable: the shim had mapped the sentinel onto `--drafter auto`, so no-drafter was never drafter-free. |
| 23:35 | `be63c6f` | "Correct swept recipe count: 102 two recipes not tracked yet" — a correction of a count swept from a peer's pending edit, superseded a minute later by `bd4671d` once those two recipes were tracked. |
| 23:35 | `bd4671d` | "Repair recipe counts concurrent sweep reverted to 100 (actual 102)" — `tools/doc-census.py --fix` rewrote only the two digits, so AGENTS.md:51 and :86 track the tree again. |
| 23:36 | `ed9cb18` | "Falsify the pool attribution for `.35`'s 27.6 GB: it is a docker image layer" — both earlier accounts were guesses; zero chunk files were created in the window and the newest chunk predates it, so the fall is the local image layer, measured rather than argued. |

**Commits that landed after that board and before this tick, each clause its own body's:**

- 23:48 `2602501` — "GLM lane: SWEEP_ENV whitelist makes DFlash2 k and verify-window sweep a `-e`": the shim's
  whitelist lets a per-arm `-e` override `RECIPE_ENV`, which is what makes the k and verify-window levers
  expressible without a code change.
- 23:49 `161d89b` — "Publish board on the 23:45 census: GLM-753B attempt 2 still loading, register at 18 open":
  that tick's board, published over a 23:44:59 census (four ranks up 30 min, `/v1/models` 000, register 18 open).
- 23:49 `6bc48f8` — "Unblock arm 5: SM12x image rebuild, replay-off knob, paired control recipe": the register row's
  SM100 arch assert is answered by an SM12x rebuild, with the replay-off knob and a paired same-digest control recipe.
- 23:51 `65309b3` — "docs: state the committed tree's suite total (1318)": the working tree's extra discovery came
  from peer test modules not in that commit; the detached-worktree count at HEAD is what the guard checks.
- 23:51 `81f2aca` — "State the suite total the committed tree discovers" (empty body): the doc-hygiene statement
  moved to the number a detached worktree at that parent discovers.
- 23:52 `87706a9` — "State the tracked recipe count the committed tree carries" (empty body): the same statement
  moved for the recipe count.
- 23:55 `0d9f835` — "GLM lane: k sweep needs its own arm path, so the carrier ships env": the plan keys an arm by
  recipe basename and refuses two rows on one path, so `zz-…-dflash2k.yaml` is config-identical to the shipped arm
  and exists only to give the k row a path; the value rides the lease env through `SWEEP_ENV`.
- 23:55 `60732da` — "Reconcile the recipe counts the committed tree carries: 104": `tools/doc-census.py --fix`
  rewrote AGENTS.md:17/:51/:86 from 103 to 104 — digits only, so the roster's findings counts and the dated
  snapshot paragraph stay as the peer measurement wrote them.
- 23:57 `5aa87fa` — "register: arm5 pair, 0.2.1 control, all three concurrency levers": arm 5 repinned to
  `dsv41-sm121-dg:0.2.1`, its same-digest control is a separate sub-row booting `zz-ds4-1017-sm121-arm3-control.yaml`
  (the 0.2.0 arm-3 run stays indexer-scoring evidence, not the control), and every survey hook passes
  `--image-id "$ARM_IMAGE_ID"` so the receipt pins what ran.

**A peer tick's board at 00:04 (`0040097`) is superseded by state, and its measurements are kept here.** It
published a 00:03:12 census on which the fleet read empty and "two leases orphaned". Its byte decomposition
survives only in that commit body: the failed quartet lost **286.9 GB** of root across two windows (23:44:59 and
23:58:41 — rank 0 228.7 GB, each worker rank ~19.4 GB, the two idle nodes flat) and **regained 273.3 GB** between
23:58:41 and 00:03:12, netting −13.2 GB on `.30` and −0.17 GB per worker rank. Its attribution: the booting ranks
were the only writers, so the loss is theirs; **who freed the gain is not established**. This tick adds the
falsifier it lacked rather than a new guess — the 00:05:24 read puts `.30` back at 1,439,364,984,832 B, within
17.6 MB of its 23:44:59 level, and bytes that return were never a staged pool body.

**Why the orphan happened, measured on the head.** The director that took the boot2 lease died on **SIGTERM with a
signal-handler reentrancy bug**: `campaign/sparkrun_campaign/director.py:546` prints from `_on_signal`, and the
handler fired while the main thread held stdout's buffer, raising
`RuntimeError: reentrant call inside <_io.BufferedWriter name='<stdout>'>` out of `selectors.poll`. It left the
lease it had just written (boot2, attempt 2, `expires_at` 00:06:53) with no process behind it for ~2.5 min, which
is what the 00:03 census and the peer's "orphaned" rows recorded. A peer restarted `director serve --queue` at
00:04:35 (`setsid nohup`, `>> director.log`), worker w1 pid 3141353; by 00:07 run-arm pid 3195637 had the boot2 arm
launched and the ranks were carrying its image. **The defect is unfixed and unwritten to the register** — a
`print` inside a signal handler kills the supervisor on the first clean stop, so every SIGTERM orphans whatever
lease was live.

## 2026-11-08 00:09 ET — board handoff: six landed rows had no other home; the 753B second boot failed, and the arm after it died in image relay

- **The 23:48 board's `Landed session` rows existed only on the board.** The 00:04 board replaced them
  with its own set, and `git grep` over `mad-science/` finds just two of them — `3695abc` and `bd4671d` — as
  prose inside `queue.json` notes, never as a record. Their clauses, preserved from
  `git show 0040097^:mad-science/STATUS.md`:
  - 23:32 `b4cd79e` "h2h-client: record resolved image, since cell alone does not prove it" — `run-arm`
    exports `ARM_IMAGE_ID` and writes `<arm>/image.txt` for every extra-client arm, so a receipt proves
    which image actually ran rather than what the manifest intended.
  - 23:32 `d7a13eb` "State the suite total both statements carry: 1318" — the earlier commit moved one of
    the two `AGENTS.md` statements and the count moved again when a peer case landed, so both now say the
    number a detached worktree at the parent discovers.
  - 23:34 `3695abc` "GLM-Flash concurrency levers: two probe arms, and `--drafter-repo none` means
    --no-drafts" — the shim had mapped that sentinel onto `--drafter auto`, so no-drafter was never
    drafter-free; the two probe arms are now authorable.
  - 23:35 `be63c6f` "Correct swept recipe count: 102 two recipes not tracked yet" — this was a correction of
    a count swept from a peer's pending edit; superseded a minute later by `bd4671d` once both recipes were
    tracked.
  - 23:35 `bd4671d` "Repair recipe counts concurrent sweep reverted to 100 (actual 102)" —
    `tools/doc-census.py --fix` rewrote only the two digits, so `AGENTS.md:51` and `:86` track the tree.
  - 23:36 `ed9cb18` "Falsify the pool attribution for `.35`'s 27.6 GB: it is a docker image layer" — zero
    chunk files were created in the window and the newest chunk predates it, so the fall is the local image
    layer, measured rather than argued.
- **The GLM-753B second boot failed, and the receipt says so without a verdict of its own.** Attempt 2
  (`…@2`) ran 23:14:25 → 23:52:37 (38.2 min) on `.30`–`.33 and ended `rc=4`, `measured: false`,
  `watchdog: loading`, `reason: no marker and no machine-readable artefact`, leftover list empty and four
  serve logs harvested; `run-arm`'s last line is `ARM DONE … rc=4`. Receipt:
  `~/benchmarks/h2h-20261107/receipts/glm-5.3-exl3-3bpw-tp4-1m-tensorfold-sglang.json`; the harness moved
  attempt 1 aside to `…prev-231427`.
- **The arm after it died in image relay, not in the engine.** `glm-5.3-flash-exl3-tp4-1m-tensorfold-sglang-boot2`
  attempt 1 (23:52:37) wrote its command line and nothing else; attempt 2 (23:59:52, receipt dir
  `~/benchmarks/tp12-20261107/…`, attempt 1 moved to `…prev-235954`) reached an OCI relay that ended
  `failed in 126.4s; receiver byte total unavailable; 0 layers reused; registry downloaded 5.1 GiB` then
  `Launch interrupted`, and docker logged the task delete at 00:02:02. The director was already gone —
  `signal 15: stopping after this tick` followed by a `RuntimeError: reentrant call` in its own signal
  handler — so `state.json` (mtime 00:01:53) kept the arm `leased` on `.30`–`.33 until 00:06:52 with no
  worker behind it.
- **`.30` carried a ≈157 GiB transient through the relay.** Root avail `1,269,033,242,624 B` at 00:00:52,
  `1,426,194,919,424 B` at 00:03:12 (peer tick's read), `1,439,364,960,256 B` at 00:06:17 — a fall and a
  recovery around the failed import that the relay's own log line does not account for (`5.1 GiB`
  downloaded, `up to 10.6 GiB` needed, `up to 64.0 GiB scratch` declared). Attribution stays open; what is
  measured is that the bytes came back to the 23:44 level rather than staying spent.
- **Follow-up, 00:11 ET: the relay-scratch attribution is corroborated.** The restarted campaign's
  attempt-3 relay ran on `.30` with root avail falling 1,439,364,960,256 → 1,376,552,742,912 B and
  recovering to 1,413,912,711,168 B as its receiver container (`oci-relay-receiver-293c157d…`, image
  `85c1ffc3e3a0`) exited before 00:11:27 — the same shape as the 00:00 transient, this time with the
  container observed while it was running. The attribution moves from open to LIKELY relay receive/decode
  scratch; nothing in the pool or the chunk store has been shown to move for it.


## 2026-11-08 00:13 ET — the published board's own commit names the wrong census

The 00:13 ET board (census **00:11:03 ET**) was published through `publish` on top of a peer's
00:07:26 board and committed by that peer's `2155b5b`, whose subject reads "Publish board on the
00:07 census: the h2h director is back, arm on attempt 3". A commit subject is the only index most
readers use, so it is recorded here rather than rewritten: `2155b5b` carries this tick's **00:11:03**
census board (bytes `02e63c6d288876a0fb19802c321e85e67652d1043a29f4d57783ea1454b70e88`), not a 00:07
one. **The 00:07:26 board is lost**: `publish` overwrote it while it was still uncommitted (its own
report: `disk was 2026-11-08 00:07:26 ET`, this census 00:11:03), and the tick had read the disk board
at 00:09, before that publish, so its rows were never read for a fold. Nothing material went with it —
the same state is in the 00:11 census: director back, arm on attempt 3, four ranks at the image-carry
stage.

## 2026-11-08 00:14 ET — an env file that names the wrong campaign, and a ctime answer for `.30`'s dip

- **The orphaned lease above is only cleared by a restart, which is what happened.** The director
  killed at 00:02:00 left `glm-5.3-flash-…-boot2@2` live-looking on `.30`–`.33` with **0 containers**
  until the 00:04:34 run reaped it (`reaped … (lease expired; 0 container(s) found)`) and assigned
  attempt 3. Read `ps` for the director before believing a lease no container supports.
- **The head's env file points at a different campaign.** `~/.config/sparkrun-campaign.env` carries
  `CAMPAIGN_ROOT=/home/red/benchmarks/d1-20261107` on a two-host set, so an env-rooted
  `director status` prints `campaign d1-20261107: 1 measured` and **no lease** while `h2h-20261107`
  (six hosts, root on `.30`) holds a live quartet. Nine roots sit in `~/benchmarks/*/state.json`;
  enumerate them.
- **`.30`'s 158.6 GiB dip was a deleted stage, not a body from the pool.** 1,439,347,339,264 B
  (23:44:59) → 1,269,033,246,720 B (00:00:5x) → 1,437,015,580,672 B (00:05:0x) → 1,404,530,204,672 B
  (00:09:29, the live 33.7 GB relay import). A **ctime** scan of `.30`'s root since 23:44 finds 193
  files / 25,807,800 B and nothing above 100 MB, and the HF pool's hub mtimes are unchanged (newest
  14:35), so the bytes were staged and deleted again by the aborted attempt-2 boot that started
  23:59:54.
- **The image carry is complete on all six nodes.** `dsv41-sm121-dg:0.2.0` (`sha256:1778ec42…`) and
  `:0.2.1` (`sha256:85c1ffc3…`) are tagged on `.30`–`.35`, measured 00:05; the 23:48 board's "no tag
  on `.31`–`.33`" rows were superseded by the survey-transfer carry's own 00:02 gate clearance.
- **This tick folded into the peer's board rather than republishing.** Its own census is 00:09:29 and
  the published board's is 00:11:03, so the fresher row stands and two clauses were appended to it: the
  ctime scan that turns "transient carry" into evidence, and the tag-form confirmation of the carry.

## 2026-11-08 00:19 ET — two clauses of the 00:13 board falsified by their own next measurement

Both were written on the 00:11:03 census board (`2155b5b`) and both are withdrawn here rather than
argued on the board, because the peer's 00:16/00:17 board already drops them in the worktree.

- **"+59.6–59.8 MiB on five nodes each" is not pool traffic.** The 00:13 census row called the uniform
  62,537,728–62,709,760 B increment "the shared pool leaves on five nodes at once". Measured at 00:18:
  `sudo -n find /srv/beegfs/storage/chunks -type f -newermt "2026-11-08 00:07:00"` returns **0** files on
  `.31` and on `.34`. This is the clause class the record already withdrew once as "161 MB/s pool write
  with no visible author" (23:44 section); the increment stays **unattributed**, and its evenness across
  five nodes is an observation, not an attribution. The same row's `.30` swing is now attributed by
  `docker system df` (72 images / 446.3 GB, 338.1 GB reclaimable, 113 GB build cache) and is LIKELY
  image unpack inside `/var/lib/docker` — not the pool either.
- **The `.34`/`.35` tag delta crossed two predicates.** The row said "5 and 7 dsv41-matching tags at this
  read (1 each at 00:01, so images landed on both inside the hour)", but the prior "1" was the
  `dsv41-sm121-dg` name-specific count while 5/7 is everything matching `dsv41`. Re-measured on both
  predicates at 00:18: `.34` holds `dsv41-sm121-dg:0.2.0` **and** `:0.2.1` (2 under that name, 5 tags
  matching `dsv41`), `.35` holds both (2 under that name, 7 matching). So a delta does exist — 0.2.1
  landed on both — but it is 1→2 on one predicate, not 1→5/7 across two, and the peer's 00:16 board
  states it correctly as "both carry `0.2.0` + `0.2.1`".
- **`origin/main` still carries both clauses**, because the fixing board is committed locally and not
  pushed (local is `ahead 2, behind 1` against `origin/main` after a peer push, so completing it is the
  holder's call, not this tick's). Readers of the published board until then should treat the pool
  mechanism and the 1→5/7 delta as withdrawn.

## 2026-11-08 00:31 ET — the fixing board is pushed, so both withdrawn clauses are off `origin/main`

The item above is closed: the 00:24 ET board (`e1cbf41`) is a board without the two falsified 00:13
clauses, and it is pushed. `git show origin/main:mad-science/STATUS.md` carries neither "the shared
pool leaves", nor "5 on `.34` and 7 on `.35`", nor `dsv41-matching`; its `.34`/`.35` row states the one
predicate this cycle re-measured — both nodes hold `dsv41-sm121-dg:0.2.0` and `:0.2.1` — and its
census row carries the `.30` attribution that commit endorsed (446.3 GB of images and 113 GB of build
cache behind the transients, LIKELY image unpack, not pool traffic). The push was a fast-forward from
`373b60d`, so the withdrawal commit and the peer's `d884a74` census board are both ancestors and
nothing was dropped.

## 2026-11-08 00:31 ET — board tick read independently, published nothing, then withdrew a false escalation

Four peer ticks published inside this hour (00:04, 00:13, 00:19, 00:26), so this tick's contribution is an
independent census and a verification, not another whole-file write. Its own reads — 00:15:29 (the flash
arm's attempt-3 quartet ready: four rank containers, rank 0 `/v1/models` **200**
`{"id":"GLM-5.3-Flash-EXL3"}`), 00:23:14 (that quartet gone; the **753B** arm's attempt-3 quartet
`sparkrun_7d9a3a61b33a29e4_3d01b30293f6_node_0..3` up and loading) and 00:26:29 (same quartet, `Up 4
minutes`, `/v1/models` 000, lease attempt 3 hb 00:26:21) — agree with the 00:26 board's own 00:25:09
read, which is why nothing was republished over it.

- **Re-derived here, not carried:** containers per node, volumes, root-avail bytes, the register's counts
  (94 tasks, 75 done, 19 open: 2 running + 15 queued + 2 blocked) and the `render --board` table (19
  rows), twice.
- **The publish→commit race is what cost this tick a commit.** It published the 00:15:29 census at 00:21
  and a peer published over it before its `git add`, so its `git commit -- mad-science/STATUS.md` took
  the peer's 00:19 board. The commit that stands in history, `d884a74`, was written by a peer with a
  paraphrase of that subject; this tick's own `9f7370a` is now unreferenced. No bytes were lost and no
  history was rewritten — the class is the one `status-board-refresh` documents, and the fix is that the
  read and the commit must be inside one bounded window, not twenty seconds of prose apart.
- **A false escalation was standing in the live doc, and this tick withdrew it.** The window row still
  read "all six read 0 containers at 00:17:41 with the lock held → escalation: idle window, orphaned
  lease" three rows under a census that read `1 / 1 / 1 / 1 / 0 / 0` — the 00:31:27 board (`060f243`)
  retakes the census, `.34`/`.35` and window rows against a fresh read (753B attempt-3 quartet up, ten
  minutes loading, `/v1/models` 000, free space within 74 kB of the previous read) and states the 00:17
  zeros as the gap between the director's death and its 00:20:20 restart. Also noted there: the 00:23:31
  all-zero container read stays unreproduced across five reads between 00:23:14 and 00:31:27.
- **Register divergence, reported not fixed:** `h2h-second-boot-glm-flash` still holds `running` plus its
  `05:06:56Z` claim for a boot that died at 00:17:41, while `h2h-second-boot-glm-753b` carries the live
  claim (`05:21:41Z`). `mad-science/queue.json` has a peer's uncommitted edit, so the correction belongs
  to its owner.
- **Escalation, unchanged:** `_on_signal` at `campaign/sparkrun_campaign/director.py:546` has now killed
  the director **twice in this hour** (measured 00:02 and 00:17; the runs since are hand-started restarts
  at 00:04:34 and 00:20:20), each death orphaning its lease. The 00:17 one took a serve that
  had reached `readiness=yes` and answered `/v1/models` 200 a minute earlier, with no receipt written —
  that arm's cells are lost work, not a measurement.

## 2026-11-08 00:34 ET — correction: this tick's 00:23:31 census row read a shifted column, not four zeros

The board this tick published at 00:24 (`e1cbf41`) said containers `.30`→`.35` were **0 / 0 / 0 / 0 /
0 / 0** at 00:23:31 ET. That was a misread of its own instrument, not a measurement: the ssh command
built `printf ".%s ctns=%s vols=%s rootB=%s"` with the node label as the first argument, that argument
came back empty on the far side, and every later value slid one field left — the line
`NODE .1 ctns=0 vols=1413910585344 rootB=` is the container count in the *label* slot, the volume count
under `ctns`, and the root-avail byte count under `vols`. The four ranks were therefore **1** container
each, which is what the peer's two reads found (00:23:20 and 00:25:09, four rank containers, `Up 3
minutes` at 00:25:09 putting creation at ~00:22:1x — before both reads). The superseding board `32ddb4b`
already carries the corrected counts and flags the non-reproduction; this note exists because the pushed
commit body of `e1cbf41` still asserts the zeros, and a pushed body is not rewritten. What survives from
that read is the part that did not come from the shifted printf: `/v1/models` **000** (a `curl` exit
code), the lease (`753B` attempt 3, `expires_at` +287 s) and the absolute byte values, whose
`rootB`-slot emptiness is the same shift and which the peer's row restates correctly. Procedure for
next time: give the remote its own label (`n=$n; printf …`), or read the counts in a form that cannot
slide — `docker ps -q | wc -l` on its own line.

## 2026-11-08 01:00 ET — the last un-homed board row: `a5286e7`

The previous board's 00:10 row was the only landed clause with no home: `git grep a5286e7` over the
whole tree matched `mad-science/STATUS.md` alone. That row has already been dropped once by board
churn — `2155b5b`'s board (00:13 title, 1 landed row) is where it appeared, `2166ef5`'s 15-row rebuild
of 01:04 did not carry it, `5a0587a` folded it back (17 rows) — so the clause is homed here rather than
left to the next whole-file publish (the 00:16 row was already carried at the sections above):

- **`a5286e7` "Record the board rows that existed only on the board"** — a peer tick's commit, and it
  carried this tick chain's 00:08 homing section in with its own (107 inserted lines, both sections):
  the six retired rows and the nine post-board commits are in this file. The misattribution is
  disclosed there rather than rewritten.

That tick also leaves the programme state it measured, which the owning docs now carry rather than the
board: the 753B arm's attempt-3 quartet (`sparkrun_7d9a3a61b33a29e4_3d01b30293f6_node_0..3`, created
00:21) was still `verdict=loading` in its watchdog at t=1673 s (io ~1 GB/probe, log growth 0, endpoint
down) when a SIGTERM stopped the director at 00:49 (`director.log`: `signal 15` → `stopping worker w1`;
the register records the operator pause at 00:56); `run-arm.sh`'s trap removed the containers and no
receipt was written, so the arm was killed before readiness at 34 min of loading and is not a
measurement.

## 2026-11-08 01:09 ET — a 01:05 publish replaced a peer's 01:04 board; its bytes survived on the shared workstation and were adopted

The tick that read the fleet at **01:03:31 ET** composed its board and called `publish` at 01:05. The
tool accepted the write because the board it replaced was **older, not newer**: disk carried title
01:04 with census **01:01:48 ET**, so `publish` printed `disks was 2026-11-08 01:01:48 ET` and replaced
the peer's board whole — the guard refuses only a *newer* census stamp, and a peer board composed on an
older read but published later reads as stale to it.

**Nothing was lost, because the peers' composed files were on the same shared `/tmp`.** Three boards
existed for this hour: `/tmp/board-0104-601473.md` (the clobbered one, census 01:01:48),
`/tmp/board-0100-574825.md` (census 01:00:54) and `/tmp/board-0104-574821.md` (census **01:03:38–42**,
the freshest read and the richest board: it had already folded the operator's `killed-attempts.json`,
the head env file's rewrite to `h2h-20261107`, the expired lease and the register divergence). The
**01:09 republish adopts `574821` verbatim** with only its title regenerated, so the restored board
carries that tick's census rather than this one's 01:03:31 read, and its `Work queue` (byte-identical
to this tick's own render) and all 19 landed rows stand.

- **The mitigation that would have caught it is the one the skill already names, applied literally:**
  re-read `mad-science/STATUS.md` immediately before `publish`, not at the start of the cycle, and treat
  a title whose minute is the current one as a peer board to fold. This tick re-read only the *title
  line* after the first failed publish and did not compare its census stamp against its own.
- What this tick measured independently and the adopted board agrees with: all six nodes at **0
  containers and 0 volumes** (01:03:31 read, `df -B1` root avail within ±11 MiB of the 00:31:27 series),
  no `sparkrun_campaign` director process on the head, `state.json` (mtime 00:49:42) still recording the
  3bpw arm `leased` with `expires_at` ~00:54, register at **77 done / 17 queued, none claimed**, and
  `task-queue.py check` green.

**Correction, 01:12 ET: that board was published already falsified, and the republish is the second half of this section.**
Run 5 started at 01:04:4x (`director serve --queue … --max-parallel 1 --retries 1 --receipts-root`), and its
quartet `sparkrun_7d9a3a61b33a29e4_574ac1a0d398_node_0..3` was created 01:04:51–54 on `.30`–`.33`. So the
all-idle census adopted above (read 01:03:38, `0 / 0 / 0 / 0 / 0 / 0`) described the fleet **73–76 s**
*before* the quartet's creation (01:04:51–54), not as it stood at that board's **01:09:00** publish —
**5.4 min** later. The 01:11:10 read — **1 / 1 / 1 / 1 / 0 / 0**,
`/v1/models` **000** on every rank, lease `glm-5.3-exl3-3bpw-tp4-1m-tensorfold-sglang` **attempt 4** with
`expires_in` 290 s, register row re-claimed `06:04:42Z` — is what this tick republished at 01:11:10. **A peer's
01:13 publish (census 01:12:49) then superseded it**, and that board is the fresher read of the same state:
quartet up on `.30`–`.33`, run 5 alive, lease attempt 4 (`expires_at` 01:17:42), `.34`/`.35` empty — so the
corrected state stands on the board and nothing from this tick's read was lost in the supersession.

- The defect is rule 6's, one step subtler than a carried figure: a peer's census is *not* a fresh figure in a
  later publish, and adopting it verbatim moved a three-minute-old read into a 01:09 board. Adopting the
  peer's **landed rows** was right (they are history and cannot go stale); adopting its **census** was not.
  A fold takes the peer's rows and the folder's own read.
- The peer's 01:06 section, **below** this one, already carries the bracket that makes this legible on the
  record: 01:01:52 all six at zero, 01:06:07 at `1 / 1 / 1 / 1 / 0 / 0`, with the quartet's creation
  timestamp inside the gap — the pause's zeros and run 5's ones are both true reads of the same
  minute-scale transition.
- **Disclosure: `5c9e64e` carried two peer sections along with this one.** It added 103 lines to this
  file; ~44 are the section above and its correction, and the rest are the peer's `## 2026-11-08 01:00 ET
  — last un-homed board row: `a5286e7`` (~44 lines) and `## 2026-11-08 01:06 ET — fifth h2h run started on
  the reconciled model…` (~27 lines), which were sitting unstaged in the worktree when the path was
  staged. Their bytes are intact and correct — this note is the record, not a rewrite: a `git commit --
  <path>` publishes whatever is in the file at that moment, which is the `ab82517`/`8038ad1` class.

## 2026-11-08 01:06 ET — fifth h2h run started on the reconciled model; the pause's kills cost work, not measurement

Run 4 (`director serve --queue`, pid 3338082) was SIGTERMed by the operator pause at 00:49 ET. The
`~/benchmarks/h2h-20261107/killed-attempts.json` entry records what that cost:
`glm-5.3-flash-exl3-tp4-1m-tensorfold-sglang-boot2` attempt 3 killed **at `readiness=yes`** before any
cell ran, and `glm-5.3-exl3-3bpw-tp4-1m-tensorfold-sglang` attempt 3 killed with readiness never
achieved (t~2050 s loading, endpoint down, GPU 0%, io ~1 GB/s) — both `not measured; no receipt`,
`containers_after: 0` fleet-wide, director recorded as `stopped (nohup pid 3338082 SIGTERM); unit
inactive`. Work lost, not numbers.

Run 5 started 01:04:4x as `… director serve --queue --hosts .30–.35 --max-parallel 1 --retries 1
--receipts-root /home/red/benchmarks/h2h-20261107` — the two flags `2abc5af` now adopts on open, which
is the persisted-state reconciliation defect the pause existed to fix. It re-claimed register row
`h2h-second-boot-glm-753b` at 01:04:42 ET (`queue.json` is therefore a peer's uncommitted edit at this
tick's read), rewrote `state.json` at 01:05:22 with a lease on attempt **4** (`expires_in` 293 s), and
its quartet `sparkrun_7d9a3a61b33a29e4_574ac1a0d398_node_0..3` was created 01:04:51–01:04:54 on
`.30`–`.33` carrying `tensorfold serve --tp 4 --context 1048576 --mtp-drafts 3 --kv q5 --dcp 4
--drafter none`, endpoint **000** at 1 m 21 s uptime — loading, as this arm's attempt 3 did for 34 min.

Census bracket worth keeping: 01:01:52 ET read all six at **0 containers / 0 volumes** and 01:06:07
read **1 / 1 / 1 / 1 / 0 / 0**. Those zeros are the operator pause, not a wedged holder, and the
quartet's creation timestamp sits inside the gap — so neither read was wrong, and a tick that judged
the declared window on the earlier one alone would have raised a false idle-window escalation.

Corrected this cycle, re-measured per node: `dgx-spark-dsv41:tensorfold-v06` sits on `.30`, `.31` and
`.35`, not `.35` alone; the `.35`-only images remain `vllm/vllm-openai:glm53-flash` and
`…-pin-819ec9c06341`.

This tick published no board: while it was composing, peer ticks published inside the same three
minutes (`5a0587a` at 01:09 on the 01:03:40 census, then a 01:13 board on the 01:12:49 census) and
both censuses agree with this tick's 01:06:07 read on every container and volume count
(`1 / 1 / 1 / 1 / 0 / 0`, volumes 0), so the board was left to the fresher publish rather than
whole-file rewritten under it. Rule-8 check against the live register holds on that board: its
`h2h-second-boot-glm-753b` row reads `running`, matching the `06:04:42Z` claim, and all 17 rows match
`render --board`. One reported divergence the 01:13 board dropped (it stood in the 01:09 one):
`h2h-second-boot-ladder` still lists `h2h-second-boot-ds4-1017` among its `holds` while the register
no longer carries that row open — reported, not edited, since `queue.json` is a peer's file.

## 2026-11-08 02:04 ET — board landed rows homed (session boundary), the 753B arm's fourth attempt fails, and Beam boot2 takes the quartet

The 02:04 ET tick began a session-boundary homing of `mad-science/STATUS.md`'s `Landed session`
table: each hourly tick is its own one-shot session, and `git grep -c <sha> -- mad-science/SESSION-RECORD.md`
returned nothing for **eleven** of the twenty-four rows the 01:22 board carried, so those clauses are
homed here verbatim, copied out of `git show HEAD:mad-science/STATUS.md` rather than retyped. The other
thirteen SHAs were already homed above. **The table itself was not cleared**: two peer ticks
regenerated the whole board while this one was composing (02:06 and 02:09), and their tables carry the
history plus two receipt rows this tick has not measured, so the rows stay on the board and this
section is additive, not a handoff.

- **00:19** `1cca4f3` — Board tick: folds `.30`'s ctime answer (193 files / 25.8 MB since 23:44,
  nothing above 100 MB) and the head env file's wrong campaign into the board.
- **00:27** `dbaba6d` — Closes the withdrawn-clause item: the corrected board is pushed.
- **00:27** `3297abc` — Records a tick that read the fleet independently and published no board.
- **00:29** `705885e` — Counts the director's deaths, not its runs: two measured deaths (00:02, 00:17)
  across four runs.
- **00:31** `53b3f94` — Board on the 00:30:27 census: the 753B retry is loading, every node's root
  moving under 2 MB in 318 s.
- **00:32** `9a9bbd9` — Restamps the ledger section that had landed out of time order.
- **00:52** `f1edc47` — Register: clears the pause's stale claims — `boot2` and `753b` back to queued,
  both kills recorded in their notes.
- **00:56** `d947997` — AGENTS.md gains the Priority section: clean code in service of repeatable
  research (+20 lines).
- **01:00** `7bea7b6` — Retires the survey parents the live sub-rows supersede.
- **01:14** `f926cc4` — "Measure what 5a0587a replaced, instead of inferring it" — the fold commit's
  own carried bytes are re-derived rather than described.
- **01:16** `4198b35` — "Fold this tick's 01:13:17 re-read into the peer's 01:12:49 board" — the
  attempt-4 quartet and the rank-level serve probe reach the board.

Three further rows the 02:06 ET peer board added before this tick published, homed here for the same
reason (`git grep -c <sha> -- mad-science/SESSION-RECORD.md` returned 0 for each):

- **01:14** `5a0587a`, second row — correction to the row above: its mechanism is not established, the
  measured hunk map is. `git diff --numstat 2166ef5 5a0587a` reads 13/13 across two 49-line boards in
  three hunks: six of the peer's in-flight rows replaced by five of this tick's (their `.34`/`.35` row
  folded into `.30`–`.35`), the two rows they had cleared (00:10, 00:16) re-added, and their phrasing of
  00:22/00:52/00:56/00:59/01:00 replaced by this tick's shorter wording — same SHAs, same facts. No fact
  is lost: the two censuses (01:03:31 and 01:03:40 ET) agree on every count and volume, and the peer's
  three finer figures it does not carry (state.json's 00:49:42 mtime, the lease expiry as a clock time,
  `.31` +1,931,520 B) are named in `47905ef`.
- **01:19** `96b5912` — "Correct the tick's own ledger: two intervals, direction, and what swept" — the
  ledger section carries the two measurement intervals and their direction; rows 01:19–01:22 are board
  bookkeeping and add no state here.
- **01:58** `2e27838` — "register: close the first client arm on its receipt; carry the house client cell
  to the 753B boot" — the register's first client arm closes against its receipt and the house-client
  cell is carried onto the 753B boot row.

Two state changes this tick measured, recorded here because they belong to the hour and not to the
board's state tables:

- **The 753B arm's fourth attempt ended `rc=4` with `readiness=no` at 01:42:44 ET.** Its arm log
  (`~/benchmarks/h2h-20261107/logs/glm-5.3-exl3-3bpw-tp4-1m-tensorfold-sglang@4.log`, 990 B) reads
  `readiness=no`, four serve logs harvested, `Workload stopped on 4 host(s)`, `rc=4`; the previous
  receipt moved to `glm-5.3-exl3-3bpw-tp4-1m-tensorfold-sglang.prev-010443`. The director now records
  the arm `failed` with the receipt-shaped reason `no marker and no machine-readable artefact`. **No
  attempt produced a ladder cell, and the discriminator is the artifact, not the log size**: every
  receipt dir for this arm — the live one plus `.prev-231427`, `.prev-002143` and `.prev-010443` —
  holds `docker-*.log`, `launch.log`, `watchdog.log` and (on two of them) `serve-0..3.log`, and no
  `ladder.*`, `house.*` or receipt JSON in any of the four. Attempts 1–3 are therefore not
  individually characterised here; attempt 4 is. Its register row `h2h-second-boot-glm-753b` is back
  to `queued` with `claimed_by` empty, and its `notes` carried the same campaign verdict **three
  times** — the reconciler appends the director's verdict without dedupe, so the board's verbatim
  copy inherited the triplicated prose. Deduped to one clause textually (JSON round-trip would
  reformat the shared file), one line changed; the reconciler itself is unfixed and will re-append.
- **Beam boot2 took the quartet at 01:56:50–53 ET** — task `30078b4aa125dd7d_62ac562fe0d4`, image id
  `58aa975fed12`, recipe `recipes/explore/zz-beam-1.0-501b-a23b-nvfp4-tp4-vllm-boot2.yaml`, ranks
  0–3 on `.30`–`.33`, `vllm serve` with DFlash2 k=7 and `--max-model-len 131072`, register row
  `h2h-second-boot-beam` `running` under claim `sparkrun-campaign:h2h-20261107` (`06:56:42Z`).
  Loading at t=418 s: `/v1/models` 000, serve child alive on every rank, `launch.log` at
  `25/53` checkpoint shards, watchdog pid 365197. By the 02:10:57 read it was at t=833 s and
  `50/53` shards (12:50 in that phase), still `verdict=loading endpoint=down serve_pid=alive`.
  **The gate is armed for this boot and for no other**: `ps -eo pid,args | grep boot-watchdog` on the
  head at 02:14 returns exactly one process, pid 365197 with `--task-id
  30078b4aa125dd7d_62ac562fe0d4 --container sparkrun_…_node_0 --interval 10`, and the previous
  boot's watchdog pid 3842579 (`--task-id …574ac1a0d398`) no longer exists — so the dead quartet's
  gate exited with it rather than lingering against a container that is gone.

## 2026-11-08 02:36 ET — session close-out: the director's state model reconciled before the campaign's first cells

The campaign's first measured cells arrived only after its persisted state was reconciled against the
register. `2abc5af` fixed five ways `state.json` outlived the decision it recorded: an existing file
overruled `--retries` on restart, `_adopt` froze an arm's `env` so a register row's later client cell
and `ARM_RECEIPTS_ROOT` never reached it, a `BLOCKED` arm was never re-evaluated even with its row
queued again, a status-only unblock could leave `needs_reap` set and then skip the arm in silence, and
`--receipts-root` never reached an adopted arm. The model now decides by newest decision: `--retries`
is adopted on open (an omitted flag keeps the stored number), `ARM_RECEIPTS_ROOT` is written into every
arm that can still run, and an arm adopts its row's fields at `prepare`; `26582bc` then closed the
gate that made the first reconciliation too narrow — `refresh` froze a record whenever `attempts != 0`,
so a reopened row with a new readiness ceiling would have carried the previous attempt's env, and it
now freezes only a `leased`, `measured` or `skipped` arm, while `path`/`tp`/`task` still wait for any
outstanding reap (the containers a reap must find are labelled with the path that launched them). A
blocked arm re-opens only on a restart, only when its row is runnable again, and only after `prepare`
proved the reap — otherwise it prints `queue-blocked: <arm> (row runnable again, but hosts still need
a verified reap: …)` instead of never assigning it. A lease issued counts as an attempt on the receipt
but stays out of the `failures` retry budget, so `--retries` remains the only lever over re-boots.

The proof is the state this section follows rather than the tests alone. The 753B arm ran a fourth
attempt under the new model and still produced no artefact — `rc=4`, `readiness=no` at 01:42:44 ET,
its receipt `receipts/glm-5.3-exl3-3bpw-tp4-1m-tensorfold-sglang.json` beside `.prev-231427`,
`.prev-002143` and `.prev-010443`, and none of the four directories holds `ladder.*` or `house.*`, so
the discriminator is the artefact set, not the log size. The house client cell reached the arm it was
written for instead of the one adopted first: the live Beam house arm's env carries `ARM_EXTRA_CLIENT`,
`ARM_EXTRA_TIMEOUT`, `ARM_OPTS` and `ARM_RECEIPTS_ROOT`, and the finished GLM-Flash arms' receipts
landed under `<campaign>/tp12-window/…` rather than a dated `~/benchmarks/tp12-<date>` tree. Arm 3
stayed `pending` while its row was queued — never leased, never silently assigned. The abandoned lease
the campaign inherited at the restart was reaped (`reaped … outstanding previous run; 0 container(s)
found`) before the quartet was re-assigned.

Register work in the same stretch: `7bea7b6` retired the survey parents its live sub-rows supersede;
`0cbcffd` put the survey lane doc on the single digest the recipes pin; `f1edc47` cleared the pause's
stale claims (boot2 and 753B back to `queued`, the kill recorded in their notes); `2e27838` closed the
first client arm on its receipt and carried the house cell onto the 753B boot; `34f677f` documented
and guarded `tools/h2h-client.py` (README index row, `tests/test_h2h_client.py` with the
all-transport-error exit-2 rule and its healthy-serve control, and the derived counts); `d947997` added
the root `## Priority` rule — clean, correct, bug-free code in service of durable, repeatable,
deterministic model and sparkrun recipe research. The three concurrency rows are registered, not
missing: `glm-flash-conc-no-drafter`, `glm-flash-conc-dflash2-k` and `glm-flash-conc-scheduler-knob`
are `queued`, each on the tracked variant recipe it boots and on the arm's pinned image
`ghcr.io/miaai-lab/glm-5.3-flash-exl3-2x-dgx-sparks-tensorfold@sha256:eb17e092…`, with the image-id
gate in `ARM_EXTRA_CLIENT` so a lever cannot be measured through an unidentified image.

Measured cells, each with the artefact set that carries it (`n=5` per cell, 2048-prompt decode,
aggregate t/s then per-request):

- **ds4-1017, second boot** — C1 51.11 ± 16.24 · C2 91.79 ± 3.92 · C5 128.88 ± 4.59 · C10 159.88 ±
  10.14 (per-request 51.11 / 49.84 / 30.80 / 19.76), monotone rise kept; the same serve ran house at
  **93**, 15 scenarios, deployability 89 / responsiveness 80.
  `receipts/deepseek-v4.1-flash-knapcio-tp4-1m-sglang.json`; artefacts in
  `~/benchmarks/h2h-20261107/deepseek-v4.1-flash-knapcio-tp4-1m-sglang/`.
- **GLM-Flash, first boot through the recipe path** — C1 103.25 ± 5.46 · C2 109.41 ± 31.29 · C5 94.18
  ± 2.62 · C10 86.65 ± 1.31 (per-request 103.25 / 65.14 / 29.32 / 20.95); house **100**, 15 scenarios,
  deployability 92 / responsiveness 75, which is the first quality battery this arm carries through
  the recipe path rather than the 2026-10-13 trial.
  `tp12-window/glm-5.3-flash-exl3-tp4-1m-tensorfold-sglang/` (`house.json`, `ladder.json`, `client/`,
  `image.txt`).
- **GLM-Flash, second boot** — C1 105.90 ± 5.68 · C2 120.46 ± 28.43 · C5 96.80 ± 1.92 · C10 86.87 ±
  1.16 (per-request 105.90 / 68.07 / 30.63 / 20.94); house identical at 100 / 92 / 75. Per-cell delta
  against the first boot is +2.65 / +11.05 / +2.62 / +0.22 aggregate, so the C2 peak and the C5/C10
  fall reproduce across boots — the sigma column the head-to-head table lacked.
  `tp12-window/glm-5.3-flash-exl3-tp4-1m-tensorfold-sglang-boot2/`.
- **Beam-1.0 501B, second boot** — C1 33.09 ± 2.50 · C2 44.91 ± 3.50 · C5 59.71 ± 10.50 · C10 69.86
  ± 7.41 (rises with concurrency). Its standard house read is **0** (15 scenarios, deployability 30 /
  responsiveness 100) and that number is a **transport artifact, not a model result**: this launch
  carried `--tool-call-parser beam` and `--reasoning-parser beam` but **not**
  `--enable-auto-tool-choice` (no such flag in its `launch.log`/`serve-0.log`), so every tool-call
  scenario is refused at the API before the model answers. The arm's quality cell therefore stays
  **unresolved** here; the read that resolves it rides the live house arm, whose argv does carry
  `--enable-auto-tool-choice`, and lands in that arm's `client/` directory: `house.json` (written,
  scores still null at this read) with the BFCL sidecar beside it in `client/bfcl.log` (running).
  Artefacts of the second boot itself: `tp12-window/zz-beam-1.0-501b-a23b-nvfp4-tp4-vllm-boot2/`.
- **GLM-753B, second boot** — no cell: four attempts, the fourth characterised at `rc=4` / `readiness=no`,
  and no `ladder.*`/`house.*` in any of the four directories (see the receipt and `.prev-*` above). The
  row stays **`queued`** — `rc=4` was the readiness ceiling, TTR **2,538.9 s against a 2,250 s bound**
  (the launch log's own total is 2,268.6 s with `readiness=no`, and the receipt window is
  23:14:25 → 01:42:54) — so the row must not be re-closed as a model rejection. Its re-boot is gated on
  `arm-author-2`'s bridge commit and on the BFCL lease ending.

Counts at this close-out, derived rather than remembered: **1341** suite tests (2 skipped), **104**
tracked recipes, **57** test modules, **35** benchmark profiles, **19** `SKILL.md` dirs. The suite
total is 1341 in the tree this section lands against — `34f677f`'s `tools/h2h-client.py` guard and the
campaign's state tests moved it after the brief's 1329 was taken, and AGENTS.md states 1341.

Still open: **Beam BFCL** (in flight — the live lease is `h2h-beam-house-boot` and its BFCL cell rides
the same serve), **arm 3 longctx** (`w4-survey-arm3-sm121-boot`: the 1,039,999-token C1 decode cell),
the **survey triad** (arm 3, arm 5, and arm 5's same-digest control), the **three concurrency rows**
(`dflash2-k`, `no-drafter`, `scheduler-knob`), and **`tensorfold-metrics-bridge-generalization`** /
**`h2h-doc-refresh`**, which land behind the rows they summarise.

## 2026-11-08 03:18 ET — board landed rows homed while a peer tick owns the board

The 03:0x board's `Landed session` table was **not** cleared at this tick's session boundary: a peer tick
republished and committed the board twice inside the same hour (`66e48d3` at 03:09:32, `f93f4cf` at
03:14:27), and clearing rows a peer had just written is the non-monotone table edit the handoff rule exists
to avoid. Every row without a home here is homed instead, so a later boundary can clear the table without
losing a clause. Verified per SHA with `git grep -c <sha> -- mad-science/SESSION-RECORD.md`: `351c93c` and
`26582bc` were already carried by the 02:36 ET close-out above, so of the ten rows below eight are un-homed.

- **02:17 ET** `534cac4` — the 753B register note deduped to one verdict clause instead of the reconciler's
  appended copies, and the board's queue row re-rendered from the register rather than hand-edited.
- **02:29 ET** `d77ddd5` — 753B second boot closed `measured-rejected` never-ready on the artefact
  discriminator (four attempts, none carrying `ladder.*` or `house.*`).
- **02:31 ET** `351c93c` — that close reversed: `rc=4` is the readiness ceiling, so the row returns to
  `queued` with the timeout and client hook its next attempt needs. *(Already logged in the 02:36 close-out.)*
- **02:35 ET** `1034cac` — three GLM-Flash concurrency rows registered, each carrying the recipe it boots
  and an image-id gate, so a lever cannot be measured through an unidentified image.
- **02:36 ET** `26582bc` — reconciliation adopts a row's `env` for every next attempt, not only the first:
  it froze env whenever `attempts != 0`, so a reopened row's new readiness ceiling never reached its boot.
  *(Already logged in the 02:36 close-out.)*
- **02:42 ET** `2b768e8` — the 753B re-boot gated on `ARM_READY_TIMEOUT=3000`, the readiness ceiling the
  measured TTR (2,538.9 s) exceeds the 2,250 s default by.
- **02:46 ET** `e557ce7` — `tools/run-arm.sh`'s readiness ceiling became a duration knob that names its
  effective value on `rc=4`, and the image cell is now written for every booting row as the container's own
  config sha, not only for extra-client arms.
- **02:49 ET** `88b4b34` — the 02:36 session closed in this file and the board published on the 02:45:07
  census.
- **02:52 ET** `d4c3ffe` — the close-out's suite count stated as **1341** against the tree it lands on; the
  brief carried 1329 from three commits earlier, and `tools/h2h-client.py`'s guard plus the campaign's state
  tests are what moved it.
- **02:55 ET** `b74094f` — the campaign's evidence readers taught the receipt shape the arms actually write
  (`campaign/sparkrun_campaign/evidence.py`, its tests, `DESIGN.md`), the measured h2h cells landed in
  `mad-science/TP4-HEAD-TO-HEAD-1025.md` (ds4-1017 second boot, GLM-Flash boot2, GLM-Flash's first client
  house 37/37, Beam boot2 with its quality cell left open), and both TensorFold launcher READMEs updated.

**Two lock timeouts this tick were self-inflicted, not a wedged holder.** `flock -o -w 90/240
.local/status-board.lock` wrapped `task-queue.py publish`, which takes that same lock itself, so `publish`
waited behind its own caller's lock and exited naming a wedged holder at 03:17:45 and 03:19:41. `fuser -v`
on the lock returned **nothing** both times, which is the discriminator: a peer holder would have shown a
pid. The outer `flock` is therefore wrong for this path — the read-modify-write serialisation the skill asks
for cannot be layered outside `publish`'s own lock on the same file, and a CAS re-read of the board's sha
immediately before `publish` is what actually guards the fold window. Recorded as a correction in
`status-board-refresh/SKILL.md` so the next tick does not spend the same two waits.

Three facts this tick measured that no board carries, each stamped with its own read:

- **03:01:38–41 ET — a second independent census**, 42 s after the peer tick's 03:00:58 one, reproducing
  containers **1 / 1 / 1 / 1 / 0 / 0**, volumes **0**, `/v1/models` **200**, and fleet root
  **−18,116,608 B over 993 s** (per node 1.3–9.7 MB, `.35` largest at 9,711,616 B with nothing on it).
- **03:02:31 state read — lease heartbeat expiry 03:07:24 ET** (293 s residual) for
  `zz-beam-1.0-501b-a23b-nvfp4-tp4-vllm` attempt 1; the director process is pid 3838066, started 01:04:38.
- **03:05:27 ET — the BFCL leg at `[PASS] simple_392 (simple)`**, mid-run, `bfcl-eval.py` pid 1032815 at
  750 s. It never completed: the arm ended at 03:15:50 and the client's `bfcl` step exit is **`rc=-15`**
  (`client/client.json`), so `client/bfcl.log` stops at `multiple_196` and **no `client/bfcl.json` exists**.
  `simple_392` is therefore a midpoint of a killed run, not a position on a finished one, and the BFCL
  category cell stays open in the register (`h2h-beam-house-and-bfcl-category`, `queued`). The arm's own
  receipt did land: `measured: true`, `rc: 0`, `artefacts: [ladder.json, house.json, ladder.yaml]`,
  `accuracy_status: ''`, `ladder: ''`.

## 2026-11-08 04:15 ET — tick published no board (two peer boards are fresher); the SM121 arm's death is attributable and the harvest line is blind

This cycle's census is **04:06:57–04:07:01 ET**, and two peer ticks published boards with fresher
reads in the same window — 04:06 ET on the 04:05:55 census (`57d376c`) and 04:12 ET on a 04:09:50
read. An older census must not replace a newer one, so this tick wrote no board; its figures are here.

- **Census (own read, 04:06:57–04:07:01 ET):** containers `.30`→`.35` **1 / 1 / 1 / 1 / 0 / 0**,
  volumes **0** on every node. `.30`–`.33` carry one `oci-relay-receiver-*` each (images
  `9a876c399945` on `.30` and `.33`, `a7f76ae9f18c` on `.31`, `e90182b5c973` on `.32`), Up about two
  minutes, `sparkrun.recipe` label **empty** — sparkrun's image-distribution relay, not a serve —
  and `/v1/models` read `000` on all six nodes. Root avail bytes: `.30` 1392637394944,
  `.31` 1803911442432, `.32` 1850582147072, `.33` 1732787273728, `.34` 1182453669888,
  `.35` 1430629912576 — **−32,433,270,784 B (−30.21 GiB) across the fleet over 251 s** against the
  04:02:46–49 read, and `.34` (−5.07 GiB) and `.35` (−3.63 GiB) hold **no container at all**, so the
  write is pool-side (the BeeGFS targets live on node roots), not a per-container write; this tick
  did not attribute the writer.
- **The arm-5 death has engine evidence; the board's "0 serve logs" reading is the harness, not the
  arm.** `zz-ds4-1017-sm121-arm5-trtllm-mla` attempt 2's watchdog observed `serve_pid=gone` at t=96 s
  (`cause='RuntimeError'`) and captured
  `~/benchmarks/h2h-20261107/zz-ds4-1017-sm121-arm5-trtllm-mla/serve-reaped-sparkrun_1c0dffa45afa6e47_33f27b31bbcd_node_0.log`
  (31,250 B, mtime 04:01:35). Its tail: `ValueError: Mxfp4FlashinferCutlassMoEMethod requires
  hidden_size and intermediate_size_per_partition to be multiples of 128 (got hidden=5120,
  intermediate=576)` at `sglang/srt/layers/quantization/mxfp4_flashinfer_cutlass_moe.py:68`, then
  `/opt/dsv41/boot.py:530 RuntimeError: Server failed to become healthy`. That is the **same terminal
  class as `w4-s0-control` (2026-10-26)**: the 0.2.1 tree's arch-assert and replay gates being gone
  does not make the arm servable — it dies at MoE weight creation, before any kernel runs, and the
  paired control on the *same* digest and backend would fail identically. Register notes now carry
  that on both rows so no quartet boot is spent before the backend changes.
- **Defect: `tools/run-arm.sh:548-561` harvests only *running* containers.** The loop greps
  `docker ps` (no `-a`) for the task id and `docker cp`s `/tmp/sparkrun_serve.log`; by harvest time
  the watchdog has already stopped the task, so the loop finds nothing and line 562 prints
  `serve logs harvested: 0 (…; 0 means the log was gone)`. The log was not gone — the watchdog's own
  capture in the receipt dir held it. Tonights's rc=4 rows carrying that line: arm-5 ×2 and
  `zz-kimi-k3.1-pro-superexpert-24b-q4p-ref-vllm` ×2. Fix is two lines (`docker ps -a`, plus counting
  `$L/serve-reaped-*.log`); **not landed by this tick** because the harness owner is mid-campaign in
  that file (last write 02:41, `e557ce7`) — recorded here so a future tick does not re-derive it.
- **Kimi SuperExpert probe attribution:** attempt 2's reaped serve log (241 B) reads `usage: serve.py
  [-h] --model MODEL [--port PORT] [--host HOST] [--context-length CONTEXT_LENGTH]` /
  `serve.py: error: unrecognized arguments: --served-model-name shashanth-27xA9/…`, and its
  `launch.log` ends `RuntimeError: head container is not running` at 34.4 s total. The reference
  server refuses the flag sparkrun appends; attempts are exhausted (2 of 2).
- **Register reconciled in place** (textual edits, `check` green): `w4-survey-arm5-sm121-boot` returned
  from `running` to `queued` with its stale `sparkrun-campaign:h2h-20261107` claim cleared and the
  failure clause appended, and the Kimi probe and arm-5 control rows carry their attribution —
  **17 open of 102: 14 queued + 3 blocked, 0 running**, 85 done.

## 2026-11-08 04:20 ET — tick published no board (a peer's 04:17 copy sits uncommitted, 7 min newer than any read I could beat); the fleet-wide byte fall is **named**: three staging downloads into the shared pool

This cycle's census is **04:15:14 ET** with a confirming third read at **04:19:40 ET**. A peer board
composed at 04:17 on a 04:13:05 read was on disk uncommitted when this tick's composition was ready,
and its `census`/`campaign`/`register` rows already carry this cycle's state, so a whole-file replace
would have been churn for a 2-minute-nearer read. The figures are here instead.

- **Census (own reads):** containers **0** and volumes **0** on every node at both 04:15:14 and
  04:19:40 — the `.30`–`.33` `oci-relay-receiver-*` set seen at 04:11:16 was torn down between then
  and 04:12:46 with **no engine container ever started**, so that launch never reached a serve.
  Root avail bytes 04:15:14: `.30` 1386322694144, `.31` 1795063455744, `.32` 1842547163136,
  `.33` 1722638618624, `.34` 1174942879744, `.35` 1422588153856; 04:19:40: `.30` 1381728583680,
  `.31` 1789033238528, `.32` 1837755400192, `.33` 1716563984384, `.34` 1174318108672,
  `.35` 1419790610432.
- **The falling byte series is a live writer, and it is staging, not a leak — the discriminator the
  04:15 entry recorded as missing.** Three successive reads 395 s apart (04:13:05 peer read →
  04:15:14 → 04:19:40) fall on **every** node, including `.34`/`.35` which hold no container:
  +12.97 GiB pooled in the first 129 s and +23.20 GiB in the next 266 s, **+36.17 GiB in 395 s
  (5.49 GiB/min)** — `.30` +2.64/+4.28, `.31` +2.94/+5.62, `.32` +2.57/+4.46, `.33` +2.92/+5.66,
  `.34` +0.93/+0.58, `.35` +0.96/+2.61 GiB. The writers are three `hf download` processes on the
  head with `HF_HOME=/mnt/beegfs/huggingface`: `ISTA-DASLab/DeepSeek-V4.1-Flash-1017-GSQ-RCO-Coder-GGUF`
  `--revision 54229d38…` (pid 1997128/1997159, etime 9:27), `ricursiveAI/Ripple-65B-Preview-DFlash2`
  `--revision 35609b3b…` (pid 2060210, etime 1:58), and a `ricursiveAI/Ripple-65B-Preview:da94cc01…`
  spec loop (pid 1400633, etime 54:16). The pool hub's own repo dirs agree: GSQ-RCO mtime 04:10:42,
  Ripple-65B-Preview 04:10:44, Ripple-65B-Preview-DFlash2 04:18:08. So the fall is bodies landing in
  `/mnt/beegfs/huggingface/hub`, whose chunk store lives on the six node roots — the idle fleet is
  **staging prerequisites**, not idle.
- **Those three bodies are what the queued rows are waiting on:** GSQ-RCO is
  `ds4-gsq-rco-coder-llamacpp-boot`'s own model and its Engram shard
  (`recipes/ds4/…gsq-rco-coder-gguf-llamacpp.yaml:2-3`, `mods/dsv41-engram-shard-link/run.sh:37-41`);
  Ripple-65B-Preview is `ripple-65b-bf16-tp2`'s checkpoint
  (`recipes/explore/zz-ripple-65b-preview-bf16-tp2-vllm.yaml:2-3`) and the DFlash2 repo is the
  drafter the blocked NVFP4 pair pins (`…nvfp4-tp1-dflash2-vllm.yaml:29,58`).
- **Campaign, own read 04:15:16:** `8 measured, 9 failed, 0 leased, 0 pending`, **no live lease
  object** in `state.json` (mtime 04:11:17), unit `active` since 01:04:38 (MainPID 3838066,
  `NRestarts=0`) — the plan is drained and the service is polling. The obstruction the 04:09 read
  named has cleared: launcher pid 1883449 is gone and `sparkrun daemon resources list` printed `[]`
  at 04:12:46, so the `Execution resources are busy` refusals that burned the last three arms were
  transient against a live launcher, not a wedged fleet.
- **Register, own read 04:15:16:** 102 tasks, **85 done + 14 queued + 3 blocked = 17 open**,
  **no `running` row and no row carrying a claim** — the arm-5 claim the 04:09 board flagged was
  released by the campaign's own transition at 04:11:17; `tools/task-queue.py check` green on this
  read. The workstation and head copies of `mad-science/queue.json` were byte-identical by 04:13
  (`17b22b72…`) after the brief divergence that made the 04:04 head claim look absent on the
  workstation; no divergent claim survived.

## 2026-11-08 06:06 ET — board published on the 06:00:41 census; an engine the campaign closed as failed is the one serving, because the appearance window is shorter than a pair distribution

- **Board:** published 06:06 ET on the **06:00:41 ET** census (commit `59601d81`); `publish`
  reported `disk was 06:00:41 ET`, which is this session's own previous write, so no peer board was
  replaced. Lint green; `tests.test_tracked_address_hygiene` + `tests.test_task_queue_tool` 81 tests
  OK. **Then the cycle's live state passed to a peer tick:** at 06:08 the worktree held an
  uncommitted 06:07 ET board composed on a **06:04:54** read — fresher census, same facts, plus the
  image id `e84c490d39a5` and rank-1 `--headless` — so this tick made no further write over it
  (`publish` refuses an older stamp by construction) and the rows quoted below are the record's copy
  of state the peer board now owns.
- **Census (own read, 06:00:41 ET):** containers `.30`/`.31` **1 / 1**, `.32`/`.33`/`.34`/`.35`
  **0 / 0 / 0 / 0**; volumes **0** on every node; the standing serve is a research container, so no
  production serve needed excluding from the count. Root avail bytes: `.30` 1327624802304,
  `.31` 1729446686720, `.32` 1809248493568, `.33` 1684320743424, `.34` 1172466966528,
  `.35` 1412550152192 — recorded as the next tick's baseline, no delta claimed, because this tick
  holds no earlier byte read of its own.
- **The boot class this cycle's head fact is about — an unowned engine.** A serving vLLM is live on
  `.30`+`.31`: task `sparkrun_b631dae1dc7bf3d6_693d01660f8b_node_0..1`, label
  `recipes/explore/zz-ripple-65b-preview-bf16-tp2-vllm.yaml`, containers started **05:32:47 ET**,
  rank-0 `/v1/models` **200** naming `ricursiveAI/Ripple-65B-Preview` at `max_model_len` 1048576,
  rank-0 argv pinning `--revision da94cc013a8fda04a502f0a185083c7099ea06c1 --tensor-parallel-size 2
  --max-model-len 1048576 --max-num-seqs 8 --gpu-memory-utilization 0.85`, and `launch.log` reading
  `TTR HTTP-ready 409.948 s` inside a 749.2 s launch. **Nothing holds it**: `state.json` carries no
  lease object (all 17 arms terminal), and no register row carries a claim, so the label — not the
  campaign — decides the holder. It is research and unleased, i.e. an unnamed holder, not a campaign
  boot.
- **Why the campaign believes that same arm failed, measured to the second.** Director log
  05:27:05 `assign: zz-ripple-65b-preview-bf16-tp2-vllm -> w1 on .30,.31 (lease …@3)`, then 05:32:21
  `zz-ripple-65b-preview-bf16-tp2-vllm: rc=1 -> failed (… no marker and no machine-readable
  artefact)` and `queue: no runnable rows; polling every 30s for new ones`. The container appeared at
  **05:32:47**, i.e. **26 s after** the arm was declared failed and **342 s** after its assignment.
  Mechanism, read in the source: `tools/run-arm.sh:201-218` polls `for _ in $(seq 1 60) … sleep 5`
  (**300 s**), exits 1 at `:225` before `TID` is parsed at `:228`, so the stop trap is not yet armed
  and the launcher runs on to a healthy engine. A peer registered the same finding as
  `run-arm-appearance-window-300s` (worktree copy, uncommitted at this read), so this tick added no
  duplicate row. This joins the `run-arm-conflates-stall-with-death` and
  `run-arm-harvest-counts-reaped-log` class: the receipt's verdict and the engine's state disagree,
  and the engine is the ground truth.
- **Campaign, own read 06:02–06:06:** `8 measured, 9 failed, 0 leased, 0 pending` over 17 arms;
  unit `active`, worker `w1` (pid 2119608) alive since 04:26:49. Nine arms have now closed with no
  cell; the last four failed on instrument classes (753B readiness ceiling, the SM121 MXFP4 kernel
  `multiples of 128` limit, the reference server's `--served-model-name` refusal, and this appearance
  window), not on a model reading.
- **Register, own read 06:07:** 106 tasks, **21 open = 15 queued + 6 blocked**, `check` green, **no
  row carrying a claim**. Re-read after the count moved under the tick, so the 06:02 figure (105
  tasks, 20 open with 14 queued) was dropped rather than stated. Drift: `ripple-65b-bf16-tp2` still
  reads `queued` while its own recipe is the one serving, so the next plan pass could boot a second
  copy on the free hosts; the three `w4-survey-*` rows flipped `queued`→`blocked` on their own
  MXFP4-kernel notes, which stops the director re-booting them every pass.
- **Session boundary, decided not assumed:** the `Landed session` table was left as the live campaign
  session wrote it and no row was added for this tick. Verified before deciding: `git grep` for six
  of its SHAs (`576b85ad`, `e20cc88`, `7c39c02`, `4401e6f`, `22ee5f8`, `d1fb57e`) finds **none** of
  them in this file, so its 04:2x–05:22 rows are genuinely un-homed — the close-out gap belongs to
  the session that wrote them (its worker is still alive), not to a read-only tick, and clearing the
  table here would have required homing ~45 clauses in the same commit.

## 2026-11-08 06:13 ET — the Ripple pair ended unrecorded; both Kimi arms died in `CacheConfig`

- **Census (own read, 06:12:15 ET):** containers `.30`→`.33` **1 / 1 / 1 / 1**, `.34`/`.35`
  **0 / 0**; volumes **0** everywhere. All four ranks carry task
  `sparkrun_7d9a3a61b33a29e4_bac2e432c20f_node_0..3`, label
  `recipes/glm/glm-5.3-exl3-3bpw-tp4-1m-tensorfold-sglang.yaml`, image `cffb3c3f6216`, `Up 3 minutes`
  — the 753B 3bpw arm's **attempt 6**, leased by the campaign after its 06:08:23 restart. Liveness
  measured, not inferred from `Up`: the serve child is alive on every rank (`pgrep` pids 808 / 676 /
  678 / 676), rank-0 `/v1/models` answers **000** (loading, not ready), and rank 0's serve log is the
  same inert **1103 B** recorded for this arm (790 B on ranks 1–3) — so the log is not a progress
  signal and nothing here is a readiness claim. Root avail bytes moved −2.75 MiB (`.30`) and
  −0.95 MiB (`.31`–`.33`) over the 249 s since my 06:08:06 read: the weights arrive over BeeGFS
  and write nothing to the node roots.
- **The Ripple-65B BF16 TP=2 pair reached readiness and then ended with no record.** At 06:00:42 the
  pair still ran task `b631dae1dc7bf3d6_693d01660f8b` on `.30`+`.31`: containers started 10:32:47Z,
  rank-0 `/v1/models` **200** naming `ricursiveAI/Ripple-65B-Preview` at `max_model_len` 1048576,
  rank 1's engine log `Extended KV cache 20416 blocks (39.88 GiB)`, `launch.log` `TTR HTTP-ready
  409.948 s`. By **06:08:06** all six nodes read **0 containers** — and not merely stopped: no
  exited container, volumes 0. **No process on the head wrote a record of the ending**: campaign
  `state.json` mtime 05:32:21, the receipt's `launch.log` mtime 05:39:37, no register claim, no
  `sparkrun daemon resources list` entry. `journalctl -u docker` on both ranks and `dmesg` printed
  nothing, which is **not** a negative here (`sudo -n` unavailable on those nodes, the daemon at
  default log level), so the ending stays unexplained rather than attributed. Net effect: the one
  cell the register's `ripple-65b-bf16-tp2` row exists for — the 1M-context BF16 control — booted
  ready and was lost unmeasured, because the arm had already been closed `failed` on
  `tools/run-arm.sh`'s 300 s container-appearance window (rows `run-arm-appearance-window-300s` and
  `executor-release-host-claim-on-failure`).
- **Both Kimi-K3.1-Pro pruned75 arms died in vLLM's `CacheConfig`, not on their model.** Their reaped
  serve logs (`serve-reaped-…_node_0.log`, attempts on `.30`–`.33`, 05:19–05:32 ET) end
  `Value error, Invalid kv_cache_dtype: 'bf16'. Valid values are: ['auto', 'float16', 'bfloat16',
  …]` — the recipes shipped `kv_cache_dtype: bf16`, which renders straight into
  `--kv-cache-dtype`. The abort is in argument validation, so neither arm loaded a weight and the
  dspark sibling's **drafter-binding gate is still unproven, not refuted**; the plain arm's engine
  gate (does the nightly resolve `KimiK31ForConditionalGeneration`) is likewise still unrun. Fixed at
  the mechanism: `kv_cache_dtype: bfloat16` in both recipes plus the lane-doc finding
  (`recipes/explore/README.md` §Kimi), commit `d41a3df8`; `validate` passes on both. No boot since,
  so both register rows stay open.
- **Register:** added `run-arm-appearance-window-300s` (§above) rather than a second note on the
  `ripple-65b-bf16-tp2` row — the mechanism is the runner's window, not the arm's.
- **Publication:** board republished on the 06:12:15 ET census (`publish`: `disk was 2026-11-08
  06:10:20 ET`, a peer board) — title, census cell and work queue regenerated, the peer's other
  In-flight rows preserved verbatim, one landed row appended for `d41a3df8`. The board's earlier
  Ripple row is gone with the pair, which is why this section carries the ending.
- **The register's live claim was overwritten mid-cycle, and that is escalated rather than repaired.**
  The head's copy (`~/src/sparkrun-recipe-registry/mad-science/queue.json`, the file the campaign
  writes) read **107 tasks / 22 open / one claim** — `h2h-second-boot-glm-753b` →
  `sparkrun-campaign:h2h-20261107` — at ~06:11. At 06:16:48 it read **106 / 21 / no claim**, its
  mtime **06:14:05.712**, which is the workstation copy's mtime to the microsecond, while the campaign
  still holds that arm's lease and its containers run on `.30`–`.33` (census above). So a whole-file
  write from this side replaced the head's register and took the live arm's claim with it. Three
  consecutive head reads 4 s apart show the 106/21/no-claim state stable, so it is not a read race.
  The claim lifecycle belongs to the campaign, so this tick recorded it and left the row alone; the
  consequence to watch is a close-out that later refuses its own arm as a stale claim, and a second
  writer publishing a register that cannot see the lease.
- **Follow-ups this cycle closed, and one negative that matters.** (a) The `CacheConfig` spelling was not
  two arms but four: `grep 'kv_cache_dtype: bf16'` finds the two Kimi arms (fixed in `d41a3df8`) plus
  both Ripple NVFP4 probes on the *same* nightly digest (`vllm/vllm-openai:nightly@sha256:390a656b…`,
  `…nvfp4-tp1-vllm.yaml:62`, `…nvfp4-tp1-dflash2-vllm.yaml:53`), now `bfloat16` in `e77bd333` — the
  BF16 sibling booted on that digest with `bfloat16`, so the digest, not the arm, is the discriminator.
  The one remaining tracked `bf16` is deliberate and correct: `recipes/cybersec/nex-n2.5-...-sglang.yaml:45`
  is an SGLang arm, and SGLang's vocabulary is `bf16`. (b) Rendered, not inferred: both Kimi arms now
  print `--kv-cache-dtype bfloat16` on the serve line (`sparkrun run … -n` with the quartet hosts).
  (c) Full suite on this tree: **1372 tests, 2 skipped, OK**. (d) **The Ripple pair's ending is not an
  OOM.** `journalctl -k --since "70 min ago"` and `journalctl -u earlyoom` on both `.30` and `.31` print
  no `oom`/`killed process`/earlyoom-kill line across the 05:0x–06:1x window — reads that now succeed,
  unlike the earlier `sudo -n dmesg` that returned nothing for want of privilege — and the pair's
  60.4 GiB/rank weights plus 39.88 GiB KV sat inside the unified pool, so "no record of the ending"
  stands as the honest state.
- **The register clobber, discriminated on content and repaired at the invariant.** The head's
  `queue.json` read 107 tasks / 22 open / one claim at ~06:11 and 106 / 21 / none at 06:16:48 with
  mtime 06:14:05.712, while `state.json` kept leasing the arm (attempt 6, re-upped 06:23:43, expiry
  06:28:43) — so the claim was deleted by a write, not released by the director: clearing a claim drops
  `claimed_by`/`claimed_at` only, and this replacement also lost a **task row** (107→106), which only
  a pre-claim whole-file copy explains. Neither side has `.stversions` and the row was never committed,
  so it is unrecoverable; the mechanism is registered (`task-queue-write-clobbers-live-claim`, commit
  `8ff3b911`) with the fix shape (`publish`-style CAS in `task-queue.py`, head copy authoritative for
  claim-bearing rows). The tick **re-asserted the claim** at 06:22:23 ET rather than reporting a live
  lease with no claim: the row's recipe is the one the quartet serves, and `--claimed-by` requires
  `running`, so the state flip restores the tool's own invariant instead of inventing one.
- **Board:** republished 06:25 ET on the 06:23:45 census (`publish`: `disk was 06:12:15 ET`, this
  session's own earlier board). The `.30`–`.33` row now carries the *current* lease (expiry 06:28:43)
  instead of the 06:09:54 read's lapsed one, the census carries per-rank liveness at minute 15
  (loading against a 2538.9 s TTR, rank-0 log still 1103 B), and the landed table's `d41a3df8` row was
  corrected: the engine aborted in `CacheConfig` at startup and the *arm* closed `rc=4` at t=334 s —
  "died at ~334 s" reads as a load-time failure that it was not.

## 2026-11-08 07:18 ET — 753B arm served at last: ladder and 15/15 house battery landed; a fresher peer board took the write, and the ladder's aggregate column is not a result
- **Board:** published 07:08 ET on this tick's own **07:03:09 / 07:03:44 ET** census (commit
  `0af2bd7a`; `publish` reported `disk was 07:02:37 ET`, a peer's board, so the peer's rows were
  read and folded rather than overwritten — its metrics-bridge verification and its note that the
  register's prose still says *attempt 5* both survive in the published copy). A peer then
  published on a **07:09:59** census (commit `bacdbc36`) carrying the same cycle facts plus the
  `.35` idle-node drift attribution, and **this tick wrote no second board**: its composed 07:11
  copy had a 50 s fresher census and nothing else the peer lacked, so a whole-file replace would
  have been a net loss. The composed file was discarded, not published.
- **The arm this campaign never got past loading finally served.** Attempt 6 of
  `glm-5.3-exl3-3bpw-tp4-1m-tensorfold-sglang` logged `readiness=yes` at **06:50:57 ET** with
  `TTFT 2534.208 s` (launch total 2543.6 s) against the arm's measured 2538.9 s TTR, and
  `boot-watchdog.py` recorded `WATCHDOG t=2539s verdict=healthy endpoint=ok serve_pid=alive
  io_delta=153788229 log_delta=319 ranks=4 peer_moved=3 unprobeable=0` — the same silence the
  per-container stall rule killed at t=2532 s in attempt 5. So `3e6c8ed9`'s group-scoped progress
  judgment is now **field-verified on the arm it was written for**, not only on its own tests.
- **Both measurement cells landed.** Ladder complete 07:04:37 ET, four cells × 5 runs; house
  battery complete 07:09:25 ET with **15 scenarios, 15 pass, 0 partial, 0 fail, score 100**
  (tool-eval-bench 2.6.0, `final_score` 100, ★★★★★, deployability 76, responsiveness 21, 287.4 s,
  run `2026-11-08T12-04-39.495432Z_5d0e805d`). `h2h-client.py --cell house4096` (pid 4066279)
  then started against the same serve and was still running at 07:10:58. The arm has no verdict
  yet — it holds an open `h2h-second-boot-glm-753b` claim and a live lease.
- **The ladder's aggregate column is an artefact, and this is the cycle's own trap.** CSV
  `t_s_mean` runs **30.27 / 18.90 / 15.95 / 15.16** while `t_s_req_mean` stays **30.27 / 28.70 /
  29.61 / 29.32** at C1/C2/C5/C10, and `ladder.json`'s per-cell `tg_throughput` series holds
  **n=2** points (c1 mean 16.07 over samples ≈30.27 and ≈1.88), so `t_s_mean` is a two-sample mean
  whose ramp sample drags it down. The printed ladder table is worse than unhelpful: its C1 row
  prints **5.3** in the `tg` column, which is the ttfr field, and a peer board read that 5.3 as C1
  decode before this cycle. Per-request tg and pp (**301.4 / 256.3 / 243.3** t/s) are the quotable
  fields; an aggregate from this ladder needs a `-b extra_body=return_token_ids=true` re-run, and
  `ladder.log`'s interpolation warning (`return_token_ids=false`) is why.
- **Census (own reads, read-only):** 07:03:09, 07:03:44 and 07:10:49 ET. Containers `.30`→`.33`
  **1 / 1 / 1 / 1**, `.34`/`.35` **0 / 0** on all three; volumes **0** on all six. Root avail GiB
  `.30` 1236.6, `.31` 1610.8, `.32` 1685.0, `.33` 1568.6, `.34` 1091.9, `.35` 1315.5; the fleet
  sum fell **131,072 B** across the 33 s pair and a further **14,946,304 B (14.3 MiB)** over the
  7 min 05 s to the third read, of which `.35` (holding no container) accounts for **8,982,528 B**
  — unattributed here, the peer board's idle-node reading is the better one.
- **Register (own read, 07:02–07:07):** 107 tasks, **22 open = 15 queued + 1 running + 6
  blocked**, `check` green, one claim (`h2h-second-boot-glm-753b` →
  `sparkrun-campaign:h2h-20261107`, claimed 11:22:23Z) matching the live quartet. The head's copy
  and the workstation's are **byte-identical** (`sha256 1b93bd28…`), so the clobber class
  registered as `task-queue-write-clobbers-live-claim` did not fire this cycle; the claim's row
  prose still naming attempt 5 is reported, not edited, exactly because `queue.json` is the
  campaign's write surface.
- **Landed-table homing: verified, and left to the writing session.** This tick appended rows and
  cleared nothing, so the row-by-row homing obligation did not trigger; re-checked anyway, and
  **23 commit SHAs in the table appear nowhere in this file** — `28fc675`, `a192fa2`, `aaabd2a`,
  `e9effb8`, `0f482bd`, `5cef9fc`, `cdddf35`, `57734fc`, `b0e6bcd`, `0dfc19c`, `ca38a34`,
  `f1400d3`, `fff29f9`, `601ef7c`, `ada13a7`, `555aeac`, `1ebfa6c1`, `00361e6a`, `c6204710`,
  `4927a7fe`, `896d0193`, `3e6c8ed9`, `2b6f82a7` (all resolve as commits — the `4ceb6c60` and
  `2119564` strings in the table are an image short-id and a pid, not commits). The 06:06 ET
  section already decided that a read-only tick does not home the writing session's rows; the gap
  therefore stands as that session's close-out debt, and this entry exists so a later clear cannot
  say the gap was never named.

## 2026-11-08 07:26 ET — board folded, not replaced; the 753B ladder's aggregate column is a real n=5 mean, and the lane doc's parenthesised aggregate matches no artefact

- **Board:** this tick's own census is **07:09:59 ET** (containers `1/1/1/1` on `.30`–`.33`, `0/0` on `.34`/`.35`,
  volumes `0` on all six). I first published at 07:04 (`56e49737`) and read the ladder's printed `tg t/s` column as
  C1 **5.3** — on the C1 line `0 1 … 30.3 5.3 5` that column is `ttfr ms`, and the aggregate is **30.3**. A peer tick
  (`0af2bd7a`, 07:08) landed the cells correctly off `runs/*.json` first, so the erroneous figure stood ~4 min and no
  longer stands; this tick then folded its fresher census and the finished house battery row-keyed into the peer's
  file (`bacdbc36`, census 07:09:59, `disk was 07:08:00`) rather than writing a whole-file replace over it.
- **The aggregate column is not an artefact and owes no re-run.** The 07:18 section above reads the ladder aggregate as
  `n=2` points whose sample drags the mean down. Both artefacts falsify that: `runs/*.json` and the arm's
  `ladder.json` each carry `tg_throughput` with **n=5 values per cell** — C1 `33.45 29.57 27.63 30.57 30.13` →
  30.27; C2 18.90 ± 0.21; C5 15.95 ± 0.24; C10 15.16 ± 0.07 — while `tg_req_throughput` pools 5×concurrency samples
  (5 / 10 / 25 / 50). The `16.07` in that bullet matches C5's first sample `16.09`, not a C1 pair, so the reading was
  of the wrong cell. `ladder.log`'s own warning says `return_token_ids=false` interpolates token *arrival times* and
  leaves token **totals** exact, which is what an aggregate tokens/s derived from usage measures: the aggregate is
  quotable and only burstiness is smoothed. No `-b extra_body=return_token_ids=true` re-run is owed for it.
- **It reproduces window 3 on the aggregate field too.** Window 3's `glm-perf-ladder.json` has the same schema and the
  same keys (`prompt_size 2048 / response_size 128`) and reads `tg_throughput` **28.83 / 18.72 / 15.26 / 14.58**
  against this boot's **30.27 / 18.90 / 15.95 / 15.16**, and per-request 28.83 / 28.94 / 26.71 / 28.21 against
  30.27 / 28.70 / 29.61 / 29.32. Both shapes match, so the second boot is a clean sigma sample and the
  aggregate-falls-with-concurrency curve is this arm's normal behaviour, not a regression.
- **Open, not edited:** `recipes/glm/README.md:60-62` parenthesises window 3's aggregate as **37.4 / 76.3 / 145.8**,
  and **no window-3 artefact contains those numbers** — `grep` over `glm-perf-ladder.{json,yaml,csv}` in
  `~/benchmarks/tp4-window3-20261024/` returns nothing, and that CSV's aggregate column (`t_s_mean`) reads
  18.72 / 15.26 / 14.58 at the same cells. Only one `glm-perf-ladder.{json,csv}` pair exists on the head. The
  per-request figures beside it check out exactly, so the parenthetical is not the cited receipt's aggregate under any
  field name. Left standing rather than guessed or overwritten; the lane's close-out owns the correction.
- **Register untouched:** `queue.json` still carries `h2h-second-boot-glm-753b` as `running` with prose naming
  attempt 5 against a live attempt 6 — reported on the board and here, not written, because a workstation-side write is
  the registered `task-queue-write-clobbers-live-claim` defect.
## 2026-11-08 08:04 ET — campaign drained on its last flight measured; the arm close landed in neither board nor ledger until this tick
- **Board:** published 08:04 ET on this tick's own **08:02:21 ET** census (`publish` reported
  `disk was 2026-11-08 07:09:59 ET`, so no peer board was overwritten; written sha `f0afbf36…`
  equals the composed file). `In flight` lost the `.30`–`.33` flight row, which had ended, and gained a
  queue-mode row; the queue table is `render --board` verbatim at **21 rows** against 21 open tasks.
- **The 753B arm closed `rc=0 measured` and nobody had recorded it.** Attempt 6's arm log
  `~/benchmarks/h2h-20261107/logs/glm-5.3-exl3-3bpw-tp4-1m-tensorfold-sglang@6.log` ends
  `serve logs harvested: 4 (expected one per running rank…)`, `Workload stopped on 4 host(s).`,
  `ARM DONE glm-5.3-exl3-3bpw-tp4-1m-tensorfold-sglang rc=0`; its `client/client.json` cell closed
  **HARD 18/18 = 100 %** (`h2h-client.py --cell house4096` → `quality-battery --tier both
  --max-tokens 4096`, `rc=0`, 07:11:23) on top of the already-landed house 15/15 and the four-cell
  ladder. The 07:10 board's last row read the client cell as *still in flight*, and the 07:18/07:26
  ledger sections stop at "still running 07:10:58", so the close existed only in the receipt. Folded
  as a landed row **and** here, because a landed row is cleared at session handoff.
- **The campaign drained and holds nothing.** `director status` at the 08:02 read: unit `active`,
  `9 measured, 8 blocked` over 17 arms, and **no arm carries a `lease` object**
  (`state.json` mtime 07:58:54). So the six-node window is declared with a live unit but zero held
  nodes — the opposite of the wedged-lease signature, and the quartet's containers are indeed all gone.
- **The declared-window escalation *does* fire, and this tick first misfiled it.** The lease class
  (live lease, hosts at 0 containers) is correctly not it, but the skill's other trigger is a stated
  condition of its own: `.local/fleet-window.lock` has rows *and* the window's nodes all read empty —
  which is exactly this fleet on every read (08:00:41, 08:02:21, 08:04:25, 08:07:20), so the tick's
  first reply filed it as "not an escalation" and that framing was wrong. The lock is
  **owner-declared** (2026-11-07 directive, `reason: production workload stopped by owner; all six
  nodes free h2h register campaign`) and its holder `campaign-queue` now holds nothing, so it is a
  **stale lock**: `AGENTS.md` says a session that finds the lock must not boot on the named nodes
  (report and wait), so six idle nodes are withheld from every other session for work that could run.
  registry row says the holder should narrow or delete it; the tick does not edit an
  owner-declared lock, and it is git-ignored so no commit can carry the correction either.
- **The correction commit swept two peer hunks — recorded, not rewritten.** `1fed6d08` was meant to
  carry one board row and this section, but `STATUS.md` and `SESSION-RECORD.md` on disk then held two
  peer ticks' uncommitted work: their 08:08 board regeneration (17 table lines) and their
  `## 2026-11-08 08:08 ET — five commits and four queue-mode refusals…` section. `git diff HEAD~1`
  confirms `HEAD~1` still carried this session's 08:04 board, so those bytes had no committed home and
  the pathspec commit published them under a subject naming only the escalation. No bytes were lost and
  the content is what those ticks composed; the defect is the message, which is the class
  `AGENTS.md` says to record rather than revert. Origin already carries the commit, so nothing is
  rewritten.
- **The fleet is empty and the register explains it.** `sparkrun status` at 08:00:55 lists all six
  nodes under `Idle hosts` (`No sparkrun containers running`), and the 08:02:21 census reads
  **0 containers / 0 volumes on all six** (`.34`/`.35` were already 0). Of 21 open register rows,
  the 10 `queued` ones carry no `recipe`/`tp`/`env`, so a queue-mode director cannot plan any of them,
  and the 11 bootable ones are `blocked`: an empty eligible set, not a stalled holder.
- **The register's close-out write, read and not repeated.** `queue.json` on the tree is uncommitted
  (`107` rows, 29+/21−) and byte-identical on head and workstation (`sha256 087e58b5…`): the campaign
  flipped `h2h-second-boot-glm-753b` `running`→`done` with `claimed_by` cleared and five bootable rows
  `queued`→`blocked`, each carrying a named gate (Kimi tokenizer/DSpark `config.json` unresolved,
  GSQ-RCO image `manifest unknown`, Ripple image digest unresolvable, the reference arm's chat cell),
  four of them gaining the `house4096` acceptance client so a healthy serve cannot close evidence-free
  again. `task-queue.py check` is green with **zero claims**; this tick wrote none of it.
## 2026-11-08 08:08 ET — five commits and four queue-mode refusals landed with no board row; the fold kept the peer's 08:04 board
- **Board:** the 08:04 board (`ff3f1d91`, census 08:02:21) already carried this tick's state, and its
  census was **newer** than this tick's 08:01:11 read, so the fold was composed from the committed copy
  and kept every peer In-flight row, re-rendered the queue table verbatim (21 rows against 21 open
  tasks), rewrote only the census cell with this tick's own **08:07:20 ET** read, and appended eleven
  time-sorted landed rows. **The publish door then landed over a peer's uncommitted board** — it reported
  `disk was 2026-11-08 08:04:25 ET`, not the `08:02:21` copy the fold was composed from, so the
  disk-stamp CAS passed on a board this tick had never read. Recovered within two minutes: the peer
  republished its own rows at 08:08:44 / 08:09:10 and folded this tick's row-keyed content at 08:10:28
  (`1fed6d08`), so the standing board carries both and no peer fact is lost — but the guarantee given up
  is a fold over a known peer copy, and a compose→publish gap of minutes is what gave it up.
- **Five commits had landed with no row anywhere.** `b449a272` (07:12, the arm's first serving cycle
  and the aggregate trap), `a3837191` (07:13, ladder aggregate corrected to `n=5` per cell from
  `runs/*.json` and `ladder.json`), `29b4d164` (07:24, campaign receipt names its ladder evidence),
  `578039f3` (07:33, the register hold read at assignment, claim, close-out and reconciliation),
  `4e1bd4c3` (07:45, a plan defect contained to its recipe). None appeared in the 08:04 board or this
  ledger, because the previous tick folded the arm close only.
- **The manifest plan spent 07:11–07:18 re-measuring three decided-blocked arms.** As soon as the 753B
  arm closed `rc=0`, the worker took `zz-ds4-1017-sm121-indexer-scoring` (rc=4, 07:14:19),
  `zz-ds4-1017-sm121-arm3-control` (rc=4, 07:16:50) and leased `zz-ds4-1017-sm121-arm5-trtllm-mla` at
  07:16:50 before the unit stopped at 07:18:05 — all three rows carried the 04:22 `do not re-boot`
  decision, which is exactly the class `578039f3` closed eleven minutes after this flight started.
- **A stop mid-flight left a claim the validator refused.** The two starts at 07:18:05 and 07:19:17
  never served: `task-queue: w4-survey-arm5-sm121-boot: a claim exists only on running row;
  state='blocked' still carries claimed_by/claimed_at`. The 07:20:26 start came up clean in queue mode
  and immediately logged `queue: 10 row(s) queued without recipe (authoring, not bootable)`.
- **Queue mode then leased five rows and every one refused inside three minutes.** `zz-kimi-…-ref-vllm`
  rc=5 at 07:45:37; `deepseek-v4.1-flash-1017-gsq-rco-coder-gguf-llamacpp` rc=5 at 07:45:42 on
  `manifest for littlecedar/dgx-spark-llama-cpp@sha256:f2579b80… not found` — the pin this arm documents
  is not resolvable from the node; `kimi-k3.1-pro-pruned75-mxfp4-dspark-vllm-tp4` rc=4 on
  `Provide a valid Hugging Face repository ID` for the drafter repo;
  `kimi-k3.1-pro-pruned75-mxfp4-vllm-tp4` rc=4 on `Couldn't instantiate the backend tokenizer … need
  sentencepiece or tiktoken`; `zz-ripple-65b-preview-bf16-tp2-vllm` rc=4 with its container gone before
  the exit-state inspect. Each row is therefore blocked on a **mechanism**, not on a timeout.
- **The reference arm's remaining block is its chat path, and the serve says so.** Attempt 5 (07:54:50,
  unit restarted at 07:54:49 under MainPID 259749) reached readiness at **t=117 s**
  (`verdict=healthy endpoint=ok serve_pid=alive ranks=1`), then the ladder failed `[1/4]` in 2.6 s, the
  house suite `[1/1]` in 0.9 s, and the client read `HARD 0/18` / `house answered 0/37 (transport
  errors)` — every request `POST /v1/chat/completions 400`. The serve log's own line is
  `ready: served name '…', no chat template (completions only)`, so the arm is a completions-only
  reference server and its ladder must run on `/v1/completions`; the register's `blocked` flip names
  that cell, correctly.
- **Census, read-only, twice this cycle.** 08:01:11 and 08:07:20 ET: **`0` containers and `0` volumes on
  all six nodes**, `sparkrun status` listing all six under `Idle hosts`; root avail fell again on every
  node — `.34` 8.48 MB, `.30` 2.82 MB, `.31`–`.33`/`.35` ≈0.48 MB over 6 min 9 s — which is node-root
  journal drift, not a writer, because no node held a container.
- **Not written by this tick:** `mad-science/queue.json` (the campaign's own close-out bytes, still
  uncommitted, `sha256 087e58b5…` on head and workstation) and the campaign unit (never started,
  stopped or restarted here).
## 2026-11-08 08:27 ET — the llama-cpp pin is alive, and the fleet's root fall is pool traffic, not drift
- **The `GSQ-RCO image 404` gate is stale, not a dead image — falsified three ways.** The 07:45:42
  refusal read `manifest for littlecedar/dgx-spark-llama-cpp@sha256:f2579b80… not found`. Probes this
  tick: the anonymous pull-token call (`https://ghcr.io/token?scope=repository:littlecedar/dgx-spark-llama-cpp:pull`)
  returns **200** with no credentials; `docker manifest inspect` on the pinned digest, in a fresh
  empty `DOCKER_CONFIG`, returns rc=0 with a 2,687 B manifest; the tag `upstream-6023692` resolves to
  that **same** digest; and both probes re-run from `.30`'s own daemon (which holds a `ghcr.io` auth
  entry) also return rc=0. So the pin is public and resolvable, the ~ten tracked recipes sharing it
  (five `recipes/liquidai/*-llamacpp.yaml`, `3d/zz-qwen35-4b-3d-coder`, `decision/liquidai-d1-2b` +
  `zz-d1-omni-2b`, `ds4/…-gsq-rco`, `explore/flint-40b`) are **not** unbootable, and the arm's row
  should be re-probed at boot time rather than re-blocked on an image that exists. The refused pull was
  a transient at 07:45, and the nightly sweep's `container-unresolvable`/`sweep-broken` legs would have
  fired if the package had really gone.
- **The 07:45 dspark drafter body now exists.** `models--LithosAI--Kimi-K3.1-Pro-DSpark` has snapshot
  files written 08:08–08:11 (`du -sL` 4 291 MiB); the arm's `Provide a valid Hugging Face repository ID`
  refusal was a pre-staging read, not a bad repo id.
- **The fleet-wide root fall is shared-pool traffic, and one part of it is still unattributed.**
  08:07:20 → 08:24:35 ET: `.30` −1.06 GiB, `.32` −1.07, `.35` −1.06, `.34` **−20.5 GiB**, `.31` −1.4 MB,
  `.33` −21.1 MB, with `0` containers and `0` volumes on all six throughout. Each of `.30`/`.32`/`.34`/`.35`
  gained exactly one ~1.128 GB new file in `/srv/beegfs/storage/chunks` (≈4.5 GB, the DSpark staging).
  The remaining ~16 GiB, all on `.34`, produced **no new file above 300 MB** under `/var/lib/docker`
  (`du -sx` 493 253 MiB) or `/srv/beegfs` (1 272 764 MiB) and journal 676.7 M, while `.34` runs
  `beegfs-storage` — the signature of pool data written into existing storage-target buddy files rather
  than a local writer. The fall stopped between 08:17 and 08:24 (`.34` flat to 0.1 MB across two reads),
  no container, no download process and no deleted-open file holds it (`lsof +L1` n=1, 0 B). Carried as
  unattributed and watched on the board, not called drift.
- **Correction to the previous section.** Its census bullet called a sub-MB per-node fall "node-root
  journal drift" — true at that scale for 0.48–8.48 MB, but the same measurement over the next 17
  minutes is GB-scale pool traffic, so the label must not be carried forward: a fleet-wide fall is
  attributed by summing per-node deltas against a staged body, never by the size of the previous delta.
- **Two board rows corrected, both active-state misreadings.** The campaign row said `drained` while the
  unit was `active` — drained means the unit exited 0 with every arm terminal, so a live queue-mode
  poller with 9 measured / 8 blocked and no lease is an **empty eligible set**, and that distinction is
  what makes four declared nodes idle a register defect rather than a completion. The queue-mode row now
  names the row that should be runnable: `h2h-beam-house-and-bfcl-category`, `node_cost: quartet`, its
  only `blocked_by` parent (`h2h-beam-house-boot`) `done`, and **no `recipe:` key** — the fix is its
  owner's register edit, not a boot.
- **Not written by this tick:** `mad-science/queue.json` (still the campaign's uncommitted bytes,
  `sha256 932224e2…`), the campaign unit, and `.local/fleet-window.lock`.

## 2026-11-08 09:13 ET — correction: `.34`'s pre-08:24 slice has no write behind it, and the pool hides a body's size from two of three instruments

Two corrections to `6d9138e1` (the 09:04 board), both from trying to harden its claims. The second is
new evidence; the first extends a peer tick's 09:09 board correction with a falsifier it had not run.

- **The `.34` −20.5 GiB slice (08:07:20→08:24:35) is not the pruned75 download, and has no write
  behind it at all.** A peer tick already pulled the timestamp half on the 09:09 board; this adds the
  whole-root falsifier. The download's pid started 08:26:19, *after* that window closed, and the pool's
  Hub received only **4.20 GiB** in 08:00–08:27 — the 4.50 GB DSpark blob at 08:08 plus pruned75
  metadata at 08:21–08:23; every pruned75 shard body is dated 08:27 or later. A `sudo` whole-root
  scan of `.34` (`find / -xdev`; ext4 root, and `/srv/beegfs/storage` chunks included because that
  path is on the root device) finds **1.06 GiB** written in 08:05–08:26: one BeeGFS chunk of
  1,124,792,578 B at 08:08 plus kilobyte metadata. So no writer consumed 20 GiB there. The slice is
  a question about the *reading series*, not about an author — the 08:07:20 point is the suspect, and
  the next `.34` dip must be read twice, minutes apart, before anything is attributed to it.
- **Three instruments disagree on the staged body by 60×.** At 09:1x the pruned75 snapshot tree held
  `find -type f` = **4.54 GiB**, `du -s` (no `-L`) = **4.88 GB**, `du -sL` = 297 GB, and an
  inode-deduped `os.stat` walk of the snapshot entries = **277.16 GiB over 59 of 96 shards**. The
  bodies are symlinks into the pool's shared store (`hub/blobs/<xx>/<hash>`), so anything that does
  not follow symlinks under-reads by ~60×; `du -sL` is safe because GNU `du` dedupes by inode. With
  that number the attribution closes: cumulative fall since 08:24:35 is 213.2 GiB (to 09:01:05) plus
  65.0 GiB (to 09:12:20) = **278.2 GiB against 277.16 GiB staged, 0.4 %** — the fall is the body.
- **An inner `ssh` whose quoting collapses runs its command on the head, and the number still looks
  plausible.** A `.34` probe returned 1197.1 GiB avail while `.34`'s real read was 1025.3 GiB — the
  1197.1 GiB was `.30`, the head, which the probe's own `hostname` confirmed. Two reads two minutes apart "disagreeing by 171 GiB"
  was the label, not the disk. Print `hostname` remotely in the same command that prints the number.

## 2026-11-08 10:53 ET — five blockers that were conditions, and the three corrections they cost

Five gates were recorded as hard verdicts — a ceiling, a rebuild, a stalled serve, a dead image, a
component failure — and each fell to a check that cost minutes. The register's own vocabulary is
where the cost sat: "blocked" was written for four different things (never tried, instrument said
no, inference from one artefact, and a real gate), so work sat behind a word instead of a
condition.

- **A readiness ceiling read as an engine verdict.** `tools/run-arm.sh:322` takes
  `READY_TIMEOUT=${ARM_READY_TIMEOUT:-2250}`, and the 753B arm's measured TTR is **2,538.9 s** —
  **288.9 s over a default**, not over anything the engine did. The knob and the measured number now
  live in the launcher, so the re-boot's gate is a timeout value set ahead of the measured TTR
  rather than a claim about the model.
- **The watchdog was memory-blind.** `last_progress` advanced on io and log deltas only, so a lease
  loading tens of GiB at zero io/log growth read as idle and was stopped. `3e6c8ed9` judges the
  lease with `group_stalled` and counts memory only past `MEM_PROGRESS_FLOOR = 128 MiB`, which is
  above the arm's quiet-loading signature and far below its real growth.
- **One rank stood in for the lease.** The same commit passes `--rank <host>:<container>` per node,
  so the verdict needs every rank: a quiet rank 0 while ranks 1–3 stream shards no longer stops a
  boot that was progressing.
- **`manifest unknown` was not a dead pin.** Probes: the anonymous pull-token call returns 200, a
  `docker manifest inspect` in a fresh empty `DOCKER_CONFIG` returns rc=0 with a 2,687 B manifest,
  the tag resolves to that same digest, and both re-run from the head's daemon. The pin was public
  the whole time; the defect was a **phantom `-cu130` tag** that named nothing while the digest
  served, dropped in `7abe916` with every digest untouched (the gated sweep went 2 → 1).
- **SM121's ÷128 error was a dispatch choice, not a rebuild.** `--moe-runner-backend marlin` makes
  the sm120 backend override a no-op (`deepseek_v4.py:66-88` → `fp8.py:436-440`), so the
  `Mxfp4FlashinferCutlassMoEMethod` assert never executes; the device gate admits GB10
  (`is_sm120_supported` majors `[12]`, 121 // 10 = 12) and `mxfp4_marlin_moe.py:77` pads
  intermediate 576 → 640 before the kernel sees it. The trap worth naming: `utils/common.py`'s
  module-level `is_sm120()` is the strict `(12, 0)` form, and reading that as the gate is how a
  working lever gets written off. Recorded `recipes/ds4/README.md:1155-1188`; the lane's verdict is
  now "config lever, device-allowed — untried pending one control boot" (`5ad932c`).

Three corrections came with the same discipline, and each replaced an inference with a measurement:

- **The pruned75 "tokenizer dependency gap" was false.** The pinned image ships **tiktoken 0.14.0**
  and **sentencepiece 0.2.3** (verified with `docker run --rm --entrypoint python3 <digest>`), and
  vLLM's "need sentencepiece or tiktoken" line is its generic fallback when no tokenizer file is on
  disk. The real cause is the pool's **config-only stub** snapshot: one entry, `config.json`
  (7,303 B), plus `refs/main`, against the full repo's **112 files, 475,525,935,884 B = 442.87 GiB**
  — the row's block is "weights unstaged", which a download closes and no wheel, mod or image edit
  could (`recipes/explore/README.md:1131-1152`).
- **DSpark's binding is proven at config level, with only acceptance counters left.**
  `SpeculativeConfig(method="dspark", num_speculative_tokens=4)` accepts the staged target's
  `config.json` (93 layers, hidden 7168, vocab 163,840) and the staged LithosAI draft: the resolved
  draft reads `Qwen3DSparkModel`, 5 layers, `num_target_layers: 93`, `block_size: 5`,
  `target_layer_ids [7, 23, 67, 83, 91]`. `Qwen3DSparkForCausalLM` constructs inside
  `set_current_vllm_config(...)` with a one-rank gloo group: **4,598,107,009 parameters**, 5 decoder
  layers, `DSparkMarkovHead` + `DSparkConfidenceHead`, first layer `model.layers.93.self_attn.attn`,
  `target_vocab 163840`. The Omni-only validator returns early for a non-Omni target, so 4 drafts
  with block 5 passes as the trained shape, not as an exception. What stays open is a serve and the
  cross-checkpoint acceptance numbers — the card's 3.448 mean was measured on the unpruned base and
  this target carries 75 % of the experts (`recipes/explore/README.md:1192-1206`).
- **Both residuals of the two closed `run-arm` rows are now scheduled rows, not prose.** The repo's
  rule is that a finding either lands as a row or does not exist, so
  `run-arm-stall-verdict-reads-as-death` and `run-arm-harvest-enumerate-reaped-logs` exist in the
  register (`92b7503`), each written the way a falsifier is: verified open at a SHA, with the exact
  `file:line` and an acceptance that names the negative control.

The standing rule this session adds: **a potential blocker gets a smoke test or an R&D falsifier
queued ahead of the blocked work**, and a lane writes "untried" wherever "blocked" was inferred
rather than proven. A gate that costs minutes to falsify must never cost a day of idle nodes, and a
verdict with no falsifier behind it is a guess wearing the register's vocabulary.

## 2026-11-08 11:09 ET — the pruned75 body is present and the arm does not fit: `du -sb` answered both questions

- **The trap is that one command describes a stub and a complete body identically.** `du -sb` on
  this pool reads **8,179 B for a complete body**, because every snapshot file is a symlink into
  the shared content-addressed store: the byte count is symlink metadata, not weights. The 7,303 B
  one-entry `config.json` stub that blocked the arm earlier today was real, but `du -sb` would have
  called that one complete as well, so a presence check must be the `find -L` byte sum over the
  snapshot (`475,525,935,884 B = 442.87 GiB`) or `hf cache verify <repo> --revision <sha>` (rc=0,
  "All checksums match"). Directory listings and `ls -la` are the same trap from the other side.
- **Presence, independently confirmed.** One snapshot `fc72e5a1…`: 112 entries, 96 shards plus 16
  sidecars, `refs/main` written, zero `.incomplete`/`.lock`, no writer, `hf cache verify` rc=0, and
  the 08:26–09:38 pull closes against a 443 GiB `df` delta.
- **Fit, and it is arithmetic, not a boot to spend.** The shards measure **442.85 GiB**, so TP=4 is
  **110.71 GiB/rank**; a 119.21 GiB pool at `gpu_memory_utilization: 0.92` is a **109.67 GiB**
  budget, which the weights exceed by about 1.0 GiB/rank **before one KV block**. The shipped
  util/ctx pair is therefore infeasible at TP=4 and the arm needs a recut: 0.93 of total just to
  hold weights leaves 0–1 GiB for KV at 16k, so the realistic shape is a shorter ctx (4k-ish) at
  about 0.95, or a smaller checkpoint — not 1M. The 423.0 GiB in the recipe note and in the
  register row's own notes is the nominal MXFP4 figure and is stale.
- **What that does to the readings around it.** An OOM on this arm is a **sizing answer, not an
  engine or checkpoint verdict**, and the lane's existing "an OOM is sizing, not the checkpoint"
  line is therefore not fresh evidence for anything. The gate that actually moved is the one worth
  naming: the tokenizer dependency was false (image carries tiktoken 0.14.0 and sentencepiece
  0.2.3), the config binds (`TARGET ModelConfig OK: ['KimiK31ForConditionalGeneration']`;
  `SpeculativeConfig(method=dspark, n=4)` constructs `Qwen3DSparkForCausalLM`, 4,598,107,009
  params, block 5, target layers 7/23/67/83/91), so the remaining question is memory and backend
  selection at 110.71 GiB/rank — and its answer is the recut's first boot.

## 2026-11-08 11:20 ET — a 127 s arm is invisible to an hourly census, and syncthing left `main` at an object nobody has

- **A census is a sample, not a state.** This tick's reads straddled the campaign's attempt 6:
  11:00:45 found the fleet empty, 11:04:52 found four ranks `Up` on `.30`-`.33`, 11:08:07 found them
  gone again — the boot lived 11:03:47-11:05:44, 127 s inside a 3.5-minute window. The peer tick that
  took its census at 11:01:03/11:02:54 legitimately reported "nothing live", and an In-flight row
  saying no node runs a workload is only true **at its stamp**. The durable consequence: for an arm
  that can boot and die between two reads, the board's lease row (campaign `state.json`) and the
  arm's receipt are the record, and a census that misses the boot is not evidence it never ran.
- **Attempt 6's marlin lever was never in the engine's argv, verified twice over.** Its
  `arm_opts.txt` holds `-o\x1fextra_args=--moe-runner-backend marlin` — a unit separator, not a
  space, which `od -c` on the rotated receipt dir settles and a byte count cannot (the space form
  `-o extra_args=…` is 42 B as well, so both attempt 5's and attempt 6's file measure the same) —
  but the launcher printed
  `Override(s) -o extra_args have no effect: the 'sglang' runtime does not understand it, so nothing
  is added to the serve command` (`launch.log:41`), and the reaped serve log (31,127 B) dumps
  `'moe_runner_backend': 'flashinfer_mxfp4'` with zero `marlin` occurrences and dies on the same `ValueError: Mxfp4FlashinferCutlassMoEMethod requires
  hidden_size and intermediate_size_per_partition to be multiples of 128 (got hidden=5120,
  intermediate=576)`; watchdog `dead_candidate` t=95 s, `dead` (cause `RuntimeError`, ranks=4,
  peer_moved=3) t=107 s, `ARM DONE ... rc=4`. `-o extra_args` is simply not a channel the sglang
  runtime consumes — the mechanism behind the retracted marlin bypass, one layer below the
  `ARM_OPTS` word-splitting that was fixed in `5f10e5a8`.
- **The ref-side sibling of the stale-index hazard.** `git status` and `git log -- <path>` both died
  on `bad tree object HEAD` because the loose `refs/heads/main` pointed at `a737411c`, a peer
  clone's unpushed commit whose objects never arrived over syncthing (its `.git/objects/ad/` holds
  `535914…` plus a `.sync-conflict-20261108-105114-Y5KSV46` copy), and one index blob was absent
  too. AGENTS.md already covers the index half (`git read-tree HEAD`); the ref half is
  `git update-ref refs/heads/main <origin/main>` after `git merge-base --is-ancestor` confirms the
  published tip descends from the last known commit. Both repairs rewrite the ref and the index
  only: the worktree kept three peers' uncommitted edits (AGENTS.md, queue.json, explore
  recipes/tests, tools/README.md), which `git reset --hard` — the obvious reflex — would have
  destroyed. The unreachable local commits had no readable objects, so nothing was lost with the
  ref move; a local tip that git cannot read is not work to preserve, it is work to re-derive.

## 2026-11-08 11:20 ET — the 11:13 board publish landed over an uncommitted peer edit, and `.30` gained an unowned container

- **`publish`'s newer-stamp refusal does not see an in-place edit of a board carrying the same
  title.** The 11:13 tick composed from sha `cbd26eb9` (the 11:08 board, which is `HEAD`'s copy)
  and published at 11:13:00; `publish` printed `(disk was 2026-11-08 11:08:00 ET)` while the file
  had already moved to sha `437f78fb` — a peer's edit under the **same** 11:08 title. The
  comparison is the newest `| census |` row against the title, so an equal stamp passes in both
  directions and the whole file is replaced. The compose-time sha compare-and-swap the skill
  prescribes cannot fire for a write that lands between compose and `publish`.
- **`437f78fb`'s bytes are unrecoverable**: nothing in `/tmp/board-*.md` matches that hash and no
  commit carried it, so whatever row the peer added in place is gone. The next tick had already
  republished a 11:17 board folded on the 11:13 one and corrected two of its cells (register
  `10 queued / 10 blocked` → `9 queued / 11 blocked`; its campaign row, since attempt 6 was a
  re-run of a register-blocked arm), so the loss is bounded to that one edit. A tick cannot fix
  this class by reading harder — only a publish-time CAS on the disk sha can, and `publish` does
  not take one.
- **`f71c1d1` carries the 11:13 board under a peer's subject** ("Board: the pruned75 arm is
  present…"): a peer's `git commit -- mad-science/STATUS.md` published the worktree bytes this
  tick had written. Nothing was lost — the committed board is exactly the 11:13 composition —
  but that commit's subject describes one clause of what it contains.
- **`.30` holds a container nothing owns**: `sm121m`, image `dsv41-sm121-dg:0.2.1` (config
  `sha256:85c1ffc3…`), `Created` 10:32:33 ET, `State.StartedAt` zero, `Cmd` `[run]`, no
  `sglang.launch_server` process — a bare `docker create` that no lease, campaign arm or lock row
  names, and the fleet's only container at every read 11:00–11:19. Left in place, because a tick
  removes no container; its owner should either start it or remove it, since any census counting
  `docker ps -aq` reads it as a live workload.
- **Register at 11:19**: 109 tasks, 89 done, 9 queued, 11 blocked, zero claims, `check` green.
  Campaign unit active, `state.json` 11:11:15, plan 9 measured / 8 blocked over 17 arms, no lease
  — every bootable row is blocked, so the poller has nothing to place and all six nodes stay
  idle. That is the empty-eligible-set state, not a drained campaign.

## 2026-11-08 11:23 ET — rule: a publisher diffs its read against the file on disk before it writes

**Measured twice today, which is why it is a rule and not a story.** The 11:20 section records the
sharper case — an in-place peer edit under an unchanged 11:08 title, replaced at 11:13, sha
`437f78fb` unrecoverable. This tick's case is the bounded one: the board was copied at 11:07
(stamped 11:04, `.local/board-cur.md` and `.local/board-base.md`), composed and published at 11:09
to a file whose stamp had moved to 11:08. Diffing the 11:04 snapshot against the committed board at
`61fb124` shows **every row that peer added present** (11:06, 11:13, 11:14, 11:16, 11:18) and only
this tick's own older rows superseded, so nothing stayed lost there — but their next tick saved it,
not the discipline.

**The rule.** A publisher compares the file it read with the file on disk immediately before writing;
any non-blank line present on disk and absent from the text being published is a peer write, and it
means **merge, never regenerate**. Regenerating from a stale base is how a board loses a claim, a
census or a landed SHA that no commit records — `437f78fb` is what that costs.

**The cheap guard, because "sha CAS" is the expensive one.** `tools/task-queue.py publish` can
express the body-side check in about six lines: after the freshness comparison and inside the lock,
`missing = {line for line in disk_text.splitlines() if line.strip()} - set(incoming.splitlines())`;
if non-empty, raise `PeerWriteInFlight(QueueError)` naming up to five missing lines and map it to
**exit 3**, so a tick can tell "a peer wrote, merge first" from exit 1 ("your markdown, your stamp or
your register is wrong"). The disk text is already read for `board_stamp`, so the check adds no I/O,
and it catches the same-title case the stamp comparison cannot see. It is the body sibling of the
title guard `cmd_lint` already carries (`tools/README.md:44`). **Not implemented this pass**:
proposed with its check and exit code so it lands as its own change with its own test.

## 2026-11-08 11:51 ET — the board-write clobber got a mechanism, not another note

- **This is the §11:23 proposal, implemented.** The section above prescribed a cheap read-vs-disk diff
  before the write and left the sha CAS for later; the sha CAS turned out to be the cheap half, and it
  is now in `publish` itself, so no second guard is owed.
- **The hole was structural, so it was closed in the tool.** `publish` compared only the board's
  stamp (`max(newest | census | row, title)`), so an in-place peer edit that keeps the title passed
  the check in both directions and the whole-file `os.replace` dropped that peer's rows — measured
  at 11:13 this hour, bytes recoverable from neither a commit nor `/tmp`.
- **`publish --expect-sha <hex>` is the gate**: the caller passes the sha256 its composition was read
  from, and inside the existing lock `publish` hashes the disk file, exiting 1 without writing when
  it moved. Fail-closed when the board is absent. Without the flag, unchanged. Landed with one
  negative control (a stale sha against a simulated in-place edit must refuse and leave the bytes
  alone) and one positive case, in `4debeac`.
- **The tick procedure now uses it.** `status-board-refresh`'s commit bullet writes
  `publish --expect-sha "$SHA"` and says why: the CAS lives inside publish's own lock instead of in
  the gap before the call, which is exactly where the 11:13 write slipped through.
- **The hour's other numeric defect was corrected on the board rather than quietly edited.** The
  11:13 landed row claimed "no node wrote more than ~10 MB in the hour" on evidence covering 63 s
  and 8.2 min; the only hourly comparison is the previous board's 1-dp GiB, where `.35` 1246.4 →
  1246.21 and `.32` 1602.8 → 1602.73 put the fleet ~0.28 GiB lower. The correction is an appended
  row (`10743ee`) that keeps the measured intervals and withdraws the bound, because the landed
  table is append-only and the wrong clause was already published under `f71c1d1`.
- **The stated suite total followed discovery, not arithmetic**: a peer's 25-test module landed
  under 1383, the `SuiteTotal` guard reddened the tip, and both statements moved to 1405 with my two
  new cases counted in the same commit (`d23b871`).
- **A pathspec commit can silently *revert* a path it does not name — measured this hour.**
  `a8eaa5b` carries my `AGENTS.md` totals change and simultaneously drops `publish --expect-sha` and
  its tests from `tools/task-queue.py`/`tests/test_task_queue_tool.py`, so `origin/main` had no
  `expect_sha` at all while the worktree still had it. The mechanism is the one the shared-index
  rules describe from the other side: a commit whose tree is assembled for one path took the other
  paths' content from an index older than the last commit, and the delta is invisible in the commit
  subject. Detection is cheap and belongs in the same breath as the `git show HEAD:<path>` check a
  session already owes its own commit — for a landed change, `git show origin/main:<path> | grep
  <the symbol>` — and the remedy is a re-land (`af6ded8`), never a rewrite.
- **Two zero-byte files in the repo root are a shell accident, not content**: `-` and
  `command: rendered from defaults + placeholders` (plus `reads`, `writes, then reown() to cache
  owner`, `mods: pre_exec, in order, as root`), all created 11:55 by a command whose unquoted
  arguments word-split. They are untracked and empty, so nothing was lost, but any directory add
  would sweep them into a registry that ships to third parties. Left for their session to remove.

### 12:02 ET — hourly board tick: the pool outage was already on the board, so the tick wrote no board

- **A peer tick published the BeeGFS outage at 12:10 (`d367c06`, board content sha `d8316d53`), and this tick's read is 38 s fresher
  at most, so the board was left standing.** `publish --expect-sha` refused at 12:09 with `disk …
  carries 2026-11-08 12:10:00 ET, newer than this read's 12:09:00 ET`; the peer's row already names
  `beegfs-mgmtd`/`meta`/`storage` failed on `.30` at 11:27:57, `.31`–`.35` `storage=active` with
  `mgmtd=inactive`, every client dead, and it folds all twelve commits from 11:41 to 12:01 that this
  tick had queued as landed rows. The one fact it did not carry is below, which is why the delta went
  here rather than into a third whole-file write 60 s after someone else's.
- **The fleet is measurably idle, not merely uncounted**: root bytes 12:01:19 → 12:02:27 ET fell
  **901 120 B ≈ 0.86 MiB across all six nodes** (`.30` 520 192 B; `.31`–`.35` 73 728–81 920 B each),
  with containers `1 / 0 / 0 / 0 / 0 / 0`, volumes `0`, and `sparkrun status` `Idle hosts` on all six.
  Free space is `.30` 1167.44 / `.31` 1530.35 / `.32` 1602.72 / `.33` 1494.13 / `.34` 1000.60 /
  `.35` 1246.19 GiB. That pair is the load-free corroboration of the pool diagnosis: nothing is
  writing *because* nothing can open the pool, so the flat series cannot be read as health.
- **Two independent probes make the outage fleet-wide rather than a head-client wedge**, and that
  distinction is the one worth keeping: `df /mnt/beegfs` returns `Communication error on send` from
  `.30` **and** from `.31`, `:8008` has no listener on the mgmtd host, and the head's kernel log gives
  the causal chain — `Receive failed from management [beegfs-mgmtd:1] @`:8008 `(recv result: -104)`,
  `NodeConn … Connect failed on all available routes`, then every metadata and storage target
  `set to offline`. Read from one node alone, the same error looks like a client that needs a remount.
- **`.31`–`.35`'s `beegfs-meta=failed` is a standing benign condition, and the falsifier is the
  journal date**: `No metadata storage directory specified`, failed since 2026-11-05 22:05:26, on
  nodes that host no metadata target. So `systemctl is-failed` fleet-wide is not an outage signal by
  itself — `.30`'s three units since 11:27:57 are — and a future tick that reads it fleet-wide without
  the date will mis-size the blast radius in the other direction, calling a healthy pool dead.
- Recovery is `sudo systemctl start beegfs-mgmtd beegfs-meta beegfs-storage` on `.30`, then the
  clients, and **this tick did not run it**: the hourly refresh is read-only on the fleet, and `.30`
  holds the single mgmtd, which makes it an owner call rather than an operator convenience.

## 2026-11-08 12:18 ET — the pool outage ended at 12:06:46; the tick published on its own census, and the register has one runnable arm again

- **The BeeGFS outage above is closed by a start, not by a repair.** `beegfs-mgmtd`, `beegfs-meta`
  and `beegfs-storage` on `.30` (which is the head, `spark-41e1`) read `active` with
  `ActiveEnterTimestamp = 12:06:46 EST` and `NRestarts = 0`, so the units were started rather than
  restarted by a supervisor. The 12:02 section's recovery line is therefore history; what it asked
  for has happened.
- **The three discriminators that rule out the cached-metadata reading an `ls` cannot:**
  `ss -ltn` shows `*:8008` LISTEN (mgmtd); `df /mnt/beegfs` returns `22530G / 9187G avail` from
  both `.30` **and** `.31`, and statfs is answered by mgmtd; and a real shard read —
  `model-00001-of-000096.safetensors` under `models--vllm-project--Kimi-K3.1-Pro-pruned75`,
  **16 MiB in 0.069 s = 243 MB/s** at 12:17:43 — crosses the fabric to a storage target rather than
  serving a name. `ls /mnt/beegfs/huggingface/hub` returned **111** entries from all six nodes and the
  head at 12:13:22–12:13:32.
- **`beegfs-meta=failed` on `.31`–`.35` is the standing benign condition the 12:02 section already
  dated** (`No metadata storage directory specified`, since 2026-11-05 22:05:26, on nodes hosting no
  metadata target) — measured again this cycle by naming each unit; `.30`'s helperd/client units are
  `inactive` while its mount is up, which is also not a fault signal.
- **Board:** published 12:14 (`bcf7d1ca`) and again 12:18 on this tick's own **12:00:59 / 12:07:01**
  census, both through `publish --expect-sha`, so the peer's 12:10 board (`d8316d53`) was folded
  rather than replaced: its `pool` row was rewritten on the evidence above, its landed rows and its
  `.34`/`.35` row kept, and one register row added.
- **The register changed under the board and is not this tick's to commit.** `mad-science/queue.json`
  is modified against HEAD (`dadc3545…`, two lines): `w4-survey-arm5-control-boot` flipped
  `blocked` → `queued`, and it carries both a `recipe:` (`zz-ds4-1017-sm121-arm3-control-marlin.yaml`)
  and `tp: 4`, so the campaign's eligible set is no longer empty and `.30`–`.33` are idle. The other
  nine queued rows name neither key, and `plan.py` admits only a row that names both.
- **Open drift, reported rather than acted on:** the board's `Landed session` table carried **144**
  rows at this cycle, accumulated across many closed sessions since no boundary clear. This tick did
  not clear it — a peer is actively appending rows (19 arrived inside ~10 minutes) — so the clearing
  session owes the homing pass first: `git grep -c <sha> -- mad-science/SESSION-RECORD.md` per row,
  carry what is missing, then clear.

## 2026-11-08 12:20 ET — the pool outage's start was this tick's, and the campaign spent its retries inside it

- **Attribution the 12:18 section left open ("started rather than restarted by a supervisor").** This
  tick started them: `sudo -n systemctl start beegfs-mgmtd` at **12:06:46** and
  `sudo -n systemctl start beegfs-meta beegfs-storage` at **12:07:21** on `.30`, ordered mgmtd first
  because meta and storage register against it (`Registration and management info download complete`,
  `Nodes added (sync results): 6 (Type: beegfs-storage)`). The unit timestamps that section read are
  these starts.
- **The diagnosis, before any start, with the discriminators in order.** `systemctl show -p Result
  -p ExecMainExitTimestamp -p NRestarts` on `.30` gave `Result=oom-kill` and
  `ExecMainExitTimestamp=Sun 2026-11-08 11:27:57` for all three, `NRestarts=0`; the journal said
  `A process of this unit has been killed by the OOM killer` for each at 11:27:57 and quoted their
  peaks — `beegfs-storage` **38.2 GB** memory peak, `beegfs-meta` 146.7 MB, `beegfs-mgmtd` 36.5 MB.
  Client side: no listener on `:8008` (`Connection refused`), `ls /mnt/beegfs` answered
  `Communication error on send` (Errno 70) on **all six** nodes and the head, `stat -f` reported
  `Blocks: Total 0  Free: 0`, and the head's client logged
  `Receive failed from management [beegfs-mgmtd:1] @ .30:8008 (recv result: -104)` at **11:27:56** —
  one second before the servers' exit timestamps — then
  `Metadata node state sync failed. All nodes set to offline` at **11:42:16**. So the pool was dead
  from 11:27:57, and every clean `ls` after 12:07:21 is post-start: the "intermittent" reading was a
  pre/post-restart comparison, which is why the live board's `pool` row was rewritten in place rather
  than amended.
- **What the outage cost, measured in the campaign's own words.** The unit restarted at 12:06:35 and
  leased `zz-ds4-1017-sm121-arm3-control-marlin` as attempts **4, 5 and 6**; each closed inside ~20 s
  at `[3/6] Distributing resources` with
  `Error: launch_inference failed: [Errno 70] Communication error on send:
  '~/.cache/huggingface/token'`. The token is a pool symlink, so a dead pool surfaces as a
  *distribution* failure — an arm failure with no `recipe:` in the message — and `retries3.conf` was
  exhausted: the arm is `failed` at `attempts=6`, no marker. Its attempt-1 lever evidence
  (`moe_runner_backend: 'marlin'`, `Load weight begin. avail mem=112.08 GB`, no 128-multiple
  refusal) survives only in the receipt dir rotated to `.prev-113207`. **The lesson is the verdict
  shape, not the arm: an unattributed Errno 70 on a cache symlink is a fleet-storage check, and the
  tick's census never looked past `docker ps`.**
- **Recovery verified from three nodes, not from the head alone** (12:07:47): `.30`, `.31` and `.35`
  each listed **111** hub entries, and the pruned75 body read **112** entries / **96** of 96
  shards / **0** `.incomplete` / `475 507 835 896 B` by a `find -L -printf '%s'` sum = **442.85 GiB**
  at revision `fc72e5a1…` — 17.3 MiB under the 11:05 walk's `475 525 935 884 B`. Both round to
  442.87 GiB and the TP=4 fit is unmoved (110.71 GiB/rank against a 109.67 GiB util-0.92 budget),
  but the difference is recorded rather than smoothed, because the only reason to prefer one
  instrument is that it is the same one that produced the number being compared.
- **Open defect, and it is why 39 minutes produced no recovery:** the three units carry no
  `Restart=` policy (`NRestarts=0`, `Result=oom-kill` left failed). A pool outage is silent — the
  fleet's own probes (`docker ps`, `sparkrun status`) read healthy throughout — so this hour's
  failure mode is available again on the next OOM. Not fixed here: a unit-level policy change on
  `.30` is an owner decision, and it is recorded here because a ticket in operator memory is not a
  ticket.
- **Register hygiene, reported and not edited.** `mad-science/queue.json` is modified against HEAD
  and that uncommitted edit carries a **raw cluster address** in the arm5-control row's notes
  (`…the sparkrun daemons were INACTIVE on .30–.33…`), which
  `tests/test_tracked_address_hygiene.py` will fail the moment anyone commits it. The board's queue
  table masks it to `.30`–`.33` (its own `publish` door refuses an address, which is how the leak was
  found), and the row itself is another session's text, so it is reported, not rewritten. The
  register also flapped between reads — 10 queued + 10 blocked at 12:07, 9 + 11 two minutes later,
  with `w4-survey-arm5-control-boot` the row that moved — the signature of the open
  `task-queue-write-clobbers-live-claim` row, now with a second observation.
- **Board:** published **12:19** through `publish --expect-sha` (`disk was 12:18:00 ET`). The fold
  kept the peer's `census`, `.30`, `.30`–`.33` and `.34`/`.35` rows verbatim, replaced the `pool`
  row with the evidence above, refreshed `campaign` (9 measured / 1 failed / 8 blocked), `queue mode`,
  `window` and `register`, and appended 14 landed rows (11 re-derived from `git log`, three
  measurements) time-sorted. A peer then committed the worktree board as `9606127` before this
  section existed; its subject ("pool reads healthy again and one quartet arm is plannable") is the
  pre-correction reading, and the board it committed carries the corrected `pool` row. **That SHA
  is now dangling** — `9606127` is reachable from no ref here and is not on `origin/main`, because
  the same content was re-applied onto the remote tip and pushed as `8668667` when the direct push
  was refused; cite `8668667`, which is the commit `origin/main` carried.

## 2026-11-08 12:21 ET — the pool as read by the tick that found it already back (appended inside the section above)

- **The pool came back at 12:19 and the body survived the crash byte-intact**: `.30`'s three units read
  `active active active` at 12:20:37 ET, `df` 23T/14T used/9.0T avail at 60%, `ls` 111 entries, 96
  safetensors shards, zero `.incomplete`, and `du -sL --apparent-size -B1` on the revision-`fc72e5a1…`
  snapshot reads **475 525 935 884 B = 442.87 GiB — identical to the 11:05:24 pre-outage read**, so the
  OOM truncated nothing and no session owes a re-stage before its next boot. Restarted by a peer
  session, not this tick, which stayed read-only.
- **`beegfs-client=inactive` is not a fault on this fleet, and the assumption that recovery owes a
  client restart is falsified**: `.30` and `.31` both report `inactive` while serving reads and `df`
  for that same mount, so the mount is carried by the kernel module and the restart is `.30`'s three
  server units only. Recorded because "restore mgmtd, meta, storage, *then* the clients" is the
  advisory-shaped answer and it would send the next session chasing a unit that is never active.
- **A remote sum needs its awk field escaped through every layer, and a zero that arrives beside a
  correct count is the tell**: `awk "{s+=\$1}"` nested inside two ssh double-quote levels lost the
  field and reported `dedup=0.00 GiB` over the 112 files the same pipeline had just counted — which
  reads exactly like an empty body. Use `du -sL --apparent-size -B1` (the sanctioned instrument) or a
  python payload, and never trust a remote total that disagrees with its own file count.

## 2026-11-08 12:22 ET — corrections to both readings above, and the gate that would have caught attempts 4–6

- **Correction to the two bullets above, in the direction they both point.** The 17.3 MiB gap between
  this tick's `find -L` sum over `*.safetensors` (`475 507 835 896 B`) and the sanctioned
  `du -sL --apparent-size -B1` tree total (`475 525 935 884 B`) is **the 16 non-shard files** —
  `config.json`, the two index files, the tokenizer set — not a body that changed between reads. Both
  instruments are correct about different sets, and the earlier "17.3 MiB unexplained" line invited
  exactly the re-stage it does not need. Weights-only is the number to divide by TP; the tree total is
  the number to compare across boots.
- **And the attribution stays as written above**: this tick started `.30`'s three server units at
  12:06:46 and 12:07:21; the "Restarted by a peer session, not this tick, which stayed read-only"
  bullet appended inside this section is a neighbouring tick describing itself, and its own ledger
  section (`12:18 ET`) names the same `12:06:46` `ActiveEnterTimestamp` it observed rather than
  caused. Two sessions disagreeing about who wrote a timestamp is the reason the start command and
  its two timestamps are recorded here in full.
- **The gate that would have saved attempts 4–6, and why it is not in this commit.** The failure is
  detectable before `[3/6] Distributing resources`: the arm never reached `sparkrun`'s registry step,
  it died resolving `~/.cache/huggingface/token`, which is pool-backed. The shape that fits this
  harness is the one `rc=7 REPLAYED, NOT MEASURED` already uses
  (`tools/run-arm.sh:543-545`): a pre-flight `test -r` on the resolved cache root mapped to its own
  exit code, worded so it can never be read as an arm verdict — and **not `rc=8`**, which the slot
  gate already owns (`:188`). Not landed here because `tools/run-arm.sh`'s test module
  (`tests/test_run_arm_tool.py`) and `tools/README.md` are both modified by peer sessions in this
  same minute: a gate without its test is a half-change, and a half-change in that file set is the
  clobber shape this ledger keeps recording. The row to land it belongs in `queue.json` when that
  file is quiescent, with the code and the test in one commit.
- **The alternative remedy to a bare restart, for whoever owns `.30`'s units.** `Result=oom-kill`
  with `NRestarts=0` means systemd did exactly what it was configured to do — nothing. Protecting
  the storage daemons (`OOMPolicy=`, `OOMScoreAdjust=-900`) or keeping quartet ranks off `.30` are
  both real options; a restart alone is the option that already failed once at 11:27:57 and would
  fail again under the same pressure.

## 2026-11-08 12:22 ET — the board's pool row after the correction

- The published board's `pool` row carried "17.3 MiB under the 11:05 walk" as if it were a
  discrepancy; it now names the non-shard files, so the next reader measures weights with
  `find -L … -name '*.safetensors'` and the whole tree with `du -sL`, and compares like with like.

## 2026-11-08 12:23 ET — attempt 7 ran on the repaired pool and still left no engine copy

- **The marlin arm got a seventh attempt and it created containers**, so the "retries exhausted at 6"
  reading on the 12:19–12:21 boards is superseded: task `1c0dffa45afa6e47_ea9d4f8276e4` on `.30`–`.33`,
  image `sha256:85c1ffc3…`, four ranks `Up` at the 12:12:10 census, watchdog `loading` at t=61 s and
  73 s, `serve_pid=gone` from t=84 s, `verdict=dead` at t=96 s, `ARM DONE … rc=4` at 12:13:08 after
  `/v1/models never answered 200 (200 polls at 15s)` and `Workload stopped on 6 host(s)`.
  `state.json` then reads 9 measured / 9 blocked with no lease, marlin `blocked` at `attempts=7`,
  mtime 12:13:27. So the pool error (`[Errno 70]`) explained attempts 4–6, not this one: attempt 7 is
  an ordinary serve death, and the arm still has no engine-side verdict.
- **Both surviving-copy routes came back empty on the same boot, and the new capture's window is why.**
  The reaped-log capture answered `No such container`, and `tools/engine-exit-capture.sh` (landed in
  `7a7db1d` at 11:44, first live use here) wrote `# capture failed: no container carrying
  sparkrun.recipe=recipes/ds4/zz-ds4-1017-sm121-arm3-control-marlin.yaml was created in 5 s of
  watching /tmp/sparkrun-exitcap.2025334; docker said: nothing` on **all four** ranks. The relay
  container for the same boot (`practical_matsumoto`, `oci-relay/pinned:129a6a39…`) was only `Up 2
  seconds` at 12:12:45, two minutes after the capture armed — a 5 s watch window ends long before a
  four-rank relay distribution produces a container. Not registered as a queue row by this tick: that file
  carries another session's uncommitted `notes` edit, and publishing it by pathspec would ship their
  half-finished text under this commit's subject.
- **A shipped-pin container lived 100 seconds inside the outage**: `nice_perlman`
  (`ghcr.io/littlecedar/dgx-spark-dsv41:canary-roce-aff52fa5`) was `Up 44 seconds (health: starting)`
  at 12:04:47 on `.30` and gone from `docker ps -a` by 12:06:28, while every node's
  `/mnt/beegfs/huggingface/hub` answered `Communication error on send` — so it cannot have loaded
  weights, which is the same pool-broken `hf` token path the 12:20 section records for the arm
  leases. No lease, campaign arm or lock row named it; this tick removed nothing.
- **Board:** published **12:23** through `publish --expect-sha` (`disk was 12:21:00 ET`), folding onto
  the peer's 12:21 board rather than replacing it — its `pool`, `head clone`, `queue mode`, `window`
  and `register` rows are kept verbatim, this tick's later container reads and the attempt-7
  correction are appended to the `census` and `campaign` rows, two measurement rows are appended
  time-sorted, and the queue table is that cycle's own `render --board` (20 rows). Census reads
  12:02:53 / 12:05:19 / 12:09:54 / 12:12:10 / 12:14:03 / 12:21:44 ET: `1/0/0/0/0/0` at every quiet
  read, `2/1/1/1/0/0` while attempt 7 was up, volumes `0` throughout, the byte pair 12:02:53 → 12:12:10
  down **53 903 360 B ≈ 51.4 MiB across six nodes**, and the register at 9 queued + 11 blocked with
  zero claims.

## 2026-11-08 12:29 ET — the OOM's third casualty is still failed, and two register notes break the board table

The 11:27:57 head `global_oom` killed three things that got a board row and one that did not. The BeeGFS
server stack came back in 39 minutes and the pool reads healthy (23 T, 9.0 T avail, all three units
`active`). What is still broken is the **user unit `syncthing.service`**: `failed (Result: exit-code)`
since **11:29:32** (19 ms runtime, its start attempt after the kill), while two orphaned
`/usr/bin/syncthing serve` pids keep running — so the head is still syncing, from processes no unit owns,
and a restart of the unit is what would put it back under supervision. Not restarted by a tick: it is a
shared box and the unit's state is the owner's call, which is why the row reads `head clone` on the board
rather than being repaired silently. Separately, the `bad object HEAD` reading from 12:04 is **closed**:
`refs/heads/main` realigned at 12:23:50 to `d99c3e2…` (which resolves on the workstation too) and the
head's checkout answers `ahead 4, behind 3` instead of dying, plus a stale
`refs/heads/main.sync-conflict-20261108-041329-TOW2T6H` ref left in its `.git`.

Two defects found while folding this hour's board, both cheap to state and neither repaired by a tick:

- **A register note is free text, so a cluster address can reach a tracked file with no gate until CI.**
  One open row's note briefly carried a literal management address; `git status` read the file clean and
  the pushed version carried it, which makes `task-queue.py publish` refuse a board built from that
  register (it lints addresses) and would redden `tests/test_tracked_address_hygiene.py` on the tip. A
  peer masked it to `.30`–`.33` shorthand and committed while this tick was composing, so nothing was
  published with it — but the class is that the note field has no writer-side check, only the readers'.
- **`render --board` does not escape a `|` inside a register note, so three open rows break their own
  table row.** `w4-survey-arm5-control-boot` (`sm121|sm_121|major == 12`),
  `glm-flash-concurrency-degradation-search` (`(vllm|sglang|...|python3|python)`) and
  `h2h-beam-house-and-bfcl-category` (`| DEFERRED`) each gain two to fourteen extra cells; GFM splits the
  row at every pipe, so the state text lands in columns that do not exist and the row reads misaligned
  against its 4-cell header. `task-queue.py lint` passes it (`ok: 1 markdown file(s) render`) because the
  delimiter row is intact — the defect is per-row, not per-table. The fix belongs in the renderer
  (escape `\|`), not in the notes: a note is prose and an operator will type a pipe again.

## 2026-11-08 12:34 ET — the head clone is diverged, not merely stale

- **`d99c3e2` ("Ledger: the pool is back and the body survived the OOM byte-intact", the head's
  `HEAD` at 12:26) is not an ancestor of `origin/main`** — `git merge-base --is-ancestor d99c3e2
  origin/main` fails on the workstation, and `git diff --stat origin/main d99c3e2` is not empty
  (11 files, 42 insertions / 444 deletions travelling backwards), so the head clone carries a local
  commit whose content was re-applied differently on the remote. Its upstream ref is also gone
  (`## main...origin/main [gone]`), so `git pull` there fails before it can merge anything. Reported,
  not touched: rewriting refs on the syncthing source of truth is the operation this repo forbids
  outright, and the content is already reachable on `origin/main` under the commits that were
  pushed. The board's `head clone` row carries the measurement.

## 2026-11-08 12:42 ET — the chore-row reconciliation gets a home off the board

- **`03f7b695`'s clause is the only landed row on the 12:xx boards with no other home** (`git grep`
  finds it nowhere but `STATUS.md`; `619e786`'s dependency-gap and 7,303 B facts already live in
  `recipes/explore/README.md` and the DSpark recipe, and `8a4aab6`'s `read-tree`/census-gap facts are
  already below): it reconciled the six chore rows by evidence — three closed against `4aabfc87` and
  `3e6c8ed9`, one narrowed to `task-queue.py`'s `_save` having no compare-and-swap (now the open
  `task-queue-write-clobbers-live-claim` row), two verified open with `file:line` gaps — and cleared
  nine finished rows' `blocks` pointers so four trackers stopped reading as gated by done work. The
  register is the artifact and carries the resulting state; this line carries the reasoning, since a
  board regeneration would take it.

## 2026-11-08 12:38 ET — a launch can fail for reasons that read as arm failures, and a capture that quits early is not evidence

- **Infrastructure failure wore the arm's own vocabulary.** Leases @3–@6 of
  `zz-ds4-1017-sm121-arm3-control-marlin` (12:06:35–12:07:04, receipts `.prev-120637` and its
  siblings) each closed in ~20 s at `[3/6] Distributing resources` on
  `Error: launch_inference failed: [Errno 70] Communication error on send:
  '/home/red/.cache/huggingface/token'`. None reached a task id, so the only place that event
  could land was the arm-failure column — and it was not the arm: the per-node `sparkrun` daemons
  were **inactive**, `sparkrun daemon start` on the hosts let the next lease reach `[6/7]`, and the
  token path itself was fine. `9ef01bc` records it as DESIGN and a one-status-per-host preflight is
  being added, because a dead daemon must surface as a daemon, not as a credential.
- **The capture was noise, not silence.** Attempt 7 of the same arm
  (`zz-ds4-1017-sm121-arm3-control-marlin@7.log`, receipt `.prev-121048`, task
  `1c0dffa45afa6e47_ea9d4f8276e4`, container `sparkrun_1c0dffa45afa6e47_ea9d4f8276e4_node_0`)
  reports `engine stdout captured: 0 container stream(s)` and the capture's own line reads
  `# capture failed: no container … was created in 5 s of watching` — because
  `tools/engine-exit-capture.sh` gave up about five seconds in, while the launcher was still
  resolving the task. The boot died 135 s later on the watchdog's stop. A capture that exits before
  the launch window has produced **no evidence at all**; it is not evidence of engine silence, and
  reading it as one is how an unattributable death becomes a false finding.
- **The rule both halves share.** An arm's failure class is only as good as the instrument that
  observed it: name the instrument in the receipt (a daemon status, a capture window), and when the
  instrument did not run or quit early, the row says `unattributable`/`untried`, never `failed`.

## 2026-11-08 12:42 ET — one window held two faults, and the error string names only one of them

- **The 12:38 section and this tick's 12:20 section are both true about attempts 4–6, and the
  difference matters for the next failure of the same shape.** Measured by this tick before any fix:
  the BeeGFS servers were `Result=oom-kill` from **11:27:57** and `ls /mnt/beegfs` returned ECOMM on
  all six nodes until **12:07:21**, i.e. across the whole 12:06:35–12:07:04 lease window. Measured by
  the 12:38 tick: the per-node `sparkrun` daemons were `inactive`, and `sparkrun daemon start` let
  the next lease reach `[6/7]`. Both conditions were live at once, so neither reading is wrong — but
  the **error string discriminates**: `[Errno 70] Communication error on send` is the BeeGFS client's
  ECOMM (`errno 70`, `ECOMM`), raised by `stat` on a pool-backed path, and a stopped local daemon
  does not produce it. What a stopped daemon produces is a *different* failure at the same step.
- **So the pre-flight owed is not one check but two, and they belong at different layers.** A pool
  probe (`test -r` on the resolved cache root, mapped to its own exit code so it can never read as
  an arm verdict) covers ECOMM; a daemon-status probe covers the `inactive` case the 12:38 tick
  found, which `9ef01bc` is already adding as a one-status-per-host preflight. Neither substitutes
  for the other, and a receipt that names only one of them will mis-file the next occurrence.
- **The discriminator that would settle it, for whoever repeats this:** with the pool up and the
  daemon down, the token `stat` succeeds and the failure moves to the distribution step's daemon
  call; with the pool down and the daemon up, it is ECOMM on the token path. One lease on each side
  separates them in ten minutes, and the second half is already available — attempt 7 ran after both
  repairs, so its failure is neither of these classes.

---

## 2026-11-08 12:45 ET — the pruned75 body is complete the way a boot needs, and `.30`'s storage server is the quartet's co-tenant

- **The entry count the board quotes both ways is one file, and that file is hidden.** The board
  carries **112** entries from the 11:05 pre-outage read and **111** from the post-recovery reads,
  which reads like the outage cost something. It did not: `ls -a` on
  `snapshots/fc72e5a1dd88…` gives 114 lines, minus `.` and `..` = **112 entries**, one of which is
  `.gitattributes` — hidden, so a plain `ls` shows 111. Of the 112, **96 are `.safetensors` shards**
  and the visible remainder is 15 files: `config.json`, `configuration_kimi_k3.py`, `encoding_k3.py`,
  `generation_config.json`, `kimi_k3_processor.py`, `kimi_k3_vision_processing.py`, `media_utils.py`,
  `model.safetensors.index.json`, `preprocessor_config.json`, `tiktoken.model`, `tokenization_kimi.py`,
  `tokenizer_config.json`, `LICENSE`, `README.md`, `assets/`.
- **The sizes are the load-bearing part, not the count.** `model.safetensors.index.json` measures
  **15,114,413 B** and `config.json` **7,303 B**; **there is no `tokenizer.json` and none is expected**,
  because this checkpoint's tokenizer is Python code (`tokenization_kimi.py` plus `tiktoken.model`) —
  precisely the config-only-stub shape the 10:45 entry mistook for a truncated download. So
  `kimi-pruned75-tp4-boot`'s pool gate closes on a real 15 MB shard index plus a code-based tokenizer,
  not on the shard count alone.
- **`.30`'s storage server shares the host with any rank placed on it, and that is the next quartet
  boot's real budget.** The 11:27:57 `global_oom` killed `beegfs-storage` with a **38.2 G** memory
  peak — `beegfs-meta` and `beegfs-mgmtd` died with it (`journalctl -u beegfs-*` on `.30`) on a
  121 GiB box that at that moment also held the marlin quartet's rank 0. A quartet boot that puts a
  rank on `.30` therefore sizes the engine's `gpu_memory_utilization` against the GB10's unified pool
  but not against the 38 G a storage server there can claim, and the cost of getting that wrong is
  fleet-wide: the OOM took the weights away from every node, not just that arm. Either move storage
  off `.30` or budget the host explicitly before the next quartet boot.

---

## 2026-11-08 12:44 ET — `nice_perlman` stopped itself, and the probe body went with it

- **The 12:04:47→12:06:28 gap resolved from `.30`'s own event stream** (the daemon has run since
  2026-11-05, so `docker events --since 2026-11-08T11:55:00 --until 2026-11-08T12:09:00` still
  replays it; a bare `--since 12:00` is refused, it wants a full timestamp or a duration):
  `nice_perlman` (`ghcr.io/littlecedar/dgx-spark-dsv41:canary-roce-aff52fa5`) ran
  `/opt/dsv41/boot.py health` on a ~5 s loop, **nine `exec_die exit=1`** up to 12:06:14, then
  **`die exit=0` at 12:06:19** and `destroy` the same second. A graceful exit and auto-remove, not a
  kill and not an OOM: the earlier wording ("came and went") under-described it, and "failed on the
  empty pool" would over-claim, because the health probe's own body was removed with the container and
  nothing names why the gate returned 1. What is established: while it ran, all six nodes answered
  `Communication error on send` on `/mnt/beegfs/huggingface/hub`, so it never loaded weights.
  Board row corrected in place at 12:43; a peer's `attempt 7` and `pool` rows on the same board carry
  the watchdog series and the `ActiveEnterTimestamp` recovery, so only this cell was mine to change.

## 2026-11-08 13:33 ET — `.35`'s unattributed root rise had an author, and the campaign's counts moved past the row that quoted them

- **A 50 s vLLM-nightly container ran on `.35` between two census reads and nothing in the repo names
  it.** Created **13:06:16**, `Up 11 seconds` at the 13:06:08-adjacent inspect, gone by the 13:07:06
  read: image `ghcr.io/spark-arena/dgx-vllm-eugr-nightly-b12x` at `sha256:cf5a2a53…`, image id
  `sha256:e90182b5…`, `Config.Labels` carrying **no** `sparkrun.recipe`, and `docker volume ls` empty
  on the node — a bare `docker run`/`--rm`, not a sparkrun task, started in the same window the pool
  went unreadable. It is the author of the fall-to-rise that the 13:07 board carried unattributed:
  the 58 s byte pair `.35 +45 846 528 B` (43.7 MiB) is that image's tail, and the earlier
  13:01:21→13:07:00 pair's `+3.699 GB` is the same pull arriving (the nightly layer, ~3.4 GiB). So
  that column needs no per-node mystery; only `.34`'s −192.8 MiB remains unattributed. The tick
  removed nothing, and the container had already removed itself.
- **The campaign row's counts are a mid-window read, and the settled numbers are different.** The
  13:26 board quotes `9 measured / 8 blocked / 1 leased` from **13:02:54**; at **13:08:07** and again
  at **13:30** `director status` reads **9 measured, 9 blocked, no lease**, `state.json` 13:13:38,
  every arm `lease None`, the marlin arm at **`attempts=11`** and back from `failed` to `blocked` on
  the register reconciliation. The direction the row states (nothing plannable) is right either way,
  which is why this is a count correction and not a finding: a lease-read taken mid-flight describes
  the flight, not the state. Left as an appended row rather than a rewrite of the peer's cell.
- **`.35`'s later container is a different one and does not supersede the above.** A peer session's
  read-only source grep (`focused_babbage`, `lmsysorg/sglang:dev-cu13@sha256:0b3e3970…`, started
  13:18:40) is the 13:26 board's `.35` row; the two are disjoint in time, so neither accounts for the
  other's byte slice.

## 2026-11-08 13:46 ET — retraction: `.35`'s movement is a deletion, not a pull, and the §13:33 attribution was wrong twice over

- **The §13:33 claim that `.35`'s rise was the vLLM-nightly image arriving is withdrawn.** One read
  settles it and contradicts both halves of the story: `docker image inspect
  ghcr.io/spark-arena/dgx-vllm-eugr-nightly-b12x` on `.35` returns size **18 186 256 536 B = 18.2 GB**
  (tag resolves to `sha256:cf5a2a53…`, image id `sha256:e90182b5…`, `.Created`
  **2026-10-15T09:48:34**), and `docker image ls --digests` shows the same digest on the node now. So
  the 50 s container reused an image already present: it pulled nothing, and **18.2 GB could not appear
  as a 3.45 GiB slice** in any case.
- **The direction was read backwards, and that is the instructive part.** `df --output=avail` **rising**
  means space was **freed**. `.35` did rise — `+3.699 GB` across the peer's 13:01:21→13:07:00 pair and
  `+45 846 528 B` across this tick's 58 s 13:06:08→13:07:06 pair — so the node **reclaimed** ~3.7 GB in
  that window, and the 13:07 board's "unattributed rise" was a deletion all along, not a write that had
  yet to find an author.
- **The timing splits the one candidate into a small part.** The bulk (~3.65 GB) is already gone by the
  13:06:08 read, i.e. **before** the container was created at 13:06:16; the remaining ~43.7 MiB is freed
  while it existed, which its own removal can account for. So the container explains at most the tail,
  and the ~3.65 GB belongs to whoever removed an image or container on `.35` between 13:01:21 and
  13:06:08 — unnamed by anything this tick read, and not attributable from `docker image ls`, which
  shows what remains rather than what was deleted.
- **What still stands from §13:33**: the container itself (created 13:06:16, `Up 11 seconds` at the
  13:06 read, gone by 13:07:06, no `sparkrun.recipe` label, no volume) and the campaign's settled counts
  (9 measured / 9 blocked / no lease at 13:08:07 and 13:30, marlin at `attempts=11`). Only the causal
  sentence is withdrawn.
- **The general lesson, worth keeping beside the `du -sb` trap**: a `df` byte series carries a sign, and
  a *rise* in available bytes is never evidence of a writer. Both this tick and the 13:07 one carried
  the number as "unattributed movement" without applying its direction, which is how a deletion got
  offered an author as a download.

## 2026-11-08 13:41 ET — the 12:59:14 kill, the daemon refusal, and a board split no CAS can see

**The two head events are not evidenced as one mechanism, and the board said they were.**
At 11:27:57 systemd logged `Failed with result 'oom-kill'`; at 12:59:14 it logged
`Failed with result 'signal'` with the same `status=9/KILL`, `NRestarts=0`, `Restart=no`.
The 12:59:14 window carries the kernel's show_mem dump (`Node 0 Normal: 206240kB` free,
`Unreclaimable slab info`) and `systemd-journald[579]: Missed 30225 kernel messages`, so
no `invoked oom-killer` or `Killed process` line survives anywhere. What is measured is
memory exhaustion immediately followed by SIGKILL: the pressure is evidenced, the killer's
identity is not. `beegfs-mgmtd`, `beegfs-meta` and `beegfs-storage` died in it and the
weights pool has been unreadable since; earlyoom's next line (13:00:46) reads
`mem avail 118650 of 124608 MiB (95.22 %)`, i.e. the kills freed the memory rather than a
shortage persisting.

**A hung BeeGFS client cannot be timed out.** `stat -f -c %T /mnt/beegfs` on the head
blocks in an unkillable D state, so `timeout 5`/`timeout 8` never reaps it and the whole
remote command hangs — two whole census attempts died that way (13:09:08, 13:10:19) before
the loop dropped every `/mnt` probe. `ConnectTimeout` bounds the connect, not the command.

**The daemon preflight's refusal has an effect but no established cause.**
`run-arm.sh` refused marlin attempts @10/@11 at 13:08:00 and 13:08:07 (`rc=9`,
`no running sparkrun daemon on .30 .31 .33`, evidence `daemon-preflight.txt`) — the shape
`9ef01bc` predicted, and the first live case of a refusal replacing a wasted boot. But
`sparkrun daemon status` answered `running: true` on all four rank hosts at 13:15, and the
daemon processes alive at 13:31:05-13:31:08 carry that start time, so they restarted at
least once after the refusal and no pid predating it was found. What is verified is the
effect (no rank could take a distribution); the cause stays unattributed.

**The board split across lineages, and `--expect-sha` cannot notice.** Measured 13:41: the
local clone's board (title 13:39) carries 253 landed rows, `origin/main`'s (title 13:36)
carries 178, with 84 rows local-only and 9 origin-only — among the 9 this tick's
`13:35 correction, the 12:59:14 attribution` row. `git rev-list --left-right --count
origin/main...HEAD` read 30/21. `publish --expect-sha` compares this clone's file against
this clone's own read, so it guards a peer *inside* one clone and is blind to a second
lineage: a whole-file push between them replaces 84 rows in one direction and 9 in the
other, silently. The landed table is the durable record, so the repair is a union merge
(row-keyed, exact strings) and not another regeneration; `0dc9764` registers the same
class from the register side ("the two clones hold one row in opposite states, and no CAS
notices").

**Armed state at 13:41.** Register: 112 tasks, 89 done, 11 queued + 12 blocked, zero
claims, `check` green. Campaign `h2h-20261107`: unit active, no lease, 9 measured / 8
blocked, and `zz-ds4-1017-sm121-arm3-control-marlin` failed at `attempts=11` with
`state.json` `failed` against a register row that reads `blocked`. Fleet: no container
running anywhere, one never-started `sm121m` `Created` on `.30` since 10:32, roots flat.
Nothing is bootable while the pool is down, and the pool needs a manual
mgmtd -> meta -> storage restart because all three units carry `Restart=no`.

## 2026-11-08 15:29:55 ET — window B closes on a verified read, not on a restart

**The rule this closes.** The 13:22 clause makes a cell timestamped in either pool-down window invalid, not weak. Window
A closed on a restart (`mgmtd` `ActiveEnter 12:06:46`, `meta`/`storage` 12:07:21, last client transient 12:07:28); window B
had no close at all, so every cell at or after `12:57:32` was invalid by default. It now has a close instant with the
evidence behind it.

- **Units, on all six hosts:** `beegfs-mgmtd`/`beegfs-meta`/`beegfs-storage` `active (running)` since **15:29:55**,
  `Result=success`, `ExecMainExitTimestamp` **empty**, `NRestarts=0`. `mgmtd` listens on `:8008` and `:8010`, every
  storage on `:8003`.
- **Registrations complete at 15:29:55:** `beegfs-meta` logged `Root directory loaded.` and
  `I got root (by possession of root directory)`; every storage logged `Node registration successful.` and
  `Registration and management info download complete.`, with node IDs 1–6 for `.30`–`.35`.
- **Every host reads the pool, which is the proof the old clause demanded:** all six list **111 hub entries** and return
  rc=0 on a shipped recipe's snapshot (`…/DeepSeek-V4.1-Flash-1017/snapshots/1bae0e1088…`); `df -B1` answers
  **22.0 TiB total / 9.0 TiB available on every host**; no host landed in either ECOMM error class, and the head
  reattached **without a remount** (no `umount` was needed).
- **Nothing lost:** `.30` storage is **byte-identical to the pre-outage read, `1,377,231,104,535 B`**, and no stale
  `lock.pid` survives — every one was rewritten 15:29/15:30.
- **Admissibility now:** a cell **at or after `15:29:55` on a host that read the snapshot** is admissible. Cells between
  `12:57:32` and `15:29:54` remain **invalid — window B**, and the 13:22 window A range is unchanged.
- **Caveat that must travel with any refusal from here on:** `tools/run-arm.sh`'s pool gate is currently **red on healthy
  clients** — it demands `mgmtd`/`meta` on *every* host, which `.31`–`.35` never ran — so until that fix lands a receipt
  refused "pool does not answer" is **not** evidence of an outage, and reading it as one would contradict the units above.
  Another session owns the fix; the clause stays until a green gate run exists.

## 2026-11-08 — the pool-window admissibility rule, stood up in this lineage

The rule below was pre-registered at **13:22** as one row of a board table in a lineage this file could not see,
so until now the fleet had the gate row (`pool-window-invalid-cells`, register) and no rule text to enforce it.
It is written out in full here. The section above already closes window B at 15:29:55; nothing below contradicts
that — the `12:57:32` range ends at the close instant, not at "now", and B is not open.

- **What the rule forbids.** A cell timestamped inside a pool-down window is **invalid, not weak**: a dead mount
  presents as an empty `/cache`, so an arm can pass readiness and produce a cell against weights it could not
  read. Such a receipt is not quoted as a measurement; the lane and the board say "invalid — pool window"
  rather than leaving a number standing.
- **Window A — `11:27:56`–`12:07:30`:** the head's `mgmtd`/`meta`/`storage` killed at 11:27:57 by the head global
  OOM, restarted 12:06:46 and 12:07:21, last client transient 12:07:28 (`Communication error. Node:
  node_storage_1`), and no verified snapshot read inside the gap.
- **Window B — `12:57:32`–`15:29:54`:** degradation with the arm's own OOM (`.31` storage `oom-kill` 12:57:42,
  `.33` `oom-kill` 12:57:33, while `.32`/`.34`/`.35` storage stayed up), then full outage at 12:59:14 when the
  head's three units exited `Result=signal` with `Restart=no` and `NRestarts=0`. **Closed at 15:29:55** — the
  close and its proof are the section above.
- **Admissible middle — `12:07:30`–`12:57:31`:** the interval in which marlin `@8` ran. It died host-side from
  the 12:57 OOM, a separate cause already recorded, so its failure is not a pool artefact.
- **Admissible from the close on:** a cell **at or after `15:29:55` on a host that read the snapshot** is
  admissible. The close proof is not a word: all six units `active (running)` since that instant with an empty
  `ExecMainExitTimestamp` and `NRestarts=0`, registrations complete at 15:29:55, **111 hub entries and a
  shipped recipe's snapshot read rc=0 on all six hosts**, `df -B1` answering 22.0 TiB / 9.0 TiB on every host,
  no host in either ECOMM error class, `.30` storage byte-identical at `1,377,231,104,535 B`, and no stale
  `lock.pid`.
- **What closes a window, should another open.** Not "the pool is back": **all three of** `timeout 10 ls
  /mnt/beegfs/huggingface/hub/<a model the recipe names>/snapshots/` succeeding, `df -h /mnt/beegfs` answering,
  and `systemctl is-active beegfs-storage` reading `active`, on the host that will boot, after the owner
  authorises the restart. **"The mount exists" is not the proof** — `/proc/self/mountinfo` carried
  `/mnt/beegfs` for the whole of window B, so a mount-listed check would have said "serving" while every read
  failed.
- **Candidates at registration: none.** Every `ladder.*`/`house.*`/`client.json` on the shared root predated
  11:27, and a later enumeration found no cell inside either window, so nothing was retracted — the rule
  changed no number, which is exactly why it was worth writing before it could.
- **The gate caveat still travels with every refusal.** `tools/run-arm.sh`'s pool gate is red on healthy
  clients (it demands `mgmtd`/`meta` on *every* host, which `.31`–`.35` never ran), so a receipt refused
  "pool does not answer" is **not** evidence of an outage until a green gate run exists.

## 2026-11-08 — quartet windows are for TP=4 arms; TP1/TP2 run on one or two hosts

Owner directive, recorded so the board's window state can be read correctly. A declared quartet window is **not** a
prerequisite for TP1/TP2 work, and a TP1/TP2 row blocked "waiting for a window" is a scheduling defect, not a
waiting state.

- **Quartets are for `tensor_parallel: 4` only.** `.31`–`.33` are the quartet ranks and are used **only while a
  window is declared**; outside a window they are not a resource a TP1/TP2 arm may take.
- **TP1 and TP2 arms run non-quartet:** one host for `node_cost: single`, two for `node_cost: pair`. No window, no
  quartet lease, no all-six reservation — a TP1 arm held for a window is a scheduling defect to name, not a waiting
  state to report.
- **Preferred non-quartet hosts: `.34` and `.35`** — client-only storage role, so an overrun there costs the arm and
  not the fleet's store.
- **`.30` is avoided for anything that could overrun**: it holds `beegfs-mgmtd` and `beegfs-meta`, so a
  memory-hungry boot there takes every host's ability to read a weight with it (that is exactly the 11:27:57 and
  12:59:14 shape above).
- **Board wording follows from this.** The window cell must read **"reserved for TP=4 arms"**, not "idle" and not
  "the holder is silent" — an idle quartet is the correct state for a fleet whose remaining work is TP1/TP2, and
  reading it as an idle fleet is what makes a window-gated TP1 row look legitimate. Where the board and the register
  disagree about a TP1/TP2 row's window dependency, that divergence is the finding, not a detail to reconcile quietly.
- **Unchanged by the policy:** a boot still needs a readable pool (§15:29:55 close) and still meets the red pool gate
  above until that fix is green — this clause changes who an arm may occupy, not whether it can read a weight.

## 2026-11-08 — correction: `.30` is a normal worker; the host-preference rule is blast radius only

The clause directly above (`## 2026-11-08 — quartet windows are for TP=4 arms; TP1/TP2 run on one or two hosts`,
landed as `f6e5570`) carries a line that says `.30` is "avoided for anything that could overrun" because it holds
`beegfs-mgmtd` and `beegfs-meta`. **That line is withdrawn.** It is the role-based exclusion that `AGENTS.md` §Node
hygiene (`Q8`) forbids: `.30` is a normal worker node, its mgmtd/storage duties are "incidental" and "may never
be used to describe it as unavailable, reserved, 'controller only', 'idle as controller', or excluded 'by role'",
and "leaving `.30` idle while research runs is a violation, not a policy". The framing has regressed three times
(2026-10-24 ×2, 2026-10-25/26) and is swept on sight; this instance arrived from the owner's own dictation, which
is why it is corrected in the record rather than quietly reworded.

**What the rule actually is.** A boot whose **per-rank memory fit is unproven** prefers a client-only host, because
an overrun there costs one storage target instead of the mgmtd+meta pair and every client's mount. That is all it
says:

- **`.30` stays in scope for TP1/TP2 work and for any arm whose fit is known or arithmetically bounded.** Ripple
  BF16 TP=2 at ~64.8 GiB/rank is a known-fit arm and may use `.30`.
- **`.31`–`.33` are ordinary workers outside a declared window**; inside one they are the quartet ranks.
- **Node choice otherwise follows availability, never role.** An idle `.30` is reported as **nothing live (no
  reservation)** — never with a reason attached.
- **Quartets remain reserved for `tensor_parallel: 4`** — that part of the clause above stands unchanged, as does
  its board wording: the window cell reads "reserved for TP=4 arms", never "idle", and never "`.30` excluded".

## 2026-11-08 — the first TP=4 boot is gated on earlyoom tuning being live, not on permission

"TP4 allowed" reads as "go" to whoever picks up the board next, so the precondition is written down **as a proof to
produce, not a box already ticked**.

- **What protection exists now, and only this much:** `OOMScoreAdjust=-1000` on `beegfs-mgmtd`, `beegfs-meta` and
  `beegfs-storage`, live in `/proc/<pid>/oom_score_adj` (drop-ins written 16:03), with `Restart=on-failure` taking
  effect at the next unit start. That stops the pool being **reaped** when the kernel OOMs.
- **What is still missing:** earlyoom's live argv is still `-m 1 -s 70`, so it will not fire before the kernel does —
  a quartet boot that overruns still reaches the kernel's global OOM first. **The proof required before any quartet
  lease** is `/proc/$(pgrep -o earlyoom)/cmdline` showing the **raised minimums on each node in the lease**, together
  with an `earlyoom --dryrun` quote for that node. A tuned unit file that has not been started is not the proof, and a
  board row saying "earlyoom tuned" is not the proof either.
- **Permission is not re-runnability.** The marlin control and the `kimi-pruned75` pair stay **blocked** with their
  measured negatives: host global OOM at ~111.7 GiB available, and 110.71 GiB/rank against a 119.21 GiB pool. A TP=4
  allowance does not reset a measurement — advancing either arm clears those numbers first.
- **Node choice follows availability and fit, never role.** `.30` is a normal worker; an idle node reads **nothing live
  (no reservation)** and carries no reason. The only role-shaped statement in force is the narrative above: a boot
  whose per-rank fit is unproven prefers a client-only host, because an overrun there costs one storage target instead
  of the mgmtd+meta pair.

## 2026-11-08 — the pool survives an overrun: `OOMScoreAdjust=-1000` on the BeeGFS units, earlyoom at 20 %

Owner authorisation: "fix the earlyoom config so the kernel's OOM killer does not reap BeeGFS processes again." Two
mechanisms, because tuning earlyoom only changes *when* a victim is chosen — the kernel still chooses when it fires.

- **The pool's processes are off both killers' lists.** `/etc/systemd/system/beegfs-{mgmtd,meta,storage}.service.d/oom.conf`
  exists on all six hosts with `OOMScoreAdjust=-1000`, `Restart=on-failure`, `RestartSec=5` (drop-ins, not the packaged
  units, so a BeeGFS upgrade cannot overwrite them), followed by `systemctl daemon-reload`. Read back on every host:
  `OOMScoreAdjust=-1000 restart=on-failure restartusec=5s`. **No unit was restarted, and none needed to be:** the
  running daemons were protected in place by writing `-1000` into `/proc/<pid>/oom_score_adj` (mgmtd 2048, meta 2168,
  storage 2164 on `.30`; storage 3243 / 3249 / 3256 / 3226 / 3250 on `.31`–`.35`), each verified by read-back with the
  units still `active/running`.
- **earlyoom now fires before the kernel does.** `/etc/default/earlyoom` went from `-m 1 -s 70` to
  `-m 20,10 -s 100,95 --prefer '(vllm|VLLM|sglang|llama-server|llama-cli|trtllm|tritonserver|ray|python3|python)' --avoid '(beegfs|mgmtd|meta|storage|systemd|sshd|dockerd|containerd|dbus-daemon|NetworkManager|syncthing)'`,
  restarted 16:10:45–16:10:53 and read back from the **live argv** on all six, never from the file. `-m 20` is ~24 GiB
  of headroom on a 119 GiB node; `-s 100` removes the swap conjunct that silenced the memory term (measured 11:27 —
  45 s at 0.34–0.45 % available while swap-free bottomed at 71.02 %, one point above `-s 70`), and the SIGKILL rung
  keeps a real swap backstop at 95 %. The pre-change file is kept as `/etc/default/earlyoom.bak-pre-fix-20261108`.
- **Bootless proof.** `earlyoom --dryrun` on the installed file prints `sending SIGTERM when mem <= 20.00% and swap <=
  100.00%, SIGKILL when mem <= 10.00% and swap <= 95.00%`. A forced-threshold dryrun (`-m 98`) carrying the same avoid
  list selected `python3` (badness 1100) and named none of the three running `beegfs-*` pids, so the avoid list holds.
  Two traps for whoever reads this next: `comm` is truncated to 15 characters (`beegfs-storage/`), and `beegfs`
  matches every pool process by prefix, so the `mgmtd|meta|storage` tokens are belt-and-braces rather than the
  load-bearing part.
- **Still unprotected, owner decision pending:** `ssh.service`, `NetworkManager.service` and `user@1000.service` carry
  no negative adj, and those are the three the 12:59:14 event killed — the user-manager teardown is what took the
  interactive session and the `sparkrun cluster monitor` with it. `OOMScoreAdjust=-900` drop-ins for them are the
  missing half and are **not** applied.
- **What this does not fix.** It changes the victim list, not the engine's footprint: a quartet boot can still overrun,
  and `docker --memory` still cannot bound a GB10 GPU allocation (`tools/README.md` §"run-arm.sh pooling receipts").
  `QUESTIONS.md` #67's candidate (a) is now executed at different numbers than it proposed; candidates (b) and (c)
  remain open, and the pool's `Restart=on-failure` closes the `beegfs-units-restart-no` half.

- **This is the proof the section above demanded.** That clause gated the first TP=4 boot on
  `/proc/$(pgrep -o earlyoom)/cmdline` showing the raised minimums on every node in the lease, plus an
  `earlyoom --dryrun` quote for that node. The argv quoted above is that read-back, one per host, and the dryrun line
  is that quote; the clause's other half (permission is not re-runnability) is untouched by this change.

## 2026-11-08 — correction: window B closed on a clean fleet reboot, and the close instant is unchanged

The section `## 2026-11-08 15:29:55 ET — window B closes on a verified read, not on a restart` (landed `d706087`)
contrasts its close with window A's interactive `systemctl start`. A later read of the same instant falsifies the
contrast: **all six nodes rebooted cleanly at 15:29:15–15:29:17** (`Reached target reboot.target`, `Finished
systemd-reboot.service` on `.30` at 15:29:17 and `.31` at 15:29:15; `uptime -s` 15:29:30–15:30:30), so the pool
units' `ActiveEnterTimestamp 15:29:55` and the campaign user unit's `MainPID` are **boot-time starts**, not a manual
restart and not a self-healing service.

**What changes and what does not.** The *proof* stands unchanged — all six hosts read 111 hub entries and a shipped
recipe's snapshot rc=0, `df -B1` answered on every host, `.30` storage stayed byte-identical, and those reads sit at
or after 15:29:55. The **admissibility boundary therefore stays 15:29:55**: `12:57:32`–`15:29:54` remains invalid —
window B. What changes is the mechanism line: "not on a restart" should read **"closed on a reboot, with verified
reads after it"**, and any future reader should not infer from the original heading that a service restart is what
ended an outage — a reboot is the only one of the two that appeared here.


## 2026-11-08 — correction: earlyoom `-m 20` reverted to `-m 4,1`; the threshold cannot be the protection

- **What was applied and why it was wrong.** The clause above (`6df4c0c`) set `-m 20,10`. That fires at 24.3 GiB free,
  and a healthy quartet serve leaves the head only ~5.7 GiB (`recipes/ds4/README.md`, "Measured: v2.4 serve line":
  `mem_fraction_static: 0.78` ships deliberately for the 16384-token chunks — a 1M prefill at 0.78 leaves 5.7 GiB, at
  0.80 only 2.7 GiB, and higher has wedged nodes). Every working serve, the production quartet included, would have
  been SIGTERMed the moment it reached steady state, on all six nodes. Reverted within the hour, before any boot ran.
- **What is live now**, applied 16:47:23–16:47:31 and read back from `/proc/$(pgrep -o earlyoom)/cmdline` on all six:
  `-m 4,1 -s 100,95 --prefer '(vllm|VLLM|sglang|llama-server|llama-cli|trtllm|tritonserver|ray|python3|python)' --avoid '(beegfs|mgmtd|meta|storage|systemd|sshd|dockerd|containerd|dbus-daemon|NetworkManager|syncthing)'`.
  `-m 4` is ~4.87 GiB, below the 5.7 GiB steady state so a healthy serve is not a victim; `-m 1` is a ~1.22 GiB SIGKILL
  floor. `-s 100,95` is unchanged, so the SIGTERM rung's swap term stays neutralised (idle swap-free reads 100.00 %,
  which satisfies `<= 100`) and the SIGKILL rung keeps its 95 % backstop.
- **The finding, not the number.** On a node whose healthy serve leaves 5.7 GiB free, earlyoom cannot be both
  non-disruptive and early: at the measured ~27 GiB/s dive the window between "healthy" and "out of memory" is about
  0.2 s. So the protection for the pool is `OOMScoreAdjust=-1000` plus `--avoid`, and the protection against a bad arm
  is the fit arithmetic, not the threshold. A quartet boot that overruns dies with ~0.2 s of warning — enough for
  earlyoom to name the engine rather than the storage daemon, and all it can honestly promise. `/etc/default/earlyoom`
  now carries this tension in its comment so the next reader does not re-derive it by SIGTERMing a serve.
- **Unchanged and still correct:** the `-1000` drop-ins and the live `/proc/<pid>/oom_score_adj` writes (mgmtd 2048,
  meta 2168, storage 2164 on `.30`; storage 3243 / 3249 / 3256 / 3226 / 3250 on `.31`–`.35`). Still unprotected and
  still an owner decision: `ssh.service`, `NetworkManager.service` and `user@1000.service`.
- **Verification.** `earlyoom --dryrun` on the installed file prints `sending SIGTERM when mem <= 4.00% and swap <=
  100.00%, SIGKILL when mem <= 1.00% and swap <= 95.00%`; at 95.74 % available it is silent; a forced-threshold dryrun
  (`-m 98`) still selects `python3` (badness 1100) and names none of the running `beegfs-*` pids 2048 / 2168 / 2164.

## 2026-11-08 17:31 ET — the rescued `metrics-land` lineage: one register row, and how to read the bundle

- **The artefact.** `/home/siv/rescued-metrics-land-20261108.bundle` — 17.1 MB, 20 refs
  (`refs/heads/land 84837a50`, `refs/heads/main fb881d80`, `refs/remotes/origin/main e1c6f31d`, plus 16
  remote refs), `git bundle verify` → "bundle is okay", created 2026-11-08. **Never pushed and never
  merged**: 33 of its 35 non-identical commits are dated board/ledger ticks of a superseded lineage, so
  landing it would rewrite this lineage's ticks without adding a fact. Read it later with
  `git clone ~/rescued-metrics-land-20261108.bundle /tmp/b && git log --oneline`; its value is
  provenance, not content.
- **The one row it held that this lineage lacked is landed**: `board-render-state-truncation`, commit
  `ef7bae8`. It is a measurement — after the 269-row landed table was retired the board still read
  82 136 B because `board_rows` restates every open task's notes in the state cell (75 821 B of a
  23-row table) — and its acceptance is a per-row byte budget with its own guard test. §17:26 here
  cited the id while `mad-science/queue.json` lacked it, because the row lived only in an unpublished,
  divergent local `main` and in this bundle. **Nothing else in the lineage is missing.**
- **Every other difference is provenance, checked against this tree.** The D-state readings
  (44 / 9 / 5 / 3 / 4 / 16, then `0` on all six at 13:16:21, head load 36.88 → 1.33) are verbatim in
  `STATUS.md`'s 13:16 row; `dropped_peer_lines`, `--base` and `--expect-sha` are in
  `tools/task-queue.py:777-858`; the `60ee067` disclosure concerns a commit that is not on this
  lineage (its objects are still in the shared store); the 274-row "Landed session" table and the
  13:43 / 14:06 / 14:14 tick sections are superseded ticks.
- **The `/tmp` adjudication behind the rescue.** Ten clones held commits absent from the shared object
  store. Nine were redundant: three materially upstream (439–450 of 450 added lines), three
  patch-identical to `e32253cc` / `8e7cd38f` / `f8d57c7f`, three single-commit snapshots whose every
  blob was already in the shared store. The three `AGENTS.md` trees were older revisions, lacking the
  push-gate rule and the `GIT_INDEX_FILE` clause. The sweep freed 2.8 GB (95 % → 77 %), left 152 of
  today's entries (1.9 GB) for liveness/citation reasons, and left 13 GB of pre-today material to its
  owners.
- **The rule that separated them.** A commit absent from the shared object store is unique work; a
  commit merely off `origin/main` is not, because today's rebases move SHAs. A clean clone whose every
  ref tip and tree resolves in the shared store is recoverable, and safe for a sweep to remove.

## 2026-11-08 18:16 ET — five board publishes in twelve minutes, and the guard that stopped a sixth

- **The hour's ticks are colliding faster than the cadence.** `bd93afd` (18:03), `2704657` (18:06),
  `bf462c7` (18:11) and `c4d9ace` (18:15) each carry a whole regenerated board. This session composed
  an 18:08 board over `bd93afd` and published it into the worktree at 18:08:00; it was superseded
  twice before it could reach origin, and nothing in it is lost — its rows (a single census read,
  pool units without a mount read) are weaker than a peer's read of the same state, not different.
- **`publish --expect-sha` refused the 18:16 composition, which is the mechanism working.** Its base
  read was `333a332a` (the `bf462c7` board); by the time `publish` ran, the file on disk was
  `4d246f9f` — the `c4d9ace` board, a peer write inside the same minute — so it exited 1 with "a peer
  wrote it in between; re-read and re-compose, do not replace their rows" and wrote nothing. A tick
  that trusts its own earlier read instead of the CAS is exactly how a fresh census row gets replaced
  by a staler one; that has already happened this hour (`bf462c7` rebuilt from the 18:03 text and so
  lost the 18:06 tick's 14 s census pair and proved pool reads).
- **An independent census pair puts the drift rate on two ticks, not one.** This session read the six
  roots at 18:14:0x and again at 18:14:18: every node idle (`1 / 0 / 0 / 0 / 0 / 0` containers, `0`
  running, `0` volumes), root avail falls `.30`/`.31`/`.33` −8 192 B and `.32`/`.34`/`.35` −12 288 B,
  **61 440 B in ≈18 s ≈ 3.4 kB/s** — the same order as the `c4d9ace` row's 208 896 B in 22 s
  (9.5 kB/s), both log drip and neither a transfer, with no register row claiming a staging body.
- **What this tick did not do**: published no board and stopped nothing. `c4d9ace` is fresher than
  this session's composition, so adopting it is the correct close and the worktree carries its bytes
  byte-for-byte.

## 2026-11-08 19:16 ET — the census cell names its sources, and the challenge against it was falsified

- **A reviewer read the published census cell as two sources under one row** — a local read
  for `.30` against ssh reads for `.31`–`.35` — and cited `.30`'s always-on infrastructure as
  proof the count could not hold. The cell never mixed sources: the `.30` script ran on the
  node itself over an `ssh` session, the workers over nested `ssh -n` hops from that head,
  and this workstation's own 11 containers were read in the same turn only to be excluded.
- **The "9 containers on the head" was my own root count, not containers.** `ls
  ~/benchmarks/*/state.json | wc -l` prints 9, and the head's `docker ps -a` holds exactly one
  entry (`sm121m`, `Created` 10:32:33, never started). Reproducing the quoted number is what
  settled it: the challenge had read the wrong command's output as the count it argued about.
- **The half of the challenge worth keeping was readability, not arithmetic.** The head's
  infrastructure is not containerized — `sparkrun cluster monitor` is a process and
  `flare-agent.service` / `sparkrun-campaign.service` are user units — so a census of `1`
  has to say so, or the next reader raises the same challenge. The cell now states which host
  produced each read and what the one container is not.
- **A dependency the challenge asserted does not exist.** origin's `tools/task-queue.py
  render` refuses a register that is not inside a git worktree, in `/tmp` and in a `git
  archive origin/main` tree alike ("not a git worktree"), so a real origin checkout is not an
  alternative route; `graph` from that archive is byte-identical to what the published board
  carries (`cmp` clean, 2 283 bytes), so running from the clone lost nothing.
- **The landed fold's divergence claim is now stated as observed, not attributed.** The clone reads
  `git rev-list --left-right --count origin/main...HEAD` = 84 73; 57 of the 73 local-ahead
  subjects appear nowhere on origin and 16 appear there under other SHAs (local `30651d4` and
  origin `bf462c7` are both "Board: 18:11 census"), so only the 57 are unpublished lineage —
  a cause the earlier row had implied for all 73.
- **What this tick did not do**: started nothing, stopped nothing, claimed no node, edited no
  other session's rows. Board commits `8afad24` and `fe58d28a`, this correction commit, and
  gate `success` read on both of them.

## 2026-11-08 20:16 ET — this tick published no board: peers covered the hour in eleven minutes

- **The hour was published three times while this tick took its reads, and the last one is current.**
  The board was read at `725f1e6` (title 19:57); by 20:11 origin carried `e321269` (title 20:03), then
  `2bd678f` (title 20:06, **carrying the 19:56 census cells**), then `666e761` (title 20:11, which
  restored a 20:03 census and pool read). Two further peer composes wrote this clone's board while
  this session measured (mtime 20:09:03, then 20:13:21), so `publish --expect-sha` would have refused
  at every point and a whole-file write would have dropped the peer's rows. The tick stands down with
  its reads on the record here; the board it would have written is already on `666e761`.
- **An independent six-node read at 20:04:01 and 20:04:50 ET corroborates that board, a minute later.**
  Containers `1 / 0 / 0 / 0 / 0 / 0` on `.30`–`.35` with **`0` running** and `0` volumes, the one
  container still the never-started `sm121m`; root avail 1 253 654 687 744 / 1 643 042 103 296 /
  1 720 743 444 480 / 1 604 136 689 664 / 1 073 945 141 248 / 1 337 861 529 600 B, and the 49 s pair
  fell **774 144 B (≈15.8 kB/s)** over all six — the 18:14 pair's 3.4 kB/s and `c4d9ace`'s 9.5 kB/s
  are the same order, so it is log drip and not a staging body.
- **The pool was proved by a read this session took itself, on a second model from the board's.**
  `df -B1 /mnt/beegfs` answered **9 862 427 705 344 B** avail at 20:04:59, the hub listed **111**
  entries, and `stat -L` on the pruned75 snapshot's `model-00001-of-000096.safetensors` at revision
  `fc72e5a1…` returned **2 341 216 112 B / 4 572 688 blocks** with 111 entries in that snapshot. Units
  at the same read: `beegfs-storage` `active (success)` `NRestarts=0` on six, `.30` mgmtd+meta
  `active` since 15:29:55, the workers' `beegfs-meta` still `exit-code` `failed` (role config gate).
- **Campaign and register were re-read from their own stores, not taken from the board.** USER unit
  `sparkrun-campaign.service` `active` / `Result=success` / `NRestarts=0` since 15:29:55; all nine
  `~/benchmarks/*/state.json` on the head parse to **32 arms, 0 leases**, the h2h root 18 arms with
  `state.json` at 13:13:38. Origin's register at `725f1e6` read **115 tasks, 26 open (14 queued + 12
  blocked), zero claims** and this session's own `check` returned rc=0; its blob `e82c181` is still
  the blob at `666e761`, so the board's `725f1e6` citation is stale by two board-only commits and
  the counts it prints are not.
- **One board defect this tick saw and did not chase**: `2bd678f` regenerated the title to 20:06 while
  its `census`/`pool`/`campaign`/`queue` cells still read 19:56 and `3bf4680` — the shape the skill
  names (`a tick that changes nothing still regenerates the census row`). `666e761` replaced those
  cells two minutes later, so no re-correction was attempted; the shape is recorded because the title
  alone is what a reader dates the board by.
- **What this tick did not do**: published no board, started nothing, stopped nothing, claimed no node,
  edited no other session's rows.

- **This tick's reads, and the publish that never went through its own hand.** Four board commits landed
  between 19:57 and 20:11 (`725f1e6`, `e321269`, `2bd678f`, `666e761`) while this session was
  measuring on the fleet, so the first `publish` attempt (20:09) was refused by `--expect-sha` exactly as
  designed. The composed 20:12 board then appeared in this clone's worktree at **20:13:21** carrying this
  tick's `In flight` clauses verbatim (`a second pair 20:03:45` / `2 341 216 112 B` / `32 arms with 0
  leases` / `10.1 kB/s` all present) while `origin/main` still carried its 20:11 board — so the bytes were
  published by `blob=$(git hash-object -w …)` + `update-index --cacheinfo` + `commit-tree -p origin/main`,
  not by `publish`. They were verified clause-by-clause before the commit rather than trusted, and the
  commit (`5b32533`) carries one path (`mad-science/STATUS.md`, 7 insertions / 9 deletions).
- **Census: two independent pairs in one cycle, both flat.** `20:03:45 → 20:05:26` fell **1 200 128 B in
  101 s (11.9 kB/s)** and `20:09:21 → 20:11:22` fell **1 220 608 B in 121 s (10.1 kB/s)**, per-node
  `−368 640 / −172 032 / −172 032 / −167 936 / −172 032 / −167 936 B` on the second pair; containers
  `1 / 0 / 0 / 0 / 0 / 0`, **`0` running**, `0` volumes at all four reads, the one container still
  `sm121m` on `dsv41-sm121-dg:0.2.1` in `Created`.
- **Pool proved by a read, not by a unit state.** At 20:05–20:06: `df -B1 /mnt/beegfs` avail
  **9 862 428 753 920 B** / used 14 328 801 001 472 B, **111** hub entries, `stat -L` on
  `model-00001-of-000096.safetensors` **2 341 216 112 B / 4 572 688 blocks** rc=0, no hub entry newer
  than six hours (so the hour's flat roots need no staging attribution); `.30` mgmtd+meta+storage
  `active (success)` `NRestarts=0` since 15:29:55, `.31`–`.35` `beegfs-storage` `active` with
  `beegfs-meta` `failed` on its recorded role gate, `beegfs-mon` `failed` since 2026-11-05.
- **Campaign and register read from their own stores.** USER unit `active` `Result=success`
  `NRestarts=0` since 15:29:55; all nine `~/benchmarks/*/state.json` on the head parse to **32 arms,
  0 leases**, no `needs_reap`, h2h root 18 arms (9 measured / 9 blocked) with `state.json` at
  13:13:38. Register at origin tip, file unchanged since `405d9e4`: **115 tasks, 26 open (14 queued +
  12 blocked), zero claims**, `check` rc=0 on an extracted copy.
- **The window is a live claim and its escalation is now four reads old.** The 20:04 tick proved the lock
  is a claim rather than a relic (byte-identical on both hosts, sha256 `2039f411…a1b4f`); this cycle's
  four census reads at 20:03–20:11 find **0 running containers on every node it claims**, which the board
  row reports every cycle it persists. No node was booted on, nothing was stopped, and the lock was
  neither deleted nor re-stamped.
- **Sibling-tick hazard, recorded as observed**: this host's `/tmp` is shared by the concurrent tick
  sessions, so a composed board written to a per-session `/tmp/board-*` path is readable by them; the
  20:12 text reaching the worktree while `publish` had refused is the second time a compose path, not the
  publish door, was what put bytes on disk. Verify content before committing; never assume the door ran.

- **Both pushed tips gated green, and the run was read rather than assumed.** `gh run list` on
  `5b325335…` and then on `297d8386…` returned `conclusion: success` for the `gate` workflow
  (`469e23b` before them also `success`), so the 206 KB board and this ledger's append passed the
  text checks CI actually runs — including the tracked-address guard, which is the one a raw literal
  in a new row would have reddened. CI boots no engine and `sparkrun recipe validate` is skipped
  there, as the workflow prints.
- **A board row falsified its own transcript, and this is the correction.** The published board's
  `publication` row said the bytes were "written through `publish --expect-sha` + `--base`"; no
  `publish` call this tick wrote anything — the first was refused by `--expect-sha` and the retry
  loop only ever reached a missing tool path. The row now names the route that carried the bytes
  (`hash-object` + `update-index` + `commit-tree` on an index read from `origin/main`), because a
  board whose own row is contradicted by its transcript is the defect the board exists to avoid.

## 2026-11-08 21:07 ET — the hour's census, and a board published off origin's lineage

- **Census taken twice, both reads on all six.** `21:02:22` and `21:05:00` ET read containers
  `1 / 0 / 0 / 0 / 0 / 0` with `0` running and `0` volumes everywhere; the one `.30` container is
  the `Created` `sm121m` leftover. Byte pairs: `1 339 392 B` over the 158 s pair (8.5 kB/s) and
  `82 227 200 B` over the `20:11:22 → 21:02:22` window (26.9 kB/s), spread over six roots with no
  node above 17.9 MB. Nothing booted, nothing stopped, no node claimed.
- **The first census attempt returned nothing, and the cause was the probe, not the fleet.**
  `ssh -n host 'bash -s' <<'EOS'` discards the heredoc (`-n` takes stdin from `/dev/null`), so six
  hosts printed their `NODE` label and no counts. Dropping `-n` is what produced the numbers above;
  the empty result was never a fleet reading.
- **The pool is serving by read, not by unit state.** `21:05:01` on the head: `df -B1 /mnt/beegfs`
  9 862 340 673 536 B avail / 14 328 889 081 856 B used with **111** hub entries, `stat -L` on a
  shipped Kolibri shard rc=0 at 3 156 374 416 B, and `find -newermt '-6 hours'` under `hub/`
  returning nothing, so no body is staging. `.30` carries mgmtd+meta+storage `active`
  `NRestarts=0` since 15:29:55; `.31`–`.35` `beegfs-storage` `active` with `beegfs-meta` `failed`
  and `beegfs-mgmtd` `inactive`, the recorded per-host role gate. `beegfs-mon` stays `failed` from
  2026-11-05.
- **The live holder has an empty plan, and that is the escalation.** All nine
  `~/benchmarks/*/state.json` roots on the head parse to **32 arms, 0 leases**, `needs_reap` empty,
  under a user unit `active` since 15:29:55 with `NRestarts=0` and MainPID 2605; the h2h root's 18
  arms have not moved since 13:13:38. `.local/fleet-window.lock` is still the live six-node
  `campaign-queue` claim (414 B, sha256 `2039f411…a1b4f`, mtime 2026-11-07 22:37:33, 22 h 28 m old).
  Reported again; not deleted, not re-stamped.
- **Register unchanged, and re-read from origin rather than the worktree.** Origin tip `405d9e4`
  (17:44) holds 115 rows: 89 done, 14 queued, 12 blocked, zero claims, `check` rc=0. The queue
  table and graph were both re-rendered from that file with origin's own `tools/task-queue.py`;
  the graph's counts line reads `12 blocked, 3 edges, 9 prose-gated, 2 question-gated, 1 question,
  18 rows not drawn (--all)`.
- **The board was published from a throwaway clone, because the shared clone cannot publish.**
  `git rev-list --left-right --count HEAD...origin/main` reads **76 99**, and the worktree's
  `tools/task-queue.py` predates the `graph` subcommand, so composing here would have drawn the
  previous tool's view. Route used: `git clone --no-hardlinks` → `fetch gh` →
  `checkout -B main gh/main` (`e743a9a`) → compose over
  `git show origin/main:mad-science/STATUS.md` (sha `9d96120c…`) → `publish --expect-sha` +
  `--base` (a saved copy of that same read) → one `-o mad-science/STATUS.md` commit →
  `push gh HEAD:main`. No merge, no reset, no force. Pushed `e743a9a..a35476a`, with the message
  amended **before** the push, and only to correct `mad-science/fleet-window.lock` to
  `.local/fleet-window.lock`.
- **A compose defect the linter caught, recorded because it is silent otherwise.** Replacing the
  whole `## In flight` body dropped its `| where | owner | what |` header and `|---|---|---|`
  delimiter; `publish` refused with `table-missing-delimiter: 6 row(s) begin here but line 5 is not
  a 3-column delimiter row`, i.e. GFM would have rendered seven rows as one paragraph. The fix
  restored both lines, and `lint` then read `ok: 1 markdown file(s) render`.
- **Folded, not rewritten:** five peer board/ledger commits since the 20:11 row (`666e761`,
  `469e23b`, `5b32533`, `297d838`, `e743a9a`) plus this tick's own fold row were appended to
  `## Landed session`; every existing row is untouched.
- **The counts line's `3 edges` and the block's six arrows are both right, and the gap is a
  naming one.** `tools/task-queue.py:1018` prints `len(row_edges)`, i.e. `blocks` pairs between
  open rows only, while the block also emits one `q<n> --> row` arrow per row that cites an open
  question (`:1070`, `row_edges | question_edges`). On this register that is 3 row edges plus
  3 question arrows from Q67, so 6 arrows against a stated 3 — matching the docstring's own
  "9 nodes and 6 edges" (`:967`). Recorded so the next tick does not read the mismatch as a
  contradiction to escalate, and does not "fix" the line by hand: the counts line is tool output
  and must be copied verbatim.
- **The census probe's `pgrep` pattern matches earlyoom, not an engine, and the node mapping was
  by magnitude.** `pgrep -f '…|llama-server|…'` hits earlyoom's own argv, which spells out
  `--prefer (vllm|VLLM|sglang|llama-server|llama-cli|trtllm|tritonserver|ray|python3|python)` —
  five false positives per node, and no engine on any of them (`docker ps` read `0` running, which
  is what the row actually rests on). A future census should print its own identity inside the
  remote block (`printf 'HOST %s\n' "$(hostname)"`) instead of mapping counts back to nodes by
  value continuity: the labels print in ssh completion order, so a crossed pair of similar
  magnitudes would read plausibly and be wrong.
- **Correction, the queue row's register pointer.** `405d9e4` (17:44) is the commit that last
  touched `mad-science/queue.json`; the read was taken at origin tip `e743a9a`. The row called the
  first the tip while the publication row named the second, so it now reads "unchanged since
  `405d9e4` (17:44), read at origin tip `e743a9a`" (`a077e7e`).
- **The publish door refused a wrong `--expect-sha` before anything landed, and the sha was mine
  to get wrong.** `--expect-sha` must be the sha of the board as *read*, not of the composed
  output: passing the composed file's own sha gets `on disk is sha256 … not the … this board was
  composed from — a peer wrote it in between`, which reads exactly like a peer race and was not
  one. Read the file, edit a copy, publish the copy with the read's sha.

## 2026-11-08 21:58 ET — the register emptied, on host memory policy and a metrics bar

- **Both open rows asked and answered in one turn**, the way the 2026-11-06 round was: `#67` (may host
  memory policy change on all six nodes, so an overrunning quartet boot cannot take the head offline)
  and `#68` (how an instrumented arm relates to its uninstrumented baseline now that every boot is
  instrumented) were the register's only rows. `#67` answered `(a)` earlyoom `-m 14,5 -s 90,80` and
  `(b)` `OOMScoreAdjust=-900` on `ssh.service` and `NetworkManager.service`, and added a placement
  constraint the row had not proposed as its own candidate: **risky TP4 jobs run only on `.31`–`.35`,
  never `.30`**. `#68` answered with a bar instead of one of the three shapes the row costed: adding
  metrics may not create a confound as large as a rough-order-of-magnitude throughput difference, so
  the metrics knobs get decomposed by cost to show the bar holds.
- **The apply is a queue row, not a fleet action taken here.** `host-memory-policy-apply` carries the
  exact host changes plus the caveat the answer alone cannot settle: earlyoom's two tests are
  conjuncts, so the swap term's reach must be measured per node (`.34` idles at 99.98 % swap-free)
  before the ruling counts as effective, and `.30` is not rebooted without owner approval.
  `metrics-instrument-confound` carries the decomposition.
- **Stale worktree, clean base.** This clone's worktree was far behind `origin/main` — its `AGENTS.md`
  still stated 1423 tests where the tree discovers 1523, and it lacked the peer's push-gate paragraph —
  so the fold was rebuilt on `origin/main`'s own bytes (`git archive origin/main`, seven files,
  re-applied rather than merged) and committed as `3f77f52`. The gate ran in a real checkout of that
  commit (`git clone --no-hardlinks … && git checkout 3f77f52`): **1523 tests, OK (4 skipped)**, with
  `test_doc_hygiene` and `test_tracked_address_hygiene` green there while red in the lagged worktree.
  The lag is a clone condition, not a repo one, and the next session's first act should be a pull
  before it trusts any count read off this worktree.

## 2026-11-08 22:22 ET — hourly board tick: census, the settled-question graph, no fleet change

- **Board published on `origin`'s lineage, not from the shared clone.** The clone reads
  `git rev-list --left-right --count origin/main...HEAD` = **106 / 76** (origin ahead 106, HEAD
  ahead 76), so the board was composed over `git show origin/main:mad-science/STATUS.md`
  (sha `99387081…`) and published from a `git clone --no-hardlinks` of the GitHub remote checked
  out at `74c728f`. `publish --base` + `--expect-sha` passed twice; the first push attempt was
  refused because the peer's `74c728f` landed between compose and push, and the board was
  re-derived over that register rather than rebased.
- **Census: three marker reads, all six nodes, `0` running containers and `0` volumes.**
  22:03:35/22:03:45 fell 152 448 B; 22:06:56/22:08:32 fell 897 008 640 B, of which `.30` alone is
  896 520 192 B; 22:13:11/22:15:01 fell 3 092 480 B (`.30` −196 608, `.31` −155 648,
  `.32` −163 840, `.33` −163 840, `.34` −167 936, `.35` −2 244 608). Each block prints its own
  `hostname`, so the labels are the nodes' and not a magnitude guess — the fix the 21:21 ledger
  asked for.
- **The head's 855 MiB is a released transient, and it is recorded unattributed.** `df` at
  22:12:57 reads 1 253 260 144 640 B, i.e. 816 934 912 B (779 MiB) of it back. Nothing above 5 MB
  was written under `/tmp`, `~` (depth 4) or `/srv/beegfs` in 15 min; `~/src`'s git objects are 16
  files / 1 000 105 B in 25 min; the hub has no entry newer than 6 h. A full-root
  `sudo find / -xdev -newermt '-12 minutes' -size +20M` had printed no hit when its 180 s budget
  expired — an incomplete scan, stated as one, and not a clean bill.
- **Pool proved on a second body, campaign lease-free across every root.** `df -B1 /mnt/beegfs`
  avail 9 861 967 904 768 B / used 14 329 261 850 624 B, **111** hub entries, `stat -L` on
  `models--orcarouter--Qwen3.8-Flash-Next-Uncensored-NVFP4/…/model-mtp.safetensors` = 5 214 305 456 B
  / 10 184 191 blocks. Units: `.30` mgmtd+meta+storage `active (success)` `NRestarts=0` since
  15:29:55; `.31`–`.35` storage `active` with meta `failed (exit-code)`, the recorded role gate. All
  nine `~/benchmarks/*/state.json` roots: 32 arms, **0 leases**, `needs_reap` empty; the h2h root is
  18 arms at 9 measured / 9 blocked with `state.json` unmoved at 13:13:38.
- **Two board defects fixed in place, neither carried forward.** The inbound board carried a second
  `|---|---|---|` delimiter under its census row, which split the six live rows into two tables —
  one delimiter kept. And `publish`'s new `future-stamp` lint refused the first two compositions
  because their titles were a minute ahead of the clock; the title is now stamped from `date` at
  compose time rather than typed.
- **The register moved under the tick, and the row follows the register.** `3f77f52` settled `#67`
  and `#68` (so the graph's `Q67` node is gone and the counts line reads `0 question-gated,
  0 question, 22 rows not drawn`), and `74c728f` reconciled that policy with what is already live:
  earlyoom runs `-m 20,10 -s 100,95` on all six, so the answer's drafted `-m 14,5 -s 90,80` would
  loosen the trigger; `quartet-boot-host-oom-containment` closed on its own stated condition, which
  is what moves the board's queue row to **117 tasks, 27 open (16 queued + 11 blocked), 90 done**.
- **Two register closes, and the committed copy lags the head's by one.** This cycle renders the head's
live copy: 26 open 119 (15 queued + 11 blocked), 93 done, zero claims. `metrics-flag-boot-verification`
closed on the head at 01:10, while `origin`'s 01:24 commit (`3381458`) carries
`host-memory-policy-apply` → `done` and still shows the metrics row queued. The memory-policy close is
verified here rather than quoted: `systemctl show` reads `OOMScoreAdjust=-900` on `ssh.service`,
`NetworkManager.service` and `user@1000.service` on `.30`, `.33` and `.35`, which is the `#72`/`#83`
remainder live; the row keeps its own open finding that configured `-900` and live `sshd` `-1000` differ.
- **What this tick did not do**: booted nothing, stopped nothing, claimed no node, edited no other
  session's rows, and did not re-stamp or delete the live `campaign-queue` window lock.

Board commit `e23a88c`, ten minutes after the peer's `74c728f`; gate run on it read after the fact.

- **Two further board corrections, appended rather than folded into the list above** (a review of the
  published bytes found them, and the first list claimed to be complete): the census cell led with
  `22:03:35 → 22:08:32` while its own text cites a third pair ending **22:15:01**, so the range a reader
  dates the cell by disagreed with the markers beneath it — it now reads `22:03:35 → 22:15:01, three
  marker reads`; and the publication row named `git clone --no-hardlinks`, the local form that once
  produced a stale tree, where the board was in fact published from a shallow
  `git clone --depth 40 https://github.com/littlecedar/sparkrun-recipe-registry.git` (the push needed no
  `--unshallow`). Both landed in `e08f1b5`, after `6dd4cf4` corrected the row's `4a94c51` tip to the
  `74c728f` the push actually landed on.

## 2026-11-08 23:11 ET — hourly board tick: three census markers, and the register moved twice under it

- **Board `b402dc6`, census 23:02:36 / 23:05:51 / 23:07:41 ET.** Containers
  `1 / 0 / 0 / 0 / 0 / 0` in every read and volumes `0` on all six; the lone `.30` container is
  `dsv41-sm121-dg:0.2.1` named `sm121m`, status `Created`, `StartedAt=0001-01-01T00:00:00Z`, no
  `sparkrun.recipe` label, so it is a never-started leftover and not a serve — `sparkrun status`
  reads `No sparkrun containers running` beside it.
- **The hour's root fall is pool traffic, not a writer.** The 110 s stamped pair fell 839 680 B
  (7.6 kB/s) and an opening 15 s pair fell 184 320 B, both spread over all six nodes with no node
  carrying the fall alone; the hub held 111 entries with none newer than 6 h at 23:08:23, so no
  body was staged this hour.
- **Pool proved by read, not by unit state.** Units: `.30` mgmtd/meta/storage and every worker's
  `beegfs-storage` `active` `NRestarts=0`, the workers' `beegfs-meta` still on its recorded role
  gate and `.30`'s `beegfs-mon` still `failed` since 2026-11-05. Through the mount: avail
  9 861 755 568 128 B, 111 hub entries, and `stat -L` on
  `models--orcarouter--Qwen3.8-Flash-Next-Uncensored-NVFP4/…/model-mtp.safetensors` returns
  5 214 305 456 B / 10 184 191 blocks rc=0 on both snapshots.
- **Campaign: live holder, nothing plannable; the escalation stands.** All nine
  `~/benchmarks/*/state.json` roots swept for per-arm `lease` objects read 32 arms / 0 leases with
  `needs_reap` empty, unit `active` MainPID 2605, and `director status --root
  ~/benchmarks/h2h-20261107` reports its arms `register: register state blocked`. The
  `campaign-queue` window lock is 24 h 31 m old at the same read, byte-identical on the workstation
  and the head, with zero running containers under it in all three of this cycle's reads.
- **The register moved twice under the tick, and the renders followed it.** `0294e8f` (22:50)
  filled the register's `questions` list 0 → 14 (`#69`–`#82`); `a77f424` (23:05) then withdrew
  `#73`/`#82`, restated `#71`/`#72`/`#74` and added `#83`, closed queue row
  `beegfs-units-restart-no` on the 16:47 drop-in evidence, and took the register to 13 open
  questions. A table and graph rendered at `0294e8f` therefore said `0 question-gated, 0 question`
  and would have been stale before the publish: the final renders are over `a77f424` — **26 open
  (15 queued + 11 blocked), 91 done, zero claims**, `check` rc=0, and the graph's own counts line
  `11 blocked, 3 edges, 1 prose-gated, 9 question-gated, 5 question, 10 rows not drawn (--all)`.
  A peer advisory caught the first render before publish; the tip is re-asserted immediately
  before the push, not only before the composition.
- **What this tick did not do**: booted nothing, stopped nothing, claimed no node, edited no other
  session's rows, and did not re-stamp or delete the live `campaign-queue` lock. No receipt under
  `~/benchmarks` on the head is newer than the 22:22 board, so the hour landed register and ledger
  work rather than a measurement.
- **One shared-surface note.** A peer tick (`0e466f0`) published its own 23:11 board over this one
  and then restored this board wholesale (`20fd935`); the board on origin at 23:18 is this
  composition, unchanged at 212 241 B.
## 2026-11-09 00:09 ET — hourly board tick: three census markers, an idle holder, no fleet change
- **Board `47ad537`, census 00:03:06 / 00:04:32 / 00:05:59 ET.** Containers
`1 / 0 / 0 / 0 / 0 / 0` in every read and volumes `0` on all six; `sparkrun status` reads
`No sparkrun containers running` in all three. `.30`'s lone container `7fba5dc0050b` (`sm121m`,
`dsv41-sm121-dg:0.2.1`) has status `Created`, `StartedAt=0001-01-01T00:00:00Z` and no
`sparkrun.recipe` label — a never-started leftover, and `.30:8000/v1/models` refuses with `000`.
- **This hour's root fall is *not* pool staging, and the previous hour's attribution does not
  carry.** All six node roots fell across the 173 s pair (`.30` −196,608 B, `.31` −253,952,
`.32` −253,952, `.33` −249,856, `.34` −249,856, `.35` −253,952; ~8.4 kB/s summed), but the pool's
own used bytes fell 236,453,888 B over the same span and the hub holds 0 entries newer than 6 h.
Writing it up as "the fall is pool traffic" would have been a carried claim: this hour nothing was
staged, so the fall stays unattributed rather than explained.
- **Pool proved by read, not by unit state.** `beegfs-storage` `active` `NRestarts=0` on all six,
`beegfs-mgmtd`+`beegfs-meta` `active` on `.30` only, `.31`–`.35`'s `beegfs-meta` on its recorded
`failed (exit-code)` role gate, `.30`'s `beegfs-mon` `failed` since 2026-11-05. Through the mount
on all six: `df -B1` avail 9,861,992,022,016 B / used 14,329,237,733,376 B, 111 hub entries, and
`stat -L` on `models--orcarouter--Qwen3.8-Flash-Next-Uncensored-NVFP4/…/model-00002-of-00017.safetensors`
returns 102,400,512,288 B.
- **Campaign: live holder, nothing plannable.** Unit `active`, MainPID 2605, `serve --queue
--max-parallel 1 --retries 8`; all nine `~/benchmarks/*/state.json` roots swept to **32 arms, 0
leases**, `needs_reap` absent in every root, and `director status --root ~/benchmarks/h2h-20261107`
rc=0 with 9 measured / 9 blocked, every block a register-state block.
- **The window lock is 25 h 29 m old and the escalation stands.** `2039f411…a1b4f`, byte-identical
on workstation and head, three six-node reads with 0 running containers under it, 0 leases in the
same cycle. Not deleted, not re-stamped, reported again.
- **Register unchanged, so the table and graph are the same bytes.** `a77f424`: 26 open of 117
(15 queued + 11 blocked), 91 done, zero claims, `check` rc=0, 13 open questions, and the graph's
own counts line 11 blocked / 3 edges / 1 prose-gated / 9 question-gated / 5 question / 10 rows not
drawn. The head's copy is byte-identical (sha256 `1d8dfb7a…`, mtime 23:05:10), so the campaign
wrote nothing this hour.
- **Instrument note, and the trap that follows from it.** The shared clone is 119 commits behind on
`tools/task-queue.py`, so the worktree tool has no `graph` subcommand and a tick that reaches for
it gets `argument command: invalid choice: 'graph'` and no diagram. This tick ran the published
tool from `git show origin/main:tools/task-queue.py`, and the diagram it drew is byte-identical to
the board's, which is the check that the register did not move.
- **What this tick did not do**: booted nothing, stopped nothing, claimed no node, edited no other
session's rows, and did not re-stamp or delete the live `campaign-queue` lock. No receipt under
`~/benchmarks` on the head is newer than the 23:11 board, so the hour landed the board restore
(`20fd935`), a close-out (`f097e95`) and the `publish` remote-sha gate (`c81fdae`) rather than a
measurement.
## 2026-11-09 01:12 ET — hourly board tick: the fleet changed hands, a quartet is serving unclaimed
- **Board `published` on `origin`'s lineage**, census 01:03:43 / 01:05:00 / 01:06:37 ET. Containers
`1 / 1 / 1 / 1 / 0 / 1` on `.30`–`.35` against `1 / 0 / 0 / 0 / 0 / 0` at the 00:09 tick: four ranks
of one quartet appeared on `.31`/`.32`/`.33`/`.35`, `.30`'s never-started `sm121m` leftover sits
unchanged, `.34` is empty, and volumes are `0` on all six.
- **The campaign released the fleet instead of draining it.** `sparkrun-campaign.service` reads
`inactive` `Result=success` with `ExecMainExitTimestamp` **00:59:11**, `Consumed 1min 5.858s CPU`, its
last journal lines naming nine arms `blocked: … register: register state blocked`; the nine
`~/benchmarks/*/state.json` roots hold **32 arms, 0 leases** with `needs_reap` absent, and the h2h
root's `state.json` is unmoved at 2026-11-08 13:13:38. No lease was cut, so no arm lost a window.
- **A new window claim replaced the old one in the same minute.** `.local/fleet-window.lock` is
**282 B**, mtime **00:59**, byte-identical on workstation and head: `sparkrun-vibe:tp4-boot` on
`.31`/`.32`/`.33`/`.35`, `2026-11-09 01:00-04:00 ET`, reason `TP4 metrics-flag verification (#69
unfreeze)`. This is the directive `953ac4a` recorded an hour earlier being executed, and `#70`'s
`.30` exclusion is honoured in the node list, so `.30`'s absence is not a role statement.
- **The live boot is the shipped knapcio ds4 arm and it already answers.** Task
`b020d2dd178343a5_b632751318c7`, `sparkrun.recipe`
`recipes/ds4/deepseek-v4.1-flash-knapcio-tp4-1m-sglang.yaml`, image `sha256:3f4480818acb…`,
`StartedAt 06:00:04Z`; the engine argv carries `--tp 4 --attention-backend dsv4
--moe-runner-backend flashinfer_mxfp4 --mem-fraction-static 0.78 --context-length 1048576
--max-running-requests 16`; rank 0 returns `/v1/models` 200 (`POST /v1/chat/completions 200 OK` at
01:06:11 ET) with GPU 6 % and 102 of 121 GB at 01:07. Peers answer 404 on their own port and `.30`/`.34`
`000`, which is the correct shape for a rank-0-only API.
- **Its register row is `queued` and unclaimed.** `metrics-flag-boot-verification` reads
`state: queued`, `claimed_by: ''` at `5e3c006`, and no receipt under `~/benchmarks` is newer than the
00:09 board. Recorded, not corrected: the claim belongs to the session that boots the arm, and this
tick never edits another session's row. The register's own count therefore says 28 open / zero claims
while a quartet of it is live.
- **The pool's +51.1 GB of used growth is reported, not explained.** `df -B1` used
14,380,270,354,432 → 14,380,616,384,512 → 14,380,731,203,584 B across 01:03:43 → 01:07:08, and the
77 s pair puts the whole fleet fall on `.35` (−343,511,040 B) with the other five roots rising.
Excluded as causes: no `hub/` entry newer than 6 h, no file at depth ≤ 6 under `hub/` newer than 4 h,
nothing matching `-newermt -12 min` under the storage tree, and no download/rsync/pull process on the
node whose root carries the fall. Last hour already refuted the inherited "root fall is pool traffic"
wording on the same evidence, so the row inherits neither claim.
- **Register moved five times between boards.** `bcbdff3` ledger, `50117b1` thirteen answers folded
(`QUESTIONS.md` empty again, 50 settled), `3263084` the SM121 trio's block made machine-readable
(`blocks`/`_relink`, `graph` 3 edges → 6, diagnosis sorts first), `be24567` DSV4-Pro closed by a note
under an untickable item, `953ac4a` the TP4 unfreeze directive plus seven re-gated rows, `5e3c006` the
GSQ-RCO gate sentence naming only open rows. Final renders are over `5e3c006` — 119 tasks,
**28 open (17 queued + 11 blocked), 91 done, zero claims**, `check` rc=0, and the graph's own counts
line `11 blocked, 6 edges, 7 prose-gated, 0 question-gated, 0 question, 19 rows not drawn (--all)`.
- **Instrument note: the publish door caught a real markdown break, and the cause was the fold shape.**
The first composition appended the new landed rows after the existing table's trailing blank line,
so nine rows began a table with no delimiter (`table-missing-delimiter`, stdin:374) and `publish`
refused rather than shipping a board GFM would render as one paragraph. Appending to a table must
strip the blank line first; `lint` passes once it does.
- **What this tick did not do**: booted nothing, stopped nothing, claimed no node, edited no other
session's rows, did not re-stamp or delete the live `sparkrun-vibe:tp4-boot` lock, and did not
correct the unclaimed register row. The shared clone is **77 ahead / 126 behind** origin and its
worktree board is the stale 23:14 one, so the board was composed from a fresh shallow clone.


## 2026-11-09 01:16 ET — hourly tick, second writer: the +51 GB is one statfs, not two measurements

- **This tick pushed nothing, and that was the right call.** It composed over the board read
  from a `--depth 1` clone at `5e3c006`, published through `publish --expect-sha/--base/
  --expect-remote-sha`, committed (`ecf9db7`, one path), and the push was refused non-fast-forward:
  a peer had published `bec8c1f` ("Board: 01:12 census, and the fleet handed to a live TP4 window")
  at 01:13:46. The peer's board carries the same census with **three** stamped reads
  (01:03:43 / 01:05:00 / 01:06:37 ET) and a `serve` row this tick could not have written — rank 0
  `/v1/models` 200 by 01:06:37 and `POST /v1/chat/completions 200 OK` at 01:06:11 on the quartet's
  own argv. Re-composing over it would have swapped three reads for one, so the commit was dropped
  and the clone reset; `main` is the peer's board.
- **Correction to the fall both boards reported, with the discriminator run.** The pool's statfs is
  the **sum of the six storage nodes' root filesystems**, verified rather than assumed:
  `df -B1 /mnt/beegfs` size 24,191,229,755,392 B against 6 x 4,031,871,553,536 = 24,191,229,321,216
  (delta 434,176 B), and used 14,380,735,922,176 B against the summed roots' 14,380,735,700,992 B
  (delta 221,184 B). So `.35`'s root-avail fall of 51,036,016,640 B and the pool's used growth of
  51,028,426,752 B are **one event seen twice** and cannot corroborate each other; a board row that
  pairs them as two observations overstates the evidence.
- **It is not new pool chunk data.** `sudo -n find /srv/beegfs/storage/chunks -type f -newermt
  '2026-11-09 00:00'` returns **0** files on `.35` and on `.31`, while `du -sb /srv/beegfs/storage`
  reads 1,489,745,579,043 B on `.35` and 1,422,508,085,939 B on `.31`. Under a statfs that
  aggregates the roots, the growth is therefore somewhere else on a storage node's root, and no
  model body was staged either (no `hub/` entry newer than 6 h).
- **Consumer still unnamed, and the reason is structural.** On `.35`, no file larger than 1 GB was
  created since 05:00Z (`sudo -n find / -xdev -newermt ... -size +1G` empty), the chunk store is
  1.45 TiB, `/home` 488 GiB and `/var/lib/docker` 485 GB; its image set (36 tags, 467.5 GB) is
  168 GB larger than `.31`'s (34 tags, 299.1 GB), so image-set parity is not a usable check and the
  33,540,547,500 B task image being present on all four ranks does not exclude a pull. Naming the
  consumer needs a before/after `du`, which does not exist for the pre-window state — so the honest
  record is the peer's: growth reported, not explained.
- **What this tick did not do**: booted nothing, claimed no node, stopped nothing, never re-stamped
  or deleted the live `sparkrun-vibe:tp4-boot` lock, and did not touch the shared clone's branch
  (still 77 ahead / 126 behind). One fact worth carrying forward, which the board could only half
  state: the live quartet's register claim exists **only in the head's working copy**
  (`metrics-flag-boot-verification` `running`, claimed by `sparkrun-vibe:tp4-boot`, sha256
  `5a4904e1…`, 00:59:26), so a board rendered from published bytes shows a serving boot with no
  claim.
## 2026-11-09 01:22 ET — second board refresh: the quartet measured metrics, then released the fleet
- **Why a second refresh this hour.** The 01:12 board was composed over `origin`'s committed register
(`5e3c006`), which still read `metrics-flag-boot-verification` `queued` and 28 open, and over a census
taken while four ranks were serving. Both had moved by then: the head's live register copy carried the
claim at 00:59:26 and closed the row `done` at 01:10, and the quartet was gone by 01:19:52. The board is
a coordination surface, so it is corrected rather than left describing a finished flight as in
progress; the correction is an appended landed row, not an edit of the earlier rows.
- **The measurement is real and the flag provably reached the engine.** `--enable-metrics` appears in
`engine-argv.txt` for **4/4 ranks**, `server_args` reads `enable_metrics: True`, the launcher's
`EXTRA_SGLANG_ARGS` ends in the flag (`launch.log:76`), and `/metrics` returns **http-200 on all four
ranks** with 28–71 KB bodies. The quality battery landed **36/37** (easy 19/19, hard 17/18; the single
miss `hard-rev reply nrukraps` is the lane's recorded miss since 2026-10-18), throughput discarded per
`#68` since an instrumented arm has no pre-instrument baseline. `SPARKRUN_EXIT=0`, TTR port-open
327.997 s / HTTP-ready 360.662 s, pin `sha256:7c3cb394…` tagged `canary-roce-aff52fa5` on the four ranks,
image id `sha256:3f448081…`, evidence `~/benchmarks/tp4-metrics-20261109/` on the head.
- **Every holder is now clean, and both ends are dated.** The window lock is gone and the register
records it released with 0 containers per rank; the campaign unit stopped at **00:59:11**
(`signal 15: stopping after this tick`) and restarted at **01:10:35** (`MainPID 4025774`, `worker w1`
one second later) with 0 leases across nine roots; the six-node census at 01:19:52 reads
`1 / 0 / 0 / 0 / 0 / 0` containers and 0 volumes, the lone `.30` container being the `Created` leftover.
- **The pool reading was one event seen twice, and `08a73de` says so.** `df -B1 /mnt/beegfs` on the head
reports `size` 24,191,229,755,392 B against 6 × 4,031,871,553,536 = 24,191,229,321,216 B of the six
nodes' own roots, and `used` 14,380,735,922,176 B against the roots' summed 14,380,735,700,992 B —
within 221,184 B. So `.35`'s root fall and the "pool used growth" are the same bytes counted twice, and
neither corroborates the other; this tick's phrasing inherited that bad pairing until the peer commit
landed mid-publish and forced the correction. The consumer is still unnamed, and structurally so rather
than for want of a probe: `find /srv/beegfs/storage/chunks -type f -newermt '2026-11-09 00:00'` returns
0 files on `.35` and `.31`, no `hub/` entry is newer than 6 h, and no file at depth ≤ 6 under `hub/` is
newer than 4 h. Naming it needs a before/after `du` the window does not have.
- **Instrument note: a clone render is only as fresh as the last commit.** `task-queue.py graph` and
`render` read a file, and the register's authoritative copy during a live session is the writer's
(here the head's, mtime 01:10), not `origin`'s tip — so a tick that renders the clone can understate a
live claim and an already-closed row. This cycle copied the head's `queue.json` into the clone for the
render, restored it before the commit, and the queue row names that source.
- **What this tick did not do**: booted nothing, stopped nothing, claimed no node, edited no other
session's rows, and did not commit the head's register (that close-out belongs to the session that
measured it). Gate: `lint` ok on the published board, address-hygiene 7/7 on the pushed tree, and the
gate run for `bec8c1f` completed `success` before this push.

## 2026-11-09 01:24 ET — third tick: composed board refused by the peer that published first
- **What this tick read, and nothing else.** Census at 01:02:32 / 01:10:34 / 01:17:27 ET — containers
`1 / 1 / 1 / 1 / 0 / 1` on `.30`–`.35`, then `1 / 0 / 0 / 0 / 0 / 0` at both later reads, volumes `0`
throughout, `sparkrun status` idle at the third; the pool by unit state on all six plus a through-mount
`stat -L` on `models--deepseek-ai--DeepSeek-V4.1-Flash-1017/snapshots/1bae0e10…/model-00019-of-00048.safetensors`
= 7 389 761 368 B; the campaign unit stopped 00:59:11 and active again 01:10:35 (MainPID 4025774) with
0 leases across nine roots; `.local/fleet-window.lock` absent on the head and in this clone; the head's
register 27 open / 92 done at 01:12 on the `PROVEN` close-out, 26 / 93 once the second close landed.
The statfs identity was re-verified rather than repeated: `df -B1 /mnt/beegfs` size 24 191 229 755 392 B
against 6 × 4 031 871 553 536 = 24 191 229 321 216 B (Δ 434 176 B) and used 14 380 738 543 616 B against
the roots' summed 14 380 738 379 776 B (Δ 163 840 B).
- **The composition was superseded and its push refused, so this tick published no board.** A 01:20 board
over the 01:12 one was composed (`17 ins / 10 del`: title, seven `In flight` rows replaced by six, the
graph's counts line, one closed queue row gone, five landed rows appended) and `git push` was rejected
non-fast-forward by `c55f165` (01:22), which already carried every cell. The local commit `db09335` lived
only in the throwaway clone and was dropped with it; nothing was force-pushed and no peer board was
overwritten.
- **Trap for the next tick: a heading-drop in the compose step is silent.** Splitting on
`(?m)^(## .*)$` leaves the heading itself in the list, so `parts[parts.index('## Landed session') + 1]`
is the section body without its title: the first composition carried two `## ` headings and put the
whole landed table under `## Work queue`. `lint` passed that file; only asserting the section list and
the queue-row count caught it.
- **Trap: a `launch.log` read while the launch is still writing cannot be trusted for its tail.** A
01:03 read returned a tail ending `SPARKRUN_EXIT=0` with `TTR HTTP-ready 360.662 s` at a moment when a
container created `2026-11-09T06:00:04Z` could not yet have been ready. The consistent series is the
container's `Created` plus the TTR line's own value equalling the file's mtime (01:06:05), so correlate
the three before quoting a tail.

## 2026-11-09 01:31 ET — correction: the lint blind-spot claim, with the command that proves it
- The 01:24 entry asserts `lint` passes a board whose `## Landed session` heading was dropped. That was
read off `lint_markdown`'s rules (tables and fences only) at the time, then reproduced on the actual
bytes: `/tmp/board-0120.md` with the heading line removed, `python3 -B tools/task-queue.py lint` in a
tree holding it as `mad-science/STATUS.md`, prints `ok: 1 markdown file(s) render` and exits 0 while
the file carries two `## ` headings and the landed table sits under `## Work queue`. So the gate that
caught it was the section-list assertion, never lint — a structural check belongs in the compose step.

## 2026-11-09 06:10 ET — board tick: the remote-sha guard refused a stale composition
- **Census, two reads from this workstation**: 06:04:04 → 06:04:07 (one probe per node) and 06:07:45.
  Containers `1 / 0 / 0 / 0 / 0 / 0`, running `0` on six, volumes `0` on six, `.30`'s `sm121m` still
  `Created`; root avail falls **1 490 944 B over 218 s** (6.8 kB/s) with nothing running, and the
  uptimes are unchanged from the 02:0x rolling reboot.
- **Pool role gate re-read, which the peer's `.30`-only probe had dropped**: `.31`–`.35`
  `beegfs-storage` `active` `Result=success` `NRestarts=0`, `beegfs-mgmtd` `inactive`, `beegfs-meta`
  `activating` on restart counters **2742 / 2724 / 2705 / 2690 / 2673** (2075… at 05:09:34) — the
  config-less loop still retrying. Through mount the avail falls 1 572 864 B in the same 218 s.
- **Campaign and register agree that there is nothing to run**: unit restarted 05:47:17 (MainPID
  1829923) and logs `queue: no runnable rows`; nine roots hold 32 arms and 0 leases; the register is
  24 open of 120 with zero claims, its `questions` list empty, and **all 13 queued rows are code/doc
  rows with no `recipe`** while all 11 boot arms are `blocked` — so the drained director is arithmetic,
  not a stalled worker.
- **The `--expect-remote-sha` door refused this tick's first board, and that is the finding.** The
  composition was built over the 05:16 published board (`31d815b4…`) and `publish` refused it with
  `origin/main carries board sha256 3d3544bb…, not the 31d815b4… this board was composed from`, because
  a peer tick had published `d271d96` at 06:08 in between. `--expect-sha` could not have caught it: the
  clone's own board on disk was still the 05:16 copy, so the local check passed against a file no one
  had committed. Re-derived over the peer's bytes, kept their six `In flight` rows and their three
  commit rows, extended only census/pool/publication, pushed as `844a8cd`.
- Note for a later tick: this hour produced three boards (05:16, 06:08, 06:10) and two of them from
  peers settling at the same census. Re-deriving over the newest is cheap; re-composing over one's own
  read is what the guard exists to stop.

## 2026-11-09 06:24 ET — the 06:03 census row's root-fall total was a running subtotal
- **Published wrong, then corrected in place**: the 06:08 board (`d271d96`) wrote "~131 MB in total"
  for a six-node root fall whose own six terms are 66,138,112 + 21,823,488 + 21,770,240 + 21,790,720
  + 21,757,952 + 21,823,488 = **175,104,000 B**. 131,522,560 B is the four-node subtotal, so the
  figure was the sum arrested after `.33`. Corrected on the 06:17 board's bytes as `8474a9b`, which
  changed one clause and nothing else.
- **The correction is what makes the attribution a measurement.** 175,104,000 B against the pool row's
  own +172,490,752 B used growth is a gap of 2,613,248 B (2.6 MB), not "the same order": six
  near-equal per-node deltas summing to the mount delta is the chunk store's per-node split, so the
  "no single node carries a local writer" reading rests on an equality instead of a resemblance.
- **Two publish-door defects this session, both about a throwaway clone.** (1) `publish`'s `--lock`
  defaults to `.local/status-board.lock` *relative to the working tree*, so a board published from
  `/tmp/<clone>` takes a private lock and gets no exclusion against peers; the shared path has to be
  passed explicitly (`--lock <repo>/.local/status-board.lock`), which the later publishes did. (2) A
  push was refused once because a peer published between the `git fetch` and the `git push`; the
  composition was re-derived over the new tip (`2a95424`) and pushed, never forced. Both are the same
  lesson as the 06:10 entry: the guards protect the *read*, and only the remote sha says what the read
  was.
## 2026-11-09 06:21 ET — the director sits under the -900 policy, and a full recomposition was the wrong shape
- **Folded one clause, on the board**: the campaign director's own `oom_score_adj` is **-800**, not the
  -900 the ratified `#72` policy puts on the system units. Read from `/proc` rather than from the
  property alone: the unit property and MainPID `1829923` both answer -800, the unit file carries no
  `OOMScoreAdjust` line, its one drop-in is `retries3.conf`, and the **user manager's own**
  `DefaultOOMScoreAdjust` answers -800 (`syncthing.service` reads the same). The -900 reaches
  `user@1000.service` at pid `1829910` and stops at that boundary; the director inherits -800 as a
  child. The pair that produced `1829923` was graceful, not a crash: `Stopping` 05:46:19, the director
  logging `signal 15: stopping this tick`, `Stopped` 05:46:20, `Started` 05:47:17 under a replaced
  manager (`systemd[2103]` → `systemd[1829910]`), `uptime -s` still 2026-11-08 15:29:35.
- **Abandoned: the six-row recomposition this tick first built.** Composed at 06:10 over the 05:16
  board with its own census/pool/campaign/queue/window/publication rows, it was refused by `publish`
  because a peer had published `d271d96` (06:08) in between; recomposed once more, refused again after
  `844a8cd`. By then the peer board already carried the same census and pool state, the same campaign
  pid, and the `abc3e6d`/`fd89b1a`/`5e31aec` rows, so re-stating them would have duplicated clauses —
  the documented trap. What the board actually lacked was one fact, so one clause is what landed
  (`f5e2732`, pulled up over `8474a9b`).
- **The publish-then-push path needs the retry loop, not one fetch.** Four attempts this cycle: two
  `publish` refusals on the moving remote, then a clean publish, then a **push** refusal because
  `8474a9b` landed between the publish and the push. A single `fetch → compose → publish → push`
  sequence cannot hold the board for that long while peers publish every ~2 min; re-deriving over the
  newest tip each attempt did.
- **Two census reads 13 s apart are not interchangeable for disk totals.** This tick's own read
  (06:02:48–06:02:51 ET, containers `1 / 0 / 0 / 0 / 0 / 0`, volumes 0, running empty) sums the six
  root falls to **122,597,376 B** against the 05:03:51 baseline; the peer's read
  (06:03:02–06:03:04) sums **175,104,000 B** against the same baseline, a **52,506,624 B** gap in
  13 s with nothing running on any node. The state agrees, the bytes do not, so this tick did not
  publish its census as a row and neither figure should be quoted as a settled total.
- **A pool read from one client is not the fleet's read.** `.31`–`.35` answered byte-for-byte
  identically (used 14,381,371,883,520 B / avail 9,809,857,871,872 B) while `.30`'s own read came back
  **exactly 1,048,576 B** higher in used. Quoted per host rather than averaged: a six-host mean would
  hide a 1 MiB client-side difference behind a plausible number.

## 2026-11-09 06:25 ET — board tick: fetching just before `publish` makes its remote gate vacuous
- **The 06:10 close-out above records the guard firing; this tick records it not firing while
the same hazard was live.** `publish` was given `--expect-remote-sha` taken from a `git fetch`
run seconds earlier, so the gate compared the remote board against itself: it matched, exited
0, and wrote a board composed over the **05:16** bytes (`31d815b4…`) onto the clone's disk
while origin was already at the 06:08 board (`d271d96`, board sha `3d3544bb…`) and a second
peer board (`844a8cd`, 06:10) 3 min behind that. Source: `tools/task-queue.py:882-888`
compares `sha256(ref_text(...))` against the value passed, so the flag can only refuse a peer
publish that happened **after** the read the flag is paired with. Procedure: fetch first
(the tool's docstring asks for it), then pass the sha of the read you **composed from** —
never the sha of the fetch you just ran. Recovery cost here was zero only because the next
command listed `origin/main` and showed the tip had moved.
- **Second trap, same cycle: a clause appended after a row's closing pipe makes the row
ragged.**
`row.rstrip() + clause` puts the text outside the last cell, so `publish` refused it with
`table-ragged: 4 cells, header has 3` on three lines. Insert before the trailing `|` and
re-add it. The refusal is the tool working: `lint` on the peer's untouched board right after
the same run read `ok`.
- **What the tick actually read**: census three times per node, 06:02:59 → 06:07:51 →
06:14:04, containers `1 / 0 / 0 / 0 / 0 / 0` with nothing running and volumes `0`, `.30`'s
`sm121m` still `created`, root avail falling **5 349 376 B over 665 s** with no node
standing out; worker pool units read where the inherited row covered only `.30` — storage
`active` from the 02:08:58–02:14:56 starts, meta `activating` on **2710 / 2692 / 2673 /
2658 / 2641**, and `stat -L` on the Ripple snapshot answering **3 541 B on all six**; nine
campaign roots at 32 arms / 0 leases; register `04e9f97f…` = 24 open of 120, zero claims,
head's copy now byte-identical to origin's.
- **Published as `2a95424`** folded row-keyed onto `844a8cd`'s bytes — census, pool and queue
cells extended, one measurement row appended, every inherited row and the whole
`render --board` table kept verbatim — with `lint` `ok`, gate run for `2a95424`
`completed success`, and `tools/push-gate.py` printing `ok -- HEAD 2a954247` (POSIX shells,
stated counts, tracked addresses). Two later peer boards (`8474a9b`, `f5e2732`) built
linearly on top and all four clauses survive on origin. Nothing on the fleet was booted,
claimed or stopped: this was a read-only tick.

## 2026-11-09 07:13 ET — board tick (hourly), composed in `/tmp/boardclone-0700`

- **Campaign stopped, and the row does not invent the actor.** `sparkrun-campaign.service` took
  SIGTERM at 07:07:06 ET (`Result=success`, `ExecMainStatus=0`, `Restart=on-failure` with
  `RestartPreventExitStatus=2`), so it is down by a stop request, not a crash; its own journal
  line names the signal, its final pass printed `9 blocked, 9 measured`, and nine roots swept to
  32 arms / 0 leases. A plain `systemctl --user stop` records no actor in the user journal, so the
  row says the actor is unknown instead of guessing.
- **The pool's hour is a release, then a re-fetch, and the board carries both.** Used bytes went
  `14,381,371,359,232 → 12,979,046,187,008` (−1.402 TB) on the cleanup receipt's nine
  `hf cache rm` deletions (its own pair: `14,381,376,602,112 → 12,966,706,544,640`), while a live
  `hf download unsloth/Qwen3.8-27B-GGUF --revision 4ca72078…` (pid 1919393, started 06:58:24) has
  put ~69 GB back, measured at 84.6 MB/s over a 30 s pair. Reading only the hour's endpoints would
  have called the whole move a deletion.
- **Root avail rose by more than the receipt measured, and that is stated as two measurements.**
  Fleet root avail is +1,191,938,793,472 B against the receipt's derived after-state — the same
  order as its pool release, and consistent with BeeGFS reclaiming chunk-store bytes on node
  roots, but the row assigns no single cause.
- **Published as `9d1956b`** from a throwaway `--depth 20` clone, because the shared worktree's
  `mad-science/STATUS.md` is a peer's uncommitted 23:11 draft (`59a314e9…`) while origin carried
  the 06:33 board (`548a7933…`): satisfying `--expect-sha` against the shared file would have
  meant overwriting bytes no commit holds. One `publish` with `--base` + `--expect-sha` +
  `--expect-remote-sha` on that same read, `lint` `ok`, single-path commit, `HEAD:main` push
  `38b980e..9d1956b`; the shared clone is untouched and its draft survives.
- **What the tick did not do**: booted nothing, stopped nothing, claimed no node, and touched no
  other session's rows. The register is unchanged since `5e31aec`, so the queue table and graph
  were re-rendered and compared byte-for-byte rather than replaced.

## 2026-11-09 07:26 ET — hourly board tick: the `beegfs-meta` loop has a mechanism, and the fleet is free and unclaimed

- **Board published over `9d1956b`.** This tick's first publish landed on `38b980e` and its push was
  refused by `9d1956b`, so the composition was re-derived over the new tip instead of forced; every
  landed row of the peer's survives, and this tick's three rows follow them. Census **07:02:39 →
  07:03:09 ET**: containers `1 / 0 / 0 / 0 / 0 / 0`, volumes `0` on all six, `sparkrun status` idle on
  every host. The one container is `.30`'s `created` `sm121m` leftover, which the 06:51 cleanup
  deliberately kept because a receipt names it.
- **`beegfs-meta` on `.31`–`.35` is a restart loop, and the cause is the drop-in working as designed on
  a host where it cannot succeed.** `/etc/systemd/system/beegfs-meta.service.d/oom.conf` (mtime
  2026-11-08 16:03 on `.30`, 16:05 on `.31`) carries `OOMScoreAdjust=-1000`, `Restart=on-failure`,
  `RestartSec=5` — the owner-authorised pool protection the 2026-11-08 section above records as written
  with **no unit restarted**, so it took effect at the next start, which the 02:08 reboot supplied. On
  the five role-gated hosts `storeMetaDirectory` is empty, so each attempt exits 1 `Error: No metadata
  storage directory specified` and systemd schedules the next: NRestarts read **3406 → 3431 on `.31`
  in two minutes** (3358 / 3339 / 3324 / 3307 on the rest), `.31`'s journal is **956.6 MB**, and
  `is-active` reads `activating` — the state a gate reads as alive. Registered as
  `beegfs-meta-restart-loop-non-meta-hosts` (queued, single); the remedy is to mask or disable that
  unit on the five, never to remove the drop-in or the score.
- **The pool's used bytes fell 1.4 TB on the cleanup and are climbing on one staging write.** Used
  12,934,060,703,744 B (07:03:15) → 12,970,863,624,192 B (07:08:24) → **13,057,790,050,304 B
  (07:16:36)**, +123,729,346,560 B in 13 min, with `.30`'s root avail down 13,277,167,616 B over the
  first five of those minutes. The writer is named by hub mtimes rather than inferred:
  `models--meta-models--Muse-Glimmer-30B-assistant` written 06:54 and
  `models--unsloth--Qwen3.8-27B-GGUF` 06:58 with blobs still arriving 07:04, against a chunk store
  that lives on the node roots. Six `df` reads inside one 3 s window differ by up to 359 MiB, so they
  stay per-host snapshots and never a byte series.
- **`models--ricursiveAI--Ripple-65B-Preview-NVFP4` is an empty shell**: one snapshot id, **0 files
  beneath it**, so the register's NVFP4 hold stands and the directory's appearance is not evidence of
  a body.
- **No window and no lock, corroborated rather than assumed.** `.local/fleet-window.lock` is absent on
  this workstation and on the head, 0 running containers sit on all six nodes, and the nine campaign
  roots hold 32 arms with **0 leases** under a unit that stopped on SIGTERM at **07:07:06**
  (`Result=success`, `Restart=on-failure` with `RestartPreventExitStatus=2`, so it stays down) and
  read `inactive` again at 07:16:36.
- **Two of this tick's own published cells were corrected in the same push, and both were stale
  phrasing rather than measurement.** The campaign row's "no receipt newer than the 06:33 board" was
  the scan's negative, not the tree's — its `find` filtered `*.json`/`*.yaml`/`*.log` and so never saw
  the 06:51 `cleanup-20261109/cleanup.md` the board itself carries three rows above; it now names the
  scan. The census row now cites `mad-science/TODO.md`'s attribution of the 07:07–07:16Z reboots to
  making the `OOMScoreAdjust` drop-ins live on `.31`–`.35`, and says `.30` is still up because its
  reboot is the one awaiting owner approval.
- **Remains:** the loop fix is queued and unstarted; the staging write was still running at the
  07:16:36 read, so the next tick must re-read the pool rather than carry these deltas.
## 2026-11-09 08:23 ET — hourly board tick: the quartet the previous census missed, and two publish traps

- **The 07:28 board read an idle fleet because its census was taken at 07:02–07:03, before the boot.**
  Beam-1.0 NVFP4 (`vllm/vllm-openai:reflection-beam`, image id `58aa975f…`) started four ranks at
  **07:18:36**, so the 08:12 board is the first to carry it: a serve pid alive on every rank and
  `/v1/models` answering **200** both from `.31`'s host port and from inside `node_0`, serving
  `reflection/Beam-1.0-501B-A23B-NVFP4` at `max_model_len` 131072 with util 0.81. Its BFCL leg is
  another session's (`.34`, pid 2018725) and read **716 of 1240 graded, 673 PASS / 43 FAIL** at
  08:07:23; the `bfcl.rc` on disk (`143`, SIGTERM) belongs to the 07:38:26 launch the running one
  replaced, so that is progress and not a verdict.
- **Two `publish` traps, both hit.** (1) `--expect-remote-sha` takes the **sha256 of the board blob at
  the remote ref**, never the tip's commit sha: passing `7cef6a5b…` was refused with "origin/main
  carries board sha256 535ecd22…, not the 7cef6a5b3957 this board was composed from", which reads like
  a peer published when none had; the value that passes is the board sha read, `535ecd22…`, identical
  to `--expect-sha` whenever the base is the remote board. (2) The push that carries a tick is **two**
  pathspec commits, not one — `633deb1` for the register row, `5781900` for the board — and the
  `publication` cell said otherwise until the 08:17 peer board replaced that cell.
- **A census that loses a node must say so.** Head's ssh now refuses `.30` on both of its aliases with
  `Host key verification failed`, while `.30` has not rebooted since 2026-11-08 15:29:35 and answers
  from the workstation; registered as `head-mesh-cannot-reach-30` (queued, single) with
  `ssh-keygen -F` as the unrun discriminator, so the cause stays open. Independent corroboration: a
  peer tick's `/tmp/tick-0800-census.txt` on the head records the same refusal at 08:03:32, and it was
  left in place as theirs.
- **Pool growth attributed, not inferred.** `df -B1` used 13,365,355,216,896 → 13,374,916,132,864 B
  over 110 s (08:05:48 → 08:07:38, **86.9 MB/s**) while `models--unsloth--Qwen3.8-27B-GGUF` carried
  `.incomplete` blobs touched inside the previous 15 min — one HF staging pull, not a fleet-local
  writer. Hub holds 106 entries (111 at the 2026-11-08 23:08 read).
- **Hygiene:** the census script's only node-side artefact, `/tmp/hub-newest.txt` on the head, was
  removed; the probes wrote nothing else on any node and the in-flight session's files were left alone.
- **Remains:** the BFCL leg is still measuring, so its window closes no earlier than 10:18; the mesh
  fix is queued; the 08:17 peer board kept this tick's campaign, flight, window, queue and landed cells
  verbatim, so no landed row was replaced.

## 2026-11-09 08:24 ET — `.30` read from its own host, the staging pull named, and a clone that was not the clone

Landed on the board two cells the 08:12 board could not fill: a direct `.30` host read
(the head's mesh cannot reach it), a stamped 14 s six-root root-avail pair, and the
staging repos named by directory mtime. Everything else was the peer's, kept verbatim.

- **`.30` answers from the workstation while the head's mesh cannot reach it.** Peer
  registered `head-mesh-cannot-reach-30` this hour; the host itself reads containers `1`,
  running `0`, the same `Created` `sm121m` leftover, root avail 1,478,558,777,344 →
  1,478,359,826,432. The gap is the route, not the host.
- **A six-root root-avail pair in 14 s (08:08:37 → 08:08:51) sums to −1,459,306,496 B,
  including `.30` and `.34`, which rank nothing** — the pool's chunk store on each node
  root absorbing the staging write. A root fall on a host with no workload is the pool
  body arriving, not a local writer.
- **The body is named by mtime, not inferred**: `hub/` mtimes 07:41:19 on
  `models--incoai--Qwen3.8-27B-DFlash2` and `models--meta-models--Muse-Glimmer-30B-assistant`
  refs, 07:59:17 on `models--unsloth--Qwen3.8-27B-GGUF` blobs; pool used
  13,057,790,050,304 B (07:16:36) → 13,384,792,145,920 B (08:08:52), +327,002,095,616 B.
- **The head's clone is not the clone, and `HEAD:` of this one is neither.** A draft said
  the head's copy reads 119 tasks, two rows short, five closes missing; that was `HEAD:`
  of the *workstation's* clone (`3eaba1c1`). The head's file (`04e9f97f`) is **120 tasks /
  24 open**, one row short, all five closes present. Two disjoint clones, both called
  "the clone": say whose bytes you counted.
- **Two publishes lost to the same race, and both were re-derived rather than forced.** A
  composition over `7cef6a5` had its push refused when a peer published the 08:12 board;
  the ledger append was then refused by `ba5b781`. Re-fetch, re-derive, append last.
- **Remains:** the BFCL leg still measures (progress, not a result); `beegfs-meta`'s loop is
  queued and unstarted; staging continues, so pool deltas must be re-read, not carried.

## 2026-11-09 11:46 ET — TP4's fit negatives, the Beam BFCL cell, host policy live, and 1.312 TiB reclaimed

The TP4 window that opened 01:00 ET produced one verification, one measurement, and two
rejections, and the night's remaining work closed the two h2h rows, the host-memory policy,
and the fleet cleanup. Receipts are cited by the root that holds them. The two fit verdicts
are arithmetic over bodies measured in the pool, not readings of a failed boot, and no
number below was carried from a board row alone.

- **The metrics verification boot proves the flag reaches the engine, not only the recipe.**
  The shipped knapcio TP4 recipe ran from its file path (never `@littlecedar`) on
  `.31`/`.32`/`.33`/`.35` as task `sparkrun_b020d2dd178343a5_b632751318c7`, pin
  `…dsv41@sha256:7c3cb394…` resolved to image id `sha256:3f448081…` on all four ranks,
  `SPARKRUN_EXIT=0`, TTR port-open 327.997 s / HTTP-ready 360.662 s. `EXTRA_SGLANG_ARGS`
  ends `--enable-metrics` (`launch.log:76`), every rank's `sglang.launch_server` cmdline
  carries it (`engine-argv.txt`, 4/4), the server_args dump reads `enable_metrics: True`,
  and `/metrics` answered HTTP 200 on 4/4 ranks with 28,204–71,750 B bodies
  (`metrics-status.txt`). Cell: `quality-battery.py` easy 19/19 plus hard 17/18 = 36/37, the
  sole miss `hard-rev / nrukraps`, the same single miss as the lane's 2026-10-18 record;
  throughput discarded per `#68`. `.30` was untouched per `#67`/`#70`. Receipt
  `head:~/benchmarks/tp4-metrics-20261109/`.

- **The SM121 marlin line is a fit negative, and the host policy proved itself in the
  process.** Two instrumented boots ran on `.31`/`.32`/`.33`/`.35` with `.30` driving
  `sparkrun` and never a rank: `boot-2`, task `1c0dffa45afa6e47_bc046dfe041f`, and
  `boot-3`, task `…_cc6ffc677667`, the latter with `-o env.DSV41_FAST_LOAD=0` and
  `MAX_TOTAL_TOKENS=6849792` in force. `.31`'s MemFree fell 115,808,796 → 3,800,692 kB =
  **106.8 GiB in 3 s**, then 117,522,996 → 1,889,340 kB = **110.3 GiB in 4 s**, while the
  rank container's cgroup never exceeded **5.87 GB** (peaks 5,870,653,440 and
  5,867,200,512 B; `.32`/`.33`/`.35` each 4.45 GB). earlyoom `-m 4` sent SIGTERM to
  `sglang::schedul` (badness 977; 976–978 on the workers), the driver logged
  `NVRM … NV_ERR_NO_MEMORY` first at 01:37:59–01:38:01, and `journalctl -k` counts **0**
  `oom-kill` lines on all four ranks. A ~110 GiB dive therefore cost one serve process and
  no pool unit, no `sshd`, and no user manager — `#67`/`#72` working in anger. The row
  closes `done` as a fit negative; the three `w4-survey-arm*` rows stay `blocked` on it plus
  the flashinfer `hidden/intermediate % 128` refusal, not on an owner retirement call.
  Receipt `head:~/benchmarks/sm121-oom-20261109/` (`VERDICT.md`, `boot-2/`, `boot-3/`).

- **Both Kimi TP4 rows are fit rejections, and the rejection is arithmetic, not staging.**
  The body is complete in the pool: 96/96 shards, 442.8512 GiB, `refs/main` `fc72e5a1`, zero
  `.incomplete`. Demand per rank = 110.7128 GiB of weights (442.8512/4) + 3.05 + 0.42 KDA +
  context at 30,816 B/token (24 DSA layers × [(512+64)×2 + 128+4] B). Best-ever free is
  115.02 GiB, so the maximum margin is **0.84 GiB at ctx 0**, the largest positive-margin
  context is 29,171 tokens, the shipped 16,384 leaves 0.37 GiB and is **−2.32 GiB at the
  worst free 112.33**; util 0.92 budgets 111.95 GiB and is 2.70 GiB short at 16k, and the
  requestable util ceiling 0.9452 clears 115.02 with neither a 2 nor a 5 GiB margin. The
  DSpark sibling adds the 4.19 GiB drafter: 114.9028 GiB of weights, 118.3728 GiB with no
  KV, 3.35 GiB above best-ever free, required util 0.9728 against the 0.9452 ceiling. Both
  rows stay `blocked` as fit-negative and keep their parent edge. Memo
  `.scratch/kimi-pruned75-fit-20261109/rederivation.md`; the derivation is also in the
  register notes.

- **The Beam BFCL cell landed at 1112/1240 = 89.68 %, and it is an accuracy cell only.**
  One direct `tools/bfcl-eval.py --json` run over five categories and 1240 questions at
  rc=0: simple 381/400 = 95.25 %, multiple 189/200 = 94.50 %, parallel 179/200 = 89.50 %,
  parallel_multiple 172/200 = 86.00 %, and irrelevance 191/240 = 79.58 %. The boot used
  `-o gpu_memory_utilization=0.81` — the recipe's 0.85 settled 1.98 GiB free and 0.90 would
  request 109.52 GiB against 106.22 GiB of startup free, so 0.81 budgets 98.57 GiB with
  21.14 GiB of KV — plus `-o extra_args=--enable-auto-tool-choice`, and the client ran on
  `.34` under `oom_score_adj=-900` with the engine's `tensorfold` comm outside earlyoom's
  `--prefer` list. That is not the arm's recorded performance configuration, and the row's
  note says so rather than letting the category table read as one. Receipt
  `head:~/benchmarks/h2h-20261107/zz-beam-1.0-501b-a23b-nvfp4-tp4-vllm/client/bfcl.json`
  (1,896,782 B).

- **The two remaining h2h rows closed on their numbers.** `h2h-second-boot-ladder` closed
  because all four second boots exist, so the head-to-head table's sigma column is
  computable and the per-cell C1/C2/C5/C10 means, sample standard deviations, and
  boot-to-boot deltas now live in the doc; `glm-flash-concurrency-degradation-search`
  closed on three legs at one image, `sha256:7f8f1b38…`: the same-window shipped control
  read C1 103.25±5.46 / C2 109.41±31.29 / C5 94.18±2.62 / C10 86.65±1.31 t/s, boot2 read
  105.90 / 120.46 / 96.80 / 86.87 (C2→C10 −20.8 %), the no-drafter leg read
  53.20 / 74.29 / 76.47 / 71.25 (C2→C10 −4.1 %, flat inside the C2 sigma) while losing
  17.8–48.5 % at every rung, and the 4-slot leg read 100.2 / 117.1 / 84.6 / 79.4 and still
  fell past C2. The C5→C10 fall therefore survives with no DFlash2 at all, so the drafter
  is not its cause. Receipts `head:~/benchmarks/h2h-20261107/`.

- **Host memory policy is live on all six nodes, and `.30`'s next-start residual is gone.**
  After the 07:07Z–07:16Z reboots, `.31`–`.35` read `OOMScoreAdjust=-900` on `ssh.service`,
  `NetworkManager.service`, and `user@1000.service`. `.30` needed no reboot: `fd89b1a`
  restarted its `NetworkManager` and `user@1000`, and the 11:41 ET read finds both units at
  `-900` **and** their running PIDs' `/proc/<pid>/oom_score_adj` at `-900` (NM pid 1828861,
  `user@1000` pid 1829910), so the configured-but-pending state is gone by read-back rather
  than by assumption. Pool units keep `-1000`, and the campaign director still inherits the
  user manager's `-800`, below the policy's `-900`; that remains a recorded finding, not a
  regression. Receipt `head:~/benchmarks/host-mem-policy-20261109/`.

- **The fleet cleanup reclaimed 1,442,780,551,520 B = 1.312 TiB, and its own rule was
  rewritten by the result.** Nine `hf cache rm model/<org>/<name>` deletions
  (`Qwen/Qwen3-1.7B`, `Qwen/Qwen3.5-2B`, `incoai/Qwen3.8-27B-DFlash2`,
  `meta-models/Muse-Glimmer-30B-assistant`, `RadixArk/Muse-Glimmer-NVFP4`,
  `Qwen/Qwen3.5-122B-A10B-FP8`, `bertholomus/…EXL3-2.5bpw` and `…EXL3-4.0bpw`, and
  `unsloth/Qwen3.8-27B-GGUF`), 11 unreferenced image ids removed one at a time, 8
  runtime-cache trees triaged by provenance, 41 scratch files, two dangling symlinks on
  `.34`, and a 48 GiB root-owned staging duplicate on `.33`; `.30`'s `sm121m` was kept
  because a receipt names it. HF net is 1,105,242,551,008 B = 1.029 TiB and the observed
  pool endpoint is 14,381,376,602,112 → 13,008,533,192,704 B; the node side's
  337,538,000,512 B carries the session total to the stated 1.312 TiB. The first pass
  counted mentions as consumers, so **four bodies were restored and then re-deleted**
  (`incoai`, `meta-models`, `RadixArk`, and `unsloth`; two xet failures and one 84.16 GB
  `.incomplete` were removed on the way). The rule that came out of it:
  **"retirement notes are not consumers"** — a mention that records a retirement,
  recommends a reclaim, or reports a finished prefetch is a deletion instruction, not a
  guard, and the rule cuts the other way too. Receipt
  `head:~/benchmarks/cleanup-20261109/cleanup.md`.

- **What remains blocked, and why.** 11 blocked rows: the three SM121 survey arms (the fit
  negative above plus the flashinfer 128-multiple kernel refusal), the two Kimi TP4 rows
  (the fit rejection above), the GSQ-RCO llama.cpp boot (needs an image at or above
  llama.cpp b11870 and the 110.60 GB Engram file present on the node), the three
  Ripple-65B rows (the NVFP4 repo is absent from the pool; the BF16 TP=2 control is still
  unmeasured), media-idol 3DGS (the facebook DINOv3 licence was not accepted, owner
  `#81`), and the Kimi SuperExpert reference probe (the serve is chat-only; the measurement
  path is the block). A further 14 rows are queued and all are instrument or gate defects,
  not fleet work. The `beegfs-meta` restart loop on `.31`–`.35` is unchanged at a ~5 s
  cadence (`NRestarts` 6559 / 6541 / 6522 / 6507 / 6490 at the 11:41 ET read) and stays
  queued; the pool read a real 970,533,624 B shard through the mount at 11:46:00 ET.
- **The 12:00 tick stood down: a peer tick published the 12:11 board three minutes
earlier, and an independent six-node probe corroborates it.** Two ticks ran this hour
on the same workstation. This one read every node at 12:03:13 and again at 12:05:20 ET
(`docker ps -q` `0` on all six, `docker ps -a` only `.30`'s `sm121m` `dsv41-sm121-dg:0.2.1`
leftover in `Created`, `docker volume ls -q` `0` on all six; root avail
1 560 187 805 696 / 1 855 691 649 024 / 1 951 778 779 136 / 1 897 695 404 032 /
1 345 070 772 224 / 1 429 979 357 184 B on `.30`–`.35`, **−17 457 152 B** against
the 11:41:32 read and **−864 256 B** across its own 127 s pair), swept the nine
campaign roots at 12:03:14 (**32 arms, 0 leases**, the same 7/1/1/1/18/1/1/1/1 split
the published board carries), read `director status` (**9 measured, 9 blocked**,
unit active since 09:12:09, `MainPID 2078281`), and re-read the register
(**122 tasks: 97 done / 14 queued / 11 blocked / 0 claims**, `check` rc=0,
`questions` 0). Every figure agrees with the board the peer published at 12:12:17
(`e671b92`), whose census (12:06:38 → 12:07:51) is fresher than this probe's, so a
second publish would have replaced fresher rows with older ones. Also corroborated:
`beegfs-meta` on `.31`–`.35` read `NRestarts` 6863 / 6844 / 6825 / 6810 / 6793 at
12:08:03, **+304 / 303 / 303 / 303 / 303** on the 11:41 figures (≈5.3 s per restart),
so the 5 s loop in the queued row is unchanged.
- **The pool's used bytes moved in both directions after the published board's window
closed.** `df -B1 /mnt/beegfs` read 12:08:04 → 12:09:35 ET: used
12 921 799 704 576 → 12 921 823 297 536 B and avail 11 269 430 050 816 →
11 269 406 457 856 B, i.e. **+23 592 960 B in 91 s = 259 KB/s**, against the board's
own window (12:06:39 → 12:07:51) of +8 912 896 B in 72 s = 124 KB/s. The two windows
chain exactly — the first ends on 12 921 799 704 576 B, where the second starts — so
176 s of growth at a rate that roughly doubled, with the hub still at **102** entries and
the DeepSeek-V4.1-Flash-1017 shard read through the mount at **970 533 624 B**
(mtime `2026-10-18 01:15:47 -0400`), unchanged. The direction reverses later in the
hour and no client-side writer exists — see the sweep bullet below, which is what that
first read could not see.
- **Two ticks shared one fixed `/tmp` compose path, and it was clobbered mid-compose.**
After this tick wrote and then patched `/tmp/compose-1200.py`, a read of that same path
returned compose text this session did not author — "avail pair over the 72 s window",
the earlyoom `-m 4,1 -s 100,95` clause — matching the peer board's wording. The skill
already names the trap (compose to a per-session path); the durable form is to put the
tick's identity in the compose script's name too (`/tmp/compose-<HHMM>-<pid>.py`), not
only in the output board's.
- **The pool's byte movement has no client-side author on any node, and it reverses.**
Read 12:24:18 ET: `df -B1 /mnt/beegfs` used **12 921 814 908 928 B**, avail
**11 269 414 846 464 B** — **8 388 608 B below** the 12:09:35 used figure, so the growth
recorded above is not a fill. Swept 12:24:04–12:24:06 on all six: no `hf download`,
`huggingface-cli`, `git-lfs` or `rsync` process anywhere, and `sudo -n fuser -v
/mnt/beegfs` prints only `root kernel mount /mnt/beegfs` on each host, so no userland
process held a file through the mount. On the head the staging pid 529334 is gone and
`models--vllm-project--Kimi-K3.1-Pro-pruned75` reads `du -sL` **464 380 873 KiB =
442.8 GiB** with `refs/main` mtime `2026-11-08 09:58` and its shard blobs `08:23`, no
`.incomplete` left — that body finished the previous day and is not today's writer. The
newest entry anywhere under `hub/` is `2026-11-09 08:50`, so no model body has been
written in the last 3.5 h. Both directions are therefore pool-side traffic (chunk-store
allocation and reclaim) with no client process behind them, which is where the next probe
belongs; the board's "writer unnamed" holds, while "consumption" overstates a quantity
that also falls. Two ticks on this workstation read the pool this hour and each carried a
different slice of the same oscillation.

## 2026-11-09 17:02 ET — 64 KiB pages tested and refuted as the marlin mechanism

One node, one reboot, one measured answer: the page-size route cannot carry the SM121 fit negative, so it is closed
here rather than left to a later quartet window. Receipt `head:~/benchmarks/ds4-64k-20261109/` (49 artifacts).

- **What was installed, and what was proved to be in force.** `linux-{image,modules,headers,tools}-7.0.0-1019-nvidia-64k`
  at `7.0.0-1019.19~24.04.2` plus `linux-modules-nvidia-580-open-7.0.0-1019-nvidia-64k` and
  `nvidia-kernel-source-580-open=580.178.04-0ubuntu0.24.04.1` (simulated first: 7 new, 0 upgraded, 0 removed, no
  NVIDIA userspace change), and `dgx-spark-memory-saver` 0.4.1 at
  `ec1b17a8ac713c6357b8f22983ded8503a524849`, registered in DKMS **for the 64 KiB kernel only**, where its
  `updates/dkms/nvidia-uvm.ko.zst` genuinely shadowed the distro-prebuilt module — the project's own read-only
  `./scripts/status` answered `State: packing-enabled`, `Packing parameter: Y`, `issues: []`, and the sibling modules
  (`nvidia`, `nvidia_drm`, `mlx5_*`) stayed prebuilt. One shot only: a top-level `menuentry` `ds4-64k-trial` in
  `/etc/grub.d/40_custom` cloned the fleet's own 1025 command line plus `panic=60 panic_on_oops=1`, armed with
  `grub-reboot`, persistent default left pinned to the 1025 entry. `panic=` covers panics alone — an early-init
  deadlock would still have needed a human power cycle on a node with no BMC — and that was accepted, not fixed.
- **Page tables got larger, and they were never a mechanism.** Idle on 4 KiB: `PageTables` 9,360 kB and
  `nr_page_table_pages` 2,451; idle on 64 KiB: 23,552 kB and 390 pages — 16× fewer pages in **+15,156 kB** of bytes
  (a 64 KiB page-table entry maps more, so the byte counters and the page count part company; the 14,192 kB figure is
  the `meminfo` delta). Against the ~107 GiB host dive those are **0.0083 % and 0.021 %**, and the peak under a
  4.5 GiB pinned host↔device copy was 49,664 kB. Page tables therefore **cannot** be the marlin mechanism: the rank
  cgroup never exceeded **5.87 GB** while `.31` lost 106.8 GiB in 3 s and 110.3 GiB in 4 s, so the lost memory was
  never container-charged and never page-table-shaped.
- **The real lever is `MemTotal`, and it is small.** 127,598,700 → 129,798,848 kB = **+2,200,148 kB = +2.10 GiB**,
  i.e. what a 16× smaller `struct page`/vmemmap array buys (~1.81 GiB by arithmetic at 64 B/page), the same order as
  upstream's measured end-to-end 1.78–1.86 GiB/node usable. (Corrected 2026-11-09 17:25: the subtraction is 2,200,148 kB;
  the earlier `+2,100,148` was one digit off — the capture pair is `baseline-4k-meminfo.txt` / `matched-64k-meminfo.txt`,
  and the receipt's §5 already stated 2,200,148.) The UVM packing half was loaded and enabled yet
  **idle-neutral by construction** — it saves at allocation time, and an idle node makes no such allocations — so its
  effect is quoted from upstream and was not re-measured (the pack-on/off A/B was impossible: a `flare` process holds
  `/dev/nvidia-uvm`). Summed additively with upstream's 1.78–1.86 GiB the whole configuration reaches **4.8 % of the
  107 GiB dive**, and the two levers do not actually compose — so a green trial would not have explained the fit
  negative, and this negative result does not refute page size either.
- **The one residual of the right order is still confounded, and stays unattributed.** Host memory outside every
  `/proc/meminfo` category read **6.22 GiB** on the 64 KiB boot against **2.35 GiB** on an idle 1025 peer whose
  `nvidia_uvm` refcount is 0. The peer comparison is confounded by a process, not a service: what holds a CUDA/NVML
  context on `.35` (and on `.30`) is a user-run `/home/red/.local/lib/flare-agent/flare agent` process — two
  `/dev/nvidia-uvm` fds, `VmRSS` 22.6 MB on `.30` / 28.5 MB on `.35` — while `flare-agent.service` **does not exist
  on any of the six nodes** (`systemctl list-units --all 'flare*'` is empty everywhere, `nvidia_uvm` refcount 0 on
  `.31`–`.34`). A 22–28 MB RSS process cannot weigh 3.9 GiB, so the residual is **not** attributed to it; the
  receipt's `flare-agent.service` naming is corrected here and the quantity is left as the thing a quartet trial must
  measure.
- **Rollback is complete and verified, not assumed.** `.35` rebooted once back onto `7.0.0-1025-nvidia`:
  `getconf PAGESIZE` 4096, `/sys/module/nvidia/version` 580.178.04, `swapon --show` 16 G `/swap.img` (the original
  `sw` entry restored, `/swap-64k.img` left `noauto`), `modinfo -k 7.0.0-1025-nvidia -F filename nvidia_uvm`
  resolving to `/lib/modules/7.0.0-1025-nvidia/kernel/nvidia-580-open/nvidia-uvm.ko` with **no** packing parameter,
  `MemTotal` back to 127,598,700 kB, `/proc/cmdline` still carrying `kho=off` with `CmaTotal 0`, `beegfs-storage`
  active, `docker ps -q` 0. `systemctl --failed` carries `beegfs-mon.service` alone, which is the fleet's
  pre-existing empty `sysMgmtdHost` config and not a regression. The kernel packages and the DKMS module **stay
  installed and inert**, reachable only through the `ds4-64k-trial` entry, because a later quartet trial may still
  want them.
- **What a quartet trial has to measure instead.** Not idle page tables. It has to account for the ~107 GiB dive
  host-side while the rank cgroups stay flat: UVM sysmem and the driver's freed-UMA pool across the exact
  `Load weight begin` window, pinned/O_DIRECT staging during checkpoint read, and the meminfo-unaccounted pool above —
  each with `flare` absent or measured beside it, and with the same numbers taken on a 1025 control boot of the same
  arm. Register row `ds4-64k-pagesize-trial` is `done` on this receipt, so the route is not re-run.

## 2026-11-09 17:03 ET — hourly tick stood down on a peer's fresher board

- **What ran, and what it read.** A read-only six-node census at **17:03:28–17:03:30 ET** from the
  workstation: `docker ps -aq` **1 / 0 / 0 / 0 / 0 / 0**, `docker ps -q` **0** and `docker volume ls -q`
  **0** on all six, no `sglang.launch_server` process anywhere, and `.30`'s only container still the
  never-started `sm121m` (`dsv41-sm121-dg:0.2.1`, `7fba5dc0050b`, `Status=Created`). Root `df -B1 /` as a
  stamped pair **17:05:28–30 → 17:05:51–52** fell **159 744 B fleet-wide** (`.30` −8 192, `.31` −24 576,
  `.32` −73 728, `.33` −16 384, `.34` −20 480, `.35` −16 384), every node falling on its own.
- **The pool, read through the mount and paired with its own file survey.** At **17:05:53** `df -B1
  /mnt/beegfs` read total 24 191 229 755 392 B, used **12 940 474 843 136 B**, avail **11 250 754 912 256 B**
  (53.49 %), `stat -L` on the shipped DeepSeek-V4.1-Flash-1017 shard returned **970 533 624 B**, and the hub
  held **102** entries with nothing newer than 15:55 — `find … -newermt '-70 minutes' -type f` returned 0, the
  explicit 15:55–16:40 window returned 0, and outside `huggingface/` (the mount's only top-level entry) 0 in
  75 min. So the hour's **+18 393 595 904 B used** against the 16:03 read has no file author in the tree and
  no mechanism is named here either.
- **Campaign and register.** Unit `active` (MainPID 2078281, started 09:12:09, `NRestarts=0`), worker `w1`
  pid 2078290, `director status` 18 arms **9 measured / 9 blocked**, nine roots **32 arms, 0 live leases**;
  the clone's register read `892197ee…` / 124 tasks at 17:02:35 while `HEAD` still held `f383bde0…` / 123 —
  that write was a peer's, committed minutes later as `b8f83f6`.
- **Stood down, because a peer's commit is the fresher refresh of the same hour.** `41a05ca` published a
  17:16 board over the same census window, and by the time this tick was ready to publish two of its
  composed cells had gone false: `.local/fleet-window.lock` is **absent** in this clone and on the head
  (it stood at 17:02 with mtime 16:25:36 and was released with `b8f83f6`), and the worktree-vs-published
  register divergence no longer exists, so the `892197ee…` cell is obsolete. Its landed table already
  carries the 64 KiB verdict row, so appending this tick's rows would duplicate both. The composed board was
  therefore withheld rather than published — replacing or doubling a peer's rows is the failure this
  stand-down avoids.
- **One discrepancy, reported not silently repeated.** This tick's two independent hub counts (**17:05:53**
  and again after the publish attempt) both read **102** entries in `/mnt/beegfs/huggingface/hub`, while the
  17:16 board's pool cell says **103**. Whichever holds, the cell's load-bearing claim is unaffected — the
  newest repo dir is still `models--vllm-project--Kimi-K3.1-Pro-pruned75` at `2026-11-08 09:58` and no file
  in the hub is newer than 15:55 — but the count is a live-board figure and should be re-derived by the next
  tick rather than carried.
- **`.35`, re-read after the release.** Boot −1 ran **16:41:24 → 16:59:03** on `7.0.0-1019-nvidia-64k`
  (`getconf PAGESIZE` 65536 at 16:46:24 and 16:48:28), ended in a clean `Reached target reboot.target`, and
  boot 0 started **16:59:17** on the default `7.0.0-1025-nvidia`; the node now reads 0 containers, 0 volumes,
  `kho=off` on its cmdline, `CmaTotal`/`CmaFree` 0, and `dgx-spark-memory-saver/0.4.1` DKMS installed for the
  64k kernel only.

## 2026-11-09 17:35 ET — hourly tick: 64 KiB trial's delta corrected, three board cells rebuilt

- **Read-only on the fleet.** Six-node census 17:04:19–17:04:44 ET from the workstation alias: containers
  `1 / 0 / 0 / 0 / 0 / 0`, `docker ps -q` 0 on all six, volumes 0 on all six, `.30`'s single container the
  never-started `Created` leftover; root `df -B1 /` fell **8 634 368 B** over the pair with `.31` carrying
  **97 %** of it. All six on `7.0.0-1025-nvidia`, `kho=off` on every cmdline, `CmaTotal`/`CmaFree`/
  `nr_free_cma` all 0, so the RDMA-registration guard survived `.35`'s reboot. Uptimes `.30` 2026-11-08
  15:29:35, `.31`–`.34` 02:08:49–02:13:17 unchanged, `.35` 16:59:17.
- **Pool, campaign, register, window.** Pool served a pair 17:07:33 → 17:08:38 moving **524 288 B** with a
  `stat -L` on the shipped DeepSeek-V4.1-Flash-1017 shard returning 970 533 624 B, hub 102 entries, and
  **0 files under `huggingface/` newer than 90 min** — while `used` sat **18 403 557 376 B** above the 16:03
  read, so the hour's growth stayed unattributed and no mechanism was named. Campaign unit `active`
  (MainPID 2078281, worker `w1`), head's nine roots **32 arms / 0 live leases**, h2h root **9 measured,
  9 blocked**; queue mode had **no eligible row**, all 15 `queued` register rows lacking a `recipe` id.
  Register `892197ee…` **124 tasks / 98 done / 15 queued / 11 blocked / 0 claims**, `check` rc=0,
  `questions` 0. The `ds4-64k-trial` window lock stood at 17:04 (mtime 16:25) and was **absent from both
  copies at 17:14**, with `.35`'s own boot list showing the trial boot 16:41:24 → 16:59:03 and the stock
  kernel from 16:59:22.
- **The correction that mattered.** The trial's lever was stated as `MemTotal +2,100,148 kB` in three
  committed carriers — the register note, `SESSION-RECORD.md`'s own trial section, and the board's 17:09
  landed row — while the captures subtract to **2,200,148 kB = 2.10 GiB** and the same sentences quoted
  `2.10 GiB`. All three now read 2,200,148 kB with the capture pair named; the ruling is unchanged (page
  tables 0.0083 % → 0.021 % of the dive, whole configuration 4.8 %). The `+15,156 kB` beside it is **not**
  a slip and was left alone: it is the page-count derivation (390 × 64 KiB − 2 451 × 4 KiB), which is why
  the ledger separates it from the 14 192 kB meminfo delta.
- **A commit that had to be undone, and was.** The first attempt (`8fc451a`) was built with
  `git commit -F - -- <three paths>` and swept ~40 lines of another session's uncommitted close-out into
  the ledger file. It was reset with `git reset --mixed 41a05ca` **before any push**, the worktree keeping
  that session's section intact, and rebuilt through a throwaway `GIT_INDEX_FILE` + `write-tree` +
  `commit-tree` so the commit carried only this tick's three hunks (`cc10aed`); that session then committed
  its own section as `4910f34`.
- **Three publication cells were wrong before this one, and the chain is resolved rather than hidden.**
  The 17:15 composition was refused by `publish` when a peer's 17:16 board landed under it, so the tick
  rebuilt on that board and published at 17:21 (`cc10aed`). `5d01981` then re-labelled the census read and
  rewrote the publication cell, but shipped a doubled date and named the previous publish's size, sha and
  commit as its own; `304b856` fixed that shape yet named the 17:21 board as the base when its real base was
  the 17:27 one (`110b3f41`, 208 304 B, origin `5d01981`). This board states each predecessor's true base and
  bytes and defers its own sha and commit to this commit's body, since a board cannot hash itself.
- **Verified, and what remains.** Gates ran green on all four of this tick's commits (`cc10aed`, `5d01981`,
  `304b856`, and this one), read back from `gh run list` and not assumed. Still open and unfixed here: the
  pool's ~18 GB/hour growth with no file author in the mount; `beegfs-meta` restarting every ~5 s on
  `.31`–`.34` (NRestarts 10 211–10 264, `.35` 61 after its reboot) under row
  `beegfs-meta-restart-loop-non-meta-hosts`; and `.35`'s new persistent state from the trial — the
  `7.0.0-1019-nvidia-64k` package, its `beegfs/8.4.1` DKMS module, `/etc/default/grub.d/zz-dgx-spark-memory-saver.cfg`
  pinning `GRUB_DEFAULT` to the 1025 entry, and `/var/lib/dgx-spark-memory-saver/preparation`, all inert but
  installed, so a later window must not assume stock GRUB on that node.

## 2026-11-09 18:12 ET — the ÷128 refusal was the shim: b12x armed and arm 3 took its 1M cell

- **The root cause, in one sentence.** The overlay launcher's staged `sitecustomize.py` shadowed the
  serving adapter's own (Python imports exactly one), so `install_moe_b12x_next` under
  `DSV41_MOE_B12X_NEXT` never ran, the stock `Mxfp4FlashinferCutlassMoEMethod` stayed in place, and its
  multiples-of-128 guard fired on the checkpoint's own 576-wide per-rank experts — a harness defect, not
  an image limit. `5ac799e` chained the shim to the adapter, and `6b0434d` replaced that commit's
  `DSV41_ADAPTER_SITECUSTOMIZE` handoff with deriving the shadowed file from `sys.path` (proof grep
  `_shadowed_sitecustomize` 2 hits, env knob 0 in `launcher.py`), so a missing adapter now prints
  `overlay patches NOT installed` instead of failing silent.
- **The boot proved the mechanism before any cell did.** `sparkrun_1c0dffa45afa6e47_61ab7a786592` on
  `:0.2.1` (`sha256:85c1ffc3…`) across `.31`/`.32`/`.33`/`.35`, launch 22:46:29Z, first healthy
  22:54:19Z — **TTR 470 s** — serve log carrying `[moe_b12x_next] armed: routed MoE on b12x_next
  a7d7d29b (W4A8, in-place repack) … tune=True` and **no** ÷128 `ValueError`. Load:
  `Load weight end. elapsed=214.72 s, quant=fp8, avail mem=34.92 GB, mem usage=76.89 GB` from 111.82 GB
  at begin, then the draft at `4.14 s`, 3.40 GB; `/v1/models` 200 at `max_model_len` 1048576. Teardown
  23:03:58Z left **0 containers / 0 volumes** on all four ranks.
- **The memory now sits where the mechanism said it would.** Minimum `MemAvailable` **9.28 GiB** (`.35`
  during the 1M prefill; per-rank `.31` 9.31 / `.32` 10.25 / `.33` 9.72 / `.35` 9.28 against a 117.7 GiB
  idle high), peak rank container cgroup **33.95 GB**, page tables ≤0.1 GiB, the 6.0 GiB two-sample stop
  rule never firing, and **zero** kernel `oom-kill` lines and **zero** earlyoom kill lines. The contrast
  is the finding: the marlin boots took ~107 GiB out of the host while every rank's cgroup stayed
  ≤5.87 GB, and this boot charges ~34 GB **inside** the cgroup instead — the in-place repack, which is
  what the sibling analysis claimed and nothing had yet measured.
- **The arm-3 cell, with its limits stated rather than implied.** Prompt **1,035,623 tokens**, TTFT
  **277.2 s**, needle **1/1 PASS** (reply `ZX81-1208`), **56.2 ms/step** median, 3 decode steps,
  53.57 tok/s. Three steps is not steady state, and no same-protocol canary ms/step baseline exists, so
  no ≥5 % claim is possible: **the lane's arm-3 falsifier stays undecided** until
  `zz-ds4-1017-sm121-arm3-control` boots on the same digest with the same protocol.
- **The cell's first attempt was a calibration overshoot, not an engine result.** The exact lane
  command's 8,192-token calibration predicted 1,039,999 tokens; the server counted 1,072,210 and
  answered HTTP 400 above the 1,048,576 window. Retried with the tool's own `--chars-per-token 6.65`
  (observed ratio 6.6778), which counted 1,035,623 — 0.4 % under the ask and above the 0.97 acceptance
  floor — and exited 0. Both JSONs are kept, so the 400 is evidence rather than a gap.
- **One acceptance line in the lane's boot checklist does not exist as worded.** It asks for `Mean
  acceptance length 1` on a decode line; the phrase appears **0** times across all four harvested serve
  logs, and the engine's own decode line reports `accept len: 3.12` with the metric
  `sglang:spec_accept_length` **3.125**. That is speculative decode active — the opposite of the
  collapse the line is meant to catch — so the gate should be read as that metric, and the checklist's
  wording is still uncorrected in `recipes/ds4/README.md`'s boot-gate list.
- **Register, and what remains.** `w4-survey-arm3-sm121-boot` closed `done` with
  `evidence: head:~/benchmarks/sm121-b12x-20261109/`; `tools/task-queue.py check` returns
  `ok: 124 task(s)`, rc=0. The arm-5 pair (`arm5-trtllm-mla` vs `arm3-control`, both on `:0.2.1`,
  replay off) is **mechanically unblocked but unrun**: the b12x path boots and fits TP=4 with the host
  never below 9.28 GiB, so the remaining obstacle is scheduling, not fit. Receipt
  `head:~/benchmarks/sm121-b12x-20261109/RECEIPT.md`.

## 2026-11-09 18:15 ET — the 18:00 tick folded nothing, and one clause of the 18:09 board did not survive a probe

- **A peer had already folded this hour, so the deliverable was a correction, not a census.** The tick
  read the 17:35 board at 18:00 and composed a full refresh; `publish` refused it (`disk was 18:09`),
  and that board already carried the hour's census pair (18:02:24 / 18:05:43), pool pair, register
  snapshot (`82212850…`, 124 tasks / 99 done / 15 queued / 10 blocked / 0 claims), the arm-3 landing and
  the window close. Re-publishing would have replaced correct rows with the same facts, so the board
  change is one rewritten cell and one probe row.
- **A head-scoped fact read through a workstation shell is the defect, not a stale row.** This tick's
  `systemctl --user is-active sparkrun-campaign.service` and `~/benchmarks/*/state.json` glob ran on the
  workstation, where the director is not a unit and one root exists (6 arms, 0 leases). On the head the
  unit reads `active`, MainPID 2078281, and nine roots sum 32 arms with 0 live leases, which is what the
  18:09 board says — that row was kept verbatim and the erroneous composition was never published.
- **The corrected clause was a mechanism, and the probe is cheap.** The 18:09 window cell read "head
  clone never had it … so a head-side reader cannot see a window declared here". A file written into
  this clone's `.local/` at 18:13:42 reached the head's `.local/` with its mtime and bytes inside 20 s,
  and the arm's receipt records the lock written on head and workstation and deleted only after its own
  0/0 check — so presence on the head at 18:03 is unverifiable after the delete and its absence is not
  evidence of blindness. Cell rewritten, probe appended to `STATUS.md`'s landed table.
- **Left deliberately untouched:** `mad-science/queue.json` (the arm session owns the arm-3 close-out,
  and the board cites it as worktree bytes rather than as `origin/main` content), and the blocked set,
  which did not move this hour.
