#!/bin/bash
# SPDX-FileCopyrightText: 2026 Little Cedar Group
#
# SPDX-License-Identifier: AGPL-3.0-or-later
set -euo pipefail

#####################################################################
# README
#####################################################################
# Materialize the query/document chat template that Qwen3-VL-Reranker needs
# when served by vLLM, at a path the recipe can name unconditionally.
#
# Why this exists:
#   Qwen/Qwen3-VL-Reranker-* ships `architectures: ["<BaseForConditionalGeneration>"]`
#   (the plain generative class), so `--runner pooling` alone resolves the model to the
#   generative runner and vLLM rejects the launch with
#   "Model ... does not support pooling tasks". The fix — an `--hf-overrides` rewrite to
#   the sequence-classification architecture — works (VERIFIED, vLLM b40673cd0:
#   the suffix table in vllm/config/model.py maps *ForSequenceClassification to
#   (pooling, classify), and _ModelRegistry._normalize_arch resolves
#   <Base>ForSequenceClassification back to the registered base class).
#   But scoring a (query, document) pair needs a chat template that reads the
#   `query` / `document` message roles vLLM's score endpoint synthesizes
#   (vllm/entrypoints/pooling/scoring/io_processor.py builds
#   {"role": "query", ...}). The checkpoint's own `chat_template.jinja` is the plain
#   Qwen3-VL *chat* template and has no `query`/`document` handling, so serving with it
#   silently scores an empty prompt pair.
#
#   The template vLLM actually wants is `examples/pooling/score/template/
#   qwen3_vl_reranker.jinja`, which lives in the vLLM *source tree*. The recipe image's
#   WORKDIR is the vLLM checkout, so it is there only if the image ships `examples/`;
#   that has to be assumed rather than guaranteed. This mod removes the assumption.
#
# What it does:
#   1. Writes the template to ${TEMPLATE_DEST} (a sparkrun-managed cache path). Default
#      source is the BUNDLED template below; `PREFER_UPSTREAM=1` takes vLLM's example file
#      instead when the image ships it. Reason for preferring ours: vLLM's
#      examples/pooling/score/template/qwen3_vl_reranker.jinja is TEXT-ONLY — it renders
#      content via `map(attribute="content") | first`, which emits a Python repr for a
#      multimodal content list, so image documents would score from garbage. The bundled
#      template is modelled on Qwen/Qwen3-VL-Reranker-2B's own
#      additional_chat_templates/reranker.jinja: same system line, same
#      `<Instruct>:/<Query>:/<Document>:` layout, same trailing assistant marker, plus
#      vision placeholder handling and a per-request `instruction` override.
#   2. Fails the launch loudly if the destination cannot be written, so a broken
#      colocated reranker never serves plausible-looking scores from an empty template.
#
# Usage in a recipe:
#   mods:
#     - "@littlecedar/mods/provide-qwen3-vl-rerank-template"
#   defaults:
#     reranker_chat_template: /cache/runtime/templates/qwen3-vl-reranker-query-document.jinja
#   command: ... --chat-template {reranker_chat_template}
#
# See recipes/qwen3/QWEN3-EMBED-OPTIMIZATION-WORK.md §2 for the evidence trail.
#####################################################################

export MOD_NAME="provide-qwen3-vl-rerank-template"
export MOD_DESCRIPTION="Materialize the Qwen3-VL-Reranker query/document chat template at a stable path"
export MOD_MAINTAINER="Little Cedar Group <sparkrun@littlecedar.net>"
export TIMEOUT="${MOD_TIMEOUT:-120}"
# Repo convention (mods/mod-template/run.sh:29) is MOD_CACHEDIR, defaulting to the
# runtime-cache mount; sparkrun exports XDG_CACHE_HOME at that same mount and its own
# validator nudges recipes to reference $XDG_CACHE_HOME rather than baking /cache/runtime in
# (core/validation.py:555). Honour both in that order, with the literal as a last resort.
# The recipe's {reranker_chat_template} default resolves against the same variable, so the
# two cannot drift if an operator relocates the cache root via `runtime_cache:` in config.
RUNTIME_ROOT="${MOD_CACHEDIR:-${XDG_CACHE_HOME:-/cache/runtime}}"
# Drift detector. The recipe names its template path as ${XDG_CACHE_HOME:-/cache/runtime}/...,
# and a mod cannot export variables into the serve command. So if an operator sets
# MOD_CACHEDIR to somewhere other than the runtime-cache root, this mod would publish a
# template the serve line never reads — and vLLM would silently fall back to the checkpoint's
# query/document-blind template, which is the exact failure this mod exists to prevent.
# Detectable here, so refuse rather than succeed quietly.
if [[ -n "${MOD_CACHEDIR:-}" && -n "${XDG_CACHE_HOME:-}" && "${MOD_CACHEDIR}" != "${XDG_CACHE_HOME}" ]]; then
  echo "${MOD_NAME}: FATAL: MOD_CACHEDIR=${MOD_CACHEDIR} differs from XDG_CACHE_HOME=${XDG_CACHE_HOME}." >&2
  echo "${MOD_NAME}:   the recipe's --chat-template resolves against XDG_CACHE_HOME, so the" >&2
  echo "${MOD_NAME}:   template published here would never be read and scoring would silently" >&2
  echo "${MOD_NAME}:   use the wrong prompt. Unset MOD_CACHEDIR, or override the recipe's" >&2
  echo "${MOD_NAME}:   reranker_chat_template default to ${MOD_CACHEDIR}/templates/qwen3-vl-reranker-query-document.jinja." >&2
  exit 1
fi
export LOGDIR="${MOD_LOGDIR:-${RUNTIME_ROOT}/modlogs}"
export TEMPLATE_DIR="${TEMPLATE_DIR:-${RUNTIME_ROOT}/templates}"
export TEMPLATE_NAME="${TEMPLATE_NAME:-qwen3-vl-reranker-query-document.jinja}"
export TEMPLATE_DEST="${TEMPLATE_DEST:-${TEMPLATE_DIR}/${TEMPLATE_NAME}}"
export UPSTREAM_TEMPLATE="${UPSTREAM_TEMPLATE:-examples/pooling/score/template/qwen3_vl_reranker.jinja}"
export MOD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

reown() {
  log "resetting permissions to ${USER_UID}:${USER_GID} on ${*}"
  chown -R "${USER_UID}:${USER_GID}" "${@}"
}

log() {
  local _message
  _message="${*}"

  o() {
    local _ts _message
    _message="${*}"
    _ts="$(date -Ins)"
    printf '%s [%s] %s\n' "$_ts" "${MOD_NAME}" "${_message}" | tee -a "${LOGDIR}/${MOD_NAME}.log"
    [[ -x "$(type -fp logger)" ]] && logger -t "${MOD_NAME}" -- "${_message}"
  }

  if [[ -z "${*}" ]]; then
    while read -rt "${TIMEOUT}" line; do
      o "${line}"
    done
  else
    o "${*}"
  fi
}

log_var() {
  local _key _val
  _key="${1}"
  _val="${!_key}"
  log "${_key}=${_val}"
}

log_cmd() {
  log "            "
  log "            "
  log "=== ${1} ==="
  "${@}" 2>&1 | log
}

# Resolve the owner of the runtime cache root so `reown` can hand files back to uid 1000.
# Mods run as root, so anything written under the mount is root-owned and unlinkable by the
# serving user unless we chown it. Deferred past the log helpers so a missing mount reports
# through the log rather than as a bare shell error. RUNTIME_ROOT was already resolved above
# (with MOD_CACHEDIR precedence); re-deriving it here would silently drop that precedence.
if [[ ! -d "${RUNTIME_ROOT}" ]]; then
  echo "${MOD_NAME}: FATAL: runtime cache root ${RUNTIME_ROOT} is absent; cannot publish the template" >&2
  exit 1
fi
export USER_UID="$(stat -c '%u' "${RUNTIME_ROOT}")"
export USER_NAME="$(stat -c '%U' "${RUNTIME_ROOT}")"
export USER_GID="$(stat -c '%g' "${RUNTIME_ROOT}")"
export USER_GROUP="$(stat -c '%G' "${RUNTIME_ROOT}")"

if ! [[ -d "${LOGDIR}" ]]; then
  mkdir -p "${LOGDIR}"
fi
if [[ -f "${LOGDIR}/${MOD_NAME}.log.gz" ]]; then
  rm -f "${LOGDIR}/${MOD_NAME}.log.gz"
fi
if [[ -f "${LOGDIR}/${MOD_NAME}.log" ]]; then
  gzip "${LOGDIR}/${MOD_NAME}.log"
  touch "${LOGDIR}/${MOD_NAME}.log"
fi
reown "${LOGDIR}"

log "${MOD_NAME} - ${MOD_DESCRIPTION}"
log "${MOD_MAINTAINER}"
log_var MOD_DIR
log_var TEMPLATE_DEST
log_var UPSTREAM_TEMPLATE

# The vLLM example template is resolved relative to the image's WORKDIR, which is the
# vLLM checkout (/workspace/vllm in the pinned ghcr.io/spark-arena/dgx-vllm-eugr-nightly*
# images). Probe it from the real WORKDIR rather than from this mod's directory — mods
# are exec'd with the mod directory as CWD, so a bare relative probe would always miss.
# Preference: the BUNDLED multimodal template, not vLLM's example file.
#
# examples/pooling/score/template/qwen3_vl_reranker.jinja is text-only. It renders the
# pair with `messages | selectattr("role","eq","query") | map(attribute="content") | first`,
# which for a multimodal content *list* emits a Python repr of the list rather than the
# image placeholder — i.e. an image-carrying document scores from garbage, silently. This is
# a vision-language reranker and the recipe caps --limit-mm-per-prompt at 4 images per
# prompt precisely because images are expected, so the bundled template (which walks
# content parts and emits the vision placeholders) is the correct default.
#
# Set PREFER_UPSTREAM=1 to take vLLM's file when the image ships it (text-only workloads, or
# to A/B the two against a hand-ranked set).
source_template=""
if [[ "${PREFER_UPSTREAM:-0}" == "1" ]]; then
  for base in "${WORKSPACE_DIR:-}" "${VLLM_BASE_DIR:-}" /workspace/vllm "$(pwd)"; do
    [[ -n "${base}" ]] || continue
    if [[ -f "${base}/${UPSTREAM_TEMPLATE}" ]]; then
      source_template="${base}/${UPSTREAM_TEMPLATE}"
      log "PREFER_UPSTREAM=1: using the pinned vLLM example template (TEXT-ONLY): ${source_template}"
      break
    fi
  done
  if [[ -z "${source_template}" ]]; then
    log "PREFER_UPSTREAM=1 but ${UPSTREAM_TEMPLATE} was not found; falling back to the bundled template"
    log "  (probed: \${WORKSPACE_DIR}=\${WORKSPACE_DIR:-} \${VLLM_BASE_DIR}=\${VLLM_BASE_DIR:-} /workspace/vllm \$(pwd))"
  fi
fi

if [[ -z "${source_template}" ]]; then
  log "writing the bundled multimodal template (reads query/document roles AND image/video content parts)"
  bundled="${TEMPLATE_DIR}/.bundled-${TEMPLATE_NAME}"
  mkdir -p "${TEMPLATE_DIR}"
  cat > "${bundled}" <<'TPL'
{%- set default_instruction = "Given a search query, retrieve relevant candidates that answer the query." -%}
{#- Instruction precedence, matching vLLM's example template (instruction, then instruct,
    then a system message) so a request can override it either way. -#}
{%- set explicit_instruction = "" -%}
{%- if instruction is defined and instruction -%}
    {%- set explicit_instruction = instruction -%}
{%- elif instruct is defined and instruct -%}
    {%- set explicit_instruction = instruct -%}
{%- endif -%}
{%- set ns = namespace(instruction="", found_instruction=false) -%}
{%- for message in messages -%}
    {%- if message.role == "system" -%}
        {%- if message.content is string -%}
            {%- set ns.instruction = message.content -%}
        {%- else -%}
            {%- for content in message.content -%}
                {%- if 'text' in content -%}
                    {%- set ns.instruction = ns.instruction + content.text -%}
                {%- endif -%}
            {%- endfor -%}
        {%- endif -%}
        {%- set ns.found_instruction = true -%}
    {%- endif -%}
{%- endfor -%}
{%- if explicit_instruction -%}
    {%- set ns.instruction = explicit_instruction -%}
{%- elif not ns.found_instruction -%}
    {%- set ns.instruction = default_instruction -%}
{%- endif -%}
{%- set image_count = namespace(value=0) -%}
{%- set video_count = namespace(value=0) -%}
{%- macro render_multimodal(message) -%}
    {%- if message.content is string -%}
        {{- message.content -}}
    {%- else -%}
        {%- for content in message.content -%}
            {%- if content.type == 'image' or 'image' in content or 'image_url' in content -%}
                {%- set image_count.value = image_count.value + 1 -%}
                {%- if add_vision_id is defined and add_vision_id %}Picture {{ image_count.value }}: {% endif -%}
                <|vision_start|><|image_pad|><|vision_end|>
            {%- elif content.type == 'video' or 'video' in content or 'video_url' in content -%}
                {%- set video_count.value = video_count.value + 1 -%}
                {%- if add_vision_id is defined and add_vision_id %}Video {{ video_count.value }}: {% endif -%}
                <|vision_start|><|video_pad|><|vision_end|>
            {%- elif 'text' in content -%}
                {{- content.text -}}
            {%- endif -%}
        {%- endfor -%}
    {%- endif -%}
{%- endmacro -%}
{{- '<|im_start|>system\nJudge whether the Document meets the requirements based on the Query and the Instruct provided. Note that the answer can only be "yes" or "no".<|im_end|>\n<|im_start|>user\n<Instruct>: ' + ns.instruction + '<Query>:' -}}
{%- for message in messages if message.role == "query" -%}
    {{- render_multimodal(message) -}}
{%- endfor -%}
{{- '\n<Document>:' -}}
{%- for message in messages if message.role == "document" -%}
    {{- render_multimodal(message) -}}
{%- endfor -%}
{{- '<|im_end|>\n' -}}
{%- if add_generation_prompt -%}
    {{- '<|im_start|>assistant\n' -}}
{%- endif -%}
TPL
  source_template="${bundled}"
fi

mkdir -p "${TEMPLATE_DIR}"
install -m 0644 "${source_template}" "${TEMPLATE_DEST}"

# A template that renders an empty prompt pair still scores happily and returns a
# confident-looking number, so verify the two properties the score endpoint depends on
# before allowing the launch: it must read the roles vLLM synthesizes (either
# `role == "query"` or `selectattr("role", "eq", "query")`), and it must emit both
# <Query>: and <Document>: anchors.
# Matches either jinja style vLLM templates use for the synthesized roles:
#   role == "query"                        (the bundled template)
#   selectattr("role", "eq", "query")      (vLLM's example template)
query_role_re='role.{0,40}(eq|==).{0,10}query'
if ! grep -Eq "${query_role_re}" "${TEMPLATE_DEST}"; then
  log "FATAL: ${TEMPLATE_DEST} does not read the 'query' message role; vLLM's score"
  log "       endpoint would score an empty (query, document) pair. Refusing to continue."
  exit 1
fi
for anchor in '<Query>:' '<Document>:'; do
  if ! grep -qF "${anchor}" "${TEMPLATE_DEST}"; then
    log "FATAL: ${TEMPLATE_DEST} does not emit ${anchor}; refusing to continue."
    exit 1
  fi
done

reown "${TEMPLATE_DIR}"
log_var TEMPLATE_DEST
log_cmd wc -c "${TEMPLATE_DEST}"
log "mod complete"
