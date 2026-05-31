#!/usr/bin/env python3
"""Pure service-management workflow helpers for ContextForge catalog candidates."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

import control_plane_contracts as contracts
import control_plane_redaction as redaction


RESULT_SCHEMA_URI = "contextforge://control-plane/schemas/service-management-result/v1"
PLAN_SCHEMA_URI = "contextforge://control-plane/service-management/catalog-plan/v1"
HELPER_VERSION = 1
REQUIRED_CLIENT_TRANSPORTS = ("streamable_http", "sse")
CONSUMABLE_COMPLETION_STATUSES = frozenset({"dedupe_existing", "approved_completed"})
NON_CONSUMABLE_STATUSES = frozenset({"plan_only", "refused", "failed"})
EXPLICIT_CATALOG_APPROVAL_CLASSES = frozenset({"catalog_promotion", "catalog_update", "catalog_repair", "catalog_removal"})
GENERIC_PROJECT_INIT_APPROVAL_CLASSES = frozenset({"project_init", "generic_project_init", "project_setup"})
DEFAULT_FORBIDDEN_FOLLOW_UP_EFFECTS = (
    "project_init_catalog_mutation",
    "project_state_service_record_without_consumable_service_management_result",
    "direct_contextforge_database_write",
)
DIRECT_DATABASE_NON_ACTIONS = (
    "does not call ContextForge APIs",
    "does not write the ContextForge database",
    "does not patch ContextForge source",
    "does not write client config",
    "does not create backend homes",
    "does not create bridges",
)
CONTEXTFORGE_GATEWAY_APIS = {
    "promote": ("POST /gateways", "POST /servers", "POST /servers/{id}/tools", "GET /servers/{id}/tools"),
    "update": ("GET /gateways/{name}", "PUT /gateways/{id}", "PUT /servers/{id}", "POST /servers/{id}/tools", "GET /servers/{id}/tools"),
    "repair": ("GET /gateways/{name}", "PUT /gateways/{id}", "POST /servers/{id}/tools", "GET /servers/{id}/tools"),
}


class ServiceManagementInputError(ValueError):
    """Raised when service-management workflow inputs are malformed or unsafe."""


def now_timestamp() -> str:
    """Return a UTC timestamp for generated refs and plans."""

    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stable_digest(value: Any) -> str:
    """Return a stable sha256 digest for JSON-compatible workflow data."""

    encoded = json.dumps(_json_copy(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def plan_service_management_from_handoff(
    handoff: Mapping[str, Any],
    *,
    existing_services: Iterable[Mapping[str, Any]] = (),
    requested_action: str = "promote",
    approval_context: Mapping[str, Any] | None = None,
    contract_card_refs: Sequence[Mapping[str, Any]] = (),
    capsule_refs: Sequence[Mapping[str, Any]] = (),
    semantic_tool_policy_refs: Sequence[Mapping[str, Any]] = (),
    catalog_revision: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Consume a typed service-management handoff and return a non-mutating result.

    Duplicate canonical services return a consumable ``dedupe_existing`` result
    only when their refs and verification evidence are complete. New or drifted
    candidates return ``plan_only`` and still require explicit approval of the
    concrete catalog plan before any ContextForge API call.
    """

    handoff_data = _validated_handoff(handoff)
    generated = generated_at or now_timestamp()
    duplicate = find_duplicate_service(handoff_data, existing_services)
    if duplicate is not None:
        return build_dedupe_existing_result(
            handoff_data,
            existing_service=duplicate,
            catalog_revision=catalog_revision or _string_or_none(duplicate.get("catalog_revision")),
            generated_at=generated,
        )

    if _approval_is_generic_project_init(approval_context):
        return build_refusal_result(
            handoff_data,
            reason="generic_project_init_approval_cannot_promote_catalog_candidate",
            details="Catalog promotion or update requires explicit service-management approval of the concrete plan.",
            generated_at=generated,
        )

    action = _catalog_action(requested_action)
    plan = build_catalog_plan(
        handoff_data,
        requested_action=action,
        approval_context=approval_context,
        contract_card_refs=contract_card_refs,
        capsule_refs=capsule_refs,
        semantic_tool_policy_refs=semantic_tool_policy_refs,
        catalog_revision=catalog_revision,
        generated_at=generated,
    )
    result = _base_result(handoff_data, "plan_only", generated_at=generated)
    result.update(
        {
            "contract_card_refs": _artifact_refs(contract_card_refs, "contract_card_refs", require=False),
            "capsule_refs": _artifact_refs(capsule_refs, "capsule_refs", require=False),
            "semantic_tool_policy_refs": _artifact_refs(semantic_tool_policy_refs, "semantic_tool_policy_refs", require=False),
            "canonical_names": [plan["canonical_names"]["gateway"]],
            "catalog_revision": catalog_revision,
            "consent_receipt_refs": [],
            "verification_trace_refs": [],
            "x_catalog_plan": plan,
            "x_completion_record_consumable": False,
            "x_required_approval": {
                "approval_class": "catalog_promotion" if action == "promote" else "catalog_update",
                "generic_project_init_approval_accepted": False,
                "separate_explicit_catalog_approval_required": True,
            },
        }
    )
    return _validate_result(result)


def build_catalog_plan(
    handoff: Mapping[str, Any],
    *,
    requested_action: str = "promote",
    approval_context: Mapping[str, Any] | None = None,
    contract_card_refs: Sequence[Mapping[str, Any]] = (),
    capsule_refs: Sequence[Mapping[str, Any]] = (),
    semantic_tool_policy_refs: Sequence[Mapping[str, Any]] = (),
    catalog_revision: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build a catalog promotion/update plan without applying it."""

    handoff_data = _validated_handoff(handoff)
    action = _catalog_action(requested_action)
    if _approval_is_generic_project_init(approval_context):
        raise ServiceManagementInputError("generic project-init approval cannot authorize catalog promotion or update")

    generated = generated_at or now_timestamp()
    descriptor = _redacted_descriptor(handoff_data.get("candidate_descriptor") or {})
    dedupe_keys = _dedupe_keys(handoff_data)
    canonical_names = _canonical_names(handoff_data, descriptor)
    transport_decision = classify_transport_decision(descriptor, dedupe_keys)
    plan = {
        "schema_uri": PLAN_SCHEMA_URI,
        "helper_version": HELPER_VERSION,
        "plan_id": _identifier("service-management-plan", f"{handoff_data['handoff_id']}-{action}"),
        "handoff_id": handoff_data["handoff_id"],
        "status": "planned_non_mutating",
        "requested_action": action,
        "mutation_allowed": False,
        "requires_explicit_approval": True,
        "generic_project_init_approval_accepted": False,
        "required_approval_classes": ["catalog_promotion" if action == "promote" else "catalog_update"],
        "approval_context": _approval_summary(approval_context),
        "candidate_descriptor": descriptor,
        "dedupe_keys": dedupe_keys,
        "dedupe_identity": dedupe_identity(dedupe_keys),
        "canonical_names": canonical_names,
        "contextforge_authority": {
            "canonical_registry": "ContextForge",
            "client_configs_are_service_identities": False,
            "mutation_path": "public_contextforge_api_or_documented_operator_script_after_explicit_approval",
            "direct_database_writes_allowed": False,
        },
        "transport_decision": transport_decision,
        "contextforge_api_operations": _contextforge_operations(action, canonical_names, transport_decision),
        "required_artifact_refs": {
            "contract_card_refs": _artifact_refs(contract_card_refs, "contract_card_refs", require=False),
            "capsule_refs": _artifact_refs(capsule_refs, "capsule_refs", require=False),
            "semantic_tool_policy_refs": _artifact_refs(semantic_tool_policy_refs, "semantic_tool_policy_refs", require=False),
        },
        "tool_policy_requirements": {
            "must_compile_semantic_tool_policy": True,
            "must_list_excluded_scope_changing_and_approval_gated_tools": True,
            "must_verify_virtual_server_associated_tool_readback": True,
        },
        "verification_requirements": _verification_requirements(transport_decision),
        "rollback_or_repair_notes": [
            "Resume or repair through service-management with fresh stale-input checks.",
            "Rollback uses public ContextForge API operations and documented operator scripts only.",
        ],
        "non_actions": _non_actions(transport_decision),
        "catalog_revision": catalog_revision,
        "generated_at": generated,
        "redaction_status": "redacted",
    }
    _assert_redacted(plan)
    return _json_copy(plan)


def find_duplicate_service(
    handoff: Mapping[str, Any],
    existing_services: Iterable[Mapping[str, Any]],
) -> dict[str, Any] | None:
    """Return the first existing canonical service matching backend and scopes."""

    handoff_data = _validated_handoff(handoff)
    wanted = dedupe_identity(_dedupe_keys(handoff_data))
    for service in existing_services:
        if not isinstance(service, Mapping):
            continue
        candidate = _existing_service_identity(service)
        if candidate == wanted:
            return _json_copy(service)
    return None


def dedupe_identity(dedupe_keys: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize dedupe fields that define backend package/server and scopes."""

    keys = _mapping(dedupe_keys, "dedupe_keys")
    backend_package = _normalize_optional(keys.get("backend_package"))
    return {
        "backend_package": backend_package,
        "backend_server": _normalize_optional(keys.get("x_backend_command") or keys.get("backend_server")) or backend_package,
        "runtime_scope": _normalize_required(keys.get("runtime_scope"), "unknown"),
        "credential_scope": _normalize_optional(keys.get("credential_scope")),
        "resource_scope": _normalize_optional(keys.get("resource_scope")),
        "transport_scope": _normalize_required(keys.get("transport_scope"), "unknown"),
    }


def classify_transport_decision(
    descriptor: Mapping[str, Any],
    dedupe_keys: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Decide native transport preservation or package bridge mode."""

    native = _native_transports(descriptor, dedupe_keys)
    has_stdio = "stdio" in native
    has_sse = "sse" in native
    has_http = "streamable_http" in native or "http" in native
    has_rest = "rest" in native

    if has_http and has_sse:
        mode = "native_http_sse"
        bridge = None
        unsupported = False
        operation = "register_native_contextforge_gateway"
    elif has_stdio and not has_http and not has_sse:
        mode = "package_bridge_stdio_to_http_sse"
        bridge = "python -m mcpgateway.translate --stdio ... --expose-sse --expose-streamable-http"
        unsupported = False
        operation = "bridge_missing_http_and_sse_with_package_translator"
    elif has_sse and not has_http:
        mode = "package_bridge_sse_to_http"
        bridge = "python -m mcpgateway.translate --connect-sse ... --expose-streamable-http"
        unsupported = False
        operation = "bridge_missing_streamable_http_only"
    elif has_http and not has_sse:
        mode = "package_bridge_http_to_sse"
        bridge = "python -m mcpgateway.translate --connect-streamable-http ... --expose-sse"
        unsupported = False
        operation = "bridge_missing_sse_only"
    elif has_rest:
        mode = "native_rest_api_tool_registration"
        bridge = None
        unsupported = False
        operation = "register_rest_or_openapi_tool_through_contextforge"
    else:
        mode = "unsupported_transport"
        bridge = None
        unsupported = True
        operation = "refuse_until_transport_is_explicit"

    decision = {
        "native_transports": native,
        "required_client_transports": list(REQUIRED_CLIENT_TRANSPORTS),
        "decision": mode,
        "bridge_required": bridge is not None,
        "package_bridge_ref": bridge,
        "unsupported": unsupported,
        "operation": operation,
        "preserve_native_http_sse": has_http or has_sse,
        "forbidden_bridge_effects": _bridge_forbidden_effects(mode),
    }
    _assert_redacted(decision)
    return decision


def build_dedupe_existing_result(
    handoff: Mapping[str, Any],
    *,
    existing_service: Mapping[str, Any],
    catalog_revision: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build a consumable result for a candidate that matches an existing service."""

    handoff_data = _validated_handoff(handoff)
    service = _mapping(existing_service, "existing_service")
    canonical_names = _canonical_name_list(service)
    contract_refs = _artifact_refs(service.get("contract_card_refs") or service.get("contract_refs") or [], "contract_card_refs", require=True)
    capsule_refs = _artifact_refs(service.get("capsule_refs") or [], "capsule_refs", require=False)
    policy_refs = _artifact_refs(
        service.get("semantic_tool_policy_refs") or service.get("policy_refs") or [],
        "semantic_tool_policy_refs",
        require=True,
    )
    trace_refs = _artifact_refs(service.get("verification_trace_refs") or service.get("verification_refs") or [], "verification_trace_refs", require=True)
    result = _base_result(handoff_data, "dedupe_existing", generated_at=generated_at)
    result.update(
        {
            "contract_card_refs": contract_refs,
            "capsule_refs": capsule_refs,
            "semantic_tool_policy_refs": policy_refs,
            "canonical_names": canonical_names,
            "catalog_revision": catalog_revision,
            "consent_receipt_refs": _artifact_refs(service.get("consent_receipt_refs") or [], "consent_receipt_refs", require=False),
            "verification_trace_refs": trace_refs,
            "x_dedupe_identity": dedupe_identity(_dedupe_keys(handoff_data)),
            "x_existing_service": {
                "canonical_names": canonical_names,
                "catalog_revision": catalog_revision,
                "dedupe_keys": _existing_service_identity(service),
            },
            "x_completion_record_consumable": True,
        }
    )
    return _validate_consumable_result(result)


def build_refusal_result(
    handoff: Mapping[str, Any],
    *,
    reason: str,
    details: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build a non-consumable refusal result."""

    handoff_data = _validated_handoff(handoff)
    result = _base_result(handoff_data, "refused", generated_at=generated_at)
    result.update(
        {
            "contract_card_refs": [],
            "capsule_refs": [],
            "semantic_tool_policy_refs": [],
            "canonical_names": [],
            "catalog_revision": None,
            "consent_receipt_refs": [],
            "verification_trace_refs": [],
            "x_refusal": {"reason": _identifier("reason", reason), "details": str(details)},
            "x_completion_record_consumable": False,
        }
    )
    return _validate_result(result)


def build_approved_completion_result(
    handoff: Mapping[str, Any],
    *,
    canonical_names: Sequence[str],
    contract_card_refs: Sequence[Mapping[str, Any]],
    semantic_tool_policy_refs: Sequence[Mapping[str, Any]],
    verification_trace_refs: Sequence[Mapping[str, Any]],
    consent_receipt_refs: Sequence[Mapping[str, Any]],
    capsule_refs: Sequence[Mapping[str, Any]] = (),
    catalog_revision: str | None = None,
    approval_context: Mapping[str, Any] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build a post-approval completion record for an already-applied plan."""

    handoff_data = _validated_handoff(handoff)
    approval = _approval_summary(approval_context)
    if not approval["explicit_catalog_approval"]:
        raise ServiceManagementInputError("approved_completed result requires explicit catalog approval, not generic project-init approval")

    result = _base_result(handoff_data, "approved_completed", generated_at=generated_at)
    result.update(
        {
            "contract_card_refs": _artifact_refs(contract_card_refs, "contract_card_refs", require=True),
            "capsule_refs": _artifact_refs(capsule_refs, "capsule_refs", require=False),
            "semantic_tool_policy_refs": _artifact_refs(semantic_tool_policy_refs, "semantic_tool_policy_refs", require=True),
            "canonical_names": _canonical_names_required(canonical_names),
            "catalog_revision": catalog_revision,
            "consent_receipt_refs": _artifact_refs(consent_receipt_refs, "consent_receipt_refs", require=True),
            "verification_trace_refs": _artifact_refs(verification_trace_refs, "verification_trace_refs", require=True),
            "x_approval": approval,
            "x_completion_record_consumable": True,
            "x_project_state_recording_policy": (
                "Project init may consume this result only as a canonical service binding record with cited "
                "contract, capsule or policy, consent, and verification refs."
            ),
        }
    )
    return _validate_consumable_result(result)


def completion_record_consumable(result: Mapping[str, Any]) -> bool:
    """Return whether project-init may consume a service-management result."""

    data = _validated_result(result)
    if data["status"] not in CONSUMABLE_COMPLETION_STATUSES:
        return False
    return bool(
        data.get("canonical_names")
        and data.get("contract_card_refs")
        and data.get("semantic_tool_policy_refs")
        and data.get("verification_trace_refs")
        and data.get("redaction_status") == "redacted"
    )


def _validated_handoff(handoff: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(handoff, Mapping):
        raise ServiceManagementInputError("handoff must be a mapping")
    data = _json_copy(handoff)
    contracts.validate_artifact("service_management_handoff", data)
    if data.get("redaction_status") != "redacted":
        raise ServiceManagementInputError("service_management_handoff must be redacted")
    if data.get("required_next_workflow") != "service_management_plan":
        raise ServiceManagementInputError("service_management_handoff must target service_management_plan")
    _assert_redacted(data)
    return data


def _validated_result(result: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(result, Mapping):
        raise ServiceManagementInputError("result must be a mapping")
    data = _json_copy(result)
    try:
        contracts.validate_artifact("service_management_result", data)
        _assert_redacted(data)
    except contracts.ContractValidationError as exc:
        raise ServiceManagementInputError(str(exc)) from exc
    return data


def _validate_result(result: Mapping[str, Any]) -> dict[str, Any]:
    data = _json_copy(result)
    contracts.validate_artifact("service_management_result", data)
    if data["status"] in NON_CONSUMABLE_STATUSES and data.get("x_completion_record_consumable") is True:
        raise ServiceManagementInputError(f"{data['status']} result cannot be marked consumable")
    _assert_redacted(data)
    return data


def _validate_consumable_result(result: Mapping[str, Any]) -> dict[str, Any]:
    data = _validate_result(result)
    if not completion_record_consumable(data):
        raise ServiceManagementInputError("consumable service-management result requires canonical names, refs, and verification evidence")
    return data


def _base_result(handoff: Mapping[str, Any], status: str, *, generated_at: str | None) -> dict[str, Any]:
    generated = generated_at or now_timestamp()
    return {
        "result_id": _identifier("service-management-result", f"{handoff['handoff_id']}-{status}"),
        "schema_uri": RESULT_SCHEMA_URI,
        "handoff_id": handoff["handoff_id"],
        "status": status,
        "contract_card_refs": [],
        "capsule_refs": [],
        "semantic_tool_policy_refs": [],
        "canonical_names": [],
        "catalog_revision": None,
        "consent_receipt_refs": [],
        "verification_trace_refs": [],
        "redaction_status": "redacted",
        "forbidden_follow_up_effects": list(DEFAULT_FORBIDDEN_FOLLOW_UP_EFFECTS),
        "x_helper_version": HELPER_VERSION,
        "x_generated_at": generated,
    }


def _contextforge_operations(action: str, canonical_names: Mapping[str, str], transport: Mapping[str, Any]) -> list[dict[str, Any]]:
    operations = []
    for index, api in enumerate(CONTEXTFORGE_GATEWAY_APIS[action], start=1):
        operations.append(
            {
                "step": index,
                "api": api,
                "authority": "public_contextforge_api",
                "target": canonical_names["gateway"] if "gateway" in api.lower() else canonical_names["virtual_server"],
                "mutation_performed": False,
            }
        )
    if transport["bridge_required"]:
        operations.insert(
            0,
            {
                "step": 0,
                "api": "documented_operator_script: python -m mcpgateway.translate",
                "authority": "package_provided_bridge",
                "target": canonical_names["gateway"],
                "mutation_performed": False,
                "bridge_command": transport["package_bridge_ref"],
            },
        )
    return operations


def _verification_requirements(transport: Mapping[str, Any]) -> list[str]:
    requirements = [
        "read back ContextForge gateway by canonical name",
        "verify ContextForge /mcp endpoint where exposed",
        "verify ContextForge /sse endpoint where exposed",
        "refresh gateway tool discovery through ContextForge",
        "verify virtual-server associated tools with GET /servers/{id}/tools",
        "verify excluded, scope-changing, and approval-gated tools remain absent",
        "validate redaction before returning plan or result data",
    ]
    if transport.get("bridge_required"):
        requirements.append(f"verify package bridge mode {transport['decision']}")
    if transport.get("decision") == "native_rest_api_tool_registration":
        requirements.append("verify REST/OpenAPI tool registration through ContextForge readback")
    return _unique(requirements)


def _non_actions(transport: Mapping[str, Any]) -> list[str]:
    non_actions = list(DIRECT_DATABASE_NON_ACTIONS)
    if transport["bridge_required"]:
        non_actions.append("does not wrap transports beyond the missing required side")
    else:
        non_actions.append("does not wrap native HTTP/SSE or REST/API service unnecessarily")
    if transport["decision"] == "native_http_sse":
        non_actions.append("preserves native HTTP and SSE access")
    return _unique(non_actions)


def _bridge_forbidden_effects(mode: str) -> list[str]:
    effects = ["do not wrap native HTTP/SSE transports unnecessarily"]
    if mode == "native_http_sse":
        effects.append("no bridge or wrapper for already-suitable native transports")
    elif mode == "package_bridge_stdio_to_http_sse":
        effects.append("bridge stdio only through package-provided translation")
    elif mode == "package_bridge_sse_to_http":
        effects.append("bridge only the missing streamable HTTP side")
    elif mode == "package_bridge_http_to_sse":
        effects.append("bridge only the missing SSE side")
    elif mode == "native_rest_api_tool_registration":
        effects.append("register REST/API tools through native ContextForge mechanisms")
    else:
        effects.append("refuse unsupported or ambiguous transport instead of inventing a wrapper")
    return _unique(effects)


def _native_transports(descriptor: Mapping[str, Any], dedupe_keys: Mapping[str, Any] | None) -> list[str]:
    backend = descriptor.get("backend") if isinstance(descriptor.get("backend"), Mapping) else {}
    transports = []
    transports.extend(_as_list(descriptor.get("native_transports")))
    if isinstance(backend, Mapping):
        transports.extend(_as_list(backend.get("native_transports")))
        transports.extend(_as_list(backend.get("transport")))
    transports.extend(_as_list(descriptor.get("transport")))
    if dedupe_keys:
        transports.extend(_as_list(dedupe_keys.get("transport_scope")))
    normalized = [_transport_name(item) for item in transports if isinstance(item, str) and item]
    return _unique(normalized) or ["unknown"]


def _canonical_names(handoff: Mapping[str, Any], descriptor: Mapping[str, Any]) -> dict[str, str]:
    keys = _dedupe_keys(handoff)
    family = _first_string(
        descriptor.get("canonical_service"),
        descriptor.get("service_family"),
        descriptor.get("candidate_name"),
        keys.get("x_canonical_service"),
        keys.get("x_service_family"),
        keys.get("backend_package"),
        "uncataloged",
    )
    canonical = _identifier_value(family)
    return {
        "service": canonical,
        "gateway": _identifier_value(_first_string(descriptor.get("gateway_name"), f"{canonical}-gateway")),
        "virtual_server": _identifier_value(_first_string(descriptor.get("virtual_server_name"), f"{canonical}-server")),
    }


def _canonical_name_list(service: Mapping[str, Any]) -> list[str]:
    names = []
    for key in ("canonical_names", "canonical_name", "gateway_name", "service_name", "virtual_server_name"):
        value = service.get(key)
        if isinstance(value, list):
            names.extend(str(item) for item in value if isinstance(item, str) and item)
        elif isinstance(value, str) and value:
            names.append(value)
    if not names:
        raise ServiceManagementInputError("existing service must include canonical ContextForge names")
    return _unique(names)


def _canonical_names_required(values: Sequence[str]) -> list[str]:
    names = _unique([str(value) for value in values if isinstance(value, str) and value])
    if not names:
        raise ServiceManagementInputError("canonical_names are required")
    return names


def _approval_summary(approval_context: Mapping[str, Any] | None) -> dict[str, Any]:
    if not approval_context:
        return {
            "present": False,
            "approval_class": None,
            "explicit_catalog_approval": False,
            "generic_project_init_approval": False,
            "mutation_allowed_by_this_helper": False,
        }
    approval = _json_copy(approval_context)
    _assert_redacted(approval)
    approval_class = _first_string(approval.get("approval_class"), approval.get("consent_class"), approval.get("workflow"))
    explicit = approval_class in EXPLICIT_CATALOG_APPROVAL_CLASSES and approval.get("explicit") is True
    generic = approval_class in GENERIC_PROJECT_INIT_APPROVAL_CLASSES
    return {
        "present": True,
        "approval_class": approval_class,
        "explicit_catalog_approval": explicit,
        "generic_project_init_approval": generic,
        "approval_ref": _string_or_none(approval.get("approval_ref") or approval.get("consent_receipt_ref")),
        "mutation_allowed_by_this_helper": False,
    }


def _approval_is_generic_project_init(approval_context: Mapping[str, Any] | None) -> bool:
    return _approval_summary(approval_context)["generic_project_init_approval"]


def _existing_service_identity(service: Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(service.get("dedupe_keys"), Mapping):
        return dedupe_identity(service["dedupe_keys"])  # type: ignore[arg-type]
    scope = service.get("scope") if isinstance(service.get("scope"), Mapping) else {}
    backend = service.get("backend") if isinstance(service.get("backend"), Mapping) else {}
    transport = _first_string(service.get("transport_scope"), service.get("transport"), backend.get("transport") if isinstance(backend, Mapping) else None)
    return dedupe_identity(
        {
            "backend_package": _first_string(
                service.get("backend_package"),
                service.get("backend_server"),
                backend.get("package") if isinstance(backend, Mapping) else None,
                backend.get("command") if isinstance(backend, Mapping) else None,
            ),
            "x_backend_command": _first_string(service.get("backend_server"), backend.get("command") if isinstance(backend, Mapping) else None),
            "runtime_scope": _first_string(service.get("runtime_scope"), scope.get("runtime_scope") if isinstance(scope, Mapping) else None, "unknown"),
            "credential_scope": service.get("credential_scope") or (scope.get("credential_scope") if isinstance(scope, Mapping) else None),
            "resource_scope": service.get("resource_scope") or (scope.get("resource_scope") if isinstance(scope, Mapping) else None),
            "transport_scope": transport or "unknown",
        }
    )


def _redacted_descriptor(descriptor: Mapping[str, Any]) -> dict[str, Any]:
    redacted = redaction.redact_data(_json_copy(descriptor))
    _assert_redacted(redacted)
    return redacted


def _dedupe_keys(handoff: Mapping[str, Any]) -> dict[str, Any]:
    return _mapping(handoff.get("dedupe_keys"), "handoff.dedupe_keys")


def _artifact_refs(values: Sequence[Mapping[str, Any]] | Any, field: str, *, require: bool) -> list[dict[str, Any]]:
    if values is None:
        values = []
    if not isinstance(values, Sequence) or isinstance(values, str | bytes):
        raise ServiceManagementInputError(f"{field} must be a sequence")
    refs = [_json_copy(value) for value in values if isinstance(value, Mapping)]
    if require and not refs:
        raise ServiceManagementInputError(f"{field} are required")
    for ref in refs:
        try:
            contracts.validate_artifact(
                "service_management_result",
                {
                    "result_id": "service-management-result-ref-validation",
                    "schema_uri": RESULT_SCHEMA_URI,
                    "handoff_id": "handoff-ref-validation",
                    "status": "plan_only",
                    "contract_card_refs": [ref] if field == "contract_card_refs" else [],
                    "capsule_refs": [ref] if field == "capsule_refs" else [],
                    "semantic_tool_policy_refs": [ref] if field == "semantic_tool_policy_refs" else [],
                    "canonical_names": [],
                    "catalog_revision": None,
                    "consent_receipt_refs": [ref] if field == "consent_receipt_refs" else [],
                    "verification_trace_refs": [ref] if field == "verification_trace_refs" else [],
                    "redaction_status": "redacted",
                    "forbidden_follow_up_effects": ["project_init_catalog_mutation"],
                },
            )
        except contracts.ContractValidationError as exc:
            raise ServiceManagementInputError(str(exc)) from exc
    return refs


def _assert_redacted(data: Any) -> None:
    try:
        contracts.validate_redacted(data, require_status=isinstance(data, Mapping) and "redaction_status" in data)
    except contracts.RedactionValidationError as exc:
        raise ServiceManagementInputError(str(exc)) from exc


def _catalog_action(action: str) -> str:
    normalized = str(action).lower().replace("-", "_")
    if normalized in {"promote", "promotion", "add", "create"}:
        return "promote"
    if normalized in {"update", "repair", "refresh"}:
        return "update" if normalized != "repair" else "repair"
    raise ServiceManagementInputError(f"unsupported catalog action: {action}")


def _mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ServiceManagementInputError(f"{name} must be a mapping")
    return _json_copy(value)


def _json_copy(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_copy(child) for key, child in value.items()}
    if isinstance(value, tuple):
        return [_json_copy(item) for item in value]
    if isinstance(value, list):
        return [_json_copy(item) for item in value]
    if value is None or isinstance(value, str | bool | int | float):
        return copy.deepcopy(value)
    return str(value)


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _first_string(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value:
            return value
    return None


def _string_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _normalize_optional(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, Mapping):
        value = _first_string(value.get("id"), value.get("name"), value.get("scope"), value.get("tenant"), value.get("resource"))
    normalized = str(value).strip().lower() if value is not None else ""
    return normalized or None


def _normalize_required(value: Any, fallback: str) -> str:
    return _normalize_optional(value) or fallback


def _transport_name(value: str) -> str:
    normalized = value.lower().replace("-", "_")
    if normalized in {"http", "mcp_http", "streamable_http"}:
        return "streamable_http"
    return normalized


def _identifier(prefix: str, value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.:/@+-]+", "-", f"{prefix}-{value}".strip())
    slug = re.sub(r"-+", "-", slug).strip("-")
    if not slug:
        slug = "unknown"
    if not re.match(r"^[A-Za-z0-9]", slug):
        slug = f"id-{slug}"
    return slug


def _identifier_value(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.:/@+-]+", "-", value.strip())
    slug = re.sub(r"-+", "-", slug).strip("-")
    if not slug:
        slug = "uncataloged"
    if not re.match(r"^[A-Za-z0-9]", slug):
        slug = f"id-{slug}"
    return slug


def _unique(values: Iterable[str]) -> list[str]:
    output = []
    seen = set()
    for value in values:
        if value not in seen:
            output.append(value)
            seen.add(value)
    return output


__all__ = [
    "ServiceManagementInputError",
    "build_approved_completion_result",
    "build_catalog_plan",
    "build_dedupe_existing_result",
    "build_refusal_result",
    "classify_transport_decision",
    "completion_record_consumable",
    "dedupe_identity",
    "find_duplicate_service",
    "plan_service_management_from_handoff",
    "stable_digest",
]
