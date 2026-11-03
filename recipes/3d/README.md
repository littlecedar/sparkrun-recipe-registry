# 3D lane

Models whose deliverable is **3D content**, not a picture or a paragraph: interactive scenes
(Three.js / WebGL / WebGPU), procedural geometry, meshes (`GLB`/`OBJ`), and parametric CAD.

**No arm ships yet.** The lane is registered by two queue rows, `3d-qwen35-4b-3d-coder-arm` (build
the first recipe) and `3d-model-survey` (find the other candidates), both in `mad-science/queue.json`;
receipts and measured cells land in this file as they are taken.

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

## Open route question for the survey

The lane has no second arm yet, and the survey row (`3d-model-survey`) is what fills it. The one
axis worth deciding early is whether the lane wants **code-emitting** models (cheap: 4B, GGUF,
`llama.cpp`, one node, a browser as the renderer) or **mesh-emitting** diffusion arms
(weights-heavy, a diffusers or vLLM-OMNI route, GLB output, no browser). They share a lane because
they share a deliverable, not an engine — a shared ladder would measure nothing.