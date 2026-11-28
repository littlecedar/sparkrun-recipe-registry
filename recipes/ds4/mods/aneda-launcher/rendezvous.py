#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Little Cedar Group <sparkrun@littlecedar.net>
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Assemble the four rail tails the picom engine's fleet file names.

Why this exists: `ANEDA_RANK_TAILS` used to be an operator input, because
sparkrun exposes no host list to a recipe (`core/env_templates.py` LAUNCH_FIELDS
is closed) and the fleet is addressed by rail octets. A default launch then
needed `-o env.ANEDA_RANK_TAILS=…`, which is a bug in the recipe, not a knob.

Every rank does know two things without help:
  * its own rail tail — from its own RoCE GID at the index sparkrun injects
    (`run.sh` resolves it and writes it to `fabric.env`);
  * rank 0's management address — `SPARKRUN_HEAD_HOST`, in the pre_exec hook
    environment (`sparkrun/orchestration/hooks.py:110-125`), which `run.sh`
    carries into `fabric.env`.
So rank 0 collects the three peers' tails over one TCP connection each and
replies with the assembled list; every rank renders its own `fleet.conf`
(the runtime directories are per node, not shared).

Rank 0 is the collector because it is the only address every rank knows. The
port is fixed at 19110: 8000 is dsfront, 18620 is the engine's ring bootstrap,
25000 is sparkrun's torch rendezvous gate — none of those may be shadowed.

Fail-closed: a missing rank at the deadline aborts with its name, and no engine
is started on a partial list.
"""

from __future__ import annotations

import argparse
import socket
import sys
import time

PORT = 19110
DEADLINE_S = 300.0


def serve(head: str, rank: int, tail: str, timeout: float) -> str:
    """Rank 0: collect every peer's tail, then answer each with the full list."""
    start = time.monotonic()
    deadline = start + timeout
    tails: dict[int, str] = {rank: tail}
    pending: list[socket.socket] = []
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.settimeout(1.0)
    try:
        server.bind(("", PORT))
        server.listen(8)
        print(f"rendezvous: rank 0 collecting on {head}:{PORT}", file=sys.stderr, flush=True)
        while len(tails) < 4 and time.monotonic() < deadline:
            try:
                conn, _peer = server.accept()
            except TimeoutError:
                continue
            except OSError as exc:
                raise SystemExit(f"rendezvous: rank 0 cannot accept on {head}:{PORT}: {exc}")
            conn.settimeout(5.0)
            try:
                line = conn.makefile("r", encoding="ascii").readline()
                parts = line.split()
                if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
                    conn.close()
                    continue
                peer_rank, peer_tail = int(parts[0]), int(parts[1])
                if not 0 <= peer_rank < 4 or not 0 <= peer_tail <= 255:
                    conn.close()
                    continue
                if peer_rank in tails and tails[peer_rank] != str(peer_tail):
                    raise SystemExit(
                        "rendezvous: rank %d announced two different tails (%s, %d)"
                        % (peer_rank, tails[peer_rank], peer_tail)
                    )
                tails[peer_rank] = str(peer_tail)
                pending.append(conn)
            except OSError:
                conn.close()
        if len(tails) < 4:
            missing = ",".join(str(r) for r in range(4) if r not in tails)
            for conn in pending:
                _reply(conn, "MISSING " + missing)
            raise SystemExit(
                "rendezvous: timed out after %ds with ranks %s missing; the engine "
                "is not started on a partial fleet" % (int(timeout), missing)
            )
        ordered = ",".join(tails[r] for r in range(4))
        for conn in pending:
            _reply(conn, "TAILS " + ordered)
        print("rendezvous: rank 0 assembled tails " + ordered, file=sys.stderr, flush=True)
        return ordered
    finally:
        server.close()


def _reply(conn: socket.socket, payload: str) -> None:
    try:
        conn.sendall((payload + "\n").encode("ascii"))
    except OSError:
        pass
    finally:
        conn.close()


def join(head: str, rank: int, tail: str, timeout: float) -> str:
    """Rank r > 0: announce own tail to rank 0 and wait for the assembled list."""
    start = time.monotonic()
    deadline = start + timeout
    last = "no attempt"
    while time.monotonic() < deadline:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5.0)
        try:
            sock.connect((head, PORT))
            sock.sendall(("%d %s\n" % (rank, tail)).encode("ascii"))
            reply = sock.makefile("r", encoding="ascii").readline().strip()
        except OSError as exc:
            last = str(exc)
            sock.close()
            time.sleep(0.5)
            continue
        finally:
            sock.close()
        if reply.startswith("TAILS "):
            ordered = reply[6:]
            if len(ordered.split(",")) != 4:
                raise SystemExit("rendezvous: rank 0 sent a malformed list: " + reply)
            return ordered
        if reply.startswith("MISSING "):
            raise SystemExit(
                "rendezvous: rank 0 timed out with ranks %s missing; the engine is "
                "not started on a partial fleet" % reply[8:]
            )
        last = "unexpected reply: " + (reply or "<empty>")
        time.sleep(0.5)
    raise SystemExit(
        "rendezvous: rank %d could not reach rank 0 at %s:%d within %ds (%s)"
        % (rank, head, PORT, int(timeout), last)
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Exchange picom rail tails over the management network.")
    ap.add_argument("--head", required=True, help="rank 0's management address (SPARKRUN_HEAD_HOST)")
    ap.add_argument("--rank", required=True, type=int, help="this node's rank (ANEDA_NODE_RANK)")
    ap.add_argument("--tail", required=True, help="this node's own rail octet (from its RoCE GID)")
    ap.add_argument("--timeout", type=float, default=None, help=f"seconds (default {DEADLINE_S:.0f})")
    args = ap.parse_args(argv)
    if not 0 <= args.rank < 4:
        print(f"rendezvous: rank {args.rank} is not 0-3", file=sys.stderr)
        return 2
    timeout = args.timeout if args.timeout is not None else DEADLINE_S
    tails = serve(args.head, args.rank, args.tail, timeout) if args.rank == 0 else join(
        args.head, args.rank, args.tail, timeout
    )
    print(tails)
    return 0


if __name__ == "__main__":
    sys.exit(main())
