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
import npm_stdio_host_records
import npm_stdio_host_runtime


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
        "host_service_bindings": ["time:canonical", "time:project"],
        "host_service_binding_prefixes": ["time:"],
        "host_runtime_slug_prefixes": ["time"],
        "gateway_names": ["time-dev-docker", "time"],
        "server_names": ["time_dev_docker_server", "time_server"],
        "tool_name_prefixes": ["time-dev-docker-", "time-"],
        "prompt_name_prefixes": ["time-", "time_"],
        "resource_uri_prefixes": [
            "contextforge://time/",
            "contextforge://services/time/",
            "contextforge://service-specs/time/",
        ],
        "repo_artifact_paths": [
            "server-instances/time",
            "docker/contextforge-harness/time-transceiver",
            "docker/contextforge-harness/scripts/register_time_dev.py",
            "docker/contextforge-harness/scripts/probe-time-dev.py",
        ],
        "repo_artifact_status": "known_development_foil_artifacts_present",
        "required_clean_scopes": [
            "mcp_service",
            "service_tools",
            "virtual_server",
            "service_bound_prompts",
            "service_bound_resources",
        ],
    },
    "memory": {
        "service_binding": "memory:canonical",
        "host_service_bindings": ["memory:canonical", "memory:project"],
        "host_service_binding_prefixes": ["memory:", "memory-"],
        "host_runtime_slug_prefixes": ["memory"],
        "gateway_names": ["memory-canonical-gateway", "memory-gateway", "memory-project-gateway", "memory"],
        "server_names": ["memory-canonical-server", "memory-server", "memory-project-server"],
        "tool_name_prefixes": ["memory-", "memory_"],
        "prompt_name_prefixes": ["memory-", "memory_"],
        "resource_uri_prefixes": [
            "contextforge://memory/",
            "contextforge://services/memory/",
            "contextforge://service-specs/memory/",
        ],
        "repo_artifact_paths": [],
        "repo_artifact_status": "no_known_repo_local_foil_artifacts",
        "required_clean_scopes": [
            "mcp_service",
            "service_tools",
            "virtual_server",
            "service_bound_prompts",
            "service_bound_resources",
        ],
    }
}


REPO_ROOT = Path(__file__).resolve().parents[3]


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


def repo_artifact_readback(foil: dict[str, Any]) -> dict[str, Any]:
    paths = [str(item) for item in foil.get("repo_artifact_paths") or [] if str(item).strip()]
    matches = [
        {"path": path, "present": (REPO_ROOT / path).exists()}
        for path in paths
    ]
    return {
        "status": str(foil.get("repo_artifact_status") or "not_declared"),
        "checked_paths": matches,
        "present_count": sum(1 for item in matches if item["present"]),
        "claim_boundary": "repo artifact readback is a veil-risk diagnostic; ContextForge clean status is based on registry artifact scopes",
    }


def host_binding_matches(binding: str, foil: dict[str, Any]) -> bool:
    if binding in set(foil.get("host_service_bindings") or []):
        return True
    return any(binding.startswith(str(prefix)) for prefix in foil.get("host_service_binding_prefixes") or [])


def host_runtime_dir_matches(path: Path, foil: dict[str, Any]) -> bool:
    name = path.name
    return any(name.startswith(str(prefix)) for prefix in foil.get("host_runtime_slug_prefixes") or [])


def managed_instance_manifest_matches(manifest: dict[str, Any], foil: dict[str, Any]) -> bool:
    if manifest.get("managed_by") != npm_stdio_host_records.HOST_SERVICE_ID:
        return False
    service_binding = str(manifest.get("service_binding") or "").strip()
    if service_binding and host_binding_matches(service_binding, foil):
        return True
    slug = str(manifest.get("slug") or "").strip()
    service = str(manifest.get("service") or "").strip()
    return any(
        value and any(value.startswith(str(prefix)) for prefix in foil.get("host_runtime_slug_prefixes") or [])
        for value in (slug, service)
    )


def managed_instance_manifest_readback(root: Path, foil: dict[str, Any]) -> list[dict[str, Any]]:
    instances_root = root / "server-instances"
    if not instances_root.exists():
        return []
    manifests: list[dict[str, Any]] = []
    for path in sorted(instances_root.glob("*/instance.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict) or not managed_instance_manifest_matches(payload, foil):
            continue
        manifests.append(
            {
                "service_binding": str(payload.get("service_binding") or ""),
                "service": str(payload.get("service") or ""),
                "slug": str(payload.get("slug") or path.parent.name),
                "manifest_path": str(path.resolve(strict=False)),
                "manifest_exists": path.exists(),
            }
        )
    return manifests


def host_readback(project_root: Path | None, foil: dict[str, Any]) -> dict[str, Any]:
    if project_root is None:
        return {
            "enabled": False,
            "claim_boundary": "host readback skipped only for fixture mode without --project-root",
            "counts": {"host_records": 0, "host_runtime_services": 0, "host_managed_instance_manifests": 0},
            "matches": {"host_records": [], "host_runtime_services": [], "host_managed_instance_manifests": []},
            "clean": True,
        }
    root = project_root.resolve(strict=False)
    index = npm_stdio_host_records.load_index(root)
    records: list[dict[str, Any]] = []
    for service_binding, entry in sorted((index.get("records") or {}).items()):
        if not isinstance(service_binding, str) or not host_binding_matches(service_binding, foil):
            continue
        record_path = ""
        record_exists = False
        if isinstance(entry, dict) and entry.get("record_path"):
            path = (root / str(entry["record_path"])).resolve(strict=False)
            record_path = str(path)
            record_exists = path.exists()
        records.append(
            {
                "service_binding": service_binding,
                "index_entry_present": True,
                "record_path": record_path,
                "record_exists": record_exists,
            }
        )

    runtime_services: list[dict[str, Any]] = []
    services_root = (root / npm_stdio_host_runtime.SERVICES_ROOT).resolve(strict=False)
    if services_root.exists():
        for path in sorted(item for item in services_root.iterdir() if item.is_dir()):
            if not host_runtime_dir_matches(path, foil):
                continue
            state_path = path / "runtime-state.json"
            service_binding = path.name
            running = False
            if state_path.exists():
                try:
                    state = json.loads(state_path.read_text(encoding="utf-8"))
                    if isinstance(state, dict):
                        service_binding = str(state.get("service_binding") or service_binding)
                        running = npm_stdio_host_runtime.bridge_state_running(state)
                except (OSError, json.JSONDecodeError):
                    pass
            runtime_services.append(
                {
                    "service_binding": service_binding,
                    "runtime_dir": str(path),
                    "runtime_state_path": str(state_path),
                    "runtime_state_exists": state_path.exists(),
                    "running": running,
                }
            )
    managed_instance_manifests = managed_instance_manifest_readback(root, foil)
    counts = {
        "host_records": len(records),
        "host_runtime_services": len(runtime_services),
        "host_managed_instance_manifests": len(managed_instance_manifests),
    }
    return {
        "enabled": True,
        "project_root": str(root),
        "host_service": npm_stdio_host_records.HOST_SERVICE_ID,
        "counts": counts,
        "matches": {
            "host_records": records,
            "host_runtime_services": runtime_services,
            "host_managed_instance_manifests": managed_instance_manifests,
        },
        "clean": all(value == 0 for value in counts.values()),
        "claim_boundary": "host readback covers managed npm-stdio host records, runtime dirs, and managed instance manifests; ContextForge registry scopes are counted separately",
    }


def host_operations(readback: dict[str, Any]) -> list[dict[str, Any]]:
    operations: list[dict[str, Any]] = []
    if not readback.get("enabled"):
        return operations
    for record in readback.get("matches", {}).get("host_runtime_services", []):
        service_binding = str(record.get("service_binding") or "").strip()
        if service_binding:
            operations.append(
                {
                    "kind": "npm_stdio_host_runtime",
                    "service_binding": service_binding,
                    "scope": "npm_stdio_host_runtime",
                    "method": "DELETE",
                    "path": record.get("runtime_dir") or "",
                }
            )
    for record in readback.get("matches", {}).get("host_managed_instance_manifests", []):
        path = str(record.get("manifest_path") or "").strip()
        if path:
            operations.append(
                {
                    "kind": "npm_stdio_host_instance_manifest",
                    "service_binding": str(record.get("service_binding") or "").strip(),
                    "scope": "npm_stdio_host_instance_manifest",
                    "method": "DELETE",
                    "path": path,
                }
            )
    for record in readback.get("matches", {}).get("host_records", []):
        service_binding = str(record.get("service_binding") or "").strip()
        if service_binding:
            operations.append(
                {
                    "kind": "npm_stdio_host_record",
                    "service_binding": service_binding,
                    "scope": "npm_stdio_host_record",
                    "method": "DELETE",
                    "path": record.get("record_path") or "",
                }
            )
    return operations


def build_manifest(
    *,
    foil_id: str,
    base_url: str,
    live: dict[str, list[dict[str, Any]]],
    apply: bool,
    project_root: Path | None = None,
) -> dict[str, Any]:
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
    host = host_readback(project_root, foil)
    host_planned_operations = host_operations(host)
    operation_counts = Counter(op["path"] for op in operations)
    clean = all(counts[scope] == 0 for scope in foil["required_clean_scopes"]) and host["clean"]
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
        "repo_artifact_readback": repo_artifact_readback(foil),
        "counts": counts,
        "npm_stdio_host_readback": host,
        "matches": {
            scope: [{"id": item_id(row), "name": item_name(row), "enabled": row.get("enabled")} for row in rows]
            for scope, rows in matches.items()
        },
        "planned_operations": operations,
        "planned_host_operations": host_planned_operations,
        "operation_counts": dict(sorted(operation_counts.items())),
        "non_actions": [
            "does not mutate legacy/live 4444 unless explicitly pointed at that base URL",
            "does not write directly to the ContextForge database",
            "does not remove Docker volumes or client harness evidence",
            "removes only scoped managed npm-stdio host records, runtime dirs, and managed instance manifests when --apply is used",
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


def execute_host_operations(project_root: Path, operations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for op in operations:
        service_binding = str(op.get("service_binding") or "")
        path = str(op.get("path") or "")
        key = (str(op.get("kind") or ""), path or service_binding)
        if not (service_binding or path) or key in seen:
            continue
        seen.add(key)
        result = {**op}
        try:
            if op["kind"] == "npm_stdio_host_runtime":
                details = npm_stdio_host_runtime.delete_service(project_root, service_binding)
                result["status"] = "deleted_or_absent"
                result["details"] = details
                result["ok"] = details.get("rollback_result") == "passed"
            elif op["kind"] == "npm_stdio_host_record":
                details = npm_stdio_host_records.delete_service_record(project_root, service_binding)
                result["status"] = "deleted_or_absent"
                result["details"] = details
                result["ok"] = bool(details.get("ok"))
            elif op["kind"] == "npm_stdio_host_instance_manifest":
                manifest_path = Path(path).resolve(strict=False)
                details: dict[str, Any] = {"path": str(manifest_path), "removed": False}
                if manifest_path.exists():
                    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
                    matching_foils = [
                        item
                        for item in FOILS.values()
                        if isinstance(payload, dict)
                        and managed_instance_manifest_matches(payload, item)
                        and (not service_binding or host_binding_matches(service_binding, item))
                    ]
                    if not matching_foils:
                        raise RuntimeError(f"refusing to remove unmanaged or nonmatching instance manifest: {manifest_path}")
                    manifest_path.unlink()
                    details["removed"] = True
                result["status"] = "deleted_or_absent"
                result["details"] = details
                result["ok"] = True
            else:
                result["status"] = "failed"
                result["ok"] = False
                result["error"] = f"unsupported host cleanup kind: {op['kind']}"
        except Exception as exc:  # noqa: BLE001
            result["status"] = "failed"
            result["ok"] = False
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
    parser.add_argument("--project-root", type=Path, help="Project root for managed npm-stdio host record/runtime cleanup.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    live = load_live(args.live_json, base_url=args.base_url, env_file=args.env_file)
    project_root = args.project_root
    if project_root is None and args.live_json is None:
        project_root = REPO_ROOT
    manifest = build_manifest(foil_id=args.foil, base_url=args.base_url, live=live, apply=args.apply, project_root=project_root)

    if args.apply and (manifest["planned_operations"] or manifest["planned_host_operations"]):
        if args.live_json is not None:
            raise RuntimeError("--apply cannot be used with --live-json fixture mode")
        token = registration.login(args.base_url, registration.read_env(args.env_file))
        manifest["operation_results"] = execute_operations(args.base_url, token, manifest["planned_operations"])
        manifest["host_operation_results"] = execute_host_operations(project_root or REPO_ROOT, manifest["planned_host_operations"])
        manifest["live_mutation_performed"] = bool(manifest["operation_results"] or manifest["host_operation_results"])
        post_live = read_live(args.base_url, args.env_file)
        manifest["post_apply_readback"] = build_manifest(
            foil_id=args.foil,
            base_url=args.base_url,
            live=post_live,
            apply=False,
            project_root=project_root,
        )
        if any(result.get("status") == "failed" for result in manifest["operation_results"]) or any(
            result.get("status") == "failed" or result.get("ok") is False
            for result in manifest["host_operation_results"]
        ):
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
