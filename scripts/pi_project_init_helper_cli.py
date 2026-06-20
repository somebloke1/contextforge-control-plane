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


def _project_root(data: Mapping[str, Any]) -> str:
    value = data.get("project_root") or data.get("projectRoot")
    if not value:
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


def _service_onboarding_helper():
    import control_plane_service_onboarding_helper

    return control_plane_service_onboarding_helper


def _service_onboarding_descriptor(data: Mapping[str, Any]) -> dict[str, Any]:
    descriptor = data.get("descriptor")
    if isinstance(descriptor, Mapping):
        return dict(descriptor)
    service = data.get("candidate_service") or data.get("candidateService") or data.get("service")
    source_path = data.get("source_path") or data.get("sourcePath") or data.get("path")
    expected_tools = data.get("expected_tools") or data.get("expectedTools")
    if isinstance(expected_tools, str):
        expected_tools = [expected_tools]
    source_evidence = []
    if source_path and not _synthetic_source_summary(str(source_path)):
        source_evidence.append({"type": "local_path", "ref": str(source_path)})
    operator_goal = data.get("operator_goal") or data.get("operatorGoal") or data.get("goal")
    if not operator_goal and service:
        operator_goal = f"Prepare a source-only onboarding plan for the uncataloged MCP service {service}."
    return {
        "candidate_service": str(service) if service else None,
        "operator_goal": operator_goal,
        "source_evidence": source_evidence,
        "classification": {
            "plan_type": data.get("plan_type") or data.get("planType") or "source_only_scaffolding",
            "localization_type": data.get("localization_type") or data.get("localizationType"),
            "functional_type": data.get("functional_type") or data.get("functionalType"),
            "transport_type": data.get("transport_type") or data.get("transportType"),
            "state_type": data.get("state_type") or data.get("stateType"),
            "approval_type": data.get("approval_type") or data.get("approvalType") or "source_only",
        },
        "credential_boundary": data.get("credential_boundary") or data.get("credentialBoundary"),
        "credential_required": data.get("credential_required") or data.get("credentialRequired"),
        "expected_tools": expected_tools if isinstance(expected_tools, list) else [],
        "validation_probe_plan": data.get("validation_probe_plan") or data.get("validationProbePlan") or [],
        "footprint": data.get("footprint") if isinstance(data.get("footprint"), Mapping) else {},
    }


def _compact_known_classifications(record: Mapping[str, Any]) -> list[str]:
    items: list[str] = []
    classification = record.get("classification")
    if not isinstance(classification, Mapping):
        return items
    labels = {
        "plan_type": "plan",
        "localization_type": "scope",
        "functional_type": "function",
        "transport_type": "transport",
        "state_type": "state footprint",
        "approval_type": "approval boundary",
    }
    values = {
        "source_only_scaffolding": "source-only planning",
        "project_scoped": "project-scoped",
        "search_retrieval": "search/retrieval",
        "stdio": "stdio",
        "project_metadata": "project metadata",
        "local_filesystem_state": "local filesystem state",
        "source_only": "source-only",
    }
    for key, value in classification.items():
        if isinstance(value, Mapping) and value.get("status") == "known" and value.get("value"):
            label = labels.get(str(key), str(key).replace("_", " "))
            display = values.get(str(value["value"]), str(value["value"]).replace("_", " "))
            items.append(f"{label}: {display}")
    return items


def _service_onboarding_visible_response(record: Mapping[str, Any]) -> str:
    candidate = record.get("candidate_service") or "the candidate service"
    status = record.get("status") or "unknown"
    blockers = record.get("blockers")
    if status == "needs_user_input" or (isinstance(blockers, list) and blockers):
        questions = [
            str(item)
            for item in record.get("next_questions", [])
            if isinstance(item, str) and item.strip()
        ]
        lines = [
            f"I can help onboard `{candidate}` as an uncataloged MCP service, and this will stay source-only until a later explicit runtime approval.",
            "Please provide the source reference or local path, transport type, credential boundary, project or user scope, expected tools, lifecycle/cleanup expectations, and proof plan.",
            "No service has been installed, registered, started, exposed, imported, validated, probed, or made available to this client.",
        ]
        if questions:
            lines.append("Next questions: " + " ".join(questions[:4]))
        return "\n".join(lines)
    known = _compact_known_classifications(record)
    questions = [
        str(item)
        for item in record.get("next_questions", [])
        if isinstance(item, str) and item.strip()
    ]
    gate = record.get("pre_runtime_workflow_gate")
    missing = []
    if isinstance(gate, Mapping):
        missing = [
            str(item)
            for item in gate.get("missing_dimensions", [])
            if isinstance(item, str) and item.strip()
        ]
    lines = [
        f"I have a source-only onboarding plan for `{candidate}`.",
        f"Status: `{status}`.",
        "Credentials: no secret values were requested, stored, or validated; credential handling remains source-evidence only.",
    ]
    if known:
        lines.append("Known classifications: " + ", ".join(known) + ".")
    if missing:
        lines.append("Still needed before runtime work: " + ", ".join(missing) + ".")
    if questions:
        lines.append("Next questions: " + " ".join(questions[:4]))
    lines.extend(
        [
            "No service has been installed, registered, started, exposed, imported, or made available to this client.",
            "A later runtime phase would need explicit approval plus source evidence, transport proof, lifecycle/cleanup boundaries, and a bounded proof plan.",
        ]
    )
    return "\n".join(lines)


def _synthetic_source_summary(value: str) -> bool:
    lowered = value.strip().lower()
    return (
        lowered.startswith("user-supplied:")
        or lowered.startswith("description:")
        or lowered.startswith("summary:")
        or "reads project notes" in lowered
    )


def _build_service_onboarding_plan(project_root: str, data: Mapping[str, Any]) -> dict[str, Any]:
    record = _service_onboarding_helper().build_onboarding_record(
        _service_onboarding_descriptor(data),
        project_root=project_root,
        issue=str(data.get("issue") or data.get("issue_number") or data.get("issueNumber") or ""),
        session_id=str(data.get("session_id") or data.get("sessionId") or "") or None,
    )
    return {
        "status": "source_only_onboarding_plan",
        "project_root": project_root,
        "mutation_allowed": False,
        "assistant_visible_response": _service_onboarding_visible_response(record),
        "record": record,
        "non_actions": record.get("non_actions") or [],
    }


def dispatch(operation: str, data: Mapping[str, Any]) -> dict[str, Any]:
    project_root = _project_root(data)
    client_type = str(data.get("client_type") or data.get("clientType") or "pi")
    if operation == "render_project_init_prompt":
        return _ok(_render_prompt(project_root, client_type=client_type))
    if operation == "get_project_context":
        return _mcp_helper().client_visible_project_init_payload(
            _ok(helper.helper_readiness(project_root=project_root, client_type=client_type))
        )
    if operation == "get_project_tool_availability":
        return _mcp_helper().client_visible_project_tool_availability_payload(
            _mcp_helper().project_tool_availability(project_root=project_root, client_type=client_type)
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
