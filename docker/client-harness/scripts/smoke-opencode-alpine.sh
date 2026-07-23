#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

mkdir -p evidence
if [[ ! -f env/semantic-model.env ]]; then
  scripts/make-semantic-model-env.sh
fi

echo "== OpenCode Alpine version =="
docker compose -f compose.yml --env-file env/semantic-model.env run --rm opencode-alpine opencode --version \
  | tee evidence/opencode-alpine-version.txt

echo "== OpenCode Alpine agent smoke =="
docker compose -f compose.yml --env-file env/semantic-model.env run --rm opencode-alpine bash -lc '
  set -euo pipefail
  opencode run --model "${CONTEXTFORGE_OPENCODE_DEFAULT_MODEL}" --agent build --format default "Reply with exactly: opencode-alpine-semantic-model-ok"
' | tee evidence/opencode-alpine-agent-smoke.txt
