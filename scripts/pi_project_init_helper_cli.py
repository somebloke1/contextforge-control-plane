#!/usr/bin/env python3
"""Pi-facing CLI wrapper for ContextForge project-init helper operations."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path
from typing import Any, Mapping

import control_plane_project_init_helper as helper
import control_plane_service_onboarding_surfaces as service_onboarding_surfaces
from project_init_common import project_identity, read_project_env


def _ok(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {"ok": True, **dict(payload)}


def _error(exc: Exception) -> dict[str, Any]:
    return {"ok": False, "error": {"type": exc.__class__.__name__, "message": str(exc)}}


def _payload(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("payload JSON must be an object")
    return data


def _project_root(data: Mapping[str, Any], *, default_to_cwd: bool = False) -> str:
    value = data.get("project_root") or data.get("projectRoot") or data.get("cwd") or data.get("session_cwd") or data.get("sessionCwd")
    if not value:
        if default_to_cwd:
            return str(Path.cwd())
        raise ValueError("project_root is required")
    return str(value)


def _plan_object(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("plan object is required")
    plan = dict(value)
    plan.pop("ok", None)
    return plan


def _render_prompt(project_root: str, *, client_type: str = "pi") -> dict[str, Any]:
    import codex_project_init_hook as prompt_hook
    import contextforge_mcp_wrapper as gateway

    root = Path(project_root).expanduser().resolve(strict=False)
    identity = project_identity(root)
    values = read_project_env(root)
    args = prompt_hook.prompt_args(identity, values, target_client=client_type)
    source = "local_template"
    text = ""
    try:
        env = gateway._read_env(gateway.CONFIG_ENV)
        token = gateway._token(env["PLATFORM_ADMIN_EMAIL"], env["PLATFORM_ADMIN_PASSWORD"])
        prompt_id = prompt_hook.get_prompt_id(token)
        if prompt_id:
            rendered = gateway._request("POST", f"/prompts/{prompt_id}", token=token, body=args)
            candidate = prompt_hook.rendered_prompt_text(rendered)
            if prompt_hook.prompt_text_is_fresh(candidate):
                text = candidate
                source = "contextforge_prompt_library"
    except Exception:
        text = ""
    if not text:
        text = prompt_hook.render_local_prompt(args)
    return {
        "status": "rendered",
        "source": source,
        "project_root": str(root),
        "client_type": client_type,
        "prompt_text": text,
        "non_actions": [
            "does not mutate ContextForge prompt/resource catalog",
            "does not write project files",
            "does not mutate user-global Pi config or extensions",
        ],
    }


def _mcp_helper():
    import contextforge_helper_mcp

    return contextforge_helper_mcp


def _build_service_onboarding_plan(project_root: str, data: Mapping[str, Any]) -> dict[str, Any]:
    return service_onboarding_surfaces.build_service_onboarding_plan(project_root, data)


def _build_service_onboarding_continuation(project_root: str, data: Mapping[str, Any]) -> dict[str, Any]:
    return service_onboarding_surfaces.build_service_onboarding_continuation(project_root, data)


def dispatch(operation: str, data: Mapping[str, Any]) -> dict[str, Any]:
    project_root = _project_root(
        data,
        default_to_cwd=operation in {"reset_current_project", "cf_project_reset_current_project"},
    )
    client_type = str(data.get("client_type") or data.get("clientType") or "pi")
    if operation == "render_project_init_prompt":
        return _ok(_render_prompt(project_root, client_type=client_type))
    if operation == "get_project_context":
        return _mcp_helper().client_visible_project_init_payload(
            _ok(helper.helper_readiness(project_root=project_root, client_type=client_type))
        )
    if operation == "get_project_tool_availability":
        return _mcp_helper().client_visible_project_tool_availability_payload(
            _mcp_helper().project_tool_availability(
                project_root=project_root,
                client_type=client_type,
                target_client_runtime=data.get("target_client_runtime") if isinstance(data.get("target_client_runtime"), Mapping) else None,
            )
        )
    if operation == "get_project_capability_summary":
        return _mcp_helper().client_visible_project_capability_summary_payload(
            _mcp_helper().project_capability_summary(project_root=project_root, client_type=client_type)
        )
    if operation == "get_project_state_readback":
        return _mcp_helper().client_visible_project_state_readback_payload(
            _mcp_helper().project_state_readback(project_root=project_root, client_type=client_type)
        )
    if operation == "build_service_onboarding_plan":
        return _ok(_build_service_onboarding_plan(project_root, data))
    if operation in {"build_service_onboarding_continuation", "cf_project_service_onboarding_continue"}:
        return _ok(_build_service_onboarding_continuation(project_root, data))
    if operation == "get_service_onboarding_how_to":
        return _ok(service_onboarding_surfaces.hidden_onboarding_guidance(data))
    if operation == "list_available_capabilities":
        result = _ok(
            helper.list_available_capabilities(
                project_root=project_root,
                client_type=client_type,
                contextforge_servers=data.get("contextforge_servers") or data.get("contextforgeServers"),
            )
        )
        return _mcp_helper().client_visible_project_init_payload(result)
    if operation == "propose_project_init":
        return _mcp_helper().propose_project_init(
            project_root,
            data.get("selected_services") or data.get("selectedServices") or [],
            client_type=client_type,
            inputs=data.get("inputs"),
            contextforge_servers=data.get("contextforge_servers") or data.get("contextforgeServers"),
            server_instances_root=data.get("server_instances_root") or data.get("serverInstancesRoot"),
        )
    if operation == "approve_project_init_plan":
        plan = _plan_object(data.get("plan"))
        approval = data.get("approval")
        if not isinstance(approval, Mapping):
            raise ValueError("approval object is required")
        return _mcp_helper().approve_project_init_plan(project_root, plan, dict(approval))
    if operation == "cf_project_init_approve":
        challenge_id = str(data.get("challenge_id") or data.get("challengeId") or "")
        plan_digest = str(data.get("plan_digest") or data.get("planDigest") or "")
        return _mcp_helper().cf_project_init_approve(project_root, challenge_id, plan_digest)
    if operation == "cf_project_init_continue":
        return _mcp_helper().cf_project_init_continue(
            project_root,
            client_type=client_type,
            dry_run=bool(data.get("dry_run") or data.get("dryRun")),
        )
    if operation == "apply_approved_project_init":
        plan = _plan_object(data.get("plan"))
        receipts = data.get("receipts")
        if not isinstance(receipts, list):
            raise ValueError("receipts array is required")
        return _mcp_helper().apply_approved_project_init(
            project_root,
            plan,
            receipts,
            contextforge_servers=data.get("contextforge_servers") or data.get("contextforgeServers"),
            dry_run=bool(data.get("dry_run") or data.get("dryRun")),
        )
    if operation == "cf_project_init_apply":
        return _mcp_helper().cf_project_init_apply(
            project_root,
            receipts=data.get("receipts") if isinstance(data.get("receipts"), list) else None,
            contextforge_servers=data.get("contextforge_servers") or data.get("contextforgeServers"),
            dry_run=bool(data.get("dry_run") or data.get("dryRun")),
        )
    if operation in {"reset_current_project", "cf_project_reset_current_project"}:
        return _mcp_helper().cf_project_reset_current_project(
            project_root,
            client_type=client_type,
            profile=str(data.get("profile") or "project_init_base"),
            preserve_evidence=bool(data.get("preserve_evidence", data.get("preserveEvidence", True))),
            dry_run=bool(data.get("dry_run") or data.get("dryRun")),
        )
    if operation == "record_project_init_client_reload":
        return _ok(
            helper.record_project_init_client_reload(
                project_root=project_root,
                client_type=client_type,
                validation_mode=data.get("validation_mode") or data.get("validationMode"),
                dry_run=bool(data.get("dry_run") or data.get("dryRun")),
            )
        )
    if operation == "repair_pending_project_init_config":
        result = _ok(
            helper.repair_pending_project_init_config(
                project_root=project_root,
                client_type=client_type,
                contextforge_servers=data.get("contextforge_servers") or data.get("contextforgeServers"),
                server_instances_root=data.get("server_instances_root") or data.get("serverInstancesRoot"),
                dry_run=bool(data.get("dry_run") or data.get("dryRun")),
            )
        )
        return _mcp_helper().client_visible_project_init_payload(result)
    raise ValueError(f"unsupported operation: {operation}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a ContextForge project-init helper operation for the Pi extension shim.")
    parser.add_argument("--operation", required=True)
    parser.add_argument("--payload-json")
    args = parser.parse_args(argv)
    try:
        captured_stdout = io.StringIO()
        with contextlib.redirect_stdout(captured_stdout):
            result = dispatch(args.operation, _payload(args.payload_json))
        logs = captured_stdout.getvalue()
        if logs:
            sys.stderr.write(logs)
    except Exception as exc:
        result = _error(exc)
    json.dump(result, sys.stdout, sort_keys=True)
    sys.stdout.write("\n")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
