# SPDX-FileCopyrightText: 2026 Travis Wichert
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Guard the repo rule that `mods/` is *shared-only* and every lane-local mod
lives beside its lane in `recipes/<lane>/mods/<mod>/`.

Why the rule exists. sparkrun resolves a `mods:` entry in this order: (1) a
`@registry/...` entry from that registry's cloned `mods/` dir; (2) ADJACENT to
the recipe, i.e. `<recipe_dir>/mods/<name>`; (3) this registry's `mods/`; (4)
the `eugr` fallback. A mod that only one lane needs, kept in the shared `mods/`
root, is therefore a mod whose blast radius nobody asked for: the shared root is
what a *published* registry clone exposes to every consumer, and it is what
`@littlecedar/mods/<name>` resolves against. Keeping a lane's mod in the shared
root means it ships with the registry, is visible to every other lane, and can
be silently reordered or repurposed by an unrelated recipe.

So the layout rule is symmetric: a shared mod must be genuinely shared (used by
2+ lanes), and a lane-local mod must be lane-local (referenced only from its own
lane, and referenced UNSCOPED as `mods/<name>` so the adjacent-resolution rung
finds it -- after the move, `@littlecedar/mods/<name>` would resolve against the
published clone, which does not have the lane dir, and the launch would fail).

Only refs that bind to THIS tree count as a lane's use of a mod: a bare
`mods/<name>`, or an `@littlecedar/mods/<name>`. An `@eugr/mods/<name>` entry
binds to eugr's copy, so it is not evidence that *our* `mods/<name>` is shared --
classifying by basename across registries is the "a substring test is not an
identifier" error, and it passes too much precisely because the result looks
plausible. The one mod whose cross-lane role is documented rather than consumed
in-tree is named explicitly in `SHARED_BY_DESIGN` instead of being inferred from
another registry's refs.

Recipes are parsed as text (stdlib only, no PyYAML); whole-line comments are
stripped before matching so a comment quoting an entry is inert. An empty or
missing parse RAISES -- a guard that silently sees zero recipes, zero mods, or a
`mods:` block with no entries would pass vacuously, which is the failure this
module exists to prevent. Every rule has a matching negative control that
sabotages a synthetic layout and asserts the rule reports it.

Run:
    uv run python -B -m unittest tests.test_mods_lane_locality -v
"""
from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RECIPES_DIR = REPO_ROOT / "recipes"
MODS_DIR = REPO_ROOT / "mods"

# `mod-template` is the scaffold every new mod is copied from, not a mod any
# recipe references, so the shared-only rule does not apply to it.
SHARED_EXEMPT = frozenset({"mod-template"})

# Mods that stay in `mods/` on documented cross-lane grounds rather than because
# this tree's recipes reference them. `drop-caches` is listed by recipes in four
# lanes (cybersec, ornith, qwen3, qwen4) as `@eugr/mods/drop-caches`; that pulls
# eugr's copy, which is INERT, while this repo's `mods/drop-caches` is its fixed,
# fail-closed counterpart -- mechanism in its README, guarded by
# `tests/test_drop_caches_mod.py` and `attic/ds4/AGENTS.md`. Four lanes are its
# audience, so it is not a lane's mod; it is named here rather than counted, so
# rule A stays honest about what "shared" means.
SHARED_BY_DESIGN = frozenset({"drop-caches"})

_COMMENT_LINE = re.compile(r"(?m)^\s*#.*$")
_MODS_BLOCK = re.compile(r"(?m)^mods:[ \t]*\n((?:(?:[ \t].*)?\n|[ \t].*\Z)*)")
_MODS_ENTRY = re.compile(r"(?m)^[ \t]*-[ \t]*(.+?)[ \t]*$")


def strip_comment_lines(text: str) -> str:
    """Drop whole-line `#` comments so prose quoting an entry is inert."""
    return _COMMENT_LINE.sub("", text)


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def basename(entry: str) -> str:
    """The mod directory name a `mods:` entry points at."""
    return entry.split("/")[-1]


def binds_to_tree(entry: str) -> bool:
    """Whether a `mods:` entry resolves to a mod in THIS registry's tree.

    A bare `mods/<name>` and `@littlecedar/mods/<name>` both do. Any other
    `@<registry>/mods/<name>` binds to that registry's own copy and says nothing
    about ours, so it must not be counted as this tree's use of the name.
    """
    head, sep, _rest = entry[1:].partition("/mods/")
    if not entry.startswith("@"):
        return True
    return sep != "" and head == "littlecedar"


def parse_mods_block(text: str) -> list[str] | None:
    """The `mods:` entries of a recipe, or None when the recipe declares none.

    A `mods:` key that yields zero entries is a parse failure and RAISES: an
    empty parse is never the same as "no mods declared".
    """
    match = _MODS_BLOCK.search(text)
    if match is None:
        if re.search(r"(?m)^mods:", text):
            raise ValueError("`mods:` key present but its block did not parse")
        return None
    entries = [_unquote(raw) for raw in _MODS_ENTRY.findall(match.group(1))]
    if not entries:
        raise ValueError("`mods:` block carries no entries")
    return entries


def iter_recipes(recipes_dir: Path = RECIPES_DIR) -> list[Path]:
    """Every `recipes/*/*.yaml`, newest-first order irrelevant; empty RAISES."""
    paths = sorted(recipes_dir.glob("*/*.yaml"))
    if not paths:
        raise ValueError(f"no recipes found under {recipes_dir}")
    return paths


def recipe_refs(recipes_dir: Path = RECIPES_DIR) -> list[tuple[str, Path, tuple[str, ...]]]:
    """(lane, recipe path, mods entries) for every recipe, comments stripped."""
    refs: list[tuple[str, Path, tuple[str, ...]]] = []
    for path in iter_recipes(recipes_dir):
        lane = path.relative_to(recipes_dir).parts[0]
        entries = parse_mods_block(strip_comment_lines(path.read_text(encoding="utf-8")))
        refs.append((lane, path, tuple(entries or ())))
    if not refs:
        raise ValueError(f"no recipes parsed under {recipes_dir}")
    return refs


def shared_mod_dirs(mods_dir: Path = MODS_DIR) -> dict[str, Path]:
    """The `mods/` directories subject to the shared-only rule; empty RAISES."""
    dirs = {
        d.name: d
        for d in sorted(mods_dir.iterdir())
        if d.is_dir() and d.name not in SHARED_EXEMPT
    }
    if not dirs:
        raise ValueError(f"no shared mods found under {mods_dir}")
    return dirs


def lane_usage(refs: list[tuple[str, Path, tuple[str, ...]]]) -> dict[str, set[str]]:
    """lane -> mod directory names it references IN THIS TREE (`binds_to_tree`)."""
    usage: dict[str, set[str]] = {}
    for lane, _path, entries in refs:
        for entry in entries:
            if binds_to_tree(entry):
                usage.setdefault(lane, set()).add(basename(entry))
    return usage


def lane_mod_dirs(recipes_dir: Path = RECIPES_DIR) -> dict[str, set[str]]:
    """lane -> set of mod directory names under `recipes/<lane>/mods/`."""
    out: dict[str, set[str]] = {}
    for lane_dir in sorted(recipes_dir.iterdir()):
        mods = lane_dir / "mods"
        if mods.is_dir():
            out[lane_dir.name] = {d.name for d in mods.iterdir() if d.is_dir()}
    return out


# --- A: mods/ is shared-only -------------------------------------------------

def shared_only_violations(
    shared: dict[str, Path] | set[str], usage: dict[str, set[str]]
) -> list[str]:
    """Shared mods referenced by fewer than two lanes, bar the by-design set."""
    bad: list[str] = []
    for name in sorted(shared):
        if name in SHARED_BY_DESIGN:
            continue
        lanes = sorted(lane for lane, names in usage.items() if name in names)
        if len(lanes) < 2:
            bad.append(f"mods/{name}: referenced by {lanes or 'no lane'}")
    return bad


# --- B: no cross-lane lane-mod ----------------------------------------------

def cross_lane_violations(
    lane_mods: dict[str, set[str]],
    refs: list[tuple[str, Path, tuple[str, ...]]],
) -> list[str]:
    """A recipe outside `recipes/<lane>/` referencing `<lane>`'s local mod."""
    bad: list[str] = []
    for lane, path, entries in refs:
        for entry in entries:
            if not binds_to_tree(entry):
                continue
            name = basename(entry)
            for owner, names in lane_mods.items():
                if name in names and owner != lane:
                    bad.append(
                        f"{_rel(path)}: lane {lane} references lane-{owner} mod {name}"
                    )
    return bad


# --- C: resolvability --------------------------------------------------------

def resolve_ok(entry: str, recipe_dir: Path, shared_root: Path) -> bool:
    """Whether sparkrun's documented resolution order can find `entry`.

    Scoped `@littlecedar/mods/<n>` resolves ONLY against the registry's shared
    `mods/`. Any other `@registry/mods/<n>` is an external registry this tree
    cannot see, so it is skipped rather than failed. An unscoped entry resolves
    adjacent to the recipe or against the shared root.
    """
    if entry.startswith("@"):
        head, sep, rest = entry[1:].partition("/mods/")
        if not sep or head != "littlecedar":
            return True
        return (shared_root / basename(rest)).is_dir()
    name = basename(entry)
    return (
        (recipe_dir / "mods" / name).is_dir()
        or (recipe_dir / name).is_dir()
        or (shared_root / name).is_dir()
    )


def unresolvable(
    refs: list[tuple[str, Path, tuple[str, ...]]], shared_root: Path = MODS_DIR
) -> list[str]:
    bad: list[str] = []
    for _lane, path, entries in refs:
        for entry in entries:
            if not resolve_ok(entry, path.parent, shared_root):
                bad.append(f"{_rel(path)}: {entry}")
    return bad


# --- D: no scoped ref to a lane mod -----------------------------------------

def scoped_lane_mod_violations(
    lane_mod_names: set[str],
    refs: list[tuple[str, Path, tuple[str, ...]]],
) -> list[str]:
    """`@littlecedar/mods/<n>` where `<n>` is a lane-local mod directory."""
    bad: list[str] = []
    for _lane, path, entries in refs:
        for entry in entries:
            if entry.startswith("@littlecedar/mods/") and basename(entry) in lane_mod_names:
                bad.append(f"{_rel(path)}: scoped ref {entry} to lane-local mod")
    return bad


# --- lane-mod harness --------------------------------------------------------

def lane_mods_without_run_sh(
    recipes_dir: Path = RECIPES_DIR,
) -> list[str]:
    """Lane mod dirs lacking a `run.sh` -- a stray dir is a fail-closed error."""
    bad: list[str] = []
    for lane_dir in sorted(recipes_dir.iterdir()):
        mods = lane_dir / "mods"
        if not mods.is_dir():
            continue
        for d in sorted(mods.iterdir()):
            if d.is_dir() and not (d / "run.sh").is_file():
                bad.append(_rel(d / "run.sh"))
    return bad


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


class SharedOnly(unittest.TestCase):
    def test_every_shared_mod_serves_two_or_more_lanes(self) -> None:
        violations = shared_only_violations(shared_mod_dirs(), lane_usage(recipe_refs()))
        self.assertEqual([], violations)


class LaneLocality(unittest.TestCase):
    def test_no_lane_reaches_another_lanes_mod(self) -> None:
        violations = cross_lane_violations(lane_mod_dirs(), recipe_refs())
        self.assertEqual([], violations)


class Resolvability(unittest.TestCase):
    def test_every_mods_entry_resolves(self) -> None:
        violations = unresolvable(recipe_refs())
        self.assertEqual([], violations)


class ScopedRefs(unittest.TestCase):
    def test_no_scoped_ref_to_a_lane_mod(self) -> None:
        names = {n for names in lane_mod_dirs().values() for n in names}
        violations = scoped_lane_mod_violations(names, recipe_refs())
        self.assertEqual([], violations)


class LaneModHarness(unittest.TestCase):
    def test_every_lane_mod_ships_a_run_sh(self) -> None:
        self.assertEqual([], lane_mods_without_run_sh())


class NegativeControls(unittest.TestCase):
    """Every rule above must fail on the mutation it exists for."""

    def test_control_single_lane_shared_mod_is_caught(self) -> None:
        shared = {"pip-install-orjson"}
        usage = {"embed": {"pip-install-orjson"}}
        self.assertTrue(shared_only_violations(shared, usage))

    def test_control_shared_mod_with_two_lanes_passes(self) -> None:
        shared = {"pip-install-orjson"}
        usage = {"embed": {"pip-install-orjson"}, "rerank": {"pip-install-orjson"}}
        self.assertEqual([], shared_only_violations(shared, usage))

    def test_control_cross_lane_reference_is_caught(self) -> None:
        lane_mods = {"qwen4": {"fix-labquant-modelopt-mixed-flat-schema"}}
        refs: list[tuple[str, Path, tuple[str, ...]]] = [
            ("cybersec", Path("recipes/cybersec/r.yaml"),
             ("mods/fix-labquant-modelopt-mixed-flat-schema",)),
        ]
        self.assertTrue(cross_lane_violations(lane_mods, refs))

    def test_control_unresolvable_scoped_ref_is_caught(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "mods").mkdir()
            recipe_dir = root / "recipes" / "cybersec"
            recipe_dir.mkdir(parents=True)
            # `@littlecedar/mods/ghost` must resolve against the shared root; the
            # mod was moved lane-local, so the scoped ref is broken.
            self.assertFalse(
                resolve_ok("@littlecedar/mods/ghost", recipe_dir, root / "mods")
            )
            # The same entry unscoped resolves adjacent and is fine.
            (recipe_dir / "mods" / "ghost").mkdir(parents=True)
            self.assertTrue(resolve_ok("mods/ghost", recipe_dir, root / "mods"))

    def test_control_unresolvable_is_reported_per_recipe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "mods").mkdir()
            recipe_dir = root / "recipes" / "ds4"
            recipe_dir.mkdir(parents=True)
            recipe = recipe_dir / "r.yaml"
            recipe.write_text("mods:\n  - '@littlecedar/mods/dsv41-sglang-overlay'\n")
            refs = recipe_refs(root / "recipes")
            self.assertTrue(unresolvable(refs, root / "mods"))

    def test_control_scoped_ref_to_lane_mod_is_caught(self) -> None:
        refs: list[tuple[str, Path, tuple[str, ...]]] = [
            ("ds4", Path("recipes/ds4/r.yaml"),
             ("@littlecedar/mods/dsv41-sglang-overlay",)),
        ]
        self.assertTrue(
            scoped_lane_mod_violations({"dsv41-sglang-overlay"}, refs)
        )

    def test_control_external_registry_ref_is_skipped(self) -> None:
        # `@eugr/mods/*` is not this tree's to resolve, and it still counts as
        # the lane's use of the shared mod name.
        self.assertTrue(
            resolve_ok("@eugr/mods/drop-caches", Path("recipes/ornith"), MODS_DIR)
        )

    def test_control_external_registry_ref_is_not_a_lane_use(self) -> None:
        refs: list[tuple[str, Path, tuple[str, ...]]] = [
            ("ornith", Path("recipes/ornith/r.yaml"), ("@eugr/mods/drop-caches",)),
        ]
        self.assertEqual({}, lane_usage(refs), "eugr's copy is not our mod")
        self.assertFalse(binds_to_tree("@eugr/mods/drop-caches"))
        self.assertTrue(binds_to_tree("@littlecedar/mods/drop-caches"))
        self.assertTrue(binds_to_tree("mods/drop-caches"))

    def test_control_by_design_shared_mod_needs_no_tree_consumer(self) -> None:
        self.assertEqual([], shared_only_violations({"drop-caches"}, {}))
        self.assertTrue(shared_only_violations({"some-lane-mod"}, {}))

    def test_control_cross_lane_ignores_a_foreign_registry_ref(self) -> None:
        lane_mods = {"qwen4": {"fix-labquant-modelopt-mixed-flat-schema"}}
        refs: list[tuple[str, Path, tuple[str, ...]]] = [
            ("cybersec", Path("recipes/cybersec/r.yaml"),
             ("@eugr/mods/fix-labquant-modelopt-mixed-flat-schema",)),
        ]
        self.assertEqual([], cross_lane_violations(lane_mods, refs))

    def test_control_empty_mods_block_raises(self) -> None:
        with self.assertRaises(ValueError):
            parse_mods_block("mods:\n\ndecode: x\n")

    def test_control_absent_mods_block_is_none(self) -> None:
        self.assertIsNone(parse_mods_block("model: foo\ncommand: x\n"))

    def test_control_no_recipes_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(ValueError):
            iter_recipes(Path(tmp))

    def test_control_shared_mods_scan_empty_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(ValueError):
            shared_mod_dirs(Path(tmp))

    def test_control_lane_mod_without_run_sh_is_caught(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "explore" / "mods" / "stray").mkdir(parents=True)
            self.assertTrue(lane_mods_without_run_sh(root))


if __name__ == "__main__":
    unittest.main()
