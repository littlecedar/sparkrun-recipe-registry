# Board — generated 2026-10-26 20:13 ET

## In flight

| where | owner | what |
|---|---|---|
| census | DSV41F1017-Parity | **20:13 ET 2026-10-26, all six nodes (read-only ssh + `docker ps` + `nvidia-smi`)**: `.31`–`.34` carry exactly one container each (the Arm A serve; GPU 37–96 %), `.30` and `.35` 0 containers / 0 % GPU — the Arm A boot is the only fleet workload. Window claimed in `.scratch/fleet-window.lock` (`.31`–`.34`, 2026-10-26 evening → A/B close) |
| ds4-1017 knapcio-parity A/B | DSV41F1017-Parity | **Arm A (strict aff52fa5 production parity) UP** on `.31`–`.34` (`sparkrun_c989632ede4f538e_4500a8b3cae2`, endpoint `http://10.0.4.31:8000`, TTR port-open 190.6 s): boot line verified `chunked_prefill_size=8192` / `max_running_requests=16` / `context_len=1048576` / pool `4,111,616`; server_args carry `watchdog_timeout=1800`, `sleep_on_idle=True`, `enable_deepseek_v4_fp4_indexer=True`, `prefill_decode_interval=2`, `min_free_slots_delay=1`; serve log shows `DSV41_PREFILL_BYPASS armed` (256 fresh / 32 candidates), `[cert_head] armed (mode 1, M [6,12,18,24,30,36,42,48])`, fast load ARMED. Boot-watchdog armed. Cells in flight: sparkDash prose c1, speedbench full (all-73 + prose geomeans), house 4096 thinking-on, needles 32k/131k. **Arm B (control, shipped line) boots after Arm A's cells** |

Mirrors `mad-science/queue.json` via `tools/task-queue.py`. **Running**: none in queue terms — the A/B is this session's window work. Open/blocked, per `TODO.md` row 22 next-window order (DeepGEMM SM12x watch first, then glm-flash, Beam staging, H3, spares):

| job | node cost | holds | state |
|---|---|---|---|
| `arch-deepgemm-sm12x-paged-sparse` — DeepGEMM SM12x for the paged-sparse logits family (upstream watch) | watch | queue | BLOCKED on upstream (row 21) — first in the next-window order |
| `w4-survey-arm3-indexer-scoring` | quartet | — | ARCH-GATED behind SM12x (row 21) |
| `w4-survey-arm5-trtllm-mla` | quartet | — | ARCH-GATED behind SM12x (row 21) |
| `h3-quartet-retry` | quartet | — | queued, idle-only |
| `glm-flash-concurrency-degradation-search` | quartet | — | DEFERRED (owner, row 19) |
| Beam staging (`h2h-beam-house-and-bfcl-category` remainder) | spare | — | parked (owner, rows 19/22) |

## Landed this session

| time ET | commit | one clause |
|---|---|---|
| ~20:05 ET | `7be1a13` | aff52fa5 production block adopted in the dsv41-sglang-overlay launcher — `DSV41_CERT_HEAD=1` + M list, `DSV41_FAST_LOAD_EP_SIZE=1`, `DSV41_FAST_LOAD_N_EXPERTS=384`, `WATCHDOG_TIMEOUT=1800`, `--sleep-on-idle`, `--enable-deepseek-v4-fp4-indexer` as AB_ENV defaults (each disablable); `DSV41_PREFILL_BYPASS` + `MIN_FREE_SLOTS_DELAY` stay arm-only (upstream-experimental / S3 negative on the pre-adoption line); ds4 README gains the protocol-comparability note (sparkDash prose c1 91.3 vs speedbench prose 64.7 / all-73 87.5 vs cold-contaminated ladder 64.08), the two arm commands and the deviations table; DEEPSEEK §18 v2.4-era "cert_head already 0" and "no scheduler flag we lack" claims annotated; gate 1007 tests OK |