#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
volume_name="${CONTEXTFORGE_HARNESS_VOLUME:-contextforge-harness_contextforge-data}"
app_uid="${CONTEXTFORGE_HARNESS_UID:-10001}"
app_gid="${CONTEXTFORGE_HARNESS_GID:-10001}"

docker volume create "${volume_name}" >/dev/null
docker run --rm \
  --user 0:0 \
  --volume "${volume_name}:/data" \
  busybox:1.36 \
  sh -c "chown -R ${app_uid}:${app_gid} /data && chmod 755 /data"

echo "Prepared ${volume_name} for ContextForge app uid ${app_uid}:${app_gid}"
