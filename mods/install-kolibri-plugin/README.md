# mods/install-kolibri-plugin

Installs [`aleph-alpha-inference`](https://github.com/Aleph-Alpha/aleph-alpha-inference)
— Aleph Alpha's pure-Python vLLM plugin — into the serve container, so
`vllm serve Aleph-Alpha/Kolibri-1` works on arm64 GB10 nodes. The vendor's own
container image (`ghcr.io/aleph-alpha/aleph-alpha-inference`) is amd64-only;
this mod reproduces its one meaningful step on the stock multi-arch
`vllm/vllm-openai:v0.29.0` image the recipe pins.

- Pinned: `aleph-alpha-inference==1.0.0` (the release that supports vLLM 0.29).
- Installed `--no-deps` per the plugin README's documented recipe for adding
  the plugin to an existing vLLM 0.29 installation — the image's vLLM, torch
  and transformers are never touched.
- Fail closed: if the install fails, or the plugin does not import, or the
  `aleph_alpha_inference` entry point is missing from `vllm.general_plugins`,
  the mod exits 1 and the launch aborts (the serve would otherwise boot
  without the `kolibri1` parsers).
- Idempotent: a content marker at `${MOD_CACHEDIR}/mod-install-kolibri-plugin.installed`
  records the installed version; a matching marker skips the pip download.
  The import/entry-point verification runs on every pass regardless.
- Everything the mod creates is `reown()`ed to the `.cache` mount's owner.

Used by `recipes/explore/kolibri-1-78b-fp8-vllm.yaml`. Bump `PLUGIN_VERSION`
in `run.sh` together with the recipe's container pin.
