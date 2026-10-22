"""No cluster-internal address or head hostname in any tracked file.

The registry is distributed to third parties, and `AGENTS.md` forbids cluster addresses in tracked
files — but the gate is syntax-only (unittest, `sparkrun recipe validate`, `bash -n`, `py_compile`),
so nothing else here looks at a byte of prose. A leak that reaches origin costs a follow-up commit,
and the tree has been re-swept by hand more than once because of it.

The pattern is the one `.omp/skills/sparkrun-tracked-file-ip-hygiene/SKILL.md` prescribes: RFC1918
with **per-branch octet counts**, since a single shared tail matches only the `10.` branch and leaves
`192.168.x.x` (the CX7 range) and `172.16-31.x.x` invisible. Masked forms (`.34`, `192.168.0.x`,
"the management subnet") are the convention and must NOT be flagged.

Text-only and stdlib. The walk is `git ls-files`, so git-ignored working files (`.local/`,
`**/*JOURNAL.md`) are out of scope by construction, and an empty walk RAISES instead of passing.
"""
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Per-branch octet counts on purpose: see the module docstring.
ADDRESS = re.compile(r"\b(10\.\d+|192\.168|172\.(1[6-9]|2\d|3[01]))\.\d+\.\d+\b")
HOST = re.compile(r"\bspark-head\b")

# Path-keyed, never content-keyed: the same bytes are legitimate or not depending on the file.
EXEMPT = {
    # Published HLE bytes: the question itself discusses 172.20.0.0/16, and masking it would
    # corrupt the benchmark fixture.
    "recipes/ds4/benchmarks/data/hle_test.jsonl",
    # The detector regex and its own positive control are the point of that file.
    "tests/test_ci_workflows.py",
    # This file's pattern and planted controls.
    "tests/test_tracked_address_hygiene.py",
}

# Binary-ish files are never prose; a decode guard backs this up, the list just avoids reading MBs.
BINARY_SUFFIXES = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip", ".gz", ".xz", ".zst", ".7z",
    ".whl", ".so", ".bin", ".safetensors", ".gguf", ".pt", ".onnx", ".wav", ".mp3", ".mp4", ".pyc",
})


def git(*args):
    """(returncode, stdout) for a git call; a missing git binary is a skip, never a pass."""
    try:
        r = subprocess.run(["git", "-C", str(REPO_ROOT), *args], capture_output=True, text=True)
    except (FileNotFoundError, NotADirectoryError):
        raise unittest.SkipTest("git binary not available: the tracked-file list cannot be asked")
    return r.returncode, (r.stdout or "")


def tracked_files():
    """Repo-relative paths of every tracked file. An empty answer RAISES."""
    code, out = git("ls-files")
    if code != 0:
        raise AssertionError(f"git ls-files failed ({code}): {out}")
    paths = [line for line in out.splitlines() if line]
    if not paths:
        raise AssertionError("git ls-files returned nothing: a vacuous pass is not a pass")
    return paths


def findings(root, paths):
    """`path:line: hit` for every non-exempt text file in `paths` carrying an address or host."""
    root = Path(root)
    if not paths:
        raise AssertionError("empty walk: nothing was scanned, so nothing is proven clean")
    hits = []
    for rel in paths:
        if rel in EXEMPT or Path(rel).suffix.lower() in BINARY_SUFFIXES:
            continue
        path = root / rel
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for n, line in enumerate(text.splitlines(), 1):
            if ADDRESS.search(line) or HOST.search(line):
                hits.append(f"{rel}:{n}: {line.strip()[:160]}")
    return hits


class TrackedFilesAreClean(unittest.TestCase):
    def test_no_tracked_file_carries_a_cluster_address(self):
        hits = findings(REPO_ROOT, tracked_files())
        self.assertEqual(hits, [], "cluster address or head hostname in tracked file(s):\n"
                         + "\n".join(hits))

    def test_every_exemption_still_exists(self):
        # A renamed exempt path would quietly stop exempting anything while looking deliberate.
        tracked = set(tracked_files())
        for rel in sorted(EXEMPT):
            self.assertIn(rel, tracked, f"exemption {rel} is not tracked: drop or repoint it")


class NegativeControls(unittest.TestCase):
    def test_a_planted_address_is_caught(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "docs").mkdir()
            (Path(tmp) / "docs/a.md").write_text(
                "measured on 10.0.4.34 and the CX7 ring 192.168.1.31\n", encoding="utf-8")
            (Path(tmp) / "docs/b.md").write_text(
                "the copy left 172.20.96.0 for the rail\n", encoding="utf-8")
            hits = findings(tmp, ["docs/a.md", "docs/b.md"])
        self.assertEqual(len(hits), 2, hits)
        self.assertTrue(hits[0].startswith("docs/a.md:1:"), hits[0])
        self.assertTrue(hits[1].startswith("docs/b.md:1:"), hits[1])

    def test_the_head_hostname_is_caught(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "AGENTS.md").write_text("never run this on spark-head\n", encoding="utf-8")
            self.assertEqual(len(findings(tmp, ["AGENTS.md"])), 1)

    def test_masked_shorthand_is_not_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "docs").mkdir()
            (Path(tmp) / "docs/a.md").write_text(
                "on `.34`, rail `192.168.0.x`, the management subnet, `.31` -> `.35`\n",
                encoding="utf-8")
            self.assertEqual(findings(tmp, ["docs/a.md"]), [])

    def test_an_exemption_does_not_swallow_another_file(self):
        # Same planted bytes, one exempt path and one ordinary path: only the ordinary one reports.
        with tempfile.TemporaryDirectory() as tmp:
            planted = "leak 10.0.4.35\n"
            (Path(tmp) / "docs").mkdir()
            (Path(tmp) / "tests").mkdir()
            (Path(tmp) / "tests/test_ci_workflows.py").write_text(planted, encoding="utf-8")
            (Path(tmp) / "docs/a.md").write_text(planted, encoding="utf-8")
            hits = findings(tmp, ["tests/test_ci_workflows.py", "docs/a.md"])
        self.assertEqual([h.split(":")[0] for h in hits], ["docs/a.md"], hits)

    def test_an_empty_walk_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(AssertionError):
                findings(tmp, [])


if __name__ == "__main__":
    unittest.main()