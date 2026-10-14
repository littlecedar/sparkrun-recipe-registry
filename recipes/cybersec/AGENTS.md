# Cybersec lane — operating guide

Durable guide for `recipes/cybersec/`. Read before editing anything here. Human-facing summary
(arm table, gating notice, reproduce commands): [`README.md`](README.md).

This lane serves **abliterated / cybersecurity-unlocked** checkpoints. The engineering is ordinary
sparkrun work; the *policy* is not — see §1.

---

## 1. Gating and the token prerequisite

Every arm's checkpoints are **gated on the Hub (`gated: auto`)**. Recipes therefore carry no
weights, and a launch fails closed at model acquisition when the token is absent or has not
accepted that specific repo's release:

- each runner node needs `HF_TOKEN` (the node's `/cache/huggingface/token`) whose **user has
  accepted that repo's release**. Gating is **per repo, not per user or per org**: listing a repo
  works unsigned, reading its files does not (the discriminating probe is `cat README.md`).
- Arms 2 and 5 each pull **two** gated repos: the overlay (template / sidecar) and the body or
  stock pack. Accept both, on every node.
- Nothing in this lane redistributes weights. A recipe ships a repo id, a `model_revision:` pin,
  and wiring.

`metadata.caveats` on every recipe restates this. Do not delete it because a boot succeeded on a
node that happens to be signed — the registry ships to third parties.

---

## 2. The served-id convention (lane-wide, non-negotiable)

Every arm renders `--served-model-name {served_model_name}` — **never `{model}`**.

On a real launch sparkrun rebinds `{model}` to the prepared on-disk snapshot path
(`models/runtime.py::bind_runtime_models`), and a `-n` dry run still prints the repo id, so the bug
is invisible until a client reads `/v1/models` and gets a
`/cache/huggingface/hub/models--…` path. `served_model_name` is the arm's repo id; the table is in
`README.md`. `tests/test_cybersec_recipes.py::ServedIdentity` pins this and has negative controls
for both directions (a `{model}`-shaped id, and a comment that merely quotes one).

For the overlay arms the served id is the **arm's identity**, not the body pack: arm 2 is the AEON
body *through the cyber template*, arm 5 serves a graft tree that exists only on the node.

---

## 3. Revisions

`model_revision:` is a **top-level** key (a `revision:` key is silently absorbed into
`runtime_config` and does nothing). Pinning it without passing it is worse than not pinning:
sparkrun downloads by commit SHA, which writes **no `refs/main`** in the HF cache, the container
runs `HF_HUB_OFFLINE=1`, and the engine resolves its default revision, finds no ref, and dies with
`LocalEntryNotFoundError` *after* the model has fully downloaded. `sparkrun recipe validate` lints
exactly this (`unpinned-model-revision`), and the lane's guard re-asserts it.

Pins (Hub `main` SHA, read 2026-10-14):

| repo | revision |
|---|---|
| `orcarouter/Qwen3.8-27B-Uncensored-NVFP4` | `f8489198f18fcd94b124541adaba3d9cb14a7ef4` |
| `sakamakismile/Qwen3.8-27B-AEON-ULTIMATE-UNCENSORED-NVFP4` | `8d5a3317b4fcb6f278e1cde7fcae5ed88a27443a` |
| `orcarouter/Nex-N2.5-mini-Uncensored-NVFP4` | `9f11be0e80ff4b7670c7dbaacb213e9ad10e32a4` |
| `orcarouter/Qwen3.8-Flash-Next-Uncensored-NVFP4` | `cd56f6c148c6287cf26fa6618223ad046b9af27c` |
| `Mia-AiLab/DeepSeek-V4.1-Flash-EXL3-2.9bpw` | `64ba41b6c916a587db06eae2e19b7845f7be6e6b` |
| overlay `drowzeys/keys-Qwen3.8-27B…Single-DGXSpark` | `a9cf9de0e143513bb16183d65d9f4ca246906321` |
| overlay `drowzeys/DeepSeek-V4.1-Flash-Abliterated-Cybersecurity-Unleashed` | `87bb9850e6f49fd20ad9c8516b7817215cbbf5fc` |

Arm 5 is the one arm whose command does **not** carry `--revision {model_revision}`: it serves a
mod-built graft tree (`--model {served_model_dir}`), so a `--revision` flag would have no receiver.
The pin is still live there — it selects which stock revision the node's cache holds, and the graft
mod's resolver reads that snapshot.

**Arm 5 must still carry an identity token or the launch is refused before it starts.** sparkrun's
`validate_runtime_command` (`sparkrun/models/runtime.py`) requires the rendered serve command to
contain either the prepared snapshot path or the recipe's `model:` plus a supported revision flag;
otherwise it raises `serve command does not identify the validated model`. A graft arm's command
names neither naturally — it loads `/cache/runtime/dsv41-ablit` and advertises the overlay's repo
id — so the recipe passes `--stock-model {model}` (which renders to the prepared path, the token
the validator looks for) and `mods/graft-dsv41-ablit-wo-b/serve-when-grafted.sh` consumes and
records it before exec'ing the launcher. Measured 2026-10-14: without it, the launch died at step
[4/6] *after* the 205 GB stock pack had been distributed.

---

## 4. Artifact facts worth not re-deriving

Sizes are **measured on-disk weight bytes** (Hub `files_metadata`, 2026-10-14), not the Hub
`Parameters` field or a name-derived guess. One node ≈ 108 GB usable at util 0.85; two ≈ 218 GB.

| arm | checkpoint | bytes on disk | quant / arch | notes |
|---|---|---|---|---|
| 1 | `orcarouter/Qwen3.8-27B-Uncensored-NVFP4` | ~24.7 GB | compressed-tensors **mixed** NVFP4 FFN + FP8 attention/GDN, static FP8 KV, `qwen3_5` | abliterated BF16 base → quantised; vision tower and MTP head preserved (MTP head is BF16) |
| 2 | `sakamakismile/…-AEON-ULTIMATE-UNCENSORED-NVFP4` | ~20.5 GB (+0.85 GB MTP) | compressed-tensors NVFP4, `qwen3_5` | AEON-7 abliteration; the overlay adds only a chat template (+ YaRN rope JSONs) |
| 3 | `orcarouter/Nex-N2.5-mini-Uncensored-NVFP4` | ~23.9 GB | compressed-tensors NVFP4 **routed experts only**, rest BF16; `qwen3_5_moe` (256E top-8 + 1 shared, 3:1 GDN) | new family here (no Nex arm existed); **no MTP head** upstream |
| 4 | `orcarouter/Qwen3.8-Flash-Next-Uncensored-NVFP4` | ~183.5 GB | compressed-tensors NVFP4 experts + FP8 attention, weight-only, KV bf16; `qwen4_exp` | ~184 GB sits near the two-node 0.85 ceiling → `gpu_memory_utilization: 0.85`; the ~100 GB bf16 PLE n-gram tensor dominates the size |
| 5 | `Mia-AiLab/…-EXL3-2.9bpw` + sidecar | ~197 GB stock + 682 MB sidecar | EXL3 mul1 K=5, 39 shards | 104 tensors edited (26 layers × trellis/suh/svh/mul1); L0-9, L36-39, MTP, embed/head, experts stay stock |

Two template traps, both *measured* on the checkpoints' own cards and templates:

- **Nex (arm 3) gates thinking on `reasoning_effort`, not `enable_thinking`.** The chat template's
  `add_generation_prompt` emits ` thinking` whenever `reasoning_effort` is unset, so a short reply
  is consumed by the deliberation trace and `content` comes back empty for every client that reads
  `content` (the house battery does). The recipe ships
  `--default-chat-template-kwargs '{"reasoning_effort": "none"}'`; a caller wanting the scratchpad
  passes `{"reasoning_effort": "high"}` per request.
- **Nex ships no `generation_config.json`**, so a loader falling back to `config.json` gets
  `eos_token_id = 248044` only. Give thinking-on requests enough budget to reach `</think>`.

Arm 1's own card is explicit that the mixed-precision `quantization_config` (including the FP8
`kv_cache_scheme`) must be read from `config.json` — **do not pass `--quantization` or
`--kv-cache-dtype`** on the vLLM route. The lane's SGLang arms omit `--quantization` too (SGLang
auto-detects `compressed-tensors` from the config); `--kv-cache-dtype {kv_cache_dtype}` is
`auto` for arms 1 and 2 so the checkpoint keeps ownership of the KV dtype.

---

## 5. The two overlay mods

Both are pre-exec mods that stage the arm's real artifact into sparkrun's managed runtime cache.
Neither writes the source snapshot. Both fail closed — a silently-missing template or graft would
leave the arm serving a **different checkpoint under its own name**, which is worse than a failed
boot.

- `mods/provide-uncensored-chat-template` — fetches the drowzeys uncensored chat template (+ the
  YaRN rope overlays) and writes `/cache/runtime/uncensored-template/chat_template.jinja`, which
  arm 2 passes to `--chat-template`. Idempotent from the artifact (a non-empty template
  short-circuits). Needs the node token.
- `mods/graft-dsv41-ablit-wo-b` — fetches the author's `apply_mia_exl3_wob.py` + the EXL3 sidecar
  and grafts them onto the stock Mia pack under `/cache/runtime/dsv41-ablit`. Idempotent from
  `ABLIT_META.json` (`n_edited == 104`); refuses `--src == --dst`.

**The graft cannot exceed the pre-exec hook.** The graft rewrites every shard carrying
`layers.10-35 attn.wo_b` (~26 shards × ~5 GiB) and must finish inside sparkrun's hard-coded
**600 s** hook budget (`sparkrun/orchestration/hooks.py::run_pre_exec`) — a recipe cannot raise
it. It is therefore synchronous and fail-closed in `run.sh`; once a graft exists the mod is a
no-op and the boot pays only TensorFold's rank-cache build.

Deferring it was tried and **does not work on a cluster launch**: sparkrun holds the head on its
rendezvous/readiness gate (~300 s) *before* the serve command's `readiness.port_timeout_s`
applies, so a serve wrapper that waits for a background graft is declared dead while it is still
polling. Measured 2026-10-14 (task `sparkrun_d42e44075b9357cd_c390039d73a3`): "Head node failed
to become ready on `.32`" at 318 s, wrapper still polling. A cold node whose graft cannot
fit 600 s is a launch failure, not a degraded serve — pre-warm out of band for such a node.

---

## 6. Arm 5 in more detail

The stock pack is the same checkpoint the `ds4` lane's TP=2 TensorFold recipe serves; the lane
reuses that lane's launcher unchanged (`mods/tensorfold-dsv41-launcher`) and adds the graft mod.
`runtime: sglang` is the shim path: sparkrun renders the command and appends its per-node
rendezvous flags, and the launcher maps them onto `tensorfold serve`.

Two facts that come from the ds4 lane, not this one — do not contradict them here:

- The engine's family check accepts **only** EXL3 (`quant_method`), which is why the stock must be
  the Mia 2.9bpw pack and not the official MXFP4 repo.
- Engram tables (~95 GiB each) are **not** in the EXL3 checkpoint. `mods/dsv41-engram-fetch`
  provisions them from the online official repo and deliberately does **not** block the boot; a
  first boot can serve degraded and pick them up on the next. GPU memory utilisation stays ≤ 0.85.

Graft never in place: the graft's `--src` is the stock snapshot and its `--dst` is the runtime
cache; the mod compares `realpath -m` of both and dies if they are equal (the author's script also
refuses it). The lane guard asserts both.


---

## 7. Validation ritual

After any edit here:

```bash
H=$PWD/.local/sparkrun-home
for f in recipes/cybersec/*.yaml; do HOME="$H" sparkrun recipe validate "$f"; done
uv run python -B -m unittest tests.test_cybersec_recipes -v
for s in mods/provide-uncensored-chat-template/run.sh mods/graft-dsv41-ablit-wo-b/run.sh; do bash -n "$s"; done
```

`validate` does **not** resolve `mods:` — only `-n` or a launch does. Render before booting:

```bash
cd ~/development   # recipes symlinked by basename; `mods` is a symlink to the repo's mods/
sparkrun run <arm> -H <node> -n
```

A guard over this lane is over shipped artifacts, not units, so **every check has a proven
negative control** (see `tests/test_cybersec_recipes.py::NegativeControls`).

---

## 8. Receipts

One boot + one measurement per arm; `GET /v1/models` must echo the arm's repo id. C1 is
`benchmarking/decode-triage.yaml` (d0/d8192, c=1, n=5), battery is `tools/quality-battery.py
--tier both`.

### Arm 1 — `qwen3.8-27b-uncensored-nvfp4-sglang` — POSITIVE (TP=1)

- Boot: task `cc7b08667c2618ea_428b66bd4af7`, container
  `sparkrun_cc7b08667c2618ea_428b66bd4af7_solo` on `.32`. `GET /v1/models` →
  `{"id":"orcarouter/Qwen3.8-27B-Uncensored-NVFP4","max_model_len":262144,"owned_by":"sglang"}`.
- SGLang parsed the checkpoint with **no** `--quantization` flag: `Load weight end. elapsed=5.73 s,
  type=Qwen3_5ForConditionalGeneration, quant=compressed-tensors`. The KV pool was allocated as
  `torch.float8_e4m3fn` (#tokens 359398) — the config's static FP8 `kv_cache_scheme` honoured via
  `--kv-cache-dtype auto`. Mamba pool 522, conv state 1.44 GB, 16.08 GB free after pool end.
- **C1** (`bench_edd91a07aee4`, `benchmarking/decode-triage.yaml`, `--skip-run`):
  **d0 10.2 t/s** (pp 2076.1, ttfr 990.6 ms) · **d8192 9.7 t/s** (pp 592.4, ttfr 3459.7 ms), c=1, n=5.
  Receipt: `~/benchmarks/cybersec/arm1-decode-triage.yaml` (+ `.json`/`.csv`) on the head.
- **House battery**: **easy 19/19, hard 18/18 = 37/37**, stable, no flaky tasks. Receipt:
  `~/benchmarks/cybersec/arm1-battery.json`. (Give the tool the **host root** as `base_url` —
  `http://<node>:8000`, not `…/v1`; it appends the path itself.)
- 10.2 t/s is **plain decode**: this arm carries no spec decode even though the checkpoint
  preserves its MTP head in BF16. The clean 27B sibling lane reaches 33.8 t/s with the DFlash2
  draft; wiring MTP here is an open, unmeasured idea.

### Arm 2 — `qwen3.8-27b-ablit-cyber-unlock-nvfp4-dflash2-sglang` — POSITIVE (TP=1)

- Boot: task `25c5e017805915a6_428b66bd4af7`, container
  `sparkrun_25c5e017805915a6_428b66bd4af7_solo` on `.32`. `GET /v1/models` →
  `{"id":"sakamakismile/Qwen3.8-27B-AEON-ULTIMATE-UNCENSORED-NVFP4","max_model_len":262144}`.
- The overlay mod worked as designed — SGLang logged `Loading chat template from argument:
  /cache/runtime/uncensored-template/chat_template.jinja` and `Detected user specified Jinja chat
  template with content format: openai`, i.e. the fetched **uncensored** template is what the arm
  serves, not the body's stock template.
- **C1** (`bench_1f7909b775f7`, `decode-triage`, `--skip-run`): **d0 33.3 t/s** (σ 3.95, pp 2534.7)
  · **d8192 26.2 t/s** (σ 2.96, pp 775.5), c=1, n=5. Receipt:
  `~/benchmarks/cybersec/arm2-decode-triage.yaml`. That d0 figure matches the clean 27B sibling
  lane's 33.8 t/s on the same DFlash2 block size (8) — the abliteration and the extra template cost
  nothing measurable here.
- **House battery**: **easy 19/19, hard 18/18 = 37/37**, stable, no flaky. Receipt:
  `~/benchmarks/cybersec/arm2-battery.json`.
- Sanity probe (reasoning is on by default in this stack): `finish_reason=stop`,
  `content='\n\n1161'` for `27*43`, `usage.reasoning_tokens=51`, `prompt_tokens=127` — the unlock
  template prepends a system block, so prompts are ~2× the length of a bare-template arm.

### Arm 3 — vLLM route: blocked on image distribution (not on the model)

`orcarouter/Nex-N2.5-mini-Uncensored-NVFP4` documents vLLM's `CompressedTensorsW4A4` as its route,
and the cluster's `ghcr.io/spark-arena/dgx-vllm-eugr-nightly` image **does** carry the arch:
`vllm 0.1.1.dev7+g8c1d1c297.d20260911` exposes `Qwen3_5MoeForConditionalGeneration`,
`Qwen3_5MoeMTP`, `Qwen3_5MoeTextConfig` (grep over `vllm/model_executor/models/`). A vLLM recipe was
written and validated, then dropped unshipped: sparkrun's OCI relay could not get the image onto
`.33`. The node's local `:latest` is one layer short of the upstream manifest ("12 layers reused",
"up to 6.8 GiB needed") and the relay streamed that layer at **~0.3 MB/s** (~2 MB in 60 s), i.e.
hours. Pinning the container to the digest the *head* already holds
(`…nvfp4-vllm` @ `sha256:b94ac8ac4760…`) did not change the shortfall — .32/.33 pulled the tag
earlier than the head did. Reviving this arm needs the image distributed first (or a node whose
local copy matches the manifest).

### Arm 3 — `nex-n2.5-mini-uncensored-nvfp4-sglang` — NEGATIVE (TP=1)

SGLang **loads** the checkpoint and the server reports ready, then the first generation dies.

- Boot: task `fcfc3411dd0ad0a9_80fa71eb085e` on `.33`; TTR port-open 135.164 s, HTTP-ready
  146.831 s; `GET /v1/models` answered `orcarouter/Nex-N2.5-mini-Uncensored-NVFP4`.
- First sampled token → `torch.AcceleratorError: CUDA error: device-side assert triggered` in
  `sglang/srt/layers/sampler.py:905 sampling_from_probs_torch` → `torch.multinomial(probs, 1)`,
  i.e. the sample-time logits are not finite.
- The `--skip-run` C1 run failed on its first cell (6.3 s) for this reason. The container stayed
  `Up` with the serve process dead — sparkrun detaches the server, so the traceback lives in
  `/tmp/sparkrun_serve.log` **inside the container**, not in the sparkrun launch log.
- A second attempt with `-o mamba_ssm_dtype=float32` (dropping an override this lane had carried
  from the qwen3.8-27B recipe, whose evidence is specific to *that* checkpoint) no longer asserts,
  but the arm serves **degenerate** text: `finish_reason=length` with `content: ''`, and with
  `chat_template_kwargs {"enable_thinking": false}` a reply of repeated `!`.
- The untested component is the MoE expert path: compressed-tensors `nvfp4-pack-quantized`
  (`weight_packed` uint8 + `weight_scale` FP8 + `weight_global_scale`), where the uploader
  documents **vLLM's `CompressedTensorsW4A4`** and nothing else.
- **Not shippable under SGLang.** Next step, unstarted: a vLLM route (`qwen3_5_moe` +
  compressed-tensors NVFP4) on a vLLM image that carries this arch. The recipe's
  `metadata.caveats` names the gate so an operator does not re-discover it.

### Arm 4 — `qwen3.8-flash-next-uncensored-nvfp4-sglang` — NEGATIVE (TP=2)

Checkpoint fully downloaded on both nodes (183.5 GB each; verified by summing the snapshot's
safetensors). Both nodes idle. Launch reached the serve stage and the scheduler died at init:

- Boot attempt: task `sparkrun_…_node_0/_node_1` on `.32`+`.33`, `[5/6]` pre-serve hooks ran,
  then the head endpoint never came up — `[sparkrun] ERROR: endpoint did not become ready — the
  startup probe did not verify a first non-empty inference token` after 1934 s.
- Serve log (container `/tmp/sparkrun_serve.log` on `.32`), the deciding line:
  `Scheduler hit an exception: … ImportError: Other method (CompressedTensorsW4A16Sparse24) is not
  supported now`.
- So the image's compressed-tensors loader maps this export's `quantization_config` to
  `CompressedTensorsW4A16Sparse24` (the `naive-quantized` FP8 groups plus NVFP4 experts make a
  scheme SGLang does not implement) and refuses. This is a **loader-scheme** failure, not memory,
  distribution, or the arch: the same image serves `qwen4_exp` fine from the RadixArk
  `modelopt_fp4` export.
- Conclusion: `orcarouter/Qwen3.8-Flash-Next-Uncensored-NVFP4` is **not shippable on SGLang** as
  written. The card's own route is vLLM (`qwen4_exp` + `compressed-tensors`), which is the next
  step; our vLLM image carries `Qwen3_5Moe*` but qwen4_exp support in it is unverified, and image
  distribution to these nodes was measured unusable (~0.3 MB/s for one missing layer — see Arm 3
  above). Pinning `--quantization` to another value is **not** a fix to try blindly: arm 1 shows
  SGLang reads the right scheme from `config.json` when the export is one it implements.

### Arm 5 — `deepseek-v4.1-flash-abliterated-cyber-tp2-tensorfold-sglang` — POSITIVE (TP=2)

**The graft fits the 600 s pre-exec hook budget, measured, not assumed.**

- Boot: task on `.32`+`.33`; `GET /v1/models` →
  `{"id":"drowzeys/DeepSeek-V4.1-Flash-Abliterated-Cybersecurity-Unleashed","owned_by":"tensorfold","max_model_len":1048576}`.
  Launcher line: `loading drowzeys/DeepSeek-V4.1-Flash-Abliterated-Cybersecurity-Unleashed:
  DeepSeek-V4.1-Flash (deepseek_v41) on CUDA, rank 0 of 2 … context=1048576 engram=OFF`.
  Total launch 604.4 s (graft + TensorFold load, warm rank cache absent).
- **Graft cost per node** (from the timestamped mod log, `…/modlogs/graft-dsv41-ablit-wo-b.log`):
  `.32` **269 s** (`10:35:42` → `10:40:11`), `.33` **284 s** (`10:40:16` → `10:45:00`), both
  ending in `verified n_edited=104 method=graft-keys-l10-35-wo_b-exl3-mul1-k5`. So the budget
  holds with ~2× headroom; the first shards are the slow ones (~39 s each) and the tail is much
  faster, which is why the mid-graft sample looked like it would overrun.
- **C1** (`bench_44534d5024c0`, `decode-triage`, `--skip-run`): **d0 63.7 t/s** · **d8192 67.7 t/s**,
  c=1, n=5. Receipt `~/benchmarks/cybersec/arm5-decode-triage.yaml`. The ds4 lane's TP=2 stock arm
  (same engine, same 2.9bpw base, with Engram) reports 73.0 t/s — so the graft costs little.
- **House battery**: **easy 19/19, hard 17/18 = 36/37** (one hard miss), matching the ds4 lane's
  36/37 on the stock EXL3 pack. Receipt `~/benchmarks/cybersec/arm5-battery.json`.
- **Refusal probe** (8 abstract harmful framings + 4 defensive cyber tasks; the overlay author's
  Refusal32/Cyber sets are **not** published with the weights, so this is our own small set, not a
  reproduction of the card's 32/32 and 22/22): **explicit-refusal rate 0/8 — no refusal marker in
  any reply.** Only 1/8 surfaced complete text at `max_tokens=900` (a bank-phishing email draft);
  the rest hit the token cap mid-trace. That is a **serve-path** artifact, not a scoring result:
  this engine exposes no reasoning channel, so a trace that never closes returns an empty
  `content`. Ping check: `17*19` → `323` (the card's own gate).
- **Cause of the two dead launches before this one** is recorded above (§3 identity token, and
  the detached-graft variant). **Engram is OFF on this boot** (`mods/dsv41-engram-fetch` runs
  detached and had not finished), so every number here is the **degraded, no-Engram** path — the
  ds4 lane's 73.0 t/s figure carries Engram. A second boot after the fetch completes would pick
  the tables up; the C1/battery comparison against the stock arm should be re-read with that in mind.
