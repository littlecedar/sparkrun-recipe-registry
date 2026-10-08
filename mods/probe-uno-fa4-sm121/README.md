# probe-uno-fa4-sm121

Probe: allow SGLang's native **UNO** speculative decoding to use the `fa4`
attention backend on NVIDIA GB10 (DGX Spark, compute capability 12.1).

## What it changes

One comparison, in `python/sglang/srt/arg_groups/speculative_hook.py`:

```python
-    if (prefill_backend, decode_backend) != ("fa3", "fa3"):
+    _UNO_ALLOWED_BACKENDS = ("fa3", "fa4", "triton")   # = UNO_ATTN_BACKENDS
+    if (prefill_backend not in _UNO_ALLOWED_BACKENDS
+        or decode_backend not in _UNO_ALLOWED_BACKENDS
+        or prefill_backend != decode_backend):
```

Nothing else. It deliberately does **not** patch the `fa3` capability assert in
`layers/attention/attention_registry.py`. If UNO can only run by neutering that
assert, it should fail loudly rather than reach a kernel that was never compiled
for `sm_121`.

## Why

`_handle_uno` requires prefill **and** decode backend to be the literal string
`fa3`, and `create_flashattention_v3_backend` asserts `major in {8, 9}` — so UNO
is unreachable on GB10 as shipped, on a code path where the error message itself
recommends flashinfer.

`create_flashattention_v4_backend` builds **the same class**
(`FlashAttentionBackend`) with `fa_impl_ver=4` and has **no capability assert**.
Inside the backend, the version selects only the kernel import, and on capability
12 it imports `kernels/ops/attention/flash_attention_v4_sm120.py` —
"FlashAttention-4 APIs specialized for SM12x". Since UNO's gate is a string
comparison rather than a capability query, the likely reading is that it means
"needs `FlashAttentionBackend`" and was written `("fa3","fa3")` because upstream
validates on Hopper.

That is a hypothesis. This mod exists to test it.

## Probe step

Before patching, the mod imports and reports:

- `torch.cuda.get_device_capability()`
- `sglang.kernels.ops.attention.flash_attention_v4_sm120` (the CC-12 shim)
- the **selected** CUTE package — `sglang.kernels.ops.attention.flash_attn.cute`
  by default (vendored in sglang), or `flash_attn.cute` when
  `SGLANG_INKLING_FA4_USE_PIP=1` — plus whether the other path is also present
- `is_flash_attention_v4_available()` and, if False, the captured import error
- the anchor count, so a base-image drift is visible before anything is written

Output is teed into `${MOD_LOGDIR}/probe-uno-fa4-sm121.log`. A green shim import
proves the Python resolves, **not** that the kernels are compiled for `sm_121`.
A probe that crashes (rather than reporting PASS/FAIL) writes an explicit
`PROBE-CRASH:` line to that log — do not read its absence of a FAIL as OK.

**Already answered no-GPU (2026-09-21):** inside a real sglang image the CC-12 shim
and the vendored CUTE package both import, and
`is_flash_attention_v4_available()` is `True`, so the Uno arm is not blocked on a
missing CUTE dependency. Whether the kernels are *compiled* for `sm_121` remains a
runtime question.

## Re-running with a different backend set

The mod is idempotent, including when `UNO_ATTN_BACKENDS` **changes** between runs
on the same node: it detects the existing `_UNO_ALLOWED_BACKENDS = (...)` and
rewrites just that tuple (`re-patched gate A -> B`). A lane-B run after a lane-A
run therefore needs no re-image and does not report a false "base image has
changed".

## Permissions

Mods run as **root** and this one imports the engine (to locate the anchor and to
prove the patch), which triggers flashinfer's JIT against the bind-mounted
`/cache/runtime`. It re-owns the **whole mount** at the end, or the next launch of
the same model key dies with `PermissionError`. See
`.swival/memory/sparkrun-notes.md` for the failure this prevents.

## Usage

Mounted by `recipes/ifm/k2-horizon-7b-fp8-uno-sglang.yaml`. Restore stock
behaviour without rebuilding anything:

```sh
UNO_FA4_GATE=0 sparkrun run ...   # leaves sglang unpatched
```

## Two lanes, different justifications

The gate is parameterized by `UNO_ATTN_BACKENDS` (default `fa3,fa4,triton`, the
union of both lanes so neither needs env propagation to run). `fa3` is
always retained so the knob can only ever widen the gate — a probe that could make
it stricter manufactures a "UNO rejected my backend" failure that looks like a
result and is only the knob.

| lane | why it might work | risk profile |
|---|---|---|
| `fa4` (default) | `create_flashattention_v4_backend` builds the **same** `FlashAttentionBackend` class with `fa_impl_ver=4`, and on capability 12 imports the SM12x-specialized FA4 kernels. Fast if it works. | Depends on the `flash_attn.cute` package being present; the speculative path through FA4 is unverified. |
| `triton` | `create_triton_backend` (`attention_registry.py:183-190`) has **no capability assert at all**, and `TritonAttnBackend` reads speculative state natively (`num_draft_tokens`, `speculative_num_steps`, `topk` at `triton_backend.py:212-214`). It is also already in `_PAGE_TREE_SPEC_BACKENDS`. | Portable Triton kernels, so far less likely to be arch-blocked — but likely **slower**, so a working-but-slow result is still a result. |

`triton` is the more defensible "should have never been arch-blocked" lane;
`fa4` is the one worth more if it works. Run `fa4` first, `triton` as the fallback.

```sh
# Lane A (default): fa4, nothing to set.
sparkrun run --recipe k2-horizon-7b-fp8-uno-sglang

# Lane B: triton. Both knobs must agree: attention_backend decides what sglang
# actually builds, UNO_ATTN_BACKENDS decides what the patched gate admits.
sparkrun run --recipe k2-horizon-7b-fp8-uno-sglang -o attention_backend=triton
```

and set `UNO_ATTN_BACKENDS` for the mod if you want the gate itself narrower than
the default. **Whether a recipe-local
`env:` block reaches mod scripts was not settled by source inspection** from this
box (mods become `pre_exec` entries via `core/mods.py:208`; the env plumbing into
that path was not traceable without running a launch), so this mod is written to
make the question moot:

1. **The default needs no env at all.** Lane A is the default, so a launch with no
   env set is a valid experiment. The default admits *both* lanes precisely so a
   lane-B run needs no propagation.
2. **The mod prints the gate it actually installed**, before anything else:
   `uno-fa4-probe: gate will accept ('fa3', 'fa4', 'triton')`. Read that line in
   `/cache/runtime/modlogs/probe-uno-fa4-sm121.log` to learn which backends were
   admitted — do not infer it from the recipe. If you set `UNO_ATTN_BACKENDS` and
   the log still shows the default, the variable did not propagate.
3. A knob that fails to propagate therefore **fails toward the default**, not
   toward a wrong-but-plausible result.

If propagation turns out to be absent, the fallback is a second recipe file for
lane B rather than an env override.

**Correctness gate on both lanes:** UNO advertises lossless decoding. A clean boot
plus a throughput number is not a result until output distribution matches the
non-spec baseline on the same prompts. Check TPF **and** correctness before quoting
any figure — a subtly broken verify path is fast and wrong.

## Knobs

| Var | Default | Meaning |
|---|---|---|
| `UNO_FA4_GATE` | `1` | `0` skips the patch entirely |
| `UNO_ATTN_BACKENDS` | `fa3,fa4,triton` | comma-separated backends to admit; `fa3` is always kept |

`UNO_ATTN_BACKENDS` is exported once and read by both the patch step and the
post-patch check, so the two cannot drift. The admitted set and the recipe's
`--attention-backend` must agree: the gate is a *permission*, `--attention-backend`
is the *selection*.

## Failure modes, all informative

| Symptom | Reading |
|---|---|
| probe reports the CUTE package FAIL | Uno is blocked on a **dependency**, not a patch. Nothing gate-related will help. (As of 2026-09-21 the stock image passes this, so this row is the one *not* expected.) |
| `UNO requires FA3...` still raised | Mod did not run, or anchor drifted. Check the probe's anchor count. |
| dies inside `create_flashattention_v4_backend` | FA4 import/kernel problem on 12.1. |
| dies in first decode step or graph capture | UNO depends on FA3-specific metadata the static reading missed. This is the interesting negative result. |

## Verification

Anchored and idempotent: the patch refuses to write unless the anchor matches
**exactly once**, and the mod re-imports `speculative_hook` afterwards to prove
the file still parses — so a bad patch fails at hook time instead of nine minutes
into a weight load.

Verify an anchor against a new base image with:

```sh
python3 -c "import sglang,pathlib,sys; \
  p=pathlib.Path(sglang.__file__).parent/'srt/arg_groups/speculative_hook.py'; \
  sys.exit(0 if p.read_text().count('!= (\"fa3\", \"fa3\")')==1 else 1)"
```

## Provenance

Written from source reading of SGLang at tag `v0.5.20`, **not** from a hardware
trial. Full derivation, including the GB10 decode roofline and the Uno
break-even acceptance rate, is in
`recipes/ifm/K2-7B-MODEL-OPTIMIZATION-WORK.md` §6.
