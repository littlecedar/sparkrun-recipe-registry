"""The fleet lease ledger: the only claim for a multi-machine boot (owner ruling 2026-11-11).

A lease is one record naming every rank a boot takes, its holder, and an expiry. The holder names
a session; the id names a claim (holder, host set and window), so two claims from one session
coexist and a write never replaces a live claim it did not create. One mechanism serves both
writers:

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

A top-level `fenced` list holds a production serve's ranks permanently: every reader refuses them
by name, `acquire` refuses them even with `takeover`, and only deleting the record opens the hosts.
"""

from __future__ import annotations

import fcntl
import json
import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .plan import PlanError
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
        if not isinstance(data.get("fenced", []), list):
            raise LeaseError(f"{self.path}: `fenced` must be a list of fence records")
        return data

    @staticmethod
    def _live(data: dict[str, Any], now: float) -> list[dict[str, Any]]:
        return [lease for lease in data["leases"]
                if isinstance(lease, dict) and float(lease.get("expires_at") or 0) > now]

    def fences(self) -> list[dict[str, Any]]:
        """Every fence record, whatever the clock says: a fence has no expiry."""
        return [fence for fence in self._read().get("fenced") or [] if isinstance(fence, dict)]

    @staticmethod
    def _fence_holds(data: dict[str, Any], hosts: list[str] | tuple[str, ...]) -> dict[str, str]:
        """host -> why a fence holds it, for the requested hosts only."""
        wanted = set(hosts)
        held: dict[str, str] = {}
        for fence in data.get("fenced") or []:
            if not isinstance(fence, dict):
                continue
            for host in fence.get("hosts") or ():
                if host in wanted:
                    held.setdefault(host, f"fence: {fence.get('reason') or 'no reason recorded'} "
                                          f"(fenced by {fence.get('fenced_by') or '?'} at "
                                          f"{fence.get('fenced_at') or '?'})")
        return held

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
        data = self._read()
        held = self._fence_holds(data, hosts)
        for lease in self._live(data, now):
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

    @staticmethod
    def claim(record: dict[str, Any]) -> tuple[str, tuple[str, ...], str]:
        """A claim's identity: holder, host set and window -- never the holder alone.

        Measured 2026-11-11: two workstreams both used the holder `session:tp4-20261111`, and the
        second write replaced the first live record, so the first workstream's `--release`
        answered "no such live lease" while the list still showed the second. The holder names a
        session; the id (and this triple) names the claim.
        """
        return (str(record.get("holder") or ""),
                tuple(sorted(str(host) for host in record.get("hosts") or ())),
                str(record.get("window") or ""))

    def acquire(self, holder: str, hosts: list[str] | tuple[str, ...], *, ttl: float,
                arm: str = "", window: str = "", proof: list[str] | tuple[str, ...] = (),
                lease_id: str = "", takeover: bool = False,
                record_risk: str = "") -> dict[str, Any]:
        """Write one claim for `hosts`, or refuse naming every live lease it would replace.

        An identical (holder, hosts, window) re-write refreshes that record -- a restart or a
        renewing worker is not a conflict. Any other live record overlapping the requested hosts is
        a different claim, whoever holds it: the write refuses, naming each holder, host set and
        expiry, unless `takeover` says the operator means to supersede it (`note` records which).
        `record_risk` is the operator's declared acceptance of a rank on the host holding the
        campaign record root: the refusal rule is the caller's (`director lease`, the director's
        own gate), and the fact is stored here so `--list` shows it beside the claim.
        """
        hosts = [str(host) for host in hosts]
        if not hosts or len(set(hosts)) != len(hosts):
            raise LeaseError(f"one host cannot hold two ranks: {hosts!r}")
        declared = self._window_lock()
        if declared is not None:
            raise LeaseError(f"declared window {declared} is present; hands off")
        mine = (str(holder), tuple(sorted(hosts)), str(window))
        wanted = set(hosts)

        def change(data: dict[str, Any], now: float) -> dict[str, Any]:
            fenced = self._fence_holds(data, hosts)
            if fenced:
                raise LeaseError(
                    "fenced: " + "; ".join(f"{host} ({why})"
                                           for host, why in sorted(fenced.items()))
                    + " -- only deleting the fence record opens these hosts, --takeover cannot")
            existing = next((lease for lease in data["leases"]
                             if self.claim(lease) == mine), None)
            if existing is not None:
                existing.update({"ttl": float(ttl), "expires_at": now + float(ttl),
                                 "proof": list(proof)})
                if arm:
                    existing["arm"] = arm
                if record_risk:
                    existing["record_risk"] = record_risk
                return existing
            conflicts = [lease for lease in data["leases"]
                         if set(lease.get("hosts") or ()) & wanted]
            if conflicts and not takeover:
                raise PlanError(
                    f"held by a live lease: {self._describe(conflicts)} -- release it by id, or "
                    f"by holder and hosts, or re-issue this claim with --takeover")
            superseded = ""
            if conflicts:
                superseded = self._describe(conflicts)
                drop = {id(lease) for lease in conflicts}
                data["leases"] = [lease for lease in data["leases"] if id(lease) not in drop]
            used = {lease.get("id") for lease in data["leases"]}
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
            if superseded:
                record["note"] = f"takeover of {superseded}"
            if record_risk:
                record["record_risk"] = record_risk
            data["leases"].append(record)
            return record

        try:
            return self._locked(change, self.clock())
        except OSError as exc:
            raise LeaseError(f"cannot write {self.path}: {exc}") from exc

    @staticmethod
    def _describe(records: list[dict[str, Any]]) -> str:
        """One live record per clause: id, holder, hosts and expiry, so a refusal is checkable."""
        return "; ".join(
            f"{lease.get('id')} held by {lease.get('holder') or '?'} on "
            f"{','.join(lease.get('hosts') or ())} until {float(lease.get('expires_at') or 0):.0f}"
            for lease in records)

    def find(self, *, lease_id: str = "", holder: str = "",
             hosts: list[str] | tuple[str, ...] = ()) -> dict[str, Any] | None:
        """The one live record an id or a (holder, hosts) claim names, or None.

        Two records can share a holder now that a holder is a session, so a holder+hosts pair that
        matches more than one record refuses and names the candidates instead of guessing.
        """
        live = self.leases()
        if lease_id:
            return next((lease for lease in live if lease.get("id") == lease_id), None)
        wanted = {str(host) for host in hosts}
        if not holder or not wanted:
            return None
        matches = [lease for lease in live
                   if lease.get("holder") == holder
                   and set(lease.get("hosts") or ()) == wanted]
        if len(matches) > 1:
            raise PlanError(f"{holder} on {','.join(sorted(wanted))} names {len(matches)} live "
                            f"leases: {self._describe(matches)}; release one by id")
        return matches[0] if matches else None

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
