"""The aneda (GLP-steered) picom stack as a sparkrun runtime.

`dsgb10` is Picom-code's from-scratch TP=4 DeepSeek-V4.1-Flash engine and
`dsfront` its Rust OpenAI front-end; this runtime is that stack with a GLP
steering vector loaded, so the front-end serves two names from one deployment:
the stock one and a second whose requests are projected out of the residual
stream (`docs/glp.md` in the engine tree; the arm is
`recipes/ds4/deepseek-v4.1-flash-1017-aneda-tp4-1m.yaml`).

Why a runtime rather than another `runtime: vllm` recipe: the shipped picom arm
borrows vLLM's *distribution contract* (one container per node, tensor_parallel
1). A steered arm must additionally be refused on a host that is not a GB10 (the
vector is sm_121-bound), must not wait out a native rendezvous gate nothing
binds (the launcher meets its peers on 19110 itself), and carries its own image.
Those are runtime declarations, not recipe text.

The serve command is the aneda launcher's; the runtime only renders it. Every
per-rank argument, the fabric resolution and the weight/Engram staging live in
`recipes/ds4/mods/aneda-launcher/` where this arm keeps them.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from sparkrun.runtimes.base import RuntimePlugin

#: Every sparkrun plugin module declares this; the loader refuses a module
#: without it (``core/registration.py``: "missing API declaration").
SPARKRUN_PLUGIN_API_VERSION = 1

if TYPE_CHECKING:
    from sparkrun.core.recipe import Recipe

logger = logging.getLogger(__name__)

#: The launcher's argv. `{...}` names resolve from the recipe's config chain.
LAUNCHER = "bash /workspace/mods/aneda-launcher/launch.sh"
#: Exactly the four flags `launch.sh` parses; it ignores any other argv word, so
#: nothing that matters may ride this line (the steered name is `ANEDA_FRONT_ARGS`).
_LAUNCH_ARGS = (
    "--model {model}",
    "--revision {model_revision}",
    "--served-model-name {served_model_name}",
    "--port {port}",
)


class AnedaRuntime(RuntimePlugin):
    """`dsgb10` + `dsfront` with a GLP vector: two served names, one deployment."""

    runtime_name = "aneda"

    #: The engine is built for sm_121 (the vector is checkpoint-bound to it), so a
    #: host without a GB10 accelerator must fail before a 130 GB conversion runs.
    requires_capability = frozenset({"gb10"})

    def cluster_strategy(self) -> str:
        """Native: one process per node, all four with the same argv but `--rank`."""
        return "native"

    def native_rendezvous_port(
        self,
        recipe: "Recipe | None",
        overrides: dict[str, Any] | None = None,
        *,
        num_nodes: int = 1,
        init_port: int = 25000,
    ) -> int | None:
        """No rendezvous gate: the launcher's own meeting on 19110 is the gate.

        The native path would start rank 0, wait for `init_port` on the head, and
        only then start the workers. Nothing ever binds it here (the engine's ring
        bootstrap is 18620 and the launcher meets its peers on 19110), so waiting
        would burn the whole budget and then declare a healthy head dead.
        """
        return None

    def managed_rendezvous_flags(self) -> tuple[str, ...]:
        """No flag is appended: `--rank`, `--fleet` and `--socket` are the recipe's."""
        return ()

    # --- command construction ---

    def _command(
        self,
        recipe: "Recipe",
        overrides: dict[str, Any],
        skip_keys: set[str] | frozenset[str] = frozenset(),
    ) -> str:
        config = recipe.build_config_chain(overrides)
        rendered = recipe.render_command(config)
        if rendered:
            return rendered
        vals = {k: config.get(k, "") for k in ("model", "model_revision", "served_model_name", "port")}
        return " ".join([LAUNCHER, *(a.format(**vals) for a in _LAUNCH_ARGS)])

    def generate_command(
        self,
        recipe: "Recipe",
        overrides: dict[str, Any],
        is_cluster: bool,
        num_nodes: int = 1,
        head_ip: str | None = None,
        skip_keys: set[str] | frozenset[str] = frozenset(),
    ) -> str:
        """Solo and cluster: the same launcher argv (the rank comes from the env)."""
        return self._command(recipe, overrides, skip_keys)

    def generate_node_command(
        self,
        recipe: "Recipe",
        overrides: dict[str, Any],
        head_ip: str,
        num_nodes: int,
        node_rank: int,
        init_port: int = 27101,
        skip_keys: set[str] | frozenset[str] = frozenset(),
        hosts: list[str] | None = None,
        placement=None,
    ) -> str:
        """Per node: the same argv; `ANEDA_NODE_RANK` (a recipe env template) is the rank."""
        return self._command(recipe, overrides, skip_keys)

    # --- cluster lifecycle ---

    def _run_cluster(
        self,
        hosts: list[str],
        image: str,
        serve_command: str = "",
        recipe=None,
        overrides=None,
        *,
        cluster_id: str = "sparkrun0",
        env: dict[str, str] | None = None,
        cache_dir: str | None = None,
        config=None,
        dry_run: bool = False,
        detached: bool = True,
        comm_env=None,
        init_port: int = 27101,
        skip_keys: set[str] | frozenset[str] = frozenset(),
        **kwargs,
    ) -> int:
        return self._run_native_cluster(
            hosts=hosts,
            image=image,
            serve_command=serve_command,
            recipe=recipe,
            overrides=overrides,
            cluster_id=cluster_id,
            env=env,
            cache_dir=cache_dir,
            config=config,
            dry_run=dry_run,
            detached=detached,
            comm_env=comm_env,
            init_port=init_port,
            skip_keys=skip_keys,
            banner_title="aneda (dsgb10) Cluster Launcher",
            port_label="Engine Port",
            node_label="aneda node",
            **kwargs,
        )

    def _stop_cluster(
        self,
        hosts: list[str],
        cluster_id: str,
        config=None,
        dry_run: bool = False,
    ) -> int:
        return self._stop_native_cluster(hosts, cluster_id, config=config, dry_run=dry_run)
