"""Guards for tools/enable-io-uring.py — the fleet-wide seccomp replacement.

Run:
    uv run python -B -m unittest discover -s tests

Stdlib-only, no network, no Docker, like every other guard here.

Why this file exists.  The tool replaces Docker's built-in seccomp profile for *every* container on
a node, and it restarts the daemon to do it.  The live run (`tools/enable-io-uring.sh --probe-only`
then the change itself, 2026-10-26) is the evidence that it works; what a live run cannot show is
that it grants exactly what it claims and nothing else.  That is what these tests pin:

* the modified profile gains the three io_uring syscalls and nothing else — no lost allow rule, no
  touched deny rule (`test_modification_touches_only_the_three_syscalls`);
* an unmodified profile *fails* the structural check, so a profile missing the three syscalls can
  never be reported as enabled (negative control,
  `test_unmodified_profile_fails_the_structural_check`);
* an extra grant, a dropped rule and a changed deny rule are all refused;
* `daemon.json` keeps every key it already had;
* a node with a running container is skipped rather than restarted.

Nothing here re-implements the tool.  The fixture below is the shape of moby's default profile
(`defaultAction` ERRNO + allowlist + the `clone3` deny), trimmed to a handful of blocks: the
arguments are the measurement, and the assertions are the properties.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOL = REPO_ROOT / "tools" / "enable-io-uring.py"

#: Shape of moby's default profile at v28.5.2 (`vendor/github.com/moby/profiles/seccomp/default.json`,
#: sha256 01536f1d…): allowlist with `defaultErrnoRet: 1`, one deliberate `clone3` deny, and — the
#: whole point — no io_uring name anywhere, so the three syscalls fall through to EPERM.
BASE_PROFILE = {
    "defaultAction": "SCMP_ACT_ERRNO",
    "defaultErrnoRet": 1,
    "archMap": [
        {"architecture": "SCMP_ARCH_X86_64", "subArchitectures": ["SCMP_ARCH_X86", "SCMP_ARCH_X32"]},
        {"architecture": "SCMP_ARCH_AARCH64", "subArchitectures": ["SCMP_ARCH_ARM"]},
    ],
    "syscalls": [
        {"names": ["accept", "accept4", "bind", "brk", "close", "epoll_create", "read", "write"], "action": "SCMP_ACT_ALLOW"},
        {"names": ["clone"], "action": "SCMP_ACT_ALLOW"},
        {"names": ["perf_event_open"], "action": "SCMP_ACT_ALLOW", "includes": {"caps": ["CAP_PERFMON"]}},
        {"names": ["clone3"], "action": "SCMP_ACT_ERRNO", "errnoRet": 38, "excludes": {"caps": ["CAP_SYS_ADMIN"]}},
    ],
}


def _load():
    spec = importlib.util.spec_from_file_location("enable_io_uring", TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules["enable_io_uring"] = module  # dash-named tool convention
    spec.loader.exec_module(module)
    return module


TOOL_MODULE = _load()


class ProfileModification(unittest.TestCase):
    def setUp(self):
        self.base = json.loads(json.dumps(BASE_PROFILE))  # fresh copy per test
        self.modified = TOOL_MODULE.add_io_uring_allows(self.base)

    def test_base_profile_denies_io_uring(self):
        self.assertFalse(TOOL_MODULE.profile_has_io_uring(self.base))
        for name in TOOL_MODULE.IO_URING_SYSCALLS:
            self.assertNotIn(name, json.dumps(self.base))

    def test_modification_touches_only_the_three_syscalls(self):
        gained = TOOL_MODULE.allow_names(self.modified) - TOOL_MODULE.allow_names(self.base)
        lost = TOOL_MODULE.allow_names(self.base) - TOOL_MODULE.allow_names(self.modified)
        self.assertEqual(gained, set(TOOL_MODULE.IO_URING_SYSCALLS))
        self.assertEqual(lost, set())
        self.assertEqual(len(self.modified["syscalls"]), len(self.base["syscalls"]) + 1)
        self.assertEqual(self.modified["defaultAction"], self.base["defaultAction"])
        self.assertEqual(self.modified["defaultErrnoRet"], self.base["defaultErrnoRet"])
        self.assertEqual(self.modified["archMap"], self.base["archMap"])
        self.assertEqual(
            [b for b in self.modified["syscalls"] if b["action"] != "SCMP_ACT_ALLOW"],
            [b for b in self.base["syscalls"] if b["action"] != "SCMP_ACT_ALLOW"],
        )
        self.assertTrue(TOOL_MODULE.profile_has_io_uring(self.modified))

    def test_input_profile_is_not_mutated(self):
        self.assertEqual(self.base, BASE_PROFILE)

    def test_add_is_idempotent(self):
        again = TOOL_MODULE.add_io_uring_allows(self.modified)
        self.assertEqual(again, self.modified)

    def test_unmodified_profile_fails_the_structural_check(self):
        """Negative control: a profile without the three syscalls must never validate as finished."""
        with self.assertRaises(ValueError):
            TOOL_MODULE.validate_modified_profile(self.base, self.base)
        TOOL_MODULE.validate_modified_profile(self.base, self.modified)  # the real edit passes

    def test_extra_grant_is_refused(self):
        extra = copy.deepcopy(self.modified)
        extra["syscalls"].append({"names": ["bpf"], "action": "SCMP_ACT_ALLOW"})
        with self.assertRaises(ValueError):
            TOOL_MODULE.validate_modified_profile(self.base, extra)

    def test_dropped_allow_rule_is_refused(self):
        dropped = copy.deepcopy(self.modified)
        dropped["syscalls"].pop(0)
        with self.assertRaises(ValueError):
            TOOL_MODULE.validate_modified_profile(self.base, dropped)

    def test_changed_deny_rule_is_refused(self):
        relaxed = copy.deepcopy(self.modified)
        for block in relaxed["syscalls"]:
            if block["action"] != "SCMP_ACT_ALLOW":
                block["action"] = "SCMP_ACT_ALLOW"
        with self.assertRaises(ValueError):
            TOOL_MODULE.validate_modified_profile(self.base, relaxed)

    def test_explicit_deny_of_io_uring_in_base_is_refused(self):
        hostile = copy.deepcopy(BASE_PROFILE)
        hostile["syscalls"].append({"names": ["io_uring_setup"], "action": "SCMP_ACT_ERRNO", "errnoRet": 1})
        with self.assertRaises(ValueError):
            TOOL_MODULE.add_io_uring_allows(hostile)


class DaemonJsonMerge(unittest.TestCase):
    def test_unrelated_keys_survive(self):
        existing = {
            "data-root": "/var/lib/docker",
            "runtimes": {"nvidia": {"path": "nvidia-container-runtime", "args": []}},
            "features": {"containerd-snapshotter": True},
            "seccomp-profile": "/etc/docker/seccomp-profiles/old.json",
        }
        merged = TOOL_MODULE.merge_daemon_json(existing, str(TOOL_MODULE.PROFILE_PATH))
        self.assertEqual(merged["seccomp-profile"], "/etc/docker/seccomp-profiles/io-uring.json")
        for key in ("data-root", "runtimes", "features"):
            self.assertEqual(merged[key], existing[key])
        self.assertEqual(set(merged), set(existing))
        self.assertEqual(existing["seccomp-profile"], "/etc/docker/seccomp-profiles/old.json")

    def test_empty_config_gets_only_the_profile(self):
        self.assertEqual(
            TOOL_MODULE.merge_daemon_json({}, "/p.json"), {"seccomp-profile": "/p.json"}
        )


class RestartSafety(unittest.TestCase):
    def test_running_container_aborts_the_node(self):
        with self.assertRaises(SystemExit) as caught:
            TOOL_MODULE.require_idle(["9c8e0fffc3cb"], "spark-03")
        self.assertIn("abort", str(caught.exception))
        self.assertIn("spark-03", str(caught.exception))

    def test_idle_node_passes(self):
        TOOL_MODULE.require_idle([], "spark-03")

    def test_container_ids_parse(self):
        self.assertEqual(TOOL_MODULE.parse_container_ids("abc\n\ndef\n"), ["abc", "def"])
        self.assertEqual(TOOL_MODULE.parse_container_ids(""), [])


class TagSelection(unittest.TestCase):
    def test_only_stable_version_tags_count(self):
        payload = [{"name": "xdocs-v1.10-28-mar-2016"}, {"name": "v28.5.0-rc.1"}, {"name": "v28.5.2"}]
        self.assertEqual(TOOL_MODULE.newest_moby_tag(payload), "v28.5.2")
        self.assertIsNone(TOOL_MODULE.newest_moby_tag([{"name": "main"}]))


if __name__ == "__main__":
    unittest.main()
