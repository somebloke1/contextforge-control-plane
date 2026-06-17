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

PYTHON="${PYTHON:-${REPO_ROOT}/.venv/bin/python}"
CONTEXTFORGE_HOST_BASE_URL="${CONTEXTFORGE_HOST_BASE_URL:-http://127.0.0.1:4445}"
CONTEXTFORGE_CONTAINER_BASE_URL="${CONTEXTFORGE_CONTAINER_BASE_URL:-http://host.docker.internal:4445}"
CONTEXTFORGE_DEV_ENV_FILE="${CONTEXTFORGE_DEV_ENV_FILE:-${REPO_ROOT}/docker/contextforge-harness/env/contextforge.env}"
CONTEXTFORGE_DEV_SERVER_NAME="${CONTEXTFORGE_DEV_SERVER_NAME:-mentality_dev_docker_server}"
OPENCODE_DEV_MCP_NAME="${OPENCODE_DEV_MCP_NAME:-contextforge-mentality-dev}"

TOKEN_ID=""

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
trap revoke_probe_token EXIT

MCP_URL="${CONTEXTFORGE_CONTAINER_BASE_URL%/}/servers/${SERVER_ID}/mcp/"

{
  printf 'surface=OpenCode client Docker\n'
  printf 'contextforge_surface=ContextForge dev Docker\n'
  printf 'mcp_name=%s\n' "${OPENCODE_DEV_MCP_NAME}"
  printf 'mcp_url=%s\n' "${MCP_URL}"
  printf 'probe_token_id=%s\n' "${TOKEN_ID}"
} | tee evidence/opencode-contextforge-dev-smoke.txt

docker compose -f compose.yml run --rm --no-deps \
  -e HOME=/tmp/opencode-home \
  -e OPENCODE_CONFIG_DIR=/tmp/opencode-home/.config/opencode \
  -e CONTEXTFORGE_DEV_MCP_NAME="${OPENCODE_DEV_MCP_NAME}" \
  -e CONTEXTFORGE_DEV_MCP_URL="${MCP_URL}" \
  -e CONTEXTFORGE_DEV_BEARER_TOKEN="${ACCESS_TOKEN}" \
  opencode bash -lc '
    set -euo pipefail
    mkdir -p "${HOME}" "${OPENCODE_CONFIG_DIR}"
    opencode mcp add "${CONTEXTFORGE_DEV_MCP_NAME}" \
      --url "${CONTEXTFORGE_DEV_MCP_URL}" \
      --header "Authorization=Bearer ${CONTEXTFORGE_DEV_BEARER_TOKEN}"
    opencode mcp list
  ' | tee -a evidence/opencode-contextforge-dev-smoke.txt
