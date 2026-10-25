# Board — generated 2026-10-26 13:15 ET

## In flight

| where | owner | what |
|---|---|---|
| census | board-keeper | **13:15 ET 2026-10-26, all six nodes (read-only `ssh` + `docker ps` per node + `df`)**: `.31`/`.32`/`.33`/`.34` 1 container each — one live sparkrun Beam boot (`sparkrun_30078b4aa125dd7d_d8aab09b0c41`, up ~8 min, one container per rank); `.30` 0, `.35` 0 — nothing live (no reservation) on the single-node cells, which the lock row designates "as needed" |
| beam-boot | tp4-window4 | window-4 Beam cells remainder ((b) needle rerun `--needle-max-tokens 512`, (c) BFCL tools leg, (d) DFlash2 A/B): quartet boot live, up ~8 min at census; **S0 control is next** per the new run order (Beam cells → S0 → candidate 6/S1/S2/S3 → parity; arms 3/5 stay blocked behind the 20 h adapter re-port) |

## Work queue

Mirrors the owner-directed task-queue system (`cd2a60a`: `tools/task-queue.py` weight order, `mad-science/queue.json` as source; TODO §"Retry queue — window 4" still the provenance). Scheduler top-3 at 13:15: S0 control (weight −3.50, queued), Beam cells remainder (**running**), candidate 6 (queued). Owner input pending: `mad-science/GUIDANCE.md` round-2 questions §5–§9 (uncommitted, awaiting the owner — cited, not folded):

| job | node cost | holds | state |
|---|---|---|---|
| 1. w4-s0-control — stock main-image control boot, gates the flag-level survey track | quartet | tp4-window4 | queued — scheduler top (weight −3.50) |
| 2. w4-beam-cells-remainder — needle 512 rerun, BFCL tools leg, DFlash2 A/B | quartet `.31`–`.34` | tp4-window4 | **running** (boot live at 13:15 census) |
| 3. w4-candidate6-reasoning-effort — `reasoning_effort` high on the main-image base | quartet | tp4-window4 | queued |
*(Later scheduler rows, weights 1.50–2.00, tier dsv4.1-1017: S1 cache-report, S2 lpm, S3 min-free-slots-delay, b12x parity; arms 3/5 build-gated behind the adapter re-port.)*

## Landed this session

| time ET | commit | one clause |
|---|---|---|
| 08:11 ET | `5141c20` | Beam arm: card's `--reasoning-parser beam`/`--tool-call-parser beam` added to `recipes/explore/zz-beam-1.0-501b-a23b-nvfp4-tp4-vllm.yaml`; TODO gains §"Retry queue — window 4" (three tracks + owner advisories) |
| 08:12 ET | `ab6078a` | Fleet-wide Docker seccomp change enables io_uring on all six nodes: `tools/enable-io-uring.{py,sh}` + guard test, probe-before/apply-after evidence recorded; b12x boot unblocked |
| ~10:30 ET | `65f8fce` | Beam arm fix: cell-(d) comment lines had landed inside the folded command scalar and ran as engine argv (boot-2 attempt 2 crash) — notes moved above `command:`, fold cleaned |
| ~10:35 ET | `3de5d70` | Beam DFlash2 drafter by pool snapshot path (vLLM SpeculativeConfig cannot resolve a repo id under `HF_HUB_OFFLINE`); snapshot `163b276b` verified |
| ~11:00 ET | `689ee3b` | TODO window-4: owner's three dated rulings landed — drafter policy (DFlash2 stays), build-gate drift (durable re-port path), model priority (1017 primary) |
| ~11:30 ET | `cd2a60a` | Owner-directed task queue: `tools/task-queue.py` weighted scheduler + `mad-science/queue.json` seed + `QUEUE.md` protocol + guard tests |