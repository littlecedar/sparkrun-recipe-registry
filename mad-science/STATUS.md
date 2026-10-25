# Board — generated 2026-10-26 18:38 ET

## In flight

| where | owner | what |
|---|---|---|
| census | board-keeper | **18:38 ET 2026-10-26, all six nodes (read-only `ssh` + `docker ps` per node + `nvidia-smi`)**: `.31`/`.32`/`.33`/`.34` 1 container each — `sparkrun_10aee0c5ca8d5bdb_f31ef03f5cb9` up ~2 h; `.31` GPU 96 % (needle@983k cell running), `.32`–`.34` 0 % (TP-sharded ranks idle between their exchanges); `.30` 0, `.35` 0 — nothing live (no reservation) on the single-node cells, which the lock row designates "as needed" |
| b12x-parity-boot + needle rerun | tp4-recovery | queue `w4-b12x-parity` (running): b12x serve live on the quartet (`--load-format b12x`, dspark spec-decode, disk-Engram); detached `parity-cells.sh` runner on the head is advancing — house battery exited, parity ladder rc=0, needle@32768 rc=0, needle@131072 timed out rc=124 (its own `timeout 2400`), needle@983040 in flight under the same cap (receipts dir `~/benchmarks/tp4-window4-20261026/`) |

## Work queue

Mirrors `mad-science/queue.json` via `tools/task-queue.py` (check **ok**, 19 tasks, at 18:38; holder turn 1's ledger edits `0550ac7` landed and verified). Scheduler top-3 at 18:38: `ds4-upstream-adapter-trial` (queued, w −2.00, the adoption path), candidate 6 (blocked, w 1.50), S1 cache-report (blocked, w 1.50). Later rows: S2 lpm, S3 min-free-slots-delay (blocked, w 1.50); `w4-b12x-parity` **running** (w 2.00); build-gated arms 3/5 (w 3.00); `ds4-knapcio-byte-reproducible` (w 4.00); new tasks `mellum-mtp-zz-probe`, `drafter-alternatives-search`, `tp4-head-to-head-2025`, `b12x-vllm-tuning-round`, `media-demo-workproduct`, `gguf-viability-triage`; `dsv41-vllm-ship-recipe` state-blocked on the external pass gate; `ds4-adapter-report-gate` rebased on upstream HEAD (w 14.00 class). S0 and Beam cells remainder **done**:

| job | node cost | holds | state |
|---|---|---|---|
| 1. `ds4-upstream-adapter-trial` — re-pin the knapcio adapter overlay `27616bec` (v2.4) to upstream HEAD `aff52fa5` on `f80c91a4b`; rebuild + boot-verify the shipped 1017 line | single | tp4-recovery | queued — scheduler top (w −2.00, the adoption path; blocks S1/S2/S3/candidate-6) |
| 2. w4-candidate6-reasoning-effort — `reasoning_effort` high on the main-image base | quartet | tp4-recovery | blocked by `ds4-upstream-adapter-trial` |
| 3. w4-s1-cache-report — prefix-cache truth (`--enable-cache-report`) | quartet | tp4-recovery | blocked by `ds4-upstream-adapter-trial` |
*(Later scheduler rows: S2 lpm, S3 min-free-slots-delay (blocked by the adapter trial, w 1.50); `w4-b12x-parity` **running** (w 2.00, boot live above); build-gated survey arms 3/5 (w 3.00); `ds4-knapcio-byte-reproducible` (w 4.00); new tasks `mellum-mtp-zz-probe`, `drafter-alternatives-search`, `tp4-head-to-head-2025`, `b12x-vllm-tuning-round`, `media-demo-workproduct`, `gguf-viability-triage`; `dsv41-vllm-ship-recipe` state-blocked on the external pass gate; `ds4-adapter-report-gate` rebased onto upstream HEAD. S0 and Beam cells remainder **done** in the ledger.)*

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
| ~18:30 ET | `0550ac7` | Queue ledger round-4/5 rulings folded: adapter trial becomes the adoption path blocking the flag track; 7 new tasks; ship-recipe state-blocked; S0 stale cite repointed to `recipes/ds4/README.md` |