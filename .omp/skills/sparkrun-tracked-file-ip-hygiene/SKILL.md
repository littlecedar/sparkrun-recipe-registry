---
name: sparkrun-tracked-file-ip-hygiene
description: "Before committing/pushing tracked docs in sparkrun-recipe-registry: scan for raw host IPs/fabric addresses, since the repo gate does not. Use whenever a session edited lane docs, runbooks, AGENTS/README, or other tracked prose — especially subagent-authored files."
---

# Tracked-file IP hygiene (sparkrun-recipe-registry)

The registry is distributed to third parties and `AGENTS.md` forbids hostnames/IPs in tracked files. Since 2026-10-22 the gate does scan **tracked** files — `tests/test_tracked_address_hygiene.py` walks `git ls-files` and fails on an RFC1918 literal or a bare `<head-node>` — so a leak that is already committed reddens the suite instead of shipping quietly. What the guard cannot see is a file that is not tracked yet, and subagent-authored lane docs leak addresses readily because they transcribe the real IPs they measured.

## Pre-commit scan

Use the `grep` tool (or `git grep`) over the staged/modified paths, with this address pattern —
RFC1918, and note the **per-branch** octet counts (a single shared tail matches only the `10.` branch,
leaving `192.168.x.x` — the CX7 range — and `172.16-31.x.x` invisible):

```
\b(10\.\d+|192\.168|172\.(1[6-9]|2\d|3[01]))\.\d+\.\d+\b
```

- Also grep for the head-node hostname and the internal domain: their literals live in
  `.local/CONFIDENTIAL.md` (git-ignored), never in a tracked pattern.
- Replace every hit in tracked prose with the `.30-.35` shorthand (e.g. `MASTER_ADDR=<node-ip>` → "the master on `.30`"; `bootstrap <cx7-ip>` → "the CX7 link").
- **Exempt** git-ignored working files: `.local/`, `**/*JOURNAL.md`, `**/*-WORK.md`, `**/*-WORK-ARCHIVE.md`.
- `tools/*` may carry deliberate example endpoints (e.g. `http://<node>:PORT`) — only flag ones the session added.

## Why

2026-10-13: `recipes/glm/README.md` runbook bullets shipped to commit `cdf7ab1` (pushed) with raw fabric/CX7 addresses and a `MASTER_ADDR` line. The rest of that session masked everything consistently; only the subagent-written doc slipped, and the gate was green. A leak that reaches origin costs a follow-up commit and looks sloppy to third parties.
