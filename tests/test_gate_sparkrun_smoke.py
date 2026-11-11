"""The gate's recipe-validate step must be honest about *why* it skipped.

Measured 2026-11-09, gate run 42580641156 on `0e7b6cc` (a board-only commit): the runner's
`sparkrun` console script existed while its package did not, so `command -v sparkrun` passed, the
step ran, and `ModuleNotFoundError: No module named 'sparkrun'` reddened main for a commit that
touched no recipe. Presence was mistaken for an install.

The tests run the workflow's own `run:` body (extracted from `gate.yml`, so the shipped step is
what is measured) against stub binaries: absent is the one tolerated state and prints SKIPPED;
present-but-broken exits non-zero and quotes the install's message; an invalid recipe still fails.

Stdlib only, no network: the install attempts inside the step are unreachable because the test
PATH carries no `uv` or `python3`.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GATE = REPO_ROOT / ".github" / "workflows" / "gate.yml"

#: POSIX: the repo has reddened CI seven times on bash-isms behind a `#!/bin/sh` stub.
PRESENT = """#!/bin/sh
while [ "$#" -gt 0 ]; do
  case "$1" in
    --version)
      printf '%s\n' "sparkrun, version 0.4.2"
      if [ "${STUB_VERSION_OK:-1}" = 0 ]; then
        printf '%s\n' "ModuleNotFoundError: No module named 'sparkrun'" >&2
        exit 1
      fi
      exit 0
      ;;
    recipe)
      exit "${STUB_RECIPE_RC:-0}"
      ;;
  esac
  shift
done
exit 0
"""


def run_body(name_fragment: str) -> str:
    """The `run: |` body of the step whose `- name:` line contains `name_fragment`."""
    lines = GATE.read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines)
                 if line.strip().startswith("- name:") and name_fragment in line)
    run = next(k for k in range(start, len(lines)) if lines[k].strip() == "run: |")
    indent = len(lines[run]) - len(lines[run].lstrip()) + 2
    body = []
    for line in lines[run + 1:]:
        if line.strip() and len(line) - len(line.lstrip()) < indent:
            break
        body.append(line[indent:] if line.strip() else "")
    return "\n".join(body)


class Step(unittest.TestCase):
    def script(self) -> str:
        body = run_body("Validate recipes")
        self.assertIn("recipes/*/*.yaml", body, "the step body was not extracted")
        return body

    def run_step(self, stubs: dict[str, str], recipe_rc: int = 0,
                 version_ok: bool = True) -> tuple[int, str, Path]:
        bash = shutil.which("bash")
        if bash is None:
            self.skipTest("no bash on this host")
        tmpdir = tempfile.TemporaryDirectory(prefix="gate-smoke-")
        self.addCleanup(tmpdir.cleanup)
        tmp = Path(tmpdir.name)
        bins = tmp / "bin"
        bins.mkdir()
        # The step shells out to `mkdir`; everything else on PATH would let it reach the network.
        (bins / "mkdir").symlink_to(shutil.which("mkdir"))
        for name, text in stubs.items():
            path = bins / name
            path.write_text(text)
            path.chmod(0o755)
        (tmp / "recipes" / "x").mkdir(parents=True)
        (tmp / "recipes" / "x" / "arm.yaml").write_text("runtime: vllm\n", encoding="utf-8")
        env = {
            "PATH": str(bins),
            "HOME": str(tmp / "home"),
            "SPARKRUN_HOME": str(tmp / "sprun"),
            "STUB_RECIPE_RC": str(recipe_rc),
            "STUB_VERSION_OK": "1" if version_ok else "0",
        }
        out = subprocess.run([bash, "-c", self.script()], cwd=tmp, env=env,
                             capture_output=True, text=True, timeout=60)
        return out.returncode, out.stdout + out.stderr, tmp

    def test_a_broken_install_reddens_the_step_with_its_own_message(self):
        rc, printed, _tmp = self.run_step({"sparkrun": PRESENT}, version_ok=False)
        self.assertNotEqual(rc, 0, f"a broken install passed the gate: {printed}")
        self.assertIn("present but not runnable", printed)
        self.assertIn("ModuleNotFoundError: No module named 'sparkrun'", printed,
                      "the install's own message is not quoted")

    def test_an_absent_sparkrun_is_the_tolerated_skip(self):
        rc, printed, _tmp = self.run_step({})
        self.assertEqual(rc, 0, f"the tolerated absence failed the gate: {printed}")
        self.assertIn("SKIPPED: sparkrun not installable in CI", printed)

    def test_a_runnable_install_validates_every_recipe(self):
        rc, printed, _tmp = self.run_step({"sparkrun": PRESENT})
        self.assertEqual(rc, 0, printed)
        self.assertIn("plain validate passed for every recipes/*/*.yaml", printed)

    def test_an_invalid_recipe_still_fails(self):
        rc, printed, _tmp = self.run_step({"sparkrun": PRESENT}, recipe_rc=1)
        self.assertNotEqual(rc, 0, f"an invalid recipe passed: {printed}")


if __name__ == "__main__":
    unittest.main()
