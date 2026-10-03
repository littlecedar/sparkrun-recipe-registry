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
sparkrun run recipes/ds4/deepseek-v4.1-flash-knapcio-tp4-1m-sglang.yaml \
  -H <node1>,<node2>,<node3>,<node4>
```

The recipe takes two run-time overrides through `defaults:`:

```bash
# a different serve port (the image's healthcheck follows the port)
sparkrun run … -o port=8123
# a shorter context (the engine accepts 4096 … 1048576)
sparkrun run … -o max_model_len=262144
```

`-o key=value` reaches `defaults:` only; it cannot change a top-level key such
as `model:`, and it reports no error if the key is unknown. Read back the
rendered command with `-n` when in doubt.

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

`sparkrun status` may show `(unhealthy)` on a healthy server only on images
older than the current digest; the shipped image discovers the served port at
runtime, so this is fixed. (Older images probed a fixed port 8888; Docker freezes
the container's creation environment, so a runtime-set port was below its view.
See [`AGENTS.md`](AGENTS.md) §5 for the mechanism.)

## Measured performance

Two harnesses were used; quote a number with its harness. The short-prompt
harness uses ~17-token prompts and is what the `C1 t/s` column in the repository
table refers to; the standardized `sparkrun benchmark` profile uses 2048-token
prompts and is the auditable cross-check.

| t/s (aggregate decode) | C1 | C4 | C8 | C16 |
|:--|--:|--:|--:|--:|
| short-prompt harness (shipped config) | **46.5** | **106** | **133** | **193** |
| standardized profile (`benchmarking/ds4-sglang-depth0-ladder.yaml`) | 43.6 | 91.3 | 99.4 | 102.1 |
| same lane, NCCL only (RoCEnante off; not shipped) | 27.4 | 62.5 | 73.2 | 155.0 |

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

## Limits and caveats

- **The 1M context is configured and served, not needle-tested here.** The
  server reports `context_len=1048576` and room for ~6.6 full-length requests,
  but a 1M-token needle retrieval has not been run on this cluster. Upstream
  reports needle PASS at 1M on their fleet. Do not claim a verified 1M retrieval
  until it is measured here.
- **Prompt-token logprobs are unavailable**, and late layers run only over the
  last 128 rows of a prefill (`--enable-decoder-swa-bounded-replay`); such
  requests return HTTP 400. Output logprobs and cache hits work. Greedy text is
  deterministic run to run, so an exact-match task battery is comparable, but a
  bitwise comparison against the release checkpoint is not available here.
- **The fast loader costs 3–13% of the KV pool.**
- **Greedy text equality is not a prefill-correctness gate**: ~70k-token cold
  prompts diverge run to run.
- **Single-stream prose is bounded by DSpark acceptance** (~3 accepted tokens per
  step on prose, ~6 on code).
- **Do not apply the SPS ragged-verify table.** It arms the scheduler and then
  crashes the Engram path on the first mixed batch. Upstream's production line is
  verify-all, which is what this recipe ships.

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