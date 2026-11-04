"""Docker facts about the fleet, and removal of only the arm's own containers.

Every function takes the ssh runner as a parameter (`run=ssh`), so the parsing and the refusal
rules are testable without a node and the only code that touches hardware is one ssh call.

Three rules come from measured incidents rather than taste:

* `docker ps -a --filter name=<task>` is asked over **every host the arm was given**, never the API
  rank alone. On 2026-11-04 a watchdog-reaped TP=2 arm left rank 1 running on the second host 39 s
  after `sparkrun stop`, and the arm still reported rc=0 because only rank 0 was checked.
* A removal names a container parsed from the arm's own `sparkrun.recipe` label **and** matches the
  launcher's naming grammar; no list expansion, no `xargs`, no prune. `docker rm -f $(docker ps -aq)`
  deleted a peer's containers on a shared node on 2026-10-22 and must never be expressible here.
* `sparkrun stop <task>` is tried first, because it also releases the launcher's resource claim;
  `docker rm -f` is the fallback for a survivor. Only when `sparkrun` itself is unusable (no CLI on
  this host) does the fallback carry the removal alone.
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
from collections.abc import Callable

#: (host, shell script) -> (returncode, stdout); tests pass a recording fake.
Runner = Callable[[str, str], tuple[int, str]]
#: (task id) -> None; `sparkrun stop` on the head.
Stopper = Callable[[str], None]

#: The launcher's container names carry the task id and the rank: `sparkrun_<task>_solo` for TP=1,
#: `sparkrun_<task>_node_<n>` for a multi-rank launch. Anchored, because a substring match on a task
#: id can name a different task whose id contains ours.
CONTAINER = re.compile(r"^sparkrun_(?P<task>[A-Za-z0-9][A-Za-z0-9_.-]*)_(?:solo|node_\d+)$")
#: The label `tools/run-arm.sh` already uses to recognise its own leftovers.
LABEL = "sparkrun.recipe"
#: `run-arm.sh` hardcodes the same login for its own probes.
SSH_USER = "red"


def ssh(host: str, script: str, timeout: float = 15.0) -> tuple[int, str]:
    """Run a shell script on one host. A failed probe returns a non-zero rc, never an empty success."""
    try:
        result = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", f"{SSH_USER}@{host}", script],
            capture_output=True, text=True, timeout=timeout, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return 2, ""
    return result.returncode, result.stdout.strip()


def list_script(recipe: str) -> str:
    """The probe: every container, running or not, that was launched from this recipe path."""
    return (
        "docker ps -a --filter "
        + shlex.quote(f"label={LABEL}={recipe}")
        + " --format '{{.Names}}'"
    )


def names(text: str) -> list[str]:
    """Container names from a `--format '{{.Names}}'` listing."""
    return [line.strip() for line in text.splitlines() if line.strip()]


def is_arm_container(name: str) -> bool:
    return CONTAINER.match(name) is not None


def task_id(name: str) -> str | None:
    """`sparkrun_<task>_node_1` -> `<task>`; None when the name is not the launcher's shape."""
    found = CONTAINER.match(name)
    return found.group("task") if found else None


def leftovers(hosts: list[str], recipe: str, run: Runner = ssh) -> list[tuple[str, str]]:
    """(host, container) for this arm's containers still present on any of `hosts`."""
    script = list_script(recipe)
    out: list[tuple[str, str]] = []
    for host in hosts:
        code, text = run(host, script)
        if code != 0:
            # A failed probe must not read as "clean": that is the difference between a green
            # leftover gate and a survivor nobody looked for.
            raise OSError(f"cannot list containers on {host} (rc={code})")
        out.extend((host, name) for name in names(text) if is_arm_container(name))
    return out


def stop_task(task: str, timeout: float = 120.0) -> None:
    """Ask the launcher to stop one task; a missing CLI is not an error, the fallback handles it."""
    try:
        _ = subprocess.run(["sparkrun", "stop", task], capture_output=True, text=True,
                           timeout=timeout, check=False)
    except (OSError, subprocess.SubprocessError):
        pass


def reap(
    hosts: list[str], recipe: str, run: Runner = ssh, stop: Stopper = stop_task
) -> dict[str, list[tuple[str, str]]]:
    """Remove every container this arm left behind, then verify on every host.

    Returns `found` (what was there), `removed` (what a removal command accepted) and `after` (the
    verification probe -- the only field a caller may read as "clean"). An unverifiable host raises,
    because the campaign must not record "no leftover" for a host it could not ask.
    """
    found = leftovers(hosts, recipe, run)
    tasks = {name_task for _, name in found if (name_task := task_id(name)) is not None}
    for task in sorted(tasks):
        stop(task)
    removed: list[tuple[str, str]] = []
    for host, name in found:
        code, _ = run(host, f"docker rm -f {shlex.quote(name)}")
        if code == 0:
            removed.append((host, name))
    return {"found": found, "removed": removed, "after": leftovers(hosts, recipe, run)}


def describe(found: list[tuple[str, str]]) -> str:
    return ", ".join(f"{name} on {host}" for host, name in found) or "none"


def default_repo_root() -> str:
    """The registry checkout this package lives in: `campaign/sparkrun_campaign/fleet.py` -> root."""
    return str(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))