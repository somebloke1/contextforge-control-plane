#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"

exec .venv/bin/python -m mcpgateway.translate \
  --stdio 'uvx mcp-ssh-tmux' \
  --expose-sse \
  --expose-streamable-http \
  --host 127.0.0.1 \
  --port 9102 \
  --logLevel info
