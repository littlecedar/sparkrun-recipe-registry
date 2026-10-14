---
name: disposition-registry-support-files
description: "Auditing mods/ or tools/ in sparkrun-recipe-registry for lane service; moving retired-lane artifacts to attic/lane/, deleting unreferenced ones; census method, attic conventions, and repoint checklists."
---

# Disposition of registry support files (mods/, tools/) in sparkrun-recipe-registry

Proven 2026-10-11 across four audits (tools → attic/delete, tools/README refresh, two untracked-mod
dispositions, full 25-mod audit). Use when asked whether every file under `mods/` or `tools/` serves
an active recipe lane.

## Decision rule

- Serves ≥1 **active** lane (a recipe in `recipes/<lane>/`, its tracked lane docs, its guards) → keep.
- Serves only a **retired** lane/arm (consumers live in `attic/<lane>/`) → `git mv` to
  `attic/<lane>/mods/` (or `attic/<lane>/` for tools), tracked — attic is the tracked archive.
- Serves **nothing** (zero mounts AND zero doc/test/tool references) → `git rm` (recoverable).
- Unmounted-but-documented lane infrastructure (a fail-closed replacement, a re-verified mitigation,
  a documented ship path, a guarded fallback) → **keep**; do not relitigate a recorded deliberate
  decision. Read the artifact's own README/header for its self-declared scope ("trial-only",
  "NOT mounted in the shipping recipe", "mount it on a control recipe") before judging.

## Census procedure (the part that keeps being needed)

1. Extract every `mods:` block: for each recipe,
   `grep -A12 '^mods:' "$f" | grep -oE '(@littlecedar/)?mods/[a-z0-9.+-]+'`.
   Run it over `recipes/*/*.yaml` AND every attic arm tree (`attic/*/arms/*.yaml`, `attic/*/*.yaml`).
2. Union-name grep across `AGENTS.md;recipes;attic;tests;tools;mad-science;benchmarking` with
   `gitignore: false` — lane docs that reference mods are often git-ignored (`*-WORK.md`).
3. Gotchas that produced wrong answers before:
   - **Registry prefixes**: arms mount `@eugr/mods/<name>` (external registry) vs bare `mods/<name>`
     or `@littlecedar/mods/<name>` (ours). A grep on the bare name matches all three; a
     `mods/<name>` extraction regex that strips prefixes will misreport an `@eugr` mount as ours.
     Check the raw YAML line before classifying.
   - **Name collisions**: a mod name can be a substring of a recipe name
     (`fix-qwen3.8-flash-next-vllm` ⊂ `qwen3.8-flash-next-nvfp4-vllm.yaml`) — census hits conflate
     them; rely on the mods:-block extraction, not the doc grep, for mount facts.
   - Short/generic patterns ("honed", "ninja", "needle") hit dataset corpora and prose; verify
     candidate "zero references" with a case-insensitive sweep before deleting.

## Moving into attic (the ifm precedent — follow it exactly)

- `git mv mods/<name> attic/<lane>/mods/<name>` (mkdir the target); keep tracked.
- Add a manifest row (attic/<lane>/ARMS-MANIFEST.md or a tracking note in attic/<lane>/AGENTS.md):
  what it does, why archived ("serves no live recipe now, not because it was wrong"), move date.
- Add/extend the **recovery footer**: resurrecting requires moving the mod back to `mods/` (and
  pushing — `@littlecedar/mods/…` references in recipes resolve only against the registry, and they
  die once the mod leaves it; bare `mods/<name>` refs resolve only with the mod restored).
- **Frozen verbatim**: archived recipes'/mods' own comments referencing pre-move paths stay as-is —
  they are only runnable again after being moved back. Repoint only *live* citations: root
  `AGENTS.md`, active lane docs, `tests/` path constants (`MOD_DIR`, `MOD_PATCH_DIR`,
  `SIBLING_ENGRAM`, …), and cross-archive doc citations.
- Deleting: no manifest row needed, but record the deletion + recovery pointer (git history) in the
  manifest row of the consumer arm if one exists.

## Verification ritual

`bash -n` + `py_compile` on moved files; full suite `uv run python -B -m unittest discover -s tests`;
`HOME=$PWD/.local/sparkrun-home sparkrun recipe validate` over `recipes/*/*.yaml`; pycache cleanup;
final gitignore-blind sweep confirming every remaining reference to moved/deleted names is
attic-internal or an attic path. Commit with explicit pathspecs only (live second writer).
