"""A llama.cpp arm must ask for GPU offload, and its receipt must prove it got it.

Why this exists (queue row `llamacpp-arms-declare-offload`, 2026-11-11). A
llama.cpp server launched without an offload flag (``--n-gpu-layers``/``-ngl``)
runs on CPU and reads as "slow but working": every health probe passes, the
ladder produces numbers, and nothing in the receipt distinguishes it from a GPU
serve. The shipped GSQ-RCO arm on ``.35`` was suspected of exactly that and was
falsified (its args carry ``--n-gpu-layers 999``; the serve log says
``offloaded 41/41 layers to GPU`` with ``CUDA0 model buffer size = 68342.87 MiB``),
so this guards the class, not that arm:

* the recipe-side check is over shipped ``runtime: llama-cpp`` arms -- the flag
  must be in ``command:``, or the arm must declare a deliberate CPU-only serve
  with a whole-line ``# offload: none`` comment (stripped text cannot carry the
  declaration, so it is read from the raw file);
* the receipt-side check is the real block from ``tools/run-arm.sh``, executed
  here against synthetic serve logs: the log witness is
  ``offloaded N/N layers to GPU`` plus a non-zero ``CUDA0 model buffer size``,
  a low tok/s is never evidence, and an arm whose log cannot prove offload
  fails its receipt (``rc=8``) rather than passing silently.

Every guard has a negative control: the flag is removed from a real recipe, the
declaration is removed from a declared arm, and the CUDA0 half of the receipt
check is mutated out so a CPU-only log must then pass (proving that half is what
catches it).
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.test_metrics_rollout import parse_text

REPO_ROOT = Path(__file__).resolve().parent.parent
RECIPE_GLOB = "recipes/*/*.yaml"
TOOL = REPO_ROOT / "tools" / "run-arm.sh"

# `--n-gpu-layers 999`, `--n-gpu-layers=999`, `-ngl 999`.  A whole-line comment is
# already stripped by parse_text, so a comment naming the flag cannot pass.
FLAG_RE = re.compile(r"--n-gpu-layers(?:[= ]\s*\S)|-ngl(?:[= ]\s*\S)")
DECLARED_RE = re.compile(r"(?m)^[ \t]*#[ \t]*offload:[ \t]*none\b")

BLOCK_START = "# llamacpp-offload: start"
BLOCK_END = "# llamacpp-offload: end"
STOP_LINE = 'sparkrun stop "$TID" 2>&1 | tail -1'


def read_tool() -> str:
    assert TOOL.exists(), f"missing {TOOL}"
    return TOOL.read_text()


def offload_block(text: str) -> str:
    """The receipt assertion verbatim, so its own control flow is what runs."""
    start = text.index(BLOCK_START)
    return text[start : text.index(BLOCK_END, start) + len(BLOCK_END)]


def recipe_violations(raw: str) -> list[str]:
    """Reasons this recipe can serve on CPU without saying so; empty means compliant."""
    recipe = parse_text(raw)
    if recipe["top"].get("runtime") != "llama-cpp":
        return []
    if FLAG_RE.search(recipe["command"]):
        return []
    if DECLARED_RE.search(raw):
        return []
    return ["llama.cpp command has no --n-gpu-layers/-ngl and no '# offload: none' declaration"]


def llamacpp_recipes() -> list[tuple[Path, str]]:
    found = []
    for path in sorted(REPO_ROOT.glob(RECIPE_GLOB)):
        raw = path.read_text(encoding="utf-8")
        if parse_text(raw)["top"].get("runtime") == "llama-cpp":
            found.append((path, raw))
    return found


GPU_LOG = (
    "load_tensors: offloading 39 repeating layers to GPU\n"
    "load_tensors: offloaded 41/41 layers to GPU\n"
    "llama_memory_recurrent: CUDA0 model buffer size = 68342.87 MiB\n"
)
CPU_LOG = (
    "load_tensors: offloaded 0/41 layers to GPU\n"
    "llama_memory_recurrent: CPU model buffer size = 68342.87 MiB\n"
    "llama_memory_recurrent: CUDA0 model buffer size = 0.00 MiB\n"
)
# The recipe pins `-lv 3`; measured on the 2026-11-12 .35 boot, the serve log then
# carries no loader lines at all -- this is the shape it really has at INFO.
INFO_LOG = (
    "0.00.337.800 I srv  llama_server: initializing ...\n"
    "0.00.337.805 I cmn  common_param: common_params_print_info: verbosity = 3 (adjust with the `-lv N` CLI arg)\n"
    "0.00.367.151 I srv    load_model: loading model '/cache/huggingface/hub/models--x/x.gguf'\n"
    "22.27.368.480 I srv  server_run_i: model loaded\n"
    "22.27.368.483 I srv  server_on_li: listening on http://0.0.0.0:8000\n"
)
RENDERED_FLAG = (
    "Serve command:\n"
    "  llama-server -m /cache/huggingface/hub/models--x/x.gguf --alias x --host 0.0.0.0\n"
    "  --port 8000 --ctx-size 32768 --parallel 2 --n-gpu-layers 999 --flash-attn auto\n"
)

# The shipped arm the row was measured on; its command is the positive fixture.
FIXTURE_RECIPE = "recipes/ds4/deepseek-v4.1-flash-1017-gsq-rco-coder-gguf-llamacpp.yaml"


def fixture_raw() -> str:
    return (REPO_ROOT / FIXTURE_RECIPE).read_text(encoding="utf-8")


def run_offload_block(recipe_raw: str, logs: dict[str, str],
                      block: str | None = None) -> tuple[str, dict[str, str]]:
    """Execute the run-arm block in a temp receipt; return output and *.txt files."""
    block = block if block is not None else offload_block(read_tool())
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        receipt = tmp / "receipt"
        receipt.mkdir()
        recipe = tmp / "recipe.yaml"
        recipe.write_text(recipe_raw)
        for name, body in logs.items():
            (receipt / name).write_text(body)
        script = tmp / "block.sh"
        script.write_text(
            "#!/usr/bin/env bash\n"
            "set -uo pipefail\n"
            "rc=0\n"
            f"RECIPE={recipe}\n"
            f"L={receipt}\n"
            f"{block}\n"
            'printf "rc=%s\\n" "$rc"\n'
        )
        out = subprocess.run(["bash", str(script)], capture_output=True, text=True, check=False)
        files = {p.name: p.read_text() for p in receipt.glob("*.txt")}
    return out.stdout + out.stderr, files


class ShippedLlamaCppArms(unittest.TestCase):
    def test_every_llamacpp_arm_asks_for_gpu_offload(self):
        arms = llamacpp_recipes()
        self.assertTrue(arms, "no llama.cpp recipes found; this guard would be vacuous")
        for path, raw in arms:
            with self.subTest(recipe=str(path.relative_to(REPO_ROOT))):
                self.assertEqual(recipe_violations(raw), [],
                                 f"{path.relative_to(REPO_ROOT)}: {recipe_violations(raw)}")

    def test_the_fixture_recipe_is_the_positive_case(self):
        self.assertEqual(recipe_violations(fixture_raw()), [])


class RecipeNegativeControls(unittest.TestCase):
    def test_dropping_the_flag_fails_the_guard(self):
        raw = fixture_raw()
        mutated = raw.replace("--n-gpu-layers {n_gpu_layers}", "")
        self.assertNotEqual(mutated, raw, "the fixture arm lost its flag; control vacuous")
        self.assertTrue(recipe_violations(mutated))

    def test_a_declared_cpu_only_arm_passes(self):
        raw = fixture_raw().replace("--n-gpu-layers {n_gpu_layers}", "")
        declared = raw.replace("command: >", "# offload: none — CPU-only probe\ncommand: >", 1)
        self.assertEqual(recipe_violations(declared), [])

    def test_removing_the_declaration_fails_the_guard(self):
        raw = fixture_raw().replace("--n-gpu-layers {n_gpu_layers}", "")
        declared = raw.replace("command: >", "# offload: none — CPU-only probe\ncommand: >", 1)
        undeclared = declared.replace("# offload: none — CPU-only probe\n", "")
        self.assertEqual(recipe_violations(declared), [])
        self.assertTrue(recipe_violations(undeclared))


class ReceiptAssertion(unittest.TestCase):
    """The run-arm block, executed: a serve log (or the rendered command) is the witness."""

    def setUp(self):
        if not shutil.which("bash"):
            self.skipTest("bash not on PATH")

    def test_a_gpu_serve_log_asserts_offload(self):
        out, files = run_offload_block(fixture_raw(), {"serve-solo.log": GPU_LOG})
        self.assertEqual(
            files.get("llamacpp-offload.txt", "").splitlines()[0],
            "llamacpp_offload: evidence=serve-log offloaded 41/41 layers to GPU; "
            "CUDA0 model buffer size = 68342.87 MiB (log: serve-solo.log)", out)
        self.assertEqual(out.strip().splitlines()[-1], "rc=0", out)

    def test_a_cpu_only_serve_log_fails_the_receipt(self):
        out, files = run_offload_block(fixture_raw(), {"serve-solo.log": CPU_LOG})
        self.assertIn("llamacpp_offload: FAIL", files.get("llamacpp-offload.txt", ""), out)
        self.assertEqual(out.strip().splitlines()[-1], "rc=8", out)

    def test_the_rendered_command_is_the_witness_at_info_verbosity(self):
        """The recipe pins -lv 3, where llama.cpp never prints the loader lines.

        Measured on the 2026-11-12 .35 boot: the serve log at lv 3 has no
        `offloaded`/`CUDA0` line at all, so the rendered serve line sparkrun wrote
        into launch.log is the runtime witness that the flag reached the engine.
        """
        logs = {"serve-solo.log": INFO_LOG, "launch.log": RENDERED_FLAG}
        out, files = run_offload_block(fixture_raw(), logs)
        self.assertIn("evidence=argv --n-gpu-layers 999",
                      files.get("llamacpp-offload.txt", ""), out)
        self.assertEqual(out.strip().splitlines()[-1], "rc=0", out)

    def test_a_rendered_command_without_a_flag_still_fails(self):
        logs = {"serve-solo.log": INFO_LOG,
                "launch.log": "Serve command:\n  llama-server -m /cache/x.gguf\n"}
        out, files = run_offload_block(fixture_raw(), logs)
        self.assertIn("llamacpp_offload: FAIL", files.get("llamacpp-offload.txt", ""), out)
        self.assertEqual(out.strip().splitlines()[-1], "rc=8", out)

    def test_a_rendered_zero_offload_flag_fails(self):
        logs = {"serve-solo.log": INFO_LOG,
                "launch.log": "Serve command:\n  llama-server -m /cache/x.gguf --n-gpu-layers 0\n"}
        out, files = run_offload_block(fixture_raw(), logs)
        self.assertIn("llamacpp_offload: FAIL", files.get("llamacpp-offload.txt", ""), out)
        self.assertEqual(out.strip().splitlines()[-1], "rc=8", out)

    def test_a_declared_cpu_only_arm_is_skipped(self):
        raw = fixture_raw().replace("command: >", "# offload: none — CPU-only probe\ncommand: >", 1)
        out, files = run_offload_block(raw, {"serve-solo.log": CPU_LOG})
        self.assertIn("skipped", files.get("llamacpp-offload.txt", ""), out)
        self.assertEqual(out.strip().splitlines()[-1], "rc=0", out)

    def test_a_non_llamacpp_arm_writes_no_verdict(self):
        raw = fixture_raw().replace("runtime: llama-cpp", "runtime: vllm")
        out, files = run_offload_block(raw, {"serve-solo.log": CPU_LOG})
        self.assertNotIn("llamacpp-offload.txt", files, out)
        self.assertEqual(out.strip().splitlines()[-1], "rc=0", out)

    def test_a_docker_capture_log_is_accepted(self):
        out, files = run_offload_block(fixture_raw(), {"docker-solo.log": GPU_LOG})
        self.assertIn("evidence=serve-log", files.get("llamacpp-offload.txt", ""), out)
        self.assertEqual(out.strip().splitlines()[-1], "rc=0", out)

    def test_no_log_at_all_fails_closed(self):
        out, files = run_offload_block(fixture_raw(), {})
        self.assertIn("no serve log in the receipt", files.get("llamacpp-offload.txt", ""), out)
        self.assertEqual(out.strip().splitlines()[-1], "rc=8", out)

    def test_the_assertion_runs_before_the_stop(self):
        text = read_tool()
        self.assertLess(text.index(BLOCK_START), text.index(STOP_LINE),
                        "the offload evidence is gathered after teardown")


class ReceiptNegativeControls(unittest.TestCase):
    def setUp(self):
        if not shutil.which("bash"):
            self.skipTest("bash not on PATH")

    def test_without_the_cuda0_check_a_cpu_log_passes(self):
        """The half this control removes is load-bearing: 0.00 MiB must fail."""
        block = offload_block(read_tool())
        mutated = block.replace(
            'if [ -n "$layers" ] && [ -n "$cuda0_mb" ] && awk -v v="$cuda0_mb" \'BEGIN{exit !(v > 0)}\'; then',
            'if [ -n "$layers" ]; then')
        self.assertNotEqual(mutated, block, "the CUDA0 check moved; control vacuous")
        out, files = run_offload_block(fixture_raw(), {"serve-solo.log": CPU_LOG}, block=mutated)
        self.assertIn("evidence=serve-log", files.get("llamacpp-offload.txt", ""), out)
        self.assertEqual(out.strip().splitlines()[-1], "rc=0", out)

    def test_without_the_positive_value_check_a_zero_flag_passes(self):
        """`--n-gpu-layers 0` is the CPU serve; the numeric check is what rejects it."""
        block = offload_block(read_tool())
        mutated = block.replace(
            '{ [ "$off_n" = all ] || awk -v v="$off_n" \'BEGIN{exit !(v > 0)}\'; }',
            'true')
        self.assertNotEqual(mutated, block, "the positive-value check moved; control vacuous")
        logs = {"serve-solo.log": INFO_LOG,
                "launch.log": "Serve command:\n  llama-server -m /cache/x.gguf --n-gpu-layers 0\n"}
        out, files = run_offload_block(fixture_raw(), logs, block=mutated)
        self.assertIn("evidence=argv", files.get("llamacpp-offload.txt", ""), out)
        self.assertEqual(out.strip().splitlines()[-1], "rc=0", out)


if __name__ == "__main__":
    unittest.main()