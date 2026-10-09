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

The directory is listed in [`../AGENTS.md`](../AGENTS.md). Neither note is authoritative over the
shipped `recipes/`, `mods/`, or `benchmarking/` docs — where they disagree, the shipped doc wins.
