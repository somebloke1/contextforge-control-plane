#!/usr/bin/env bash
set -euo pipefail

: "${OPENCODE_CONFIG:=/config/opencode/opencode.json}"
: "${LITELLM_BASE_URL:=http://host.docker.internal:3333/v1}"
: "${CONTEXTFORGE_OPENCODE_DEFAULT_MODEL:=litellm/codex/gpt-5.6-luna}"

fail_model_policy() {
  printf '%s\n' "$1" >&2
  exit 2
}

[[ "${LITELLM_BASE_URL%/}" == "http://host.docker.internal:3333/v1" ]] || \
  fail_model_policy "OpenCode Alpine requires sandbox LiteLLM on host.docker.internal:3333"
[[ -n "${LITELLM_API_KEY:-}" ]] || fail_model_policy "OpenCode Alpine requires LITELLM_API_KEY"
[[ "${CONTEXTFORGE_OPENCODE_DEFAULT_MODEL}" == "litellm/codex/gpt-5.6-luna" ]] || \
  fail_model_policy "OpenCode Alpine is fixed to Luna/medium through LiteLLM"

for key in OPENAI_API_KEY CODEX_API_KEY ANTHROPIC_API_KEY OPENROUTER_API_KEY GOOGLE_API_KEY GEMINI_API_KEY; do
  [[ -z "${!key:-}" ]] || fail_model_policy "OpenCode Alpine rejects direct-provider credential ${key}"
done

python3 - "${OPENCODE_CONFIG}" <<'PY'
import json
import sys
from pathlib import Path

config = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
model = "litellm/codex/gpt-5.6-luna"
if config.get("enabled_providers") != ["litellm"] or set(config.get("provider", {})) != {"litellm"}:
    raise SystemExit("OpenCode Alpine config must enable only the litellm provider")
if config.get("model") != model or config.get("small_model") != model:
    raise SystemExit("OpenCode Alpine config must default to Luna through LiteLLM")
build = config.get("agent", {}).get("build", {})
if build.get("model") != model or build.get("variant") != "medium":
    raise SystemExit("OpenCode Alpine build agent must use Luna/medium")
PY

exec /sbin/tini -- "$@"
