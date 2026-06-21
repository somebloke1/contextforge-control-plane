#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "${ROOT}/../.." && pwd)"
cd "${ROOT}"

mkdir -p evidence
if [[ ! -w evidence ]]; then
  docker compose -f compose.yml run --rm --no-deps -u root opencode \
    chown -R "$(id -u):$(id -g)" /evidence
fi
if [[ ! -f env/local-llama.env ]]; then
  scripts/make-local-llama-env.sh
fi

if [[ -z "${PYTHON:-}" ]]; then
  if [[ -x "${REPO_ROOT}/run/test-venvs/project-init-workflow/bin/python" ]]; then
    PYTHON="${REPO_ROOT}/run/test-venvs/project-init-workflow/bin/python"
  elif [[ -x "${REPO_ROOT}/.venv/bin/python" ]]; then
    PYTHON="${REPO_ROOT}/.venv/bin/python"
  else
    PYTHON="python3"
  fi
fi
CONTEXTFORGE_HOST_BASE_URL="${CONTEXTFORGE_HOST_BASE_URL:-http://127.0.0.1:4445}"
CONTEXTFORGE_CONTAINER_BASE_URL="${CONTEXTFORGE_CONTAINER_BASE_URL:-http://host.docker.internal:4445}"
CONTEXTFORGE_DEV_ENV_FILE="${CONTEXTFORGE_DEV_ENV_FILE:-${REPO_ROOT}/docker/contextforge-harness/env/contextforge.env}"
CONTEXTFORGE_DEV_SERVER_NAME="${CONTEXTFORGE_DEV_SERVER_NAME:-mentality_dev_docker_server}"
OPENCODE_DEV_MCP_NAME="${OPENCODE_DEV_MCP_NAME:-contextforge-mentality-dev}"
OPENCODE_SAFE_PROBE_ID="${OPENCODE_SAFE_PROBE_ID:-governance-list}"
OPENCODE_SAFE_PROBE_SERVICE="${OPENCODE_SAFE_PROBE_SERVICE:-mentality}"
OPENCODE_SAFE_PROBE_ALLOWED_TOOLS="${OPENCODE_SAFE_PROBE_ALLOWED_TOOLS:-mentality-governance-list,mentality-governance-read,governance_list,governance_read}"
OPENCODE_SAFE_PROBE_EXPECTED_TOOL="${OPENCODE_SAFE_PROBE_EXPECTED_TOOL:-mentality-governance-list}"
OPENCODE_REQUIRE_SAFE_CALL="${OPENCODE_REQUIRE_SAFE_CALL:-1}"
OPENCODE_SAFE_CALL_COMMAND="${OPENCODE_SAFE_CALL_COMMAND:-}"
REDACTOR="${REPO_ROOT}/docker/client-harness/scripts/redact-contextforge-secrets.py"

TOKEN_ID=""
TOKEN_ENV_FILE=""

if [[ -n "${OPENCODE_SAFE_CALL_COMMAND}" ]]; then
  SAFE_CALL_COMMAND_TOOL_ALLOWED=0
  IFS=',' read -r -a SAFE_PROBE_TOOLS <<<"${OPENCODE_SAFE_PROBE_ALLOWED_TOOLS}"
  for safe_probe_tool in "${SAFE_PROBE_TOOLS[@]}"; do
    if [[ "${OPENCODE_SAFE_CALL_COMMAND}" == *"${safe_probe_tool}"* ]]; then
      SAFE_CALL_COMMAND_TOOL_ALLOWED=1
      break
    fi
  done
  if [[ "${SAFE_CALL_COMMAND_TOOL_ALLOWED}" != "1" ]]; then
    printf 'safe_call_command_status=rejected_unknown_tool\n' >&2
    printf 'safe_call_blocker=OPENCODE_SAFE_CALL_COMMAND must reference one of OPENCODE_SAFE_PROBE_ALLOWED_TOOLS before a scoped token or Docker client run is started\n' >&2
    exit 21
  fi
fi

create_payload="$(
  PYTHONDONTWRITEBYTECODE=1 "${PYTHON}" - "${REPO_ROOT}" "${CONTEXTFORGE_HOST_BASE_URL}" "${CONTEXTFORGE_DEV_ENV_FILE}" "${CONTEXTFORGE_DEV_SERVER_NAME}" <<'PY'
import json
import sys
import importlib.util
from pathlib import Path

repo_root = Path(sys.argv[1])
base_url = sys.argv[2]
env_file = Path(sys.argv[3])
server_name = sys.argv[4]
script_dir = repo_root / "docker" / "contextforge-harness" / "scripts"
sys.path.insert(0, str(script_dir))

import register_mentality_dev as registration  # noqa: E402

spec = importlib.util.spec_from_file_location("probe_mentality_dev", script_dir / "probe-mentality-dev.py")
probe = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(probe)

admin_token = registration.login(base_url, registration.read_env(env_file))
server = probe.virtual_server(base_url, admin_token, server_name)
token_id, access_token = probe.create_probe_token(base_url, admin_token, server["id"])
print(json.dumps({"server_id": server["id"], "token_id": token_id, "access_token": access_token}))
PY
)"

SERVER_ID="$(jq -r '.server_id' <<<"${create_payload}")"
TOKEN_ID="$(jq -r '.token_id' <<<"${create_payload}")"
ACCESS_TOKEN="$(jq -r '.access_token' <<<"${create_payload}")"

revoke_probe_token() {
  if [[ -z "${TOKEN_ID}" ]]; then
    return
  fi
  PYTHONDONTWRITEBYTECODE=1 "${PYTHON}" - "${REPO_ROOT}" "${CONTEXTFORGE_HOST_BASE_URL}" "${CONTEXTFORGE_DEV_ENV_FILE}" "${TOKEN_ID}" <<'PY'
import sys
import importlib.util
from pathlib import Path

repo_root = Path(sys.argv[1])
base_url = sys.argv[2]
env_file = Path(sys.argv[3])
token_id = sys.argv[4]
script_dir = repo_root / "docker" / "contextforge-harness" / "scripts"
sys.path.insert(0, str(script_dir))

import register_mentality_dev as registration  # noqa: E402

spec = importlib.util.spec_from_file_location("probe_mentality_dev", script_dir / "probe-mentality-dev.py")
probe = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(probe)

admin_token = registration.login(base_url, registration.read_env(env_file))
probe.revoke_probe_token(base_url, admin_token, token_id)
PY
  printf 'probe_token_revoked=%s\n' "${TOKEN_ID}" | tee -a evidence/opencode-contextforge-dev-smoke.txt
}
cleanup() {
  revoke_probe_token
  if [[ -n "${TOKEN_ENV_FILE}" ]]; then
    rm -f "${TOKEN_ENV_FILE}"
  fi
}
trap cleanup EXIT

MCP_URL="${CONTEXTFORGE_CONTAINER_BASE_URL%/}/servers/${SERVER_ID}/mcp/"
TOKEN_ENV_FILE="$(mktemp)"
chmod 0600 "${TOKEN_ENV_FILE}"
{
  printf 'CONTEXTFORGE_DEV_MCP_NAME=%s\n' "${OPENCODE_DEV_MCP_NAME}"
  printf 'CONTEXTFORGE_DEV_MCP_URL=%s\n' "${MCP_URL}"
  printf 'CONTEXTFORGE_DEV_BEARER_TOKEN=%s\n' "${ACCESS_TOKEN}"
} > "${TOKEN_ENV_FILE}"

redact_token_stream() {
  CONTEXTFORGE_REDACT_VALUES="${ACCESS_TOKEN:-}" PYTHONDONTWRITEBYTECODE=1 "${PYTHON}" "${REDACTOR}"
}

{
  printf 'surface=OpenCode client Docker\n'
  printf 'contextforge_surface=ContextForge dev Docker\n'
  printf 'mcp_name=%s\n' "${OPENCODE_DEV_MCP_NAME}"
  printf 'mcp_url=%s\n' "${MCP_URL}"
  printf 'probe_token_id=%s\n' "${TOKEN_ID}"
  printf 'safe_probe_service=%s\n' "${OPENCODE_SAFE_PROBE_SERVICE}"
  printf 'safe_probe_id=%s\n' "${OPENCODE_SAFE_PROBE_ID}"
  printf 'safe_probe_expected_tool=%s\n' "${OPENCODE_SAFE_PROBE_EXPECTED_TOOL}"
  printf 'safe_probe_allowed_tools=%s\n' "${OPENCODE_SAFE_PROBE_ALLOWED_TOOLS}"
  printf 'safe_call_required=%s\n' "${OPENCODE_REQUIRE_SAFE_CALL}"
} | tee evidence/opencode-contextforge-dev-smoke.txt

docker compose -f compose.yml run --rm --no-deps \
  --env-file "${TOKEN_ENV_FILE}" \
  -e HOME=/tmp/opencode-home \
  -e OPENCODE_CONFIG_DIR=/tmp/opencode-home/.config/opencode \
  -e OPENCODE_CONFIG=/tmp/opencode-home/.config/opencode/opencode.json \
  -e CONTEXTFORGE_OPENCODE_CONFIG_TARGET=/tmp/opencode-home/.config/opencode/opencode.json \
  -e CONTEXTFORGE_OPENCODE_PLUGIN_TARGET=/tmp/opencode-home/.config/opencode/plugins/contextforge-project-init.js \
  -e CONTEXTFORGE_OPENCODE_RULES_TARGET=/tmp/opencode-home/.config/opencode/AGENTS.md \
  -e XDG_RUNTIME_DIR=/tmp/opencode-home/.local/state/contextforge-client-harness-runtime \
  -e CONTEXTFORGE_PROJECT_INIT_RUN_ROOT=/tmp/opencode-home/.local/state/contextforge-client-harness-runtime/project-init \
  -e CONTEXTFORGE_HELPER_APPROVAL_SOURCE_PATH=/tmp/opencode-home/.local/state/contextforge-client-harness-runtime/project-init/opencode-latest-user-message.json \
  -e OPENCODE_SAFE_PROBE_ID="${OPENCODE_SAFE_PROBE_ID}" \
  -e OPENCODE_SAFE_PROBE_SERVICE="${OPENCODE_SAFE_PROBE_SERVICE}" \
  -e OPENCODE_SAFE_PROBE_ALLOWED_TOOLS="${OPENCODE_SAFE_PROBE_ALLOWED_TOOLS}" \
  -e OPENCODE_SAFE_PROBE_EXPECTED_TOOL="${OPENCODE_SAFE_PROBE_EXPECTED_TOOL}" \
  -e OPENCODE_REQUIRE_SAFE_CALL="${OPENCODE_REQUIRE_SAFE_CALL}" \
  -e OPENCODE_SAFE_CALL_COMMAND="${OPENCODE_SAFE_CALL_COMMAND}" \
  opencode bash -lc '
    set -euo pipefail
    mkdir -p "${HOME}" "${OPENCODE_CONFIG_DIR}"
    opencode mcp add "${CONTEXTFORGE_DEV_MCP_NAME}" \
      --url "${CONTEXTFORGE_DEV_MCP_URL}" \
      --header "Authorization=Bearer ${CONTEXTFORGE_DEV_BEARER_TOKEN}"
    printf "opencode_mcp_list_status=started\n"
    opencode mcp list
    printf "opencode_mcp_list_status=passed\n"
    printf "safe_call_target_client_visible=false\n"
    printf "safe_call_probe_service=%s\n" "${OPENCODE_SAFE_PROBE_SERVICE}"
    printf "safe_call_probe_id=%s\n" "${OPENCODE_SAFE_PROBE_ID}"
    printf "safe_call_allowed_tools=%s\n" "${OPENCODE_SAFE_PROBE_ALLOWED_TOOLS}"
    printf "safe_call_expected_tool=%s\n" "${OPENCODE_SAFE_PROBE_EXPECTED_TOOL}"

    if [[ -z "${OPENCODE_SAFE_CALL_COMMAND}" ]]; then
      printf "safe_call_status=not_executed\n"
      printf "safe_call_blocker=OPENCODE_SAFE_CALL_COMMAND not set; OpenCode CLI MCP tool-call mechanics require a reviewed command before target_client_ready evidence can be claimed\n"
      if [[ "${OPENCODE_REQUIRE_SAFE_CALL}" == "0" ]]; then
        printf "smoke_result=list_only_without_safe_call\n"
        exit 0
      fi
      printf "smoke_result=failed_missing_required_safe_call\n"
      exit 20
    fi

    printf "safe_call_command_status=provided_redacted\n"
    printf "safe_call_status=started\n"
    bash -lc "${OPENCODE_SAFE_CALL_COMMAND}"
    printf "safe_call_status=passed\n"
    printf "safe_call_target_client_visible=true\n"
    printf "smoke_result=list_plus_safe_call\n"
  ' | redact_token_stream | tee -a evidence/opencode-contextforge-dev-smoke.txt
