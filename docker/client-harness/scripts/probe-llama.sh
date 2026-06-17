#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

mkdir -p evidence
if [[ ! -f env/local-llama.env ]]; then
  scripts/make-local-llama-env.sh
fi

docker compose -f compose.yml run --rm pi bash -lc '
  set -euo pipefail
  mkdir -p "${PI_CODING_AGENT_DIR}"
  cp /config/pi/models.json "${PI_CODING_AGENT_DIR}/models.json"
  cp /config/pi/AGENTS.md "${PI_CODING_AGENT_DIR}/AGENTS.md"
  echo "LOCAL_LLAMA_KEY_PRESENT=${LOCAL_LLAMA_KEY:+yes}"
  curl -sS -H "Authorization: Bearer ${LOCAL_LLAMA_KEY}" "${LOCAL_LLAMA_BASE_URL}/models" \
    | jq -r ".data[]?.id // .models[]? // empty" | grep -E "qwen|local-llama" || true
' | tee evidence/pi-llama-models.txt

docker compose -f compose.yml run --rm opencode bash -lc '
  set -euo pipefail
  echo "LOCAL_LLAMA_KEY_PRESENT=${LOCAL_LLAMA_KEY:+yes}"
  curl -sS -H "Authorization: Bearer ${LOCAL_LLAMA_KEY}" "${LOCAL_LLAMA_BASE_URL}/models" \
    | jq -r ".data[]?.id // .models[]? // empty" | grep -E "qwen|local-llama" || true
' | tee evidence/opencode-llama-models.txt
