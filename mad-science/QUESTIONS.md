# QUESTIONS — the register of owner questions (2026-10-22)

This file holds the **unresolved** questions only — `open` and `blocked on hardware` — one row each, with
the provenance that raises it. **Settled (answered) questions live in `TODO.md` §"Settled questions"**, which
carries the answer and the rationale verbatim; row numbers are stable across both files, so a citation such
as `QUESTIONS.md #9` still resolves through that record, and a settled question is never re-opened.

| summary | value |
|---|---|
| unanswered | **3** — `#85` (below), raised 2026-11-17: who deleted the production fence on `.31`–`.34`, and was it authorized; `#86` (below), raised 2026-11-20: which licence class `tencent/Hy4-flash` gets under the Tencent Hy License 1.0; and `#87` (below), raised 2026-11-20: which licence class `Edge0/Edge0-145B-NVFP4` gets under the Edge0 Community Model License 1.0 stacked over the Qwen Community License 1.0. Before them the register held **0** — `#84` (the ERNIE-5.5-Flash-Base licence class) was raised by the **2026-11-11 TP>=4 owner survey round** and answered the same day; it is settled in `TODO.md` §"Settled questions" under `## Owner answer 2026-11-11 — ERNIE licence class` and has left this file's open set. That round's nine survey questions (`S1`–`S9`) were asked and answered in one file and folded verbatim into `TODO.md` §"Settled questions" under `## Owner round 2026-11-11 — TP>=4 survey`, and the `mad-science/SURVEY.md` they lived in was deleted at that fold. Before it the register was empty: the thirteen rows `#69`–`#81` + `#83` were **asked and answered in one batch on 2026-11-09** and moved verbatim to the same section under `## Owner round 2026-11-09`. That batch came from the 2026-11-08 sweep of `mad-science/` and was re-checked against current state before asking, which withdrew two of the original fifteen: `#73` (BeeGFS `Restart=on-failure`) had already been executed the same day, and `#82` (`# DECISIONS` in JSON) is ruled by `QUEUE.md` itself ("a settled question or decision stays prose … correctly outside the JSON"). What the answers produced: the TP1/TP2 freeze **holds** (`#69`); the SM121 trio is **not retired** — the OOM is to be diagnosed, and any risky attempt runs `.31`–`.35` and never `.30` (`#70`); the stale six-node campaign lock is **deleted** (`#71`); the live earlyoom pair `-m 4,1 -s 100,95` is **ratified** and the drafted `-m 14,5 -s 90,80` dropped (`#72`); the single shared HF hub **stays** (`#74`); the storage budget is **restated at pool level** (`#75`); the installed FLARE build is **accepted as-is** (`#76`); the `flare agent` grant **extends to `.31`–`.34`** with the serve port moved to 9000 (`#77`); DSV4-Pro is **closed as a quality gamble** (`#78`); the compute set is **fixed at six GB10 nodes** (`#79`); Mistral-Large-4 **moved to `attic/`** (`#80`); `FLUX.2-dev` and `flux-3-image-klein` licences **accepted**, `dinov3` **declined** (`#81`); and `OOMScoreAdjust=-900` **may** also go on `user@1000.service` (`#83`) |
| settled | **51** — `#1`, `#4`, `#5`, `#8`–`#16` moved verbatim to `TODO.md` §"Settled questions" on 2026-10-23, `#19` joined them **answered 2026-10-24** (the Community license), `#20` (**executed**: the HF cache is entirely on the pool) and `#17` (**authorized**, pending the seccomp route) joined them the same day, `#2` joined **2026-10-24** (the 16384 prefill chunk, measured and shipped), and `#3`, `#7` and `#21` joined them **2026-10-24** (answered via the one-time owner questionnaire and folded per the protocol); `#18` joined them **2026-10-29** (superseded — fixed by `kho=off` fleet-wide), `#54` + `#56` joined them **2026-11-02** (owner answers in session: the ghcr push had already landed, so `#54`'s grant was moot; the LFM arms ship as ordinary arms, no eval-only banner), `#6` + `#53` joined them **2026-11-03** (a phased `flare agent` install via the vendor APT repository, whose key's `apt upgrade` reach the owner accepted; DeepGEMM's SM121 kernels patched in-house rather than tracked upstream), `#57`–`#66` joined them **2026-11-06** — a ten-question round asked and answered in one session because this register was empty while ten queue rows sat `blocked`; `#67` (host memory policy on all six nodes, **with a dated correction: its earlyoom numbers were superseded by measurement the same afternoon**) + `#68` (instrumented vs uninstrumented baseline) joined them **2026-11-08**; and `#69`–`#81` + `#83` joined them **2026-11-09** in one batch (§"unanswered" above). Numbering is stable, so a citation such as `QUESTIONS.md #9` still resolves. The 2026-11-11 survey round answered nine unnumbered survey rows (`S1`–`S9`), and `#84` joined them **2026-11-11** (the ERNIE licence class: a production arm is permitted, subject to the licence's attribution and one-time use notice, with the ship call left to measured performance), so this count is **51** |
| blocks the most downstream work | **`#86`** — the Hy4 Flash licence class is the only thing between that quartet arm and a promotion out of `zz-`; `#87` (the Edge0 class) gates the same promotion for the single-node probe and nothing more, and `#85` blocks nothing downstream (it is authorization and register hygiene). `#84`, the previous open row, was answered on 2026-11-11. The blocked set is otherwise ordinary queue state now: the TP≤2 rows wait on the production return the 2026-11-11 directive names, the SM121 trio waits on `sm121-marlin-oom-diagnosis` (`#70`), the `.30`-root-target question is moot with the hub left as it is (`#74`), and the FLARE work moved into `flare-agent-rollout` as its phase-2 scope (`#76`, `#77`). Two rows now exist only to turn an answer into a receipt: `host-memory-policy-apply` (the `OOMScoreAdjust` drop-ins on `ssh.service`, `NetworkManager.service` and `user@1000.service`, `#72`/`#83`) and `cache-audit-pool-budget` (the tool must measure the pool, not the node, `#75`) |

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

- **#86 — Which licence class does `tencent/Hy4-flash` get under the Tencent Hy License 1.0: ship its quartet
  arm as a normal explore arm, ship it probe-only, or not ship at all?** — `open` — the licence is
  Apache-2.0 with section 10 added, and the file says so in its own preamble: *"This License is derived
  from the Apache License, Version 2.0 … with modifications, mainly the additional commercial terms for
  large Model-as-a-Service ("MaaS") businesses in Section 10. This License is not the Apache License,
  Version 2.0, and is not endorsed by or affiliated with the Apache Software Foundation."* Four clauses
  carry the exposure. **§10.2** — *"if You operate a MaaS business, You must obtain a separate written
  license to use the Work or any Derivative Works from Licensor (including by email), in either of the
  following cases: (a) if Your aggregate worldwide gross revenue exceeds US$50 million (or the equivalent
  in other currencies) in any consecutive 12-month period, whether or not such revenue is derived from the
  Work or any Derivative Works, before using (or continuing to use) the Work or any Derivative Works; or
  (b) before using the Work or any Derivative Works in or for any product or service provided by You that
  has more than 100 million monthly active users in any calendar month."* **§10.1** defines the trigger as
  *"giving third parties remote access to model inference or fine-tuning (e.g., via API), allowing them to
  submit inputs or specify parameters or training data"*, excluding end-user products whose model
  capabilities are confined to specific features or workflows and mere relaying to an independently
  operated third-party service. **§10.3** — *"Section 10.2 does not apply to Your use of the Work or any
  Derivative Works solely for internal purposes, provided that neither the Work, any Derivative Works, nor
  their outputs are made available to third parties."* **§6** withholds the marks — *"This License does not
  grant permission to use the trade names, trademarks, service marks, or product names of the Licensor,
  except as required for reasonable and customary use in describing the origin of the Work and reproducing
  the content of the NOTICE file."* **§4(c)** keeps attribution on anything redistributed — *"You must
  retain, in the Source form of any Derivative Works that You distribute, all copyright, patent, trademark,
  and attribution notices from the Source form of the Work"* — and the Definitions put quantised bodies
  inside that term: *"For the avoidance of doubt, Derivative Works include any fine-tuned, quantized,
  distilled, merged, pruned, or otherwise modified versions of the model weights."* **Exposure today is
  nil:** no arm in this lane is sold, no serve is exposed, and the Hy4 arm
  (`recipes/explore/zz-hy4-flash-220b-bf16-thinking-tools-vllm.yaml`) is authored-not-booted, so §10.3
  covers the whole current state on its face. **The open part is narrow and it is the reason this is asked:**
  whether a serve reachable from the lab network only stays *"solely for internal purposes"* under §10.3, or
  becomes §10.1 MaaS because colleagues submit inputs through it — i.e. whether the test is who can reach the
  port or whether anyone pays. Answer it against the `#84` precedent (owner 2026-11-11: a production arm
  **permitted** for the ERNIE-5.5-Flash-Base licence, whose trigger was a revenue ceiling plus attribution
  and a one-time written notice, with those obligations carried rather than waived); this class adds the MAU
  prong and a trademark carve-out, so a ruling here may land the same way or differently without
  contradicting `#84`. provenance: `tencent/Hy4-flash` `LICENSE` (13,942 B; card `license: other`,
  `license_name: tencent-hy-license`, revision `b2498eba6a1a3f9bbcab4190bc1313a3c7010c2f`), clauses quoted
  verbatim from it; the arm's fit, engine and gate evidence in
  `recipes/explore/zz-hy4-flash-220b-bf16-thinking-tools-vllm.yaml` and the pending
  `recipes/explore/README.md` §"zz-hy4-flash-220b-bf16-thinking-tools-vllm"; `#84` settled in `TODO.md`
  §"Settled questions" under `## Owner answer 2026-11-11 — ERNIE licence class`; asked 2026-11-20.
- **#87 — Which licence class does `Edge0/Edge0-145B-NVFP4` get under the Edge0 Community Model License
  1.0, stacked over the Qwen Community License 1.0: research-only (stay `zz-`, never promoted), a
  promotable production arm, or not shipped at all?** — `open` — a new class, and the first on file
  whose grant is **stacked**: the model licence covers only Edge0's own contributions and the upstream
  Qwen licence still binds underneath. `LICENSE` §2 says it in its own words — *"Permission from Edge0
  is not permission from Qwen, and permission from Qwen is not permission from Edge0 for separately
  protected Edge0 Materials."* — and `NOTICE` repeats it: *"The Edge0 license does not replace them.
  Required Qwen commercial permission must come from Qwen or a party authorized by Qwen."* **§3 grants
  the surface this lane actually uses:** *"Subject to Sections 2, 4, and 5, Edge0 grants You a
  worldwide, non-exclusive, no-charge, royalty-free copyright license to use, run, study, reproduce,
  modify, fine-tune, quantize, prune, convert, merge, evaluate, publish, and redistribute Edge0
  Materials"*, naming *"(b) research, education, teaching, benchmarking, and publication of findings"*
  and *"(d) internal organizational use, including use by businesses, when You are not making a
  Commercial Model Offering"*, and adding *"Edge0 does not require … prior approval for research or
  benchmarking."* **§4 reserves the commercial surface:** *"You must obtain a separate written
  commercial license from Edge0 before making any of the following Commercial Model Offerings: …
  (b) Commercial model services: operating a service for third parties that offers language-model
  inference or fine-tuning as a capability in its own right, through an API, hosted endpoint, hosted
  general-purpose model interface, or equivalent arrangement, and that is financed by access or usage
  fees, a subscription, advertising, or sponsorship tied to that service … (c) Commercial independent
  coding or office assistants: offering an independent product primarily designed for AI-assisted
  coding or office productivity that uses a Covered Model and is financed by sales, access or usage
  fees, subscriptions, advertising, or sponsorship tied to the product."* **§5** keeps the
  redistribution duty — *"include this License and all applicable upstream license texts and notices"*,
  *"(c) identify Your material modifications and the responsible modifier"* — and **§10** disclaims
  what the file does not certify: *"It does not certify that a release contains protectable new
  rights, that Edge0 has obtained a separate Qwen commercial license, or that every contemplated
  activity is permitted by an upstream rights holder."* **Exposure today is nil:** nothing is sold, no
  serve is exposed, and the arm (`recipes/explore/zz-edge0-145b-nvfp4-latentmoe-strata.yaml`) is
  authored-not-booted, so §3 covers the whole current state on its face. **Two parts of this are not
  the revenue test this register has answered before.** (i) §4(b)/(c) are *activity* reservations, not
  ceilings — unlike `#84`'s US$50M line or `#86`'s MaaS/MAU prongs, no revenue figure makes them stop
  applying, so the ruling is about what the fleet may *become*, not what it earns. (ii) The upstream
  provenance is unverified by the publisher's own record: `release-scope.json` carries
  `actual_training_base_revision_verified: false` and `actual_training_or_conversion_base_revision:
  null` with *"No training-source commit or independent ownership audit is asserted"*, and `NOTICE`
  says the Qwen reference revision *"is not a representation of the training or conversion revision
  used to create the Edge0 models"* — a question about **which** Qwen terms bind, not about Edge0's
  grant. Answer it against `#84` (owner 2026-11-11: a production arm **permitted**, obligations carried
  rather than waived) and beside `#86` (the Hy4 MaaS class, open); the three differ in kind — a revenue
  ceiling, a MaaS/MAU trigger, and an activity reservation under a stacked upstream grant. provenance:
  `Edge0/Edge0-145B-NVFP4` `LICENSE` (13,059 B), `NOTICE` (2,560 B), `release-scope.json` and
  `third-party/Qwen-LICENSE.txt` at revision `17bb271c…`, clauses quoted verbatim from them; the arm's
  engine and fit evidence in `recipes/explore/zz-edge0-145b-nvfp4-latentmoe-strata.yaml` and
  `recipes/explore/README.md` §"zz-edge0-145b-nvfp4-latentmoe-strata"; `#84` settled in `TODO.md`
  §"Settled questions" under `## Owner answer 2026-11-11 — ERNIE licence class`; asked 2026-11-20.

`#84` (the ERNIE licence class) was answered 2026-11-11 and is settled in `TODO.md` §"Settled questions"
under `## Owner answer 2026-11-11 — ERNIE licence class`; the earlier batch (`#69`–`#83`, 2026-11-09) and the
2026-11-11 survey round are settled there too.

## Priority & close-out

No open rows. The last batch (`#69`–`#83`, 2026-11-09) is settled in `TODO.md` §"Settled questions".
