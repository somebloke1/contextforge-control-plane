#!/usr/bin/env bash
set -euo pipefail

: "${OPENCODE_CONFIG:=/home/agent/.config/opencode/opencode.json}"
: "${CONTEXTFORGE_OPENCODE_PLUGIN_SOURCE:=/config/opencode/plugins/contextforge-project-init.js}"
: "${CONTEXTFORGE_OPENCODE_PLUGIN_TARGET:=/home/agent/.config/opencode/plugins/contextforge-project-init.js}"
: "${CONTEXTFORGE_OPENCODE_RULES_SOURCE:=/config/opencode/AGENTS.md}"
: "${CONTEXTFORGE_OPENCODE_RULES_TARGET:=/home/agent/.config/opencode/AGENTS.md}"
: "${CONTEXTFORGE_OPENCODE_HOOK:=/repo/scripts/opencode_project_init_hook.py}"
: "${CONTEXTFORGE_OPENCODE_HOOK_PYTHON:=${CONTEXTFORGE_HELPER_PYTHON:-/opt/contextforge-helper-venv/bin/python}}"
: "${CONTEXTFORGE_OPENCODE_WRAPPER_PYTHON:=/opt/contextforge-helper-venv/bin/python}"
: "${CONTEXTFORGE_OPENCODE_WRAPPER_SCRIPT:=/repo/scripts/contextforge_mcp_wrapper.py}"
: "${CONTEXTFORGE_OPENCODE_WRAPPER_CONFIG_ENV:=/config/contextforge/contextforge.env}"
: "${CONTEXTFORGE_OPENCODE_WRAPPER_BASE_URL:=http://host.docker.internal:4445}"
: "${CONTEXTFORGE_OPENCODE_WRAPPER_TOKEN_CACHE:=/tmp/contextforge-wrapper-token.local.json}"
: "${CONTEXTFORGE_PROJECT_INIT_RUN_ROOT:=/home/agent/.local/state/contextforge-client-harness-runtime/project-init}"
: "${CONTEXTFORGE_ADDITIONAL_SAFE_PROJECT_ROOTS:=/workspace}"
mkdir -p "$(dirname "${CONTEXTFORGE_OPENCODE_PLUGIN_TARGET}")" "$(dirname "${CONTEXTFORGE_OPENCODE_RULES_TARGET}")"
if [ -f "${CONTEXTFORGE_OPENCODE_RULES_SOURCE}" ]; then
  cp "${CONTEXTFORGE_OPENCODE_RULES_SOURCE}" "${CONTEXTFORGE_OPENCODE_RULES_TARGET}"
fi
cd /workspace
export OPENCODE_CONFIG
export CONTEXTFORGE_OPENCODE_HOOK
export CONTEXTFORGE_OPENCODE_HOOK_PYTHON
export CONTEXTFORGE_OPENCODE_WRAPPER_PYTHON
export CONTEXTFORGE_OPENCODE_WRAPPER_SCRIPT
export CONTEXTFORGE_OPENCODE_WRAPPER_CONFIG_ENV
export CONTEXTFORGE_OPENCODE_WRAPPER_BASE_URL
export CONTEXTFORGE_OPENCODE_WRAPPER_TOKEN_CACHE
export CONTEXTFORGE_PROJECT_INIT_RUN_ROOT
export CONTEXTFORGE_ADDITIONAL_SAFE_PROJECT_ROOTS

exec opencode "$@"
