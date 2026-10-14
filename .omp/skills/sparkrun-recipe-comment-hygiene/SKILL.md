---
name: sparkrun-recipe-comment-hygiene
description: "Use when trimming, moving, or auditing comments in sparkrun-recipe-registry shipped recipes (recipes/lane/*.yaml) — the crucial-only rule, the README/attic destinations, and the parsed-YAML verification that catches corrupted keys."
---

# Recipe comment hygiene (sparkrun-recipe-registry)

## Rule

A shipped recipe's `#` comments must be moved out of the YAML into the lane's `README.md` (or its
attic) **unless the comment is crucial to a surprising, novel, or confusing property of that
recipe**. Keep one only when an operator who knows sparkrun but not this model would get it wrong —
silent-failure footguns, surprising knob interactions, required orderings/pairings, client contracts —
and keep it to ≤2 lines beside the value it governs.

## Destination (nothing may be lost)

| material | home |
|---|---|
| how to run/configure it (a knob's effect, a required mod pairing, a client contract) | `recipes/<lane>/README.md`, under that recipe's section |
| history/evidence (dates, boot IDs, measured numbers, A/B narratives, provenance) | `attic/<lane>/AGENTS.md`, under `## Recipe comment archive (YYYY-MM-DD)`, keyed by recipe filename |

## Procedure

1. **Census.** `python3 -c` over `recipes/*/*.yaml`, counting lines whose strip starts with `#`, per lane.
2. **Per lane (one agent per lane; disjoint scopes).** Classify every comment KEEP/MOVE; write the
   movers to the two destinations; delete them from the YAML. Preserve indentation and blank-line
   structure; a trailing `key: value  # note` that is not crucial loses only its `# …` tail.
3. **Never touch** `metadata.description` (guards assert its prose). Keep comments out of a folded
   `command:` block — a `#` **mid-command** truncates the launch line at the shell. **One tracked
   exception, do not "fix" it:** `recipes/qwen3/qwen3.8-27b-mlx4bit-tensorfold-sglang.yaml` ships a
   terminal in-fold comment that is load-bearing — sparkrun's `_augment_served_model_name` skips its own
   append only when `--served-model-name` already appears in the rendered command, and that engine
   parses no such flag (the first boot died on `unrecognized arguments: --served-model-name`). It is
   line-terminal, so the shell swallows it. The `test_no_hash_inside_command_block` guards are
   **ds4/ifm lane-scoped**, not repo-wide.
4. **Verify — the decisive check.** Parsed-YAML equality against the pre-edit blob:
   `uv run --with pyyaml python -c "import subprocess,yaml; yaml.safe_load(open(f))==yaml.safe_load(subprocess.run(['git','show',f'HEAD:{f}'],capture_output=True,text=True).stdout)"`
   over every recipe. Any recipe that differs outside comments is corrupt — including a comment removed
   *inside* a folded scalar, which changes that scalar's value. Run the real gate too — and never pipe
   the test command (a pipeline hides its exit status; `… | tail` printed "GREEN" over four failures once).
5. **Guards.** Text guards mostly strip whole-line comments ("F20") and are safe, but a few assert
   comment prose deliberately (e.g. `tests/test_k2_7b_recipes.py` requires the literal `tree_mode`
   correction note in the UNO arm). Restore the cited note; do not weaken the guard.

## Known traps

- Agents self-report success while having deleted a *key* instead of a comment — the pyyaml check is
  not optional. Measured failures: a lost `attention_backend: fa4` (three guards), lost `metadata.tags`
  (feeds the index flag column), a paraphrased in-`command` comment, a stray trailing newline.
- `strip_comments` helpers usually drop whole-line comments only — keep surviving comments on their
  own lines, or an equality guard on a scalar absorbs the `# tail`.
- Line-number citations into a recipe (`file.yaml:NN`) go stale the moment comments above them move;
  prefer section/file references, and sweep the docs that cite them — including prose that names where a
  fact is "documented in the recipe", which can dangle once the comment moves out.
- Archived `attic/` recipes are frozen provenance — leave their comments verbatim.
