# Board — 2026-10-22 02:01 ET

Six nodes all allocated; gate **876 tests OK**; CI is failing on GitHub and the TP=4 block is on W12 next after W6 died on an engine limit.

## Now

| where | what | since | state |
|---|---|---|---|
| `.30`–`.33` | TP=4 block — qwen4 W6 → W12 → ds4 TP=4 candidates → four-node suite legs, resumable | 2026-10-22 01:52 ET | W6 **failed** 01:55 ET on all four ranks (`modelopt_quant.py:2624`, gated-activation MoE padding); W12 next; no verdict |
| `.34` | stock llama.cpp build + Mellum MTP A/B | 2026-10-22 01:22 ET | allocated, no build receipt yet; Mellum MTP is NOT FEASIBLE on the shipped pin |
| `.35` | SGLang `v0.5.22` re-pin | 2026-10-22 01:34 ET | arm A in progress, progress not re-measured at this stamp; no verdict |
| repo/CI | CI gate + nightly pin sweep + weekly engine report | 2026-10-22 01:38 ET | landed and **running on GitHub, currently failing** — diagnosis in flight; sweep reads 12 gating rows and 8 holds |

## Attention

| what | why it matters | where it is tracked |
|---|---|---|
| Quartet's TP=4 production serve stays stopped (owner decision; stopped 00:38:39 ET) | `.30`–`.33` are measurement-only now; nothing restores production | `mad-science/TODO.md`, qwen4 and ds4 TP=4 items |
| vLLM `v0.32.0` moved thinking to `message.reasoning`, and `reasoning_tokens` reads 0 | any harness reading `reasoning_content` reports a false empty reply | `mad-science/TODO.md` explore item; `recipes/explore/README.md` |
| llama.cpp publisher stalled at `b10549-cu131` (2026-08-21) | every llama.cpp arm is ~2 months behind upstream, so Mellum MTP is unreachable | `recipes/explore/Dockerfile.llamacpp-upstream`; arm64 runner item in `mad-science/TODO.md` |
| TP=4 W6 dies in `modelopt_quant.py:2624` on every rank | TP=4 is an engine limit on this build, not memory and not the arm | `attic/qwen4/arms/qwen3.8-flash-next-labquant-tp4-sglang.yaml`; `recipes/qwen4/README.md`; `attic/qwen4/AGENTS.md` |
| CI workflows failing on GitHub | the failures page the owner and no fix has landed yet, so they need a human until then | diagnosis in flight; `.github/workflows/` |

## Gate

| suite | plain validate | strict validate | remote tip | measured at |
|---|---|---|---|---|
| **876 tests OK** (2 skipped) | **53/53**, 0 errors | **17/53 fail** | `26d5dcc` | 2026-10-22 02:01 ET suite, 01:58 ET validate |

## Recently landed

| time ET | commit | one clause |
|---|---|---|
| 01:55 | `e8d34fc` | W6 TP=4 hits an engine limit; knapcio ARC 93.5 % / GSM8K 97.5 %; W12 pins `cf5a2a53` |
| 01:46 | `f6cec8e` | sweep counts a digest-pinned `FROM` as current, 8 declared holds, gating rows 24 → 12 |
| 01:42 | `a6c0cd7` | `tools/refresh-sweep.py`, the survey CI gates on |
| 01:38 | `d8c1339` | CI gate, nightly pin sweep, weekly llama.cpp engine report |
| 01:36 | `5d767de` | qwen-image request path guarded; the shipped `NameError` named |

## Pointers

`mad-science/TODO.md` = the queue (work items and `# DECISIONS`). `mad-science/SESSION-RECORD.md` = dated history, including this day's full register. `recipes/<lane>/README.md` = per-arm evidence.
