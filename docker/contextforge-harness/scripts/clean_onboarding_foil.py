#!/usr/bin/env python3
"""Inspect or clean development ContextForge artifacts for onboarding foils."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import register_time_dev as registration


SCHEMA_URI = "contextforge://diagnostics/onboarding-foil-cleanup/v1"
DEFAULT_GATEWAY_BASE = registration.DEFAULT_GATEWAY_BASE
DEFAULT_ENV_FILE = registration.DEFAULT_ENV_FILE
READ_ENDPOINTS = {
    "gateways": "/gateways?include_inactive=true&limit=1000",
    "tools": "/tools?include_inactive=true&limit=1000",
    "servers": "/servers?include_inactive=true&limit=1000",
    "prompts": "/prompts?include_inactive=true&limit=1000",
    "resources": "/resources?include_inactive=true&limit=1000",
}

FOILS = {
    "time": {
        "service_binding": "time:canonical",
        "gateway_names": ["time-dev-docker", "time"],
        "server_names": ["time_dev_docker_server", "time_server"],
        "tool_name_prefixes": ["time-dev-docker-", "time-"],
        "prompt_name_prefixes": ["time-", "time_"],
        "resource_uri_prefixes": ["contextforge://time/", "contextforge://services/time/"],
        "required_clean_scopes": [
            "mcp_service",
            "service_tools",
            "virtual_server",
            "service_bound_prompts",
            "service_bound_resources",
        ],
    }
}


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def item_id(row: dict[str, Any]) -> str:
    value = row.get("id")
    return str(value) if value is not None else ""


def item_name(row: dict[str, Any]) -> str:
    for key in ("name", "customName", "custom_name", "uri"):
        value = row.get(key)
        if isinstance(value, str) and value:
            return value
    return item_id(row)


def row_values(row: dict[str, Any], *names: str) -> list[str]:
    values: list[str] = []
    for name in names:
        value = row.get(name)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict) and item.get("id") is not None:
                    values.append(str(item["id"]))
                elif item is not None:
                    values.append(str(item))
        elif isinstance(value, dict) and value.get("id") is not None:
            values.append(str(value["id"]))
        elif value is not None:
            values.append(str(value))
    return values


def has_prefix(value: Any, prefixes: list[str]) -> bool:
    if not isinstance(value, str):
        return False
    return any(value.startswith(prefix) for prefix in prefixes)


def read_live(base_url: str, env_file: Path) -> dict[str, list[dict[str, Any]]]:
    if not env_file.exists():
        raise RuntimeError(f"missing {env_file}; run docker/contextforge-harness/scripts/init-env.sh first")
    token = registration.login(base_url, registration.read_env(env_file))
    return {
        key: registration.items(registration.request_json("GET", base_url, path, token=token))
        for key, path in READ_ENDPOINTS.items()
    }


def load_live(path: Path | None, *, base_url: str, env_file: Path) -> dict[str, list[dict[str, Any]]]:
    if path is not None:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return {key: [row for row in payload.get(key, []) if isinstance(row, dict)] for key in READ_ENDPOINTS}
    return read_live(base_url, env_file)


def operation(kind: str, row: dict[str, Any]) -> dict[str, Any]:
    ident = item_id(row)
    plural = {
        "gateway": "gateways",
        "tool": "tools",
        "server": "servers",
        "prompt": "prompts",
        "resource": "resources",
    }[kind]
    return {
        "kind": kind,
        "id": ident,
        "name": item_name(row),
        "method": "DELETE",
        "path": f"/{plural}/{ident}",
    }


def collect_matches(live: dict[str, list[dict[str, Any]]], foil: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    gateway_names = set(foil["gateway_names"])
    server_names = set(foil["server_names"])

    gateways = [row for row in live["gateways"] if row.get("name") in gateway_names]
    gateway_ids = {item_id(row) for row in gateways}

    servers = [row for row in live["servers"] if row.get("name") in server_names]
    server_prompt_ids: set[str] = set()
    server_resource_ids: set[str] = set()
    for server in servers:
        server_prompt_ids.update(row_values(server, "associatedPromptIds", "associatedPrompts", "prompts"))
        server_resource_ids.update(row_values(server, "associatedResourceIds", "associatedResources", "resources"))

    tools = [
        row
        for row in live["tools"]
        if str(row.get("gatewayId") or row.get("gateway_id") or "") in gateway_ids
        or row.get("gatewaySlug") in gateway_names
        or row.get("gateway_slug") in gateway_names
        or has_prefix(row.get("name"), foil["tool_name_prefixes"])
    ]
    prompts = [
        row
        for row in live["prompts"]
        if item_id(row) in server_prompt_ids
        or has_prefix(row.get("name"), foil["prompt_name_prefixes"])
        or has_prefix(row.get("customName"), foil["prompt_name_prefixes"])
        or has_prefix(row.get("custom_name"), foil["prompt_name_prefixes"])
    ]
    resources = [
        row
        for row in live["resources"]
        if item_id(row) in server_resource_ids
        or has_prefix(row.get("uri"), foil["resource_uri_prefixes"])
    ]
    return {
        "mcp_service": gateways,
        "service_tools": tools,
        "virtual_server": servers,
        "service_bound_prompts": prompts,
        "service_bound_resources": resources,
    }


def contextforge_server_readback(live: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    servers: list[dict[str, Any]] = []
    for row in live["servers"]:
        name = row.get("name")
        if not isinstance(name, str) or not name:
            continue
        server = {"name": name}
        if row.get("id") is not None:
            server["id"] = str(row["id"])
        if row.get("enabled") is not None:
            server["enabled"] = row["enabled"]
        servers.append(server)
    return servers


def build_manifest(*, foil_id: str, base_url: str, live: dict[str, list[dict[str, Any]]], apply: bool) -> dict[str, Any]:
    foil = FOILS[foil_id]
    matches = collect_matches(live, foil)
    operations: list[dict[str, Any]] = []
    for scope in ("virtual_server", "service_bound_prompts", "service_bound_resources", "service_tools", "mcp_service"):
        kind = {
            "mcp_service": "gateway",
            "service_tools": "tool",
            "virtual_server": "server",
            "service_bound_prompts": "prompt",
            "service_bound_resources": "resource",
        }[scope]
        for row in matches[scope]:
            operations.append({**operation(kind, row), "scope": scope})

    counts = {scope: len(rows) for scope, rows in matches.items()}
    operation_counts = Counter(op["path"] for op in operations)
    clean = all(counts[scope] == 0 for scope in foil["required_clean_scopes"])
    return {
        "schema_uri": SCHEMA_URI,
        "generated_at": now_iso(),
        "foil": foil_id,
        "service_binding": foil["service_binding"],
        "surface": "ContextForge dev Docker",
        "base_url": base_url,
        "mode": "apply" if apply else "readback",
        "live_mutation_performed": False,
        "status": "clean" if clean else "dirty",
        "required_clean_scopes": foil["required_clean_scopes"],
        "contextforge_servers": contextforge_server_readback(live),
        "counts": counts,
        "matches": {
            scope: [{"id": item_id(row), "name": item_name(row), "enabled": row.get("enabled")} for row in rows]
            for scope, rows in matches.items()
        },
        "planned_operations": operations,
        "operation_counts": dict(sorted(operation_counts.items())),
        "non_actions": [
            "does not mutate legacy/live 4444 unless explicitly pointed at that base URL",
            "does not write directly to the ContextForge database",
            "does not remove Docker volumes, server-instance directories, or client harness evidence",
        ],
    }


def execute_operations(base_url: str, token: str, operations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for op in operations:
        key = (op["kind"], op["id"])
        if key in seen:
            continue
        seen.add(key)
        result = {**op}
        try:
            registration.request_json("DELETE", base_url, op["path"], token=token)
            result["status"] = "deleted_or_deactivated"
        except Exception as exc:  # noqa: BLE001
            result["status"] = "failed"
            result["error"] = str(exc)
        results.append(result)
    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--foil", choices=sorted(FOILS), default="time")
    parser.add_argument("--base-url", default=os.environ.get("CONTEXTFORGE_HARNESS_BASE_URL", DEFAULT_GATEWAY_BASE))
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--live-json", type=Path, help="Fixture JSON with gateways, tools, servers, prompts, and resources.")
    parser.add_argument("--output", type=Path, help="Write the full readback manifest JSON here.")
    parser.add_argument("--apply", action="store_true", help="Delete matched foil artifacts from the selected development surface.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    live = load_live(args.live_json, base_url=args.base_url, env_file=args.env_file)
    manifest = build_manifest(foil_id=args.foil, base_url=args.base_url, live=live, apply=args.apply)

    if args.apply and manifest["planned_operations"]:
        if args.live_json is not None:
            raise RuntimeError("--apply cannot be used with --live-json fixture mode")
        token = registration.login(args.base_url, registration.read_env(args.env_file))
        manifest["operation_results"] = execute_operations(args.base_url, token, manifest["planned_operations"])
        manifest["live_mutation_performed"] = True
        post_live = read_live(args.base_url, args.env_file)
        manifest["post_apply_readback"] = build_manifest(foil_id=args.foil, base_url=args.base_url, live=post_live, apply=False)
        if any(result.get("status") == "failed" for result in manifest["operation_results"]):
            manifest["status"] = "cleanup_failed"
        else:
            manifest["status"] = manifest["post_apply_readback"]["status"]

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0 if manifest["status"] == "clean" else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
