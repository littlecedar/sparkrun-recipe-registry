# mad-science/

Research notes that trace claims and record experiments — not recipes, not shipped config. Nothing
in this directory is served by the registry and nothing here changes a launch; each file is a
self-contained note with its own status line and date. Kept because the *reasoning* (what a claim
was, why it does or does not transfer, what was measured) is not recoverable from the code it
influenced.

Evidence vocabulary is shared across the directory: **VERIFIED** = read from a primary artifact or
measured here; **LIKELY** = strong secondary evidence; **SPECULATIVE** = reasoning without a source.
A file states its own scope in its first lines — read that before quoting a number out of it.

## Index

| file | what it covers |
|---|---|
| [`CUSTOM_ALL_REDUCE_SM120_EXPERIMENTS.md`](CUSTOM_ALL_REDUCE_SM120_EXPERIMENTS.md) | Traces the "free 5% on TP=4" CustomAllReduce tip to its SM120 single-node, PCIe-P2P origin, shows why it is a category error on the `ds4` lane (**four nodes**, TP across nodes over RoCE, where SGLang disables custom all-reduce by design and RoCEnante already fills the role), and lists the experiments actually worth running (RoCEnante coverage sweep, crossover curve). |
| [`RESEARCH_LORE.md`](RESEARCH_LORE.md) | Mined from the git-ignored `.swival/` work corpus: sparkrun recipe grammar and placeholder resolution, CLI/dry-run mechanics, mod failure modes, env/portability/distribution, SGLang and vLLM flag semantics, checkpoint and model-path layout, measurement discipline, guard conventions, and a register of claims that are now stale. The long-form evidence behind the one-line rules in [`../AGENTS.md`](../AGENTS.md). |
| [`EXPLORE-CANDIDATES.md`](EXPLORE-CANDIDATES.md) | The `explore` lane's frontier reasoning+tool-calling candidates (2026-10-10 scan): ten models ranked by the owner's four priorities, with license, quant availability, fit arithmetic and DGX-Spark precedent flags; six have verified third-party Spark precedents, and the owner-decision blockers (MiniMax-M3 license, missing MiMo quant) are named. |
| [`KNAPCIO-UPSTREAM-DELTA.md`](KNAPCIO-UPSTREAM-DELTA.md) | The ds4 lane's upstream-delta memo (2026-10-10): our pin `58f2321` IS knapcio's v2.3 release commit; only two docs-only commits follow it, none touching code — no image rebuild warranted, two defer-able experiment ideas recorded. Corrects an earlier scan's "upstream moved past our pin" premise. |
| [`STORAGE-POLICY.md`](STORAGE-POLICY.md) | The registry's storage positions (2026-10-15): sparkrun's runtime-cache prune path **demonstrated** (`sparkrun setup prune-runtime-cache`, the launch-time sibling sweep, and the leaf-key identity that splits a live tree from a superseded one where `modlogs/` cannot), the per-node cache budget (runtime-cache ≤ 0.5 TB, HF ≤ 2.2 TB, ≥ 1.0 TB free) with its derivation and enforcement, the key-verified reclaim list with sizes and marker ages, and the Qwen3.8-27B three-pack license verdicts (all Apache-2.0; **no** small sidecar exists — the three packs are three different quantisations). |
| [`LLAMACPP-GGUF.md`](LLAMACPP-GGUF.md) | The llama.cpp runtime on GB10 (2026-10-17): the pinned `scitrera/dgx-spark-llama-cpp` tier and what the image actually contains (engine build, flag surface, no `rpc-server`), the stock-loadable GGUF arch map with the two fork-only archs named, the plumbing facts that decide a GGUF recipe (`:quant` suffix, `-hf`→`-m` rewrite, `--kv-unified` with explicit `--parallel`), and the standing policy for when a GGUF sibling may stand in for a safetensors arm. |

None of these notes is authoritative over the
shipped `recipes/`, `mods/`, or `benchmarking/` docs — where they disagree, the shipped doc wins.
