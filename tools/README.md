# tools/

Stopgap measurement tooling for `sparkrun` recipes that the built-in benchmarking path
cannot reach, plus the DeepSeek-V4.1 artifact builders and the one shared module
(`synthetic_png.py`) that the measurement tools import. `safe_text.py` is the safety filter
that has to run *before* anything else here reads a log or a chat template.

Every tool here serves a live recipe lane; nothing in this directory is archival —
retired-lane instruments are archived with their lane (e.g. `attic/ifm/k2_36b_arith.py`).
Disposition audited 2026-10-11; the standard-suite trio (`eval-suite.py`, `agentic-horizon-probe.py`, `horizon-analyze.py`) added 2026-10-15:

| tool | serves | relationships |
|---|---|---|
| `safe_text.py` | every lane's log/template handling | guard: `tests/test_safe_text.py`; run before any DeepSeek log or 400 dump is read |
| `pooling-bench.py` | `recipes/embed/` + `recipes/rerank/` | imports `synthetic_png.py` by sibling path; guarded by `tests/test_qwen3_vl_embeddings.py` |
| `../plugins/pooling_bench_framework.py` | the same two lanes, driven through a `sparkrun benchmark` profile | the `BenchmarkingPlugin` that runs `pooling-bench.py` as its subprocess; out-of-tree, so it loads only from `plugins.paths` (see §plugins/); guarded by `tests/test_pooling_bench_framework.py` |
| `synthetic_png.py` | library for `pooling-bench.py` | also loaded by the same embed/rerank guard |
| `quality-battery.py` | `recipes/ds4/` benchmarks rig | imported verbatim by `recipes/ds4/benchmarks/run_benchmarks.py`; scoring kinds reused by `qwen4-quality-eval.py` |
| `build-dsv41-engram.py` | ds4 TP=2 lanes | still cuts the Engram tables from a repo that carries them (the open 1017 refresh path uses it); the bundled copy lives in `recipes/cybersec/mods/dsv41-engram-fetch/`, which **no shipped recipe mounts** as of 2026-10-17; guarded by `tests/test_dsv41_engram_builder.py` |
| `build-dsv41-combined.py` | cybersec arm 5 (the combined `littlecedar` stock it grafts onto) | shells out to `build-dsv41-engram.py`; reached through the launcher's `--stock-model` — the ds4 TP=2 arm now serves the 1017 pack and pre-warms `hub/dsv41-engram` instead; guarded by `tests/test_dsv41_combined_tool.py` |
| `needle-haystack.py` | ds4 1M lanes (any long-context boot) | guarded by `tests/test_needle_haystack.py` |
| `qwen4-quality-eval.py` | qwen4 W3 labquant comparator | scoring kinds from `quality-battery.py`; self-test only, no `tests/` guard |
| `jev-decision-bench.py` | `recipes/decision/jev-9b-decision-vllm.yaml` (JEV-9B scoring) | metric semantics mirror `tool-eval-bench` v2.8.0's decision plugin; self-test only, no `tests/` guard |
| `decision-tandem.py` | `recipes/decision/` CPU+GPU tandem probe | parses two tool-eval-bench decision reports' Full Trace and pools per-question distributions; self-test only, no `tests/` guard |
| `decision-ensemble.py` | the served clef+Kai ensemble (`/v1/systemone` proxy) | imports `decision-tandem.py`'s pooling rule so the served and analysed ensembles cannot drift; self-test only, no `tests/` guard |
| `decision-ladder.py` | `recipes/decision/` arms (the concurrent ladder; `/v1/systemone` plus JEV's `/v1/completions`) | replays the vendored Typed Decisions split at c 1/2/5/10; reports **req/s** and decisions/s, never t/s; a failed cell exits 1; guarded by `tests/test_decision_ladder.py` |
| `bfcl-eval.py` | `recipes/explore/` tool-calling models (BFCL v3) | port of BFCL's official AST checker; guarded by `tests/test_bfcl_eval.py` |
| `eval-suite.py` | every lane's standard evaluation pass (the SOP) | drives `quality-battery.py`, `needle-haystack.py`, `bfcl-eval.py` and the ds4 hard tier against one live endpoint, then the horizon probe; `--selftest` |
| `agentic-horizon-probe.py` | long-horizon agentic arms (ornith lane; any agentic serve) | writes `<out>.jsonl` + `<out>.jsonl.summary.json`; `--selftest` |
| `horizon-analyze.py` | the horizon probe's JSONL arms | prints the per-arm loop/degradation summary; used by `eval-suite.py --checks horizon` |
| `humanizer-measure.py` | the **rewrite-integrity instrument** — any arm whose job is to rewrite text without changing its facts (`recipes/explore/humanizer-12b-q6k-llamacpp.yaml` is its first shipped user) | 20 fixed drafts × 2 samples through `/v1/completions` with a byte-exact prompt (fingerprint `cc51d66b4c593fbe`) and a deterministic sampler; reports fact-diff, formatting-drop and wall-clock per 1k output tokens. Recovered verbatim from the 2026-10-14 receipt so the 2026-10-22 quant tiers compare against the archived bf16 baseline on one scale |
| `humanizer-analyze.py` | the scorer of the same instrument | re-imports the drafts from `humanizer-measure.py` rather than from a receipt, and re-scores any arm's `results.json` — that is how bf16 / Q4_K_M / Q6_K were compared; guarded with the recipe by `tests/test_humanizer_measure.py` |
| `cache-audit.py` | the fleet `sparkrun` runtime-cache (every lane's compiles) | registry-level, not lane-level: maps each cache tree to the recipe that owns its leaf key, so "which of these 99 trees is stale?" is a command and not a hand-derivation; `--selftest`; guarded by `tests/test_cache_audit.py`; policy and reclaim list in `mad-science/STORAGE-POLICY.md` |
| `refresh-sweep.py` | every lane's pins (the CI refresh gate) | registry-level like `cache-audit.py`: surveys recipe `model:`/`model_revision:`/`container:` lines, the mod/launcher revision pins and the Dockerfiles' `ARG BASE_IMAGE`/`FROM`/`ARG <NAME>_REF` build inputs against Hugging Face, Docker Hub, ghcr and GitHub, plus the dedicated llama.cpp fork-vs-upstream section; `--apply` moves containers only; `--accept-file` declares deliberate holds and a dead entry gates as `stale-acceptance`; guarded by `tests/test_refresh_sweep.py`; needs network and exits 2 without it |

## eval-suite.py (the SOP pass)

One live OpenAI-compatible endpoint in, one receipt directory out. Axes are chosen with `--checks`
(default `contract,house,needle`; add `hard,tools` for reasoning/tool-calling arms, `horizon` for
agentic ones): `contract` (`/v1/models` served id + `max_model_len` + one greedy completion), `house`
(the 19+18 battery), `needle` (32k / 128k / served max), `hard`
(`recipes/ds4/benchmarks/run_benchmarks.py` — GSM8K + ARC), `tools` (`bfcl-eval.py`; needs
`--bfcl-data-dir`, and a missing data dir is a `skip`, never a pass; its completion budget is
`--bfcl-max-tokens`, **default 4096** — bfcl-eval's own default is 512 and the leg passed none until
2026-10-17, which is why the first llama-cpp arm's `parallel` cells were answered inside a 512-token
budget), `horizon`
(`agentic-horizon-probe.py` + `horizon-analyze.py`).

The exit code is the verdict; `summary.json` and each check's raw artifact land in the receipt
directory. A truncated non-empty reply is a measurement, not an error. Perf is deliberately out of
scope — the SOP runs `benchmarking/concurrency-ladder.yaml` with `--skip-run` against the same boot.
`--selftest` proves every check's wiring against stub children and a socket mock (no model, no
network).

## safe_text.py

The serving API rejects any request whose `message.content` **or** `reasoning_content` carries
the raw image placeholder token with HTTP 400 `reasoning_content contains image special
token` — the request is refused, not sanitised, so a session that *reads* one byte of that
token out of a file loses its context. The token is the sequence

    U+003C  U+FF5C  "deepseek_image"  U+FF5C  U+003E

(U+FF5C is FULLWIDTH VERTICAL LINE — not the ASCII `|`). It arrives through file reads: an
image a harness serialises as text, a raw HTTP-400 request dump under
`~/.omp/logs/http-400-requests/`, or a chat template that stores the placeholder on purpose
(the upstream DeepSeek-V4.1 encoding file in `.scratch/ifm/upstream/sglang/.../encoding_dsv41.py`
is one such file). This tool never prints the token: it is assembled from codepoints by
`raw_token()`, and no shipped file in this tree contains the literal (guarded by
`tests/test_safe_text.py`).

**A byte-clean file is not a safe file.** A *decodable spelling* — the six ASCII characters
`\uff5c` between the `<` and `>` — holds no raw token bytes, so a byte scan says "clean", and
then the next `json.loads` on that object rebuilds the raw token and poisons the reader anyway.
Measured 2026-10-07: `.scratch/ds4/vision-hard/raw/B.1.jsonl` stored the serving API's 400 text
verbatim (via `json.dumps`) and killed a live agent session. So `--check` flags the spellings
too, `--scrub` removes them, and no shipped file may hold one (same guard file).

Four modes, one transform each:

- **escape** (default, read): every non-ASCII codepoint becomes `\uXXXX`/`\UXXXXXXXX`, every
  backslash is doubled, undecodable bytes become `\xNN`. Output is **ASCII-only**, so no input
  can carry the token through it.
- **`--unescape`** (write): the exact inverse, for the callers that need the raw placeholder
  bytes back — a chat template handed to a tokenizer, an HTTP body. Writes are tmp +
  `os.replace`, preserve mode/owner, and replace a symlink rather than following it (writing
  through one would rewrite the node's HF snapshot).
- **`--check`**: reports line:column of every raw token and the count of decodable spellings,
  exits 1 if either is present, and prints the *escaped* form, never the token. A
  missing/unreadable file is exit 2, never "clean". `--check-nonascii` adds advisory non-ASCII
  locations.
- **`--scrub`**: replaces every spelling (raw, `\uff5c`, `\U0000FF5C`, doubled backslashes)
  with `[deepseek_image]`, a marker with no delimiter and no backslash that stays inert through
  further decoding. Far narrower than `escape`: everything else is byte-identical, so a JSONL
  stays valid JSONL. Content-addressed (a clean file is not rewritten) and refused on a file a
  running process holds open — tmp+replace would strand a live writer (an omp session JSONL) on
  the orphaned inode; `--force` overrides. Use it on logs, session files, and dumps; use
  `--scrub -o`/stdin when you need a *readable* safe copy.

```sh
tools/safe_text.py --check ~/.omp/logs/http-400-requests/*.json   # locate, exit 1 on hit
tools/safe_text.py dump.json -o dump.safe.txt                     # ASCII-safe copy
tools/safe_text.py --unescape tpl.safe -o chat_template.jinja     # raw token back
tools/safe_text.py --in-place --unescape tpl.safe                 # rewrite in place
tools/safe_text.py --scrub record.jsonl -o record.safe.jsonl      # safe read path
tools/safe_text.py --scrub --in-place ~/.omp/logs/http-400-requests/*.json
```

Exit codes: `0` clean, `1` `--check` found the token (raw or decodable spelling), `2` the tool
could not run. The escape is the one trusted boundary: `escape()` asserts its own ASCII-only
output, `unescape()` raises on any backslash it did not emit *and* on non-ASCII input (which
proves the caller is holding a raw file), and all of it is covered by `tests/test_safe_text.py`
(44 tests, including negative controls proving the detector ignores ASCII-bar lookalikes, that
`escape()` is not an identity, and that a scrub leaves prose which cannot decode back).
Verified end-to-end on the real 400-dump artifact: 191427 bytes → 196412 ASCII bytes →
byte-identical unescape (sha256 match).

**Escaped at rest, raw at the call site.** A template that must *contain* the placeholder —
a VL request body, a tokenizer fixture, a chat template the campaign launches compare — is
stored escaped and unescaped only where it is used: `save_template(path, text)` /
`load_template(path)` in the module, or `--unescape` on the CLI. That keeps every checkout of
this tree free of the literal token (guarded by the test above) while the request still
carries the real bytes. Importable API: `raw_token`, `escaped_token`, `escape`, `unescape`,
`escape_bytes`, `unescape_bytes`, `save_template`, `load_template`, `find_raw_token`,
`contains_raw_token`, `find_token_spellings`, `contains_token_spelling`, `non_ascii_spans`,
`scan_text`, `scan_file`, `SCRUB_MARKER`, `scrub_text`, `scrub_file`.

## pooling-bench.py

`sparkrun`'s benchmarking frameworks (`benchmarking/*.yaml`, `framework: llama-benchy` and
`tool-eval-bench`) both drive `/chat/completions`, and a pooling engine has no chat endpoint.
**Neither can measure an embedding or reranker server, and the failure is not silent** —
measured 2026-10-15 on the installed stack (sparkrun 0.4.0, llama-benchy 0.4.0): against a
stub serving `/v1/embeddings` and 404ing `/v1/chat/completions`, `llama-benchy` exits 1 with
`Warmup failed: HTTP 404: ... does not support chat completions` and writes no result row,
so the same run through `sparkrun benchmark performance <pooling recipe> --profile
benchmarking/concurrency-ladder.yaml` reports `Task 1/4 failed` and then
`Error: Benchmark incomplete; schedule did not complete` (exit 1) having launched nothing it
could measure. (The *older* failure mode — a result file whose every metric is `null`, which
exported as a clean-looking table — is what `BenchmarkingPlugin.measured_nothing` exists to
reject: `sparkrun/api/_benchmark.py:1328-1332`, `benchmarking/llama_benchy.py:620-627`.)
Either way **no standard profile produces a pooling number.** This tool measures
`/v1/embeddings`, `/v2/embed`, and `/v1/score`; `plugins/pooling_bench_framework.py`
(next section) is the same instrument behind `sparkrun benchmark`.

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
and `embed-v1-raw` prints a warning. The client-side contract this encodes is written up
in `recipes/embed/README.md` ("Serving the encoder correctly").

**A 200 OK is not a pass.** The point of this over `curl` is the checks after the status
line: embedding dimension, two different inputs producing different vectors, the same input
twice producing the *same* vector, a near-uniform score detector, a rank-inversion check
against a built-in fixture whose correct order is obvious, and — the one that matters most —
a **cross-encoder symmetry probe**.

The symmetry probe is two requests: score `(A,B)`, then score `(B,A)`. A cross-encoder reads
an ordered prompt, so the two differ. A bi-encoder computes cosine between independently
encoded vectors, so they are *identical* — swapping arguments cannot change a dot product.
That means it detects the worst failure this model family has (a reranker silently served as
an embedding model — the bi-encoder catch-all `recipes/rerank/README.md` guards against) **with no
labelled data, no expected ranking, and no log parsing**. Mock-verified as non-redundant: the
symmetric mock passes the ranking check and the uniform checks and fails *only* symmetry,
which is exactly how the real bug presents. `--asymmetry-eps` sets the threshold (1e-4);
failure is fatal.

Read the score checks as a decision table rather than a scorecard: uniform **and** rank
failing together points at template/classifier wiring; rank passing while symmetry fails is
the bi-encoder; uniform failing while rank passes is a depth or temperature problem.

Latency at low `--requests` is an anecdote and the tool says so; compare medians of
repeated runs before believing a delta.

## plugins/pooling_bench_framework.py

The pooling lanes' `BenchmarkingPlugin`: it lives in the repo's top-level `plugins/`
directory (not `tools/`, which stays stdlib-only — this module imports `sparkrun` by
definition), it measures nothing itself, and it drives `tools/pooling-bench.py` from a
sparkrun **profile**, so a pooling sweep gets what every other lane gets from a framework —
one resumable artifact per cell (`000_embed_c1.json`), gap detection on a cell that measured
nothing, an exported `--output` measurement, and `sparkrun benchmark pooling …` as a
first-class subcommand.

**A registry cannot supply a plugin, and this repo cannot fix that.** sparkrun's plugin
discovery is config-driven and separate from the registry it clones: a `RegistryEntry` is
`subpath` / `tuning_subpath` / `benchmark_subpath` / `mods_subpath` / `format` and nothing
else (`sparkrun/core/registry.py:168-178`), so no registry field can point at a plugin
directory. Out-of-tree plugins arrive two ways — a `plugins.paths` directory
(`sparkrun/core/external_plugins.py`, every module inside is imported and each must declare
`SPARKRUN_PLUGIN_API_VERSION = 1`) or a pip `sparkrun.plugins` entry point — and **both are
user actions on the machine running `sparkrun`, not registry content.** The clone therefore
ships the module and the docs ship the two lines; without them the framework is simply not
registered.

```sh
sparkrun setup features enable core.external_plugins   # OFF by default on every channel
```
```yaml
# config.yaml
plugins:
  paths:
    - <path to this clone>/plugins
```

`sparkrun setup plugins list` then shows `pooling_bench_framework  external  on`, and
`sparkrun benchmark pooling --help` exists (a framework's `categories` become subcommands).
Only the head that drives the sweep imports it — never the serving nodes: the scheduler runs
the instrument locally and hands it the endpoint URL.

Profile contract — one task per `concurrency` value, and `kind` is **required** because
embed and rerank answer on different routes, so neither is a safe default:

```yaml
framework: pooling-bench
args:
  kind: embed                 # embed | rerank
  mode: embed-v1-chat         # instructed form; embed-v1-raw is the A/B, never a default
  concurrency: [1, 4, 8, 16, 32]
  requests: 100
  input_tokens: 256
  dimension_check: 4096       # 2048 for the 2B / 4096 for the 8B AWQ encoder
  salt: true
  warmup: 5
```

```sh
# the shipped ladder pair (benchmarking/pooling-ladder-embed.yaml / -rerank.yaml),
# on an arm that is already serving
sparkrun benchmark pooling recipes/embed/qwen3-vl-embedding-8b-awq-4bit-vllm-b12x.yaml \
  --hosts <node> --skip-run --profile benchmarking/pooling-ladder-embed.yaml --output ladder.yaml
```

**How the framework gets picked, and the one way to get this wrong.** `framework_name` and
`categories` are what register it: `sparkrun benchmark pooling …` exists because
`categories = ("pooling",)`, and `--framework pooling-bench` is the explicit alternative.
What matters is *when* it is chosen — a pinned category subcommand sets the framework from
its category **before** the profile is read (`sparkrun/api/_benchmark.py:438-457`), and the
profile's own `framework:` key only fills one that is still unset (`:495-505`). So either run
`benchmark pooling`, or run `benchmark run` with the profile naming the framework; run a
pooling profile under `benchmark performance` and llama-benchy gets pooling args (measured
2026-10-15: `Error: Benchmark incomplete`, exit 1, no number), while `--framework
pooling-bench` under `performance` is refused outright — `Error: Framework 'pooling-bench' is
not registered for category 'performance'`.

Every other arg is rendered straight onto the instrument's command line (`-b
docs_per_query=10` for the rerank kind), so a new pooling-bench option needs no edit here and
a misspelt one fails in the tool's own argparse. Two failure modes worth knowing: a missing
`kind` raises `BenchmarkError` from `build_task_list` *before* any launch (sparkrun prints it
as a traceback — the message is the last line), and a target that answers nothing fails the
task and aborts the run rather than exporting a number. Guard:
`tests/test_pooling_bench_framework.py` (command shape, the cell-identity keys compared
against a *real* instrument payload, and negative controls proving both "measured nothing"
and a mismatched cell are rejected).

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

**Budget:** house runs take `--max-tokens 4096`. A thinking arm at 1024 can spend the whole
allowance reasoning and return a truncated answer (`finish_reason: length`) — `big-1` came back
`11111` instead of `1111111110` on Nemotron-3.5-Lightning that way. That is a **budget miss, not a
capability miss**: re-ask before recording a failure (4096 was the budget on 42 of the 43 house
receipts up to 2026-10-21).

**Mode is part of the number:** `--thinking on|off` sends
`chat_template_kwargs {"enable_thinking": bool}`, and **unset sends no kwargs at all**, so every
lane measured before 2026-10-22 sent the identical request bytes and its receipts stay comparable.
Say which mode a score came from: on `Spark-X2.6-4B` the same battery scores **37/37 thinking-on and
30/37 stable thinking-off** (decode rate is not the only thing a caller gives up).

Measured on `deepseek-v4.1-flash-exl3-tp4-vllm` (2026-09-24): easy 19/19, hard
17/18 = 94.4 %, stable over 3 repeats; the single hard failure is character
reversal of an uncommon word (`sparkrun`), which common and long words pass —
a checkpoint weakness, **not** a proven quantization defect (no release-checkpoint
comparator was run). Full write-up: `attic/ds4/AGENTS.md` §7.6.

Live consumer: `recipes/ds4/benchmarks/run_benchmarks.py` imports this file verbatim for the
house tier of the deepseek vs deepseek-turbo gateway comparison (`recipes/ds4/benchmarks/README.md`).

## build-dsv41-engram.py

Builds the DeepSeek-V4.1-Flash **Engram tables** from the *online* Hugging Face repo,
without downloading or unpacking the model weights into a local HF cache.

The TensorFold TP=2 lane (`recipes/ds4/deepseek-v4.1-flash-tensorfold-tp2-1m-sglang.yaml`)
serves from the EXL3 checkpoint, whose quantizer **omitted the Engram tables**. The tables
(189 GiB, layers 1 and 14) exist only in the *official* `deepseek-ai/DeepSeek-V4.1-Flash`
repo — a ~285 GB checkpoint. `huggingface_hub` snapshotting it to reach 189 GiB of tables
means materializing the whole model. This tool instead speaks **HTTP byte-range GETs** to
the HF CDN, reads the two shard headers to locate the four `engram.embed.{weight,scale}`
tensors, and copies their ranges into a small self-contained directory that the engine
reads verbatim.

```sh
# pre-warm a node for the TP=2 lane (the launcher's TF_DS_ENGRAM path)
python3 tools/build-dsv41-engram.py --out /cache/huggingface/hub/dsv41-engram --workers 24

# slow link: run it detached, then poll; it survives logouts and ssh drops
python3 tools/build-dsv41-engram.py --detach         # prints pid + log path
python3 tools/build-dsv41-engram.py --status         # progress; exit 0 = complete

# offline completeness check (no network); exit 0 = complete
python3 tools/build-dsv41-engram.py --check

# smoke test, no big transfer
python3 tools/build-dsv41-engram.py --layers 1 --limit-rows 5000 --out /tmp/engram-smoke

# knapcio TP=4 packed 264-B shards instead (parity with pack_engram.py)
python3 tools/build-dsv41-engram.py --format packed --tensor-parallel 4 --rank 0 --out /tmp/engram
```

Run it **on a node** (not through `sparkrun`) to pre-warm: with a bare `--out` it
writes the host HF cache the container bind-mounts
(`~/.cache/huggingface/hub/dsv41-engram`), resumable across interruptions. Run it
inside the serving image and it uses the in-container path. It always resumes: an
interrupted fetch continues from its `.engram-progress.json` cursor.

**Why ranged reads, not `hf_hub_download`.** A GB10 has ~117 GB of usable unified memory and
the source is 189 GiB; snapshotting or buffering it does not fit. The tool bounds each
in-flight range, writes straight to disk, and advises written pages `POSIX_FADV_DONTNEED`,
so **peak RSS measured ~0.6 GiB** while writing 94 GiB (verified on `[.34]`, 2026-10-06). One
ranged request per 256 MiB segment also keeps the request count low enough to avoid HF's
`429`; one request per chunk does not (observed at ~12k requests on a full table).

**Output layout.** `--format safetensors` (default) writes `engram-l<L>.safetensors`, one per
layer, each with that layer's `.engram.embed.weight` and `.engram.embed.scale` as two
contiguous planes. This is exactly what TensorFold's `Engram` reader expects: it globs
`*.safetensors` in `TF_DS_ENGRAM` and reads row `i` at
`8 + header_len + data_offsets[0] + i * prod(shape[1:])`. `--format packed` writes the
knapcio TP=4 layout (magic `DSV1EN41`, 4096-B header, 264-B records). Both are resumable.

**Wiring.** `recipes/cybersec/mods/dsv41-engram-fetch/` (unmounted mod) wraps this builder as a
pre-exec hook, but **no shipped recipe mounts it** as of 2026-10-17: both TP=2 arms read their
Engram tables from the combined `littlecedar/DeepSeek-V4.1-Flash-EXL3-2.9bpw-with-engram` pack,
which carries them in its own `engram/` subdir and which the launcher prefers (the ds4 arm serves
that pack directly; the cybersec abliterated arm grafts onto it and reaches the tables through the
launcher's `--stock-model`). The mod remains the **out-of-band pre-warm path** for a node without
the combined pack — and the engram path the open 1017 refresh item still names. Its invocation is
unchanged: **always fetches detached** — sparkrun runs a mod as a pre-exec hook under a hard
600 s timeout, and a slow-link fetch can take hours, so a blocking fetch is a
launch-killing risk (observed); it is a no-op once the tables are complete (`--check`), and
`--detach` prints a pid and log path to poll with `--status`. For a fresh deployment the honest
path is to
**pre-warm each node out-of-band** with this tool, or to declare an Engram repo in the
recipe's `distribution_config.models` so sparkrun downloads it once on the head and
rsyncs it to the workers (`--verify-rows N` re-fetches N random rows from the source
and compares them to the output). Guarded by `tests/test_dsv41_engram_builder.py`
(stdlib-only, network-free): the decisive check re-implements the reader's addressing
rule and proves the emitted bytes satisfy it.

## build-dsv41-combined.py

Vendors **one local Hugging Face repo** that carries everything the TensorFold TP=2
lane needs, so a node no longer stitches three sources together:

- `Mia-AiLab/DeepSeek-V4.1-Flash-EXL3-2.9bpw` — the EXL3 2.9 bpw weights (39 shards,
  ~196 GiB) and the EXL3 `config.json` / `quantization_config.json` (authoritative);
- `deepseek-ai/DeepSeek-V4.1-Flash` — the **updated prompt** (`chat_template.jinja`),
  `tokenizer.json` / `tokenizer_config.json`, and the whole repo under `upstream/`;
- the **Engram tables** (layers 1 & 14, ~189 GiB) that the EXL3 quantizer omitted,
  written to an `engram/` subdir.

```sh
# build the repo (~430 GiB free); stages shards 47/48 for a fast local rebuild
python3 tools/build-dsv41-combined.py --out ~/.cache/models/DeepSeek-V4.1-Flash-EXL3-2.9bpw-combined

# ranged-fetch the tables from HF instead of staging 203 GB of shards
python3 tools/build-dsv41-combined.py --out <dir> --engram-online
```

**Why a subdir for the tables.** The engine globs `*.safetensors` **non-recursively**
in its Engram dir; at the repo root that glob would also walk the 39 EXL3 shards. So
the tables live in `engram/`, and `mods/tensorfold-dsv41-launcher` prefers
`<model_dir>/engram/`, making `model: <this repo>` sufficient (consumed by
`recipes/ds4/deepseek-v4.1-flash-tensorfold-tp2-1m-sglang.yaml`).

**Why stage the shards by default.** A direct ranged read of the two tables runs at
~15 MiB/s (hundreds of small segment requests), while a whole-file `hf download` of
`model-00047/48` runs at ~170 MiB/s; the local rebuild then streams disk-to-disk.
`--engram-online` is there for the low-disk case.

Output includes `provenance/SOURCES.json` (pinned revisions) and `provenance/MANIFEST.json`
(per-file size + sha256), plus `provenance/chat_template.exl3.jinja` (the prompt the
EXL3 conversion shipped, kept for comparison) and `provenance/README.md` (the layout and
the distribution model). **Never reads tokenizer or chat-template content** — files are
moved and hashed as bytes only.

**Distributing.** `sparkrun` distributes models **by repo id into the node HF hub cache**
(`huggingface-cli download <id> --cache-dir <cache>/hub`); a local directory is not
auto-distributed. Push the repo to the org (`hf upload`) and point the recipe's `model:`
at that id, or pre-place `models--<org>--<name>/snapshots/<rev>` on each node.

Guarded by `tests/test_dsv41_engram_builder.py` (the launcher's combined-repo resolution)
and the recipe guards in `tests/test_ds4_recipes.py`.

## needle-haystack.py

`sparkrun`'s benchmarking path measures **speed**, and `quality-battery.py` plants
a single needle in a ~3k-word haystack — a reasoning probe, not a context-window
probe. It has since produced the DS4 lane's 1M receipts on our hardware (measured
below): the TP=4 canary passed at 985k, and the TensorFold TP=2 lane passed a 262k
sweep plus a ~959k probe on 2026-10-10.

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

**`--verbose`** prints live, **timestamped** progress to **stderr**, so you can
watch a run that otherwise sits silent for minutes on a deep prefill. Each line
starts with a local-time `[YYYY-MM-DD HH:MM:SS]` stamp (self-contained, no OS
locale), so a transcript can be correlated with the server log afterwards. It
narrates the endpoint and resolved model, the server's `max_model_len`, the
calibration outcome, the depth list, and then per depth an `attempt N … ~T tokens
to send` line before the request and a `PASS/FAIL/TRUNCATED (hits, prompt_tokens,
latency)` line after it. It is stdout-clean by design — the report and the
`--json` redirection stay parseable — so `python3 tools/needle-haystack.py …
--verbose > report.txt 2> progress.log` separates them, and `--json` on stdout is
never polluted by progress:

```
[2026-10-03 20:04:44] [nh] endpoint http://<head>:8000, model deepseek-ai/DeepSeek-V4.1-Flash
[2026-10-03 20:04:44] [nh] server max_model_len: 1048576
[2026-10-03 20:04:46] [nh] calibration: largest two probes agreed; sweep stopped early [~65536→75283tok; ~32768→37481tok]; using 4.0065 chars/token
[2026-10-03 20:04:46] [nh] depths: [100]  (1 prefill(s))
[2026-10-03 20:04:46] [nh] depth 100%: attempt 1, 4120189 chars, ~1027605 tokens to send (ratio 4.0065 chars/token)
[2026-10-03 20:10:59] [nh] depth 100%: PASS (1/1 needles, prompt_tokens 1026494, 373.22s)
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

- It reads the served window from `/v1/models` — `max_model_len`, or
  llama.cpp's `meta.n_ctx` (its entry carries no top-level window key) — and
  **never builds a prompt longer than the server advertises**, leaving a 2 %
  headroom. Filling exactly the window is not possible — a request for
  1,048,576 tokens always arrives a little over and is rejected — so the
  deepest depth serves ~1.03–1.07M tokens.
- It **measures** chars-per-token with a **size sweep** (`--chars-per-token N`
  overrides it). The naive ~4.6-char estimate overshoots this fleet's tokenizer
  by ~15 %; more subtly, *each probe size builds a different haystack*, so the
  measured ratio carries a content variance that shrinks with size (measured on
  this fleet against the 1M truth of 4.0139: ~0.65 % spread at 8k, ~0.31 % at
  65k, ~0.09 % at 128k). The sweep (`65536, 32768, 8192`) probes largest-first
  and takes the ratio from the **largest usable probe**, which reads within
  ~0.06 % of truth — a few hundred tokens at a 1M target, well inside the 2 %
  headroom. 128k was tried and dropped: its extra precision cannot change the
  outcome and costs ~15 s more prefill. Smaller sizes are fallbacks for
  narrow-window servers, and probe targets are kept well below the window (the
  build overshoots its target by ~15 %), so a probe is never a request that 400s.
- A depth that was **cut rather than answered** — empty content with
  `finish_reason: length` — is recorded `TRUNCATED` with the cut named
  (completion budget spent on reasoning vs window exhausted), never as a
  retrieval miss; the per-depth `finish_reason` is in the artifact.  The first
  llama-cpp arm hit this at the suite's 256-token needle default (a thinking
  template spent it inside the think block).

The first cut's failure mode was quiet until you watched the server logs: on a
too-long error it shrank the *chars-per-token ratio* and rebuilt an equally-long
prompt, so a 1M request kept arriving as ~892k tokens — still over the window —
while each rejected attempt paid a full multi-minute prefill. It looked like a
400 loop, not a wrong answer. The retry now shrinks the **token target**, and
when the engine's error body carries the counts (`The input (N tokens) is longer
than the model's context length (M tokens).`, or llama.cpp's `request (N tokens)
exceeds the available context size (M tokens), try increasing it` with
`"type": "exceed_context_size_error"` and the counts in `n_prompt_tokens` /
`n_ctx`) it parses them and corrects the ratio exactly instead of guessing.
Matching only the SGLang/vLLM wording is how the first llama-cpp arm's 131k
rung ended as a hard error instead of a retry, so the matcher and the counter
parser now cover both engines.

**Exit codes** distinguish *the server errored* from *the server answered
confidently and wrongly*, so a runbook can use it: `0` all depths retrieved and
reached the window; `1` transport / unreachable / every request errored; `2` bad
flags; `3` a check failed — a miss or a short (truncated) prompt.

**The tool carries its own negative controls.** `--selftest` runs the whole
ladder against an in-process mock with four controls — correct, always-wrong,
truncating, and an over-window 400 in llama.cpp's wording — and asserts each is
classified the way it must be. A guard that
has only ever passed is not a guard (`self-check-your-own-tools.md`), and the
same controls are re-run by `tests/test_needle_haystack.py`, which also
pins determinism across processes (the tool once seeded prompts with Python's
per-process-randomised `str` hash, which silently broke reproducibility).

Measured (`VERIFIED 2026-10-03`, `http://<head>:8000`,
`deepseek-ai/DeepSeek-V4.1-Flash`, TP=4 SGLang, one boot):

| window | depths run | result |
|---|---|---|
| 32k | 10 / 50 / 90% | 3/3 retrieved (prompt_tokens ~37.5k, pre-calibration) |
| 64k | 10 / 50 / 90% | 3/3 retrieved (single 8k probe, 4.037 chars/token, ~66.0k) |
| 1M | 100% | 1/1 retrieved (single 8k probe, prompt_tokens 1,006,665, 362 s) — *over target* |
| 1M | 100% | 1/1 retrieved (single-probe fix, prompt_tokens 1,034,340, 379 s) |
| **1M** | **100%** | **1/1 — sweep ratio 4.0173, prompt_tokens 1,029,226 (target 1,027,605, +0.16 %), 377 s** |

The 1M rows are the edge case that matters: 100 % depth is the deepest a prompt
can sit, and it is what exposed the overshoot. The sizing improved across the three
fixes — the single 8k probe predicted a 1,036,572-token prompt for a 1,027,605
target (+0.87 %, a rejection), the sweep predicts 1,020,107 (+0.16 % at the server,
comfortably inside `max_model_len`). A full 1M ladder (all ten depths) is ~10 cold
prefills of up to ~20 min each and is left to the operator; the tool exists so
that run is reproducible.

**2026-10-10, TensorFold TP=2 lane** (receipts in `recipes/ds4/README.md`): 262k sweep
3/3 at depths 10/50/90 % (prefill 190–364 s per probe) and a single ~959k probe at
depth 50 %: 1/1 at 958,919 prompt tokens, 1226.7 s prefill (~782 tok/s) — retrieval
intact at ~96 % of the 1M window.

## gate-37111.py

Nothing else in `tools/` **soaks**. `quality-battery.py` and `qwen4-quality-eval.py` score a
short answer once, `needle-haystack.py` retrieves once per depth, and `sparkrun`'s
benchmarking path measures speed — none of them sit on a server for an hour, compare a warm
prefix against a cold one, or watch for degeneration. Two upstream SGLang bugs corrupt
output **silently** on exactly the engine and topology the qwen4 lane ships
(Qwen3.8-Flash-Next, QSA sparse attention + NEXTN speculative decoding, GB10 / SM121, TP2):

- `sgl-project/sglang#37111` — "QSA + NEXTN decode graph silently corrupts output on GB10
  TP2" (opened 2026-08-30; open as of 2026-10-04);
- `sgl-project/sglang#38319` — "Chunked Prefill + Radix Insert race corrupts KV pages (QSA,
  Qwen3.8-Flash-Next)" (opened 2026-09-07; open as of 2026-10-04, proposed fix PR #38355
  open and unmerged).

Both return HTTP 200 with plausible-but-wrong text, so a health check, a throughput
benchmark and a `curl` smoke test all pass while the server emits garbage. The lane's rule
(the WORK doc's §14) is blunt: a config that is 10 % faster and occasionally emits garbage is
a regression. The issue states are kept in the tool's `UPSTREAM` block and printed at start
and into every report, so a verdict is self-describing instead of re-derived from memory.

```sh
# default soak: 1 minute, temperature 0, tool loop, no depth padding
python3 tools/gate-37111.py --base-url http://127.0.0.1:8000

# a real release gate: 90 minutes at ~100k depth, JSON artifact
python3 tools/gate-37111.py --base-url http://127.0.0.1:8000 \
    --depth-tokens 100000 --duration-min 90 --json gate-37111.json

# a fast smoke before a long soak
python3 tools/gate-37111.py --depth-tokens 8192 --turns 3

python3 tools/gate-37111.py --selftest     # offline, in-process mock, ~2 s
```

**`--thinking` off is explicit** (since 2026-10-19, `9eee3a2`): every request carries
`chat_template_kwargs.enable_thinking` as a boolean. It has to — the flag used to omit the kwarg, and a
thinking-by-default template (Qwen3.8-Flash-Next) then spent the whole essay budget inside the think
block and returned `content: ""` with `finish_reason: length`, which the detectors report as
degeneration plus truncation. A thinking arm needs `--thinking` *and* a larger `--essay-max-tokens`
(2048 is not enough here; 8192 was not either); a non-thinking arm is unaffected.

**Three failure modes, three detectors.** (1) *Repetition / `!!!!` collapse*, the signature
both reports describe: a reply is flagged if it is empty, shorter than 40 chars, more than
30 % punctuation, contains a ≤20-char fragment repeated 6+ times, or — for replies of 40+
words — has under 15 % distinct words. (2) *Truncation*, a reply the engine calls finished
that stops dead: `finish_reason == "length"` without a terminal character, or long prose
ending mid-clause on a bare alphanumeric. (3) *Prefix-cache corruption*, the discriminator
that makes this tool more than a vibes check.

**The discriminator is warm-prefix vs cold-prefix disagreement.** #38319's mechanism is a
radix node referencing KV pages a retract already freed, so its observable is
*prefix-specific and persistent*: every request sharing the corrupted prefix reads the same
garbage. The tool therefore asks a fixed canary (`47*89`, answer `4183`) twice — once at the
end of the soak with the long shared system prompt resident in the radix tree, once after a
cold re-ask (a `/flush_cache` POST, then GET if the method is gated, else a salted fresh
system prompt using `--seed`). `temperature=0` everywhere, so agreement is a pass and any
disagreement is corruption, not sampling noise; the report records which `cold_method` was
used. A canary that answers wrongly on *both* asks is its own finding.

The soak itself: every request carries the same long system prompt (`--depth-tokens N` pads
it toward N estimated tokens with a structured fake-registry ledger, so the prefix is
realistic rather than one repeated line; 0 = unpadded, otherwise the flag must be `>= 1024`
or the tool exits 2). Two of every three iterations are a deterministic tool-call turn
(`get_shard_status` / `verify_checksum` / `list_entries` with fixed args, accepted as either
native `tool_calls` or a JSON reply), the third is a non-looping ~600-word essay probe
(`--essay-max-tokens`, default 2048). The conversation grows across turns so prefix reuse is
genuinely exercised. Note `--chars-per-token` (default 4.0) only *builds* the prompt — the
report carries the server's real `usage.prompt_tokens`. `--model` defaults to the first id
from `/v1/models`; `--verbose` prints timestamped progress on stderr so a 90-minute soak
shows life while stdout and the `--json` artifact stay clean.

**Exit codes** separate *the server errored* from *the server answered confidently and
wrongly*, so a release runbook can gate on them: `0` PASS; `1` transport failure /
unreachable / every request errored; `2` bad flags (a non-positive `--duration-min` with no
`--turns`, or `--depth-tokens` between 1 and 1023); `3` FAIL. `3` also covers `PARTIAL` — a
run where no corruption was seen but transport errors kept it from completing — because a
gate must not turn an incomplete soak into a pass.

**A PASS is a negative result, not proof of absence.** #37111 has not had its cross-boot
frequency measured and #38319 is stochastic and appears at specific context sizes; the
default 1-minute soak is a smoke, not a release gate (§14 asks for 1–2 h at ~100k depth). A
report is only about the endpoint it records, and if `/flush_cache` is unavailable the cold
path falls back to a salt the server may decline. A FAIL, by contrast, is actionable on its
own. The tool says all of this at the end of a clean run and points at
`tools/gate-37111-design.md`, which holds the failure mode, the R0–R6 toggle ladder that
localises a FAIL to a named cause (radix off, the in-tree chunked-insert fix, eager vs
decode graph, spec off, chunk shape), and the "what a PASS proves" limits. Guarded by its own
`--selftest` (five mock behaviours — clean must PASS/0; degenerate, truncate, and both
radix shapes must FAIL/3, with the clean case asserted to produce no findings at all); no
`tests/` guard references it.

Lane state: `attic/qwen4/AGENTS.md` (the W4 row); run record and reproducer shapes:
`attic/qwen4/status/W4-GATE-STATUS.md`.

## qwen4-quality-eval.py

`recipes/qwen4/` now ships a single checkpoint, the locally-quantised
`local-inference-lab/Qwen3.8-Flash-Next-NVFP4` (the "labquant" export); the
`RadixArk/Qwen3.8-Flash-Next-NVFP4` reference arm was archived to `attic/qwen4/arms/` on
2026-10-14 (the instrument still runs against either). Labquant quantises
attention/GDN projections *and* the PLE n-gram table where RadixArk leaves them BF16, and its
own recipe caveat says benchmark wins are **not** evidence of equal quality — the lane had no
eval. `quality-battery.py` is a small generic battery shared with the DS4 lane; this is the
labquant-specific instrument, built to separate the two checkpoints on the exact paths
labquant quantises.

It measures **exact-match task accuracy** at `temperature=0` over
`/v1/chat/completions`, on a fixed, version-controlled battery that the tool pins to a
`battery_sha256` printed in the header and stored in the JSON. 38 tasks in six categories:

- **`arith` (8)** — multi-step arithmetic whose regex demands the *required intermediate*
  value as well as the final one, so guessing the answer without doing the steps fails;
- **`instr` (8)** — exact instruction-following (reverse, upper-case, JSON-only, count,
  hyphenated words), most of them anchored with `$`;
- **`falsepremise` (6)** — traps whose correct move is to reject the premise (US independence
  from France, Einstein failing maths, Mercury "reclassified", a third Curie Nobel, the
  largest prime, a woman winning the 1896 marathon); scored with the added `reject` kind, an
  accept-marker list, so answering the question as asked fails;
- **`recall` (6)** — long in-prompt recall with a decoy code, filler generated per task from
  `--seed` so prompts are unique and share no long prefix (a radix cache cannot flatter a
  run);
- **`code` (8)** — short Python/JS comprehension;
- **`verbatim` (2)** — one-copy round-trip of an exact string, the closest exact-match probe
  of the n-gram / PLE path that speculative decoding leans on.

Scoring kinds `num` / `any` / `re` are reused from `quality-battery.py` so the two
instruments read alike (`quality-battery.py` itself is not modified). The raw
`message.content` is scored; if `content` is empty but `message.reasoning_content` came back
— the split-channel shape SGLang serves for this model — the reasoning text is scored
instead and the record is flagged `reply_used_reasoning_fallback`, so a budget-exhausted
answer is visible rather than silently a fail.

```sh
python3 tools/qwen4-quality-eval.py                       # http://127.0.0.1:8000
python3 tools/qwen4-quality-eval.py --base-url http://host:8000 \
    --model /cache/runtime/labq-patched --json q4-labquant.json --repeat 3
python3 tools/qwen4-quality-eval.py --selftest            # offline, no GPU
```

`--repeat N` repeats the whole battery; a task that flips is printed as `FLAKY` and belongs
in the report as "unstable", not as a score — the same determinism caveat as
`quality-battery.py` (a reasoning-capable server may not be bitwise-stable across batch
composition even at `temperature=0`). `--limit N` runs the first N tasks of battery order,
`--seed` (default `20261004`) seeds the generated recall prompts, `--max-tokens` (1024),
`--timeout` (600 s) and `--api-key` pass through, `--model` is resolved from `/v1/models`
when omitted, and `--fail-under PCT` turns the run into a release gate that exits 1 when the
total percentage is below PCT (0 disables). **Every raw reply is kept and printed**, with the
final line carrying the per-category tallies, `TOTAL x/y = z%`, `stable-pass n/tasks` and any
transport failures; `--json` writes the whole artifact (battery version + sha256, per-task
pass vectors, per-category summary, every record with its reply and reasoning-fallback flag).
Measured numbers belong next to the *other* arm: this is a **paired comparator, not an
absolute quality score**, and a 38-task exact-match battery cannot certify an export — it can
only fail to find a gross regression on the axes it covers. It does not measure reasoning
quality, safety, calibration, long-context retrieval (`needle-haystack.py`) or throughput.
Exit codes: `0` the battery ran (the score is the artifact), `1` no request completed — the
endpoint was unreachable for every task — or `--fail-under` was missed, `2` bad flags.
Guarded by its own `--selftest`
(ground truth — every task's sample must pass its own scorer — prompt uniqueness with no
shared prefix over 16 chars, category coverage, `score()` units, and correct/wrong/empty
mock controls); no `tests/` guard references it.

Measured numbers live next to the arms: `attic/qwen4/AGENTS.md` (the W3 row) and
`attic/qwen4/status/W3-QUALITY-EVAL-STATUS.md` (the paired-run record).

## jev-decision-bench.py

The decision lane's scoring instrument for `autotrust/JEV-9B`. `sparkrun`'s
built-in `tool-eval-bench` path drives `/v1/systemone` (clef's surface); JEV
does not have one — its card's native System 1 contract is one
`/v1/completions` request per question with `logprobs` +
`allowed_token_ids` over the `jev-decision` LoRA, scored client-side with the
decision-head bias and per-kind calibration temperature. This tool speaks
exactly that contract (the request body and the `z_i = (lp + bias) / T`
softmax are the card's, verbatim) over the vendored Typed Decisions test
split — the same 400 cases / 2000 decisions tool-eval-bench v2.8.0 scores, so
the headline number is comparable with clef-flash's 70.3%.

Metric semantics mirror tool-eval-bench's decision plugin exactly (argmax
with first-listed tie-break, KL(gold ‖ pred) in nats with a 1e-12 floor over
the gold keys, Brier over the union, top-label ECE in 10 bins, the ★
rating at the 47.0% prior / 73.5% teacher-ceiling anchors). Documented
differences: one request per question (JEV's native per-question contract;
TEB sends all five questions of a case in one `/v1/systemone` request — same
decisions, different request shape, so latencies are not comparable), and
structured states serialize as sorted-key compact JSON (the vendor's
SystemOne convention; the JEV card documents only string states).

```sh
python3 tools/jev-decision-bench.py --base-url http://<node>:8000 \
    --cases <vendored>/test.jsonl.gz --json jev-decision-bench.json
python3 tools/jev-decision-bench.py --selftest     # offline, no network, ~1 s
```

The case file is the tool-eval-bench v2.8.0 vendored copy; the tool verifies
its decompressed sha256 against the vendored manifest and fails closed on a
modified split. Exit codes: `0` run completed (the score is the artifact),
`1` every request failed, `2` bad flags or case-file integrity failure.
Guarded by its own `--selftest` (golden prompt rendering, hand-computed
bias/temperature softmax, hand-computed accuracy/KL/Brier/ECE including a
tie case and a floor case); no `tests/` guard references it.

Measured (2026-10-12, `recipes/decision/README.md`): the card's worked choice
example reproduces (0.328 / 0.144 / 0.528 / 0.001 against the card's ≈ 0.33 /
0.14 / 0.53 / 0.001).


## decision-tandem.py

Answers whether co-serving a GPU decision model with a CPU one lifts accuracy, and whether
the two contend. Input is the `### Full Trace` section of a tool-eval-bench v2.8.0
`--decision-bench-only` markdown report (its durable artifact): the tool parses the
per-question predicted and gold distributions, then pools them question-by-question under two
equal-weight rules — **linear** (arithmetic mean) and **loglinear** (geometric mean /
product-of-experts) — and scores `argmax(pooled) == gold label`. It reports each model alone,
each ensemble, the exact two-sided McNemar test of the ensemble-vs-A accuracy delta, and a
per-kind table.

```sh
python3 tools/decision-tandem.py <a-report.md> <b-report.md> --a-name clef --b-name kai
python3 tools/decision-tandem.py --selftest     # offline, synthetic fixture, ~0 s
```

Both arms must speak `/v1/systemone` so the distributions share an option space: clef-flash,
Kai-0.6B, and Sol-2B do; JEV-9B does not (its card contract is `/v1/completions`, one request
per question, `tools/jev-decision-bench.py`) and its report is not accepted. The 2026-10-13
probe (result, pairing study, co-serve contention) is archived in
`attic/decision/AGENTS.md` §"CPU+GPU tandem probe (2026-10-13)"; the tool is re-run with
`recipes/decision/README.md` §"The clef + Kai ensemble", receipts
`~/benchmarks/decision-tandem-20261013/` and `~/benchmarks/decision-ensemble-20261015/`.

## decision-ensemble.py

The reference implementation of the clef + Kai ensemble, **served** as one
`/v1/systemone` endpoint. The ensemble is a client-side pooling rule, so every
re-implementation is a chance to get the rule subtly wrong (mean-then-argmax vs
argmax-then-vote, a different tie-break, a dropped label, a log-linear pool that
is scored as accuracy): this proxy imports `decision-tandem.py`'s `linear` /
`normalise` / `argmax` so the served ensemble and the analysed ensemble cannot
drift apart, and it answers the same wire shape both members answer. It fans a
request out to both members in parallel, pools each question by type
(`probabilities` for choice/score, the `noul` scalar for noul), and reports
`usage.input_tokens` as the **sum** of the two members' usage - the ensemble's
real compute bill. Both members must answer: a dead member is a 502 (and a 503
from `/health`), never a silent pass-through of the survivor.

```sh
python3 tools/decision-ensemble.py --a http://<node>:8020 --b http://<node>:8000 \
    --a-model Cloudflare/clef-flash --b-model vllm-sr/Decision-2.0-Kai-0.6B --port 8021
python3 tools/decision-ensemble.py --selftest     # offline, stub members, ~1 s
```

Two behaviours are load-bearing and both are asserted by `--selftest`:

* **One advertised model.** `/v1/models` returns the proxy's own id (`--as-model`, default
  `decision-ensemble`) and nothing else. Merging the members' ids looks tidy and is a trap: a
  client that auto-detects the model then sees two candidates and prompts for a number — with
  no TTY, tool-eval-bench v2.8.0 looped on `Select model [1-2]:` and wrote 3.7 GB of prompts
  into a log before the run was killed (2026-10-15). The client's model string is irrelevant
  here anyway: `--a-model` / `--b-model` decide what each member is asked for.
* **Per-request fan-out.** Each client request gets its own pair of threads; a shared small
  pool would make the proxy the ensemble's concurrency ceiling. `--selftest` asserts four
  concurrent clients overlap.

Measured 2026-10-15 (`.34`, both members booted from their recipes): pooling the two members'
own reports with `decision-tandem.py` gives **71.6% (1432/2000)** on the Typed Decisions test
split — +63/−37 against clef alone, exact McNemar p = 0.012 — and the recorded instrument pass
*through this proxy* (`uvx tool-eval-bench@2.8.0 --base-url http://127.0.0.1:8021 --model
decision-ensemble --decision-bench-only`, full 400 cases) scores **71.7% (1433/2000)** on the
same boot. Recomputing the served report's distributions with `decision-tandem.py` gives 1432:
the difference is one *exact tie* (`security_incidents_000055` severity, 0.28/0.28) where
tool-eval-bench breaks by first-listed option and `decision-tandem.py` by greater label —
served and offline agree on the argmax label at 1999/2000 and on the distributions to ≤5e-4,
so this is a tie-break convention, not a pooling difference. Read the *rate* as the pool's,
never as a member's: a pooled request costs `max(member)` latency, so the served ensemble runs
at the CPU arm's pace (**0.192 req/s, p50 5.2 s** on a 20-case prefix at c1; the full pass ran
p50 8.4 s co-resident) while clef alone serves 4.9 req/s. Receipts:
`~/benchmarks/decision-ensemble-20261015/` (`ensemble.json`, `reports/ensemble-served-c1.md`,
`logs/proxy-teb-r2.log`, `logs/proxy-correctness.log`, `ladder-ensemble-c1.json`).

## decision-ladder.py

The concurrent harness the decision lane's `C1`/`C2`/`C5`/`C10` columns need.
`sparkrun`'s benchmarking frameworks both drive `/chat/completions`, which no
arm in this lane serves, so the lane's throughput numbers can only come from a
tool that speaks the lane's own APIs; and the instrument that produces the
lane's accuracy (`tool-eval-bench --decision-bench-only`) is serial unless it is
given `--parallel N`. This tool replays the *vendored* Typed Decisions test
split - the same 400 cases the instrument scores, extracted from
`tool-eval-bench`'s own `vendor/typed_decisions/test.jsonl.gz` and verified
against its manifest sha256 - at a fixed concurrency per level and reports
**requests/s**, aggregate **decisions/s**, the per-request decisions/s at that
cell's median latency, TTFT p50/p95 and the decisions returned against the
decisions asked for. One `/v1/systemone` request is one case (five decisions in
one forward pass); `--api completions` swaps to JEV-9B's card contract, one
question per request (one decision), reusing `jev-decision-bench.py`'s body and
prompt rendering, so the JEV path cannot drift from the scoring tool.

Read the unit strictly: `req/s` here is **not** `t/s`, and a prefill-only scorer
has no decode rate to report, so these numbers never fill a `t/s` column. It is
a closed-loop rate (offer N, count completions) and the concurrency is the
client's, so quote the level with every number.

**A cell is verified, never merely timed.** A 4xx, a transport failure, an
unparseable body, a body truncated short of its `Content-Length`, a response
with fewer decisions than the case has questions, or zero decisions marks the
cell `ok: false`, prints `FAILED` with its error counts, and exits 1 - the rate
over the survivors is not the endpoint's rate.

```sh
python3 tools/decision-ladder.py --base-url http://<node>:8020 \
    --model Cloudflare/clef-flash \
    --cases <vendored test split>.jsonl --concurrency 1,2,5,10 --runs 5 --json ladder.json
python3 tools/decision-ladder.py --base-url http://<node>:8000 --api completions \
    --decision-head <jev decision_head.json> --model autotrust/JEV-9B \
    --cases <vendored test split>.jsonl --json jev-ladder.json
python3 tools/decision-ladder.py --selftest    # offline, stub server, ~2 s
```

Both lane servers **require** the request's `model` field (clef's `/v1/systemone` answers
`422 {"loc":["body","model"]}` without it), and `--model` is checked before any request is
sent rather than left to the server. `--runs` defaults to 5 (the registry's five-run
convention, pooled into one rate); the 2026-10-15 ladders below were single passes (`--runs 1`).

`--limit` takes a deterministic *prefix*, which samples one workflow of the
four; for a CPU arm that cannot afford 4 x 400 requests, slice with a stride
file instead (every 4th case keeps all four workflows at 1/4 the cost) and use
the same file for every arm being compared.

Guarded by `tests/test_decision_ladder.py` (31 tests): independent stub servers over
sockets cover the happy cell, `--runs`, both APIs, the artifact and exit codes, every failure
mode, and a `NegativeControls` ladder that re-derives the wire-counted decisions, the measured
wall, the per-request TTFT and the saturation ratio.

Measured 2026-10-15 (`.34`, each arm booted solo, `req/s` at c1/2/5/10):

| arm | c1 | c2 | c5 | c10 | p50 at c1 -> c10 |
|---|---:|---:|---:|---:|---|
| clef-flash (GPU), stride-4 slice | 4.89 | 5.11 | 5.16 | 5.51 | 206 ms -> 1.82 s |
| Kai-0.6B (CPU), stride-4 slice | 0.187 | 0.186 | 0.156 | 0.128 | 5.70 s -> 82.1 s |

Both arms are serial — clef buys 13% of throughput for 8.8x the latency, Kai
*loses* 32% for 14x — and the instrument's own `--parallel N` reproduces clef's
row within 1%, so this is the endpoint, not the harness. Numbers, unit
discipline and the index consequence: `recipes/decision/README.md` §"A req/s
ladder, not a t/s ladder" (receipts `~/benchmarks/decision-ensemble-20261015/`,
`ladder-*.json`).

## synthetic_png.py

Not a CLI — the one **library** in this directory, and the reason `pooling-bench.py` can
benchmark image-bearing score traffic honestly. vLLM's multimodal cache is keyed on image
*content*, not on URL: appending a random query parameter to every image URL left a run at an
identical 81.5 % prefix-cache hit rate and moved `mm_cache_hits_total` from 448 to 898 — all
450 new requests hit the cache despite 450 distinct URLs. So the only way to send genuinely
distinct pixels is to generate them.

Solid-colour PNGs are the cheapest way to do that: a flat image compresses to a few hundred
bytes, so 400 distinct images cost less bandwidth than one photographic one while still
presenting the vision encoder with the same patch grid — encoder cost follows sequence length,
not image entropy, which makes it a fair proxy for encoder and prefill cost. It is **not** a
proxy for realistic attention over real content and a flat image may be scored oddly: it
measures capacity, not quality.

Stdlib only (`base64`, `zlib`, `struct`). `solid_png_b64(width, height, rgb)` returns a
base64 non-interlaced 8-bit RGB PNG (colour type 2, every row filter byte 0 so zlib collapses
the image to a handful of bytes) and rejects out-of-range dimensions or channels with
`ValueError`; `solid_data_url(...)` wraps it as a `data:image/png;base64,…` URL;
`iter_chunks(png)` yields `(tag, data)` per chunk and raises `ValueError` on structural
damage (bad signature, truncated chunk, CRC mismatch, no `IEND`) — used by the self-check
rather than hand-computed offsets, which is exactly the kind of arithmetic a self-check
should not get wrong.

**Where it is imported from.** `tools/pooling-bench.py` loads it by sibling path in
`_synthetic_png_module()` (`importlib.util.spec_from_file_location("synthetic_png",
Path(__file__).resolve().parent / "synthetic_png.py")`) — by path rather than by name
because that file runs three ways (as a script, by path from a recipe, and via importlib from
tests), and pooling-bench exits with a message if the module is missing. It is consumed by
pooling-bench's `--synthetic-images` (one distinct PNG per document; implied `--multimodal
image`) at `--synthetic-size` WxH (default 480x640). `tests/test_qwen3_vl_embeddings.py` also
loads it by path to check that the same nonce gives the same image, different nonces give
different images, and that a corrupted PNG is rejected.

```sh
python3 tools/synthetic_png.py     # self-check, offline, stdlib only
```

The self-check decodes its own output using nothing but the standard library — header fields,
per-row `filter=None`, an all-flat-red pixel scan — confirms distinct colours produce distinct
bytes, and corrupts one byte to prove `iter_chunks`' CRC check actually fires (a negative
control, not decoration).

## bfcl-eval.py

`sparkrun`'s benchmarking path measures **speed**, and the repo's quality instruments
(`quality-battery.py`, `qwen4-quality-eval.py`) are in-house exact-match batteries that no
published number is comparable to. The explore lane's brief is frontier reasoning + **tool-calling**
models, and three of its shortlist entries publish **BFCL** scores (`inclusionAI/Ling-3.0-flash`,
`Aleph-Alpha/Kolibri-1`, `meta-models/Muse-Glimmer-30B`) — so BFCL is the standard suite that lane
needs, and the one its research doc names (`attic/explore/EXPLORE-MODELS-RESEARCH.md` §4).

This tool runs the official BFCL v3 questions against an OpenAI-compatible `/v1/chat/completions`
and scores them with a **port of the official AST checker**
(`bfcl_eval/eval_checker/ast_eval/ast_checker.py`, ShishirPatil/gorilla, AGPL-3.0): function name,
required parameters present, no unexpected parameter, and value **plus type** matched against the
gold answer with BFCL's own case/punctuation standardization (`"April 1, 2024"` == `"april1 2024"`;
an integer is accepted for a `float` parameter, a float is not accepted for an `integer` one).

**One deliberate deviation.** Same questions, same gold, same scoring rule; the *request shape*
differs. The official harness prompts the model for a BFCL-dialect function call as text and parses
it; this tool sends the functions through the OpenAI `tools` parameter and reads the structured
`message.tool_calls` back (with a JSON-in-`content` fallback). That is how a vLLM/SGLang serve
exposes tools (`--tool-call-parser`) and how the already-adopted `tool-eval-bench` drives them, so
the score is comparable **in kind** with a published BFCL number — not identical to it: a template
or parser that drops the structured call reads as "no call", which is a real finding about that
serve rather than a scoring bug.

Scored: `simple`, `multiple`, `parallel`, `parallel_multiple`, `irrelevance`, and their `live_*`
twins (plus `live_relevance`; `irrelevance` passes iff the model emits **no** call, `relevance` iff
it emits one). Not scored, by construction: `java`/`javascript` (language-specific type
converters), `rest`/`sql`/`exec_*` (executable, not AST, evaluation), and `multi_turn_*` (stateful
tool execution) — a `--categories` naming one of those is a bad-flag exit, not a silent skip.

The data is the official v3 JSON, revision-pinned (Apache-2.0). Fetch it once on the head node:

```sh
hf download gorilla-llm/Berkeley-Function-Calling-Leaderboard \
    --repo-type dataset --revision 61fc0608cfd831fcfbbaa676ebdfef0ed963eeda \
    --local-dir ~/bfcl
```

```sh
python3 tools/bfcl-eval.py --base-url http://127.0.0.1:8000 \
    --data-dir ~/bfcl --categories simple,multiple,parallel,irrelevance \
    --json bfcl.json
python3 tools/bfcl-eval.py --selftest     # offline, in-process mock, ~1 s
```

`temperature` is 0, and the raw `tool_calls` of **every** question — pass or fail — go into
`--json`, so a scoring mistake is auditable rather than trusted. **`--max-tokens` defaults to 512**,
which is the right default for a non-thinking arm and a truncation trap for a thinking one: a
reasoning template spends the budget inside the think block and the record then carries `calls: []`.
The artifact keeps the choice's `finish_reason` (since 2026-10-17; the two receipts written that
morning predate the field, so their `calls: []` rows cannot be re-diagnosed), which is what makes a
`length` cut distinguishable from a genuine no-call. The suite's `eval-suite.py --bfcl-max-tokens`
(default 4096) is the budget knob that matters for a sweep; check for it in the receipt's argv echo
before comparing two arms.
`--tool-choice` (default `auto`) is
there because on the explore lane's Ling arm auto mode answered in prose and only a forced
`tool_choice` produced structured calls: `auto` is the standard BFCL condition, `required` isolates
the parser. Exit codes: `0` the run completed (the score is the artifact), `1` no request completed
or `--fail-under` missed, `2` bad flags / missing or malformed data files. A transport error is
excluded from the score — never counted as a pass or a miss — and a question needing a modality this
tool does not send (an image) is skipped and counted, not scored.

**Verified.** `--selftest` runs five mock behaviours end-to-end (correct must score 100 %;
wrong-name, wrong-value, empty-output, and hallucinated-on-an-irrelevant-question must all be
rejected), and `tests/test_bfcl_eval.py` (47 tests) re-runs that ladder plus the negative controls it
does not isolate, drives the whole CLI over a socket against a mock endpoint, and pins the loader's
fail-closed rule. Offline against the real BFCL v3 AST split (2026-10-14), the ported checker accepts
a correct model's output on **1000/1000** questions — **400** simple, **200** multiple, **200**
parallel, **200** parallel-multiple — so the port agrees with the gold on every question a perfect
model should pass, and (from the guard and the selftest) rejects the tampered ones. One
official-split oddity worth knowing: `simple_363`'s question names the function
`restaurant_search.find_closest` while its answer key is `find_closest`; the checker scores by the
*description's* name, so a real model is unaffected, but a naive gold-replay keyed on the answer name
mis-scores it.

A score is not proof of quality: it is one instrument on one endpoint, and a reasoning-capable
server is not bitwise-stable across batch composition even at `temperature` 0.

## cache-audit.py

The one tool here that is not a lane instrument. `sparkrun`'s runtime cache
(`${WOPR_USER_CACHE}/sparkrun/runtime-cache/<family>/<model_key>`) holds every lane's compiled and
autotuned artifacts — ~2.5 TiB across the six nodes, in ~99 trees — and **the only way to tell a live
tree from a superseded one is the leaf key**, which sparkrun derives as
`sanitize(model)[:48] + "-" + sha256("<model>@<model_revision>")[:8]`. Nothing on the node knows the
registry's shipped set, and the `modlogs/` heuristic in AGENTS.md fails exactly where it matters most:
measured 2026-10-15 on the ds4 lane, the live tree (the recipe's current pin) and the superseded one
(the same model with an *empty* `model_revision`) carry the same `dsv41-sglang-overlay.log` and the
same mod set. This tool recomputes the key for every recipe and answers the question mechanically.

```sh
# the other half of the census is per node: `hf cache ls`, `df -h /home`
sparkrun setup prune-runtime-cache --hosts .30,.31,.32,.33,.34,.35 --all --dry-run > census.txt
uv run python -B tools/cache-audit.py --census census.txt --budget-gb 500
uv run python -B tools/cache-audit.py --selftest        # offline, no cluster, ~0 s
```

It accepts both census shapes — sparkrun's `would-remove <size> <host>:<path>` receipt and a
`du -sk`/`stat` listing under a `##### <host>` header — merges a tree seen in both (the dry-run rounds
sizes to 0.1 GB and carries no marker, so a first-wins parser would report every tree as unmarked and
pin its age at unknown), and labels each leaf `live` (a shipped recipe produces the key), `retired`
(only an `attic/` arm does) or `STALE` (nothing does). It prints per-node totals against the budget,
exits 1 when a node is over it, and prints the reclaim list with sizes, marker ages and the guarded
sweep command. **It deletes nothing and never calls a tree stale on recency** — the 72 h in-use rule
is applied on top of the key verdict, and an unmarked tree is reported as invisible to both of
sparkrun's sweeps rather than as free space.

`--selftest` pins the key derivation against six leaves read off the fleet (including the 48-char
label-cap case `…-AEON-ULTIMATE-UNCENSO-b9f737e7`, so a reader who "fixes" the truncation fails it),
the recipe scan finding the shipped keys and *not* producing the two stale ds4 keys, both parser
shapes, the merge rule, and the 72 h gate; `tests/test_cache_audit.py` re-runs that ladder inside the
repo's gate. Policy, budget derivation, and the reclaim list live in
`mad-science/STORAGE-POLICY.md`.

## refresh-sweep.py

`sparkrun` records pins in six places and nothing reads them back: the recipe's `model:` +
`model_revision:`, its `container:` digest, the mod/launcher revision constants
(`DEFAULT_REVISION`, `OVERLAY_REVISION`, `MODEL_REVISION`, `hf download … --revision`), the
Dockerfile's `ARG BASE_IMAGE` / `FROM …@sha256:` / `ARG <NAME>_REF`, and the engine ref inside a
fork-built image. Two hand surveys on 2026-10-22 found all of the failure modes at once — model
revisions behind Hub heads across five arms, a floating `ARG BASE_IMAGE` that made a rebuild
non-reproducible, and every llama.cpp arm frozen behind a publisher that stopped — so the survey is
a command now, and CI runs it.

```sh
uv run python -B tools/refresh-sweep.py --json /tmp/sweep.json --markdown /tmp/sweep.md --exit-code
tools/refresh-sweep.py --lane explore --only container-newer-release --exit-code   # one lane, one class
tools/refresh-sweep.py --recipe recipes/explore/kolibri-1-apex-24bpw-llamacpp.yaml
tools/refresh-sweep.py --cache ~/.cache/refresh-sweep.json --apply               # containers only
tools/refresh-sweep.py --accept-file tools/refresh-sweep-accepted.json --exit-code
```

**What it answers.** Per pin, a class from a fixed vocabulary — `model-current`,
`model-stale-weights`, `model-stale-docs`, `model-unpinned`, `model-unresolvable`,
`container-current`, `container-newer-release`, `container-floating`,
`container-unresolvable`, `build-input-current`, `build-input-newer-release`,
`build-input-floating`, `build-input-stale`, `build-input-unresolvable`, and
`stale-acceptance` — printed verbatim in the table, the JSON and the markdown so an issue
body can be assembled from it. Stale models are split **weights** vs **docs** by the unified diff
of `…/compare/{pin}..main`: a changed `.safetensors`/`.gguf` is a re-boot, a changed `README.md` or
`.eval_results/` is not. A repo id keeps its owner's spelling (`Qwen/…`, `inclusionAI/…`) — Hub
lookups are case-sensitive and are never lower-cased before a request.

**A digest pin is a freeze, and the two kinds of pin are read differently.** In a recipe,
`container: tag@sha256:…` whose tag moved is `container-newer-release`, because that is the line CI is
asked to bump. In a Dockerfile, `FROM tag@sha256:…` (or `ARG BASE_IMAGE`) is the reproducible form the
repo writes on purpose, so the same tag resolving elsewhere is `build-input-current` with the live
digest recorded — `build-input-stale` is reserved for a git build ref (`ARG <NAME>_REF`) that its
branch has moved past, `build-input-floating` for a tag with no digest (the actual reproducibility
defect), and `build-input-newer-release` for a tag the registry no longer publishes (report-only,
never applied).

**Fail closed.** A pin the tool could not check is `*-unresolvable`, never silent cleanliness: an
unparseable recipe is an error, an empty selection is an error, an empty diff behind a moved head is
an error (the state is contradictory, so nothing is claimed), and a registry 404 for a pinned tag
is `container-unresolvable`. Exit codes, which CI depends on: **0** no drift class present, **1**
drift present, **2** the sweep could not run (network, parse, git). `--only` narrows both the report
and the gate to the classes named, so a container-only job cannot be failed by model drift; an exit
of 2 is *always* 2, with or without `--exit-code`, so a broken sweep can never read as clean.

**`--apply` is container-only by policy.** It rewrites `container:` lines whose class is
`container-newer-release` — the same tag resolving to a newer digest, which is a rebuild of the tag
the arm already names — and nothing else. It refuses to run on a non-empty `git status --porcelain`
(so a bump can never be folded into someone else's in-flight edit), refuses if the `container:` line
no longer matches the ref it surveyed, and prints per edited arm the boot command and the receipt the
bump needs (TTR to port-open, `/v1/models`, one smoke completion, then the arm's own ladder/battery).
**A model re-pin is never applied**: those are boot-gated by lane policy, and a newer tag the arm does
not already name is reported (`newest_tag`) for a human to choose, never auto-selected.

**Sources and caching.** Docker Hub tag listings and tag details, ghcr's anonymous pull token plus
the manifest digest, Hugging Face model metadata + raw compare diffs + commit lists (token from
`--token-env`/`HF_TOKEN`, else `~/.cache/huggingface/token`), and the GitHub API for llama.cpp and its
forks (`GITHUB_TOKEN`/`GH_TOKEN`, else the gh CLI's stored oauth token — unauthenticated GitHub is
60 requests/hour and the llama section needs about a dozen). `--cache PATH` stores responses with
their `cached_at`, and the report prints it beside any row served from cache; an entry older than an
hour is refetched, so a stale cache is never presented as current.

**The llama.cpp section is why the tool exists.** Every llama.cpp arm here runs a fork or a
third-party build: `brywil/llama.cpp@68fa28b` (`kolibri1`), `Xunzhuo/llama.cpp@c9f5974`
(`decision2`), and `scitrera/dgx-spark-llama-cpp:b10549-cu131` whose publisher stopped. The section
reports our refs with `behind_by` against **upstream** `ggml-org/llama.cpp` master (cross-repo
compare, same fork network) *and* against the branch that holds the ref, upstream head + date + latest
release, the `upstream_supports` map for the three features that motivated the forks (`graph_mtp` in
`src/models/mellum.cpp`, `src/models/kolibri1.cpp`, `src/models/vllm-decision2.cpp`) plus `121a-real`
in `ggml/src/ggml-cuda/CMakeLists.txt` — determined by fetching those paths at the upstream head and
matching text, so a 404 is `false` and only a network failure is `unknown` — and each llama-cpp
image's publisher status (newest tag, newest upload date). That is the answer to "can a stock build
replace this fork image?".

**Deliberate holds are declared, not silenced.** `--accept-file PATH` (default
`tools/refresh-sweep-accepted.json` when it exists) takes
`{"accepted": [{"ref", "class", "reason", "since"}]}`, where `ref` is a regex matched against a row's
pinned ref or its path, so one entry can cover a group of arms. An accepted row is still printed and
still appears in the markdown under its own **Accepted** table, but it does not gate `--exit-code` and
`--apply` will not touch it. An entry that matches nothing is reported as `stale-acceptance` and
**gates**: a hold that was fixed silently must not linger. The shipped file is the three holds that
are correct today — the five `lmsysorg/sglang:dev-cu13` arms (digest-frozen per lane policy), the two
`python:3.12-slim` decision arms (the base is only an interpreter; their server is pip-installed at
boot), and the Mellum GGUF's additive `mtp/*` drafts (the shipped `Q4_K_M` is byte-identical).

Measured 2026-10-22 against the tracked tree: 52 recipes, **59 model pins, 52 container pins, 13
build inputs**, 0 unresolvable, 12 gating drift rows and 8 accepted holds, exit 1 — `lmsysorg/sglang:dev-cu13`
had moved under 5 arms and `python:3.12-slim` under 2 (the seven `--apply` candidates, all accepted
holds today), 9 arms were behind on docs only, 1 behind on weights (the Mellum `mtp/*` files, also
accepted), 10 Dockerfile base images were digest-frozen and current, 2 `ARG <NAME>_REF` build inputs
have no default, and `upstream_supports` was yes for all four features while the `scitrera`
publisher's newest upload was still 2026-08-21.

**It needs network.** Run it where Docker Hub, ghcr, Hugging Face and GitHub are reachable; offline it
exits 2 rather than reporting a clean tree, which is the point. Guard: `tests/test_refresh_sweep.py`
(46 tests, stdlib only, every registry call served by a fixture, an unmatched URL is a failure) — the
negative controls are that `revision:` is not a pin, that a missing tag is not `current`, that a
digest-pinned base whose tag moved is *current* while a tag-only `FROM` is *floating*, that an accepted
drift stops gating while a dead acceptance starts, that an empty selection and an unparseable recipe
raise, that `--apply` refuses a dirty tree and leaves `model_revision:` bytes untouched, and that the
`graph_mtp` map flips when the fetched file lacks it.
