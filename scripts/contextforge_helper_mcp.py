#!/usr/bin/env python3
"""MCP wrapper for ContextForge helper project-init workflow tools."""

from __future__ import annotations

import hashlib
import json
import os
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


def _remember_plan(project_root: str, plan: dict[str, Any]) -> dict[str, Any]:
    _CACHED_PLANS[_cache_key(project_root)] = dict(plan)
    current = _read_durable_cache(project_root)
    _write_durable_cache(project_root, {**current, "plan": dict(plan)})
    return plan


def _remember_receipts(project_root: str, receipts: list[dict[str, Any]]) -> None:
    _CACHED_RECEIPTS[_cache_key(project_root)] = list(receipts)
    current = _read_durable_cache(project_root)
    _write_durable_cache(project_root, {**current, "receipts": list(receipts)})


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
def get_project_context(project_root: str, client_type: str = "codex") -> dict[str, Any]:
    """Return helper readiness and local project-root attestation."""
    try:
        return {"ok": True, **helper.helper_readiness(project_root=project_root, client_type=client_type)}
    except Exception as exc:
        return _error(exc)


@server.tool()
def cf_project_init_get_context(project_root: str, client_type: str = "codex") -> dict[str, Any]:
    """Alias for get_project_context with the project-init tool id."""
    return get_project_context(project_root=project_root, client_type=client_type)


@server.tool()
def list_available_capabilities(
    project_root: str,
    client_type: str = "codex",
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
    client_type: str = "codex",
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
    client_type: str = "codex",
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
    client_type: str = "codex",
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
    client_type: str = "codex",
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
    client_type: str = "codex",
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
        cached_receipts = receipts if receipts is not None else _CACHED_RECEIPTS.get(_cache_key(project_root))
        if cached_receipts is None:
            durable = _read_durable_cache(project_root)
            durable_receipts = durable.get("receipts") if isinstance(durable.get("receipts"), list) else None
            if durable_receipts is not None:
                cached_receipts = list(durable_receipts)
                _CACHED_RECEIPTS[_cache_key(project_root)] = cached_receipts
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
    client_type: str = "codex",
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
    client_type: str = "codex",
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
    client_type: str = "codex",
    dry_run: bool = False,
) -> dict[str, Any]:
    """Record validation choice/results.

    For validation_mode="validate_now", first call a target-client-visible safe
    probe tool for each selected service. Then pass validation_results as a
    top-level object keyed by selected service binding, normalized binding key,
    or service identity id, for example:
    {"context7:canonical": {"status": "passed", "target_client_visible": true,
    "proof_kind": "target_client_safe_probe_result",
    "safe_probe_result": "passed", "safe_probe_id": "resolve-library-id",
    "verification_trace_refs": ["contextforge://control-plane/traces/context7:canonical-target-client"]}}.
    Do not call validate_now with missing or empty validation_results. Do not
    nest results under {"services": ...}.
    """
    try:
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
    client_type: str = "codex",
    dry_run: bool = False,
) -> dict[str, Any]:
    """Record validation choice/results with the project-init tool id.

    For validation_mode="validate_now", first call a target-client-visible safe
    probe tool for each selected service. Then pass validation_results as a
    top-level object keyed by selected service binding, normalized binding key,
    or service identity id, for example:
    {"context7:canonical": {"status": "passed", "target_client_visible": true,
    "proof_kind": "target_client_safe_probe_result",
    "safe_probe_result": "passed", "safe_probe_id": "resolve-library-id",
    "verification_trace_refs": ["contextforge://control-plane/traces/context7:canonical-target-client"]}}.
    Do not call validate_now with missing or empty validation_results. Do not
    nest results under {"services": ...}.
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
    client_type: str = "codex",
    dry_run: bool = False,
) -> dict[str, Any]:
    """Record that the target client has been reloaded after project activation."""
    try:
        return {
            "ok": True,
            **helper.record_project_init_client_reload(
                project_root=project_root,
                client_type=client_type,
                dry_run=dry_run,
            ),
        }
    except Exception as exc:
        return _error(exc)


@server.tool()
def cf_project_init_record_client_reload(
    project_root: str,
    client_type: str = "codex",
    dry_run: bool = False,
) -> dict[str, Any]:
    """Alias for record_project_init_client_reload with the project-init tool id."""
    return record_project_init_client_reload(
        project_root=project_root,
        client_type=client_type,
        dry_run=dry_run,
    )


if __name__ == "__main__":
    server.run()
