# Board — generated 2026-10-26 17:43 ET

## In flight

| where | owner | what |
|---|---|---|
| census | board-keeper | **17:43 ET 2026-10-26, all six nodes (read-only `ssh` + `docker ps` per node + `nvidia-smi`)**: `.31`/`.32`/`.33`/`.34` 1 container each — one live sparkrun boot (`sparkrun_10aee0c5ca8d5bdb_f31ef03f5cb9`, up ~1 h, one container per rank), **all four GPUs at 96 % util** — a live benchmark; `.30` 0, `.35` 0 — nothing live (no reservation) on the single-node cells, which the lock row designates "as needed" |
| b12x-parity-boot | tp4-recovery | queue `w4-b12x-parity` (running): upstream vLLM b12x fork serving DeepSeek-V4.1-Flash-1017 on the quartet (disk-Engram, io_uring) against the pre-registered §17 bars — boot `10aee0c5ca8d5bdb_f31ef03f5cb9` live, GPUs saturated at census |

## Work queue

Mirrors the owner-directed task-queue system (`cd2a60a`: `tools/task-queue.py` weight order, `mad-science/queue.json` as source; TODO §"Retry queue — window 4" still the provenance). `task-queue.py check`: **ok** (12 tasks) at 17:43. Scheduler top-3 at 17:43: candidate 6 (blocked), S1 cache-report (blocked), S2 lpm (blocked); the running job is `w4-b12x-parity`. Owner input: `GUIDANCE.md` round-2 questions §5–§9 were ANSWERED and folded 2026-10-26 (evening) as dated advisories in `mad-science/TODO.md` §"Retry queue — window 4" (adapter ownership → upstream HEAD; BeeGFS mitigation not a hard gate; Mellum `zz-` MTP probe + DFlash/DSpark search; Beam ships if bars pass, head-to-head vs 1017/GLM in `TP4-HEAD-TO-HEAD-1025.md`; parity C10 fallback = more vLLM experimentation). The queue implications (unblock/retarget rows) are applied to `queue.json` separately:

| job | node cost | holds | state |
|---|---|---|---|
| 1. w4-candidate6-reasoning-effort — `reasoning_effort` high on the main-image base | quartet | tp4-recovery | blocked (S0 answered NEGATIVE — shipped-image fallback = owner decision) |
| 2. w4-s1-cache-report — prefix-cache truth (`--enable-cache-report`) | quartet | tp4-recovery | blocked (designed for the stock main-tree base; S0 negative) |
| 3. w4-s2-lpm — lpm alongside `--enable-cache-report` | quartet | tp4-recovery | blocked (same base dependency as S1) |
*(Later scheduler rows, tier dsv4.1-1017: S3 min-free-slots-delay (blocked, w 1.50); `w4-b12x-parity` **running** (w 2.00, boot live); survey arms 3/5 (build-gated, w 3.00); `ds4-knapcio-byte-reproducible` and `ds4-upstream-adapter-trial` (w 4.00); `ds4-adapter-report-gate` (the 20 h re-port, w 14.00, blocked). S0 and Beam cells remainder are **done** in the ledger.)*

## Landed this session

| time ET | commit | one clause |
|---|---|---|
| 08:11 ET | `5141c20` | Beam arm: card's `--reasoning-parser beam`/`--tool-call-parser beam` added to `recipes/explore/zz-beam-1.0-501b-a23b-nvfp4-tp4-vllm.yaml`; TODO gains §"Retry queue — window 4" (three tracks + owner advisories) |
| 08:12 ET | `ab6078a` | Fleet-wide Docker seccomp change enables io_uring on all six nodes: `tools/enable-io-uring.{py,sh}` + guard test, probe-before/apply-after evidence recorded; b12x boot unblocked |
| ~10:30 ET | `65f8fce` | Beam arm fix: cell-(d) comment lines had landed inside the folded command scalar and ran as engine argv (boot-2 attempt 2 crash) — notes moved above `command:`, fold cleaned |
| ~10:35 ET | `3de5d70` | Beam DFlash2 drafter by pool snapshot path (vLLM SpeculativeConfig cannot resolve a repo id under `HF_HUB_OFFLINE`); snapshot `163b276b` verified |
| ~11:00 ET | `689ee3b` | TODO window-4: owner's three dated rulings landed — drafter policy (DFlash2 stays), build-gate drift (durable re-port path), model priority (1017 primary) |
| ~11:30 ET | `cd2a60a` | Owner-directed task queue: `tools/task-queue.py` weighted scheduler + `mad-science/queue.json` seed + `QUEUE.md` protocol + guard tests |
| 16:26 ET | `7fa352d` | Beam sha guard exempts `--speculative-config` tokens + two controls; parity recipe carries BOTH ulimits (boots 2–4 proved each half alone is fatal) |
| 17:34 ET | `055ab3d` | GUIDANCE adapter background folded into tracked records; only open questions remain |
| 17:42 ET | `cbede11` | Owner answers §5–§12 folded into TODO dated advisories; GUIDANCE rewound to open questions |