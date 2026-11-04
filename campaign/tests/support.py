"""Fixture builders shared by the campaign tests.

Everything here writes into a temporary directory, so a test can build the exact receipt shape it
is about: a full ladder, a partial one, a marker with the wrong field, a serve log that a reaper
should have preserved. No fixture touches the fleet.
"""

from __future__ import annotations

import json
from pathlib import Path


def write(path: str | Path, text: str) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def recipe(root: str | Path, lane: str, arm: str, marker: str | None = None) -> Path:
    """A minimal recipe file; `marker` lands inside `metadata:` as the skip source expects."""
    lines = ["container: example/image:tag", "metadata:", "  description: fixture arm"]
    if marker is not None:
        lines.append(f'  measured_rejected: "{marker}"')
    return write(Path(root) / "recipes" / lane / f"{arm}.yaml", "\n".join(lines) + "\n")


def lane_doc(root: str | Path) -> Path:
    return write(Path(root) / "docs" / "lane.md", "line one\nline two\nline three\n")


def manifest(path: str | Path, arms: list[tuple[str, str, int]]) -> Path:
    rows = [{"arm": arm, "path": recipe, "tp": tp} for arm, recipe, tp in arms]
    return write(path, json.dumps(rows, indent=1) + "\n")


def receipt(
    root: str | Path,
    arm: str,
    *,
    cells: int = 2,
    ladder: str = "ok",
    accuracy: str = "",
    serve_logs: int = 0,
    watchdog: str = "",
    window: str = "tp12-20260101",
) -> Path:
    """One arm's receipt directory, shaped like `tools/run-arm.sh` writes it.

    `cells=0` builds the partial ladder that a died-mid-run benchmark leaves behind: it parses, the
    marker even says `ok`, and there is no cell in it.
    """
    arm_dir = Path(root) / window / arm
    arm_dir.mkdir(parents=True, exist_ok=True)
    table = {"benchmarks": [{"concurrency": index + 1} for index in range(cells)]}
    write(arm_dir / "ladder.json", json.dumps(table) + "\n")
    marker = ["suite: concurrency-ladder"]
    if ladder:
        marker.append(f"ladder: {ladder}")
    if accuracy:
        marker.append(f"accuracy_status: {accuracy}")
    write(arm_dir / "house.yaml", "\n".join(marker) + "\n")
    for index in range(serve_logs):
        write(arm_dir / f"serve-node_{index}.log", "engine log line\n")
    if watchdog:
        write(arm_dir / "watchdog.log", watchdog)
    return arm_dir