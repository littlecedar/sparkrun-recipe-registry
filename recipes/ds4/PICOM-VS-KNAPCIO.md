# picom vs knapcio: one model, two engines on four GB10s

The lane record (arms, boots, measurement tables) is
[the lane README](README.md#deepseek-v41-flash-knapcio-tp4-1m-sglang); this page only
compares the two engines serving the same checkpoint on the same four ranks. Every numeric cell
names its receipt; every mechanism cell names a source line or the flag that carries it. Nothing
here is a leaderboard row — the two arms do not run the same budgets and no cell was measured
interleaved.

## 1. What each is

**knapcio (`deepseek-v4.1-flash-knapcio-tp4-1m-sglang.yaml`)** is SGLang `sglang.launch_server` from
the image's `dev-dsv41` build (`da64c5cb`, staged tree `f80c91a4b`), TP=4 / EP=1 over RoCEnante RDMA,
1M context, DSpark k=5, driven by a lane mod that owns the memory line and the extra flags
(`mods/dsv41-sglang-overlay/launcher.py`). It optimizes the *production serve line*: one long-lived
process holding a 1M-token KV pool, 16 uniform request slots, a 16384-token prefill chunk, and SGLang's
paged attention, radix prefix cache and in-process multimodal stack as the tuning surface
(`launcher.py:148-300`).

**picom (`zz-deepseek-v4.1-flash-1017-picom-tp4-1m.yaml`)** is a from-scratch C++/CUDA engine
(`dsgb10_rank`, one process per node, its own RDMA ring) behind a Rust front-end (`dsfront`), from
`Picom-code/pico-dgx-ds4@7c123ad4` with two integrated PR patches (`Dockerfile.picom-ds41f`). It
optimizes *per-token decode cost at single stream*: every rank holds one quarter of a 1M model
GPU-resident, 16 session slots of which 4 hold the full window, drafts verify 5 tokens a step, and
session state migrates to a 12 GiB store plus a per-rank disk tier instead of a pre-sized KV pool
(`engine/server/main.cpp:295-296`, `docs/engine.md:451-523`).

## 2. Same model, different machine

| axis | knapcio (SGLang) | picom (dsgb10) |
|:--|:--|:--|
| Context budget | 1,048,576 served (`--context-length` from `defaults.max_model_len`); KV pool profiled at boot and pinned to 6,849,792 tokens on the stock loader under `MEM_FRACTION_STATIC` 0.78 (`launcher.py:148,156`, `launcher.py:217-236`) | 1,048,576 for the 4 big slots; the other 12 hold `max_ctx / 8` = 131,072 each (`engine/model/model.cu:79-88`, `kUnitMul` 8 at `engine/model/config.h:39`); no `max_model_len` in the recipe, no KV pool to pin |
| KV / session memory | one paged KV+SHA pool sized from MemAvailable at boot; fp8 KV; 128 SWA prefix tails reserved inside that budget (`launcher.py:268`, recipe `metadata.kv_dtype: fp8`) | compressed KV + index keys, ~890 B per position across all 40 layers, replicated (`docs/engine.md:90-116`); 12 GiB session-store pool, blocks of 64 KiB, spill to a per-rank 32 GiB disk tier (`docs/engine.md:451-523`) |
| Scheduler / admission | `MAX_RUNNING_REQUESTS=16` uniform slots; `--cuda-graph-max-bs-decode` follows the same number (`launcher.py:167`, live flags in `head:~/benchmarks/knapcio-live-20261117/README.md`) | 16 slots with 4 big (`--slots 16 --big-slots 4`, `recipes/ds4/mods/picom-launcher/launch.sh:190`); smallest-fit pick, small slots first so big ones stay for long requests (`engine/server/serve.cpp:1198-1205`); more requests than slots take turns of `--slice` 64 tokens (`docs/engine.md:615-700`) |
| Prefill | chunked at 16384 tokens (`CHUNKED_PREFILL_SIZE`, `launcher.py:178`); decode-between-chunks ships **off** (`PREFILL_DECODE_INTERVAL` 0, `launcher.py:278`) | whole request in `--prefill-rows` 8192 chunks; decode between chunks not built, so other requests wait one chunk (`docs/engine.md:451-460`) |
| Speculative decoding | DSpark, verify-all, k=5 (`SPEC_ALGO DSPARK` `launcher.py:219`, `DSPARK_BLOCK_SIZE` `launcher.py:240`); decoded accepts 3.9–5.8 tokens/step on the measured boot (`knapcio-bench-20261117/boot/serve-rank0.log`) | DSpark, 5 drafts (6 rows per session step including the bonus, `engine/dspark/dspark.h:27`, `engine/model/ops.h:34`); drafts in a one-request run or a batch of ≤8, a larger batch takes the plain loop (`docs/engine.md:615-700`); levers `DSGB10_BUDGET`, `DSGB10_DRAFT1`, `DSGB10_WIDE` (`launch.sh:190`, `engine/server/cmd.cpp:662-664`, `engine/model/spec.cu:38`) |
| Weights as served | checkpoint as shipped: native MXFP4/F8, 510 GB resident, Engram read from NVMe (`recipes/ds4/README.md` knapcio table; arm `metadata.model_dtype: mxfp4`) | same checkpoint converted once per rank to a 72.38 GiB `.dsw` file (≈289.5 GiB across 4 ranks) plus 50.7 GB Engram shards on that rank's SSD (`docs/engine.md:90-116`; lane README artifacts row) |
| Vision | in-engine native multimodal; the measured boot's gate line records full-budget native vision passing (`knapcio-bench-20261117/boot/serve-rank0.log:447`) | separate supervised ViT child on rank 0, `127.0.0.1:18950`, ~0.90 GiB, front-end reaches it by `--vision-addr` (`launch.sh:269-271`, PR #15 patch) |
| Tool calls | `--tool-call-parser deepseekv41` with `--reasoning-parser deepseek-v41`; name then argument pieces, `finish_reason: tool_calls` (`knapcio-live-20261117/README.md` probes 4 and 8) | dsfront parses the model's own tool-call text (`frontend/src/server.rs:1006`) and streams argument pieces (`server.rs:1073-1076`; `--stream-tool-args` at `launch.sh:242`, PR #7 patch) |
| Prefix / cache behavior | radix prefix cache with 128 SWA tails and cache reporting on; a repeated ~4.8k prompt reports `prompt_tokens_details.cached_tokens: 4608` (`launcher.py:268`, `knapcio-live-20261117/README.md` probe 6) | session table matched by longest shared *text* prefix, 64 shared bytes minimum (`frontend/src/session.rs:17`), state spilled per slot; every measured cell ran cold — `reused 0 (cold)`, `cached_tokens: 0` (`picom-ladder-20261117/README.md` falsifiers, `knapcio-live-20261117/README.md` probe 6) |
| Readiness (container start → HTTP ready) | 696.2 s port-open / **708.4 s** HTTP-ready, one cold boot (`knapcio-bench-20261117/README.md`) | **27.7 s** with per-rank artifacts cached; 166.4 s on the boot that had to convert weights and Engram (`picom-gap-20261117/README.md`) |

### Request surface (the live probe pair, 2026-11-18 knapcio serve and the pinned picom front-end)

Receipts: `head:~/benchmarks/knapcio-live-20261117/` (17 files, keyless anonymous probes) and the
picom front-end read at `7c123ad4` (`frontend/src/server.rs:522-538`, `frontend/src/main.rs:126-132`).

| axis | knapcio (SGLang) | picom (dsfront) |
|:--|:--|:--|
| Defaults when the request omits them | samples: three runs, three distinct answers (`02-defaults.json`) | `temperature` 1.0, `top_p` 0.95, `max_tokens` = cap 32,768 (`frontend/src/main.rs:126,130-131`) |
| Honored sampling / limits | vendor surface: `temperature`, `top_p`, `stop` (`matched_stop: 1`), `max_tokens` floor-checked with a 400 | `temperature`, `top_p`, `top_k` (approximate past ~256: candidate union capped at 64 logits/rank), `seed` (`mix64(seed) ^ pos`, reproducible), `max_tokens` / `max_completion_tokens`, `stop` (held-back partial tail), `stop_token_ids`, `ignore_eos` (`server.rs:522-545`) |
| Silently dropped | none found in the probed set | `min_p`, `presence_penalty`, `frequency_penalty`, `repetition_penalty`, `logit_bias`, `return_token_ids` — hand-written `r.get(...)` list, no unknown-key refusal (`server.rs:522-545`) |
| Token-id echo | honored: `prompt_token_ids` + `response_token_ids` present (`03-greedy`/probe 3) | ignored: 200 with no ids (`picom-ladder-20261117/preflight-transcript.txt:18,23`) |
| Thinking / reasoning channel | `chat_template_kwargs.thinking: true` produces content: `reasoning_tokens: 25`; default emits none (`08-reasoning.json`, `09-thinking-true.json`) | selects prompt encoding only; no reasoning channel emitted, `completion_tokens_details.reasoning_tokens: 0` (`main.rs-adjacent encoding path`, `server.rs:510-519`) |
| Prefix-cache visibility | reports a hit: `cached_tokens: 4608` on the repeat, `null` on the first (`07-long-prefix-cache.json`) | reports 0 and never a hit in our receipts (match needs 64 shared bytes, `session.rs:17`) |
| Errors | OpenAI-shaped 400 (`BadRequestError` on `max_tokens: -1`); unknown model name served and echoed | 400 with its own message strings; `max_tokens` above the cap is clamped, not refused (`server.rs:523-528`) |
| Loop guard | none | on by default: truncates 4 repeats of a 32–256-token n-gram, 64 identical tokens, or 8 identical lines (`frontend/src/guard.rs:63-67`; `--no-loop-guard` unset in the launcher) |
| Against the vendor card (`08c8657f`) | — | matches vendor temperature 1.0, one notch tighter on `top_p` (0.95 vs 1.0); deviates materially on `max_tokens` (32,768 default *and* cap vs ≥256K recommended) |

## 3. Measured, one instrument

One script on both arms — upstream's own `tools/bench/bench.py`, sha256 `4aff8517…b97967`,
byte-identical in both receipts, unpatched: 16 distinct code prompts, 512 output tokens, greedy,
thinking off, random prefix per request so no cache can help, completion tokens ÷ wall clock. Same
four ranks (`.31`–`.34`), same day. Run order was **picom lossless, picom `PICOM_OEA=4,12,9`,
knapcio** — sequential boots, one per configuration, not interleaved.

| cell | knapcio SGLang | picom, lossless | picom, `PICOM_OEA=4,12,9` | receipt |
|:--|--:|--:|--:|:--|
| `distinct 16` run 1 | 354.1 | 321.4 | 372.6 | `knapcio-bench-20261117/boot/distinct-16-run1.txt`; `picom-gap-20261117/boot-{a,b}/distinct-16-run1.txt` |
| `distinct 16` run 2 | 352.9 | 325.9 | 380.1 | `…/distinct-16-run2.txt` both receipts |
| `distinct 16` run 3 | 368.6 | 327.6 | 377.5 | `…/distinct-16-run3.txt` both receipts |
| `distinct 16` median / spread | **354.1 / 15.7** | 325.9 / 6.2 | 377.5 / 7.5 | `knapcio-bench-20261117/README.md`; `picom-gap-20261117/README.md` |
| `copies 16` (prompt-content locality; random prefix still defeats the cache, so not a caching cell) | 334.8 | 360.4 | 429.0 | `knapcio-bench-20261117/boot/copies-16.txt`; `picom-gap-20261117/boot-{a,b}/copies-16.txt` |
| `c1 9` chat median | 64.8 | 84.5 | 83.4 | `knapcio-bench-20261117/boot/c1-9.txt`; `picom-gap-20261117/boot-{a,b}/c1-9.txt` |
| `c1 9` code median | 119.8 | 142.5 | 144.3 | same files |
| fixed greedy prompt, 48 tokens, temp 0 | `picom arm online.`, 16+6 = 22 | same text, 15+6 = 21 | same text, 15+6 = 21 | `knapcio-bench-20261117/boot/fixed-prompt.json`; `picom-gap-20261117/boot-{a,b}/fixed-prompt.json` |
| llama-benchy `tg t/s`, depth 0 | C1 67.18 ± 6.97 / C4 118.9 / C8 107.5 / C16 115.9 (2026-10-18, depth-0 ladder, `~/benchmarks/ds4-knapcio-1017-20261018/`) | C1 87.4 / C4 108.6 / C8 120.4 / C16 141.0 (2026-11-17, `picom-ladder-20261117/`) | cell 5 only: c16 tg 159.6 (put in `picom-gap-20261117/boot-a/cell5-benchy.txt`) | as named per column |

Read the table as three separate one-boot measurements, never as a row of a leaderboard:

- **The budgets differ.** knapcio carries a 1M-context KV pool at `MEM_FRACTION_STATIC` 0.78 (6,849,792
  tokens), 16 uniform slots and DSpark k=5; picom carries 4 full-window + 12 eighth-window slots and no
  KV pool. `distinct 16` is the same *demand* on both, not the same batch size.
- **One boot per configuration**, in a fixed order, so only each boot's own spread bounds its number;
  no boot-to-boot drift is controlled.
- **The llama-benchy pair is not a paired cell** — the two rows are different days and different serve
  lines; the picom ladder and the knapcio ladder were never run in one window.
- **The fixed-prompt equality is a smoke check**, one 48-token greedy prompt, not a quality
  measurement.

## 4. Where each wins and why

- **16 concurrent users: knapcio ahead of the lossless picom arm (354.1 vs 325.9, +8.7 %) and 6.6 %
  behind the lossy one (377.5).** Mechanism, partly demonstrated: with 16 requests in flight picom's
  batch takes the plain loop and only the *last* request of a batch keeps its drafts
  (`docs/engine.md:615-700`), while SGLang runs DSpark across the whole batch at
  `MAX_RUNNING_REQUESTS=16` (`launcher.py:167`). That the speculation difference is what separates
  325.9 from 354.1 is INFERRED — no cell isolates it.
- **Single stream: picom ahead (84.5 vs 64.8 chat, +30.4 %; 142.5 vs 119.8 code, +19.0 %).** Both
  engines speculate with 5 drafts, so this is a per-step cost difference, not a different strategy.
  INFERRED mechanism: picom's step is one hand-written graph with no host-side scheduler hop per
  token and its own ring, while SGLang's decode passes through its Python scheduler and TP collectives.
  Neither receipt decomposes the step.
- **OEA is a knob, not an engine property.** `DSGB10_OEA=4,12,9` — a batch-aware MoE re-route that
  keeps each row's top 4 experts but prefers the batch's core among top 12, from 9 rows
  (`engine/kernels/moe.cu:1452-1455`) — buys +15.8 % at 16 users and costs ~1 % at one
  (`picom-gap-20261117/README.md`). It is lossy by construction and ships off; the cell to trust it on
  is the lane's quality gate, not these totals.
- **Prefill chunking is a budget, not a win.** knapcio's 16384-token chunk is 2.35× its 8192 control on
  1M prefills (`launcher.py:170-178`, `~/benchmarks/tp4-window-20261024/`), and its decode-between-chunks
  feature costs 17–28 % of ladder throughput and therefore ships off (`launcher.py:270-278`). picom
  prefills 8192 rows and has no interleave at all (`docs/engine.md:451-460`). No cell here measures a
  long-context prefill on both engines, so no direction is claimed.
- **The client contract is where the engines differ most in kind.** SGLang's surface honors
  `return_token_ids`, a real thinking channel and cache accounting; picom's front-end is a thin
  hand-written parser that drops unknown fields silently and clamps output at 32,768 tokens
  (section 2 surface group). For an agent workload that matters more than 10 % of decode, and it is the
  one difference here that is demonstrated by receipts rather than inferred from a total.

## 5. What is not comparable / not measured

- **No interleaved A/B.** One boot per configuration, run in a fixed order (picom A, picom B, knapcio).
- **Different budgets by design**: KV pool vs session store, 16 uniform slots vs 4 big + 12 small,
  chunked prefill at 16384 vs whole-request prefill at 8192 rows.
- **Vision and tool calls are functional only.** Both paths answered; no cost, latency or quality cell
  exists for either.
- **No quality cell for picom's lossy shortcut.** OEA's +15.8 % is measured on totals; the 48-token
  greedy prompt is identical text in both boots but proves nothing about accuracy. The gate that
  decides it is the lane's open gate 7 (house and needle cells), which has not run on the OEA shape.
- **No depth > 0 (long context) cell on either engine in this window**, and no repeated-prefix /
  multi-turn cell — so the prefix-cache difference (SGLang reports hits, picom ran cold in every
  receipt) is unmeasured as a cost.
- **No second boot per configuration, no power/thermal/RDMA capture**, and the readiness comparison is
  one cold boot against one warm-cached boot, not a like-for-like start.
- **`copies 16` is not a prefix-sharing cell** on either engine: the instrument randomizes the prefix.

## 6. What to try next

1. **Boot the queued `picom-prefill16k-boot` row** (`zz-ds4-1017-picom-prefill16k.yaml`, register row
   `state: queued`). Settling cell: needle/128k and 1M prefill cells against the shipped arm on the
   same image, with the `pp 2048` cell required to come out unchanged.
2. **Boot the queued `picom-engram-batch8-boot` row** (`zz-ds4-1017-picom-engram-batch8.yaml`).
   Settling cell: c1 and c16 decode cells of the long-context ladder against
   `PICOM_ENGRAM_READ_BATCH=1` on the same image.
3. **Run one interleaved A/B** — knapcio, picom lossless, knapcio, picom — three `distinct 16` runs
   each, one window. Settles whether the +8.7 % is boot order or engine, which is the only claim in
   section 4 currently resting on a single boot.
4. **Add a repeated-prefix multi-turn cell** on both arms (one conversation replayed twice against a
   warm serve, `cached_tokens` and wall clock). Settles what SGLang's cache reporting is worth on the
   workload the lane actually runs, and whether picom's 64-byte match threshold ever fires.
