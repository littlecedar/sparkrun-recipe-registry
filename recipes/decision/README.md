# Decision lane

Small models that make classification / routing / judgment calls, co-located with the shipped
embed + rerank pair on **one** DGX Spark (the lane's core constraint: nodes are at a premium).
Full candidate research — both owner leads resolved, 8-model shortlist, co-location budget math —
is in [`DECISION-MODELS-RESEARCH.md`](DECISION-MODELS-RESEARCH.md).

| recipe | runtime | model | status |
|---|---|---|---|
| [`jev-9b-decision-vllm.yaml`](jev-9b-decision-vllm.yaml) | vLLM | [autotrust/JEV-9B][jev] + the `jev-decision` LoRA | **BOOT-VERIFIED 2026-10-11** |
| [`clef-flash-decision-sglang.yaml`](clef-flash-decision-sglang.yaml) | SGLang | [Cloudflare/clef-flash][clef] | drafted; boot pending |

## What these models are

Decision models are **prefill-only scorers**, not chat models. JEV-9B answers with
`logprobs` + `allowed_token_ids` over `/v1/chat/completions` (SystemOne-shaped); clef-flash answers
`choice` / `noul` / `score` questions over `/v1/systemone`. Neither serves text generation as its
product — a chat client that reads `content` will see empty replies when the model puts its answer
in the reasoning channel, which is why the JEV recipe pins `--logprobs-mode processed_logprobs` and
why any quality harness must read the right field.

`clef-flash` therefore ships the pooling-lane readiness (`readiness: inference: false`, port +
`/health` only) and takes port 8020 (embed 8010, rerank 8011).

## Co-location

After the shipped embed (0.25) + rerank (0.30) caps, ~54.5 GiB of the node's 121.69 GiB is free
(Kokoro-82M costs 0.3 GiB of it). Everything on the shortlist through JEV-9B fits; clef-flash at the
vendor's 41 GB needs the embed/rerank caps lowered to ~0.15/0.18 first — a cap-bookkeeping decision,
not a memory wall. Cores: the embed recipe pins 5-9 and the reranker 15-19 (the X925 cluster), so
clef-flash is pinned to 0-4,10-14 (A725) to keep the three from contending.

[jev]: https://huggingface.co/autotrust/JEV-9B
[clef]: https://huggingface.co/Cloudflare/clef-flash