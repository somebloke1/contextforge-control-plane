#!/usr/bin/env python3
"""Read-only ContextForge project-init readiness reconciliation."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any, Mapping, Sequence

import control_plane_project_init_helper as helper
import control_plane_project_state as project_state
import project_init_common as common


REPORT_SCHEMA_URI = "contextforge://control-plane/project-init-readiness-report/v1"
HELPER_PROCESS_SCRIPT_NAMES = (
    "contextforge_helper_mcp.py",
    "control_plane_project_init_helper.py",
    "contextforge_mcp_wrapper.py",
)
LEGACY_ROOTS = (
    Path("/home/dgk/workspace/contextforge-slices/repo-local-skills-and-governance"),
    Path("/home/dgk/workspace/context-portal"),
)
COMPATIBILITY_IDENTIFIER_NEEDLES = (
    "contextforge://context-portal/",
    "serena-context-portal",
)
SERENA_APPROVAL_BOUNDARY = (
    "Serena provisioning or compatibility retention must be handled in a "
    "GitHub-tracked Serena/project-init slice with explicit approval before "
    "any live registry, service, systemd, or global client state changes."
)
PENDING_ACTIVATION_JOB_STATUSES = frozenset(
    {
        "applied_validation_choice_pending",
        "validation_choice_pending",
        "validation_pending",
    }
)
NON_BLOCKING_CLIENT_STATUSES = frozenset({"verified", "presumed_working", "disabled"})


def _canonical(path: str | Path) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _json_summary(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.exists():
        return None, None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"{exc.__class__.__name__}: {exc}"
    if not isinstance(data, dict):
        return None, f"project state must be a JSON object: {path}"
    return data, None


def _read_text(path: Path) -> tuple[str, str | None]:
    try:
        return path.read_text(encoding="utf-8"), None
    except (OSError, UnicodeDecodeError) as exc:
        return "", f"{exc.__class__.__name__}: {exc}"


def _reference_counts(text: str, needles: Sequence[str | Path]) -> dict[str, int]:
    return {str(needle): text.count(str(needle)) for needle in needles}


def _text_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if not path.is_dir():
        return []
    return sorted(
        candidate
        for candidate in path.rglob("*")
        if candidate.is_file() and "__pycache__" not in candidate.parts and ".git" not in candidate.parts
    )


def _tree_reference_counts(path: Path, needles: Sequence[str | Path]) -> dict[str, int]:
    counts = {str(needle): 0 for needle in needles}
    for file_path in _text_files(path):
        text, error = _read_text(file_path)
        if error:
            continue
        for needle, count in _reference_counts(text, needles).items():
            counts[needle] += count
    return counts


def _summarize_python_environment(root: Path) -> dict[str, Any]:
    python_path = root / ".venv" / "bin" / "python"
    return {
        "python_path": str(python_path),
        "exists": python_path.exists(),
        "is_executable": python_path.exists() and os.access(python_path, os.X_OK),
    }


def _mcp_server_summary(name: str, config: Mapping[str, Any], *, root: Path) -> dict[str, Any]:
    command = config.get("command")
    args = config.get("args") if isinstance(config.get("args"), list) else []
    cwd = config.get("cwd")
    text = " ".join(
        [
            str(command or ""),
            " ".join(str(arg) for arg in args),
            str(cwd or ""),
        ]
    )
    legacy_counts = _reference_counts(text, LEGACY_ROOTS)
    command_path = Path(str(command)).expanduser() if isinstance(command, str) else None
    cwd_path = Path(str(cwd)).expanduser() if isinstance(cwd, str) else None
    return {
        "name": name,
        "command": command,
        "args": [str(arg) for arg in args],
        "cwd": cwd,
        "command_exists": command_path.exists() if command_path and command_path.is_absolute() else None,
        "cwd_exists": cwd_path.exists() if cwd_path and cwd_path.is_absolute() else None,
        "current_root_reference_count": text.count(str(root)),
        "legacy_root_reference_counts": legacy_counts,
        "legacy_bound": any(count > 0 for count in legacy_counts.values()),
    }


def _summarize_codex_config(root: Path) -> dict[str, Any]:
    path = root / ".codex" / "config.toml"
    text, read_error = _read_text(path) if path.exists() else ("", None)
    parsed: dict[str, Any] = {}
    parse_error = None
    if text:
        try:
            parsed = tomllib.loads(text)
        except tomllib.TOMLDecodeError as exc:
            parse_error = f"{exc.__class__.__name__}: {exc}"
    mcp_servers = parsed.get("mcp_servers") if isinstance(parsed.get("mcp_servers"), Mapping) else {}
    server_summaries = [
        _mcp_server_summary(str(name), server, root=root)
        for name, server in sorted(mcp_servers.items())
        if isinstance(server, Mapping)
    ]
    return {
        "path": str(path),
        "exists": path.exists(),
        "read_error": read_error,
        "parse_error": parse_error,
        "mcp_server_count": len(server_summaries),
        "current_root_reference_count": text.count(str(root)),
        "legacy_root_reference_counts": _reference_counts(text, LEGACY_ROOTS),
        "mcp_servers": server_summaries,
    }


def _summarize_serena_identity(root: Path) -> dict[str, Any]:
    identity = common.project_identity(root)
    expected_instance = root / "server-instances" / identity.instance_slug
    legacy_instance = root / "server-instances" / "serena-context-portal"
    expected_manifest_exists = (expected_instance / "instance.json").exists()
    legacy_manifest_exists = (legacy_instance / "instance.json").exists()
    if expected_manifest_exists:
        readiness_status = "canonical_instance_present"
        classification = "canonical_cf_controlplane_serena_ready_for_validation"
    elif legacy_manifest_exists:
        readiness_status = "canonical_instance_missing_compatibility_present"
        classification = "compatibility_evidence_not_provisioning_completion"
    else:
        readiness_status = "canonical_instance_missing"
        classification = "serena_hard_requirement_unmet"
    return {
        "expected": {
            "service_binding": f"serena:{identity.hash}",
            "instance_slug": identity.instance_slug,
            "server_name": identity.server_name,
            "backend_instance": str(expected_instance.relative_to(root)),
            "instance_exists": expected_instance.exists(),
            "manifest_exists": expected_manifest_exists,
        },
        "legacy": {
            "backend_instance": str(legacy_instance.relative_to(root)),
            "instance_exists": legacy_instance.exists(),
            "manifest_exists": legacy_manifest_exists,
            "legacy_root_reference_counts": _tree_reference_counts(legacy_instance, LEGACY_ROOTS),
        },
        "readiness_decision": {
            "status": readiness_status,
            "classification": classification,
            "hard_requirement": True,
            "approval_boundary": SERENA_APPROVAL_BOUNDARY,
            "retirement_condition": (
                f"Generate and validate {identity.instance_slug} for "
                f"{root}, or record an explicit validated compatibility decision."
            ),
        },
    }


def _compatibility_identifier_paths(root: Path) -> tuple[Path, ...]:
    return (
        root / "scripts" / "project_init_common.py",
        root / "scripts" / "register_serena_context_portal_service.py",
        root / "server-instances" / "serena-context-portal",
    )


def _summarize_compatibility_identifiers(root: Path) -> dict[str, Any]:
    paths = (
        *_compatibility_identifier_paths(root),
    )
    files: list[Path] = []
    for path in paths:
        files.extend(_text_files(path))
    counts = {needle: 0 for needle in COMPATIBILITY_IDENTIFIER_NEEDLES}
    references: list[dict[str, Any]] = []
    for file_path in files:
        text, error = _read_text(file_path)
        if error:
            continue
        for needle, count in _reference_counts(text, COMPATIBILITY_IDENTIFIER_NEEDLES).items():
            counts[needle] += count
            if count:
                references.append(
                    {
                        "path": str(file_path.relative_to(root)),
                        "identifier": needle,
                        "count": count,
                        "classification": "compatibility_pending_retirement",
                        "owner_issue": "#37",
                        "retirement_condition": (
                            "Retain only while compatibility naming is required, "
                            "or retire in a focused GitHub-tracked slice."
                        ),
                    }
                )
    return {
        "paths": [str(path) for path in paths],
        "reference_counts": counts,
        "references": sorted(references, key=lambda item: (str(item["path"]), str(item["identifier"]))),
        "policy": {
            "classification_required": True,
            "broad_rename_allowed": False,
            "owner_issue": "#37",
            "approval_boundary": SERENA_APPROVAL_BOUNDARY,
        },
    }


def inspect_activation_artifacts(root: str | Path) -> dict[str, Any]:
    canonical = _canonical(root)
    return {
        "python_environment": _summarize_python_environment(canonical),
        "codex_config": _summarize_codex_config(canonical),
        "serena_project_instance": _summarize_serena_identity(canonical),
        "compatibility_identifiers": _summarize_compatibility_identifiers(canonical),
    }


def _status_counts(values: Sequence[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _activation_job_summary(job: Mapping[str, Any]) -> dict[str, Any]:
    records = job.get("validation_records") if isinstance(job.get("validation_records"), Mapping) else {}
    record_statuses = [
        str(record.get("status") or "unknown")
        for record in records.values()
        if isinstance(record, Mapping)
    ]
    return {
        "job_id": job.get("job_id"),
        "client_type": job.get("client_type"),
        "plan_id": job.get("plan_id"),
        "status": job.get("status"),
        "recovery_state": job.get("recovery_state"),
        "local_client_config_digest": job.get("local_client_config_digest"),
        "selected_service_ids": [str(value) for value in job.get("selected_service_ids") or []],
        "selected_service_bindings": [str(value) for value in job.get("selected_service_bindings") or []],
        "validation_status_counts": _status_counts(record_statuses),
        "x_reconciled_from_verified_job_id": job.get("x_reconciled_from_verified_job_id"),
        "x_operator_direction": job.get("x_operator_direction"),
    }


def _client_state_summary(state: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "client_type": state.get("client_type"),
        "status": state.get("status"),
        "current_job_id": state.get("current_job_id"),
        "activation_surface": state.get("activation_surface"),
        "validation_status": state.get("validation_status"),
        "reload_status": state.get("reload_status"),
        "selected_service_bindings": [str(value) for value in state.get("selected_service_bindings") or []],
        "selected_service_ids": [str(value) for value in state.get("selected_service_ids") or []],
        "local_client_config_digest": state.get("local_client_config_digest"),
        "x_operator_direction": state.get("x_operator_direction"),
    }


def _service_signature(record: Mapping[str, Any]) -> tuple[str, ...]:
    bindings = [str(value) for value in record.get("selected_service_bindings") or [] if value]
    if bindings:
        return tuple(sorted(bindings))
    return tuple(sorted(str(value) for value in record.get("selected_service_ids") or [] if value))


def _job_reconciliation(
    job: Mapping[str, Any],
    *,
    client_state: Mapping[str, Any] | None,
    current_job: Mapping[str, Any] | None,
) -> dict[str, Any]:
    job_id = str(job.get("job_id") or "")
    current_job_id = str((client_state or {}).get("current_job_id") or "")
    job_status = str(job.get("status") or "unknown")
    client_status = str((client_state or {}).get("status") or "unknown")
    job_signature = _service_signature(job)
    current_signature = _service_signature(client_state or current_job or {})
    same_selected_services = bool(job_signature and current_signature and job_signature == current_signature)

    if current_job_id and job_id == current_job_id:
        if client_status == "verified":
            classification = "current_verified"
            recommended_disposition = "keep_current_verified"
            blocking = False
        elif client_status == "presumed_working":
            classification = "current_presumed_working"
            recommended_disposition = "keep_current_presumed_working"
            blocking = False
        else:
            classification = "current_validation_pending"
            recommended_disposition = "resolve_current_validation_choice"
            blocking = True
    elif job_status in PENDING_ACTIVATION_JOB_STATUSES and client_status in NON_BLOCKING_CLIENT_STATUSES and same_selected_services:
        classification = "superseded_by_current_client_state"
        recommended_disposition = "retain_as_historical_audit_trail"
        blocking = False
    elif job_status in PENDING_ACTIVATION_JOB_STATUSES:
        classification = "pending_validation_attention_required"
        recommended_disposition = "resolve_or_explicitly_retain"
        blocking = True
    else:
        classification = "historical_terminal_or_informational"
        recommended_disposition = "retain_as_historical_audit_trail"
        blocking = False

    return {
        "job_id": job.get("job_id"),
        "client_type": job.get("client_type"),
        "status": job.get("status"),
        "recovery_state": job.get("recovery_state"),
        "classification": classification,
        "recommended_disposition": recommended_disposition,
        "blocking": blocking,
        "same_selected_services_as_current": same_selected_services,
    }


def _activation_job_reconciliation(
    job_summaries: Sequence[Mapping[str, Any]],
    client_states: Mapping[str, Mapping[str, Any]],
    current_job_id: str | None,
) -> dict[str, Any]:
    jobs_by_id = {str(job.get("job_id")): job for job in job_summaries if job.get("job_id")}
    clients: dict[str, Any] = {}
    all_clients = sorted(
        {
            str(job.get("client_type") or "")
            for job in job_summaries
            if job.get("client_type")
        }
        | {str(client) for client in client_states}
    )
    for client in all_clients:
        client_state = client_states.get(client, {})
        client_current_job_id = str(client_state.get("current_job_id") or current_job_id or "")
        current_job = jobs_by_id.get(client_current_job_id)
        client_jobs = [
            _job_reconciliation(job, client_state=client_state, current_job=current_job)
            for job in job_summaries
            if str(job.get("client_type") or "") == client
        ]
        classifications = [str(job.get("classification") or "unknown") for job in client_jobs]
        clients[client] = {
            "client_status": client_state.get("status"),
            "validation_status": client_state.get("validation_status"),
            "current_job_id": client_current_job_id or None,
            "current_job_status": current_job.get("status") if isinstance(current_job, Mapping) else None,
            "classification_counts": _status_counts(classifications),
            "jobs": client_jobs,
        }

    all_reconciliations = [
        job
        for client in clients.values()
        for job in client.get("jobs", [])
        if isinstance(job, Mapping)
    ]
    return {
        "summary": {
            "current_verified_jobs": sum(1 for job in all_reconciliations if job.get("classification") == "current_verified"),
            "current_presumed_working_jobs": sum(1 for job in all_reconciliations if job.get("classification") == "current_presumed_working"),
            "current_validation_pending_jobs": sum(1 for job in all_reconciliations if job.get("classification") == "current_validation_pending"),
            "superseded_pending_jobs": sum(1 for job in all_reconciliations if job.get("classification") == "superseded_by_current_client_state"),
            "attention_required_jobs": sum(1 for job in all_reconciliations if job.get("blocking") is True),
        },
        "policy": {
            "source_ready": "tracked source/config/state is inspectable without mutation",
            "validation_pending": "current target-client validation choice or reload remains unresolved",
            "presumed_working": "operator accepted skip-validation state without target-client proof",
            "verified": "target-client-visible validation passed or operator-directed project-local validation was recorded",
        },
        "clients": clients,
    }


def _raw_state_summary(root: Path, raw_state: Mapping[str, Any] | None, read_error: str | None) -> dict[str, Any]:
    path = project_state.project_state_path(root)
    if raw_state is None:
        return {
            "state_path": str(path),
            "exists": path.exists(),
            "read_error": read_error,
            "digest": project_state.state_file_artifact_digest(root),
        }
    project = raw_state.get("project") if isinstance(raw_state.get("project"), Mapping) else {}
    project_init = raw_state.get("project_init") if isinstance(raw_state.get("project_init"), Mapping) else {}
    jobs = project_init.get("activation_jobs") if isinstance(project_init.get("activation_jobs"), Mapping) else {}
    client_states = project_init.get("client_states") if isinstance(project_init.get("client_states"), Mapping) else {}
    job_summaries = [
        _activation_job_summary(job)
        for job in jobs.values()
        if isinstance(job, Mapping)
    ]
    state_summary = {
        "state_path": str(path),
        "exists": True,
        "digest": project_state.state_file_artifact_digest(root),
        "read_error": None,
        "raw_status": raw_state.get("status"),
        "meta_revision": (raw_state.get("meta") or {}).get("revision") if isinstance(raw_state.get("meta"), Mapping) else None,
        "project_name": project.get("name"),
        "project_root": project.get("root"),
        "project_root_hash": project.get("root_hash"),
        "root_match": project_state.root_match_details(dict(raw_state), root),
        "project_init_present": bool(project_init),
        "current_job_id": project_init.get("current_job_id"),
        "client_states": {
            str(client): _client_state_summary(state)
            for client, state in sorted(client_states.items())
            if isinstance(state, Mapping)
        },
        "activation_job_status_counts": _status_counts(
            [str(summary.get("status") or "unknown") for summary in job_summaries]
        ),
        "activation_jobs": sorted(job_summaries, key=lambda item: str(item.get("job_id") or "")),
    }
    state_summary["activation_job_reconciliation"] = _activation_job_reconciliation(
        state_summary["activation_jobs"],
        state_summary["client_states"],
        str(project_init.get("current_job_id") or "") or None,
    )
    return state_summary


def inspect_root(root: str | Path, *, label: str, client_types: Sequence[str]) -> dict[str, Any]:
    canonical = _canonical(root)
    raw_state, read_error = _json_summary(project_state.project_state_path(canonical))
    inspections = {
        client_type: project_state.inspect_project_init_state(
            canonical,
            require_workspace=True,
            target_client=client_type,
        )
        for client_type in client_types
    }
    first = inspections[client_types[0]] if client_types else {}
    return {
        "label": label,
        "project_root": str(canonical),
        "readiness_status": first.get("lifecycle_status"),
        "recommended_action": first.get("recommended_action"),
        "inspections": inspections,
        "state": _raw_state_summary(canonical, raw_state, read_error),
    }


def _script_source_root(script_path: str | Path) -> str | None:
    path = Path(script_path).expanduser().resolve(strict=False)
    if path.parent.name != "scripts":
        return None
    return str(path.parent.parent)


def _process_cwd(pid: str) -> str | None:
    try:
        return str((Path("/proc") / pid / "cwd").resolve(strict=True))
    except OSError:
        return None


def _extract_process_script(command: str, *, cwd: str | None = None) -> tuple[str | None, str | None]:
    try:
        parts = shlex.split(command)
    except ValueError:
        parts = command.split()
    for part in parts:
        candidate = Path(part)
        if candidate.name in HELPER_PROCESS_SCRIPT_NAMES:
            if candidate.is_absolute():
                script_path = candidate
            elif cwd:
                script_path = Path(cwd) / candidate
            else:
                return str(candidate), None
            script = str(script_path.expanduser().resolve(strict=False))
            source_root = _script_source_root(script)
            return script, source_root
    return None, None


def list_helper_processes() -> list[dict[str, Any]]:
    try:
        result = subprocess.run(
            ["ps", "-eo", "pid=,args="],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if result.returncode != 0:
        return []
    processes: list[dict[str, Any]] = []
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if not stripped or not any(name in stripped for name in HELPER_PROCESS_SCRIPT_NAMES):
            continue
        try:
            pid_text, command = stripped.split(maxsplit=1)
        except ValueError:
            continue
        cwd = _process_cwd(pid_text)
        script, source_root = _extract_process_script(command, cwd=cwd)
        processes.append(
            {
                "pid": int(pid_text) if pid_text.isdigit() else pid_text,
                "cwd": cwd,
                "script": script,
                "source_root": source_root,
                "command": command,
            }
        )
    return processes


def _readiness_findings(
    roots: Sequence[Mapping[str, Any]],
    helper_processes: Sequence[Mapping[str, Any]],
    activation_artifacts: Mapping[str, Any],
) -> tuple[str, list[str], list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    next_actions: list[str] = []
    primary = roots[0] if roots else {}
    primary_root = str(primary.get("project_root") or "")
    primary_status = str(primary.get("readiness_status") or "")
    state = primary.get("state") if isinstance(primary.get("state"), Mapping) else {}
    root_match = state.get("root_match") if isinstance(state.get("root_match"), Mapping) else {}
    expected_project_name = Path(primary_root).name if primary_root else ""
    state_project_name = str(state.get("project_name") or "")
    state_client_bindings = [
        binding
        for client_state in (state.get("client_states") or {}).values()
        if isinstance(client_state, Mapping)
        for binding in client_state.get("selected_service_bindings") or []
    ]
    state_job_bindings = [
        binding
        for activation_job in state.get("activation_jobs") or []
        if isinstance(activation_job, Mapping)
        for binding in activation_job.get("selected_service_bindings") or []
    ]
    selected_bindings = [str(binding) for binding in state_client_bindings + state_job_bindings]
    reconciliation = state.get("activation_job_reconciliation") if isinstance(state.get("activation_job_reconciliation"), Mapping) else {}
    reconciliation_summary = reconciliation.get("summary") if isinstance(reconciliation.get("summary"), Mapping) else {}

    if primary_status == "invalid_blocked":
        blockers.append("primary_project_state_invalid_blocked")
        if root_match.get("root_matches") is False or root_match.get("root_hash_matches") is False:
            blockers.append("primary_project_state_root_mismatch")
        next_actions.append("Do not hand-edit .project/context_forge_state.json; use helper-approved repair or an approved rebind plan.")
    elif primary_status == "missing":
        warnings.append("primary_project_state_missing")
    elif primary_status != "valid":
        warnings.append(f"primary_project_state_{primary_status or 'unknown'}")

    if state_project_name and expected_project_name and state_project_name != expected_project_name:
        blockers.append("project_state_name_mismatch")
        next_actions.append("Retire stale project.name values through a focused project-state migration before claiming activation readiness.")

    if int(reconciliation_summary.get("attention_required_jobs") or 0):
        warnings.append("project_init_activation_jobs_need_reconciliation")
        next_actions.append(
            "Use roots[0].state.activation_job_reconciliation to resolve current validation choices or explicitly retain historical pending jobs."
        )

    compare_roots = roots[1:]
    if any(str(root.get("readiness_status") or "") == "valid" for root in compare_roots):
        warnings.append("comparison_root_has_valid_project_state")
        next_actions.append("Treat the comparison root as potentially live state until dirty-checkout retirement explicitly moves or retires it.")

    source_roots = sorted(
        {
            str(process.get("source_root"))
            for process in helper_processes
            if process.get("source_root")
        }
    )
    unknown_source_processes = [
        process
        for process in helper_processes
        if process.get("script") and not process.get("source_root")
    ]
    foreign_source_roots = [source_root for source_root in source_roots if source_root != primary_root]
    if unknown_source_processes:
        blockers.append("helper_process_source_unknown")
        next_actions.append("Do not treat helper readiness as proven while any helper process source root is unknown.")
    if foreign_source_roots:
        blockers.append("helper_process_source_mismatch")
        next_actions.append("Do not terminate helper processes implicitly; rebind or retire the legacy helper source only after explicit approval.")

    python_environment = activation_artifacts.get("python_environment") if isinstance(activation_artifacts.get("python_environment"), Mapping) else {}
    if python_environment.get("is_executable") is not True:
        blockers.append("python_environment_missing")
        next_actions.append("Create the ignored local .venv before retargeting project-local MCP commands to this checkout.")

    codex_config = activation_artifacts.get("codex_config") if isinstance(activation_artifacts.get("codex_config"), Mapping) else {}
    if codex_config.get("read_error"):
        blockers.append("codex_config_unreadable")
    if codex_config.get("parse_error"):
        blockers.append("codex_config_parse_error")
    legacy_config_refs = sum(int(count) for count in (codex_config.get("legacy_root_reference_counts") or {}).values())
    if legacy_config_refs:
        blockers.append("codex_config_legacy_root_references")
        next_actions.append("Retarget project-local MCP command, args, and cwd values through the helper/project-init path; do not activate the legacy-bound config as-is.")
    for server in codex_config.get("mcp_servers") or []:
        if isinstance(server, Mapping) and (server.get("command_exists") is False or server.get("cwd_exists") is False):
            blockers.append("codex_config_missing_mcp_path")
            break

    serena = activation_artifacts.get("serena_project_instance") if isinstance(activation_artifacts.get("serena_project_instance"), Mapping) else {}
    expected_serena = serena.get("expected") if isinstance(serena.get("expected"), Mapping) else {}
    legacy_serena = serena.get("legacy") if isinstance(serena.get("legacy"), Mapping) else {}
    legacy_serena_refs = sum(int(count) for count in (legacy_serena.get("legacy_root_reference_counts") or {}).values())
    serena_selected = any(binding.startswith("serena:") for binding in selected_bindings)
    serena_legacy_present = bool(legacy_serena.get("instance_exists"))
    if expected_serena.get("manifest_exists") is not True and (serena_selected or serena_legacy_present):
        warnings.append("serena_project_instance_not_provisioned")
        next_actions.append(
            "Open or update a GitHub-tracked Serena/project-init slice to generate the canonical cf-controlplane Serena instance or record an explicit validated compatibility decision."
        )
    if legacy_serena.get("instance_exists") and legacy_serena_refs:
        warnings.append("legacy_serena_project_instance_present")

    compatibility = activation_artifacts.get("compatibility_identifiers") if isinstance(activation_artifacts.get("compatibility_identifiers"), Mapping) else {}
    compatibility_refs = sum(int(count) for count in (compatibility.get("reference_counts") or {}).values())
    if compatibility_refs:
        warnings.append("project_init_compatibility_identifiers_present")
        next_actions.append("Use the compatibility_identifiers.references report to retire active context-portal naming through focused GitHub-tracked slices; do not broad-rename compatibility/history.")

    if blockers:
        status = "blocked"
    elif warnings:
        status = "attention_required"
    else:
        status = "ready"
    return status, blockers, warnings, list(dict.fromkeys(next_actions))


def build_report(
    *,
    project_root: str | Path,
    compare_roots: Sequence[str | Path] = (),
    client_types: Sequence[str] = ("codex", "pi", "gemini", "opencode"),
    include_processes: bool = True,
    process_snapshot: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    roots = [inspect_root(project_root, label="primary", client_types=client_types)]
    roots.extend(
        inspect_root(root, label=f"comparison:{index}", client_types=client_types)
        for index, root in enumerate(compare_roots, start=1)
    )
    helper_processes = list(process_snapshot) if process_snapshot is not None else (list_helper_processes() if include_processes else [])
    activation_artifacts = inspect_activation_artifacts(project_root)
    status, blockers, warnings, next_actions = _readiness_findings(roots, helper_processes, activation_artifacts)
    return {
        "schema_uri": REPORT_SCHEMA_URI,
        "project_name": "ContextForge",
        "status": status,
        "blockers": blockers,
        "warnings": warnings,
        "roots": roots,
        "activation_artifacts": activation_artifacts,
        "helper_processes": helper_processes,
        "next_actions": next_actions,
        "non_actions": [
            "read-only inspection; no project files are written",
            "no helper approval/apply workflow is invoked",
            "no client config, trust, registry, catalog, service, or process state is mutated",
        ],
    }


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default=str(Path.cwd()), help="Primary project root to inspect.")
    parser.add_argument(
        "--compare-root",
        action="append",
        default=[],
        help="Additional project root to compare against the primary root. May be repeated.",
    )
    parser.add_argument(
        "--client-type",
        action="append",
        choices=sorted(helper.SUPPORTED_CLIENTS),
        help="Target client type to inspect. May be repeated. Defaults to all supported clients.",
    )
    parser.add_argument("--no-processes", action="store_true", help="Skip read-only helper process source inspection.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    client_types = tuple(args.client_type or ("codex", "pi", "gemini", "opencode"))
    report = build_report(
        project_root=args.project_root,
        compare_roots=tuple(args.compare_root),
        client_types=client_types,
        include_processes=not args.no_processes,
    )
    print(json.dumps(report, indent=2 if args.pretty else None, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
