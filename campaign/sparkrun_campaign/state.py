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

#: A worker beats every 20 s; 300 s is fifteen missed beats. The bound that decides this number is
#: the director's longest in-request stall, not a dead worker's detection latency: `_report` runs a
#: leftover reap before it answers, and that reap is two listing probes, one `sparkrun stop`
#: (bounded at 60 s), per-container removals and the verifying re-probe -- under 160 s worst case.
#: A lease that expired while another worker's report was being reaped would re-boot a live arm,
#: which is the waste this design exists to prevent; 300 s keeps that margin, and five minutes of
#: detection latency is noise against a 20-130 minute arm.
LEASE_TTL = 300.0
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
        retries: int | None = None,
        order: list[str] | None = None,
    ) -> Campaign:
        """Open or create; `retries=None` (flag omitted) keeps the number the previous life stored.

        An explicit retry budget on the command line is the newer decision -- the operator
        restarting a campaign to retry a terminal arm must not have that overruled by the
        `retries=0` the previous invocation recorded.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = _acquire(path.with_name(path.name + ".lock"))
        try:
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                if data.get("version") != VERSION:
                    raise StateError(f"{path}: version {data.get('version')!r}, expected {VERSION}")
                instance = cls(path, data, fd)
                if retries is not None and int(retries) != instance.retries:
                    data["retries"] = int(retries)
                    instance.save()
                return instance
            if not campaign:
                raise StateError(f"{path} does not exist and no campaign name was given")
            data = {
                "version": VERSION,
                "campaign": campaign,
                "created_at": time.time(),
                "hosts": list(hosts),
                "max_parallel": int(max_parallel),
                "retries": int(retries or 0),
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

    def add(self, arm: str, path: str, tp: int = 1, env: dict[str, str] | None = None,
            task: str = "", memory_risky: bool = False,
            exclude_hosts: list[str] | tuple[str, ...] = (),
            nodes: int = 0, pp: int = 1,
            allow_hosts: list[str] | tuple[str, ...] = (),
            window: str = "") -> dict[str, Any]:
        """One arm. `task` is its register row id: a queue campaign closes the row it claimed.

        `nodes` is the rank count the lease takes (`tp * pp`; `tp` alone when absent), because the
        six-node TP=2 x PP=3 shape has six ranks and two TP groups -- the executor keeps `tp`.
        """
        if arm in self.data["arms"]:
            raise StateError(f"{arm!r} is already in this campaign")
        record = {
            "path": path,
            "tp": int(tp),
            "pp": int(pp),
            "nodes": int(nodes or tp),
            "env": dict(env or {}),
            "task": task,
            "memory_risky": bool(memory_risky),
            "exclude_hosts": list(exclude_hosts),
            "allow_hosts": list(allow_hosts),
            "window": window,
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
        self.event(arm, "plan", path=path, tp=int(tp), pp=int(pp), nodes=record["nodes"])
        self.save()
        return record

    def refresh(self, arm: str, *, path: str, tp: int, env: dict[str, str],
                task: str, memory_risky: bool = False,
                exclude_hosts: list[str] | tuple[str, ...] = (),
                allow_hosts: list[str] | tuple[str, ...] = (),
                window: str = "") -> bool:
        """Adopt a register row's current launch fields for an arm that is not running now.

        Queue mode's precedence: the row is the current launch plan, so an arm awaiting its next
        attempt (pending, failed inside the retry budget, or blocked with its row runnable again)
        takes the row's `env` -- a client hook or a readiness timeout added since the last attempt
        must reach the next boot, not the one already recorded. A leased, measured or skipped arm
        keeps the record it ran with, because that record is what its receipt describes.

        `path`/`tp`/`task` move only when no reap is outstanding: the containers a reap must find
        are labelled with the path that launched them, so the old path stays until `prepare` has
        proved the hosts clear (`Campaign.cleared`). The placement fields move with `env`: they are
        what the next assignment reads, and a row that now declares its shape memory-risky must
        not be placed from a stale record.
        """
        record = self.arm(arm)
        if record["status"] in (LEASED, MEASURED, SKIPPED):
            return False
        fresh: dict[str, Any] = {"env": dict(env), "memory_risky": bool(memory_risky),
                                 "exclude_hosts": list(exclude_hosts),
                                 "allow_hosts": list(allow_hosts), "window": window}
        if not record["needs_reap"]:
            fresh.update({"path": path, "tp": int(tp), "nodes": int(tp), "pp": 1, "task": task})
        changed = sorted(key for key, value in fresh.items() if record.get(key) != value)
        if not changed:
            return False
        record.update(fresh)
        self.event(arm, "reconcile", fields=changed)
        self.save()
        return True

    def set_env(self, arm: str, key: str, value: str) -> bool:
        """Pin one env cell on an arm that can still run; a finished arm's record stays final."""
        record = self.arm(arm)
        if record["status"] in (MEASURED, SKIPPED) or record["env"].get(key) == value:
            return False
        record["env"][key] = value
        self.event(arm, "env", key=key, value=value)
        self.save()
        return True

    def accept_record_risk(self, hosts: list[str] | tuple[str, ...], reason: str) -> bool:
        """Record that the operator accepted ranks on the host holding this campaign's record.

        The record-root gate refuses such a shape unless it is declared (`--accept-record-risk`),
        and this is the declaration: beside the plan it applies to, so a later reader sees a risk
        that was chosen rather than one the plan missed.
        """
        risk = {"hosts": list(hosts), "reason": reason, "accepted_at": time.time()}
        previous = self.data.get("record_risk") or {}
        if (previous.get("hosts"), previous.get("reason")) == (risk["hosts"], reason):
            return False
        self.data["record_risk"] = risk
        self.save()
        return True

    def record_skip(self, arm: str, verdict: Verdict) -> None:
        record = self.arm(arm)
        if record["status"] in (MEASURED, SKIPPED):
            return
        record["status"] = SKIPPED
        record["lease"] = None
        record["last"] = {"at": time.time(), "reason": f"{verdict['verdict']} ({verdict['doc']})"}
        self.event(arm, "skip", verdict=verdict["verdict"], doc=verdict["doc"])
        self.save()

    def assign(self, arm: str, worker: str, hosts: list[str], now: float,
               ledger: str = "") -> dict[str, Any]:
        record = self.arm(arm)
        if record["status"] == LEASED:
            raise StateError(f"{arm!r} is already leased")
        if record["needs_reap"]:
            raise StateError(f"{arm!r} still needs a reap on {record['needs_reap']}")
        nodes = int(record.get("nodes") or record["tp"])
        # Everything the worker needs to run the arm travels in the lease: the recipe path is what
        # the executor is invoked with, and `env` carries per-arm overrides (`ARM_OPTS`, `ARM_TAG`).
        # A declared window is the executor's guard-arming opt-in, so it travels as ARM_WINDOW.
        env = dict(record["env"])
        if record.get("window"):
            env["ARM_WINDOW"] = record["window"]
        lease = {
            "id": f"{arm}@{record['attempts'] + 1}",
            "arm": arm,
            "path": record["path"],
            "tp": record["tp"],
            "pp": int(record.get("pp", 1)),
            "nodes": nodes,
            "env": env,
            "worker": worker,
            "hosts": list(hosts),
            "ledger": ledger,
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

    def cleared(self, arm: str, *, evidence: str = "reap") -> None:
        """The one path that drops `needs_reap`: verifiable evidence, never a register row.

        `evidence` names what was verified, so a state file shows a reap separate from a
        register row that a human flipped back to `queued` (which says the gate opened, not
        that the hosts are clean).
        """
        record = self.arm(arm)
        record["needs_reap"] = []
        if record["status"] in (BLOCKED, LEASED):
            record["status"] = PENDING
        self.event(arm, "cleared", evidence=evidence)
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