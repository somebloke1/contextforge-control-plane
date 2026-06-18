#!/usr/bin/env python3
"""Apply or dry-run manifest-driven ContextForge registry recreation.

Default mode is a dry run. `--apply` is required before this script calls
ContextForge APIs. The helper only covers services whose manifests are
classified by the planner as `needs_manifest_driven_api_recreation`.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
from pathlib import Path
from typing import Any, Protocol

import contextforge_mcp_wrapper as gateway
import plan_contextforge_registry_recreation as planner


SCHEMA_URI = "contextforge://diagnostics/registry-recreation-apply/v1"
VISIBILITY = "public"


class ContextForgeClient(Protocol):
    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        ...

    def items(self, path: str) -> list[dict[str, Any]]:
        ...


class HttpContextForgeClient:
    def __init__(self, token: str):
        self.token = token

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        try:
            return gateway._request(method, path, token=self.token, body=body)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            raise RuntimeError(f"{method} {path} failed: HTTP {exc.code} {exc.reason}: {detail}") from exc

    def items(self, path: str) -> list[dict[str, Any]]:
        return gateway._items(self.request("GET", path))


def load_default_client() -> HttpContextForgeClient:
    config = gateway._read_env(gateway.CONFIG_ENV)
    token = gateway._token(config["PLATFORM_ADMIN_EMAIL"], config["PLATFORM_ADMIN_PASSWORD"])
    return HttpContextForgeClient(token)


def by_name(rows: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    for row in rows:
        if row.get("name") == name:
            return row
    return None


def row_id(row: dict[str, Any]) -> str:
    value = row.get("id")
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"row missing string id: {row}")
    return value


def gateway_payload(service: dict[str, Any]) -> dict[str, Any]:
    operation = service["operations"][0]["payload"]
    return {
        "name": operation["name"],
        "url": operation["url"],
        "description": f"Canonical ContextForge gateway for {service['slug']}.",
        "transport": operation["transport"],
        "tags": operation["tags"],
        "visibility": operation["visibility"],
        "owner_email": operation["owner_email"],
        "gateway_mode": operation["gateway_mode"],
    }


def server_payload(service: dict[str, Any], tool_ids: list[str]) -> dict[str, Any]:
    operation = service["operations"][1]["payload"]
    return {
        "name": operation["name"],
        "description": operation["description"],
        "associated_tools": tool_ids,
        "tags": operation["tags"],
        "owner_email": operation["owner_email"],
        "visibility": operation["visibility"],
    }


def tool_gateway_id(tool: dict[str, Any]) -> str | None:
    value = tool.get("gatewayId") or tool.get("gateway_id")
    return str(value) if value else None


def associated_ids(existing: dict[str, Any], camel: str, snake: str) -> list[str]:
    values = existing.get(camel) or existing.get(snake) or []
    return [str(value) for value in values if isinstance(value, str)]


def plan_service(service: dict[str, Any]) -> dict[str, Any]:
    return {
        "slug": service["slug"],
        "classification": service["classification"],
        "mutation_performed": False,
        "operations": [
            {"operation": "upsert_gateway", "match_by": ["name", "url"], "payload": gateway_payload(service)},
            {"operation": "refresh_gateway_tools"},
            {
                "operation": "upsert_server",
                "match_by": ["name"],
                "server_name": service["server_name"],
                "preserve_existing_associations": ["associatedResources", "associatedPrompts", "associatedA2aAgents"],
                "expected_tool_names": service["export_dependency_tool_names"] or service["expected_tool_names"],
            },
        ],
    }


def apply_service(service: dict[str, Any], client: ContextForgeClient, *, wait_attempts: int = 12) -> dict[str, Any]:
    gateway_name = service["gateway_name"]
    gateway_body = gateway_payload(service)
    gateways = client.items("/gateways?include_inactive=true&limit=1000")
    existing_gateway = by_name(gateways, gateway_name)
    if existing_gateway:
        gateway_row = client.request("PUT", f"/gateways/{row_id(existing_gateway)}", gateway_body)
        gateway_action = "updated"
    else:
        gateway_row = client.request("POST", "/gateways", gateway_body)
        gateway_action = "created"
    gateway_id = row_id(gateway_row)

    client.request("POST", f"/gateways/{gateway_id}/tools/refresh")
    tools: list[dict[str, Any]] = []
    for attempt in range(wait_attempts):
        tools = sorted(
            [tool for tool in client.items("/tools?include_inactive=true&limit=1000") if tool_gateway_id(tool) == gateway_id],
            key=lambda tool: str(tool.get("name", "")),
        )
        if tools:
            break
        if attempt + 1 < wait_attempts:
            time.sleep(1)
    if not tools:
        raise RuntimeError(f"gateway {gateway_name} ({gateway_id}) did not expose tools after refresh")

    tool_ids = [row_id(tool) for tool in tools]
    servers = client.items("/servers?include_inactive=true&limit=1000")
    existing_server = by_name(servers, service["server_name"])
    if existing_server:
        payload = {
            "associatedTools": tool_ids,
            "associatedResources": associated_ids(existing_server, "associatedResources", "associatedResourceIds"),
            "associatedPrompts": associated_ids(existing_server, "associatedPrompts", "associatedPromptIds"),
            "associatedA2aAgents": associated_ids(existing_server, "associatedA2aAgents", "associatedA2aAgentIds"),
            "ownerEmail": planner.OWNER,
            "visibility": VISIBILITY,
        }
        server_row = client.request("PUT", f"/servers/{row_id(existing_server)}", payload)
        server_action = "updated"
    else:
        server_row = client.request("POST", "/servers", {"server": server_payload(service, tool_ids), "visibility": VISIBILITY})
        server_action = "created"

    return {
        "slug": service["slug"],
        "mutation_performed": True,
        "gateway": {"action": gateway_action, "id": gateway_id, "name": gateway_name},
        "server": {"action": server_action, "id": row_id(server_row), "name": service["server_name"]},
        "tool_count": len(tools),
        "tool_names": [str(tool.get("name")) for tool in tools],
    }


def eligible_services(plan: dict[str, Any], requested_slugs: set[str] | None = None) -> list[dict[str, Any]]:
    services = [
        service
        for service in plan["services"]
        if service["classification"] == "needs_manifest_driven_api_recreation"
    ]
    if requested_slugs:
        services = [service for service in services if service["slug"] in requested_slugs]
    return services


def run(
    *,
    apply: bool,
    manifests_root: Path = planner.SERVER_INSTANCES,
    export_path: Path | None = None,
    slugs: set[str] | None = None,
    client: ContextForgeClient | None = None,
) -> dict[str, Any]:
    plan = planner.build_plan(manifests_root=manifests_root, export_path=export_path)
    services = eligible_services(plan, slugs)
    if apply and client is None:
        client = load_default_client()
    results = [apply_service(service, client) if apply and client else plan_service(service) for service in services]
    return {
        "schema_uri": SCHEMA_URI,
        "mutation_performed": apply,
        "apply_requested": apply,
        "service_count": len(results),
        "services": results,
        "non_actions": []
        if apply
        else [
            "dry-run; no ContextForge API calls",
            "dry-run; no database reads or writes",
            "dry-run; no service, process, systemd, Docker, or client mutation",
            "dry-run; no env-file contents read",
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifests-root", type=Path, default=planner.SERVER_INSTANCES)
    parser.add_argument("--export-json", type=Path)
    parser.add_argument("--service", action="append", dest="services", help="Limit to one service slug; repeatable.")
    parser.add_argument("--apply", action="store_true", help="Call ContextForge APIs. Omit for dry-run planning.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run(
        apply=args.apply,
        manifests_root=args.manifests_root,
        export_path=args.export_json,
        slugs=set(args.services or []),
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
