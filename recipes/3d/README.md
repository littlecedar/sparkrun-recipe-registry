# 3D lane

Models whose deliverable is **3D content**, not a picture or a paragraph: interactive scenes
(Three.js / WebGL / WebGPU), procedural geometry, meshes (`GLB`/`OBJ`), and parametric CAD.

**No arm ships yet.** The lane is registered by two queue rows, `3d-qwen35-4b-3d-coder-arm` (build
the first recipe) and `3d-model-survey` (find the other candidates), both in `mad-science/queue.json`;
receipts and measured cells land in this file as they are taken. The survey row's output is the
[two tables below](#candidates--the-survey-rows-table): six candidates that clear all four gates, and
a rejects table that records which gate each family failed so the census is never repeated. Those are
candidate rows to draft, not recipes.

The lane's inclusion rule, so it neither starves nor swallows Media: an arm belongs here when the
model **emits geometry** — scene code a browser renders, a triangle mesh, or a CAD script. Arms that
emit pixels of an already-modelled object (image and video generation) stay in `recipes/media/`;
arms that reason about 3D in text without producing geometry stay in `recipes/explore/`.

## First arm — `ccore/Qwen3.5-4B-3D-Coder`

Independent fine-tune of `Qwen/Qwen3.5-4B` by CCORE, Apache-2.0, ungated; an early preview, **not
an official Qwen release** (card and `config.json`, read 2026-11-02). Its output is a **single
self-contained HTML file that draws the scene with Three.js from a pinned cdnjs URL** — it does not
emit a mesh, so the arm's measurement is a browser render, not a file-format check.

Facts that decide the boot:

- **Architecture** `Qwen3_5ForConditionalGeneration`: 32 layers, hybrid attention 3 linear : 1 full,
  interleaved mRoPE (11/11/10), `partial_rotary_factor` 0.25, vocab 248,320, 262,144-token context,
  one MTP layer, plus a 24-layer vision tower (patch 16, spatial merge 2). The vision tower is why
  the model is multi-modal at all: it reads a reference image and writes the scene.
- **Two weight routes.** GGUF in-repo — `Q4_K_M` 2.7 GB, `Q8_0` 4.5 GB, and the optional
  `mmproj-Qwen3.5-4B-BF16.gguf` (675,568,768 B) that the card says to load with `--mmproj` for
  images; the card's own llama.cpp line is `--n-gpu-layers all --flash-attn on --ctx-size 65536
  --parallel 1` on build `b11889`. FP16 — four shards, 9,078,619,400 B total, verified by the author
  under Transformers 5.20.2; that is the route a vLLM/SGLang serve needs, and `qwen3_5` support puts
  a floor on the engine build.
- **Sampling is part of the arm**, not a taste: temperature 0.6–0.8, top-p 0.90–0.95, top-k 20–40,
  repetition penalty 1.0. The card also warns that a runtime enabling **MTP by default must turn it
  off** (LM Studio does), or the model misbehaves — the same class of trap as the shipped ds4
  `--mtp-drafts` row.
- **System prompt is load-bearing.** The card's is: use only the Three.js core ES module from
  `cdnjs.cloudflare.com/ajax/libs/three.js/0.160.0/three.module.min.js`, import no addons or legacy
  `examples/js` paths, implement camera controls inline. Drop it and the model reaches for imports
  that a self-contained page cannot satisfy.
- **Known failure mode**, from the card: duplicate variable names rather than structural breakage —
  which a render gate sees immediately as a `SyntaxError`/`ReferenceError`.

## The quality battery

`ccore/ThreeJS-3D-Scenes` (MIT, public since 2026-10-29) is the reference material: 4,146 examples —
3,933 train / 213 validation — each carrying the prompt, the full thinking trace, the complete
HTML/JS response, a complexity level, and rendered previews in an optional `previews`
configuration. The **213 validation prompts are a ready-made offline battery**: ask the served arm
for a scene, load the reply in a headless browser, and score (a) renders without a console error,
(b) emits geometry (non-empty scene graph / non-blank framebuffer), (c) honours the import
constraint. Screen-capture quality judgement stays human; the pass/fail column stays mechanical.

## Candidates — the survey row's table

Desk work, no boots: the survey row (`3d-model-survey`) files candidates, it does not author recipe
YAML. Every figure below was read on **2026-11-03** — the Hub API `/api/models/<id>?blobs=true` for
the byte column (the sum of `siblings[].size`, with the single-route fetch named where a repo ships
several quantisations or variants), PyPI's JSON API for wheel presence, and `diffusers` `master`
(`src/diffusers/__init__.py`, `src/diffusers/pipelines/`) for pipeline classes. Bytes are exact and
fits are against one 128 GB node's unified pool.

The seed families resolve as: TRELLIS-2 is `microsoft/TRELLIS.2-4B`; **Hunyuan3D 3.x does not
exist** on the Hub — the newest is `tencent/Hunyuan3D-2.1` (with `-2mini`, `-Omni`, `-Part` beside
it); SPAR3D is `stabilityai/stable-point-aware-3d`; TripoSR is `stabilityai/TripoSR`; PartCrafter is
`wgsxm/PartCrafter`; and "CAD-Coder" names two different models in two namespaces, which is why the
axis-3 row below carries a provenance note.

| candidate (read) | axis | license + ship posture | weights bytes, fit | runtime route | mechanical quality metric | next action |
|---|---|---|---|---|---|---|
| `ccore/Qwen3.5-4B-3D-Coder` (2026-11-03) | 1, scene code | Apache-2.0, ungated — ordinary arm, no banner | repo 16,977,023,807 B; one route is Q8_0 4,482,402,816 + mmproj 675,568,768, the other FP16 9,078,619,400 — fits | llama.cpp on the in-repo GGUFs, or vLLM/SGLang on FP16 (`qwen3_5` support is the engine-build floor) | the 213 `ccore/ThreeJS-3D-Scenes` validation prompts: headless render, no console error, non-empty scene graph, pinned-cdnjs import honoured | already queued as `3d-qwen35-4b-3d-coder-arm` — no new row |
| `ccore/Qwen3.5-4B-GLB-3D-Coder` (2026-11-03) | 1, scene code **and** mesh | Apache-2.0, ungated — ordinary arm, no banner | repo 7,875,514,052 B (both quants, the mmproj, and preview PNGs); Q4_K_M 2,708,804,128, Q8_0 4,482,402,848, mmproj 675,568,768. **No safetensors yet** — the card says full weights follow the training run — fits | llama.cpp only, GGUF-only preview. Same Qwen3.5 stack as the row above, so the same image and the same MTP-off trap | the 213-prompt battery **plus** a GLB gate: click Export in the headless browser, `trimesh.load` the download, verts and faces non-zero, no external URIs inside the glTF (the harness must serve or mirror `three.module.min.js`, since the generated page imports it from cdnjs and a sealed eval has no network) | draft `3d-qwen35-4b-glb-3d-coder-arm`. Pin by revision, not filename: the card replaced both GGUFs in place on 2026-11-02 04:50 UTC |
| `louhless/Ycoder-medium` (2026-11-03) | 1, GLSL | Apache-2.0 — ordinary arm, no banner | repo 994,158,162 B, one `Ycoder-medium-f16.gguf` at 994,154,208 — fits | llama.cpp (base is `Qwen/Qwen2.5-Coder-0.5B-Instruct`, a 0.5B LoRA merge) | fragment shader compiles in headless WebGL and the frame is not blank; no reference prompt set, so the battery is authored per arm | draft `3d-ycoder-medium-glsl-arm`, **low priority** — a shader is scene code, not geometry, so its cell measures less than the two Qwen rows |
| `Zhengyi/LLaMA-Mesh` + `bartowski/LLaMA-Mesh-GGUF` (2026-11-03) | 2, mesh | **NSCLv1 — non-commercial only** in the card body, on top of the Llama 3.1 Community License; the Hub *tag* says only `license:llama3.1`, the body governs → **eval-only banner, `QUESTIONS.md` #11** | upstream repo 16,069,738,398 B (8,030,261,248 BF16 params); GGUF mirror Q4_K_M 4,920,735,008, Q8_0 8,540,771,616. The mirror repo sums to 127,392,019,424 B because it carries every quant — fetch one file, not the repo — fits | **llama.cpp, text out**: the mesh is OBJ vertex/face text, so no mesh engine exists to boot | emitted OBJ parses, face count stays under the 500-face training filter, `trimesh` reports a non-empty and finite mesh; conversation is 8k context, so long meshes truncate into broken OBJ (counted, not hidden) | draft `3d-llamamesh-8b-arm` — axis 2 without leaving the llama.cpp ladder |
| `openai/shap-e` (2026-11-03) | 2, mesh | MIT — ordinary arm, no banner | repo 4,900,988,326 B; the f32 components are prior 1,262,937,295 + renderer 905,200,536 + shap_e_renderer 905,233,202 + text_encoder 494,664,885 ≈ 3.07 GB, with `.fp16.safetensors` variants at roughly half — fits | **media Diffusers-script pattern**: `ShapEPipeline` is still in `diffusers` master, the repo is diffusers-layout (`model_index.json`), and the pipeline is torch, numpy, and CLIP only. Mesh export is not shipped by diffusers, so the mod carries the marching-cubes step (`skimage`) and `trimesh` GLB write | latents → `skimage.measure.marching_cubes` → GLB: parse, non-empty, render, non-blank | draft `3d-shap-e-arm`. Boot risk to clear first: a 2023 CLIP `.bin` under `transformers` 5.17, so load the fp16 safetensors variant or pin the venv |
| `gudo7208/CAD-Coder` (2026-11-03) | 3, CAD code | card declares **Apache-2.0** over base `Qwen/Qwen2.5-7B-Instruct`; hub tags carry arXiv 2505.19713 ("CAD-Coder: Text-to-CAD Generation with Chain-of-Thought and Geometric Reward"), and `github.com/gudo7208/CAD-Coder` — the repo the card names as the project — has no LICENSE file, so the grant rests on the card alone. Record the pin and the two-namespace confusion: `CADCODER/CAD-Coder` is a **different** 13.4B model and declares nothing (see rejects) | repo 15,247,184,455 B, 7,615,616,512 BF16 params in 4 shards — fits | vLLM text serve (Qwen2 architecture, in-tree) plus a CadQuery venv on the *eval* side, not in the serve: `cadquery` 2.8.0 ships a pure-Python wheel and `cadquery-ocp` publishes `manylinux_2_28_aarch64` wheels | generated script executes, builds one solid named `result`, the STEP/STL parses, and the bounding box in mm matches the dimensions the prompt stated (string-level check, no judgement). Reference: `CADCODER/GenCAD-Code`, 147,289 train rows with `prompt` + `cadquery` fields, **no license tag** — prompt from it only if the MIT `ennucore/cadquery` battery is too thin | draft `3d-cadcoder-qwen25-7b-arm` |

## Rejects — the gate that failed

Recorded so the sweep is never re-run. Gate letters: **(a)** public weights with a servable license,
**(b)** byte sum fits one 128 GB node, **(c)** a runtime this tree already exercises, **(d)** a
mechanical quality metric. Every row below failed at least one; the ones that failed only (c) carry
their byte count so a future image class can reopen them without another census.

| repo (read) | axis | failed gate | why it is out |
|---|---|---|---|
| `microsoft/TRELLIS.2-4B` (2026-11-03) | 2, mesh | (c) | The best-quality mesh candidate and it clears (a) and (b): MIT, ungated, repo 16,237,485,044 B. `setup.sh --new-env` builds a conda env with `o_voxel`, `cumesh`, `nvdiffrast`, `nvdiffrec`, `flexgemm`, and `flash-attn` from source against CUDA toolkit 12.4, and the media lane's image base is `nvidia/cuda:*-base` (`vllm` `Dockerfile` `FINAL_BASE_IMAGE`), which carries no `nvcc`. A 3D image class, the way `ds4`/`glm` carry their own TensorFold Dockerfiles, is the only door |
| `tencent/Hunyuan3D-2.1` and `-2mini` (2026-11-03) | 2, mesh | (a) | Runtime was the surprise: the shape stage clears (c). `hy3dshape` extracts geometry with `skimage.measure.marching_cubes` (no `torchmcubes`), imports no flash-attn, and its one awkward import-time wheel, `pymeshlab`, publishes `manylinux_2_35_aarch64` builds. Shape-only cost is 8,022,037,920 B (DiT `model.fp16.ckpt` 7,366,389,768 + `hunyuan3d-vae-v2-1` 655,648,152), the repo is 14,909,683,275 B, and `-2mini`'s single variant is ≈4,478,607,440 B — all fit. It dies on the license: Tencent Hunyuan 3D 2.1 Community License, territory-limited to the world **minus the EU, the UK, and South Korea**, 1M-MAU cap, and outputs may not be used to improve another model. That is harsher than `#11`'s non-commercial case and matches the MiniMax-H3 precedent, a `zz-` probe at most, and it needs its own `QUESTIONS.md` entry before it is anything. Second defect, recorded here: the paint stage needs `custom_rasterizer` + `DifferentiableRenderer` compiled, so shape-only means **untextured** GLB |
| `stabilityai/stable-point-aware-3d` (2026-11-03) | 2, mesh | (a), (c) | 7,334,551,700 B in one `model.safetensors` fits, and it is MIT-adjacent only in the sense that the code is public: weights are `gated: auto` under the Stability AI Community License, and on 2026-11-03 the Hub answered this account's token with "not in the authorized list", so nothing can be staged without an owner access request. Runtime is a second wall: `requirements.txt` installs `./texture_baker/` and `./uv_unwrapper/` in place (local CUDA packages) and pins `transformers==4.42.3` |
| `stabilityai/TripoSR` (2026-11-03) | 2, mesh | (c) | Clean MIT, 1,679,825,527 B total (`model.ckpt` 1,677,246,742), OBJ or GLB export built in, so (a), (b), and (d) pass. `tsr/models/isosurface.py` imports `torchmcubes`, which had no PyPI project on 2026-11-03 (`404`), and the card's install line is `pip install git+https://github.com/tatsy/torchmcubes.git` — a build needing a toolchain the serving image lacks. Reopen either with an image class or with a swap to the `mcubes` wheel (aarch64 manylinux wheel published, 2026-11-03); the swap is **unproven**, not measured |
| `wgsxm/PartCrafter` (2026-11-03) | 2, mesh | (c) | MIT and 3,973,450,778 B fits (transformer 2,879,298,752 + DINOv2 encoder 608,785,376 + VAE 485,361,378), and its `model_index.json` names `PartCrafterPipeline`, which looks like a diffusers route. It is not one: every component resolves to the project's own `src.*` modules, so the repo's `src` tree must be on the path, and the decoder imports `torch_cluster`, which PyPI ships only as an sdist and whose own install line is the PyG `torch-2.5.1+cu124` wheel index (x86-only). Compiled build, plus `briaai/RMBG-1.4` for background removal |
| `raven38/pixal3d-q8_0-v1` (2026-11-03) | 2, mesh | (a), (c) | 8,091,994,774 B of GGUFs for `pixal3d.cpp` — a TRELLIS-shaped C++/WebGPU runtime with no presence in this tree — and the card's license is `other` = `mit-and-dinov3`, where the DINOv3 license is not one this tree can ship. Watch it as a future GGUF-mesh route; it is not a row |
| `CADCODER/CAD-Coder` (2026-11-03) | 3, CAD code | (a) | 26,702,372,993 B, `llava_llama`, 13,350,839,296 BF16 params. No card, no README, no license tag: nothing grants serving rights, and it is a different model from the `gudo7208` row despite the name |
| `thirteen3333/text2cad-multiturn` (2026-11-03) | 3, CAD code | (c) | 635,683,133 B as a single `llama_text2cad_multiturn.pth` with dim 256, 8 layers, Chinese prompts, and no tokenizer or config in the repo — no runtime in this tree loads it |
| `hanasaan/frag-loop` (2026-11-03) | 1, GLSL | (a), (c) | 3,249,587,470 B `frag-loop.pt` plus `tokenizer.pkl`, a from-scratch PyTorch shader LM under `license: other` with no named terms in the card: neither a runtime nor a grant |
| `guell00/OBSIDIAN-9B-Coder` (2026-11-03) | 1, scene code | (a) | A `threejs`-tagged 9B coder with **no license tag** on the card at all |
| `coderofpears/gemma-cad` (2026-11-03) | 3, CAD code | (a) | 10,278,842,002 B, `gemma4` architecture, 205-byte card, `license: apache-2.0` with no base model named: the grant cannot be traced to a licensor |
| `yuvit-batra/qwen2.5-coder-7b-cadquery-gguf` (2026-11-03) | 3, CAD code | none — **held in reserve** | 4,683,078,719 B single GGUF, `cc-by-nc-sa-4.0` → eval-only banner if used, llama.cpp route, same CadQuery metric as the axis-3 row. Out of the table because `gudo7208/CAD-Coder` is Apache-2.0 and has 4× the parameters; it is the fallback if that provenance ever fails |

## What the survey settles

The lane's own open question — code-emitting models against mesh-emitting diffusion arms — turned out
to be the wrong cut. **Four of the six filed candidates ride runtimes this tree already boots**:
the two `ccore` Qwen3.5 rows and LLaMA-Mesh on `llama.cpp`, `gudo7208/CAD-Coder` on vLLM, and only
Shap-E needs a diffusers venv. Axis 2 is therefore **not** gated by an engine class: a mesh arm can be
a text arm that emits OBJ tokens, which is LLaMA-Mesh, 4.9 GB, one quantisation, no new image, no
compiled extension.

What does gate the lane is the license and the 3D-specific runtime stack. Every heavy mesh family —
TRELLIS-2, Hunyuan3D-2.1, SPAR3D, TripoSR, PartCrafter — needs a purpose-built image with `nvcc` and
compiled CUDA packages, because the serving image base is `nvidia/cuda:*-base`; two of them then
fail on license as well (Tencent's territory limit, Stability's gated community license). A 3D image
class, built the way `ds4` and `glm` carry their own TensorFold Dockerfiles, is the single change
that reopens TRELLIS-2, TripoSR, and Hunyuan shape at once. Until then the ordered next actions are
`3d-qwen35-4b-glb-3d-coder-arm` (the only mesh-file route with no new image), then
`3d-llamamesh-8b-arm` (eval-only), then `3d-shap-e-arm`, then `3d-cadcoder-qwen25-7b-arm`, with
`3d-ycoder-medium-glsl-arm` last.

The cells do not merge. A render gate, an OBJ parse gate, and a CadQuery dimension gate measure
different questions, so a "3D ladder" across axes would compare a browser against a file parser —
the shared thing is the node and the receipt format, not the column.