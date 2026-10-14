---
name: audit-orphan-artifacts-sparkrun
description: "Use when asked whether tools/, mods/, benchmarking profiles, or other shared sparkrun-recipe-registry artifacts serve active lanes; census, classify, and disposition them (commit / move to attic / delete)."
---

# Disposition audit for shared registry artifacts (tools/, mods/, profiles)

The user's decision rule (2026-10-11, applied to tools/ then mods/): serves an active recipe lane → keep (and commit if untracked); serves only a retired lane/arm → move to `attic/<lane>/`; serves nothing → delete.

## Census (do this first, never from memory)

- Grep each artifact's name across `AGENTS.md;recipes;attic;tests;tools;mods;mad-science;benchmarking` with **gitignore:false** — the repo-wide ignore rules (`**/*-WORK.md`, `**/*JOURNAL.md`, `**/COOP.md`) hide lane working docs that cite artifacts; a gitignore-respecting census silently misses them.
- Also grep mechanism keywords (e.g. a crash symbol or tensor name), not just filenames — lane docs may cite the artifact indirectly.
- "Serves a lane" = consumed by the lane's work: recipe `mods:` lists, mods bundling the artifact, tracked lane AGENTS/README workstream rows, tests/ guards, tools/README sections — not only YAML references.

## Acting

- **Active + untracked → commit.** Screen first for internal addresses (`<node-ip>`, hostnames, `/home/…`); masked forms `<head>` / `[.NN]` are the convention. Use explicit `git add -- <path>` pathspecs (live second writer; never `-A`).
- **Retired → `mv` into `attic/<lane>/`** (mods use an `attic/<lane>/mods/` subdir; precedent `attic/ifm/mods/patch-sglang-k2-horizon-fp8`). Untracked sources move with plain `mv`, then get `git add`ed at the new path — attic keeps the artifact tracked. Add a manifest row (file | what | why archived | provenance) plus a recovery footer ("move back to `mods/` and remove the row"). Leave frozen arm/recipe YAML comments verbatim; DO repoint doc citations that name the old path (root AGENTS.md exemplars, cross-archive references). Update attic-contents row in root AGENTS.md.
- **Orphan → delete** and update every referencing doc/test.

## Verify

`bash -n` moved `run.sh`, `py_compile` moved `.py`, full gate (`uv run python -B -m unittest discover -s tests` + `HOME=$PWD/.local/sparkrun-home sparkrun recipe validate recipes/*/*.yaml`), then a final reference sweep expecting only attic-internal or repointed hits.

## Recurrent trap

Sessions commit the docs that cite a new deliverable but never stage the deliverable itself (happened to tools/gate-37111.py, qwen4-quality-eval.py, and two mods). When tracked docs/tests reference an untracked file, that is the finding — screen and commit it.
