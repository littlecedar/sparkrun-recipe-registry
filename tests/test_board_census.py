"""Guards for tools/board-census.py — the fleet census as one documented evidence document.

Run:
    uv run python -B -m unittest tests.test_board_census -v

Stdlib-only, no network, no cluster: a fake `ssh` on PATH answers from fixture probe output keyed
by (mode, host), so the tool's own parsing, schema and delta arithmetic are exercised without one
byte leaving the machine.  The failure path is a host the stub refuses to answer for.

What is pinned:
* the schema — every documented top-level key, the per-node fields the board's cells read, the
  head extras (units, campaign, window lock, lease ledger, register sha);
* a node that cannot answer is `{"error": ...}` in its entry and the census still exits 0;
* deltas against a named previous document, and the default "newest older evidence" base;
* non-zero exit only when the evidence file cannot be written.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOL = REPO_ROOT / "tools" / "board-census.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "board"

#: `-n -o BatchMode=yes -o ConnectTimeout=30 HOST "printf %s <b64> | base64 -d | bash -s -- node L B"`.
#: The last argument names the mode, so the stub answers per (mode, host) from fixtures.
SSH_STUB = """#!/bin/sh
for last do :; done
host=""; prev=""
for arg in "$@"; do
  if [ "$prev" = "-o" ]; then prev="$arg"; continue; fi
  case "$arg" in
    -*) prev="$arg" ;;
    *) host="$arg"; break ;;
  esac
done
case "$last" in
  *"bash -s -- head"*) mode=head ;;
  *"bash -s -- node"*) mode=node ;;
  *) echo "fake ssh: unknown command: $last" >&2; exit 255 ;;
esac
echo "$host $mode" >> "$CALLS"
if [ -n "$FAIL_HOST" ] && [ "$host" = "$FAIL_HOST" ]; then
  echo "ssh: connect to host $host port 22: Connection timed out" >&2
  exit 255
fi
file="$FIXTURES/$mode-$host.txt"
[ -f "$file" ] || { echo "fake ssh: no fixture for $host ($mode)" >&2; exit 255; }
cat "$file"
"""


def _load():
    spec = importlib.util.spec_from_file_location("board_census", TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules["board_census"] = module
    spec.loader.exec_module(module)
    return module


census = _load()


class CensusTool(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.calls = self.root / "calls.log"
        stub = self.bin / "ssh"
        stub.write_text(SSH_STUB, encoding="utf-8")
        stub.chmod(0o755)
        # The head fixture's `register_sha` is a stub answer, not a fact about today's register:
        # pinning it to the sha the register had when the fixture was cut made every queue.json
        # write redden this test (measured 2026-11-22, the summaries commit). Derive it instead.
        self.fixtures = self.root / "fixtures"
        shutil.copytree(FIXTURES, self.fixtures)
        head = self.fixtures / "head-n30.txt"
        register_sha = hashlib.sha256(
            (REPO_ROOT / "mad-science" / "queue.json").read_bytes()).hexdigest()
        head.write_text(re.sub(r"(?m)^register_sha\|.*$", f"register_sha|{register_sha}",
                               head.read_text(encoding="utf-8")), encoding="utf-8")
        self.env = dict(os.environ, PATH=f"{self.bin}:{os.environ['PATH']}",
                        FIXTURES=str(self.fixtures), CALLS=str(self.calls), FAIL_HOST="")

    def run_tool(self, *args, env=None):
        return subprocess.run([sys.executable, "-B", str(TOOL), *args],
                              capture_output=True, text=True, env=env or self.env)

    def census(self, *args, env=None):
        proc = self.run_tool(*args, env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return Path(proc.stdout.strip())

    def test_writes_the_documented_schema(self):
        path = self.census("--out", str(self.root / "evidence"),
                           "--node", "n30", "--node", "n31", "--node", "n32",
                           env=dict(self.env, FAIL_HOST="n32"))
        self.assertTrue(path.is_file())
        self.assertRegex(path.name, r"^\d{4}-\d\d-\d\dT\d{6}Z\.json$")
        document = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(set(document),
                         {"version", "at", "base", "nodes", "head", "register", "notes"})
        self.assertEqual(document["version"], 1)
        self.assertIsNone(document["base"], "a first run has no base")

        node = document["nodes"]["n30"]
        self.assertEqual(node["read"], "2026-11-22T01:12:34Z")
        self.assertEqual(node["host"], "node-thirty")
        self.assertEqual((node["containers_all"], node["containers_running"], node["volumes"]), (0, 0, 0))
        self.assertEqual(node["root"], {"size": 4031871553536, "used": 2660770533376,
                                        "avail": 1371101020160})
        self.assertEqual(node["mem"], {"MemTotal": 127598704, "MemAvailable": 121141800,
                                       "Cached": 24799356, "AnonPages": 1089548})
        self.assertEqual(node["btime"], 1795118800)
        self.assertEqual(node["uptime_s"], 191154)
        self.assertEqual(node["ring"]["all"], 256)
        self.assertEqual(node["ring"]["window"], {"lifecycle": 0, "exec": 0})
        self.assertIsNone(node["serve"], "no listener: no serve probe")

        served = document["nodes"]["n31"]
        self.assertEqual(served["listeners_8000"], 2)
        self.assertEqual(served["serve"], {"models": 200, "health": 200})
        self.assertEqual(served["ring"]["window"]["exec"], 80)

        self.assertIn("error", document["nodes"]["n32"])
        self.assertTrue(document["nodes"]["n32"]["error"])

        head = document["head"]
        self.assertEqual(head["read"], "2026-11-22T01:12:36Z")
        self.assertEqual(head["units"]["beegfs-meta"],
                         {"active": "activating", "result": "exit-code", "restarts": 36536})
        self.assertEqual(head["units"]["beegfs-storage"],
                         {"active": "active", "result": "success", "restarts": 0})
        self.assertEqual(head["campaign"], {"active": "active", "sub": "running",
                                            "pid": 3930275, "restarts": 0})
        self.assertEqual(head["window_lock"], {"present": False})
        self.assertEqual(head["register_sha256"], document["register"]["sha256"])
        ledger = head["lease_ledger"]
        self.assertEqual(ledger["size"], 389)
        self.assertEqual(ledger["fenced"][0]["fenced_by"], "tp-le2-20261120")
        self.assertEqual(ledger["fenced"][0]["hosts"], [".31", ".32", ".33", ".34"])
        self.assertEqual([lease["id"] for lease in ledger["leases"]], ["lease-1", "lease-0"])
        self.assertEqual(ledger["leases"][0]["hosts"], [".30"])

        self.assertEqual(len(document["register"]["sha256"]), 64)
        self.assertEqual(document["register"]["path"], "mad-science/queue.json")
        self.assertEqual(document["notes"], ["n32: ssh: connect to host n32 port 22: "
                                             "Connection timed out"])

        calls = self.calls.read_text(encoding="utf-8").splitlines()
        self.assertEqual(calls, ["n30 node", "n31 node", "n32 node", "n30 head"],
                         "one hop per node plus one for the head extras, nothing else")

    def test_delta_against_a_named_previous_file(self):
        previous = {"version": 1, "at": "2026-11-22T00:13:44Z", "base": None,
                    "nodes": {
                        "n30": {"read": "2026-11-22T00:13:43Z", "host": "node-thirty",
                                "containers_all": 0, "containers_running": 0, "volumes": 0,
                                "listeners_8000": 0, "uptime_s": 189806,
                                "root": {"size": 4031871553536,
                                         "used": 2660770817024, "avail": 1371100736512},
                                "mem": {"MemTotal": 127598704, "MemAvailable": 121141572,
                                        "Cached": 24514776, "AnonPages": 1126852},
                                "ring": {"all": 250, "window": {"lifecycle": 0, "exec": 0}}},
                        "n31": {"read": "2026-11-22T00:13:44Z", "host": "node-thirty-one",
                                "containers_all": 1, "containers_running": 1, "volumes": 0,
                                "listeners_8000": 2, "uptime_s": 189531,
                                "root": {"size": 4031871553536,
                                         "used": 2382079557376, "avail": 1649791996160},
                                "mem": {"MemAvailable": 7829084},
                                "ring": {"all": 256, "window": {"lifecycle": 0, "exec": 80}}}},
                    "head": {"read": "2026-11-22T00:13:43Z",
                             "units": {"beegfs-meta": {"active": "activating",
                                                       "result": "exit-code",
                                                       "restarts": 36530}},
                             "campaign": {"active": "active", "sub": "running", "pid": 1,
                                          "restarts": 0}},
                    "register": {}, "notes": []}
        prev_path = self.root / "previous.json"
        prev_path.write_text(json.dumps(previous), encoding="utf-8")

        path = self.census("--out", str(self.root / "evidence"),
                           "--node", "n30", "--node", "n31", "--prev", str(prev_path))
        document = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(document["base"], "2026-11-22T00:13:43Z")
        delta = document["nodes"]["n30"]["delta"]
        self.assertEqual(delta["avail"], 1371101020160 - 1371100736512)
        self.assertEqual(delta["used"], 2660770533376 - 2660770817024)
        self.assertEqual(delta["mem"]["MemAvailable"], 121141800 - 121141572)
        self.assertEqual(delta["uptime_s"], 191154 - 189806)
        self.assertEqual(delta["ring"]["all"], 256 - 250)
        self.assertEqual(delta["ring"]["window_exec"], 0)
        self.assertEqual(delta["containers_all"], 0)
        self.assertEqual(document["head"]["delta"]["restarts"]["beegfs-meta"], 6)
        self.assertEqual(document["head"]["delta"]["campaign_restarts"], 0)

    def test_the_newest_older_evidence_file_is_the_default_base(self):
        out = self.root / "evidence"
        out.mkdir()
        older = {"version": 1, "at": "2026-11-21T00:00:00Z", "base": None,
                 "nodes": {"n30": {"read": "2026-11-21T00:00:01Z",
                                   "containers_all": 0, "containers_running": 0, "volumes": 0,
                                   "listeners_8000": 0, "uptime_s": 180000,
                                   "root": {"size": 4031871553536,
                                            "used": 4031871553536 - 1371100000000,
                                            "avail": 1371100000000},
                                   "mem": {"MemAvailable": 121000000},
                                   "ring": {"all": 200, "window": {"lifecycle": 0, "exec": 0}}}},
                 "head": {}, "register": {}, "notes": []}
        (out / "2026-11-21T000000Z.json").write_text(json.dumps(older), encoding="utf-8")
        future = dict(older, at="2999-01-01T00:00:00Z")
        (out / "2999-01-01T000000Z.json").write_text(json.dumps(future), encoding="utf-8")

        path = self.census("--out", str(out), "--node", "n30")
        document = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(document["base"], "2026-11-21T00:00:01Z")
        self.assertEqual(document["nodes"]["n30"]["delta"]["avail"],
                         1371101020160 - 1371100000000)
        self.assertEqual(document["nodes"]["n30"]["delta"]["mem"]["MemAvailable"], 141800)

    def test_exit_is_non_zero_only_when_the_evidence_cannot_be_written(self):
        blocked = self.root / "not-a-directory"
        blocked.write_text("", encoding="utf-8")
        proc = self.run_tool("--out", str(blocked), "--node", "n30")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("cannot create", proc.stderr)

    def test_an_unreadable_previous_file_is_a_note_not_a_crash(self):
        path = self.census("--out", str(self.root / "evidence"), "--node", "n30",
                           "--prev", str(self.root / "missing.json"))
        document = json.loads(path.read_text(encoding="utf-8"))
        self.assertIsNone(document["base"])
        self.assertTrue(any("unreadable" in note for note in document["notes"]))

    def test_node_labels_come_from_the_last_octet(self):
        # 127.0.0.0/8 on purpose: this tracked file must carry no cluster address.
        self.assertEqual(census.label_for("127.0.0.31"), ".31")
        self.assertEqual(census.label_for("n30"), "n30")


if __name__ == "__main__":
    unittest.main()
