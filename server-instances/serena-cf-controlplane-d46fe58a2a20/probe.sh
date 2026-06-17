#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"

url="${1:-http://127.0.0.1:9108/mcp}"

exec .venv/bin/python - "$url" <<'PY'
import anyio
import sys

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def main(url: str) -> None:
    async with streamablehttp_client(url, timeout=30, sse_read_timeout=30) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.list_tools()
            names = sorted(tool.name for tool in result.tools)
            print(f"tool_count={len(names)}")
            for name in names:
                print(name)


anyio.run(main, sys.argv[1])
PY
