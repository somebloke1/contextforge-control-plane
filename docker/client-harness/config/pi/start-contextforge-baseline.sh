#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=/usr/local/bin/contextforge-pi-bootstrap
. /usr/local/bin/contextforge-pi-bootstrap

has_thinking=false
for arg in "$@"; do
  case "${arg}" in
    --thinking|--thinking=*) has_thinking=true ;;
  esac
done

thinking_args=()
if [[ "${has_thinking}" == false ]]; then
  thinking_args+=(--thinking "${CONTEXTFORGE_PI_DEFAULT_THINKING:-medium}")
fi

exec "${CONTEXTFORGE_PI_REAL_BIN:-/usr/bin/pi}" \
  --provider "${CONTEXTFORGE_PI_DEFAULT_PROVIDER}" \
  --model "${CONTEXTFORGE_PI_DEFAULT_MODEL}" \
  "${thinking_args[@]}" \
  "$@"
