#!/usr/bin/env python3
"""Attribute a fleet ``sparkrun`` runtime-cache census to recipes, and answer
"is this tree stale?" without guesswork.

Why this exists.  ``~/.cache/sparkrun/runtime-cache/<family>/<model_key>`` holds
compiled/autotuned artifacts (torch.compile, Inductor, Triton, FlashInfer,
TRT-LLM autotuner).  It is a cache, so every tree is *disposable* — the only
question that matters is which trees something still serves, because a wrong
answer either recompiles for an hour or deletes a live tree.  sparkrun's own
sweep (``sparkrun setup prune-runtime-cache``) can only age trees by their
last-used marker; it knows nothing about which of them the registry still
ships.  This tool supplies that half.

The decisive test is the leaf key, not the mod logs.  ``sparkrun`` builds the
leaf as ``<family>/<model_key>`` where

    model_key = sanitize(model)[:48] + "-" + sha256("<model>@<model_revision>")[:8]

(``sparkrun/core/runtime_cache.py: model_key`` / ``sanitize_key_component`` /
``_short_hash``).  So the 8-hex suffix IS the identity: it folds in the pinned
revision.  Two trees of the same model with different suffixes are two
different pins, and a suffix no recipe's ``model@revision`` hashes to is
material nothing can re-enter.  Measured 2026-10-15 on the ds4 lane, where the
``modlogs/`` heuristic in AGENTS.md could not separate them: the live tree
(``…-11826f49``, the recipe's current pin) and the superseded one
(``…-9a74d993``, the same model with an *empty* revision) both carry
``modlogs/dsv41-sglang-overlay.log`` and the same mod set.

What this tool does NOT do: it deletes nothing and it never calls a tree stale
on recency.  A tree listed STALE is one no *shipped* recipe and no *attic* arm
produces the key for; whether to reclaim it is the policy's call
(``mad-science/STORAGE-POLICY.md``), and a tree touched inside the ~72 h window
is in use whatever its provenance.

Stdlib only, no network, no cluster access.  Input is a read-only census:

    sparkrun setup prune-runtime-cache --hosts .30,.31,.32,.33,.34,.35 \\
        --all --dry-run > census.txt
    uv run python -B tools/cache-audit.py --census census.txt --budget-gb 2000

Any line carrying ``<host>:/absolute/path`` is parsed; an optional size beside
it (``94.8 GB`` or ``49980704K``) and an optional ``YYYY-MM-DD[ _]HH:MM``
timestamp are used when present and ignored when not — so the ``--all
--dry-run`` receipt works as-is, and so does a ``du -sk`` / ``stat`` listing of
the same trees.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Marker sparkrun re-stamps in the leaf on every launch; both sweeps age by it
#: (``sparkrun/core/runtime_cache.py: LAST_USED_MARKER``), and a tree without
#: one is invisible to them.
LAST_USED_MARKER = ".sparkrun-last-used"

#: A tree touched inside this window is in use whatever its provenance
#: (AGENTS.md, "Node hygiene").
IN_USE_HOURS = 72

_LINE = re.compile(
    r"(?P<host>[A-Za-z0-9][A-Za-z0-9._-]*):(?P<path>/[^\s:]+)"
    r"(?:\s+(?P<stamp>\d{4}-\d{2}-\d{2}(?:[ _]\d{2}:\d{2})?))?"
)
#: A `##### <host>` (or `host: <host>`) line opens a section whose hostless
#: `du`/`ls` lines belong to it — the shape both of this repo's census receipts
#: use, since the accepting command is run once per node.
_HOST_HEADER = re.compile(r"^\s*(?:#{2,}|host:)\s*(?P<host>[A-Za-z0-9][A-Za-z0-9._-]*)\s*$")
_SIZE = re.compile(r"(?P<num>\d+(?:\.\d+)?)\s*(?P<unit>GB|G|MB|M|K|B)\b")
_SCALE = {"B": 1, "K": 1024, "M": 1024**2, "G": 1024**3, "GB": 1024**3, "MB": 1024**2}

_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")
_COLLAPSE = re.compile(r"-{2,}")
_MAX_LABEL_LEN = 48

_MODEL_KEY = re.compile(r"^model:\s*(.+?)\s*$", re.MULTILINE)
_REVISION_KEY = re.compile(r"^model_revision:\s*(\S+)\s*$", re.MULTILINE)


# ---------------------------------------------------------------------------
# Key construction — mirrors sparkrun/core/runtime_cache.py
# ---------------------------------------------------------------------------


def sanitize_key_component(text: str, max_len: int = _MAX_LABEL_LEN) -> str:
    """sparkrun's ``sanitize_key_component``: ``/`` -> ``__``, everything
    outside ``[A-Za-z0-9._-]`` -> ``-``, runs collapsed, ends stripped, then
    truncated to *max_len* and stripped again.  The truncation is why the AEON
    arm's directory is ``…-AEON-ULTIMATE-UNCENSO-b9f737e7``.
    """
    cleaned = text.strip().replace("/", "__")
    cleaned = _UNSAFE_CHARS.sub("-", cleaned)
    cleaned = _COLLAPSE.sub("-", cleaned).strip("-._")
    cleaned = cleaned[:max_len].strip("-._")
    return cleaned or "unknown"


def model_key(model: str, revision: str = "") -> str:
    """The leaf component sparkrun derives for *model* pinned at *revision*."""
    model, revision = str(model or ""), str(revision or "")
    label = sanitize_key_component(model.rstrip("/").rsplit("/", 1)[-1] if model.startswith("/") else model)
    return f"{label}-{hashlib.sha256(f'{model}@{revision}'.encode('utf-8', 'replace')).hexdigest()[:8]}"


def strip_comment_lines(text: str) -> str:
    return "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))


def recipe_keys(root: Path | None = None) -> dict[str, list[str]]:
    """``{model_key: ["shipped:recipes/…" | "retired:attic/…", …]}`` for every
    recipe naming a resolvable model.

    ``recipes/`` is the shipped set and is authoritative for "live"; ``attic/``
    arms are retired but still launchable, so their keys stay separate rather
    than folded in.  An absolute-path model hashes its path (label = directory
    name), so node-local checkpoints get a key like any other.
    """
    root = root or REPO_ROOT
    found: dict[str, list[str]] = {}
    for kind, pattern in (("shipped", "recipes/*/*.yaml"), ("retired", "attic/**/*.yaml")):
        for path in sorted(root.glob(pattern)):
            text = strip_comment_lines(path.read_text(encoding="utf-8", errors="replace"))
            match = _MODEL_KEY.search(text)
            if not match:
                continue
            model = match.group(1).strip().strip("\"'")
            if not model or model.startswith("{"):
                continue  # a placeholder or a derived arm: not a repo id
            rev = _REVISION_KEY.search(text)
            revision = rev.group(1).strip().strip("\"'") if rev else ""
            found.setdefault(model_key(model, "" if revision.startswith("{") else revision), []).append(
                f"{kind}:{path.relative_to(root).as_posix()}"
            )
    return found


# ---------------------------------------------------------------------------
# Census parsing
# ---------------------------------------------------------------------------


class Tree:
    __slots__ = ("host", "path", "size", "stamp")

    def __init__(self, host: str, path: str, size: int | None = None, stamp: str | None = None):
        self.host, self.path, self.size, self.stamp = host, path, size, stamp

    @property
    def family(self) -> str:
        parts = self.path.rstrip("/").split("/")
        return parts[-2] if len(parts) >= 2 else ""

    @property
    def leaf(self) -> str:
        return self.path.rstrip("/").split("/")[-1]

    @property
    def keyed(self) -> bool:
        """True when the leaf is a keyed child of a family root.  The sweep's
        own arithmetic (it prunes nothing when ``leaf == family_root``): after
        the ``runtime-cache`` root there must be a family AND a key."""
        parts = [p for p in self.path.rstrip("/").split("/") if p]
        if "runtime-cache" not in parts:
            return False
        return len(parts) - parts.index("runtime-cache") >= 3


_STAMP = re.compile(r"\d{4}-\d{2}-\d{2}(?:[ _]\d{2}:\d{2})?")


def _size_in(text: str) -> int | None:
    match = _SIZE.search(text)
    return int(float(match.group("num")) * _SCALE[match.group("unit")]) if match else None


def parse_census(paths: list[Path]) -> list[Tree]:
    """Every ``<host>:<runtime-cache path>`` in *paths*, plus hostless
    ``du``/``ls`` lines attributed to the nearest preceding ``##### <host>``.

    Rows are deduplicated by ``(host, path)`` and **merged**, never dropped:
    the same tree appears in the coarse ``--dry-run`` receipt (sizes rounded to
    0.1 GB, no marker) and in a ``du``/``stat`` listing (KiB, with the marker),
    so a missing stamp or a smaller size is filled from the other source.  A
    first-wins rule would report every tree as unmarked and pin its age at
    unknown — exactly the bug this tool exists to prevent.
    """
    trees: dict[tuple[str, str], Tree] = {}
    order: list[tuple[str, str]] = []

    def add(host: str, path: str, before: str) -> None:
        stamp = _STAMP.search(before)
        size = _size_in(before)
        key = (host, path)
        found = trees.get(key)
        if found is None:
            trees[key] = Tree(host, path, size, stamp.group(0) if stamp else None)
            order.append(key)
            return
        if found.stamp is None and stamp:
            found.stamp = stamp.group(0)
        if size is not None and (found.size is None or size > found.size):
            found.size = size

    for receipt in paths:
        host = "-"
        for raw in receipt.read_text(encoding="utf-8", errors="replace").splitlines():
            header = _HOST_HEADER.match(raw)
            if header:
                host = header.group("host")
                continue
            match = _LINE.search(raw)
            if match:
                add(match.group("host"), match.group("path"), raw[: match.start("path")])
                continue
            if "runtime-cache/" in raw:  # hostless `du -sk` / `stat` output
                for bare in re.finditer(r"(?P<path>/[^\s:]*runtime-cache/[^\s:]+)", raw):
                    add(host, bare.group("path"), raw[: bare.start("path")])
    return [trees[key] for key in order]


# ---------------------------------------------------------------------------
# Verdicts
# ---------------------------------------------------------------------------


def age_hours(stamp: str | None, now: dt.datetime | None = None) -> float | None:
    """Hours since *stamp* (``YYYY-MM-DD`` or ``YYYY-MM-DD_HH:MM``).  A bare
    date resolves to 00:00, so it reports the *oldest* possible age — a bare-day
    listing never looks fresher than it is."""
    if not stamp:
        return None
    text = stamp.replace("_", " ")
    when = dt.datetime.strptime(text, "%Y-%m-%d %H:%M" if " " in text else "%Y-%m-%d")
    return ((now or dt.datetime.now()) - when).total_seconds() / 3600.0


def verdict(tree: Tree, keys: dict[str, list[str]]) -> tuple[str, str]:
    """``(verdict, owning recipe or reason)``: ``live`` (a shipped recipe
    produces this key), ``retired`` (only an attic arm), ``stale`` (nothing
    does), ``unkeyed`` (not a keyed child)."""
    if not tree.keyed:
        return "unkeyed", "leaf is not a keyed child of a family root"
    hits = keys.get(tree.leaf)
    if not hits:
        return "stale", "no shipped or attic model@revision hashes to this key"
    return ("live" if hits[0].startswith("shipped:") else "retired"), hits[0].split(":", 1)[1]


def reclaim_note(tree: Tree, kind: str, now: dt.datetime) -> str:
    """The action for a non-live tree, or ``""`` when it is not reclaimable
    yet.  Nothing here is executed."""
    if kind == "live":
        return ""
    if tree.stamp is None:
        return f"no {LAST_USED_MARKER} marker: both sparkrun sweeps skip it — remove by absolute path after a look"
    hours = age_hours(tree.stamp, now)
    if hours is None or hours < IN_USE_HOURS:
        return f"touched {hours:.0f} h ago: in use by the {IN_USE_HOURS}h rule, re-check later"
    return f"sparkrun setup prune-runtime-cache --hosts {tree.host} --older-than 30"


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def human(n: int | None) -> str:
    """Sizes labelled exactly as the evidence labels them: ``du -sh`` and
    sparkrun's own receipt both divide by 1024³ and print a bare ``GB``, so
    "94.8 GB" here is 94.8 GiB — the same figure, byte for byte, as either
    source.  Do not compare these with a Hub page's size without checking that
    scale first."""
    if n is None:
        return "?"
    for unit, scale in (("TB", 1024**4), ("GB", 1024**3), ("MB", 1024**2), ("KB", 1024)):
        if n >= scale:
            return f"{n / scale:.1f} {unit}"
    return f"{n} B"


def report(trees: list[Tree], keys: dict[str, list[str]], budget_gb: float) -> int:
    now = dt.datetime.now()
    by_host: dict[str, list[Tree]] = {}
    for tree in trees:
        by_host.setdefault(tree.host, []).append(tree)

    print(f"cache-audit — {len(trees)} tree(s) across {len(by_host)} host(s); budget {budget_gb:.0f} GB of cache per node\n")

    print("== per node ==")
    over_budget = 0
    for host in sorted(by_host):
        group = by_host[host]
        total = sum(t.size or 0 for t in group)
        stale = [t for t in group if verdict(t, keys)[0] == "stale"]
        idle = sum(t.size or 0 for t in stale if reclaim_note(t, "stale", now).startswith("sparkrun"))
        over = total > budget_gb * 1024**3
        over_budget += over
        print(
            f"  {host:<16} {human(total):>9} in {len(group):>3} tree(s)   "
            f"stale {len(stale):>3} ({human(idle):>9} reclaimable now)   {'OVER BUDGET' if over else ''}"
        )

    print("\n== trees (verdict is by leaf key, never by name) ==")
    print(f"  {'host':<16} {'size':>9} {'age':>6}  {'verdict':<8} key  ->  owning recipe / why")
    for host in sorted(by_host):
        for tree in sorted(by_host[host], key=lambda t: -(t.size or 0)):
            kind, detail = verdict(tree, keys)
            hours = age_hours(tree.stamp, now)
            note = reclaim_note(tree, kind, now)
            print(
                f"  {host:<16} {human(tree.size):>9} {'-' if hours is None else f'{hours:.0f}h':>6}  "
                f"{kind.upper() if kind == 'stale' else kind:<8} {tree.family}/{tree.leaf}"
            )
            if kind == "live":
                print(f"  {'':<16} {'':>9} {'':>6}          served by {detail}")
            else:
                print(f"  {'':<16} {'':>9} {'':>6}          {detail}")
                if note:
                    print(f"  {'':<16} {'':>9} {'':>6}          -> {note}")

    print("\n== stale keys nothing ships (the policy's reclaim set) ==")
    stale_leaves = sorted({(t.family, t.leaf) for t in trees if verdict(t, keys)[0] == "stale"})
    if not stale_leaves:
        print("  (none)")
    for family, leaf in stale_leaves:
        holding = [t for t in trees if t.leaf == leaf]
        print(
            f"  {family:<6} {leaf:<52} {human(sum(t.size or 0 for t in holding)):>9}  on "
            + ",".join(sorted({t.host for t in holding}))
        )
    print(
        f"\nSTALE = no shipped recipe and no attic arm produces this key.  Measure the marker age "
        f"before\nreclaiming: a tree touched inside {IN_USE_HOURS} h is in use by the hygiene rule."
    )
    return 1 if over_budget else 0


# ---------------------------------------------------------------------------
# Self-check
# ---------------------------------------------------------------------------

#: ``(model, revision, expected leaf)`` read off the fleet on 2026-10-15 from
#: ``sparkrun setup prune-runtime-cache --all --dry-run`` plus an ``ls``/``stat``
#: of the same trees.  If sparkrun changes its key derivation these fail, which
#: is the point.  The last one is the 48-char label-cap case.
KNOWN_KEYS = [
    ("deepseek-ai/DeepSeek-V4.1-Flash", "5254448103b6254fc646dacbca1cbbf20e9216c1",
     "deepseek-ai__DeepSeek-V4.1-Flash-11826f49"),
    ("deepseek-ai/DeepSeek-V4.1-Flash", "", "deepseek-ai__DeepSeek-V4.1-Flash-9a74d993"),
    ("deepseek-ai/DeepSeek-V4.1-Flash", "fb2764a5cf321eaa5070ca8f9e892818f477c16d",
     "deepseek-ai__DeepSeek-V4.1-Flash-db95f94c"),
    ("littlecedar/DeepSeek-V4.1-Flash-EXL3-2.9bpw-with-engram", "",
     "littlecedar__DeepSeek-V4.1-Flash-EXL3-2.9bpw-wit-2bd42ac5"),
    ("Mia-AiLab/DeepSeek-V4.1-Flash-EXL3-2.9bpw", "64ba41b6c916a587db06eae2e19b7845f7be6e6b",
     "Mia-AiLab__DeepSeek-V4.1-Flash-EXL3-2.9bpw-a54d5c5d"),
    ("sakamakismile/Qwen3.8-27B-AEON-ULTIMATE-UNCENSORED-NVFP4", "8d5a3317b4fcb6f278e1cde7fcae5ed88a27443a",
     "sakamakismile__Qwen3.8-27B-AEON-ULTIMATE-UNCENSO-b9f737e7"),
]

#: Keys a shipped recipe must produce, so the tool is reading the recipes it
#: thinks it is.
SHIPPED_KEYS = [k for _, _, k in KNOWN_KEYS if k.endswith(("11826f49", "2bd42ac5", "a54d5c5d"))]


def selftest() -> int:
    import tempfile

    bad: list[str] = []

    def check(condition: bool, message: str) -> None:
        if not condition:
            bad.append(message)

    for model, revision, expect in KNOWN_KEYS:
        check(model_key(model, revision) == expect, f"key({model}@{revision or '(empty)'}) != {expect}")
    # The 48-char cap is load-bearing: without it the AEON arm's key changes,
    # so a reader who "fixes" the truncation mis-attributes every long model id.
    check(
        model_key("sakamakismile/Qwen3.8-27B-AEON-ULTIMATE-UNCENSORED-NVFP4", "x" * 40)
        != model_key("sakamakismile/Qwen3.8-27B-AEON-ULTIMATE-UNCENSORED-NVFP4-y", "x" * 40),
        "the 48-char label cap is not active",
    )

    keys = recipe_keys(REPO_ROOT)
    for key in SHIPPED_KEYS:
        check(bool(keys.get(key)), f"no shipped recipe found for {key}")
    for key in ("deepseek-ai__DeepSeek-V4.1-Flash-9a74d993", "deepseek-ai__DeepSeek-V4.1-Flash-db95f94c"):
        check(not keys.get(key), f"{key} is produced by a recipe and must not classify stale")

    with tempfile.TemporaryDirectory() as tmp:
        rc = "/home/red/.cache/sparkrun/runtime-cache/sglang"
        dry = Path(tmp) / "dry.txt"
        dry.write_text(
            f"  would-remove    45.0 GB  10.0.4.30:{rc}/deepseek-ai__DeepSeek-V4.1-Flash-db95f94c\n"
            "Would remove 1 tree(s), 45.0 GB.\n",
            encoding="utf-8",
        )
        listing = Path(tmp) / "ls.txt"
        listing.write_text(
            "##### 10.0.4.30\n"
            f"49501500K\t2026-10-10_13:59\t{rc}/deepseek-ai__DeepSeek-V4.1-Flash-db95f94c\n"
            f"49980704K\t2026-10-13_11:13\t{rc}/deepseek-ai__DeepSeek-V4.1-Flash-9a74d993\n",
            encoding="utf-8",
        )
        parsed = parse_census([dry, listing])
        trees = {t.leaf: t for t in parsed}
        check(len(parsed) == 2, f"parse_census found {len(parsed)} rows, expected 2")
        merged = trees.get("deepseek-ai__DeepSeek-V4.1-Flash-db95f94c")
        # The coarse dry-run row must be merged with, not preferred over, the
        # fine listing: its 0.1-GB rounding under-reports and it carries no marker.
        check(merged is not None and merged.host == "10.0.4.30", "the dry-run line lost its host")
        check(merged is not None and merged.size == 49501500 * 1024, "the larger (KiB) size must win the merge")
        check(merged is not None and merged.stamp == "2026-10-10_13:59", "a missing marker stamp must be filled from the listing")
        listed = trees.get("deepseek-ai__DeepSeek-V4.1-Flash-9a74d993")
        check(
            listed is not None and listed.host == "10.0.4.30" and listed.size == 49980704 * 1024,
            "a `##### host` header did not attribute its hostless listing line",
        )
        check(verdict(merged, keys)[0] == "stale", "db95f94c must classify stale")
        check(
            verdict(Tree("h", f"{rc}/deepseek-ai__DeepSeek-V4.1-Flash-11826f49"), keys)[0] == "live",
            "11826f49 must classify live",
        )
        check(verdict(Tree("h", rc), keys)[0] == "unkeyed", "a family root must classify unkeyed")
        now = dt.datetime(2026, 10, 15, 10, 0)
        check(
            merged is not None and reclaim_note(merged, "stale", now).startswith("sparkrun setup prune-runtime-cache --hosts 10.0.4.30"),
            "a 116h-old stale tree must get the sweep command",
        )
        check(
            listed is not None and reclaim_note(listed, "stale", now).startswith("touched 47 h"),
            "the 72h in-use guard did not fire on a 47h-old tree",
        )
        check(
            reclaim_note(Tree("h", f"{rc}/deepseek-ai__DeepSeek-V4.1-Flash-db95f94c"), "stale", now).startswith(
                f"no {LAST_USED_MARKER} marker"
            ),
            "an unmarked tree must not get the sweep command",
        )

    print("selftest: " + ("OK" if not bad else f"{len(bad)} FAILURE(S)"))
    for message in bad:
        print("  FAIL " + message)
    return 1 if bad else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--census", action="append", type=Path, default=[], help="census receipt; repeatable")
    parser.add_argument("--budget-gb", type=float, default=2000.0, help="per-node runtime-cache budget (default 2000)")
    parser.add_argument("--selftest", action="store_true", help="offline self-check; no census needed")
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()
    if not args.census:
        parser.error("give at least one --census file, or --selftest")

    trees = parse_census(args.census)
    if not trees:
        print("no `<host>:/path` lines found in " + ", ".join(str(p) for p in args.census), file=sys.stderr)
        return 2
    return report(trees, recipe_keys(REPO_ROOT), args.budget_gb)


if __name__ == "__main__":
    raise SystemExit(main())