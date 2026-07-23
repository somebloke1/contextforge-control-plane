#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

mkdir -p evidence
scripts/make-semantic-model-env.sh

docker compose -f compose.yml --env-file env/semantic-model.env run --rm pi bash -lc '
  set -euo pipefail
  . /usr/local/bin/contextforge-pi-bootstrap
  expected=(codex/gpt-5.6-terra codex/gpt-5.6-luna codex/gpt-5.6-sol)
  pi --list-models litellm | tee /tmp/pi-models.txt >/dev/null
  for model in "${expected[@]}"; do
    grep -Fq "${model}" /tmp/pi-models.txt
  done
  python3 - <<"PY"
import json
import os
from pathlib import Path

expected = {"codex/gpt-5.6-terra", "codex/gpt-5.6-luna", "codex/gpt-5.6-sol"}
models = json.loads((Path(os.environ["PI_CODING_AGENT_DIR"]) / "models.json").read_text(encoding="utf-8"))
assert set(models["providers"]) == {"litellm"}
provider = models["providers"]["litellm"]
assert provider["api"] == "openai-responses"
assert provider["compat"]["supportsReasoningEffort"] is True
assert {model["id"] for model in provider["models"]} == expected
assert all(model["reasoning"] is True and "thinkingLevelMap" in model for model in provider["models"])
settings = json.loads((Path(os.environ["PI_CODING_AGENT_DIR"]) / "settings.json").read_text(encoding="utf-8"))
assert settings["defaultProvider"] == "litellm"
assert settings["defaultModel"] == "codex/gpt-5.6-luna"
assert settings["defaultThinkingLevel"] == "medium"
assert set(settings["enabledModels"]) == {f"litellm/{model}" for model in expected}
PY
  models_json="$(curl -fsS -H "Authorization: Bearer ${LITELLM_API_KEY}" "${LITELLM_BASE_URL}/models")"
  printf "[\n"
  first=true
  for model in "${expected[@]}"; do
    if [[ "${first}" == false ]]; then printf ",\n"; fi
    first=false
    printf "%s" "${models_json}" | python3 /repo/scripts/client_model_identity.py \
      --surface "Pi client Docker" \
      --client pi \
      --base-url "${LITELLM_BASE_URL}" \
      --expected-model-id "${model}" \
      --fail-on-stale
  done
  printf "]\n"
' | tee evidence/pi-semantic-model-identity.json

docker compose -f compose.yml --env-file env/semantic-model.env run --rm opencode bash -lc '
  set -euo pipefail
  expected=(codex/gpt-5.6-terra codex/gpt-5.6-luna codex/gpt-5.6-sol)
  opencode models litellm | tee /tmp/opencode-models.txt >/dev/null
  for model in "${expected[@]}"; do
    grep -Fq "litellm/${model}" /tmp/opencode-models.txt
  done
  python3 - <<"PY"
import json
import os
from pathlib import Path

expected = {"codex/gpt-5.6-terra", "codex/gpt-5.6-luna", "codex/gpt-5.6-sol"}
config = json.loads(Path(os.environ["OPENCODE_CONFIG"]).read_text(encoding="utf-8"))
assert config["enabled_providers"] == ["litellm"]
assert set(config["provider"]) == {"litellm"}
assert set(config["provider"]["litellm"]["models"]) == expected
assert set(config["provider"]["litellm"]["whitelist"]) == expected
assert config["model"] == "litellm/codex/gpt-5.6-luna"
assert config["small_model"] == "litellm/codex/gpt-5.6-luna"
assert config["agent"]["build"]["variant"] == "medium"
PY
  models_json="$(curl -fsS -H "Authorization: Bearer ${LITELLM_API_KEY}" "${LITELLM_BASE_URL}/models")"
  printf "[\n"
  first=true
  for model in "${expected[@]}"; do
    if [[ "${first}" == false ]]; then printf ",\n"; fi
    first=false
    printf "%s" "${models_json}" | python3 /repo/scripts/client_model_identity.py \
      --surface "OpenCode client Docker" \
      --client opencode \
      --base-url "${LITELLM_BASE_URL}" \
      --expected-model-id "${model}" \
      --fail-on-stale
  done
  printf "]\n"
' | tee evidence/opencode-semantic-model-identity.json
