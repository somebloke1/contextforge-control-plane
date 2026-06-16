#!/usr/bin/env python3
"""Fixture-backed dry run for the repo-owned Pi ContextForge shim."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping

import control_plane_project_state as project_state


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "tool"


def approved_pi_services(state: Mapping[str, Any]) -> list[dict[str, Any]]:
    services: list[dict[str, Any]] = []
    raw_services = state.get("services") if isinstance(state.get("services"), Mapping) else {}
    for key, raw_service in raw_services.items():
        if not isinstance(raw_service, Mapping):
            continue
        target_clients = raw_service.get("target_clients") if isinstance(raw_service.get("target_clients"), Mapping) else {}
        pi = target_clients.get("pi") if isinstance(target_clients.get("pi"), Mapping) else None
        if not pi or str(pi.get("status") or "") == "blocked":
            continue
        verification_layers = raw_service.get("verification_layers") if isinstance(raw_service.get("verification_layers"), Mapping) else {}
        tool_policy = verification_layers.get("tool_policy") if isinstance(verification_layers.get("tool_policy"), Mapping) else {}
        policy = tool_policy.get("policy") if isinstance(tool_policy.get("policy"), Mapping) else {}
        services.append(
            {
                "service_binding": str(raw_service.get("service_binding") or key),
                "service_family": str(raw_service.get("service_family") or key),
                "service_identity_id": str((raw_service.get("x_service_identity") or {}).get("id") or raw_service.get("x_service_identity_id") or ""),
                "contextforge_server_id": str(raw_service.get("x_contextforge_server_id") or ""),
                "descriptor_digest": str(raw_service.get("x_descriptor_digest") or (raw_service.get("x_service_identity") or {}).get("descriptor_digest") or ""),
                "virtual_server": str(pi.get("virtual_server") or raw_service.get("virtual_server") or ""),
                "pi_tool_prefix": slug(str(pi.get("pi_tool_prefix") or pi.get("alias") or raw_service.get("service_family") or key)),
                "validation_status": str(pi.get("validation_status") or "pending"),
                "safe_operations": [slug(str(item)) for item in policy.get("safe_operations") or []],
            }
        )
    return sorted(services, key=lambda item: item["service_binding"])


def blocked_by_default(service: Mapping[str, Any], tool_name: str) -> bool:
    service_key = str(service.get("service_binding") or "").lower()
    tool_key = tool_name.lower()
    mutating = ("add-", "create-", "delete-", "fork-", "merge-", "open-session", "push-", "send-", "update-", "write-")
    return service_key.startswith(("ssh-tmux:", "github:")) and any(pattern in tool_key for pattern in mutating)


def unique_name(base: str, seen: set[str]) -> str:
    clipped = base[:72]
    if clipped not in seen:
        seen.add(clipped)
        return clipped
    for index in range(2, 1000):
        candidate = f"{clipped[:66]}_{index}"
        if candidate not in seen:
            seen.add(candidate)
            return candidate
    raise RuntimeError(f"could not allocate unique tool name for {base}")


def stable_route_name(service: Mapping[str, Any], mcp_name: str, *, route_names: dict[str, str], seen: set[str]) -> str:
    service_identity = (
        str(service.get("contextforge_server_id") or "")
        or str(service.get("service_identity_id") or "")
        or str(service.get("descriptor_digest") or "")
        or str(service.get("service_binding") or "")
    )
    route_key = "\0".join(["v2", service_identity, mcp_name])
    if route_key not in route_names:
        route_names[route_key] = unique_name(f"cf_{service['pi_tool_prefix']}_{service_identity_segment(service_identity)}__{slug(mcp_name)}", seen)
    return route_names[route_key]


def service_identity_segment(identity: str) -> str:
    digest = identity.removeprefix("sha256:").removeprefix("contextforge-service-")
    return "s" + (slug(digest).replace("-", "")[:10] or "service")


def validation_signals(services: list[dict[str, Any]], tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    for service in services:
        service_tools = [tool for tool in tools if tool["service_binding"] == service["service_binding"]]
        safe_operations = list(service.get("safe_operations") or [])
        candidate = next(
            (
                tool
                for tool in service_tools
                if not tool["blocked_by_default"]
                and any(operation in slug(str(tool["mcp_name"])) for operation in safe_operations)
            ),
            None,
        )
        if candidate:
            signals.append(
                {
                    "service_binding": service["service_binding"],
                    "service_identity_id": service["service_identity_id"],
                    "status": "safe_probe_available",
                    "pi_name": candidate["pi_name"],
                    "mcp_name": candidate["mcp_name"],
                    "safe_probe_id": next(operation for operation in safe_operations if operation in slug(str(candidate["mcp_name"]))),
                }
            )
        else:
            if not service_tools:
                reason = "no_pi_tools_registered"
            elif not safe_operations:
                reason = "no_safe_validation_policy"
            else:
                reason = "no_matching_safe_pi_tool"
            signals.append(
                {
                    "service_binding": service["service_binding"],
                    "service_identity_id": service["service_identity_id"],
                    "status": "skipped",
                    "skipped_reason": reason,
                    "safe_operations": safe_operations,
                }
            )
    return signals


def load_tool_fixture(path: Path) -> dict[str, list[dict[str, Any]]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise ValueError("tool fixture must map virtual server names to tool arrays")
    output: dict[str, list[dict[str, Any]]] = {}
    for virtual_server, tools in data.items():
        if not isinstance(tools, list):
            raise ValueError(f"tool fixture value must be a list: {virtual_server}")
        output[str(virtual_server)] = [tool for tool in tools if isinstance(tool, dict)]
    return output


def dry_run(project_root: str | Path, tool_fixture: Mapping[str, list[dict[str, Any]]]) -> dict[str, Any]:
    root = project_state.validate_project_root(project_root, require_workspace=False)
    state = project_state.load_state(root) or project_state.default_state(root)
    services = approved_pi_services(state)
    seen: set[str] = set()
    route_names: dict[str, str] = {}
    tools: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for service in services:
        virtual_server = service["virtual_server"]
        if not virtual_server:
            skipped.append({"service_binding": service["service_binding"], "reason": "missing virtual_server"})
            continue
        for tool in tool_fixture.get(virtual_server, []):
            mcp_name = str(tool.get("name") or "")
            if not mcp_name:
                continue
            tools.append(
                {
                    "pi_name": stable_route_name(service, mcp_name, route_names=route_names, seen=seen),
                    "mcp_name": mcp_name,
                    "service_binding": service["service_binding"],
                    "virtual_server": virtual_server,
                    "blocked_by_default": blocked_by_default(service, mcp_name),
                }
            )
    return {
        "project_root": str(root),
        "state_path": str(project_state.project_state_path(root)),
        "services": services,
        "registered_tools": tools,
        "validation_signals": validation_signals(services, tools),
        "skipped": skipped,
        "target_client_visible": bool(tools),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dry-run Pi ContextForge shim registration from project state and a tools/list fixture.")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--tool-fixture", required=True, type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(dry_run(args.project_root, load_tool_fixture(args.tool_fixture)), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
