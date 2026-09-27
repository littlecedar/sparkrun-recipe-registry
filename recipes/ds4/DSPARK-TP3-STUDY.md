# DSPARK-TP3-STUDY — feasibility of DSpark at TP=3 / TP=6 (unaligned drafter divisors)

**Status:** study complete 2026-09-27. Verdict: **feasible**. One design survives; it is
a ~25-line mod addition plus recipe edits, not a kernel or engine project.
**IMPLEMENTED AND BOOTED 2026-09-27 (§12).** Design A shipped; the TP=3/TP=6
recipes carry DSpark k=3; **all three DSpark-eligible arms booted and served live** —
TP=3 C1/C4/C8 34.3/59.1/77.7 t/s (accept 2.40–2.50), TP=6 300K 44.5/72.5/115.3
(accept 2.43–2.50), TP=6 1M 35.3/—/118.4 (accept 2.37–2.44, booted as shipped),
every §7.3 gate held. Results: `.scratch/ds4/dspark_tp36/live/RESULTS.md`.
**Audience:** the agent who writes the mod next. Everything below is either cited to a
primary artifact or labelled. Do not build on anything labelled SPECULATIVE.

Evidence vocabulary is the repo convention (AGENTS.md header): VERIFIED / LIKELY /
SPECULATIVE.

---

## 1. The question

The TP=3 and TP=6 recipes ship **no-spec**: the DSpark drafter's own dimensions (64
attention heads, 128 routed experts) do not divide by 3 or by 6, and `SpeculativeConfig`
validation rejects the arm. Can a mod make DSpark work at TP=3 and TP=6?

## 2. Verdict

**Feasible.** The load-bearing discovery is that the *drafter reuses the target's model
code* — including the mod's virtual-heads padding — so the only thing missing is that the
drafter's **config** still declares the raw 64 heads / 8 groups. Dict `hf_overrides`
(what our recipes pass) are documented and verified to be **target-only** in this vLLM;
the drafter never sees them. Make the drafter see the same padding declaration and every
other unaligned divisor is already handled by files the mod installs today.

- TP=3 + DSpark: **proven externally** — upstream (tonyd2wild) served exactly this
  configuration as their TP=3 serving config (§3.5).
- TP=6 + DSpark: never booted by anyone (AGENTS.md §10 E7). Arithmetic is clean
  (§3.4); treat the first boot as the experiment.

## 3. Verified facts (the evidence base)

### 3.1 The mod already carries upstream's TP=3+DSpark patch set

`mods/mount-dsv41-exl3-patches/files/` is **md5-identical** to
`tonyd2wild/DeepSeek-V4.1-Flash-vLLM-DGX-Spark` `patch/exl3-tp3/` at commit `d45538f6`
(cloned at `.scratch/ds4/tonyd2wild-vllm/`), per both `MD5SUMS.txt` files:

```
1069303d attention.py      cc6e6017 dsv4_nvidia_model.py   c0329107 engram.py
4e80dfba  exl3_config.py   11faaa7a exl3_moe.py            af0f8447 flashinfer_sparse.py
0a14bee6  model_state.py   a9b73756 sparse_attn_indexer.py cc419353 sparse_swa.py
4b396a58  virtual_heads.py facb8300 vl_model.py            2ab4522b vocab_parallel_embedding.py
7e1027f1  weight_utils.py
```

The parts that matter for unaligned divisors, all in the shipped mod:

| unaligned divisor | where it is handled | mechanism |
|:--|:--|:--|
| drafter's 128 experts % 3 / % 6 | `dsv4_nvidia_model.py:984-1008` (mounted to `models/deepseek_v4/nvidia/model.py`) | with EP and EPLB off, FusedMoE keeps every expert on every rank; the expert-range divisibility assert is skipped only on that path. The comment names the DSpark drafter explicitly. |
| MoE intermediate width at TP | `exl3_moe.py` `create_weights`/`_tp_split` (mounted to `cuda_exl3/moe.py`) | uneven 128-block split of the intermediate dim (e.g. 2304/4 → [512,640,640,512]); no-op when already aligned |
| vocab split `divide(129280, tp)` | `vocab_parallel_embedding.py` | pads vocab to a multiple of lcm(64, tp) |
| main model 64 heads / 8 groups % 3 / % 6 | `virtual_heads.py` + hook in `attention.py:346-349` | config declares 72/9 (TP=3) or 96/12 (TP=6) + `virtual_heads_from`; `wq_b`/`wo_a` pad by repeating the last real group, `wo_b` pads zero columns; `attn_sink` self-pads −inf |

### 3.2 The drafter is built from the same modded model code

Image `littlecedar/dgx-spark-dsv41:exl3a` (vLLM `0.28.1rc1.dev388+g8a728663c`), read
2026-09-27 from the image (`docker run` on `.32`; md5s of the relevant files below):

- `vllm/models/deepseek_v4_1/nvidia/dspark.py` (`DSparkDeepseekV4Model.__init__`,
  line ~112): the drafter's layers are ordinary `DeepseekV4DecoderLayer` instances built
  with the **draft** config; `dspark.py:72` reads
  `config = vllm_config.speculative_config.draft_model_config.hf_config`.
- `vllm/models/deepseek_v4_1/nvidia/model.py:65` imports `DeepseekV4Attention` from
  `vllm.models.deepseek_v4_1.attention` — **the file the mod replaces**. So the
  drafter's attention is the modded class, and its `__init__` calls
  `wrap_attention(self, tp_size, config)` (`attention.py:346-349`) with the draft config.
  If the draft config carries `virtual_heads_from`, the drafter's `wq_b`/`wo_a`/`wo_b`
  pad exactly like the main model's.
- The drafter's weights arrive through the same param objects, so the installed
  `weight_loader` wrappers intercept `mtp.*` tensors too (`dspark.py` `load_weights`
  calls `param.weight_loader(...)` for every mapped name).
- `vllm/models/deepseek_v4_1/nvidia/model.py:96-102`: at layer index ≥
  `num_hidden_layers`, `DeepseekV4MoE` swaps in `dspark_n_routed_experts` (128) and
  `dspark_num_experts_per_tok` (3) — that is how the drafter's MoE is configured.
- The drafter's `load_weights` `attn_sink` narrow (`dspark.py:486-490`) slices the
  checkpoint's 64-entry sink with head ranges derived from the *declared* head count —
  the same arithmetic as the main model's loader (`model.py:701-702`), which boots at
  TP=3 today. Padded-head sinks stay −inf. Self-consistent.
- The drafter runs **inside every TP worker** (`v1/worker/gpu/model_runner.py:262` →
  `init_speculator(vllm_config)` → `DSparkSpeculator` → `load_dspark_model(...)` in
  `v1/worker/gpu/spec_decode/dspark/utils.py:34-76`). There is **no** separate draft
  worker and no use of `draft_parallel_config` at DSpark runtime.

Relevant image md5s (pre-mod): `speculative.py 879adcb3`, `config/model.py a3bde618`,
`deepseek_v4/nvidia/model.py d9874206` (→ `cc6e6017` after the mod),
`deepseek_v4_1/nvidia/model.py 4df8a4e2`, `dspark.py e6d89fa6`,
`spec_decode/dspark/speculator.py f24f3149`, `spec_decode/dspark/utils.py 9cae95bc`.

### 3.3 The root cause is config-only: dict `hf_overrides` never reach the draft config

Read from the image, 2026-09-27:

- `vllm/config/speculative.py:1237-1260`: the draft `ModelConfig` is built with
  `draft_hf_overrides = SpeculativeConfig.compose_draft_hf_overrides(
  self.target_model_config.hf_overrides)`.
- `vllm/config/speculative.py:1044-1067` (`compose_draft_hf_overrides` docstring):
  *"Callable overrides on the target are config-to-config transforms … and must also
  reach the draft config … **Dict overrides are target-specific key patches and are not
  applied to the draft.**"* If the target's overrides are a dict, the composed override
  is the bare `hf_config_override` (no dict keys).
- `vllm/config/model.py:1420-1430` (`verify_with_parallel_config`):
  `total_num_attention_heads % tensor_parallel_size != 0` → the exact ValueError that
  kills our TP=3/TP=6 arms. Called on the draft at `speculative.py:1786-1789` with
  `draft_parallel_config`.
- `vllm/config/speculative.py:1665-1694` (`_verify_and_get_draft_tp`): draft TP
  defaults to the target's TP unless `mlp_speculator`; explicit values must be 1 or the
  target TP (`:1686-1692`).

**Device-free probe** (run in the image, no GPU, 2026-09-27, checkpoint config.json +
flat dict override exactly as the TP=3 recipe passes it):

| variant | target heads seen | draft heads seen | `verify_with_parallel_config` @TP=3 |
|:--|--:|--:|:--|
| dict `hf_overrides` (today's recipe) | 72 / o_groups 9 | **64** | **FAILS** — "Total number of attention heads (64) must be divisible by tensor parallel size (3)" |
| `draft_tensor_parallel_size=1`, dict overrides | 72 | 64 | **PASSES** validation (see §5 for why this is a trap) |
| **callable** `hf_overrides` (sets the same keys) | 72 | **72 / 9** | **PASSES** |

The probe is the decisive fact: **nothing is wrong with the drafter's math — it is
never given the padded declaration.**

### 3.4 Drafter arithmetic at TP=3 and TP=6 (computed here from checkpoint headers)

Checkpoint `bot-lab-21/DeepSeek-V4.1-Flash-EXL3-3.5bpw-Pollard`, shard
`model-00044-of-00048.safetensors` header (HTTP Range read, 2026-09-27):

```
mtp.0.attn.wq_b.weight  F8_E4M3 [32768, 1280]   # 64 heads × 512 head_dim
mtp.0.attn.wo_a.weight  F8_E4M3 [ 8192, 4096]   # 8 groups × 1024 o_lora
mtp.0.attn.wo_b.weight  F8_E4M3 [ 5120, 8192]
mtp.0.ffn.experts.0.w1.weight I8 [2304, 2560]   # hidden 5120, intermediate 2304 (2×FP4/byte)
mtp.0.ffn.experts.0.w2.weight I8 [5120, 1152]   # 2304/2
```

The drafter's config fields come from the same `text_config` (`dspark_n_routed_experts:
128`, `dspark_num_experts_per_tok: 3`, `dspark_target_layer_ids: [37,38,39]`,
`dspark_block_size: 5`). So:

| quantity | TP=3 | TP=6 |
|:--|:--|:--|
| drafter heads 64 → declared | 72 (pad +8) | 96 (pad +32) |
| heads/rank | 24 | 16 |
| o_groups 8 → declared | 9 (pad +1) | 12 (pad +4) |
| groups/rank | 3 | 2 |
| drafter experts 128, EP off | all local ✓ (mod) | all local ✓ (mod) |
| drafter MoE width 2304 / TP | **768 = 128×6 ✓ aligned** | **384 = 128×3 ✓ aligned** |
| drafter vocab | aliased from target (no own embed/head) ✓ |

The drafter's MoE width is 128-aligned at both TPs — no uneven split even needed. The
Engram/indexer/compressor/hyper-connection pieces are replicated per rank (upstream
note, EXL3-TP3.md "Replicated on every rank already"), and the drafter has no Engram
layers (`dspark.py` builds `DeepseekV4DecoderLayer` without `engram_layout`).

### 3.5 Upstream's TP=3+DSpark is a measured, served configuration

`tonyd2wild` `docs/EXL3-TP3.md` (read at `d45538f6`):

- Bring-up row **exl3tp3a11 (2026-09-11)**: "Try 10 plus DSpark [k=5] … **up at 15:22
  ET**: the drafter loads past try 8's check on all three ranks"; model plus drafter
  **84.2 GiB per Spark** ("the drafter costs **3.9 GiB per rank**"); graph capture "15
  piecewise + 8 full sizes"; **KV pool 678,950 tokens** (vs 1,995,725 no-spec at the
  same gmu). VERIFIED.
- Try 8's failure is the exact failure we must avoid re-deriving: the drafter's
  128-expert MoE divisibility assert — already relaxed in our mod (§3.1).
- Results (their bench, their harness): TP=3+DSpark k=5 aggregate C1 46.0 → C6 152.9
  t/s, "ahead of boot 10 (four Sparks, release checkpoint) at every concurrency level".
  VERIFIED (their measurement, not ours).
- Their mechanism for the padded config was a **72-head config.json copy** built with
  hardlinks (`exl3/tools/reddie_prep_tp3.sh`: 72 heads / 9 groups +
  `virtual_heads_from`, top level and `text_config` both). That copy is what let their
  drafter see 72 heads — the same end-state design A below produces at runtime.

## 4. Root-cause chain (one paragraph)

TP=3/TP=6 DSpark arms die at `ModelConfig.verify_with_parallel_config`
(`config/model.py:1424-1430`) because the *draft* `ModelConfig` still declares 64 heads.
That happens because `SpeculativeConfig.compose_draft_hf_overrides` applies **callable**
target overrides to the draft but **not dict** overrides (`speculative.py:1044-1067`),
and our recipes pass a dict. Everything downstream of that — drafter attention padding,
MoE expert counts, MoE width alignment, vocab, sinks — is already handled by the
installed mod files (§3.1-§3.4).

## 5. Negative result: `draft_tensor_parallel_size=1` does NOT work for DSpark

AGENTS.md §10 **E8** proposed draft TP=1 as the cheap unlock. Probed and traced
2026-09-27 — it does not hold for DSpark:

1. `draft_tensor_parallel_size=1` **passes** `SpeculativeConfig` validation (probe, §3.3).
2. But `draft_parallel_config` is consumed only by the v1 *proposer* path
   (`v1/spec_decode/draft_model.py:72-89`, eagle-style separate draft workers). DSpark
   is an **in-worker speculator**: `DraftModelSpeculator`/`DSparkSpeculator` is built
   from the **worker's** `vllm_config` (`model_runner.py:262`) and the drafter model is
   built inside each TP worker (`dspark/utils.py:34-76`) with
   `get_tensor_model_parallel_world_size()` = the **target's** TP.
3. So after the config gate passes, the drafter's `DeepseekV4Attention.__init__` runs
   `assert 64 % 3 == 0` (attention.py:227) with 64 heads and dies at model build.
   `draft_tensor_parallel_size` is, for DSpark, a validation-only knob.

**Consequence for the next agent:** do not spend a boot on E8 as written. The E8 gate
("boot must reach `Capturing dspark CUDA graphs` and a non-zero Mean acceptance
length") remains the right acceptance gate for whatever design ships, but the mechanism
must be the one in §7. (AGENTS.md §10 E8 carries a dated correction pointing here.)

## 6. Why not other designs

| design | verdict | reason |
|:--|:--|:--|
| **A. mod patch: apply the dict `hf_overrides` to the draft config (env-toggled)** | **recommended** | smallest correct point; matches the mod's existing toggle style; end-state identical to upstream's proven config (72/9 drafter) |
| B. 72/96-head config.json hardlink copy of the checkpoint (upstream's approach) | workable, not recommended | zero code, but a second checkpoint identity collides with this repo's conventions: sparkrun `model:` is an HF repo id; `CUDA_EXL3_MODEL_PATH` and Engram row paths must be re-pointed; `MillionTokenContext`/sibling guards assume the 1M twins share a base; and it forks the cache on the NFS server for every future checkpoint update |
| C. `draft_tensor_parallel_size=1` | dead | §5 |
| D. pad the drafter to 129 experts with a dummy expert | unnecessary | the 128-expert assert is already relaxed on the no-EP path (§3.1); upstream considered this in try 8 and chose the relaxation instead |
| E. patch `vllm/config/model.py` to relax the heads check | rejected | it would let a 64-head drafter *build* at TP=3 and then crash at the attention assert (attention.py:227) — the check is not the only gate, and relaxing it hides the real requirement (padding) |

## 7. The design (what the mod-writing agent should build)

### 7.1 Mod change: one new file + two manifest lines

New file `mods/mount-dsv41-exl3-patches/files/config_speculative.py`, mounted over
`vllm/config/speculative.py`. It wraps `SpeculativeConfig.compose_draft_hf_overrides`
so that, when the target's `hf_overrides` is a dict containing `virtual_heads_from`
(gate on exactly that key — do not generalize), the returned callable applies
`hf_config_override` **and then** the dict keys to the draft config. Sketch:

```python
import functools, os

_DSV41_DRAFT_VIRTUAL_HEADS = os.environ.get("DSV41_DRAFT_VIRTUAL_HEADS", "1") == "1"

_orig_compose = SpeculativeConfig.compose_draft_hf_overrides


def _apply_dict_override(extra: dict, cfg):
    """Module-level so the partial below pickles (a closure does not)."""
    cfg = SpeculativeConfig.hf_config_override(cfg)
    for k, v in extra.items():
        setattr(cfg, k, v)
    return cfg


def _compose(target_hf_overrides):
    if (
        not _DSV41_DRAFT_VIRTUAL_HEADS
        or not isinstance(target_hf_overrides, dict)
        or "virtual_heads_from" not in target_hf_overrides
    ):
        return _orig_compose(target_hf_overrides)
    return functools.partial(_apply_dict_override, dict(target_hf_overrides))


SpeculativeConfig.compose_draft_hf_overrides = staticmethod(_compose)
```

Requirements copied from the surrounding code:

- **Pickle safety.** The composed override is sent to spawned engine-core processes
  (`speculative.py:1057-1067` docstring warns a closure fails with `Can't get local
  object`). The sketch above binds the dict via `functools.partial` over a **module-level**
  function — a plain closure does not survive pickling. **Verify this** by pickling the
  returned callable in the no-GPU probe before burning a boot.
- **Flat, not nested.** The dict keys land on the *flattened* `DeepseekV41Config`
  (AGENTS.md §7.3: `text_config` is flattened before overrides apply; the TP=3 recipe's
  flat override already proves the right shape). `setattr` on the config object is what
  `_apply_dict_overrides` effectively does for non-nested values.
- **Toggle default ON, `DSV41_DRAFT_VIRTUAL_HEADS=0` restores today's behaviour
  exactly** (mod house style; cf. upstream's `DSV41_DRAFT_SHARD_FILTER`).
- **Whole-file replacement, not an import hook.** The mod mounts whole files; keep the
  real image file and append/insert the block at module scope rather than shipping a
  stub. The wrapper must be installed at import time of `vllm.config.speculative` (it is
  imported by `vllm.config`, so module import order is safe), and it must be idempotent
  (guard with a module flag) in case the module is re-imported.
- `run.sh` needs no change: add the file to `files/mounts.txt`
  (`config_speculative.py vllm/config/speculative.py`) and `files/MD5SUMS.txt`. The
  fail-closed md5 gate and `.sparkrun-orig` backup then cover it automatically. Note
  `speculative.py` md5s differ between the exl3a image and any future image bump — the
  backup-then-verify ritual already handles "target exists"; consider also asserting
  the marker string `compose_draft_hf_overrides` is present post-install (mirrors the
  existing `DSV41_ENGRAM_DISK` assertion at `run.sh:189-196`).
- The file must not break non-DSpark recipes: with the gate on `virtual_heads_from`,
  TP=4 recipes (no overrides at all) are untouched; TP=2/other models untouched.

### 7.2 Recipe changes (after a probe boot, not before)

Apply to `deepseek-v4.1-flash-exl3-tp3-vllm`, `deepseek-v4.1-flash-exl3-tp6-vllm`,
and `deepseek-v4.1-flash-exl3-tp6-1m-vllm` (TP=3 has no 1M sibling):

1. Add the TP=4 `speculative_config` default, k=3 (the measured optimum, AGENTS.md
   AGENTS.md §7.7): `{"method":"dspark","num_speculative_tokens":3,"draft_sample_method":
   "probabilistic","rejection_sample_method":"block","enable_adaptive_verification":false}`.
2. Change the capture ladder to the k=3 ladder (guard `KCaptureSizes` enforces
   `max_num_seqs*(k+1)` = 32): `[3,4,6,8,9,12,15,16,18,20,21,24,28,32]`.
3. Update `metadata.description` (no more "NO DSpark"; state k=3 and that it is
   measured at TP=3 parity upstream / first-boot at TP=6). Guard
   `test_description_matches_spec_config` will enforce agreement.
4. Keep `--hf-overrides` exactly as-is (flat dict) — the mod now propagates it.
5. Do **not** add `--enable-expert-parallel` (unchanged rule; the relaxation is for the
   no-EP path, and EP at TP=6 is unmeasured over RoCE).
6. Update the header comments that currently explain DSpark is off.

**Sequence discipline (AGENTS.md §7.9 lesson):** prove the arm with `-o` overrides on
a live launch **before** editing the recipes, and prefer a single-node or smallest
change first. Suggested probe order:

```bash
# TP=3 probe arm (3 nodes), no recipe edit yet:
HOME="$H" sparkrun run recipes/ds4/deepseek-v4.1-flash-exl3-tp3-vllm --cluster ds4tp3 \
  -o speculative_config='{"method":"dspark","num_speculative_tokens":3,"draft_sample_method":"probabilistic","rejection_sample_method":"block","enable_adaptive_verification":false}' \
  -o compilation_config='{"cudagraph_mode":"FULL_AND_PIECEWISE","cudagraph_capture_sizes":[3,4,6,8,9,12,15,16,18,20,21,24,28,32]}' \
  --no-follow
```

### 7.3 Boot-log gates (all must hold; a missed gate is a negative result, not a tweak)

1. Mod log: `config_speculative.py` installed; `DSV41_ENGRAM_DISK` assertion intact.
2. No `Total number of attention heads (64) …` error. If it appears, the patch did not
   reach the draft config — debug the compose wrap, do **not** touch model.py.
3. `DSpark draft model loaded: 97 params` (the TP=4 count — same param set expected;
   a different count means a mapping problem).
4. `Engram DISK mode … rows [start,end)` **differs per rank** (8 hash cols at TP=3, 4 at
   TP=6) — unchanged rule (AGENTS.md §6.7 item 2).
5. `Capturing dspark CUDA graphs (FULL): 8/8` present (upstream captured 8 full sizes at
   TP=3).
6. `GPU KV cache size` read from the log; expect a **material drop** vs the no-spec arm
   (AGENTS.md §8) — record it.
7. **Mean acceptance length non-zero and > 1** on `Decode batch` lines. This is the E8
   gate: a boot that serves but accepts nothing (the EAGLE-on-DSpark-head failure mode)
   is a failure, reported as such.
8. Quality smoke: `27*43 → 1161`, plus the AGENTS.md §7.6 battery spot-check if a full arm is
   being adopted.

## 8. Expected memory and throughput (planning numbers, labelled)

- **Drafter cost at TP=3:** upstream measured **3.9 GiB/rank** with k=5 graphs and
  vision on (VERIFIED, their try 11). At k=3 the drafter weights are identical; graph
  scratch is if anything smaller. Budget ~4 GiB/rank.
- **TP=3 KV pool:** ours no-spec is 2,798,624 tok (booted 2026-09-24). Upstream's
  no-spec→DSpark ratio at the same gmu was 1,995,725 → 678,950 (−66%, k=5 + vision).
  Our arm should land well under that loss (we ship k=3, and our baseline differs), but
  **plan for ~1.6-2.0M tokens** and treat ≥ 2 concurrent 300K requests as the pass bar.
  Read the actual number from the log (AGENTS.md §6.5 trap).
- **TP=6 drafter cost:** 7.93 GB total drafter (AGENTS.md §2.2) / 6 ≈ 1.32 GB/rank plus
  attention buffers — the lightest split. KV pool 12,783,985 → expect roughly
  **11-12M tokens**. Computed here; no boot has ever carried DSpark at TP=6.
- **Throughput expectation (LIKELY, from upstream's TP=3 arm + our k-sweep):** TP=3
  C1 should rise materially over the no-spec 15.8 t/s (upstream: 24.2 → 46.0 aggregate
  at k=5 vs no-spec); C8 gains are possible but the k-sweep says the verify-window tax
  grows with batch — measure, don't assume. At TP=6, DSpark mainly helps C1/C4; C8 is
  already 108.0 t/s and bandwidth-bound (AGENTS.md §4.3).

## 9. Guards to update in the same change

`tests/test_ds4_recipes.py` (stdlib-only; keep it that way):

- `test_dspark_spec_config` — the `no_spec = {EXL3_TP3, EXL3_TP6, EXL3_TP6_1M}` set and
  its docstring encode the old negative result. After the recipes change, TP=3/TP=6
  arms must assert the positive contract instead: dspark present, k ∈ {1,2,3},
  `enable_adaptive_verification:false`. Keep the assertion meaningful (it once passed
  vacuously; every guard needs a negative control).
- `test_graph_capture_covers_max_seqs` / `KCaptureSizes` — already k-driven; they will
  pass once the ladder is changed. Verify the negative control still fires by rewriting
  the ladder in memory.
- `test_description_matches_spec_config` — will pass once descriptions are updated;
  add/keep a control that flips the description.
- Consider a new guard pinning the mod contract: `mount-dsv41-exl3-patches` must carry
  the `config_speculative.py` line in `mounts.txt` (and `MD5SUMS.txt`) for as long as
  any recipe relies on drafter virtual heads. Without it, a mod-file prune silently
  reintroduces the §3.3 failure.

## 10. Open questions and risks (ranked)

1. **Pickle safety of the composed override** (§7.1). Test device-free: build the
   target `ModelConfig` + `SpeculativeConfig` in the no-GPU container with the patched
   module and `pickle.dumps(speculative_config)` — the draft ModelConfig and its
   overrides must survive. A failure here shows up in the boot as a spawn-time
   `Can't get local object`, which costs a boot.
2. **`_apply_dict_overrides` semantics vs plain setattr.** `_apply_dict_overrides`
   recurses into nested `PretrainedConfig` values; our keys (`num_attention_heads`,
   `o_groups`, `virtual_heads_from`) are scalars/dicts on the flattened config, so
   plain setattr matches. If a future key is a nested config, reuse
   `ModelConfig._apply_dict_overrides` logic instead of setattr.
3. **Drafter-attention numeric parity of the padding at TP=6.** Upstream's offline check
   (max rel. error 3.4e-6 vs 64-head math) was done for TP=3's 72/9. 96/12 repeats the
   same construction (`pad_tensor` dup/zero), but nobody has boot-verified 96/12 on the
   drafter. The quality battery is the check.
4. **Acceptance at TP=3/TP=6.** Assumed identical to TP=4 (same drafter weights,
   same k=3); nothing in the drafter is TP-dependent by construction, but the aux
   hidden states come from target layers 37-39 whose attention is *padded* — the
   padded groups contribute zeros, so the drafter input should be numerically the same
   modulo fp8 reduction order. SPECULATIVE that acceptance is unchanged; verify against
   the TP=4 k=3 per-position curve (0.66/0.39/0.21, `ksweep/ALL_BOOTS.json`).
5. **Indexer/`topk_indices_buffer` sizing** is per-worker and replicated — unaffected by
   TP (buffer dim is `max_num_batched_tokens × index_topk`), no change expected.
6. **Adaptive verification stays off** (FlashInfer #5015 hangs SM120 sparse MLA on
   padded spec batches). Non-negotiable; the recipe string already pins it.
7. **k must be ≤ 5 or a multiple of 5** (drafter `n_predict = dspark_block_size = 5`).
   k=3 satisfies it; do not "fix" k=4/6 here.

## 11. Handoff checklist

- [x] Write `mods/mount-dsv41-exl3-patches/files/config_speculative.py` per §7.1
      (toggle `DSV41_DRAFT_VIRTUAL_HEADS`, default ON; pickle-safe). **Done
      2026-09-27** — whole-file replacement of the image's `config/speculative.py`
      with our block appended; md5 `c542580c`.
- [x] Add to `files/mounts.txt` + `files/MD5SUMS.txt`; add a post-install marker
      assertion to `run.sh` (grep for `compose_draft_hf_overrides`). **Done** —
      `run.sh` now dies if `DSV41_DRAFT_VIRTUAL_HEADS` or `compose_draft_hf_overrides`
      is absent from the installed `config/speculative.py`; the fail-closed md5 gate
      was exercised (tampered file → `FATAL: vendored file checksum mismatch`).
- [x] Device-free probe (no GPU): with the patched module, dict-override arm → draft
      heads == 72 (TP=3) / 96 (TP=6); `verify_with_parallel_config` passes;
      `pickle.dumps` of the SpeculativeConfig succeeds; toggle off → today's failure
      reproduces (the negative control). **Done** — `.scratch/ds4/probe_draft_virtual_heads.py`
      + `dspark_tp36/PROBE-RESULTS.txt`; all gates pass, toggle off raises the exact
      "64 … must be divisible by … 3/6" errors. A real `SpeculativeConfig` also builds
      from each recipe's rendered JSON (`dspark_tp36/probe_spec_config_builds.py`).
- [x] `bash -n mods/mount-dsv41-exl3-patches/run.sh`;
      `python3 -m py_compile` the new file; md5 table updated. **Done** — and the mod
      was run end-to-end in a throwaway container: 14 files installed, both marker
      assertions logged.
- [x] Probe boot TP=3 with `-o` overrides (§7.2), all §7.3 gates; capture
      accept-length and KV numbers into `.scratch/ds4/`. **DONE 2026-09-27** — booted
      and served; KV 1,896,721, accept 2.40–2.50, C1/C4/C8 34.3/59.1/77.7.
      `.scratch/ds4/dspark_tp36/live/`.
- [x] Probe boot TP=6 the same way (first-of-kind; single boot, all gates).
      **DONE 2026-09-27** — first DSpark boot at TP=6 anywhere; KV 12,006,501,
      accept 2.43–2.50, C1/C4/C8 44.5/72.5/115.3.
- [x] Boot the TP=6 **1M** sibling with DSpark, since it ships the spec config in its
      own defaults. **DONE 2026-09-27** — booted exactly as shipped (no `-o`); KV
      13,054,046, accept 2.37–2.44, C1/C8 35.3/118.4, quality smoke correct.
- [x] Edit the three recipes + descriptions; update guards (§9) **with negative
      controls**; run the full ritual (AGENTS.md §8.3): unittest discover,
      `sparkrun recipe validate` (no `--strict`) on all five, rendered-line grep.
      **Done** — 238 unittests pass (2 new guard classes + 4 new negative controls),
      all five recipes validate rc=0/no warnings, rendered lines carry the k=3
      `--speculative-config` and the correct `--hf-overrides`.
- [x] Update AGENTS.md: §7.3/§7.4/§7.5 (no-spec notes retired, DSpark shipped but
      unbooted), §10 E7 (solved in design) / E8 (closed as a dead end), §5/§6.7/§8.1
      (14 files, new guard). **Done.**

## 12. Implementation record (2026-09-27)

The boot gates in §7.3 are the only outstanding items; everything else is on disk.

| artifact | change |
|:--|:--|
| `mods/mount-dsv41-exl3-patches/files/config_speculative.py` | NEW; image `config/speculative.py` + appended block (md5 `c542580c`). Wraps `compose_draft_hf_overrides` to apply a target dict `hf_overrides` to the draft config when it carries `virtual_heads_from`. Toggle `DSV41_DRAFT_VIRTUAL_HEADS` (default `1`); idempotent; pickle-safe via `functools.partial` over a module-level fn. |
| `files/mounts.txt` / `files/MD5SUMS.txt` | `config_speculative.py config/speculative.py` mapped (md5 `c542580c`); `mounts.txt` md5 row refreshed. |
| `run.sh` | post-install assertion: `DSV41_DRAFT_VIRTUAL_HEADS` + `compose_draft_hf_overrides` present, else die. |
| `deepseek-v4.1-flash-exl3-tp3-vllm.yaml` | DSpark k=3 spec config added, capture ladder → k=3 set, description + comments rewritten. Booted live 2026-09-27 before the edit (via `-o`), then edited. |
| `deepseek-v4.1-flash-exl3-tp6-vllm.yaml`, `…-tp6-1m-vllm.yaml` | same; 1M stays identical to 300K except `max_model_len`. TP=6 300K booted live 2026-09-27 (first-of-kind). |
| `tests/test_ds4_recipes.py` | `test_dspark_spec_config` rewritten to the positive contract; `ModDraftConfigContract` added; 4 new negative controls. |

**Evidence (live boots, image `exl3a`, 2026-09-27):**
- TP=3 (`ds4tp3` = .32/.33/.34): booted and served. Medians C1 34.3 / C4 59.1 /
  C8 77.7 t/s, accept length 2.40–2.50, KV 1,896,721 tok, draft `97 params`,
  dspark graphs `8/8`, Engram rows differ per rank, `27*43 → 1161`.
- TP=6 (`ds4six` = .30–.35): first DSpark boot at TP=6 anywhere. C1 44.5 / C4 72.5 /
  C8 115.3 t/s, accept 2.43–2.50, KV 12,006,501 tok, same gates.
- Raw: `.scratch/ds4/dspark_tp36/live/{RESULTS.md, tp3_serve.log, tp6_serve.log,
  tp3_accept.txt, tp6_accept.txt, tp3_kv.txt, tp6_kv.txt, measure_tp3.out,
  measure_tp6.out}`.

**Evidence (device-free, image `exl3a`, 2026-09-27):**
- `.scratch/ds4/probe_draft_virtual_heads.py` + `.scratch/ds4/dspark_tp36/PROBE-RESULTS.txt`
  — fix ON: draft heads 72/96, `verify_with_parallel_config` passes at TP=3/TP=6,
  override pickles (182 B); control OFF: draft stays 64, the exact §3.3 ValueError
  reproduces.
- `.scratch/ds4/dspark_tp36/probe_spec_config_builds.py` — each recipe's *rendered*
  `--speculative-config` builds a real `SpeculativeConfig` at TP=3 (draft 72/9) and
  TP=6 (draft 96/12).
- Mod install run in a throwaway container: `Installed 14 file(s)` + both assertions;
  a tampered vendored file aborts before install.

## 13. Evidence index

- Mod ↔ upstream identity: `mods/mount-dsv41-exl3-patches/files/MD5SUMS.txt` vs
  `.scratch/ds4/tonyd2wild-vllm/patch/exl3-tp3/MD5SUMS.txt` (compared 2026-09-27).
- Upstream TP=3+DSpark bring-up and numbers: `tonyd2wild` `docs/EXL3-TP3.md` (rows
  exl3tp3a8-a11, serving config try 11) at commit `d45538f6`.
- Image source lines: quoted in §3.2/§3.3 with file:line, read from
  `littlecedar/dgx-spark-dsv41:exl3a` on 2026-09-27 (md5s listed in §3.2).
- Device-free probes (dict vs callable vs draft_tp=1): run 2026-09-27 in the image
  against the real checkpoint config; outputs summarized in §3.3/§5.
- Drafter tensor shapes: shard `model-00044-of-00048.safetensors` header via HTTP
  Range (§3.4).
- Our boots: `.scratch/ds4/boottp3/launch.log`, `boottp6/launch.log`, `boot1/launch.log`
  (TP=4 DSpark behaviour, accept length, graph capture).
- k-sweep data: `.scratch/ds4/ksweep/ALL_BOOTS.json`, `PREREGISTRATION.md`.
- Implementation probes (2026-09-27): `.scratch/ds4/dspark_tp36/` —
  `probe_draft_virtual_heads.py` (+ `PROBE-RESULTS.txt`, `run_probe.sh`),
  `probe_spec_config_builds.py`, and a snapshot of the shipped
  `config_speculative.py`.
