# Board — generated 2026-10-26 08:16 ET

## In flight

| where | owner | what |
|---|---|---|
| census | board-keeper | **08:16 ET 2026-10-26, all six nodes (read-only `ssh` + `docker ps -aq` + `df`)**: `.31`/`.32`/`.33`/`.34` 1 container each — one live sparkrun boot (`sparkrun_30078b4aa125dd7d…`, up ~1 min on `.31`, quartet-wide); `.30` 0, `.35` 0 — nothing live (no reservation) on the single-node cells; docker healthy fleet-wide (seccomp change complete, no restarts pending) |
| beam-boot | tp4-window4 | window-4 item 1, Beam cells (b)–(d): quartet boot live (one container per rank, up ~1 min at census); parser flags `--reasoning-parser beam`/`--tool-call-parser beam` landed by `5141c20` before the boot |

## Work queue

Mirrors `mad-science/TODO.md` §"Retry queue — window 4 (declared 2026-10-26)" (holder `tp4-window4`; all four owner tracks in scope, screen-then-extend, builds authorized for survey candidates 3/5 only; seccomp workstream DONE and dropped from the board note):

| job | node cost | holds | state |
|---|---|---|---|
| 1. Beam cells (b)–(d): house battery + needle, BFCL tools leg, DFlash2 A/B (parser flags landed `5141c20`) | quartet `.31`–`.34` | tp4-window4 | **running** (boot live at 08:16 census) |
| 2. ds4 candidate survey (flag-level 1/2/6 on main-image base; builds only for 3/5) | quartet | tp4-window4 | queued (one boot at a time) |
| 3. b12x parity boot (§17 acceptance: C1 ≥ 64.0, C10 ≥ 110.5 t/s, house ≥36/37, needle 3/3) | quartet | tp4-window4 | queued (unblocked by the landed seccomp change) |

## Landed this session

| time ET | commit | one clause |
|---|---|---|
| 08:11 ET | `5141c20` | Beam arm: card's `--reasoning-parser beam`/`--tool-call-parser beam` added to `recipes/explore/zz-beam-1.0-501b-a23b-nvfp4-tp4-vllm.yaml`; TODO gains §"Retry queue — window 4" (three tracks + owner advisories) |
| 08:12 ET | `ab6078a` | Fleet-wide Docker seccomp change enables io_uring on all six nodes: `tools/enable-io-uring.{py,sh}` + guard test, probe-before/apply-after evidence recorded; b12x boot unblocked |