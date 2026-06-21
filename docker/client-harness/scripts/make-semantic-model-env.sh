#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${ROOT}/env/semantic-model.env"
HOST_ENV="${HOST_ENV:-${HOME}/.env}"

if [[ -f "${HOST_ENV}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${HOST_ENV}"
  set +a
fi

if [[ -z "${OPENROUTER_API_KEY:-}" ]]; then
  echo "OPENROUTER_API_KEY is not set in ${HOST_ENV}" >&2
  exit 1
fi

umask 077
{
  printf 'CONTEXTFORGE_TEST_PROVIDER=%s\n' "${CONTEXTFORGE_TEST_PROVIDER:-openrouter}"
  printf 'CONTEXTFORGE_TEST_MODEL=%s\n' "${CONTEXTFORGE_TEST_MODEL:-google/gemini-2.5-flash-lite}"
  printf 'CONTEXTFORGE_TEST_PROVIDER_ROUTE=%s\n' "${CONTEXTFORGE_TEST_PROVIDER_ROUTE:-google-ai-studio}"
  printf 'OPENROUTER_BASE_URL=%s\n' "${OPENROUTER_BASE_URL:-https://openrouter.ai/api/v1}"
  printf 'OPENROUTER_MODEL=%s\n' "${OPENROUTER_MODEL:-${CONTEXTFORGE_TEST_MODEL:-google/gemini-2.5-flash-lite}}"
  printf 'OPENROUTER_OPENCODE_MODEL=%s\n' "${OPENROUTER_OPENCODE_MODEL:-${CONTEXTFORGE_TEST_MODEL:-google/gemini-2.5-flash-lite}}"
  printf 'OPENROUTER_PROVIDER_ROUTE=%s\n' "${OPENROUTER_PROVIDER_ROUTE:-${CONTEXTFORGE_TEST_PROVIDER_ROUTE:-google-ai-studio}}"
  printf 'OPENROUTER_PROVIDER_ROUTES=%s\n' "${OPENROUTER_PROVIDER_ROUTES:-${OPENROUTER_PROVIDER_ROUTE:-${CONTEXTFORGE_TEST_PROVIDER_ROUTE:-google-ai-studio}}}"
  printf 'OPENROUTER_STICKY_KEY=%s\n' "${OPENROUTER_STICKY_KEY:-contextforge-semantic-test}"
  printf 'OPENROUTER_STICKY_EPOCH_SECONDS=%s\n' "${OPENROUTER_STICKY_EPOCH_SECONDS:-7200}"
  printf 'CONTEXTFORGE_PI_DEFAULT_PROVIDER=%s\n' "${CONTEXTFORGE_PI_DEFAULT_PROVIDER:-openrouter-gemini-flash-lite}"
  printf 'CONTEXTFORGE_PI_DEFAULT_MODEL=%s\n' "${CONTEXTFORGE_PI_DEFAULT_MODEL:-${OPENROUTER_MODEL:-${CONTEXTFORGE_TEST_MODEL:-google/gemini-2.5-flash-lite}}}"
  printf 'CONTEXTFORGE_OPENCODE_DEFAULT_MODEL=%s\n' "${CONTEXTFORGE_OPENCODE_DEFAULT_MODEL:-openrouter/${OPENROUTER_OPENCODE_MODEL:-${CONTEXTFORGE_TEST_MODEL:-google/gemini-2.5-flash-lite}}}"
  printf 'OPENROUTER_API_KEY=%s\n' "${OPENROUTER_API_KEY}"
} > "${OUT}"

echo "wrote ${OUT} with OPENROUTER_API_KEY redacted"
