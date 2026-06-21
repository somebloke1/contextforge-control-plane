#!/usr/bin/env python3
"""Plan 4445 Docker successor-surface migration without mutating ContextForge."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import plan_contextforge_registry_recreation as registry_plan
import register_tool_guidance


REPO_ROOT = Path(__file__).resolve().parents[1]
SERVER_INSTANCES = REPO_ROOT / "server-instances"
SCHEMA_URI = "contextforge://diagnostics/docker-successor-migration-plan/v1"
DEFAULT_TARGET_BASE_URL = "http://127.0.0.1:4445"
DEFAULT_TARGET_ENV_FILE = "docker/contextforge-harness/env/contextforge.env"


DOCKER_TARGET_PROFILE: dict[str, dict[str, Any]] = {
    "context7": {
        "locality": "compose_sidecar",
        "target_upstream_url": "http://context7-transceiver:9203/mcp",
        "approval_state": "available_in_current_harness",
        "notes": "Current 4445 already has canonical context7 names, but guidance is absent.",
    },
    "mentality": {
        "locality": "compose_sidecar",
        "target_upstream_url": "http://mentality-transceiver:9201/mcp",
        "approval_state": "requires_canonical_name_projection",
        "notes": "Current 4445 has dev names; replacement parity needs mentality/mentality_server.",
    },
    "ssh-tmux": {
        "locality": "host_gateway_projection",
        "target_upstream_url": "http://host.docker.internal:9102/mcp",
        "approval_state": "blocked_pending_single_user_boundary_review",
        "notes": "Persistent sessions are host-local state; do not blindly share without approval.",
    },
    "playwright": {
        "locality": "compose_sidecar",
        "target_upstream_url": "http://playwright-transceiver:9204/mcp",
        "approval_state": "available_in_isolated_browser_sidecar",
        "notes": "Docker-local isolated browser sidecar uses an in-memory shared context for ContextForge proxy continuity without sharing host browser/session state.",
    },
    "exa-search": {
        "locality": "compose_sidecar",
        "target_upstream_url": "http://exa-search-transceiver:9205/mcp",
        "approval_state": "ready_after_credential_env_preflight",
        "notes": "Credential-scoped sidecar uses ignored server-instances/exa-search/.env; prove env presence without printing secrets before apply.",
    },
    "github": {
        "locality": "host_gateway_projection",
        "target_upstream_url": "http://host.docker.internal:9106/mcp",
        "approval_state": "blocked_pending_credential_boundary_review",
        "notes": "GitHub token scope is a credential boundary; helper must target 4445 explicitly.",
    },
    "web-search": {
        "locality": "host_gateway_projection",
        "target_upstream_url": "http://host.docker.internal:9107/mcp",
        "approval_state": "blocked_pending_credential_boundary_review",
        "notes": "Credential/cookie-backed capabilities must be reviewed before successor registration.",
    },
    "openzeppelin-solidity-contracts": {
        "locality": "remote_direct",
        "target_upstream_url": "https://mcp.openzeppelin.com/contracts/solidity/mcp",
        "approval_state": "ready_for_dry_run_registration_plan",
        "notes": "Remote shared service does not need host gateway projection.",
    },
    "serena-cf-controlplane-d46fe58a2a20": {
        "locality": "project_scoped_host_gateway_projection",
        "target_upstream_url": "http://host.docker.internal:9108/mcp",
        "approval_state": "blocked_pending_project_scoped_runtime_approval",
        "notes": "Project-scoped code-intelligence state needs explicit Docker/runtime approval.",
    },
}


HELPER_DISPOSITIONS: dict[str, dict[str, str]] = {
    "docker/contextforge-harness/scripts/register_context7_dev.py": {
        "disposition": "reusable_as_is_for_current_context7_dev_surface",
        "reason": "Targets 4445 and compose-network Context7, but still needs guidance association.",
    },
    "docker/contextforge-harness/scripts/register_mentality_dev.py": {
        "disposition": "reusable_after_canonical_name_parameterization",
        "reason": "Registers dev names; replacement parity needs mentality/mentality_server.",
    },
    "scripts/plan_contextforge_registry_recreation.py": {
        "disposition": "reusable_after_docker_profile_parameterization",
        "reason": "Read-only, but default URLs are host 127.0.0.1:910x live-surface assumptions.",
    },
    "scripts/apply_contextforge_registry_recreation.py": {
        "disposition": "unsafe_as_is_for_4445_apply",
        "reason": "Uses default wrapper env/base and host-local URLs unless explicitly parameterized.",
    },
    "scripts/register_tool_guidance.py": {
        "disposition": "reusable_after_target_parameterization",
        "reason": "Supports explicit 4445 base/env, dry-run planning, target gateway ID lookup, and bounded service selection.",
    },
    "scripts/register_project_init_prompt.py": {
        "disposition": "reusable_after_target_parameterization",
        "reason": "API path is fine; auth/base and Serena association must target 4445.",
    },
    "scripts/register_github_service.py": {
        "disposition": "unsafe_as_is_for_4445",
        "reason": "Live-surface localhost defaults and default auth/base must be parameterized.",
    },
    "scripts/register_web_search_service.py": {
        "disposition": "unsafe_as_is_for_4445",
        "reason": "Live-surface localhost defaults plus credential locality need review.",
    },
    "scripts/register_serena_cf_controlplane_service.py": {
        "disposition": "unsafe_as_is_for_4445",
        "reason": "Legacy/live-gated and project-scoped; Docker successor needs a separate endpoint plan.",
    },
}

EXPECTED_TOOL_GUIDANCE_TAG_TO_TOOL = {
    register_tool_guidance.tool_guidance_tag(tool_name): tool_name
    for tool_name in register_tool_guidance.PROMPTS
}
EXPECTED_TOOL_GUIDANCE_TAGS = set(EXPECTED_TOOL_GUIDANCE_TAG_TO_TOOL)


def _read_json(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _endpoint_rows(readback: dict[str, Any] | None, surface: str, endpoint: str) -> list[dict[str, Any]]:
    if not readback:
        return []
    endpoint_data: Any = None
    if "bases" in readback:
        endpoint_data = readback.get("bases", {}).get(surface, {}).get("endpoints", {}).get(endpoint)
    elif surface in readback:
        endpoint_data = readback.get(surface, {}).get("endpoints", {}).get(endpoint)
    if not isinstance(endpoint_data, dict):
        return []
    rows = endpoint_data.get("all")
    return rows if isinstance(rows, list) else []


def _row_names(rows: list[dict[str, Any]]) -> set[str]:
    return {str(row["name"]) for row in rows if isinstance(row.get("name"), str)}


def _resource_keys(rows: list[dict[str, Any]]) -> set[str]:
    keys: set[str] = set()
    for row in rows:
        value = row.get("uri") or row.get("name") or row.get("customName") or row.get("id")
        if isinstance(value, str):
            keys.add(value)
    return keys


def _tag_labels(row: dict[str, Any]) -> set[str]:
    labels: set[str] = set()
    for tag in row.get("tags") or []:
        if isinstance(tag, str):
            labels.add(tag)
        elif isinstance(tag, dict):
            for key in ("label", "id", "name"):
                value = tag.get(key)
                if isinstance(value, str):
                    labels.add(value)
    return labels


def _tool_guidance_tags(rows: list[dict[str, Any]]) -> set[str]:
    tags: set[str] = set()
    for row in rows:
        labels = _tag_labels(row)
        if "tool-guidance" not in labels:
            continue
        tags.update(label for label in labels if label in EXPECTED_TOOL_GUIDANCE_TAGS)
    return tags


def _tool_names_for_tags(tags: set[str]) -> list[str]:
    return sorted(EXPECTED_TOOL_GUIDANCE_TAG_TO_TOOL.get(tag, tag) for tag in tags)


def _counts(readback: dict[str, Any] | None, surface: str) -> dict[str, int]:
    return {
        endpoint: len(_endpoint_rows(readback, surface, endpoint))
        for endpoint in ("servers", "tools", "prompts", "resources")
    }


def _name_gap(
    baseline: dict[str, Any] | None,
    current: dict[str, Any] | None,
    endpoint: str,
) -> dict[str, Any]:
    baseline_rows = _endpoint_rows(baseline, "host_4444", endpoint)
    current_rows = _endpoint_rows(current, "docker_4445", endpoint)
    if endpoint == "resources":
        baseline_names = _resource_keys(baseline_rows)
        current_names = _resource_keys(current_rows)
    else:
        baseline_names = _row_names(baseline_rows)
        current_names = _row_names(current_rows)
    return {
        "baseline_count": len(baseline_rows),
        "current_count": len(current_rows),
        "missing_on_4445": sorted(baseline_names - current_names),
        "extra_on_4445": sorted(current_names - baseline_names),
    }


def _server_association_count(server: dict[str, Any], *keys: str) -> int:
    for key in keys:
        value = server.get(key)
        if isinstance(value, list):
            return len(value)
    return 0


def _current_server_summary(current: dict[str, Any] | None) -> dict[str, dict[str, int]]:
    summary: dict[str, dict[str, int]] = {}
    for server in _endpoint_rows(current, "docker_4445", "servers"):
        name = str(server.get("name") or server.get("id"))
        summary[name] = {
            "tools": _server_association_count(server, "associatedTools", "associated_tools", "associatedToolIds"),
            "prompts": _server_association_count(server, "associatedPrompts", "associated_prompts", "associatedPromptIds"),
            "resources": _server_association_count(server, "associatedResources", "associated_resources", "associatedResourceIds"),
        }
    return summary


def _approval_blocked(profile: dict[str, Any]) -> bool:
    return str(profile.get("approval_state", "")).startswith("blocked_")


def _unsafe_live_default(default_url: str, target_url: str) -> bool:
    return default_url.startswith("http://127.0.0.1:910") and target_url != default_url


def build_plan(
    *,
    manifests_root: Path = SERVER_INSTANCES,
    baseline_readback_path: Path | None = None,
    target_readback_path: Path | None = None,
    target_base_url: str = DEFAULT_TARGET_BASE_URL,
    target_env_file: str = DEFAULT_TARGET_ENV_FILE,
) -> dict[str, Any]:
    baseline = _read_json(baseline_readback_path)
    current = _read_json(target_readback_path)
    registry = registry_plan.build_plan(manifests_root=manifests_root)
    current_server_names = _row_names(_endpoint_rows(current, "docker_4445", "servers"))
    baseline_server_names = _row_names(_endpoint_rows(baseline, "host_4444", "servers"))
    services: list[dict[str, Any]] = []

    for service in registry["services"]:
        slug = service["slug"]
        defaults = registry_plan.CANONICAL_SERVICE_DEFAULTS.get(slug)
        profile = DOCKER_TARGET_PROFILE.get(slug)
        if not defaults or not profile:
            continue
        target_url = str(profile["target_upstream_url"])
        default_url = str(defaults["url"])
        services.append(
            {
                "slug": slug,
                "canonical_gateway_name": defaults["gateway_name"],
                "canonical_server_name": defaults["server_name"],
                "expected_tool_names": service.get("expected_tool_names", []),
                "baseline_server_present": defaults["server_name"] in baseline_server_names if baseline else None,
                "current_4445_server_present": defaults["server_name"] in current_server_names if current else None,
                "current_4445_dev_name_collision": (
                    slug == "mentality" and "mentality_dev_docker_server" in current_server_names
                ),
                "locality": profile["locality"],
                "default_live_upstream_url": default_url,
                "target_upstream_url": target_url,
                "approval_state": profile["approval_state"],
                "approval_blocked": _approval_blocked(profile),
                "docker_projection_required": target_url != default_url,
                "unsafe_to_reuse_live_default": _unsafe_live_default(default_url, target_url),
                "helper": service.get("helper"),
                "notes": profile["notes"],
            }
        )

    endpoint_gaps = {
        endpoint: _name_gap(baseline, current, endpoint)
        for endpoint in ("servers", "tools", "prompts", "resources")
    }
    baseline_prompt_tags = _tool_guidance_tags(_endpoint_rows(baseline, "host_4444", "prompts"))
    baseline_resource_tags = _tool_guidance_tags(_endpoint_rows(baseline, "host_4444", "resources"))
    target_prompt_tags = _tool_guidance_tags(_endpoint_rows(current, "docker_4445", "prompts"))
    target_resource_tags = _tool_guidance_tags(_endpoint_rows(current, "docker_4445", "resources"))
    baseline_prompt_missing = EXPECTED_TOOL_GUIDANCE_TAGS - baseline_prompt_tags
    baseline_resource_missing = EXPECTED_TOOL_GUIDANCE_TAGS - baseline_resource_tags
    target_prompt_missing = baseline_prompt_tags - target_prompt_tags
    target_resource_missing = baseline_resource_tags - target_resource_tags

    return {
        "schema_uri": SCHEMA_URI,
        "mutation_performed": False,
        "target_surface": {
            "base_url": target_base_url,
            "env_file": str((REPO_ROOT / target_env_file).resolve()),
            "env_values_read": False,
        },
        "sources": {
            "manifests_root": str(manifests_root),
            "baseline_readback": str(baseline_readback_path) if baseline_readback_path else None,
            "target_readback": str(target_readback_path) if target_readback_path else None,
        },
        "summary": {
            "target_service_count": len(services),
            "baseline_counts": _counts(baseline, "host_4444"),
            "current_4445_counts": _counts(current, "docker_4445"),
            "approval_blocked_services": sorted(service["slug"] for service in services if service["approval_blocked"]),
            "unsafe_live_default_services": sorted(service["slug"] for service in services if service["unsafe_to_reuse_live_default"]),
            "current_4445_server_associations": _current_server_summary(current),
        },
        "endpoint_gaps": endpoint_gaps,
        "guidance_tag_gap": {
            "expected_source_tool_guidance_tags": len(EXPECTED_TOOL_GUIDANCE_TAGS),
            "baseline_prompt_tool_guidance_tags": len(baseline_prompt_tags),
            "baseline_resource_tool_guidance_tags": len(baseline_resource_tags),
            "target_prompt_tool_guidance_tags": len(target_prompt_tags),
            "target_resource_tool_guidance_tags": len(target_resource_tags),
            "baseline_prompt_tags_missing_expected_source": sorted(baseline_prompt_missing),
            "baseline_resource_tags_missing_expected_source": sorted(baseline_resource_missing),
            "baseline_prompt_tools_missing_expected_source": _tool_names_for_tags(baseline_prompt_missing),
            "baseline_resource_tools_missing_expected_source": _tool_names_for_tags(baseline_resource_missing),
            "prompt_tags_missing_on_4445": sorted(target_prompt_missing),
            "resource_tags_missing_on_4445": sorted(target_resource_missing),
            "prompt_tools_missing_on_4445": _tool_names_for_tags(target_prompt_missing),
            "resource_tools_missing_on_4445": _tool_names_for_tags(target_resource_missing),
        },
        "helper_dispositions": HELPER_DISPOSITIONS,
        "services": services,
        "recommended_ordered_slices": [
            "parameterize target/auth inputs for 4445 without using 4444 wrapper defaults",
            "materialize Docker locality profile for each canonical service",
            "register canonical sidecar-proven services first: context7, mentality, playwright, and exa-search after env preflight where applicable",
            "add or approve service-specific reachable topology for remaining credential and single-user services",
            "register remote OpenZeppelin directly",
            "replay tool guidance using 4445-discovered gateway IDs and canonical tool tags",
            "handle project-scoped Serena only after explicit runtime/project-state approval",
            "rerun authenticated full readback and tag-based parity reconciliation",
        ],
        "non_actions": [
            "read-only plan; no ContextForge API calls",
            "read-only plan; no Docker, service, systemd, or process mutation",
            "read-only plan; no token creation, revocation, or secret value output",
            "read-only plan; no database reads or writes",
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifests-root", type=Path, default=SERVER_INSTANCES)
    parser.add_argument("--baseline-readback", type=Path)
    parser.add_argument("--target-readback", type=Path)
    parser.add_argument("--target-base-url", default=DEFAULT_TARGET_BASE_URL)
    parser.add_argument("--target-env-file", default=DEFAULT_TARGET_ENV_FILE)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(
        json.dumps(
            build_plan(
                manifests_root=args.manifests_root,
                baseline_readback_path=args.baseline_readback,
                target_readback_path=args.target_readback,
                target_base_url=args.target_base_url,
                target_env_file=args.target_env_file,
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
