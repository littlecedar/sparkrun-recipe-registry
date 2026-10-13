# GLM 5.3 lane

Two model lines, both documented in
[`GLM-5.3-RECOMMENDATIONS.md`](GLM-5.3-RECOMMENDATIONS.md) (rewritten 2026-10-10; the
image claim corrected 2026-10-11):

- **Flash NVFP4 / vLLM** — [`glm-5.3-flash-nvfp4-dflash-vllm.yaml`](glm-5.3-flash-nvfp4-dflash-vllm.yaml):
  repo B's independently validated formula, image digest-pinned
  (`vllm/vllm-openai:glm53-flash`, manifest-list digest `819ec9c0…`), checkpoint
  pinned `36c184c6`. **Boot-attempted, BLOCKED on the pinned public image** —
  2026-10-13, four boots on `.30-.33`, logs in
  `~/benchmarks/glm53-flash-20261013/`. The image's SM120 sparse-MLA backend
  forces the `fp8_ds_mla` KV layout, whose `concat_and_cache_mla` kernel requires
  a 64-dim RoPE tail while the checkpoint is NoPE MLA (`qk_rope_head_dim 0`,
  `mla_use_nope true`); `--kv-cache-dtype bfloat16` and `nvfp4_ds_mla` each
  select no valid attention backend, and forcing the non-SM120
  `FLASHINFER_MLA_SPARSE` (whose fp8 path keeps the standard layout) fails with
  `compute capability not supported` on GB10. The DFlash2 drafter is separately unusable
  in this image: its `dflash` proposer needs the target to implement
  `SupportsEagle3`, which `Glm5NextForConditionalGeneration` does not. See the
  recipe `metadata.description` for the full root cause and receipt paths.
- **EXL3 3.0bpw / TensorFold** — shipped as a **runbook note, not a sparkrun
  recipe** (rationale below). **BOOT-VERIFIED 2026-10-13 on `.30-.33`**:
  repo A's [`bertholomus/glm-5.3-tensorfold-tp4-4xgb10`](https://github.com/bertholomus/glm-5.3-tensorfold-tp4-4xgb10)
  scripts serve the full GLM-5.3 EXL3 3.0bpw checkpoint (292.7 GB) on the
  [`bertholomus/TensorFold@glm-dsa-tp4`](https://github.com/bertholomus/TensorFold/tree/glm-dsa-tp4)
  engine (`ddfad35`, TensorFold 0.6.0). Serve verified healthy — `GET /v1/models`
  and a real chat round-trip. **C1 decode 35.7 t/s @ d0 / 35.9 @ d8k** (single
  stream, pp 2048, tg 128, n=5, decode phase only), **MTP-3 acceptance 63.4 %**
  (1556/2453 draft tokens). Receipts: `~/benchmarks/glm53-exl3-20261013/`.

  Why a runbook: the engine is an **unreleased fork branch**, not an image — the
  proven route installs it editable at container start. A sparkrun recipe would
  need a baked image *plus* a GLM variant of `mods/tensorfold-dsv41-launcher`
  (the ds4 pattern), i.e. a build-and-push, not a config edit. Recipe sketch if
  wanted: `runtime: sglang` shim, image = the fork over the sglang base, a
  `tensorfold-glm-exl3-launcher` mod mapping sparkrun's
  `--dist-init-addr/--nnodes/--node-rank` onto
  `tensorfold serve --tp 4 --rank R --master … --master-port …`, env
  `TF_GLM_KV=q5 TF_GLM_EMBED_SPLIT=1 TF_GLM_MTP_REUSE=2`, extra
  `--mtp-drafts 3 --parallel 4`. Runbook (proven here): engine at
  `~/glm53-tf/TensorFold`, checkpoint at `~/models/GLM-5.3-EXL3-3.0bpw` on every
  node, then
  `cd ~/glm53-tf && TF_GLM_KV=q5 TF_GLM_EMBED_SPLIT=1 TF_GLM_MTP_REUSE=2 bash tp4_start.sh 32768 "--mtp-drafts 3 --parallel 4"`;
  rank 0 serves on `.30`'s management IP at `:18090`. `tfrun-sglang.sh` swaps
  repo A's `nvcr.io/nvidia/pytorch:26.07-py3` base for the already-present
  `lmsysorg/sglang:dev-cu13` (digest `aa878e8d`; CUDA 13, torch 2.13, libibverbs
  headers, libnccl); `tp4_start.sh` is set to the `.30-.33` fabric (master
  `192.168.0.30`, `NCCL_SOCKET_IFNAME enp1s0f0np0`,
  `NCCL_IB_HCA rocep1s0f0,roceP2p1s0f0`, RoCEv2 `NCCL_IB_GID_INDEX=3`).

- **GLM-5.3-Flash EXL3 4bpw / TensorFold, 2 Sparks (TP=2)** — runbook note, not a
  sparkrun recipe. [Mia-AiLab/GLM-5.3-Flash-EXL3-2x-DGX-Sparks-TensorFold](https://github.com/MiaAI-Lab/GLM-5.3-Flash-EXL3-2x-DGX-Sparks-TensorFold)
  `main` @ `3fd60df` is a **script launcher** (`./start.sh` prepares both Sparks,
  starts rank 0 where it runs and rank 1 on `WORKER`, serves `:8888`) — rank 0 is the
  invocation host, so this boot ran it on `.34` with `WORKER=.35`, never on the
  production head. Model `Mia-AiLab/GLM-5.3-Flash-EXL3-4bpw-TensorFold` @ `078455ff`
  (~176 GB, 4-bpw EXL3 + q4 dense + FP8 KV), drafter `incoai/GLM-5.3-Flash-DFlash2` @
  `bf582e4e`, image `ghcr.io/miaai-lab/glm-5.3-flash-exl3-2x-dgx-sparks-tensorfold` @
  `sha256:14b5072e…` (TF 0.6.0 + 96 patches; tag `v0.6.0-e66c657a433d`). **Fabric
  auto-detected** (bootstrap `192.168.1.34` on `enP2p1s0f0np0`, rendezvous on the CX7
  link, both RoCEv2 rails at GID 3) — no manual `NCCL_*` env needed. **BOOT-VERIFIED
  2026-10-13**: live 407 s after prepare; `GET /v1/models` → `GLM-5.3-Flash-EXL3`, chat
  round-trip OK (237 completion tokens, 184 reasoning). **KV pool 1,875,968 tokens**
  (window 1,048,576, `--parallel 4`) — below the README's 2,922,496 because the pool is
  sized from free memory at start; treat the README number as best-case, not a
  constant. **C1 decode 58.5 ± 4.5 t/s @ d0 / 60.5 ± 3.8 @ d8k** (single stream, pp
  2048, tg 128, n=5, decode phase only). **DFlash2 drafts every request** (MTP head not
  loaded, `TF_GLM_MTP=auto`), 16-row verify windows + copy drafts ≤15, **session
  acceptance 12,881 / 14,799 = 87.0 %**. **Quality 37/37 — 19/19 easy + 18/18 hard,
  0 misses** on the house held-out battery (`tools/quality-battery.py --tier both
  --max-tokens 4096`, second boot); DFlash2 acceptance over that battery run
  1,586 / 2,031 = 78.1 %. Also `tools/toolcheck.py` OK; `tools/end_of_turn.py` q4
  4/48 cut, P(eot) 0.68. Long context: `tools/needle-haystack.py` retrieved 2/2
  needles at 10 % and 50 % of a 1,000,000-token window (prompt_tokens 999,936 /
  999,740; PASS — the `--max-tokens 64` tries before the budget fix returned empty
  thinking replies, not retrieval failures). **TP=3 (3 Sparks, `./start-tp3.sh`,
  experimental) BOOT-VERIFIED 2026-10-13** on `.31-.33` (rank 0 = `.31`, never the
  production head): `COMM=nccl`, `--parallel 8`, 64-row window, live 371 s after
  prepare, **KV pool 4,841,472 tokens**; `27*43→1161` round-trip OK. C1 decode
  **65.4 ± 6.7 t/s @ d0 / 65.1 ± 8.9 @ d8k** (same decode-triage semantics, n=5
  each), DFlash2 acceptance **1,443 / 2,026 = 71.2 %** over that run. The CX7
  triangle is detected automatically (each pair shares both rail subnets; NCCL
  bootstrap on the mgmt netdev `enP7s7`, `MASTER_ADDR` = the head's LAN address,
  both RoCE devices at GID 3, `NCCL_CROSS_NIC` + subnet-aware routing), so
  `scripts/local.sh` needs only `WORKER`/`WORKER2`. Why a runbook: the launcher's
  multi-node prepare/ssh/topology logic is not expressible in the recipe schema (single
  container + command) without a shim, and TP=2/TP=3 are topologies the 4-node registry
  does not target. Receipts: `~/benchmarks/glm53-exl3-tp2-trial-20261013/` (TP=3:
  `~/benchmarks/glm53-exl3-tp3-trial-20261013/`).

- **GLM-5.3-Flash EXL3 4bpw / TensorFold, 4 Sparks (TP=4)** — runbook note, same
  external launcher (`MiaAI-Lab/GLM-5.3-Flash-EXL3-2x-DGX-Sparks-TensorFold`
  branch `tp4` @ `d220030`; `./start-tp4.sh`). **BOOT-VERIFIED 2026-10-13 on
  `.30-.33`** (rank 0 = `.30`, which is also the control host). The image
  `tensorfold-glm53:v0.6.0` (106 patches) and the `078455ff` checkpoint + DFlash2
  `bf582e4e` were replicated from the sibling's `.34` cache (175.7 GB checkpoint,
  83 shards); links auto-detected (head `192.168.0.30` ↔ the three workers over
  `rocep1s0f0,roceP2p1s0f0`). Host overrides in `scripts/local.sh`: `WORKER`/
  `WORKER2`/`WORKER3` → `.31`/`.32`/`.33`, `MASTER_ADDR=10.0.4.30`, and
  `SOCKET_IFNAME=enP7s7,enP2p1s0f0np0,enp1s0f0np0`; `NCCL_IB_GID_INDEX` left
  unset. `earlyoom` was disabled on `.30-.33` before launch and re-enabled after.
  **HEALTHY**: `GET /v1/models` → `GLM-5.3-Flash-EXL3`; chat round-trip `27*43` →
  `1161`, finish stop; `--parallel 8`, KV pool **5,834,752 tokens**, fp8 KV,
  DFlash2 drafts. **C1 decode 98.4 ± 5.9 t/s @ d0 / 99.4 ± 10.9 @ d8k** (single
  stream, pp 2048, tg 128, n=5, decode phase only) — ~2.7× our own EXL3 3.0bpw
  route above, from the 106-patch engine, q4 dense weights, split/overlapped
  prefill and DFlash2 (acceptance **1549/2023 = 76.6 %**). Why a runbook: same as
  the TP=2 entry — the launcher's multi-node prepare/ssh/topology logic is not
  expressible in the recipe schema, and the engine is an external pre-built image.
  Receipts: `~/benchmarks/glm53-flash-exl3-tp4-trial-20261013/`.

Licence note: the Flash line is MIT; the DFlash2 drafter is **CC BY-NC-ND** —
acceptable for this non-commercial cluster (owner decision 2026-10-11), not for
commercial resale.
