#!/usr/bin/env python3
"""Register the ContextForge-scoped Serena MCP backend in ContextForge."""

from __future__ import annotations

import argparse
import sys
import time
import urllib.error
from urllib.parse import urlparse
from typing import Any

import contextforge_mcp_wrapper as gateway


OWNER = "admin@contextforge.dev"
GATEWAY_ID = "6737c3908d3a4bb098d829a5a4e5327f"
SERVER_ID = "c14f033a68f34b9ba26870bfede42cbf"
GATEWAY_NAME = "serena-cf-controlplane-d46fe58a2a20"
SERVER_NAME = "serena_cf_controlplane_d46fe58a2a20_server"
GATEWAY_URL = "http://localhost:9108/mcp"
EXCLUDED_ORIGINAL_TOOL_NAMES = {"activate_project"}
LIVE_REGISTRATION_APPROVAL = "--allow-live-serena-registration"


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


def tag_values(values: Any) -> set[str]:
    tags: set[str] = set()
    if not isinstance(values, list):
        return tags
    for value in values:
        if isinstance(value, str):
            tags.add(value)
        elif isinstance(value, dict):
            for key in ("id", "name", "label"):
                if value.get(key):
                    tags.add(str(value[key]))
    return tags


def normalized_endpoint(url: str) -> tuple[str, int | None, str]:
    parsed = urlparse(url)
    host = parsed.hostname or ""
    if host in {"localhost", "127.0.0.1"}:
        host = "127.0.0.1"
    return host, parsed.port, parsed.path.rstrip("/")


def gateway_matches(row: dict[str, Any]) -> bool:
    name = str(row.get("name") or "")
    slug = str(row.get("slug") or "")
    if row.get("id") == GATEWAY_ID:
        return True
    if name == GATEWAY_NAME or slug == GATEWAY_NAME:
        return True
    url = str(row.get("url") or "")
    return normalized_endpoint(url) == normalized_endpoint(GATEWAY_URL)


def server_matches(row: dict[str, Any]) -> bool:
    name = str(row.get("name") or "")
    if row.get("id") == SERVER_ID:
        return True
    if name == SERVER_NAME:
        return True
    tags = tag_values(row.get("tags"))
    description = str(row.get("description") or "").lower()
    return "serena" in tags and "contextforge operator repository" in description


def unique_match(rows: list[dict[str, Any]], predicate: Any, label: str) -> dict[str, Any] | None:
    matches = [row for row in rows if predicate(row)]
    if len(matches) > 1:
        names = ", ".join(str(row.get("name") or row.get("id")) for row in matches)
        raise RuntimeError(f"ambiguous {label} matches: {names}")
    return matches[0] if matches else None


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
    existing = unique_match(api_items("/gateways?include_inactive=true&limit=1000", token), gateway_matches, "Serena gateway")
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
            and original_tool_name(tool) not in EXCLUDED_ORIGINAL_TOOL_NAMES
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
            str(resource.get("uri") or "").startswith("serena-cf-controlplane-d46fe58a2a20://tools/")
            or str(resource.get("uri") or "") == "contextforge://cf-controlplane/serena-project-instance-guidance/v15"
        )
    )


def prompt_ids(token: str) -> list[str]:
    prompts = api_items("/prompts?include_inactive=true&limit=1000", token)
    return sorted(
        prompt["id"]
        for prompt in prompts
        if isinstance(prompt.get("id"), str)
        and str(prompt.get("customName") or prompt.get("custom_name") or prompt.get("name") or "")
        == "serena_project_instance_guidance"
    )


def original_tool_name(tool: dict[str, Any]) -> str:
    original = tool.get("originalName") or tool.get("original_name")
    if original:
        return str(original)
    name = str(tool.get("name") or "")
    if name.startswith(f"{GATEWAY_NAME}-"):
        return name[len(GATEWAY_NAME) + 1 :].replace("-", "_")
    return name.replace("-", "_")


def ensure_server(token: str, tool_ids: list[str]) -> dict[str, Any]:
    existing = unique_match(api_items("/servers?include_inactive=true&limit=1000", token), server_matches, "Serena virtual server")
    body = server_body(tool_ids)
    if existing:
        update_body = {
            "name": body["name"],
            "description": body["description"],
            "associatedTools": tool_ids,
            "associatedResources": resource_ids(token),
            "associatedPrompts": prompt_ids(token),
            "associatedA2aAgents": existing.get("associatedA2aAgents") or [],
            "tags": body["tags"],
            "ownerEmail": OWNER,
            "visibility": "public",
        }
        return api_request("PUT", f"/servers/{existing['id']}", token=token, body=update_body)
    return api_request("POST", "/servers", token=token, body={"server": body, "visibility": "public"})


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        LIVE_REGISTRATION_APPROVAL,
        action="store_true",
        help=(
            "Explicitly allow this compatibility helper to mutate the legacy/live "
            "Serena ContextForge gateway/server records. Use only after a separate "
            "operator approval for that live surface."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.allow_live_serena_registration:
        print(
            "Refusing to mutate live ContextForge Serena registration. "
            f"This helper is non-mutating by default; rerun with "
            f"{LIVE_REGISTRATION_APPROVAL} only after explicit operator approval.",
            file=sys.stderr,
        )
        return 2

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
