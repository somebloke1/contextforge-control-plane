#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "${ROOT}/../.." && pwd)"
cd "${ROOT}"

mkdir -p evidence workspace/.project
if [[ ! -w evidence ]]; then
  docker compose -f compose.yml run --rm --no-deps -u root pi \
    chown -R "$(id -u):$(id -g)" /evidence
fi
if [[ ! -f env/semantic-model.env ]]; then
  scripts/make-semantic-model-env.sh
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
CONTEXTFORGE_DEV_SERVER_NAME="${CONTEXTFORGE_DEV_SERVER_NAME:-context7_local_server}"
EVIDENCE_FILE="evidence/pi-context7-dev-smoke.txt"
REDACTOR="${REPO_ROOT}/docker/client-harness/scripts/redact-contextforge-secrets.py"

TOKEN_ID=""
TOKEN_ENV_FILE=""

create_payload="$(
  PYTHONDONTWRITEBYTECODE=1 "${PYTHON}" - "${REPO_ROOT}" "${CONTEXTFORGE_HOST_BASE_URL}" "${CONTEXTFORGE_DEV_ENV_FILE}" "${CONTEXTFORGE_DEV_SERVER_NAME}" <<'PY'
import importlib.util
import json
import sys
from pathlib import Path

repo_root = Path(sys.argv[1])
base_url = sys.argv[2]
env_file = Path(sys.argv[3])
server_name = sys.argv[4]
script_dir = repo_root / "docker" / "contextforge-harness" / "scripts"
sys.path.insert(0, str(script_dir))

import register_context7_dev as registration  # noqa: E402

spec = importlib.util.spec_from_file_location("probe_context7_dev", script_dir / "probe-context7-dev.py")
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
  if [[ -n "${TOKEN_ENV_FILE}" && -f "${TOKEN_ENV_FILE}" ]]; then
    rm -f "${TOKEN_ENV_FILE}"
  fi
  if [[ -z "${TOKEN_ID}" ]]; then
    return
  fi
  PYTHONDONTWRITEBYTECODE=1 "${PYTHON}" - "${REPO_ROOT}" "${CONTEXTFORGE_HOST_BASE_URL}" "${CONTEXTFORGE_DEV_ENV_FILE}" "${TOKEN_ID}" <<'PY'
import importlib.util
import sys
from pathlib import Path

repo_root = Path(sys.argv[1])
base_url = sys.argv[2]
env_file = Path(sys.argv[3])
token_id = sys.argv[4]
script_dir = repo_root / "docker" / "contextforge-harness" / "scripts"
sys.path.insert(0, str(script_dir))

import register_context7_dev as registration  # noqa: E402

spec = importlib.util.spec_from_file_location("probe_context7_dev", script_dir / "probe-context7-dev.py")
probe = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(probe)

admin_token = registration.login(base_url, registration.read_env(env_file))
probe.revoke_probe_token(base_url, admin_token, token_id)
PY
  printf 'probe_token_revoked=%s\n' "${TOKEN_ID}" | tee -a "${EVIDENCE_FILE}"
}
trap revoke_probe_token EXIT

redact_token_stream() {
  CONTEXTFORGE_REDACT_VALUES="${ACCESS_TOKEN:-}" PYTHONDONTWRITEBYTECODE=1 "${PYTHON}" "${REDACTOR}"
}

TOKEN_ENV_FILE="$(mktemp "${TMPDIR:-/tmp}/contextforge-pi-context7-token-env.XXXXXX")"
chmod 600 "${TOKEN_ENV_FILE}"
{
  printf 'CONTEXTFORGE_BASE_URL=%s\n' "${CONTEXTFORGE_CONTAINER_BASE_URL}"
  printf 'CONTEXTFORGE_SERVER_ID=%s\n' "${SERVER_ID}"
  printf 'CONTEXTFORGE_BEARER_TOKEN=%s\n' "${ACCESS_TOKEN}"
  printf 'CONTEXTFORGE_CONFIG_ENV=/tmp/missing-contextforge.env\n'
  printf 'CONTEXTFORGE_TOKEN_CACHE=/tmp/contextforge-wrapper-token.local.json\n'
  printf 'CONTEXTFORGE_TOKEN_LOCK=/tmp/contextforge-wrapper-token.local.json.lock\n'
  printf 'CONTEXTFORGE_PI_SHIM_PORTAL_ROOT=/repo\n'
  printf 'CONTEXTFORGE_PI_SHIM_WORKSPACE_ROOT=/workspace\n'
  printf 'CONTEXTFORGE_PI_SHIM_PYTHON=/opt/contextforge-wrapper-venv/bin/python\n'
  printf 'CONTEXTFORGE_PI_SHIM_WRAPPER=/repo/scripts/contextforge_mcp_wrapper.py\n'
} > "${TOKEN_ENV_FILE}"

PYTHONDONTWRITEBYTECODE=1 "${PYTHON}" - "${ROOT}/workspace/.project/context_forge_state.json" "${SERVER_ID}" <<'PY'
import json
import sys
from pathlib import Path

state_path = Path(sys.argv[1])
server_id = sys.argv[2]
state = {
    "status": "initialized",
    "project": {
        "name": "pi-context7-dev",
        "root": "/workspace",
    },
    "services": {
        "context7:canonical": {
            "service_binding": "context7:canonical",
            "service_family": "context7",
            "backend_instance": "server-instances/context7",
            "x_contextforge_server_id": server_id,
            "x_descriptor_digest": "sha256:context7-dev-docker-smoke",
            "x_service_identity_id": "contextforge-service-1c0fb210b9aa8a8797287e69",
            "virtual_server": "context7_local_server",
            "target_clients": {
                "pi": {
                    "status": "enabled",
                    "virtual_server": "context7_local_server",
                    "pi_tool_prefix": "context7",
                    "validation_status": "pending",
                },
            },
            "verification_layers": {
                "tool_policy": {
                    "policy": {
                        "safe_operations": ["resolve-library-id", "query-docs"],
                    },
                },
            },
        },
    },
}
state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

{
  printf 'surface=Pi client Docker\n'
  printf 'contextforge_surface=ContextForge dev Docker\n'
  printf 'contextforge_base_url=%s\n' "${CONTEXTFORGE_CONTAINER_BASE_URL}"
  printf 'server_name=%s\n' "${CONTEXTFORGE_DEV_SERVER_NAME}"
  printf 'server_id=%s\n' "${SERVER_ID}"
  printf 'probe_token_id=%s\n' "${TOKEN_ID}"
  printf 'project_root=/workspace\n'
  printf 'pi_tool=cf_contextforge_pi_readback\n'
} | tee "${EVIDENCE_FILE}"

docker compose -f compose.yml --env-file env/semantic-model.env run --rm --no-deps \
  -v "${REPO_ROOT}:/repo:ro" \
  --env-from-file "${TOKEN_ENV_FILE}" \
  -e NODE_PATH=/usr/lib/node_modules/@earendil-works/pi-coding-agent/node_modules:/usr/lib/node_modules \
  pi bash -lc '
    set -euo pipefail
    pi \
      --extension /repo/pi-extensions/contextforge-global-shim/index.ts \
      --no-session \
      --no-builtin-tools \
      --no-context-files \
      --tools cf_contextforge_pi_readback \
      --provider "${CONTEXTFORGE_PI_DEFAULT_PROVIDER}" \
      --model "${CONTEXTFORGE_PI_DEFAULT_MODEL}" \
      -p "Use the cf_contextforge_pi_readback tool for projectRoot /workspace. Return the tool JSON result verbatim."
  ' | redact_token_stream | tee -a "${EVIDENCE_FILE}"

if ! grep -q 'context7:canonical' "${EVIDENCE_FILE}"; then
  printf 'pi_readback_status=missing_context7_service\n' | tee -a "${EVIDENCE_FILE}"
  exit 1
fi
if ! grep -q 'cf_context7_' "${EVIDENCE_FILE}"; then
  printf 'pi_readback_status=missing_context7_pi_tool\n' | tee -a "${EVIDENCE_FILE}"
  exit 1
fi

printf 'pi_readback_status=passed\n' | tee -a "${EVIDENCE_FILE}"
