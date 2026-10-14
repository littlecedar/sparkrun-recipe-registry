---
name: sparkrun-recipe-revision-drift-survey
description: "Use when auditing sparkrun recipe model/checkpoint revisions against upstream (Hub/cache drift) in the littlecedar registry; covers the three pin sites, the draft layer, and cache-vs-Hub diffing."
---

# Auditing recipe revision drift (sparkrun-recipe-registry)

Goal: for each shipped recipe, find whether the served checkpoint (or its spec-decode draft) has moved upstream, and file a pin + re-bench item per lane. Get this wrong and you either miss a silent quality change or raise a phantom "update".

## 1. Find every pin site (there are three)

1. **Recipe YAML** — top-level `model_revision:`. Many recipes have none (they float).
2. **Container image env** — some images bake the revision (e.g. the ds4 knapcio image's `boot.py:24` `REVISION`/`HF_REVISION`). A recipe can pin one revision in YAML while the image bakes another — check the *recipe's own* pin first; if it already equals upstream `main`, there is no recipe-level adopt to propose (the only open question is whether the image's baked value disagrees).
3. **Spec-decode drafts** — `speculative_draft_model` (sglang) or `defaults.speculative_config`'s `model` (vllm) are almost always bare repo ids, i.e. UNPINNED. A draft that moves changes acceptance length and therefore C1 for a *kept* arm, silently. Always sweep the draft repos separately.

## 2. Diff cache and Hub against the pins

- Cache: on a runner node, `~/.cache/huggingface/hub/models--*/refs/main` holds the fetched revision (the sha under `snapshots/` too). A directory mtime alone is noisy — use `refs`.
- Hub (compact — do NOT `read` the API URL raw, it's a multi-thousand-line config dump):
  `curl -s https://huggingface.co/api/models/<repo> | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d["sha"], d["lastModified"])'`
- Compare Hub `sha` (current `main`) + `lastModified` against the recipe pin and the cache ref. Report as "main moved <date>" (factual), not "newer than the pin" (inference), unless the dates prove it.

## 3. Scope honestly

A single node's cache covers only what that node cached. Arms living elsewhere (decision lane on `.34`/`.35`, the Ornith 397B, etc.) must be checked via the Hub API directly. Never write "diffed against every recipe pin" from a one-node sweep — say which node and which extra repos were queried.

## 4. File the work

Add one `- [ ]` item per affected lane in `mad-science/TODO.md` carrying the exact old/new shas, the dates, and the bench suite to re-run. If the lane still says "*(all items completed — archived in ../attic/DONE.md)*", DELETE that pointer when you add an open item — a stale "all completed" line under a new task is the recurring defect. Do not edit recipes to perform the re-pin; the task is the deliverable.

## 5. Watch for the draft→acceptance confound

When an arm's acceptance length fails to reproduce, hypothesise BOTH the metric-window artifact AND a moved unpinned draft; the two are indistinguishable without a same-draft A/B.
