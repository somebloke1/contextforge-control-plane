#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"

if [[ -f server-instances/context7/.env ]]; then
  set -a
  # shellcheck disable=SC1091
  source server-instances/context7/.env
  set +a
fi

exec .venv/bin/python -m mcpgateway.translate \
  --stdio 'npx -y @upstash/context7-mcp@latest' \
  --expose-sse \
  --expose-streamable-http \
  --host 127.0.0.1 \
  --port 9103 \
  --logLevel info
