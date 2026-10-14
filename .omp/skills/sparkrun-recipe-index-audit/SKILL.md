---
name: sparkrun-recipe-index-audit
description: "Audit or refresh recipes/README.md in the sparkrun recipe registry against the recipe tree: row/name/mem/flag drift, link hygiene, and which measured numbers not to 'fix'"
---

# sparkrun-recipe-index audit (`recipes/README.md`)

Use when asked whether the shipped recipe index is up to date, or after adding/renaming/retiring a recipe.

## Facts to establish first

```bash
git ls-files 'recipes/*/*.yaml' | sort      # the shipped set — the only set the index lists
ls recipes/*/*.yaml                        # SUPERSET on a syncthing-shared tree: a live second writer leaves untracked WIP recipes
```
Root `AGENTS.md` counts the **working tree** (`ls`), the index lists the **tracked** set; at 2026-10-09 that was 18 vs 16. Never reconcile them by assuming either is wrong.

## Checks

1. **Row census.** Recipe-name cells in the per-family tables must be exactly the tracked basenames minus `.yaml` — same count, same set. A row whose name is not a filename is stale (seen: a 397B row missing its `-vllm` suffix).
2. **Name grammar.** No `.yaml` inside the name cell. `zz-`/probe arms and attic arms are never listed.
3. **Cells from the recipe, not from prose.**
   - `Mem` = the recipe's `gpu_memory_utilization`; `TP` = `tensor_parallel` (grep the recipe's `defaults:`).
   - `Flags` = `metadata.tags` mapped through the Model Flags table. **A lane README may disagree with its own recipe metadata** (the 8B VL reranker is not tagged `fast` on purpose). The index's stated rule is that flags come from metadata — follow the metadata.
   - Unmeasured `C1 t/s` / unpublished `Size` → `—` (em dash). Never invent or estimate one; never carry a lane summary's rounded number into a cell the recipe does not support.
4. **Link hygiene** (catches both broken references and dead weight):
   ```python
   defs=set(re.findall(r"(?m)^\[([^\]]+)\]:", t))
   used=set(re.findall(r"\]\[([^\]]+)\]", t))
   print(sorted(used-defs), sorted(defs-used))
   ```
   `used-defs` renders literally in the shipped doc; `defs-used` is dead unless another file's table needs it (check before deleting — a retired lane's README carries its own links).
5. **Guide pointers.** `# Notes` should point at each lane's entry doc — but only at **tracked** files (an untracked lane README is not shippable yet).

## Judgment rule: do not "fix" a measured cell

If a `C1 t/s` cell disagrees with a lane document, read the lane's work record before touching it. When the lane reconciles both values as real measurements of different profiles/windows and warns they are not interchangeable (e.g. qwen3 27B: index 50 vs `WORK §10`'s §2 33.76 — *"Do not read this as 'the recipe got faster'"*), the right output is the conflict **with citations**, not a silent swap. Renumbering such a column is usually an open lane work item.

## Editing gotcha

`edit` op `PUT n.=n:` **replaces** line `n`; to insert after it use `PUT >n:`. Miswriting this silently deletes the anchor line (it cost a link definition once). Follow any index edit with the link-hygiene script.

## Gate

```bash
uv run --offline python -B -m unittest discover -s tests   # 372 at 2026-10-09
find mods tests tools -name __pycache__ -type d -exec rm -rf {} +
```

The suite does scan `recipes/` (`test_safe_text.py`, `SHIPPED_DIRS`), so index prose must stay free of internal IPs/hostnames and image special-token spellings. Commit with explicit pathspecs (`git add recipes/README.md`), never `git add -A` — the tree is shared with a second writer.
