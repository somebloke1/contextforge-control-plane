#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=/usr/local/bin/contextforge-pi-bootstrap
. /usr/local/bin/contextforge-pi-bootstrap

exec "${CONTEXTFORGE_PI_REAL_BIN:-/usr/bin/pi}" \
  --provider "${CONTEXTFORGE_PI_DEFAULT_PROVIDER:-openrouter-gemini-flash-lite}" \
  --model "${CONTEXTFORGE_PI_DEFAULT_MODEL:-${OPENROUTER_MODEL:-google/gemini-2.5-flash-lite}}" \
  "$@"
