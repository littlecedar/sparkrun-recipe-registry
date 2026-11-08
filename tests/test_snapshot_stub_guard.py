"""Refuse a config-only staging stub at every launcher that resolves a snapshot.

Four launcher paths resolved a model directory by `config.json` alone, so a 7,303 B
config-only tree -- a state this fleet's pool actually produced -- resolved as a model
and the boot died later inside the engine with nothing naming the staging state. Each
resolver must now refuse a tree with no top-level `*.safetensors` at or above the 1 MiB
floor (`tools/stage-audit.py`), hand a complete tree on unchanged, and still refuse a
tree that is not there at all. After the guard fires: `--model` and the drafter name the
tree, its entry count and its resolved bytes; the graft mod's stock resolver names the
same three facts on stderr before `die`; and the DSV41 launcher's bare-repo-id fallback
stays a WARN, because that path may legitimately drive a cache-resolved model.

Behaviour, not wording: assertions are the exit/return value, the path handed onward,
and the three facts a refusal must carry. Each class also carries a negative control
that bypasses the guard (floor 0) and shows the stub then passes -- so a green case
cannot be coming from a fixture that never looked like a stub.

Stdlib only; no GPU, no image, no checkpoint.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
GLM_EXL3 = REPO_ROOT / "recipes" / "glm" / "mods" / "tensorfold-glm-exl3-launcher" / "launcher.py"
GLM_3BPW = REPO_ROOT / "recipes" / "glm" / "mods" / "tensorfold-glm53-3bpw-launcher" / "launcher.py"
TF_DSV41 = REPO_ROOT / "mods" / "tensorfold-dsv41-launcher" / "launcher.py"
GRAFT_RUN = REPO_ROOT / "recipes" / "cybersec" / "mods" / "graft-dsv41-ablit-wo-b" / "run.sh"

REPO = "Mia-AiLab/GLM-5.3-Flash-EXL3-4bpw-TensorFold"
DRAFTER = "incoai/GLM-5.3-Flash-DFlash2"
REVISION = "078455ff"
STUB_CONFIG_BYTES = 7303  # exactly the size the pool staged: config.json and nothing else
FLOOR = 1 << 20


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _snapshot_root(hub: Path, repo: str, revision: str) -> Path:
    snap = hub / ("models--" + repo.replace("/", "--")) / "snapshots" / revision
    snap.mkdir(parents=True)
    return snap


def complete_snapshot(hub: Path, repo: str = REPO, revision: str = REVISION) -> Path:
    """A launchable tree: config plus one shard above the floor."""
    snap = _snapshot_root(hub, repo, revision)
    (snap / "config.json").write_text("{}")
    with open(snap / "model-00001-of-00001.safetensors", "wb") as fh:
        fh.seek(FLOOR + 1)  # sparse: the guard reads stat, never contents
        fh.write(b"\0")
    return snap


def stub_snapshot(hub: Path, repo: str = REPO, revision: str = REVISION) -> Path:
    """The staging state that burned a boot: a 7,303 B config.json, no weights."""
    snap = _snapshot_root(hub, repo, revision)
    (snap / "config.json").write_text("x" * STUB_CONFIG_BYTES)
    return snap


def write_ref(hub: Path, repo: str, revision: str) -> None:
    refs = hub / ("models--" + repo.replace("/", "--")) / "refs"
    refs.mkdir(parents=True, exist_ok=True)
    (refs / "main").write_text(revision)


def assert_names_stub(case: unittest.TestCase, text: str, snap: Path) -> None:
    """A refusal must carry the tree, its entry count and its resolved bytes."""
    case.assertIn(str(snap), text)
    case.assertIn("entries=1", text)
    case.assertIn("bytes=0", text)


class ResolverCase(unittest.TestCase):
    """Point a loaded launcher's HF_HUB at a temp cache and capture what it says."""

    PATH = GLM_EXL3
    RESOLVER = "resolve_model_dir"
    REPO = REPO

    def setUp(self) -> None:
        self.mod = load(self.PATH, type(self).__name__)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.hub = Path(tmp.name)
        patcher = mock.patch.object(self.mod, "HF_HUB", str(self.hub))
        patcher.start()
        self.addCleanup(patcher.stop)

    def resolve(self, value: str, resolver: str | None = None):
        """(resolved path or None, everything it printed)."""
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            resolved = getattr(self.mod, resolver or self.RESOLVER)(value)
        return resolved, out.getvalue()

class GlmExl3Checkpoint(ResolverCase):
    """`recipes/glm/mods/tensorfold-glm-exl3-launcher/launcher.py:196-207`."""

    PATH = GLM_EXL3

    def test_complete_snapshot_is_handed_on_unchanged(self) -> None:
        snap = complete_snapshot(self.hub)
        write_ref(self.hub, REPO, REVISION)
        self.assertEqual(str(snap), self.mod.resolve_model_dir(REPO))

    def test_config_only_stub_is_refused(self) -> None:
        snap = stub_snapshot(self.hub)
        write_ref(self.hub, REPO, REVISION)
        resolved, text = self.resolve(REPO)
        self.assertIsNone(resolved)
        assert_names_stub(self, text, snap)

    def test_missing_repo_is_refused(self) -> None:
        resolved, text = self.resolve("Nobody/No-Such-Checkpoint")
        self.assertIsNone(resolved)
        self.assertNotIn("STUB", text)

    def test_control_floor_zero_lets_the_stub_through(self) -> None:
        snap = stub_snapshot(self.hub)
        write_ref(self.hub, REPO, REVISION)
        with mock.patch.object(self.mod, "STUB_BYTES", 0):
            self.assertEqual(str(snap), self.mod.resolve_model_dir(REPO))


class GlmExl3Drafter(ResolverCase):
    """Same file, `:224-235`: the DFlash2 drafter is a snapshot too."""

    PATH = GLM_EXL3
    RESOLVER = "resolve_drafter"

    def test_complete_drafter_is_handed_on_unchanged(self) -> None:
        snap = complete_snapshot(self.hub, DRAFTER)
        write_ref(self.hub, DRAFTER, REVISION)
        self.assertEqual(str(snap), self.mod.resolve_drafter(DRAFTER, REVISION))

    def test_config_only_stub_is_refused(self) -> None:
        snap = stub_snapshot(self.hub, DRAFTER)
        write_ref(self.hub, DRAFTER, REVISION)
        resolved, text = self.resolve(DRAFTER, "resolve_drafter")
        self.assertIsNone(resolved)
        assert_names_stub(self, text, snap)

    def test_missing_drafter_is_refused(self) -> None:
        resolved, text = self.resolve("Nobody/No-Drafter", "resolve_drafter")
        self.assertIsNone(resolved)
        self.assertNotIn("STUB", text)

    def test_control_floor_zero_lets_the_stub_through(self) -> None:
        snap = stub_snapshot(self.hub, DRAFTER)
        write_ref(self.hub, DRAFTER, REVISION)
        with mock.patch.object(self.mod, "STUB_BYTES", 0):
            self.assertEqual(str(snap), self.mod.resolve_drafter(DRAFTER, REVISION))


class Glm3bpwCheckpoint(ResolverCase):
    """`recipes/glm/mods/tensorfold-glm53-3bpw-launcher/launcher.py:237-248`."""

    PATH = GLM_3BPW

    def test_complete_snapshot_is_handed_on_unchanged(self) -> None:
        snap = complete_snapshot(self.hub)
        write_ref(self.hub, REPO, REVISION)
        self.assertEqual(str(snap), self.mod.resolve_model_dir(REPO))

    def test_config_only_stub_is_refused(self) -> None:
        snap = stub_snapshot(self.hub)
        write_ref(self.hub, REPO, REVISION)
        resolved, text = self.resolve(REPO)
        self.assertIsNone(resolved)
        assert_names_stub(self, text, snap)

    def test_missing_repo_is_refused(self) -> None:
        resolved, text = self.resolve("Nobody/No-Such-Checkpoint")
        self.assertIsNone(resolved)
        self.assertNotIn("STUB", text)

    def test_control_floor_zero_lets_the_stub_through(self) -> None:
        snap = stub_snapshot(self.hub)
        write_ref(self.hub, REPO, REVISION)
        with mock.patch.object(self.mod, "STUB_BYTES", 0):
            self.assertEqual(str(snap), self.mod.resolve_model_dir(REPO))


class TensorfoldDsv41Checkpoint(ResolverCase):
    """`mods/tensorfold-dsv41-launcher/launcher.py:265-273`, including the bare-id fallback."""

    PATH = TF_DSV41
    RESOLVER = "resolve_checkpoint"

    def run_main(self, model: str) -> tuple[int, list[str] | None]:
        """`main()` with the engine's exec intercepted: (rc, argv it would have exec'd)."""
        with tempfile.TemporaryDirectory() as d:
            self.mod.RUNTIME_CACHE = d
            self.mod.ENGRAM_DIR = str(Path(d) / "engram")
            self.mod.RECIPE_ENV = dict(self.mod.RECIPE_ENV)
            self.mod.RECIPE_ENV["HOME"] = d
            executed: dict[str, list[str]] = {}

            def fake_execvp(prog: str, argv: list[str]) -> None:
                executed["argv"] = list(argv)
                raise SystemExit(0)

            before = dict(os.environ)
            try:
                with mock.patch.object(self.mod.os, "execvp", fake_execvp):
                    try:
                        rc = self.mod.main(["--boot", "--model", model, "--port", "8000",
                                            "--tp", "2", "--served-model-name", "x",
                                            "--context", "262144"])
                    except SystemExit:
                        rc = 0
            finally:
                os.environ.clear()
                os.environ.update(before)
        return rc, executed.get("argv")

    def test_complete_tree_is_handed_on_unchanged(self) -> None:
        snap = complete_snapshot(self.hub)
        self.assertEqual(str(snap), self.mod.resolve_checkpoint(str(snap)))

    def test_config_only_stub_is_refused_and_main_stops(self) -> None:
        snap = stub_snapshot(self.hub)
        self.assertIsNone(self.mod.resolve_checkpoint(str(snap)))
        resolved, text = self.resolve(str(snap), "resolve_checkpoint")
        self.assertIsNone(resolved)
        assert_names_stub(self, text, snap)
        rc, argv = self.run_main(str(snap))
        self.assertEqual(2, rc)
        self.assertIsNone(argv, "a stub tree must never reach the engine")

    def test_missing_tree_warns_and_lets_the_engine_resolve_the_id(self) -> None:
        # Preserved behaviour: a bare repo id may legitimately drive a cache-resolved
        # model, so this path logs and continues instead of dying silently.
        resolved, text = self.resolve("Nobody/No-Such-Checkpoint", "resolve_checkpoint")
        self.assertEqual("Nobody/No-Such-Checkpoint", resolved)
        self.assertIn("WARN", text)
        self.assertIn("entries=0 bytes=0", text)
        rc, argv = self.run_main("Nobody/No-Such-Checkpoint")
        self.assertEqual(0, rc)
        self.assertIsInstance(argv, list, "the fallback must still start the engine")
        self.assertIn("Nobody/No-Such-Checkpoint", argv or [])

    def test_control_floor_zero_lets_the_stub_through(self) -> None:
        snap = stub_snapshot(self.hub)
        with mock.patch.object(self.mod, "STUB_BYTES", 0):
            self.assertEqual(str(snap), self.mod.resolve_checkpoint(str(snap)))


class GraftStockResolver(unittest.TestCase):
    """`recipes/cybersec/mods/graft-dsv41-ablit-wo-b/run.sh:150-190`, run as the mod runs it.

    The resolver is sliced out of run.sh rather than re-implemented, so the shipped bytes
    are what is proven -- the shape `tests/test_cybersec_recipes.py` already uses for the
    generation check.
    """

    REPO = "littlecedar/DeepSeek-V4.1-Flash-EXL3-2.9bpw-with-engram"

    def setUp(self) -> None:
        script = GRAFT_RUN.read_text(encoding="utf-8")
        start = script.index('STOCK="$(python3 -')
        end = script.index('\nlog "stock: ${STOCK}"', start)
        self.block = script[start:end]
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.hub = Path(tmp.name)

    def run_block(self, block: str | None = None) -> subprocess.CompletedProcess:
        harness = (
            "set -euo pipefail\n"
            f'HF_HUB="{self.hub}"\nSTOCK_REPO="{self.REPO}"\n'
            'die() { echo "die: $*" >&2; exit 1; }\n'
            + (block or self.block)
            + '\necho "$STOCK"\n'
        )
        return subprocess.run(["bash", "-c", harness], capture_output=True, text=True, timeout=60)

    def test_complete_stock_pack_is_handed_on_unchanged(self) -> None:
        snap = complete_snapshot(self.hub, self.REPO, REVISION)
        write_ref(self.hub, self.REPO, REVISION)
        run = self.run_block()
        self.assertEqual(0, run.returncode, run.stderr)
        self.assertEqual(str(snap), run.stdout.strip())

    def test_config_only_stub_is_refused(self) -> None:
        snap = stub_snapshot(self.hub, self.REPO, REVISION)
        write_ref(self.hub, self.REPO, REVISION)
        run = self.run_block()
        self.assertEqual(1, run.returncode, "the mod must die, not graft onto a stub")
        assert_names_stub(self, run.stderr, snap)

    def test_missing_stock_pack_is_refused(self) -> None:
        run = self.run_block()
        self.assertEqual(1, run.returncode)
        self.assertIn("no launchable snapshot", run.stderr)
        self.assertNotIn("STUB stock snapshot", run.stderr)

    def test_control_floor_zero_lets_the_stub_through(self) -> None:
        snap = stub_snapshot(self.hub, self.REPO, REVISION)
        write_ref(self.hub, self.REPO, REVISION)
        bypassed = self.block.replace("STUB_BYTES = 1 << 20", "STUB_BYTES = 0")
        self.assertNotEqual(bypassed, self.block, "the floor line vanished; update the control")
        run = self.run_block(bypassed)
        self.assertEqual(0, run.returncode, run.stderr)
        self.assertEqual(str(snap), run.stdout.strip())


if __name__ == "__main__":
    unittest.main()
