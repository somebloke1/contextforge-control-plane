#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
instance_home="$repo_root/server-instances/serena-context-portal"

export SERENA_HOME="$instance_home/run/serena-home"

exec serena start-mcp-server \
  --transport streamable-http \
  --host 127.0.0.1 \
  --port 9108 \
  --context codex \
  --project "$repo_root" \
  --open-web-dashboard false
