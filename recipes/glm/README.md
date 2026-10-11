# GLM 5.3 lane

Two model lines, both documented in
[`GLM-5.3-RECOMMENDATIONS.md`](GLM-5.3-RECOMMENDATIONS.md) (rewritten 2026-10-10; the
image claim corrected 2026-10-11):

- **Flash NVFP4 / vLLM** — [`glm-5.3-flash-nvfp4-dflash-vllm.yaml`](glm-5.3-flash-nvfp4-dflash-vllm.yaml):
  repo B's independently validated formula, image digest-pinned
  (`vllm/vllm-openai:glm53-flash`, amd64 manifest-list digest `819ec9c0…`),
  checkpoint pinned `36c184c6`. **NOT boot-verified** — TP4 needs a 4-node window;
  this session's free nodes were 2.
- **EXL3 3.0bpw / TensorFold** — no recipe yet. The engine is NOT an image build:
  clone [`bertholomus/TensorFold@glm-dsa-tp4`](https://github.com/bertholomus/TensorFold/tree/glm-dsa-tp4)
  (head `ddfad35`, cloned on the head run dir 2026-10-11) and run via repo A's
  `scripts/tfrun.sh`, which installs it editable into
  `nvcr.io/nvidia/pytorch:26.07-py3` at container start.

Licence note: the Flash line is MIT; the DFlash2 drafter is **CC BY-NC-ND** —
acceptable for this non-commercial cluster (owner decision 2026-10-11), not for
commercial resale.
