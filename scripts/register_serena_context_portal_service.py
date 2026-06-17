#!/usr/bin/env python3
"""Register the ContextForge-scoped Serena MCP backend in ContextForge."""

from __future__ import annotations

import sys
import time
import urllib.error
from typing import Any

import contextforge_mcp_wrapper as gateway


OWNER = "admin@contextforge.dev"
GATEWAY_NAME = "serena-context-portal"
SERVER_NAME = "serena_context_portal_server"
GATEWAY_URL = "http://localhost:9108/mcp"
EXCLUDED_ORIGINAL_TOOL_NAMES = {"activate_project"}


def api_request(method: str, path: str, *, token: str, body: dict[str, Any] | None = None) -> Any:
    try:
        return gateway._request(method, path, token=token, body=body)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise RuntimeError(f"{method} {path} failed: HTTP {exc.code} {exc.reason}: {detail}") from exc


def api_items(path: str, token: str) -> list[dict[str, Any]]:
    return gateway._items(api_request("GET", path, token=token))


def by_name(rows: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    for row in rows:
        if row.get("name") == name:
            return row
    return None


def gateway_body() -> dict[str, Any]:
    return {
        "name": GATEWAY_NAME,
        "url": GATEWAY_URL,
        "description": "Serena MCP code-intelligence backend scoped to the active cf-controlplane repository root.",
        "transport": "STREAMABLEHTTP",
        "tags": ["contextforge", "serena", "cf-controlplane", "local-backend"],
        "visibility": "public",
        "owner_email": OWNER,
        "gateway_mode": "cache",
    }


def ensure_gateway(token: str) -> dict[str, Any]:
    existing = by_name(api_items("/gateways?include_inactive=true&limit=1000", token), GATEWAY_NAME)
    body = gateway_body()
    if not existing:
        return api_request("POST", "/gateways", token=token, body=body)

    update_body = dict(body)
    update_body["enabled"] = True
    return api_request("PUT", f"/gateways/{existing['id']}", token=token, body=update_body)


def tools_for_gateway(token: str, gateway_id: str) -> list[dict[str, Any]]:
    tools = api_items("/tools?include_inactive=true&limit=1000", token)
    return sorted(
        [
            tool
            for tool in tools
            if (tool.get("gatewayId") == gateway_id or tool.get("gateway_id") == gateway_id)
            and tool.get("originalName") not in EXCLUDED_ORIGINAL_TOOL_NAMES
        ],
        key=lambda tool: tool["name"],
    )


def refresh_and_wait_for_tools(token: str, gateway_id: str) -> list[dict[str, Any]]:
    api_request("POST", f"/gateways/{gateway_id}/tools/refresh", token=token)
    for _ in range(24):
        tools = tools_for_gateway(token, gateway_id)
        if tools:
            return tools
        time.sleep(1)
    raise RuntimeError(f"gateway {gateway_id} did not expose any tools after refresh")


def server_body(tool_ids: list[str]) -> dict[str, Any]:
    return {
        "name": SERVER_NAME,
        "description": "Virtual server exposing Serena for the ContextForge operator repository.",
        "associated_tools": tool_ids,
        "tags": ["contextforge", "serena", "cf-controlplane"],
        "owner_email": OWNER,
        "visibility": "public",
    }


def resource_ids(token: str) -> list[str]:
    resources = api_items("/resources?include_inactive=true&limit=1000", token)
    return sorted(
        resource["id"]
        for resource in resources
        if isinstance(resource.get("id"), str)
        and (
            str(resource.get("uri") or "").startswith("serena-context-portal://tools/")
            or "serena" in (resource.get("tags") or [])
        )
    )


def prompt_ids(token: str) -> list[str]:
    prompts = api_items("/prompts?include_inactive=true&limit=1000", token)
    return sorted(
        prompt["id"]
        for prompt in prompts
        if isinstance(prompt.get("id"), str)
        and (
            str(prompt.get("customName") or prompt.get("custom_name") or prompt.get("name") or "").startswith("serena_")
            or "serena" in (prompt.get("tags") or [])
        )
    )


def ensure_server(token: str, tool_ids: list[str]) -> dict[str, Any]:
    existing = by_name(api_items("/servers?include_inactive=true&limit=1000", token), SERVER_NAME)
    body = server_body(tool_ids)
    if existing:
        update_body = {
            "associatedTools": tool_ids,
            "associatedResources": existing.get("associatedResources") or existing.get("associatedResourceIds") or resource_ids(token),
            "associatedPrompts": existing.get("associatedPrompts") or existing.get("associatedPromptIds") or prompt_ids(token),
            "associatedA2aAgents": existing.get("associatedA2aAgents") or [],
            "ownerEmail": OWNER,
            "visibility": "public",
        }
        return api_request("PUT", f"/servers/{existing['id']}", token=token, body=update_body)
    return api_request("POST", "/servers", token=token, body={"server": body, "visibility": "public"})


def main() -> int:
    config = gateway._read_env(gateway.CONFIG_ENV)
    token = gateway._token(config["PLATFORM_ADMIN_EMAIL"], config["PLATFORM_ADMIN_PASSWORD"])

    gateway_row = ensure_gateway(token)
    gateway_id = gateway_row["id"]
    tools = refresh_and_wait_for_tools(token, gateway_id)
    server = ensure_server(token, [tool["id"] for tool in tools])

    print(f"gateway_id={gateway_id}")
    print(f"server_id={server['id']}")
    print(f"tool_count={len(tools)}")
    for tool in tools:
        print(tool["name"])
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
