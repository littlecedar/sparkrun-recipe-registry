# ornith-honed-chat-template

Stages the honed Ornith 1.5-35B chat template where sglang's `--chat-template`
flag can read it, so the lane keeps serving the community-honed template
(`qwen3.8-honed-v22.5.1`, 30,438 B) without the recipe's caches diverging from
what sparkrun's model-preparation validator expects.

## Why this mod exists

The honed template was once injected directly into the runner nodes' HF
snapshots (`chat_template.jinja` rewritten in place through the snapshot
symlink, original preserved as `.bak`/`.dist` siblings). Sparkrun validates
every cached model file against a manifest built from hub metadata, and the
hub metadata at the pinned revision (`94e431d9`) now records different file
sizes than September's fetch distributed — so the injected snapshot fails
`wrong_size` validation and every launch dies at model distribution.

The fix keeps the two worlds honest:

- The HF caches carry the hub's content again (untouched by this mod).
- The honed template ships inside this mod's own directory and is staged to
  `${MOD_CACHEDIR}/ornith-honed-chat-template/chat_template.jinja`
  (default `/cache/runtime/ornith-honed-chat-template/chat_template.jinja`).
- The recipe points `--chat-template` at the staged path. sglang's
  `server_args.py` documents the flag as "the path of the chat template file"
  (verified against the pinned `lmsysorg/sglang:dev-cu13` image).

## Contract

- Never writes into the HF cache.
- Idempotent by content (`cmp`), not timestamps.
- Fail closed: exits 1 if the shipped template is missing, if the staged size
  is not 30,438 B, or if the staged file lacks the
  `qwen3.8-honed-v22.5.1` version marker.
- Staged file is reowned to the cache-mount UID/GID.

## Recipe wiring

`recipes/ornith/ornith-1.5-35b-a3b-nvfp4-dflash2-sglang.yaml` runs this mod
**last** (after `@eugr/mods/drop-caches` and
`@littlecedar/mods/pip-install-fastsafetensors`) and maps
`honed_chat_template` → `--chat-template {honed_chat_template}`.
