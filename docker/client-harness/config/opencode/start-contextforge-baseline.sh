#!/usr/bin/env bash
set -euo pipefail

: "${OPENCODE_CONFIG:=/config/opencode/opencode.json}"
: "${CONTEXTFORGE_OPENCODE_PLUGIN_SOURCE:=/config/opencode/plugins/contextforge-project-init.js}"
: "${CONTEXTFORGE_OPENCODE_PLUGIN_TARGET:=/workspace/.opencode/plugins/contextforge-project-init.js}"
: "${CONTEXTFORGE_OPENCODE_HOOK:=/repo/scripts/opencode_project_init_hook.py}"
: "${CONTEXTFORGE_OPENCODE_HOOK_PYTHON:=python3}"
: "${CONTEXTFORGE_ADDITIONAL_SAFE_PROJECT_ROOTS:=/workspace}"

mkdir -p "$(dirname "${CONTEXTFORGE_OPENCODE_PLUGIN_TARGET}")"
cp "${CONTEXTFORGE_OPENCODE_PLUGIN_SOURCE}" "${CONTEXTFORGE_OPENCODE_PLUGIN_TARGET}"

cd /workspace
export OPENCODE_CONFIG
export CONTEXTFORGE_OPENCODE_HOOK
export CONTEXTFORGE_OPENCODE_HOOK_PYTHON
export CONTEXTFORGE_ADDITIONAL_SAFE_PROJECT_ROOTS

exec opencode "$@"
