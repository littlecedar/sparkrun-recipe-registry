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

1. **Two production TP=2 lanes now ship** off the labquant checkpoint, plus the balanced base and the
   RadixArk reference. See [`../../README.md`](../../recipes/qwen4/README.md) for the lane rationale.
   - **Lane A (high concurrency):** `qwen3.8-flash-next-nvfp4-labquant-highcon-sglang` — `max_num_seqs: 32`,
     `max_mamba_cache_size: 128` (ceiling 28→32). Renders verified; boot-verified this session.
   - **Lane B (long context, 1M):** `qwen3.8-flash-next-nvfp4-labquant-longctx-sglang` — `max_model_len:
     1000000` + YaRN override + `SGLANG_ALLOW_OVERWRITE_LONGER_CONTEXT_LEN=1`. Boot-verified this session.
2. Best measured decode (unchanged): RadixArk **37.973 tok/s** k=1 d=0; peak **~87–91 aggregate** at
   d=8192/k=16, both checkpoints falling ~38% by k=24. The story is a **decode-step model**
   (`t_step = 8.375 ms + bytes/145.5 GB/s`), not a byte-reduction story.
3. The lane's scarcest resource is **cluster time on one free TP=2 pair**. `.34/.35` free this session;
   `.30/.31` restricted; `.32/.33` carry the DS4 serving job. **Both qwen4 checkpoints are now cached
   on `.34/.35`** (RadixArk 126 GB, labquant 196 GB) — a boot needs no model pull.
4. W1 (fp8 KV) = **config-level NO**; W2 (EXL3) = **NO-GO**; **W9 (long context) DELIVERED as Lane B**.
   Open: W3/W4 (quality/gate soaks), W6 (TP=4), W7 (kernel timing), W12 (vLLM).
5. **Directory is lean (production-only, ds4 convention):** `../../recipes/qwen4` holds just the 4
   production recipes + `README.md` + `AGENTS.md` + this `NOTES.md`. **All** else — 24 arms, the
   record/journal/ledger, and the status memos — is under [`../../attic/qwen4/`](../../attic/qwen4/)
   (manifest: `attic/qwen4/ARMS-MANIFEST.md`).

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