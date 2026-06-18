#!/usr/bin/env python3
"""Pure redaction helpers for ContextForge control-plane diagnostics."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


SCHEMA_URI = "contextforge://control-plane/schemas/diagnostic-bundle/v1"
FAILURE_DIAGNOSTICS_SCHEMA_URI = "contextforge://control-plane/schemas/failure-diagnostics-bundle/v1"
REDACTED_MARKER = "<redacted>"
FAILURE_DIAGNOSTIC_WORKFLOWS = frozenset({"add", "repair", "verify", "activation"})

SENSITIVE_KEY_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private_key", re.compile(r"(^|_)private(_|$)|(^|_)private_key($|_)|(^|_)pem($|_)")),
    ("api_key", re.compile(r"(^|_)(api_key|apikey|access_key|secret_key)($|_)")),
    ("password", re.compile(r"(^|_)(password|passwd|passphrase|pwd)($|_)")),
    ("bearer_token", re.compile(r"(^|_)(authorization|auth_header|bearer)($|_)")),
    ("jwt", re.compile(r"(^|_)jwt($|_)")),
    ("token", re.compile(r"(^|_)(token|auth_token|session_token|refresh_token|token_file|token_path)($|_)")),
    ("encryption_secret", re.compile(r"(^|_)(auth_encryption_key|encryption_key|signing_key)($|_)")),
    ("secret", re.compile(r"(^|_)(secret|client_secret|shared_secret)($|_)")),
    ("credential", re.compile(r"(^|_)(credential|credentials|downstream_credential)($|_)")),
)
SAFE_METADATA_KEYS = frozenset(
    {
        "source_client_auth_strength",
        "token_source",
        "token_source_class",
        "token_source_constraints",
    }
)

SENSITIVE_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("bearer_token", re.compile(r"\bBearer\s+\S+")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}")),
    (
        "credential_assignment",
        re.compile(r"(?i)\b(?:api[_-]?key|auth[_-]?token|token|password|secret)\s*=\s*[^\s'\"<>]+"),
    ),
)

SAFE_PLACEHOLDER_RE = re.compile(
    r"^(|null|none|n/a|redacted|redacted-[A-Za-z0-9_.:-]+|\*\*\*|<redacted>|placeholder|"
    r"\$\{[A-Z0-9_]+\})$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RedactionEvent:
    """Metadata for one removed value."""

    path: tuple[str, ...]
    classification: str
    reason: str
    digest: str
    value_type: str

    def as_dict(self) -> dict[str, str]:
        return {
            "path": format_path(self.path),
            "classification": self.classification,
            "reason": self.reason,
            "value_digest": self.digest,
            "value_type": self.value_type,
        }


@dataclass(frozen=True)
class RedactionResult:
    """Redacted data plus summary events."""

    data: Any
    events: tuple[RedactionEvent, ...]

    def summary(self) -> dict[str, Any]:
        classifications: dict[str, int] = {}
        for event in self.events:
            classifications[event.classification] = classifications.get(event.classification, 0) + 1
        return {
            "redaction_status": "redacted",
            "redacted_value_count": len(self.events),
            "classifications": classifications,
            "events": [event.as_dict() for event in self.events],
        }


class RedactionLeakError(ValueError):
    """Raised when unredacted sensitive material remains in redacted output."""


def now_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def classify_sensitive_key(key: str) -> str | None:
    """Return the sensitive-data class implied by a field name, if any."""

    normalized = _normalize_key(key)
    if normalized in SAFE_METADATA_KEYS:
        return None
    for classification, pattern in SENSITIVE_KEY_PATTERNS:
        if pattern.search(normalized):
            return classification
    return None


def classify_sensitive_value(value: str) -> str | None:
    """Return the sensitive-data class implied by a string value, if any."""

    if is_safe_placeholder(value):
        return None
    for classification, pattern in SENSITIVE_VALUE_PATTERNS:
        if pattern.search(value):
            return classification
    return None


def is_safe_placeholder(value: Any) -> bool:
    return isinstance(value, str) and bool(SAFE_PLACEHOLDER_RE.match(value.strip()))


def stable_digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def redact_data(data: Any) -> Any:
    """Return a redacted deep copy of JSON-compatible data."""

    return redact_with_report(data).data


def redact_with_report(data: Any, *, raw_values: Sequence[str] = ()) -> RedactionResult:
    """Return redacted data and structured redaction events."""

    events: list[RedactionEvent] = []
    redacted = _redact_value(data, (), None, events, raw_values={value for value in raw_values if value})
    return RedactionResult(redacted, tuple(events))


def redact_env_summary(env: Mapping[str, Any], *, source_path: str | None = None) -> dict[str, Any]:
    """Summarize environment variables without returning raw values."""

    variables: dict[str, dict[str, Any]] = {}
    for key in sorted(env):
        value = env[key]
        variables[str(key)] = _redacted_metadata(
            value,
            classification=classify_sensitive_key(str(key)) or "env_value",
            reason="env_value",
            source_path=source_path,
        )
    return {
        "redaction_status": "redacted",
        "source_path": source_path,
        "variable_count": len(variables),
        "variables": variables,
    }


def build_diagnostic_bundle(
    *,
    source: str,
    catalog: Any | None = None,
    env: Mapping[str, Any] | None = None,
    tokens: Any | None = None,
    audit: Any | None = None,
    traces: Any | None = None,
    metadata: Mapping[str, Any] | None = None,
    generated_at: str | None = None,
    raw_values: Sequence[str] = (),
) -> dict[str, Any]:
    """Build a redacted diagnostic bundle from caller-supplied snapshots."""

    sections: dict[str, Any] = {}
    events: list[RedactionEvent] = []
    for name, value in (("catalog", catalog), ("tokens", tokens), ("audit", audit), ("traces", traces)):
        result = redact_with_report(value if value is not None else {})
        sections[name] = result.data
        events.extend(_prefix_events(name, result.events))

    sections["env"] = redact_env_summary(env or {})
    for key, summary in sections["env"]["variables"].items():
        events.append(
            RedactionEvent(
                path=("env", "variables", key),
                classification=summary["classification"],
                reason="env_value",
                digest=summary["value_digest"],
                value_type=summary["value_type"],
            )
        )

    metadata_result = redact_with_report(dict(metadata or {}))
    events.extend(_prefix_events("metadata", metadata_result.events))

    bundle = {
        "schema_uri": SCHEMA_URI,
        "generated_at": generated_at or now_timestamp(),
        "source": source,
        "redaction_status": "redacted",
        "metadata": metadata_result.data,
        "sections": sections,
        "redaction": RedactionResult(None, tuple(events)).summary(),
    }
    assert_no_sensitive_raw_values(bundle, raw_values=raw_values)
    return bundle


def build_failure_diagnostics_bundle(
    *,
    workflow: str,
    service_slug: str,
    canonical_service_identity: str,
    registry_id: str | None = None,
    virtual_server_id: str | None = None,
    transport_path: str,
    bridge_or_transceiver_reason: str,
    client_visibility_target: str,
    last_probe: Mapping[str, Any],
    failing_call_shape: Mapping[str, Any],
    next_safe_diagnostic_action: str,
    failure_summary: Mapping[str, Any] | None = None,
    generated_at: str | None = None,
    raw_values: Sequence[str] = (),
) -> dict[str, Any]:
    """Build a compact redacted failure packet for add/repair/verify/activation flows."""

    normalized_workflow = _failure_workflow(workflow)
    required_strings = {
        "service_slug": service_slug,
        "canonical_service_identity": canonical_service_identity,
        "transport_path": transport_path,
        "bridge_or_transceiver_reason": bridge_or_transceiver_reason,
        "client_visibility_target": client_visibility_target,
        "next_safe_diagnostic_action": next_safe_diagnostic_action,
    }
    missing = [name for name, value in required_strings.items() if not str(value or "").strip()]
    if missing:
        raise ValueError(f"missing failure diagnostics field(s): {', '.join(missing)}")
    if not isinstance(last_probe, Mapping):
        raise ValueError("last_probe must be a mapping")
    if not isinstance(failing_call_shape, Mapping):
        raise ValueError("failing_call_shape must be a mapping")

    sections: dict[str, Any] = {
        "service": {
            "service_slug": str(service_slug),
            "canonical_service_identity": str(canonical_service_identity),
            "registry_id": _optional_text(registry_id),
            "virtual_server_id": _optional_text(virtual_server_id),
        },
        "transport": {
            "path": str(transport_path),
            "bridge_or_transceiver_reason": str(bridge_or_transceiver_reason),
        },
        "client_visibility": {
            "target": str(client_visibility_target),
        },
    }
    events: list[RedactionEvent] = []
    for name, value in (
        ("last_probe", last_probe),
        ("failing_call_shape", failing_call_shape),
        ("failure_summary", failure_summary or {}),
    ):
        result = redact_with_report(dict(value), raw_values=raw_values)
        sections[name] = result.data
        events.extend(_prefix_events(name, result.events))

    bundle = {
        "schema_uri": FAILURE_DIAGNOSTICS_SCHEMA_URI,
        "generated_at": generated_at or now_timestamp(),
        "workflow": normalized_workflow,
        "redaction_status": "redacted",
        "service": sections["service"],
        "transport": sections["transport"],
        "client_visibility": sections["client_visibility"],
        "last_probe": sections["last_probe"],
        "failing_call_shape": sections["failing_call_shape"],
        "failure_summary": sections["failure_summary"],
        "next_safe_diagnostic_action": str(next_safe_diagnostic_action),
        "redaction": RedactionResult(None, tuple(events)).summary(),
    }
    assert_no_sensitive_raw_values(bundle, raw_values=raw_values)
    return bundle


def assert_no_sensitive_raw_values(data: Any, *, raw_values: Iterable[str] = ()) -> None:
    """Reject raw sensitive values in a JSON-compatible redacted object."""

    blocked_values = {value for value in raw_values if value}
    for path, value in _walk(data):
        if not isinstance(value, str):
            continue
        if classify_sensitive_value(value) is not None:
            raise RedactionLeakError(f"secret-like value remains at {format_path(path)}")
        for raw in blocked_values:
            if raw in value:
                raise RedactionLeakError(f"raw sensitive value remains at {format_path(path)}")

    for path, value in _walk(data):
        key = path[-1] if path else ""
        if classify_sensitive_key(key) and _unsafe_secret_value(value):
            raise RedactionLeakError(f"secret-bearing field is not redacted at {format_path(path)}")


def format_path(path: Iterable[str]) -> str:
    parts = list(path)
    return ".".join(parts) if parts else "<root>"


def _redact_value(
    value: Any,
    path: tuple[str, ...],
    key: str | None,
    events: list[RedactionEvent],
    *,
    raw_values: set[str],
) -> Any:
    key_classification = classify_sensitive_key(key or "") if key is not None else None
    if key_classification and not _already_redacted(value):
        events.append(
            RedactionEvent(
                path=path,
                classification=key_classification,
                reason="sensitive_key",
                digest=stable_digest(value),
                value_type=type(value).__name__,
            )
        )
        return _redacted_metadata(value, classification=key_classification, reason="sensitive_key")

    if isinstance(value, Mapping):
        return {
            str(child_key): _redact_value(
                child,
                (*path, str(child_key)),
                str(child_key),
                events,
                raw_values=raw_values,
            )
            for child_key, child in value.items()
        }
    if isinstance(value, list):
        return [
            _redact_value(child, (*path, str(index)), None, events, raw_values=raw_values)
            for index, child in enumerate(value)
        ]
    if isinstance(value, str):
        value_classification = classify_sensitive_value(value)
        if value_classification:
            events.append(
                RedactionEvent(
                    path=path,
                    classification=value_classification,
                    reason="sensitive_value",
                    digest=stable_digest(value),
                    value_type="str",
                )
            )
            return _redacted_metadata(value, classification=value_classification, reason="sensitive_value")
        if any(raw in value for raw in raw_values):
            events.append(
                RedactionEvent(
                    path=path,
                    classification="explicit_raw_value",
                    reason="caller_supplied_raw_value",
                    digest=stable_digest(value),
                    value_type="str",
                )
            )
            return _redacted_metadata(value, classification="explicit_raw_value", reason="caller_supplied_raw_value")
    return value


def _redacted_metadata(
    value: Any,
    *,
    classification: str,
    reason: str,
    source_path: str | None = None,
) -> dict[str, Any]:
    metadata = {
        "redacted": True,
        "classification": classification,
        "reason": reason,
        "value_type": type(value).__name__,
        "value_digest": stable_digest(value),
        "shape": _shape(value),
    }
    if source_path is not None:
        metadata["source_path"] = source_path
    if value is None:
        metadata["present"] = False
    else:
        metadata["present"] = True
    if isinstance(value, str):
        metadata["value_length"] = len(value)
    if isinstance(value, Mapping):
        metadata["key_count"] = len(value)
    if isinstance(value, list):
        metadata["item_count"] = len(value)
    return metadata


def _shape(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {"type": "object", "keys": sorted(str(key) for key in value.keys())}
    if isinstance(value, list):
        return {"type": "array", "item_count": len(value)}
    if isinstance(value, str):
        return {"type": "string", "length": len(value)}
    if value is None:
        return {"type": "null"}
    return {"type": type(value).__name__}


def _walk(value: Any, path: tuple[str, ...] = ()) -> Iterable[tuple[tuple[str, ...], Any]]:
    yield path, value
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield from _walk(child, (*path, str(key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, (*path, str(index)))


def _normalize_key(key: str) -> str:
    normalized = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", key)
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", normalized)
    return normalized.strip("_").lower()


def _already_redacted(value: Any) -> bool:
    if is_safe_placeholder(value):
        return True
    if isinstance(value, Mapping):
        return value.get("redacted") is True or value.get("redaction_status") in {"redacted", "passed"}
    return False


def _unsafe_secret_value(value: Any) -> bool:
    if value is None or isinstance(value, bool | int | float):
        return False
    if is_safe_placeholder(value):
        return False
    if isinstance(value, Mapping):
        return not (value.get("redacted") is True or value.get("redaction_status") in {"redacted", "passed"})
    return True


def _prefix_events(prefix: str, events: Iterable[RedactionEvent]) -> tuple[RedactionEvent, ...]:
    return tuple(
        RedactionEvent(
            path=(prefix, *event.path),
            classification=event.classification,
            reason=event.reason,
            digest=event.digest,
            value_type=event.value_type,
        )
        for event in events
    )


def _failure_workflow(workflow: str) -> str:
    normalized = str(workflow).strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "service_add": "add",
        "service_repair": "repair",
        "service_verify": "verify",
        "validation": "verify",
        "project_activation": "activation",
        "activate": "activation",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in FAILURE_DIAGNOSTIC_WORKFLOWS:
        raise ValueError(f"unknown failure diagnostics workflow: {workflow}")
    return normalized


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
