#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "${ROOT}/../.." && pwd)"
cd "${ROOT}"

mkdir -p evidence workspace/.codex

if [[ -z "${PYTHON:-}" ]]; then
  if [[ -x "${REPO_ROOT}/run/test-venvs/project-init-workflow/bin/python" ]]; then
    PYTHON="${REPO_ROOT}/run/test-venvs/project-init-workflow/bin/python"
  elif [[ -x "${REPO_ROOT}/.venv/bin/python" ]]; then
    PYTHON="${REPO_ROOT}/.venv/bin/python"
  else
    PYTHON="python3"
  fi
fi

CONTEXTFORGE_CONTAINER_BASE_URL="${CONTEXTFORGE_CONTAINER_BASE_URL:-http://host.docker.internal:4445}"
CONTEXTFORGE_DEV_SERVER_NAME="${CONTEXTFORGE_DEV_SERVER_NAME:-mentality_dev_docker_server}"
CODEX_DEV_MCP_NAME="${CODEX_DEV_MCP_NAME:-contextforge-mentality-dev}"
EVIDENCE_FILE="evidence/codex-contextforge-dev-smoke.txt"
REDACTOR="${REPO_ROOT}/docker/client-harness/scripts/redact-contextforge-secrets.py"

cat > workspace/.codex/config.toml <<EOF
cli_auth_credentials_store = "file"
model = "gpt-5.4-mini"

[projects."/workspace"]
trust_level = "trusted"

[mcp_servers.${CODEX_DEV_MCP_NAME}]
command = "/opt/contextforge-helper-venv/bin/python"
args = ["/repo/scripts/contextforge_mcp_wrapper.py", "${CONTEXTFORGE_DEV_SERVER_NAME}"]
cwd = "/repo"
env = { CONTEXTFORGE_CONFIG_ENV = "/run/contextforge-client-scoped/contextforge.env", CONTEXTFORGE_BASE_URL = "${CONTEXTFORGE_CONTAINER_BASE_URL}", CONTEXTFORGE_TOKEN_CACHE = "/tmp/contextforge-wrapper-token.local.json", CONTEXTFORGE_TOKEN_LOCK = "/tmp/contextforge-wrapper-token.local.json.lock", CONTEXTFORGE_WRAPPER_IDLE_TIMEOUT_SECONDS = "300", MCP_WRAPPER_LOG_LEVEL = "INFO" }
startup_timeout_ms = 60000
tool_timeout_ms = 120000
EOF

{
  printf 'surface=Codex client Docker\n'
  printf 'contextforge_surface=ContextForge dev Docker\n'
  printf 'contextforge_base_url=%s\n' "${CONTEXTFORGE_CONTAINER_BASE_URL}"
  printf 'mcp_name=%s\n' "${CODEX_DEV_MCP_NAME}"
  printf 'server_name=%s\n' "${CONTEXTFORGE_DEV_SERVER_NAME}"
  printf 'project_config=/workspace/.codex/config.toml\n'
  printf 'oauth_required=true\n'
  printf 'api_key_auth_allowed=false\n'
  printf 'model_required=gpt-5.4-mini\n'
  printf 'safe_call_status=not_claimed\n'
} | tee "${EVIDENCE_FILE}"

scripts/run-codex-authenticated.sh bash -lc '
  set -euo pipefail
  cd /workspace
  printf "codex_version="
  codex --version
  codex login status
  grep -qx "cli_auth_credentials_store = \"file\"" "${HOME}/.codex/config.toml"
  grep -qx "model = \"gpt-5.4-mini\"" "${HOME}/.codex/config.toml"
  grep -qx "model = \"gpt-5.4-mini\"" /workspace/.codex/config.toml
  codex mcp list --json > /tmp/codex-mcp-list.json
  python3 - <<PY
import json
from pathlib import Path

data = json.loads(Path("/tmp/codex-mcp-list.json").read_text(encoding="utf-8"))
print("codex_mcp_list_json_type=" + type(data).__name__)
print("codex_mcp_list_json=" + json.dumps(data, sort_keys=True))
PY
  printf "codex_mcp_list_status=passed\n"
' | PYTHONDONTWRITEBYTECODE=1 "${PYTHON}" "${REDACTOR}" | tee -a "${EVIDENCE_FILE}"

printf 'codex_smoke_result=config_list_readback_without_safe_call\n' | tee -a "${EVIDENCE_FILE}"
