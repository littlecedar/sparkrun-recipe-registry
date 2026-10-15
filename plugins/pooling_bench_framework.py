"""``BenchmarkingPlugin`` for vLLM **pooling** engines — embed and rerank.

A pooling engine has no ``/chat/completions``, so neither shipped framework can
measure one: pointed at an embed server, ``llama-benchy`` 0.4.0 dies in its
warmup (``Warmup failed: HTTP 404``, exit 1) and sparkrun reports the run as
``Benchmark incomplete`` — the standard profiles cannot produce a pooling
number at all, in either direction.  Pooling is also not a chat shape wearing a
different unit: the unit is a *document* (texts embedded, or query-document
pairs scored) and the request contract differs per mode — a plain
``/v1/embeddings`` body takes the **un-instructed** prompt path, while the chat
form and ``/v2/embed`` apply the checkpoint's own instruction
(``recipes/embed/README.md`` §Serving the encoder correctly).

Nothing is measured here.  ``tools/pooling-bench.py`` is the instrument: it owns
the request shapes, the correctness checks a 200 OK cannot satisfy, and the
receipts the embed/rerank lanes publish.  This module is the adapter that lets a
*profile* ask sparkrun to run it, so a pooling sweep gets what every other lane
gets from a framework — resumable per-cell artifacts, gap detection on a cell
that measured nothing, an exported ``--output`` measurement, and one place the
two lanes' ladders are described::

    framework: pooling-bench
    args:
      kind: embed                 # required: embed | rerank (different routes)
      mode: embed-v1-chat         # instructed form; embed-v1-raw is the A/B
      concurrency: [1, 2, 5, 10]  # one task (and one artifact) per value
      requests: 100
      input_tokens: 256

Loading — sparkrun's *plugin* discovery is config-driven and separate from the
recipe/benchmark registry, so a cloned registry cannot ship this on its own
(the loader imports every module in the configured directory, hence a directory
that holds only plugins)::

    sparkrun setup features enable core.external_plugins
    # config.yaml
    plugins.paths:
      - <path to this clone>/plugins

``plugins.paths`` directories are imported into the ``sparkrun benchmark``
process only (the head that drives the sweep), never onto the serving nodes.
"""

from __future__ import annotations

import json
import sys
from itertools import product
from pathlib import Path
from typing import Any

from sparkrun.benchmarking.base import (
    BenchmarkingPlugin,
    ProgressColumn,
    ProgressTableSpec,
)
from sparkrun.benchmarking.scheduler import BenchTask
from sparkrun.core.benchmark_profiles import BenchmarkError

#: Every sparkrun plugin module declares this; the loader refuses a module
#: without it (``core/registration.py``: "missing API declaration").
SPARKRUN_PLUGIN_API_VERSION = 1

#: The instrument, resolved from this file's sibling ``tools/`` directory.  The
#: plugin is a thin adapter, so shipping one without the other is a
#: misconfigured ``plugins.paths`` — not a supported state, and
#: ``check_prerequisites`` says so by name before anything is launched.
INSTRUMENT = Path(__file__).resolve().parent.parent / "tools" / "pooling-bench.py"

KINDS = ("embed", "rerank")

#: Args this plugin consumes itself.  Everything else is rendered as an
#: instrument flag, so a *new* pooling-bench option needs no edit here and a
#: misspelt one fails in the tool's own argparse (which exits non-zero).
#: ``json_out`` is here because the scheduler owns the result file: a
#: user-supplied path would be written by the tool and then ignored.
_HANDLED = frozenset({"kind", "base_url", "model", "json_out"})

_COLUMNS = ("kind", "conc", "ok/total", "units/s", "p50 ms")


def _runs_of(payload: Any) -> list[dict[str, Any]]:
    """Per-run payloads from *payload*, whether it is one task's artifact or the
    consolidated dict the final parse sees (``{"runs": [...]}``).

    The scheduler measures "did this measure anything" on the *consolidated*
    result, so a reader that only understood a single task's payload would
    report every real sweep as "measured nothing".
    """
    if not isinstance(payload, dict):
        return []
    runs = payload.get("runs")
    if isinstance(runs, list):
        return [run for run in runs if isinstance(run, dict)]
    return [payload]


def _rows_from_consolidated(consolidated: dict[str, Any]) -> list[tuple[Any, ...]]:
    """One progress row per task artifact: cell, successes, and units/second.

    ``units/s`` is recomputed from the tool's own ``units`` and ``wall_seconds``
    (the same ratio the lane receipts quote) rather than read from a field, so a
    run whose wall clock covers retries cannot be quoted as faster than it was.
    """
    rows: list[tuple[Any, ...]] = []
    for run in consolidated.get("runs") or []:
        if not isinstance(run, dict):
            continue
        config = run.get("config") or {}
        result = run.get("result") or {}
        units = result.get("units")
        wall = result.get("wall_seconds")
        rate = units / wall if isinstance(units, (int, float)) and isinstance(wall, (int, float)) and wall > 0 else None
        rows.append(
            (
                config.get("kind"),
                config.get("concurrency"),
                f"{result.get('requests_ok', '?')}/{result.get('requests_total', '?')}",
                rate,
                (result.get("latency_ms") or {}).get("p50"),
            )
        )
    return rows


def _format_cell(value: Any, column: ProgressColumn) -> str:
    if column.name == "units/s":
        return "…" if value is None else f"{value:.1f}"
    if column.name == "p50 ms":
        return "…" if value is None else f"{value:.0f}"
    return str(value)


class PoolingBenchFramework(BenchmarkingPlugin):
    """Drives ``tools/pooling-bench.py`` — the pooling lanes' measurement instrument."""

    framework_name = "pooling-bench"
    categories = ("pooling",)
    # ``resolve_request_model``'s default is the *served* name, which is what
    # this instrument sends; the weights identity is irrelevant to it (unlike
    # llama-benchy, which tokenizes locally). See base.resolve_request_model.
    model_argument_is_model_id = False
    default_args: dict[str, Any] = {
        "concurrency": [1],
        "requests": 50,
        "input_tokens": 128,
    }
    passthrough_args: set[str] = set()

    def check_prerequisites(self) -> list[str]:
        if INSTRUMENT.is_file():
            return []
        return [f"{INSTRUMENT} is missing — plugins.paths must point at this clone's plugins/ directory"]

    # --- Task list ---------------------------------------------------------

    def build_task_list(
        self,
        base_args: dict[str, Any],
        schedule: list[dict[str, Any]] | None,
    ) -> list[BenchTask]:
        """One task per cell: the cartesian product of the list-valued args.

        ``concurrency`` is the ladder axis, and expanding *every* list-valued
        arg (sorted for a stable index order) is what makes a shape sweep
        expressible without a second code path.  A ``schedule:`` entry is one
        task: ``concurrency`` must be an int there, and no other arg may carry
        more than one value — the alternative is a schedule that silently
        expands into tasks the author did not write.
        """
        args = dict(base_args or {})
        kind = args.get("kind")
        if kind not in KINDS:
            raise BenchmarkError(
                f"pooling-bench requires 'kind: {' | '.join(KINDS)}' in the profile/recipe args (-b kind=...): "
                "embed answers on /v1/embeddings and rerank on /v1/score, so neither is a safe default"
            )

        if schedule is not None:
            tasks: list[BenchTask] = []
            for idx, entry in enumerate(schedule):
                concurrency = entry.get("concurrency")
                if not isinstance(concurrency, int):
                    raise BenchmarkError(f"schedule entry {idx} missing/invalid 'concurrency' (must be int)")
                run_args = {**args, **entry, "concurrency": [concurrency]}
                multi = [key for key, value in run_args.items() if isinstance(value, list) and len(value) > 1]
                if multi:
                    raise BenchmarkError(
                        f"schedule entry {idx} carries multi-valued args {', '.join(sorted(multi))}; "
                        "a schedule entry is one task (a schedule that expands is a schedule nobody wrote)"
                    )
                tasks.append(
                    BenchTask(
                        index=idx,
                        label=f"c={concurrency}",
                        run_args=run_args,
                        schedule_entry=dict(entry),
                    )
                )
            return tasks

        names = sorted(key for key, value in args.items() if isinstance(value, list))
        tasks = []
        for idx, combo in enumerate(product(*(args[name] for name in names))):
            run_args = dict(args)
            for name, value in zip(names, combo):
                run_args[name] = [value]
            tasks.append(
                BenchTask(
                    index=idx,
                    label=" ".join(f"{name}={value}" for name, value in zip(names, combo)) or "single",
                    run_args=run_args,
                    schedule_entry=dict(zip(names, combo)),
                )
            )
        return tasks

    # --- Command construction ---------------------------------------------

    def build_benchmark_command(
        self,
        target_url: str,
        model: str,
        args: dict[str, Any],
        result_file: str | None = None,
    ) -> list[str]:
        """Render ``python3 tools/pooling-bench.py <kind> --base-url ... --json-out ...``.

        ``target_url`` arrives with sparkrun's ``/v1`` suffix
        (``api/_benchmark.py`` builds ``http://host:port/v1``); the instrument
        strips it, because ``/v2/embed`` does not live under ``/v1``.
        """
        cmd = [sys.executable, str(INSTRUMENT), str(args.get("kind")), "--base-url", target_url, "--model", model]
        if result_file:
            cmd.extend(["--json-out", result_file])
        for key, value in args.items():
            if key in _HANDLED:
                continue
            flag = "--" + key.replace("_", "-")
            if isinstance(value, bool):
                if value:
                    cmd.append(flag)
                continue
            if isinstance(value, list):
                if len(value) != 1:
                    raise BenchmarkError(f"pooling-bench task args must be single-valued after expansion, got {key}={value!r}")
                value = value[0]
            cmd.extend([flag, str(value)])
        return cmd

    def estimate_test_count(self, args: dict[str, Any]) -> int | None:
        """One task per expanded cell (``build_task_list`` is the definition)."""
        try:
            return len(self.build_task_list(args, None))
        except BenchmarkError:
            return None

    # --- Results -----------------------------------------------------------

    def parse_results(self, stdout: str, stderr: str, result_file: str | None = None) -> dict[str, Any]:
        """Read the instrument's ``--json-out`` payload (``{}`` when absent)."""
        data: dict[str, Any] = {}
        if result_file:
            try:
                parsed = json.loads(Path(result_file).read_text())
            except (OSError, ValueError):
                parsed = None
            if isinstance(parsed, dict):
                data = parsed
        return {"json": data, "stdout": stdout}

    def measured_nothing(self, parsed: dict[str, Any]) -> bool:
        """True when no run recorded a single successful request.

        The unreachable-target shape is already loud — the tool exits non-zero,
        so the scheduler fails the task — but a framework whose results can be
        "every request null" must not rely on the exit code alone (see
        ``base.BenchmarkingPlugin.measured_nothing``).  This is also the check
        the final export is gated on, so it reads the consolidated payload, not
        just one task's.
        """
        payload = (parsed or {}).get("json")
        return not any(isinstance(run.get("result"), dict) and run["result"].get("requests_ok") for run in _runs_of(payload))

    # --- Scheduler / aggregator / progress-UI integration ------------------

    def result_filename_suffix(self, task: BenchTask) -> str:
        """``_embed_c8``: an artifact names its own kind *and* cell.

        Kind is in the name as well as the concurrency, because two pooling
        lanes can share a benchmark directory and a reader must not have to
        infer the route from the number.
        """
        run_args = task.run_args
        kind = run_args.get("kind")
        concurrency = run_args.get("concurrency") or []
        if not kind or not isinstance(concurrency, list) or not concurrency:
            return ""
        return f"_{kind}_c{concurrency[0]}"

    def task_coverage_key(self, task: BenchTask) -> tuple[Any, Any]:
        """``(kind, concurrency)`` for gap detection."""
        run_args = task.run_args
        concurrency = run_args.get("concurrency") or []
        return (run_args.get("kind"), concurrency[0] if isinstance(concurrency, list) and concurrency else None)

    def consolidated_coverage_keys(self, consolidated: dict[str, Any]) -> set[tuple[Any, Any]]:
        """``(kind, concurrency)`` pairs a result artifact actually measured."""
        keys: set[tuple[Any, Any]] = set()
        for run in consolidated.get("runs") or []:
            if not isinstance(run, dict):
                continue
            config = run.get("config") or {}
            kind, concurrency = config.get("kind"), config.get("concurrency")
            if kind is not None and concurrency is not None:
                keys.add((kind, concurrency))
        return keys

    def progress_table_spec(self) -> ProgressTableSpec:
        return ProgressTableSpec(
            columns=[ProgressColumn(name=name, justify="right") for name in _COLUMNS],
            rows_from_consolidated=_rows_from_consolidated,
            row_key=lambda row: (row[0], row[1]),
            format_cell=_format_cell,
        )