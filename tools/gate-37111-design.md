# `gate-37111.py` — design memo (W4 / `recipes/qwen4`)

**Purpose.** Explain what the gate in `tools/gate-37111.py` detects, the toggle
ladder that would localise the two upstream correctness bugs, why each
discriminator can falsify a hypothesis, and what a PASS does *not* prove.
Upstream state below was read **2026-10-04** from the GitHub API/HTML.

## 1. The claimed failure mode (WORK §14)

WORK doc §14, *"Correctness risks that outrank every throughput knob"* (`LIKELY`
as to root cause, `VERIFIED` as to the issues existing):

- **#37111** — "QSA plus NEXTN decode graphs **silently corrupt output** on GB10
  TP2". The reporter's own A/B: eager passes, decode-graph emits repeated
  punctuation (`!`) and fails 25k-token marker retrieval, **same 200 OK, higher
  tok/s**. Byte-identical claim in the tool's `UPSTREAM` block.
- **#38319** — "Chunked Prefill + Radix Insert race corrupts KV pages (QSA)":
  a retract frees KV pages a radix node still references, so every request that
  shares the corrupted prefix decodes an impossible token (`248319`) forever —
  the `!!!!` loop. §14's summary: "degenerate repeated-character loops after 1 to
  2 hours".

Both are silent: "a config that is 10% faster and occasionally emits garbage is
a regression."

## 2. Upstream status — VERIFIED 2026-10-04 (do not re-derive from memory)

| ref | title (verbatim) | state read 2026-10-04 | opened | last updated |
|---|---|---|---|---|
| [issue #37111](https://github.com/sgl-project/sglang/issues/37111) | "[Bug] Qwen3.8-Flash-Next QSA + NEXTN decode graph silently corrupts output on GB10 TP2" | **OPEN** | 2026-08-30 | 2026-08-31 |
| [issue #38319](https://github.com/sgl-project/sglang/issues/38319) | "[Bug] Chunked Prefill + Radix Insert race corrupts KV pages (QSA, Qwen3.8-Flash-Next)" | **OPEN** (assigned `alphabetc1`) | 2026-09-07 | 2026-09-11 |
| [PR #38355](https://github.com/sgl-project/sglang/pull/38355) | "fix(mem_cache): eliminate chunked-prefill radix-insert race corrupting QSA KV pages (#38319)" | **OPEN, unmerged** — base branch `qwen4-main-squashed`, 1 commit `af27224`; closed 09-14 by a maintainer, then **reopened 09-14** | 2026-09-07 | 2026-09-14 |
| [PR #37110](https://github.com/sgl-project/sglang/pull/37110) | "fix(qsa): support EAGLE draft-extend row bounds" | **OPEN, unmerged**, same side-branch base | 2026-08-30 | 2026-09-14 |

Source: `api.github.com/repos/sgl-project/sglang/{issues,pulls}/<n>` (`value.state`),
read 2026-10-04. Notable: both issues have **zero linked merged PRs** and neither
has been revalidated on current `main` (both reporters say so explicitly).

## 3. The discriminator — why warm-vs-cold falsifies the hypothesis

#38319's mechanism is a **prefix-specific, persistent** corruption: `flush_cache`
fixes it "temporarily … re-appears at the same prefix once re-triggered." That is
the bug's own fingerprint, and it is directly testable without reading a log:

- Ask a fixed canary with the long shared system prompt **already resident** in
  the radix tree (warm), then again after emptying the cache (`/flush_cache`, or a
  salted fresh session if that endpoint 404s).
- **Agreement** ⇒ the shared prefix is not being served differently warm vs cold
  ⇒ #38319's signature is absent on this path.
- **Disagreement** ⇒ the cached prefix changed the answer with `temperature=0` ⇒
  prefix corruption is live. This is the tool's primary discriminator.

The canary also carries a known answer (`47*89=4183`), so a wrong reply is a
corruption signal even if warm and cold happen to *agree* on the wrong value
(which is exactly what a persistently-corrupted prefix would do).

## 4. The toggle ladder (localise before patching — §14 step 3)

Flags below VERIFIED present in the shipped recipes / WORK §5/§12/§14:

| rung | change | isolates | falsifier |
|---|---|---|---|
| R0 | ship as-is (labquant: `--cuda-graph-backend-prefill disabled` mandatory, §7f) | baseline | — |
| R1 | `--disable-radix-cache` (§14; decisive, not shippable) | prefix reuse **vs** kernels | corruption survives with radix off ⇒ **not** #38319 |
| R2 | gate the in-tree fix `mods/fix-sglang-radix-chunked-insert` (`SGLANG_DISABLE_CHUNKED_RADIX_INSERT=1` on, `=0` stock) | is the #38355 port sufficient? | stock-vs-fix flips a FAIL ⇒ #38319 confirmed and mitigated |
| R3 | `--disable-cuda-graph` (eager) vs the decode-graph profile | decode CUDA-graph capture (**#37111**) | eager clean + graph FAIL ⇒ #37111 |
| R4 | `--cuda-graph-bs-decode 1..10` + `--disable-cuda-graph-padding` (§14; note #37111 writes `--cuda-graph-max-bs-decode` — LIKELY same knob) | graph *shape* breadth | narrow capture passes while wide fails ⇒ shape-dependent |
| R5 | drop speculative: `zz-rk-nospec` / `zz-lq-nospec-matched` recipe arms | NEXTN/EAGLE involvement | clean without spec ⇒ NEXTN implicated (#37111 names it) |
| R6 | `--chunked-prefill-size` 4096→8192, `--enable-mixed-chunk` / `--enable-dynamic-chunking` (§14) | chunked-prefill insertion pattern | only one chunk shape corrupts ⇒ reportable minimal case (#38319) |

Boot each rung via `.scratch/q4/launch.sh` (one job at a time, §3.2) and run the
gate against **that** boot's endpoint. The gate is the detector; the ladder is how
a cluster operator turns a FAIL into a named cause.

## 5. What a PASS proves — and does not

- **Does not prove absence.** #37111 was observed once, "cross-boot frequency has
  not yet been measured"; #38319 is stochastic (chunk-insert vs retract timing)
  and appears at specific context sizes (33k, 145k). A green soak is a *negative
  result under the tested conditions*: one config, one depth, one duration. The
  default 1-minute soak is a smoke, **not** a release gate — §14 requires 1–2 h at
  ~100k depth for that.
- **Does not cover a different endpoint than the one passed.** The tool records
  `endpoint.model`; a report is only about that server.
- **Cannot see a cold-path-only bug** if `/flush_cache` is unavailable and the
  salted fallback is declined by the server (the report names `cold_method`).
- **`FAIL`** is actionable on its own: it means a real 200-with-garbage event, a
  mid-sentence stop, or a warm≠cold disagreement — all three outrank throughput.

## 6. Run it

```sh
python3 tools/gate-37111.py --selftest                      # offline, ~2 s
python3 tools/gate-37111.py --base-url http://<node>:8000 \
    --depth-tokens 100000 --duration-min 90 --json gate-37111.json
```

Exit `0` PASS · `1` unreachable · `2` bad flags · `3` corruption (or a partial
run too incomplete to certify).