# TP=4 head-to-head, 2025-class frontier arms — receipts-only comparison

tp4-single, 2026-10-26, window 4 (owner round-5 §1(b): **existing receipts only** — no new boots; one
row per arm per cell with receipt pointers). Arms: the ds4 shipped line (DeepSeek-V4.1-Flash-1017,
knapcio SGLang TP=4), both GLM-5.3 TensorFold EXL3 TP=4 lines, and the Beam-1.0-501B NVFP4 TP=4 probe.
Every number below is quoted from a tracked doc or receipt listed in the pointer column; nothing here
is newly measured. Decode rows are per-request t/s unless marked aggregate; house/needle/tools cells
carry the instrument and its config in the pointer.

## Contents

- [Ladder cells (decode t/s)](#ladder-cells-decode-ts)
- [Second boots and first clients (2026-11-08, campaign h2h-20261107)](#second-boots-and-first-clients-2026-11-08-campaign-h2h-20261107)
- [Second-boot deltas (receipts re-read 2026-11-09)](#second-boot-deltas-receipts-re-read-2026-11-09)
- [Quality / capability cells](#quality--capability-cells)
- [Reading (grounded in the rows above, no new claims)](#reading-grounded-in-the-rows-above-no-new-claims)
- [Failure class: SM121 marlin fit negative and earlyoom (2026-11-09)](#failure-class-sm121-marlin-fit-negative-and-earlyoom-2026-11-09)
- [Provenance index](#provenance-index)

## Ladder cells (decode t/s)

| arm | C1 | C2 | C5 | C10 | receipts |
|---|---|---|---|---|---|
| DSv4.1-Flash-1017 knapcio SGLang TP=4 (shipped) | **69.28** | **86.40** | **108.78** | **116.27** | `~/benchmarks/tp4-20261018/` (same-boot ladder; house/needle/tools same serve); `recipes/ds4/README.md` |
| DSv4.1-Flash-1017 TensorFold TP=2 (comparison) | 68.6 | 48.1 | 44.6 | 42.1 | `~/benchmarks/ds4-tp2-ladder-20261018/`; SESSION-RECORD.md |
| GLM-5.3-Flash EXL3 4bpw TF TP=4 (shipped) | 83.03 ± 17.74 | 102.36 ± 24.01 | 79.49 ± 11.34 | 73.37 ± 8.44 | `~/benchmarks/tp4-20261018/` (`glm-ladder.{yaml,json,csv}`); `recipes/glm/README.md` §Boot receipt (trial C1 98.4 does NOT reproduce: 76.0 ± 9.3 ex-warm-up) |
| GLM-5.3 EXL3 3bpw TF TP=4 (753B) | 28.83 ± 1.37 | 28.94 ± 0.99 (agg 37.4) | 26.71 ± 5.44 (agg 76.3) | 28.21 ± 3.49 (agg 145.8) | window 3, task `sparkrun_7d9a3a61b33a29e4_e1ba2bd6f9d9`: `~/benchmarks/tp4-window3-20261024/glm-perf-ladder.{yaml,json,csv}`; `recipes/glm/README.md` |
| Beam-1.0-501B NVFP4 vLLM TP=4, no drafter | 26.20 | 40.66 | 63.96 | 69.80 | `~/benchmarks/tp4-window4-20261026/beam-b1-ladder.csv`; queue `w4-beam-cells-remainder` (d) |
| Beam-1.0-501B NVFP4 TP=4 + DFlash2 | 31.57 | 40.72 | 58.86 | 74.14 | `…/beam-b2-ladder.{csv,yaml}`; 7 spec tokens, FlashInfer draft attention, FULL CUDA graphs (`beam-b2-attempt8-node1-serve.log`) |

Shape notes, all receipt-backed: the ds4 knapcio arm is the only one whose **aggregate decode rises
monotonically with concurrency** (69→116; the C5/C10 1017 peaks predate the per-request-identity
finding recorded in `attic/ds4/AGENTS.md` — the bar's aggregate column reads 12.00 with the
per-request identity broken at C≥5, so read the 1017 C5/C10 as aggregate-shape, not per-request);
GLM-Flash peaks at C2 and falls (DFlash2 verify-window shape); GLM-753B holds a flat 27–29 t/s
per-request from C1 through C10 (MTP-3 sustains under load) while aggregate scales ~5.1× at C10;
Beam's ladder rises with concurrency in both arms and DFlash2 buys +20 % at C1 (deltas within noise
elsewhere, per-run stds 6–16 t/s).

## Second boots and first clients (2026-11-08, campaign `h2h-20261107`)

One controlled second boot per arm, measured on the live campaign root at
`head:/home/red/benchmarks/h2h-20261107/`. Cells are `ladder.json` `tg_throughput` (mean ± the
receipt's own sd over the run's five samples; the exporter writes population sd, so sample sd is
×1.119 of the printed value) and are **not** interchangeable with the 2026-10-18/26 rows above —
different boot, same recipe. The campaign's `house.*` artefact is the standard-suite
(`benchmarking/standard-suite.yaml`, framework `tool-eval-bench`) run, so its score is the table's
"tools leg" number, not the 37/37 quality battery; the battery ran only as the first client below.

| arm | C1 | C2 | C5 | C10 | standard suite (TEB) | receipts |
|---|---|---|---|---|---|---|
| DSv4.1-Flash-1017 knapcio SGLang TP=4, second boot | 51.11 ± 16.24 | 91.79 ± 3.92 | 128.88 ± 4.59 | 159.88 ± 10.14 | **93** | `~/benchmarks/h2h-20261107/deepseek-v4.1-flash-knapcio-tp4-1m-sglang/{ladder.json,house.json}`; campaign receipt `receipts/deepseek-v4.1-flash-knapcio-tp4-1m-sglang.json` |
| GLM-5.3-Flash EXL3 4bpw TF TP=4, boot2 | 105.90 ± 5.68 | 120.46 ± 28.43 | 96.80 ± 1.92 | 86.87 ± 1.16 | **100** | `~/benchmarks/h2h-20261107/glm-5.3-flash-exl3-tp4-1m-tensorfold-sglang-boot2/{ladder.json,house.json}`; `receipts/glm-5.3-flash-exl3-tp4-1m-tensorfold-sglang-boot2.json` |
| GLM-5.3-Flash, first client (same arm, other boot) | — (client cell, not a ladder) | — | — | — | house battery **37/37** (easy 19/19, hard 18/18) @4096 thinking-on; image `sha256:7f8f1b38…` | `…/glm-5.3-flash-exl3-tp4-1m-tensorfold-sglang/client/{client.json,house.json}` |
| Beam-1.0-501B NVFP4 vLLM TP=4, no drafter, boot2 | 33.09 ± 2.50 | 44.91 ± 3.50 | 59.71 ± 10.50 | 69.86 ± 7.41 | open — the same boot's standard-suite artefact scores 0/"Poor", which is not a quality verdict | `~/benchmarks/h2h-20261107/zz-beam-1.0-501b-a23b-nvfp4-tp4-vllm-boot2/{ladder.json,house.json}` |
| GLM-5.3 EXL3 3bpw TP=4 (753B), boot2 (attempt 6) | 30.27 ± 1.88 | 28.70 ± 1.01 (agg 37.8) | 29.61 ± 1.24 (agg 79.8) | 29.32 ± 3.62 (agg 151.6) | — (ladder only) | `~/benchmarks/h2h-20261107/glm-5.3-exl3-3bpw-tp4-1m-tensorfold-sglang/{ladder.json,ladder.csv}`; the rc=4 first-attempt receipt is retained in `receipts/glm-5.3-exl3-3bpw-tp4-1m-tensorfold-sglang.json` |

Boot-to-boot spread is the finding these rows carry: ds4's C1 is 51.11 against the first boot's
69.28, GLM-Flash's 105.90 against 83.03, Beam's 33.09 against 26.20 — 25-30 % at C1 in both
directions, so a single-boot C1 is a boot's number, not the arm's. Signatures survive: ds4 still
rises monotonically to C10, GLM-Flash still peaks at C2 and falls, Beam still rises with
concurrency.

### Second-boot deltas (receipts re-read 2026-11-09)

Each cell is `first ± sd → second ± sd, Δ on the mean`. The sd is the receipt's own
(`t_s_std` / `tg_throughput.std`, population as written; sample sd = ×1.119). The table above
prints sample sd where it prints ± for the GLM arms (e.g. C2 first is ±24.01 there against the
receipt's ±21.48 here); the means are identical. The ds4 pair is
deliberately `~/benchmarks/tp4-20261018/knapcio-ladder-suiteboot.csv` → the h2h ladder, **not**
its sibling `knapcio-ladder.csv` (that file carries 69.65 / 89.89 / 113.44 / 115.36 and is a
different boot). The 753B arm keeps the doc's per-request convention with aggregate in
parentheses, so neither series is read as the other.

| arm | C1 | C2 | C5 | C10 | shape on the second boot | receipts |
|---|---|---|---|---|---|---|
| ds4-1017 knapcio | 69.28 ± 4.70 → 51.11 ± 16.24, −26.2 % | 86.40 ± 3.21 → 91.79 ± 3.92, +6.2 % | 108.78 ± 12.69 → 128.88 ± 4.59, +18.5 % | 116.27 ± 5.56 → 159.88 ± 10.14, +37.5 % | rises monotonically to C10 in both boots | `~/benchmarks/tp4-20261018/knapcio-ladder-suiteboot.csv` → `~/benchmarks/h2h-20261107/deepseek-v4.1-flash-knapcio-tp4-1m-sglang/ladder.json` |
| glm-flash | 83.03 ± 15.87 → 105.90 ± 5.68, +27.5 % | 102.36 ± 21.48 → 120.46 ± 28.43, +17.7 % | 79.48 ± 10.14 → 96.80 ± 1.92, +21.8 % | 73.37 ± 7.55 → 86.87 ± 1.16, +18.4 % | still peaks at C2 and falls (C2 > C5 > C10) | `~/benchmarks/tp4-20261018/glm-ladder.csv` → `~/benchmarks/h2h-20261107/glm-5.3-flash-exl3-tp4-1m-tensorfold-sglang-boot2/ladder.json` |
| glm-753b (per-request; agg in parens) | 28.83 ± 1.37 → 30.27 ± 1.88, +5.0 % (agg 28.8 → 30.3) | 28.94 ± 0.99 → 28.70 ± 1.01, −0.8 % (agg 37.4 → 37.8) | 26.71 ± 5.44 → 29.61 ± 1.24, +10.9 % (agg 76.3 → 79.8) | 28.21 ± 3.49 → 29.32 ± 3.62, +3.9 % (agg 145.8 → 151.6) | flat 27–30 t/s per-request C1→C10 in both; aggregate scales ~5× | `~/benchmarks/tp4-window3-20261024/glm-perf-ladder.csv` → `~/benchmarks/h2h-20261107/glm-5.3-exl3-3bpw-tp4-1m-tensorfold-sglang/ladder.json` |
| beam-b1 | 26.20 ± 0.60 → 33.09 ± 2.50, +26.3 % | 40.66 ± 0.91 → 44.91 ± 3.50, +10.5 % | 63.96 ± 1.42 → 59.71 ± 10.50, −6.7 % | 69.80 ± 1.85 → 69.86 ± 7.41, +0.1 % | rises with concurrency in both (the second boot's C5 dip sits inside its ±) | `~/benchmarks/tp4-window4-20261026/beam-b1-ladder.csv` → `~/benchmarks/h2h-20261107/zz-beam-1.0-501b-a23b-nvfp4-tp4-vllm-boot2/ladder.json` |

**What this is not.** Each ± is a within-boot sd over five samples, and each delta is one
observed pair. Together they are *not* a boot-to-boot variance estimate: a sigma column on the
table above would need a third boot per arm on the same plan, so none is printed. The observed
C1 shifts (−26.2 % ds4, +27.5 % glm-flash, +5.0 % 753B, +26.3 % beam) are pair deltas, not
distributions. **Era boundary:** the 2026-11-09 metrics boot
(`sparkrun_b020d2dd178343a5_b632751318c7`) was **instrumented** (`--enable-metrics`), so its
throughput must not enter this table (owner ruling `#68`); the two GLM-Flash ladder numbers
above predate that instrument.

## Quality / capability cells

| arm | house battery | needle | tools leg | receipts |
|---|---|---|---|---|
| DSv4.1-Flash-1017 knapcio TP=4 | **36/37** @4096 (easy 19/19, hard 17/18; miss `hard-rev`) | **3/3** @ 32,768 / 131,072 / 983,040 (top rung 981,950 prompt tokens) | **TEB 93** on the 2026-11-08 second boot (standard-suite); the earlier boot scored 90 (13 pass, 1 partial, 1 fail `TC-03 wrong_args`) | `~/benchmarks/tp4-20261018/` (`REPO…` full-suite receipt, SESSION-RECORD.md §2026-10-18) |
| GLM-5.3-Flash EXL3 4bpw TP=4 | **37/37 through the recipe path** — 2026-11-08 first client on the live boot (easy 19/19, hard 18/18, @4096 thinking-on, image `sha256:7f8f1b38…`); the 2026-10-13 trial's 37/37 predated it | **10/10 PASS** @512 at 32,768 (3 min) and 131,072 (8 min); 983,040 **capped-by-precedent** — window 4 through the recipe path (`~/benchmarks/tp4-window4-20261026/glm-needle/`) | **TEB 100 — measured 2026-11-08 on boot2 (standard-suite)**; supersedes the withdrawn take below ( — the "14/15" pass I first recorded ran against the LINGERING 3bpw serve (`/v1/models` answered `GLM-5.3-EXL3-3.0bpw`), not the flash arm: the flash arm's checkpoint at the shipped pin `078455ff` is a **stub fleet-wide** (config.json only, 6,098 B; the launcher fails with `startup memory estimate needs the checkpoint tensor headers`). The Hub's pin is 175.7 GB across 95 files | needle: window 4 on the refetched body; the withdrawn tools leg re-runs only after that 175.7 GB re-fetch verified into a fresh boot. The contaminated "14/15" artifacts (14/15 csv + 100/100-marked report) stay as negative evidence under `.scratch/tp4-window4/glm-teb/` |
| GLM-5.3 EXL3 3bpw TP=4 (753B) | **37/37** @4096 thinking-on through the recipe path (easy 19/19, hard 18/18, 124.7 s) | **10/10 PASS** @512 at 32,768 (19 min) and 131,072 (62 min); 983,040 **wrapper-capped ×2** (7200 s and 14400 s, ~4 h quartet per attempt, serve warm throughout — unmeasurable in-window, not an arm failure) — window 4 leg-1 rerun after the 02:11Z foreign-stop kill (`~/benchmarks/tp4-window4-20261026/glm-needle/`) | **TEB 100 — 15/15 pass, 0 partial, 0 fail** — window 4 (`benchmark_glm-5.3-exl3-3bpw…tp4.{json,csv}`, `.scratch/tp4-window4/glm-teb/`) | house: window 3 `~/benchmarks/tp4-window3-20261024/suite-glm/`; needle+tools: window 4 `~/benchmarks/tp4-window4-20261026/` |
| Beam-1.0-501B NVFP4 TP=4 | open — the 2026-11-08 second boot ran the standard suite but its artefact scores 0/"Poor", a harness artefact rather than a quality verdict; the pre-registered (b) cell became the needle rerun (window-3 smoke 17×23=391 correct) | **20/20 PASS** @512 with `--needle-max-tokens 512` at 32,768 and 131,072, all depths (the window-3 0/3 shape was budget truncation — finish=length, the documented false-capability class) | **BFCL tools leg ran direct** (eval-suite wrapper stalls 52 min — instrument finding): per-case PASS/FAIL lines give **475 PASS / 40 FAIL** (`beam-b1-bfcl2.log`) and **182 PASS / 25 FAIL** (`beam-b1-bfcl3.log`) = **657/722 (91.0 %)** across the two populated logs; the harness's own category summary is absent from the logs, so the per-category split is open | `~/benchmarks/tp4-window4-20261026/beam-b1-needle-*-512.json`, `beam-b1-bfcl{2,3}.log`; queue `w4-beam-cells-remainder` notes |

## Reading (grounded in the rows above, no new claims)

- **Throughput at C1**: GLM-Flash 83.0 > ds4-1017 69.3 > GLM-753B 28.8 ≈ Beam 26.2 (31.6 with DFlash2).
  The 1017 arm is the only ladder whose aggregate grows to 116 at C10 — it is the concurrency arm;
  GLM-Flash is the single-stream arm; GLM-753B is the capability arm that does not slow down under
  load; Beam is a probe with one quarter of the active parameters the others carry (23.4B active).
- **Capability**: ds4-1017 is the only arm with the full triple **on one boot** (house + needle +
  tools through one recipe path, 2026-10-18). Window 4 closed the GLM gaps through the recipe path
  across boots: both GLM arms now carry needle 32,768/131,072 **10/10 PASS** each (983,040
  wrapper-capped on both — unmeasurable in-window at the 3bpw arm's prefill rate, capped-by-precedent
  on the flash arm; a full 983k number is only worth an ~8-h dedicated window if the owner asks),
  GLM-753B adds tools **TEB 100 (15/15)** and house **37/37**; GLM-Flash now has both through the
  recipe path as well — the 2026-11-08 first client scored house **37/37** and that arm's boot2 wrote
  a standard-suite **TEB 100**, superseding the withdrawn contaminated take; Beam's needle 20/20@512 clears its rung set with the truncation trap handled.
- **Open cells this table must not paper over**: the Beam house battery and BFCL-category summary
  (the boot's standard-suite artefact is 0/"Poor" and proves nothing); the GLM-753B ladder, house and
  tools cells (first boot rejected by the harness readiness ceiling, re-boot pending
  `ARM_READY_TIMEOUT`); the survey arms' cells (arm 3 indexer scoring and arm 5 TRT-LLM sparse MLA,
  receipts not yet landed); and one second boot is not a sigma — the 2026-11-08 rows are single
  second boots per arm, so the boot-to-boot spreads they show are *observed differences*, not
  estimates of variance. The 983,040 needle rung stays **open on every arm but ds4-1017**: the GLM
  arms' 983k rungs are wrapper-capped unmeasurable-in-window (two caps on the 3bpw arm at
  7200/14400 s — the rung needs an ~8-h dedicated quartet window at that arm's prefill rate; the
  flash arm took the cap-by-precedent), so a 983k capability comparison is not on the table without
  the owner ordering that window.

## Failure class: SM121 marlin fit negative and earlyoom (2026-11-09)

**The sm121 marlin path cannot fit TP=4 on the plan it was booted with.** Two instrumented boots
on `.31/.32/.33/.35` — the first with the fast loader (`MAX_TOTAL_TOKENS=0`), the second with
`-o env.DSV41_FAST_LOAD=0` and the stock pin `6,849,792` proven in the launcher line — both drove
host `MemFree` down in 3–4 s: **106.8 GiB** (115,808,796 → 3,800,692 kB) on `.31` in the first,
**110.3 GiB** (117,522,996 → 1,889,340 kB) in the second, while the rank container's cgroup never
exceeded **5.87 GB** (`cg_current` peak 5,870,653,440 B). The memory was therefore held outside
container accounting (driver/UMA), and the kernel logged the driver's own
`NVRM: … NV_ERR_NO_MEMORY (0x51) … _memdescAllocInternal` at the crossing. Against a declared
`0.78 × 124,608 MiB = 101.9 GB` static budget and the shipped knapcio arm's measured 19.49 GB
headroom, a ~75 GB padded-copies repack transient cannot fit; the stock loader did not change
it. The same 552B checkpoint boots healthy on the shipped knapcio TP4 arm with shared-expert K
padding armed (`RowParallelLinear padded (5120, 576) -> (5120, 640)`), so the delta is the sm121
line's backend/padding, not the model. Verdict and CSVs:
`head:~/benchmarks/sm121-oom-20261109/VERDICT.md` (boots `boot-2/`, `boot-3/`).

**earlyoom with `--prefer python3` turned two would-be host kills into one dead serve.** On all
four ranks, at the 4 % available line, `earlyoom -m 4` sent SIGTERM to `sglang::schedul`
(badness 976–978, VmRSS ~2.3 GiB; `.35` escalated to SIGKILL after 0.9 s in the second boot); the
process exited in 1.4–2.8 s and the memory was released. `journalctl -k` recorded `oom-kill`
**0 times** on every rank, and ssh, the user manager, the pool server units
(`OOMScoreAdjust=-1000`) and `/mnt/beegfs` (23T/9.0T before and after) survived. That is the
`#67`/`#72` host policy working as designed on a ~110 GiB dive — and the reason this failure
class now costs one serve per occurrence instead of a node.

## Provenance index

- `recipes/ds4/README.md` (shipped bars + strict-validate table), `attic/ds4/AGENTS.md`
  (C≥5 aggregate-identity finding), SESSION-RECORD.md §2026-10-18 (ds4 TP=4 + TP=2 ladders).
- `recipes/glm/README.md` §Boot receipt (Flash) + window-3 paragraphs (3bpw ladder + house);
  `attic/glm/AGENTS.md` (runbook lines).
- `mad-science/TODO.md` §"Retry queue — window 4" + queue `w4-beam-cells-remainder`
  (Beam cells (b)-(d) receipts), `recipes/explore/zz-beam-1.0-501b-a23b-nvfp4-tp4-vllm.yaml`
  (the probe arm).
- Receipts roots: `~/benchmarks/tp4-20261018/`, `~/benchmarks/tp4-window3-20261024/`,
  `~/benchmarks/tp4-window4-20261026/`, `~/benchmarks/glm53-flash-exl3-tp4-trial-20261013/`,
  `~/benchmarks/ds4-tp2-ladder-20261018/`.