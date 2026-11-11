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
* the **host memory sampler** (`mem-guard.sh`, the 6.0 GiB `MemAvailable` stop-rule guard a window
  arms) is running, and its argv is quoted.

No check is inferred from another: a single missing probe raises `plan.PlanError` naming the host
and the check, and the director blocks the arm instead of placing it somewhere else.
"""

from __future__ import annotations

from collections.abc import Callable

from . import fleet
from .plan import PlanError

#: Units whose OOM score must protect them. `user@1000.service` is this account's session leader;
#: the BeeGFS trio is what `.30` runs for the whole fleet.
UNITS = ("ssh.service", "NetworkManager.service", "user@1000.service",
         "beegfs-mgmtd.service", "beegfs-meta.service", "beegfs-storage.service")
#: The window's `MemAvailable` guard; its argv names the floor it is watching.
SAMPLER = "mem-guard"

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


def prove(host: str, *, run: Runner = fleet.ssh) -> list[str]:
    """Proof lines for one waived host, or `PlanError` naming the first missing guardrail."""
    proof: list[str] = []

    code, line = _probe(host, "pgrep -a earlyoom", run)
    argv = line.splitlines()[0] if line else ""
    if code != 0 or not argv:
        raise PlanError(f"{host}: earlyoom is not running (pgrep -a earlyoom rc={code}); a "
                        "memory-risky shape may not take this host without it")
    tokens = argv.split()
    memory = _threshold(tokens, "-m", "--mem-percent")
    swap = _threshold(tokens, "-s", "--swap-percent")
    if not memory or not swap:
        raise PlanError(f"{host}: earlyoom argv quotes no memory/swap threshold: {argv!r}")
    for term, value in (("memory", memory), ("swap", swap)):
        try:
            disabled = int(value.split(",")[0]) <= 0
        except ValueError:
            raise PlanError(f"{host}: earlyoom {term} threshold is not a number: {value!r}")
        if disabled:
            raise PlanError(f"{host}: earlyoom {term} threshold is {value!r}, which disables the "
                            "kill; a disabled guard is not a guard")
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

    code, line = _probe(host, f"pgrep -af {SAMPLER}", run)
    sampler = line.splitlines()[0] if line else ""
    if code != 0 or not sampler:
        raise PlanError(f"{host}: host memory sampler ({SAMPLER}) is not armed "
                        f"(pgrep -af {SAMPLER} rc={code}); arm the window's stop-rule guard first")
    proof.append(f"memory sampler: {sampler}")

    return proof
