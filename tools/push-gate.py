#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The pre-push gate: the checks that made six pushes land on an already-red gate.

Why this exists.  On 2026-11-08 `gate` runs #1205-#1210 were six consecutive red
pushes to `main`: five carried a stale stated suite total, one an RFC1918 literal
in tracked prose.  Every one of them had already been rejected by `gate.yml`, and
each red run is an email to the owner.  The two checks that catch them cost about
three seconds and need no network, so they run here before the push instead.

It reads the **committed** tree (`git archive HEAD`), not the worktree: that is
what CI checks out, and on this syncthing-shared clone the worktree `AGENTS.md`
also carries a peer's uncommitted count edit (`test_doc_hygiene` reads it).

Usage:
    uv run python -B tools/push-gate.py    # non-zero = do not push

Interpreter.  A bare `python3` discovers 1368 tests where the repo venv discovers
1411 (the missing modules import `jinja2`), which is exactly how a false red gets
filed against a correct number.  So when `REPO/.venv/bin/python` exists this
script re-executes itself under it rather than trusting how it was invoked.

Exit: 0 clean, 1 the committed tree is red, 2 the gate could not run.
"""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def clean_env() -> dict[str, str]:
    """The environment for git and for the suite.

    A `GIT_DIR`/`GIT_WORK_TREE`/`GIT_INDEX_FILE` in the caller's shell answers for
    somebody else's repository: the extracted tree has no `.git` of its own, so a
    leak there makes the suite's git calls read the wrong tree (measured: discovery
    then counts 1343 instead of 1411).  `PYTHONPATH` would likewise import this
    clone's modules instead of the archive's.
    """
    return {k: v for k, v in os.environ.items()
            if not k.startswith("GIT_") and k != "PYTHONPATH"}


ENV = clean_env()


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, env=ENV)


def git_dir() -> str:
    out = git("rev-parse", "--absolute-git-dir")
    if out.returncode != 0:
        sys.exit(f"push-gate: not a git checkout: {out.stderr.decode().strip()}")
    return out.stdout.decode().strip()


def extract_head(tree: Path) -> str:
    """The tree CI will check out, extracted from the commit, not the worktree."""
    sha = git("rev-parse", "HEAD").stdout.decode().strip()
    archive = git("archive", "HEAD")
    if archive.returncode != 0:
        sys.exit(f"push-gate: git archive HEAD failed: {archive.stderr.decode().strip()}")
    with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as tar:
        # `filter=` is 3.12+; older interpreters keep the pre-3.12 default.
        tar.extractall(tree, **({"filter": "data"} if sys.version_info >= (3, 12) else {}))
    return sha


def changed(base: str | None, *paths: str) -> list[str]:
    """Paths changed between the upstream and HEAD; empty when there is no upstream."""
    if not base:
        return []
    out = git("diff", "--name-only", f"{base}...HEAD", "--", *paths)
    return out.stdout.decode().split() if out.returncode == 0 else []


def upstream() -> str | None:
    for ref in ("origin/main", "@{u}"):
        out = git("rev-parse", "--verify", "--quiet", ref)
        if out.returncode == 0:
            return out.stdout.decode().strip()
    return None


def run(name: str, argv: list[str], cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess:
    print(f"push-gate: {name}", flush=True)
    out = subprocess.run(argv, cwd=str(cwd), env=env, capture_output=True, text=True)
    if out.returncode != 0:
        sys.stderr.write(f"\npush-gate: FAILED -- {name}\n{out.stdout}{out.stderr}")
    return out


def checks(tree: Path, gitdir: str, base: str | None) -> bool:
    # Cheapest first: a text scan for bash-isms behind a `#!/bin/sh` shebang. This host's
    # /bin/sh is bash, so no local run can find them; on 2026-11-08 one such stub reddened
    # seven consecutive CI runs (CI's /bin/sh is dash).
    lint = run("POSIX shells (bash-ism lint)",
               [sys.executable, "-B", str(tree / "tools" / "bash-ism-lint.py"),
                "--root", str(tree)], tree, ENV)
    if lint.returncode != 0:
        sys.stderr.write("push-gate: repair: make the flagged stub POSIX, or give it "
                         "`#!/usr/bin/env bash` when it needs bash (CI's /bin/sh is dash)\n")

    # Both stated totals (snapshot and Testing & QA) plus the entry-point census, which
    # lives in the same module and fails the same way on a stale committed count.
    doc = run("stated counts and suite total (test_doc_hygiene)",
              [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests",
               "-p", "test_doc_hygiene.py"], tree, ENV)
    ok = lint.returncode == 0 and doc.returncode == 0
    if "discovery finds" in doc.stdout + doc.stderr:
        sys.stderr.write("push-gate: repair: uv run python -B tools/doc-census.py --fix"
                         " (derives the count and rewrites both statements)\n")

    # The walk is `git ls-files`; point git at the archive and at an index read from
    # HEAD so the file list is the commit's, while the bytes read are the archive's.
    address = dict(ENV, GIT_DIR=gitdir, GIT_WORK_TREE=str(tree),
                   GIT_INDEX_FILE=str(tree.parent / "index"))
    read_tree = subprocess.run(["git", "--git-dir", gitdir, "read-tree", "HEAD"],
                               capture_output=True, env=address)
    if read_tree.returncode != 0:
        sys.stderr.write(f"push-gate: read-tree HEAD failed: {read_tree.stderr.decode()}")
        return False
    ok &= run("tracked addresses (test_tracked_address_hygiene)",
              [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests",
               "-p", "test_tracked_address_hygiene.py"], tree, address).returncode == 0

    shells = [s for s in changed(base, "*.sh") if (tree / s).is_file()]
    if not shutil.which("bash"):
        sys.stderr.write("push-gate: SKIPPED bash -n -- bash not on PATH\n")
    for rel in shells:
        ok &= run(f"bash -n {rel}", ["bash", "-n", str(tree / rel)], tree, ENV).returncode == 0

    if changed(base, "campaign/"):
        ok &= run("campaign driver suite",
                  [sys.executable, "-B", "-m", "unittest", "discover",
                   "-s", "campaign/tests", "-t", "campaign"], tree, ENV).returncode == 0
    return ok


def main() -> int:
    venv_python = REPO / ".venv" / "bin" / "python"
    if venv_python.is_file() and Path(sys.executable).resolve() != venv_python.resolve():
        os.execv(str(venv_python), [str(venv_python), "-B", str(Path(__file__).resolve()),
                                    *sys.argv[1:]])

    gitdir = git_dir()
    base = upstream()
    with tempfile.TemporaryDirectory() as tmp:
        tree = Path(tmp) / "tree"
        tree.mkdir()
        sha = extract_head(tree)
        ok = checks(tree, gitdir, base)

    if not ok:
        sys.stderr.write(
            "\npush-gate: red -- do not push. Fix the committed tree, not the worktree: "
            "the message above names the file and line CI would fail on.\n")
        return 1
    print(f"push-gate: ok -- HEAD {sha[:8]} is what CI will see")
    return 0


if __name__ == "__main__":
    sys.exit(main())
