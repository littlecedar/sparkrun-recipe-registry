---
name: sparkrun-revision-pin-survey
description: "Survey sparkrun recipe-pinned HF checkpoint revisions against the per-node cache + Hub main, then add re-pin/re-bench tasks to the lane TODOs"
---

# Survey pinned HF revisions against the cache + Hub

Use when the owner says "model updates in the cache" / asks to re-pin revisions or re-run suites.

## Procedure

1. **Read the cache on EVERY node** (sparkrun caches are per-node; `.34`/`.35` hold the decision arms that `.30` lacks):
   ```sh
   for h in <nodes .30–.35>; do echo "== $h"; ssh ${WOPR_USERNAME}@$h 'cd ~/.cache/huggingface/hub && for d in models--*; do printf "%s %s\n" "${d#models--}" "$(cat $d/refs/* 2>/dev/null|head -1)"; done'; done
   ```
   A `refs/main` with an empty `snapshots/` is a stale/partial entry — it will re-download.
2. **Extract every recipe pin** (`grep '^model:\|^model_revision:' recipes/ attic/`). There are THREE pin surfaces, not one:
   - top-level `model_revision:` (most lanes);
   - a revision baked into a digest-pinned `container:` (ds4 knapcio: `HF_REVISION`/`boot.py`; the recipe sets no `model_revision`);
   - **nothing** — a floating binding (spec-decode drafts, and the `littlecedar/Ornith-1.5-397B-*` / `RadixArk/Qwen3.8-*` bases).
3. **Query the Hub** for every repo (recipe models **and their drafts**):
   `curl -s https://huggingface.co/api/models/<repo> | python3 -c "import sys,json;d=json.load(sys.stdin);print(d['sha'],d['lastModified'])"`
4. **Diff.** Cache/Hub sha ≠ pin ⇒ upstream `main` moved. Do NOT conclude "recipe stale": sparkrun may distribute `main` rather than the pin, and `--revision` is dropped for templated vLLM commands. The task is *verify + decide*, never a blind bump.
5. **Add one `- [ ]` task per lane** in `mad-science/TODO.md` — both shas, the date, the re-bench suite. Create the lane section if absent (the file had **no `## ifm`**). Do not edit recipes for this.

## Pitfalls
- Don't write "diffed every pin" until every node **and every draft** is covered.
- Drafts matter most: an unpinned draft sets acceptance length, so a moved draft can silently change a kept arm (Ling + Nemotron DSpark both moved 2026-10-12; that re-frames our 3.67→1.66 acceptance drop from "metric-window artifact" to "draft change").
- Re-read a recipe line before acting on a pin claim — review/advisory "clean reads" of a specific line were wrong twice this session (knapcio:3 was claimed to pin `52544481`; it is `runtime: sglang`).
