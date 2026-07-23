#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "${ROOT}/../.." && pwd)"
cd "${ROOT}"

scripts/make-semantic-model-env.sh

docker compose -f compose.yml --env-file env/semantic-model.env run --rm --no-deps \
  -v "${REPO_ROOT}:/repo:ro" \
  -v "${REPO_ROOT}:/workspace:ro" \
  pi /config/pi/start-contextforge-baseline.sh "$@"
