# Qwen3 lane — consolidated notes & action plan (`recipes/qwen3/`)

**Who this is for:** the next agent picking up this lane. It is the **entry point**: current state,
the constraints that bite, and the **action plan divided into parallel workstreams** with a
coordination mechanism. Everything long-form is a `§N` cite-target in the sibling evidence docs.

**Reading order for a new agent:** this file → [`COOP.md`](COOP.md) (live node/bench claims) →
[`README.md`](README.md) (the shipped recipes, for a human audience) → the `§N` section named next to
your workstream. **Do not re-read the WORK/DEPTH docs front-to-back — they are written for targeted
lookup** and run to 3,300 / 3,800 lines.

**Confidence labels are the house rule.** Every claim carries `VERIFIED` (measured on device or read
from the artifact that decides it) / `LIKELY` / `SPECULATIVE`, with a source (`§N`, `file:line`,
`bench_*`) or an explicit "unmeasured". A confident unsourced sentence is a defect. **Many numbers in
the docs were retracted** — check a section's retraction banner before quoting it.

---

## 1. Mission and current state

Produce and defend the highest-quality, highest-throughput `sparkrun` recipes for the **RadixArk
Qwen3.8-27B** checkpoint (dense hybrid, 48 GDN + 16 full-attention layers, **no MoE**) on a **single**
DGX Spark (GB10, TP=1), plus the **Qwen3-VL embed/rerank** encoders on vLLM.

**One shipped, production recipe** (single-node, `sglang:dev-cu13`), plus the retired control:

| recipe | role |
|---|---|
| `qwen3.8-27b-nvfp4-dflash2-sglang.yaml` | **shipping** — DFLASH2 spec decode, block 8 |
| `attic/qwen3/qwen3.8-27b-nvfp4-nospec-control-sglang.yaml` | **control only, archived 2026-10-10** — same bytes, no `--speculative-*`; its plain-decode metrics are now recorded in `AGENTS.md` §6 |

**Four Qwen3-VL recipes** (vLLM `b12x` container): `qwen3-vl-embedding-{2b,8b-awq-4bit}`, `qwen3-vl-reranker-{2b,8b}`. Correctness shipped and hardware-verified; performance sizing intentionally open (§5 WP8b).

**Best measured state** (`VERIFIED` unless noted; sources in WORK):

| quantity | value | note |
|---|---|---|
| plain decode (no-spec, d=0, c=1) | **12.56 ± 0.02 tok/s** | 10 runs / 2 containers; ±0.25 % across boots |
| shipping decode (block 8, d=0, c=1) | **33.76 tok/s** | absolute is the reference; the *ratio* is not |
| block 8 vs block 4 | **+22.5 %** (95 % CI [1.188, 1.262]) | pooled over 3 same-node interleaved phases, 24 boots |
| granted concurrency | **21** (`K=85`) at `D=8`, fresh container | not the requested 48; ceiling 26 at any ratio |
| implied weight bandwidth | **221 GB/s** | = 17.608 GB × 12.56 tok/s |
| accepted tokens/step `A_eff` | **3.265** pooled (1,481 log lines); 3.99 is a single probe | quote 3.265 for capacity math |
| c=8 depth cost (8k→) | **~20 %** (boot-level 8–29 %) | congested/pool-limited; uncongested c=4 is **~11 %** |

---

## 2. Where the evidence lives

| artifact | location | tracked? | cite form |
|---|---|---|---|
| Decision record (current answer + open queue) | `QWEN3-MODEL-OPTIMIZATION-WORK.md` | no (git-ignored) | `WORK §N` |
| Depth-cost thread | `DEPTH-COST.md` | **yes** | `DEPTH-COST §12.NN` |
| SSM/gdn dtype thread | `SSM-STATE-DTYPE.md` | **yes** | `SSM §12.NN` |
| Answered queues (search by PROFILE name before re-running) | `ANSWERED-QUEUES.md` | **yes** | `AQ item N` |
| Narrative log | `JOURNAL.md` | no (git-ignored) | — |
| Qwen3-VL embeddings work | `QWEN3-EMBED-OPTIMIZATION-WORK.md` | no (git-ignored) | `EMBED §N` |
| Qwen3-VL narrative | `EMBED-JOURNAL.md` | no (git-ignored) | — |
| Coordination ledger (live) | `COOP.md` | **no — never `git add`** | — |
| Benchmark profiles | `benchmarking/*.yaml`; dead arms in `attic/benchmarking/` | yes | profile filename |
| Bench results | `~/.cache/sparkrun/benchmarks/bench_<id>/` on head | scratch (reaped) | `bench_*` id |
| Scratch drivers/analyzers | `.scratch/qwen3-27b/` (~269 files) | no (git info/exclude) | `file:line` |

**A result has no provenance without its `bench_*` id**, and a boot's config comes from **that boot's**
`state.yaml`, never a sibling's or memory. Cite `bench_*` + `§N`, never the printed sparkrun table.

---

## 3. Hard constraints and traps

1. **Node allowlist.** Session assignment: the free pair (`node-free-1`/`node-free-2`); the head and
   `node-restricted-1..3` are **restricted** (all four serve the DS4 job). Concrete addresses live in
   `COOP.md` (untracked); re-check it each session and re-resolve hostnames before acting.
2. **The head is the run-from host.** `sparkrun` runs on the head; recipes are run **by name** from
   `$WOPR_RUN_FROM_DIR` with `mods` symlinked in. **qwen3 recipes are not yet symlinked there** — that
   is a per-session setup step. Running by absolute path breaks `mods/<name>` resolution.
3. **One boot/arm at a time** on the free pair. Co-resident jobs recreate each other's containers.
4. **`-o` overrides `defaults:` only through a consumed `{placeholder}`.** Verify on the rendered line
   (`sparkrun run <recipe> -H <node> -n`), then on the live argv for load-bearing flags.
5. **Mods run as root** in the persisted runtime cache; reown anything under `/cache/runtime` to
   `stat -c '%u' /cache/runtime`, or later launches die with a root-owned `PermissionError`. Never
   `import sglang` from a `pre_exec` mod (flashinfer JIT writes root-owned files).
6. **Internal IPs stay out of tracked files** (tracked = shipped to nodes and third parties). Keep them
   in `.local/CONFIDENTIAL.md` vars and `COOP.md` (untracked).
7. **This tree is syncthing-shared with a live second writer.** Never `git add -A`, directory adds, or
   bare globs. Use explicit pathspecs and review `git diff --cached --stat`.
8. **Mods fail closed**; a launch log is not the server log.

---

## 4. The action plan — parallel workstreams

The cluster bottleneck means the genuinely parallelisable work is **off-cluster** (research,
instrument/reproducer design, docs, upstream contact), interleaved with **serialised cluster arms**.
Legend: **C** = needs the cluster (serialize, one at a time); **O** = off-cluster, parallel-safe.
Each deliverable is a committed file or a `bench_*` id — never a chat sentence.

| ID | Workstream | C/O | Prereq | Deliverable / done-when |
|---|---|---|---|---|
| **WP1** | **Multi-node TP=2 boot** — the only open path to material throughput gain (halving weight-read time). | C | add `recipes/cybersec/mods/fix-fastsafetensors-tp2-sglang` to the recipe's `mods:` chain | First real TP=2 (`--tp 2` across the free pair) number, or a captured boot failure. **Highest value.** Re-run the TP=2 arm *only* with the fix mod mounted; WORK §5 records the exact failure without it. |
| **WP2** | **Docs consolidation / lane README** — give the lane a distribution-facing entry point and condense sprawl. | O | — | **In progress:** `README.md` created. Owed: condense `QWEN3-EMBED-OPTIMIZATION-WORK.md` §8 (process notes) and `EMBED-JOURNAL.md` (≈80–90 % superseded by the WORK doc) into a short process appendix; migrate narrative to the journal. |
| **WP3** | **Traffic-shape decision support** (§6 item B) — gates whether the shipped `mamba_full_memory_ratio: 3.51` should change. | O/C | user policy input on target traffic mix | A stated target mix, or a memo mapping {4k, 8k, 16k-heavy} → ratio. **Blocked on policy, not data.** The measured table exists: ≈3.6 at 4k, ≈2.3 at 8k, ≈1.2 at 16k (WORK §12.9/.15/.24). Do **not** change the default unilaterally. |
| **WP4** | **Image/manifest digest pinning** (§6 item 7). | O | registry manifest digest | The correct digest pinned in the recipe, or a memo stating why local-config digests were rejected (WORK §6.2 item 7 spells out the wrong-digest hazard). |
| **WP5** | **Drop `cluster_only:`** (§6 item 8) — the validator shows it constrains nothing. | O | — | Removed from both recipes; `sparkrun recipe validate` still exit 0; sibling discipline checked. |
| **WP6** | **Depth-cost frontier** — resolve the `tg`-vs-`peak` disagreement and the acceptance instrument. | O first | — | First pass is **zero-boot**: re-analyse archived JSONs for §12.49's `c=4`/`c=8` repeat (§12.55) before scheduling anything. New arms need the §12.53 length rule (`≥ ~2,500` generated tokens). DEPTH-COST §12.36/.49/.53/.55. |
| **WP7** | **Does the GDN path suit multi-node at all?** | O | — | A memo: are the Triton-GDN kernels on SM121 compatible with the offload/TP sharding WP1 would introduce? WORK §12.7 (both CuTe-DSL gates exclude major 12). Feeds WP1's go/no-go. |
| **WP8** | **README `t/s` column annotation** (§6 item 9). | O | — | A repo-wide annotation marking the column non-comparable; one recipe legitimately spans 15–121 t/s (WORK §10). |
| **WP8b** | **Qwen3-VL embed/rerank sizing** — correctness is shipped, performance gap is open. | C | — | Measured colocation cost as a fixed capacity charge, or a decision to accept it. SPECULATIVE cap of 4 images; D5 page-cache rationale is `FALSE` though the feasibility survives (EMBED §6/§7). |
| **WP9** | **Sprawl hygiene** (this file's §6). | O | — | Keep `recipes/qwen3/` to shipped recipes + guides; move dead arms/docs to `attic/qwen3/`. README-declared NOT-RUN arms archived this session. |
| **WP10** | **Doc-drift reconciliation** | O | — | Fix the stale doc self-descriptions and the `recipes/ifm/COOP.md` test failure listed in §7. |

**Sequencing for a single free pair (cheapest first):** WP4/WP5/WP8 and **WP6's zero-boot analysis**
and WP2/WP7/WP9/WP10 are all off-cluster and can run immediately/parallel. Cluster work serialises:
**WP1** (add the mod, one TP=2 arm) → **WP8b** (VL sizing) → any **WP6** boot the zero-boot pass leaves
open. Post every result (including failures) to `COOP.md` before releasing the lock.

**Out of scope / closed — do not re-open** (see `ANSWERED-QUEUES.md` before queueing anything):
`--enable-linear-replayssm-spec`; `z-lab` vs `incoai` draft A/B (same blob); `dev-qwen38-27b-dflash2`
container; raising `runs` to fix spec variance; the sub-4k depth bump; KV-bandwidth GB/s figures;
`max_num_seqs: 48` (never granted). **Search `ANSWERED-QUEUES.md` by profile name first** — an
experiment has been re-run at 8 boots' cost for lack of a recorded profile name.

---

## 5. Coordination mechanism

[`COOP.md`](COOP.md) is the cross-agent ledger. The protocol (full text in that file):

1. **Claim before you work** — add your agent id + workstream to the ownership table.
2. **BENCH LOCK** — one line in Live state before launching; remove it when done.
3. **One dated entry per finding**, with its evidence pointer; never delete another agent's entry.
4. **Post failures too** — one line saves the other agents a boot.
5. **No third coordination file.**

**Success condition:** no two agents spend a boot answering the same question, and no agent acts on a
node, recipe, or profile another agent has claimed.

---

## 6. Sprawl reduction (secondary task — running log)

Policy: `recipes/qwen3/` is a shipped artifact. **Keep** the shipped/support recipes and the guides.
**Archived arms/docs go to `attic/qwen3/`** (tracked, never lost) with a manifest row. A profile whose
recipe no longer exists is dead. **Condense, do not just delete** — before moving a file confirm
nothing live references its name and its finding is preserved in a `§N` section or manifest.

Done this session:
- Archived 4 README-declared **NOT RUN / dead** `benchmarking/` arms to `attic/benchmarking/` with
  manifest rows: `kv-residency-dissociation`, `pp-sweep-c4c8`, `a2-depth-gap-c8`,
  `d0-baseline-dissociation`. (`a2-depth-gap-c8`'s design intent remains cited by `§N` refs to the
  attic copy — the citation, not the profile, is load-bearing.)
- **Redacted internal addresses** from the three qwen3 docs that are **not** git-ignored
  (`DEPTH-COST.md`, `SSM-STATE-DTYPE.md`, `ANSWERED-QUEUES.md`): internal node addresses → role names
  (`the head node`, `node-restricted-N`, `node-free-N`), operator home paths → `/home/<operator>/…`.
  These had
  tracked-intent and 21 full-IP plus ~60 shorthand `.<octet>` references — a violation of the root
  convention that `tracked = distributed to nodes and third parties` (the qwen4 lane redacted its
  archived docs for the same reason). `WORK`/`JOURNAL` are git-ignored and were left as-is. Arithmetic
  identities and `§N` cross-references re-verified after the edit (`doc_check.py`, `doc_arith.py`).
- Unstaged an accidental `tests/__pycache__/` (18 `.pyc`, unrelated to qwen3) from the shared git
  index — per root `AGENTS.md` `py_compile` leaves untracked `__pycache__/`.
- Added [`README.md`](README.md) (human/lane summary) and [`NOTES.md`](NOTES.md) (agent entry point).

**What is deliberately retained, not deleted (the docs are the evidence).** `WORK` / `DEPTH-COST` /
`SSM` / `ANSWERED-QUEUES` are large *on purpose*: they hold the derivation trail, the retraction
banners, and the negative results that stop an experiment being run a third time (the file headers say
so). Sprawl policy here is **relocate and index**, not delete — a `§N` citation must keep resolving.

Candidate list for the next pass (needs a README/manifest edit — **not** an unannounced move):
- `benchmarking/acceptance-vs-depth.yaml` — `ANSWERED-QUEUES` A5 records its question answered and
  "should not be run"; it also has a shape defect (the `metadata.description` block is indented under
  the `framework:` key, 31 lines). Verify it loads before touching.
- Narrative-vs-decision split in `QWEN3-EMBED-OPTIMIZATION-WORK.md` (~25–35 % condensable) and
  `EMBED-JOURNAL.md` (~80–90 % superseded).
- `.scratch/` is large (~150 MB of qwen3 artifacts) and untracked; prune only with a manifest of what
  is being discarded and what `§N` cites it.

---

## 7. Known drift (fix when touched)

- **The local (sandbox) registry cache is a stale clone — `sparkrun show <name>` can lie.**
  `HOME=.local/sparkrun-home` gives sparkrun a cached copy of the registry at
  `.local/sparkrun-home/.cache/sparkrun/registries/littlecedar/` that is a **clone from 2026-09-27**.
  It resolves by *name* from that cache and reported `speculative_draft_tokens: 4` for the shipping
  recipe, while the working tree (and `git HEAD`) say `8`. `sparkrun recipe validate <path>` reads the
  path directly and is correct, so **validate by path**; but **do not trust `sparkrun show/run <name>`
  off the sandbox cache** — run from the head node (whose tree is synced) or refresh/remove the cache
  first. This cost a scare during the 2026-10-04 session and is exactly the class of defect the
  "prove a flag reached the server" rule exists for.
- **`recipes/ifm/COOP.md` — RESOLVED 2026-10-07.** The file was lost from the working tree; it is now
  reconstructed from the lane's surviving documents and cross-references (its own header records
  that), and `tests/test_ifm_recipes.FilesExist.test_coordination_and_docs_present` passes again.
  (Test counts elsewhere in this file predate the DS4/engram suites — re-measure, do not quote 328.)
- **Doc self-descriptions are stale by design but wrong today:** `DEPTH-COST.md` line 5 says it holds
  "§12.22–12.52" while its highest section is §12.55 (the range "is not maintained by hand");
  `QWEN3-MODEL-OPTIMIZATION-WORK.md`'s Contents/§12 pointer still describes §12 as "65 % of this
  file". Low priority; fix during WP2.
- **`DEPTH-COST.md` says `acceptance-vs-depth.yaml` "should not be run"** while the profile still sits
  in the curated `benchmarking/` library (see §6 candidate list).
- `WORK §12.24` records that the phase-10 logs no longer exist, so its "predicted 18 / measured 18"
  agreement is **status-unknown, not validated**. Do not cite it as model validation.

---

## 8. Validation ritual (after every edit)

```bash
set -e
H=$PWD/.local/sparkrun-home
uv run python -m unittest discover -s tests
for f in recipes/*/*.yaml; do HOME="$H" sparkrun recipe validate "$f" >/dev/null; done
for s in mods/*/*.sh; do bash -n "$s"; done
for p in mods/*/*.py tools/*.py; do uv run python -m py_compile "$p"; done
find mods tools -name __pycache__ -type d -exec rm -rf {} +
```

Use **plain** `validate`, not `--strict` (accepted warnings exist on shipped recipes). `py_compile`
leaves untracked `__pycache__/` — clean it and **never stage it**. Current baseline: 328 tests, 1
pre-existing IFM failure (§7).

---

## 9. Open questions — pointer, not a copy

For the current answer to any question, read the `§N` section; this file does not duplicate the
evolving detail. The live queue is `WORK §6.1` (items B, 7, 8, 9 → WP3/WP4/WP5/WP8) plus the
depth-cost frontier (WP6) and the embed/rerank sizing gap (WP8b). Everything else has a verdict in
`ANSWERED-QUEUES.md` or a closed-arm row in `WORK §5`.