#!/usr/bin/env python3
"""Pure ContextForge binding intents for project-scoped service provision."""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

import control_plane_contracts as contracts


SCHEMA_URI = "contextforge://control-plane/contextforge-binding-intent/v1"
HELPER_VERSION = 1
PROJECT_SCOPED_CLASSES = frozenset({"instance_per_project", "project_scoped_shared_backend"})
FORBIDDEN_PROJECT_PROVISION_CLASSES = frozenset(
    {
        "catalog_promotion",
        "user_global_client_trust",
        "user_global_config_write",
        "secret_value_write",
        "token_material_change",
        "network_exposure_change",
    }
)
CLIENT_CONFIG_OWNED_BLOCK_CLASSES = frozenset({"owned", "legacy_owned", "absent"})
RECOVERY_OUTCOMES = frozenset(
    {
        "resume",
        "forward_repair",
        "rollback_by_approved_workflow",
        "manual_recovery",
        "fresh_approval_required",
    }
)
RECOVERY_BY_FAILURE = {
    "registration_missing": "resume",
    "registration_stale": "forward_repair",
    "virtual_server_missing": "resume",
    "virtual_server_policy_mismatch": "forward_repair",
    "client_binding_not_written": "resume",
    "client_binding_config_conflict": "manual_recovery",
    "target_client_mismatch": "fresh_approval_required",
    "stale_gateway_digest": "forward_repair",
    "stale_client_digest": "fresh_approval_required",
    "shared_canonical_identity_mutation": "fresh_approval_required",
    "catalog_promotion_requested": "fresh_approval_required",
    "user_global_trust_bundled": "fresh_approval_required",
}
REQUIRED_CLIENT_BINDING_TRACE_LAYERS = (
    "contextforge_gateway",
    "virtual_server",
    "tool_policy",
    "target_client",
    "redaction",
)


class ContextForgeBindingInputError(ValueError):
    """Raised when an intent request is missing required identity inputs."""


def now_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stable_digest(value: Any) -> str:
    encoded = json.dumps(_json_copy(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def build_contextforge_registration_intent(
    *,
    plan_id: str,
    service_binding: str,
    contract_card: Mapping[str, Any],
    backend_manifest_ref: Mapping[str, Any],
    gateway_name: str,
    gateway_url: str,
    upstream_transport: str,
    consent_receipt_refs: Sequence[Mapping[str, Any]] = (),
    stale_inputs: Mapping[str, Any] | None = None,
    requested_operation_class: str = "service_provision",
    mutate_shared_canonical_identity: bool = False,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build a non-mutating ContextForge gateway registration intent."""

    _require("plan_id", plan_id)
    _require("service_binding", service_binding)
    _require("gateway_name", gateway_name)
    _require("gateway_url", gateway_url)
    instantiation_class = str(contract_card.get("instantiation_class") or "")
    blockers = _base_scope_blockers(
        contract_card=contract_card,
        requested_operation_class=requested_operation_class,
        mutate_shared_canonical_identity=mutate_shared_canonical_identity,
    )
    if not backend_manifest_ref:
        blockers.append(_blocker("missing_backend_manifest_ref", "ContextForge registration requires a backend manifest ref."))
    if _stale(stale_inputs):
        blockers.append(_blocker("stale_gateway_digest", "gateway/catalog inputs changed since planning."))

    intent = {
        "schema_uri": SCHEMA_URI,
        "intent_type": "contextforge_gateway_registration",
        "helper_version": HELPER_VERSION,
        "plan_id": plan_id,
        "service_binding": service_binding,
        "service_family": contract_card.get("service_family"),
        "instantiation_class": instantiation_class,
        "decision": "block" if blockers else "intend",
        "blockers": _dedupe_blockers(blockers),
        "contextforge_authority": {
            "canonical_registry": "ContextForge",
            "client_configs_are_service_identities": False,
            "mutation_path": "contextforge_api_or_admin_behavior",
        },
        "gateway_registration": {
            "action": "register_or_refresh_gateway",
            "name": gateway_name,
            "url": gateway_url,
            "transport": upstream_transport,
            "service_binding": service_binding,
            "backend_manifest_ref": _json_copy(backend_manifest_ref),
        },
        "required_consent_receipt_refs": _json_copy(list(consent_receipt_refs)),
        "stale_inputs": _json_copy(stale_inputs or {}),
        "write_set": ["contextforge:gateways"],
        "non_actions": [
            "does not call ContextForge APIs",
            "does not promote catalog candidates",
            "does not mutate shared canonical service identity",
            "does not write client config or trust state",
        ],
        "trace_requirements": build_trace_ref_requirements(service_binding=service_binding, target_client=None),
        "generated_at": generated_at or now_timestamp(),
        "redaction_status": "redacted",
    }
    contracts.validate_redacted(intent, require_status=True)
    return intent


def build_virtual_server_association_intent(
    *,
    plan_id: str,
    service_binding: str,
    contract_card: Mapping[str, Any],
    virtual_server_name: str,
    gateway_ref: Mapping[str, Any],
    semantic_tool_policy: Mapping[str, Any],
    consent_receipt_refs: Sequence[Mapping[str, Any]] = (),
    stale_inputs: Mapping[str, Any] | None = None,
    requested_operation_class: str = "service_provision",
    mutate_shared_canonical_identity: bool = False,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build a non-mutating virtual-server tool-association intent."""

    _require("plan_id", plan_id)
    _require("service_binding", service_binding)
    _require("virtual_server_name", virtual_server_name)
    blockers = _base_scope_blockers(
        contract_card=contract_card,
        requested_operation_class=requested_operation_class,
        mutate_shared_canonical_identity=mutate_shared_canonical_identity,
    )
    blockers.extend(_policy_blockers(semantic_tool_policy, expected_service_binding=service_binding))
    if not gateway_ref:
        blockers.append(_blocker("missing_gateway_ref", "virtual-server association requires a ContextForge gateway ref."))
    if _stale(stale_inputs):
        blockers.append(_blocker("stale_gateway_digest", "gateway/catalog inputs changed since planning."))

    intent = {
        "schema_uri": SCHEMA_URI,
        "intent_type": "contextforge_virtual_server_association",
        "helper_version": HELPER_VERSION,
        "plan_id": plan_id,
        "service_binding": service_binding,
        "decision": "block" if blockers else "intend",
        "blockers": _dedupe_blockers(blockers),
        "virtual_server_update": {
            "action": "create_or_refresh_project_virtual_server",
            "name": virtual_server_name,
            "gateway_ref": _json_copy(gateway_ref),
            "associated_tool_ids": list(semantic_tool_policy.get("compiled_tool_ids") or []),
            "association_source": "compiled_semantic_tool_policy",
            "negative_checks": _json_copy(list(semantic_tool_policy.get("negative_checks") or [])),
        },
        "required_policy_refs": [_artifact_ref_for("semantic-tool-policies", semantic_tool_policy, generated_at=generated_at)],
        "required_consent_receipt_refs": _json_copy(list(consent_receipt_refs)),
        "expected_readback": [
            "ContextForge virtual server exists by canonical name",
            "associated tool set exactly matches compiled semantic policy",
            "excluded tools are absent in virtual-server readback",
        ],
        "write_set": ["contextforge:virtual_servers"],
        "non_actions": [
            "does not call ContextForge APIs",
            "does not write client config",
            "does not suppress negative tool-policy checks",
        ],
        "trace_requirements": build_trace_ref_requirements(service_binding=service_binding, target_client=None),
        "generated_at": generated_at or now_timestamp(),
        "redaction_status": "redacted",
    }
    contracts.validate_redacted(intent, require_status=True)
    return intent


def build_client_binding_intent(
    *,
    plan_id: str,
    project_root: str,
    service_binding: str,
    target_client: str,
    virtual_server_ref: Mapping[str, Any],
    semantic_tool_policy: Mapping[str, Any],
    conformance_result: Mapping[str, Any],
    consent_receipt_refs: Sequence[Mapping[str, Any]],
    negative_check_readbacks: Sequence[Mapping[str, Any]],
    trace_refs: Sequence[Mapping[str, Any]],
    expected_gateway_digest: str | None = None,
    current_gateway_digest: str | None = None,
    expected_client_digest: str | None = None,
    current_client_digest: str | None = None,
    requested_operation_class: str = "project_local_config_write",
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build a client-binding intent; never write a client configuration."""

    gate = evaluate_client_binding_gate(
        plan_id=plan_id,
        project_root=project_root,
        service_binding=service_binding,
        target_client=target_client,
        virtual_server_ref=virtual_server_ref,
        semantic_tool_policy=semantic_tool_policy,
        conformance_result=conformance_result,
        consent_receipt_refs=consent_receipt_refs,
        negative_check_readbacks=negative_check_readbacks,
        trace_refs=trace_refs,
        expected_gateway_digest=expected_gateway_digest,
        current_gateway_digest=current_gateway_digest,
        expected_client_digest=expected_client_digest,
        current_client_digest=current_client_digest,
        requested_operation_class=requested_operation_class,
        generated_at=generated_at,
    )
    patch_plan = {
        "surface": _client_surface(target_client),
        "scope": "project_local",
        "operation": "upsert_owned_contextforge_binding",
        "service_binding": service_binding,
        "virtual_server_ref": _json_copy(virtual_server_ref),
        "target_client": target_client,
    }
    intent = {
        "schema_uri": SCHEMA_URI,
        "intent_type": "client_binding",
        "helper_version": HELPER_VERSION,
        "plan_id": plan_id,
        "project_root": project_root,
        "service_binding": service_binding,
        "target_client": target_client,
        "decision": "intend" if gate["eligible"] else "block",
        "eligible_for_client_visible_binding": gate["eligible"],
        "blockers": gate["blockers"],
        "binding_intent": patch_plan,
        "required_conformance_refs": gate["required_conformance_refs"],
        "required_policy_refs": gate["required_policy_refs"],
        "required_consent_receipt_refs": _json_copy(list(consent_receipt_refs)),
        "required_trace_refs": gate["required_trace_refs"],
        "negative_check_readbacks": _json_copy(list(negative_check_readbacks)),
        "write_set": [_client_surface(target_client)],
        "non_actions": [
            "does not write client config",
            "does not grant user-global trust",
            "does not write secrets",
            "does not restart client",
        ],
        "generated_at": generated_at or now_timestamp(),
        "redaction_status": "redacted",
    }
    contracts.validate_redacted(intent, require_status=True)
    return intent


def evaluate_client_binding_gate(
    *,
    plan_id: str,
    project_root: str,
    service_binding: str,
    target_client: str,
    virtual_server_ref: Mapping[str, Any],
    semantic_tool_policy: Mapping[str, Any],
    conformance_result: Mapping[str, Any],
    consent_receipt_refs: Sequence[Mapping[str, Any]],
    negative_check_readbacks: Sequence[Mapping[str, Any]],
    trace_refs: Sequence[Mapping[str, Any]],
    expected_gateway_digest: str | None = None,
    current_gateway_digest: str | None = None,
    expected_client_digest: str | None = None,
    current_client_digest: str | None = None,
    requested_operation_class: str = "project_local_config_write",
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Return the fail-closed eligibility decision for client-visible binding."""

    _require("plan_id", plan_id)
    _require("project_root", project_root)
    _require("service_binding", service_binding)
    _require("target_client", target_client)
    blockers: list[dict[str, Any]] = []
    if requested_operation_class in FORBIDDEN_PROJECT_PROVISION_CLASSES:
        blockers.append(_blocker(f"{requested_operation_class}_requested", f"{requested_operation_class} requires a separate workflow."))
    if not virtual_server_ref:
        blockers.append(_blocker("missing_virtual_server_ref", "client binding requires a ContextForge virtual-server ref."))
    blockers.extend(_policy_blockers(semantic_tool_policy, expected_service_binding=service_binding, expected_target_client=target_client))
    blockers.extend(_conformance_blockers(conformance_result, service_binding=service_binding, target_client=target_client, project_root=project_root))
    blockers.extend(_negative_readback_blockers(semantic_tool_policy, negative_check_readbacks))
    blockers.extend(_consent_ref_blockers(consent_receipt_refs))
    blockers.extend(_trace_ref_blockers(trace_refs, target_client=target_client))
    if expected_gateway_digest and current_gateway_digest and expected_gateway_digest != current_gateway_digest:
        blockers.append(_blocker("stale_gateway_digest", "gateway digest changed since planning."))
    if expected_client_digest and current_client_digest and expected_client_digest != current_client_digest:
        blockers.append(_blocker("stale_client_digest", "target-client digest changed since planning."))

    return {
        "decision": "allow_client_binding_intent" if not blockers else "block_client_binding",
        "eligible": not blockers,
        "blockers": _dedupe_blockers(blockers),
        "required_policy_refs": [_artifact_ref_for("semantic-tool-policies", semantic_tool_policy, generated_at=generated_at)],
        "required_conformance_refs": [_artifact_ref_for("client-conformance", conformance_result, generated_at=generated_at)],
        "required_trace_refs": _json_copy(list(trace_refs)),
        "trace_requirements": build_trace_ref_requirements(service_binding=service_binding, target_client=target_client),
    }


def build_client_write_hook_preflight(
    *,
    client_binding_intent: Mapping[str, Any],
    owned_block_class: str,
    config_scope: str,
    trust_mutation_requested: bool = False,
) -> dict[str, Any]:
    """Gate a future client write hook without writing any client file."""

    blockers = list(client_binding_intent.get("blockers") or [])
    if client_binding_intent.get("eligible_for_client_visible_binding") is not True:
        blockers.append(_blocker("client_binding_not_eligible", "client-binding gate has not passed."))
    if owned_block_class not in CLIENT_CONFIG_OWNED_BLOCK_CLASSES:
        blockers.append(_blocker("client_config_conflict", f"unsupported owned-block class: {owned_block_class}"))
    if config_scope != "project_local":
        blockers.append(_blocker("user_global_config_write_requested", "client write hook may only target project-local config."))
    if trust_mutation_requested:
        blockers.append(_blocker("user_global_trust_bundled", "user-global trust cannot be bundled with client config writes."))

    return {
        "schema_uri": SCHEMA_URI,
        "intent_type": "client_write_hook_preflight",
        "decision": "allow_owned_project_local_write" if not blockers else "block",
        "write_allowed_by_hook": not blockers,
        "blockers": _dedupe_blockers(blockers),
        "patch_plan": _json_copy(client_binding_intent.get("binding_intent") or {}),
        "non_actions": ["does not write client config", "does not grant trust", "does not restart client"],
        "redaction_status": "redacted",
    }


def build_trace_ref_requirements(*, service_binding: str, target_client: str | None) -> dict[str, Any]:
    """Return the trace layers required before project-scoped binding is verified."""

    layers = list(REQUIRED_CLIENT_BINDING_TRACE_LAYERS if target_client else ("contextforge_gateway", "virtual_server", "tool_policy", "redaction"))
    return {
        "service_binding": service_binding,
        "target_client": target_client,
        "required_layers": layers,
        "required_results": ["passed"],
        "failure_is_blocking": True,
    }


def classify_recovery(failure: Mapping[str, Any] | str) -> dict[str, Any]:
    """Classify a partial binding failure for W7-C recovery fixtures."""

    failure_type = str(failure.get("type") if isinstance(failure, Mapping) else failure)
    outcome = RECOVERY_BY_FAILURE.get(failure_type, "manual_recovery")
    if outcome not in RECOVERY_OUTCOMES:
        outcome = "manual_recovery"
    return {
        "failure_type": failure_type,
        "recovery_outcome": outcome,
        "allowed_outcomes": sorted(RECOVERY_OUTCOMES),
        "requires_new_consent": outcome == "fresh_approval_required",
        "requires_approved_workflow": outcome in {"rollback_by_approved_workflow", "fresh_approval_required"},
    }


def _base_scope_blockers(
    *,
    contract_card: Mapping[str, Any],
    requested_operation_class: str,
    mutate_shared_canonical_identity: bool,
) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    instantiation_class = str(contract_card.get("instantiation_class") or "")
    if requested_operation_class in FORBIDDEN_PROJECT_PROVISION_CLASSES:
        blockers.append(_blocker("catalog_promotion_requested", f"{requested_operation_class} requires a separate workflow."))
    if instantiation_class not in PROJECT_SCOPED_CLASSES:
        blockers.append(
            _blocker(
                "not_project_scoped_service",
                f"project-scoped ContextForge binding requires one of {sorted(PROJECT_SCOPED_CLASSES)}.",
            )
        )
    if mutate_shared_canonical_identity or bool(contract_card.get("x_mutates_shared_canonical_identity")):
        blockers.append(_blocker("shared_canonical_identity_mutation", "project provision cannot mutate shared canonical identity."))
    return blockers


def _policy_blockers(
    policy: Mapping[str, Any],
    *,
    expected_service_binding: str,
    expected_target_client: str | None = None,
) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    if not policy:
        return [_blocker("missing_semantic_tool_policy", "compiled semantic tool policy is required.")]
    if policy.get("service_binding") != expected_service_binding:
        blockers.append(_blocker("policy_service_binding_mismatch", "semantic policy service binding does not match."))
    if expected_target_client and policy.get("x_target_client") != expected_target_client:
        blockers.append(_blocker("target_client_mismatch", "semantic policy target client does not match binding target."))
    if policy.get("x_status") != "compiled":
        blockers.append(_blocker("semantic_tool_policy_not_compiled", "semantic tool policy must be compiled."))
    for item in policy.get("x_blockers") or []:
        blockers.append(_blocker(str(item.get("type") or "tool_policy_blocker"), str(item.get("message") or "tool policy blocker")))
    stale = policy.get("x_stale_policy_inputs")
    if isinstance(stale, Mapping) and stale.get("stale"):
        blockers.append(_blocker("stale_policy_inputs", "semantic tool policy inputs are stale."))
    if not policy.get("negative_checks"):
        blockers.append(_blocker("missing_negative_checks", "semantic policy must include negative checks."))
    return blockers


def _conformance_blockers(
    conformance: Mapping[str, Any],
    *,
    service_binding: str,
    target_client: str,
    project_root: str,
) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    if not conformance:
        return [_blocker("missing_conformance", "passing client adapter conformance is required.")]
    if conformance.get("status") != "passing_conformance" or conformance.get("decision") != "allow_target_client_proof":
        blockers.append(_blocker("failed_conformance", "target client conformance has not passed."))
    if conformance.get("client_name") and conformance.get("client_name") != target_client:
        blockers.append(_blocker("target_client_mismatch", "conformance client does not match target client."))
    if conformance.get("service_binding") and conformance.get("service_binding") != service_binding:
        blockers.append(_blocker("conformance_service_binding_mismatch", "conformance service binding does not match."))
    if conformance.get("project_root") and conformance.get("project_root") != project_root:
        blockers.append(_blocker("conformance_project_root_mismatch", "conformance project root does not match."))
    for item in conformance.get("blockers") or []:
        blockers.append(_blocker(str(item.get("name") or "conformance_blocker"), str(item.get("message") or "conformance blocker")))
    return blockers


def _negative_readback_blockers(policy: Mapping[str, Any], readbacks: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    expected = _negative_check_keys(policy.get("negative_checks") or [])
    observed = _negative_check_keys(readbacks, only_passed=True)
    blockers: list[dict[str, Any]] = []
    if not readbacks:
        return [_blocker("missing_negative_check_readback", "negative tool-policy readback proof is required.")]
    missing = sorted(expected - observed)
    if missing:
        blockers.append(_blocker("missing_negative_check_readback", "negative check readback proof is missing or not passed.", missing=missing))
    failed = [item for item in readbacks if item.get("status") != "passed"]
    if failed:
        blockers.append(_blocker("failed_negative_check_readback", "one or more negative check readbacks failed."))
    return blockers


def _consent_ref_blockers(receipt_refs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    classes = {str(item.get("consent_class") or item.get("x_consent_class") or "") for item in receipt_refs}
    if "service_provision" not in classes:
        blockers.append(_blocker("missing_service_provision_receipt", "service_provision consent receipt ref is required."))
    if "project_local_config_write" not in classes:
        blockers.append(_blocker("missing_project_local_config_write_receipt", "project_local_config_write consent receipt ref is required."))
    forbidden = classes & FORBIDDEN_PROJECT_PROVISION_CLASSES
    if forbidden:
        blockers.append(_blocker("user_global_trust_bundled", f"separate workflow consent classes cannot be bundled: {sorted(forbidden)}"))
    return blockers


def _trace_ref_blockers(trace_refs: Sequence[Mapping[str, Any]], *, target_client: str) -> list[dict[str, Any]]:
    required = set(REQUIRED_CLIENT_BINDING_TRACE_LAYERS)
    passed = {str(item.get("layer") or item.get("x_verification_layer")) for item in trace_refs if item.get("result") == "passed"}
    missing = sorted(required - passed)
    if missing:
        return [_blocker("trace_missing", "required verification trace refs are missing.", missing=missing)]
    mismatched = [item for item in trace_refs if item.get("target_client") not in {None, target_client}]
    if mismatched:
        return [_blocker("target_client_mismatch", "trace ref target client does not match binding target.")]
    return []


def _negative_check_keys(checks: Iterable[Mapping[str, Any]], *, only_passed: bool = False) -> set[str]:
    keys = set()
    for check in checks:
        if only_passed and check.get("status") != "passed":
            continue
        keys.add(
            "|".join(
                str(check.get(part) or "")
                for part in ("check", "layer", "tool_id", "probe")
            )
        )
    return keys


def _artifact_ref_for(prefix: str, artifact: Mapping[str, Any], *, generated_at: str | None = None) -> dict[str, Any]:
    artifact_id = (
        artifact.get("policy_id")
        or artifact.get("pack_id")
        or artifact.get("trace_id")
        or stable_digest(artifact)[7:19]
    )
    safe_id = str(artifact_id).replace("/", "-").replace(":", "-")
    return contracts.artifact_ref(
        f"contextforge://control-plane/{prefix}/{safe_id}",
        artifact,
        resolved_at=generated_at or str(artifact.get("generated_at") or artifact.get("last_compiled_at") or now_timestamp()),
        catalog_revision_or_etag=None,
    )


def _blocker(blocker_type: str, message: str, **extra: Any) -> dict[str, Any]:
    blocker = {"type": blocker_type, "message": message, "recovery": classify_recovery(blocker_type)["recovery_outcome"]}
    blocker.update(extra)
    return blocker


def _dedupe_blockers(blockers: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for blocker in blockers:
        key = stable_digest(blocker)
        if key not in seen:
            seen.add(key)
            deduped.append(_json_copy(blocker))
    return deduped


def _client_surface(target_client: str) -> str:
    if target_client == "codex":
        return ".codex/config.toml"
    return f"{target_client}:project_local_config"


def _stale(stale_inputs: Mapping[str, Any] | None) -> bool:
    if not isinstance(stale_inputs, Mapping):
        return False
    for expected_key, current_key in (
        ("expected_gateway_digest", "current_gateway_digest"),
        ("expected_gateway_revision", "current_gateway_revision"),
        ("expected_catalog_revision_or_etag", "current_catalog_revision_or_etag"),
    ):
        expected = stale_inputs.get(expected_key)
        current = stale_inputs.get(current_key)
        if expected and current and expected != current:
            return True
    return bool(stale_inputs.get("stale"))


def _require(name: str, value: str) -> None:
    if not value:
        raise ContextForgeBindingInputError(f"{name} is required")


def _json_copy(value: Any) -> Any:
    return copy.deepcopy(value)
