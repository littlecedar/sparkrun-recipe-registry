"""Guards over `.github/`: the three workflows exist, parse as workflow-shaped YAML text, and keep
the promises their comments make (x86-only gate, no silently-green job, no cluster identifiers).

The repo is stdlib-only by design and carries no PyYAML, so this parses the workflow files as
TEXT: top-level keys at column 0, job ids at two spaces under `jobs:` (or one space under
`jobs:`), steps as `      - ` blocks. A missing or empty structure RAISES; it never passes
vacuously. Every guard has a negative control that mutates text in memory.
"""
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
GATE = WORKFLOWS / "gate.yml"
SWEEP = WORKFLOWS / "refresh-sweep.yml"
LLAMA = WORKFLOWS / "llamacpp-engine.yml"
REPORT_SCRIPT = REPO_ROOT / ".github" / "scripts" / "llamacpp-engine-report.py"

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


class WorkflowFiles(unittest.TestCase):
    def test_the_three_workflows_exist(self):
        for path in (GATE, SWEEP, LLAMA):
            self.assertTrue(path.is_file(), f"missing {path.relative_to(REPO_ROOT)}")

    def test_each_is_workflow_shaped(self):
        for path in (GATE, SWEEP, LLAMA):
            text = _text(path)
            keys = top_level_keys(text)
            for key in ("name", "on", "permissions", "jobs"):
                self.assertIn(key, keys, f"{path.name}: no top-level `{key}:`")
            self.assertTrue(job_ids(text), f"{path.name}: no jobs")
            self.assertNotIn("\t", text, f"{path.name}: YAML indentation must not use tabs")
            self.assertNotIn("\r", text, f"{path.name}: CRLF in a workflow file")

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
            "uv run python -m py_compile",
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


class RefreshSweep(unittest.TestCase):
    def setUp(self):
        self.text = _text(SWEEP)

    def test_schedule_and_manual_inputs(self):
        self.assertRegex(self.text, r'(?m)^    - cron: "17 6 \* \* \*"$')
        self.assertIn("workflow_dispatch:", self.text)
        for name in ("exit_code_on_drift:", "apply:"):
            self.assertIn(name, self.text, name)
        self.assertRegex(self.text, r"(?m)^      apply:\n(?:        .*\n)+        default: false$")

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

    def test_apply_is_guarded_and_nothing_commits_or_pushes(self):
        self.assertIn("APPLY: ${{ inputs.apply }}", self.text)
        self.assertEqual(unguarded_apply_steps(self.text), [],
                         "a step passes --apply without the apply guard")
        for forbidden in ("git commit", "git push", "git add"):
            self.assertNotIn(forbidden, self.text)


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

    def test_cluster_identifier_is_caught(self):
        text = _text(GATE)
        self.assertEqual(identifier_findings(text), [])
        self.assertTrue(identifier_findings(text + "\n# spark-head.internal.littlecedar.net\n"))

    def test_repo_root_is_the_tree_this_test_lives_in(self):
        self.assertTrue((REPO_ROOT / "AGENTS.md").is_file(), REPO_ROOT)


if __name__ == "__main__":
    unittest.main()
