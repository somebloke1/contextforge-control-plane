#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"

exec npx -y @playwright/mcp@latest \
  --browser=chromium \
  --headless \
  --isolated \
  --host 127.0.0.1 \
  --port 9104
