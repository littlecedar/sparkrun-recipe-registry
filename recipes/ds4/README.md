# DeepSeek V4.1-Flash on DGX Spark — `ds4`

DeepSeek-V4.1-Flash served on NVIDIA DGX Spark (GB10) nodes with SGLang. Two
shipped recipes, one per engine; both serve the model's full 1M-token window.
The retired EXL3/vLLM lane and all lane history — measurements, boot receipts,
negative results, working notes — live under [`attic/ds4/`](../../attic/ds4/)
(see the [Attic index](#attic-index)).

## Contents

- [deepseek-v4.1-flash-knapcio-tp4-1m-sglang](#deepseek-v41-flash-knapcio-tp4-1m-sglang)
  — SGLang, TP=4, official MXFP4/F8 weights, RoCEnante RDMA, native vision.
- [deepseek-v4.1-flash-tensorfold-tp2-1m-sglang](#deepseek-v41-flash-tensorfold-tp2-1m-sglang)
  — TensorFold, TP=2, EXL3 2.9 bpw, single-user.
- [Quality benchmarks](#quality-benchmarks)
- [Attic index](#attic-index)

## deepseek-v4.1-flash-knapcio-tp4-1m-sglang

| | |
|:--|:--|
| Recipe | `recipes/ds4/deepseek-v4.1-flash-knapcio-tp4-1m-sglang.yaml` |
| Engine | SGLang (`sglang.launch_server`), driven through the mod shim `recipes/ds4/mods/dsv41-sglang-overlay` |
| Model | [`deepseek-ai/DeepSeek-V4.1-Flash-1017`](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash-1017) (native MXFP4/F8, official weights, 2026-10-17 refresh) |
| Pin | `model_revision: 1bae0e10…` (the refresh's repo head, 2026-10-17) — all 48 shards are new objects vs the pre-refresh checkpoint, so the pin is what selects the refresh; the image's baked `fb2764a5…` is the superseded base and is never served |
| Size / fit | 510 GB, `mem_fraction_static` 0.80 |
| Topology | TP=4, EP=1 — four GB10 nodes, one rank per node |
| Context | 1,048,576 tokens served |
| Spec decode | DSpark k=5, verify-all |
| Transport | RoCEnante RDMA (shipped on) |
| Image | `littlecedar/dgx-spark-dsv41:canary-roce@sha256:acfc331a…` — vendored, digest-pinned, rebuilt 2026-10-17 on upstream knapcio `27616bec` (v2.4) with the local health-port patch |
| Tags | `official`, `large_context`, `lcg_favorite`, `vision` |
| Measured | 1017 base, v2.4 image: C1 **81.0** / C4 118.9 / C8 107.5 / C16 115.9 t/s aggregate (3 runs/cell, `benchmarking/ds4-sglang-depth0-ladder.yaml`, `--fresh`), 119k prefill 29.5 s, 231k 64.8 s, KV pool 9,273,856 (`~/benchmarks/ds4-knapcio-1017-20261018/arm-1017/`). C4/C8/C16 at parity with the V4.1 base inside the two arms' spreads; **C1 is unattributable** — the lane's C1 spans 59.2-75.3 across five single-boot v2.4 arms, and this boot ran its prefill probes first (`attic/ds4/AGENTS.md` §12.17) |
| Boot-verified | 2026-10-18, warm relaunch **545.9 s** (weight load 300.6 s + DSpark draft 66.8 s, packed Engram on all four ranks), `/v1/models` = the 1017 id, chat answers, vision **3/3** + text control (`~/benchmarks/ds4-knapcio-1017-20261018/`) |

**What the 1017 base needed that V4.1 did not.** Same architecture and same quant
(`config.json` byte-identical between the two repos, sha256 `8be45ce0…`: fp8 block weights with fp4
experts, unchanged vision config), so the engine and the adapter carry over unchanged. Two things
did not: the refresh ships **no `chat_template.jinja` by design** (its card replaces the Jinja
template with `encoding/encoding.py` and the `deepseek-recipe` toolkit), which the mod now stages as
a symlink farm beside the checkpoint (`ensure_template_overlay`, see the mod's README); and the
image's `pack_engram.py` derives each rank's packed Engram shards from the checkpoint's
`model.safetensors.index.json`, so the pre-refresh pack is invalid — shards 47/48 are
`76a05106…/9dc51433…` now, and `/cache/runtime/engram` must be empty (or re-packed) before the first
boot on the new base. A packed shard is an *optional* acceleration whose absence costs the
checkpoint fallback, not correctness, so the launcher re-packs per rank in the background.

### What it serves

A 1M-context chat/completions server for the official release weights, **including
native image input** (the image's own smoke test sends a generated PNG through
`/v1/chat/completions` on every boot). A per-node-Engram design: the model's two
203 GB Engram tables cannot coexist with the weight shards in a Spark's 128 GB
unified pool, so they are packed to node-local NVMe and streamed on demand. The
engine, kernels and reader come from the vendored image; this repository supplies
the recipe and the pre-launch mod (`recipes/ds4/mods/dsv41-sglang-overlay/`).

Provenance: this lane adapts
[`knapcio/DeepSeek-V4.1-Flash-4x-DGX-Spark-TP4`](https://github.com/knapcio/DeepSeek-V4.1-Flash-4x-DGX-Spark-TP4)
(a downstream of MiaAI-Lab's recipe) onto sparkrun. The launcher, adapters, b12x
kernels and measurement design are upstream's, kept under their licenses. For
provenance, boot gates and limits in full, see [`attic/ds4/AGENTS.md`](../../attic/ds4/AGENTS.md).

### Run it

```bash
sparkrun run recipes/ds4/deepseek-v4.1-flash-knapcio-tp4-1m-sglang.yaml
# or name the nodes (TP=4 = one rank per node):
sparkrun run recipes/ds4/deepseek-v4.1-flash-knapcio-tp4-1m-sglang.yaml \
  -H <node1>,<node2>,<node3>,<node4>
```

### Requirements

- **Four DGX Spark GB10 nodes, all idle** (TP=4 needs four nodes).
- **The pinned checkpoint in each node's own Hugging Face cache** — the cache is
  per-node, and the pin is a revision every node cache already holds, so a launch
  distributes nothing. Expect ~510 GB per node only if you re-pin to one no node has.
- **The image**, pulled from Docker Hub by sparkrun under its default distribution
  config; no local build is required.
- **~47 GiB node-local disk per node** for the packed Engram shards. The launcher
  packs them automatically on first boot (detached), so normally you do nothing.
  To pre-warm or debug by hand, run the packer (`/opt/dsv41/scripts/pack_engram.py`)
  inside the serving image on each node with the node's rank.

No host bind mounts are used: Engram shards, boot state and JIT caches all live
under sparkrun's managed runtime cache, mounted at `/cache/runtime`.

### Knobs a user cannot infer

- **`max_model_len` is per-request; the KV pool is separate and pinned.** The
  overlay launcher pins `MAX_TOTAL_TOKENS=9,400,000`; the head at
  `mem_fraction_static=0.80` permits ~9.5–9.6M, and a larger pin is *clamped* to
  that, never refused. The pool is **page-shared, not extent-reserved**: 16
  concurrent requests each declaring ~1M tokens were all admitted (the bound is
  the `MAX_RUNNING_REQUESTS=16` cap and total actual tokens, not a per-stream
  reservation). Keep `mem_fraction_static` at 0.80 — higher has wedged nodes.
- **`DSV41_FAST_LOAD` lives in the launcher, not the recipe** — there is no
  recipe-side knob (the recipe carries no `env:` block; everything is the
  launcher's `RECIPE_ENV`). Shipped `"0"` (stock loader, ~350 s startup). Setting
  it to `"1"` saves ~220 s/boot but shrinks the host's allowed KV budget 3–13%;
  at the shipped fixed pin, concurrency is unchanged either way.
- **Rollback for the RDMA transport is one launcher line:**
  `SGLANG_ROCE_ALLREDUCE=0`. RoCEnante is the single largest lever measured on
  this lane (1.23–1.81× over NCCL, outside the 7–25% boot-to-boot spread).
- **Prompt-token logprobs are unavailable.** The decoder runs
  `--enable-decoder-swa-bounded-replay` (late layers attend only the last 128 rows
  of a prefill), so a request for prompt-token logprobs (`echo`/`prompt_logprobs`)
  returns **HTTP 400**. Output-token logprobs and prefix cache hits work; greedy
  text is deterministic run to run but not bitwise-equal to a stock-prefill reference.
- **Do not set `DSPARK_SPS_TABLE` / `DSPARK_STS_TABLE`.** The ragged-verify
  scheduling table crashes the NVMe Engram reader on the first mixed batch
  (`AssertionError: engram target-verify expects one equal block per request`).
  The shipped uniform verify-all contract is deliberate.
- **The DSpark verify window (γ) stays at 5.** A fork pre-registered γ=2 as a win;
  the on-lane same-window paired A/B (2026-10-10) measured it *losing* at moderate
  concurrency (C4 −5.3%, C8 −2.9%). See the launcher's `DSPARK_BLOCK_SIZE` comment.
- **The checkpoint revision is pinned in the recipe, not the image.** The image
  bakes `fb2764a5…` but the launcher sets `SKIP_PREPARE=1` and serves the
  sparkrun-distributed snapshot, so `model_revision:` alone decides what is served.
  `launch.json` records the baked revision and is **not** evidence; the launcher's
  `serving …/snapshots/<sha>` line is. Moving the pin invalidates every receipt in
  the lane docs.
- **Any value can be overridden with `-o`** (e.g. `-o max_model_len=…`); the
  context flag is applied after `RECIPE_ENV`, so the recipe/CLI wins. `boot.py`
  asserts `4096 ≤ CONTEXT_LENGTH ≤ 1048576`.

### A healthy boot

Cold boot to ready is **~9 minutes**; a first cold boot additionally packs the
Engram in the background and serves from the checkpoint (the next boot uses the
packed shards). The server is up when these appear in the serve log, in order:

1. `[dsv41-sglang-overlay] overlay gate OK`, and a launcher line naming
   `NNODES=4 NODE_RANK=<r>` — **the rank must differ per node**.
2. `launcher: MODEL_ID is an on-disk checkpoint dir; serving …/snapshots/<sha>` —
   `<sha>` must be the recipe's `model_revision`. `launch.json` is **not** evidence.
3. `Exact nvme Engram layer=… rows=[a,b)` — the row range must **differ per rank**;
   identical ranges mean the staging is wrong.
4. `[moe_b12x_next] armed` — the routed MoE is on the b12x_next kernel.
5. `Mean acceptance length > 1` on `Decode batch` lines — a boot that serves but
   accepts nothing is a failure, not a win.
6. `Structured output, tool round trip and full-budget native vision passed.` —
   the image's own smoke test, which includes a native image-input check.

### License

The image's Dockerfile carries `SPDX-License-Identifier: Apache-2.0`; the overlay
mod `recipes/ds4/mods/dsv41-sglang-overlay` is **AGPL-3.0-or-later**. The upstream launcher,
adapters and b12x kernels are retained under their upstream licenses (knapcio's
repo, itself a downstream of MiaAI-Lab's).

### Launch caveats

- **Not a standing serve.** Launch only on nodes verified idle
  (`docker ps -q | wc -l` = 0) and stop it by recipe name when done.
- **The mod resolves from the node's registry git clone**, not the synced working
  tree — the mod must be committed and pushed before a launch sees new code.
  `sparkrun recipe validate` does **not** check mod existence; only a real launch
  (or `-n`) surfaces a resolution failure.
- `readiness.port_timeout_s: 7200` / `health_timeout_s: 3600` are deliberately
  generous — a cold boot reads/packs a 510 GB checkpoint.
- `sparkrun recipe validate --strict` fails this recipe with
  `model_revision is pinned to '<sha>', but command: never passes it`: a **false positive** for
  this shim lane, where the launcher receives a prepared snapshot path through `{model}` and the
  engine never resolves a ref. See `attic/ds4/AGENTS.md` §5. (Re-measured 2026-10-15: the
  sibling TP=2 tensorfold arm is the opposite case — it carries no `model_revision` at all, which
  no validator setting flags; registered as an open item.)
- **The radix/prefix cache did not hit on this lane** (measured 2026-10-06):
  back-to-back requests with identical prompts still logged `#cached-token: 0`.
  Treat "warm/reused context is near-instant" as **unproven here**.
- **Single-stream prose speed is bounded by DSpark acceptance** (~3 tokens/step on
  prose, ~6 on code); batch C4–C16 recovers aggregate throughput. Check `Mean
  acceptance length > 1` to confirm speculation is working.
- **Greedy text equality is not a prefill-correctness gate.** ~70k-token cold
  prompts diverge run to run (non-associative FP reductions across TP); verify
  with semantic/needle batteries, not exact string equality.

## deepseek-v4.1-flash-tensorfold-tp2-1m-sglang

| | |
|:--|:--|
| Recipe | `recipes/ds4/deepseek-v4.1-flash-tensorfold-tp2-1m-sglang.yaml` |
| Engine | TensorFold `deepseek_v41` ([bertholomus/TensorFold](https://github.com/bertholomus/TensorFold) @ `d5d7bb3`, branch `deepseek-v41-tp2`) |
| Model | [`LibertAIDAI/DeepSeek-V4.1-Flash-1017-EXL3-2.9bpw`](https://huggingface.co/LibertAIDAI/DeepSeek-V4.1-Flash-1017-EXL3-2.9bpw) — the 2026-10-17 refresh's EXL3 2.9 bpw (~196 GiB), pinned `c178a012…` |
| Engram | the 1017 tables (layers 1/14, ~189 GiB) in the node's `hub/dsv41-engram` dir, **outside** the checkpoint snapshot so a refresh cannot empty it; the recipe passes `--require-engram`, so a node without them fails the launch instead of serving degraded |
| Size / fit | 385 GB |
| Topology | TP=2 — two GB10 nodes, one rank per node |
| Context | 1,048,576 tokens served (the model's full trained window, which is also the KV pool) |
| Spec decode | DSpark k=5 (in-checkpoint draft blocks) |
| Image | `littlecedar/dgx-spark-dsv41@sha256:fabbe861…` (vendored, digest-pinned) |
| Tags | `fast`, `large_context`, `single_user`, `vision` |
| Measured | c1 **66.4** / c4 47.8 / c8 44.8 / c16 48.4 t/s — interleaved, 5 runs/cell, 3 boots per arm (`~/benchmarks/ds4-1017-ab-interleaved-20261018/`); upstream reports 101 code / 62 prose / 142 structured, 4 streams 112 |
| Boot-verified | 2026-10-18, shipped arm: TTR **62 s**, `/v1/models` = the 1017 id, vision 3/3, `weights in 26 s (from the rank cache)` (`~/benchmarks/ds4-1017-ship-20261017/`) |

### What it serves

Chat/completions with **image input**, at the full 1M window on **two** nodes. It
trades the four-node SGLang lane's measured quality record and its ability to hold
several long-context streams at once for a lower node count and better
single-stream speed on a smaller (EXL3-quantized) checkpoint. The `runtime: sglang`
here is the shim path: sparkrun renders the command and appends its per-node
rendezvous flags, and `mods/tensorfold-dsv41-launcher` maps them onto
`tensorfold serve`.

### Run it

```bash
sparkrun run recipes/ds4/deepseek-v4.1-flash-tensorfold-tp2-1m-sglang.yaml
```

### Knobs a user cannot infer

- **`--context` IS the KV pool, not a per-request allowance.** TensorFold exposes
  no separate pool-size flag, so `max_model_len: 1048576` is also the whole cache
  and the largest value the recipe can carry. The engine hard-refuses anything
  larger before loading a weight (`--context 1048577` → "*exceeds this model's
  1048576-token window*"); 1,048,576 = YaRN `65536 × 16`. **Concurrency and
  per-stream context trade off:** `--parallel 4` streams share one window, one
  stream may use the whole 1M, and four coexist only up to ~250K tokens each.
- **Vision works end to end as of 2026-10-17 — images, not only the tower.** The recipe carries the
  `vision` tag, the launcher appends `--vision`, the engine loads the tower on rank 0 (+0.90 GiB)
  with all 43 VL gates, and the *served chat template* is the mod's patched copy, delivered through
  an overlay model dir (`/cache/runtime/tensorfold/model-overlay`: symlinks to the checkpoint plus a
  real `chat_template.jinja`). Until this date every `image_url` part answered **HTTP 400 from the
  template**: the engine's vision path (`families/deepseek_v41/cuda/app.py`, `DsVision.split`)
  rewrites each image part into a placeholder inside one string content, and the upstream template
  rejects a placeholder arriving that way. Receipt (3/3 solid-colour probes, text control clean):
  `attic/ds4/AGENTS.md` §12.14.1.
- **Two vision contracts the value itself does not show.** (1) The served template defaults to
  **thinking mode**, so a small `max_tokens` is spent on `reasoning_content` and `content` returns
  empty — send `chat_template_kwargs: {"enable_thinking": false}` for one-shot answers. (2)
  `--vision` is the launcher's opt-in and this recipe passes it; the cybersec TP=2 arm mounts the
  same mod and passes no flag, so its serve line stays byte-identical.
- **The 43-tensor `ffn.gate.bias_vl` VL-routing bias**, which the EXL3 pack omits, ships
  **inside `@littlecedar/mods/tensorfold-dsv41-launcher`** as `vl_bias.safetensors`, beside the
  launcher that points `TF_DS_VISION_EXTRA` at its own directory and **fails the launch closed**
  when no `*.safetensors` is there (the engine would only warn and route image tokens with the text
  bias). A `--vision` boot missing the template refuses the launch the same way. The trial that
  proved the bias is preserved at `attic/ds4/mods/dsv41-vision-overlay/`.
- **The Engram tables live outside the checkpoint, in `hub/dsv41-engram`.** The 1017 pack ships
  none; the tables (layers 1/14, ~189 GiB) are pre-warmed per node into that standalone dir — the
  launcher's second engram home — so a revision refresh or an `hf cache` prune cannot empty them
  (the old `<snapshot>/engram/` location could, silently). `--require-engram` fails the launch when
  they are missing: the engine would otherwise only warn and serve at the card's
  PPL 1.87/6.43 → 4.16/9.06. Pre-warm with `tools/build-dsv41-engram.py` (its defaults are the 1017
  base, revision-pinned) or the unmounted `recipes/cybersec/mods/dsv41-engram-fetch`. A
  **rank-0/rank-1 Engram mismatch hangs at readiness** — every rank must have the tables before
  booting.
- **The serve line ignores request-level `temperature`/`repetition_penalty`**
  (byte-identical replies across override arms), so any future mitigation must go
  through the TensorFold launcher, not the client.
- **Distribution is by repo id, not local path.** sparkrun distributes a model by
  repo id into the node HF cache; to run across the cluster either push the repo
  (`hf upload littlecedar/…`) and point `model:` at the id, or pre-place
  `models--<org>--<name>/snapshots/<rev>` on every node.
- **The recipe sets `ulimit: memlock=-1:-1`.** The RDMA gather and NCCL over the
  CX7 fabric need registered (locked) memory; dropping it breaks the transport.
- **The readiness timeouts are generous on purpose.** A cold first boot compiles
  the CUDA extensions and writes the ~106 GiB/rank weight cache before the serve
  port opens; later boots are much shorter. `port_timeout_s: 3600`,
  `health_timeout_s: 1800`.

### License

Engine: TensorFold **Apache-2.0** (a fork of ashhart/TensorFold v0.6.3); the
`deepseek_v41` family is a clean-room re-implementation of DeepSeek's **MIT**
inference code (see the fork's `tools/dsv41/ATTRIBUTION.md`). Checkpoint: the
`Mia-AiLab/DeepSeek-V4.1-Flash-EXL3-2.9bpw` base is **MIT**. The shim mod
`mods/tensorfold-dsv41-launcher` is **AGPL-3.0-or-later**.

### Launch caveats

- **Two nodes, idle.** Boot-verified 2026-10-05 on 2× GB10: cold ~511 s
  engine-load, warm **51 s** TTR. A cold first boot compiles the CUDA extensions
  and writes the ~106 GiB/rank weight cache before the port opens.
- **Quality is measured, not assumed.** The EXL3 2.9 bpw quant scores **17/18** on
  the house hard tier — *identical* to the official-weights lane, with no
  benchmark separating the two across 11 benches / ~1,900 paired items. See
  [Quality benchmarks](#quality-benchmarks).
- **The mod must be committed and pushed** — `@littlecedar/mods/…` resolves from
  the node's registry clone, so this recipe only launches once the mod is pushed.
- Vision rides the launcher's `--vision` flag (this recipe passes it, with the 43-gate
  bias shipped in the mod); see the vision knob above.

## Quality benchmarks

`recipes/ds4/benchmarks/` holds the quality comparison of the two live cluster
gateway aliases (`deepseek` = official weights, `deepseek-turbo` = EXL3 2.9 bpw) —
a harness, not a recipe. Headline: **parity within noise** (house 36/37 both,
hard tier 17/18 both, same single failure). Method and caveats in
[`benchmarks/README.md`](benchmarks/README.md); published reference scores for the
unquantized model in [`benchmarks/REFERENCE-SCORES.md`](benchmarks/REFERENCE-SCORES.md).

## Attic index

Everything under `attic/ds4/` — the retired EXL3/vLLM lane and all lane history.
Nothing here is shipped or covered by `recipes/` guards. Restore a file with
`git mv attic/ds4/<file> recipes/ds4/<file>`.

| File | What it holds / the question it answers |
|:--|:--|
| `README.md` | The attic's own index: why the EXL3/vLLM material was archived, the five retired recipes, each doc's role, and how to restore a file. |
| `AGENTS.md` | Three documents, appended newest-last: the former ds4-family agent guide (EXL3/vLLM era — model anatomy, the 203 GB Engram residency wall, the DSpark k-sweep, §1–§14); the live-lane guide for the knapcio + TensorFold lanes (§1–§14); and the pre-rewrite `recipes/ds4/README.md`. All §N numbering preserved so existing `§N` citations still resolve. |
| `NOTES.md` | Appended 2026-10-14 from `recipes/ds4/NOTES.md`: the combined local HF repo (EXL3 + Engram + prompt) build/boot record and the Engram-from-HF builder notes for the TP=2 lane. |
| `ds4_NOTES.md` | The session working record for the retired EXL3/vLLM lane. |
| `DSPARK-TP3-STUDY.md` | Feasibility study for DSpark speculative decoding at TP=3/TP=6, where the drafter's head and expert counts do not divide the TP degree. Verdict: feasible; implemented and booted 2026-09-27. |
| `MEMORY-RECLAIM-PLAN.md` | Host-memory reclaim analysis for the EXL3 lane: the `instanttensor` load path is closed (incompatible with this checkpoint) and cache drops are not a mitigation. |
| `PERF-ISSUES.md` | Long-context performance triage of the EXL3 1M arms: the observed collapse is the cost of a cold deep prefill, not decode starvation. |
| `deepseek-v4.1-flash-exl3-tp3-vllm.yaml` | Retired EXL3/vLLM recipe — TP=3, 300K context (3 nodes). |
| `deepseek-v4.1-flash-exl3-tp4-vllm.yaml` | Retired EXL3/vLLM recipe — TP=4, 300K context (4 nodes). |
| `deepseek-v4.1-flash-exl3-tp4-1m-vllm.yaml` | Retired EXL3/vLLM recipe — TP=4, 1M context (4 nodes). |
| `deepseek-v4.1-flash-exl3-tp6-vllm.yaml` | Retired EXL3/vLLM recipe — TP=6, 300K context (6 nodes). |
| `deepseek-v4.1-flash-exl3-tp6-1m-vllm.yaml` | Retired EXL3/vLLM recipe — TP=6, 1M context (6 nodes). |
| `mods/` | The mods the retired recipes mounted, plus one provenance copy. `mount-dsv41-exl3-patches` installs tonyd2wild's DeepSeek-V4.1-Flash vLLM patch set (incl. the Engram-on-disk reader and the TP=3/6 draft virtual-heads config fix); `bound-engram-cache` is an opt-in post-patch mod that `fadvise(DONTNEED)`s the Engram reader's read-once pages out of the host page cache; `dsv41-vision-overlay` is the archived TP=2 vision trial, SHIPPED 2026-10-15 into `mods/tensorfold-dsv41-launcher` (see the vision knob above). |
| `tuning/` | The vLLM autotuning cache for the EXL3 3.5 bpw (`bot-lab-21/…-Pollard`) checkpoint at TP=6 — MoE and FP8 kernel configs plus the tuning report. |
