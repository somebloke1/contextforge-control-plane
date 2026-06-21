#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "${ROOT}/../.." && pwd)"
cd "${ROOT}"

if [[ ! -f env/semantic-model.env ]]; then
  scripts/make-semantic-model-env.sh
fi

docker compose -f compose.yml run --rm --no-deps \
  -v "${REPO_ROOT}:/repo:ro" \
  -v "${REPO_ROOT}:/workspace:ro" \
  pi /config/pi/start-contextforge-baseline.sh "$@"
