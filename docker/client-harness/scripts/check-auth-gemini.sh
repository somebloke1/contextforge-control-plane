#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

docker compose -f compose.yml run --rm gemini-cli bash -lc '
  set -euo pipefail
  gemini --skip-trust --output-format text -p "Reply with exactly: gemini-auth-ok"
'
