# Decision lane

Small models that make classification / routing / judgment calls, co-located with the shipped
embed + rerank pair on **one** DGX Spark (the lane's core constraint: nodes are at a premium).
Full candidate research — both owner leads resolved, 8-model shortlist, co-location budget math —
is in [`DECISION-MODELS-RESEARCH.md`](DECISION-MODELS-RESEARCH.md).

| recipe | runtime | model | status |
|---|---|---|---|
| [`jev-9b-decision-vllm.yaml`](jev-9b-decision-vllm.yaml) | vLLM | [autotrust/JEV-9B][jev] + the `jev-decision` LoRA | **BOOT-VERIFIED 2026-10-11** |
| [`clef-flash-decision-sglang.yaml`](clef-flash-decision-sglang.yaml) | SGLang | [Cloudflare/clef-flash][clef] | **BOOT-VERIFIED 2026-10-11** |
| [`kai-0.6b-decision-vllm-srun.yaml`](kai-0.6b-decision-vllm-srun.yaml) | vllm-srun (CPU) | [vllm-sr/Decision-2.0-Kai-0.6B][kai] | **BOOT-VERIFIED 2026-10-13** |
| [`sol-2b-decision-vllm-srun.yaml`](sol-2b-decision-vllm-srun.yaml) | vllm-srun (CPU) | [vllm-sr/Decision-2.0-Sol-2B][sol] | **BOOT-VERIFIED 2026-10-13** |

## Verified surfaces (2026-10-11)

- **JEV-9B** — `/v1/models` advertises both `autotrust/JEV-9B` and the `jev-decision` LoRA adapter;
  the scoring path returns processed `top_logprobs` (`--logprobs-mode processed_logprobs` accepted by
  the pinned image). **Constrained scoring VERIFIED 2026-10-11:** top-level `allowed_token_ids` is
  accepted AND enforced on both `/v1/completions` (the card's native shape) and
  `/v1/chat/completions` — non-allowed tokens are masked to logprob −9999. (An earlier note here
  claimed this build rejects the field; that was wrong — the earlier attempt's failure was
  request-shape, not the flag. `extra_body`/`sampling_params` variants are silently ignored:
  vLLM drops unknown JSON fields with a 200.) Five decision questions scored through the card's
  exact recipe — returned option-token logprobs, + per-slot head bias from
  `~/benchmarks/jev-card/adapter_vllm/decision_head.json`, ÷ per-kind temperature from
  `calibration.json`, softmax. **Surface caveat that matters:** the chat-template surface shifts the
  distribution vs the card's raw `/v1/completions` shape (`add_special_tokens=false`) and flipped an
  argmax in our 5-question sample (frontend_css 0.39 chat vs 0.94 completions) — the card's contract
  is the **completions** shape; use it for scoring, not the chat surface.
- **clef-flash** — a real `/v1/systemone` round-trip: `routing` returned
  `choice: technical_support` at 0.957 confidence with calibrated option probabilities
  (`{billing: 0.016, technical_support: 0.971, sales: 0.013}`), and `urgency` returned
  `noul: 0.952` — 249 input tokens, **0 output tokens** (prefill-only scoring, as the vendor
  documents). Receipt: `~/benchmarks/clef_smoke.py` on the head node.
  **Official benchmark (2026-10-11, `tool-eval-bench` v2.8.0 `--decision-bench-only`):**
  **Decision Accuracy 70.3% (1406/2000)** on the Typed Decisions test split — 400 cases / 2000
  questions, 81.5 s, 0 request errors. The tool natively drives `/v1/systemone` (no fallback
  needed); the score compares each predicted distribution against gold. The tool's own rating for
  this run: ★★, above its prior baseline. Note: the vendor's leaderboard is self-reported and
  unreproduced on the community board — this number is OURS. Full report:
  `/tmp/teb-clef/2026/10/2026-10-11T16-09-17.516296Z_88866997.md` on the head node (417 KB, with
  per-question-type tables, calibration, latency and the 400-case trace; copied with the console log
  to `~/benchmarks/teb-clef-durable/` because `/tmp` is reaped).
- **Served-id wart (fixed 2026-10-13):** the arm shipped `--served-model-name {model}`, and
  sparkrun rebinds every `{model}` occurrence to the prepared snapshot path on a real launch
  (`-n` still prints the repo id), so clef-flash advertised
  `/cache/huggingface/hub/models--Cloudflare--clef-flash/snapshots/8b2e5fd1…` as its model id.
  The recipe now declares `served_model_name: Cloudflare/clef-flash` and passes
  `--served-model-name {served_model_name}`; clients use the repo id `Cloudflare/clef-flash`.
  **Receipt**: boot `625b43fd997e4d5b_8ed3ce77d78f` on `.34` — `GET /v1/models` →
  `Cloudflare/clef-flash` (262144 ctx).

## JEV-9B official score (2026-10-12)

**Decision Accuracy 67.0% (1340/2000), ★★** on the Typed Decisions test split
(`tool-eval-bench` v2.8.0's data — 400 cases / 2000 decisions), scored through
`tools/jev-decision-bench.py` over the card's native `/v1/completions`
System 1 contract: **0 request errors**, KL(gold ‖ pred) mean 0.3523 nats,
Brier mean 0.1336, top-label ECE 0.0299, 132 ms median per decision (serial,
one request per question), 561,065 input tokens, 265 s wall. clef-flash
scored 70.3% (★★) on the same data through the tool's own `/v1/systemone`
path — JEV is 3.3 points behind on the shared instrument.

Per kind: `noul` 79.3% (476/600), `choice` 67.2% (403/600), `score` 57.6%
(461/800). Per workflow: agent_trace_observability 51.0%,
customer_service 71.2%, invoice_processing 78.2%, security_incidents 67.6%.
The chat-template surface shifts distributions and flips argmaxes (the
2026-10-11 caveat above); the completions shape is the card's contract and
the only one scored here.

Comparability caveats: same cases, same gold, same metric formulas as
tool-eval-bench v2.8.0, but the request shape differs — one request per
question (JEV's native contract) instead of all five questions of a case in
one `/v1/systemone` request, so per-request latency is not comparable with
clef's; and structured states serialize as sorted-key compact JSON (the
vendor's SystemOne convention; the JEV card documents only string states).
The card-example smoke reproduced before scoring: the card's worked choice
example returned {issue_warning: 0.328, renegotiate: 0.144, dual_source:
0.528, maintain: 0.001} against the card's ≈ {0.33, 0.14, 0.53, 0.001}, and
the noul refund example returned P(true) = 0.991.

Receipts on the head node: `~/benchmarks/jev-decision-20261012/`
(`jev-decision-bench.json` with the per-decision trace + `run.log`).

## vllm-srun arms: Kai-0.6B + Sol-2B (2026-10-12)

The Decision 2.0 models run on the vendor's own runtime, **vllm-srun** — a
standalone single-process server shipped inside the `vllm-sr` router image
(not on PyPI, no image of its own; `vllm-srun models` lists every built-in
model at its golden-checked pinned revision, which is what the recipes pin).
Both recipes serve on **CPU**, pinned to the unclaimed A725 cores
(`taskset -c 0-4,10-14`, mirroring clef-flash): the vendor marks DGX-Spark
arm64 CUDA "experimental, not qualified", and the lane's slot for these is a
decision model at no GPU cost. Recipe notes:

- The image's default ENTRYPOINT starts the vllm-sr router/gateway; the
  recipes clear it (`executor_config.entrypoint: ""`) so the vllm-srun serve
  line runs.
- **The kill-shim prefix.** The image is built on `python:*-slim` and has no
  standalone `kill` binary; sparkrun's detached-launch liveness check runs
  `docker exec <c> kill -0 <serve-pid>`, which exits 127 on this image and
  was misread as "serve process exited immediately" — three consecutive
  launches declared failure while the serve came up healthy seconds later
  (observed 2026-10-13). The recipes therefore prepend a `printf` that
  installs a bash-builtin kill shim into `/usr/local/bin` before the server
  starts, and run the container as root (`executor_config.user: "root"`) so
  the shim can be written. vLLM / SGLang images ship procps and are
  unaffected.
- `--revision=<sha>` uses the runtime's own pinned revisions
  (Kai `cd49ea38…`, Sol `64235bef…`) — the revisions its golden readiness
  check was built against, so they are the strongest (`matched`) readiness
  state. `/health` returns 200 for a served revision that golden-checks
  `unverified` too (readiness gates on `failed`, not on `unverified`); see the
  revision-drift determination below.

**Kai-0.6B boot-verified 2026-10-13** on .34: launch succeeds (TTR port-open
8.1 s, HTTP-ready 10.1 s), `/health` → `{"status":"ready"}` (golden-checked),
`/v1/models` reports the served id, revision and model sha. The Kai card's
three-question example over `/v1/systemone` (damaged-order state) answers
sensibly: `route` → `returns` 0.962, `receipt` → noul 0.916, `urgency` →
score 1.475 ("Today"-leaning), 286 input tokens, 0 output tokens; 0.90 s
round-trip from the head (single request, cold client). Receipts:
`~/benchmarks/kai-sol-20261012/` (`kai-card-smoke.json`; the
tool-eval-bench v2.8.0 `--decision-bench-only` run below — same 400-case /
2000-decision instrument as clef's 70.3%).


**Kai-0.6B official score (2026-10-13, tool-eval-bench v2.8.0
`--decision-bench-only`): Decision Accuracy 47.5% (949/2000), ★★** — just
above the dataset's 47.0% prior that anchors the ★ rating. KL(gold ‖ pred)
0.362, Brier 0.198, ECE 0.061, 0 request errors. Per type: `noul` 62.8%,
`choice` 42.3%, `score` 39.8%. Latency on the A725 CPU pins: p50 5.70 s /
mean 5.25 s per request — one request carries all five questions of a case,
so ≈ 1.05 s per question, against the card's 4.9 ms per question on a GPU
(CPU inference, not a same-hardware comparison). Duration 2100 s, 629,180
input tokens. For scale on the shared instrument: clef-flash 70.3%, JEV-9B
67.0% — Kai-0.6B is 0.6B serving at no GPU cost; its case is the CPU slot,
not accuracy leadership. The score run took ~35 min wall for 2000 decisions:
every case is a serial HTTP round-trip through one CPU process.

**Sol-2B boot-verified 2026-10-13** on .34: launch succeeds first-try with
the kill-shim fix (TTR port-open 7.8 s, HTTP-ready 18.8 s), `/health` →
`{"status":"ready"}`. The Sol card documents the **same** worked example as
the Kai card (no substitution needed) — `/v1/systemone` answers `route` →
`returns` 0.969, `receipt` → noul 0.970, `urgency` → score 1.60, 317 input
tokens, 0 output tokens.

**Sol-2B official score (2026-10-13, same instrument): Decision Accuracy
55.0% (1100/2000), ★★** — KL 0.352, Brier 0.190, ECE 0.058, 0 errors. Per
type: `noul` 65.8%, `choice` 49.5%, `score` 51.0%. Latency on the A725 CPU
pins: p50 15.0 s / mean 14.2 s per request (all five questions of a case) —
≈ 2.8 s per question vs Kai's ≈ 1.05 s; duration 5670 s (94.5 min), 652,665
input tokens. Ladder on the shared instrument: **Sol-2B 55.0% > Kai-0.6B
47.5%**, matching the vendor's own ordering (JevArena 52.1 vs 48.6); both sit
below clef-flash 70.3% and JEV-9B 67.0%, the expected shape for 0.6B/2B
CPU-served models at zero GPU cost.

Receipts on the head: `~/benchmarks/kai-sol-20261012/` — `teb-kai-report.md`
and `teb-sol-report.md` (the full tool-eval-bench reports: per-question
tables, calibration, latency, 400-case trace) plus the two card-smoke JSONs.
Deviation worth recording: `--json-file` produced no file in v2.8.0 for these
runs; the markdown report under `~/runs/2026/10/` is the durable artifact
(copied into the receipts dir) and carries every number quoted here.

**Revision-drift determination (2026-10-14).** Hub `main` moved to
`cc7f30cda9e7…` (Kai) / `df30237f9c1c…` (Sol) — both 2026-10-10 — past the
pinned `cd49ea38…` / `64235bef…`, opening the re-pin question. Inspecting the
runtime in the digest-pinned `vllm-sr` image, **the runtime pins its own
validation revisions, so both recipes are left as-is**:

- `vllm-srun models` lists the built-in table at exactly the recipe pins
  (`Decision-2.0-Kai-0.6B@cd49ea38…`, `Decision-2.0-Sol-2B@64235bef…`).
- The golden *reference answers* are looked up by **content identity** —
  `vllm_srun/registry/builtin.py:golden(model_sha256, …)` goes through
  `by_identity(model_sha256)`, not through a revision — and
  `registry/tables/common.py:with_recorded` attaches `golden_answers.json` /
  `kernel_choices.json` to a built-in entry only when the recorded `revision`
  equals the entry's pin (the recorded Kai/Sol references carry
  `"revision": cd49ea38…` / `64235bef…`).
- `registry/resolve.py:pinned_revision` accepts any 40-hex commit, so a newer
  revision is *served*, not refused — but `families/decision2/family.py` only
  applies its identity-equality guard when `known.revision == package.revision`,
  and `runtime._start` fails the load only on golden status `failed` — not on
  `unverified`. An unrecorded revision therefore reaches readiness with golden
  status **`unverified`**, never `matched`: only the recorded revision's content
  can be golden-vouched. (`/health` stays 200 because readiness gates on
  `failed`, not on `matched`.)
- **The Hub drift is cosmetic.** A pin-vs-`main` diff of every file (LFS oids)
  shows both repos differ by `assets/banner.png` alone — every model file is
  byte-identical, so `main`'s content identity equals the pin's (`bb806f31…`
  Kai / `e20df76c…` Sol). A re-pin would change nothing served, so no re-score
  is warranted.

Evidence (the inspection commands and their output):
`~/benchmarks/decision-revision-20261014/` on the head — `models.txt`,
`golden-probe.txt`, `hub-tree-diff.txt`.

## CPU+GPU tandem probe (2026-10-13)

Can a GPU decision model and a CPU decision model be co-served on one node, and does
pooling their answers beat either alone? Measured on `.34`: clef-flash (SGLang `:8020`) +
Kai-0.6B (vllm-srun CPU `:8000`), the same 400-case / 2000-decision split, `tool-eval-bench`
v2.8.0 `--decision-bench-only`.

**Ensemble rule** (`tools/decision-tandem.py`, stdlib-only, `--selftest`): an equal-weight
**linear mean** of the two models' per-question distributions, renormalised, scored by
`argmax(pooled) == gold label`; a log-linear (geometric-mean / product-of-experts) pool is
recorded beside it.

| scorer | accuracy | KL(gold‖pred) | Brier |
|---|---:|---:|---:|
| clef-flash alone | 70.3% | 0.209 | 0.111 |
| Kai-0.6B alone | 47.5% | 0.362 | 0.198 |
| ensemble (linear mean) | **71.6%** | 0.196 | 0.098 |
| ensemble (log-linear) | 71.3% | 0.168 | 0.086 |

**Verdict: a small, statistically significant gain, and only for the right pairing.** The
linear pool is +1.3 pts over clef alone (McNemar p = 0.012; case-level bootstrap 95% CI
[0.35, 2.20]), concentrated in the `score` kind; the log-linear pool trades ~0.3 pt of
accuracy for a larger calibration gain (KL −20%, Brier −22%). clef + Sol-2B is a small net
loss (69.9%) and a 3-way pool dilutes (69.6%) — Kai is the more complementary partner (argmax
agreement with clef 46.3% vs Sol's 58.7%), so the gain is **model-specific, not a property of
"CPU + GPU"**.

Co-serve is clean (no OOM, both accuracies bit-reproducible) but **asymmetric**: the GPU model
is unaffected (p50 205 → 210 ms, identical 70.3%), while the CPU model slows ~45% under
co-residency (p50 5699 → 8253 ms; 2100 → 3087 s per full bench). An isolation probe (one
3-question request, clef idle) shows Kai's p50 **856 ms → 1800 ms** the moment clef is
*resident*, so the tax is the GPU model's residency, not its traffic. Both serve processes
ship pinned to the *same* `0-4,10-14` cluster (live `taskset -pc`) and clef holds ~90 GiB,
dropping node `available` from 121 → 16 GiB; which of the two dominates is not isolated.

Contract note: clef, Kai, and Sol all answer `/v1/systemone` (all five questions of a case in
one request), so their distributions are directly poolable. JEV-9B is **not** comparable — its
card contract is `/v1/completions`, one request per question, scored by
`tools/jev-decision-bench.py` — and is excluded from the ensemble.

Receipts: `~/benchmarks/decision-tandem-20261013/` (`REPORT.md`, the three run reports, the
launch and TEB logs, `cpu-samples.txt`, the isolation-probe output, the ensemble JSONs).

## What these models are

Decision models are **prefill-only scorers**, not chat models. JEV-9B answers with
`logprobs` + `allowed_token_ids` over `/v1/chat/completions` (SystemOne-shaped); clef-flash answers
`choice` / `noul` / `score` questions over `/v1/systemone`. A chat client that reads `content` sees
an empty reply from both when the answer lives in the reasoning channel.

`clef-flash` ships the pooling-lane readiness (`readiness: inference: false`, port + `/health` only)
and takes port 8020 (embed 8010, rerank 8011).

## Co-location

After the shipped embed (0.25) + rerank (0.30) caps, ~54.5 GiB of the node's 121.69 GiB is free
(Kokoro-82M costs 0.3 GiB of it). Everything on the shortlist through JEV-9B fits; clef-flash at the
vendor's 41 GB needs the embed/rerank caps lowered to ~0.15/0.18 first — a cap-bookkeeping decision,
not a memory wall. Cores: the embed recipe pins 5-9 and the reranker 15-19 (the X925 cluster), so
clef-flash is pinned to 0-4,10-14 (A725) to keep the three from contending.

[jev]: https://huggingface.co/autotrust/JEV-9B
[clef]: https://huggingface.co/Cloudflare/clef-flash
[kai]: https://huggingface.co/vllm-sr/Decision-2.0-Kai-0.6B
[sol]: https://huggingface.co/vllm-sr/Decision-2.0-Sol-2B
