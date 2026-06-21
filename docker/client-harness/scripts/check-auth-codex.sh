#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

scripts/run-codex-authenticated.sh bash -lc '
  set -euo pipefail
  while IFS="=" read -r name value; do
    case "${name}" in
      API_KEY|*_API_KEY)
        if [[ -n "${value}" ]]; then
          echo "Refusing Codex API-key auth in the client harness; use ChatGPT/OAuth subscription auth." >&2
          exit 2
        fi
        ;;
    esac
  done < <(env)
  grep -qx "cli_auth_credentials_store = \"file\"" "${HOME}/.codex/config.toml"
  test "$(grep -Ec "^model[[:space:]]*=" "${HOME}/.codex/config.toml")" -eq 1
  grep -qx "model = \"gpt-5.4-mini\"" "${HOME}/.codex/config.toml"
  codex --version
  codex login status
  codex doctor --summary --ascii
'
