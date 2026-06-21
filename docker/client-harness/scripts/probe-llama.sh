#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

mkdir -p evidence
if [[ ! -f env/semantic-model.env ]]; then
  scripts/make-semantic-model-env.sh
fi

docker compose -f compose.yml run --rm pi bash -lc '
  set -euo pipefail
  mkdir -p "${PI_CODING_AGENT_DIR}"
  cp /config/pi/models.json "${PI_CODING_AGENT_DIR}/models.json"
  cp /config/pi/AGENTS.md "${PI_CODING_AGENT_DIR}/AGENTS.md"
  models_json="$(curl -sS -H "Authorization: Bearer ${OPENROUTER_API_KEY}" "${OPENROUTER_BASE_URL}/models")"
  printf "%s" "${models_json}" \
    | python3 /repo/scripts/client_model_identity.py \
      --surface "Pi client Docker" \
      --client pi \
      --base-url "${OPENROUTER_BASE_URL}" \
      --expected-model-id "${OPENROUTER_MODEL}" \
      --fail-on-stale
' | tee evidence/pi-semantic-model-identity.json

docker compose -f compose.yml run --rm opencode bash -lc '
  set -euo pipefail
  models_json="$(curl -sS -H "Authorization: Bearer ${OPENROUTER_API_KEY}" "${OPENROUTER_BASE_URL}/models")"
  printf "%s" "${models_json}" \
    | python3 /repo/scripts/client_model_identity.py \
      --surface "OpenCode client Docker" \
      --client opencode \
      --base-url "${OPENROUTER_BASE_URL}" \
      --expected-model-id "${OPENROUTER_MODEL}" \
      --fail-on-stale
' | tee evidence/opencode-semantic-model-identity.json
