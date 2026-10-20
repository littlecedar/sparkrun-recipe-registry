# Qwen4 lane — the two engine issues, root-caused (2026-10-19)

Two lane questions had been carried as "unexplained". Both are now resolved from source with boot
evidence. This note is the durable record; the working narrative lives in the git-ignored `.scratch/q4/`
snapshots cited below.

Evidence vocabulary: **VERIFIED** = read from source at the image's reported base commit, or measured
on a boot; **HYPOTHESIS** = code-derived, not observed.

## 1. The shared-expert `_scale` blocker — understood, and its fix ships

**Symptom (VERIFIED, recorded traceback).** `RuntimeError: a Tensor with 51200 elements cannot be
converted to Scalar` at image `qwen4_exp.py:2136`. `51200 = 640×80`: the shared expert's
`mlp.shared_expert.gate_proj.weight_scale`, U8 `[640, 80]`, an ue8m0 MXFP8 block scale.

**Mechanism (VERIFIED).** The checkpoint names the scale `weight_scale`; the engine registers
`weight_scale_inv` (`fp8.py:580-595` upstream; `use_mxfp8` forces a `[1, 32]` block, `fp8.py:270-275`).
The loader's ignore list has `_weight_scale` (underscore — the FusedMoE names) and `.weight_scale_inv`
but **not `.weight_scale` with a dot** (`qwen4_exp.py:1839-1852`), so the tensor reaches the "skipped
scale must be 1.0" branch (`:2115-2118`), where `.item()` raises inside the assert's *condition* — the
name never reaches the log, which is why four static diagnoses failed. The second half is gate/up
stacking: the shared expert's `gate_proj`/`up_proj` fuse into `gate_up_proj` *after* any pre-dispatch
hook (`stacked_params_mapping`, `:1809-1821`), so a rename hook must leave an un-fused stem intact and
let stacking match.

**The fix ships.** `fix-labquant-mxfp8-weight-scale-name` rewrites `<X>.weight_scale →
<X>.weight_scale_inv` only when a destination exists (direct or via stacking) and covers the GDN/QKV
pairs. Measured live 2026-10-19: 144 shared-expert remaps plus the attention/GDN remaps
(`serve-rank0.log:48-247`), numeric checks relL2 0.029 / corr 0.99959 on the shared expert, and the
shipped suite boot shows zero `UNPLACED`/`Expected 1.0` lines and passes contract/house/needle/ARC/
GSM8K/tools/W4-soak (`~/benchmarks/qwen4-labq-suite-20261018/`).

**`diag-qwen4-unplaced-scales` was insurance, not a workaround — and it is now retired
(2026-10-20).** The control ran: `recipes/qwen4/zz-labq-no-diag.yaml` (job
`1895030211ea0500_3510a5e0d37d`, TP=2 on the pair) served `/v1/models` 200 in ≈670 s, answered a chat
request, and passed house **37/37**; its serve log's only `_scale` lines are the fix mod's own benign
`[remap] …weight_scale -> …weight_scale_inv` entries, with no `unplaced` and no `AssertionError`. So the
assert at `qwen4_exp.py:2136` does not fire on the fixed chain, the mod is deleted, and the probe recipe
stays as the recorded control (`~/benchmarks/qwen4-nodiag-20261020/`).

**Upstream etiquette.** The nameless assert is an ergonomics defect: log `name` before touching
`.item()`, or reject multi-element non-`_inv` scales with a message that names them.

## 2. The QSA-prefill CUDA-graph crash — not the projection, not the leaves

**Symptom (VERIFIED, 2026-09-18/20).** Prefill graph capture dies at
`qsa/metadata.py:141 get_prefill_mqa_inputs` with `Cannot copy between CPU and CUDA tensors during CUDA
graph capture unless the CPU tensor is pinned`. `PREFILL_CUDA_GRAPH_CAPTURE_FAILED` is the breakable
context manager's *log* (`runner_backend_utils/breakable_cuda_graph/context.py:34-47`), not the raising
line — the lane's earlier cite conflated them.

**Mechanism (VERIFIED).** `get_prefill_mqa_inputs` calls `sequence_lengths.tolist()` and then builds
per-sequence `index_select` + `torch.cat` results whose leading dimension is data-dependent — both
illegal during capture. Its decode counterpart *has* the capture-safe branch (`if self.is_cuda_graph:`
returns prebuilt `graph_*` buffers, `metadata.py:201`), and the same class guards its other host sync
with `get_is_capture_mode()` (`qsa_indexer.py:179-184`, `:413-416`). The asymmetry is in the source.
Pinning would not fix it: the captured output's shape depends on request composition at replay
[INFERENCE, strong].

**The `EXTRA_LEAVES` hypothesis is falsified, not just untested.** That knob rewrites an MXFP8
projection to BF16; nothing in `get_prefill_mqa_inputs` reads the projection, and the demoted
`index_qk_proj` boot (`11b2c8b941e89cb9`) crashed identically with the projection verified BF16. The
live tree today ships the knob empty (`demoted: 72, dropped_scales: 72, ignore_added: 144`, no extra
leaves), so `EXTRA_LEAVES` is dead weight: its only stated purpose is falsified. Delete it, or keep it
only behind a named bisect ticket. The demote mod's **floor** path is unaffected and still required.

**Today the crash path is unreachable.** The engine disables prefill graphs for this multimodal
checkpoint (`server_args.py:4723-4736`, logged `Breakable CUDA graph is incompatible with multimodal
model`), and an explicit `--cuda-graph-backend-prefill full` is accepted then disabled by the EAGLE
rule. `--cuda-graph-backend-prefill disabled` in the recipe is redundant but self-documenting; no perf
lever is lost (three identical effective configs span 8.6 % at C2 — the inter-boot floor). Why it
crashed in September is a HYPOTHESIS: the then-shipped `skip-labquant-vision-tower` made the model
text-only, so the multimodal disable rule did not fire and capture engaged.

**Fix ownership.** Upstream only: a capture-safe `get_prefill_mqa_inputs` (static padded `graph_*`
buffers filled in `capture_prepare`, mirroring decode) or an explicit refusal to capture prefill with a
QSA indexer.

## Consequences for the register

- The diagnostic item shrinks to two boots/edits: run `zz-labq-no-diag` (retire the diag if clean), and
  delete `EXTRA_LEAVES` (no boot needed; code + docs).
- Do not spend a boot on the `EXTRA_LEAVES` theory again — it is measured-negative.
- The two mods' READMEs and the shipped recipes' "removable once … understood" comments should say
  "understood; insurance" instead.