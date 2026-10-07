"""Guards for tools/safe_text.py -- the escape-on-read/escape-on-write tool.

Run:
    uv run python -B -m unittest tests.test_safe_text -v

Stdlib-only, offline, no sparkrun needed.

Why these exist. The raw image placeholder token (U+003C U+FF5C
"deepseek_image" U+FF5C U+003E) makes the serving API return HTTP 400 and the
producing session is lost, so *reading* a token-bearing file is itself the
outage -- not a wrong answer to recover from. safe_text.py exists so logs and
chat templates can cross a model context boundary in escaped form and come back
byte-exact for the callers that need the raw placeholder (a tokenizer, an HTTP
body). Four properties are load-bearing and each gets a guard with a negative
control that fails when the property is broken:

1. escape() output is ASCII-only, so the token cannot survive it;
2. escape() -> unescape() is byte-exact, including for non-UTF-8 input;
3. detection is the *full* token, not the name and not the ASCII bars -- a
   detector that flags ``|deepseek_image|`` would fire on ordinary log text;
4. nothing shipped in this tree contains the literal token, this file included.

The token is never written literally here: it is built by ``raw_token()``. If a
test needs the bytes, call that function.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOL_PATH = REPO_ROOT / "tools" / "safe_text.py"

# Directories that ship to the cluster and to third parties.  A literal token in
# any of them is a hazard for every downstream reader, so it is a guard.
SHIPPED_DIRS = ("tools", "tests", "recipes", "mods", "benchmarking")


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _run(*args: str, stdin: bytes | None = None):
    return subprocess.run(
        [sys.executable, str(TOOL_PATH), *args],
        input=stdin,
        capture_output=True,
    )


class TokenSpelling(unittest.TestCase):
    """The token is assembled from codepoints, and has the shape we think."""

    def setUp(self):
        self.tool = _load(TOOL_PATH, "safe_text_spelling")

    def test_token_is_assembled_from_codepoints(self):
        token = self.tool.raw_token()
        self.assertEqual(len(token), 18)  # open + bar + 14 chars + bar + close
        self.assertEqual(ord(token[0]), 0x003C)
        self.assertEqual(ord(token[1]), 0xFF5C)
        self.assertEqual(token[2:-2], "deepseek_image")
        self.assertEqual(ord(token[-2]), 0xFF5C)
        self.assertEqual(ord(token[-1]), 0x003E)
        self.assertEqual([ord(c) for c in token], list(self.tool.TOKEN_CODEPOINTS))

    def test_escaped_form_is_ascii_and_name_bearing(self):
        escaped = self.tool.escaped_token()
        self.assertTrue(all(ord(c) < 0x80 for c in escaped))
        self.assertIn("deepseek_image", escaped)
        # The bars must be gone: the escape is what makes the token inert.
        self.assertNotIn(chr(0xFF5C), escaped)

    def test_source_files_carry_no_literal_token(self):
        # The tool cannot be trusted as a filter if it contains the thing it
        # filters; neither can this guard file.
        token = self.tool.raw_token()
        for path in (TOOL_PATH, Path(__file__)):
            self.assertNotIn(token, path.read_text())


class EscapeProperties(unittest.TestCase):
    def setUp(self):
        self.tool = _load(TOOL_PATH, "safe_text_escape")

    def test_escape_is_ascii_only_and_unescape_round_trips(self):
        token = self.tool.raw_token()
        original = (
            f"system: you may emit {token} when an image is attached\n"
            "user: 中文 emoji \U0001f600 backslash \\ tab\tcol\n"
            f"assistant: ok\n{token}\n"
        )
        escaped = self.tool.escape(original)
        self.assertTrue(all(ord(c) < 0x80 for c in escaped), "escape output not ASCII")
        self.assertNotIn(token, escaped)
        self.assertIn("\\uff5c", escaped)
        self.assertEqual(self.tool.unescape(escaped), original)

    def test_bytes_round_trip_is_byte_exact(self):
        data = os.urandom(4096)
        escaped = self.tool.escape_bytes(data)
        self.assertTrue(all(ord(c) < 0x80 for c in escaped))
        self.assertEqual(self.tool.unescape_bytes(escaped), data)

    def test_invalid_utf8_becomes_hex_escape(self):
        # A truncated multi-byte sequence must not raise and must round-trip.
        data = b"ok \xe4\xb8 broken"
        escaped = self.tool.escape_bytes(data)
        self.assertIn("\\xe4", escaped)
        self.assertEqual(self.tool.unescape_bytes(escaped), data)

    def test_unescape_refuses_input_escape_could_not_have_produced(self):
        # escape() output is ASCII-only, so non-ASCII input is proof the caller
        # passed a raw file; accepting it would silently keep the token alive.
        with self.assertRaises(ValueError):
            self.tool.unescape("caf\u00e9 " + self.tool.raw_token())

    def test_unescape_fails_closed_on_unknown_or_malformed_escape(self):
        # Guessing here would silently corrupt a template; unrecognised input
        # means the caller handed us something escape() did not produce.
        for bad in ("\\q", "\\u12", "\\xZZ", "\\U00110000", "half \\"):
            with self.assertRaises(ValueError, msg=bad):
                self.tool.unescape(bad)


class Detection(unittest.TestCase):
    def setUp(self):
        self.tool = _load(TOOL_PATH, "safe_text_detect")
        self.token = self.tool.raw_token()

    def test_locations_are_line_and_column(self):
        text = "line one\n" + "ab" + self.token + " tail\n" + self.token
        self.assertEqual(self.tool.find_raw_token(text), [(2, 3), (3, 1)])
        self.assertTrue(self.tool.contains_raw_token(text))

    def test_escaped_text_is_clean(self):
        escaped = self.tool.escape("x " + self.token)
        self.assertEqual(self.tool.find_raw_token(escaped), [])
        self.assertFalse(self.tool.contains_raw_token(escaped))

    def test_scan_result_reports_size_and_non_ascii(self):
        text = "a\u00e9 " + self.token
        result = self.tool.scan_text(text, "f")
        self.assertFalse(result.clean)
        self.assertEqual(len(result.hits), 1)
        self.assertEqual(result.non_ascii, 3)  # U+00E9 + two U+FF5C
        self.assertEqual(result.size, len(text.encode("utf-8")))

    def test_scan_file_missing_path_raises(self):
        # "unreadable" must never read as "clean".
        with self.assertRaises(FileNotFoundError):
            self.tool.scan_file(REPO_ROOT / "tools" / "no-such-file-xyz.log")


class CliBehaviour(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.tool = _load(TOOL_PATH, "safe_text_cli")
        self.token = self.tool.raw_token()

    def tearDown(self):
        self.tmp.cleanup()

    def test_escape_from_stdin_is_ascii_only(self):
        proc = _run(stdin=("hello " + self.token + " \u00e9\n").encode("utf-8"))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(all(b < 0x80 for b in proc.stdout))
        self.assertNotIn(self.token.encode("utf-8"), proc.stdout)
        self.assertIn(b"deepseek_image", proc.stdout)

    def test_check_flags_token_and_exits_one_without_leaking_it(self):
        target = self.dir / "dump.json"
        target.write_text('{"content": "see ' + self.token + ' here"}')
        proc = _run("--check", str(target))
        self.assertEqual(proc.returncode, 1)
        out = proc.stdout.decode("ascii")  # raises if anything non-ASCII escaped
        self.assertIn("RAW TOKEN x1 at 1:18", out)
        self.assertNotIn(self.token, out)

    def test_check_clean_file_exits_zero(self):
        target = self.dir / "clean.log"
        target.write_text("nothing to see\n")
        proc = _run("--check", str(target))
        self.assertEqual(proc.returncode, 0)
        self.assertIn(b"no raw token", proc.stdout)

    def test_check_missing_file_is_exit_two_not_clean(self):
        proc = _run("--check", str(self.dir / "absent.log"))
        self.assertEqual(proc.returncode, 2)

    def test_in_place_escape_then_unescape_restores_bytes(self):
        target = self.dir / "template.jinja"
        original = ("{% if x %}" + self.token + "{% endif %}\n").encode("utf-8")
        target.write_bytes(original)
        self.assertEqual(_run("--in-place", str(target)).returncode, 0)
        escaped = target.read_bytes()
        self.assertTrue(all(b < 0x80 for b in escaped))
        self.assertNotIn(self.token.encode("utf-8"), escaped)
        self.assertEqual(_run("--in-place", "--unescape", str(target)).returncode, 0)
        self.assertEqual(target.read_bytes(), original)

    def test_in_place_does_not_write_through_a_symlink(self):
        real = self.dir / "snapshot-template.jinja"
        original = ("x " + self.token).encode("utf-8")
        real.write_bytes(original)
        link = self.dir / "link.jinja"
        link.symlink_to(real)
        self.assertEqual(_run("--in-place", str(link)).returncode, 0)
        # The real file must be untouched; the link is replaced, not followed.
        self.assertEqual(real.read_bytes(), original)
        self.assertFalse(link.is_symlink())
        self.assertNotIn(self.token.encode("utf-8"), link.read_bytes())

    def test_save_template_stores_it_inert_and_load_restores_it(self):
        # The escaped-at-rest convention: a token-bearing template lives in the
        # tree ASCII-only and is unescaped only at the call site.
        target = self.dir / "vl-template.jinja"
        text = "{% for m in messages %}" + self.token + "{{ m.content }}{% endfor %}"
        self.tool.save_template(target, text)
        stored = target.read_bytes()
        self.assertTrue(all(b < 0x80 for b in stored))
        self.assertNotIn(self.token.encode("utf-8"), stored)
        self.assertEqual(self.tool.load_template(target), text)

    def test_load_template_refuses_a_file_that_is_not_escaped(self):
        # A raw-token file handed to load_template() means someone stored it
        # wrongly; raising beats silently returning something half-decoded.
        target = self.dir / "raw.jinja"
        target.write_bytes(("plain-text \u00e9\n" + self.token).encode("utf-8"))
        with self.assertRaises(ValueError):
            self.tool.load_template(target)

    def test_unescape_on_a_raw_file_is_exit_two(self):
        target = self.dir / "raw-again.jinja"
        target.write_text("already raw " + self.token)
        proc = _run("--unescape", str(target))
        self.assertEqual(proc.returncode, 2)
        self.assertIn(b"not produced by escape()", proc.stderr)

    def test_conflicting_flags_are_exit_two(self):
        target = self.dir / "f"
        target.write_text("x")
        self.assertEqual(_run("--check", "--in-place", str(target)).returncode, 2)
        self.assertEqual(_run("--in-place").returncode, 2)


class NegativeControls(unittest.TestCase):
    """Each control fails when the guard it backs is broken.

    These are the tests that must go red if someone "simplifies" the tool into
    an identity function or a name-based detector.
    """

    def setUp(self):
        self.tool = _load(TOOL_PATH, "safe_text_controls")
        self.token = self.tool.raw_token()

    def test_ascii_bars_are_not_the_token(self):
        # Ordinary log text mentioning the placeholder with ASCII pipes: a
        # detector matching only the name, or normalising U+FF5C to '|', fires
        # here and would refuse to read a harmless file.
        decoy = "<|deepseek_image|>"
        self.assertFalse(self.tool.contains_raw_token(decoy))
        self.assertEqual(self.tool.find_raw_token(decoy), [])

    def test_no_flag_for_fullwidth_less_than_or_name_alone(self):
        for decoy in ("\uff1c\uff5cdeepseek_image\uff5c\uff1e", "deepseek_image", chr(0xFF5C)):
            self.assertFalse(self.tool.contains_raw_token(decoy), repr(decoy))

    def test_detector_is_not_always_true(self):
        self.assertFalse(self.tool.contains_raw_token("plain text\n"))
        self.assertFalse(self.tool.contains_raw_token(""))

    def test_escape_is_not_identity(self):
        # Guards every round-trip test above: if escape() returned its input,
        # the round-trip would still pass while leaking the token.
        self.assertNotEqual(self.tool.escape(self.token), self.token)
        self.assertNotEqual(self.tool.escape("caf\u00e9"), "caf\u00e9")

    def test_scan_does_not_treat_empty_input_as_failure_or_success(self):
        result = self.tool.scan_text("")
        self.assertTrue(result.clean)
        self.assertEqual(result.hits, [])

    def test_two_bar_lookalikes_do_not_compose_into_the_token(self):
        # open + bar + name + ASCII '|' + close: one bar short of the token.
        almost = chr(0x003C) + chr(0xFF5C) + "deepseek_image" + "|" + chr(0x003E)
        self.assertFalse(self.tool.contains_raw_token(almost))


class ShippedTreeIsClean(unittest.TestCase):
    """No shipped file may contain the literal token."""

    def setUp(self):
        self.tool = _load(TOOL_PATH, "safe_text_tree")
        self.token = self.tool.raw_token()

    def test_no_shipped_file_contains_the_literal_token(self):
        offenders = []
        for name in SHIPPED_DIRS:
            for path in sorted((REPO_ROOT / name).rglob("*")):
                if not path.is_file():
                    continue
                try:
                    text = path.read_bytes().decode("utf-8", "surrogateescape")
                except OSError:
                    continue
                if self.token in text:
                    offenders.append(str(path.relative_to(REPO_ROOT)))
        self.assertEqual(offenders, [])

    def test_the_scanner_can_actually_see_a_token(self):
        # Negative control for the guard above: a scanner that never matches
        # would report a clean tree.  Build a file the scanner must flag.
        with tempfile.TemporaryDirectory() as tmp:
            planted = Path(tmp) / "planted.txt"
            planted.write_text("planted " + self.token)
            self.assertIn(self.token, planted.read_text())


if __name__ == "__main__":
    unittest.main()