#!/usr/bin/env python3
"""Plan ContextForge registry recreation from project-local manifests.

This script is deliberately read-only. It does not call ContextForge APIs and
does not read secret env-file contents. It turns server-instance manifests and
an optional ContextForge export artifact into an executable migration checklist.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SERVER_INSTANCES = REPO_ROOT / "server-instances"
SCHEMA_URI = "contextforge://diagnostics/registry-recreation-plan/v1"
OWNER = "admin@contextforge.dev"

CANONICAL_SERVICE_DEFAULTS: dict[str, dict[str, Any]] = {
    "mentality": {
        "gateway_name": "mentality",
        "server_name": "mentality_server",
        "url": "http://127.0.0.1:9100/mcp",
        "tags": ["contextforge", "mentality", "local-backend"],
        "helper": None,
    },
    "ssh-tmux": {
        "gateway_name": "ssh-tmux",
        "server_name": "ssh_tmux_server",
        "url": "http://127.0.0.1:9102/mcp",
        "tags": ["contextforge", "ssh-tmux", "local-backend"],
        "helper": None,
    },
    "context7": {
        "gateway_name": "context7-local",
        "server_name": "context7_local_server",
        "url": "http://127.0.0.1:9103/mcp",
        "tags": ["contextforge", "context7", "local-backend"],
        "helper": None,
    },
    "playwright": {
        "gateway_name": "playwright",
        "server_name": "playwright_server",
        "url": "http://127.0.0.1:9104/mcp",
        "tags": ["contextforge", "playwright", "local-backend"],
        "helper": None,
    },
    "exa-search": {
        "gateway_name": "exa-search",
        "server_name": "exa_search_server",
        "url": "http://127.0.0.1:9105/mcp",
        "tags": ["contextforge", "exa-search", "local-backend"],
        "helper": None,
    },
    "github": {
        "gateway_name": "github",
        "server_name": "github_server",
        "url": "http://127.0.0.1:9106/mcp",
        "tags": ["contextforge", "github", "local-backend"],
        "helper": "scripts/register_github_service.py",
    },
    "web-search": {
        "gateway_name": "web-search",
        "server_name": "web_search_server",
        "url": "http://127.0.0.1:9107/mcp",
        "tags": ["contextforge", "web-search", "local-backend"],
        "helper": "scripts/register_web_search_service.py",
    },
    "openzeppelin-solidity-contracts": {
        "gateway_name": "openzeppelin-solidity-contracts",
        "server_name": "openzeppelin_solidity_contracts_server",
        "url": "https://mcp.openzeppelin.com/contracts/solidity/mcp",
        "tags": ["contextforge", "openzeppelin", "remote-backend"],
        "helper": None,
    },
    "serena-cf-controlplane-d46fe58a2a20": {
        "gateway_name": "serena-cf-controlplane-d46fe58a2a20",
        "server_name": "serena_cf_controlplane_d46fe58a2a20_server",
        "url": "http://127.0.0.1:9108/mcp",
        "tags": ["contextforge", "serena", "cf-controlplane"],
        "helper": "scripts/register_serena_cf_controlplane_service.py --allow-live-serena-registration",
    },
}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _manifest_paths(root: Path) -> list[Path]:
    return sorted(root.glob("*/instance.json"))


def _items(export_data: dict[str, Any] | None, key: str) -> list[dict[str, Any]]:
    if not export_data:
        return []
    value = export_data.get("entities", {}).get(key, [])
    return value if isinstance(value, list) else []


def _by_name(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(item.get("name")): item for item in items if item.get("name")}


def _export_metadata_tools(export_data: dict[str, Any] | None, server_name: str) -> list[str]:
    if not export_data:
        return []
    deps = export_data.get("metadata", {}).get("dependencies", {}).get("servers_to_tools", {})
    tools = deps.get(server_name, [])
    return sorted(str(tool) for tool in tools)


def _needs_env(manifest: dict[str, Any]) -> list[str]:
    backend = manifest.get("backend")
    env = backend.get("env") if isinstance(backend, dict) else None
    if isinstance(env, str):
        return [env]
    return []


def _path_state(path_text: str) -> dict[str, Any]:
    path = REPO_ROOT / path_text
    return {"path": str(path), "exists": path.exists(), "is_file": path.is_file()}


def _gateway_operation(defaults: dict[str, Any]) -> dict[str, Any]:
    return {
        "api": "POST /gateways or PUT /gateways/{id}",
        "match_by": ["name", "url"],
        "payload": {
            "name": defaults["gateway_name"],
            "url": defaults["url"],
            "transport": "STREAMABLEHTTP",
            "tags": defaults["tags"],
            "visibility": "public",
            "owner_email": OWNER,
            "gateway_mode": "cache",
        },
        "then": ["POST /gateways/{id}/tools/refresh", "GET /tools?include_inactive=true&limit=1000"],
    }


def _server_operation(defaults: dict[str, Any], expected_tools: list[str]) -> dict[str, Any]:
    return {
        "api": "POST /servers or PUT /servers/{id}",
        "match_by": ["name"],
        "payload": {
            "name": defaults["server_name"],
            "description": f"Virtual server exposing {defaults['gateway_name']}.",
            "associated_tools": "resolve from refreshed gateway tools",
            "tags": defaults["tags"],
            "visibility": "public",
            "owner_email": OWNER,
        },
        "expected_tool_names": expected_tools,
    }


def build_plan(*, manifests_root: Path = SERVER_INSTANCES, export_path: Path | None = None) -> dict[str, Any]:
    export_data = _read_json(export_path) if export_path else None
    exported_gateways = _by_name(_items(export_data, "gateways"))
    exported_servers = _by_name(_items(export_data, "servers"))
    services: list[dict[str, Any]] = []

    for manifest_path in _manifest_paths(manifests_root):
        manifest = _read_json(manifest_path)
        slug = str(manifest.get("slug") or manifest_path.parent.name)
        defaults = CANONICAL_SERVICE_DEFAULTS.get(slug)
        if defaults is None:
            services.append(
                {
                    "slug": slug,
                    "manifest": str(manifest_path),
                    "classification": "unsupported_manifest_requires_manual_plan",
                    "mutation_performed": False,
                    "reason": "no canonical registry recreation defaults are defined for this manifest",
                }
            )
            continue

        expected_tools = sorted(str(tool) for tool in manifest.get("registration", {}).get("registered_tools", []))
        exported_tools = _export_metadata_tools(export_data, defaults["server_name"])
        env_refs = [_path_state(path) for path in _needs_env(manifest)]
        helper = defaults.get("helper")
        if helper:
            classification = "covered_by_existing_helper"
        elif slug.startswith("serena-"):
            classification = "serena_project_specific_plan_required"
        else:
            classification = "needs_manifest_driven_api_recreation"
        services.append(
            {
                "slug": slug,
                "manifest": str(manifest_path),
                "classification": classification,
                "helper": helper,
                "gateway_name": defaults["gateway_name"],
                "server_name": defaults["server_name"],
                "url": defaults["url"],
                "env_refs": env_refs,
                "existing_export_gateway": defaults["gateway_name"] in exported_gateways if export_data else None,
                "existing_export_server": defaults["server_name"] in exported_servers if export_data else None,
                "expected_tool_names": expected_tools,
                "export_dependency_tool_names": exported_tools,
                "tool_name_drift": bool(exported_tools and expected_tools and exported_tools != expected_tools),
                "operations": [
                    _gateway_operation(defaults),
                    _server_operation(defaults, exported_tools or expected_tools),
                    {"api": "verify", "checks": ["GET /servers/{id}/tools", "POST /servers/{id}/mcp/", "GET /servers/{id}/sse"]},
                ],
                "mutation_performed": False,
            }
        )

    counts: dict[str, int] = {}
    for service in services:
        classification = service["classification"]
        counts[classification] = counts.get(classification, 0) + 1
    return {
        "schema_uri": SCHEMA_URI,
        "repo_root": str(REPO_ROOT),
        "manifests_root": str(manifests_root),
        "export_path": str(export_path) if export_path else None,
        "mutation_performed": False,
        "summary": {
            "service_count": len(services),
            "classification_counts": counts,
            "services_needing_manifest_driven_api_recreation": [
                service["slug"]
                for service in services
                if service["classification"] == "needs_manifest_driven_api_recreation"
            ],
            "services_covered_by_existing_helper": [
                service["slug"]
                for service in services
                if service["classification"] == "covered_by_existing_helper"
            ],
            "services_with_tool_name_drift": [
                service["slug"] for service in services if service.get("tool_name_drift")
            ],
        },
        "services": services,
        "non_actions": [
            "read-only plan; no ContextForge API calls",
            "read-only plan; no database reads or writes",
            "read-only plan; no service, process, systemd, Docker, or client mutation",
            "read-only plan; no env-file contents read",
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifests-root", type=Path, default=SERVER_INSTANCES)
    parser.add_argument("--export-json", type=Path, help="Optional existing ContextForge export artifact.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(json.dumps(build_plan(manifests_root=args.manifests_root, export_path=args.export_json), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
