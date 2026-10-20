# SPDX-FileCopyrightText: 2026 Travis Wichert
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Guard the GLM-5.3-Flash EXL3 TP=4 launcher shim's sparkrun <-> TensorFold mapping.

`recipes/glm/mods/tensorfold-glm-exl3-launcher/launcher.py` is what makes the
recipe's `runtime: sglang` shim work, and three of its behaviours are silent
when wrong: sparkrun gates the launch on the rendezvous port it put in
`--dist-init-addr` (TensorFold's TCPStore must be told the same port as
`--master-port`), only the shim sees `--node-rank` (getting it wrong makes every
rank think it is rank 0), and the drafter must resolve to a snapshot directory.

The shim is exercised as a module with `os.execvp` captured, so the argv it
would exec is asserted exactly. Stdlib only; no GPU, no image, no checkpoint.
"""
from __future__ import annotations

import importlib.util
import os
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
SHIM = REPO_ROOT / "recipes" / "glm" / "mods" / "tensorfold-glm-exl3-launcher" / "launcher.py"

MODEL = "Mia-AiLab/GLM-5.3-Flash-EXL3-4bpw-TensorFold"
DRAFTER = "incoai/GLM-5.3-Flash-DFlash2"


def load_shim():
    spec = importlib.util.spec_from_file_location("glm_exl3_launcher_shim", SHIM)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def snapshot(hub: Path, repo: str, revision: str) -> Path:
    """Materialize an HF-cache-shaped snapshot (config.json + refs) under *hub*."""
    root = hub / ("models--" + repo.replace("/", "--"))
    snap = root / "snapshots" / revision
    snap.mkdir(parents=True)
    (snap / "config.json").write_text("{}")
    (root / "refs").mkdir(exist_ok=True)
    (root / "refs" / "main").write_text(revision)
    return snap


class ShimTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.mod = load_shim()
        self._tmp = __import__("tempfile").TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.hub = Path(self._tmp.name)
        self.model_snap = snapshot(self.hub, MODEL, "078455ff")
        self.drafter_snap = snapshot(self.hub, DRAFTER, self.mod.DFLASH2_REVISION)
        patcher = mock.patch.object(self.mod, "HF_HUB", str(self.hub))
        patcher.start()
        self.addCleanup(patcher.stop)
        env = mock.patch.dict(os.environ, {}, clear=False)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("NCCL_IB_HCA", None)
        os.environ.pop("TF_ROCE_HCA", None)

    def exec_argv(self, argv: list[str]) -> list[str]:
        """Run the shim with os.execvp captured; returns the argv it would exec."""
        with mock.patch("os.execvp") as execvp:
            rc = self.mod.main(argv)
        self.assertTrue(execvp.called, f"the shim refused to start (rc={rc})")
        return list(execvp.call_args.args[1])

    def exec_refusal(self, argv: list[str]) -> int:
        """Run the shim expecting a fail-closed refusal; returns its exit code."""
        with mock.patch("os.execvp") as execvp:
            rc = self.mod.main(argv)
        self.assertFalse(execvp.called, "the shim started on state it cannot serve")
        return rc

    def base_argv(self, extra: list[str] | None = None, **overrides) -> list[str]:
        argv = [
            "--boot",
            "--model", MODEL,
            "--served-model-name", "GLM-5.3-Flash-EXL3",
            "--port", "8000",
            "--tp", "4",
            "--context", "1048576",
            "--drafter-repo", DRAFTER,
            "--drafter-revision", self.mod.DFLASH2_REVISION,
        ]
        for flag, value in overrides.items():
            argv += ["--" + flag.replace("_", "-"), str(value)]
        return argv + list(extra or [])


class Rendezvous(ShimTestCase):
    """sparkrun's three flags, mapped onto TensorFold's spelling."""

    def test_master_port_is_the_gated_rendezvous_port(self) -> None:
        argv = self.exec_argv(self.base_argv(dist_init_addr=".30:25000", nodes=4, node_rank="1"))
        self.assertIsInstance(argv, list)
        self.assertEqual("25000", argv[argv.index("--master-port") + 1])
        self.assertEqual(".30", argv[argv.index("--master") + 1])

    def test_node_rank_reaches_the_engine(self) -> None:
        argv = self.exec_argv(self.base_argv(extra=["--nnodes", "4"], dist_init_addr=".30:25000", node_rank=3))
        self.assertEqual("3", argv[argv.index("--rank") + 1])
        self.assertEqual("4", argv[argv.index("--tp") + 1])

    def test_only_rank_zero_serves_http(self) -> None:
        rank0 = self.exec_argv(self.base_argv(extra=["--nnodes", "4"], dist_init_addr=".30:25000", node_rank=0))
        self.assertEqual("GLM-5.3-Flash-EXL3", rank0[rank0.index("--name") + 1])
        self.assertEqual("8000", rank0[rank0.index("--port") + 1])
        worker = self.exec_argv(self.base_argv(extra=["--nnodes", "4"], dist_init_addr=".30:25000", node_rank=2))
        for flag in ("--name", "--host", "--port"):
            self.assertNotIn(flag, worker)

    def test_no_addr_falls_back_to_the_engine_default(self) -> None:
        argv = self.exec_argv(self.base_argv())
        self.assertEqual("29551", argv[argv.index("--master-port") + 1])


class Artifacts(ShimTestCase):
    """Checkpoint and drafter resolution, and the two fail-closed paths."""

    def test_prepared_path_is_used_as_given(self) -> None:
        argv = self.exec_argv(self.base_argv(model=str(self.model_snap)))
        self.assertEqual(str(self.model_snap), argv[2])

    def test_drafter_is_a_snapshot_directory(self) -> None:
        argv = self.exec_argv(self.base_argv())
        self.assertEqual(str(self.drafter_snap), argv[argv.index("--drafter") + 1])

    def test_pinned_drafter_revision_beats_a_newer_snapshot(self) -> None:
        other = snapshot(self.hub, DRAFTER, "ffffffff")
        (other / "config.json").write_text("{}")
        argv = self.exec_argv(self.base_argv())
        self.assertEqual(str(self.drafter_snap), argv[argv.index("--drafter") + 1])

    def test_drafter_none_is_passed_through(self) -> None:
        argv = self.exec_argv(self.base_argv(drafter_repo="none"))
        self.assertEqual("auto", argv[argv.index("--drafter") + 1])

    def test_unresolvable_checkpoint_fails_closed(self) -> None:
        rc = self.exec_refusal(self.base_argv(model="Nobody/No-Such-Checkpoint"))
        self.assertEqual(2, rc)

    def test_missing_drafter_fails_closed(self) -> None:
        rc = self.exec_refusal(self.base_argv(drafter_repo="Nobody/No-Drafter"))
        self.assertEqual(2, rc)

    def test_a_pinned_drafter_revision_is_required_to_be_present(self) -> None:
        # refs/main still names the snapshot in this cache; a pin that is not
        # there must NOT silently serve whatever main points at.
        rc = self.exec_refusal(self.base_argv(drafter_revision="deadbeef"))
        self.assertEqual(2, rc)


class ServedName(ShimTestCase):
    def test_repo_id_recovers_from_the_cache_path(self) -> None:
        self.assertEqual(MODEL, self.mod.served_model_name(str(self.model_snap)))

    def test_plain_value_is_untouched(self) -> None:
        self.assertEqual("GLM-5.3-Flash-EXL3", self.mod.served_model_name("GLM-5.3-Flash-EXL3"))


class RecipeEnv(ShimTestCase):
    def test_roce_hca_comes_from_the_probe_and_is_rank_local(self) -> None:
        env = self.mod.recipe_env({"NCCL_IB_HCA": "rocep1s0f0,roceP2p1s0f0"})
        self.assertEqual("rocep1s0f0,roceP2p1s0f0", env["TF_ROCE_HCA"])
        self.assertNotIn("TF_ROCE_HCA", self.mod.recipe_env({}))

    def test_no_host_device_names_are_baked_in(self) -> None:
        self.assertEqual("roce", self.mod.RECIPE_ENV["TF_GLM_COMM"])
        for key in ("NCCL_IB_HCA", "NCCL_SOCKET_IFNAME", "TF_ROCE_HCA"):
            self.assertNotIn(key, self.mod.RECIPE_ENV)

    def test_compile_caches_are_persistent(self) -> None:
        for key in ("TORCH_EXTENSIONS_DIR", "TRITON_CACHE_DIR", "HOME"):
            self.assertTrue(self.mod.RECIPE_ENV[key].startswith("/cache/runtime"), key)


class ModFiles(unittest.TestCase):
    def test_mod_ships_its_harness(self) -> None:
        # A lane mod without run.sh is a fail-closed error in tests/test_mods_lane_locality.py.
        self.assertTrue((SHIM.parent / "run.sh").is_file())

    def test_gate_refuses_a_non_patched_engine(self) -> None:
        """The run.sh gate must name the checks that identify the patched build."""
        gate = (SHIM.parent / "run.sh").read_text()
        self.assertIn('die', gate)
        self.assertIn("choices=(1, 2, 3, 4)", gate)          # patch 0066: --tp 4
        for marker in ("TF_GLM_SIDE", "TF_GLM_PROMPT_OWN_FRONT", "TF_GLM_PROMPT_MICROBATCH"):
            self.assertIn(marker, gate)                     # the TP=4 switches RECIPE_ENV sets
        self.assertIn("tf-patches", gate)


if __name__ == "__main__":
    unittest.main()