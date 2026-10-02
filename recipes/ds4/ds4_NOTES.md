# ds4_NOTES — DeepSeek V4.1-Flash EXL3 lane: working record

Session log for `model_symbol=ds4`. Durable facts graduate into `AGENTS.md` and
`recipes/README.md`; this file is pruned. Read `AGENTS.md` first.

## Prior session (2026-09-27/28) — the `max_num_seqs=16` / `gmu 0.85` retune

Four recipes (`…exl3-{tp4,tp4-1m,tp6,tp6-1m}`) retuned to `max_num_seqs: 16`,
`gmu: 0.85`, capture ladder to 64; every arm booted as-shipped and measured.
Consolidated in **AGENTS.md §7.12** and the README table — **do not re-derive
here.** Headline: TP6-1M KV 15,034,010 tokens, C1/C4/C8/C16 = 43.4/72.7/110.2/149.1.

## Prior session (2026-10-01) — spark-arena-v2 long-context "collapse" — CLOSED

**Condensed:** the full chronological record is preserved in `PERF-ISSUES.md`
§§1–10 (the deliverable) and consolidated into `AGENTS.md` §11 + the README.
Do not re-derive here. Headline in one paragraph:

The recipe is healthy. The `spark-arena-v2` "collapse" at `depth>0, c≥2` is the
cost of a **cold deep prefill**, not decode starvation: warm long-context
concurrency is **51 t/s at d32768 c2** (bench reported 5.2). The decisive probe
was `warm_cold.py` (`.scratch/ds4/perf2/`); `disk_isolate.py` (`.scratch/ds4/perf3/`)
then showed the cold prefill is **compute-bound, not Engram-disk-bound** (ratio
0.99). `--long-prefill-token-threshold 2048` was a **mixed** result and was **not
shipped**. No throughput-motivated recipe change; envelope: cold deep prefill
~1300 t/s @TP4 and serialises under concurrency. Process notes that survive:
`sparkrun benchmark --profile` resolves from the **registry cache**, not the
working tree; the serve log is `/tmp/sparkrun_serve.log` **inside** the
container (`docker logs` is empty); containers are reaped after a run (use
`--no-rm` to keep one); `rtk ssh` breaks on multi-line commands with parens.


## Session 2026-10-02 — NEW SECOND LANE: knapcio DSV41 SGLang (TP=4, native MXFP4)

**Objective this session:** integrate
`github.com/knapcio/DeepSeek-V4.1-Flash-4x-DGX-Spark-TP4` (SGLang, native
checkpoint, DSpark, Engram-on-NVMe) into this registry. Full provenance/plan:
**`recipes/ds4/KNAPCIO-SGLANG-INTEGRATION.md`**. Recipe:
`deepseek-v4.1-flash-sglang-tp4-knapcio.yaml`; mod: `mods/dsv41-sglang-overlay/`.

Why a new lane at all: it runs the **official** checkpoint (comparator for the
EXL3 94.4% hard-tier question, AGENTS.md E5) and upstream measures **89.7 t/s
prose c1** (~2× our vLLM EXL3 lane) from the b12x kernels + DSpark.

**The old "SGLang is a dead end" verdict is superseded for a purpose-built image.**
The prior blockers were real *for published images*: no single image was both
V4.1 and b12x; the MXFP4-Cutlass MoE rejects `2304/4 = 576` (needs a multiple of
128). Both are solved here — the repo builds `dsv41-4x-spark:canary-roce`
(dsv4.1 branch + adapter overlay + b12x_next; built on all four nodes, internet
works), and **`EP_SIZE=2`** gives `2304/2 = 1152 = 9×128`. `EP_SIZE=1` is the
upstream production line (b12x_next), a follow-up A/B.

**Feasibility verified this session:**
- The **native checkpoints are already in the shared HF cache**: `deepseek-ai/DeepSeek-V4.1-Flash`
  (snapshot `dba1be0a40aa45a94ad051997016db3960a90277`, 510.30 GB, 48 shards) and
  `deepseek-ai/DeepSeek-V4-Flash-0731`. `lmsysorg/sglang:dev-dsv41` (33.2 GB) is present.
- **Engram packs built on all four nodes**: `pack_engram.py --rank R --tp 4`,
  ~47 GiB/node at `/home/red/dsv41-engram/`. Mount the **whole `hub/` dir** — this
  cache uses the two-level `hub/blobs/<xx>/<sha>` layout, so mounting only the
  `models--…` dir leaves every blob symlink dangling.
- **Fabric is full-mesh, not a ring**: two RoCE planes (192.168.0.0/24 on
  `rocep1s0f0`, 192.168.1.0/24 on `roceP2p1s0f0`), all six pairwise pings OK,
  port 1 ACTIVE (port 2 DOWN — do not use `*s0f1`), **RoCEv2 GID index 3**.
  So the switchless-ring path is not needed.

**EP_SIZE: use 1, not 2.** EP=2 *loads* (2304/2 = 1152 = 9×128, clearing the
MXFP4-MoE `%128` check) but **dies at the first decode plan**:
`dsv41-moe-E192-N1152-k6-M5 failed to prepare … planned dynamic direct routing is
unsupported for this launch shape`. `adapter/moe_b12x_next.py` states it plainly:
"the production profile is EP_SIZE=1, EP>1 is an A/B setup". All measured numbers
below are EP=1.

**Sparkrun wiring (the load-bearing bits):**
- The image's entrypoint is `boot.py`, which builds the whole `sglang.launch_server`
  argv from env. sparkrun appends `--dist-init-addr/--nnodes/--node-rank` to the
  command assuming `sglang serve`. The mod's `launcher.py` consumes those and
  maps them onto `DIST_INIT_ADDR`/`NNODES`/`NODE_RANK`/`SERVER_PORT`, then execs
  `boot.py`. The recipe `command:` is a one-line call to the shim.
- A **local-only image is not distributable**: `sparkrun run` pulls it from a
  registry unless the recipe sets **`distribution_config.containers.enabled: false`**
  (the top-level key is `distribution_config`, NOT `distribution`). Also
  `executor_config.volumes` is a **list of `host:container` strings**, not a dict.
- `/state` must be bind-mounted writable (boot.py writes `launch.json`); the image's
  `/state` is not writable as the sparkrun user.
- Rootless sparkrun already grants `IPC_LOCK`, `memlock=-1`, `/dev/infiniband`,
  `shm_size 32gb` — so no `privileged`/`cap_add`/`user` override is needed.

**Measured (boot #4/#5 this session; bench `.scratch/ds4/knapcio/bench_sglang.py`,
two discarded warm-ups, non-streaming 200-token, distinct prompts, greedy):**

| t/s aggregate | C1 | C4 | C8 | C16 |
|:--|--:|--:|--:|--:|
| NCCL only (boot #4) | 27.4 | 62.5 | 73.2 | 155.0 |
| **+ RoCEnante (boot #5, SHIPPED)** | **46.6** | **105.6** | **132.5** | **191.0** |
| upstream v2.3 (their fabric/clock) | 89.7 | 165.9 | 244.6 | 357.2 |

**RoCEnante is the single biggest win this session: 1.70×/1.69×/1.81×/1.23× over
NCCL**, far beyond the 7–25% GB10 inter-boot spread. **C1 46.6 beats our shipped
vLLM/EXL3 TP=4 lane (40.7) on the same four nodes.** Boot log:
`RoCEnante ready: world=4 hcas=rocep1s0f0,roceP2p1s0f0 gid_index=3
max_size=2097152`. Correctness smoke `27*43 -> 1161`, planets correct; DSpark
acceptance 2.4–2.8 unchanged. Rollback is one env line (`SGLANG_ROCE_ALLREDUCE=0`).

**Remaining gap to upstream 89.7 c1 — resolved as "no knob left".** The SPS
ragged-verify table **crashes the Engram path** (upstream's own README lists it
under "Not used"; our fit → `AssertionError: engram target-verify expects one
equal block per request, got 84 tokens for 16 requests of 6`), so **upstream
production is verify-all** and our recipe is already the production line. The
200+ MHz clock-cap convention and fabric differ. **89.7 remains their number.**

**Boot #9 (recipe exactly as shipped) reproduced the numbers within 2 %:**
46.3/106.8/132.7/194.6 t/s at C1/C4/C8/C16 — the lane is stable across boots.

**E5 CLOSED — the headline result.** `quality_hard_sglang.py` (the hard 18-task
tier) against the release checkpoint, two runs: **17/18 = 94.4 %, the same score
and the same single failure (`hard-rev`) as the EXL3 lane** (§7.6). Verdict: the
EXL3 3.5 bpw quantization costs nothing measurable on that battery; the one
failure is a base-model limitation. Artifacts:
`.scratch/ds4/knapcio/quality_hard_sglang{,_rep2}.json`.

**Verdict for the recipes:** the SGLang lane is a working, measured **second
engine** — `deepseek-v4.1-flash-sglang-tp4-knapcio.yaml`, shipped with RoCEnante
ON and no SPS table — and the EXL3/vLLM lane remains the default. Full details,
boot gates, provenance and limits: `KNAPCIO-SGLANG-INTEGRATION.md`; durable
summary: `AGENTS.md` §7.13.
