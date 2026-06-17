#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_URL="${CONTEXTFORGE_BASE_URL:-http://127.0.0.1:4445}"
ENV_FILE="${ROOT}/env/contextforge.env"
EVIDENCE_DIR="${ROOT}/evidence"

mkdir -p "${EVIDENCE_DIR}"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing ${ENV_FILE}; run scripts/init-env.sh first." >&2
  exit 1
fi

admin_email="$(grep -E '^PLATFORM_ADMIN_EMAIL=' "${ENV_FILE}" | cut -d= -f2-)"
admin_password="$(grep -E '^PLATFORM_ADMIN_PASSWORD=' "${ENV_FILE}" | cut -d= -f2-)"

curl -fsS "${BASE_URL}/health" | tee "${EVIDENCE_DIR}/health.json" >/dev/null
curl -fsS "${BASE_URL}/ready" | tee "${EVIDENCE_DIR}/ready.json" >/dev/null

login_json="$(
  curl -fsS \
    -H 'Content-Type: application/json' \
    -d "{\"email\":\"${admin_email}\",\"password\":\"${admin_password}\"}" \
    "${BASE_URL}/auth/login"
)"

token="$(
  printf '%s' "${login_json}" |
    python3 -c 'import json,sys; data=json.load(sys.stdin); print(data.get("access_token") or data.get("token") or data.get("jwt") or "")'
)"

if [[ -z "${token}" ]]; then
  echo "Login response did not include an access token." >&2
  exit 1
fi

printf '%s' "${login_json}" |
  python3 -c 'import json,sys; data=json.load(sys.stdin); print(json.dumps({k: ("<redacted>" if "token" in k else v) for k,v in data.items()}, indent=2, sort_keys=True))' \
  > "${EVIDENCE_DIR}/admin-login.redacted.json"

curl -fsS \
  -H "Authorization: Bearer ${token}" \
  "${BASE_URL}/version" |
  tee "${EVIDENCE_DIR}/version.json" >/dev/null

curl -fsS \
  -H "Authorization: Bearer ${token}" \
  "${BASE_URL}/tokens" |
  tee "${EVIDENCE_DIR}/tokens-list.json" >/dev/null

curl -fsS \
  -H "Authorization: Bearer ${token}" \
  "${BASE_URL}/auth/email/me" |
  tee "${EVIDENCE_DIR}/admin-user.json" >/dev/null

curl -fsS \
  -H "Authorization: Bearer ${token}" \
  "${BASE_URL}/gateways" |
  tee "${EVIDENCE_DIR}/gateways.json" >/dev/null

curl -fsS \
  -H "Authorization: Bearer ${token}" \
  "${BASE_URL}/servers" |
  tee "${EVIDENCE_DIR}/servers.json" >/dev/null

curl -fsS \
  "${BASE_URL}/admin/login" |
  python3 -c 'import sys; body=sys.stdin.read(); print("admin_html_bytes", len(body)); sys.exit(0 if ("ContextForge" in body or "Admin" in body) else 1)' \
  | tee "${EVIDENCE_DIR}/admin-html-check.txt" >/dev/null

echo "ContextForge container auth verification passed for ${BASE_URL}"
