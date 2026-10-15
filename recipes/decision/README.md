# Decision lane

Small models that make classification / routing / judgment calls — **prefill-only scorers, not
chat models** — co-located with the shipped embed + rerank pair on **one** DGX Spark (the lane's
core constraint: nodes are at a premium). This README covers the four shipped recipes. The
candidate research, verified surfaces, official scores, the CPU+GPU tandem probe and the
revision-drift determination are archived under [`attic/decision/`](../../attic/decision/)
(indexed at the end).

## Contents

- [jev-9b-decision-vllm](#jev-9b-decision-vllm)
- [clef-flash-decision-sglang](#clef-flash-decision-sglang)
- [kai-0.6b-decision-vllm-srun](#kai-06b-decision-vllm-srun)
- [sol-2b-decision-vllm-srun](#sol-2b-decision-vllm-srun)
- [Operating constraints](#operating-constraints)
  - [The `vllm-srun` runtime (Kai + Sol)](#the-vllm-srun-runtime-kai--sol)
  - [Served-id caveat](#served-id-caveat)
  - [Co-location budget](#co-location-budget)
- [The clef + Kai ensemble](#the-clef--kai-ensemble)
- [A `req/s` ladder, not a `t/s` ladder](#a-reqs-ladder-not-a-ts-ladder)
- [Attic index](#attic-index)

Accuracy on the shared instrument (`tool-eval-bench` v2.8.0, Typed Decisions test split — 400
cases / 2000 decisions): **clef-flash 70.3% > JEV-9B 67.0% > Sol-2B 55.0% > Kai-0.6B 47.5%**.

Two measurements sit outside that ranking and have their own sections below: the lane's
accuracy record is **not** clef-flash alone but the **clef + Kai ensemble at 71.6%** (pooling
the two arms' per-question distributions — [§The clef + Kai
ensemble](#the-clef--kai-ensemble)), and the index's C-columns for this lane are `req/s`
ladders, not decode `t/s` ([§A `req/s` ladder, not a `t/s`
ladder](#a-reqs-ladder-not-a-ts-ladder)).

### jev-9b-decision-vllm

| field | value |
|---|---|
| repo id | [`autotrust/JEV-9B`][jev] (pinned `7ac669b8`), + the `jev-decision` LoRA (rank 32); Apache-2.0 |
| accuracy | **67.0%** (1340/2000), ★★ |
| size | 18 GB (bf16 9B + 173 MB LoRA); ~17 GiB weights |
| API | `/v1/completions` — the card's native SystemOne scoring shape (`logprobs` + top-level `allowed_token_ids`); the server runs `--logprobs-mode processed_logprobs --enable-lora`. The chat-template surface shifts the distribution and can flip argmaxes, so score on completions, not chat. |
| TP | 1 |
| flags | 🤏 smol · 🚮 classifier |
| status | **BOOT-VERIFIED 2026-10-11** (`.34`) |

`max_model_len` ships at 4096 (card-sized for decisions); raise it to 16384 only if System 2 thinking
at length is needed (the card's own note).

### clef-flash-decision-sglang

| field | value |
|---|---|
| repo id | [`Cloudflare/clef-flash`][clef] (pinned `8b2e5fd1`) |
| accuracy | **70.3%** (1406/2000), ★★ — the lane's accuracy leader |
| size | 19 GB (4 shards 18.82 GB + `joint_head` 0.244 GB); vendor 41 GB VRAM at 64k ctx |
| API | `/v1/systemone` (choice / noul / score, calibrated probabilities, no text generation; multimodal text/JSON/images/video). No chat endpoint → `readiness: inference: false`, port + `/health` only (port 8020; embed 8010, rerank 8011). |
| TP | 1 |
| flags | 🤏 smol · 🚮 classifier |
| status | **BOOT-VERIFIED 2026-10-11** |

### kai-0.6b-decision-vllm-srun

| field | value |
|---|---|
| repo id | [`vllm-sr/Decision-2.0-Kai-0.6B`][kai] (0.60B Qwen3-0.6B-Base fine-tune, 8192 ctx; pinned `cd49ea38`) |
| accuracy | **47.5%** (949/2000), ★★ |
| size | 2 GB (1.503 GB + head) |
| API | `/v1/systemone` (and the `/v1/decisions` superset), **CPU** |
| TP | 1 |
| flags | 🤏 smol · 🖥 cpu · 🚮 classifier |
| status | **BOOT-VERIFIED 2026-10-13** |

### sol-2b-decision-vllm-srun

| field | value |
|---|---|
| repo id | [`vllm-sr/Decision-2.0-Sol-2B`][sol] (1.88B, 16384 ctx; pinned `64235bef`) |
| accuracy | **55.0%** (1100/2000), ★★ |
| size | 5 GB (3.02 + 1.76 GB + head) |
| API | `/v1/systemone`, **CPU** |
| TP | 1 |
| flags | 🤏 smol · 🖥 cpu · 🚮 classifier |
| status | **BOOT-VERIFIED 2026-10-13** |

## Operating constraints

### The `vllm-srun` runtime (Kai + Sol)

The Decision 2.0 models run on the vendor's own runtime, **`vllm-srun`** — a standalone
single-process server (`vllm_srun.cli:main`, `src/model-runtime` in the vendor's
`semantic-router` repo) shipped inside the `vllm-sr` router image (not on PyPI, no image of its
own; `vllm-srun models` lists every built-in model at its golden-checked pinned revision). Both
recipes declare `runtime: vllm` (the family whose distribution + launcher contract the command
satisfies) and clear the image's default router/gateway ENTRYPOINT
(`executor_config.entrypoint: ""`) so the serve line runs. They serve on **CPU**, pinned to the
unclaimed A725 cores (`taskset -c 0-4,10-14`, mirroring clef-flash), because the vendor marks
DGX-Spark arm64 CUDA "experimental, not qualified" — so the lane's slot for these is a decision
model at no GPU cost. `--revision=` uses the runtime's own pinned revisions (Kai `cd49ea38…`,
Sol `64235bef…`), the ones its golden readiness check is built against; `/health` gates on that
check (not plain liveness), hence the long readiness timeouts. The image is built on
`python:*-slim` and ships no standalone `kill` binary, which breaks sparkrun's detached-launch
liveness check (`docker exec <c> kill -0` exits 127 and is misread as "serve process exited");
both recipes prepend a bash-builtin `kill` shim and run as root so the shim can be written.
(vLLM / SGLang images ship procps and are unaffected.)

### Served-id caveat

sparkrun rebinds every `{model}` occurrence to the prepared snapshot path on a real launch (`-n`
still prints the repo id), so an arm that shipped `--served-model-name {model}` advertised the
cache path as its model id. clef-flash declares `served_model_name: Cloudflare/clef-flash` and
passes `--served-model-name {served_model_name}` (fixed 2026-10-13); the vllm-srun recipes pass
the repo id literally. Clients use the repo id.

### Co-location budget

Co-location with the shipped embed + rerank 2B pair (and eventually TTS) on ONE GB10 node is the
lane's core constraint. After the embed (0.25) + rerank (0.30) caps, ~54.5 GiB of the node's
121.69 GiB is free (Kokoro-82M costs 0.3 GiB of it) — everything here through JEV-9B fits;
clef-flash at the vendor's 41 GB needs the embed/rerank caps lowered to ~0.15/0.18 first, a
cap-bookkeeping decision rather than a memory wall. Cores: embed pins 5-9 and rerank 15-19 (the
X925 cluster), so clef-flash (and the CPU Decision 2.0 arms) pin 0-4,10-14 (A725) to keep the
tenants from contending.

## The clef + Kai ensemble

Co-serving the lane's accuracy leader with its smallest CPU arm and **pooling their answers**
lifts accuracy a little, and the gain is reproducible across sessions, not a one-off analysis.
The rule is an equal-weight **linear mean** of the two models' per-question distributions,
renormalised, scored by `argmax(pooled) == gold` — a client-side rule, not a different server.

| scorer | accuracy | KL(gold‖pred) | Brier |
|---|---:|---:|---:|
| clef-flash alone (GPU) | 70.3% (1406/2000) | 0.209 | 0.111 |
| Kai-0.6B alone (CPU) | 47.5% (950/2000) | 0.362 | 0.198 |
| **ensemble (linear mean)** | **71.6% (1432/2000)** | 0.196 | 0.098 |
| ensemble (log-linear) | 71.3% (1427/2000) | 0.168 | 0.086 |

Ensemble vs clef alone: **+63 / −37 discordant decisions, exact two-sided McNemar p = 0.012**
(small but real; the 2026-10-13 probe put a case-level bootstrap 95% CI of **[0.35, 2.20]** on
the +1.3 pt delta, and this run repeats the same discordant split exactly). The gain is
concentrated in the `score` kind (+2.6 pts). The log-linear (geometric-mean) pool trades ~0.3 pt
of accuracy for a larger calibration gain (KL −20%, Brier −22% vs clef alone).

Per kind (noul 600 / choice 600 / score 800): clef 81.5 / 70.3 / 61.9, Kai 62.8 / 42.5 / 39.8,
ensemble-linear 81.8 / 70.8 / 64.5.

*Measured 2026-10-15 on `.34`, both arms booted fresh for this run — the table is that run.* It
reproduces the 2026-10-13 probe's headline exactly (71.6%, +63/−37, p = 0.012): clef's own
report is identical decision-for-decision (1406/2000) and the ensemble's is too (1432/2000),
while **Kai's differs by one decision** (950 vs 949/2000; its `choice` kind 42.5% vs 42.3%) —
the same ±1–3-decision variance that batch composition produces elsewhere in this lane (the
C2/C5/C10 passes below swing 1404–1407/2000), not a configuration difference. The gain is
**pairing-specific**: clef + Sol-2B is a net loss (69.9%) and a 3-way pool dilutes (69.6%) —
Kai is the more complementary partner (argmax agreement with clef 46.3% vs Sol's 58.7%), so
this is not a property of "GPU + CPU" as such.*

### Reproduce it

Two boots, two instrument passes, one pooling command — nothing hidden:

```bash
sparkrun run recipes/decision/clef-flash-decision-sglang.yaml -H <node>        # GPU arm, :8020
sparkrun run recipes/decision/kai-0.6b-decision-vllm-srun.yaml -H <node>       # CPU arm, :8000
uvx tool-eval-bench@2.8.0 --base-url http://<node>:8020 --decision-bench-only  # -> report A (82 s on a GB10)
uvx tool-eval-bench@2.8.0 --base-url http://<node>:8000 --decision-bench-only  # -> report B (~35 min, CPU)
python3 tools/decision-tandem.py <report A> <report B> --a-name clef --b-name kai
```

`decision-tandem.py` parses each report's `### Full Trace` section (the durable artifact the
instrument writes), pools the per-question distributions and prints the table above with its
McNemar test; `--json` writes the machine-readable result. Both arms must speak
`/v1/systemone` so their option spaces match — JEV-9B does not (one `/v1/completions` request
per question) and is not poolable, which is why it is absent here.

Or **serve** the ensemble as one endpoint and let the instrument score it in a single pass:

```bash
python3 tools/decision-ensemble.py --a http://<node>:8020 --b http://<node>:8000 \
    --a-model Cloudflare/clef-flash --b-model vllm-sr/Decision-2.0-Kai-0.6B --port 8021
uvx tool-eval-bench@2.8.0 --base-url http://<node>:8021 --decision-bench-only
```

The proxy is the reference implementation of the rule for a client that would rather not
implement it (mean-then-argmax vs argmax-then-vote, tie-breaks and dropped labels are all ways
to get a different number from the same two models): it imports `decision-tandem.py`'s
`linear` / `normalise` / `argmax`, so the served ensemble and the analysed ensemble cannot
drift apart, and it answers the same wire shape both members answer. A member that is down is
a 502 (`/health` 503), never a silenced half-answer. It also advertises **one** model id
(`/v1/models`): a merged list from both members reads as an ambiguous choice to a
model-auto-detecting client, and an interactive client (tool-eval-bench v2.8.0) will sit in a
`Select model [1-2]:` prompt instead of running.

Its **rate is the pool's, not a member's**: a pooled request costs `max(member)` latency, so
the served ensemble runs at the CPU arm's pace — 0.192 req/s, p50 5.2 s on a 20-case prefix at
c1, measured 2026-10-15 behind Kai — where clef alone serves 4.9 req/s. The ensemble buys
accuracy, not speed (and the ladder numbers in the next section are per-arm, booted solo;
they are not the ensemble's).

The served end-to-end pass (2026-10-15, full 400 cases through `:8021` with both members
co-resident) scores **71.7% (1433/2000)** — one decision above the offline pooled 71.6%,
because one pooled question is an exact tie (`security_incidents_000055` severity, 0.28/0.28)
and the instrument breaks ties by first-listed option where `decision-tandem.py` breaks by
greater label. Served and offline otherwise agree on the argmax label at 1999/2000 and on the
distributions to ≤ 5·10⁻⁴ (`logs/proxy-teb-r2.log`, `reports/ensemble-served-c1.md`; a
15-question spot-check against the two members' own live answers is `0` mismatches in
`logs/proxy-correctness.log`).

**Why there is no ensemble recipe, and no `benchmarking/` profile.** A `sparkrun` recipe serves
**one** model per launch (`model:` + one `command:`; a recipe's `containers:` key is its image
*staging* list, not a serve composition), so a two-model ensemble has no recipe shape — the
lane's pair already ships as the two recipes above and the ensemble is the client rule plus the
proxy. A benchmarking profile cannot carry it either: both registered frameworks drive
`/chat/completions`, and a profile naming this lane's real instrument
(`args: {ref: v2.8.0, decision_bench_only: true}`) is *refused before the run starts* —
verified 2026-10-15, `sparkrun benchmark tools <recipe> --profile <that profile> -n` →
`BenchmarkError: tool-eval-bench modes do not provide scheduled JSON artifacts` (the plugin's
`_NO_ARTIFACT_MODES`; log: `logs/profile-refusal.log` in the receipt below). Reproducing this
lane is therefore the command block above plus the two tools, not a profile file.

Receipts (2026-10-15, `.34`): `~/benchmarks/decision-ensemble-20261015/` —
`reports/clef-alone-c1.md` and `reports/kai-alone-c1.md` (the two `### Full Trace` reports),
`ensemble.json` (the pooling result), `logs/ensemble-pool.log`, `logs/kai-teb-c1.log`, the
launch logs, and `runbooks/` (the three measurement scripts as run). The 2026-10-13 probe's
report, pairing study and co-serve contention finding are archived in
[`attic/decision/AGENTS.md`](../../attic/decision/AGENTS.md) §"CPU+GPU tandem probe
(2026-10-13)", receipts `~/benchmarks/decision-tandem-20261013/`.

## A `req/s` ladder, not a `t/s` ladder

The registry index's C1/C2/C5/C10 columns are decode `t/s`. **No arm in this lane has a decode
rate to report** — a decision model answers a prefill-only `/v1/systemone` (or
`/v1/completions`) request and emits no tokens — which is why the index's decision table heads
those columns `req/s`. Read that unit against the arm's own request shape: a "req" is one
`/v1/systemone` **case** (all five questions in one forward pass) for clef/Kai/Sol, and one
`/v1/completions` **question** for JEV-9B. The granularities are not interchangeable: clef's
C1 of 4.9 req/s is 24.5 decisions/s, while JEV's 7.6 req/s is 7.6 decisions/s.

The instrument's own concurrency knob (`--decision-bench-only --parallel N`: the same 400-case
pass with N requests in flight) and this repo's `tools/decision-ladder.py` (replaying the
vendored split) agree within 1% at every level on clef, so the shape below is not a harness
artifact:

| arm / measurement | c1 | c2 | c5 | c10 |
|---|---:|---:|---:|---:|
| clef-flash (GPU) — `req/s`, full 400-case split, instrument | 4.87 | 5.10 | 5.16 | 5.48 |
| clef-flash (GPU) — `req/s`, stride-4 slice (100 cases), harness | 4.89 | 5.11 | 5.16 | 5.51 |
| clef-flash (GPU) — p50 per request, instrument | 206 ms | 393 ms | 966 ms | 1823 ms |
| Kai-0.6B (CPU) — `req/s`, stride-4 slice, harness | 0.187 | 0.186 | 0.156 | 0.128 |
| Kai-0.6B (CPU) — p50 per request, harness | 5.70 s | 11.6 s | 30.5 s | 82.1 s |

**Both arms are serial, and the CPU arm is worse than serial under load.** clef gains 13% of
throughput at 10× concurrency while its per-request p50 inflates 8.8×: the extra requests
queue, they do not batch (each case is ~870 input tokens on the `/v1/systemone` path, not the
generation path). Kai *loses* 32% of throughput at c10 while its p50 inflates 14×: on five
pinned A725 cores, offered concurrency buys nothing and costs latency. Whether the GPU arm's
serialization is a scheduler limit, a lock inside the joint schema head, or a
`max_running_requests`-style default **is not isolated here** — what is measured is that it
does not scale.

That is the honest close for this lane's C2/C5/C10 cells: the ladder exists and is
flat-to-negative, so the columns can carry the measured `req/s` above (with the unit and the
flatness stated) or stay `—` — but a `t/s`-shaped number here would be a category error.
Sol-2B and JEV-9B are not ladded (Sol is the same `vllm-srun` CPU shape as Kai; JEV's
one-request-per-question contract needs a different harness), so their cells stay `—`.

Ladders taken 2026-10-15 on `.34` with the arms booted solo, each level a closed-loop pass
(offer N, count completions):

```bash
# this repo's harness (any /v1/systemone arm); --model is required by the servers
python3 tools/decision-ladder.py --base-url http://<node>:8020 --model Cloudflare/clef-flash \
    --cases <vendored test split>.jsonl --concurrency 1,2,5,10 --json ladder.json
# or the instrument's own knob, on the same 400-case pass the scores come from:
uvx tool-eval-bench@2.8.0 --base-url http://<node>:8020 --decision-bench-only --parallel 10
```

The case file is the instrument's *own* vendored split — `tool_eval_bench/plugins/decision/
vendor/typed_decisions/test.jsonl.gz` in its uvx cache, `gzip -dc`'d to jsonl — and the
extracted file's sha256 is `78a228c8…`, exactly the `jsonl_sha256` recorded in that vendor
directory's `manifest.json`, so a replay is provably the same 400 cases the scores are taken
on (the receipt keeps the file beside `cases/SHA256SUMS`).

clef is ladded on both the full split and the stride-4 slice — the slice is 25 cases from each
of the four workflows, chosen because Kai cannot afford 4 × 400 requests at 5.7 s each — and
the two agree (harness c1: 4.84 req/s on the full 400 cases vs 4.89 on the slice; the
instrument's own full-split pass: 4.87), so the slice is representative. Receipts:
`~/benchmarks/decision-ensemble-20261015/` (`ladder-clef-stride4.json`,
`ladder-clef-full-c1.json`, `ladder-kai-stride4.json`, `logs/clef-teb-c*.log`,
`logs/kai-ladder-stride4.log`, `cases/SHA256SUMS`).

## Attic index

Files under [`attic/decision/`](../../attic/decision/):
| file | what it holds |
|---|---|
| [`DECISION-MODELS-RESEARCH.md`](../../attic/decision/DECISION-MODELS-RESEARCH.md) | The 2026-10-11 read-only candidate research: both owner leads resolved, the 8-model shortlist, the one-node co-location budget math, the recommended first recipes, and the cross-cutting facts the recipes must handle. |
| [`AGENTS.md`](../../attic/decision/AGENTS.md) | Archived lane notes moved out of this README (2026-10-14): the verified surfaces, the JEV-9B and clef-flash official scores, the Kai/Sol `vllm-srun` arms record, the CPU+GPU tandem probe, "what these models are", and the archive of `#` comments removed from the recipes. Extended 2026-10-15 with §"Ensemble productized, and the req/s ladder": the fresh-boot reproduction, the served-ensemble proxy, the ladder numbers, the profile-refusal mechanism and the re-pull cost. |

[jev]: https://huggingface.co/autotrust/JEV-9B
[clef]: https://huggingface.co/Cloudflare/clef-flash
[kai]: https://huggingface.co/vllm-sr/Decision-2.0-Kai-0.6B
[sol]: https://huggingface.co/vllm-sr/Decision-2.0-Sol-2B
