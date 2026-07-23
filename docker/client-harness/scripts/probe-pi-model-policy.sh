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

reject_rpc() {
  local service="$1"
  local slug="$2"
  shift 2
  local output="${tmp_dir}/${service}.${slug}.txt"
  if printf '%s\n' '{"type":"get_state"}' | "${compose[@]}" run --rm --no-deps -T \
    -e PI_CODING_AGENT_DIR=/proc/contextforge-policy-probe \
    "${service}" pi "$@" >"${output}" 2>&1; then
    printf '%s\n' "${service}/${slug}: RPC unexpectedly reached Pi" >&2
    exit 1
  fi
  grep -Fq "unsupported Pi sandbox control mode: rpc" "${output}"
}

for service in pi pi-alpine; do
  reject_rpc "${service}" canonical --mode rpc
  reject_rpc "${service}" short-print-first -p --mode rpc
  reject_rpc "${service}" long-print-first --print --mode rpc
  reject_rpc "${service}" print-last --mode rpc --print
  reject_rpc "${service}" equals-after-print --print --mode=rpc

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
