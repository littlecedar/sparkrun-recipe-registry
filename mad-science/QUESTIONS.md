# QUESTIONS — the index of the owner-question record (2026-10-22; migrated 2026-11-22)

**Open owner questions are `ask` rows in `mad-science/queue.json`.** Owner directive 2026-11-22: an
owner input is a row — the question in `title`, the options and the answer procedure in `notes`, and
every row that needs the answer `blocked` on it. This file is an **index**, not a register: it holds
no open rows.

- create one: `uv run python -B tools/task-queue.py add --state ask --id ask-… --title "Ask: …"`
- read the open set: `uv run python -B tools/task-queue.py questions`
- answer one: `done --id <ask>` (the answer goes in `notes`/`evidence`), then return each dependent
  to `queued` — `lint` names the ones left `blocked`, because a hold whose blockers are all `done`
  cannot clear itself.

**Settled questions live in `TODO.md` §"Settled questions"** with the answer and rationale verbatim,
and `# DECISIONS` holds the decisions taken. Numbering is stable across all three, so a citation such
as `QUESTIONS.md #9` still resolves for a question that has since settled.

The `questions` array the tool used to read is retired with this migration: `validate` refuses the
key, because two homes for the open set is the restatement drift `QUEUE.md` §"Relationship to
TODO.md" exists to prevent.

## Where the rows went

| # | question | now |
|---|---|---|
| #85 | Who deleted the production fence over `.31`–`.34` at `2026-11-17T08:06:52Z`, and was it owner-authorized? | `ask-fence-deletion-authorization` in `queue.json`, migrated 2026-11-22 |
| #88 | Which license class does `meta-models/Muse-Glimmer-30B` get — an Apache-2.0 grant with a separate acceptable-use policy? | `ask-muse-glimmer-license-class` in `queue.json`, migrated 2026-11-22 |
| #89 | MiniMax-H3's territorial license and recipe authoring / R&D | settled — `TODO.md` §"Settled questions", `## Owner ruling 2026-11-22 — MiniMax-H3's territorial license does not reach recipe authoring or R&D` |
| #86, #87 | the two licence classes raised 2026-11-20 | settled — `TODO.md` §"Settled questions", `## Owner ruling 2026-11-20 — both licence classes ruled not applicable` |
| #84 | the ERNIE-5.5-Flash-Base licence class (2026-11-11 survey round) | settled — `TODO.md` §"Settled questions", `## Owner answer 2026-11-11 — ERNIE licence class` |
| #69–#83 | the 2026-11-09 batch | settled — `TODO.md` §"Settled questions" |
| #1–#68 | the 2026-10-21/22 rounds | settled — `TODO.md` §"Settled questions" |

The two dated corrections the old status table carried are settled facts now recorded in the rulings
they cite: the 2026-11-09 freeze lift (`## Owner directive 2026-11-09 — TP4 unfrozen, TP1/TP2 only
via TP4`) and the 2026-11-12 DINOv3 acceptance (`## Owner ruling 2026-11-12 — DINOv3 accepted, two
eval-only arms authorized`). Nothing here is read by a tick, a guard or CI; it exists so the numbers
resolve.
