#!/usr/bin/env python3
"""Pure service-instantiation classifier for ContextForge control-plane inputs."""

from __future__ import annotations

import copy
import re
from collections.abc import Mapping
from typing import Any

import control_plane_contracts as contracts
import control_plane_redaction as redaction


CLASSIFIER_VERSION = 1
DEFAULT_RESOLVED_AT = "2026-05-30T00:00:00Z"

INSTANTIATION_CLASSES = {
    "instance_per_project",
    "project_scoped_shared_backend",
    "shared_canonical",
    "credential_scoped",
    "resource_scoped",
    "caller_scoped",
    "session_scoped",
    "static_repo_local",
    "candidate_or_uncataloged_backend",
}

SHARED_CAPSULE_CLASSES = {"shared_canonical"}
PROJECT_SCOPED_REUSE_CLASSES = {
    "project_scoped_shared_backend",
    "credential_scoped",
    "resource_scoped",
    "caller_scoped",
    "session_scoped",
    "static_repo_local",
}
NO_PROJECT_DUPLICATION_ACTIONS = [
    "no per-project backend",
    "no per-project gateway",
    "no per-project bridge",
    "no per-project wrapper",
    "no per-project port",
    "no per-project unit",
    "no per-project server-instance directory",
]
CAPSULE_FORBIDDEN_EFFECTS = [
    "new_backend",
    "new_gateway",
    "new_bridge",
    "new_wrapper",
    "new_port",
    "new_unit",
    "server_instance_directory",
    "catalog_mutation",
]
VERIFICATION_LAYERS = {
    "instance_per_project": ["backend", "contextforge_gateway", "virtual_server", "target_client", "tool_policy", "redaction"],
    "project_scoped_shared_backend": ["backend", "contextforge_gateway", "virtual_server", "target_client", "tool_policy", "redaction"],
    "shared_canonical": ["contextforge_gateway", "target_client", "tool_policy", "redaction"],
    "credential_scoped": ["contextforge_gateway", "virtual_server", "target_client", "trust", "tool_policy", "redaction"],
    "resource_scoped": ["contextforge_gateway", "virtual_server", "target_client", "tool_policy", "redaction"],
    "caller_scoped": ["backend", "target_client", "trust", "redaction"],
    "session_scoped": ["backend", "target_client", "trust", "redaction"],
    "static_repo_local": ["backend", "contextforge_gateway", "target_client", "tool_policy", "redaction"],
}


class ClassificationInputError(ValueError):
    """Raised when the classifier receives a malformed descriptor."""


def classify_service_binding(
    descriptor: Mapping[str, Any],
    *,
    project_root: str | None = None,
    source: str = "project_init",
    resolved_at: str = DEFAULT_RESOLVED_AT,
    catalog_revision_or_etag: str | None = None,
) -> dict[str, Any]:
    """Classify one concrete service binding descriptor without side effects.

    The descriptor must already be a manifest or catalog-level service object.
    Client config aliases may be supplied for evidence, but they are deliberately
    ignored for canonical identity.
    """

    if not isinstance(descriptor, Mapping):
        raise ClassificationInputError("descriptor must be a mapping")

    data = copy.deepcopy(dict(descriptor))
    scope = _mapping(data.get("scope"))
    classification = _mapping(data.get("classification"))
    service_family = _canonical_identity(data, scope, "service_family")
    canonical_service = _canonical_identity(data, scope, "canonical_service") or service_family
    client_aliases = _client_aliases(data)

    if _is_candidate(data):
        return _candidate_result(
            data,
            service_family=service_family,
            canonical_service=canonical_service,
            project_root=project_root,
            source=source,
        )

    blockers = []
    if not service_family:
        blockers.append(_blocker("canonical_identity_required", "Catalog/manifest identity is required; client aliases are discovery evidence only."))
    instantiation_class = _explicit_instantiation_class(data, scope, classification)
    if not instantiation_class:
        instantiation_class = _infer_instantiation_class(data, scope, classification)
    if not instantiation_class:
        blockers.append(_blocker("instantiation_class_ambiguous", "Descriptor does not prove a narrow authority boundary."))
    elif instantiation_class not in INSTANTIATION_CLASSES - {"candidate_or_uncataloged_backend"}:
        blockers.append(_blocker("instantiation_class_invalid", f"Unsupported instantiation class: {instantiation_class}"))

    if instantiation_class == "project_scoped_shared_backend" and not _isolation_mechanism(data, scope, classification):
        blockers.append(
            _blocker(
                "isolation_required",
                "project_scoped_shared_backend requires a concrete virtual-server, request-time, allowlist, caller, or service-side isolation mechanism.",
            )
        )
    if service_family and instantiation_class and instantiation_class in INSTANTIATION_CLASSES - {"candidate_or_uncataloged_backend"}:
        supplied_binding_blocker = _supplied_service_binding_blocker(data, service_family, instantiation_class, scope)
        if supplied_binding_blocker:
            blockers.append(supplied_binding_blocker)

    if blockers:
        return _blocked_result(
            data,
            service_family=service_family,
            canonical_service=canonical_service,
            instantiation_class=instantiation_class,
            blockers=blockers,
            client_aliases=client_aliases,
        )

    service_binding = _service_binding(data, service_family, instantiation_class, scope)
    transport_profile = _transport_profile(data)
    scopes = _scope_boundaries(data, scope, classification, instantiation_class, project_root)
    non_actions = _non_actions(instantiation_class, transport_profile, data)
    verification_requirements = _verification_requirements(instantiation_class, transport_profile)
    contract_card = _contract_card(
        data,
        service_family=service_family,
        canonical_service=canonical_service,
        service_binding=service_binding,
        instantiation_class=instantiation_class,
        scopes=scopes,
        transport_profile=transport_profile,
        non_actions=non_actions,
        verification_requirements=verification_requirements,
        resolved_at=resolved_at,
        catalog_revision_or_etag=catalog_revision_or_etag,
    )
    contracts.validate_artifact("service_binding_contract_card", contract_card)

    capsule = None
    if instantiation_class in SHARED_CAPSULE_CLASSES:
        capsule = _shared_capsule(
            data,
            service_family=service_family,
            canonical_service=canonical_service,
            contract_card=contract_card,
            transport_profile=transport_profile,
            verification_requirements=verification_requirements,
            resolved_at=resolved_at,
            catalog_revision_or_etag=catalog_revision_or_etag,
        )
        contracts.validate_artifact("shared_service_capability_capsule", capsule)

    return {
        "schema_version": CLASSIFIER_VERSION,
        "status": "classified",
        "confidence": "high",
        "mutation_allowed": False,
        "durable_project_state_record_allowed": instantiation_class != "candidate_or_uncataloged_backend",
        "service_family": service_family,
        "canonical_service": canonical_service,
        "service_binding": service_binding,
        "instantiation_class": instantiation_class,
        "authority_boundary": contract_card["authority_boundary"],
        "project_scope": scopes["project_scope"],
        "credential_scope": scopes["credential_scope"],
        "resource_scope": scopes["resource_scope"],
        "caller_or_session_scope": scopes["caller_or_session_scope"],
        "scope_boundaries": scopes,
        "transport_profile": transport_profile,
        "blockers": [],
        "non_actions": non_actions,
        "contract_card_draft": contract_card,
        "shared_service_capability_capsule": capsule,
        "service_management_handoff": None,
        "verification_requirements": verification_requirements,
        "identity": {
            "identity_source": "manifest_or_catalog",
            "client_aliases_ignored": client_aliases,
        },
    }


def _candidate_result(
    descriptor: Mapping[str, Any],
    *,
    service_family: str | None,
    canonical_service: str | None,
    project_root: str | None,
    source: str,
) -> dict[str, Any]:
    handoff = _service_management_handoff(
        descriptor,
        service_family=service_family,
        canonical_service=canonical_service,
        project_root=project_root,
        source=source,
    )
    contracts.validate_artifact("service_management_handoff", handoff)
    return {
        "schema_version": CLASSIFIER_VERSION,
        "status": "handoff_required",
        "confidence": "blocked",
        "mutation_allowed": False,
        "durable_project_state_record_allowed": False,
        "service_family": service_family,
        "canonical_service": canonical_service,
        "service_binding": None,
        "instantiation_class": "candidate_or_uncataloged_backend",
        "authority_boundary": "uncataloged backend requires service-management promotion before project init may record a service",
        "project_scope": None,
        "credential_scope": None,
        "resource_scope": None,
        "caller_or_session_scope": None,
        "scope_boundaries": {
            "project_scope": None,
            "credential_scope": None,
            "resource_scope": None,
            "caller_or_session_scope": None,
        },
        "transport_profile": None,
        "blockers": [
            _blocker(
                "service_management_handoff_required",
                "Catalog candidates cannot become durable project-state services under project-init approval.",
            )
        ],
        "non_actions": [
            "do not create project-state service record",
            "do not promote catalog candidate",
            "do not register ContextForge gateway",
            "do not provision backend",
        ],
        "contract_card_draft": None,
        "shared_service_capability_capsule": None,
        "service_management_handoff": handoff,
        "verification_requirements": ["service-management plan approval before registration or project-state recording"],
        "identity": {
            "identity_source": "candidate_descriptor",
            "client_aliases_ignored": _client_aliases(descriptor),
        },
    }


def _blocked_result(
    descriptor: Mapping[str, Any],
    *,
    service_family: str | None,
    canonical_service: str | None,
    instantiation_class: str | None,
    blockers: list[dict[str, str]],
    client_aliases: list[str],
) -> dict[str, Any]:
    return {
        "schema_version": CLASSIFIER_VERSION,
        "status": "blocked",
        "confidence": "blocked",
        "mutation_allowed": False,
        "durable_project_state_record_allowed": False,
        "service_family": service_family,
        "canonical_service": canonical_service,
        "service_binding": descriptor.get("service_binding") if isinstance(descriptor.get("service_binding"), str) else None,
        "instantiation_class": instantiation_class,
        "authority_boundary": None,
        "project_scope": None,
        "credential_scope": None,
        "resource_scope": None,
        "caller_or_session_scope": None,
        "scope_boundaries": {
            "project_scope": None,
            "credential_scope": None,
            "resource_scope": None,
            "caller_or_session_scope": None,
        },
        "transport_profile": None,
        "blockers": blockers,
        "non_actions": ["do not mutate project state", "do not provision backend", "do not register ContextForge service"],
        "contract_card_draft": None,
        "shared_service_capability_capsule": None,
        "service_management_handoff": None,
        "verification_requirements": ["resolve classification blockers before planning mutation"],
        "identity": {
            "identity_source": "blocked_manifest_or_catalog",
            "client_aliases_ignored": client_aliases,
        },
    }


def _contract_card(
    descriptor: Mapping[str, Any],
    *,
    service_family: str,
    canonical_service: str,
    service_binding: str,
    instantiation_class: str,
    scopes: Mapping[str, Any],
    transport_profile: Mapping[str, Any],
    non_actions: list[str],
    verification_requirements: list[str],
    resolved_at: str,
    catalog_revision_or_etag: str | None,
) -> dict[str, Any]:
    contextforge = _mapping(descriptor.get("contextforge"))
    gateway = _mapping(contextforge.get("gateway") or descriptor.get("gateway"))
    virtual_server = _mapping(contextforge.get("virtual_server") or descriptor.get("virtual_server"))
    return {
        "card_id": _identifier("card", service_binding),
        "schema_uri": "contextforge://control-plane/schemas/service-binding-contract-card/v1",
        "service_family": _identifier_value(service_family),
        "service_binding": service_binding,
        "instantiation_class": instantiation_class,
        "authority_boundary": _authority_boundary(instantiation_class, scopes),
        "project_scope": scopes["project_scope"],
        "credential_scope": scopes["credential_scope"],
        "resource_scope": scopes["resource_scope"],
        "caller_or_session_scope": scopes["caller_or_session_scope"],
        "backend_instance_ref": _backend_instance_ref(descriptor, resolved_at, catalog_revision_or_etag),
        "contextforge_gateway": _redact_simple(gateway) if gateway else {"canonical_service": canonical_service},
        "virtual_server": _redact_simple(virtual_server) if virtual_server else None,
        "client_adapter_refs": _artifact_ref_list(descriptor.get("client_adapter_refs")),
        "semantic_tool_policy_ref": _artifact_ref_or_none(descriptor.get("semantic_tool_policy_ref")),
        "transport_profile": dict(transport_profile),
        "required_consent_classes": _required_consent_classes(instantiation_class),
        "verification_matrix": {
            "required_layers": VERIFICATION_LAYERS[instantiation_class],
            "layer_requirements": {
                "endpoint_probes": list(transport_profile["required_endpoint_verification"]),
                "semantic": verification_requirements,
            },
        },
        "non_actions": non_actions,
        "evidence_requirements": verification_requirements,
    }


def _shared_capsule(
    descriptor: Mapping[str, Any],
    *,
    service_family: str,
    canonical_service: str,
    contract_card: Mapping[str, Any],
    transport_profile: Mapping[str, Any],
    verification_requirements: list[str],
    resolved_at: str,
    catalog_revision_or_etag: str | None,
) -> dict[str, Any]:
    card_ref = contracts.artifact_ref(
        f"contextforge://control-plane/service-bindings/{contract_card['card_id']}/v1",
        contract_card,
        resolved_at=resolved_at,
        catalog_revision_or_etag=catalog_revision_or_etag,
    )
    return {
        "capsule_id": _identifier("capsule", canonical_service),
        "schema_uri": "contextforge://control-plane/schemas/shared-service-capability-capsule/v1",
        "service_family": _identifier_value(service_family),
        "canonical_service": canonical_service,
        "allowed_project_binding_modes": ["record_availability", "bind_existing", "verify_existing"],
        "project_state_recording_policy": (
            "Record availability, contract refs, consent refs, and verification traces only; "
            "do not claim ownership of the shared backend."
        ),
        "verification_requirements": verification_requirements,
        "consent_requirements": _required_consent_classes("shared_canonical"),
        "transport_profile": dict(transport_profile),
        "forbidden_project_init_effects": list(CAPSULE_FORBIDDEN_EFFECTS),
        "contract_card_refs": [card_ref],
    }


def _service_management_handoff(
    descriptor: Mapping[str, Any],
    *,
    service_family: str | None,
    canonical_service: str | None,
    project_root: str | None,
    source: str,
) -> dict[str, Any]:
    backend = _mapping(descriptor.get("backend"))
    scope = _mapping(descriptor.get("scope"))
    candidate_name = canonical_service or service_family or _first_string(descriptor.get("candidate_name"), descriptor.get("name")) or "uncataloged"
    return {
        "handoff_id": _identifier("handoff", candidate_name),
        "schema_uri": "contextforge://control-plane/schemas/service-management-handoff/v1",
        "source": source if source in {"project_init", "catalog_read", "user_request"} else "project_init",
        "project_root": project_root,
        "candidate_descriptor": _redact_for_contract(descriptor),
        "redaction_status": "redacted",
        "dedupe_keys": {
            "backend_package": _first_string(
                descriptor.get("backend_package"),
                backend.get("package"),
                backend.get("command"),
                descriptor.get("package"),
            ),
            "runtime_scope": _runtime_scope(scope),
            "credential_scope": _scope_label(scope.get("credential_scope") or descriptor.get("credential_scope")),
            "resource_scope": _scope_label(scope.get("resource_scope") or descriptor.get("resource_scope")),
            "transport_scope": _transport_scope(backend, descriptor),
        },
        "suspected_instantiation_class": "candidate_or_uncataloged_backend",
        "required_next_workflow": "service_management_plan",
        "forbidden_under_current_approval": [
            "catalog_promotion",
            "project_state_service_record",
            "contextforge_registration",
            "backend_provision",
        ],
    }


def _transport_profile(descriptor: Mapping[str, Any]) -> dict[str, Any]:
    native = _native_transports(descriptor)
    bridge_mode, package_bridge_ref = _bridge_mode(native)
    forbidden = ["do not wrap native HTTP/SSE transports unnecessarily"]
    if bridge_mode == "none":
        forbidden.append("no bridge or wrapper for already-suitable native transports")
    elif bridge_mode == "sse_to_http":
        forbidden.append("bridge only the missing streamable HTTP side")
    elif bridge_mode == "http_to_sse":
        forbidden.append("bridge only the missing SSE side")
    elif bridge_mode == "stdio_to_http_sse":
        forbidden.append("bridge stdio only through package-provided translation")
    return {
        "native_transports": native,
        "required_client_transports": ["streamable_http", "sse"],
        "bridge_mode": bridge_mode,
        "package_bridge_ref": package_bridge_ref,
        "forbidden_bridge_effects": forbidden,
        "required_endpoint_verification": ["/mcp", "/sse"],
    }


def _native_transports(descriptor: Mapping[str, Any]) -> list[str]:
    explicit = descriptor.get("native_transports")
    if isinstance(explicit, list) and explicit:
        return _normalize_transports(explicit)
    backend = _mapping(descriptor.get("backend"))
    bridge = _mapping(descriptor.get("bridge"))
    transports = []
    transports.extend(_as_list(backend.get("native_transports")))
    if backend.get("transport"):
        transports.append(backend["transport"])
    if descriptor.get("transport"):
        transports.append(descriptor["transport"])
    if bridge.get("needed") is False:
        if bridge.get("streamable_http_url") or bridge.get("http_url"):
            transports.append("streamable_http")
        if bridge.get("sse_url"):
            transports.append("sse")
    normalized = _normalize_transports(transports)
    return normalized or ["stdio"]


def _bridge_mode(native_transports: list[str]) -> tuple[str, str | None]:
    has_stdio = "stdio" in native_transports
    has_sse = "sse" in native_transports
    has_http = "http" in native_transports or "streamable_http" in native_transports
    if has_http and has_sse:
        return "none", None
    if has_stdio and not has_http and not has_sse:
        return "stdio_to_http_sse", "python -m mcpgateway.translate --stdio ... --expose-sse --expose-streamable-http"
    if has_sse and not has_http:
        return "sse_to_http", "python -m mcpgateway.translate --connect-sse ... --expose-streamable-http"
    if has_http and not has_sse:
        return "http_to_sse", "python -m mcpgateway.translate --connect-streamable-http ... --expose-sse"
    return "none", None


def _scope_boundaries(
    descriptor: Mapping[str, Any],
    scope: Mapping[str, Any],
    classification: Mapping[str, Any],
    instantiation_class: str,
    project_root: str | None,
) -> dict[str, Any]:
    project_scope = None
    credential_scope = None
    resource_scope = None
    caller_or_session_scope = None
    if instantiation_class in {"instance_per_project", "project_scoped_shared_backend", "static_repo_local"}:
        project_scope = _redact_simple(
            scope.get("project_scope")
            or {
                "project_root": project_root or scope.get("workspace_root") or descriptor.get("project_root"),
                "scope_type": scope.get("scope_type"),
                "isolation_mechanism": _isolation_mechanism(descriptor, scope, classification),
            }
        )
    if instantiation_class == "shared_canonical":
        project_scope = {"mode": "availability_binding_only"}
    if instantiation_class == "credential_scoped":
        credential_scope = _redact_simple(scope.get("credential_scope") or descriptor.get("credential_scope") or {"scope": "explicit"})
    if instantiation_class == "resource_scoped":
        resource_scope = _redact_simple(scope.get("resource_scope") or descriptor.get("resource_scope") or {"scope": "explicit"})
    if instantiation_class in {"caller_scoped", "session_scoped"}:
        caller_or_session_scope = _redact_simple(
            scope.get("caller_or_session_scope")
            or {
                "scope": "caller" if instantiation_class == "caller_scoped" else "session",
                "authority": scope.get("authority") or classification.get("authority"),
            }
        )
    return {
        "project_scope": project_scope,
        "credential_scope": credential_scope,
        "resource_scope": resource_scope,
        "caller_or_session_scope": caller_or_session_scope,
    }


def _non_actions(instantiation_class: str, transport_profile: Mapping[str, Any], descriptor: Mapping[str, Any]) -> list[str]:
    actions = []
    if instantiation_class == "shared_canonical":
        actions.extend(NO_PROJECT_DUPLICATION_ACTIONS)
        actions.append("bind or verify the existing canonical service only")
    elif instantiation_class in PROJECT_SCOPED_REUSE_CLASSES:
        actions.append("do not duplicate backend for client alias or project name convenience")
        if instantiation_class in {"caller_scoped", "session_scoped"}:
            actions.append("do not claim durable project ownership of the live caller/session")
        if instantiation_class == "static_repo_local":
            actions.append("do not let client-local memory supersede governance ledgers")
        if instantiation_class == "project_scoped_shared_backend":
            actions.append("do not reuse shared backend without isolation verification")
    if transport_profile["bridge_mode"] == "none":
        actions.append("do not create bridge or wrapper for native HTTP/SSE access")
    else:
        actions.append("do not wrap transports beyond the missing required side")
    return _unique(actions)


def _verification_requirements(instantiation_class: str, transport_profile: Mapping[str, Any]) -> list[str]:
    requirements = [
        "verify ContextForge /mcp endpoint where exposed",
        "verify ContextForge /sse endpoint where exposed",
        "verify semantic tool policy readback and negative checks",
        "verify redaction before returning diagnostics",
    ]
    if instantiation_class == "shared_canonical":
        requirements.insert(0, "read back existing canonical ContextForge gateway and virtual server")
    if instantiation_class == "project_scoped_shared_backend":
        requirements.insert(0, "prove project isolation mechanism with allowed and denied operations")
    if instantiation_class == "instance_per_project":
        requirements.insert(0, "verify project-bound backend health before client exposure")
    if instantiation_class in {"credential_scoped", "resource_scoped"}:
        requirements.insert(0, "verify representative allowed and denied scope operations")
    if instantiation_class in {"caller_scoped", "session_scoped"}:
        requirements.insert(0, "verify live caller/session authority without claiming project ownership")
    if transport_profile["bridge_mode"] != "none":
        requirements.append(f"verify package bridge mode {transport_profile['bridge_mode']}")
    return _unique(requirements)


def _required_consent_classes(instantiation_class: str) -> list[str]:
    if instantiation_class == "instance_per_project":
        return ["read_only_inspection", "project_state_write", "service_provision"]
    if instantiation_class == "shared_canonical":
        return ["read_only_inspection"]
    if instantiation_class in {"project_scoped_shared_backend", "credential_scoped", "resource_scoped"}:
        return ["read_only_inspection", "project_state_write"]
    if instantiation_class in {"caller_scoped", "session_scoped", "static_repo_local"}:
        return ["read_only_inspection"]
    return ["read_only_inspection"]


def _authority_boundary(instantiation_class: str, scopes: Mapping[str, Any]) -> str:
    if instantiation_class == "instance_per_project":
        return "project-local backend instance owns project lifecycle and state"
    if instantiation_class == "project_scoped_shared_backend":
        return "shared backend with project isolation enforced by binding metadata and verification"
    if instantiation_class == "shared_canonical":
        return "host-level canonical ContextForge service; project init records availability and verification only"
    if instantiation_class == "credential_scoped":
        return "credential/account/tenant boundary controls safe reuse"
    if instantiation_class == "resource_scoped":
        return "resource allowlist boundary controls safe reuse"
    if instantiation_class == "caller_scoped":
        return "active caller authority controls live service scope"
    if instantiation_class == "session_scoped":
        return "active session authority controls live service scope"
    if instantiation_class == "static_repo_local":
        return "repository governance files are the durable service authority"
    return str(scopes)


def _explicit_instantiation_class(
    descriptor: Mapping[str, Any],
    scope: Mapping[str, Any],
    classification: Mapping[str, Any],
) -> str | None:
    return _first_string(
        descriptor.get("instantiation_class"),
        classification.get("instantiation_class"),
        classification.get("class"),
        scope.get("instantiation_class"),
    )


def _infer_instantiation_class(
    descriptor: Mapping[str, Any],
    scope: Mapping[str, Any],
    classification: Mapping[str, Any],
) -> str | None:
    if scope.get("static_repo_local") or classification.get("static_repo_local") or descriptor.get("governance_authority"):
        return "static_repo_local"
    if scope.get("caller_scope") or classification.get("caller_scope"):
        return "caller_scoped"
    if scope.get("session_scope") or classification.get("session_scope"):
        return "session_scoped"
    if scope.get("credential_scope") or descriptor.get("credential_scope"):
        return "credential_scoped"
    if scope.get("resource_scope") or descriptor.get("resource_scope"):
        return "resource_scoped"
    if scope.get("project_scoped_shared_backend") or classification.get("project_scoped_shared_backend"):
        return "project_scoped_shared_backend"
    if scope.get("requires_local_project_scope") or scope.get("scope_type") in {"single_workspace_code_intelligence", "project_local"}:
        return "instance_per_project"
    if descriptor.get("shared_canonical") or scope.get("shared_canonical") or classification.get("shared_canonical"):
        return "shared_canonical"
    return None


def _is_candidate(descriptor: Mapping[str, Any]) -> bool:
    registration = _mapping(descriptor.get("registration"))
    classification = _mapping(descriptor.get("classification"))
    return bool(
        descriptor.get("candidate")
        or descriptor.get("uncataloged")
        or descriptor.get("required_next_workflow") == "service_management_handoff"
        or descriptor.get("instantiation_class") == "candidate_or_uncataloged_backend"
        or classification.get("instantiation_class") == "candidate_or_uncataloged_backend"
        or registration.get("status") in {"candidate", "uncataloged", "not_cataloged"}
    )


def _canonical_identity(descriptor: Mapping[str, Any], scope: Mapping[str, Any], field: str) -> str | None:
    if field == "service_family":
        return _first_string(
            descriptor.get("service_family"),
            descriptor.get("family"),
            scope.get("service_family"),
            descriptor.get("canonical_service"),
        )
    return _first_string(descriptor.get("canonical_service"), descriptor.get("canonical_name"))


def _service_binding(
    descriptor: Mapping[str, Any],
    service_family: str,
    instantiation_class: str,
    scope: Mapping[str, Any],
) -> str:
    existing = descriptor.get("service_binding")
    if isinstance(existing, str) and existing:
        return existing
    return _derived_service_binding(service_family, instantiation_class, scope, descriptor)


def _supplied_service_binding_blocker(
    descriptor: Mapping[str, Any],
    service_family: str,
    instantiation_class: str,
    scope: Mapping[str, Any],
) -> dict[str, str] | None:
    existing = descriptor.get("service_binding")
    if not isinstance(existing, str) or not existing:
        return None
    expected = _derived_service_binding(service_family, instantiation_class, scope, descriptor)
    if existing == expected:
        return None
    return _blocker(
        "service_binding_not_canonical",
        f"Supplied service_binding {existing!r} does not match canonical binding {expected!r}.",
    )


def _derived_service_binding(
    service_family: str,
    instantiation_class: str,
    scope: Mapping[str, Any],
    descriptor: Mapping[str, Any],
) -> str:
    suffix = _first_string(scope.get("binding"), scope.get("scope_id"), descriptor.get("binding"))
    if not suffix:
        suffix = {
            "instance_per_project": "project",
            "project_scoped_shared_backend": "project-shared",
            "shared_canonical": "canonical",
            "credential_scoped": "credential",
            "resource_scoped": "resource",
            "caller_scoped": "caller",
            "session_scoped": "session",
            "static_repo_local": "repo-local",
        }[instantiation_class]
    return f"{service_family}:{_slug(suffix)}"


def _isolation_mechanism(
    descriptor: Mapping[str, Any],
    scope: Mapping[str, Any],
    classification: Mapping[str, Any],
) -> Any | None:
    return (
        scope.get("isolation_mechanism")
        or classification.get("isolation_mechanism")
        or descriptor.get("isolation_mechanism")
        or scope.get("resource_allowlist")
        or scope.get("request_time_root_binding")
        or scope.get("service_side_scope_checks")
    )


def _backend_instance_ref(
    descriptor: Mapping[str, Any],
    resolved_at: str,
    catalog_revision_or_etag: str | None,
) -> dict[str, Any] | None:
    slug = _first_string(descriptor.get("instance_slug"), descriptor.get("slug"))
    if not slug:
        return None
    data = {"instance_slug": slug, "backend": _redact_simple(_mapping(descriptor.get("backend")))}
    return contracts.artifact_ref(
        f"contextforge://control-plane/backend-instances/{_identifier_value(slug)}/v1",
        data,
        resolved_at=resolved_at,
        catalog_revision_or_etag=catalog_revision_or_etag,
    )


def _artifact_ref_or_none(value: Any) -> dict[str, Any] | None:
    if isinstance(value, Mapping):
        required = {"ref", "content_digest", "catalog_revision_or_etag", "resolved_at"}
        if required <= set(value):
            return copy.deepcopy(dict(value))
    return None


def _artifact_ref_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    refs = []
    for item in value:
        ref = _artifact_ref_or_none(item)
        if ref:
            refs.append(ref)
    return refs


def _runtime_scope(scope: Mapping[str, Any]) -> str:
    runtime_scope = scope.get("runtime_scope")
    if runtime_scope in {"host", "project", "credential", "caller", "session", "unknown"}:
        return str(runtime_scope)
    if scope.get("requires_local_project_scope"):
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
    if normalized in {"stdio", "http", "sse", "rest"}:
        return normalized
    return "unknown"


def _scope_label(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return "<redacted>" if redaction.classify_sensitive_value(value) else value
    if isinstance(value, Mapping):
        label = _first_string(value.get("id"), value.get("name"), value.get("scope"), value.get("tenant"), value.get("resource"))
        return _scope_label(label) if label else "explicit"
    return str(value)


def _client_aliases(descriptor: Mapping[str, Any]) -> list[str]:
    aliases: list[str] = []
    for key in ("client_alias", "client_name", "codex_alias", "name"):
        value = descriptor.get(key)
        if isinstance(value, str) and value:
            aliases.append(value)
    for item in _as_list(descriptor.get("client_config_names")):
        if isinstance(item, str) and item:
            aliases.append(item)
    return sorted(set(aliases))


def _normalize_transports(values: list[Any]) -> list[str]:
    transports = []
    for value in values:
        name = _transport_name(str(value))
        if name in {"stdio", "http", "sse", "streamable_http", "rest"}:
            transports.append(name)
    return sorted(set(transports))


def _transport_name(value: str) -> str:
    normalized = value.lower().replace("-", "_")
    if normalized in {"streamable_http", "mcp_http"}:
        return "streamable_http"
    return normalized


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
    if isinstance(value, tuple):
        return [_redact_for_contract(item) for item in value]
    if isinstance(value, str) and redaction.classify_sensitive_value(value):
        return "<redacted>"
    return copy.deepcopy(value)


def _redact_simple(value: Any) -> Any:
    return _redact_for_contract(value)


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


def _first_string(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value:
            return value
    return None


def _blocker(blocker_type: str, message: str) -> dict[str, str]:
    return {"type": blocker_type, "severity": "blocking", "message": message}


def _unique(values: list[str]) -> list[str]:
    seen = set()
    output = []
    for value in values:
        if value not in seen:
            seen.add(value)
            output.append(value)
    return output


def _identifier(prefix: str, value: str) -> str:
    return _identifier_value(f"{prefix}-{value}")


def _identifier_value(value: str) -> str:
    slug = _slug(value)
    if not slug:
        slug = "unknown"
    if not re.match(r"^[A-Za-z0-9]", slug):
        slug = f"id-{slug}"
    return slug


def _slug(value: Any) -> str:
    text = str(value)
    text = re.sub(r"[^A-Za-z0-9_.:/@+-]+", "-", text.strip())
    text = re.sub(r"-+", "-", text).strip("-")
    return text or "unknown"
