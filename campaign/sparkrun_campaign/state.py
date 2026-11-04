"""The campaign's persisted state: the plan as issued, one record per arm.

Why a file and not memory: acceptance item 7, resume a half-finished campaign after a reboot.
Nothing about a campaign lives only in the director's heap. Every transition rewrites `state.json`
atomically -- serialise, write a temp file, fsync it, replace, fsync the directory -- so a power
cut leaves either the old document or the new one, never a truncated one.

Why one JSON document and not a database: a campaign is tens of arms and a few transitions per
arm-minute. Something an operator can read with `less` after a failed night is the right durability
mechanism at this size.

Ownership: the file is the record, and an exclusive `flock` beside it is what makes a second
director refuse to start. Two directors over one plan is the double-boot this project exists to
prevent, so the refusal is at open time, not at first assignment.
"""

from __future__ import annotations

import fcntl
import json
import os
import time
from pathlib import Path
from typing import Any

from .evidence import Verdict

VERSION = 1

PENDING = "pending"   # eligible for assignment
LEASED = "leased"     # one worker holds it (there is no separate "running": the lease is the record)
MEASURED = "measured" # a receipt says the arm has numbers
FAILED = "failed"     # a receipt does not; retryable while `failures <= retries`
SKIPPED = "skipped"   # the recipe records this arm as a measured negative
BLOCKED = "blocked"   # a human must look: an unverifiable leftover, or a reap that could not run

#: A worker beats every few seconds; 120 s is six missed beats. Deliberately generous: a false
#: reclaim costs a second boot of a 20-130 minute arm, which is the waste this design prevents,
#: while detection latency of two minutes is noise against an arm.
LEASE_TTL = 120.0
#: Diagnostics only -- the last events per arm; the authoritative record of a measurement is the
#: receipt on disk, never this history.
HISTORY_CAP = 40


class StateError(RuntimeError):
    """The state file is unreadable, held by another director, or the transition is illegal."""


def write_json(path: str | Path, data: dict[str, Any]) -> None:
    """Durably replace `path` with `data`: temp file, fsync, rename, fsync the directory.

    Serialisation happens before the temp file is opened, so a value that cannot be encoded leaves
    the previous document untouched.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=1, sort_keys=True) + "\n"
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)
    dir_fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def _acquire(lock_path: Path) -> int:
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        os.close(fd)
        raise StateError(f"{lock_path} is held by another director ({exc})") from exc
    return fd


class Campaign:
    """One campaign's plan and per-arm records, loaded from and saved to one JSON file."""

    def __init__(self, path: str | Path, data: dict[str, Any], lock_fd: int | None = None):
        self.path = Path(path)
        self.data = data
        self._lock_fd = lock_fd

    # --- lifecycle ---------------------------------------------------------------------------

    @classmethod
    def open(
        cls,
        path: str | Path,
        *,
        campaign: str = "",
        hosts: tuple[str, ...] | list[str] = (),
        max_parallel: int = 1,
        retries: int = 0,
        order: list[str] | None = None,
    ) -> Campaign:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = _acquire(path.with_name(path.name + ".lock"))
        try:
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                if data.get("version") != VERSION:
                    raise StateError(f"{path}: version {data.get('version')!r}, expected {VERSION}")
                return cls(path, data, fd)
            if not campaign:
                raise StateError(f"{path} does not exist and no campaign name was given")
            data = {
                "version": VERSION,
                "campaign": campaign,
                "created_at": time.time(),
                "hosts": list(hosts),
                "max_parallel": int(max_parallel),
                "retries": int(retries),
                "lease_ttl": LEASE_TTL,
                "order": list(order or []),
                "arms": {},
            }
            instance = cls(path, data, fd)
            instance.save()
            return instance
        except BaseException:
            os.close(fd)
            raise

    def close(self) -> None:
        if self._lock_fd is not None:
            os.close(self._lock_fd)
            self._lock_fd = None

    def save(self) -> None:
        write_json(self.path, self.data)

    # --- queries -----------------------------------------------------------------------------

    @property
    def retries(self) -> int:
        return int(self.data.get("retries", 0))

    @property
    def lease_ttl(self) -> float:
        return float(self.data.get("lease_ttl", LEASE_TTL))

    @property
    def order(self) -> list[str]:
        return list(self.data["order"])

    def arms(self) -> dict[str, dict[str, Any]]:
        return self.data["arms"]

    def arm(self, arm: str) -> dict[str, Any]:
        try:
            return self.data["arms"][arm]
        except KeyError as exc:
            raise StateError(f"{arm!r} is not in this campaign's plan") from exc

    def free_hosts(self, now: float) -> list[str]:
        """Hosts no live lease holds. An expired lease holds nothing -- `expire()` clears it."""
        held: set[str] = set()
        for record in self.data["arms"].values():
            lease = record.get("lease")
            if lease and float(lease["expires_at"]) > now:
                held.update(lease["hosts"])
        return [host for host in self.data["hosts"] if host not in held]

    def lease_for(self, lease_id: str) -> tuple[str, dict[str, Any]] | None:
        for arm, record in self.data["arms"].items():
            lease = record.get("lease")
            if lease and lease["id"] == lease_id:
                return arm, lease
        return None

    # --- transitions -------------------------------------------------------------------------

    def event(self, arm: str, kind: str, **detail) -> None:
        record = self.data["arms"][arm]
        record.setdefault("history", []).append({"at": time.time(), "kind": kind, **detail})
        del record["history"][:-HISTORY_CAP]

    def add(self, arm: str, path: str, tp: int = 1, env: dict[str, str] | None = None) -> dict[str, Any]:
        if arm in self.data["arms"]:
            raise StateError(f"{arm!r} is already in this campaign")
        record = {
            "path": path,
            "tp": int(tp),
            "env": dict(env or {}),
            "status": PENDING,
            "attempts": 0,
            "failures": 0,
            "lease": None,
            "needs_reap": [],
            "last": {},
            "history": [],
        }
        self.data["arms"][arm] = record
        if arm not in self.data["order"]:
            self.data["order"].append(arm)
        self.event(arm, "plan", path=path, tp=int(tp))
        self.save()
        return record

    def record_skip(self, arm: str, verdict: Verdict) -> None:
        record = self.arm(arm)
        if record["status"] in (MEASURED, SKIPPED):
            return
        record["status"] = SKIPPED
        record["lease"] = None
        record["last"] = {"at": time.time(), "reason": f"{verdict['verdict']} ({verdict['doc']})"}
        self.event(arm, "skip", verdict=verdict["verdict"], doc=verdict["doc"])
        self.save()

    def assign(self, arm: str, worker: str, hosts: list[str], now: float) -> dict[str, Any]:
        record = self.arm(arm)
        if record["status"] == LEASED:
            raise StateError(f"{arm!r} is already leased")
        if record["needs_reap"]:
            raise StateError(f"{arm!r} still needs a reap on {record['needs_reap']}")
        # Everything the worker needs to run the arm travels in the lease: the recipe path is what
        # the executor is invoked with, and `env` carries per-arm overrides (`ARM_OPTS`, `ARM_TAG`).
        lease = {
            "id": f"{arm}@{record['attempts'] + 1}",
            "arm": arm,
            "path": record["path"],
            "tp": record["tp"],
            "env": dict(record["env"]),
            "worker": worker,
            "hosts": list(hosts),
            "issued_at": now,
            "heartbeat_at": now,
            "expires_at": now + self.lease_ttl,
        }
        record["lease"] = lease
        record["status"] = LEASED
        record["attempts"] += 1
        self.event(arm, "assign", worker=worker, hosts=hosts, lease=lease["id"])
        self.save()
        return lease

    def beat(self, lease_id: str, now: float) -> bool:
        """Refresh a live lease; False when it is gone or already expired."""
        found = self.lease_for(lease_id)
        if found is None:
            return False
        _, lease = found
        if float(lease["expires_at"]) <= now:
            return False
        lease["heartbeat_at"] = now
        lease["expires_at"] = now + self.lease_ttl
        self.save()
        return True

    def expire(self, now: float) -> list[dict[str, Any]]:
        """Release leases nobody is holding; each comes back needing a reap of its hosts."""
        expired: list[dict[str, Any]] = []
        for arm, record in self.data["arms"].items():
            lease = record.get("lease")
            if not lease or float(lease["expires_at"]) > now:
                continue
            record["needs_reap"] = sorted(set(record["needs_reap"]) | set(lease["hosts"]))
            record["status"] = PENDING if record["status"] == LEASED else record["status"]
            record["lease"] = None
            self.event(arm, "expire", worker=lease["worker"], hosts=lease["hosts"])
            expired.append({"arm": arm, "hosts": record["needs_reap"]})
        if expired:
            self.save()
        return expired

    def need_reap(self, arm: str, hosts: list[str], reason: str) -> None:
        record = self.arm(arm)
        record["needs_reap"] = sorted(set(record["needs_reap"]) | set(hosts))
        self.event(arm, "reap-needed", hosts=hosts, reason=reason)
        self.save()

    def cleared(self, arm: str) -> None:
        """A verified reap: the arm is assignable again, including one a failed reap blocked."""
        record = self.arm(arm)
        record["needs_reap"] = []
        if record["status"] in (BLOCKED, LEASED):
            record["status"] = PENDING
        self.event(arm, "reaped")
        self.save()

    def finish(
        self,
        arm: str,
        *,
        status: str,
        rc: int | None,
        reason: str,
        measurement_dir: str = "",
        measured: bool = False,
    ) -> None:
        if status not in (MEASURED, FAILED):
            raise StateError(f"finish() takes {MEASURED!r} or {FAILED!r}, not {status!r}")
        record = self.arm(arm)
        record["lease"] = None
        record["status"] = status
        record["last"] = {
            "at": time.time(),
            "rc": rc,
            "reason": reason,
            "measurement_dir": measurement_dir,
            "measured": measured,
        }
        if status == FAILED:
            record["failures"] += 1
        self.event(arm, "report", status=status, rc=rc, reason=reason)
        self.save()

    def mark_measured(self, arm: str, measurement_dir: str, reason: str) -> None:
        """A receipt proves the arm has numbers, so the campaign records that without a boot."""
        record = self.arm(arm)
        record["status"] = MEASURED
        record["lease"] = None
        record["last"] = {"at": time.time(), "reason": reason,
                          "measurement_dir": measurement_dir, "measured": True}
        self.event(arm, "measured-on-disk", dir=measurement_dir)
        self.save()

    def block(self, arm: str, reason: str, hosts: list[str] | None = None, **extra: Any) -> None:
        """Stop the run for this arm and keep whatever the report knew (`rc`, `measured`, ...)."""
        record = self.arm(arm)
        record["status"] = BLOCKED
        record["lease"] = None
        if hosts:
            record["needs_reap"] = sorted(set(record["needs_reap"]) | set(hosts))
        record["last"] = {"at": time.time(), "reason": reason, **extra}
        self.event(arm, "blocked", reason=reason)
        self.save()

    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for record in self.data["arms"].values():
            out[record["status"]] = out.get(record["status"], 0) + 1
        return out