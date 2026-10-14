---
name: sparkrun-benchmark-campaign
description: "Run a same-window multi-arm benchmark campaign on a sparkrun DGX Spark cluster (decode/concurrency sweeps, knob ladders) and read the results correctly; not a single boot check."
---

# sparkrun benchmark campaign (DGX Spark / GB10)

Use when comparing recipe arms or knob values on a sparkrun cluster. Do NOT use for a single boot/smoke check.

## The non-negotiables

1. **One boot per arm cannot rank arms.** `benchmarking/decode-triage.yaml`'s own metadata puts the inter-boot noise floor at 7-25 % for byte-identical boots. Every comparison must be same-window, and the number you quote is a mean over several boots (2-7). Refuse to rank a gap under ~7 %.
2. **Read the `--output` file, never the printed table.** `sparkrun benchmark performance ... --output <tag>.yaml` also writes `<tag>.json` and `<tag>.csv`. Per cell there are TWO records (a `is_context_prefill_phase: true` prefill record and a decode record) and BOTH carry `tg_throughput`; filter `is_context_prefill_phase` out or you pool two phases and invent a bimodal boot.
3. **`bench_*` ids are NOT unique across concurrent campaigns** (derived per recipe+config, shared `~/.cache/sparkrun/benchmarks/<id>/` on the head node). Arm identity lives in your `<tag>` filenames and the `Benchmark ID:` line of `<tag>.log`; the id is provenance, not identity. A relaunched identical arm reuses its id and empties the earlier `runs/`.
4. **Equalize the admission cap before blaming the algorithm.** A concurrency flatline is usually `max_num_seqs` (a scheduler *admission* limit, not memory). Measured: UNO at cap 8 flatlined at c=8 (97.5) while the plain baseline reached 120; at cap 32 the same arm hit 145.5. Run any arm you are scaling at a cap >= 2x the highest concurrency you test.

## Procedure

Write one driver script on the head node that takes `<node>` and a list of `tag|recipe|profile-name|extra-args`, and for each arm runs:

```bash
sparkrun benchmark performance "$RECIPE" -H "$NODE" \
  --profile "$PROFILE" --output "$RUNS/$TAG.yaml" \
  --fresh --no-stop $EXTRA > "$RUNS/$TAG.log" 2>&1
sparkrun logs "$RECIPE" -H "$NODE" -n 8000 > "$RUNS/$TAG.serve.log"
```

- `--profile` takes a **bare registry name** (`decode-triage`, `concurrency-sweep`), not a path; a path fails unless `benchmarking/` exists in the cwd.
- `--fresh --no-stop` relaunches cleanly and leaves the server up for the next arm. Stop all leftovers at the end.
- `-o key=value` only overrides defaults that already have a `{placeholder}` in `command:`; otherwise append to `defaults.extra_args`.
- Displayed bench stdout hides the decode row; parse `<tag>.json`.
- **Accept length / accept rate are not in the bench output** — grep `accept len:` from `<tag>.serve.log` (the sglang container log).

Run arms in parallel on separate nodes only when each node also runs a same-window control; nodes differ ~2 %. Launch with `nohup` and poll the `.out` file, do not hold one long ssh call.

## Reading results

Decode-phase `tg_throughput.mean` at `context_size` x `concurrency`; `tg_req_throughput` is per-request. Quote a cv beside every spec-decode mean — accept-count variance is intrinsic (5-17 %) versus <0.1 % for plain decode, so a one-shot comparison of raw means across arms will mislead.

## Cluster hygiene

Head node: ssh as `${WOPR_USERNAME}` then `export HOME=/home/<operator>`; run from `${WOPR_RUN_FROM_DIR}` where recipes are symlinked. Unpublished mods need `sparkrun cluster update <name> --transfer-mode local` (or `--transfer-mode local` on `run`). Stop every leftover container when done.
