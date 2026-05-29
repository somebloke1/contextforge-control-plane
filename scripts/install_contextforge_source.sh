#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
version="${CONTEXTFORGE_VERSION:-v1.0.2}"
source_dir="${CONTEXTFORGE_SOURCE_DIR:-$repo_root/upstream/contextforge-${version#v}}"

if [[ ! -x "$repo_root/.venv/bin/python" ]]; then
  echo "Missing .venv/bin/python. Run: uv venv .venv" >&2
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "npm is required to build the stock ContextForge Admin UI bundle." >&2
  exit 1
fi

mkdir -p "$(dirname "$source_dir")"
if [[ ! -d "$source_dir/.git" ]]; then
  git clone --depth 1 --branch "$version" https://github.com/IBM/mcp-context-forge.git "$source_dir"
else
  git -C "$source_dir" fetch --depth 1 origin "refs/tags/$version:refs/tags/$version"
  git -C "$source_dir" checkout --detach "$version"
fi

(
  cd "$source_dir"
  if [[ -f package-lock.json ]]; then
    npm ci --no-audit --no-fund
  else
    npm install --no-audit --no-fund
  fi
  npm run build:css
  npm run vite:build
)

uv pip install --python "$repo_root/.venv/bin/python" -e "$source_dir"
