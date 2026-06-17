#!/usr/bin/env bash
set -euo pipefail
export SERENA_HOME="/home/dgk/workspace/cf-controlplane/server-instances/serena-context-portal/run/serena-home"
mkdir -p "$SERENA_HOME"
if [[ -f "/home/dgk/workspace/cf-controlplane/server-instances/serena-context-portal/lsp.env" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "/home/dgk/workspace/cf-controlplane/server-instances/serena-context-portal/lsp.env"
  set +a
fi
exec serena start-mcp-server \
  --transport streamable-http \
  --host 127.0.0.1 \
  --port 9108 \
  --context codex \
  --project "/home/dgk/workspace/cf-controlplane" \
  --open-web-dashboard false
