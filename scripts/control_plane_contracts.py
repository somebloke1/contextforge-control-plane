#!/usr/bin/env python3
"""Validators for ContextForge control-plane contract artifacts."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schemas/control-plane/contract-artifacts.schema.json"

ARTIFACT_KINDS = {
    "service_binding_contract_card",
    "shared_service_capability_capsule",
    "semantic_tool_policy",
    "service_memory_provider",
    "service_management_handoff",
    "service_management_result",
    "service_provision_plan",
    "consent_receipt",
    "verification_trace",
    "client_adapter_conformance_pack",
    "requirement_scenario",
    "evaluator_verdict",
    "evidence_ledger",
    "governance_reconciliation_pack",
}

REDACTION_REQUIRED_KINDS = {
    "service_management_handoff",
    "service_management_result",
    "service_provision_plan",
    "consent_receipt",
    "verification_trace",
    "client_adapter_conformance_pack",
    "evaluator_verdict",
    "evidence_ledger",
    "governance_reconciliation_pack",
    "service_memory_provider",
}

SECRET_KEY_RE = re.compile(
    r"(api[_-]?key|auth[_-]?token|bearer|client[_-]?secret|credential|jwt|password|"
    r"private[_-]?key|refresh[_-]?token|secret|session[_-]?token|token)",
    re.IGNORECASE,
)
SECRET_VALUE_RE = re.compile(
    r"(-----BEGIN [A-Z ]*PRIVATE KEY-----|"
    r"\bBearer\s+[A-Za-z0-9._~+/=-]{12,}|"
    r"\b(?:sk|pk|ghp|gho|github_pat|xox[baprs]|ya29)[_-][A-Za-z0-9._-]{12,}|"
    r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}|"
    r"(?i:\b(?:api[_-]?key|token|password|secret)\s*=\s*[^\\s'\"<>]+))"
)
SECRET_METADATA_KEYS = {
    "credential_scope",
    "source_client_auth_strength",
    "token_source_constraints",
}
SAFE_REDACTED_VALUE_RE = re.compile(
    r"^(|null|none|n/a|redacted|redacted-[A-Za-z0-9_.:-]+|"
    r"\*\*\*|<redacted>|\\$\\{[A-Z0-9_]+\\}|placeholder)$",
    re.IGNORECASE,
)
ISOLATION_FORBIDDEN_RE = re.compile(
    r"(hidden|hidden_initial_conditions|hidden_state_delta|evaluator|evaluator_only|"
    r"rubric|oracle|remediation|remediator|future judge|test harness|under test)",
    re.IGNORECASE,
)


class ContractValidationError(ValueError):
    """Base exception for contract artifact validation failures."""


class UnknownArtifactKindError(ContractValidationError):
    """Raised when a caller asks to validate an unknown artifact kind."""


class SchemaValidationError(ContractValidationError):
    """Raised when JSON Schema validation fails."""


class RedactionValidationError(ContractValidationError):
    """Raised when a secret-like key or value appears in an artifact."""


class InferentialIsolationError(ContractValidationError):
    """Raised when a scenario leaks hidden or evaluator-only state."""


def load_schema(path: Path = SCHEMA_PATH) -> dict[str, Any]:
    """Load the contract artifact JSON Schema."""

    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def schema_validator(schema: Mapping[str, Any] | None = None) -> Draft202012Validator:
    """Return a Draft 2020-12 validator for the contract schema."""

    loaded = dict(schema) if schema is not None else load_schema()
    Draft202012Validator.check_schema(loaded)
    return Draft202012Validator(loaded)


def artifact_digest(data: Mapping[str, Any]) -> str:
    """Return a stable sha256 digest string for a JSON-compatible artifact."""

    encoded = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def artifact_ref(
    ref: str,
    data: Mapping[str, Any],
    *,
    resolved_at: str,
    catalog_revision_or_etag: str | None = None,
) -> dict[str, Any]:
    """Build a snapshot ref with digest metadata for stale-plan checks."""

    return {
        "ref": ref,
        "content_digest": artifact_digest(data),
        "catalog_revision_or_etag": catalog_revision_or_etag,
        "resolved_at": resolved_at,
    }


def validate_artifact(kind: str, data: Mapping[str, Any]) -> Mapping[str, Any]:
    """Validate one contract artifact by kind and return the input on success."""

    if kind not in ARTIFACT_KINDS:
        raise UnknownArtifactKindError(f"unknown contract artifact kind: {kind}")
    schema = load_schema()
    subschema = {"$schema": schema["$schema"], "$defs": schema["$defs"], "$ref": f"#/$defs/{kind}"}
    validator = Draft202012Validator(subschema)
    try:
        validator.validate(data)
    except JsonSchemaValidationError as exc:
        location = "/".join(str(part) for part in exc.absolute_path)
        prefix = f"{kind}"
        if location:
            prefix = f"{prefix} at {location}"
        raise SchemaValidationError(f"{prefix}: {exc.message}") from exc

    validate_redacted(data, require_status=kind in REDACTION_REQUIRED_KINDS)
    if kind == "requirement_scenario":
        validate_scenario_isolation(data)
    if kind == "service_memory_provider":
        _validate_service_memory_provider(data)
    if kind == "evaluator_verdict":
        _validate_verdict_evidence(data)
    return data


def validate_redacted(data: Any, *, require_status: bool = False) -> Any:
    """Reject secret-bearing keys and values in a JSON-compatible object."""

    if require_status:
        status = data.get("redaction_status") if isinstance(data, Mapping) else None
        if status not in {"redacted", "passed"}:
            raise RedactionValidationError("redaction_status must be redacted or passed")

    for path, value in _walk(data):
        key = str(path[-1]) if path else ""
        if key not in SECRET_METADATA_KEYS and SECRET_KEY_RE.search(key) and not _safe_secret_placeholder(value):
            raise RedactionValidationError(f"secret-bearing field is not redacted: {_format_path(path)}")
        if isinstance(value, str) and SECRET_VALUE_RE.search(value):
            raise RedactionValidationError(f"secret-like value is not redacted: {_format_path(path)}")
    return data


def validate_scenario_isolation(data: Mapping[str, Any]) -> Mapping[str, Any]:
    """Enforce inferential isolation for tested-agent-visible scenario content."""

    tested_agent_view = data.get("tested_agent_view", {})
    _reject_isolation_terms(tested_agent_view, ("tested_agent_view",))

    for index, event in enumerate(data.get("during_test_events", [])):
        event_path = ("during_test_events", str(index))
        visible_to = set(event.get("visible_to", []))
        payload_visible = "tested_agent" in visible_to or event.get("tool_output_visibility") == "tested_agent"
        if payload_visible:
            _reject_isolation_terms(event.get("payload", {}), (*event_path, "payload"))
        if event.get("evaluator_only") and "tested_agent" in visible_to:
            raise InferentialIsolationError(f"evaluator-only event visible to tested agent: {_format_path(event_path)}")
        if event.get("tool_output_visibility") == "tested_agent" and event.get("hidden_state_delta"):
            raise InferentialIsolationError(
                f"tested-agent-visible tool output carries hidden_state_delta: {_format_path(event_path)}"
            )
    return data


def _validate_verdict_evidence(data: Mapping[str, Any]) -> None:
    verdict = data.get("verdict")
    evidence = data.get("evidence", [])
    failed_requirements = data.get("failed_requirements", [])
    if verdict in {"fail", "inconclusive", "requirement_gap"} and not evidence:
        raise SchemaValidationError("evaluator_verdict requires cited evidence for non-pass verdicts")
    if verdict == "fail" and not failed_requirements:
        raise SchemaValidationError("failed evaluator_verdict requires failed_requirements")
    if verdict == "requirement_gap" and not data.get("requirement_gap_proposal"):
        raise SchemaValidationError("requirement_gap verdict requires requirement_gap_proposal")


def _validate_service_memory_provider(data: Mapping[str, Any]) -> None:
    operations = set(data.get("supported_operations", []))
    if "none" in operations and len(operations) > 1:
        raise SchemaValidationError("service_memory_provider supported_operations cannot combine none with other operations")
    if operations & {"write", "update", "delete", "rename"} and not data.get("writes_require_approval"):
        raise SchemaValidationError("service_memory_provider mutating operations require writes_require_approval")

    policy = data.get("governance_reference_policy", {})
    if isinstance(policy, Mapping):
        if policy.get("generated_governance_projection_allowed") is not False:
            raise SchemaValidationError("service_memory_provider cannot allow generated governance projection")
        if policy.get("bidirectional_sync_allowed") is not False:
            raise SchemaValidationError("service_memory_provider cannot allow bidirectional sync")

    conflict_behavior = data.get("conflict_flag_behavior", {})
    if isinstance(conflict_behavior, Mapping) and conflict_behavior.get("authority") != "governance_ledger":
        raise SchemaValidationError("service_memory_provider conflicts must prefer governance ledger authority")


def _walk(value: Any, path: tuple[str, ...] = ()) -> Iterable[tuple[tuple[str, ...], Any]]:
    yield path, value
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield from _walk(child, (*path, str(key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, (*path, str(index)))


def _safe_secret_placeholder(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, bool | int | float):
        return True
    if isinstance(value, str):
        return bool(SAFE_REDACTED_VALUE_RE.match(value))
    if isinstance(value, list):
        return all(_safe_secret_placeholder(item) for item in value)
    if isinstance(value, Mapping):
        return all(_safe_secret_placeholder(item) for item in value.values())
    return False


def _reject_isolation_terms(value: Any, path: tuple[str, ...]) -> None:
    for child_path, child in _walk(value, path):
        key = child_path[-1] if child_path else ""
        if ISOLATION_FORBIDDEN_RE.search(key):
            raise InferentialIsolationError(f"tested-agent-visible field leaks isolation metadata: {_format_path(child_path)}")
        if isinstance(child, str) and ISOLATION_FORBIDDEN_RE.search(child):
            raise InferentialIsolationError(f"tested-agent-visible value leaks isolation metadata: {_format_path(child_path)}")


def _format_path(path: Iterable[str]) -> str:
    parts = list(path)
    return ".".join(parts) if parts else "<root>"


def clone_artifact(data: Mapping[str, Any]) -> dict[str, Any]:
    """Return a deep JSON-compatible copy for test fixtures and callers."""

    return copy.deepcopy(dict(data))
