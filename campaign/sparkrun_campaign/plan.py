"""What runs next, and on which hosts.

Two plan sources, one placement rule. A **manifest** is a hand-written list whose order is the
plan. A **queue campaign** reads the register (`mad-science/queue.json`) instead: rows that name a
`recipe` and its `tp` are the work, ordered by the register's own weighted order, which is read from
`tools/task-queue.py queue --json` rather than re-derived here -- one implementation of the weight
arithmetic, not two. The declared host set is still the whole node set a campaign may use; the
director discovers *work*, never nodes.

Ordering is the manifest's order. There is no static partition of the plan into per-node slices:
the 2026-11-04 campaign lost 2.02 node-hours because one node's slice ended with a 132-minute arm
while the other node sat idle with nothing queued. A static slice cannot see its peer's queue; a
director that hands the next pending arm to whichever slot is free can, so that is the only
placement rule here.

Assignment is a pure function of (order, arm records, free hosts). It takes no clock and does no
I/O, which is what lets the placement rules -- a leaked host, an arm awaiting a reap, a TP=2 arm
with one host free -- be tested without a fleet.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .evidence import Verdict, skip_line
from .state import FAILED, LEASED, PENDING, SKIPPED

#: Runtime keys a recipe may carry. `tp` is the tensor-parallel width; the manifest is where that
#: decision lives because it is a property of the arm, not of the run, and the rank count is
#: `tp * pp` (`pp` defaults to 1 -- tp 2 x pp 3 is the six-node shape, `next_assignment` reads
#: `nodes`). A queue row may ask for a quartet (`tp=4`), which `queue_entries` admits only when
#: four hosts are declared; the register itself stays tp in {1,2,4}.
TP_VALUES = (1, 2)
#: The register, relative to `--repo-root`, when `--queue` is given without a path.
DEFAULT_QUEUE = "mad-science/queue.json"
#: Hosts a memory-risky shape may not take. `.30` is the head: it carries ssh, NetworkManager and
#: BeeGFS, and a global pool overrun there takes those units with it, so the memory-overrunning
#: shapes run on the other five while `.30` stays an ordinary worker for the rest. Shorthand on
#: purpose: tracked files may not carry cluster addresses or the head's hostname (the hygiene
#: gate), so a hostname-declared set names the head through `--exclude-host` /
#: `$CAMPAIGN_EXCLUDE_HOSTS`. A host matches an entry exactly or by the `.30` tail (an address
#: ending in `.30` matches `.30`), and a risky row whose exclusion set matches no declared host
#: refuses the plan rather than ordering as if the head were absent.
MEMORY_RISKY_EXCLUDED_HOSTS = (".30",)


def barred(host: str, entries: tuple[str, ...] | list[str]) -> bool:
    """Whether `host` matches any exclusion entry (exact, or the `.30` tail shorthand)."""
    return any(host == entry or (entry.startswith(".") and host.endswith(entry))
               for entry in entries)


def memory_risky(row: dict[str, Any]) -> bool:
    """Whether a shape may not take an excluded host.

    The row decides, explicitly: `memory_risky: true`, or `exclude_hosts` naming hosts for this
    arm alone. Absent both, the only numeric shape declaration the register carries is
    `node_cost`, and a quartet is the class that has overrun the pool. `tp` alone is wrong in both
    directions -- a TP=2 x PP=3 six-node shape overruns while a ~20 GiB/rank quartet does not --
    so a shape the row does not classify is not refused; the excluded hosts still sort last for
    it, so it cannot displace a safe host it had room for.
    """
    if "memory_risky" in row:
        return bool(row["memory_risky"])
    return bool(row.get("exclude_hosts")) or row.get("node_cost") == "quartet"


def waiver(owner: str, row: dict[str, Any], risky: bool,
           excluded: tuple[str, ...] | None = None) -> tuple[list[str], str]:
    """(hosts this boot may take despite the exclusion, its declared window name).

    Owner ruling 2026-11-11 (#2): an excluded host is waivable only inside a window named per boot
    and only by that boot's own declaration. A declaration without a window name is the silent
    placement the ruling forbids, so it refuses the plan; when the run's exclusion set is known
    (`excluded`), a waiver naming none of its hosts refuses too, because it could never be used
    and would read as a guard that was not one.
    """
    declared = row.get("allow_hosts") or ()
    window = str(row.get("window") or "").strip()
    if not declared:
        return [], ""
    if not isinstance(declared, (list, tuple)) or not all(
            isinstance(host, str) and host.strip() for host in declared):
        raise PlanError(f"{owner}: allow_hosts must be a list of host strings, got {declared!r}")
    hosts = [host.strip() for host in declared]
    if not risky:
        raise PlanError(f"{owner}: allow_hosts {hosts} without memory_risky; only a memory-risky "
                        "shape may waive the exclusion")
    if not window:
        raise PlanError(f"{owner}: allow_hosts {hosts} without a declared `window` name; the "
                        "exclusion is waivable only inside a window named per boot")
    if excluded is not None and not any(barred(host, excluded) for host in hosts):
        raise PlanError(f"{owner}: allow_hosts {hosts} names no excluded host "
                        f"{list(excluded)}; the waiver would be inert")
    return hosts, window


class PlanError(RuntimeError):
    """The plan cannot be issued as written. Never plan around a broken one."""


class RegisterError(RuntimeError):
    """The register refused a read or a write. Never read as "nothing to do"."""


class Register:
    """The queue register: plan source and the one writer of claims, via `tools/task-queue.py`.

    Shelled out, never imported: `tools/` is stdlib-only and dash-named, and the tool owns the
    register's atomic save -- a second writer here would race its own lock out of existence. The
    ordering, the tiering and the weight arithmetic are the tool's too, so this package carries no
    second copy to drift.
    """

    def __init__(self, tool: str | Path, queue: str | Path, session: str,
                 run: Callable[..., Any] = subprocess.run):
        self.tool = Path(tool)
        self.queue = Path(queue)
        self.session = session
        self._run = run

    def _call(self, *args: str) -> str:
        command = [sys.executable, "-B", str(self.tool), "--file", str(self.queue), *args]
        result = self._run(command, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise RegisterError(f"{' '.join(args)}: rc={result.returncode}: "
                                f"{(result.stderr or '').strip()[:300]}")
        return result.stdout

    def rows(self) -> list[dict[str, Any]]:
        """Every task, in the register's own weighted order."""
        try:
            rows = json.loads(self._call("queue", "--json"))
        except ValueError as exc:
            raise RegisterError(f"{self.queue}: queue --json is not JSON: {exc}") from exc
        if not isinstance(rows, list):
            raise RegisterError(f"{self.queue}: queue --json is not a list of tasks")
        return rows

    def update(self, task_id: str, **fields: Any) -> None:
        """The tool is the writer: `update` relinks, validates, then replaces the file atomically."""
        argv = ["update", "--id", task_id]
        for key, value in fields.items():
            argv += [f"--{key.replace('_', '-')}", str(value)]
        self._call(*argv)

    def state(self, task_id: str) -> str:
        """The row's state as the file says now, or "" when the row is gone."""
        return next((str(row.get("state", "")) for row in self.rows()
                     if row.get("id") == task_id), "")

    def note(self, task_id: str, why: str) -> str:
        """The row's notes with `why` appended, because `--notes` replaces the whole cell."""
        current = next((str(row.get("notes", "")) for row in self.rows()
                        if row.get("id") == task_id), "")
        return f"{current} — {why}" if current else why


def row_arm(row: dict[str, Any]) -> str:
    """The arm a register row names: its recipe's basename, or "" for an authoring row."""
    recipe = row.get("recipe")
    return Path(str(recipe)).stem if recipe else ""


def row_runnable(row: dict[str, Any], session: str) -> bool:
    """A row a campaign may claim now: explicit `queued` (or our own claim), no hold."""
    state = row.get("state")
    ours = state == "running" and row.get("claimed_by") == session
    return (state == "queued" or ours) and row.get("blocked_by") == []


def sibling_hold(others: list[dict[str, Any]], session: str) -> str:
    """The strictest row sharing a recipe that holds it, as a log phrase, or "".

    One recipe named by several rows is one arm, so a `blocked` or `done` sibling holds it even
    when its own row reads `queued`; the 2026-11-08 survey pair (`done` + `blocked`) showed a
    queued sibling protecting nothing. `blocked` outranks `done` outranks another session's
    `running`; two runnable rows are not a hold but an ambiguity `queue_entries` skips by name.
    """
    order = {"blocked": 0, "done": 1, "running": 2}
    held = [row for row in others if not row_runnable(row, session)]
    if not held:
        return ""
    worst = min(held, key=lambda row: order.get(str(row.get("state")), 3))
    state = worst.get("state")
    if state == "queued":
        held_by = ", ".join(str(ref) for ref in worst.get("blocked_by") or [])
        return (f"sibling {worst.get('id', '?')} is held by "
                f"{held_by or 'a missing blocked_by list'}")
    return f"sibling {worst.get('id', '?')} is {state!r}"


def queue_entries(rows: list[dict[str, Any]], hosts: list[str], session: str,
                  held: set[str] | frozenset[str] = frozenset(),
                  excluded_hosts: tuple[str, ...] = MEMORY_RISKY_EXCLUDED_HOSTS,
                  ) -> tuple[list[dict[str, Any]], list[str], dict[str, str]]:
    """(entries, explanation lines, arm -> why it is not runnable) from the register's ordering.

    Only `queued` rows that name a `recipe` and `tp` are work: `blocked`/`done` are somebody else's
    answer, `running` is another session's claim, and a row whose `tp` exceeds the declared host
    count is skipped by name rather than truncated onto fewer nodes. A row whose `blocked_by` is
    not an explicit empty list is held too, whatever its `state`: the mirror is the register's
    structural hold, and a missing field is not an edit that opens one. A recipe named by several
    rows is one arm, so a `blocked` or `done` sibling holds it even while the row being read says
    `queued` (the skip names the sibling and its state); two runnable rows for one recipe are an
    ambiguity skipped by name for that tick, because the register has not said which row the
    numbers would close. An authoring row is counted, not listed: the register is mostly prose
    work and a line per row would bury the exclusions that matter.

    A `running` row under this campaign's own session id is still offered when `held` (the arms the
    campaign already has) contains it: that is the in-flight arm a restart must finish, and the
    campaign's own lease/reap record is what makes re-assignment safe. The same row with no
    campaign state behind it is a stale claim from a root that was lost -- refused by name, because
    adopting it would boot an arm whose previous boot nobody has verified stopped.
    """
    entries: list[dict[str, Any]] = []
    lines: list[str] = []
    excluded: dict[str, str] = {}
    owner: dict[str, str] = {}
    authoring = 0
    by_recipe: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if row.get("recipe"):
            by_recipe.setdefault(row_arm(row), []).append(row)
    for row in rows:
        task = str(row.get("id", "?"))
        state = row.get("state")
        recipe, tp = row.get("recipe"), row.get("tp")
        if not recipe or not tp:
            if state == "queued":
                authoring += 1      # queued prose/work rows: counted, because that is the queue
            continue
        arm = Path(str(recipe)).stem
        blocked_by = row.get("blocked_by")
        if blocked_by != []:
            # An explicit empty mirror is the register's "nothing holds this"; a live edge is a
            # hold whatever `state` says, and a missing field is not an edit that opens one.
            reason = ("register row has no blocked_by list" if not isinstance(blocked_by, list)
                      else f"blocked by {', '.join(str(ref) for ref in blocked_by)}")
            lines.append(f"queue-skip: {task} ({reason})")
            excluded[arm] = reason
            continue
        ours = state == "running" and row.get("claimed_by") == session
        if state != "queued" and not (ours and arm in held):
            reason = (f"claimed running by {session} with no campaign state (stale claim)"
                      if ours else
                      f"claimed running by {row.get('claimed_by') or 'another session'}"
                      if state == "running" else f"register state {state}")
            lines.append(f"queue-skip: {task} ({reason})")
            excluded[arm] = reason
            continue
        if tp > len(hosts):
            reason = f"tp={tp} needs {tp} hosts, {len(hosts)} declared"
            lines.append(f"queue-skip: {task} ({reason})")
            excluded[arm] = reason
            continue
        risky = memory_risky(row)
        declared = row.get("exclude_hosts") or ()
        per_arm = tuple(str(host) for host in declared) if isinstance(declared, (list, tuple)) else ()
        allow, window = waiver(task, row, risky, tuple(excluded_hosts) + per_arm)
        if risky:
            # A shape that cannot be placed without an excluded host is refused by name, never
            # narrowed onto that host: the row stays queued for a human to reshape. A declared
            # waiver is the one exception, and the director proves the host's guardrails before
            # the lease record exists.
            barred_for_arm = tuple(excluded_hosts) + per_arm
            if barred_for_arm and not any(barred(host, barred_for_arm) for host in hosts):
                # Fail closed: a hostname-declared set that matches no exclusion would sort as if
                # the head were not in it and take the head first -- the guard installed on paper.
                raise PlanError(
                    f"{task}: exclusion {', '.join(barred_for_arm)} matched no declared host "
                    f"{hosts!r}; declare the head under one of those names or pass --exclude-host")
            safe = [host for host in hosts if not barred(host, barred_for_arm)]
            waived = [host for host in hosts
                      if barred(host, barred_for_arm) and barred(host, allow)]
            if tp > len(safe) + len(waived):
                hit = [host for host in hosts
                       if barred(host, barred_for_arm) and host not in waived]
                reason = (f"memory-risky shape needs {tp} ranks, {len(safe) + len(waived)} "
                          f"declared outside {', '.join(hit) or 'the excluded hosts'}")
                lines.append(f"queue-skip: {task} ({reason})")
                excluded[arm] = reason
                continue
        hold = sibling_hold([other for other in by_recipe.get(arm, []) if other is not row],
                            session)
        if hold:
            reason = f"recipe also named by {hold}"
            lines.append(f"queue-skip: {task} ({reason})")
            excluded[arm] = reason
            continue
        if arm in owner:
            # Two runnable rows for one recipe are an ambiguity, not a broken register: skip that
            # recipe for this tick and name both rows, so every other arm still runs.
            previous = owner[arm]
            entries[:] = [entry for entry in entries if entry["arm"] != arm]
            reason = f"{previous} and {task} both name recipe {recipe}"
            lines.append(f"queue-skip: {arm} ({reason})")
            excluded[arm] = reason
            owner[arm] = task
            continue
        owner[arm] = task
        entries.append({"arm": arm, "path": recipe, "tp": int(tp), "pp": 1, "nodes": int(tp),
                        "env": dict(row.get("env") or {}), "task": task,
                        "memory_risky": risky, "exclude_hosts": list(per_arm),
                        "allow_hosts": allow, "window": window})
    if authoring:
        lines.append(f"queue: {authoring} row(s) queued without a recipe (authoring, not bootable)")
    return entries, lines, excluded


def load_manifest(path: str | Path) -> list[dict[str, Any]]:
    """Read and validate a campaign manifest: a JSON list of {arm, path, tp, pp?, env?}.

    `nodes` is `tp * pp`, so the six-node TP=2 x PP=3 shape is expressible here while the
    register's `tp` stays in {1, 2, 4}. `memory_risky`, `allow_hosts` and `window` are the same
    head-host waiver a register row may declare, and the director proves its guardrails before
    the lease.
    """
    path = Path(path)
    try:
        entries = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise PlanError(f"cannot read {path}: {exc}") from exc
    except ValueError as exc:
        raise PlanError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(entries, list):
        raise PlanError(f"{path} must hold a list of arms")
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise PlanError(f"{path}: entry {index} is a {type(entry).__name__}, not an object")
        arm = entry.get("arm")
        recipe = entry.get("path")
        if not isinstance(arm, str) or not arm:
            raise PlanError(f"{path}: entry {index} has no `arm` string")
        if not isinstance(recipe, str) or not recipe:
            raise PlanError(f"{path}: {arm} has no `path` string")
        if arm in seen:
            raise PlanError(f"{path}: {arm} appears twice")
        seen.add(arm)
        tp = entry.get("tp", 1)
        if tp not in TP_VALUES:
            raise PlanError(f"{path}: {arm} has tp={tp!r}; expected one of {TP_VALUES}")
        pp = entry.get("pp", 1)
        if not isinstance(pp, int) or isinstance(pp, bool) or pp < 1:
            raise PlanError(f"{path}: {arm} has pp={pp!r}; expected a positive integer")
        env = entry.get("env") or {}
        if not isinstance(env, dict):
            raise PlanError(f"{path}: {arm} has a non-object `env`")
        risky = bool(entry.get("memory_risky", False))
        allow, window = waiver(f"{path}: {arm}", entry, risky)
        out.append({"arm": arm, "path": recipe, "tp": int(tp), "pp": pp,
                    "nodes": int(tp) * pp, "env": dict(env), "memory_risky": risky,
                    "exclude_hosts": [], "allow_hosts": allow, "window": window})
    return out


def build(
    entries: list[dict[str, Any]],
    verdicts: dict[str, Verdict],
    measured: dict[str, str],
    root: str | Path = ".",
) -> tuple[list[str], list[str]]:
    """(arm order, explanation lines). Every exclusion is named, so "not planned" is checkable.

    A recipe the tree records as a measured negative is excluded by the skip source, never by a
    remembered list -- that is what printed `skip:` lines are for. An arm with a measurement
    already on disk is excluded too, and says where its numbers are.
    """
    order: list[str] = []
    lines: list[str] = []
    for entry in entries:
        arm = entry["arm"]
        missing = Path(root) / entry["path"]
        if not missing.is_file():
            raise PlanError(f"{arm}: {entry['path']} does not exist under {root}")
        order.append(arm)
        if arm in verdicts:
            lines.append(skip_line(verdicts[arm]))
        elif arm in measured:
            lines.append(f"measured: {arm} ({measured[arm]})")
    return order, lines


def next_assignment(
    order: list[str],
    arms: dict[str, dict[str, Any]],
    free_hosts: list[str],
    retries: int = 0,
    excluded_hosts: tuple[str, ...] = MEMORY_RISKY_EXCLUDED_HOSTS,
) -> tuple[str, tuple[str, ...]] | None:
    """The next arm and the hosts it takes, or None when no pending arm fits.

    An arm is eligible while it is pending, or failed with retries left. It must have no reap
    outstanding: a host may still be running the arm's own container, and handing the arm out
    again while that is unverified is how a second boot lands on a held port. A TP=2 arm takes two
    hosts in one lease -- `tools/run-arm.sh` is launched once with both, so one worker owns the pair.

    Hosts keep the declared order except that excluded ones come last, so a shape with room on
    the safe hosts never takes the head whatever its `nodes`. A memory-risky shape that is short
    on free safe hosts waits instead of spilling onto one; the plan has already refused it by
    name when the declared set could never cover it, and truncating onto the excluded host is the
    2026-11-10 defect. The one way a risky shape takes an excluded host is that boot's own
    declaration (`allow_hosts` + `window`), and even then it is tried only after every safe host
    -- the director proves the host's guardrails before the lease. A risky shape still runs when
    the safe hosts cover it: a ~20 GiB/rank quartet on five safe hosts is placed, never refused.
    """
    free = list(free_hosts)
    for arm in order:
        record = arms.get(arm)
        if record is None:
            raise PlanError(f"{arm} is in the plan order but has no arm record")
        status = record["status"]
        eligible = status == PENDING or (status == FAILED and record["failures"] <= retries)
        if not eligible or status == SKIPPED or status == LEASED:
            continue
        if record["needs_reap"]:
            continue
        need = int(record.get("nodes") or record["tp"])
        barred_for_arm = tuple(excluded_hosts) + tuple(record.get("exclude_hosts") or ())
        allow = tuple(record.get("allow_hosts") or ())
        safe = [host for host in free if not barred(host, barred_for_arm)]
        if record.get("memory_risky"):
            waived = [host for host in free
                      if barred(host, barred_for_arm) and barred(host, allow)]
            if len(safe) + len(waived) < need:
                continue
            return arm, tuple((safe + waived)[:need])
        if len(free) < need:
            continue
        tail = [host for host in free if barred(host, barred_for_arm)]
        return arm, tuple((safe + tail)[:need])
    return None