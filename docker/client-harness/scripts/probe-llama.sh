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
  models_json="$(curl -sS -H "Authorization: Bearer ${LOCAL_LLAMA_KEY}" "${LOCAL_LLAMA_BASE_URL}/models")"
  printf "%s" "${models_json}" \
    | python3 /repo/scripts/client_model_identity.py \
      --surface "Pi client Docker" \
      --client pi \
      --base-url "${LOCAL_LLAMA_BASE_URL}" \
      --expected-model-id "${LOCAL_LLAMA_MODEL}" \
      --fail-on-stale
' | tee evidence/pi-llama-model-identity.json

docker compose -f compose.yml run --rm opencode bash -lc '
  set -euo pipefail
  models_json="$(curl -sS -H "Authorization: Bearer ${LOCAL_LLAMA_KEY}" "${LOCAL_LLAMA_BASE_URL}/models")"
  printf "%s" "${models_json}" \
    | python3 /repo/scripts/client_model_identity.py \
      --surface "OpenCode client Docker" \
      --client opencode \
      --base-url "${LOCAL_LLAMA_BASE_URL}" \
      --expected-model-id "${LOCAL_LLAMA_MODEL}" \
      --fail-on-stale
' | tee evidence/opencode-llama-model-identity.json
