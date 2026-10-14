---
name: sparkrun-recipe-test-boot
description: "Test-boot a sparkrun inference recipe on the WOPR DGX Spark cluster (head=${WOPR_HEAD_NODE}, idle nodes) end-to-end: state preflight, mod delivery, dry-run, detached launch, readiness/Engram verification, multi-arm sweep hygiene."
---

# Sparkrun recipe test boot (WOPR cluster)

When the user asks to boot-test or trial a recipe on idle nodes. Run `sparkrun` ON ${WOPR_HEAD_NODE} as ${WOPR_USERNAME}; target nodes via `-H <ip>,<ip>` (first host = head/rank0).

## 0. Preconditions
- Repo tree is rsync'd to `/home/<operator>/src/sparkrun-recipe-registry` (no `.git` on the head; never `git -C` there).
- In-progress recipes need a symlink in `/home/<operator>/development` -> src tree file (old symlink names may dangle).
- Local (laptop) CLI calls need `HOME="$PWD/.local/sparkrun-home"`; head-side calls don't.

## 1. Preflight (head + nodes)
- `docker ps` on nodes must be clean; check recipe's `container:` digest vs `docker images --digests` on each node (matching digest => no pull).
- Disk: nodes need ~repo size free (`df -h /home`).
- HF cache completeness: `du -shL ~/.cache/huggingface/hub/models--<org>--<name>` (NEVER plain `du -sh` — xet symlinks make it under-report by ~100x); definitive: `hf cache verify <org>/<name>` (exit 0, "All checksums match"). Stray `*.incomplete` blobs are leftovers, not a defect.

## 2. Mod delivery (unpushed mods)
- `@littlecedar/mods/<name>` resolves on the control machine to `~/.cache/sparkrun/registries/littlecedar/mods/<name>/` (scoped refs do NOT git-sync). To ship unpushed code, rsync the mod dir from the src tree into that clone (and into any legacy `_url_<hash>` clone). Do not push commits just for a trial unless asked.
- Verify with `diff -rq` + md5sum vs the worktree copy.

## 3. Dry run
```bash
cd /home/<operator>/development && sparkrun run ./<recipe>.yaml -H <a>,<b> --transfer-mode local -n
```
Check: placement, distribution lines, rendered serve command. (`-v` is NOT a `run` option in 0.4.0-alpha.)

## 4. Launch detached (survives ssh drop)
```bash
cd /home/<operator>/development
nohup bash -c 'sparkrun run ./<recipe>.yaml -H <a>,<b> --transfer-mode local; echo SPARKRUN_EXIT=$?' >/home/<operator>/<name>-boot.log 2>&1 </dev/null &
echo $! > /home/<operator>/<name>-boot.pid
```
Then an async waiter: `P=$(cat pid); while kill -0 $P 2>/dev/null; do sleep 20; done; tail -400 <log>`.

## 5. Verify readiness (CLI exits 0 at HTTP-ready)
- `sparkrun logs <job-id> </dev/null 2>&1 | grep -a ...` — **always redirect stdin** (`</dev/null`) for `sparkrun logs`; without it, in a heredoc/piped script it SLURPS the remaining script lines (same for nested `ssh` -> use `-n`).
- Read the launcher boot line (`[tensorfold-launcher] boot: ... engram=<path>`) to confirm model + engram wiring.
- In-container proof (both nodes): find the engine pid via `docker exec <c> sh -c 'for d in /proc/[0-9]*; do grep -qa <engine> "$d/cmdline" ...'` (PID 1 is a wrapper shell, not the engine), then check `$d/environ` for the engine vars and `ls -l $d/fd` for open weight/engram files.
- API: `curl <head>:8000/v1/models` (check `max_model_len`), `/health`, one plain-text chat completion (repeatable answer at temperature 0/`max_tokens` small). Worker logs live at `/tmp/sparkrun_serve.log` INSIDE the container (docker logs on the worker is often empty).
- Cold vs warm boot: sparkrun's runtime cache is keyed by model id — changing the recipe's `model:` forces a cold boot (per-rank weight cache write + CUDA JIT), e.g. ~530 s TTR rank-0; warm boots are ~1 min. Note it in the report; do not mistake it for a hang.

## 6. Close out
- Record the boot in the lane NOTES (job id, TTR, weight-load times, engram paths/FDs, API checks, how to stop).
- Leave the server running by default; report `sparkrun stop <job-id>` (in a multi-arm sweep, stop between arms instead — see §7).

## 7. Multi-arm sweeps (several boots in one session)

Back-to-back arms add failure modes a single boot never shows. Each rule below
cost real time on the 2026-10-13 served-model-name sweep (12 arms):

- **Assert the node(s) empty before every boot**: `docker ps -q | wc -l` must be 0.
  A leftover server from the previous arm keeps the port bound; the next arm's
  engine dies on bind while sparkrun's readiness probe curls the port and reports
  the OLD server as "Inference ready" (exit 0, suspiciously fast TTR). You then
  record the wrong model as verified.
- **Parse job ids from `sparkrun status` WITHOUT the `.yaml` suffix**: the job
  name is the recipe basename (e.g. `clef-flash-decision-sglang`). Matching
  `grep -F "<basename>.yaml "` finds nothing, the `stop` is silently skipped, and
  the leftover poisons every following arm. Echo the parsed jid, keep `stop`
  output, and re-check `docker ps` after each stop.
- **Verify the answered id, not just "ready"**: `GET /v1/models` must return THIS
  arm's repo id; a fast TTR or an id belonging to the previous arm means the probe
  hit a leftover — re-run after cleanup.
- **One GPU-resident model per node**: a still-running large arm starves the next
  boot (a resident 72G INT4 Ling serve made the next arm's probe time out after
  30 min; the same arm booted in 125 s solo). Stop before starting.
- **Two-node arms need both nodes**: run TP=2 arms serially; 1-node arms can go
  paired (one per node) in the same window.
- **Recipes sharing `served_model_name` share one cluster id** (the served name
  folds into the job intent hash), e.g. three labquant arms -> one id; `sparkrun
  stop <id>` addresses whichever is currently running.
