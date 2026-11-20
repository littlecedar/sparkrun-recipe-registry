# QUESTIONS — the register of owner questions (2026-10-22)

This file holds the **unresolved** questions only — `open` and `blocked on hardware` — one row each, with
the provenance that raises it. **Settled (answered) questions live in `TODO.md` §"Settled questions"**, which
carries the answer and the rationale verbatim; row numbers are stable across both files, so a citation such
as `QUESTIONS.md #9` still resolves through that record, and a settled question is never re-opened.

| summary | value |
|---|---|
| unanswered | **1** — `#85` (below), raised 2026-11-17: who deleted the production fence on `.31`–`.34`, and was it authorized. `#86` and `#87`, the two licence classes raised 2026-11-20, were answered the same day and moved to `TODO.md` §"Settled questions" under `## Owner ruling 2026-11-20 — both licence classes ruled not applicable`. Before them the register held **0** — `#84` (the ERNIE-5.5-Flash-Base licence class) was raised by the **2026-11-11 TP>=4 owner survey round** and answered the same day; it is settled in `TODO.md` §"Settled questions" under `## Owner answer 2026-11-11 — ERNIE licence class` and has left this file's open set. That round's nine survey questions (`S1`–`S9`) were asked and answered in one file and folded verbatim into `TODO.md` §"Settled questions" under `## Owner round 2026-11-11 — TP>=4 survey`, and the `mad-science/SURVEY.md` they lived in was deleted at that fold. Before it the register was empty: the thirteen rows `#69`–`#81` + `#83` were **asked and answered in one batch on 2026-11-09** and moved verbatim to the same section under `## Owner round 2026-11-09`. That batch came from the 2026-11-08 sweep of `mad-science/` and was re-checked against current state before asking, which withdrew two of the original fifteen: `#73` (BeeGFS `Restart=on-failure`) had already been executed the same day, and `#82` (`# DECISIONS` in JSON) is ruled by `QUEUE.md` itself ("a settled question or decision stays prose … correctly outside the JSON"). What the answers produced: the TP1/TP2 freeze **holds** (`#69`); the SM121 trio is **not retired** — the OOM is to be diagnosed, and any risky attempt runs `.31`–`.35` and never `.30` (`#70`); the stale six-node campaign lock is **deleted** (`#71`); the live earlyoom pair `-m 4,1 -s 100,95` is **ratified** and the drafted `-m 14,5 -s 90,80` dropped (`#72`); the single shared HF hub **stays** (`#74`); the storage budget is **restated at pool level** (`#75`); the installed FLARE build is **accepted as-is** (`#76`); the `flare agent` grant **extends to `.31`–`.34`** with the serve port moved to 9000 (`#77`); DSV4-Pro is **closed as a quality gamble** (`#78`); the compute set is **fixed at six GB10 nodes** (`#79`); Mistral-Large-4 **moved to `attic/`** (`#80`); `FLUX.2-dev` and `flux-3-image-klein` licences **accepted**, `dinov3` **declined** (`#81`); and `OOMScoreAdjust=-900` **may** also go on `user@1000.service` (`#83`) |
| settled | **53** — `#86` and `#87` joined them **2026-11-20** (both licence classes ruled not applicable to our use), `#1`, `#4`, `#5`, `#8`–`#16` moved verbatim to `TODO.md` §"Settled questions" on 2026-10-23, `#19` joined them **answered 2026-10-24** (the Community license), `#20` (**executed**: the HF cache is entirely on the pool) and `#17` (**authorized**, pending the seccomp route) joined them the same day, `#2` joined **2026-10-24** (the 16384 prefill chunk, measured and shipped), and `#3`, `#7` and `#21` joined them **2026-10-24** (answered via the one-time owner questionnaire and folded per the protocol); `#18` joined them **2026-10-29** (superseded — fixed by `kho=off` fleet-wide), `#54` + `#56` joined them **2026-11-02** (owner answers in session: the ghcr push had already landed, so `#54`'s grant was moot; the LFM arms ship as ordinary arms, no eval-only banner), `#6` + `#53` joined them **2026-11-03** (a phased `flare agent` install via the vendor APT repository, whose key's `apt upgrade` reach the owner accepted; DeepGEMM's SM121 kernels patched in-house rather than tracked upstream), `#57`–`#66` joined them **2026-11-06** — a ten-question round asked and answered in one session because this register was empty while ten queue rows sat `blocked`; `#67` (host memory policy on all six nodes, **with a dated correction: its earlyoom numbers were superseded by measurement the same afternoon**) + `#68` (instrumented vs uninstrumented baseline) joined them **2026-11-08**; and `#69`–`#81` + `#83` joined them **2026-11-09** in one batch (§"unanswered" above). Numbering is stable, so a citation such as `QUESTIONS.md #9` still resolves. The 2026-11-11 survey round answered nine unnumbered survey rows (`S1`–`S9`), and `#84` joined them **2026-11-11** (the ERNIE licence class: a production arm is permitted, subject to the licence's attribution and one-time use notice, with the ship call left to measured performance), so this count is **53** |
| blocks the most downstream work | **`#85`** — the only open row, and it blocks nothing downstream (it is authorization and register hygiene). `#86` and `#87` were answered on 2026-11-20, so neither licence class gates a promotion any more; `#84` was answered on 2026-11-11. The blocked set is otherwise ordinary queue state now: the TP≤2 rows wait on the production return the 2026-11-11 directive names, the SM121 trio waits on `sm121-marlin-oom-diagnosis` (`#70`), the `.30`-root-target question is moot with the hub left as it is (`#74`), and the FLARE work moved into `flare-agent-rollout` as its phase-2 scope (`#76`, `#77`). Two rows now exist only to turn an answer into a receipt: `host-memory-policy-apply` (the `OOMScoreAdjust` drop-ins on `ssh.service`, `NetworkManager.service` and `user@1000.service`, `#72`/`#83`) and `cache-audit-pool-budget` (the tool must measure the pool, not the node, `#75`) |

*(Correction 2026-11-09, later the same day: **the 2026-11-08 freeze this table reports as holding is lifted** — for
TP4 work, and for those TP1/TP2 items that unblock a TP4 item — by the owner directive recorded in `TODO.md`
§"Settled questions" under `## Owner directive 2026-11-09 — TP4 unfrozen, TP1/TP2 only via TP4`; the cells above that
say the freeze holds, and that the TP≤2 rows wait on it, read as the 2026-11-09 answer's state at its date, not as
current state. What the lift does not touch: a TP1/TP2 row that unblocks no TP4 row stays blocked, `#70` still confines
a memory-risky quartet boot to `.31`–`.35` and never `.30`, and `#58` still forbids displacing the production ds4
TP=4 quartet on `.31`–`.34`.)*

*(Correction 2026-11-12: **`#81`'s dinov3 half is superseded** — the owner's 2026-11-12 oversight thread accepts
`facebook/dinov3-vith16plus-pretrain-lvd1689m` ("accept") and authorizes two eval-only arms, so the "unanswered"
cell's "`dinov3` **declined**" reads as the 2026-11-09 answer's state at its date, not as current state. The row
stays settled and the counts above do not move: an accepted license settles the same question `#81` settled,
it does not open one. Record and obligations: `TODO.md` §"Settled questions" under
`## Owner ruling 2026-11-12 — DINOv3 accepted, two eval-only arms authorized`.)*

## Hardware & authorization
- **#85 — Who deleted the production fence over `.31`–`.34` at `2026-11-17T08:06:52Z`, and was it
  owner-authorized?** — `open` — the fence was installed by *"owner directive, session production-fence"*
  (`fenced_at` `2026-11-12T05:05:32Z`, `corrected_at` `2026-11-17T03:23:28Z` naming task
  `b020d2dd178343a5_510ded98367b`), its `reason` being *production serve: DeepSeek-V4.1-Flash-1017 TP=4 —
  never displaced, stopped, or leased*. Between the 03:00 ET tick's head read (`2,120 B`, sha `44b4804b…`,
  one `fenced` record) and the same file at `08:06:52Z` mtime (`482 B`, sha `45b625b4…`) the record became
  `fenced: []` and one live lease appeared for `session:picom-boot-20261117` over the same four hosts. **The
  ledger keeps no record of who removed the fence** — a `fenced_by` audit trail records creation and
  correction, not deletion — so the removal is unattributed. The serve the fence protected had itself been
  gone since `04:32:25Z` (board rows at 01:07, 02:00 and 03:18 ET), so the question is authorization and
  register hygiene, not whether lifting it made operational sense. provenance: `mad-science/STATUS.md`
  03:18 ET `window` row; `.local/fleet-leases.json` sha transition `44b4804b…` → `45b625b4…`; asked
  2026-11-17.

The last batch (`#69`–`#83`, 2026-11-09) is settled in `TODO.md` §"Settled questions".

## Host memory & storage policy

No open rows. The last batch (`#69`–`#83`, 2026-11-09) is settled in `TODO.md` §"Settled questions".

## Spend & risk

`#84` (the ERNIE licence class) was answered 2026-11-11 and is settled in `TODO.md` §"Settled questions"
under `## Owner answer 2026-11-11 — ERNIE licence class`; the earlier batch (`#69`–`#83`, 2026-11-09) and the
2026-11-11 survey round are settled there too.

## Priority & close-out

One open row: `#85`. The last batch (`#69`–`#83`, 2026-11-09) is settled in `TODO.md` §"Settled questions", and
`#86`/`#87` joined it 2026-11-20.
