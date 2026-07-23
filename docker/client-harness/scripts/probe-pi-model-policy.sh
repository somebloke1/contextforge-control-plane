#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
HARNESS_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
cd "${HARNESS_ROOT}"

project_name="contextforge-pi-policy-$$"
compose=(docker compose --project-name "${project_name}" -f compose.yml)
if [[ "${CONTEXTFORGE_PI_POLICY_SKIP_BUILD:-0}" != 1 ]]; then
  "${compose[@]}" build pi pi-alpine
fi

tmp_dir="$(mktemp -d)"
cleanup() {
  "${compose[@]}" down -v --remove-orphans >/dev/null 2>&1 || true
  rm -rf "${tmp_dir}"
}
trap cleanup EXIT

reject_invocation() {
  local service="$1"
  local slug="$2"
  local expected_error="$3"
  shift 3
  local output="${tmp_dir}/${service}.${slug}.txt"
  if printf '%s\n' '{"type":"get_state"}' | "${compose[@]}" run --rm --no-deps -T \
    -e PI_CODING_AGENT_DIR=/proc/contextforge-policy-probe \
    "${service}" pi "$@" >"${output}" 2>&1; then
    printf '%s\n' "${service}/${slug}: rejected invocation unexpectedly reached Pi" >&2
    exit 1
  fi
  grep -Fq "${expected_error}" "${output}"
}

for service in pi pi-alpine; do
  rpc_error="unsupported Pi sandbox control mode: rpc"
  prompt_error="unsupported Pi sandbox option: --prompt"
  reject_invocation "${service}" canonical "${rpc_error}" --mode rpc
  reject_invocation "${service}" short-print-first "${rpc_error}" -p --mode rpc
  reject_invocation "${service}" long-print-first "${rpc_error}" --print --mode rpc
  reject_invocation "${service}" print-last "${rpc_error}" --mode rpc --print
  reject_invocation "${service}" equals-after-print "${rpc_error}" --print --mode=rpc
  reject_invocation "${service}" legacy-prompt-hides-mode "${prompt_error}" --prompt --mode rpc
  reject_invocation "${service}" legacy-prompt-equals "${prompt_error}" --prompt=message --mode rpc

  version="$("${compose[@]}" run --rm --no-deps -T \
    -e LITELLM_API_KEY=contextforge-policy-probe \
    -e LITELLM_BASE_URL=http://host.docker.internal:3333/v1 \
    "${service}" pi --version)"
  [[ "${version}" == 0.81.1 ]] || {
    printf '%s\n' "${service}: expected version 0.81.1, got: ${version}" >&2
    exit 1
  }
  printf '%s\n' "${service}: rpc=blocked version=${version}"
done
