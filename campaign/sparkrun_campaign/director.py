"""The campaign director: owns the plan, hands out leases, and decides what "done" means.

    python -m sparkrun_campaign.director serve --manifest <json> --hosts a,b --root <dir>

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

from . import evidence, fleet, plan, protocol
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
        order, lines = plan.build(self.entries, verdicts, measured, self.repo_root)
        for line in lines:
            print(line, file=self.out)

        recorded = self.campaign.order
        if not recorded:
            for entry in self.entries:
                self.campaign.add(entry["arm"], entry["path"], entry["tp"], entry["env"])
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
            live = self.campaign.beat(str(message.get("lease", "")), self.clock())
            return protocol.ack() if live else protocol.revoked("lease expired or unknown")
        if op == "report":
            return self._report(message)
        return protocol.error(f"unknown op {op!r}")

    def _assign(self, worker: str) -> dict[str, Any] | None:
        now = self.clock()
        self.campaign.expire(now)
        while True:
            choice = plan.next_assignment(
                self.campaign.order,
                self.campaign.arms(),
                self.campaign.free_hosts(now),
                self.campaign.retries,
            )
            if choice is None:
                return None
            arm, hosts = choice
            measured, _, arm_dir = evidence.find_measurement(self.receipts_root, arm)
            if not measured:
                break
            # The arm answered while its worker was gone; booting it again spends a window for
            # numbers that are already on disk.
            self._found_measured(arm, arm_dir, hosts=[], lease_id="", started=None)
        lease = self.campaign.assign(arm, worker or "unknown", list(hosts), now)
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
                    print("plan drained", file=self.out)
                    break
        finally:
            self._stop_workers()
            server.server_close()
            self.socket.unlink(missing_ok=True)
            signal.signal(signal.SIGTERM, previous)
        return self.summary()

    def _found_measured(self, arm: str, arm_dir: str, *, hosts: list[str], lease_id: str,
                        started: float | None) -> None:
        """Record a measurement the receipts already carry; no window is spent on it."""
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
            "watchdog": "",
            "leftovers": [f"{name} on {host}" for host, name in leftovers],
        }
        if mdir:
            try:
                marker = evidence.marker_fields(mdir) or {}
            except evidence.EvidenceError as exc:
                marker = {}
                fields["marker_error"] = str(exc)
            fields["ladder"] = marker.get("ladder", "")
            fields["accuracy_status"] = marker.get("accuracy_status", "")
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


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)
    ap = argparse.ArgumentParser(prog="sparkrun_campaign.director",
                                 description="Own a campaign plan and hand arms to workers.")
    commands = ap.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve", help="run the campaign on the head")
    serve.add_argument("--manifest", required=True, help="campaign manifest (JSON list of arms)")
    serve.add_argument("--hosts", required=True, help="comma-separated hosts the campaign may use")
    serve.add_argument("--root", required=True,
                       help="campaign directory: state, receipts, logs and the socket")
    serve.add_argument("--name", default="", help="campaign id (default: the root's name)")
    serve.add_argument("--max-parallel", type=int, default=0,
                       help="worker slots (default: one per host)")
    serve.add_argument("--retries", type=int, default=0,
                       help="extra attempts for an arm whose receipt says it did not measure")
    serve.add_argument("--receipts-root", default=os.path.expanduser("~/benchmarks"),
                       help="where the per-arm executor writes its tp12-* windows")
    serve.add_argument("--repo-root", default=fleet.default_repo_root(),
                       help="registry checkout: recipe paths and the skip source resolve here")
    serve.add_argument("--run-arm", default=str(Path(fleet.default_repo_root()) / "tools" / "run-arm.sh"),
                       help="per-arm executor (default: tools/run-arm.sh in --repo-root)")
    serve.add_argument("--dry-run", action="store_true",
                       help="read the evidence, print the plan, do not bind or spawn")
    status = commands.add_parser("status",
                                 help="print a campaign's per-arm state without taking the lock")
    status.add_argument("--root", required=True, help="campaign directory holding state.json")
    args = ap.parse_args(argv)

    if args.command == "status":
        return status_campaign(Path(args.root).expanduser())

    hosts = [host.strip() for host in args.hosts.split(",") if host.strip()]
    if not hosts:
        print("no hosts: pass --hosts a,b", file=sys.stderr)
        return 2
    if len(set(hosts)) != len(hosts):
        print(f"cannot start: duplicate hosts in {hosts!r}", file=sys.stderr)
        return 2
    root = Path(args.root).expanduser()
    try:
        entries = plan.load_manifest(args.manifest)
        campaign = Campaign.open(
            root / "state.json",
            campaign=args.name or root.name,
            hosts=hosts,
            max_parallel=args.max_parallel or len(hosts),
            retries=args.retries,
        )
    except (plan.PlanError, StateError) as exc:
        print(f"cannot start: {exc}", file=sys.stderr)
        return 2
    director = Director(
        campaign,
        entries,
        root=root,
        receipts_root=Path(args.receipts_root).expanduser(),
        repo_root=Path(args.repo_root),
        run_arm_sh=Path(args.run_arm),
    )
    try:
        director.validate()
        if args.dry_run:
            director.prepare()
            print("dry run: no socket bound, no worker spawned", file=director.out)
            return director.summary()
        return director.serve()
    except (plan.PlanError, StateError) as exc:
        print(f"cannot start: {exc}", file=sys.stderr)
        return 2
    finally:
        campaign.close()


if __name__ == "__main__":
    sys.exit(main())