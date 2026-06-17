#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT}/env/contextforge.env"
EXAMPLE_FILE="${ROOT}/env/contextforge.env.example"

if [[ -f "${ENV_FILE}" ]]; then
  echo "Refusing to overwrite existing ${ENV_FILE}" >&2
  exit 1
fi

umask 077
admin_password="CfHarness-$(openssl rand -base64 30 | tr -dc 'A-Za-z0-9' | head -c 28)!9z"
basic_password="CfBasic-$(openssl rand -base64 24 | tr -dc 'A-Za-z0-9' | head -c 24)!9a"
jwt_secret="$(openssl rand -base64 48)"
auth_secret="$(openssl rand -base64 48)"
csrf_secret="$(openssl rand -base64 48)"

sed \
  -e "s#PLATFORM_ADMIN_PASSWORD=.*#PLATFORM_ADMIN_PASSWORD=${admin_password}#" \
  -e "s#BASIC_AUTH_PASSWORD=.*#BASIC_AUTH_PASSWORD=${basic_password}#" \
  -e "s#JWT_SECRET_KEY=.*#JWT_SECRET_KEY=${jwt_secret}#" \
  -e "s#AUTH_ENCRYPTION_SECRET=.*#AUTH_ENCRYPTION_SECRET=${auth_secret}#" \
  -e "s#CSRF_SECRET_KEY=.*#CSRF_SECRET_KEY=${csrf_secret}#" \
  "${EXAMPLE_FILE}" > "${ENV_FILE}"

chmod 600 "${ENV_FILE}"
echo "Wrote ${ENV_FILE}"
grep -E '^PLATFORM_ADMIN_EMAIL=' "${ENV_FILE}" | sed 's/^/Admin /'
echo "Admin password is stored only in the ignored env file."
