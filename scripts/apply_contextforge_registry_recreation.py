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
import urllib.request
from pathlib import Path
from typing import Any, Protocol

import contextforge_mcp_wrapper as gateway
import control_plane_registry_discipline as registry_discipline
import plan_contextforge_registry_recreation as planner


SCHEMA_URI = "contextforge://diagnostics/registry-recreation-apply/v1"
VISIBILITY = "public"


class ContextForgeClient(Protocol):
    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        ...

    def items(self, path: str) -> list[dict[str, Any]]:
        ...


class HttpContextForgeClient:
    def __init__(self, token: str, *, base_url: str | None = None):
        self.token = token
        self.base_url = base_url.rstrip("/") if base_url else None

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        registry_discipline.assert_public_contextforge_api_path(method, path)
        try:
            if self.base_url:
                return self._request_target(method, path, body=body)
            return gateway._request(method, path, token=self.token, body=body)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            raise RuntimeError(f"{method} {path} failed: HTTP {exc.code} {exc.reason}: {detail}") from exc

    def items(self, path: str) -> list[dict[str, Any]]:
        return gateway._items(self.request("GET", path))

    def _request_target(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        headers = {"Accept": "application/json"}
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        headers["Authorization"] = f"Bearer {self.token}"
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            headers=headers,
            method=method,
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = response.read()
        return json.loads(payload) if payload else None


def load_default_client() -> HttpContextForgeClient:
    config = gateway._read_env(gateway.CONFIG_ENV)
    token = gateway._token(config["PLATFORM_ADMIN_EMAIL"], config["PLATFORM_ADMIN_PASSWORD"])
    return HttpContextForgeClient(token)


def read_target_env(path: Path) -> dict[str, str]:
    return gateway._read_env(path)


def target_login_token(base_url: str, email: str, password: str) -> str:
    for login_path in ("/auth/login", "/auth/email/login"):
        try:
            payload = _target_request(
                "POST",
                base_url,
                login_path,
                body={"email": email, "password": password},
            )
        except urllib.error.HTTPError as exc:
            if exc.code in {404, 405}:
                continue
            raise
        token = payload.get("access_token") if isinstance(payload, dict) else None
        if isinstance(token, str) and token:
            return token
    raise RuntimeError(f"ContextForge login did not return an access token for {base_url.rstrip('/')}")


def _target_request(method: str, base_url: str, path: str, body: dict[str, Any] | None = None) -> Any:
    headers = {"Accept": "application/json"}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=data,
        headers=headers,
        method=method,
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = response.read()
    return json.loads(payload) if payload else None


def load_target_client(base_url: str, env_file: Path) -> HttpContextForgeClient:
    config = read_target_env(env_file)
    email = config.get("PLATFORM_ADMIN_EMAIL")
    password = config.get("PLATFORM_ADMIN_PASSWORD")
    if not email or not password:
        raise RuntimeError(f"missing PLATFORM_ADMIN_EMAIL or PLATFORM_ADMIN_PASSWORD in {env_file}")
    return HttpContextForgeClient(target_login_token(base_url, email, password), base_url=base_url)


def by_name(rows: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    for row in rows:
        if row.get("name") == name:
            return row
    return None


def by_url(rows: list[dict[str, Any]], url: str) -> dict[str, Any] | None:
    for row in rows:
        if row.get("url") == url:
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
    result = {
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
    if "docker_successor_profile" in service:
        result["docker_successor_profile"] = service["docker_successor_profile"]
    return result


def load_docker_profile(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        str(service["slug"]): service
        for service in data.get("services", [])
        if isinstance(service, dict) and isinstance(service.get("slug"), str)
    }


def apply_docker_profile(plan: dict[str, Any], profile_path: Path | None) -> dict[str, Any]:
    profile = load_docker_profile(profile_path)
    if not profile:
        return plan
    for service in plan["services"]:
        profile_service = profile.get(service["slug"])
        if not profile_service:
            continue
        target_url = profile_service.get("target_upstream_url")
        if isinstance(target_url, str) and target_url:
            service["url"] = target_url
            service["operations"][0]["payload"]["url"] = target_url
        service["docker_successor_profile"] = {
            key: profile_service.get(key)
            for key in (
                "locality",
                "approval_state",
                "approval_blocked",
                "docker_projection_required",
                "unsafe_to_reuse_live_default",
            )
        }
    return plan


def apply_service(service: dict[str, Any], client: ContextForgeClient, *, wait_attempts: int = 12) -> dict[str, Any]:
    gateway_name = service["gateway_name"]
    gateway_body = gateway_payload(service)
    gateways = client.items("/gateways?include_inactive=true&limit=1000")
    existing_gateway = by_name(gateways, gateway_name)
    gateway_match = "name"
    if not existing_gateway:
        existing_gateway = by_url(gateways, str(gateway_body["url"]))
        gateway_match = "url"
    if existing_gateway:
        gateway_row = client.request("PUT", f"/gateways/{row_id(existing_gateway)}", gateway_body)
        gateway_action = "updated" if gateway_match == "name" else "updated_from_url_match"
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
    docker_migration_plan: Path | None = None,
    slugs: set[str] | None = None,
    client: ContextForgeClient | None = None,
    base_url: str | None = None,
    env_file: Path | None = None,
) -> dict[str, Any]:
    plan = apply_docker_profile(
        planner.build_plan(manifests_root=manifests_root, export_path=export_path),
        docker_migration_plan,
    )
    services = eligible_services(plan, slugs)
    if apply and client is None:
        client = load_target_client(base_url, env_file) if base_url and env_file else load_default_client()
    results = [apply_service(service, client) if apply and client else plan_service(service) for service in services]
    return {
        "schema_uri": SCHEMA_URI,
        "registry_mutation_discipline": registry_discipline.registry_mutation_discipline(
            owner="apply_contextforge_registry_recreation",
            operations=[
                {"entity": "gateway", "operation": "upsert", "authority": "name+url"},
                {"entity": "gateway_tools", "operation": "refresh", "authority": "gateway API readback"},
                {"entity": "server", "operation": "upsert_associations", "authority": "server name + refreshed tool names"},
            ],
        ),
        "mutation_performed": apply,
        "apply_requested": apply,
        "target": {
            "base_url": base_url or gateway.GATEWAY_BASE,
            "env_file": str(env_file or gateway.CONFIG_ENV),
            "env_values_recorded": False,
            "docker_migration_plan": str(docker_migration_plan) if docker_migration_plan else None,
        },
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
    parser.add_argument("--docker-migration-plan", type=Path)
    parser.add_argument("--service", action="append", dest="services", help="Limit to one service slug; repeatable.")
    parser.add_argument("--base-url", help="Target ContextForge base URL for --apply; omit to use wrapper defaults.")
    parser.add_argument("--env-file", type=Path, help="Target env file for --apply; omit to use wrapper defaults.")
    parser.add_argument("--apply", action="store_true", help="Call ContextForge APIs. Omit for dry-run planning.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run(
        apply=args.apply,
        manifests_root=args.manifests_root,
        export_path=args.export_json,
        docker_migration_plan=args.docker_migration_plan,
        slugs=set(args.services or []),
        base_url=args.base_url,
        env_file=args.env_file,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
