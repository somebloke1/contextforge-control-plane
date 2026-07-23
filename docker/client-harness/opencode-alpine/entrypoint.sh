#!/usr/bin/env bash
set -euo pipefail

: "${CONTEXTFORGE_OPENCODE_CONFIG_SOURCE:=${OPENCODE_CONFIG:-/config/opencode/opencode.json}}"
: "${CONTEXTFORGE_OPENCODE_CONFIG_TARGET:=/home/agent/.config/opencode/opencode.json}"
: "${CONTEXTFORGE_OPENCODE_RENDERER:=/usr/local/bin/contextforge-opencode-render-config}"
: "${OPENCODE_DISABLE_PROJECT_CONFIG:=1}"
: "${LITELLM_BASE_URL:=http://host.docker.internal:3333/v1}"
: "${CONTEXTFORGE_OPENCODE_DEFAULT_MODEL:=litellm/codex/gpt-5.6-luna}"
: "${CONTEXTFORGE_OPENCODE_SMALL_MODEL:=litellm/codex/gpt-5.6-luna}"
: "${CONTEXTFORGE_OPENCODE_DEFAULT_VARIANT:=medium}"

fail_model_policy() {
  printf '%s\n' "$1" >&2
  exit 2
}

[[ "${LITELLM_BASE_URL%/}" == "http://host.docker.internal:3333/v1" ]] || \
  fail_model_policy "OpenCode Alpine requires sandbox LiteLLM on host.docker.internal:3333"
[[ -n "${LITELLM_API_KEY:-}" ]] || fail_model_policy "OpenCode Alpine requires LITELLM_API_KEY"
[[ "${OPENCODE_DISABLE_PROJECT_CONFIG}" == "1" ]] || \
  fail_model_policy "OpenCode Alpine requires OPENCODE_DISABLE_PROJECT_CONFIG=1"
[[ "${CONTEXTFORGE_OPENCODE_DEFAULT_MODEL}" == "litellm/codex/gpt-5.6-luna" ]] || \
  fail_model_policy "OpenCode Alpine is fixed to Luna/medium through LiteLLM"
[[ "${CONTEXTFORGE_OPENCODE_SMALL_MODEL}" == "litellm/codex/gpt-5.6-luna" ]] || \
  fail_model_policy "OpenCode Alpine small model is fixed to Luna/medium through LiteLLM"
[[ "${CONTEXTFORGE_OPENCODE_DEFAULT_VARIANT}" == "medium" ]] || \
  fail_model_policy "OpenCode Alpine is fixed to Luna/medium reasoning"

for key in OPENAI_API_KEY CODEX_API_KEY ANTHROPIC_API_KEY OPENROUTER_API_KEY GOOGLE_API_KEY GEMINI_API_KEY PERPLEXITY_API_KEY EXA_API_KEY CONTEXT7_API_KEY; do
  [[ -z "${!key:-}" ]] || fail_model_policy "OpenCode Alpine rejects direct-provider credential ${key}"
done

export CONTEXTFORGE_OPENCODE_CONFIG_SOURCE
export CONTEXTFORGE_OPENCODE_CONFIG_TARGET
export OPENCODE_DISABLE_PROJECT_CONFIG
python3 "${CONTEXTFORGE_OPENCODE_RENDERER}"
export OPENCODE_CONFIG="${CONTEXTFORGE_OPENCODE_CONFIG_TARGET}"

exec /sbin/tini -- "$@"
