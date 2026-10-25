# mad-science/

Research notes that trace claims and record experiments — not recipes, not shipped config. Nothing
in this directory is served by the registry and nothing here changes a launch; each file is a
self-contained note with its own status line and date. Kept because the *reasoning* (what a claim
was, why it does or does not transfer, what was measured) is not recoverable from the code it
influenced.

Evidence vocabulary is shared across the directory: **VERIFIED** = read from a primary artifact or
measured here; **LIKELY** = strong secondary evidence; **SPECULATIVE** = reasoning without a source.
A file states its own scope in its first lines — read that before quoting a number out of it.

None of these notes is authoritative over the shipped `recipes/`, `mods/`, or `benchmarking/` docs —
where they disagree, the shipped doc wins.

## Master locator

Every research-bearing document in the registry, one row each. **Where is the prior research on X**
starts here, not in a lane README. Classes: **live research** = an argument still being added to;
**standing record** = the long-form provenance behind a rule that ships; **standing policy** = a
position the programme holds; **register** = the queue/board/history of record; **agent guidance** =
the rules and long-form evidence an agent works under in this directory; **archived** = kept for
provenance, not live.

Dates in *last updated* are the newest date the document itself states (its status line or its latest
entry) — never an mtime, and `—` where the file states none.

### `mad-science/` — live research, policy and the registers

| doc | class | what it is | last updated |
|---|---|---|---|
| [`AGENTS.md`](AGENTS.md) | agent guidance | The agent-facing companion to this README: the register protocol, the long-form evidence digest behind the root [`../AGENTS.md`](../AGENTS.md) one-liners (recipe grammar, CLI and launch mechanics, mod authoring, env/portability/distribution, SGLang and vLLM flag semantics, checkpoint paths, measurement discipline, guard conventions), the stale-claims list, and the known-stale flags for quoting attic docs. | — |
| [`DEEPSEEK.md`](DEEPSEEK.md) | live research | All DeepSeek-V4.1-Flash research in one document: the knapcio TP=4 1M SGLang stack end to end (upstream provenance and post-pin delta, image build and the byte-reproducibility verdict, the overlay launcher and who owns which value, the measured ladders, accuracy legs, every failed attempt with its mechanism, the 1M prefill-chunk arithmetic), then the TensorFold EXL3 TP=2 line, the TP=2-vs-TP=4 comparison, the TP=1 byte wall and the ranked candidate survey. Absorbed `KNAPCIO-UPSTREAM-DELTA.md`, `DEEPSEEK-1017-DECODE-RESEARCH.md`, `DS4-SPEEDUPS.md`. | 2026-10-24 |
| [`DSV4PRO-FEASIBILITY.md`](DSV4PRO-FEASIBILITY.md) | live research | The DeepSeek-V4-Pro-0813 (1.65T/49B `deepseek_v4`) feasibility pass: the 13-repo quant census condensed, the fleet envelope, a fit table for every whole-model artifact with per-rank bytes at TP=4/6 and verdicts (three sub-2-bpw GGUF tiers fit TP4 bytes-wise via a llama.cpp RPC route that needs a self-built image; the EXL3 pair is engine-blocked; everything ≥622 GiB is impossible on six nodes), the resolved llama.cpp multi-node answer with citations, and a ranked feasibility list with falsifiers and boot gates. | 2026-10-24 |
| [`BEEGFS-REPORT.md`](BEEGFS-REPORT.md) | live research | The BeeGFS-as-shared-HF-cache question in one document: cost, measured hardware and Engram demand, inter-node transfer shapes, the fetch-once fan-out rule, the two-node pilot (§10), fleet activation, the completed HF-cache migration, and what the WOPR cluster profile now does with model distribution. **Adopted**: the cache lives entirely on the pool; boot-time persistence is the open cell. | 2026-10-24 |
| [`FLARE.md`](FLARE.md) | live research | The FLARE `gb10` package and its install decision: what `flare agent` is and the six-way "FLARE" identity split, the runtime package's shape and `.deb`/`APT` facts, why containerization is possible yet was not the route, the two-node authorization ask, the per-artifact grant table and the preconditions. Read-only: nothing installed, no node contacted. | 2026-10-24 |
| [`CUSTOM_ALL_REDUCE_SM120_EXPERIMENTS.md`](CUSTOM_ALL_REDUCE_SM120_EXPERIMENTS.md) | live research | Traces the "free 5% on TP=4" CustomAllReduce tip to its SM120 single-node PCIe-P2P origin, shows why it is a category error on the `ds4` lane (four nodes, TP across nodes over RoCE, where SGLang disables custom all-reduce by design and RoCEnante already fills the role), and lists the experiments actually worth running. | 2026-10-03 |
| [`RESEARCH_LORE.md`](RESEARCH_LORE.md) | distributed — deleted 2026-10-24 | Its mechanical facts moved into [`../recipes/MECHANICS.md`](../recipes/MECHANICS.md) (§1/§2/§4–§7: grammar, CLI mechanics, env/portability, SGLang and vLLM flag semantics, checkpoint paths), its mod-failure modes and guard/measurement discipline into [`../AGENTS.md`](../AGENTS.md) and [`../benchmarking/README.md`](../benchmarking/README.md) (§3/§8/§9). Verbatim text preserved in git history at the commit that deleted it. | 2026-10-24 |
| [`STORAGE-POLICY.md`](STORAGE-POLICY.md) | standing policy | The registry's storage positions: sparkrun's runtime-cache prune path demonstrated, the per-node cache budget with its derivation and enforcement, the key-verified reclaim list, and the Qwen3.8-27B three-pack license verdicts. | 2026-10-17 |
| [`LLAMACPP-GGUF.md`](LLAMACPP-GGUF.md) | standing policy | The llama.cpp runtime on GB10: the pinned image tier and what it actually contains, the stock-loadable GGUF arch map with the two fork-only archs named, the plumbing facts that decide a GGUF recipe, and the standing policy for when a GGUF sibling may stand in for a safetensors arm. | 2026-10-22 |
| [`GGUF-VIABILITY-TRIAGE.md`](GGUF-VIABILITY-TRIAGE.md) | live research | The owner round-5 §5 per-candidate GGUF viability triage: standing lessons (pool-residency as a logistics line after the migration dedup, the `a37cc4610` ref floor, the pool-era launch route), a candidate table with engine-gate and expected-benefit verdicts (one conversion warranted — qwen3.8 `spark2_5` official Q4_K_M; JEV clone not viable without an `allowed_token_ids` surface; Ornith measured-rejected; GLM/ds4 not viable), and the window-4 baseline boot receipts (Sol-2B decision2 ladder, first Ternary-Bonsai decode rows, the shipped Mellum plain arm). | 2026-10-26 |
| [`DRAFTER-ALTERNATIVES-1026.md`](DRAFTER-ALTERNATIVES-1026.md) | live research | The owner round-4 §7 drafter-alternatives survey: what each arm runs today, the DFlash/DSpark/DLoop/EAGLE/Medusa families with engine-support facts (`sglang#30261` DSpark ragged verify, Spec-V2 default, `dev-dspark` image), the weights-availability gate that actually decides adoption, the registry's own negative ngram/UNO-tree precedent, and the concrete next boot (ds4 engine post-`#30261` DSpark check). | 2026-10-26 |
| [`STATUS.md`](STATUS.md) | register | The board: dated fleet census, gate/baseline/foundation rows, the `Now` owner table, the standing traps-and-rules list, measurements, and the recently-landed commit log. **State** — read first, cite last. | 2026-10-24 |
| [`TODO.md`](TODO.md) | register | The work register and its protocol: open work by lane and registry-level area, the owner↔agent planning-round interface, and §"Settled questions" holding answered questions verbatim with their numbers intact. **Work**, never open questions. | 2026-10-24 |
| [`QUESTIONS.md`](QUESTIONS.md) | register | The register of **unresolved** owner questions — one row each with `path:line` provenance and asked date, grouped by subject, topped by a summary naming the row that blocks the most downstream work. Settled rows move to `TODO.md` with their numbers, so `QUESTIONS.md #N` keeps resolving. | 2026-10-24 |
| [`SESSION-RECORD.md`](SESSION-RECORD.md) | register | Session history moved out of `TODO.md`: dated narrative per session — what ran, what was verified, what landed, what was left open. **History**: the long-form "how we got here". | 2026-10-24 |
| [`../attic/ds4/DS4-CANDIDATES.md`](../attic/ds4/DS4-CANDIDATES.md) | archived (moved from `mad-science/` 2026-10-24) | The 2026-10-24 survey of quant/engine variants of DeepSeek-V4.1-Flash-1017 that could become a TP=4 arm beyond the shipped knapcio SGLang arm and the TensorFold TP=2 pair. Read-only, no boot; proposes candidates for the next window. | 2026-10-24 |
| [`../attic/explore/EXPLORE-CANDIDATES.md`](../attic/explore/EXPLORE-CANDIDATES.md) | archived (moved from `mad-science/` 2026-10-24) | The original 2026-10-10 explore-lane scan: frontier reasoning+tool-calling candidates ranked by the owner's four priorities, with license, quant availability, fit arithmetic and Spark-precedent flags. Partly superseded by [`EXPLORE-MODELS-RESEARCH.md`](../attic/explore/EXPLORE-MODELS-RESEARCH.md), which corrects five of its claims. | 2026-10-21 |
| [`../attic/qwen4/QWEN4-DIAGNOSTICS.md`](../attic/qwen4/QWEN4-DIAGNOSTICS.md) | archived (moved from `mad-science/` 2026-10-24) | The qwen4 lane's two carried engine issues root-caused with `file.py:line`: the shared-expert `.weight_scale` vs `.weight_scale_inv` naming blocker and the QSA-prefill CUDA-graph crash, plus the observables that confirm each on a boot. | 2026-10-21 |

### `attic/` — archived lane evidence

Each lane directory under [`../attic/`](../attic/) holds what left `recipes/<lane>/` when the lane was
consolidated: research records, guides, arm manifests and status memos. The index of a lane's arms is
its `ARMS-MANIFEST.md`; the lane's durable findings are its `AGENTS.md`.

| doc | lane | what it is | last updated |
|---|---|---|---|
| [`../attic/ds4/AGENTS.md`](../attic/ds4/AGENTS.md) | ds4 | The lane's durable guide, absorbing `DS4-MODEL-OPTIMIZATION-WORK.md`, `JOURNAL.md` and the old recipe header comments: invariants, shipped-suite history, boot/tuning findings, mod and guard conventions, and the trap list. | 2026-10-22 |
| [`../attic/ds4/README.md`](../attic/ds4/README.md) | ds4 | Why the EXL3/vLLM material is archived and what replaced it (the knapcio SGLang go-live recipe), with the arm inventory and the rename history. | 2026-09-27 |
| [`../attic/ds4/NOTES.md`](../attic/ds4/NOTES.md) | ds4 | ds4 work notes: the combined local HF repo built for the TensorFold TP=2 lane, what ships in it, and the ledger cleanup. | 2026-10-11 |
| [`../attic/ds4/ds4_NOTES.md`](../attic/ds4/ds4_NOTES.md) | ds4 | Session log for the lane (durable facts graduate into `AGENTS.md`/`README.md`; the file is pruned): retunes, launcher/env probe traps, checkpoint resolution. | 2026-10-22 |
| [`../attic/ds4/PERF-ISSUES.md`](../attic/ds4/PERF-ISSUES.md) | ds4 | Triage of the `-exl3-tp6-1m-vllm` collapse under `spark-arena-v2`, ending in the resolved mechanism (a cold deep prefill) and the finding that no knob examined gives a clean win. | 2026-10-02 |
| [`../attic/ds4/DSPARK-TP3-STUDY.md`](../attic/ds4/DSPARK-TP3-STUDY.md) | ds4 | Feasibility study for DSpark at TP=3/TP=6 with unaligned drafter divisors: verdict feasible, one ~25-line design, implemented and booted. | 2026-09-27 |
| [`../attic/ds4/MEMORY-RECLAIM-PLAN.md`](../attic/ds4/MEMORY-RECLAIM-PLAN.md) | ds4 | Memory-reclaim recommendation and action plan: the InstantTensor question closed, cache drops ruled out, and the bounded-reader fix named as the only viable route. | 2026-09-27 |
| [`../attic/qwen4/AGENTS.md`](../attic/qwen4/AGENTS.md) | qwen4 | The Qwen3.8-Flash-Next lane's entry-point guide: current state, the constraints that bite, and the action plan split into parallel workstreams (long-form evidence is in the git-ignored WORK doc it cites). | 2026-10-22 |
| [`../attic/qwen4/NOTES.md`](../attic/qwen4/NOTES.md) | qwen4 | One-page kept-current state-of-play for the lane; durable guidance is `AGENTS.md`, the long form is the archive. | 2026-10-18 |
| [`../attic/qwen4/ARMS-MANIFEST.md`](../attic/qwen4/ARMS-MANIFEST.md) | qwen4 | Every qwen4 recipe outside the production surface, tracked because a `bench_*` id is the provenance of a result, each with why it is archived. | 2026-10-22 |
| [`../attic/qwen4/SELECTION-RANKING.md`](../attic/qwen4/SELECTION-RANKING.md) | qwen4 | The durable selection ranking across the lane's arms under the owner's four priorities, with provenance keys into the READMEs and the ds4 guide. | 2026-10-14 |
| [`../attic/qwen4/status/W8-UPSTREAM-DRAFTS.md`](../attic/qwen4/status/W8-UPSTREAM-DRAFTS.md) | qwen4 | Workstream W8: verified upstream engagement status plus ready-to-post drafts — drafts only, nothing posted, no agent-executable action. | 2026-10-04 |
| [`../attic/qwen4/status/W4-GATE-STATUS.md`](../attic/qwen4/status/W4-GATE-STATUS.md) | qwen4 | Workstream W4 one-pager on the `#37111` silent-decode-corruption gate: what is done, smoked live, and still owed. | 2026-10-18 |
| [`../attic/qwen4/status/W3-QUALITY-EVAL-STATUS.md`](../attic/qwen4/status/W3-QUALITY-EVAL-STATUS.md) | qwen4 | Workstream W3 one-pager: quality-eval results for the labquant export from the live paired run, and the caveats on reading them. | 2026-10-14 |
| [`../attic/qwen4/status/W3-QUALITY-EVAL-PLAN.md`](../attic/qwen4/status/W3-QUALITY-EVAL-PLAN.md) | qwen4 | Workstream W3 plan: what the fixed version-controlled battery measures and the provenance each claim must carry. | — |
| [`../attic/qwen4/status/W14-LABQUANT-5500-MOD-PLAN.md`](../attic/qwen4/status/W14-LABQUANT-5500-MOD-PLAN.md) | qwen4 | Analysis-only plan for re-verifying the 7-mod chain against the labquant step-5500 upgrade, with the target revision corrected from live Hub headers. | 2026-10-10 |
| [`../attic/qwen3/AGENTS.md`](../attic/qwen3/AGENTS.md) | qwen3 | The maintained lane guide, `§N` numbering unchanged; it states its own rule that where it disagrees with a `§N` in the archive, the archive holds the evidence. | 2026-10-15 |
| [`../attic/qwen3/NOTES.md`](../attic/qwen3/NOTES.md) | qwen3 | The lane's entry point: current state, the constraints that bite, the workstream action plan and the coordination mechanism. | 2026-10-15 |
| [`../attic/qwen3/ARMS-MANIFEST.md`](../attic/qwen3/ARMS-MANIFEST.md) | qwen3 | The arms and records that left `recipes/qwen3/` in the 2026-10-11 consolidation, with why each is archived and which paths elsewhere must keep resolving. | 2026-10-15 |
| [`../attic/qwen3/DEPTH-COST.md`](../attic/qwen3/DEPTH-COST.md) | qwen3 | The depth-cost investigation (§12.22–12.52): what a deeper context tier costs and buys on a single Spark — the doctrine behind the measurement discipline. | 2026-09-23 |
| [`../attic/qwen3/SSM-STATE-DTYPE.md`](../attic/qwen3/SSM-STATE-DTYPE.md) | qwen3 | Whether `mamba_ssm_dtype: bfloat16` changes the model's outputs — the state-dtype numerics thread, with its six probes and the nulls reported where they occur. | 2026-09-21 |
| [`../attic/qwen3/ANSWERED-QUEUES.md`](../attic/qwen3/ANSWERED-QUEUES.md) | qwen3 | Closed experiments relocated out of the lane's open queue with their answers, so nothing already paid for gets re-run — search it by profile name before queueing. | 2026-09-22 |
| [`../attic/explore/AGENTS.md`](../attic/explore/AGENTS.md) | explore | The lane's working notes: measured histories, selection receipts, serving traps and per-arm research — everything that is not a shipped recipe. | 2026-10-22 |
| [`../attic/explore/ARMS-MANIFEST.md`](../attic/explore/ARMS-MANIFEST.md) | explore | Every explore recipe outside the lane's 2026-10-19 Pareto set plus the earlier archives, with the selection rationale per arm. | 2026-10-22 |
| [`../attic/explore/QWEN-IMAGE.md`](../attic/explore/QWEN-IMAGE.md) | explore | Bring-up notes for the Qwen-Image-2.1-Turbo media-gen arm, opening with its non-commercial license banner and the owner's ship-with-banner call. | 2026-10-22 |
| [`../attic/explore/LTX-25.md`](../attic/explore/LTX-25.md) | explore | LTX-2.5 media-gen lane notes: a ComfyUI runbook rather than a sparkrun recipe, the gated access prerequisite, and the acceptance criterion. | 2026-10-18 |
| [`../attic/explore/MELLUM-21.md`](../attic/explore/MELLUM-21.md) | explore | Per-arm record for Mellum2.1-12B-A2.5B-Thinking: why it exists (owner-added, outside the ranked list), what was read at the pin, and the boot result. | 2026-10-15 |
| [`../attic/explore/EXPLORE-MODELS-RESEARCH.md`](../attic/explore/EXPLORE-MODELS-RESEARCH.md) | explore | The lane's ranked candidate research: corrects five claims of `EXPLORE-CANDIDATES.md`, adds four families, and separates third-party GB10 measurements from vendor card numbers. Fit arithmetic is Hub blob sums, not boots. | 2026-10-18 |
| [`../attic/decision/AGENTS.md`](../attic/decision/AGENTS.md) | decision | Durable non-catalogue notes for the decision lane (small classification/routing/judgment models), moved out of the lane README. | 2026-10-19 |
| [`../attic/decision/DECISION-MODELS-RESEARCH.md`](../attic/decision/DECISION-MODELS-RESEARCH.md) | decision | Read-only candidate research for the lane under its core constraint: co-location with the shipped embed + rerank pair on one node, with receipt URLs inline and `[INFERENCE]` marked. | 2026-10-19 |
| [`../attic/glm/AGENTS.md`](../attic/glm/AGENTS.md) | glm | GLM 5.3 runbook notes and the revision pins, moved verbatim out of the lane README (the lane ships no recipe). | 2026-10-14 |
| [`../attic/glm/ARMS-MANIFEST.md`](../attic/glm/ARMS-MANIFEST.md) | glm | The archived GLM-5.3-Flash DFlash arm recorded as a proven-negative on the pinned public image, with the mechanism and the receipt pointers. | 2026-10-14 |
| [`../attic/glm/GLM-5.3-RECOMMENDATIONS.md`](../attic/glm/GLM-5.3-RECOMMENDATIONS.md) | glm | Which GLM-5.3 checkpoints, engines, node counts, context and draft strategy to build for the cluster; supersedes its earlier version and names the three facts that version got wrong. | 2026-10-11 |
| [`../attic/ifm/AGENTS.md`](../attic/ifm/AGENTS.md) | ifm | The IFM K2-Horizon lane guide: state, constraints and guards — and the note that the deep WORK/JOURNAL records it names are git-ignored and absent from this tree. | 2026-10-22 |
| [`../attic/ifm/NOTES.md`](../attic/ifm/NOTES.md) | ifm | Tracked working notes for the lane; with the deep records absent, the numbers that matter are folded into these dated sessions. | 2026-10-18 |
| [`../attic/ifm/ARMS-MANIFEST.md`](../attic/ifm/ARMS-MANIFEST.md) | ifm | The withdrawn MoVA-36B sub-lane, the retired 7B spec-decode arms and the measured-rejected UNO tree-mode probe, wave by wave, with what each still needs. | 2026-10-19 |
| [`../attic/ornith/AGENTS.md`](../attic/ornith/AGENTS.md) | ornith | The Ornith 1.5 lane guide: state, constraints and traps for serving the agentic-coding family. | 2026-10-22 |
| [`../attic/ornith/NOTES.md`](../attic/ornith/NOTES.md) | ornith | Staged cluster work: plans authored off-cluster with acceptance criteria and boot commands — prior receipts, not new measurements. | 2026-10-19 |
| [`../attic/cybersec/AGENTS.md`](../attic/cybersec/AGENTS.md) | cybersec | The lane's operating guide, opening with the gating/token prerequisite and the policy that is not ordinary sparkrun engineering. | 2026-10-22 |
| [`../attic/embed/AGENTS.md`](../attic/embed/AGENTS.md) | embed | The lane's research record: cross-lane facts and the per-recipe serving contract, cut from the lane README so it could speak to shipped recipes only. | 2026-10-18 |
| [`../attic/rerank/AGENTS.md`](../attic/rerank/AGENTS.md) | rerank | Retired lane material: state, constraints, guards, knob rationale, negative results and the 8B variant's measurement. | 2026-10-15 |
| [`../attic/DONE.md`](../attic/DONE.md) | register (archive) | Every completed item archived verbatim from `TODO.md`, sweep by sweep, with the owner-decision notes it carried. The closing record of what was paid for. | 2026-10-24 |
| [`../attic/PRIMARY-README-ARCHIVE.md`](../attic/PRIMARY-README-ARCHIVE.md) | archived | The research and lane-state prose removed from the root `README.md` when it became a pure index; its quoted blocks keep README-relative links that do not resolve from here (the file says so itself). | 2026-10-14 |

## Orientation: which file first

| the question | read |
|---|---|
| What is the fleet doing now, and what is the gate? | [`STATUS.md`](STATUS.md) |
| What is open to work on / what did the owner already decide? | [`TODO.md`](TODO.md) → [`QUESTIONS.md`](QUESTIONS.md) |
| Why does an `../AGENTS.md` rule exist? What is the evidence behind it? | [`../AGENTS.md`](../AGENTS.md) — the rule text is the contract; the long-form evidence and mining provenance live in git history (`RESEARCH_LORE.md`, deleted 2026-10-24 on distribution into [`../recipes/MECHANICS.md`](../recipes/MECHANICS.md), [`../benchmarking/README.md`](../benchmarking/README.md) and the lane docs) |
| Anything DeepSeek-V4.1-Flash: engines, TP shapes, what failed and why | [`DEEPSEEK.md`](DEEPSEEK.md) → [`../attic/ds4/AGENTS.md`](../attic/ds4/AGENTS.md) → [`../recipes/ds4/README.md`](../recipes/ds4/README.md) |
| Why CustomAllReduce / RoCEnante / comm backends behave as they do on this fabric | [`CUSTOM_ALL_REDUCE_SM120_EXPERIMENTS.md`](CUSTOM_ALL_REDUCE_SM120_EXPERIMENTS.md) |
| Storage, cache budgets, reclaim, shared-pool rules | [`STORAGE-POLICY.md`](STORAGE-POLICY.md) + [`BEEGFS-REPORT.md`](BEEGFS-REPORT.md) |
| GGUF / llama.cpp viability: which archs load, what the image carries | [`LLAMACPP-GGUF.md`](LLAMACPP-GGUF.md) |
| Whether to install or containerize a third-party package (and the FLARE decision) | [`FLARE.md`](FLARE.md) |
| Was this model already tried, and what did it score? | the lane's [`ARMS-MANIFEST.md`](../attic/) → [`../attic/DONE.md`](../attic/DONE.md) → [`SESSION-RECORD.md`](SESSION-RECORD.md) |
| Which candidates remain uncooked in a lane | [`../attic/explore/EXPLORE-MODELS-RESEARCH.md`](../attic/explore/EXPLORE-MODELS-RESEARCH.md), [`../attic/decision/DECISION-MODELS-RESEARCH.md`](../attic/decision/DECISION-MODELS-RESEARCH.md), [`../attic/ds4/DS4-CANDIDATES.md`](../attic/ds4/DS4-CANDIDATES.md) |
| Why an archived lane ships nothing / why an arm is not in `recipes/` | that lane's `attic/<lane>/README.md`, `AGENTS.md` or `ARMS-MANIFEST.md` |

Agent-facing rules — the register protocol, the long-form evidence digest, stale claims and the
known-stale flags — live in [`AGENTS.md`](AGENTS.md).
