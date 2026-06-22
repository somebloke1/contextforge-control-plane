#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

mkdir -p evidence
if [[ ! -f env/semantic-model.env ]]; then
  scripts/make-semantic-model-env.sh
fi

echo "== Pi Alpine version =="
docker compose -f compose.yml run --rm pi-alpine pi --version \
  | tee evidence/pi-alpine-version.txt

echo "== Pi Alpine agent smoke =="
docker compose -f compose.yml run --rm pi-alpine bash -lc '
  set -euo pipefail
  mkdir -p "${PI_CODING_AGENT_DIR}"
  cp /config/pi/AGENTS.md "${PI_CODING_AGENT_DIR}/AGENTS.md"
  python3 - <<PY
import json, os
p = "/config/pi/models.json"
data = json.load(open(p))
provider = data["providers"]["openrouter-semantic-test"]
provider["baseUrl"] = os.environ["OPENROUTER_BASE_URL"]
provider["apiKey"] = os.environ["OPENROUTER_API_KEY"]
provider["compat"]["openRouterRouting"]["only"] = [os.environ["OPENROUTER_PROVIDER_ROUTE"]]
provider["compat"]["openRouterRouting"]["order"] = [os.environ["OPENROUTER_PROVIDER_ROUTE"]]
provider["models"][0]["id"] = os.environ["OPENROUTER_MODEL"]
out = os.path.join(os.environ["PI_CODING_AGENT_DIR"], "models.json")
json.dump(data, open(out, "w"), indent=2)
PY
  pi --list-models "${CONTEXTFORGE_PI_DEFAULT_MODEL}"
  pi --no-session --no-tools --no-context-files --provider "${CONTEXTFORGE_PI_DEFAULT_PROVIDER}" --model "${CONTEXTFORGE_PI_DEFAULT_MODEL}" -p "Reply with exactly: pi-alpine-semantic-model-ok"
' | tee evidence/pi-alpine-agent-smoke.txt
