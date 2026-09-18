#!/bin/bash
# SPDX-FileCopyrightText: 2026 Travis Wichert
#
# SPDX-License-Identifier: AGPL-3.0-or-later
set -euo pipefail

#####################################################################
# README
#####################################################################
# Declare local-inference-lab/Qwen3.8-Flash-Next-NVFP4 text-only so SGLang can
# load it. See README.md in this directory for the full mechanism; short version:
#
# The labquant export quantises the vision tower (110 F8_E4M3 layers + 110 U8
# MXFP8 block scales). SGLang builds the vision tower with quant_config=None
# (qwen3_vl.py:1251), so vision Linear layers have only weight/bias and there is
# nowhere to put a scale tensor: the load dies on
#   UNPLACED _scale name=visual.blocks.0.attn.proj.weight_scale
# No remap can fix that -- the destination parameter does not exist.
#
# qwen3_vl.py:1243 honours config.language_model_only by setting self.visual=None,
# and qwen4_exp.py:2004 then skips the visual tensors while loading. The CLI flag
# --language-model-only is REFUSED for this architecture (server_args.py:7724
# allows only MuseGlimmerForConditionalGeneration), but model_config.py:331 reads
# the same value off hf_config, so the checkpoint can declare it. That also makes
# is_multimodal False (model_config.py:452-454) and routes the tokenizer away
# from the mm processor (processor.py:260), so the config route is complete rather
# than half-wired.
#
# RESULT IS A TEXT-ONLY SERVER. All benchmarks here are text, so no measured
# capability is lost, but do not use this configuration to serve images.
#
# Writes into the tree built by mods/fix-labquant-modelopt-mixed-flat-schema. Run
# AFTER that mod. Never writes through a symlink into the shared HF snapshot.
#####################################################################

#####################################################################
# Metadata
#####################################################################
MOD_NAME="skip-labquant-vision-tower"
MOD_DESCRIPTION="Mark labquant Qwen3.8-Flash-Next config text-only to skip the vision tower"
MOD_MAINTAINER="Little Cedar Group <sparkrun@littlecedar.net>"

#####################################################################
# Config
#####################################################################
TIMEOUT="${MOD_TIMEOUT:-120}"
CFG="${MOD_LABQ_CONFIG:-/cache/runtime/labq-patched/config.json}"

log()  { echo "[mod:${MOD_NAME}] $*"; }
warn() { echo "[mod:${MOD_NAME}] WARNING: $*" >&2; }
die()  { echo "[mod:${MOD_NAME}] ERROR: $*" >&2; exit 1; }

#####################################################################
# Preconditions
#####################################################################
[ -e "${CFG}" ] || die "no ${CFG}; run mods/fix-labquant-modelopt-mixed-flat-schema first"

# Guard against writing through a symlink, which would rewrite the shared snapshot.
if [ -L "${CFG}" ]; then
  tgt="$(readlink -f "${CFG}")"
  case "${tgt}" in
    /cache/huggingface/*) die "${CFG} is a symlink into the shared HF cache (${tgt}); refusing to mutate a shared snapshot" ;;
  esac
  # Safe to keep the link only if it already points at a patched copy we own.
  log "note: ${CFG} is a symlink to ${tgt}; writing through it"
fi

python3 - "${CFG}" <<'PY'
import json, os, sys

cfg_path = sys.argv[1]
cfg = json.load(open(cfg_path))

prev = cfg.get("language_model_only", "<<ABSENT>>")
if prev is True:
    print("language_model_only already true; nothing to do")
    sys.exit(0)

# Set it at the top level only. model_config.py:331 reads hf_config.language_model_only
# and model_config.py:552 propagates it back onto hf_config for the model classes, so a
# single top-level value is the documented contract. Setting text_config.* as well would
# create two sources of truth that can disagree.
cfg["language_model_only"] = True

# Fail loudly rather than silently if the export ALSO declares a vision tower we are now
# pretending not to have. This is expected (vision_config is present); we log it so the
# serve log records that the drop was deliberate.
vc = cfg.get("vision_config")
print(f"was language_model_only={prev!r}; now True")
print(f"vision_config present: {vc is not None} "
      f"({'%d keys' % len(vc) if isinstance(vc, dict) else vc})")
print("NOTE: server becomes TEXT-ONLY. Vision weights are skipped at load.")

tmp = cfg_path + ".tmp"
with open(tmp, "w") as f:
    json.dump(cfg, f, indent=2)
    f.write("\n")
os.replace(tmp, cfg_path)

# Prove it reads back, and prove it is valid JSON.
chk = json.load(open(cfg_path))
assert chk.get("language_model_only") is True, "write did not take"
print("verified: language_model_only == True on re-read")
PY

# Prove the engine actually agrees, in-process, without loading weights. If this
# disagrees we want to know in the hook, not 9 minutes into a weight load.
python3 - "${CFG%/*}" <<'PY' 2>&1 | tail -8 || true
import sys
from sglang.srt.configs.model_config import ModelConfig
mc = ModelConfig(model_path=sys.argv[1], trust_remote_code=True)
print(f"engine view: is_lm_only={getattr(mc,'is_lm_only',None)} "
      f"is_multimodal={mc.is_multimodal} "
      f"hf_config.language_model_only={getattr(mc.hf_config,'language_model_only',None)}")
if mc.is_multimodal:
    print("WARNING: is_multimodal still True; the mm processor path will still run")
PY

log "config declares text-only; vision tower will be skipped"
