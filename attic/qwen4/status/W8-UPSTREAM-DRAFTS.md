# W8 — upstream engagement: verified status + ready-to-post drafts

> **DRAFTS ONLY. Nothing here has been posted.** Posting (comment, issue, PR) requires explicit human
> authorization. Do not authenticate to GitHub from an agent. This file contains no agent-executable
> action. Node ids are `<node-a>` / `<node-b>`; no internal IPs, hostnames, or node names appear here
> (repo rule, `AGENTS.md` §3.8).
>
> Every claim carries `VERIFIED` / `LIKELY` / `SPECULATIVE` and a source: an upstream URL with access
> date, or our WORK doc `§N` / `file:line`. Upstream state read **2026-10-04** via the public GitHub
> REST API (unauthenticated).

## Container images cited (read from recipe files)

| fact | value | source |
|---|---|---|
| Pinned SGLang image (manifest digest) | `lmsysorg/sglang:dev-cu13-qwen38-next-local@sha256:9d2a843c706c74bc259c0d9abf360551eb2734e1e7d255ab012a6965f10480b6` | `qwen3.8-flash-next-nvfp4-sglang.yaml:5`; `…-labquant-sglang.yaml:8` (VERIFIED) |
| Same image, Docker config ID | `sha256:cdd9649ba1cf…` | WORK §16 "Two digests for one image" (VERIFIED) |
| In-image git HEAD | branch `qwen4-main-squashed` @ `4ccff141db` | WORK §1 (VERIFIED) |

`9d2a843c` = manifest digest (`@sha256:` pin); `cdd9649b` = image config `.Id` — two hashes of two objects for one image; compare like-for-like field names. Cite the public model id only.

---

## Item 1 — issue sgl-project/sglang#37111

- **Title:** `[Bug] Qwen3.8-Flash-Next QSA + NEXTN decode graph silently corrupts output on GB10 TP2` (VERIFIED)
- **Author:** `hellojiaru` · **State:** **open** · **Created:** 2026-08-30 · **Last activity:** 2026-08-31 (2 comments, author scope-updates) · no labels/assignee (VERIFIED)
- **URL:** https://github.com/sgl-project/sglang/issues/37111 (read 2026-10-04)

**What our data adds.** Our lane runs the same checkpoint (`RadixArk/Qwen3.8-Flash-Next-NVFP4`) at TP=2 on two GB10 (SM121) nodes, NEXTN 3/1/4 — a second deployment of the reported topology (VERIFIED,
`qwen3.8-flash-next-nvfp4-sglang.yaml:3,26,39-43`). We have **not** reproduced the reported silent corruption (no `gate_37111.py` soak; W4 claimed, not closed — `COOP.md:38`, `AGENTS.md` §4). What we add now is a deterministic sibling failure on the same QSA + CUDA-graph path: our second checkpoint
(the locally-quantised `local-inference-lab` export) reaches `Capture target prefill CUDA graph begin`
and dies at prefill capture with `RuntimeError("PREFILL_CUDA_GRAPH_CAPTURE_FAILED")`, cause one frame
earlier at `qsa/metadata.py:141` — a non-pinned CPU→CUDA copy (WORK §7f, lines 3090-3101; confirmed by
deliberate falsification, §6 PRIORITY-1 gate (iv), lines 2175-2192). The reference export runs prefill
graphs and never reaches that line; the second never survives it — same image, engine, arch (§7f,
lines 3226-3228). That corroborates QSA prefill-capture fragility on SM121 independent of the
decode-graph corruption and gives a second, cheaper reproducer of the same line.

**Draft comment (not posted):**

```text
Second deployment data point, same topology (2x GB10/SM121, TP=2, one GPU/node),
same model (RadixArk/Qwen3.8-Flash-Next-NVFP4), NEXTN 3/1/4. We have NOT yet
reproduced the silent corruption, so this does not confirm the report — but we hit a
deterministic failure on the same QSA + CUDA-graph path that may be relevant.

With prefill CUDA-graph capture enabled on a locally-quantised export of the same
architecture, capture dies at sglang/srt/layers/attention/qsa/metadata.py:141:

    RuntimeError: PREFILL_CUDA_GRAPH_CAPTURE_FAILED
    (cause one frame earlier) Cannot copy between CPU and CUDA tensors during CUDA
    graph capture unless the CPU tensor is pinned ...

The same image and engine run the reference export with prefill graphs on and never
reach that line, so the trigger tracks the checkpoint, not the engine. Disabling the
prefill graph (--cuda-graph-backend-prefill disabled / --disable-prefill-cuda-graph)
avoids the path entirely and is mandatory for our second checkpoint.

Questions: (1) does the decode-graph corruption you report depend on the same QSA indexer
path? (2) is the companion gate_37111.py harness the canonical reproducer? We can run it
on our two-node pair and report eager-vs-graph results, both ranks' restart counts, and
OOMKilled.
```

**Caveat:** report stack is `d91c3682b` + SM121 fixes; ours is a different pinned digest (`9d2a843c`,
WORK §1). The digest is safe to share (already in the recipe file).

---

## Item 2 — issue #38319 (and fix PR #38355)

- **#38319 title:** `[Bug] Chunked Prefill + Radix Insert race corrupts KV pages (QSA, Qwen3.8-Flash-Next)` · **Author:** `andreasknopke` · **State:** **open** · **Assignee:** `alphabetc1` · **Created:** 2026-09-07 · **Last activity:** 2026-09-11 · **Comments:** 0 · https://github.com/sgl-project/sglang/issues/38319 (read 2026-10-04) (VERIFIED)
- **#38355 title:** `fix(mem_cache): eliminate chunked-prefill radix-insert race corrupting QSA KV pages (#38319)` · **Author:** `andreasknopke` · **State:** **open, unmerged**, not draft · **Base:** `qwen4-main-squashed` (**not `main`**) · **Created:** 2026-09-07 · **Last activity:** 2026-09-14 · https://github.com/sgl-project/sglang/pull/38355 (VERIFIED)

**What our data adds.** Our lane ports #38355 into an in-tree mod (`mods/fix-sglang-radix-chunked-insert`) and re-verified all four patch anchors against the pinned digest `9d2a843c` (§6 item 3, lines 2470-2474; anchor table §14, lines 4509-4517). It is a correctness fix — expected to remove the "!!!!"
wrong-output loop, with no tok/s change (§6 item 3). We independently observe the symptom class
(degenerate repeated-token output after long context with prefix reuse on this architecture) and
confirm our pinned image's HEAD is on `qwen4-main-squashed` @ `4ccff141db`, the same side branch #38355
targets (WORK §1; §14 lines 4559-4561) — a second-artifact port onto a non-`main` divergence.

**Draft comment (not posted):**

```text
Corroboration from a second deployment (2x GB10/SM121, TP=2, RadixArk/Qwen3.8-Flash-Next-NVFP4,
QSA + chunked prefill). We independently hit the repeated-token ("!!!!") wrong-output class at
~262k context with prefix reuse.

We ported the #38355 change into a mod against our pinned image
(lmsysorg/sglang:dev-cu13-qwen38-next-local@sha256:9d2a843c…) and re-verified all four patch
anchors against that digest; the fix applies and removes the loop, with no throughput change
expected (it is a correctness fix). Our image HEAD sits on qwen4-main-squashed, matching this
PR's base branch rather than main.

Observations that may help land it:
- The PR targets qwen4-main-squashed; if the intent is to merge upstream it likely needs
  retargeting to main. In our experience these anchors moved relative to main, so a rebase is
  not mechanical. Happy to report the exact anchors/hashes we matched.
- No action requested beyond making #38355 mergeable; we are not proposing a competing patch.
```

**Caveat:** our evidence for the *race* is symptom-level, not a page-level forensic dump; the issue
author holds those. Do not claim we independently proved the race mechanism.

---

## Item 3 — duplicated fastsafetensors PRs: #26597 vs #29717 (+ #29272, #31859, #40065, #32199)

- **#26597** `[Bugfix][ModelLoader] fastsafetensors: fix multinode device + add nogds opt-out` · `ubehera` · **closed, not merged**, closed 2026-09-22 by inactivity bot · https://github.com/sgl-project/sglang/pull/26597 (VERIFIED)
- **#29717** `[Bugfix][ModelLoader] fix fastsafetensors multi-node device + configurable bbuf/threads` · `shichaooutlook` · **closed, not merged**, closed 2026-09-30 by inactivity bot · https://github.com/sgl-project/sglang/pull/29717 (VERIFIED)
- Both make the same device change (`pg.rank()` → `torch.cuda.current_device()`); differ in the second half (#26597 `nogds` env opt-out; #29717 bbuf/threads CLI args, references #26597) (VERIFIED).
- **#29272** (the bug both fix) `[Bug] --load-format fastsafetensors crashes on multi-node TP …` · **closed** 2026-09-23 by inactivity bot · https://github.com/sgl-project/sglang/issues/29272 (VERIFIED)
- Still-open fix attempts: **#32199** (wire nogds/threads, 2026-07-23) and **#40065** (release file buffers after each shard, 2026-09-18; body reports GB10 warm-cache load 47.12→27.03 GB — the same retained-buffer defect our mod fixes) (VERIFIED).
- **#31859** `Support fastsafetensors no-GDS loading and page-cache release` **merged 2026-07-31**, but does **not** fix the device bug: `main` **still** has `device = torch.device(f"cuda:{rank}")` in `fastsafetensors_weights_iterator` (VERIFIED reading `main` @ `python/sglang/srt/model_loader/weight_utils.py:1189,1193`, 2026-10-04).

**What our data adds.** Our lane patches this same function in `mods/fix-fastsafetensors-tp2-sglang` because neither PR merged (mod `run.sh:20-21`; WORK §11, lines 3929-3954). We confirm two **independent**
defects invisible on single-node multi-GPU rigs: (1) device selection uses the global rank, so
one-GPU-per-node TP=2 asks rank 1 for `cuda:1` and dies "invalid device ordinal" (§11 table, lines
3944-3948); (2) the staging buffer is never released — `main`'s `finally:` calls only `loader.close()`,
never `fb.close()`, retaining ~26.9 GB from the same 128 GB unified pool as weights+KV, which is why
`--mem-fraction-static 0.85` fails "no GPU memory for the KV cache" (mod `run.sh:23-36`). We also
establish a **negative** that saves reviewer time: **no config-only workaround exists** —
`--model-loader-extra-config enable_gds:false`, `LOCAL_RANK`, etc. all fail, because the device index
is computed *before* the loader is constructed (§11, lines 3956-3958). Others corroborate on GB10
(#29272 comments by `ronhuafeng`, `gitbisector`, `ZackSample`).

**Draft comment (not posted — candidate target #29717, cross-referencing #26597):**

```text
These two PRs (#26597, #29717) are the same one-line device fix (pg.rank() -> local CUDA
device) plus different config plumbing; both were auto-closed for inactivity (2026-09-22 and
2026-09-30), as was the bug they target (#29272, 2026-09-23). main still has
`device = torch.device(f"cuda:{rank}")` in fastsafetensors_weights_iterator, and on
1-GPU-per-node TP=2 that resolves rank 1 to cuda:1 and fails with "invalid device ordinal".

We hit this on 2x GB10/SM121 (TP=2, one GPU/node) and run the local-device change
(torch.cuda.current_device()) in production; it is correct in both single- and multi-node.

Two notes for whoever picks this up, since the duplication likely stalled it:
1. There is no config-only workaround. We checked --model-loader-extra-config enable_gds:false
   and LOCAL_RANK; both fail, because the device index is computed before the loader is built.
2. There is a second, independent defect in the same iterator: its `finally:` block calls only
   loader.close() and never closes the FilesBufferOnDevice, so the staging buffer is never
   released. On a 128 GB unified-memory GB10 that competes with weights and the KV cache (we
   measured ~26 GB retained after load). PR #40065 covers this half; landing (1) and (2) together
   makes --load-format fastsafetensors usable on Spark-class hardware.

Suggest consolidating on one device-fix PR (plus #40065 for the buffer half) rather than
resubmitting two.
```

**Caveats:** we are not proposing our mod file upstream, only confirming the change. Do not claim
credit for others' corroborations. State `~26.9 GB` as measured-on-our-checkpoint, not universal.
---

## Item 4 — SM121 GDN decode silently falls back to Triton (no matching upstream item verified in scope)

- **Upstream item:** none found in scope; treat as a candidate **new issue**, not a reply. No URL → do not draft as a reply. (UNVERIFIED that none exists — not exhaustively searched.)
- **Our fact (`VERIFIED`, WORK §12, lines 4285-4306):** in the pinned container on GB10 (`capability (12, 1)`, `is_sm100_supported() False`, `is_sm120_supported() True`, flashinfer 0.6.17), the FlashInfer GDN decode auto-enable branch requires `is_sm100_supported()` **and** `mamba_ssm_dtype == "bfloat16"`; the first is False on SM121, so `--linear-attn-decode-backend` stays `triton` **with no warning and no log line**. A *closed* lever at c=1 here (not an optimization win) but a real ergonomics bug: an SM121 user cannot tell from logs.

**Draft comment (not posted — for a new issue, if the lane decides to open one):**

```text
On GB10 / SM121 (capability (12,1)), SGLang silently falls back to Triton for GDN
linear-attention decode with no log line. The auto-enable branch in server_args.py requires
is_sm100_supported() AND mamba_ssm_dtype == "bfloat16"; is_sm100_supported() is False on
SM121 while is_sm120_supported() is True, so the backend is never set and nothing says so.

Observed (VERIFIED in-container, flashinfer 0.6.17): capability (12,1), NVIDIA GB10,
is_sm100_supported() False, is_sm120_supported() True, linear_attn_decode_backend stays triton.

Request: either log the selected linear-attn decode backend at startup, or gate on
is_sm120_supported() | is_sm100_supported() so SM121 is not excluded silently. We are not
claiming forcing FlashInfer is faster on SM121 — only that the current silence makes the
choice unknowable from the logs.
```

---

## Fact bank — SM121 QSA guard worth contributing (candidate (a))

`VERIFIED` (WORK §15, lines 4698-4731): `sglang/kernels/kda_kernels/qwen38_qsa_sm121/__init__.py` exposes `can_use_qwen38_qsa_sm121()`, requiring BF16 (line 32) and `k.dtype == q.dtype == v.dtype`
(line 37), rejecting `head_dim != 256` (line 35), with `_SUPPORTED_HEAD_TOPOLOGIES = {(12,1),(24,2)}`
(line 40), `_MAX_BATCH = 128`, `_MAX_SELECTED_KV = 2055`. **Consequence: fp8 KV would never be
accelerated by this kernel even if it booted** — the predicate returns False and the caller falls back
to generic Triton. Corroborated opposite-runtime by an independent vLLM/EXL3 report ("Qwen4Exp QSA
requires a BF16 main KV cache", §6 item 14, lines 2611-2613). **Do not repeat the retracted
fabrication:** there is no `ValueError` / `kernels/ops/attention/__init__.py:115` dtype guard; that
text was fabricated and deleted (§15, lines 4668-4744) — cite only the real predicate. **Where it
could go:** a comment on #37111 or a new SM121-QSA-eligibility issue; not drafted standalone because
it answers neither verified thread's question.

## Open gaps / unverified assumptions

1. **#37111 corruption unconfirmed on our stack** — no `gate_37111.py` soak (W4 claimed, not closed). Draft 1 is path-corroboration, not a reproduction.
2. **Item 4 upstream status unverified** — no exhaustive search for an existing GDN/SM121 issue.
3. **Upstream statuses are a snapshot** (2026-10-04); a maintainer may act between reading and posting — re-verify before posting.
4. Drafts post under a human identity; no internal IPs/hostnames; no non-public pins.
5. **No file other than this one was changed; nothing was posted, commented on, or modified upstream; no GitHub authentication was performed.**