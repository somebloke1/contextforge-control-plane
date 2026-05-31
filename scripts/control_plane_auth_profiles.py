#!/usr/bin/env python3
"""Pure auth-profile checks for ContextForge control-plane workflows."""

from __future__ import annotations

import copy
import ipaddress
import re
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

import control_plane_authorization as authorization
import control_plane_redaction as redaction


ACTIVE_AUTH_PROFILE = "loopback_authenticated_http"
REMOTE_AUTH_PROFILE = "remote_ready"
TOKEN_MATERIAL_CONSENT_CLASS = "token_material_change"
NETWORK_EXPOSURE_CONSENT_CLASS = "network_exposure_change"
REDACTED_MARKER = "<redacted>"

AUTH_STRENGTH_ORDER = authorization.AUTH_STRENGTH_ORDER
LOCAL_BIND_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "[::1]"})
WILDCARD_BIND_HOSTS = frozenset({"", "*", "0.0.0.0", "::", "[::]"})
TOKEN_LIFECYCLE_ACTIONS = frozenset({"create", "creation", "rotate", "rotation", "revoke", "revocation"})
TOKEN_STATES_REQUIRING_FRESH_APPROVAL = frozenset({"failed", "failure", "stale", "revoked"})
REQUIRED_TOKEN_REDACTION_SURFACES = (
    "plan_payloads",
    "project_state",
    "audit_records",
    "diagnostics",
    "catalog_output",
    "normal_logs",
    "command_arguments",
)
SAFE_TOKEN_METADATA_KEYS = frozenset(
    {
        "auth_profile",
        "credential_scope",
        "lifecycle_state",
        "redaction_status",
        "source_client_auth_strength",
        "token_file",
        "token_path",
        "token_source",
        "token_source_class",
        "token_source_constraints",
        "token_storage_class",
    }
)
DEFAULT_APPROVED_CONTROL_WORKFLOWS = frozenset(
    {
        "approve_plan",
        "apply_approved_project_local_plan",
        "local_assistant_token_lifecycle",
        "propose_project_init",
        "read_control_plane_status",
        "read_only_inspection",
        "verify_project_binding",
    }
)
FORBIDDEN_LOCAL_TOKEN_OPERATION_CLASSES = frozenset(
    {
        "raw_admin",
        "admin",
        "catalog_admin",
        "catalog_crud",
        "catalog_create",
        "catalog_delete",
        "catalog_update",
        "token_admin",
        "token_create",
        "token_delete",
        "token_rotate",
        "token_revoke",
        "unapproved_apply",
        "service_management_mutation",
        "secret_value_write",
        "network_exposure_change",
        "remote_exposure",
        "remote_only_workflow",
        "trust_write",
        "user_global_config_write",
    }
)
REQUIRED_LOCAL_TOKEN_DENIAL_CATEGORIES = {
    "raw_admin": frozenset({"raw_admin", "admin"}),
    "catalog_crud": frozenset({"catalog_admin", "catalog_create", "catalog_crud", "catalog_delete", "catalog_update"}),
    "token_admin": frozenset({"token_admin", "token_create", "token_delete", "token_revoke", "token_rotate"}),
    "unapproved_apply": frozenset({"unapproved_apply"}),
    "service_management_mutation": frozenset({"service_management_mutation"}),
    "remote_only_workflow": frozenset({"remote_exposure", "remote_only_workflow"}),
    "unrelated_virtual_server": frozenset(),
}


class AuthProfileError(ValueError):
    """Raised when a caller supplies an invalid auth-profile check request."""


def active_auth_profile() -> dict[str, Any]:
    """Return the active v1 auth-profile contract without secret material."""

    return {
        "auth_profile": ACTIVE_AUTH_PROFILE,
        "bind_default": "loopback",
        "client_auth": "bearer_http",
        "assistant_token": {
            "admin": False,
            "required_auth_strength_for_token_material_change": "per_client_token",
            "allowed_use": "approved virtual-server and control-plane workflow surfaces",
        },
        "remote_exposure": {
            "default": "disabled",
            "required_consent_class": NETWORK_EXPOSURE_CONSENT_CLASS,
            "must_use_separate_token_material": True,
        },
        "redaction_status": "redacted",
    }


def validate_loopback_bind_observations(
    bind_observations: Iterable[Mapping[str, Any]],
    *,
    auth_profile: str = ACTIVE_AUTH_PROFILE,
) -> dict[str, Any]:
    """Validate that local profile bind probes prove loopback-only exposure."""

    reasons: list[str] = []
    observations: list[dict[str, Any]] = []
    loopback_count = 0
    non_loopback_count = 0
    unauthenticated_count = 0

    if auth_profile != ACTIVE_AUTH_PROFILE:
        reasons.append(f"unsupported active auth profile: {auth_profile}")

    for index, item in enumerate(bind_observations):
        observation = _bind_observation(item, index=index)
        observations.append(observation)
        if observation["classification"] == "loopback":
            loopback_count += 1
        else:
            non_loopback_count += 1
            reasons.append(
                f"bind {observation['bind']} is {observation['classification']} and requires "
                f"{NETWORK_EXPOSURE_CONSENT_CLASS}"
            )
        if observation["http_requires_bearer"] is not True:
            unauthenticated_count += 1
            reasons.append(f"bind {observation['bind']} does not prove authenticated bearer HTTP")

    if not observations:
        reasons.append("missing bind-address observations")
    if loopback_count == 0:
        reasons.append("no loopback bind was observed")

    local_success = bool(observations) and loopback_count > 0 and non_loopback_count == 0 and unauthenticated_count == 0
    return _decision(
        "allow" if local_success and not reasons else "block",
        reasons,
        auth_profile=auth_profile,
        local_success=local_success,
        network_exposure_workflow_required=non_loopback_count > 0,
        required_remote_consent_class=NETWORK_EXPOSURE_CONSENT_CLASS if non_loopback_count else None,
        observed_binds=observations,
    )


def validate_local_assistant_token_profile(
    token_profile: Mapping[str, Any],
    *,
    approved_virtual_servers: Iterable[str],
    approved_control_workflows: Iterable[str] = DEFAULT_APPROVED_CONTROL_WORKFLOWS,
) -> dict[str, Any]:
    """Check that the local assistant token is non-admin and least privilege."""

    reasons: list[str] = []
    approved_servers = set(_strings(approved_virtual_servers))
    approved_workflows = set(_strings(approved_control_workflows))
    allowed_servers = set(_strings(_first_present(token_profile, "allowed_virtual_servers", "virtual_servers", default=())))
    allowed_workflows = set(_strings(_first_present(token_profile, "allowed_workflows", "control_workflows", default=())))
    allowed_operations = set(_strings(_first_present(token_profile, "allowed_operations", "scopes", "permissions", default=())))
    denied_operations = set(_strings(_first_present(token_profile, "denied_operations", "negative_operations", default=())))

    if bool(token_profile.get("admin") or token_profile.get("is_admin") or token_profile.get("raw_admin")):
        reasons.append("local assistant token must be non-admin")
    if not allowed_servers:
        reasons.append("local assistant token must name approved virtual-server access")
    if not allowed_workflows:
        reasons.append("local assistant token must name approved control workflow access")
    unapproved_servers = sorted(allowed_servers - approved_servers)
    if unapproved_servers:
        reasons.append(f"unapproved virtual-server access: {', '.join(unapproved_servers)}")
    unapproved_workflows = sorted(allowed_workflows - approved_workflows)
    if unapproved_workflows:
        reasons.append(f"unapproved control workflow access: {', '.join(unapproved_workflows)}")

    forbidden_allowed = sorted(operation for operation in allowed_operations | allowed_workflows if _is_forbidden_local_token_operation(operation))
    for operation in forbidden_allowed:
        reasons.append(f"forbidden local assistant token permission: {operation}")

    negative_probe_results = []
    for probe in _probe_items(token_profile.get("negative_probes") or token_profile.get("negative_checks") or ()):
        operation = str(probe.get("operation") or probe.get("scope") or probe.get("workflow") or "")
        allowed = _probe_allowed(probe)
        required_denial = _is_forbidden_local_token_operation(operation) or _references_unapproved_virtual_server(operation, approved_servers)
        status = "passed" if required_denial and not allowed else "not_applicable"
        if required_denial and allowed:
            status = "failed"
            reasons.append(f"negative probe allowed forbidden operation: {operation}")
        negative_probe_results.append({"operation": operation, "status": status, "allowed": allowed})

    denial_evidence = set(denied_operations)
    denial_evidence.update(result["operation"] for result in negative_probe_results if result["status"] == "passed")
    missing_denials = [
        category
        for category in REQUIRED_LOCAL_TOKEN_DENIAL_CATEGORIES
        if not _has_denial_category_evidence(category, denial_evidence, approved_servers)
    ]
    if missing_denials:
        reasons.append("missing least-privilege denial evidence for: " + ", ".join(missing_denials))

    return _decision(
        "allow" if not reasons else "block",
        reasons,
        auth_profile=ACTIVE_AUTH_PROFILE,
        approved_virtual_servers=sorted(approved_servers),
        approved_control_workflows=sorted(approved_workflows),
        negative_probe_results=negative_probe_results,
    )


def validate_token_lifecycle_workflow(
    *,
    action: str,
    source_client_auth_strength: str,
    consent_receipts: Iterable[Mapping[str, Any]],
    redaction_surfaces: Mapping[str, Any],
    raw_token_materials: Iterable[str] = (),
    token_state: Mapping[str, Any] | None = None,
    plan: Mapping[str, Any] | None = None,
    actor: str | None = None,
    source_client: str | None = None,
    project_root: str | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Gate token creation, rotation, and revocation without mutating tokens."""

    reasons: list[str] = []
    normalized_action = _normalize_lifecycle_action(action)
    if normalized_action not in {"create", "rotate", "revoke"}:
        reasons.append(f"unsupported token lifecycle action: {action}")
    if not _auth_strength_at_least(source_client_auth_strength, "per_client_token"):
        reasons.append("token material workflows require per-client token auth strength")

    receipts = [dict(receipt) for receipt in consent_receipts]
    matching_receipts = [receipt for receipt in receipts if receipt.get("consent_class") == TOKEN_MATERIAL_CONSENT_CLASS]
    if not matching_receipts:
        reasons.append("missing token_material_change consent receipt")

    receipt_checks = [
        _validate_token_receipt(
            receipt,
            plan=plan,
            actor=actor,
            source_client=source_client,
            project_root=project_root,
            now=now,
        )
        for receipt in matching_receipts
    ]
    valid_receipts = [receipt for receipt, check in zip(matching_receipts, receipt_checks) if check["decision"] == "allow"]
    if matching_receipts and not valid_receipts:
        reasons.extend(f"receipt check: {reason}" for check in receipt_checks for reason in check["reasons"])

    state = token_state or {}
    state_name = str(state.get("state") or state.get("status") or "valid").lower()
    if state_name in TOKEN_STATES_REQUIRING_FRESH_APPROVAL and not _has_fresh_receipt(valid_receipts, state, now=now):
        reasons.append(f"fresh approval required after {state_name} token state")

    redaction_check = verify_token_redaction_surfaces(redaction_surfaces, raw_token_materials=raw_token_materials)
    if redaction_check["decision"] != "allow":
        reasons.extend(f"redaction check: {reason}" for reason in redaction_check["reasons"])

    return _decision(
        "allow" if not reasons else "block",
        reasons,
        action=normalized_action,
        required_consent_class=TOKEN_MATERIAL_CONSENT_CLASS,
        observed_token_material_receipts=len(valid_receipts),
        source_client_auth_strength=source_client_auth_strength,
        redaction=redaction_check,
    )


def verify_token_redaction_surfaces(
    surfaces: Mapping[str, Any],
    *,
    raw_token_materials: Iterable[str] = (),
    required_surfaces: Sequence[str] = REQUIRED_TOKEN_REDACTION_SURFACES,
) -> dict[str, Any]:
    """Prove token material is absent from all required redacted surfaces."""

    reasons: list[str] = []
    surface_results: dict[str, dict[str, Any]] = {}
    raw_values = tuple(value for value in raw_token_materials if value)
    for surface_name in required_surfaces:
        if surface_name not in surfaces:
            reasons.append(f"missing redaction surface: {surface_name}")
            surface_results[surface_name] = {"status": "missing"}
            continue
        surface = surfaces[surface_name]
        leaks = _token_material_leaks(surface, raw_values=raw_values)
        status = "passed" if not leaks else "failed"
        surface_results[surface_name] = {"status": status, "leaks": leaks}
        for leak in leaks:
            reasons.append(f"{surface_name} leaks token material at {leak['path']}: {leak['reason']}")

    return _decision(
        "allow" if not reasons else "block",
        reasons,
        required_surfaces=list(required_surfaces),
        surface_results=surface_results,
        raw_token_material_values_checked=len(raw_values),
    )


def classify_auth_boundary_observation(observation: Mapping[str, Any]) -> dict[str, Any]:
    """Distinguish ContextForge client auth from downstream credentials."""

    reasons: list[str] = []
    blocking_items: list[dict[str, Any]] = []
    contextforge = observation.get("contextforge_client_auth")
    downstream = observation.get("downstream_credentials") or observation.get("downstream_service_credentials")

    if isinstance(contextforge, Mapping) and str(contextforge.get("status") or "").lower() in {"failed", "missing", "denied"}:
        reasons.append("ContextForge client auth failed")
        blocking_items.append(
            {
                "type": "auth",
                "domain": "contextforge_client_auth",
                "classification": "contextforge_client_auth_failed",
                "required_action": "repair local ContextForge client token or auth profile",
            }
        )

    missing_secret_names = _missing_downstream_secret_names(downstream)
    if missing_secret_names:
        reasons.append("downstream service credentials are missing")
        blocking_items.append(
            {
                "type": "secret",
                "domain": "downstream_service_credentials",
                "classification": "downstream_missing_secret",
                "secret_names": missing_secret_names,
                "required_action": "separate secret-entry workflow",
            }
        )

    if isinstance(downstream, Mapping) and str(downstream.get("status") or "").lower() in {"failed", "denied"} and not missing_secret_names:
        reasons.append("downstream service credential check failed")
        blocking_items.append(
            {
                "type": "secret",
                "domain": "downstream_service_credentials",
                "classification": "downstream_credential_failed",
                "required_action": "verify downstream credential scope without exposing values",
            }
        )

    return _decision(
        "allow" if not reasons else "block",
        reasons,
        blocking_items=blocking_items,
        contextforge_client_auth_distinct_from_downstream_credentials=True,
    )


def _bind_observation(item: Mapping[str, Any], *, index: int) -> dict[str, Any]:
    raw_bind = str(item.get("bind") or item.get("bind_address") or item.get("address") or item.get("url") or "")
    host = _host_from_bind(raw_bind, item)
    classification = _classify_bind_host(host)
    requires_bearer = _http_requires_bearer(item)
    return {
        "index": index,
        "bind": raw_bind or host or "<missing>",
        "host": host,
        "port": item.get("port"),
        "transport": item.get("transport") or item.get("scheme") or _scheme_from_bind(raw_bind),
        "classification": classification,
        "http_requires_bearer": requires_bearer,
    }


def _host_from_bind(raw_bind: str, item: Mapping[str, Any]) -> str:
    for key in ("host", "hostname", "listen_host", "bind_host"):
        if item.get(key) is not None:
            return _normalize_host(str(item[key]))
    if "://" in raw_bind:
        split = urlsplit(raw_bind)
        return _normalize_host(split.hostname or "")
    if raw_bind.startswith("[") and "]" in raw_bind:
        return _normalize_host(raw_bind[1 : raw_bind.index("]")])
    if raw_bind.count(":") == 1 and not raw_bind.startswith(":"):
        return _normalize_host(raw_bind.rsplit(":", 1)[0])
    return _normalize_host(raw_bind)


def _scheme_from_bind(raw_bind: str) -> str | None:
    if "://" not in raw_bind:
        return None
    return urlsplit(raw_bind).scheme


def _normalize_host(host: str) -> str:
    value = host.strip().lower()
    if value.startswith("[") and value.endswith("]"):
        return value[1:-1]
    return value


def _classify_bind_host(host: str) -> str:
    if host in LOCAL_BIND_HOSTS:
        return "loopback"
    if host in WILDCARD_BIND_HOSTS:
        return "wildcard"
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return "non_loopback"
    if address.is_loopback:
        return "loopback"
    if address.is_unspecified:
        return "wildcard"
    return "non_loopback"


def _http_requires_bearer(item: Mapping[str, Any]) -> bool | None:
    auth = item.get("http_requires_bearer", item.get("bearer_required", item.get("requires_bearer")))
    if auth is not None:
        return bool(auth)
    auth_scheme = str(item.get("auth_scheme") or item.get("authentication") or item.get("auth") or "").lower()
    if auth_scheme in {"bearer", "bearer_http", "authenticated_http"}:
        return True
    if auth_scheme in {"none", "disabled", "anonymous", "unauthenticated"}:
        return False
    return None


def _normalize_lifecycle_action(action: str) -> str:
    normalized = str(action).strip().lower()
    if normalized == "creation":
        return "create"
    if normalized == "rotation":
        return "rotate"
    if normalized == "revocation":
        return "revoke"
    return normalized


def _validate_token_receipt(
    receipt: Mapping[str, Any],
    *,
    plan: Mapping[str, Any] | None,
    actor: str | None,
    source_client: str | None,
    project_root: str | None,
    now: str | None,
) -> dict[str, Any]:
    reasons: list[str] = []
    if receipt.get("consent_class") != TOKEN_MATERIAL_CONSENT_CLASS:
        reasons.append("receipt consent class is not token_material_change")
    if not _auth_strength_at_least(str(receipt.get("source_client_auth_strength") or ""), "per_client_token"):
        reasons.append("receipt source-client auth strength is insufficient")
    if plan is not None:
        check = authorization.validate_consent_receipt(
            receipt,
            plan=plan,
            operation_class=TOKEN_MATERIAL_CONSENT_CLASS,
            actor=actor,
            source_client=source_client,
            source_client_auth_strength="per_client_token",
            project_root=project_root,
            persistent_target="token-store",
            replay_intent="initial_apply",
            now=now,
        )
        reasons.extend(check["reasons"])
    else:
        expires_at = receipt.get("expires_at")
        if expires_at and _parse_timestamp(str(expires_at)) <= _parse_timestamp(now or _now_timestamp()):
            reasons.append("receipt has expired")
    return _decision("allow" if not reasons else "block", reasons)


def _has_fresh_receipt(receipts: Sequence[Mapping[str, Any]], token_state: Mapping[str, Any], *, now: str | None) -> bool:
    observed_at = (
        token_state.get("observed_at")
        or token_state.get("failed_at")
        or token_state.get("stale_at")
        or token_state.get("revoked_at")
    )
    if not observed_at:
        return False
    try:
        observed = _parse_timestamp(str(observed_at))
    except ValueError:
        return False
    for receipt in receipts:
        approved_at = receipt.get("approved_at")
        if not approved_at:
            continue
        try:
            if _parse_timestamp(str(approved_at)) > observed and (
                not now or _parse_timestamp(str(approved_at)) <= _parse_timestamp(now)
            ):
                return True
        except ValueError:
            continue
    return False


def _token_material_leaks(value: Any, *, raw_values: Sequence[str]) -> list[dict[str, str]]:
    leaks: list[dict[str, str]] = []
    for path, child in _walk(value):
        key = path[-1] if path else ""
        path_text = redaction.format_path(path)
        if isinstance(child, str):
            for raw in raw_values:
                if raw and raw in child:
                    leaks.append({"path": path_text, "reason": "raw token material"})
            if redaction.classify_sensitive_value(child):
                leaks.append({"path": path_text, "reason": "secret-shaped token material"})
        if key not in SAFE_TOKEN_METADATA_KEYS and redaction.classify_sensitive_key(key) and _unsafe_sensitive_surface_value(child):
            leaks.append({"path": path_text, "reason": "sensitive token field is not redacted"})
    return leaks


def _unsafe_sensitive_surface_value(value: Any) -> bool:
    if value is None or isinstance(value, bool | int | float):
        return False
    if isinstance(value, str):
        return not redaction.is_safe_placeholder(value)
    if isinstance(value, Mapping):
        return not (value.get("redacted") is True or value.get("redaction_status") in {"redacted", "passed"})
    if isinstance(value, list):
        return any(_unsafe_sensitive_surface_value(item) for item in value)
    return True


def _missing_downstream_secret_names(downstream: Any) -> list[str]:
    if not isinstance(downstream, Mapping):
        return []
    candidates = downstream.get("missing") or downstream.get("missing_secrets") or downstream.get("required_missing")
    if candidates is True:
        name = downstream.get("name") or downstream.get("secret_name") or "downstream credential"
        return [str(name)]
    return sorted(_strings(candidates or ()))


def _first_present(mapping: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in mapping:
            return mapping[key]
    return default


def _strings(values: Any) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        return [values]
    if isinstance(values, Mapping):
        return [str(key) for key, enabled in values.items() if enabled]
    if isinstance(values, Iterable):
        return [str(value) for value in values]
    return [str(values)]


def _probe_items(values: Any) -> list[Mapping[str, Any]]:
    if values is None:
        return []
    if isinstance(values, Mapping):
        return [values]
    if isinstance(values, Iterable) and not isinstance(values, str):
        return [value for value in values if isinstance(value, Mapping)]
    return []


def _probe_allowed(probe: Mapping[str, Any]) -> bool:
    if "allowed" in probe:
        return bool(probe["allowed"])
    status = str(probe.get("status") or probe.get("result") or "").lower()
    return status in {"allow", "allowed", "passed", "success", "200"}


def _is_forbidden_local_token_operation(operation: str) -> bool:
    normalized = _normalize_operation(operation)
    if normalized in FORBIDDEN_LOCAL_TOKEN_OPERATION_CLASSES:
        return True
    markers = (
        "admin",
        "catalog_crud",
        "catalog_create",
        "catalog_delete",
        "catalog_update",
        "token_admin",
        "unapproved_apply",
        "remote_only",
        "remote_exposure",
        "network_exposure",
        "secret_value",
        "service_management_mutation",
    )
    return any(marker in normalized for marker in markers)


def _has_denial_category_evidence(category: str, operations: set[str], approved_servers: set[str]) -> bool:
    if category == "unrelated_virtual_server":
        return any(_references_unapproved_virtual_server(operation, approved_servers) for operation in operations)
    aliases = REQUIRED_LOCAL_TOKEN_DENIAL_CATEGORIES[category]
    normalized_operations = {_normalize_operation(operation) for operation in operations}
    return bool(aliases & normalized_operations)


def _references_unapproved_virtual_server(operation: str, approved_servers: set[str]) -> bool:
    if not operation.startswith("virtual_server:"):
        return False
    parts = operation.split(":")
    return len(parts) >= 2 and parts[1] not in approved_servers


def _normalize_operation(operation: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", operation.strip().lower()).strip("_")


def _auth_strength_at_least(actual: str, minimum: str) -> bool:
    return AUTH_STRENGTH_ORDER.get(actual, -1) >= AUTH_STRENGTH_ORDER.get(minimum, 99)


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _now_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _walk(value: Any, path: tuple[str, ...] = ()) -> Iterable[tuple[tuple[str, ...], Any]]:
    yield path, value
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield from _walk(child, (*path, str(key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, (*path, str(index)))


def _decision(decision: str, reasons: Iterable[str], **metadata: Any) -> dict[str, Any]:
    result = {
        "decision": decision,
        "allowed": decision == "allow",
        "reasons": list(dict.fromkeys(str(reason) for reason in reasons)),
    }
    result.update(copy.deepcopy(metadata))
    return result
