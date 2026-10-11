# Qwen3.8-27b on DGX Spark: does `mamba_ssm_dtype: bfloat16` change the model's outputs?

Extracted verbatim from `QWEN3-MODEL-OPTIMIZATION-WORK.md` §12 on 2026-09-21, because that
section had grown past half the document and its two threads -- **pool sizing** and **state
dtype numerics** -- serve different questions. Section numbers are unchanged: a reference to
**§12.12** means the section in *this* file and remains accurate in every artifact that cites it.
Read §12.1–12.3 and §12.5–12.10 in the work doc for the pool-sizing thread, and §12.13 there for
how delegated claims in this area were verified.

**The finding, in one paragraph, for readers who will not read the six probes.** The recipe asks
sglang to store the recurrent (Mamba/GDN) state in bf16 while the checkpoint declares float32, and
the flag provably wins: the pool allocation halves (72.04 → 144.07 MiB/slot across real boots).
Whether that changes anything the model *says* turned out to be extraordinarily hard to answer,
and three successive "clean explanations" of the null were each refuted by the next probe. What
survives: on the path that actually **reads** stored state, bf16 and fp32 produced
**bit-identical logprobs** (§12.12); the perturbation introduced by bf16 storage is real and about
one bf16 quantum, **~1.7e-3** relative (§12.14); and the chunk kernel's internal scratch buffer
takes its dtype from `k`, not from the flag, so the flag cannot affect that buffer at all (§12.14
point 3). **"Bit-identical here" is not "safe"** -- it means undetectable by these instruments on
this corpus, which is a resolution-threshold statement, not a safety one. That distinction is the
single most important sentence in this file and it is repeated where each null is reported.

**One correction carried forward from §12.14 to the pool-sizing thread:** "KV read is not a factor
on this recipe" is FALSE at high concurrency. It was ruled out from a single-stream null and
§12.16 measures it as the dominant throughput factor at 13 streams. The two threads share that
error, so it is stated here as well as there.


### 12.4 `mamba_ssm_dtype`: the flag works; the interesting part is what it overrides

`server_args.py:2617-2624` accepts `{float32, bfloat16, float16}` (`:2621`), **default `None`**
(`:2616`) — and
`None` is load-bearing, because the resolution chain is

```
env SGLANG_MAMBA_SSM_DTYPE  >  config.mamba_ssm_dtype  >  "float32"   (configs/mamba_utils.py:47-107)
```

and `--mamba-ssm-dtype` reaches the pool *only* by setting that env var
(`arg_groups/serving_hook.py:396-397`, inside `handle_environment_variables`). So:

- **The flag is honoured.** `configs/qwen3_next.py:311-312` builds the cache params with
  `dtype=mamba2_state_dtype(self)`, passing the config explicitly rather than relying on the
  `default_factory`, and step 3 of `mamba2_state_dtype` overrides the config value with the env
  var. **VERIFIED by reading the chain end to end.**
- **No SM100/GB10 gating is involved in the dtype itself**, which was the standing worry in §11.
  The capability checks near this path (`arg_groups/attention_hook.py:239-248,285-310`) gate
  *kernel backend selection* on `mamba_ssm_dtype` — they do not gate the dtype. `is_sm100`
  resolves to `is_sm100_supported` (`runtime_context.py:1780` → `utils/common.py:296-300`), whose
  `device_capability_majors` is **`[10]`** and so **excludes 12**. Two nearby symbols are easy to
  confuse with it and are *not* what this path uses: `is_sm100_or_sm110_supported` is `[10, 11]`
  (`:303-309`, and its own comment says it exists for the flash_attn.cute absorbed-MLA `qv`
  argument), and `is_blackwell_supported` is `[10, 11, 12]` (`:283-290`) — **which does include
  GB10**, so a future refactor that swaps `is_sm100` for `is_blackwell` would silently re-enable
  the SM100 branch here. `is_sm120_supported` is the separate flag at `:291-295` (`[12]`).
  So on GB10 the SM100 auto-default at `attention_hook.py:239-248` is dead — its third conjunct
  is `get_platform().is_sm100`, i.e. `[10]`.
  **Two claims in the first draft of this bullet were wrong, and the corrected version is more
  interesting than the original.** The asserts at `attention_hook.py:285-295` and `:300-310`
  require **`bfloat16`**, not `float16` (they raise when `decode`/`verify == "flashinfer"` *and*
  `mamba_ssm_dtype != "bfloat16"` *and* `capability[0] >= 10`), and `mamba_hook.py:26-35` is not
  the right citation either — the genuine `float16` requirement is `mamba_hook.py:29-36`, gated on
  `--enable-mamba-cache-stochastic-rounding`, which this recipe does not set. More importantly,
  **those asserts are not made inert by capability**: their capability test is `>= 10`, which
  GB10's major 12 *passes*. They are inert for two other reasons — `decode` resolves to
  `"triton"` (`:260`, from `linear_attn_backend`'s default `"triton"` at `server_args.py:2691`;
  the recipe sets only `attention_backend: flashinfer`, which is the *softmax* backend and does
  not touch this path), **and** the recipe's `bfloat16` makes the dtype conjunct false. So the two
  mechanisms differ and re-arm differently: the **auto-default** dies on capability (`[10]`
  excludes 12) and would come back if anyone swapped in `is_blackwell_supported` (`[10, 11, 12]`,
  `:283-290` — **which includes GB10**); the **asserts** are held off by the dtype value, and
  would fire immediately if someone passed `--linear-attn-decode-backend flashinfer` *and* changed
  `mamba_ssm_dtype` to `float32`. Confusing "capability-gated" with "value-gated" here would make
  a future change look safe when it is not. `is_sm120_supported` is at `:291-295` (`[12]`).
- **What the flag is actually doing:** the checkpoint declares
  `text_config.mamba_ssm_dtype = "float32"` (read from
  `.scratch/qwen3-27b/artifacts/config.json`; absent from the root config). The recipe therefore
  *overrides a value the checkpoint explicitly requests*, halving SSM state precision to gain
  slots. That is a real accuracy decision, not a free perf knob, and it has never been
  measured. `attention_hook.py:450-456` carries sglang's own warning for the analogous case:
  "validate long-sequence accuracy and throughput."
- **fp32→bf16 is a 1.962× saving, not 2.000×**: the conv half of `mamba_cache_per_req` is a
  separate knob (`SGLANG_MAMBA_CONV_DTYPE`, default `bfloat16`, `environ.py:1306`) and does not
  halve. `p` is 74.81 MiB (bf16) vs 146.81 MiB (fp32). Use 1.962 when comparing those two boots.
- **The ordering hazard is closed** (was the last NOT DETERMINED in this section). The worry was
  that `handle_environment_variables` might set the env var *after* the process building the pool
  had already read it. It cannot: `handle_environment_variables` runs inside
  `run_resolution_pipeline` (`pipeline.py:340`), reached via `resolve_once()`
  (`server_args.py:3744`), and `_launch_subprocesses` calls `server_args.resolve_once()` at
  `entrypoints/engine.py:1064` (enclosing function is `_launch_subprocesses`, `:1040` — not
  `__init__`; the other two call sites are `http_server_engine.py:19` and a
  dummy-model probe at `runtime_context.py:1193`) — **before** the first `mp.Process` spawn at
  `:1134` / `_launch_scheduler_processes`. The scheduler therefore inherits an environment that
  already carries `SGLANG_MAMBA_SSM_DTYPE`. **VERIFIED by reading each hop.** The one thing I did *not*
  verify is the spawn's environment handling in detail: `mp.Process(...)` takes no `env=` argument
  anywhere in `engine.py` (checked), so it inherits `os.environ`, but I did not confirm there is
  no later `os.environ.clear()`/`execve` with a rebuilt environment between spawn and pool build.
  That residual is small and the `K(fp32)/K(bf16) ≈ 0.5` test in §12.5 discriminates it either
  way, which is exactly why that test was designed to be `T`-free. Note the claim this supports is
  only that **the flag reaches the pool** — it says nothing about whether overriding the
  checkpoint's declared `float32` is *wise*, and §12.4's accuracy caveat still stands unmeasured.

### 12.11 Does `mamba_ssm_dtype bfloat16` change what the model outputs? — phases 12 and 14, and the answer is about the instrument

Phase 12 booted the shipping recipe (bf16 state) on one node and the same recipe with
`-o mamba_ssm_dtype=float32` on the other, then greedy-decoded 12 fixed prompts against both,
twice each, through SSH tunnels. Tooling: `.scratch/qwen3-27b/ssm_dtype_neutrality.py`, driver
`run_phase12.sh`, artifacts `.scratch/p12-0920/` (transcripts + full server logs).

**The self-reproduction null passed cleanly**: each arm, probed twice in the same window, returned
**12/12 byte-identical completions**. That is worth knowing on its own — this server *is*
deterministic at `temperature=0` under continuous batching at c = 1, which is not something I had
evidence for and is a precondition for any behavioural comparison being meaningful at all.

**Then the two arms diverged: 1 of 12 prompts identical, median first divergence at character 70,
median edit distance 143.** Example, prompt 4 (`List the first 8 prime numbers`):

```
bf16: '10th prime number?\n\nThe 10th prime numbe...'
fp32: 'smallest prime number?\n\nThe smallest pri...'
```

**And that result, as collected, cannot be attributed to the dtype.** The two arms ran on
**different nodes**, so dtype and node are perfectly confounded: "11/12 prompts diverge" is equally
consistent with "bf16 state changes behaviour" and with "node A differs from node B." The error is
the same class as §12.10's cross-node throughput pair — but worse here, because throughput has a
c = 8 null to catch it and this design had none.

**Why the divergence is not the strong evidence it looks like.** Greedy decoding over 96 tokens
amplifies *any* perturbation: a one-bit difference in a single logit produces a completely
different continuation within tens of tokens. A median edit distance of 143 is therefore roughly
what **any** difference produces — including moving to another machine. **A large edit distance is
not a large numerical change; it is what amplification does.** The interesting quantity would have
been logit magnitudes or per-token divergence depth, not edit distance, and I measured neither.

**Phase 14 ran, and the pre-registered interpretation rule fired on the first branch.** Driver
`run_phase14.sh`, artifacts `.scratch/p14-0920/transcripts/`. Three boots; the dtype comparison is
made from **saved transcripts**, because node `node-free-1` must stop bf16 before it can boot fp32 — so
"same node, different dtype" cannot be probed in one live invocation and has to be reconstructed
from disk (`--compare`).

| comparison | design | identical prompts | median first-diff char |
|---|---|---|---|
| **NULL-1** | same node, same server, two passes | **12/12** | — |
| **NULL-1b** | same on `node-free-2`, two passes (+ a re-probe hours later, also 12/12) | **12/12** | — |
| **NULL-2** | **identical config, different node** | **1/12** | 77 |
| **EFFECT** | same node (`node-free-1`), bf16 → float32 | 2/12 | 73 |

Read the rows in that order, because the ordering is the whole result:

- **NULL-1 establishes the server is deterministic.** Byte-identical across passes on the same
  server, and `node-free-2`'s re-probe after a full boot-swap still 12/12. So divergence below is not
  run-to-run noise.
- **NULL-2 is the finding: two nodes, byte-identical configuration, produce different greedy
  output on 11 of 12 prompts.** Median divergence at character 77 of ~315 — about a quarter of the
  way into the completion. The two machines are hardware-indistinguishable on everything I can
  query (same driver 580.173.02, same VBIOS, same kernel, same 127,600,812 kB RAM), so this is not
  a misconfigured node; it is what "a different GPU" costs a greedy rollout.
- **EFFECT is *smaller* than NULL-2** (73 vs 77). bf16-vs-fp32 moves the output *less* than moving
  rooms does.

**Therefore phase 12 measured nothing, exactly as its own falsifier predicted, and the dtype
question remains open — but for a sharper reason than "it was confounded."** The instrument has no
power at this effect size. Greedy decoding over 96–315 tokens is an **amplifier**: any perturbation,
including a different machine's floating-point history, destroys the continuation within tens of
tokens. Comparing amplified outputs cannot rank the perturbations that caused them. The edit-distance
number I reported in the phase-12 write-up (`median edit distance 143`) was therefore never a
measure of a numerical change; it was a measure of the amplifier, and it would have looked equally
large for a null.

**A better reading of the node null, and it turns phase 14 from a null result into a useful one.**
Calling NULL-2 "a confound that destroyed the experiment" is too pessimistic, because the decision
this feeds is not the philosophical *"does bf16 change the numerics?"* — it obviously does, half the
mantissa bits — but *"is the change large enough to matter?"*, and that question needs a **yardstick**.
A user deploys this recipe on *their* Spark, not on this test node. The numerical variation they get
from moving between machines is real, unavoidable, and accepted without complaint. NULL-2 measures
exactly that quantity. So the null is not merely a control to be survived, it is a **reference scale
the effect can be normalised against**:

- **effect ≫ null** → bf16 perturbs the model *more than changing machines does*. That exceeds the
  heterogeneity users already tolerate for free, so it is a defensible reason to care.
- **effect ≈ null** → bf16's change is *within the same class as ordinary deployment variation*.
  That is not "no effect" and it is not "safe", but it is the strongest statement this experiment
  can produce, and it is decision-relevant: it says the dtype is not the largest source of
  numerical variation in the deployment.

Phase 14 therefore did not measure *nothing* — it accidentally measured a calibration point, and its
own conclusion ("the dtype question stays open") was understated because I framed the null purely as
an obstacle. **Caveat that limits the yardstick:** its size depends on *why* the two nodes differ
(kernel autotuning, non-deterministic reductions, clocks), so if these two happened to be unusually
divergent the scale is inflated and `effect ≈ null` is a weaker statement than it looks. Always report
the null's **absolute** magnitude, not only the ratio — which is why phase 16 prints nulls and effects
as separate rows rather than one normalised number.

**What would have power, and it is cheap.** Teacher-forced per-token logprobs over a fixed prompt
(`.scratch/qwen3-27b/logprob_probe.py`): no sampling, so no rollout, so no amplification — token *i*'s
logprob depends only on an identical prefix, and a real SSM-state perturbation appears as a
**continuous** distribution over |Δlogprob| instead of a cliff. It can resolve ~1e-6 differences that
greedy text cannot see at all. The synthetic selftest (`selftest_logprob_probe.py`) verifies the
comparison path against known deltas before any boot is spent on it — justified, because **this
instrument family has already failed silently twice**: once when a null was satisfiable by total
request failure (12 identical `__ERROR__` strings are "identical"), and once when 12 transcript rows
were indexed as `[key, text]` pairs when they were plain strings, collapsing the comparison to the
first two *characters* and printing "identical 2/2". Neither failure raised an error; both produced
plausible numbers.

**Reusable lesson, and it generalises past this arm.** *A null control must be expected to pass for
the right reason, and an effect must be compared against the largest null, not the most convenient
one.* NULL-1 passing is what made NULL-2's failure interpretable; NULL-2 is what made EFFECT
uninterpretable. Had I run only EFFECT against NULL-1 — the obvious design — I would have reported
"bf16 changes model output on 10 of 12 prompts" as a discovery. **The second control was not
optional rigour; it was the difference between a finding and an artifact.**

**Standing conclusion for the recipe, unchanged by phases 12 *and* 14:** the asymmetry runs the
other way from how it is usually stated. `mamba_ssm_dtype: bfloat16` **buys** concurrency — it
grants **21 slots where the checkpoint's own declared `float32` grants 10** (`conv_state` 0.24 →
0.12 GB, `ssm_state` 6.05 GB unchanged, exactly §12.4's dtype mechanism). What is unmeasured is not
the benefit but the **cost**: whether halving the SSM state's precision changes what the model
outputs. So the recipe takes a *known* win in exchange for an *assumed-safe* numerical risk, and
**phase 14 did not settle the assumption — it retired the method used to test it.** The next attempt
is the logprob probe above, not another greedy-text run. Anyone tempted to "restore" `float32` for
prudence should note they would be surrendering 11 of 21 concurrent requests on an unmeasured
benefit, and anyone tempted to call bf16 safe should note the same thing.

#### 12.11bis Phase 16: teacher-forced logprobs say bf16 and fp32 are BIT-IDENTICAL — and the instrument was blind to the reason

Run 2026-09-20 05:52–06:04, `.scratch/qwen3-27b/run_phase16.sh`, artifacts `.scratch/p16-0920/`.
Four boots in a **2×2 (dtype × node)**, `--fresh` each, teacher-forced per-token logprobs over a
6-prompt corpus (371 scored tokens), 3 reps/arm. This is the instrument §12.11's analysis called for
after greedy text failed.

| arm | server-reported `mamba_ssm_dtype` | `capped` | `K` | `conv_state` |
|---|---|---|---|---|
| `A_bf16` (node-free-1) | `bfloat16` | **21** | 86 | 0.24 GB |
| `B_bf16` (node-free-2) | `bfloat16` | **21** | 85 | 0.24 GB |
| `A_fp32` (node-free-1) | `float32` | **10** | 42 | 0.12 GB |
| `B_fp32` (node-free-2) | `float32` | **10** | 42 | 0.12 GB |

Arm identity comes from each running server's own reported args and pool line, not from the recipe on
disk — the lesson from phase 12 running eight arms against an unparseable recipe. **The dtype override
undeniably reached the pool** (grants 21 vs 10, `conv_state` halved).

**The four comparisons:**

| comparison | design | median \|Δlogprob\| | p95 | max | tokens >1e-2 |
|---|---|---|---|---|---|
| `A_bf16` vs `B_bf16` | node null | 0 | **4.87e-1** | **1.57** | 155/371 (42 %) |
| `A_fp32` vs `B_fp32` | node null | 0 | **4.87e-1** | **1.57** | 155/371 (42 %) |
| `A_bf16` vs `A_fp32` | **dtype effect** | **0** | **0** | **0** | **0** |
| `B_bf16` vs `B_fp32` | **dtype effect** | **0** | **0** | **0** | **0** |

Three things to notice, in order of how much they cost me to believe:

1. **The dtype effect is not "small", it is exactly zero** — bit-identical, 371/371 `(token_id,
   logprob)` tuples equal. Not a rounding result, not a below-threshold result.
2. **Both node nulls are large and *numerically identical* to each other** (same p95, same max, same
   counts). That is not a coincidence or a copy-paste error: if `A_bf16 ≡ A_fp32` and `B_bf16 ≡
   B_fp32` bit-for-bit, then the two null comparisons are *literally the same comparison*, so they
   must agree exactly. **The internal consistency of the table is itself evidence the dtype delta is
   truly zero.** Node-to-node, by contrast, moves logits by up to **1.57 nats** and shifts 42 % of
   tokens by more than 1e-2 — a genuinely large numerical difference between two machines I cannot
   distinguish on any property I can query.
3. **Within-arm rep-to-rep spread is exactly 0.000e+00 in all four arms.** The server is deterministic
   to the last bit at `temperature=0`, which is what makes an exact zero meaningful rather than a
   symptom of a dead probe.

**Why the zero is a statement about the experiment, not a vindication of bf16.** The mechanism is
visible in the pinned source: `layers/attention/linear/gdn_backend.py:721` sets
`has_initial_states = forward_batch.extend_prefix_lens > 0`. For a **fresh prompt with no cached
prefix** that is False — the prefill kernel is *told there is no initial state to read*. The SSM state
buffer is therefore **written** by prefill and only **read** by decode (and by a continuation whose
prefix is cached). So the dtype of that storage cannot, by construction, affect the logits of a
teacher-forced fresh prompt. **My instrument was structurally blind to exactly the quantity it was
built to measure.** `LIKELY`, not proven: the code line is read directly, and the bit-exactness is
consistent with it, but I did not trace every kernel branch (`initial_state_source=ssm_states` is
passed at `:975`/`:994`, which I believe is the decode path). Position-resolved data
(`position_dlogprob.py`) agrees: positions 0–4 are identical across nodes too, with node divergence
starting around position ~5 — i.e. not a token-0 numerics difference.

**So this is the third instrument in this family that could not answer the question**, and unlike the
first two the reason is now understood:

| attempt | instrument | why it failed |
|---|---|---|
| phase 12/14 | greedy text diff | amplifier — node swap diverges more than dtype, so effects cannot be ranked |
| phase 16 | teacher-forced prefill logprobs | **structurally cannot see the recurrent state** — prefill never reads it |
| phase 17 (designed) | logprobs of a **cached-prefix continuation** | — |

**Phase 17, the design that follows from the mechanism, and it is cheap.** Score logprobs on a
*second* turn whose prefix is already cached, so `extend_prefix_lens > 0` and the kernel genuinely
reads the SSM state. Two-step probe: generate/absorb turn 1, then teacher-force turn 2 and compare
its per-token logprobs across dtypes. It keeps what made phase 16 good (no sampling, no amplification,
exact arithmetic) while removing the blind spot. **Falsifier, stated now:** if the continuation probe
*also* returns an exact zero across a 2×2 with live node nulls, then either prefix reuse did not occur
(check `extend_prefix_lens` in the log — the probe is blind again, not the dtype neutral) or the state
dtype truly does not reach the logits, in which case **the accuracy question is closed on the
throughput-only justification** and bf16 stands as a pure concurrency win. Budget: 4 boots, same shape
as phase 16.

**What may be quoted today, and what may not.**
- **May:** `mamba_ssm_dtype: bfloat16` doubles the concurrency grant (21 vs 10 slots) and is
  **bit-identical to `float32` on the prefill path** — a measured, replicated result across two nodes.
- **May not:** "bf16 is safe" as a general claim, or "the accuracy question is closed".
  **Superseded as to scope:** what was "never measured" here — the path where the state is consumed —
  **has since been measured (§12.12)**: bit-identical across 495 tokens on the state-read path, with a
  positive control showing that path is sensitive at the 1-nat level. What remains genuinely unmeasured
  is long-distance state accumulation, free-running generation, and any downstream quality metric.
  Reverting to `float32` would surrender **11 of 21** concurrent requests on evidence nobody has
  produced; calling bf16 unconditionally safe would overstate a 128-token-prefix null.

### 12.12 Phases 22–23: `bfloat16` state is bit-identical on the path that READS the state

Run 2026-09-20 15:43–15:50, driver `.scratch/qwen3-27b/run_phase22.sh`, transcripts and full server
logs in `.scratch/p22-cont/` (and `/home/<operator>/scratch/p22/` on the head node). **This closes the
question §12.4 opened and §12.11 left unresolved — and it took three instrument failures plus one
free control to earn the answer.**

Three arms, same node (`node-free-1`), one boot each where needed:

| arm | how obtained | `capped` | `K` | `conv_state` | `ssm_state` | ssm MiB/slot |
|---|---|---|---|---|---|---|
| `aged_bf16` | **free** — the container already serving since phase 21 | 21 | 85 | 0.24 GB | 6.05 GB | 72.04 |
| `fp32` | boot with `-o mamba_ssm_dtype=float32` | **10** | **42** | **0.12 GB** | 6.05 GB | **144.07** |
| `bf16f` | fresh boot, shipped settings | 21 | 85 | 0.24 GB | 6.05 GB | 72.04 |

| comparison | design | median \|Δlogprob\| | p95 | max | exact? |
|---|---|---|---|---|---|
| `aged_bf16` vs `bf16f` | **NULL**: same node, same config, different boot age | 0 | **5.80e-1** | **4.27** | no |
| `fp32` vs `bf16f` | **EFFECT**: same node, same age class, dtype flipped | **0** | **0** | **0** | **YES** |

495 scored suffix tokens per arm, **zero blind prompts**, and `cached_tokens` **identical across all
three arms** (64/128/128/128), so the two dtype arms had byte-identical cache behaviour.

**The result: bit-identical logprobs across a dtype change that provably altered the allocation.**
The allocation evidence is not inferred, it is printed by the server (`ssm MiB/slot` above):
**72.04 → 144.07, exactly 2.00×**, i.e. the temporal state really is stored at 2 bytes instead of 4,
while the total `ssm_state` holds at 6.05 GB because `K` halved to compensate — §12.1's conservation
invariant, reproduced a third time and now measured to 4 significant figures. Meanwhile `conv_state`
halves in *total* (0.24 → 0.12 GB) while staying at **2.86 MiB/slot in both**, because conv is pinned
at bf16 by `SGLANG_MAMBA_CONV_DTYPE` and does not follow the SSM dtype; it halves only because `K`
halves. **If you are using `conv_state` as a dtype tell, that is the reason it works and the reason
it is not measuring what its name suggests.**

**Why this null is trustworthy when §12.11's was not.** §12.11's exact zero came from prefill, which
`gdn_backend.py:721` never lets read the state (`has_initial_states = extend_prefix_lens > 0`). An
exact zero from a path that cannot see the quantity is not a measurement. That objection is now
answered by a **positive control that cost no boot at all**
(`.scratch/qwen3-27b/full_reuse_control.py`): on one server, compare scoring a continuation with the
prefix *fully cached* against scoring it *cold*, where full means `cached_tokens == prefix_tokens`,
i.e. the prefix is **entirely skipped** and the stored state is the only thing that can carry it.

| prompt | prefix tok | full reuse | cold | n | median \|Δ\| | max \|Δ\| |
|---|---|---|---|---|---|---|
| long-derive | 128 | 128 | 0 | 174 | 1.33e-1 | 1.03 |
| long-state | 64 | 64 | 0 | 108 | 1.95e-1 | 2.32 |
| long-recall | 128 | 128 | 0 | 106 | 1.12e-1 | 1.74 |
| long-translation | 128 | 128 | 0 | 103 | 2.26e-1 | **5.12** |

**Full reuse ≠ cold, by 1–5 nats.** So the read path is live and demonstrably sensitive to what the
state buffer holds. A comparison that can see 5-nat differences through this path reported **0.00e+00**
for a 2× storage-precision change. That is the strongest shape of null available here, and it is not
the same claim as "the state does not matter" — the control says the state matters enormously, the
dtype pair says the state's *stored precision* does not.

**Phase 23 removed the one remaining weakness in that null, for one boot.** Phase 22's own numbers
showed its reuse was only **partial** — prefixes 118–187 tokens, `cached_tokens` 64/128 — so
40–123 prefix tokens were *recomputed* on every request, and recomputed tokens run through the scan
at whatever internal precision the kernel uses, independent of the stored dtype. Any genuine
stored-precision effect is therefore **diluted by the un-read fraction**. Phase 22's zero was real
but measured on a diluted test.

`.scratch/qwen3-27b/full_reuse_probe.py` absorbs until `cached_tokens == prefix_tokens`, i.e. the
prefix is **entirely skipped** and the stored state is the only thing that can carry it. Absorb counts
came out **identical in both arms** (4/3/4/4), which is what makes the comparison clean: neither arm
recomputed more of the prefix than the other.

| | `bf16f_full` | `fp32_full` |
|---|---|---|
| `capped` / `K` | 21 / 85 | 10 / 42 |
| `conv_state` | 0.24 GB | 0.12 GB |
| `server_args` | bfloat16 | **float32** (override confirmed, not inferred) |
| scored tokens | 982 (2 reps × 491) | 1473 (3 reps × 491) |
| distinct logprob values | **491 of 491** | **491 of 491** |

**Per-rep pairwise, not averaged: 6/6 rep-pairs bit-identical, worst |Δ| = 0.000e+00, token-id
mismatches 0.** The averaged statistic agrees (median/p95/max all 0) but the per-rep one is the
claim that matters — see below.

**Two methodological traps I hit writing that analyzer, both worth recording because both were
silent:**
1. **Averaging is the wrong statistic for an exactness claim.** If bf16 rep 0 is +e and rep 1 is −e
   against fp32, the two means can agree exactly while every individual pair differs; and one
   divergent rep out of three moves a mean by a third of the effect, so a token-level median can sit
   below a threshold the per-rep comparison clears. `analyze_fullreuse.py` now reports the full
   *i*×*j* rep matrix and prints the averaged figure underneath **specifically so a disagreement
   between the two is visible instead of averaged away**. Here they agree.
2. **My first version of that analyzer printed a matrix of `nan` and looked like a result.** It
   indexed one transcript by `(rep, name)` and then tested `if name not in B` — always true, so every
   cell was skipped. A `nan` matrix is a *suspicious* shape and I only caught it by running the
   analyzer on phase-22 data, where I already knew the expected answer. **That is the same argument
   as §12.11's selftest rule, applied to analysis code rather than instruments: validate a new
   analyzer against data whose answer you already know, before letting it look at new data.**

**Degeneracy check, because "491/491 identical" is only impressive if the values vary.** The
transcripts contain **491 distinct logprob values across 491 positions** in both arms — not a
constant array, not near-saturation. And the *same* instrument on the *same* construction moves
1.0–5.1 nats when the state is read versus recomputed. It can see; it did not.

**The mechanism, partially established from the installed kernel source — and the extraction cost
no boot.** `docker create` (which never starts a container, allocates no GPU, loads no weights) plus
`docker cp` pulled the *installed* `kernels/ops/attention/fla` out of
`lmsysorg/sglang:dev-qwen38-27b-dflash2`; the tree is archived at
`.scratch/qwen3-27b/fla_installed/`. This matters because the mirrored subtree this document's other
source citations come from does **not** contain `kernels/`, so every previous line reference into
these files was indirect.

**Candidate (a) — "the kernels upcast the state, so bf16 never participates" — is now
DISCONFIRMED as an explanation, and I had this backwards on the first pass.** The installed
`chunk_delta_h.py` (the extend/chunk path our continuation probe exercises) reads the state and
immediately widens it, with no arithmetic at the stored width:

```
:135  b_h1 += tl.load(p_h0_1, boundary_check=(0, 1)).to(tl.float32)     # stored dtype -> fp32
:298  tl.store(p_ht, b_h1.to(p_ht.dtype.element_ty), boundary_check=(0, 1))
```

`fused_recurrent.py:78` / `:121` (decode path) are the same shape. My first reading concluded this
makes an exact zero "expected rather than surprising" — **no.** Upcasting removes the error channel
"the kernel does bf16 arithmetic", but the *operand* is still whatever was stored. A state written as
`b_h.to(bf16)` and a state written as `b_h.to(fp32)` are **different numbers**, and both are then
handed to identical fp32 arithmetic. Different input, same arithmetic, same output is not available —
so the zero is *more* mysterious than before this code was read, not less. It removes a hypothesis
and sharpens the remaining one, which is the opposite of closure.

Two things follow, and neither is settled:

1. **The difference must be erased somewhere other than the kernel's arithmetic.** Either the state
   the continuation actually reads is not the buffer whose dtype the flag changes, or the values
   written are exactly bf16-representable in this configuration, or the probe's read path bypasses
   the stored state in a way the `cached_tokens` evidence does not rule out. Nothing here
   distinguishes them. Candidate (b) — a state buffer pinned independently of the flag — is still
   weakened by the allocation numbers (`intermediate_ssm` 72.03 → 144.06 MiB/slot doubles with the
   flag, so that buffer does follow it), but "weakened" was the honest word and it remains the
   strongest surviving candidate.
2. **The clean way to settle this is not a longer corpus — it is a unit test on the buffer, not a
   comparison of two servers.** Take the state pool immediately after absorbing a prefix and read it
   back: if the bf16 arm's stored tensor differs numerically from the fp32 arm's, the zero has to be
   explained downstream; if they are identical, the flag reaches the *allocation* but not the
   *values*, and the whole null is about a perturbation that never happened. A side argument says the
   values almost certainly do differ: arbitrary fp32 states are not bf16-representable, so bf16
   storage cannot be lossless here -- which is why "allocation changed, output did not" is a real
   puzzle and not a triviality. **Feasibility is NOT established**: nothing in this project has ever
   read the mamba state pool, and no HTTP surface that exposes it is known. Realistic routes are a
   patched container, a debug/introspection endpoint, or a standalone harness that instantiates the
   pool outside the server -- the last is the most likely to work. Do not budget this as "one boot".
   **This is the highest-value remaining action on the dtype question** and it replaces the
   "run a longer corpus" plan in §6 item C, which cannot answer this: the open question is *where the
   difference is erased*, not *whether a longer sequence accumulates it*.

**Honest scope.** `VERIFIED`: the kernel lines quoted, and that the tree is the installed one.
`LIKELY`: that this is the path the probe exercised (the backend at `gdn_backend.py:721` routes the
extend to this kernel, and the probe is an extend). `UNVERIFIED`: which buffer the continuation's
initial state is read from — which is precisely the open question above. **`LIKELY` that bf16 state is numerically inconsequential for this model on this
path; `VERIFIED` only that it is undetectable across 495 tokens by an instrument with demonstrated
1-nat sensitivity.**

**What this changes in the standing risk statement.** §12.11 ended with: *"a known 2× concurrency win
against an unmeasured numerical risk."* **The risk is now measured, on the path that reads the state,
and it is zero to the limit of an instrument that can see 1 nat.** bf16 is no longer an
assumed-safe default; it is a 2× concurrency grant with a null behind it. Three things that would
still overturn it, in order of value:
1. **Longer prefixes.** 128-token prefixes exercise a state accumulated over two chunks. The
   accumulation concern (§12.11) is only partly addressed — the state read here is real, but the
   distance it has integrated over is short.
2. **Free-running generation.** Everything here is teacher-forced; a difference that only appears
   once the model chooses its own tokens is out of scope by construction.
3. **A downstream eval**, which is the only thing that can convert "no numerical difference
   detected" into "no quality difference" (§6 item C).
   None of these is a reason to revert. Reverting `float32` costs **11 of 21** concurrent requests.

**Operational finding that outlives the dtype question, and it is free:** **prefix reuse grows with
the number of times the server has seen a prefix**, under `mamba_radix_cache_strategy:
extra_buffer_lazy`. Measured ladder, flushed first, 128-token prefix:
**1 absorb → `cached=0`, 2 → 64, 3 → 64, 4 → 128 (full)**. A 64-token prefix takes 3 absorbs.
Consequences:
- **Any warm-up must absorb the shared prefix several times, not once.** Phase 21's continuation
  probe reported `cached=0` and correctly refused to run — which looked like a broken instrument and
  was actually the lazy strategy doing what it does. The guard's error message blamed
  `logprob_start_len`; the real cause was absorb count. **A good error message sent me down the wrong
  path for a whole session.**
- Full reuse is reachable, so `cached_tokens == prompt_tokens` is a usable target for any experiment
  that needs the kernel to depend on stored state.
- It also means `prefix_caching: true` in a benchmark does **not** mean prefixes are shared on the
  first pass. The §12.9/§12.10 ratio runs at `prefix_caching: true` therefore had *less* sharing than
  their settings imply on early runs — a plausible partial explanation for why measured token-pool
  usage tracked the no-sharing model so well (0.96–0.99 predicted vs observed) rather than showing
  the large sharing discount one might have expected.

**Instruments written for this, all reusable:** `logprob_probe.py` (`--mode continuation
--corpus long`), `selftest_logprob_probe.py` (**7 checks with known answers**, including an
all-requests-failed arm that must yield zero matched tokens — the failure mode that fooled this
project twice), `full_reuse_control.py` (this section's control), `position_dlogprob.py`
(accumulation-by-position), `analyze_phase18.py` (decision rules fixed before data).

### 12.14 Reading the state pool directly: the perturbation is real and ~1.7e-3, and my first explanation of the null was a metric artifact

Closed the experiment §12.12 left open — **"read the stored state pool"** — and it cost **no boot**:
no model, no weights, no KV pool. `docker create` (which never starts a container or allocates a GPU)
plus `docker cp` pulled the kernel tree out of the image; then `docker run --rm --gpus all` on an
authorized trial node executes the **real installed** `chunk_gated_delta_rule_fwd_h` on synthetic
tensors. Probes (five iterations; **all five are lost from this worktree** — see §12.20's provenance
table, which is the reason the citation below is marked rather than linked): probes 4 and 5
exist because 1 through 3 used a metric that turned out to be unusable, which is the main
lesson here. The findings below stand on the printed outputs, not on the scripts.

**First, a correction to §12.12's evidence base.** I had been citing the wrong image. Benchmarks ran
`lmsysorg/sglang:dev-cu13`, but the tree extracted in §12.12 came from `dev-qwen38-27b-dflash2`. The
two differ in `chunk_delta_h.py` (387 vs 386 lines — one reformatted `assert`, cosmetic), but the
lines §12.12 cited were `:135`/`:298` and in the **serving** image they are **`:136`/`:299`**. An
off-by-one from an unverified mirror — the same class of error as §12.2's cross-config `#tokens`
quote. Citations below are from `dev-cu13`, verified by `md5sum` against the image that actually
served. `CHUNK_SIZE == 64` re-confirmed inside it on GB10, with dims taken from
`artifacts/config.json` (`H=48`, `Hg=16`, `K=V=128`) rather than invented.

**Probe 1 — the kernel is NOT blind to the stored dtype.** Comparing a state stored bf16 against the
same state stored fp32, with fp32 outputs, **100 % of output elements differ**, every trial. So
§12.12's "candidate (b): the flag reaches the allocation but not the values" is **refuted** — the
values differ and the kernel sees them. The identical-*values* control (same numbers in a bf16 vs an
fp32 container) is bit-identical, so the probe measures stored precision, not a dtype-dependent code
path.

**Probe 3 — and then probes 4 and 5, which refuted probe 3's headline. Read all five rows.**
Probe 3 compared the bf16-state and fp32-state arms using **`frac-differ`** (how often output
elements are unequal) and got 100 % / 21.07 % / 0.76 % as the input dtype and output precision
stepped toward shipping. I wrote that up as "two absorbers, second one unexplained". **The metric
was wrong and the claim is retracted.**

Two independent defects, both found by probing the instrument rather than the world:

- **On fp32 outputs, `a != b` is bit-exactness, not magnitude.** A 1e-7 relative perturbation
  changes ~100 % of fp32 elements. So probe 3's "100 %" row said nothing about signal size — it
  described floating-point representation. Rows 2 and 3 are mutually comparable (both count
  bf16-rounding crossings); **row 1 is not a "before" value and the 100 % → 0.76 % ratio was
  arithmetic between incommensurable metrics.**
- **`frac-differ` saturates.** probe 4 swept `h0` by **1×, 2×, 10×, 100×, 1000×** and the metric
  read ~100 % at every single scale (99.96–100.00 %) in both input dtypes. **A metric that cannot
  distinguish a 1× from a 1000× perturbation cannot support a claim about a 27.7× difference.**
  That is the cleanest statement of why probe 3 was not evidence.

Probe 5 measured the quantity that was actually being asserted — **relative L2 change in the
kernel output** caused by storing `h0` as bf16 rather than fp32:

| `T` tokens | inputs | rel L2 change from `h0` storage dtype |
|---|---|---|
| 64 | fp32 | **1.66e-3** |
| 64 | bf16 | **0.00e+00** |
| 128 | fp32 | 1.65e-3 |
| 128 | bf16 | 2.33e-4 |
| 256 | fp32 | 1.75e-3 |
| 256 | bf16 | 2.03e-3 |

Three things follow, and the first is the only quantitative statement worth keeping:

1. **The effect of stored-state precision on kernel output is ~1.7e-3 relative — one bf16
   quantum, in every condition.** That is exactly what bf16 storage must produce and it is
   `VERIFIED`. It also means the server-level exact zero is *not* explained at this boundary: a
   1.7e-3 perturbation is far above the noise floor of the logprob instrument (§12.12 moved
   1.0–5.1 nats on its positive control), so something downstream of this kernel erases it.

**Then the arithmetic closed most of what remained — and it was sitting in plain sight.** The bf16
relative quantum is `2^-8` = **0.3906 %**. The measured perturbation is **0.1700 %**, i.e.
**0.435 of one quantum — the state perturbation is *sub-quantum*.** Three consequences, all checkable:

- **Probe 3's 21.07 % is the same phenomenon as its 0.76 %, not a different stage.** A perturbation
  smaller than the rounding quantum maps most values to the *same* bf16 result; for values spread
  through a binade the boundary-crossing fraction is ≈ `r/q`. Here that predicts 43.5 % against 21.07 %
  measured — same order, and the shortfall is expected because real activations are not uniform
  within a binade.
**Probe 7 — and where this stops, deliberately.** After three mechanism stories, each refuted by a
new probe, probe 7 was designed to test the fourth (that the kernel coerces `initial_state` to the
output dtype, making probe 3's row a comparison of two dtypes holding the same value). It ran a
three-way comparison — bf16 pool vs fp32 pool vs **fp32 pool whose values already equal the bf16
rounding** — in both input dtypes:

| comparison | bf16 `k/w/u` (shipping-shaped) | fp32 `k/w/u` (control) |
|---|---|---|
| A = bf16 pool vs B = raw fp32 pool (probe 3's row) | **0.76 %** differ, median rel **0** | 100 % differ, median rel 1.46e-3 |
| A vs C = fp32 pool, values already equal to A | **bit-identical** | **bit-identical** |
| B vs C | 0.76 %, median rel 0 | 100 %, median rel 1.46e-3 |

**Two things are settled by this, and they are the last dtype claims in this document.**

1. `VERIFIED`: **the incoming state tensor's storage dtype is irrelevant to this kernel — only its
   values are.** Feeding it an fp32 tensor whose values already equal the bf16 rounding reproduces the
   bf16 case *bit-for-bit*, in both input dtypes. So there is no dtype-dependent code path here, and
   probe 3's A-vs-B row was never "dtype A vs dtype B" — it was a value perturbation.
   `UNVERIFIED`: **why the same configuration gives 0.76 % here (probe 7) and 47 % in probe 6** for
   perturbations of nearly identical relative size (1.46e-3 rounding vs 1.7e-3 injected). The
   perturbations differ in *structure* — rounding vs random direction — so **boundary-crossing
   fraction is evidently not a function of relative perturbation size alone**, which also puts a
   ceiling on the `r/q` model above (probe 6 validated it using random perturbations only). I am not
   writing a fifth mechanism. The number of times a "clean" explanation of this one figure has
   survived contact with the next probe is now **three**, and that should end the search rather than
   encourage another round.
2. `VERIFIED`, and the most important limit in this section: **everything in §12.14 is about the
   chunk kernel's internal `h` scratch buffer, not about the server's persistent state pool.** The
   buffer is allocated `k.new_empty(...)` — in `k`'s dtype, bf16 — so *within this kernel* the pool
   dtype cannot matter regardless of the flag. The **server's** persistent mamba pool is allocated
   separately, from `cache_params.dtype.temporal`, and the flag provably moves it (72.04 → 144.07
   MiB/slot across real boots, §12.12). Conflating those two buffers is the error that made all three
   earlier mechanism stories sound plausible: they explained a dtype sensitivity in a buffer whose dtype
   the flag does not control. **No probe here says anything about the flag's effect on the persistent
   pool, and none should be quoted as if it did.**
2. **"bf16 inputs damp the propagation" does not survive.** It is 0 at `T=64`, 7× smaller at
   `T=128`, and *identical* at `T=256` — inconsistent in direction, not a damping law. There is no
   second absorber to explain, because the 27.7× that needed explaining was an artifact of the
   saturating metric.
3. **The synthetic generator is out of regime and no percentage from it transfers to the server.**
   `|out|` rms climbs 0.35 → 11 → 14,770 as `T` goes 64 → 128 → 256 (1.79e9 at `T=512`), because
   `w` is drawn from `N(0,1)` when in the real model it is formed from the decay. The recurrence
   diverges. `T=64`'s exact zero with bf16 inputs is probably just the `h0` contribution falling
   below the output's own bf16 quantum — which is a statement about these amplitudes, not about
   Qwen3.

**What is established, and what is not.** `VERIFIED`: the stored dtype changes the values (probe 1:
100 % of fp32 outputs differ), the kernel reads them (probe 4: output responds to `h0` at every
scale), and the size of the change is **~1.7e-3 relative — one bf16 quantum** (probe 5).
`UNVERIFIED`, and now the actual open question: **where downstream of this kernel the 1.7e-3
disappears.** It is not this kernel boundary, and probe 3's claim that it was was an artifact.
Candidate sites that have not been examined: the output projection, the logits `gather`, the
`log_softmax`, or a second rounding in `chunk_o` / `chunk_fwd`. Note the uncomfortable
consequence — a 1.7e-3 state perturbation producing a **bit-exact** logprob vector (not merely a
small one) is still not explained, and that exactness is what makes the null interesting rather than
settled.

**What this does and does not license about the recipe.**
- It **does** explain 12.12's bit-identical continuation without the flag failing to reach the
  values, so the null is not an instrument artifact and the state is not inert.
- It **does not** license "bf16 state is numerically safe". The states provably differ, the kernel
  provably propagates the difference, and it is *absorbed* — absorption by quantization is a
  statement about this output precision and this amplitude, not about correctness. A configuration
  keeping more precision downstream (fp32 logits, different accumulation, a longer autoregressive
  chain where absorption can compound) is covered by **no** measurement here.
- §6 item C's conclusion stands and is now mechanistically grounded: **do not revert to
  `float32`** — it costs 11 of 21 concurrency slots and buys nothing this instrument can detect. But
  "detect" is doing real work in that sentence: the difference exists and is simply below the
  resolution of everything measured.

**Transferable technique, worth more than the finding.** `docker create <image> true` + `docker cp`
extracts installed source without starting a container, allocating a GPU, or loading weights; a
follow-up `docker run --rm --gpus all` runs arbitrary code against the real kernels on hardware.
Every source-level question in this document so far needed either a guess or a boot. This cost
neither, and it is the right first move for any "what does the installed code actually do" question.

**Consequence for the open item.** The remaining question is no longer "does the dtype matter" but
**"which stage erases the difference"** — and that is answerable without a corpus at all: instrument
the store and the read separately. It replaces "run a longer corpus" in §6 item C, because the
question is *where the difference is erased*, not *whether a longer sequence accumulates it*.
Phase 24 as written cannot answer it: it boots 1,500–2,200-token prefixes, but the probe it invokes
(`full_reuse_probe.py`) has **no `--min-prefix` flag** (argparse would exit 2 after a ~12-minute
boot) and actually draws from `CONTINUATIONS_LONG` at ~150–180 tokens. Its `max_absorbs` default of
12 is also far below the ~30 absorbs a 2,000-token prefix needs to saturate reuse at the 64-token
chunk granularity. **Both bugs were caught by reading the invoked script before launching — the
third latent driver defect found that way this session.** Phase 24 should not be run until the
corpus is lengthened and the flag is added or removed.

### 12.18 Reading `MambaPool.__init__` on the device: the state-pool ceiling is dead code, and two of my own explanations were wrong

> ### ⚠ CITATIONS IN THIS SUBSECTION DO NOT RESOLVE AGAINST THE RUNNING IMAGE — read §12.20 first
>
> Checked 2026-09-21 against the container actually serving this recipe (`lmsysorg/sglang:dev-cu13`,
> id `003b7b5899ed`, `sglang.__version__ = 0.0.0.dev1+g09daea94a`). `mamba_pool.py` **does not exist**
> anywhere in the image (`find / -name 'mamba_pool*.py'` → nothing); `MambaPool` is at
> **`memory_pool.py:371`**; `MambaPoolV2` appears **nowhere** in the tree; `num_max_requests` and
> `_resolve_num_max_requests` appear **nowhere under `mem_cache/`**. The `inspect_dtype.py` driver this
> section names is absent from the repo, the head node and `/home/<operator>/scratch`. The image this section
> cites (`ai-inference/sglang:spark`, sglang 0.5.15) is **not present on either trial node**, so its
> evidence cannot be reproduced even in principle.
>
> **Do not read this as "the section is wrong."** Its testable conclusions that I could re-test came
> back **right or right-ish** (§12.20 re-derives them from the real source). What failed is the
> citation apparatus, which is the part a reader relies on to check the reasoning. Treat every line
> reference below as unverified until re-grounded; §12.20 gives the ones that are.

Run against the live container on `node-free-1` (image `ai-inference/sglang:spark`, sglang **0.5.15**,
checksum `53189887` — re-verified this session, so the line numbers below are from the file that
actually ran). Driver: `.scratch/qwen3-27b/inspect_dtype.py` — **lost**; the outputs quoted below survive in this section, the script does not (§12.20 row: "repo, head node, `/home/<operator>/scratch` — absent").

This section exists mainly to retract two explanations I had argued for **in-session, in
conversation** — neither of them ever survived into a document, and that distinction matters.
`grep` for `160 slots`, `12.85` and `§12.17` across the whole repo **and** across every pre-split
backup (`/tmp/W.bak`, `/tmp/work.bak`, `/tmp/wd.bak`) returns nothing: the sections those claims
were attributed to were never written. So this is a retraction of reasoning, not of text, and it is
recorded anyway because the reasoning was load-bearing for a recommendation (keep the ratio high)
and the recommendation is still standing on other grounds. **The absence of the text is not a
reason to trust the reasoning.**

**Retraction 1 — "the state pool is capped at `num_max_requests × 8 = 160 slots`" is false.** It
was offered as the mechanism for why `mamba_full_memory_ratio` cannot be lowered. It is wrong on
three counts:

1. **`num_max_requests` is not a parameter of `MambaPool.__init__`.** The signature
   (`mem_cache/mamba_pool.py:1576-1583`) is `max_mamba_cache_size, page_size, num_mamba_layers,
   mamba_cache_per_req, mamba_ssm_cache_loc, mamba_nginx_start, dtype, spec_state_cache_len,
   intermediate_ssm_cache_size, enable_extra_buffer, mamba_slot_manager, enable_linear_replayssm,
   **kwargs`. `num_max_requests` is what the *caller* passes (confirmed live:
   `kwargs keys: ['num_max_requests']`, value 20), so it falls into `**kwargs` and **vanishes**.
2. **`_resolve_num_max_requests` is never called on this path.** It exists at `:1545` and its
   fallback logic is exactly the `min(K // (D+1), max_requests)` reasoning I reported as live
   behaviour. On this path it is dead code.
3. **The number quoted as evidence — `0.49009663735996454` — is not a measurement.** It comes from
   the `__init__` **docstring example** (`num_max_requests=32, mamba_budget=120 GiB, D+1=8, D=7`).
   The same line carries its own `NOTE (b/c)` caveat about that ratio being wrong, which I also
   lifted into prose as though it described *our* config. **Reading a docstring example and
   reporting it as a live measurement is the most avoidable error available in a document like this,
   and it happened anyway.**

**What the same read does establish:**

- **Pool size is governed by `max_mamba_cache_size` and `num_mamba_layers` alone.** `:862` —
  `size = (max_mamba_cache_size + num_mamba_layers) × ssm_slot_bytes`; `:910` —
  `conv_state = (num_conv_slots, num_mamba_layers, conv_slot_bytes)`. No request-count term anywhere.
- **`intermediate_ssm` is 75.05 % of the mamba bytes, which retires the in-session "unaccounted
  12.85 GiB" figure. There was never an unaccounted pool.** `intermediate_ssm` at 57.85 GiB is four
  and a half times the figure I had called unaccounted; the earlier arithmetic had subtracted `conv + ssm +
  intermediate_conv_window` and then treated the remainder — i.e. `intermediate_ssm` itself, the
  largest term — as a mystery. The pool total was always fully accounted for.
- **Observed `MambaPoolV2` fields, fp32 arm (`bfp32`, ratio 0.4, `capped 12`):** `K = 121`,
  `conv_capacity 12`, `ssm_capacity 12`, `conv_slots [12]`, `ssm_slots [9]`,
  `inter_ssm_capacity 198`, `inter_ssm_slots [9]×22`, `num_mamba_layers 48`,
  `inter_ssm_slot_bytes 16,777,216` (fp32), `ssm_slot_bytes 8,388,608`, `conv_slot_bytes 8,192`.
  The bf16 arm at the same ratio logs `conv_state 0.11` GiB against fp32's `0.23` GiB, so **the conv
  state's dtype follows `mamba_ssm_dtype`** — that is the mechanism behind the `conv_state`-halving
  dtype tell used in §12.6, now traced to a line rather than inferred from an allocation log.

**What is NOT established, stated plainly because the previous two attempts both over-reached.** I
cannot derive `num_conv_slots = 12` or `ssm_capacity = 12` from `K = 121` by any formula I have
verified. `capped = 12` coincides with `conv_capacity`, but `inter_ssm_capacity 198 = 22 × 9` fits
neither `capped` nor `K`. So the relationship among `max_mamba_cache_size`, the granted `capped`, and
these slot counts is **unresolved**, and the `slots = (K+1) + (capped+1)×D` claim — attributed in
conversation to `§12.17`, a section that, as noted just above, **was never written**, so there is no
text here to correct, only the claim itself — is **not supported by the pool's own fields**. What survives is what was measured rather than derived:
`capped`, `K`, `#tokens` and the allocation sizes, all read from logs (§12.2bis), plus the empirical
fact that the ratio moves `K`/`#tokens` in the predicted direction on every boot so far.

**The conclusion I had drawn survives; the mechanism does not.** Lowering `mamba_full_memory_ratio` below
~1.5 is still a bad idea — but because it **cuts slots** (`capped` 21 → 12 going 3.51 → 0.4,
measured), not because of any 160-slot ceiling. The two are opposite in direction: the dead
`min(K // (D+1), max_requests)` would have *raised* the cap as `K` grew. That inversion is the
cleanest illustration here of the difference between "a formula exists in the source" and "the
program executes that formula" — and the extra lesson from this section, which cost me writing a
retraction of a paragraph that did not exist: **before retracting a claim, grep for it.** A
retraction aimed at text that was never written is a record of a conversation, not of the project,
and it silently teaches the reader that the document has been audited when it has not.

**The lesson is the one §12.2 and §12.14 already recorded from other angles: cite the line you read,
and distinguish the line that RUNS from the line that EXISTS.** A tool worth building here would
assert on call-site reachability — is this function called on this path — rather than grepping for a
string. A grep-based guard would have passed every version of the wrong claim above.

### 12.19 Prefix-reuse floor measured at 64 tokens, the cross-node null is EXACTLY zero, and a `ProbeBlind` escape that killed phase 21

Run 2026-09-21, entirely **free** (no boots): the servers from earlier phases were still up and idle,
so everything here cost requests, not machines. Scripts `.scratch/qwen3-27b/probe_prefix_alignment.py`
and `logprob_probe.py`; transcripts `.scratch/p36-cont/`.

**1. Reuse needs `prefix_tokens >= 64`, and is quantised to multiples of 64 — measured directly.**
This closes the open question at the end of §12.18 and explains the phase-21 failure without invoking
state-buffer pressure:

| target tok | actual `n_pre` | `cached_tokens` | verdict |
|---|---|---|---|
| 16 | 29 | **0** | blind |
| 32 | 57 | **0** | blind |
| 48 | 57 | **0** | blind |
| 64 | 85 | 64 | reusable |
| 96 | 113 | 64 | reusable |
| 128 | 141 | 128 | reusable |
| 192 | 197 | 192 | reusable |
| 512 | 533 | 512 | reusable |

The floor is the mamba `CHUNK_SIZE = 64` of §12.7, and the quantisation is that same number: a 64-token
chunk is the unit below which nothing can be skipped.

The rule then predicts the behaviour of the probe's own corpora, and it is right without exception —
all 8 prompts, measured on the live server:

| corpus | prompt | prefix tok | scored? |
|---|---|---|---|
| short | `cont-derive` | 94 | yes |
| short | `cont-code` | **54** | **blind** |
| short | `cont-recall` | 100 | yes |
| short | `cont-translation` | **58** | **blind** |
| long | `long-derive` | 168 | yes |
| long | `long-state` | 118 | yes |
| long | `long-recall` | 187 | yes |
| long | `long-translation` | 142 | yes |

Every prompt under 64 is blind and every prompt at or above it is scored. That is the strongest form of
this result available cheaply: a threshold derived from one sweep, then confirmed against a corpus that
was written for a different purpose and never tuned to it.

The `no-logprob cached=0` columns matter. At the short lengths the prefix was not cached **even without
the logprob request**, so this is *not* the §12.13 trap ("asking for whole-prompt logprobs defeats the
cache") reappearing at a new length. Two failure modes with different fixes, separated only because
both request shapes were tested at every length.

**2. The "cross-node null" on the continuation path is EXACTLY ZERO — but its provenance is NOT
established, so it does not license a cross-machine claim.** Recorded originally as "`node-free-1` vs `node-free-2`,
identical recipe, 495 paired suffix tokens, `median / p95 / max |Δlogprob| = 0.00e+00`, `tokmis = 0`".
Audited 2026-09-21 and the provenance does not hold up:

- `lp_cont__A_bf16.json` (11:54:57) and `lp_cont__B_bf16.json` (11:55:20) were both written **23
  minutes *before* `run_phase36.sh` started** (11:57:27), by an interactive session that left no log.
  Phase 36's own driver only ever touched `node-free-1` (single `--hosts "$NODE"`, `$NODE=node-free-1`), so
  `B_bf16` was **not produced by the driver whose analysis consumes it.**
- All three transcripts embed `url = http://127.0.0.1:8000`, which is node-*local* (probes were run
  over `ssh` on the node), so the field cannot identify which machine answered.
- The original "checked against comparing a file with itself" defence — different md5s — **does not
  work**: the transcripts necessarily differ in their embedded `label` and `url` fields, so different
  md5s are guaranteed even for two probes of the same server. It could not have detected a duplicate.

So `A_bf16 vs B_bf16` may be a same-server repeat, or a pair across `node-free-1`/`node-free-2` — and if it was `node-free-2`,
that node was running **`mamba_full_memory_ratio = 1.2`** at the time, not the shipped 3.51, so
"identical recipe" would also be false. **Which it was cannot be determined from the artifacts.**

What survives, and what must not be quoted:
- **Survives:** the *dtype* pair (`A_bf16` vs `A_fp32`, both written by phase 36 on `node-free-1`, fp32 boot
  confirmed by `_memlog.txt`) is exactly zero over 495 tokens. That is the section's load-bearing
  result and its provenance is documented.
- **Must not be quoted:** "teacher-forced continuation logprobs are *deterministic across machines*".
  That was inferred from a comparison whose cross-machine status is unverified. §12.12's argument that
  "the node null swamps the effect, so a zero here is meaningful" **loses its support** — if the null
  is a same-server repeat then it is trivially zero and says nothing about resolution.
- **Still standing independently:** phase 22's same-node null *did* move logits up to 4.27 nats on
  175/495 tokens, so the instrument is demonstrably sensitive on this path. That is the evidence to
  cite for "a zero is not automatic", not the `B_bf16` pair.
- **Re-measure:** a genuine cross-node null needs **one boot** (`node-free-1` currently has no container;
  only `node-free-2` is live, and it runs `mamba_full_memory_ratio = 1.2`, not the shipped 3.51 — so even
  pairing today's two boxes would not be an "identical recipe" test). That is the honest cost, and
  it is why this note says *unverified* rather than *probably fine*: the measurement is cheap but
  not free, and it has to control config as well as node. The probe now writes `probe_host`,
  `gpu_uuid`, `url` and a UTC timestamp into every transcript, so a future run cannot be
  un-attributable the way `B_bf16` was.

The two consequences pull in opposite directions:
* **Good:** teacher-forced continuation logprobs are *deterministic across machines* on this stack. A
  dtype delta measured on this path cannot be dismissed as hardware variation, so §12.11's "the node
  null swamps the effect" objection does not apply to this instrument.
* **Bad, and it changes how §12.12 should be read:** a zero null is not a *scale*. If a dtype
  comparison on this path returns zero, "within node noise" is an empty statement — zero is the floor
  of the instrument, not its resolution. A zero here means either genuine invariance on this path or
  the probe not reaching the quantity. §12.14's kernel probe is what separates them, and it says the
  stored values really do differ.

**3. Phase 21 died on an exception *type*, not on blindness.** Reconstructed from the archived log,
not guessed: `cont-derive` scored normally (`35 suffix tokens, prefix 94, cached 64`), then the next
prompt raised. The traceback shows `raise RuntimeError(` — the cached-token blindness guard at that
time raised a plain `RuntimeError`, while `collect_continuation`'s per-prompt tolerance catches
`ProbeBlind`. So the exception escaped, one blind prompt aborted the whole run, and the boot was spent.

This is verifiable rather than inferred, because it can be reproduced free: running the current probe
over the `short` corpus on a live server reports
`EXCLUDING prompts blind in some arm: ['cont-code', 'cont-translation']`. Those two prefixes are under
64 tokens, so they are blind by the rule in point 1 — **expected, and exactly what the per-prompt
tolerance exists to survive.** Had the type matched, phase 21 would have scored the other two prompts
and finished, instead of returning nothing.

A second instance of the same class was found by reading and fixed: the `if not suffix_rows` guard also
raised `RuntimeError` with the word "BLIND" in its message. Both now raise `ProbeBlind`.

**The generalisable lesson: an instrument that fails loudly is not necessarily one that fails
correctly.** A wrong exception type produces a log line that *resembles* the intended safety behaviour,
so the failure reads as "the guard worked" and the real cause — a two-line type mismatch — never gets
examined. Phase 21 burned a boot that way. This is the fourth latent defect this session found by
reading the invoked script before launching it.

**4. Re-verified that the probe reaches the state-read path** (the thing that made three earlier
instruments useless): on the live server the `long` corpus scored **695 suffix tokens across 4 prompts
with `cached_tokens > 0` on every one**, stable across reps (128/64/128/128, min-of-reps recorded).
Confirmed before any paid arm rather than assumed.

**Pending, pre-registered now so it cannot be re-fitted afterwards.** Phase 36
(`.scratch/qwen3-27b/run_phase36.sh`) boots `node-free-1` with `mamba_ssm_dtype=float32` and re-scores the same
`long` corpus — the decisive same-node, same-age dtype pair on a path whose null is a hard zero. Rules,
written before the data:
* **nonzero** median on `A_bf16` vs `A_fp32` → stored precision is visible on the state-read path. That
  contradicts §12.12's null, and with §12.14's kernel result means the earlier nulls were blind spots,
  not evidence of safety.
* **exactly zero**, with `cached_tokens > 0` on every scored prompt → genuine invariance of the scored
  logits *on this path*. Still **not** "bf16 is safe": the kernel probe already proved the values
  differ, so a zero here describes where the probe reaches, not what the model does.
* Either way the claim is bounded by four prompts, ~700 tokens, no task metric. It cannot rank dtypes.

**Result, run same day (one boot, `node-free-1` → `float32`): the second branch, and the guards all held.**

`A_bf16` vs `A_fp32`, same node, same corpus, 495 paired suffix tokens:
**median = p95 = max |Δlogprob| = 0.00e+00, `>1e-3` count 0, `tokmis` 0.**

Not a silent no-op, checked before interpreting:

| check | `bf16` | `fp32` |
|---|---|---|
| `server_args` (printed by the running server) | `bfloat16` | **`float32`** |
| `capped` / `K` | 21 / 85 | **10 / 42** |
| `conv_state` | 0.24 GB | **0.12 GB** |
| `cached_tokens` per prompt | 128/64/128/128 | **128/64/128/128** |

The override reached the process and halved the per-slot allocation, exactly as §12.12 measured, and the
two arms had **byte-identical cache behaviour** — so the comparison really was a dtype comparison. Three
transcripts have distinct md5s and distinct timestamps; `corpus` is `long` in all three, so no
corpus-mixing. Same image on both (`lmsysorg/sglang:dev-cu13`, id `003b7b5899ed`), so no build drift
between arms.

**What this adds over §12.12, which already reported this zero.** Phase 22's zero was on one node with a
nonzero null (p95 5.8e-1) and a partially-cached prefix; §12.13 then removed the partial-cache weakness.
Phase 36 is an **independent replication** on a fresh boot, and it closes the one alternative explanation
phase 22 left: that the bf16 and fp32 containers differed in something besides dtype. They cannot, here —
same host, same image, same corpus, `cached_tokens` identical in all four prompts, allocation different.
So the null is not an artefact of one pair of containers.

**The one thing a zero null cannot do, restated because it is the trap in this section.** A zero cross-node
null makes "within node noise" unfalsifiable, so it provides **no scale**. The power for this null comes
entirely from §12.12's `full_reuse_control` — the same instrument on the same construction moving
**1.0–5.1 nats** between full-reuse and cold — not from the null. Quote the control whenever quoting this
zero; quoting the zero against a null of 0.00 is meaningless.

Net position on the dtype question is unchanged by this run, and unchanged is the right outcome: the
stored values provably differ (§12.14, ~1.7e-3 relative, ≈ bf16 epsilon), the scored continuation logits
provably do not, **and the mechanism connecting those two facts is still unknown.** The open action is
still the one §12.14 named — read the live pool buffer, not two servers.

### 12.20 Re-grounding §12.18 against the image that is actually running: the core formulas hold, the citations do not

Run 2026-09-21, **free** — read-only `docker exec grep/sed` against the live container on
`node-free-2`. No boots, no GPU work. This section exists because §12.18 cites code I could not find.

**First, the good news, and it is the important kind.** The central §12 arithmetic — the thing
`predict_capacity.py` implements and §12.2bis/§12.8 validate against boots — is present in the running
source, nearly verbatim (`kv_cache_configurator.py:2372-2392`):

```
#   (K + 1) * per_req + (K / ratio + 1) * D * per_req = mamba_budget_bytes
mamba_budget = total_rest_memory * ratio / (1 + ratio)
    max_mamba_cache_size=int((mamba_budget_bytes - per_req * (1 + D))
                             // (per_req * (1 + D / ratio)))
capped_reqs = min(max_running_requests // attn_dp_size, max_mamba_cache_size // ratio)
intermediate_size = per_req * (capped_reqs + 1) * D
```

That is §12.2's `K`, §12.3's `capped`, and §12.6's `intermediate` term, with the same operators in the
same order. So the model whose predictions have been landing at ±1 slot is **reading the code that
runs**, not a fossil. Given how much of this document is corrections, it is worth stating plainly which
part is not.

**Now the citations.** Against the container that served every phase-36 measurement
(`lmsysorg/sglang:dev-cu13`, id `003b7b5899ed`):

| §12.18 asserts | check | result |
|---|---|---|
| `mem_cache/mamba_pool.py:1576-1583` | `find / -name 'mamba_pool*.py'` | **no such file** |
| `class MambaPoolV2`, observed fields | grep whole tree | **symbol absent** |
| `_resolve_num_max_requests` at `:1545` | grep `mem_cache/` | **absent** |
| `num_max_requests` a caller kwarg to the pool | grep `mem_cache/` | **absent**; only hit tree-wide is `base_cuda_graph_runner.py` |
| `intermediate_ssm` 57.85 GiB, 75.05 % of mamba bytes | boot logs on disk | **12.38 GB, 66.4 %** — absolute off by 4.7× |
| image `ai-inference/sglang:spark`, sglang 0.5.15 | `docker images -a` on `node-free-1`/`node-free-2` | **image not present on either node** |
| — | **and**: `mamba_pool.py` / `MambaPoolV2` searched in *all three* sglang images on the nodes (`dev-cu13`, `dev-qwen38-27b-dflash2`, `dev-cu13-qwen38-next-local`) | **absent from all three** |
| driver `.scratch/qwen3-27b/inspect_dtype.py` | repo, head node, `/home/<operator>/scratch` | **absent** |

Where the real code lives, verified this pass:
* `MambaPool` — **`memory_pool.py:371`** (the file is 5,081 lines, so `:1576` is inside it but is
  unrelated prose, not a signature).
* dtype selection — **`memory_pool.py:511-512`**: `conv_dtype = cache_params.dtype.conv`,
  `ssm_dtype = cache_params.dtype.temporal`; `temporal_state` allocated `dtype=ssm_dtype` at **:604-606**,
  `intermediate_ssm_state_cache` `dtype=ssm_dtype` at **:743-754**. So **both** the main state and the
  spec-intermediate buffer follow the flag, which is consistent with the allocation logs and is the fact
  §12.12's null has to be explained against.
* the joint solve — `kv_cache_configurator.py:2372-2392`, quoted above.
* `enable_linear_replayssm_spec` **is** a real parameter (`memory_pool.py:507`), and when set it makes
  `intermediate_ssm_state_cache = None` (**:743**) — i.e. the dominant spec scratch is skipped. Real,
  reachable, and a genuinely large capacity lever that this recipe does not use.

**How to read a disagreement like this, which is the actual lesson.** Two hypotheses fit, and the
evidence does not separate them: (a) §12.18 was written against a different image that has since been
removed, and everything in it was true then; (b) it was written against something that was never the
running code. I cannot distinguish them, and **the distinction is unimportant compared with the
consequence**: a reader today cannot follow either citation to anything. An unverifiable citation is
worth what no citation is worth, and it is worse than no citation because it discourages checking.

Three things follow, all cheap:
1. **A citation should be pinned to something checkable, not just to a path.** The cheapest version:
   record the image ID next to any line number (`dev-cu13@003b7b5899ed`), because `file.py:1576` in a
   container whose image floats is not a reference. This is §6 item 7 (image digest pinning) arriving
   from an unexpected direction — it was filed as a hypothetical hygiene issue and it just produced a
   concrete, dated failure.
2. **Grep for the symbol before trusting the line.** `grep -rn "class MambaPool"` takes one second on
   the node and would have caught this at writing time.
3. **Prefer fields the server prints to fields the code computes.** Everything in §12.12's allocation
   table (`conv_state 0.24 → 0.12 GB`, `ssm MiB/slot 72.04 → 144.07`) survived this audit because it
   came from a log line. The numbers that came from reading `__init__` did not.

**What is NOT retracted.** §12.18's headline conclusion — that lowering `mamba_full_memory_ratio` is bad
because it **cuts slots**, not because of any request-count ceiling — stands, and it is *measured*
(`capped` 21 → 12 going 3.51 → 0.4, §12.8's `R09` arm). The retraction of the "160-slot ceiling" also
stands, since the symbol it rested on does not exist. The claim that needs re-grounding is the
`intermediate_ssm` share, and the honest number from the logs on disk is **66 %**, not 75 %.
