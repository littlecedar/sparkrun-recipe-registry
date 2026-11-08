"""Guards for tools/engine-exit-capture.sh -- the stdout of an engine that dies during init.

Run:
    uv run python -B -m unittest discover -s tests

Stdlib only, no network, no Docker: the real script runs against a stub `docker` on PATH, so
the assertions are about behaviour rather than about the text of the script. That matters here
because the defect is a race -- measured on the fleet head 2026-11-08, a `docker run --rm alpine
sh -c 'echo boom; exit 137'` is destroyed ~26 ms after its `die` event, so a `docker logs`
started on that event already answers "No such container". The capture is armed before the
launch and attaches at `create`, which is the only place the text still exists.

Every assertion has its negative control: a copy with the `create` attach removed must lose
`boom`, and a copy with the `die` watcher removed must lose the exit state. Without those, a
formatted-away attach would leave the tests passing.
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOL = REPO_ROOT / "tools" / "engine-exit-capture.sh"

# The two docker subcommands the capture uses. `events` records its argv (so the label scope is
# checkable), replays the case's event lines, then holds the stream open like a real one -- a
# capture must be killable, not just readable. `exec` so the pid the capture kills is the sleep,
# and no orphan is left behind by the test itself.
STUB = """#!/usr/bin/env bash
case "$1" in
  events)
    printf '%s\\n' "$@" > "$STUB_ARGV"
    if [ -n "${STUB_EVENTS_ERROR:-}" ]; then
      printf '%s\\n' "$STUB_EVENTS_ERROR" >&2
      exit 1
    fi
    cat "${STUB_EVENTS:-/dev/null}"
    exec sleep "${STUB_HOLD:-30}"
    ;;
  logs)
    printf 'boom\\n'
    exit 0
    ;;
esac
exit 0
"""

EVENTS = (
    "create deadbeef sparkrun_t1_node_0 <no value>\n"
    "die deadbeef sparkrun_t1_node_0 137\n"
)


class Harness(unittest.TestCase):
    def run_capture(
        self,
        events: str = "",
        label: str = "",
        max_seconds: str = "2",
        script: str | None = None,
        env_extra: dict[str, str] | None = None,
    ) -> tuple[dict[str, str], str, str]:
        """Run the capture against the stub docker; return (capture files, argv, output)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            bins = tmp / "bin"
            bins.mkdir()
            stub = bins / "docker"
            stub.write_text(STUB)
            stub.chmod(0o755)
            events_file = tmp / "events.txt"
            events_file.write_text(events)
            argv_file = tmp / "argv.txt"
            tool = tmp / "capture.sh"
            tool.write_text(script if script is not None else TOOL.read_text())
            cap = tmp / "cap"
            env = {
                **os.environ,
                "PATH": f"{bins}:{os.environ['PATH']}",
                "STUB_EVENTS": str(events_file),
                "STUB_ARGV": str(argv_file),
                "CAPTURE_IDLE_EXIT": "1",
            }
            env.pop("STUB_EVENTS_ERROR", None)
            env.update(env_extra or {})
            args = ["bash", str(tool), str(cap), max_seconds]
            if label:
                args.append(label)
            out = subprocess.run(args, capture_output=True, text=True, timeout=60,
                                 check=False, env=env)
            files = {p.name: p.read_text() for p in cap.glob("*")} if cap.is_dir() else {}
            argv = argv_file.read_text() if argv_file.is_file() else ""
            return files, argv, out.stdout + out.stderr


class CaptureOnDie(Harness):
    def test_the_text_and_the_exit_state_survive_the_container(self):
        files, _argv, out = self.run_capture(events=EVENTS)
        log = files.get("sparkrun_t1_node_0.log", "")
        self.assertIn("boom", log, f"the engine's own text is lost: {files} / {out}")
        self.assertIn("# capture: create", log, "the log does not say which container it is")
        self.assertIn("die exit=137", files.get("sparkrun_t1_node_0.die", ""),
                      f"the exit state the die event carried is missing: {files}")
        self.assertNotIn("no-capture.txt", files, "a capture that did run reported failure")

    def test_the_capture_is_scoped_to_the_arm_it_was_armed_for(self):
        files, argv, out = self.run_capture(events=EVENTS, label="sparkrun.recipe=/r/x.yaml")
        self.assertIn("label=sparkrun.recipe=/r/x.yaml", argv,
                      f"a peer's boot on a shared node would be captured: {argv} / {out}")
        self.assertIn("boom", files.get("sparkrun_t1_node_0.log", ""))


class FailClosed(Harness):
    def test_an_idle_window_is_watched_for_its_whole_length(self):
        """One 5 s read timeout is the idle case, not a verdict: 2026-11-08, 7 boots x 4 nodes.

        The marlin lease's captures all said "no container ... in 5 s" while the boot was still
        loading, because the old loop read `rc=$?` after `if read ...; then ...; fi` and took the
        `if` statement's own 0 for a dead stream. A capture armed for a boot must outlive its
        first idle wait, so the window it reports must be the window it was given.
        """
        started = time.monotonic()
        files, _argv, out = self.run_capture(events="", max_seconds="8")
        elapsed = time.monotonic() - started
        self.assertGreaterEqual(elapsed, 8, f"the watch ended before its window: {out}")
        marker = files.get("no-capture.txt", "")
        self.assertTrue(marker.startswith("# capture failed:"), f"no marker: {files}")
        window = re.search(r"in (\d+) s of watching", marker)
        self.assertIsNotNone(window, f"the marker does not say how long it watched: {marker!r}")
        self.assertGreaterEqual(int(window.group(1)), 8,
                                f"the watch reported {window.group(1)} s of a 8 s window: {marker}")
        self.assertNotIn("docker events exited", marker,
                         f"an idle stream was reported as a dead client: {marker}")
        self.assertNotIn("docker events exited", files.get("events.err", ""))

    def test_a_client_that_exits_immediately_is_reported_not_hidden(self):
        """A broken instrument must say so; "docker said: nothing" sent the next session hunting."""
        files, _argv, out = self.run_capture(
            events="", max_seconds="3",
            env_extra={"STUB_EVENTS_ERROR": "Cannot connect to the Docker daemon"},
        )
        err = files.get("events.err", "")
        self.assertIn("# capture: docker events exited rc=1", err,
                      f"the dead client is not recorded: {files} / {out}")
        marker = files.get("no-capture.txt", "")
        self.assertIn("# capture failed:", marker)
        self.assertIn("docker events exited", marker,
                      f"the marker reads as a plain no-container verdict: {marker!r}")
        self.assertIn("Cannot connect to the Docker daemon", marker)

    def test_no_container_ever_created_says_so(self):
        files, _argv, _out = self.run_capture(events="")
        marker = files.get("no-capture.txt", "")
        self.assertTrue(marker.startswith("# capture failed:"),
                        f"an empty capture is indistinguishable from no output: {files}")
        self.assertIn("no container", marker)

    def test_a_docker_that_cannot_run_says_why(self):
        files, _argv, _out = self.run_capture(
            events="", env_extra={"STUB_EVENTS_ERROR": "Cannot connect to the Docker daemon"}
        )
        marker = files.get("no-capture.txt", "")
        self.assertTrue(marker.startswith("# capture failed:"), f"no marker: {files}")
        self.assertIn("Cannot connect to the Docker daemon", marker,
                      f"the artifact does not name the reason: {marker!r}")


class NegativeControls(Harness):
    def test_removing_the_create_attach_loses_the_text(self):
        mutated = TOOL.read_text().replace(
            '( docker logs -f "$id" < /dev/null', '( : < /dev/null', 1
        )
        files, _argv, out = self.run_capture(events=EVENTS, script=mutated)
        self.assertIn("# capture: create", files.get("sparkrun_t1_node_0.log", ""),
                      f"the mutation broke the watcher itself: {files} / {out}")
        self.assertNotIn("boom", files.get("sparkrun_t1_node_0.log", ""),
                         "the attach survived the mutation; the control is void")

    def test_removing_the_die_watcher_loses_the_exit_state(self):
        mutated = "\n".join(
            line for line in TOOL.read_text().splitlines()
            if '>> "$CAP/$name.die"' not in line
        )
        self.assertNotIn('>> "$CAP/$name.die"', mutated, "the die write survived the mutation")
        files, _argv, _out = self.run_capture(events=EVENTS, script=mutated)
        self.assertIn("boom", files.get("sparkrun_t1_node_0.log", ""),
                      "the mutation broke the attach, not the die watcher")
        self.assertNotIn("sparkrun_t1_node_0.die", files,
                         "the exit state survived the mutation; the control is void")


if __name__ == "__main__":
    unittest.main()
