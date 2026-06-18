#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "${ROOT}/../.." && pwd)"
cd "${ROOT}"

if [[ ! -f env/local-llama.env ]]; then
  scripts/make-local-llama-env.sh
fi

docker compose -f compose.yml run --rm --no-deps \
  -v "${REPO_ROOT}:/repo:ro" \
  pi /config/pi/start-contextforge-baseline.sh "$@"
