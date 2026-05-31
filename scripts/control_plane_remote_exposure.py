#!/usr/bin/env python3
"""Pure remote-exposure planning gates for the ContextForge control plane."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


HELPER_VERSION = 1
LOCAL_DEFAULT_AUTH_PROFILE = "loopback_authenticated_http"
DORMANT_REMOTE_PROFILE = "remote_ready"
REMOTE_CONSENT_CLASS = "network_exposure_change"
SEPARATE_WORKFLOW_CONSENT_CLASSES = frozenset(
    {
        "project_state_write",
        "project_local_config_write",
        "catalog_promotion",
        "user_global_client_trust",
        "user_global_config_write",
        "secret_value_write",
        "token_material_change",
    }
)
REQUIRED_REVIEWS = frozenset(
    {
        "bind_address_review",
        "tls_material_review",
        "origin_policy",
        "scoped_token_review",
        "service_tool_allowlist",
        "excluded_service_tool_list",
        "rollback_instructions",
        "remote_probe_plan",
        "diagnostic_redaction",
    }
)
LOCAL_TOKEN_SOURCE_CLASSES = frozenset(
    {
        "local_shared_token",
        "shared_local_token",
        "shared_token",
        "wrapper_token",
        "wrapper_bound_token",
        "local_wrapper_token",
        "local_contextforge_client_token",
    }
)
FORBIDDEN_REMOTE_RISK_CLASSES = frozenset(
    {
        "admin",
        "catalog_admin",
        "catalog_crud",
        "control_plane_mutation",
        "raw_catalog_admin",
        "secret",
        "secret_value",
        "secret_value_workflow",
        "service_management_mutation",
        "scope_changing",
        "token",
        "token_material",
        "token_workflow",
        "trust",
        "trust_change",
        "user_global_trust",
    }
)
SCOPE_CHANGING_IMPACTS = frozenset(
    {
        "active_project",
        "backend_operating_scope",
        "backend_scope",
        "credential_scope",
        "network_exposure",
        "project_scope",
        "remote_exposure",
        "resource_scope",
        "workspace_root",
    }
)
SECRET_VALUE_RE = re.compile(
    r"(-----BEGIN [A-Z ]*PRIVATE KEY-----|"
    r"\bBearer\s+[A-Za-z0-9._~+/=-]{12,}|"
    r"\b(?:sk|pk|ghp|gho|github_pat|xox[baprs]|ya29)[_-][A-Za-z0-9._-]{12,}|"
    r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}|"
    r"(?i:\b(?:api[_-]?key|token|password|secret)\s*=\s*[^\\s'\"<>]+))"
)


class RemoteExposureInputError(ValueError):
    """Raised when a remote exposure helper receives malformed inputs."""


def build_remote_exposure_plan(
    *,
    project_root: str | Path,
    request_id: str,
    requested_profile: str = DORMANT_REMOTE_PROFILE,
    remote_exposure_requested: bool = False,
    bind_address: str | None = None,
    reviews: Mapping[str, Any] | None = None,
    remote_auth_profile: Mapping[str, Any] | None = None,
    service_allowlist: Sequence[Mapping[str, Any]] = (),
    excluded_services: Sequence[str] = (),
    excluded_tools: Sequence[str] = (),
    candidate_tools: Sequence[Mapping[str, Any]] = (),
    consent_receipt_refs: Sequence[Mapping[str, Any]] = (),
    rollback: Mapping[str, Any] | None = None,
    remote_probe_plan: Mapping[str, Any] | None = None,
    diagnostic_redaction: Mapping[str, Any] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build a non-mutating remote exposure plan with fail-closed gates."""

    if not request_id:
        raise RemoteExposureInputError("request_id is required")
    root = str(Path(project_root).expanduser().resolve(strict=False))
    timestamp = generated_at or now_timestamp()
    review_map = copy.deepcopy(dict(reviews or {}))
    normalized_allowlist = [_normalize_allowlist_entry(item) for item in service_allowlist]
    allowed_index = _allowlist_index(normalized_allowlist)
    tool_decisions = classify_remote_tool_exposure(candidate_tools, allowlist=normalized_allowlist)
    blockers = []

    if not remote_exposure_requested or requested_profile != DORMANT_REMOTE_PROFILE:
        blockers.append(_blocker("remote_exposure_non_default", "remote exposure is dormant and must be explicitly requested"))

    consent_check = validate_remote_consent(consent_receipt_refs)
    blockers.extend(consent_check["blockers"])
    blockers.extend(validate_required_reviews(review_map, bind_address=bind_address))
    blockers.extend(validate_remote_auth_profile(remote_auth_profile or {}))
    blockers.extend(validate_remote_plan_materials(
        rollback=rollback or {},
        remote_probe_plan=remote_probe_plan or {},
        diagnostic_redaction=diagnostic_redaction or {},
        service_allowlist=normalized_allowlist,
        excluded_services=excluded_services,
        excluded_tools=excluded_tools,
    ))
    blockers.extend(tool_decisions["blockers"])

    decision = "intend" if not blockers else "block"
    plan = {
        "schema_version": HELPER_VERSION,
        "plan_type": "remote_exposure",
        "request_id": request_id,
        "project_root": root,
        "active_local_auth_profile": LOCAL_DEFAULT_AUTH_PROFILE,
        "requested_remote_profile": requested_profile,
        "remote_profile_default": False,
        "status": "planned_non_mutating" if decision == "intend" else "blocked",
        "decision": decision,
        "eligible_for_remote_exposure": decision == "intend",
        "required_consent_class": REMOTE_CONSENT_CLASS,
        "separate_from_consent_classes": sorted(SEPARATE_WORKFLOW_CONSENT_CLASSES),
        "consent_receipt_refs": _json_compatible_copy(list(consent_receipt_refs)),
        "bind_address": bind_address,
        "reviews": review_map,
        "remote_auth_profile": _redacted_auth_profile(remote_auth_profile or {}),
        "service_allowlist": normalized_allowlist,
        "excluded_services": sorted(str(item) for item in excluded_services),
        "excluded_tools": sorted(str(item) for item in excluded_tools),
        "tool_exposure": tool_decisions["tool_exposure"],
        "negative_exposure_checks": tool_decisions["negative_exposure_checks"],
        "rollback": _json_compatible_copy(dict(rollback or {})),
        "remote_probe_plan": _json_compatible_copy(dict(remote_probe_plan or {})),
        "diagnostic_redaction": _json_compatible_copy(dict(diagnostic_redaction or {})),
        "blockers": _dedupe_blockers(blockers),
        "open_items": _open_items(request_id, blockers, timestamp),
        "local_state_reference": local_state_remote_reference(decision=decision, request_id=request_id),
        "mutation_performed": False,
        "generated_at": timestamp,
    }
    plan["plan_digest"] = stable_digest({key: value for key, value in plan.items() if key != "plan_digest"})
    _assert_no_secret_values(plan)
    return plan


def validate_remote_consent(consent_receipt_refs: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Require explicit network exposure approval, not neighboring consent classes."""

    classes = {str(ref.get("x_consent_class") or ref.get("consent_class") or "") for ref in consent_receipt_refs}
    blockers = []
    if REMOTE_CONSENT_CLASS not in classes:
        blockers.append(_blocker("missing_network_exposure_approval", "remote exposure requires explicit network_exposure_change approval"))
    substituted = sorted(classes & SEPARATE_WORKFLOW_CONSENT_CLASSES)
    if substituted:
        blockers.append(
            _blocker(
                "approval_class_not_substitutable",
                "project-local, catalog, global-trust, token, or secret approvals cannot be bundled with remote exposure",
                consent_classes=substituted,
            )
        )
    return {"decision": "allow" if not blockers else "block", "blockers": blockers, "observed_consent_classes": sorted(classes)}


def validate_required_reviews(reviews: Mapping[str, Any], *, bind_address: str | None) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for review_name in sorted(REQUIRED_REVIEWS):
        if not _review_passed(reviews.get(review_name)):
            blockers.append(_blocker(f"missing_{review_name}", f"remote exposure requires {review_name}"))
    if not bind_address:
        blockers.append(_blocker("missing_bind_address", "remote exposure requires an explicit reviewed bind address"))
    origin_policy = reviews.get("origin_policy")
    if isinstance(origin_policy, Mapping) and "*" in {str(item) for item in _list(origin_policy.get("allowed_origins"))}:
        blockers.append(_blocker("origin_policy_too_broad", "remote exposure origin policy cannot use wildcard origins"))
    return blockers


def validate_remote_auth_profile(remote_auth_profile: Mapping[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    source_class = _normalize_token(remote_auth_profile.get("token_source_class") or remote_auth_profile.get("source_class"))
    profile_type = _normalize_token(remote_auth_profile.get("profile_type") or remote_auth_profile.get("token_profile_type"))
    if not remote_auth_profile:
        return [_blocker("missing_remote_auth_profile", "remote exposure requires a separate remote token profile")]
    if source_class in LOCAL_TOKEN_SOURCE_CLASSES:
        blockers.append(_blocker("local_token_reuse_rejected", "local shared or wrapper token material cannot be reused for remote exposure"))
    if profile_type != "remote":
        blockers.append(_blocker("missing_remote_token_profile", "remote exposure requires token material labeled as a remote profile"))
    if not bool(remote_auth_profile.get("separate_from_local")):
        blockers.append(_blocker("remote_token_not_separate", "remote token profile must be separate from local assistant and wrapper tokens"))
    if not remote_auth_profile.get("scope"):
        blockers.append(_blocker("missing_scoped_token_review", "remote token profile must name scoped service/tool authority"))
    if not remote_auth_profile.get("revocation_plan"):
        blockers.append(_blocker("missing_revocation_plan", "remote token profile must include revocation instructions"))
    return blockers


def validate_remote_plan_materials(
    *,
    rollback: Mapping[str, Any],
    remote_probe_plan: Mapping[str, Any],
    diagnostic_redaction: Mapping[str, Any],
    service_allowlist: Sequence[Mapping[str, Any]],
    excluded_services: Sequence[str],
    excluded_tools: Sequence[str],
) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    if not service_allowlist:
        blockers.append(_blocker("missing_service_tool_allowlist", "remote exposure requires an explicit service/tool allowlist"))
    if not excluded_services and not excluded_tools:
        blockers.append(_blocker("missing_excluded_service_tool_list", "remote exposure requires explicit excluded services or tools"))
    if not rollback.get("instructions") or not rollback.get("revocation_steps"):
        blockers.append(_blocker("missing_rollback_instructions", "remote exposure requires rollback and token revocation steps"))
    if not remote_probe_plan.get("external_or_remote_probe") or not remote_probe_plan.get("negative_probe"):
        blockers.append(_blocker("missing_remote_probe_plan", "remote exposure requires external/remote positive and negative probes"))
    if diagnostic_redaction.get("status") not in {"passed", "redacted"}:
        blockers.append(_blocker("missing_diagnostic_redaction", "remote exposure requires diagnostic redaction proof"))
    return blockers


def classify_remote_tool_exposure(
    tools: Sequence[Mapping[str, Any]],
    *,
    allowlist: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Classify remote tool exposure and emit negative checks for denied items."""

    allowed_index = _allowlist_index(allowlist)
    tool_records: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    negative_checks: list[dict[str, Any]] = []

    for tool in sorted((_json_compatible_copy(dict(item)) for item in tools), key=_tool_sort_key):
        service_binding = str(tool.get("service_binding") or "")
        tool_id = str(tool.get("tool_id") or tool.get("id") or tool.get("name") or "<unknown>")
        risk_classes = {_normalize_token(item) for item in _list(tool.get("risk_classes") or tool.get("risk_class"))}
        scope_impacts = {_normalize_token(item) for item in _list(tool.get("scope_impacts") or tool.get("scope_impact"))}
        allowed_tools = allowed_index.get(service_binding, set())
        reasons: list[dict[str, str]] = []

        if service_binding not in allowed_index:
            reasons.append(_reason("non_allowlisted_service_denied", "service is not in the remote exposure allowlist"))
        if "*" in allowed_tools:
            reasons.append(_reason("wildcard_remote_allowlist_denied", "remote exposure requires exact tool allowlists"))
        elif tool_id not in allowed_tools:
            reasons.append(_reason("non_allowlisted_tool_denied", "tool is not in the remote exposure allowlist"))
        for risk in sorted(risk_classes & FORBIDDEN_REMOTE_RISK_CLASSES):
            reasons.append(_reason(f"{risk}_denied", f"remote exposure denies {risk} tools by default"))
        if risk_classes & {"scope_changing"} or scope_impacts & SCOPE_CHANGING_IMPACTS:
            reasons.append(_reason("scope_changing_tool_denied", "remote exposure denies scope-changing tools by default"))
        if service_binding.startswith("serena") and ("*" in allowed_tools or tool.get("exposure_scope") in {"broad", "global", "workspace"}):
            reasons.append(_reason("broad_serena_exposure_denied", "project-scoped Serena exposure cannot be made broad remote surface"))

        decision = "deny" if reasons else "allow"
        record = {
            "service_binding": service_binding,
            "tool_id": tool_id,
            "name": tool.get("name") or tool_id,
            "decision": decision,
            "risk_classes": sorted(risk_classes),
            "scope_impacts": sorted(scope_impacts),
            "reasons": reasons,
        }
        tool_records.append(record)
        if reasons:
            for reason in reasons:
                blockers.append(_blocker(reason["type"], reason["message"], service_binding=service_binding, tool_id=tool_id))
            negative_checks.extend(_negative_checks_for_denied_tool(record))
        else:
            negative_checks.append(
                {
                    "check": "remote_allowlisted_tool_exact_match",
                    "service_binding": service_binding,
                    "tool_id": tool_id,
                    "expected": "present",
                    "status": "pending",
                }
            )

    return {
        "decision": "allow" if not blockers else "block",
        "tool_exposure": tool_records,
        "negative_exposure_checks": negative_checks,
        "blockers": _dedupe_blockers(blockers),
    }


def local_state_remote_reference(*, decision: str, request_id: str) -> dict[str, Any]:
    """Return the only remote marker normal local state should carry."""

    return {
        "active_auth_profile": LOCAL_DEFAULT_AUTH_PROFILE,
        "remote_exposure_default": False,
        "remote_profile": DORMANT_REMOTE_PROFILE,
        "remote_status": "separate_profile_approved" if decision == "intend" else "separate_open_item",
        "remote_request_ref": request_id,
        "local_verification_role": "not_default_local_verification",
    }


def now_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stable_digest(value: Any) -> str:
    encoded = json.dumps(_json_compatible_copy(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _normalize_allowlist_entry(item: Mapping[str, Any]) -> dict[str, Any]:
    service_binding = str(item.get("service_binding") or "")
    if not service_binding:
        raise RemoteExposureInputError("allowlist entries require service_binding")
    tool_ids = sorted(str(tool) for tool in _list(item.get("tool_ids") or item.get("tools")))
    return {
        "service_binding": service_binding,
        "tool_ids": tool_ids,
        "reviewed": bool(item.get("reviewed", True)),
        "remote_eligible": bool(item.get("remote_eligible", True)),
        "rationale": str(item.get("rationale") or "reviewed remote allowlist entry"),
    }


def _allowlist_index(allowlist: Sequence[Mapping[str, Any]]) -> dict[str, set[str]]:
    return {str(item["service_binding"]): {str(tool) for tool in item.get("tool_ids", [])} for item in allowlist}


def _negative_checks_for_denied_tool(record: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "check": "remote_denied_tool_absent",
            "layer": layer,
            "probe": probe,
            "service_binding": record["service_binding"],
            "tool_id": record["tool_id"],
            "negative_match_names": sorted({str(record["tool_id"]), str(record.get("name") or record["tool_id"])}),
            "expected": "absent",
            "status": "pending",
            "denial_reasons": [reason["type"] for reason in record.get("reasons", [])],
        }
        for layer, probe in (
            ("remote_contextforge_virtual_server", "readback_remote_server_tools"),
            ("remote_client", "list_tools_and_call_tool"),
        )
    ]


def _redacted_auth_profile(profile: Mapping[str, Any]) -> dict[str, Any]:
    redacted = _json_compatible_copy(dict(profile))
    for key in list(redacted):
        if "value" in str(key).lower() or "material" in str(key).lower():
            redacted[key] = "<redacted>"
    return redacted


def _review_passed(value: Any) -> bool:
    if value is True:
        return True
    if isinstance(value, Mapping):
        return value.get("status") in {"approved", "passed", "reviewed"} or value.get("reviewed") is True
    return False


def _list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Iterable):
        return list(value)
    return [value]


def _tool_sort_key(tool: Mapping[str, Any]) -> tuple[str, str]:
    return (str(tool.get("service_binding") or ""), str(tool.get("tool_id") or tool.get("name") or ""))


def _reason(reason_type: str, message: str) -> dict[str, str]:
    return {"type": reason_type, "message": message}


def _blocker(blocker_type: str, message: str, **metadata: Any) -> dict[str, Any]:
    blocker = {"type": blocker_type, "message": message}
    blocker.update({key: value for key, value in metadata.items() if value is not None})
    return blocker


def _open_items(request_id: str, blockers: Sequence[Mapping[str, Any]], created_at: str) -> list[dict[str, Any]]:
    return [
        {
            "id": f"remote-exposure-{stable_digest({'request_id': request_id, 'blocker': blocker})[7:19]}",
            "type": "remote_exposure",
            "severity": "blocking",
            "created_at": created_at,
            "detail": _json_compatible_copy(dict(blocker)),
        }
        for blocker in _dedupe_blockers(blockers)
    ]


def _dedupe_blockers(blockers: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for blocker in blockers:
        digest = stable_digest(blocker)
        if digest not in seen:
            seen.add(digest)
            deduped.append(_json_compatible_copy(dict(blocker)))
    return deduped


def _assert_no_secret_values(value: Any) -> None:
    for path, item in _walk(value):
        if isinstance(item, str) and SECRET_VALUE_RE.search(item):
            raise RemoteExposureInputError(f"remote exposure plan contains unredacted secret-like value: {'.'.join(path)}")


def _walk(value: Any, path: tuple[str, ...] = ()) -> Iterable[tuple[tuple[str, ...], Any]]:
    yield path, value
    if isinstance(value, Mapping):
        for key, item in value.items():
            yield from _walk(item, (*path, str(key)))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk(item, (*path, str(index)))


def _normalize_token(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")


def _json_compatible_copy(value: Any) -> Any:
    return json.loads(json.dumps(value, sort_keys=True, default=str))
