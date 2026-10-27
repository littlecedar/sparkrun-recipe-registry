# llama.cpp on GB10 — the runtime tier, the GGUF arch map, and the standing policy

Registry-level working note for the `## Runtimes (registry-level)` item in
[`TODO.md`](TODO.md). The *lane* arm built on it is
`recipes/explore/mellum2.1-12b-a2.5b-q4km-thinking-llamacpp.yaml`; its measured numbers go in
`recipes/explore/README.md` and the root index, not here.

Status legend: **VERIFIED** = measured in this registry (date + command/receipt); **READ** =
upstream/installed-source reading; **PENDING** = not yet measured here.

## 1. The GB10 tier — pinned, and what is inside it (VERIFIED 2026-10-17)

sparkrun maps `runtime: llama-cpp` on GB10 to `scitrera/dgx-spark-llama-cpp:latest`
(`platforms/dgx_spark.py`, READ, and it forces `{"mmap": False}` unless a recipe opts back in with
`mmap: true`). The tag floats per build (458 tags on Docker Hub), so the first arm pins tag +
digest:

| fact | value |
|---|---|
| pin | `scitrera/dgx-spark-llama-cpp:b10549-cu131@sha256:ad14055470c2bd5c2b4c088dc5727d950da00f62408f438f4f3833c704af0dca` |
| local image | `sha256:2dcf49ada913a53eac42c5a24087e695876a508a2db5346c04b583070367c3f9`, arm64, 2.58 GB, created 2026-08-21 |
| tag ↔ digest | `latest` and `b10549-cu131` carry the same digest (Docker Hub API, 2026-10-17) |
| engine | llama.cpp `0.1.2-dev (build 1, commit b2e5e9b)`, GNU 13.3.0 aarch64, CUDA 13.1.1 |
| flags present | `--jinja` (default **enabled**), `--reasoning-format {none,deepseek,deepseek-legacy}` (default auto), `--reasoning [on\|off\|auto]`, `--chat-template-kwargs`, `--parallel`, `--kv-unified` (`-kvu`, default: enabled only when slots are auto), `--flash-attn [on\|off\|auto]`, `-ctk/-ctv` cache types, `--alias`, `--no-webui`, `--metrics` |
| `rpc-server` | **absent** — the image ships `llama-server` only, so the experimental multi-node RPC path cannot be exercised with this tier |
| `--no-mmap` | accepted but marked DEPRECATED in favour of `--load-mode`. **The GB10 platform's forced `{"mmap": False}` never reaches a template recipe** (see §3), so the arm asks for it itself — as `--load-mode none` since 2026-10-27 (same policy, `common/arg.cpp:2672`), because the deprecation warning's own "use `--load-mode mmap`" hint names the opposite mode |

**The fast route is the ref, not the image** (VERIFIED 2026-10-22): `b2e5e9b` decodes **114.2 / 113.9 t/s**
where `a37cc4610` gives **100.3 / 98.7** on the same bytes, same node and same flags, and this image
carries **no patches** — its Dockerfile clones `ggml-org/llama.cpp` at the tag — so treat the pin as a
convenient carrier of an old upstream ref, not as a tuned build. Pick by which archs the arm needs:
`b2e5e9b` for speed, `a37cc4610` for Mellum MTP / Kolibri-1 / flint. Measurements and the flag-by-flag
elimination: `attic/explore/AGENTS.md` §"The residual ~15 % is the upstream ref era".
**Mellum MTP is not a reason to take `a37cc4610` for speed** (VERIFIED 2026-10-22, `.32`): the ref does
carry the head, but a draft-length sweep of `--spec-draft-n-max` 1–8 (same GGUF, same flags, three
128-token greedy requests per cell, baseline in the same window) peaks at **103.4 ± 2.8 t/s with one
drafted token** — the vendor card's own recommendation — against the ref's own no-MTP baseline of
**101.5 ± 0.7**, and every longer draft is slower: **90.0 / 75.9 / 66.6 / 51.4 / 47.7 t/s** at 2 / 3 /
4 / 6 / 8. Mean accepted length saturates at 2.0–2.3, so the verify pass costs more than the drafts
save. Pick the ref for Kolibri-1 / flint; speculative decoding buys nothing on this model. Receipt:
`~/benchmarks/mellum-mtp-draft-20261022/`.


Receipt: `~/benchmarks/llamacpp-pin-20261017/pull.txt` + `llama-server-help.txt` (head), pulled from
`.34`. Exec-time loading needs no extra env: a container started `sleep infinity` + `docker exec`
finds `libllama-server-impl.so` (measured 2026-10-17; the library lives in `/usr/local/lib` and the
image's `LD_LIBRARY_PATH` does not name it, so this was checked rather than assumed).

**The pin resolves to exactly that image (VERIFIED 2026-10-17 at the first boot).**
`docker buildx imagetools inspect` on the pinned list digest returns the arm64 manifest
`sha256:ba199b43b7ed00188c0285a44af35789c7079b033ce956fff0cf19f81d34a449`, whose `config.digest` is
`sha256:2dcf49ada913…` — the boot's container `.Image` on `.34`. (The list also carries an
`unknown/unknown` attestation manifest, `sha256:f0763b27…`.)

## 2. GGUF arch map — which archs a stock image can load (VERIFIED 2026-10-16, re-checked 2026-10-17)

Loadable by a **stock** first-party image only if the wrapper's `general.architecture` is in upstream
llama.cpp. Present on master: `mellum`, `gemma4`, `laguna`, `qwen3*`, `gemma3*`, `deepseek4`,
`glm4moe`, `glm5-next`, `mimo2`, `kimi-k3`, `nemotron`, `minimax-m3`. **Absent** — fork-built image
required, which is the bring-up cost the lane items must budget: `kolibri1` (Kolibri-1),
`k2-horizon` (IFM).

| candidate | repo | quant | arch check |
|---|---|---|---|
| Mellum2.1-12B-A2.5B | `JetBrains/Mellum2.1-12B-A2.5B-Thinking-GGUF` `20b439426f` | Q4_K_M 8,071,295,264 B (card-recommended) | **verified here**: GGUF v3, 339 tensors, `general.architecture = mellum` (Range-read header, 2026-10-17) |
| humanizer-12b | Q4_K_M 7.10 GiB sibling | Q4_K_M | READ (2026-10-16) |
| Laguna-XS-2.1 | `poolside/Laguna-XS-2.1-GGUF` | Q4_K_M 18.88 GiB | READ (2026-10-16); *research doc had assumed a poolside fork — upstream now carries the arch* |

## 3. Plumbing facts that decide a GGUF recipe (READ, sparkrun 0.4.0 + first boot)

- `model:` carries the **`:quant` suffix** (`…-GGUF:Q4_K_M`). `model_file_selection` must NOT be set
  for GGUF (it errors on repos whose files do not identify exactly one model) — the `:quant` suffix
  is what selects a file.
- A `command:` template may write `-hf {model}`; on a real launch sparkrun rebinds `{model}` to the
  staged GGUF file and rewrites the first `-hf ` to `-m ` (`runtimes/llama_cpp.py`, READ);
  **measured at the first boot** — the container's `/tmp/sparkrun_serve.sh` ran `llama-server -m
  /cache/huggingface/hub/models--JetBrains--Mellum2.1-12B-A2.5B-Thinking-GGUF/snapshots/<pin>/Mellum2.1-12B-A2.5B-Thinking-Q4_K_M.gguf
  --alias JetBrains/Mellum2.1-12B-A2.5B-Thinking-GGUF …`, i.e. the staged file is the pin's own
  quant file and the alias survives, so `/v1/models` reports the HF repo id, not a cache path.
- **A `defaults:` flag-map key is consumed only on the command-less path.** With a `command:`
  template, `generate_command` returns the render after `-hf`→`-m`, `--split-mode`, `--alias`,
  skip-strip and `--mmproj` only — `build_flags_from_map`/`_special_flags` run in
  `_build_command` alone (read 2026-10-17). So `jinja:`/`webui:`/`mmap:` defaults are silent drops
  in a template recipe, the platform's forced `mmap: False` included; the arm names
  `--jinja --no-webui --no-mmap --cont-batching` as literals, and the repo's `InertDefaults` guard
  applies to a llama-cpp template arm unchanged.
- `--kv-unified` matters: with an explicit `--parallel N` the default flips to *disabled* (divided
  slots), passing `-kvu` keeps one shared pool, which is what lets a c1 request use the full
  `--ctx-size` while c10 still batches.
- **The served window is `meta.n_ctx`, not `max_model_len`.** llama.cpp's /v1/models entry carries
  no top-level window key, so the suite tools — which read `max_model_len` — treated this arm as
  window-less until 2026-10-17: the top needle rung filled the window exactly (130,964 prompt +
  108 completion tokens, empty reply) and a sibling probe 400'd ("exceeds the available context
  size", a wording the shrink-retry list still misses). Fixed in `e13ccd5`; the rung re-probes
  3/3 at `paced_target` 128,451 (receipt `~/benchmarks/mellum-gguf-20261017/recheck-needle/`).
- **The suite's 256-token needle budget is below this template's thinking spend.** Two 32k cells
  returned empty content with `completion == max_tokens`; `e13ccd5` records that shape as a
  budget-cut `TRUNCATED` (never a retrieval miss) and the rung re-probes at `--max-tokens 4096`.

## 4. Standing policy for GGUF arms

1. **When a GGUF sibling may replace a safetensors arm**: only with a boot receipt *plus* the lane's
   own battery on the GGUF — llama.cpp sampler defaults and `n_ctx` are not vLLM's, so the
   uploader's KLD/top-1 table is the card's claim and never our comparison.
2. **Sizing**: prefer the card-recommended quant unless the objective is size or FP4 (measure-before
   -ship: `model_dtype:` must be a dtype the estimator knows — `q4_k_m`, not `gguf-q4_k_m`,
   else `sparkrun recipe show` cannot size the arm).
3. **Transport**: a 7–80 GiB single file rides the 200 GbE fabric into the per-node HF cache like
   any other model; no `model_file_selection` narrowing is possible or needed.
4. **First llama.cpp arm = bring-up, not a variation** (image pin + template + reasoning-format +
   slot/ctx shape), per `attic/explore/MELLUM-21.md` §5.
5. **Keep the GB10 platform's forced `mmap: false`.** Measured 2026-10-19 in a same-window pair on
   `.34` (a variant recipe that drops the arm's literal no-mmap flag, spelled `--load-mode none`
   since 2026-10-27, because the flag-map key is inert on a template arm): mmap ON is at or below
   OFF at every ladder cell — C1 108.80 vs 110.64, C2 151.78 vs 151.87, **C5 196.48 vs 208.28
   (-5.7 %)**, C10 143.45 vs 144.82 — so the fault-through
   -unified-pool cost the platform comment predicts is real. Receipt
   `~/benchmarks/mellum-mmap-20261019/`.

## 5. First boot of the arm — measured (2026-10-17, `.34`)

`recipes/explore/mellum2.1-12b-a2.5b-q4km-thinking-llamacpp.yaml`; receipt
`head:~/benchmarks/mellum-gguf-20261017/` (`provenance.txt` holds the boot script's capture; the
suite legs ran after it).

- **TTR ≈ 100 s** — launcher 02:13:01 ET → `GET /v1/models` 200 at 02:14:41; container
  `6cbc227cde9b` with `.Image` = the pin's config digest (§1). Serve log
  (`/tmp/sparkrun_serve.log`): `load_model: initializing, n_slots = 8, n_ctx_slot = 131072,
  kv_unified = 'true'`.
- **The card's own quant, loaded as such:** `/v1/models` meta `n_params` 12,149,923,072 / `size`
  8,067,705,856 / `ftype` `Q4_K - Medium` / `n_ctx` 131,072 / `n_vocab` 98,304 / `n_embd` 2,304 —
  the head-read GGUF header (§2) confirmed by the loader. Served id = the HF repo id (§3).
- **Tool calling works with thinking split:** a tool request returned `finish_reason: tool_calls`,
  one `get_weather {"city": "Paris"}` call, `content` empty and `reasoning_content` populated (439
  chars) — `--reasoning-format deepseek` moving thinking out of the reply.
- **The thinking-budget trap, measured:** the boot script's 24-token plain-chat probe came back
  `content: ""` with `finish_reason: length` — the budget was spent inside the think block. Clients
  must raise `max_tokens`, or send `chat_template_kwargs: {"enable_thinking": false}` (the template
  writes an empty think block only on `false`).
- `/v1/completions` answers too, so raw-completion clients are served by the same process.
- **Same-boot suite (2026-10-17) — §4.1's bar is met for this arm:** house **37/37** (easy 19/19, hard
  18/18); hard arc 77.0% / gsm8k 93.5% (n=200 each); the `standard-suite` profile (tool-eval-bench)
  **97** (15 scenarios, 14 pass, 1 partial; deployability 84, responsiveness 54); bfcl **88.3%**
  (1095/1240) at `--bfcl-max-tokens 4096` — the raised-budget probe is now run, and it *settles* the
  shape: the 512-token default was the mechanism, not a capability limit. At 512 the leg scored 73.5%
  with `parallel` 46.5% / `parallel_multiple` 41.0% and **179** of those 400 questions cut to no call
  at all; at 4096 only **6** are cut (every one `finish_reason: length`) and the residual
  parallel-category loss is **multi-call shape** — 34 of the 65 failures emit exactly one call, 25
  emit a wrong set of two or more. Receipt `~/benchmarks/mellum-gguf-tools4096-20261017/`
  (+ `NOTE-budget-probe.md`); decode ladder
  C1 111.9 ± 0.3 /
  C2 151.1 ± 2.6 / C5 208.0 ± 2.8 / C10 146.4 ± 1.5 t/s (`bench_4247926b7b9a`) — c10 exceeds the arm's
  8 slots, so per-request decode spreads (32.9 ± 16.1 t/s) and the aggregate falls past c5.
- **Needle rungs:** 131k **3/3** at `paced_target` 128,451. 32k is 1/3 at the suite's 256-token
  default — the two empties are the thinking-budget class, not retrieval: depth 50 PASSes at
  `--max-tokens 4096` and depth 90 PASSes with `enable_thinking: false` (9 completion tokens, 0.74 s):
  retrieval is **3/3 by union** — 1/3 at the suite's 256 default, 2/3 at 4,096, 3/3 with the
  thinking-off probe. Two tool-side false-FAIL classes surfaced on
  this arm and are fixed in `e13ccd5` — llama.cpp's window arrives as `meta.n_ctx` (the 2 % clamp
  never ran; the 131k rung overflowed and 400'd on a wording the shrink-retry list missed), and an
  empty reply at `finish_reason: length` was scored as a retrieval miss (`tools/needle-haystack.py`
  now records `finish_reason` and marks that shape TRUNCATED). Originals keep their false FAILs; the
  re-runs and re-probes live in `recheck-needle/` beside the receipt note.