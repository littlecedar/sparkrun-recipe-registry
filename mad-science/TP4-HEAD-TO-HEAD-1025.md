# TP=4 head-to-head, 2025-class frontier arms — receipts-only comparison

tp4-single, 2026-10-26, window 4 (owner round-5 §1(b): **existing receipts only** — no new boots; one
row per arm per cell with receipt pointers). Arms: the ds4 shipped line (DeepSeek-V4.1-Flash-1017,
knapcio SGLang TP=4), both GLM-5.3 TensorFold EXL3 TP=4 lines, and the Beam-1.0-501B NVFP4 TP=4 probe.
Every number below is quoted from a tracked doc or receipt listed in the pointer column; nothing here
is newly measured. Decode rows are per-request t/s unless marked aggregate; house/needle/tools cells
carry the instrument and its config in the pointer.

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

## Quality / capability cells

| arm | house battery | needle | tools leg | receipts |
|---|---|---|---|---|
| DSv4.1-Flash-1017 knapcio TP=4 | **36/37** @4096 (easy 19/19, hard 17/18; miss `hard-rev`) | **3/3** @ 32,768 / 131,072 / 983,040 (top rung 981,950 prompt tokens) | **TEB 90** (tool-eval-bench, 15 scenarios: 13 pass, 1 partial, 1 fail `TC-03 wrong_args`) | `~/benchmarks/tp4-20261018/` (`REPO…` full-suite receipt, SESSION-RECORD.md §2026-10-18) |
| GLM-5.3-Flash EXL3 4bpw TP=4 | **37/37** — the 2026-10-13 trial's, not through the recipe path (still unproven through it) | not measured | **TEB 100** (15 scenarios: 14 pass, 1 fail `TC-15 connection_error`) — window 4 through the recipe path (`~/benchmarks/tp4-window4-20261026/benchmark_glm-5.3-flash-exl3…tp4.{json,csv}`; boot→ready ~54 min — slow load, not a hang) |
| GLM-5.3 EXL3 3bpw TP=4 (753B) | **37/37** @4096 thinking-on through the recipe path (easy 19/19, hard 18/18, 124.7 s) | not measured | **TEB 100 — 15/15 pass, 0 partial, 0 fail** — window 4 (`benchmark_glm-5.3-exl3-3bpw…tp4.{json,csv}`) | house: window 3 `~/benchmarks/tp4-window3-20261024/suite-glm/`; tools: window 4 `~/benchmarks/tp4-window4-20261026/` |
| Beam-1.0-501B NVFP4 TP=4 | not measured through the recipe path (the pre-registered (b) cell became the needle rerun; window-3 boot-gate smoke 17×23=391 correct) | **20/20 PASS** @512 with `--needle-max-tokens 512` at 32,768 and 131,072, all depths (the window-3 0/3 shape was budget truncation — finish=length, the documented false-capability class) | **BFCL tools leg ran direct** (eval-suite wrapper stalls 52 min — instrument finding): per-case PASS/FAIL lines give **475 PASS / 40 FAIL** (`beam-b1-bfcl2.log`) and **182 PASS / 25 FAIL** (`beam-b1-bfcl3.log`) = **657/722 (91.0 %)** across the two populated logs; the harness's own category summary is absent from the logs, so the per-category split is open | `~/benchmarks/tp4-window4-20261026/beam-b1-needle-*-512.json`, `beam-b1-bfcl{2,3}.log`; queue `w4-beam-cells-remainder` notes |

## Reading (grounded in the rows above, no new claims)

- **Throughput at C1**: GLM-Flash 83.0 > ds4-1017 69.3 > GLM-753B 28.8 ≈ Beam 26.2 (31.6 with DFlash2).
  The 1017 arm is the only ladder whose aggregate grows to 116 at C10 — it is the concurrency arm;
  GLM-Flash is the single-stream arm; GLM-753B is the capability arm that does not slow down under
  load; Beam is a probe with one quarter of the active parameters the others carry (23.4B active).
- **Capability**: ds4-1017 is the only arm with the full triple (house + needle + tools through one
  recipe path). Window 4 closed the GLM tools leg through the recipe path for both arms — GLM-753B
  TEB 100 (15/15, the cleanest tools line on the table), GLM-Flash 14/15 (`TC-15 connection_error`,
  cause unprobed) — and GLM-753B already matched the house score; GLM-Flash's 37/37 is still the
  trial's; Beam's needle 20/20@512 clears its rung set with the truncation trap handled.
- **Open cells this table must not paper over**: no GLM Flash house through the recipe path, no
  second-boot ladder for any arm, no Beam house/BFCL-category summary, and the 131k/983k needle rungs
  exist for ds4-1017 only (its 131k/983k prefill legs were wrapper-clipped, not capability-missed —
  `rc=124` wrapper-cap class, rerun needs `timeout 7200`).

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