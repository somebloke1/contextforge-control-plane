#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

mkdir -p evidence
if [[ ! -f env/semantic-model.env ]]; then
  scripts/make-semantic-model-env.sh
fi

echo "== OpenCode Alpine version =="
docker compose -f compose.yml run --rm opencode-alpine opencode --version \
  | tee evidence/opencode-alpine-version.txt

echo "== OpenCode Alpine agent smoke =="
docker compose -f compose.yml run --rm opencode-alpine bash -lc '
  set -euo pipefail
  install -d -m 0700 /home/agent/.local/share/opencode
  python3 - <<PY
import json
import os
from pathlib import Path
target = Path("/home/agent/.local/share/opencode/auth.json")
target.write_text(json.dumps({"openrouter": {"type": "api", "key": os.environ["OPENROUTER_API_KEY"]}}, indent=2) + "\n", encoding="utf-8")
target.chmod(0o600)
PY
  opencode run --model "${CONTEXTFORGE_OPENCODE_DEFAULT_MODEL}" --agent build --format default "Reply with exactly: opencode-alpine-semantic-model-ok"
' | tee evidence/opencode-alpine-agent-smoke.txt
