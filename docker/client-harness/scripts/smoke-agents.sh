#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

mkdir -p evidence
scripts/make-semantic-model-env.sh

require_exact_response() {
  local expected="$1"
  local actual="$2"
  if [[ "${actual}" != "${expected}" ]]; then
    printf 'response mismatch: expected exactly %q\n' "${expected}" >&2
    return 1
  fi
}

run_pi_cell() {
  local slug="$1"
  local model="$2"
  local thinking="$3"
  local marker="pi-${slug}-${thinking}-ok"
  local output
  output="$(docker compose -f compose.yml --env-file env/semantic-model.env run --rm \
    -e CONTEXTFORGE_PI_DEFAULT_MODEL="${model}" \
    -e CONTEXTFORGE_PI_DEFAULT_THINKING="${thinking}" \
    pi pi --no-session --no-tools --no-context-files \
      --provider litellm --model "${model}" --thinking "${thinking}" \
      -p "Reply with exactly: ${marker}")"
  printf '%s\n' "${output}" | tee "evidence/pi-${slug}-agent-smoke.txt"
  require_exact_response "${marker}" "${output}"
}

run_opencode_cell() {
  local slug="$1"
  local model="$2"
  local variant="$3"
  local marker="opencode-${slug}-${variant}-ok"
  local opencode_model="litellm/${model}"
  local output
  output="$(docker compose -f compose.yml --env-file env/semantic-model.env run --rm \
    -e CONTEXTFORGE_OPENCODE_DEFAULT_MODEL="${opencode_model}" \
    -e CONTEXTFORGE_OPENCODE_SMALL_MODEL="${opencode_model}" \
    -e CONTEXTFORGE_OPENCODE_DEFAULT_VARIANT="${variant}" \
    opencode opencode run --model "${opencode_model}" --agent build --format default \
      "Reply with exactly: ${marker}")"
  printf '%s\n' "${output}" | tee "evidence/opencode-${slug}-agent-smoke.txt"
  require_exact_response "${marker}" "${output}"
}

run_pi_cell terra codex/gpt-5.6-terra high
run_pi_cell luna codex/gpt-5.6-luna medium
run_pi_cell sol codex/gpt-5.6-sol high

run_opencode_cell terra codex/gpt-5.6-terra high
run_opencode_cell luna codex/gpt-5.6-luna medium
run_opencode_cell sol codex/gpt-5.6-sol high
