# Ornith 1.5 — staged cluster work (`recipes/ornith/NOTES.md`)

Working state for the lane: the plans this session authored off-cluster, with the
acceptance criteria and the boot commands the next cluster phase executes. Nothing
below was booted here — every node held another workstream during the authoring
phase, so the numbers quoted are prior receipts, not new measurements.

Read [`AGENTS.md`](AGENTS.md) first for the lane's constraints and traps; the
durable record is [`recipes/ornith/README.md`](../../recipes/ornith/README.md). This file is the *plan*; when a plan
runs, its result moves into `README.md`/`AGENTS.md` and the entry here is closed.

**No hostnames or addresses in tracked files.** Node shorthand `.30`–`.35` only.

---

## Contents

- [0. What this session produced](#0-what-this-session-produced)
- [1. Boot hygiene (applies to every arm below)](#1-boot-hygiene-applies-to-every-arm-below)
- [2. The 9B arm — BOOTED 2026-10-14 (CLOSED)](#2-the-9b-arm--booted-2026-10-14-closed)
- [3. Plan A — 35B: first-party DFlash head vs the shipped jzinno DFlash2 — CLOSED 2026-10-14](#3-plan-a--35b-first-party-dflash-head-vs-the-shipped-jzinno-dflash2--closed-2026-10-14)
- [4. Plan B — 397B: first-party DFlash head vs the checkpoint's MTP head — CLOSED 2026-10-14 (MTP ships)](#4-plan-b--397b-first-party-dflash-head-vs-the-checkpoints-mtp-head--closed-2026-10-14-mtp-ships)
- [5. Plan C — quality confidence — EXECUTED 2026-10-14 (owner ratifies the bar)](#5-plan-c--quality-confidence--executed-2026-10-14-owner-ratifies-the-bar)
- [6. Root index (README.md) — the row to add (not edited here)](#6-root-index-readmemd--the-row-to-add-not-edited-here)
- [7. Open questions (state after the 9B boot)](#7-open-questions-state-after-the-9b-boot)
- [8. Plan D — the YaRN ~1M arm — BUILT 2026-10-15, GATE RUN 2026-10-18](#8-plan-d--the-yarn-1m-arm--built-2026-10-15-gate-run-2026-10-18)

## 0. What this session produced

| artifact | state |
|---|---|
| [`ornith-1.5-9b-nvfp4-dflash-sglang.yaml`](../../recipes/ornith/ornith-1.5-9b-nvfp4-dflash-sglang.yaml) | **booted + measured 2026-10-14** (§2, closed); the draft pin was dropped to make it serve |
| [`../../tests/test_ornith_recipes.py`](../../tests/test_ornith_recipes.py) | lane guards O1–O4; the lane had none before |
| plan A — 35B first-party DFlash vs shipped DFlash2 | §3, **executed + closed 2026-10-14** (null; shipped draft pinned) |
| plan B — 397B DFlash head vs the checkpoint MTP head | §4, ready to execute |
| plan C — long-horizon quality-confidence set | §5, **executed 2026-10-14** — a bounded null (no loop); the owner ratifies the bar |
| plan D — YaRN ~1M long-context arm | §8, **built 2026-10-15** (`ornith-1.5-35b-a3b-nvfp4-yarn-1m-sglang.yaml`); boot + needle gate queued |

---

## 1. Boot hygiene (applies to every arm below)

These are not optional and are the same for all three plans.

1. **Clear the node first.** `docker ps -q | wc -l == 0`. A memory-starved boot is
   not a recipe cell — the lane voided one `.35` boot at 30.8 t/s with a serve log
   ending in `Killed` (§4 of `AGENTS.md`).
2. **Assert spec decode engaged.** The serve log shows `Mean acceptance length > 1`
   on `Decode batch` lines. A boot that serves with an accept near 1 is a
   misconfiguration, not a loss.
3. **Assert the served id.** `GET /v1/models` returns the repo id, never a
   `/cache/huggingface/hub/...` path.
4. **One knob per arm, one boot per arm, same node per comparison.** The measured
   same-config spread on this hardware is 7.5% (`.34`, 2026-10-11); without a
   same-window control an arm measures boot noise, not the knob.
5. **Read the decode-phase rows only.** Each bench cell emits a context-prefill
   record **and** a decode record, and both carry `tg_throughput`. Filter
   `is_context_prefill_phase` before pooling.
6. **Keep the `sparkrun --output` JSON.** `~/.cache/sparkrun/benchmarks/bench_*/runs/`
   is reaped; the output file carries the same records.
7. **Push before launching.** `@littlecedar/<name>` resolves from the registry
   *clone* on the head, not the local tree. Push, `sparkrun registry update
   littlecedar`, and use `--transfer-mode local`.

The measurement profile for all three plans is
[`benchmarking/decode-triage.yaml`](../../benchmarking/decode-triage.yaml): depth
{0, 8192}, pp 2048, tg 128, concurrency 1, `prefix_caching: true`, n=5 per cell.

---

## 2. The 9B arm — BOOTED 2026-10-14 (CLOSED)

**Shipped and measured.** `ornith-1.5-9b-nvfp4-dflash-sglang.yaml` booted on `.30`
2026-10-14: `GET /v1/models` returns `ornith-ai/Ornith-1.5-9B-NVFP4`, spec decode
engaged (serve-log `accept len` mean **3.35**, range 1.85–6.85, over 38 decode
batches), house battery **37/37** (19/19 + 18/18), and C1 **51.7 / 56.6 t/s** (cold) and
**59.4 / 54.1 t/s** (warm) at d0 / d8192 — n=5 per cell, decode-phase rows, two
same-window sweeps on one boot. The numbers, the receipts, and the design rationale (no
`mamba_*`/`moe_runner_backend`, no honed template, alias spelling, unpinned draft) now
live in [`recipes/ornith/README.md`](../../recipes/ornith/README.md) §"the small single-Spark arm" and [`AGENTS.md`](AGENTS.md)
§1 / §3.12; raw evidence is `~/benchmarks/ornith-9b-20261014/`.

**The one design change the boot forced.** The arm as authored pinned the draft
(`speculative_draft_model_revision: 21be3446…`) and **could not serve**: a SHA-keyed draft
fetch writes no `refs/` entry, and the container's `HF_HUB_OFFLINE=1` draft-config lookup
(`sglang …/speculative_hook.py::_resolve_speculative_algorithm_alias` → `get_config`)
resolves only `refs/main`, so the server died with `LocalEntryNotFoundError` at
`resolve_once`. The pin was removed — the 35B sibling's jzinno draft is unpinned for the
same reason — and the trap is recorded as `AGENTS.md` §3.12. The `mamba_*`/`moe_runner_backend`
omission was validated rather than assumed: the hybrid pool does **not** clamp
`max_num_seqs: 48` (`max_running_requests=48`, `max_mamba_cache_size: 273`).

**Both open boot questions are answered.** The pinned image *does* load the plain
`DFlashDraftModel` (`Load weight end. … type=DFlashDraftModel`), and the card's
`--speculative-dflash-block-size` alias is accepted (the block-size mismatch is
warning-only). See [`AGENTS.md`](AGENTS.md) §1.

---

## 3. Plan A — 35B: first-party DFlash head vs the shipped jzinno DFlash2 — CLOSED 2026-10-14

**Executed on `.31` 2026-10-14 — a null, and the shipped draft is now pinned.** One boot per arm,
same window, `benchmarking/decode-triage.yaml`, decode-phase rows only (n=5 per cell; all arms serve
with `accept len` mean > 1: jzinno 2.50, first-party n=4 2.44, first-party n=8 2.75):

| arm | draft | n | d0 t/s (σ) | d8192 t/s (σ) |
|---|---|---|---|---|
| A0 | shipped `jzinno` DFlash2 | 4 | 95.9 (10.9) | 101.3 (2.6) |
| A1 | first-party `942d20fe…` | 4 | 101.3 (5.2) | 97.8 (11.1) |
| A2 | first-party `942d20fe…` | 8 | 92.7 (7.9) | 92.8 (9.3) |

The 2026-10-13 jzinno baseline (99.6 / 100.2, σ 9.1 / 3.9) lands inside this window's spread. No
delta clears the ~9 t/s d0 boot noise and n=8 is *not* better, so **the shipped jzinno DFlash2
stands — the null is the result** (criterion 6). The winner's draft is pinned
(`speculative_draft_model_revision: 9b4852c05fd00b672b7434b1bb105bc03c8682b0`, distribution-only)
with a `pre_exec` hook seeding its `refs/main` — the pin alone leaves no `refs/` and the offline
draft-config lookup needs `refs/main`; verified cold (both caches stripped) on `.31`, and the pinned
boot scored the house battery **37/37**. Result, mechanism, and receipts now live in
[`recipes/ornith/README.md`](../../recipes/ornith/README.md) §"First-party DFlash head A/B" and [`AGENTS.md`](AGENTS.md) §1 / §3.12;
raw evidence is `~/benchmarks/ornith-dflash-ab-20261014/`.

**The question.** The lane ships the *third-party* draft
(`jzinno/Ornith-1.5-35B-A3B-DFlash2`, `9b4852c0…`, `DFlash2DraftModel`; unpinned when this plan was
written, pinned 2026-10-14 as recorded above).
The vendor published its own head two weeks later
(`ornith-ai/Ornith-1.5-35B-A3B-DFlash`, `942d20fe…`, MIT, plain `DFlashDraftModel`,
0.77 GB, no published numbers), which the lane's model scan already lists as an
unmeasured candidate (`README.md` §"2026-10-10 update scan"). This plan turns that
note into a measurement.

**Arms** (one boot each, same node, same window, `benchmarking/decode-triage.yaml`,
n=5 per cell):

| arm | draft | n | why |
|---|---|---|---|
| A0 | shipped `jzinno` DFlash2 | 4 | the same-window control; the 99.6/100.2 baseline is another day's |
| A1 | first-party `942d20fe…` | 4 | the head swap alone |
| A2 | first-party `942d20fe…` | 8 | the card's block size; the 2026-10-11 ladder lost ~19% at n=10, so the sweep is bounded at 8 |

Run A0–A2 interleaved if node time allows; the lane's own precedent is that a
single ordered sweep cannot separate an arm from a drift in node state.

```bash
sparkrun benchmark performance @littlecedar/ornith-1.5-35b-a3b-nvfp4-dflash2-sglang \
  -H <node> --profile benchmarking/decode-triage.yaml \
  --output ~/benchmarks/ornith-dflash-ab-<date>/armA2-firstparty-n8.json \
  -o speculative_draft_model=ornith-ai/Ornith-1.5-35B-A3B-DFlash \
  -o speculative_draft_model_revision=942d20fee84d04c9ecbf18e9c6fc4144914a1d5d \
  -o speculative_draft_tokens=8
```

`-o` reaches the draft *distribution* pin as well as the rendered flag — verified
against sparkrun 0.4.0 via `recipe._effective_default`, which consults applied
overrides — so a single `-o` pair is the whole arm and no probe recipe file is
needed.

**Acceptance criteria**

1. Every arm asserts `Mean acceptance length > 1` and a cleared node (hygiene §1).
2. A delta counts only if it clears **the d0 boot noise, σ ≈ 9 t/s** (the 2026-10-13
   d0 spread), and the losing arms are reported with the same σ rather than dropped.
3. The winner runs the house battery once; the comparison arm's score is 37/37.
4. **Pin the winner's draft** with `speculative_draft_model_revision: <sha>`
   (`942d20fe…` first-party / `9b4852c0…` jzinno) in the shipped recipe's `defaults:`.
   It is distribution-only by design — see §2 for why it is not rendered.
5. A flag-side finding is required either way: record whether the pinned image
   accepts `--speculative-dflash-block-size` (the card's spelling). If it does, the
   recipe may switch to it; if it does not, the alias documented in §2 is load-bearing
   and belongs in the recipe comment.
6. Done when one draft is pinned and the C1 delta is a receipt in `README.md`. A null
   ("the two drafts are indistinguishable") is a complete result and closes the item —
   but only beside the same-window control.

---

## 4. Plan B — 397B: first-party DFlash head vs the checkpoint's MTP head — CLOSED 2026-10-14 (MTP ships)

**The question.** The flagship arm specs with the grafted MTP head (`method: mtp`,
3 tokens) and carries only a **card figure** (41.86 t/s, tied to the floating
`:latest` tag). The third collection head is `ornith-ai/Ornith-1.5-397B-DFlash`
(`db9c35a0…`, 2.58 GB, `DFlashDraftModel`, taps 1/9/…/57 of a 60-layer target, MIT,
ungated, no published numbers). This is the registry's most expensive arm: 235 GB
per node at `gpu_memory_utilization: 0.80`, four nodes.

**Keep the target constant.** The shipped graft tree
(`littlecedar/Ornith-1.5-397B-NVFP4-MTP-Graft`) carries both methods. Reach for the
upstream plain quant (`ornith-ai/Ornith-1.5-397B-NVFP4`, `fcefb8b2…`, 241.8 GB)
**only** if the graft's packaging fights `method: dflash` — a target swap makes the
comparison two variables, and that swap gets its own line here if it happens.

**Swap exactly one knob.** Arm MTP is the baseline re-measured in the same window
(the 41.86 figure is a card number, not a house measurement). Arm DFlash replaces
the `speculative_config` JSON:

```bash
sparkrun benchmark performance @littlecedar/littlecedar-ornith-1.5-397b-nvfp4-mtp-graft-vllm \
  -H <.30>,<.31>,<.32>,<.33> --profile benchmarking/decode-triage.yaml \
  --output ~/benchmarks/ornith-397b-spec-ab-<date>/armDFlash.json \
  -o 'speculative_config={"method":"dflash","model":"ornith-ai/Ornith-1.5-397B-DFlash","revision":"db9c35a091e89f942c609880f98bb385019dc4f8","num_speculative_tokens":8}'
```

The revision must be pinned **inside that JSON**, never via `model_revision:` — that
SHA does not exist in the target repo and sparkrun reads both the draft and its
revision out of the JSON to distribute the draft to all four nodes
(`runtimes/_vllm_common.py`, `vllm_ray.py`). The MTP config's
`max_model_len`/`attention_backend`/`moe_backend` keys are MTP-specific: start
minimal, as above.

**Execution state (2026-10-14).** Pre-boot checks resolved, then the boots launched.

- **Digests resolved — and the tag was not even uniform across the nodes.** The four serving nodes held
  **three different builds** under `ghcr.io/spark-arena/dgx-vllm-eugr-nightly:latest`: `.30` =
  `1e6901494c15` (`nightly-20260913`, vLLM `0.29.1rc1.dev17+gd2d649e67`), `.31` = `8af109d2db48`
  (`nightly-20260826`, `0.26.1rc1`), `.32`/`.33` = `87e57cafa670` (`nightly-20260911`). The registry's
  `:latest` resolved to a **fourth** build, `sha256:364005b0376e2bad0261d420a3fba19bb1a812e7e1385e83e93fb1d0005c3e33`
  (`nightly-20261013`, vLLM `0.32.0rc1.dev78+gd96f1aa34`) — which this cluster **could not pull**: the
  OCI relay's registry download stalled (~11 MiB/s → 400 KiB/s) and failed on all four nodes. The recipe
  is now pinned to the head-resident build
  (`@sha256:b94ac8ac47603f9c3d14f88c12b90eacbc37c7a42f922631cb8c9ac80f7b37c3`, `nightly-20260913`),
  distributed uniformly to all four nodes. **A TP=4 comparison on the bare tag was never one engine.**
  The pinned build exposes `method: dflash` (`vllm/config/speculative.py`: `DFlashModelTypes =
  Literal["dflash"]`, `use_dflash()`), verified by running the image on `.30`.
- **Loader trap — resolved, no mod change.** `instanttensor` is not a separate on-disk format: vLLM maps
  it to the *default* loader with an InstantTensor safetensors iterator (`vllm/config/load.py`;
  `model_loader/__init__.py`: `"instanttensor": DefaultModelLoader`), so a plain-safetensors
  `DFlashDraftModel` loads under `--load-format instanttensor`. And
  `@eugr/mods/instanttensor-hybrid-draft-loader`'s `auto` mode only switches the *draft* to lazy
  safetensors when draft and target share a repo+revision (the MTP case); it returns the run's loader for a
  different draft repo — the standard path, which is what we want. The mod stays in place.
- **Second trap found: the `-o` in the command above was a silent no-op as written.** The recipe's
  `--speculative-config` JSON was **inline** in `command:`, and sparkrun only distributes the draft from a
  *declared* `speculative_config` default (`runtimes/_vllm_common.py::detect_spec_config_draft`). Fix
  (shipped): the recipe now declares `defaults.speculative_config` and renders
  `--speculative-config '{speculative_config}'`, so `-o speculative_config={...}` swaps the method *and*
  makes sparkrun distribute `ornith-ai/Ornith-1.5-397B-DFlash` to the four nodes — verified against
  sparkrun 0.4.0 (`-n`: both models in the distribution list; the exact DFlash JSON renders). The MTP arm
  renders byte-identically to the old inline JSON.
- **Arm A (MTP baseline) — BOOTED + MEASURED 2026-10-14** on the pinned build (`.30–.33`, TP=4).
  Receipts `~/benchmarks/ornith-397b-ab-20261014/` (`armA-mtp.json` + its `.json`/`.csv` sidecars,
  `armA-state/` = the preserved `bench_7fca0d44df65` incl. `runs/`, `armA-launch2.log`):

  | arm | method | C1 d0 t/s (σ) | C1 d8192 t/s (σ) | spec accept | TTR (cold) |
  |---|---|---|---|---|---|
  | A | MTP, 3 tok | **42.55** (2.78) | **38.48** (1.91) | `Mean acceptance length` 2.68–3.06 (5 samples) | port 590.7 s |

  Cells: `benchmarking/decode-triage.yaml` (depth {0,8192}, pp 2048, tg 128, c=1, n=5), decode-phase rows
  only (`is_context_prefill_phase: False`; the d8192 *prefill-phase* record carries a third, confusing tg
  figure of 40.11 — **not** pooled). `GET /v1/models` = `littlecedar/Ornith-1.5-397B-NVFP4-MTP-Graft` (repo
  id); container = the pinned `1e6901494c15` on all four nodes. The d0 result (42.55) is the first house
  measurement beside the card's 41.86.
  Arm A's serve log was **not preserved** (the server is torn down at benchmark end; the acceptance
  samples were read live) — see the receipt dir's `armA-serve.log.README`. Arm B's is preserved.
- **Arm B (DFlash) — BOOTED + MEASURED 2026-10-14** on the same pinned build, same window, same node set.
  Arm A ran the registry clone's recipe via `--image`; Arm B ran the edited recipe **by file path** with
  `-o speculative_config={...}` (renders the MTP arm byte-identically — verified `-n`). The draft
  (`ornith-ai/Ornith-1.5-397B-DFlash`, 2.58 GB) was **distributed to all four nodes by sparkrun from the
  `speculative_config` default** — the recipe change is load-bearing and proven. Serve log
  (`armB-serve.log`): `Resolved architecture: DFlashDraftModel`, `Speculative decoding (method=dflash) is
  enabled`, `Mean acceptance length: 3.27` mean over 2 samples [3.02, 3.53]; `GET /v1/models` = repo id.
  Rendered `--speculative-config` = `{"method":"dflash","model":"ornith-ai/Ornith-1.5-397B-DFlash",
  "revision":"db9c35a091e89f942c609880f98bb385019dc4f8","num_speculative_tokens":8}` (from the serve log's
  `non-default args`). Receipts: `armB-dflash.json{,.json,.csv}`, `armB-state/` (`bench_1e451153b130`).

**Result — MTP wins; the DFlash head does not transfer the acceptance gain to throughput.**

| arm | method | C1 d0 t/s (σ) | C1 d8192 t/s (σ) | spec accept |
|---|---|---|---|---|
| **A** | **MTP, 3 tok** | **42.55** (2.78) | **38.48** (1.91) | 2.68–3.06 |
| B | DFlash, 8 tok | 37.58 (4.45) | 33.64 (1.13) | 3.27 (3.02–3.53) |

DFlash is **−11.7% at d0 and −12.6% at d8192** — outside both arms' spread — **despite a higher
acceptance length** (3.27 vs ~2.9): the extra accepted tokens do not clear the DFlash speculator's own
overhead. It also carries a **structural confound**: with `method: dflash` on this hybrid-Mamba target
vLLM logs *"no KV cache group could be identified as the draft model's, so every group — including Mamba
groups [0..44] — will be treated as a draft group … prefix-cache reuse across requests will be disabled"*
(serve log ×2). Only the DFlash arm triggers that widening (the MTP config has no separate draft KV
group to misidentify), so the two arms differ on prefix-cache reuse as well as on method — part of the
arm, not a knob we set. **The lane ships MTP** (the recipe's default is
unchanged). The DFlash head is **not archived and needs no recipe file**: it stays a documented one-knob
alternative via `-o speculative_config={...}` (this is the recipe's own swappability, §3.13).

**Traps checked before the boots (all three resolved — see the execution state above)**

1. **The floating nightly must expose `method: dflash`.** ✅ Resolved — and the check changed the plan:
   the four nodes did **not** agree on a digest, so the pin is the head-resident build (`b94ac8ac…`),
   not the registry's current `:latest` (`364005b0…`, which could not be pulled from this cluster).
   The pinned build exposes `dflash`, verified by running the image.
2. **`--load-format instanttensor` + the hybrid-draft mod were built for the MTP head.** ✅ Resolved —
   no loader knob needed: `instanttensor` *is* the default loader's safetensors path, and the mod's
   `auto` mode returns the run's loader for a draft whose repo differs from the target. See the
   execution state.
3. **The draft adds ~2.6 GB per node on top of a ~235 GB/node footprint at 0.80.** Noted for the second
   arm — the draft (`ornith-ai/Ornith-1.5-397B-DFlash`, 2,585,613,754 B) is distributed to all four
   nodes by the `speculative_config` default (§3.13). Watch `MemAvailable` before Arm B.

**Acceptance criteria**

1. Both arms are same-window; each is a clean boot (hygiene §1) with a recorded
   digest and a serve-log acceptance figure.
2. C1 at depth 0 and 8192 for both arms, beside each other, n=5 per cell.
3. The winner is recorded in `README.md`/`AGENTS.md` **with the loser's rationale**,
   and the `:latest` tag gets a digest pin in the recipe carrying the winner's
   numbers.
4. Done when both arms have receipts and the digest pin lands. This is the item most
   likely to spill; if only one arm runs, that is an unfinished comparison, not a
   result.

---

## 5. Plan C — quality confidence — EXECUTED 2026-10-14 (owner ratifies the bar)

The owner was not convinced of the model's quality and was surprised the 2026-10-13 investigation
could not reproduce the long-horizon looping. That investigation ran nine single-turn reasoning
prompts × {temp 0, temp 0.6} × {4096, 8192 tokens} and found zero repeated-window runs. **A battery
that cannot exercise a long-horizon agentic workload is not evidence about long-horizon looping** —
that is the gap this plan closes.

**Executed 2026-10-14 on `.31`** — C1–C4 in one boot of the shipped 35B arm, C5 in a second boot of
the 9B arm — by
`~/benchmarks/ornith-horizon-20261014/agentic_horizon_probe.py` (a long-horizon scheduling agent
with a growing transcript; per-message and session 25-word-window repeat scoring, cross-turn 8-word
shingle overlap, `finish_reason`), `tools/needle-haystack.py`, and `tools/quality-battery.py`. Full
method, arm table, and result are in [`recipes/ornith/README.md`](../../recipes/ornith/README.md) §"Long-horizon agentic
re-investigation (2026-10-14)"; receipts are `~/benchmarks/ornith-horizon-20261014/`.

**Pre-registered experiment set (C1–C5).**

- **C1 — Reproduce on the right workload.** A multi-turn tool-using loop carrying a large
  transcript, scored on `reasoning_content` for repeated-window runs with `finish_reason` read to
  separate a true loop from a budget truncation.
- **C2 — A standard suite, not only the house battery.** The adopted shared suite
  (`sparkrun benchmark tools`, tool-eval-bench) and the ds4 hard tier, beside the 35B's score.
- **C3 — Sampling fidelity.** The card's *coding* sampling (temp 0.6) against its *general* recipe
  (temp 1.0, top_p 0.95, top_k 20, min_p 0.0, **presence_penalty 1.5** — an anti-repetition knob
  this endpoint had never served), same prompts, both ways.
- **C4 — Context degradation.** `tools/needle-haystack.py` at 32k, 128k, and 262144 (the native
  window; YaRN is not enabled in either recipe).
- **C5 — Cross-scale.** Run C1–C4 on the 9B arm and compare.

**Results against that set.**

- **C1 — NOT REPRODUCED, bounded.** Five long-horizon arms (16k and 32k budgets, temp 0.6 and
  1.0 ± `presence_penalty` 1.5, up to 48 assistant turns and a 34,705-token prompt) produced **no
  decode loop**: the per-message 25-word repeat never exceeded 5, and every ≥3 event is the model
  re-listing the *provided* requirement set, not replaying its own reasoning; cross-turn overlap
  never approached 1 (max 0.71, the shared shingles being that same list); reasoning grows with the
  task (63 → 638 words); no arm hit `finish_reason=length`; and the model converges on valid plans.
  **Detection limit:** ~35k-token transcripts, 48 turns, 16k and 32k budgets, temp 0.6 and 1.0 ± a
  presence penalty of 1.5, with the metric firing at ≥3 repeats — a loop outside that envelope is
  not excluded.
- **C2 — met only by the house battery.** **37/37** (19/19 + 18/18, zero flakes) re-scored on this
  boot — parity with prior runs, no regression. The named `tool-eval-bench` framework was **not
  configured in this registry** when this pass ran (it is now: `benchmarking/standard-suite.yaml`,
  added 2026-10-15), so the "adopted shared suite" clause of C2 could not be run; the house battery
  is the lane's only suite score. **Gap stated, not smoothed.**
- **C3 — discriminated.** Request-level sampling is honoured (distinct `reasoning_content` hashes
  at temp 0, 0.6, and 1.0 + `presence_penalty` 1.5). The card's *general* recipe gives the same
  shape as the served coding sampling: no loop either way. **No sampling-dependent loop, so no
  client-side mitigation is indicated.**
- **C4 — passes at two of three windows; the third is a budget artifact.** 32k 3/3, 128k 3/3, and
  the native 262,144 2/3 at a 64-token budget. The 262k miss is **not** a retrieval failure: at the
  native window the model emits ~150–200 characters of reasoning before the answer under the served
  default, so a 64-token budget truncates the visible answer; re-probing at 256 tokens passes, and
  six repeats at 64 tokens mix full (`finish=stop`) and truncated (`finish=length`) answers.
  Retrieval is intact at ~256k prompt tokens. Recorded as a **client-facing caveat** (short
  `max_tokens` plus a `content`-reading client → empty or partial replies at long context), not a
  capability limit.
- **C5 — run; same null at the smaller scale, plus a worse empty-reply rate.** The 9B arm, booted on
  `.31` (second boot, ready ~280 s), gives the same long-horizon shape (no decode loop; per-message
  repeat max 2, the ≥3 session windows again the re-cited requirement list; reasoning growing
  29 → 423 words; 9/5 valid/invalid plans) and a 32k needle **0/3 at a 64-token budget, every reply
  empty**. A direct probe shows the empties are the *same* reasoning-budget artifact, worse at this
  scale: the 9B spends 250+ characters of reasoning before answering, so `max_tokens=64` yields
  empty content and `max_tokens=512` recovers the correct codeword in 2 of 3 tries. Retrieval itself
  is intact; the 9B is simply more prone to reasoning-before-answer than the 35B (0/3 versus 2/3 at
  64 tokens).

**Bar for ratification (pre-registered — carried unchanged).** Quality is "confirmed" only if all
of:

1. **C1 is bounded, either way.** Reproducing the symptom satisfies the item directly. A null does
   **not**: the report must state the *detection limit* — the longest transcript driven and the
   repetition threshold the scoring could have caught — so the null is bounded evidence.
2. **C2 holds.** No regression against the 35B's suite result at the served sampling.
3. **C3 is discriminated.** The difference between the two sampling recipes is stated with receipts,
   whichever way it goes.
4. **C4 passes** at two of the three depths, and the failing depth (if any) is recorded as a
   capability limit rather than smoothed over.

**Verdict against the bar.** (1) met — a bounded null at both scales (C1, C5); (2) met in the
house-battery sense only, with the suite C2 named unavailable and disclosed as an unmet clause;
(3) met; (4) met at two windows, the third explained as a client-budget artifact, and reproduced at
the 9B scale. **The set is complete except for the C2 suite clause.** The owner ratifies the result
and decides whether the lane ships as-is, gates on a fix, or records the model as not recommended
for long-horizon agentic work. The verdicts were pre-registered before the boots and are carried
unchanged.

---

## 6. Root index (`README.md`) — the row to add (not edited here)

The index is the parent agent's to edit. With §2 closed the row is measured, and the
`🚀` condition is met — both warm C1 cells clear the ≥ 50 t/s threshold:

| recipe | Scale | Runtime | Nodes (TP) | C1 t/s | Size | Mem | Flags |
|---|---|---|---|---|---|---|---|
| `ornith-1.5-9b-nvfp4-dflash-sglang.yaml` | 9B | SGLang | 1 (TP=1) | 55 | ~11GB | 0.85 | ✨🚀🤏👀🧠🦾🔧 |

`✨` official, `🤏` smol, `👀` vision, `🧠` reasoning, `🦾` agent, `🔧` tools; `🚀` fast
(C1 ≥ 50 t/s) — earned, but the per-run spread is wide (d0 σ 6.8–13.2, d8192 σ 9.0–16.4)
and one cold cell sits at 26 t/s, so drop `🚀` if the lane wants the stricter read. `🌲`
lcg_favorite is **not** claimed.

**The YaRN 1M arm's row — do NOT add it yet (2026-10-15).** Nothing about it is measured, and only
its `🚚` large_context flag is earned by *construction* (a ≥512k window it cannot yet prove it
serves). The row, for after §8's gate passes:

| recipe | Scale | Runtime | Nodes (TP) | C1 t/s | Size | Mem | Flags |
|---|---|---|---|---|---|---|---|
| `ornith-1.5-35b-a3b-nvfp4-yarn-1m-sglang.yaml` | 35B-A3B | SGLang | 1 (TP=1) | — | ~26GB | 0.85 | ✨🚚👀🧠🦾🔧 |

`🚚` large_context (≥ 512k window), and no `🚀`/`🐢`/`🌲` until a C1 and a needle receipt exist.
`Size` is the draft-free sibling's 23.5 GB of weights plus its ~2 GiB of target CUDA graphs — an
estimate, not a measurement; replace it with the boot's own numbers.

## 7. Open questions (state after the 9B boot)

Answered 2026-10-14 (§2, closed):

- **Yes** — the pinned SGLang image loads a plain `DFlashDraftModel` (serve log:
  `Load weight end. … type=DFlashDraftModel`).
- **No** — the omitted `mamba_*` defaults do not cost concurrency on the 9B: the pool
  grants `max_running_requests=48` with `max_mamba_cache_size: 273`.
- **Yes** — the pinned image accepts the card's `--speculative-dflash-block-size` alias
  (spelled `--speculative-num-draft-tokens`); the block-size mismatch is warning-only.

Still open (Plan B, §4):

- Does the plain-safetensors draft load under the instanttensor/hybrid-draft loader?

---

## 8. Plan D — the YaRN ~1M arm — BUILT 2026-10-15, GATE RUN 2026-10-18

**Booted; the gate is measured and the arm ships for ≤768k with 1M to depth 50 %.** The gate table,
the d90 ERROR ×2 diagnosis and the four boot grants are in [`recipes/ornith/README.md`](../../recipes/ornith/README.md) §"The YaRN 1M arm"
and [`AGENTS.md`](AGENTS.md) §9.1; receipts `~/benchmarks/ornith-trials-20261018/` and
`~/benchmarks/ornith-yarn-1m-20261018/`. `recipes/ornith/ornith-1.5-35b-a3b-nvfp4-yarn-1m-sglang.yaml` —
the 35B checkpoint (same pin as the sibling, `94e431d9…` = Hub `main`) at the model card's YaRN factor-4.0
route with `max_model_len: 1000000` and **no DFlash2 draft**. Build record, the card
quote, the engine citations (`sglang v0.5.18` `configs/model_config.py:819-843`, `:328-336`, `:590`,
`utils/hf_transformers/config.py:266-275`, `environ.py:298`) and the KV arithmetic:
[`AGENTS.md`](AGENTS.md) §9. Read [`recipes/ornith/README.md`](../../recipes/ornith/README.md) §"The YaRN 1M arm" for the arm itself.

**The three things that make it a boot and not a flag change:** (1) the YaRN override must nest under
`text_config.rope_parameters` **and** restate the mrope keys — a flat form is silently ignored, a
partial form silently drops the model off its M-RoPE path; (2) `SGLANG_ALLOW_OVERWRITE_LONGER_CONTEXT_LEN=1`
is load-bearing — this build *raises* above the derived 262,144 rather than warning; (3) the draft is
gone on purpose (a 262,144-window, default-RoPE head has no per-draft override flag, so it would be
scored out of distribution).

**Boot (one node, `.34`/`.35`, mem-fraction 0.85 — no memory change needed).**

```bash
docker ps -q | wc -l   # must be 0 (§1.1)
sparkrun run recipes/ornith/ornith-1.5-35b-a3b-nvfp4-yarn-1m-sglang.yaml \
  -H <node> --transfer-mode local            # recipe REAL path, never a flattened symlink
curl -s http://<node>:8000/v1/models         # max_model_len must read 1000000, id = the repo id
```

Read from the serve log and record with the receipt: `max_total_num_tokens` (the grant; the recorded
262k boot gave 1,172,758 tokens / 11.18 GiB of fp8 KV at 10,235 B/token), `context_len=1000000`, and
the absence of any speculative/draft init line. Skip every spec-decode assertion in §1.2 — this arm
has no draft by design.

**The needle gate (the pass criterion is pre-registered; do not re-cut it after seeing the numbers).**
`tools/needle-haystack.py`, depths `10,50,90`, seed 1234, 64-token budget, one boot:

```bash
for ctx in 262144 512k 768k 1m; do
  python3 tools/needle-haystack.py --model auto --api-endpoint http://<node>:8000 \
    --context-length "$ctx" --depths 10,50,90 \
    --json ~/benchmarks/ornith-yarn-1m-<date>/needle-$ctx.json
done
```

- **Pass** = every ladder (including the 262,144 control rung) exits 0 / verdict `PASS`: every key
  retrieved **and** `usage.prompt_tokens ≥ 0.95 × requested` (the instrument reports a short count as
  `TRUNCATED`, exit 3 — a window/pool finding and a gate failure, not a retrieval miss).
- **The 262,144 control rung is not optional**: it is the only cheap test of the card's own
  "static YaRN can slightly hurt ordinary-length inputs" warning on this checkpoint.
- Cost ≈ 1–2 h of prefill (recorded: 45 s / 128k, 142 s / ~256k on this node → ~5 / 8 / 10 min per
  512k / 768k / 1M rung, ×3 depths), plus calibration.
- Then, and only then, the §6 index row and a `big_context` claim. **Done 2026-10-19:** the gate is
  6/6 across the two boots (1M at depths 10 %/50 % on 2026-10-18, 90 % on 2026-10-19 at 977,975
  counted tokens), so the root-README row landed with the 🚚 flag and no ladder cells (the arm is
  depth-gated, not speed-gated). The two earlier d90 serve exits make the 1M path measured but not
  reliable — that caveat is carried in the row's footnote and the lane README.

**Open boot questions** (AGENTS.md §9): does the override reach the loaded config as `rope_type:
yarn` (the serve log does not print it — a >262,144 rung that PASSes is the behavioural proof); does
anything downstream need `max_position_embeddings` raised with `context_len` (the base config keeps
262,144; SGLang raises it only for a draft model); and the arm's C1 is unknown — do not inherit the
sibling's ~100 t/s (it is spec-decoded).
