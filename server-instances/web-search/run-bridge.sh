#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"

export WEB_ACCESS_ENABLE_GEMINI_WEB="${WEB_ACCESS_ENABLE_GEMINI_WEB:-false}"

if [[ -f server-instances/web-search/.env ]]; then
  set -a
  # shellcheck disable=SC1091
  source server-instances/web-search/.env
  set +a
fi

exec .venv/bin/python -m mcpgateway.translate \
  --stdio "node /home/dgk/workspace/web_search/dist/mcp-server.js" \
  --expose-sse \
  --expose-streamable-http \
  --host 127.0.0.1 \
  --port 9107 \
  --logLevel info
