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
