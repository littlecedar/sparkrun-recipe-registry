"""The `campaign` wrapper: the exact director argv, its defaults, and its human errors.

Each case runs the real wrapper with a stub `uv` first on `PATH`, so what is asserted is the argv a
live run would take, without a venv, a fleet, or the director itself. The live host set is read from
the unit's untracked EnvironmentFile, so the fixtures use synthetic hostnames, never addresses.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

WRAPPER = Path(__file__).resolve().parents[1] / "bin" / "campaign"
CAMPAIGN = WRAPPER.parents[1]
DIRECTOR = ["run", "--project", ".", "--frozen", "python", "-B", "-m",
            "sparkrun_campaign.director"]
# /bin/sh is dash on CI: no bashisms in the stub. The first line is the directory uv ran in.
STUB_UV = """#!/bin/sh
printf 'PWD=%s\\n' "$(pwd)" > "$UV_LOG"
printf '%s\\n' "$@" >> "$UV_LOG"
"""


class WrapperCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        self.log = self.tmp / "uv-argv"
        stub = self.bin / "uv"
        stub.write_text(STUB_UV)
        stub.chmod(0o755)
        self.repo = self.home / "src" / "sparkrun-recipe-registry"
        self.env_file = self.home / ".config" / "sparkrun-campaign.env"

    def _env_file(self, text: str) -> None:
        self.env_file.parent.mkdir(parents=True, exist_ok=True)
        self.env_file.write_text(text)

    def _run(self, *args: str, **env: str) -> subprocess.CompletedProcess[str]:
        environ = dict(os.environ)
        environ.pop("CAMPAIGN_ROOT", None)
        environ.pop("CAMPAIGN_HOSTS", None)
        environ.update(HOME=str(self.home), PATH=f"{self.bin}:{os.environ['PATH']}",
                       UV_LOG=str(self.log))
        environ.update(env)
        return subprocess.run([str(WRAPPER), *args], env=environ, capture_output=True, text=True)

    def _pwd(self) -> str:
        first = self.log.read_text().splitlines()[0]
        self.assertTrue(first.startswith("PWD="), first)
        return first.removeprefix("PWD=")

    def _argv(self) -> list[str]:
        return self.log.read_text().splitlines()[1:]

    def _state(self, root: Path) -> Path:
        root.mkdir(parents=True, exist_ok=True)
        (root / "state.json").write_text("{}")
        return root

    def test_status_defaults_to_the_live_root(self) -> None:
        root = self._state(self.home / "benchmarks" / "h2h-20261107")
        result = self._run("status")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self._argv(), DIRECTOR + ["status", "--root", str(root)])
        self.assertEqual(self._pwd(), str(CAMPAIGN))

    def test_status_is_the_default_with_no_subcommand(self) -> None:
        root = self._state(self.tmp / "elsewhere")
        result = self._run(CAMPAIGN_ROOT=str(root))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self._argv(), DIRECTOR + ["status", "--root", str(root)])

    def test_status_reads_the_root_from_the_env_file(self) -> None:
        root = self._state(self.tmp / "from-file")
        self._env_file(f"CAMPAIGN_ROOT={root}\n")
        result = self._run("status")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self._argv(), DIRECTOR + ["status", "--root", str(root)])

    def test_leases_lists_with_the_repo_root(self) -> None:
        result = self._run("leases")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self._argv(),
                         DIRECTOR + ["lease", "--list", "--repo-root", str(self.repo)])
        self.assertEqual(self._pwd(), str(CAMPAIGN))

    def test_plan_reads_the_hosts_from_the_env_file(self) -> None:
        self._env_file("CAMPAIGN_HOSTS=alpha,beta\n")
        result = self._run("plan", "--manifest", "/tmp/manifest.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self._argv(), DIRECTOR + [
            "plan", "--hosts", "alpha,beta", "--repo-root", str(self.repo),
            "--manifest", "/tmp/manifest.json",
        ])
        self.assertEqual(self._pwd(), str(CAMPAIGN))

    def test_plan_passes_an_override_and_extra_args_through(self) -> None:
        result = self._run("plan", "--manifest", "/tmp/m.json", "--exclude-host", ".30",
                           CAMPAIGN_HOSTS="gamma,delta")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self._argv(), DIRECTOR + [
            "plan", "--hosts", "gamma,delta", "--repo-root", str(self.repo),
            "--manifest", "/tmp/m.json", "--exclude-host", ".30",
        ])

    def test_plan_without_hosts_exits_two(self) -> None:
        result = self._run("plan", "--manifest", "/tmp/m.json")
        self.assertEqual(result.returncode, 2)
        self.assertIn("CAMPAIGN_HOSTS", result.stderr)
        self.assertIn(str(self.env_file), result.stderr)
        self.assertFalse(self.log.exists())

    def test_the_real_uv_finds_the_director_module_from_the_project(self) -> None:
        # The venv does not install the package: only the project cwd puts it on sys.path.
        if shutil.which("uv") is None:
            self.skipTest("uv is not on PATH")
        result = subprocess.run(
            ["uv", "run", "--project", ".", "--frozen", "python", "-B", "-m",
             "sparkrun_campaign.director", "--help"],
            cwd=CAMPAIGN, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_help_lists_the_subcommands_and_overrides(self) -> None:
        result = self._run("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        for word in ("status", "leases", "plan", "log", "CAMPAIGN_ROOT", "CAMPAIGN_HOSTS"):
            self.assertIn(word, result.stdout)
        self.assertFalse(self.log.exists())

    def test_a_missing_root_exits_two_naming_the_path_and_override(self) -> None:
        root = self.tmp / "gone"
        result = self._run("status", CAMPAIGN_ROOT=str(root))
        self.assertEqual(result.returncode, 2)
        self.assertIn(str(root / "state.json"), result.stderr)
        self.assertIn("CAMPAIGN_ROOT", result.stderr)
        self.assertIn("head", result.stderr)
        self.assertFalse(self.log.exists())

    def test_verbose_echoes_the_command(self) -> None:
        root = self._state(self.tmp / "root")
        result = self._run("-v", "status", CAMPAIGN_ROOT=str(root))
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = result.stdout.splitlines()
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0].startswith("# uv run --project "), lines[0])
        self.assertIn("sparkrun_campaign.director", lines[0])
