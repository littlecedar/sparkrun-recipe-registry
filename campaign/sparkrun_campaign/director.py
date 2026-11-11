"""The campaign director: owns the plan, hands out leases, and decides what "done" means.

    python -m sparkrun_campaign.director serve --manifest <json> --hosts a,b --root <dir>
    python -m sparkrun_campaign.director serve --queue [register] --hosts a,b --root <dir>

One process, one thread of decisions: the socket server accepts one request at a time and the
supervisor loop runs between requests, so no two transitions can interleave. That is the whole
concurrency design, and it is why nothing here locks the state object -- the OS holds a `flock` on
the state file instead, so a second director refuses to start rather than double-booking a node.

Three decisions carry the acceptance checklist:

* **The skip source is read and printed before the first assignment.** `prepare()` runs before the
  socket is bound, so no worker can be told to boot anything first.
* **"Done" is read from receipt fields, never from the worker's return code and never from file
  presence.** A worker's rc=0 with a partial ladder is a failed arm; an rc=6 or a write-off is a
  measured arm if its receipt carries the numbers.
* **A lease nobody is refreshing is reclaimed.** The arm returns to pending only after its hosts
  have been probed and cleared of its containers on *every* host, because a dead worker's arm may
  still be running -- the 2026-11-04 rank-1 survivor is exactly that case.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import socketserver
import subprocess
import sys
import time
import traceback
from pathlib import Path
from collections import Counter
from collections.abc import Callable
from typing import Any

from . import evidence, fleet, guardrails, leases, plan, protocol
from .state import (
    BLOCKED,
    FAILED,
    LEASED,
    MEASURED,
    PENDING,
    SKIPPED,
    Campaign,
    StateError,
    write_json,
)

#: What an idle worker waits before asking again. Short, because the answer changes the moment any
#: arm ends, and a poll is one local round trip.
IDLE_RETRY = 5.0
#: Floor between respawns of one worker slot: a worker that dies instantly must not hot-loop.
RESPAWN_DELAY = 30.0
SOCKET_NAME = "director.sock"
#: Queue mode's re-read interval. A drained plan does not exit there: the register is where new
#: work lands (an authoring row gains a `recipe`), so the loop keeps serving and looks again at a
#: bounded interval instead of busy-looping on rows that are blocked or not bootable yet.
QUEUE_POLL = 30.0


def _last_watchdog_verdict(path: Path) -> str:
    """The last `verdict=` token the boot watchdog wrote, or "" when it never ran."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    verdict = ""
    for line in text.splitlines():
        for token in line.split():
            if token.startswith("verdict="):
                verdict = token.split("=", 1)[1]
    return verdict


class Director:
    """Owns one campaign. `handle()` is the protocol surface; `serve()` is the run loop."""

    def __init__(
        self,
        campaign: Campaign,
        entries: list[dict[str, Any]],
        *,
        root: str | Path,
        receipts_root: str | Path,
        repo_root: str | Path,
        run_arm_sh: str | Path,
        clock: Callable[[], float] = time.time,
        spawn: bool = True,
        out: Any = None,
        fleet_reap: Callable[..., dict[str, list[tuple[str, str]]]] = fleet.reap,
        register: plan.Register | None = None,
        once: bool = False,
        exclude_hosts: tuple[str, ...] = plan.MEMORY_RISKY_EXCLUDED_HOSTS,
        ledger: leases.Ledger | None = None,
        head_proof: Callable[..., list[str]] = guardrails.prove,
        record_hosts: tuple[str, ...] | list[str] | None = None,
        record_risk: str = "",
    ):
        self.campaign = campaign
        self.entries = entries
        self.root = Path(root)
        self.receipts_root = Path(receipts_root)
        self.repo_root = Path(repo_root)
        self.run_arm_sh = Path(run_arm_sh)
        self.clock = clock
        self.spawn = spawn
        self.out = out if out is not None else sys.stdout
        self.fleet_reap = fleet_reap
        #: Queue mode: the register is the plan source and the writer of claims. `None` is
        #: manifest mode, whose behavior is unchanged (one list, no register, drain and exit).
        self.register = register
        self.once = once
        #: Hosts a memory-risky shape may not take; a placement decision of this run, never a role.
        self.exclude_hosts = tuple(exclude_hosts)
        #: The fleet lease ledger: every multi-rank boot is claimed here before a worker can launch,
        #: and another session's claim (or a legacy declared window) is honoured as a held rank.
        self.ledger = ledger if ledger is not None else leases.Ledger(
            self.repo_root / leases.LEDGER, clock=clock)
        self.holder = f"sparkrun-campaign:{campaign.data['campaign']}"
        #: The head's guardrail probe; a waived risky shape cannot be leased without its proof.
        self.head_proof = head_proof
        #: Declared hosts that hold this campaign's record root, and the operator's acceptance of
        #: a shape that takes one. The root is a local directory, so the record host is this host;
        #: a shape cannot avoid it once its ranks outnumber the hosts outside it.
        self.record_hosts = (tuple(record_hosts) if record_hosts is not None else
                             plan.record_hosts(list(campaign.data.get("hosts", []))))
        self.record_risk = record_risk.strip()
        self._held_said: dict[str, str] = {}
        self._last_poll = 0.0
        self._idle_said = False
        self.max_parallel = int(campaign.data.get("max_parallel", 1))
        self.socket = self.root / SOCKET_NAME
        self.workers: dict[int, Any] = {}
        self.spawned: dict[int, float] = {}
        self._stop = False

    def validate(self) -> None:
        """Refuse a deployment that cannot work, before state is touched or a worker spawned."""
        hosts = list(self.campaign.data.get("hosts", []))
        if len(set(hosts)) != len(hosts):
            raise StateError(f"duplicate hosts in {hosts!r}; one host cannot hold two ranks")
        if not self.run_arm_sh.is_file() or not os.access(self.run_arm_sh, os.X_OK):
            raise StateError(f"no executable per-arm executor at {self.run_arm_sh}")
        if self.register is not None and not self.register.tool.is_file():
            raise StateError(f"no register tool at {self.register.tool}")
        if len(str(self.socket)) > 107:
            raise StateError(f"{self.socket} is {len(str(self.socket))} bytes; a unix socket path "
                             "limit is 107")

    # --- start-up ----------------------------------------------------------------------------

    def prepare(self) -> None:
        """Read the two evidence sources, print every exclusion, then reconcile a previous life."""
        verdicts = evidence.skips(self.repo_root)
        problems = evidence.citation_problems(verdicts, self.repo_root)
        for problem in problems:
            print(f"stale-citation: {problem}", file=self.out)
        if problems:
            raise plan.PlanError(
                "the skip source cites a document that no longer resolves; re-point"
                f" metadata.{evidence.REJECT_MARKER} in the recipe before running a campaign"
            )
        measured = evidence.measured(self.receipts_root)
        entries, queue_lines, excluded = self._plan()
        declared = list(self.campaign.data.get("hosts", []))
        gate = plan.record_gate(entries, declared, self.record_hosts, self.record_risk)
        for line in gate:
            print(line, file=self.out)
        if self.record_risk and any(host in declared for host in self.record_hosts):
            # The declaration lands in the state beside the plan it applies to, so the acceptance
            # is auditable rather than a flag a later reader cannot see.
            self.campaign.accept_record_risk(
                [host for host in self.record_hosts if host in declared], self.record_risk)
        order, lines = plan.build(entries, verdicts, measured, self.repo_root)
        for line in queue_lines + lines:
            print(line, file=self.out)
        if self.register is not None and not order:
            print("queue: no runnable rows", file=self.out)

        recorded = self.campaign.order
        if self.register is not None:
            # The register is the plan of record, so a row that appeared since the last life is
            # ingested and a row that stopped being runnable is reconciled below.
            self._adopt(entries)
        elif not recorded:
            self._adopt(entries)
        else:
            added = sorted(set(order) - set(recorded))
            dropped = sorted(set(recorded) - set(order))
            if added or dropped:
                print(f"manifest differs from this campaign's plan; the plan of record wins "
                      f"(new: {added or 'none'}, absent: {dropped or 'none'})", file=self.out)

        for arm in self.campaign.order:
            if arm in verdicts:
                verdict = verdicts[arm]
                self.campaign.record_skip(arm, verdict)
                self._write_receipt(arm, status=SKIPPED, rc=None,
                                    note=f"{verdict['verdict']} ({verdict['doc']})",
                                    mdir="", hosts=[], lease_id="", started=None, leftovers=[])
                self._close_skipped(arm, verdict)

        # A reboot or a killed director leaves both leases and possibly live containers behind.
        # The lease expiry is what makes the arm assignable again; the reap is what makes that safe.
        now = self.clock()
        self.campaign.expire(now)
        for arm in self.campaign.order:
            record = self.campaign.arms()[arm]
            if record["needs_reap"]:
                self._reap_and_clear(arm, list(record["needs_reap"]), "outstanding from a previous run")

        # Anything measured while no director was listening is already answered; a worker that died
        # between the last cell and its report must not cost a second boot.
        for arm in self.campaign.order:
            if self.campaign.arms()[arm]["status"] in (MEASURED, SKIPPED):
                continue
            ok, reason, arm_dir = evidence.find_measurement(self.receipts_root, arm)
            if ok:
                self._found_measured(arm, arm_dir, hosts=[], lease_id="", started=None)
            elif arm_dir:
                print(f"unmeasured: {reason}", file=self.out)

        # The CLI's receipts root is this run's decision, so it lands on every arm that can still
        # run -- an executor writing elsewhere produces numbers the campaign cannot attribute.
        self._pin_receipts_root()
        if self.register is not None:
            self._reconcile(entries, excluded, unblock=True)

    # --- plan source -------------------------------------------------------------------------

    def _plan(self) -> tuple[list[dict[str, Any]], list[str], dict[str, str]]:
        """(entries, exclusion lines, arm -> why it is not runnable) from this campaign's source."""
        if self.register is None:
            return list(self.entries), [], {}
        entries, lines, excluded = plan.queue_entries(
            self.register.rows(), list(self.campaign.data.get("hosts", [])),
            self.register.session, set(self.campaign.arms()), self.exclude_hosts)
        runnable: list[dict[str, Any]] = []
        for entry in entries:
            if (self.repo_root / entry["path"]).is_file():
                runnable.append(entry)
                continue
            # One row naming a deleted recipe is one arm skipped, never a dead tick: a manifest
            # still refuses, but the register is live and every other row must weigh in.
            reason = f"{entry['path']} does not exist under {self.repo_root}"
            lines.append(f"queue-skip: {entry['arm']} ({reason})")
            excluded[entry["arm"]] = reason
        return runnable, lines, excluded

    def _env_for(self, env: dict[str, str] | None) -> dict[str, str]:
        """An arm's executor env: the register row's cells with this run's receipts root on top.

        `--receipts-root` is a campaign-run decision and the evidence readers look under it, so it
        wins over a register cell: an executor writing elsewhere produces numbers nobody can
        attribute to this campaign.
        """
        out = dict(env or {})
        out["ARM_RECEIPTS_ROOT"] = str(self.receipts_root)
        return out

    def _adopt(self, entries: list[dict[str, Any]]) -> None:
        for entry in entries:
            if entry["arm"] not in self.campaign.arms():
                self.campaign.add(entry["arm"], entry["path"], entry["tp"],
                                  self._env_for(entry.get("env")), task=entry.get("task", ""),
                                  memory_risky=bool(entry.get("memory_risky")),
                                  exclude_hosts=entry.get("exclude_hosts") or (),
                                  nodes=int(entry.get("nodes") or entry["tp"]),
                                  pp=int(entry.get("pp") or 1),
                                  allow_hosts=entry.get("allow_hosts") or (),
                                  window=str(entry.get("window") or ""))

    def _pin_receipts_root(self) -> None:
        """Write this invocation's `--receipts-root` into every arm that can still run."""
        for arm in self.campaign.order:
            self.campaign.set_env(arm, "ARM_RECEIPTS_ROOT", str(self.receipts_root))

    def _reconcile(self, entries: list[dict[str, Any]], excluded: dict[str, str],
                   *, unblock: bool = False) -> None:
        """The register's current rows against the arms this campaign already holds.

        Precedence follows who is newer. An arm no lease has started adopts its row's current
        path/tp/env/task (`Campaign.refresh`); an arm that has been leased keeps the record it
        ran with. An arm this campaign holds but the register no longer offers is blocked, not
        booted -- the dangerous case is another session's claim or a row closed elsewhere, which
        the campaign's own state cannot see.

        `unblock` is set on a restart only (a running director does not retry a blocked arm).
        A blocked arm whose row is runnable again becomes pending, but only with no reap
        outstanding: a row flipped back to `queued` says a human opened the external gate, not
        that the hosts are clean. `prepare` proved or failed that reap before this runs.
        """
        runnable = {entry["arm"]: entry for entry in entries}
        for arm in self.campaign.order:
            record = self.campaign.arms()[arm]
            if not record.get("task"):
                continue
            if arm in runnable:
                entry = runnable[arm]
                self.campaign.refresh(arm, path=str(entry["path"]), tp=int(entry["tp"]),
                                      env=self._env_for(entry.get("env")),
                                      task=str(entry.get("task", "")),
                                      memory_risky=bool(entry.get("memory_risky")),
                                      exclude_hosts=entry.get("exclude_hosts") or (),
                                      allow_hosts=entry.get("allow_hosts") or (),
                                      window=str(entry.get("window") or ""))
                if record["status"] != BLOCKED or not unblock:
                    continue
                if record["needs_reap"]:
                    print(f"queue-blocked: {arm} (row runnable again, but hosts still need a "
                          f"verified reap: {','.join(record['needs_reap'])})", file=self.out)
                    continue
                self.campaign.cleared(arm, evidence="register row queued again")
                print(f"queue-unblocked: {arm} (register row queued again)", file=self.out)
                continue
            if record["status"] in (PENDING, FAILED):
                # A retry is a claim like any other: raising --retries must not reach past a
                # register hold, so a failed arm whose row is not runnable is stopped here too.
                reason = excluded.get(arm) or "no longer a runnable row in the register"
                self.campaign.block(arm, f"register: {reason}")
                print(f"queue-blocked: {arm} ({reason})", file=self.out)

    def refresh(self) -> bool:
        """Re-read the register and ingest rows that became runnable. True when the plan grew."""
        if self.register is None:
            return False
        entries, lines, excluded = self._plan()
        fresh = [entry for entry in entries if entry["arm"] not in self.campaign.arms()]
        if not fresh:
            self._reconcile(entries, excluded)
            return False
        for line in lines:
            print(line, file=self.out)
        verdicts = evidence.skips(self.repo_root)
        order, build_lines = plan.build(fresh, verdicts, {}, self.repo_root)
        for line in build_lines:
            print(line, file=self.out)
        self._adopt(fresh)
        for arm in order:
            if arm in verdicts:
                verdict = verdicts[arm]
                self.campaign.record_skip(arm, verdict)
                self._write_receipt(arm, status=SKIPPED, rc=None,
                                    note=f"{verdict['verdict']} ({verdict['doc']})",
                                    mdir="", hosts=[], lease_id="", started=None, leftovers=[])
                self._close_skipped(arm, verdict)
                continue
            measured, reason, arm_dir = evidence.find_measurement(self.receipts_root, arm)
            if measured:
                self._found_measured(arm, arm_dir, hosts=[], lease_id="", started=None)
            elif arm_dir:
                print(f"unmeasured: {reason}", file=self.out)
        self._reconcile(entries, excluded)
        print(f"queue: {len(fresh)} new runnable row(s): "
              f"{', '.join(entry['arm'] for entry in fresh)}", file=self.out)
        return True

    def _wait_for_rows(self) -> None:
        """Queue mode's drained state: look again at a bounded interval, never per tick."""
        now = time.monotonic()
        if now - self._last_poll < QUEUE_POLL:
            return
        self._last_poll = now
        try:
            grew = self.refresh()
        except plan.RegisterError as exc:
            print(f"queue: cannot read the register ({exc}); retrying in {QUEUE_POLL:g}s",
                  file=self.out)
            return
        except plan.PlanError as exc:
            # A plan defect is not an unreadable register: name it as what it is. Per-arm
            # containment in `queue_entries`/`_plan` keeps this to a real tree defect.
            print(f"queue: plan defect this tick ({exc}); retrying in {QUEUE_POLL:g}s",
                  file=self.out)
            return
        if grew:
            self._idle_said = False
        elif not self._idle_said:
            # Once per quiet spell, not once per tick: a blocked row must not fill the journal.
            print(f"queue: no runnable rows; polling every {QUEUE_POLL:g}s for new ones",
                  file=self.out)
            self._idle_said = True

    # --- register claims ---------------------------------------------------------------------

    def _admit(self, arm: str) -> tuple[str | None, bool]:
        """The register row's verdict on an arm about to be claimed: (refusal, our claim is live).

        Assignment re-reads the row instead of trusting the plan it was built from: a peer can
        flip `blocked` or add a `blocked_by` edge while this process is busy, and the 2026-11-08
        leak was exactly one such flip landing after `prepare` had cached a `pending` arm. The
        `state` must be an explicit `queued` (or this campaign's own running claim) and
        `blocked_by` an explicit empty list; a missing mirror is not an edit that opens a hold.
        """
        task = str(self.campaign.arm(arm).get("task") or "")
        if not task:
            return "arm has no register row", False
        try:
            rows = self.register.rows()
        except plan.RegisterError as exc:
            return f"cannot read the register ({exc})", False
        row = next((item for item in rows if str(item.get("id")) == task), None)
        if row is None:
            return "register row no longer exists", False
        state = row.get("state")
        ours = state == "running" and row.get("claimed_by") == self.register.session
        if state != "queued" and not ours:
            claimed = f" claimed by {row.get('claimed_by')}" if state == "running" else ""
            return f"register state {state!r}{claimed}", False
        blocked_by = row.get("blocked_by")
        if blocked_by != []:
            reason = ("register row has no blocked_by list" if not isinstance(blocked_by, list)
                      else f"blocked by {', '.join(str(ref) for ref in blocked_by)}")
            return reason, ours
        siblings = [item for item in rows if item is not row and plan.row_arm(item) == arm]
        hold = plan.sibling_hold(siblings, self.register.session)
        if hold:
            return hold, ours
        return None, ours

    def _refuse(self, arm: str, refusal: str, cached: str, *, release: bool) -> None:
        """A hold the cached plan missed: stop the arm and say which record said what.

        `release` is only for a claim this director wrote that a peer's hold has just overridden
        (it returns the row to `blocked` with the reason); a row another session now owns is left
        alone.
        """
        reason = f"register: {refusal}"
        if release:
            self._settle(arm, BLOCKED, reason, "")
        self.campaign.block(arm, f"{reason} (state.json had {cached})")
        self._write_receipt(arm, status=BLOCKED, rc=None, note=reason, mdir="", hosts=[],
                            lease_id="", started=None, leftovers=[])
        print(f"queue-blocked: {arm} ({refusal}; state.json had {cached}; "
              f"the register wins)", file=self.out)

    def _claim(self, arm: str) -> None:
        """Claim the arm in the register before the boot: a message is not a claim, the row is."""
        if self.register is None:
            return
        task = self.campaign.arm(arm).get("task") or ""
        if not task:
            raise plan.RegisterError(f"{arm} has no register row to claim")
        self.register.update(task, state="running", claimed_by=self.register.session)

    def _settle(self, arm: str, status: str, why: str, mdir: str) -> None:
        """Close or return the arm's row: measured -> done, failed -> queued, else blocked."""
        if self.register is None:
            return
        task = self.campaign.arm(arm).get("task") or ""
        if not task:
            return
        try:
            if status == MEASURED:
                self.register.update(task, state="done",
                                     evidence=mdir or str(self.root / "receipts" / f"{arm}.json"))
                return
            note = self.register.note(task, f"campaign: {why}")
            # A human's `blocked`/`done` written while the arm ran outranks the campaign's wish to
            # retry: requeueing over it is what resurrected the SM121 rows three times on
            # 2026-11-08. The failed attempt is still recorded in the row's notes.
            current = self.register.state(task)
            if current in ("blocked", "done"):
                self.register.update(task, notes=note)
                print(f"register: {arm} keeps its {current} hold; the {status} is recorded",
                      file=self.out)
            elif status == FAILED:
                self.register.update(task, state="queued", notes=note)
            else:
                self.register.update(task, state="blocked", notes=note)
        except plan.RegisterError as exc:
            print(f"register: {arm} not updated ({exc}); its row may still read running",
                  file=self.out)

    def _close_skipped(self, arm: str, verdict: evidence.Verdict) -> None:
        """A recorded negative is an answer, so the row is done and cites the verdict."""
        if self.register is None:
            return
        task = self.campaign.arm(arm).get("task") or ""
        if not task:
            return
        try:
            self.register.update(task, state="done",
                                 evidence=f"{verdict['doc']} ({verdict['verdict']})")
        except plan.RegisterError as exc:
            print(f"register: {arm} skip not recorded ({exc})", file=self.out)

    def summary(self) -> int:
        counts = self.campaign.counts()
        line = ", ".join(f"{count} {status}" for status, count in sorted(counts.items()))
        print(f"campaign {self.campaign.data['campaign']}: {line}", file=self.out)
        for arm in self.campaign.order:
            record = self.campaign.arms()[arm]
            if record["status"] in (FAILED, BLOCKED):
                print(f"  {record['status']}: {arm} -- {record['last'].get('reason', '')}",
                      file=self.out)
        return 0

    # --- protocol ----------------------------------------------------------------------------

    def handle(self, message: dict[str, Any]) -> dict[str, Any]:
        op = message.get("op")
        if op == "poll":
            lease = self._assign(str(message.get("worker", "")))
            return protocol.assign(lease) if lease else protocol.idle(IDLE_RETRY)
        if op == "beat":
            lease_id = str(message.get("lease", ""))
            live = self.campaign.beat(lease_id, self.clock())
            if live:
                found = self.campaign.lease_for(lease_id)
                if found is not None:
                    self.ledger.renew(str(found[1].get("ledger") or ""), self.clock())
            return protocol.ack() if live else protocol.revoked("lease expired or unknown")
        if op == "report":
            return self._report(message)
        return protocol.error(f"unknown op {op!r}")

    def _assign(self, worker: str) -> dict[str, Any] | None:
        now = self.clock()
        self.campaign.expire(now)
        declared = list(self.campaign.data.get("hosts", []))
        # Another session's lease, or a declared window, is a held rank: the campaign does not
        # choose it, and it is named so "no runnable row" is checkable rather than silent.
        held = self.ledger.held_hosts(declared, now, holder=self.holder)
        if held != self._held_said:
            for host in sorted(held):
                print(f"lease-held: {host} ({held[host]})", file=self.out)
            for host in sorted(set(self._held_said) - set(held)):
                print(f"lease-free: {host}", file=self.out)
            self._held_said = held
        free = [host for host in self.campaign.free_hosts(now) if host not in held]
        if not self.record_risk:
            # The record root lives on this host; an arm that only fits by taking it waits, and
            # the plan already refused the shapes that could never avoid it.
            free = [host for host in free if host not in self.record_hosts]
        while True:
            choice = plan.next_assignment(
                self.campaign.order,
                self.campaign.arms(),
                free,
                self.campaign.retries,
                self.exclude_hosts,
            )
            if choice is None:
                return None
            arm, hosts = choice
            measured, _, arm_dir = evidence.find_measurement(self.receipts_root, arm)
            if measured:
                # The arm answered while its worker was gone; booting it again spends a window for
                # numbers that are already on disk.
                self._found_measured(arm, arm_dir, hosts=[], lease_id="", started=None)
                continue
            if self.register is None:
                break
            cached = self.campaign.arm(arm)["status"]
            refusal, _ = self._admit(arm)
            if refusal is None:
                break
            # The register is newer than the plan cached at prepare (a peer's hold can land while
            # this process is busy), and "never assign a held row" outranks a pending record.
            self._refuse(arm, refusal, cached, release=False)

        # The head's lease gate: the only way a memory-risky shape may take an excluded host is
        # its own declaration, and the guardrails are proven before any claim or lease record, so a
        # refusal can never be a boot. A failed proof blocks the arm -- retrying elsewhere would be
        # the silent placement the owner ruling forbids.
        proof: list[str] = []
        waived = tuple(self.campaign.arm(arm).get("allow_hosts") or ())
        window = str(self.campaign.arm(arm).get("window") or "")
        for host in [item for item in hosts
                     if plan.barred(item, self.exclude_hosts) and plan.barred(item, waived)]:
            try:
                lines = self.head_proof(host, window=window)
            except plan.PlanError as exc:
                reason = f"lease refused: {exc}"
                self.campaign.block(arm, reason)
                self._write_receipt(arm, status=BLOCKED, rc=None, note=reason, mdir="", hosts=[],
                                    lease_id="", started=None, leftovers=[])
                print(f"{arm}: BLOCKED, {reason}", file=self.out)
                return None
            proof.extend(lines)
            for line in lines:
                print(f"lease-proof: {host} {line}", file=self.out)

        # One writer for every multi-rank claim: the record names every rank before a worker can
        # launch, so a peer's lease is either honoured above or the arm is not attempted.
        ledger_id = ""
        if len(hosts) > 1:
            try:
                claim = self.ledger.acquire(
                    self.holder, list(hosts), ttl=self.campaign.lease_ttl, arm=arm,
                    window=str(self.campaign.arm(arm).get("window") or ""), proof=proof)
                ledger_id = str(claim["id"])
            except leases.LeaseError as exc:
                print(f"lease-refused: {arm} on {','.join(hosts)} ({exc}); not attempted",
                      file=self.out)
                return None
        try:
            # Before the lease exists, so no worker can launch an arm this campaign has not claimed.
            self._claim(arm)
        except plan.RegisterError as exc:
            self.ledger.release(ledger_id)
            reason = f"register claim refused: {exc}"
            self.campaign.block(arm, reason)
            self._write_receipt(arm, status=BLOCKED, rc=None, note=reason, mdir="", hosts=[],
                                lease_id="", started=None, leftovers=[])
            print(f"{arm}: BLOCKED, {reason}", file=self.out)
            return None
        if self.register is not None:
            cached = self.campaign.arm(arm)["status"]
            refusal, ours = self._admit(arm)
            if refusal is not None:
                # A hold that landed between the read above and this claim wins: the arm has not
                # been leased, so no boot has happened. Release only a claim this director wrote.
                self.ledger.release(ledger_id)
                self._refuse(arm, refusal, cached, release=ours)
                return None
        try:
            lease = self.campaign.assign(arm, worker or "unknown", list(hosts), now,
                                         ledger=ledger_id)
        except StateError:
            self.ledger.release(ledger_id)
            raise
        print(f"assign: {arm} -> {lease['worker']} on {','.join(hosts)} (lease {lease['id']})",
              file=self.out)
        return lease

    def _report(self, message: dict[str, Any]) -> dict[str, Any]:
        now = self.clock()
        lease_id = str(message.get("lease", ""))
        rc = int(message.get("rc", -1))
        note = str(message.get("note", ""))
        self.campaign.expire(now)
        found = self.campaign.lease_for(lease_id)
        if found is None:
            print(f"late report for {lease_id}: lease already reclaimed, ignored", file=self.out)
            return protocol.ack(late=True)
        arm, lease = found
        record = self.campaign.arm(arm)
        measured, reason, arm_dir = evidence.find_measurement(self.receipts_root, arm)

        try:
            result = self.fleet_reap(list(lease["hosts"]), record["path"])
            leftovers = result["after"]
        except OSError as exc:
            note = f"{note}; cannot verify leftovers: {exc}".strip("; ")
            self.campaign.block(arm, f"cannot verify leftovers on {lease['hosts']}: {exc}",
                                list(lease["hosts"]), rc=rc, measured=measured,
                                measurement_dir=arm_dir)
            self._write_receipt(arm, status=BLOCKED, rc=rc, note=note, mdir=arm_dir,
                                hosts=lease["hosts"], lease_id=lease_id,
                                started=lease["issued_at"], leftovers=[])
            print(f"{arm}: BLOCKED, leftover state unverifiable on {lease['hosts']}", file=self.out)
            self._settle(arm, BLOCKED, f"cannot verify leftovers on {lease['hosts']}: {exc}",
                         arm_dir)
            self.ledger.release(str(lease.get("ledger") or ""))
            return protocol.ack(status=BLOCKED)

        if leftovers:
            status = BLOCKED
            self.campaign.block(arm, f"container left behind: {fleet.describe(leftovers)}",
                                list(lease["hosts"]), rc=rc, measured=measured,
                                measurement_dir=arm_dir)
        else:
            status = MEASURED if measured else FAILED
            self.campaign.finish(arm, status=status, rc=rc, reason=reason or note,
                                 measurement_dir=arm_dir, measured=measured)
        self._write_receipt(arm, status=status, rc=rc, note=reason or note, mdir=arm_dir,
                            hosts=lease["hosts"], lease_id=lease_id, started=lease["issued_at"],
                            leftovers=leftovers)
        self._settle(arm, status, reason or note, arm_dir)
        self.ledger.release(str(lease.get("ledger") or ""))
        print(f"{arm}: rc={rc} -> {status}" + (f" ({reason})" if reason else ""), file=self.out)
        return protocol.ack(status=status)

    # --- supervisor --------------------------------------------------------------------------

    def supervise(self) -> None:
        self.campaign.expire(self.clock())
        for arm in self.campaign.order:
            record = self.campaign.arms()[arm]
            # A blocked arm is not retried by the running director: an unverifiable host is a
            # human's call, and hammering ssh every second is not evidence. A restart retries.
            if record["needs_reap"] and record["status"] != BLOCKED:
                self._reap_and_clear(arm, list(record["needs_reap"]), "lease expired")
        self._workers()

    def _reap_and_clear(self, arm: str, hosts: list[str], reason: str) -> None:
        path = self.campaign.arm(arm)["path"]
        try:
            result = self.fleet_reap(hosts, path)
        except (OSError, RuntimeError) as exc:
            self.campaign.block(arm, f"cannot reap {hosts}: {exc}", hosts)
            print(f"{arm}: cannot reap {hosts} ({exc}); arm blocked", file=self.out)
            return
        if result["after"]:
            self.campaign.block(arm, f"container left behind: {fleet.describe(result['after'])}", hosts)
            print(f"{arm}: {fleet.describe(result['after'])} survived the reap; arm blocked",
                  file=self.out)
            return
        self.campaign.cleared(arm)
        print(f"reaped {arm} on {','.join(hosts)} ({reason}; "
              f"{len(result['found'])} container(s) found)", file=self.out)

    def _workers(self) -> None:
        if not self.spawn:
            return
        now = self.clock()
        for index in range(self.max_parallel):
            process = self.workers.get(index)
            if process is not None and process.poll() is None:
                continue
            if process is not None:
                print(f"worker w{index + 1} exited rc={process.returncode}", file=self.out)
                del self.workers[index]  # one line per death, not one per tick
            if now - self.spawned.get(index, 0.0) < RESPAWN_DELAY:
                continue
            command = [
                sys.executable, "-B", "-m", "sparkrun_campaign.worker",
                "--socket", str(self.socket),
                "--worker", f"w{index + 1}",
                "--run-arm", str(self.run_arm_sh),
                "--log-dir", str(self.root / "logs"),
            ]
            # One session per worker slot, so stopping the campaign can signal the whole slot:
            # the worker, `run-arm.sh` and the boot watchdog all receive SIGTERM together, which is
            # what makes `run-arm.sh`'s EXIT trap stop the serve instead of orphaning it.
            self.workers[index] = subprocess.Popen(
                command, cwd=str(Path(__file__).resolve().parents[1]), start_new_session=True
            )
            self.spawned[index] = now
            print(f"worker w{index + 1} started (pid {self.workers[index].pid})", file=self.out)

    def _stop_workers(self) -> None:
        for index, process in self.workers.items():
            if process.poll() is not None:
                continue
            print(f"stopping worker w{index + 1} (pid {process.pid})", file=self.out)
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            except (OSError, ProcessLookupError):
                continue
        # The unit's TimeoutStopSec=180 leaves the executor's trap time to run `sparkrun stop`.
        deadline = time.monotonic() + 100.0
        for process in self.workers.values():
            remaining = max(0.0, deadline - time.monotonic())
            try:
                process.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                except (OSError, ProcessLookupError):
                    pass

    def drained(self) -> bool:
        for arm in self.campaign.order:
            record = self.campaign.arms()[arm]
            status = record["status"]
            if status in (PENDING, LEASED):
                return False
            if status == FAILED and record["failures"] <= self.campaign.retries:
                return False
            if status == BLOCKED and record["needs_reap"]:
                # Blocked is terminal for this run; the outstanding reap is reported, not retried.
                continue
        return True

    # --- run loop ----------------------------------------------------------------------------

    def _bind(self) -> _Server:
        self.root.mkdir(parents=True, exist_ok=True)
        if self.socket.exists():
            try:
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as probe:
                    probe.settimeout(1.0)
                    probe.connect(str(self.socket))
            except OSError:
                self.socket.unlink()  # stale file from a killed director; the flock said we own it
            else:
                raise StateError(f"{self.socket} is already being served")
        server = _Server(str(self.socket), _Handler)
        server.director = self
        server.timeout = 1.0
        return server

    def _on_signal(self, signum: int, _frame: Any) -> None:
        print(f"signal {signum}: stopping after this tick (workers get SIGTERM, arms are stopped"
              " by run-arm.sh's own trap)", file=self.out)
        self._stop = True

    def serve(self) -> int:
        self.prepare()
        server = self._bind()
        print(f"serving {self.socket} with {self.max_parallel} worker slot(s); plan: "
              f"{', '.join(self.campaign.order) or 'empty'}", file=self.out)
        previous = signal.signal(signal.SIGTERM, self._on_signal)
        signal.signal(signal.SIGINT, self._on_signal)
        try:
            while not self._stop:
                server.handle_request()
                self.supervise()
                if self.drained():
                    if self.register is None or self.once:
                        print("plan drained", file=self.out)
                        break
                    self._wait_for_rows()
        finally:
            self._stop_workers()
            server.server_close()
            self.socket.unlink(missing_ok=True)
            signal.signal(signal.SIGTERM, previous)
        return self.summary()

    def _found_measured(self, arm: str, arm_dir: str, *, hosts: list[str], lease_id: str,
                        started: float | None) -> None:
        """Record a measurement the receipts already carry; no window is spent on it."""
        self._settle(arm, MEASURED, "measured in receipts before any boot", arm_dir)
        self.campaign.mark_measured(arm, arm_dir, "measured in receipts before any boot")
        self._write_receipt(arm, status=MEASURED, rc=None,
                            note="measured on disk; no worker report", mdir=arm_dir, hosts=hosts,
                            lease_id=lease_id, started=started, leftovers=[])
        print(f"measured: {arm} ({arm_dir}); not booted", file=self.out)

    # --- receipts ----------------------------------------------------------------------------

    def _write_receipt(
        self,
        arm: str,
        *,
        status: str,
        rc: int | None,
        note: str,
        mdir: str,
        hosts: list[str],
        lease_id: str,
        started: float | None,
        leftovers: list[tuple[str, str]],
    ) -> None:
        """One JSON per arm, beside the campaign's own state -- item 8 of the checklist."""
        record = self.campaign.arm(arm)
        fields: dict[str, Any] = {
            "campaign": self.campaign.data["campaign"],
            "task": record.get("task", ""),
            "arm": arm,
            "path": record["path"],
            "tp": record["tp"],
            "hosts": list(hosts),
            "lease": lease_id,
            "attempt": record["attempts"],
            "started_at": started,
            "ended_at": self.clock(),
            "rc": rc,
            "status": status,
            "reason": note,
            "measurement_dir": mdir,
            "measured": bool(mdir) and evidence.done(mdir)[0],
            "artefacts": [],
            "serve_logs": [],
            "ladder": "",
            "accuracy_status": "",
            # The metrics scrape, read from its own artifacts (`metrics-status.txt` and the
            # per-host bodies) beside the marker, never through it: a sidecar-shaped house.yaml
            # discards flat keys. `None` is an absent artifact and is stated as such -- it is not
            # `absent`, which is the engine exposing nothing.
            "metrics_status": {},
            # Which house.yaml shape the outcome fields came from (`run-arm` or
            # `sparkrun_benchmark`, empty when there is no marker). The nested sidecar has no
            # ladder field of its own, so the field is read from the artefact instead (below):
            # a receipt never carries a blank ladder beside `measured: true`.
            # The earlyoom reader, from its own artifact for the same reason: `earlyoom-terminated`
            # says a SIGTERM (exit 143) killed the serve, and `unknown` says nobody could tell --
            # never a default to `clean`, which is how a kill gets blamed on the engine.
            "oom_watchdog": {},
            "marker_shape": "",
            "house_score": "",
            "client": {},
            "watchdog": "",
            "leftovers": [f"{name} on {host}" for host, name in leftovers],
        }
        if mdir:
            try:
                marker = evidence.marker_fields(mdir) or {}
                ladder = evidence.ladder_status(mdir)
            except evidence.EvidenceError as exc:
                marker = {}
                ladder = f"unreadable marker — {exc}"
                fields["marker_error"] = str(exc)
            fields["ladder"] = ladder
            fields["accuracy_status"] = marker.get("accuracy_status", "")
            fields["metrics_status"] = evidence.metrics_status(mdir) or {
                "status": "", "reason": "no artifact"}
            fields["oom_watchdog"] = evidence.oom_watchdog(mdir) or {
                "state": "", "reason": "no artifact"}
            fields["marker_shape"] = marker.get("shape", "")
            fields["house_score"] = marker.get("house_score", "")
            try:
                client = evidence.client_receipt(mdir)
            except evidence.EvidenceError as exc:
                client = None
                fields["client_error"] = str(exc)
            fields["client"] = client or {}
            fields["artefacts"] = [
                name for name in evidence.MEASURED_ARTEFACTS + ("ladder.yaml",)
                if (Path(mdir) / name).exists()
            ]
            fields["serve_logs"] = sorted(
                path.name for path in Path(mdir).glob("serve-*.log")
            ) + sorted(path.name for path in Path(mdir).glob("docker-*.log"))
            fields["watchdog"] = _last_watchdog_verdict(Path(mdir) / "watchdog.log")
        write_json(self.root / "receipts" / f"{arm}.json", fields)


class _Server(socketserver.UnixStreamServer):
    director: Director | None = None


class _Handler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        # `socketserver` types its base server as BaseServer, which has no director slot.
        director = getattr(self.server, "director", None)
        if director is None:
            raise protocol.ProtocolError("this server was built without a director")
        try:
            reply = director.handle(protocol.read_message(self.rfile))
        except protocol.ProtocolError as exc:
            reply = protocol.error(str(exc))
        except (StateError, evidence.EvidenceError, plan.PlanError) as exc:
            reply = protocol.error(f"{exc.__class__.__name__}: {exc}")
        except Exception as exc:  # noqa: BLE001 - a service survives one bad message, visibly
            traceback.print_exc(file=director.out)
            reply = protocol.error(f"{exc.__class__.__name__}: {exc}")
        self.wfile.write(protocol.encode(reply))
        self.wfile.flush()


def status_campaign(root: Path) -> int:
    """Read state.json without the director's flock: an operator may look while a run owns it."""
    path = Path(root) / "state.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        order = list(data["order"])
        arms = data["arms"]
        name = data["campaign"]
        counts = Counter(arms[arm]["status"] for arm in order)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"cannot read {path}: {exc}", file=sys.stderr)
        return 2
    summary = ", ".join(f"{counts[status]} {status}" for status in
                        (PENDING, LEASED, MEASURED, FAILED, SKIPPED, BLOCKED) if counts[status])
    print(f"campaign {name}: {summary or 'no arms'}")
    for arm in order:
        record = arms[arm]
        reason = (record.get("last") or {}).get("reason", "")
        print(f"  {record['status']:<9}{arm}" + (f"  -- {reason}" if reason else ""))
    return 0


def _excluded(args: argparse.Namespace) -> tuple[str, ...]:
    """The run's excluded-host set: `--exclude-host`, else `$CAMPAIGN_EXCLUDE_HOSTS`, else default.

    A hostname-declared set names the head in the untracked EnvironmentFile, because a tracked
    default may not carry its hostname.
    """
    flag = args.exclude_host
    if flag is None:
        from_env = os.environ.get("CAMPAIGN_EXCLUDE_HOSTS", "")
        flag = [from_env] if from_env.strip() else None
    return (plan.MEMORY_RISKY_EXCLUDED_HOSTS if flag is None else
            tuple(host.strip() for value in flag
                  for host in value.split(",") if host.strip()))


def plan_command(args: argparse.Namespace) -> int:
    """Plan-only: skip source, receipt predicate, placement and head proof for a manifest.

    Writes nothing at all -- no `state.json`, no ledger record, no lease -- which is what makes it
    safe against a live tree and live hosts. It prints the arm, the host order placement chose and
    the proof lines for any waived rank; a refusal exits 3, because that is what `serve` would
    refuse (the arm would be blocked, not placed elsewhere).
    """
    hosts = [host.strip() for host in args.hosts.split(",") if host.strip()]
    if not hosts or len(set(hosts)) != len(hosts):
        print(f"cannot plan: bad --hosts {hosts!r}", file=sys.stderr)
        return 2
    repo_root = Path(args.repo_root)
    excluded = _excluded(args)
    entries = plan.load_manifest(args.manifest)
    verdicts = evidence.skips(repo_root)
    problems = evidence.citation_problems(verdicts, repo_root)
    for problem in problems:
        print(f"stale-citation: {problem}")
    if problems:
        print("cannot plan: the skip source cites a document that no longer resolves",
              file=sys.stderr)
        return 2
    measured = evidence.measured(Path(args.receipts_root).expanduser())
    record_risk = str(getattr(args, "accept_record_risk", "") or "").strip()
    record = plan.record_hosts(hosts)
    for line in plan.record_gate(entries, hosts, record, record_risk):
        print(line)
    free = [host for host in hosts if record_risk or host not in record]
    order, lines = plan.build(entries, verdicts, measured, repo_root)
    for line in lines:
        print(line)
    arms: dict[str, dict[str, Any]] = {}
    for entry in entries:
        arm = entry["arm"]
        arms[arm] = {
            "tp": int(entry["tp"]),
            "pp": int(entry.get("pp") or 1),
            "nodes": int(entry.get("nodes") or entry["tp"]),
            "status": (SKIPPED if arm in verdicts else MEASURED if arm in measured else PENDING),
            "failures": 0,
            "needs_reap": [],
            "memory_risky": bool(entry.get("memory_risky")),
            "exclude_hosts": list(entry.get("exclude_hosts") or ()),
            "allow_hosts": list(entry.get("allow_hosts") or ()),
            "window": str(entry.get("window") or ""),
        }
    choice = plan.next_assignment(order, arms, free, 0, excluded)
    if choice is None:
        print("plan: no pending arm fits the declared hosts")
        return 3
    arm, chosen = choice
    record = arms[arm]
    print(f"plan: {arm} -> {','.join(chosen)} (tp={record['tp']} pp={record['pp']} "
          f"ranks={record['nodes']} window={record['window'] or '-'})")
    barred = [host for host in chosen if plan.barred(host, excluded)]
    for host in barred:
        try:
            proof = guardrails.prove(host, window=record["window"])
        except plan.PlanError as exc:
            print(f"lease-refused: {host} ({exc})")
            print("plan: no state, lease or ledger written")
            return 3
        for line in proof:
            print(f"lease-proof: {host} {line}")
    print(f"plan: excluded host(s) used: {','.join(barred) or 'none'}")
    print("plan: no state, lease or ledger written")
    return 0


def lease_command(args: argparse.Namespace) -> int:
    """The manual session's entry point: write, list or release a fleet lease.

    Same ledger and same record as the director uses, so one mechanism claims a multi-rank boot.
    A `--ttl` is required to write: the claim expires on its own, which is what lets a lost session
    stop holding the fleet.
    """
    ledger = leases.Ledger(Path(args.repo_root).expanduser() / leases.LEDGER)
    try:
        if args.release:
            released = ledger.release(args.release)
            print(("released " if released else "no such live lease: ") + args.release)
            return 0 if released else 3
        if args.list or not args.hosts:
            live = ledger.leases()
            for record in live:
                print(f"{record.get('id')} {record.get('holder')} on "
                      f"{','.join(record.get('hosts') or ())} until "
                      f"{float(record.get('expires_at') or 0):.0f}"
                      + (f" ({record['window']})" if record.get("window") else ""))
            print(f"{len(live)} live lease(s) in {ledger.path}")
            return 0
        if not args.holder or args.ttl is None:
            print("cannot lease: --holder and --ttl are required to write a lease", file=sys.stderr)
            return 2
        hosts = [host.strip() for host in args.hosts.split(",") if host.strip()]
        record = ledger.acquire(args.holder, hosts, ttl=args.ttl, arm=args.arm,
                                window=args.window)
        print(f"leased {record['id']} to {record['holder']} on {','.join(record['hosts'])}"
              f" until {record['expires_at']:.0f}")
        return 0
    except leases.LeaseError as exc:
        print(f"cannot lease: {exc}", file=sys.stderr)
        return 3


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)
    ap = argparse.ArgumentParser(prog="sparkrun_campaign.director",
                                 description="Own a campaign plan and hand arms to workers.")
    commands = ap.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve", help="run the campaign on the head")
    source = serve.add_mutually_exclusive_group(required=True)
    source.add_argument("--manifest", help="campaign manifest (JSON list of arms)")
    source.add_argument("--queue", nargs="?", const=plan.DEFAULT_QUEUE, metavar="PATH",
                        help="the register as the plan source: queued rows that name a recipe and "
                             f"tp (default {plan.DEFAULT_QUEUE} under --repo-root)")
    serve.add_argument("--once", action="store_true",
                       help="queue mode: run the rows runnable now, then exit instead of polling")
    serve.add_argument("--hosts", required=True, help="comma-separated hosts the campaign may use")
    serve.add_argument("--exclude-host", action="append", metavar="HOST",
                       help="host a memory-risky shape may not take (repeatable, comma-separated; "
                            "default: $CAMPAIGN_EXCLUDE_HOSTS, else "
                            f"{','.join(plan.MEMORY_RISKY_EXCLUDED_HOSTS)}; pass an empty value to "
                            "disable). A hostname-declared set names the head here, because a "
                            "tracked default may not carry its name")
    serve.add_argument("--root", required=True,
                       help="campaign directory: state, receipts, logs and the socket")
    serve.add_argument("--name", default="", help="campaign id (default: the root's name)")
    serve.add_argument("--max-parallel", type=int, default=0,
                       help="worker slots (default: one per host)")
    serve.add_argument("--retries", type=int, default=None,
                       help="extra attempts for an arm whose receipt says it did not measure "
                            "(default: the number the campaign stored; 0 when it is new)")
    serve.add_argument("--receipts-root", default=os.path.expanduser("~/benchmarks"),
                       help="where the per-arm executor writes its tp12-* windows")
    serve.add_argument("--repo-root", default=fleet.default_repo_root(),
                       help="registry checkout: recipe paths and the skip source resolve here")
    serve.add_argument("--run-arm", default=str(Path(fleet.default_repo_root()) / "tools" / "run-arm.sh"),
                       help="per-arm executor (default: tools/run-arm.sh in --repo-root)")
    serve.add_argument("--dry-run", action="store_true",
                       help="read evidence, print the plan, do not bind or spawn")
    serve.add_argument("--accept-record-risk", default="", metavar="REASON",
                       help="declare, in your own words, that a rank may hold the campaign "
                            "record root (state.json, its lock, the socket and the lease record); "
                            "recorded in the journal and state.json")
    status = commands.add_parser("status",
                                 help="print a campaign's per-arm state without taking the lock")
    status.add_argument("--root", required=True, help="campaign directory holding state.json")
    planp = commands.add_parser(
        "plan", help="plan-only: placement and head proof for a manifest; writes nothing")
    planp.add_argument("--manifest", required=True, help="campaign manifest (JSON list of arms)")
    planp.add_argument("--hosts", required=True, help="comma-separated hosts the campaign may use")
    planp.add_argument("--exclude-host", action="append", metavar="HOST",
                       help="host a memory-risky shape may not take (repeatable, comma-separated; "
                            "default: $CAMPAIGN_EXCLUDE_HOSTS, else "
                            f"{','.join(plan.MEMORY_RISKY_EXCLUDED_HOSTS)})")
    planp.add_argument("--repo-root", default=fleet.default_repo_root(),
                       help="registry checkout: recipe paths and the skip source resolve here")
    planp.add_argument("--receipts-root", default=os.path.expanduser("~/benchmarks"),
                       help="where per-arm executor writes its tp12-* windows")
    planp.add_argument("--accept-record-risk", default="", metavar="REASON",
                       help="declare, in your own words, that a rank may hold the campaign "
                            "record root; printed as the acceptance, nothing written")
    claim = commands.add_parser(
        "lease", help="write, list or release a fleet lease (a manual session's claim)")
    claim.add_argument("--hosts", help="comma-separated ranks this lease claims")
    claim.add_argument("--holder", default="", help="session name that holds the lease")
    claim.add_argument("--ttl", type=float, help="seconds until the lease expires (required)")
    claim.add_argument("--arm", default="", help="arm the ranks are booting, for the record")
    claim.add_argument("--window", default="", help="declared window name, per boot")
    claim.add_argument("--release", default="", metavar="ID", help="drop this lease id")
    claim.add_argument("--list", action="store_true", help="print every live lease")
    claim.add_argument("--repo-root", default=fleet.default_repo_root(),
                       help="registry checkout holding .local/fleet-leases.json")
    args = ap.parse_args(argv)

    if args.command == "status":
        return status_campaign(Path(args.root).expanduser())
    if args.command == "plan":
        try:
            return plan_command(args)
        except (plan.PlanError, StateError) as exc:
            print(f"cannot plan: {exc}", file=sys.stderr)
            return 2
    if args.command == "lease":
        return lease_command(args)

    hosts = [host.strip() for host in args.hosts.split(",") if host.strip()]
    if not hosts:
        print("no hosts: pass --hosts a,b", file=sys.stderr)
        return 2
    if len(set(hosts)) != len(hosts):
        print(f"cannot start: duplicate hosts in {hosts!r}", file=sys.stderr)
        return 2
    excluded = _excluded(args)
    if args.once and args.queue is None:
        print("cannot start: --once is a queue-mode flag; a manifest campaign drains and exits",
              file=sys.stderr)
        return 2
    root = Path(args.root).expanduser()
    repo_root = Path(args.repo_root)
    try:
        entries = plan.load_manifest(args.manifest) if args.manifest else []
        campaign = Campaign.open(
            root / "state.json",
            campaign=args.name or root.name,
            hosts=hosts,
            max_parallel=args.max_parallel or len(hosts),
            retries=args.retries,
        )
        register = None
        if args.queue is not None:
            queue_path = Path(args.queue)
            if not queue_path.is_absolute():
                queue_path = repo_root / queue_path
            # The session id is stable across restarts, which is what lets a claim be recognised
            # as this campaign's own on the next life.
            register = plan.Register(repo_root / "tools" / "task-queue.py", queue_path,
                                     f"sparkrun-campaign:{campaign.data['campaign']}")
    except (plan.PlanError, StateError) as exc:
        print(f"cannot start: {exc}", file=sys.stderr)
        return 2
    director = Director(
        campaign,
        entries,
        root=root,
        receipts_root=Path(args.receipts_root).expanduser(),
        repo_root=repo_root,
        run_arm_sh=Path(args.run_arm),
        register=register,
        once=args.once,
        exclude_hosts=excluded,
        record_risk=args.accept_record_risk,
    )
    try:
        director.validate()
        if args.dry_run:
            director.prepare()
            print("dry run: no socket bound, no worker spawned", file=director.out)
            return director.summary()
        return director.serve()
    except (plan.PlanError, plan.RegisterError, StateError) as exc:
        print(f"cannot start: {exc}", file=sys.stderr)
        return 2
    finally:
        campaign.close()


if __name__ == "__main__":
    sys.exit(main())