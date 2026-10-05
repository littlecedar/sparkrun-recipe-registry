# W3 — quality-eval status (one page)

Workstream W3: quality eval for the `local-inference-lab/Qwen3.8-Flash-Next-NVFP4`
("labquant") export (`recipes/qwen4/AGENTS.md:112`, WORK §6 item 5 at lines
2491–2496). Owner: `sub-q4-w3` (`COOP.md:37`).

## RESULTS — live paired run, 2026-10-04 (added by the main session)

Both arms were booted TP=2 on `.34/.35` and scored with `tools/qwen4-quality-eval.py`
at `temperature=0`, `--max-tokens 512`, `--seed 20261004`, one boot each.

| arm | served id | battery | score | artifact |
|---|---|---|---|---|
| reference (RadixArk, bf16 KV) | `RadixArk/Qwen3.8-Flash-Next-NVFP4` | 36 tasks (5 cats) | **35/36 = 97.2%** | `.scratch/q4/W3-radixark-full.json` |
| shipping (labquant, patched tree) | `/cache/runtime/labq-patched` | 38 tasks (6 cats) | **37/38 = 97.4%** | `.scratch/q4/W3-labquant-full.json` |

**On the 36 tasks common to both runs there are ZERO disagreements** and the five shared
category totals are identical (arith 8/8, code 7/8, falsepremise 6/6, instr 8/8, recall 6/6).
labquant additionally passes the 2 `verbatim` tasks. So on this instrument the two checkpoints
are **indistinguishable** — LIKELY **no gross quality regression** from the labquant export.

**Caveats, stated so nobody over-reads the row (all VERIFIED):**
1. **The battery is not frozen across the two runs.** `tools/qwen4-quality-eval.py` was extended
   from 36 to 38 tasks between the runs (mtime 02:57 vs the RadixArk JSON at 02:54), so the
   `battery_sha256` differs (`09ed86…` vs `e007dd…`) and the totals are on slightly different
   task sets. The comparison was therefore made on the **36-task intersection**, which is valid
   but not a pre-registered paired design. A clean artifact needs both arms re-run on one frozen
   battery. **Rule for the lane: never run the two halves of an A/B across an edit to the battery.**
2. **n=1, one repeat, 38 tasks.** This is a gross-breakage / large-regression instrument, not a
   benchmark. It cannot see a ≤1–2% quality delta. The plan memo's PASS/BLOCK/INCONCLUSIVE rule
   needs `--repeat` and more tasks to be a release gate.
3. `tools/quality-battery.py` is a tripwire, not this instrument's parent — the two are siblings.

**This closes the "no eval exists" half of §6 item 5. It does NOT close the item:** an eval now
exists and shows no gross regression, but it is not a certifying accuracy measurement, and the
"scores equal" result is a package-level comparison — it cannot attribute any future gap to the
PLE path specifically.

## DONE (off-cluster, this session)

- **`tools/qwen4-quality-eval.py`** — stdlib-only, Python 3.12+, no venv
  (`AGENTS.md:41`). OpenAI-compatible endpoint via `--base-url` (default
  `http://127.0.0.1:8000`), `--model`, `--json`, `--limit`, `--seed`,
  `--repeat`. `temperature=0`, prints every raw reply, per-task pass/fail, a
  per-category breakdown, and a total. `VERIFIED` it compiles
  (`uv run python -m py_compile`) and its own `--selftest` passes.
- **Battery:** 38 fixed tasks, 6 categories (arithmetic with a required
  intermediate, instruction-following, false-premise traps, generated
  long-in-prompt recall with a distractor, code comprehension, verbatim
  reproduction). `VERIFIED` every task's ground-truth sample passes its own
  scorer, all prompts are unique and share no >16-char prefix, and the battery
  hash is stable — the `--selftest` asserts all of this offline.
- **Negative controls:** `--selftest` runs the whole battery against an
  in-process mock in three modes — correct (38/38), always-wrong (0/38), and
  empty (0/38) — so a scorer that only ever passes is caught
  (`tests/` convention, `AGENTS.md:42`). `VERIFIED` all three classify as
  required.
- **`recipes/qwen4/W3-QUALITY-EVAL-PLAN.md`** — the A/B protocol, sample-size
  reasoning, and the pre-registered PASS/BLOCK/INCONCLUSIVE decision rule.

## BLOCKED — needs the cluster (a live server)

Nothing here has been run against a model. **I did not run this against a
server, and I could not:** this session has no cluster access, and the lane's
rules forbid launching containers from a subagent (`AGENTS.md:75–77`, one TP=2
job at a time; `COOP.md:19` holds the bench lock). Both exports also need a
~99–135 GB per-node checkpoint pull that is not cached on the assigned pair
(`COOP.md:22`). What remains is exactly the two-command A/B in the plan memo,
run on one boot each.

To unblock: claim the pair after the current W1 lock clears, boot each recipe
in turn (TP=2), and run the battery against each endpoint, writing both JSONs.
No code changes should be needed; `--model` is the only per-arm knob.

## Doc discrepancy found (not silently propagated)

`AGENTS.md:112` and WORK §6 item 5 (`QWEN4-MODEL-OPTIMIZATION-WORK.md`, item 5's
opening sentence) both say the export quantises "the PLE n-gram table ... where
RadixArk leaves [them] **BF16**". That framing is **inaccurate for the PLE
table**:

- WORK §17's own byte-family table row `| PLE n-gram table | ... |` records
  **RadixArk = `F8_E4M3 [2500012,160]`×128 (51.20 GB)** and **labquant =
  `U8 [2500012,80]`+`F8_E4M3 [2500012,10]`×128 (28.80 GB)** — i.e. **both**
  checkpoints store the table quantised; RadixArk is already fp8 e4m3.
- `mods/unpack-labquant-ple-nvfp4-to-fp8/README.md:26–28` independently confirms
  this (RadixArk `F8_E4M3 [2500012, 160]`; labquant packed NVFP4). The mod exists
  precisely to unpack labquant's NVFP4 to the fp8 the engine's PLE loader wants.
- §17 is **internally inconsistent**: three lines after that table it says
  "RadixArk's `quantization_config.ignore` keeps these in **BF16**: ... `*.ple.*`
  ...", contradicting its own table row (the ignore list is the *NVFP4*
  quantiser's ignore list; the PLE table is ignored by NVFP4 but stored as fp8,
  not BF16).

`VERIFIED` (two independent sources: WORK §17 table + mod README). The real
difference is **fp8 (RadixArk) vs packed-NVFP4-then-fp8 (labquant)** on the same
logical 160-wide table — still a genuine precision difference on the speculative
path, but not "BF16 vs quantised". Note the "attention/GDN projections" half of
the same sentence **is** correct (RadixArk BF16 vs labquant MXFP8, §17 rows
`GDN in_proj...` and `attn q/k/v/o_proj`). The labquant recipe's own caveat
("more aggressively quantized ... in the ... PLE-n-gram paths") is the accurate
wording. **I did not edit the lane's shipped docs** — flagging per the task's
instruction to report rather than propagate. The battery is not affected by this
wording; the A/B in the plan memo is still the right test.

## Not verified (explicitly unmeasured)

- Any actual accuracy number for either checkpoint — **unmeasured**.
- Whether the PLE precision difference is the cause of any gap — **unmeasured**;
  a gap is a package-level difference only (`W3-QUALITY-EVAL-PLAN.md` §2).
- Whether a reasoning server emits answers in `content` vs `reasoning_content`;
  the tool scores `content` and falls back to `reasoning_content` if `content`
  is empty, marking the fallback in the JSON — but this path is untested against
  the real server.
- The McNemar sample-size figures — a standard method (`LIKELY`), not measured
  on this model.