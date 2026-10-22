# Session status — 2026-10-21 20:15 ET

**Both queues are empty and both nodes are idle** — 0 running and 0 exited containers on `.34` and
`.35` (the highcon probe that was up at 18:49 is finished and gone; the earlier leftover sglang
container from the 07:52 Muse boot is logged at
`~/benchmarks/_leftover-logs/43acfc12bcc4-sglang-20261021.log`). The production quartet's TP=4 serve
is untouched and healthy. Gate: **765 tests OK** (2 skipped — the pooling guard's real-CLI case runs
now that `sparkrun` is on this workstation; the count moved 752 → 765 when the Qwen-Image guard
landed), **52/52 tracked recipes** pass plain `sparkrun recipe validate` (0 errors, 53 files on disk),
**12/52** fail `--strict` (re-run file by file). Everything is pushed, remote tip `2e4a775`.

**2026-10-21 20:00 ET — the single-node queue is now empty too.** **Nemotron-3.5-Lightning-30B-A3B
NVFP4 shipped** (house **37/37**, C1 **63.27 ± 0.65 t/s** with a ladder of 63.27 / 90.81 / 122.27 /
144.15 and prefill flat at ~6.2k, 20.10 GiB, tool calls passing) — the lane's fastest single-node chat
arm, `3800002`. Two follow-ups landed with it: thinking-off is **decode-identical** (62.73 vs 62.74
t/s, recipe serve 63.85 vs 63.49, all inside each other's spread) but costs **five** house items
(**32/37**: `wp-3`, the three `hard-arith` items, `trick-3`), so both shipped numbers are thinking-on
and the reasoning channel is load-bearing; and its **first `sparkrun` boot died once** inside
PIECEWISE CUDA-graph capture with `CUDA error: an illegal instruction` and did not reproduce across
five further boots/variants — retry once before debugging, and it is not a reason to set the
deprecated mamba flag. **That empties the ranked candidate table for 1-node work**: ranks 1–5 are all
closed and 6–10 are 2+ nodes (MiniMax-M3 is 795.5 GiB on the Hub, not the ~220 GB the dossier carried;
Inkling-Small 495.4 GiB). Node-free work also closed tonight: the **house-budget audit** (42 of 43
receipts at 4096; `hard-rev` named as the near-universal discriminator; convention written into
`tools/README.md`), the **render sweep** (53 files, 46 clean, 7 flagged — four host-count refusals and
three checker artifacts, no real defect), the **Qwen-Image sigmas guard** with three negative
controls, and the AGENTS count refresh. **The media-gen residue is now fully measured too:** the
vLLM-OMNI route serves the Qwen-Image checkpoint natively on one GB10 at **8.66–8.75 s warm / 11.19 s
cold** per 1024² 8-step image against the shipped Diffusers arm's 11.49 / 12.64 s — ~24 % faster at
identical peak (36.84 vs 36.82 GiB), TTR ≈ 4 min, `CUDNN_ATTN` auto-selected for sm_121. It is
**recorded as a measured alternative, not an arm**: no recipe, the step knob is inert *and* mis-reported
(4/8/12 → one byte-identical PNG at ~8.7 s while `denoise_step_latency_ms` read 2164/1086/721), and same
seed gives a different picture (`38ce554a…` vs `e24f6e3a…`). **Both 8-step images were then inspected at
full resolution** — an operator defect review, not the owner's eye — and **both are clean typographic
posters**: Diffusers a two-line `SPARK` / `RUN` in blue over orange on cream, OMNI a single-line
`SPARKRUN` in a rainbow run of letters on white, both correctly spelled with crisp edges and **no gross
defect in either** (no smearing, no blended or doubled glyphs, no gibberish letterforms, no step-count
starvation). So the ~24 % win is not bought with visible quality loss, the two differ in **composition,
not merely palette**, and OMNI is not "the same image, faster".

**2026-10-21 evening — the pair block is empty.** Both remaining pair items closed without a
finding. **flash-next is refuted on both engines** (`b85f611`, `510215b`): the b12x build cannot
construct the model config (`qwen_sparse_attention` is not a layer type it knows, so no weight is
read) and the documented `vllm-openai:v0.31.0` fallback clears that gate and dies at worker init
(`Qwen4Exp PLE embedding does not support CompressedTensorsConfig`) — two gates, so the answer is an
image that has both, not a repack and not a knob. **qwen4 labquant-highcon passed its control**: TTR
9.6 min, `max_model_len 262144`, admission unclamped, 41/41 shards, diagnostic payload fired 0 times,
and the d8192/pp2048/tg128 sweep (86.8 / 87.5 / 89.5 / 75.4 t/s against 84.9 / 89.1 / 89.1 / 72.9)
sits inside 3.4 % in every cell — no 10 % finding, the restore did not move the serve. Nothing
pair-bound is runnable tonight; the offsite TP=4 block is the only pair work left and it is an
**owner decision**, not a queued job.

**2026-10-21 afternoon — four results, one of them shipped.** **Nox-4B shipped** at **67.8 %
(1356/2000)** — the best CPU route in the decision lane, 12.8 points over Sol-2B (`39a4f00`).
**JEV-27B does not ship**: 66.8 % (1337/2000) against its 9B sibling's 67.0 % (1340/2000) is three
decisions, 0.15 pp, a tie below the lane's strictly-beat rule. **Muse Glimmer 30B closed as a
checkpoint defect**, not a pack defect — the bf16 control misses `nurkrpas` identically (`3c3c134`).
The **flash-next staging record was corrected**: both nodes have held the 183.48 GB export complete
since 2026-10-15, so only a boot receipt is outstanding (`955c96a`). And the docs moved to the
**sparkrun 0.4.2** build this workstation and the head now both report, with the schema cites
re-derived and three claims that the code had outgrown rewritten (`e85c786`, `745ebd3`).

**2026-10-21 — three results landed, all permanent.** Cybersec arm 5's tools leg closed at **1037/1240
= 83.6 %** (`3fbb5e0`), the ornith **SGLang 0.5.21 bump** validated on all three arms and shipped
(`9d67131`), and the **LTX-2.5 T2V arm** first-booted at **100.13 s cold / 78.1 s warm** (`d61cb30`).
The ornith bump had been the 6–9 h line in Table 2; it is gone, the pair-bound block lost nothing
else, and the single-node queue was then the media-gen residue and the reasoning candidates (the
decision candidates closed the same day: Nox-4B shipped, JEV-27B did not; both remaining lines closed
later the same evening, see the header).

**2026-10-21 02:48 ET — cybersec arm 5's tools leg is finished; the arm is 5/5.** A fresh TP=2 boot
(`2f9a8f3e60a51ee4_3510a5e0d37d`, TTR HTTP-ready 59.407 s) and a cap-free tools-only run scored
**1037/1240 = 83.6 %** in 3,887 s with 0 transport errors (simple 376/400 · multiple 188/200 ·
parallel 181/200 · parallel_multiple 177/200 · irrelevance 115/240), 3.133 s/question. Receipt
`~/benchmarks/cybersec-arm5-tools-20261021/` (`REPORT.md` merges the four 2026-10-20 legs); the pair
was drained afterwards. That removes the arm from Table 2's pair-bound block.

## Table 1 — Current tasks (in flight)

| Task | Machine role | Elapsed | Landed | Remaining |
|---|---|---:|---|---:|
| — none: both queues are empty (0 containers running or exited, no leg processes, no queued node-bound item) — | test pair | — | ornith 0.5.21 bump shipped; arm 5 5/5; LTX T2V shipped; ds4 v0.6 A/B adopted + `reasoning_effort` measured; Nox-4B shipped 67.8 %; JEV-27B measured 66.8 % and not shipped; **flash-next refuted on both engines; qwen4 highcon control passed (2026-10-21)** | 0 h |

## Table 2 — Remaining tasks (queued and runnable now)

| Bucket | Content | Wall | Notes |
|---|---:|---:|---|
| Suite tail — single-node | **0 h — closed** | 0 h | every single-node arm now has a boot, a ladder and a suite receipt; the qwen3 MLX top rung is TRUNCATED at its real ~222.5k window and the ornith YaRN d90 rung passed |
| Other local — single-node | **0 h — closed** | 0 h | everything closed on 2026-10-21: the decision candidates (Nox-4B shipped 67.8 %, JEV-27B tied at 66.8 % and did not ship), the reasoning candidates (Lightning shipped 37/37 at 63.27 t/s; the ranked table has no 1-node entry left), the media-gen non-8-step schedule (Qwen-Image `sigmas` mod + guard with negative controls), the house-budget audit and the repo-wide render sweep. The **vLLM-OMNI route is measured and closed-with-a-comparison** (8.66–8.75 s warm vs 11.49 s, same peak, ~24 % faster; not shipped — no recipe, and both 8-step images inspected clean). **What is left anywhere: (a) the owner's aesthetic choice between the two looks and (b) the offsite TP=4 block** |
| Pair-bound | **0 h — closed** | 0 h | every pair item is resolved: ds4 v0.6 adopted (c8 +26.5 %, c16 +25.7 %, prefill +24.6 %/+39.5 %, pin `d6e4c10d…`), ds4 `reasoning_effort` measured (10.6 % paired saving, one task), **flash-next refuted** (b12x: `qwen_sparse_attention` not a layer type at `ModelConfig`, no weight read; `vllm-openai:v0.31.0`: clears that gate, dies at worker init on `Qwen4Exp PLE embedding … CompressedTensorsConfig`), **qwen4 highcon control passed** (86.8/87.5/89.5/75.4 t/s, all within 3.4 % of control, no 10 % finding) |

## Table 3 — Deferred tasks (cannot run without a named unblocker)

| Deferred | Unblocked by | Where it lives |
|---|---|---|
| **Offsite TP=4 measurement block** (20–28 h: qwen4 W6/W12, ds4 TP=4 candidates, four-node suite legs) | the owner switching the session to an offsite endpoint — **the local pair block is now empty and nothing else is pair-bound, so this is the only pair work left and it is an owner decision, not queued for tonight** | register, under the qwen4 and ds4 items; ask repeated below |
| **Ornith intermittent 1M serve exit** (1–2 h) | a failing boot with the capture armed — **4 of 4 d90 passes now on two builds**, the last one a first-attempt pass on 0.5.21 with a null die-capture | `~/benchmarks/ornith-yarn-d90-20261020/` and the 0.5.21 receipt, plus the register item that stays open for the next failure |

Dropped by owner policy, not waiting on anything: the GLM ≥1M probe and the ornith 397B retry (both
recorded in the lane attic).

## Totals

| Bucket | Range |
|---|---:|
| In flight | 0 h |
| Queued node-bound content, runnable now (Table 2) | **0 h — both rows closed** |
| **Node-bound wall at two lanes** | **0 h** |
| Deferred (Table 3: offsite TP=4 20–28 h + ornith intermittent 1–2 h) | 21–30 h |
| **Grand total including deferred** | **≈21–30 h, every hour of it blocked on an owner decision or a failing boot** |

## Risks

- **BFCL is not resumable**, so a drain mid-leg costs the whole 1,240-question run: the 2026-10-20
  interruption forced a fresh boot and a full re-run on 2026-10-21, which closed it at 83.6 %.
- **Buffered logs look like stalls.** Every long leg tonight has shown a question count frozen for tens
  of minutes while the serve decoded; liveness comes from the serve log, never from the count alone.
- **Pair-bound stall**: the 15–25 h pair block holds both test nodes; nothing single-node runs during it.
- **Stopping a serve can delete its evidence.** `sparkrun stop --all` bypasses `--no-rm` and removes
  the container, taking the in-container serve log with it (it cost the 9B `.35` log on 2026-10-21).
  Stop by cluster/task id and `docker cp /tmp/sparkrun_serve.log` out first.
- **A CPU decision pass is a four-hour window, not two.** Nox-4B took 14,066 s (35.2 s/case) where
  a three-case probe predicted 8,760 s — the first cases are cheaper than the mean, so price a CPU
  arm from a wide probe or from the lane's own per-arm history.
- **The head's `127.0.0.1:8000` is the production TP=4 serve**, so a probe that addresses loopback
  measures production, not the arm. Always use the node's IP root.
- **Address hygiene is done for the tree, not for history** — tracked files are masked (71 lines, 22
  files); pushed history was deliberately not rewritten, so older commits still contain the addresses.

## Closed this session

**flash-next refuted on both engines — the pair item closes with no finding (`b85f611`, `510215b`).**
Weights were already complete on both nodes (18/18 shards each), so the pair boot cost **10.6 s** of
distribution and the staging fear was a measurement error, not a fact. The sparkrun-built b12x image
(`cf5a2a53…`, vLLM `0.1.dev21830+g8244d1c44.d20261015`) cannot build the model config at all: the
checkpoint's `qwen_sparse_attention` is not an allowed `layer_types` member for `model_type:
qwen4_exp`, so **no weight is read**. The documented fallback `vllm/vllm-openai:v0.31.0`
(`sha256:c1c9f6fd…`, local ID `bbe704505570` on both nodes) clears `ModelConfig`, warms up multimodal
in **11.9 s** and starts TP=2, then dies in the worker: `NotImplementedError: Qwen4Exp PLE embedding
does not support quantization config CompressedTensorsConfig`. Two gates, so the answer is an image
that clears both — not a repack, and nothing in the recipe can move either. Lane fact recorded in
`recipes/cybersec/README.md`: `vllm/vllm-openai` declares `ENTRYPOINT ["vllm","serve"]`, which eats
sparkrun's launcher, so an `executor_config` `entrypoint: ""` is required to adopt it (the
sparkrun-built b12x image has no entrypoint).

**qwen4 labquant-highcon control passed (task `1895030211ea0500_3510a5e0d37d`).** TTR **9.6 min**
(`load_weight` 508.93 s), `/v1/models` at `max_model_len 262144`, admission **unclamped**
(`max_total_num_tokens=1587072`, `max_running_requests=32`, mamba 128), **41/41** shards on both the
main and MTP classes, no `_scale` assertion, and the diagnostic payload fired **0** times. Sweep at
d8192/pp2048/tg128, k=8/12/16/24: **86.8 / 87.5 / 89.5 / 75.4 t/s** against the controls'
84.9 / 89.1 / 89.1 / 72.9 — every cell inside **3.4 %**, no 10 % finding. The restored diagnostic mod
did not move the serve, which is the point of the control.

**Nox-4B booted, scored and shipped (`.34`, 2026-10-21).** The CPU decision arm scored **67.8 %
(1356/2000), ★★** on `uvx tool-eval-bench@2.8.0 --decision-bench-only` (KL 0.219, Brier 0.114, ECE
0.063, 0 completion errors, 14,066 s at 35.2 s/case), second in the lane behind clef-flash's 70.3 %
and 12.8 points over Sol-2B. The vendor golden gate passed on aarch64 (`/health` 200 ready, no
`GoldenResult` failure). As sparkrun stages it (`HF_HUB_OFFLINE=1`) the loader still calls the Hub
tree API and `/health` stalled at 503 `loading`; the recipe now carries `HF_HUB_OFFLINE=0`, the
documented mitigation, and boots clean in ~30 s. Ladder c1/c2/c5 all **0.044 req/s** at p50
22,763/45,480/113,797 ms — a pure queue, no batching; c10 was not run (the serve was stopped to free
the pair). Receipt `~/benchmarks/nox4b-20261021/REPORT.md`; commit `39a4f00`.

**JEV-27B measured and not shipped (`.35`, 2026-10-21).** 66.8 % (1337/2000) against JEV-9B's
67.0 % (1340/2000) — three decisions, 0.15 pp, a tie, so it fails the lane's strictly-beat rule and
gets no README or index row. Boot wall 1244 s, most of it CUDA-graph capture (102 graphs, ~660 s);
ladder c1 2.912 / c2 2.974 / c5 4.351 / c10 4.488 req/s with no useful scaling past c2 (the align
path serializes decision prefill). Receipt `~/benchmarks/jev27-20261021/REPORT.md`.

**Muse Glimmer 30B closed: the checkpoint, not the pack (`3c3c134`).** The bf16 control
(`meta-models/Muse-Glimmer-30B @7af58019`, same drafter, same image digest, same flag line bar
`mem_fraction_static 0.80`) answers `nurkrpas` on hard-rev exactly as the NVFP4 pack did — house
36/37, same item, same string — so the weights are the cause and no repack is worth trying. C1 12.1
t/s on bf16 against the pack's 20.2. The arm is out of both trees; route and numbers live in
`attic/explore/AGENTS.md`.

**flash-next staging corrected (`955c96a`).** The lane README said the 183.5 GB export was reclaimed
from every node on 2026-10-14; re-verified, `.34` and `.35` have held it complete since the
2026-10-15 staging (18/18 shards, 183.48 GB, zero bytes fetched). Only a boot receipt is outstanding,
and `.35` carries 78.06 GB of orphan `.incomplete` blobs from the earlier attempt.

**sparkrun 0.4.2 docs pass (`e85c786`, `745ebd3`).** Both files claimed `0.4.0-alpha+g29f53fb` while
this workstation and the head both report `0.4.2-alpha+g36d8a44`. The module paths survived
(`core/launcher.py`, `core/recipe.py`, `core/validation.py`, `models/runtime.py`); 27 line cites did
not and were re-derived, and three sentences were rewritten because the code had outgrown them:
`recipe list`/`recipe search` now fall back to `metadata.description`, the unmapped-key drop is no
longer silent (0.4.2 raises `unmapped-config-key`), and the `_KNOWN_KEYS` literal set moved by two
lines (still 41 keys). The MECHANICS header now names exactly which sections are 0.4.2-numbered and
that the rest are still 0.4.0-numbered. The eleven arms carrying `unpinned-model-revision` were
re-counted file by file: still eleven.

27B-NEXTN suite + ladder (`bench_e66cbef09760`: 15.39 / 28.81 / 60.35 / 102.82 t/s) · 27B-uncensored
tools **1072/1240 (86.5 %)** · kolibri APEX five legs `ok`, needle a real 262k pass · laguna-XS 59.8 %
tools, triaged as capability not parser · qwen3 MLX needle TRUNCATED at ~222.5k · ornith YaRN d90 PASS
with a null die-capture · Sol-2B built, published and scored **55.0 % (1101/2000)** at p50 195 ms ·
qwen4 `zz-labq-no-diag` passed, retiring the diagnostic on the balanced arm (restored in highcon only) ·
27B-NEXTN and arm-1 lane-doc blocks · Laguna-M.1 TP=2 booted, suite + ladder landed (C1 12.85 /
C2 21.85 / C5 34.15 / C10 34.64 t/s), tools 750/1240 triaged as capability · Sol-2B recipe
boot-verified through `sparkrun run` (1101/2000, 80.5 s) · tracked-file addresses masked (71 lines, 22
files → 0) · **cybersec arm 5 — 5/5, tools leg closed 2026-10-21**: house 37/37, needle 3/3 at every
rung, ARC 188/200 (94.0 %), GSM8K 197/200 (98.5 %), tools **1037/1240 = 83.6 %** in 3,887 s with 0
transport errors (`~/benchmarks/cybersec-arm5-tools-20261021/REPORT.md`); the 2026-10-20 interruption
is superseded · **ornith SGLang 0.5.21 bump shipped**: all three arms validated (35B ladder inside
every band, 9B C2 settled at −3.2 % on `.34`, YaRN 6/6 with a first-attempt d90 pass at 97.80 % fill),
receipts `~/benchmarks/ornith-0.5.21-bump-20261021/` · **LTX-2.5 T2V arm shipped**: 100.13 s cold /
78.1 s warm on `.35` at 83.45–84.00 GiB peak, receipt `~/benchmarks/ltx25-recipe-20261021/`.

## Open ask

**TP=4 offsite switch** — the condition that gated it is met (the single-node tail is closed). Options:
switch **now** (20–28 h of TP=4 work becomes runnable while the test pair keeps working), switch **after
the pair-bound block**, or **park** it. Nothing is blocked either way.

**Missing tools on the workstation** (measured 2026-10-21, after `sparkrun` landed there and reported
`0.4.2-alpha+g36d8a44`, the head's own build). One row asks for something; the others are here because
the owner asked which gate steps can now leave the head.

| tool | what the repo needs it for (one caller) | on the workstation | where it works today | ask |
|---|---|---|---|---|
| `sparkrun` | validate, render with `-n`, registry lookup, launch — the whole recipe surface | **yes.** `sparkrun recipe validate <path>` returns the head's answer verbatim, with and without an override; anything registry-qualified (`@littlecedar/…`) or cluster-profile-driven needs `HOME=$PWD/.local/sparkrun-home`, because the real `~/.config/sparkrun/registries.yaml` carries no `littlecedar` entry and `~/.config/sparkrun/clusters/` is empty while the repo-local home has both | head, and the nodes for launches | none |
| `uv`, `uvx` | the guard suite (`uv run python -B -m unittest discover -s tests`, 752 tests) and the docs' own instruments (`uvx tool-eval-bench@2.8.0` at `recipes/decision/README.md:332`, `uvx llama-benchy@0.4.0` via sparkrun) | **yes** (uv 0.13.4); `uvx tool-eval-bench@2.8.0 --version` answers 2.8.0 here | head | none |
| `hf` | model sizing and revision probes (`tools/build-dsv41-combined.py`, the per-arm revision checks) | **yes** (1.29.0) | head | none |
| `docker` | resolving an image ref to its digest (`docker buildx imagetools inspect`, the pin method in `mad-science/SESSION-RECORD.md:354`), plus the node-side log and liveness ops every runbook depends on (`docker cp /tmp/sparkrun_serve.log`, `docker exec … kill -0`, `docker events --filter event=die`) | **partly**: the daemon runs (29.9.1) and `imagetools inspect` resolves the sglang v0.5.21 index and its amd64 manifest from here; there is no GPU, so any command that runs a container stays meaningless | head, and the nodes for container work | none — container work belongs where the hardware is |
| `python3` | the stdlib instruments (`python3 tools/decision-ladder.py`, `tools/quality-battery.py`, `tools/jev-decision-bench.py`) | **yes** (3.14.8; all three print usage) | head | none |
| `ffmpeg`, `ffprobe` | checking a media arm's output — the LTX-2.5 receipt claims h264 1344×768, 121 frames, 24 fps plus AAC (`README.md:237`, `attic/explore/AGENTS.md:501`); no `tools/` or `mods/` script shells out to it, so this is the operator's own verification | **no** — neither is installed | head | install `ffmpeg` here, or accept that video-receipt verification stays head-side |

Checked and present, no row needed because none is a local gate step: `git`, `ssh`, `scp`, `rsync`,
`curl`, `jq`, `setsid`, `stdbuf`, `taskset`, `nproc`, `timeout`, `sha256sum`.

**Effect on the gate.** Recipe validation, `-n` rendering, the 752-test guard suite, `@littlecedar/…`
resolution, `hf` sizing probes, and container-digest resolution can now all run on the workstation; what
stays head-side is anything that needs a GPU or a live container (boots, serves, `docker cp`, benchmarks,
the ladder instruments that measure a live endpoint) and video-receipt verification until `ffprobe`
exists here.