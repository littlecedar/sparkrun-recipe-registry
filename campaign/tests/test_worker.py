"""The worker's one job: hand the lease to the executor untouched, and keep what it printed.

The lease is the contract between the director's state and the executor's argv. A lease that
carried no recipe path crashed every worker on its first arm and left it leased until the TTL -- a
smoke run found it, and these tests keep it found.
"""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any

from sparkrun_campaign import worker

SCRIPT = """\
#!/usr/bin/env bash
printf '%s\\n' "$@" > "$OUT/argv.txt"
printf 'opts=%s\\n' "${ARM_OPTS:-}" > "$OUT/env.txt"
echo "executor output"
exit "${EXIT_RC:-0}"
"""


class Executor(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.executor = self.root / "fake-run-arm.sh"
        self.executor.write_text(SCRIPT, encoding="utf-8")
        self.executor.chmod(0o755)
        self.logs = self.root / "logs"
        self.logs.mkdir()
        self.lease: dict[str, Any] = {
            "id": "arm@1",
            "arm": "arm",
            "path": "recipes/lane/arm.yaml",
            "tp": 2,
            "env": {"ARM_OPTS": "-o parallel=10", "OUT": str(self.root)},
            "hosts": ["node-a", "node-b"],
            "expires_at": 0.0,
        }

    def test_the_executor_gets_the_recipe_path_and_the_host_list(self) -> None:
        rc, _ = worker.run_arm(self.lease, self.executor, self.logs)
        self.assertEqual(rc, 0)
        argv = (self.root / "argv.txt").read_text(encoding="utf-8").split("\n")
        self.assertEqual(argv[:2], ["recipes/lane/arm.yaml", "node-a,node-b"])

    def test_the_arms_environment_reaches_the_executor(self) -> None:
        worker.run_arm(self.lease, self.executor, self.logs)
        self.assertEqual((self.root / "env.txt").read_text(encoding="utf-8").strip(),
                         "opts=-o parallel=10")

    def test_the_executors_exit_code_is_the_arms_return_code(self) -> None:
        self.lease["env"]["EXIT_RC"] = "6"
        rc, _ = worker.run_arm(self.lease, self.executor, self.logs)
        self.assertEqual(rc, 6)

    def test_one_log_per_attempt_holds_the_output_and_the_command(self) -> None:
        _, log_path = worker.run_arm(self.lease, self.executor, self.logs)
        text = Path(log_path).read_text(encoding="utf-8")
        self.assertTrue(Path(log_path).name.startswith("arm@1"))
        self.assertIn("fake-run-arm.sh recipes/lane/arm.yaml node-a,node-b", text)
        self.assertIn("executor output", text)


if __name__ == "__main__":
    unittest.main()