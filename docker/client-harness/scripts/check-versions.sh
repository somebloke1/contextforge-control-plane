#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

mkdir -p evidence
if [[ ! -f env/semantic-model.env ]]; then
  scripts/make-semantic-model-env.sh
fi

services=(codex-cli claude-code gemini-cli opencode pi)
for svc in "${services[@]}"; do
  echo "== ${svc} =="
  docker compose -f compose.yml run --rm "${svc}" 2>&1 | tee "evidence/${svc}-version.txt"
done
