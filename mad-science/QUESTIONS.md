# QUESTIONS — the register of owner questions (2026-10-22)

This file holds the **unresolved** questions only — `open` and `blocked on hardware` — one row each, with
the provenance that raises it. **Settled (answered) questions live in `TODO.md` §"Settled questions"**, which
carries the answer and the rationale verbatim; row numbers are stable across both files, so a citation such
as `QUESTIONS.md #9` still resolves through that record, and a settled question is never re-opened.

| summary | value |
|---|---|
| unanswered | **1** — `#84` (the ERNIE-5.5-Flash-Base licence class), raised by the **2026-11-11 TP>=4 owner survey round**: that round's nine survey questions (`S1`–`S9`) were asked and answered in one file and folded verbatim into `TODO.md` §"Settled questions" under `## Owner round 2026-11-11 — TP>=4 survey`, and the `mad-science/SURVEY.md` they lived in was deleted at that fold. Before it the register was empty: the thirteen rows `#69`–`#81` + `#83` were **asked and answered in one batch on 2026-11-09** and moved verbatim to the same section under `## Owner round 2026-11-09`. That batch came from the 2026-11-08 sweep of `mad-science/` and was re-checked against current state before asking, which withdrew two of the original fifteen: `#73` (BeeGFS `Restart=on-failure`) had already been executed the same day, and `#82` (`# DECISIONS` in JSON) is ruled by `QUEUE.md` itself ("a settled question or decision stays prose … correctly outside the JSON"). What the answers produced: the TP1/TP2 freeze **holds** (`#69`); the SM121 trio is **not retired** — the OOM is to be diagnosed, and any risky attempt runs `.31`–`.35` and never `.30` (`#70`); the stale six-node campaign lock is **deleted** (`#71`); the live earlyoom pair `-m 4,1 -s 100,95` is **ratified** and the drafted `-m 14,5 -s 90,80` dropped (`#72`); the single shared HF hub **stays** (`#74`); the storage budget is **restated at pool level** (`#75`); the installed FLARE build is **accepted as-is** (`#76`); the `flare agent` grant **extends to `.31`–`.34`** with the serve port moved to 9000 (`#77`); DSV4-Pro is **closed as a quality gamble** (`#78`); the compute set is **fixed at six GB10 nodes** (`#79`); Mistral-Large-4 **moved to `attic/`** (`#80`); `FLUX.2-dev` and `flux-3-image-klein` licences **accepted**, `dinov3` **declined** (`#81`); and `OOMScoreAdjust=-900` **may** also go on `user@1000.service` (`#83`) |
| settled | **50** — `#1`, `#4`, `#5`, `#8`–`#16` moved verbatim to `TODO.md` §"Settled questions" on 2026-10-23, `#19` joined them **answered 2026-10-24** (the Community license), `#20` (**executed**: the HF cache is entirely on the pool) and `#17` (**authorized**, pending the seccomp route) joined them the same day, `#2` joined **2026-10-24** (the 16384 prefill chunk, measured and shipped), and `#3`, `#7` and `#21` joined them **2026-10-24** (answered via the one-time owner questionnaire and folded per the protocol); `#18` joined them **2026-10-29** (superseded — fixed by `kho=off` fleet-wide), `#54` + `#56` joined them **2026-11-02** (owner answers in session: the ghcr push had already landed, so `#54`'s grant was moot; the LFM arms ship as ordinary arms, no eval-only banner), `#6` + `#53` joined them **2026-11-03** (a phased `flare agent` install via the vendor APT repository, whose key's `apt upgrade` reach the owner accepted; DeepGEMM's SM121 kernels patched in-house rather than tracked upstream), `#57`–`#66` joined them **2026-11-06** — a ten-question round asked and answered in one session because this register was empty while ten queue rows sat `blocked`; `#67` (host memory policy on all six nodes, **with a dated correction: its earlyoom numbers were superseded by measurement the same afternoon**) + `#68` (instrumented vs uninstrumented baseline) joined them **2026-11-08**; and `#69`–`#81` + `#83` joined them **2026-11-09** in one batch (§"unanswered" above). Numbering is stable, so a citation such as `QUESTIONS.md #9` still resolves. The 2026-11-11 survey round answered nine unnumbered survey rows (`S1`–`S9`) and raised `#84` rather than settling a numbered row, so this count stands at 50 |
| blocks the most downstream work | **`#84` only** — the ERNIE licence class decides whether that arm ships, stays probe-only, or is dropped. The rest of the blocked set is ordinary queue state now: the TP≤2 rows wait on the freeze the owner confirmed (`#69`), the SM121 trio waits on `sm121-marlin-oom-diagnosis` (`#70`), the `.30`-root-target question is moot with the hub left as it is (`#74`), and the FLARE work moved into `flare-agent-rollout` as its phase-2 scope (`#76`, `#77`). Two rows now exist only to turn an answer into a receipt: `host-memory-policy-apply` (the `OOMScoreAdjust` drop-ins on `ssh.service`, `NetworkManager.service` and `user@1000.service`, `#72`/`#83`) and `cache-audit-pool-budget` (the tool must measure the pool, not the node, `#75`) |

*(Correction 2026-11-09, later the same day: **the 2026-11-08 freeze this table reports as holding is lifted** — for
TP4 work, and for those TP1/TP2 items that unblock a TP4 item — by the owner directive recorded in `TODO.md`
§"Settled questions" under `## Owner directive 2026-11-09 — TP4 unfrozen, TP1/TP2 only via TP4`; the cells above that
say the freeze holds, and that the TP≤2 rows wait on it, read as the 2026-11-09 answer's state at its date, not as
current state. What the lift does not touch: a TP1/TP2 row that unblocks no TP4 row stays blocked, `#70` still confines
a memory-risky quartet boot to `.31`–`.35` and never `.30`, and `#58` still forbids displacing the production ds4
TP=4 quartet on `.31`–`.34`.)*

## Hardware & authorization

No open rows. The last batch (`#69`–`#83`, 2026-11-09) is settled in `TODO.md` §"Settled questions".

## Host memory & storage policy

No open rows. The last batch (`#69`–`#83`, 2026-11-09) is settled in `TODO.md` §"Settled questions".

## Spend & risk

| # | question | status | why it matters | provenance | asked |
|---|---|---|---|---|---|
| `#84` | **Which licence class does `baidu/ERNIE-5.5-Flash-Base` get — does the eval-only arm ship with the licence's attribution and use-notice obligations, stay probe-only, or not ship at all?** The checkpoint's licence is a custom `ernie-5.5-flash-base-model-license-v1.0`: free for non-commercial use, commercial use at or below US$50M annual related revenue with attribution plus a one-time use notice (section 4.2), and above that only with separate authorization (section 4.3). The arm boots, scores 190/200 GSM8K 0-shot, and carries a window the port passes; the recipe still ships as a `zz-` probe under no ruling. | open — owner decision | This is the only thing between the arm and a shipped recipe. The licence is not non-commercial-only, so a classification exists — but the obligations must be stated wherever the arm is documented, and only the owner can accept them. | `mad-science/TODO.md` §"Settled questions" `## Owner round 2026-11-11 — TP>=4 survey` S5; `mad-science/queue.json` row `lane-survey-baidu-ernie-5.5-flash-base` (licence terms read from the Hub `LICENSE`, 2026-11-10) | 2026-11-11 |

The earlier batch (`#69`–`#83`, 2026-11-09) is settled in `TODO.md` §"Settled questions"; the 2026-11-11 survey round answered its nine unnumbered survey rows and raised `#84` above.

## Priority & close-out

No open rows. The last batch (`#69`–`#83`, 2026-11-09) is settled in `TODO.md` §"Settled questions".
