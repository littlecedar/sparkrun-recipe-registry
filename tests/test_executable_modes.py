"""Scripts the repo runs directly must be committed executable.

Measured 2026-11-10: `tools/run-arm.sh` was committed mode 100644 (d6fae84 dropped the bit while
editing content) and the campaign director refused to restart with "no executable per-arm
executor" until a session ran `chmod +x` locally. A local chmod is not a fix: the pushed artifact
stayed unrunnable for everyone else, and `bash -n`, `py_compile` and the behavioural suite all pass
on a non-executable file. So the mode is read from git's record of the commit
(`git ls-tree HEAD`), never from the worktree: `os.access(..., X_OK)` would have passed through the
whole incident because the local chmod sets the bit it reads.

The list is only what the repo invokes as `argv[0]`, which is a small, evidenced set -- not every
`.sh` (mod scripts are run through `bash -s`, and python tools through an interpreter).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Directly executed path -> why. `git ls-tree` must record 100755 for each.
DIRECTLY_INVOKED = {
    "tools/run-arm.sh":
        "the campaign worker runs it as the executor (sparkrun_campaign/worker.py builds "
        "[executor, recipe, hosts]) and tools/README.md tells operators to run it",
    "tools/queue-drip.py":
        "tools/README.md and its own usage run it directly (`tools/queue-drip.py --once`)",
}


def committed_modes(repo: Path, paths: list[str],
                    env: dict[str, str] | None = None) -> dict[str, str] | None:
    """path -> mode string from git's record of HEAD; None when git/HEAD is unavailable.

    `env` lets a caller point at another repository (push-gate runs this from an archive tree and
    passes GIT_DIR). A scratch-repo caller must pass an env with the GIT_* variables stripped, or
    its `git` commands speak to the repository this process was launched in.
    """
    git = shutil.which("git")
    if git is None:
        return None
    out = subprocess.run([git, "ls-tree", "-r", "HEAD", "--", *paths], cwd=str(repo),
                         env=os.environ if env is None else env,
                         capture_output=True, text=True)
    if out.returncode != 0:
        return None
    modes = {}
    for line in out.stdout.splitlines():
        meta, _, path = line.partition("\t")
        fields = meta.split()
        if len(fields) == 3:
            modes[path] = fields[0]
    return modes


def non_executable(modes: dict[str, str]) -> dict[str, str]:
    return {p: mode for p, mode in modes.items() if mode != "100755"}


def mode_failure(repo: Path, paths: list[str],
                 env: dict[str, str] | None = None) -> str:
    """The refusal text, or "" when every path is committed executable."""
    modes = committed_modes(repo, paths, env)
    if modes is None:
        return ""
    missing = [p for p in paths if p not in modes]
    if missing:
        return f"not tracked at HEAD: {missing}"
    wrong = non_executable(modes)
    if wrong:
        return ("committed mode is not executable: "
                + ", ".join(f"{p} is {mode}" for p, mode in sorted(wrong.items()))
                + " -- `git update-index --chmod=+x <path>` and commit the index change")
    return ""


class CommittedModes(unittest.TestCase):
    def test_directly_invoked_scripts_are_committed_executable(self):
        reason = mode_failure(REPO_ROOT, list(DIRECTLY_INVOKED))
        if reason == "" and committed_modes(REPO_ROOT, list(DIRECTLY_INVOKED)) is None:
            self.skipTest(f"not a git checkout at {REPO_ROOT} (or no git), so no mode to read")
        self.assertEqual(reason, "")

    def test_a_committed_100644_script_is_refused(self):
        """Negative control: the checker must fire on the mode d6fae84 actually recorded."""
        git = shutil.which("git")
        if git is None:
            self.skipTest("no git on this host")
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            # No GIT_DIR/GIT_WORK_TREE leaked in from a parent (push-gate sets both): this
            # scratch repository must be the one these commands write.
            env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
            script = repo / "run-arm.sh"
            script.write_text("#!/bin/sh\ntrue\n", encoding="utf-8")
            ident = ["-c", "user.email=gate@example.invalid", "-c", "user.name=gate"]
            for argv in (["init", "-q"], ["add", "run-arm.sh"],
                         ["update-index", "--chmod=-x", "run-arm.sh"],
                         [*ident, "commit", "-q", "-m", "non-executable"]):
                subprocess.run([git, *argv], cwd=str(repo), check=True, env=env,
                               capture_output=True, text=True)
            self.assertIn("run-arm.sh is 100644",
                          mode_failure(repo, ["run-arm.sh"], env))

            subprocess.run([git, "update-index", "--chmod=+x", "run-arm.sh"], cwd=str(repo),
                           check=True, capture_output=True, env=env, text=True)
            subprocess.run([git, *ident, "commit", "-q", "-m", "executable"], cwd=str(repo),
                           check=True, capture_output=True, text=True, env=env)
            self.assertEqual(mode_failure(repo, ["run-arm.sh"], env), "")

    def test_the_list_carries_its_reason(self):
        """A path added without a reason is a list nobody can re-derive."""
        for path, reason in DIRECTLY_INVOKED.items():
            self.assertTrue(reason, path)
        self.assertTrue(DIRECTLY_INVOKED, "an empty guard checks nothing")


if __name__ == "__main__":
    unittest.main()
