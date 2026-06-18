#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_URL="${CONTEXTFORGE_BASE_URL:-http://127.0.0.1:4445}"
ENV_FILE="${CONTEXTFORGE_DEV_ENV_FILE:-${ROOT}/env/contextforge.env}"
SYNC_FROM="${CONTEXTFORGE_DEV_ENV_SYNC_FROM:-}"

if [[ ! -f "${ENV_FILE}" ]]; then
  if [[ -n "${SYNC_FROM}" && -f "${SYNC_FROM}" ]]; then
    install -m 600 "${SYNC_FROM}" "${ENV_FILE}"
    echo "synced_env_file=${ENV_FILE}"
  else
    echo "missing_env_file=${ENV_FILE}" >&2
    echo "run ${ROOT}/scripts/init-env.sh or set CONTEXTFORGE_DEV_ENV_SYNC_FROM to a matching ignored env file" >&2
    exit 1
  fi
fi

login_status() {
  python3 - "$BASE_URL" "$ENV_FILE" <<'PY'
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

base_url = sys.argv[1].rstrip("/")
env_file = Path(sys.argv[2])
values = {}
for raw_line in env_file.read_text(encoding="utf-8").splitlines():
    line = raw_line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    values[key] = value.strip().strip("\"'")
email = values.get("PLATFORM_ADMIN_EMAIL")
password = values.get("PLATFORM_ADMIN_PASSWORD")
if not email or not password:
    print("missing_admin_credentials", file=sys.stderr)
    raise SystemExit(2)
body = json.dumps({"email": email, "password": password}).encode()
request = urllib.request.Request(
    f"{base_url}/auth/login",
    data=body,
    headers={"Content-Type": "application/json", "Accept": "application/json"},
    method="POST",
)
try:
    with urllib.request.urlopen(request, timeout=15) as response:
        response.read()
except urllib.error.HTTPError as exc:
    print(f"http_{exc.code}", file=sys.stderr)
    raise SystemExit(10 if exc.code == 401 else 11) from exc
except Exception as exc:
    print(exc.__class__.__name__, file=sys.stderr)
    raise SystemExit(12) from exc
print("auth_ok")
PY
}

if login_status; then
  echo "env_auth_status=passed"
  exit 0
fi

if [[ -n "${SYNC_FROM}" && -f "${SYNC_FROM}" ]]; then
  install -m 600 "${SYNC_FROM}" "${ENV_FILE}"
  if login_status; then
    echo "env_auth_status=passed_after_sync"
    exit 0
  fi
fi

echo "env_auth_status=failed" >&2
echo "The ignored env file does not authenticate against the current dev gateway volume." >&2
echo "Use a matching env file or reset only the isolated dev Docker volume before continuing." >&2
exit 1
