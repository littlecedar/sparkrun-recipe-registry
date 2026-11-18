# Agentic coding battery: does the serve finish real code work, and how fast

The lane's engine comparison ([`PICOM-VS-KNAPCIO.md`](PICOM-VS-KNAPCIO.md)) measures decode cost;
this battery measures the workload the lane actually exists for — an agent reading a small
repository, patching it, running its tests and verifying. Eight tasks, one base URL, deterministic
grading. Every number below names its receipt; nothing here is a leaderboard row.

## 1. What it measures

Per task, from `tools/agentic-battery.py`:

| field | meaning |
|:--|:--|
| `pass` | every hidden check exited 0 after the loop ended; the model never sees them |
| `wall_s` | request-to-last-turn wall clock, including tool execution |
| `tokens` | `prompt` + `completion` summed from each response's `usage` |
| `turns` / `tool_calls` | model turns and executed tool calls; `invalid_args` counts unparsable arguments |
| `truncated` | turns with `finish_reason: length` — a harness cap, not a model failure |

The task set is fixed and small enough to fit one context:

| task | shape | checker |
|:--|:--|:--|
| `fix-failing-test` | failing suite, two bugs in one module | visible suite + hidden cases |
| `two-file-bug-hunt` | type coercion in one module breaks its caller | visible suite + round-trip script |
| `spec-to-function` | implement `parse_duration` from `SPEC.md` | visible suite + 13-case table incl. errors |
| `refactor-preserve-behavior` | remove duplicated formatting | byte-identical output + `format_row` call count via monkeypatch |
| `config-migration` | INI → JSON, callers unchanged | visible suite + migration script (JSON shape, INI gone, `load()` default) |
| `csv-to-json-cli` | finish an argparse CLI | subprocess run on a fresh CSV, exact JSON |
| `mutable-default-bug` | shared default list leaks between batches | visible suite + isolation script |
| `validation-boundary` | `withdraw` must refuse bad amounts without side effects | visible suite + balance-unchanged script |

Grading is offline and deterministic: `unittest`, exact JSON/string comparison, and subprocess exit
codes. No judge model, no timing threshold, no network beyond the model endpoint.

## 2. How to run it against any arm

One base URL, one served model name, an optional key — nothing engine-specific:

```sh
python3 tools/agentic-battery.py \
    --base-url http://rank0-host:8000 \
    --model deepseek-ai/DeepSeek-V4.1-Flash-1017 \
    --outdir ~/benchmarks/agentic-battery-$(date +%Y%m%d)
```

- `--api-key-env VAR` names the variable holding the bearer key; unset sends no `Authorization`
  header (the knapcio serve is keyless). Never pass a key on the command line.
- `--tasks fix-failing-test,spec-to-function` takes a subset; `--list` prints the set.
- `--max-turns` (16) and `--wall-clock` (600 s per task) bound each task.
- `--resume` skips tasks that already hold a result, so a window can be re-entered.
- A run stops after **two consecutive** tasks error or time out — the serve is never touched, and
  the remaining tasks are reported as not run, so a dead endpoint costs two requests, not eight.
- `--fixture-root` defaults to `.scratch/agentic/` (git-ignored); each task's workspace is re-seeded
  on every non-resumed run, so a receipt can be reproduced.
- `--selftest` runs the whole loop against a local mock endpoint and proves a solved task passes and
  an unsolved one fails — offline.

Requests are **non-streaming**. That is deliberate: picom assembles its streamed argument deltas and
SGLang returns complete `tool_calls`, and with `stream: false` both answer with whole
`message.tool_calls`, so the parser difference cannot dominate the result. The three tools are
`read_file`, `write_file` and `run_shell`, all sandboxed to the task workspace.

## 3. How to read a receipt

`<outdir>/summary.json` carries the run's provenance (`base_url`, `model`, `when`), `passed/tasks`,
`wall_median_s`, `wall_worst_s` and the per-task results. `<task>.json` is that task's verdict and
counters; `<task>.wire.jsonl` holds every request and response, so a failed task can be replayed
without re-running the serve. `<fixture-root>/<task>/workspace` is the finished tree.

Read wall seconds for sizing a window, not as a leaderboard: one task on a cold cache and the same
task after a warm prefix differ. `pass` and `tool_calls` are the comparison's claim; `wall_s` is how
long it took to get there.

## 4. Known biases

- **Three minimal tools.** Shell-only models are not penalised for lacking a structured editor, but a
  serve that formats large `write_file` arguments badly pays for it — the schema is small on purpose.
- **English prompts, small tasks.** Each task fits one context with room for several turns; nothing
  here measures long-horizon planning, multi-file repos, or 100k-token codebases.
- **Greedy and non-streaming.** `temperature: 0` removes sampling variance, and non-streaming hides
  any streaming tool-argument defect. A streaming-only bug is this instrument's blind spot, not a
  pass.
- **Hidden checks are narrower than review.** A patch that satisfies the checks can still be poor
  style; the checker answers "finishes correctly", never "writes good code".
- **One served model at a time, sequential.** No concurrency cell, so a serve's batch behaviour is
  invisible here; that is what the ladder profiles measure.

## 5. What it does not measure

Long-context agent work, multi-repo edits, vision, retrieval, or tool-call schema negotiation. It also
says nothing about two engines' client-surface differences `PICOM-VS-KNAPCIO.md` §2 records (token-id
echo, thinking channel, prefix-cache accounting) — the battery sends the same minimal request to both.

## 6. First receipt

2026-11-18, knapcio SGLang production serve (`deepseek-v4.1-flash-knapcio-tp4-1m-sglang`, task
`b020d2dd178343a5_9cdb266b5e0d`, keyless endpoint on rank 0), full eight-task set, single-flight,
`--max-turns 16`, `--wall-clock 600`, greedy:

| task | verdict | wall | turns | tool calls | tokens |
|:--|:--|--:|--:|--:|--:|
| `fix-failing-test` | pass | 5.6 s | 5 | 6 | 5,737 |
| `two-file-bug-hunt` | pass | 6.6 s | 5 | 7 | 6,316 |
| `spec-to-function` | pass | 12.6 s | 6 | 6 | 7,949 |
| `refactor-preserve-behavior` | pass | 4.3 s | 4 | 4 | 4,032 |
| `config-migration` | pass | 4.2 s | 4 | 4 | 4,086 |
| `csv-to-json-cli` | pass | 7.3 s | 5 | 5 | 5,861 |
| `mutable-default-bug` | pass | 8.2 s | 7 | 9 | 9,415 |
| `validation-boundary` | pass | 4.8 s | 4 | 3 | 3,876 |

**8/8 pass, median 6.6 s, worst 12.6 s, total 53.6 s.** Receipt
`head:~/benchmarks/agentic-battery-20261118/knapcio/` (`summary.json` names the endpoint the run
saw). A two-task timing gate (`fix-failing-test` 7.4 s, `two-file-bug-hunt` 6.8 s) ran first in the
parent directory and is kept beside it. This is the production reference row: a picom run on the same
harness compares against it cell by cell, and the ~54 s total means a window can afford repeats.
