# Board — generated 2026-10-26 21:20 ET

## In flight

| where | owner | what |
|---|---|---|
| census | DSV41F1017-Parity | **21:1x ET 2026-10-26, all six nodes (read-only ssh + `docker ps` + `nvidia-smi`)**: ALL SIX EMPTY — 0 containers, 0 % GPU on `.30`–`.35`; every arm of the parity A/B/C was stopped by literal task id and its serve log harvested first. Fleet-window lock released at close |
| nothing live | — | the ds4-1017 knapcio-parity window is **closed**: three arms (strict parity / old line / as-committed defaults) booted, measured, stopped; verdicts landed in `recipes/ds4/README.md` §"Measured: aff52fa5 parity A/B/C" |

| job | node cost | holds | state |
|---|---|---|---|
| `arch-deepgemm-sm12x-paged-sparse` — DeepGEMM SM12x for the paged-sparse logits family (upstream watch) | watch | queue | BLOCKED on upstream (row 21) — first in the next-window order |
| `w4-survey-arm3-indexer-scoring` | quartet | — | ARCH-GATED behind SM12x (row 21) |
| `w4-survey-arm5-trtllm-mla` | quartet | — | ARCH-GATED behind SM12x (row 21) |
| `h3-quartet-retry` | quartet | — | queued, idle-only |
| `glm-flash-concurrency-degradation-search` | quartet | — | DEFERRED (owner, row 19) |
| Beam staging remainder | spare | — | parked (owner, rows 19/22) |
| queue mirror | — | board-keeper | mirrors `mad-science/queue.json` (`tools/task-queue.py`); **Running**: none; open/blocked per `TODO.md` row 22 next-window order |

## Landed this session

| time ET | commit | one clause |
|---|---|---|
| ~20:05 ET | `7be1a13` | aff52fa5 production block adopted in the dsv41-sglang-overlay launcher — `DSV41_CERT_HEAD=1` + M list, `DSV41_FAST_LOAD_EP_SIZE/N_EXPERTS`, `WATCHDOG_TIMEOUT=1800`, `--sleep-on-idle`, `--enable-deepseek-v4-fp4-indexer` as AB_ENV defaults (each disablable); `DSV41_PREFILL_BYPASS` + `MIN_FREE_SLOTS_DELAY` stay arm-only; ds4 README protocol note, arm commands, deviations table; DEEPSEEK §18 v2.4-era claims annotated; gate 1007 OK |
| ~20:13 ET | `82e6932` | Board refresh (session boundary) + `SESSION-RECORD` entry for the **BeeGFS outage**: `beegfs-meta`/`beegfs-storage` on `.30` failed 19:28:50 ET with "Couldn't find any usable NIC"; services restarted, dead client sessions remounted on head and `.30`; two launch attempts died on the token read before the fix |
| ~21:05 ET | `a0c7ec3` | ds4 README §"Measured: aff52fa5 parity A/B/C": shipped line at parity with upstream — speedbench ALL 86.82 vs 87.5, prose 64.50 vs 64.7, sparkDash prose **decode window** 90.77 vs 91.3; house 37/37 and needles 32k/131k 10/10 on both measured arms; the seven new defaults are sub-threshold over the old line and ship as config identity; the four contested knobs stay arm-only |
| ~21:2x ET | *(this commit)* | Corrections on top of `a0c7ec3`: cross-arm deltas flagged as boot-order-confounded (TTR 190.6 → 235.9 → 435.8 s monotonic; Arm B's own prose runs declined 85.66 → 84.1 → 82.33 within its boot) — only the within-boot comparisons against upstream are claimed; the address-hygiene guard failure that `a0c7ec3` slipped past (an endpoint literal in this board's earlier row) is fixed |