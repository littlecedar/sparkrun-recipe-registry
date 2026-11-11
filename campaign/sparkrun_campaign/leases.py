"""The fleet lease ledger: the only claim for a multi-machine boot (owner ruling 2026-11-11).

A lease is one record naming every rank a boot takes, its holder, and an expiry. Two claims that
used to race are one mechanism:

* the **campaign director** writes a record before it hands a multi-node boot to a worker, and
  refuses the boot when any rank is already leased;
* a **manual session** writes the same record through `director lease --hosts … --ttl …`, so the
  legacy `.local/fleet-window.lock` is no longer a second mechanism for a new window. The lock is
  still *honoured* -- as a blanket hold, the way `tools/queue-drip.py` reads it -- because a session
  that wrote one has not moved to a lease yet, and two mechanisms that disagree is the defect.

Why one file beside the director's state rather than inside it: `<CAMPAIGN_ROOT>/state.json` is one
campaign's record, and the collision the ruling exists to stop is between *different* sessions. The
ledger lives at `<repo-root>/.local/fleet-leases.json`: `.local/` is syncthing-shared (a lock written
under `.scratch/` never left the clone that wrote it, measured 2026-10-30) and git-ignored, so the
claim is visible to every checkout and no cluster address is tracked.

Writes are serialised by an exclusive `flock` on a sibling file and land through the state module's
atomic `write_json`, so a power cut leaves the old ledger or the new one. Expired records are dropped
on every write and ignored on every read; renewal is what keeps a live claim alive (`renew`, driven
by the worker's lease beat), so a director that dies stops holding ranks after one TTL like any
stale claim.
"""

from __future__ import annotations

import fcntl
import json
import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .state import write_json

#: Ledger path relative to the registry checkout.
LEDGER = Path(".local") / "fleet-leases.json"
#: The declared-window files a manual session used before this ledger. Honoured, not written.
WINDOW_LOCKS = (Path(".local") / "fleet-window.lock", Path(".scratch") / "fleet-window.lock")


class LeaseError(RuntimeError):
    """A rank is held by another lease, a window is declared, or the ledger is unreadable."""


class Ledger:
    """The lease records under one checkout's `.local/`, plus the legacy window hold."""

    def __init__(self, path: str | Path = LEDGER, *, clock: Callable[[], float] = time.time):
        self.path = Path(path)
        self.clock = clock
        # `<repo>/.local/fleet-leases.json` -> the checkout the window-lock paths resolve under.
        self.repo = self.path.parent.parent
        self.lock_path = self.path.with_name(self.path.name + ".lock")

    # --- reads -------------------------------------------------------------------------------

    def _window_lock(self) -> Path | None:
        return next((self.repo / relative for relative in WINDOW_LOCKS
                     if (self.repo / relative).exists()), None)

    def _read(self) -> dict[str, Any]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {"version": 1, "leases": []}
        except (OSError, ValueError) as exc:
            raise LeaseError(f"cannot read {self.path}: {exc}") from exc
        if not isinstance(data, dict) or not isinstance(data.get("leases"), list):
            raise LeaseError(f"{self.path} is not a lease ledger (no `leases` list)")
        return data

    @staticmethod
    def _live(data: dict[str, Any], now: float) -> list[dict[str, Any]]:
        return [lease for lease in data["leases"]
                if isinstance(lease, dict) and float(lease.get("expires_at") or 0) > now]

    def leases(self, now: float | None = None) -> list[dict[str, Any]]:
        """Every live record, oldest first. An expired one holds nothing and is not listed."""
        return self._live(self._read(), self.clock() if now is None else now)

    def held_hosts(self, hosts: list[str] | tuple[str, ...], now: float | None = None,
                   *, holder: str = "") -> dict[str, str]:
        """host -> why it is not free, for another holder's lease or a declared window.

        `holder` is the caller's own identity: its records are its own claim, governed by the
        campaign's state and reap, never a conflict with itself. A window lock holds every host
        it is asked about, which is how the legacy file reads today.
        """
        hosts = list(hosts)
        window = self._window_lock()
        if window is not None:
            return {host: f"declared window {window}" for host in hosts}
        now = self.clock() if now is None else now
        held: dict[str, str] = {}
        for lease in self._live(self._read(), now):
            if lease.get("holder") == holder:
                continue
            for host in lease.get("hosts") or ():
                if host in hosts:
                    held.setdefault(host, f"lease {lease.get('id')} held by "
                                          f"{lease.get('holder') or '?'}")
        return held

    # --- writes ------------------------------------------------------------------------------

    def _locked(self, change: Callable[[dict[str, Any], float], Any], now: float) -> Any:
        """Apply `change` under the ledger lock, pruning expired records, then persist it."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.lock_path, os.O_CREAT | os.O_RDWR, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            data = self._read()
            data["leases"] = self._live(data, now)
            result = change(data, now)
            write_json(self.path, data)
            return result
        finally:
            os.close(fd)

    def acquire(self, holder: str, hosts: list[str] | tuple[str, ...], *, ttl: float,
                arm: str = "", window: str = "", proof: list[str] | tuple[str, ...] = (),
                lease_id: str = "") -> dict[str, Any]:
        """Write one lease for `hosts`, or raise naming the rank another holder has."""
        hosts = [str(host) for host in hosts]
        if not hosts or len(set(hosts)) != len(hosts):
            raise LeaseError(f"one host cannot hold two ranks: {hosts!r}")
        declared = self._window_lock()
        if declared is not None:
            raise LeaseError(f"declared window {declared} is present; hands off")

        def change(data: dict[str, Any], now: float) -> dict[str, Any]:
            # A repeat by the same holder for an overlapping rank is this session's own stale
            # claim (a restart saw its campaign lease expire), never a conflict with a peer.
            live = [lease for lease in data["leases"]
                    if not (lease.get("holder") == holder
                            and set(lease.get("hosts") or ()) & set(hosts))]
            data["leases"] = live
            conflicts: dict[str, str] = {}
            for lease in live:
                for host in lease.get("hosts") or ():
                    if host in hosts:
                        conflicts.setdefault(host, str(lease.get("holder") or "?"))
            if conflicts:
                raise LeaseError("held by another lease: " + ", ".join(
                    f"{host} ({name})" for host, name in sorted(conflicts.items())))
            used = {lease.get("id") for lease in live}
            base = lease_id or f"{holder}:{arm or 'manual'}:{int(now)}"
            record_id, index = base, 1
            while record_id in used:
                index += 1
                record_id = f"{base}:{index}"
            record = {
                "id": record_id,
                "holder": holder,
                "hosts": hosts,
                "arm": arm,
                "window": window,
                "proof": list(proof),
                "ttl": float(ttl),
                "issued_at": now,
                "expires_at": now + float(ttl),
            }
            data["leases"].append(record)
            return record

        try:
            return self._locked(change, self.clock())
        except OSError as exc:
            raise LeaseError(f"cannot write {self.path}: {exc}") from exc

    def renew(self, lease_id: str, now: float | None = None) -> bool:
        """Extend a live lease by its own TTL; False when it is gone."""
        if not lease_id:
            return False

        def change(data: dict[str, Any], at: float) -> bool:
            for lease in data["leases"]:
                if lease.get("id") == lease_id:
                    lease["expires_at"] = at + float(lease.get("ttl") or 0)
                    return True
            return False

        try:
            return bool(self._locked(change, self.clock() if now is None else now))
        except OSError:
            return False

    def release(self, lease_id: str) -> bool:
        """Drop one lease now; False when it was already gone or the ledger could not be written."""
        if not lease_id:
            return False

        def change(data: dict[str, Any], _now: float) -> bool:
            kept = [lease for lease in data["leases"] if lease.get("id") != lease_id]
            if len(kept) == len(data["leases"]):
                return False
            data["leases"] = kept
            return True

        try:
            return bool(self._locked(change, self.clock()))
        except OSError:
            return False
