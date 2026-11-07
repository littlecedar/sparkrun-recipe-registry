"""Campaign worker: one subprocess per slot; poll the director, run one arm, report the outcome.

The arm runs through `tools/run-arm.sh` unchanged. Everything the checklist needs on hardware --
the readiness loop that also polls the watchdog, the boot watchdog itself, serve-log harvest, the
all-rank teardown and the rc=6 leftover gate -- is already implemented and measured there. A second
implementation in Python would be an unmeasured copy, so the worker's whole job is the two things
`run-arm.sh` cannot do: hold a lease, and report to a director that decides from the receipts what
"done" means.

The worker is one session with its child (`run-arm.sh` inherits this process group), so the
director's SIGTERM to the slot reaches the arm executor too and its EXIT trap stops the serve.
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

from . import fleet, protocol


class Beats(threading.Thread):
    """Refresh the lease while the arm runs, and learn early when it is revoked."""

    def __init__(self, socket_path: str, lease_id: str, period: float):
        super().__init__(daemon=True)
        self.socket_path = socket_path
        self.lease_id = lease_id
        self.period = period
        self.stop = threading.Event()
        self.revoked = ""

    def run(self) -> None:
        while not self.stop.wait(self.period):
            try:
                reply = protocol.request(self.socket_path, protocol.beat(self.lease_id),
                                         timeout=10.0)
            except (OSError, protocol.ProtocolError):
                continue  # a missed beat is not a lost lease; keep the arm running
            if reply.get("op") == "revoked":
                self.revoked = str(reply.get("reason", ""))
                return


def run_arm(lease: dict[str, Any], executor: Path, log_dir: Path) -> tuple[int, str]:
    """Run the per-arm executor; its stdout/stderr land in one log per attempt."""
    log_path = log_dir / f"{lease['id']}.log"
    environment = dict(os.environ)
    environment.update({str(key): str(value) for key, value in (lease.get("env") or {}).items()})
    command = [str(executor), lease["path"], ",".join(lease["hosts"])]
    with open(log_path, "w", encoding="utf-8") as handle:
        handle.write(f"$ {' '.join(command)}\n")
        handle.flush()
        # No `start_new_session`: the arm stays in this worker's process group so one SIGTERM from
        # the director stops the executor and lets its own trap stop the serve.
        result = subprocess.run(command, stdout=handle, stderr=subprocess.STDOUT,
                                env=environment, check=False)
    return result.returncode, str(log_path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="sparkrun_campaign.worker",
                                 description="Poll a campaign director and run the arms it hands out.")
    ap.add_argument("--socket", required=True, help="the director's socket")
    ap.add_argument("--worker", required=True, help="this slot's name")
    ap.add_argument("--run-arm", default=fleet.default_repo_root() + "/tools/run-arm.sh",
                    help="per-arm executor (default: tools/run-arm.sh)")
    ap.add_argument("--log-dir", required=True, help="where each attempt's executor log lands")
    ap.add_argument("--beat", type=float, default=20.0, help="lease heartbeat period, seconds")
    ap.add_argument("--poll-timeout", type=float, default=300.0,
                    help="how long one poll may wait on a director busy reaping")
    ap.add_argument("--max-misses", type=int, default=12,
                    help="consecutive unreachable polls before this slot stops itself")
    args = ap.parse_args(argv)

    executor = Path(args.run_arm)
    if not executor.is_file():
        print(f"worker {args.worker}: no executor at {executor}", file=sys.stderr)
        return 2
    log_dir = Path(args.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    misses = 0
    while True:
        try:
            reply = protocol.request(args.socket, protocol.poll(args.worker),
                                     timeout=args.poll_timeout)
        except (OSError, protocol.ProtocolError) as exc:
            misses += 1
            # A crashed director must not leave a fleet of workers polling a dead socket, and an
            # orphaned arm is a double boot waiting to happen (the restart's reconcile is one
            # probe behind). Signalling our own group takes the executor down with us.
            if misses >= args.max_misses:
                print(f"worker {args.worker}: no director after {misses} polls ({exc});"
                      " stopping this slot", file=sys.stderr, flush=True)
                os.killpg(os.getpgrp(), signal.SIGTERM)
                return 3
            print(f"worker {args.worker}: director unreachable ({exc}); retrying", file=sys.stderr,
                  flush=True)
            time.sleep(5.0)
            continue
        misses = 0

        op = reply.get("op")
        if op == "shutdown":
            print(f"worker {args.worker}: shutdown", flush=True)
            return 0
        if op == "idle":
            time.sleep(float(reply.get("retry_after", 5.0)))
            continue
        if op != "assign":
            print(f"worker {args.worker}: unexpected reply {reply}", file=sys.stderr, flush=True)
            time.sleep(5.0)
            continue

        lease = reply["lease"]
        print(f"worker {args.worker}: {lease['arm']} on {','.join(lease['hosts'])}"
              f" (lease {lease['id']})", flush=True)
        beats = Beats(args.socket, lease["id"], args.beat)
        beats.start()
        try:
            rc, log_path = run_arm(lease, executor, log_dir)
        finally:
            beats.stop.set()
            beats.join(timeout=5.0)
        note = f"log {log_path}"
        if beats.revoked:
            note += f"; lease revoked: {beats.revoked}"
        try:
            # The director reaps before answering; a stop can hold this request for a minute, and
            # a client timeout must not read as a lost report.
            protocol.request(args.socket, protocol.report(lease["id"], rc, note), timeout=300.0)
        except (OSError, protocol.ProtocolError) as exc:
            # The director reclaims an unreported lease after its TTL and reaps the hosts, so the
            # numbers are still recoverable from the receipt window on the next start.
            print(f"worker {args.worker}: cannot report {lease['id']} ({exc})", file=sys.stderr,
                  flush=True)
        print(f"worker {args.worker}: {lease['arm']} rc={rc}", flush=True)


if __name__ == "__main__":
    sys.exit(main())