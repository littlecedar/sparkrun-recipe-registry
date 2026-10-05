# Qwen4 — `recipes/qwen4/` agent & developer guide

Condensed, durable operating guide for the Qwen3.8-Flash-Next lane. This is the **entry point** a
new session should read first; it holds the current state, the constraints that bite, and the
**action plan divided into parallel workstreams**. Everything long-form now lives in the **archive**,
[`../../attic/qwen4/`](../../attic/qwen4/): the research record
(`QWEN4-MODEL-OPTIMIZATION-WORK.md`, git-ignored, `§N` cite-target), the journal (`JOURNAL.md`,
git-ignored), the cross-agent ledger (`COOP.md`), the status memos (`status/`), and every archived
recipe arm (`arms/`, with [`ARMS-MANIFEST.md`](../../attic/qwen4/ARMS-MANIFEST.md)). See
[`README.md`](README.md) for the recipe/lane summary.

> **Reading order for a new agent:** this file → `README.md` (the recipes) → `attic/qwen4/COOP.md`
> (workstream ledger) → the `§N` sections named next to your workstream. Do **not** re-read the
> 11k-line WORK doc front-to-back; it is written for targeted lookup.

> **Provenance discipline is the house rule.** Every claim carries a confidence label
> (`VERIFIED` / `LIKELY` / `SPECULATIVE`), a source (`file.py:line`, a bench id, a boot log) or an
> explicit "unmeasured". A confident unsourced sentence is a defect. See WORK doc §8 (retraction
> register) before repeating any number from an old section — several were withdrawn.

## 1. Mission and current state

Produce and defend the highest-quality, highest-throughput `sparkrun` recipes for the
Qwen3.8-Flash-Next (180B MoE, hybrid GDN + full attention, PLE n-gram table) checkpoint on a 2-node
DGX Spark (GB10) TP=2 pair. **Quality outranks throughput** — a config that is 10% faster and
occasionally emits garbage is a regression (WORK §14).

**Shipped recipes.** The lane now ships **two production TP=2 lanes** off the labquant checkpoint,
plus the balanced base they derive from and the RadixArk quality reference:

| recipe | role |
|---|---|
| `qwen3.8-flash-next-nvfp4-labquant-sglang.yaml` | **balanced base + control** (cap 24 / pool 112 / ctx 262144) |
| `qwen3.8-flash-next-nvfp4-labquant-highcon-sglang.yaml` | **Lane A — high concurrency** (cap 32 / pool 128) |
| `qwen3.8-flash-next-nvfp4-labquant-longctx-sglang.yaml` | **Lane B — long context, up to 1M** (YaRN route) |
| `qwen3.8-flash-next-nvfp4-sglang.yaml` | RadixArk **quality reference** (vision intact) |

Each lane differs from the base in one or two `defaults` knobs only; the checkpoint, container
digest, and 7-mod chain are identical. **See [`README.md`](README.md) for the lane rationale and the
measured numbers.** Those four are the **entire** production directory. Everything else that used to
live here is archived under `../../attic/qwen4/arms/` (§8): the contributor recipes (`eugr-`,
`ursuciprian-`), the cross-runtime `…-vllm` recipe, the never-benchmarked TP=4 attempt
(`qwen3.8-flash-next-labquant-tp4-sglang.yaml`), and the two `zz-*-metrics` instrumented arms.

**Best measured state** (all `VERIFIED`, WORK §3/§4/§19 unless noted):

| quantity | value | note |
|---|---|---|
| RadixArk d=0 decode, k=1 | **37.973 tok/s** | §4, ≥7 runs |
| bs=8 vs bs=1 (aggregate) | **+119%** (80.57 vs 36.77) | §19; per-request falls to 15.76 tok/s, TTFT 2087→5579 ms |
| peak aggregate (d=8192) | RadixArk **86.86** @ k=16, labquant **91.38** @ k=16 | both fall ~38% at k=24 |
| decode model | `t_step = F + bytes/B`, `B = 145.5±0.8 GB/s`, `F = 8.375 ms/step` | §3; out-of-sample reproduced to 1% |
| NEXTN acceptance | `A = 2.18` (RadixArk n=21) / `2.1924` (labquant n=7) | indistinguishable; flat in batch |
| mamba pool 128 vs 112 | **+11.1%** at cap32/cps8192/d8192/k24 | §19x/19y; mechanism **unestablished** |
| `max_num_seqs` 24→32 (RadixArk) | **+0.42 GB** intermediate scratch, **−4.55%** KV, boots fine at cps 4096 | §19z; `capped to 28` — the mamba slot pool is the ceiling |
| fp8 KV pool vs bf16 (RadixArk) | `2728960` vs `1460864` tokens = **1.87×** (not 2×) | §15; moot — fp8 KV cannot serve |
| labquant quality vs RadixArk | **35/36 vs 37/38**, 0 disagreements on 36 shared tasks | `W3-QUALITY-EVAL-STATUS.md`; n=1, battery drifted 36→38 |

**Levers that are answered — do not re-litigate.** `--max-prefill-tokens 32768` is a null on both
checkpoints (§6 PRIORITY-1 ii). `chunked_prefill_size 8192` helps k=24 but **regresses k=8/k=16 on
the shipping labquant checkpoint** and is **not adopted**; keep 4096 (§6 PRIORITY-1, §19c).
`--cuda-graph-backend-prefill disabled` is **mandatory** for labquant, not a tunable (§7f).
`--moe-runner-backend flashinfer_cutlass` is **required** for labquant (`auto` → FLASHINFER_TRTLLM,
dead on SM121, §7g). The CUDA-graph observability bundle is closed (§5). **`kv_dtype: fp8_e4m3` is a
config-level NO** — it boots and allocates an fp8 pool but the SM121 QSA decode kernel requires BF16
queries and raises in CUDA-graph warmup (§15, closed 2026-10-04). `max_num_seqs` above the mamba
slot pool's ceiling buys nothing, and 24→32 costs +0.42 GB of intermediate scratch for −4.55% KV
(§19z).

**Two operational facts that each cost a boot (do not rediscover):**
1. **The checkpoint pin key is `model_revision:`, not `revision:`.** sparkrun reads the former
   (`core/recipe.py:346`) and silently ignores a bare `revision:`, so the distribution would pull
   `main` while the mod chain is pinned to `7c4f1bc1…` and the boot dies in
   `unpack-labquant-ple-nvfp4-to-fp8`. This was a live shipping defect, fixed 2026-10-04 (§7 top box).
2. **Run a recipe by name from the run-from dir, not by absolute path.** `sparkrun run <abs-path>`
   resolves `mods/<name>` relative to `recipes/qwen4/` (no `mods/` there) and fails; symlink the
   recipe into `~/development/` and run it by name, where `mods → …/sparkrun-recipe-registry/mods`
   resolves.

**The two lane knobs, and why (VERIFIED — full detail in `README.md` and WORK §19):**
- *High concurrency (Lane A):* `max_num_seqs` must be **strictly above** every served `k` (at
  `k == cap` the batch saturates at `cap − 1` with one request queued and per-request decode loses
  ~6%), and the **effective admission ceiling is the mamba pool**, `max_mamba_cache_size // 4` on the
  lazy strategy — pool 112 → 28, pool 128 → 32. Raising 112 → 128 is associated with ~13% more k=24
  throughput at matched config (`zz-rk-metrics`, four boots); **mechanism unestablished**. Keep
  `chunked_prefill_size: 4096` — 8192 regresses k=8/k=16 on labquant.
- *Long context (Lane B):* raising `--context-length` past the checkpoint's 262144 **raises
  `ValueError` unless `SGLANG_ALLOW_OVERWRITE_LONGER_CONTEXT_LEN=1`** is in the container env
  (`model_config.py:860`), so that `env:` value is **load-bearing** and travels with `max_model_len`.
  The 1M route also needs the YaRN `--json-model-override-args`, and **its quality is unmeasured**
  (see WORK §15; a neighbouring needle test failed at 300k). `--context-length 262144` is the
  quality-safe point.

## 2. Where the evidence lives

| artifact | location (control ↔ head) | lifetime |
|---|---|---|
| Research record | `attic/qwen4/QWEN4-MODEL-OPTIMIZATION-WORK.md` (`§N`) | git-ignored, backed up out-of-band |
| Narrative log | `attic/qwen4/JOURNAL.md` | git-ignored |
| Coordination ledger | `attic/qwen4/COOP.md` | IP-redacted; the live node assignment stays node-side |
| Status memos (W3/W4/W8) | `attic/qwen4/status/` | archived reports |
| Archived arms | `attic/qwen4/arms/` (+ `ARMS-MANIFEST.md`) | every non-production recipe, with provenance |
| Benchmark results | `~/benchmarks/<TAG>_<date>/` on head (path-keyed, durable) **and** `~/.cache/sparkrun/benchmarks/bench_*/` | the `bench_*` dir is scratch and **gets reaped**; a relaunch reusing an id **clears `runs/`** |
| Per-boot config of record | `bench_*/state.yaml` (`recipe_qualified_name`, `extras.measurement_overrides`) | same as above |
| Arm launcher | `.scratch/q4/launch.sh` | the guarded generic launcher, replaces ~40 one-off scripts |
| Scratch helpers | `.scratch/q4/` (~hundreds of files) | not authoritative; cite `bench_*` and the WORK doc |

**A result has no provenance without its `bench_*` id.** The `.json`/`.csv` carry model + throughput
only — no recipe, no serve command. State an arm's config from its own `state.yaml`, never from a
sibling's or from memory (`launch.sh` `--match-bench` enforces this). To analyse, read the named JSON
fields and select the phase with `is_context_prefill_phase`; never quote the printed sparkrun table
(`benchmarking/README.md` rule 2).

## 3. Hard constraints

1. **Node allowlist.** The tasking names the free trial/benchmark nodes for the session and the
   restricted ones. **The current session's assignment is recorded in the archived `COOP.md`
   "Live state" row** (and must be re-checked each session). Resolve hostnames to addresses and
   compare before acting. Never assume node `.30` (the NFS/HF head) is available — touching a serving
   node stalls every boot on the fleet. (Historical fixpoint: an earlier session crashed a node; the
   operator accepts occaisional alpha-software crashes but this is not a licence to treat restricted
   nodes as free.)
2. **One cluster job at a time.** The free pair supports exactly one TP=2 arm; cluster time is the
   scarcest resource here. Queue cluster work in `COOP.md` and claim it before launching. `launch.sh`
   already aborts when a `sparkrun` job is live.
3. **Portability (user rule).** Every recipe must rely on sparkrun's own detection. No recipe `env`
   value may name a host device (`rocep|enp|ens|enP|eth` + digit) and none of
   `orchestration/infiniband.py:MANAGED_COMM_ENV_KEYS` may be set. `mods/make-roce-env` is for legacy
   runners, **not** for sparkrun recipes.
4. **Mods run as root (uid 0); the server runs as uid 1000** in the same persisted per-model runtime
   cache. Any file a mod creates there must be `reown`ed to `stat -c '%u' /cache/runtime`, or every
   later launch of that model key dies with a `PermissionError` that persists. **Do not `import
   sglang` (or any JIT-heavy lib) from a pre_exec mod** — flashinfer JIT writes root-owned files
   (WORK §16, `.swival/memory/sparkrun-notes.md`).
5. **`mods:` is an ordered dependency chain**, not a set. Reordering yields a checkpoint tree that
   boots, answers, and is numerically wrong (the labquant 7-mod list must keep `fix-labquant-…-schema`
   first and `demote-labquant-…-bf16` last).
6. **Model distribution.** Each node's HF cache is node-local and models must be distributed
   (`distribution_config.models.enabled: true`); the failure mode is a bare `missing config.json`.
   Cluster `distribution:` blocks override the recipe.
7. **This tree is syncthing-shared with live writers.** Use explicit `git add -- <path>` pathspecs;
   never `git add -A`, directory adds, or bare globs. Review `git diff --cached --stat`.
8. **Internal IPs and hostnames stay out of tracked files.** Tracked = shipped to nodes and third
   parties. Keep operator/head values in `.local/CONFIDENTIAL.md` shell vars; keep the live node
   assignment node-side, **not** in this file. (The archived `attic/qwen4/COOP.md` was redacted for
   exactly this reason.)

## 4. The action plan — parallel workstreams

The cluster bottleneck means the genuinely parallelizable work is **off-cluster** (research,
instrument design, reproducer code, docs, upstream contact), interleaved with **serialized cluster
arms**. Status changes should be recorded in the lane notes; each workstream's *deliverable* is a
committed file or a `bench_*` id, never a chat sentence.

Legend: **C** = needs the cluster (serialize); **O** = off-cluster, parallel-safe.

| ID | Workstream | C/O | Prereq | Deliverable / done-when |
|---|---|---|---|---|
| **W1** | **fp8 KV cache — capture the real failure** (§6 item 4) | C | none | **CLOSED 2026-10-04 — config-level NO.** `sparkrun run` captured the error on both nodes: `ValueError: unsupported SM121 QSA call …` in CUDA-graph warmup (the SM121 QSA decode requires BF16 queries). Evidence: `.scratch/q4/boot-evidence/w1-fp8kv-logs/`; §15. **The prior "fabricated root cause" verdict was itself wrong** — the error is real and reproducible; the rule is *re-run before retracting*. |
| **W2** | **EXL3 (turboderp 3.05bpw) go/no-go decision** (§6 item 14) | O | — | **CLOSED 2026-10-04 — NO-GO** (policy/topology). Memo: `.scratch/q4/exl3/W2-EXL3-GO-NO-GO.md`. The published route is TP=1 single-Spark only; every qwen4 recipe is TP=2/4, and the numbers are MTP-inflated. The memo's cross-checks (BF16-KV QSA refusal, the exact-163,840-token MTP acceptance cliff, needle exact at 240k / miss at 300k) **corroborate §15 and are a lead on blocker (f)** — read them before re-opening. |
| **W3** | **Quality eval for the labquant export** (§6 item 5) | O | — | **Advanced 2026-10-04: eval built and run.** `tools/qwen4-quality-eval.py` (38-task fixed battery, selftest green) + `attic/qwen4/status/W3-QUALITY-EVAL-PLAN.md` + `…-STATUS.md`. Live paired: RadixArk **35/36**, labquant **37/38**, **0 disagreements on the 36 shared tasks**. n=1 and the battery drifted 36→38 between runs — re-run on one frozen battery before quoting. Not a certifying accuracy measurement. |
| **W4** | **#37111 silent-decode-corruption gate** (§6 item 11, §14) | O→C | reproducer code | **Built 2026-10-04: `tools/gate-37111.py`** (selftest green, 5 negative controls) + `tools/gate-37111-design.md` + `attic/qwen4/status/W4-GATE-STATUS.md`. Live smoke **PASSED** (warm==cold canary correct) — a negative result, not proof. The 1–2 h / ~100k release soak is still owed. |
| **W5** | **The `max_num_seqs` ↔ KV-capacity trade** (§19n/§19o/§19x) | C | none | **Measured 2026-10-04 (§19z).** cap 24→32 = +0.42 GB intermediate scratch, −4.55% KV, and it **boots** at `cps 4096`. Mechanism VERIFIED: scratch ∝ `spec_state_size = max_running_requests` (`kv_cache_configurator.py:489`). `capped to 28` at cap 32 → the mamba slot pool, not `max_num_seqs`, is the ceiling. Residual: the `cps=8192 + cap=32` non-boot (§19o) is untested. |
| **W6** | **TP=4 under SGLang** (§6 item 1b) | C | fix `attic/qwen4/arms/qwen3.8-flash-next-labquant-tp4-sglang.yaml` first (moved to the archive in the production-dir narrowing) | First real TP=4 number, or a captured boot failure. Relaunch with `readiness.port_timeout_s: 3600`, without the two known-bad TP>2 knobs. |
| **W7** | **MoE/kernel ceiling probes** (§6 items 2, 9) | C | — | Time `torch._grouped_mm` (present, **still untimed** — its argument contract rejects the naive shapes, so the real SGLang MoE layout is needed; a *dedicated* container works, a shell in a *serving* container OOMs on `set_device(0)`); and A/B `--fp4-gemm-backend`. Current `flashinfer_cutlass` was inherited from vLLM without justification. |
| **W8** | **Upstream engagement** (§14) | O | W4 reproducer | **Drafted 2026-10-04: `attic/qwen4/status/W8-UPSTREAM-DRAFTS.md`** (nothing posted — posting needs explicit authorization). Upstream states re-verified: #37111 OPEN, #38319 OPEN, #38355 OPEN/unmerged. |
| **W9** | **Long-context route (262k→1M)** (§6 item 13) | C | needle gate | **DELIVERED as Lane B 2026-10-04:** `recipes/qwen4/qwen3.8-flash-next-nvfp4-labquant-longctx-sglang.yaml` exposes the 1M route (`--context-length 1000000` + YaRN `--json-model-override-args` + the **required** env `SGLANG_ALLOW_OVERWRITE_LONGER_CONTEXT_LEN=1`, which the build needs or it *raises* rather than warns). **Quality above 262k is still UNMEASURED** — the recipe ships the route with a loud caveat and documents 262144 as the quality-safe point. The needle gate (`README`/`WORK §15` step 3) remains the prerequisite before serving 1M. |
| **W10** | **Doc & sprawl hygiene** (this file's §8) | O | — | Keep the recipes dir to shipped + live arms; move every dead arm under `attic/qwen4/` with a manifest row. |
| **W11** | **NCCL/RoCE transport confirmation** (§6 item 7) | C | a boot with `NCCL_DEBUG=INFO` | **VERIFIED 2026-10-04 that NCCL is set for RoCE**: `NCCL_NET=IB`, `NCCL_IB_DISABLE=0`, `NCCL_IB_HCA=rocep1s0f0,roceP2p1s0f0`, `UCX_NET_DEVICES=roce…:1`, HCAs `link_layer: Ethernet`/`PORT_ACTIVE`. `via NET/IB` in the ring still wants `NCCL_DEBUG=INFO` — do **not** overclaim from the env alone. |
| **W12** | **Benchmark the vLLM recipe** `attic/qwen4/arms/qwen3.8-flash-next-nvfp4-vllm.yaml` (§6 item 10) | C | — | The only legitimate same-checkpoint competitor to eugr's number, never measured. Cross-runtime, so state the engine version and digest; do not compare raw tok/s without the flag set. |
| **W13** | **`tuning_fast_boot` infra variant** (§6 item 12) | O | — | **Delivered 2026-10-04 as `zz-labq-fastboot-sglang.yaml`; now ARCHIVED to [`../../attic/qwen4/arms/`](../../attic/qwen4/arms/)** (validates; `fastsafetensors` + `0.91`; documents that it is NOT a comparison arm; never booted). Shipped default stays on `safetensors`. |

Already-closed/near-closed streams, recorded so nobody re-opens them: the **Radix chunked-insert
quality fix** exists as `mods/fix-sglang-radix-chunked-insert` with all four anchors re-verified
against the pinned image (§6 item 3) — a correctness fix, expect no tok/s change; the **shared-expert
drop** question is closed negative (§6 item 6); **NEXTN acceptance** is measured on both checkpoints
(§6 item 0) with only a deprioritised draft-weight ablation left.

**Sequencing suggestion for a single cluster pair (revised 2026-10-04):** W1, W5, and W11 are done.
Remaining cluster work, cheapest first: **W7** (kernel timing in a dedicated container) → the
**`--enable-linear-replayssm-spec`** arm (one boot, then a `gate-37111.py` soak) → **W12** (vLLM
benchmark) → **W6** (TP=4, fix the recipe first) → **W11**'s `NCCL_DEBUG=INFO` confirm. Off-cluster
W10 runs whenever the cluster is busy. **Run at most one TP=2 job at a time** — launching a second
onto the same pair leaves two jobs co-resident on `.34/.35` and the earlier one's container gets
recreated (observed 2026-10-04).

## 5. Coordination — how agents talk to each other

`attic/qwen4/COOP.md` is the cross-agent ledger (archived; IP-redacted before archiving). The
protocol:

1. **Claim before you work.** Add a row to the ownership table with your agent id and the workstream
   ID, and the date. One owner per workstream per session.
2. **One dated entry per finding**, appended under "Log", with the evidence pointer (`bench_*` id,
   `§N`, or a file:line). Do not delete another agent's entry; annotate with your evidence and date.
3. **Cluster claims are exclusive.** Add a `BENCH LOCK: <agent> <profile> <nodes> <eta>` line before
   launching and remove it when the job ends (or mark it `DONE`). Never launch while a lock is held.
4. **Shared findings go in COOP, not in a private notice.** Anything expensive to re-derive
   (a boot failure, a flag that does not reach the server, a node that is unhealthy) is a COOP
   bullet. "Post the probe result even if it fails — one line saves the other agents a boot."
5. **Cross-directory heads-ups** (a fleet-wide fact, e.g. the HF-cache topology change) also go in
   the repo-root surface if the other lanes need it; do not create a third coordination file.

The success condition for coordination is blunt: **no two agents spend a boot answering the same
question, and no agent acts on a node or recipe another agent has claimed.**

## 6. Runbook

Run from the head node (`$WOPR_HEAD_NODE`, in `.local/CONFIDENTIAL.md`) with the in-progress recipes
symlinked from `$WOPR_SRC_DIR` into `$WOPR_RUN_FROM_DIR`; the `mods` symlink must be present so
unscoped `mods/<name>` resolves to working-tree edits.

```bash
# 1. validate the recipe file (grammar only — does not check mods exist)
HOME=$H sparkrun recipe validate recipes/qwen4/<recipe>.yaml

# 2. cheapest render check: dry run, which DOES resolve mods before printing the command
HOME=$H sparkrun run <recipe> -H 127.0.0.1 -n        # grep the rendered line for your flag

# 3. a real arm — always via the guarded launcher, never hand-rolled
.scratch/q4/launch.sh <log-tag> <profile-on-head> --recipe <recipe> -o key=value
#    --preflight-only  : run every guard, launch nothing (use to TEST a guard)
#    --match-bench <id>: enforce recipe+override identity with the boot being replicated

# lifecycle
HOME=$H sparkrun status          # job ids; SCOPE teardown to the node you measured
HOME=$H sparkrun logs <job-id>
HOME=$H sparkrun stop <job-id>
```

**There is no `sparkrun up`, no `sparkrun stop all`, no `sparkrun recipe info`.** `-o` overrides
`defaults` only and only for keys the `command:` consumes through a `{placeholder}`. Read the
rendered serve line *and*, for a load-bearing flag, the live argv on the host
(`docker top` + `/proc/<pid>/cmdline`) — `state.yaml` proves a flag was *requested*, not that the
engine accepted it.

## 7. Traps that cost the most, in one place

- **`tg_throughput` at k>1 is a window metric** over submission/first-token/last-token events; the
  interpretable per-sequence quantity is `m = (t(k) − t(1))/(k − 1)` in ms/seq, not the ratio
  `G(k) = k·t(1)/t(k)` (§3c). **Quote aggregate and per-request together or neither.**
- **No single noise floor.** Read your cell's floor from §4b; several cells are bimodal. `runs: 7`
  plus a **same-window control** is the protocol; interleaved beats more runs.
- **A null from an impossible query is not evidence of absence.** Four sessions' recurring failure is
  concluding "X does not exist" from a grep whose shape could not have matched (§8).
- **A sparkrun launch log is not the server log.** A clean launch log does not mean the server came
  up; the crash text lives in the container (`/tmp/sparkrun_serve.log` on the node).
- **`launch.sh` bench-id collision:** a `--dry-run` probe *creates* the directory; a real run writes
  `state.yaml`. The id hashes the **profile path**, so a replication needs a **new profile filename**.
- **`pmproxy` leaks ~30 GB/hour** during benchmark activity (host-side, not GPU). A boot can die in
  `alloc_memory_pool` and blame the peer node. `launch.sh` gates on `MIN_AVAIL_GB`; do not lower it.
- **Mods fail closed**; verify a mod by the artifact it leaves in the runtime cache, not by its exit
  status or its log line.

## 8. Sprawl policy

`recipes/qwen4/` is a **shipped artifact and is kept to its production surface only** — the same
convention the `ds4` lane uses.

- **Keep in `recipes/qwen4/`:** the shipped production recipes (the balanced base, Lane A, Lane B,
  the RadixArk reference) and the two guides (`README.md`, `AGENTS.md`) plus the working `../../attic/qwen4/NOTES.md`.
- **Everything else moves to `attic/qwen4/arms/`** with a row in
  [`attic/qwen4/ARMS-MANIFEST.md`](../../attic/qwen4/ARMS-MANIFEST.md): every `zz-` arm, contributor
  recipe, alternative-runtime recipe, and un-benchmarked variant.
- **`attic/qwen4/`** is the quarantine zone (tracked, so it is never lost) and also holds the lane's
  research record, journal, ledger, and `status/` memos. Archived recipes may still be cited by
  `bench_*` ids — the id is the provenance, the file is convenience.
- **Naming:** `zz-` prefix is the conventional marker that a recipe exists only to define an arm
  variant, not a shippable recipe. Never ship a `zz-` file.
- **`benchmarking/*.yaml`** is also shipped and nearly all untracked; keep only profiles that are
  either run or genuinely planned-and-referenced. A profile whose recipe no longer exists is dead.
- **Internal IPs never enter the tracked `attic/`.** The record and journal are git-ignored for that
  reason; anything else archived there (e.g. `COOP.md`) is redacted first.
- **Condense, do not just delete.** Before moving a file, confirm (a) nothing in `recipes/`,
  `benchmarking/`, `tools/`, or `tests/` references its filename, and (b) its finding is preserved in
  the WORK doc / manifest.

## 9. Validation ritual (after every edit)

```bash
set -e
H=$PWD/.local/sparkrun-home
uv run python -m unittest discover -s tests
for f in recipes/*/*.yaml; do HOME="$H" sparkrun recipe validate "$f" >/dev/null; done
for s in mods/*/*.sh; do bash -n "$s"; done
for p in mods/*/*.py tools/*.py; do uv run python -m py_compile "$p"; done
find mods tools -name __pycache__ -type d -exec rm -rf {} +
```

Use plain `validate` as the gate, **not** `--strict` (accepted warnings exist on shipped recipes).
A `recipe validate` **suggestion** may be pre-existing — compare against a sibling before "fixing".

---

*This file is the condensed, maintained guide for the lane. If a fact here disagrees with a `§N`
section of `attic/qwen4/QWEN4-MODEL-OPTIMIZATION-WORK.md`, the `§N` section holds the raw evidence
and this file has a bug — fix this file and say so in the lane notes.*