# The task queue protocol (`queue.json` + `tools/task-queue.py`)

Owner policy, 2026-10-26 (verbatim; answered in `GUIDANCE.md` §2/§4, file since trimmed — the
dated decisions live in `TODO.md` §"Retry queue — window 4"):

> The amount of time something takes should only determine its position in the queue — heavier
> tasks (more time) sink lower in the queue. Lighter tasks (less time) float to the top. A task's
> weight is reduced by a value equal to the weight of tasks it blocks. This means that if a queue
> is 48 hours deep, a task that takes 24 hours at the bottom of the queue would be pushed to the
> top of the queue if it is blocking 24 hours worth of other tasks. You could write a python
> script to weigh tasks, calculate what they're blocking, and update the queue accordingly. You
> would need to define a standard task schema and queue protocol.

> DeepSeek-V4.1-Flash-1017 is our primary model at this time, with GLM-5.3 and GLM-5.3-Flash as
> our secondary models of interest. Always prioritize unblocking and running items related to
> those models until told to do otherwise.

This document is that schema and protocol. The data is `mad-science/queue.json` (tracked, JSON,
human-diffable); the tool is `tools/task-queue.py` (stdlib-only; `tools/README.md` §task-queue.py
carries the command reference and exit codes). `TODO.md` remains the work record; the queue is the
scheduler's view of the same work (§Relationship to TODO.md).

## Contents

- [Task schema](#task-schema)
- [Weight](#weight)
- [Priority tiers (the owner's standing override)](#priority-tiers-the-owners-standing-override)
- [Session protocol](#session-protocol)
- [Fail-closed contract](#fail-closed-contract)
- [Relationship to TODO.md](#relationship-to-todomd)

## Task schema

Top level of `queue.json`: `priority_models` (the tier list, below) and `tasks` (the list). Every
task carries every field — no field is optional in the file, because a missing field must fail
`check`, not default silently:

| Field | Type | Meaning |
|---|---|---|
| `id` | string, unique | Stable identifier; referenced by `blocks`/`blocked_by`. Never reuse an id. |
| `title` | string | One-line human description. |
| `estimate_h` | number ≥ 0 | The task's own cost in hours. Uncertain estimates carry `estimate: provisional` in `notes`. A missing or non-numeric estimate is a validation error — the tool never guesses. |
| `blocks` | list of ids | Tasks this task blocks (its dependents). Edges point task → dependent. |
| `blocked_by` | list of ids | The stored mirror: every task whose `blocks` names this one. Maintained by the tool on every mutation; `check` fails if it drifts from the derived mirror. Structural only — a task whose blockers are all `done` is runnable even if `blocked_by` is non-empty. |
| `state` | `queued` / `running` / `blocked` / `done` | `blocked` is a manual annotation for an *external* gate (an owner decision, a missing authorization) — it is not the same as having entries in `blocked_by`. |
| `model` | string, free tag | The model the task serves, e.g. `dsv4.1-1017`, `glm-5.3`, `glm-5.3-flash`, or empty. Drives tiering (below). |
| `node_cost` | `` / `single` / `quartet` | Fleet cost of the task's run. |
| `notes` | string | Caveats, claim stamps, `estimate: provisional` markers. |
| `provenance` | string | Pointer into the work record (`TODO.md` §section, `DEEPSEEK.md` §…, `GUIDANCE.md` §…). A queued task with no provenance is a defect. |
| `claimed_by`, `claimed_at` | strings, optional | Set by `update --claimed-by` (the tool stamps the UTC timestamp); cleared by `done`. A `done` task carrying either fails `check`. |

## Weight

```
weight = estimate_h − Σ estimate_h over every task this task transitively blocks
```

Transitive, deliberately: unblocking a task unblocks the whole chain behind it, so the credit is
the chain's total time, not only the direct dependents'. If A blocks B (12 h) and B blocks C
(12 h), A's blocking credit is 24 h, not 12 — that is exactly the owner's illustration. A task
whose blockers are all `done` gets no credit from them: a `done` task no longer blocks, and
traversal stops there, so finishing work lets the blocked tasks' own weights rise and the queue
re-sort itself on the next read. Weights can be negative (a 1 h control gating 4.5 h of arms
weighs −3.5) — that is the mechanism working.

**Worked example (the owner's 48 h / 24 h case).** A queue holds 48 h of work: task X takes
24 h, and behind it sit tasks totaling 24 h (X → A 12 h → B 12 h). X's weight is
`24 − (12 + 12) = 0` — lighter than any other queued task, so X floats to the top of the queue
despite being the most expensive item in it. The 48-hour-deep queue's next opportunity is X,
because running X is the only act that converts 24 h of blocked work into runnable work.

Ordering: sort ascending by weight (lighter first). Weights are recomputed from the file on every
`queue`/`render`/`weight` read — the tool never stores a derived number.

## Priority tiers (the owner's standing override)

Tiering is applied **before** weight: a task's `model` tag is matched (case-insensitive,
exact-match after trimming) against `priority_models`; tier index = the first tier whose tag set
contains it, and unmatched or empty models fall to a trailing tier after all listed ones. Within
a tier, weight ascending, then `id` ascending as the deterministic tie-break. So the seeded list

```json
"priority_models": [["deepseek-v4.1-flash-1017", "dsv4.1-1017"], "glm-5.3", "glm-5.3-flash"]
```

gives: tier 0 = DeepSeek-V4.1-Flash-1017 items (a tier may be a string or a **list of equivalent
tags** — the registry spells the model both ways, so both tags share tier 0), tier 1 = GLM-5.3,
tier 2 = GLM-5.3-Flash, tier 3 = everything else. To change the policy, edit `priority_models` in
`queue.json` — no tool change is needed; `check` validates the shape.

## Session protocol

1. **At session start, read the queue**: `uv run python -B tools/task-queue.py queue`. Work the
   top of your tier; `weight --id X` shows any task's arithmetic if the order is not obvious.
2. **Claim before you boot**: `update --id X --state running --claimed-by <session-name>` stamps
   `claimed_at` (UTC). A task claimed `running` in the file is the claim — a message is not.
3. **On completion**: `done --id X`. The tool clears the claim fields; the next `queue` recomputes
   every weight the finished task was inflating.
4. **When adding work**, state the estimate (with `estimate: provisional` in `notes` if
   uncertain) and what the task blocks (`--blocks` for dependents, `--blocked-by` for blockers —
   the mirror is derived either way). Refuse to queue work whose estimate you cannot state; the
   whole mechanism runs on estimates.
5. **External gates** use `block --id X` / `unblock --id X` (a state flip, not an edge) plus a
   `notes` line naming the gate, e.g. an owner decision in `TODO.md` §"Retry queue — window 4".
6. **Escalation**: when the queue and reality disagree — a task has been `running` with no
   heartbeat across sessions, a blocker turned out to be unmeasurable, or the ordering contradicts
   what actually ran — fix the queue first (`update` the state/estimate), then say so in the
   session report. The queue is the scheduler's source of truth; leaving it stale is the defect
   this protocol exists to prevent.

## Fail-closed contract

`check` — and every command that reads the file — exits non-zero with a precise message (naming
the offending id) on: duplicate ids; a dangling id in `blocks` or `blocked_by`; a cycle in
`blocks` (no well-defined weight exists); a missing, non-numeric, or negative `estimate_h`; a bad
`state` or `node_cost`; a stored `blocked_by` out of sync with the derived mirror; a `done` task
still carrying claim fields. There are no silent defaults anywhere in the tool.

## Relationship to TODO.md

`TODO.md` stays the work record: item text, owner decisions, receipts, and history live there and
only there. `queue.json` is the scheduler's view — ids, estimates, and edges — and every queue row
must cite its `TODO.md` (or lane-doc) section in `provenance`. `render` emits the markdown table
pasted into `TODO.md`/`STATUS.md` when a section wants the live ordering; re-run it after every
re-sort rather than editing the pasted table by hand. Work is added to both: the descriptive item
in `TODO.md`, the schedulable row in `queue.json`, linked by the `provenance` pointer.