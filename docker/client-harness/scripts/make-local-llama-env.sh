#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${ROOT}/env/local-llama.env"
HOST_ENV="${HOST_ENV:-${HOME}/.env}"

if [[ ! -f "${HOST_ENV}" ]]; then
  echo "missing host env file: ${HOST_ENV}" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "${HOST_ENV}"
set +a

if [[ -z "${LOCAL_LLAMA_KEY:-}" ]]; then
  echo "LOCAL_LLAMA_KEY is not set after sourcing ${HOST_ENV}" >&2
  exit 1
fi

umask 077
{
  printf 'LOCAL_LLAMA_BASE_URL=%s\n' "${LOCAL_LLAMA_BASE_URL:-http://host.docker.internal:8742/v1}"
  printf 'LOCAL_LLAMA_MODEL=%s\n' "${LOCAL_LLAMA_MODEL:-qwen3.6-a3b}"
  printf 'LOCAL_LLAMA_KEY=%s\n' "${LOCAL_LLAMA_KEY}"
} > "${OUT}"

echo "wrote ${OUT} with LOCAL_LLAMA_KEY redacted"
