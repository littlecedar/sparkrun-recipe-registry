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


def sidecar_receipt(
    root: str | Path,
    arm: str,
    *,
    cells: int = 2,
    score: str | None = "93",
    window: str = "tp12-20260101",
    client: dict | None = None,
) -> Path:
    """An arm directory shaped like sparkrun's own benchmark, not run-arm's marker.

    `house.yaml` is the nested `sparkrun_benchmark` sidecar (the shape the sglang branch and the
    TensorFold arms both wrote on 2026-11-08): outcome under `benchmark`/`results`, no flat
    ladder field. `score=None` drops the results block, the control for "a sidecar alone is not
    a measurement".
    """
    arm_dir = receipt(root, arm, cells=cells, ladder="", window=window)
    lines = [
        "sparkrun_benchmark:",
        "  version: '1'",
        "  benchmark:",
        "    framework: tool-eval-bench",
        "    profile: benchmarking/standard-suite.yaml",
    ]
    if score is None:
        lines += ["  results:", "    json: {}"]
    else:
        lines += ["  results:", "    json:", f"      final_score: {score}"]
    write(arm_dir / "house.yaml", "\n".join(lines) + "\n")
    if client is not None:
        write(
            arm_dir / "client" / "client.json",
            json.dumps({
                "tool": "h2h-client",
                "cell": client.get("cell", "house4096"),
                "image_id": client.get("image_id", "sha256:abc"),
                "rc": client.get("rc", 0),
            }) + "\n",
        )
    return arm_dir


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


def metrics(
    arm_dir: str | Path,
    *,
    hosts: dict[str, tuple[str, str]] | None = None,
    status_text: str | None = None,
) -> None:
    """The metrics scrape `run-arm.sh` writes: `metrics-status.txt` plus one artifact per host.

    `hosts` maps host -> (status, raw body): the same verdict line goes into both files, so a
    captured verdict with an empty body builds the disagreement the reader must catch.
    `status_text` writes `metrics-status.txt` verbatim instead, for an artifact with no per-host
    witness (or a reason the fixture line cannot produce).
    """
    if status_text is not None:
        write(Path(arm_dir) / "metrics-status.txt", status_text)
        return
    lines = ["# runtime=vllm port=8000"]
    for host, (status, body) in (hosts or {}).items():
        line = (f"{status} host={host} container=- "
                f"url=http://127.0.0.1:8000/metrics reason=fixture")
        lines.append(line)
        write(Path(arm_dir) / f"metrics-{host}.txt", line + "\n" + body)
    write(Path(arm_dir) / "metrics-status.txt", "\n".join(lines) + "\n")