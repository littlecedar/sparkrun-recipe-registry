# DeepSeek V4.1-Flash on DGX Spark — `ds4`

DeepSeek-V4.1-Flash served on four NVIDIA DGX Spark (GB10) nodes with SGLang.
This is the chosen, go-live recipe for the model; the earlier vLLM/EXL3 lane has
been retired to `attic/ds4/` (see [Retired material](#retired-material)).

| | |
|:--|:--|
| Recipe | `deepseek-v4.1-flash-knapcio-tp4-1m-sglang.yaml` |
| Engine | SGLang |
| Model | [`deepseek-ai/DeepSeek-V4.1-Flash`](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash) (native MXFP4/F8, official weights) |
| Nodes | 4 (TP=4, one GB10 per node, EP=1) |
| Context | 1,048,576 tokens (served) |
| Spec decode | DSpark, verify-all |
| Transport | RoCEnante RDMA (shipped on) |
| Image | `littlecedar/dgx-spark-dsv41:canary-roce@sha256:4e5002ab…` (vendored, digest-pinned) |
| Measured | C1 46.5 / C4 106 / C8 133 / C16 193 t/s aggregate (short-prompt harness) |

## What this is

A per-node-Engram design: the model's two 203 GB Engram tables cannot live in
the 128 GB unified memory of a Spark, so they are packed to node-local NVMe and
read on demand. The engine, its kernels, and the reader all come from the
vendored image; this repository supplies only the recipe and the pre-launch mod
(`mods/dsv41-sglang-overlay/`).

Provenance: this lane adapts
[`knapcio/DeepSeek-V4.1-Flash-4x-DGX-Spark-TP4`](https://github.com/knapcio/DeepSeek-V4.1-Flash-4x-DGX-Spark-TP4)
(a downstream of MiaAI-Lab's recipe) onto sparkrun. The launcher, adapters, b12x
kernels, and measurement design are upstream's, kept under their licences.
For provenance, boot gates, and limits in full, see [`AGENTS.md`](AGENTS.md) in
this directory (the archived analysis behind this lane is in
[`attic/ds4/`](../../attic/ds4/)).

## Requirements

- **Four DGX Spark GB10 nodes**, all idle. Tensor parallelism is one node per
  rank, so TP=4 needs four nodes.
- **The official checkpoint in each node's own Hugging Face cache.** The cache
  is per-node (there is no shared export), and sparkrun distributes the model to
  every runner node. Expect ~510 GB per node.
- **The image**, pulled from Docker Hub by sparkrun under its default
  distribution config. No local build is required.
- **~47 GiB of node-local disk per node** for the packed Engram shards. The
  launcher packs them automatically on first boot (detached), so normally you do
  nothing. To pre-warm or debug by hand, run this inside the serving image on
  each node, with `<R>` the node rank (`0`…`3`) and against the snapshot the
  cache actually serves (`refs/main`):

  ```bash
  python3 /opt/dsv41/scripts/pack_engram.py \
    --model /cache/huggingface/hub/models--deepseek-ai--DeepSeek-V4.1-Flash/snapshots/$(cat /cache/huggingface/hub/models--deepseek-ai--DeepSeek-V4.1-Flash/refs/main) \
    --rank <R> --tp 4 --out /cache/runtime/engram
  ```

No host bind mounts are used. Every non-model, non-image artifact (Engram
shards, boot state, JIT caches) lives under sparkrun's managed runtime cache,
mounted at `/cache/runtime`.

## Run it

```bash
sparkrun run recipes/ds4/deepseek-v4.1-flash-knapcio-tp4-1m-sglang.yaml
````

Or if you want to specify the nodes:

```bash
sparkrun run recipes/ds4/deepseek-v4.1-flash-knapcio-tp4-1m-sglang.yaml \
  -H <node1>,<node2>,<node3>,<node4>
```

## What a healthy boot looks like

Boot to ready is **~9 minutes cold** (a first cold boot additionally packs the
Engram in the background and serves from the checkpoint; the next boot uses the
packed shards). The server is up when these appear in the serve log, in order:

1. `[dsv41-sglang-overlay] overlay gate OK`, and a launcher line naming
   `NNODES=4 NODE_RANK=<r>` — **the rank must differ per node**.
2. `Exact nvme Engram layer=… rows=[a,b)` — the row range must **differ per
   rank**; identical ranges mean the staging is wrong.
3. `[moe_b12x_next] armed` — the routed MoE is on the b12x_next kernel, not a
   Triton fallback.
4. `DSV4 memory calculation: … full_token=<N>` — the granted KV pool.
5. `Mean acceptance length > 1` on `Decode batch` lines — DSpark is working. A
   boot that serves but accepts nothing is a failure, not a win.

## Measured performance

Two harnesses were used. The short-prompt harness uses ~17-token prompts and is what the `C1 t/s` column in the repository table refers to; the standardized `sparkrun benchmark` profile uses 2048-token prompts and is the auditable cross-check.

| t/s (aggregate decode)                                              |       C1 |      C4 |      C8 |     C16 |
|:--------------------------------------------------------------------|---------:|--------:|--------:|--------:|
| short-prompt harness (shipped config)                               | **46.5** | **106** | **133** | **193** |
| standardized profile (`benchmarking/ds4-sglang-depth0-ladder.yaml`) |     43.6 |    91.3 |    99.4 |   102.1 |
| same lane, NCCL only (RoCEnante off; not shipped)                   |     27.4 |    62.5 |    73.2 |   155.0 |

RoCEnante is the single largest lever measured on this lane (1.70×/1.69×/1.81×/
1.23× over NCCL), far outside the 7–25% GB10 boot-to-boot spread. It is shipped
on; rollback is one line in the launcher (`SGLANG_ROCE_ALLREDUCE=0`).

Quality: the release checkpoint scores **17/18 (94.4%)** on this project's hard
18-task tier, the same score and the same single failure as the retired EXL3
lane — so the EXL3 quantization cost nothing measurable, and that one failure is
a base-model limitation. The comparator runs the release checkpoint on the same
hard tier and returns the same score and the same single failure (character
reversal of an uncommon word); the one failure is a base-model limit, not
quantization damage.

## Caveats & Limitations with Explanations

> **Scope:** everything in this section describes the **knapcio TP=4 SGLang lane**
> (`deepseek-v4.1-flash-knapcio-tp4-1m-sglang.yaml`, SGLang + `dsv41-sglang-overlay`). It does
> **not** apply to the TensorFold TP=2 lane further down — a different engine with a different KV
> model (`--context` is a single shared pool there; see §"Context window and concurrency"). The
> numbers below are the knapcio lane's, and several come from upstream.

### 1M Context

A `context_length` of 1,048,576 tokens is configured, served, and needle-tested. However, hardware memory boundaries and prefill compute impose real operational constraints.

#### Memory Residency and Concurrency Limits

* **KV Pool Capacity:** In the 128 GB unified memory architecture across four DGX Spark nodes (TP=4), the granted KV cache pool fits approximately 7.5M tokens total.
* **Concurrent 1M Streams:** At maximum context length (1,048,576 tokens per stream), the KV pool accommodates approximately ~6.6 full-length concurrent requests before exhausting memory and queuing.

#### Cold Prefill Latency vs. Cache Hits

* **Cold Prefill Computation:** Ingesting a cold, un-cached 1M-token prompt takes approximately 6.5 minutes of compute on this cluster.
* **Warm / Reused Context:** Leveraging prefix KV caching avoids recomputing full-context attention. Re-running queries against an existing cached context executes near instantaneously.

#### Workload Recommendations

* **Agentic & Conversational Workflows:** Highly recommended for multi-turn conversations, agentic workflows, and document analysis where large prompt prefixes (such as codebases or knowledge bases) remain cached across interactions.
* **Stateless Cold Batches:** Avoid high concurrency of simultaneous cold 1M-token inputs without shared prefixes, as queued prefill latency will accumulate.

### Prompt-token logprobs are unavailable
...and late layers run only over the last 128 rows of a prefill (`--enable-decoder-swa-bounded-replay`); such requests return HTTP 400. Output logprobs and cache hits work. Greedy text is deterministic run to run, so an exact-match task battery is comparable, but a bitwise comparison against the release checkpoint is not available here.

#### Inability to Return Prompt-Token Logprobs (`HTTP 400`)

* **What it means:** When client requests ask for log probabilities of the input prompt tokens (e.g., via `echo: true` or `prompt_logprobs` parameters in OpenAI-compatible/SGLang APIs), the server cannot compute them and explicitly rejects the request with an `HTTP 400 Bad Request` status code.
* **Why it happens:** Calculating log probabilities across the prompt requires full forward-pass activations and output logits for every prompt token position. Because of the bounded replay optimization described below, those intermediate states are not fully computed for early prompt tokens.

#### Prefill Optimization via `--enable-decoder-swa-bounded-replay`

* **Mechanism:** SWA stands for **Sliding Window Attention**. With `--enable-decoder-swa-bounded-replay` enabled, the engine applies an aggressive prefill-phase optimization where later decoder layers process only the tail end (the last 128 rows/tokens) of the prefill sequence rather than running full attention across the entire prompt context.
* **Impact:** This significantly cuts down computation and memory bandwidth during cold prompt ingestion (prefill), which is critical for long contexts (e.g., up to 1M tokens).

#### Output Logprobs and Prompt Caching Still Function

* **Output Logprobs:** During autoregressive generation (decoding steps), token generation occurs token-by-token at the sequence boundary, meaning standard output log probabilities for generated tokens are fully supported.
* **Cache Hits:** The KV cache prefix structures remain valid for prefix caching and reuse across subsequent requests.

#### Deterministic Evaluation vs. Bitwise Checkpoint Parity

* **Exact-Match Task Battery:** Setting `temperature=0` (greedy decoding) generates deterministic output strings across repeated runs on this serving configuration. As a result, functional evaluation benchmarks (such as accuracy on question-answering, code generation, or math test batteries) can be reliably evaluated and compared.
* **Lack of Bitwise Parity:** Because late layers only attend to the last 128 rows during prefill, the resulting hidden states and logits deviate numerically from standard, full-sequence prefill execution. Consequently, outputs will not be bit-for-bit identical to outputs produced by reference release checkpoints running with baseline unconstrained prefill.

**Summary Table**

| Feature / Behavior | Status / Consequence | Explanation |
| :--- | :--- | :--- |
| **Prompt-token logprobs** | **Unavailable (`HTTP 400`)** | Intermediate logits for full prompt tokens are not computed. |
| **Output-token logprobs** | **Available** | Generated tokens compute full logits during decoding. |
| **Prefill speed / throughput** | **Accelerated** | Late layers only compute the last 128 tokens of the prompt. |
| **Prompt cache hits** | **Supported** | Prefix KV caching operates normally. |
| **Greedy reproducibility** | **Deterministic** | Output is repeatable across runs on the same configuration. |
| **Bitwise reference parity** | **Not available** | Numerical results differ from standard baseline prefill runs. |


### Fast loader disabled to reclaim 3–13% KV pool

Upstream's eager safetensors loader (`DSV41_FAST_LOAD=1`) accelerates startup at the cost of reducing the available runtime KV cache capacity. This recipe disables the fast loader to reclaim the KV pool at the cost of ~220s additional startup time.

#### Mechanism and Memory Impact

* **What the Fast Loader Does:** Rather than reading model weights sequentially via stock SGLang loaders, the fast loader reads each rank's tensors eagerly into pinned host memory slabs, parallelizing checkpoint ingestion during container startup.
* **Why the KV Pool Shrinks:** On the DGX Spark unified memory architecture, SGLang determines KV cache pool size by querying available system memory (`psutil.virtual_memory().available`). Although the fast loader releases tensor buffers before the pool is sized, temporary driver staging state and pinned page allocations retain ~0.8–1.5 GB in the unified memory pool. This reduction in reported `MemAvailable` shrinks the allocated KV cache pool from 7.47–7.82M tokens down to 6.71–7.27M tokens (a 3–13% reduction).

#### Startup Time vs. KV Capacity Trade-off

* **Fast Loader (`DSV41_FAST_LOAD=1`):** Reduces engine startup time from ~350 s down to ~125 s (saving ~220 s per boot), but permanently forfeits up to ~730k tokens of KV cache for the life of the container.
* **Stock Loader (`DSV41_FAST_LOAD=0`):** Requires ~350 s for cold engine launch, but maximizes available KV cache memory to guarantee full multi-user serving headroom.

#### Shipped Configuration Decision

* **Deliberately Disabled:** The recipe explicitly ships with `"DSV41_FAST_LOAD": "0"` in `launcher.py` to maximize available KV memory and support long-context / multi-stream serving.

**Summary Table**

| Metric / Attribute | Stock Loader (`DSV41_FAST_LOAD=0`, Shipped) | Fast Loader (`DSV41_FAST_LOAD=1`) |
| :--- | :--- | :--- |
| **Engine Startup Time (`scheduler_e2e`)** | ~343–354 s | **~124–129 s** (~220 s faster) |
| **Total KV Pool Capacity (`full_token`)** | **~7.47–7.82M tokens** | ~6.71–7.27M tokens (~3–13% smaller) |
| **Model Weights & Numeric Output** | Bitwise identical | Bitwise identical |
| **Inference Latency & Quality** | Unchanged | Unchanged |
| **Recommended Use Case** | **Production serving & long context** | Development & fast iteration |


### Greedy text equality is not a prefill-correctness gate

~70k-token cold prompts diverge run to run!

#### What is "Greedy Text Equality"?

* In autoregressive decoding, **greedy decoding** (setting `temperature=0` or taking `argmax(logits)`) always selects the single most probable token at each step.
* Theoretically, on deterministic systems, greedy decoding on identical inputs should yield identical, character-for-character output text across repeated runs.

#### What is a "Prefill-Correctness Gate"?

* A **correctness gate** is an automated validation check used in testing pipelines to verify that the engine initialized, ingested the prompt, and computed the initial KV cache and attention states without corruption.
* A common intuitive approach is to compare the greedy output against a golden reference string or across multiple runs: if output matches, prefill is deemed correct; if it differs, the run is flagged as failed.

#### Why It Fails for ~70k+ Token Prompts ("Diverge Run to Run")

* **Non-associative floating-point reductions**: Large-scale tensor-parallel matrix multiplications and reduction operations (e.g., across multi-node tensor parallelism, flash attention chunking, and quantized matrix formats like MXFP4/FP8) execute operations in non-deterministic order across thousands of parallel GPU threads.
* **Accumulated floating-point drift**: Across tens of thousands of tokens (such as ~70k tokens), minute rounding differences ($\approx 10^{-7}$ in float32/bfloat16 or larger in lower precisions) accumulate across layers and attention heads.
* **Argmax boundary flipping**: If the logits for the top two candidate tokens are nearly identical (e.g., $14.200001$ vs $14.200000$), a microscopic numerical delta will flip which token is selected first.
* **Autoregressive cascade**: Once a single token selection differs at step $N$, all subsequent generation steps receive different context and diverge completely.

#### Practical Implications

* **Avoid false negatives in test suites**: Treating greedy text diffs as a test failure for long-context runs will incorrectly flag healthy, performant deployments as broken.
* **Adopt robust evaluation criteria**: Prefill and engine health should be verified using downstream semantic benchmarks, needle-in-a-haystack retrieval tasks, logit tolerance thresholds, or target accuracy batteries rather than exact bitwise/string equality over massive context lengths.


### Single-stream prose is bounded by DSpark acceptance

Single-stream generation speed is constrained by the speculative acceptance rate (~3 accepted tokens per step on prose, ~6 on code).

#### Speculative Decoding Mechanism (DSpark)

* **Draft and Verify Pipeline:** DSpark employs speculative decoding to accelerate autoregressive generation. In each step, candidate tokens are drafted and verified in parallel by the target model, producing multiple output tokens per forward pass when speculation succeeds.
* **Acceptance Length Metric:** Performance gains depend directly on the mean number of speculative tokens accepted per verification step (`Mean acceptance length`).

#### Workload Entropy: Prose vs. Code

* **Structured Code Generation (~6 tokens/step):** Code contains predictable keywords, syntax structures, and indentation patterns, yielding higher speculative draft accuracy and achieving ~6 accepted tokens per step.
* **Natural Language Prose (~3 tokens/step):** Natural language prose exhibits higher entropy, varied vocabulary, and less deterministic phrasing, resulting in lower draft acceptance rates (~3 accepted tokens per step).

#### Concurrency and Throughput Scaling

* **Single-Stream (C1) Latency:** Single-user interactive requests on prose generation will experience decode speed bounded by the lower acceptance rate (~46.5 t/s aggregate).
* **Batch Concurrency (C4–C16) Throughput:** When serving concurrent streams (C4, C8, C16), GPU compute utilization increases and tensor-parallel batches saturate hardware capacity, raising aggregate throughput to 106–193 t/s.

#### Operational Notes

* **Verify Healthy Operation:** Check serving logs to confirm `Mean acceptance length > 1` on `Decode batch` lines. A speculative decode run that accepts ≤ 1 token per step indicates speculation is failing.
* **Reasoning Effort:** Configured with `chat_template_kwargs {"thinking": false}` for standard low-latency serving.


### Do not apply the SPS ragged-verify table

The speculative scheduling cost table (`DSPARK_SPS_TABLE` / `DSPARK_STS_TABLE`) arms the scheduler but crashes the Engram retrieval path on mixed-batch workloads.

#### What is the SPS/STS Ragged-Verify Table?

* **Ragged Verification Optimization:** The SPS (Speculative Scheduling) and STS tables provide cost models that allow the speculative scheduler to dynamically batch and verify uneven, variable-length candidate token sequences ("ragged" batches) across concurrent requests.

#### Mechanism of Failure with NVMe Engram Shards

* **Fixed-Block Invariant:** To stream DeepSeek V4.1-Flash's 203 GB Engram embedding tables from node-local NVMe within tight latency budgets, the custom Engram reader relies on strict, equal-block memory alignment per request.
* **Assertion Crash:** When ragged verification passes heterogeneous candidate sequence lengths to the verification step, the reader's batch invariant fails, throwing `AssertionError: engram target-verify expects one equal block per request, got 84 tokens for 16 requests of 6` and causing the serving worker to crash immediately on the first mixed batch.

#### Shipped Configuration Decision

* **Verify-All Mode Shipped:** The recipe deliberately leaves `DSPARK_SPS_TABLE` and `DSPARK_STS_TABLE` unset.
* **Production Stability:** Booting without the SPS table retains the uniform `verify-all` scheduling contract, ensuring complete stability across all mixed-batch production traffic.



## TensorFold TP=2 lane (two nodes)

A second lane in this directory serves the same model on **two** GB10 nodes with a
different engine. It trades the four-node SGLang lane's measured quality record and
its ability to hold several long-context streams at once for a lower node count and
better single-stream speed on a smaller (EXL3-quantized) checkpoint. Both lanes serve
the model's full 1M window; this one reaches it with two nodes instead of four, but
shares one KV pool across its streams rather than sizing the pool separately (see
[Context window and concurrency](#context-window-and-concurrency)).

| | |
|:--|:--|
| Recipe | `deepseek-v4.1-flash-tensorfold-tp2-1m-sglang.yaml` |
| Engine | TensorFold `deepseek_v41` ([bertholomus/TensorFold](https://github.com/bertholomus/TensorFold) @ `d5d7bb3`, branch `deepseek-v41-tp2`) |
| Model | [`Mia-AiLab/DeepSeek-V4.1-Flash-EXL3-2.9bpw`](https://huggingface.co/Mia-AiLab/DeepSeek-V4.1-Flash-EXL3-2.9bpw) (EXL3 2.9bpw, ~197 GB) |
| Engram | Official DeepSeek shards **47/48** (~95 GB each), distributed out-of-band |
| Nodes | 2 (TP=2, one GB10 per node) |
| Context | **1,048,576 tokens served** — the model's full trained window, which is also the KV pool |
| Spec decode | DSpark k=5 (in-checkpoint draft blocks) |
| Image | `littlecedar/dgx-spark-dsv41@sha256:fabbe861…` (vendored, digest-pinned) |
| Measured | C1 101 code / 62 prose / 142 structured t/s; 4 streams 112 t/s (upstream's numbers on 2× GB10) |
| Boot-verified | 2026-10-05 on 2× GB10: cold ~511 s engine-load, warm **51 s** TTR; **73 tok/s** single-stream (our own number) |

See [`AGENTS.md`](AGENTS.md) §12 for the design, the launcher/rendezvous details, and how to
rebuild the image. The lane is **boot-verified**: it loads both ranks, serves `/v1/models` and
`/v1/chat/completions`, and DSpark accepts (mean 2.76 tokens/round) — see §12.11 for our numbers.
Two caveats remain. First, the EXL3 checkpoint is a lossy quant, so its **quality** on this
project's hard tier is still unmeasured; do not imply parity with the SGLang lane's 17/18. Second,
the shipping prerequisite that bites first: the `@littlecedar/mods/…` reference resolves from the
node's registry clone, so this recipe only launches once the mod is committed and pushed (§12.10).

### Context window and concurrency

**The recipe ships at `max_model_len: 1048576` — the model's full trained window.** For this engine
that is also the largest possible KV cache, because `--context` *is* the pool: TensorFold exposes no
separate pool-size flag, so a bigger context and a bigger cache are one and the same setting. It is
therefore the largest value the recipe can carry, and the engine hard-refuses anything larger before
loading a single weight:

```
$ tensorfold serve <model> --context 1048577
tensorfold: --context 1048577 exceeds this model's 1048576-token window
```

(`cli.py`: `if native_context and context > native_context: raise …`; `native_context` is
`config.json`'s `max_position_embeddings`.) `1048576` itself boots and is served — verified on
2× GB10 (`/v1/models` reports it, the engine logs `context 1048576`).

That ceiling is the **model's**, not the machine's. 1,048,576 is not a round number by accident:
the checkpoint's `rope_scaling` is YaRN with `original_max_position_embeddings: 65536` and
`factor: 16`, and 65,536 × 16 = 1,048,576. Past it the model has no valid positions, so the engine
refuses to start rather than serve nonsense. Memory would allow far more — DeepSeek-V4.1-Flash uses
MLA (one shared latent KV head), so the cache costs only ~2.9 KiB per token; measured on the trial
pair, rank 0's warm-up `reserved` was **100.8 GiB at `context 262144`** and **103.0 GiB at
`1048576`** — the entire extra 786,432 tokens of window cost **2.16 GiB**.

`max_model_len` is **not** a per-request allowance — it is the **whole KV pool**, shared by the
`--parallel` lanes. The engine says so at startup:

```
[tensorfold] --parallel 4: 4 streams share one window of 1048576 tokens (an extent each)
```

Each stream carves its own `prompt + max_tokens + draft rows` out of that one window, and a request
whose prompt+reply exceeds it is refused up front. So **concurrency and per-stream context trade
off**, and you cannot run four full-window streams:

| 4 concurrent requests, each declaring | at `max_model_len: 1048576` (shipped) | at `max_model_len: 262144` (the old value) |
|:--|:--|:--|
| 2,000 reply tokens | **4 concurrent** | **4 concurrent** |
| 200,000 | **4 concurrent** | — |
| 250,000 | **4 concurrent** | **1** |
| 300,000 | **3 concurrent** | — |
| 500,000 | **2 concurrent** | — |
| 900,000 | **1** | — |

Measured 2026-10-05 on 2× GB10 via the engine's `/health` `streams.decoding` counter (full method
and the code path in [`AGENTS.md`](AGENTS.md) §12.13). `--parallel 4` is a hard cap: eight tiny
concurrent requests still decode at most 4 at once.

- **One stream can use the whole 1M window** (that stream is then the only decoder; others queue) —
  which is what makes the recipe usable for genuine long-context work.
- **Four streams coexist up to ~250K tokens each.** The pool is a superset of the old 262K one, so
  shipping 1M **strictly improves** concurrency: four requests each declaring a 250K reply went from
  **1 concurrent** at 262K to **4 concurrent** at 1M.
- **Decode speed is unaffected by the larger pool** — measured 72.5 tok/s median at `context
  1048576` versus 73.0 at 262144, identical DSpark acceptance. Pages are touched only as used.
- Size clients' `max_tokens` to about `max_model_len / n` for *n* concurrent long-context streams.
  Upstream's reported 4-way concurrency is real, and was measured on 384-token generations
  (~4K of window each).

## Retired material

The DeepSeek V4.1-Flash **vLLM / EXL3 lane** (five recipes over
`bot-lab-21/DeepSeek-V4.1-Flash-EXL3-3.5bpw-Pollard`) and its documentation —
the consolidated agent guide, the DSpark TP=3/TP=6 study, the memory-reclaim
plan, the performance triage, and the session notes — were moved to
[`attic/ds4/`](../../attic/ds4/) when this SGLang recipe was chosen for go-live.
That material is not shipped, not tested by `recipes/` guards, and kept only as
reference (it holds the load-bearing residency analysis, the DSpark k-sweep, and
a set of measured negative results). See [`attic/ds4/README.md`](../../attic/ds4/README.md).

For agents and developers working on this lane, read
[`AGENTS.md`](AGENTS.md) (same directory) before touching the recipe or the mod.