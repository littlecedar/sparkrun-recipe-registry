# Board — generated 2026-10-26 23:19 ET

## In flight

| where | owner | what |
|---|---|---|
| census | sparkrun-recipe-re-34025 | **23:14 ET 2026-10-26, all six nodes (read-only ssh + `docker ps` + `nvidia-smi`)**: 0 containers and 0 % GPU on `.30`–`.35`; no `.scratch/fleet-window.lock` exists; root avail 1369–2028 GB, BeeGFS pool ~11.9 TB avail |
| pool-prefetch host process | tp4-recovery | `.30` (head) runs `hf download Qwen/Qwen3.5-122B-A10B-FP8` (pid 694234) — the serial pool-prefill runner, no container; queue task `pool-prefetch-missing-bodies`, claimed 2026-10-25 23:53 UTC; ledger `~/benchmarks/cache-prefill-20261026/QUEUE.md` |

## Work queue

| job | node cost | holds | state |
|---|---|---|---|
| `arch-deepgemm-sm12x-paged-sparse` — DeepGEMM SM12x for the paged-sparse logits family (upstream watch) | watch | — | BLOCKED on upstream (TODO row 21); first in the next-window order |
| `w4-survey-arm3-indexer-scoring` — SGLang PR #43401 candidate-only indexer scoring | quartet | — | BLOCKED: arch gate (SM12x) |
| `w4-survey-arm5-trtllm-mla` — TRT-LLM sparse-MLA attention backend | quartet | — | BLOCKED: arch gate (SM12x) |
| `h2h-glm-flash-house-recipe` — GLM-5.3-Flash 4bpw TP=4 house battery @4096 thinking-on | quartet | — | queued |
| `glm-flash-concurrency-degradation-search` — GLM-5.3-Flash variants that do not degrade with concurrency | quartet | — | queued |
| `h2h-doc-refresh` — TP4-HEAD-TO-HEAD open-cells note per landed cell | single | — | queued |
| `tensorfold-metrics-bridge-generalization` — metrics bridge for both GLM TensorFold launchers + a vLLM-OMNI media equivalent | single | — | queued |
| `pool-prefetch-missing-bodies` — pool hub dedup-stub bodies, serial hf-download runner | single | tp4-recovery | RUNNING |
| `h2h-beam-house-and-bfcl-category` — Beam-1.0 NVFP4 house @4096 + BFCL category summary | quartet | — | queued |
| `h3-quartet-retry` — MiniMax-H3 four-rank video probe (two unprobed axes) | quartet | — | queued, idle-only |
| `h2h-second-boot-ladder` — controlled second-boot ladder per arm (sigma column) | quartet | — | queued |

## Landed this session

| time ET | commit | one clause |
|---|---|---|
| ~20:05 ET | `7be1a13` | aff52fa5 production block adopted in the dsv41-sglang-overlay launcher — `DSV41_CERT_HEAD=1` + M list, `DSV41_FAST_LOAD_EP_SIZE/N_EXPERTS`, `WATCHDOG_TIMEOUT=1800`, `--sleep-on-idle`, `--enable-deepseek-v4-fp4-indexer` as AB_ENV defaults (each disablable); `DSV41_PREFILL_BYPASS` + `MIN_FREE_SLOTS_DELAY` stay arm-only; ds4 README protocol note, arm commands, deviations table; DEEPSEEK §18 v2.4-era claims annotated; gate 1007 OK |
| ~20:13 ET | `82e6932` | Board refresh (session boundary) + `SESSION-RECORD` entry for the **BeeGFS outage**: `beegfs-meta`/`beegfs-storage` on `.30` failed 19:28:50 ET with "Couldn't find any usable NIC"; services restarted, dead client sessions remounted on head and `.30`; two launch attempts died on the token read before the fix |
| ~21:2x ET | `c264134` | Corrections on top of `a0c7ec3`: cross-arm deltas flagged as boot-order-confounded (TTR 190.6 → 235.9 → 435.8 s monotonic; Arm B's own prose runs declined 85.66 → 84.1 → 82.33 within its boot) — only the within-boot comparisons against upstream are claimed; the address-hygiene guard failure that `a0c7ec3` slipped past (an endpoint literal in this board's earlier row) is fixed |
| ~21:14 ET | `cedcf4a` | review fixes: disablable guard now asserts on flag names (the env-key form was vacuous) with presence checked only for enabled defaults; both README parity arm commands carry `--cluster WOPR` (bare `-H` anonymous-cluster fan-out trap); sparkDash accounting stated as ratio-inferred, not code-read; Arm A's decode-window cell labeled derived; speedbench identity verified (`0.3.0`, prompt set `speedbench-v1`, 73 prompts); the last plan cell measured — registry ladder on the shipped line C1 70.41 ± 10.66 / C10 160.88 ± 17.48 vs adoption 64.08/152.24, inside the 7–25 % inter-boot noise floor: continuity, no claim |
| ~21:46 ET | `5e99497` | Root README refreshed to current numbers: ds4 knapcio row now carries the shipped line's 2026-10-26 evening ladder (C1 70.41 ± 10.66 / C10 160.88 ± 17.48, adoption 64.08/152.24 beside it, 7–25 % noise floor stated) + upstream-parity note (speedbench all-73 86.82 vs 87.5, prose 64.50 vs 64.7, sparkDash decode window 90.77 vs 91.3); superseded v2.3/v2.4 footnotes deleted; GLM 3bpw row superseded by window-3 ladder (28.83 C1, aggregates 37.4/76.3/145.8, house 37/37 — receipt JSON names `bertholomus/GLM-5.3-EXL3-3.0bpw`); CI "Issues disabled" corrected (has_issues verified true); ds4 lane pin-paragraph broken sentence repaired |
| ~21:48 ET | `82dfb06` | ds4 index-note attribution fix: house 37/37 + needles 10/10 credited to Arms A and B (the committed-default arm's quality cells are `—`), against 36/37 on the adoption boot — no quality claim rests on the new defaults alone |
| 23:09 ET | `1a00e94` | `mad-science/METHODOLOGY.md` + README "Mad Science" sub-bullet — how README cell numbers are derived; address-hygiene suite 7 tests OK |
