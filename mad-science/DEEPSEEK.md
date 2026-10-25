# DeepSeek-V4.1-Flash on GB10 — the consolidated research record

**Status:** research note, 2026-10-23. Consolidates the three `mad-science/` DeepSeek notes and the
research detail that was inlined in `TODO.md` §ds4 into one document. **No boot was run for this
consolidation**; every number below was measured in the window its receipt names. Nothing here is a
recipe change, and nothing here overrides a shipped artifact: `recipes/ds4/README.md`, the recipe
YAML, `Dockerfile.knapcio-dsv41`, the overlay mod and `attic/ds4/AGENTS.md` are authoritative where
they disagree with this page, and each is cited rather than copied.

The question this document answers without opening five files: **what these stacks are, what was
measured, what failed and why, and what is still open.**

## 1. Provenance and citation discipline

| section | fed by | date / commit |
|---|---|---|
| §3, §4 | `KNAPCIO-UPSTREAM-DELTA.md` (whole) | memo 2026-10-10, upstream HEAD `fa13563`; absorbed at commit `0c335ec` |
| §5, §7, §8 | `DS4-SPEEDUPS.md` §§1–11, the checked-and-rejected table, unverified leads, method/limits; the image-reproducibility and b12x detail previously inlined in `TODO.md` §ds4 | survey 2026-10-19 (no boot); inlined detail 2026-10-22; absorbed at `0c335ec` |
| §7, §11, §12, §13 | `DEEPSEEK-1017-DECODE-RESEARCH.md` (whole) | note 2026-10-20 (no boot); absorbed at `0c335ec` |
| §9 | `TODO.md` §ds4 prefill-chunk item; `recipes/ds4/README.md` §Knobs | measured 2026-10-22 |
| §10 | `DS4-SPEEDUPS.md` (whole survey, including its two TP=2 items) | 2026-10-19, plus the 2026-10-21 measurements recorded in it |
| §14 | `TODO.md` §ds4, `QUESTIONS.md` | live work items |
| §17 | vLLM's own DeepSeek-V4.1 recipe and model-registry entries; the `local-inference-lab/vllm` b12x fork's Engram config, disk table and four-Spark launchers; the `spark-vllm-docker` 4x recipe and image tag; the retired `attic/ds4/` vLLM verdicts; the 1017 model card | study 2026-10-23, no boot — upstream `main` @ `d561af5d`, fork `dev/karmic-kraken` @ `8244d1c4` |
| §18 | `MashieSaldana/DeepSeek-V4.1-Flash-1017-4x-DGX-Spark` @ `ec61f23` (recipe, docs, benchmark CSVs); knapcio `403a5aa2` vs our `27616bec`; the git-ignored `.scratch/ds4/knapcio/logs/boot9-head-serve.log` | study 2026-10-23, no boot |
| §18.1 | the 2026-10-23 TP=4 window's receipts (`~/benchmarks/tp4-pad-20261023/` on the head: `a1-control-*`, `b1-treatment*`) | measured 2026-10-23, four boots attempted (one clean serve) |
| §19 | the uncommitted owner-guidance file's upstream survey: GitHub API/raw reads of `knapcio/DeepSeek-V4.1-Flash-4x-DGX-Spark-TP4` against our overlay pin `27616bec`, upstream HEAD `aff52fa5` | survey 2026-10-26, no boot |

The three source notes were deleted (`git rm`) in the same commit that created this document; the
filenames above are provenance, not live paths. Everything they stated is in the sections named, and
their verbatim history is `git log --diff-filter=D --` on those paths.

**Evidence vocabulary** (the directory's): **VERIFIED** = read from a primary artifact or measured on
GB10; **LIKELY** = strong secondary evidence; **UNVERIFIED** = no primary source, or one that does not
cover SM121. `SPECULATIVE` is used where the directory uses it (reasoning without a source).

**Number discipline.** Every decode cell below is a `llama-benchy` record with
`is_context_prefill_phase: false` unless stated. `±` is the **sample sd (ddof 1)** of the per-run
values, recomputed from the run files; a receipt JSON's own `tg_throughput.std` is the **population**
sd, `0.894×` that at n=5, and some older lane prose quotes the JSON field. Cold-boot ladders
contaminate C1 (first run 19–39 t/s) — no ladder's C1 cell is an arm's single-stream number.

## 2. The family boundary

Five distinct things, kept apart throughout:

| what | body / engine | topology | this document |
|---|---|---|---|
| **Stack A — knapcio SGLang** | official `deepseek-ai/DeepSeek-V4.1-Flash-1017`, native MXFP4/F8 (510.31 GB), SGLang `dsv4.1` + b12x/b12x_next + RoCEnante | TP=4 EP=1 over four GB10 (`.30`–`.33`) | §3–§10 |
| **Stack B — TensorFold EXL3** | `LibertAIDAI/DeepSeek-V4.1-Flash-1017-EXL3-2.9bpw`, 210.72 GB, Engram streamed from NVMe; TensorFold fork | TP=2 (`.34`/`.35`) | §11 |
| **Stack C — vLLM b12x (unbooted)** | official `deepseek-ai/DeepSeek-V4.1-Flash-1017` on `local-inference-lab/vllm` (a fork of upstream vLLM) with b12x kernels and **disk-backed** Engram — the only vLLM route not excluded by memory | TP=4 over four GB10 | §17 |
| **The TP=1 byte wall** | any 1017-class body on one 128 GB node | TP=1 | §12, §13 |
| **Excluded artifacts** | `mad-science/FLARE.md` (own consolidated document), the GSQ strata export (§15.2), `recipes/*`, `attic/*`, `tests/`, `tools/`, `benchmarking/` | — | cited, never absorbed |

The single most important boundary: **Stack A and Stack B differ in engine, quantization and topology
at once**, so every TP=2-vs-TP=4 ratio in §12 is a lane-vs-lane comparison at matched concurrency, not
a controlled TP sweep. The registry has never booted one engine on both topologies (§14, `QUESTIONS.md`
`#3`).

Stack C is **unbooted**, so no ratio involving it exists: §17 treats it as a documented route with a
declared parity bar and one acceptance test, not as a measured arm.

The community 1017 repository in §18 is **not** a fourth stack: it is Stack A carrying a different env
line — same base-image digest, same SGLang tree, same adapters — so it explains a candidate on our own
serve rather than adding an engine to compare.

## 3. Stack A — what the knapcio TP=4 stack is

| field | value | authoritative source |
|---|---|---|
| Recipe | `recipes/ds4/deepseek-v4.1-flash-knapcio-tp4-1m-sglang.yaml` | the file |
| Upstream | [`knapcio/DeepSeek-V4.1-Flash-4x-DGX-Spark-TP4`](https://github.com/knapcio/DeepSeek-V4.1-Flash-4x-DGX-Spark-TP4), a downstream of MiaAI-Lab's recipe; launcher, adapters, b12x kernels and measurement design are theirs | `recipes/ds4/README.md:24-33` |
| Model | `deepseek-ai/DeepSeek-V4.1-Flash-1017` (2026-10-17 refresh), native MXFP4/F8, 510 GB | recipe `:2` |
| Pin chain | image bakes `fb2764a5…` (never served) → recipe pinned `5254448103b6254fc646dacbca1cbbf20e9216c1` on 2026-10-14 → **live pin `1bae0e1088993b9b82de08f59de5be5a34e42170`** (all 48 shards new LFS objects vs pre-refresh) | recipe `:7`; `attic/ds4/AGENTS.md` §5, §12.17 |
| Image | `littlecedar/dgx-spark-dsv41:canary-roce@sha256:acfc331a959b247a1ce356a864d167a7bf2bffd91694d9caa1102e334ff4ee93` (image id `sha256:1db2155f…`), built 2026-10-17 from upstream `27616bec` (v2.4) + the local health-port patch | recipe `:9`; `Dockerfile.knapcio-dsv41:41-47` |
| Mod | `recipes/ds4/mods/dsv41-sglang-overlay` — fail-closed gate + launcher shim; holds the whole production env | mod `README.md` |
| Topology | TP=4, EP=1, four GB10, one rank per node | recipe `:10,39` |
| Context | 1,048,576 tokens served, page-shared | recipe `:40` |
| Spec decode | DSpark k=5, verify-all | recipe `:44` |
| Transport | RoCEnante RDMA (SG17 overlay adapted to TP4), shipped on; rollback is `SGLANG_ROCE_ALLREDUCE=0` | mod `README.md`; lane README §Knobs |
| Serve line | 0.78 static, 8192 chunks, `MAX_TOTAL_TOKENS=6,850,000` pin (→ 6,849,792), 16 slots, `--swa-prefix-tails 128`, prefill/decode interleave **off**, `DSV41_FAST_LOAD=1` | §7.3; lane README §Measured: the v2.4 serve line |
| Engram | packed per rank on node-local NVMe, 2 × 23.6 GiB/rank, 57–73 s on a first boot | `attic/ds4/AGENTS.md` §12.17 |

**RoCEnante is the single largest lever measured on this lane:** 1.70×/1.69×/1.81×/1.23× over NCCL at
C1/C4/C8/C16, far outside the 7–25 % boot spread (`attic/ds4/AGENTS.md` §7.13, 2026-10-02 short-prompt
harness: 46.5 / 106 / 133 / 193 t/s with RoCEnante, 27.4 / 62.5 / 73.2 / 155.0 NCCL-only).
Quote a ladder with its prompt length attached — the short-prompt harness uses ~17-token prompts and
the standard profile 2048-token prompts; the two agree at c1 only.

## 4. Upstream provenance and the post-pin delta (2026-10-10)

**Headline, which corrected the earlier scan's premise: our pin `58f2321` IS the v2.3 release commit** —
`docs: v2.3 results (fresh-clone gate, 2200 MHz cap)`, 2026-09-29T15:09:02Z, whose parent is the v2.3
candidate **code** commit `5f11a97` (`adapter/cert_head.py`, `replay_guard.py`, gates). The v2.2/v2.3
"throughput work" and the "do not use NVFP4 on GB10" verdict are therefore **already at (or before)
our pin**, not past it.

**Only two commits existed after the pin, both 2026-10-09, both documentation-only.** No v2.4, no tag,
no GitHub release (`/releases` → `[]`); history linear (`4e70a6c.parent = 58f2321`,
`fa13563.parent = 4e70a6c`) — no force-push, no rewrite. Method: fresh clone (HEAD `fa13563`), full
`git log`/`git diff 58f2321..HEAD`, GitHub API corroboration.

```
git diff --stat 58f2321..HEAD
.env.tp4.example               |  43 ++++++++--
README.md                      |  24 ++++++-
docs/chunked-prefill-memory.md |   5 ++
docs/community-results.md      |  16 ++
docs/switchless-ring.md        | 123 ++++++++++++++++++--
```

`git diff --stat 58f2321..HEAD -- Dockerfile.canary-roce Dockerfile scripts/ adapter/ boot.py
runtime/` is **empty**. Zero changes to `boot.py`, the adapter overlay, the b12x/b12x_next kernels,
the Dockerfile, or the SGLang-pin script (`scripts/fetch-sglang-canary.sh`, still stages `dsv4.1 @
f80c91a4b`). **Nothing in the delta can change a served number.**

| SHA | Date | Subject | Files |
|---|---|---|---|
| `4e70a6c` | 2026-10-09 | docs: host prerequisites, download step, patched NCCL and ring addressing | `.env.tp4.example`, `README.md`, `docs/chunked-prefill-memory.md`, `docs/switchless-ring.md` |
| `fa13563` | 2026-10-09 | docs: bring-up pitfalls, ring recovery notes, results from other fleets | `.env.tp4.example`, `README.md`, `docs/community-results.md` (new), `docs/switchless-ring.md` |

Both are prose ports of Saolence's first-deployer review (#3/#4, closed unmerged) and other fleets'
field reports.

| # | Change | Verdict | Why |
|---|---|---|---|
| 1 | `.env.tp4.example` — `IB_HCA` corrected to `rocep1s0f0,roceP2p1s0f0`, "names are host-specific" | **Reject** (already covered, better) | the launcher deliberately sets no `NCCL_IB_HCA`/`B12X_ROCE_HCA`; sparkrun's IB probe fills them (ds4 `AGENTS.md` §6) |
| 2 | `.env.tp4.example` — `EP_SIZE=4` does not boot with `DSV41_MOE_B12X_NEXT` | **Reject** (corroboration only) | the lane ships `EP_SIZE=1`; §8 already records EP>1 dying at the first decode plan |
| 3 | `.env.tp4.example` — `DSV41_CACHE_GIB=0` trade-off: "one ring fleet reported +9 % KV pool and +1.5 GiB MemAvailable… not re-measured here" | **Defer** → later **closed negative** | tested 2026-10-18: pool 9,381,376 vs 9,386,240 (**−0.05 %**), so the claimed +9 % does not reproduce (`attic/DONE.md` (a) closure) |
| 4 | `.env.tp4.example` — `HF_REPO`/`HF_REVISION`/`EXPECTED_SHARDS=48` documented | **Reject** (no delta) | `HF_REVISION=fb2764a5…` matches `boot.py:24` already at the pin |
| 5 | `.env.tp4.example` — Engram pack "~68 → ~48 GiB/node at TP4 (measured)" | **Reject** (cosmetic) | size-figure correction, no config impact |
| 6 | `.env.tp4.example` — `SGLANG_RUST_BUILD_MODE=never` cargo-probe hang workaround | **Defer** → later **closed** | tested 2026-10-18: `auto` does not hang (532 s) because the Rust image processor is unavailable in this image |
| 7 | `README.md` — host prerequisites + `./start-tp4.sh download` | **Reject** (not applicable) | sparkrun owns distribution; MiaAI-Lab's `start.sh` is not our launcher |
| 8 | `docs/*` — ring recovery notes, community results | **Informational** | field reports from other fleets; nothing to adopt |

**Verdict then:** no rebuild, no re-pin — the shipped lane was at the upstream code frontier. **Verdict
now:** superseded. Upstream moved to **v2.4 `27616bec` (2026-10-12)**, and the lane rebuilt on it
2026-10-17 (§5). The memo's two deferred items are both closed with results (§8.5).

## 5. Stack A — the image: build, pins, reproducibility

**Base and tree.** `lmsysorg/sglang:dev-dsv41@sha256:4a5d132a06a77c8331e15845f2e925adc788b00105097ad55409afa3f4fa4860`
(floating tag digest-pinned 2026-10-22 so the base cannot move under a rebuild) + the upstream `dsv4.1`
branch at **`f80c91a4b` (2026-09-16)** replaced wholesale (`runtime/sglang-canary/python`, from a GitHub
tarball because the image's git cannot fetch unauthenticated), kernel pins `sglang-kernel==0.4.7` and
`sgl-deep-gemm==0.2.0` (aarch64 wheels from PyPI), Mia's SM120 page-split override re-applied, plus the
RoCEnante overlay, b12x/b12x_next, the adapter overlay and the compiled `row_store.so`. arm64-only,
33.5 GB. v2.4 adds the `BASE_IMAGE` build arg, the encoding-placeholder anchor check
(`runtime/patch_encoding_dsv41.py`) and the Messages-thinking / prefill-bypass in-image tests.
(`Dockerfile.knapcio-dsv41:1-63`.)

**The `git apply` is load-bearing.** The dynamic HEALTHCHECK is a **local** patch to the build
context's `boot.py`, absent upstream (knapcio `58f2321`, `27616bec` and `origin/main` all lack it). A
literal fresh-clone build silently drops it and produces a **different** image — measured 2026-10-14:
image `dd9d1c3c…`, digest `ac9bc917…`, whose `boot.py health` has no `health_port()` and
re-introduces `(unhealthy)` on any port but 8888. **Never push that as `canary-roce`.** With the patch
applied the cached build reproduced the v2.2-era image `18e36391…` / digest `4e5002ab…` exactly
(patched `boot.py` sha256 `6d2b4898…`). The patch is vendored as
`recipes/ds4/boot.py.health-port.patch`; `Dockerfile.knapcio-dsv41` is a reference **copy** of
upstream's `Dockerfile.canary-roce` body (header + body, body sha256 `dbd1cfbf…`), not self-contained.
(`Dockerfile.knapcio-dsv41:6-34`; `attic/ds4/AGENTS.md` §5.)

Why the patch exists: the image bakes `HEALTHCHECK CMD ["python3","-S","/opt/dsv41/boot.py","health"]`,
and `boot.py health` originally probed `127.0.0.1:$SERVER_PORT` defaulting to 8888. Docker freezes
`Config.Env` at `docker run`, so a value the launcher sets at runtime is below its view and sparkrun
never puts `SERVER_PORT` there — a server on any other port reported `Up … (unhealthy)`. The rebuild
makes `boot.py health` resolve the port as `HEALTH_PORT`/`SERVER_PORT` → the port the launcher
persists to `/tmp/sparkrun_health_port` → the engine's own `--port` from `/proc/<pid>/cmdline` → any
LISTEN port from `/proc/net/tcp{,6}` → image default. (mod `README.md` §Docker's HEALTHCHECK.)

**Image reproducibility (2026-10-22) — behavior-identical, NOT byte-reproducible.** The rebuild from
the same context with the base digest-pinned produced `littlecedar/dgx-spark-dsv41:canary-roce-20261022`
= **`sha256:0cbe228a…`**, which is **not** the shipped **`acfc331a…`**. Config is identical
(entrypoint, cmd, env, healthcheck, labels); 91 layers, layers 0–69 identical; the content diff is
four recompiled `__pycache__/*.pyc` plus 6,707 hash-equal files. So it is a drop-in for serving but not
a reproducible artifact, and the shipped tag stays pinned. Unblocker: a deterministic build step
(bytecode off, `SOURCE_DATE_EPOCH` set). Receipt: `~/benchmarks/ds4-expin-20261022/image-compare.txt`.
*(The lane README's "Reproducibly rebuilt … drop-in" phrase is a compatibility claim, not a byte
claim; this note records the byte verdict. Duplicate finding, one statement, per `TODO.md` §ds4.)*

**What a boot must read, not infer.** `launch.json` records the image's baked `REVISION =
fb2764a5…` (`boot.py:24`, written at `boot.py:471-475`) regardless of what is served — it is **not**
evidence. The served checkpoint is identified by the launcher's
`MODEL_ID is an on-disk checkpoint dir; serving …/snapshots/<sha>` line, `/v1/models`, and the
`ships no chat_template.jinja; serving …` line. `docker exec <c> env` is not a valid probe either: the
launcher rewrites its own environment before `execve`.

## 6. Stack A — the launcher, the overlay, and who owns which value

**Why a shim.** `boot.py` builds the entire `sglang.launch_server` argv from environment variables and
its entrypoint is `python3 -u /opt/dsv41/boot.py run`; sparkrun's SGLang runtime instead assumes
`sglang serve …` and appends `--dist-init-addr HOST:PORT --nnodes N --node-rank R`. `launcher.py`
consumes those three flags, maps them to `DIST_INIT_ADDR`/`NNODES`/`NODE_RANK`, and execs `boot.py`.
Serve parameters ride in the recipe's `command:` (`--model`, `--tp`, `--context-length`, `--port`,
`--dspark-block-size`, `--fp8-gemm-backend`) or in the mod's `RECIPE_ENV` (everything else).

**The gate is fail-closed.** `run.sh` refuses unless `/opt/dsv41/boot.py` exists,
`/opt/dsv41/adapter/sitecustomize.py` exists and contains `EngramLoader`, `/opt/b12x_next/b12x_next`
exists, and the engine's `engram.py` exists; it then creates and `reown`s the cacheable-object
directories under `/cache/runtime` (`engram`, `state`, `b12x-compile`, `b12x-roce`, `model-overlay`).
Nothing in the image is modified.

**`RECIPE_ENV` overrides, it does not default.** It is applied with `env.update(RECIPE_ENV)` because
the image bakes `STATE_PATH=/state`, `DSV41_CACHE_GIB=16`, `PYTORCH_CUDA_ALLOC_CONF=…True`,
`SGLANG_RUST_BUILD_MODE` and `OFFLOAD_MODE`; a `setdefault` would let those win (silently redirecting
state to an unwritable `/state`, and re-arming the allocator mode that NaNs above 64 prefill query
tokens). The recipe therefore carries **no `env:` block**, and a value that exists only as a
`RECIPE_ENV` entry has **no `-o env.` path** — that is why γ became a `defaults` key with a launcher
flag. `AB_ENV` is the allow-list that lets a recipe `env:` block win: `EP_SIZE` joined it 2026-10-22
for the EP=4 experiment; `PREFILL_DECODE_INTERVAL` and the v2.4 knobs are already in it.

**The 1017 template farm.** The refresh ships **no `chat_template.jinja` by design** (its card points
at `encoding/encoding.py` and the `deepseek-recipe` toolkit), and this SGLang resolves the template
from `<model_dir>/chat_template.jinja` when the tokenizer carries no embedded one
(`srt/utils/hf_transformers/processor.py:383-390`). `launcher.py:ensure_template_overlay()` serves
`/cache/runtime/model-overlay`: a symlink farm of the checkpoint whose one real file is the mod's
`chat_template.jinja` (byte-identical to the TensorFold lane's, sha256 `297be886…`, guarded). Nothing
is copied from the 475 GB checkpoint, the snapshot is never written through, the farm is rebuilt from
content every boot (foreign links dropped), a checkpoint with its own template is served untouched,
and an unstageable template exits 2 rather than serving templateless. `boot.py:475` re-derives
`DSV41_SOURCE` from `MODEL_PATH`, so every rank's engine sees the farm. Per-rank claim: *farm staged
on every rank, template resolved on the serving rank* — workers show no template line by design, and
the `Loaded chat_template from …` line belongs to the download path so its absence proves nothing.

**Engram re-packs itself, detached.** `pack_engram.py` derives each rank's shards from the
checkpoint's `model.safetensors.index.json`, so a new checkpoint invalidates the pack (shards 47/48
are `76a05106…`/`9dc51433…` on the refresh). Missing shards ⇒ the launcher starts the packer detached
(`flock`-guarded, one per node) and boots on the checkpoint fallback; packed shards are used from the
next boot. 2 × 23.6 GiB per rank in 57–73 s (340–440 MiB/s, node-local snapshot). Synchronicity would
blow sparkrun's ~150 s head rendezvous, and correctness is unaffected: `adapter/engram_backend.py`
treats the packed shard as optional acceleration and `row_store.cpp` fails closed on a range mismatch.

**Checkpoint resolution.** On a real launch sparkrun renders `{model}` to the prepared on-disk snapshot
path; a dry run still shows the repo id. `launcher.py:resolve_checkpoint()` accepts that path, or a
repo id resolved in `/cache/huggingface/hub/models--<org>--<name>` (preferring `refs/main`, else the
newest snapshot carrying `config.json` and `model.safetensors.index.json`), and leaves a container-bind
`MODEL_PATH` alone. No snapshot path is ever spelled in the recipe; a cache that re-resolves cannot
break the boot; a `--served-model-name` that arrives as a path is reported back as the repo id.

### 6.1 The b12x backend is declared, not inherited — and the guard keeps the last word

The image's `boot.py` (`@ 27616bec`) **strips every `--fp8-gemm-backend` carried in
`EXTRA_SGLANG_ARGS` and appends its own last** (`required_sglang_args()`, `boot.py:264-287`, called at
`:376`; the launcher's mapping is at `launcher.py:219-229`), keyed off `DSV41_MXFP8_BACKEND=b12x` (image
default). So the arg cannot win the *order*, and an undeclared recipe boots with a substitution warning:
`DSV41_MXFP8_BACKEND=b12x requires --fp8-gemm-backend flashinfer_cutlass; effective value 'auto
(omitted)' replaced`. b12x was active either way (the value the engine ran was `flashinfer_cutlass`),
but nobody declared it, so reading `--fp8-gemm-backend` as "unset" mis-diagnoses prefill GEMM
behavior. The repair (`18a05d2`, 2026-10-22 13:32:53, "Declare the dense FP8 GEMM backend in the ds4
knapcio arm") spells the flag in the recipe's `command:`, which the launcher maps to
`FP8_GEMM_BACKEND` → `EXTRA_SGLANG_ARGS`; the guard's rewrite then re-stamps the same value and goes
silent instead of replacing an omitted one, and the declared value still reaches the engine if the
image default ever goes away. Reproduced offline against `boot.py @ 27616bec`: the declared extras
yield exactly one `--fp8-gemm-backend flashinfer_cutlass` with no warning under both
`DSV41_MXFP8_BACKEND=b12x` and `=off`, while the pre-change extras yield the warning.
Guard: `test_fp8_gemm_backend_is_declared_not_inherited`. **Acceptance is a quartet boot and is
UNVERIFIED** — it must show `[moe_b12x_next] armed`, `fp8_gemm_backend='flashinfer_cutlass'` in the
`server_args` dump, **no** `WARNING: DSV41_MXFP8_BACKEND=` line, and exactly one flag in
`launch.json`'s args; then compare prefill GEMM against the recorded **2897 t/s cold pp at C1**,
within the inter-boot floor.

### 6.2 The DSpark γ knob: no route, then a route

`DSPARK_BLOCK_SIZE` is a `RECIPE_ENV` entry applied with `env.update(...)`
(`mods/dsv41-sglang-overlay/launcher.py:166`), so `-o env.DSPARK_BLOCK_SIZE=3` is silently clobbered
back to 5. The shipped fix (2026-10-18): a `--dspark-block-size` launcher flag (`launcher.py:555-557`,
applied at `:607-611` *after* `apply_recipe_env`), `defaults.dspark_block_size: 5` plus the
`--dspark-block-size {dspark_block_size}` placeholder in the recipe (`…knapcio-tp4-1m-sglang.yaml:41-54`),
and the effective value printed on the launcher's boot line (`launcher.py:644-645`, `… CONTEXT=1048576
DSPARK_BLOCK_SIZE=5` on all four ranks) — that line is the per-boot proof the value landed. Shipped
behavior is unchanged at 5; §8.2 is why 3 does not boot.

### 6.3 The fast loader

`DSV41_FAST_LOAD=1` is shipped since 2026-10-22 (owner decision): the eager path cuts engine start from
343 s to ~124 s but leaves the KV pool smaller and more variable between boots, because SGLang sizes
the pool from the head's `MemAvailable` right after the loads and the pinned reads leave memory
visible-but-uncounted then. Upstream's documents disagree in width — `docs/fast-load.md` 3–6 % at EP2
(7.27M vs 7.47–7.82M tokens), the README summary 3–13 % — and its EP1 slab rework "gave back ~0.7M
tokens". **The lane's EP1 delta is UNMEASURED**, so the `MAX_TOTAL_TOKENS` pin is not pre-scaled: it
stays at 6.85M for the first fast-loader boot and is re-derived from that boot's `full_token` if it
clamps. `DSV41_FAST_LOAD=0` is the rollback; the fast path logs `DSV41 fast load ARMED: …` and nothing
when off, so a bare pool figure does not identify which loader produced it.

## 7. Stack A — measured: ladders, accuracy, and how to read them

### 7.1 The v2.3 line: two same-config boots (2026-10-18)

Profile: `benchmarking/concurrency-ladder.yaml`, depth 0, 2048-token prompts, 128-token replies,
prefix caching, 5 runs/cell; v2.3 serve line = 0.80 static / 4096 chunks / 9.4M pin. Receipts
`~/benchmarks/tp4-20261018/`, deployment `a2e141223b52793c_7afff0589a33` (three boots under one id).

| cell | boot A (`knapcio-ladder`) | boot C (`knapcio-ladder-suiteboot`) | A→C |
|:--|--:|--:|--:|
| C1 | 69.65 ± 11.51 (56.8–87.9) | 69.28 ± 5.25 (64.0–77.5) | −0.5 % |
| C2 | 89.89 ± 3.57 (85.5–95.4) | 86.40 ± 3.59 (80.3–89.6) | −3.9 % |
| C5 | 113.44 ± 6.84 (105.1–123.6) | 108.78 ± 14.19 (86.5–125.4) | −4.1 % |
| C10 | 115.36 ± 6.62 (107.7–123.1) | 116.27 ± 6.22 (105.2–119.8) | +0.8 % |

Per cell pp t/s: boot A 3703 / 4004 / 4532 / 4849; boot C 3674 / 4125 / 4567 / 4671. TTFT ms: 556 /
1018 / 2167 / 3188 and 560 / 993 / 2029 / 3347. C2 is the lane's first cell at exactly 2, C5/C10 its
first at 5 and 10 — the depth-0 row (C4/C8/C16) is a *different shape*, not a cross-check. C10 sits at
or above C5 on both boots (+1.7 %, +6.9 %): that is what a page-shared 9.28M-token pool admitting ten
2048/128 requests without extent reservation looks like, a shape rather than a queueing claim.

**Boot facts, both boots.** KV pool **9,277,952** full tokens — the launcher's 9.4M pin is clamped to
the engine's profiled value (`max_total_tokens=9400000 is larger than the profiled value 9277952. Use
the profiled value instead.`, all four ranks), never refused — with swa 51,712 / c4 2,319,488 / c128
72,484. TTR 487.797 s port / 501.714 s HTTP (boot A), 491.887 / 505.725 s (boot C). `ROCE_TP8_READY`
on all four ranks, `world_size 4`, hcas `roceP2p1s0f0,rocep1s0f0`, `max_size` 2097152. `Engram shards
present for rank r/4` on all four (neither boot packed). `/v1/models` →
`deepseek-ai/DeepSeek-V4.1-Flash-1017`, `max_model_len` 1048576.

### 7.2 Accuracy

Standard suite, one serve (boot C), `tools/eval-suite.py` 1.0.1, verdict `ok`:

| leg | result |
|---|---|
| contract | ok — model id, `max_model_len` 1048576, greedy `READY`, finish `stop` |
| house | **36/37** — easy 19/19, hard 17/18, the one miss `hard-rev` (reply `nrukraps`) |
| needle | **3/3 at each rung** — 32,768 (max prompt 32,786) / 131,072 (131,137) / 983,040 (**981,950**); 1852 s for the three rungs |
| tool-eval-bench | **90** — 27/30, 15 scenarios, 13 pass / 1 partial `TC-14` / 1 fail `TC-03` (`wrong_args`), ref v2.6.0 |

Two harness notes: `tool-eval-bench` is not reachable through `sparkrun benchmark performance`
("Framework 'tool-eval-bench' is not registered for category 'performance'") — the call is
`sparkrun benchmark tools … --profile benchmarking/standard-suite.yaml`; and `--skip-run` matches a
running deployment by intent id, which hashes the `-o` overrides, so pass the same overrides to the
bench call as to the launch.

The two open accuracy legs closed 2026-10-22 (same recipe and node set, one fresh four-node boot):
hard **ARC 93.5 %** (187/200) and **GSM8K 97.5 %** (195/200), thinking off, seed 1234,
`--hard-limit 200`, 0 errors / 0 empty replies, both legs in one serve (427.6 s, suite 1.0.1, verdict
`ok`), Engram packed on both layers (hit_rate 100 %). Receipt
`~/benchmarks/tp4-20261022/knapcio-arc-gsm8k/`.

**The 2026-10-24 window's suite legs (boot 6, `.31`–`.34`, shared-cache pool, shipped 16384-chunk
line, task `a2e141223b52793c_d9b5393d1cb6`, KV 3,132,416 this boot).** House **37/37** (easy 19/19,
hard 18/18, 14.2 s); needle **3/3** with `--needle-max-tokens 512` at 32,768 / 131,072 / 262,144
(167.0 s) — **caveat: the lengths were the tool's `auto` set, so the top rung is 262,144, NOT the
historical 983,040**; the 983k rung is not re-claimed by this leg. tool-eval-bench **90, ★★★★★
Excellent** (15 scenarios, ref v2.6.0, run `2026-10-24T18-13-07…afc6319b`). The ladder leg ran on
the earlier boot 5 (`a2e141223b52793c_b696795db281`, KV 2,887,936, n=5/cell, decode rows):
**C1 65.98 / C2 84.94 / C5 126.69 / C10 152.5 t/s** (pp 3890 / 4734 / 4621 / 3886) — C5 and C10
sit above the v2.3 bands (111/116); **one boot each, low-KV pools both**, so not a new baseline;
the 16384 chunk plausibly reduces prefill/decode switching under concurrency, which the
interleaved re-take would have to confirm. Receipts `~/benchmarks/tp4-window-20261024/`
(`boot6-suite-eval/`, `boot6-toolbench.{json,csv}`, `suite-ladder.json{,.csv}`).

**Long-needle re-take, 2026-10-24 ~15:45 ET (boot 10, same shipped line, task in
`boot10-needle.launch.log`): the boot-6 caveat is RESOLVED UPWARD.** `tools/needle-haystack.py`
depths 10–50 at a 1,048,576-token window, `--chars-per-token 4.0065`, `--max-tokens 512`
(non-truncated answers): **5/5 PASS at ~999k prompt tokens** — 998,468 / 997,583 / 999,044 /
999,281 / 999,241 prompt tokens, latencies **257.5 / 252.2 / 248.5 / 262.4 / 268.0 s** (~4.1 min
per 1M prefill at the shipped 16384 chunk). The window's needle leg now matches the baseline
receipt's bar (5/5 at ~999k, depths 10–50) rather than the auto-length 262,144 top rung.
Receipts `needle-983k-retake.{log,json}` in the window root.

### 7.3 The v2.4 line: three boots and the pool re-derivation

Same image digest, same pin, same ladder; three TP=4 boots on `.30`–`.33`, one four-node job at a
time, `--transfer-mode local`. Receipts `~/benchmarks/ds4-v24-line-20261018/` (`ladder.*`, `house/`,
`serve-evidence.txt`; `pd-off/`, `confirm/`).

| cell | interval **on**, 7.5M pin | interval off, 7.5M pin | interval off, 6.85M pin |
|:--|--:|--:|--:|
| C1 | 60.22 ± 13.00 (39.0–71.4) | 51.84 ± 17.68 (23.4–64.2) | 53.40 ± 21.35 (19.5–69.9) |
| C2 | 73.16 ± 4.96 (68.9–81.6) | 88.35 ± 6.33 (81.7–96.7) | 82.02 ± 10.14 (71.0–94.8) |
| C5 | 95.10 ± 14.66 (69.3–106.0) | **131.83 ± 8.50** (122.4–139.7) | 130.97 ± 10.50 (117.4–143.4) |
| C10 | 101.49 ± 10.45 (89.3–114.2) | 123.49 ± 8.45 (114.3–135.1) | 119.79 ± 8.09 (107.5–127.1) |

**(a) The image pin moves nothing.** All five TP=4 SGLang boots with a retained `bench.log` ran the
same digest `acfc331a…`, read from each boot's `bench.log`. The v2.4 *line* with its interleave flag
**on** was slower than the v2.3 line on every cell: C2 −17.0 %, C5 −14.4 %, C10 −12.4 % against the
v2.3 means (89.1 / 111.1 / 115.8).

**(b) `--prefill-decode-interval 2` costs 17–28 % of steady-state ladder throughput and ships off.**
Same-pin pair (7,500,000 both): C2 73.16 → 88.35 (−17.2 % with it on), C5 95.10 → 131.83 (−27.9 %),
C10 101.49 → 123.49 (−17.8 %). It is a multi-user *latency* feature (a short request is answered
mid-prefill), not a throughput one. `PREFILL_DECODE_INTERVAL: "0"` is the launcher default
(`launcher.py:247`), the knob is in `AB_ENV` (`launcher.py:335-338`) so `-o env.PREFILL_DECODE_INTERVAL=2`
re-enables it per launch, and `extra_sglang_args` (`launcher.py:357-382`) omits the flag at 0 so the
engine default applies. Guard: `tests/test_ds4_recipes.py:1338-1349`.

**(c) With it off: C5 +18 %, C10 +3–7 %, C2 at parity at best.** C5 131.83 / 130.97 against
113.44 / 108.78 = +18.7 % / +17.9 % on the line's 111.1 mean (+16.2 % / +15.5 % against its best cell);
C10 123.49 / 119.79 against 115.36 / 116.27 = +6.6 % / +3.4 % on the mean (+6.2 % / +3.0 % against its
best); C2 88.35 / 82.02 against 89.89 / 86.40 = +0.2 % / −6.9 % on the mean — at best parity. The two
off boots differ only in the pin and sit inside each other's sd, so 7.5M → 6.85M is not a throughput
factor.

**(d) None of these C1 cells is the arm's C1.** Every ladder's first run is cold — 39.0, 23.4, 19.5 t/s
— and the cell mean is the ramp: 39.0 / 64.5 / 57.4 / 68.8 / 71.4 (interval 2), 23.4 / 45.6 / 62.3 /
64.2 / 63.8 (off, 7.5M), 19.5 / 45.5 / 63.4 / 69.9 / 68.7 (off, 6.85M). The pooled 67.18 ± 6.97 (§7.5)
stays the reference until an interleaved C1 re-take on the shipped line exists; none was taken.

**The pool pin: formula, measurement, correction.** At 0.78 the engine's budget arithmetic predicted
**7,687,277** full tokens — 9,277,952 measured at 0.80, minus 1,564,260 for the smaller static pool
(0.02 × 121.7 GiB / 1670.75 B per token), minus 26,415 for 64 extra prefix tails (384 SWA slots ×
1,795.8 B); the arithmetic is pinned in `tests/test_ds4_recipes.py:1326-1336`. The boot measured
**6,993,408**, so the formula under-estimated the tails' cost by ~0.7M tokens
(`max_total_tokens=7500000 is larger than the profiled value 6993408. Use the profiled value instead.`,
`pd-off/boot-evidence.txt`, 21:33:43Z). A pin at or above the budget is silently **clamped**, never
refused, which would put the pool back to being a boot lottery — so the pin became **6,850,000**, 97.9 %
of the measured budget. The confirm boot reports **6,849,792** with **no clamp line** (the pin floored
to the engine's 256-token page, 6,850,000 → 256 × 26,757) and `available_gpu_mem` 17.53 GB against
16.70 GB at the clamp. Read every boot: `max_total_num_tokens=…`, then `chunked_prefill_size=8192`,
`max_prefill_tokens=16384`, `max_running_requests=16`, `context_len=1048576`. Guard:
`test_launcher_v24_serve_line` (`tests/test_ds4_recipes.py:1302-1375`) asserts 0.78 / 8192 / 16, a pin
> 0 and **below 6,993,408**, the tails-only default assembly, and that a launch-time `0` disables each
knob; it deliberately does not pin the exact integer. Cost: 6.85M page-shared tokens holds **six** full
1M contexts, where the 0.80 / 4096 line's 9.28M held nine.

**Quality on the shipped line was not re-taken.** The house battery ran on the interval-**on** boot only
— 36/37 (easy 19/19, hard 17/18) — and neither interval-off serve ran a quality leg, so that number
transfers to the shipped line by assumption, not measurement.

### 7.4 The depth-0 shape and the 2026-10-22 live baseline boot

Depth-0 profile (`benchmarking/ds4-sglang-depth0-ladder.yaml`, C1/C4/C8/C16, 3 runs/cell, `--fresh`),
1017 arm after two cold prefill probes: **C1 80.97 ± 4.29, C4 118.87 ± 13.92 (runs 104.2/131.9/120.5),
C8 107.53 ± 9.64 (101.9/102.1/118.7), C16 115.90 ± 3.82 (111.5/117.7/118.5)** vs the V4.1 base's
59.21 ± 3.54 / 110.85 ± 1.05 / 111.38 ± 1.53 / 112.80 ± 2.69: C4 +7.2 %, C8 −3.5 %, C16 +2.7 %, each
inside the spreads, so **no speed change is established**; cold prefill 119k 29.53 s (3904 tok/s) and
231k 64.79 s (3455 tok/s) against 27.93/66.02 s. Receipt `~/benchmarks/ds4-knapcio-1017-20261018/`,
bench `bench_147c4e4cadab`. Boot receipt: cold launch 57 min (the ~475 GiB/node distribution), warm
relaunch **545.9 s** total, **8 m 31 s** container start → first `/v1/models` 200, weight load 300.64 s
+ DSpark draft 66.81 s on the head (187.94 + 46.20 s on a worker), `max_total_num_tokens=9,273,856`
(−1.2 % vs the V4.1 base), vision **3/3** solid-colour probes plus a clean text control.

The **2026-10-22 live boot** (owner's verbatim command, no flags, scheduler-placed on `.30`–`.33`, task
`sparkrun_a2e141223b52793c_d7960e70d961`, TTR 544 s, `max_model_len` 1,048,576 unclamped, KV
6,849,792): **C1 60.20 / C2 85.13 / C5 114.87 / C10 116.86** t/s (n=5, `--skip-run`, decode rows
only), house **37/37** (easy 19/19, hard 18/18, `--max-tokens 4096`, thinking on, 30.9 s),
needle **5/5 at ~999k** prompt tokens (998,446 / 997,583 / 999,044 / 999,281 / 999,241; 592.8 /
626.2 / 550.1 / 567.9 / 543.9 s, serial c1, depths 10–50 %; **depths 60–100 were not attempted**).
Every cell carried the fleet's own traffic — the same four ranks were answering the agent fleet while
the legs ran — so the C1 deficit against 69.28 is `LIKELY` self-inflicted contention and
`SPECULATIVE` as a cause; 69.28 is not a like-for-like control in any case (different traffic, and
different node set: `.30` is now a TP rank carrying the control's ssh and syncthing duties). C10 116.86
is at the historical 116.27, so any shortfall is concentrated at low concurrency, which is what a busy
head rank costs first. Receipts `~/benchmarks/knapcio-tp4-20261022/`. JSON completeness was re-checked
because a previous C10 row was non-evidence: `perf-ladder.json`, 21,898 bytes, four records, each with
`pp_throughput`/`tg_throughput` means and five values, `is_context_prefill_phase: false` on every row.

### 7.5 C1 arithmetic — the pool, not a cell

| take | n | mean | receipt |
|:--|--:|--:|:--|
| boot A ladder | 5 | 69.65 | `knapcio-ladder.json` |
| boot A, second bench | 10 | 66.40 | `knapcio-c1-extra.json` |
| γ=5 pair arm (third boot) | 5 | 64.16 | `gamma-p1-g5.json` |
| boot C ladder | 5 | 69.28 | `knapcio-ladder-suiteboot.json` |

Pooled over 25 samples: **67.18 ± 6.97 t/s, CV 10.4 %, range 56.4–87.9**. Against the v2.4 baseline's
**59.21 ± 3.54** (3 runs, one boot) that is **+13.5 % in the means with overlapping intervals**
(60.21–62.75 is the overlap), which narrows the v2.4-vs-1017 C1 question and does **not** close it.
The earlier 1017 boot's **81.0 is 1.98 σ above the pool's mean** — a warm-cache draw (it ran after two
cold 119k/231k prefill probes), not a weight property. Four numbers now coexist and are not
interchangeable: the owner-declared gate figures **69.28 / 116.27** (`TODO.md` settled `#49`), the
pooled reference **67.18**, the v2.4 line's *invalid* C1 cells (§7.3(d)), and the contended **60.20**.

## 8. Stack A — what failed, and why

### 8.1 Expert parallelism above 1 (EP=2, EP=4 + graphs off)

**EP_SIZE=2** loads — it clears the MXFP4 MoE `%128` check — then dies at the first decode plan:
`planned dynamic direct routing is unsupported for this launch shape` (**E192-N1152**). **EP_SIZE=4
with `--cuda-graph-backend-decode disabled --cuda-graph-backend-prefill disabled`** was re-tested
2026-10-22 and died identically (**E96-N2304, M5**), so the failing route plan is prepared **before any
graph capture**: graphs-off does not reach it, and "graphs-off changes it" is false. The launcher line
confirms TP=4 EP=4 with the extras in effect, weights load, and the guard fires at MoE prepare. The
adapter says so itself: "the production profile is EP_SIZE=1". Trial log
`~/benchmarks/knapcio-tp4-20261022/ep4-eager-serve.log`; archived arm
`attic/ds4/deepseek-v4.1-flash-knapcio-tp4-1m-sglang-ep4-eager.yaml` (its `env:` block is what put
`EP_SIZE` into `AB_ENV`). Verified flag spellings on the pinned image's `sglang.launch_server --help`:
EP-on-MoE is `--ep-size N` (there is **no** `--enable-ep-moe`); there is **no** `--enforce-eager`
(vLLM spelling) — the eager equivalent is `--cuda-graph-backend-decode disabled
--cuda-graph-backend-prefill disabled` (aliases `--disable-decode-cuda-graph` /
`--disable-prefill-cuda-graph`, umbrella `--disable-cuda-graph`), choices `{full,breakable,tc_piecewise,disabled}`.
Upstream's own docs corroborate the rejection: `EP_SIZE=4` does not boot with `DSV41_MOE_B12X_NEXT`
(§4 row 2).

### 8.2 DSpark γ=3 does not boot; γ=2 loses

**γ=3 is a proven negative on this image and has no number.** `DSPARK_BLOCK_SIZE` sets only the
requested window; the engine derives `speculative_num_draft_tokens = γ + 1`, while the draft head's
`block_size = 5` comes from the checkpoint. Booted with `-o dspark_block_size=3`, all four ranks log at
15:57:32Z

```
DSpark gamma mismatch: using gamma=3 (from speculative_num_draft_tokens=4) but draft config block_size=5.
Initialized DSpark draft runner … gamma=3, verify_num_draft_tokens=4, query_token_num=3, sample_from_anchor=True
```

then die identically at decode CUDA-graph capture (~8 min in) through
`decode_cuda_graph_runner.py:1044 capture` → `:1217 capture_one_shape` → `:1191 run_once` →
`draft_worker_common.py:151 capture_hook` → `/opt/dsv41/adapter/eager_glue.py:327` →
**`/opt/dsv41/adapter/verify_cap.py:308 compute_confidence_tensor`** → `dspark_planner.py:267` →
`RuntimeError: Sizes of tensors must match except in dimension 2. Expected size 5 but got size 4 for
tensor number 1 in the list.` The shipped `DSV41_VERIFY_CAP=conf:0.1` adapter builds a size-5
confidence tensor against the runner's 4 verify tokens, so only the checkpoint's block size 5 coheres.
**No γ=3 C1 exists and no γ delta can be quoted** — the spread it would have to clear is the §7.5 pool
(67.18 ± 6.97, CV 10.4 %).

**γ=2 was measured on an earlier image (2026-10-10) and loses at moderate concurrency:** C4 −5.3 %,
C8 −2.9 %, C1 tied, +4.5 % at C16. Shipped value stays 5; the fork's γ=3 baseline point remains
unmeasured on this lane. The register's only measured DSpark pair is therefore 2 vs 5, on a different
image, and nothing was re-booted to chase it.

### 8.3 The SPS ragged-verify table crashes the Engram reader

Upstream's README lists it under "Not used". With a fitted `/state/dspark_sps.json` the scheduler
enables and the first mixed batch dies with `AssertionError: engram target-verify expects one equal
block per request, got 84 tokens for 16 requests of 6`. Upstream production is verify-all, so the
shipped recipe sets no table (`DSV41_SPS_TABLE`/`DSPARK_STS_TABLE` are do-not-set). The table needs a
dedicated record boot with `SGLANG_RAGGED_VERIFY_MODE=static SGLANG_DSPARK_ENABLE_SPS_RECORD=1
SGLANG_SIMULATE_ACC_LEN=1.0` and `SKIP_SMOKE=1`, capped to the graph tier (`--max-batch-size 16`).

### 8.4 The radix/prefix cache did not hit (measured 2026-10-06)

Back-to-back requests with identical prompts still logged `#cached-token: 0`, despite
`disable_radix_cache: False` / `radix_eviction_policy: lru`. The DSpark/bounded-replay serving path
does not retain short-prompt prefixes the way stock SGLang's radix cache does — a lane behavior, not a
pool-pin regression. Do not assume prefix-cache reuse when sizing agent/web workloads here, and read
the README's "warm context is near-instant" language with the same caveat. Candidate #2 in §10 is the
measurement that would settle whether this is a real zero-hit path or a mis-read instrument; the 1M
boots measured prefix-cache hits of 0 / 0 / 1.6 / 3.7 / 8.6 % (§9).

### 8.5 Two closed deferrals and two closed negatives

- `DSV41_CACHE_GIB=0` (third-party claim: +9 % KV pool): pool **9,381,376** vs 9,386,240 = −0.05 % — the
  claim does not reproduce. Closed 2026-10-18.
- `SGLANG_RUST_BUILD_MODE=auto`: no hang (532 s) because the Rust image processor is unavailable in
  this image. Closed 2026-10-18.
- `DSV41_CERT_HEAD` / `DSV41_ENGRAM_DRM_NODE` re-test: closed by the same v2.4 boot.
- RoCE coverage sweep + the 1 KB…2 MiB crossover microbench: closed by the same boot.

### 8.6 Traps that make a Stack A number wrong

- **`MEM_FRACTION_STATIC=0.90` wedges GB10 nodes (2026-10-06 incident).** Probing whether a higher
  fraction raised the KV budget (it does not: the ceiling is the 0.80 `full_token`) wedged the head
  `.30` and workers `.31`/`.32` — SSH refused (banner timeout) for >10 min while ping stayed up.
  `.30`/`.32` recovered (`.30` after a reboot); **`.31` went fully unreachable (no ping)** and had not
  returned at session end. On GB10 the GPU pool *is* host memory, so a fraction above ~0.80 can
  exhaust the host and kill userspace; recovery is a reboot (no in-band path: `ipmitool` present but
  no `/dev/ipmi0`, no BMC documented).
- **Greedy text equality is not a prefill-correctness gate.** ~70k-token cold prompts diverge run to
  run (non-associative FP reductions across TP); verify with semantic/needle batteries.
- **`sparkrun run --dry-run` skips InfiniBand detection**, so it prints "No InfiniBand detected" and
  renders no `NCCL_IB_*` env — a false negative.
- **Node identity.** The quartet is `.30`–`.33` (head `.30` = rank 0). sparkrun derives the task id
  from the launch shape, so a relaunch reuses the id: an unchanged id is not evidence of an unchanged
  boot. Name a boot by its receipt directory, never by the id.
- **`sparkrun stop --all` bypasses `--no-rm` and deletes containers**, taking the in-container serve log
  with it; stop by task id after copying `/tmp/sparkrun_serve.log`.
- **The cache-audit leaf is model-keyed.** The knapcio pin's cache leaf classifies live from
  `recipes/ds4/deepseek-v4.1-flash-knapcio-tp4-1m-sglang.yaml`; a re-pin makes the old leaf a leftover
  (`tools/cache-audit.py`, `tests/test_cache_audit.py`).

## 9. Stack A — the 1M prefill-chunk accounting (2026-10-22)

Long-context prefill is **chunk-launch-bound, not hardware-bound**. Measured on the live boot: five
~999k-token requests at **1684 / 1593 / 1816 / 1760 / 1837 t/s** (mean **1738**, 1.67× the per-token
cost of short-context prefill; **1.97×** against the cold 8192-chunk first-chunk median **3428** t/s and
**1.67×** against a cold 2048-token pp of **2897** t/s at C1). Per-chunk throughput decays
**3428 → 1447 t/s** early and then saturates at ~1500 t/s instead of following 1/L; quintiles
3195 / 1684 / 1518 / 1516 / 1484 (first ten 3428, last ten 1447); prefix-cache hits 0 / 0 / 1.6 / 3.7 /
8.6 %.

It is **not expert all-to-all** — at `EP_SIZE=1` all 384 experts are local per rank, so no dispatch
exists — and it is **not compute**: 40 layers × 495 MFLOP/token ≈ **19.8 GFLOP/token** ⇒ ~**0.02 EFLOP**
for 1M tokens, i.e. ~35 TF/s aggregate at 550 s, and **~15 GB/s/rank** of weight traffic against ~273.
What remains is ~**122 eager 8192-token chunk launches** (prefill CUDA graphs are disabled for this
model: `Breakable CUDA graph is incompatible with DeepSeek-V4`, `prefill.backend='disabled'`), each
costing a flat **~4.5 s**. The chunk size is therefore the only lever left:
`-o env.CHUNKED_PREFILL_SIZE=16384` halves the launch count at 1M and does not touch the 16-slot decode
path. **Not run** — it needs a fresh boot and an A/B, which needs the `#4` fence lifted
(`QUESTIONS.md` `#2`). Quote cold first-chunk throughput when it is run, not the TTFT-derived ladder
row. Forensics: `~/benchmarks/knapcio-tp4-20261022/REPORT.md`.

**Ran 2026-10-24 — 16384 wins decisively and ships (`06ca895`).** One boot on `.31`–`.34`
(image `acfc331a`, task `a2e141223b52793c_e2c160f10849`, `-o env.CHUNKED_PREFILL_SIZE=16384`),
five cold ~999k needle requests (serial c1, `chars_per_token` 4.0065): latencies **269.8 / 239.4 /
237.0 / 243.1 / 235.3 s** — mean **245.0 s ⇒ ~4.09k t/s mean prefill, 2.35× the 8192-chunk
control's 1738** — and **needle 5/5 PASS** at ~999k prompt tokens, so accuracy is intact at the
doubled chunk. The mechanism is exactly §9's launch-bound accounting: the chunk count halves
(122 → 61) and the per-chunk rate collapses upward — 16384-token chunks log **mean 4179 t/s
(n=299, median 4159, 2156–5594)** where the 8192 chunks decayed 3428 → ~1500; cold first-chunk
3003 t/s (warm-up chunk, not the metric that moved). `CHUNKED_PREFILL_SIZE` is `AB_ENV`, so the
cell was one `-o` on the shipped line, and the shipped value flipped 8192 → 16384 under the
owner's 2026-10-18 `[#36]` same-window rule (≥ 2 % win, accuracy-neutral flag, boot receipt +
lane record); the guard `test_launcher_v24_serve_line` pins the new value. Receipts
`~/benchmarks/tp4-window-20261024/` (`chunk16k-needle.{log,json}`,
`boot4-chunk16k-rank0-serve.log`).

**Ran 2026-10-25 (window 3) — 32768 loses, 16384 stays.** One boot on `.31`–`.34`
(`-o env.CHUNKED_PREFILL_SIZE=32768`, task `sparkrun_a2e141223b52793c_8428af90136f`), five cold
~999k needles (serial c1): latencies **284.9 / 270.2 / 268.1 / 246.7 / 247.9 s — mean 263.6 s ⇒
~3.79k t/s mean prefill, 7.6 % SLOWER than the 16384 bar's 245.0 s / 4.09k t/s** — needle 5/5
PASS at ~999k, so accuracy is intact but there is no win to buy. Two mechanism notes: (a) the
chunk really was live — 153 `#new-token: 32768` prefill batches in the rank-0 serve log, and
`max_prefill_tokens=16384` did NOT clamp it (the two knobs are independent in this engine); (b)
the bigger chunk is not free capacity-wise — `max_total_num_tokens` collapsed 3,042,304 (16384
boot) → **1,356,288** (−55 %, chunk activation buffers at the same 0.78), so a 32768 line would
also cost three full 1M contexts of pool. Both axes say **16384 is the optimum on this
hardware**: the per-chunk rate had already saturated (~4179 t/s at 16384) and the flat launch
cost §9 attributed the gap to is no longer the binding term. Receipts
`~/benchmarks/tp4-window3-20261024/` (`chunk32k-needle.{log,json}`,
`chunk32k-node{1..4}-serve.log`).

**Ran 2026-10-25 (window 3, owner-directed) — 4096 loses harder; the curve is peaked at 16384.**
Same cell design, `-o env.CHUNKED_PREFILL_SIZE=4096` (task
`sparkrun_a2e141223b52793c_33a0348fab26`): five cold ~999k needles **322.1 /
304.8 / 306.5 / 305.2 / 307.8 s — mean 309.3 s ⇒ ~3.23k t/s, 26 % slower than the shipped 16384**
(and 17 % slower than 32768). Chunk proven live: **1,242 `#new-token: 4096` batches** (~248
chunks per 1M request vs ~61 at 16384), needle 5/5 PASS. The pool moves the mirror-image way, as
predicted: `max_total_num_tokens` **rises** 3,042,304 (16384) → **4,352,000** — a smaller chunk
buys pool capacity that nothing here needs at the cost of prefill speed. Per-chunk rate: ~1.25
s per 4096-token chunk = **3.28k t/s/chunk** vs 4179 at 16384 — the flat per-chunk cost dominates
a smaller denominator exactly as §9's arithmetic says, and 32768 showed the other wall (pool
collapse). **The 16384 optimum is now bracketed from both sides and stays shipped; the chunk
ladder is closed.** Receipts `~/benchmarks/tp4-window3-20261024/` (`chunk4k-needle.{log,json}`,
`chunk4k-node{1..4}-serve.log`).
  *(Owner decision 2026-10-25 (SURVEY #3): the precedent is confirmed as the standing rule for
  chunk-size arms — `mem_fraction_static` stays pinned, the shrunken pool is reported as-is, no
  fraction compensation on any future arm.)*

Related, and the reason the pool is a pin: a 1M prefill at 0.78 leaves the head **5.7 GiB**, at 0.80
only **2.7 GiB** — which is why `mem_fraction_static` stays 0.78 and why a prefill-graph capture pool
(~39 GB at a 16K capture on GB300) is plausibly infeasible here (§10, candidate 7).

## 10. The speedup survey (2026-10-19) — candidates, rejects, and the A/B rules

**Scope.** Upstream SGLang / FlashInfer / DeepGEMM / DeepEP work that touches Blackwell and SM121,
DeepSeek-V4.1-specific PRs and roadmaps, NVFP4/FP8/EXL3 releases of the 1017 base, DSpark/MTP work,
prefix-cache and scheduler features, CUDA 13.x image bases, and published DGX Spark numbers. The knobs
this lane already measured are **out of scope and not repeated**. **No boot was run for the survey.**
Searched 2026-10-19 across SGLang issues/PRs and the V4.1 roadmap, SGLang/FlashInfer release notes,
DeepGEMM/DeepEP PRs, the LMSYS V4.1 and DSpark posts, the cookbook, the knapcio/MiaAI/sparkring stacks,
the 2×-Spark EXL3 repos, HF cards for the 1017 base, and the NVIDIA DGX Spark forum.

### 10.1 The A/B rules these plans obey (the lane's own, from §12.16)

1. One serve at a time; alternate arms **A/B/A/B** — never one boot per arm.
2. `--fresh` on every bench call (a reused bench id re-emits the earlier boot's numbers).
3. Assert `/v1/models` per boot so an arm cannot be mistaken for its sibling.
4. Pre-register the target cell and the falsifier. A delta counts only if the target cell's mean clears
   the control arm's 15-value range **and** the mechanism signal moves (achieved concurrency, accept
   length, `cached_tokens`, ms/step). Otherwise it is a boot slot, not a win.
5. Three boots per arm for anything quoted; two boots per arm only as a screen, extended on a
   near-threshold result.
6. Hold the shipped pool/pin **constant across arms** — a concurrent memory change is a confound.

Scores below are judgment, E×F on 1–5 each. TP=4 items are upgrade candidates because `.30`–`.33` are
fenced by owner policy (`QUESTIONS.md` `#4`); `.34`/`.35` can run P0, candidate 4 and candidate 6.

| # | candidate | layer | target | expected | E×F | nodes |
|--:|:--|:--|:--|:--|--:|:--|
| P0 | GPU clock-latch audit | host | every cell | up to **1.9×** if a node is latched | 25 | `.34`/`.35` now, then all |
| 1 | `--min-free-slots-delay 1` | scheduler | C8/C16, worst TTFT | **+21 %** C8 decode measured on GB10 | 20 | `.30`–`.33` |
| 2 | Prefix-cache truth (`--enable-cache-report`, `lpm`) | cache | long-prefix revisit | 1.5 s vs 89 s re-prefill if hits work | 16 | `.30`–`.33` |
| 3 | Candidate-only indexer scoring (#43401) | decode kernel | 1M decode | **−17 %** step at 1M on 2×GB10 | 10 | `.30`–`.33` |
| 4 | TensorFold v0.6 bump | engine (TP=2) | prefill + C4/C8 | measured 2026-10-21: c8 **+26.5 %**, c16 **+25.7 %**, prefill **+24.6 %/+39.5 %** — ADOPTED | 9 | `.34`/`.35` |
| 5 | TRT-LLM sparse MLA (`--dsv4-attn-backend trtllm`) | attention kernel | C5/C10, 128K | **2.26×** kernel geomean on GB10 | 8 | `.30`–`.33` |
| 6 | `reasoning_effort` high, not max | workload (both) | output tokens | measured 2026-10-21: **10.6 %** paired saving, one task carries it — clears, not headline | 8 | both |
| 7 | Rebuild on newer SGLang + CUDA 13.3 | composite | prefill + decode | per-PR; **+19 %** cold prefill claimed | 6 | `.30`–`.33` |
| 8 | Encoder SWA bounded replay stack | prefix cache | 64K-hit TTFT | 4.6 s → ~1.0 s at 16 hits | 6 | `.30`–`.33` |
| 9 | DSpark compact verify (#42718) | spec decode | C5/C10/C16 | high-batch only; no GB10 number | 4.5 | `.30`–`.33` |
| 10 | 1017 NVFP4 checkpoint (W4A4) | quant | decode + prefill | +8 % C1 decode, −30 % 655K needle (pre-1017 pack) | 4 | `.30`–`.33` |
| 11 | DCP2 decode context parallelism | attention | 1M decode | +3.4 % full model (2×GB10, uncontrolled) | 3 | none upstream |

### 10.2 P0 — is any node's SM clock latched below 1 GHz?

**Mechanism.** A GB10 can come up with its SM clock latched low; the reported case is two of four
Sparks stuck **below 1 GHz**, where a reboot did not clear it and unplugging the node did.
**Source:** tonyd615, NVIDIA forum, 2026-09-10 ("41 with CUDA graphs + DSpark → 77 after un-latching 2
GPUs stuck below 1 GHz"). **Expected:** 41 → 77 tok/s (**1.9×**) only if a node is latched; otherwise
zero. It is a precondition, not a knob: a latched node corrupts every cross-boot comparison.
**Artifact:** none — read `nvidia-smi --query-gpu=clocks.sm,clocks.max.sm --format=csv,noheader` once
per node before a window, and sample `nvidia-smi dmon -s u -d 1` **during** the ladder on each rank.

**Result (2026-10-19) — no latch on the pair; closed negative.** Idle `clocks.sm` reads 208 MHz (normal
idle, not evidence either way); under a 60 s bf16 matmul load both ramp to **2171–2190 MHz** against
`clocks.max.sm` = 3003 MHz, with `clocks_throttle_reasons.active = 0x4` (**SW Power Cap**, no HW
slowdown). That is the pair's documented ~2200 MHz operating point. A first `.35` attempt produced no
kernel load (container cold start outran the timeout) and was discarded rather than read as a latch.
**P0 is closed as a precondition**; the `dmon` sampling stays the rule for any quoted A/B. The
production nodes `.30`–`.33` were read once without extra load while the TP=4 serve was live:
**2184–2190 MHz** with `clocks_throttle_reasons.active = 0x0` on all four, so the serving nodes are not
latched either. (Note the knapcio v2.2 CHANGELOG lists "locked GPU clocks" as tested and not adopted —
that is a *cap*, not a latch, and does not contradict the finding.) Receipt
`~/benchmarks/ds4-p0-clock-20261019/REPORT.md`.

### 10.3 Candidate 1 — single-slot prefill admission (`--min-free-slots-delay 1`)

**Mechanism.** SGLang classifies DSpark as DFlash-family, and at `--max-running-requests >= 8` it
auto-enables an admission delayer that holds new prefills until
`min(4, max(2, (max_running_requests + 5) // 6))` slots are free — **3 at 16** — so a steady arrival
stream sustains ~13–14 of 16, not 16. Passing `--min-free-slots-delay 1` lets a waiting prefill enter
with one slot free (≤1 disables the delay). **Sources:** MiaAI-Lab README (2026-10-19, "Admission at
concurrency 8"), sparkring's SGLang profile (2026-10-19), knapcio v2.4 profile table (2026-10-12).
**Measured elsewhere (GB10):** sparkring 2026-09-17 TP4/EP4 record — C8 decode **85.9 → 104.0 tok/s
(+21 %)**, C8 worst first-token wait **17.0 s → 1.2 s**, reproducing on every later boot with the flag.
**Confound, stated:** that boot also changed `mem_fraction_static` 0.90 → 0.80 and the pool
1,500,000 → 7,000,000, so the pool is entangled with the flag; the scheduler mechanism and the
17 s → 1.2 s wait are not pool effects. Our own ladder says C10 ≈ C5, so the effect should appear at
C16, not C5/C10. **Artifact:** no image change; the flag rides `EXTRA_SGLANG_ARGS`, which the overlay
appends after its own two flags and which is **not** a `RECIPE_ENV` key, so a launch override survives:
`-o env.EXTRA_SGLANG_ARGS='--min-free-slots-delay 1'`. Confirm the effective value in the boot's
`server_args`, not from the recipe. The same flag ships in Mia's TP4 profile and knapcio's v2.4 table;
**our launcher does not pass it** (no `min-free-slots` match in the tree).
**A/B:** control = shipped line; treatment = same launch plus the override; 3 boots/arm, A/B/A/B,
`--fresh`; profile A = `ds4-sglang-depth0-ladder.yaml` (C16 target, C1/C4 regression guard); profile B =
`concurrency-ladder.yaml` (expected flat — if C5/C10 move, the effect is not the delayer); record max
`running-req` at C16 and the worst first-token wait of a 16-request burst. **Falsifier:** the C16 mean
does not clear the control's 15-value range, **or** achieved concurrency stays at ~13–14 in the
treatment arm. A C16 gain without a concurrency rise is a boot slot. *(Third-party receipt, one
observation per cell, pool confound: `LIKELY`.)*

### 10.4 Candidate 2 — prefix-cache truth (`--enable-cache-report`, `lpm`)

**Mechanism.** The radix cache is supposed to reuse compressed KV plus indexer keys on a matching
prefix; the lane measured `#cached-token: 0` on identical back-to-back prompts (§8.4), which is either
a real zero-hit path or a mis-read instrument. Upstream spent a long issue on exactly this symptom: on
v0.5.17 long agentic sessions missed every turn while short requests hit ~98 %, and the resolved causes
were three stacked — a gateway-injected prefix break, a client system-prompt tail that rotates, and a
HiCache `load_back` eviction storm; the source analysis also names an **SWA tombstone veto** on
multi-chunk prefixes and the chunk-front zeroing of the full→SWA mapping. **Sources:** SGLang #35129
(opened 2026-08-17, closed 2026-09-01); MiaAI-Lab `docs/cache-reporting.md` (2026-10-19).
**Expected:** if hits exist, the lane's own v2.4 prize is a 388K-token session revisit in **1.5 s
instead of an 89 s re-prefill** (knapcio CHANGELOG v2.4, 2026-10-12 — that comes from the shipped
prefix-tail budget, not a new knob; it is cited only as the size of a cache hit). If hits are genuinely
zero, the candidate becomes a bug report, not a speedup. **Artifact/flags:** `--enable-cache-report`
(adds `usage.prompt_tokens_details.cached_tokens`; Mia's `boot.py` enables it, ours does not) and
`--schedule-policy lpm` (default `fcfs`); both reach the serve line through `EXTRA_SGLANG_ARGS`, no
image change. **Evidence:** the zero-hit observation is ours; the mechanism is `UNVERIFIED` on this
stack — the HiCache branch does not apply (this lane has no HiCache) and the gateway/client causes are
external, so the surviving hypotheses are the SWA-tombstone/chunk-front path and the measurement
itself. **A/B:** Phase A, same boot, no reboot between probes — one 32K and one 131K prompt 8× back to
back, recording `cached_tokens` and TTFT per repeat (the first is cold by construction; repeats 2–8
must hit if the path works). Phase B, interleaved 2 boots/arm as a screen (extend to 3): `--schedule-policy
lpm` vs `fcfs`, 32K with a shared 16K prefix, cached-token fraction and p50/p90 TTFT. **Falsifier:**
`cached_tokens` 0 on every repeat with reporting enabled ⇒ the path is broken, stop and file it; in
phase B, no change in hit fraction or TTFT ⇒ `lpm` is a null here.

### 10.5 Candidate 3 — score candidate blocks only (upstream #43401)

**Mechanism.** Layer 20 publishes up to 2,048 blocks of 8 compressed positions per decode row; the four
consumer indexer layers select their top-512 **inside** those blocks. Today the paged decode path
materializes a boolean mask over the full graph capacity and every consumer still runs the FP4 indexer
over every tile of the visible context, masking non-candidates out — so consumer cost grows with
context even though at most 16,384 positions can be selected. Scoring only the candidate blocks makes
that cost context-independent. **Sources:** SGLang #43401 (opened 2026-10-09, open); overlapping
implementation #40860 (noted 2026-10-10); roadmap #42170 (2026-10-18). **Expected:** microbench on one
RTX PRO 6000 (SM120), mask + masked scan → candidates: **4.96× at 200K, 1 row** (78.3 → 15.8 µs),
**5.73× at 200K, 4 rows** (230.3 → 40.2 µs), 1.28–1.59× at 1–4K; the saving is per consumer and the mask
was shared, so the per-consumer saving is smaller than the table. The independent 2× GB10 lane
implemented the same idea and measured **81.7 → 67.5 ms/step (−17.4 %)** on a 1,039,999-token retrieval
prompt (25.7 → 32.5 tok/s) with in-place indexer scoring and candidate-only consumer scoring.
**Artifact:** no flag — a patch on `dsv4/fp4_indexer.py` (#43401 or #40860) inside the image's SGLang
tree, i.e. an image rebuild; not in the pinned `f80c91a4b` tree (2026-09-16). **Evidence:** the
end-to-end −17 % is 2× GB10 in a different engine/overlay (`LIKELY`; its own README says the current
runtime has not repeated the 1M test); the PR's microbench is SM120, and #43401's SM120 enablement
depends on #42371. **A/B:** 2 boots/arm interleaved (extend to 3 near threshold), same recipe, `--fresh`;
`concurrency-ladder.yaml` as the short-context regression guard; long-context probe = a 1,039,999-token
synthetic retrieval prompt, greedy, ≥128 output tokens, reporting **ms/step** and the needle result.
**Falsifier:** 1M ms/step does not fall by ≥5 % while the ladder is flat, or the needle stops being
found; a short-context gain contradicts the mechanism (nothing to skip at 1–4K) and is a boot slot.

### 10.6 Candidate 4 — TensorFold v0.6 on the TP=2 pair (measured, ADOPTED)

Detail in §11.3; the survey's own entry: v0.6 rebases `deepseek-v41-tp2` onto upstream `python-0.6`
and adds prompt-path work (mHC post fused into the next sublayer's mixes with rows sharing weight
tiles, row-strided matmul reads, shared expert as one dense GEMM in the grouped kernels' order, FP4
cache writes through the one-launch kernels, Engram rows through `O_DIRECT`; `TF_DS_ROUND_ROWS`,
`TF_DS_IDX_RB`, `TF_DS_IDX_WARPS`, `TF_DS_IDX_TREE`). Source: commit `3825f62` (2026-10-18), plus
`222a9c0` (2026-10-19) for DSML tool-call parsing.

### 10.7 Candidate 5 — TRT-LLM sparse MLA on SM121 (`--dsv4-attn-backend trtllm`)

**Mechanism.** Replaces the FlashMLA sparse-MLA decode with TRT-LLM-GEN sparse MLA. FlashInfer v0.7.1
added DeepSeek-V4.1 dual-cache sparse MLA for SM120/SM121, and v0.7.2 added the SM121 mixed-cache Cake
decode kernel: it reads the two caches **in place** — 528 B/token FP8 SWA main cache (512 E4M3 + 16
UE8M0 group-32 footer scales) and 288 B/token FP4 compressed cache (512 E2M1 dims incl. RoPE; 256 B
payload + 32 B E4M3 group-16 scales) — with BF16 Q, exact on-chip dequantization, BF16 P/V, fp32
softmax/merge. The 288 B cache is never reinterpreted as the 384 B DSv4 NVFP4 layout. **Sources:**
FlashInfer v0.7.1 notes (2026-10-09) and v0.7.2 (2026-10-15); PR #5983 (opened 2026-10-02, closed
2026-10-07); SGLang #41603 (opened 2026-09-29, **merged 2026-10-06**), done on roadmap #42170.
**Expected:** PR #5983's paired, interleaved, CUPTI benchmark against the hand-written SM120 `sparse`
kernel (same card/session, cold L2, graph), 37 representative rows: **GB10 37/37 rows faster, geomean
2.26×, min 1.28×**; RTX PRO 6000 2.46×, RTX 5090 2.48×. That is a kernel measurement. End to end on
GB300, #41603 measured sparse attention **73.5–73.8 → 44.6–45.1 µs** at C64 × 6 verify rows and 128K
context, and serving at C64 (32K in / 1K out, DSpark, Engram offload) **564.6 → 575.4 tok/s (+1.9 %)**
across two repeats. **UNVERIFIED on SM121 end to end.** **Artifact/flags:**
`--dsv4-attn-backend trtllm --cuda-graph-backend-prefill disabled`; needs FlashInfer ≥ 0.7.0.post1 (the
SM121 Cake route needs 0.7.2) **and** the SGLang tree containing #41603. Our image pins FlashInfer
**0.6.18** (`UNVERIFIED` from the image, but the same base reports 0.6.18 in SGLang #39173's environment
block, 2026-09-12), so this is a rebuild. **Compatibility, stated before the plan:** #41603 rejects V4.1
TRT-LLM prefill CUDA graphs **and SWA bounded replay for now**; this lane ships
`--enable-decoder-swa-bounded-replay` by default, worth **1.37× prefill on 4× GB300** in the day-0
blog's paired test (2026-09-10), so the A/B must disable replay in **both** arms — giving up a known
prefill win to test the decode kernel. **A/B:** control = shipped `acfc331a…`; treatment = same tree +
#41603 + FlashInfer 0.7.2 (or newer nightly), both with `--no-enable-decoder-swa-bounded-replay`; 3
boots/arm, `--fresh`, assert the resolved backend in the startup line and `/v1/models`; ladder +
one attention-heavy cell (128K prompt, 6-token verify, C64), report sparse-attention µs if logged, else
ms/step. **Falsifier:** C5/C10 decode does not clear the control's 15-value range, or the replay-off
control already matches the new backend, or a quality miss on the house battery.

### 10.8 Candidate 6 — `reasoning_effort` high instead of max (measured on the TP=2 serve)

Detail in §11.4. Mechanism: on agent loops each turn's reasoning stays in the prompt and is re-read by
later turns, so reasoning cost compounds; capping the default effort reduces output and subsequent
prefill tokens without changing answer quality on the measured set. Source: LibertAIDAI 1017 EXL3 2.9
bpw model card (2026-10-19): on **3,738 jobs** `high` (75, the default) matched `max` (100) on quality at
**0.55–0.8× the cost**, and `low` (50) matched too at **0.4–0.6×**. The lane measured **10.6 %** paired
saving with house 37/37 on both arms (§11.4) — clears the 10 % bar by 0.6 points, carried by one task.

### 10.9 Candidate 7 — rebuild on a newer SGLang tree and CUDA 13.3

**Mechanism.** The image's tree is `dsv4.1 @ f80c91a4b` (2026-09-16). Roadmap #42170 (updated
2026-10-18) lists merged post-09-16 work that removes launches, host syncs or intermediate traffic on
this model: `q_rope_store` folded into `fused_q_norm_rope` (#41657); faster FP4 index-K gather and
`combine_topk_swa_indices` (#41658); prefill indexer raw selection, row-pair schedule IDs and host-sync
removal (#41659); fused c1/c2 compression for eager extend and faster c2 decode (#41660); trimmed
prefill model-entry overhead (#41704); cached MXFP8 dispatch (#42156); reduced eager Engram extend
preparation (#42159); two extra multiply kernels removed from V4.1 attention (#42232); fused indexer
score/ReLU/weighting/head reduction (#42365); request-window copy cuts (#42715/#42921). CUDA 13.2 also
carries two SM121-relevant items: cuBLASLt "up to 3× for NVFP4 and MXFP8 on DGX Spark for large M and
N", and PTX ISA 9.2's direct `cvt.rn.bf16x2.e4m3x2`, which FlashInfer #5983 uses on CUDA ≥ 13.2 and
emulates below it (2026-10-02) — NVIDIA forum recap 2026-03-11, `LIKELY`, not verified on our stack.
**Expected:** not isolatable as one number. The roadmap claims **+19 % cold prefill** from the prefill
CUDA graph (#43440, replaced by #43736) and the decoder-replay fold (#43736, opened 2026-10-12, merged
2026-10-13) measured p50 TTFT −38…−53 % up to C16 on GB300 with throughput +1…+5 % and TPOT flat. The
H20 integration report in #42170 (community comment, 2026-10-13) measured 524K TTFT 323 → 25.5 s and
C64 +189 % for a **whole** backport — do not transfer that. On GB10 decode is launch-bound, so the
small fusions are plausible but `UNVERIFIED`. **Artifact:** a new base + overlay. Best-documented
CUDA-13 nightly in the V4.1 cookbook:
`lmsysorg/sglang:nightly-dev-cu13-20261015-a6a8c560@sha256:0a1ba33aa4e032b8c5bcebdc69c45664074c032074add4f7db01629ec1fcc381`
(cookbook `generatedOn` 2026-10-18). The lane's RoCEnante overlay, b12x/b12x_next and adapter set all
patch engine symbols and **refuse to boot on source drift**, so this is a re-port, not a tag bump
(adapter catalog: knapcio `docs/adapters.md`, read 2026-10-19). **Infeasibility flag:** a prefill graph
needs a capture pool — #43736 reports **~39 GB at a 16K capture** on GB300 and had to lower its static
memory fraction; on a 121.7 GiB GB10 the shipped 1M prefill already leaves 5.7 GiB head, so test the
library fusions first and the graph separately. **A/B (staged, not single-variable):** Stage 1 — new
tree, **no** prefill graph, same adapters/flags, interleaved 3 boots/arm on the concurrency ladder plus
the 4k/32k/131k prefill ladder; falsifier "no prefill gain and no decode gain outside the 15-value
range". Stage 2 (only if stage 1 is green) — `--cuda-graph-backend-prefill breakable` with the replay
fold, after reading the boot's free memory; falsifier: the 1M cold prefill wedges or `MemAvailable`
low-water drops below the shipped 5.7 GiB. CUDA 13.3 base is a separate arm: prefill ladder 4k–262k.

### 10.10 Candidate 8 — encoder SWA bounded replay stack

**Mechanism.** Encoder-side bounded replay removes the window-checkpoint requirement for a prefix hit:
the cache keeps compressed KV and indexer keys and on a hit SGLang recomputes the cached prefix's last
128 tokens to reconstruct window KV. #43166 folds that replay into the extend forward instead of one
eager 128-token forward per hit; #44673 keeps the DSpark draft's SWA in a per-request ring so evicting
it no longer cuts the target's prefix hits. **Sources:** #43166 (opened 2026-10-08, **merged
2026-10-15**), #44673 (**merged 2026-10-16**), roadmap #42170, day-0 blog §4 (2026-09-10) — the blog's
"replay excludes speculative decoding" restriction is superseded by #44673. **Expected:** #44673, GB300
TP4 with DSpark: a prompt whose draft SWA was evicted by 400 other prompts **re-hits 8,448 of 8,565
tokens instead of 0**; GSM8K 98.0 % with and without decoder replay; accept length 3.81 vs 3.78.
#43166: 64K-hit TTFT p50 at 16 concurrent **4,608 → 983 ms** (flag-off control 582 ms), 7K-hit
4,530 → 878 ms. **Cost:** the flag raises decode step p50 at 32 requests **15.3 → 24.1 ms** on that
tree, residual attributed to request-window copies addressed by the still-open #42715/#42921.
**Artifact/flags:** `--enable-encoder-swa-bounded-replay` (opt-in; the lane ships only decoder replay)
plus the #43166/#44673 source and, for the decode-cost fix, #42715/#42921 — image rebuild. **Evidence:**
all numbers GB300; SM121 `UNVERIFIED` (the mechanism does not depend on the GPU, the decode-step cost
might). **A/B:** shipped; shipped + encoder replay; A/B/A/B, 3 boots/arm. Probe 1 — warm a 65,536-token
shared prefix, then send **16 concurrent** requests appending 1,024 new tokens; report p50/max TTFT and
`cached_tokens`. Probe 2 — standard ladder at C16/C10; the flag must not cost more than 5 % on the
target cells. **Falsifier:** hit fraction stays near zero, or the C16 decode step rises by >5 % and the
request-window PRs are not in the image.

### 10.11 Candidate 9 — DSpark compact verify with a profiled SPS table (#42718)

**Mechanism.** DSpark's confidence scheduler turns per-block survival probability into a per-request
verify budget each step; `compact` verifies only the window the scheduler picked, front-packs the batch
ragged, and replays a smaller CUDA-graph tier as budgets trim. On V4.1 the Engram hasher asserted
`num_tokens == bs * draft_token_num` and `token_req_indices` used a uniform `repeat_interleave`, so every
compact tier but the largest aborted at capture (#39173) and the first trimmed request died. #42718
derives the token-to-request mapping with one `searchsorted` over the layout's `qo_indptr` and reuses
Engram's extend kernel. **Sources:** #39173 (2026-09-12, open), #42718 (2026-10-06, open with failing
CI), DSpark blog (2026-07-06) for the schedule. **Expected:** the blog's paired `compact` vs `no-trim`:
**tie at batch 1**, gain opening as concurrency grows and larger on lower-acceptance traffic; no
absolute number transfers. The H20 whole-deployment report in #42170 is not an isolated compact-verify
result. On this lane the target is C5/C10/C16; `UNVERIFIED` on GB10. **Artifact/flags:**
`SGLANG_RAGGED_VERIFY_MODE=compact` plus a profiled `dspark_sps.json`
(`python3 -m sglang.benchmark.dspark_sps_profiler all --base-url …`), and the #42718 (+#42709) source
— image rebuild. The lane deliberately does **not** ship the ragged cost table because it crashes the
Engram path (§8.3); #42718 is the fix that makes it usable, and it is not merged. **Evidence:** the
crash reproduces on 4× GB10 TP4 and 3× GB10 TP3; the fix is tested on RTX PRO 6000 (SM120) and end to
end on 4× RTX PRO 6000, not on GB10. **A/B:** shipped verify-all vs compact with the table; 2 boots/arm
interleaved (3 near threshold); assert the SPS path and `Mean acceptance length` per boot; ladder plus a
C16 cell; log accept length, verify rows/step, ms/step. **Falsifier:** no C10/C16 gain outside the
range, or accept length falls without a step-time fall (trimming lossy, not free); a capture abort or
first-request crash is a hard fail.

### 10.12 Candidate 10 — a 1017 NVFP4 W4A4 checkpoint

**Mechanism.** NVFP4 stores routed experts as E2M1 with one E4M3 scale per 16 values plus an FP32
global scale and a calibrated FP32 `input_scale` per projection, so the expert GEMMs run W4A4 on
Blackwell FP4 tensor cores instead of MXFP4 W4A16. The 1017 MXFP4→NVFP4 transcode keeps the 4-bit codes
bit-exact (NVFP4's 16-element blocks refine MXFP4's 32); only scales change. The 1017 NVFP4 repo is
**399.51 GiB** vs the 475.24 GiB MXFP4 base, because its Engram tables are MXFP4 (97.28 GiB vs
188.83 GiB). **Source:** LibertAIDAI card (2026-10-19). **Expected (measured on the pre-1017 pack, same
SGLang stack):** sparkring 2026-09-17, 4× GB10 TP4/EP4, `nvidia/DeepSeek-V4.1-Flash-NVFP4` (491.1 GiB)
+ `MOE_RUNNER_BACKEND=flashinfer_cutlass` vs stock: decode C1 **34.2 → 36.9 (+7.9 %)**, C4 79.1 → 80.8
(+2.1 %), C8 105.7 → 107.4 (+1.6 %); prefill 16K/64K 3,499/3,391 → **3,697/3,682**; needle 262K
104.8 → **88.9 s**, 655K 386.9 → **268.6 s**; C8 × 262K distinct 776.8 → **694.5 s**. Quality on a
1,440-position panel: top-1 agreement **0.9292** (code 0.992, prose 0.898), truncated top-20 KL mean
0.0293; disagreements sit where stock's own top-1 margin is 0.03 (vs 0.84 overall); same-checkpoint
boot-vs-boot was identical. Note the arm also changed the MoE runner, so the delta is checkpoint+runner.
**Blocker for 1017:** the 1017 NVFP4 pack quantizes Engram to MXFP4, and NVIDIA's card states "the MXFP4
Engram tables are not supported in SGLang yet" (quoted in the LibertAIDAI card) — the working sparkring
variant is the **pre-1017** pack, whose Engram is FP8. An upgrade needs a 1017 NVFP4 pack that keeps
Engram at FP8, which did not exist as of 2026-10-19. The pack also needs `flashinfer_cutlass` (the image
default `flashinfer_mxfp4` fails on the per-expert `input_scale` slice) and a draft overlay for DSpark;
with the draft the reported budget fell to 5,448,448 tokens, a cut versus our shipped pool.
**Artifact:** `model_revision` on a 1017-NVFP4-with-FP8-Engram repo + `MOE_RUNNER_BACKEND=flashinfer_cutlass`
+ the DSpark draft overlay — none of which exists for 1017. **A/B (gated on the checkpoint existing):**
2 boots/arm interleaved, same image, same pool **measured per boot** (the two packs have different
budgets), assert the served snapshot path; ladder + prefill ladder + a 262K needle; quality = house
battery and a 1,440-position top-1/KL panel against the shipped MXFP4 stack. **Falsifier:** top-1
agreement below 0.92, or a house-tier drop >1 item, or no decode gain once the budget difference is
held constant.

### 10.13 Candidate 11 — DCP2 decode context parallelism (blocked upstream)

**Mechanism.** DCP stripes a request's MLA KV across ranks by token position (`owner(p) = p mod c`),
runs attention against the owner-local shard, and merges partial outputs exactly by LSE. Decode reads
~1/c of the cache per rank and adds one packed all-to-all per MLA layer. `--dcp-size N`,
`--dcp-comm-backend {ag_rs,a2a,fi_a2a}`, `--dcp-replicate-q-proj`. **Source:** SGLang DCP docs
(2026-10-19). **Expected:** a custom concurrent DCP2 overlay on 2× GB10 measured component gains of
6–10 % (4-row decode), ~25 % (24-row, representative of C6 verification) and 16–20 % (512-row prefill),
and a full-model **+3.43 % pooled decode / +4.85 % prefill** against a historical run — explicitly "not
a fresh controlled full-model A/B" (coolbho3k `docs/dcp-overlap-performance.md`, 2026-09-18).
**Blocker:** upstream DCP × speculative decoding is allowlisted only for **Kimi Linear + DSpark on
`tokenspeed_mla`/`cutedsl_mla`**; everything else raises. DCP × DSA requires SM100/SM103 with the
`trtllm` DSA backends. V4.1 uses the `dsv4` backend and ships DSpark, so `--dcp-size 2` is unavailable
(DCP roadmap #29736, updated 2026-10-06; doc §"DCP × speculative decoding"). **Artifact:** none usable —
the 2× lane's DCP2 is a bespoke vLLM/EXL3 overlay, not an SGLang flag. **A/B:** not runnable until
upstream supports DCP with `dsv4` + DSpark; if it lands, 3 interleaved boots/arm on the depth-0 ladder
plus a 131K decode probe, falsifier "no long-context decode gain outside the range", with the all-to-all
cost visible at short context as a regression.

### 10.14 Checked and rejected (found in the search, not worth a boot here)

| Item | Why not | Source, date |
|:--|:--|:--|
| Fused TP4 low-latency decode chain (`SGLANG_OPT_DSV41_LOW_LATENCY_DECODE`) | static precondition is **SM100** (B200/B300); not SM121 | SGLang #44933, 2026-10-17 |
| mHC split-K / 160-slice decode mixing | 160 slices are SM120-only (SM121 keeps 80); end-to-end −0.5…+3.5 % on RTX PRO; open PR | #42864, 2026-10-07 |
| Bumping the verify-cap threshold | upstream fit on 6,074 uncut steps: per-position thresholds worth **+0.4 %** over the shipped 0.1; a perfect cut would be +15.5 % | knapcio `docs/adapters.md` |
| More L2-prefetch sub-gates (`AHEAD`, `DRAFT`, `ENGRAM`, `LMHEAD`, `WOB_MB`, `MOE`) | measured flat or slower; only `WOA` is in the line | knapcio CHANGELOG v2.2, 2026-09-25 |
| `--enable-deepseek-v4-fp4-indexer` | four-boot off/on/off/on: identical greedy output, speed and prefill (no-op on V4.1) | knapcio CHANGELOG, 2026-09-24 |
| Locked/capped GPU clocks | tested and not adopted (a cap, not a latch — cf. P0) | knapcio CHANGELOG v2.2, 2026-09-25 |
| 1,024-token prefill chunks at 1M | −31 % prefill and −34 % on a 655K needle vs 4,096 | sparkring record, 2026-09-17 |
| MXFP8 **MoE-input** gathers in prefill SP (`DSV41_PREFILL_SP_FP8_MOE`) | bit-exact but flat on real-text prefill; not in the line | knapcio CHANGELOG v2.2 |
| `--num-continuous-decode-steps 4` | measured null on an 8× RTX PRO PCIe stack (2,741.7 vs ~2,800 tok/s); no GB10 evidence | magik.net benchmark note |
| Pre-1017 NVFP4 as a drop-in for the 1017 base | older weights; and the 1017 NVFP4 Engram is MXFP4, unsupported in SGLang | LibertAIDAI card |
| HiCache / host-tier KV / `OFFLOAD_MODE=ram` | host RAM is GPU RAM on GB10; the lane already records this | `attic/ds4/AGENTS.md` §3.2, §9 |
| EP > 1 / DeepEP | the lane ships EP=1; EP=2 loads but dies at the first decode plan; EP=4 + graphs off dies identically (§8.1) | `attic/ds4/AGENTS.md` §11 |

### 10.15 Unverified leads (plausible, not candidates yet)

- **`--fp4-gemm-backend auto` → `flashinfer_cudnn` on CUDA 13+.** The server-args docs list `auto` as
  choosing cuDNN when CUDA 13+/cuDNN 9.15+ is present, and cuBLASLt/cuDNN claim gains for FP4 on GB10.
  Our MoE is b12x, so the flag may reach only the compressed-KV/indexer FP4 GEMMs. Also conflicts with
  the lane rule "do not override a resolved backend" — confirm the resolved value in the startup log
  first (server args read 2026-10-19).
- **`sgl-deep-gemm` 0.2.0 → 0.2.2.** DeepGEMM's 2026-09-30 release claims improved Lightning Indexer
  kernels for V4.1 (prefill and paged decode) and Sparse Indexer head counts 4–32; no evidence the GB10
  image dispatches those kernels (the lane's indexer path is the chunked backport + b12x). DeepGEMM #462.
- **`DSV41_CACHE_GIB` > 4.** Upstream ships 4 GiB / 16 ways with a 67–76 % row-cache hit rate and says
  the ways are free; no published sweep of a larger cache. It trades KV pool, which is measured and
  pinned, so it needs its own boot pair (knapcio README, 2026-10-12). *(The 4 GiB override with 16 ways
  is separately implicated in the 2026-10-22 prefill slowdown diagnosis — two coldest ranks at 33–58 %
  Engram hit rate with 2.9–4.3 GB NVMe reads per 30k-token prefill; the fix direction is env-only, raise
  the cache, lower `MEM_FRACTION_STATIC` to pay for it.)*
- **`--min-free-slots-delay` > 1.** The "batch admissions" mode is documented but the only measured
  point is 1 vs automatic; no source for a middle value.
- **`--sleep-on-idle`.** Reduces idle CPU from 47 % to 14 % upstream; no measured serving effect. Could
  matter on a 20-core GB10 shared with the GPU, or could add wakeup latency.
- **TensorFold `TF_DS_ROUND_ROWS`, `TF_DS_IDX_RB/WARPS/TREE`.** New v0.6 knobs with no sweep published;
  the defaults are the only measured point.
- **`--stream-interval` > 1.** Docs say a larger value raises throughput by reducing streaming flushes;
  it cannot change a non-streaming ladder. Unverified for streaming clients.
- **`SGLANG_OPT_FP8_WO_A_GEMM`.** The older SM121 lead; the lane instead ships the `DSV41_WO_A_W8`
  twins, and no source compares the two on this tree.

### 10.16 Method and limits of the survey

Limits, stated because they bound how much any of this can be trusted:

- **No boot, no measurement.** Every GB10 number in §10 is someone else's, on a different image,
  checkpoint revision, or peer count unless the text says otherwise.
- **Build distance.** Candidates 3, 5, 7, 8 and 9 need an image built from a tree newer than `f80c91a4b`,
  and the adapters refuse to boot on engine drift. Candidates 4, 10 and 11 need a different image or
  checkpoint entirely. The real cost is the re-port, not the flag.
- **One-variable discipline.** The sparkring delayer record and the NVFP4 record both bundle a memory
  change with the tested change; hold the pool constant wherever the checkpoint permits, and state a
  budget difference instead of hiding it.
- **Node policy.** `.30`–`.33` were fenced (`QUESTIONS.md` `#4`) — *(superseded: the fence lifted
  2026-10-23, `TP4-BGFS Q1`; `.30` is a full cluster member (owner, 2026-10-24) whose controller +
  mgmtd duties are additional, never a fence)*. Nothing in §10 is queued; the TP=4 items
  are upgrade candidates for the next owner-declared window. `.34`/`.35` can run P0, candidate 4
  and candidate 6 today, and nothing else.

## 11. Stack B — the TensorFold EXL3 TP=2 line

Different engine, different quantization, different topology. It is here for the comparison, not as a
variant of Stack A.

### 11.1 Measured cells (all `concurrency-ladder.yaml` unless stated, 5 runs/cell)

| # | arm | body | lever this row changes | C1 | C2 | C5 | C10 | provenance |
|--:|:--|:--|:--|--:|--:|--:|--:|:--|
| 10 | TensorFold TP=2, stock | `LibertAIDAI/…-1017-EXL3-2.9bpw`, 210.72 GB, Engram ~189 GiB on NVMe | the shipped TP=2 line; DSpark k=5 in-checkpoint drafts; KV grant `reserved 104.00 GiB` | **68.63 ± 3.79** | 48.05 ± 2.46 | 44.56 ± 1.75 | 42.07 ± 3.96 | `~/benchmarks/ds4-tp2-ladder-20261018/tp2-ladder.json`, `bench_2d5f1236b08d` |
| 11 | TensorFold TP=2, stock, depth-0 | same | interleaved A/B arm A, 3 boots, 5 runs/cell (means of the 3 boots) | 66.37 | C4 47.83 | C8 44.80 | C16 48.39 | `…/ds4-1017-ab-interleaved-20261018/ab-A{1,2,3}.json` |
| 12 | TensorFold TP=2, cybersec graft | same body + 682 MB `attn.wo_b` sidecar | the graft (104 tensors, layers 10–35 `attn.wo_b`) | 67.02 ± 3.57 | 52.95 ± 1.67 | 47.75 ± 0.60 | 46.78 ± 0.37 | `~/benchmarks/cybersec-arm5-ladder-20261019/ladder.json` |
| 13 | TensorFold TP=2, graft, Engram **off** | same | `--require-engram` bypassed on the 2026-10-17 boot | 63.7 | — | — | — | REPORT-level citation only; the decode JSON is not in `~/benchmarks/cybersec-arm5-20261017/` |
| 14 | TensorFold TP=2, env-toggle pair | 1017 EXL3 body | `DSV41_CERT_HEAD=1` (C1) vs `DSV41_ENGRAM_DRM_NODE=/dev/dri/card0` (D1) — two keys the TensorFold engine does **not** reference | 66.29 ± 5.41 / 66.63 ± 2.14 | C4 49.32 / 44.20 | C8 48.65 / 44.01 | C16 44.11 / 45.72 | `…/ds4-1017-envtoggles-20261018/{C1,D1}.json`; `C1.env-proof.txt`/`D1.env-proof.txt` show `engine_files_referencing_DSV41= []` |
| 15 | TensorFold TP=2, 1017 trial, 2026-10-17 | 1017 EXL3 body, Engram under `<snapshot>/engram` | first 1017 boot on this arm (3 runs/cell) | 61.53 ± 2.40 | C4 48.87 ± 0.70 | C8 49.31 ± 0.46 | C16 48.22 ± 0.09 | `~/benchmarks/ds4-1017-20261017/ladder.json` |

Row 14 is the **control**: two boots of the same body and engine, each carrying an env key the engine
never reads, land at 66.3 and 66.6 t/s C1 — a 0.5 % gap, the tightest same-config pair in the family,
agreeing with rows 10 and 11 (68.6, 66.4).

Two levers the ds4 README lists are **not** knobs on this family and appear in no row: a
`mamba_full_memory_ratio` (V4.1 is MLA + sliding-window attention, not a GDN body — that knob is the
qwen3.8 lane's), and a KV-dtype sweep (both 1017 recipes declare `kv_dtype: fp8` and no receipt differs
it).

### 11.2 Why the pair never batches

Aggregate ÷ per-request throughput — the effective number of streams the engine decodes at once — is
**1.00 / 0.92 / 1.26 / 1.19** across the pair's C1/C2/C5/C10 cells, against **1.00 / 1.83 / 3.88 /
6.74** on the quartet (`tg_req_throughput` in the same receipt JSONs). So the pair's C5 and C10 cells
measure **queueing**, not capacity, and most of the "2.5–2.75× for 2× the nodes" is the pair
contributing no batching. The pair's launcher passes `--parallel 4`
(`mods/tensorfold-dsv41-launcher/launcher.py:406`) and its boot line prints `--parallel 4: 4 streams
share one window of 1048576 tokens (an extent each)`; whether the 4-slot config *causes* the ~1.2
effective streams is `[INFERENCE]` — no receipt logs the engine's admitted-request count.

### 11.3 The v0.6 engine bump — measured 2026-10-21, ADOPTED

Control `fabbe861…` (engine `tensorfold 0.6.3`, built 2026-10-05 from `d5d7bb3`), treatment
`d6e4c10d…` (engine `0.6.6` at `3825f62`). Six interleaved boots (A/B/A/B/A/B), depth-0 ladder at 3
runs/cell, `--fresh`, `/v1/models` and the container's own `tensorfold --version` asserted per boot.
Receipt `~/benchmarks/ds4-v06-ab-20261021/REPORT.md`.

| cell | 0.6.3 (n=9) | 0.6.6 (n=9) | Δ |
|:--|--:|--:|--:|
| c1 | 64.70 (57.02–74.71) | 64.47 (60.26–70.05) | −0.4 % |
| c4 | 46.13 (42.68–48.14) | 51.15 (46.91–53.46) | +10.9 % |
| c8 | 41.47 (37.36–47.83) | 52.45 (50.43–53.24) | **+26.5 %** |
| c16 | 42.33 (33.75–46.78) | 53.21 (52.66–53.59) | **+25.7 %** |
| prefill 32k | 1,667 t/s (1,550–1,745) | 2,077 (1,848–2,255) | **+24.6 %** |
| prefill 131k | 1,486 (1,418–1,535) | 2,073 (2,032–2,098) | **+39.5 %** |

The falsifier is **not** met: the treatment's worst single run beats the control's best at c8
(50.43 > 47.83) and c16 (52.66 > 46.78), and at both prefill sizes. c4 and c1 overlap — quote c4 only as
a mean effect (+10.9 %) and c1 as flat. The first v0.6 start costs 264 s JIT-building three CUDA
extensions; later boots launch in 80.3–80.9 s, inside the control's 80.1–81.5 s, so the win carries no
launch-time penalty. The v0.6 indexer knobs remain engine defaults (no sweep run). Artifact:
`ARG TENSORFOLD_REF=3825f62022f25e3e5cf01fa5ea708d4a93b0a9e3` in
`recipes/ds4/Dockerfile.tensorfold-dsv41`; the shipped recipe pins `d6e4c10d…`. Build log and digest
`~/benchmarks/ds4-v06-build-20261021/`.

### 11.4 `reasoning_effort: high` — measured 2026-10-21 on this serve

Same ten tasks to both arms, two rounds, arm order flipped per round (40 requests), paired per task:
`max` 47.5 reasoning tokens mean vs `high` 37.1 → **10.6 % paired saving**; completion tokens 51.7 →
41.4; no length cuts; house battery **37/37 on both** arms (baseline 36/37); no task flipped
pass→fail. The saving is **not uniform**: `hard-rev` 128 → 43 supplies most of it (+66 %), then
`hard-json` +12.5 %, `hard-upper` +11.9 %, `trick-2` +11.3 %; `hard-arith-2` is slightly negative.
Without `hard-rev` the mean paired saving is ~6–7 %. **Verdict against the pre-registered bar: PASS, but
it clears 10 % by 0.6 points and is carried by one task — do not quote it as a headline saving.**
Receipt `~/benchmarks/ds4-v06-ab-20261021/reasoning-effort/reasoning-effort-ab.json`. The mapping is
carried by the lane's own chat template (`mods/tensorfold-dsv41-launcher/chat_template.jinja`:
low/medium/high/max → 50/62/75/100), and this run proves it is wired on that serve (identical reasoning
counts across arms would have meant INERT). Request-level `reasoning_effort` and the served alias/cookbook
default are the artifact; the SGLang V4.1 cookbook lists `SGLANG_DSV41_REASONING_EFFORT` in its env block
and says the parser maps the values; thinking is off by default on this model.

## 12. TP=2 vs TP=4 — what the data supports

Ratios use the TensorFold pair (row 10) against the v2.3 line's two-boot means (rows 1–2 of §7.1:
89.1 / 111.1 / 115.8 t/s for C2/C5/C10) and the pooled C1 (§7.5).

| cell | TP=2 pair | TP=4 quartet | TP=2 as a fraction of TP=4 | TP=4 ÷ TP=2 aggregate | per node: pair (÷2) | per node: quartet (÷4) |
|:--|--:|--:|--:|--:|--:|--:|
| C1 | 68.63 | 67.18 (pooled) | **102 %** | 0.98× | 34.3 | 16.8 |
| C2 | 48.05 | 89.1 | **54 %** | 1.85× | 24.0 | 22.3 |
| C5 | 44.56 | 111.1 | **40 %** | 2.49× | 22.3 | 27.8 |
| C10 | 42.07 | 115.8 | **36 %** | 2.75× | 21.0 | 28.9 |

The graft arm (row 12) sits slightly higher — 52.95 / 47.75 / 46.78, i.e. 59 % / 43 % / 40 % of the
quartet — so the pair's band is 54–59 % at C2 and 36–43 % at C5/C10. Against the **shipped** v2.4 line
(§7.3 interval off), which beats the v2.3 line by 18.7 % at C5, the pair is 33.8 % at C5 and 34.1 % at
C10.

1. **Aggregate decode does not scale with node count at C1, scales below the node ratio at C2, and
   above it from C5.** Doubling nodes buys 0.98× at C1, 1.85× at C2, 2.49× at C5, 2.75× at C10. The
   reason is measurable and it is not tensor parallelism: the pair never batches (§11.2).
2. **The quartet stops scaling at C5; the pair at C2.** On the quartet, C10 is flat against C5 on both
   v2.3 boots (+1.7 %, +6.9 %) and *below* C5 by 6.3 % on the shipped v2.4 line; the depth-0 shape is
   likewise flat from C4 to C16 (118.9 / 107.5 / 115.9). Its sustained ceiling is ~115–120 t/s with
   **131.83 as the best cell ever measured**. The pair's aggregate is already below its C1 by C2 and
   settles at ~42–48 t/s from C5. Per node the pair is **2.04× the quartet at C1** and still ahead at C2
   (1.07–1.19×), then behind from C5 (0.79–0.86×) and C10 (0.73–0.81×): the crossover sits between C2
   and C5, at the concurrency where the quartet starts batching.
3. **Memory and headroom.**

| | test pair (2 × 128 GB) | production quartet (4 × 128 GB) |
|:--|:--|:--|
| weights per node | **105.36 GB** (EXL3 210.72 GB ÷ 2) = 82 % of one node | **76.89 GB** ((510.31 − 202.76) ÷ 4) = 60 % of one node |
| Engram | ~189 GiB per node, **on NVMe**, streamed (`--require-engram` fails a miss) | packed per rank on NVMe (2 × 23.6 GiB/rank, 57–73 s first boot) |
| KV | engine grants `reserved 104.00 GiB` plus a shared 1,048,576-token window (a grant, not an occupancy) | pool **9,277,952** tokens at 1670.75 B/token ≈ **15.5 GB per rank** — `num_key_value_heads: 1`, so KV cannot shard |
| context served | 1,048,576 (the pool *is* the window; four streams share it) | 1,048,576, page-shared, up to 16 slots |
| node cost | 2 nodes | 4 nodes |

So the pair converts **1.37× the weight bytes per node** into **1.02× the C1 rate for half the nodes**,
and pays with no multi-stream capacity. The quartet has ~36 GB of headroom per node after weights and KV
(128 − 76.89 − 15.50); the pair has ~22 GB after weights alone, before any KV.

4. **Two receipts that look like TP=4 wins and are not.** The depth-0 C1 80.97 (§7.4) is 1.98 σ above the
   pooled 67.18 and was taken after two cold 119k/231k prefill probes warmed the Engram and L2 caches —
   a draw, not an arm. The v2.4 C1 cells (§7.3(d)) are cold-contaminated the other way. The pooled 67.18
   stands.

## 13. The TP=1 byte wall

One node is **128 GB of unified memory**. Two anchors say what fits in practice: the TP=2 arm boots with
**105.36 GB of weights per rank** (`210,721,837,240 B ÷ 2`, from the checkpoint's own
`model.safetensors.index.json`) plus the vision tower at 0.90 GiB, and reserves a 104.00 GiB KV grant on
a 128 GB node; and the KV pool costs **1670.75 B per token**, so a 1,048,576-token window is **1.75 GB**
— it does not decide fit at any plausible quant.

So a working ceiling for a TP=1 body is **~105 GB** (what a 128 GB node has booted with) and the hard
ceiling is **128 GB**. The body has **552B parameters**; the Hub's own safetensors metadata for
`deepseek-ai/DeepSeek-V4.1-Flash-1017` totals **763,205,315,794** parameters — the 552B body plus the
196.6B Engram (2 × 384M rows × 256) plus MTP and vision. Bytes per body parameter = on-disk ÷ 552e9, so
the bpw that fits is:

```
105 GB  →  105e9 × 8 / 552e9 = 1.52 bpw
128 GB  →  128e9 × 8 / 552e9 = 1.85 bpw   (weights alone, no KV, no workspace, no host)
```

| body | on-disk bytes (source) | body bpw | ÷ 128 GB node | verdict |
|:--|--:|--:|--:|:--|
| official 1017 MXFP4/F8 | **510.31 GB** total; **202.76 GB** is the two FP8 Engram tables, so body = **307.53 GB** | 4.46 | 2.40× | 4 nodes (shipped, TP=4) |
| `LibertAIDAI/…-1017-EXL3-2.9bpw` | **210,721,837,240 B** = 210.72 GB (`index.json` `total_size`; Hub sum agrees at 210.82 GB); ships **no** Engram | 3.05 | 1.65× | 2 nodes (shipped, TP=2) |
| `LibertAIDAI/…-1017-NVFP4` | **429.01 GB** total, Engram MXFP4 97.28 GiB → body ≈ 324.60 GB | 4.70 | 2.54× | does not fit any topology the lane runs (Engram unsupported in SGLang) |
| `0xSero/…-1017-EXL3-2.7bpw` | **198.60 GB** | 2.88 | 1.55× | no TP=2 receipt |
| `kaushikvira/…-1017-GSQ-agentic-strata` | body GGUF **174.36 GB** + Engram 188.8 GiB | 2.53 | 1.36× | research only; no shipped engine opens the strata format (§15.2) |
| `lxe/…-1017-dsx-2bit` | **148.09 GB** body (37.26 + 37.17 + 37.05 + 36.61) + 0.97 GB vision; the card requires the official 203 GB Engram beside it | 2.15 | 1.16× | smallest 1017 body in a real runtime format; still 1.16× the whole node |
| `unsloth/…-1017-GGUF` UD-IQ1_S | **122.38 GB** body, computed two ways: the repo's 232.98 GB tier minus its 110.595 GB Engram file, and the `lxe` card's "~122 GB without Engram" | 1.77 | **0.96×** | the smallest 1017 body published anywhere — and it still does not fit: 122.38 GB is 95.6 % of the node's *total* memory before KV, activations or a host, and 1.17× the 105 GB a node has actually booted with |

**Verdict: no 1017-class body fits TP=1, at any quantization the lanes record or the Hub publishes.**
552B parameters at the ~3.05 bpw effective the TP=2 arm's 2.9 bpw pack measures is 210.72 GB, 1.65× a
whole node; the best published compression (UD-IQ1_S, 1.77 bpw) still needs 122.38 GB; and the smallest
148 GB body needs a runtime that streams from host RAM the way `dsx` does on a 48 GB + 128 GB box —
memory a Spark does not have spare, because its 128 GB *is* both. A TP=1 safetensors recipe would also
have to hold the Engram, which no single-node path in this registry does (both shipped arms stream it
from NVMe); a GGUF route would have to hold it too — Unsloth's IQ4_NL Engram file is 110.595 GB alone,
and the MXFP8 one is 202.76 GB.

Two consequences worth writing down:

- **The family's smallest reachable topology is TP=2, and it is not close to TP=1.** The gap is not a
  rounding error to be closed by a flag: it is 1.17–1.65× the node on the smallest bodies that exist,
  against a 1.52 bpw target that nothing publishes.
- **Even if a body fit, quality would not survive.** The 1.77 bpw body's own publisher-measured cost is
  KL 0.373, top-1 74.4 %, perplexity 10.68 against the FP8 original's 8.56 (`lxe` card, measured on the
  Lucebox 1017 eval set). The registry's own bar for this family is EXL3 2.9 bpw at **parity with
  official weights** — house 36/37 both, hard tier 17/18 both, no benchmark separating them across 11
  benches and ~1,900 paired items (`recipes/ds4/benchmarks/`). A 1.5 bpw 1017 arm would be a different
  product, not a smaller one.

**What would have to happen next** (each gate named; no TP=1 recipe is authorable today — a recipe that
cannot boot is not a plan):

1. **A TP=1 body at ≤1.5 bpw effective (≤105 GB) does not exist.** Producing one means quantizing the 552B
   body ~14 % below the smallest published body (122.38 GB at 1.77 bpw), and the EXL3 recipe this lane
   runs (mul1, K=3/K=4 trellis on the routed experts) was tuned for 2.7–3.5 bpw, so a sub-1.5 bpw EXL3
   export is unproven, not merely unpublished. Gate: a published repo whose body measures under 105 GB,
   plus a card-measured quality point at or near the parity bar above.
2. **An engine that loads such a body on GB10.** Three routes, each gated: **llama.cpp** — the pinned
   runtime tier's engine is `0.1.2-dev (build 1, commit b2e5e9b)` and its arch map lists `deepseek4` but
   not this family's arch (`mad-science/LLAMACPP-GGUF.md` §2); Unsloth's card says to use *their*
   llama.cpp PR; gate = a boot of an IQ1_S-class 1017 GGUF on the pinned image, which also has to hold
   the Engram in the same 128 GB pool. **`dsx`** (the 148 GB body's runtime) — a Rust + CUDA engine,
   GPU + host-RAM split at 48 GB + 128 GB; a Spark has no second memory tier to spill into; gate = a
   demonstrated GB10 build, which does not exist. **TensorFold/SGLang with a re-quantized body** — they
   already stream Engram from NVMe, so only the body must fit; gate = a body under 105 GB that the
   engine's `family.check()` admits (it refuses a non-`exl3` `quant_method` on this arm).
3. **A TP=2 re-measure before any TP=1 work is justified.** The pair's effective concurrency never
   exceeds ~1.4, the cheapest open lever in the family: one boot with a larger `--parallel` and a logged
   admitted-request count would say whether the 42–48 t/s plateau is a config cap (the pair is
   under-measured) or the engine's ceiling (TP=2's single-user tag is a hardware statement). Cost: one
   test-pair boot; nothing on the quartet, so production is not disturbed.
4. **An interleaved TP=2-vs-TP=4 comparison on one engine.** No such receipt exists; §12 compares two
   stacks. The honest version is one engine, one quant, two topologies, A/B/A/B boot slots — which needs
   the quartet's owner-scheduled window and a TP=2 body the quartet can also serve (EXL3 2.9 bpw at
   105.36 GB/node, or the official base at 76.89 GB/node). Tracked as `QUESTIONS.md` `#3` (the `#4`
   fence it was queued behind lifted 2026-10-23).

## 14. Open work and open unknowns

Work items live in `TODO.md` §ds4 and stay there; this section is the index, not a second queue.

| open item | gate | detail lives in |
|:--|:--|:--|
| Run the TP=4 arms of the survey (§10 candidates 1, 2, 3, 5, 7, 8, 9, 10, 11) | owner-declared window (`QUESTIONS.md` `#4` lifted 2026-10-23) | §10 |
| Larger 1M prefill chunk (`CHUNKED_PREFILL_SIZE=16384`) | same window; own question `#2` | §9 |
| b12x quartet acceptance boot | **closed 2026-10-23** — `QUESTIONS.md` `#9` | §6.1, §18.1 |
| Make the image byte-reproducible | deterministic build step (bytecode off, `SOURCE_DATE_EPOCH`) | §5 |
| Interleaved C1 re-take on the shipped line | needs the quartet; **dropped, not deferred**, by the 2026-10-18 19:15 policy | §7.5 |
| One-engine TP=2 vs TP=4 A/B | `QUESTIONS.md` `#3`, queued | §13 item 4 |
| TP=2 `--parallel` / admitted-request re-measure | `.34`/`.35` (runnable today) | §11.2, §13 item 3 |
| vLLM parity acceptance boot | owner-declared window; needs the third-party image authorization (`QUESTIONS.md` `#17`) | §17 |
| `DSV41_TP_PAD=0` A/B boot | **closed 2026-10-23: falsified** — the split was already ON and the treatment never booted; do not ship the line | §18.1 |
| RDMA registration wedge (`ibv_reg_mr_iova2` ENOMEM at `ncclCommInitRank`) | **owner approval to reboot `.30`** (`QUESTIONS.md` `#18`); other nodes at discretion | §18.1 |
| KV pool regression / inert 6.85M pin | one boot's `max_total_num_tokens` plus a `DSV41_FAST_LOAD` A/B | §18.1 |

**Open unknowns.**

- Is the pair's ~1.2 effective concurrency a `--parallel 4` cap? The launcher hardcodes it
  (`launcher.py:406`) and no receipt logs an admitted-request count — `[INFERENCE]` until a boot logs it.
- `bench_44534d5024c0` (arm 5, Engram-off, C1 63.7) is cited by that receipt's `REPORT.md`, but its
  decode JSON is not in `~/benchmarks/cybersec-arm5-20261017/`.
- The TP=2 C2/C5/C10 row and the TP=2 depth-0 row come from **different node pairs**: row 10 ran on the
  production quartet's first two nodes (cold boot, `CUDA extensions built from scratch`, TTR 516.5 s),
  rows 11–15 on the test pair. The lane's documented boot-slot spread is 7–25 %, so pooling them into one
  "TP=2 ladder" would be wrong and this note does not do it.
- Whether the pair's engine batches above 4 streams at all: untested. C16 on the pair (48.39) is *higher*
  than its C8 (44.80), which is not the shape a hard 4-slot cap predicts — but C8 instability is
  documented for both arms, so that inversion is a boot slot, not a signal.
- The quartet's C1 has no interleaved v2.4-vs-1017 A/B. The 67.18 pool is four takes on the v2.3 line;
  the +13.5 % against 59.21 has overlapping intervals.
- `unsloth/…-UD-IQ1_S` body bytes are a subtraction, not a file census: 232.98 GB repo sum minus the
  110.595 GB Engram file assumes shard 5 *is* the Engram, which the identical byte count supports but
  does not prove; the `lxe` card's "~122 GB" is the independent second reading, and no GGUF header was
  read.
- The 1017 NVFP4 pack has no published FP8-Engram variant, so the W4A4 route's +7.9 % cannot be tested on
  the 1017 weights (§10.12).
- `ds4-knapcio-1017-20261018/arm-1017` also carries `chat.json`, which is the vision/contract probe,
  not a ladder; it was excluded from the tables by shape, not by distrust.

## 15. Other artifacts for this model

### 15.1 FLARE — its own document

`mad-science/FLARE.md` carries the FLARE `gb10` package and its install decision (2026-10-23): a
publisher-signed *runtime package* targeting four DGX Sparks at TP4/c16, a 1,048,576-token per-request
context and disk-backed Engram; no shipped engine reads it ("Transformers, vLLM, SGLang and llama.cpp
cannot load this runtime format"), so `flare-inference` from a third-party APT repo plus `flare orbit`
RoCE pairing is the only route. The install is an owner supply-chain authorization
(`QUESTIONS.md` `#6`, open, narrowed to `.34`/`.35`), the TP4 cell also needs the `#4` fence lifted, and
nothing verifies the package on arm64 + CUDA 13. **Not repeated here**; read `FLARE.md`.

### 15.2 The GSQ strata export — full fact block, kept

`kaushikvira/DeepSeek-V4.1-Flash-1017-GSQ-agentic-strata`, a **382.8 GB** "GSQ" mixed-precision export of
the 1017 body in a *strata*-format GGUF that no engine this lane ships can open. **Research only, not
queued for a boot.**

Facts: open (`gated: false`), card `license: mit`, one branch `main` @ `7aa29158…`, Hub `usedStorage`
**382,778,487,408 B = 382.78 GB / 356.5 GiB**: `V41-GSQ-1017.gguf.part-00` 96,636,764,160 +
`.part-01` 77,722,075,136 (one **174.36 GB / 162.4 GiB** GGUF, `cat`-recombined; the card's "153 GiB"
budget and "90 GiB + 73 GiB" parts describe a build that is not what shipped),
`V41-MTP-Vision-1017.Q2_K.gguf` 5,661,492,320, `engram-layers.{1,14}/engram-L{1,14}.safetensors`
101,377,628,584 + 101,380,404,328 (**188.8 GiB** of Engram, the same L1/L14 tables the lane already
stages per node), `V41-GSQ-1017.gguf.experts.json` 1,226,894, `rank.bin` 122,880, `tokenizer/` 5.8 MB.
**Weights, not an overlay** — unlike the `drowzeys/…` overlays (no weights; 683 MB + 1.09 GB sidecars
grafted by a mod), this repo ships the whole quantized body plus its own Engram tables. `config.json` is
only the base declaration: `quantization_config` = `{"quant_method": "fp8", "activation_scheme":
"dynamic", "weight_block_size": [32, 32], "scale_fmt": "ue8m0", "expert_dtype": "fp4"}` and **no
`kv_cache_scheme` key** (the card's FP4 KV is a serve-time `--kv-fp4` flag). The scheme is in the GGUF
header instead: `deepseek41.quantization` = "routed experts: per-expert Q3_K / Q2_0 / PTQ1_0 (gate+up
share a type, down its own); Q8_0 attention / shared / head; F16 embedding"; `strata.v41.expert_tiers` =
`{"down:PTQ1_0": 4447, "down:Q2_0": 6682, "down:Q3_K": 4231, "gu:PTQ1_0": 5750, "gu:Q2_0": 5113,
"gu:Q3_K": 4497}`; `strata.v41.expert_layout` = "uniform role: ffn_<role>_exps.weight; mixed:
ffn_<role>_exps.<type>.weight per type (experts in id order) + I32 ffn_exps_{gu,down}_type[384]";
`strata.v41.expert_source` = `inplace:rtn:q2_0:268d4652…`; Engram `e4m3_e8m0_32_row264`. Those tier
counts are exactly the `experts.json` code census over 40 layers × 384 experts × 2 projections
(10,197 / 11,795 / 8,728), so **143 = PTQ1_0 (the card's "ternary"), 42 = Q2_0, 11 = Q3_K**. "GSQ" is
the card's "GSQ (Gumbel-Softmax Quantization) + per-expert mixed-precision tier allocation" (method
credited to antirez); "agentic" is the *calibration* weighting, not a layer mix and not a pruned expert
set — "Every routed-expert projection is assigned its own precision tier (Q3_K / Q2_0 / ternary) from
activation calibration on an agentic + coding corpus" (32 × 8,192-token sequences: agentic_long 10, code
10, agent 5, reasoning 3, web 2, chat 1, multi 1), allocated to a fixed 153 GiB budget; "strata" is the
engine (`library_name: strata`). **Provenance contradicts the card:** the GGUF's own `general.name` is
"DeepSeek V4.1 Flash UNCENSORED (Strata v41 GSQ-RCO mixed tier)" and `general.source.url` is
`dealignai/DeepSeek-V4.1-Flash-UNCENSORED-FP8` (510.3 GB, tags `abliterated`/`uncensored`, its own base
`deepseek-ai/DeepSeek-V4.1-Flash`, not the 1017 refresh), while the card claims `base_model:
deepseek-ai/DeepSeek-V4.1-Flash-1017` and "no abliteration".

Why it matters: weight-only it is the smallest ds4 body measured — weights + sidecar **180.0 GB /
167.7 GiB** vs 510.3 GB (official), 210.8 GB (EXL3 2.9 bpw), 413.4 GB (Engram pack) — and two 128 GB
nodes (238.4 GiB) would hold it resident, but **the loader question is closed, not open**:
`recipes/ds4/README.md:25` (SGLang through `mods/dsv41-sglang-overlay`) and `:349` (TensorFold
`deepseek_v41`, EXL3 mul1) are the only engines this lane ships, neither reads GGUF, and the card says so
outright — "Not runnable on vanilla llama.cpp, Ollama, vLLM, or SGLang without a strata-compatible
loader". Its engine is `strata`/`ds41_generate` from `Indras-Mirror/Xolotl` (public, MIT, a heavily
extended fork of Strata): one host, three tiers (VRAM / pinned RAM / NVMe), Linux-only, reference
machine 24 GB VRAM + 90 GB RAM + NVMe at ~27 tok/s — weaker than one Spark, which is why size does not
rule a single node out; the engine has no arm64/GB10 build and no multi-node path.

Blockers/unknowns: nothing to boot on — a strata port is a new engine family, not a recipe re-point;
arm64 + CUDA 13 support unknown; the card's quality gate is unfinished ("Full evaluation is coming"; 21
HumanEval + 10 tool calls only); the shipped 174.36 GB GGUF does not match the card's 153 GiB
arithmetic; the abliteration-provenance mismatch must be settled before the id is quoted as an
official-weights variant; `tokenizer.ggml.pre` is `joyai-llm` and `tokenizer/chat_template.jinja` is a
91-byte stub pointing at `serve_ds41.py`, so a loader port inherits the lane's template-less problem.
All sizes are Hub `usedStorage`/`tree` bytes; no node cache was read.

### 15.3 Artifacts (cite, never absorb)

- `recipes/ds4/README.md` — the user-facing lane doc and the authoritative measured cells; its
  §Upgrade candidates is the pointer to §10, and its `## Measured` sections are the lane's own record.
- `recipes/ds4/deepseek-v4.1-flash-knapcio-tp4-1m-sglang.yaml`, `Dockerfile.knapcio-dsv41`,
  `boot.py.health-port.patch`, `mods/dsv41-sglang-overlay/*` — shipped recipe, image reference and mod.
- `attic/ds4/AGENTS.md` §5/§5.1 (image and boot receipt), §7.13 (lane launch), §11 (negative results),
  §12.16–§12.19 (the receipts this note restates), `attic/ds4/ds4_NOTES.md` (session log);
  `attic/DONE.md` (closed items); `attic/qwen4/SELECTION-RANKING.md` (the arm comparison).
- `benchmarking/concurrency-ladder.yaml`, `benchmarking/ds4-sglang-depth0-ladder.yaml`,
  `benchmarking/standard-suite.yaml` — the profiles.
- `tools/eval-suite.py`, `tools/needle-haystack.py`, `tools/cache-audit.py`,
  `tools/build-dsv41-engram.py`; `tests/test_ds4_recipes.py`,
  `tests/test_ds4_knapcio_template_overlay.py`, `tests/test_cache_audit.py`.

## 16. Receipts index

| window | what | path on the head |
|---|---|---|
| 2026-10-14 | pin served (`5254448103b6…`), C1 triage, battery | `.scratch/ds4/knapcio-tp4-boot-20261014/` (local, git-excluded) |
| 2026-10-17 | v2.4 image build + TP=4 boot | `~/benchmarks/ds4-knapcio-v24-20261017/` |
| 2026-10-17 | TP=2 1017 trial | `~/benchmarks/ds4-1017-20261017/` |
| 2026-10-18 | v2.3 ladder, suite, γ pair | `~/benchmarks/tp4-20261018/` (task `a2e141223b52793c_7afff0589a33`) |
| 2026-10-18 | 1017 arm depth-0 + boot | `~/benchmarks/ds4-knapcio-1017-20261018/` (`bench_147c4e4cadab`) |
| 2026-10-18 | v2.4 line, three boots | `~/benchmarks/ds4-v24-line-20261018/` |
| 2026-10-18 | TP=2 ladder + interleaved A/B | `~/benchmarks/ds4-tp2-ladder-20261018/`, `~/benchmarks/ds4-1017-ab-interleaved-20261018/` |
| 2026-10-18 | TP=2 env toggles | `~/benchmarks/ds4-1017-envtoggles-20261018/` |
| 2026-10-19 | P0 clock audit (pair + quartet) | `~/benchmarks/ds4-p0-clock-20261019/REPORT.md` |
| 2026-10-19 | cybersec arm 5 ladder | `~/benchmarks/cybersec-arm5-ladder-20261019/` |
| 2026-10-21 | TensorFold v0.6 A/B + build + reasoning effort | `~/benchmarks/ds4-v06-ab-20261021/`, `~/benchmarks/ds4-v06-build-20261021/` |
| 2026-10-22 | EP=4 eager trial | `~/benchmarks/knapcio-tp4-20261022/ep4-eager-serve.log` |
| 2026-10-22 | live baseline boot, ladder, house, needle | `~/benchmarks/knapcio-tp4-20261022/` (task `sparkrun_a2e141223b52793c_d7960e70d961`) |
| 2026-10-22 | ARC/GSM8K legs | `~/benchmarks/tp4-20261022/knapcio-arc-gsm8k/` |
| 2026-10-22 | image-reproducibility compare | `~/benchmarks/ds4-expin-20261022/image-compare.txt` |

## 17. A vLLM route to the shipped bar — what exists, what it costs, and the test that settles it (2026-10-23)

**CLOSED NEGATIVE 2026-10-26 (owner: "That's horrible. Cancel it." — the vLLM route for 1017 is
cancelled and retired to `attic/ds4/zz-ds4-1017-b12x-vllm-parity.yaml`, metrics in
`attic/ds4/AGENTS.md`):** the fork's boot reached every boot gate (b12x load, disk-Engram,
RoCEnante, DSpark k=5 engaged, house 37/37, 1M context, needle 32k 10/10) but the ladder read
**C1 34.04 aggregate / 40.4 peak vs the 64.0 bar** — ~half the shipped SGLang C1 (66.14 band);
C10 peak 113.8 clears 110.5 while the aggregate column reads 12.00 with the per-request
identity broken at C≥5 (recorded as an anomaly). Receipts:
`~/benchmarks/tp4-window4-20261026/parity-ladder.{csv,yaml}`. No tuning iterations were run;
the tuning-round and ship-recipe queue tasks were withdrawn with the route.

**Question.** Can a vLLM serve of the same body reach the shipped arm's numbers, and where such a route
exists, which axis decides it? **Parity, stated once and held to below:** the same checkpoint and
revision (`1bae0e1088993b9b82de08f59de5be5a34e42170`), one rank on each of four GB10 nodes at TP=4, a
served window of ≥1,048,576 tokens, **C1 ≥ 64.0 t/s** and **C10 ≥ 110.5 t/s** on
`benchmarking/concurrency-ladder.yaml`, house ≥36/37 at `--max-tokens 4096` thinking-on, and the needle
passing 3/3 at 32,768 / 131,072 / 983,040. The tolerances are the bars' own noise — C1 69.28 ± 5.25
(n=5, 7.6 %) and C10 116.27 ± 6.22 (5.3 %), so one sample sd on C1 and 95 % on C10 are each the smallest
gap a five-run cell can resolve (`recipes/ds4/README.md:59-64`; accuracy cells `:89-93`). A miss on
a speed bar is a **decode-parity** miss; a serve that cannot hold 1M is a **context** miss. They are
independent, and neither substitutes for the other.

**What vLLM can and cannot do here.**

| capability | status | source |
|:--|:--|:--|
| `deepseek_v41` target + `DSparkV41DraftModel` draft | **upstream, no patch**; the architecture shipped in vLLM 0.30.0 and the model recipe's floor is 0.31.0 | `vllm/models/deepseek_v41/` and registry entries (`vllm/model_executor/models/registry.py:383-386,659-662` @ fork `8244d1c4`); `vllm-project/vllm` `recipes/models/deepseek-ai/DeepSeek-V4.1-Flash.yaml:36-41` |
| vendor declaration | **none** — the card documents a Torch reference implementation and the `deepseek-recipe` encoding toolkit, not an engine | card `README.md` §*Minimal Inference*; `inference/README.md` |
| Engram placement, upstream | device or **pinned host RAM** only: `cpu_offload`, `embedding_across_dp`, `dp_shared_memory`, `use_thp`; weight offload (`--offload-backend {auto,prefetch,uva}`, `--cpu-offload-gb`) is also host DRAM | `vllm/config/engram.py` @ upstream `main` `d561af5d` (2026-10-23) |
| Engram placement, b12x fork | **disk**: `table_memory: Literal["device","ram","disk"]` (io_uring staging) plus `disk_resident_scales`, `projection_tp` | `vllm/config/engram.py:76-86`; `vllm/models/deepseek_v4_1/common/engram.py` (`DiskTable`, `prepare_disk`) @ fork `8244d1c4` |
| four-Spark TP=4 serve line | published: `--engram-config '{"cpu_offload":false,"table_memory":"disk"}'`, b12x attention/MoE/linear, k=7 DSpark, `VLLM_ENABLE_ROCE_ALLREDUCE=1` | `eugr/spark-vllm-docker` `recipes/4x-spark-cluster/deepseek-v4.1-flash.yaml:26-56`; fork `scripts/serve-ds41-flash-dspark-tp4-rdma.sh:18-20` |
| GB10-aware decode path | `CUTE_DSL_ARCH=sm_121a`, b12x attention/MoE/linear, and an SM121 L2 weight-prefetch pass | `eugr/spark-vllm-docker` `recipes/4x-spark-cluster/deepseek-v4.1-flash.yaml:26-34,50-52`; `vllm/models/deepseek_v4_1/l2_prefetch.py:3-25` |
| hardware coverage upstream | **no GB10 row** — the matrix is H100/H200/B200/GB200/GB300/B300/MI3xx/`dgx_station_gb300`, and the fit floor is `vram_minimum_gb: 614` | same recipe `:20-35,679-681` |
| image | `eugr/spark-vllm-b12x:latest` is **arm64/linux**, digest `sha256:03a9565…`, pushed 2026-10-15, built from the fork; the registry's own resident b12x pin is `ghcr.io/spark-arena/dgx-vllm-eugr-nightly-b12x@sha256:cf5a2a53…` | Docker Hub tag metadata; `recipes/qwen4/qwen3.8-flash-next-nvfp4-solo-vllm-b12x.yaml:5` |

Two consequences follow. (a) Upstream vLLM's Engram placements *are* the unified pool itself (below), so
only the fork's disk path fits; (b) that fork is a third-party branch with no release wheel, so a vLLM bump
can strand the route — a maintenance cost, not a reachability one.

**The Engram arithmetic at 1M on four Sparks.** At TP=4 every byte is charged per rank, and a Spark's
pool is *unified*: a byte "offloaded" to pinned host RAM is still one of the 121.7 GiB.

| component | cluster total | per rank at TP=4 | source |
|:--|--:|--:|:--|
| checkpoint | 510.29 GB (475.2 GiB) | — | `recipes/ds4/README.md:26`; disk census `:286-293` |
| Engram tables (layers 1, 14) | 202.76 GB (188.8 GiB) | 50.7 GB = **47.2 GiB** | `attic/ds4/AGENTS.md:74-83`; packed shards 2 × 23.6 GiB/rank (§3) |
| everything else (experts, dense, DSpark, vision, head) | 307.53 GB (286.4 GiB) | 76.9 GB = **71.6 GiB** | `attic/ds4/AGENTS.md:158-163` |
| KV at the shipped pool | — | 6,849,792 tok × 1,670.75 B = 11.44 GB = **10.7 GiB** | `attic/ds4/AGENTS.md:241-247`; pool `recipes/ds4/README.md:212` |

With the Engram **resident or host-mapped** (upstream's only options): 71.6 + 47.2 = **118.8 GiB/rank**
against a 121.69 GiB device and, after the ~18 GiB the OS and page cache hold, about **103.7 GiB usable** —
a **~15 GiB deficit at zero KV, zero activation, zero graph memory**. `gpu_memory_utilization` is a promise
against device capacity, so this is a refusal, not a tuning question, and it is the same wall §3.2 records
for SGLang's host-table feature: upstream's targets are 80–288 GiB **per GPU**, not one shared 121.7 GiB.

With `table_memory: "disk"`: 71.6 + 10.7 = **82.3 GiB/rank**, plus activation/graphs (single-digit GiB) and,
with `disk_resident_scales` on, ~5.7 GiB of pinned host RAM for the E8M0 scales (`vllm/config/engram.py:80-82`)
— inside 0.85 × 121.69 = 103.4 GiB and the ~103.7 GiB physical ceiling, but not with much room; the fork's
own TP=4 script defaults to 0.82, 10 GiB of KV/rank and `MAX_MODEL_LEN=500000`
(`scripts/serve-ds4-flash-dspark-tp4-rdma.sh:50-59`). **Context is reachable, not free.**

**Verdict.** *Reachable in principle, unproven in fact — the deciding axis is aggregate decode (C10), not
memory and not 1M context.* The disk-Engram path removes the two reasons to expect this route to die; what
remains is throughput, and the evidence is thin in exactly one place:

- **C1 has one structural number and one supporting number.** The fork's GB10 decode note measures TP=4
  decode at **47.45 ms/step** at a fixed eight-row verifier, down from 49.36 without the L2 prefetch
  (`l2_prefetch.py:12-15`) — 69.28 t/s at an acceptance length of 3.29, and the lane's own prose
  acceptance is ~3 tokens/step (~6 on code, `recipes/ds4/README.md:446-448`). The image project's
  changelog reports **~73 t/s** on SPEED-Bench coding for its 3- and 4-Spark V4.1 recipes
  (`spark-vllm-docker` README §2026-10-05). So C1 sits **on** the bar and can land either side: at the
  retired lane's measured acceptance (2.40–2.64) the same step time yields 50.6–55.6 t/s.
- **C10 has no number at all.** The only same-hardware vLLM-vs-SGLang batch comparison in this repo is
  the retired EXL3 lane — C4/C8/C16 66.3 / 88.5 / 122.0 t/s against SGLang's short-prompt 106 / 133 / 193
  on the same four nodes (`attic/ds4/AGENTS.md:41-45,986-1005`), **63–67 %** at every batch cell. That
  lane used NCCL and vLLM 0.28.1; this route adds `VLLM_ENABLE_ROCE_ALLREDUCE=1` and the b12x kernels,
  which is exactly the pair of levers SGLang's 1.7× came from. It could close the gap; it is not
  evidence that it does.
- The published four-Spark recipe also ships `--max-num-seqs 2`, which **cannot** produce a C10 cell (ten
  clients queue in five batches). A parity attempt must set 16, matching the SGLang arm's slot count.

**If reachable: the serve line, the recipe sketch, and the acceptance test.** The sketch below is a
document, not a shipped recipe (`recipes/` is out of scope for this study). It holds the SGLang arm's
comparison frame — k=5 rather than the vendor recipe's k=7, 16 slots rather than 2, 1M declared rather
than `auto`:

```yaml
runtime: vllm
container: eugr/spark-vllm-b12x@sha256:03a956544e9f9b4b7ba91690469fbe7848bdbef29a7d2e0f5788368467bb3595
model: deepseek-ai/DeepSeek-V4.1-Flash-1017
model_revision: 1bae0e1088993b9b82de08f59de5be5a34e42170
min_nodes: 4
executor_config: { entrypoint: "", shm_size: 32gb, ulimit: [memlock=-1:-1] }
env: { VLLM_ENABLE_ROCE_ALLREDUCE: "1", VLLM_ROCE_ALLREDUCE_MAX_SIZE: "2MB", CUTE_DSL_ARCH: "sm_121a",
       VLLM_USE_V2_MODEL_RUNNER: "1", VLLM_USE_BREAKABLE_CUDAGRAPH: "1", VLLM_MXFP8_LM_HEAD: "1" }
command: >
  vllm serve {model} --revision {model_revision} --served-model-name {model}
  --host 0.0.0.0 --port 8000 --tensor-parallel-size 4 --dtype bfloat16
  --load-format b12x --block-size 256 --kv-cache-dtype fp8
  --gpu-memory-utilization 0.85 --max-model-len 1048576
  --max-num-seqs 16 --max-num-batched-tokens 4096
  --enable-prefix-caching --enable-chunked-prefill
  --engram-config '{"table_memory":"disk","disk_resident_scales":true}'
  --linear-backend b12x --moe-backend b12x --attention-backend b12x
  --speculative-config '{"method":"dspark","num_speculative_tokens":5,"draft_sample_method":"probabilistic","rejection_sample_method":"standard","enable_adaptive_verification":true}'
  --compilation-config '{"cudagraph_mode":"FULL_AND_PIECEWISE","custom_ops":["all"],"cudagraph_capture_sizes":[6,12,18,24,30,36,48,60,72,96]}'
  --tokenizer-mode deepseek_v41 --reasoning-parser deepseek_v41
  --tool-call-parser deepseek_v41 --enable-auto-tool-choice
  --limit-mm-per-prompt '{"image":1}'
```

Two prerequisites the sketch cannot express. **io_uring**: the fork ships `scripts/seccomp/spark-io-uring.json`
for disk Engram (`scripts/seccomp/README.md:8-9`), while this repository's recipes expose only
`entrypoint`/`user`/`shm_size`/`ulimit`/`cap_add`/`restart_policy` under `executor_config`, so a profile is
an executor-level addition or a mod. The qwen4 b12x arm boots with `VLLM_PLE_TABLE_MEMORY=disk` and no
profile (`recipes/qwen4/qwen3.8-flash-next-nvfp4-solo-vllm-b12x.yaml:13-14,46`) — which says nothing
about seccomp. **Probed 2026-10-26: this fleet's Docker DENIES all three** — `io_uring_setup(425)`
returns `ret=-1 errno=1` (EPERM) in a `--rm` container while the host reports
`kernel.io_uring_disabled=0`, because the built-in profile is an allowlist (`defaultErrnoRet: 1`) with
no io_uring name on it. Fixed fleet-wide the same day by `tools/enable-io-uring.py` +
`tools/enable-io-uring.sh` (`seccomp-profile` in `daemon.json`; index and caveats in
`tools/README.md` §enable-io-uring): after the change `io_uring_setup` returns `fd=3`,
`io_uring_enter` `ret=0`, `io_uring_register` `errno=14` (EINVAL — allowed, no buffers registered). **Image
content**: confirm the pin exposes `table_memory` before paying for a boot (`docker run --rm --entrypoint
python <image> -c "from vllm.config.engram import EngramConfig; print('table_memory' in EngramConfig.model_fields)"`).

**The acceptance test** is one four-node boot on `.30`–`.33` after the owner stands the production serve
down (`QUESTIONS.md` `#4`), with the checkpoint already resident per node. On that one serve:
`/v1/models` reports `max_model_len 1,048,576`; the startup banner echoes the `--engram-config` and the
Engram module logs its disk table; `benchmarking/concurrency-ladder.yaml` gives C1 and C10
(`is_context_prefill_phase: false` rows only, `--fresh`); the house battery runs at 4096 tokens
thinking-on; and the needle ladder runs 32,768 / 131,072 / 983,040 **on the same serve**. Pass = both
speed bars and both accuracy bars inside the tolerances at the top of this section, on one boot. A C1
pass with a C10 miss is a partial, and it is the expected shape if the batch path has not closed.

**If the test fails on C10: the closest reachable point, and the single dependency.** The closest point
is then low-concurrency parity with a C10 near 70 % of the bar — the retired lane's batch ratio, with the
C1 gap closed by RoCEnante and b12x. One dependency would change the verdict: **an upstream release
carrying both the disk-Engram placement and the b12x batch path**, which is what turns a fork-held
capability into a pinnable one. Until then the route's risk is concentrated in one cell, and one boot
measures it.

**Not verified here.** No boot was run. The 47.45 ms/step and the ~73 t/s figures are a source comment and a
project changelog, both on hardware we do not own (`LIKELY`), neither on a workload comparable to
`concurrency-ladder.yaml`; the fork pins the 0909 body (`fb2764a5…`), not `1bae0e10…` — the refresh shares
`config.json` byte-for-byte (`recipes/ds4/README.md:38-40`), but no vLLM boot has served it. No C10, house
or needle result exists on any vLLM DeepSeek-V4.1 route, here or elsewhere.


**2026-10-24:** the window-1 candidate survey is archived at `attic/ds4/DS4-CANDIDATES.md`. Its
still-live next-window top picks carry forward: (1) **Stack C — the vLLM b12x parity boot**
(`DEEPSEEK.md` §17 sketch + acceptance test; authorized per `QUESTIONS.md` #17; remaining gate is the
io_uring/seccomp probe — `io_uring_setup` under `--rm` first); (2) the **bertholomus EXL3 2.5 bpw
(1017)** trial as the cheapest new-body route, TP=2 pair first. Its §3 counterexample worth keeping:
the VQ route is a measured single-Spark TP=1 exception to §13's byte wall (YoungAi 113.6 GB body,
prefill 489 t/s / decode 30.7 t/s, 2026-09-28) — single-node only, no TP=4 path, but §13's "no
1017-class body fits TP=1" should be read with it named.

## 18. The community 1017 repo is our own stack — and the TP_PAD inference it suggested (refuted 2026-10-23, see §18.1)

> **Falsified 2026-10-23 — the split is ON on the shipped pair; see §18.1.** Everything below is the
> record as it stood before the window, kept because the boot9 quote is the historical evidence.

**Subject.** `MashieSaldana/DeepSeek-V4.1-Flash-1017-4x-DGX-Spark` @
`ec61f23890c3ddea832b637cb5b6ab72aa8a5ae1` (2026-10-23T13:45+01:00), MIT, 39 tracked files: two recipes,
three docs, eleven aggregate CSVs and twelve raw `llama-benchy` JSONs from a 2026-10-19 tuning window on
four DGX Sparks (`README.md:24-28,378-386`). It presents itself as an independent production note, "not an
official Little Cedar Group or knapcio repository" (`README.md:7-9`).

**Identity — this is Stack A.** Both lanes build knapcio's `Dockerfile.canary-roce` on the **same base
image** `lmsysorg/sglang:dev-dsv41@sha256:4a5d132a…` (`README.md:252`; `recipes/ds4/Dockerfile.knapcio-dsv41:56`),
with the **same SGLang tree** `f80c91a4b` and the same `sglang-kernel 0.4.7` / `sgl-deep-gemm 0.2.0`
(`README.md:257-259`; `Dockerfile.knapcio-dsv41:48-51,60-72`), on four GB10 nodes and the same checkpoint
revision `1bae0e10…` (`README.md:16-17`; recipe `:7`). Their build sits at knapcio `403a5aa2` (2026-10-18),
ours at `27616bec` (2026-10-12) plus the health-port patch, and `git diff --stat 27616bec 403a5aa2` touches
**no** `adapter/`, `boot.py` or `Dockerfile` — only `README.md`, `docs/switchless-ring.md`,
`files/nccl.sh`, `scripts/ring_mesh/plan.py`, `start.sh` and two tests. Their decode numbers are therefore
one env line away from ours, not a different engine — which is exactly what makes the next finding
load-bearing.

**The pre-window hypothesis: `DSV41_TP_PAD=0` is live on our line, so the replicated split is OFF on all 42
layers.** (Refuted 2026-10-23 — see §18.1: the shipped pair logs the split ON.) The adapter defaults
padding on — `tp3_pad.py:26 @ 27616bec` reads
`if os.environ.get('DSV41_TP_PAD', '1') in ('0', 'false', 'off')` — and no file in this repository ever
mentions the key (`git grep DSV41_TP_PAD` = 0 hits; `git log -S DSV41_TP_PAD --all` = no commits). With
padding on, the per-layer split probe fails and `replicated_split` falls back to the stock replicated GEMM
plus a padded all-gather for `wqkv_a` 1792×5120 and `engram.wkv` 25600×6144 on every one of 42 layers. The
archived head-rank serve log of our 2026-10-02 quartet boot
`.scratch/ds4/knapcio/logs/boot9-head-serve.log` (**git-ignored**, `.gitignore:23` — which is why the
evidence never surfaced in a `git grep` of the tracked tree) records it directly:

```text
:8            DSV41 TP pad installed (tp=4)
:9            launcher: boot.py run NNODES=4 NODE_RANK=0 ... TP=4 EP=1 PORT=8888
:233-234      [replicated_split] model.layers.0.self_attn.wqkv_a: slice failed on rank 0: AssertionError()
              [replicated_split] model.layers.0.self_attn.wqkv_a 1792x5120: split OFF (rank 0 window False, slice False; 0/1 layers on so far)
:242-243      [replicated_split] model.layers.1.engram.wkv: slice failed on rank 0: AssertionError()
              [replicated_split] model.layers.1.engram.wkv 25600x6144: split OFF (... 0/2 layers on so far)
:322-324      [replicated_split] model.layers.39.self_attn.wqkv_a: slice failed on rank 0: AssertionError()
              [replicated_split] model.layers.39.self_attn.wqkv_a 1792x5120: split OFF (... 0/42 layers on so far)
```

Counts in that file: `split OFF` 42, `slice failed` 42, `split ON` 0, `window GEMMs` 0, `compact gather
(roce)` 0; the six `armed for ['wqkv_a', 'engram.wkv']` lines are install-time prints and report no
per-layer outcome (`replicated_split.py:345 @ 27616bec`, versus the per-layer line at `:307`). That is
byte-for-byte the failure the community repo documents, together with its fix (`docs/gates.md:35-43`;
`README.md:102-127`), and upstream reports the same shape at its own build, where the key is pinned:
`DSV41_TP_PAD: "0"` (`recipe/production.yaml:115`).

**Why it carries from that boot to the shipped line.** The adapters are the same code:
`git diff --stat 58f2321 27616bec -- adapter/replicated_split.py adapter/tp3_pad.py` is empty — only
`adapter/sitecustomize.py` gained nine lines, the Anthropic-protocol and `DSV41_PREFILL_BYPASS` hooks, and
the `tp3_pad.install()` call site (`sitecustomize.py:324-325 @ 27616bec`) is untouched. The failing tensor
shapes are the 1017 refresh's shapes too, since `config.json` is byte-identical between the two weight
repositories (`recipes/ds4/README.md:38-40`). The one honest gap: the log is **canary-era on the pre-1017
checkpoint** `dba1be0a` (`:40`, `:61`) with the old `max_total_num_tokens=4000000, chunked_prefill_size=4096`
line (`:422`), so "still OFF on `acfc331a` + 1017" rests on code identity plus identical shapes, not on a
second log — `LIKELY`, one grep of the next shipped boot promotes it to VERIFIED.

**Ownership: the flip is free.** Nothing in the shipped path can set or override the key. `RECIPE_ENV`
does not contain it and `AB_ENV` is a seven-key set that does not either (`launcher.py:354-364`), so
`apply_recipe_env` never writes it (`:376-380`); `SGLANG_EXTRA_FLAGS` carries only `SWA_PREFIX_TAILS`,
`PREFILL_DECODE_INTERVAL` and `FP8_GEMM_BACKEND` (`:384-391`), and TP_PAD is an adapter-read env var, not
an SGLang flag, so that path can neither add nor strip it; `run.sh` sets no environment at all (it creates
and reowns cache directories, `run.sh:112-116`, then gates on files, `:121-133`); and the launcher hands
the process env through untouched — `env = dict(os.environ)` (`launcher.py:729`) into
`os.execve(..., env)` (`:831`). So `-o env.DSV41_TP_PAD=0` reaches the adapter today with no file change;
a permanent landing is one `RECIPE_ENV` line, deliberately **not** added to `AB_ENV`.

**The delta table — only rows that could move performance.**

| parameter | upstream | ours | direction and mechanism |
|---|---|---|---|
| `DSV41_TP_PAD` | `0` (`recipe/production.yaml:115`) | unset → `1` (`tp3_pad.py:26 @ 27616bec`) | **upstream ≻ ours, magnitude unmeasured.** Split ON replaces per-layer replicated GEMM + padded all-gather with window GEMMs and a compact RoCE column gather on 42 layers/step; upstream never isolated it same-image (`README.md:393-395`), and the boot9 log above proves our side of the comparison |
| memory line | `mem_fraction_static 0.80` + `chunked_prefill 4096` (`recipe/production.yaml:41-42`) | `0.78` + `8192` (`launcher.py:144,156`) | **capacity, not tok/s.** Their 0.01 ≈ 1.22 GB ≈ 0.73M tokens (`docs/boot-and-memory.md:57`) is a pool rule; our pairing is deliberate — at 0.80 a 1M prefill leaves 2.7 GiB head versus 5.7 at 0.78 (§9) — so copying one half of their pairing would regress the other |
| our `DSV41_FAST_LOAD` pool cost | they ship `0` to keep 9.12M tokens; the fast loader costs −24.5 % at 0.80 (`recipe/production.yaml:119`; `docs/boot-and-memory.md:95-111`) | we ship `1` (`launcher.py:282`) for boot time; EP1 delta **UNMEASURED** (`launcher.py:187-199`) | **ours ≺ upstream in capacity, ≻ in boot time.** Decode showed no defensible change on their six-run pair (p ≥ 0.061, `docs/tuning-log.md:124-136`); our effective pool is unknown until a fast-loader boot prints its budget |
| `SGLANG_FLASHINFER_MOE_FUSED_FINALIZE` | `0` (`recipe/production.yaml:127`) | unset → `True` (`python/sglang/srt/environ.py:1048 @ f80c91a4b`) | **ours ≻ upstream ≈0.3 ms/step**, paid for with run-to-run drift up to ~1 nat on first-token logprobs. Our own note says keep it 0 (`attic/ds4/AGENTS.md:1205-1207`) and the launcher never applies it: a determinism divergence on our side, not a speed lever to copy |

**Not a delta, stated so it is not re-opened.** `DSV41_CERT_HEAD` is already effective `0` for us
(`cert_head.py:99 @ 27616bec`), so the +26.6 % d8k c1 the community repo banks for turning it off
(`README.md:129-150`) is a gain this lane already holds; `--enable-decoder-swa-bounded-replay` is hardcoded
in `boot.py:330 @ 27616bec`, making their `enable_decoder_swa_bounded_replay: true`
(`recipe/production.yaml:47`) decorative on both sides; `DSV41_PREFILL_EMPTY_CACHE_TOKENS` is 8192 by
adapter default (`prefill_empty_cache.py:30 @ 27616bec`), so their explicit pin is a no-op; `MAX_RUNNING_REQUESTS`
16, `cuda_graph_max_bs_decode` 16, `attention_backend dsv4`, `moe_runner_backend flashinfer_mxfp4` and
`fp8_gemm_backend flashinfer_cutlass` match (`boot.py:322-323 @ 27616bec`; recipe `:67-76`). Their
production carries **no** scheduler or cache flag we lack — `--min-free-slots-delay`, the fp4 indexer,
`--sleep-on-idle` and `--enable-cache-report` appear only in their bridge experiment
(`docs/tuning-log.md:64-70`) — and EP > 1 stays falsified on our hardware (§8.1).

**Reproduction trap in their repo.** `recipe/production.yaml` is described as "the flattened,
self-contained recipe" (`README.md:304`), yet it carries **no** `MEM_FRACTION_STATIC` and **no**
`MAX_RUNNING_REQUESTS`, and this image's `boot.py` defaults those to **0.95** and **4**
(`boot.py:312,314 @ 27616bec`) while ignoring CLI argv entirely (`:431-443`). The documented live values
`mem_fraction_static=0.8 max_running_requests=16` (`README.md:45,47`) can therefore only have come from the
unseen `@experimental/…` base (`recipe/overlay.yaml:17`) that the flatten dropped. **Do not copy that file
as a recipe**; its CSVs and raw JSONs are real artifacts, but its recipe is not self-contained.

**Not verified here.** No boot was run for this section, no node was contacted, and none of the upstream
numbers are transferred: their cells are depth 0 / 8192 at concurrency 1 / 10 with n=3–6
(`benchmarks/ab-4cell.yaml:5-9`; `benchmarks/summary.csv:1-9`), a different profile and a different pool
from this lane's ladder, and their own d8k c1 values spread 54.8–72.0 within one day
(`docs/tuning-log.md:133-136`). The TP_PAD magnitude is unmeasured on either side. What §18 established was
the *history* — a canary-era `42/42 split OFF` — and the *price of finding out* — one boot, no file edit;
§18.1 records that the window falsified the transfer to the shipped pair.

### 18.1 The window's resolution: the split was never OFF, and the treatment never booted (2026-10-23)

**Falsified — on the shipped pair the split is ON.** The first post-fence window booted the shipped arm
(image `acfc331a`, 1017 body `1bae0e10…`, pad left at its default) on `.30`–`.33`, and every rank logged
`split ON, window GEMMs (no pad)` with **`split OFF` 0** and **`slice failed` 0** (`a1-control-node*.log`):

```text
[replicated_split] model.layers.0.self_attn.wqkv_a 1792x5120: split ON, window GEMMs (no pad) (rank 0 window True, slice True; 1/1 layers on so far)
[replicated_split] model.layers.1.engram.wkv 25600x6144: split ON, window GEMMs (no pad) (rank 0 window True, slice True; 2/2 layers on so far)
```

The 2026-10-22 baseline serve log shows the same, so the canary-era boot9 `42/42 split OFF` **does not
carry** to the shipped pair despite byte-identical adapters. The pad adapter still prints `DSV41 TP pad
installed (tp=4)` — 5× on rank 0, 4× per worker — and the per-layer probe succeeds anyway: the install
print is a precondition, not the outcome. §18's inference from adapter identity was wrong in the only
direction that mattered. **Consequence: do not ship the one-line `RECIPE_ENV` change.** The owner's
ship-if-passes permission was conditional on a passing treatment, and the treatment never served.

**The treatment never booted — an infrastructure result, not a knob result.** All three
`-o env.DSV41_TP_PAD=0` launches died before weights load: `RuntimeError: NCCL error: unhandled system
error` at `ncclCommInitRank`, then `Call to ibv_reg_mr_iova2 failed with error Cannot allocate memory`
(3 lines across the harvested logs, the first-failing rank moving rank 3 → rank 0). The **ownership test
passed in the direction that matters**: `DSV41 TP pad installed` count is **0** in all ten harvested
treatment rank logs against 5/4 in control — the override reaches the adapter with no file edit, exactly
as §18 argued. Only the premise about split state was wrong.

**New open item — RDMA registration wedge.** After several engine starts the *control* stopped booting too
(2/2 failures at 22:43Z and 22:57Z, first-failing rank moving `.31` → `.30`), and a `.30`-free rerun on
`.31`–`.34` died with the same NCCL error. Three reboots (`.32`/`.33` at 22:24Z, `.31` at 22:53Z) cleared
it temporarily each time. It correlates with nodes not rebooted since the window opened (`.30`, `.31`)
and with cumulative engine starts, and it is **not** attributable to the pad flip. Mitigation: reboot the
implicated node. `.30` was never rebooted, per the owner's rule, and is now implicated — a clean quartet
needs owner approval to reboot it (`QUESTIONS.md` `#18`).

**New open item — the KV pool regressed by half, and the pin is inert.** A1 profiled
`max_total_num_tokens=3,424,000` with `available_bytes=7.21 GB`, where the 2026-10-22 boot on the same
nodes, image and pin profiled 7,342,336 → pinned 6,849,792 at `available_bytes=13.31 GB`. Both ran
`mem_fraction_static=0.78` with `DSV41_FAST_LOAD=1`; ~6 GB more was resident at pool-sizing time. Cause
undetermined — `LIKELY` the fast loader's uncounted memory, whose documented 3–6 % at EP2 cannot explain
46 %. `MAX_TOTAL_TOKENS=6,850,000` is therefore **inert** on today's boot, and 6.85M must not be quoted as
today's pool.

**`QUESTIONS.md` `#9` closes on this boot.** `[moe_b12x_next] armed: routed MoE on b12x_next a7d7d29b
(W4A8, in-place repack); graph bs [1 … 16]`, zero `WARNING: DSV41_MXFP8_BACKEND=` lines, and exactly one
`--fp8-gemm-backend flashinfer_cutlass` in `/cache/runtime/state/launch.json`. **Field-name correction:**
this SGLang capitalises the dump key as **`fp8_gemm_runner_backend`**, so grep for that; the original
acceptance wording (`fp8_gemm_backend=`) would read as a failure on a passing boot.

**The window's cells (A1, `.30`–`.33`, task `a2e141223b52793c_7afff0589a33`).** TTR port **161.3 s** /
HTTP **168.5 s**; C1 **65.63 ± 5.08**, C2 94.89 ± 7.47, C5 132.94 ± 6.97, C10 **133.34 ± 11.38** (n=5,
sample sd); prefill 3905.8 / 4884.5 / 5399.2 / 5636.4 t/s; the 131,072-depth cell prefills at 5242.3 t/s
→ TTFR 25.02 s, decode 75.68 ± 9.73. C10 is **above** the 116.27 bar while C1 sits ~5 % under 69.28 —
**not a new baseline**: one boot, and a pool that differs from the pinned one. Receipts
`~/benchmarks/tp4-pad-20261023/` on the head.

**Operational rule.** On the head, `HOME=$PWD/.local/sparkrun-home` **fails** for this arm: it mounts an
empty HF cache (model-cache publication lease error — no 475 GB body) and a root-owned runtime tree
(chat-template `PermissionError` on ranks 2/3). Every successful boot used the real `HOME`; recorded in
`AGENTS.md`.

### 18.2 The FAST_LOAD=0 control (2026-10-24): the KV triad, and the pin per mode

The owed control boot ran in the 2026-10-24 window on `.31`–`.34` (shared BeeGFS cache, same image
`acfc331a`, same 1017 body `1bae0e10…`, same serve line), after a fix to the overlay launcher: the
first control launch passed `-o env.DSV41_FAST_LOAD=0` and the serve still logged `DSV41 fast load
ARMED` five times — `DSV41_FAST_LOAD` sat in `RECIPE_ENV` as a hard override, so the launch env was
clobbered (`recipes/ds4/mods/dsv41-sglang-overlay/launcher.py`, the same trap §6.2 recorded for
`DSPARK_BLOCK_SIZE`). The key joined `AB_ENV` (`49471a2`) and the relaunched control profiled with
**zero** `fast load ARMED` lines. That clobbered first attempt is still a FAST_LOAD=1 data point:
it profiled 4,355,584 at `available_bytes=8.66 GB`, `load_weight=77.04 s`.

**The triad, one serve line, one image, one body:**

| boot | FAST_LOAD | max_total_num_tokens | available_bytes at sizing | load_weight | task |
|:--|:--|--:|--:|--:|:--|
| 2026-10-22 baseline (`.30`–`.33`) | 1 | 6,849,792 | 13.31 GB | — | `a2e141223b52793c_e11d626ec2c6` |
| 2026-10-23 regression (§18.1) | 1 | 3,424,000 | 7.21 GB | — | A1 window |
| 2026-10-24 pool boot 2 | 1 | 4,238,080 | 18.82 GB | 71.15 s | `~/benchmarks/pool-boot-20261024/` |
| 2026-10-24 window boot 1 | 1 | 3,846,656 | 7.87 GB | 138.12 s | `a2e141223b52793c_c3190282f4d4` |
| 2026-10-24 control | **0** | **6,849,792** | 12.77 GB | 583.97 s | `a2e141223b52793c_2472013827ce` |

The control settles the causality the regression item left `LIKELY`: at FAST_LOAD=0 the same line
profiles **6,999,040** full tokens (`bytes_per_full_token=1670.75`) and the 6.85M pin clamps to
**6,849,792 — bit-identical to the 2026-10-22 baseline**, not near it. Every FAST_LOAD=1 boot
profiles a smaller and variable pool (3.42–4.36M across four boots) because SGLang sizes from the
head's `MemAvailable` while the eager loader's pinned reads leave memory visible-but-uncounted; the
spread between the 18.82 GB and 7.87 GB boots is page-cache timing, and no FAST_LOAD=1 figure is
reproducible enough to pin against.

**What the pin should be per mode.** At FAST_LOAD=0 the shipped `MAX_TOTAL_TOKENS=6850000` is
**correct as shipped** — 97.9 % of the 6,999,040 budget, and the engine clamps it to the profiled
6,849,792. At FAST_LOAD=1 the pin is inert-but-harmless: the profiled value is always smaller, the
engine always takes its own profile, and quoting "the pin" for a fast-loader boot is wrong (quote
`max_total_num_tokens` from the boot). The open owner call is whether the recipe should keep the
single 6.85M pin (correct where it matters, self-limiting where it does not) or pin per-mode —
`QUESTIONS.md` `#21`. The control's cost side is recorded for that decision: the stock loader's
`load_weight` is **583.97 s** against 71–138 s eager over the pool, i.e. the ~8.5× load cost is what
the larger pool buys. Receipts `~/benchmarks/tp4-window-20261024/` on the head
(`boot1-baseline.launch.log`, `boot3-fastload0.launch.log`, `boot3-fastload0-rank0-serve.log`).

### 18.3 The 2026-10-24 window's two non-DS4 outcomes (window record)

Both belong to other lanes; recorded here because they are this window's closures and the lane docs
carry the detail.

- **`#7` MiniMax-H3 four-rank video cell — measured negative** (`recipes/media/README.md`
  §"The four-rank probe"). Three walls in boot order: (1) the `auto` performance mode's auto-tuner
  probes torch device ids `0..num_gpus-1` as *local* and a 1-GPU-per-node fleet dies at arg parse
  (`speed` mode skips it); (2) repo-id-shaped component-weight overrides die under
  `HF_HUB_OFFLINE=1` on `HfApi().model_info` with no cache fallback (absolute pool paths
  short-circuit to the local branch — commit `b9ca89a`); (3) engine-side, unresolved: after the
  warmup-staging fix (input saving must stay *enabled* at an absolute path on the four-rank serve),
  the first distributed video request **deadlocks** — four ranks at 0 % GPU, warmup frozen at
  `0/1`, zero errors. Receipt: `~/benchmarks/tp4-window-20261024/H3-TP4-CELL-RESULT.md`.
- **`#7` H3 four-rank retry under `--warmup-mode off` — second independent reproduction, FILED
  upstream as sgl-project/sglang#46390 (2026-10-25, window 3).** The recon's action-1 lever
  (`NCCL_DEBUG=INFO` + hand-set `NCCL_SOCKET_IFNAME`/`NCCL_IB_HCA` + `NCCL_NVLS_ENABLE=0`) is now
  exhausted: NCCL init is clean on every rank (`Connected all rings/trees/binomial trees`, `Using
  network IB`) and the serve still wedges — this time with warmup OFF, so the health gate's own
  internal generation never returns and `/health` never binds (40+ min, 4 × 0 % GPU, zero errors;
  `sparkrun_05929de845c64661_6517f5f8884b`). Two boots, two request issuers (engine warmup; health
  gate), same silent freeze ⇒ the wedge is the first cross-node pure-Ulysses collective, matching
  the recon's "most likely mechanism". Torch SDPA fallback present as expected (#40558), and it
  forces `ring_degree=1` on sm_121. Receipts `~/benchmarks/tp4-window3-20261024/`
  (`h3-retry-node{1..4}-serve.log`, `h3-retry-launch.log`); upstream draft
  `.scratch/tp4-window3/upstream-h3-a2a.md`. The `.35` single-node proof stands.
- **GLM-5.3 3bpw TP=4 stall triage — H1/H2 refuted, H3 sharpened** (`recipes/glm/README.md`). The
  triage's one-boot 32k-window experiment ran the same window: the stall reproduces identically
  with **zero NVRM events** at a 17.0 GiB margin (H1, unified-memory exhaustion, refuted as the
  sole mechanism), and the launcher mod sets `TF_GLM_EMBED_SPLIT=1`/`TF_GLM_MTP_REUSE=2` itself
  (H2, missing env, refuted by source). Remaining hypothesis: **NCCL interface selection** — the
  fork transports over plain NCCL and the working 2026-10-13 runbook hand-set
  `NCCL_SOCKET_IFNAME`/`NCCL_IB_HCA`, which the sparkrun path does not. Next-window one-knob
  experiment recorded in the triage file.
- **GLM-5.3 3bpw TP=4 — the H3 one-knob fix CONFIRMED, and the arm's perf + quality cells are
  measured (window 2 → window 3, 2026-10-24/25)** (`recipes/glm/README.md`). With
  `-o env.NCCL_SOCKET_IFNAME=enp1s0f0np0 -o env.NCCL_IB_HCA=rocep1s0f0,roceP2p1s0f0`
  (`NCCL_NET_PLUGIN=spcx` is absent from the image — dropped) the boot passes the pre-load stall
  every time: window-2 boot2b HTTP-ready 2746.3 s, window-3 boot1 **2538.9 s**. Window-3 measured
  cells (task `7d9a3a61b33a29e4_e1ba2bd6f9d9`, quartet, n=5 decode rows, `--fresh`): C1 **28.83 ±
  1.37**, C2 per-request 28.94 ± 0.99 (agg 37.4), C5 per-request 26.71 ± 5.44 (agg 76.3), C10
  per-request 28.21 ± 3.49 (agg 145.8) t/s — per-request decode flat 27–29 t/s across C1→C10, so
  the MTP-3 draft head sustains under load and aggregate scales ~5.1× at C10; house @4096
  thinking-on **37/37** (easy 19/19, hard 18/18), the arm's first quality battery through the
  recipe path. Receipts `~/benchmarks/tp4-window3-20261024/` (`glm-perf-ladder.*`, `suite-glm/`).
  The one-knob env is load-bearing every boot (TTR ~42–46 min at ~95 MB/s pool reads with
  CPU-dequant gaps); window-2's ladder `--skip-run` auto-finish failure (bench-id collision →
  stale state, c10 FAILED) is why the cells took two windows.

### 18.4 The 2026-10-25 window's Beam boot-gate (window record, explore lane)

- **Beam staging + quartet boot-gate — PASSED (window 3, 2026-10-25).** Staging leg:
  `reflection/Beam-1.0-501B-A23B-NVFP4` @ `f8ecac0e…` to the shared BeeGFS pool, `du -sbL`
  **293,654,945,142 B** vs the card's `usedStorage` **293,648,862,719 B** (+6 MB overhead);
  `vllm/vllm-openai:reflection-beam` pulled to the head (38.5 GB on disk, RepoDigest
  `sha256:c1a6be6ad080…` — the TODO's pull-time `7fc940745c…` no longer matches the tag, it was
  re-pushed). Boot-gate leg: `recipes/explore/zz-beam-1.0-501b-a23b-nvfp4-tp4-vllm.yaml`
  (`7afcafb`; ENTRYPOINT fix `debb1eb` — the image declares `ENTRYPOINT ["vllm","serve"]`, which
  sparkrun's launcher refuses, so `executor_config.entrypoint: ""` is required), task
  `sparkrun_30078b4aa125dd7d_b2f8c6e5117c` on `.31`–`.34`, NVFP4 TP=4, fp8 KV, default
  `flashinfer_trtllm` MoE path: `/v1/models` 200 at 05:11:26Z (TTR ~18 min from the 04:53 relaunch
  — the 293.6 GB pool read went fast and no 10-min FlashInfer autotune stall followed), smoke chat
  correct (17×23 = 391, `finish_reason: stop`). **The kernel falsifier never fired — the marlin
  retry was not needed.** One knob gap recorded: the recipe omits the card's
  `--reasoning-parser beam`/`--tool-call-parser beam`, so the smoke content shows raw
  modified-Harmony `<|channel|>` markers — content correct, parser follow-up for any full cell
  (TODO §explore Beam item cells (b)–(d) remain: house+needle, BFCL tools leg, DFlash2 A/B). One
  process miss on the record: the first gate fire (04:41:57Z) failed fast at sparkrun validation
  and sat unnoticed ~10 min because no completion watcher was armed — any auto-fire script now
  gets its watcher at fire time. Receipts `~/benchmarks/tp4-window3-20261024/`
  (`beam-gate-launch.log`, `beam-gate.log`, `beam-gate-node{1..4}-serve.log` harvested pre-stop,
  `beam-gate-stop.log`); stopped by literal id, quartet 0 containers. TODO §Retry queue item 3
  closes on this.

## 19. Upstream knapcio adapter update — findings (2026-10-26)

**Method.** GitHub API/raw reads of `knapcio/DeepSeek-V4.1-Flash-4x-DGX-Spark-TP4` against our
adapter-overlay pin `27616bec` (v2.4, 2026-10-12); nothing below is boot-verified by us — every
number is upstream's own claim, cited to its commit.

**What changed upstream since `27616bec` (79 commits, HEAD `aff52fa5`, 2026-10-24):**

- Upstream quarantined the v2.4 era we pin: issue #16 reported Xid 13/43 CUDA faults under large
  prefix-cache hits (200k–966k cached tokens); the fix path is their PR #18 backporting SGLang
  #41303 (bounded-replay window safety) with `--fuzz=0` plus a rebuild — "old v2.4 images require
  a rebuild" (`de6ef51c`, `docs/issue-16-swa-crash.md`). Our vendored overlay descends from exactly
  that quarantined lineage, on the same tree, without the #41303 backport.
- v2.5 (`c3fe50a8`/`4123250f`, 2026-10-22) re-qualified the v2.4 lever set on rebuilt images
  (their sparkDash c1 prose/code 88.6/144.9, speedbench 85.9), fixed the logprob-decode hang and
  the Linux staging path (`f9a1de41`), and repaired the prefill-SP adapter after its hash-pins
  drifted against the #42901/#45301 backports (`57a98886`) — the same adapter-drift failure shape
  our gate exists to catch.
- The tree pin did NOT move: `scripts/fetch-sglang-canary.sh` at HEAD still sets
  `SGLANG_CANARY_REF=f80c91a4b…` (the 2026-09-16 dsv4.1 branch we build from). Instead upstream
  backports ~26 upstream SGLang PRs onto that pin as zero-fuzz patches with per-patch verify+test
  pairs (`patches/sglang-*.patch`, `scripts/verify_*.py`/`scripts/test_*.py`): #41303 safety,
  #42901 layer-20 tail (upstream claims 5–10 % cold-TTFT at 16K–200K on GB300 — unmeasured on
  GB10), #44001 prefill-interval min-BS, #41259/#45410 parallel native encode, #43549
  inline-system prefix cache, #44751 tool-image/thinking ordering, #45301 padded-query buffer,
  #40424 DP-padding, #43448 MHC prewarm, #44923 greedy-flags refresh (`c0b07102` — restores DSpark
  folded-verify eligibility once a sampled request drains), #45450/#45663/#45518 DSpark fixes,
  #45630 MXFP8 decode tactics, #45745/#45793/#45794/#45762/#45804 dsv41 indexer/thinking fixes,
  #45726 fused window layout, #45579 window-history source, #45586/#45699 idle-SWA stores.
- Measured additions: Engram NVMe keepalive (`a2e805a2`/`1059dfe4`, c16 decode +5 % on their fleet
  A/B/A), two weights profiles (`36d2bd33`), `DSV41_WO_A_INPUT_FP8` measured ~3 % slower decode
  and left off (`7991d4a5`), and the #45251 grouped-verify backport carried for a day then dropped
  for hanging every TP rank on a greedy logprob request (`030813ad`, bisected across the 26
  backport steps).
- The in-image gate grew from ~11 tests to ~40: per-patch verify/test pairs plus vendored
  upstream tests run in-image (`Dockerfile.canary` delta), packaging/provenance tests
  (`tests/test_adapter_engine_pins.py`), and the prefill-bypass gate still runs with
  `DSV41_PREFILL_BYPASS_EXPECT=supported` against the tree's own managers code.
- Provenance/licence: new code is credited and documented — the `NOTICE` delta adds SGLang #39665
  `deepseekv41_detector.py` vendored unmodified and the NCCL #2393 AArch64 CTS-fence patch, both
  Apache-2.0; the repo licence is AGPL-3.0; `docs/upstream-watch.md` records per-PR carry/HOLD
  decisions with mechanisms.

**Consequence for our queue.** Upstream has no adapter state for trees newer than `f80c91a4b`, so
the 16–24 h in-house re-port (`ds4-adapter-report-gate`) remains the only route to survey arms 3/5
— its blocking edges stay. What upstream DOES offer is a same-tree overlay upgrade: our v2.4-era
overlay is the quarantined lineage without the #41303 SWA-safety backport, and v2.5+ carries
measured wins on the tree we already build. Queued as `ds4-upstream-adapter-trial` (~4 h,
GitHub-read evidence only — not boot-verified here).

