# CustomAllReduce on SM120 / TP=4 — what the claim is, why it does not transfer to `ds4`, and what is worth trying

Status: research note, 2026-10-03. Not a recipe change. Nothing here is shipped.
Read alongside [`../AGENTS.md`](../recipes/ds4/AGENTS.md) (lane invariants, guards) and
[`../README.md`](../recipes/ds4/README.md) (measured numbers). Evidence vocabulary follows
`../recipes/ds4/AGENTS.md`: **VERIFIED** = read from a primary artifact or measured here;
**LIKELY** = strong secondary evidence; **SPECULATIVE** = reasoning without a
source. Numbers this note derives are marked "computed here".

> **Verdict up front.** The "free 5% on TP=4 / SM120" tip is real, but it is about a
> **single-node, 4-GPU, PCIe, no-NVLink SM120 box** (RTX 6000 Pro Blackwell class) and
> a **custom all-reduce kernel**, not an SGLang flag. `ds4` is a different topology
> (**four nodes**, one GB10/SM121 each, TP=4 **across nodes** over RoCE) on which SGLang's
> CustomAllReduce is **hard-disabled by design**, and whose role is **already filled by
> RoCEnante** (the RDMA one-shot all-reduce). There is no flag to flip and no free 5% to
> collect. The transferable idea — a size-aware one-shot crossover — is worth *measuring*
> against RoCEnante's coverage, which is what the experiments below do.

---

## 1. The claim, traced

- **Origin:** Zach Mueller (Hugging Face), X post 2026-10-03: *"There's a free 5% boost
  waiting for you on TP=4 if you tell your LLM to enable CustomAllReduce on SM120 to not
  be just TP=2."* The post has no engine, model, or topology in its text; the attached
  image is the detail. `LIKELY` the subject is a single 4-GPU PCIe SM120 workstation.
- **The documented analogue:** [`local-inference-lab/rtx6kpro`](https://github.com/local-inference-lab/rtx6kpro)
  and [`voipmonitor/rtx6kpro`](https://github.com/voipmonitor/rtx6kpro) document precisely
  this: "PCIe Oneshot AllReduce", a custom kernel from Luke Alonso's SGLang **fork**
  ([commit `d39236a`](https://github.com/lukealonso/sglang/commit/d39236aee635cca2725f94539358da0d1c85d8c2)),
  enabled with `--enable-pcie-oneshot-allreduce`. `VERIFIED` (read from the wiki).
  Measured there, Qwen3.5-397B NVFP4 **TP=4, single node, same NUMA**:
  +7.8% at c=1 (70.6 → 76.1 tok/s), +11.3% c=1 / +5.2% at c=32 end-to-end; 1.4–6× lower
  all-reduce latency up to 512 KB; crossover ~512 KB. On **8-GPU cross-socket** the same
  kernel is *slower* (−4% to −15.7%) because the system-scope barrier crosses Infinity
  Fabric. The "5% on TP=4" tip matches the low end of these numbers.
- **Important:** `--enable-pcie-oneshot-allreduce` is **not in upstream SGLang**, not in
  this lane's pinned branch, and not in the `ds4` image. `VERIFIED` (grep of
  `python/sglang/srt/server_args.py` and `python/sglang/srt/arg_groups/fields/exec_.py` on
  both `main` and `f80c91a4b`: no `oneshot`/`pcie` field exists; the flag lives only in the
  fork). So even the SM120 single-node case needs a **kernel patch + a host driver
  override**, not a config line.

---

## 2. Where the gate lives in SGLang (why 4× PCIe SM120 does nothing by default)

Pinned branch for this lane is SGLang `dsv4.1` @ `f80c91a4b` (2026-09-16).
`VERIFIED` that its `python/sglang/srt/distributed/device_communicators/custom_all_reduce.py`
is the same gate as `main`:

- `_SUPPORTED_WORLD_SIZES = [2, 4, 6, 8]` — TP=4 is a *supported* world size.
- `can_use_custom_all_reduce_with_nvlink()` disables for **world_size > 2 and not
  full_nvlink**: *"disabled because it's not supported on more than two PCIe-only GPUs"*.
- Even if instantiated, `should_custom_ar()` returns `False` on CUDA unless
  **`world_size == 2 or full_nvlink`**. So on TP=4 over plain PCIe the kernel is never
  used; you silently get NCCL. That is the gap Luke's fork closes, by replacing NCCL for
  small messages with a one-shot kernel (direct PCIe P2P writes + a system-scope barrier),
  with an auto-crossover that hands large messages back to NCCL.
- `CustomAllReduceV2` (JIT, `SGLANG_OPT_USE_CUSTOM_ALL_REDUCE_V2`, default on in `main`)
  only relaxes this for a **single NVLink clique / MNNVL multicast domain**
  (`can_use_custom_all_reduce_v2` → `full_nvlink is True`, or `is_one_nvlink_clique`).
  On a PCIe-only box it collapses to the same rule. **Multi-node is admitted only for one
  NVLink fabric clique**; every other cross-node group falls back to NCCL.

`VERIFIED` in SGLang `main` and `f80c91a4b` (files fetched 2026-10-03).

**Prerequisites the wikis call out** (none of which `ds4` currently has or wants):
a `/etc/modprobe.d/nvidia-p2p-override.conf` with `ForceP2P=0x11;RMForceP2PType=1;…`
(otherwise direct P2P loads silently route through SysMem and the kernel is ~15× slower),
`pcie_port_pm=off` in GRUB, `uvm_disable_hmm=1`, Resizable BAR; and
`PYTORCH_CUDA_ALLOC_CONF=expandable_segments:False` (expandable segments break the IPC
handle exchange and crash the kernel). These are host-level changes, which is exactly the
class of change `../AGENTS.md` §7 refuses to ship (`DSV41_ENGRAM_DRM_NODE`).

---

## 3. Why the claim does not transfer to `ds4`

The `ds4` lane is **not** one 4-GPU box. It is four DGX Spark (GB10, **SM121**) nodes,
TP=4 **one rank per node, across nodes**, over 2× ConnectX-7 RoCE. Three independent
reasons the SM120 custom-AR does not apply:

1. **Cross-node, so the gate is permanently closed.** SGLang's custom-AR (v1 and v2)
   requires all ranks in one node (v1) or one NVLink clique (v2). A four-node group fails
   both. `VERIFIED` in this lane's own boot log — the gate fires and says so
   (`.scratch/ds4/knapcio/logs/boot9-head-serve.log:105`; a local, git-excluded work
   area, so this citation is not a clickable link):
   `CustomAllreduce is disabled because this process group spans across nodes.`
   GB10's NVLink-C2C links that Spark's CPU and GPU *inside one node* — there is no
   GPU↔GPU NVSwitch across the four Sparks — so v2's fabric-clique path can never open
   across this group either.
2. **SM121, not SM120** (`../AGENTS.md` §1). The NVIDIA P2P driver override and BAR1 story
   in the SM120 wikis is about PCIe root-port P2P inside one chassis; a Spark node has a
   4-GPU-equivalent *inside one GB10*, and the cross-node path is RDMA, not PCIe P2P.
3. **The role is already filled — by RoCEnante.** `ds4` ships
   `SGLANG_ROCE_ALLREDUCE=1`, `SGLANG_ROCE_MAX_SIZE=2097152`, `DSV41_ROCE_GATHER=2097152`
   (`VERIFIED`, launcher `RECIPE_ENV`). RoCEnante is the RDMA one-shot all-reduce/all-gather:
   *"its one-shot all-reduce/all-gather writes into every peer"* — the cross-node analogue
   of Luke's PCIe oneshot kernel. Boot log (VERIFIED):
   `RoCEnante ready: world=4 hcas=rocep1s0f0,roceP2p1s0f0 gid_index=3 max_size=2097152`
   and `ROCE_TP8_READY {...}`. `../README.md` measures it as the single largest lever on the
   lane: **1.70×/1.69×/1.81×/1.23×** over NCCL-only. The all-reduce lever has already been
   pulled — that *is* the RoCEnante headline, not something still on the table.

**Therefore "enable CustomAllReduce on ds4" is a category error:** the engine refuses it
(cross-node), and the thing it would buy (a low-latency one-shot all-reduce) is already
installed under a different name.

---

## 4. What is actually load-bearing here (so we price a "5%" correctly)

Measured on the production stack (uncapped clock, `docs/upstream-watch.md`, 2026-09-19):

- Decode step at c=1: **prose 31.2–32.5 ms**, code 37.4–37.8 ms on this model mix.
- **The entire NCCL collective family is 0.6 ms/step** (42 decode steps, live profiler):
  `all_gather` 0.288 ms (265 calls), `all_reduce` 0.278 ms (83 calls), `broadcast` 0.027 ms.
  That is ~1.2% of a step — and RoCEnante already moves the large TP SUM all-reduces and
  the ≤2 MiB all-gathers off NCCL onto RDMA.
- The remaining per-step sync on the critical path is the **9 spec-decode broadcasts**
  (5 draft-graph + 3 verify epilogue + 1 verify_cap), ~0.14 ms/step; the production line
  sets `DSV41_SPEC_SYNC_FREE=all`, which drops/merges them (bit-identical on greedy rows;
  audited). `VERIFIED` (`docs/adapters.md`, `adapter/spec_sync_free.py`).

Computed here: **a "free 5%" from a *different* all-reduce is arithmetically impossible on
this lane.** If the whole collective family is ~1.2% of a step, no all-reduce kernel change
can yield 5% of decode. The 5%-class lever on `ds4` is RoCEnante-vs-NCCL (already shipped)
and it is measured at 1.2–1.8×, not 1.05× — because on *this* topology NCCL is the slow
baseline that the kernel replaced, whereas on a single-node SM120 box NCCL was already
decent and oneshot bought the last few percent.

---

## 5. Experiments worth running

Everything the launcher owns lives in `RECIPE_ENV` and is applied with `env.update()`
(**override**, not `setdefault`), so a container env or a recipe `env:` cannot override it
(`../AGENTS.md` §4). **Every experiment below is a `mods/dsv41-sglang-overlay/launcher.py`
edit**, then `git commit` + push/refresh the registry clone before launching (mod refs
resolve from the registry clone, `AGENTS.md` §4). `-o key=value` reaches `defaults:` only
and cannot change these. Render with `sparkrun run … -n` before each real boot.

Measurement rules for all of these: a 5% claim is **below the GB10 inter-boot scatter
(7–25%)** (`../AGENTS.md` §10). Use ≥3 boots per arm, a same-config control boot before
calling an arm a win, and the short-prompt harness `C1 t/s` contract. Read the granted KV
pool from the boot log, never computed.

### E1 — Confirm the baseline (no change; do this first)

Gate check, not an edit. On the next boot, grep the serve log for, in order:
`RoCEnante ready:`, `ROCE_TP8_READY`, `CustomAllreduce is disabled because this process
group spans across nodes.`, and `DSV41_ROCE_GATHER ready`. The win condition is the first
two present and the third present (expected) — this *proves* the engine is on RoCEnante,
not custom-AR, and that the custom-AR path is off for a documented reason. Cost: one boot.

### E2 — Re-price the RoCEnante baseline as a control

Set `SGLANG_ROCE_ALLREDUCE=0` (and `DSV41_ROCE_GATHER=0`) in `RECIPE_ENV`; this is the
documented rollback one-liner (`../README.md`, `AGENTS.md` §7). Expected: the NCCL-only
column of `README.md` (27.4 / 62.5 / 73.2 / 155 t/s). Purpose: a *contemporaneous*
control so any later arm is compared boot-for-boot, not against a stale table. If the
spread between the two arms is under ~15%, stop — you are in the noise and there is
nothing here to chase.

### E3 — Sweep RoCEnante coverage (`SGLANG_ROCE_MAX_SIZE`) — the actually relevant knob

`SGLANG_ROCE_MAX_SIZE=2097152` (2 MiB) covers the 16-slot decode step (983 KB) and the
2 MiB all-gathers. Question: **do any TP SUM all-reduces or all-gathers exceed 2 MiB and
silently fall back to NCCL?** Candidates: the compact-gather path
(`DSV41_SPLIT_COMPACT_GATHER`), the prefill TP split, and long-context prefill
all-reduces. Try `SGLANG_ROCE_MAX_SIZE=4194304` and `8388608`, boot-matched against E2's
control and against the shipped 2 MiB. Watch `writes_completed_per_hca` /
`bytes_posted_per_hca` in the `ROCE_TP8_READY` stats line to see whether the new bytes
actually moved over RDMA. Gate: decode step time (c=1 prose/code) and, separately, prefill
TTFT at 119k/231k (the prefill table in `upstream-watch.md`). Reject on any quality
regression — RoCEnante sums in a different order than NCCL, so greedy text can shift on
some prompts (`history.md`); compare step time and a many-prompt battery, not one prompt.

### E4 — Residual broadcast path (the only collectives RoCEnante does not cover)

RoCEnante covers all-reduce and all-gather only. The 9 spec-decode broadcasts are handled
by `DSV41_SPEC_SYNC_FREE=all` (drop/merge), not by RDMA. There is no RoCE *broadcast*
adapter today. If E3 shows the collective budget is still non-trivial, the candidate is a
`b12x.comm` broadcast path (one-shoter writing into every peer, like the all-reduce), or
extending `spec_sync_free` to remove the last broadcast. `SPECULATIVE` value: ≤0.14 ms/step
(~0.4%) — quantify with the live profiler before building anything.

### E5 — Full-RDMA "oneshot" parity check (the transferable idea)

If the goal is genuinely "Luke's kernel, but for ds4", the honest port is **not** PCIe
oneshot — it is confirming RoCEnante's auto-crossover behaves like Luke's: small messages
stay on the one-shot path, large ones go to NCCL. Luke's crossover is ~512 KB on 4 PCIe
GPUs at 4.10 µs effective latency; RoCEnante's `max_size` is the fixed 2 MiB. There is no
measured RoCEnante crossover curve here. Measure one: an in-image all-reduce microbench
over the RoCE transport vs NCCL at 1 KB…2 MiB, same four nodes, to see whether the 2 MiB
cap is too high (sending 512 KB–2 MiB over a system-scope-style RoCE barrier where NCCL
would win). If so, lower `SGLANG_ROCE_MAX_SIZE` and re-test E2/E3. This is the one
experiment that maps the tweet's actual finding onto our fabric.

### Explicitly NOT worth doing

- **Flipping `SGLANG_OPT_USE_CUSTOM_ALL_REDUCE_V2` or `--disable-custom-all-reduce`, or
  hunting for an enable flag.** The v2 path re-checks `full_nvlink`/clique and stays off;
  `--disable_custom_all_reduce` is a real field
  (`arg_groups/fields/exec_.py:613` on `main`, `:592` on `f80c91a4b`) but only silences the
  already-correct warning; and no flag that *enables* custom-AR exists upstream or in the
  pinned branch. The only adjacent flag is `--flashinfer-allreduce-fusion-backend`
  (*fusion*, not this kernel — the SM120 crasher noted below). `VERIFIED` 2026-10-03.
- **Patching the cross-node gate to force custom-AR on.** The kernel is intra-node by
  construction (cudaIpc handles + a same-node process group); forcing it across four nodes
  cannot work, and would fight `../AGENTS.md`'s portability invariants.
- **Adopting the NVIDIA P2P driver override / GRUB changes.** Host-level, per-machine,
  breaks the recipe's no-host-device portability contract (`test_managed_comm_env_not_pinned`,
  `test_no_host_device_names_in_env`), and buys nothing cross-node.
- **FlashInfer/TRT-LLM all-reduce *fusion*.** `sglang#15650` — it auto-enables on SM120 and
  crashes CUDA-graph capture; fix PR `#32330` open. Gated/irrelevant on SM121 cross-node.
  Kept here only so nobody re-derives it as "the custom all-reduce thing".

---

## 6. Traps

- **`PYTORCH_CUDA_ALLOC_CONF=expandable_segments`** must stay `False` — required by this
  lane anyway (NaN logits above 64 prefill query tokens, `../AGENTS.md` §4;
  `test_no_expandable_segments`), and separately incompatible with the PCIe oneshot kernel
  (`pcie_allreduce.cu:321`). Do not "fix" one into breaking the other.
- **Do not pin `NCCL_NET/NCCL_IB_HCA/NCCL_IB_GID_INDEX/NCCL_CROSS_NIC/NCCL_P2P_LEVEL`** to
  chase P2P: sparkrun's InfiniBand probe fills them per cluster and pinning trips the
  `managed-comm-env` guard (`test_managed_comm_env_not_pinned`).
- **`NCCL_BUFFSIZE` is a connection-buffer byte size, not a token count** — do not wire it
  to context (`test_nccl_buffsize_is_not_context_length`).
- **Do not compare greedy *text* across transports.** RoCEnante sums in a different order
  than NCCL, so a stack that changes all-reduce can shift greedy output on some prompts
  (`history.md`). Step time / many-prompt aggregate only.
- **A 5% arm needs a control boot**, not a table lookup. Inter-boot scatter is 7–25%.

---

## 7. Measurement discipline for any "5%" claim on this lane

1. Reproduce E1's gate lines on the boot you measure — no gate, no number.
2. Same-image, same-clock control boot immediately before/after each arm.
3. ≥3 boots, short-prompt harness, quote the harness with the number (`../README.md`).
4. Read the granted KV pool from the boot log; a faster arm that shrank the pool is not a
   win.
5. State the DSpark accept length alongside any decode number
   (`chat_template_kwargs {"thinking": false}` here).
6. A claim under ~15% needs an A/B pair, not a single run.

---

## 8. Provenance and references

Traced 2026-10-03.

- Claim: [Zach Mueller on X, 2026-10-03](https://x.com/TheZachMueller/status/2106346165751189872);
  [AGI Hunt summary](https://agihunt.info/en/p/1a101899781f1d484cb21ae9f0b).
- SM120 single-node PCIe context and measurements:
  [local-inference-lab/rtx6kpro — SGLang](https://github.com/local-inference-lab/rtx6kpro/blob/master/inference-engines/sglang.md),
  [PCIe Oneshot AllReduce](https://github.com/voipmonitor/rtx6kpro/blob/master/optimization/pcie-oneshot-allreduce.md),
  [PCIe bandwidth / P2P](https://github.com/local-inference-lab/rtx6kpro/blob/master/hardware/pcie-bandwidth.md),
  [lukealonso/sglang `d39236a`](https://github.com/lukealonso/sglang/commit/d39236aee635cca2725f94539358da0d1c85d8c2),
  [NCCL AllReduce benchmarks](https://github.com/voipmonitor/rtx6kpro/blob/master/benchmarks/results.md).
- SGLang gates (fetched 2026-10-03): `python/sglang/srt/distributed/device_communicators/custom_all_reduce.py`,
  `…/custom_all_reduce_v2.py`, `…/custom_all_reduce_utils.py`, `python/sglang/srt/server_args.py`
  and `python/sglang/srt/arg_groups/fields/exec_.py` (`disable_custom_all_reduce` field) —
  on `main` and on the pinned `f80c91a4b`; `SGLANG_OPT_USE_CUSTOM_ALL_REDUCE_V2` default in
  `python/sglang/srt/environ.py` (`main` line ~1352); [SM120 perf plan `#19637`](https://github.com/sgl-project/sglang/issues/19637);
  [TRT all-reduce fusion `#15650`](https://github.com/sgl-project/sglang/issues/15650).
- This lane (measured / VERIFIED locally): `../AGENTS.md` §4, §6, §7, §10;
  `README.md` (RoCEnante 1.70× headline; C1–C16 table);
  `.scratch/ds4/knapcio/logs/boot9-head-serve.log` (gate lines);
  `.scratch/ds4/knapcio/docs/upstream-watch.md` (profile: 0.6 ms/step collectives;
  spec-decode broadcasts ~0.14 ms/step);
  `.scratch/ds4/knapcio/docs/adapters.md` and `adapter/spec_sync_free.py`;
  `mods/dsv41-sglang-overlay/launcher.py` (`RECIPE_ENV`);
  `runtime/sglang-rocenante.patch`, `adapter/roce_gather.py`.

## 9. How to update this doc

If this lane ever moves to a **single-node** multi-GPU SM120/SM121 box, or a future SGLang
merges a generic PCIe-oneshot path (watch `#19637` → "SM120 4-GPU PCIe-switch topology
support for AllReduce optimization", still open), re-run §2's gate check: read
`dispatch_custom_allreduce` and `should_custom_ar` on the *then-current* branch and record
whether `world_size == 2 or full_nvlink` has been relaxed. That line, not the tweet, is the
thing that would make this doc's verdict change.