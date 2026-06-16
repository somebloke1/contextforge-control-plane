#!/usr/bin/env python3
"""Pure authorization helpers for ContextForge control-plane apply workflows."""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import control_plane_contracts as contracts
import control_plane_project_state as project_state


CONSENT_RECEIPT_SCHEMA_URI = "contextforge://control-plane/schemas/consent-receipt/v1"
AUTHORIZATION_HELPER_VERSION = 1

AUTH_STRENGTH_ORDER = {
    "asserted": 0,
    "shared_token": 1,
    "wrapper_bound": 2,
    "per_client_token": 3,
}
DEFAULT_MIN_AUTH_STRENGTH = {
    "read_only_inspection": "asserted",
    "project_state_write": "shared_token",
    "project_local_config_write": "shared_token",
    "service_provision": "shared_token",
    "secret_placeholder_change": "shared_token",
    "catalog_promotion": "wrapper_bound",
    "user_global_client_trust": "wrapper_bound",
    "user_global_config_write": "wrapper_bound",
    "secret_value_write": "per_client_token",
    "token_material_change": "per_client_token",
    "network_exposure_change": "per_client_token",
}
PROJECT_INIT_CONSENT_CLASSES = frozenset(
    {
        "read_only_inspection",
        "project_state_write",
        "project_local_config_write",
        "service_provision",
        "secret_placeholder_change",
    }
)
FORBIDDEN_GENERIC_PROJECT_INIT_CLASSES = frozenset(
    {
        "catalog_promotion",
        "user_global_client_trust",
        "user_global_config_write",
        "secret_value_write",
        "token_material_change",
        "network_exposure_change",
    }
)
REPLAY_COMPATIBILITY = {
    "single_use": frozenset({"initial_apply"}),
    "same_plan_resume": frozenset({"initial_apply", "resume"}),
    "repair_only": frozenset({"repair"}),
    "fresh_approval_required": frozenset({"initial_apply"}),
}
SERVICE_BOUND_OPERATION_CLASSES = frozenset({"service_provision"})
PERSISTENT_TARGET_BY_CLASS = {
    "project_state_write": "file",
    "project_local_config_write": "file",
    "service_provision": "systemd",
    "catalog_promotion": "contextforge",
    "user_global_client_trust": "trust-store",
    "user_global_config_write": "file",
    "secret_placeholder_change": "file",
    "secret_value_write": "token-store",
    "token_material_change": "token-store",
    "network_exposure_change": "network",
}
MUTATING_CLASSES = frozenset(DEFAULT_MIN_AUTH_STRENGTH) - {"read_only_inspection"}
SECRET_OUTPUT_KEYS = frozenset({"secret", "token", "password", "api_key", "apikey", "bearer", "jwt", "credential"})


def plan_digest(plan: Mapping[str, Any]) -> str:
    """Return a deterministic digest for a JSON-compatible plan object."""

    return stable_digest(plan)


def stable_digest(value: Any) -> str:
    encoded = json.dumps(_json_compatible_copy(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def create_consent_receipt(
    *,
    plan: Mapping[str, Any],
    consent_class: str,
    actor: str,
    source_client: str,
    source_client_auth_strength: str,
    approval_event_ref: str,
    approval_evidence: str,
    expires_at: str,
    scope: Mapping[str, Any] | None = None,
    plan_presented_digest: str | None = None,
    approval_nonce: str | None = None,
    approval_channel: str = "interactive_user",
    issued_by: str = "approve_plan",
    approved_at: str | None = None,
    replay_policy: str = "same_plan_resume",
) -> dict[str, Any]:
    """Create a schema-valid immutable consent receipt object."""

    digest = plan_digest(plan)
    root = _canonical_root(_plan_project_root(plan, scope))
    receipt_scope = _receipt_scope(scope or {}, root=root, consent_class=consent_class)
    receipt = {
        "receipt_id": "",
        "schema_uri": CONSENT_RECEIPT_SCHEMA_URI,
        "plan_id": str(plan.get("plan_id") or "plan"),
        "plan_digest": digest,
        "plan_presented_digest": plan_presented_digest or digest,
        "consent_class": consent_class,
        "scope": receipt_scope,
        "actor": actor,
        "source_client": source_client,
        "source_client_auth_strength": source_client_auth_strength,
        "approval_nonce": approval_nonce,
        "approval_channel": approval_channel,
        "approval_event_ref": approval_event_ref,
        "issued_by": issued_by,
        "approved_at": approved_at or now_timestamp(),
        "approval_evidence": approval_evidence,
        "expires_at": expires_at,
        "replay_policy": replay_policy,
        "redaction_status": "redacted",
    }
    receipt["receipt_id"] = _receipt_id(receipt)
    contracts.validate_artifact("consent_receipt", receipt)
    return receipt


def validate_consent_receipt(
    receipt: Mapping[str, Any],
    *,
    plan: Mapping[str, Any] | None = None,
    consent_class: str | None = None,
    actor: str | None = None,
    source_client: str | None = None,
    source_client_auth_strength: str | None = None,
    project_root: str | Path | None = None,
    service_binding: str | None = None,
    target_clients: Iterable[str] | None = None,
    persistent_target: str | None = None,
    operation_class: str | None = None,
    replay_intent: str = "initial_apply",
    now: str | None = None,
) -> dict[str, Any]:
    """Validate receipt schema, expiry, scope, class, actor, and replay fit."""

    reasons: list[str] = []
    try:
        contracts.validate_artifact("consent_receipt", receipt)
    except contracts.ContractValidationError as exc:
        return _decision("block", [f"invalid consent receipt: {exc}"])

    if plan is not None and receipt.get("plan_digest") != plan_digest(plan):
        reasons.append("receipt plan digest does not match plan")
    if plan is not None and str(receipt.get("plan_id")) != str(plan.get("plan_id")):
        reasons.append("receipt plan id does not match plan")
    if receipt.get("receipt_id") != _receipt_id(receipt):
        reasons.append("receipt integrity check failed")
    expected_class = consent_class or operation_class
    if expected_class and receipt.get("consent_class") != expected_class:
        reasons.append("receipt consent class does not match operation")
    if actor and receipt.get("actor") != actor:
        reasons.append("receipt actor does not match caller")
    if source_client and receipt.get("source_client") != source_client:
        reasons.append("receipt source client does not match caller")
    if source_client_auth_strength and not _auth_strength_at_least(str(receipt.get("source_client_auth_strength")), source_client_auth_strength):
        reasons.append("receipt source-client auth strength is insufficient")
    if _is_expired(str(receipt.get("expires_at")), now or now_timestamp()):
        reasons.append("receipt has expired")
    reasons.extend(_scope_mismatch_reasons(receipt, project_root, service_binding, target_clients, persistent_target, expected_class))
    if not _replay_allowed(str(receipt.get("replay_policy")), replay_intent):
        reasons.append("receipt replay policy is incompatible with requested apply mode")
    return _decision("block" if reasons else "allow", reasons)


def authorize_operation(
    *,
    plan: Mapping[str, Any],
    operation_class: str,
    actor: str,
    workflow_identity: str,
    source_client: str,
    source_client_auth_strength: str,
    target_clients: Iterable[str],
    project_root: str | Path,
    current_state: Mapping[str, Any] | None,
    current_target_client_digests: Mapping[str, Any] | None = None,
    current_trust_digest: str | None = None,
    current_catalog_revision_or_etag: str | None = None,
    current_descriptor_digests: Mapping[str, str] | None = None,
    token_source: str | None = None,
    expected_token_source: str | None = None,
    service_binding: str | None = None,
    persistent_target: str | None = None,
    receipts: Iterable[Mapping[str, Any]] = (),
    replay_intent: str = "initial_apply",
    approval_workflow: str = "project_init",
    allowed_callers: Iterable[str] | None = None,
    allowed_workflows: Iterable[str] | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Authorize an operation immediately before a mutating apply step."""

    reasons: list[str] = []
    root = _canonical_root(project_root)
    target_tuple = tuple(sorted(str(client) for client in target_clients))
    persistent = persistent_target or PERSISTENT_TARGET_BY_CLASS.get(operation_class) or "file"
    if operation_class not in DEFAULT_MIN_AUTH_STRENGTH:
        reasons.append(f"unknown operation class: {operation_class}")
    if approval_workflow == "project_init" and operation_class in FORBIDDEN_GENERIC_PROJECT_INIT_CLASSES:
        reasons.append(f"{operation_class} requires a separate explicit workflow")
    if allowed_callers is not None and actor not in set(allowed_callers):
        reasons.append("caller is not authorized for this operation")
    if allowed_workflows is not None and workflow_identity not in set(allowed_workflows):
        reasons.append("workflow identity is not authorized for this operation")
    required_strength = DEFAULT_MIN_AUTH_STRENGTH.get(operation_class, "per_client_token")
    if not _auth_strength_at_least(source_client_auth_strength, required_strength):
        reasons.append("source-client auth strength is insufficient for operation class")
    if expected_token_source is not None and token_source != expected_token_source:
        reasons.append("token source does not match approved operation")

    stale = validate_stale_plan(
        plan,
        current_state=current_state,
        project_root=root,
        current_target_client_digests=current_target_client_digests,
        current_trust_digest=current_trust_digest,
        current_catalog_revision_or_etag=current_catalog_revision_or_etag,
        current_descriptor_digests=current_descriptor_digests,
    )
    reasons.extend(f"stale plan: {reason}" for reason in stale["reasons"])

    receipt_decisions = []
    if operation_class in MUTATING_CLASSES:
        matching_receipts = [
            receipt
            for receipt in receipts
            if receipt.get("consent_class") == operation_class and receipt.get("source_client") == source_client
        ]
        if not matching_receipts:
            reasons.append("missing consent receipt for mutating operation")
        for receipt in matching_receipts:
            check = validate_consent_receipt(
                receipt,
                plan=plan,
                operation_class=operation_class,
                actor=actor,
                source_client=source_client,
                source_client_auth_strength=required_strength,
                project_root=root,
                service_binding=service_binding,
                target_clients=target_tuple,
                persistent_target=persistent,
                replay_intent=replay_intent,
                now=now,
            )
            receipt_decisions.append(check)
            if check["decision"] == "allow":
                break
        else:
            if matching_receipts:
                reasons.extend(f"receipt check: {reason}" for decision in receipt_decisions for reason in decision["reasons"])

    decision = "allow" if not reasons else "block"
    if decision == "allow" and replay_intent == "resume":
        decision = "resume"
    elif decision == "allow" and replay_intent == "repair":
        decision = "repair"
    return _decision(decision, reasons, observed_receipt_count=len(receipt_decisions), target_clients=list(target_tuple))


def validate_stale_plan(
    plan: Mapping[str, Any],
    *,
    current_state: Mapping[str, Any] | None,
    project_root: str | Path,
    current_target_client_digests: Mapping[str, Any] | None = None,
    current_trust_digest: str | None = None,
    current_catalog_revision_or_etag: str | None = None,
    current_descriptor_digests: Mapping[str, str] | None = None,
    expected_plan_digest: str | None = None,
) -> dict[str, Any]:
    """Compare current snapshots against the plan's stale-input evidence."""

    reasons: list[str] = []
    stale_inputs = plan.get("stale_plan_inputs")
    if not isinstance(stale_inputs, Mapping):
        return _decision("block", ["plan is missing stale-plan inputs"])
    if expected_plan_digest is not None and plan_digest(plan) != expected_plan_digest:
        reasons.append("plan digest changed")
    planned_root = _canonical_root(str(stale_inputs.get("project_root") or _plan_project_root(plan)))
    if planned_root != _canonical_root(project_root):
        reasons.append("project root changed")
    planned_root_hash = stale_inputs.get("project_root_hash")
    if planned_root_hash and planned_root_hash != project_state.project_root_hash(project_root):
        reasons.append("project root hash changed")

    base_state = stale_inputs.get("base_project_state")
    if isinstance(base_state, Mapping):
        current_revision = _state_revision_or_none(current_state)
        if base_state.get("revision") != current_revision:
            reasons.append("project state revision changed")
        if base_state.get("status") != (current_state or {}).get("status"):
            reasons.append("project state status changed")
        current_digest = stable_digest(current_state) if current_state else None
        if base_state.get("digest") != current_digest:
            reasons.append("project state digest changed")

    planned_clients = stale_inputs.get("target_client_digests")
    if isinstance(planned_clients, Mapping):
        current_clients = dict(current_target_client_digests or {})
        for client, digest in planned_clients.items():
            if current_clients.get(client) != digest:
                reasons.append(f"target client digest changed: {client}")
    if stale_inputs.get("trust_state_digest") != current_trust_digest:
        reasons.append("trust state digest changed")
    catalog = stale_inputs.get("catalog")
    if isinstance(catalog, Mapping) and catalog.get("revision_or_etag") != current_catalog_revision_or_etag:
        reasons.append("catalog revision or etag changed")
    descriptor_digests = current_descriptor_digests or {}
    for descriptor in stale_inputs.get("selected_service_descriptors", []) or []:
        if not isinstance(descriptor, Mapping):
            continue
        descriptor_id = str(descriptor.get("descriptor_id"))
        if descriptor_id in descriptor_digests and descriptor_digests[descriptor_id] != descriptor.get("artifact_digest"):
            reasons.append(f"descriptor digest changed: {descriptor_id}")
    if isinstance(catalog, Mapping) and isinstance(catalog.get("descriptor_digests"), Mapping):
        for descriptor_id, planned_digest in catalog["descriptor_digests"].items():
            descriptor_key = str(descriptor_id)
            if descriptor_key in descriptor_digests and descriptor_digests[descriptor_key] != planned_digest:
                reasons.append(f"descriptor digest changed: {descriptor_key}")
    return _decision("block" if reasons else "allow", reasons)


def build_plan_journal_entry(
    *,
    plan: Mapping[str, Any],
    run_id: str,
    step_id: str,
    operation_class: str,
    actor: str,
    source_client: str,
    base_revision: int | None,
    observed_revision: int | None,
    required_receipts: Iterable[Mapping[str, Any]],
    observed_receipts: Iterable[Mapping[str, Any]],
    service_contract_refs: Iterable[Mapping[str, Any]] = (),
    semantic_policy_refs: Iterable[Mapping[str, Any]] = (),
    service_management_handoff_refs: Iterable[Mapping[str, Any]] = (),
    redacted_output_summary: Mapping[str, Any] | None = None,
    status: str = "planned",
    replay_policy: str = "same_plan_resume",
    recovery_outcome: str = "resume",
    lock_owner: str | None = None,
    lock_acquisition: Mapping[str, Any] | None = None,
    preconditions: Iterable[Mapping[str, Any] | str] = (),
    write_set: Iterable[Mapping[str, Any] | str] = (),
    verification_trace_refs: Iterable[Mapping[str, Any]] = (),
    result_hashes: Iterable[str] = (),
    created_at: str | None = None,
) -> dict[str, Any]:
    """Construct one append-only approved-plan journal entry."""

    summary = _redacted_summary(redacted_output_summary or {})
    entry = {
        "schema_version": AUTHORIZATION_HELPER_VERSION,
        "journal_type": "approved_plan_step",
        "plan_id": str(plan.get("plan_id") or "plan"),
        "run_id": run_id,
        "step_id": step_id,
        "plan_digest": plan_digest(plan),
        "pre_apply_snapshot_refs": _snapshot_refs(plan),
        "actor": actor,
        "source_client": source_client,
        "base_revision": base_revision,
        "observed_revision": observed_revision,
        "lock_owner": lock_owner,
        "lock_acquisition": _json_compatible_copy(lock_acquisition or {"status": "not_requested"}),
        "preconditions": _json_compatible_copy(list(preconditions)),
        "operation_class": operation_class,
        "consent_class": operation_class,
        "required_consent_receipts": [_receipt_ref(receipt, created_at=created_at) for receipt in required_receipts],
        "observed_consent_receipts": [_receipt_ref(receipt, created_at=created_at) for receipt in observed_receipts],
        "service_contract_refs": _json_compatible_copy(list(service_contract_refs)),
        "semantic_tool_policy_refs": _json_compatible_copy(list(semantic_policy_refs)),
        "service_management_handoff_refs": _json_compatible_copy(list(service_management_handoff_refs)),
        "write_set": _json_compatible_copy(list(write_set)),
        "redacted_output_summary": summary,
        "status": status,
        "created_at": created_at or now_timestamp(),
        "result_hashes": list(result_hashes),
        "verification_trace_refs": _json_compatible_copy(list(verification_trace_refs)),
        "replay_policy": replay_policy,
        "recovery_outcome": recovery_outcome,
        "redaction_status": "redacted",
    }
    contracts.validate_redacted(entry, require_status=True)
    return entry


def project_local_apply_preflight(
    *,
    operation_class: str,
    project_root: str | Path,
    target_path: str | Path,
    desired_content: Any,
    current_content: Any | None = None,
    current_block: Mapping[str, Any] | None = None,
    owner_id: str = "contextforge-control-plane",
    receipt: Mapping[str, Any] | None = None,
    plan: Mapping[str, Any] | None = None,
    replay_intent: str = "initial_apply",
    now: str | None = None,
) -> dict[str, Any]:
    """Return idempotent project-local apply decisions without file mutation."""

    reasons: list[str] = []
    root = _canonical_root(project_root)
    path = Path(target_path).expanduser()
    if not path.is_absolute():
        path = root / path
    path = path.resolve(strict=False)
    if not project_state.is_relative_to(path, root):
        return _decision("block", ["target path is outside canonical project root"], target_path=str(path))
    if operation_class not in {"project_state_write", "project_local_config_write", "secret_placeholder_change"}:
        return _decision("block", ["preflight only supports project-local state and owned project-local config"], target_path=str(path))

    if receipt is not None:
        check = validate_consent_receipt(
            receipt,
            plan=plan,
            operation_class=operation_class,
            project_root=root,
            persistent_target="file",
            replay_intent=replay_intent,
            now=now,
        )
        reasons.extend(check["reasons"])

    desired_digest = stable_digest(desired_content)
    current_digest = stable_digest(current_content) if current_content is not None else None
    if current_block is not None:
        block_name_matches = bool(current_block.get("name") in {None, "", "contextforge", "contextforge-control-plane"} or current_block.get("target_path") == str(path))
        managed_by = current_block.get("managed_by") or current_block.get("owner")
        owned = current_block.get("owned") is True or managed_by == owner_id
        block_content = current_block.get("content", current_content)
        block_digest = current_block.get("content_digest") or stable_digest(block_content)
        if block_name_matches and not owned:
            return _decision("block", ["unmanaged same-name config block requires user action"], target_path=str(path), action="user_action")
        if owned and block_digest == desired_digest:
            decision = "resume" if replay_intent == "resume" else "allow"
            return _decision(decision, reasons, target_path=str(path), action="noop", content_digest=desired_digest)
        if owned:
            decision = "repair" if replay_intent == "repair" else "allow"
            return _decision(decision if not reasons else "block", reasons, target_path=str(path), action="update_owned_block", content_digest=desired_digest)

    if current_content is not None and current_digest == desired_digest:
        decision = "resume" if replay_intent == "resume" else "allow"
        return _decision(decision if not reasons else "block", reasons, target_path=str(path), action="noop", content_digest=desired_digest)
    return _decision("allow" if not reasons else "block", reasons, target_path=str(path), action="write_project_local", content_digest=desired_digest)


def now_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _decision(decision: str, reasons: Iterable[str], **metadata: Any) -> dict[str, Any]:
    result = {"decision": decision, "allowed": decision in {"allow", "resume", "repair"}, "reasons": list(dict.fromkeys(reasons))}
    result.update(metadata)
    return result


def _receipt_scope(scope: Mapping[str, Any], *, root: str | None, consent_class: str) -> dict[str, Any]:
    target_clients = _target_clients(scope.get("target_clients"))
    output = {
        "project_root": root,
        "service_binding": scope.get("service_binding"),
        "client": scope.get("client") or (target_clients[0] if len(target_clients) == 1 else None),
        "persistent_target": scope.get("persistent_target") or PERSISTENT_TARGET_BY_CLASS.get(consent_class, "file"),
    }
    if target_clients:
        output["x_target_clients"] = target_clients
    if scope.get("operation_class"):
        output["x_operation_class"] = scope.get("operation_class")
    return output


def _receipt_id(receipt: Mapping[str, Any]) -> str:
    consent_class = str(receipt.get("consent_class") or "unknown")
    integrity_body = {
        key: _json_compatible_copy(value)
        for key, value in receipt.items()
        if key != "receipt_id"
    }
    raw = stable_digest(integrity_body)
    return f"receipt-{consent_class.replace('_', '-')}-{raw.removeprefix('sha256:')[:16]}"


def _scope_mismatch_reasons(
    receipt: Mapping[str, Any],
    project_root: str | Path | None,
    service_binding: str | None,
    target_clients: Iterable[str] | None,
    persistent_target: str | None,
    operation_class: str | None,
) -> list[str]:
    scope = receipt.get("scope") if isinstance(receipt.get("scope"), Mapping) else {}
    reasons: list[str] = []
    if project_root is not None and scope.get("project_root") != _canonical_root(project_root):
        reasons.append("receipt project root scope does not match")
    scoped_service = scope.get("service_binding")
    if service_binding is not None:
        if operation_class in SERVICE_BOUND_OPERATION_CLASSES and scoped_service != service_binding:
            reasons.append("receipt service binding scope does not match")
        elif operation_class not in SERVICE_BOUND_OPERATION_CLASSES and scoped_service not in {None, service_binding}:
            reasons.append("receipt service binding scope does not match")
    if persistent_target is not None and scope.get("persistent_target") != persistent_target:
        reasons.append("receipt persistent target scope does not match")
    expected_clients = _target_clients(target_clients)
    scoped_clients = _target_clients(scope.get("x_target_clients") or scope.get("client"))
    if expected_clients and scoped_clients and scoped_clients != expected_clients:
        reasons.append("receipt target-client scope does not match")
    return reasons


def _replay_allowed(policy: str, replay_intent: str) -> bool:
    return replay_intent in REPLAY_COMPATIBILITY.get(policy, frozenset())


def _auth_strength_at_least(actual: str, minimum: str) -> bool:
    return AUTH_STRENGTH_ORDER.get(actual, -1) >= AUTH_STRENGTH_ORDER.get(minimum, 99)


def _is_expired(expires_at: str, now: str) -> bool:
    try:
        return _parse_timestamp(expires_at) <= _parse_timestamp(now)
    except ValueError:
        return True


def _parse_timestamp(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _plan_project_root(plan: Mapping[str, Any], scope: Mapping[str, Any] | None = None) -> str | None:
    if scope and scope.get("project_root"):
        return str(scope["project_root"])
    project = plan.get("project")
    if isinstance(project, Mapping) and project.get("root"):
        return str(project["root"])
    stale_inputs = plan.get("stale_plan_inputs")
    if isinstance(stale_inputs, Mapping) and stale_inputs.get("project_root"):
        return str(stale_inputs["project_root"])
    return None


def _canonical_root(root: str | Path | None) -> str | None:
    if root is None:
        return None
    return str(project_state.canonical_root(root))


def _state_revision_or_none(state: Mapping[str, Any] | None) -> int | None:
    if not state:
        return None
    try:
        return project_state.state_revision(dict(state))
    except project_state.StateValidationError:
        return None


def _target_clients(clients: Any) -> list[str]:
    if clients is None:
        return []
    if isinstance(clients, str):
        return [clients]
    if isinstance(clients, Iterable):
        return sorted(str(client) for client in clients)
    return [str(clients)]


def _snapshot_refs(plan: Mapping[str, Any]) -> dict[str, Any]:
    stale_inputs = plan.get("stale_plan_inputs") if isinstance(plan.get("stale_plan_inputs"), Mapping) else {}
    return _json_compatible_copy(stale_inputs)


def _receipt_ref(receipt: Mapping[str, Any], *, created_at: str | None = None) -> dict[str, Any]:
    return {
        "ref": f"run/consent-receipts/{receipt.get('receipt_id', 'receipt')}.json",
        "content_digest": stable_digest(receipt),
        "catalog_revision_or_etag": None,
        "resolved_at": created_at or now_timestamp(),
    }


def _redacted_summary(summary: Mapping[str, Any]) -> dict[str, Any]:
    redacted = _json_compatible_copy(summary)
    for path, value in _walk(redacted):
        key = path[-1].lower() if path else ""
        if any(marker in key for marker in SECRET_OUTPUT_KEYS):
            raise ValueError(f"redacted output summary contains secret-like field: {'.'.join(path)}")
        if isinstance(value, str):
            contracts.validate_redacted({"value": value})
    return redacted


def _walk(value: Any, path: tuple[str, ...] = ()) -> Iterable[tuple[tuple[str, ...], Any]]:
    yield path, value
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield from _walk(child, (*path, str(key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, (*path, str(index)))


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
