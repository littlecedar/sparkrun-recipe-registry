# NOTES — Qwen4 lane working notes

**Purpose.** A one-page, kept-current state-of-play for `../../recipes/qwen4`. This is the *working* note
— short, revised often, never a second research record. Durable guidance is in
[`AGENTS.md`](AGENTS.md); the public-facing summary is [`README.md`](README.md); the lane's archive
(evidence, journal) is [`../../attic/qwen4/`](../../attic/qwen4/)
(`QWEN4-MODEL-OPTIMIZATION-WORK.md` `§N`, `JOURNAL.md`, `status/`, `arms/`; the `COOP.md`
ledger is a git-ignored working file, removed from git 2026-10-10).
**If it is long, it is in the wrong file.**

_Last condensed: 2026-10-04 (session 3 — lane harvest)._

## State in five lines

1. **The directory ships exactly two recipes (2026-10-14 cut):** the fastest TP=1
   (`qwen3.8-flash-next-nvfp4-solo-vllm-b12x`, one Spark, PLE table on disk) and the fastest TP=2
   (`qwen3.8-flash-next-nvfp4-labquant-sglang`, re-pinned to `6c01ac37`, 262k context). Both serve the
   labquant export. See [`../../recipes/qwen4/README.md`](../../recipes/qwen4/README.md) for the cut
   table and receipts.
2. **Cut evidence (`benchmarking/decode-triage.yaml`, decode-phase rows):** TP=2 labquant
   base **41.32 / 38.58** tok/s C1 (d0/d8192), re-pinned **40.32 / 43.29**; the other two labquant
   TP=2 arms C1-tied (highcon 40.10/41.92, longctx 42.47/39.04); RadixArk TP=2 36.84/34.44; TP=1 solo
   vLLM 33.92/34.35. Five in the cut window; the sixth, TP=1 solo SGLang, failed readiness there (a
   port timeout, not architectural) and was **re-measured later the same day: 19.82 / 20.97**
   (`bench_253dd84c9a78`) — ~42% below the TP=1 pick, so **it stays archived**.
3. **All four non-survivors are in `attic/qwen4/arms/` (wave 4).** The shipped tooling uses
   `.34/.35`; `.30/.31` are restricted and `.32/.33` carry peer work. Both qwen4 checkpoints are
   cached on `.34/.35` (RadixArk 126 GB, labquant 196 GB). **Cache hygiene (owner policy 2026-10-14):**
   the RadixArk checkpoint is referenced by **no recipe under `recipes/`** any more, so its node cache
   was cleared 2026-10-14 with `hf cache rm -y model/RadixArk/Qwen3.8-Flash-Next-NVFP4` on `.34` and
   `.35` (**freed 135.3 GB on each**; never a raw `rm -rf`). It is re-fetchable from the Hub, so a
   resurrected RadixArk arm (or a needle/quality cross-check) costs a download.
   *(2026-10-14 sixth-arm re-measure: `.34` was re-populated with the RadixArk snapshot — sparkrun
   distributed 126 GiB to boot the archived arm there, since `.30` was held by another workstream.
   Clear `.34` again if the cache-hygiene policy still stands.)*
4. **The labquant chain was re-verified against `6c01ac37`** (W14): `unpack-labquant-ple-nvfp4-to-fp8`
   gained a preserve-and-rewrite path (guard `tests/test_labquant_ple_mod_classify.py`),
   `skip-labquant-vision-tower` was dropped as obsolete (the export serves **vision** again), and a
   **hybrid-tree** defect in `fix-labquant-modelopt-mixed-flat-schema` (revision switch refused to
   rebuild) was fixed — it now rebuilds on a stale stamp.
5. **W1 (fp8 KV) = NO; W2 (EXL3) = NO-GO; W9 (long context) built then ARCHIVED (1M droppable).**
   Open: W3/W4 soaks, W6 (TP=4), W7 (kernel timing), W12 (cross-runtime vLLM benchmark).

## Session 2026-10-04 (3) — lane harvest, in brief

- **Lane A recipe written + render-verified** (`…-highcon-…`): cap 32 / pool 128 / cps **4096** (8192
  regresses k=8/k=16 on labquant). Rationale in the file header; `--max-running-requests 32
  --max-mamba-cache-size 128` confirmed in the rendered line on the head.
- **Lane B recipe written + boot-verified** (`…-longctx-…`). **Two real findings, both cost a boot:**
  1. **This build RAISES on over-long context, it does not warn.** `--context-length 1000000` vs the
     derived 262144 dies with `ValueError … model_config.py:860` unless
     **`SGLANG_ALLOW_OVERWRITE_LONGER_CONTEXT_LEN=1`** is in the container env. WORK §15 said
     "accepts … with only a warning" — **wrong for this pinned image**; the recipe now carries the env
     var (load-bearing, travels with `max_model_len`).
  2. **The YaRN `--json-model-override-args` only works NESTED under `text_config.rope_parameters`.**
     The loader does `config.text_config.update(value)` (`utils/hf_transformers/config.py:282`), so a
     FLAT `{"text_config": {"rope_type": "yarn", …}}` setattrs `rope_type` beside the real dict and
     left it at `default` → **the YaRN silently did not apply** while the server booted and looked
     fine. Proved in-container: flat → `rope_type: default`, nested → `yarn`. Fixed.
- **Cluster facts:** `.34/.35` idle, 117 GB avail, `pmproxy` up (~1 proc each). Head runs sparkrun
  **v0.4.0-alpha** (local is v0.3.10). dry-run `-n` needs real target nodes to satisfy rank planning.
- **Attic wave 2:** `zz-rk-fp8kv`, `zz-rk-nospec`, `zz-rk-nospec-matched`, `zz-lq-nospec-matched`,
  `zz-rk-moebackend`, `zz-labq-fastboot-sglang` moved to `arms` with rows.
- **Docs:** `../../recipes/qwen4/README.md` written (lane rationale, measured table, caveats); root
  `recipes/README.md` Qwen-4x table updated with the two lanes; `AGENTS.md` §1/§4 (W9)/runbook updated.

## What a new session should do first

1. Read `../../AGENTS.md` end-to-end (it is short on purpose), then `README.md` for the lanes.
2. Set the **Live state** node assignment from the tasking and claim a
   workstream (the git-ignored ledger is working scratch; record the live assignment node-side).
3. Left: W3/W4 (re-run the quality battery on one frozen set; the #37111 release soak), W6 (TP=4, fix
   the recipe first), W7 (kernel timing in a **dedicated** container), W12 (vLLM). Off-cluster: W10.
4. **Quality gates outrank throughput knobs** — Lane B's 1M route is unverified above ~262k; do not put
   it in front of users without a needle gate (WORK §15 step 3).

## Next checks, cheapest first

| # | check | cost | why it is next |
|---|---|---|---|
| 1 | `sparkrun run <recipe> -H <pair> -n` and read the rendered serve line | seconds | catches an unmapped/ignored `-o` or an unresolved mod before a 50-minute boot |
| 2 | Confirm the two mandatory labquant flags survive a recipe edit (`--moe-runner-backend flashinfer_cutlass`, `--cuda-graph-backend-prefill disabled`) | seconds | dropping the second does not degrade output — it prevents boot (§7f) |
| 3 | For any long-context arm, grep the container serve log for `rope_type: yarn` | seconds | the flat override form is **silently inert** (this session) — a booted server is not proof |
| 4 | Confirm any new checkpoint `pin` uses `model_revision:` (not `revision:`) | seconds | the `revision:` key is silently inert |
| 5 | `MemAvailable` + `pmproxy` RSS on the assigned pair before launching | seconds | a boot can die in `alloc_memory_pool` and blame the peer |

## Open questions, with the discriminating arm

- **`--enable-linear-replayssm-spec`:** does it boot and what does it free on our geometry? One boot,
  then a `../../tools/gate-37111.py` soak before any adoption. Most promising un-measured memory lever.
- **Pool 112→128 mechanism (§19x Result 4):** ~13% more k=24 tok/s at matched config, unexplained by
  the admission model; a third pool-128 replication would tighten it. Do not ship as if established.
- **The `F` mechanism (§3b):** `F = 8.375 ms/step` is measured but unattributed.
- **MoE kernel ceiling (W7):** `torch._grouped_mm` still untimed; `--fp4-gemm-backend` never A/B'd.
- **#37111 (W4):** silent decode-graph corruption on this engine/topology; gate exists, release soak owed.
- **Lane B quality (NEW):** the 1M route boots but **no needle/quality gate has run**. This is the
  prerequisite before serving 1M and is the most important open item for Lane B.

## Do-not-re-derive (the short list)

- `--max-prefill-tokens` = null on both checkpoints. `chunked_prefill_size 8192` = not adopted on labquant.
- **fp8 KV = config-level NO** (SM121 QSA needs BF16 queries). Do not re-open as a throughput lever.
- **`revision:` is inert — use `model_revision:`.** Do not "simplify" the key back.
- **`json_model_override_args` must nest under `text_config.rope_parameters`, not flat** (this session).
- **`--context-length` past the trained ceiling raises unless `SGLANG_ALLOW_OVERWRITE_LONGER_CONTEXT_LEN=1`**.
- `max_num_seqs ≥ target + 1`, and the **mamba pool** (`max_mamba_cache_size // 4`, lazy) is the real
  admission ceiling — not `max_num_seqs`.
- The `~80 GB/s gather ceiling` does **not** reproduce; `67 tok/s` competitor gap **dissolved** (§13).

## Hygiene / standing

- Every claim carries `VERIFIED` / `LIKELY` / `SPECULATIVE` + a source, or says "unmeasured".
- **Before retracting an error, re-run the arm and capture fresh** — absence from reaped `bench_*`
  scratch is not absence of the event (the fp8-KV lesson, WORK §15).
- `launch.sh` guards: one cluster job at a time; new profile filename per replication; never override
  `MIN_AVAIL_GB`; scoped teardown only.
- Keep `../../recipes/qwen4` to shipped + contributor + live arms; dead arms go to `attic/qwen4/arms/` with
  a manifest row ([`attic/qwen4/ARMS-MANIFEST.md`](../../attic/qwen4/ARMS-MANIFEST.md)).
- Internal IPs/hostnames do not go in tracked files. The live node assignment stays node-side.