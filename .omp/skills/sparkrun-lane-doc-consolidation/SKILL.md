---
name: sparkrun-lane-doc-consolidation
description: "Use when consolidating or maintaining lane documentation in the sparkrun-recipe-registry (recipes/lane/README.md, AGENTS.md, NOTES.md, attic/lane/) — applies the shipped-recipes-only README rule, the attic index, and the citation-repair sweep."
---

# Lane-doc consolidation (sparkrun-recipe-registry)

## The rule

A lane's `recipes/<lane>/README.md` speaks to **shipped recipes only**. It opens with a `## Contents`
table of contents and ends with a `## Attic index` naming **every** file under `attic/<lane>/` with a
one-line "what it holds / what question it answers". Everything else — lane state, constraints/traps,
guards, validation rituals, measurement histories, boot IDs, A/B receipts, negative results, candidate
lists, research docs, working notes — lives in `attic/<lane>/`, indexed from the README.

The PRIMARY root `README.md` is a pure index (per-family tables, `# Model Flags`, `# References`,
model-card link definitions). Command-template mechanics live in the tracked `recipes/MECHANICS.md`;
research prose removed from the index goes to `attic/PRIMARY-README-ARCHIVE.md`.

## Procedure

1. **Recon.** Inventory each lane's markdown (`wc -l recipes/*/*.md`), note which lanes have `AGENTS.md`
   /`NOTES.md`/research docs, and grep for cross-file citations (`recipes/[a-z0-9]+/(AGENTS|NOTES)\.md`)
   and test dependencies (`grep -rn 'AGENTS\.md' tests/`) — a guard may assert a lane doc's existence.
2. **Per lane (one agent per lane; disjoint scopes).**
   - Rewrite `recipes/<lane>/README.md`: `## Contents`, one section per shipped recipe (repo id,
     size/mem/TP/flags, the knobs a user cannot infer and what breaks if they move, license, launch
     caveats), then `## Attic index`.
   - Move to `attic/<lane>/` **verbatim**: `AGENTS.md` → `attic/<lane>/AGENTS.md`, `NOTES.md` →
     `attic/<lane>/NOTES.md`, and each standalone research doc. **If the destination exists, APPEND
     under a `## From recipes/<lane>/… (YYYY-MM-DD)` heading — never overwrite.** Preserve `§N`
     numbering; line numbers will shift, sections will not.
   - Append the material cut from the README to `attic/<lane>/AGENTS.md` under the dated heading.
   - Remove the lane files only after their attic copies are byte-verified (`cmp`/`md5sum`).
3. **Primary index.** Split the root `README.md`: mechanics → `recipes/MECHANICS.md` (verbatim), removed
   per-lane prose → `attic/PRIMARY-README-ARCHIVE.md`, index keeps tables + flags + links.
4. **Citation repair (repo-wide).** Path-swap every cite of a moved file (root `AGENTS.md`, `tools/README.md`,
   `mad-science/*`, `attic/*`, `mods/*` comments, `recipes/*/Dockerfile*`, tests). Drop raw line numbers
   into moved files; keep the `§N`. Inside `attic/<lane>/` a sibling is a bare filename; from elsewhere
   use the relative path. Historical/archival docs get link-only fixes, never prose rewrites.
5. **Guards.** Update any test that asserts a now-removed lane doc exists (e.g.
   `tests/test_cybersec_recipes.py::test_lane_docs_exist` — assert `README.md` plus the attic guide).
6. **Verify.** `uv run python -B -m unittest discover -s tests` (stdlib-only suite; the recipe guards
   read lane docs as text), the per-recipe `sparkrun recipe validate` loop with the
   `HOME=$PWD/.local/sparkrun-home` override, `bash -n` on `mods/*/*.sh`, `py_compile` on
   `mods/*/*.py tools/*.py`. Then check every rewritten README has `## Contents` + `## Attic index`.

## Pitfalls

- **Agents loop-degenerate.** One long lane task emitted 12 KB of "..." and stopped mid-task, leaving
  attic copies written but the README unrewritten and the lane files undeleted. Verify each lane's end
  state from the tree (`ls recipes/<lane>/`, line counts) rather than trusting the report.
- **Verbatim or nothing.** The attic copy is the only record once the lane file is deleted; verify with
  `cmp` before removing, and never "tidy" archived prose (its `§N` cites are load-bearing).
- **Relative links break silently.** A moved doc's internal links must be recomputed for its new depth.
- **Frozen archives** (`attic/DONE.md`) get path swaps only — the completed-item prose is history.
- Keep the primary README's **counts** consistent with `git ls-files 'recipes/*/*.yaml'`; stale counts are
  a recurring defect (see `mad-science/RESEARCH_LORE.md` §10).
