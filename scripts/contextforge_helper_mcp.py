#!/usr/bin/env python3
"""MCP wrapper for ContextForge helper project-init workflow tools."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Mapping

from mcp.server.fastmcp import FastMCP

import control_plane_project_init_helper as helper
import control_plane_project_state as project_state
import project_init_common as common


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


_CLIENT_HIDDEN_KEYS = frozenset(
    {
        "planned_state",
        "validation_plan",
        "validation_policy",
        "validation_records",
        "validation_results",
        "validation_result_shape",
        "validation_mode",
        "validation_status",
        "x_validation_mode",
        "safe_default",
        "safe_operations",
        "safe_probe_id",
        "safe_probe_result",
        "probe_contract",
        "proof_kind",
        "target_client_proof_layers",
        "accepted_proof_kinds",
        "allowed_tool_name_patterns",
        "default_probe",
        "client_reload_requirement",
        "job",
        "recovery_state",
        "approval_challenge",
        "challenge_id",
        "plan_digest",
        "plan_id",
        "receipt_refs",
        "receipts",
    }
)


def client_visible_project_init_apply_payload(value: dict[str, Any]) -> dict[str, Any]:
    """Return the narrow install-only public DTO for apply-style results."""

    cleaned = client_visible_project_init_payload(value)
    keep_keys = [
        "ok",
        "project_root",
        "dry_run",
        "approval_scope",
        "state_status",
        "selected_service_bindings",
        "writes",
        "non_actions",
        "state_revision",
        "installation_mode",
        "installation_status",
        "installed_service_bindings",
        "message",
        "next_turn",
        "status",
        "error",
    ]
    public = {key: cleaned[key] for key in keep_keys if key in cleaned}
    if cleaned.get("installation_status") == "installed":
        installed = [str(binding) for binding in cleaned.get("installed_service_bindings") or [] if str(binding)]
        installed_text = ", ".join(installed)
        next_turn_value = cleaned.get("next_turn") if isinstance(cleaned.get("next_turn"), Mapping) else {}
        reload_prompt = str(next_turn_value.get("prompt") or "").strip()
        if reload_prompt.startswith("ContextForge tools are installed for this project. "):
            reload_prompt = reload_prompt.removeprefix("ContextForge tools are installed for this project. ")
        if installed_text:
            public["message"] = (
                f"ContextForge tools are installed for this project: {installed_text}. "
                f"{reload_prompt or 'A new session or reload is required before the tools register in the client.'}"
            )
        elif "message" not in public:
            public["message"] = "ContextForge tools are installed for this project. A new session or reload is required before the tools register in the client."
    return public


def client_visible_project_init_list_payload(value: dict[str, Any]) -> dict[str, Any]:
    """Return only the service menu needed for client-facing selection."""

    cleaned = client_visible_project_init_payload(value)
    public: dict[str, Any] = {
        key: cleaned[key]
        for key in ("ok", "client_type", "root_attestation", "status", "assistant_visible_response", "alignment_import_offer", "next_turn", "non_actions", "error")
        if key in cleaned
    }
    services = []
    for service in cleaned.get("available_services") or []:
        if not isinstance(service, dict):
            continue
        services.append(
            {
                key: service[key]
                for key in (
                    "service_binding",
                    "display_name",
                    "activation_class",
                    "scope_label",
                    "user_visible_effect",
                    "project_service_state",
                    "target_client_projection_status",
                    "target_client_state",
                    "available_to_target_client",
                    "recommended_action",
                )
                if key in service
            }
        )
    if services:
        public["available_services"] = services
    return public


def client_visible_project_init_plan_payload(value: dict[str, Any], *, include_next_turn: bool = True) -> dict[str, Any]:
    """Return the narrow approval package needed for client-facing consent."""

    cleaned = client_visible_project_init_payload(value)
    keep_keys = [
        "ok",
        "workflow",
        "client_type",
        "project_root",
        "required_inputs",
        "skipped_services",
        "plan_summary",
        "installation_mode",
        "non_actions",
        "next_turn",
        "status",
        "error",
    ]
    public = {key: cleaned[key] for key in keep_keys if key in cleaned}
    if "selected_service_bindings" not in public:
        public["selected_service_bindings"] = [
            str(service.get("service_binding"))
            for service in cleaned.get("selected_services") or []
            if isinstance(service, dict) and service.get("service_binding")
        ]
    if "message" not in public and isinstance(cleaned.get("plan_summary"), dict):
        summary = cleaned["plan_summary"]
        bindings = summary.get("bindings") if isinstance(summary.get("bindings"), list) else []
        service_names = ", ".join(
            str(binding.get("service_binding"))
            for binding in bindings
            if isinstance(binding, dict) and binding.get("service_binding")
        ) or ", ".join(public.get("selected_service_bindings") or [])
        writes = summary.get("project_local_writes") if isinstance(summary.get("project_local_writes"), list) else []
        writes_text = ", ".join(str(path) for path in writes) or "project-local ContextForge state"
        required_inputs = _visible_required_input_summary(cleaned.get("required_inputs"))
        input_text = f" Required inputs: {required_inputs}." if required_inputs else ""
        public["message"] = (
            f"Plan ready for {service_names}. It will write {writes_text}; "
            "it will not mutate user-global config, secrets, backend services, or the ContextForge registry."
            f"{input_text} "
            "Approve or decline?"
        )
    if "message" not in public and isinstance(cleaned.get("next_turn"), dict):
        next_turn_value = cleaned["next_turn"]
        prompt = str(next_turn_value.get("prompt") or "").strip()
        choices = next_turn_value.get("choices") if isinstance(next_turn_value.get("choices"), list) else []
        rendered_choices = []
        for choice in choices:
            if not isinstance(choice, Mapping):
                continue
            number = choice.get("number")
            label = str(choice.get("label") or choice.get("id") or "").strip()
            effect = str(choice.get("effect") or "").strip()
            if isinstance(number, int) and label:
                rendered_choices.append(f"{number}. {label}" + (f" - {effect}" if effect else ""))
        if prompt:
            public["message"] = "\n".join([prompt, *rendered_choices]) if rendered_choices else prompt
    if public.get("message"):
        visible_message = str(public["message"])
        reordered: dict[str, Any] = {
            "ok": public.get("ok", True),
            "assistant_visible_response": visible_message,
            "message": visible_message,
        }
        for key in (
            "workflow",
            "client_type",
            "project_root",
            "selected_service_bindings",
            "installation_mode",
            "non_actions",
            "status",
            "error",
        ):
            if key in public and key not in reordered:
                reordered[key] = public[key]
        if public.get("required_inputs"):
            for key, item in public.items():
                if key not in reordered:
                    reordered[key] = item
        public = reordered
    if not include_next_turn:
        public.pop("next_turn", None)
    return public


def _visible_required_input_summary(value: Any) -> str:
    if not isinstance(value, Mapping):
        return ""
    parts: list[str] = []
    for service_binding, service_inputs in value.items():
        if not isinstance(service_inputs, Mapping):
            continue
        rendered = ", ".join(
            f"{key}={service_inputs[key]}"
            for key in sorted(service_inputs)
            if service_inputs.get(key)
        )
        if rendered:
            parts.append(f"{service_binding} {rendered}")
    return "; ".join(parts)


def client_visible_project_init_decision_payload(value: dict[str, Any]) -> dict[str, Any]:
    """Return the narrow public DTO for decline/defer decisions."""

    cleaned = client_visible_project_init_payload(value)
    keep_keys = [
        "ok",
        "assistant_visible_response",
        "message",
        "copy_as_complete_visible_response",
        "do_not_summarize",
        "project_root",
        "client_type",
        "decision_state",
        "selected_service_bindings",
        "state_revision",
        "non_actions",
        "status",
        "error",
    ]
    public = {key: cleaned[key] for key in keep_keys if key in cleaned}
    if "assistant_visible_response" in public:
        public["message"] = public["assistant_visible_response"]
        public["copy_as_complete_visible_response"] = True
        public["do_not_summarize"] = True
    return public


def client_visible_project_tool_availability_payload(value: dict[str, Any]) -> dict[str, Any]:
    """Return the normal-use read-only availability DTO for initialized projects."""

    cleaned = client_visible_project_init_payload(value)
    keep_keys = [
        "ok",
        "assistant_visible_response",
        "message",
        "copy_as_complete_visible_response",
        "do_not_summarize",
        "non_actions",
        "status",
        "error",
    ]
    public = {key: cleaned[key] for key in keep_keys if key in cleaned}
    if "assistant_visible_response" in public:
        public["message"] = public["assistant_visible_response"]
        public["copy_as_complete_visible_response"] = True
        public["do_not_summarize"] = True
    return public


def client_visible_project_capability_summary_payload(value: dict[str, Any]) -> dict[str, Any]:
    """Return the normal-use read-only capability-summary DTO."""

    cleaned = client_visible_project_init_payload(value)
    keep_keys = [
        "ok",
        "assistant_visible_response",
        "message",
        "copy_as_complete_visible_response",
        "do_not_summarize",
        "non_actions",
        "status",
        "error",
    ]
    public = {key: cleaned[key] for key in keep_keys if key in cleaned}
    if "assistant_visible_response" in public:
        public["message"] = public["assistant_visible_response"]
        public["copy_as_complete_visible_response"] = True
        public["do_not_summarize"] = True
    return public


def client_visible_project_state_readback_payload(value: dict[str, Any]) -> dict[str, Any]:
    """Return the normal-use read-only project-state readback DTO."""

    cleaned = client_visible_project_init_payload(value)
    keep_keys = [
        "ok",
        "assistant_visible_response",
        "message",
        "copy_as_complete_visible_response",
        "do_not_summarize",
        "non_actions",
        "status",
        "error",
    ]
    public = {key: cleaned[key] for key in keep_keys if key in cleaned}
    if "assistant_visible_response" in public:
        public["message"] = public["assistant_visible_response"]
        public["copy_as_complete_visible_response"] = True
        public["do_not_summarize"] = True
    return public


def client_visible_project_init_payload(value: Any) -> Any:
    """Remove retired project-init check/probe internals from client tool output."""

    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            if key in _CLIENT_HIDDEN_KEYS:
                continue
            if key == "verification_layers" and isinstance(item, dict):
                visible_layers = {
                    layer_key: client_visible_project_init_payload(layer_value)
                    for layer_key, layer_value in item.items()
                    if layer_key != "tool_policy"
                }
                if visible_layers:
                    cleaned[key] = visible_layers
                continue
            cleaned[key] = client_visible_project_init_payload(item)
        return cleaned
    if isinstance(value, list):
        return [client_visible_project_init_payload(item) for item in value]
    return value


def _tool_names_for_service(service_family: str) -> list[str]:
    policy = common.safe_validation_policy(service_family)
    contract = policy.get("probe_contract") if isinstance(policy.get("probe_contract"), Mapping) else {}
    names = contract.get("allowed_tool_name_patterns") if isinstance(contract.get("allowed_tool_name_patterns"), list) else []
    return [str(name) for name in names if str(name)]


def _service_family_from_state(binding_id: str, service: Mapping[str, Any]) -> str:
    return str(
        service.get("service_family")
        or service.get("canonical_service")
        or binding_id.split(":", 1)[0]
        or binding_id
    )


def _state_skipped_or_unavailable(service: Mapping[str, Any]) -> dict[str, Any] | None:
    status = str(
        service.get("status")
        or service.get("contextforge_readback_status")
        or service.get("provision_status")
        or ""
    ).lower()
    if status in {"skipped", "unavailable", "missing", "blocked", "failed"}:
        return {
            "service_binding": str(service.get("service_binding") or ""),
            "status": status,
            "reason": str(service.get("skipped_reason") or service.get("reason") or service.get("x_reason") or "reported unavailable"),
        }
    return None


def _tool_policy_status_for_service(service: Mapping[str, Any], tool_names: list[str]) -> str:
    layers = service.get("verification_layers")
    if isinstance(layers, Mapping):
        tool_policy = layers.get("tool_policy")
        if isinstance(tool_policy, Mapping) and tool_policy.get("status"):
            return str(tool_policy.get("status"))
    return "known" if tool_names else "not_recorded"


def _target_client_projection_status(target_client_state: Mapping[str, Any]) -> str:
    status = str(target_client_state.get("status") or "not_recorded")
    if status == "not_recorded":
        return "missing"
    if status == "blocked":
        return "blocked"
    return "recorded"


def _target_client_visibility_status(target_client_state: Mapping[str, Any]) -> str:
    if _target_client_projection_status(target_client_state) == "missing":
        return "not_claimed"
    if target_client_state.get("target_client_visible") is True:
        return "visible_proof_recorded"
    return "not_proven_by_readback"


def _target_client_proof_status(target_client_state: Mapping[str, Any]) -> str:
    if _target_client_projection_status(target_client_state) == "missing":
        return "not_recorded"
    if target_client_state.get("proof_ref"):
        return "proof_ref_recorded"
    return "not_claimed_by_readback"


def _missing_projection_action(service_binding: str, client_type: str) -> dict[str, str]:
    return {
        "action": "align_target_client_to_existing_project_service",
        "target_client": client_type,
        "service_binding": service_binding,
        "boundary": (
            f"Align/import {client_type} to the existing project service instance; "
            "do not create a new project service instance unless explicitly approved."
        ),
    }


def _project_client_reload_state(state: Mapping[str, Any], client_type: str) -> dict[str, Any]:
    project_init = state.get("project_init") if isinstance(state.get("project_init"), Mapping) else {}
    client_states = project_init.get("client_states") if isinstance(project_init.get("client_states"), Mapping) else {}
    client_state = client_states.get(client_type) if isinstance(client_states.get(client_type), Mapping) else {}
    reload_status = str(client_state.get("reload_status") or "unknown")
    requires_reload = reload_status in {"required", "pending_reload", "reload_observed"}
    acknowledged = reload_status in {"acknowledged", "reload_acknowledged"}
    if acknowledged:
        user_status = "reload_acknowledged"
    elif requires_reload:
        user_status = "reload_required"
    elif reload_status == "not_required":
        user_status = "reload_not_required"
    else:
        user_status = "reload_status_unknown"
    return {
        "client_type": client_type,
        "reload_status": reload_status,
        "user_status": user_status,
        "requires_reload": requires_reload,
        "reload_acknowledged": acknowledged,
    }


def _client_session_boundary(state: Mapping[str, Any], client_type: str) -> dict[str, Any]:
    reload_state = _project_client_reload_state(state, client_type)
    reload_requirement = common.client_reload_requirement(client_type, event="project_activation_apply")
    if reload_state["reload_acknowledged"]:
        if client_type == "pi":
            instruction = "Pi reload has been acknowledged for this project state; no additional Pi reload is recorded as pending."
        elif client_type == "opencode":
            instruction = "A new OpenCode session has been acknowledged for this project state; no additional OpenCode session restart is recorded as pending."
        else:
            instruction = "The required client reload or new session has been acknowledged for this project state; no additional reload is recorded as pending."
    elif isinstance(reload_requirement, Mapping):
        instruction = str(reload_requirement.get("instruction") or "")
    else:
        instruction = "This client can use the current project-state readback without a separate reload requirement recorded for project activation."
    return {
        **reload_state,
        "instruction": instruction,
    }


def _target_client_user_state(target_client_state: Mapping[str, Any], session_boundary: Mapping[str, Any]) -> str:
    if session_boundary.get("reload_acknowledged"):
        return "projection recorded; reload acknowledged"
    status = str(target_client_state.get("status") or "recorded")
    if session_boundary.get("requires_reload"):
        return "projection recorded; client reload required"
    if status == "not_recorded":
        return "client state not_recorded"
    if status == "blocked":
        return "blocked"
    return "projection recorded"


def project_tool_availability(project_root: str, client_type: str = DEFAULT_CLIENT_TYPE) -> dict[str, Any]:
    """Read initialized project state and summarize client-visible ContextForge tools."""

    root = project_state.validate_project_root(project_root, require_workspace=True)
    state = project_state.load_state(root)
    services = state.get("services") if isinstance(state.get("services"), Mapping) else {}
    available_tools: list[dict[str, Any]] = []
    project_services: list[dict[str, Any]] = []
    project_tool_policies: list[dict[str, Any]] = []
    missing_target_client_projection: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    approved: list[str] = []
    decision_bindings: set[str] = set()
    decisions = state.get("decisions") if isinstance(state.get("decisions"), Mapping) else {}
    for decision_key, decision_value in decisions.items():
        if not isinstance(decision_value, Mapping):
            continue
        decision_state = str(decision_value.get("state") or "")
        if decision_state not in {"declined", "deferred", "disabled"}:
            continue
        binding = str(decision_value.get("service_binding") or decision_key)
        if not binding:
            continue
        decision_bindings.add(binding)
        skipped.append(
            {
                "service_binding": binding,
                "status": decision_state,
                "reason": str(decision_value.get("notes") or f"service was {decision_state} by project-local user decision"),
            }
        )
    for binding_id, service_value in services.items():
        if not isinstance(service_value, Mapping):
            continue
        service = dict(service_value)
        service.setdefault("service_binding", str(binding_id))
        service_binding = str(service.get("service_binding") or binding_id)
        if service_binding in decision_bindings:
            continue
        approved.append(service_binding)
        service_family = _service_family_from_state(service_binding, service)
        skipped_item = _state_skipped_or_unavailable(service)
        if skipped_item:
            skipped.append(skipped_item)
            continue
        tool_names = _tool_names_for_service(service_family)
        target_client_state = _client_state_for_service(service, client_type)
        projection_status = _target_client_projection_status(target_client_state)
        tool_policy_status = _tool_policy_status_for_service(service, tool_names)
        availability_item = {
            "service_binding": service_binding,
            "service_family": service_family,
            "project_service_state": "present",
            "provision_status": str(service.get("provision_status") or "unknown"),
            "target_client_state": target_client_state,
            "target_client_projection_status": projection_status,
            "tool_policy_status": tool_policy_status,
            "tool_policy_names": tool_names,
            "target_client_visibility_status": _target_client_visibility_status(target_client_state),
            "target_client_proof_status": _target_client_proof_status(target_client_state),
            "available_to_target_client": bool(projection_status == "recorded" and tool_names),
        }
        if projection_status == "missing":
            action = _missing_projection_action(service_binding, client_type)
            availability_item["recommended_action"] = action
            missing_target_client_projection.append(action)
        project_services.append(availability_item)
        project_tool_policies.append(
            {
                "service_binding": service_binding,
                "service_family": service_family,
                "project_service_state": "present",
                "tool_policy_status": tool_policy_status,
                "tool_policy_names": tool_names,
            }
        )
        if tool_names:
            if projection_status == "recorded":
                available_tools.append(
                    {
                        "service_binding": service_binding,
                        "service_family": service_family,
                        "tool_names": tool_names,
                        "project_service_state": "present",
                        "target_client_state": target_client_state,
                        "target_client_projection_status": projection_status,
                        "tool_policy_status": tool_policy_status,
                        "tool_policy_names": tool_names,
                        "available_to_target_client": True,
                    }
                )
    skipped_text = (
        "none reported"
        if not skipped
        else "; ".join(f"{item['service_binding']}: {item['status']} ({item['reason']})" for item in skipped)
    )
    tool_text = (
        "; ".join(
            f"{item['service_binding']} exposes {', '.join(item['tool_names'])}"
            for item in available_tools
        )
        or "no target-client projection/import recorded for the approved project services"
    )
    project_service_text = (
        ", ".join(item["service_binding"] for item in project_services)
        or "none recorded"
    )
    missing_projection_text = (
        "; ".join(
            f"{item['service_binding']}: align/import existing project service instance for {client_type}; do not create a new project service instance without explicit approval"
            for item in missing_target_client_projection
        )
        or "none recorded"
    )
    revision = project_state.state_revision(state)
    session_boundary = _client_session_boundary(state, client_type)
    refresh_boundary = session_boundary["instruction"]
    visible_response = (
        f"ContextForge state for {str(root)} is initialized at revision {revision}. "
        f"Project services present: {project_service_text}. "
        f"Configured/imported-tool policy for this client: {tool_text}. "
        f"Missing target-client projections: {missing_projection_text}. "
        f"Skipped or unavailable services: {skipped_text}. "
        "client-visible tool use is not proven by this readback; target-client-visible=false states remain unproven. "
        "This is a read-only project-state readback; interactive proof is not claimed by this readback. "
        f"Note: {refresh_boundary}"
    )
    return {
        "ok": True,
        "status": "available_tools_report",
        "client_type": client_type,
        "project_root": str(root),
        "state_status": state.get("status"),
        "state_revision": revision,
        "approved_service_bindings": approved,
        "available_tools": available_tools,
        "project_services": project_services,
        "project_tool_policies": project_tool_policies,
        "missing_target_client_projection": missing_target_client_projection,
        "skipped_or_unavailable_services": skipped,
        "current_session_boundary": session_boundary,
        "assistant_visible_response_policy": {
            "internal_status_terms_suppressed": True,
            "diagnostic_state_retained_in_structured_fields": True,
        },
        "assistant_visible_response": visible_response,
        "non_actions": [
            "read-only initialized-project availability report",
            "no service selection",
            "no project-init proposal, approval, or apply",
            "no tool probe or backend mutation",
        ],
    }


def project_capability_summary(project_root: str, client_type: str = DEFAULT_CLIENT_TYPE) -> dict[str, Any]:
    """Read project state and catalog candidates into a normal-language capability summary."""

    root = project_state.validate_project_root(project_root, require_workspace=True)
    state = project_state.load_state(root)
    tool_report = project_tool_availability(project_root=str(root), client_type=client_type)
    approved = set(str(item) for item in tool_report.get("approved_service_bindings") or [])
    project_services = [
        item
        for item in tool_report.get("project_services") or []
        if isinstance(item, Mapping)
    ]
    missing_projection = [
        item
        for item in tool_report.get("missing_target_client_projection") or []
        if isinstance(item, Mapping)
    ]
    unavailable_bindings = {
        str(item.get("service_binding") or "")
        for item in tool_report.get("skipped_or_unavailable_services") or []
        if isinstance(item, Mapping)
    }
    available_now = [
        {
            "service_binding": str(item.get("service_binding")),
            "capability": _capability_label(str(item.get("service_family") or item.get("service_binding"))),
            "tool_names": [str(name) for name in item.get("tool_names") or []],
            "provenance": "approved project state plus recorded target-client projection and ContextForge tool policy",
        }
        for item in tool_report.get("available_tools") or []
        if isinstance(item, Mapping)
    ]
    known_unavailable = [
        {
            "service_binding": str(item.get("service_binding")),
            "status": str(item.get("status")),
            "reason": str(item.get("reason")),
            "provenance": "project state unavailable/skipped service record",
        }
        for item in tool_report.get("skipped_or_unavailable_services") or []
        if isinstance(item, Mapping)
    ]
    onboarding_needed: list[dict[str, str]] = []
    catalog_services = common.discover_contextforge_hosted_services(project_root=root)
    for candidate in catalog_services:
        if not isinstance(candidate, Mapping):
            continue
        binding = str(candidate.get("service_binding") or "")
        if not binding or binding in approved or binding in unavailable_bindings:
            continue
        onboarding_needed.append(
            {
                "service_binding": binding,
                "capability": str(candidate.get("display_name") or candidate.get("canonical_service") or binding.split(":", 1)[0]),
                "scope": str(candidate.get("scope_label") or candidate.get("activation_class") or candidate.get("instantiation_class") or "known catalog service"),
                "provenance": "ContextForge activation catalog; not approved in this project state",
            }
        )
    revision = project_state.state_revision(state)
    available_text = (
        "; ".join(
            f"{item['capability']} via {item['service_binding']}"
            for item in available_now
        )
        or "none reported"
    )
    project_service_text = (
        ", ".join(str(item.get("service_binding") or "") for item in project_services if item.get("service_binding"))
        or "none recorded"
    )
    missing_projection_text = (
        "; ".join(
            f"{item.get('service_binding')}: align/import existing project service instance for {client_type}; no new project service instance without explicit approval"
            for item in missing_projection
        )
        or "none recorded"
    )
    unavailable_text = (
        "; ".join(
            f"{item['service_binding']} ({item['status']}: {item['reason']})"
            for item in known_unavailable
        )
        or "none reported"
    )
    onboarding_text = (
        ", ".join(
            item["capability"]
            for item in onboarding_needed
        )
        or "none reported"
    )
    session_boundary = _client_session_boundary(state, client_type)
    refresh_boundary = session_boundary["instruction"]
    return {
        "ok": True,
        "status": "project_capability_summary",
        "client_type": client_type,
        "project_root": str(root),
        "state_status": state.get("status"),
        "state_revision": revision,
        "project_services": project_services,
        "available_now": available_now,
        "known_unavailable": known_unavailable,
        "onboarding_needed": onboarding_needed,
        "missing_target_client_projection": missing_projection,
        "current_session_boundary": session_boundary,
        "assistant_visible_response_policy": {
            "internal_status_terms_suppressed": True,
            "diagnostic_state_retained_in_structured_fields": True,
        },
        "assistant_visible_response": (
            "Source: project state plus ContextForge catalog; no changes were made. "
            f"In this project, ContextForge is initialized for {str(root)} at state revision {revision}. "
            f"Important client/session boundary for {client_type}: {refresh_boundary} "
            f"Project services present: {project_service_text}. "
            f"Configured in current project state for {client_type}: {available_text}. "
            f"Missing target-client projections: {missing_projection_text}. "
            f"Known but unavailable: {unavailable_text}. "
            f"Could be onboarded with approval: {onboarding_text}."
        ),
        "non_actions": [
            "read-only project capability summary",
            "no service selection",
            "no project-init proposal, approval, or apply",
            "no tool probe or backend mutation",
            "no service onboarding",
        ],
    }


def _layer_status(service: Mapping[str, Any], *names: str) -> str:
    layers = service.get("verification_layers")
    if not isinstance(layers, Mapping):
        return "not_claimed"
    for name in names:
        value = layers.get(name)
        if isinstance(value, Mapping):
            status = value.get("status") or value.get("state")
            if status:
                return str(status)
    return "not_claimed"


def _client_state_for_service(service: Mapping[str, Any], client_type: str) -> dict[str, Any]:
    clients = service.get("target_clients")
    if not isinstance(clients, Mapping):
        return {"status": "not_recorded"}
    state = clients.get(client_type)
    if not isinstance(state, Mapping):
        return {"status": "not_recorded"}
    keep = [
        "status",
        "validation_status",
        "reload_status",
        "surface",
        "shim",
        "virtual_server",
        "service_identity_id",
        "contextforge_server_id",
        "alias",
        "tool_prefix",
        "pi_tool_prefix",
        "global_trigger_surface",
        "target_client_visible",
        "proof_ref",
        "safe_probe_id",
        "x_proof_kind",
        "x_safe_probe_result",
    ]
    return {key: state[key] for key in keep if key in state}


def project_state_readback(project_root: str, client_type: str = DEFAULT_CLIENT_TYPE) -> dict[str, Any]:
    """Read current project state and return an honest target-client readback."""

    root = project_state.validate_project_root(project_root, require_workspace=True)
    state = project_state.load_state(root)
    tool_report = project_tool_availability(project_root=str(root), client_type=client_type)
    services = state.get("services") if isinstance(state.get("services"), Mapping) else {}
    session_boundary = _client_session_boundary(state, client_type)
    service_readbacks: list[dict[str, Any]] = []
    for binding_id, service_value in services.items():
        if not isinstance(service_value, Mapping):
            continue
        service = dict(service_value)
        service_binding = str(service.get("service_binding") or binding_id)
        service_family = _service_family_from_state(service_binding, service)
        tool_names = _tool_names_for_service(service_family)
        target_client_state = _client_state_for_service(service, client_type)
        projection_status = _target_client_projection_status(target_client_state)
        tool_policy_status = _tool_policy_status_for_service(service, tool_names)
        target_client_user_state = _target_client_user_state(target_client_state, session_boundary)
        readback_item = {
            "service_binding": service_binding,
            "service_family": service_family,
            "project_service_state": "present",
            "provision_status": str(service.get("provision_status") or "unknown"),
            "backend_instance": service.get("backend_instance"),
            "virtual_server": service.get("virtual_server"),
            "target_client_state": target_client_state,
            "target_client_projection_status": projection_status,
            "target_client_user_state": target_client_user_state,
            "tool_policy_status": tool_policy_status,
            "tool_policy_names": tool_names,
            "target_client_visibility_status": _target_client_visibility_status(target_client_state),
            "target_client_proof_status": _target_client_proof_status(target_client_state),
            "available_to_target_client": bool(projection_status == "recorded" and tool_names),
            "readiness_layers": {
                "source_ready": "present_in_project_state",
                "backend_ready": _layer_status(service, "backend", "upstream_backend", "service_backend"),
                "contextforge_ready": _layer_status(service, "contextforge", "contextforge_route", "registry", "gateway"),
                "client_visible": _layer_status(service, "target_client"),
                "interactive_proof": "not_claimed_by_readback",
            },
        }
        if projection_status == "missing":
            readback_item["recommended_action"] = _missing_projection_action(service_binding, client_type)
        service_readbacks.append(
            readback_item
        )
    revision = project_state.state_revision(state)
    selected = [item["service_binding"] for item in service_readbacks]
    project_tool_policies = tool_report.get("project_tool_policies") if isinstance(tool_report.get("project_tool_policies"), list) else []
    missing_projection = tool_report.get("missing_target_client_projection") if isinstance(tool_report.get("missing_target_client_projection"), list) else []
    imported_tools = tool_report.get("available_tools") if isinstance(tool_report.get("available_tools"), list) else []
    skipped = tool_report.get("skipped_or_unavailable_services") if isinstance(tool_report.get("skipped_or_unavailable_services"), list) else []
    bounded_errors = [
        {
            "service_binding": str(item.get("service_binding") or ""),
            "status": str(item.get("status") or "unavailable"),
            "reason": str(item.get("reason") or "reported unavailable"),
        }
        for item in skipped
        if isinstance(item, Mapping)
    ]
    service_text = ", ".join(selected) or "none recorded"
    tools_text = (
        "; ".join(
            f"{item.get('service_binding')}: {', '.join(str(name) for name in item.get('tool_names') or [])}"
            for item in imported_tools
            if isinstance(item, Mapping)
        )
        or "none reported"
    )
    policy_text = (
        "; ".join(
            f"{item.get('service_binding')}: {', '.join(str(name) for name in item.get('tool_policy_names') or [])}"
            for item in project_tool_policies
            if isinstance(item, Mapping)
        )
        or "none recorded"
    )
    missing_projection_text = (
        "; ".join(
            f"{item.get('service_binding')}: align/import existing project service instance for {client_type}; no new project service instance without explicit approval"
            for item in missing_projection
            if isinstance(item, Mapping)
        )
        or "none recorded"
    )
    skipped_text = (
        "none reported"
        if not skipped
        else "; ".join(
            f"{item.get('service_binding')} ({item.get('status')}: {item.get('reason')})"
            for item in skipped
            if isinstance(item, Mapping)
        )
    )
    refresh_boundary = session_boundary["instruction"]
    target_summaries = (
        "; ".join(
            f"{item['service_binding']} projection {item['target_client_projection_status']}; {item['target_client_user_state']}"
            for item in service_readbacks
        )
        or "none recorded"
    )
    return {
        "ok": True,
        "status": "project_state_readback",
        "client_type": client_type,
        "project_root": str(root),
        "state_status": state.get("status"),
        "state_revision": revision,
        "selected_service_bindings": selected,
        "project_tool_policies": project_tool_policies,
        "imported_tools": imported_tools,
        "missing_target_client_projection": missing_projection,
        "skipped_or_unavailable_services": skipped,
        "bounded_errors": bounded_errors,
        "target_client_services": service_readbacks,
        "current_session_boundary": session_boundary,
        "assistant_visible_response_policy": {
            "internal_status_terms_suppressed": True,
            "diagnostic_state_retained_in_structured_fields": True,
        },
        "claim_layers": {
            "source_ready": "project-state file loaded and schema revision read",
            "backend_ready": "reported only from recorded service readiness fields when present",
            "contextforge_ready": "reported only from recorded ContextForge route/readiness fields when present",
            "client_visible": "reported only from recorded target-client projection state; project tool policy alone is not target-client availability",
            "interactive_proof": "not claimed by this readback; requires a separate ordinary tool-use transcript",
        },
        "assistant_visible_response": (
            f"ContextForge state for {str(root)} is {state.get('status')} at revision {revision}. "
            f"Target client: {client_type}. Selected services: {service_text}. "
            f"Project tool policy: {policy_text}. "
            f"Configured/imported-tool policy for this client: {tools_text}. "
            f"Missing target-client projections: {missing_projection_text}. "
            f"Skipped or unavailable services: {skipped_text}. "
            f"Target-client binding state: {target_summaries}. "
            "client-visible tool use is not proven by this readback; target-client-visible=false states remain unproven. "
            "This is a read-only project-state readback; interactive proof is not claimed by this readback. "
            f"Note: {refresh_boundary}"
        ),
        "non_actions": [
            "read-only project-state readback",
            "no service selection",
            "no project-init proposal, approval, or apply",
            "no validation, tool probe, backend mutation, or registry mutation",
            "no claim of interactive proof",
            "no claim of interactive proof from local state alone",
        ],
    }


def _capability_label(service_family: str) -> str:
    labels = {
        "context7": "Context7 documentation lookup",
        "exa-search": "Exa search",
        "github": "GitHub project integration",
        "mentality": "project governance readback",
        "openzeppelin-solidity-contracts": "OpenZeppelin Solidity contracts reference",
        "playwright": "browser automation",
        "ssh-tmux": "SSH/tmux operations",
        "web-search": "web search",
        "serena": "project-scoped code navigation",
    }
    return labels.get(service_family, service_family)


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


def _read_latest_user_message_cwd() -> str:
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
    return cwd if isinstance(cwd, str) else ""


def _continuation_project_root(project_root: str, client_type: str) -> str:
    if client_type != "opencode":
        return project_root
    supplied = str(project_root or "").strip()
    if supplied and _cache_key(supplied) != _cache_key("/"):
        return project_root
    cwd = _read_latest_user_message_cwd().strip()
    if cwd and _cache_key(cwd) != _cache_key("/"):
        return cwd
    return project_root


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


def _latest_text_is_approval(text: str) -> bool:
    lowered = text.strip().lower()
    return lowered in {"approve", "approved", "yes approve", "i approve"} or re.search(r"\bapprove\b", lowered) is not None


def _latest_text_is_decline(text: str) -> bool:
    lowered = text.strip().lower()
    return lowered in {"decline", "declined", "no", "no thanks", "do not install"} or re.search(r"\bdecline\b", lowered) is not None


def _latest_text_is_defer(text: str) -> bool:
    lowered = text.strip().lower()
    return lowered in {"defer", "deferred", "later", "not now"} or re.search(r"\bdefer\b", lowered) is not None


def _selected_service_ids_from_text(text: str, capabilities: Mapping[str, Any]) -> list[str]:
    stripped = text.strip()
    if not stripped:
        return []
    lowered = stripped.lower()
    next_turn_value = capabilities.get("next_turn") if isinstance(capabilities.get("next_turn"), Mapping) else {}
    choices = next_turn_value.get("choices") if isinstance(next_turn_value.get("choices"), list) else []
    numeric_selection_text = re.fullmatch(r"[\d,\s]+", stripped) is not None
    if "all" in lowered and re.search(r"\bservices?\b", lowered):
        return [
            str(choice.get("id") or "")
            for choice in choices
            if isinstance(choice, Mapping) and choice.get("id") and str(choice.get("id")) != "none"
        ]
    selected: list[str] = []
    for choice in choices:
        if not isinstance(choice, Mapping):
            continue
        choice_id = str(choice.get("id") or "")
        if not choice_id or choice_id == "none":
            continue
        label = str(choice.get("label") or "").lower()
        number = choice.get("number")
        if (
            (numeric_selection_text and isinstance(number, int) and _contains_selection_number(stripped, number))
            or choice_id.lower() in lowered
            or (label and re.search(rf"\b{re.escape(label)}\b", lowered))
        ):
            selected.append(choice_id)
    return selected


def _is_serena_service_ref(item: Any) -> bool:
    if isinstance(item, Mapping):
        binding = str(item.get("service_binding") or "")
        family = str(item.get("service_family") or item.get("canonical_service") or item.get("codex_alias") or "")
        return binding.startswith("serena:") or family == "serena" or family.startswith("serena:")
    ref = str(item)
    return ref == "serena" or ref.startswith("serena:")


def _pending_service_refs(pending_input: Mapping[str, Any] | None) -> list[Any]:
    return [
        item
        for item in (pending_input or {}).get("selected_services") or []
        if item
    ]


def _language_input_from_text(text: str, pending_input: Mapping[str, Any] | None = None) -> str | None:
    lowered = text.strip().lower()
    if (pending_input or {}).get("input_name") == "language":
        numeric_choices = {"1": "python", "2": "typescript", "3": "defer"}
        if lowered in numeric_choices:
            return numeric_choices[lowered]
    if lowered in {"python", "typescript", "defer"}:
        return lowered
    return None


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
            "latest user message does not contain explicit approval text; "
            "ask the user to approve or decline the listed project-local effects before calling approval tools"
        )


def _remember_plan(project_root: str, plan: dict[str, Any]) -> dict[str, Any]:
    _CACHED_PLANS[_cache_key(project_root)] = dict(plan)
    current = _read_durable_cache(project_root)
    current.pop("pending_input", None)
    _write_durable_cache(project_root, {**current, "plan": dict(plan)})
    return plan


def _remember_pending_project_init_input(project_root: str, selected_services: list[Any]) -> None:
    normalized: list[Any] = []
    for item in selected_services:
        if isinstance(item, Mapping):
            normalized.append(dict(item))
            continue
        else:
            ref = str(item)
        if ref:
            normalized.append(ref)
    current = _read_durable_cache(project_root)
    _write_durable_cache(
        project_root,
        {
            **current,
            "pending_input": {
                "selected_services": normalized,
                "input_name": "language",
            },
        },
    )


def _clear_pending_project_init_input(project_root: str) -> None:
    current = _read_durable_cache(project_root)
    if "pending_input" not in current:
        return
    current.pop("pending_input", None)
    _write_durable_cache(project_root, current)


def _pending_project_init_input(project_root: str) -> dict[str, Any] | None:
    pending = _read_durable_cache(project_root).get("pending_input")
    return dict(pending) if isinstance(pending, dict) else None


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


def _cached_project_init_plan_or_none(project_root: str) -> dict[str, Any] | None:
    try:
        return _matching_cached_plan(project_root, None, None)
    except Exception:
        return None


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
        result = {"ok": True, **helper.helper_readiness(project_root=project_root, client_type=client_type)}
        return client_visible_project_init_payload(result)
    except Exception as exc:
        return _error(exc)


@server.tool()
def cf_project_init_get_context(project_root: str, client_type: str = DEFAULT_CLIENT_TYPE) -> dict[str, Any]:
    """Alias for get_project_context with the project-init tool id."""
    return get_project_context(project_root=project_root, client_type=client_type)


@server.tool()
def get_project_tool_availability(project_root: str, client_type: str = DEFAULT_CLIENT_TYPE) -> dict[str, Any]:
    """Return a read-only initialized-project report; copy assistant_visible_response exactly."""
    try:
        return client_visible_project_tool_availability_payload(
            project_tool_availability(project_root=project_root, client_type=client_type)
        )
    except Exception as exc:
        return _error(exc)


@server.tool()
def cf_project_tool_availability(project_root: str, client_type: str = DEFAULT_CLIENT_TYPE) -> dict[str, Any]:
    """Normal-use availability report; copy assistant_visible_response exactly as the complete reply."""
    return get_project_tool_availability(project_root=project_root, client_type=client_type)


@server.tool()
def get_project_capability_summary(project_root: str, client_type: str = DEFAULT_CLIENT_TYPE) -> dict[str, Any]:
    """Return a read-only initialized-project capability summary; copy assistant_visible_response exactly."""
    try:
        return client_visible_project_capability_summary_payload(
            project_capability_summary(project_root=project_root, client_type=client_type)
        )
    except Exception as exc:
        return _error(exc)


@server.tool()
def cf_project_capability_summary(project_root: str, client_type: str = DEFAULT_CLIENT_TYPE) -> dict[str, Any]:
    """Normal-use capability summary; copy assistant_visible_response exactly as the complete reply."""
    return get_project_capability_summary(project_root=project_root, client_type=client_type)


@server.tool()
def get_project_state_readback(project_root: str, client_type: str = DEFAULT_CLIENT_TYPE) -> dict[str, Any]:
    """Return a read-only project-state readback; copy assistant_visible_response exactly."""
    try:
        return client_visible_project_state_readback_payload(
            project_state_readback(project_root=project_root, client_type=client_type)
        )
    except Exception as exc:
        return _error(exc)


@server.tool()
def cf_project_state_readback(project_root: str, client_type: str = DEFAULT_CLIENT_TYPE) -> dict[str, Any]:
    """Normal-use project-state readback; copy assistant_visible_response exactly as the complete reply."""
    return get_project_state_readback(project_root=project_root, client_type=client_type)


@server.tool()
def list_available_capabilities(
    project_root: str,
    client_type: str = DEFAULT_CLIENT_TYPE,
    contextforge_servers: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """List activation candidates and one service-selection next_turn."""
    try:
        result = {
            "ok": True,
            **helper.list_available_capabilities(
                project_root=project_root,
                client_type=client_type,
                contextforge_servers=contextforge_servers,
            ),
        }
        return client_visible_project_init_list_payload(result)
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
        if result.get("status") == "needs_input":
            _remember_pending_project_init_input(project_root, selected_services)
        _remember_project_init_result(project_root, result)
        return result
    except Exception as exc:
        return _error(exc)


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
def cf_project_init_record_service_decision(
    project_root: str,
    selected_services: list[dict[str, Any] | str] | None = None,
    decision_state: str = "declined",
    client_type: str = DEFAULT_CLIENT_TYPE,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Record a project-local decline/defer decision without active import."""
    try:
        project_root = _continuation_project_root(project_root, client_type)
        selected = selected_services
        source_plan_id = None
        if not selected:
            plan = _cached_project_init_plan_or_none(project_root)
            if isinstance(plan, dict):
                selected = [
                    dict(service)
                    for service in plan.get("selected_services") or []
                    if isinstance(service, dict)
                ]
                source_plan_id = str(plan.get("plan_id") or "") or None
        if not selected:
            pending = _pending_project_init_input(project_root)
            selected = [
                item
                for item in (pending or {}).get("selected_services") or []
                if item
            ]
        result = helper.record_project_init_service_decision(
            project_root=project_root,
            selected_services=selected or [],
            decision_state=decision_state,
            client_type=client_type,
            source_plan_id=source_plan_id,
            dry_run=dry_run,
        )
        if not dry_run:
            _clear_pending_project_init_input(project_root)
        return client_visible_project_init_decision_payload(result)
    except Exception as exc:
        return _error(exc)


@server.tool()
def cf_project_init_continue(
    project_root: str,
    client_type: str = DEFAULT_CLIENT_TYPE,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Continue project init from the latest plain user reply.

    This is the narrow client-facing OpenCode tool: selection text proposes a
    plan, explicit approval applies it, and any other text returns the service
    menu. Direct approve/apply tools remain helper internals.
    """
    try:
        project_root = _continuation_project_root(project_root, client_type)
        latest = _read_latest_user_message_text(project_root)
        pending_input = _pending_project_init_input(project_root)
        language = _language_input_from_text(latest, pending_input)
        if pending_input and language:
            pending_services = _pending_service_refs(pending_input)
            if language == "defer":
                non_serena_services = [
                    item
                    for item in pending_services
                    if not _is_serena_service_ref(item)
                ]
                if non_serena_services:
                    result = propose_project_init(
                        project_root=project_root,
                        selected_services=non_serena_services,
                        client_type=client_type,
                    )
                    if result.get("status") != "needs_input":
                        _clear_pending_project_init_input(project_root)
                    return client_visible_project_init_plan_payload(result, include_next_turn=client_type != "codex")
                serena_services = [
                    item
                    for item in pending_services
                    if _is_serena_service_ref(item)
                ]
                return cf_project_init_record_service_decision(
                    project_root=project_root,
                    selected_services=serena_services or None,
                    decision_state="deferred",
                    client_type=client_type,
                    dry_run=dry_run,
                )
            if pending_services:
                result = propose_project_init(
                    project_root=project_root,
                    selected_services=pending_services,
                    client_type=client_type,
                    inputs={"language": language},
                )
                if result.get("status") != "needs_input":
                    _clear_pending_project_init_input(project_root)
                return client_visible_project_init_plan_payload(result, include_next_turn=client_type != "codex")
        if _latest_text_is_decline(latest):
            return cf_project_init_record_service_decision(
                project_root=project_root,
                decision_state="declined",
                client_type=client_type,
                dry_run=dry_run,
            )
        if _latest_text_is_defer(latest):
            pending_services = _pending_service_refs(pending_input)
            serena_services = [
                item
                for item in pending_services
                if _is_serena_service_ref(item)
            ]
            return cf_project_init_record_service_decision(
                project_root=project_root,
                selected_services=serena_services or None,
                decision_state="deferred",
                client_type=client_type,
                dry_run=dry_run,
            )
        if _latest_text_is_approval(latest):
            approval = cf_project_init_approve(project_root=project_root)
            if approval.get("ok") is False:
                return approval
            result = cf_project_init_apply(
                project_root=project_root,
                dry_run=dry_run,
            )
            return client_visible_project_init_apply_payload(result)
        capabilities = helper.list_available_capabilities(
            project_root=project_root,
            client_type=client_type,
        )
        selected = _selected_service_ids_from_text(latest, capabilities)
        if selected:
            result = propose_project_init(
                project_root=project_root,
                selected_services=selected,
                client_type=client_type,
            )
            if result.get("status") == "needs_input":
                _remember_pending_project_init_input(project_root, selected)
            return client_visible_project_init_plan_payload(result, include_next_turn=client_type != "codex")
        return client_visible_project_init_list_payload({"ok": True, **capabilities})
    except Exception as exc:
        return _error(exc)


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


def approve_project_init_plan(
    project_root: str,
    plan: dict[str, Any],
    approval: dict[str, Any],
) -> dict[str, Any]:
    """Issue helper-owned consent receipts for approved project-local effects."""
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


def approve_project_init_recovery_plan(
    project_root: str,
    plan: dict[str, Any],
    approval: dict[str, Any],
) -> dict[str, Any]:
    """Issue helper-owned recovery consent receipts for approved recovery effects."""
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
        return client_visible_project_init_payload(result)
    except Exception as exc:
        return _error(exc)


def cf_project_init_recovery_approve(
    project_root: str,
    challenge_id: str = "",
    plan_digest: str = "",
) -> dict[str, Any]:
    """Approve the latest cached recovery plan after explicit user approval."""
    try:
        plan = _matching_cached_recovery_plan(project_root, challenge_id or None, plan_digest or None)
        challenge = plan.get("approval_challenge") if isinstance(plan.get("approval_challenge"), dict) else {}
        actual_challenge_id = str(challenge.get("challenge_id") or "")
        actual_plan_digest = str(plan.get("plan_digest") or "")
        _require_user_approval_text(project_root, actual_challenge_id, actual_plan_digest)
        helper.restore_process_local_approval_session(project_root=project_root, plan=plan)
        local_event = helper.record_local_approval_event(
            project_root=project_root,
            plan=plan,
            issuer_token=helper._LOCAL_APPROVAL_ISSUER_TOKEN,
            channel="interactive_user",
        )
        approval = {"decision": "approve", "challenge_id": actual_challenge_id, "plan_digest": actual_plan_digest}
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
        return client_visible_project_init_payload(result)
    except Exception as exc:
        return _error(exc)


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
        result = {
            "ok": True,
            **helper.apply_project_init_recovery(
                project_root=project_root,
                plan=clean_plan,
                receipts=receipts,
                contextforge_servers=contextforge_servers,
                dry_run=dry_run,
            ),
        }
        return result
    except Exception as exc:
        return _error(exc)


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


def cf_project_init_approve(
    project_root: str,
    challenge_id: str = "",
    plan_digest: str = "",
) -> dict[str, Any]:
    """Approve the latest cached project-init plan after explicit user approval."""
    try:
        plan = _matching_cached_plan(project_root, challenge_id or None, plan_digest or None)
        challenge = plan.get("approval_challenge") if isinstance(plan.get("approval_challenge"), dict) else {}
        actual_challenge_id = str(challenge.get("challenge_id") or "")
        actual_plan_digest = str(plan.get("plan_digest") or "")
        _require_user_approval_text(project_root, actual_challenge_id, actual_plan_digest)
        helper.restore_process_local_approval_session(project_root=project_root, plan=plan)
        local_event = helper.record_local_approval_event(
            project_root=project_root,
            plan=plan,
            issuer_token=helper._LOCAL_APPROVAL_ISSUER_TOKEN,
            channel="interactive_user",
        )
        approval = {"decision": "approve", "challenge_id": actual_challenge_id, "plan_digest": actual_plan_digest}
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


def apply_approved_project_init(
    project_root: str,
    plan: dict[str, Any],
    receipts: list[dict[str, Any]],
    contextforge_servers: list[dict[str, Any]] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Apply a helper-approved project-init plan and return installed/reload-required next_turn."""
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
            raise ValueError("no cached project-init receipts are available; approve the plan before calling cf_project_init_apply")
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


def repair_pending_project_init_config(
    project_root: str,
    client_type: str = DEFAULT_CLIENT_TYPE,
    contextforge_servers: list[dict[str, Any]] | None = None,
    server_instances_root: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Repair an approved project-init job whose project-local config is incomplete."""
    try:
        result = {
            "ok": True,
            **helper.repair_pending_project_init_config(
                project_root=project_root,
                client_type=client_type,
                contextforge_servers=contextforge_servers,
                server_instances_root=server_instances_root,
                dry_run=dry_run,
            ),
        }
        return client_visible_project_init_payload(result)
    except Exception as exc:
        return _error(exc)


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


if __name__ == "__main__":
    server.run()
