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

for service in pi pi-alpine; do
  output="${tmp_dir}/${service}.rpc.txt"
  if "${compose[@]}" run --rm --no-deps -T \
    -e PI_CODING_AGENT_DIR=/proc/contextforge-policy-probe \
    "${service}" pi --mode rpc >"${output}" 2>&1; then
    printf '%s\n' "${service}: RPC unexpectedly reached Pi" >&2
    exit 1
  fi
  grep -Fq "unsupported Pi sandbox control mode: rpc" "${output}"

  version="$("${compose[@]}" run --rm --no-deps -T \
    -e LITELLM_API_KEY=contextforge-policy-probe \
    -e LITELLM_BASE_URL=http://host.docker.internal:3333/v1 \
    "${service}" pi --version)"
  [[ "${version}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || {
    printf '%s\n' "${service}: invalid version output: ${version}" >&2
    exit 1
  }
  printf '%s\n' "${service}: rpc=blocked version=${version}"
done
