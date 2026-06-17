#!/usr/bin/env bash
set -euo pipefail

docker run --rm \
  -v contextforge-harness_contextforge-data:/data:ro \
  busybox:1.36 \
  sh -c 'du -sh /data && find /data -maxdepth 2 -type f -exec ls -l {} \; | sort'
