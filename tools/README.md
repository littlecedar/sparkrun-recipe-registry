# tools/

Stopgap measurement tooling for `sparkrun` recipes that the built-in benchmarking path
cannot reach, plus the DeepSeek-V4.1 artifact builders and the one shared module
(`synthetic_png.py`) that the measurement tools import. `safe_text.py` is the safety filter
that has to run *before* anything else here reads a log or a chat template.

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

Three modes, one transform each:

- **escape** (default, read): every non-ASCII codepoint becomes `\uXXXX`/`\UXXXXXXXX`, every
  backslash is doubled, undecodable bytes become `\xNN`. Output is **ASCII-only**, so no input
  can carry the token through it.
- **`--unescape`** (write): the exact inverse, for the callers that need the raw placeholder
  bytes back — a chat template handed to a tokenizer, an HTTP body. Writes are tmp +
  `os.replace`, preserve mode/owner, and replace a symlink rather than following it (writing
  through one would rewrite the node's HF snapshot).
- **`--check`**: reports line:column of every raw token and exits 1; prints the *escaped* form,
  never the token. A missing/unreadable file is exit 2, never "clean". `--check-nonascii` adds
  advisory non-ASCII locations.

```sh
tools/safe_text.py --check ~/.omp/logs/http-400-requests/*.json   # locate, exit 1 on hit
tools/safe_text.py dump.json -o dump.safe.txt                     # ASCII-safe copy
tools/safe_text.py --unescape tpl.safe -o chat_template.jinja     # raw token back
tools/safe_text.py --in-place --unescape tpl.safe                 # rewrite in place
```

Exit codes: `0` clean, `1` `--check` found a raw token, `2` the tool could not run. The escape
is the one trusted boundary: `escape()` asserts its own ASCII-only output, `unescape()` raises
on any backslash it did not emit *and* on non-ASCII input (which proves the caller is holding a
raw file), and both are covered by `tests/test_safe_text.py` (30 tests, including negative
controls proving the detector ignores ASCII-bar lookalikes and that `escape()` is not an
identity). Verified end-to-end on the real 400-dump artifact: 191427 bytes → 196412 ASCII
bytes → byte-identical unescape (sha256 match).

**Escaped at rest, raw at the call site.** A template that must *contain* the placeholder —
a VL request body, a tokenizer fixture, a chat template the campaign launches compare — is
stored escaped and unescaped only where it is used: `save_template(path, text)` /
`load_template(path)` in the module, or `--unescape` on the CLI. That keeps every checkout of
this tree free of the literal token (guarded by the test above) while the request still
carries the real bytes. Importable API: `raw_token`, `escaped_token`, `escape`, `unescape`,
`escape_bytes`, `unescape_bytes`, `save_template`, `load_template`, `find_raw_token`,
`contains_raw_token`, `non_ascii_spans`, `scan_text`, `scan_file`.

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
so **peak RSS measured ~0.6 GiB** while writing 94 GiB (verified on `.34`, 2026-10-06). One
ranged request per 256 MiB segment also keeps the request count low enough to avoid HF's
`429`; one request per chunk does not (observed at ~12k requests on a full table).

**Output layout.** `--format safetensors` (default) writes `engram-l<L>.safetensors`, one per
layer, each with that layer's `.engram.embed.weight` and `.engram.embed.scale` as two
contiguous planes. This is exactly what TensorFold's `Engram` reader expects: it globs
`*.safetensors` in `TF_DS_ENGRAM` and reads row `i` at
`8 + header_len + data_offsets[0] + i * prod(shape[1:])`. `--format packed` writes the
knapcio TP=4 layout (magic `DSV1EN41`, 4096-B header, 264-B records). Both are resumable.

**Wiring.** The recipe adds `mods/dsv41-engram-fetch`, which runs this builder on each
runner node before the launcher. It is a no-op once the tables are complete, and it
**always fetches detached** — sparkrun runs a mod as a pre-exec hook under a hard
600 s timeout, and a slow-link fetch can take hours, so a blocking fetch is a
launch-killing risk (observed). For a fresh deployment the honest path is to
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
`<model_dir>/engram/`, making `model: <this repo>` sufficient.

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
[2026-10-03 20:04:44] [nh] endpoint http://10.0.4.30:8000, model deepseek-ai/DeepSeek-V4.1-Flash
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

- It reads `max_model_len` from `/v1/models` and **never builds a prompt longer
  than the server advertises**, leaving a 2 % headroom. Filling exactly the
  window is not possible — a request for 1,048,576 tokens always arrives a little
  over and is rejected — so the deepest depth serves ~1.03–1.07M tokens.
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

## qwen4-quality-eval.py

`recipes/qwen4/` ships two checkpoints for the same base model: the reference
`RadixArk/Qwen3.8-Flash-Next-NVFP4` and the locally-quantised
`local-inference-lab/Qwen3.8-Flash-Next-NVFP4` (the "labquant" export). Labquant quantises
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
