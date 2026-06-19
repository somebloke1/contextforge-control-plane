#!/usr/bin/env bash
set -euo pipefail

: "${OPENCODE_CONFIG_DIR:=/home/agent/.config/opencode}"
: "${CONTEXTFORGE_OPENCODE_CONFIG_SOURCE:=/config/opencode/opencode.json}"
: "${CONTEXTFORGE_OPENCODE_CONFIG_TARGET:=${OPENCODE_CONFIG_DIR}/opencode.json}"
: "${CONTEXTFORGE_OPENCODE_PLUGIN_SOURCE:=/config/opencode/plugins/contextforge-project-init.js}"
: "${CONTEXTFORGE_OPENCODE_PLUGIN_TARGET:=${OPENCODE_CONFIG_DIR}/plugins/contextforge-project-init.js}"
: "${CONTEXTFORGE_OPENCODE_HOOK:=/repo/scripts/opencode_project_init_hook.py}"
: "${CONTEXTFORGE_OPENCODE_HOOK_PYTHON:=${CONTEXTFORGE_HELPER_PYTHON:-/opt/contextforge-helper-venv/bin/python}}"
: "${CONTEXTFORGE_OPENCODE_WRAPPER_PYTHON:=/opt/contextforge-helper-venv/bin/python}"
: "${CONTEXTFORGE_OPENCODE_WRAPPER_SCRIPT:=/repo/scripts/contextforge_mcp_wrapper.py}"
: "${CONTEXTFORGE_OPENCODE_WRAPPER_CONFIG_ENV:=/config/contextforge/contextforge.env}"
: "${CONTEXTFORGE_OPENCODE_WRAPPER_BASE_URL:=http://host.docker.internal:4445}"
: "${CONTEXTFORGE_OPENCODE_WRAPPER_TOKEN_CACHE:=/tmp/contextforge-wrapper-token.local.json}"
: "${CONTEXTFORGE_PROJECT_INIT_RUN_ROOT:=/home/agent/.local/state/contextforge-client-harness-runtime/project-init}"
: "${CONTEXTFORGE_ADDITIONAL_SAFE_PROJECT_ROOTS:=/workspace}"
: "${XDG_RUNTIME_DIR:=/home/agent/.local/state/contextforge-client-harness-runtime}"

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
cp "${CONTEXTFORGE_OPENCODE_CONFIG_SOURCE}" "${CONTEXTFORGE_OPENCODE_CONFIG_TARGET}"
cp "${CONTEXTFORGE_OPENCODE_PLUGIN_SOURCE}" "${CONTEXTFORGE_OPENCODE_PLUGIN_TARGET}"

export OPENCODE_CONFIG_DIR
export OPENCODE_CONFIG="${OPENCODE_CONFIG:-${CONTEXTFORGE_OPENCODE_CONFIG_TARGET}}"
export CONTEXTFORGE_OPENCODE_HOOK
export CONTEXTFORGE_OPENCODE_HOOK_PYTHON
export CONTEXTFORGE_OPENCODE_WRAPPER_PYTHON
export CONTEXTFORGE_OPENCODE_WRAPPER_SCRIPT
export CONTEXTFORGE_OPENCODE_WRAPPER_CONFIG_ENV
export CONTEXTFORGE_OPENCODE_WRAPPER_BASE_URL
export CONTEXTFORGE_OPENCODE_WRAPPER_TOKEN_CACHE
export CONTEXTFORGE_PROJECT_INIT_RUN_ROOT
export CONTEXTFORGE_ADDITIONAL_SAFE_PROJECT_ROOTS
export XDG_RUNTIME_DIR

exec "$@"
