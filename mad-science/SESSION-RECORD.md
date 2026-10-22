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
LTX cells), `de71df7` (decision kev/d3), `1dbc79b` (K2 36B D2/E6 + the LTX wall correction),
`de81835` (ornith YaRN 1M gate), `2f44e07` (qwen4 linear-replayssm), `5e57d66` (register swept
open-work-only). Gate at close, on the tree carrying all seven: **778 tests OK (2 skipped)**; no
recipe YAML, mod, tool or test changed after `1dbc79b`, so that run's recipe validation, `bash -n`
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
C2), so `c59f00d` ships it with `PREFILL_DECODE_INTERVAL: "0"` and a re-derived
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

**Every shipped recipe's `description:` moved to the top level** (`03b01cb`, all 59; `attic/` stays
frozen). `recipe list` / `recipe search` read `data.get("description", "")` at the top level only, so
the nested form listed as empty and could not be searched: at HEAD~1, 0/59 summaries carried a
description and a phrase from each description matched 2/59; after the move, 59/59. `recipe show` hid
the bug — the constructor falls back to `metadata.description` (`recipe.py:1256`). `maintainer:`
stays nested (the constructor reads it metadata-only), and the relocated prose is byte-identical
after a two-column dedent (0 unexpected diff lines, 0 text mismatches across the 59 files). Guard:
`_description_errors` in `tests/test_recipe_placeholder_resolution.py`, positive over every shipped
recipe plus a negative control. Note this record's earlier "778 tests ... still describe the tree"
line: the tree now carries that guard and the gate-tool change, and the gate reads **780 tests OK
(2 skipped)** at `da18528`.

**`gate-37111.py --thinking` never disabled thinking** (`9eee3a2`). "Default off" omitted
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

**ds4 deep search delivered** (commit `774cea9`). `mad-science/DS4-SPEEDUPS.md` — 631 lines, 34 dated
primary sources, 15 explicit UNVERIFIED markers — ranks 11 candidates plus a precondition (GPU
clock-latch audit), each with mechanism, expected effect, the carrying flag/artifact, a GB10
evidence label, and a pre-registered interleaved A/B with its falsifier; it also carries a
checked-and-rejected table so the rejected ideas do not return as suggestions. No boot was run: the
item's deliverable was the plan. `recipes/ds4/README.md` gained the upgrade-candidate section the
directive required (three arms runnable on the `.34`/`.35` pair now, eight TP=4-only candidates, the
rejected set), and the runnable subset became its own register item.

**Register corrections.** The Kokoro TTS entry said the arm "was never built", but
`recipes/decision/kokoro-82m-tts-cpu.yaml` has shipped since `025ca2a` (digest-pinned image,
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

**Cybersec arm 5 — 5/5, closed (commit `3fbb5e0`).** The 2026-10-20 interruption at 107 of 1,240
questions was re-run from a fresh TP=2 boot (`2f9a8f3e60a51ee4_3510a5e0d37d`, TTR HTTP-ready
59.407 s) with no job cap: **1037/1240 = 83.6 %** in 3,887 s (3.133 s/question), 0 transport errors —
simple 376/400, multiple 188/200, parallel 181/200, parallel_multiple 177/200, irrelevance 115/240.
With house 37/37, needle 3/3 at every rung, ARC 188/200 and GSM8K 197/200 from the earlier legs, the
arm is complete. Receipt `~/benchmarks/cybersec-arm5-tools-20261021/REPORT.md` merges the four
2026-10-20 legs; the pair was drained afterwards. BFCL is not resumable, so this leg cost a full
re-run rather than a resume.

**Ornith SGLang 0.5.18→0.5.21 — the recorded blocker did not exist, and all three arms validated
(commit `9d67131`).** The 2026-10-10 scan's claim that the Mamba/SWA radix-cache args "were removed
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

**Explore LTX-2.5 T2V — the probe is now a recipe (commit `d61cb30`).**
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
instrument's `runs/2026/10/*.md`, `probe.json`, `ladder.log`, `serve.log`); commit `39a4f00` (recipe,
lane section, root index row).

`autotrust/JEV-27B @14b42526` booted solo on `.35` (53.79 GB, 14 files, `vllm-openai:glm53-flash` at
engine `0.28.1rc1.dev580+g385dce36b`) and **does not ship**: **66.8 % (1337/2000)** against JEV-9B's
**67.0 % (1340/2000)** is three decisions and 0.15 pp — a tie, below the lane's strictly-beat rule, so
no README or index row and no status change. Boot wall 1244 s, of which ~660 s is CUDA-graph capture
for 102 graphs (budget ~21 min cold, ~13 min warm with the compile cache); ladder c1 2.912 / c2 2.974
/ c5 4.351 / c10 4.488 req/s with no useful scaling past c2, because the `--mamba-cache-mode align`
path serializes decision prefill. KV 805,546 tokens (24.58× at 32k), so the mamba page pool binds
before `max_num_seqs`. Receipt `~/benchmarks/jev27-20261021/REPORT.md`.

**Muse Glimmer 30B: the checkpoint, not the pack (`3c3c134`, closing `0df411c`).** The bf16 control
(`meta-models/Muse-Glimmer-30B @7af58019`, same drafter, same `sglang:v0.5.21` digest, same flag line
bar `mem_fraction_static 0.80`) answers `nurkrpas` on hard-rev exactly as the NVFP4 pack did — house
36/37, easy 19/19, same item, same string — which makes the weights the cause and exonerates the pack,
so no repack is worth trying. C1 is 12.1 t/s on bf16 against the pack's 20.2 (the bandwidth of 52 GB
of bf16 weights), with DFLASH accepted at block size 5. The arm is out of both trees; the route, flags
and numbers live in `attic/explore/AGENTS.md`.

**flash-next staging, corrected (`955c96a`).** The lane README recorded the 183.5 GB export as
reclaimed from every node on 2026-10-14, which made a per-node re-fetch look like the boot's remaining
cost. Re-verified 2026-10-21: `.34` and `.35` have held it complete since the 2026-10-15 staging
(18/18 shards, 183.48 GB, zero bytes fetched), so only a boot receipt is outstanding. `.35` also
carries **78.06 GB of orphan `.incomplete` blobs** from that attempt, named for the next storage pass.

**The docs moved to sparkrun 0.4.2 (`e85c786`, `745ebd3`).** `AGENTS.md` and `recipes/MECHANICS.md`
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

**flash-next closes refuted, on two different gates (`b85f611`, `510215b`, 2026-10-21).**
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
`recipes/explore/nemotron-3.5-lightning-30b-a3b-nvfp4-vllm.yaml`, commit `3800002`, receipt
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
with no NVFP4 export at all. `mad-science/EXPLORE-CANDIDATES.md` now records the closures and the
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
(3) **The Qwen-Image schedule path is guarded:** the launcher mod takes a `sigmas` list (`f610cba`) and
schedule selection was extracted into a pure `schedule_kwargs(req, shipped)` with 13 cases and **three
negative controls that must go red** — the pre-fix forwarded-field function, index rounding instead of
value interpolation, a dropped `sigmas` kwarg — run against temp-dir shadow copies (`75fb9fc`). The suite
reads 752 with that module moved aside and **765** with it present. (4) **AGENTS.md counts re-measured**
rather than adjusted: 52 tracked recipes (53 files on disk) in 11 dirs, 29 guard modules, 765 tests with
2 skips, 12/52 strict, 18 tools, 35 benchmark profiles, 53/53 folded command templates, and the attic
re-counted per directory (where the IFM line's "two retired 7B arms" became three).

## 2026-10-22 — the register becomes a board; the refresh, engine and CI block

*(Moved out of `mad-science/STATUS.md` on 2026-10-22 01:58 ET, when that file was cut down to a status board and the queue moved to `mad-science/TODO.md`. Times are the ones each row was recorded with; nothing below is re-measured.)*

### Landed (2026-10-22) — one row per commit, with the evidence

| commit | what changed | verification | receipt/evidence |
|---|---|---|---|
| `6a03329` (00:48 ET) | ornith SGLang 0.5.21: the blocker marked refuted and the killed worker's two staged-plan state claims retired (`mad-science/TODO.md:398` is the progress paragraph of the closed item at `:396`; the CLOSED paragraph `:399-421` records the rest) | the bump shipped as `9d67131`, so the claims its own later writes falsified are gone | `attic/ornith/AGENTS.md`, `recipes/ornith/README.md` §"Engine bump to SGLang 0.5.21" |
| `3b8c2c8` (00:51 ET) | `recipes/ornith/README.md`'s three live runtime rows (`:111`, `:193`, `:275`) still advertised `dev-cu13@9a352a35…` and "sglang v0.5.18" after the 0.5.21 bump — corrected | the `9d67131` diff record at `:449-455` is history and stays verbatim | `recipes/ornith/README.md` |
| `af8c88f` (00:53 ET) | `ARG TENSORFOLD_REF` made mandatory in `recipes/ds4/Dockerfile.tensorfold-dsv41` (it defaulted to 0.6.3 `d5d7bb38…` while the shipped ds4 image is 0.6.6 `3825f62…`), fail-closed `RUN test -n`; `recipes/ds4/README.md` gained a per-image Rebuild block; the one documented no-arg build command (`attic/ds4/AGENTS.md:2336`) now passes its ref | a plain rebuild can no longer silently pick a different engine | `recipes/ds4/Dockerfile.tensorfold-dsv41` |
| `b39bf63` (01:03 ET) | EXL3 pack re-pin `c178a012…` → `0be63c3337efbb2a0061d5b8bb4006fa186d433f`, booted on `.34`/`.35` (task `sparkrun_a9804d09ec5e137d_3510a5e0d37d`) | `/v1/models` answers `LibertAIDAI/DeepSeek-V4.1-Flash-1017-EXL3-2.9bpw` at `max_model_len` **1,048,576**; **TTR 590 s cold** (318 s weight re-conversion + three CUDA extension rebuilds; **no warm second boot was measured, so no warm TTR is quoted**); thinking off → `PINEAPPLE-42`, `finish_reason` stop, 0 reasoning tokens; thinking on → `reasoning_content` + `391` = 17×23, DSpark accepted 13/31 drafts; distribution a 9.1 s blob-cache hit; **the snapshot's new `chat_template.jinja` is IGNORED** by the `--vision` overlay (`launcher.py:263`) — served sha `297be886…` is the mod's, snapshot's `2ed8bc33…` absent, and adopting upstream's would require changing the overlay (recorded decision) | pin sweep row below |
| `5655019` (01:05 ET) | four unpinned embed/rerank checkpoints pinned to that day's Hub heads: `Qwen/Qwen3-VL-Embedding-2B` `9f2f7e71…`, `gonuit/Qwen3-VL-Embedding-8B-AWQ-4bit` `5c4cca00…`, `Qwen/Qwen3-VL-Reranker-2B` `4bd860ac…`, `Qwen/Qwen3-VL-Reranker-8B` `b212dc8c…` | every pin == head, so no served byte changes; strict-validate moves 12/52 → 16/52 and `unpinned-model-revision` eleven → fifteen, because these arms pass the prepared path and the finding is the lane's known false positive | pin sweep row below |
| `04885ed` (01:09 ET) | qwen4 TP=4 arm repaired to the shipped chain: bare `revision:` key sparkrun ignores, the pre-re-cut `7c4f1bc1` pin, 3 of the 5 required mods, `moe_runner_backend auto` (FLASHINFER_TRTLLM, dead on SM121), `mods:` entries resolving against the recipe directory; now the shipped TP=2 arm with `tensor_parallel 4`, `min_nodes 4`, NEXTN dropped, `port_timeout_s 3600` | `tests/test_qwen4_recipes.py` diffs the two arms with a negative control per defect class, so the drift cannot return | `attic/qwen4/AGENTS.md`, `qwen3.8-flash-next-labquant-tp4-sglang.yaml` |
| `bb5a46e` (01:10 ET; content landed as `df9ee74` 01:09 ET) | the 2026-10-22 refresh entry and the quartet correction; **model-pin sweep over all 52 tracked recipes** (47 distinct Hub repos, one API call per repo, authenticated as the `littlecedar` user): 31 current, 5 stale-weights, 5 stale-docs, 6 unpinned, 0 unresolvable — the two DeepSeek-v4.1-Flash artifacts split: `deepseek-ai/DeepSeek-V4.1-Flash-1017` (TP=4 knapcio pack, also the Engram tables' `DEFAULT_REVISION`) is pin == head (`1bae0e10…`, 2026-10-17) so production weights are unaffected, while `LibertAIDAI/…-EXL3-2.9bpw` (TP=2 TensorFold pack) was 4 commits behind on `README.md` + a new `chat_template.jinja` and zero safetensors; **container/runtime sweep**: 26 distinct container refs across shipped recipes, all digest-pinned, our seven own-namespace images enumerated against their Dockerfiles, and the mod- and launcher-level Hub pins (`drowzeys/…` `87bb9850`, `drowzeys/keys-…` `a9cf9de`, launcher `DFLASH2_REVISION` `bf582e4e`, Engram `DEFAULT_REVISION` `1bae0e10`) all current and agreeing with the recipe pins that govern them, so no cybersec arm serves drifted weights | pin and container counts above are the sweep's own result | this file; `recipes/` tree at `5655019` |
| `bb5a46e` (01:10 ET, recorded there; no code commit) | `recipes/ds4/Dockerfile.knapcio-dsv41`'s `ARG BASE_IMAGE=lmsysorg/sglang:dev-dsv41` — the only floating build input in the shipped tree — pinned to `sha256:4a5d132a…` (tag kept); rebuild on `.30` (native arm64, 208.8 s) pushed as `littlecedar/dgx-spark-dsv41:canary-roce-20261022` = `sha256:0cbe228a8788ec06472dd2dc5cd31acb117ec5ba5101f2442d32e54d2ae5b8ea` | config identical (entrypoint, cmd, env, healthcheck, labels; 91 layers, layers 0–69 identical); content diff is four recompiled `__pycache__/*.pyc` plus 6,707 hash-equal files — **behavior-identical but NOT byte-reproducible**, so the shipped `acfc331a…` stays pinned | `recipes/ds4/Dockerfile.knapcio-dsv41` |
| `bdc51b9` (01:12 ET) | removed a quoted owner answer that was never given (`"switch now."`); the verbatim grant `"You have .30-.35 available for you to work on the TP=4 queue."` replaced it, and both TP=4 questions stay open | sweep of the file for other invented attribution on 2026-10-22 found none; the 2026-10-21 entries keep their own recorded answers. The quartet stop is attributed in Alerts, from the owner's own 2026-10-22 ≈01:28 ET relay | this file |
| `df2c259` (01:15 ET) | `vllm-sr/d3-edge` head-revision probe recorded and the vendor pin kept: `18d61df7…` → `c454ee39…` on **both** pin sites (`model_revision:` line 3, literal `--revision=` in `command:` line 50), booted twice (`.31` as shipped, `.35` with `-e HF_HUB_OFFLINE=0`), **reverted** | `/health` 503 `{"status":"failed","reason":"VerificationError: golden answers differ from the reference"}`, `/v1/models` `ready:false`, golden `{checked:3, matched:1, reference:"cpu"}` — the **same 3-checked / 1-matched result the README recorded at the old pin on 2026-10-18**, so the aarch64-vs-x86 divergence is revision-independent; no `/v1/systemone` round-trip in either boot (`503 not_ready`); `18d61df7` is the `d3-edge v3.1.0` release commit (2026-10-11) and `c454ee39` a post-release card/eval commit (2026-10-17); both safetensors (1,215.7 MB) byte-identical | `~/benchmarks/decision-d3-repin-20261022/` (head) |
| `ee8c3e2` (01:16 ET) | the d3-edge verdict folded into the decision lane item, quartet duty opened as `TODO.md` #46, and two inherited 752-test counts corrected to 782 | gate `782 tests OK` (2 skipped) at `df2c259` | `mad-science/TODO.md`, this file |
| `5ce1d02` (01:22 ET) | stock upstream `llama.cpp` image and the lane's engine target pinned: `recipes/explore/Dockerfile.llamacpp-upstream` with pinned CUDA base digests, a required `LLAMA_REF` with no default, and gates that reject the `b2e5e9b` failure mode | `docker build --check` clean; stock upstream `9df0b73c` (2026-10-20) carries Mellum MTP, `kolibri1` and `121a-real`/sm_121 upstream-native, and only the decision2 pack still needs its fork (its GGUF declares `qwen35` with 330 tensors where upstream expects 320) | `recipes/explore/Dockerfile.llamacpp-upstream` |
| `9bce38b` (01:34 ET) | explore vLLM arms re-pinned to `v0.32.0` for the CVE reason, `container:` pins moved to index digest `befccf0e…` (arm64 child `6ff5ff0d…`) | Laguna-XS on `.34`: TTR **282 s**, `/v1/models` served `poolside/Laguna-XS-2.1-NVFP4` at 262,144, KV 41.87 GiB → **1,413,525 tokens (5.39×)** against v0.29.0's 41.56 GiB / 1,403,263, chat 200 `finish_reason=stop` in both modes; the qwen-image arm on `v0.32.0` wrote a **byte-identical PNG** (`e24f6e3a…`) to its v0.30.0 reference, both images on torch 2.13.0+cu130, so the bump moved the vLLM wheel and not the torch build | `recipes/explore/` |
| `5d767de` (01:36 ET) | qwen-image request path guarded and a latent shipped bug named: `recipes/explore/mods/qwen-image-2.1-turbo-launcher/server.py` raised `NameError: name 'sigmas_used' is not defined` on **every** `POST /generate` since `f610cba` (the `schedule_kwargs(...)[0]` unpack) — the 2026-10-21 sigmas feature shipped non-working while the suite stayed green, because the resample test exercised `schedule_kwargs()` and never `run_generate()`; the vLLM `v0.32.0` thinking contract recorded (Alerts); a 1,024-token budget with thinking on returns `finish_reason=length` (1,933 completion tokens for a one-line arithmetic prompt), so **4096 is the floor**; Laguna-M.1's pin moved for the CVE and is labelled **BUMPED, NOT RE-BOOTED** | fixed, re-booted, and a new test drives `run_generate()` with stubbed torch/pipeline — the negative control reproduces the `NameError` on the pre-fix artifact and passes after | `recipes/explore/mods/qwen-image-2.1-turbo-launcher/`, `recipes/explore/poolside-laguna-m1-nvfp4-vllm-tp2.yaml` |
| `d8c1339` (01:38 ET) | the repo has CI: `.github/workflows/gate.yml` (push/PR — `uv sync --frozen` with a C toolchain for `netifaces`, the unittest suite, per-recipe `sparkrun recipe validate` that prints `SKIPPED: sparkrun not installable in CI` rather than failing, `bash -n`, `py_compile`, `__pycache__` cleanup), `refresh-sweep.yml` (daily cron + dispatch: runs the sweep, uploads artifacts, upserts one open issue labelled `pin-drift` with distinct titles for exit 1 "pin drift found" vs exit 2 "sweep could not run", and never edits a recipe unless the `apply` input is set, then only prints the boot checklist), `llamacpp-engine.yml` (weekly report of our refs vs upstream `ggml-org/llama.cpp` with `behind_by` and four feature gates; its arm64 `build` job is gated on `vars.ARM64_RUNNER_ENABLED == 'true'` because **no self-hosted runner is registered**, stated in the file, `AGENTS.md` and `README.md`); `AGENTS.md`'s "No CI … no `.github/`" claim replaced with what is true, counts refreshed to 31 guard modules / 806 tests (2026-10-22) | `tests/test_ci_workflows.py` (22 tests) guards the contract; CI never bumps a model pin — lane policy stands | `.github/workflows/`, `tests/test_ci_workflows.py` |
| `a6c0cd7` (01:42 ET) | `tools/refresh-sweep.py`, the pin-drift survey the nightly CI job gates on | the same survey `refresh-sweep.yml` runs, so CI and the operator share one implementation | `tools/refresh-sweep.py` |
| `f6cec8e` (01:46 ET) | the sweep's classification corrected and holds made declarable: a digest-pinned `FROM` now counts as **build-input-current** rather than stale (genuinely stale build inputs **4 → 1**); `--accept-file` with **8 declared holds** in `tools/refresh-sweep-accepted.json` and `stale-acceptance` gates so a hold cannot silently outlive its reason; the ornith 397B `model-unrevision` row closed by pinning `b4864e44…` | gating drift rows **24 → 12**; suite 852 | `tools/refresh-sweep.py`, `tools/refresh-sweep-accepted.json` |

### Alerts detail (2026-10-22)

| what | measured | when | by whom | state |
|---|---|---|---|---|
| **Quartet down — the 2026-10-21 entry's "TP=4 serve is untouched and healthy" was stale** | 0 containers on `.30`–`.33`, no `:8000` listener on any quartet node IP, head `127.0.0.1:8000` refusing connections, no vllm or sglang process on the host, gateway `deployments: []` (last `sparkrun sync` 04:39Z) | stop at 2026-10-22 **00:38:39 ET**; censuses **≈01:05 ET**, then again minutes later; attribution relayed by the owner **≈01:28 ET**; answered **01:46 ET** | two independent workers | **cause DETERMINED: the owner stopped the DeepSeek model on `.30`–`.33`** at 2026-10-22 00:38:39 ET, consistent with the same owner's node grant that put `.30`–`.35` on the TP=4 queue — the quartet being free is deliberate, not an incident and not a fault. The four negatives corroborate that nothing was lost rather than standing in for a cause: no OOM, no Xid, no node reboot, model/runtime caches still warm (the 2026-10-14 `stop --all` fingerprint). **Answered 2026-10-22 01:46 ET — production stays stopped, the quartet keeps measurement duty** (verbatim "keep the quartet measurement duty as planned."); `#46` is folded into its work items in `mad-science/TODO.md` |
| Descriptor mistaken for liveness | `@littlecedar/deepseek-v4.1-flash-knapcio-tp4-1m-sglang`, served id `deepseek-ai/DeepSeek-V4.1-Flash-1017`, TP=4, cluster `sparkrun_a2e141223b52793c_e11d626ec2c6` — static since 2026-10-18 | censused 2026-10-22 **≈01:05 ET** | the 2026-10-21 entry trusted it and was wrong | corrected: only containers, listeners, gateway `deployments` and host processes answer "is it up" |
| Foreign or unowned container on a quartet node | `sparkrun_6c7626d237f22cdd_68907e0cb1d8_solo` on `.31`, relay-imported image | 2026-10-22 **≈01:07 ET** (head local clock), after both censuses | **reported by the re-pin campaign, unverified here** | consistent with the node grant and measurement duty; not the missing serve |
| Known-bad pin in service | vLLM `v0.29.0` (CVE-bearing) under the two Laguna arms; `v0.30.0` under the three media-gen arms | swept 2026-10-22, committed **01:10 ET** (`bb5a46e`) | runtime sweep | re-pin campaign in flight (In flight); the arms still ship the old pin |
| Gate red, then cleared | `782 tests, 2 failures, 2 skipped` — two `tests/test_k2_7b_recipes` container-pin assertions, one arm on `lmsysorg/sglang:v0.5.22-cu130@sha256:e3a4f060…` while its guard asserted the `v0.5.20-cu130` tag and `sha256:06e4f2ed…` digest | failed before **01:15 ET**, cleared at the pin that landed with `df2c259` (01:15 ET) | this register | cleared when the pin landed; the campaign itself still carries no verdict |
| **The llama.cpp image the tree depends on is a stalled publisher** | `scitrera/dgx-spark-llama-cpp` `:latest` == `b10549-cu131` == 2026-08-21, and that is the tag sparkrun's llama-cpp runtime advertises | recorded 2026-10-22 **01:21 ET** (`a93651e`) | pin sweep | **standing risk, no verdict**: every llama.cpp arm in the tree is frozen ~2 months behind upstream; the stock-upstream route is a Deferred row, and nothing about a shipped llama.cpp arm changes today |
| **vLLM `v0.32.0` changes the thinking contract** | thinking arrives at **`message.reasoning`**, not `message.reasoning_content`, and `usage.completion_tokens_details.reasoning_tokens` reads 0 while emitting thousands of characters | found 2026-10-22 **01:36 ET** (`5d767de`) | the qwen-image guard worker | **open for every future check, not just this arm**: the lane's old-shape checks read the reply as "all-empty", so any harness reading `reasoning_content` or counting reasoning tokens against vLLM `v0.32.0` reports a false empty |

### Campaign detail as of 01:53 ET

*(The board carries one row per node group; this is the per-campaign version, including the two closed rows.)*

| campaign | nodes | arms | started | est | state |
|---|---|---|---|---|---|
| campaign | nodes | arms | started | est | state |
|---|---|---|---|---|---|
| SGLang `v0.5.22` re-pin | `.35` | 6 — three ornith (off `v0.5.21`), three IFM (off `v0.5.20-cu130`); arm A (35B dflash2) booting now | 2026-10-22, start time not recorded | 4–8 h, derived from the 0.5.21 bump receipt (~4 h for three ornith arms on a free pair, same shape per three-arm lane) | index `e3a4f060…` and arm64 child `06441be3…` resolved; the K2-7B pin landed and its guard is green; **no verdict** — updated 01:48 ET |
| vLLM `v0.32.0` re-pin — **partly verified** | `.34` | 5 — two Laguna (off CVE-bearing `v0.29.0`), three media-gen (off `v0.30.0`); Laguna-XS measured, M.1 not re-booted | 2026-10-22 01:34 ET (`9bce38b` pin) | 4–6 h, derived from the media-gen receipts (≈4 min TTR per arm) plus the Laguna-M.1 TP=2 boot + suite receipt | **done:** Laguna-XS (TTR 282 s, 1,413,525 tokens = 5.39× the v0.29.0 pool) and the media-gen byte-identical PNG. **Not done:** Laguna-M.1 is **BUMPED, NOT RE-BOOTED** — its 2026-10-20 numbers stay v0.29.0 measurements — and its TP=2 phase is deferred for lack of a free pair. **No verdict on the campaign** — updated 01:48 ET |
| TP=4 block — **running, resumable** | `.30`–`.33` | qwen4 **W6** then **W12**, the **ds4 TP=4 candidates**, then the **four-node suite legs** | 2026-10-22, start time not recorded | 20–28 h block | **content settled 2026-10-22 01:52 ET** (owner: "run everything you can. We can always resume later if we need to pause TP=4 work.") — so the block runs in that order and **a pause is never a loss**; duty settled 01:46 ET (quartet on measurement, production stays stopped); W6 boot in flight; **not restated as finished** — updated 01:53 ET |
| Mellum MTP feasibility probe — **finished, negative** | — | shipped Q4_K_M main + `mtp-Mellum2.1-12B-A2.5B-Thinking-BF16.gguf` | 2026-10-22, found by the pin sweep recorded 01:10 ET | — | **NOT FEASIBLE on the shipped pin.** Needs llama.cpp `b11747` (2026-10-19) or newer: at our `b2e5e9b`, `src/models/mellum.cpp` has no `nextn`/`graph_mtp` and `llama-model.cpp`'s MTP-aware KV path lists QWEN3NEXT / QWEN35 / QWEN35MOE / BAILINGMOE3 / NEMOTRON_H_MOE but not MELLUM; the support lands in `b2e5e9b..b11747` as `nextn_flags`, the `nextn.eh_proj` / `enorm` / `hnorm` / `shared_head_norm` loads and `graph_mtp`. Found by the 2026-10-22 pin sweep, which saw the Mellum GGUF repo publish an additive MTP head at `4159d684…`. Our engine is `b2e5e9b` and `scitrera/dgx-spark-llama-cpp` has published nothing since `b10549-cu131` (2026-08-21). Pre-registered for the day the gate is met: existing Q4_K_M main + `-md mtp-Mellum2.1-12B-A2.5B-Thinking-BF16.gguf --spec-type draft-mtp --spec-draft-n-max 1`, falsifier "C1 > 114 t/s n=5 vs 111.9 ± 0.3, accept-len recorded, no C2/C5 regression, house 37/37 and bfcl 88.3 % held". The shipped main file is byte-identical (`ecc4d5b8…`) at both the pin and the head, so **nothing about the shipped arm changes** — updated 01:48 ET |
| pin sweep in CI (`refresh-sweep.yml`) | — | the 52-recipe sweep | 2026-10-22 01:38 ET (`d8c1339`), sweep tooling 01:42 ET (`a6c0cd7`) and 01:46 ET (`f6cec8e`) | daily cron | workflow landed and guarded by `tests/test_ci_workflows.py`; the sweep's own survey now reads **12 gating drift rows (24 before `f6cec8e`)**, **8 declared holds** in `tools/refresh-sweep-accepted.json`, and **1 genuinely stale build input** (4 before — a digest-pinned `FROM` is current, not stale); the ornith 397B `model-unrevision` row closed by pinning `b4864e44…`; **not yet run on GitHub, so no daily `pin-drift` issue exists yet** — updated 01:53 ET |

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
| **Stock-upstream llama.cpp image (source ref ≥ `b11747`)** — recorded 2026-10-22 01:21 ET, image Dockerfile added 01:22 ET (`5ce1d02`) | a build host window: `recipes/explore/Dockerfile.llamacpp-upstream` exists with pinned base digests, a required `LLAMA_REF` (no default) and gates against the `b2e5e9b` failure mode, `docker build --check` clean; the build and the Mellum MTP A/B are pre-registered (falsifier: C1 > 114 t/s n=5 vs 111.9 ± 0.3, accept-len recorded, no C2/C5 regression, house 37/37 and bfcl 88.3 % held) | `recipes/explore/Dockerfile.llamacpp-upstream`, `recipes/explore/` |
| **Laguna-M.1 re-boot on vLLM `v0.32.0`** — recorded 2026-10-22 01:36 ET (`5d767de`) | a free node pair: `.34` is on the vLLM re-pin and `.35` on the SGLang `v0.5.22` re-pin | `recipes/explore/poolside-laguna-m1-nvfp4-vllm-tp2.yaml` (labelled BUMPED, NOT RE-BOOTED) |

### Risks carried out of the register

| risk | trigger | mitigation |
|---|---|---|
| **BFCL is not resumable** | a drain mid-leg costs the whole 1,240-question run — the 2026-10-20 interruption (time not recorded) forced a fresh boot and a full re-run on 2026-10-21, which closed it at 83.6 % (`3fbb5e0`, 03:00 ET) | drain before a leg, not during one |
| **Buffered logs look like stalls** | a question count frozen for tens of minutes while the serve decoded | read liveness from the serve log, never from the count alone |
| **Pair-bound stall** | the 15–25 h pair block holds both test nodes, so nothing single-node runs during it | schedule single-node work outside the block |
| **Stopping a serve can delete its evidence** | `sparkrun stop` bypasses `--no-rm` and removes the container with its in-container serve log — it cost the 9B `.35` log on 2026-10-21 (time not recorded) and it took the quartet's TP=4 serve log when the owner stopped the serve at 2026-10-22 00:38:39 ET | stop by cluster/task id and `docker cp /tmp/sparkrun_serve.log` out first |
| **A CPU decision pass is a four-hour window, not two** | Nox-4B took 14,066 s (35.2 s/case) where a three-case probe predicted 8,760 s, because the first cases are cheaper than the mean | price a CPU arm from a wide probe or the lane's own per-arm history |
| **The head's `127.0.0.1:8000` was the production TP=4 serve** | a probe that addresses loopback measures production, not the arm; as of 2026-10-22 01:05 ET that loopback refuses connections because the quartet serve is down, and refusing loopback is not evidence of a misconfigured probe | always use the node's IP root |
| **Address hygiene is done for the tree, not for history** | tracked files are masked (71 lines, 22 files) but pushed history was deliberately not rewritten, so older commits still contain the addresses | do not quote older revisions as clean; rewriting needs a force-push |
| **A quartet descriptor proves the role, not liveness** | `@littlecedar/deepseek-v4.1-flash-knapcio-tp4-1m-sglang` has been static since 2026-10-18 (time not recorded) | check containers, listeners, gateway `deployments` and host processes |
| **The head's `.git` is syncthing-shared with a second writer** | 11 `.git/index.sync-conflict-*` files have accumulated there, and an edit that syncs before the pull aborts a fast-forward | repair with `git checkout HEAD -- <path>`, never `git checkout -- <path>`, which restores the stale index blob and loops |
| **Our llama.cpp publisher is stalled** | `scitrera/dgx-spark-llama-cpp` `:latest` == `b10549-cu131` == 2026-08-21 is what sparkrun's llama-cpp runtime advertises, so every llama.cpp arm in the tree is frozen about two months behind upstream and a feature the upstream engine already carries (Mellum MTP at `b11747`+) is unreachable | build from stock upstream through `recipes/explore/Dockerfile.llamacpp-upstream` (pinned bases, required `LLAMA_REF`); `llamacpp-engine.yml` reports our refs against `ggml-org/llama.cpp` weekly so the drift is visible instead of discovered late |

### History carried out of the old register

| when (ET) | head commit | what landed | receipts |
|---|---|---|---|
| 2026-10-22 01:16 ET | `ee8c3e2` | this entry — the refresh, the quartet correction, the d3-edge revert, the register fixes; detail in Landed above | `~/benchmarks/decision-d3-repin-20261022/` |
| 2026-10-22 01:46–01:47 ET | `eb02529` + this pass | both owner calls answered and folded: `#46` (quartet keeps measurement duty, production stays stopped — folded as a dated advisory note on the qwen4 and ds4 TP=4 items and removed from `# DECISIONS`) and the TP=4 offsite switch (answer "rephrase the question", executed as `#47`, which asks to confirm or narrow the block's content) | `mad-science/TODO.md` |
| 2026-10-22 01:52–01:53 ET | `96b0f2b` + this pass | `#47` answered and folded as the run-everything directive on the TP=4 items (full W6 → W12 → ds4 TP=4 → four-node suite order, resumable, so a pause is never a loss); `# DECISIONS` now reads 0 open; the sweep tooling (`a6c0cd7`, `f6cec8e`) registered with its row and hold counts | `mad-science/TODO.md`, `tools/refresh-sweep.py`, `tools/refresh-sweep-accepted.json` |
| 2026-10-22 01:22–01:38 ET | `5ce1d02`, `9bce38b`, `5d767de`, `d8c1339` | the engine/CI block: stock upstream llama.cpp image added, explore vLLM arms re-pinned to `v0.32.0` (Laguna-XS measured, media-gen PNG byte-identical), the qwen-image `NameError` guard plus the reasoning-contract finding, and CI (gate, nightly pin sweep, weekly llama.cpp engine report); detail in Landed above | `recipes/explore/Dockerfile.llamacpp-upstream`, `.github/workflows/` |
| 2026-10-21 20:15 ET (commit `2e4a775` 20:04 ET) | `2e4a775` (remote tip then) | both queues empty and both nodes idle: 0 running and 0 exited containers on `.34`/`.35`, the 18:49 highcon probe finished and gone, the earlier leftover sglang container from the 07:52 Muse boot logged; gate 765 tests OK (2 skipped; 752 → 765 with the Qwen-Image guard), 52/52 tracked recipes plain-validate (0 errors, 53 files on disk), 12/52 `--strict`; the quartet claim in that entry is stale (Alerts) — the owner stopped that serve at 2026-10-22 00:38:39 ET | `~/benchmarks/_leftover-logs/43acfc12bcc4-sglang-20261021.log` |
| 2026-10-21 20:00 ET (commit `3800002` 19:49 ET) | `3800002` | Nemotron-3.5-Lightning-30B-A3B NVFP4 shipped: house 37/37, C1 63.27 ± 0.65 t/s, ladder 63.27 / 90.81 / 122.27 / 144.15, prefill flat at ~6.2k, 20.10 GiB, tool calls passing — the lane's fastest single-node chat arm; thinking-off is decode-identical (62.73 vs 62.74 t/s, recipe serve 63.85 vs 63.49, inside each other's spread) but costs five house items (32/37: `wp-3`, the three `hard-arith` items, `trick-3`), so both shipped numbers are thinking-on and the reasoning channel is load-bearing; its first `sparkrun` boot died once inside PIECEWISE CUDA-graph capture (`CUDA error: an illegal instruction`) and did not reproduce across five further boots/variants, so retry once and do not set the deprecated mamba flag; that emptied the ranked 1-node table (ranks 1–5 closed, 6–10 are 2+ nodes: MiniMax-M3 is 795.5 GiB on the Hub against the ~220 GB the dossier carried, Inkling-Small 495.4 GiB); node-free work closed the same night: house-budget audit (42 of 43 receipts at 4096, `hard-rev` the near-universal discriminator, convention into `tools/README.md`), render sweep (53 files, 46 clean, 7 flagged — four host-count refusals and three checker artifacts, no real defect), the Qwen-Image sigmas guard with three negative controls, and the AGENTS count refresh | — |
| 2026-10-21 21:42–23:59 ET (recorded under the 20:00 entry) | `3800002` | vLLM-OMNI serves the Qwen-Image checkpoint natively on one GB10 at 8.66–8.75 s warm / 11.19 s cold per 1024² 8-step image against the shipped Diffusers arm's 11.49 / 12.64 s — ~24 % faster at identical peak (36.84 vs 36.82 GiB), TTR ≈ 4 min, `CUDNN_ATTN` auto-selected for sm_121; recorded as a measured alternative, not an arm: no recipe, the step knob is inert and mis-reported (4/8/12 → one byte-identical PNG at ~8.7 s while `denoise_step_latency_ms` read 2164/1086/721), same seed gives a different picture (`38ce554a…` vs `e24f6e3a…`); both 8-step images opened at full resolution against the prompt's `two-color screenprint` requirement: Diffusers honors it (two-line `SPARK` / `RUN`, exactly two inks, blue over orange on cream, correctly spelled, crisp edges), OMNI violates it (single-line `SPARKRUN`, rainbow of many hues on white) — a prompt-adherence defect, not a style difference; what stands: no smearing, no blended or doubled glyphs, no gibberish letterforms, no step-count starvation, so the ~24 % win is real but spent on the wrong instruction; scope is one prompt, one seed, one image per route, so it is not a measured general quality gap; the shipped Diffusers arm stays the default and the OMNI variant was offered and declined (2026-10-21) | — |
| 2026-10-21 17:50–18:45 ET | `b85f611`, `510215b` | the pair block emptied with no finding: **flash-next refuted on both engines** — the b12x build cannot construct the model config (`qwen_sparse_attention` is not a layer type it knows, so no weight is read) and the documented `vllm/vllm-openai:v0.31.0` fallback clears that gate and dies at worker init (`Qwen4Exp PLE embedding does not support CompressedTensorsConfig`), two gates, so the answer is an image that has both; **qwen4 labquant-highcon passed its control** (TTR 9.6 min, `max_model_len 262144`, admission unclamped, 41/41 shards, diagnostic payload fired 0 times, sweep 86.8 / 87.5 / 89.5 / 75.4 t/s against 84.9 / 89.1 / 89.1 / 72.9, every cell inside 3.4 %, no 10 % finding); nothing pair-bound runnable | — |
| 2026-10-21 17:21–17:32 ET | `39a4f00`, `3c3c134`, `955c96a`, `e85c786`, `745ebd3` | **Nox-4B shipped** at 67.8 % (1356/2000), the best CPU route in the decision lane, 12.8 points over Sol-2B; **JEV-27B does not ship**: 66.8 % (1337/2000) against its 9B sibling's 67.0 % (1340/2000) is three decisions, 0.15 pp, a tie below the lane's strictly-beat rule; **Muse Glimmer 30B closed as a checkpoint defect**, not a pack defect (the bf16 control misses `nurkrpas` identically); flash-next staging record corrected (both nodes have held the 183.48 GB export complete since 2026-10-15, so only a boot receipt is outstanding); docs moved to the sparkrun 0.4.2 build with schema cites re-derived and three claims the code had outgrown rewritten | — |
| 2026-10-21 03:00–07:29 ET | `3fbb5e0`, `9d67131`, `d61cb30` | cybersec arm 5's tools leg closed at 1037/1240 = 83.6 %; the ornith SGLang 0.5.21 bump validated on all three arms and shipped; the LTX-2.5 T2V arm first-booted at 100.13 s cold / 78.1 s warm | `~/benchmarks/cybersec-arm5-tools-20261021/`, `~/benchmarks/ornith-0.5.21-bump-20261021/`, `~/benchmarks/ltx25-recipe-20261021/` |
| 2026-10-21 02:48 ET (commit `3fbb5e0` 03:00 ET) | `2f9a8f3e60a51ee4_3510a5e0d37d` (boot id) | cybersec arm 5 finished 5/5: fresh TP=2 boot (TTR HTTP-ready 59.407 s), cap-free tools-only run 1037/1240 = 83.6 % in 3,887 s with 0 transport errors (simple 376/400 · multiple 188/200 · parallel 181/200 · parallel_multiple 177/200 · irrelevance 115/240) at 3.133 s/question; the pair was drained afterwards | `~/benchmarks/cybersec-arm5-tools-20261021/` (`REPORT.md` merges the four 2026-10-20 legs) |
| 2026-10-21, time not recorded (pair block, undated in the old table) | — | ds4 pair work closed: **v0.6 adopted** (c8 +26.5 %, c16 +25.7 %, prefill +24.6 % / +39.5 %, pin `d6e4c10d…`), and ds4 `reasoning_effort` measured (10.6 % paired saving, one task) | — |
| 2026-10-20–21, times not recorded (undated bullets from the old §Closed this session) | — | 27B-NEXTN suite + ladder (`bench_e66cbef09760`: 15.39 / 28.81 / 60.35 / 102.82 t/s); 27B-uncensored tools 1072/1240 (86.5 %); kolibri APEX five legs `ok` with a real 262k needle pass; laguna-XS 59.8 % tools, triaged as capability not parser; qwen3 MLX needle TRUNCATED at ~222.5k; ornith YaRN d90 PASS with a null die-capture; Sol-2B built, published and scored 55.0 % (1101/2000) at p50 195 ms; qwen4 `zz-labq-no-diag` passed, retiring the diagnostic on the balanced arm (restored in highcon only); 27B-NEXTN and arm-1 lane-doc blocks; Laguna-M.1 TP=2 booted, suite + ladder landed (C1 12.85 / C2 21.85 / C5 34.15 / C10 34.64 t/s), tools 750/1240 triaged as capability; Sol-2B recipe boot-verified through `sparkrun run` (1101/2000, 80.5 s); tracked-file addresses masked (71 lines, 22 files → 0); cybersec arm 5 — house 37/37, needle 3/3 at every rung, ARC 188/200 (94.0 %), GSM8K 197/200 (98.5 %), tools 1037/1240 = 83.6 % in 3,887 s with 0 transport errors, superseding the 2026-10-20 interruption; ornith SGLang 0.5.21 bump — 35B ladder inside every band, 9B C2 settled at −3.2 % on `.34`, YaRN 6/6 with a first-attempt d90 pass at 97.80 % fill; LTX-2.5 T2V — 100.13 s cold / 78.1 s warm on `.35` at 83.45–84.00 GiB peak | `~/benchmarks/cybersec-arm5-tools-20261021/REPORT.md`, `~/benchmarks/ornith-0.5.21-bump-20261021/`, `~/benchmarks/ltx25-recipe-20261021/` |
| 2026-10-21 14:26–18:45 ET (per the cited commits; undated paragraphs from the old §Closed this session) | `b85f611`, `510215b`, `3c3c134`, `39a4f00`, `955c96a`, `e85c786`, `745ebd3` | flash-next: weights already complete on both nodes (18/18 shards each), so the pair boot cost 10.6 s of distribution and the staging fear was a measurement error; the sparkrun-built b12x image (`cf5a2a53…`, vLLM `0.1.dev21830+g8244d1c44.d20261015`) reads no weight, and `vllm/vllm-openai:v0.31.0` (`sha256:c1c9f6fd…`, local ID `bbe704505570` on both nodes) warms multimodal in 11.9 s, starts TP=2 and dies in the worker; `vllm/vllm-openai` declares `ENTRYPOINT ["vllm","serve"]`, which eats sparkrun's launcher, so an `executor_config` `entrypoint: ""` is required to adopt it (recorded in `recipes/cybersec/README.md`). qwen4 highcon (task `1895030211ea0500_3510a5e0d37d`): `load_weight` 508.93 s, `max_total_num_tokens=1587072`, `max_running_requests=32`, mamba 128, 41/41 shards on both classes, no `_scale` assertion; sweep at d8192/pp2048/tg128, k=8/12/16/24 against the controls 84.9 / 89.1 / 89.1 / 72.9 — the restored diagnostic mod did not move the serve. Nox-4B on `.34`: KL 0.219, Brier 0.114, ECE 0.063, 0 completion errors, 14,066 s at 35.2 s/case, second in the lane behind clef-flash's 70.3 %; vendor golden gate passed on aarch64 (`/health` 200 ready, no `GoldenResult` failure); as sparkrun stages it (`HF_HUB_OFFLINE=1`) the loader still calls the Hub tree API and `/health` stalled at 503 `loading`, so the recipe carries `HF_HUB_OFFLINE=0` and boots clean in ~30 s; ladder c1/c2/c5 all 0.044 req/s at p50 22,763 / 45,480 / 113,797 ms, a pure queue with no batching, c10 not run. JEV-27B on `.35`: boot wall 1244 s, most of it CUDA-graph capture (102 graphs, ~660 s); ladder c1 2.912 / c2 2.974 / c5 4.351 / c10 4.488 req/s, no useful scaling past c2 because the align path serializes decision prefill. Muse Glimmer 30B: bf16 control `meta-models/Muse-Glimmer-30B @7af58019`, same drafter, same image digest, same `mem_fraction_static 0.80`; house 36/37, same item, same string `nurkrpas`; C1 12.1 t/s on bf16 against the pack's 20.2; arm out of both trees, route and numbers in `attic/explore/AGENTS.md`. flash-next staging: the lane README's claim that the 183.5 GB export was reclaimed from every node on 2026-10-14 was wrong — 18/18 shards, 183.48 GB, zero bytes fetched, and `.35` carries 78.06 GB of orphan `.incomplete` blobs. sparkrun 0.4.2 docs pass: both files claimed `0.4.0-alpha+g29f53fb` while this workstation and the head report `0.4.2-alpha+g36d8a44`; module paths survived (`core/launcher.py`, `core/recipe.py`, `core/validation.py`, `models/runtime.py`), 27 line cites re-derived, three sentences rewritten (`recipe list`/`recipe search` fall back to `metadata.description`, the unmapped-key drop raises `unmapped-config-key`, `_KNOWN_KEYS` still 41 keys and moved two lines); the eleven arms carrying `unpinned-model-revision` re-counted file by file: still eleven | `~/benchmarks/nox4b-20261021/REPORT.md`, `~/benchmarks/jev27-20261021/REPORT.md`, `attic/explore/AGENTS.md` |

### Workstation tooling (measured 2026-10-21, time not recorded, after `sparkrun` landed there and reported `0.4.2-alpha+g36d8a44`)

## Workstation tooling (measured 2026-10-21, time not recorded, after `sparkrun` landed there and reported `0.4.2-alpha+g36d8a44`)

| tool | what the repo needs it for (one caller) | on the workstation | where it works today | ask |
|---|---|---|---|---|
| `sparkrun` | validate, render with `-n`, registry lookup, launch — the whole recipe surface | **yes.** `sparkrun recipe validate <path>` returns the head's answer verbatim, with and without an override; anything registry-qualified (`@littlecedar/…`) or cluster-profile-driven needs `HOME=$PWD/.local/sparkrun-home`, because the real `~/.config/sparkrun/registries.yaml` carries no `littlecedar` entry and `~/.config/sparkrun/clusters/` is empty while the repo-local home has both | head, and the nodes for launches | none |
| `uv`, `uvx` | the guard suite (`uv run python -B -m unittest discover -s tests`, **782 tests**, 2 skipped, measured 2026-10-22 at `df2c259`) and the docs' own instruments (`uvx tool-eval-bench@2.8.0` at `recipes/decision/README.md:332`, `uvx llama-benchy@0.4.0` via sparkrun) | **yes** (uv 0.13.4); `uvx tool-eval-bench@2.8.0 --version` answers 2.8.0 here | head | none |
| `hf` | model sizing and revision probes (`tools/build-dsv41-combined.py`, the per-arm revision checks) | **yes** (1.29.0) | head | none |
| `docker` | resolving an image ref to its digest (`docker buildx imagetools inspect`, the pin method in `mad-science/SESSION-RECORD.md:354`), plus the node-side log and liveness ops every runbook depends on (`docker cp /tmp/sparkrun_serve.log`, `docker exec … kill -0`, `docker events --filter event=die`) | **partly**: the daemon runs (29.9.1) and `imagetools inspect` resolves the sglang v0.5.21 index and its amd64 manifest from here; there is no GPU, so any command that runs a container stays meaningless | head, and the nodes for container work | none — container work belongs where the hardware is |
| `python3` | the stdlib instruments (`python3 tools/decision-ladder.py`, `tools/quality-battery.py`, `tools/jev-decision-bench.py`) | **yes** (3.14.8; all three print usage) | head | none |
| `ffmpeg`, `ffprobe` | checking a media arm's output — the LTX-2.5 receipt claims h264 1344×768, 121 frames, 24 fps plus AAC (`README.md:237`, `attic/explore/AGENTS.md:501`); no `tools/` or `mods/` script shells out to it, so this is the operator's own verification | **no** — neither is installed | head | install `ffmpeg` here, or accept that video-receipt verification stays head-side |

| gate step | runs on the workstation | stays head-side |
|---|---|---|
| recipe validation, `-n` rendering, the 782-test guard suite, `@littlecedar/…` resolution, `hf` sizing probes, container-digest resolution | **yes** | — |
| boots, serves, `docker cp`, benchmarks, the ladder instruments that measure a live endpoint, video-receipt verification until `ffprobe` exists here | — | **yes** |

Checked and present, no row needed because none is a local gate step: `git`, `ssh`, `scp`, `rsync`, `curl`, `jq`, `setsid`, `stdbuf`, `taskset`, `nproc`, `timeout`, `sha256sum`.

### 01:55 ET — `e8d34fc`: the W6 TP=4 failure, the knapcio accuracy legs, the W12 image pin

**W6 booted, loaded 41/41 shards on four ranks and died in `modelopt_quant.py:2624` (gated-activation MoE
padding) on every rank**, so TP=4 is an engine limit on this build, not a memory or arm defect. The knapcio
four-node arm closed the two accuracy cells the 2026-10-18 suite left open: **ARC 93.5 % / GSM8K 97.5 %**
(n=200 each, seed 1234). W12's arm now pins the b12x build by digest — latest resolved to `cf5a2a53`, the
build the shipped TP=1 solo arm already pins, so both vLLM receipts describe one engine. Files:
`attic/qwen4/AGENTS.md`, `attic/qwen4/arms/qwen3.8-flash-next-nvfp4-vllm.yaml`, `recipes/ds4/README.md`.
