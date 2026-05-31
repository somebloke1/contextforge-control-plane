#!/usr/bin/env python3
"""Pure Codex trust-broker helpers for control-plane workflows.

These helpers inspect caller-supplied evidence and build/verify explicit trust
approval records. They never mutate Codex trust stores or user-global config.
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import control_plane_authorization as authorization
import control_plane_contracts as contracts
import control_plane_project_state as project_state
import control_plane_redaction as redaction


BROKER_VERSION = 1
TRUST_APPROVAL_RECORD_SCHEMA_URI = "contextforge://control-plane/codex-trust-approval-record/v1"
TRUST_APPROVAL_REQUEST_SCHEMA_URI = "contextforge://control-plane/codex-trust-approval-request/v1"
TRUST_CONSENT_CLASS = "user_global_client_trust"
TRUST_PERSISTENT_TARGET = "trust-store"
DEFAULT_TRUST_SURFACE = "codex_project_root_trust"
KNOWN_TRUST_STATES = {
    "unknown",
    "untrusted",
    "trusted_but_not_loaded",
    "trusted_requires_restart",
    "trusted",
    "declined",
    "not_required",
}
PASSING_TRUST_STATES = {"trusted", "not_required"}
OPEN_ITEM_BY_STATE = {
    "unknown": ("trust_broker", "blocking", "Codex trust state is unknown."),
    "untrusted": ("trust", "blocking", "Codex project trust is not granted."),
    "declined": ("trust", "blocking", "Codex project trust was declined."),
    "trusted_requires_restart": ("restart", "blocking", "Codex trust requires a client restart before it is active."),
    "trusted_but_not_loaded": ("restart", "warning", "Codex trust is approved but not yet loaded by the client."),
}
FORBIDDEN_BUNDLED_CLASSES = {"project_init", "service_provision", "project_state_write", "project_local_config_write"}


class TrustBrokerError(ValueError):
    """Raised when trust-broker inputs cannot be represented safely."""


def now_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stable_digest(value: Any) -> str:
    encoded = json.dumps(_json_compatible_copy(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def inspect_codex_trust_state(
    evidence: Mapping[str, Any] | None,
    *,
    project_root: str | Path,
    client: str = "codex",
    trust_surface: str = DEFAULT_TRUST_SURFACE,
    observed_at: str | None = None,
    raw_sensitive_values: Iterable[str] = (),
) -> dict[str, Any]:
    """Return a redacted, non-mutating trust report from supplied evidence."""

    root = _canonical_root(project_root)
    safe_evidence = _redacted(evidence or {}, raw_sensitive_values=raw_sensitive_values)
    state = _normalize_trust_state(safe_evidence)
    evidence_root = _optional_root(safe_evidence.get("root") or safe_evidence.get("project_root"))
    evidence_client = str(safe_evidence.get("client") or client)
    evidence_surface = str(safe_evidence.get("trust_surface") or trust_surface)
    reasons: list[str] = []
    if evidence_client != client:
        state = "unknown"
        reasons.append("evidence client does not match requested client")
    if evidence_surface != trust_surface:
        state = "unknown"
        reasons.append("evidence trust surface does not match requested surface")
    if evidence_root and evidence_root != root:
        state = "unknown"
        reasons.append("evidence project root does not match requested root")
    if bool(safe_evidence.get("user_global_trust_mutated")) or bool(safe_evidence.get("trust_grant_attempted")):
        reasons.append("evidence indicates an attempted user-global trust mutation")

    report = {
        "schema_version": BROKER_VERSION,
        "broker": "codex_trust_broker",
        "client": client,
        "project_root": root,
        "trust_surface": trust_surface,
        "state": state,
        "trusted": state in PASSING_TRUST_STATES,
        "observed_at": observed_at or now_timestamp(),
        "last_probe": safe_evidence.get("last_probe") or safe_evidence.get("probe_id"),
        "approval_record": safe_evidence.get("approval_record"),
        "verification_trace_ref": safe_evidence.get("verification_trace_ref"),
        "redacted_evidence_summary": _evidence_summary(safe_evidence),
        "open_items": [],
        "gaps": [],
        "non_actions": [
            "no user-global trust mutation",
            "no user-global config write",
            "no service/project-init approval reused as trust approval",
        ],
        "mutation_allowed": False,
        "redaction_status": "redacted",
    }
    gaps = list(reasons)
    if state not in PASSING_TRUST_STATES:
        gaps.append(f"trust state is {state}")
    report["gaps"] = list(dict.fromkeys(gaps))
    report["open_items"] = _open_items_for_state(
        state,
        client=client,
        project_root=root,
        trust_surface=trust_surface,
        created_at=str(report["observed_at"]),
        extra_reasons=reasons,
    )
    _assert_redacted(report, raw_sensitive_values=raw_sensitive_values)
    return report


def build_trust_approval_request(
    *,
    project_root: str | Path,
    client: str = "codex",
    trust_surface: str = DEFAULT_TRUST_SURFACE,
    actor: str,
    requested_at: str | None = None,
    approval_evidence: Any | None = None,
    consent_receipt_ref: str | Mapping[str, Any] | None = None,
    reason: str = "Codex requires explicit project-root trust before loading project-local control-plane config.",
    raw_sensitive_values: Iterable[str] = (),
) -> dict[str, Any]:
    """Build a redacted request object for a separate Codex trust approval."""

    root = _canonical_root(project_root)
    request = {
        "schema_uri": TRUST_APPROVAL_REQUEST_SCHEMA_URI,
        "broker_version": BROKER_VERSION,
        "request_id": "",
        "project_root": root,
        "client": str(client),
        "trust_surface": str(trust_surface),
        "actor": str(actor),
        "requested_at": requested_at or now_timestamp(),
        "consent_class": TRUST_CONSENT_CLASS,
        "persistent_target": TRUST_PERSISTENT_TARGET,
        "approval_evidence": _redacted(approval_evidence, raw_sensitive_values=raw_sensitive_values),
        "consent_receipt_ref": _json_compatible_copy(consent_receipt_ref),
        "reason": reason,
        "required_boundary": "separate_explicit_user_global_client_trust_approval",
        "forbidden_bundled_consent_classes": sorted(FORBIDDEN_BUNDLED_CLASSES),
        "non_actions": ["does not grant trust", "does not edit Codex config", "does not run Codex trust commands"],
        "redaction_status": "redacted",
    }
    request["request_id"] = _id("trust-request", request)
    _assert_redacted(request, raw_sensitive_values=raw_sensitive_values)
    return request


def create_trust_consent_receipt(
    *,
    plan: Mapping[str, Any],
    project_root: str | Path,
    client: str = "codex",
    trust_surface: str = DEFAULT_TRUST_SURFACE,
    actor: str,
    source_client_auth_strength: str = "wrapper_bound",
    approval_event_ref: str,
    approval_evidence: Any,
    expires_at: str,
    approved_at: str | None = None,
    approval_nonce: str | None = None,
    approval_channel: str = "interactive_user",
    replay_policy: str = "same_plan_resume",
    raw_sensitive_values: Iterable[str] = (),
) -> dict[str, Any]:
    """Create a scoped consent receipt for the trust approval boundary."""

    safe_evidence = _approval_evidence_text(approval_evidence, raw_sensitive_values=raw_sensitive_values)
    receipt = authorization.create_consent_receipt(
        plan=plan,
        consent_class=TRUST_CONSENT_CLASS,
        actor=actor,
        source_client=client,
        source_client_auth_strength=source_client_auth_strength,
        approval_event_ref=approval_event_ref,
        approval_evidence=safe_evidence,
        expires_at=expires_at,
        approved_at=approved_at,
        approval_nonce=approval_nonce,
        approval_channel=approval_channel,
        replay_policy=replay_policy,
        scope={
            "project_root": _canonical_root(project_root),
            "client": client,
            "target_clients": [client],
            "persistent_target": TRUST_PERSISTENT_TARGET,
            "operation_class": TRUST_CONSENT_CLASS,
        },
    )
    _assert_redacted(receipt, raw_sensitive_values=raw_sensitive_values)
    return receipt


def build_trust_approval_record(
    *,
    project_root: str | Path,
    client: str = "codex",
    trust_surface: str = DEFAULT_TRUST_SURFACE,
    actor: str,
    approval_evidence: Any,
    approved_at: str | None = None,
    expires_at: str | None = None,
    consent_receipt: Mapping[str, Any] | None = None,
    consent_receipt_ref: str | Mapping[str, Any] | None = None,
    approval_event_ref: str | None = None,
    source_client_auth_strength: str = "wrapper_bound",
    approval_workflow: str = "codex_trust_broker",
    bundled_consent_classes: Iterable[str] = (),
    raw_sensitive_values: Iterable[str] = (),
) -> dict[str, Any]:
    """Build an immutable broker approval record without granting trust."""

    root = _canonical_root(project_root)
    safe_evidence = _redacted(approval_evidence, raw_sensitive_values=raw_sensitive_values)
    record = {
        "schema_uri": TRUST_APPROVAL_RECORD_SCHEMA_URI,
        "broker_version": BROKER_VERSION,
        "record_id": "",
        "project_root": root,
        "client": str(client),
        "trust_surface": str(trust_surface),
        "actor": str(actor),
        "approval_evidence": safe_evidence,
        "approval_event_ref": approval_event_ref,
        "approved_at": approved_at or now_timestamp(),
        "expires_at": expires_at,
        "consent_class": TRUST_CONSENT_CLASS,
        "persistent_target": TRUST_PERSISTENT_TARGET,
        "source_client_auth_strength": source_client_auth_strength,
        "approval_workflow": approval_workflow,
        "consent_receipt_ref": _json_compatible_copy(consent_receipt_ref),
        "consent_receipt": _json_compatible_copy(consent_receipt),
        "bundled_consent_classes": sorted(str(item) for item in bundled_consent_classes),
        "approval_boundary": "user_global_client_trust",
        "non_actions": ["does not grant trust", "does not edit user-global Codex trust", "does not edit Codex config"],
        "redaction_status": "redacted",
    }
    record["record_id"] = _id("trust-approval", record)
    _assert_redacted(record, raw_sensitive_values=raw_sensitive_values)
    return record


def verify_trust_approval_record(
    record: Mapping[str, Any] | None,
    *,
    project_root: str | Path,
    client: str = "codex",
    trust_surface: str = DEFAULT_TRUST_SURFACE,
    actor: str | None = None,
    now: str | None = None,
    max_age_seconds: int | None = None,
    plan: Mapping[str, Any] | None = None,
    replay_intent: str = "initial_apply",
) -> dict[str, Any]:
    """Fail-closed verification for one broker approval record."""

    if not record:
        return _decision("block", ["missing trust approval record"])

    reasons: list[str] = []
    root = _canonical_root(project_root)
    if record.get("schema_uri") != TRUST_APPROVAL_RECORD_SCHEMA_URI:
        reasons.append("record schema uri does not match trust approval record")
    if record.get("record_id") != _id("trust-approval", record):
        reasons.append("record integrity check failed")
    if _optional_root(record.get("project_root")) != root:
        reasons.append("record project root scope does not match")
    if record.get("client") != client:
        reasons.append("record client scope does not match")
    if record.get("trust_surface") != trust_surface:
        reasons.append("record trust surface scope does not match")
    if actor is not None and record.get("actor") != actor:
        reasons.append("record actor does not match")
    if record.get("consent_class") != TRUST_CONSENT_CLASS:
        reasons.append("record consent class is not user-global client trust")
    if record.get("persistent_target") != TRUST_PERSISTENT_TARGET:
        reasons.append("record persistent target is not trust-store")
    if record.get("approval_workflow") in {"project_init", "service_provision"}:
        reasons.append("trust approval is conflated with service/project-init approval")
    bundled = {str(item) for item in record.get("bundled_consent_classes", []) or []}
    if bundled & FORBIDDEN_BUNDLED_CLASSES:
        reasons.append("trust approval bundles service/project-init consent")
    if not record.get("approval_evidence"):
        reasons.append("record approval evidence is missing")
    reasons.extend(_timestamp_reasons(record, now=now or now_timestamp(), max_age_seconds=max_age_seconds))
    reasons.extend(_receipt_reasons(record, root=root, client=client, trust_surface=trust_surface, actor=actor, plan=plan, replay_intent=replay_intent, now=now))
    return _decision("allow" if not reasons else "block", reasons, record_id=record.get("record_id"))


def verify_trust_report(
    report: Mapping[str, Any],
    *,
    approval_record: Mapping[str, Any] | None = None,
    project_root: str | Path,
    client: str = "codex",
    trust_surface: str = DEFAULT_TRUST_SURFACE,
    now: str | None = None,
) -> dict[str, Any]:
    """Verify report evidence and optional approval record without mutating trust."""

    reasons: list[str] = []
    if report.get("mutation_allowed") is not False:
        reasons.append("trust report must be non-mutating")
    if any("trust mutation" in str(gap) for gap in report.get("gaps", []) or []):
        reasons.append("trust report includes attempted user-global trust mutation evidence")
    if report.get("state") not in PASSING_TRUST_STATES:
        reasons.append(f"trust report state is {report.get('state')}")
    if report.get("client") != client:
        reasons.append("trust report client scope does not match")
    if _optional_root(report.get("project_root")) != _canonical_root(project_root):
        reasons.append("trust report project root scope does not match")
    if report.get("trust_surface") != trust_surface:
        reasons.append("trust report surface scope does not match")
    if approval_record is not None:
        record_decision = verify_trust_approval_record(
            approval_record,
            project_root=project_root,
            client=client,
            trust_surface=trust_surface,
            now=now,
        )
        if record_decision["decision"] != "allow":
            reasons.extend(f"approval record: {reason}" for reason in record_decision["reasons"])
    return _decision("allow" if not reasons else "block", reasons, state=report.get("state"))


def _normalize_trust_state(evidence: Mapping[str, Any]) -> str:
    raw_state = evidence.get("state") or evidence.get("trust_state")
    if isinstance(raw_state, str) and raw_state in KNOWN_TRUST_STATES:
        return raw_state
    if evidence.get("declined") is True:
        return "declined"
    if evidence.get("not_required") is True:
        return "not_required"
    if evidence.get("trusted") is True and evidence.get("requires_restart") is True:
        return "trusted_requires_restart"
    if evidence.get("trusted") is True and evidence.get("loaded") is False:
        return "trusted_but_not_loaded"
    if evidence.get("trusted") is True:
        return "trusted"
    if evidence.get("trusted") is False:
        return "untrusted"
    return "unknown"


def _open_items_for_state(
    state: str,
    *,
    client: str,
    project_root: str,
    trust_surface: str,
    created_at: str,
    extra_reasons: Iterable[str] = (),
) -> list[dict[str, Any]]:
    if state in PASSING_TRUST_STATES:
        return []
    item_type, severity, summary = OPEN_ITEM_BY_STATE.get(state, ("trust_broker", "blocking", "Codex trust state blocks verification."))
    return [
        {
            "id": f"{item_type}:{client}:{trust_surface}",
            "type": item_type,
            "severity": severity,
            "blocks_initialized": severity == "blocking",
            "resource": client,
            "created_at": created_at,
            "summary": summary,
            "detail": {
                "client": client,
                "project_root": project_root,
                "trust_surface": trust_surface,
                "state": state,
                "reasons": list(dict.fromkeys(extra_reasons)),
                "required_consent_class": TRUST_CONSENT_CLASS,
                "proposed_repair": "fresh_approval_required" if state in {"unknown", "untrusted", "declined"} else "manual_recovery",
            },
        }
    ]


def _receipt_reasons(
    record: Mapping[str, Any],
    *,
    root: str,
    client: str,
    trust_surface: str,
    actor: str | None,
    plan: Mapping[str, Any] | None,
    replay_intent: str,
    now: str | None,
) -> list[str]:
    receipt = record.get("consent_receipt")
    receipt_ref = record.get("consent_receipt_ref")
    reasons: list[str] = []
    if receipt is None:
        if not receipt_ref:
            reasons.append("record has neither consent receipt nor receipt ref")
        return reasons
    if not isinstance(receipt, Mapping):
        return ["embedded consent receipt is not an object"]
    if receipt.get("consent_class") != TRUST_CONSENT_CLASS:
        reasons.append("embedded receipt consent class is not user-global client trust")
    check = authorization.validate_consent_receipt(
        receipt,
        plan=plan,
        consent_class=TRUST_CONSENT_CLASS,
        actor=actor,
        source_client=client,
        source_client_auth_strength="wrapper_bound",
        project_root=root,
        target_clients=[client],
        persistent_target=TRUST_PERSISTENT_TARGET,
        operation_class=TRUST_CONSENT_CLASS,
        replay_intent=replay_intent,
        now=now,
    )
    reasons.extend(f"embedded receipt: {reason}" for reason in check["reasons"])
    return reasons


def _timestamp_reasons(record: Mapping[str, Any], *, now: str, max_age_seconds: int | None) -> list[str]:
    reasons: list[str] = []
    try:
        approved_at = _parse_timestamp(str(record.get("approved_at") or ""))
        current = _parse_timestamp(now)
    except ValueError:
        return ["record approval timestamp is invalid"]
    if approved_at > current:
        reasons.append("record approval timestamp is in the future")
    expires_at = record.get("expires_at")
    if expires_at:
        try:
            if _parse_timestamp(str(expires_at)) <= current:
                reasons.append("record approval has expired")
        except ValueError:
            reasons.append("record expiry timestamp is invalid")
    if max_age_seconds is not None and (current - approved_at).total_seconds() > max_age_seconds:
        reasons.append("record approval is stale")
    return reasons


def _decision(decision: str, reasons: Iterable[str], **metadata: Any) -> dict[str, Any]:
    result = {"decision": decision, "allowed": decision == "allow", "reasons": list(dict.fromkeys(reasons))}
    result.update(metadata)
    return result


def _approval_evidence_text(evidence: Any, *, raw_sensitive_values: Iterable[str]) -> str:
    safe = _redacted(evidence, raw_sensitive_values=raw_sensitive_values)
    if isinstance(safe, str):
        return safe
    return json.dumps(safe, sort_keys=True, separators=(",", ":"))


def _evidence_summary(evidence: Mapping[str, Any]) -> dict[str, Any]:
    allowed_keys = {
        "state",
        "trust_state",
        "trusted",
        "declined",
        "not_required",
        "requires_restart",
        "loaded",
        "root",
        "project_root",
        "client",
        "trust_surface",
        "last_probe",
        "probe_id",
        "approval_record",
        "verification_trace_ref",
        "user_global_trust_mutated",
        "trust_grant_attempted",
    }
    return {key: _json_compatible_copy(value) for key, value in evidence.items() if key in allowed_keys}


def _redacted(value: Any, *, raw_sensitive_values: Iterable[str]) -> Any:
    safe = redaction.redact_data(_json_compatible_copy(value))
    _assert_redacted(safe, raw_sensitive_values=raw_sensitive_values)
    return safe


def _assert_redacted(value: Any, *, raw_sensitive_values: Iterable[str]) -> None:
    redaction.assert_no_sensitive_raw_values(value, raw_values=raw_sensitive_values)
    contracts.validate_redacted(value, require_status=isinstance(value, Mapping) and "redaction_status" in value)


def _id(prefix: str, data: Mapping[str, Any]) -> str:
    body = {key: _json_compatible_copy(value) for key, value in data.items() if key not in {"record_id", "request_id"}}
    return f"{prefix}-{stable_digest(body).removeprefix('sha256:')[:16]}"


def _json_compatible_copy(value: Any) -> Any:
    return json.loads(json.dumps(value, sort_keys=True, default=str))


def _canonical_root(root: str | Path) -> str:
    return str(project_state.canonical_root(root))


def _optional_root(root: Any) -> str | None:
    if root in {None, ""}:
        return None
    return _canonical_root(str(root))


def _parse_timestamp(value: str) -> datetime:
    if not value:
        raise ValueError("timestamp is empty")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def clone(data: Mapping[str, Any]) -> dict[str, Any]:
    """Return a deep copy for tests and callers."""

    return copy.deepcopy(dict(data))
