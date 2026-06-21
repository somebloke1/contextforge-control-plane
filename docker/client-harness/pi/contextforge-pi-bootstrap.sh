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

if [[ -f /config/pi/models.json ]]; then
  export PI_CODING_AGENT_DIR
  export OPENROUTER_STICKY_KEY="${OPENROUTER_STICKY_KEY:-contextforge-semantic-test}"
  export OPENROUTER_STICKY_EPOCH_SECONDS="${OPENROUTER_STICKY_EPOCH_SECONDS:-7200}"
  python3 - <<'PY'
import json
import os
import time
from pathlib import Path

def effective_sticky_key() -> str:
    base = os.environ["OPENROUTER_STICKY_KEY"]
    epoch_seconds = int(os.environ["OPENROUTER_STICKY_EPOCH_SECONDS"])
    if epoch_seconds <= 0:
        return base
    return f"{base}-e{int(time.time() // epoch_seconds)}"

source = Path("/config/pi/models.json")
target = Path(os.environ["PI_CODING_AGENT_DIR"]) / "models.json"
data = json.loads(source.read_text(encoding="utf-8"))
provider = data["providers"]["openrouter-gemini-flash-lite"]
provider["baseUrl"] = os.environ["OPENROUTER_BASE_URL"]
provider["apiKey"] = os.environ["OPENROUTER_API_KEY"]
provider["headers"]["x-session-id"] = effective_sticky_key()
routes = [item.strip() for item in os.environ.get("OPENROUTER_PROVIDER_ROUTES", "").split(",") if item.strip()]
if not routes and os.environ.get("OPENROUTER_PROVIDER_ROUTE"):
    routes = [os.environ["OPENROUTER_PROVIDER_ROUTE"]]
if routes:
    provider["compat"]["openRouterRouting"] = {
        "only": routes,
        "order": routes,
        "allow_fallbacks": False,
    }
else:
    provider["compat"].pop("openRouterRouting", None)
provider["models"][0]["id"] = os.environ["OPENROUTER_MODEL"]
if os.environ.get("CONTEXTFORGE_TEST_CONTEXT_WINDOW"):
    provider["models"][0]["contextWindow"] = int(os.environ["CONTEXTFORGE_TEST_CONTEXT_WINDOW"])
target.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
fi

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
