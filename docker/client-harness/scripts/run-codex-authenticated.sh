#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

env_args=()
while IFS='=' read -r name _value; do
  case "${name}" in
    API_KEY|*_API_KEY)
      env_args+=("-u" "${name}")
      ;;
  esac
done < <(env)

exec env "${env_args[@]}" \
  docker compose -f compose.yml run --rm --no-deps \
  -e OPENAI_API_KEY= \
  -e CODEX_API_KEY= \
  -e ANTHROPIC_API_KEY= \
  -e OPENROUTER_API_KEY= \
  -e GOOGLE_API_KEY= \
  -e GEMINI_API_KEY= \
  -e PERPLEXITY_API_KEY= \
  -e EXA_API_KEY= \
  -e CONTEXT7_API_KEY= \
  codex-cli-authenticated "$@"
