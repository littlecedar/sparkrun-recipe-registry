"""Guards over `.github/`: the three workflows exist, parse as workflow-shaped YAML text, and keep
the promises their comments make (x86-only gate, no silently-green job, no cluster identifiers).

The repo is stdlib-only by design and carries no PyYAML, so this parses the workflow files as
TEXT: top-level keys at column 0, job ids at two spaces under `jobs:` (or one space under
`jobs:`), steps as `      - ` blocks. A missing or empty structure RAISES; it never passes
vacuously. Every guard has a negative control that mutates text in memory.
"""
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
GATE = WORKFLOWS / "gate.yml"
SWEEP = WORKFLOWS / "refresh-sweep.yml"
LLAMA = WORKFLOWS / "llamacpp-engine.yml"
REPORT_SCRIPT = REPO_ROOT / ".github" / "scripts" / "llamacpp-engine-report.py"
MARKER_SCRIPT = REPO_ROOT / ".github" / "scripts" / "sweep-marker.py"

# Cluster/DGX identifiers that must never reach a workflow: the registry ships to third parties.
IDENTIFIERS = (r"littlecedar\.net", r"\bspark-head\b", r"\b10\.0\.4\.\d", r"\bwopr\b", r"\bWOPR_")


def _text(path):
    if not path.is_file():
        raise AssertionError(f"missing workflow: {path.relative_to(REPO_ROOT)}")
    return path.read_text(encoding="utf-8")


def top_level_keys(text):
    """Column-0 `key:` names; empty RAISES (a file with no top-level keys is not a workflow)."""
    keys = [m.group(1) for m in re.finditer(r"(?m)^([A-Za-z_][A-Za-z0-9_-]*):", text)]
    if not keys:
        raise AssertionError("no top-level keys found")
    return keys


def job_ids(text):
    """Job ids under `jobs:`; a `jobs:` block with no job RAISES."""
    lines = text.splitlines()
    if "jobs:" not in lines:
        raise AssertionError("no top-level `jobs:` line")
    ids, seen = [], False
    for line in lines[lines.index("jobs:") + 1:]:
        if line and not line.startswith(" "):
            break                       # next top-level key: the jobs block ended
        m = re.fullmatch(r" {1,2}([A-Za-z0-9_-]+):", line)
        if m:
            ids.append(m.group(1))
            seen = True
    if not seen:
        raise AssertionError("`jobs:` with no job ids")
    return ids


def step_blocks(text):
    """Each `      - ` step as one string; no step at all RAISES."""
    blocks, cur = [], None
    for line in text.splitlines():
        if line.startswith("      - "):
            if cur is not None:
                blocks.append("\n".join(cur))
            cur = [line]
        elif cur is not None:
            cur.append(line)
    if cur is not None:
        blocks.append("\n".join(cur))
    if not blocks:
        raise AssertionError("no `      - ` step blocks found")
    return blocks


def identifier_findings(text):
    return [p for p in IDENTIFIERS if re.search(p, text, re.IGNORECASE)]


def unguarded_apply_steps(text):
    """Steps that pass `--apply` without the apply guard in the same block."""
    return [b.splitlines()[0] for b in step_blocks(text)
            if "--apply" in b and "env.APPLY == 'true'" not in b]


def job_env_lines(text):
    """Values of every job-level `env:` block. `runner` is NOT a legal context there — using it
    makes the workflow fail to compile before any job starts (measured: seven runs, zero jobs)."""
    lines, inside = [], False
    for line in text.splitlines():
        if re.fullmatch(r"    env:", line):
            inside = True
            continue
        if inside and re.match(r"      \S", line):
            lines.append(line)
            continue
        if inside and line.strip() and not line.startswith("      "):
            inside = False
    return lines        # [] means the workflow has no job-level env at all


def nonzero_exit_blocks(text):
    """Steps that can end the job non-zero, except the two sanctioned shapes: the opt-in
    `FAIL_ON_DRIFT` step and the impossible-branch `unexpected exit code` guard."""
    out = []
    for b in step_blocks(text):
        if "exit 1" not in b:
            continue
        if "env.FAIL_ON_DRIFT == 'true'" in b or "unexpected exit code" in b:
            continue
        out.append(b.splitlines()[0])
    return out


class WorkflowFiles(unittest.TestCase):
    def test_the_three_workflows_exist(self):
        for path in (GATE, SWEEP, LLAMA):
            self.assertTrue(path.is_file(), f"missing {path.relative_to(REPO_ROOT)}")

    def test_only_the_three_workflow_files_exist(self):
        # A syncthing conflict copy (`*.sync-conflict-*.yml`) in this directory would be loaded by
        # GitHub as a fourth workflow — a second nightly sweep — so the listing is exact.
        self.assertEqual(sorted(p.name for p in WORKFLOWS.iterdir()),
                         ["gate.yml", "llamacpp-engine.yml", "refresh-sweep.yml"])

    def test_each_is_workflow_shaped(self):
        for path in (GATE, SWEEP, LLAMA):
            text = _text(path)
            keys = top_level_keys(text)
            for key in ("name", "on", "permissions", "jobs"):
                self.assertIn(key, keys, f"{path.name}: no top-level `{key}:`")
            self.assertTrue(job_ids(text), f"{path.name}: no jobs")
            self.assertNotIn("\t", text, f"{path.name}: YAML indentation must not use tabs")
            self.assertNotIn("\r", text, f"{path.name}: CRLF in a workflow file")

    def test_no_runner_context_in_a_job_level_env(self):
        # `runner` is not a legal context at jobs.<id>.env: GitHub rejects the whole file
        # ("Invalid workflow file") and the run shows zero jobs — the failure this guards against.
        self.assertTrue(job_env_lines(_text(GATE)), "gate has no job-level env to check")
        for path in (GATE, SWEEP, LLAMA):
            for line in job_env_lines(_text(path)):
                self.assertNotIn("${{ runner.", line,
                                 f"{path.name}: runner context in a job-level env: {line.strip()}")

    def test_no_cluster_identifiers_and_no_literal_credentials(self):
        for path in (GATE, SWEEP, LLAMA):
            text = _text(path)
            self.assertEqual(identifier_findings(text), [], f"{path.name}: cluster identifiers")
            # Every credential field is a secrets.* reference, never a literal. (No lookahead:
            # `\s*` backtracks past the space and defeats one — compare the value instead.)
            for m in re.finditer(r"(?m)^\s+[A-Z_]*(?:TOKEN|PASSWORD|USERNAME)\s*:\s*(.+)$", text):
                self.assertTrue(m.group(1).startswith("${{ secrets."),
                                f"{path.name}: literal credential in {m.group(0).strip()}")


class Gate(unittest.TestCase):
    def setUp(self):
        self.text = _text(GATE)

    def test_triggers_on_main_push_and_pull_request(self):
        self.assertRegex(self.text, r"(?m)^  push:\n    branches: \[main\]\n  pull_request:$")

    def test_runs_the_documented_gate_verbatim(self):
        for fragment in (
            "uv sync",
            "uv run python -B -m unittest discover -s tests",
            "for f in recipes/*/*.yaml; do",
            "sparkrun recipe validate",
            'for s in mods/*/*.sh recipes/*/mods/*/*.sh; do bash -n "$s"; done',
            "for p in mods/*/*.py recipes/*/mods/*/*.py tools/*.py plugins/*.py; do",
            "-m py_compile",
            "find mods recipes tools tests plugins -name __pycache__ -type d -exec rm -rf {} +",
        ):
            self.assertIn(fragment, self.text, fragment)

    def test_validate_step_degrades_honestly(self):
        """No sparkrun on the runner must be a printed SKIPPED, not a red or a silent green."""
        blocks = [b for b in step_blocks(self.text) if "recipes/*/*.yaml" in b]
        self.assertTrue(blocks, "no step validates recipes/*/*.yaml")
        block = blocks[0]
        self.assertIn("SKIPPED: sparkrun not installable in CI", block)
        self.assertIn("exit 0", block)
        self.assertIn('HOME="$SPARKRUN_HOME"', block, "every sparkrun call needs a HOME override")

    def test_ci_is_x86_only_and_says_so(self):
        self.assertIn("runs-on: ubuntu-latest", self.text)
        self.assertNotIn("runs-on: self-hosted", self.text,
                         "the arm64 build must not live in the gate")
        self.assertIn("CI never bumps a model pin", self.text)

    def test_gate_can_be_dispatched_manually(self):
        self.assertIn("workflow_dispatch:", self.text, "`gh workflow run gate.yml` needs it")

    def test_sync_failure_falls_back_to_the_runner_python(self):
        blocks = [b for b in step_blocks(self.text) if "uv sync --frozen" in b]
        self.assertTrue(blocks, "no uv sync step")
        self.assertIn("continue-on-error: true", blocks[0])
        self.assertIn("python3 -B -m unittest discover -s tests", self.text)


class RefreshSweep(unittest.TestCase):
    def setUp(self):
        self.text = _text(SWEEP)

    def test_schedule_and_manual_inputs(self):
        self.assertRegex(self.text, r'(?m)^    - cron: "17 6 \* \* \*"$')
        self.assertIn("workflow_dispatch:", self.text)
        for name in ("exit_code_on_drift:", "apply:"):
            self.assertIn(name, self.text, name)
        self.assertRegex(self.text, r"(?m)^      apply:\n(?:        .*\n)+        default: false$")
        # Drift is the registry's normal state: the run stays green unless a human re-arms it.
        self.assertRegex(
            self.text,
            r"(?m)^      exit_code_on_drift:\n(?:        .*\n)+        default: false$")

    def test_exit_code_contract_and_artifact(self):
        self.assertIn("tools/refresh-sweep.py --json sweep.json --markdown sweep.md --exit-code",
                      self.text)
        self.assertIn("actions/upload-artifact", self.text)
        self.assertIn("if: always()", self.text)
        self.assertIn("1 = drift, 2 = could not run", self.text)

    def test_one_tracking_issue_with_distinct_titles(self):
        self.assertIn("pin-drift", self.text)
        self.assertIn("Pin drift found by refresh-sweep", self.text)
        self.assertIn("Refresh sweep could not run", self.text)
        self.assertIn("gh issue edit", self.text, "must update the open issue, not add one a day")

    def test_the_issue_path_skips_when_issues_are_disabled(self):
        # Measured: this repository has has_issues=false, and an unconditional `gh issue create`
        # turned every sweep run red. The fallback signal is the run summary.
        blocks = [b for b in step_blocks(self.text) if "gh issue edit" in b]
        self.assertTrue(blocks, "no issue-upsert step")
        self.assertIn("hasIssuesEnabled", blocks[0])
        self.assertIn("SKIPPED: repository issues are disabled", blocks[0])

    def test_sweep_never_fails_a_run_on_drift(self):
        self.assertIn("FAIL_ON_DRIFT: ${{ inputs.exit_code_on_drift }}", self.text)
        self.assertEqual(nonzero_exit_blocks(self.text), [],
                         "a step can fail the run without the opt-in guard")
        self.assertIn("GITHUB_STEP_SUMMARY", self.text, "the report must land in the summary")
        self.assertIn("sweep-broken", self.text, "exit 2 must be label-distinct, not an email")

    def test_the_daily_signal_is_a_retained_artifact_and_a_summary_marker(self):
        # Nobody subscribes to a green run: the artifact is the retained copy and the summary's
        # first line is the stable, greppable marker a session can look for.
        self.assertIn("sweep-marker.py", self.text)
        self.assertRegex(self.text, r"(?m)^          name: refresh-sweep$")
        self.assertIn("retention-days: 90", self.text)
        self.assertIn("gh run download", self.text)

    def test_the_marker_line_is_well_formed(self):
        script = _text(MARKER_SCRIPT)
        imports = set(re.findall(r"(?m)^import ([a-z_.]+)", script))
        self.assertLessEqual(imports, {"json", "sys"}, imports)
        self.assertIn("pin-drift:", script)
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "sweep.json"
            report.write_text(json.dumps({
                "generated_at": "2026-10-22T06:09:42Z", "exit_code": 1, "gated": [{}] * 12,
                "totals": {"recipes": 52, "model_pins": 59, "container_pins": 52,
                           "build_inputs": 13, "accepted": 8},
            }), encoding="utf-8")
            out = subprocess.run([sys.executable, "-B", str(MARKER_SCRIPT), str(report)],
                                 capture_output=True, text=True)
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertTrue(out.stdout.startswith("pin-drift: 12 rows (8 accepted) | exit 1 |"),
                            out.stdout)
            # An unreadable report must still be a marker, not a failed step.
            broken = subprocess.run([sys.executable, "-B", str(MARKER_SCRIPT),
                                     str(Path(tmp) / "absent.json")],
                                    capture_output=True, text=True)
            self.assertEqual(broken.returncode, 0, broken.stderr)
            self.assertIn("pin-drift: report unreadable", broken.stdout)

    def test_apply_is_guarded_and_nothing_commits_or_pushes(self):
        self.assertIn("APPLY: ${{ inputs.apply }}", self.text)
        self.assertEqual(unguarded_apply_steps(self.text), [],
                         "a step passes --apply without the apply guard")
        for forbidden in ("git commit", "git push", "git add"):
            self.assertNotIn(forbidden, self.text)


class DocsSignal(unittest.TestCase):
    def test_agents_states_where_the_daily_signal_lands(self):
        agents = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
        for needle in ("refresh-sweep", "retention", "pin-drift:", "has_issues=true",
                       "container-only"):
            self.assertIn(needle, agents, needle)


class LlamaCppEngine(unittest.TestCase):
    def setUp(self):
        self.text = _text(LLAMA)
        start = self.text.index("  report:")
        end = self.text.index("  build:")
        self.report = self.text[start:end]
        self.build = self.text[end:]

    def test_report_never_fails_and_never_builds(self):
        self.assertIn("runs-on: ubuntu-latest", self.report)
        self.assertIn(".github/scripts/llamacpp-engine-report.py", self.report)
        self.assertNotIn("docker build", self.report)

    def test_build_is_arm64_dispatch_only_and_guarded(self):
        self.assertIn("runs-on: [self-hosted, linux, arm64, dgx-spark]", self.build)
        self.assertIn("github.event_name == 'workflow_dispatch'", self.build)
        self.assertIn("vars.ARM64_RUNNER_ENABLED == 'true'", self.build,
                      "an unguarded self-hosted job would sit queued forever")
        self.assertIn("No self-hosted runner is registered today", self.text)
        self.assertIn("--build-arg LLAMA_REF=", self.build)
        self.assertIn("recipes/explore/Dockerfile.llamacpp-upstream", self.build)
        self.assertIn("GITHUB_STEP_SUMMARY", self.build, "the digest must land in the run summary")

    def test_build_credentials_come_from_secrets_and_fail_loudly(self):
        for name in ("secrets.DOCKERHUB_USERNAME", "secrets.DOCKERHUB_TOKEN"):
            self.assertIn(name, self.build, name)
        self.assertIn("set secrets.DOCKERHUB_USERNAME and secrets.DOCKERHUB_TOKEN", self.build)

    def test_report_script_is_stdlib_only_and_non_fatal(self):
        text = _text(REPORT_SCRIPT)
        imports = set(re.findall(r"(?m)^import ([a-z_.]+)", text))
        self.assertTrue(imports, "no imports found")
        self.assertLessEqual(imports, {"json", "os", "pathlib", "re", "urllib.request"}, imports)
        self.assertIn("except Exception", text, "a failed probe must be printed, not fatal")
        for probe in ("graph_mtp", "kolibri1.cpp", "vllm-decision2.cpp", "121a-real", "behind_by"):
            self.assertIn(probe, text, probe)


class Docs(unittest.TestCase):
    def test_the_no_ci_claim_is_gone(self):
        agents = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8").lower()
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8").lower()
        self.assertNotIn("no `.github/`", agents)
        self.assertNotIn("no ci, no pre-commit", agents)
        for workflow in ("gate.yml", "refresh-sweep.yml", "llamacpp-engine.yml"):
            self.assertIn(workflow, agents, workflow)
            self.assertIn(workflow, readme, workflow)


class NegativeControls(unittest.TestCase):
    """Each control proves its guard fires on the pre-fix or broken text."""

    def test_missing_jobs_block_raises(self):
        with self.assertRaises(AssertionError):
            job_ids("name: x\non: push\npermissions:\n  contents: read\n")

    def test_empty_step_list_raises(self):
        with self.assertRaises(AssertionError):
            step_blocks("name: x\njobs:\n  a:\n    runs-on: ubuntu-latest\n")

    def test_missing_workflow_file_raises(self):
        with self.assertRaises(AssertionError):
            _text(WORKFLOWS / "does-not-exist.yml")

    def test_unguarded_apply_step_is_caught(self):
        text = _text(SWEEP)
        self.assertEqual(unguarded_apply_steps(text), [])
        broken = text.replace("env.APPLY == 'true'", "true")
        self.assertTrue(unguarded_apply_steps(broken),
                        "removing the apply guard must be caught")

    def test_job_env_runner_context_is_caught(self):
        broken = _text(GATE).replace("${{ github.workspace }}/.local/sparkrun-home",
                                     "${{ runner.temp }}/sparkrun-home")
        self.assertTrue([ln for ln in job_env_lines(broken) if "${{ runner." in ln],
                        "the compile-breaking job-level env must be caught")

    def test_unguarded_failing_step_is_caught(self):
        text = _text(SWEEP)
        self.assertEqual(nonzero_exit_blocks(text), [])
        broken = text.replace("env.FAIL_ON_DRIFT == 'true'", "true")
        self.assertTrue(nonzero_exit_blocks(broken),
                        "a step that can fail the run must be caught")

    def test_cluster_identifier_is_caught(self):
        text = _text(GATE)
        self.assertEqual(identifier_findings(text), [])
        self.assertTrue(identifier_findings(text + "\n# spark-head.internal.littlecedar.net\n"))

    def test_repo_root_is_the_tree_this_test_lives_in(self):
        self.assertTrue((REPO_ROOT / "AGENTS.md").is_file(), REPO_ROOT)


if __name__ == "__main__":
    unittest.main()
