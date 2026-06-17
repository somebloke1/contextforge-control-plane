#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

mkdir -p evidence
if [[ ! -f env/local-llama.env ]]; then
  scripts/make-local-llama-env.sh
fi

echo "== OpenCode Alpine version =="
docker compose -f compose.yml run --rm opencode-alpine opencode --version \
  | tee evidence/opencode-alpine-version.txt

echo "== OpenCode Alpine agent smoke =="
docker compose -f compose.yml run --rm opencode-alpine bash -lc '
  set -euo pipefail
  opencode run --model "llama.cpp/${LOCAL_LLAMA_MODEL}" --agent build --format default "Reply with exactly: opencode-alpine-qwen-ok"
' | tee evidence/opencode-alpine-agent-smoke.txt
