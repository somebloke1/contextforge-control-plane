#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=/usr/local/bin/contextforge-pi-bootstrap
. /usr/local/bin/contextforge-pi-bootstrap

exec "${CONTEXTFORGE_PI_REAL_BIN:-/usr/bin/pi}" \
  --provider local-llama-qwen \
  --model qwen3.6-a3b \
  "$@"
