"""A keyed arm's variable name travels register -> lease -> executor; its value never does.

`tools/run-arm.sh` passes `--api-key-env <name>` to sparkrun when `ARM_API_KEY_ENV` is set, so the
register row declares the name and the campaign service's environment holds the key. These tests
run the handoff through the director and one throwaway executor, and re-run it against mutated
worker source to show the guard can fail.
"""

from __future__ import annotations

import json
import os
import subprocess
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from sparkrun_campaign import protocol, worker

from . import test_director

SCRIPT = """\
#!/bin/sh
printf 'argv=%s\\n' "$*" > "{seen}"
printf 'name=%s\\n' "${{ARM_API_KEY_ENV-<unset>}}" >> "{seen}"
printf 'key=%s\\n' "${{PICOM_API_KEY-<unset>}}" >> "{seen}"
"""


def run_arm_from_source(mutation: tuple[str, str]) -> Any:
    """The shipped `run_arm` with one text mutation, executed -- not the imported copy."""
    source = Path(worker.__file__).read_text(encoding="utf-8")
    start = source.index("\ndef run_arm(")
    body = source[start + 1:source.index("\n\ndef main(", start)]
    old, new = mutation
    if old not in body:
        raise AssertionError(f"mutation target not found in run_arm source: {old!r}")
    body = body.replace(old, new, 1)
    namespace: dict[str, Any] = {"os": os, "subprocess": subprocess, "Path": Path}
    exec("from __future__ import annotations\n\n" + body, namespace)  # noqa: S102 - the control
    return namespace["run_arm"]


class KeyedArmEnv(test_director.CampaignCase):
    SECRET = "picom-secret-not-in-any-tracked-file"

    def setUp(self) -> None:
        super().setUp()
        self.manifest_path.write_text(json.dumps([
            {"arm": "arm-one", "path": "recipes/lane/arm-one.yaml", "tp": 2,
             "env": {"ARM_API_KEY_ENV": "PICOM_API_KEY"}},
            {"arm": "arm-two", "path": "recipes/lane/arm-two.yaml", "tp": 1},
        ]) + "\n", encoding="utf-8")
        self.seen = self.tmp / "executor-env.txt"
        self.executor = self.tmp / "fake-run-arm.sh"
        self.executor.write_text(SCRIPT.format(seen=self.seen), encoding="utf-8")
        self.executor.chmod(0o755)
        self.logs = self.tmp / "logs"
        self.logs.mkdir()

    def lease(self) -> dict[str, Any]:
        leader, _ = self.build()
        leader.prepare()
        lease = leader.handle(protocol.poll("w1"))["lease"]
        self.assertEqual(lease["arm"], "arm-one")
        return lease

    def observe(self, run_arm, lease: dict[str, Any]) -> dict[str, str]:
        if self.seen.exists():
            self.seen.unlink()
        with mock.patch.dict(os.environ, {"PICOM_API_KEY": self.SECRET}):
            rc, log_path = run_arm(lease, self.executor, self.logs)
        self.assertEqual(rc, 0)
        lines = self.seen.read_text(encoding="utf-8").splitlines()
        seen = dict(line.split("=", 1) for line in lines)
        self.assertNotIn(self.SECRET, Path(log_path).read_text(encoding="utf-8"),
                         "the key value reached the executor log")
        return seen

    def test_the_rows_variable_name_reaches_the_executor_while_the_key_stays_in_the_service_env(
            self) -> None:
        lease = self.lease()
        self.assertEqual(lease["env"]["ARM_API_KEY_ENV"], "PICOM_API_KEY")
        self.assertEqual(lease["env"]["ARM_RECEIPTS_ROOT"], str(self.receipts))
        self.assertNotIn(self.SECRET, self.manifest_path.read_text(encoding="utf-8"),
                         "the key value must stay out of the register row")

        seen = self.observe(worker.run_arm, lease)
        self.assertEqual(seen["name"], "PICOM_API_KEY")
        self.assertEqual(seen["key"], self.SECRET,
                         "the key must be inherited from the service environment")
        self.assertNotIn(self.SECRET, seen["argv"], "the key value reached the executor argv")

    def test_the_rows_cells_survive_and_the_runs_receipts_root_wins(self) -> None:
        leader, _ = self.build()
        env = leader._env_for({"ARM_API_KEY_ENV": "PICOM_API_KEY",
                               "ARM_RECEIPTS_ROOT": "/somewhere/else"})
        self.assertEqual(env["ARM_API_KEY_ENV"], "PICOM_API_KEY")
        self.assertEqual(env["ARM_RECEIPTS_ROOT"], str(self.receipts),
                         "the run's receipts root must win over a stale row cell")

    def test_control_a_clean_or_lease_dropping_worker_loses_the_chain(self) -> None:
        lease = self.lease()
        for mutation, field, value in (
            (("environment = dict(os.environ)", "environment = {}"), "key", self.SECRET),
            (('lease.get("env") or {}', "{}"), "name", "PICOM_API_KEY"),
        ):
            with self.subTest(mutation=mutation[0]):
                seen = self.observe(run_arm_from_source(mutation), lease)
                self.assertNotEqual(seen[field], value,
                                    f"the control did not remove {field}: {mutation}")
                self.assertFalse(seen["name"] == "PICOM_API_KEY"
                                 and seen["key"] == self.SECRET,
                                 f"the guard survived the mutation {mutation}; the control is void")


if __name__ == "__main__":
    unittest.main()
