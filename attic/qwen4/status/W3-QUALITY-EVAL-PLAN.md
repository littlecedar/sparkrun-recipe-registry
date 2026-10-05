# W3 — Quality-eval plan for the labquant export

Workstream W3 (`recipes/qwen4/AGENTS.md:112`, WORK §6 item 5).
Artifact under this memo: `tools/qwen4-quality-eval.py` (fixed 38-task battery).
Every claim carries a provenance label; an unsourced sentence is a defect.

## 1. What the eval measures

- Exact-match accuracy on a **fixed, version-controlled 38-task battery** at
  `temperature=0`, behind an OpenAI-compatible `/v1/chat/completions` endpoint
  (`tools/qwen4-quality-eval.py`; the tool pins the battery to a SHA so a result
  is reproducible). 6 categories: multi-step arithmetic with a required
  intermediate, exact instruction-following, false-premise traps, generated
  long-in-prompt recall with a distractor, short code comprehension, and
  verbatim reproduction (the last is the closest exact-match probe of the PLE
  n-gram path, mirroring `probe_correctness.py`'s rationale).
- It is a **paired comparator**, not an absolute score: the number is meaningful
  only against the same battery on the reference checkpoint, same window.
- `VERIFIED` the battery is unique and shares no >16-char prefix (the tool's
  `--selftest` asserts this), so a radix prefix cache cannot flatter a run —
  matching the rationale in `tools/quality-battery.py:32–34`.
- `VERIFIED` the tool's own `--selftest` passes ground truth + 3 negative
  controls (correct / always-wrong / empty mock) offline, no GPU.

## 2. What the eval CANNOT conclude

- **Not** an absolute "is labquant good enough" verdict; 38 short exact-match
  tasks cannot certify an export (`tools/quality-battery.py:20–26` says the same
  of its easy tier).
- **Not** reasoning quality, safety, calibration, or long-context retrieval
  (that is `tools/needle-haystack.py`).
- **Not** throughput evidence (`AGENTS.md:24` — quality outranks throughput;
  benchmark wins are not quality evidence, WORK §6 item 5).
- **Not** a per-knob attribution: the two recipes differ by the whole labquant
  mod chain and `quantization` value (`modelopt_mixed` vs `modelopt_fp4`,
  `qwen3.8-flash-next-nvfp4-labquant-sglang.yaml:113` vs
  `qwen3.8-flash-next-nvfp4-sglang.yaml:31`), so a gap is a *package* difference,
  not proof that PLE quantisation alone caused it. `LIKELY` package-level;
  mechanism unseparated.
- Does **not** cover the `#37111` silent-corruption risk; that is W4 (WORK §14).

## 3. Exact A/B protocol (pre-registered)

Run once per checkpoint, same window, both TP=2, one cluster job at a time
(`AGENTS.md:75–77`). Control every free variable:

| axis | value (both arms) |
|---|---|
| battery | `tools/qwen4-quality-eval.py`, same `battery_sha256` |
| seed | `--seed 20261004` |
| repeat | same `--repeat` on both arms, run **interleaved** (ABAB) if feasible |
| `--max-tokens` | same value on both arms (default 1024) |
| recipe (control) | `qwen3.8-flash-next-nvfp4-sglang` (RadixArk reference) |
| recipe (treatment) | `qwen3.8-flash-next-nvfp4-labquant-sglang` |
| endpoint | each arm's own `/v1/chat/completions`; record `--model` as served |

Commands (control arm shown; swap `--model` and endpoint for the treatment):

```sh
python3 tools/qwen4-quality-eval.py --base-url http://<node>:8000 \
  --model RadixArk/Qwen3.8-Flash-Next-NVFP4 --repeat 3 \
  --json q4-radixark.json
python3 tools/qwen4-quality-eval.py --base-url http://<node>:8000 \
  --model /cache/runtime/labq-patched --repeat 3 \
  --json q4-labquant.json
```

Interleave if the pair is free: this lane's rule is that a same-window control
beats more runs (`AGENTS.md:190–191`). A task that flips across repeats is
reported `FLAKY` and treated as unstable, not as a score (`quality-battery.py:36–41`).

## 4. Sample size for a paired exact-match comparison

Both checkpoints are the same base model, so most tasks pass on both; the
discriminating signal is only the **discordant** tasks. The correct test is
**McNemar's exact test** on the paired 2×2, **not** two independent proportions.
`LIKELY` (standard method, not measured on this model).

Required paired observations (McNemar normal approximation, α=0.05, power 0.8),
for net discordance `p10 − p01`:

| RadixArk-only fail `p10` | labquant-only fail `p01` | per-pair n | repeats of 38 |
|---|---|---|---|
| 0.15 | 0.05 | ~122 | 4 |
| 0.10 | 0.02 | ~114 | 3 |
| 0.08 | 0.03 | ~270 | 8 |
| 0.10 | 0.05 | ~369 | 10 |

`SPECULATIVE` the effect size; the table is what makes a **single pass
insufficient** — n=38 sees only very large gaps. **Pre-registered:** budget
`--repeat 3` (n=114) minimum; that reliably blocks only an ~8 pp-plus net
deficit. A smaller true gap reads `INCONCLUSIVE` — take more repeats, not adoption.

## 5. Pre-registered decision rule (fixed before any data)

Per-task outcome per arm = **modal** result across repeats (majority of an odd
count). Let `R` = RadixArk total, `L` = labquant total (out of 38).

- **PASS — "no gross quality regression":** `L ≥ 0.90·38` (i.e. `L ≥ 35`) **and**
  `R − L ≤ 2` **and** McNemar exact one-sided p ≥ 0.05 **and** no single category
  where labquant trails RadixArk by ≥2 tasks.
- **BLOCK adoption** (do not ship labquant as the default recipe) if **any** of:
  1. `L ≤ 34/38` (< 90 % absolute) — gross regression tripwire;
  2. RadixArk wins ≥ 3 net discordant tasks **and** McNemar exact p < 0.05;
  3. any one category's labquant pass-rate ≤ 50 % while RadixArk's is ≥ 90 %.
- **INCONCLUSIVE:** everything else, including a large but non-significant gap or
  ≥3 FLAKY tasks. Do not adopt on INCONCLUSIVE; collect more repeats.

**The threshold that blocks adoption is criterion 2** (≈3-task / 8 pp net deficit
at p<0.05), because criterion 1 alone would pass a model that is uniformly
mediocre on both arms. This is deliberately stricter than a "don't score below
X %" tripwire, which a quantised export could satisfy while still being
systematically worse than its reference.

## 6. Standing

A green battery is a **negative result on the axes tested**, not a quality
certificate — the same caveat `probe_correctness.py` carries about itself
(`.upstream-cache/probe_correctness.py:14–16`). Record the artifact JSONs; the
run is not done until both are on disk with their `battery_sha256`.