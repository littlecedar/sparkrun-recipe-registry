# QUESTIONS — the register of owner questions (2026-10-22)

Every question this programme is holding for the owner lives here, one row each, with the provenance
that raises it; `TODO.md` holds work, not questions, and a decision is recorded where it was taken.

| summary | value |
|---|---|
| unanswered | **14** — 12 answerable now, 2 blocked on a boot no window has run (`#3`, `#7`); counted from the status column, `answered` rows excluded |
| blocks the most downstream work | **`#4`** — whether the TP=4 queue may run on `.30`–`.33` at all decides the ds4 upgrade candidates, the four-node suite legs, the one-engine topology A/B and every four-node artifact probe |

## Baseline & gate

| # | question | status | why it matters | provenance | asked |
|---|---|---|---|---|---|
| 1 | Should the easy-traffic gate's non-decreasing C5→C10 leg disqualify an arm whose ten-slot C10 clears the absolute bar by 60 % but whose throughput genuinely peaks at five streams? | open | Decides whether Mellum2.1 — the only candidate that clears both absolute bars — ships as the single-node easy-traffic arm, and so the verdict of every later candidate judged against the gate. | `mad-science/TODO.md:88-90` (leg itself `:54-62`; duplicate `mad-science/STATUS.md:42`) | 2026-10-22 |
| 2 | Is a quartet boot worth spending on a larger 1M prefill chunk than the shipped 8192? | open | The measured 1.67× 1M penalty is chunk-launch-bound rather than compute- or bandwidth-bound, so the chunk size is the only lever left on 1M prefill throughput. | `mad-science/STATUS.md:33` | 2026-10-22 |
| 3 | Will a quartet window be scheduled for one engine booted at both TP=2 and TP=4 in interleaved A/B slots? | blocked on hardware | Every published TP=2-vs-TP=4 ratio in the DeepSeek family compares two different engines and quants at once; without the window the family has no controlled topology number. | `mad-science/DEEPSEEK-1017-DECODE-RESEARCH.md:234-236` (bound stated `:20-22`) | undated |

## Hardware & authorization

| # | question | status | why it matters | provenance | asked |
|---|---|---|---|---|---|
| 4 | May the ds4 TP=4 upgrade candidates and the four-node suite legs run on `.30`–`.33` while those ranks serve the fleet's own inference, or does the workload fence hold until the serve is stood down? | open | It is the gate on the whole TP=4 queue — the ds4 candidates, the four-node suite legs, the `#3` topology A/B, and every four-node artifact probe — and the record currently carries both instructions. | `mad-science/TODO.md:552` + `mad-science/TODO.md:290` (queue) against `AGENTS.md:239-250` (fence) and `mad-science/STATUS.md:19` (the serve occupying those ranks) | 2026-10-22 |
| 5 | Should the two-node BeeGFS pilot be run to settle adoption, or does the "not now" verdict stand unaudited? | open | The pilot's three numbers are the prerequisites of any adoption decision, none has been taken, and a shared cache would change every lane's fetch and residency arithmetic. | `mad-science/BEEGFS-REPORT.md:228-239` (verdict `:194-214`) | 2026-10-20 |
| 6 | May a third-party APT repository and a per-host `flare agent` service be installed on four nodes to evaluate the FLARE `gb10` package? | open | It is the only artifact seen whose target is this lane's exact shape (four Sparks, TP4, c16, 1M context), and it cannot be served at all without that supply-chain step. | `mad-science/TODO.md:423-425` | 2026-10-22 |
| 7 | Is a four-rank MiniMax-H3 video cell authorized on `.30`–`.33`? | blocked on hardware | The 33.12 B DiT's per-step activation exchange may need TP=2 or TP=4, and a four-rank cell would displace the fleet's production serve for its whole wall time. | `mad-science/TODO.md:2243` | 2026-10-22 |
| 8 | Which host becomes the arm64 self-hosted runner for the llama.cpp build job? | open | No runner is registered, so the weekly job never builds and the stock-upstream image work and the Mellum MTP A/B stay unstartable. | `mad-science/TODO.md:2409` | 2026-10-22 |

## Engine & pin policy

| # | question | status | why it matters | provenance | asked |
|---|---|---|---|---|---|
| 9 | Should the silent `DSV41_MXFP8_BACKEND=b12x` override be repaired — a launcher assertion rather than a value that never reaches the engine — or stay recorded-only? | open | The shipped ds4 arm requests a backend the engine never receives, so any future MXFP8 A/B measures `auto` and reads as a null result. | `mad-science/STATUS.md:34` | 2026-10-22 |
| 10 | Should the repository Issues tracker be enabled so the nightly pin-drift sweep can maintain its issue in place? | open | Without it the drift signal is the run summary plus a 90-day artifact only, and there is no single updated row to read. | `AGENTS.md:491-495` | undated |

## Licences & shipping

| # | question | status | why it matters | provenance | asked |
|---|---|---|---|---|---|
| 11 | May the registry ship an eval-only arm for MiniMax-M3 under its non-commercial Community License, or is that licence a hard no for a tree distributed to third parties? | open | It is the highest accuracy-per-node candidate at two nodes, so the licence decides whether it can exist here at all. | `mad-science/EXPLORE-CANDIDATES.md:53-54` (duplicate `:75`) | undated |
| 12 | Should the cybersec lane ship a single-node OrcaCyber-Nano-1.0 arm, and at which GGUF tier? | open | The two tiers trade ~2.5 GB of bytes against quality and the model's only engine is llama.cpp, so the tier is a ship decision rather than a bench result. | `mad-science/TODO.md:2004-2006` | 2026-10-22 |
| 13 | Which look does the shipped image arm serve — the current Diffusers render, or is the declined vLLM-OMNI variant reopened? | open | The two routes produce different pictures at the same seed, and the prompt-adherence review deliberately does not choose between them. | `mad-science/TODO.md:1153-1155` | 2026-10-21 |
| 14 | Does the MiniMax H3 Community Licence permit this cluster to run the arm? | answered 2026-10-22 | Settles the boot location: permitted at a non-US site by deployment location, not permitted at a US site. | `mad-science/TODO.md:2229`, `recipes/media/README.md:310-314` | 2026-10-22 |
| 15 | Do the Timestral and indra-ocr modified licences block shipping their arms? | answered 2026-10-22 | Both banners are accepted and ship inside the recipes; the remaining gap is the runtime, not permission. | `mad-science/STATUS.md:32` | 2026-10-22 |

## Operations

| # | question | status | why it matters | provenance | asked |
|---|---|---|---|---|---|
| 16 | Is a rewrite of git history authorized to purge the cluster-internal addresses that the tree-level sweep masked? | open | 221 patch-body lines and 8 commit-message lines still carry fabric addresses in a registry distributed to third parties. | `mad-science/TODO.md:2582-2590` | 2026-10-20 |