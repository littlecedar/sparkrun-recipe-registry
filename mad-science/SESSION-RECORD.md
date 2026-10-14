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
headline is now measured). New `recipes/ornith/AGENTS.md`; root cross-reference updated.

**decision.** CPU+GPU tandem probe: clef-flash (GPU) + Kai-0.6B (CPU) equal-weight linear-mean ensemble
**71.6% vs clef's 70.3% alone** (+1.3, McNemar p=0.012) — pairing-specific (clef+Sol 69.9%, 3-way 69.6%);
co-residency slows the CPU model ~45%. New stdlib tool `tools/decision-tandem.py`.

**kolibri mod defect.** `mods/install-kolibri-plugin` keyed idempotence on a persistent marker while pip installs
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
