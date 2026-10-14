"""Guards for the `install-kolibri-plugin` mod.

Run:
    python3 -m unittest discover -s tests -v

Stdlib-only, deliberate (AGENTS.md: "tools/ and tests/ are stdlib-only, on
purpose") -- this must run on a head node, in a container, and on a laptop.

Why these exist. `MOD_CACHEDIR` (`/cache/runtime`) is a PERSISTENT cache mount,
but the mod's `pip install` targets the container's EPHEMERAL layer, which is
empty on every relaunch. A skip-install decision keyed on the persistent marker
alone therefore boots a second launch without the plugin: measured 2026-10-13 on
`.35`, the second boot skipped on a surviving marker and died
`ModuleNotFoundError: No module named 'aleph_alpha_inference'` in
`launch_inference`. The guards execute `run.sh` against temp dirs with STUBBED
`pip` and `python3` (no test may install a package, and it must run anywhere) and
assert the skip is gated on a LIVE import:

  * happy path: no marker -> install, verify, marker written, rc 0;
  * idempotence: marker + live module -> the second run skips the install;
  * NEGATIVE CONTROL (the defect): marker present but the module absent from the
    live layer -> the mod MUST re-install, not skip. The pre-fix marker-only
    logic satisfies a naive "marker => skip" test vacuously, so a guard that only
    checked that would never have caught the outage (see NegativeControls);
  * fail-closed: an install that leaves the module unimportable exits 1.

The stub `python3`/`pip` read `$CACHEDIR` (exported by the mod) and emulate the
ephemeral container layer as one state file: `pip install` writes
`$CACHEDIR/ephemeral-installed`, and the import check succeeds iff that file
names the pinned version.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MOD_DIR = REPO_ROOT / "recipes" / "explore" / "mods" / "install-kolibri-plugin"
# Overridable so the fail-before demonstration can point the same guards at a
# pre-fix copy of run.sh (see NegativeControls.test_prefix_logic_skips_...).
MOD_SCRIPT = Path(os.environ.get("KOLIBRI_MOD_SCRIPT", MOD_DIR / "run.sh"))
PLUGIN_VERSION = "1.0.0"
MARKER_NAME = "mod-install-kolibri-plugin.installed"

PIP_STUB = """#!/bin/bash
set -eu
ver=""
for a in "$@"; do
  case "${a}" in
    aleph-alpha-inference==*) ver="${a#*==}" ;;
  esac
done
printf '%s' "${ver}" > "${CACHEDIR}/ephemeral-installed"
printf 'pip %s\\n' "${ver}" >> "${CACHEDIR}/pip-calls"
echo "Successfully installed aleph-alpha-inference-${ver}"
"""

PYTHON_STUB = """#!/bin/bash
set -eu
ver=""
[[ -f "${CACHEDIR}/ephemeral-installed" ]] && ver="$(cat "${CACHEDIR}/ephemeral-installed")"
if [[ "${ver}" != "1.0.0" ]]; then
  echo "ModuleNotFoundError: No module named 'aleph_alpha_inference'" >&2
  exit 1
fi
echo "plugin OK: ['aleph_alpha_inference']"
"""


def _write_stub(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


def _run_mod(env_extra: dict[str, str], root: Path, script: Path | None = None, timeout: int = 60) -> subprocess.CompletedProcess:
    workdir = root / "mod"
    workdir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(script or MOD_SCRIPT, workdir / "run.sh")
    stubdir = root / "stub-bin"
    stubdir.mkdir(exist_ok=True)
    _write_stub(stubdir / "pip", PIP_STUB)
    _write_stub(stubdir / "python3", PYTHON_STUB)
    env = {k: v for k, v in os.environ.items() if not k.startswith("MOD_")}
    env["PATH"] = f"{stubdir}:{env.get('PATH', '/usr/bin:/bin')}"
    env.update(env_extra)
    return subprocess.run(
        ["bash", str(workdir / "run.sh")],
        capture_output=True, text=True, timeout=timeout, env=env, cwd=str(workdir),
    )


def _base_env(cache: Path, **extra: str) -> dict[str, str]:
    env = {
        "MOD_CACHEDIR": str(cache),
        "MOD_LOGDIR": str(cache / "modlogs"),
    }
    env.update(extra)
    return env


def _marker(cache: Path) -> Path:
    return cache / MARKER_NAME


def _pip_calls(cache: Path) -> int:
    f = cache / "pip-calls"
    return len(f.read_text(encoding="utf-8").splitlines()) if f.exists() else 0


def _executable_text() -> str:
    """run.sh minus whole-line `#` comments (the prose NAMES the defect)."""
    return "\n".join(
        ln for ln in MOD_SCRIPT.read_text(encoding="utf-8").splitlines()
        if not ln.lstrip().startswith("#")
    )


class ModShape(unittest.TestCase):
    def test_mod_is_executable_with_harness(self):
        self.assertTrue(MOD_SCRIPT.is_file(), "missing %s" % MOD_SCRIPT)
        self.assertTrue(MOD_SCRIPT.stat().st_mode & 0o111, "%s not executable" % MOD_SCRIPT)
        src = MOD_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("set -euo pipefail", src)
        self.assertIn("SPDX-License-Identifier: AGPL-3.0-or-later", src)
        self.assertIn("reown()", src, "mod-template harness missing reown()")
        self.assertTrue((MOD_DIR / "README.md").is_file(), "a new mod ships a README.md")

    def test_skip_gate_couples_the_marker_to_a_live_import(self):
        """The idempotence condition must require the live check, not the marker."""
        text = _executable_text()
        self.assertIn("plugin_installed_at_version()", text, "live import check missing")
        self.assertRegex(
            text,
            r'if \[\[ -f "\$\{MARKER\}" \]\].*grep -qx "\$\{PLUGIN_VERSION\}" "\$\{MARKER\}"'
            r'.*plugin_installed_at_version; then',
            "skip gate must AND the marker with a live import check",
        )


class InstallAndVerify(unittest.TestCase):
    def test_first_run_installs_verifies_and_writes_the_marker(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cache = root / "cache"
            cache.mkdir()
            r = _run_mod(_base_env(cache), root)
            self.assertEqual(r.returncode, 0, (r.stdout, r.stderr))
            self.assertIn("Installing aleph-alpha-inference==", r.stdout)
            self.assertEqual(_pip_calls(cache), 1, "pip not invoked exactly once")
            self.assertEqual((cache / "ephemeral-installed").read_text(), PLUGIN_VERSION)
            self.assertTrue(_marker(cache).is_file(), "marker not written")
            self.assertEqual(_marker(cache).read_text().strip(), PLUGIN_VERSION)

    def test_second_run_skips_the_install_when_the_module_is_live(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cache = root / "cache"
            cache.mkdir()
            first = _run_mod(_base_env(cache), root)
            self.assertEqual(first.returncode, 0, first.stderr)
            second = _run_mod(_base_env(cache), root)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertIn("skipping pip install", second.stdout)
            self.assertEqual(_pip_calls(cache), 1, "a live marker must not re-run pip")


class NegativeControls(unittest.TestCase):
    """A guard that cannot fail proves nothing. These reproduce the 2026-10-13
    outage shape: a marker that outlived its module."""

    def test_stale_marker_alone_does_not_skip_the_install(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cache = root / "cache"
            cache.mkdir()
            first = _run_mod(_base_env(cache), root)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertTrue(_marker(cache).is_file())
            # The relaunch's ephemeral layer is empty while the marker survives.
            (cache / "ephemeral-installed").unlink()
            second = _run_mod(_base_env(cache), root)
            self.assertEqual(second.returncode, 0, (second.stdout, second.stderr))
            self.assertNotIn(
                "skipping pip install", second.stdout,
                "a stale marker must NOT let the mod skip the install",
            )
            self.assertEqual(_pip_calls(cache), 2, "the mod must re-install on a stale marker")

    def test_fail_closed_when_the_install_leaves_the_module_absent(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cache = root / "cache"
            cache.mkdir()
            _marker(cache).write_text(PLUGIN_VERSION + "\n")  # stale marker
            workdir = root / "mod"
            workdir.mkdir()
            shutil.copy2(MOD_SCRIPT, workdir / "run.sh")
            stubdir = root / "stub-bin"
            stubdir.mkdir(exist_ok=True)
            # A pip that reports success but installs nothing.
            _write_stub(stubdir / "pip", "#!/bin/bash\nexit 0\n")
            _write_stub(stubdir / "python3", PYTHON_STUB)
            env = {k: v for k, v in os.environ.items() if not k.startswith("MOD_")}
            env["PATH"] = f"{stubdir}:{env.get('PATH', '/usr/bin:/bin')}"
            env.update(_base_env(cache))
            r = subprocess.run(
                ["bash", str(workdir / "run.sh")],
                capture_output=True, text=True, timeout=60, env=env, cwd=str(workdir),
            )
            self.assertEqual(r.returncode, 1, (r.stdout, r.stderr))
            self.assertIn("FATAL", r.stdout)

    def test_prefix_logic_skips_on_a_stale_marker(self):
        """The pre-fix gate passes a naive 'marker => skip' test vacuously.

        Revert the gate condition to marker-only (and its skip message) and the
        stale-marker scenario takes the skip branch without a live check: pip is
        never invoked. That is exactly what a guard keyed on the marker would
        bless, so this control proves the guard above has discriminating power.
        """
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cache = root / "cache"
            cache.mkdir()
            prefix = root / "prefix-run.sh"
            text = MOD_SCRIPT.read_text(encoding="utf-8")
            reverted = text.replace(
                ' && plugin_installed_at_version; then', '; then', 1
            ).replace(
                "records ${PLUGIN_VERSION} and the plugin imports — skipping pip install",
                "already records ${PLUGIN_VERSION} — skipping pip install",
                1,
            )
            self.assertNotEqual(reverted, text, "gate condition not found to revert")
            prefix.write_text(reverted, encoding="utf-8")
            _marker(cache).write_text(PLUGIN_VERSION + "\n")  # stale marker, no module
            _run_mod(_base_env(cache), root, script=prefix)
            self.assertEqual(_pip_calls(cache), 0, "pre-fix logic must skip on a stale marker")
            self.assertFalse((cache / "ephemeral-installed").exists())


class RecipeWiring(unittest.TestCase):
    def test_recipe_lists_the_mod(self):
        recipe = REPO_ROOT / "recipes" / "explore" / "kolibri-1-78b-fp8-vllm.yaml"
        text = recipe.read_text(encoding="utf-8")
        self.assertIn("mods/install-kolibri-plugin", text)


if __name__ == "__main__":
    unittest.main()
