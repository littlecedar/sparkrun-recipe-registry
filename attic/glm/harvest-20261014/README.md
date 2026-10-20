# GLM-5.3 TensorFold runbook scripts — harvested 2026-10-14

`AGENTS.md` (this lane) cites these scripts **by path**: the runbook's revive step is
`cd ~/glm53-tf && TF_GLM_KV=… bash tp4_start.sh 32768 "…"`. An automated node hygiene pass
reclaimed the `~/glm53-tf` trees on `.30`–`.33` on 2026-10-14, and no tracked copy existed.
These two surviving variants were copied in so the next sweep cannot destroy them again.

| File | Source on the node | What it is |
|---|---|---|
| `tp4_start.sh.launcher-clone`, `tfrun.sh.launcher-clone` | `~/src/glm-5.3-tensorfold-tp4-4xgb10/scripts/` | The upstream template (`spark1..spark4` ssh names, `MASTER=<master-ip>`, "Edit for your cluster"). |
| `tp4_start.sh.development-variant`, `tfrun.sh.development-variant` | `~/development/TensorFold/tools/` | A locally modified variant: dynamic HCA detection per node, `M=/models/glm53-exl3-3.0bpw-full`. |

Still on the nodes (not reclaimed): the TensorFold checkout at `~/development/TensorFold`,
and the launcher clone at `~/src/glm-5.3-tensorfold-tp4-4xgb10/`.

**Lost in the reclamation:** `tfrun-sglang.sh`, which existed only in the reclaimed
directory. Its behaviour is documented in `../AGENTS.md`: it swaps repo A's
`nvcr.io/nvidia/pytorch:26.07-py3` base for the already-present `lmsysorg/sglang:dev-cu13`
(digest `aa878e8d`), i.e. it is re-derivable from that sentence plus the digest.

Neither harvested variant carries this cluster's fabric addresses — the `.30–.33` master,
`NCCL_SOCKET_IFNAME` and `NCCL_IB_HCA`/GID settings live in the runbook prose and must be
re-applied on a revive.

## Provenance and license

Both sources are upstream Apache-2.0: `github.com/bertholomus/glm-5.3-tensorfold-tp4-4xgb10`
(the `*-launcher-clone` pair) and `github.com/bertholomus/TensorFold` (the
`*-development-variant` pair, locally modified). The scripts are included verbatim, with the
upstream `LICENSE`/`NOTICE.md` left in those clones on the nodes; if these copies are ever
made to carry weight here, re-check the notice requirements rather than assuming this table
is sufficient.
