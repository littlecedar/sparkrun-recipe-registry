# Board — generated 2026-10-26 00:56 ET

## In flight

| where | owner | what |
|---|---|---|
| census | board-keeper | **00:55 ET 2026-10-26, all six nodes (read-only `ssh` + `docker ps` + `sparkrun status`)**: `.30`–`.35` **1 container each** (6 fleet-wide, matching `sparkrun status`); free root 2.1/2.2/2.3/2.3/1.6/1.8 TB — drift: none |
| `.31`–`.34` | tp4-window3 | **Beam quartet boot live** — `recipes/explore/zz-beam-1.0-501b-a23b-nvfp4-tp4-vllm.yaml` (tp=4) task `30078b4aa125dd7d_b2f8c6e5117c`, 4 containers (`Up 3 minutes` at 00:56, image `sha256:58aa975fed12…`), one per rank |

## Work queue

Mirrors `mad-science/TODO.md` §"Retry queue — unparked 2026-10-25" (items 1–7, schedule order 1→7, the only dependency inside item 3).

| job | node cost | holds | state |
|---|---|---|---|
| 1. H3 quartet retry (stage 4, MiniMax-H3 four-rank video probe; SDPA-on-SM12x + NCCL-init axes instrumented) | four ranks | tp4-window3 | queued (after GLM ladder + 32768 probe per the confirmed order) |
| 2. 32768 prefill-chunk probe (ds4 knapcio) | four ranks | tp4-window3 | queued |
| 3. Beam staging (293.6 GB) + quartet boot-gate | staging control-side; boot-gate four ranks | tp4-window3 | staging leg **DONE** (63/63, `✓ Downloaded`, snapshot `f8ecac0e…`); boot-gate remains, waiting on a free quartet |
| 4. Main-image boot-gate (`sglang-main-arm64:6563312` vs the `v0.5.22` control) | one node | tp4-window3 | **PASSED** on `.30` (C1 21.3 t/s ≈ control 20.38 +4.5 %, within noise; receipts `~/benchmarks/tp4-window3-20261024/gate-c1.*`) — a re-queue is only owed if the gate bar is revisited |
| 5. Ornith-1.5-122B NVFP4 completion — the pre-registered spec-decode cell | one node | tplt4-research | **DONE 2026-10-25** — MTP n=3 **C1 +44 % paired** (38.8 vs 26.9 plain-in-window; acceptance 2.43–2.60; house 36/37 vs 37/37); above the 17 t/s falsifier, still a capability arm; DFlash2 not owed. `recipes/ornith/zz-ornith-1.5-122b-nvfp4-mtp-vllm.yaml`; receipts `~/benchmarks/tplt4-20261024/ornith122b/` |
| 6. Spark-X2.6-4B remaining open cells (tool-call contract + clamp ladder) | one node | tplt4-research | **DONE 2026-10-25 on `.30`** — tool-call contract **PASS 3/3** (`get_weather({"city":"Lisbon"})`, temp 0); clamp cell **negative** (c32 294.5 / c48 272.2 / c64 291.9 / c96 294.7 — flat, keep 32); the "MTP" half resolved by absence (no draft head/repo) with **NGRAM measured-rejected** (slower at every rung, falsifier fired). Receipts `~/benchmarks/tplt4-20261024/sparkx26/` |
| 7. kokoro-shaped recipe arm (phonon) | one node | tplt4-research | **DONE 2026-10-25** — `recipes/media/phonon-31m-tts-cpu.yaml` + `recipes/media/mods/phonon-tts-server/` boot-verified on `.35` (TTR 8.2 s, RTF 0.10–0.14), root README index row added; guards caught the first draft (mods ref form + inert default) and the fix is in. Receipts `~/benchmarks/tplt4-20261024/phonon-arm/` |

## Landed this session

| time ET | commit | one clause |
|---|---|---|
| 22:29 10-24 | `45d085e` | board refresh 2026-10-24 22:29 ET (all six nodes 0 containers) |
| 22:49 10-24 | `31a595b` | board fix: `.30` is a full member; window-3 and tplt4 boots live |
| 22:51 10-24 | `731f651` | sweep of the stale `.30` reservation framing out of the docs |
| 22:57 10-24 | `33a987d` | tplt4 closes its two cells: Bonsai Q2_0 passes the easy-traffic gate on a quiet `.35` (C1 75.51 ± 1.38 / C10 129.79 ± 0.90, house 36/37) and the kokoro-vs-phonon hard-sentence WER A/B lands (phonon 0.1747 vs kokoro 0.2329) |
| 22:57 10-24 | `ca7dee0` | board Recently-landed row for `33a987d` |
| 23:01 10-24 | `3a1e6d9` | tplt4: Bonsai quiet-node C2/C5 corrected to the receipt (129.24 ± 0.76 / 151.95 ± 1.21) and the five-stream peak shape stated |
| 23:05 10-24 | `8448b4c` | ornith `zz-ornith-1.5-122b-nvfp4-mtp-vllm.yaml` — the 122B MTP spec-decode probe (cell 4, pre-registered), `--speculative-config` via placeholder |
| 23:10 10-24 | `846328a` | seven board jobs unparked into the `TODO.md` retry queue (owner directive) |
| 23:10 10-24 | `37bcf03` | restore of `zz-ornith-1.5-122b-nvfp4-mtp-vllm.yaml` — a stale shared index had recorded a phantom deletion in `846328a` |
| 23:21 10-25 | `cc81898` | board restructured to the owner's three-table spec (In flight / Work queue / Landed this session), history swept |
| 23:16 10-25 | `57543db` | ornith MTP: `--speculative-config` placeholder single-quoted (boot3's stripped double quotes reached argparse) |
| 23:13 10-25 | `10fb558` | ornith MTP: speculative-config JSON quoted inside the command template (boot2's bash-strip failure) |
| 23:2x 10-25 | `e5997ca` | board reconciliation: Beam staging verified DONE 63/63 (`dl-beam.log` tail), queue row 3 state flipped |
| 00:51 10-26 | `d8b31c4` | board refresh: In-flight reduced to the fresh census + the live phonon boot, stale GLM/ornith/Beam rows swept |
| 00:52 10-26 | `47de13f` | wording fix: `.30` idleness stated as "nothing live (no reservation)", role-based framing removed |
| 00:55 10-26 | `3aef0f9` | Beam quartet boot row landed (the tp4-window3 ordered boot) |
| 01:2x 10-26 | `2584701` | **tplt4 round 2 lands**: Ornith-122B MTP cell (+44 % C1 paired), Spark-X2.6 tool-call PASS + clamp negative + NGRAM rejected, phonon-31m-tts-cpu arm boot-verified + indexed; `d767a07` is the gate-green phonon recipe fix (guards + suite BEFORE push) |
