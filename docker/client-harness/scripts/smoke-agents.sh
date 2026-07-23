#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

runtime_root="$(mktemp -d "${TMPDIR:-/tmp}/contextforge-model-smoke.XXXXXX")"
evidence_root="${runtime_root}/evidence"
semantic_model_env="${runtime_root}/semantic-model.env"
runtime_id="${runtime_root##*.}"
project_name="contextforge-model-smoke-${runtime_id,,}"
mkdir -p "${evidence_root}" "${runtime_root}/workspace" "${runtime_root}/server-instances" "${runtime_root}/client-scoped"
export CONTEXTFORGE_CLIENT_HARNESS_EVIDENCE="${evidence_root}"
export CONTEXTFORGE_CLIENT_HARNESS_WORKSPACE="${runtime_root}/workspace"
export CONTEXTFORGE_CLIENT_HARNESS_SERVER_INSTANCES="${runtime_root}/server-instances"
export CONTEXTFORGE_CLIENT_HARNESS_CLIENT_SCOPED="${runtime_root}/client-scoped"
export CONTEXTFORGE_CLIENT_HARNESS_PI_HOME=pi-home
export CONTEXTFORGE_CLIENT_HARNESS_OPENCODE_HOME=opencode-home
export CONTEXTFORGE_SEMANTIC_MODEL_ENV="${semantic_model_env}"
compose=(docker compose --project-name "${project_name}" -f compose.yml --env-file "${semantic_model_env}")

cleanup_started=0
active_cell_pid=""

project_resources_present() {
  [[ -n "$(docker ps -aq --filter "label=com.docker.compose.project=${project_name}")" ||
     -n "$(docker volume ls -q --filter "label=com.docker.compose.project=${project_name}")" ||
     -n "$(docker network ls -q --filter "label=com.docker.compose.project=${project_name}")" ]]
}

remove_project_resources() {
  local -a resources=()
  mapfile -t resources < <(docker ps -aq --filter "label=com.docker.compose.project=${project_name}")
  if (( ${#resources[@]} )); then
    docker rm -f "${resources[@]}" >/dev/null 2>&1 || true
  fi
  mapfile -t resources < <(docker network ls -q --filter "label=com.docker.compose.project=${project_name}")
  if (( ${#resources[@]} )); then
    docker network rm "${resources[@]}" >/dev/null 2>&1 || true
  fi
  mapfile -t resources < <(docker volume ls -q --filter "label=com.docker.compose.project=${project_name}")
  if (( ${#resources[@]} )); then
    docker volume rm -f "${resources[@]}" >/dev/null 2>&1 || true
  fi
}

cleanup() {
  local pid="${active_cell_pid}"
  if (( cleanup_started )); then
    return
  fi
  cleanup_started=1
  trap - EXIT
  trap '' INT TERM HUP
  if [[ -n "${pid}" ]]; then
    kill -TERM -- "-${pid}" >/dev/null 2>&1 || kill -TERM "${pid}" >/dev/null 2>&1 || true
    for _ in {1..10}; do
      if ! kill -0 "${pid}" >/dev/null 2>&1; then
        break
      fi
      sleep 0.05
    done
    kill -KILL -- "-${pid}" >/dev/null 2>&1 || true
    wait "${pid}" >/dev/null 2>&1 || true
    active_cell_pid=""
  fi
  "${compose[@]}" down -v --remove-orphans --timeout 1 >/dev/null 2>&1 || true
  rm -rf "${runtime_root}"
  if [[ -n "${pid}" ]]; then
    for _ in {1..20}; do
      remove_project_resources
      sleep 0.1
    done
    if project_resources_present; then
      printf 'model smoke cleanup could not remove all resources for %s\n' "${project_name}" >&2
    fi
    rm -rf "${runtime_root}"
  fi
}

terminate() {
  local status="$1"
  cleanup
  exit "${status}"
}

trap cleanup EXIT
trap 'terminate 130' INT
trap 'terminate 143' TERM
trap 'terminate 129' HUP

scripts/make-semantic-model-env.sh

reset_model_homes() {
  "${compose[@]}" down -v --remove-orphans >/dev/null 2>&1
}

run_compose_cell() {
  local output_file="$1"
  local status
  shift
  setsid "$@" > "${output_file}" &
  active_cell_pid=$!
  if wait "${active_cell_pid}"; then
    status=0
  else
    status=$?
  fi
  active_cell_pid=""
  return "${status}"
}

require_exact_response() {
  local expected="$1"
  local actual_file="$2"
  local expected_file
  expected_file="$(mktemp "${runtime_root}/expected.XXXXXX")"
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
  reset_model_homes
  output_file="$(mktemp "${runtime_root}/pi-${slug}.XXXXXX")"
  if ! run_compose_cell "${output_file}" "${compose[@]}" run --rm --no-deps -T \
    -e CONTEXTFORGE_PI_DEFAULT_MODEL="${model}" \
    -e CONTEXTFORGE_PI_DEFAULT_THINKING="${thinking}" \
    pi pi --no-session --no-tools --no-context-files --no-extensions \
      --provider litellm --model "${model}" --thinking "${thinking}" \
      -p "Reply with exactly: ${marker}"; then
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
  reset_model_homes
  output_file="$(mktemp "${runtime_root}/opencode-${slug}.XXXXXX")"
  if ! run_compose_cell "${output_file}" "${compose[@]}" run --rm --no-deps -T \
    -e CONTEXTFORGE_OPENCODE_DEFAULT_MODEL="${opencode_model}" \
    -e CONTEXTFORGE_OPENCODE_SMALL_MODEL="${opencode_model}" \
    -e CONTEXTFORGE_OPENCODE_DEFAULT_VARIANT="${variant}" \
    -e CONTEXTFORGE_OPENCODE_MODEL_SMOKE=1 \
    -e OPENCODE_CONFIG_DIR=/home/agent/.config/opencode-model-smoke \
    -e OPENCODE_CONFIG=/home/agent/.config/opencode-model-smoke/opencode.json \
    -e CONTEXTFORGE_OPENCODE_CONFIG_TARGET=/home/agent/.config/opencode-model-smoke/opencode.json \
    -e CONTEXTFORGE_OPENCODE_PLUGIN_TARGET=/home/agent/.config/opencode-model-smoke/plugins/contextforge-project-init.js \
    -e CONTEXTFORGE_OPENCODE_RULES_TARGET=/home/agent/.config/opencode-model-smoke/AGENTS.md \
    opencode opencode run --model "${opencode_model}" --agent build --format default \
      "Reply with exactly: ${marker}"; then
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
