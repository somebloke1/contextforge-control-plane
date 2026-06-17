#!/usr/bin/env bash
set -euo pipefail

: "${PI_CODING_AGENT_DIR:=/home/agent/.pi/agent}"
: "${CONTEXTFORGE_PI_SHIM_EXTENSION:=/repo/pi-extensions/contextforge-global-shim/index.ts}"
: "${CONTEXTFORGE_PI_SHIM_PORTAL_ROOT:=/repo}"
: "${CONTEXTFORGE_PI_SHIM_WORKSPACE_ROOT:=/workspace}"
: "${CONTEXTFORGE_PI_SHIM_PYTHON:=/opt/contextforge-wrapper-venv/bin/python}"
: "${CONTEXTFORGE_PI_SHIM_WRAPPER:=/repo/scripts/contextforge_mcp_wrapper.py}"

mkdir -p "${PI_CODING_AGENT_DIR}"
cp /config/pi/AGENTS.md "${PI_CODING_AGENT_DIR}/AGENTS.md"

python3 - <<'PY'
import json
import os
from pathlib import Path

source = Path("/config/pi/models.json")
target = Path(os.environ["PI_CODING_AGENT_DIR"]) / "models.json"
data = json.loads(source.read_text(encoding="utf-8"))
provider = data["providers"]["local-llama-qwen"]
provider["baseUrl"] = os.environ["LOCAL_LLAMA_BASE_URL"]
provider["apiKey"] = os.environ["LOCAL_LLAMA_KEY"]
target.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

export CONTEXTFORGE_PI_SHIM_PORTAL_ROOT
export CONTEXTFORGE_PI_SHIM_WORKSPACE_ROOT
export CONTEXTFORGE_PI_SHIM_PYTHON
export CONTEXTFORGE_PI_SHIM_WRAPPER

exec pi \
  --extension "${CONTEXTFORGE_PI_SHIM_EXTENSION}" \
  --provider local-llama-qwen \
  --model qwen3.6-a3b \
  "$@"
