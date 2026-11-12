"""A campaign lease refuses the drip exactly like a declared window, and for the same reason.

Measured 2026-11-07: the four `Campaign` cases read `tools/queue-drip.py`'s *real* `LOCK_PATHS`,
so the window this checkout legitimately declared made every one of them refuse with rc 3 before
their own lease logic ran. The isolation belongs in the tests rather than in the tool: a lock is a
promise to other sessions and the tool is right to stop for it. What these cases pin is the parity
that isolation would otherwise hide -- a leased host is withheld from the planner with no lock in
sight, and a fleet whose every node is leased refuses with rc 3 and the holder's own reason, never
with an empty plan.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "queue_drip_parity", Path(__file__).resolve().parent.parent / "tools" / "queue-drip.py")
drip = importlib.util.module_from_spec(_spec)
sys.modules["queue_drip_parity"] = drip
_spec.loader.exec_module(drip)


def config(tmp: str, body: str) -> Path:
    path = Path(tmp) / "fleet.yaml"
    path.write_text(body, encoding="utf-8")
    return path


def leased_root(tmp: str, hosts, name: str = "d1", attempt: int = 2) -> Path:
    root = Path(tmp) / "campaign"
    root.mkdir()
    now = time.time()
    lease = {"id": "arm@1", "arm": "arm", "path": "recipes/x/arm.yaml", "tp": len(hosts),
             "env": {}, "worker": "w1", "hosts": hosts, "issued_at": now - 60,
             "heartbeat_at": now - 5, "expires_at": now + 600}
    root.joinpath("state.json").write_text(json.dumps({
        "campaign": name, "order": ["arm"],
        "arms": {"arm": {"status": "leased", "attempts": attempt, "lease": lease}},
    }), encoding="utf-8")
    return root


class LeaseParity(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        # No real lock: these cases are about the lease gate, and a checkout may be declaring a
        # window while a campaign runs -- exactly the state this file was written in.
        self.lock = self.dir / "fleet-window.lock"
        original_lock_paths = drip.LOCK_PATHS
        self.addCleanup(setattr, drip, "LOCK_PATHS", original_lock_paths)
        drip.LOCK_PATHS = (self.lock,)
        self.planned = []
        original_plan = drip.plan_pass

        def fake_plan(cfg, busy=frozenset(), nodes=None):
            self.planned.append(list(nodes or []))
            return []

        self.addCleanup(setattr, drip, "plan_pass", original_plan)
        drip.plan_pass = fake_plan

    def run_drip(self, research: str, *extra: str):
        cfg = config(self.tmp.name, research)
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            rc = drip.main(["--config", str(cfg), "--state", str(self.dir / "state.json"),
                            "--campaign-env", str(self.dir / "absent.env"),
                            "--once", "--dry-run", *extra])
        return rc, out.getvalue()

    def test_every_node_leased_refuses_just_as_a_declared_window_does(self):
        rc, _out = self.run_drip("research:\n  - node-a\n")
        self.assertEqual((rc, self.planned[-1]), (0, ["node-a"]), "baseline: a free node is planned")

        self.lock.write_text("session: someone\n", encoding="utf-8")
        rc_lock, out_lock = self.run_drip("research:\n  - node-a\n")
        self.lock.unlink()
        before = len(self.planned)

        root = leased_root(self.tmp.name, ["node-a"])
        rc_lease, out_lease = self.run_drip("research:\n  - node-a\n", "--campaign-root", str(root))

        self.assertEqual((rc_lock, rc_lease), (3, 3), "a lease refuses like a lock, not with a plan")
        self.assertIn("unparseable declaration, still hands off", out_lock)
        self.assertIn("every node this session may use is held", out_lease)
        self.assertIn("campaign d1 holds node-a", out_lease)
        self.assertIn("attempt 2", out_lease)
        self.assertNotIn("campaign", out_lock, "the lock names itself and no campaign")
        self.assertEqual(len(self.planned), before, "a refused fleet is never handed to the planner")

    def test_a_leased_host_never_reaches_the_planner(self):
        root = leased_root(self.tmp.name, ["node-a"])
        rc, out = self.run_drip("research:\n  - node-a\n  - node-c\n",
                                "--campaign-root", str(root))
        self.assertEqual(rc, 0)
        self.assertEqual(self.planned[-1], ["node-c"], "the leased host must not be offered")
        self.assertIn("campaign d1 holds node-a", out)


if __name__ == "__main__":
    unittest.main()
