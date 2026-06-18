#!/usr/bin/env python3
"""Probe direct and ContextForge-virtual Context7 dev-Docker MCP endpoints."""

from __future__ import annotations

import argparse
import anyio
from pathlib import Path
from typing import Any
from uuid import uuid4

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

import register_context7_dev as registration


DEFAULT_DIRECT_URL = "http://127.0.0.1:9203/mcp"
PROBE_TOKEN_PERMISSIONS = [
    "servers.use",
    "tools.read",
    "tools.execute",
    "resources.read",
    "prompts.read",
]
SAFE_CONTEXT7_ARGS = {
    "libraryName": "python",
    "query": "standard library documentation lookup",
}


async def list_tools(url: str, *, headers: dict[str, str] | None = None) -> list[str]:
    async with streamablehttp_client(url, headers=headers, timeout=30, sse_read_timeout=30) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.list_tools()
            return sorted(tool.name for tool in result.tools)


async def call_resolve_library(url: str, *, headers: dict[str, str] | None = None) -> str:
    async with streamablehttp_client(url, headers=headers, timeout=30, sse_read_timeout=30) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = sorted(tool.name for tool in tools.tools)
            candidates = [name for name in names if name.endswith("resolve-library-id")]
            if not candidates:
                raise RuntimeError(f"no Context7 resolve-library-id tool found in {names}")
            result = await session.call_tool(candidates[0], SAFE_CONTEXT7_ARGS)
            if getattr(result, "isError", False):
                raise RuntimeError("Context7 safe probe returned isError=true")
            text = str(result.content[0].text if result.content else "")
            if "/python/" not in text.lower() and "python" not in text.lower():
                raise RuntimeError("Context7 safe probe did not return Python documentation evidence")
            return candidates[0]


def virtual_server(base_url: str, admin_token: str, server_name: str) -> dict[str, Any]:
    servers = registration.items(
        registration.request_json("GET", base_url, "/servers?include_inactive=true&limit=1000", token=admin_token)
    )
    matches = [server for server in servers if server.get("name") == server_name]
    if len(matches) != 1:
        raise RuntimeError(f"expected one virtual server named {server_name!r}, found {len(matches)}")
    return matches[0]


def create_probe_token(base_url: str, admin_token: str, server_id: str) -> tuple[str, str]:
    response = registration.request_json(
        "POST",
        base_url,
        "/tokens",
        token=admin_token,
        body={
            "name": f"context7-dev-docker-probe-{uuid4().hex[:12]}",
            "description": "Ephemeral dev harness token for Context7 virtual MCP probe.",
            "expires_in_days": 1,
            "scope": {
                "server_id": server_id,
                "permissions": PROBE_TOKEN_PERMISSIONS,
            },
            "tags": ["contextforge", "dev-docker", "context7", "probe", "ephemeral"],
        },
    )
    if not isinstance(response, dict):
        raise RuntimeError("ContextForge token create did not return JSON")
    token_record = response.get("token")
    token_id = token_record.get("id") if isinstance(token_record, dict) else None
    access_token = response.get("access_token")
    if not isinstance(token_id, str) or not token_id:
        raise RuntimeError("ContextForge token create did not return token.id")
    if not isinstance(access_token, str) or not access_token:
        raise RuntimeError("ContextForge token create did not return access_token")
    return token_id, access_token


def revoke_probe_token(base_url: str, admin_token: str, token_id: str) -> None:
    registration.request_json(
        "DELETE",
        base_url,
        f"/tokens/{token_id}",
        token=admin_token,
        body={"reason": "dev harness Context7 virtual MCP probe complete"},
    )


async def main_async(args: argparse.Namespace) -> None:
    direct_names = await list_tools(args.direct_url)
    print(f"direct_url={args.direct_url}")
    print(f"direct_tool_count={len(direct_names)}")
    for name in direct_names:
        print(f"direct_tool={name}")
    direct_probe_tool = await call_resolve_library(args.direct_url)
    print(f"direct_safe_probe_tool={direct_probe_tool}")
    print("direct_safe_probe_status=passed")

    if args.direct_only:
        return

    admin_token = registration.login(args.base_url, registration.read_env(args.env_file))
    server = virtual_server(args.base_url, admin_token, args.server_name)
    virtual_url = f"{args.base_url.rstrip('/')}/servers/{server['id']}/mcp/"
    probe_token_id = ""
    try:
        probe_token_id, probe_token = create_probe_token(args.base_url, admin_token, server["id"])
        virtual_names = await list_tools(virtual_url, headers={"Authorization": f"Bearer {probe_token}"})
        print(f"virtual_url={virtual_url}")
        print(f"probe_token_id={probe_token_id}")
        print(f"virtual_tool_count={len(virtual_names)}")
        for name in virtual_names:
            print(f"virtual_tool={name}")
        virtual_probe_tool = await call_resolve_library(virtual_url, headers={"Authorization": f"Bearer {probe_token}"})
        print(f"virtual_safe_probe_tool={virtual_probe_tool}")
        print("virtual_safe_probe_status=passed")
    finally:
        if probe_token_id:
            revoke_probe_token(args.base_url, admin_token, probe_token_id)
            print(f"probe_token_revoked={probe_token_id}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--direct-url", default=DEFAULT_DIRECT_URL)
    parser.add_argument("--base-url", default=registration.DEFAULT_GATEWAY_BASE)
    parser.add_argument("--env-file", type=Path, default=registration.DEFAULT_ENV_FILE)
    parser.add_argument("--server-name", default=registration.SERVER_NAME)
    parser.add_argument("--direct-only", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    anyio.run(main_async, args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
