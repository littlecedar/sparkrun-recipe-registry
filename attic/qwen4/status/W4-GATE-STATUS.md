# W4 — #37111 silent-decode-corruption gate: STATUS

**One page. State plainly what is done and what is blocked.**

## Verdict: DONE (code) · SMOKED live (main session, 2026-10-04) · BLOCKED (release-grade soak)

| deliverable | state | artifact |
|---|---|---|
| Correctness soak gate | **DONE / self-tested** | [`tools/gate-37111.py`](../../tools/gate-37111.py) |
| Design memo (failure mode, toggle ladder, PASS limits, upstream status) | **DONE** | [`tools/gate-37111-design.md`](../../tools/gate-37111-design.md) |
| Reduced live smoke on a real TP=2 boot | **DONE — PASS** (negative result) | `.scratch/q4/W4-gate-smoke.json` |
| Full 1–2 h @ ~100k release soak | **BLOCKED — needs the cluster** | — |

**Live smoke result (main session, 2026-10-04):** run against the RadixArk TP=2 boot on `.34/.35`
(`--duration-min 0.5 --turns 2 --max-tokens 256`), the gate printed `=== VERDICT: PASS ===` —
no degeneration, no truncation, and the warm/cold canary was **correct and equal** (`4183` both
ways, via the `flush_cache` route). **This is a negative result, not proof of absence:** the smoke
was short and unpadded. The 1–2 h / ~100k gate below is still owed, and per design memo §5 a PASS
there is also a negative result.

## Upstream status — VERIFIED 2026-10-04 (API `value.state`)

- [#37111](https://github.com/sgl-project/sglang/issues/37111) "QSA + NEXTN decode
  graph silently corrupts output on GB10 TP2" — **OPEN**, opened 2026-08-30,
  updated 2026-08-31, no linked PR.
- [#38319](https://github.com/sgl-project/sglang/issues/38319) "Chunked Prefill +
  Radix Insert race corrupts KV pages (QSA, Qwen3.8-Flash-Next)" — **OPEN**,
  opened 2026-09-07, updated 2026-09-11, assigned `alphabetc1`.
- [#38355](https://github.com/sgl-project/sglang/pull/38355) (its fix) — **OPEN,
  unmerged**, base `qwen4-main-squashed`, 1 commit `af27224`. This is the port
  already in-tree as `mods/fix-sglang-radix-chunked-insert` (§6 item 3).

Correction to the lane's notes: WORK §14 and `NOTES.md` say #37111 was "updated
2026-08-31" and #38319 "updated 2026-09-11" — both confirmed. `mods/fix-sglang-radix-chunked-insert/README.md`
calls #38355 "the **closed** PR"; the API says it is **open** (closed 09-14, then
reopened 09-14). LIKELY stale wording, not a behaviour change.

## The exact command a cluster operator should run

Boot the config under test first (one job at a time, `.scratch/q4/launch.sh`), then:

```sh
# smoke first (~2 min, deep-ish): proves the endpoint answers and the tool runs
python3 tools/gate-37111.py --base-url http://<node-ip>:8000 \
    --depth-tokens 12000 --turns 6 --json gate-37111-smoke.json

# the release gate: 1–2 h at ~100k depth (WORK §14's reproducer shape)
python3 tools/gate-37111.py --base-url http://<node-ip>:8000 \
    --depth-tokens 100000 --duration-min 90 --json gate-37111.json
```

Exit codes: `0` PASS · `1` unreachable · `2` bad flags · `3` FAIL (corruption,
or a partial run too incomplete to certify). The JSON carries every raw reply and
the warm/cold canary; keep it as the provenance artifact.

Recommended ladder once a FAIL is in hand (design memo §4): re-run with
`--disable-radix-cache` (R1), the `mods/fix-sglang-radix-chunked-insert` on/off
toggle (R2), eager vs decode-graph (R3), then the `zz-*-nospec` arms (R5).

## Provenance

- Gate: `tools/gate-37111.py` v0.1, stdlib-only, `--selftest` green (5 mock
  behaviours: clean PASS; degenerate/truncate/radix/radix-nosalt FAIL), 2026-10-04.
- Upstream states: GitHub API, read 2026-10-04 (see URLs above).
- Failure-mode claims: WORK doc §14 (VERIFIED issues; LIKELY root cause),
  §6 item 11, §7f, `tools/gate-37111-design.md`.