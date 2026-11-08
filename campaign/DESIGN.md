# Campaign director — design

The campaign driver is the project's top priority because it gates every boot: a night that re-runs
an arm the tree already refused, or counts a dead arm as measured, spends node-hours and produces no
new number. This document is phase 1 of the driver epic — the design, the skeleton, and the
acceptance tests that can be decided without a fleet. Phase 2 is one unattended multi-arm campaign
that shows every checklist item on hardware; §Phase 2 names what that run must demonstrate.

## Name

`campaign/`, because "campaign" is already the noun this repository uses for a multi-arm
measurement run (`mad-science` windows, `.scratch/tp12-campaign/`, the receipts directories). The
package is `sparkrun_campaign` (importable; the distribution is `sparkrun-campaign`). Rejected:
`tools/driver.py` — `tools/` is stdlib-only by rule and must stay that way; `orchestrator/` — names
the scheduling mechanism rather than the thing being scheduled, and this tree already has
`sparkrun` for orchestration.

## Component split

| Module | Owns | Not its job |
|---|---|---|
| `protocol.py` | The director↔worker wire: message constructors, one-JSON-object-per-line framing, size limit | Campaign state (that is `state.py`) |
| `evidence.py` | The two evidence readers: the skip source (`metadata.measured_rejected`) and the receipt predicate (`ladder` / `accuracy_status` fields plus the cell table) | Deciding what to do about an arm |
| `state.py` | The persisted plan and per-arm records: atomic file writes, the single-director lock, lease/bookkeeping transitions | Which arm is next (that is `plan.py`) |
| `plan.py` | The two plan sources (manifest and register), plan order, the register client that claims and closes rows through the tool, and the pure placement function | Talking to a worker |
| `fleet.py` | Docker facts: which containers a recipe left on which hosts, and removal of only those | Knowing why it was asked |
| `director.py` | The service: prints the exclusions, claims the arm in the register before its lease, hands out leases, decides "measured" from receipts, reclaims dead leases, spawns workers, writes per-arm receipts | Running an arm |
| `worker.py` | One slot: poll, run `tools/run-arm.sh`, heartbeat the lease, report the return code | Interpreting the return code |
| `systemd/sparkrun-campaign.service` | Supervision on the head | Anything about a specific campaign |

The per-arm executor is **not** in this tree. `tools/run-arm.sh` already implements the readiness
loop that polls the watchdog, serve-log harvest, all-rank teardown and the `rc=6` leftover gate; a
Python reimplementation would be a second, unmeasured copy of the most expensive code in the
project.

## Why assignment is dynamic, not a slice

The 2026-11-04 campaign lost 2.02 node-hours because one node's share of the plan ended with a
132-minute arm while the other node sat idle with nothing queued. That is not an ordering problem —
no ordering fixes a static cut that cannot see its peer. The director therefore holds the whole
plan and hands the next pending arm to *whichever slot asks*: when a slot drains, its request is
served from the same queue, so a long tail cannot strand a node (`plan.next_assignment`). The
defect is kept as a negative control (`test_plan.NegativeControls`) so it cannot come back as a
"simplification".

Ordering is the manifest's order. A longest-first heuristic was considered and dropped: expected
durations are unknown for an arm that has never run, and a wrong guess reorders the plan for no
measurable gain. What is recorded when known is duration, in the receipt; re-ordering on it is a
later decision with data behind it rather than a guess in the first version.

A TP=2 arm takes two hosts in **one** lease: `run-arm.sh` is launched once with both, so one worker
owns the pair and there is no way for two workers to half-own an arm.

## Queue mode: the register as the plan source

A manifest lists the arms a session already decided on. The register (`mad-science/queue.json`,
protocol `mad-science/QUEUE.md`) lists the work the programme has not done yet, and a queue campaign
reads it instead: `serve --queue [path]` (`path` defaults to `mad-science/queue.json` under
`--repo-root`), mutually exclusive with `--manifest`. The owner's requirement is the reason — a
drained manifest must not leave a declared node idle while the register holds bootable work.

A row becomes an arm only when it is machine-runnable: `state == "queued"` plus the optional
`recipe` (a tracked `recipes/<lane>/<arm>.yaml`) and `tp` (1/2/4, equal to its `node_cost`). The arm
name is the recipe's basename, because that is what the receipt window and the skip source are keyed
on; `env` travels into the lease unchanged. Rows without those fields are authoring, docs or
analysis work and no scheduler may boot them.

Exclusions are named, never truncated:

| Row | Effect |
|---|---|
| `blocked` | `queue-skip: <row> (register state blocked)` — an external gate is not the campaign's to open |
| `running`, another session | skipped, naming `claimed_by` |
| `running`, this campaign's session id, arm already in this campaign | **offered** like a queued row: it is the in-flight arm a restart must finish, and the campaign's own lease/reap record is what makes re-assignment safe |
| `running`, this campaign's session id, no campaign state holds the arm | refused by name (`stale claim`): a row that claims this session id with no lease record behind it is a root that was lost, and adopting it would boot an arm nobody has verified stopped |
| `done` | skipped; if this campaign holds no measurement for that arm it is blocked, not booted |
| `blocked_by` not an explicit empty list | skipped by name (`queue-skip: <row> (blocked by <ids>)`): a live dependency edge holds the row whatever its `state`, and a missing mirror is not an edit that opens it |
| no `recipe`/`tp` | counted in one line (`authoring, not bootable`): most rows are prose work |
| `tp` > declared hosts | skipped by name (`tp=4 needs 4 hosts, 2 declared`); a quartet is never cut onto fewer nodes |
| two rows naming one recipe | one arm: any non-runnable sibling (`blocked`, `done`, a live edge, another session's claim) holds it by name (`queue-skip: <row> (recipe also named by sibling <id> is 'blocked')`), so a blocked or done row protects the recipe; two runnable rows are an ambiguity, named with both ids and skipped for that tick only, because the register has not said which row the numbers would close |

**Ordering is the register's.** The plan is `tools/task-queue.py queue --json` in the order it
prints — tier, then weight ascending, then id, which is exactly what the weight is for: a row that
unblocks a chain floats. A guard in `tests/test_task_queue_tool.py` pins the machine read to the
human table, so the ordering has one implementation and no second copy to drift. Placement is still
`plan.next_assignment`, so the declared `--hosts` set is the whole node set and the director never
chooses nodes; what it discovers is *work*.

**The claim is the lock.** Before a lease exists, the director writes the claim through the same
tool: `task-queue.py update --id <row> --state running --claimed-by sparkrun-campaign:<campaign>`.
A worker can only launch from a lease, so no arm boots unclaimed, and the session id is derived from
the campaign name so the next life recognises its own claim. The claim re-reads the row it is about
to overwrite, because the plan was cached: the row must carry an explicit `state: queued` (or this
campaign's own `running` claim) and an explicit empty `blocked_by` list. A row a peer flipped to
`blocked`, or one given a blocking edge, refuses the lease; `blocked_by` is a structural hold that
`state` cannot open, and a missing mirror is not an edit that opens one. The refusal blocks the arm,
records it, and prints the disagreement with the cached record
(`queue-blocked: <arm> (<hold>; state.json had pending; the register wins)`). The row is read once
more between the claim and the lease, so a hold landing in that window wins too — a lease is the
only thing a worker launches from, so no boot has happened yet. The register is last-write-wins, so
a hold written after a lease exists cannot un-launch that boot; stopping a running arm is the
lease/reap path, not the register. At the end of the arm:

| Outcome | Register row |
|---|---|
| measured (from receipt fields, never the rc) | `--state done --evidence <measurement dir>` |
| failed | `--state queued` when the row carries no hold, `--notes` appended with `campaign: <reason>` — the row keeps its own justification text and no evidence pointer is invented; the transition clears `claimed_by`/`claimed_at`, so the row cannot be mistaken for a live claim. A `blocked` or `done` state that landed while the arm ran keeps its state and only gains the note: a human's hold outranks the campaign's wish to retry, and requeueing over it is what resurrected the SM121 rows three times on 2026-11-08 |
| blocked (leftover survivor, unverifiable host) | `--state blocked` plus the same note, because a human must look — unless a `done` state already answers the row, which is preserved; the claim is cleared the same way |
| recorded negative | `--state done --evidence "<doc>:<line> (measured-rejected)"` — a recorded negative is an answer, and the citation is its evidence |
| claim refused by the tool | the arm is blocked in the campaign and no lease is issued; the row is left alone |

A tick is not all-or-nothing: a duplicate runnable pair, a non-runnable sibling, or a row naming a
recipe deleted from the tree skips only that recipe/arm, by name, while the rest of the register is
still adopted, reconciled and assigned. `RegisterError` is the only whole-look failure — the
register could not be read — and it alone prints the retry line; a `PlanError` is reported as the
plan defect it is, not as an unreadable file.

A claim that cannot be written is a refusal to boot, not a warning: two sessions on one arm is the
double-boot this project exists to prevent. The tool is the register's only writer (temp file +
`os.replace`), so the campaign never edits the JSON itself; a failed *close* is printed loudly and
the row may still read `running`, which is a queue-tool failure for a human, not a second boot.

**Draining.** Manifest mode is unchanged: drained means exit 0 and stay down. A queue campaign
defaults to **polling** instead — every `QUEUE_POLL` (30 s) a drained plan re-reads the register,
because the owner's requirement is "keep the available nodes busy" and the register is where the
next bootable row lands (an authoring row gains a `recipe`, another session `unblock`s a row). The
interval is what makes it a scheduler rather than a busy loop: rows that are `blocked`, not
bootable, or over the host count are excluded at read time and never re-attempted, and the "no
runnable rows" line is printed once per quiet spell, not per tick. SIGTERM ends the run through the
ordinary service path. `--once` is the escape: run what is runnable now, then exit 0 like a manifest
campaign — for a preflight, or an operator who wants one pass.

Preflight against the live register (no boot, no worker; it prints the exclusions, the skip lines
and the plan, and creates/updates `state.json`):

```bash
cd <checkout>/campaign
uv run --frozen python -m sparkrun_campaign.director serve --queue --dry-run \
  --hosts "$CAMPAIGN_HOSTS" --root "$CAMPAIGN_ROOT"
```

## Wire protocol

A Unix stream socket at `<campaign-root>/director.sock`, one JSON object per line, one request per
connection. Not HTTP, and not a port: the director spawns every worker on the same host, so a
filesystem path reaches all of them, while the head's TCP ports are contested (serves bind
8000/8010, a BeeGFS daemon holds 8010) and a collision looks exactly like a boot that never becomes
ready. A socket path also needs no authentication.

Worker → director:

```json
{"op": "poll",   "worker": "w1"}
{"op": "beat",   "lease": "<arm>@<attempt>"}
{"op": "report", "lease": "<arm>@<attempt>", "rc": 0, "note": "log .../arm@1.log"}
```

Director → worker:

```json
{"op": "assign",   "lease": {"id", "arm", "path", "hosts", "tp", "env", "expires_at"}}
{"op": "idle",     "retry_after": 5.0}
{"op": "ack",      "status": "measured"}
{"op": "revoked",  "reason": "lease expired or unknown"}
{"op": "error",    "reason": "..."}
{"op": "shutdown"}
```

**Cadence.** An idle slot polls every 5 s. A running arm beats every 20 s from a thread, because the
worker blocks on the executor for 20–130 minutes and a blocking worker cannot prove it is alive.
Polls are one local round trip; their cost is noise against an arm.

**Lease and reclaim.** The lease TTL is 300 s: fifteen missed beats. The bound that decides it is
the director's longest in-request stall, not a dead worker's detection latency — `_report` reaps
before it answers, and that reap is two listing probes, one `sparkrun stop` (bounded at 60 s),
per-container removals and the verifying re-probe, under 160 s worst case. A lease that expired
while another worker's report was being reaped would re-boot a live arm, which is the waste this
design exists to prevent; five minutes of detection latency is noise against a 20–130 minute arm.
A short axis is chosen the other way everywhere else in this tree (the watchdog counts observations,
not durations); here the asymmetry of the two mistakes decides it.

A lease past its deadline is expired by the director, and the arm comes back **pending but not
assignable** until its hosts are proven clean (`needs_reap`). The reclaim path is the same
`fleet.reap` that runs after every arm, on every host of the lease:

1. list containers carrying this recipe's `sparkrun.recipe` label, on **every** host of the lease;
2. `sparkrun stop <task>` for each task id recovered from a container name, then `docker rm -f` for
   survivors;
3. re-probe; report clean only if the second probe is empty.

A failed probe is never read as clean: `fleet.leftovers` raises, and the arm is blocked with the
host named. A blocked arm is not retried by the running director (hammering ssh is not evidence); a
restart retries, and a successful reap returns it to the queue.

The wire protocol is deliberately not where readiness lives. The director never probes an endpoint:
readiness, the dead-serve verdict and the serve-log capture belong to `run-arm.sh` and
`tools/boot-watchdog.py`, and the director's five-minute lease clock must never be able to kill a
loading boot.

## Persisted state and resume

One JSON document, `<campaign-root>/state.json`, rewritten on every transition: serialise, write
`state.json.tmp`, fsync it, `os.replace`, fsync the directory. A power cut therefore leaves the old
document or the new one, never a truncated one. A `flock` on `state.json.lock` makes a second
director refuse to start — two directors over one plan is the double-boot this project exists to
prevent, so the refusal is at open time.

Per arm: `path`, `tp`, `env`, `status`, `attempts`, `failures`, `lease`, `needs_reap`, `last`,
and a bounded history of transitions. Statuses are `pending`, `leased`, `measured`, `failed`,
`skipped`, `blocked`. There is no separate `running`: the lease is the record of what is running.

Start-up (`Director.prepare`) is the resume, in this order:

1. read the skip source; print every `skip:` line; refuse to start if a marker's citation no longer
   resolves (the verdict is untrustworthy, and planning without it is how a recorded negative gets
   booted);
2. read the receipts; print every arm it will not boot because the numbers already exist;
3. expire any lease the previous life left behind;
4. for every arm with a reap outstanding, reap its hosts and record the result;
5. re-check every unresolved arm against the receipts — an arm measured while no director was
   listening becomes `measured` with a receipt of its own and no boot;
6. only then bind the socket and spawn workers.

Assignment re-checks the receipts too, not only start-up: a reclaim can land between a worker's
last cell and its report, and the arm must not be handed out for numbers that are already on disk.

After a reboot the same path runs: `state.json` is on the head's disk, the leases are stale, and
step 3–4 cleans up the containers the reboot did not stop. Nothing about a campaign lives only in
the director's memory.

### State reconciliation: register, state, CLI

Three writers can disagree about one arm, so one precedence rule decides, newest decision first:

| Writer | Wins for | Why |
|---|---|---|
| `--retries` on the command line | every arm, at open | The operator restarting to retry a terminal arm is the newer decision; an omitted flag keeps the number the previous life stored instead of resetting it to `0`. |
| `--receipts-root` on the command line | `ARM_RECEIPTS_ROOT` in every arm that can still run | It is this run's decision and the evidence readers look under it; an executor writing elsewhere produces numbers the campaign cannot attribute. |
| The register row (queue mode) | `env`, and `path`/`tp`/`task` while no reap is outstanding, for an arm that is not leased, measured or skipped | The row is the current launch plan: a client hook or readiness timeout added since the last attempt must reach the next boot. `path` waits for the reap because the containers a reap must find are labelled with the path that launched them. |
| The state record | every field of an arm that is leased, measured or skipped | The record is what is running or what ran; rewriting it would make the state disagree with the receipt it produced. A new attempt is a new decision, so the row's `env` applies to it. |
| The register no longer carrying a state arm | block, never boot | A dropped row means another session or a human closed that work; the campaign's own state cannot see why. |
| A blocked arm | retried on a restart only (`prepare`), and only with `needs_reap == []` | A running director does not retry a blocked arm; a row flipped back to `queued` says the external gate opened, not that the hosts are clean. |
| The register row at assignment time | the lease itself | The plan is cached between reads, so the row is re-read before the claim and again before the lease: `queued`/own-claim plus an explicit empty `blocked_by` are required, a non-runnable sibling for the same recipe holds the arm, and a disagreement with `state.json` is logged with the stricter record winning. |

`prepare` proves that reap (step 4) before reconciling, and `Campaign.cleared` is the one transition
that drops `needs_reap`. A register `unblock` therefore reaches `pending` only through it: a queued
row alone can never turn an unverified host into an assignment, and the arm is named in the log
(`queue-blocked: <arm> (row runnable again, but hosts still need a verified reap: …)`), so a
status-only unblock is a stated refusal rather than a silent no-run. When the register no longer
carries an arm the campaign holds, reconciliation blocks it with the register's own reason
(`queue-blocked: <arm> (…)`).

An attempt is a lease issued, never a report: a boot killed before it reported is an `attempt` on
the receipt but not a `failure` in the retry budget, so restarting a killed arm is counted honestly
and `--retries` remains the only lever over re-boots.

That lever is still bounded by the register. `plan.next_assignment` reads only state.json, so
reconciliation blocks a `failed` arm whose row is not runnable as well as a `pending` one;
widening `--retries` therefore cannot reach past a hold, and the assignment re-read (§The claim is
the lock) is the second gate for a hold written after the last reconcile.

## What "measured" means

`evidence.done(arm_dir)` reads fields, never presence:

- `house.yaml`'s unindented `ladder` must be `ok`, or `failed (rc=N)` for a boot that finished and
  a ladder that did not;
- a `ladder.json` that parses must contain a cell (`benchmarks` / `cells` / `runs` non-empty);
- a `ladder.yaml` proves nothing — `run-arm.sh` writes it the moment a benchmark starts, so it is
  exactly the artefact an arm that died before its first cell leaves behind;
- `accuracy_status` is carried into the receipt beside the score's log, not copied as a number.

The worker reports a return code; the director decides the status. `rc=0` with a partial ladder is
`failed`, and an `rc=4` with a full receipt is `measured`. The receipt records both, so the
disagreement is auditable (`status` beside `ladder`).

## Reused from `tools/` versus reimplemented

| Thing | Decision | Why |
|---|---|---|
| `tools/run-arm.sh` | **Reused as a subprocess**, unchanged | It is the measured executor: readiness loop that also polls the watchdog, serve-log harvest before teardown, all-rank removal by name, `rc=6` leftover gate, `rc=7` replayed-state gate. |
| `tools/boot-watchdog.py` | **Reused as a subprocess**, spawned by `run-arm.sh` | Items 3 and 4 are its behavior (two observed absences, serve log captured before the stop). The director deliberately has no serve liveness logic. |
| `tools/next-arms.py` skip reader | **Reimplemented** (`evidence.skips`) | Importing a dash-named script from another project is a hack, and its CLI is fleet-shaped (it ssh-probes nodes), so importing it would drag a probe into the decision path. A parity test compares both implementations over the whole tracked tree and over shaped receipts, so drift fails the suite rather than the campaign. |
| `tools/next-arms.py` manifest/placement | **Reimplemented** (`plan.py`) | Its placement copies node lists out of a live probe and prints launch lines; the campaign needs a queue and leases. Same manifest shape is accepted. |
| `tools/task-queue.py` register | **Shelled out to** (plan source and claim writer) | It owns the register: the ordering (`queue --json`, so the weight arithmetic has one implementation), and every write (claim, done, note) through its own atomic save. Editing the JSON here would race that save. A manifest campaign never touches it. |
| `sparkrun` CLI | **Shelled out to**, never imported | `AGENTS.md` keeps `plugins/` as the one tree that imports sparkrun. The executor already shells out, and a subprocess keeps the suite runnable with no sparkrun and no GPU. |

### The per-node daemon preflight (in `run-arm.sh` since d6fae84)

- **The probe is a new ssh-to-`sparkrun` dependency.** `run-arm.sh` has never run anything on a node
  but `bash -s` and `docker …`, so the remote binary and `HOME` are resolved, never assumed: one
  `bash -s` per host that prepends the PATH sparkrun's own remote detection uses
  (`$HOME/.local/bin:$HOME/.cargo/bin:/usr/local/bin:/usr/bin:/bin`,
  `orchestration/systemd_service.py:262-268`), prints `command -v sparkrun` and `$HOME`, then calls
  the resolved absolute path with `HOME` pinned to it. Measured 2026-11-08: `which sparkrun` →
  `/home/red/.local/bin/sparkrun` and `$HOME` → `/home/red` on every node, the same pair sparkrun's
  own detection returns, and the launch's one-liner form (`ssh <host> <command>`,
  `orchestration/ssh.py:705`) runs under the same sshd `HOME` — the probe follows the launch's
  environment instead of guessing one.
- **Why it is pinned.** A wrong `HOME` reports a running daemon as down: measured on the head,
  `HOME=/tmp/wrong-home … daemon status` answered `"running": false` where `HOME=/home/red`
  answered `true`. The preflight must not be able to refuse the fleet on its own environment.
- **Not `daemon resources list`.** It is not a liveness probe and has no RPC behind it: it reads
  *this controller's* reservation table (`cli/_daemon.py:409-413` → `reservations(config_path.parent)`,
  `core/coordination.py:311-316`), so it can never see another host's daemon.
- **Exit codes do not discriminate.** `daemon status` exits 0 for `"running": false` and for `true`
  alike (measured 2026-11-08), so the field decides, never `$?`.
- **Three outcomes, not two** (the `boot-watchdog` `no_probe` idiom): `"running": false` is the
  inactive-daemon refusal, exit **9**, naming the host and `sparkrun daemon start`; a probe that
  could not read — ssh non-zero, binary not found, output without a `running` field — is
  **unverifiable**, exit **10**, naming the probe and what it could not read; `"running": true`
  proceeds. A failed probe must never render as "daemon not running", and an unreachable host is
  unverifiable: it neither continues the arm nor concludes the daemon is down.
- **Evidence.** One `daemon-preflight.txt` in the arm's receipt directory, a line per host —
  `<host>,<resolved binary>,<HOME>,<the status line or the probe's stderr>` — written before any
  refusal, so a refused arm says which environment it probed. A refusal with no recorded probe is
  unfalsifiable.
- **Placement.** After the arm's last precondition (the slot gate) and before the exit-capture arm
  loop, therefore before the launch. Arming first is a leak: the EXIT trap that kills the watchers
  is installed further down, so a refused arm would leave one `docker events` client per host.
- **Taken exit codes.** `exit 1` usage / no container / no chdir, `rc=2` ladder, `rc=3` instrument,
  `rc=4` readiness ceiling, `rc=5` and `exit 5` missing artefact and failed launch, `rc=6` leftover
  survivor, `rc=7` and `exit 7` replayed state, `exit 8` slot-limited; 9 (inactive) and 10
  (unverifiable) are reserved here.
- **Tests** (`tests/test_run_arm_tool.py`, a fake `ssh` on `PATH` returning each case): one host
  inactive → exit 9, that host named, nothing launched; all active → the next step runs; ssh
  non-zero, or a status with no `running` field → exit 10 with no "not running" claim; negative
  control — with the block removed the inactive host's arm launches and the exit-9 assertions fail.

## Failure modes a campaign run has shown, and what prevents each

| Observed | Structural prevention |
|---|---|
| The driver had an inline `derive()` and never read the skip source, so two recorded negatives were booted | The skip source is read in `prepare()` before the socket exists or a worker is spawned; a stale citation stops the start. New code cannot reach an assignment path without passing it. |
| Completion was presence-only (`is_file()` + size > 0) and could not tell a partial ladder from a measured one | `evidence.done` reads fields and the cell table; the worker's rc cannot promote an arm. Two negative controls keep the old predicates in the suite as failing examples. |
| A watchdog-reaped TP=2 arm left rank 1 running on the second node | Reap enumerates by the recipe's own label on **every** host of the lease and re-probes; the listing is never rank-filtered, and a survivor blocks the arm instead of passing as clean. Control: the rank-0-only check. |
| 2.02 node-hours lost because one stream's last arm ran 132 minutes while the other node was idle | Assignment is dynamic from one queue (`plan.next_assignment`); nothing cuts the plan into per-node slices. Control: the static slice leaves a free node with nothing runnable while work is pending. |
| An inactive per-node `sparkrun` daemon surfaced as `[3/6] Distributing resources` then `[Errno 70] Communication error on send: /home/red/.cache/huggingface/token`, a token/permission error that it is not (leases `@3`–`@6`, 2026-11-08) | `sparkrun daemon status` on **each** host of the lease before the launch, and `sparkrun daemon start` on any host that answers `"running": false`. |
| A worker (or the host) dies mid-arm, and the arm's containers keep running | Leases expire; the arm becomes pending-with-a-reap; the reap runs on all its hosts before it is handed out again. The worker also stops its own slot after 12 unreachable polls, so an orphan cannot outlive a crashed director indefinitely. |

## Dependencies

**None.** `pyproject.toml` declares an empty dependency list on purpose: the whole design is
`socket` + `socketserver` (protocol), `json`/`os`/`fcntl` (state), `subprocess` (fleet + executor),
`argparse`, `threading` (worker heartbeat) and `unittest` (tests). `uv` manages the interpreter and
the project directory; `[tool.uv] package = false` means nothing is built or installed, so a start
needs no network and no build backend. `pytest` was not taken: the repo's convention is stdlib
`unittest`, its guards are judged by negative controls rather than by framework features, and one
test command for both trees is worth more than richer assertions.

The cost of `package = false` is that the package is imported by path, not installed: commands that
use `-m` must run with the campaign directory as the working directory (the systemd unit sets
`WorkingDirectory`), and the test command passes `-t campaign` so discovery puts
`sparkrun_campaign/` on `sys.path`. That is the trade for an offline-capable start with no build
step.

## Tests, one command, and CI

The one command, from the repository root:

```
uv run --project campaign --frozen python -B -m unittest discover -s campaign/tests -t campaign
```

`--frozen` keeps a run on the committed `uv.lock`; drop it only when changing `pyproject.toml`.
A single module or case, from `campaign/`:
`uv run --project . --frozen python -B -m unittest tests.test_director`, or
`... tests.test_director.Resume.test_a_report_for_a_reclaimed_lease_is_ignored`.

CI runs **exactly that command**, as the step `Campaign driver suite (its own uv project, zero
dependencies)` in `.github/workflows/gate.yml`. It runs on the hosted runner because nothing in it
needs a GPU, a node, docker, ssh or sparkrun: the director is driven through a fake fleet with
fixture receipts. The subprocesses it starts are `git` (the parity fixture and the register
round-trip) and, in one register test, `tools/task-queue.py` itself — a stdlib script, so the hosted
runner already has everything it needs.

One smaller gate change came with it: a `py_compile over the campaign tree` step, because the
documented loop compiles `tools`, `plugins` and mod Python only, and `tests/test_ci_workflows.py`
pins that loop verbatim — so the campaign tree gets its own step rather than an edit to the
documented command. Before this phase the tree was invisible to the gate: not compiled, not tested.

Checklist to test map:

| Item | Where | State |
|---|---|---|
| 1. reads the skip source, prints `skip: <arm> (<verdict>, <doc>:<line>)` before any boot | `test_evidence.SkipSource`, `test_director.SkipSource.test_skip_lines_are_printed_before_anything_can_be_assigned`; journal + 5 `skipped` receipts, 2026-11-07 | **green** |
| 2. reads receipt FIELDS, not file presence | `test_evidence.ReceiptFields`, `test_director.CompletionIsReadFromReceipts` | **green** |
| 3. reaps a dead serve in ≤ 2 probes | `test_checklist_hardware` (skipped) + `tools/boot-watchdog.py`; `verdict=dead` at t=43 s (labquant) and t=95 s (cyankiwi), 2026-11-07 | **green** |
| 4. preserves the serve log across that reap | cyankiwi's 26 KB `serve-reaped-*.log`; labquant's log was absent in the container and its live `docker-*.log` was retained instead, 2026-11-07 | **green** |
| 5. reaps every rank | grammar and listing (`test_fleet.Leftovers`); TP=2 labquant's rank-1 container removed on the second host, 2026-11-07 | **green** |
| 6. no container behind on any host | block-and-record (`test_director.Leftovers`); post-campaign probe 0 containers / 0 volumes on both hosts, 2026-11-07 | **green** |
| 7. resumes a half-finished campaign after a reboot | `test_state.Leases`, `test_director.Resume`; service stopped/started at the first receipt, same plan resumed and no terminal arm re-booted, 2026-11-07 | **green** |
| 8. writes per-arm receipts | `test_director`; 7 receipts (5 skipped, 2 failed) in the 2026-11-07 campaign | **green** |

Every off-hardware item carries a negative control: presence-only completion accepts a partial
ladder, a manifest-only plan boots a recorded negative, a static slice strands a node, a resume that
trusts the state file re-boots a live arm, and a rank-0-only leftover check reports clean with rank
1 alive. The four hardware items still have their skipped harness tests in
`test_checklist_hardware.py`; the 2026-11-07 run is the evidence that closed them.

Counting the root suite from a committed tree needs **the repository's own interpreter**: archive the
tree, then count it with that clone's `.venv/bin/python -B -c
'import unittest;print(unittest.defaultTestLoader.discover("tests").countTestCases())'`. A bare
`uv run` in the extracted tree builds a fresh venv and reads 1368 against the same tree's 1410,
because `tests/test_qwen3_vl_embeddings.py:26` imports `jinja2` and discovery turns that into one
failed module. The totals themselves stay in `AGENTS.md`, which owns them.

## Per-arm receipts

`<campaign-root>/receipts/<arm>.json`, written atomically at the end of every arm — measured,
failed, blocked, or found measured on disk at start-up. Fields: campaign, arm, recipe path, tp,
hosts, lease id, attempt, start/end, `rc`, `status`, `reason`, `measurement_dir`, `measured`,
`artefacts`, `serve_logs`, `ladder`, `accuracy_status`, `marker_shape`, `house_score`, `client`,
`metrics_status`, `oom_watchdog`, `watchdog`, `leftovers`. `marker_shape` names the `house.yaml` shape the
outcome fields came from: `run-arm`'s flat marker (`suite`/`ladder`/`accuracy_status`) or
sparkrun's nested
`sparkrun_benchmark` sidecar, whose outcome lives under `benchmark`/`results` and which carries
no ladder field of its own. `house_score` carries the sidecar's own `results.json.final_score`,
because a fabricated `ladder: ok` would let a sidecar recording a failed run read as measured.
`ladder` is never left blank: a flat marker's own verdict is copied verbatim, and for any other
shape the field names the artefact the cells came from and its row count
(`measured — ladder.json (7 rows)`), says `absent — no ladder artefact in this receipt`, or names
the defect (`not a measurement — ladder.json parses to no cell`). The 753B second boot measured
seven rows into `ladder.json` while its receipt read `ladder: ""`, so the cells had to be
recovered from the CSV; the field is a receipt account, not the verdict — `done()` still decides
measurability, and a sidecar's house score can measure an arm whose ladder is absent without the
ladder reading as `ok`. `metrics_status` is read from the scrape's own artifacts —
`metrics-status.txt`'s per-host `<status> host=… url=… reason=…` lines and the
`metrics-<host>.txt` bodies — and never through the marker, because a `sparkrun_benchmark`
sidecar discards every flat key. `captured` needs that host's own non-empty body or the field
says `disagrees — …`; a missing artifact is `{"status": "", "reason": "no artifact"}`, so a
scrape that never ran is never `absent` (the engine exposing nothing). `oom_watchdog` is the earlyoom verdict, read from `oom-watchdog.txt` beside the marker: `earlyoom-terminated` (a journal line names the process; earlyoom sends SIGTERM, so the engine exits 143), `clean` (a readable journal, an exit outside {137,143}, a result artifact) or `unknown` (a 137/143 with no line, an unreadable journal, no artifact — never a default to `clean`), with the quoting line and the exit/unread/artifact facts in `reason`. `client` is the
arm-scoped extra client's receipt (`client/client.json`: cell, image_id, rc), empty when the arm
ran no extra client. The numbers themselves stay where the executor wrote them
(`~/benchmarks/tp12-<date>/<arm>/`); the receipt is the campaign's own account of the arm and
points at them, so a reader never has to guess which window a status refers to.

## Supervision on the head

A **per-user** unit: the campaign runs as the account that owns the checkout and the SSH keys, and
no step needs privilege. `loginctl enable-linger` is what makes it survive the last SSH session
ending, and a reboot.

Install (no root anywhere):

```bash
# 1. one time: user services run without a login session (also after a reboot)
loginctl enable-linger "$USER"
loginctl show-user "$USER" -p Linger                  # expect: Linger=yes
# If the distribution's policy forbids self-linger, `sudo loginctl enable-linger <user>` is the
# only privileged step: a one-time permission, not a root daemon.

# 2. the per-head run definition. Untracked on purpose -- it carries the node set, and a tracked
#    file with cluster addresses fails `tests/test_tracked_address_hygiene.py`.
umask 077
$EDITOR ~/.config/sparkrun-campaign.env
#   CAMPAIGN_MANIFEST=<checkout>/.scratch/<campaign>/manifest.json
#   CAMPAIGN_HOSTS=<node-a>,<node-b>
#   CAMPAIGN_ROOT=<home>/benchmarks/campaign-<name>

# 3. install and start
mkdir -p ~/.config/systemd/user
cp <checkout>/campaign/systemd/sparkrun-campaign.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now sparkrun-campaign.service
```

The shipped unit starts a **manifest** campaign (`--manifest ${CAMPAIGN_MANIFEST}`). A queue
campaign is the same unit with one override — the register is the plan, so `CAMPAIGN_HOSTS` and
`CAMPAIGN_ROOT` keep their meaning and no manifest is named:

```bash
systemctl --user edit sparkrun-campaign.service   # drop-in:
#   [Service]
#   ExecStart=
#   ExecStart=/usr/bin/env uv run --project %h/src/sparkrun-recipe-registry/campaign --frozen \
#     python -B -m sparkrun_campaign.director serve --queue --hosts ${CAMPAIGN_HOSTS} \
#     --root ${CAMPAIGN_ROOT}
systemctl --user daemon-reload
systemctl --user restart sparkrun-campaign.service
```

`--queue` with no path is `mad-science/queue.json` under `--repo-root` (the checkout the package
lives in), so a checkout's own register is what the service reads. Without the override the same
campaign can be started by hand, which is what the operator command below does.

Preflight without booting anything (this is the human check for item 1 — it prints the `skip:` lines
and the plan, then exits; it does not bind the socket or spawn a worker, but it does create/update
`state.json`, which is the record of what the plan is):

```bash
cd <checkout>/campaign
uv run --frozen python -m sparkrun_campaign.director serve --dry-run \
  --manifest "$CAMPAIGN_MANIFEST" --hosts "$CAMPAIGN_HOSTS" --root "$CAMPAIGN_ROOT"
```

Verification:

```bash
systemctl --user is-active sparkrun-campaign.service      # active
systemctl --user show sparkrun-campaign.service -p ExecStart -p WorkingDirectory
journalctl --user -u sparkrun-campaign.service -n 40 --no-pager   # the skip lines come first
ls "$CAMPAIGN_ROOT"/state.json "$CAMPAIGN_ROOT"/director.sock
```

That the unit is not tied to a login session is shown, not assumed, by disconnecting and asking
again from a new shell:

```bash
systemctl --user is-active sparkrun-campaign.service      # still active
ps -o lstart= -p "$(systemctl --user show -p MainPID --value sparkrun-campaign.service)"
```

Stopping: `systemctl --user stop sparkrun-campaign.service`. SIGTERM goes to the director, which
signals each worker's process group; `run-arm.sh`'s own trap stops the serve, and whatever it could
not finish is reaped on the next start. Every start is a reconcile, not a replay: it adopts an
explicit `--retries`, writes `--receipts-root` into the arms it can still run, refreshes unstarted
arms from their register rows, and re-opens a blocked arm only when its row is runnable again and
its hosts are proven clean (§State reconciliation). `KillMode=mixed` plus `TimeoutStopSec=180` give
the director's 100 s worker grace and then that trap time to run `sparkrun stop`.
`Restart=on-failure` retries a crash (safe: every start resumes), while
`RestartPreventExitStatus=2` keeps a refusal — a stale citation, a bad host set, a missing executor
— failed for a human instead of restarting every 15 s. A drained manifest campaign exits 0 and
stays down, which is the completion signal; a queue campaign in poll mode keeps serving (§Queue
mode) and is stopped like any other service.

While a run owns the state lock, an operator reads it through the same module without disturbing it:

```bash
cd <checkout>/campaign
uv run --frozen python -m sparkrun_campaign.director status --root "$CAMPAIGN_ROOT"
```

Deliberately not done: a system-wide unit (needs root for no benefit), a timer (a campaign is
started by a decision, not a schedule), and `Restart=always` (a finished campaign must not restart
and re-read a plan whose arms are all answered).

## Phase 2: what the campaign run must show

One unattended campaign over the declared node set, covering the whole checklist in one run:

- the journal's first `skip:` lines precede the first `assign:` line, and no arm in the skip source
  is ever assigned;
- every `<campaign-root>/receipts/<arm>.json` exists, with `leftovers: []`, and none of the four
  hardware items is claimed without its evidence: `watchdog: dead` on the second observation, the
  harvested `serve-node_*.log` named in `serve_logs`, a TP=2 arm whose end-of-arm probe asked both
  hosts, and a post-campaign probe of the campaign's hosts with no `sparkrun_*` container;
- a deliberately interrupted restart (reboot or `systemctl --user restart`) resumes the same plan
  without re-booting a measured arm;
- the campaign ends drained, with the node-hour accounting the old driver lost: no node idle while
  a pending arm existed.

## Acceptance campaign (2026-11-07)

Phase 2's run, executed as one unattended service campaign over the declared pair. The manifest has
seven arms; five are answered by the skip source and must never be assigned, and two are boots:

| Arm | TP | Expected |
|---|---|---|
| `zz-labq-no-diag` | 2 | boot; dies before the engine writes `/tmp/sparkrun_serve.log`, so its `docker-*.log` is the only cause |
| `zz-cyankiwi-ornith-1.5-122b-awq-int4-dflash2-sglang` | 1 | boot; the retry the live capture exists for |
| `zz-spark-x2.6-4b-int8-sglang` | 1 | skipped, `recipes/explore/README.md` |
| `nex-n2.5-mini-uncensored-nvfp4-sglang` | 1 | skipped, `attic/cybersec/AGENTS.md` |
| `nex-n2.5-mini-uncensored-nvfp4-vllm` | 1 | skipped, `attic/cybersec/AGENTS.md` |
| `qwen3.8-flash-next-uncensored-nvfp4-sglang` | 2 | skipped, `recipes/cybersec/README.md` |
| `qwen3.8-flash-next-uncensored-nvfp4-vllm` | 2 | skipped, `recipes/cybersec/README.md` |

Restart point: the service is stopped and started again as soon as the first boot's receipt exists,
so the resume path is exercised while the second arm is pending. The proof is that the measured arm
is never booted again, the lease grace after the restart costs at most one re-boot of the in-flight
arm (`attempt: 2` in the cyankiwi receipt, re-assigned at 01:05:45 after the
`reaped … lease expired; 0 container(s) found` line), the same plan is reported, and no lease is
handed out before its hosts are cleared.

Each checklist item's evidence: the five `skip:` lines before the first `assign:` and five
`skipped` receipts (items 1 and 8); a `watchdog: dead` receipt with its harvested `serve-node_*.log`
(items 3 and 4); the `docker-*.log` from the live follower (phase 2's added capture); a TP=2 receipt
naming both hosts and an end-of-arm probe that asked both (items 5 and 6); the restart's journal and
the absence of a second assignment for the measured arm (item 7); and a post-campaign probe of both
declared hosts with no `sparkrun_*` container.

**Outcome (2026-11-07).** The campaign drained with 5 skipped and 2 failed, exit 0. Both boots died:
`zz-labq-no-diag` exited before the engine wrote its log (`watchdog: dead` at t=43 s; its live
`docker-*.log` holds only the entrypoint banner), and `zz-cyankiwi…` reproduced the fused-MoE
`384 vs 32` weight-loader failure with the watchdog preserving a 26 KB serve log (`verdict=dead` at
t=95 s). The restart point fired at the first receipt: the service stopped and started, the new
director honoured the outstanding lease for its remaining TTL, then reaped it (0 containers) and
re-booted that one arm once; the failed labquant arm was not touched. Post-run probes: 0 containers
and 0 volumes on both campaign hosts. Receipts: 5 skipped, 2 failed.

## Non-goals of phase 1

No boots, no docker, no ssh, no `sparkrun` invocation — the package has no code path that runs on
import. No host discovery: the node set is declared, because a campaign that picks its own nodes
would collide with any other session's window. (Amended 2026-11-07 by an owner requirement, which
overrules the original assumption that the register is "not used": what a campaign *discovers* is
work, from the register, and the declared-host rule is unchanged — the director still never chooses
a node. §Queue mode is the new rule; the manifest stays a valid plan source.) No automatic retry of
a *measured-and-failed* arm (`--retries 0` by default): a failure is recorded and reported, and
re-booting a recorded negative is the defect this whole tree exists to stop. No arm-duration cap: the executor and the watchdog
already bound the failure modes they can see, and a wall clock that kills a slow-but-loading arm
would cost the measurement.