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

The task set is fixed, in two tiers. The **easy** floor exercises the loop; the **hard** ceiling is
where engines separate, because each task has several ways to be partially right.

Easy tier (`--tier easy`, 8 tasks, 16 turns / 600 s each):

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

Hard tier (`--tier hard`, 5 tasks, 24 turns / 900 s each):

| task | shape | checker |
|:--|:--|:--|
| `multi-file-refactor` | one money/date helper extracted from three modules into a new fourth; `cli.py` output unchanged | visible suite + golden render output + AST structure: helper defined once in `textfmt.py`, no `_money`/`_day` left, all three modules import it, import graph acyclic |
| `shell-repro-rounding` | bill split loses cents; the visible test passes, only `python -B repro.py` shows it | visible suite + the repro script + a 3,591-case sweep: exact sum, spread ≤ 1 cent, deterministic, ints |
| `normalize-edge-table` | canonicalise account keys against a written spec | visible suite + 8 valid and 11 invalid inputs (unicode dashes, padding, separators, signed, non-ASCII) |
| `stub-service-client` | wire `collect()` to a local line service | end-to-end: harness starts its own socket server with different keys, asserts the parsed dict, then malformed and non-integer payloads must raise `ValueError` |
| `golden-regression` | add an optional PRIORITY column | three tracked golden outputs byte-identical + two exact expected tables (present and mixed rows) |

Grading is offline and deterministic: `unittest`, exact JSON/string comparison, AST checks, sockets on
loopback and subprocess exit codes. No judge model, no timing threshold, no network beyond the model
endpoint.

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
- `--tier easy|hard|all` selects the set (default `all`); the tier is written into every task
  receipt and into `summary.json`.
- `--tasks fix-failing-test,spec-to-function` takes a subset; `--list` prints the set and its tier.
- Budgets are per task — easy 16 turns / 600 s, hard 24 turns / 900 s — and `--max-turns` /
  `--wall-clock` override them for a whole run.
- `--resume` skips tasks that already hold a result, so a window can be re-entered.
- A run stops after **two consecutive** tasks error or time out — the serve is never touched, and
  the remaining tasks are reported as not run, so a dead endpoint costs two requests, not eight.
- `--fixture-root` defaults to `.scratch/agentic/` (git-ignored); each task's workspace is re-seeded
  on every non-resumed run, so a receipt can be reproduced.
- `--selftest` proves every task is red on its untouched fixture and green under the task's
  reference patch, plus a scripted mock proving the loop passes a solved task and fails an
  unsolved one — offline. A red cell is then the model's, not the harness's.

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

## 6. Reference run

2026-11-18, knapcio SGLang production serve (`deepseek-v4.1-flash-knapcio-tp4-1m-sglang`, task
`b020d2dd178343a5_9cdb266b5e0d`, keyless endpoint on rank 0), `--tier all`, single-flight, greedy:

| tier | task | verdict | wall | turns | tool calls | tokens |
|:--|:--|:--|--:|--:|--:|--:|
| easy | `fix-failing-test` | pass | 7.5 s | 7 | 8 | 9,287 |
| easy | `two-file-bug-hunt` | pass | 6.3 s | 6 | 7 | 7,034 |
| easy | `spec-to-function` | pass | 11.5 s | 5 | 5 | 6,723 |
| easy | `refactor-preserve-behavior` | pass | 4.4 s | 4 | 4 | 4,032 |
| easy | `config-migration` | pass | 4.4 s | 4 | 4 | 4,121 |
| easy | `csv-to-json-cli` | pass | 7.9 s | 5 | 5 | 6,018 |
| easy | `mutable-default-bug` | pass | 6.0 s | 5 | 8 | 6,021 |
| easy | `validation-boundary` | pass | 5.1 s | 4 | 3 | 3,899 |
| hard | `multi-file-refactor` | pass | 11.4 s | 6 | 13 | 11,542 |
| hard | `shell-repro-rounding` | pass | 12.3 s | 6 | 8 | 9,178 |
| hard | `normalize-edge-table` | pass | 7.4 s | 4 | 3 | 4,410 |
| hard | `stub-service-client` | pass | 78.9 s | 9 | 9 | 16,962 |
| hard | `golden-regression` | pass | 8.6 s | 6 | 6 | 7,323 |

**13/13 pass, median 7.5 s, worst 78.9 s, total 171.7 s** (2 m 54 s wall including fixtures and
grading). Receipt `head:~/benchmarks/agentic-battery-20261118/knapcio-v2/`; the earlier eight-task
run and its two-task timing gate stay in the parent directory. The stub task's 78.9 s is model
behaviour — it held the stub in a foreground shell call until the 60 s tool timeout, then retried —
not a harness stall; the wire receipt is the witness. This is reference v2: a picom run on the same
harness compares cell by cell, and under three minutes buys repeats in a window.

The floor and ceiling differ in kind: easy cells finish in 4–12 s with 3–8 calls, hard cells in
7–79 s with 3–13 calls, and the hard checkers fail a patch that passes the visible suite
(`shell-repro-rounding` and `multi-file-refactor` are the two with the largest hidden surface).
