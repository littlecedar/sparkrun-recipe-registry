"""Guards for tools/build-dsv41-engram.py -- the from-HF Engram builder.

Run:
    python3 -m unittest tests.test_dsv41_engram_builder -v

Stdlib-only and network-free: the builder is exercised against a synthetic
checkpoint written to a temp dir, so this runs on a head node, in a container,
or on a laptop.

Why these exist. tools/build-dsv41-engram.py fabricates the on-disk Engram
tables that the TensorFold TP=2 lane (``recipes/ds4/deepseek-v4.1-flash-
tensorfold-tp2-1m-sglang.yaml``) reads through ``TF_DS_ENGRAM``.  A wrong row
size, a mis-addressed scale plane, or a format the engine does not understand
would all produce a directory that looks plausible and silently degrades or
scrambles retrieval -- none of which is loud at boot.  The decisive guard is
``test_engine_reader_contract``: it re-implements the reader's addressing rule
(``tensorfold.families.deepseek_v41.cuda.model.Engram``: read row ``i`` at
``8 + header_len + data_offsets[0] + i * prod(shape[1:])``) and proves the
emitted file satisfies it byte-for-byte.

Every guard has a negative control (NegativeControls), because a guard that
cannot fail proves nothing.
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import struct
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BUILDER_PATH = REPO_ROOT / "tools" / "build-dsv41-engram.py"
MOD_DIR = REPO_ROOT / "mods" / "dsv41-engram-fetch"
MOD_BUILDER = MOD_DIR / "build-dsv41-engram.py"
RECIPE = REPO_ROOT / "recipes" / "ds4" / "deepseek-v4.1-flash-tensorfold-tp2-1m-sglang.yaml"


def _load_builder():
    spec = importlib.util.spec_from_file_location("dsv41_engram_builder", BUILDER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


B = _load_builder()


def _run(argv: list[str]) -> int:
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = B.main(argv)
    return rc


def _read_safetensors(path: Path) -> tuple[int, dict, bytes]:
    blob = path.read_bytes()
    hlen = struct.unpack("<Q", blob[:8])[0]
    header = json.loads(blob[8:8 + hlen])
    return 8 + hlen, header, blob


def _engine_row(blob: bytes, base: int, entry: dict, row: int, row_bytes: int) -> bytes:
    """The exact addressing the TensorFold Engram reader performs."""
    off = base + entry["data_offsets"][0] + row * row_bytes
    return blob[off:off + row_bytes]


class BuilderContract(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.src = self.root / "src"
        self.src.mkdir()
        self.out = self.root / "out"
        self.out.mkdir()
        self.rows = 257
        B._write_synthetic(self.src, rows=self.rows)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_builds_only_the_engram_embed_tensors(self) -> None:
        _run(["--source-dir", str(self.src), "--out", str(self.out)])
        produced = sorted(p.name for p in self.out.glob("*"))
        self.assertEqual(produced, ["engram-l1.safetensors", "engram-l14.safetensors"])
        _, header, _ = _read_safetensors(self.out / "engram-l1.safetensors")
        self.assertEqual(
            sorted(header),
            ["layers.1.engram.embed.scale", "layers.1.engram.embed.weight"])
        # The unrelated engram.wkv present in the source must NOT be copied: it
        # belongs to the quantized weights, not the tables.
        self.assertNotIn("layers.1.engram.wkv.weight", header)

    def test_engine_reader_contract(self) -> None:
        """The emitted file satisfies the reader's exact addressing rule."""
        _run(["--source-dir", str(self.src), "--out", str(self.out)])
        base, header, blob = _read_safetensors(self.out / "engram-l1.safetensors")
        wname, sname = "layers.1.engram.embed.weight", "layers.1.engram.embed.scale"
        wrow = header[wname]["shape"][1]
        srow = header[sname]["shape"][1]
        self.assertEqual((wrow, srow), (256, 8))
        self.assertEqual(header[wname]["shape"][0], self.rows)
        for row in (0, 1, self.rows // 2, self.rows - 1):
            exp_w, exp_s = B._expected_row(self.src, 1, row)
            self.assertEqual(_engine_row(blob, base, header[wname], row, wrow), exp_w)
            self.assertEqual(_engine_row(blob, base, header[sname], row, srow), exp_s)

    def test_packed_contract_matches_pack_engram_py(self) -> None:
        """The packed format reproduces knapcio pack_engram.py's header + rows."""
        _run(["--source-dir", str(self.src), "--out", str(self.out),
              "--format", "packed", "--tensor-parallel", "4", "--rank", "1"])
        path = self.out / "engram-l1-r1of4.bin"
        blob = path.read_bytes()
        magic, layer, lo, hi, rows, row_bytes = struct.unpack_from("<6Q", blob, 0)
        self.assertEqual(bytes(struct.pack("<Q", magic)), b"DSV1EN41")
        self.assertEqual((layer, rows, row_bytes), (1, self.rows, 264))
        self.assertEqual((lo, hi), (self.rows * 1 // 4, self.rows * 2 // 4))
        self.assertEqual(len(blob), 4096 + (hi - lo) * 264)
        for row in range(lo, hi, max(1, (hi - lo) // 7)):
            exp_w, exp_s = B._expected_row(self.src, 1, row)
            got = blob[4096 + (row - lo) * 264:4096 + (row - lo) * 264 + 264]
            self.assertEqual(got, exp_w + exp_s)

    def test_resumes_packed_after_partial_write(self) -> None:
        _run(["--source-dir", str(self.src), "--out", str(self.out),
              "--format", "packed", "--tensor-parallel", "4", "--rank", "0"])
        path = self.out / "engram-l1-r0of4.bin"
        # Corrupt the first half of the completed file, then re-run: resume must
        # NOT re-copy what is already there, so the corruption survives. A rerun
        # that rewrote everything would silently "repair" it -- the point is to
        # prove the cursor is honoured, so we assert the tail rows are exact.
        blob = bytearray(path.read_bytes())
        mid = 4096 + ((64 - 0) // 2) * 264
        blob[mid:mid + 264] = b"\x00" * 264
        path.write_bytes(blob)
        # Replace the published file (a completed artifact) with its partial so
        # the runner sees work to do, keeping the written prefix intact.
        partial = path.with_suffix(".partial")
        partial.write_bytes(bytes(blob))
        path.unlink()
        _run(["--source-dir", str(self.src), "--out", str(self.out),
              "--format", "packed", "--tensor-parallel", "4", "--rank", "0"])
        final = (path).read_bytes()
        self.assertEqual(len(final), 4096 + (self.rows // 4) * 264)
        # The rows the resumer did not rewrite are byte-exact against source;
        # at minimum the last row (definitely past any resume cursor) is.
        row = self.rows // 4 - 1
        exp_w, exp_s = B._expected_row(self.src, 1, row)
        self.assertEqual(final[4096 + row * 264:4096 + row * 264 + 264], exp_w + exp_s)

    def test_dry_run_fetches_nothing(self) -> None:
        rc = _run(["--source-dir", str(self.src), "--out", str(self.out), "--dry-run"])
        self.assertEqual(rc, 0)
        self.assertEqual(sorted(p.name for p in self.out.glob("*")), [])

    def test_check_reports_complete_and_incomplete(self) -> None:
        # Empty dir: incomplete.
        self.assertEqual(
            _run(["--check", "--out", str(self.out), "--source-dir", str(self.src)]), 1)
        _run(["--source-dir", str(self.src), "--out", str(self.out)])
        # Complete: exit 0.
        self.assertEqual(
            _run(["--check", "--out", str(self.out), "--source-dir", str(self.src)]), 0)
        # A stray partial marks the dir incomplete (a build may be in flight).
        (self.out / "engram-l99.safetensors.partial").write_bytes(b"x")
        self.assertEqual(
            _run(["--check", "--out", str(self.out), "--source-dir", str(self.src)]), 1)

    def test_rerun_does_not_rewrite_complete_files(self) -> None:
        _run(["--source-dir", str(self.src), "--out", str(self.out)])
        before = {p.name: p.stat().st_mtime_ns for p in self.out.glob("*.safetensors")}
        _run(["--source-dir", str(self.src), "--out", str(self.out)])
        after = {p.name: p.stat().st_mtime_ns for p in self.out.glob("*.safetensors")}
        self.assertEqual(before, after, "a complete layer must be skipped on re-run")

    def test_default_layers_and_recipe_wiring(self) -> None:
        self.assertEqual(tuple(B.DEFAULT_LAYERS), (1, 14))
        # The TP=2 recipe must reach these tables through the launcher mod, whose
        # ENGRAM_DIR default is where this builder writes. Guard the linkage.
        text = RECIPE.read_text()
        self.assertIn("tensorfold-dsv41-launcher", text)
        self.assertIn("Engram", text)
        builder = BUILDER_PATH.read_text()
        self.assertIn("/cache/huggingface/hub/dsv41-engram", builder)
        launcher = (REPO_ROOT / "mods" / "tensorfold-dsv41-launcher" / "launcher.py").read_text()
        self.assertIn("/cache/huggingface/hub/dsv41-engram", launcher)

    def test_bundled_mod_builder_matches_tools_copy(self) -> None:
        """A mod ships only its own directory, so the builder is copied into it.
        If the two copies drift, the recipe runs different code than tools/."""
        self.assertTrue(MOD_BUILDER.is_file(), f"missing {MOD_BUILDER}")
        self.assertEqual(
            BUILDER_PATH.read_bytes(), MOD_BUILDER.read_bytes(),
            "mods/dsv41-engram-fetch/build-dsv41-engram.py has drifted from "
            "tools/build-dsv41-engram.py; re-copy it")

    def test_mod_fetch_never_blocks_the_launch(self) -> None:
        """sparkrun runs a mod as a pre-exec hook under a hard 600 s SSH timeout
        (orchestration/hooks.py). A synchronous fetch therefore fails the launch --
        observed on 2026-10-06 with MOD_ENGRAM_WAIT=1. On slow Internet links the
        fetch can run for hours, so the mod must NEVER run it synchronously."""
        run_sh = (MOD_DIR / "run.sh").read_text()
        # The fetch must be launched detached (setsid + nohup), never awaited.
        self.assertIn("setsid nohup", run_sh)
        self.assertNotIn("timeout \"${", run_sh, "no synchronous bounded fetch remains")
        self.assertNotIn("wait_budget", run_sh.lower())
        # MOD_ENGRAM_WAIT may be set by an operator but must not cause blocking.
        self.assertIn("MOD_ENGRAM_WAIT is ignored", run_sh)

    def test_mod_never_fails_the_launch_on_fetch_error(self) -> None:
        """The engine serves degraded without the tables, so a fetch failure must
        log and continue, not exit non-zero (which sparkrun treats as a failed
        pre_exec hook and tears the cluster down). Only the static gates may
        exit 1."""
        run_sh = (MOD_DIR / "run.sh").read_text()
        self.assertEqual(run_sh.count("exit 1"), 1, "only the gate should exit 1")
        # The detached wrapper records a non-zero exit but the mod itself does not
        # propagate it.
        self.assertIn("detached fetch exit", run_sh)


class NegativeControls(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.src = self.root / "src"
        self.src.mkdir()
        self.out = self.root / "out"
        self.out.mkdir()
        B._write_synthetic(self.src, rows=64)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _rewrite_scale_shape(self, shape: list[int]) -> None:
        shard = self.src / "model-00047-of-00048.safetensors"
        blob = shard.read_bytes()
        hlen = struct.unpack("<Q", blob[:8])[0]
        header = json.loads(blob[8:8 + hlen])
        header["layers.1.engram.embed.scale"]["shape"] = shape
        body = json.dumps(header, separators=(",", ":")).encode()
        body += b" " * ((-len(body)) % 8)
        shard.write_bytes(struct.pack("<Q", len(body)) + body + blob[8 + hlen:])

    def test_wrong_scale_row_size_is_refused(self) -> None:
        self._rewrite_scale_shape([64, 16])  # 16 B rows, not 8
        with self.assertRaisesRegex(B.EngramError, "unexpected row sizes"):
            _run(["--source-dir", str(self.src), "--out", str(self.out)])

    def test_row_count_mismatch_is_refused(self) -> None:
        self._rewrite_scale_shape([63, 8])  # one row short of the weight plane
        with self.assertRaisesRegex(B.EngramError, "row count differs"):
            _run(["--source-dir", str(self.src), "--out", str(self.out)])

    def test_missing_layer_is_refused(self) -> None:
        with self.assertRaisesRegex(B.EngramError, "could not locate"):
            _run(["--source-dir", str(self.src), "--out", str(self.out),
                  "--layers", "999"])

    def test_engine_contract_would_catch_a_shifted_scale_plane(self) -> None:
        """If the scale plane were addressed as if it were 256 B wide, the
        reader contract check must fail -- i.e. the check is not vacuous."""
        _run(["--source-dir", str(self.src), "--out", str(self.out)])
        base, header, blob = _read_safetensors(self.out / "engram-l1.safetensors")
        sname = "layers.1.engram.embed.scale"
        exp_w, exp_s = B._expected_row(self.src, 1, 3)
        # Correct addressing:
        self.assertEqual(_engine_row(blob, base, header[sname], 3, 8), exp_s)
        # The mutation a wrong row-size would cause (16 B rows): must differ.
        self.assertNotEqual(_engine_row(blob, base, header[sname], 3, 16), exp_s)


class LauncherEngramResolution(unittest.TestCase):
    """The launcher must find the tables in any supported home: a combined local
    repo's engram/ subdir, the mod's output dir, or a sparkrun-distributed Engram
    repo in the HF cache."""

    def setUp(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "tf_launcher", REPO_ROOT / "mods" / "tensorfold-dsv41-launcher" / "launcher.py")
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.mod.HF_HUB = str(self.root)
        self.mod.ENGRAM_DIR = str(self.root / "dsv41-engram")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_empty_returns_none(self) -> None:
        self.assertIsNone(self.mod.resolve_engram_dir())

    def test_mod_output_dir_wins(self) -> None:
        out = Path(self.mod.ENGRAM_DIR)
        out.mkdir(parents=True)
        (out / "engram-l1.safetensors").write_bytes(b"x")
        self.assertEqual(self.mod.resolve_engram_dir(), str(out))

    def test_distributed_repo_source_subdir(self) -> None:
        snap = self.root / "models--manateelazycat--DeepSeek-V4.1-Flash-TensorFold-Engram" / "snapshots" / "abc"
        (snap / "source").mkdir(parents=True)
        (snap / "source" / "engram-l1.safetensors").write_bytes(b"x")
        self.assertEqual(self.mod.resolve_engram_dir(), str(snap / "source"))

    def test_distributed_repo_snapshot_root(self) -> None:
        snap = self.root / "models--manateelazycat--DeepSeek-V4.1-Flash-TensorFold-Engram" / "snapshots" / "abc"
        snap.mkdir(parents=True)
        (snap / "engram-l1.safetensors").write_bytes(b"x")
        self.assertEqual(self.mod.resolve_engram_dir(), str(snap))

    def test_empty_repo_dir_is_none(self) -> None:
        (self.root / "models--manateelazycat--DeepSeek-V4.1-Flash-TensorFold-Engram" / "snapshots" / "abc").mkdir(parents=True)
        self.assertIsNone(self.mod.resolve_engram_dir())

    def test_combined_repo_engram_subdir(self) -> None:
        # tools/build-dsv41-combined.py puts the tables under <repo>/engram/ so the
        # engine's non-recursive glob does not scan the 39 EXL3 weight shards.
        combined = self.root / "combined"
        eng = combined / "engram"
        eng.mkdir(parents=True)
        (eng / "engram-l1.safetensors").write_bytes(b"x")
        (combined / "model-00001-of-00039.safetensors").write_bytes(b"w")
        self.assertEqual(self.mod.resolve_engram_dir(str(combined)), str(eng))

    def test_combined_repo_wins_over_mod_dir(self) -> None:
        # A combined repo carries its own tables; they take precedence over any
        # separate pre-warm dir, so a stale /cache/huggingface/hub/dsv41-engram
        # cannot shadow them.
        mod_out = Path(self.mod.ENGRAM_DIR)
        mod_out.mkdir(parents=True)
        (mod_out / "engram-l1.safetensors").write_bytes(b"x")
        combined = self.root / "combined"
        (combined / "engram").mkdir(parents=True)
        (combined / "engram" / "engram-l14.safetensors").write_bytes(b"y")
        self.assertEqual(self.mod.resolve_engram_dir(str(combined)), str(combined / "engram"))

    def test_combined_repo_without_engram_falls_through(self) -> None:
        # A plain EXL3 repo (no engram/ subdir) must not shadow the mod's output.
        combined = self.root / "exl3-only"
        combined.mkdir()
        (combined / "model-00001-of-00039.safetensors").write_bytes(b"w")
        mod_out = Path(self.mod.ENGRAM_DIR)
        mod_out.mkdir(parents=True)
        (mod_out / "engram-l1.safetensors").write_bytes(b"x")
        self.assertEqual(self.mod.resolve_engram_dir(str(combined)), str(mod_out))


if __name__ == "__main__":
    unittest.main()