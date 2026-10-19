*(Moved verbatim from `mad-science/TODO.md` on 2026-10-13 — the TODO now references this file).*

## Session record

**2026-10-11 wrap (snapshot at 12:41 — superseded by the refresh below):** gate **384 tests OK** (skipped=1); all 23 shipped recipes validate plain; `bash -n` + `py_compile` clean. Independent audit of the day's recipe/mod/test changes: no blockers; all findings fixed (unconsumed `draft_model` removed, README typos, a negative control that proved nothing, stale `NOT boot-verified` prose in two recipe descriptions, raw node IPs masked to the `.34`/`.35` shorthand, plus a new `LiteralShaConsistency` guard). At that snapshot all work was committed and pushed.

**Landed after the wrap, same day (`882d463`–`0dfa881`):** the Ling needle probe and the Nemotron checklist closure folded into the lane docs; render-check fixes — the comment-inside-a-folded-command class and the inert-`defaults`-key class (which had shipped three times) are now guarded by `tests/test_recipe_placeholder_resolution.py`; the Nemotron `moe_backend` pin restored; coder-next `tensor_parallel` made to reach the command; glm inert defaults dropped.

**2026-10-12 refresh (verified in-tree):** gate re-run — **386 tests OK** (skipped=1), 23/23 recipes validate plain, `bash -n` + `py_compile` clean; working tree clean as of that check — this restatement is the only change on top of it (uncommitted as written). Push state before this edit: everything through 2026-10-11 is pushed, with one local-only commit, `5f3d83a` (README capability-icon row, 2026-10-12). The head node's registry clone sits at `9929e86` (2026-10-11 13:56) — its misses at writing are a guard test, recipe comment/doc edits, and that README row; run `sparkrun registry update littlecedar` before relying on the clone's shipped docs.

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
`tools/jev-decision-bench.py --selftest` exit 0. Commits `74252f6`–`28041c2`, pushed, head registry
clone updated to `28041c2`.

**2026-10-13 session — owner-announced TP=4 window (DeepSeek down; all six nodes free), agent-orchestrated.**
Headline (owner decision): the two shipped glm5 TP4 boots, then the three MiaAI-Lab/DeepSeek trial recipes, with
TP≤2 lane work on the spare nodes. Opened by committing the tree's unstaged flag-propagation pass (28 files;
recipe `tags:` dashed→snake_case + README Flag cells; the 27/27 derived-emoji==cell invariant verified) as
`5c9e438`.

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

**Commits:** all session work committed locally on `main`, unpushed (`f471bdd` onward; twelve through the extension session). All six nodes were left idle (0 containers) at the 10:00 ET close.
**Extension session (after the 10:00 ET wall — owner-approved open-item spend):** the ornith 397B
DFlash-vs-MTP A/B closed — **MTP ships** (42.55 ± 2.78 / 38.48 ± 1.91 t/s vs the DFlash head's
37.58 ± 4.45 / 33.64 ± 1.13, same-window on `.30`–`.33`, TP=4; the floating `:latest` was three
different builds and is now digest-pinned; commit `3524dca`). The owner un-deferred the two
media-gen arms: **Qwen-Image-2.1-Turbo** recipe (~11.4 s per 1024²/8-step image, NON-COMMERCIAL
banner, eval-only) and **LTX-2.5** ComfyUI runbook (two-stage, cold 100.3/90.1 s, gated prerequisite
documented) — commit `5c6795a`. A node-cache reclamation recovered ~1.85 TB from failed/deprecated
lanes (cybersec negatives, archived glm5 staging, orphaned caches; `dsv41-engram` staging kept for
the shipped arm-5 chain) — commit `39404eb`. Gate: **508 tests OK** (1 skipped), **31/31** recipes
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
effort tag) and six owner questions (#28–#33) in `# DECISIONS` — commit `dd4fea8`. Storage highlights:
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

**Landed 2026-10-15 (parallel slices).** *(GLM 5.3 TP=4 arm `34a2a2f` — boot deferred to a `.30`–`.33`
window; cybersec arms 3/4 vLLM routes `202f482` — arm 3's boot receipt landed later the same day (the
route answers, the checkpoint degenerates in every probe, no index row), arm 4's boot is still owed;
ornith 35B YaRN 1M arm `8bfb62d` — gate pre-registered in `attic/ornith/NOTES.md` §8 and still
unproven; pooling `BenchmarkingPlugin` + the silent-skip correction `6801c41`; storage positions +
`tools/cache-audit.py` `1d7d4ad`; the Engram log fix `a884dee`.)*

**Closed later on 2026-10-15** (each with its receipt, doc edit, and the gate re-run): the decision
lane's ensemble + ladder (`~/benchmarks/decision-ensemble-20261015/`), the qwen3 27B re-anchored
suite (`~/benchmarks/qwen3-27b-suite-20261015/`) and its TP=2 boot
(`~/benchmarks/qwen3-27b-tp2-20261015/`), the ornith 35B standard-suite pass, the qwen4 highcon k≥16
aggregate window (`~/benchmarks/qwen4-highcon-20261015/`, which earned that arm an index row and
closed its revival item), the cybersec weight prefetch on both nodes, and the four-boot nex vLLM
route receipt. The two-node window itself ran as `~/benchmarks/tp2-window.sh` (q1 / d1 / w1, serial by
construction, each arm capturing grants before stopping the container).

**2026-10-16 session — the register's planning round, then the sweep's first five tasks** (owner-ordered; every boot on the free `.34`/`.35`, the peer's `…-b12x-dspark-sglang-tp4` job on `.30`–`.33` untouched throughout). Commit `0dbc386`, pushed.

Opened with the planning round: all five `# DECISIONS` questions (the `🚀 fast` band, the warm DS4 runtime-cache lobes, the AEON-7 clause, `.34` residency, the pooling ladder pair) went to the owner in one batch, were answered, and folded — `# DECISIONS` is now empty, the bands landed in `README.md` §Model Flags, the calls are recorded in `STORAGE-POLICY.md` §5, and the two shipped profiles are `benchmarking/pooling-ladder-{embed,rerank}.yaml` (both loaded through sparkrun's own `BenchmarkSpec.load` before shipping).

**1 — runtime cache (the instant-tagged item).** Owner Q2 executed by absolute path, not by the sweep: the sweep's own `--older-than 2` would have taken **30 trees / 968.7 GB**, including ornith, RadixArk and IFM leaves a *shipped* recipe still produces. Removed the four `9a74d993` ds4 lobes, every `db95f94c` tree, and `ca6f25af` — the labquant model's **unpinned** leaf (103.4 GB each on `.32`/`.33`, 51.8 on `.34`), a row §2 never listed, found by deriving leaves with `sparkrun.core.runtime_cache.model_key`. **≈1.30 TB freed**; `.32`/`.33` back inside the 0.5 TB cap (734.8/732.1 GB → 406.2/403.4); the live job's `11826f49` leaf was never in the set. Receipt `~/benchmarks/storage-20261016/`.

**2/3/4 — pins: nine recipes, three boots.** Every arm riding a floating tag is digest-pinned; `recipes/` now holds **37/37** digest-pinned `container:` refs and zero tag-only. Method (relay-imported images carry no `RepoDigests`, so `docker images --digests` prints `<none>`): `docker buildx imagetools inspect <ref>` for the tag's digest, match that manifest's config digest to the container's `docker inspect .Image`, then confirm the ref resolves. **Two tags had moved**: `dgx-vllm-eugr-nightly` (2026-10-15 read `7717585a…`, today resolved `cc47adc1…`, engine `vLLM 0.32.0rc1.dev301`) and `dev-cu13` (`.34`/`.35` held `0a1ba33a…`, today `0b3e3970…`, engine `0.0.0.dev1+gc15edf314`). Boots: the 2B embed arm on `.34`, the nex sglang arm on `.35`, the qwen3 coder arm on `.35`. The qwen4 solo README's "the b12x build publishes no digest-pinnable alias" claim was **wrong** and is corrected.

**2-extra — the embed ladder.** First live use of the shipped profile: c1 38.2 / c2 45.5 / c5 85.2 / c10 102.4 units/s, 100/100 per cell — index row plus a shape footnote (never pool those cells with the lane's published c 1/4/8/16/32 numbers).

**4-extra — qwen3 coder-next.** Ladder C1 70.4 / C2 114.0 / C5 177.1 / C10 249.5 t/s @ d0 (decode rows read from the `--output`, σ 0.2/2.6/14.9/3.9) and tool-eval-bench v2.6.0 **90/100 (27/30), excellent**, deployability 89, responsiveness 87 — index cells filled and two lane-README rows added.

**5 — ornith 35B standard pass, re-run in full on one boot.** eval-suite 1.0.1 verdict `ok` (contract ok; house **37/37** = easy 19/19 + hard 18/18; needle **3/3 at each** of 32k/131k/262k, the top rung 256,394-token prompts at 142.5–142.9 s per probe), same-boot ladder **C1 101.8 / C2 153.1 / C5 217.4 / C10 244.2 t/s** @ d0 (per-stream 101.8/79.8/54.5/34.2, ttfr 303/582/1208/1973 ms — 2026-10-15's 158.2/220.4/249.9 reproduced within 3 %), tool-eval-bench **100** (15/15 pass). Both ornith arms' index C2/C5/C10 filled with a receipt footnote. Receipts `~/benchmarks/ornith-35b-suite-20261016/`.

**Cybersec correction (same boot as task 3).** On the engine the three SGLang cybersec arms now pin, the nex arm's CUDA device-side assert is **gone** — the server answers — but every greedy probe returns 64 identical `!` tokens, the same checkpoint-level degeneration the vLLM route showed on 2026-10-15. The failure follows the **checkpoint, not the engine**; the recipe's `metadata.caveats`, the arm-3 block in `recipes/cybersec/README.md` and `attic/cybersec/AGENTS.md` were corrected to that state.

**Two operational traps, recorded.** (a) My legs-runner waited on `while pgrep -f "tools/eval-suite.py"` — which never exits, because a **peer's day-old watcher loop** carries that string in its own command line; a booted arm sat idle on `.34` until the owner flagged it. Match a pid file or a unique marker, never a substring of a command line. (b) `pkill -f "<pattern>"` over ssh **killed the session carrying the pattern** (exit 255, no output) — use the `[.]` bracket trick so the pattern cannot match its own command line.

**Hygiene.** Every session serve stopped by explicit task id (`.34` and `.35` at zero containers, zero orphan volumes fleet-wide); `/tmp` scratch removed on the head and `.35`; `.30`–`.33` untouched. Working tree: only the second writer's `README.md` edit left unstaged. Head change: `~/.config/sparkrun/config.yaml` gained `core.external_plugins: true` and `plugins.paths` pointing at this repo's `plugins/`, so the shipped pooling ladder runs — the pre-change file is kept as `config.yaml.bak-pre-plugins-20261016` beside it, and the change is documented in `~/benchmarks/pins-20261016/head-config-change.md`. Gate: **606 tests OK** (2 skipped), all recipes validate plain, `bash -n` + `py_compile` clean. Receipts `~/benchmarks/{pins-20261016,storage-20261016,ornith-35b-suite-20261016}/`.

**2026-10-16, later pass — the README consolidation: `recipes/README.md` merged into the root `README.md`** (owner-ordered). The root keeps its content on top, the recipes table of contents moved above `# Recipe Format`, and the recipe index follows it (three relative links rewritten for the new depth — `recipes/glm/README.md`, `attic/glm/ARMS-MANIFEST.md`, `recipes/MECHANICS.md`); `recipes/README.md` is deleted. Commit `bd0ee59` (pushed) carries all 29 paths: the merged README, the deletion, 26 further repointed paths (path swaps only, plus section-anchored retargets where the referenced text moved — the two laguna recipes' `# Notes` cites now name `recipes/MECHANICS.md`), and `sparkrun-index-table-row-edit` relocated from the managed-global skills root into the tracked `.omp/skills/` tree.

**Fidelity.** A rebuild of the merged file from both sources plus the three rewrites is byte-identical except the final newline byte (`write`/`edit` strip trailing newlines from parameters and shell redirection is blocked); the pre-merge root file ended without one (`bd0ee59^:README.md`). Corrected 2026-10-17: the committed `README.md` is 25,314 bytes and ends with a newline; no test reads its bytes. `recipes/MECHANICS.md:4`'s "the former `recipes/README.md`" is left as historical wording; the register's last four cites (`mad-science/TODO.md`) were repointed by owner decision, one section-anchored (`README.md` §Cybersec). Link check: all 16 TOC anchors resolve and every ref-style link is defined.

**Gate.** 606 tests OK (2 skipped), all 37 recipes validate plain, `bash -n` + `py_compile` clean.

**2026-10-16, advisory bump — five explore arms to vLLM 0.30.0, three held by a device-free config preflight.** Commits `0c41f18` (bump) and `2a8243f` (holds); the peer's DS4.1 TP4 job on `.30`–`.33` untouched throughout, every boot on the free `.35`.

The `v0.30.0` pin resolved to the Docker Hub top-level manifest-list digest `sha256:8a69ffad…` (the 0.29.0 pin `c2914767…` re-derived the same way to confirm the method), and `0c41f18` moved five of the six `vllm/vllm-openai:v0.29.0` explore pins (humanizer, mellum, laguna-S, laguna-XS, qwen-image) while holding Kolibri in the same commit (its vendor plugin pins vLLM 0.29); OSV 23 records / 16 CVEs at 0.29.0 → **0** at 0.30.0).

**The preflight is the finding.** Before spending a boot, each pinned checkpoint's config was loaded device-free inside the new image on `.35` (`get_config(<repo>, trust_remote_code, revision=<pin>)`, HF **repo dir** mounted — never a `snapshots/<sha>` dir, whose `../../blobs` symlinks dangle outside it). Three of the five moved arms **cannot load their config at all** on 0.30.0 (vLLM-side in each case), and `2a8243f` names the mechanisms in-recipe: **mellum2.1-12b** — vLLM 0.30.0 registers its own `MellumConfig` (a `Qwen3MoeConfig` subclass) ahead of transformers' upstream class for model_type `mellum`; the stub's generic `convert_rope_params_to_dict` flattens the checkpoint's nested per-layer `rope_parameters` and `validate_rope` dies on the float (`AttributeError: 'float' object has no attribute 'get'`; reproduced device-free and live — the first boot died in that frame before any weight load); an `hf_overrides_kw={'rope_parameters': …}` override loads clean if the arm is to move before upstream fixes the stub. **laguna-{s,xs}-2.1** — vLLM 0.30.0's own `LagunaConfig` stub shadows the transformers class and `get_config` raises `'str' object has no attribute 'get'` (identical with `trust_remote_code` True/False); a 2026-10-17 correction probe showed the original attribution to transformers 5.17 was wrong — `AutoConfig.from_pretrained` builds both pins and keeps their nested rope intact — so the unblock is a vLLM-side fix or a stub-compatible re-pin, a lane decision, since the measured numbers belong to the old pin. Kolibri holds as before (vendor plugin pins 0.29).

**The boot that verifies the batch:** `humanizer-12b-vllm` on `.35`, task `sparkrun_17678da2f7107eb2_a4bf874feb5a` — engine `vllm 0.30.0`, container `.Image` == the manifest list's arm64 config digest `91d9b077…`, TTR port-open 252.4 s (0.29.0: 277.9 s), `/v1/models` → `jialinyyzz/humanizer` (8192 ctx, the pinned snapshot), a `/v1/completions` rewrite smoke (`system_fingerprint: vllm-0.30.0-372a78a5`, every number preserved), serve-log KV **371,031 tokens / 45.29×** (0.29.0: 370,597 / 45.2× — a clean cross-version match). qwen-image keeps the bump (its mod stages its own `transformers>=5.17` venv on the image's torch); its media-gen boot is the check. Receipts `~/benchmarks/bump-20261016/` (both boot logs, the preflight/probe scripts, models+smoke JSON, `NOTES.md`).

**jev-9b look (the item's second half).** `vllm/vllm-openai:glm53-flash@sha256:819ec9c0…` = vLLM **0.28.1rc1.dev580+g385dce36b** (base already recorded in `attic/glm/`); OSV: **24 records**, the delta against 0.29.0 being **CVE-2026-93840 / PYSEC-2026-3998** (cross-request logits corruption via `allowed_token_ids`, fixed in 0.29.0). The Hub tag still resolves to the pinned manifest-list digest (checked 2026-10-16), so moving the arm needs a new build from the tag's author — it stays as-found.

**Hygiene.** Both session serves stopped by explicit task id; `.35` at zero containers/volumes, `.30`–`.33` untouched. Removed `.35`'s uncited `img-pull-9a352a.log` (a 2026-10-15 pull by-product); kept the cited `tf-tp2-boot.log`/`hf-verify.log` and the live peer job's `/tmp/tmp.Ke4vikV633` JSON state. Gate re-run after the holds: **606 tests OK** (2 skipped), all 37 recipes validate plain, `bash -n` + `py_compile` clean.

**2026-10-17 session — three dual-node TP=2 tasks on the free `.34`/`.35`** (the peer's
`…-b12x-dspark-sglang-tp4` job on `.30`–`.33` was never touched; one TP=2 serve at a time).
Commits `f13c45b`, `18aa85b`, `d7c879b`, `d1d2c65`, `b567994`, `955b70b`, `a61890a`, pushed.

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

**What shipped** (`d8000bc`, `bff2259`): `recipes/ds4/deepseek-v4.1-flash-tensorfold-tp2-1m-sglang.yaml`
now serves `LibertAIDAI/DeepSeek-V4.1-Flash-1017-EXL3-2.9bpw@c178a01284fc5c0e859d8668cffaac81ca8f4042`
(public, 66 files), with the release's own Engram tables (189 GiB, built from 1017 shards 47/48) in the
standalone `hub/dsv41-engram` dir rather than inside the snapshot, and the launcher gained
`--require-engram`. Boot receipt `~/benchmarks/ds4-1017-ship-20261017/` (task
`5959b937d06087c6_3510a5e0d37d`): `/v1/models` = the 1017 id, `max_model_len 1048576`, TTR **62 s**,
`reserved 104.00 GiB`, `engram=/cache/huggingface/hub/dsv41-engram`, `rank cache reading
…/rank-cache/c178a012…/rank{0,1}of2-*.bin`, `weights in 26 s (from the rank cache)`, text clean,
vision **3/3** with a clean control.

**Two defects the boot exposed, both fixed.** (1) sparkrun stages mods from
`~/.cache/sparkrun/registries/littlecedar`, not the source tree: that cache sat at `2611a1d`, so the
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

**Committed this stretch:** `d60f53b` (GLM 3.0bpw promotion + boot), `c936dd3` (Nemotron archive +
LTX cells), `de71df7` (decision kev/d3), `1dbc79b` (K2 36B D2/E6 + the LTX wall correction). Gate:
778 tests OK (2 skipped), every recipe validates plain, `bash -n` / `py_compile` clean.

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

**Traps worth carrying.** (1) A killed boot leaves the TensorFold JIT build lock and the next start
waits on it instead of compiling — the lane's `run.sh` now sweeps it pre-exec. (2) sparkrun's readiness
probe can kill a healthy serve 8 s after uvicorn comes up while CUDA graphs capture; `--no-ready-wait`
plus a `/v1/models` check got the ornith boot through. (3) `--no-rm` does not preserve a container:
the job record says `executor_config.auto_remove: false` yet dockerd task-deleted it, taking the
traceback. (4) The KV pool is not the recipe's — the same ornith file booted to 1,203,041 / 282,227 /
69,281 tokens depending on a co-tenant, and at the low grant every 1M rung reads TRUNCATED, which is
indistinguishable from a window failure.
