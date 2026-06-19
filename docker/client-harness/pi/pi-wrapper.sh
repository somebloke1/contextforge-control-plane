#!/usr/bin/env bash
set -euo pipefail

: "${CONTEXTFORGE_PI_REAL_BIN:=/usr/bin/pi}"
: "${CONTEXTFORGE_PI_DEFAULT_PROVIDER:=local-llama-qwen}"
: "${LOCAL_LLAMA_MODEL:=qwen3.6-a3b}"

# shellcheck source=/usr/local/bin/contextforge-pi-bootstrap
. /usr/local/bin/contextforge-pi-bootstrap

has_provider=false
has_model=false
skip_defaults=false

for arg in "$@"; do
  case "${arg}" in
    --provider|--provider=*)
      has_provider=true
      ;;
    --model|--model=*)
      has_model=true
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
    default_args+=(--model "${LOCAL_LLAMA_MODEL}")
  fi
fi

exec "${CONTEXTFORGE_PI_REAL_BIN}" "${default_args[@]}" "$@"
