# Session status — 2026-10-21 07:35 ET

**The test pair is drained and idle** (0 containers on `.34` and `.35` at write time; the ds4 v0.6
A/B has not started). The production quartet's TP=4 serve is untouched and healthy. Gate: **752
tests OK** (3 skipped — this workstation has no `sparkrun`, so the pooling guard's real-CLI case
skips), **52/52** recipes pass plain `sparkrun recipe validate` on the head, **12/52** fail
`--strict` (unchanged in count). Landed on top of `9d67131`.

**2026-10-21 — three results landed, all permanent.** Cybersec arm 5's tools leg closed at **1037/1240
= 83.6 %** (`3fbb5e0`), the ornith **SGLang 0.5.21 bump** validated on all three arms and shipped
(`9d67131`), and the **LTX-2.5 T2V arm** first-booted at **100.13 s cold / 78.1 s warm** (`d61cb30`).
The ornith bump had been the 6–9 h line in Table 2; it is gone, the pair-bound block lost nothing
else, and the single-node queue is now the media-gen residue, the decision candidates and the
reasoning candidates.

**2026-10-21 02:48 ET — cybersec arm 5's tools leg is finished; the arm is 5/5.** A fresh TP=2 boot
(`2f9a8f3e60a51ee4_3510a5e0d37d`, TTR HTTP-ready 59.407 s) and a cap-free tools-only run scored
**1037/1240 = 83.6 %** in 3,887 s with 0 transport errors (simple 376/400 · multiple 188/200 ·
parallel 181/200 · parallel_multiple 177/200 · irrelevance 115/240), 3.133 s/question. Receipt
`~/benchmarks/cybersec-arm5-tools-20261021/` (`REPORT.md` merges the four 2026-10-20 legs); the pair
was drained afterwards. That removes the arm from Table 2's pair-bound block.

## Table 1 — Current tasks (in flight)

| Task | Machine role | Elapsed | Landed | Remaining |
|---|---|---:|---|---:|
| — none: the test pair is drained (0 containers, no leg processes); the ds4 v0.6 A/B is next — | test pair | — | ornith 0.5.21 bump shipped; arm 5 5/5; LTX T2V shipped | 0 h |

## Table 2 — Remaining tasks (queued and runnable now)

| Bucket | Content | Wall | Notes |
|---|---:|---:|---|
| Suite tail — single-node | **0 h — closed** | 0 h | every single-node arm now has a boot, a ladder and a suite receipt; the qwen3 MLX top rung is TRUNCATED at its real ~222.5k window and the ornith YaRN d90 rung passed |
| Other local — single-node | 6–11 h | ~3–6 h | media-gen residue (Qwen-Image non-8-step schedules via a `sigmas`-accepting mod, the vLLM-OMNI route) · decision Nox-4B/JEV-27B 3–5 · reasoning candidates 1–3 · **LTX T2V and the ornith 0.5.21 bump are done** |
| Pair-bound | 15–25 h | 15–25 h | ds4 TensorFold v0.6 3–5 · flash-next b12x 3–6 · ds4 `reasoning_effort` 1–2 · qwen4 highcon + 1 probe 8–12 (highcon is also the boot that retires the restored diagnostic mod) |

## Table 3 — Deferred tasks (cannot run without a named unblocker)

| Deferred | Unblocked by | Where it lives |
|---|---|---|
| **Offsite TP=4 measurement block** (20–28 h: qwen4 W6/W12, ds4 TP=4 candidates, four-node suite legs) | the owner switching the session to an offsite endpoint; the local-tail condition that held it is now met | register, under the qwen4 and ds4 items; ask repeated below |
| **Ornith intermittent 1M serve exit** (1–2 h) | a failing boot with the capture armed — **4 of 4 d90 passes now on two builds**, the last one a first-attempt pass on 0.5.21 with a null die-capture | `~/benchmarks/ornith-yarn-d90-20261020/` and the 0.5.21 receipt, plus the register item that stays open for the next failure |

Dropped by owner policy, not waiting on anything: the GLM ≥1M probe and the ornith 397B retry (both
recorded in the lane attic).

## Totals

| Bucket | Range |
|---|---:|
| In flight | 0 h (pair drained) |
| Queued node-bound content, runnable now (Table 2) | 21–36 h |
| **Node-bound wall at two lanes** | **≈15–27 h** |
| Deferred (Table 3, owner action or event) | 21–30 h |
| **Grand total including deferred** | **≈36–57 h** |

## Risks

- **BFCL is not resumable**, so a drain mid-leg costs the whole 1,240-question run: the 2026-10-20
  interruption forced a fresh boot and a full re-run on 2026-10-21, which closed it at 83.6 %.
- **Buffered logs look like stalls.** Every long leg tonight has shown a question count frozen for tens
  of minutes while the serve decoded; liveness comes from the serve log, never from the count alone.
- **Pair-bound stall**: the 15–25 h pair block holds both test nodes; nothing single-node runs during it.
- **Stopping a serve can delete its evidence.** `sparkrun stop --all` bypasses `--no-rm` and removes
  the container, taking the in-container serve log with it (it cost the 9B `.35` log on 2026-10-21).
  Stop by cluster/task id and `docker cp /tmp/sparkrun_serve.log` out first.
- **The head's `127.0.0.1:8000` is the production TP=4 serve**, so a probe that addresses loopback
  measures production, not the arm. Always use the node's IP root.
- **Address hygiene is done for the tree, not for history** — tracked files are masked (71 lines, 22
  files); pushed history was deliberately not rewritten, so older commits still contain the addresses.

## Closed this session

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