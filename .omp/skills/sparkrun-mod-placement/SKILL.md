---
name: sparkrun-mod-placement
description: "Use when adding, moving or referencing a sparkrun mod in the sparkrun-recipe-registry repo: whether it belongs in the shared mods/ root or in recipes/<lane>/mods/, and which ref form each recipe must use."
---

# Placing a sparkrun mod

Applies to the `sparkrun-recipe-registry` tree (registry `littlecedar`).

## Rule

- `mods/` = **shared mods only**: a mod referenced by recipes in **two or more lanes**.
- A mod relevant to **one lane** lives at `recipes/<lane>/mods/<mod>/`.
- `mod-template/` stays in `mods/` (a scaffold no recipe references).
- `drop-caches` is the one documented exception: four lanes list `@eugr/mods/drop-caches`
  (eugr's copy, which is inert) and this repo's copy is its fixed fail-closed counterpart,
  so it is shared by design, not by in-tree usage. See `tests/test_mods_lane_locality.py`
  (`SHARED_BY_DESIGN`).

## Why it is not cosmetic — the resolution order

`sparkrun/core/mods.py` resolves each `mods:` entry first-hit-wins:

1. `@registry/...` → that registry's **cloned** `mods/` dir, and nothing else.
2. **Adjacent** to the recipe: `<recipe_dir>/mods/<name>`, then `<recipe_dir>/<name>`.
3. the recipe's own registry's `mods/`.
4. the `eugr` fallback.

Rungs 2-4 are **skipped for scoped (`@…`) refs**. Therefore:

- a **lane-local** mod MUST be referenced **unscoped** as `mods/<name>`;
- `@littlecedar/mods/<name>` for a lane-local mod **breaks the launch** (loud `ModNotFoundError`,
  with no eugr fallback to hide it);
- a **shared** mod keeps `@littlecedar/mods/<name>`, which works from any cwd.

The registry clone is a cone-mode sparse checkout of the `recipes` subpath, so
`recipes/<lane>/mods/**` travels with it; `--transfer-mode delegated` rsyncs the adjacent hit.

## Procedure

1. Count **lanes**, not references: a mod referenced by recipes in ≥2 lanes is shared. An
   `@eugr/mods/<name>` ref counts as a lane's use of a *different registry's* copy, so it is not
   evidence that ours is shared — classify by what the ref binds to, not by basename.
2. One lane → `git mv mods/<mod> recipes/<lane>/mods/<mod>`; ≥2 → leave it in `mods/`.
3. Rewrite refs: lane-local `@littlecedar/mods/<name>` → `mods/<name>`. Leave shared refs alone.
4. Never touch `/workspace/mods/<name>/…` strings — that is the in-container copy path, keyed on
   the basename, independent of where the mod lives.
5. Update paths in live docs (`recipes/<lane>/README.md`, `tests/`, `tools/`, `mad-science/**`,
   `attic/**/*.md`, `.omp/skills/`). Sweep with `(^|[^/])mods/<name>` — a backtick-quoted citation
   in prose is the easy miss. Leave `attic/**/*.yaml` (frozen recipes) alone.
6. Verify, in order of strength:
   - `uv run python -B -m unittest discover -s tests` (the locality guard is `tests/test_mods_lane_locality.py`);
   - the gate: `sparkrun recipe validate` on `recipes/*/*.yaml`, `bash -n` on `mods/*/*.sh` **and**
     `recipes/*/mods/*/*.sh`, `py_compile` on those plus `tools/*.py`;
   - clone-side: register a throwaway HOME whose `littlecedar` entry is `file://` this worktree,
     `sparkrun registry update littlecedar`, then load each recipe as `@littlecedar/<name>` and
     resolve its mods. That exercises the **served** path (source_path = the clone) without pushing.

## Pitfalls

- `sparkrun recipe validate` does **not** resolve `mods:`; a bad ref surfaces only at launch. The
  locality guard is the only offline check the standard gate performs.
- A doc's filesystem path (`recipes/<lane>/mods/<name>`) and a recipe's quoted `mods:` entry
  (`mods/<name>`) are different spellings — a mechanical sweep must not convert one into the other,
  and in-container `/workspace/mods/<name>` is a third.
- A `mods:` list is an ordered dependency chain, not a set: moving a mod never licenses reordering it.
