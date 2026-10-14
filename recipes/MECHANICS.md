# Mechanics

Command-template rules and traps every recipe author needs, plus the per-family agent-guide
index. Moved verbatim from the former `recipes/README.md` `# Notes` section (2026-10-14).

# Notes

## vLLM custom-command templates: hardcode the snapshot path (sparkrun 0.4.0-alpha)

For a vLLM recipe whose `command:` is a template, sparkrun's render resolves `{model}` to the
**declared repo id** (not the prepared snapshot path) and **strips `--revision`** from the template —
then its own serve-command validator demands a path or `--revision=<prepared-sha>` token and refuses
the launch (`serve command does not consume the validated model`) after the model has already been
distributed. `{model_revision}` does not survive either. The pattern that boots (used by the qwen3
coder, decision, explore and glm5 lanes):

```yaml
model_revision: <sha>                      # keeps distribution pinned
command: >
  vllm serve
  /cache/huggingface/hub/models--<org>--<name>/snapshots/<sha>
  --served-model-name <org>/<name>         # so clients keep the HF id
  --revision=<sha>                         # the `=` spelling is the one the validator accepts
```

The in-container path is deterministic: `${HF_HUB_CACHE}/models--<org>--<name>/snapshots/<sha>` with
`--` for `/` in the repo id. The sglang runtime is unaffected (it renders the path and keeps
`--revision`). Three related traps:

1. A `defaults:` key referenced by the command but **missing** renders as a literal into the serve
   line and only dies at the engine — guarded by `tests/test_recipe_placeholder_resolution.py`.
2. vLLM's speculative-config field is **`model`**, not `draft_model` — sparkrun's draft binding reads
   the same key.
3. The speculative config must live in **`defaults:`** (`speculative_config: '<json>'`, referenced as
   `'{speculative_config}'` in the command), not inline: only then does sparkrun add the draft repo to
   the distribution set and inject the prepared revision. An inline literal leaves the drafter
   undistributed and the offline engine dies resolving it — measured on the Nemotron boot 2026-10-11.
   Inside that JSON, use **literals**: two placeholder behaviours were observed — inside a defaults
   VALUE nothing resolves (the raw token survives into sparkrun's own `json.loads` and kills the
   launch), and inside the command template an *unquoted* placeholder resolves but a *quoted* one
   does not (braces inside quoted JSON blobs are masked). The boot-proven form is literals in the
   defaults JSON; comments never go inside a folded `command:` block (a `>` scalar keeps them as
   literal text and the shell-comment rule then eats every following flag).
   sglang is again unaffected (`speculative_draft_model` in defaults is the shipped pattern).

## sglang custom-command templates: declare the served model id

An sglang recipe whose `command:` template writes `--served-model-name {model}` does **not** serve
the repo id on a real launch: sparkrun rebinds every `{model}` occurrence to the prepared on-disk
snapshot path (`models/runtime.py::bind_runtime_models`), so the engine advertises
`/cache/huggingface/hub/models--<org>--<name>/snapshots/<sha>` as its `model` id — wrong for every
client, the proxy and any benchmark that sends the HF id. `-n` still prints the repo id (bindings
exist only on a launch), so a dry run cannot show this. The same defect with the flag omitted: a
`command:`-templated arm with no `--served-model-name` at all serves the `--model-path` value.

Declare the literal and render the flag from it (sparkrun's own prescription —
`core/validation.py` suggests exactly this when it sees a hardcoded flag):

```yaml
defaults:
  served_model_name: <org>/<name>          # the upstream repo id
command: >
  --model-path {model}
  --served-model-name {served_model_name}
```

Both lines are required together: a declared key the command never references is rejected by
`tests/test_recipe_placeholder_resolution.py::InertDefaults`, and the runtime's own append only
fires when the flag is absent (`runtimes/base.py`). An arm whose `--model-path` is a mod-built tree
rather than the snapshot (labquant) also needs `--revision {model_revision}` — the launch validator
requires a revision token once the prepared path no longer appears in the command. The two ds4 arms
are the deliberate exception: their in-container launchers normalize a path back to the repo id
(`tests/test_ds4_recipes.py` guards it). A fix is not verified until a live boot's `GET /v1/models`
returns the repo id.

The knapcio TP4 arm pins `model_revision:` without spelling `--revision`, so `validate` warns
`unpinned-model-revision` there: its launcher is handed the prepared snapshot path through `{model}`
and never resolves a ref itself. That warning is expected for that arm, not a defect — the mechanism
is in `attic/ds4/AGENTS.md` §5.

Per-family agent guides: the Qwen3.8-Flash-Next lane carries its own
[`attic/qwen4/AGENTS.md`](../attic/qwen4/AGENTS.md) (state, constraints, workstream plan, runbook) and
[`qwen4/README.md`](qwen4/README.md) (the recipe/lane summary), with `../attic/qwen4/NOTES.md` (working notes).
Read those before starting work in that directory. Archived arms and the lane's research record,
journal, and coordination ledger live under [`../attic/qwen4/`](../attic/qwen4/).

The DeepSeek V4.1-Flash lanes are documented in [`ds4/README.md`](ds4/README.md) (user guide)
and [`attic/ds4/AGENTS.md`](../attic/ds4/AGENTS.md) (design, boot gates, guards, and measurement discipline for
both the knapcio TP=4 and TensorFold TP=2 lanes); the retired vLLM/EXL3 lane is under
[`../attic/ds4/`](../attic/ds4/).


The IFM K2-Horizon lanes are documented in [`ifm/README.md`](ifm/README.md) (recipe
summary) and [`attic/ifm/AGENTS.md`](../attic/ifm/AGENTS.md) (constraints, falsified claims, guards,
and the validation ritual for the `0.9B` / `7B-FP8` set); the
research record and journals are git-ignored working files beside them.

The Ornith 1.5 lanes are documented in [`ornith/README.md`](ornith/README.md) (per-recipe wiring,
caveats, and the three archived arms) and [`attic/ornith/AGENTS.md`](../attic/ornith/AGENTS.md) (lane state,
constraints, the A/B negative result, and the validation ritual); the lane's guards are in
`tests/test_ornith_recipes.py` (O1–O5).

The Qwen3 lane is documented in [`qwen3/README.md`](qwen3/README.md) (recipe summary) and
[`attic/qwen3/AGENTS.md`](../attic/qwen3/AGENTS.md) (model thesis, tunable rationale, negative results, and the
validation ritual); the lane's research record — including the no-spec control recipe, the measured
DSpark arm, and the depth/SSM/queue threads — moved to [`../attic/qwen3/`](../attic/qwen3/) on
2026-10-11 with a manifest mapping its `§N` cite forms.
