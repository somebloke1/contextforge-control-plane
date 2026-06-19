#!/usr/bin/env python3
"""MCP wrapper for ContextForge helper project-init workflow tools."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

import control_plane_project_init_helper as helper


server = FastMCP("contextforge-helper")

_CACHED_PLANS: dict[str, dict[str, Any]] = {}
_CACHED_RECEIPTS: dict[str, list[dict[str, Any]]] = {}
_CACHED_RECOVERY_PLANS: dict[str, dict[str, Any]] = {}
_CACHED_RECOVERY_RECEIPTS: dict[str, list[dict[str, Any]]] = {}
DEFAULT_CLIENT_TYPE = os.environ.get("CONTEXTFORGE_HELPER_DEFAULT_CLIENT_TYPE", "codex").strip() or "codex"


def _cache_dir() -> Path:
    root = Path(os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir())
    return root / "contextforge-helper" / "project-init-cache"


def _cache_path(project_root: str) -> Path:
    digest = hashlib.sha256(_cache_key(project_root).encode("utf-8")).hexdigest()[:32]
    return _cache_dir() / f"{digest}.json"


def _read_durable_cache(project_root: str) -> dict[str, Any]:
    path = _cache_path(project_root)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict) or data.get("project_root") != _cache_key(project_root):
        return {}
    return data


def _write_durable_cache(project_root: str, data: dict[str, Any]) -> None:
    path = _cache_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"project_root": _cache_key(project_root), **data}
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(temp_path, 0o600)
    temp_path.replace(path)


def _clear_durable_cache(project_root: str) -> None:
    try:
        _cache_path(project_root).unlink()
    except FileNotFoundError:
        pass


def _error(exc: Exception) -> dict[str, Any]:
    return {
        "ok": False,
        "error": {
            "type": exc.__class__.__name__,
            "message": str(exc),
        },
    }


def _unwrap_tool_envelope(value: dict[str, Any]) -> dict[str, Any]:
    """Remove MCP response metadata before passing a plan back to pure helpers."""

    if value.get("ok") is True:
        return {key: item for key, item in value.items() if key != "ok"}
    return value


def _cache_key(project_root: str) -> str:
    return str(Path(project_root).expanduser().resolve(strict=False))


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _approval_source_path() -> Path | None:
    raw = os.environ.get("CONTEXTFORGE_HELPER_APPROVAL_SOURCE_PATH", "").strip()
    return Path(raw).expanduser() if raw else None


def _read_latest_user_message_text(project_root: str) -> str:
    path = _approval_source_path()
    if path is None:
        return ""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    if not isinstance(data, dict):
        return ""
    cwd = data.get("cwd")
    if cwd and _cache_key(str(cwd)) != _cache_key(project_root):
        return ""
    text = data.get("text")
    return text if isinstance(text, str) else ""


def _require_latest_user_text(project_root: str, *, env_name: str, purpose: str, keywords: set[str]) -> None:
    if not _env_truthy(env_name):
        return
    text = _read_latest_user_message_text(project_root)
    lowered = text.lower()
    if any(keyword in lowered for keyword in keywords):
        return
    raise PermissionError(f"latest user message does not contain explicit {purpose} intent")


def _contains_selection_number(text: str, selection_number: int) -> bool:
    return re.search(rf"(?<!\d){selection_number}(?!\d)", text) is not None


def _require_user_approval_text(project_root: str, challenge_id: str | None, plan_digest: str | None) -> None:
    if not _env_truthy("CONTEXTFORGE_HELPER_REQUIRE_USER_APPROVAL_TEXT"):
        return
    text = _read_latest_user_message_text(project_root)
    lowered = text.lower()
    approved = (
        "approve" in lowered
        or "approved" in lowered
        or (bool(challenge_id) and str(challenge_id) in text)
        or (bool(plan_digest) and str(plan_digest) in text)
    )
    if not approved:
        raise PermissionError(
            "latest user message does not contain explicit approval text, challenge id, or plan digest; "
            "ask the user to approve the exact project-init plan before calling approval tools"
        )


def _require_user_reload_text(project_root: str) -> None:
    _require_latest_user_text(
        project_root,
        env_name="CONTEXTFORGE_HELPER_REQUIRE_USER_RELOAD_TEXT",
        purpose="reload or validation",
        keywords={"reload", "reloaded", "restart", "restarted", "new session", "validate", "validation", "skip", "presume"},
    )


def _require_user_validation_text(project_root: str, validation_mode: str) -> None:
    if not _env_truthy("CONTEXTFORGE_HELPER_REQUIRE_USER_VALIDATION_TEXT"):
        return
    text = _read_latest_user_message_text(project_root)
    lowered = text.lower()
    if validation_mode == "validate_now":
        if "validate" in lowered or "validation" in lowered or _contains_selection_number(text, 1):
            return
    elif validation_mode == "presume_working":
        if "skip" in lowered or "presume" in lowered or "working" in lowered or _contains_selection_number(text, 2):
            return
    else:
        if (
            "validate" in lowered
            or "validation" in lowered
            or "skip" in lowered
            or "presume" in lowered
            or "working" in lowered
            or _contains_selection_number(text, 1)
            or _contains_selection_number(text, 2)
        ):
            return
    raise PermissionError("latest user message does not contain explicit validation intent")


def _record_reload_from_validation_request_if_configured(
    project_root: str,
    *,
    validation_mode: str,
    client_type: str,
    dry_run: bool,
) -> dict[str, Any] | None:
    if not _env_truthy("CONTEXTFORGE_HELPER_RECORD_RELOAD_ON_VALIDATION_REQUEST"):
        return None
    if validation_mode not in {"validate_now", "presume_working"}:
        return None
    try:
        resume = helper.pending_validation_resume(project_root=project_root, client_type=client_type)
    except Exception:
        return None
    if not isinstance(resume, dict) or resume.get("status") != "client_reload_required":
        return None
    return {
        "ok": True,
        **helper.record_project_init_client_reload(
            project_root=project_root,
            client_type=client_type,
            validation_mode=validation_mode,
            dry_run=dry_run,
        ),
    }


def _remember_plan(project_root: str, plan: dict[str, Any]) -> dict[str, Any]:
    _CACHED_PLANS[_cache_key(project_root)] = dict(plan)
    current = _read_durable_cache(project_root)
    _write_durable_cache(project_root, {**current, "plan": dict(plan)})
    return plan


def _remember_receipts(project_root: str, receipts: list[dict[str, Any]]) -> None:
    _CACHED_RECEIPTS[_cache_key(project_root)] = list(receipts)
    current = _read_durable_cache(project_root)
    _write_durable_cache(project_root, {**current, "receipts": list(receipts)})


def _receipts_match_current_plan(receipts: Any, plan: dict[str, Any]) -> bool:
    if not isinstance(receipts, list):
        return False
    plan_id = str(plan.get("plan_id") or "")
    plan_digest = str(plan.get("plan_digest") or "")
    required = {str(item) for item in plan.get("required_consent_classes") or []}
    if not plan_id or not plan_digest:
        return False
    if not required:
        return receipts == []
    if len(receipts) != len(required):
        return False
    observed: set[str] = set()
    for receipt in receipts:
        if not isinstance(receipt, dict):
            return False
        if str(receipt.get("plan_id") or "") != plan_id:
            return False
        if str(receipt.get("plan_digest") or "") != plan_digest:
            return False
        if not str(receipt.get("plan_presented_digest") or ""):
            return False
        observed.add(str(receipt.get("consent_class") or ""))
    return observed == required


def _matching_cached_receipts(project_root: str, plan: dict[str, Any]) -> list[dict[str, Any]] | None:
    cached_receipts = _CACHED_RECEIPTS.get(_cache_key(project_root))
    if _receipts_match_current_plan(cached_receipts, plan):
        return list(cached_receipts or [])
    durable = _read_durable_cache(project_root)
    durable_receipts = durable.get("receipts") if isinstance(durable.get("receipts"), list) else None
    if _receipts_match_current_plan(durable_receipts, plan):
        remembered = list(durable_receipts or [])
        _CACHED_RECEIPTS[_cache_key(project_root)] = remembered
        return remembered
    return None


def _remember_recovery_plan(project_root: str, plan: dict[str, Any]) -> dict[str, Any]:
    _CACHED_RECOVERY_PLANS[_cache_key(project_root)] = dict(plan)
    current = _read_durable_cache(project_root)
    _write_durable_cache(project_root, {**current, "recovery_plan": dict(plan)})
    return plan


def _remember_recovery_receipts(project_root: str, receipts: list[dict[str, Any]]) -> None:
    _CACHED_RECOVERY_RECEIPTS[_cache_key(project_root)] = list(receipts)
    current = _read_durable_cache(project_root)
    _write_durable_cache(project_root, {**current, "recovery_receipts": list(receipts)})


def _remember_project_init_result(project_root: str, result: dict[str, Any]) -> None:
    clean = _unwrap_tool_envelope(result)
    recovery_plan = clean.get("recovery_plan") if isinstance(clean.get("recovery_plan"), dict) else None
    if recovery_plan:
        _remember_recovery_plan(project_root, recovery_plan)
    if clean.get("workflow") == "project_init" and clean.get("plan_id"):
        _remember_plan(project_root, clean)


def _clear_durable_recovery_cache(project_root: str, *, keep_plan: bool = False) -> None:
    current = _read_durable_cache(project_root)
    if not current:
        return
    if not keep_plan:
        current.pop("recovery_plan", None)
    current.pop("recovery_receipts", None)
    _write_durable_cache(project_root, current)


def _matching_cached_plan(project_root: str, challenge_id: str | None, plan_digest: str | None) -> dict[str, Any]:
    plan = _CACHED_PLANS.get(_cache_key(project_root))
    if not plan:
        durable = _read_durable_cache(project_root)
        durable_plan = durable.get("plan") if isinstance(durable.get("plan"), dict) else None
        if durable_plan:
            plan = dict(durable_plan)
            _CACHED_PLANS[_cache_key(project_root)] = plan
    if not plan:
        raise ValueError("no cached project-init plan is available; call propose_project_init or cf_project_init_propose first")
    challenge = plan.get("approval_challenge") if isinstance(plan.get("approval_challenge"), dict) else {}
    if challenge_id and challenge.get("challenge_id") != challenge_id:
        raise ValueError("cached project-init plan challenge id does not match")
    if plan_digest and plan.get("plan_digest") != plan_digest:
        raise ValueError("cached project-init plan digest does not match")
    return plan


def _matching_cached_recovery_plan(project_root: str, challenge_id: str | None, plan_digest: str | None) -> dict[str, Any]:
    plan = _CACHED_RECOVERY_PLANS.get(_cache_key(project_root))
    if not plan:
        durable = _read_durable_cache(project_root)
        durable_plan = durable.get("recovery_plan") if isinstance(durable.get("recovery_plan"), dict) else None
        if durable_plan:
            plan = dict(durable_plan)
            _CACHED_RECOVERY_PLANS[_cache_key(project_root)] = plan
    if not plan:
        raise ValueError("no cached project-init recovery plan is available; call cf_project_init_recovery_propose first")
    challenge = plan.get("approval_challenge") if isinstance(plan.get("approval_challenge"), dict) else {}
    if challenge_id and challenge.get("challenge_id") != challenge_id:
        raise ValueError("cached project-init recovery plan challenge id does not match")
    if plan_digest and plan.get("plan_digest") != plan_digest:
        raise ValueError("cached project-init recovery plan digest does not match")
    return plan


def _cached_recovery_continuation_plan(project_root: str, activation_plan: dict[str, Any]) -> dict[str, Any] | None:
    plan = _CACHED_RECOVERY_PLANS.get(_cache_key(project_root))
    if not plan:
        durable = _read_durable_cache(project_root)
        durable_plan = durable.get("recovery_plan") if isinstance(durable.get("recovery_plan"), dict) else None
        if durable_plan:
            plan = dict(durable_plan)
            _CACHED_RECOVERY_PLANS[_cache_key(project_root)] = plan
    if not isinstance(plan, dict):
        return None
    source = plan.get("source_activation_plan") if isinstance(plan.get("source_activation_plan"), dict) else {}
    if source.get("plan_id") != activation_plan.get("plan_id") or source.get("plan_digest") != activation_plan.get("plan_digest"):
        return None
    return plan


@server.tool()
def get_project_context(project_root: str, client_type: str = DEFAULT_CLIENT_TYPE) -> dict[str, Any]:
    """Return helper readiness and local project-root attestation."""
    try:
        return {"ok": True, **helper.helper_readiness(project_root=project_root, client_type=client_type)}
    except Exception as exc:
        return _error(exc)


@server.tool()
def cf_project_init_get_context(project_root: str, client_type: str = DEFAULT_CLIENT_TYPE) -> dict[str, Any]:
    """Alias for get_project_context with the project-init tool id."""
    return get_project_context(project_root=project_root, client_type=client_type)


@server.tool()
def list_available_capabilities(
    project_root: str,
    client_type: str = DEFAULT_CLIENT_TYPE,
    contextforge_servers: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """List activation candidates and one service-selection next_turn."""
    try:
        return {
            "ok": True,
            **helper.list_available_capabilities(
                project_root=project_root,
                client_type=client_type,
                contextforge_servers=contextforge_servers,
            ),
        }
    except Exception as exc:
        return _error(exc)


@server.tool()
def cf_project_init_list_capabilities(
    project_root: str,
    client_type: str = DEFAULT_CLIENT_TYPE,
    contextforge_servers: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Alias for list_available_capabilities with the project-init tool id."""
    return list_available_capabilities(
        project_root=project_root,
        client_type=client_type,
        contextforge_servers=contextforge_servers,
    )


@server.tool()
def propose_project_init(
    project_root: str,
    selected_services: list[dict[str, Any] | str],
    client_type: str = DEFAULT_CLIENT_TYPE,
    inputs: dict[str, Any] | None = None,
    contextforge_servers: list[dict[str, Any]] | None = None,
    server_instances_root: str | None = None,
) -> dict[str, Any]:
    """Build a non-mutating activation plan or the next required input turn."""
    try:
        result = {
            "ok": True,
            **helper.propose_project_init(
                project_root=project_root,
                selected_services=selected_services,
                client_type=client_type,
                inputs=inputs,
                contextforge_servers=contextforge_servers,
                server_instances_root=server_instances_root,
            ),
        }
        _remember_project_init_result(project_root, result)
        return result
    except Exception as exc:
        return _error(exc)


@server.tool()
def cf_project_init_propose(
    project_root: str,
    selected_services: list[dict[str, Any] | str],
    client_type: str = DEFAULT_CLIENT_TYPE,
    inputs: dict[str, Any] | None = None,
    contextforge_servers: list[dict[str, Any]] | None = None,
    server_instances_root: str | None = None,
) -> dict[str, Any]:
    """Build and cache a project-init plan for later id/digest approval."""
    return propose_project_init(
        project_root=project_root,
        selected_services=selected_services,
        client_type=client_type,
        inputs=inputs,
        contextforge_servers=contextforge_servers,
        server_instances_root=server_instances_root,
    )


@server.tool()
def propose_project_init_recovery(
    project_root: str,
    client_type: str = DEFAULT_CLIENT_TYPE,
    contextforge_servers: list[dict[str, Any]] | None = None,
    server_instances_root: str | None = None,
    inputs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build and cache a recovery project-init plan."""
    try:
        recovery_inputs = dict(inputs or {})
        if not any(key in recovery_inputs for key in ("activation_plan", "project_init_plan", "source_activation_plan", "plan")):
            cached_activation_plan = _CACHED_PLANS.get(_cache_key(project_root))
            if not cached_activation_plan:
                durable = _read_durable_cache(project_root)
                durable_plan = durable.get("plan") if isinstance(durable.get("plan"), dict) else None
                if durable_plan:
                    cached_activation_plan = dict(durable_plan)
            if isinstance(cached_activation_plan, dict) and cached_activation_plan.get("workflow") == "project_init":
                recovery_inputs["activation_plan"] = cached_activation_plan
            elif not recovery_inputs:
                cached_recovery_plan = _CACHED_RECOVERY_PLANS.get(_cache_key(project_root))
                if not cached_recovery_plan:
                    durable = _read_durable_cache(project_root)
                    durable_recovery_plan = durable.get("recovery_plan") if isinstance(durable.get("recovery_plan"), dict) else None
                    if durable_recovery_plan:
                        cached_recovery_plan = dict(durable_recovery_plan)
                        _CACHED_RECOVERY_PLANS[_cache_key(project_root)] = cached_recovery_plan
                if cached_recovery_plan:
                    return {"ok": True, **cached_recovery_plan}
        result = {
            "ok": True,
            **helper.propose_project_init_recovery(
                project_root=project_root,
                client_type=client_type,
                contextforge_servers=contextforge_servers,
                server_instances_root=server_instances_root,
                inputs=recovery_inputs,
            ),
        }
        _remember_recovery_plan(project_root, _unwrap_tool_envelope(result))
        return result
    except Exception as exc:
        return _error(exc)


@server.tool()
def cf_project_init_recovery_propose(
    project_root: str,
    client_type: str = DEFAULT_CLIENT_TYPE,
    contextforge_servers: list[dict[str, Any]] | None = None,
    server_instances_root: str | None = None,
    inputs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Alias for recovery plan creation with the project-init tool id."""
    return propose_project_init_recovery(
        project_root=project_root,
        client_type=client_type,
        contextforge_servers=contextforge_servers,
        server_instances_root=server_instances_root,
        inputs=inputs,
    )


@server.tool()
def approve_project_init_plan(
    project_root: str,
    plan: dict[str, Any],
    approval: dict[str, Any],
) -> dict[str, Any]:
    """Issue helper-owned consent receipts for an exact approved plan digest."""
    try:
        clean_plan = _unwrap_tool_envelope(plan)
        challenge = clean_plan.get("approval_challenge") if isinstance(clean_plan.get("approval_challenge"), dict) else {}
        approval_challenge_id = (
            approval.get("challenge_id")
            if isinstance(approval, dict) and approval.get("challenge_id")
            else challenge.get("challenge_id")
        )
        approval_plan_digest = (
            approval.get("plan_digest")
            if isinstance(approval, dict) and approval.get("plan_digest")
            else clean_plan.get("plan_digest")
        )
        _require_user_approval_text(project_root, str(approval_challenge_id or ""), str(approval_plan_digest or ""))
        helper.restore_process_local_approval_session(project_root=project_root, plan=clean_plan)
        local_event = helper.record_local_approval_event(
            project_root=project_root,
            plan=clean_plan,
            issuer_token=helper._LOCAL_APPROVAL_ISSUER_TOKEN,
            channel="interactive_user",
        )
        result = {
            "ok": True,
            **helper.approve_project_init_plan(
                project_root=project_root,
                plan=clean_plan,
                approval=approval,
                local_approval_event_ref=local_event["event_ref"],
                actor="developer",
                source_client=str(clean_plan.get("client_type") or "codex"),
                source_client_auth_strength="shared_token",
            ),
        }
        _remember_plan(project_root, clean_plan)
        _remember_receipts(project_root, list(result.get("receipts") or []))
        return result
    except Exception as exc:
        return _error(exc)


@server.tool()
def approve_project_init_recovery_plan(
    project_root: str,
    plan: dict[str, Any],
    approval: dict[str, Any],
) -> dict[str, Any]:
    """Issue helper-owned recovery consent receipts for an exact approved recovery plan digest."""
    try:
        clean_plan = _unwrap_tool_envelope(plan)
        challenge = clean_plan.get("approval_challenge") if isinstance(clean_plan.get("approval_challenge"), dict) else {}
        approval_challenge_id = (
            approval.get("challenge_id")
            if isinstance(approval, dict) and approval.get("challenge_id")
            else challenge.get("challenge_id")
        )
        approval_plan_digest = (
            approval.get("plan_digest")
            if isinstance(approval, dict) and approval.get("plan_digest")
            else clean_plan.get("plan_digest")
        )
        _require_user_approval_text(project_root, str(approval_challenge_id or ""), str(approval_plan_digest or ""))
        helper.restore_process_local_approval_session(project_root=project_root, plan=clean_plan)
        local_event = helper.record_local_approval_event(
            project_root=project_root,
            plan=clean_plan,
            issuer_token=helper._LOCAL_APPROVAL_ISSUER_TOKEN,
            channel="interactive_user",
        )
        result = {
            "ok": True,
            **helper.approve_project_init_recovery_plan(
                project_root=project_root,
                plan=clean_plan,
                approval=approval,
                local_approval_event_ref=local_event["event_ref"],
                actor="developer",
                source_client=str(clean_plan.get("client_type") or "codex"),
                source_client_auth_strength="shared_token",
            ),
        }
        _remember_recovery_plan(project_root, clean_plan)
        _remember_recovery_receipts(project_root, list(result.get("receipts") or []))
        return result
    except Exception as exc:
        return _error(exc)


@server.tool()
def cf_project_init_recovery_approve(
    project_root: str,
    challenge_id: str,
    plan_digest: str,
) -> dict[str, Any]:
    """Approve the latest cached recovery plan by challenge id and plan digest."""
    try:
        plan = _matching_cached_recovery_plan(project_root, challenge_id, plan_digest)
        _require_user_approval_text(project_root, challenge_id, plan_digest)
        helper.restore_process_local_approval_session(project_root=project_root, plan=plan)
        local_event = helper.record_local_approval_event(
            project_root=project_root,
            plan=plan,
            issuer_token=helper._LOCAL_APPROVAL_ISSUER_TOKEN,
            channel="interactive_user",
        )
        approval = {"decision": "approve", "challenge_id": challenge_id, "plan_digest": plan_digest}
        result = {
            "ok": True,
            **helper.approve_project_init_recovery_plan(
                project_root=project_root,
                plan=plan,
                approval=approval,
                local_approval_event_ref=local_event["event_ref"],
                actor="developer",
                source_client=str(plan.get("client_type") or "codex"),
                source_client_auth_strength="shared_token",
            ),
        }
        _remember_recovery_plan(project_root, plan)
        _remember_recovery_receipts(project_root, list(result.get("receipts") or []))
        return result
    except Exception as exc:
        return _error(exc)


@server.tool()
def apply_project_init_recovery(
    project_root: str,
    plan: dict[str, Any],
    receipts: list[dict[str, Any]],
    contextforge_servers: list[dict[str, Any]] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Apply a helper-approved recovery plan and return reload or validation next_turn."""
    try:
        clean_plan = _unwrap_tool_envelope(plan)
        helper.restore_process_local_approval_session(project_root=project_root, plan=clean_plan, receipts=receipts)
        return {
            "ok": True,
            **helper.apply_project_init_recovery(
                project_root=project_root,
                plan=clean_plan,
                receipts=receipts,
                contextforge_servers=contextforge_servers,
                dry_run=dry_run,
            ),
        }
    except Exception as exc:
        return _error(exc)


@server.tool()
def cf_project_init_recovery_apply(
    project_root: str,
    receipts: list[dict[str, Any]] | None = None,
    contextforge_servers: list[dict[str, Any]] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Apply the cached recovery plan and receipts."""
    try:
        plan = _matching_cached_recovery_plan(project_root, None, None)
        cached_receipts = receipts if receipts is not None else _CACHED_RECOVERY_RECEIPTS.get(_cache_key(project_root))
        if cached_receipts is None:
            durable = _read_durable_cache(project_root)
            durable_receipts = durable.get("recovery_receipts") if isinstance(durable.get("recovery_receipts"), list) else None
            if durable_receipts is not None:
                cached_receipts = list(durable_receipts)
                _CACHED_RECOVERY_RECEIPTS[_cache_key(project_root)] = cached_receipts
        if not isinstance(cached_receipts, list):
            raise ValueError("no cached project-init receipts are available; call cf_project_init_recovery_approve first")
        helper.restore_process_local_approval_session(project_root=project_root, plan=plan, receipts=cached_receipts)
        result = {
            "ok": True,
            **helper.apply_project_init_recovery(
                project_root=project_root,
                plan=plan,
                receipts=cached_receipts,
                contextforge_servers=contextforge_servers,
                dry_run=dry_run,
            ),
        }
        if not dry_run:
            _clear_durable_recovery_cache(project_root, keep_plan=True)
        return result
    except Exception as exc:
        return _error(exc)


@server.tool()
def cf_project_init_approve(
    project_root: str,
    challenge_id: str,
    plan_digest: str,
) -> dict[str, Any]:
    """Approve the latest cached project-init plan by challenge id and plan digest."""
    try:
        plan = _matching_cached_plan(project_root, challenge_id, plan_digest)
        _require_user_approval_text(project_root, challenge_id, plan_digest)
        helper.restore_process_local_approval_session(project_root=project_root, plan=plan)
        local_event = helper.record_local_approval_event(
            project_root=project_root,
            plan=plan,
            issuer_token=helper._LOCAL_APPROVAL_ISSUER_TOKEN,
            channel="interactive_user",
        )
        approval = {"decision": "approve", "challenge_id": challenge_id, "plan_digest": plan_digest}
        result = {
            "ok": True,
            **helper.approve_project_init_plan(
                project_root=project_root,
                plan=plan,
                approval=approval,
                local_approval_event_ref=local_event["event_ref"],
                actor="developer",
                source_client=str(plan.get("client_type") or "codex"),
                source_client_auth_strength="shared_token",
            ),
        }
        _remember_plan(project_root, plan)
        _remember_receipts(project_root, list(result.get("receipts") or []))
        return result
    except Exception as exc:
        return _error(exc)


@server.tool()
def apply_approved_project_init(
    project_root: str,
    plan: dict[str, Any],
    receipts: list[dict[str, Any]],
    contextforge_servers: list[dict[str, Any]] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Apply a helper-approved project-init plan and return reload or validation next_turn."""
    try:
        clean_plan = _unwrap_tool_envelope(plan)
        helper.restore_process_local_approval_session(project_root=project_root, plan=clean_plan, receipts=receipts)
        result = {
            "ok": True,
            **helper.apply_approved_project_init(
                project_root=project_root,
                plan=clean_plan,
                receipts=receipts,
                contextforge_servers=contextforge_servers,
                recovery_plan=_cached_recovery_continuation_plan(project_root, clean_plan),
                dry_run=dry_run,
            ),
        }
        _remember_project_init_result(project_root, result)
        return result
    except Exception as exc:
        return _error(exc)


@server.tool()
def cf_project_init_apply(
    project_root: str,
    receipts: list[dict[str, Any]] | None = None,
    contextforge_servers: list[dict[str, Any]] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Apply the cached approved project-init plan and receipts."""
    try:
        plan = _matching_cached_plan(project_root, None, None)
        cached_receipts = _matching_cached_receipts(project_root, plan)
        if cached_receipts is None and receipts is not None:
            cached_receipts = receipts
        if not isinstance(cached_receipts, list):
            raise ValueError("no cached project-init receipts are available; call cf_project_init_approve first")
        helper.restore_process_local_approval_session(project_root=project_root, plan=plan, receipts=cached_receipts)
        recovery_plan = _cached_recovery_continuation_plan(project_root, plan)
        result_payload = helper.apply_approved_project_init(
            project_root=project_root,
            plan=plan,
            receipts=cached_receipts,
            contextforge_servers=contextforge_servers,
            recovery_plan=recovery_plan,
            dry_run=dry_run,
        )
        result = {
            "ok": True,
            **result_payload,
        }
        _remember_project_init_result(project_root, result)
        if not dry_run and result_payload.get("status") != "config_recovery_required":
            _clear_durable_cache(project_root)
        return result
    except Exception as exc:
        return _error(exc)


@server.tool()
def repair_pending_project_init_config(
    project_root: str,
    client_type: str = DEFAULT_CLIENT_TYPE,
    contextforge_servers: list[dict[str, Any]] | None = None,
    server_instances_root: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Repair an approved project-init job whose project-local config is incomplete."""
    try:
        return {
            "ok": True,
            **helper.repair_pending_project_init_config(
                project_root=project_root,
                client_type=client_type,
                contextforge_servers=contextforge_servers,
                server_instances_root=server_instances_root,
                dry_run=dry_run,
            ),
        }
    except Exception as exc:
        return _error(exc)


@server.tool()
def cf_project_init_repair(
    project_root: str,
    client_type: str = DEFAULT_CLIENT_TYPE,
    contextforge_servers: list[dict[str, Any]] | None = None,
    server_instances_root: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Alias for repair_pending_project_init_config with the project-init tool id."""
    return repair_pending_project_init_config(
        project_root=project_root,
        client_type=client_type,
        contextforge_servers=contextforge_servers,
        server_instances_root=server_instances_root,
        dry_run=dry_run,
    )


@server.tool()
def record_project_init_validation(
    project_root: str,
    validation_mode: str,
    validation_results: dict[str, Any] | None = None,
    client_type: str = DEFAULT_CLIENT_TYPE,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Record validation choice/results.

    For validation_mode="validate_now", first call a target-client-visible safe
    probe tool for each selected service. Then pass validation_results as a
    top-level object keyed by selected service binding, normalized binding key,
    or service identity id, for example:
    {"context7:canonical": {"status": "passed", "target_client_visible": true,
    "target_client": "opencode",
    "proof_kind": "target_client_safe_probe_result",
    "safe_probe_result": "passed", "safe_probe_id": "resolve-library-id",
    "tool_name": "context7_context7-local-resolve-library-id",
    "result_summary": "brief summary of the actual tool output",
    "verification_trace_refs": ["contextforge://control-plane/traces/context7:canonical-target-client"]}}.
    Do not call validate_now with missing or empty validation_results. Do not
    invent validation_results before calling the target-client service tool. Do
    not nest results under {"services": ...}.
    """
    try:
        _require_user_validation_text(project_root, validation_mode)
        reload_result = _record_reload_from_validation_request_if_configured(
            project_root,
            validation_mode=validation_mode,
            client_type=client_type,
            dry_run=dry_run,
        )
        if reload_result is not None:
            return reload_result
        return {
            "ok": True,
            **helper.record_project_init_validation(
                project_root=project_root,
                validation_mode=validation_mode,
                validation_results=validation_results,
                client_type=client_type,
                dry_run=dry_run,
            ),
        }
    except Exception as exc:
        return _error(exc)


@server.tool()
def cf_project_init_record_validation(
    project_root: str,
    validation_mode: str,
    validation_results: dict[str, Any] | None = None,
    client_type: str = DEFAULT_CLIENT_TYPE,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Record validation choice/results with the project-init tool id.

    For validation_mode="validate_now", first call a target-client-visible safe
    probe tool for each selected service. Then pass validation_results as a
    top-level object keyed by selected service binding, normalized binding key,
    or service identity id, for example:
    {"context7:canonical": {"status": "passed", "target_client_visible": true,
    "target_client": "opencode",
    "proof_kind": "target_client_safe_probe_result",
    "safe_probe_result": "passed", "safe_probe_id": "resolve-library-id",
    "tool_name": "context7_context7-local-resolve-library-id",
    "result_summary": "brief summary of the actual tool output",
    "verification_trace_refs": ["contextforge://control-plane/traces/context7:canonical-target-client"]}}.
    Do not call validate_now with missing or empty validation_results. Do not
    invent validation_results before calling the target-client service tool. Do
    not nest results under {"services": ...}.
    """
    return record_project_init_validation(
        project_root=project_root,
        validation_mode=validation_mode,
        validation_results=validation_results,
        client_type=client_type,
        dry_run=dry_run,
    )


@server.tool()
def record_project_init_client_reload(
    project_root: str,
    client_type: str = DEFAULT_CLIENT_TYPE,
    validation_mode: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Record that the target client has been reloaded after project activation.

    If the resumed user turn already chose validation or skip validation, pass
    validation_mode="validate_now" or "presume_working" so the helper can carry
    that intent forward without asking the same validation-choice question
    again. Reload acknowledgement is not service validation proof.
    """
    try:
        _require_user_reload_text(project_root)
        return {
            "ok": True,
            **helper.record_project_init_client_reload(
                project_root=project_root,
                client_type=client_type,
                validation_mode=validation_mode,
                dry_run=dry_run,
            ),
        }
    except Exception as exc:
        return _error(exc)


@server.tool()
def cf_project_init_record_client_reload(
    project_root: str,
    client_type: str = DEFAULT_CLIENT_TYPE,
    validation_mode: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Alias for record_project_init_client_reload with the project-init tool id."""
    return record_project_init_client_reload(
        project_root=project_root,
        client_type=client_type,
        validation_mode=validation_mode,
        dry_run=dry_run,
    )


if __name__ == "__main__":
    server.run()
