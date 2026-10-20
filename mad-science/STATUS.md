# Session status — 2026-10-20 12:40 ET

The test pair is on **Laguna-M.1 TP=2**: booted 07:10, `/v1/models` 200 at 07:53:48, house, needle and
hard legs landed, tools leg at **956/1,240 questions (9.3 s/question)** with ≈45 min left. The
production quartet is untouched (its own TP=4 serve, healthy). Gate: **752 tests OK** (2 skipped),
**51/51** recipes pass plain `sparkrun recipe validate`. Last commit `fc28b9e`.

## Table 1 — Current tasks (in flight)

| Task | Machine role | Elapsed | Landed | Remaining |
|---|---|---:|---|---:|
| **Laguna-M.1 TP=2 standard suite** (225B/23B-active, vLLM 0.29.0) | test pair | 5 h 26 | boot TTR ≈43 min (129.75 GiB download, 259.51 GiB distributed, TP=2 load) · house **37/37** · needle **3/3 at 32k, 131k, 262k** · **GSM8K 188/200 (94.0 %)** · **ARC 178/200 (89.0 %)**, 0 empty · tools **956/1,240** (554 pass / 402 fail) | **≈0.75 h** of tools, then the ladder on the same boot |

Two readings from that tools leg, to be confirmed against its JSON at completion: the pass count froze
at 554 while failures climbed past 400 — the leg has entered the `parallel` and `parallel_multiple`
categories and every one of those fails `wrong_count`, the same one-call-where-several-are-asked shape
the smaller Laguna-XS arm showed. That is a capability reading, not a parser one (Laguna-XS's records
carried a single `calls` entry with the prose naming both requests).

## Table 2 — Remaining tasks (queued and runnable now)

| Bucket | Content | Wall | Notes |
|---|---:|---:|---|
| Suite tail — single-node | **0 h — closed** | 0 h | every single-node arm now has a boot, a ladder and a suite receipt; the qwen3 MLX top rung is TRUNCATED at its real ~222.5k window and the ornith YaRN d90 rung passed |
| Other local — single-node | 12–20 h | ~6–10 h | media-gen 2–3 · decision Nox-4B/JEV-27B 3–5 · reasoning candidates 1–3 · ornith 0.5.21 bump + revalidation 6–9 |
| Pair-bound | 18–30 h | 18–30 h | cybersec arm 5 3–5 · ds4 TensorFold v0.6 3–5 · flash-next b12x 3–6 · ds4 `reasoning_effort` 1–2 · qwen4 highcon + 1 probe 8–12 (highcon is also the boot that retires the restored diagnostic mod) |
| Sol-2B `sparkrun run` boot proof | 0.2–0.3 h | 0.2–0.3 h | needs one free node; the render is verified line-for-line against the measured boot, then re-score with the decision instrument |

## Table 3 — Deferred tasks (not runnable without an owner action or a triggering event)

| Deferred | Unblocked by | Where it lives |
|---|---|---|
| **Offsite TP=4 measurement block** (20–28 h: qwen4 W6/W12, ds4 TP=4 candidates, four-node suite legs) | the owner switching the session to an offsite endpoint; the gate that held it (the local tail) is now met | register under the qwen4/ds4 items; ask repeated below |
| **Ornith intermittent 1M serve exit** (1–2 h) | a failing boot with the capture armed — 2 of 2 d90 passes since the two 2026-10-18 exits, and the capture has produced a null result twice | `~/benchmarks/ornith-yarn-d90-20261020/` + the register item that stays open for the next failure |
| **GLM ≥1M probe** — *dropped, not deferred* | nothing; the owner's policy closed it | lane attic, recorded as dropped |
| **Ornith 397B retry** — *dropped, not deferred* | nothing; the owner's policy closed it | lane attic, recorded as dropped |

## Totals

| Bucket | Range |
|---|---:|
| In flight (Laguna tools remainder + its ladder) | 2.5–3 h |
| Queued node-bound content, runnable now (Table 2) | 30–50 h |
| **Node-bound wall at two lanes** | **≈24–40 h** |
| Deferred (Table 3, owner action or event) | 21–30 h |
| **Grand total including deferred** | **≈54–83 h** |

## Risks

- **BFCL is not resumable** and it is the leg running now: the per-question records exist only at
  completion, so an interruption costs the remaining ≈0.75 h whole. The per-check cap has ≈1.3× headroom.
- **Buffered logs look like stalls.** Every long leg tonight has shown a question count frozen for tens
  of minutes while the serve decoded; liveness comes from the serve log, never from the count alone.
- **Pair-bound stall**: the 18–30 h pair block holds both test nodes; nothing single-node runs during it.
- **Tracked-file addresses are an open hygiene item** — a history-wide audit found internal addresses in
  tracked lane docs and benchmark harness files (counts in the register). Not yet sanitized.

## Closed this session

27B-NEXTN suite + ladder (`bench_e66cbef09760`: 15.39 / 28.81 / 60.35 / 102.82 t/s) · 27B-uncensored
tools **1072/1240 (86.5 %)** · kolibri APEX five legs `ok`, needle a real 262k pass · laguna-XS 59.8 %
tools, triaged as capability not parser · qwen3 MLX needle TRUNCATED at ~222.5k · ornith YaRN d90 PASS
with a null die-capture · Sol-2B built, published and scored **55.0 % (1101/2000)** at p50 195 ms ·
qwen4 `zz-labq-no-diag` passed, retiring the diagnostic on the balanced arm (restored in highcon only) ·
27B-NEXTN and arm-1 lane-doc blocks.

## Open ask

**TP=4 offsite switch** — the condition that gated it is met (the single-node tail is closed). Options:
switch **now** (20–28 h of TP=4 work becomes runnable while the test pair keeps working), switch **after
the pair-bound block**, or **park** it. Nothing is blocked either way.