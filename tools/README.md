# tools/

Stopgap measurement tooling for `sparkrun` recipes that the built-in benchmarking path
cannot reach.

## pooling-bench.py

`sparkrun`'s benchmarking frameworks (`benchmarking/*.yaml`, `framework: llama-benchy` and
`tool-eval-bench`) both drive `/chat/completions`. **Neither can measure an embedding or
reranker server** — there is no chat endpoint on a pooling engine — and the miss is a
*silent skip*, not an error, so a run can look clean and have measured nothing. Until
someone writes a real pooling `BenchmarkingPlugin` (the interface is
`sparkrun/benchmarking/base.py`; a plugin, not a script, is the correct long-term home),
this is what measures `/v1/embeddings`, `/v2/embed`, and `/v1/score`.

Single file, stdlib only, Python 3.12+. Nothing here knows about hostnames or cluster
nodes — everything is a flag.

```sh
# Encoder: the INSTRUCTED chat form (see the note below before choosing a mode)
python3 tools/pooling-bench.py embed \
  --base-url http://<encoder>:8010 --model Qwen/Qwen3-VL-Embedding-2B \
  --mode embed-v1-chat --requests 100 --concurrency 8 --input-tokens 256 \
  --dimension-check 2048 --json-out embed.json

# Reranker: 1 query x 10 documents, fail loudly on a near-uniform score vector
python3 tools/pooling-bench.py rerank \
  --base-url http://<reranker>:8011 --model Qwen/Qwen3-VL-Reranker-2B \
  --requests 100 --docs-per-query 10 --concurrency 4 --fail-on-uniform

# Both servers, one request per shape, before measuring anything
python3 tools/pooling-bench.py smoke --base-url http://<encoder>:8010 \
  --model Qwen/Qwen3-VL-Embedding-2B --dimension-check 2048
```

**Why the mode flag exists and why it defaults to instructed.** On `/v1/embeddings` a plain
`{"input": "..."}` body takes a code path with **no chat template and no trained
instruction** — it returns plausible 2048-dim vectors computed from a prompt the model was
never trained on, while the startup log says the prompt prefixes loaded. Benchmarking that
path and comparing it to the instructed one is comparing two different models. `--mode` is
`embed-v1-chat` by default, every report prints the exact request shape plus a SHA of it,
and `embed-v1-raw` prints a warning. See `recipes/qwen3/QWEN3-EMBED-OPTIMIZATION-WORK.md`
§2 F11.

**A 200 OK is not a pass.** The point of this over `curl` is the checks after the status
line: embedding dimension, two different inputs producing different vectors, the same input
twice producing the *same* vector, a near-uniform score detector, a rank-inversion check
against a built-in fixture whose correct order is obvious, and — the one that matters most —
a **cross-encoder symmetry probe**.

The symmetry probe is two requests: score `(A,B)`, then score `(B,A)`. A cross-encoder reads
an ordered prompt, so the two differ. A bi-encoder computes cosine between independently
encoded vectors, so they are *identical* — swapping arguments cannot change a dot product.
That means it detects the worst failure this model family has (a reranker silently served as
an embedding model, `recipes/qwen3/QWEN3-EMBED-OPTIMIZATION-WORK.md` §2 F7) **with no
labelled data, no expected ranking, and no log parsing**. Mock-verified as non-redundant: the
symmetric mock passes the ranking check and the uniform checks and fails *only* symmetry,
which is exactly how the real bug presents. `--asymmetry-eps` sets the threshold (1e-4);
failure is fatal.

Read the score checks as a decision table rather than a scorecard: uniform **and** rank
failing together points at template/classifier wiring; rank passing while symmetry fails is
the bi-encoder; uniform failing while rank passes is a depth or temperature problem.

Latency at low `--requests` is an anecdote and the tool says so; compare medians of
repeated runs before believing a delta.

## quality-battery.py

`sparkrun`'s benchmarking path measures **speed** only. A quantized checkpoint can
lose quality without losing a single token/s, so the DeepSeek-V4.1-Flash EXL3 work
needed a quality instrument and had none — the only published numbers were the
checkpoint author's own in-domain calibration rows. This is that instrument.

Two deterministic, exact-match tiers over `/v1/chat/completions`:

- **`easy` (19 tasks)** — arithmetic, word problems, simple logic, factual recall,
  formatting, code basics, one needle. Proves a server answers and is not
  degenerate. It **saturates** (a competent model scores 100 %), so its number
  **cannot rank quality**; do not quote it as one.
- **`hard` (18 tasks)** — multi-step arithmetic with a required intermediate,
  exact constraint-following (count, reverse, case, JSON-only), false-premise
  traps (feathers-vs-steel, bat-and-ball, machines-and-widgets), in-prompt recall
  with a distractor, and longer code comprehension. Built to fail, so a
  non-perfect score is the informative result.

Why it is not just `curl`: every failure that matters returns **200 with plausible
text**, so scoring is exact-match/regex, `temperature` is pinned to 0, prompts are
unique (no shared prefix, so a radix cache cannot flatter a run), and **every raw
reply is kept and printed**. Two ground-truth bugs in this file's own history
(a forgotten 10 % tax; `'sparkrun'[::-1]` mis-typed as `nurknaps`) were caught
*only* because the raw answers were visible — read the failures, do not just read
the score.

Determinism caveat: DeepSeek-V4.1 is documented as not bitwise-stable across
batch composition, so a task can differ run-to-run at `temperature 0`. Use
`--repeat N`; a task that flips is reported as `FLAKY` and should be treated as
unstable, not scored.

```sh
python3 tools/quality-battery.py http://<head>:8000 --tier both --repeat 3 --json q.json
```

Measured on `deepseek-v4.1-flash-exl3-tp4-vllm` (2026-09-24): easy 19/19, hard
17/18 = 94.4 %, stable over 3 repeats; the single hard failure is character
reversal of an uncommon word (`sparkrun`), which common and long words pass —
a checkpoint weakness, **not** a proven quantization defect (no release-checkpoint
comparator was run). Full write-up: `attic/ds4/AGENTS.md` §7.6.

## needle-haystack.py

`sparkrun`'s benchmarking path measures **speed**, and `quality-battery.py` plants
a single needle in a ~3k-word haystack — a reasoning probe, not a context-window
probe. Nothing in this repo **exercised** a long context: the go-live DS4 recipe
serves 1,048,576 tokens, but its own README says the 1M retrieval "is configured
and served, **not needle-tested here**". This is the missing instrument.

It builds a haystack that reaches a requested context length, plants a needle at
each requested depth, asks for it, and reports where the window was actually
reached. The default depth grid is **every 10% of the window** (10…100), the
standard needle-in-a-haystack shape and the one the mod work cites
("needle correct at 799K", `attic/ds4/AGENTS.md` §7.5).

```sh
python3 tools/needle-haystack.py \
  --model deepseek-ai/DeepSeek-V4.1-Flash \
  --context-length 1000000 \
  --api-endpoint http://<head>:8000 \
  --json needle-1m.json

python3 tools/needle-haystack.py --selftest     # offline, no GPU, ~1 s
```

**`--json needle-1m.json`** writes the full result of the run to that file as
JSON — it is not a mode and it changes nothing about the test. The file is a
path you choose; the argument names a directory-relative destination, so
`needle-1m.json` means "write `needle-1m.json` in the current working directory".
The report the tool prints to stdout is a summary; the JSON is the durable
artifact and the thing to keep, because it carries what the summary drops:

- `model`, `endpoint`, `context_length`, and the server's `max_model_len`;
- the `calibration` block (the probe's measured tokens and the chars-per-token
  ratio actually used to size every prompt);
- one record per depth with `prompt_tokens` (the server's own count), `hits`/`of`,
  `latency_s`, `status`, `attempts`, and **the raw reply to every needle**, pass
  or fail — the replies are the reason it exists: summarised scores hide a wrong
  answer key, raw replies do not (`self-check-your-own-tools.md`);
- the final `verdict`.

Pick a filename that encodes the recipe or boot it measured (`needle-1m.json`,
`needle-knapcio-tp4.json`); the JSON records the *endpoint*, not the recipe name,
so the filename is the only place the recipe is written down. Omit `--json` and
the run is identical — you just lose the artifact and keep only the stdout
report.

**`--verbose`** prints live progress to **stderr**, so you can watch a run that
otherwise sits silent for minutes on a deep prefill. It narrates the endpoint and
resolved model, the server's `max_model_len`, the calibration outcome, the depth
list, and then per depth an `attempt N … ~T tokens to send` line before the
request and a `PASS/FAIL/TRUNCATED (hits, prompt_tokens, latency)` line after it.
It is stdout-clean by design — the report and the `--json` redirection stay
parseable — so `python3 tools/needle-haystack.py … --verbose > report.txt
2> progress.log` separates them, and `--json` on stdout is never polluted by
progress:

```
[nh] endpoint http://10.0.4.30:8000, model deepseek-ai/DeepSeek-V4.1-Flash
[nh] server max_model_len: 1048576
[nh] calibration: calibrated from one probe request; using 4.0374 chars/token
[nh] depths: [10, 50, 90]  (3 prefill(s))
[nh] depth 10%: attempt 1, 132273 chars, ~32768 tokens to send (ratio 4.0374 chars/token)
[nh] depth 10%: PASS (1/1 needles, prompt_tokens 33031, 8.41s)
```

As a library, pass `verbose=True` to `run_needle_test(...)` for the same stream.

**Why it is not just `curl` — a 200 OK proves nothing here.** A server that
silently truncates, was started with a smaller `max_model_len`, or answers from a
cached prefix all return 200 with plausible text. So the tool checks what the
status line cannot:

- the **actual** `usage.prompt_tokens` per request, and whether it reached the
  requested length — a prompt the server *accepts but reports as short* is a
  `TRUNCATED` finding, not a pass, because the run did not test the context it
  claims to;
- `temperature=0`, and a haystack that is **unique per depth** (a shared prefix
  would let this fleet's radix cache serve the deeper request from the shallower
  one and hide a real retrieval failure);
- the raw reply is kept and printed for every depth, pass or fail, so a scoring
  bug is visible rather than trusted.

**Sizing is measured, and capped to the served window.** Two things are
load-bearing, and the tool got both wrong in its first cut (`VERIFIED`
2026-10-03 against the live 1M endpoint):

- It reads `max_model_len` from `/v1/models` and **never builds a prompt longer
  than the server advertises**, leaving a 2 % headroom. Filling exactly the
  window is not possible — a request for 1,048,576 tokens always arrives a little
  over and is rejected — so the deepest depth serves ~1.03–1.07M tokens.
- It **measures** chars-per-token with one small probe request
  (`--chars-per-token N` overrides it). The naive ~4.6-char estimate overshoots
  this fleet's tokenizer (~4.04) by ~15 %.

The first cut's failure mode was quiet until you watched the server logs: on a
too-long error it shrank the *chars-per-token ratio* and rebuilt an equally-long
prompt, so a 1M request kept arriving as ~892k tokens — still over the window —
while each rejected attempt paid a full multi-minute prefill. It looked like a
400 loop, not a wrong answer. The retry now shrinks the **token target**, and
when the engine's error body carries the counts (`The input (N tokens) is longer
than the model's context length (M tokens).`) it parses them and corrects the
ratio exactly instead of guessing.

**Exit codes** distinguish *the server errored* from *the server answered
confidently and wrongly*, so a runbook can use it: `0` all depths retrieved and
reached the window; `1` transport / unreachable / every request errored; `2` bad
flags; `3` a check failed — a miss or a short (truncated) prompt.

**The tool carries its own negative controls.** `--selftest` runs the whole
ladder against an in-process mock with three behaviours — correct, always-wrong,
and truncating — and asserts each is classified the way it must be. A guard that
has only ever passed is not a guard (`self-check-your-own-tools.md`), and the
same three controls are re-run by `tests/test_needle_haystack.py`, which also
pins determinism across processes (the tool once seeded prompts with Python's
per-process-randomised `str` hash, which silently broke reproducibility).

Measured (`VERIFIED 2026-10-03`, `http://10.0.4.30:8000`,
`deepseek-ai/DeepSeek-V4.1-Flash`, TP=4 SGLang, one boot):

| window | depths run | result |
|---|---|---|
| 32k | 10 / 50 / 90% | 3/3 retrieved (prompt_tokens ~37.5k, pre-calibration) |
| 64k | 10 / 50 / 90% | 3/3 retrieved (calibrated 4.037 chars/token, prompt_tokens ~66.0k) |
| 1M | 100% | 1/1 retrieved (prompt_tokens 1,006,665, 362 s) — *pre-fix: overwindow, 400* |
| **1M** | **100%** | **1/1 retrieved — prompt_tokens 1,034,340, 379 s, no rejection** |

The 1M rows are the edge case that matters: 100 % depth is the deepest a prompt
can sit, and it is what exposed the overshoot. The final row is the tool run
exactly as the objective describes it (`--context-length 1048576` against the
live 1M endpoint) and it lands *inside* `max_model_len` and retrieves correctly.
A full 1M ladder (all ten depths) is ~10 cold prefills of up to ~20 min each and
is left to the operator; the tool exists so that run is reproducible.
