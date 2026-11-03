# Python runtime overhead — does a newer interpreter move a serving cell?

Answer for queue row `py314-executor-overhead` (owner request 2026-10-30), Leg A: **no, and the
ceiling is three orders of magnitude below the noise floor of a decode cell.** Leg B — source-building
sglang/vllm against cp314 — is retired on this arithmetic, not deferred.

Measured 2026-11-03 on the workstation (`x86_64`, CPython 3.12.14 / 3.14.6 / 3.14.9 free-threaded,
`gil_enabled: false` on the last) with the repo's own instrument, `tools/py-runtime-bench.py`,
`--repeat 5` keeping the best run per case. Each case is the Python-side work a token or a request
actually passes through; the whole point is that the interpreter can only be charged for these.

| case | 3.12 (ns) | 3.14 (ns) | 3.14t (ns) | 3.14 / 3.12 | 3.14t / 3.12 |
|---|---|---|---|---|---|
| `loop` — tight arithmetic | 79 | 48 | 49 | **0.612x** | 0.626x |
| `json` — streaming delta `json.dumps` | 3 421 | 3 513 | 3 638 | 1.027x | 1.063x |
| `detok` — detokenizer step | 108 | 114 | 110 | 1.058x | 1.021x |
| `pydetok` — pure-Python detokenize | 1 674 | 1 522 | 1 681 | 0.909x | 1.004x |
| `httparse` — request-body parse | 3 445 | 3 136 | 3 284 | 0.910x | 0.953x |
| `asyncio` — scheduler turn | 237 779 | 206 860 | 249 711 | 0.870x | 1.050x |

## What the table says

The specializing interpreter is real and it shows exactly where the release notes put it: a tight
arithmetic loop drops **39 %** (79 → 48 ns). Nothing else follows it. The two cases that dominate a
real token — the streaming JSON encode and the detokenizer step — **get slower** on 3.14 (1.027x and
1.058x), and the free-threaded build is slower still on `json` (1.063x) with a compiled-extension
detokenizer that does not care (1.021x). A per-token Python cost of `json` + `pydetok` moves from
**5.10 us to 5.03 us** — a 1.4 % reduction, on the interpreter change that reports a 39 % loop win.

## The ceiling

Python-side 5.1 us per token against a decode step:

| arm | step time | Python share of step |
|---|---|---|
| abliterated TP=2, 10.6 t/s per stream | 94 ms | 0.0054 % |
| same arm, 13.7 t/s per stream | 73 ms | 0.0070 % |
| ds4 TP=4 production, 67 t/s aggregate | 15 ms | 0.034 % |

At the fastest rung in the fleet the interpreter is 3.4 parts in 10 000 of a step, and the 1.4 %
improvement available to it is **0.013 %** of that step. A cell cannot resolve it: the ladder's own
run-to-run spread is percent-scale. At high concurrency the per-request scheduler turn falls 238 → 207 us
(31 us saved per entry), which at 100 entries/s is 3 ms of one core per second — 0.3 % of a core, again
under the GPU.

## Verdict

* **Leg A closes the serving question: no.** Keep 3.12/3.13 with the wheels the engines publish. A
  cp314 interpreter buys nothing a serving cell can see and costs an unbuilt engine plus an unbuilt
  flashinfer.
* **Leg B is retired, not deferred.** It was priced as "source-build sglang or vllm under cp312 and
  cp314 in one CUDA base" — days of work whose best case is bounded above by 0.013 % of a decode step.
  The gate that would reopen it is not a release note but a measurement: a cell where Python-side time
  is a visible fraction of wall time, e.g. a CPU-only serve (`recipes/decision/` `kev`/`laya`) under
  c50+, where the interpreter competes with matmul rather than a GPU.
* **Free-threaded is not a fleet option yet.** 3.14t lands at 0.63x on `loop`, 1.05x on `asyncio` and
  1.06x on `json` versus 3.12, and the serving engines publish no cp314t wheels at all — a
  thread-safety gain with no threads to gain it from.

## Provenance

* Instrument: `tools/py-runtime-bench.py` (its own case set; guarded by
  `tests/test_py_runtime_bench.py`), run as
  `python3.NN tools/py-runtime-bench.py --repeat 5 --json .scratch/py314/python3.NN.json`.
* Interpreter survey (2026-10-30, PyPI): torch 2.15.0 ships 8 cp314 wheels, triton 3.9.0 cp314 and
  cp314t, tokenizers 0.23.3 seven, uvloop 0.23.0 twelve — while **sglang 0.5.23 publishes 0 cp314
  (2 cp312)**, vllm 0.32.0 publishes no cp31x wheels at all, and `flashinfer-python` / `sgl-kernel`
  publish none — so Leg B needed source builds of the engine **and** flashinfer.
* Local interpreters: `/usr/bin/python3.12` (3.12.14), uv-managed 3.14.6, uv-managed 3.14.9
  free-threaded (`~/.local/bin/python3.14t`).