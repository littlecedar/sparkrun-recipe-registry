#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Flag bash-only syntax in shell that declares `sh`, `dash` or `/bin/sh`.

Why this exists.  2026-11-08: seven consecutive red `gate` runs came from one test stub
whose shebang was `#!/bin/sh` and whose body used `${@: -1}`.  This workstation's
`/bin/sh` is bash, so the stub worked here forever; the CI runner's is dash, which
answered "bad substitution", the stub printed nothing, and `run-arm.sh` exited 10 three
times per run.  A guard that only runs the code cannot find this: the difference is the
interpreter, and no `dash` is installed here to try.  So the text is read instead.

Scope.  Shell-bearing text only: a `.sh` file whose shebang is sh-family, and any
string literal inside `tests/*.py` that opens with such a shebang (the stub a test
writes for `ssh`, `docker`, `sparkrun`, ...).  A bash/zsh/ksh shebang is skipped on
purpose -- `bash -n` is CI's job for those.

shortcut: literals are read as the parser sees them (adjacent literals merge, f-strings
contribute their constant parts); a stub assembled from `+` or a variable is not
reconstructed, and a reported line inside a multi-line literal is the literal's start
plus its offset, which is the shape these stubs are written in.

Usage:
    uv run python -B tools/bash-ism-lint.py              # this checkout
    uv run python -B tools/bash-ism-lint.py --root DIR   # an extracted archive or fixture

Exit: 0 clean, 1 findings (printed as `path:line: construct: line`), 2 could not scan.
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: An `sh`-family shebang, bare or through env. `bash`/`zsh`/`ksh` are deliberately not here.
SH_SHEBANG = re.compile(r"^#!\s*(?:/bin/|/usr/bin/env\s+|/usr/bin/)(sh|dash)\s*$")

#: (name, pattern) -- bash-only constructs that dash rejects or reads differently.
CONSTRUCTS = (
    ("positional-parameter slice", re.compile(r"\$\{[@*]:")),
    ("[[ ... ]] test", re.compile(r"\[\[")),
    ("function keyword", re.compile(r"^\s*function\s+\w+\s*(?:\(\s*\))?\s*\{")),
    ("local (not POSIX)", re.compile(r"^\s*local\s+\w+=")),
)
#: `==` is bash's spelling inside `[ ]`; POSIX says `=`. Checked separately because `[[ ]]`
#: lines are already flagged and use `==` legally.
SINGLE_BRACKET_EQ = re.compile(r"\[(?!\[)[^\]]*==")


def shebang_of(shell: str) -> str:
    """The first line when it is a shebang, else empty."""
    first = shell.splitlines()[0].strip() if shell.strip() else ""
    return first if first.startswith("#!") else ""


def findings_in_shell(shell: str) -> list[tuple[int, str, str]]:
    """(line, construct, line text) for every bash-ism in a shell snippet."""
    hits = []
    for n, line in enumerate(shell.splitlines(), 1):
        for name, pattern in CONSTRUCTS:
            if pattern.search(line):
                hits.append((n, name, line.strip()))
        if "[[" not in line and SINGLE_BRACKET_EQ.search(line):
            hits.append((n, "== in a single-bracket test (POSIX is =)", line.strip()))
    return hits


def literal_snippets(source: str) -> list[tuple[int, str]]:
    """(lineno, text) for every string literal that opens with an sh-family shebang."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            text = node.value
        elif isinstance(node, ast.JoinedStr):
            text = "".join(v.value for v in node.values
                           if isinstance(v, ast.Constant) and isinstance(v.value, str))
        else:
            continue
        if SH_SHEBANG.match(shebang_of(text)):
            out.append((node.lineno, text))
    return out


def files(root: Path) -> list[Path]:
    """The shell-bearing text this checks: repo shell scripts and test-written stubs."""
    found = []
    for pattern in ("tools/*.sh", "tests/*.sh", "mods/**/*.sh", "recipes/**/mods/**/*.sh",
                    "recipes/**/*.sh", "plugins/**/*.sh"):
        found.extend(root.glob(pattern))
    found.extend(root.glob("tests/test_*.py"))
    return sorted(set(p for p in found if p.is_file()))


def scan(root: Path) -> list[str]:
    """`path:line: construct: line` for every finding under `root`."""
    hits = []
    for path in files(root):
        rel = path.relative_to(root).as_posix()
        source = path.read_text(errors="replace")
        if path.suffix == ".py":
            snippets = literal_snippets(source)
        else:
            snippets = [(1, source)] if SH_SHEBANG.match(shebang_of(source)) else []
        for start, shell in snippets:
            for n, name, line in findings_in_shell(shell):
                hits.append(f"{rel}:{start + n - 1}: {name}: {line[:120]}")
    return hits


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=ROOT)
    args = ap.parse_args(argv)
    if not args.root.is_dir():
        print(f"bash-ism-lint: no such directory: {args.root}", file=sys.stderr)
        return 2
    if not files(args.root):
        print(f"bash-ism-lint: nothing to scan under {args.root}", file=sys.stderr)
        return 2
    hits = scan(args.root)
    for hit in hits:
        print(hit)
    print(f"bash-ism-lint: {len(hits)} finding(s) under {args.root}")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
