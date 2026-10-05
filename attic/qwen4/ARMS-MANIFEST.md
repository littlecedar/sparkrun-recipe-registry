# `attic/qwen4/arms/` — archived Qwen4 recipes

**What this is.** Every Qwen4 recipe that is **not part of the production surface** in
`recipes/qwen4/`. `recipes/qwen4/` now ships exactly four recipes (the balanced base, Lane A
high-concurrency, Lane B long-context, and the RadixArk quality reference) plus its guides — the same
convention the `ds4` lane uses. Everything else lives here, **tracked** (so it is never lost) because
a `bench_*` id is the provenance of a result and the recipe file is convenience for reading what that
id ran.

**Why they are here, not in `recipes/qwen4/`.** `recipes/qwen4/` is a shipped artifact (distributed
over git to nodes and third parties). An arm variant whose finding is closed, a contributor recipe we
do not run, or an alternative-runtime recipe nobody benchmarks is clutter there and a hazard to the
next reader, who cannot tell a live recipe from a dead one. See `recipes/qwen4/AGENTS.md` §8 (sprawl
policy).

**Archive criterion.** A recipe came here if it is **not a production lane** and its filename is named
by **no live benchmarking profile** in `benchmarking/` (checked by literal `grep -rF`; the two
`zz-*-metrics` instrumented arms failed this test and were **kept** in `recipes/qwen4/` through the
first harvest wave, then moved here in the second wave *together with* the benchmarking cleanup —
i.e. they are here now because the production directory was narrowed to the four shipped recipes, not
because their profiles were deleted). Nothing in `recipes/`, `benchmarking/`, `tools/`, or `tests/`
globs `recipes/qwen4/*.yaml` in a way that a move breaks. **Do not re-add these to `recipes/qwen4/`;
run them by path from here.** `sparkrun` runs a recipe by path, and `AGENTS.md` §6 shows the by-path
invocation.

## Manifest

### Wave 1 — `zz-` experiment variants (archived 2026-10-04, first harvest)

| file | parent | one-line delta | why archived |
|---|---|---|---|
| `zz-labq-bisect-fp8triton.yaml` | labquant | appends `--fp8-gemm-backend triton` | §7 bisect ladder complete; no profile references it |
| `zz-labq-bisect-loadauto.yaml` | labquant | `load_format: auto`, drops prefill-graph-disable | superseded; the loader question is closed (§11) |
| `zz-labq-bisect-nomoe.yaml` | labquant | drops `--moe-runner-backend flashinfer_cutlass` | superseded; the backend requirement is established (§7g) |
| `zz-labq-bisect-nospec.yaml` | labquant | removes the 5 `--speculative-*` keys/flags | **duplicate** of `zz-lq-nospec-matched.yaml` (only `metadata.description` differs) |
| `zz-labq-nospec-meas.yaml` | labquant | no-spec, for acceptance measurement | **duplicate** of `zz-lq-nospec-matched.yaml` |
| `zz-labq-prefilloff.yaml` | labquant | *claims* prefill-graph-off; **implements none** | **duplicate of the labquant parent** after comment-stripping; the arm it names cannot be built by override (§7f) |
| `zz-lq-specflagcheck.yaml` | labquant | *claims* a spec-flag check; **implements none** | **duplicate of the labquant parent**; a re-labelled copy |
| `zz-rk-steps1.yaml` | RadixArk | `speculative_num_steps 3→'1'`, draft tokens `4→'2'` | steps=1 arm measured (journal `bench_b11ea1185538`); superseded |
| `zz-rk-steps1-metrics.yaml` | RadixArk | as above + `--enable-metrics` | as above; instrumented steps=1 arm |

### Wave 2 — closed-question arms (archived 2026-10-04, second harvest)

These were live arms in `recipes/qwen4/` through the 2026-10-04 morning session. They are archived
now because the question each answers is **closed** and the finding is captured in the WORK doc.
Several **are** cited by narrative sections of `WORK.md`/`JOURNAL.md` — that is expected and fine: the
archive keeps the file so the citation still resolves.

| file | parent | one-line delta | why archived | finding lives in |
|---|---|---|---|---|
| `zz-rk-fp8kv.yaml` | RadixArk | `kv_dtype: fp8_e4m3` only | **W1 CLOSED — config-level NO.** Boots, allocates an fp8 pool (`#tokens 2728960`), then dies in CUDA-graph warmup: `ValueError: unsupported SM121 QSA call` (SM121 QSA decode needs BF16 queries). Do not re-open. | WORK §15; `.scratch/q4/boot-evidence/w1-fp8kv-logs/` |
| `zz-rk-nospec.yaml` | RadixArk | removes the 5 `--speculative-*` keys/flags | NEXTN acceptance measured on both checkpoints; the spec-vs-nospec ablation is spent. | WORK §6 item 0 |
| `zz-rk-nospec-matched.yaml` | RadixArk | as above, matched-profile variant | duplicate/of the same spent ablation | WORK §6 item 0 |
| `zz-lq-nospec-matched.yaml` | labquant | no-spec labquant arm | spent ablation; still referenced by `tools/gate-37111-design.md` as a control (citation preserved) | WORK §6 item 0 |
| `zz-labq-fastboot-sglang.yaml` | labquant | `fastsafetensors` + `0.91` mem-fraction (W13 infra variant) | W13 delivered as an infra variant, documented NOT a comparison arm, and never booted. Shipped default stays on `safetensors`. | WORK §6 item 12; this session's NOTES |
| `zz-labq-iscale-radixark.yaml` | labquant | `mods/fix-labquant-expert-input-scale` (the `input_scale` arm) | Coherence **FAILED**; this is the arm whose out-of-band write contaminated the shared runtime cache (WORK §7l). No live profile names it (`bench_66600aa2c662` is the provenance). | WORK §7l |
| `zz-labq-iscale-clamp-median.yaml` | labquant | sibling of the above (variant iscale arm) | Same closed `input_scale` line; no live profile names it. | WORK §7l |

**Do not resurrect any of wave 2 without re-reading its "finding lives in" section first** — each was
closed on evidence, and several close **negatively** (fp8 KV, TRTLLM MoE).

**One candidate was REVERTED out of wave 2 on audit.** `zz-rk-moebackend.yaml` was moved here and
then moved back to `recipes/qwen4/`, because three **live** benchmarking profiles still name it —
`benchmarking/bs-sweep-high.yaml:63`, `benchmarking/rk-nograph-cps8192-k8-16-24.yaml:11,13,24`, and
`benchmarking/lq-graphson-cps8192.yaml:10`. It is the arm §19x's `bench_rk_moebackend`-family boots
ran against ("a replication, not an isolation" — §6 PRIORITY-1 gate iv). **It is back here in wave 3
below**, once the production directory was narrowed to the four shipped recipes. The three profiles
that name it are instrumentation profiles, not production runs; a `bench_*` id citing the arm still
resolves, but no *production* launch reaches for it.

### Wave 3 — production-directory narrowing (archived 2026-10-04, third pass)

`recipes/qwen4/` was narrowed to its **production surface only** (the ds4-lane convention: guides +
shipped recipes). These recipes are not experiment variants; they are contributor recipes,
alternative-runtime recipes, and instrumented measurement arms that were simply not part of the
production set. They are archived here, tracked, with their provenance.

| file | checkpoint | runtime | why archived |
|---|---|---|---|
| `zz-lq-metrics.yaml` | labquant | sglang | Instrumented (`--enable-metrics`) arm; cited by ~6 instrumentation profiles (e.g. `instr-cps4096-vs-2048-k16.yaml`), but not a serving recipe. |
| `zz-rk-metrics.yaml` | RadixArk | sglang | Same, RadixArk; cited by ~5 instrumentation profiles incl. `pool128-cap32-causal-REPL.yaml`. |
| `zz-rk-moebackend.yaml` | RadixArk | sglang | The `--moe-runner-backend` arm (§7g); named by 3 instrumentation profiles. Back to the archive now that the production dir is narrowed. |
| `eugr-qwen3.8-flash-next-nvfp4-radixark.yaml` | RadixArk | vllm-distributed | Contributor recipe (eugr); a third-party vLLM path, not our sglang serving lane. |
| `eugr-qwen3.8-flash-next-nvfp4-cluster.yaml` | RadixArk | vllm-distributed | Contributor recipe (eugr); cluster variant. |
| `qwen3.8-flash-next-nvfp4-vllm.yaml` | RadixArk | vllm-distributed | Cross-runtime competitor; never benchmarked (W12). |
| `qwen3.8-flash-next-labquant-tp4-sglang.yaml` | local-inference-lab | sglang | TP=4 arm; never produced a number (§6 item 1b). Recovered from git HEAD (the live writer had staged its deletion). |
| `ursuciprian-qwen3.8-flash-next-nvfp4-fastqsa4096bigkv-g8-sglang.yaml` | RadixArk | sglang | Contributor recipe (ursuciprian); carries a **non-portable** host bind-mount (`executor_config.volumes`), so it is not shippable as-is. |

Parent assignment and exact deltas are from `.scratch/q4/recipe_manifest.md` (produced by direct
diff of the parsed documents, not by filename inference) and are reproduced here so the manifest can
be deleted if the scratch tree is reaped.

## Provenance notes

- `zz-labq-prefilloff.yaml` and `zz-lq-specflagcheck.yaml` are **misleading by name**: they promise a
  delta their config does not contain. They are archived rather than deleted precisely because that
  contradiction is itself a finding (a "variant" that is the parent is how a null result gets
  reported against a configuration that was never under test — the `launch.sh --match-bench` guard
  exists for the same failure).
- `zz-labq-bisect-nospec.yaml`, `zz-labq-nospec-meas.yaml`, and `zz-lq-nospec-matched.yaml` are the
  same arm under three labels (4 duplicate pairs among the original 16, per the scratch manifest).
- **The lane's research record, journal, and coordination ledger also live in this archive directory**
  (`QWEN4-MODEL-OPTIMIZATION-WORK.md`, `JOURNAL.md`, `COOP.md`) plus the report memos under
  `status/`. The record and journal are git-ignored (they hold internal IPs); `COOP.md` was
  IP-redacted before archiving so the tracked copy carries node *roles*, not addresses. Keep new
  hostnames/IPs out of anything tracked (root `AGENTS.md`).

*Archived 2026-10-04 by the harvest/consolidation sessions. If you resurrect one of these, move it
back to `recipes/qwen4/` and remove its row here.*