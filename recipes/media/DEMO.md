# Media lane demo workproduct — 2026-10-26 (tp4-single, window 4)

One demo artifact per arm, produced on the idle single-node pair (.30/.35) while the quartet ran its
window-4 cells, under the owner's TP<4 parallelism ruling (coordinated boots, never during a
quartet measurement cell without a go). Artifacts live in the head receipt tree
`~/benchmarks/tp4-single-20261026/media-demo/`; this file indexes them by relative path. No node
addresses are recorded here; each arm's receipt carries the launch facts.

| arm | recipe | artifact (head receipt path) | what it shows | receipt |
|---|---|---|---|---|
| Kokoro-82M TTS (CPU) | `kokoro-82m-tts-cpu.yaml` | `~/benchmarks/tp4-single-20261026/media-demo/kokoro-sample.wav` | 24 kHz mono 16-bit WAV, 5.45 s audio from an 18-word sentence, 3.48 s generation → **RTF 0.64**; the OpenAI-compatible model id is `kokoro` (the image rejects the repo id with `invalid_model`) | `RECEIPT-kokoro.md` |
| humanizer-12B (Q6_K, llama.cpp) | `humanizer-12b-q6k-llamacpp.yaml` | `~/benchmarks/tp4-single-20261026/media-demo/humanizer-rewrite.txt` | forum-post draft rewritten via the arm's byte-exact prompt format (fingerprint `cc51d66b4c593fbe` asserted by `tools/humanizer-measure.py`): 173 completion tokens in 9.26 s ≈ **18.7 t/s**, matching the shipped 17.92 t/s C1 | `RECEIPT-humanizer.md` |
| drama-3 TTS (35B fp8, vLLM-Omni) | `drama-3-35b-a3b-fp8-vllm-omni-tts.yaml` | `~/benchmarks/tp4-single-20261026/media-demo/drama3-sample.wav` + `drama3-sample-take2.wav` | seeded takes (seed 7) are **byte-identical** (sha256 `f5ade9ab…` both): warm take 3.93 s wall for 4.64 s of 44.1 kHz audio → **warm RTF 0.85**, reproducing the shipped 0.848 ± 0.015; first request of the boot is cold (RTF 1.69, compile warm-up) | `RECEIPT-drama3.md` |
| Qwen-Image-2.1-Turbo (7B bf16) | `qwen-image-2.1-turbo-7b-bf16-diffusers-script.yaml` | `~/benchmarks/spares-20261026/qwen-image-demo/t2i_1024x1024_seed7.png` | **LANDED 2026-10-26 (spares-lane, `.30`)** after the prefill row's DONE marker: pool body 32,493,327,348 B `du`-verified at pin `fc13ba19`; render pair seed 7 twice → **byte-identical PNGs (sha256 `d2d2c7fc…`)**, 1024² 8-step, warm render 12.7 s, peak 36.8 GiB alloc / 37.6 GiB reserved (matches the shipped arm's 36.85/37.68 and its 11.3-11.4 s class); load 295 s after the launcher's snapshot-path fix (first boot died `OfflineModeIsEnabled` — pool bodies must be bound by snapshot path, not hub revision; fix in the launcher mod, trap recorded in `README.md`) | this row + `~/benchmarks/spares-20261026/qwen-image-demo/RECEIPT.md` |
| LTX-2.5 T2V (22B nvfp4, ComfyUI) | `ltx-2.5-22b-nvfp4-t2v-comfyui-script.yaml` | `~/benchmarks/spares-20261026/ltx25-demo/t2v_42_1344x768_121f_00002.mp4` | **LANDED 2026-10-26 (spares-lane, `.35`)** after the `-lgc 0,2200` prerequisite was applied on the host (driver accepts; the applications-clock readback stays 2418 — recorded in the receipt so future `.35` arms check under load) and the gated weights' prefill DONE marker: render of the row's template shape (seed 42, 1344×768, 121 frames @ 24 fps) → **success, wall 128.36 s cold-first-generate** (row's classes: 78.1 warm / 100.13 cold), peak 83.37 GiB (shipped 83.45-84.00); artifact ffprobe-verified **h264 1344×768 @ 24 fps, 121 frames, AAC audio, 5.04 s** (sha256 `39f5f7af…`) | this row + `~/benchmarks/spares-20261026/ltx25-demo/RECEIPT.md`; queue row `ltx-25-t2v-spare-demo` done |

## Standing rules these demos ran under

- **Pre-flight body check on every boot** (owner rule, adopted after the stub class appeared): `du -sbL`
  through the exact pinned snapshot dir under `/cache/huggingface/hub/models--<org>--<name>/snapshots/<pin>/`,
  require ≫100 KB, before any launch; a stub = do not boot, check the prefill ledger's DONE marker.
- **Launch route (pool era):** the head's real `HOME` + `--cluster WOPR -H <rail-IP>`; the
  `$PWD/.local/sparkrun-home` override fails single-node boots with "prepared model is not visible
  through the workload mounts" (`recipes/ds4/README.md` Launch caveats).
- **Stop discipline:** every boot stopped by literal task id, 0-containers census after; the
  GPU-exclusive allocation means a CPU arm still occupies the slot until stopped (hit when kev
  followed Kokoro, and Kokoro followed kev).
- **kev-0.8b is not a demo row**: its boot died of a bind conflict, not a stub — separate queue task
  `kev-bind-conflict-fix` (log: `serve-kev-dead.log`).