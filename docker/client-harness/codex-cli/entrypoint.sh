#!/usr/bin/env bash
set -euo pipefail

: "${CODEX_HOME:=/home/agent/.codex}"
: "${CONTEXTFORGE_HELPER_PYTHON:=/opt/contextforge-helper-venv/bin/python}"
: "${CONTEXTFORGE_HELPER_SCRIPT:=/repo/scripts/contextforge_helper_mcp.py}"
: "${CONTEXTFORGE_CODEX_HOOK:=/usr/local/bin/contextforge-codex-project-init-hook}"
: "${CONTEXTFORGE_CODEX_WRAPPER_PYTHON:=/opt/contextforge-helper-venv/bin/python}"
: "${CONTEXTFORGE_CODEX_WRAPPER_SCRIPT:=/repo/scripts/contextforge_mcp_wrapper.py}"
: "${CONTEXTFORGE_CODEX_WRAPPER_CONFIG_ENV:=/config/contextforge/contextforge.env}"
: "${CONTEXTFORGE_CODEX_WRAPPER_BASE_URL:=http://host.docker.internal:4445}"
: "${CONTEXTFORGE_CODEX_WRAPPER_TOKEN_CACHE:=/tmp/contextforge-wrapper-token.local.json}"
: "${CONTEXTFORGE_PROJECT_INIT_RUN_ROOT:=/home/agent/.local/state/contextforge-client-harness-runtime/project-init}"
: "${CONTEXTFORGE_HELPER_APPROVAL_SOURCE_PATH:=${CONTEXTFORGE_PROJECT_INIT_RUN_ROOT}/codex-latest-user-message.json}"
: "${CONTEXTFORGE_ADDITIONAL_SAFE_PROJECT_ROOTS:=/workspace}"
: "${XDG_RUNTIME_DIR:=/home/agent/.local/state/contextforge-client-harness-runtime}"

while IFS="=" read -r name value; do
  case "${name}" in
    API_KEY|*_API_KEY)
      if [[ -n "${value}" ]]; then
        printf 'Refusing Codex API-key auth in the client harness; use ChatGPT/OAuth subscription auth.\n' >&2
        exit 2
      fi
      ;;
  esac
done < <(env)

config_path="${CODEX_HOME}/config.toml"
mkdir -p "${CODEX_HOME}" "${XDG_RUNTIME_DIR}" "${CONTEXTFORGE_PROJECT_INIT_RUN_ROOT}"
touch "${config_path}"

if ! grep -q '^cli_auth_credentials_store = "file"$' "${config_path}"; then
  printf 'cli_auth_credentials_store = "file"\n' >> "${config_path}"
fi

if ! grep -q '^model = "gpt-5.4-mini"$' "${config_path}"; then
  printf 'model = "gpt-5.4-mini"\n' >> "${config_path}"
fi

if ! grep -q '^\[projects\."/workspace"\]$' "${config_path}"; then
  {
    printf '\n[projects."/workspace"]\n'
    printf 'trust_level = "trusted"\n'
  } >> "${config_path}"
fi

if ! grep -q '^\[mcp_servers\.contextforge-helper\]$' "${config_path}"; then
  {
    printf '\n# contextforge-client-harness-codex-baseline\n'
    printf '[mcp_servers.contextforge-helper]\n'
    printf 'command = "%s"\n' "${CONTEXTFORGE_HELPER_PYTHON}"
    printf 'args = ["%s"]\n' "${CONTEXTFORGE_HELPER_SCRIPT}"
    printf 'cwd = "/repo"\n'
    printf 'env = { CONTEXTFORGE_HELPER_DEFAULT_CLIENT_TYPE = "codex", CONTEXTFORGE_HELPER_REQUIRE_USER_APPROVAL_TEXT = "1", CONTEXTFORGE_HELPER_PYTHON = "%s", CONTEXTFORGE_HELPER_SCRIPT = "%s", CONTEXTFORGE_PROJECT_INIT_RUN_ROOT = "%s", CONTEXTFORGE_HELPER_APPROVAL_SOURCE_PATH = "%s", CONTEXTFORGE_ADDITIONAL_SAFE_PROJECT_ROOTS = "%s", CONTEXTFORGE_CODEX_WRAPPER_PYTHON = "%s", CONTEXTFORGE_CODEX_WRAPPER_SCRIPT = "%s", CONTEXTFORGE_CODEX_WRAPPER_CONFIG_ENV = "%s", CONTEXTFORGE_CODEX_WRAPPER_BASE_URL = "%s", CONTEXTFORGE_CODEX_WRAPPER_TOKEN_CACHE = "%s" }\n' \
      "${CONTEXTFORGE_HELPER_PYTHON}" \
      "${CONTEXTFORGE_HELPER_SCRIPT}" \
      "${CONTEXTFORGE_PROJECT_INIT_RUN_ROOT}" \
      "${CONTEXTFORGE_HELPER_APPROVAL_SOURCE_PATH}" \
      "${CONTEXTFORGE_ADDITIONAL_SAFE_PROJECT_ROOTS}" \
      "${CONTEXTFORGE_CODEX_WRAPPER_PYTHON}" \
      "${CONTEXTFORGE_CODEX_WRAPPER_SCRIPT}" \
      "${CONTEXTFORGE_CODEX_WRAPPER_CONFIG_ENV}" \
      "${CONTEXTFORGE_CODEX_WRAPPER_BASE_URL}" \
      "${CONTEXTFORGE_CODEX_WRAPPER_TOKEN_CACHE}"
  } >> "${config_path}"
fi

if ! grep -q '^\[hooks\]$' "${config_path}"; then
  printf '\n[hooks]\n' >> "${config_path}"
fi

if ! grep -q "${CONTEXTFORGE_CODEX_HOOK}" "${config_path}"; then
  {
    printf '\n[[hooks.SessionStart]]\n'
    printf 'matcher = "startup"\n'
    printf '\n[[hooks.SessionStart.hooks]]\n'
    printf 'type = "command"\n'
    printf 'command = "%s"\n' "${CONTEXTFORGE_CODEX_HOOK}"
    printf 'timeout = 10\n'
    printf '\n[[hooks.UserPromptSubmit]]\n'
    printf '\n[[hooks.UserPromptSubmit.hooks]]\n'
    printf 'type = "command"\n'
    printf 'command = "%s"\n' "${CONTEXTFORGE_CODEX_HOOK}"
    printf 'timeout = 10\n'
  } >> "${config_path}"
fi

export CODEX_HOME
export CONTEXTFORGE_HELPER_PYTHON
export CONTEXTFORGE_HELPER_SCRIPT
export CONTEXTFORGE_CODEX_WRAPPER_PYTHON
export CONTEXTFORGE_CODEX_WRAPPER_SCRIPT
export CONTEXTFORGE_CODEX_WRAPPER_CONFIG_ENV
export CONTEXTFORGE_CODEX_WRAPPER_BASE_URL
export CONTEXTFORGE_CODEX_WRAPPER_TOKEN_CACHE
export CONTEXTFORGE_PROJECT_INIT_RUN_ROOT
export CONTEXTFORGE_HELPER_APPROVAL_SOURCE_PATH
export CONTEXTFORGE_ADDITIONAL_SAFE_PROJECT_ROOTS
export XDG_RUNTIME_DIR

exec "$@"
