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
| `Mia-AiLab/DeepSeek-V4.1-Flash-EXL3-2.9bpw` | `64ba41b6c916a587db06eae2e19b7845f7be6e6b` — its shards are the combined pack's weight shards (attribution only; arm 5 serves the combined pack) |
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
the validator looks for) and `recipes/cybersec/mods/graft-dsv41-ablit-wo-b/serve-when-grafted.sh` consumes and
records it before exec'ing the launcher. Measured 2026-10-14: without it, the launch died at step
[4/6] *after* the 205 GB stock pack of the day had been distributed.

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
| 5 | `littlecedar/…-EXL3-2.9bpw-with-engram` + sidecar | ~386 GB stock (the 197 GB Mia shards + ~189 GB Engram tables) + 682 MB sidecar | EXL3 mul1 K=5, 39 shards | 104 tensors edited (26 layers × trellis/suh/svh/mul1); L0-9, L36-39, MTP, embed/head, experts stay stock |
| 6 | `orcarouter/OrcaCyber-Nano-1.0:Mix-15.7G` | 15.70 GB (14.62 GiB) + 0.93 GB `mmproj` | GGUF mixed **4.60 bpw** (IQ4_XS 244 · Q6_K 129 · Q5_K 106 · IQ3_S 18 · Q4_K 10 · F32 360), `qwen35`, 27.32B dense over 866 tensors | GGUF-only vendor file: in-file MTP block (`blk.64`) + a separate `qwen3vl_merger` projector, so llama.cpp is the only engine; the `:Mix-13G` tier (12.99 GB, 3.80 bpw) is its A/B control, never the default (sizes read 2026-10-22, Hub `files_metadata`, byte-identical on `.31`/`.35`) |

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

- `recipes/cybersec/mods/provide-uncensored-chat-template` — fetches the drowzeys uncensored chat template (+ the
  YaRN rope overlays) and writes `/cache/runtime/uncensored-template/chat_template.jinja`, which
  arm 2 passes to `--chat-template`. Idempotent from the artifact (a non-empty template
  short-circuits). Needs the node token.
- `recipes/cybersec/mods/graft-dsv41-ablit-wo-b` — fetches the author's `apply_mia_exl3_wob.py` + the EXL3 sidecar
  and grafts them onto the stock pack (`littlecedar/…-2.9bpw-with-engram`) under
  `/cache/runtime/dsv41-ablit`. Idempotent from
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
  the combined `littlecedar/DeepSeek-V4.1-Flash-EXL3-2.9bpw-with-engram` pack (its weight shards are
  the Mia 2.9bpw shards byte-for-byte) and not the official MXFP4 repo.
- Engram tables (~95 GiB each) are **not** in the EXL3 weights, but the combined pack this arm
  grafts onto carries them under `engram/`, so since 2026-10-17 arm 5 reads them there via the
  launcher's `--stock-model` and mounts no fetch mod; `recipes/cybersec/mods/dsv41-engram-fetch` is
  now mounted by no shipped recipe and stays as the fresh-node/pre-warm path (`attic/ds4/AGENTS.md`
  §12.7). GPU memory utilisation stays ≤ 0.85.

Graft never in place: the graft's `--src` is a mod-built **symlink view** of the stock snapshot
(absolute symlinks, `engram/` excluded) and its `--dst` is the runtime cache; the mod compares
`realpath -m` of both and dies if they are equal (the author's script also refuses it). The view
exists for two reasons: the script `os.link`s each shard it does not edit, which hardlinks the
snapshot's own *relative* `../../blobs/…` symlink and does not resolve from the graft tree; and it
`shutil.copytree`s `engram/` (~189 GiB). The lane guard asserts both.


---

## 7. Validation ritual

After any edit here:

```bash
H=$PWD/.local/sparkrun-home
for f in recipes/cybersec/*.yaml; do HOME="$H" sparkrun recipe validate "$f"; done
uv run python -B -m unittest tests.test_cybersec_recipes -v
for s in recipes/cybersec/mods/provide-uncensored-chat-template/run.sh recipes/cybersec/mods/graft-dsv41-ablit-wo-b/run.sh; do bash -n "$s"; done
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

**SUPERSEDED 2026-10-15 — kept as history, because this is why the arm was held unshipped.** The
model-side half still stands (the card's route is vLLM's `CompressedTensorsW4A4`); the
distribution half does not: a direct `docker pull` by digest measured **76–142 MB/s** on `.34`, and
the pinned image now sits with an identical RepoDigest on the head, `.34`, and `.35`, which makes
sparkrun's digest short-circuit skip the transfer entirely. See *Arms 3 and 4 — the
card-documented vLLM routes (2026-10-15)* below.

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
  above). **Both open halves closed on 2026-10-15** — `Qwen4ExpForConditionalGeneration` imports
  from `vllm/models/qwen4_exp`, and the distribution figure was the *relay's* stream, not the
  network — see *Arms 3 and 4 — the card-documented vLLM routes (2026-10-15)* below. Pinning
  `--quantization` to another value is **not** a fix to try blindly: arm 1 shows
  SGLang reads the right scheme from `config.json` when the export is one it implements.

### Arms 3 and 4 — the card-documented vLLM routes (2026-10-15)

**Status: the loader/route gate is closed; arm 3 now has a boot receipt, arm 4 does not.**
Everything that follows the receipt subsection is **loader-level** evidence: which scheme class
vLLM's compressed-tensors config builds for each checkpoint's own `quantization_config` groups, and
which arch class imports. Arm 3's route boots and answers but the checkpoint degenerates (the
receipt subsection below), so its index row stays out; arm 4 still owes a boot. "Route established"
is not "verified".

#### Arm 3 — the vLLM route boot receipt (2026-10-15)

Four bounded boots of `recipes/cybersec/nex-n2.5-mini-uncensored-nvfp4-vllm.yaml`, one at a time on
`.34`, each stopped after capture — receipt `~/benchmarks/cybersec-nex-20261015/` (stories, per-boot
serve logs, probe JSONs, image line), job `9e32c36ca6496294_8ed3ce77d78f`, harness
`.scratch/cybersec/nex-vllm-boot.sh`, copied to `~/benchmarks/cybersec/nex-vllm-boot.sh` on
the head — md5 `997aa02e0576037ac462d9dd3a72b0a9` on both, recorded so the harness survives the
head even though `.scratch/` is untracked.

| boot | question | answer |
|---|---|---|
| 1 — 11:45 | does the route come up at all? | **yes.** HTTP ready at TTR port-open 257.6 s, `GET /v1/models` = `orcarouter/Nex-N2.5-mini-Uncensored-NVFP4`; image `ghcr.io/spark-arena/dgx-vllm-eugr-nightly@sha256:7717585a…` (resolved ID `c654ae41…`); EngineCore init 128.8 s, graph capture 2 s, 113.54/121.69 GiB free at startup. First probe: `finish=length`, `content: null`, `reasoning` 96 chars, `completion_tokens_details.reasoning_tokens = 96/96` — all generated tokens were *reasoning*, none surfaced as text |
| 2 — 12:01 | does the recipe's `reasoning_effort: none` default suppress thinking? | **no.** Server default and explicit per-request shapes are identical: `content: null`, `reasoning` 96 chars of `duct…`, `reasoning_tokens 96/96` |
| 3 — 12:08 | is `enable_thinking` the real gate, on a realistic prompt? | **yes to the gate**: `{"enable_thinking": false}` moves the text into `content` (1600 chars) where both `reasoning_effort` shapes leave `content: null` (reasoning 1600 chars). Every shape still degenerates to `duct…` |
| 4 — 12:22 | greedy artifact, or the checkpoint? | **the checkpoint.** Sampled (`temperature 0.7, top_p 0.95`) thinking-on returns `!`-repetition and never closes `</think>` at 800 tokens; the answer-channel shape fills `content` (300 chars) with the same `!`-repetition. Degeneracy is not a greedy or a budget artifact |

**Conclusion.** The route gate is closed — the card's own vLLM route loads this export
(`CompressedTensorsW4A4Fp4`), boots in ~4.3 min, and answers HTTP — and the arm still **cannot
serve**: generation degenerates to one repeated token under every tested configuration. Per the
standing rule the recipe stays as the route record with **no index row**. Three reusable facts from
the boots: the documented `reasoning_effort: none` is inert on this route; `enable_thinking: false`
is the working switch; and this engine's admission/engine log lines land in the **sparkrun job
log**, not in the container's stdout (preamble only) or its `/tmp` (the mod's log only).

#### Why no vLLM image was runnable at the start: the pinned images are SGLang builds

`docker images` (read-only SSH, 2026-10-15) plus `docker image inspect` labels:

| node | images (before this session) | verdict |
|---|---|---|
| head, `.30`–`.33` | `littlecedar/dgx-spark-dsv41:canary-roce` = `oci-relay/pinned:f7fbc4f8…`, ID `18e36391488e`, 33.5 GB | **SGLang** — labels `ai.sglang.image.tag = lmsysorg/sglang:dev-dsv41`, `Entrypoint = ["python3","-u","/opt/dsv41/boot.py"]`, and `docker run … pip show vllm` answers `ModuleNotFoundError: No module named 'vllm'` |
| `.34` | `oci-relay/pinned:be1d654c…` (33.4 GB) | **SGLang** `lmsysorg/sglang:v0.5.20` |
| `.34` | `oci-relay/pinned:847e5d37…` (33.8 GB) | **SGLang** `lmsysorg/sglang:nightly-dev-20260908-20ca564b` |
| `.35` | `lmsysorg/sglang:dev-cu13` (36.1 GB) | **SGLang** — the container both negative recipes name |

So **neither `oci-relay/pinned:<sha>` image on `.34` was the missing vLLM build**: both carry
`ai.sglang.image.tag` and `org.opencontainers.image.source = github.com/sgl-project/sglang`. `.30`–`.33`
were also holding the in-flight TP=4 job (`sparkrun_a4c699c1299bbbdf_…_node_0..3`, 12 h, healthy),
which is why the free window is `.34`/`.35`.

#### The image that does carry both routes, and what it cost to get there

`ghcr.io/spark-arena/dgx-vllm-eugr-nightly:latest` resolved on 2026-10-15 to digest
`sha256:7717585a874b07dcd9df9f5ea776985b591cb3c213abd0e8ebe4a680e3e07214` (26 layers, **11.26 GB
compressed / 25.03 GB on disk**; labels `dev.sparkrun.source-tag = nightly-20261014`,
`dev.sparkrun.vllm-version = 0.32.0rc1.dev161+g660bd051d.d20261014`,
`dev.sparkrun.vllm-hash = 660bd051d7de8101e6fb4299d1ce58b19e669f85`). A plain
`docker pull <repo>@sha256:7717585a…` on the head, `.34`, and `.35` left **one image ID
(`sha256:c654ae419ca3792be11f50f3970bd8e04034569c230f51d2b29b27a49b8efc27`) and one RepoDigest on
all three**, each pull finishing inside ~2 minutes. Logs: `~/benchmarks/_image-pulls-20261015/`
(owned by the orchestrator's prime-pull convention; this session added `vllm-nightly-20261014.log`
and `…-head.log`).

**The ~0.3 MB/s figure was the relay's stream, not the node's network.** Measured the same day,
fetching one blob of that manifest directly from ghcr:

```
# on .34  (curl -sL -o /dev/null -w 'rate=%{speed_download} B/s bytes=%{size_download} t=%{time_total}\n' \
#          -H "Authorization: Bearer $T" <blob URL>, --max-time 20)
rate=76309553 B/s bytes=1530920960 t=20.061983
rate=141605133 B/s bytes=2159268284 t=15.248517
# on the head
rate=83931911 B/s bytes=1258928814 t=14.999406
```

Consequence for a launch: sparkrun compares the *source* image identity (Id + RepoDigests) with
each target host's and **skips the transfer on a digest match**
(`sparkrun/containers/distribute.py:182-228`; it logs `Container image up-to-date on all N host(s)`
instead of `Container image stale on N of M host(s), syncing` at `:225`). With the image resident
by digest on head, `.34`, and `.35`, distribution never runs. If a transfer is ever needed, the
documented relay bypass is `container_distribution_provider: builtin` (or disabling the plugin) —
`docs/OCI_RELAY.md` in the sparkrun repo. **Do not generalize this to `:latest`:** the tag moved
again after the ornith lane's `b94ac8ac…` pin, so recipes here pin the digest.

#### Loader-level evidence (all containers `--rm`, `--network none`)

Arch and module (two throwaway probe scripts, `docker run --rm`, deleted from the node afterwards):

```
Qwen3_5MoeForConditionalGeneration   in vllm.model_executor.models.qwen3_5: YES
Qwen4ExpForConditionalGeneration     in vllm.models.qwen4_exp: YES
Qwen3_5MoeMTP                        in vllm.model_executor.models.qwen3_5_mtp: YES
Qwen4ExpMTP                          in vllm.models.qwen4_exp: YES
supported archs count: 394
```

Scheme mapping — feed each checkpoint's own `quantization_config` (from its pinned revision) to
`CompressedTensorsConfig.from_config` and ask which scheme the loader builds for a real layer name
(`probe2.py`, `probe3.py`):

```
# arms 3 — orcarouter/Nex-N2.5-mini-Uncensored-NVFP4  (format: nvfp4-pack-quantized, targets ['Linear'])
from_config: OK; target_scheme_map size 1
group_0: nvfp4_w=True nvfp4_i=True
  -> …schemes.compressed_tensors_w4a4_nvfp4.CompressedTensorsW4A4Fp4
get_scheme 5.mlp.experts.3.gate_proj -> CompressedTensorsW4A4Fp4      # the card's CompressedTensorsW4A4
get_scheme 11.self_attn.q_proj       -> None                          # ignored: BF16

# arm 4 — orcarouter/Qwen3.8-Flash-Next-Uncensored-NVFP4  (format: mixed-precision)
from_config: OK; target_scheme_map size 301; regex target re:.*mlp\.experts\..*proj$ present
group_0 (naive-quantized, FP8 per-channel, weight-only) -> …compressed_tensors_w8a16_fp8.CompressedTensorsW8A16Fp8
group_1 (nvfp4-pack-quantized, weight-only)             -> …compressed_tensors_w4a4_nvfp4.CompressedTensorsW4A4Fp4
get_scheme 5.mlp.experts.3.gate_proj -> CompressedTensorsW4A4Fp4
```

The one exception the probe raised (`AssertionError: Current vLLM config is not set`) is the probe
having no engine config, not a scheme refusal: with a stub `set_current_vllm_config()` the FP8
group constructs `CompressedTensorsW8A16Fp8`. **SGLang refuses the same config**
(`Other method (CompressedTensorsW4A16Sparse24) is not supported now`), which is exactly the
difference these two recipes exist for.

CLI surface, read from `vllm serve --help=all` in the same image: `--quantization` accepts
`compressed-tensors` (`QuantizationMethods`, `model_executor/layers/quantization/__init__.py:15-49`),
`--reasoning-parser qwen3` (`reasoning/__init__.py:155`), `--tool-call-parser qwen3_coder`
(`tool_parsers/__init__.py:193`), `--kv-cache-dtype` includes `bfloat16` (no bare `bf16`),
`--default-chat-template-kwargs` exists. **`VLLM_PLE_TABLE_MEMORY` does not exist in this build**
(no grep hit), so the q4 lane's TP=1 PLE-offload knob is a b12x-image feature; arm 4 keeps the PLE
table on device, as its SGLang TP=2 shape did.

#### What ships

`recipes/cybersec/nex-n2.5-mini-uncensored-nvfp4-vllm.yaml` (TP=1) and
`recipes/cybersec/qwen3.8-flash-next-uncensored-nvfp4-vllm.yaml` (TP=2, `min_nodes: 2`), both
digest-pinned to `sha256:7717585a…`, both carrying `--served-model-name {served_model_name}` and
`--revision {model_revision}`, both validating (`sparkrun recipe validate`) and rendering (`-n`).
Rendered arm 3 command:

```
taskset -c 5-9,15-19 vllm serve orcarouter/Nex-N2.5-mini-Uncensored-NVFP4
  --served-model-name orcarouter/Nex-N2.5-mini-Uncensored-NVFP4 --revision 9f11be0e80ff4b7670c7dbaacb213e9ad10e32a4
  --host 0.0.0.0 --port 8000 --tensor-parallel-size 1 --trust-remote-code --quantization compressed-tensors
  --kv-cache-dtype bfloat16 --max-model-len 262144 --max-num-seqs 16 --max-num-batched-tokens 4096
  --gpu-memory-utilization 0.85 --reasoning-parser qwen3 --tool-call-parser qwen3_coder --enable-auto-tool-choice
  --default-chat-template-kwargs '{"enable_thinking": false}'
```

Neither recipe replaces its SGLang sibling: the SGLang arms stay the documented negatives, and the
new files carry no index row until a boot receipt exists.

#### What a boot costs, and what is not started

The 2026-10-14 reclamation deleted both negatives' checkpoints from every node's cache, so a boot
re-fetches. Measured per-node Hub fetch (ranged GET of each repo's largest file, `--max-time 20`):
`.34` `rate=94453157 B/s bytes=1889009787 t=19.999435`, `.35` `rate=100796412 B/s
bytes=2021122298 t=20.051530`, that is ~95–100 MB/s per node.

- **Arm 3: 23.9 GB on one node** (~4–5 min at that rate; largest file 2.82 GB).
- **Arm 4: 183.5 GB per node** — the largest single file is `model-00002-of-00017.safetensors` at
  **102.4 GB** (the bf16 PLE n-gram tensor), so ~31 min per node if both fetch independently, longer
  if they share the upstream: ~367 GB of cache growth. Disk after the image pulls: `.34` 1.9 TB
  free, `.35` 1.8 TB free, so it fits. A fetch saturates that node's NIC and contends with any
  concurrent dist on the same node, but touches no running container.

Nothing was started: the fetch is a cost decision for the window owner, and `.34` was serving
another lane's workload when this was written.

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
  ***Superseded 2026-10-19:** the engram-ON ladder reads C1 **67.02 ± 3.19** t/s with C2/C5/C10
  **52.95 / 47.75 / 46.78** (n=5, `bench_484eb77839b4`, `~/benchmarks/cybersec-arm5-ladder-20261019/`);
  use those cells, not the 63.7 above.*
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
  the detached-graft variant). **Engram is OFF on this boot** (`recipes/cybersec/mods/dsv41-engram-fetch` runs
  detached and had not finished), so every number here is the **degraded, no-Engram** path — the
  ds4 lane's 73.0 t/s figure carries Engram. A second boot after the fetch completes would pick
  the tables up; the C1/battery comparison against the stock arm should be re-read with that in mind.

**2026-10-17 — re-boot on the combined pack: the Engram dedup done, engram ON.** The arm grafts from
`littlecedar/…-2.9bpw-with-engram` (owner decision 2026-10-15: combined repo everywhere) and
`--stock-model {model}` stopped being decorative — the launcher resolves the Engram tables from the
pack named there when the served dir has none (commit `d7c879b`).

- **The author's script `os.link`s every shard it does not edit, and `os.link` does not dereference
  a symlink.** Verified from the script source plus a direct link-semantics experiment on the node:
  `os.link(symlink, dst)` issues `link(2)` and hardlinks the *symlink inode*, so each untouched shard
  became a hardlink of the snapshot's own *relative* `../../blobs/…` symlink, which cannot resolve
  from the graft tree; and `shutil.copytree` dereferences the `engram/` directory, i.e. 189 GiB of
  real bytes. Measured on `.34`, a graft straight from the combined snapshot produced a **386 GiB**
  tree (`/` went 2.2T → 2.7T used). **That tree was deleted, so its composition is not
  reconstructible:** the rewritten shards (118.58 GiB) plus the `engram/` copy (~189 GiB) account for
  ~308 GiB, and the residual ~78 GiB is **unexplained — most likely the script's `copy2` fallback**
  (`apply_mia_exl3_wob.py:76`), which *follows* a symlink and would materialize unedited shards as
  real bytes. The dedup as first wired *added* ~190 GB per node.
- **Fix (commit `a61890a`).** The mod builds a 50-entry `--src` symlink view of the stock pack
  without `engram/`, hands that to the script, and links `${STOCK}/engram` into the graft tree; the
  repair runs before the `ABLIT_META` short-circuit, so a graft already on a node is fixed on its
  next launch. Re-boot receipt (task `2f9a8f3e60a51ee4_948390812ad5`, receipt
  `~/benchmarks/cybersec-arm5-20261017/`): `src view: … (50 entries, engram/ excluded)`, graft
  **148 s** (`.34` 22:32:29→22:34:57) and **137 s** (`.35` 22:35:12→22:37:29) — ~390 s before,
  because the table copy is gone — `verified n_edited=104 method=graft-keys-l10-35-wo_b-exl3-mul1-k5`,
  `dsv41-ablit` **119 GiB** (`du` == `du --apparent-size`: 24 shards with `nlink=1` totalling
  118.58 GiB; the other 15 shards and `engram/` are links),
  and the launcher boot line `engram=<stock>/engram`.
- **Serve contract:** `GET /v1/models` → `drowzeys/DeepSeek-V4.1-Flash-Abliterated-Cybersecurity-Unleashed`
  at **865.9 s** TTR (graft + cold rank cache `rank0of2-50cbbba13afcf8991af9.bin`, weights 299 s,
  `reserved 102.98 GiB`); `17*19` → `323` with `chat_template_kwargs {"enable_thinking": false}`.
- **Storage reclaimed with it:** the stale `Mia-AiLab__…-a54d5c5d` trees (299 GB `.32`, 296 GB
  `.33`) and their `dsv41-engram` pre-warms removed (both 1.6T → 1.3T used); the wasteful
  469 GB/459 GB trees on `.34`/`.35` deleted before the fixed re-boot. Per node, the two TP=2 arms
  now cost the combined pack (386 GB) plus this arm's 119 GiB graft — one table set between them.


---

### Arm 6 — `orcacyber-nano-1.0-15.7g-gguf-llamacpp` — POSITIVE (TP=1)

- Boot: task `f5f1433d7dd0b74e_a4bf874feb5a`, container
  `sparkrun_f5f1433d7dd0b74e_a4bf874feb5a_solo` on `.35` (0 containers before and after the boot).
  `GET /v1/models` → `{"id":"orcarouter/OrcaCyber-Nano-1.0","capabilities":["completion",
  "multimodal"],"n_ctx":32768,"n_ctx_train":262144,"n_params":27320697856}`, `owned_by: llamacpp`.
- TTR **30.29 s** (launch → first 200), warm by construction: the image pin was already verified
  (`no transfer`), the 15.7G tier + F16 `mmproj` were rsynced from `.31` over the rail
  (`.31` → `.35`), sparkrun's model stage was 6.1 s of it and llama-server's own load 16.5 s
  (serve log: `model loaded`, `n_slots 4`, `n_ctx_slot 32768`, `kv_unified 'true'`, MTP draft
  context created against the target GGUF).
- **C1** (`bench_2e3d1141622c`, `benchmarking/concurrency-ladder.yaml` with `-b concurrency=1`,
  `--skip-run`, d0 pp 2048 tg 128, n=5): **25.62 ± 2.31 t/s** (28.50 / 25.77 / 25.10 / 21.63 /
  27.10), prefill 742.9 ± 72.0 t/s, ttfr 2,399 ms. Every ladder value appears in the serve log as
  that slot's `eval time` line, and those lines carry `draft acceptance 0.40–0.86, mean len
  2.19–3.57` — the counters are what attribute the speed to the in-file MTP head.
- Not measured on this boot: C2/C5/C10, an MTP-off control (`-o spec_type=none`), the 13G tier, any
  quality battery, and any vision request (`multimodal` is the server's capability advertisement).
  Receipt `~/benchmarks/orcacyber-nano-20261022/` (`serve.log`, `ladder.yaml`/`.json`/`.csv`,
  `ttr.txt`).

## Recipe comment archive (2026-10-14)

Provenance and history removed from the lane's recipe `#` comments on 2026-10-14 — recipe comments
now carry only facts crucial to running the shipped arm (the README carries the how-to facts).
Organised per recipe file.

### `qwen3.8-27b-uncensored-nvfp4-sglang.yaml`

- `mamba_ssm_dtype: bfloat16` was annotated in-recipe as a "checkpoint-derived override, as in the
  qwen3.8-27B NVFP4 recipe" — that lineage is the qwen3.8-27B lane, whose evidence is specific to
  *that* checkpoint.

### `qwen3.8-27b-ablit-cyber-unlock-nvfp4-dflash2-sglang.yaml`

- `speculative_draft_tokens: 8` was annotated with the value the overlay author's own seat used
  instead: `n=7`.

## From recipes/cybersec/README.md (2026-10-14)

Material displaced from the lane README when it was rewritten to shipped-recipes-only form on
2026-10-14 (lane-doc consolidation). Kept verbatim so nothing is lost; the §1–§8 numbering above is
untouched.

### Old pointer line

> Working here? Read [`AGENTS.md`](AGENTS.md) first — it is the lane's durable guide (gating,
> token prerequisite, traps, receipts). This README is the human-facing summary.

### The arm table (with measurements)

| # | recipe | runtime | model | TP | C1 t/s (d0 / d8192) | battery | status |
|---|---|---|---|---|---|---|---|
| 1 | `qwen3.8-27b-uncensored-nvfp4-sglang` | sglang | [orcarouter/Qwen3.8-27B-Uncensored-NVFP4] (mixed NVFP4+FP8, `qwen3_5`, vision) | 1 | **10.2 / 9.7** | 37/37 | boots, `GET /v1/models` = repo id |
| 2 | `qwen3.8-27b-ablit-cyber-unlock-nvfp4-dflash2-sglang` | sglang | [sakamakismile/Qwen3.8-27B-AEON-ULTIMATE-UNCENSORED-NVFP4] **+ the [drowzeys keys overlay]** (chat template) + [z-lab/Qwen3.8-27B-DFlash2] draft | 1 | **33.3 / 26.2** | 37/37 | boots, `GET /v1/models` = repo id; uncensored template confirmed in the serve log |
| 3 | `nex-n2.5-mini-uncensored-nvfp4-sglang` | sglang | [orcarouter/Nex-N2.5-mini-Uncensored-NVFP4] (`qwen3_5_moe`, 256E top-8, vision) | 1 | — | — | **negative** under SGLang (NaN sample-time logits → CUDA device-side assert); its card's vLLM route now has a boot receipt — route works, checkpoint degenerates to one repeated token in every probe, no index row — see AGENTS.md |
| 4 | `qwen3.8-flash-next-uncensored-nvfp4-sglang` | sglang | [orcarouter/Qwen3.8-Flash-Next-Uncensored-NVFP4] (`qwen4_exp`, NVFP4 experts / FP8 attention) | 2 | — | — | **negative** — SGLang's compressed-tensors loader refuses the export's scheme (`CompressedTensorsW4A16Sparse24` unsupported); the card's vLLM route is the next step — see AGENTS.md |
| 5 | `deepseek-v4.1-flash-abliterated-cyber-tp2-tensorfold-sglang` | sglang shim → TensorFold | stock [combined littlecedar/DeepSeek-V4.1-Flash-EXL3-2.9bpw-with-engram pack] **+ the [drowzeys wo_b sidecar]** | 2 | **63.7 / 67.7** | 36/37 | boots, `GET /v1/models` = the overlay repo id (1M ctx); graft measured at 148 s / 137 s per node (2026-10-17, on the combined stock), inside the 600 s hook budget; refusal probe 0/8 explicit refusals (1/8 completed; 7/8 truncated-empty at the cap) — see AGENTS.md |

**Cache reclamation (2026-10-14, owner space directive):** the two **negatives'** checkpoints were
deleted from every node's HF cache — an arm with no working serve ships no artifact —
`orcarouter/Qwen3.8-Flash-Next-Uncensored-NVFP4` (**183.5 GB/node**, `.32`+`.33`) and
`orcarouter/Nex-N2.5-mini-Uncensored-NVFP4` (24 GB). A re-test re-fetches. The three positives'
checkpoints — including arm 5's stock combined `littlecedar/DeepSeek-V4.1-Flash-EXL3-2.9bpw-with-engram`
pack, which carries the Engram tables the launcher reads — are **kept cached**. The
`Mia-AiLab/DeepSeek-V4.1-Flash-EXL3-2.9bpw` tree is **reclaimable** since 2026-10-17 (its shards
survive inside the combined pack) and is named as such in `mad-science/STORAGE-POLICY.md`.

`[bracketed]` links resolve at the bottom of this section. Every arm is one recipe; the measured
receipts (boot id, `GET /v1/models` answer, `decode-triage` run, house battery) live in
[`AGENTS.md`](/attic/cybersec/AGENTS.md) §8 so this table stays readable.

### Two of the five arms are overlays

Arms 2 and 5 are *not* checkpoints. The upstream repos ship **no weights** — they are a chat
template / a config / a small `attn.wo_b` sidecar plus wiring. Both are handled by a mod that
builds the arm's real artifact inside the container, from the container's own HF cache, and never
writes the source snapshot:

| arm | overlay repo | body / stock | what the arm adds | mod |
|---|---|---|---|---|
| 2 | [drowzeys keys-Qwen3.8-27B…Single-DGXSpark] | `sakamakismile/…-AEON-ULTIMATE-UNCENSORED-NVFP4` | the cybersecurity-unlock **chat template** (+ the YaRN rope overlays for the 1M route) | `recipes/cybersec/mods/provide-uncensored-chat-template` |
| 5 | [drowzeys DeepSeek-V4.1-Flash-Abliterated…Unleashed] | combined `littlecedar/DeepSeek-V4.1-Flash-EXL3-2.9bpw-with-engram` pack | the `layers.10-35 attn.wo_b` **EXL3 mul1 K=5 sidecar**, grafted | `recipes/cybersec/mods/graft-dsv41-ablit-wo-b` |

For arm 5 the author's `INSTALL.md` pairs a stock pack with a sidecar and forbids mixing them —
the combined pack's EXL3 weight shards take the **EXL3** sidecar and the EXL3 graft script;
native / Pollard / TR3 take the FP8 pair. The lane ships the EXL3 pair because the combined pack
(Mia shards, plus the Engram tables) is what our 2-node EXL3 engine serves.

### Served model id — the convention

Every arm renders `--served-model-name {served_model_name}`, never `{model}`. On a real launch
sparkrun rebinds `{model}` to the prepared on-disk snapshot, so a `{model}`-derived id would make
the server advertise a `/cache/huggingface/hub/models--…` path to every client, the proxy, and any
benchmark that sends the id. `served_model_name` is the arm's repo id:

| arm | served id |
|---|---|
| 1 | `orcarouter/Qwen3.8-27B-Uncensored-NVFP4` |
| 2 | `sakamakismile/Qwen3.8-27B-AEON-ULTIMATE-UNCENSORED-NVFP4` |
| 3 | `orcarouter/Nex-N2.5-mini-Uncensored-NVFP4` |
| 4 | `orcarouter/Qwen3.8-Flash-Next-Uncensored-NVFP4` |
| 5 | `drowzeys/DeepSeek-V4.1-Flash-Abliterated-Cybersecurity-Unleashed` |

For the two overlay arms the served id is the **arm's identity** (what the registry ships and
what a client should ask for), not the body pack: arm 2 serves the AEON body through the cyber
template, and arm 5 serves a graft tree that exists only on the node.

### Reproduce

```bash
# from the run-from dir on the head node, recipes symlinked by basename
sparkrun run qwen3.8-27b-uncensored-nvfp4-sglang -H <node>
curl -s http://<node>:8000/v1/models        # id == the arm's repo id

sparkrun benchmark performance qwen3.8-27b-uncensored-nvfp4-sglang -H <node> \
  --profile benchmarking/decode-triage.yaml --output runs/<arm>.yaml
python3 tools/quality-battery.py http://<node>:8000/v1 --tier both --json runs/<arm>.battery.json
```

Arm 5's graft (a large on-node rewrite of the stock EXL3 shards) runs **synchronously and
fail-closed** in the mod — the serve command does not wait on a background step; see AGENTS.md §6.

### Other surfaced arms (not shipped)

Recorded, over the 1–2-node bar or license-blocked; see `mad-science/TODO.md` §cybersec:
`orcarouter/GLM-5.3-Flash-Uncensored-NVFP4` (205.1 GB), `drowzeys/keys-MiMo-V2.6-Pro-RL-Jarrelscy-ARVQ-Abliterated`
(315.7 GB ⇒ ≥3 nodes), `drowzeys/MiMo-V2.6-Flash-RL-Abliterated` (310B), `orcarouter/DeepSeek-V4-Flash-Vision-Uncensored` (304B).

## 2026-10-16 re-measure: the SGLang engine gate changed form (arm 3, nex)

Purpose: the three SGLang cybersec arms now pin `lmsysorg/sglang:dev-cu13@sha256:0b3e3970…`, and the
tag had moved again since the 2026-10-13/14 receipts — the cached image on `.34`/`.35` was
`@sha256:0a1ba33a…`, while today's boot resolved `0b3e3970` (arm64 manifest `35206090…`, engine
`0.0.0.dev1+gc15edf314`; the 2026-10-15 advisory pass had read `ga6a8c5601`). Boot evidence and
probes: `head:~/benchmarks/pins-20261016/` (`nex-sglang-evidence.txt`, `nex-sglang-boot.log`).

`nex-n2.5-mini-uncensored-nvfp4-sglang` reached ready on `.35` on that image (sparkrun exit 0; TTR
104.1 s port-open, 112.3 s HTTP-ready). **The CUDA device-side assert is gone** — the container log
carries no `device-side assert` / `NaN` / `CUDA error` line — and `/v1/chat/completions` answers. But
every probe degenerates: three greedy probes (default; `chat_template_kwargs
{"enable_thinking": false}`; `{"reasoning_effort": "none"}`), 64 tokens each, all returned 64
identical `!` characters, the switch only moving them between `reasoning_content` and `content`. That
is the failure mode the vLLM route showed on 2026-10-15 (single repeated token at 800 tokens), so the
two engines now agree: **the checkpoint, not the engine, blocks this arm.** The SGLang negative
stands; `metadata.caveats` on the recipe and the arm-3 block in `recipes/cybersec/README.md` were
corrected to this state.

The pin is the other half of the receipt: an arm booted today silently runs a *different* SGLang
build than the 2026-10-13/14 receipts did, which is what the digest pin now freezes.

### Links (as referenced by the material above)

[orcarouter/Qwen3.8-27B-Uncensored-NVFP4]: https://huggingface.co/orcarouter/Qwen3.8-27B-Uncensored-NVFP4
[sakamakismile/Qwen3.8-27B-AEON-ULTIMATE-UNCENSORED-NVFP4]: https://huggingface.co/sakamakismile/Qwen3.8-27B-AEON-ULTIMATE-UNCENSORED-NVFP4
[z-lab/Qwen3.8-27B-DFlash2]: https://huggingface.co/z-lab/Qwen3.8-27B-DFlash2
[drowzeys keys-Qwen3.8-27B…Single-DGXSpark]: https://huggingface.co/drowzeys/keys-Qwen3.8-27B-NVFP4-DFlash2-Ablit-Cybersecurity-Unlock-1M-Context-YARN-Single-DGXSpark
[orcarouter/Nex-N2.5-mini-Uncensored-NVFP4]: https://huggingface.co/orcarouter/Nex-N2.5-mini-Uncensored-NVFP4
[orcarouter/Qwen3.8-Flash-Next-Uncensored-NVFP4]: https://huggingface.co/orcarouter/Qwen3.8-Flash-Next-Uncensored-NVFP4
[Mia-AiLab/DeepSeek-V4.1-Flash-EXL3-2.9bpw]: https://huggingface.co/Mia-AiLab/DeepSeek-V4.1-Flash-EXL3-2.9bpw
[combined littlecedar/DeepSeek-V4.1-Flash-EXL3-2.9bpw-with-engram pack]: https://huggingface.co/littlecedar/DeepSeek-V4.1-Flash-EXL3-2.9bpw-with-engram
[drowzeys DeepSeek-V4.1-Flash-Abliterated…Unleashed]: https://huggingface.co/drowzeys/DeepSeek-V4.1-Flash-Abliterated-Cybersecurity-Unleashed
[drowzeys keys overlay]: https://huggingface.co/drowzeys/keys-Qwen3.8-27B-NVFP4-DFlash2-Ablit-Cybersecurity-Unlock-1M-Context-YARN-Single-DGXSpark
[drowzeys wo_b sidecar]: https://huggingface.co/drowzeys/DeepSeek-V4.1-Flash-Abliterated-Cybersecurity-Unleashed
