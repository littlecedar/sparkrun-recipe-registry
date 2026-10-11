# Decision lane

Small models that make classification / routing / judgment calls, co-located with the shipped
embed + rerank pair on **one** DGX Spark (the lane's core constraint: nodes are at a premium).
Full candidate research — both owner leads resolved, 8-model shortlist, co-location budget math —
is in [`DECISION-MODELS-RESEARCH.md`](DECISION-MODELS-RESEARCH.md).

| recipe | runtime | model | status |
|---|---|---|---|
| [`jev-9b-decision-vllm.yaml`](jev-9b-decision-vllm.yaml) | vLLM | [autotrust/JEV-9B][jev] + the `jev-decision` LoRA | **BOOT-VERIFIED 2026-10-11** |
| [`clef-flash-decision-sglang.yaml`](clef-flash-decision-sglang.yaml) | SGLang | [Cloudflare/clef-flash][clef] | **BOOT-VERIFIED 2026-10-11** |

## Verified surfaces (2026-10-11)

- **JEV-9B** — `/v1/models` advertises both `autotrust/JEV-9B` and the `jev-decision` LoRA adapter;
  the scoring path returns processed `top_logprobs` (`--logprobs-mode processed_logprobs` accepted by
  the pinned image).
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
- **Served-id wart:** SGLang in this image carries no `--served-model-name`, so clef-flash
  advertises its **snapshot path** as the model id
  (`/cache/huggingface/hub/models--Cloudflare--clef-flash/snapshots/8b2e5fd1…`), not
  `Cloudflare/clef-flash`. Clients must pass the path or route through an alias layer — the same
  sparkrun `{model}`-to-path substitution the other lanes document.

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
