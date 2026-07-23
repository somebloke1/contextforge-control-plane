#!/usr/bin/env bash
set -euo pipefail

: "${CONTEXTFORGE_PI_REAL_BIN:=/usr/bin/pi}"
: "${CONTEXTFORGE_PI_DEFAULT_PROVIDER:=litellm}"
: "${CONTEXTFORGE_PI_DEFAULT_MODEL:=codex/gpt-5.6-luna}"
: "${CONTEXTFORGE_PI_DEFAULT_THINKING:=medium}"
readonly CONTEXTFORGE_PI_APPROVED_MODELS="litellm/codex/gpt-5.6-terra,litellm/codex/gpt-5.6-luna,litellm/codex/gpt-5.6-sol"

fail_model_policy() {
  printf '%s\n' "$1" >&2
  exit 2
}

expected_thinking() {
  case "$1" in
    codex/gpt-5.6-terra) printf 'high\n' ;;
    codex/gpt-5.6-luna) printf 'medium\n' ;;
    codex/gpt-5.6-sol) printf 'high\n' ;;
    *) fail_model_policy "unsupported Pi sandbox model: $1" ;;
  esac
}

validate_provider() {
  [[ "$1" == litellm ]] || fail_model_policy "unsupported Pi sandbox provider: $1"
}

validate_provider "${CONTEXTFORGE_PI_DEFAULT_PROVIDER}"
default_expected_thinking="$(expected_thinking "${CONTEXTFORGE_PI_DEFAULT_MODEL}")"
if [[ "${CONTEXTFORGE_PI_DEFAULT_THINKING}" != "${default_expected_thinking}" ]]; then
  fail_model_policy "Pi sandbox thinking level ${CONTEXTFORGE_PI_DEFAULT_THINKING} does not match ${CONTEXTFORGE_PI_DEFAULT_MODEL} (${default_expected_thinking})"
fi

has_provider=false
has_model=false
has_thinking=false
skip_defaults=false
latest_prompt=""
selected_model="${CONTEXTFORGE_PI_DEFAULT_MODEL}"
selected_thinking=""
args=("$@")

for ((index = 0; index < ${#args[@]}; index += 1)); do
  arg="${args[index]}"
  case "${arg}" in
    --provider)
      ((index + 1 < ${#args[@]})) || fail_model_policy "--provider requires a value"
      [[ "${has_provider}" == false ]] || fail_model_policy "repeated --provider is forbidden"
      index=$((index + 1))
      validate_provider "${args[index]}"
      has_provider=true
      ;;
    --provider=*)
      validate_provider "${arg#--provider=}"
      fail_model_policy "Pi sandbox requires '--provider litellm' syntax"
      ;;
    --model)
      ((index + 1 < ${#args[@]})) || fail_model_policy "--model requires a value"
      [[ "${has_model}" == false ]] || fail_model_policy "repeated --model is forbidden"
      index=$((index + 1))
      selected_model="${args[index]}"
      expected_thinking "${selected_model}" >/dev/null
      has_model=true
      ;;
    --model=*)
      selected_model="${arg#--model=}"
      expected_thinking "${selected_model}" >/dev/null
      fail_model_policy "Pi sandbox requires '--model MODEL' syntax"
      ;;
    --thinking)
      ((index + 1 < ${#args[@]})) || fail_model_policy "--thinking requires a value"
      [[ "${has_thinking}" == false ]] || fail_model_policy "repeated --thinking is forbidden"
      index=$((index + 1))
      selected_thinking="${args[index]}"
      has_thinking=true
      ;;
    --thinking=*)
      fail_model_policy "Pi sandbox requires '--thinking LEVEL' syntax"
      ;;
    --api-key|--api-key=*)
      fail_model_policy "--api-key is forbidden; the Pi sandbox uses only LITELLM_API_KEY from its env file"
      ;;
    -p|--prompt)
      ((index + 1 < ${#args[@]})) || fail_model_policy "${arg} requires a value"
      index=$((index + 1))
      latest_prompt="${args[index]}"
      ;;
    --prompt=*)
      latest_prompt="${arg#--prompt=}"
      ;;
    --list-models)
      ((index + 1 < ${#args[@]})) || fail_model_policy "--list-models requires the litellm provider"
      index=$((index + 1))
      validate_provider "${args[index]}"
      skip_defaults=true
      ;;
    --list-models=*)
      validate_provider "${arg#--list-models=}"
      fail_model_policy "Pi sandbox requires '--list-models litellm' syntax"
      ;;
    --models|--models=*)
      fail_model_policy "--models is fixed by the Pi sandbox policy"
      ;;
    --version|-V|version|--help|-h|help|update)
      skip_defaults=true
      ;;
  esac
done

selected_expected_thinking="$(expected_thinking "${selected_model}")"
if [[ "${has_thinking}" == true && "${selected_thinking}" != "${selected_expected_thinking}" ]]; then
  fail_model_policy "Pi sandbox thinking level ${selected_thinking} does not match ${selected_model} (${selected_expected_thinking})"
fi

# shellcheck source=/usr/local/bin/contextforge-pi-bootstrap
. /usr/local/bin/contextforge-pi-bootstrap

default_args=()
if [[ "${skip_defaults}" == false ]]; then
  if [[ "${has_provider}" == false ]]; then
    default_args+=(--provider "${CONTEXTFORGE_PI_DEFAULT_PROVIDER}")
  fi
  if [[ "${has_model}" == false ]]; then
    default_args+=(--model "${CONTEXTFORGE_PI_DEFAULT_MODEL}")
  fi
  if [[ "${has_thinking}" == false ]]; then
    default_args+=(--thinking "${selected_expected_thinking}")
  fi
  default_args+=(--models "${CONTEXTFORGE_PI_APPROVED_MODELS}")
fi

if [[ -n "${latest_prompt}" && -n "${CONTEXTFORGE_HELPER_APPROVAL_SOURCE_PATH:-}" ]]; then
  mkdir -p "$(dirname "${CONTEXTFORGE_HELPER_APPROVAL_SOURCE_PATH}")"
  jq -n \
    --arg cwd "${PWD}" \
    --arg text "${latest_prompt}" \
    --arg recorded_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    '{cwd: $cwd, text: $text, recorded_at: $recorded_at}' \
    > "${CONTEXTFORGE_HELPER_APPROVAL_SOURCE_PATH}"
fi

exec "${CONTEXTFORGE_PI_REAL_BIN}" "${default_args[@]}" "$@"
