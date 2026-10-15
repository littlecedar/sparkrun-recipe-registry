# provide-uncensored-chat-template

Pre-exec mod for the `cybersec` lane's Qwen3.8-27B "cyber unlock" arm. It fetches the
**drowzeys uncensored (cybersecurity-unlock) chat template** plus the two YaRN rope
overlays the 1M route needs, from the gated overlay repo, into the sparkrun runtime
cache so the serve command can point `--chat-template` at it.

| | |
|:--|:--|
| Kind | Pre-exec mod; **modifies no model file**. |
| License | AGPL-3.0-or-later (this repo). |
| Source | `drowzeys/keys-Qwen3.8-27B-NVFP4-DFlash2-Ablit-Cybersecurity-Unlock-1M-Context-YARN-Single-DGXSpark` (gated: auto, revision pinned) |

## Why it exists

That overlay repo ships **no weights** (`0 GB` of safetensors) — it is a wiring pack: an
uncensored chat template, a YaRN rope override for the body, and a YaRN config for the
DFlash2 draft. The body weights live in `sakamakismile/Qwen3.8-27B-AEON-ULTIMATE-UNCENSORED-NVFP4`
(+ the `z-lab/Qwen3.8-27B-DFlash2` drafter). Without the template the arm serves the body's
**stock** Qwen template, i.e. it is not the arm.

sparkrun recipes cannot bind-mount host paths, so the template is staged through the managed
runtime cache (`/cache/runtime/uncensored-template/chat_template.jinja`).

## Mechanics

- Reads the node's HF token from `/cache/huggingface/token` (the overlay is gated; that token
  must have accepted the repo's release) and fetches
  `chat_template_b5_uncensored.jinja`, `yarn_hf_overrides.json`, and
  `dflash2_config_yarn_1m.json` at the **pinned revision**.
- Writes a real `chat_template.jinja` next to the fetched file (not a symlink into the cache).
- **Idempotent from content**: a non-empty `chat_template.jinja` short-circuits the fetch.
- **Fail closed**: a missing token or an empty body is fatal — a silently-missing template would
  leave the recipe serving a different arm than its name claims.
- `reown`s everything under the output dir to the cache mount's UID/GID.

## Knobs

`OVERLAY_REPO`, `OVERLAY_REVISION`, `OUTDIR` (default `/cache/runtime/uncensored-template`),
`TOKENFILE` (default `/cache/huggingface/token`).
