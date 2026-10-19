# attic/explore/mods/install-kolibri-plugin

Archived 2026-10-19 with its only users (the Kolibri FP8 base and the three 4-bit
packs). Archived recipes still resolve `mods/<name>` adjacent to themselves.

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
  records the installed version; the pip install is skipped only when the marker
  matches **and** the module imports at that version in the current container
  layer. The marker lives on the persistent `.cache` mount while pip installs
  into the container's **ephemeral** layer, so a marker alone is not proof the
  module is present (measured 2026-10-13 on `.35`: a second boot skipped on a
  surviving marker and died `ModuleNotFoundError: No module named
  'aleph_alpha_inference'` in `launch_inference`). The import/entry-point
  verification then runs on every pass regardless, and the marker is rewritten
  only after it passes.
- Everything the mod creates is `reown()`ed to the `.cache` mount's owner.
- Guard: `attic/explore/test_kolibri_plugin_mod.py` executes `run.sh` against
  temp dirs with stubbed `pip`/`python3` (no package is installed, so it runs
  anywhere). The negative control reproduces the 2026-10-13 outage shape — a
  marker that outlived its module — and asserts the mod re-installs rather than
  skipping.

Used by the archived `attic/explore/kolibri-1-78b-fp8-vllm.yaml`,
`kolibri-1-nvfp4a16-fp8-vllm.yaml`, `kolibri-1-nvfp4-experts-vllm.yaml` and
`kolibri-1-mxfp4-mxwave-vllm.yaml`. Bump `PLUGIN_VERSION` in `run.sh` together
with those recipes' container pin.
