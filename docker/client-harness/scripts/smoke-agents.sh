#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

mkdir -p evidence
if [[ ! -f env/semantic-model.env ]]; then
  scripts/make-semantic-model-env.sh
fi

echo "== Pi agent smoke =="
docker compose -f compose.yml run --rm pi bash -lc '
  set -euo pipefail
  pi --list-models "${CONTEXTFORGE_PI_DEFAULT_MODEL}"
  pi --no-session --no-tools --no-context-files -p "Reply with exactly: pi-semantic-model-ok"
' | tee evidence/pi-agent-smoke.txt

echo "== OpenCode agent smoke =="
docker compose -f compose.yml run --rm opencode bash -lc '
  set -euo pipefail
  opencode run --model "${CONTEXTFORGE_OPENCODE_DEFAULT_MODEL}" --agent build --format default "Reply with exactly: opencode-semantic-model-ok"
' | tee evidence/opencode-agent-smoke.txt
