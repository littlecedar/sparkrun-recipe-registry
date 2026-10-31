#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Count the documentation corpus, and keep the entry points' counts honest.

Why this exists.  A global count restated in prose is a claim that rots the
moment the tree changes, and this registry had four of them stale at once
(2026-10-31: `AGENTS.md` said 79 tracked recipes when there were 80, 46 test
modules when there were 51).  The fix is not a reminder to re-measure: it is a
derivation the docs are checked against, so the count cannot drift silently.

Usage:
    python3 tools/doc-census.py            # corpus census + derived facts
    python3 tools/doc-census.py --check    # exit 1 if AGENTS.md/README.md disagree
    python3 tools/doc-census.py --fix      # rewrite the stale numbers in place
    python3 tools/doc-census.py --json     # machine-readable

Scope.  Only the four counts below are checked, because only these are exactly
derivable from the tracked tree.  A count that needs a run to know (the suite's
test total, `recipe validate --strict` passes) is a *dated snapshot* and belongs
in the sentence with its date; it is deliberately not checked here.  The check
covers the entry points only (`ROSTER`): lane docs state lane-scoped counts
("15/15 pass"), which are a different claim and would be false positives.

Stdlib only, no network, no git requirement (falls back to a filesystem walk,
which can see untracked drafts -- so the counts are only authoritative inside a
git checkout).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROSTER = ("AGENTS.md", "README.md")

# fact key -> (glob, exclude-substring, human phrase).  `count` is the number of
# tracked paths matching `glob` that do not contain `exclude`.
FACTS = {
    "recipes": ("recipes/*/*.yaml", None, "tracked recipe files"),
    "test_modules": ("tests/test_*.py", "sync-conflict", "test modules"),
    "profiles": ("benchmarking/*.yaml", None, "benchmark profiles"),
    "skills": (".omp/skills/*/SKILL.md", None, "`SKILL.md` dirs"),
}

ZONES = (
    ("live", ("recipes/", "mods/", "tools/", "benchmarking/", "tuning/", "plugins/", ".omp/")),
    ("frozen", ("attic/",)),
    ("ledger", ("mad-science/",)),
)

# (regex, fact key, group) -- group 2 means the number after a `n/m` pair, as in
# "21/79 fail strict": the total is the denominator.
PATTERNS = (
    (r"(?<![\w.-])(\d+)(?=\s+tracked\s+recipe)", "recipes", 1),
    (r"(?<![\w.-])(\d+)(?=\s+recipes\s+pass\b)", "recipes", 1),
    (r"\b(\d+)/(\d+)\s+(?:fail\s+strict|strict\b)", "recipes", 2),
    (r"(?<![\w.-])(\d+)(?=\s+test\s+modules?\b)", "test_modules", 1),
    (r"(?<![\w.-])(\d+)(?=\s+(?:llama-benchy\s+)?profiles?\b)", "profiles", 1),
    (r"(\d+)(?=\s+`?SKILL\.md`?\s+(?:dirs?|skills?))", "skills", 1),
)


def tracked(root: Path, glob: str) -> list[str]:
    """Tracked paths matching `glob`, or a filesystem walk where git is absent."""
    if (root / ".git").exists():
        out = subprocess.run(
            ["git", "-C", str(root), "ls-files", glob],
            capture_output=True, text=True, check=False,
        )
        if out.returncode == 0:
            return [p for p in out.stdout.splitlines() if p]
    return [str(p.relative_to(root)) for p in root.glob(glob)]


def derive(root: Path) -> dict[str, int]:
    facts = {}
    for key, (glob, exclude, _) in FACTS.items():
        paths = tracked(root, glob)
        if exclude:
            paths = [p for p in paths if exclude not in p]
        facts[key] = len(paths)
    return facts


def zone_of(path: str) -> str:
    for name, prefixes in ZONES:
        if path.startswith(prefixes):
            return name
    return "live"  # root files, and anything a future zone has not claimed yet


def census(root: Path) -> dict:
    files = sorted(f for f in tracked(root, "*") if f.endswith(".md"))
    by_zone: dict[str, dict[str, int]] = {}
    for f in files:
        z = by_zone.setdefault(zone_of(f), {"files": 0, "lines": 0})
        z["files"] += 1
        z["lines"] += len((root / f).read_text(errors="replace").splitlines())
    largest = sorted(files, key=lambda f: -(root / f).stat().st_size)[:8]
    return {
        "zones": by_zone,
        "largest": [[f, len((root / f).read_text(errors="replace").splitlines())] for f in largest],
        "facts": derive(root),
    }


def statements(root: Path, facts: dict[str, int]) -> list[tuple[str, int, str, int, int]]:
    """(file, lineno, fact key, stated, actual) for every checked statement."""
    found = []
    for name in ROSTER:
        path = root / name
        if not path.exists():
            continue
        for lineno, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
            for pattern, key, group in PATTERNS:
                for m in re.finditer(pattern, line):
                    found.append((name, lineno, key, int(m.group(group)), facts[key]))
    return found


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--check", action="store_true", help="exit 1 if a roster count is stale")
    ap.add_argument("--fix", action="store_true", help="rewrite stale counts in place")
    ap.add_argument("--fact", action="append", default=[], metavar="KEY=N",
                    help="override a derived fact (repeatable; for tests)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if not args.root.is_dir():
        print(f"doc-census: no such directory: {args.root}", file=sys.stderr)
        return 2
    facts = derive(args.root)
    for override in args.fact:
        key, _, value = override.partition("=")
        if key not in FACTS or not value.isdigit():
            print(f"doc-census: bad --fact {override!r}", file=sys.stderr)
            return 2
        facts[key] = int(value)

    report = census(args.root)
    report["facts"] = facts
    stale = [s for s in statements(args.root, facts) if s[3] != s[4]]
    report["stale"] = [{"file": f, "line": n, "fact": k, "stated": s, "actual": a} for f, n, k, s, a in stale]

    if args.fix and stale:
        for name in ROSTER:
            path = args.root / name
            if not path.exists():
                continue
            text = path.read_text()
            for pattern, key, group in PATTERNS:
                def repl(m, key=key, group=group):
                    if int(m.group(group)) == facts[key]:
                        return m.group(0)
                    start = m.start(group) - m.start(0)
                    end = m.end(group) - m.start(0)
                    return m.group(0)[:start] + str(facts[key]) + m.group(0)[end:]
                text = re.sub(pattern, repl, text)
            path.write_text(text)
        print(f"doc-census: rewrote {len(stale)} stale count(s)")
        stale = []

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        zones = report["zones"]
        total = sum(z["files"] for z in zones.values())
        line_total = sum(z["lines"] for z in zones.values())
        print(f"{'zone':9} {'files':>6} {'lines':>8}")
        for name in ("live", "frozen", "ledger"):
            z = zones.get(name, {"files": 0, "lines": 0})
            print(f"{name:9} {z['files']:6d} {z['lines']:8d}")
        print(f"{'total':9} {total:6d} {line_total:8d}")
        print("\nfacts (derived, not remembered):")
        for key, value in facts.items():
            print(f"  {value:5d}  {FACTS[key][2]}")
        for name, lineno, key, stated, actual in stale:
            print(f"{name}:{lineno}: {key} stated {stated}, actual {actual}", file=sys.stderr)

    if stale and (args.check or not args.fix):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())