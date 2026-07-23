#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${ROOT}/env/semantic-model.env"
HOST_ENV="${HOST_ENV:-${HOME}/.config/litellm/client.env}"

if [[ ! -f "${HOST_ENV}" ]]; then
  printf 'LiteLLM client env is missing: %s\n' "${HOST_ENV}" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "${HOST_ENV}"
set +a

if [[ -z "${LITELLM_API_KEY:-}" ]]; then
  printf 'LITELLM_API_KEY is not set in %s\n' "${HOST_ENV}" >&2
  exit 1
fi

host_litellm_base_url="${LITELLM_BASE_URL:-http://127.0.0.1:3333/v1}"

umask 077
{
  printf 'LITELLM_BASE_URL=%s\n' "${CONTEXTFORGE_LITELLM_DOCKER_BASE_URL:-http://host.docker.internal:3333/v1}"
  printf 'CONTEXTFORGE_LITELLM_HOST_BASE_URL=%s\n' "${host_litellm_base_url}"
  printf 'LITELLM_API_KEY=%s\n' "${LITELLM_API_KEY}"
  printf 'CONTEXTFORGE_TEST_PROVIDER=litellm\n'
  printf 'CONTEXTFORGE_TEST_PROVIDER_KIND=litellm\n'
  printf 'CONTEXTFORGE_TEST_MODEL=codex/gpt-5.6-luna\n'
  printf 'CONTEXTFORGE_TERRA_MODEL=codex/gpt-5.6-terra\n'
  printf 'CONTEXTFORGE_TERRA_ROLE=human\n'
  printf 'CONTEXTFORGE_TERRA_REASONING=high\n'
  printf 'CONTEXTFORGE_LUNA_MODEL=codex/gpt-5.6-luna\n'
  printf 'CONTEXTFORGE_LUNA_ROLE=blind\n'
  printf 'CONTEXTFORGE_LUNA_REASONING=medium\n'
  printf 'CONTEXTFORGE_SOL_MODEL=codex/gpt-5.6-sol\n'
  printf 'CONTEXTFORGE_SOL_ROLE=evaluator\n'
  printf 'CONTEXTFORGE_SOL_REASONING=high\n'
  printf 'CONTEXTFORGE_PI_DEFAULT_PROVIDER=litellm\n'
  printf 'CONTEXTFORGE_PI_DEFAULT_MODEL=codex/gpt-5.6-luna\n'
  printf 'CONTEXTFORGE_PI_DEFAULT_THINKING=medium\n'
  printf 'CONTEXTFORGE_OPENCODE_DEFAULT_MODEL=litellm/codex/gpt-5.6-luna\n'
  printf 'CONTEXTFORGE_OPENCODE_SMALL_MODEL=litellm/codex/gpt-5.6-luna\n'
  printf 'CONTEXTFORGE_OPENCODE_DEFAULT_VARIANT=medium\n'
} > "${OUT}"

printf 'wrote %s with LITELLM_API_KEY redacted\n' "${OUT}"
