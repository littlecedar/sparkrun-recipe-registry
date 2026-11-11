"""The head-host lease gate: what a memory-risky shape must prove before it may take an excluded host.

Owner ruling 2026-11-11 (#2): the `.30` exclusion is waivable only inside an explicitly declared
window, named per boot, and only when the guardrails are proven **at lease time**. The checks are
read-only probes of the host, taken by the director before the lease record is written:

* **earlyoom** is running, and its argv quotes both threshold terms -- the live pair is quoted
  verbatim, because the running process is the policy; a dry-run report is the documented
  alternative in the register and this reads the stronger source.
* **`OOMScoreAdjust`** is negative on every unit whose death costs the head its access or the pool
  its server: `ssh`, `NetworkManager`, `user@1000`, and the BeeGFS mgmtd/meta/storage units. A
  non-negative value is the default, not a guard, so it is a refusal.
* the **window can arm its guard** at the only moment arming is possible: `mem-guard.sh` exists and
  is executable under the window's own directory (`~/benchmarks/<window>/`). The guard must carry
  the boot's own task id, so the executor arms it after the launch resolves that id and before
  readiness; lease time cannot see a process that does not exist yet, and a running stale or foreign
  guard proves nothing (measured 2026-11-11: eleven dead-window guards on `.30`).

No check is inferred from another: a single missing probe raises `plan.PlanError` naming the host
and the check, and the director blocks the arm instead of placing it somewhere else.
"""

from __future__ import annotations

import re
import shlex
from collections.abc import Callable

from . import fleet
from .plan import PlanError

#: Units whose OOM score must protect them. `user@1000.service` is this account's session leader;
#: the BeeGFS trio is what `.30` runs for the whole fleet.
UNITS = ("ssh.service", "NetworkManager.service", "user@1000.service",
         "beegfs-mgmtd.service", "beegfs-meta.service", "beegfs-storage.service")
#: The guard script the window's executor arms after the launch resolves its task id.
GUARD = "mem-guard.sh"
#: A window is a single directory name, never a path: it becomes `~/benchmarks/<window>/`.
WINDOW_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")

Runner = Callable[[str, str], tuple[int, str]]


def _probe(host: str, script: str, run: Runner) -> tuple[int, str]:
    code, text = run(host, script)
    return code, (text or "").strip()


def _threshold(tokens: list[str], short: str, long: str) -> str:
    """The value after `short`/`long` in an argv, or ""; earlyoom's own spelling is the policy."""
    for index, token in enumerate(tokens[:-1]):
        if token in (short, long):
            return tokens[index + 1]
    return ""


def _enabled(value: str) -> bool:
    """earlyoom treats a zero term as disabled; a disabled term is not a guard."""
    return int(value.split(",")[0]) > 0


def prove(host: str, *, window: str = "", run: Runner = fleet.ssh) -> list[str]:
    """Proof lines for one waived host, or `PlanError` naming the first missing guardrail."""
    proof: list[str] = []

    code, text = _probe(host, "pgrep -a earlyoom", run)
    candidates: list[tuple[str, str, str]] = []
    for raw in text.splitlines():
        tokens = raw.split()
        memory = _threshold(tokens, "-m", "--mem-percent")
        swap = _threshold(tokens, "-s", "--swap-percent")
        if memory and swap:
            candidates.append((raw.strip(), memory, swap))
    if not candidates:
        if code != 0 or not text:
            raise PlanError(f"{host}: earlyoom is not running (pgrep -a earlyoom rc={code}); a "
                            "memory-risky shape may not take this host without it")
        raise PlanError(f"{host}: no running earlyoom quotes both thresholds (a --dryrun process "
                        f"has none): {text.splitlines()!r}")
    argv = ""
    for raw, memory, swap in candidates:
        try:
            enabled = _enabled(memory) and _enabled(swap)
        except ValueError:
            raise PlanError(f"{host}: earlyoom argv is not numeric: {raw!r}")
        if enabled:
            argv = raw
            break
    if not argv:
        raise PlanError(f"{host}: every running earlyoom quotes a threshold that disables the "
                        f"kill: {[raw for raw, _, _ in candidates]!r}")
    proof.append(f"earlyoom argv: {argv}")

    for unit in UNITS:
        code, value = _probe(host, f"systemctl show -p OOMScoreAdjust --value {unit}", run)
        try:
            score = int(value.splitlines()[0])
        except (IndexError, ValueError):
            raise PlanError(f"{host}: OOMScoreAdjust unreadable on {unit} "
                            f"(rc={code}, output {value!r}); the unit's own score is the guard")
        if score >= 0:
            raise PlanError(f"{host}: OOMScoreAdjust on {unit} is {score}, not negative; "
                            "the unit would lose the OOM race this gate exists to prevent")
        proof.append(f"OOMScoreAdjust {unit} = {score}")

    window = window.strip()
    if not window:
        raise PlanError(f"{host}: no declared window name; the guard script path cannot be "
                        "resolved")
    if WINDOW_NAME.fullmatch(window) is None:
        raise PlanError(f"{host}: window {window!r} is not a directory name; declare the "
                        "window's own directory (letters, digits, dot, underscore, dash)")
    script = (f'p="$HOME/benchmarks"/{shlex.quote(window)}/{GUARD}; '
              'if [ -x "$p" ]; then printf "%s\\n" "$p"; '
              'else printf "missing %s\\n" "$p"; exit 1; fi')
    code, text = _probe(host, script, run)
    found = text.splitlines()[0] if text else ""
    if code != 0 or not found:
        raise PlanError(f"{host}: window {window!r} has no executable guard script at "
                        f"~/benchmarks/{window}/{GUARD} (probe rc={code}, "
                        f"output {found or 'empty'})")
    proof.append(f"guard script: {found}")

    return proof
