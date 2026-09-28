# ds4_NOTES — DeepSeek V4.1-Flash EXL3 recipes: the max_num_seqs=16 / gmu retune

Session log for the **DeepSeek v4.1 Flash** lane (`model_symbol=ds4`), 2026-09-27/28.
Durable facts are consolidated into `AGENTS.md` **§7.12** and the
`recipes/README.md` table — read those first; this file is the working record and
is pruned as facts graduate.

## Objective

Raise `max_num_seqs` to ≥16 on the TP=4 and TP=6 arms (including the 1M arms),
align `gpu_memory_utilization` with actual usage, benchmark the release
candidates, and update `recipes/README.md`. TP=3 is out of scope (task names
TP=4/TP=6); left at 8 / 0.80.

## Change set

Four recipes — `…-exl3-{tp4,tp4-1m,tp6,tp6-1m}-vllm`:

- `max_num_seqs: 8 → 16`
- `gpu_memory_utilization: 0.80 → 0.85`
- `compilation_config` ladder extended to `16·(k+1) = 64`:
  `[3,4,6,8,9,12,15,16,18,20,21,24,28,32,36,40,44,48,52,56,60,64]`
- 1M siblings kept in **lockstep** with their 300K twin (guard
  `test_each_1m_recipe_matches_its_300k_sibling_apart_from_context` allows only
  `max_model_len` to differ).

`tests/test_ds4_recipes.py`: `test_control_truncated_capture_sizes` updated for the
64-topped ladder; `test_control_unconsumed_default` re-anchored on
`tensor_parallel: 4` (its old `gpu_memory_utilization: 0.80` anchor was a tunable
value and the retune broke it — the control's own comment had warned of exactly
that).

Registry fix: `mods/bound-engram-cache` is **untracked in git**, so the `file://`
littlecedar registry clone could not resolve it; symlinked the working-tree dir
into `.local/sparkrun-home/.cache/sparkrun/registries/littlecedar/mods/`. Real
fix (done this commit): commit the mod.

## Why 0.85 / 16 — measured, not derived

The vLLM boot log prints the real per-rank budget (`Desired GPU memory
utilization is (gmu, gmu·121.69) … Actual usage is W … Current kv cache memory in
use is K`). Measured W on every TP=4/TP=6 arm is only 47–64 GiB, so 0.85 (103.44
GiB promised) leaves ~18 GiB of the 121.69 GiB device beneath the promise — and
the TP=3 arm already consumed ~94 GiB of 121.69 at 0.80 and boots. `max_num_seqs`
bounds resident slots; **max concurrency is pool/ctx** (AGENTS.md §6.5) — on TP=4
1M the 16 slots queue rather than run 16-wide; the other three run 16 concurrent.

## Results — every arm booted EXACTLY as shipped

| arm | KV GiB | KV tokens | conc | was | C1/C4/C8/C16 t/s |
|:--|--:|--:|--:|--:|:--|
| TP=4 300K | 38.06 | **5,203,288** | 17.34× | 3,879,721 | 38.8 / 66.3 / 88.5 / 122.0 |
| TP=4 1M | 33.84 | **5,750,109** | 5.75× | 4,200,885 | 40.7 / 65.4 / 84.5 / 121.3 |
| TP=6 300K | 52.78 | **13,594,187** | 45.31× | 12,006,501 | 40.0 / 78.0 / 107.9 / 151.1 |
| TP=6 1M | 49.41 | **15,034,010** | 15.03× | 13,054,046 | 43.4 / 72.7 / 110.2 / 149.1 |

Pool +13 % to +37 % on every arm; **C16 newly reachable**. One cold boot per arm,
distinct prompts, greedy, non-streaming (`usage.completion_tokens`/elapsed).
Quality smoke (`27*43→1161`, planets) correct on all four. Needle at **799K prompt
tokens** correct on both 1M arms (TP=4 639 t/s, TP=6 579 t/s prefill); a
~1.6M-token prompt correctly returns HTTP 400 (over the ceiling).

Per-rank memory lines (weights+non-torch / activation / graph, GiB) at 0.85:
TP=4 300K 59.54/5.83/1.0, TP=4 1M 63.75/5.84/1.11, TP=6 300K 47.17/3.49/1.21,
TP=6 1M 50.18/3.85/1.13. Raw logs: `.scratch/ds4/gmu/{tp4-300k,tp4-1m,tp6-300k,
tp6-1m,r4}.{launch.log,measure.out,needle*}`; harness
`.scratch/ds4/gmu/{boot_and_probe.sh,measure_arm.py,needle_curl.py,depth_ladder.py}`.

## Process lesson (recorded on purpose)

A ~799K prefill at ~600 t/s takes **20–23 min**, and killing the client does
**not** cancel it — the worker keeps burning CPU to finish (`/proc/<worker>/stat`
ticks climbing). A 20–30 s probe thus "times out" on a *busy* engine, which I
twice read as a wedge before checking worker cpu ticks. On a GB10 deep-prefill
arm, never call a state a "hang" from one timed-out probe (AGENTS.md §11).

## Follow-ups (not done here)

- `mods/bound-engram-cache` must be committed (was untracked) and the registry
  clone refreshed; otherwise every launched recipe fails mod resolution.
- TP=3 retune (16 / 0.85) is a possible future ask but was out of scope; TP=3 is
  the memory-tight arm (KV only 7.32 GiB at 0.80) and would need its own boot.
