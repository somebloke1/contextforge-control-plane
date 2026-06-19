#!/usr/bin/env bash
set -euo pipefail

: "${OPENCODE_CONFIG:=/home/agent/.config/opencode/opencode.json}"
: "${CONTEXTFORGE_OPENCODE_PLUGIN_SOURCE:=/config/opencode/plugins/contextforge-project-init.js}"
: "${CONTEXTFORGE_OPENCODE_PLUGIN_TARGET:=/home/agent/.config/opencode/plugins/contextforge-project-init.js}"
: "${CONTEXTFORGE_OPENCODE_HOOK:=/repo/scripts/opencode_project_init_hook.py}"
: "${CONTEXTFORGE_OPENCODE_HOOK_PYTHON:=${CONTEXTFORGE_HELPER_PYTHON:-/opt/contextforge-helper-venv/bin/python}}"
: "${CONTEXTFORGE_PROJECT_INIT_RUN_ROOT:=/tmp/contextforge-client-harness-runtime/project-init}"
: "${CONTEXTFORGE_ADDITIONAL_SAFE_PROJECT_ROOTS:=/workspace}"

cd /workspace
export OPENCODE_CONFIG
export CONTEXTFORGE_OPENCODE_HOOK
export CONTEXTFORGE_OPENCODE_HOOK_PYTHON
export CONTEXTFORGE_PROJECT_INIT_RUN_ROOT
export CONTEXTFORGE_ADDITIONAL_SAFE_PROJECT_ROOTS

exec opencode "$@"
