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
CONTEXTFORGE_DEV_SERVER_NAME="${CONTEXTFORGE_DEV_SERVER_NAME:-mentality_dev_docker_server}"
EVIDENCE_FILE="evidence/pi-contextforge-dev-smoke.txt"
REDACTOR="${REPO_ROOT}/docker/client-harness/scripts/redact-contextforge-secrets.py"

TOKEN_ID=""
TOKEN_ENV_FILE=""

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
  printf 'probe_token_revoked=%s\n' "${TOKEN_ID}" | tee -a "${EVIDENCE_FILE}"
}
cleanup() {
  revoke_probe_token
  if [[ -n "${TOKEN_ENV_FILE}" ]]; then
    rm -f "${TOKEN_ENV_FILE}"
  fi
}
trap cleanup EXIT
TOKEN_ENV_FILE="$(mktemp)"
chmod 0600 "${TOKEN_ENV_FILE}"
{
  printf 'CONTEXTFORGE_BASE_URL=%s\n' "${CONTEXTFORGE_CONTAINER_BASE_URL}"
  printf 'CONTEXTFORGE_SERVER_ID=%s\n' "${SERVER_ID}"
  printf 'CONTEXTFORGE_BEARER_TOKEN=%s\n' "${ACCESS_TOKEN}"
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
        "name": "pi-contextforge-dev",
        "root": "/workspace",
    },
    "services": {
        "mentality:dev_docker": {
            "service_binding": "mentality:dev_docker",
            "service_family": "mentality",
            "x_contextforge_server_id": server_id,
            "virtual_server": "mentality_dev_docker_server",
            "target_clients": {
                "pi": {
                    "status": "enabled",
                    "virtual_server": "mentality_dev_docker_server",
                    "pi_tool_prefix": "mentality-dev-docker",
                    "validation_status": "pending",
                },
            },
            "verification_layers": {
                "tool_policy": {
                    "policy": {
                        "safe_operations": ["governance-list", "governance-read"],
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

docker compose -f compose.yml run --rm --no-deps \
  --env-file "${TOKEN_ENV_FILE}" \
  -v "${REPO_ROOT}:/repo:ro" \
  -e NODE_PATH=/usr/lib/node_modules/@earendil-works/pi-coding-agent/node_modules:/usr/lib/node_modules \
  -e CONTEXTFORGE_CONFIG_ENV=/tmp/missing-contextforge.env \
  -e CONTEXTFORGE_TOKEN_CACHE=/tmp/contextforge-wrapper-token.local.json \
  -e CONTEXTFORGE_TOKEN_LOCK=/tmp/contextforge-wrapper-token.local.json.lock \
  -e CONTEXTFORGE_PI_SHIM_PORTAL_ROOT=/repo \
  -e CONTEXTFORGE_PI_SHIM_WORKSPACE_ROOT=/workspace \
  -e CONTEXTFORGE_PI_SHIM_PYTHON=/opt/contextforge-wrapper-venv/bin/python \
  -e CONTEXTFORGE_PI_SHIM_WRAPPER=/repo/scripts/contextforge_mcp_wrapper.py \
  pi bash -lc '
    set -euo pipefail
    mkdir -p "${PI_CODING_AGENT_DIR}"
    cp /config/pi/AGENTS.md "${PI_CODING_AGENT_DIR}/AGENTS.md"
    python3 - <<PY
import json
import os

path = "/config/pi/models.json"
data = json.load(open(path, encoding="utf-8"))
provider = data["providers"]["openrouter-semantic-test"]
provider["baseUrl"] = os.environ["OPENROUTER_BASE_URL"]
provider["apiKey"] = os.environ["OPENROUTER_API_KEY"]
provider["compat"]["openRouterRouting"]["only"] = [os.environ["OPENROUTER_PROVIDER_ROUTE"]]
provider["compat"]["openRouterRouting"]["order"] = [os.environ["OPENROUTER_PROVIDER_ROUTE"]]
provider["models"][0]["id"] = os.environ["OPENROUTER_MODEL"]
out = os.path.join(os.environ["PI_CODING_AGENT_DIR"], "models.json")
json.dump(data, open(out, "w", encoding="utf-8"), indent=2)
PY
    pi \
      --extension /repo/pi-extensions/contextforge-global-shim/index.ts \
      --no-session \
      --no-builtin-tools \
      --no-context-files \
      --tools cf_contextforge_pi_readback \
      --provider "${CONTEXTFORGE_PI_DEFAULT_PROVIDER}" \
      --model "${CONTEXTFORGE_PI_DEFAULT_MODEL}" \
      -p "Use the cf_contextforge_pi_readback tool for projectRoot /workspace. Return the tool JSON result verbatim."
  ' | CONTEXTFORGE_REDACT_VALUES="${ACCESS_TOKEN:-}" PYTHONDONTWRITEBYTECODE=1 "${PYTHON}" "${REDACTOR}" | tee -a "${EVIDENCE_FILE}"

if ! grep -q 'mentality:dev_docker' "${EVIDENCE_FILE}"; then
  printf 'pi_readback_status=missing_mentality_service\n' | tee -a "${EVIDENCE_FILE}"
  exit 1
fi
if ! grep -q 'cf_mentality' "${EVIDENCE_FILE}"; then
  printf 'pi_readback_status=missing_mentality_pi_tool\n' | tee -a "${EVIDENCE_FILE}"
  exit 1
fi

printf 'pi_readback_status=passed\n' | tee -a "${EVIDENCE_FILE}"
