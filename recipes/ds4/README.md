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
- [Measured: TP=4 ladder and suite](#measured-tp4-ladder-and-suite)
- [Measured: the v2.4 serve line](#measured-the-v24-serve-line)
- [The vendored adapter set](#the-vendored-adapter-set)
  — what the knapcio adapter overlay is, component by component, and what its build gate protects.
- [Attic index](#attic-index)

## deepseek-v4.1-flash-knapcio-tp4-1m-sglang

| | |
|:--|:--|
| Recipe | `recipes/ds4/deepseek-v4.1-flash-knapcio-tp4-1m-sglang.yaml` |
| Engine | SGLang (`sglang.launch_server`), driven through the mod shim `recipes/ds4/mods/dsv41-sglang-overlay` |
| Model | [`deepseek-ai/DeepSeek-V4.1-Flash-1017`](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash-1017) (native MXFP4/F8, official weights, 2026-10-17 refresh) |
| Pin | `model_revision: 1bae0e10…` (the refresh's repo head, 2026-10-17) — all 48 shards are new objects vs the pre-refresh checkpoint, so the pin is what selects the refresh; the image's baked `fb2764a5…` is the superseded base and is never served |
| Size / fit | 510 GB, `mem_fraction_static` 0.78, `chunked_prefill_size` 8192 |
| Topology | TP=4, EP=1 — four GB10 nodes, one rank per node |
| Context | 1,048,576 tokens served |
| Spec decode | DSpark k=5, verify-all |
| Transport | RoCEnante RDMA (shipped on) |
| Image | `littlecedar/dgx-spark-dsv41:canary-roce-aff52fa5@sha256:3f4480818acb…` — **production overlay since 2026-10-26 (adoption)**: vendored from upstream knapcio `aff52fa5` (v2.5+, 79 commits past the v2.4 pin; quarantined v2.4 lineage retired, carries the SGLang #41303 SWA-safety backport and ~26 zero-fuzz dsv41 backports on the same `f80c91a4b` tree) with the local health-port patch, base digest-pinned (`Dockerfile.knapcio-dsv41-aff52fa5`; full in-image gate green). Healthcheck note: a first same-tag build `21d1bf34…` shipped the unpatched boot.py (its healthcheck probes 8888 and reads unhealthy while serving — patch only implements the health branch, serving unaffected); the corrected `3f4480818acb…` is the shipped image and recipe `container:` target. The v2.4 line it replaces: `canary-roce@sha256:acfc331a…` (rebuilt 2026-10-22 digest-pinned as `canary-roce-20261022` `sha256:0cbe228a…`, drop-in — `~/benchmarks/ds4-expin-20261022/image-compare.txt`) — vendored header kept at `Dockerfile.knapcio-dsv41` for provenance. |
| Tags | `official`, `fast`, `large_context`, `lcg_favorite`, `vision` |
| Measured | **TP=4 ladder, first C2/C5/C10 row for this lane (2026-10-18)** — C1 **67.18 ± 6.97** (pooled n=25, CV 10.4 %) / C2 89.9 / C5 113.4 / C10 115.4 t/s, two **v2.3-serve-line** boots, 5 runs/cell (`benchmarking/concurrency-ladder.yaml`; `~/benchmarks/tp4-20261018/`, see [Measured](#measured-tp4-ladder-and-suite)); the shipped v2.4 line's own takes — interleave flag off — are in [the v2.4 section](#measured-the-v24-serve-line). Depth-0 C4/C8/C16 118.9 / 107.5 / 115.9 (3 runs/cell, `benchmarking/ds4-sglang-depth0-ladder.yaml`, `--fresh`) at parity with the V4.1 base inside the two arms' spreads; KV pool 9,277,952 (the 9.4M pin clamps), prefill 119k 29.5 s / 231k 64.8 s (`~/benchmarks/ds4-knapcio-1017-20261018/arm-1017/`). The earlier single-boot **81.0** is one draw from that C1 pool (2.0 σ above its mean), not an attributable gain |
| Boot-verified | 2026-10-18, warm relaunch **545.9 s** (weight load 300.6 s + DSpark draft 66.8 s, packed Engram on all four ranks), `/v1/models` = the 1017 id, chat answers, vision **3/3** + text control (`~/benchmarks/ds4-knapcio-1017-20261018/`). Standard suite on a later boot, one serve: house **36/37**, needle **3/3 at 32k / 131k / 983k**, tool-eval-bench **90** (`~/benchmarks/tp4-20261018/knapcio-suite/`) |

**Adoption boot (2026-10-26, quartet `c989632ede4f538e_06d0703ef003`, canary-roce-aff52fa5):**
ladder C1 **64.08 ± 3.66 agg** (bar ≥ 64.0 — clears by **+0.08, i.e. at the edge of the bar's
noise band**) / C10 **152.24 ± 13.88 agg**, peak **202.8 t/s**; house **36/37**
(hard items 17/18); needles 32,768 **10/10** and 131,072 **10/10**; the 983,040 rung was still
in flight at ship time (started 23:31Z, 7,200 s wrapper — not a ship gate). Receipts
`~/benchmarks/tp4-window4-20261026/` on the head. Every landed bar cleared its threshold on the
first boot — adoption confirmed: **matches the shipped bars, C1 at the bar's edge** (no headroom
claimed; the flag-track arms must keep the same-window paired comparison to read any C1 delta).

The 983,040 rung landed after the ship (00:07Z, wrapper in full): **10/10 PASS**, top rung
980,835 prompt tokens, finish `stop` on every item, 289.7 s at depth 10 — the full needle bar
3/3 on the new overlay closes clean (`trial-needle-983040.json`).

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

### Measured: TP=4 ladder and suite

Two same-config boots on the **v2.3 serve line** (0.80 static, 4096-token chunks, the 9.4M pin) in
one 2026-10-18 TP=4 window, on
`benchmarking/concurrency-ladder.yaml` (depth 0, 2048-token prompts, 128-token replies, prefix
caching, 5 runs/cell). `±` is the **sample sd of the per-run decode samples**
(`is_context_prefill_phase: false`); the receipt JSON's own `tg_throughput.std` is the
population sd, 0.894× these.

| cell |   boot A (`knapcio-ladder`) | boot C (`knapcio-ladder-suiteboot`) |    A→C |
|:-----|----------------------------:|------------------------------------:|-------:|
| C1   |   69.65 ± 11.51 (56.8–87.9) |            69.28 ± 5.25 (64.0–77.5) | −0.5 % |
| C2   |    89.89 ± 3.57 (85.5–95.4) |            86.40 ± 3.59 (80.3–89.6) | −3.9 % |
| C5   | 113.44 ± 6.84 (105.1–123.6) |         108.78 ± 14.19 (86.5–125.4) | −4.1 % |
| C10  | 115.36 ± 6.62 (107.7–123.1) |         116.27 ± 6.22 (105.2–119.8) | +0.8 % |

Per cell (C1/C2/C5/C10), pp t/s: boot A 3703 / 4004 / 4532 / 4849, boot C 3674 / 4125 / 4567 /
4671; TTFT ms: 556 / 1018 / 2167 / 3188 and 560 / 993 / 2029 / 3347.

**C1 is the pooled number, not any one cell.** Four same-config C1 takes in this window — 69.65
(n=5, boot A), 66.40 (n=10, boot A, second bench, `knapcio-c1-extra`), 64.16 (n=5, the γ=5 arm
of the pair, `gamma-p1-g5`), 69.28 (n=5, boot C) — pool to **67.18 ± 6.97 t/s, n=25, CV 10.4 %,
range 56.4–87.9**. That pool, not a 5-run cell, is what the v2.4 baseline's **59.21 ± 3.54**
(3 runs, one boot — `attic/ds4/AGENTS.md` §12.17) is compared against: **+13.5 % in the means,
with overlapping intervals**. The 81.0 read off the earlier 1017 boot is 2.0 σ above the pool's
mean — a warm-cache draw, not a weight property. Only an interleaved v2.4-vs-1017 A/B settles a
C1 delta; this pool narrows the question and does not close it. C2 is the lane's first cell taken
at exactly 2, C5/C10 its first at 5 and 10, so the C4/C8/C16 row above is a different shape, not
a comparison.

**Boot facts, both boots.** KV pool **9,277,952** full tokens — the launcher's 9.4M pin is
clamped to the engine's profiled value, never refused — with swa 51,712 / c4 2,319,488 / c128
72,484 (`DSV4 pool sizes: …`). TTR **487.8 s port / 501.7 s HTTP** (boot A; task
`a2e141223b52793c_7afff0589a33`), 491.9 / 505.7 s (boot C, same deployment id, relaunched).
`ROCE_TP8_READY` reports `world_size 4` on all four ranks, `Engram shards present for rank r/4`
on all four (no pack on either boot), and the 1017 template overlay resolves on the serving rank
(`Using default HuggingFace chat template with detected content format: openai`, once).
`/v1/models` → `deepseek-ai/DeepSeek-V4.1-Flash-1017`, `max_model_len` 1048576.

**Standard suite (boot C, one serve, `eval-suite.py` 1.0.1).** contract ok; house **36/37** —
easy 19/19, hard 17/18, the one miss `hard-rev` (reply `nrukraps`); needle **3/3 at each of
32,768 / 131,072 / 983,040** (top rung reached 981,950 prompt tokens, 31 min for the ladder);
tool-eval-bench **90** — 27/30, 15 scenarios, 13 pass / 1 partial (`TC-14`) / 1 fail (`TC-03`,
`wrong_args`), profile `benchmarking/standard-suite.yaml`, ref v2.6.0.

**The two open accuracy legs were closed on 2026-10-22** (same recipe and node set, one fresh
four-node boot, task `sparkrun_a2e141223b52793c_7afff0589a33`): hard **ARC 93.5 %** (187/200) and
**GSM8K 97.5 %** (195/200), thinking off, seed 1234, `--hard-limit 200`, **0 errors / 0 empty
replies**, both legs in one serve (427.6 s, suite 1.0.1, verdict `ok`). `/v1/models` at
`max_model_len 1048576`, Engram packed on both layers (hit_rate 100 %). Receipt
`~/benchmarks/tp4-20261022/knapcio-arc-gsm8k/` (`REPORT.md`, `suite/hard/`, `serve-node0..3.log`).

**DSpark γ=3 is a proven negative on this image.** Booted with `-o dspark_block_size=3`, every
rank logs `DSpark gamma mismatch: using gamma=3 (from speculative_num_draft_tokens=4) but draft
config block_size=5` and then all four die at decode-graph capture —
`adapter/verify_cap.py:308` → `dspark_planner.py:267`,
`RuntimeError: Sizes of tensors must match except in dimension 2. Expected size 5 but got size 4`
(~8 min in; the engine's own `DSV41_VERIFY_CAP=conf:0.1` builds a size-5 confidence tensor
against the runner's 4 verify tokens). Only the checkpoint's block size 5 coheres end to end, so
**no γ=3 number exists and no gamma delta can be quoted**; the γ=5 arm of that pair is the
64.16 ± 7.97 take in the C1 pool. The knob is reachable at all only since 2026-10-18:
`defaults.dspark_block_size: 5` in the recipe, `--dspark-block-size` in the launcher (applied
after `apply_recipe_env`), because `-o env.DSPARK_BLOCK_SIZE=` was silently clobbered by the
launcher's `RECIPE_ENV`. Shipped behaviour is unchanged (5). Full mechanism and the file:line
chain: `attic/ds4/AGENTS.md` §12.18.

Receipts: `~/benchmarks/tp4-20261018/` — `knapcio-ladder.*`, `knapcio-c1-extra.*`,
`knapcio-ladder-suiteboot.*`, `knapcio-suite/`, `knapcio-teb.*`, `gamma-p1-g5.*`,
`serve-p1-g3.log`, `knapcio-serve.log`, `knapcio-launch.log`, `knapcio-models.json`.

### Measured: the v2.4 serve line

Three TP=4 boots (`.30`–`.33`, one four-node job at a time, `--transfer-mode local`) on the same
image (`…:canary-roce@sha256:acfc331a…`), the same checkpoint pin and the same
`benchmarking/concurrency-ladder.yaml` as the two boots above. They differ only in the launcher's
serve line. `±` is the **sample sd (ddof 1)** of the five per-run decode samples; each receipt
JSON's own `tg_throughput.std` is the population sd, 0.894× these.

| cell | interval **on**, 7.5M pin (`ladder.json`) | interval off, 7.5M pin (`pd-off/`) | interval off, 6.85M pin (`confirm/`) |
|:-----|------------------------------------------:|-----------------------------------:|-------------------------------------:|
| C1   |                 60.22 ± 13.00 (39.0–71.4) |          51.84 ± 17.68 (23.4–64.2) |            53.40 ± 21.35 (19.5–69.9) |
| C2   |                  73.16 ± 4.96 (68.9–81.6) |           88.35 ± 6.33 (81.7–96.7) |            82.02 ± 10.14 (71.0–94.8) |
| C5   |                95.10 ± 14.66 (69.3–106.0) |        131.83 ± 8.50 (122.4–139.7) |         130.97 ± 10.50 (117.4–143.4) |
| C10  |               101.49 ± 10.45 (89.3–114.2) |        123.49 ± 8.45 (114.3–135.1) |          119.79 ± 8.09 (107.5–127.1) |
**(a) The image pin moves nothing.** All five TP=4 SGLang boots in this document (boots A and C
above and these three) ran the same image digest (`acfc331a…`, read from each boot's `bench.log`),
so no decode change is attributable to it. The v2.4 *line* with its interleave flag on was slower
than the v2.3 line on every cell: C2 −17.0 %, C5 −14.4 %, C10 −12.4 % against the v2.3 line's
means (89.1 / 111.1 / 115.8 t/s). Whatever the v2.4 line buys, it buys with the flag off.

**(b) `--prefill-decode-interval 2` costs 17–28 % of ladder throughput and ships off.** Against the
same-pin (7,500,000) interval-off boot: C2 73.16 → 88.35 (−17.2 % with the flag on), C5 95.10 →
131.83 (−27.9 %), C10 101.49 → 123.49 (−17.8 %). It is a multi-user *latency* feature (a short
request is answered mid-prefill), not a throughput one. `PREFILL_DECODE_INTERVAL: "0"` is the
launcher default; the knob is in `AB_ENV`, so `-o env.PREFILL_DECODE_INTERVAL=2` turns it back on
per launch. At 0 the flag is omitted entirely (`launcher.py:357-382`), so the engine default
applies.

**(c) With it off, C5/C10 beat the v2.3 line; C2 does not.** C5 131.83 (pd-off) and 130.97
(confirm) against 113.44 / 108.78 — **+18.7 % / +17.9 %** on the line's 111.1 mean, +16.2 % /
+15.5 % against its best cell. C10 is **+6.6 % / +3.4 %** on the mean (123.49 / 119.79 vs 115.8)
and +6.2 % / +3.0 % against its best (116.27). C2 against the line's best cell is −1.7 % to −8.8 %
— at or under the v2.3 cells, not above them — so the v2.4 line's gain is C5 and C10, not C2.
The pin change between the two off boots (7.5M → 6.85M) is inside their spreads and is not a
throughput factor.

**(d) The C1 cells are cold-contaminated — none is the arm's C1.** Every ladder's first run is
19–39 t/s and the cell mean is set by the ramp: 39.0 / 64.5 / 57.4 / 68.8 / 71.4 (on), 23.4 /
45.6 / 62.3 / 64.2 / 63.8 (off, 7.5M), 19.5 / 45.5 / 63.4 / 69.9 / 68.7 (off, 6.85M). These are
first-ladder-on-a-cold-boot numbers, not the arm's single-stream figure. The pooled
**67.18 ± 6.97** (n=25) above stays the C1 reference until an interleaved C1 re-take on the
shipped line.

**The pool pin: formula, measurement, correction.** At 0.78 the engine's own budget arithmetic
predicted 7,687,277 full tokens — 9,277,952 measured at 0.80, minus 1,564,260 for the smaller
static pool (0.02 × 121.7 GiB / 1670.75 B per token), minus 26,415 for 64 extra prefix tails
(384 SWA slots × 1,795.8 B each); the arithmetic is pinned in
`tests/test_ds4_recipes.py:1326-1336`. The boot measured **6,993,408**, so that formula
under-estimated the tails' cost by ~0.7M tokens
(`max_total_tokens=7500000 is larger than the profiled value 6993408. Use the profiled value
instead.`, `pd-off/boot-evidence.txt`, 21:33:43Z). A pin at or above the budget is silently
clamped, so the pin became **6,850,000** (97.9 % of the measured budget). The confirm boot reports
**6,849,792** with **no clamp line** — the pin floored to the engine's 256-token page
(6,850,000 → 256 × 26,757) — and `available_gpu_mem` 17.53 GB against 16.70 GB at the clamp. The
boot line to read is `max_total_num_tokens=…`, then `chunked_prefill_size=8192`,
`max_prefill_tokens=16384`, `max_running_requests=16`, `context_len=1048576`. The guard is
`tests/test_ds4_recipes.py::test_launcher_v24_serve_line`: it asserts 0.78 / 8192 / 16, that the
pin is > 0 and **below 6,993,408** ("must stay under the MEASURED value"), that the default
assembly is `--swa-prefix-tails 128` and nothing else, and that a launch-time `0` disables each
knob. It deliberately does not pin the exact integer: any value under the measured budget is
safe, and every boot re-derives it.

The cost is real: 6.85M page-shared tokens holds **six** full 1M contexts, where the
0.80 / 4096 line's 9.28M held nine.

**Quality on the new line was not re-taken.** The house battery ran on the interval-**on** boot
only — **36/37** (easy 19/19, hard 17/18; `house/summary.json`) — and neither interval-off serve
ran a quality leg, so that number transfers to the shipped line by assumption, not measurement.

**Receipts.** `~/benchmarks/ds4-v24-line-20261018/`: the interval-on boot is `ladder.{csv,json,yaml}`
+ `house/` + `serve-evidence.txt` (the retained serve-log slice is the bench window, so that
boot's own startup lines — its clamp included — were not captured; its launch line was recorded
in `mad-science/TODO.md` at the time, and the slice does show 8192-token prefill batches
(`#new-token: 8192`), `pd-off/boot-evidence.txt` + `ladder.*`, and
`confirm/boot-evidence.txt` + `ladder.*`. Both interval-off `boot-evidence.txt` files prove the
off state in `server_args`: `prefill_decode_interval: 0`, `swa_prefix_tails: 128`.

### Measured: 2026-10-22 live baseline boot (online, scheduler-placed)

The owner's verbatim command, no flags — the recipe's `min_nodes: 4` plus the default cluster's
hosts did the placement:

```bash
sparkrun run deepseek-v4.1-flash-knapcio-tp4-1m-sglang
```

| | |
|:--|:--|
| Task | `sparkrun_a2e141223b52793c_d7960e70d961` (containers `…_node_0`…`_node_3`) |
| Rank set | `.30` (head) `.31` `.32` `.33` — "4 of 6 hosts from default cluster 'WOPR' (occupancy-sparse scheduler)". Not chosen by hand: `-H` was not passed |
| TTR | **544 s** to `The server is fired up and ready to roll!` / first `/v1/models` 200 (~68 s of it weight load, 48/48 shards per rank) |
| `max_model_len` | **1,048,576, unclamped** — what the engine reports, matching the recipe |
| KV pool | **`max_total_num_tokens=6,849,792`** = 97.9 % of the 6,993,408 budget at 0.78, `max_running_requests=16` |
| House | **37/37** (easy 19/19, hard 18/18), `--max-tokens 4096`, **thinking on**, 30.9 s for all 37 items — vs the historical **36/37** |
| Needle | **5/5 at ~999k prompt tokens** (998,446 / 997,583 / 999,044 / 999,281 / 999,241; 592.8 / 626.2 / 550.1 / 567.9 / 543.9 s), serial c1, depths 10–50 %; **depths 60–100 were NOT attempted** (the serve became production traffic — a 10-min 1M prefill on 16 slots would have blocked the handover), so this is five depths at the full window, not the whole ladder |
| Ladder | C1 **60.20** / C2 85.13 / C5 114.87 / C10 **116.86** t/s, n=5, decode rows only (`is_context_prefill_phase: false`), `--skip-run` on this same boot, 4/4 tasks in 143.8 s |
| Receipts | `~/benchmarks/knapcio-tp4-20261022/` on the head: `REPORT.md`, `boot.log`, `perf-ladder.{yaml,json,csv}`, `sparkrun_serve.log`, `battery-thinking-on.json` |

**Every cell above carries this session's own traffic.** The rank set is `.30`–`.33`, which are the
fleet's inference nodes: the same four ranks were answering the agent fleet's requests — this session's
included — while the ladder, house and needle legs ran, so the numbers are contended by traffic the
benchmark campaign itself generated. The C1 deficit against the historical 69.28 is therefore `LIKELY`
self-inflicted contention rather than a property of the arm, `SPECULATIVE` because nothing was measured
with and without that traffic in the same window; and 69.28 is not a like-for-like control in any case,
having been taken under different traffic conditions and a different node set. The clean comparison
needs a window in which the ranks answer nothing else.

**JSON completeness (checked, because a previous C10 row was non-evidence).** `perf-ladder.json` was
re-parsed after the run: 21,898 bytes, `model = deepseek-ai/DeepSeek-V4.1-Flash-1017`,
`max_concurrency = 10`, four records, each with `pp_throughput`/`tg_throughput` means and five
`values`, `is_context_prefill_phase: false` on every row. The C10 row exists and parses.

**C1 gap is an open question, not a regression.** C1 60.20 sits below the v2.3 reference 69.28 and
below the v2.4 interval-off 123.49-class C10 shape it otherwise matches; the rank set here includes
the **head node `.30` as a TP rank**, which also carries the control's ssh and syncthing duties —
whereas the historical 69.28 came from a different node set. The clean test is a same-window
`.31`–`.34` boot once `.34` is a resident (it is not a rank here), and it was deliberately **not**
run in this window. C10 (116.86) is at the historical 116.27, so the shortfall is concentrated at
low concurrency, which is what a busy head rank would cost first.

### Measured: the `aff52fa5` overlay survey arms (2026-10-26 window 4)

All four speedup-survey flag arms measured on this lane's shipped line (boots on `.31`–`.34`,
receipts `~/benchmarks/tp4-window4-20261026/`, analysis in `mad-science/DEEPSEEK.md` §8.4/§10.3/§10.4/§10.8):

| arm | lever | verdict |
|:--|:--|:--|
| candidate 6 — `reasoning_effort` high vs max | request-level, thinking on, paired 10 tasks × 2 rounds | **2.96 %** paired reasoning-token saving (878 → 852), pass 10/10 both arms, 0 flips — below the 10 % bar and the TP=2 precedent's 10.6 %; keep `high`, no ship case. The knob is wired: the template default IS `high` (chat-default ≡ high byte-identical; `max` moves `hard-rev` 82 → 119 tokens) |
| S1 — `--enable-cache-report` | reporting only (reach via `-o env.EXTRA_SGLANG_ARGS=…`; a bare `-o extra_args=` is inert on the sglang runtime) | **the radix cache already reuses**: repeats 2–8 report `cached_tokens` 28,928/28,952 at 32K and 119,552 at 131K (99.8–99.9 %), revisit TTFT 0.29 s / 0.46 s; the no-flag boot collapses TTFT identically but reports nothing — the 2026-10-06 "zero-hit" read (§8.4) was the missing usage field, not a dead cache |
| S2 — `--schedule-policy lpm` | alongside cache-report | **null** — hit fraction and revisit TTFT identical to S1 (28,928 / 119,552 cached; 0.29 s / 0.46 s); fcfs stays |
| S3 — `--min-free-slots-delay 1` | same-line A/B vs a plain-arm control boot, depth0 ladder 3 runs/cell `--fresh` | **measured negative — do not ship**: C4 104.20 ± 6.08 vs 116.20 ± 7.47 (−10.3 %), C8 148.44 ± 7.32 vs 159.61 ± 8.71 (−7.0 %), C16 135.61 ± 12.44 vs 151.80 ± 6.69 (−10.7 %); max running-req 15 (treatment) vs 16 (control). The plain control's C8/C16 (159.6/151.8) also prove the shipped line's gain over the v2.4-era depth0 control (§7.4's 107.5/115.9) is the serve-line change, not any flag |

The 2026-10-22 "online baseline" C1/C4 rows above are **not** comparable to the S3 A/B: that boot ran
under fleet traffic on different ranks; the S3 pair is same-line, same-profile, back-to-back boots.

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

- **Disk residency for the four ranks, measured 2026-10-22.** The `-1017` body must be a complete
  per-node tree; the plain `deepseek-ai/DeepSeek-V4.1-Flash` repo is a *builder* input (Engram
  shards 47–48, `tools/build-dsv41-combined.py`), not a boot input, and only one copy is kept
  cluster-wide:

  | node | `-1017` body (`du -s` on `hub/models--…-1017`) | plain `V4.1-Flash` | free `/` after the 2026-10-22 sweep |
  |---|---|---|---|
  | `.30` | complete, 498,351,024 KB (475.2 GiB) — head of the 2026-10-22 boot | removed | 117 G |
  | `.31` | complete, 475.2 GiB (real-file tree, no `blobs/`) | **present — the only copy** | 794 G |
  | `.32` | complete, 475.2 GiB | removed (`hf cache rm`, 510.3 G) | 1.1 T |
  | `.33` | complete, 475.2 GiB | removed (510.3 G) | 1.2 T |
  | `.34` | **complete, 498,350,468 KB** — all 57 snapshot entries byte-size identical to `.31` (diff of size+name lists empty); the 556–608 KB `du` delta is filesystem/metadata, not a short file, and no rsync remained at the end | removed (510.3 G) | 506 G |
  | `.35` | absent | removed (510.3 G) | 705 G |

  A body transfer has **exactly one owning session**. Measured 2026-10-22: two sessions each believed
  they owned the same `.31`→`.34` copy, one killed the other's `rsync` pids, and rsync deleted its own
  temp files — the destination went from 390 GB (78 %) back to 307 GB (60 %), ~83 GB of progress
  destroyed about seven minutes from completion. Check `ps -o pid,ppid,lstart,args` before signalling
  anything on a node (a pid you did not create is someone else's work), and do not move a body over the
  management subnet while a RoCE copy is on the critical path — use
  the plane-A/plane-B rail addresses.

### Knobs a user cannot infer

- **`max_model_len` is per-request; the KV pool is separate and pinned.** The
  overlay launcher pins `MAX_TOTAL_TOKENS=6,850,000` at `mem_fraction_static=0.78`
  and `chunked_prefill_size=8192`; the engine profiles **6,849,792** at that line
  and the pin must stay under the *measured* budget — a larger pin is *clamped*
  (6,993,408 at a 7.5M pin), never refused. Re-derive it by reading
  `max_total_num_tokens=` on every boot (see
  [the v2.4 section](#measured-the-v24-serve-line)); `-o env.MAX_TOTAL_TOKENS=0`
  unpins. The pool is **page-shared, not extent-reserved**: 16 concurrent requests
  each declaring ~1M tokens were all admitted (the bound is the
  `MAX_RUNNING_REQUESTS=16` cap and total actual tokens, not a per-stream
  reservation). Keep `mem_fraction_static` at 0.78 — the 8192-token chunks need
  the headroom (a 1M prefill at 0.78 leaves the head 5.7 GiB, at 0.80 only 2.7
  GiB), and higher has wedged nodes.
- **The two v2.4 flags are per-launch switches.** `--swa-prefix-tails 128` ships on
  (the engine default is 64 at 16 slots); each extra tail is one sliding window plus
  a page (384 SWA slots), so the 64 extra cost 26,415 tokens of budget and buy room
  to keep a 388K session cached (revisit 1.5 s instead of an 89 s re-prefill).
  `--prefill-decode-interval 2` ships **off**:
  measured cost **17–28 %** of ladder throughput at C2/C5/C10, and it is a
  multi-user latency feature (`-o env.PREFILL_DECODE_INTERVAL=2` to enable). Both
  are `AB_ENV` keys, and `0` omits the flag rather than passing it.
- **`DSV41_FAST_LOAD` lives in the launcher, not the recipe** — there is no
  recipe-side knob (the recipe carries no `env:` block; everything is the
  launcher's `RECIPE_ENV`). Shipped `"1"` as of 2026-10-22 (owner decision:
  ~220 s saved per boot over the pool). The eager path cuts engine start from
  343 s to ~124 s but shrinks the host's allowed KV budget; upstream's own docs
  quote 3–6 % at EP2 (`docs/fast-load.md`) and the older 3–13 % in its README
  summary, while the EP1 slab rework "gave back ~0.7M tokens". The lane's EP1
  delta is unmeasured, so the pin is **not** pre-scaled: it stays at 6.85M for
  the first fast-loader boot and is re-derived from that boot's `full_token` if
  it clamps. `"0"` is the rollback. At the old 9.4M pin's 9.28M pool
  concurrency was unchanged either way (measured before the 2026-10-18 pin
  change; not re-taken since).
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
- **The DSpark verify window (γ) stays at 5 — and γ=3 does not boot at all.** A fork
  pre-registered γ=2 as a win; the on-lane same-window paired A/B (2026-10-10) measured it *losing*
  at moderate concurrency (C4 −5.3%, C8 −2.9%). On this image γ=3 aborts at decode-graph capture
  on all four ranks (`adapter/verify_cap.py:308` → `dspark_planner.py:267`: `Expected size 5 but
  got size 4`), because the checkpoint's DSpark draft block size is 5 and only 5 coheres with the
  shipped `DSV41_VERIFY_CAP=conf:0.1` adapter. The knob is `defaults.dspark_block_size` /
  `--dspark-block-size`; `-o env.DSPARK_BLOCK_SIZE=` does **not** work (the launcher's `RECIPE_ENV`
  is applied over the process env). Evidence: [Measured](#measured-tp4-ladder-and-suite), and
  `attic/ds4/AGENTS.md` §12.18 for the mechanism.
- **The checkpoint revision is pinned in the recipe, not the image.** The image
  bakes `fb2764a5…` but the launcher sets `SKIP_PREPARE=1` and serves the
  sparkrun-distributed snapshot, so `model_revision:` alone decides what is served.
  `launch.json` records the baked revision and is **not** evidence; the launcher's
  `serving …/snapshots/<sha>` line is. Moving the pin invalidates every receipt in
  the lane docs.
- **Long-context prefill is flat-cost per chunk, not compute-bound.** Measured on the 2026-10-22
  live boot: 1M prefill runs **~1.7× the per-token cost** of short-context prefill (mean **1738** t/s
  over five ~999k-token requests vs a cold 2048-token pp of **2897** t/s at C1, and **1.97×** against
  the cold 8192-chunk first-chunk median **3428** t/s). The cost is *not* expert all-to-all —
  `routed MoE at EP_SIZE=1` means all 384 experts are local per rank, so no dispatch exists — and it
  is not compute: 40 layers × 495 MFLOP/token ≈ **19.8 GFLOP/token** ⇒ ~0.02 EFLOP for 1M tokens, i.e.
  ~35 TF/s aggregate at 550 s, and ~15 GB/s/rank of weight traffic. What is left is ~122 eager
  **8192-token chunk launches** (prefill CUDA graph is disabled for this model) each costing a flat
  ~4.5 s; per-chunk throughput decays 3428 → 1447 t/s early and then saturates at ~1500 t/s rather
  than following 1/L. **Not run, recorded as the candidate:** `-o env.CHUNKED_PREFILL_SIZE=16384`
  halves the eager launch count at 1M and is the only knob that plausibly moves long-prefill cost
  without touching the 16-slot decode path — it needs a fresh boot and an A/B, so it waits for a
  window where this serve is not the owner's production endpoint. Forensics: `~/benchmarks/knapcio-tp4-20261022/REPORT.md`.
- **The dense FP8 GEMM backend is declared by the recipe, not substituted by the image — boot-gated.**
  Recorded 2026-10-22 and left unfixed then because the serve was live: the boot log carried
  `DSV41_MXFP8_BACKEND=b12x requires --fp8-gemm-backend flashinfer_cutlass; effective value
  'auto (omitted)' replaced`. b12x **is** active and the value the engine ran with was
  `flashinfer_cutlass` either way, but it was *stamped in* by `boot.py` and declared by nobody, so
  anyone reading `--fp8-gemm-backend` as "unset" mis-diagnoses prefill GEMM behaviour. The recipe now
  spells `--fp8-gemm-backend flashinfer_cutlass` in `command:` and the launcher forwards it into
  `EXTRA_SGLANG_ARGS`. The arg still cannot win the *order* — `required_sglang_args()`
  (`boot.py:264-287`, called at `:376` @ `27616bec`) strips every `--fp8-gemm-backend` from the extras
  and appends its own last — so the repair is that the value re-emitted as the last one is the value the
  recipe declared: the substitution warning cannot fire, and if the image's `DSV41_MXFP8_BACKEND` default
  ever goes away the declared flag, not `auto`, is what reaches the engine. Reproduced offline against
  `boot.py` @ `27616bec`: the declared extras yield exactly one `--fp8-gemm-backend flashinfer_cutlass`
  with no warning under both `DSV41_MXFP8_BACKEND=b12x` and `=off`, while the pre-change extras yield the
  warning above. **Acceptance is UNVERIFIED until a quartet boot** (`.30`–`.33` were fenced for workloads —
  superseded: the `#4` fence lifted 2026-10-23 and `.30` is a full cluster member, owner 2026-10-24):
  it must show `[moe_b12x_next] armed`, a `server_args=` dump naming `fp8_gemm_backend='flashinfer_cutlass'`,
  **no** `WARNING: DSV41_MXFP8_BACKEND=` line, and `launch.json`'s `args` carrying exactly one
  `--fp8-gemm-backend flashinfer_cutlass`.
- **Any recipe *default* can be overridden with `-o`** (e.g. `-o max_model_len=…`); the
  launcher's flags are applied after `RECIPE_ENV`, so the recipe/CLI wins for every value it
  takes a flag for. `boot.py` asserts `4096 ≤ CONTEXT_LENGTH ≤ 1048576`. A value that exists only
  as a `RECIPE_ENV` entry has **no** `-o` path (`env.` keys are clobbered) — that is why γ is a
  `defaults` key with a launcher flag.

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
- **Pool era: the `$PWD/.local/sparkrun-home` override fails for single-node boots too, not only
  quartet ds4 boots** — measured 2026-10-26, Sol-2B GGUF on `.35`: bare `-H` under the override dies
  in 10 s with `Error: launch_inference failed: prepared model is not visible through the workload
  mounts` (the anonymous cluster's model fan-out no longer lands the prepared snapshot in the node's
  workload mounts); the working form is the head's real `HOME` plus `--cluster WOPR -H <rail-IP>`,
  which skips fan-out and reads the shared pool cache. Keep the override for `recipe validate`.
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

## The vendored adapter set

**What it is.** The ds4/knapcio production arm serves DeepSeek-V4.1-Flash-1017 through a third-party
stack: SGLang's `dsv4.1` branch pinned at `f80c91a4b` (2026-09-16), staged into the image at build time
(`mad-science/DEEPSEEK.md:141-145`; `recipes/ds4/Dockerfile.knapcio-dsv41:20-23`), wrapped by an
adapter overlay from `knapcio/DeepSeek-V4.1-Flash-4x-DGX-Spark-TP4` (our pin `27616bec`, v2.4) that
bakes to `/opt/dsv41/adapter` on `PYTHONPATH` and installs itself through `sitecustomize.py`
(`recipes/ds4/mods/dsv41-sglang-overlay/README.md:21-25`). The adapters patch engine symbols at
import time — weight-loading, attention, collective and speculative-decode paths — and refuse to boot
on source drift (`mad-science/DEEPSEEK.md:838-839`). Our registry does not carry the adapter source:
the build `COPY`s it from a knapcio clone (`recipes/ds4/Dockerfile.knapcio-dsv41:16-23`), plus one
patch we do carry locally, and the launcher mod (`recipes/ds4/mods/dsv41-sglang-overlay`) gates the
result fail-closed and applies the production environment that switches individual adapter modules on
(`launcher.py:121-313`). "Vendored" means exactly that: upstream's code, our pinned build, verified
by an in-image test suite before a boot is allowed.

**Component by component, with a verdict for each:**

- **Engram reader** (`adapter/engram_backend.py` + the compiled `row_store.so`; env
  `DSV41_PACKED_DIR`, `DSV41_CACHE_*` — `launcher.py:124,132-138`). Reads the model's Engram tables as
  packed 264-byte per-rank shards from node-local NVMe (2 × 23.6 GiB per rank packed in 57–73 s on a
  first boot — `mad-science/DEEPSEEK.md:80,227`). The packed shard is an *optional acceleration* with
  an exact checkpoint fallback, and `row_store.cpp` fails closed on a range mismatch
  (`recipes/ds4/mods/dsv41-sglang-overlay/README.md:111-113`; `launcher.py:49-51`). **Verdict:
  performance convenience** — the arm boots, fits and serves correctly without it.
- **`replicated_split`** (`adapter/replicated_split.py`; `DSV41_REPLICATED_SPLIT=wqkv_a,engram.wkv`,
  `launcher.py:304`). Slices two per-layer replicated GEMMs — `wqkv_a` 1792×5120 and `engram.wkv`
  25600×6144, on all 42 layers per step — into rank-window GEMMs plus a compact RoCE column gather
  (`mad-science/DEEPSEEK.md:1529-1531`). Measured state on the shipped line: every rank logs
  `split ON, window GEMMs (no pad)` with zero `split OFF` and zero `slice failed`
  (`mad-science/DEEPSEEK.md:1612-1617`, receipt `~/benchmarks/tp4-pad-20261023/a1-control-node*.log`
  on the head). Upstream never isolated its same-image magnitude (`DEEPSEEK.md:1577`), so no t/s
  number is recorded for the split itself. **Verdict: performance** — it is upstream's production
  shape and we run it on, but the arm would serve without it (the fallback is the stock replicated
  GEMM plus a padded all-gather).
- **`tp3_pad`** (`adapter/tp3_pad.py`; `DSV41_TP_PAD`, adapter default on — `DEEPSEEK.md:1526-1528`).
  Pads tensors so the split probe can slice on TP degrees where the dimensions do not divide; when the
  slice fails it is the mechanism behind the fallback above. On the shipped TP=4 line the split
  succeeds and the boot logs `no pad` (`DEEPSEEK.md:1617`), so the padding path never engages. The
  2026-10-23 `DSV41_TP_PAD=0` A/B was closed **falsified and moot**: the treatment never booted (NCCL
  RDMA-registration wedge, `DEEPSEEK.md:1628-1634`) and the record's consequence is "do not ship the
  line" (`DEEPSEEK.md:1222,1625-1626`). Upstream's own production pin is `DSV41_TP_PAD: "0"`
  (`DEEPSEEK.md:1551`). **Verdict: obsolete on the TP=4-only vendored line** — a leftover of the
  upstream lineage's other topologies; it costs nothing while the split is on, and turning it off
  is one `RECIPE_ENV` line away. **Qualified 2026-10-26 (S0 evidence):** obsolete applies to our
  TP=4 vendored line only. On a stock tree the pad/selection mechanism is load-bearing for boot:
  the S0 control's stock main image rejected the checkpoint at its default MoE backend —
  `Mxfp4FlashinferCutlassMoEMethod requires hidden_size and intermediate_size_per_partition to be
  multiples of 128 (got hidden=5120, intermediate=576)` — which is precisely the divisibility case
  the vendored padding path absorbs (receipt
  `~/benchmarks/tp4-window4-20261026/s0-stock-tree-rank0-serve.log`).
- **DSpark speculative-decode adapters** (`verify_cap`, `block_verify`, `draft_main_proj_split`,
  `draft_head_fp8`, folded fence/sampling; `launcher.py:274,298-308`). Hold the shipped DSpark k=5
  configuration coherent: the confidence cap (`DSV41_VERIFY_CAP=conf:0.1`) builds a size-5 verify
  tensor that must match the checkpoint's draft block size 5, and a mismatched block size aborts all
  four ranks at decode-graph capture — measured when γ=3 was tried
  (`recipes/ds4/README.md:102-108`). **Verdict: load-bearing for the shipped configuration** — not
  for memory fit, but the shipped arm's spec-decode path aborts without the coherent pairing.
- **`fast_load`** (`adapter/fast_load.py`; `DSV41_FAST_LOAD=1`, `launcher.py:293` with the decision
  record at `:277-292`). Eager pinned weight loading: cuts engine start from 343 s to ~124 s, at the
  cost of a smaller, boot-variable KV pool (3.42M–4.36M tokens across the 2026-10-23/24 boots versus
  the stock loader's profiled 6.99M — `launcher.py:198-211`; `DEEPSEEK.md` §18.2). **Verdict:
  deliberate performance trade** (owner decision 2026-10-22), reversible with `DSV41_FAST_LOAD=0`.
- **`spec_sync_free`** (`adapter/spec_sync_free.py`; `DSV41_SPEC_SYNC_FREE=all`). Drops and merges
  the spec-decode sync broadcasts; audited bit-identical on greedy rows
  (`mad-science/CUSTOM_ALL_REDUCE_SM120_EXPERIMENTS.md:123-124`). **Verdict: performance**, small —
  the whole collective family is ~1.2 % of a step on this lane (`:126-127`).
- **Anthropic-protocol / Messages-thinking / prefill-bypass hooks** (nine lines added to
  `sitecustomize.py` between knapcio `58f2321` and our pin `27616bec` —
  `mad-science/DEEPSEEK.md:1554-1556`). Enable the Anthropic-protocol prefill-bypass behaviour for
  the Messages API. No throughput or latency measurement for it is recorded anywhere in the tracked
  docs. **Verdict: feature convenience, not load-bearing** — the arm would boot, fit and serve
  without it — but it is the component whose gate test fails behaviourally on candidate 3's tree
  (`test_prefill_bypass` 6F/2E — `mad-science/TODO.md` §Retry queue — window 4, Build-gate drift
  advisory), so it is what drives the re-port.
- **Build-time encoding anchor check** (`runtime/patch_encoding_dsv41.py`,
  `recipes/ds4/Dockerfile.knapcio-dsv41:78-80`). Fails the build if either pinned
  textual-placeholder anchor in SGLang's `encoding_dsv41.py` has drifted. The newer trees moved this
  file: the candidate builds had to re-derive anchor 1 because upstream dropped the
  `_validate_no_image_sp_tokens` docstring line the anchor matched
  (`recipes/ds4/zz-ds4-1017-main-tree-sglang.yaml:14-16`), and candidate 5's tree dropped
  `encoding_dsv41.py` entirely, forcing the re-pin to the #41603 merge commit `620c76f2`
  (window-4 evidence: build receipts `~/benchmarks/tp4-window4-20261026/build-c{3,5}.log`;
  `mad-science/TODO.md` §Retry queue — window 4, Build-gate drift advisory). **Verdict:
  load-bearing build gate** — it is the canary that says the adapter's assumptions about the tree
  no longer hold — but it is not a runtime component.
- **Chat-template staging** sits beside the adapter set but is not part of it: the 1017 refresh ships
  no `chat_template.jinja` on purpose, and both the overlay launcher (symlink farm,
  `launcher.py:106-111`) and the stock-tree mod (`recipes/ds4/mods/dsv41-chat-template-stage/run.sh:11-19`)
  stage the same file; without it a templateless checkpoint serves under SGLang's default template,
  which is the wrong output shape (`run.sh:13-15`). **Verdict: load-bearing correctness on any tree**
  — which is why the stock-tree S0 arm carries the staging mod even with no adapter at all.
- **Our one local patch, `boot.py.health-port.patch`** (`recipes/ds4/boot.py.health-port.patch`).
  Dynamic port discovery for the image HEALTHCHECK. A plain fresh-clone build silently drops it and
  yields a *different* image — measured 2026-10-14, image `dd9d1c3c…` / digest `ac9bc917…`, never to
  be pushed as `canary-roce` (`boot.py.health-port.patch:17-20`; `mad-science/DEEPSEEK.md:150-159`).
  **Verdict: load-bearing** for sparkrun's boot and health lifecycle.

**Would the arm run without the adapter set? No, on no stock main tree and at neither MoE backend — measured
2026-10-26.** The S0 control boot of `recipes/ds4/zz-ds4-1017-main-tree-sglang.yaml` (the stock
main tree `6563312` with the staging mod and no knapcio overlay —
`recipes/ds4/zz-ds4-1017-main-tree-sglang.yaml:5-6,28-29`;
`recipes/ds4/mods/dsv41-chat-template-stage/run.sh:12`; the knapcio `boot.py` is not in that image,
which is why the overlay launcher exits rc=2 there) FAILED at engine init on rank 0:
`ValueError: Mxfp4FlashinferCutlassMoEMethod requires hidden_size and
intermediate_size_per_partition to be multiples of 128 (got hidden=5120, intermediate=576)` →
child sigquit → process tree killed (receipt
`~/benchmarks/tp4-window4-20261026/s0-stock-tree-rank0-serve.log`, copied there by the recovery
holder). The checkpoint's per-partition intermediate (576 = 2304/4) violates the MXFP4-FlashInfer-Cutlass
÷128 rule — precisely the divisibility case the vendored padding path absorbs — so at the stock
default the pad/selection handling is load-bearing for boot, not a convenience. The
owner-authorized one-shot retry with `--moe-runner-backend triton` ALSO failed (2026-10-26): the
engine confirmed `moe_runner_backend=triton`, got past the ÷128 geometry check and began weight
load (108.83 GB available), then died 16 s in with an NVRM `NV_ERR_NO_MEMORY` GPU OOM — the un-fused
runner cannot materialize the fp4 experts inside the 128 GB unified GPU. So the stock main tree
(`6563312`) does NOT serve the 1017 on GB10 TP=4 at either in-arm MoE backend: cutlass rejects the
geometry, triton cannot fit the memory. The corrected conclusion is a memory-fit one as much as a
geometry one: the vendored fused/packed MoE path is load-bearing for MEMORY FIT on this checkpoint,
so the adapter set is not optional for boot. Both tracebacks: cutlass
`~/benchmarks/tp4-window4-20261026/s0-stock-tree-rank0-serve.log`; the triton retry's
`s0-retry-node{1..4}-serve.log` saved beside it, its OOM in spark-d325's kernel log and the
launch-side failure in `s0-retry-launch.log` (record: `mad-science/TODO.md:749-763`; queue verdict
e84ce8d, S0 DONE NEGATIVE; any shipped-image fallback is a control-lineage change reserved to the
owner).
Upstream knapcio (checked 2026-10-26, HEAD `aff52fa5`) carries no guard or pad for this
MoE-divisibility case on stock trees — its whole patch stack is pinned to the same `f80c91a4b`
dsv4.1 branch, where the vendored selection applies (see `mad-science/DEEPSEEK.md` §19).
What the adapter set buys beyond boot remains the upstream production configuration: the RoCEnante
transport (the lane's single largest measured lever, 1.70× at C1 —
`mad-science/DEEPSEEK.md:82-84`), packed-Engram boot speed, the split, fast load and the DSpark
line. What we still do not have is a same-window measurement of the shipped overlay line against
a stock-tree line — the survey was how we were about to get one.

**The gate.** The image build runs the adapter test suite as one `RUN` chain and fails the build on
any failure (`recipes/ds4/Dockerfile.knapcio-dsv41:85-110`): `test_anthropic_thinking`,
`test_prefill_bypass` (run with `DSV41_PREFILL_BYPASS_SOURCE_ROOT` pointed *into* the tree's own
`sglang/srt/managers` code and `DSV41_PREFILL_BYPASS_EXPECT=supported`),
`test_thinking_alias`, `test_max_new_tokens`, `test_loop_abort`, `test_replay_guard`,
`test_replicated_split`, `test_compact_gather`, `test_verify_cap` (with `VC_TEST_N=60000`), and
`test_spec_sync_free`. Why it exists: the adapters patch engine symbols and refuse to boot on source
drift (`mad-science/DEEPSEEK.md:838-839`), and the gate is the build-time expression of that refusal
— a build whose adapter no longer matches its tree may carry a silently-wrong adapter and produce
plausible-but-wrong numbers (`mad-science/TODO.md` §Retry queue — window 4, Build-gate drift
advisory). Honest
limit: the test sources are vendored from the knapcio build context, not carried in this repo
(`recipes/ds4/Dockerfile.knapcio-dsv41:16-23`), so the gate's negative controls are not enumerable
from tracked files — the tracked record asserts they exist and directs that any gate rewrite preserve
them (`mad-science/TODO.md` §Retry queue — window 4, Build-gate drift advisory). What the gate
prevents, concretely, is the neutered-gate shortcut the owner rejected (option (b) of the trimmed
round-1 question): neutering it on a mismatched tree would ship a boot whose adapter semantics
nobody verified.

**Why the re-port costs 16–24 h.** Four work items, itemized:

1. **Re-derive each adapter patch against upstream's rewritten code** — hours, the bulk of the
   estimate. The adapters sit on specific upstream files (`sglang/srt/managers` for the bypass,
   `encoding_dsv41.py` for the placeholders). Candidate 3's tree fails `test_prefill_bypass` 6F/2E
   behaviourally — our vendored patch no longer matches that tree's code
   (`mad-science/TODO.md` §Retry queue — window 4, Build-gate drift advisory; window-4 evidence
   `~/benchmarks/tp4-window4-20261026/build-c{3,5}.log` on the head) — and main @ `ad950cdd` dropped
   `encoding_dsv41.py` entirely (same advisory). Every module must be re-read against the
   new code, re-diffed, re-patched and made to probe successfully. **~8–12 h.**
2. **Rewrite the gate's behavioural expectations to the new semantics while preserving its negative
   controls** (`mad-science/TODO.md` §Retry queue — window 4, Build-gate drift advisory) — smaller but careful: each test's assertions must
   match what the new upstream code actually does, and the deliberately-broken-input cases must still
   go red. **~2–4 h.**
3. **Rebuild and boot-verify the shipped 1017 line on the new base** — a boot-gated check, not a unit
   test: image build is ~10 min per node including the in-image tests
   (`attic/ds4/AGENTS.md:992-993`), plus push, plus a quartet TTR measured at 545.9 s warm
   (`recipes/ds4/README.md:36`). **~2–4 h** including margin for a failed attempt.
4. **Re-measure that the shipped line still hits its bars** — C1/C10 ladder, house ≥ 36/37, needle
   3/3 (the shipped bars: `recipes/ds4/README.md`; `mad-science/DEEPSEEK.md` §17 carries the same
   acceptance shape and the boot-cost precedent) — one boot plus cells at ~45–60 min TTR. This is
   not bureaucracy: an adapter silently mismatched to its tree produces plausible-but-wrong
   numbers, which is exactly what the gate exists to prevent (`mad-science/TODO.md` §Retry queue —
   window 4, Build-gate drift advisory). **~2–4 h.**

Total ~16–24 h; the queue carries it as `ds4-adapter-report-gate`, estimate 20.0 h
(task `ds4-adapter-report-gate` in `mad-science/queue.json`). What would shorten it: merging the
adapter semantics upstream as PRs and keeping only a thin shim locally (round-2 option (b),
`mad-science/GUIDANCE.md` §5), or shrinking the patch surface the adapters touch. The survey's own
limits section already said it: "the real cost is the re-port, not the flag"
(`mad-science/DEEPSEEK.md:995-997`).

**Consequence for this window.** Arms 3 and 5 are blocked behind this re-port
(`mad-science/STATUS.md:8`; `mad-science/TODO.md` §Retry queue — window 4, Build-gate drift
advisory; queue task `ds4-adapter-report-gate`), while
the flag-level arms (S0, 1, 2, 6) are not build-gated and run; the b12x parity boot ran, measured
~half the shipped C1, and was retired to `attic/ds4/` by owner decision 2026-10-26
(`mad-science/TODO.md` §Retry queue — window 4). Under the owner's queueing formula the re-port's
weight is its 20 h estimate minus the 6 h of candidate work it blocks (arms 3 and 5 at 3.0 h each
— queue tasks `w4-survey-arm3-indexer-scoring` / `w4-survey-arm5-trtllm-mla`), i.e. 14 h — so it
sinks well below its raw cost in the queue, and the model-priority ruling (1017 is the primary
model — `mad-science/TODO.md` §Retry queue — window 4, Priority-models ruling) keeps it ahead of
non-1017 work regardless. Note the re-port also blocks every future newer-tree build, not just
these two arms (task `ds4-adapter-report-gate`), so its true blocked-set weight grows each time
the survey wants a newer base.

## deepseek-v4.1-flash-tensorfold-tp2-1m-sglang

| | |
|:--|:--|
| Recipe | `recipes/ds4/deepseek-v4.1-flash-tensorfold-tp2-1m-sglang.yaml` |
| Engine | TensorFold `deepseek_v41` ([bertholomus/TensorFold](https://github.com/bertholomus/TensorFold) @ `3825f62` — the v0.6 release commit, 2026-10-18; reports `tensorfold 0.6.6`) |
| Model | [`LibertAIDAI/DeepSeek-V4.1-Flash-1017-EXL3-2.9bpw`](https://huggingface.co/LibertAIDAI/DeepSeek-V4.1-Flash-1017-EXL3-2.9bpw) — the 2026-10-17 refresh's EXL3 2.9 bpw (~196 GiB), pinned `0be63c33…` (2026-10-19). The four commits past the previous `c178a012…` pin touch only `README.md` and add a `chat_template.jinja`: every safetensors blob is unchanged, so the weights are the same bytes |
| Engram | the 1017 tables (layers 1/14, ~189 GiB) in the node's `hub/dsv41-engram` dir, **outside** the checkpoint snapshot so a refresh cannot empty it; the recipe passes `--require-engram`, so a node without them fails the launch instead of serving degraded |
| Size / fit | 385 GB |
| Topology | TP=2 — two GB10 nodes, one rank per node |
| Context | 1,048,576 tokens served (the model's full trained window, which is also the KV pool) |
| Spec decode | DSpark k=5 (in-checkpoint draft blocks) |
| Image | `littlecedar/dgx-spark-dsv41@sha256:d6e4c10d…` (vendored, digest-pinned; built 2026-10-21 from `Dockerfile.tensorfold-dsv41` with `--build-arg TENSORFOLD_REF=3825f62` — the arg is mandatory, see Rebuild below) |
| Tags | `fast`, `large_context`, `single_user`, `vision` |
| Measured | **v0.6 (shipped since 2026-10-21):** c1 **64.5** / c4 51.2 / c8 **52.5** / c16 **53.2** t/s (n=9: 3 boots × 3 runs) and cold prefill **2,077** t/s @ 32k / **2,073** @ 131k — `~/benchmarks/ds4-v06-ab-20261021/REPORT.md`. The control (0.6.3, `fabbe861…`) on the same interleaved run: 64.7 / 46.1 / 41.5 / 42.3 t/s, prefill 1,667 / 1,486 — the treatment's worst boot beats the control's best at c8 and c16. Upstream reports 101 code / 62 prose / 142 structured, 4 streams 112. The older 5-run `ds4-1017` 66.4 / 47.8 / 44.8 / 48.4 cells were the 0.6.3 engine (`~/benchmarks/ds4-1017-ab-interleaved-20261018/`). |
| Boot-verified | 2026-10-21, v0.6 arm: six boots, `/v1/models` = the 1017 id and `tensorfold --version` = 0.6.6 on every treatment boot; launch 80.3–80.9 s after the one-time JIT (the first v0.6 start costs 264 s building three CUDA extensions). Earlier 0.6.3 ship: TTR 62 s, vision 3/3 (`~/benchmarks/ds4-1017-ship-20261017/`). **Re-verified on the `0be63c33…` pin 2026-10-22:** TTR **590 s** — a new pin keys a new per-tree rank cache, so the boot re-converts the weights (318 s) and rebuilds the three CUDA extensions — then `/v1/models` = the 1017 id at `max_model_len` 1,048,576, `loaded in 556.8s`, DSpark accepting 13/31 drafts (17×23 → 391, thinking **and** `enable_thinking:false` both answered), overlay symlinks resolving into the new snapshot (`~/benchmarks/ds4-expin-20261022/`) |

### Rebuild

`Dockerfile.tensorfold-dsv41` has **no default `TENSORFOLD_REF`**: the two shipped images come from
different commits, so a default would silently rebuild the wrong engine. Pass the ref the image you
want is supposed to carry:

```bash
# ds4 arm (`tensorfold-v06`, sha256:d6e4c10d…) — TensorFold 0.6.6, v0.6 release commit 2026-10-18
docker build -f Dockerfile.tensorfold-dsv41 \
  --build-arg TENSORFOLD_REF=3825f62022f25e3e5cf01fa5ea708d4a93b0a9e3 \
  -t littlecedar/dgx-spark-dsv41:tensorfold-v06 .

# cybersec arm (`tensorfold-tp2`, sha256:fabbe861…) — TensorFold 0.6.3
docker build -f Dockerfile.tensorfold-dsv41 \
  --build-arg TENSORFOLD_REF=d5d7bb389ddf4325c1edf4a15dd1c23727040ea1 \
  -t littlecedar/dgx-spark-dsv41:tensorfold-tp2 .
```

The build fails closed on a missing ref (`RUN test -n "${TENSORFOLD_REF}"`) and on a ref that is not
a real commit (the `git rev-parse HEAD` equality check after the checkout).

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
- **The checkpoint's own chat template is never served on this arm.** The `--vision` overlay skips any
  `chat_template.jinja` the snapshot ships (`launcher.py:263`) and writes the mod's copy as the one real
  file, so a template the pack itself starts shipping cannot take effect while `--vision` is on — and
  this recipe passes it. Proved 2026-10-22 on the `0be63c33…` pin, whose new commits add exactly such a
  file: the served template is `297be886…` (the mod's) and the snapshot's `2ed8bc33…` is absent from the
  54-entry overlay. Dropping `--vision` serves the checkpoint's own template, and gives up image input.
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

## Upgrade candidates (measured elsewhere, not queued)

A 2026-10-19 search of upstream SGLang / FlashInfer / DeepGEMM / DeepEP work, DeepSeek-V4.1 PRs, and
published GB10 numbers produced a ranked shortlist, now consolidated in
[`../../mad-science/DEEPSEEK.md`](../../mad-science/DEEPSEEK.md) §10 — mechanism, expected effect, the
exact flag or artifact, a dated primary source, and a pre-registered interleaved A/B per candidate.
None of it is measured on this lane, and none of it is a recipe change:

- **Measured and adopted 2026-10-21** — (4) the TensorFold v0.6 engine bump: c8 **+26.5 %**, c16
  **+25.7 %** (worst treatment boot beats the best control boot at both), cold prefill **+24.6 %**
  at 32k and **+39.5 %** at 131k, c1 flat, c4 +10.9 % with overlapping ranges; six interleaved
  boots — `~/benchmarks/ds4-v06-ab-20261021/REPORT.md`. The shipped pin now is the v0.6 image
  (`d6e4c10d…`, engine 0.6.6 at commit `3825f62`). (6) `reasoning_effort: high` instead of max:
  paired same-task A/B, **10.6 %** fewer reasoning tokens with house 37/37 on both arms and no
  pass→fail flip — but the bar is cleared by 0.6 points and one task (`hard-rev`, 128 → 43) carries
  most of it; treat it as "just clears", not a headline. (P0) the GPU clock-latch audit is closed
  negative (2026-10-19).
- **TP=4-only, upgrade candidates for `.30`–`.33`** (frozen by the 2026-10-18 owner policy) —
  `--min-free-slots-delay 1` (+21 % C8 decode on 4xGB10), prefix-cache truth via
  `--enable-cache-report` / `lpm`, candidate-only indexer scoring (upstream #43401), TRT-LLM sparse
  MLA (`--dsv4-attn-backend trtllm`, 2.26x kernel geomean on GB10), a newer SGLang tree on CUDA 13.3,
  encoder SWA bounded replay, DSpark compact verify (#42718), and a 1017 NVFP4 W4A4 checkpoint.
  DCP2 is blocked upstream (the DCP x DSpark allowlist is Kimi Linear only).
- **Checked and rejected** — the SM100-only low-latency chain, mHC split-K, the verify-cap sweep,
  L2 sub-gates, the FP4-indexer flag, locked clocks, 1,024-token chunks,
  `--num-continuous-decode-steps`, HiCache/offload and EP>1; reasons per row in the note.
  The EP=4 arm was re-tested 2026-10-22 with the decode and prefill CUDA graphs disabled and
  still hit the same guard at MoE prepare (`dsv41-moe-E96-N2304-k6-M5 failed to prepare …
  planned dynamic direct routing is unsupported for this launch shape`) — so the rejection is
  route-plan geometry, not graph capture. Trial log on the head:
  `~/benchmarks/knapcio-tp4-20261022/ep4-eager-serve.log`.

The shortlist's A/B rules are this lane's own (§12.16): alternate arms A/B/A/B, `--fresh` on every
bench call, assert `/v1/models` per boot, pre-register the target cell and falsifier, three boots per
arm for anything quoted, and hold the shipped pool/pin constant across arms.

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
