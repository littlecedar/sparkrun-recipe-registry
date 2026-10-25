# GLM 5.3 lane

**This lane carries two recipes.** `glm-5.3-flash-exl3-tp4-1m-tensorfold-sglang.yaml` is the
GLM-5.3-Flash EXL3 4bpw TP=4 line, **BOOT-VERIFIED as a sparkrun recipe 2026-10-18** (the boot
receipt below). `glm-5.3-exl3-3bpw-tp4-1m-tensorfold-sglang.yaml` is the full 753B EXL3 3.0bpw
line, over a vendored engine image built the same day and **booted and receipted 2026-10-18**. The lane
also carries its **runbook + research archive**: the 3.0bpw line and the
TP=2/TP=3 Flash topologies were boot-verified on this cluster outside sparkrun, and a fourth line
was attempted and archived as a proven-negative.

## Contents

- [Status](#status)
- [Shipped arm](#shipped-arm)
- [Boot receipt](#boot-receipt-2026-10-18)
- [Boot-verified serving lines](#boot-verified-serving-lines)
- [License](#license)
- [Runbook notes and revision pins](#runbook-notes-and-revision-pins)
- [Revision pins](#revision-pins)
- [Attic index](#attic-index)

- **One recipe, booted 2026-10-18.** `glm-5.3-flash-exl3-tp4-1m-tensorfold-sglang.yaml` realizes the
  Flash EXL3 4bpw TP=4 line in the recipe schema: the engine image is the upstream `tp4` build,
  digest-pinned, and the multi-node prepare/ssh/topology logic is replaced by sparkrun's own
  distribution + rendezvous plus the lane's launcher mod
  ([`mods/tensorfold-glm-exl3-launcher/`](mods/tensorfold-glm-exl3-launcher/README.md)). It booted on
  `.30`–`.33` and served; see [Boot receipt](#boot-receipt-2026-10-18). What a boot does **not**
  settle — a quality battery, a second boot's ladder, and the trial's 98.4 t/s — is listed there.
- **One archived arm.** `glm-5.3-flash-nvfp4-dflash-vllm.yaml` was **archived 2026-10-13** to
  [`attic/glm/`](../../attic/glm/ARMS-MANIFEST.md) as a proven-negative (owner decision): it is repo
  B's independently validated TP=4 formula, image- and checkpoint-pinned, but the pinned public image
  blocks it (its SM120 sparse-MLA backend forces an `fp8_ds_mla` KV layout the NoPE-MLA checkpoint
  cannot use). Do not re-add it without a public image that can serve this checkpoint. Full rationale:
  [`attic/glm/ARMS-MANIFEST.md`](../../attic/glm/ARMS-MANIFEST.md),
  [`attic/glm/AGENTS.md`](../../attic/glm/AGENTS.md#from-recipesglmreadmemd-2026-10-14).
- **Two recipes, both booted.** The EXL3 3.0bpw 753B line is
  `glm-5.3-exl3-3bpw-tp4-1m-tensorfold-sglang.yaml` plus its own launcher mod, over a **vendored
  engine image built the same day** (source build of the unreleased fork branch; pin and derivation
  under [Revision pins](#revision-pins)). It booted on `.30`–`.33` and served: C1 31.7 t/s, 100,559-token
  TTFT 258.4 s, 1M window with DCP over 4 ranks. Two boot blockers it exposed are now guarded —
  an absent `TF_TP_WORLD` and a wheel that shipped no CUDA sources. The TP=2/TP=3 Flash topologies
  stay runbook-only launchers — they are not what this 4-node registry targets.
- **Research** (checkpoint/engine/topology selection, measured numbers, license traps) is in
  [`attic/glm/GLM-5.3-RECOMMENDATIONS.md`](../../attic/glm/GLM-5.3-RECOMMENDATIONS.md).

## Shipped arm

| Recipe | What it is | Status |
|---|---|---|
| [`glm-5.3-flash-exl3-tp4-1m-tensorfold-sglang.yaml`](glm-5.3-flash-exl3-tp4-1m-tensorfold-sglang.yaml) | GLM-5.3-Flash EXL3 4bpw (~176 GB) on 4 Sparks, TP=4, TensorFold v0.6.0 + the 106-patch `tp4` engine, DFlash2 drafts, 1M window, RoCE all-gathers. Checkpoint `Mia-AiLab/GLM-5.3-Flash-EXL3-4bpw-TensorFold@078455ff`, drafter `incoai/GLM-5.3-Flash-DFlash2@bf582e4e`, image `ghcr.io/miaai-lab/glm-5.3-flash-exl3-2x-dgx-sparks-tensorfold@sha256:eb17e092…` | **BOOT-VERIFIED 2026-10-18** — TTR 309.6 s, KV pool 5,834,752, ladder C1 83.03 ± 17.74 / C2 102.36 ± 24.01 / C5 79.49 ± 11.34 / C10 73.37 ± 8.44 t/s. |
| [`glm-5.3-exl3-3bpw-tp4-1m-tensorfold-sglang.yaml`](glm-5.3-exl3-3bpw-tp4-1m-tensorfold-sglang.yaml) | Full GLM-5.3 753B EXL3 3.0bpw (~273 GB) on 4 Sparks, TP=4, TensorFold 0.6.0 from the unreleased `glm-dsa-tp4` fork, 1M window with DCP over 4 ranks, the checkpoint's own MTP-3 head. Checkpoint `bertholomus/GLM-5.3-EXL3-3.0bpw@7f057383`, image `littlecedar/dgx-spark-tensorfold-glm53-exl3-3bpw:0.6.0-ddfad35@sha256:366c2d4e…` | **BOOT-VERIFIED 2026-10-18** — `/v1/models` at 240 s, engine load 308.7 s, startup estimate 96.27 of 102.86 GiB, ladder c1 31.7 t/s / c2 25.3 agg (14.5 per request) / c4 40.6 agg (11.4 per request), 100,559-token prompt TTFT 258.4 s. Not measured: quality, a warm-JIT boot, four concurrent 1M windows. |

  The 2026-10-24 pool-era boot of this arm stalled twice before weights load
  (DCP banner, then frozen; NVRM `NV_ERR_NO_MEMORY` on rank 0 at 15:36:57).
  The triage's one-boot experiment RAN the same window (`GLM-BOOT9-TRIAGE.md`
  on the head, updated): at `max_model_len=32768` the stall **reproduces
  identically with ZERO NVRM events** — 17.0 GiB margin, same frozen DCP
  banner, `/v1/models` never bound at 20 min — so **H1 (unified-memory
  exhaustion at the 1M window) is refuted as the sole mechanism**, and **H2
  is refuted by source**: the launcher mod sets `TF_GLM_EMBED_SPLIT=1` and
  `TF_GLM_MTP_REUSE=2` itself (`CONSTANT_ENV`), so the env was correct in
  every boot. Remaining hypothesis **H3, sharpened to NCCL interface
  selection**: this fork transports over *plain NCCL* (`TF_TP_WORLD` +
  `--rank/--master/--master-port`, supplied by the shim), and the lane's own
  "claims not settled" item 2 records that the working 2026-10-13 runbook
  **hand-set `NCCL_SOCKET_IFNAME`/`NCCL_IB_HCA`** — the sparkrun path does
  not, and the signature (rendezvous banner, silent indefinite wait, no
  allocation failures) is an NCCL bootstrap wedged on a wrong-default
  interface on the multi-NIC GB10 nodes. Next-window one-knob experiment:
  the same boot plus the `tp4_start.sh` NCCL vars
  (`-o env.NCCL_SOCKET_IFNAME=… -o env.NCCL_IB_HCA=…`, values read from
  `~/glm53-tf/tp4_start.sh` on the node holding the 2026-10-13 runbook).
  The pool read path remains excluded (977 MB/s sustained through the
  snapshot).
  **Window 2 ran the one-knob experiment (2026-10-24) and it CONFIRMED H3**: with
  `-o env.NCCL_SOCKET_IFNAME=enp1s0f0np0 -o env.NCCL_IB_HCA=rocep1s0f0,roceP2p1s0f0`
  (`NCCL_NET_PLUGIN=spcx` is absent from the image and was dropped) the boot got past the pre-load
  stall to **inference-ready — container-start TTR port-open 2746.273 s / HTTP-ready 2746.298 s**
  (`boot2b-glm-launch.log` in `~/benchmarks/tp4-window2-20261024/`; an earlier board row quoted
  2888.8 s — superseded by the launch-log figure). Pool reads ~95 MB/s with CPU-dequant gaps. The
  ladder cells are still owed (the auto-finish launched with `--skip-run`, so GLM perf numbers
  remain unmeasured); one stray-stop incident is recorded from that window: a peer's prefix-grep
  `sparkrun stop` killed boot2 2 min post-ready — never stop by parsed id.
The recipe validates (plain) and renders with `-n` on the workstation; it carries one accepted
`unpinned-model-revision` warning, as the lane's other shim recipes do: the engine is handed the
prepared snapshot *path* via `{model}`, so there is no `--revision` for the validator to find
(TensorFold's `serve` has no such flag — it resolves a directory). Two engine knobs the trial ran
(`--parallel 8`, `--max-tokens 32768`, `--vision`) live in the mod, not the recipe, because they are
the upstream launcher's production constants rather than per-launch choices; the mod README inventories
them, and its `RECIPE_ENV` is upstream `scripts/config.sh` at TP=4.

## Boot receipt (2026-10-18)

First boot of the recipe as a sparkrun recipe, on `.30`–`.33` (task
`b55c050475ff4b3a_7afff0589a33`, `--transfer-mode local` from the head). Receipts:
`~/benchmarks/tp4-20261018/` — `glm-launch.log`, `glm-serve.log`, `glm-models.json`,
`glm-smoke.json`, `glm-ladder.{yaml,json,csv}`, `smoke_glm.py`.

| fact | value |
|---|---|
| TTR port-open / HTTP-ready / TTFT | **309.637 s** / **309.653 s** / 310.176 s (container start) |
| launch total | 1720.3 s — 163.65 GiB checkpoint + 2.18 GiB drafter download, 490.95 GiB copied to four hosts, image relay 233.9 s |
| image | `…@sha256:eb17e092fa56…` — no node held the pin; the OCI relay fetched 10.6 GiB and imported it on all four (17 layers reused on each receiver). `docker manifest inspect` returns the same single-platform manifest, config `sha256:7f8f1b38…`; the container's label `tf.patches = 7a37454d3238` **equals the recipe's patch hash** |
| `/v1/models` | id **`GLM-5.3-Flash-EXL3`**, `owned_by: tensorfold` (this server's model object carries no `max_model_len`) |
| context / KV pool | `context: 1048576; loaded in 297.8s`; **5,834,752 tokens** at `--parallel 8` ("up to 8 requests decode together, their caches in one pool of 5834752 tokens (each up to 1048576)") — identical to the 2026-10-13 trial |
| memory | rank 0 estimate 52.03 GiB within 90.04 GiB; workers 50.23 GiB within 90.72–91.02 GiB; ranks 1–3 ready in 291.5–291.6 s, following rank 0 |
| smokes | chat **0.53 s** (`17 × 23 = 391.`, finish `stop`, 41 reasoning tokens); tool call **0.67 s** (`get_temperature{"city":"Reykjavik","unit":"c"}`, finish `tool_calls`) |

Ladder (`--skip-run`, same live serve, `benchmarking/concurrency-ladder.yaml`, 5 runs/cell; `±` is
the sample sd of the per-run decode samples — the receipt JSON's own `tg_throughput.std` is the
population sd, 15.87 / 21.48 / 10.14 / 7.55):

| cell | tg t/s | sd (n=5) | per-run range |             pp t/s | e2e TTFT |
|:-----|-------:|---------:|:--------------|-------------------:|---------:|
| C1   |  83.03 |    17.74 | 62.6–111.3    | — (single request) |   992 ms |
| C2   | 102.36 |    24.01 | 75.4–137.0    |               2050 |  1824 ms |
| C5   |  79.49 |    11.34 | 68.7–98.0     |               1401 |  4282 ms |
| C10  |  73.37 |     8.44 | 63.1–85.4     |               1235 |  8428 ms |

**The trial's 98.4 t/s single-stream does not reproduce on the recipe path.** C1 is 83.03, and the
five runs are 111.3, 84.4, 77.6, 79.2, 62.6 — a warm-up ramp, so ex-first it is **76.0 ± 9.3**
(n=4). Same image patch set, different invocation: the trial ran upstream's scripts under a local
tag (`tensorfold-glm53:v0.6.0`). Aggregate tg peaks at C2 and falls with concurrency — the
`--parallel 8` / DFlash2 verify-window shape, not a throughput claim.

**Still unproven on this arm** (do not upgrade these from the trial's record): a quality battery
through the recipe path (the 37/37 house result is the trial's), a second boot's ladder (every cell
here is one boot), and any concurrency beyond 10. Benign deviation, recorded so the next reader does
not chase it: `[4/6] Syncing tuning configs` fails on all four nodes (`RuntimeError: Cannot locate
the installed SGLang package`) — the image is TensorFold, not SGLang, and the hook is non-fatal.

## Boot-verified serving lines

One line each; full operator detail (serve commands, host overrides, receipts) is in
[`attic/glm/AGENTS.md`](../../attic/glm/AGENTS.md).

- **EXL3 3.0bpw / TensorFold, TP=4 (full 753B)** — **BOOT-VERIFIED 2026-10-13** on `.30`–`.33`; repo
  A's `bertholomus/glm-5.3-tensorfold-tp4-4xgb10` scripts over `bertholomus/TensorFold@glm-dsa-tp4`
  (`ddfad35`, TensorFold 0.6.0); **C1 decode 35.7 t/s @ d0 / 35.9 @ d8k**, MTP-3 acceptance 63.4 %.
  Receipts: `~/benchmarks/glm53-exl3-20261013/`.
  The sparkrun recipe for this line, `glm-5.3-exl3-3bpw-tp4-1m-tensorfold-sglang.yaml`, **booted on
  this image 2026-10-18** (c1 31.7 t/s, 100,559-token TTFT 258.4 s — the recipe path, not the
  editable install); the 35.7 / 63.4 % numbers in this bullet remain the external runbook's.
- **GLM-5.3-Flash EXL3 4bpw / TensorFold, TP=2 / TP=3 / TP=4** — **all BOOT-VERIFIED 2026-10-13**;
  `MiaAI-Lab/GLM-5.3-Flash-EXL3-2x-DGX-Sparks-TensorFold` launcher (`main` `3fd60df`, `tp4` `d220030`),
  checkpoint `Mia-AiLab/GLM-5.3-Flash-EXL3-4bpw-TensorFold@078455ff`, drafter
  `incoai/GLM-5.3-Flash-DFlash2@bf582e4e`; TP=4 **C1 decode 98.4 t/s @ d0 / 99.4 @ d8k**, DFlash2
  acceptance 76.6 %, quality 37/37 on the house battery. Receipts:
  `~/benchmarks/glm53-flash-exl3-tp4-trial-20261013/` (TP=2/TP=3 siblings). The **TP=4 line is now the
  [shipped arm](#shipped-arm)** (the same engine image, checkpoint and drafter, launched by sparkrun),
  and its **98.4 t/s does not reproduce on the recipe path** — 83.0, or 76.0 ex-warm-up; see
  [Boot receipt](#boot-receipt-2026-10-18). TP=2/TP=3 stay runbooks — they are external script
  launchers, and the 2-/3-Spark topologies are not what this 4-node registry targets.
- **Flash NVFP4 / vLLM** — **ARCHIVED 2026-10-13**, proven-negative on the pinned public image; see
  [`attic/glm/ARMS-MANIFEST.md`](../../attic/glm/ARMS-MANIFEST.md).

## License

The **Flash** line is **MIT**; the **DFlash2 drafter is CC BY-NC-ND** — acceptable for this
non-commercial cluster (owner decision 2026-10-11), not for commercial resale. The full 753B line and
its derivatives carry the **Z.AI GLM-5.3 License** (permissive, with the MaaS >$10B security-review
clause). Full map: [`attic/glm/GLM-5.3-RECOMMENDATIONS.md`](../../attic/glm/GLM-5.3-RECOMMENDATIONS.md#licensing-map).

## Runbook notes and revision pins

The runbook bullets and the revision pins below move with the lane's research. The live copy is in
[`attic/glm/AGENTS.md`](../../attic/glm/AGENTS.md).

The Flash 4bpw line's three-part blocker is **closed** for the TP=4 arm — the "a recipe needs a baked
image + a GLM variant of the launcher mod + a `runtime: sglang` shim" note in
[`attic/glm/AGENTS.md`](../../attic/glm/AGENTS.md) was written before the engine image existed on GHCR:

1. **the baked image** — not built here: the upstream `tp4` build is published
   (`ghcr.io/miaai-lab/…@sha256:eb17e092…`, the digest upstream's own `prepare.sh` pulls, re-tagged
   `tensorfold-glm53:v0.6.0` for the trial). Resolved and pinned in the recipe; see its comment for the
   three checks that agree on it.
2. **the launcher mod** — shipped: [`mods/tensorfold-glm-exl3-launcher/`](mods/tensorfold-glm-exl3-launcher/README.md).
3. **the `runtime: sglang` shim** — shipped: the recipe's `command:` is the mod's launcher, which maps
   sparkrun's `--dist-init-addr/--nnodes/--node-rank` onto `tensorfold serve`.

**All three are closed, and the boot is closed too.** The recipe booted 2026-10-18
([Boot receipt](#boot-receipt-2026-10-18)), so the arm no longer rests on the external launcher's
numbers: its own C1/C2/C5/C10 row exists. What a boot cannot settle stays open — a quality battery
through this path (37/37 is still the trial's), a second boot, and the single-stream gap against
98.4.
The other serving lines are unchanged: no booted recipe, and a revive re-stages weights (see the
re-fetch costs under revision pins).

## Revision pins

**Moved to [`attic/glm/AGENTS.md`](../../attic/glm/AGENTS.md#revision-pins-verified-2026-10-14-hub-api--every-nodes-hf-cache)
§"Revision pins" (verified 2026-10-14, Hub API + every node's HF cache).**

| pin | value | where it lives |
|:--|:--|:--|
| Flash EXL3 4bpw checkpoint | `Mia-AiLab/GLM-5.3-Flash-EXL3-4bpw-TensorFold@078455ff` (`main` `76c0b517`) | shipped recipe's `model_revision:` |
| Flash DFlash2 drafter | `incoai/GLM-5.3-Flash-DFlash2@bf582e4e` | shipped recipe's `defaults.speculative_draft_model_revision` |
| EXL3 3.0bpw checkpoint | `bertholomus/GLM-5.3-EXL3-3.0bpw@7f057383` (`main`) | 3.0bpw recipe's `model_revision:` — ~273 GB/node re-fetch after the 2026-10-14 reclamation |
| archived Flash NVFP4 | `RedHatAI/GLM-5.3-Flash-NVFP4@36c184c6` — gone from all nodes, `main` is now `18d55bfd` | archived arm only |
| TensorFold engine | `bertholomus/TensorFold@glm-dsa-tp4` = `ddfad356` (TensorFold 0.6.0) | the 3.0bpw image's build arg; the commit is the whole provenance anchor (that branch carries no patch set) |
| **3.0bpw engine image** | `littlecedar/dgx-spark-tensorfold-glm53-exl3-3bpw:0.6.0-ddfad35@sha256:25bb6806…` | the 3.0bpw recipe's `container:` pin |

The image row is new (2026-10-18): a **source build** of the unreleased fork branch over
`lmsysorg/sglang:dev-cu13` arm64 manifest `e9aa22ad`, from
[`Dockerfile.tensorfold-glm53-3bpw`](Dockerfile.tensorfold-glm53-3bpw). Cite the `@sha256:` — the
`0.6.0-ddfad35` tag is a convenience. A local-registry derivation taken during the build reported
`44e478f1…`; that is the **local manifest**, not the registry's, and must never be cited as the
pin. The pushed tag resolves to `25bb6806…` (verified from the head with `docker buildx imagetools
inspect`, 2026-10-18), and that is what the recipe carries. Build receipt, including the
build-time gate and the read-only image probe: `~/benchmarks/glm-3bpw-image-20261018/REPORT.md` on
the workstation (its "Push: NOT done" section predates the push).

**The image is built, pushed and booted.** The recipe booted on `.30`–`.33` 2026-10-18 and served: TP=4
rendezvous (`TF_TP_WORLD` is now set from `--tp` — unset, the fork defaulted the world to 2 and
`ncclCommInitRank` failed with NCCL error 4), the first-boot sm_121 JIT (four extensions, and the
wheel's absent `*.cu` sources are now mirrored by the Dockerfile), the `TF_GLM_KV=q5` 1M pool
(1,048,584 slots, 96.27 of 102.86 GiB) and a 100,559-token TTFT of 258.4 s. MTP-3 acceptance is still
the trial's 63.4 % — the smoke's 19/34 drafts is one request. Receipt:
`~/benchmarks/glm-3bpw-boot-20261018/` (`RECEIPT.md`, `NCCL-DEBUG.md`).

The **shipped Flash arm's** two pins now live in its recipe and are what sparkrun re-stages on a
launch; the pins above remain the runbook's. Verified 2026-10-15 against the Hub API: `078455ff`
resolves (97 files, 2026-10-02) and DFlash2 `main` is still `bf582e4e`, and the engine image digest
resolves from the cluster (a read-only `docker manifest inspect` from the head).

## Attic index

Everything below lives in [`attic/glm/`](../../attic/glm/) and answers a question the lane README no
longer carries. Nothing in it is served by the registry.

| File | What it holds | Question it answers |
|---|---|---|
| [`ARMS-MANIFEST.md`](../../attic/glm/ARMS-MANIFEST.md) | Provenance table for the one archived arm (`glm-5.3-flash-nvfp4-dflash-vllm.yaml`), the owner decision, and the "do not re-add" rule | Why was the Flash NVFP4 recipe archived, and what would it take to revive it? |
| [`AGENTS.md`](../../attic/glm/AGENTS.md) | Runbook notes for the boot-verified serving lines (serve commands, host overrides, topologies, metrics, receipts) + the moved revision pins | How do I re-run a GLM-5.3 serving line on this cluster, and which Hub revisions does each pin? |
| [`GLM-5.3-RECOMMENDATIONS.md`](../../attic/glm/GLM-5.3-RECOMMENDATIONS.md) | Research: the two model lines, four checkpoints, topology arithmetic, engines/spec-decode, two concrete serving configs, licensing map, platform risks, sources | Which GLM-5.3 checkpoint/engine/node-count should a future GLM recipe be built from, and why? |
| [`glm-5.3-flash-nvfp4-dflash-vllm.yaml`](../../attic/glm/glm-5.3-flash-nvfp4-dflash-vllm.yaml) | The archived vLLM arm itself (repo B's runtime-formula.json, image- and checkpoint-pinned) | What did the archived recipe actually configure? |
