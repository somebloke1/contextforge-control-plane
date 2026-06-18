#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "${ROOT}/../.." && pwd)"
cd "${ROOT}"

SESSION_NAME="${CONTEXTFORGE_PI_INTERACTIVE_CONTAINER:-contextforge-pi-interactive}"
PYTHON="${PYTHON:-${REPO_ROOT}/.venv/bin/python}"
CONTEXTFORGE_HOST_BASE_URL="${CONTEXTFORGE_HOST_BASE_URL:-http://127.0.0.1:4445}"
CONTEXTFORGE_CONTAINER_BASE_URL="${CONTEXTFORGE_CONTAINER_BASE_URL:-http://host.docker.internal:4445}"
CONTEXTFORGE_DEV_ENV_FILE="${CONTEXTFORGE_DEV_ENV_FILE:-${REPO_ROOT}/docker/contextforge-harness/env/contextforge.env}"
CONTEXTFORGE_DEV_SERVER_NAME="${CONTEXTFORGE_DEV_SERVER_NAME:-mentality_dev_docker_server}"
EVIDENCE_FILE="${CONTEXTFORGE_PI_INTERACTIVE_EVIDENCE_FILE:-evidence/pi-contextforge-interactive.txt}"

usage() {
  cat <<'USAGE'
Usage:
  scripts/start-pi-contextforge-interactive.sh [pi args...]
  scripts/start-pi-contextforge-interactive.sh --attach

Start an interactive Pi TUI session inside the client harness with the
ContextForge Pi extension shim loaded from the repository and a ContextForge
dev Docker project-state fixture available at /workspace. Do not pass -p or
--no-session when validating multi-turn initialization behavior.

Set CONTEXTFORGE_PI_INTERACTIVE_CONTAINER to override the Docker container name.
USAGE
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

if [[ "${1:-}" == "--attach" ]]; then
  exec docker attach "${SESSION_NAME}"
fi

if [[ ! -f env/local-llama.env ]]; then
  scripts/make-local-llama-env.sh
fi
mkdir -p evidence workspace/.project
if [[ ! -w evidence || ! -w workspace ]]; then
  docker compose -f compose.yml run --rm --no-deps -u root pi \
    chown -R "$(id -u):$(id -g)" /evidence /workspace
fi

if docker ps --format '{{.Names}}' | grep -Fxq "${SESSION_NAME}"; then
  printf 'Pi interactive container is already running: %s\n' "${SESSION_NAME}" >&2
  printf 'Attach with:\n  docker attach %s\n' "${SESSION_NAME}" >&2
  exit 2
fi

if docker ps -a --format '{{.Names}}' | grep -Fxq "${SESSION_NAME}"; then
  docker rm "${SESSION_NAME}" >/dev/null
fi

TOKEN_ID=""

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
import importlib.util
import sys
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
trap revoke_probe_token EXIT

PYTHONDONTWRITEBYTECODE=1 "${PYTHON}" - "${ROOT}/workspace/.project/context_forge_state.json" "${SERVER_ID}" <<'PY'
import json
import sys
from pathlib import Path

state_path = Path(sys.argv[1])
server_id = sys.argv[2]
state = {
    "project": {
        "name": "pi-contextforge-interactive",
        "root": "/workspace",
    },
    "services": {
        "mentality:dev_docker": {
            "service_binding": "mentality:dev_docker",
            "service_family": "mentality",
            "target_clients": {
                "pi": {
                    "pi_tool_prefix": "mentality-dev-docker",
                    "shim": "contextforge-global-shim",
                    "status": "enabled",
                    "validation_status": "pending",
                    "virtual_server": "mentality_dev_docker_server",
                },
            },
            "verification_layers": {
                "tool_policy": {
                    "policy": {
                        "safe_operations": ["governance-list", "governance-read"],
                    },
                },
            },
            "virtual_server": "mentality_dev_docker_server",
            "x_contextforge_server_id": server_id,
        },
    },
    "status": "initialized",
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
  printf 'launcher=start-pi-contextforge-interactive.sh\n'
} | tee "${EVIDENCE_FILE}"

cat <<EOF
Starting interactive Pi TUI session for ContextForge validation.

Manual validation cues:
- Do not pass -p, --no-session, --no-tools, or --no-context-files.
- In the Pi TUI, ask about ContextForge project-init guidance.
- Ask Pi to use cf_contextforge_pi_readback for /workspace.
- Confirm the readback imports mentality:dev_docker tools such as
  cf_mentality-dev-docker__governance_list.
- Ask Pi to use a safe imported governance read/list tool.
- Continue for multiple turns to verify context persists across the session.
- From another terminal, reconnect while it is running with:
  docker attach ${SESSION_NAME}
EOF

docker compose -f compose.yml run --rm --no-deps \
  --name "${SESSION_NAME}" \
  --interactive \
  -v "${REPO_ROOT}:/repo:ro" \
  -e NODE_PATH=/usr/lib/node_modules/@earendil-works/pi-coding-agent/node_modules:/usr/lib/node_modules \
  -e CONTEXTFORGE_BASE_URL="${CONTEXTFORGE_CONTAINER_BASE_URL}" \
  -e CONTEXTFORGE_SERVER_ID="${SERVER_ID}" \
  -e CONTEXTFORGE_BEARER_TOKEN="${ACCESS_TOKEN}" \
  -e CONTEXTFORGE_CONFIG_ENV=/tmp/missing-contextforge.env \
  -e CONTEXTFORGE_TOKEN_CACHE=/tmp/contextforge-wrapper-token.local.json \
  -e CONTEXTFORGE_TOKEN_LOCK=/tmp/contextforge-wrapper-token.local.json.lock \
  -e CONTEXTFORGE_PI_SHIM_PORTAL_ROOT=/repo \
  -e CONTEXTFORGE_PI_SHIM_WORKSPACE_ROOT=/workspace \
  -e CONTEXTFORGE_PI_SHIM_PYTHON=/opt/contextforge-wrapper-venv/bin/python \
  -e CONTEXTFORGE_PI_SHIM_WRAPPER=/repo/scripts/contextforge_mcp_wrapper.py \
  pi /config/pi/start-contextforge-baseline.sh "$@"
