#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

runtime_root="$(mktemp -d "${TMPDIR:-/tmp}/contextforge-model-smoke.XXXXXX")"
evidence_root="${runtime_root}/evidence"
project_name="contextforge-model-smoke-$$"
mkdir -p "${evidence_root}" "${runtime_root}/workspace" "${runtime_root}/server-instances" "${runtime_root}/client-scoped"
export CONTEXTFORGE_CLIENT_HARNESS_EVIDENCE="${evidence_root}"
export CONTEXTFORGE_CLIENT_HARNESS_WORKSPACE="${runtime_root}/workspace"
export CONTEXTFORGE_CLIENT_HARNESS_SERVER_INSTANCES="${runtime_root}/server-instances"
export CONTEXTFORGE_CLIENT_HARNESS_CLIENT_SCOPED="${runtime_root}/client-scoped"
compose=(docker compose --project-name "${project_name}" -f compose.yml --env-file env/semantic-model.env)

cleanup() {
  "${compose[@]}" down -v --remove-orphans >/dev/null 2>&1 || true
  rm -rf "${runtime_root}"
}
trap cleanup EXIT

scripts/make-semantic-model-env.sh

require_exact_response() {
  local expected="$1"
  local actual_file="$2"
  local expected_file
  expected_file="$(mktemp)"
  printf '%s\n' "${expected}" > "${expected_file}"
  if ! cmp -s "${expected_file}" "${actual_file}"; then
    rm -f "${expected_file}"
    printf 'response mismatch: expected exactly %q\n' "${expected}" >&2
    return 1
  fi
  rm -f "${expected_file}"
}

run_pi_cell() {
  local slug="$1"
  local model="$2"
  local thinking="$3"
  local marker="pi-${slug}-${thinking}-ok"
  local output_file
  output_file="$(mktemp)"
  if ! "${compose[@]}" run --rm --no-deps -T \
    -e CONTEXTFORGE_PI_DEFAULT_MODEL="${model}" \
    -e CONTEXTFORGE_PI_DEFAULT_THINKING="${thinking}" \
    pi pi --no-session --no-tools --no-context-files --no-extensions \
      --provider litellm --model "${model}" --thinking "${thinking}" \
      -p "Reply with exactly: ${marker}" > "${output_file}"; then
    tee "${evidence_root}/pi-${slug}-agent-smoke.txt" < "${output_file}"
    rm -f "${output_file}"
    return 1
  fi
  tee "${evidence_root}/pi-${slug}-agent-smoke.txt" < "${output_file}"
  if ! require_exact_response "${marker}" "${output_file}"; then
    rm -f "${output_file}"
    return 1
  fi
  rm -f "${output_file}"
}

run_opencode_cell() {
  local slug="$1"
  local model="$2"
  local variant="$3"
  local marker="opencode-${slug}-${variant}-ok"
  local opencode_model="litellm/${model}"
  local output_file
  output_file="$(mktemp)"
  if ! "${compose[@]}" run --rm --no-deps -T \
    -e CONTEXTFORGE_OPENCODE_DEFAULT_MODEL="${opencode_model}" \
    -e CONTEXTFORGE_OPENCODE_SMALL_MODEL="${opencode_model}" \
    -e CONTEXTFORGE_OPENCODE_DEFAULT_VARIANT="${variant}" \
    -e CONTEXTFORGE_OPENCODE_MODEL_SMOKE=1 \
    -e OPENCODE_CONFIG_DIR=/home/agent/.config/opencode-model-smoke \
    -e CONTEXTFORGE_OPENCODE_CONFIG_TARGET=/home/agent/.config/opencode-model-smoke/opencode.json \
    -e CONTEXTFORGE_OPENCODE_PLUGIN_TARGET=/home/agent/.config/opencode-model-smoke/plugins/contextforge-project-init.js \
    -e CONTEXTFORGE_OPENCODE_RULES_TARGET=/home/agent/.config/opencode-model-smoke/AGENTS.md \
    opencode opencode run --model "${opencode_model}" --agent build --format default \
      "Reply with exactly: ${marker}" > "${output_file}"; then
    tee "${evidence_root}/opencode-${slug}-agent-smoke.txt" < "${output_file}"
    rm -f "${output_file}"
    return 1
  fi
  tee "${evidence_root}/opencode-${slug}-agent-smoke.txt" < "${output_file}"
  if ! require_exact_response "${marker}" "${output_file}"; then
    rm -f "${output_file}"
    return 1
  fi
  rm -f "${output_file}"
}

run_pi_cell terra codex/gpt-5.6-terra high
run_pi_cell luna codex/gpt-5.6-luna medium
run_pi_cell sol codex/gpt-5.6-sol high

run_opencode_cell terra codex/gpt-5.6-terra high
run_opencode_cell luna codex/gpt-5.6-luna medium
run_opencode_cell sol codex/gpt-5.6-sol high
