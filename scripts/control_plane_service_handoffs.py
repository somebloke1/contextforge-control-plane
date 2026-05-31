#!/usr/bin/env python3
"""Pure service-management handoff builders for ContextForge control-plane use."""

from __future__ import annotations

import copy
import re
from collections.abc import Mapping
from typing import Any

import control_plane_contracts as contracts
import control_plane_redaction as redaction


SCHEMA_URI = "contextforge://control-plane/schemas/service-management-handoff/v1"
DEFAULT_FORBIDDEN_EFFECTS = (
    "catalog_promotion",
    "project_state_service_record",
    "contextforge_registration",
    "backend_provision",
)
REPAIR_FORBIDDEN_EFFECTS = (*DEFAULT_FORBIDDEN_EFFECTS, "direct_catalog_repair")
VALID_SOURCES = frozenset({"project_init", "catalog_read", "user_request"})
VALID_RUNTIME_SCOPES = frozenset({"host", "project", "credential", "caller", "session", "unknown"})
VALID_TRANSPORT_SCOPES = frozenset({"stdio", "http", "sse", "rest", "unknown"})


class ServiceHandoffInputError(ValueError):
    """Raised when a handoff descriptor is malformed."""


def build_catalog_candidate_handoff(
    descriptor: Mapping[str, Any],
    *,
    project_root: str | None = None,
    source: str = "project_init",
    reason: str = "catalog_candidate",
) -> dict[str, Any]:
    """Build a redacted handoff for an uncataloged backend candidate."""

    return build_service_management_handoff(
        descriptor,
        project_root=project_root,
        source=source,
        handoff_class="catalog_candidate",
        reason=reason,
        forbidden_under_current_approval=DEFAULT_FORBIDDEN_EFFECTS,
    )


def build_catalog_repair_handoff(
    descriptor: Mapping[str, Any],
    *,
    project_root: str | None = None,
    source: str = "catalog_read",
    reason: str = "catalog_repair_need",
    repair_need: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a redacted handoff for catalog repair that project init cannot perform."""

    return build_service_management_handoff(
        descriptor,
        project_root=project_root,
        source=source,
        handoff_class="catalog_repair_need",
        reason=reason,
        repair_need=repair_need,
        forbidden_under_current_approval=REPAIR_FORBIDDEN_EFFECTS,
    )


def build_service_management_handoff(
    descriptor: Mapping[str, Any],
    *,
    project_root: str | None = None,
    source: str = "project_init",
    handoff_class: str,
    reason: str,
    repair_need: Mapping[str, Any] | None = None,
    forbidden_under_current_approval: tuple[str, ...] = DEFAULT_FORBIDDEN_EFFECTS,
) -> dict[str, Any]:
    """Build and validate a service-management handoff without side effects."""

    if not isinstance(descriptor, Mapping):
        raise ServiceHandoffInputError("descriptor must be a mapping")
    if repair_need is not None and not isinstance(repair_need, Mapping):
        raise ServiceHandoffInputError("repair_need must be a mapping when supplied")

    descriptor_copy = _json_compatible_copy(descriptor)
    backend = _mapping(descriptor_copy.get("backend"))
    scope = _mapping(descriptor_copy.get("scope"))
    identity = _handoff_identity(descriptor_copy, backend)
    handoff = {
        "handoff_id": _identifier("handoff", f"{handoff_class}-{identity}"),
        "schema_uri": SCHEMA_URI,
        "source": source if source in VALID_SOURCES else "project_init",
        "project_root": project_root,
        "candidate_descriptor": _redact_for_contract(descriptor_copy),
        "redaction_status": "redacted",
        "dedupe_keys": _dedupe_keys(descriptor_copy, backend, scope),
        "suspected_instantiation_class": "candidate_or_uncataloged_backend",
        "required_next_workflow": "service_management_plan",
        "forbidden_under_current_approval": _unique(forbidden_under_current_approval),
        "x_handoff_class": handoff_class,
        "x_handoff_reason": reason,
    }
    discovery_evidence = _discovery_evidence(descriptor_copy)
    if discovery_evidence:
        handoff["x_discovery_evidence"] = discovery_evidence
    if repair_need is not None:
        handoff["x_repair_need"] = _redact_for_contract(_json_compatible_copy(repair_need))

    contracts.validate_artifact("service_management_handoff", handoff)
    return handoff


def _dedupe_keys(
    descriptor: Mapping[str, Any],
    backend: Mapping[str, Any],
    scope: Mapping[str, Any],
) -> dict[str, Any]:
    backend_package = _first_string(
        descriptor.get("backend_package"),
        backend.get("package"),
        backend.get("command"),
        descriptor.get("package"),
        descriptor.get("command"),
    )
    dedupe = {
        "backend_package": backend_package,
        "runtime_scope": _runtime_scope(scope),
        "credential_scope": _scope_label(scope.get("credential_scope") or descriptor.get("credential_scope")),
        "resource_scope": _scope_label(scope.get("resource_scope") or descriptor.get("resource_scope")),
        "transport_scope": _transport_scope(backend, descriptor),
    }
    backend_command = _first_string(backend.get("command"), descriptor.get("command"))
    if backend_command and backend_command != backend_package:
        dedupe["x_backend_command"] = backend_command
    service_family = _first_string(descriptor.get("service_family"), descriptor.get("family"))
    canonical_service = _first_string(descriptor.get("canonical_service"), descriptor.get("canonical_name"))
    if service_family:
        dedupe["x_service_family"] = service_family
    if canonical_service:
        dedupe["x_canonical_service"] = canonical_service
    return dedupe


def _runtime_scope(scope: Mapping[str, Any]) -> str:
    runtime_scope = scope.get("runtime_scope")
    if runtime_scope in VALID_RUNTIME_SCOPES:
        return str(runtime_scope)
    if scope.get("requires_local_project_scope") or scope.get("workspace_root"):
        return "project"
    if scope.get("credential_scope"):
        return "credential"
    if scope.get("caller_scope"):
        return "caller"
    if scope.get("session_scope"):
        return "session"
    return "unknown"


def _transport_scope(backend: Mapping[str, Any], descriptor: Mapping[str, Any]) -> str:
    transport = _first_string(backend.get("transport"), descriptor.get("transport"))
    normalized = _transport_name(transport) if transport else None
    if normalized == "streamable_http":
        return "http"
    if normalized in VALID_TRANSPORT_SCOPES:
        return normalized
    native = _as_list(descriptor.get("native_transports")) or _as_list(backend.get("native_transports"))
    normalized_native = [_transport_name(item) for item in native if isinstance(item, str)]
    if "streamable_http" in normalized_native or "http" in normalized_native:
        return "http"
    for value in ("sse", "stdio", "rest"):
        if value in normalized_native:
            return value
    return "unknown"


def _scope_label(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return "<redacted>" if redaction.classify_sensitive_value(value) else value
    if isinstance(value, Mapping):
        label = _first_string(value.get("id"), value.get("name"), value.get("scope"), value.get("tenant"), value.get("resource"))
        return _scope_label(label) if label else "explicit"
    if isinstance(value, bool | int | float):
        return str(value)
    return "explicit"


def _discovery_evidence(descriptor: Mapping[str, Any]) -> dict[str, Any]:
    evidence: dict[str, Any] = {}
    client_config_names = _string_list(descriptor.get("client_config_names"))
    if client_config_names:
        evidence["client_config_names"] = client_config_names
        evidence["identity_policy"] = "client config names are discovery evidence only"
    source_clients = _string_list(descriptor.get("source_clients"))
    if source_clients:
        evidence["source_clients"] = source_clients
    return evidence


def _handoff_identity(descriptor: Mapping[str, Any], backend: Mapping[str, Any]) -> str:
    return (
        _first_string(
            descriptor.get("canonical_service"),
            descriptor.get("service_family"),
            descriptor.get("candidate_name"),
            backend.get("package"),
            backend.get("command"),
            descriptor.get("package"),
            descriptor.get("command"),
        )
        or "uncataloged"
    )


def _redact_for_contract(value: Any) -> Any:
    if isinstance(value, Mapping):
        output = {}
        for key, child in value.items():
            key_str = str(key)
            if redaction.classify_sensitive_key(key_str):
                output[key_str] = "<redacted>"
            else:
                output[key_str] = _redact_for_contract(child)
        return output
    if isinstance(value, list):
        return [_redact_for_contract(item) for item in value]
    if isinstance(value, str) and redaction.classify_sensitive_value(value):
        return "<redacted>"
    return copy.deepcopy(value)


def _json_compatible_copy(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_compatible_copy(child) for key, child in value.items()}
    if isinstance(value, tuple):
        return [_json_compatible_copy(item) for item in value]
    if isinstance(value, list):
        return [_json_compatible_copy(item) for item in value]
    if value is None or isinstance(value, str | bool | int | float):
        return copy.deepcopy(value)
    return str(value)


def _mapping(value: Any) -> dict[str, Any]:
    return copy.deepcopy(dict(value)) if isinstance(value, Mapping) else {}


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if value is None:
        return []
    return [value]


def _string_list(value: Any) -> list[str]:
    return sorted({item for item in _as_list(value) if isinstance(item, str) and item})


def _first_string(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value:
            return value
    return None


def _transport_name(value: str) -> str:
    normalized = value.lower().replace("-", "_")
    if normalized in {"streamable_http", "mcp_http"}:
        return "streamable_http"
    return normalized


def _unique(values: tuple[str, ...]) -> list[str]:
    output = []
    seen = set()
    for value in values:
        if value not in seen:
            output.append(value)
            seen.add(value)
    return output


def _identifier(prefix: str, value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.:/@+-]+", "-", f"{prefix}-{value}".strip())
    slug = re.sub(r"-+", "-", slug).strip("-")
    if not slug:
        slug = "unknown"
    if not re.match(r"^[A-Za-z0-9]", slug):
        slug = f"id-{slug}"
    return slug


__all__ = [
    "ServiceHandoffInputError",
    "build_catalog_candidate_handoff",
    "build_catalog_repair_handoff",
    "build_service_management_handoff",
]
