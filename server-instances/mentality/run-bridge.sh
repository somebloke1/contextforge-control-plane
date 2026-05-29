#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."

exec .venv/bin/python -m mcpgateway.translate \
  --stdio ".venv/bin/python scripts/governance_mcp.py" \
  --expose-sse \
  --expose-streamable-http \
  --host 127.0.0.1 \
  --port 9100 \
  --logLevel info
