#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

docker compose -f compose.yml run --rm codex-cli bash -lc '
  set -euo pipefail
  codex login status
  codex doctor --summary --ascii
'
