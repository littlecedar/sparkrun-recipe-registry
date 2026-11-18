# picom vs knapcio: one model, two engines on four GB10s

The lane record (arms, boots, measurement tables) is
[the lane README](README.md#deepseek-v41-flash-knapcio-tp4-1m-sglang); this page only
compares the two engines serving the same checkpoint on the same four ranks. Every numeric cell
names its receipt; every mechanism cell names a source line or the flag that carries it. Nothing
here is a leaderboard row — the two arms do not run the same budgets and no cell was measured
interleaved.

## The answer, in ten lines

- **One stream: picom.** 84.5 against 64.8 tok/s chat and 142.5 against 119.8 code, same
  instrument, same day (section 3); both engines draft 5 tokens, so this is per-step cost.
- **Two streams: a tie.** 90.8 against **90.3** tok/s on the same-day knapcio rerun (+0.6 %, inside
  the 6.2 % within-boot spread) and 83.4 on the October row (+8.9 %), so the ordering does not
  survive the same-day column.
- **Five to ten users: knapcio.** 111.5 against **122.6 and 127.3** tok/s at C5, and 129.2 against
  **153.3 and 160.9** at C10 (same-day rerun, then October); the direction holds on either column.
- **Agentic tool loop: picom.** Per-boot median totals 119.9–123.4 s and 122.5–124.4 s against
  159.5–178.6 s over two boots per arm, disjoint at the per-boot median level — LIKELY, two boots
  per arm.
- **Fast restart matters: picom.** 27.7 s to HTTP-ready against 708.4 s.
- **Client contract matters: knapcio.** It echoes token ids, has a real thinking channel and
  reports prefix-cache hits; picom drops unknown fields silently and clamps `max_tokens`.
- **Exact vs lossy picom: a tie on this evidence.** Same wall clock inside either arm's spread;
  the lossy arm is ahead **+5.5 % at C5 and +3.9 % at C10** (section 5).
- **What would change the answer: cell-level interleaving.** The agentic ordering now rests on two
  boots per arm, disjoint at the per-boot median level and still LIKELY; every ladder ordering rests
  on one boot per side.

## Which engine, by workload

| workload shape | pick | cell that supports it | confidence |
|:--|:--|:--|:--|
| Single stream, chat | picom | `c1 9` chat 84.5 vs 64.8 tok/s (section 3) | measured, one boot per side |
| Single stream, code | picom | `c1 9` code 142.5 vs 119.8 tok/s (section 3) | measured, one boot per side |
| 2 users | either | shipped exact C2 90.8 vs knapcio 90.3 rerun / 83.4 October (section 3) | tie on the same-day column |
| 5–10 fan-out | knapcio | C5 111.5 vs 122.6 / 127.3, C10 129.2 vs 153.3 / 160.9 (rerun / October) | holds on both columns — other boots |
| Agentic tool loop | picom | per-boot median totals 119.9–123.4 / 122.5–124.4 vs 159.5–178.6 s, two boots each | LIKELY, two boots per arm |
| Tool calling, scored | either | BFCL scoped 87/100 both, `transport_errors` 0, per-category 19/17/17/20/14 vs 19/17/18/19/15 | tie; 100 of 1,240 questions |
| Million-token context | either | 983,040 needle PASS at depth 10 on both shipped arms | PASS measured; decode unmeasured |
| Vision | knapcio | native in-engine stack; picom needs a supervised child | functional on both, no cost cell |
| Long-form generation | picom | 40,000 tokens in 207.9 s (192.4 tok/s) under a 262,144 cap | measured on picom; knapcio names 32,768 and enforces neither bound |
| Restart-sensitive work | picom | 27.7 s warm-cached vs 708.4 s cold | one boot each, not like-for-like |

## Architecture

```mermaid
flowchart LR
  client[OpenAI client] --> fe{engine}
  fe -->|knapcio| sg["SGLang launch_server"]
  fe -->|picom| df["dsfront, Rust"]
  sg --> r0[rank 0]
  df --> r0
  sg --> kv["SGLang paged KV pool"]
  df --> ss["picom session store"]
  ss --> disk["per-rank disk tier"]
  r0 --> ring["RoCE ring, f1 ports down"]
  r1[rank 1] --> ring
  r2[rank 2] --> ring
  r3[rank 3] --> ring
  r0 --> vis["supervised ViT child"]
  r0 --> nat["native multimodal"]
```

knapcio (`deepseek-v4.1-flash-knapcio-tp4-1m-sglang.yaml`) is SGLang `sglang.launch_server` from
the image's `dev-dsv41` build (`da64c5cb`, staged tree `f80c91a4b`), TP=4 / EP=1 over two
RoCEv2 RDMA devices (`rocep1s0f0`, `roceP2p1s0f0`), with RoCEnante doing the one-shot
all-reduce and all-gather, 1M context, DSpark k=5, driven by a lane mod that owns the memory
line and the extra flags (`mods/dsv41-sglang-overlay/launcher.py`). It optimizes the production
serve line: one long-lived process holding a 1M-token KV pool, 16 uniform request slots, a
16384-token prefill chunk, and SGLang's paged attention, radix prefix cache and in-process
multimodal stack as the tuning surface
(`launcher.py:148-300`).

picom (`zz-deepseek-v4.1-flash-1017-picom-tp4-1m.yaml` as the probe, shipped as
`deepseek-v4.1-flash-1017-picom-tp4-1m.yaml` with a lossy twin
`…-picom-tp4-1m-oea.yaml`) is a from-scratch C++/CUDA engine (`dsgb10_rank`, one process per node,
its own RDMA ring) behind a Rust front-end (`dsfront`), from `Picom-code/pico-dgx-ds4@7c123ad4`
with two integrated PR patches (`Dockerfile.picom-ds41f`). It optimizes per-token decode cost at
single stream: every rank holds one quarter of a 1M model GPU-resident, 16 session slots of which
4 hold the full window, drafts verify 5 tokens a step, and session state migrates to a 12 GiB store
plus a per-rank disk tier instead of a pre-sized KV pool (`engine/server/main.cpp:295-296`,
`docs/engine.md:451-523`).

The fabric is one switch and both f1 ports are down on this fleet, so a ring's two directions share
the same two f0 devices (`mods/picom-launcher/README.md:104`). It was probed read-only in the paired
window (`paired-20261118/fabric-probe/`): MTU **9000** on both RoCE netdevs (`enp1s0f0np0`,
`enP2p1s0f0np0`, maxmtu 9978), RDMA links ACTIVE, `ethtool -a` autoneg off with RX and TX pause
**on**, `mlnx_qos` DCBX OS-controlled, priority trust pcp, **PFC disabled on all eight priorities**.
Two facts are **not obtained** and nothing below rests on them: the switch-side PFC/ECN
configuration (the switch is not reachable from the hosts) and picom's queue-pair `hop_limit` (no
log, container env, launcher script or binary string exposes it).

## How each was measured

```mermaid
graph TD
  boot["boot one arm"] --> gate["warm-up, HTTP-ready gate"]
  gate --> ladder["ladder cells"]
  gate --> agentic["agentic battery"]
  gate --> needle["needle rungs"]
  gate --> grant["40,000-token grant"]
  ladder --> down["teardown to zero"]
  agentic --> down
  needle --> down
  grant --> down
  down --> receipt["receipt on the head"]
  agentic --> poll["polluted_runs 0?"]
  poll -->|yes| keep["keep the rows"]
  poll -->|no| rerun["rerun, drop the rows"]
  keep --> receipt
  rerun --> receipt
```

One boot per configuration in the original windows, cells run in a fixed order, then torn down to 0
containers, 0 volumes and no `:8000` listener before the next start (`post-teardown.txt` beside each
phase's cells). The paired window in section 3 boots each arm twice, in the order `E, K, L, L, K, E`,
with the same teardown gate between boots. The pollution rule is the whole reason the agentic
section exists in its current form: runs whose
report carries a non-zero `polluted_runs` are dropped and re-measured, because a mixed-fixture
table once read a harness timeout as an engine property (section 3, old fixture's rows).

## 1. Same model, different machine

| axis | knapcio (SGLang) | picom (dsgb10) |
|:--|:--|:--|
| Context budget | 1,048,576 served (`--context-length` from `defaults.max_model_len`); KV pool profiled at boot and pinned to 6,849,792 tokens on the stock loader under `MEM_FRACTION_STATIC` 0.78 (`launcher.py:148,156`, `launcher.py:217-236`) | 1,048,576 for the 4 big slots; the other 12 hold `max_ctx / 8` = 131,072 each (`engine/model/model.cu:79-88`, `kUnitMul` 8 at `engine/model/config.h:39`); no `max_model_len` in the recipe, no KV pool to pin |
| Output ceiling | **32,768** new tokens, named by the engine's own refusal: `min_tokens` 40000 draws HTTP 400 with `min_new_tokens must be in [0, max_new_tokens(32768)], got 40000`, while `max_tokens` 40000 is accepted silently and the reply self-terminates at 2,001 tokens with `finish_reason: stop`; at 32,768 `min_tokens` is accepted but not enforced (`paired-20261118/K2/ceiling/`) | **262,144** on the production arm (`PICOM_MAX_TOKENS`, `launch.sh:311,324`), which binds each long request to the four big slots — `engine/server/serve.cpp:1195` admits a request only where `prompt + max_new` fits, so a fifth 262k reply queues silently instead of being refused; the front-end's own default stays 32,768 (`frontend/src/main.rs:126`) and clamps a larger value rather than refusing it (`frontend/src/server.rs:522-528`), which is the silent clamp the shipped arm used to report as `finish_reason: length` |
| KV / session memory | one paged KV+SHA pool sized from MemAvailable at boot; fp8 KV; 128 SWA prefix tails reserved inside that budget (`launcher.py:268`, recipe `metadata.kv_dtype: fp8`) | compressed KV + index keys, ~890 B per position across all 40 layers, replicated (`docs/engine.md:90-116`); 12 GiB session-store pool, blocks of 64 KiB, spill to a per-rank 32 GiB disk tier (`docs/engine.md:451-523`) |
| Scheduler / admission | `MAX_RUNNING_REQUESTS=16` uniform slots; `--cuda-graph-max-bs-decode` follows the same number (`launcher.py:167`, live flags in `head:~/benchmarks/knapcio-live-20261117/README.md`) | 16 slots with 4 big (`--slots 16 --big-slots 4`, `recipes/ds4/mods/picom-launcher/launch.sh:190`); smallest-fit pick, small slots first so big ones stay for long requests (`engine/server/serve.cpp:1198-1205`); more requests than slots take turns of `--slice` 64 tokens (`docs/engine.md:615-700`) |
| Prefill | chunked at 16384 tokens (`CHUNKED_PREFILL_SIZE`, `launcher.py:178`); decode-between-chunks ships **off** (`PREFILL_DECODE_INTERVAL` 0, `launcher.py:278`) | whole request in `--prefill-rows` chunks: 8192 on the probe arm, 16384 on the shipped arms; decode between chunks not built, so other requests wait one chunk (`docs/engine.md:451-460`) |
| Speculative decoding | DSpark, verify-all, k=5 (`SPEC_ALGO DSPARK` `launcher.py:219`, `DSPARK_BLOCK_SIZE` `launcher.py:240`); decoded accepts 3.9–5.8 tokens/step on the measured boot (`knapcio-bench-20261117/boot/serve-rank0.log`) | DSpark, 5 drafts (6 rows per session step including the bonus, `engine/dspark/dspark.h:27`, `engine/model/ops.h:34`); drafts in a one-request run or a batch of ≤8, a larger batch takes the plain loop (`docs/engine.md:615-700`); levers `DSGB10_BUDGET`, `DSGB10_DRAFT1`, `DSGB10_WIDE` (`launch.sh:190`, `engine/server/cmd.cpp:662-664`, `engine/model/spec.cu:38`) |
| Weights as served | checkpoint as shipped: native MXFP4/F8, 510 GB resident, Engram read from NVMe (`recipes/ds4/README.md` knapcio table; arm `metadata.model_dtype: mxfp4`) | same checkpoint converted once per rank to a 72.38 GiB `.dsw` file (≈289.5 GiB across 4 ranks) plus 50.7 GB Engram shards on that rank's SSD (`docs/engine.md:90-116`; lane README artifacts row) |
| Vision | in-engine native multimodal; the measured boot's gate line records full-budget native vision passing (`knapcio-bench-20261117/boot/serve-rank0.log:447`) | separate supervised ViT child on rank 0, `127.0.0.1:18950`, ~0.90 GiB, front-end reaches it by `--vision-addr` (`launch.sh:269-271`, PR #15 patch) |
| Tool calls | `--tool-call-parser deepseekv41` with `--reasoning-parser deepseek-v41`; name then argument pieces, `finish_reason: tool_calls` (`knapcio-live-20261117/README.md` probes 4 and 8) | dsfront parses the model's own tool-call text (`frontend/src/server.rs:1006`) and streams argument pieces (`server.rs:1073-1076`; `--stream-tool-args` at `launch.sh:242`, PR #7 patch) |
| Prefix / cache behavior | radix prefix cache with 128 SWA tails and cache reporting on; a repeated ~4.8k prompt reports `prompt_tokens_details.cached_tokens: 4608` (`launcher.py:268`, `knapcio-live-20261117/README.md` probe 6) | session table matched by longest shared *text* prefix, 64 shared bytes minimum (`frontend/src/session.rs:17`), state spilled per slot; every measured cell ran cold — `reused 0 (cold)`, `cached_tokens: 0` (`picom-ladder-20261117/README.md` falsifiers, `knapcio-live-20261117/README.md` probe 6) |
| Readiness (container start → HTTP ready) | 696.2 s port-open / **708.4 s** HTTP-ready, one cold boot (`knapcio-bench-20261117/README.md`) | **27.7 s** with per-rank artifacts cached; 166.4 s on the boot that had to convert weights and Engram (`picom-gap-20261117/README.md`) |

## 2. Request surface

The live probe pair: the 2026-11-18 knapcio serve and the pinned picom front-end.
Receipts: `head:~/benchmarks/knapcio-live-20261117/` (17 files, keyless anonymous probes) and the
picom front-end read at `7c123ad4` (`frontend/src/server.rs:522-538`, `frontend/src/main.rs:126-132`).

| axis | knapcio (SGLang) | picom (dsfront) |
|:--|:--|:--|
| Defaults when the request omits them | samples: three runs, three distinct answers (`02-defaults.json`) | `temperature` 1.0, `top_p` 0.95, `max_tokens` = its cap, 32,768 with no launcher flag (`frontend/src/main.rs:126,130-131`) |
| Honored sampling / limits | vendor surface: `temperature`, `top_p`, `stop` (`matched_stop: 1`), `max_tokens` floor-checked with a 400 whose text names the 32,768-new-token ceiling (`paired-20261118/K2/ceiling/`) | `temperature`, `top_p`, `top_k` (approximate past ~256: candidate union capped at 64 logits/rank), `seed` (`mix64(seed) ^ pos`, reproducible), `max_tokens` / `max_completion_tokens`, `stop` (held-back partial tail), `stop_token_ids`, `ignore_eos` (`server.rs:522-545`) |
| Silently dropped | none found in the probed set | `min_p`, `presence_penalty`, `frequency_penalty`, `repetition_penalty`, `logit_bias`, `return_token_ids` — hand-written `r.get(...)` list, no unknown-key refusal (`server.rs:522-545`) |
| Token-id echo | honored: `prompt_token_ids` + `response_token_ids` present (`03-greedy`/probe 3) | ignored: 200 with no ids (`picom-ladder-20261117/preflight-transcript.txt:18,23`) |
| Thinking / reasoning channel | `chat_template_kwargs.thinking: true` turns it on: non-empty `reasoning_content`, `reasoning_tokens: 25`; the default emits none (`08-reasoning.json`, `09-thinking-true.json`) | the same kwargs select prompt *encoding* only; no reasoning channel is ever emitted, `completion_tokens_details.reasoning_tokens: 0` (`frontend/src/server.rs:510-519`, `frontend/src/main.rs:129`) |
| Prefix-cache visibility | reports a hit: `cached_tokens: 4608` on the repeat, `null` on the first (`07-long-prefix-cache.json`) | reports 0 and never a hit in our receipts (match needs 64 shared bytes, `session.rs:17`) |
| Errors | OpenAI-shaped 400 (`BadRequestError` on `max_tokens: -1`); unknown model name served and echoed | 400 with its own message strings; `max_tokens` above the cap is clamped, not refused (`server.rs:523-528`) |
| Loop guard | none | on by default: truncates 4 repeats of a 32–256-token n-gram, 64 identical tokens, or 8 identical lines (`frontend/src/guard.rs:63-67`; `--no-loop-guard` unset in the launcher) |
| Against the vendor card (`08c8657f`) | — | matches vendor temperature 1.0, one notch tighter on `top_p` (0.95 vs 1.0); deviates on `max_tokens` (32,768 default and clamp vs ≥256K recommended) only until the launcher's `PICOM_MAX_TOKENS` raises the cap, as the production arm's 262,144 does |

## 3. The measured cells

### One instrument, three configurations

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
| llama-benchy `tg t/s`, depth 0 C4 / C8 / C16 | 118.9 / 107.5 / 115.9, 3 runs/cell, `ds4-sglang-depth0-ladder.yaml` (`~/benchmarks/ds4-knapcio-1017-20261018/arm-1017/`) | 108.6 / 120.4 / 141.0, 3 runs/cell, same profile (`picom-ladder-20261117/`) | — | per column |
| llama-benchy C1 aggregate | 67.18 ± 6.97, n=25, `concurrency-ladder.yaml` (`~/benchmarks/tp4-20261018/`) | 87.4, 3 runs, depth-0 ladder (`picom-ladder-20261117/`) | 159.6 is c16, not c1 (`picom-gap-20261117/boot-a/cell5-benchy.txt`) | per column |

Read the table as three separate one-boot measurements, never as a row of a leaderboard:

- **The budgets differ.** knapcio carries a 1M-context KV pool at `MEM_FRACTION_STATIC` 0.78
  (6,849,792 tokens), 16 uniform slots and DSpark k=5; picom carries 4 full-window + 12
  eighth-window slots and no KV pool. `distinct 16` is the same *demand* on both, not the same
  batch size.
- **One boot per configuration**, in a fixed order, so only each boot's own spread bounds its
  number; no boot-to-boot drift is controlled.
- **The llama-benchy rows are not paired cells** — different days, different serve lines and, for
  C1, different profiles; the picom ladder and the knapcio ladder were never run in one window.
- **The fixed-prompt equality is a smoke check**, one 48-token greedy prompt, not a quality
  measurement.

### Shipped-arm ladder

The two shipped artifacts, booted back to back on the same image:
`deepseek-v4.1-flash-1017-picom-tp4-1m.yaml` (exact, task `…053127e6543a`) and
`deepseek-v4.1-flash-1017-picom-tp4-1m-oea.yaml` (lossy, task `…2f2f42a6d68f`), both on
`ghcr.io/littlecedar/dgx-picom-ds41f@sha256:1e529c67…` with the 262,144-token reply ceiling and
`--prefill-rows 16384`. Instrument: `benchmarking/concurrency-ladder.yaml`, depth 0, 2048-token
prompts, 128-token replies, 5 runs/cell, `--skip-run --fresh`.

| cell | shipped exact | shipped lossy (OEA) | knapcio (rerun boot) | knapcio (October recorded row) |
|:--|--:|--:|--:|--:|
| C1 | 83.4 | 87.1 | 64.8 | 70.4 |
| C2 | 90.8 | 90.9 | 90.3 | 83.4 |
| C5 | 111.5 | 117.6 | 122.6 | 127.3 |
| C10 | 129.2 | 134.4 | 153.3 | 160.9 |

Receipts: `head:~/benchmarks/picom-prod-20261118/phase5/ladder.csv` (exact) and
`head:~/benchmarks/picom-prod-20261118/phase6/ladder.csv` (lossy), each beside `ladder.json` and
`ladder.log`. The knapcio columns are two different boots and are not interchangeable: the rerun
boot's own cells are `head:~/benchmarks/picom-prod-20261118/rerun-20261118/boot1-knapcio/ladder.csv`
(same day, separate window, 5 runs/cell, decode-phase rows only) and the October row is
[the lane README](README.md)'s (`head:~/benchmarks/ds4-1017-parity-20261027/armC/armC-ladder.csv`).
The exact-vs-lossy pair is the only same-window comparison; both knapcio columns are a shape to read
the picom columns against. Within-boot spread: C1 6.2 % exact vs 3.4 % lossy; rerun knapcio 8.8 %
C1, 5.3 % C10.

### Probe-window ladder (history)

These came first: `zz-ds4-1017-picom-out256k.yaml`, the shipped engine plus `PICOM_MAX_TOKENS=262144`
but with 8192-row prefill and a probe name, so its cells are not interchangeable with the shipped
arms above — same image and instrument, different engine shape.

| cell | probe exact | probe OEA | knapcio (recorded row) |
|:--|--:|--:|--:|
| C1 | 87.5 | 85.1 | 70.4 |
| C2 | 90.4 | 93.8 | 83.4 |
| C5 | 112.9 | 121.2 | 127.3 |
| C10 | 125.8 | 135.8 | 160.9 |

Receipts: `head:~/benchmarks/picom-prod-20261118/phase1/ladder.csv` (exact) and
`head:~/benchmarks/picom-prod-20261118/phase2/ladder.csv` (OEA), each with `ladder.json` and
`ladder.log`; knapcio as above. Within-boot spread: C1 14.3 % exact vs 8.6 % OEA, C10 1.8 %
vs 2.7 %.

### Agentic battery

`tools/agentic-battery.py --tier all`, 13 tasks (8 easy, 5 hard), fixed `max_tokens: 4096`,
single-flight. Three runs of the same battery per configuration, one boot per configuration — the
earlier window; the paired window below boots each arm twice. All nine runs come from the post-fix
fixture (the `start_stub.sh` launcher plus the run report's pollution flag), so the three
configurations are comparable to each other and to nothing measured earlier on this page.

| configuration | run | pass | median | worst | total wall |
|:--|:--|:--|--:|--:|--:|
| knapcio SGLang (production) | 1 | 13/13 | 9.2 s | 31.1 s | 152.9 s |
| | 2 | 13/13 | 11.4 s | 29.7 s | 147.1 s |
| | 3 | **12/13** | 9.8 s | 30.6 s | 152.9 s |
| | totals range | — | — | — | **147.1–152.9 s** |
| picom exact (shipped) | 1 | 13/13 | 10.0 s | 25.5 s | 125.1 s |
| | 2 | 13/13 | 9.9 s | 31.9 s | 133.4 s |
| | 3 | **12/13** | 8.6 s | 14.9 s | 110.2 s |
| | totals range | — | — | — | **110.2–133.4 s** |
| picom OEA (shipped) | 1 | 13/13 | 9.7 s | 11.8 s | 108.1 s |
| | 2 | **12/13** | 7.9 s | 45.7 s | 136.7 s |
| | 3 | **12/13** | 8.7 s | 30.6 s | 131.8 s |
| | totals range | — | — | — | **108.1–136.7 s** |

Receipts: knapcio `head:~/benchmarks/picom-prod-20261118/knapcio-newfix-20261118/run{1,2,3}/
summary.json` (boot `b020d2dd178343a5`, `ttr.txt` 710 s, keyless), exact
`final-20261118/bootA-exact/agentic-run{1,2,3}/summary.json`, lossy
`final-20261118/bootB-oea/agentic-run{1,2,3}/summary.json`, one boot and one summary per run. All
nine `summary.json` files carry `polluted_runs` 0 and `harness_timeouts` 0.

**The totals separate picom from SGLang in this sample, and nothing finer.** The medians are 125.1 s
(exact) and 131.8 s (OEA) against 152.9 s (SGLang) — 18.2 % and 13.8 % below — and the totals ranges
are disjoint in that one-boot-per-arm sample: 110.2–133.4 s and 108.1–136.7 s against
147.1–152.9 s. That is LIKELY rather than established: one boot per arm with three runs each, and
the battery's own inter-boot floor is ~7 %, so a second boot per arm is what would test it — the
paired window below takes that boot, and it keeps the verdict LIKELY. Between the two picom arms
the totals ranges overlap almost completely (medians 125.1 against 131.8, inside either arm's
21–24 % run-to-run spread), so exact and lossy stay indistinguishable on total wall clock and the
agentic choice still rests on the concurrency curve and the lossy construction.

### The paired window: two boots per arm

The same battery in a declared window 17:40–20:45Z over the same four ranks `.31`–`.34`, boot order
**E, K, L, L, K, E** (E = picom exact, L = picom lossy `PICOM_OEA=4,12,9`, K = knapcio SGLang),
every boot torn down to 0 containers, 0 volumes and no `:8000` before the next and the lease
released after. Receipt: `head:~/benchmarks/picom-prod-20261118/paired-20261118/README.md`, with one
directory per boot (`E1/`, `K1/`, …). All 18 passes carry `polluted_runs` 0 and
`harness_timeouts` 0, `max_tokens` 4096, tier `all`, temperature 0, non-streaming; no pass
discarded or re-run. Totals are the battery's three pass totals per boot, in run order.

| boot | arm | order | pass totals (pass count) | socket-task wall | ladder C1 / C2 / C5 / C10 |
|:--|:--|:--:|:--|:--|:--|
| E1 | picom exact | 1st | 118.6 (12/13) · 119.9 (12/13) · 129.7 (12/13) | 10.7 · 9.8 · 10.0 s | not run |
| K1 | knapcio | 2nd | 189.2 (13/13) · 178.6 (13/13) · 122.7 (13/13) | 15.8 · 11.1 · 14.5 s | not run |
| L1 | picom lossy | 3rd | 126.3 (12/13) · 100.0 (13/13) · 124.4 (11/13) | 12.0 · 8.2 · 11.1 s | not run |
| L2 | picom lossy | 4th | 125.7 (13/13) · 114.6 (13/13) · 122.5 (13/13) | 11.8 · 7.9 · 8.0 s | 91.29 / 93.05 / 114.66 / 138.09 |
| K2 | knapcio | 5th | 159.5 (13/13) · 161.6 (13/13) · 135.0 (13/13) | 15.1 · 14.2 · 14.0 s | 66.94 / 89.59 / 123.92 / 161.23 |
| E2 | picom exact | 6th | 123.4 (13/13) · 130.4 (13/13) · 120.1 (13/13) | 9.4 · 11.1 · 11.9 s | 77.29 / 97.39 / 106.89 / 124.92 |

In this window: picom TTR flat at 25.2–26.5 s across its four boots, knapcio at 674–722 s, and every
boot armed its watchdog with `ranks=4 unprobeable=0`.

| arm | boots, in window order | pass count | median of the pass medians | per-boot median total | totals range |
|:--|:--|:--|:--|:--|:--|
| picom exact (E) | E1 (1st), E2 (6th) | 75/78 | 8.4 s / 9.0 s | 119.9 / 123.4 s | **119.9–123.4 s** |
| picom lossy (L) | L1 (3rd), L2 (4th) | 75/78 | 8.1 s / 8.0 s | 124.4 / 122.5 s | **122.5–124.4 s** |
| knapcio (K) | K1 (2nd), K2 (5th) | 78/78 | 9.0 s / 9.8 s | 178.6 / 159.5 s | **159.5–178.6 s** |

**Verdict: picom leads SGLang on agentic wall clock, disjoint at the per-boot median level across
both boots of each arm — LIKELY, not established.** Individual passes do overlap, though: K1's
fastest pass was 122.7 s, inside the picom arms' per-pass band (E 118.6–130.4 s, L 100.0–126.3 s),
so the ordering rests on central tendency across two boots per arm, not on every run. At the
ranges' ends: (159.5 − 119.9) ÷ 159.5 = **24.8 %** and (178.6 − 123.4) ÷ 178.6 = **30.9 %** less
wall clock, i.e. knapcio takes 1.33× to 1.45× the time.
Alternation changed no ordering: same-arm boots differ by ≤ 0.9 s in median and ≤ 19 % in total,
and the differences do not track boot order — the pair adjacent in time, L1→L2, agrees to 0.1 s,
while the pair furthest apart in the window, K 2nd against 5th, moves most. It stays LIKELY because
these are single-flight sequential runs of a 13-task set, two boots per arm, with no cell-level
interleaving.

**Pass counts give SGLang a small accuracy edge in this window.** K 78/78 against E 75/78 and
L 75/78: SGLang passed every pass, while each picom arm missed three — E1 12/13 on all three
passes, and L1 12/13 once, 11/13 once and 13/13 once. None of the misses is reproducible across
boots, and `shell-repro-rounding` is the miss the lane doc already records for the exact arm.
Three misses across 78 passes is a small sample and no single task repeats across boots, so this is
a small edge rather than a parity finding, and no significance is claimed.

**Ladder, still one boot per arm.** Only each arm's second boot carries the depth-0 ladder — the
requirement arrived mid-window — and E1, K1 and L1 have none: missing, not substituted.

| cell | picom exact (E2) | picom lossy (L2) | knapcio (K2) |
|:--|--:|--:|--:|
| C1 | 77.29 | 91.29 | 66.94 |
| C2 | 97.39 | 93.05 | 89.59 |
| C5 | 106.89 | 114.66 | 123.92 |
| C10 | 124.92 | 138.09 | 161.23 |

Receipts: `paired-20261118/E2/ladder.csv`, `L2/ladder.csv`, `K2/ladder.csv`, each with `ladder.json`
and `ladder.log`. Same 3 tok/s chart as the shipped-arm table (section 4), same directions: picom
ahead at C1, knapcio ahead at C5 and C10, C2 inside the spread — so this window separates no new
ladder direction. A first L2 attempt without `--fresh` printed the archived phase-6 table and wrote
no file (`L2/ladder.log`); it is not evidence and the recorded L2 numbers are the `--fresh` run's.

**A scoped BFCL tools leg ran in this window, on the first boot of each arm.**
`--limit 20` × 5 default categories = **100 of 1,240 questions**, fixture revision
`gorilla-llm/Berkeley-Function-Calling-Leaderboard` `61fc0608…`, `--max-tokens` 4096, temperature 0,
`tool_choice auto`, serial. **E1 87/100 and K1 87/100, `transport_errors` 0 in both**; per category
(simple / multiple / parallel / parallel_multiple / irrelevance) E1 19/17/17/20/14 and K1
19/17/18/19/15. This is the page's first tool-calling score and it **separates nothing**: it is not
comparable to a full-leg or `/1,240` number (section 6), only to itself and to the other engine on
the same 100 questions. Receipts: `paired-20261118/E1/`, `paired-20261118/K1/`.

### Knapcio output ceiling (probe)

`paired-20261118/K2/ceiling/`, four requests to the same live serve. `max_tokens` 40000 is
**accepted** — no 400 and no clamp message — and the reply self-terminates at 2,001 tokens with
`finish_reason: stop` at 152.4 tok/s. `min_tokens` 40000 is **refused** with HTTP 400 in the
engine's own words, `min_new_tokens must be in [0, max_new_tokens(32768)], got 40000`, which names
the ceiling: **32,768 new tokens**. At 32,768 both are accepted and `min_tokens` is **not
enforced** (the reply stops at 2,001 tokens with `stop`). So the ceiling is named, not exercised: no
32k reply was generated, `max_tokens` above it is accepted silently, and `min_tokens` neither bounds
the request nor holds a floor.

### The old fixture's rows (history)

This section used to carry a mixed-instrument table: the knapcio rows **127.7 / 160.2 / 149.4 s**
(`rerun-20261118/README.md`) came from the pre-fix battery while the picom rows came from the
post-fix one, and mixing fixtures is the earlier error — it made a ~50 % agentic gap read as an
engine property. The gap was the harness's own 60 s tool timeout: repeating `stub-service-client`
on both shipped arms puts wall time in two modes, exact **12.8 / 13.1 / 12.8 s** fast against
**109.8 / 120.2 / 75.3 s** slow (3 of 6 draws), lossy **12.6 / 13.2 / 14.8 s** fast against
**76.9 s** slow (1 of 6), every slow draw's wire log carrying `command timed out 60s` while the
engine's `ttft` stayed 0.10–0.33 s at 130–160 tok/s throughout
(`head:~/benchmarks/picom-prod-20261118/socket-repro-20261118/`). The launcher fix removed that
path, and under `stub-service-client` the cell now runs **14.9 / 12.6 / 14.6 s** on SGLang against
**11.4 / 11.1 / 8.7 s** exact and **11.4 / 11.0 / 10.8 s** lossy, so the 75–120 s regime is gone.
Those old-fixture totals are not comparable to the table above.

Arm identity is the engine log, not the run label: rank 0's leaf
`…/vllm/deepseek-ai__DeepSeek-V4.1-Flash-1017-b03807ac/picom/logs/rank.0.log` on `.31` prints
`moe: DSGB10_OEA re-routing on: keep top 4, prefer the batch's core among top 12, from 9 rows` at
line 11405 inside the final boot (lines 11389–12503, its one `starting dsfront … max_tokens 262144`
at 11414), while the exact arm's own boot section (lines 10258–11388, one start line at 10282)
holds 0 `DSGB10_OEA` lines — that absence is its proof (`final-20261118/bootB-oea/proof.txt`).

Every configuration still loses a task once or twice in three runs — knapcio run 3 and both later
OEA runs miss `shell-repro-rounding` on the hidden sweep's `AssertionError: (75, 1, [89], 88)` on
`sum(shares) == due` while the visible suite and `repro.py` pass, and exact run 3 misses
`golden-regression` — so pass counts do not separate the arms at 12–13 of 13 everywhere. The probe
pair's agentic cells remain one boot each (13/13 both, totals 126.2 and 108.1 s,
`phase1`/`phase2` receipts above) and are not comparable to this table.

### The production window

Every receipt in this section is on the head: `head:~/benchmarks/picom-prod-20261118/` holds the
probe phases, the two shipped-arm confirmations and the extra boot, and
`head:~/benchmarks/agentic-battery-20261118/knapcio-v2/` holds the knapcio reference — the one cell
measured from a workstation against the remote endpoint, so its files were created locally and
archived there, while every other receipt was written on the head itself. All cells ran on
`ghcr.io/littlecedar/dgx-picom-ds41f@sha256:1e529c67…` over ranks `.31`–`.34`, in this order: one
exact probe boot (`…9aea1006d19f`) ran the ladder, agentic battery, both needle rungs and the
40,000-token grant; one OEA probe boot (`…b2aaddef7ada`) repeated the same four groups; a third,
lossless boot (`…1f1549d1421d`) was taken only to pair the house battery; then the shipped exact arm
(`…053127e6543a`) and the shipped lossy arm (`…2f2f42a6d68f`) each ran the same cells, adding the
983,040-token needle rung. Every boot reached HTTP-ready in 25.2–26.3 s, armed its watchdog with
`unprobeable=0`, and was torn down to 0 containers, 0 volumes and no `:8000` listener before the
next start (`post-teardown.txt` beside each phase's cells).

The three-run agentic table is a later window of the same day: one boot per configuration — exact
`…da567c594d37`, OEA `…0b23560656a9` — each torn down to 0 containers, 0 volumes and no `:8000`
listener before the next. Its SGLang row was re-measured on the post-fix battery as its own boot,
`b020d2dd178343a5` (cluster `sparkrun_b020d2dd178343a5_11628c2281a4`) on
`ghcr.io/littlecedar/dgx-spark-dsv41@sha256:7c3cb394…`, launch 12:17:33Z and HTTP-ready 12:29:29Z —
**TTR 710 s**, keyless, watchdog `unprobeable=0` throughout, torn down to 0 containers, 0 volumes
and no `:8000` listener. The superseded old-fixture knapcio rows (`…d143959e5792`) and the rerun
ladder stay in `rerun-20261118/README.md`, and the new boot's own receipts are
`head:~/benchmarks/picom-prod-20261118/knapcio-newfix-20261118/` (`README.md`, `ttr.txt`,
`watchdog.log`, `run{1,2,3}/summary.json`).

## 4. The same numbers as bars

Mermaid cannot draw a value axis honestly, so the quantitative comparisons are fixed-width bars.
Every bar is the section 3 number rounded to the nearest character; the value is printed beside it.

### Shipped-arm ladder, one character = 3 tok/s, origin = column 19 (the first `#`)

```
C1  picom exact   ############################                            83.4
C1  picom OEA     #############################                           87.1
C1  knapcio rerun ######################                                  64.8
C1  knapcio Oct   #######################                                 70.4
C2  picom exact   ##############################                          90.8
C2  picom OEA     ##############################                          90.9
C2  knapcio rerun ##############################                          90.3
C2  knapcio Oct   ############################                            83.4
C5  picom exact   #####################################                  111.5
C5  picom OEA     #######################################                117.6
C5  knapcio rerun #########################################              122.6
C5  knapcio Oct   ##########################################             127.3
C10 picom exact   ###########################################            129.2
C10 picom OEA     #############################################          134.4
C10 knapcio rerun ###################################################    153.3
C10 knapcio Oct   ###################################################### 160.9
```

The two picom bars of a level come from one boot each in a single window, the two knapcio bars from
other boots. Reading down a level compares engines, reading across compares the two picom arms.

### Agentic totals, one character = 3 s, origin = the `0` column

Each bar is one boot's median of its three pass totals, `round(median ÷ 3)` characters, from the
paired window in section 3; an arm's two boots are the two bars under its name.

```
            |         |         |         |         |         |         |
            0        30        60        90        120       150       180
E1 exact    ######################################## 119.9
E2 exact    ######################################### 123.4
L1 lossy    ######################################### 124.4
L2 lossy    ######################################### 122.5
K1 knapcio  ############################################################ 178.6
K2 knapcio  ###################################################### 161.6
```

119.9 → 40 characters, 123.4 → 41, 124.4 → 41, 122.5 → 41, 178.6 → 60, 161.6 → 54. The axis ends
at **180 s**, which is where the longest boot (K1, 178.6 s, 60 characters) lands, so the scale has
no headroom above today's data and a future total over 180 s would run past the last tick. The two
knapcio bars stay clear of all four picom bars; that per-boot median non-overlap over two boots
per arm is the whole of the LIKELY ordering in section 3, and single-flight sequential runs with no
cell-level interleaving are why it is LIKELY.

### Readiness, one character = 0.05 in log10 of seconds

Twenty characters is a 10× step, so the bars compare orders of magnitude, not time.

```
picom cached    27.7 #############################
picom convert  166.4 ############################################
knapcio cold   708.4 #########################################################
```

27.7 s is with per-rank artifacts already cached; 166.4 s is the boot that had to convert weights
and Engram; 708.4 s is knapcio's one cold boot. Three different boots, not a like-for-like start.

## 5. Where each wins and why

- **Shipped pair, same window: picom ahead at one stream, level at two, behind at five and
  ten.** Against knapcio's October recorded row the shipped exact arm is **+18.5 % at C1**
  (83.4 vs 70.4) and **+8.9 % at C2** (90.8 vs 83.4), and **−12.4 % at C5** (111.5 vs 127.3) and
  **−19.7 % at C10** (129.2 vs 160.9); the shipped lossy arm is **+23.8 / +8.9 / −7.6 / −16.5 %**
  (`phase5/ladder.csv`, `phase6/ladder.csv`). Against the rerun boot's own knapcio ladder
  the shape holds and C1 widens:
  exact **+28.7 / +0.6 / −9.1 / −15.7 %**, lossy **+34.4 / +0.7 / −4.1 / −12.3 %**
  (`rerun-20261118/boot1-knapcio/ladder.csv`). Only the exact-vs-lossy pair is same-window; both
  knapcio columns are other boots and are read as the shape of the trade, not a margin — and both
  come from the old-fixture boot, so these are ladder cells, not the agentic comparison section 3
  now makes on the paired battery.
- **Agentic totals favor picom over SGLang across two boots per arm, and keep the two picom arms
  tied.** On the paired window (section 3) the per-boot median totals are SGLang **159.5–178.6 s**
  against exact **119.9–123.4 s** and lossy **122.5–124.4 s**, disjoint at both ends of the
  per-boot medians, so picom is **(159.5 − 119.9) ÷ 159.5 = 24.8 %** to **(178.6 − 123.4) ÷**
  **178.6 = 30.9 %** faster — knapcio takes 1.33× to 1.45× the wall clock (lossy: 23.2 % to
  30.3 %). That is **LIKELY, not established**:
  single-flight sequential runs of a 13-task set, two boots per arm, no cell-level interleaving. The
  earlier one-boot window's 18.2 % and 13.8 % medians are the same direction on a weaker design and
  are no longer the claim. Between the picom arms the ranges overlap in 122.5–123.4 s and both arms
  pass 75/78, so exact and lossy are indistinguishable on total wall clock and the choice between
  them rests on the concurrency curve and the lossy construction. The earlier
  50 % OEA deficit was the harness, not the knob: a 60 s tool-timeout path fired on either arm
  (section 3's historical rows), and no ranking from that table survives. Under concurrency OEA is
  still the faster arm — **+5.4 % at C5, +4.0 % at C10** against exact, one boot per side — and that
  ladder result is untouched by this.
- **Probe window, 16 concurrent users: knapcio ahead of the lossless picom arm (354.1 vs 325.9,
  +8.7 %) and 6.6 % behind the lossy one (377.5).** Drafting was **not** off on the picom side: the
  16-user window's request lines report multi-row verify steps with 3.08–4.90 drafts verified per
  step (`picom-gap-20261117/boot-a/rank.0.log:675,679,683,687`), and that boot captured a batch spec
  graph of up to 16 entries (`rank.0.log:44`; `DSGB10_DRAFT1=6` and `DSGB10_WIDE=64` at
  `launch.sh:190` are what extend drafting past one session). So the deficit is per-step cost at
  2–6 rows plus whatever scheduling difference remains — INFERRED, because no cell decomposes step
  time on either engine and the two engines' step sizes at 16 requests are not the same quantity.
- **Single stream (the 2026-11-17 probe window): picom ahead (84.5 vs 64.8 chat, +30.4 %; 142.5 vs
  119.8 code, +19.0 %).** Both engines speculate with 5 drafts, so this is a per-step cost
  difference, not a different strategy. INFERRED mechanism: picom's step is one hand-written graph
  with no host-side scheduler hop per token and its own ring, while SGLang's decode passes through
  its Python scheduler and TP collectives. Neither receipt decomposes the step. The lane's
  llama-benchy C1 rows point the same way (87.4 with a 74.8–99.4 spread against 67.18 ± 6.97), a
  different instrument and window, so it corroborates rather than confirms.
- **OEA is a measured knob on this arm, not an engine property.** `PICOM_OEA=4,12,9` — a batch-aware
  MoE re-route that keeps each row's top 4 experts but prefers the batch's core among top 12, from
  9 rows (`engine/kernels/moe.cu:1452-1455`) — moves the depth-0 ladder **+7.4 % at C5** (121.2 vs
  112.9) and **+8.0 % at C10** (135.8 vs 125.8) against the exact boot of the same window, and
  **−2.7 % at C1** (85.1 vs 87.5), inside that cell's 14.3 % spread (`phase1/ladder.csv`,
  `phase2/ladder.csv`). In the shipped pair the same knob reads +4.4 % C1, +0.1 % C2, **+5.5 % C5**
  (117.6 vs 111.5) and **+3.9 % C10** (134.4 vs 129.2; `phase5/ladder.csv`, `phase6/ladder.csv`), so
  the gain lands where the probe said it would, smaller because the shipped exact control read high
  at C5. Both gains exceed the within-boot spread on either side, but each side is one boot, so this
  is a same-window LIKELY effect, not an interleaved A/B. On accuracy the knob now loses nothing:
  three rerun runs of the OEA arm drop `shell-repro-rounding` zero times, while exact and knapcio
  each drop it once in three (section 3), so the pass counts do not separate the arms. The knob is
  lossy by construction and ships as a separate arm, never as the default.
- **The shortcut cost nothing on this lane's accuracy cells.** On the shipped pair: needle 3/3 at
  131,072 (12.1 s per cell) and the **983,040 rung PASS** at depth 10 on both (980,868 prompt tokens,
  97.1 s, `phase5/needle-983k-d10.json`, `phase6/needle-983k-d10.json`); house battery 37/37 on both
  (19 easy + 18 hard, all stable-pass, `phase5/house-exact.json`, `phase6/house-oea.json`; `hard-rev`
  answers `nurkraps`, the one item the knapcio line misses). The probe boots' 32,768 and 131,072
  cells were already 3/3 on both (12.8–12.9 s per 131k cell), and the 40,000-token grant returns
  byte-identical text on both probes (content sha256 `3616f8ac…`). That bounds the cost on exact-match
  retrieval and this fixed task set; it is not a free-form code-quality measurement.
- **The output ceiling is measured, and it is a slot question.** The shipped front end clamps
  `max_tokens` at its `--max-tokens` (`frontend/src/server.rs:522-528`), which used to be 32,768, so
  a longer request ended at 32,768 with `finish_reason: length` and no way to tell that from a stop.
  The shipped arms pass 262,144 (`launch.sh:311,324`): a 40,000-token request returns
  `completion_tokens` 40,000 and `finish_reason` `length` in 207.9 s (192.4 tok/s) on both
  configurations. Because `engine/server/serve.cpp:1195` admits only where `prompt + max_new` fits,
  every request that budgets 262k needs one of the four big slots, and a fifth waits in `wait_`
  rather than drawing a refusal or a timeout. Knapcio's own ceiling is now named rather than
  unknown: **32,768 new tokens**, from the engine's refusal of `min_tokens` 40000, with `max_tokens`
  above it accepted silently and `min_tokens` unenforced at the ceiling itself — so the engine
  bounds neither end of a long-form request (section 3, `paired-20261118/K2/ceiling/`).
- **Prefill chunking is a budget, not a win.** knapcio's 16384-token chunk is 2.35× its 8192 control
  on 1M prefills (`launcher.py:170-178`, `~/benchmarks/tp4-window-20261024/`), and its
  decode-between-chunks feature costs 17–28 % of ladder throughput and therefore ships off
  (`launcher.py:270-278`). The shipped picom arms prefill 16384 rows (`--prefill-rows 16384`) and have
  no interleave at all (`docs/engine.md:451-460`); the probe arm's 8192 rows is the one engine
  difference between the two ladder tables. No cell here measures a long-context prefill on both
  engines, so no direction is claimed.
- **The client contract is where the engines differ most in kind.** SGLang's surface honors
  `return_token_ids`, a real thinking channel and cache accounting; picom's front-end is a thin
  hand-written parser that drops unknown fields silently, has no reasoning channel, and takes its
  output ceiling from a launcher flag (section 2). For an agent workload that matters more than 10 %
  of decode, and it is the one difference here that is demonstrated by receipts rather than inferred
  from a total.

## 6. What is not comparable, and why

_Instrument._

- **No cell-level interleaving.** The paired window alternates boots (`E, K, L, L, K, E`), but every
  cell inside a boot runs single-flight and sequentially, and no two engines were ever measured at
  the same time; the shipped ladder boots ran back to back and never alternated.
- **Two boots per arm: the agentic gap is disjoint at both ends of the per-boot medians and still
  LIKELY.** All 18 passes are unpolluted (`polluted_runs` 0, section 3) and the per-boot median
  totals do not overlap — exact
  119.9–123.4 s and lossy 122.5–124.4 s against SGLang 159.5–178.6 s — which is why the 24.8 % and
  30.9 % range-end gaps read as LIKELY rather than established. What stays uncontrolled is the
  absence of cell-level interleaving on a 13-task single-flight set. Within picom, the two ranges
  meet in 122.5–123.4 s, so the ~3 % difference is not a claim.
- **Two picom ladder generations and two knapcio ladders, no power/thermal/RDMA capture**, and the
  readiness comparison is one cold boot against one warm-cached boot, not a like-for-like start. The
  knapcio rerun boot and the picom ladder boots are separate boots, so no knapcio-vs-picom ladder
  margin here is interleaved.

_Coverage._

- **The 983,040 needle gap closed, not widened.** Both shipped boots pass it at depth 10; what stays
  unmeasured at that length is decode throughput, since the reply is a few tokens and no ladder
  covers depth > 0.
- **No long-context decode ladder.** The 131k and 983k needles are one retrieval probe each, and no
  repeated-prefix / multi-turn cell exists — so the prefix-cache difference (SGLang reports hits,
  picom ran cold in every receipt) is unmeasured as a cost.
- **The BFCL tools leg is scoped, not full.** 100 of 1,240 questions (`--limit 20` across five
  categories) on the first boot of each arm scored 87/100 on both engines with `transport_errors` 0
  (section 3). It is the first tool-calling score here and it separates nothing; the full leg is
  still unmeasured.
- **Vision is functional only.** The path answers; no cost, latency or quality cell exists.
- **No free-form quality metric.** The needle and house cells are exact-match and pass/fail; nothing
  here scores generated code or prose.
- **OEA's accuracy question is answered on this battery only.** It loses `shell-repro-rounding` in
  two of three runs where exact loses `golden-regression` once and knapcio loses
  `shell-repro-rounding` once (section 3), which bounds the cost at this fixed task set and says
  nothing about tasks that are not in it.
- **`copies 16` is not a prefix-sharing cell** on either engine: the instrument randomizes the prefix.

_Design._

- **Different budgets by construction**: KV pool vs session store, 16 uniform slots vs 4 big + 12
  small, chunked prefill at 16384 tokens vs whole-request prefill of 16384-row chunks.

## 7. What to try next

1. **Interleave at the cell, not the boot.** The paired window already alternates boots
   (`E, K, L, L, K, E`, section 3), so what is left is running the same 13-task battery in
   interleaved turns against both engines, and putting the ladder's C1, C5 and C10 (where the lossy
   margin is largest) inside one alternation at 5 runs/cell. The agentic ordering is disjoint at both
   ends of the per-boot medians over two boots per arm and still LIKELY; an interleaved run is what
   would take it to established, and where the shipped +5.5 % / +3.9 % has to settle into the
   shortcut or the boot order.
2. **Run the full BFCL leg** — all 1,240 questions, same fixture revision and turn budget on both
   engines. The scoped 100-question leg is a dead heat at 87/100 (section 3), so it settles nothing
   about whether the client-contract differences in section 2 (thinking channel, token-id echo,
   unknown-field handling) cost anything an agent can feel.
