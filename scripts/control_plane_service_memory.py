#!/usr/bin/env python3
"""Pure service-memory provider metadata and advisory governance helpers."""

from __future__ import annotations

import copy
import re
from collections.abc import Mapping, Sequence
from typing import Any

import control_plane_contracts as contracts
import control_plane_redaction as redaction


SCHEMA_URI = "contextforge://control-plane/schemas/service-memory-provider/v1"
DEFAULT_REFERENCE_FORMAT = "ledger_id:<dec-*|oq-*|ai-*>"
DEFAULT_ALLOWED_LEDGER_PREFIXES = ("dec-", "oq-", "ai-")
GOVERNANCE_LEDGER_BY_PREFIX = {
    "dec-": "DECISIONS.md",
    "oq-": "OPEN_QUESTIONS.md",
    "ai-": "ABEYANT_INTENTIONS.md",
}
PROVIDER_SCOPES = {"project", "repository", "credential", "session", "host"}
DURABILITY_CLASSES = {
    "ephemeral",
    "session_persistent",
    "project_persistent",
    "repository_persistent",
    "host_persistent",
    "external_service_persistent",
}
STORAGE_LOCATION_CLASSES = {
    "service_local_store",
    "project_local_file",
    "repository_local_file",
    "host_user_state",
    "host_system_state",
    "remote_service",
    "unknown",
}
SUPPORTED_OPERATIONS = {"list", "read", "write", "update", "delete", "rename", "none"}
MUTATING_OPERATIONS = {"write", "update", "delete", "rename"}
ALLOWED_RECORD_CLASSES = {
    "working_note",
    "recall_hint",
    "code_navigation_note",
    "governance_reference",
    "governance_proposal",
    "conflict_flag",
}
GOVERNANCE_SUBJECTS = {"decision", "open_question", "parked_intention", "consent", "project_policy", "conflict"}
FORBIDDEN_EFFECTS = (
    "settle_governance_decision",
    "settle_open_question",
    "settle_parked_intention",
    "record_consent",
    "change_project_policy",
    "edit_governance_ledgers",
    "generate_governance_projection",
    "bidirectional_sync",
)
DEFAULT_VERIFICATION_FIELDS = (
    "provider_name",
    "service_binding",
    "provider_scope",
    "supported_operations",
    "allowed_record_classes",
    "governance_reference_policy",
)


class ServiceMemoryError(ValueError):
    """Raised when service-memory metadata or advisory records are invalid."""


def build_service_memory_provider_metadata(
    *,
    provider_name: str,
    service_binding: str,
    provider_scope: str,
    durability: str,
    storage_location_class: str,
    supported_operations: Sequence[str] = ("list", "read"),
    allowed_record_classes: Sequence[str] = (
        "working_note",
        "recall_hint",
        "code_navigation_note",
        "governance_reference",
        "governance_proposal",
        "conflict_flag",
    ),
    governance_reference_format: str = DEFAULT_REFERENCE_FORMAT,
    allowed_ledger_id_prefixes: Sequence[str] = DEFAULT_ALLOWED_LEDGER_PREFIXES,
    verification_probe: Mapping[str, Any] | None = None,
    writes_require_approval: bool | None = None,
) -> dict[str, Any]:
    """Build and validate reference/proposal-only provider capability metadata."""

    operations = _validated_set("supported_operations", supported_operations, SUPPORTED_OPERATIONS)
    record_classes = _validated_set("allowed_record_classes", allowed_record_classes, ALLOWED_RECORD_CLASSES)
    prefixes = _validated_set("allowed_ledger_id_prefixes", allowed_ledger_id_prefixes, set(DEFAULT_ALLOWED_LEDGER_PREFIXES))
    if "none" in operations and len(operations) > 1:
        raise ServiceMemoryError("supported_operations cannot combine none with other operations")
    if provider_scope not in PROVIDER_SCOPES:
        raise ServiceMemoryError(f"unsupported provider_scope: {provider_scope}")
    if durability not in DURABILITY_CLASSES:
        raise ServiceMemoryError(f"unsupported durability: {durability}")
    if storage_location_class not in STORAGE_LOCATION_CLASSES:
        raise ServiceMemoryError(f"unsupported storage_location_class: {storage_location_class}")

    requires_approval = bool(operations & MUTATING_OPERATIONS) if writes_require_approval is None else bool(writes_require_approval)
    if operations & MUTATING_OPERATIONS and not requires_approval:
        raise ServiceMemoryError("mutating service-memory operations require approval")

    probe = _verification_probe(verification_probe)
    provider_id_source = "redacted" if redaction.classify_sensitive_value(provider_name) else provider_name
    provider_id = "memory-provider-" + _slug(provider_id_source)
    artifact = {
        "provider_id": provider_id,
        "schema_uri": SCHEMA_URI,
        "provider_name": provider_name,
        "service_binding": service_binding,
        "provider_scope": provider_scope,
        "durability": durability,
        "storage_location_class": storage_location_class,
        "supported_operations": sorted(operations),
        "allowed_record_classes": sorted(record_classes),
        "governance_reference_policy": {
            "reference_format": governance_reference_format,
            "allowed_ledger_id_prefixes": sorted(prefixes),
            "authoritative_source": "governance_ledgers",
            "required_write_path": "mentality_or_governance_crud_after_user_approval",
            "generated_governance_projection_allowed": False,
            "bidirectional_sync_allowed": False,
        },
        "conflict_flag_behavior": {
            "on_conflict": "flag_and_prefer_governance_ledger",
            "authority": "governance_ledger",
            "memory_mutation": "none",
            "proposal_allowed": True,
            "warning_class": "service_memory_governance_conflict",
        },
        "verification_probe": probe,
        "writes_require_approval": requires_approval,
        "advisory_only": True,
        "forbidden_effects": list(FORBIDDEN_EFFECTS),
        "redaction_status": "passed",
    }
    sanitized, redacted_count = _sanitize_for_contract(artifact)
    sanitized["redaction_status"] = "redacted" if redacted_count else "passed"
    contracts.validate_artifact("service_memory_provider", sanitized)
    return sanitized


def build_governance_reference(
    provider: Mapping[str, Any],
    governance_id: str,
    *,
    summary: str | None = None,
    source_ref: str | None = None,
) -> dict[str, Any]:
    """Build an advisory memory record that points to, but does not replace, a ledger entry."""

    prefix = _allowed_prefix(provider, governance_id)
    record = {
        "record_class": "governance_reference",
        "provider_name": str(provider.get("provider_name", "")),
        "service_binding": str(provider.get("service_binding", "")),
        "governance_id": governance_id,
        "ledger": GOVERNANCE_LEDGER_BY_PREFIX[prefix],
        "reference": f"ledger_id:{governance_id}",
        "summary": summary,
        "source_ref": source_ref,
        "authoritative_source": "governance_ledger",
        "advisory_only": True,
        "settles_governance": False,
        "mutates_governance": False,
        "forbidden_effects": list(FORBIDDEN_EFFECTS),
    }
    return _sanitized_redacted_record(record)


def build_governance_proposal(
    provider: Mapping[str, Any],
    *,
    proposal_type: str,
    summary: str,
    proposed_operation: str = "propose_governance_update",
    governance_ids: Sequence[str] = (),
) -> dict[str, Any]:
    """Build a non-mutating proposal that must be accepted through governance tooling."""

    if proposal_type not in GOVERNANCE_SUBJECTS:
        raise ServiceMemoryError(f"unsupported proposal_type: {proposal_type}")
    for governance_id in governance_ids:
        _allowed_prefix(provider, governance_id)

    record = {
        "record_class": "governance_proposal",
        "proposal_type": proposal_type,
        "proposal_status": "proposed_only",
        "provider_name": str(provider.get("provider_name", "")),
        "service_binding": str(provider.get("service_binding", "")),
        "summary": summary,
        "proposed_operation": proposed_operation,
        "governance_ids": list(governance_ids),
        "required_write_path": "mentality_or_governance_crud_after_user_approval",
        "writes_require_approval": True,
        "authoritative_source": "governance_ledger",
        "advisory_only": True,
        "settles_governance": False,
        "mutates_governance": False,
        "forbidden_effects": list(FORBIDDEN_EFFECTS),
    }
    return _sanitized_redacted_record(record)


def flag_governance_conflict(
    provider: Mapping[str, Any],
    *,
    governance_id: str,
    memory_summary: str,
    governance_summary: str,
) -> dict[str, Any]:
    """Return a non-mutating conflict flag that keeps governance as authority."""

    prefix = _allowed_prefix(provider, governance_id)
    proposal = build_governance_proposal(
        provider,
        proposal_type="conflict",
        summary=f"Review service-memory conflict for {governance_id}.",
        proposed_operation="review_conflict_without_mutation",
        governance_ids=(governance_id,),
    )
    record = {
        "record_class": "conflict_flag",
        "provider_name": str(provider.get("provider_name", "")),
        "service_binding": str(provider.get("service_binding", "")),
        "governance_id": governance_id,
        "ledger": GOVERNANCE_LEDGER_BY_PREFIX[prefix],
        "conflict_status": "flagged",
        "authority": "governance_ledger",
        "selected_value_source": "governance_ledger",
        "memory_value_used_as_authority": False,
        "memory_summary": memory_summary,
        "governance_summary": governance_summary,
        "warnings": [
            {
                "warning_class": "service_memory_governance_conflict",
                "severity": "warning",
                "message": "Service-local memory conflicts with governance; governance ledger remains authoritative.",
            }
        ],
        "proposal": proposal,
        "advisory_only": True,
        "settles_governance": False,
        "mutates_governance": False,
        "forbidden_effects": list(FORBIDDEN_EFFECTS),
    }
    return _sanitized_redacted_record(record)


def sanitize_memory_provider_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return a secret-free copy suitable for service-memory metadata or records."""

    sanitized, _ = _sanitize_for_contract(payload)
    contracts.validate_redacted(sanitized)
    return sanitized


def _verification_probe(probe: Mapping[str, Any] | None) -> dict[str, Any]:
    base: dict[str, Any] = {
        "probe_type": "metadata_readback",
        "expected_fields": list(DEFAULT_VERIFICATION_FIELDS),
        "mutation_allowed": False,
    }
    if probe:
        for key, value in probe.items():
            if key in {"probe_type", "expected_fields"} or key.startswith("x_"):
                base[str(key)] = copy.deepcopy(value)
        base["mutation_allowed"] = False
    if not isinstance(base.get("expected_fields"), list) or not base["expected_fields"]:
        raise ServiceMemoryError("verification_probe.expected_fields must be a non-empty list")
    return base


def _allowed_prefix(provider: Mapping[str, Any], governance_id: str) -> str:
    policy = provider.get("governance_reference_policy", {})
    allowed = set(DEFAULT_ALLOWED_LEDGER_PREFIXES)
    if isinstance(policy, Mapping):
        supplied = policy.get("allowed_ledger_id_prefixes")
        if isinstance(supplied, list) and supplied:
            allowed = {str(item) for item in supplied}
    for prefix in sorted(allowed):
        if governance_id.startswith(prefix) and prefix in GOVERNANCE_LEDGER_BY_PREFIX:
            return prefix
    raise ServiceMemoryError(f"governance_id is not allowed by provider policy: {governance_id}")


def _validated_set(name: str, values: Sequence[str], allowed: set[str]) -> set[str]:
    result = {str(value) for value in values}
    unknown = result - allowed
    if unknown:
        raise ServiceMemoryError(f"{name} contains unsupported values: {sorted(unknown)}")
    return result


def _sanitized_redacted_record(record: Mapping[str, Any]) -> dict[str, Any]:
    sanitized, redacted_count = _sanitize_for_contract(record)
    sanitized["redaction_status"] = "redacted" if redacted_count else "passed"
    contracts.validate_redacted(sanitized, require_status=True)
    return sanitized


def _sanitize_for_contract(value: Any) -> tuple[Any, int]:
    if isinstance(value, Mapping):
        redacted_count = 0
        sanitized: dict[str, Any] = {}
        for key, child in value.items():
            key_text = str(key)
            if redaction.classify_sensitive_key(key_text):
                sanitized[key_text] = redaction.REDACTED_MARKER
                redacted_count += 1
                continue
            sanitized_child, child_count = _sanitize_for_contract(child)
            sanitized[key_text] = sanitized_child
            redacted_count += child_count
        return sanitized, redacted_count
    if isinstance(value, list | tuple):
        redacted_count = 0
        sanitized_list = []
        for child in value:
            sanitized_child, child_count = _sanitize_for_contract(child)
            sanitized_list.append(sanitized_child)
            redacted_count += child_count
        return sanitized_list, redacted_count
    if isinstance(value, str) and redaction.classify_sensitive_value(value):
        return redaction.REDACTED_MARKER, 1
    return copy.deepcopy(value), 0


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.:+-]+", "-", value.strip()).strip("-")
    if not slug:
        return "provider"
    if not re.match(r"^[A-Za-z0-9]", slug):
        slug = "provider-" + slug
    return slug


__all__ = [
    "ALLOWED_RECORD_CLASSES",
    "DEFAULT_ALLOWED_LEDGER_PREFIXES",
    "FORBIDDEN_EFFECTS",
    "GOVERNANCE_LEDGER_BY_PREFIX",
    "MUTATING_OPERATIONS",
    "SCHEMA_URI",
    "SUPPORTED_OPERATIONS",
    "ServiceMemoryError",
    "build_governance_proposal",
    "build_governance_reference",
    "build_service_memory_provider_metadata",
    "flag_governance_conflict",
    "sanitize_memory_provider_payload",
]
