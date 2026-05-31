#!/usr/bin/env python3
"""Pure wrapper auth helpers for ContextForge control-plane evidence.

The helpers in this module only evaluate caller-supplied snapshots.  They do
not read token files, inspect live processes, call ContextForge, or mutate any
client/runtime state.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from pathlib import PurePath
from typing import Any

import control_plane_redaction as redaction


HELPER_VERSION = 1
DEFAULT_AUTH_PROFILE = "loopback_authenticated_http"
REDACTED_MARKER = "<redacted>"

ALLOWED_TOKEN_SOURCE_CLASSES = frozenset(
    {
        "restrictive_local_token_file",
        "contextforge_token_provider_api",
        "wrapper_bound_brokered_token",
        "approved_remote_token_store",
    }
)
TOKEN_SOURCE_CLASS_ALIASES = {
    "local_token_file": "restrictive_local_token_file",
    "restrictive local token file": "restrictive_local_token_file",
    "contextforge_token_provider": "contextforge_token_provider_api",
    "contextforge token provider api": "contextforge_token_provider_api",
    "wrapper_broker": "wrapper_bound_brokered_token",
    "wrapper-bound brokered token": "wrapper_bound_brokered_token",
    "remote_token_store": "approved_remote_token_store",
    "approved remote-token store": "approved_remote_token_store",
}
INHERITED_ENV_SOURCE_CLASSES = frozenset(
    {
        "environment_variable",
        "inherited_environment",
        "long_lived_inherited_environment",
        "rfc_approved_inherited_environment",
    }
)
REVOKED_OR_STALE_STATES = frozenset({"revoked", "stale", "expired", "unknown_revocation_state"})
REMOTE_BINDING_SCOPES = frozenset({"remote", "remote_ready", "experimental_remote"})
SAFE_METADATA_KEYS = redaction.SAFE_METADATA_KEYS | frozenset(
    {
        "token_source_class",
        "source_class",
        "source_id",
        "path_class",
        "storage_class",
        "provider_class",
        "provider_endpoint_class",
        "broker_binding_class",
        "remote_store_class",
        "file_mode_octal",
        "cached_token_state",
        "revocation_status",
        "token_profile",
    }
)
LEAK_SURFACES = (
    "argv",
    "process_title_snapshot",
    "stdout",
    "stderr",
    "shell_trace",
    "wrapper_logs",
    "diagnostics",
    "audit_excerpts",
    "project_state",
    "catalog_output",
    "child_environment_snapshot",
)
SURFACE_ALIASES = {
    "command_args": "argv",
    "process_title": "process_title_snapshot",
    "logs": "wrapper_logs",
    "audit": "audit_excerpts",
    "catalog": "catalog_output",
    "child_env": "child_environment_snapshot",
    "child_environment": "child_environment_snapshot",
}
SECRET_VALUE_RE = re.compile(
    r"(-----BEGIN [A-Z ]*PRIVATE KEY-----|"
    r"\bBearer\s+[A-Za-z0-9._~+/=-]{8,}|"
    r"\b(?:sk|pk|ghp|gho|github_pat|xox[baprs]|ya29)[_-][A-Za-z0-9._-]{8,}|"
    r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}|"
    r"(?i:\b(?:api[_-]?key|auth[_-]?token|token|password|secret)\s*=\s*[^\\s'\"<>]+))"
)


class WrapperAuthEvidenceError(ValueError):
    """Raised when wrapper auth evidence is not JSON-compatible."""


def evaluate_wrapper_auth_security(
    *,
    token_source: Mapping[str, Any],
    wrapper_command: Mapping[str, Any] | Sequence[Any] | None = None,
    leak_evidence: Mapping[str, Any] | None = None,
    auth_profile: str = DEFAULT_AUTH_PROFILE,
    binding_scope: str = "local",
    raw_token_markers: Iterable[str] = (),
) -> dict[str, Any]:
    """Evaluate token-source and wrapper leak evidence as a redacted trace."""

    markers = tuple(str(marker) for marker in raw_token_markers if marker)
    source_decision = evaluate_token_source(
        token_source,
        auth_profile=auth_profile,
        binding_scope=binding_scope,
    )
    command_snapshot = build_wrapper_command_snapshot(
        wrapper_command or {},
        token_source_metadata=source_decision["metadata"],
        raw_token_markers=markers,
    )
    leak_decision = evaluate_wrapper_leak_checks(
        leak_evidence or {},
        raw_token_markers=markers,
    )
    blockers = list(source_decision["blockers"]) + list(command_snapshot["blockers"]) + list(leak_decision["blockers"])
    trace = {
        "helper": "control_plane_auth_wrappers",
        "helper_version": HELPER_VERSION,
        "auth_profile": auth_profile,
        "binding_scope": binding_scope,
        "decision": "block_wrapper_auth_evidence" if blockers else "allow_wrapper_auth_evidence",
        "status": "failed" if blockers else "passed",
        "token_source": source_decision,
        "wrapper_command_snapshot": command_snapshot["snapshot"],
        "leak_checks": leak_decision,
        "blockers": blockers,
        "redaction_status": "passed",
        "non_actions": [
            "did_not_read_token_file",
            "did_not_return_token_value",
            "did_not_inspect_live_process_table",
            "did_not_run_wrapper",
            "did_not_call_contextforge_api",
            "did_not_mutate_client_config",
        ],
    }
    _assert_no_raw_markers(trace, markers)
    return trace


def evaluate_token_source(
    token_source: Mapping[str, Any],
    *,
    auth_profile: str = DEFAULT_AUTH_PROFILE,
    binding_scope: str = "local",
) -> dict[str, Any]:
    """Validate token-source metadata without returning token material."""

    source = _json_copy(token_source)
    source_class = _canonical_source_class(source.get("class") or source.get("source_class") or source.get("token_source_class"))
    metadata = _safe_token_source_metadata(source, source_class=source_class)
    checks: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []

    if not source_class:
        _add_check(checks, blockers, "token_source_class_allowed", "failed", "missing token-source class")
    elif source_class in INHERITED_ENV_SOURCE_CLASSES:
        approved = source.get("rfc_approved") is True and source.get("leak_probes_passed") is True and source.get("long_lived") is not True
        if approved:
            _add_check(
                checks,
                blockers,
                "token_source_class_allowed",
                "passed",
                "RFC-approved non-long-lived inherited environment token model has leak probes",
            )
        else:
            _add_check(checks, blockers, "token_source_class_allowed", "failed", "inherited environment token source fails closed")
    elif source_class not in ALLOWED_TOKEN_SOURCE_CLASSES:
        _add_check(checks, blockers, "token_source_class_allowed", "failed", "token-source class is not allowed")
    else:
        _add_check(checks, blockers, "token_source_class_allowed", "passed", "token-source class is allowed")

    if source_class == "restrictive_local_token_file":
        _check_local_token_file(source, checks, blockers)
    elif source_class == "contextforge_token_provider_api":
        _check_contextforge_provider(source, checks, blockers)
    elif source_class == "wrapper_bound_brokered_token":
        _check_wrapper_broker(source, checks, blockers)
    elif source_class == "approved_remote_token_store":
        _check_remote_store(source, checks, blockers)

    cached_state = str(source.get("cached_token_state") or source.get("revocation_status") or "fresh")
    if cached_state in REVOKED_OR_STALE_STATES:
        _add_check(checks, blockers, "cached_token_not_revoked_or_stale", "failed", "cached token state is revoked, stale, expired, or unknown")
    else:
        _add_check(checks, blockers, "cached_token_not_revoked_or_stale", "passed", "no revoked or stale cached token state reported")

    if binding_scope in REMOTE_BINDING_SCOPES:
        _check_remote_binding(source, source_class, checks, blockers)
    else:
        _add_check(checks, blockers, "remote_binding_token_separation", "not_applicable", "binding scope is local")

    if source.get("contains_token_value") is True or "value" in source or "token_value" in source:
        _add_check(checks, blockers, "token_value_absent", "failed", "token-source metadata must not include token value fields")
    else:
        _add_check(checks, blockers, "token_value_absent", "passed", "token-source metadata contains no token value field")

    return {
        "decision": "block_token_source" if blockers else "allow_token_source",
        "status": "failed" if blockers else "passed",
        "metadata": metadata,
        "checks": checks,
        "blockers": blockers,
        "redaction_status": "passed",
        "non_actions": ["did_not_read_token_file", "did_not_return_token_value"],
    }


def build_wrapper_command_snapshot(
    command: Mapping[str, Any] | Sequence[Any],
    *,
    token_source_metadata: Mapping[str, Any] | None = None,
    raw_token_markers: Iterable[str] = (),
) -> dict[str, Any]:
    """Return a redacted wrapper command snapshot safe for evidence ledgers."""

    markers = tuple(str(marker) for marker in raw_token_markers if marker)
    command_data: Any = _json_copy(command)
    argv = _extract_argv(command_data)
    env = _extract_env(command_data)
    leaks = _find_leaks({"argv": argv, "env": env, "command": command_data}, raw_token_markers=markers)
    blockers = [
        _blocker("wrapper_command_snapshot_safe", "failed", "wrapper command snapshot contains token material", finding)
        for finding in leaks
    ]
    snapshot = {
        "redaction_status": "redacted",
        "argv_present": bool(argv),
        "argv_count": len(argv),
        "argv_shape": [_argument_shape(index, value, raw_token_markers=markers) for index, value in enumerate(argv)],
        "environment": _env_shape(env),
        "token_source": dict(token_source_metadata or {}),
        "contains_raw_token_material": bool(blockers),
    }
    _assert_no_raw_markers(snapshot, markers)
    return {
        "decision": "block_wrapper_command_snapshot" if blockers else "allow_wrapper_command_snapshot",
        "status": "failed" if blockers else "passed",
        "snapshot": snapshot,
        "blockers": blockers,
        "redaction_status": "passed",
        "non_actions": ["did_not_run_wrapper"],
    }


def evaluate_wrapper_leak_checks(
    evidence: Mapping[str, Any],
    *,
    raw_token_markers: Iterable[str] = (),
) -> dict[str, Any]:
    """Reject token material in wrapper runtime and diagnostic snapshots."""

    markers = tuple(str(marker) for marker in raw_token_markers if marker)
    evidence_copy = _json_copy(evidence)
    normalized = _normalized_surfaces(evidence_copy)
    checks: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    for surface in LEAK_SURFACES:
        if surface not in normalized:
            check = {
                "name": f"{surface}_leak_check",
                "status": "failed",
                "reason": "surface not supplied; required leak-check evidence is missing",
            }
            checks.append(check)
            blockers.append(check)
            continue
        surface_findings = _find_leaks({surface: normalized[surface]}, raw_token_markers=markers)
        findings.extend(surface_findings)
        if surface_findings:
            check = {
                "name": f"{surface}_leak_check",
                "status": "failed",
                "reason": "token material detected in supplied snapshot",
                "finding_count": len(surface_findings),
            }
            checks.append(check)
            blockers.append(check)
        else:
            checks.append({"name": f"{surface}_leak_check", "status": "passed", "reason": "no token material detected"})

    return {
        "decision": "block_wrapper_leak_checks" if blockers else "allow_wrapper_leak_checks",
        "status": "failed" if blockers else "passed",
        "checks": checks,
        "findings": findings,
        "blockers": blockers,
        "redaction_status": "passed",
        "non_actions": ["did_not_inspect_live_process_table", "did_not_run_wrapper"],
    }


def _check_local_token_file(source: Mapping[str, Any], checks: list[dict[str, Any]], blockers: list[dict[str, Any]]) -> None:
    ignored = source.get("ignored_by_vcs") is True or source.get("ignored") is True
    if ignored:
        _add_check(checks, blockers, "local_token_file_ignored", "passed", "token file is modeled as ignored")
    else:
        _add_check(checks, blockers, "local_token_file_ignored", "failed", "token file must be modeled as ignored")

    owner_matches = source.get("owner_matches_current_user") is True or source.get("owner") in {"current_user", "self"}
    if owner_matches:
        _add_check(checks, blockers, "local_token_file_owner", "passed", "token file owner matches current user")
    else:
        _add_check(checks, blockers, "local_token_file_owner", "failed", "token file owner must match current user")

    mode = _mode_int(source.get("mode") if "mode" in source else source.get("file_mode"))
    if mode is not None and _mode_is_0600_or_stricter(mode):
        _add_check(checks, blockers, "local_token_file_mode", "passed", "token file mode is 0600 or stricter")
    else:
        _add_check(checks, blockers, "local_token_file_mode", "failed", "token file mode must be 0600 or stricter")

    path_class = str(source.get("path_class") or "")
    if path_class in {"ignored_local_secret_file", "ignored_restrictive_local_file", "local_ignored_token_file"}:
        _add_check(checks, blockers, "local_token_path_class", "passed", "token path class is acceptable")
    else:
        _add_check(checks, blockers, "local_token_path_class", "failed", "token path class must identify an ignored restrictive local file")


def _check_contextforge_provider(source: Mapping[str, Any], checks: list[dict[str, Any]], blockers: list[dict[str, Any]]) -> None:
    provider_class = str(source.get("provider_class") or source.get("provider") or "")
    endpoint_class = str(source.get("endpoint_class") or source.get("provider_endpoint_class") or "")
    if provider_class == "contextforge" and endpoint_class in {"loopback_authenticated_http", "contextforge_local_api", "contextforge_token_provider"}:
        _add_check(checks, blockers, "contextforge_provider_api", "passed", "ContextForge token provider API is modeled")
    else:
        _add_check(checks, blockers, "contextforge_provider_api", "failed", "provider source must be a ContextForge token provider API")


def _check_wrapper_broker(source: Mapping[str, Any], checks: list[dict[str, Any]], blockers: list[dict[str, Any]]) -> None:
    if source.get("wrapper_bound") is True and source.get("brokered") is True:
        _add_check(checks, blockers, "wrapper_bound_broker", "passed", "brokered token is wrapper-bound")
    else:
        _add_check(checks, blockers, "wrapper_bound_broker", "failed", "brokered token must be wrapper-bound")
    if source.get("ephemeral") is True or source.get("cache_policy") in {"none", "memory_only"}:
        _add_check(checks, blockers, "wrapper_broker_cache_policy", "passed", "broker does not persist long-lived token material")
    else:
        _add_check(checks, blockers, "wrapper_broker_cache_policy", "failed", "broker cache policy must avoid long-lived persisted tokens")


def _check_remote_store(source: Mapping[str, Any], checks: list[dict[str, Any]], blockers: list[dict[str, Any]]) -> None:
    if source.get("approved") is True and source.get("separate_remote_token") is True:
        _add_check(checks, blockers, "remote_token_store_approved", "passed", "remote-token store is explicitly approved and separate")
    else:
        _add_check(checks, blockers, "remote_token_store_approved", "failed", "remote-token store must be approved and use separate token material")
    if source.get("revocation_profile") in {"remote_separate", "remote_ready", "separate_remote_revocation"}:
        _add_check(checks, blockers, "remote_token_revocation_profile", "passed", "remote store has separate revocation profile")
    else:
        _add_check(checks, blockers, "remote_token_revocation_profile", "failed", "remote store requires a separate revocation profile")


def _check_remote_binding(
    source: Mapping[str, Any],
    source_class: str,
    checks: list[dict[str, Any]],
    blockers: list[dict[str, Any]],
) -> None:
    if source_class != "approved_remote_token_store":
        _add_check(checks, blockers, "remote_binding_token_separation", "failed", "remote binding requires an approved remote-token store")
        return
    reused_local = source.get("reuses_local_shared_token") is True or source.get("token_profile") == DEFAULT_AUTH_PROFILE
    if reused_local:
        _add_check(checks, blockers, "remote_binding_token_separation", "failed", "remote binding must not reuse the local shared token")
    else:
        _add_check(checks, blockers, "remote_binding_token_separation", "passed", "remote binding uses separate token material")


def _safe_token_source_metadata(source: Mapping[str, Any], *, source_class: str) -> dict[str, Any]:
    mode = _mode_int(source.get("mode") if "mode" in source else source.get("file_mode"))
    metadata = {
        "token_source_class": source_class or "unknown",
        "source_id": _safe_metadata_value(source.get("source_id") or source.get("id") or "unspecified"),
        "path_class": _safe_metadata_value(source.get("path_class") or "not_applicable"),
        "storage_class": _safe_metadata_value(source.get("storage_class") or source_class or "unknown"),
        "provider_class": _safe_metadata_value(source.get("provider_class") or source.get("provider") or "not_applicable"),
        "provider_endpoint_class": _safe_metadata_value(source.get("endpoint_class") or source.get("provider_endpoint_class") or "not_applicable"),
        "broker_binding_class": _safe_metadata_value(source.get("broker_binding_class") or "not_applicable"),
        "remote_store_class": _safe_metadata_value(source.get("remote_store_class") or "not_applicable"),
        "file_mode_octal": f"{mode:04o}" if mode is not None else None,
        "ignored_by_vcs": source.get("ignored_by_vcs") is True or source.get("ignored") is True,
        "owner_matches_current_user": source.get("owner_matches_current_user") is True or source.get("owner") in {"current_user", "self"},
        "cached_token_state": _safe_metadata_value(source.get("cached_token_state") or source.get("revocation_status") or "fresh"),
        "token_profile": _safe_metadata_value(source.get("token_profile") or DEFAULT_AUTH_PROFILE),
        "contains_token_value": False,
        "redaction_status": "passed",
    }
    return metadata


def _find_leaks(value: Any, *, raw_token_markers: Iterable[str]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    markers = tuple(marker for marker in raw_token_markers if marker)
    for path, node in _walk(value):
        key = path[-1] if path else ""
        key_class = None if key in SAFE_METADATA_KEYS else redaction.classify_sensitive_key(key)
        if isinstance(node, str):
            value_class = _secret_value_class(node, markers)
            if value_class:
                findings.append(_finding(path, value_class, "secret_shaped_or_raw_token_value", node))
                continue
        if key_class and _unsafe_secret_value(node):
            findings.append(_finding(path, key_class, "secret_bearing_key_with_unredacted_value", node))
    return findings


def _secret_value_class(value: str, raw_token_markers: Sequence[str]) -> str | None:
    if redaction.is_safe_placeholder(value):
        return None
    for marker in raw_token_markers:
        if marker and marker in value:
            return "raw_token_marker"
    classified = redaction.classify_sensitive_value(value)
    if classified:
        return classified
    if SECRET_VALUE_RE.search(value):
        return "secret_like_value"
    return None


def _unsafe_secret_value(value: Any) -> bool:
    if value is None or isinstance(value, bool | int | float):
        return False
    if isinstance(value, str):
        return not redaction.is_safe_placeholder(value)
    if isinstance(value, Mapping):
        return value.get("redacted") is not True and value.get("redaction_status") not in {"redacted", "passed"}
    return True


def _finding(path: Iterable[str], classification: str, reason: str, value: Any) -> dict[str, Any]:
    return {
        "path": _format_path(path),
        "classification": classification,
        "reason": reason,
        "value_digest": _stable_digest(value),
        "value_type": type(value).__name__,
        "redacted": True,
    }


def _blocker(name: str, status: str, reason: str, finding: Mapping[str, Any] | None = None) -> dict[str, Any]:
    blocker: dict[str, Any] = {"name": name, "status": status, "reason": reason}
    if finding is not None:
        blocker["finding"] = dict(finding)
    return blocker


def _add_check(
    checks: list[dict[str, Any]],
    blockers: list[dict[str, Any]],
    name: str,
    status: str,
    reason: str,
) -> None:
    check = {"name": name, "status": status, "reason": reason}
    checks.append(check)
    if status == "failed":
        blockers.append(check)


def _argument_shape(index: int, value: Any, *, raw_token_markers: Iterable[str]) -> dict[str, Any]:
    text = str(value)
    secret_class = _secret_value_class(text, tuple(raw_token_markers))
    if index == 0:
        argument_class = "executable"
    elif text.startswith("-"):
        argument_class = "flag"
    else:
        argument_class = "secret_like" if secret_class else "value"
    return {
        "index": index,
        "argument_class": argument_class,
        "value_digest": _stable_digest(text),
        "value_length": len(text),
        "redacted": True,
    }


def _env_shape(env: Mapping[str, Any]) -> dict[str, Any]:
    keys = []
    for key in sorted(str(key) for key in env):
        keys.append(
            {
                "name_digest": _stable_digest(key),
                "sensitive_name": redaction.classify_sensitive_key(key) is not None,
            }
        )
    return {"variable_count": len(keys), "keys": keys, "values_returned": False}


def _normalized_surfaces(evidence: Mapping[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in evidence.items():
        surface = SURFACE_ALIASES.get(str(key), str(key))
        normalized[surface] = value
    return normalized


def _extract_argv(command: Any) -> list[Any]:
    if isinstance(command, Sequence) and not isinstance(command, str | bytes | bytearray):
        return list(command)
    if not isinstance(command, Mapping):
        return []
    for key in ("argv", "command_args", "args"):
        value = command.get(key)
        if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
            return list(value)
    command_value = command.get("command")
    if isinstance(command_value, str):
        return [command_value]
    return []


def _extract_env(command: Any) -> Mapping[str, Any]:
    if isinstance(command, Mapping):
        value = command.get("env") or command.get("environment")
        if isinstance(value, Mapping):
            return value
    return {}


def _canonical_source_class(value: Any) -> str:
    raw = str(value or "").strip()
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", raw).strip("_").lower()
    return TOKEN_SOURCE_CLASS_ALIASES.get(raw, TOKEN_SOURCE_CLASS_ALIASES.get(normalized, normalized))


def _mode_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value & 0o7777
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(text, 8) & 0o7777
    except ValueError:
        return None


def _mode_is_0600_or_stricter(mode: int) -> bool:
    owner_has_read = bool(mode & 0o400)
    no_group_or_other = (mode & 0o077) == 0
    no_execute_or_special = (mode & 0o7111) == 0
    owner_permissions_not_broader_than_0600 = (mode & 0o700) in {0o400, 0o600}
    return owner_has_read and no_group_or_other and no_execute_or_special and owner_permissions_not_broader_than_0600


def _safe_metadata_value(value: Any) -> Any:
    if value is None or isinstance(value, bool | int | float):
        return value
    text = str(value)
    if _secret_value_class(text, ()):
        return REDACTED_MARKER
    if "/" in text or "\\" in text:
        return PurePath(text).name if redaction.classify_sensitive_key(PurePath(text).name) is None else "path_name_redacted"
    return text


def _json_copy(value: Any) -> Any:
    try:
        return copy.deepcopy(json.loads(json.dumps(value, sort_keys=True)))
    except TypeError as exc:
        raise WrapperAuthEvidenceError("wrapper auth evidence must be JSON-compatible") from exc


def _stable_digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


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


def _assert_no_raw_markers(value: Any, raw_token_markers: Iterable[str]) -> None:
    encoded = json.dumps(value, sort_keys=True)
    for marker in raw_token_markers:
        if marker and marker in encoded:
            raise WrapperAuthEvidenceError("redacted wrapper auth trace contains raw token marker")
