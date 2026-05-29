#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"

if [[ -z "${GITHUB_PERSONAL_ACCESS_TOKEN:-}" ]]; then
  GITHUB_PERSONAL_ACCESS_TOKEN="$(gh auth token)"
  export GITHUB_PERSONAL_ACCESS_TOKEN
fi

exec .venv/bin/python -m mcpgateway.translate \
  --stdio "npx -y @modelcontextprotocol/server-github" \
  --expose-sse \
  --expose-streamable-http \
  --host 127.0.0.1 \
  --port 9106 \
  --logLevel info
