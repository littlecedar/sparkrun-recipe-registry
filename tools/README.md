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
comparator was run). Full write-up: `recipes/ds4/DS4-MODEL-OPTIMIZATION-WORK.md`
§7.5.6.
