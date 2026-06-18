#!/usr/bin/env python3
"""Pure verification trace and lifecycle-transition helpers."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

import control_plane_contracts as contracts


SCHEMA_URI = "contextforge://control-plane/schemas/verification-trace/v1"
TRACE_REF_PREFIX = "run/verification-traces"
REDACTED_MARKER = "<redacted>"
EVIDENCE_SURFACES = frozenset(
    {
        "legacy_live_read_only",
        "contextforge_dev_docker",
        "pi_client_docker",
        "opencode_client_docker",
        "local_source",
        "target_client",
        "generated_run_evidence",
    }
)
VERIFICATION_LAYERS = frozenset(
    {
        "backend",
        "contextforge_gateway",
        "virtual_server",
        "target_client",
        "trust",
        "tool_policy",
        "redaction",
    }
)
TRACE_RESULT_STATUSES = frozenset({"passed", "failed", "stale", "pending", "not_applicable", "inconclusive"})
PASSING_STATUSES = frozenset({"passed"})
BLOCKING_STATUSES = frozenset({"failed", "stale", "pending", "missing", "mismatched", "inconclusive"})
SURFACE_LAYER_SUPPORT = {
    "legacy_live_read_only": frozenset({"backend", "contextforge_gateway", "virtual_server", "target_client"}),
    "contextforge_dev_docker": frozenset({"backend", "contextforge_gateway", "virtual_server"}),
    "pi_client_docker": frozenset({"target_client"}),
    "opencode_client_docker": frozenset({"target_client"}),
    "local_source": frozenset({"trust", "tool_policy", "redaction"}),
    "target_client": frozenset({"target_client"}),
    "generated_run_evidence": VERIFICATION_LAYERS,
}
SECRET_KEY_RE = re.compile(
    r"(api[_-]?key|auth[_-]?token|bearer|client[_-]?secret|credential|jwt|password|"
    r"private[_-]?key|refresh[_-]?token|secret|session[_-]?token|token)",
    re.IGNORECASE,
)
SECRET_VALUE_RE = re.compile(
    r"(-----BEGIN [A-Z ]*PRIVATE KEY-----|"
    r"\bBearer\s+[A-Za-z0-9._~+/=-]{8,}|"
    r"\b(?:sk|pk|ghp|gho|github_pat|xox[baprs]|ya29)[_-][A-Za-z0-9._-]{8,}|"
    r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}|"
    r"(?i:\b(?:api[_-]?key|auth[_-]?token|token|password|secret)\s*=\s*[^\\s'\"<>]+))"
)
SAFE_SECRET_METADATA_KEYS = frozenset(
    {
        "credential_scope",
        "source_client_auth_strength",
        "token_source_constraints",
    }
)


class VerificationTraceError(ValueError):
    """Raised when a trace or transition request is invalid."""


def now_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stable_digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def build_verification_trace(
    *,
    trace_id: str,
    plan_id: str | None,
    step_id: str,
    service_binding: str,
    layer: str,
    probe_id: str,
    probe_type: str,
    subject: str,
    status: str,
    observations: Any,
    exercised_surface: str | None = None,
    target_client: str | None = None,
    adapter_conformance_pack: Mapping[str, Any] | None = None,
    failure_classification: str | None = None,
    negative_checks: Sequence[Mapping[str, Any]] = (),
    redaction_checks: Sequence[Mapping[str, Any]] = (),
    generated_at: str | None = None,
    raw_sensitive_values: Iterable[str] = (),
) -> dict[str, Any]:
    """Build a schema-valid, redacted verification trace for one probe result."""

    _require_identifier("trace_id", trace_id)
    if plan_id is not None:
        _require_identifier("plan_id", plan_id)
    _require_identifier("step_id", step_id)
    _require_identifier("probe_id", probe_id)
    if not service_binding:
        raise VerificationTraceError("service_binding is required")
    if layer not in VERIFICATION_LAYERS:
        raise VerificationTraceError(f"unknown verification layer: {layer}")
    normalized_surface = _normalize_exercised_surface(exercised_surface or _default_surface_for_layer(layer))
    normalized_status = _normalize_status(status)
    if normalized_status in {"failed", "stale"} and not failure_classification:
        raise VerificationTraceError("failed or stale traces require failure_classification")

    redacted_observations = redact_observations(observations, raw_sensitive_values=raw_sensitive_values)
    observation_digest = stable_digest(redacted_observations)
    probe_event = {
        "probe_id": probe_id,
        "layer": layer,
        "status": _schema_probe_status(normalized_status),
        "evidence_hash": observation_digest,
        "summary": _summary_for(redacted_observations),
        "x_step_id": step_id,
        "x_probe_type": str(probe_type),
        "x_subject": str(subject),
        "x_result_status": normalized_status,
        "x_observation_digest": observation_digest,
        "x_redacted_observations": redacted_observations,
        "x_observation_redaction": {
            "raw_observation_included": False,
            "redacted_observation_digest": observation_digest,
        },
    }
    if failure_classification:
        probe_event["x_failure_classification"] = str(failure_classification)

    trace_result = _schema_trace_result(normalized_status)
    trace = {
        "trace_id": trace_id,
        "schema_uri": SCHEMA_URI,
        "plan_id": plan_id,
        "service_binding": service_binding,
        "exercised_surface": normalized_surface,
        "target_client": target_client,
        "adapter_conformance_pack": copy.deepcopy(dict(adapter_conformance_pack)) if adapter_conformance_pack else None,
        "probe_events": [probe_event],
        "negative_checks": [redact_observations(dict(item), raw_sensitive_values=raw_sensitive_values) for item in negative_checks],
        "redaction_checks": _redaction_checks(redaction_checks, redacted_observations),
        "result": trace_result,
        "failed_layer": layer if trace_result == "failed" else None,
        "result_hash": stable_digest(
            {
                "trace_id": trace_id,
                "plan_id": plan_id,
                "step_id": step_id,
                "service_binding": service_binding,
                "target_client": target_client,
                "layer": layer,
                "probe_id": probe_id,
                "status": normalized_status,
                "observation_digest": observation_digest,
                "failure_classification": failure_classification,
            }
        ),
        "generated_at": generated_at or now_timestamp(),
        "redaction_status": "redacted",
        "x_step_id": step_id,
        "x_verification_layer": layer,
        "x_exercised_surface": normalized_surface,
        "x_probe_type": str(probe_type),
        "x_subject": str(subject),
        "x_result_status": normalized_status,
        "x_observation_digest": observation_digest,
        "x_failure_classification": failure_classification,
    }
    assert_no_secret_material(trace, raw_sensitive_values=raw_sensitive_values)
    contracts.validate_artifact("verification_trace", trace)
    return trace


def validate_surface_claim(
    *,
    target_state: str,
    required_layers: Sequence[str],
    trace_artifacts: Mapping[str, Mapping[str, Any]] | Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Return whether trace surfaces can support a target readiness claim."""

    required = list(required_layers)
    for layer in required:
        if layer not in VERIFICATION_LAYERS:
            raise VerificationTraceError(f"unknown verification layer: {layer}")
    trace_index = _trace_index(trace_artifacts)
    unsupported: list[dict[str, str]] = []
    for ref, trace in trace_index.items():
        layer = str(trace.get("x_verification_layer") or _first_probe_layer(trace) or "")
        surface = _trace_exercised_surface(trace)
        supported_layers = SURFACE_LAYER_SUPPORT[surface]
        if layer in required and layer not in supported_layers:
            unsupported.append(
                {
                    "trace_ref": ref,
                    "trace_id": str(trace.get("trace_id") or ""),
                    "layer": layer,
                    "exercised_surface": surface,
                    "reason": f"{surface} evidence cannot prove {layer}",
                }
            )
    valid = not unsupported
    reason = "passed"
    if unsupported:
        reason = "surface_cannot_support_required_layer"
    return {
        "target_state": target_state,
        "valid": valid,
        "decision": "allow" if valid else "block",
        "reason": reason,
        "required_layers": required,
        "unsupported_surfaces": unsupported,
    }


def build_verification_trace_ref(
    trace: Mapping[str, Any],
    *,
    ref: str | None = None,
    resolved_at: str | None = None,
    catalog_revision_or_etag: str | None = None,
) -> dict[str, Any]:
    """Return an artifact ref for a verification trace."""

    contracts.validate_artifact("verification_trace", trace)
    trace_ref = ref or f"{TRACE_REF_PREFIX}/{trace['trace_id']}.json"
    return contracts.artifact_ref(
        trace_ref,
        trace,
        resolved_at=resolved_at or str(trace["generated_at"]),
        catalog_revision_or_etag=catalog_revision_or_etag,
    )


def validate_lifecycle_transition(
    *,
    plan_id: str | None,
    step_id: str,
    service_binding: str,
    target_state: str,
    required_layers: Sequence[str],
    trace_refs: Sequence[str | Mapping[str, Any]],
    trace_artifacts: Mapping[str, Mapping[str, Any]] | Sequence[Mapping[str, Any]],
    target_client: str | None = None,
) -> dict[str, Any]:
    """Evaluate a lifecycle transition against trace refs without mutating state."""

    _require_identifier("step_id", step_id)
    if plan_id is not None:
        _require_identifier("plan_id", plan_id)
    for layer in required_layers:
        if layer not in VERIFICATION_LAYERS:
            raise VerificationTraceError(f"unknown verification layer: {layer}")

    refs = [_ref_key(item) for item in trace_refs]
    trace_index = _trace_index(trace_artifacts)
    matrix = build_verification_matrix(
        plan_id=plan_id,
        step_id=step_id,
        service_binding=service_binding,
        required_layers=required_layers,
        trace_refs=trace_refs,
        trace_artifacts=trace_artifacts,
        target_client=target_client,
    )
    surface_claim = validate_surface_claim(
        target_state=target_state,
        required_layers=required_layers,
        trace_artifacts=trace_artifacts,
    )
    requires_passed = target_state in {"backend_ready", "registered", "verified", "removed"}
    missing_refs = [ref for ref in refs if ref not in trace_index]
    digest_mismatches = [
        ref
        for ref in trace_refs
        if isinstance(ref, Mapping)
        and ref.get("content_digest")
        and _ref_key(ref) in trace_index
        and _trace_content_digest(trace_index[_ref_key(ref)]) != ref.get("content_digest")
    ]
    invalid_layers = [
        layer
        for layer, outcome in matrix["layers"].items()
        if requires_passed and outcome["status"] not in PASSING_STATUSES
    ]
    valid = not missing_refs and not digest_mismatches and not invalid_layers
    if requires_passed and not refs:
        valid = False
    if valid and not surface_claim["valid"]:
        valid = False
    reason = "passed"
    if not refs and requires_passed:
        reason = "missing_trace_ref"
    elif not surface_claim["valid"]:
        reason = surface_claim["reason"]
    elif missing_refs:
        reason = "trace_ref_not_found"
    elif digest_mismatches:
        reason = "trace_ref_digest_mismatch"
    elif invalid_layers:
        reason = "required_trace_not_passed"

    return {
        "target_state": target_state,
        "valid": valid,
        "decision": "allow" if valid else "block",
        "reason": reason,
        "plan_id": plan_id,
        "step_id": step_id,
        "service_binding": service_binding,
        "target_client": target_client,
        "required_layers": list(required_layers),
        "trace_refs": refs,
        "missing_trace_refs": missing_refs,
        "digest_mismatched_trace_refs": [_ref_key(ref) for ref in digest_mismatches],
        "surface_claim": surface_claim,
        "matrix": matrix,
    }


def build_verification_matrix(
    *,
    plan_id: str | None,
    step_id: str,
    service_binding: str,
    required_layers: Sequence[str],
    trace_refs: Sequence[str | Mapping[str, Any]],
    trace_artifacts: Mapping[str, Mapping[str, Any]] | Sequence[Mapping[str, Any]],
    target_client: str | None = None,
) -> dict[str, Any]:
    """Classify required verification layers from referenced trace artifacts."""

    refs = [_ref_key(item) for item in trace_refs]
    trace_index = _trace_index(trace_artifacts)
    layers: dict[str, dict[str, Any]] = {}
    for layer in required_layers:
        mismatched_refs = {
            _ref_key(ref)
            for ref in trace_refs
            if isinstance(ref, Mapping)
            and ref.get("content_digest")
            and _ref_key(ref) in trace_index
            and _trace_content_digest(trace_index[_ref_key(ref)]) != ref.get("content_digest")
        }
        candidates = [
            trace_index[ref]
            for ref in refs
            if ref in trace_index and ref not in mismatched_refs and _trace_has_layer(trace_index[ref], layer)
        ]
        if any(ref in mismatched_refs and _trace_has_layer(trace_index[ref], layer) for ref in refs if ref in trace_index):
            layers[layer] = _layer_outcome("mismatched", trace_index[next(ref for ref in refs if ref in mismatched_refs and ref in trace_index)], "trace ref content digest does not match artifact")
            continue
        matching = [
            trace
            for trace in candidates
            if _trace_matches(trace, plan_id=plan_id, step_id=step_id, service_binding=service_binding, target_client=target_client)
        ]
        if not candidates:
            layers[layer] = _layer_outcome("missing", None, "no referenced trace for required layer")
            continue
        if not matching:
            layers[layer] = _layer_outcome("mismatched", candidates[0], "trace is not tied to requested plan/step/service/client")
            continue
        best = _best_trace(matching)
        status = trace_result_status(best)
        layers[layer] = _layer_outcome(status, best, _failure_reason(best) if status in BLOCKING_STATUSES else "passed")
    return {
        "required_layers": list(required_layers),
        "plan_id": plan_id,
        "step_id": step_id,
        "service_binding": service_binding,
        "target_client": target_client,
        "layers": layers,
        "summary": {
            "passed": sum(1 for item in layers.values() if item["status"] == "passed"),
            "failed": sum(1 for item in layers.values() if item["status"] == "failed"),
            "stale": sum(1 for item in layers.values() if item["status"] == "stale"),
            "missing": sum(1 for item in layers.values() if item["status"] == "missing"),
            "mismatched": sum(1 for item in layers.values() if item["status"] == "mismatched"),
            "pending": sum(1 for item in layers.values() if item["status"] == "pending"),
            "not_applicable": sum(1 for item in layers.values() if item["status"] == "not_applicable"),
        },
    }


def trace_result_status(trace: Mapping[str, Any]) -> str:
    status = trace.get("x_result_status")
    if status in TRACE_RESULT_STATUSES:
        return str(status)
    result = trace.get("result")
    if result == "passed":
        return "passed"
    if result == "failed":
        return "failed"
    return "inconclusive"


def redact_observations(data: Any, *, raw_sensitive_values: Iterable[str] = ()) -> Any:
    redacted = _redact(copy.deepcopy(data), (), raw_sensitive_values=set(raw_sensitive_values))
    assert_no_secret_material(redacted, raw_sensitive_values=raw_sensitive_values)
    return redacted


def assert_no_secret_material(data: Any, *, raw_sensitive_values: Iterable[str] = ()) -> None:
    blocked_values = {value for value in raw_sensitive_values if value}
    for path, value in _walk(data):
        key = path[-1] if path else ""
        if key not in SAFE_SECRET_METADATA_KEYS and SECRET_KEY_RE.search(str(key)) and not _is_redacted_placeholder(value):
            raise VerificationTraceError(f"secret-bearing field is not redacted: {_format_path(path)}")
        if isinstance(value, str):
            if SECRET_VALUE_RE.search(value):
                raise VerificationTraceError(f"secret-like value is not redacted: {_format_path(path)}")
            for raw in blocked_values:
                if raw in value:
                    raise VerificationTraceError(f"raw sensitive value remains: {_format_path(path)}")


def _redact(value: Any, path: tuple[str, ...], *, raw_sensitive_values: set[str]) -> Any:
    key = path[-1] if path else ""
    if key not in SAFE_SECRET_METADATA_KEYS and SECRET_KEY_RE.search(str(key)) and not _is_redacted_placeholder(value):
        return REDACTED_MARKER
    if isinstance(value, Mapping):
        return {str(child_key): _redact(child, (*path, str(child_key)), raw_sensitive_values=raw_sensitive_values) for child_key, child in value.items()}
    if isinstance(value, list):
        return [_redact(child, (*path, str(index)), raw_sensitive_values=raw_sensitive_values) for index, child in enumerate(value)]
    if isinstance(value, str):
        if SECRET_VALUE_RE.search(value) or any(raw and raw in value for raw in raw_sensitive_values):
            return _redacted_summary(value, "sensitive_value")
    return value


def _redacted_summary(value: Any, reason: str) -> dict[str, str]:
    return {
        "redaction": REDACTED_MARKER,
        "reason": reason,
        "value_type": type(value).__name__,
        "value_digest": stable_digest(value),
    }


def _redaction_checks(redaction_checks: Sequence[Mapping[str, Any]], redacted_observations: Any) -> list[dict[str, Any]]:
    checks = [redact_observations(dict(item)) for item in redaction_checks]
    checks.append(
        {
            "check": "observations_redacted",
            "status": "passed",
            "redacted_observation_digest": stable_digest(redacted_observations),
        }
    )
    return checks


def _schema_probe_status(status: str) -> str:
    if status == "passed":
        return "passed"
    if status == "failed":
        return "failed"
    return "skipped"


def _schema_trace_result(status: str) -> str:
    if status == "passed":
        return "passed"
    if status == "failed":
        return "failed"
    return "inconclusive"


def _normalize_status(status: str) -> str:
    normalized = str(status).strip().lower()
    if normalized == "skipped":
        return "not_applicable"
    if normalized not in TRACE_RESULT_STATUSES:
        raise VerificationTraceError(f"unknown trace status: {status}")
    return normalized


def _normalize_exercised_surface(surface: str) -> str:
    normalized = str(surface).strip().lower().replace("-", "_").replace(" ", "_").replace("/", "_")
    aliases = {
        "legacy_live_contextforge_read_only": "legacy_live_read_only",
        "legacy_live_read_only_contextforge": "legacy_live_read_only",
        "contextforge_development_docker": "contextforge_dev_docker",
        "pi_docker": "pi_client_docker",
        "opencode_docker": "opencode_client_docker",
        "source": "local_source",
        "local": "local_source",
        "run_evidence": "generated_run_evidence",
        "generated_evidence": "generated_run_evidence",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in EVIDENCE_SURFACES:
        raise VerificationTraceError(f"unknown exercised surface: {surface}")
    return normalized


def _default_surface_for_layer(layer: str) -> str:
    if layer in {"backend", "contextforge_gateway", "virtual_server"}:
        return "contextforge_dev_docker"
    if layer == "target_client":
        return "target_client"
    return "local_source"


def _trace_index(trace_artifacts: Mapping[str, Mapping[str, Any]] | Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    if isinstance(trace_artifacts, Mapping):
        index: dict[str, Mapping[str, Any]] = {}
        for ref, trace in trace_artifacts.items():
            annotated = copy.deepcopy(dict(trace))
            annotated.setdefault("x_artifact_ref", str(ref))
            index[str(ref)] = annotated
        return index
    index: dict[str, Mapping[str, Any]] = {}
    for trace in trace_artifacts:
        trace_copy = copy.deepcopy(dict(trace))
        ref = trace.get("x_artifact_ref") or f"{TRACE_REF_PREFIX}/{trace.get('trace_id')}.json"
        trace_copy.setdefault("x_artifact_ref", str(ref))
        index[str(ref)] = trace_copy
    return index


def _trace_content_digest(trace: Mapping[str, Any]) -> str:
    digest_body = copy.deepcopy(dict(trace))
    digest_body.pop("x_artifact_ref", None)
    return contracts.artifact_digest(digest_body)


def _trace_matches(
    trace: Mapping[str, Any],
    *,
    plan_id: str | None,
    step_id: str,
    service_binding: str,
    target_client: str | None,
) -> bool:
    if trace.get("plan_id") != plan_id:
        return False
    if trace.get("service_binding") != service_binding:
        return False
    if target_client is not None and trace.get("target_client") != target_client:
        return False
    return _trace_step_id(trace) == step_id


def _trace_has_layer(trace: Mapping[str, Any], layer: str) -> bool:
    if trace.get("x_verification_layer") == layer:
        return True
    return any(event.get("layer") == layer for event in trace.get("probe_events", []))


def _first_probe_layer(trace: Mapping[str, Any]) -> str | None:
    for event in trace.get("probe_events", []):
        if isinstance(event, Mapping) and event.get("layer"):
            return str(event["layer"])
    return None


def _trace_exercised_surface(trace: Mapping[str, Any]) -> str:
    surface = trace.get("exercised_surface") or trace.get("x_exercised_surface")
    if surface is None:
        return "local_source"
    return _normalize_exercised_surface(str(surface))


def _trace_step_id(trace: Mapping[str, Any]) -> str | None:
    if trace.get("x_step_id"):
        return str(trace["x_step_id"])
    for event in trace.get("probe_events", []):
        if isinstance(event, Mapping) and event.get("x_step_id"):
            return str(event["x_step_id"])
    return None


def _best_trace(traces: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
    priority = {"passed": 0, "failed": 1, "stale": 2, "pending": 3, "inconclusive": 4, "not_applicable": 5}
    return sorted(traces, key=lambda trace: priority.get(trace_result_status(trace), 9))[0]


def _layer_outcome(status: str, trace: Mapping[str, Any] | None, reason: str) -> dict[str, Any]:
    return {
        "status": status,
        "trace_id": trace.get("trace_id") if trace else None,
        "trace_ref": trace.get("x_artifact_ref") if trace else None,
        "failure_classification": trace.get("x_failure_classification") if trace else None,
        "reason": reason,
    }


def _failure_reason(trace: Mapping[str, Any]) -> str:
    classification = trace.get("x_failure_classification")
    if classification:
        return str(classification)
    return str(trace.get("result") or "inconclusive")


def _ref_key(item: str | Mapping[str, Any]) -> str:
    if isinstance(item, Mapping):
        return str(item.get("ref") or item.get("trace_ref") or item.get("x_artifact_ref") or "")
    return str(item)


def _summary_for(redacted_observations: Any) -> str:
    if isinstance(redacted_observations, Mapping) and redacted_observations.get("summary"):
        summary = str(redacted_observations["summary"])
    else:
        summary = f"redacted {type(redacted_observations).__name__} observation"
    return summary[:240]


def _require_identifier(name: str, value: str) -> None:
    if not isinstance(value, str) or not re.match(r"^[A-Za-z0-9][A-Za-z0-9_.:/@+-]*$", value):
        raise VerificationTraceError(f"{name} must be a schema-compatible identifier")


def _is_redacted_placeholder(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, bool | int | float):
        return True
    if isinstance(value, str):
        return value in {"", "redacted", REDACTED_MARKER, "***", "placeholder"} or value.startswith("redacted-")
    if isinstance(value, Mapping):
        return value.get("redaction") == REDACTED_MARKER or value.get("value_digest")
    if isinstance(value, list):
        return all(_is_redacted_placeholder(item) for item in value)
    return False


def _walk(value: Any, path: tuple[str, ...] = ()) -> Iterable[tuple[tuple[str, ...], Any]]:
    yield path, value
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield from _walk(child, (*path, str(key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, (*path, str(index)))


def _format_path(path: Iterable[str]) -> str:
    parts = list(path)
    return ".".join(parts) if parts else "<root>"
