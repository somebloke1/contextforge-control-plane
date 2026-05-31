#!/usr/bin/env python3
"""Pure semantic tool-policy compiler for ContextForge virtual-server views."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

import control_plane_contracts as contracts


SCHEMA_URI = "contextforge://control-plane/schemas/semantic-tool-policy/v1"
COMPILER_VERSION = 1
RISK_CLASS_SCHEMA_MAP = {
    "catalog_admin": "admin",
    "catalog_crud": "admin",
    "trust": "admin",
    "token": "secret",
    "token_material": "secret",
    "secret_value": "secret",
    "remote_exposure": "network_exposure",
}
SCHEMA_RISK_CLASSES = frozenset({"unknown", "read_only", "write", "scope_changing", "admin", "secret", "network_exposure"})
CONSENT_REQUIRED_RISK_CLASSES = frozenset(
    {
        "write",
        "scope_changing",
        "admin",
        "catalog_admin",
        "catalog_crud",
        "trust",
        "token",
        "token_material",
        "secret",
        "secret_value",
        "network_exposure",
        "remote_exposure",
    }
)
SEMANTIC_BLOCKING_RISK_CLASSES = CONSENT_REQUIRED_RISK_CLASSES | frozenset({"unknown"})
SCOPE_CHANGING_IMPACTS = frozenset(
    {
        "project_scope",
        "workspace_root",
        "active_project",
        "credential_scope",
        "resource_scope",
        "backend_scope",
        "backend_operating_scope",
        "remote_exposure",
        "network_exposure",
    }
)
RISK_HINT_RE = re.compile(
    r"(activate[_-]?project|change[_-]?project|workspace[_-]?root|credential|catalog|admin|"
    r"trust|token|secret|network[_-]?exposure|remote[_-]?exposure|expose[_-]?remote)",
    re.IGNORECASE,
)


class ToolPolicyInputError(ValueError):
    """Raised when the policy compiler receives malformed top-level inputs."""


def compile_tool_policy(
    *,
    service_binding: str,
    virtual_server_id: str,
    target_client: str,
    tools: Sequence[Mapping[str, Any]],
    policy_id: str | None = None,
    expected_gateway_revision: str | None = None,
    current_gateway_revision: str | None = None,
    expected_target_client_digest: str | None = None,
    current_target_client_digest: str | None = None,
    manual_overrides: Sequence[Mapping[str, Any]] = (),
    last_readback_trace_ref: Mapping[str, Any] | None = None,
    compiled_at: str | None = None,
) -> dict[str, Any]:
    """Compile discovered tool metadata into a ContextForge association policy.

    This function is intentionally side-effect free. It does not mutate
    ContextForge, client config, trust state, or local project state.
    """

    if not service_binding:
        raise ToolPolicyInputError("service_binding is required")
    if not virtual_server_id:
        raise ToolPolicyInputError("virtual_server_id is required")
    if not target_client:
        raise ToolPolicyInputError("target_client is required")

    tool_copies = [copy.deepcopy(dict(tool)) for tool in tools]
    override_copies = [copy.deepcopy(dict(override)) for override in manual_overrides]
    stale_reasons = _stale_reasons(
        expected_gateway_revision=expected_gateway_revision,
        current_gateway_revision=current_gateway_revision,
        expected_target_client_digest=expected_target_client_digest,
        current_target_client_digest=current_target_client_digest,
    )
    compiled_time = compiled_at or now_timestamp()

    allowed: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    all_risk_classes: set[str] = set()
    all_scope_impacts: set[str] = set()
    approval_gates: set[str] = set()

    override_index = _override_index(override_copies)
    matched_overrides: set[int] = set()

    if stale_reasons:
        blockers.extend(_blocker("stale_policy_inputs", reason) for reason in stale_reasons)

    for tool in sorted(tool_copies, key=_tool_sort_key):
        decision = _classify_tool(
            tool,
            service_binding=service_binding,
            target_client=target_client,
            stale_reasons=stale_reasons,
            override_index=override_index,
        )
        matched_overrides.update(decision["matched_override_indexes"])
        all_risk_classes.update(decision["schema_risk_classes"])
        all_scope_impacts.update(decision["scope_impacts"])
        approval_gates.update(decision["required_consent_classes"])
        if decision["decision"] == "allow":
            allowed.append(decision["record"])
        else:
            excluded.append(decision["record"])
            blockers.extend(decision["blockers"])

    for index, override in enumerate(override_copies):
        if index not in matched_overrides:
            selector = override.get("tool_selector")
            blockers.append(_blocker("unmatched_manual_override", f"manual override did not match a discovered tool: {selector}"))

    compiled_tool_ids = sorted(str(item["tool_id"]) for item in allowed)
    negative_checks = _negative_checks(
        service_binding=service_binding,
        virtual_server_id=virtual_server_id,
        target_client=target_client,
        excluded=excluded,
        compiled_tool_ids=compiled_tool_ids,
    )
    status = "blocked" if blockers else "compiled"

    policy = {
        "policy_id": policy_id
        or _policy_id(
            {
                "service_binding": service_binding,
                "virtual_server_id": virtual_server_id,
                "target_client": target_client,
                "tools": tool_copies,
                "manual_overrides": override_copies,
            }
        ),
        "schema_uri": SCHEMA_URI,
        "service_binding": service_binding,
        "risk_classes": sorted(all_risk_classes or {"unknown"}),
        "scope_impacts": sorted(all_scope_impacts or {"unknown"}),
        "approval_gates": sorted(approval_gates),
        "allowed_tool_selectors": [_selector_for_allowed(tool_id) for tool_id in compiled_tool_ids],
        "excluded_tool_selectors": [_selector_for_excluded(item) for item in excluded],
        "manual_overrides": [_schema_manual_override(item) for item in override_copies],
        "compiled_tool_ids": compiled_tool_ids,
        "negative_checks": negative_checks,
        "last_compiled_at": compiled_time,
        "last_readback_trace_ref": copy.deepcopy(dict(last_readback_trace_ref)) if last_readback_trace_ref else None,
        "x_compiler_version": COMPILER_VERSION,
        "x_status": status,
        "x_virtual_server_id": virtual_server_id,
        "x_target_client": target_client,
        "x_allowed_tools": allowed,
        "x_excluded_tools": excluded,
        "x_blockers": _dedupe_blockers(blockers),
        "x_open_items": _open_items(service_binding, target_client, blockers, compiled_time),
        "x_repair_plan_trigger": bool(blockers),
        "x_stale_policy_inputs": {
            "expected_gateway_revision": expected_gateway_revision,
            "current_gateway_revision": current_gateway_revision,
            "expected_target_client_digest": expected_target_client_digest,
            "current_target_client_digest": current_target_client_digest,
            "stale": bool(stale_reasons),
        },
    }
    contracts.validate_artifact("semantic_tool_policy", policy)
    return policy


def now_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stable_digest(value: Any) -> str:
    encoded = json.dumps(_json_compatible_copy(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _classify_tool(
    tool: Mapping[str, Any],
    *,
    service_binding: str,
    target_client: str,
    stale_reasons: Sequence[str],
    override_index: Mapping[str, list[tuple[int, Mapping[str, Any]]]],
) -> dict[str, Any]:
    tool_id = _tool_id(tool)
    original_name = _tool_name(tool, "original_name")
    exposed_name = _tool_name(tool, "exposed_name") or original_name
    risk_classes = _risk_classes(tool, original_name, exposed_name)
    scope_impacts = _scope_impacts(tool, risk_classes)
    schema_risk_classes = {_schema_risk_class(risk) for risk in risk_classes}
    required_consent_classes = _required_consent_classes(tool, risk_classes)
    reasons: list[dict[str, str]] = []
    blockers: list[dict[str, Any]] = []

    if not tool_id:
        reasons.append(_reason("unknown_tool", "tool has no ContextForge tool id"))
    if not original_name or not exposed_name:
        reasons.append(_reason("unknown_tool", "tool is missing original or exposed name"))
    if not tool.get("service_binding"):
        reasons.append(_reason("missing_service_binding", "tool metadata lacks service binding"))
    elif str(tool.get("service_binding")) != service_binding:
        reasons.append(_reason("service_binding_mismatch", "tool service binding does not match the policy service binding"))
    if target_client not in _target_clients(tool):
        reasons.append(_reason("target_client_mismatch", "tool metadata does not authorize this target client"))
    if not _metadata_present(tool):
        reasons.append(_reason("missing_risk_metadata", "tool lacks required semantic risk metadata"))
    if "unknown" in risk_classes:
        reasons.append(_reason("unknown_risk_class", "tool risk class is unknown or unsupported"))
    for risk in sorted(risk_classes & SEMANTIC_BLOCKING_RISK_CLASSES):
        reasons.append(_reason("semantic_risk_excluded", f"risk class requires exclusion or explicit consent: {risk}"))
    if _scope_changing(tool, risk_classes, scope_impacts):
        reasons.append(_reason("scope_changing_excluded", "tool can change project, credential, resource, backend, or exposure scope"))
    for stale_reason in stale_reasons:
        reasons.append(_reason("stale_policy_inputs", stale_reason))

    matched_overrides: list[int] = []
    override = _matching_override(tool, tool_id, original_name, exposed_name, override_index, matched_overrides)
    if override:
        override_decision = str(override.get("decision"))
        if override_decision == "deny":
            reasons.append(_reason("manual_override_deny", "manual override denied the tool"))
        elif override_decision == "allow" and _manual_allow_has_evidence(override, risk_classes):
            reasons = [reason for reason in reasons if reason["type"] not in {"semantic_risk_excluded", "scope_changing_excluded"}]
        elif override_decision == "allow":
            reasons.append(_reason("manual_allow_missing_evidence", "manual allow lacks consent receipt, requirement id, risk class, or negative checks"))

    if reasons:
        blockers.extend(_blocker(reason["type"], reason["message"], tool_id=tool_id or "<unknown>") for reason in reasons)

    record = {
        "tool_id": tool_id or "<unknown>",
        "original_name": original_name or "<unknown>",
        "exposed_name": exposed_name or "<unknown>",
        "service_binding": tool.get("service_binding"),
        "target_client": target_client,
        "semantic_risk_classes": sorted(risk_classes),
        "schema_risk_classes": sorted(schema_risk_classes),
        "scope_impacts": sorted(scope_impacts),
        "required_consent_classes": sorted(required_consent_classes),
    }
    if reasons:
        record["exclusion_reasons"] = reasons
    else:
        record["decision_reason"] = "risk metadata permits target-client virtual-server association"

    return {
        "decision": "exclude" if reasons else "allow",
        "record": record,
        "blockers": blockers,
        "schema_risk_classes": schema_risk_classes,
        "scope_impacts": scope_impacts,
        "required_consent_classes": required_consent_classes,
        "matched_override_indexes": matched_overrides,
    }


def _negative_checks(
    *,
    service_binding: str,
    virtual_server_id: str,
    target_client: str,
    excluded: Sequence[Mapping[str, Any]],
    compiled_tool_ids: Sequence[str],
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for item in sorted(excluded, key=lambda record: str(record.get("tool_id"))):
        names = sorted({str(item["tool_id"]), str(item["original_name"]), str(item["exposed_name"])})
        risk_classes = list(item.get("semantic_risk_classes", []))
        for layer, probe in (
            ("contextforge_virtual_server", "readback_server_tools"),
            ("target_client", "list_tools_and_call_tool"),
        ):
            checks.append(
                {
                    "check": "excluded_tool_absent",
                    "layer": layer,
                    "probe": probe,
                    "service_binding": service_binding,
                    "virtual_server_id": virtual_server_id,
                    "target_client": target_client if layer == "target_client" else None,
                    "tool_id": item["tool_id"],
                    "original_name": item["original_name"],
                    "exposed_name": item["exposed_name"],
                    "negative_match_names": names,
                    "risk_classes": risk_classes,
                    "expected": "absent",
                    "status": "pending",
                }
            )
    checks.append(
        {
            "check": "compiled_association_exact_match",
            "layer": "contextforge_virtual_server",
            "probe": "readback_server_tools",
            "service_binding": service_binding,
            "virtual_server_id": virtual_server_id,
            "expected_tool_ids": list(compiled_tool_ids),
            "status": "pending",
        }
    )
    return checks


def _stale_reasons(
    *,
    expected_gateway_revision: str | None,
    current_gateway_revision: str | None,
    expected_target_client_digest: str | None,
    current_target_client_digest: str | None,
) -> list[str]:
    reasons: list[str] = []
    if expected_gateway_revision and current_gateway_revision and expected_gateway_revision != current_gateway_revision:
        reasons.append("gateway revision changed since policy inputs were resolved")
    if expected_target_client_digest and current_target_client_digest and expected_target_client_digest != current_target_client_digest:
        reasons.append("target-client digest changed since policy inputs were resolved")
    return reasons


def _risk_classes(tool: Mapping[str, Any], original_name: str | None, exposed_name: str | None) -> set[str]:
    raw = tool.get("risk_classes")
    if raw is None:
        raw = tool.get("risk_class")
    if isinstance(raw, str):
        values = {raw}
    elif isinstance(raw, Iterable):
        values = {str(item) for item in raw}
    else:
        values = set()
    normalized = {_normalize_risk(value) for value in values if value}
    if not normalized:
        return {"unknown"}
    if any(risk not in SCHEMA_RISK_CLASSES and risk not in RISK_CLASS_SCHEMA_MAP for risk in normalized):
        normalized.add("unknown")
    if RISK_HINT_RE.search(" ".join(filter(None, [original_name, exposed_name]))):
        normalized.update(_semantic_hints(" ".join(filter(None, [original_name, exposed_name]))))
    return normalized


def _scope_impacts(tool: Mapping[str, Any], risk_classes: set[str]) -> set[str]:
    raw = tool.get("scope_impacts")
    if raw is None:
        raw = tool.get("scope_impact")
    if isinstance(raw, str):
        impacts = {raw}
    elif isinstance(raw, Iterable):
        impacts = {str(item) for item in raw}
    else:
        impacts = set()
    impacts = {_normalize_token(item) for item in impacts if item}
    if "scope_changing" in risk_classes:
        impacts.add("backend_operating_scope")
    if risk_classes & {"network_exposure", "remote_exposure"}:
        impacts.add("network_exposure")
    return impacts or {"none"}


def _required_consent_classes(tool: Mapping[str, Any], risk_classes: set[str]) -> set[str]:
    raw = tool.get("required_consent_classes") or tool.get("approval_gates") or []
    if isinstance(raw, str):
        classes = {raw}
    elif isinstance(raw, Iterable):
        classes = {str(item) for item in raw}
    else:
        classes = set()
    if risk_classes & {"secret", "secret_value"}:
        classes.add("secret_value_write")
    if risk_classes & {"token", "token_material"}:
        classes.add("token_material_change")
    if risk_classes & {"network_exposure", "remote_exposure"}:
        classes.add("network_exposure_change")
    if risk_classes & {"catalog_admin", "catalog_crud"}:
        classes.add("catalog_promotion")
    if "trust" in risk_classes:
        classes.add("user_global_client_trust")
    if "write" in risk_classes or "scope_changing" in risk_classes or "admin" in risk_classes:
        classes.add("service_provision")
    return classes


def _scope_changing(tool: Mapping[str, Any], risk_classes: set[str], scope_impacts: set[str]) -> bool:
    if "scope_changing" in risk_classes:
        return True
    if scope_impacts & SCOPE_CHANGING_IMPACTS:
        return True
    return bool(tool.get("changes_scope"))


def _metadata_present(tool: Mapping[str, Any]) -> bool:
    return ("risk_classes" in tool or "risk_class" in tool) and ("scope_impacts" in tool or "scope_impact" in tool)


def _matching_override(
    tool: Mapping[str, Any],
    tool_id: str | None,
    original_name: str | None,
    exposed_name: str | None,
    override_index: Mapping[str, list[tuple[int, Mapping[str, Any]]]],
    matched_overrides: list[int],
) -> Mapping[str, Any] | None:
    candidates: list[tuple[int, Mapping[str, Any]]] = []
    for value in (tool_id, original_name, exposed_name):
        if value:
            candidates.extend(override_index.get(str(value), []))
    for index, override in candidates:
        if _selector_matches(override.get("tool_selector"), tool, tool_id, original_name, exposed_name):
            matched_overrides.append(index)
            return override
    return None


def _manual_allow_has_evidence(override: Mapping[str, Any], risk_classes: set[str]) -> bool:
    return (
        bool(override.get("consent_receipt_ref"))
        and bool(override.get("x_requirement_id"))
        and bool(override.get("x_risk_class"))
        and str(override.get("x_risk_class")) in risk_classes
        and bool(override.get("x_negative_checks"))
    )


def _override_index(overrides: Sequence[Mapping[str, Any]]) -> dict[str, list[tuple[int, Mapping[str, Any]]]]:
    index: dict[str, list[tuple[int, Mapping[str, Any]]]] = {}
    for item_index, override in enumerate(overrides):
        selector = override.get("tool_selector")
        if isinstance(selector, Mapping):
            value = selector.get("value")
            if value is not None:
                index.setdefault(str(value), []).append((item_index, override))
    return index


def _selector_matches(
    selector: Any,
    tool: Mapping[str, Any],
    tool_id: str | None,
    original_name: str | None,
    exposed_name: str | None,
) -> bool:
    if not isinstance(selector, Mapping):
        return False
    selector_type = str(selector.get("selector_type") or "")
    value = str(selector.get("value") or "")
    if selector_type == "tool_id":
        return value == tool_id
    if selector_type == "tool_name":
        return value in {original_name, exposed_name}
    if selector_type == "original_name":
        return value == original_name
    if selector_type == "exposed_name":
        return value == exposed_name
    if selector_type == "risk_class":
        return value in _risk_classes(tool, original_name, exposed_name)
    if selector_type == "tag":
        raw_tags = tool.get("tags") or []
        tags = {str(tag) for tag in raw_tags} if isinstance(raw_tags, Iterable) and not isinstance(raw_tags, str) else {str(raw_tags)}
        return value in tags
    return False


def _schema_manual_override(override: Mapping[str, Any]) -> dict[str, Any]:
    selector = copy.deepcopy(dict(override.get("tool_selector") or {}))
    if selector.get("selector_type") in {"original_name", "exposed_name"}:
        selector["x_original_selector_type"] = selector["selector_type"]
        selector["selector_type"] = "tool_name"
    schema_override = {
        "tool_selector": selector,
        "decision": str(override.get("decision") or "deny"),
        "consent_receipt_ref": copy.deepcopy(dict(override.get("consent_receipt_ref") or _placeholder_ref())),
    }
    for key, value in override.items():
        if str(key).startswith("x_"):
            schema_override[str(key)] = copy.deepcopy(value)
    return schema_override


def _selector_for_allowed(tool_id: str) -> dict[str, Any]:
    return {"selector_type": "tool_id", "value": tool_id, "fail_closed": True}


def _selector_for_excluded(item: Mapping[str, Any]) -> dict[str, Any]:
    return {"selector_type": "tool_id", "value": str(item["tool_id"]), "fail_closed": True}


def _tool_id(tool: Mapping[str, Any]) -> str | None:
    value = tool.get("tool_id") or tool.get("id")
    return str(value) if value else None


def _tool_name(tool: Mapping[str, Any], key: str) -> str | None:
    value = tool.get(key)
    if value is None and key == "original_name":
        value = tool.get("name")
    if value is None and key == "exposed_name":
        value = tool.get("name")
    return str(value) if value else None


def _target_clients(tool: Mapping[str, Any]) -> set[str]:
    raw = tool.get("target_clients")
    if raw is None:
        raw = tool.get("target_client")
    if raw is None:
        return set()
    if isinstance(raw, str):
        return {raw}
    if isinstance(raw, Iterable):
        return {str(item) for item in raw}
    return set()


def _semantic_hints(text: str) -> set[str]:
    hints: set[str] = set()
    lowered = text.lower()
    if "activate_project" in lowered or "project" in lowered or "workspace_root" in lowered:
        hints.add("scope_changing")
    if "catalog" in lowered:
        hints.add("catalog_admin")
    if "trust" in lowered:
        hints.add("trust")
    if "token" in lowered:
        hints.add("token")
    if "secret" in lowered or "credential" in lowered:
        hints.add("secret_value")
    if "network_exposure" in lowered or "remote_exposure" in lowered or "expose_remote" in lowered:
        hints.add("remote_exposure")
    return hints


def _normalize_risk(value: str) -> str:
    return _normalize_token(value).replace("-", "_")


def _normalize_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")


def _schema_risk_class(risk: str) -> str:
    return RISK_CLASS_SCHEMA_MAP.get(risk, risk if risk in SCHEMA_RISK_CLASSES else "unknown")


def _tool_sort_key(tool: Mapping[str, Any]) -> tuple[str, str, str]:
    return (_tool_id(tool) or "", _tool_name(tool, "original_name") or "", _tool_name(tool, "exposed_name") or "")


def _reason(reason_type: str, message: str) -> dict[str, str]:
    return {"type": reason_type, "message": message}


def _blocker(blocker_type: str, message: str, *, tool_id: str | None = None) -> dict[str, Any]:
    blocker = {"type": blocker_type, "message": message}
    if tool_id is not None:
        blocker["tool_id"] = tool_id
    return blocker


def _dedupe_blockers(blockers: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for blocker in blockers:
        key = stable_digest(blocker)
        if key not in seen:
            seen.add(key)
            deduped.append(copy.deepcopy(dict(blocker)))
    return deduped


def _open_items(service_binding: str, target_client: str, blockers: Sequence[Mapping[str, Any]], created_at: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for blocker in _dedupe_blockers(blockers):
        items.append(
            {
                "id": _open_item_id(service_binding, target_client, blocker),
                "type": "tool_policy",
                "severity": "blocking",
                "created_at": created_at,
                "detail": blocker,
            }
        )
    return items


def _open_item_id(service_binding: str, target_client: str, blocker: Mapping[str, Any]) -> str:
    digest = stable_digest({"service_binding": service_binding, "target_client": target_client, "blocker": blocker})[7:19]
    return f"tool-policy-{digest}"


def _policy_id(payload: Mapping[str, Any]) -> str:
    return f"policy-{stable_digest(payload)[7:19]}"


def _placeholder_ref() -> dict[str, str | None]:
    return {
        "ref": "contextforge://control-plane/consent-receipts/missing",
        "content_digest": "sha256:" + "0" * 64,
        "catalog_revision_or_etag": None,
        "resolved_at": "1970-01-01T00:00:00Z",
    }


def _json_compatible_copy(value: Any) -> Any:
    return json.loads(json.dumps(value, sort_keys=True, default=str))
