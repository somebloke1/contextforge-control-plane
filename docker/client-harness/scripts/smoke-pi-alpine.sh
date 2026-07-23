#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

mkdir -p evidence
if [[ ! -f env/semantic-model.env ]]; then
  scripts/make-semantic-model-env.sh
fi

echo "== Pi Alpine version =="
docker compose -f compose.yml --env-file env/semantic-model.env run --rm pi-alpine pi --version \
  | tee evidence/pi-alpine-version.txt

echo "== Pi Alpine agent smoke =="
docker compose -f compose.yml --env-file env/semantic-model.env run --rm pi-alpine bash -lc '
  set -euo pipefail
  pi --list-models "${CONTEXTFORGE_PI_DEFAULT_PROVIDER}"
  pi --no-session --no-tools --no-context-files \
    --provider "${CONTEXTFORGE_PI_DEFAULT_PROVIDER}" \
    --model "${CONTEXTFORGE_PI_DEFAULT_MODEL}" \
    --thinking "${CONTEXTFORGE_PI_DEFAULT_THINKING}" \
    -p "Reply with exactly: pi-alpine-semantic-model-ok"
' | tee evidence/pi-alpine-agent-smoke.txt
