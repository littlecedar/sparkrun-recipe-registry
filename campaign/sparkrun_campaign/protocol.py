"""Wire protocol between the campaign director and its workers.

Why a Unix stream socket and not HTTP: the director spawns every worker on the same host, so a
filesystem path is available to all of them, and the head's TCP ports are contested ground --
serves bind 8000/8010 and a BeeGFS management daemon holds 8010 there, so a collide looks exactly
like a boot that never becomes ready. A socket path needs no authentication and no firewall change.

One JSON object per line, one request per connection. Stateless request/response keeps framing
bugs out of the liveness path: the lease, not the connection, carries campaign state, so a worker
that loses the socket mid-poll has lost nothing.
"""

from __future__ import annotations

import json
import socket
from typing import Any, TypedDict

#: A poll is under a kilobyte; 64 KiB is already generous and keeps a broken peer from making the
#: director read forever.
MAX_LINE = 1 << 16


class ProtocolError(RuntimeError):
    """A peer sent something this protocol does not define."""


class Lease(TypedDict):
    """An arm assigned to one worker for a bounded time.

    The state's lease record carries audit fields on top of these (`worker`, `issued_at`,
    `heartbeat_at`); a worker needs exactly the fields below, and a test pins that it gets them.
    """

    id: str
    arm: str
    path: str
    hosts: list[str]
    tp: int
    env: dict[str, str]
    expires_at: float


class Request(TypedDict, total=False):
    """Worker -> director. `op` selects the fields that matter."""

    op: str  # "poll" | "beat" | "report"
    worker: str
    lease: str
    rc: int
    note: str


class Reply(TypedDict, total=False):
    """Director -> worker."""

    op: str  # "assign" | "idle" | "ack" | "revoked" | "error" | "shutdown"
    lease: Lease
    retry_after: float
    reason: str
    late: bool


def encode(message: dict[str, Any]) -> bytes:
    return (json.dumps(message, separators=(",", ":"), sort_keys=True) + "\n").encode("utf-8")


def decode(raw: bytes) -> dict[str, Any]:
    if len(raw) > MAX_LINE:
        raise ProtocolError(f"message is {len(raw)} bytes, limit is {MAX_LINE}")
    try:
        message = json.loads(raw)
    except ValueError as exc:
        raise ProtocolError(f"not JSON: {exc}") from exc
    if not isinstance(message, dict):
        raise ProtocolError(f"message is a {type(message).__name__}, not an object")
    if not isinstance(message.get("op"), str):
        raise ProtocolError("message has no string `op`")
    return message


def read_message(fh) -> dict[str, Any]:
    """One message from a binary file object; raises on EOF, oversize, or garbage."""
    line = fh.readline(MAX_LINE + 1)
    if not line:
        raise ProtocolError("peer closed without sending a message")
    return decode(line)


def request(socket_path, message: dict[str, Any], timeout: float = 30.0) -> dict[str, Any]:
    """One request/response round trip over a fresh connection."""
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        sock.connect(str(socket_path))
        stream = sock.makefile("rwb")
        stream.write(encode(message))
        stream.flush()
        return read_message(stream)


# --- messages -----------------------------------------------------------------------------------
# Constructors, not classes: the wire form is the contract, and a dict is what JSON gives back.


def poll(worker: str) -> dict[str, Any]:
    return {"op": "poll", "worker": worker}


def beat(lease_id: str) -> dict[str, Any]:
    return {"op": "beat", "lease": lease_id}


def report(lease_id: str, rc: int, note: str = "") -> dict[str, Any]:
    return {"op": "report", "lease": lease_id, "rc": int(rc), "note": note}


def assign(lease: dict[str, Any]) -> dict[str, Any]:
    return {"op": "assign", "lease": lease}


def idle(retry_after: float) -> dict[str, Any]:
    return {"op": "idle", "retry_after": float(retry_after)}


def ack(**extra: Any) -> dict[str, Any]:
    return {"op": "ack", **extra}


def revoked(reason: str) -> dict[str, Any]:
    return {"op": "revoked", "reason": reason}


def error(reason: str) -> dict[str, Any]:
    return {"op": "error", "reason": reason}


def shutdown() -> dict[str, Any]:
    return {"op": "shutdown"}