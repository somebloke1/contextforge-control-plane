#!/usr/bin/env python3
"""Pure helper workflow primitives for ContextForge project initialization."""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import secrets
import shutil
from argparse import Namespace
from collections.abc import Iterable, Mapping, Sequence
from contextlib import redirect_stdout
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import control_plane_authorization as authorization
import control_plane_contextforge_binding as binding
import control_plane_project_state as project_state
from project_init_common import (
    client_reload_requirement,
    discover_contextforge_hosted_services,
    normalize_codex_alias,
    safe_probe_contract,
    safe_validation_policy,
    stable_digest,
)


HELPER_PROTOCOL_VERSION = 1
HELPER_PLAN_SCHEMA_URI = "contextforge://control-plane/helper-project-init-plan/v1"
HELPER_RECOVERY_PLAN_SCHEMA_URI = "contextforge://control-plane/helper-project-init-recovery-plan/v1"
HELPER_READY_STATES = frozenset(
    {
        "available",
        "missing",
        "stale",
        "untrusted",
        "wrong_project_root",
        "unsupported_client",
        "read_only_plan_only",
    }
)
MUTATING_CONSENT_CLASSES = ("project_local_config_write", "project_state_write", "service_provision")
PROJECT_LOCAL_CONSENT_CLASSES = ("project_local_config_write", "project_state_write")
PROJECT_RESET_PROFILES = frozenset({"project_init_base"})


def _env_truthy(name: str) -> bool:
    return str(os.environ.get(name) or "").strip().lower() in {"1", "true", "yes", "on"}


def _serena_no_systemd_requested_or_required() -> bool:
    return _env_truthy("CONTEXTFORGE_SERENA_NO_SYSTEMD") or shutil.which("systemctl") is None


PI_PROJECT_LOCAL_CONSENT_CLASSES = ("project_state_write",)
SUPPORTED_CLIENTS = frozenset({"codex", "gemini", "opencode", "pi"})
_PENDING_CHALLENGES: dict[str, dict[str, Any]] = {}
_LOCAL_APPROVAL_EVENTS: dict[str, dict[str, Any]] = {}
_APPROVED_RECEIPT_IDS_BY_PLAN: dict[str, set[str]] = {}
_CONSUMED_RECEIPT_IDS: set[str] = set()
_LOCAL_APPROVAL_ISSUER_TOKEN = secrets.token_urlsafe(32)


class ProjectInitHelperError(ValueError):
    """Raised when the helper workflow would violate the project-init contract."""


def now_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _reset_id() -> str:
    return f"reset-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')}-{secrets.token_hex(4)}"


def next_turn(
    *,
    question_id: str,
    prompt: str,
    choices: Sequence[Mapping[str, Any]],
    allowed_response_shape: str,
    selection_mode: str = "single",
    accept_selection_numbers: bool = True,
) -> dict[str, Any]:
    numbered_choices = [
        {"number": index, **dict(choice)}
        for index, choice in enumerate(choices, start=1)
    ]
    rendered_choices = numbered_choices if accept_selection_numbers else [dict(choice) for choice in choices]
    respond_with = "selection number or option id" if accept_selection_numbers else "option id or explicit approval/decline text"
    allowed = (
        f"{allowed_response_shape}; selection number(s) are accepted"
        if accept_selection_numbers
        else f"{allowed_response_shape}; selection numbers are not accepted for approval"
    )
    return {
        "question_id": question_id,
        "prompt": prompt,
        "choices": rendered_choices,
        "response_form": {
            "type": "multi_select" if selection_mode == "multi" else "single_select",
            "options": rendered_choices,
            "respond_with": respond_with,
        },
        "allowed_response_shape": allowed,
        "must_stop": True,
    }


def validation_choice_turn() -> dict[str, Any]:
    return installation_complete_turn(client_type="codex", reload_requirement=None)


def installation_complete_turn(*, client_type: str, reload_requirement: Mapping[str, Any] | None) -> dict[str, Any]:
    command = str((reload_requirement or {}).get("command") or "start_new_session")
    if client_type in {"codex", "opencode"}:
        prompt = "ContextForge tools are installed for this project. Start a new session from this project root for the tools to register."
        label = "Start new session"
        effect = "Load the newly installed project-local ContextForge tools."
        allowed = "start a new session from this project root"
    elif client_type == "gemini":
        prompt = "ContextForge tools are installed for this project. Start a new Gemini CLI session from this project root for the tools to register."
        label = "Start new session"
        effect = "Load the newly installed project-local ContextForge tools."
        allowed = "start a new Gemini CLI session from this project root"
    elif client_type == "pi":
        prompt = "ContextForge tools are installed for this project. Run /reload in Pi for the tools to register."
        label = "Reload Pi"
        effect = "Load the newly installed ContextForge extension tools."
        allowed = "run /reload in Pi"
    else:
        prompt = f"ContextForge tools are installed for this project. Reload {client_type} for the tools to register."
        label = "Reload"
        effect = "Load the newly installed ContextForge tools."
        allowed = f"reload {client_type}"
    return next_turn(
        question_id=f"{client_type}-project-init-installed",
        prompt=prompt,
        choices=[
            {
                "id": command,
                "label": label,
                "effect": effect,
            }
        ],
        allowed_response_shape=allowed,
    )


def config_repair_turn(*, client_type: str = "codex") -> dict[str, Any]:
    if client_type == "pi":
        return next_turn(
            question_id="repair-pi-shim-activation-metadata",
            prompt="Project-init state and Pi shim activation metadata are out of sync. Repair the approved project-state records?",
            choices=[
                {
                    "id": "repair_pi_shim_activation_metadata",
                    "label": "Repair metadata",
                    "effect": "Write only approved project-state Pi shim activation metadata from the pending job.",
                },
                {"id": "restart_selection", "label": "Restart selection", "effect": "Start a new service-selection plan instead of repairing the pending job."},
            ],
            allowed_response_shape="choose repair_pi_shim_activation_metadata or restart_selection",
        )
    return next_turn(
        question_id="repair-project-local-config",
        prompt="Project-init state and project-local Codex config are out of sync. Repair the approved project-local MCP bindings?",
        choices=[
            {"id": "repair_project_local_config", "label": "Repair config", "effect": "Write only missing/owned project-local Codex MCP bindings from the approved job."},
            {"id": "restart_selection", "label": "Restart selection", "effect": "Start a new service-selection plan instead of repairing the pending job."},
        ],
        allowed_response_shape="choose repair_project_local_config or restart_selection",
    )


def config_recovery_approval_turn(*, client_type: str = "codex") -> dict[str, Any]:
    return next_turn(
        question_id="approve-project-init-config-recovery",
        prompt="Approve the listed project-local MCP config recovery effects?",
        choices=[
            {"id": "approve", "label": "Approve", "effect": "Issue scoped consent receipts for the exact recovery plan digest."},
            {"id": "decline", "label": "Decline", "effect": "No config, project state, services, trust, or catalog changes."},
        ],
        allowed_response_shape="approve or decline the exact recovery challenge id and plan digest",
        accept_selection_numbers=False,
    )


def reset_current_project(
    *,
    project_root: str | Path,
    client_type: str = "codex",
    profile: str = "project_init_base",
    preserve_evidence: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Reset helper-owned project-init state for one project root."""

    if profile not in PROJECT_RESET_PROFILES:
        raise ProjectInitHelperError(f"unsupported project reset profile: {profile}")
    if client_type not in SUPPORTED_CLIENTS:
        raise ProjectInitHelperError(f"unsupported client_type: {client_type}")
    root = project_state.validate_project_root(project_root, require_workspace=True)
    state_path = project_state.project_state_path(root)
    reset_id = _reset_id()
    evidence_dir = root / project_state.STATE_DIR_NAME / "contextforge-reset-evidence" / reset_id

    state = None
    state_error: str | None = None
    if state_path.exists():
        try:
            state = project_state.load_state(root)
        except Exception as exc:
            state_error = f"{exc.__class__.__name__}: {exc}"

    services = _project_init_services_from_state(state if isinstance(state, Mapping) else {})
    actions: list[dict[str, Any]] = []
    refusals: list[dict[str, Any]] = []
    preserved: list[dict[str, Any]] = []

    def preserve(path: Path, label: str) -> None:
        if not preserve_evidence or not path.exists():
            return
        target = evidence_dir / label
        if not dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(path.read_bytes())
        preserved.append({"path": str(path), "evidence_path": str(target), "dry_run": dry_run})

    preserve(state_path, "before/project_state/context_forge_state.json")
    if state_path.exists():
        actions.append({"surface": str(state_path), "operation": "remove_project_init_state", "dry_run": dry_run})
        if not dry_run:
            state_path.unlink()

    for result in (
        _reset_codex_project_config(root, services, preserve=preserve, dry_run=dry_run),
        _reset_json_mcp_project_config(
            services,
            config_path=root / "opencode.json",
            mcp_key="mcp",
            entry_builder=binding.build_project_init_opencode_binding_entry,
            entry_matches=binding._opencode_managed_entry_matches,
            preserve=preserve,
            dry_run=dry_run,
        ),
        _reset_json_mcp_project_config(
            services,
            config_path=root / ".gemini" / "settings.json",
            mcp_key="mcpServers",
            entry_builder=binding.build_project_init_gemini_binding_entry,
            entry_matches=binding._gemini_managed_entry_matches,
            preserve=preserve,
            dry_run=dry_run,
        ),
    ):
        actions.extend(result.get("actions", []))
        refusals.extend(result.get("refusals", []))

    manifest = {
        "reset_id": reset_id,
        "profile": profile,
        "project_root": str(root),
        "client_type": client_type,
        "dry_run": dry_run,
        "services_considered": [
            {
                key: service.get(key)
                for key in ("service_family", "service_binding", "codex_alias", "virtual_server")
                if service.get(key) is not None
            }
            for service in services
        ],
        "state_error": state_error,
        "actions": actions,
        "refusals": refusals,
        "preserved": preserved,
        "non_actions": [
            "does not remove Docker containers or volumes",
            "does not mutate user-global client config, trust, extensions, or authentication",
            "does not remove ContextForge token caches or secret material",
            "does not mutate ContextForge registry, service catalog, or backend services",
            "does not mutate git state",
            "does not remove unmanaged project-local MCP entries",
        ],
    }
    manifest["postcondition"] = _project_reset_postcondition(root)
    manifest["status"] = "reset" if manifest["postcondition"] else "needs_attention"
    action_count = len(actions)
    refusal_count = len(refusals)
    if dry_run:
        visible_status = "Project reset dry run complete"
    elif manifest["postcondition"]:
        visible_status = "Project reset complete"
    else:
        visible_status = "Project reset needs attention"
    evidence_note = f" Evidence preserved at {evidence_dir}." if preserve_evidence else ""
    manifest["assistant_visible_response"] = (
        f"{visible_status} for {root}. "
        f"Helper-owned project-init state and client bindings reset with {action_count} action(s) "
        f"and {refusal_count} refusal(s).{evidence_note} "
        "No Docker, user-global client config, authentication, token cache, ContextForge registry, backend service, or git state was reset."
    )
    manifest["evidence_dir"] = str(evidence_dir) if preserve_evidence else None
    if preserve_evidence and not dry_run:
        evidence_dir.mkdir(parents=True, exist_ok=True)
        (evidence_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def _project_init_services_from_state(state: Mapping[str, Any]) -> list[dict[str, Any]]:
    project_init = state.get("project_init") if isinstance(state.get("project_init"), Mapping) else {}
    services_by_binding: dict[str, dict[str, Any]] = {}
    activation_jobs = project_init.get("activation_jobs") if isinstance(project_init.get("activation_jobs"), Mapping) else {}
    for job in activation_jobs.values():
        if not isinstance(job, Mapping):
            continue
        for binding_name in [str(item) for item in job.get("selected_service_bindings") or [] if item]:
            alias = normalize_codex_alias(binding_name.split(":", 1)[0])
            services_by_binding.setdefault(
                binding_name,
                {
                    "service_family": alias,
                    "canonical_service": alias,
                    "service_binding": binding_name,
                    "codex_alias": alias,
                },
            )
    state_services = project_init.get("services") if isinstance(project_init.get("services"), Mapping) else {}
    for service in state_services.values():
        if not isinstance(service, Mapping):
            continue
        binding_name = str(service.get("service_binding") or service.get("service_family") or "")
        if not binding_name:
            continue
        record = services_by_binding.setdefault(binding_name, dict(service))
        record.update({key: value for key, value in service.items() if value is not None})
    client_states = project_init.get("client_states") if isinstance(project_init.get("client_states"), Mapping) else {}
    for client_state in client_states.values():
        if not isinstance(client_state, Mapping):
            continue
        projections = client_state.get("services") if isinstance(client_state.get("services"), Mapping) else {}
        for service_binding, projection in projections.items():
            if not isinstance(projection, Mapping):
                continue
            binding_name = str(service_binding)
            alias = normalize_codex_alias(binding_name.split(":", 1)[0])
            record = services_by_binding.setdefault(
                binding_name,
                {
                    "service_family": alias,
                    "canonical_service": alias,
                    "service_binding": binding_name,
                    "codex_alias": alias,
                },
            )
            if projection.get("alias"):
                record["codex_alias"] = str(projection["alias"])
            if projection.get("virtual_server"):
                record["virtual_server"] = str(projection["virtual_server"])
    return [
        service
        for service in services_by_binding.values()
        if service.get("service_binding") and service.get("codex_alias")
    ]


def _reset_codex_project_config(
    root: Path,
    services: Sequence[Mapping[str, Any]],
    *,
    preserve,
    dry_run: bool,
) -> dict[str, list[dict[str, Any]]]:
    config_path = root / ".codex" / "config.toml"
    if not config_path.exists():
        return {"actions": [], "refusals": []}
    text = config_path.read_text(encoding="utf-8")
    output = text
    actions: list[dict[str, Any]] = []
    refusals: list[dict[str, Any]] = []
    aliases = sorted({normalize_codex_alias(str(service.get("codex_alias") or service.get("service_family") or "")) for service in services if service.get("codex_alias") or service.get("service_family")})
    removed_aliases: set[str] = set()
    for alias in aliases:
        section_re = binding._codex_section_re(alias)
        match = section_re.search(output)
        if not match:
            continue
        block = match.group(0)
        if binding.PROJECT_INIT_OWNER_MARKER not in block:
            refusals.append({"surface": str(config_path), "alias": alias, "reason": "unmanaged_codex_mcp_block_preserved"})
            continue
        output = output[: match.start()] + output[match.end() :]
        removed_aliases.add(alias)
        actions.append({"surface": str(config_path), "alias": alias, "operation": "remove_owned_codex_mcp_block", "dry_run": dry_run})
    section_re = re.compile(r"(?ms)^(?:# contextforge-project-init-[^\n]*\n)*\[mcp_servers\.([^\]]+)\]\n.*?(?=^(?:# contextforge-project-init-[^\n]*\n)*\[|\Z)")
    while True:
        orphan = None
        for match in section_re.finditer(output):
            block = match.group(0)
            alias = normalize_codex_alias(match.group(1))
            if alias in removed_aliases:
                continue
            if binding.PROJECT_INIT_OWNER_MARKER in block:
                orphan = match
                break
        if orphan is None:
            break
        alias = normalize_codex_alias(orphan.group(1))
        output = output[: orphan.start()] + output[orphan.end() :]
        removed_aliases.add(alias)
        actions.append({"surface": str(config_path), "alias": alias, "operation": "remove_orphaned_owned_codex_mcp_block", "dry_run": dry_run})
    if output != text:
        preserve(config_path, "before/codex/config.toml")
        if not dry_run:
            if output.strip():
                config_path.write_text(output.strip() + "\n", encoding="utf-8")
            else:
                config_path.unlink()
    return {"actions": actions, "refusals": refusals}


def _reset_json_mcp_project_config(
    services: Sequence[Mapping[str, Any]],
    *,
    config_path: Path,
    mcp_key: str,
    entry_builder,
    entry_matches,
    preserve,
    dry_run: bool,
) -> dict[str, list[dict[str, Any]]]:
    if not config_path.exists():
        return {"actions": [], "refusals": []}
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"actions": [], "refusals": [{"surface": str(config_path), "reason": "invalid_json_preserved", "message": str(exc)}]}
    if not isinstance(config, dict):
        return {"actions": [], "refusals": [{"surface": str(config_path), "reason": "non_object_json_preserved"}]}
    mcp_servers = config.get(mcp_key)
    if mcp_servers is None:
        return {"actions": [], "refusals": []}
    if not isinstance(mcp_servers, dict):
        return {"actions": [], "refusals": [{"surface": str(config_path), "reason": f"invalid_{mcp_key}_object_preserved"}]}
    output = json.loads(json.dumps(config))
    output_servers = output.get(mcp_key)
    assert isinstance(output_servers, dict)
    actions: list[dict[str, Any]] = []
    refusals: list[dict[str, Any]] = []
    removed_aliases: set[str] = set()
    for service in services:
        alias = normalize_codex_alias(str(service.get("codex_alias") or service.get("service_family") or ""))
        if not alias or alias not in output_servers:
            continue
        existing = output_servers.get(alias)
        expected = entry_builder(service) if service.get("virtual_server") else None
        if (expected is not None and entry_matches(existing, expected)) or _json_mcp_entry_is_contextforge_owned(existing):
            del output_servers[alias]
            removed_aliases.add(alias)
            actions.append({"surface": str(config_path), "alias": alias, "operation": "remove_owned_json_mcp_entry", "dry_run": dry_run})
        else:
            refusals.append({"surface": str(config_path), "alias": alias, "reason": "unmanaged_or_drifted_json_mcp_entry_preserved"})
    for alias, existing in list(output_servers.items()):
        normalized_alias = normalize_codex_alias(str(alias))
        if normalized_alias in removed_aliases:
            continue
        if _json_mcp_entry_is_contextforge_owned(existing):
            del output_servers[alias]
            actions.append(
                {
                    "surface": str(config_path),
                    "alias": str(alias),
                    "operation": "remove_orphaned_contextforge_json_mcp_entry",
                    "dry_run": dry_run,
                }
            )
        elif _json_mcp_entry_uses_contextforge_wrapper(existing):
            refusals.append(
                {
                    "surface": str(config_path),
                    "alias": str(alias),
                    "reason": "unmanaged_wrapper_json_mcp_entry_preserved",
                }
            )
    if actions:
        preserve(config_path, f"before/{config_path.name}")
        if not output_servers:
            output.pop(mcp_key, None)
        if not dry_run:
            config_path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"actions": actions, "refusals": refusals}


def _json_mcp_entry_is_contextforge_owned(existing: Any) -> bool:
    if not isinstance(existing, Mapping):
        return False
    if not _json_mcp_entry_has_project_init_owner_marker(existing):
        return False
    return _json_mcp_entry_uses_contextforge_wrapper(existing)


def _json_mcp_entry_uses_contextforge_wrapper(existing: Any) -> bool:
    if not isinstance(existing, Mapping):
        return False
    command = existing.get("command")
    args = existing.get("args")
    if isinstance(command, list):
        command_parts = [str(item) for item in command]
        return any(part.endswith("contextforge_mcp_wrapper.py") for part in command_parts)
    if isinstance(args, list):
        arg_parts = [str(item) for item in args]
        return any(part.endswith("contextforge_mcp_wrapper.py") for part in arg_parts)
    return False


def _json_mcp_entry_has_project_init_owner_marker(existing: Mapping[str, Any]) -> bool:
    env = existing.get("environment")
    if not isinstance(env, Mapping):
        env = existing.get("env")
    return isinstance(env, Mapping) and str(env.get(binding.PROJECT_INIT_OWNER_ENV) or "") == binding.PROJECT_INIT_OWNER_VALUE


def _project_reset_postcondition(root: Path) -> bool:
    if project_state.project_state_path(root).exists():
        return False
    codex_path = root / ".codex" / "config.toml"
    if codex_path.exists() and binding.PROJECT_INIT_OWNER_MARKER in codex_path.read_text(encoding="utf-8"):
        return False
    for config_path, mcp_key in (
        (root / "opencode.json", "mcp"),
        (root / ".gemini" / "settings.json", "mcpServers"),
    ):
        if not config_path.exists():
            continue
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        servers = config.get(mcp_key) if isinstance(config, Mapping) else None
        if not isinstance(servers, Mapping):
            continue
        for entry in servers.values():
            if _json_mcp_entry_is_contextforge_owned(entry):
                return False
    return True


def state_repair_turn(*, client_type: str = "codex") -> dict[str, Any]:
    return next_turn(
        question_id="repair-project-init-state",
        prompt="Project-init state is missing durable install metadata, but existing ContextForge service records match this project. Repair the state?",
        choices=[
            {
                "id": "repair_project_init_state",
                "label": "Repair state",
                "effect": "Add only missing project-init install metadata and preserve existing service and config evidence.",
            },
            {"id": "restart_selection", "label": "Restart selection", "effect": "Start a new service-selection plan instead of repairing existing records."},
        ],
        allowed_response_shape="choose repair_project_init_state or restart_selection",
    )


def helper_readiness(
    *,
    project_root: str | Path,
    client_type: str = "codex",
    helper_state: str = "available",
    helper_version: int = HELPER_PROTOCOL_VERSION,
) -> dict[str, Any]:
    if helper_state not in HELPER_READY_STATES:
        raise ProjectInitHelperError(f"unknown helper readiness state: {helper_state}")
    root = project_state.validate_project_root(project_root, require_workspace=True)
    blockers: list[str] = []
    if helper_state != "available":
        blockers.append(helper_state)
    if helper_version < HELPER_PROTOCOL_VERSION:
        blockers.append("stale")
    if client_type not in SUPPORTED_CLIENTS:
        blockers.append("unsupported_client")
    status = "available" if not blockers else blockers[0]
    result = {
        "helper": {
            "name": "contextforge-helper",
            "protocol_version": HELPER_PROTOCOL_VERSION,
            "observed_version": helper_version,
            "status": status,
        },
        "client_type": client_type,
        "root_attestation": _root_attestation(root, client_type=client_type),
        "can_mutate": status == "available",
        "non_actions": [
            "remote agents do not write local files directly",
            "helper unavailable states do not fall back to direct config writes",
        ],
    }
    reload_requirement = client_reload_requirement(client_type, event="project_activation_apply")
    if reload_requirement:
        result["client_reload_requirement"] = reload_requirement
    if status != "available":
        result["next_turn"] = next_turn(
            question_id="helper-unavailable",
            prompt=f"ContextForge project init cannot continue because contextforge-helper is {status}.",
            choices=[
                {"id": "stop", "label": "Stop here", "effect": "No project files, config, services, or git state are changed."}
            ],
            allowed_response_shape="choose one remediation or stop",
        )
    return result


def _project_state_snapshot_for_init(root: Path) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    path = project_state.project_state_path(root)
    if not path.exists():
        return None, {"artifact_status": "absent", "exists": False, "digest": None}
    try:
        state = project_state.load_state(root)
    except project_state.StateValidationError as exc:
        return None, {
            "artifact_status": "invalid",
            "exists": True,
            "digest": project_state.state_file_artifact_digest(root),
            "error_type": exc.__class__.__name__,
            "message": str(exc),
            "recovery": "replace_after_scoped_project_init_approval",
        }
    assert state is not None
    return state, {
        "artifact_status": "valid",
        "exists": True,
        "revision": project_state.state_revision(state),
        "status": state.get("status"),
        "digest": authorization.stable_digest(state),
    }


def _planned_invalid_state_replacement(plan: Mapping[str, Any]) -> bool:
    stale_inputs = plan.get("stale_plan_inputs") if isinstance(plan.get("stale_plan_inputs"), Mapping) else {}
    base_state = stale_inputs.get("base_project_state") if isinstance(stale_inputs.get("base_project_state"), Mapping) else {}
    return base_state.get("artifact_status") == "invalid" and base_state.get("recovery") == "replace_after_scoped_project_init_approval"


def list_available_capabilities(
    *,
    project_root: str | Path,
    client_type: str = "codex",
    contextforge_servers: Iterable[dict[str, Any]] | None = None,
    contextforge_service_offerings: Iterable[dict[str, Any]] | None = None,
    server_instances_root: str | Path | None = None,
) -> dict[str, Any]:
    root = project_state.validate_project_root(project_root, require_workspace=True)
    readiness = helper_readiness(project_root=project_root, client_type=client_type)
    inspection = project_state.inspect_project_init_state(project_root, require_workspace=True)
    if inspection.get("lifecycle_status") == "invalid_repairable":
        return {
            "client_type": client_type,
            "root_attestation": readiness["root_attestation"],
            "status": "state_repair_required",
            "resume_reason": "project state has existing ContextForge service records but is missing project-init install metadata",
            "project_state_inspection": inspection,
            "next_turn": state_repair_turn(client_type=client_type),
            "non_actions": [
                "do not restart service selection before offering repair",
                "do not overwrite unmanaged target-client config during state repair",
                _no_user_global_mutation_label(client_type),
            ],
        }
    resume = pending_validation_resume(project_root=project_root, client_type=client_type)
    if resume is not None:
        return {
            "client_type": client_type,
            "root_attestation": readiness["root_attestation"],
            **resume,
        }
    existing_state: dict[str, Any] | None = None
    try:
        existing_state = project_state.load_state(root)
    except Exception:
        existing_state = None
    if isinstance(existing_state, Mapping):
        alignment_offer = _alignment_import_offer(root, existing_state, client_type=client_type)
        if alignment_offer is not None:
            return {
                "client_type": client_type,
                "root_attestation": readiness["root_attestation"],
                **alignment_offer,
            }
    live_contextforge_readback_supplied = contextforge_servers is not None or contextforge_service_offerings is not None
    if contextforge_service_offerings is not None:
        services = [service for service in contextforge_service_offerings if isinstance(service, Mapping)]
    else:
        services = discover_contextforge_hosted_services(
            project_root=project_root,
            contextforge_servers=contextforge_servers,
            **({"server_instances_root": server_instances_root} if server_instances_root is not None else {}),
        )
    candidates = [
        _candidate(service, client_type=client_type)
        for service in services
        if _service_visible_in_activation_menu(service, live_contextforge_readback_supplied=live_contextforge_readback_supplied)
    ]
    return {
        "client_type": client_type,
        "root_attestation": readiness["root_attestation"],
        "available_services": candidates,
        "next_turn": next_turn(
            question_id="select-services",
            prompt="Which ContextForge services should I enable for this project?",
            choices=[
                {
                    "id": candidate["service_binding"],
                    "label": candidate["display_name"],
                    "activation_class": candidate["activation_class"],
                    "effect": candidate["user_visible_effect"],
                }
                for candidate in candidates
            ]
            + [{"id": "none", "label": "None", "effect": "Do not enable a service now."}],
            allowed_response_shape="list service ids, selection numbers, or choose none",
            selection_mode="multi",
        ),
        "non_actions": [
            "discovery is read-only",
            "client configs are not service identity",
            "no backend installation, registry mutation, or global trust change",
        ],
    }


def _alignment_import_offer(
    root: Path,
    state: Mapping[str, Any],
    *,
    client_type: str,
) -> dict[str, Any] | None:
    services = state.get("services") if isinstance(state.get("services"), Mapping) else {}
    alignment_services: list[dict[str, Any]] = []
    missing_actions: list[dict[str, Any]] = []
    non_current_actions: list[dict[str, Any]] = []
    unavailable_project_services: list[dict[str, Any]] = []
    for binding_id, service_value in services.items():
        if not isinstance(service_value, Mapping):
            continue
        service = dict(service_value)
        service.setdefault("service_binding", str(binding_id))
        service_binding = str(service.get("service_binding") or binding_id)
        unavailable_summary = _service_skipped_or_unavailable_summary(service)
        if unavailable_summary:
            unavailable_project_services.append(unavailable_summary)
            continue
        target_clients = service.get("target_clients") if isinstance(service.get("target_clients"), Mapping) else {}
        target_client_state = target_clients.get(client_type) if isinstance(target_clients, Mapping) else None
        if isinstance(target_client_state, Mapping):
            projection_status = _alignment_projection_status(target_client_state)
            if projection_status in {"imported", "verified", "recorded"}:
                continue
        else:
            projection_status = "missing"
        candidate = _candidate(service, client_type=client_type)
        candidate["project_service_state"] = "present"
        candidate["target_client_projection_status"] = projection_status
        candidate["target_client_state"] = dict(target_client_state) if isinstance(target_client_state, Mapping) else {"status": "not_recorded"}
        candidate["available_to_target_client"] = False
        if projection_status == "missing":
            candidate["user_visible_effect"] = (
                f"Import this project's existing {candidate['display_name']} binding for {client_type} "
                "without provisioning a new project service instance."
            )
            candidate["recommended_action"] = _projection_alignment_action(service_binding, client_type, projection_status)
            missing_actions.append(candidate["recommended_action"])
        else:
            candidate["user_visible_effect"] = (
                f"Repair this project's existing {candidate['display_name']} projection for {client_type} "
                "without provisioning a new project service instance."
            )
            candidate["recommended_action"] = _projection_alignment_action(service_binding, client_type, projection_status)
            non_current_actions.append(candidate["recommended_action"])
        alignment_services.append(candidate)

    if not alignment_services and not unavailable_project_services:
        return None
    project_service_bindings = [str(service["service_binding"]) for service in alignment_services]
    unavailable_bindings = [str(item["service_binding"]) for item in unavailable_project_services if str(item.get("service_binding") or "")]
    project_service_text = ", ".join(project_service_bindings + unavailable_bindings)
    importable_text = ", ".join(project_service_bindings) if project_service_bindings else "none currently importable"
    missing_text = ", ".join(str(item["service_binding"]) for item in missing_actions) if missing_actions else "none"
    non_current_text = ", ".join(str(item["service_binding"]) for item in non_current_actions) if non_current_actions else "none"
    prompt_client = {
        "codex": "Codex",
        "gemini": "Gemini",
        "opencode": "OpenCode",
        "pi": "Pi",
    }.get(client_type, client_type)
    return {
        "status": "alignment_import_offer",
        "alignment_import_offer": {
            "mode": "alignment_import",
            "source": "project_state",
            "target_client": client_type,
            "project_root": str(root),
            "project_service_bindings": project_service_bindings,
            "missing_target_client_projection": missing_actions,
            "non_current_target_client_projection": non_current_actions,
            "unavailable_project_services": unavailable_project_services,
            "service_count": len(alignment_services),
            "unavailable_service_count": len(unavailable_project_services),
        },
        "available_services": alignment_services,
        "assistant_visible_response": (
            f"ContextForge state for {str(root)} already contains project services: {project_service_text}. "
            f"Missing target-client projections for {prompt_client}: {missing_text}. "
            f"Non-current target-client projections for {prompt_client}: {non_current_text}. "
            f"Importable or repairable target-client projections for {prompt_client}: {importable_text}. "
            f"{_alignment_unavailable_visible_text(unavailable_project_services)}"
            "This is a read-only alignment/import offer; no project service instance is duplicated or provisioned here. "
            f"Import this project's existing ContextForge services for {prompt_client}?"
        ),
        "next_turn": next_turn(
            question_id="align-existing-project-services",
            prompt=(
                f"Project services are already present. Import this project's existing ContextForge services for {prompt_client}?"
            ),
            choices=[
                {
                    "id": service["service_binding"],
                    "label": service["display_name"],
                    "activation_class": service["activation_class"],
                    "effect": service["user_visible_effect"],
                }
                for service in alignment_services
            ]
            + [{"id": "none", "label": "None", "effect": "Record no service alignment."}],
            allowed_response_shape="list service ids, selection numbers, or choose none",
            selection_mode="multi",
        ),
        "non_actions": [
            "discovery is read-only",
            "project service identities are not duplicated for client aliases",
            "no backend installation, registry mutation, or global trust change",
        ],
    }


def _service_skipped_or_unavailable(service: Mapping[str, Any]) -> bool:
    return bool(_service_skipped_or_unavailable_summary(service))


def _service_skipped_or_unavailable_summary(service: Mapping[str, Any]) -> dict[str, str] | None:
    service_binding = str(service.get("service_binding") or service.get("id") or "unknown")
    status = str(service.get("status") or "")
    if status in {"declined", "deferred", "disabled", "blocked", "unavailable"}:
        return {
            "service_binding": service_binding,
            "status": status,
            "reason": str(service.get("skipped_reason") or service.get("reason") or service.get("x_reason") or f"service is {status}"),
            "alignment_status": "blocked",
        }
    provision_status = str(service.get("provision_status") or "")
    if provision_status in {"skipped", "unavailable", "missing", "blocked", "failed"}:
        return {
            "service_binding": service_binding,
            "status": provision_status,
            "reason": str(service.get("skipped_reason") or service.get("reason") or service.get("x_reason") or f"service provisioning is {provision_status}"),
            "alignment_status": "blocked",
        }
    lifecycle = service.get("lifecycle") if isinstance(service.get("lifecycle"), Mapping) else {}
    lifecycle_status = str(lifecycle.get("status") or "")
    if lifecycle_status in {"declined", "deferred", "disabled", "blocked", "unavailable"}:
        return {
            "service_binding": service_binding,
            "status": lifecycle_status,
            "reason": str(lifecycle.get("reason") or service.get("reason") or service.get("x_reason") or f"service lifecycle is {lifecycle_status}"),
            "alignment_status": "blocked",
        }
    return None


def _alignment_unavailable_visible_text(unavailable_project_services: Sequence[Mapping[str, Any]]) -> str:
    if not unavailable_project_services:
        return ""
    details = "; ".join(
        f"{item.get('service_binding')}: {item.get('status')} ({item.get('reason')})"
        for item in unavailable_project_services
    )
    return (
        "Some project services cannot be imported for this client in the current plan: "
        f"{details}. "
    )


def _alignment_projection_status(target_client_state: Mapping[str, Any]) -> str:
    status = str(target_client_state.get("status") or "")
    validation_status = str(target_client_state.get("validation_status") or "")
    reload_status = str(target_client_state.get("reload_status") or "")
    if status in {"blocked", "failed"} or validation_status == "blocked":
        return "blocked"
    if status == "stale":
        return "stale"
    if status == "partial" or validation_status == "mixed":
        return "partial"
    if reload_status in {"pending_reload", "reload_required"}:
        return "reload_required"
    if status == "validation_pending" or validation_status == "pending":
        return "validation_pending"
    if status == "verified" or validation_status == "passed":
        return "verified"
    if status in {"installed", "project_local_opencode_config_planned", "project_local_codex_config_planned", "project_local_gemini_config_planned"}:
        return "imported"
    return "recorded"


def _projection_alignment_action(service_binding: str, client_type: str, projection_status: str) -> dict[str, str]:
    return {
        "action": "align_target_client_to_existing_project_service",
        "target_client": client_type,
        "service_binding": service_binding,
        "target_client_projection_status": projection_status,
        "boundary": (
            f"Align/import {client_type} to the existing project service instance; "
            "do not create a new project service instance unless explicitly approved."
        ),
    }


def propose_project_init(
    *,
    project_root: str | Path,
    selected_services: Sequence[Mapping[str, Any] | str],
    client_type: str = "codex",
    inputs: Mapping[str, Any] | None = None,
    contextforge_servers: Iterable[dict[str, Any]] | None = None,
    contextforge_service_offerings: Iterable[dict[str, Any]] | None = None,
    server_instances_root: str | Path | None = None,
    catalog_revision_or_etag: str | None = "fixture-catalog",
) -> dict[str, Any]:
    if client_type not in SUPPORTED_CLIENTS:
        raise ProjectInitHelperError(f"unsupported client_type: {client_type}")
    root = project_state.validate_project_root(project_root, require_workspace=True)
    if not (inputs or {}).get("restart_project_init"):
        inspection = project_state.inspect_project_init_state(root, require_workspace=True)
        if inspection.get("lifecycle_status") == "invalid_repairable":
            if (inputs or {}).get("repair_project_init_state"):
                repaired = repair_missing_project_init_state(
                    project_root=root,
                    client_type=client_type,
                    dry_run=False,
                )
                resume = pending_validation_resume(project_root=root, client_type=client_type)
                return {
                    "root_attestation": _root_attestation(root, client_type=client_type),
                    **(resume or repaired),
                }
            return {
                "root_attestation": _root_attestation(root, client_type=client_type),
                "status": "state_repair_required",
                "resume_reason": "project state has existing ContextForge service records but is missing project-init install metadata",
                "project_state_inspection": inspection,
                "next_turn": state_repair_turn(client_type=client_type),
                "non_actions": [
                    "do not restart project-init service selection before offering repair",
                    "do not overwrite unmanaged target-client config during state repair",
                    _no_user_global_mutation_label(client_type),
                ],
            }
        resume = pending_validation_resume(project_root=root, client_type=client_type)
        if resume is not None:
            if resume.get("status") == "config_repair_required" and (inputs or {}).get("repair_project_local_config"):
                repair = repair_pending_project_init_config(
                    project_root=root,
                    client_type=client_type,
                    contextforge_servers=contextforge_servers,
                    server_instances_root=server_instances_root,
                    dry_run=False,
                )
                if repair.get("status") == "config_repaired":
                    resume = pending_validation_resume(project_root=root, client_type=client_type) or repair
            return {
                "root_attestation": _root_attestation(root, client_type=client_type),
                **resume,
            }
    services = _resolve_selected_services(
        root,
        selected_services,
        client_type=client_type,
        contextforge_servers=contextforge_servers,
        contextforge_service_offerings=contextforge_service_offerings,
        server_instances_root=server_instances_root,
    )
    if not services:
        raise ProjectInitHelperError("selected_services must not be empty")
    missing_input = _first_missing_input(services, inputs or {})
    if missing_input is not None:
        return {
            "status": "needs_input",
            "root_attestation": _root_attestation(root, client_type=client_type),
            "service_binding": missing_input["service_binding"],
            "required_input": missing_input["input"],
            "next_turn": next_turn(
                question_id=f"input-{missing_input['service_binding']}-{missing_input['input']}",
                prompt=missing_input["prompt"],
                choices=missing_input["choices"],
                allowed_response_shape=f"provide {missing_input['input']}",
            ),
        }

    existing_state, state_snapshot = _project_state_snapshot_for_init(root)
    base_state = existing_state or project_state.default_state(root)
    config_plan = _client_activation_plan(root, services, client_type=client_type, existing_state=base_state)
    if config_plan.get("decision") == "block":
        resolution = _config_conflict_resolution(inputs or {})
        if resolution == "skip_conflicting_service":
            services, skipped_services = _skip_conflicting_services(services, config_plan)
            if not services:
                return _config_conflict_response(
                    root=root,
                    client_type=client_type,
                    config_plan=config_plan,
                    services=services,
                    skipped_services=skipped_services,
                    status="all_selected_services_conflict",
                    inputs=inputs or {},
                )
            config_plan = _client_activation_plan(root, services, client_type=client_type, existing_state=base_state)
            if config_plan.get("decision") == "block":
                return _config_conflict_response(
                    root=root,
                    client_type=client_type,
                    config_plan=config_plan,
                    services=services,
                    skipped_services=skipped_services,
                    inputs=inputs or {},
                )
        elif resolution == "keep_existing_block":
            return {
                "status": "activation_blocked",
                "root_attestation": _root_attestation(root, client_type=client_type),
                "config_plan": {key: value for key, value in config_plan.items() if key != "next_text"},
                "blocked_services": _conflicting_services(services, config_plan),
                "non_actions": [
                    "project-local config left unchanged",
                    "no project state write",
                    "no user-global config or trust mutation",
                    "no ContextForge registry or catalog mutation",
                ],
            }
        else:
            return _config_conflict_response(root=root, client_type=client_type, config_plan=config_plan, services=services, inputs=inputs or {})
    else:
        skipped_services = []
    plan_summary = _plan_summary(
        root=root,
        services=services,
        config_plan=config_plan,
        skipped_services=skipped_services,
        client_type=client_type,
        state_snapshot=state_snapshot,
    )
    required_inputs = _normalized_required_inputs(inputs or {}, services)
    plan_seed = {
        "schema_uri": HELPER_PLAN_SCHEMA_URI,
        "workflow": "project_init",
        "client_type": client_type,
        "project_root": str(root),
        "project_root_hash": project_state.project_root_hash(root),
        "selected_services": services,
        "required_inputs": required_inputs,
        "required_consent_classes": _required_consent_classes(services, client_type=client_type),
        "skipped_services": skipped_services,
        "stale_plan_inputs": _stale_plan_inputs(
            root=root,
            base_state=base_state,
            state_exists=existing_state is not None,
            state_snapshot=state_snapshot,
            client_type=client_type,
            config_plan=config_plan,
            catalog_revision_or_etag=catalog_revision_or_etag,
            services=services,
        ),
        "config_plan": {key: value for key, value in config_plan.items() if key != "next_text"},
        "plan_summary": plan_summary,
        "installation_mode": "install_only",
        "non_actions": [
            "no user-global config or trust mutation",
            "no ContextForge registry or catalog mutation",
            "no backend install or restart for shared canonical services",
            "no secret or token material write",
        ],
    }
    plan_id = "project-init-" + stable_digest(plan_seed).removeprefix("sha256:")[:16]
    plan = {"plan_id": plan_id, **plan_seed}
    plan["plan_digest"] = _plan_digest(plan)
    plan["approval_challenge"] = _approval_challenge(plan)
    _PENDING_CHALLENGES[plan["approval_challenge"]["challenge_id"]] = {
        "plan_id": plan["plan_id"],
        "plan_digest": plan["plan_digest"],
        "project_root": str(root),
        "expires_at": plan["approval_challenge"]["expires_at"],
        "nonce": plan["approval_challenge"]["nonce"],
    }
    plan["next_turn"] = next_turn(
        question_id="approve-project-init-plan",
        prompt="Approve the listed project-local ContextForge activation effects?",
        choices=[
            {"id": "approve", "label": "Approve", "effect": "Issue scoped consent receipts for the listed project-local effects."},
            {"id": "decline", "label": "Decline", "effect": "No config, project state, services, trust, or catalog changes."},
        ],
        allowed_response_shape="reply approve or decline",
        accept_selection_numbers=False,
    )
    return plan


def propose_project_init_recovery(
    *,
    project_root: str | Path,
    client_type: str = "codex",
    contextforge_servers: Iterable[dict[str, Any]] | None = None,
    server_instances_root: str | Path | None = None,
    inputs: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if client_type not in SUPPORTED_CLIENTS:
        raise ProjectInitHelperError(f"unsupported client_type: {client_type}")
    root = project_state.validate_project_root(project_root, require_workspace=True)
    source_plan = _recovery_source_activation_plan(inputs or {})
    if source_plan is not None:
        if str(source_plan.get("project_root")) != str(root):
            raise ProjectInitHelperError("recovery source plan project root does not match requested project root")
        services = [dict(service) for service in source_plan.get("selected_services") or [] if isinstance(service, Mapping)]
        if not services:
            raise ProjectInitHelperError("recovery source plan has no selected services")
    else:
        try:
            state, job, selected = _pending_validation_state_job(root, client_type=client_type)
        except ProjectInitHelperError as exc:
            raise ProjectInitHelperError("project-init recovery requires a cached activation plan or pending project-init job") from exc
        services = _services_from_state_or_catalog(
            root,
            state,
            selected,
            selected_bindings=_job_selected_service_bindings(job),
            client_type=client_type,
        )

    config_plan = _client_activation_plan(
        root,
        services,
        client_type=client_type,
        existing_state=project_state.read_or_default(root),
    )
    return _build_project_init_recovery_plan(
        root=root,
        client_type=client_type,
        services=services,
        source_plan=source_plan,
        config_plan=config_plan,
        inputs=inputs or {},
    )


def approve_project_init_recovery_plan(
    *,
    project_root: str | Path,
    plan: Mapping[str, Any],
    approval: Mapping[str, Any],
    local_approval_event_ref: str | None = None,
    actor: str = "developer",
    source_client: str = "codex",
    source_client_auth_strength: str = "shared_token",
) -> dict[str, Any]:
    if plan.get("schema_uri") != HELPER_RECOVERY_PLAN_SCHEMA_URI or plan.get("workflow") != "project_init_recovery":
        return {"decision": "block", "receipts": [], "reasons": ["plan is not a project-init recovery plan"]}
    return approve_project_init_plan(
        project_root=project_root,
        plan=plan,
        approval=approval,
        local_approval_event_ref=local_approval_event_ref,
        actor=actor,
        source_client=source_client,
        source_client_auth_strength=source_client_auth_strength,
    )


def apply_project_init_recovery(
    *,
    project_root: str | Path,
    plan: Mapping[str, Any],
    receipts: Sequence[Mapping[str, Any]],
    contextforge_servers: Iterable[dict[str, Any]] | None = None,
    server_instances_root: str | Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    root = project_state.validate_project_root(project_root, require_workspace=True)
    if str(plan.get("project_root")) != str(root):
        raise ProjectInitHelperError("recovery plan project root does not match requested project root")
    if plan.get("schema_uri") != HELPER_RECOVERY_PLAN_SCHEMA_URI or plan.get("workflow") != "project_init_recovery":
        raise ProjectInitHelperError("plan is not a project-init recovery plan")
    digest_errors = _validate_plan_digest(plan)
    if digest_errors:
        raise ProjectInitHelperError("; ".join(digest_errors))
    _validate_receipts_for_plan(plan, receipts, project_root=root, consume=False)
    _validate_recovery_plan_not_stale(root, plan)

    client_type = str(plan.get("client_type") or "codex")
    config_recovery = plan.get("config_recovery_plan") if isinstance(plan.get("config_recovery_plan"), Mapping) else {}
    result = {
        "status": "project_init_recovery_dry_run" if dry_run else "project_init_recovery_applied",
        "project_root": str(root),
        "client_type": client_type,
        "recovery_plan_id": plan.get("plan_id"),
        "recovery_plan_digest": plan.get("plan_digest"),
        "config_recovery_plan": {key: value for key, value in config_recovery.items() if key != "next_text"},
        "service_recovery_plan": plan.get("service_recovery_plan") or [],
        "non_actions": [
            _no_user_global_mutation_label(client_type),
            "no ContextForge catalog promotion",
            "no secrets or token material written",
        ],
    }
    if dry_run:
        result["next_turn"] = _post_recovery_next_turn(plan)
        return result
    service_recovery_results = _apply_service_recovery(root, plan)
    if config_recovery.get("write_allowed") and config_recovery.get("before_digest") != config_recovery.get("after_digest"):
        _write_client_activation(root, config_recovery, client_type=client_type)
    _validate_receipts_for_plan(plan, receipts, project_root=root, consume=True)
    result["service_recovery_results"] = service_recovery_results
    result["post_recovery"] = _post_recovery_summary(root, plan)
    result["next_turn"] = _post_recovery_next_turn(plan)
    return result


def pending_validation_resume(*, project_root: str | Path, client_type: str = "codex") -> dict[str, Any] | None:
    root = project_state.validate_project_root(project_root, require_workspace=True)
    try:
        state = project_state.load_state(root)
    except Exception:
        return None
    if not isinstance(state, Mapping) or state.get("status") not in {"in_progress", "initialized"}:
        return None
    project_init = state.get("project_init") if isinstance(state.get("project_init"), Mapping) else {}
    jobs = project_init.get("activation_jobs") if isinstance(project_init.get("activation_jobs"), Mapping) else {}
    current_job_id = str(project_state.project_init_current_job_id_for_client(dict(state), client_type) or "")
    job = jobs.get(current_job_id) if current_job_id else None
    if not isinstance(job, Mapping):
        return None
    resumable_statuses = {"applied_validation_choice_pending", "validation_choice_pending", "installed"}
    has_pending_records = any(
        isinstance(record, Mapping) and record.get("status") == "pending_user_choice"
        for record in (job.get("validation_records") or {}).values()
    )
    has_incomplete_validation_records = any(
        isinstance(record, Mapping) and record.get("status") in {"pending", "skipped", "pending_user_choice"}
        for record in (job.get("validation_records") or {}).values()
    )
    if (
        job.get("status") not in resumable_statuses
        and job.get("recovery_state") != "local_written_validation_pending"
        and not has_pending_records
        and not (job.get("status") == "validation_pending" and has_incomplete_validation_records)
    ):
        return None
    if str(job.get("client_type") or client_type) != client_type:
        return None
    selected_ids = _job_selected_service_ids(job)
    selected_bindings = _job_selected_service_bindings(job)
    repair_status = _pending_job_config_repair_status(root, state, job, selected_ids, selected_bindings=selected_bindings, client_type=client_type)
    if repair_status.get("repair_required"):
        return {
            "status": "config_repair_required",
            "resume_reason": _repair_resume_reason(client_type),
            "current_job": _job_resume_summary(job, selected_ids, selected_bindings=selected_bindings),
            "config_repair": repair_status,
            "next_turn": config_repair_turn(client_type=client_type),
            "non_actions": [
                _repair_project_init_block_label(client_type),
                "do not edit target-client activation state directly outside contextforge-helper repair",
                "do not mutate user-global config or trust",
            ],
        }
    reload_requirement = client_reload_requirement(client_type, event="project_activation_apply")
    if reload_requirement and reload_requirement.get("blocks_validation_until_done") and not _job_tools_registered_observed(job):
        return {
            "status": "client_reload_required",
            "resume_reason": "project activation was applied, and this target client must reload before installed tools register",
            "current_job": _job_resume_summary(job, selected_ids, selected_bindings=selected_bindings),
            "client_reload_requirement": reload_requirement,
            "next_turn": installation_complete_turn(client_type=client_type, reload_requirement=reload_requirement),
            "non_actions": [
                _validation_not_recorded_label(client_type),
                "do not call further project-init tools after apply succeeds",
                "do not mutate user-global config or trust",
            ],
        }
    if _job_tools_registered_observed(job):
        return None
    return {
        "status": "installed_reload_required",
        "resume_reason": "project init already wrote project-local config and state; selected tools are installed",
        "current_job": _job_resume_summary(job, selected_ids, selected_bindings=selected_bindings),
        "next_turn": installation_complete_turn(client_type=client_type, reload_requirement=client_reload_requirement(client_type, event="project_activation_apply")),
        "non_actions": [
            "do not restart project-init service selection",
            "do not call further project-init tools after apply succeeds",
            "do not mutate user-global config or trust",
        ],
    }


def record_project_init_client_reload(
    *,
    project_root: str | Path,
    client_type: str = "pi",
    validation_mode: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    if validation_mode is not None:
        raise ProjectInitHelperError(
            "project-init reload reporting is install-only and non-authoritative; "
            "do not request post-install validation or service probing from reload reports"
        )
    root = project_state.validate_project_root(project_root, require_workspace=True)
    state, job, selected = _pending_validation_state_job(root, client_type=client_type)
    selected_bindings = _job_selected_service_bindings(job)
    reload_requirement = client_reload_requirement(client_type, event="project_activation_apply")
    if not reload_requirement or not reload_requirement.get("blocks_validation_until_done"):
        result = {
            "status": "reload_not_required",
            "client_type": client_type,
            "current_job": _job_resume_summary(job, selected, selected_bindings=selected_bindings),
        }
        return result
    result = {
        "status": "client_reload_report_ignored",
        "client_type": client_type,
        "current_job": _job_resume_summary(job, selected, selected_bindings=selected_bindings),
        "reload_state": "reload_required",
        "message": (
            "Reload reports are not recorded as proof. The project remains at "
            "reload_required until a post-reload target-client tool readback proves the tools registered."
        ),
        "non_actions": [
            _validation_not_recorded_label(client_type),
            "no reload acknowledgement state write",
            "no project-local client config write",
            _no_user_global_mutation_label(client_type),
            "no ContextForge registry or catalog mutation",
        ],
    }
    return result


def _post_reload_validation_continuation(
    root: Path,
    state: Mapping[str, Any],
    job: Mapping[str, Any],
    selected: Sequence[str],
    *,
    selected_bindings: Sequence[str],
    client_type: str,
    validation_mode: str | None,
) -> dict[str, Any]:
    return {}


def repair_pending_project_init_config(
    *,
    project_root: str | Path,
    client_type: str = "codex",
    contextforge_servers: Iterable[dict[str, Any]] | None = None,
    server_instances_root: str | Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    root = project_state.validate_project_root(project_root, require_workspace=True)
    inspection = project_state.inspect_project_init_state(root, require_workspace=True)
    if inspection.get("lifecycle_status") == "invalid_repairable":
        return repair_missing_project_init_state(project_root=root, client_type=client_type, dry_run=dry_run)
    state, job, selected = _current_project_init_state_job(root, client_type=client_type)
    selected_bindings = _job_selected_service_bindings(job)
    if not selected:
        raise ProjectInitHelperError("current project-init job has no selected service ids")
    if not job.get("consent_receipt_refs"):
        raise ProjectInitHelperError("current project-init job has no prior scoped consent receipt refs")
    services = _services_from_state_or_catalog(root, state, selected, selected_bindings=selected_bindings, client_type=client_type)
    config_plan = _client_activation_plan(root, services, client_type=client_type, existing_state=state)
    if config_plan.get("decision") == "block":
        return _config_conflict_response(root=root, client_type=client_type, config_plan=config_plan, services=services, inputs={})
    repair_required = config_plan.get("before_digest") != config_plan.get("after_digest") or config_plan.get("before_digest") != job.get("local_client_config_digest")
    result = {
        "status": "config_repair_dry_run" if dry_run else ("config_repaired" if repair_required else "config_already_current"),
        "project_root": str(root),
        "client_type": client_type,
        "current_job": _job_resume_summary(job, selected, selected_bindings=selected_bindings),
        "config_plan": {key: value for key, value in config_plan.items() if key != "next_text"},
        "next_turn": installation_complete_turn(
            client_type=client_type,
            reload_requirement=client_reload_requirement(client_type, event="project_activation_apply"),
        ),
        "non_actions": [
            _no_user_global_mutation_label(client_type),
            "no ContextForge registry or catalog mutation",
            "no backend install or restart",
        ],
    }
    if dry_run:
        return result
    if repair_required:
        _write_client_activation(root, config_plan, client_type=client_type)
        job = json.loads(json.dumps(job))
        job["selected_service_ids"] = [str(service.get("service_identity_id")) for service in services]
        job["selected_service_bindings"] = [str(service.get("service_binding")) for service in services]
        job["local_client_config_digest"] = config_plan.get("after_digest")
        job.setdefault("step_statuses", []).append(
            {
                "operation_id": _repair_activation_operation_id(client_type),
                "operation_type": _repair_activation_operation_type(client_type),
                "status": "completed",
                "idempotency_key": f"repair-{client_type}-activation-" + str(job.get("plan_id") or job.get("job_id")),
                "pre_digest": config_plan.get("before_digest"),
                "post_digest": config_plan.get("after_digest"),
                "recovery_state": "none",
            }
        )
        job["recovery_state"] = "none"
        if client_type == "pi":
            validation_plan = binding.build_project_init_validation_plan(
                services,
                validation_mode="installed",
                target_client=client_type,
            )
            state = project_state.apply_project_init_activation_to_state(
                json.loads(json.dumps(state)),
                services,
                target_client=client_type,
                client_config_plan=config_plan,
                validation_plan=validation_plan,
                validation_results={},
                activation_job=job,
                consent_receipt_refs=list(job.get("consent_receipt_refs") or []),
                updated_by="control_plane_project_init_helper",
            )
        else:
            state = json.loads(json.dumps(state))
            state["project_init"]["activation_jobs"][str(job["job_id"])] = job
        written = project_state.write_state_atomic(root, state, updated_by="control_plane_project_init_helper")
        result["state_revision"] = written["meta"]["revision"]
    return result


def repair_missing_project_init_state(
    *,
    project_root: str | Path,
    client_type: str = "codex",
    dry_run: bool = False,
) -> dict[str, Any]:
    root = project_state.validate_project_root(project_root, require_workspace=True)
    inspection = project_state.inspect_project_init_state(root, require_workspace=True)
    if inspection.get("lifecycle_status") != "invalid_repairable":
        raise ProjectInitHelperError("project state is not in a repairable missing-project_init shape")
    raw_state = project_state.read_json_file(project_state.project_state_path(root))
    project_state.validate_state_root(raw_state, root)
    repaired = json.loads(json.dumps(raw_state))
    repaired["status"] = "in_progress"
    repaired["project_init"] = project_state.default_project_init()
    project_state.normalize_service_identity_fields(repaired)
    services = _repair_services_from_state(root, repaired, client_type=client_type)
    if not services:
        raise ProjectInitHelperError("repairable project state has no service records to resume")
    config_plan = _client_activation_plan(root, services, client_type=client_type, existing_state=repaired)
    now = now_timestamp()
    plan_id = "project-init-repair-" + stable_digest(
        {
            "project_root": str(root),
            "client_type": client_type,
            "service_identity_ids": [service["service_identity_id"] for service in services],
            "config_before_digest": config_plan.get("before_digest"),
        }
    ).removeprefix("sha256:")[:16]
    job_id = f"job-{plan_id}"
    selected_ids = [str(service["service_identity_id"]) for service in services]
    selected_bindings = [str(service["service_binding"]) for service in services]
    repaired["project_init"] = {
        "current_job_id": job_id,
        "activation_jobs": {
            job_id: {
                "job_id": job_id,
                "plan_id": plan_id,
                "plan_digest": stable_digest({"plan_id": plan_id, "services": selected_ids, "repair": "missing_project_init"}),
                "status": "installed",
                "client_type": client_type,
                "selected_service_ids": selected_ids,
                "selected_service_bindings": selected_bindings,
                "step_statuses": [
                    {
                        "operation_id": "import-existing-project-init-state",
                        "operation_type": "repair_missing_project_init_state",
                        "status": "completed",
                        "idempotency_key": stable_digest({"plan_id": plan_id, "op": "repair-state"}).removeprefix("sha256:")[:32],
                        "pre_digest": inspection.get("state_path") and project_state.state_file_artifact_digest(root),
                        "post_digest": None,
                        "recovery_state": None,
                    },
                    {
                        "operation_id": _repair_activation_operation_id(client_type),
                        "operation_type": _repair_activation_operation_type(client_type),
                        "status": "skipped" if config_plan.get("decision") == "block" else "completed",
                        "idempotency_key": stable_digest({"plan_id": plan_id, "op": client_type}).removeprefix("sha256:")[:32],
                        "pre_digest": config_plan.get("before_digest"),
                        "post_digest": config_plan.get("before_digest"),
                        "recovery_state": None,
                    },
                ],
                "stale_plan_inputs": {
                    "base_project_state": {
                        "artifact_status": "invalid_repairable",
                        "digest": project_state.state_file_artifact_digest(root),
                        "message": inspection.get("schema_error"),
                        "recovery": "repair_missing_project_init_state",
                    }
                },
                "consent_receipt_refs": ["run/project-init-repair/imported-existing-state.json"],
                "local_client_config_digest": config_plan.get("before_digest"),
                "validation_records": {},
                "recovery_state": "none",
                "non_actions": [
                    "preserved existing service records",
                    "did not overwrite unmanaged target-client config",
                    _no_user_global_mutation_label(client_type),
                    "no ContextForge registry or catalog mutation",
                    "no secret or token material write",
                ],
                "x_repair_kind": "missing_project_init",
            }
        },
        "x_hook_prompt_state": project_state.HOOK_PROMPT_COMPLETED_UNVERIFIED,
    }
    repaired.setdefault("migration", project_state.default_migration())
    repaired["migration"].setdefault("client_config_migrations", {})
    _record_repaired_client_config_evidence(repaired, root, client_type=client_type, config_plan=config_plan)
    project_state.validate_state(repaired)
    result = {
        "status": "state_repair_dry_run" if dry_run else "state_repaired",
        "project_root": str(root),
        "client_type": client_type,
        "project_state_inspection": inspection,
        "current_job": _job_resume_summary(
            repaired["project_init"]["activation_jobs"][job_id],
            selected_ids,
            selected_bindings=selected_bindings,
        ),
        "config_plan": {key: value for key, value in config_plan.items() if key != "next_text"},
        "next_turn": validation_choice_turn(),
        "non_actions": [
            "no target-client config write",
            _no_user_global_mutation_label(client_type),
            "no ContextForge registry or catalog mutation",
            "no secrets or token material written",
        ],
    }
    if dry_run:
        return result
    written = project_state.write_state_atomic(
        root,
        repaired,
        updated_by="control_plane_project_init_helper",
        allow_invalid_existing=True,
    )
    result["state_revision"] = written["meta"]["revision"]
    return result


def record_project_init_validation(
    *,
    project_root: str | Path,
    validation_mode: str,
    validation_results: Mapping[str, Any] | None = None,
    client_type: str = "codex",
    dry_run: bool = False,
) -> dict[str, Any]:
    return {
        "ok": False,
        "status": "project_init_validation_retired",
        "project_root": str(project_root),
        "client_type": client_type,
        "message": (
            "Project init is install-only. Do not record post-install validation, "
            "do not request service probes, and do not ask the user to choose validation. "
            "If tools were installed, tell the user a new session or reload is required before they register."
        ),
        "non_actions": [
            "no project-init validation recorded",
            "no target-client service probe requested",
            "no project-local client config write",
            _no_user_global_mutation_label(client_type),
            "no ContextForge registry or catalog mutation",
        ],
    }


def _validation_results_diagnostic(services: Sequence[Mapping[str, Any]], validation_results: Mapping[str, Any]) -> dict[str, Any]:
    received_keys = [str(key) for key in validation_results.keys()]
    expected_by_binding: dict[str, list[str]] = {}
    expected_keys: set[str] = set()
    matched_keys: list[str] = []
    missing_keys: list[str] = []
    invalid_value_keys: list[str] = []
    for service in services:
        binding_id = str(service.get("service_binding") or service.get("service_family") or "")
        service_identity_id = str(service.get("service_identity_id") or "")
        keys = [key for key in (binding_id, project_state._state_map_key(binding_id), service_identity_id) if key]
        keys = list(dict.fromkeys(keys))
        expected_by_binding[binding_id] = keys
        expected_keys.update(keys)
        service_matched_keys = [
            key for key in received_keys
            if key in keys and isinstance(validation_results.get(key), Mapping)
        ]
        if service_matched_keys:
            matched_keys.extend(service_matched_keys)
        else:
            missing_keys.append(binding_id)
    unmatched_keys = [key for key in received_keys if key not in expected_keys]
    for key in received_keys:
        if key in expected_keys and not isinstance(validation_results.get(key), Mapping):
            invalid_value_keys.append(key)
    return {
        "expected_keys_by_service_binding": expected_by_binding,
        "received_keys": received_keys,
        "matched_keys": list(dict.fromkeys(matched_keys)),
        "missing_keys": missing_keys,
        "unmatched_keys": unmatched_keys,
        "invalid_value_keys": invalid_value_keys,
    }


def _validation_report_diagnostic(
    services: Sequence[Mapping[str, Any]],
    validation_results: Mapping[str, Any],
    *,
    client_type: str,
) -> dict[str, Any]:
    insufficient_keys: list[str] = []
    missing_fields_by_key: dict[str, list[str]] = {}
    invalid_fields_by_key: dict[str, list[str]] = {}
    for service in services:
        binding_id = str(service.get("service_binding") or service.get("service_family") or "")
        service_identity_id = str(service.get("service_identity_id") or "")
        result_key = next(
            (
                key
                for key in (binding_id, project_state._state_map_key(binding_id), service_identity_id)
                if key and isinstance(validation_results.get(key), Mapping)
            ),
            None,
        )
        if not result_key:
            continue
        result = validation_results.get(result_key)
        if not isinstance(result, Mapping):
            continue
        service_family = str(service.get("service_family") or binding_id.split(":", 1)[0] or "")
        missing, invalid = _safe_probe_proof_gaps(service_family, result, client_type=client_type)
        if missing or invalid:
            insufficient_keys.append(result_key)
            if missing:
                missing_fields_by_key[result_key] = missing
            if invalid:
                invalid_fields_by_key[result_key] = invalid
    return {
        "insufficient_keys": insufficient_keys,
        "missing_fields_by_key": missing_fields_by_key,
        "invalid_fields_by_key": invalid_fields_by_key,
    }


def _safe_probe_proof_gaps(service_family: str, result: Mapping[str, Any], *, client_type: str) -> tuple[list[str], list[str]]:
    contract = safe_probe_contract(service_family)
    if not contract:
        return [], []
    if result.get("status") == "skipped":
        return ([] if result.get("skipped_reason") else ["skipped_reason"]), []
    missing: list[str] = []
    invalid: list[str] = []
    for field in (
        "status",
        "target_client",
        "safe_probe_result",
        "safe_probe_id",
        "tool_name",
        "result_summary",
    ):
        value = result.get(field)
        if value is None or value == "" or value == []:
            missing.append(field)

    if result.get("target_client") not in {client_type, None}:
        invalid.append("target_client")
    accepted_proof_kinds = {str(item) for item in contract.get("accepted_proof_kinds") or []}
    if result.get("proof_kind") and result.get("proof_kind") not in accepted_proof_kinds:
        invalid.append("proof_kind")
    safe_operations = {str(item) for item in safe_validation_policy(service_family).get("safe_operations") or []}
    if result.get("safe_probe_id") not in safe_operations:
        invalid.append("safe_probe_id")
    allowed_tools = [str(item) for item in contract.get("allowed_tool_name_patterns") or []]
    tool_name = str(result.get("tool_name") or "")
    if allowed_tools and not any(pattern and pattern in tool_name for pattern in allowed_tools):
        invalid.append("tool_name")
    if result.get("status") not in {"passed", "verified"}:
        invalid.append("status")
    if result.get("safe_probe_result") != "passed":
        invalid.append("safe_probe_result")
    if "target_client_visible" in result and result.get("target_client_visible") is not True:
        invalid.append("target_client_visible")
    return list(dict.fromkeys(missing)), list(dict.fromkeys(invalid))


def _normalize_validation_results_for_recording(
    services: Sequence[Mapping[str, Any]],
    validation_results: Mapping[str, Any],
    *,
    client_type: str,
) -> dict[str, Any]:
    normalized = {
        str(key): (dict(value) if isinstance(value, Mapping) else value)
        for key, value in validation_results.items()
    }
    for service in services:
        binding_id = str(service.get("service_binding") or service.get("service_family") or "")
        service_identity_id = str(service.get("service_identity_id") or "")
        result_key = next(
            (
                key
                for key in (binding_id, project_state._state_map_key(binding_id), service_identity_id)
                if key and isinstance(normalized.get(key), Mapping)
            ),
            None,
        )
        if not result_key:
            continue
        result = dict(normalized[result_key])
        if result.get("status") in {"passed", "verified"} and result.get("safe_probe_result") == "passed":
            result.setdefault("target_client", client_type)
            result.setdefault("target_client_visible", True)
            result.setdefault(
                "proof_kind",
                "pi_safe_probe_result" if client_type == "pi" else "target_client_safe_probe_result",
            )
            result.setdefault(
                "verification_trace_refs",
                [f"contextforge://control-plane/traces/{project_state._state_map_key(binding_id)}-{client_type}-reported-working"],
            )
        normalized[result_key] = result
    return normalized


def _expected_validation_results_shape(services: Sequence[Mapping[str, Any]], *, target_client: str) -> dict[str, Any]:
    service = services[0] if services else {}
    binding_id = str(service.get("service_binding") or "context7:canonical")
    service_family = str(service.get("service_family") or binding_id.split(":", 1)[0] or "context7")
    contract = safe_probe_contract(service_family)
    contract_shape = contract.get("validation_result_shape") if isinstance(contract.get("validation_result_shape"), Mapping) else {}
    if contract_shape:
        shape = {
            key: value
            for key, value in dict(contract_shape).items()
            if key not in {"target_client_visible", "proof_kind", "verification_trace_refs"}
        }
        shape["tool_name"] = str((contract.get("default_probe") or {}).get("tool_name_hint") or "")
        shape["target_client"] = target_client
        shape["result_summary"] = "brief summary of the actual target-client tool output"
    else:
        shape = {
            "status": "passed",
            "target_client": target_client,
            "tool_name": "target-client-visible safe probe tool name",
            "safe_probe_result": "passed",
            "safe_probe_id": "list-tools",
            "result_summary": "brief summary of the actual target-client tool output",
        }
    return {
        binding_id: shape,
    }


def _pending_validation_state_job(root: Path, *, client_type: str) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    state, job, selected = _current_project_init_state_job(root, client_type=client_type)
    pending = pending_validation_resume(project_root=root, client_type=client_type)
    if pending is None:
        raise ProjectInitHelperError("current project-init job is not pending validation")
    return state, job, selected


def _current_project_init_state_job(root: Path, *, client_type: str) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    state = project_state.load_state(root)
    if not isinstance(state, Mapping):
        raise ProjectInitHelperError("project state is missing")
    project_init = state.get("project_init") if isinstance(state.get("project_init"), Mapping) else {}
    jobs = project_init.get("activation_jobs") if isinstance(project_init.get("activation_jobs"), Mapping) else {}
    current_job_id = str(project_state.project_init_current_job_id_for_client(dict(state), client_type) or "")
    job = jobs.get(current_job_id) if current_job_id else None
    if not isinstance(job, Mapping):
        raise ProjectInitHelperError("project state has no current project-init job")
    if str(job.get("client_type") or client_type) != client_type:
        raise ProjectInitHelperError("current project-init job client_type does not match")
    selected = _job_selected_service_ids(job)
    return dict(state), dict(job), selected


def _job_selected_service_ids(job: Mapping[str, Any]) -> list[str]:
    selected_ids = [str(service_id) for service_id in job.get("selected_service_ids") or [] if service_id]
    if selected_ids:
        return selected_ids
    return [str(binding_id) for binding_id in job.get("selected_service_bindings") or [] if binding_id]


def _job_selected_service_bindings(job: Mapping[str, Any]) -> list[str]:
    return [str(binding_id) for binding_id in job.get("selected_service_bindings") or [] if binding_id]


def _job_tools_registered_observed(job: Mapping[str, Any]) -> bool:
    fsm = job.get("x_client_reload_fsm") if isinstance(job.get("x_client_reload_fsm"), Mapping) else {}
    if str(fsm.get("state") or "") == "tools_registered_observed" and bool(fsm.get("observed_at") or fsm.get("proof_ref")):
        return True
    validation_records = job.get("validation_records") if isinstance(job.get("validation_records"), Mapping) else {}
    return any(
        isinstance(record, Mapping)
        and str(record.get("status") or "") in {"passed", "verified"}
        and record.get("target_client_visible") is True
        for record in validation_records.values()
    )


def _job_resume_summary(job: Mapping[str, Any], selected_service_ids: Sequence[str], *, selected_bindings: Sequence[str] | None = None) -> dict[str, Any]:
    return {
        "job_id": job.get("job_id"),
        "plan_id": job.get("plan_id"),
        "plan_digest": job.get("plan_digest"),
        "status": job.get("status"),
        "recovery_state": job.get("recovery_state"),
        "selected_service_ids": list(selected_service_ids),
        "selected_service_bindings": list(selected_bindings if selected_bindings is not None else _job_selected_service_bindings(job)),
        "local_client_config_digest": job.get("local_client_config_digest"),
        "client_reload_fsm": dict(job.get("x_client_reload_fsm") or {}) if isinstance(job.get("x_client_reload_fsm"), Mapping) else None,
    }


def _pending_job_config_repair_status(
    root: Path,
    state: Mapping[str, Any],
    job: Mapping[str, Any],
    selected: Sequence[str],
    *,
    selected_bindings: Sequence[str] | None = None,
    client_type: str,
) -> dict[str, Any]:
    if not selected:
        return {"repair_required": False, "reason": "no selected service ids"}
    try:
        services = _services_from_state_or_catalog(root, state, selected, selected_bindings=selected_bindings or [], client_type=client_type)
        config_plan = _client_activation_plan(root, services, client_type=client_type, existing_state=state)
    except Exception as exc:
        return {
            "repair_required": True,
            "reason": f"could not evaluate project-local config repair status: {type(exc).__name__}: {exc}",
            "config_plan": None,
        }
    planned_digest = str(job.get("local_client_config_digest") or "")
    before_digest = str(config_plan.get("before_digest") or "")
    after_digest = str(config_plan.get("after_digest") or "")
    current_service_ids = [str(service.get("service_identity_id") or "") for service in services]
    selected_ids = [str(service_id) for service_id in selected]
    service_id_repair_required = current_service_ids != selected_ids
    changed_bindings = [
        str(change.get("service_binding"))
        for change in config_plan.get("changes") or []
        if isinstance(change, Mapping) and change.get("operation") in {"append", "replace", "record", "blocked"}
    ]
    if service_id_repair_required:
        changed_bindings.extend(str(service.get("service_binding") or "") for service in services)
    repair_required = before_digest != after_digest or service_id_repair_required
    return {
        "repair_required": repair_required,
        "service_id_repair_required": service_id_repair_required,
        "current_service_ids": current_service_ids,
        "selected_service_ids": selected_ids,
        "current_config_digest": before_digest,
        "expected_or_repaired_config_digest": after_digest,
        "recorded_job_config_digest": planned_digest or None,
        "write_allowed": bool(config_plan.get("write_allowed")),
        "changed_service_bindings": changed_bindings,
        "config_plan": {key: value for key, value in config_plan.items() if key != "next_text"},
    }


def _services_from_state_or_catalog(
    root: Path,
    state: Mapping[str, Any],
    selected: Sequence[str],
    *,
    selected_bindings: Sequence[str] = (),
    client_type: str,
) -> list[dict[str, Any]]:
    services_by_binding = {
        str(service.get("service_binding")): service
        for service in (state.get("services") or {}).values()
        if isinstance(service, Mapping) and service.get("service_binding")
    }
    services_by_identity = {
        str((service.get("x_service_identity") or {}).get("id") or service.get("x_service_identity_id")): service
        for service in (state.get("services") or {}).values()
        if isinstance(service, Mapping)
        and (
            (isinstance(service.get("x_service_identity"), Mapping) and (service.get("x_service_identity") or {}).get("id"))
            or service.get("x_service_identity_id")
        )
    }
    services: list[dict[str, Any]] = []
    missing: list[str] = []
    selected_binding_list = list(selected_bindings)
    for index, service_ref in enumerate(selected):
        fallback_binding = selected_binding_list[index] if index < len(selected_binding_list) else service_ref
        service = services_by_identity.get(service_ref) or services_by_binding.get(service_ref) or services_by_binding.get(fallback_binding)
        if service:
            target_clients = service.get("target_clients") if isinstance(service.get("target_clients"), Mapping) else {}
            target_client = target_clients.get(client_type) if isinstance(target_clients.get(client_type), Mapping) else {}
            codex = target_clients.get("codex") if isinstance(target_clients.get("codex"), Mapping) else {}
            verification_layers = service.get("verification_layers") if isinstance(service.get("verification_layers"), Mapping) else {}
            tool_policy = verification_layers.get("tool_policy") if isinstance(verification_layers.get("tool_policy"), Mapping) else {}
            policy = tool_policy.get("policy") if isinstance(tool_policy.get("policy"), Mapping) else None
            service_family = str(service.get("service_family") or str(fallback_binding).split(":", 1)[0])
            services.append(
                _candidate(
                    {
                        "service_family": service_family,
                        "canonical_service": service_family,
                        "service_binding": service.get("service_binding") or fallback_binding,
                        "codex_alias": codex.get("alias") or target_client.get("alias") or str(fallback_binding).split(":", 1)[0],
                        "pi_tool_prefix": target_client.get("pi_tool_prefix") or target_client.get("alias"),
                        "instantiation_class": service.get("instantiation_class"),
                        "backend_instance": service.get("backend_instance"),
                        "virtual_server": service.get("virtual_server"),
                        "contextforge_server_id": service.get("x_contextforge_server_id"),
                        "descriptor_digest": service.get("x_descriptor_digest"),
                        "gateway": (service.get("lifecycle") or {}).get("gateway") if isinstance(service.get("lifecycle"), Mapping) else None,
                        "contextforge_readback_status": ((service.get("verification_layers") or {}).get("contextforge_gateway") or {}).get("status")
                        if isinstance((service.get("verification_layers") or {}).get("contextforge_gateway"), Mapping)
                        else None,
                        "validation_policy": dict(policy) if isinstance(policy, Mapping) else safe_validation_policy(service_family),
                    },
                    client_type=client_type,
                )
            )
        else:
            missing.append(fallback_binding)
    if missing:
        resolved = _resolve_selected_services(root, missing, client_type=client_type)
        services.extend(resolved)
    return services


def _repair_services_from_state(root: Path, state: Mapping[str, Any], *, client_type: str) -> list[dict[str, Any]]:
    services: list[dict[str, Any]] = []
    for service in (state.get("services") or {}).values():
        if not isinstance(service, Mapping) or not service.get("service_binding"):
            continue
        target_clients = service.get("target_clients") if isinstance(service.get("target_clients"), Mapping) else {}
        target_client = target_clients.get(client_type) if isinstance(target_clients.get(client_type), Mapping) else {}
        codex = target_clients.get("codex") if isinstance(target_clients.get("codex"), Mapping) else {}
        identity = service.get("x_service_identity") if isinstance(service.get("x_service_identity"), Mapping) else {}
        service_identity_id = str(service.get("x_service_identity_id") or identity.get("id") or "")
        service_family = str(service.get("service_family") or str(service.get("service_binding")).split(":", 1)[0])
        verification_layers = service.get("verification_layers") if isinstance(service.get("verification_layers"), Mapping) else {}
        tool_policy = verification_layers.get("tool_policy") if isinstance(verification_layers.get("tool_policy"), Mapping) else {}
        policy = tool_policy.get("policy") if isinstance(tool_policy.get("policy"), Mapping) else safe_validation_policy(service_family)
        candidate = _candidate(
            {
                "service_family": service_family,
                "canonical_service": service_family,
                "service_binding": service.get("service_binding"),
                "codex_alias": codex.get("alias") or target_client.get("alias") or service_family,
                "pi_tool_prefix": target_client.get("pi_tool_prefix") or target_client.get("alias"),
                "instantiation_class": service.get("instantiation_class"),
                "backend_instance": service.get("backend_instance"),
                "virtual_server": service.get("virtual_server"),
                "contextforge_server_id": service.get("x_contextforge_server_id") or identity.get("contextforge_server_id"),
                "descriptor_digest": service.get("x_descriptor_digest") or identity.get("descriptor_digest"),
                "gateway": (service.get("lifecycle") or {}).get("gateway") if isinstance(service.get("lifecycle"), Mapping) else None,
                "contextforge_readback_status": ((service.get("verification_layers") or {}).get("contextforge_gateway") or {}).get("status")
                if isinstance((service.get("verification_layers") or {}).get("contextforge_gateway"), Mapping)
                else None,
                "validation_policy": dict(policy) if isinstance(policy, Mapping) else safe_validation_policy(service_family),
            },
            client_type=client_type,
        )
        if service_identity_id:
            candidate["service_identity_id"] = service_identity_id
        services.append(candidate)
    if not services:
        _resolve_selected_services(root, [], client_type=client_type)
    return services


def _record_repaired_client_config_evidence(
    state: dict[str, Any],
    root: Path,
    *,
    client_type: str,
    config_plan: Mapping[str, Any],
) -> None:
    migrations = state.setdefault("migration", project_state.default_migration()).setdefault("client_config_migrations", {})
    blockers = [dict(item) for item in config_plan.get("blockers") or [] if isinstance(item, Mapping)]
    changes = [dict(item) for item in config_plan.get("changes") or [] if isinstance(item, Mapping)]
    if client_type == "codex":
        source_path = ".codex/config.toml"
        ownership_class = "unmanaged_same_name" if config_plan.get("decision") == "block" else ("owned" if (root / source_path).exists() else "absent")
        disposition = "conflict" if config_plan.get("decision") == "block" else ("imported" if ownership_class == "owned" else "not_present")
    elif client_type == "gemini":
        source_path = ".gemini/settings.json"
        ownership_class = "unmanaged_same_name" if config_plan.get("decision") == "block" else ("owned" if (root / source_path).exists() else "absent")
        disposition = "conflict" if config_plan.get("decision") == "block" else ("imported" if ownership_class == "owned" else "not_present")
    elif client_type == "opencode":
        source_path = "opencode.json"
        ownership_class = "unmanaged_same_name" if config_plan.get("decision") == "block" else ("owned" if (root / source_path).exists() else "absent")
        disposition = "conflict" if config_plan.get("decision") == "block" else ("imported" if ownership_class == "owned" else "not_present")
    elif client_type == "pi":
        source_path = None
        ownership_class = "owned"
        disposition = "imported"
    else:
        source_path = None
        ownership_class = "unsupported_schema"
        disposition = "conflict"
    migrations[client_type] = {
        "source_path": source_path,
        "ownership_class": ownership_class,
        "source_digest": str(config_plan.get("before_digest") or "").removeprefix("sha256:") or None,
        "disposition": disposition,
        "imported_binding_refs": [
            f"contextforge://control-plane/service-bindings/{change.get('service_binding')}"
            for change in changes
            if change.get("service_binding")
        ],
        "conflicts": blockers,
        "verification_trace_refs": [],
    }


def approve_project_init_plan(
    *,
    project_root: str | Path,
    plan: Mapping[str, Any],
    approval: Mapping[str, Any],
    local_approval_event_ref: str | None = None,
    actor: str = "developer",
    source_client: str | None = None,
    source_client_auth_strength: str = "shared_token",
) -> dict[str, Any]:
    root = project_state.validate_project_root(project_root, require_workspace=True)
    digest_errors = _validate_plan_digest(plan)
    if digest_errors:
        return {"decision": "block", "receipts": [], "reasons": digest_errors}
    challenge = plan.get("approval_challenge") if isinstance(plan.get("approval_challenge"), Mapping) else {}
    pending = _PENDING_CHALLENGES.get(str(challenge.get("challenge_id") or ""))
    if not pending:
        return {"decision": "block", "receipts": [], "reasons": ["approval challenge is not pending in helper state"]}
    if pending.get("plan_digest") != plan.get("plan_digest") or pending.get("project_root") != str(root):
        return {"decision": "block", "receipts": [], "reasons": ["approval challenge provenance does not match plan"]}
    event_ref = str(local_approval_event_ref or approval.get("local_approval_event_ref") or "")
    local_event = _LOCAL_APPROVAL_EVENTS.get(event_ref, {})
    if local_event.get("challenge_id") != challenge.get("challenge_id") or local_event.get("plan_digest") != plan.get("plan_digest"):
        return {"decision": "block", "receipts": [], "reasons": ["missing local approval event bound to challenge and plan digest"]}
    if local_event.get("channel") not in {"local_ui", "interactive_user"}:
        return {"decision": "block", "receipts": [], "reasons": ["local approval event channel is not trusted for project init"]}
    if approval.get("decision") != "approve":
        return {"decision": "declined", "receipts": [], "reasons": ["user did not approve"]}
    if approval.get("challenge_id") != challenge.get("challenge_id"):
        return {"decision": "block", "receipts": [], "reasons": ["approval challenge does not match plan"]}
    if approval.get("plan_digest") != plan.get("plan_digest"):
        return {"decision": "block", "receipts": [], "reasons": ["approval plan digest does not match"]}
    if str(plan.get("project_root")) != str(root):
        return {"decision": "block", "receipts": [], "reasons": ["approval project root does not match"]}

    receipt_source_client = source_client or str(plan.get("client_type") or "codex")
    receipts = []
    auth_plan = _authorization_plan(plan)
    for consent_class in plan.get("required_consent_classes") or []:
        receipts.append(
            authorization.create_consent_receipt(
                plan=auth_plan,
                consent_class=str(consent_class),
                actor=actor,
                source_client=receipt_source_client,
                source_client_auth_strength=source_client_auth_strength,
                approval_event_ref=str(local_event.get("event_ref") or approval.get("approval_event_ref") or challenge.get("challenge_id")),
                approval_evidence="developer approved exact ContextForge project-init plan digest",
                expires_at=str(pending.get("expires_at")),
                approval_nonce=str(pending.get("nonce")),
                scope={
                    "project_root": str(root),
                    "client": receipt_source_client,
                    "service_binding": _receipt_service_scope(plan, str(consent_class)),
                },
            )
        )
    _PENDING_CHALLENGES.pop(str(challenge.get("challenge_id")), None)
    _APPROVED_RECEIPT_IDS_BY_PLAN[str(plan.get("plan_id"))] = {str(receipt["receipt_id"]) for receipt in receipts}
    return {
        "decision": "allow",
        "plan_id": plan.get("plan_id"),
        "plan_digest": plan.get("plan_digest"),
        "receipts": receipts,
        "receipt_refs": [_receipt_ref(receipt) for receipt in receipts],
    }


def restore_process_local_approval_session(
    *,
    project_root: str | Path,
    plan: Mapping[str, Any],
    receipts: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Restore exact-plan approval state for short-lived local helper clients.

    The canonical helper MCP server keeps pending challenges and helper-issued
    receipt ids in process memory. Pi's global extension intentionally calls the
    helper through a short-lived local CLI process, so it must rehydrate only the
    exact unexpired challenge and receipt ids that are already present in the
    model-visible helper plan/approval results. This does not mint receipts or
    skip receipt validation; it only restores the process-local provenance map
    that the normal long-lived helper server would already have.
    """

    root = project_state.validate_project_root(project_root, require_workspace=True)
    digest_errors = _validate_plan_digest(plan)
    if digest_errors:
        raise ProjectInitHelperError("; ".join(digest_errors))
    if str(plan.get("project_root")) != str(root):
        raise ProjectInitHelperError("plan project root does not match requested project root")
    challenge = plan.get("approval_challenge") if isinstance(plan.get("approval_challenge"), Mapping) else {}
    challenge_id = str(challenge.get("challenge_id") or "")
    expires_at = str(challenge.get("expires_at") or "")
    if not challenge_id or not expires_at:
        raise ProjectInitHelperError("plan has no restorable approval challenge")
    try:
        expires = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProjectInitHelperError("approval challenge expiry is invalid") from exc
    if expires <= datetime.now(UTC):
        raise ProjectInitHelperError("approval challenge is expired")
    if challenge.get("plan_digest") != plan.get("plan_digest") or challenge.get("plan_id") != plan.get("plan_id"):
        raise ProjectInitHelperError("approval challenge does not match plan identity")
    _PENDING_CHALLENGES.setdefault(
        challenge_id,
        {
            "plan_id": plan.get("plan_id"),
            "plan_digest": plan.get("plan_digest"),
            "project_root": str(root),
            "expires_at": expires_at,
            "nonce": challenge.get("nonce"),
        },
    )
    receipt_ids = {str(receipt.get("receipt_id") or "") for receipt in receipts or [] if isinstance(receipt, Mapping)}
    receipt_ids.discard("")
    if receipt_ids:
        _APPROVED_RECEIPT_IDS_BY_PLAN.setdefault(str(plan.get("plan_id")), set()).update(receipt_ids)
    return {
        "status": "approval_session_restored",
        "challenge_id": challenge_id,
        "plan_digest": plan.get("plan_digest"),
        "restored_receipt_count": len(receipt_ids),
    }


def record_local_approval_event(
    *,
    project_root: str | Path,
    plan: Mapping[str, Any],
    issuer_token: str,
    channel: str = "local_ui",
) -> dict[str, Any]:
    """Record local approval UI evidence for a pending challenge.

    This simulates the user-local client/UI side of approval for the MVP. It is
    intentionally not exposed by the MCP wrapper as a general agent tool and
    requires a process-local issuer capability that is never embedded in plans.
    """

    if not secrets.compare_digest(issuer_token, _LOCAL_APPROVAL_ISSUER_TOKEN):
        raise ProjectInitHelperError("local approval event issuer is not authorized")
    root = project_state.validate_project_root(project_root, require_workspace=True)
    digest_errors = _validate_plan_digest(plan)
    if digest_errors:
        raise ProjectInitHelperError("; ".join(digest_errors))
    challenge = plan.get("approval_challenge") if isinstance(plan.get("approval_challenge"), Mapping) else {}
    pending = _PENDING_CHALLENGES.get(str(challenge.get("challenge_id") or ""))
    if not pending or pending.get("project_root") != str(root):
        raise ProjectInitHelperError("approval challenge is not pending for this project root")
    if channel not in {"local_ui", "interactive_user"}:
        raise ProjectInitHelperError("unsupported local approval event channel")
    event_id = "local-approval-" + secrets.token_urlsafe(18).replace("-", "").replace("_", "")[:24]
    event = {
        "event_ref": event_id,
        "channel": channel,
        "challenge_id": challenge.get("challenge_id"),
        "plan_digest": plan.get("plan_digest"),
        "project_root": str(root),
        "recorded_at": now_timestamp(),
    }
    _LOCAL_APPROVAL_EVENTS[event_id] = event
    return dict(event)


def apply_approved_project_init(
    *,
    project_root: str | Path,
    plan: Mapping[str, Any],
    receipts: Sequence[Mapping[str, Any]],
    contextforge_servers: Iterable[dict[str, Any]] | None = None,
    server_instances_root: str | Path | None = None,
    catalog_revision_or_etag: str | None = None,
    recovery_plan: Mapping[str, Any] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    root = project_state.validate_project_root(project_root, require_workspace=True)
    if str(plan.get("project_root")) != str(root):
        raise ProjectInitHelperError("plan project root does not match requested project root")
    digest_errors = _validate_plan_digest(plan)
    if digest_errors:
        raise ProjectInitHelperError("; ".join(digest_errors))
    services = list(plan.get("selected_services") or [])
    _validate_plan_not_stale(
        plan,
        services=services,
        project_root=root,
        contextforge_servers=contextforge_servers,
        server_instances_root=server_instances_root,
        catalog_revision_or_etag=catalog_revision_or_etag,
        recovery_plan=recovery_plan,
    )
    _validate_receipts_for_plan(plan, receipts, project_root=root, consume=False)
    client_type = str(plan.get("client_type") or "codex")
    recovery_ensured_bindings = _recovery_ensured_service_bindings(plan, recovery_plan, client_type=client_type)
    provisioning_results = [] if dry_run else _apply_project_scoped_provisioning(
        root,
        services,
        plan=plan,
        skip_service_bindings=recovery_ensured_bindings,
    )
    services = _services_with_project_scoped_provisioning_results(services, provisioning_results)
    activation_config_plan = _client_activation_plan(
        root,
        services,
        client_type=client_type,
        existing_state=project_state.read_or_default(
            root,
            allow_invalid_existing=_planned_invalid_state_replacement(plan),
        ),
    )
    if activation_config_plan.get("decision") == "block":
        return _apply_time_config_recovery_required_response(
            root=root,
            client_type=client_type,
            plan=plan,
            services=services,
            config_plan=activation_config_plan,
            provisioning_results=provisioning_results,
        )
    job = _activation_job_from_plan(
        plan,
        receipts,
        provisioning_results=provisioning_results,
        config_plan=activation_config_plan,
    )
    receipt_refs = [_receipt_ref(receipt)["ref"] for receipt in receipts]
    result = binding.apply_project_init_service_activation(
        root,
        services,
        validation_mode="installed",
        approval_scope=binding.PROJECT_INIT_APPROVAL_SCOPE,
        target_client=client_type,
        activation_job=job,
        consent_receipt_refs=receipt_refs,
        allow_invalid_existing_state=_planned_invalid_state_replacement(plan),
        dry_run=True,
    )
    if not dry_run:
        _write_client_activation(root, activation_config_plan, client_type=client_type)
        written_state = project_state.write_state_atomic(
            root,
            result["planned_state"],
            updated_by="control_plane_project_init_helper",
            allow_invalid_existing=_planned_invalid_state_replacement(plan),
        )
        _validate_receipts_for_plan(plan, receipts, project_root=root, consume=True)
        result["dry_run"] = False
        result["state_revision"] = written_state["meta"]["revision"]
    result["job"] = job
    reload_requirement = client_reload_requirement(client_type, event="project_activation_apply")
    result["installation_status"] = "installed"
    result["installed_service_bindings"] = [str(service.get("service_binding") or "") for service in services]
    result["message"] = "ContextForge tools are installed for this project. A new session or reload is required before the tools register in the client."
    if reload_requirement:
        result["client_reload_requirement"] = reload_requirement
    result["next_turn"] = installation_complete_turn(client_type=client_type, reload_requirement=reload_requirement)
    return result


def record_project_init_service_decision(
    *,
    project_root: str | Path,
    selected_services: Sequence[Mapping[str, Any] | str],
    decision_state: str,
    client_type: str = "codex",
    source_plan_id: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    root = project_state.validate_project_root(project_root, require_workspace=True)
    if decision_state not in {"declined", "deferred"}:
        raise ProjectInitHelperError(f"unsupported project-init decision state: {decision_state}")
    current_state = project_state.read_or_default(root)
    services = _resolve_selected_services(
        root,
        selected_services,
        client_type=client_type,
    )
    next_state = project_state.apply_project_init_decisions_to_state(
        current_state,
        [dict(service) for service in services],
        decision_state=decision_state,
        target_client=client_type,
        source_plan_id=source_plan_id,
        updated_by="control_plane_project_init_helper",
    )
    written_state = next_state
    if not dry_run:
        written_state = project_state.write_state_atomic(
            root,
            next_state,
            updated_by="control_plane_project_init_helper",
        )
    bindings = [str(service.get("service_binding") or "") for service in services]
    state_word = "declined" if decision_state == "declined" else "deferred"
    service_text = ", ".join(bindings)
    return {
        "ok": True,
        "status": f"service_{state_word}",
        "project_root": str(root),
        "client_type": client_type,
        "decision_state": decision_state,
        "selected_service_bindings": bindings,
        "state_revision": written_state["meta"]["revision"],
        "dry_run": dry_run,
        "assistant_visible_response": (
            f"Recorded {state_word} for {service_text} in this project's ContextForge state. "
            "It was not installed or imported as an active client tool. "
            "You can continue with any already available ContextForge capabilities or choose other services later."
        ),
        "non_actions": [
            "no active service import",
            _no_user_global_mutation_label(client_type),
            "no project-local client config write",
            "no ContextForge registry or catalog mutation",
            "no backend install or restart",
            "no secret or token material write",
        ],
    }


def _services_with_project_scoped_provisioning_results(
    services: Sequence[Mapping[str, Any]],
    provisioning_results: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    by_binding = {
        str(result.get("service_binding") or ""): result
        for result in provisioning_results
        if isinstance(result, Mapping) and result.get("service_binding")
    }
    enriched: list[dict[str, Any]] = []
    for service in services:
        service_copy = dict(service)
        result = by_binding.get(str(service_copy.get("service_binding") or ""))
        if result and str(result.get("status") or "") == "completed":
            service_copy["provision_status"] = "created"
            provisioning = dict(service_copy.get("provisioning") or {})
            provisioning["provision_status"] = "created"
            provisioning["status"] = "completed"
            provisioning["result"] = {
                key: result.get(key)
                for key in ("operation_type", "language", "instance_slug", "server_name", "manifest_path", "contextforge_server_id")
                if result.get(key) is not None
            }
            service_copy["provisioning"] = provisioning
            service_copy["contextforge_readback_status"] = "provisioned_pending_readback"
        enriched.append(service_copy)
    return enriched


def _apply_project_scoped_provisioning(
    root: Path,
    services: Sequence[Mapping[str, Any]],
    *,
    plan: Mapping[str, Any],
    skip_service_bindings: Iterable[str] = (),
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    client_type = str(plan.get("client_type") or "codex")
    skip = set(skip_service_bindings)
    for service in services:
        if str(service.get("service_binding") or "") in skip:
            continue
        if not _needs_serena_project_provisioning(service):
            continue
        language = _serena_language_from_plan(plan, service)
        results.append(_run_serena_project_provisioning(root, service, language=language, client_type=client_type))
    return results


def _needs_serena_project_provisioning(service: Mapping[str, Any]) -> bool:
    if not str(service.get("service_family") or "").lower().startswith("serena"):
        return False
    provisioning = service.get("provisioning") if isinstance(service.get("provisioning"), Mapping) else {}
    if provisioning.get("status") == "required":
        return True
    return str(service.get("contextforge_readback_status") or "") in {"not_provisioned", "missing", "stale"}


def _serena_language_from_plan(plan: Mapping[str, Any], service: Mapping[str, Any]) -> str:
    inputs = plan.get("required_inputs") if isinstance(plan.get("required_inputs"), Mapping) else {}
    language = _service_input_value(inputs, service, "language")
    if not language or str(language) == "defer":
        raise ProjectInitHelperError("approved Serena provisioning plan is missing a concrete language")
    return str(language)


def _run_serena_project_provisioning(
    root: Path,
    service: Mapping[str, Any],
    *,
    language: str,
    client_type: str,
) -> dict[str, Any]:
    import manage_serena_project_instance as serena_manager

    before_manifest = serena_manager.existing_manifest_for_project(root)
    output = io.StringIO()
    args = Namespace(
        project_root=str(root),
        require_workspace=True,
        replace_existing_serena_config=False,
        language=language,
        no_systemd=_serena_no_systemd_requested_or_required(),
        verify=False,
        app_server=False,
        write_codex_config=False,
    )
    with redirect_stdout(output):
        exit_code = serena_manager.create(args)
    if exit_code != 0:
        raise ProjectInitHelperError(f"Serena project provisioning failed with exit code {exit_code}")
    manifest = serena_manager.existing_manifest_for_project(root)
    if not manifest:
        raise ProjectInitHelperError("Serena project provisioning completed without writing an instance manifest")
    virtual = manifest.get("contextforge", {}).get("virtual_server", {}) if isinstance(manifest.get("contextforge"), Mapping) else {}
    return {
        "service_binding": str(service.get("service_binding") or "serena"),
        "status": "completed",
        "operation_type": "provision_project_scoped_serena",
        "language": language,
        "instance_slug": str(manifest.get("instance_slug") or manifest.get("slug") or ""),
        "server_name": str(manifest.get("server_name") or service.get("virtual_server") or ""),
        "manifest_path": str(manifest.get("_manifest_path") or ""),
        "contextforge_server_id": str(virtual.get("id") or ""),
        "pre_digest": stable_digest(before_manifest) if before_manifest else None,
        "post_digest": stable_digest(manifest),
        "stdout": _compact_json_stdout(output.getvalue()),
    }


def _compact_json_stdout(text: str) -> dict[str, Any] | str:
    stripped = text.strip()
    if not stripped:
        return {}
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return stripped[-4000:]
    if isinstance(parsed, dict):
        return {
            key: parsed.get(key)
            for key in (
                "project_root",
                "instance_slug",
                "server_name",
                "port",
                "selected_language",
                "language_source",
                "provisioning_mode",
            )
            if key in parsed
        }
    return stripped[-4000:]


def _candidate(service: Mapping[str, Any], *, client_type: str = "codex") -> dict[str, Any]:
    service_family = str(service.get("service_family") or service.get("canonical_service") or "")
    if not service_family:
        raise ProjectInitHelperError("service is missing service_family")
    activation_class = str(service.get("activation_class") or _activation_class(service))
    binding_id = str(service.get("service_binding") or f"{service_family}:canonical")
    display_name = str(service.get("display_name") or service_family)
    descriptor_digest = str(service.get("descriptor_digest") or stable_digest(dict(service)))
    return {
        **{key: value for key, value in dict(service).items() if key != "client"},
        "service_family": service_family,
        "display_name": display_name,
        "service_binding": binding_id,
        "codex_alias": normalize_codex_alias(str(service.get("codex_alias") or service_family)),
        "activation_class": activation_class,
        "menu_group": _menu_group(service, activation_class),
        "scope_label": _scope_label(service, activation_class),
        "user_visible_effect": _effect_label(activation_class, client_type=client_type),
        "descriptor_digest": descriptor_digest,
        "service_identity_id": _service_identity_id(
            binding=binding_id,
            descriptor_digest=descriptor_digest,
            backend_instance=service.get("backend_instance"),
            virtual_server=service.get("virtual_server"),
            contextforge_server_id=service.get("contextforge_server_id"),
        ),
    }


def _service_visible_in_activation_menu(
    service: Mapping[str, Any],
    *,
    live_contextforge_readback_supplied: bool,
) -> bool:
    if not live_contextforge_readback_supplied:
        return True
    status = str(service.get("contextforge_readback_status") or "")
    provisioning = service.get("provisioning") if isinstance(service.get("provisioning"), Mapping) else {}
    if status in {"missing", "stale"} and provisioning.get("status") != "required":
        return False
    return True


def _service_identity_id(
    *,
    binding: str,
    descriptor_digest: str,
    backend_instance: Any,
    virtual_server: Any,
    contextforge_server_id: Any,
) -> str:
    digest = stable_digest(
        {
            "binding": binding,
            "contextforge_server_id": contextforge_server_id,
            "descriptor_digest": descriptor_digest,
            "backend_instance": backend_instance,
            "virtual_server": virtual_server,
        }
    )
    return "contextforge-service-" + digest.removeprefix("sha256:")[:24]


def _config_conflict_response(
    *,
    root: Path,
    client_type: str,
    config_plan: Mapping[str, Any],
    services: Sequence[Mapping[str, Any]],
    skipped_services: Sequence[Mapping[str, Any]] | None = None,
    status: str = "config_conflict",
    inputs: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    recovery_plan = _build_project_init_recovery_plan(
        root=root,
        client_type=client_type,
        services=services,
        source_plan=None,
        config_plan=config_plan,
        inputs=inputs or {},
    )
    return {
        "status": status,
        "root_attestation": _root_attestation(root, client_type=client_type),
        "config_plan": {key: value for key, value in config_plan.items() if key != "next_text"},
        "blocked_services": _conflicting_services(services, config_plan),
        "skipped_services": [_service_skip_summary(service) for service in skipped_services or []],
        "recovery": "helper_mediated_recovery_available",
        "recovery_plan": recovery_plan,
        "next_turn": next_turn(
            question_id="resolve-config-conflict",
            prompt=f"A project-local {client_type} MCP config entry conflicts with the selected ContextForge service. How should I proceed?",
            choices=[
                {
                    "id": "approve_recovery_plan",
                    "label": "Approve recovery",
                    "effect": "Approve the exact recovery plan digest to replace only conflicting project-local MCP blocks.",
                },
                {"id": "skip_conflicting_service", "label": "Skip service", "effect": "Do not activate the conflicting service."},
                {"id": "keep_existing_block", "label": "Keep existing", "effect": "Leave the project config unchanged and mark activation blocked."},
            ],
            allowed_response_shape="choose approve_recovery_plan, skip_conflicting_service, or keep_existing_block",
        ),
    }


def _apply_time_config_recovery_required_response(
    *,
    root: Path,
    client_type: str,
    plan: Mapping[str, Any],
    services: Sequence[Mapping[str, Any]],
    config_plan: Mapping[str, Any],
    provisioning_results: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    recovery_plan = _build_project_init_recovery_plan(
        root=root,
        client_type=client_type,
        services=services,
        source_plan=plan,
        config_plan=config_plan,
        inputs=plan.get("required_inputs") if isinstance(plan.get("required_inputs"), Mapping) else {},
    )
    return {
        "status": "config_recovery_required",
        "project_root": str(root),
        "client_type": client_type,
        "root_attestation": _root_attestation(root, client_type=client_type),
        "resume_reason": "approved project-init apply reached a project-local config conflict before activation state was written",
        "source_plan": {
            "plan_id": plan.get("plan_id"),
            "plan_digest": plan.get("plan_digest"),
            "selected_service_bindings": [service.get("service_binding") for service in services],
        },
        "provisioning_results": list(provisioning_results),
        "config_plan": {key: value for key, value in config_plan.items() if key != "next_text"},
        "blocked_services": _conflicting_services(services, config_plan),
        "recovery_plan": recovery_plan,
        "next_turn": config_recovery_approval_turn(client_type=client_type),
        "non_actions": [
            "activation receipts were not consumed",
            "project-local activation state was not written",
            "project state was not written",
            _no_user_global_mutation_label(client_type),
            "no ContextForge catalog mutation",
        ],
    }


def _build_project_init_recovery_plan(
    *,
    root: Path,
    client_type: str,
    services: Sequence[Mapping[str, Any]],
    source_plan: Mapping[str, Any] | None,
    config_plan: Mapping[str, Any],
    inputs: Mapping[str, Any],
) -> dict[str, Any]:
    effective_inputs = dict(inputs or {})
    source_inputs = source_plan.get("required_inputs") if isinstance(source_plan, Mapping) and isinstance(source_plan.get("required_inputs"), Mapping) else {}
    effective_inputs = {**dict(source_inputs), **effective_inputs}
    if client_type == "codex":
        conflict_aliases = sorted(_conflicting_aliases(config_plan))
        config_recovery = binding.plan_project_init_codex_config_conflict_recovery(
            root,
            services,
            conflict_aliases=conflict_aliases,
        )
    elif client_type == "gemini":
        conflict_aliases = sorted(_conflicting_aliases(config_plan))
        config_recovery = binding.plan_project_init_gemini_config_conflict_recovery(
            root,
            services,
            conflict_aliases=conflict_aliases,
        )
    elif client_type == "opencode":
        conflict_aliases = sorted(_conflicting_aliases(config_plan))
        config_recovery = binding.plan_project_init_opencode_config_conflict_recovery(
            root,
            services,
            conflict_aliases=conflict_aliases,
        )
    else:
        config_recovery = {
            "surface": "project_state",
            "scope": "project_state",
            "decision": "noop",
            "write_allowed": True,
            "recovery_required": False,
            "blockers": [],
            "operations": [],
            "before_digest": None,
            "after_digest": None,
            "non_actions": [_no_user_global_mutation_label(client_type)],
            "redaction_status": "redacted",
        }
    service_recovery = _project_scoped_service_recovery_plan(root, services, inputs=effective_inputs)
    required_consent_classes: list[str] = []
    if config_recovery.get("recovery_required"):
        required_consent_classes.append("project_local_config_write")
    if any(item.get("recovery_required") for item in service_recovery):
        required_consent_classes.append("service_provision")
    required_consent_classes = list(dict.fromkeys(required_consent_classes))
    plan_seed = {
        "schema_uri": HELPER_RECOVERY_PLAN_SCHEMA_URI,
        "workflow": "project_init_recovery",
        "client_type": client_type,
        "project_root": str(root),
        "project_root_hash": project_state.project_root_hash(root),
        "selected_services": [dict(service) for service in services],
        "source_activation_plan": _source_plan_ref(source_plan),
        "required_inputs": effective_inputs,
        "required_consent_classes": required_consent_classes,
        "config_recovery_plan": {key: value for key, value in config_recovery.items() if key != "next_text"},
        "service_recovery_plan": service_recovery,
        "stale_plan_inputs": {
            "project_root": str(root),
            "project_root_hash": project_state.project_root_hash(root),
            "target_client_digests": {client_type: config_recovery.get("before_digest")},
            "post_recovery_target_client_digests": {client_type: config_recovery.get("after_digest")},
        },
        "plan_summary": {
            "project_root": str(root),
            "target_client": client_type,
            "operations": list(config_recovery.get("operations") or []),
            "service_operations": service_recovery,
            "resume": "resume_approved_project_init_apply" if source_plan else "restart_project_init_proposal",
        },
        "non_actions": [
            _no_user_global_mutation_label(client_type),
            "no ContextForge catalog promotion",
            "no secrets or token material written",
        ],
    }
    if config_recovery.get("next_text") is not None:
        plan_seed["config_recovery_plan"] = dict(plan_seed["config_recovery_plan"])
        plan_seed["config_recovery_plan"]["next_text"] = config_recovery.get("next_text")
    plan_id = "project-init-recovery-" + stable_digest(plan_seed).removeprefix("sha256:")[:16]
    plan = {"plan_id": plan_id, **plan_seed}
    plan["status"] = "recovery_plan_ready" if required_consent_classes else "recovery_not_required"
    plan["plan_digest"] = _plan_digest(plan)
    plan["approval_challenge"] = _approval_challenge(plan)
    _PENDING_CHALLENGES[plan["approval_challenge"]["challenge_id"]] = {
        "plan_id": plan["plan_id"],
        "plan_digest": plan["plan_digest"],
        "project_root": str(root),
        "expires_at": plan["approval_challenge"]["expires_at"],
        "nonce": plan["approval_challenge"]["nonce"],
    }
    plan["next_turn"] = config_recovery_approval_turn(client_type=client_type)
    return plan


def _recovery_source_activation_plan(inputs: Mapping[str, Any]) -> Mapping[str, Any] | None:
    for key in ("activation_plan", "project_init_plan", "source_activation_plan", "plan"):
        value = inputs.get(key)
        if isinstance(value, Mapping) and value.get("workflow") == "project_init":
            return value
    return None


def _source_plan_ref(plan: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(plan, Mapping):
        return None
    return {
        "plan_id": plan.get("plan_id"),
        "plan_digest": plan.get("plan_digest"),
        "workflow": plan.get("workflow"),
    }


def _project_scoped_service_recovery_plan(
    root: Path,
    services: Sequence[Mapping[str, Any]],
    *,
    inputs: Mapping[str, Any],
) -> list[dict[str, Any]]:
    reset_requested = bool(
        inputs.get("reset_project_scoped_services")
        or inputs.get("reset_serena_project_instance")
        or inputs.get("delete_stale_project_scoped_services")
    )
    operations: list[dict[str, Any]] = []
    for service in services:
        if not str(service.get("service_family") or "").lower().startswith("serena"):
            continue
        language = _service_input_value(inputs, service, "language")
        operations.append(
            {
                "service_binding": service.get("service_binding"),
                "operation": "remove_stale_project_scoped_serena_instance" if reset_requested else "noop_no_reset_requested",
                "recovery_required": bool(reset_requested),
                "delete_instance_dir": bool(inputs.get("delete_instance_dir", True)),
                "delete_contextforge_records": bool(inputs.get("delete_contextforge_records", True)),
                "reason": (
                    "explicit project-init recovery input requested project-scoped Serena reset"
                    if reset_requested
                    else "project-scoped Serena reset was not requested"
                ),
            }
        )
        needs_provisioning = _needs_serena_project_provisioning(service) or reset_requested
        operations.append(
            {
                "service_binding": service.get("service_binding"),
                "operation": "ensure_project_scoped_serena_instance" if needs_provisioning else "noop_project_scoped_serena_current",
                "recovery_required": bool(needs_provisioning),
                "language": language,
                "reason": (
                    "selected project-scoped Serena service requires idempotent provisioning"
                    if needs_provisioning
                    else "selected project-scoped Serena service is already provisioned"
                ),
            }
        )
    return operations


def _validate_recovery_plan_not_stale(root: Path, plan: Mapping[str, Any]) -> None:
    client_type = str(plan.get("client_type") or "codex")
    config_recovery = plan.get("config_recovery_plan") if isinstance(plan.get("config_recovery_plan"), Mapping) else {}
    if client_type != "codex" or not config_recovery:
        return
    config_path = root / ".codex" / "config.toml"
    text = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    current_digest = stable_digest(text)
    before_digest = str(config_recovery.get("before_digest") or "")
    after_digest = str(config_recovery.get("after_digest") or "")
    if current_digest not in {before_digest, after_digest}:
        raise ProjectInitHelperError("stale recovery plan: project-local client config changed since recovery planning")


def _apply_service_recovery(root: Path, plan: Mapping[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    services_by_binding = {
        str(service.get("service_binding") or ""): service
        for service in plan.get("selected_services") or []
        if isinstance(service, Mapping)
    }
    for operation in plan.get("service_recovery_plan") or []:
        if not isinstance(operation, Mapping) or not operation.get("recovery_required"):
            continue
        if operation.get("operation") == "remove_stale_project_scoped_serena_instance":
            results.append(_run_serena_project_removal(root, operation))
        elif operation.get("operation") == "ensure_project_scoped_serena_instance":
            binding_id = str(operation.get("service_binding") or "")
            service = services_by_binding.get(binding_id)
            if not isinstance(service, Mapping):
                raise ProjectInitHelperError(f"recovery service operation references unknown service binding: {binding_id}")
            language = str(operation.get("language") or "")
            if not language or language == "defer":
                raise ProjectInitHelperError(f"recovery service operation for {binding_id} is missing a concrete language")
            results.append(_run_serena_project_provisioning(root, service, language=language, client_type=str(plan.get("client_type") or "codex")))
    return results


def _run_serena_project_removal(root: Path, operation: Mapping[str, Any]) -> dict[str, Any]:
    import manage_serena_project_instance as serena_manager

    output = io.StringIO()
    args = Namespace(
        project_root=str(root),
        yes=True,
        delete_instance_dir=bool(operation.get("delete_instance_dir")),
        delete_contextforge_records=bool(operation.get("delete_contextforge_records")),
    )
    with redirect_stdout(output):
        exit_code = serena_manager.remove(args)
    if exit_code != 0:
        raise ProjectInitHelperError(f"Serena project removal failed with exit code {exit_code}")
    return {
        "service_binding": operation.get("service_binding"),
        "operation": operation.get("operation"),
        "status": "completed",
        "stdout": _compact_json_stdout(output.getvalue()),
    }


def _post_recovery_summary(root: Path, plan: Mapping[str, Any]) -> dict[str, Any]:
    client_type = str(plan.get("client_type") or "codex")
    config_path = root / ".codex" / "config.toml"
    current_digest = stable_digest(config_path.read_text(encoding="utf-8") if config_path.exists() else "") if client_type == "codex" else None
    return {
        "target_client_config_digest": current_digest,
        "source_activation_plan": plan.get("source_activation_plan"),
        "resume": "call cf_project_init_apply with the cached approved activation plan" if plan.get("source_activation_plan") else "request a fresh project-init proposal",
    }


def _post_recovery_next_turn(plan: Mapping[str, Any]) -> dict[str, Any]:
    if plan.get("source_activation_plan"):
        return next_turn(
            question_id="resume-approved-project-init-apply",
            prompt="Recovery is complete. Resume the approved project-init apply?",
            choices=[
                {"id": "resume_apply", "label": "Resume apply", "effect": "Call cf_project_init_apply using the cached approved activation plan and receipts."}
            ],
            allowed_response_shape="choose resume_apply",
        )
    return next_turn(
        question_id="restart-project-init-proposal",
        prompt="Recovery is complete. Start a fresh project-init proposal so the digest reflects the recovered config?",
        choices=[
            {"id": "restart_selection", "label": "Restart selection", "effect": "Call cf_project_init_propose again with the desired services."}
        ],
        allowed_response_shape="choose restart_selection",
    )


def _config_conflict_resolution(inputs: Mapping[str, Any]) -> str | None:
    value = inputs.get("resolve-config-conflict") or inputs.get("resolve_config_conflict")
    return str(value) if value else None


def _conflicting_aliases(config_plan: Mapping[str, Any]) -> set[str]:
    aliases: set[str] = set()
    for change in config_plan.get("changes") or []:
        if not isinstance(change, Mapping):
            continue
        if change.get("operation") == "blocked" or change.get("owned_block_class") == "unmanaged_same_name":
            alias = str(change.get("alias") or "")
            if alias:
                aliases.add(alias)
    return aliases


def _conflicting_services(services: Sequence[Mapping[str, Any]], config_plan: Mapping[str, Any]) -> list[dict[str, Any]]:
    aliases = _conflicting_aliases(config_plan)
    by_alias = {normalize_codex_alias(str(service.get("codex_alias") or service.get("service_family") or "")): service for service in services}
    summaries: list[dict[str, Any]] = []
    for alias in sorted(aliases):
        service = by_alias.get(alias, {})
        summaries.append(
            {
                "alias": alias,
                "service_binding": service.get("service_binding"),
                "virtual_server": service.get("virtual_server"),
                "reason": f"unmanaged [mcp_servers.{alias}] already exists",
            }
        )
    return summaries


def _skip_conflicting_services(
    services: Sequence[Mapping[str, Any]],
    config_plan: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    aliases = _conflicting_aliases(config_plan)
    kept: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for service in services:
        alias = normalize_codex_alias(str(service.get("codex_alias") or service.get("service_family") or ""))
        if alias in aliases:
            skipped.append(dict(service))
        else:
            kept.append(dict(service))
    return kept, [_service_skip_summary(service) for service in skipped]


def _service_skip_summary(service: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "service_binding": service.get("service_binding"),
        "codex_alias": normalize_codex_alias(str(service.get("codex_alias") or service.get("service_family") or "")),
        "virtual_server": service.get("virtual_server"),
        "reason": "project-local config contains an unmanaged same-name MCP block",
    }


def _plan_summary(
    *,
    root: Path,
    services: Sequence[Mapping[str, Any]],
    config_plan: Mapping[str, Any],
    skipped_services: Sequence[Mapping[str, Any]],
    client_type: str,
    state_snapshot: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    summary = {
        "project_root": str(root),
        "target_client": client_type,
        "project_local_writes": _planned_project_local_writes(root, client_type),
        "bindings": [
            {
                "service_binding": service.get("service_binding"),
                "service_identity_id": service.get("service_identity_id"),
                "contextforge_server_id": service.get("contextforge_server_id"),
                "codex_alias": normalize_codex_alias(str(service.get("codex_alias") or service.get("service_family") or "")),
                "pi_tool_prefix": _pi_tool_prefix(service),
                "virtual_server": service.get("virtual_server"),
                "gateway": service.get("gateway"),
                "activation_class": service.get("activation_class"),
                "scope_label": service.get("scope_label") or _scope_label(service, str(service.get("activation_class") or "")),
                "config_operation": _config_operation_for_service(service, config_plan),
            }
            for service in services
        ],
        "skipped_services": [_service_skip_summary(service) for service in skipped_services],
        "non_actions": [
            _no_user_global_mutation_label(client_type),
            "no ContextForge registry or catalog mutation",
            "no backend install or restart for shared canonical services",
            "no secrets or token material written",
        ],
    }
    if state_snapshot and state_snapshot.get("artifact_status") == "invalid":
        summary["project_state_recovery"] = {
            "artifact_status": "invalid",
            "digest": state_snapshot.get("digest"),
            "recovery": state_snapshot.get("recovery"),
            "message": state_snapshot.get("message"),
        }
        summary["non_actions"].append("invalid stale project-state artifact is not edited during planning")
    return summary


def _config_operation_for_service(service: Mapping[str, Any], config_plan: Mapping[str, Any]) -> str | None:
    alias = normalize_codex_alias(str(service.get("codex_alias") or service.get("service_family") or ""))
    pi_prefix = _pi_tool_prefix(service)
    for change in config_plan.get("changes") or []:
        if not isinstance(change, Mapping):
            continue
        if change.get("alias") == alias or change.get("pi_tool_prefix") == pi_prefix:
            return str(change.get("operation") or "")
    return None


def _client_activation_plan(
    root: Path,
    services: Sequence[Mapping[str, Any]],
    *,
    client_type: str,
    existing_state: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return binding.plan_project_init_target_client_activation(
        root,
        services,
        target_client=client_type,
        existing_state=existing_state,
    )


def _write_client_activation(root: Path, config_plan: Mapping[str, Any], *, client_type: str) -> None:
    if client_type == "codex":
        config_path = root / ".codex" / "config.toml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(str(config_plan["next_text"]), encoding="utf-8")
        return
    if client_type == "gemini":
        config_path = root / ".gemini" / "settings.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(str(config_plan["next_text"]), encoding="utf-8")
        return
    if client_type == "opencode":
        config_path = root / "opencode.json"
        config_path.write_text(str(config_plan["next_text"]), encoding="utf-8")
        return
    if client_type == "pi":
        return
    raise ProjectInitHelperError(f"unsupported client_type: {client_type}")


def _planned_project_local_writes(root: Path, client_type: str) -> list[str]:
    writes = []
    if client_type == "codex":
        writes.append(str(root / ".codex" / "config.toml"))
    if client_type == "gemini":
        writes.append(str(root / ".gemini" / "settings.json"))
    if client_type == "opencode":
        writes.append(str(root / "opencode.json"))
    writes.append(str(project_state.project_state_path(root)))
    return writes


def _pi_tool_prefix(service: Mapping[str, Any]) -> str:
    raw = str(service.get("pi_tool_prefix") or service.get("codex_alias") or service.get("service_family") or "service")
    prefix = normalize_codex_alias(raw).replace("_", "-")
    return prefix or "service"


def _no_user_global_mutation_label(client_type: str) -> str:
    if client_type == "pi":
        return "no user-global Pi config, extension, or trust mutation"
    if client_type == "gemini":
        return "no user-global Gemini config or trust mutation"
    if client_type == "opencode":
        return "no user-global OpenCode config, plugin, or trust mutation"
    if client_type == "codex":
        return "no user-global Codex config or trust mutation"
    return "no user-global client config or trust mutation"


def _repair_resume_reason(client_type: str) -> str:
    if client_type == "pi":
        return "project init selected services, but project-state Pi shim activation metadata is missing approved bindings"
    if client_type == "gemini":
        return "project init selected services and recorded state, but project-local Gemini settings are missing approved bindings"
    if client_type == "opencode":
        return "project init selected services and recorded state, but project-local OpenCode config is missing approved bindings"
    return "project init selected services and recorded state, but project-local Codex config is missing approved bindings"


def _repair_project_init_block_label(client_type: str) -> str:
    if client_type == "pi":
        return "do not continue project init until project-state Pi shim metadata matches the approved job"
    if client_type == "gemini":
        return "do not continue project init until project-local Gemini settings match the approved job"
    if client_type == "opencode":
        return "do not continue project init until project-local OpenCode config matches the approved job"
    return "do not continue project init until project-local config matches the approved job"


def _validation_not_recorded_label(client_type: str) -> str:
    if client_type == "pi":
        return "install status was not advanced because Pi shim activation metadata is out of sync"
    return "install status was not advanced because project-local config is out of sync"


def _resolve_selected_services(
    project_root: Path,
    selected_services: Sequence[Mapping[str, Any] | str],
    *,
    client_type: str = "codex",
    contextforge_servers: Iterable[dict[str, Any]] | None = None,
    contextforge_service_offerings: Iterable[dict[str, Any]] | None = None,
    server_instances_root: str | Path | None = None,
) -> list[dict[str, Any]]:
    if contextforge_service_offerings is not None:
        services = [service for service in contextforge_service_offerings if isinstance(service, Mapping)]
    else:
        services = discover_contextforge_hosted_services(
            project_root=project_root,
            contextforge_servers=contextforge_servers,
            **({"server_instances_root": server_instances_root} if server_instances_root is not None else {}),
        )
    available = [_candidate(service, client_type=client_type) for service in services]
    by_key: dict[str, dict[str, Any]] = {}
    for service in available:
        keys = {
            str(service.get("service_binding") or ""),
            str(service.get("service_family") or ""),
            str(service.get("canonical_service") or ""),
            str(service.get("codex_alias") or ""),
            normalize_codex_alias(str(service.get("service_family") or "")),
        }
        binding_id = str(service.get("service_binding") or "")
        if ":" in binding_id:
            keys.add(binding_id.split(":", 1)[0])
        for key in keys:
            if key:
                by_key.setdefault(key, service)

    resolved: list[dict[str, Any]] = []
    missing: list[str] = []
    for item in selected_services:
        if isinstance(item, str):
            ref = item.strip()
            service = by_key.get(ref) or by_key.get(normalize_codex_alias(ref))
            if service is None:
                missing.append(ref)
            else:
                resolved.append(dict(service))
            continue
        if not isinstance(item, Mapping):
            raise ProjectInitHelperError("selected_services entries must be service descriptors, refs, or id objects")
        if item.get("service_family") or item.get("canonical_service"):
            resolved.append(_candidate(item, client_type=client_type))
            continue
        ref = str(item.get("service_binding") or item.get("id") or item.get("name") or item.get("slug") or "").strip()
        service = by_key.get(ref) or by_key.get(normalize_codex_alias(ref))
        if service is None:
            missing.append(ref or "<missing service id>")
        else:
            resolved.append(dict(service))
    if missing:
        raise ProjectInitHelperError(f"unknown selected service ids: {', '.join(missing)}")
    return resolved


def _activation_class(service: Mapping[str, Any]) -> str:
    if str(service.get("service_family") or "").lower().startswith("serena"):
        return "client_local_project_scoped"
    instantiation_class = str(service.get("instantiation_class") or "shared_canonical")
    if instantiation_class in {
        "shared_canonical",
        "static_repo_local",
        "caller_scoped",
        "session_scoped",
        "credential_scoped",
        "resource_scoped",
    }:
        return "shared_canonical"
    if instantiation_class in {"instance_per_project", "project_scoped_shared_backend"}:
        return "client_local_project_scoped"
    return "server_provisioned"


def _effect_label(activation_class: str, *, client_type: str = "codex") -> str:
    if activation_class == "shared_canonical":
        return "Enable this existing ContextForge service for this project."
    if activation_class == "client_local_project_scoped":
        return "Prepare this project-scoped ContextForge service and enable it for this project."
    return "Prepare this ContextForge service and enable it for this project."


def _scope_label(service: Mapping[str, Any], activation_class: str) -> str:
    instantiation_class = str(service.get("instantiation_class") or "")
    if activation_class == "client_local_project_scoped":
        return "project-scoped provisioning"
    if instantiation_class == "shared_canonical":
        return "shared canonical binding"
    if instantiation_class == "static_repo_local":
        return "repo-local hosted binding"
    if instantiation_class == "session_scoped":
        return "session-scoped hosted binding"
    if instantiation_class == "credential_scoped":
        return "credential-scoped hosted binding"
    if instantiation_class == "caller_scoped":
        return "caller-scoped hosted binding"
    if instantiation_class == "resource_scoped":
        return "resource-scoped hosted binding"
    return activation_class.replace("_", " ")


def _menu_group(service: Mapping[str, Any], activation_class: str) -> str:
    instantiation_class = str(service.get("instantiation_class") or "")
    if activation_class == "client_local_project_scoped":
        return "project_scoped_provisioning"
    if instantiation_class == "shared_canonical":
        return "shared_canonical"
    if instantiation_class in {"static_repo_local", "caller_scoped", "session_scoped", "credential_scoped", "resource_scoped"}:
        return "hosted_scoped"
    return "server_provisioned"


def _first_missing_input(services: Sequence[Mapping[str, Any]], inputs: Mapping[str, Any]) -> dict[str, Any] | None:
    for service in services:
        if service["activation_class"] == "client_local_project_scoped" and str(service["service_family"]).startswith("serena"):
            if not _service_input_value(inputs, service, "language"):
                return {
                    "service_binding": service["service_binding"],
                    "input": "language",
                    "prompt": "Which language should the project-local Serena instance use?",
                    "choices": [
                        {"id": "python", "label": "Python", "effect": "Configure Serena for Python language support."},
                        {"id": "typescript", "label": "TypeScript", "effect": "Configure Serena for TypeScript language support."},
                        {"id": "defer", "label": "Defer", "effect": "Do not provision Serena in this project-init pass."},
                    ],
                }
    return None


def _service_input_value(inputs: Mapping[str, Any], service: Mapping[str, Any], input_name: str) -> Any:
    binding = str(service.get("service_binding") or "")
    candidates = [
        binding,
        str(service.get("service_family") or ""),
        str(service.get("canonical_service") or ""),
        str(service.get("codex_alias") or ""),
        normalize_codex_alias(str(service.get("service_family") or "")),
    ]
    if binding and ":" in binding:
        candidates.append(binding.split(":", 1)[0])

    input_keys = [
        key
        for candidate in candidates
        if candidate
        for key in (f"{candidate}.{input_name}", f"{candidate}-{input_name}", f"{candidate}_{input_name}")
    ]
    for key in input_keys:
        if inputs.get(key):
            return inputs.get(key)
    for key in candidates:
        nested = inputs.get(key)
        if isinstance(nested, Mapping) and nested.get(input_name):
            return nested.get(input_name)
        if nested and input_name == "language":
            return nested
    return inputs.get(input_name)


def _normalized_required_inputs(inputs: Mapping[str, Any], services: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    normalized = dict(inputs or {})
    for service in services:
        if service["activation_class"] != "client_local_project_scoped":
            continue
        if not str(service["service_family"]).startswith("serena"):
            continue
        language = _service_input_value(inputs, service, "language")
        if language:
            normalized[str(service["service_binding"])] = {"language": str(language)}
    return normalized


def _required_consent_classes(services: Sequence[Mapping[str, Any]], *, client_type: str) -> list[str]:
    classes = list(PI_PROJECT_LOCAL_CONSENT_CLASSES if client_type == "pi" else PROJECT_LOCAL_CONSENT_CLASSES)
    if any(service["activation_class"] != "shared_canonical" for service in services):
        classes.append("service_provision")
    return classes


def _stale_plan_inputs(
    *,
    root: Path,
    base_state: Mapping[str, Any],
    state_exists: bool,
    state_snapshot: Mapping[str, Any] | None = None,
    client_type: str,
    config_plan: Mapping[str, Any],
    catalog_revision_or_etag: str | None,
    services: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    snapshot = dict(state_snapshot or {})
    return {
        "project_root": str(root),
        "project_root_hash": project_state.project_root_hash(root),
        "base_project_state": {
            "revision": project_state.state_revision(dict(base_state)) if state_exists else None,
            "status": base_state.get("status") if state_exists else None,
            "digest": authorization.stable_digest(base_state) if state_exists else None,
            "artifact_status": snapshot.get("artifact_status", "valid" if state_exists else "absent"),
            "artifact_digest": snapshot.get("digest"),
            "recovery": snapshot.get("recovery"),
        },
        "target_client_digests": {client_type: config_plan.get("before_digest")},
        "trust_state_digest": None,
        "catalog": {
            "revision_or_etag": catalog_revision_or_etag,
            "descriptor_digests": {service["service_binding"]: service["descriptor_digest"] for service in services},
        },
    }


def _approval_challenge(plan: Mapping[str, Any]) -> dict[str, Any]:
    expires = datetime.now(UTC).replace(microsecond=0) + timedelta(minutes=15)
    nonce = hashlib.sha256(f"{plan['plan_id']}:{plan['plan_digest']}:{expires.isoformat()}".encode("utf-8")).hexdigest()[:24]
    return {
        "challenge_id": "approval-" + hashlib.sha256(f"{plan['plan_digest']}:{nonce}".encode("utf-8")).hexdigest()[:16],
        "plan_id": plan["plan_id"],
        "plan_digest": plan["plan_digest"],
        "nonce": nonce,
        "expires_at": expires.isoformat().replace("+00:00", "Z"),
        "consent_classes": list(plan.get("required_consent_classes") or []),
    }


def _validate_receipts_for_plan(
    plan: Mapping[str, Any],
    receipts: Sequence[Mapping[str, Any]],
    *,
    project_root: Path,
    consume: bool,
) -> None:
    auth_plan = _authorization_plan(plan)
    by_class = {str(receipt.get("consent_class")): receipt for receipt in receipts}
    missing = [klass for klass in plan.get("required_consent_classes") or [] if klass not in by_class]
    if missing:
        raise ProjectInitHelperError(f"missing consent receipts: {', '.join(missing)}")
    if not list(plan.get("required_consent_classes") or []) and not list(receipts or []):
        return
    approved_ids = _APPROVED_RECEIPT_IDS_BY_PLAN.get(str(plan.get("plan_id")), set())
    observed_ids = {str(receipt.get("receipt_id") or "") for receipt in receipts}
    if not observed_ids or not observed_ids.issubset(approved_ids):
        raise ProjectInitHelperError("consent receipts were not issued by this helper approval session")
    replayed = sorted(observed_ids & _CONSUMED_RECEIPT_IDS)
    if replayed:
        raise ProjectInitHelperError(f"consent receipts already consumed: {', '.join(replayed)}")
    for klass in plan.get("required_consent_classes") or []:
        decision = authorization.validate_consent_receipt(
            by_class[str(klass)],
            plan=auth_plan,
            operation_class=str(klass),
            actor=str(by_class[str(klass)].get("actor")),
            source_client=str(by_class[str(klass)].get("source_client")),
            project_root=project_root,
            target_clients=[str(plan.get("client_type") or "codex")],
            replay_intent="initial_apply",
        )
        if decision["decision"] != "allow":
            raise ProjectInitHelperError(f"receipt rejected for {klass}: {decision['reasons']}")
    if consume:
        _CONSUMED_RECEIPT_IDS.update(observed_ids)


def _validate_plan_not_stale(
    plan: Mapping[str, Any],
    *,
    services: Sequence[Mapping[str, Any]],
    project_root: Path,
    contextforge_servers: Iterable[dict[str, Any]] | None = None,
    server_instances_root: str | Path | None = None,
    catalog_revision_or_etag: str | None = None,
    recovery_plan: Mapping[str, Any] | None = None,
) -> None:
    client_type = str(plan.get("client_type") or "codex")
    current_state, current_snapshot = _project_state_snapshot_for_init(project_root)
    stale_inputs = plan.get("stale_plan_inputs") if isinstance(plan.get("stale_plan_inputs"), Mapping) else {}
    planned_base = stale_inputs.get("base_project_state") if isinstance(stale_inputs.get("base_project_state"), Mapping) else {}
    planned_artifact_status = planned_base.get("artifact_status")
    if current_snapshot.get("artifact_status") == "invalid" or planned_artifact_status == "invalid":
        if (
            current_snapshot.get("artifact_status") != "invalid"
            or planned_artifact_status != "invalid"
            or current_snapshot.get("digest") != planned_base.get("artifact_digest")
        ):
            raise ProjectInitHelperError("stale plan: invalid project-state artifact changed")
    existing_for_config = current_state if current_state is not None else project_state.default_state(project_root)
    current_config = _client_activation_plan(project_root, services, client_type=client_type, existing_state=existing_for_config)
    should_refresh_descriptors = (
        contextforge_servers is not None
        or server_instances_root is not None
        or all(service.get("manifest_path") for service in services)
    )
    current_services = (
        discover_contextforge_hosted_services(
            project_root=project_root,
            contextforge_servers=contextforge_servers,
            **({"server_instances_root": server_instances_root} if server_instances_root is not None else {}),
        )
        if should_refresh_descriptors
        else list(services)
    )
    current_by_binding = {str(service.get("service_binding")): service for service in current_services}
    descriptor_digests: dict[str, str] = {}
    missing_bindings: list[str] = []
    for service in services:
        binding_id = str(service.get("service_binding") or "")
        if not binding_id:
            continue
        current_service = current_by_binding.get(binding_id)
        if not current_service:
            missing_bindings.append(binding_id)
            continue
        descriptor_digests[binding_id] = str(current_service.get("descriptor_digest") or "")
    if missing_bindings:
        raise ProjectInitHelperError(f"stale plan: selected service descriptors missing from current catalog: {', '.join(missing_bindings)}")
    stale = authorization.validate_stale_plan(
        _authorization_plan(plan),
        current_state=current_state,
        project_root=project_root,
        current_target_client_digests={client_type: current_config.get("before_digest")},
        current_trust_digest=None,
        current_catalog_revision_or_etag=(
            catalog_revision_or_etag
            if catalog_revision_or_etag is not None
            else ((plan.get("stale_plan_inputs") or {}).get("catalog") or {}).get("revision_or_etag")
        ),
        current_descriptor_digests=descriptor_digests,
    )
    if stale["decision"] != "allow":
        if _stale_plan_allowed_by_recovery_continuation(
            plan,
            recovery_plan,
            client_type=client_type,
            current_target_client_digest=current_config.get("before_digest"),
            stale_reasons=stale["reasons"],
        ):
            return
        raise ProjectInitHelperError(f"stale plan: {stale['reasons']}")


def _stale_plan_allowed_by_recovery_continuation(
    plan: Mapping[str, Any],
    recovery_plan: Mapping[str, Any] | None,
    *,
    client_type: str,
    current_target_client_digest: Any,
    stale_reasons: Sequence[Any],
) -> bool:
    """Allow the exact post-recovery digest for an exact source activation plan."""

    if list(stale_reasons) != [f"target client digest changed: {client_type}"]:
        return False
    if not _recovery_plan_matches_source_activation(plan, recovery_plan, client_type=client_type):
        return False
    recovery_inputs = recovery_plan.get("stale_plan_inputs") if isinstance(recovery_plan.get("stale_plan_inputs"), Mapping) else {}
    post_recovery = recovery_inputs.get("post_recovery_target_client_digests") if isinstance(recovery_inputs.get("post_recovery_target_client_digests"), Mapping) else {}
    expected_digest = post_recovery.get(client_type)
    return bool(expected_digest) and current_target_client_digest == expected_digest


def _recovery_plan_matches_source_activation(
    plan: Mapping[str, Any],
    recovery_plan: Mapping[str, Any] | None,
    *,
    client_type: str,
) -> bool:
    if not isinstance(recovery_plan, Mapping):
        return False
    if recovery_plan.get("schema_uri") != HELPER_RECOVERY_PLAN_SCHEMA_URI or recovery_plan.get("workflow") != "project_init_recovery":
        return False
    if _validate_plan_digest(recovery_plan):
        return False
    if str(recovery_plan.get("client_type") or "codex") != client_type:
        return False
    if str(recovery_plan.get("project_root") or "") != str(plan.get("project_root") or ""):
        return False
    source = recovery_plan.get("source_activation_plan") if isinstance(recovery_plan.get("source_activation_plan"), Mapping) else {}
    if source.get("workflow") != plan.get("workflow"):
        return False
    return source.get("plan_id") == plan.get("plan_id") and source.get("plan_digest") == plan.get("plan_digest")


def _recovery_ensured_service_bindings(
    plan: Mapping[str, Any],
    recovery_plan: Mapping[str, Any] | None,
    *,
    client_type: str,
) -> set[str]:
    if not _recovery_plan_matches_source_activation(plan, recovery_plan, client_type=client_type):
        return set()
    return {
        str(operation.get("service_binding"))
        for operation in recovery_plan.get("service_recovery_plan") or []
        if isinstance(operation, Mapping)
        and operation.get("recovery_required") is True
        and operation.get("operation") == "ensure_project_scoped_serena_instance"
        and operation.get("service_binding")
    }


def _activation_job_from_plan(
    plan: Mapping[str, Any],
    receipts: Sequence[Mapping[str, Any]],
    *,
    provisioning_results: Sequence[Mapping[str, Any]] = (),
    config_plan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    refs = [_receipt_ref(receipt)["ref"] for receipt in receipts]
    client_type = str(plan.get("client_type") or "codex")
    effective_config_plan = config_plan or (plan.get("config_plan") if isinstance(plan.get("config_plan"), Mapping) else {})
    provision_steps = [
        {
            "operation_id": "provision-" + normalize_codex_alias(str(result.get("service_binding") or "serena")),
            "operation_type": str(result.get("operation_type") or "provision_project_scoped_service"),
            "status": str(result.get("status") or "completed"),
            "idempotency_key": "service-provision-" + str(plan.get("plan_id")) + "-" + normalize_codex_alias(str(result.get("service_binding") or "serena")),
            "pre_digest": result.get("pre_digest"),
            "post_digest": result.get("post_digest"),
            "recovery_state": None,
        }
        for result in provisioning_results
    ]
    return {
        "job_id": "job-" + str(plan.get("plan_id")),
        "plan_id": str(plan.get("plan_id")),
        "plan_digest": str(plan.get("plan_digest")),
        "status": "installed",
        "client_type": client_type,
        "selected_service_ids": [str(service.get("service_identity_id")) for service in plan.get("selected_services") or []],
        "selected_service_bindings": [str(service.get("service_binding")) for service in plan.get("selected_services") or []],
        "step_statuses": [
            *provision_steps,
            {
                "operation_id": _client_activation_operation_id(client_type),
                "operation_type": _client_activation_operation_type(client_type),
                "status": "completed",
                "idempotency_key": f"{client_type}-activation-" + str(plan.get("plan_id")),
                "pre_digest": effective_config_plan.get("before_digest"),
                "post_digest": effective_config_plan.get("after_digest"),
                "recovery_state": None,
            },
            {
                "operation_id": "write-project-state",
                "operation_type": "write_project_state",
                "status": "completed",
                "idempotency_key": "project-state-" + str(plan.get("plan_id")),
                "pre_digest": None,
                "post_digest": None,
                "recovery_state": None,
            },
        ],
        "stale_plan_inputs": dict(plan.get("stale_plan_inputs") or {}),
        "consent_receipt_refs": refs,
        "local_client_config_digest": effective_config_plan.get("after_digest"),
        "validation_records": {},
        "recovery_state": "none",
        "non_actions": list(plan.get("non_actions") or []),
    }


def _client_activation_operation_id(client_type: str) -> str:
    if client_type == "pi":
        return "record-pi-shim-activation-metadata"
    if client_type == "opencode":
        return "write-opencode-project-config"
    return "write-managed-client-config"


def _client_activation_operation_type(client_type: str) -> str:
    if client_type == "pi":
        return "record_pi_shim_activation_metadata"
    if client_type == "opencode":
        return "write_opencode_project_config"
    return "write_managed_client_config"


def _repair_activation_operation_id(client_type: str) -> str:
    if client_type == "pi":
        return "repair-pi-shim-activation-metadata"
    if client_type == "opencode":
        return "repair-opencode-project-config"
    return "repair-managed-client-config"


def _repair_activation_operation_type(client_type: str) -> str:
    if client_type == "pi":
        return "repair_pi_shim_activation_metadata"
    if client_type == "opencode":
        return "repair_opencode_project_config"
    return "repair_managed_client_config"


def _receipt_service_scope(plan: Mapping[str, Any], consent_class: str) -> str | None:
    services = list(plan.get("selected_services") or [])
    if consent_class == "service_provision" and len(services) == 1:
        return str(services[0].get("service_binding"))
    return None


def _authorization_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    clean = json.loads(json.dumps(plan, sort_keys=True, default=str))
    clean.pop("plan_digest", None)
    clean.pop("approval_challenge", None)
    clean.pop("next_turn", None)
    return clean


def _plan_digest(plan: Mapping[str, Any]) -> str:
    return authorization.plan_digest(_authorization_plan(plan))


def _validate_plan_digest(plan: Mapping[str, Any]) -> list[str]:
    expected = plan.get("plan_digest")
    actual = _plan_digest(plan)
    if expected != actual:
        return ["plan digest does not match current plan contents"]
    return []


def _receipt_ref(receipt: Mapping[str, Any]) -> dict[str, Any]:
    receipt_id = str(receipt.get("receipt_id") or "receipt")
    return {
        "ref": f"run/consent-receipts/{receipt_id}.json",
        "content_digest": authorization.stable_digest(receipt),
        "x_consent_class": receipt.get("consent_class"),
    }


def _root_attestation(root: Path, *, client_type: str) -> dict[str, Any]:
    return {
        "canonical_root": str(root),
        "project_root_hash": project_state.project_root_hash(root),
        "client_type": client_type,
        "helper_protocol_version": HELPER_PROTOCOL_VERSION,
        "attested_at": now_timestamp(),
    }
