#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"

if [[ -f server-instances/time/.env ]]; then
  set -a
  # shellcheck disable=SC1091
  source server-instances/time/.env
  set +a
fi

local_timezone="${LOCAL_TIMEZONE:-UTC}"

exec .venv/bin/python -m mcpgateway.translate \
  --stdio "uvx mcp-server-time --local-timezone ${local_timezone}" \
  --expose-sse \
  --expose-streamable-http \
  --host 127.0.0.1 \
  --port 9109 \
  --logLevel info
