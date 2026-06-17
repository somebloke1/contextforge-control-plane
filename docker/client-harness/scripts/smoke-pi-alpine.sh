#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

mkdir -p evidence
if [[ ! -f env/local-llama.env ]]; then
  scripts/make-local-llama-env.sh
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
provider = data["providers"]["local-llama-qwen"]
provider["baseUrl"] = os.environ["LOCAL_LLAMA_BASE_URL"]
provider["apiKey"] = os.environ["LOCAL_LLAMA_KEY"]
out = os.path.join(os.environ["PI_CODING_AGENT_DIR"], "models.json")
json.dump(data, open(out, "w"), indent=2)
PY
  pi --list-models qwen3.6-a3b
  pi --no-session --no-tools --no-context-files --provider local-llama-qwen --model qwen3.6-a3b -p "Reply with exactly: pi-alpine-qwen-ok"
' | tee evidence/pi-alpine-agent-smoke.txt
