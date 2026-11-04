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
| `plan.py` | Manifest validation, plan order, and the pure placement function | Talking to anyone |
| `fleet.py` | Docker facts: which containers a recipe left on which hosts, and removal of only those | Knowing why it was asked |
| `director.py` | The service: prints the exclusions, hands out leases, decides "measured" from receipts, reclaims dead leases, spawns workers, writes per-arm receipts | Running an arm |
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

**Lease and reclaim.** The lease TTL is 120 s: six missed beats. Deliberately generous — a false
reclaim costs a *second boot* of a long arm, which is the waste this design exists to prevent, while
two minutes of detection latency is nothing against an arm. A short axis is chosen the other way
everywhere else in this tree (the watchdog counts observations, not durations); here the asymmetry
of the two mistakes decides it.

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
`tools/boot-watchdog.py`, and the director's two-minute lease clock must never be able to kill a
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
| `tools/task-queue.py` register | **Not used** | The register orders *sessions'* work by weight; a campaign is one task in it, and its plan is the manifest. |
| `sparkrun` CLI | **Shelled out to**, never imported | `AGENTS.md` keeps `plugins/` as the one tree that imports sparkrun. The executor already shells out, and a subprocess keeps the suite runnable with no sparkrun and no GPU. |

## Failure modes from 2026-11-04, and what prevents each

| Observed | Structural prevention |
|---|---|
| The driver had an inline `derive()` and never read the skip source, so two recorded negatives were booted | The skip source is read in `prepare()` before the socket exists or a worker is spawned; a stale citation stops the start. New code cannot reach an assignment path without passing it. |
| Completion was presence-only (`is_file()` + size > 0) and could not tell a partial ladder from a measured one | `evidence.done` reads fields and the cell table; the worker's rc cannot promote an arm. Two negative controls keep the old predicates in the suite as failing examples. |
| A watchdog-reaped TP=2 arm left rank 1 running on the second node | Reap enumerates by the recipe's own label on **every** host of the lease and re-probes; the listing is never rank-filtered, and a survivor blocks the arm instead of passing as clean. Control: the rank-0-only check. |
| 2.02 node-hours lost because one stream's last arm ran 132 minutes while the other node was idle | Assignment is dynamic from one queue (`plan.next_assignment`); nothing cuts the plan into per-node slices. Control: the static slice leaves a free node with nothing runnable while work is pending. |
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
fixture receipts, and the only subprocess the suite starts is `git ls-files` in the parity test.
One smaller gate change came with it: a `py_compile over the campaign tree` step, because the
documented loop compiles `tools`, `plugins` and mod Python only, and `tests/test_ci_workflows.py`
pins that loop verbatim — so the campaign tree gets its own step rather than an edit to the
documented command. Before this phase the tree was invisible to the gate: not compiled, not tested.

Checklist to test map:

| Item | Where | State |
|---|---|---|
| 1. reads the skip source, prints `skip: <arm> (<verdict>, <doc>:<line>)` before any boot | `test_evidence.SkipSource`, `test_director.SkipSource.test_skip_lines_are_printed_before_anything_can_be_assigned` | **green** |
| 2. reads receipt FIELDS, not file presence | `test_evidence.ReceiptFields`, `test_director.CompletionIsReadFromReceipts` | **green** |
| 3. reaps a dead serve in ≤ 2 probes | `test_checklist_hardware` (skipped) + `tools/boot-watchdog.py` | pending a real arm |
| 4. preserves the serve log across that reap | receipt records the harvested logs (`test_director...test_the_receipt_keeps_the_serve_log_of_a_watchdog_reaped_arm`); live capture skipped | half green |
| 5. reaps every rank | grammar and listing (`test_fleet.Leftovers`); live teardown skipped | half green |
| 6. no container behind on any host | block-and-record (`test_director.Leftovers`); live absence skipped | half green |
| 7. resumes a half-finished campaign after a reboot | `test_state.Leases`, `test_director.Resume` | **green** |
| 8. writes per-arm receipts | `test_director` (`receipts/<arm>.json` after every arm, and for an arm found measured at start) | **green** |

Every off-hardware item carries a negative control: presence-only completion accepts a partial
ladder, a manifest-only plan boots a recorded negative, a static slice strands a node, a resume that
trusts the state file re-boots a live arm, and a rank-0-only leftover check reports clean with rank
1 alive. The four hardware items are skipped tests in `test_checklist_hardware.py`, each naming the
receipt evidence the campaign run must produce, so the checklist lives in the suite rather than in
prose.

## Per-arm receipts

`<campaign-root>/receipts/<arm>.json`, written atomically at the end of every arm — measured,
failed, blocked, or found measured on disk at start-up. Fields: campaign, arm, recipe path, tp,
hosts, lease id, attempt, start/end, `rc`, `status`, `reason`, `measurement_dir`, `measured`,
`artefacts`, `serve_logs`, `ladder`, `accuracy_status`, `watchdog`, `leftovers`. The numbers
themselves stay where the executor wrote them (`~/benchmarks/tp12-<date>/<arm>/`); the receipt is
the campaign's own account of the arm and points at them, so a reader never has to guess which
window a status refers to.

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
not finish is reaped on the next start. `KillMode=mixed` plus `TimeoutStopSec=120` give that trap
time. `Restart=on-failure` retries a crash (safe: every start resumes); a drained campaign exits 0
and stays down, which is the completion signal.

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

## Non-goals of phase 1

No boots, no docker, no ssh, no `sparkrun` invocation — the package has no code path that runs on
import. No host discovery: the node set is declared, because a campaign that picks its own nodes
would collide with any other session's window. No automatic retry of a *measured-and-failed* arm
(`--retries 0` by default): a failure is recorded and reported, and re-booting a recorded negative
is the defect this whole tree exists to stop. No arm-duration cap: the executor and the watchdog
already bound the failure modes they can see, and a wall clock that kills a slow-but-loading arm
would cost the measurement.