#!/usr/bin/env bash

: "${PI_CODING_AGENT_DIR:=/home/agent/.pi/agent}"
: "${CONTEXTFORGE_PI_SHIM_EXTENSION:=/repo/pi-extensions/contextforge-global-shim/index.ts}"
: "${CONTEXTFORGE_PI_SHIM_INSTALL_DIR:=${PI_CODING_AGENT_DIR}/extensions/contextforge-global-shim}"
: "${CONTEXTFORGE_PI_SHIM_PORTAL_ROOT:=/repo}"
: "${CONTEXTFORGE_PI_SHIM_WORKSPACE_ROOT:=/workspace}"
: "${CONTEXTFORGE_PI_SHIM_PYTHON:=/opt/contextforge-wrapper-venv/bin/python}"
: "${CONTEXTFORGE_PI_SHIM_WRAPPER:=/repo/scripts/contextforge_mcp_wrapper.py}"
: "${CONTEXTFORGE_CONFIG_ENV:=/run/contextforge-client-scoped/contextforge.env}"
: "${CONTEXTFORGE_BASE_URL:=http://host.docker.internal:4445}"
: "${CONTEXTFORGE_TOKEN_CACHE:=/tmp/contextforge-wrapper-token.local.json}"
: "${CONTEXTFORGE_TOKEN_LOCK:=${CONTEXTFORGE_TOKEN_CACHE}.lock}"
: "${CONTEXTFORGE_PROJECT_INIT_RUN_ROOT:=/home/agent/.local/state/contextforge-client-harness-runtime/project-init}"
: "${CONTEXTFORGE_HELPER_APPROVAL_SOURCE_PATH:=${CONTEXTFORGE_PROJECT_INIT_RUN_ROOT}/pi-latest-user-message.json}"
: "${CONTEXTFORGE_ADDITIONAL_SAFE_PROJECT_ROOTS:=/workspace}"

mkdir -p "${PI_CODING_AGENT_DIR}" "${CONTEXTFORGE_PROJECT_INIT_RUN_ROOT}"

if [[ -f /config/pi/AGENTS.md ]]; then
  cp /config/pi/AGENTS.md "${PI_CODING_AGENT_DIR}/AGENTS.md"
fi

if [[ -f "${CONTEXTFORGE_PI_SHIM_EXTENSION}" ]]; then
  case "${CONTEXTFORGE_PI_SHIM_INSTALL_DIR}" in
    "${PI_CODING_AGENT_DIR}/extensions/"*) ;;
    *)
      printf 'Refusing unsafe CONTEXTFORGE_PI_SHIM_INSTALL_DIR outside %s/extensions\n' "${PI_CODING_AGENT_DIR}" >&2
      return 2 2>/dev/null || exit 2
      ;;
  esac
  mkdir -p "$(dirname "${CONTEXTFORGE_PI_SHIM_INSTALL_DIR}")"
  rm -rf "${CONTEXTFORGE_PI_SHIM_INSTALL_DIR}"
  cp -R "$(dirname "${CONTEXTFORGE_PI_SHIM_EXTENSION}")" "${CONTEXTFORGE_PI_SHIM_INSTALL_DIR}"
  printf '{"portalRoot":"%s"}\n' "${CONTEXTFORGE_PI_SHIM_PORTAL_ROOT}" > "${CONTEXTFORGE_PI_SHIM_INSTALL_DIR}/contextforge-root.json"
fi

if [[ ! -f /config/pi/models.json || ! -f /config/pi/settings.json ]]; then
  printf 'Pi sandbox requires /config/pi/models.json and /config/pi/settings.json\n' >&2
  return 2 2>/dev/null || exit 2
fi

export PI_CODING_AGENT_DIR
python3 /usr/local/lib/contextforge-pi-render-config.py

export PI_CODING_AGENT_DIR
export CONTEXTFORGE_PI_SHIM_PORTAL_ROOT
export CONTEXTFORGE_PI_SHIM_WORKSPACE_ROOT
export CONTEXTFORGE_PI_SHIM_PYTHON
export CONTEXTFORGE_PI_SHIM_WRAPPER
export CONTEXTFORGE_CONFIG_ENV
export CONTEXTFORGE_BASE_URL
export CONTEXTFORGE_TOKEN_CACHE
export CONTEXTFORGE_TOKEN_LOCK
export CONTEXTFORGE_PROJECT_INIT_RUN_ROOT
export CONTEXTFORGE_HELPER_APPROVAL_SOURCE_PATH
export CONTEXTFORGE_ADDITIONAL_SAFE_PROJECT_ROOTS
