#!/usr/bin/env python3
"""Read-only ContextForge registry cleanup inspector.

This script builds a dry-run manifest for issue #5. It performs registry reads
only; deletion of tools, prompts, resources, services, or backing runtime state
requires a separate approval-gated apply step.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import contextforge_mcp_wrapper as gateway
import register_tool_guidance as guidance


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INSTANCE_ROOT = REPO_ROOT / "server-instances"
PROJECT_STATE_PATH = REPO_ROOT / ".project" / "context_forge_state.json"
SCHEMA_URI = "contextforge://diagnostics/registry-cleanup/v1"
NON_ACTIONS = (
    "read-only inspection; no ContextForge registry mutation",
    "read-only inspection; no direct database writes",
    "read-only inspection; no service, systemd, process, or Docker mutation",
    "read-only inspection; no server-instance or project-tree deletion",
)
APPROVAL_BOUNDARY = (
    "Deleting registry records, stopping services, disabling units, removing "
    "server-instance directories, or deleting project trees requires separate "
    "explicit approval with exact ids and paths."
)


def now_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _field(row: dict[str, Any], *names: str) -> Any:
    for name in names:
        value = row.get(name)
        if value is not None:
            return value
    return None


def _ids(values: Any) -> set[str]:
    if not isinstance(values, list):
        return set()
    ids: set[str] = set()
    for value in values:
        if isinstance(value, dict):
            candidate = value.get("id")
        else:
            candidate = value
        if candidate is not None:
            ids.add(str(candidate))
    return ids


def _items(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {str(row[key]): row for row in rows if isinstance(row.get(key), str)}


def read_live() -> dict[str, Any]:
    env = gateway._read_env(gateway.CONFIG_ENV)
    token = gateway._token(env["PLATFORM_ADMIN_EMAIL"], env["PLATFORM_ADMIN_PASSWORD"])
    return {
        "tools": gateway._items(gateway._request("GET", "/tools?include_inactive=true&limit=1000", token=token)),
        "servers": gateway._items(gateway._request("GET", "/servers?include_inactive=true&limit=1000", token=token)),
        "prompts": gateway._items(gateway._request("GET", "/prompts?include_inactive=true&limit=1000", token=token)),
        "resources": gateway._items(gateway._request("GET", "/resources?include_inactive=true&limit=1000", token=token)),
    }


def load_instance_manifests(instance_roots: list[Path]) -> list[dict[str, Any]]:
    manifests: list[dict[str, Any]] = []
    seen_paths: set[Path] = set()
    for root in instance_roots:
        for path in sorted(root.glob("*/instance.json")):
            resolved = path.resolve(strict=False)
            if resolved in seen_paths:
                continue
            seen_paths.add(resolved)
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            contextforge = data.get("contextforge") if isinstance(data.get("contextforge"), dict) else {}
            gateway_info = contextforge.get("gateway") if isinstance(contextforge.get("gateway"), dict) else {}
            virtual_server = contextforge.get("virtual_server") if isinstance(contextforge.get("virtual_server"), dict) else {}
            manifests.append(
                {
                    "path": str(path),
                    "instance_dir_name": path.parent.name,
                    "slug": data.get("slug") or path.parent.name,
                    "service": data.get("service") or data.get("slug") or data.get("name") or path.parent.name,
                    "server_name": data.get("server_name"),
                    "enabled": data.get("enabled"),
                    "canonical_project_root": data.get("canonical_project_root"),
                    "gateway_id": gateway_info.get("id"),
                    "gateway_name": gateway_info.get("name"),
                    "virtual_server": virtual_server.get("name"),
                }
            )
    return manifests


def server_indexes(servers: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, set[str]], set[str], set[str]]:
    by_id = _items(servers, "id")
    tool_ids: dict[str, set[str]] = {}
    prompt_ids: set[str] = set()
    resource_ids: set[str] = set()
    for server in servers:
        server_id = str(server["id"])
        tool_ids[server_id] = _ids(
            _field(server, "associatedToolIds", "associatedTools", "tools")
        )
        prompt_ids.update(_ids(_field(server, "associatedPromptIds", "associatedPrompts", "prompts")))
        resource_ids.update(_ids(_field(server, "associatedResourceIds", "associatedResources", "resources")))
    return by_id, tool_ids, prompt_ids, resource_ids


def canonical_expected_tools() -> dict[str, set[str]]:
    expected: dict[str, set[str]] = defaultdict(set)
    for tool_name in guidance.PROMPTS:
        expected[guidance.service_for_tool(tool_name)].add(tool_name)
    return expected


def serena_manifest_sets(instances: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, dict[str, dict[str, Any]]]:
    current = None
    stale: dict[str, dict[str, Any]] = {}
    for item in instances:
        name = str(item.get("instance_dir_name") or item.get("slug") or "")
        if not name.startswith("serena-"):
            continue
        if name == "serena-context-portal":
            current = item
        else:
            stale[name] = item
    return current, stale


def is_test_serena_instance(manifest: dict[str, Any]) -> bool:
    slug = str(manifest.get("instance_dir_name") or manifest.get("slug") or "")
    project_root = str(manifest.get("canonical_project_root") or "")
    return slug.startswith("serena-test-new-proj") and Path(project_root).name.startswith("test-new-proj")


def classify_tools(live: dict[str, Any], instances: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    servers_by_id, tool_ids_by_server, _prompt_ids, _resource_ids = server_indexes(live["servers"])
    current_serena, stale_serena_by_slug = serena_manifest_sets(instances)
    canonical_by_gateway = {
        str(item["gateway_id"]): str(item["service"])
        for item in instances
        if item.get("gateway_id") and item.get("service") != "serena"
    }
    current_serena_gateway_id = str(current_serena.get("gateway_id")) if current_serena else ""
    expected = canonical_expected_tools()
    counts = Counter()
    rows: list[dict[str, Any]] = []
    for tool in live["tools"]:
        tool_id = str(tool["id"])
        gateway_id = str(_field(tool, "gatewayId", "gateway_id") or "")
        gateway_slug = str(_field(tool, "gatewaySlug", "gateway_slug") or "")
        original_name = str(_field(tool, "originalName", "original_name") or "")
        associated_server_ids = [server_id for server_id, ids in tool_ids_by_server.items() if tool_id in ids]
        classification = "unknown_review"
        evidence: dict[str, Any] = {
            "associated_server_ids": associated_server_ids,
            "associated_servers": [
                str(servers_by_id[server_id].get("name"))
                for server_id in associated_server_ids
                if server_id in servers_by_id
            ],
            "raw_associated": bool(associated_server_ids),
        }

        if gateway_id == current_serena_gateway_id and current_serena_gateway_id:
            classification = "keep_project_scoped"
            evidence["project_root"] = current_serena.get("canonical_project_root") if current_serena else None
            evidence["virtual_server"] = current_serena.get("virtual_server") if current_serena else None
        elif gateway_slug in stale_serena_by_slug:
            stale_manifest = stale_serena_by_slug[gateway_slug]
            evidence["project_root"] = stale_manifest.get("canonical_project_root")
            evidence["virtual_server"] = stale_manifest.get("virtual_server")
            evidence["backend_instance"] = stale_manifest.get("path")
            if is_test_serena_instance(stale_manifest):
                classification = "stale_project_scoped"
            else:
                classification = "retain_project_scoped_or_unknown"
                evidence["reason"] = "non-current Serena instance is not a test-new-proj cleanup candidate"
        elif gateway_id in canonical_by_gateway:
            service = canonical_by_gateway[gateway_id]
            evidence["canonical_service"] = service
            evidence["expected_registered_tools"] = sorted(expected.get(service, set()))
            if str(tool.get("name")) in expected.get(service, set()):
                classification = "keep_canonical"
            elif original_name == "cleanup_dead_sessions" and gateway_slug == "ssh-tmux":
                classification = "orphaned"

        if not associated_server_ids:
            evidence["server_association"] = "none"
        if classification in {"stale_project_scoped", "orphaned"}:
            evidence["reason"] = "candidate is unassociated or tied to non-current registry state"

        counts[classification] += 1
        rows.append(
            {
                "id": tool_id,
                "name": tool.get("name"),
                "original_name": original_name or None,
                "enabled": tool.get("enabled"),
                "gateway_id": gateway_id,
                "gateway_slug": gateway_slug,
                "classification": classification,
                "evidence": evidence,
            }
        )
    return rows, dict(counts)


def orphan_prompt_resource_rows(live: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    _servers_by_id, _tool_ids, prompt_ids, resource_ids = server_indexes(live["servers"])
    prompts = [
        {
            "id": prompt["id"],
            "name": prompt.get("name"),
            "custom_name": _field(prompt, "customName", "custom_name"),
            "title": prompt.get("title"),
            "enabled": prompt.get("enabled"),
            "visibility": prompt.get("visibility"),
        }
        for prompt in live["prompts"]
        if str(prompt["id"]) not in prompt_ids
    ]
    resources = [
        {
            "id": resource["id"],
            "name": resource.get("name"),
            "title": resource.get("title"),
            "uri": resource.get("uri"),
            "enabled": resource.get("enabled"),
            "visibility": resource.get("visibility"),
        }
        for resource in live["resources"]
        if str(resource["id"]) not in resource_ids
    ]
    return prompts, resources


def guidance_gap_summary(live: dict[str, Any]) -> dict[str, dict[str, int]]:
    tools_by_name = _items(live["tools"], "name")
    resources_by_uri = _items(live["resources"], "uri")
    prompts_by_custom = {
        str(_field(prompt, "customName", "custom_name", "name")): prompt
        for prompt in live["prompts"]
        if _field(prompt, "customName", "custom_name", "name")
    }
    prompts_by_name = _items(live["prompts"], "name")
    prompt_map = {
        tool_name: prompt
        for tool_name, prompt in guidance.PROMPTS.items()
        if tool_name in tools_by_name
    }
    guidance_items, existing_by_key = guidance.build_guidance_items(
        tools_by_name,
        resources_by_uri,
        prompts_by_custom,
        prompts_by_name,
        prompt_map,
    )
    gaps: dict[str, Counter[str]] = defaultdict(Counter)
    for item in guidance_items:
        if existing_by_key[f"prompt:{item.tool_name}"] is None:
            gaps[item.service]["missing_prompts"] += 1
        if existing_by_key[f"resource:{item.tool_name}"] is None:
            gaps[item.service]["missing_resources"] += 1
    return {
        service: {
            "missing_prompts": counts.get("missing_prompts", 0),
            "missing_resources": counts.get("missing_resources", 0),
        }
        for service, counts in sorted(gaps.items())
    }


def cleanup_candidates(
    tool_rows: list[dict[str, Any]],
    prompt_orphans: list[dict[str, Any]],
    resource_orphans: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for row in tool_rows:
        if row["classification"] not in {"stale_project_scoped", "orphaned"}:
            continue
        candidates.append(
            {
                "operation": "DELETE /tools/{tool_id}",
                "dry_run": True,
                "approval_required": True,
                "tool_id": row["id"],
                "tool_name": row["name"],
                "original_name": row["original_name"],
                "classification": row["classification"],
                "gateway_id": row["gateway_id"],
                "gateway_slug": row["gateway_slug"],
                "rollback": {
                    "readback": "GET /tools/{tool_id}",
                    "restore_source": row["evidence"].get("backend_instance")
                    or row["evidence"].get("canonical_service"),
                },
            }
        )
    for prompt in prompt_orphans:
        candidates.append(
            {
                "operation": "DELETE /prompts/{prompt_id}",
                "dry_run": True,
                "approval_required": True,
                "prompt_id": prompt["id"],
                "name": prompt["name"],
                "custom_name": prompt["custom_name"],
                "rollback": {"readback": "GET /prompts/{prompt_id}"},
            }
        )
    for resource in resource_orphans:
        candidates.append(
            {
                "operation": "DELETE /resources/{resource_id}",
                "dry_run": True,
                "approval_required": True,
                "resource_id": resource["id"],
                "name": resource["name"],
                "uri": resource["uri"],
                "rollback": {"readback": "GET /resources/{resource_id}"},
            }
        )
    return candidates


def build_manifest(live: dict[str, Any], instances: list[dict[str, Any]], instance_roots: list[Path]) -> dict[str, Any]:
    tool_rows, classification_counts = classify_tools(live, instances)
    prompt_orphans, resource_orphans = orphan_prompt_resource_rows(live)
    candidates = cleanup_candidates(tool_rows, prompt_orphans, resource_orphans)
    operation_counts = Counter(candidate["operation"] for candidate in candidates)
    return {
        "schema_uri": SCHEMA_URI,
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "dry_run": True,
        "live_mutation_performed": False,
        "project_root": str(REPO_ROOT),
        "project_state_path": str(PROJECT_STATE_PATH),
        "instance_roots": [str(path) for path in instance_roots],
        "summary": {
            "counts": {
                "tools": len(live["tools"]),
                "servers": len(live["servers"]),
                "prompts": len(live["prompts"]),
                "resources": len(live["resources"]),
                "instance_manifests": len(instances),
            },
            "classification": classification_counts,
            "cleanup_candidates_by_operation": dict(sorted(operation_counts.items())),
            "orphan_prompts": len(prompt_orphans),
            "orphan_resources": len(resource_orphans),
            "guidance_gaps": guidance_gap_summary(live),
        },
        "tool_classification": tool_rows,
        "prompt_orphans": prompt_orphans,
        "resource_orphans": resource_orphans,
        "cleanup_candidates": candidates,
        "approval_boundary": APPROVAL_BOUNDARY,
        "non_actions": list(NON_ACTIONS),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live-json", type=Path, help="Fixture JSON with tools, servers, prompts, and resources.")
    parser.add_argument(
        "--instance-root",
        action="append",
        type=Path,
        default=[],
        help="server-instances root to inspect. Defaults to this repository's server-instances.",
    )
    parser.add_argument(
        "--extra-instance-root",
        action="append",
        type=Path,
        default=[],
        help="Additional read-only server-instances root, for migration/legacy evidence.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "generated" / f"contextforge-cleanup-{now_stamp()}.json",
        help="Write the dry-run manifest JSON here.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    instance_roots = args.instance_root or [DEFAULT_INSTANCE_ROOT]
    instance_roots = [*instance_roots, *args.extra_instance_root]
    if args.live_json:
        live = json.loads(args.live_json.read_text(encoding="utf-8"))
    else:
        live = read_live()
    instances = load_instance_manifests(instance_roots)
    manifest = build_manifest(live, instances, instance_roots)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest["summary"], indent=2, sort_keys=True))
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
