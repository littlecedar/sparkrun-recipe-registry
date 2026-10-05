# COOP — `recipes/qwen4/` (Qwen3.8-Flash-Next lane)

Cross-agent coordination ledger for this lane. **Read this before launching anything.** It exists so
that two agents never spend a boot answering the same question and nobody acts on a node or recipe
another agent has claimed. This file is **not** a journal: narrative goes in `JOURNAL.md`, durable
facts go in `AGENTS.md` (condensed) or `QWEN4-MODEL-OPTIMIZATION-WORK.md` (evidentiary). This file is
git-ignored (`*` not matched by a tracked pattern; it carries the session's live node assignment), so
it is safe to put session-specific host/IP detail here — but do not let it rot into a second journal.

## Live state — UPDATE THIS EVERY SESSION

| field | value |
|---|---|
| Session date | 2026-10-04 (session 2 — cluster work) |
| Cluster pair for this lane | **node-free-1, node-free-2** — confirmed idle 2026-10-04 01:49 EDT via `sparkrun status` on head (no containers, no pending) |
| Restricted / off-limits | **the head node, node-restricted-1** (our own model is running here; head is `.30`). `.32`/`.33` are **occupied** by the DS4 serving job `a4c699c1299bbbdf_98f702a62dff` (tp=4, up 10 h, healthy) — do not disturb. |
| Head node (run `sparkrun` here) | `the head node` = **the head node** (resolved, matches `.local/CONFIDENTIAL.md`) |
| Workstream claims | see table below |
| Bench lock | **none — released 2026-10-04 ~04:0x EDT.** `.34/.35` are idle (verified via `sparkrun status` after stopping both test jobs). |
| Cluster hostnames | `.34` = `spark-node`, `.35` = `spark-node`, head `.30` = `spark-node` |
| **Head checkout state** | `/home/red/src/sparkrun-recipe-registry` is **not a git repo** (synced tree). As of session 3 its `recipes/qwen4/` carries the 7 original recipes + **2 production lanes** (`…-highcon-…`, `…-longctx-…`) + the live arms `zz-lq-metrics`, `zz-rk-metrics`, `zz-rk-moebackend`; dead arms are in `attic/qwen4/arms/`. `mods` resolves from the run-from dir `~/development/mods -> …/sparkrun-recipe-registry/mods`. |
| **Checkpoint cache on assigned nodes** | **node-free-1 and .35 have NO qwen4 checkpoint cached** (verified 2026-10-04: only `deepseek-ai/DeepSeek-V4.1-Flash` is present, 476 GB). The first qwen4 arm on either node pays a **~99 GiB pull** (labquant) or larger (RadixArk) before it can boot. Budget for it; it is not a boot failure. Nodes .32/.33 hold only DS4 too. |

> **Node allowlist is authoritative for the session.** The tasking assigned `.34/.35`. If a future
> session is given a different pair, change this row *first* and re-check before any launch. Resolve
> hostnames to addresses and compare — do not act on a name you did not resolve.

## Ownership — one owner per workstream per session

Workstream definitions live in `AGENTS.md` §4. Claim a row before you start; the deliverable is a
committed file or a `bench_*` id, never a chat sentence.

| workstream | owner (agent id) | started | status | evidence pointer |
|---|---|---|---|---|
| **W1** fp8 KV failure capture | main (session 2) | 2026-10-04 | **CLOSED — config-level NO** | §15, `.scratch/q4/boot-evidence/w1-fp8kv-logs/` |
| **W2** EXL3 go/no-go | sub_1 (2026-10-04) | 2026-10-04 | **CLOSED — NO-GO** (policy/topology) | `.scratch/q4/exl3/W2-EXL3-GO-NO-GO.md` |
| **W3** labquant quality eval | sub-q4-w3 + main | 2026-10-04 | **advance, not closed** — eval built; paired run = 35/36 vs 37/38, 0 disagreements on 36 shared | `.scratch/q4/W3-*.json`, `W3-QUALITY-EVAL-STATUS.md` |
| **W4** #37111 corruption gate | sub-q4-w4 + main | 2026-10-04 | **built + smoked (PASS); release soak still owed** | `tools/gate-37111.py`, `W4-GATE-STATUS.md` |
| **W5** `max_num_seqs`↔KV trade | main (session 2) | 2026-10-04 | **measured** — cap 24→32 = +0.42 GB scratch for −4.55% KV, boots fine at cps 4096; mechanism pinned to `kv_cache_configurator.py:489` | WORK §19z |
| **W6** TP=4 SGLang | *(unclaimed)* | | BLOCKED on recipe fix | §6 item 1b |
| **W7** MoE/kernel ceiling probes | main (session 2) | 2026-10-04 | **blocked w/o a dedicated boot** — a shell in the serving container OOMs on `set_device(0)` | §6 items 2, 9 |
| **W8** upstream engagement | sub-q4-w8 (session 2) | 2026-10-04 | **drafts written, nothing posted** | `W8-UPSTREAM-DRAFTS.md` |
| **W9** long-context 262k→1M | *(unclaimed)* | | DEPRIORITISED | §6 item 13 |
| **W10** doc & sprawl hygiene | *(unclaimed)* | | ONGOING | `AGENTS.md` §8 |
| **W11** NCCL/RoCE transport confirm | main (session 2) | 2026-10-04 | **VERIFIED over RoCE** (`NCCL_NET=IB`, HCAs Ethernet/ACTIVE); `via NET/IB` still wants a `NCCL_DEBUG=INFO` boot | NOTES "Findings added 2026-10-04" |
| **W12** vLLM recipe benchmark | *(unclaimed)* | | OPEN | §6 item 10 |
| **W13** fast-boot infra variant | sub-q4-w13 (session 2) | 2026-10-04 | **delivered** (validates; not booted) | `attic/qwen4/arms/zz-labq-fastboot-sglang.yaml` |

## Coordination protocol

1. **Claim before you work.** Add/update your row above with your agent id and the date.
2. **BENCH LOCK.** Before launching, add a line `BENCH LOCK: <agent> <profile> <nodes> <eta>` in Live
   state. Remove it (or mark `DONE`) when the job ends. The cluster pair supports exactly **one**
   TP=2 arm at a time; `launch.sh` refuses while a `sparkrun` job is live, but that check is on the
   head, not on your intent — the lock is for humans/agents.
3. **One dated entry per finding**, appended under "Log" below, with its evidence pointer
   (`bench_*` id, `§N`, or `file:line`). **Never delete another agent's entry** — annotate it with
   your evidence and the date.
4. **Post failures too.** A boot that dies, a flag that does not reach the server, a node with low
   `MemAvailable` — all are COOP bullets. "Post the probe result even if it fails; one line saves the
   other agents a boot."
5. **No third coordination file.** Cross-directory/fleet-wide facts can also be noted on the
   repo-root surface if the other lanes need them.

## Shared findings — do not re-derive

These are the lane's settled facts that are *expensive* to rediscover. Each points at its evidence.
Full detail in `AGENTS.md` and the `§N` cited.

- **fp8 KV is a config-level NO on GB10 (CLOSED 2026-10-04).** `kv_dtype: fp8_e4m3` boots, allocates
  an fp8 pool, then dies in CUDA-graph warmup: `ValueError: unsupported SM121 QSA call: expected
  BF16 D=256, 12:1 GQA, …`. Mechanism: `is_sm121()` selects `qwen38_qsa_sm121_varlen` for the packed
  decode and its predicate rejects a non-BF16 query. Not memory, not the prefill graph (this build
  already disables it: "Breakable CUDA graph is incompatible with multimodal model"), not an `-o`
  knob. Evidence: `.scratch/q4/boot-evidence/w1-fp8kv-logs/`. **Do not re-open as a throughput lever.**
- **The fp8-KV "fabricated root cause" was NOT fabricated.** The 2026-09-20 retraction deleted a real
  `ValueError` because it could not be re-found in reaped `bench_*` scratch. The 2026-10-04 re-run
  reproduced it exactly. Rule: **before retracting an error, re-run the arm and capture fresh**;
  absence from a reaped artefact is not absence of the event. WORK §15 carries the correction.
- **Run a recipe by NAME from `~/development`, not by absolute path.** `sparkrun run <abs-path-to-recipe>`
  resolves `mods/<name>` relative to the recipe file's directory (`recipes/qwen4/`), which has no
  `mods/` — so the labquant chain dies with `Could not resolve mod …`. The working form is the
  documented one: symlink the recipe into the run-from dir (`ln -s …/recipes/qwen4/<r>.yaml
  ~/development/<r>.yaml`) and run `sparkrun run <r>`; `~/development/mods` is the repo-root symlink
  that resolution then finds. VERIFIED 2026-10-04 (a by-path launch failed, a by-name launch booted).
- **labquant cannot boot without two flags in `defaults.extra_args`:** `--moe-runner-backend `--moe-runner-backend
  flashinfer_cutlass` (else `auto`→FLASHINFER_TRTLLM, dead on SM121, §7g) and
  `--cuda-graph-backend-prefill disabled` (else `qsa/metadata.py:141` capture crash, §7f). Both are
  mandatory, not tunable. `-o extra_args=` **replaces**; a flag-absent arm needs a variant recipe.
- **`--max-prefill-tokens` is a measured null** on both checkpoints; it must ride `extra_args` (the
  runtime does not map `max_prefill_tokens`, and `-o` on an unmapped key prints "no effect" *and then
  carries on* — the run completes and records an override that never reached the server). §6 item 0,
  §7f.
- **`chunked_prefill_size 8192` is NOT adopted**: +k=24 but regresses k=8/k=16 on the shipping
  labquant checkpoint. Keep 4096. §6 PRIORITY-1, §19c.
- **Mods run as root in the persisted runtime cache.** Reown anything you create there to
  `stat -c '%u' /cache/runtime`, or every later launch of that model key dies with a root-owned
  `flashinfer_jit.log` `PermissionError`. Never `import sglang` from a pre_exec mod. §16.
- **`pmproxy` leaks ~30 GB/h host-side**; a boot can die in `alloc_memory_pool` and *blame the peer
  node*. `launch.sh`'s `MIN_AVAIL_GB` gate exists for this — do not override it downward.
- **`tg_throughput` at k>1 is a window metric.** Do not compare aggregate ratios across arms with
  different `t(1)` — use `m = (t(k)−t(1))/(k−1)` in ms/seq (§3c). Quote aggregate and per-request
  together or neither.
- **A sparkrun launch log is not the server log.** A clean launch log does not mean the server came
  up; crash text is in the container's `/tmp/sparkrun_serve.log` on the node.
- **Read a boot's recipe from THAT boot's `state.yaml`** (`recipe_qualified_name`), never a sibling's
  or memory. A cross-checkpoint result attributed to the wrong checkpoint is the most expensive
  recorded mistake in this lane. `launch.sh --match-bench` enforces identity.

## Log — dated entries, newest last

### 2026-10-04 — session 3: lane harvest (two TP=2 production lanes)

- **Two production TP=2 lanes delivered off the labquant checkpoint** (PRIMARY task):
  `qwen3.8-flash-next-nvfp4-labquant-highcon-sglang.yaml` (Lane A — `max_num_seqs: 32`,
  `max_mamba_cache_size: 128`) and `…-longctx-sglang.yaml` (Lane B — `max_model_len: 1000000` + YaRN).
  Both render-verified on the head and **boot-verified on `.34/.35`**; see `README.md`.
- **Lane B finding (cost a boot each; both now fixed in the recipe + WORK §15):**
  1. `--context-length` past the trained 262144 **RAISES** (`model_config.py:860`) unless
     `SGLANG_ALLOW_OVERWRITE_LONGER_CONTEXT_LEN=1` is in the container env. WORK §15's "accepts with
     a warning" was wrong for this image.
  2. `--json-model-override-args` is **silently inert unless nested under `text_config.rope_parameters`**
     (loader does `config.text_config.update(value)`, `utils/hf_transformers/config.py:282`; flat →
     `rope_type: default`, nested → `yarn`). **Always grep the serve log for `rope_type: yarn`.**
- **Lane A**: the `pool 128 / cap 32 / cps 4096` argv is the same one `bench_7364de5fcb64` ran
  (`zz-rk-metrics`); boot-verified here as a standalone recipe.
- **Attic wave 2 (TERTIARY):** `zz-rk-fp8kv`, `zz-rk-nospec`, `zz-rk-nospec-matched`,
  `zz-lq-nospec-matched`, `zz-labq-fastboot-sglang` → `attic/qwen4/arms/` with manifest rows;
  status memos → `recipes/qwen4/status/`. **`zz-rk-moebackend` was inspected and KEPT live** — three
  live benchmarking profiles still name it (`bs-sweep-high.yaml`, `rk-nograph-cps8192-k8-16-24.yaml`,
  `lq-graphson-cps8192.yaml`).
- **Audit:** `uv run python -m unittest discover -s tests` → **328 tests, 0 failures**;
  no git-tracked file references any moved arm/memo (drift is confined to untracked docs).

### 2026-10-04 — session 2: W1/W3/W4/W7/W11/W13 results

- **W5 measured (first *measured* price on §19o's coupling).** RadixArk TP=2, `mem-fraction 0.8`,
  one boot per cap: `max_num_seqs` 24 → 32 raised `intermediate_ssm_state_cache` 2.64 → **3.06 GB**
  (+0.42 GB) and lowered `max_total_num_tokens` 1460864 → **1394368** (−4.55%). **It boots** (health
  200; the `cps=8192 + cap=32` non-boot of §19o is untested here since this used the shipped
  `cps 4096`). Mechanism VERIFIED from source: the scratch is sized by `spec_state_size`, passed as
  `max_running_requests` (`mem_cache/kv_cache_configurator.py:489`), shape
  `[layers, spec_state_size+1, draft_tokens, …]`. At cap 32 the server still printed `capped to 28`
  — **mamba slot pool, not `max_num_seqs`, is the ceiling** (confirms §19x). WORK §19z.

- **W1 CLOSED (config-level NO).** Re-ran `zz-rk-fp8kv` with `sparkrun run`; captured the real
  failure on both nodes: `ValueError: unsupported SM121 QSA call: expected BF16 D=256, 12:1 GQA, TP1
  24Q/2KV or TP2 12Q/1KV, bs<=128, and selected KV<=2055`, raised in CUDA-graph warmup via
  `qwen_sparse_attn_backend.py:1718 → kernels/ops/attention/__init__.py:115`. The fp8 pool **does**
  allocate (`#tokens 2728960` vs the bf16 control's `1460864` = 1.87×, not 2×). **A same-window bf16
  control on the shipped RadixArk recipe served (health=200).** Evidence:
  `.scratch/q4/boot-evidence/w1-fp8kv-logs/` + `.scratch/q4/capture-boot-evidence.sh`.
- **The "fabricated root cause" verdict was itself wrong.** The 2026-09-20 retraction deleted a real,
  reproducible error because it could not be re-found in reaped `bench_*` scratch. WORK §15 corrected;
  rule posted to COOP shared findings. **Before retracting an error, re-run the arm and capture
  fresh.**
- **NEW SHIPPING DEFECT FOUND AND FIXED — the labquant `revision:` pin was inert.** sparkrun reads the
  pin from top-level **`model_revision:`** (`core/recipe.py:346`); a bare `revision:` is an ignored
  unknown key (root `AGENTS.md` documents this trap). So distribution pulled `main` (`6909a5be…`)
  while the mod chain is contract-pinned to `7c4f1bc1…`, and the boot **died** in
  `unpack-labquant-ple-nvfp4-to-fp8`: "pinned revision … not cached … refusing to guess" — i.e. **the
  shipped labquant recipe could not boot on a clean node.** Fixed in
  `qwen3.8-flash-next-nvfp4-labquant-sglang.yaml` and the other three labquant-family arms
  (`…-tp4-…`, `zz-lq-metrics`, `zz-lq-nospec-matched`, `zz-labq-fastboot-sglang`); all four still
  `recipe validate` clean. **Do not "fix" this back.** The correct form is documented in the recipe
  header.
- **W11 (NCCL transport).** VERIFIED over RoCE: `NCCL_NET=IB`, `NCCL_IB_DISABLE=0`,
  `NCCL_IB_HCA=rocep1s0f0,roceP2p1s0f0`, `NCCL_IB_GID_INDEX=3`, `UCX_NET_DEVICES=roce…:1`; HCAs are
  `link_layer: Ethernet`, `PORT_ACTIVE`. `via NET/IB` in the ring still wants `NCCL_DEBUG=INFO`.
- **W7 (kernel timing) blocked without a dedicated boot.** A shell in the serving container gets
  `CUDA error: out of memory` on `set_device(0)` because the server owns the unified memory. Needs a
  separate quick boot (19 GB free is plenty).
- **W13 delivered:** `attic/qwen4/arms/zz-labq-fastboot-sglang.yaml` (validates; fastsafetensors + 0.91;
  documented as NOT a comparison arm).
- **W3 delivered (off-cluster + first live half):** `tools/qwen4-quality-eval.py` (38-task fixed
  battery, selftest green) + plan/status memos. Live smoke vs the RadixArk arm: **35/36 = 97.2%**
  (`.scratch/q4/W3-radixark-full.json`). The labquant half is running now.
- **W4 delivered:** `tools/gate-37111.py` (selftest green, 5 negative controls) +
  `tools/gate-37111-design.md` + `W4-GATE-STATUS.md`. Live smoke vs the RadixArk TP=2 server:
  **PASS** (warm==cold canary `4183` correct) — a negative result, not proof of absence.
- **W8 delivered:** `recipes/qwen4/W8-UPSTREAM-DRAFTS.md`; upstream states re-verified 2026-10-04
  (#37111 OPEN, #38319 OPEN, #38355 OPEN/unmerged). Drafts only — nothing posted.
- **`mods` resolution gotcha (cost one boot):** a recipe must be run **by name** from
  `~/development` (whose `mods` symlink exists); `sparkrun run <abs-path>` resolves `mods/` relative to
  the recipe file's dir and fails. Posted to shared findings.

### 2026-10-04 — session 2: W1 launched

- **W1 arm launched** on `.34/.35`: `sparkrun run attic/qwen4/arms/zz-rk-fp8kv.yaml` (RadixArk baseline,
  only `defaults.kv_dtype: fp8_e4m3`; no fastsafetensors mods → no root-owned-file risk). Log on head:
  `~/benchlogs/rk_fp8kv_w1_1004_0207.log`. Chosen deliberately as `run` (not `benchmark`) so sglang's
  own stdout/error lands in the log — this is the §6 item 4 prerequisite ("read the real failure"; the
  prior root cause was fabricated and deleted).
  - **Preflight verified before launch:** recipe resolves + renders `--kv-cache-dtype fp8_e4m3` (dry-run
    on head); `.34/.35` idle, 0 compute procs, **117 GB MemAvailable** each, `pmproxy` 0 GB; head has 0
    concurrent sparkrun jobs; head HF cache already holds `RadixArk/Qwen3.8-Flash-Next-NVFP4` (**126 GB**,
    a populated snapshot) → the RadixArk pull is a **head→worker** copy, not an internet fetch. The
    earlier note that "the first qwen4 arm pays a ~99 GiB pull" applies to **labquant**; RadixArk is
    cached on the head but not on the workers.
  - Head is memory-loaded (106/121 GB used, 15 GB avail) by other lanes' models — irrelevant to worker
    RAM, but do not schedule head-side heavy work while this runs.

### 2026-10-04 — new session: consolidation

- **Recon complete.** Read `QWEN4-MODEL-OPTIMIZATION-WORK.md` (top-level structure + TL;DR + §1/§5/§6
  + §19 index), `JOURNAL.md` (structure; last entry 2026-09-23 ~20:45), recipes, `benchmarking/`,
  `mods/`, `.scratch/q4/launch.sh`, and `.swival/memory/`.
- **Wrote `recipes/qwen4/AGENTS.md`** — the condensed agent guide: current state, hard constraints,
  the W1–W10 parallel action plan, the coordination mechanism, runbook, and sprawl policy.
- **Wrote `NOTES.md`** — consolidated working index (what the lane knows / what is
  next), replacing the prior ad-hoc note dump that no longer exists in the tree.
- **Sprawl reduction (W10), first pass.** Moved 9 provably-dead arm recipes from `recipes/qwen4/` to
  `attic/qwen4/arms/` with a provenance manifest (`attic/qwen4/ARMS-MANIFEST.md`): recipes named by
  **no** benchmarking profile and **no** live scratch launcher, listed in
  `.scratch/q4/recipe_manifest.md` with superseded/NOT-RUN status. Full criteria in the manifest.
- **Node assignment recorded** above: free pair `.34/.35`; `.30/.31` restricted.
- **W2 (EXL3) closed NO-GO** on 2026-10-04 by a parallel subagent; memo at
  `.scratch/q4/exl3/W2-EXL3-GO-NO-GO.md`. Decisive gate: the published route is TP=1 single-Spark
  only, while this lane is TP=2/4 on a 2-node grid. Free wins recorded in WORK §6 item 14's outcome
  banner: EXL3's `Qwen4Exp QSA requires a BF16 main KV cache` error independently corroborates §15;
  its MTP acceptance cliff at exactly 163,840 prompt tokens is a lead on blocker (f).
- **Assigned nodes have no qwen4 checkpoint cached.** First boot on `.34/.35` pays a full model pull
  (~99 GiB labquant). `distribution_config.models.enabled` must be true; a cluster `distribution:`
  block overrides the recipe.
- **Resolved the WORK-doc "revision trap" (formerly unreconciled):** `local-inference-lab` rev
  `7c4f1bc1` (the pin in both labquant recipes) is a **populated 36-shard / 105.90 GB** snapshot;
  `ada4da32` is **37 shards / 105.94 GB**. The 36-vs-37 "discrepancy" was two different revisions,
  not a contradiction, and the pin is safe. **`main` moved again** (2026-10-02 → `6909a5be`, 43
  shards). Checked against the HF API, **not** disk (nodes uncached) — re-confirm on disk before
  quoting a shard count as a disk fact. WORK §17 carries the full resolution.

### 2026-09-23 (prior session, carried forward) — pool-128 replication

- `bench_5e245e1029b3` (recipe `zz-rk-metrics`, cells `[24,32]`, d=8192): k=24 = **88.35** median,
  reproducing the comparator `bench_7364de5fcb64` (87.78) at **+0.6%**, against two pool-112 boots at
  80.48/78.02. **~11% pool effect, mechanism UNESTABLISHED**; §19v's ceiling model is right about
  admission but incomplete about the cost of raising the pool. The `launch.sh --match-bench` guard
  was written this session after a wrong-recipe replication nearly produced a fabricated result.

---

*Last updated: 2026-10-04 by the consolidation session.*