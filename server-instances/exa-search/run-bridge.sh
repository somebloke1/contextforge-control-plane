#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"

if [[ -f server-instances/exa-search/.env ]]; then
  set -a
  # shellcheck disable=SC1091
  source server-instances/exa-search/.env
  set +a
fi

exec .venv/bin/python -m mcpgateway.translate \
  --stdio ".venv/bin/python server-instances/exa-search/server.py" \
  --expose-sse \
  --expose-streamable-http \
  --host 127.0.0.1 \
  --port 9105 \
  --logLevel info
