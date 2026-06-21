#!/usr/bin/env bash
set -euo pipefail

: "${CONTEXTFORGE_PI_REAL_BIN:=/usr/bin/pi}"
: "${CONTEXTFORGE_PI_DEFAULT_PROVIDER:=openrouter-gemini-flash-lite}"
: "${CONTEXTFORGE_PI_DEFAULT_MODEL:=${OPENROUTER_MODEL:-google/gemini-2.5-flash-lite}}"

# shellcheck source=/usr/local/bin/contextforge-pi-bootstrap
. /usr/local/bin/contextforge-pi-bootstrap

has_provider=false
has_model=false
skip_defaults=false
latest_prompt=""
expect_prompt_value=false

for arg in "$@"; do
  if [[ "${expect_prompt_value}" == true ]]; then
    latest_prompt="${arg}"
    expect_prompt_value=false
    continue
  fi
  case "${arg}" in
    --provider|--provider=*)
      has_provider=true
      ;;
    --model|--model=*)
      has_model=true
      ;;
    -p|--prompt)
      expect_prompt_value=true
      ;;
    --prompt=*)
      latest_prompt="${arg#--prompt=}"
      ;;
    --version|-V|version|--help|-h|help|update|--list-models|--list-models=*)
      skip_defaults=true
      ;;
  esac
done

default_args=()
if [[ "${skip_defaults}" == false ]]; then
  if [[ "${has_provider}" == false ]]; then
    default_args+=(--provider "${CONTEXTFORGE_PI_DEFAULT_PROVIDER}")
  fi
  if [[ "${has_model}" == false ]]; then
    default_args+=(--model "${CONTEXTFORGE_PI_DEFAULT_MODEL}")
  fi
fi

if [[ -n "${latest_prompt}" && -n "${CONTEXTFORGE_HELPER_APPROVAL_SOURCE_PATH:-}" ]]; then
  mkdir -p "$(dirname "${CONTEXTFORGE_HELPER_APPROVAL_SOURCE_PATH}")"
  jq -n \
    --arg cwd "${PWD}" \
    --arg text "${latest_prompt}" \
    --arg recorded_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    '{cwd: $cwd, text: $text, recorded_at: $recorded_at}' \
    > "${CONTEXTFORGE_HELPER_APPROVAL_SOURCE_PATH}"
fi

exec "${CONTEXTFORGE_PI_REAL_BIN}" "${default_args[@]}" "$@"
