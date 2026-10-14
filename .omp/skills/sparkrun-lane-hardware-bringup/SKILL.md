---
name: sparkrun-lane-hardware-bringup
description: "Bring up (boot + benchmark) a sparkrun recipe lane on the DGX Spark cluster for the first time, and correct theory-only recipes against real hardware."
---

# Bringing up a sparkrun recipe lane on hardware

Use when a lane's recipes have never booted (theory-only) and you must run them on the DGX Spark cluster, or when a recipe fails to launch.

## 0. Orient (read-only)
- `recipes/<lane>/AGENTS.md` / `README.md` if present; else the `*-WORK.md` and `*JOURNAL.md` (git-ignored) and `COOP.md`.
- Root `AGENTS.md` for the gate and conventions.
- `git ls-files recipes/<lane> mods/<k2-mods>` — a lane can be entirely untracked; note what ships vs not.

## 1. Cluster preflight (head node = WOPR_HEAD_NODE, user WOPR_USERNAME)
```
ssh <head> 'HOME=/home/<operator> sparkrun status'         # find idle hosts
ssh <head> 'HOME=/home/<operator> sparkrun cluster show WOPR'  # transfer_mode
```
Recipes not in the published registry must be run **by path**; symlink them beside `mods` in the run dir (e.g. `/home/<operator>/development`), like the sibling lanes:
```
ssh <head> 'cd /home/<operator>/development && ln -sfn <abs-recipe> .'
```

## 2. Image + model
- The recipe digest-pins a `container:`. Pull it **on each target node**, fully detached so it survives the ssh session:
  `ssh <node> "setsid nohup docker pull <image> >/tmp/pull.log 2>&1 </dev/null &"`
  A bare `nohup ... &` dies when ssh closes; leftover child PIDs are docker de-duping, not a live pull.
- Prefetch the checkpoint while the image pulls (models are big): the container reads `/cache/huggingface/hub/models--OWNER--NAME/`. sparkrun distributes it in the launch's `[3/6] Distributing resources` step if not present.
- `sparkrun recipe validate <file>` is the gate (NOT `--strict`). It does NOT resolve `mods:`.

## 3. Boot / benchmark (detached)
```
ssh <head> "cd /home/<operator>/development && export HOME=/home/<operator> && \
  setsid nohup sparkrun benchmark performance <recipe> -H <node1,node2> \
  --profile <repo>/benchmarking/decode-triage.yaml \
  --output <durable/out.yaml> --fresh > <log> 2>&1 </dev/null &"
```
- Match the profile's `tg` across arms you intend to compare — a `tg=32` number is NOT comparable to `tg=128`.
- Read `tg_throughput`/`tg_req_throughput` from the per-cell JSON, never the printed table (it has no header and shows only the decode row).
- First boot is slow: weight load streams in `docker exec <ctr> tail -f /tmp/sparkrun_serve.log` — that file, not `docker logs`, has the real serve output.

## 4. When a boot dies
Get the real traceback: `docker exec <ctr> tail -60 /tmp/sparkrun_serve.log`. Classify:
- **gate in `srt/models/xllm.py`** (`_normalize_k2_horizon_config` / `_validate_mova_config`): a required config value is absent. Supply it — via `--json-model-override-args` as a **literal in `command:`** (sparkrun's `_SGLANG_FLAG_MAP` does not map that flag, so a `defaults:` key is dropped silently).
- **mod not found**: use bare `mods/<name>` for unpublished mods; `@<registry>/mods/<name>` resolves against the published clone and fails.
- Re-run the dry render to confirm a fix reaches the engine: `sparkrun run <recipe> -H <node> -n | grep -- '<flag>'`.

## 5. Correct the record and guard it
- Record measured t/s in the recipe header and the journal; mark now-false claims in the WORK docs (strike + FALSIFIED + date).
- Add a guard test pinning the fix (existence **and** value, literal-not-default) plus a negative control.
- A tracked guard must not require a git-ignored file: `skipTest` the ignored docs when absent, or the suite goes red on a fresh clone.

## 6. Gate + commit
Run the repo gate (unittest, `recipe validate` all, `bash -n`, `py_compile`), then `git add` **explicit pathspecs only** (the tree is syncthing-shared with a live second writer), review `git diff --cached --stat`, scan the commit message with `tools/safe_text.py --check`, and commit.

## 7. Clean up
`docker rm -f` IFM containers, remove scratch dirs (e.g. `/home/<operator>/ifm-runs`) and `/tmp/pull-*.log`; leave the `/home/<operator>/development` symlinks (documented working setup).
