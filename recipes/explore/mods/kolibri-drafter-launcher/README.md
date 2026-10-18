# kolibri-drafter-launcher

Map sparkrun's rendered launch onto `tensorfold serve` for the Kolibri-1
block-drafter arm, and arm the drafter the only way that fork image accepts:
the `TENSORFOLD_KOLIBRI_DRAFTER` environment variable.

The recipe keeps `runtime: sglang` because that is the command-template shim
path: sparkrun renders the recipe's `command:` and appends its rendezvous
flags, and this launcher owns the mapping to the TensorFold CLI. Nothing in
the image is modified.

## Why a launcher at all

- **The engine has no `--revision`.** The recipe's `model_revision:` is
  therefore spent here, as a check that the prepared path sparkrun handed us
  (`{model}`, rebound to the snapshot dir on a real launch) *is* the pinned
  snapshot. A mismatch exits 2 rather than serving a different checkpoint.
- **The drafter is not an engine flag.** TensorFold reads it from
  `TENSORFOLD_KOLIBRI_DRAFTER`, a directory of a separate HF repo. The shim
  resolves the prepared drafter snapshot (sparkrun distributed it from
  `speculative_draft_model` / `_revision`), verifies it is a *block* drafter
  release (`config.json` has `drafter.block`), then exports the variable.
  The fork image raises `no draft model on CUDA yet` if the engine's own
  `--drafter` flag is used — do not switch to it.
- **Fail closed.** An unresolvable model, an unpinned model dir, an
  unresolvable drafter, or a non-block drafter release each exit 2. A silent
  no-speculation serve would still answer correctly at roughly half the
  speed, which is the failure this gate exists to prevent.
- **The served id survives the rebind.** `{model}` reaches the command as a
  cache path, so the shim recovers the repo id from the `models--org--name`
  segment before passing `--name`.

## Behaviour

- Creates `/cache/runtime` and `/cache/runtime/torch-extensions` if absent
  (the engine JITs there), exports `TORCH_EXTENSIONS_DIR` and a writable
  `HOME` so nothing writes to a read-only `/`.
- Captures sparkrun's appended `--dist-init-addr` / `--nnodes` /
  `--node-rank` and maps them, so an unexpected rendezvous flag cannot crash
  the launch; anything else unknown is logged and ignored.
- Runs `tensorfold serve <snapshot> --no-update-check` (no boot-time version
  check), with `--context` only when the recipe sets one.

## Ordering and image

Single mod in this arm. The image is pinned by manifest digest in the recipe
(`littlecedar/dgx-spark-tensorfold-kolibri1-drafter:0.6.5-8ea05aa`) and built
from `recipes/explore/Dockerfile.kolibri1-tensorfold-drafter` — base
`lmsysorg/sglang:dev-cu13`, engine `jschmied/TensorFold` branch
`kolibri1-drafter` @ `8ea05aa`. A stock TensorFold image lacks the fork
branch, so `run.sh` fails the launch at the pre-exec gate rather than at the
first decode.