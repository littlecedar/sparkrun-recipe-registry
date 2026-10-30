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
