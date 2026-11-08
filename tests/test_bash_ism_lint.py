"""The `#!/bin/sh` stubs must be POSIX, and this tool is the only thing that can say so here.

Why: 2026-11-08, seven consecutive red `gate` runs all came from one test stub written
`#!/bin/sh` with `${@: -1}`. This workstation's `/bin/sh` is bash, so the defect cannot be
observed locally at all; the fix is a text scan, not an execution. Every construct below is
a fixture, the clean POSIX stub is a control, and one negative control disables the checker
to show the slice fixture passing -- a guard nobody has watched fire is decoration.

Stdlib-only, like the rest of tests/ and tools/; the tool is dash-named, so it is imported
via importlib and registered in sys.modules before exec_module (the house idiom).
"""

from __future__ import annotations

import importlib.util
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOL = REPO_ROOT / "tools" / "bash-ism-lint.py"

#: A real shebang once concatenated, but not a literal that opens this file: the scan reads
#: tests/*.py too, so the fixture text must not look like a stub until this test assembles it.
SH = "#!" + "/bin/sh\n"


def load_tool():
    spec = importlib.util.spec_from_file_location("bash_ism_lint", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["bash_ism_lint"] = module
    spec.loader.exec_module(module)
    return module


class Constructs(unittest.TestCase):
    """Each bash-only construct is flagged by name; the POSIX form is not."""

    def setUp(self):
        self.tool = load_tool()

    def names(self, shell: str) -> list[str]:
        return [name for _, name, _ in self.tool.findings_in_shell(shell)]

    def test_positional_parameter_slice_is_flagged(self):
        self.assertIn("positional-parameter slice", self.names(SH + 'last="${@: -1}"\n'))

    def test_double_bracket_test_is_flagged(self):
        self.assertIn("[[ ... ]] test", self.names(SH + "if [[ -f x ]]; then :; fi\n"))

    def test_double_equals_in_a_single_bracket_test_is_flagged(self):
        self.assertIn("== in a single-bracket test (POSIX is =)",
                      self.names(SH + '[ "$a" == "$b" ] && echo same\n'))

    def test_local_is_flagged(self):
        self.assertIn("local (not POSIX)", self.names(SH + "f() {\n  local x=1\n}\n"))

    def test_function_keyword_is_flagged(self):
        self.assertIn("function keyword", self.names(SH + "function f {\n  :\n}\n"))

    def test_a_posix_stub_is_clean(self):
        posix = (SH + "last=; for a in \"$@\"; do last=$a; done\n"
                       "case \"$last\" in\n  *\"sh -s\"*) echo POOL=entries:3 ;;\nesac\n"
                       '[ "$last" = x ] && printf "%s\\n" "$last"\n')
        self.assertEqual(self.tool.findings_in_shell(posix), [])

    def test_a_bash_shebang_is_skipped(self):
        source = 'STUB = "#' + '!/usr/bin/env bash\\nif [[ -f x ]]; then :; fi\\n"\n'
        self.assertEqual(self.tool.literal_snippets(source), [])


class Scan(unittest.TestCase):
    """`scan(root)` finds stubs written by tests, and leaves bash scripts alone."""

    def setUp(self):
        self.tool = load_tool()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "tools").mkdir()
        (self.root / "tests").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_stub_written_by_a_test_is_found_at_its_line(self):
        (self.root / "tests/test_stub_owner.py").write_text(
            "x = (\n"
            '    "#' + "!/bin/sh\\n\"\n"
            '    \'case "${@: -1}" in\\n\'\n'
            ")\n", encoding="utf-8")
        hits = self.tool.scan(self.root)
        self.assertTrue(hits, "a /bin/sh stub with a slice must be found")
        self.assertIn("tests/test_stub_owner.py:3: positional-parameter slice", hits[0])

    def test_a_sh_script_is_found_and_a_bash_script_is_not(self):
        (self.root / "tools/sh.sh").write_text(SH + "local x=1\necho \"$x\"\n", encoding="utf-8")
        (self.root / "tools/bash.sh").write_text(
            "#!" + "/usr/bin/env bash\nf() { local x=1; }\n", encoding="utf-8")
        hits = self.tool.scan(self.root)
        self.assertEqual([h.split(":")[0] for h in hits], ["tools/sh.sh"])

    def test_this_repo_is_clean_and_the_cli_says_so(self):
        self.assertEqual(self.tool.scan(REPO_ROOT), [],
                         "the tracked tree must pass its own lint")
        out = subprocess.run([sys.executable, "-B", str(TOOL)], capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("0 finding(s)", out.stdout)


class NegativeControls(unittest.TestCase):
    def test_disabling_the_checker_lets_the_slice_fixture_pass(self):
        tool = load_tool()
        shell = SH + 'last="${@: -1}"\n'
        self.assertTrue(tool.findings_in_shell(shell), "the fixture must fire first")
        tool.CONSTRUCTS = ()
        self.assertEqual(tool.findings_in_shell(shell), [],
                         "with the construct table emptied the fixture passes: the guard is "
                         "load-bearing, not the fixture")

    def test_an_execution_check_runs_only_where_dash_exists(self):
        """The real interpreter difference, when a dash is installed -- never a silent pass."""
        dash = shutil.which("dash")
        if not dash:
            self.skipTest("no dash on this host: the text scan is the only guard here")
        bad = subprocess.run([dash, "-c", 'echo "${@: -1}"'], capture_output=True, text=True)
        self.assertNotEqual(bad.returncode, 0, "dash must reject the bash slice")
        good = subprocess.run([dash, "-c", 'last=; for a in "$@"; do last=$a; done; echo "$last"'],
                              capture_output=True, text=True)
        self.assertEqual(good.returncode, 0, good.stderr)


if __name__ == "__main__":
    unittest.main()
