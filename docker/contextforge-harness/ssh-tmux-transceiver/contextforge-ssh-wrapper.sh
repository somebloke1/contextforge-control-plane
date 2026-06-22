#!/bin/sh
set -eu

REAL_SSH=/usr/bin/ssh
TARGET_HOST=${CONTEXTFORGE_SSH_TMUX_TEST_HOST:-}
TARGET_PORT=${CONTEXTFORGE_SSH_TMUX_TEST_PORT:-}
AUTH_MODE=${CONTEXTFORGE_SSH_TMUX_TEST_AUTH_MODE:-}
PRIVATE_KEY=${CONTEXTFORGE_SSH_TMUX_TEST_PRIVATE_KEY_PATH:-}
KNOWN_HOSTS=${CONTEXTFORGE_SSH_TMUX_TEST_KNOWN_HOSTS_PATH:-}
STRICT_HOST_KEY_CHECKING=${CONTEXTFORGE_SSH_TMUX_TEST_STRICT_HOST_KEY_CHECKING:-}
TARGET_PASSWORD=${CONTEXTFORGE_SSH_TMUX_TEST_PASSWORD:-}

destination_host() {
  previous_takes_value=0
  dest=""
  for arg in "$@"; do
    if [ "$previous_takes_value" = "1" ]; then
      previous_takes_value=0
      continue
    fi
    case "$arg" in
      -b|-c|-D|-E|-e|-F|-I|-i|-J|-L|-l|-m|-O|-o|-p|-Q|-R|-S|-W|-w)
        previous_takes_value=1
        continue
        ;;
      --)
        continue
        ;;
      -*)
        continue
        ;;
      *)
        dest=$arg
        ;;
    esac
  done
  dest=${dest#*@}
  printf '%s' "$dest"
}

DEST_HOST=$(destination_host "$@")
if [ -z "$TARGET_HOST" ] || [ "$DEST_HOST" != "$TARGET_HOST" ]; then
  exec "$REAL_SSH" "$@"
fi

if [ "$AUTH_MODE" = "key" ] && [ -n "$PRIVATE_KEY" ]; then
  set -- -i "$PRIVATE_KEY" "$@"
fi
if [ -n "$STRICT_HOST_KEY_CHECKING" ]; then
  set -- -o "StrictHostKeyChecking=$STRICT_HOST_KEY_CHECKING" "$@"
fi
if [ -n "$KNOWN_HOSTS" ]; then
  set -- -o "UserKnownHostsFile=$KNOWN_HOSTS" "$@"
fi
if [ -n "$TARGET_PORT" ]; then
  set -- -p "$TARGET_PORT" "$@"
fi

if [ "$AUTH_MODE" = "password" ] && [ -n "$TARGET_PASSWORD" ]; then
  export SSHPASS=$TARGET_PASSWORD
  exec sshpass -e "$REAL_SSH" "$@"
fi

exec "$REAL_SSH" "$@"
