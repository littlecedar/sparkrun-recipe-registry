"""The `campaign` wrapper: the exact director argv, its defaults, and its human errors.

Each case runs the real wrapper with a stub `uv` first on `PATH`, so what is asserted is the argv a
live run would take, without a venv, a fleet, or the director itself. The live host set is read from
the unit's untracked EnvironmentFile, so the fixtures use synthetic hostnames, never addresses.
`systemctl` is stubbed too: the real user bus must never leak a live root into a test.
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
DIRECTOR = ["run", "--project", str(CAMPAIGN), "--frozen", "python", "-B", "-m",
            "sparkrun_campaign.director"]
# /bin/sh is dash on CI: no bashisms in the stub. PWD is where uv ran; PYTHONPATH is what the
# wrapper exported to put the package on sys.path without leaving the caller's cwd.
STUB_UV = """#!/bin/sh
{
  printf 'PWD=%s\\n' "$(pwd)"
  printf 'PYTHONPATH=%s\\n' "${PYTHONPATH:-}"
  printf '%s\\n' "$@"
} > "$UV_LOG"
"""
# No unit on the bus: the wrapper must treat this as absent, never as an empty --root.
STUB_SYSTEMCTL_ABSENT = "#!/bin/sh\nexit 1\n"
STUB_SYSTEMCTL = """#!/bin/sh
printf '%s\\n' "$SYSTEMCTL_EXECSTART"
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
        self._systemctl_absent()
        self.repo = self.home / "src" / "sparkrun-recipe-registry"
        self.env_file = self.home / ".config" / "sparkrun-campaign.env"

    def _systemctl_absent(self) -> None:
        stub = self.bin / "systemctl"
        stub.write_text(STUB_SYSTEMCTL_ABSENT)
        stub.chmod(0o755)

    def _systemctl(self, execstart: str) -> None:
        stub = self.bin / "systemctl"
        stub.write_text(STUB_SYSTEMCTL)
        stub.chmod(0o755)
        self.systemctl_env = execstart

    def _env_file(self, text: str) -> None:
        self.env_file.parent.mkdir(parents=True, exist_ok=True)
        self.env_file.write_text(text)

    def _run(self, *args: str, cwd: str | None = None, **env: str) -> subprocess.CompletedProcess[str]:
        environ = dict(os.environ)
        environ.pop("CAMPAIGN_ROOT", None)
        environ.pop("CAMPAIGN_HOSTS", None)
        environ.update(HOME=str(self.home), PATH=f"{self.bin}:{os.environ['PATH']}",
                       UV_LOG=str(self.log),
                       SYSTEMCTL_EXECSTART=getattr(self, "systemctl_env", ""))
        environ.update(env)
        return subprocess.run([str(WRAPPER), *args], env=environ, cwd=cwd or os.getcwd(),
                              capture_output=True, text=True)

    def _lines(self) -> list[str]:
        return self.log.read_text().splitlines()

    def _pwd(self) -> str:
        first = self._lines()[0]
        self.assertTrue(first.startswith("PWD="), first)
        return first.removeprefix("PWD=")

    def _pythonpath(self) -> str:
        second = self._lines()[1]
        self.assertTrue(second.startswith("PYTHONPATH="), second)
        return second.removeprefix("PYTHONPATH=")

    def _argv(self) -> list[str]:
        return self._lines()[2:]

    def _state(self, root: Path) -> Path:
        root.mkdir(parents=True, exist_ok=True)
        (root / "state.json").write_text("{}")
        return root

    def test_status_defaults_to_the_live_root(self) -> None:
        root = self._state(self.home / "benchmarks" / "h2h-20261107")
        result = self._run("status")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self._argv(), DIRECTOR + ["status", "--root", str(root)])
        self.assertEqual(self._pwd(), os.getcwd())
        self.assertTrue(self._pythonpath().startswith(str(CAMPAIGN)), self._pythonpath())
        self.assertIn("falling back", result.stderr)

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

    def test_status_reads_the_root_from_the_unit(self) -> None:
        root = self._state(self.tmp / "unit-root")
        self._systemctl(f"ExecStart=/usr/bin/python -m sparkrun_campaign.director serve "
                        f"--root {root} --hosts alpha,beta")
        result = self._run("status")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self._argv(), DIRECTOR + ["status", "--root", str(root)])

    def test_missing_unit_falls_back_to_the_documented_root_and_says_so(self) -> None:
        # A true absence: no systemctl stub and no real one reachable, so only the fallback is left.
        minbin = self.tmp / "minbin"
        minbin.mkdir()
        (minbin / "dirname").symlink_to(shutil.which("dirname"))
        (minbin / "bash").symlink_to(shutil.which("bash"))
        (minbin / "uv").symlink_to(self.bin / "uv")
        root = self._state(self.home / "benchmarks" / "h2h-20261107")
        environ = {k: v for k, v in os.environ.items() if k not in ("CAMPAIGN_ROOT", "CAMPAIGN_HOSTS")}
        environ.update(HOME=str(self.home), PATH=str(minbin), UV_LOG=str(self.log))
        result = subprocess.run([str(WRAPPER), "status"], env=environ, capture_output=True,
                                text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self._argv(), DIRECTOR + ["status", "--root", str(root)])
        self.assertIn(str(root), result.stderr)
        self.assertIn("CAMPAIGN_ROOT", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_leases_lists_with_the_repo_root(self) -> None:
        result = self._run("leases")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self._argv(),
                         DIRECTOR + ["lease", "--list", "--repo-root", str(self.repo)])
        self.assertEqual(self._pwd(), os.getcwd())
        self.assertTrue(self._pythonpath().startswith(str(CAMPAIGN)), self._pythonpath())

    def test_plan_reads_the_hosts_from_the_env_file(self) -> None:
        self._env_file("CAMPAIGN_HOSTS=alpha,beta\n")
        result = self._run("plan", "--manifest", "/tmp/manifest.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self._argv(), DIRECTOR + [
            "plan", "--hosts", "alpha,beta", "--repo-root", str(self.repo),
            "--manifest", "/tmp/manifest.json",
        ])
        self.assertEqual(self._pwd(), os.getcwd())
        self.assertTrue(self._pythonpath().startswith(str(CAMPAIGN)), self._pythonpath())

    def test_a_relative_manifest_resolves_against_the_callers_cwd(self) -> None:
        (self.tmp / "m.json").write_text("{}")
        result = self._run("plan", "--manifest", "./m.json", cwd=str(self.tmp),
                           CAMPAIGN_HOSTS="alpha,beta")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self._pwd(), str(self.tmp))
        self.assertIn("./m.json", self._argv())
        self.assertEqual(self._argv()[-1], "./m.json")

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
        self.assertIn("sparkrun-campaign.service", result.stderr)
        self.assertFalse(self.log.exists())

    def test_the_real_uv_finds_the_director_module_from_the_project(self) -> None:
        # The venv does not install the package: PYTHONPATH, not the cwd, puts it on sys.path.
        if shutil.which("uv") is None:
            self.skipTest("uv is not on PATH")
        environ = dict(os.environ)
        environ["PYTHONPATH"] = str(CAMPAIGN) + (
            f":{environ['PYTHONPATH']}" if environ.get("PYTHONPATH") else "")
        result = subprocess.run(
            ["uv", "run", "--project", str(CAMPAIGN), "--frozen", "python", "-B", "-m",
             "sparkrun_campaign.director", "--help"],
            cwd=CAMPAIGN.parent, env=environ, capture_output=True, text=True,
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
