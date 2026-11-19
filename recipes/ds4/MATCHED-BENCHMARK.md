# Matched head-to-head: picom and SGLang on the same four GB10 ranks

This page is a protocol, not a result. [PICOM-VS-KNAPCIO.md](PICOM-VS-KNAPCIO.md)
compares the two shipped arms on cells measured in different boots; its own "what to
change" item is cell-level interleaving. This is the window that would do it: the two
arms, four boots, one instrument, one declared set of cells, and an admission rule that
says in advance which numbers may be quoted and which may not.

The protocol is in force, and part of it has run since. Measured with receipts: the
four-boot paired window and the five-boot tuning window under
`head:~/benchmarks/picom-prod-20261118/` (`paired-20261118/`, `picom-tuning-20261118/`),
and the full BFCL leg under `head:~/benchmarks/fabric-lossless-20261118/`. Unmeasured:
the two-boots-per-arm cross-arm delta, the 40,000-token grant and shared-prefix caching
cells, and the long-context fan-out. Every flag named is in the recipe or launcher it names
(`file:line`); every number quoted as a bound comes from a receipt under
`head:~/benchmarks/picom-prod-20261118/` (the production window) or
`head:~/benchmarks/picom-gap-20261117/` (the upstream `bench.py` cells).

Arms: **P** = `deepseek-v4.1-flash-1017-picom-tp4-1m.yaml` (exact picom),
**S** = `deepseek-v4.1-flash-knapcio-tp4-1m-sglang.yaml`.
## 1. Decision table

| axis | picom | SGLang | equal? | reported as |
|:--|:--|:--|:--|:--|
| Admission | 16 slots, 4 big | 16 uniform | count only | pinned at 16; every cell ≤131,072 ctx |
| Spec decode | DSpark, 5 drafts | DSpark, k=5 | shipped arms yes | C1/C2/C5 ranked; C10 mixed |
| Prefill chunk | 16384 rows | 16384 tokens | yes, equal | one ranked number, no change |
| Output ceiling | 262,144 | 262,144 | yes, equal | pinned, verified before the window |
| Prefix cache | text prefix, cold | radix, hits | no | cache-defeating default + 1 shared cell |
| Weights | `.dsw` + NVMe Engram | native MXFP4 | no | same-bytes claim, bounded by text identity |
| Instrument | one ladder profile | same | yes | decode record only, ≥5 runs/cell |
| Ordering | boots 1 and 4 | boots 2 and 3 | yes | delta needs both boots on one side |

### Admission topology

picom is `--slots 16 --big-slots 4` (P `:64`); the 12 small slots hold `max_ctx / 8` =
131,072 each and the 4 big ones hold the full 1,048,576. SGLang is 16 uniform slots,
`MAX_RUNNING_REQUESTS` `16` (launcher.py:167), with the pool profiled at **5.82–5.91 M
tokens** across two boots once the 262,144 ceiling is reserved
(`head:~/benchmarks/picom-prod-20261118/knapcio-256k/`), so `16 × 262,144 = 4.19 M`
still fits.
Equal in **count** only, and that is what the protocol pins: **16 concurrent requests is
the ceiling of every claim**, and **every cell keeps `prompt + max_new` ≤ 131,072** so
picom's 12 small slots stay eligible. Above that the two machines differ in kind — at the
262,144 cap SGLang admits 16 requests and picom 4 — and that is reported as structure,
never as a rate.
### Speculative decoding

Both shipped arms draft 5 tokens: picom `DSGB10_DRAFT1=6` rows including the bonus
(P `:66`) with `--draft-head4 --draft-markov8` (P `:68`); SGLang `SPEC_ALGO` DSPARK
(launcher.py:219), `DSPARK_BLOCK_SIZE` `5` (launcher.py:240) and the recipe's
`dspark_block_size: 5` (S `:78`).

**No no-spec control arm.** picom's engine argv is one overridable env string
(`PICOM_ENGINE_ARGS`, read at launch.sh:190), so its drafts could be dropped; SGLang's
argv is built inside the image's own `boot.py` and has no launcher-level knob for it —
`SPEC_ALGO` is neither in `SGLANG_EXTRA_FLAGS` (launcher.py:452-470) nor in `AB_ENV`
(launcher.py:384-386). An asymmetric control cannot bound a symmetric difference, so the
protocol instead **restricts the ranked decode claim to C1/C2/C5**, where both engines
draft, and prints C10 with its mechanism on the label: SGLang's DSpark against picom's
plain loop, which engages above batch 8.

If a later window wants the control, it is a **real second recipe per side**, not an `-o`
override, and it must gate on a boot line proving drafting is off — silently dropping an
unknown argv token is this launcher's documented failure mode (P `:59-60`).
### Prefill chunking

Equal already: picom `--prefill-rows 16384` (P `:70`), SGLang `CHUNKED_PREFILL_SIZE`
`16384` (launcher.py:178). Nothing in the grid exercises more than one chunk except the
long-context cells: the ladder's `pp 2048` is one chunk on both, a 131,072 prompt is 8,
and the 983,040 needle is 60. No chunk-size experiment belongs in this window.
### Output ceiling

Pinned at 262,144 on both sides: `PICOM_MAX_TOKENS: "262144"` (P `:82`) reaching dsfront
as `--max-tokens` (launch.sh:311,324), and `DSV41_MAX_NEW_TOKENS: "262144"` (S `:68`).
SGLang's engine reaches the cap — a `max_tokens` 262144 `ignore_eos` request returned
`completion_tokens` 262,144 with `finish_reason: length` in 1,805.8 s
(`head:~/benchmarks/picom-prod-20261118/knapcio-256k/`) — but only with its loop guard
off, so a full-262k reply under the shipped configuration is **not** demonstrated
(PICOM-VS-KNAPCIO.md §3). The protocol never asks for one. The pre-window gate is the
**boot line naming the cap**, and the grant cell is the **40,000-token draw**: its
`completion_tokens` and `finish_reason` are recorded on both arms and reported as they
land — a `stop` short of 40000 is the loop guard ending a repetitive draw, which is a
finding about the guard, not a ceiling failure, and no cell is voided by it.
### Prefix caching

Not equalizable. SGLang runs a radix cache with `--enable-cache-report`
(launcher.py:268,464-468) and the ladder profile asks for `prefix_caching: true`
(benchmarking/concurrency-ladder.yaml:16); picom matched on shared *text* prefix with a
64-byte minimum and logged `reused 0 (cold)` on all 88 of the `picom-ladder-20261117`
2048-token requests, so the same profile flag is not the same behavior.

Decision: the **default comparison cell is cache-defeating** (section 4), and **one
shared-prefix cell per arm boot** carries the difference. The ladder's decode rows stay
comparable; its `e2e_ttft` column is reported, never ranked, because on SGLang it may be
served warm from run 2 onward.
### Weight representation

Structurally different and staying that way: picom converts each rank once to a 72.38 GiB
`.dsw` and packs 50.7 GB of Engram on that rank's SSD (launch.sh:27-31); SGLang serves the
native MXFP4 checkpoint with its Engram re-packed on NVMe. Both pins are the same
checkpoint revision `08c8657f…` (P `:9`, S `:18`), so "same model" means **same checkpoint
bytes, different on-disk representation**. What bounds the claim is text identity, not
layout: the fixed greedy 48-token prompt, `house` 37/37 on both, needle PASS at 983,040
on both. A per-token cost difference caused by `.dsw` layout or NVMe Engram reads stays
inside the reported delta and is named in the finding.
## 2. The exact boot plan

Four boots, order **P, S, S, P** on ranks `.31`–`.34`: two boots per arm, the second pair
in reverse order so a monotone drift inside the window lands on both arms instead of on
whichever engine booted first.

| boot | arm | order | cells |
|:--:|:--|:--:|:--|
| P1 | picom exact | 1st | warm-up, ladder, shared-prefix, 40k grant, house, needle |
| S1 | SGLang | 2nd | warm-up, ladder, shared-prefix, 40k grant, house, needle |
| S2 | SGLang | 3rd | warm-up, ladder |
| P2 | picom exact | 4th | warm-up, ladder |

Per boot: readiness gate → watchdog armed → warm-up → ladder → remaining cells →
teardown to 0 containers, 0 volumes and no `:8000` → `post-teardown.txt`.

Boot cost is asymmetric and is not a metric: picom reached HTTP-ready in 25.2–26.5 s on
all four `paired-20261118` boots, SGLang in 687.8–721.9 s. Budget **about an hour**: 2 ×
(26 s + 700 s) of boot, 4 × ~2 min of ladder (`E2/ladder.log` 19:05:17Z → 19:07:06Z;
`K2/ladder.log` 18:53:34Z → 18:55:54Z), plus the identity cells on each arm's first boot.

Out of the grid, and why:

- **No `PICOM_OEA` arm.** `deepseek-v4.1-flash-1017-picom-tp4-1m-oea.yaml` is a different
  model construction (lossy MoE re-route, OEA `4,12,9`); it cannot appear in an
  apples-to-apples window.
- **No `-o` overrides.** The four boots run the recipes as shipped, so nothing depends on
  an override reaching the engine (benchmarking/README.md rule 8). The single exception is
  `-o env.PICOM_RANK_TAILS=31,32,33,34`, which the recipe requires on P (P `:50`).
- **No full BFCL leg.** The scoped 100-question leg already reads 87/100 both and
  separates nothing; the full leg runs outside this window (section 8) rather than in it.
## 3. One instrument

The decode instrument is **`benchmarking/concurrency-ladder.yaml`**, unmodified:
llama-benchy, depth 0, `pp` 2048, `tg` 128, `concurrency` 1/2/5/10, `runs` 5,
`prefix_caching: true`. The same profile file on both arms gives identical prompts, one
`tg` budget, one sampling path, non-streaming requests, and five runs per cell with no new
script to keep in sync.

```bash
HOME="$H" sparkrun benchmark performance <recipe> -H <api-rank> \
  --profile benchmarking/concurrency-ladder.yaml --skip-run --fresh \
  --output ~/benchmarks/h2h-<window>/<boot>/ladder-<boot>.yaml
```

Reading rules, all load-bearing:

1. **Decode record only.** Each cell emits two records that both carry `tg_throughput`
   (benchmarking/README.md rule 4); only the decode record is ranked, with
   `is_context_prefill_phase: true` filtered out. `e2e_ttft` is kept beside it, unranked.
2. **Warm-up is one discarded `distinct 16` invocation** of the upstream `bench.py`
   (sha256 `4aff8517…b97967`, `picom-gap-20261117/bench.py`) on the fresh serve, then the
   ladder. The warm-up builds the graphs and is never a cell.
3. **C10 carries a label**, per section 1: drafting against a plain loop.
4. **A replayed table is not a measurement.** Without `--fresh`, sparkrun re-emits the last
   result for the same (profile, recipe, hosts) and exits 0 — exactly how `L2`'s first
   attempt printed the archived phase-6 table and wrote no file
   (`paired-20261118/L2/ladder.log`). All three checks are required: the `--output` file
   exists and is newer than this boot's readiness; the log has no `re-emitting` line; the
   printed table matches the file's rows.
## 4. The two caching cells

Default comparison cell — **cache-defeating**. `bench.py` puts a random eight-decimal
prefix on every prompt by construction (bench.py:43), and picom matched nothing in the
production window. Client rule: a request prefix carries at least 64 random bytes
(picom's matching minimum) and no two requests inside a cell share it.

One **shared-prefix** cell per arm's first boot, where the difference is the finding:
non-streaming, temperature 0, three requests, prompt+reply inside 131,072.

| request | prefix | evidence collected |
|:--|:--|:--|
| 1 | A, first use on this boot | TTFT, `cached_tokens` |
| 2 | A, verbatim | TTFT, `cached_tokens` |
| 3 | B, never seen | TTFT, `cached_tokens` |

The cell is **void** ("no hit observed") unless request 2 shows a hit on at least one
engine: SGLang's `prompt_tokens_details.cached_tokens` above 0, or picom's rank-0 engine
log carrying `reused <n>` for that prompt. Picom's `cached_tokens` is always 0 — the log
counter, not the response field, decides. The number reported is TTFT(2)/TTFT(1), and
request 3 proves the boot had not gone warm globally.
## 5. Acceptance criteria

A cell enters the report only when every row holds. A failing row drops the **cell**; two
dropped cells drop the **boot**; a dropped boot drops the arm's pair and the window is
re-run rather than repaired.

| check | rule | evidence |
|:--|:--|:--|
| fresh | `--fresh`, output file newer than readiness, no `re-emitting` | `ladder.log`, mtime |
| record | decode-phase rows only | `ladder.yaml` flag |
| spread | within-cell CV ≤ 10 % on every tg row | `t_s_std / t_s_mean` |
| pollution | `polluted_runs` 0, `harness_timeouts` 0 | `summary.json` |
| transport | transport errors 0 in any tool cell | cell report |
| watchdog | `ranks=4 unprobeable=0` on every probe, no `no_probe` | `watchdog-<id>.log` |
| teardown | 0 containers, 0 volumes, no `:8000` | `post-teardown.txt` |
| ceiling | boot line names 262,144; grant `.json` recorded | `launch.log` |
| coldness | picom log shows no prefix hit on default cells | `rank.0.log` |
| identity | fixed 48-token prompt identical text, house 37/37 | cell `.json` |

Observed spreads to judge the bound by: the paired window's ladder CVs ran 1.7–9.2 % on
nine of twelve tg rows, and `L2`'s C1 at 20.8 % is the kind of cell this rule rejects.

The coldness row is one command on the rank-0 engine log of each picom boot:

```bash
grep "prompt 2048" /cache/runtime/picom/logs/rank.0.log | grep -vc "reused 0 "
```

It must print 0. A non-zero line means the ladder measured a warm prefix and the decode
rows are not cache-free.

## 6. Ordering, drift, and what invalidates a delta

Two boots per arm, order `P, S, S, P`. A cross-arm delta is quoted only when both boots of
one arm lie on the same side of both boots of the other, and the smallest gap between the
arms' per-boot numbers exceeds the larger of that arm's own boot-to-boot drift and
**10 %** — above the best observed same-arm reproduction, inside the documented 7–25 %
inter-boot floor (benchmarking/README.md, "Noise").

Same-arm cross-boot drift to judge against, from the ladder receipts: exact picom C1 83.4
(`phase5`) against 77.3 (`E2`) = **7.3 %**; lossy 87.1 against 91.3 = **4.6 %**; knapcio
64.8 (`rerun-20261118/boot1-knapcio`) against 66.9 (`K2`) = **3.2 %**.

Invalidators, stated in advance:

- **Order effect.** If an arm's two boots differ by more than the claimed delta, order
  confounds it and the cell carries no claim.
- **Window drift.** If the cold `e2e_ttft` cells or the 40k grant's tok/s move
  monotonically across the four boots — the kind that read 190 → 236 → 436 s of TTR on
  2026-10-26 — the window is reported as drifted and no cross-arm delta is quoted.
- **One-sided reproduction.** One boot per arm reproduces nothing; the claim level here is
  "repeated, order-reversed pair", and a single boot is reported as a shape.
- **A reboot inside the window** changes page-cache and clock state; it voids the pair
  unless both arms boot after it.
## 7. Pre-window checklist (five minutes, no boots)

| # | check | evidence |
|:--|:--|:--|
| 1 | both digests pull anonymously (P`:13`, S`:20`) | `manifest inspect` |
| 2 | checkpoint `08c8657f…` complete on `.31`–`.34` | snapshot dir, each rank |
| 3 | picom artifacts cached: `rank<N>.dsw`, Engram `.ok` | `/cache/runtime/picom/` |
| 4 | ceiling in a boot log: `max_tokens 262144`, `caps at 262144` | last `launch.log` |
| 5 | 40k grant recorded (count, `finish_reason`) | one request, ~3.5 min |
| 6 | instrument pinned: the ladder profile, `bench.py` `4aff8517…` | `sha256sum` |
| 7 | fixtures present: house, needle, agentic | `tools/README.md` |
| 8 | lease and lock written for the window | `.local/*.json`, `*.lock` |
| 9 | nodes quiet: no sparkrun containers on `.31`–`.34` | `docker ps -aq` |
| 10 | environment recorded per boot: clocks, temp, `MemAvailable`, `uptime` | boot dir |

No application-clock lock is used by any receipt on this lane; item 10 is the record that
makes two boots comparable after the fact, and a pair whose recorded clocks or
temperatures disagree is reported with that caveat.
## 8. What this protocol still cannot settle

- **Why a decode cell moves.** No no-spec control exists on SGLang's side and no receipt
  on either side decomposes a step into draft, verify and collective time. A margin is a
  margin; the mechanism stays INFERRED.
- **Long context at concurrency.** Above 131,072 tokens picom's 12 small slots are out, so
  a 16-way long-context cell is a different machine. Max-budget fan-out — 16 requests on
  SGLang against 4 on picom at the 262,144 cap — is unmeasured and named as structure.
- **The weight representation.** `.dsw` plus NVMe Engram against native MXFP4 cannot be
  equalized; the identity cells bound the output, not the cost of reaching it.
- **Steady-state cache value.** The shared-prefix cell measures a second request's TTFT,
  not a long session's reuse pattern, and the ranked decode rows are cache-free by the
  time they are counted.
- **Power, thermal and fabric state.** The switch statically enables PFC on traffic class 3,
  but every host port classifies its RoCE traffic to tc1, so no priority pause, CNP or tc3
  packet has moved; picom's QP `hop_limit` still has no readable surface, and no rank's power
  is captured. Two engines cannot serve one four-rank set at once, so there is no cell-level
  interleaving either — only boot alternation.
- **Quality beyond identity.** The scoped BFCL leg separated nothing at 87/100 both; the full
  1,240-question leg reads E 1,094 / L 1,094 / K 1,092 with `transport_errors` 0
  (`head:~/benchmarks/fabric-lossless-20261118/{E1,L1,K1}/bfcl_*.json`), so tool calling is
  measured outside this window, and no cell here scores free-form code or prose.
