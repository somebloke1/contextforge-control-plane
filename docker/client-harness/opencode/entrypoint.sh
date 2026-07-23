#!/usr/bin/env bash
set -euo pipefail

: "${OPENCODE_CONFIG_DIR:=/home/agent/.config/opencode}"
: "${OPENCODE_DISABLE_PROJECT_CONFIG:=1}"
: "${CONTEXTFORGE_OPENCODE_CONFIG_SOURCE:=/config/opencode/opencode.json}"
: "${CONTEXTFORGE_OPENCODE_CONFIG_TARGET:=${OPENCODE_CONFIG_DIR}/opencode.json}"
: "${CONTEXTFORGE_OPENCODE_PLUGIN_SOURCE:=/config/opencode/plugins/contextforge-project-init.js}"
: "${CONTEXTFORGE_OPENCODE_PLUGIN_TARGET:=${OPENCODE_CONFIG_DIR}/plugins/contextforge-project-init.js}"
: "${CONTEXTFORGE_OPENCODE_RULES_SOURCE:=/config/opencode/AGENTS.md}"
: "${CONTEXTFORGE_OPENCODE_RULES_TARGET:=${OPENCODE_CONFIG_DIR}/AGENTS.md}"
: "${CONTEXTFORGE_OPENCODE_HOOK:=/repo/scripts/opencode_project_init_hook.py}"
: "${CONTEXTFORGE_OPENCODE_HOOK_PYTHON:=${CONTEXTFORGE_HELPER_PYTHON:-/opt/contextforge-helper-venv/bin/python}}"
: "${CONTEXTFORGE_OPENCODE_WRAPPER_PYTHON:=/opt/contextforge-helper-venv/bin/python}"
: "${CONTEXTFORGE_OPENCODE_WRAPPER_SCRIPT:=/repo/scripts/contextforge_mcp_wrapper.py}"
: "${CONTEXTFORGE_OPENCODE_WRAPPER_CONFIG_ENV:=/run/contextforge-client-scoped/contextforge.env}"
: "${CONTEXTFORGE_OPENCODE_WRAPPER_BASE_URL:=http://host.docker.internal:4445}"
: "${CONTEXTFORGE_OPENCODE_WRAPPER_TOKEN_CACHE:=/tmp/contextforge-wrapper-token.local.json}"
: "${CONTEXTFORGE_PROJECT_INIT_RUN_ROOT:=/home/agent/.local/state/contextforge-client-harness-runtime/project-init}"
: "${CONTEXTFORGE_HELPER_APPROVAL_SOURCE_PATH:=${CONTEXTFORGE_PROJECT_INIT_RUN_ROOT}/opencode-latest-user-message.json}"
: "${CONTEXTFORGE_ADDITIONAL_SAFE_PROJECT_ROOTS:=/workspace}"
: "${CONTEXTFORGE_OPENCODE_MODEL_SMOKE:=0}"
: "${XDG_RUNTIME_DIR:=/home/agent/.local/state/contextforge-client-harness-runtime}"

if [[ "${OPENCODE_DISABLE_PROJECT_CONFIG}" != "1" ]]; then
  printf 'OpenCode sandbox requires OPENCODE_DISABLE_PROJECT_CONFIG=1\n' >&2
  exit 2
fi
if [[ -n "${OPENCODE_CONFIG_CONTENT:-}" ]]; then
  printf 'OpenCode sandbox rejects OPENCODE_CONFIG_CONTENT\n' >&2
  exit 2
fi
unset OPENCODE_CONFIG_CONTENT
case "${CONTEXTFORGE_OPENCODE_MODEL_SMOKE}" in
  0) ;;
  1)
    if [[ "${OPENCODE_CONFIG_DIR}" != "/home/agent/.config/opencode-model-smoke" ]]; then
      printf 'OpenCode model smoke requires its isolated config directory\n' >&2
      exit 2
    fi
    if [[ "${CONTEXTFORGE_OPENCODE_CONFIG_TARGET}" != "${OPENCODE_CONFIG_DIR}/opencode.json" ||
          "${CONTEXTFORGE_OPENCODE_PLUGIN_TARGET}" != "${OPENCODE_CONFIG_DIR}/plugins/contextforge-project-init.js" ||
          "${CONTEXTFORGE_OPENCODE_RULES_TARGET}" != "${OPENCODE_CONFIG_DIR}/AGENTS.md" ]]; then
      printf 'OpenCode model smoke requires exact isolated config targets\n' >&2
      exit 2
    fi
    ;;
  *)
    printf 'CONTEXTFORGE_OPENCODE_MODEL_SMOKE must be 0 or 1\n' >&2
    exit 2
    ;;
esac
for key in OPENAI_API_KEY CODEX_API_KEY ANTHROPIC_API_KEY OPENROUTER_API_KEY GOOGLE_API_KEY GEMINI_API_KEY PERPLEXITY_API_KEY EXA_API_KEY CONTEXT7_API_KEY; do
  if [[ -n "${!key:-}" ]]; then
    printf 'OpenCode sandbox rejects direct-provider credential %s\n' "${key}" >&2
    exit 2
  fi
done

case "${CONTEXTFORGE_OPENCODE_CONFIG_TARGET}" in
  "${OPENCODE_CONFIG_DIR}/opencode.json") ;;
  *)
    printf 'Refusing unsafe CONTEXTFORGE_OPENCODE_CONFIG_TARGET outside %s\n' "${OPENCODE_CONFIG_DIR}" >&2
    exit 2
    ;;
esac

case "${CONTEXTFORGE_OPENCODE_PLUGIN_TARGET}" in
  "${OPENCODE_CONFIG_DIR}/plugins/"*) ;;
  *)
    printf 'Refusing unsafe CONTEXTFORGE_OPENCODE_PLUGIN_TARGET outside %s/plugins\n' "${OPENCODE_CONFIG_DIR}" >&2
    exit 2
    ;;
esac

mkdir -p "${OPENCODE_CONFIG_DIR}" "$(dirname "${CONTEXTFORGE_OPENCODE_PLUGIN_TARGET}")" "${XDG_RUNTIME_DIR}" "${CONTEXTFORGE_PROJECT_INIT_RUN_ROOT}"
if [[ "${CONTEXTFORGE_OPENCODE_MODEL_SMOKE}" == 0 ]]; then
  cp "${CONTEXTFORGE_OPENCODE_PLUGIN_SOURCE}" "${CONTEXTFORGE_OPENCODE_PLUGIN_TARGET}"
  if [ -f "${CONTEXTFORGE_OPENCODE_RULES_SOURCE}" ]; then
    cp "${CONTEXTFORGE_OPENCODE_RULES_SOURCE}" "${CONTEXTFORGE_OPENCODE_RULES_TARGET}"
  fi
elif [[ -e "${CONTEXTFORGE_OPENCODE_PLUGIN_TARGET}" ||
        -e "${CONTEXTFORGE_OPENCODE_RULES_TARGET}" ||
        -e "/home/agent/.config/opencode/plugins/contextforge-project-init.js" ||
        -e "/home/agent/.config/opencode/AGENTS.md" ]]; then
  printf 'OpenCode model smoke requires a fresh hook-free config directory\n' >&2
  exit 2
fi
cp "${CONTEXTFORGE_OPENCODE_CONFIG_SOURCE}" "${CONTEXTFORGE_OPENCODE_CONFIG_TARGET}"

/usr/local/bin/contextforge-opencode-render-config

export OPENCODE_CONFIG_DIR
export OPENCODE_DISABLE_PROJECT_CONFIG
export OPENCODE_CONFIG="${CONTEXTFORGE_OPENCODE_CONFIG_TARGET}"
export CONTEXTFORGE_OPENCODE_HOOK
export CONTEXTFORGE_OPENCODE_HOOK_PYTHON
export CONTEXTFORGE_OPENCODE_WRAPPER_PYTHON
export CONTEXTFORGE_OPENCODE_WRAPPER_SCRIPT
export CONTEXTFORGE_OPENCODE_WRAPPER_CONFIG_ENV
export CONTEXTFORGE_OPENCODE_WRAPPER_BASE_URL
export CONTEXTFORGE_OPENCODE_WRAPPER_TOKEN_CACHE
export CONTEXTFORGE_PROJECT_INIT_RUN_ROOT
export CONTEXTFORGE_HELPER_APPROVAL_SOURCE_PATH
export CONTEXTFORGE_ADDITIONAL_SAFE_PROJECT_ROOTS
export CONTEXTFORGE_OPENCODE_MODEL_SMOKE
export XDG_RUNTIME_DIR

exec "$@"
