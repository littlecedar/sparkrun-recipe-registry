# Board — generated 2026-10-26 18:05 ET

## In flight

| where | owner | what |
|---|---|---|
| census | board-keeper | **18:05 ET 2026-10-26, all six nodes (read-only `ssh` + `docker ps` per node + `nvidia-smi`)**: `.31`/`.32`/`.33`/`.34` 1 container each — `sparkrun_10aee0c5ca8d5bdb_f31ef03f5cb9` up ~2 h; GPUs 0 % at the census instant (between-cells gap; rank-0 serve log advanced ~9 min before the census, APIServer alive, `Running: 0 reqs`); `.30` 0, `.35` 0 — nothing live (no reservation) on the single-node cells, which the lock row designates "as needed" |
| b12x-parity-boot | tp4-recovery | queue `w4-b12x-parity` (running): upstream vLLM b12x fork serving DeepSeek-V4.1-Flash-1017 on the quartet (disk-Engram, io_uring; `--load-format b12x`, dspark spec-decode confirmed in server args) against the pre-registered §17 bars — boot `10aee0c5ca8d5bdb_f31ef03f5cb9` live ~2 h; between-cells gap at census (GPUs 0 %, serve log advanced ~9 min prior) |

## Work queue

Mirrors `mad-science/queue.json` via `tools/task-queue.py` (check **ok**, 12 tasks, at 18:05). Scheduler top-3 at 18:05: candidate 6 (blocked, w 1.50), S1 cache-report (blocked, w 1.50), S2 lpm (blocked, w 1.50); `w4-b12x-parity` **running** (w 2.00, live boot above); S0 and Beam cells remainder **done**. Queue-edit spot-check: tp4-recovery's pending ledger changes (flag-track `blocked_by` → `ds4-upstream-adapter-trial`, four new tasks, S0 note re-point) are **still unapplied** — flagged to the director at 18:05. Owner round-5 answers folded into `TODO.md` dated advisories by `541d843` (GUIDANCE.md deleted):

| job | node cost | holds | state |
|---|---|---|---|
| 1. w4-candidate6-reasoning-effort — `reasoning_effort` high on the main-image base | quartet | tp4-recovery | blocked (S0 answered NEGATIVE — shipped-image fallback = owner decision) |
| 2. w4-s1-cache-report — prefix-cache truth (`--enable-cache-report`) | quartet | tp4-recovery | blocked (designed for the stock main-tree base; S0 negative) |
| 3. w4-s2-lpm — lpm alongside `--enable-cache-report` | quartet | tp4-recovery | blocked (same base dependency as S1) |
*(Later scheduler rows: S3 min-free-slots-delay (blocked, w 1.50); arms 3/5 build-gated (w 3.00); `ds4-knapcio-byte-reproducible` and `ds4-upstream-adapter-trial` (w 4.00); `ds4-adapter-report-gate` (the 20 h re-port, w 14.00, blocked).)*

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
| 18:00 ET | `541d843` | Owner round-5 answers folded into TODO dated advisories; `mad-science/GUIDANCE.md` deleted |