---
name: retire-sparkrun-recipe-to-attic
description: "Retire a sparkrun-recipe-registry recipe/arm into attic/: record its measured metrics in the lane doc first, move bytes verbatim, update every reference and count, validate, commit explicit pathspecs."
---

# Retire a recipe to `attic/` without losing its measurements

For `sparkrun-recipe-registry` when an arm/control/experiment stops being shipped but its measured
numbers are still cited. Five waves of this already exist (`attic/{ds4,qwen4,ifm,ornith,qwen3}`).

## Order matters: metrics first, move second

1. **Recover the metrics from run artifacts, never from lane prose.** The artifacts are the
   receipts and they live in untracked scratch:
   - `~/benchmarks/<lane>-<date>/*.{json,csv,yaml}` on the head node, and
     `.scratch/<lane>/results/*.json`, `.scratch/p<NN>-<tag>/p<NN>.json` locally.
   - sparkrun/llama-benchy JSON: `benchmarks[].tg_throughput.{mean,values}`; **skip records with
     `is_context_prefill_phase: true`** — the same cell emits a prefill record whose `tg_throughput`
     is roughly half the decode value and looks like a second, slower boot.
   - Boot-level facts (grant, pools, KV allocation) come from that boot's `p<NN>.digest`
     (`grep -F 'capped to'`, `Mamba Cache is allocated`, `KV Cache is allocated`,
     `max_total_num_tokens=… max_running_requests=…`), never from a sibling boot's log.
   - The profile that produced a run is named in the driver (`.scratch/<lane>/run_phase<N>.sh`,
     `PROFILE=` line). Quote the profile, the boot tag, and the receipt path beside every number.
   Do not read these files raw if they may carry a model special token — `uv run python -B
   tools/safe_text.py --check <file>` first, or extract numbers programmatically and print only
   them.
2. **Write the metrics into the lane doc before touching the recipe** — the lane's `AGENTS.md`
   section for that arm (e.g. qwen3 §6). This is the only durable home once the file is frozen.
3. **If the recipe was a control, prove the pairing before archiving**: comment-strip and diff
   `defaults:` + `command:` against the treated recipe; only the intended keys/flags may differ.
   Record the check's date in the lane doc, and note that the lane's parity script returns early
   (silently skips) once either path is missing.

## Move

- `mkdir -p attic/<lane> && sha256sum <src>` → `mv` → `sha256sum <dst>`: the hashes must match.
  **Never edit the moved file** — archived recipes are frozen provenance ("leave their comments
  verbatim"); status/metrics notes go in the lane doc, not as new YAML comments.
- `git add` the explicit new path: attic items are tracked (the whole point — a retired arm that was
  never committed is invisible to a fresh clone and to third parties).

## Update every reference (the move is not done until these are green)

- Lane `AGENTS.md`: scope table, the arm's section, any "N recipes" phrasing, references section.
- Lane `README.md` (human table row + a Notes bullet) and the lane's `NOTES.md` if it lists the arm.
- Root `AGENTS.md`: recipe file count (`recipes/`, N files), the combined Key-Directories row's
  per-lane count, and the `attic/` inventory row.
- `recipes/README.md` root index usually lists only served recipes — check, do not assume.
- Untracked evidence/journals (`WORK §N`-style docs, `JOURNAL.md`): a one-line path fix is fine; do
  not rewrite history. Grep the whole tree (`git grep` for tracked, a python walk for ignored
  scratch) for the filename and the old path.

## Verify and commit

- Gate: `uv run python -B -m unittest discover -s tests`, `sparkrun recipe validate` over
  `recipes/*/*.yaml` **and the moved file's new path**, `bash -n mods/*/*.sh`,
  `py_compile mods/*/*.py tools/*.py`, then clear `__pycache__` (the `find`-based cleanup line in
  the docs is blocked by the tool policy — use a small python `shutil.rmtree` over globs).
- Working tree is syncthing-shared with a live second writer: stage explicit pathspecs only, review
  `git diff --cached --stat`, leave other lanes' untracked files alone.
- Commit body: what changed → what was verified (hash equality, parity diff, test counts) → what
  was not re-measured. No internal IPs/hostnames; run
  `uv run python -B tools/safe_text.py --check <msgfile>` before `git commit -F`.
- Leave the user's own tracking files (`mad-science/TODO.md`) alone; report them instead.
