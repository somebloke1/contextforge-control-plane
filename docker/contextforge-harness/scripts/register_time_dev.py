#!/usr/bin/env python3
"""Register the dev-Docker Time transceiver with the harness gateway."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILE = ROOT / "env" / "contextforge.env"
OWNER = "admin@contextforge-harness.dev"
GATEWAY_NAME = "time-dev-docker"
SERVER_NAME = "time_dev_docker_server"
DEFAULT_GATEWAY_BASE = "http://127.0.0.1:4445"
DEFAULT_UPSTREAM_URL = "http://time-transceiver:9209/mcp"


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value.strip().strip("\"'")
    return values


def request_json(
    method: str,
    base_url: str,
    path: str,
    *,
    token: str | None = None,
    body: dict[str, Any] | None = None,
) -> Any:
    headers = {"Accept": "application/json"}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise RuntimeError(f"{method} {path} failed: HTTP {exc.code} {exc.reason}: {detail}") from exc
    return json.loads(payload) if payload else None


def items(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        return data["items"]
    if isinstance(data, list):
        return data
    return []


def by_name(rows: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    for row in rows:
        if row.get("name") == name:
            return row
    return None


def login(base_url: str, env: dict[str, str]) -> str:
    email = env.get("PLATFORM_ADMIN_EMAIL")
    password = env.get("PLATFORM_ADMIN_PASSWORD")
    if not email or not password:
        raise RuntimeError("missing PLATFORM_ADMIN_EMAIL or PLATFORM_ADMIN_PASSWORD in harness env")
    response = request_json(
        "POST",
        base_url,
        "/auth/login",
        body={"email": email, "password": password},
    )
    token = response.get("access_token") if isinstance(response, dict) else None
    if not isinstance(token, str) or not token:
        raise RuntimeError("ContextForge login did not return an access token")
    return token


def gateway_body(upstream_url: str) -> dict[str, Any]:
    return {
        "name": GATEWAY_NAME,
        "url": upstream_url,
        "description": "Dev-Docker Time MCP development foil exposed through stock mcpgateway.translate.",
        "transport": "STREAMABLEHTTP",
        "tags": ["contextforge", "dev-docker", "time", "development-foil"],
        "visibility": "public",
        "owner_email": OWNER,
        "gateway_mode": "cache",
    }


def ensure_gateway(base_url: str, token: str, upstream_url: str) -> dict[str, Any]:
    existing = by_name(items(request_json("GET", base_url, "/gateways?include_inactive=true&limit=1000", token=token)), GATEWAY_NAME)
    body = gateway_body(upstream_url)
    if existing:
        if existing.get("url") == upstream_url and existing.get("transport") == "STREAMABLEHTTP":
            return existing
        return request_json("PUT", base_url, f"/gateways/{existing['id']}", token=token, body=body)
    return request_json("POST", base_url, "/gateways", token=token, body=body)


def tools_for_gateway(base_url: str, token: str, gateway_id: str) -> list[dict[str, Any]]:
    tools = items(request_json("GET", base_url, "/tools?include_inactive=true&limit=1000", token=token))
    return sorted(
        [
            tool
            for tool in tools
            if tool.get("gatewayId") == gateway_id or tool.get("gateway_id") == gateway_id
        ],
        key=lambda tool: str(tool.get("name") or ""),
    )


def refresh_and_wait_for_tools(base_url: str, token: str, gateway_id: str) -> list[dict[str, Any]]:
    existing = tools_for_gateway(base_url, token, gateway_id)
    if existing:
        return existing
    request_json("POST", base_url, f"/gateways/{gateway_id}/tools/refresh", token=token)
    for _ in range(20):
        tools = tools_for_gateway(base_url, token, gateway_id)
        if tools:
            return tools
        time.sleep(1)
    raise RuntimeError(f"gateway {gateway_id} did not expose tools after refresh")


def server_body(tool_ids: list[str]) -> dict[str, Any]:
    return {
        "name": SERVER_NAME,
        "description": "Dev-Docker virtual server exposing the Time onboarding development foil.",
        "associated_tools": tool_ids,
        "tags": ["contextforge", "dev-docker", "time", "development-foil"],
        "owner_email": OWNER,
        "visibility": "public",
    }


def ensure_server(base_url: str, token: str, tool_ids: list[str]) -> dict[str, Any]:
    existing = by_name(items(request_json("GET", base_url, "/servers?include_inactive=true&limit=1000", token=token)), SERVER_NAME)
    body = server_body(tool_ids)
    if existing:
        update_body = {
            "associatedTools": tool_ids,
            "associatedResources": existing.get("associatedResources") or existing.get("associatedResourceIds") or [],
            "associatedPrompts": existing.get("associatedPrompts") or existing.get("associatedPromptIds") or [],
            "associatedA2aAgents": existing.get("associatedA2aAgents") or [],
            "ownerEmail": OWNER,
            "visibility": "public",
        }
        return request_json("PUT", base_url, f"/servers/{existing['id']}", token=token, body=update_body)
    return request_json("POST", base_url, "/servers", token=token, body={"server": body, "visibility": "public"})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.environ.get("CONTEXTFORGE_HARNESS_BASE_URL", DEFAULT_GATEWAY_BASE))
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--upstream-url", default=os.environ.get("TIME_TRANSCEIVER_URL", DEFAULT_UPSTREAM_URL))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not args.env_file.exists():
        raise RuntimeError(f"missing {args.env_file}; run docker/contextforge-harness/scripts/init-env.sh first")
    token = login(args.base_url, read_env(args.env_file))
    gateway = ensure_gateway(args.base_url, token, args.upstream_url)
    gateway_id = gateway["id"]
    tools = refresh_and_wait_for_tools(args.base_url, token, gateway_id)
    server = ensure_server(args.base_url, token, [tool["id"] for tool in tools])

    print(f"gateway_name={GATEWAY_NAME}")
    print(f"gateway_id={gateway_id}")
    print(f"gateway_url={args.upstream_url}")
    print(f"server_name={SERVER_NAME}")
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
