"""Guards recipes/MECHANICS.md — every `file.py:line` cite lands inside the installed package.

Run: uv run python -B -m unittest tests.test_mechanics_cites -v

Why this file exists. Every cite in that doc is `file.py:NN[-MM]` relative to the installed
sparkrun package, and the line numbers move whenever the build does: the 2026-11-22 sweep
re-derived 59 anchors and found two more that a build bump had invalidated in sections
re-derived a week earlier. A range past the end of its file is the worst of those — the
reader lands in unrelated code and trusts it — and nothing else in the tree reads this doc.

What it does NOT do: judge whether the cited range still states the claim. That needs the
sentence re-read against the source, which is what the sweep is. This guard keeps a cite
*resolvable*, and its failure message names the build so the reader knows which one to
re-derive against.

Stdlib only. The package is located with `find_spec`, and the module skips when sparkrun is
not installed (CI installs it opportunistically, so an absent package is not a failure).
"""

from __future__ import annotations

import importlib.util
import re
import shutil
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOC = REPO_ROOT / "recipes" / "MECHANICS.md"

#: ``file.py:NN`` or ``file.py:NN-MM``, the doc's only cite form.
CITE = re.compile(r"`([A-Za-z0-9_./-]+\.(?:py|sh|jinja|md)):(\d+)(?:-(\d+))?`")

#: Cites into evidence outside the package tree: agent memory and the vendored SGLang source.
#: They are `src:` footnotes, not package anchors, so their line numbers cannot be re-derived
#: against an installed build and this guard does not judge them.
FOREIGN = (".swival/", "srt/")


def package_root() -> Path | None:
    """The installed sparkrun package directory, or None when it cannot be located.

    Import is not enough: the registry's own venv does not depend on sparkrun, and the tool
    lives in its own `uv tool` environment. So fall back to the `sparkrun` executable on PATH
    and read the package out of that environment's `site-packages` — the same tree the doc
    names.
    """
    try:
        spec = importlib.util.find_spec("sparkrun")
    except (ImportError, ValueError):
        spec = None
    if spec is not None and spec.submodule_search_locations:
        return Path(next(iter(spec.submodule_search_locations)))
    exe = shutil.which("sparkrun")
    if not exe:
        return None
    for base in Path(exe).resolve().parents:
        found = sorted(base.glob("lib/python*/site-packages/sparkrun"))
        if found:
            return found[0]
    return None


def cite_problems(text: str, root: Path) -> list[str]:
    """Cites that do not resolve inside `root`, as `file:range — why` strings (pure).

    A cite resolves when its file exists under the package root and its range is inside the
    file and non-empty. Nothing here reads the cited code.
    """
    problems: list[str] = []
    cache: dict[Path, int] = {}
    for match in CITE.finditer(text):
        rel, start, end = match.group(1), int(match.group(2)), match.group(3)
        if rel.startswith(FOREIGN):
            continue
        path = root / rel
        if path not in cache:
            cache[path] = len(path.read_text(encoding="utf-8", errors="replace").split("\n")) if path.is_file() else 0
        length = cache[path]
        if not length:
            problems.append(f"{rel}:{start}{'-' + end if end else ''} — no such file under {root}")
            continue
        last = int(end) if end else start
        if start < 1 or last < start or last > length:
            problems.append(f"{rel}:{start}{'-' + end if end else ''} — outside 1-{length}")
    return problems


class MechanicsCites(unittest.TestCase):
    """Every package-tree cite in the doc resolves in the build it names."""

    def setUp(self) -> None:
        root = package_root()
        if root is None:
            self.skipTest("sparkrun is not installed; its package tree cannot be read")
        self.root = root
        self.text = DOC.read_text(encoding="utf-8")

    def test_every_cite_resolves_inside_the_installed_package(self):
        version = "the installed build"
        try:
            from importlib.metadata import version as dist_version

            version = dist_version("sparkrun")
        except Exception:  # noqa: BLE001 - a version string is a courtesy, not the assertion
            pass
        self.assertEqual(
            cite_problems(self.text, self.root), [],
            f"recipes/MECHANICS.md cites code that is not there in sparkrun {version} "
            f"({self.root}); re-derive the range against that build and update the "
            "Cite provenance paragraph with its name")

    def test_the_doc_names_the_build_it_was_derived_against(self):
        """A sweep that does not name its build cannot be checked, only believed."""
        self.assertRegex(self.text, r"\*\*0\.\d+\.\d+[^*]*\*\*", "no build named in the header")

    def test_negative_control_an_out_of_range_cite_is_reported(self):
        fake = "`core/recipe.py:1-999999` and `core/absent.py:1`"
        found = cite_problems(fake, self.root)
        self.assertEqual(len(found), 2, found)
        self.assertIn("outside", found[0])
        self.assertIn("no such file", found[1])

    def test_negative_control_foreign_cites_are_not_judged(self):
        """The `.swival`/`srt` footnotes have no package file, and flagging them would be noise."""
        self.assertEqual(cite_problems("`.swival/HISTORY.md:4010`", self.root), [])


if __name__ == "__main__":
    unittest.main()
