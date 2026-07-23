#!/usr/bin/env python3
"""Seed ContextForge service-offering Resources from local migration manifests.

This is an operator migration script, not product runtime discovery.  It reads
``server-instances/*/instance.json`` only to seed or refresh ContextForge-hosted
service-offering metadata Resources.  The helper runtime must discover ordinary
service offerings from ContextForge Resources, not from these local manifests.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

# Keep direct script execution and test imports working with this repo's scripts/ layout.
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import contextforge_mcp_wrapper as gateway  # noqa: E402
import project_init_common as common  # noqa: E402

OWNER = "admin@contextforge.dev"
VISIBILITY = "public"
RESOURCE_URI_TEMPLATE = "contextforge://control-plane/service-offerings/{offering_id}/v1"
RESOURCE_NAME_TEMPLATE = "service_offering_{safe_offering_id}_v1"
SERVICE_OFFERING_TAGS = ["contextforge-service-offering", "service-offering"]
STANDARD_ACTIONS = ["list", "enable", "disable", "remove", "repair", "details"]
CANONICAL_SEED_SERVICES = {
    "chrome-devtools",
    "context7",
    "exa-search",
    "github",
    "mentality",
    "openzeppelin-solidity-contracts",
    "playwright",
    "serena",
    "ssh-tmux",
    "time",
    "web-search",
}
SERVICE_ALIASES = {
    "openzeppelin": "openzeppelin-solidity-contracts",
    "openzeppelin-solidity": "openzeppelin-solidity-contracts",
}
SECRET_KEY_FRAGMENTS = ("token", "password", "secret", "api_key", "apikey", "private_key", "client_secret")
UUIDISH_RE = re.compile(r"^[0-9a-fA-F]{32}$|^[0-9a-fA-F-]{36}$")
TARGET_BASE_URL: str | None = None
TARGET_ENV_FILE: Path | None = None
TARGET_TOKEN: str | None = None


@dataclass
class PlannedOffering:
    offering_id: str
    service_family: str
    instance_dir: str
    instance_path: str
    server_id: str
    resource_uri: str
    resource_body: dict[str, Any]
    metadata: dict[str, Any]


@dataclass
class MigrationReport:
    created: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    associated: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)
    planned: list[dict[str, Any]] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return {
            "created": len(self.created),
            "updated": len(self.updated),
            "unchanged": len(self.unchanged),
            "associated": len(self.associated),
            "skipped": len(self.skipped),
            "errors": len(self.errors),
            "created_services": self.created,
            "updated_services": self.updated,
            "unchanged_services": self.unchanged,
            "associated_services": self.associated,
            "skipped_services": self.skipped,
            "error_details": self.errors,
            "planned": self.planned,
        }


def _base_url() -> str:
    return (TARGET_BASE_URL or common.contextforge_base_url()).rstrip("/")


def _target_login_token(base_url: str, email: str, password: str) -> str:
    for login_path in ("/auth/login", "/auth/email/login"):
        request = urllib.request.Request(
            f"{base_url.rstrip('/')}{login_path}",
            data=json.dumps({"email": email, "password": password}).encode("utf-8"),
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.loads(response.read())
        except urllib.error.HTTPError as exc:
            if exc.code in {404, 405}:
                continue
            raise
        token = payload.get("access_token") if isinstance(payload, dict) else None
        if isinstance(token, str) and token:
            return token
    raise RuntimeError(f"ContextForge login did not return an access token for {base_url.rstrip('/')}")


def _token() -> str:
    global TARGET_TOKEN
    if TARGET_TOKEN:
        return TARGET_TOKEN
    env_path = TARGET_ENV_FILE or common.contextforge_env_path()
    if env_path is None or not env_path.exists():
        raise RuntimeError("no ContextForge client-scoped env file was found")
    env = gateway._read_env(env_path)
    bearer = str(env.get("CONTEXTFORGE_BEARER_TOKEN") or "").removeprefix("Bearer ").strip()
    if bearer:
        TARGET_TOKEN = bearer
        return TARGET_TOKEN
    email = str(env.get("PLATFORM_ADMIN_EMAIL") or "")
    password = str(env.get("PLATFORM_ADMIN_PASSWORD") or "")
    if not email or not password:
        raise RuntimeError(f"missing ContextForge credentials in {env_path}")
    if TARGET_BASE_URL:
        TARGET_TOKEN = _target_login_token(_base_url(), email, password)
    else:
        TARGET_TOKEN = gateway._token(email, password)
    return TARGET_TOKEN


def _request(method: str, path: str, *, body: dict[str, Any] | None = None) -> Any:
    headers = {"Accept": "application/json"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    token = _token()
    headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(f"{_base_url()}{path}", headers=headers, method=method, data=data)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = response.read()
        return json.loads(payload) if payload else None
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {_safe_error_text(error_body)}") from exc


def _api_items(path: str) -> list[dict[str, Any]]:
    data = _request("GET", path)
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        return [item for item in data["items"] if isinstance(item, dict)]
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return []


def _safe_error_text(text: str) -> str:
    redacted = text
    for fragment in SECRET_KEY_FRAGMENTS:
        redacted = redacted.replace(fragment.upper(), f"{fragment.upper()}[REDACTED]")
    return redacted[:1000]


def _ids(entity: Mapping[str, Any], *keys: str, uuid_only: bool = False) -> set[str]:
    values: set[str] = set()
    for key in keys:
        raw = entity.get(key)
        if not isinstance(raw, list):
            continue
        for item in raw:
            if isinstance(item, Mapping):
                value = item.get("id")
            else:
                value = item
            if value is not None and str(value) and (not uuid_only or UUIDISH_RE.match(str(value))):
                values.add(str(value))
    return values


def _association_ids(entity: Mapping[str, Any], id_key: str, fallback_key: str) -> set[str]:
    explicit = _ids(entity, id_key, uuid_only=True)
    if explicit:
        return explicit
    return _ids(entity, fallback_key, uuid_only=True)


def _tag_values(raw: Any) -> set[str]:
    if not isinstance(raw, list):
        return set()
    tags: set[str] = set()
    for item in raw:
        if isinstance(item, Mapping):
            value = item.get("label") or item.get("name") or item.get("id")
        else:
            value = item
        if value is not None and str(value):
            tags.add(str(value))
    return tags


def _read_instance(path: Path) -> dict[str, Any] | None:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _service_family(instance: Mapping[str, Any]) -> str:
    # Serena project instances carry service=serena and slug=<instance slug>.
    # The offering is the service family, not the instance directory slug.
    for key in ("service", "service_family", "canonical_service", "slug", "name"):
        value = str(instance.get(key) or "").strip()
        if value:
            return SERVICE_ALIASES.get(value, value)
    return ""


def _display_name(instance: Mapping[str, Any], service_family: str) -> str:
    value = str(instance.get("display_name") or instance.get("name") or service_family).strip()
    if not value:
        value = service_family
    words = value.replace("_", " ").replace("-", " ").split()
    return " ".join(word.upper() if word.lower() in {"ssh", "mcp"} else word[:1].upper() + word[1:] for word in words)


def _aliases(instance: Mapping[str, Any], service_family: str, display_name: str) -> list[str]:
    raw = {
        service_family,
        display_name.lower().replace(" ", "-"),
        str(instance.get("name") or ""),
        str(instance.get("slug") or ""),
        str(instance.get("service") or ""),
        str(instance.get("codex_alias") or ""),
    }
    if service_family == "openzeppelin-solidity-contracts":
        raw.add("openzeppelin")
    return sorted(value for value in raw if value)


def _scope_model(instance: Mapping[str, Any], instantiation_class: str) -> str:
    declared = str(instance.get("scope_model") or "").strip()
    if declared in {"global", "per_project", "per_user"}:
        return declared
    if instantiation_class == "instance_per_project":
        return "per_project"
    if instantiation_class in {"credential_scoped", "per_user"}:
        return "per_user"
    return "global"


def _required_context(instance: Mapping[str, Any], scope_model: str, instantiation_class: str) -> dict[str, str]:
    if scope_model == "per_project":
        return {"project_root": "required"}
    scope = instance.get("scope") if isinstance(instance.get("scope"), Mapping) else {}
    scope_type = str(scope.get("scope_type") or "")
    if scope_type == "caller_supplied_local_repo":
        return {"project_root": "request_context_required"}
    if instantiation_class == "credential_scoped":
        return {"credential_scope": "required"}
    if instantiation_class == "session_scoped":
        return {"session_scope": "required"}
    return {}


def _instantiation_class(instance: Mapping[str, Any]) -> str:
    declared = str(instance.get("instantiation_class") or "").strip()
    if declared:
        return declared
    # Migration should preserve existing service behavior.  These helpers are
    # manifest-derived migration logic, not runtime product discovery.
    return common._manifest_instantiation_class(dict(instance))


def _binding(instance: Mapping[str, Any], service_family: str, instantiation_class: str) -> dict[str, str]:
    declared = str(instance.get("service_binding") or "").strip()
    if declared:
        return {"mode": "literal", "value": declared}
    if instantiation_class == "instance_per_project":
        return {"mode": "project_hash_template", "template": f"{service_family}:{{project_hash_12}}"}
    binding = common._manifest_service_binding(dict(instance), service_family, instantiation_class, instance.get("canonical_project_root"))
    return {"mode": "literal", "value": binding}


def _contextforge_runtime(instance: Mapping[str, Any]) -> tuple[str, str, str, str]:
    cf = instance.get("contextforge") if isinstance(instance.get("contextforge"), Mapping) else {}
    gateway_row = cf.get("gateway") if isinstance(cf.get("gateway"), Mapping) else {}
    server_row = cf.get("virtual_server") if isinstance(cf.get("virtual_server"), Mapping) else {}
    server_id = str(server_row.get("id") or cf.get("server_id") or "").strip()
    server_name = str(server_row.get("name") or instance.get("server_name") or "").strip()
    gateway_id = str(gateway_row.get("id") or cf.get("gateway_id") or "").strip()
    gateway_name = str(gateway_row.get("name") or cf.get("gateway_name") or "").strip()
    return server_id, server_name, gateway_id, gateway_name


def _metadata_from_instance(instance: Mapping[str, Any], *, instance_dir: str) -> dict[str, Any]:
    service_family = _service_family(instance)
    instantiation_class = _instantiation_class(instance)
    scope_model = _scope_model(instance, instantiation_class)
    server_id, server_name, gateway_id, gateway_name = _contextforge_runtime(instance)
    display_name = _display_name(instance, service_family)
    scope = instance.get("scope") if isinstance(instance.get("scope"), Mapping) else {}
    scope_type = str(scope.get("scope_type") or scope_model)
    description = str(instance.get("description") or scope.get("notes") or f"{display_name} service.").strip()
    required_context = _required_context(instance, scope_model, instantiation_class)
    client_support = {"pi": True, "opencode": True, "codex": False}
    resource_uri = RESOURCE_URI_TEMPLATE.format(offering_id=service_family)
    return {
        "schema_uri": common.SERVICE_OFFERING_SCHEMA_URI,
        "metadata_version": 1,
        "resource_uri": resource_uri,
        "offering_id": service_family,
        "service_family": service_family,
        "display_name": display_name,
        "description": description,
        "aliases": _aliases(instance, service_family, display_name),
        "scope_model": scope_model,
        "scope_type": scope_type,
        "scope_label": scope_type.replace("_", " "),
        "instantiation_class": instantiation_class,
        "instance_model": instantiation_class,
        "binding": _binding(instance, service_family, instantiation_class),
        "runtime": {
            "server_id": server_id,
            "server_name": server_name,
            "gateway_id": gateway_id,
            "gateway_name": gateway_name,
            "reload_required": True,
        },
        "helper": {
            "actions_supported": STANDARD_ACTIONS,
            "required_context": required_context,
            "client_support": client_support,
        },
        "required_context": required_context,
        "client_support": client_support,
        "reload_required": True,
        "guidance": {
            "abstract_resource_uri": f"contextforge://control-plane/guidance/{service_family}/abstract/v1",
            "detail_resource_uri": f"contextforge://control-plane/guidance/{service_family}/detail/v1",
        },
        "lifecycle": "active",
        "provenance": {
            "source": "server-instances migration seed",
            "seed_instance_dir": instance_dir,
            "migration_schema_version": 1,
        },
    }


def _resource_body(metadata: Mapping[str, Any]) -> dict[str, Any]:
    offering_id = str(metadata["offering_id"])
    safe_offering_id = offering_id.replace("-", "_")
    return {
        "uri": str(metadata["resource_uri"]),
        "name": RESOURCE_NAME_TEMPLATE.format(safe_offering_id=safe_offering_id),
        "title": f"Service offering: {metadata['display_name']}",
        "description": str(metadata.get("description") or f"{offering_id} service offering metadata"),
        "mimeType": "application/json",
        "content": json.dumps(metadata, sort_keys=True, separators=(",", ":")),
        "tags": sorted(set(SERVICE_OFFERING_TAGS) | {offering_id}),
        "visibility": VISIBILITY,
        "owner_email": OWNER,
    }


def _validate_metadata(metadata: Mapping[str, Any]) -> list[str]:
    return common._service_offering_metadata_errors(metadata)  # intentional contract reuse by migration tests


def _planned_offerings(selected_services: set[str] | None = None) -> tuple[list[PlannedOffering], list[str]]:
    planned_by_offering: dict[str, PlannedOffering] = {}
    skipped: list[str] = []
    for entry in sorted(common.SERVER_INSTANCES_ROOT.iterdir()):
        instance_path = entry / "instance.json"
        if not entry.is_dir() or not instance_path.exists():
            continue
        instance = _read_instance(instance_path)
        if not instance:
            skipped.append(f"{entry.name}: unreadable instance.json")
            continue
        service_family = _service_family(instance)
        if selected_services and service_family not in selected_services and entry.name not in selected_services:
            continue
        if service_family not in CANONICAL_SEED_SERVICES:
            skipped.append(f"{entry.name}: service family {service_family or '<unknown>'} is not in canonical seed set")
            continue
        metadata = _metadata_from_instance(instance, instance_dir=entry.name)
        errors = _validate_metadata(metadata)
        migration_errors = [
            error
            for error in errors
            if error != "missing runtime.server_id"
            or not str((metadata.get("runtime") or {}).get("server_name") or "")
        ]
        if migration_errors:
            skipped.append(f"{entry.name}: invalid metadata: {', '.join(migration_errors)}")
            continue
        server_id = str(metadata["runtime"]["server_id"])
        offering = PlannedOffering(
            offering_id=str(metadata["offering_id"]),
            service_family=service_family,
            instance_dir=entry.name,
            instance_path=str(instance_path.relative_to(common.REPO_ROOT)),
            server_id=server_id,
            resource_uri=str(metadata["resource_uri"]),
            resource_body=_resource_body(metadata),
            metadata=dict(metadata),
        )
        existing = planned_by_offering.get(offering.offering_id)
        if existing:
            skipped.append(f"{entry.name}: duplicate offering_id {offering.offering_id}; keeping {existing.instance_dir}")
            continue
        planned_by_offering[offering.offering_id] = offering
    return list(planned_by_offering.values()), skipped


def _resource_by_uri(resources: Iterable[dict[str, Any]], uri: str) -> dict[str, Any] | None:
    for resource in resources:
        if str(resource.get("uri") or "") == uri:
            return resource
    return None


def _resource_content(resource: Mapping[str, Any]) -> dict[str, Any]:
    content = resource.get("content")
    if isinstance(content, Mapping):
        return dict(content)
    if isinstance(content, str):
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _resource_matches_offering(resource: Mapping[str, Any] | None, offering: PlannedOffering) -> bool:
    return bool(resource) and _resource_content(resource or {}) == offering.metadata


def _hydrate_service_offering_resources(resources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    hydrated: list[dict[str, Any]] = []
    for resource in resources:
        row = resource
        uri = str(resource.get("uri") or "")
        resource_id = str(resource.get("id") or "")
        if uri.startswith("contextforge://control-plane/service-offerings/") and resource_id and not resource.get("content"):
            detail = _request("GET", f"/resources/{resource_id}")
            if isinstance(detail, dict):
                row = {**resource, **detail}
        hydrated.append(row)
    return hydrated


def _server_by_id(servers: Iterable[dict[str, Any]], server_id: str) -> dict[str, Any] | None:
    for server in servers:
        if str(server.get("id") or "") == server_id:
            return server
    return None


def _server_by_name(servers: Iterable[dict[str, Any]], server_name: str) -> dict[str, Any] | None:
    for server in servers:
        if str(server.get("name") or "") == server_name:
            return server
    return None


def _gateway_by_name(gateways: Iterable[dict[str, Any]], gateway_name: str) -> dict[str, Any] | None:
    for gateway_row in gateways:
        if str(gateway_row.get("name") or "") == gateway_name:
            return gateway_row
    return None


def _with_live_runtime(offering: PlannedOffering, servers: list[dict[str, Any]], gateways: list[dict[str, Any]]) -> PlannedOffering:
    """Return an offering whose runtime.server_id matches the live CF server.

    Local instance.json IDs can be stale after registry rebuilds.  Names are
    migration hints only; the metadata written to ContextForge must contain the
    live server ID that will be used as the runtime anchor by the helper.
    """
    server_name = str(offering.metadata.get("runtime", {}).get("server_name") or "")
    live = _server_by_id(servers, offering.server_id) or _server_by_name(servers, server_name)
    if not live:
        raise RuntimeError(f"server {offering.server_id} / {server_name or '<unnamed>'} was not found for {offering.offering_id}")
    metadata = dict(offering.metadata)
    runtime = dict(metadata.get("runtime") or {})
    runtime["server_id"] = str(live["id"])
    gateway_name = str(runtime.get("gateway_name") or "")
    gateway_row = _gateway_by_name(gateways, gateway_name) if gateway_name else None
    if gateway_row is None:
        gateway_row = common._matching_gateway(live, gateways)
    if gateway_row and gateway_row.get("id"):
        runtime["gateway_id"] = str(gateway_row["id"])
        runtime["gateway_name"] = str(gateway_row.get("name") or gateway_name)
    metadata["runtime"] = runtime
    metadata_errors = _validate_metadata(metadata)
    if metadata_errors:
        raise RuntimeError(
            f"resolved metadata for {offering.offering_id} is invalid: {', '.join(metadata_errors)}"
        )
    return PlannedOffering(
        offering_id=offering.offering_id,
        service_family=offering.service_family,
        instance_dir=offering.instance_dir,
        instance_path=offering.instance_path,
        server_id=str(live["id"]),
        resource_uri=offering.resource_uri,
        resource_body=_resource_body(metadata),
        metadata=metadata,
    )


def _upsert_resource(offering: PlannedOffering, resources: list[dict[str, Any]]) -> tuple[str, str]:
    existing = _resource_by_uri(resources, offering.resource_uri)
    if existing:
        resource_id = str(existing["id"])
        if _resource_matches_offering(existing, offering):
            return "unchanged", resource_id
        _request("PUT", f"/resources/{resource_id}", body=offering.resource_body)
        return "updated", resource_id
    created = _request("POST", "/resources", body={"resource": offering.resource_body, "visibility": VISIBILITY})
    if not isinstance(created, Mapping) or not created.get("id"):
        raise RuntimeError(f"resource create for {offering.offering_id} did not return an id")
    return "created", str(created["id"])


def _associate_resource(offering: PlannedOffering, resource_id: str, servers: list[dict[str, Any]]) -> None:
    server = _server_by_id(servers, offering.server_id)
    if not server:
        raise RuntimeError(f"server {offering.server_id} was not found for {offering.offering_id}")
    resources = _association_ids(server, "associatedResourceIds", "associatedResources")
    resources.add(resource_id)
    body = {
        "associatedTools": sorted(_association_ids(server, "associatedToolIds", "associatedTools")),
        "associatedResources": sorted(resources),
        "associatedPrompts": sorted(_association_ids(server, "associatedPromptIds", "associatedPrompts")),
        "associatedA2aAgents": sorted(_association_ids(server, "associatedA2aAgentIds", "associatedA2aAgents")),
        "ownerEmail": str(server.get("ownerEmail") or server.get("owner_email") or OWNER),
        "visibility": str(server.get("visibility") or VISIBILITY),
    }
    tags = _tag_values(server.get("tags"))
    if tags:
        body["tags"] = sorted(tags)
    _request("PUT", f"/servers/{offering.server_id}", body=body)


def _normalize_selected_services(values: list[str] | None) -> set[str] | None:
    if not values:
        return None
    return {SERVICE_ALIASES.get(value, value) for value in values}


def migrate(*, dry_run: bool = False, services: list[str] | None = None) -> MigrationReport:
    report = MigrationReport()
    selected = _normalize_selected_services(services)
    offerings, skipped = _planned_offerings(selected)
    report.skipped.extend(skipped)
    resources = _hydrate_service_offering_resources(
        _api_items("/resources?include_inactive=true&limit=1000")
    )
    servers = _api_items("/servers?include_inactive=true&limit=1000")
    gateways = _api_items("/gateways?include_inactive=true&limit=1000")
    resolved: list[tuple[PlannedOffering, str, str]] = []

    # Resolve every target before applying any mutation so an incomplete all-service
    # catalog cannot produce a partial update.
    for raw_offering in offerings:
        try:
            offering = _with_live_runtime(raw_offering, servers, gateways)
            existing_resource = _resource_by_uri(resources, offering.resource_uri)
            server = _server_by_id(servers, offering.server_id)
            existing_resource_id = str((existing_resource or {}).get("id") or "")
            associated_resource_ids = (
                _association_ids(server or {}, "associatedResourceIds", "associatedResources")
                if server
                else set()
            )
            resource_action = (
                "unchanged"
                if _resource_matches_offering(existing_resource, offering)
                else "update" if existing_resource else "create"
            )
            association_action = (
                "preserve"
                if existing_resource_id and existing_resource_id in associated_resource_ids
                else "associate"
            )
            resolved.append((offering, resource_action, association_action))
            report.planned.append(
                {
                    "offering_id": offering.offering_id,
                    "service_family": offering.service_family,
                    "instance_path": offering.instance_path,
                    "resource_uri": offering.resource_uri,
                    "runtime_server_id": offering.server_id,
                    "binding": offering.metadata.get("binding"),
                    "scope_model": offering.metadata.get("scope_model"),
                    "instantiation_class": offering.metadata.get("instantiation_class"),
                    "resource_action": resource_action,
                    "association_action": association_action,
                }
            )
        except Exception as exc:  # report all services without leaking local env values
            report.errors.append({"service": raw_offering.offering_id, "error": _safe_error_text(str(exc))})

    if report.errors and not dry_run:
        report.skipped.append("apply blocked: one or more selected offerings failed live preflight")
        return report

    for offering, resource_action, association_action in resolved:
        if dry_run:
            if resource_action == "unchanged":
                report.unchanged.append(offering.offering_id)
            elif resource_action == "update":
                report.updated.append(offering.offering_id)
            else:
                report.created.append(offering.offering_id)
            if association_action == "associate":
                report.associated.append(offering.offering_id)
            continue

        try:
            action, resource_id = _upsert_resource(offering, resources)
            if action == "unchanged":
                report.unchanged.append(offering.offering_id)
            elif action == "updated":
                report.updated.append(offering.offering_id)
            else:
                report.created.append(offering.offering_id)
            if association_action == "associate":
                _associate_resource(offering, resource_id, servers)
                report.associated.append(offering.offering_id)
        except Exception as exc:
            report.errors.append({"service": offering.offering_id, "error": _safe_error_text(str(exc))})
            break
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Read live target state and print the migration plan without mutating ContextForge.")
    parser.add_argument("--services", nargs="*", help="Limit to service families or aliases, e.g. context7 github openzeppelin serena.")
    parser.add_argument("--base-url", help="Explicit ContextForge target base URL, such as http://127.0.0.1:4445.")
    parser.add_argument("--env-file", type=Path, help="Explicit client-scoped ContextForge env file for the selected target.")
    args = parser.parse_args()
    global TARGET_BASE_URL, TARGET_ENV_FILE, TARGET_TOKEN
    TARGET_BASE_URL = args.base_url.rstrip("/") if args.base_url else None
    TARGET_ENV_FILE = args.env_file.expanduser().resolve() if args.env_file else None
    TARGET_TOKEN = None
    report = migrate(dry_run=args.dry_run, services=args.services)
    output = {
        "schema_uri": "contextforge://diagnostics/service-offering-registration/v1",
        "dry_run": args.dry_run,
        "mutation_performed": bool(
            not args.dry_run and (report.created or report.updated or report.associated)
        ),
        "target": {
            "base_url": _base_url(),
            "env_file": str(TARGET_ENV_FILE or common.contextforge_env_path() or ""),
            "env_values_recorded": False,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **report.to_json(),
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    return 1 if report.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
