#!/usr/bin/env python3
"""Deterministic no-mutation onboarding records for new ContextForge services."""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import control_plane_redaction as redaction


HELPER_VERSION = 1
SCHEMA_URI = "contextforge://control-plane/schemas/service-onboarding-record/v1"
SESSION_SCHEMA_URI = "contextforge://control-plane/schemas/service-onboarding-session/v1"
DEFAULT_SESSION_DIR = Path("run/service-onboarding-sessions")
LOCAL_SESSION_STORAGE_MODE = "local_ignored_session_file"

DIALOGUE_STATES = (
    "intake",
    "source_discovery",
    "feasibility_review",
    "classification",
    "strategy_selection",
    "footprint_plan",
    "approval_gate",
    "handoff",
)

CLASSIFICATION_VALUES = {
    "plan_type": {
        "read_only_audit",
        "source_only_scaffolding",
        "dev_docker_proof",
        "runtime_registration",
        "client_validation",
        "cleanup_migration",
        "compatibility_decision",
        "release_hardening",
    },
    "localization_type": {
        "shared_canonical",
        "credential_scoped",
        "user_scoped",
        "project_scoped",
        "client_local_session_scoped",
        "remote_native_hosted",
        "dev_only",
        "gateway_integrated_exception",
    },
    "functional_type": {
        "code_intelligence",
        "search_retrieval",
        "browser_automation",
        "governance_memory",
        "shell_process_control",
        "filesystem_content",
        "remote_api_tool",
        "client_adapter",
        "model_inference",
        "observability_diagnostics",
        "service_management",
    },
    "transport_type": {
        "stdio",
        "sse",
        "streamable_http",
        "rest_openapi",
        "native_hosted",
        "bridge_required",
        "mixed",
    },
    "state_type": {
        "stateless",
        "local_filesystem_state",
        "project_metadata",
        "credential_state",
        "cache_index_state",
        "registry_state",
        "runtime_evidence_state",
    },
    "approval_type": {
        "source_only",
        "local_ignored_state",
        "docker_dev_surface",
        "contextforge_dev_registry",
        "live_runtime_service",
        "global_config_client_install",
        "pi_client_mutation",
        "destructive_cleanup",
    },
}

NON_MUTATION_DEFAULTS = (
    "do not register ContextForge services",
    "do not start, stop, build, or rebuild Docker containers",
    "do not mutate systemd units or processes",
    "do not write global or client config",
    "do not copy secrets, OAuth state, trust tokens, or credentials",
    "do not change hook trust/state",
    "do not clean registry records",
    "do not mutate the legacy archive checkout",
)

APPROVAL_TEXT = {
    "docker_dev_surface": "Approve Docker development-surface execution for this service only, including bounded build/run/probe commands and generated local evidence paths.",
    "contextforge_dev_registry": "Approve ContextForge development registry/API mutation for this service only, with disposable credentials and post-write readback.",
    "live_runtime_service": "Approve live/runtime service mutation for this service only, including exact service, registry, process, and rollback boundaries.",
    "global_config_client_install": "Approve global/client configuration writes for this service only, naming exact files, client commands, and reload requirements.",
    "pi_client_mutation": "Approve Pi client mutation for this service only, naming exact install/reload/config paths and validation commands.",
    "destructive_cleanup": "Approve destructive cleanup for this service only, naming exact objects, selectors, backups, and rollback or compensation steps.",
}


class ServiceOnboardingInputError(ValueError):
    """Raised when an onboarding descriptor is malformed."""


def build_onboarding_record(
    descriptor: Mapping[str, Any],
    *,
    project_root: str | None = None,
    issue: str | None = None,
    previous_record: Mapping[str, Any] | None = None,
    session_id: str | None = None,
    storage_mode: str = "stdout_only",
    write_persistence: bool = False,
    session_record_path: str | None = None,
) -> dict[str, Any]:
    """Build a structured service-onboarding record without side effects."""

    if not isinstance(descriptor, Mapping):
        raise ServiceOnboardingInputError("descriptor must be a mapping")
    if previous_record is not None and not isinstance(previous_record, Mapping):
        raise ServiceOnboardingInputError("previous_record must be a mapping")

    source = _merge_resume_descriptor(previous_record, descriptor)
    candidate_service = _first_string(
        source.get("candidate_service"),
        source.get("candidate_service_name"),
        source.get("service_family"),
        source.get("canonical_service"),
        source.get("name"),
    )
    operator_goal = _first_string(source.get("operator_goal"), source.get("goal"), source.get("desired_outcome"))
    source_evidence = _source_evidence(source)
    classification = _classification(source)
    feasibility = _feasibility(source, classification)
    strategy = _strategy(source, classification, feasibility)
    footprint = _footprint(source, candidate_service, strategy, project_root)
    approvals = _approval_gate(classification, strategy)
    record_blockers = _blockers(candidate_service, operator_goal, source_evidence, classification, feasibility, footprint)
    pre_runtime_gate = _pre_runtime_workflow_gate(
        source,
        candidate_service,
        source_evidence,
        classification,
        feasibility,
        strategy,
        footprint,
        approvals,
        record_blockers,
    )
    blockers = _unique_blockers(record_blockers + list(pre_runtime_gate["blockers"]))
    current_state = _current_state(blockers, approvals)
    questions = _questions(blockers, classification, strategy)

    status = "ready_for_handoff"
    if blockers:
        status = "needs_user_input"
    elif approvals["approval_required"]:
        status = "approval_required"

    record = {
        "schema_version": HELPER_VERSION,
        "schema_uri": SCHEMA_URI,
        "status": status,
        "mutation_allowed": False,
        "redaction_status": "redacted",
        "issue": issue,
        "project_root": project_root,
        "current_state": current_state,
        "state_sequence": list(DIALOGUE_STATES),
        "candidate_service": candidate_service,
        "operator_goal": operator_goal,
        "source_evidence": source_evidence,
        "unresolved_source_questions": [blocker["question"] for blocker in blockers if blocker["field"].startswith("source_")],
        "classification": classification,
        "feasibility": feasibility,
        "integration_strategy": strategy,
        "footprint_plan": footprint,
        "approval_gate": approvals,
        "pre_runtime_workflow_gate": pre_runtime_gate,
        "dialogue_session": _dialogue_session(
            previous_record,
            session_id,
            current_state,
            status,
            questions,
            classification,
            strategy,
            approvals,
            storage_mode,
            write_persistence,
            session_record_path,
        ),
        "blockers": blockers,
        "next_questions": questions,
        "non_actions": list(NON_MUTATION_DEFAULTS),
        "residual_risks": _residual_risks(source, blockers, approvals),
        "next_issue_pr_steps": _next_steps(status, candidate_service, approvals),
        "source_descriptor": _redact_for_record(source),
    }
    _validate_no_secret_leaks(record)
    return record


def _merge_resume_descriptor(previous_record: Mapping[str, Any] | None, descriptor: Mapping[str, Any]) -> dict[str, Any]:
    source = _json_compatible_copy(descriptor)
    if previous_record is None:
        return source

    previous_source = previous_record.get("source_descriptor")
    if not isinstance(previous_source, Mapping):
        raise ServiceOnboardingInputError("previous_record.source_descriptor must be a mapping when resuming")
    return _deep_merge(_json_compatible_copy(previous_source), source)


def _dialogue_session(
    previous_record: Mapping[str, Any] | None,
    session_id: str | None,
    current_state: str,
    status: str,
    questions: list[str],
    classification: Mapping[str, Mapping[str, str | None]],
    strategy: Mapping[str, Any],
    approvals: Mapping[str, Any],
    storage_mode: str,
    write_persistence: bool,
    session_record_path: str | None,
) -> dict[str, Any]:
    previous_session = _mapping(previous_record.get("dialogue_session") if previous_record else None)
    previous_history = [
        item
        for item in _as_list(previous_session.get("history"))
        if isinstance(item, Mapping)
    ]
    previous_state_history = _string_list(previous_session.get("state_history"))
    previous_questions = set(_string_list(previous_record.get("next_questions") if previous_record else None))
    current_questions = set(questions)
    previous_state = _first_string(previous_record.get("current_state") if previous_record else None)
    previous_status = _first_string(previous_record.get("status") if previous_record else None)
    resolved_session_id = (
        session_id
        or _first_string(previous_session.get("session_id"))
        or "unassigned"
    )
    turn_index = len(previous_history) + 1
    transition: dict[str, str] = {
        "from_state": previous_state or "new_session",
        "to_state": current_state,
        "status": status,
    }
    if previous_status:
        transition["from_status"] = previous_status

    session = {
        "schema_uri": SESSION_SCHEMA_URI,
        "session_id": resolved_session_id,
        "turn_index": turn_index,
        "resume_source": "previous_record" if previous_record is not None else "fresh_descriptor",
        "previous_state": previous_state,
        "current_state": current_state,
        "state_history": _unique(previous_state_history + [current_state]),
        "answered_questions": sorted(previous_questions - current_questions),
        "decision_log": _decision_log(turn_index, classification, strategy, approvals),
        "storage_mode": storage_mode,
        "write_persistence": bool(write_persistence),
        "history": [_json_compatible_copy(item) for item in previous_history] + [transition],
        "next_resume_inputs": [
            "save this onboarding record if future resumption is needed",
            "rerun with --previous-record and an updated descriptor to add evidence",
        ],
    }
    if session_record_path:
        session["session_record_path"] = session_record_path
    return session


def session_record_path(session_dir: Path, session_id: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", session_id):
        raise ServiceOnboardingInputError("session_id must be 1-128 characters of letters, digits, dot, underscore, or dash")
    return session_dir / f"{session_id}.json"


def resolve_session_dir(session_dir: str | Path | None, *, project_root: str | None = None) -> Path:
    root = Path(project_root).expanduser() if project_root else Path.cwd()
    root = root.resolve()
    requested = Path(session_dir) if session_dir else DEFAULT_SESSION_DIR
    if not requested.is_absolute():
        requested = root / requested
    requested = requested.expanduser().resolve()
    allowed_root = (root / "run").resolve()
    if requested != allowed_root and allowed_root not in requested.parents:
        raise ServiceOnboardingInputError("session_dir must be inside the project-local ignored run/ directory")
    return requested


def load_session_record(session_dir: Path, session_id: str) -> dict[str, Any]:
    return _load_record(str(session_record_path(session_dir, session_id)))


def save_session_record(record: Mapping[str, Any], session_dir: Path) -> Path:
    session = _mapping(record.get("dialogue_session"))
    session_id = _first_string(session.get("session_id"))
    if not session_id or session_id == "unassigned":
        raise ServiceOnboardingInputError("--save-session requires --session-id or a previous record with a session_id")
    path = session_record_path(session_dir, session_id)
    session_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp_path.replace(path)
    return path


def build_session_status(record: Mapping[str, Any], *, session_record_path: str | None = None) -> dict[str, Any]:
    """Build a compact no-mutation readback summary for a saved onboarding session."""

    if not isinstance(record, Mapping):
        raise ServiceOnboardingInputError("session record must be a mapping")
    session = _mapping(record.get("dialogue_session"))
    classification = _mapping(record.get("classification"))
    strategy = _mapping(record.get("integration_strategy"))
    approvals = _mapping(record.get("approval_gate"))

    known_dimensions = sorted(
        dimension
        for dimension, entry in classification.items()
        if isinstance(entry, Mapping) and entry.get("status") == "known"
    )
    open_dimensions = sorted(
        dimension
        for dimension, entry in classification.items()
        if not isinstance(entry, Mapping) or entry.get("status") != "known"
    )
    summary = {
        "schema_uri": SESSION_SCHEMA_URI,
        "summary_type": "service_onboarding_session_status",
        "session_id": _first_string(session.get("session_id")) or "unassigned",
        "candidate_service": _first_string(record.get("candidate_service")),
        "status": _first_string(record.get("status")),
        "current_state": _first_string(record.get("current_state")),
        "turn_index": session.get("turn_index"),
        "state_history": _string_list(session.get("state_history")),
        "storage_mode": _first_string(session.get("storage_mode")) or "unknown",
        "write_persistence": bool(session.get("write_persistence")),
        "mutation_allowed": bool(record.get("mutation_allowed")),
        "classification_known": known_dimensions,
        "classification_open": open_dimensions,
        "primary_paradigm": _first_string(strategy.get("primary_paradigm")),
        "secondary_validation_paradigms": _string_list(strategy.get("secondary_validation_paradigms")),
        "approval_required": bool(approvals.get("approval_required")),
        "required_approval_types": _string_list(approvals.get("required_approval_types")),
        "pre_runtime_workflow_gate": _compact_pre_runtime_workflow_gate(record.get("pre_runtime_workflow_gate")),
        "answered_questions": _string_list(session.get("answered_questions")),
        "next_questions": _string_list(record.get("next_questions")),
        "next_resume_inputs": _string_list(session.get("next_resume_inputs")),
        "next_issue_pr_steps": _string_list(record.get("next_issue_pr_steps")),
        "residual_risks": _string_list(record.get("residual_risks")),
    }
    if session_record_path:
        summary["session_record_path"] = session_record_path
    elif _first_string(session.get("session_record_path")):
        summary["session_record_path"] = _first_string(session.get("session_record_path"))
    _validate_no_secret_leaks(summary)
    return summary


def list_session_statuses(session_dir: Path) -> dict[str, Any]:
    """List compact readback summaries for saved onboarding sessions without writing state."""

    statuses: list[dict[str, Any]] = []
    if session_dir.exists():
        if not session_dir.is_dir():
            raise ServiceOnboardingInputError("session_dir must be a directory when listing sessions")
        for path in sorted(session_dir.glob("*.json"), key=lambda item: item.name):
            statuses.append(build_session_status(_load_record(str(path)), session_record_path=str(path)))
    result = {
        "schema_uri": SESSION_SCHEMA_URI,
        "summary_type": "service_onboarding_session_list",
        "session_dir": str(session_dir),
        "session_count": len(statuses),
        "mutation_allowed": False,
        "sessions": statuses,
    }
    _validate_no_secret_leaks(result)
    return result


def build_session_template(record: Mapping[str, Any], *, session_record_path: str | None = None) -> dict[str, Any]:
    """Build a deterministic descriptor patch scaffold for resuming a saved session."""

    if not isinstance(record, Mapping):
        raise ServiceOnboardingInputError("session record must be a mapping")

    status = build_session_status(record, session_record_path=session_record_path)
    classification = _mapping(record.get("classification"))
    footprint = _mapping(record.get("footprint_plan"))
    feasibility = _mapping(record.get("feasibility"))
    pre_runtime_gate = _mapping(record.get("pre_runtime_workflow_gate"))

    descriptor_patch: dict[str, Any] = {}
    if not _first_string(record.get("candidate_service")):
        descriptor_patch["candidate_service"] = "<candidate service name>"
    if not _first_string(record.get("operator_goal")):
        descriptor_patch["operator_goal"] = "<operator outcome this service should support>"
    if not _as_list(record.get("source_evidence")):
        descriptor_patch["source_evidence"] = [
            {"type": "<docs|package|repository|local_path|issue>", "ref": "<source reference>"}
        ]

    classification_patch = {}
    for dimension, allowed in CLASSIFICATION_VALUES.items():
        entry = _mapping(classification.get(dimension))
        if entry.get("status") != "known":
            classification_patch[dimension] = f"<one of: {', '.join(sorted(allowed))}>"
    if classification_patch:
        descriptor_patch["classification"] = classification_patch

    service_slug = _first_string(footprint.get("service_slug"))
    if not service_slug:
        descriptor_patch["footprint_plan"] = {"service_slug": "<stable-service-slug>"}

    missing_gate_dimensions = set(_string_list(pre_runtime_gate.get("missing_dimensions")))
    if "credential_boundary" in missing_gate_dimensions:
        descriptor_patch["credential_boundary"] = "<credential, account, tenant, token, or installation boundary>"
    if "scope_locality" in missing_gate_dimensions:
        descriptor_patch["scope_boundary"] = "<shared, project, user, credential, remote, dev, or client-local boundary evidence>"
    if "state_footprint" in missing_gate_dimensions:
        descriptor_patch.setdefault("footprint_plan", {})["state_footprint"] = "<stateless or concrete local/cache/registry/runtime state footprint>"
    if "validation_probe_plan" in missing_gate_dimensions:
        descriptor_patch["validation_probe_plan"] = [
            {"layer": "<source-only planned probe layer>", "description": "<what a later approved turn should validate>"}
        ]

    evidence_gaps = _string_list(feasibility.get("evidence_gaps"))
    if evidence_gaps:
        descriptor_patch["feasibility"] = {
            "evidence_gaps": [],
            "notes": [f"<evidence resolving {gap}>" for gap in evidence_gaps],
        }

    session_id = status["session_id"]
    rerun_guidance = {
        "descriptor_path": "<project-local descriptor patch JSON path>",
        "command": (
            "PYTHONDONTWRITEBYTECODE=1 .venv/bin/python "
            "scripts/control_plane_service_onboarding_helper.py "
            "--descriptor <descriptor-patch.json> "
            f"--resume-session {session_id} "
            "--project-root <project-root> "
            "--issue <issue> "
            "--save-session"
        ),
        "write_persistence": False,
    }

    result = {
        "schema_uri": SESSION_SCHEMA_URI,
        "summary_type": "service_onboarding_resume_template",
        "mutation_allowed": False,
        "session": status,
        "pre_runtime_workflow_gate": _compact_pre_runtime_workflow_gate(pre_runtime_gate),
        "next_questions": _string_list(record.get("next_questions")),
        "descriptor_patch_template": descriptor_patch,
        "rerun_guidance": rerun_guidance,
    }
    _validate_no_secret_leaks(result)
    return result


def _decision_log(
    turn_index: int,
    classification: Mapping[str, Mapping[str, str | None]],
    strategy: Mapping[str, Any],
    approvals: Mapping[str, Any],
) -> list[dict[str, Any]]:
    known_dimensions = sorted(
        dimension for dimension, entry in classification.items() if entry.get("status") == "known"
    )
    open_dimensions = sorted(
        dimension for dimension, entry in classification.items() if entry.get("status") != "known"
    )
    return [
        {
            "turn_index": turn_index,
            "classification_known": known_dimensions,
            "classification_open": open_dimensions,
            "primary_paradigm": strategy.get("primary_paradigm"),
            "approval_required": approvals.get("approval_required"),
            "required_approval_types": approvals.get("required_approval_types", []),
            "mutation_allowed": False,
        }
    ]


def _current_state(blockers: list[dict[str, str]], approvals: Mapping[str, Any]) -> str:
    if blockers:
        return blockers[0]["state"]
    if approvals["approval_required"]:
        return "approval_gate"
    return "handoff"


def _classification(source: Mapping[str, Any]) -> dict[str, dict[str, str | None]]:
    raw = _mapping(source.get("classification"))
    output: dict[str, dict[str, str | None]] = {}
    for dimension, allowed in CLASSIFICATION_VALUES.items():
        value = _first_string(raw.get(dimension), source.get(dimension))
        normalized = _normalize_token(value)
        if normalized in allowed:
            output[dimension] = {"value": normalized, "status": "known", "next_evidence_step": None}
        elif value:
            output[dimension] = {
                "value": None,
                "status": "invalid",
                "next_evidence_step": f"map `{value}` to one supported {dimension} value",
            }
        else:
            output[dimension] = {
                "value": None,
                "status": "unknown",
                "next_evidence_step": f"identify {dimension} from source evidence",
            }
    return output


def _feasibility(source: Mapping[str, Any], classification: Mapping[str, Mapping[str, str | None]]) -> dict[str, Any]:
    explicit = _mapping(source.get("feasibility"))
    known = _known_classifications(classification)
    missing = [dimension for dimension, entry in classification.items() if entry["status"] != "known"]
    evidence_gaps = _string_list(explicit.get("evidence_gaps"))
    if missing:
        evidence_gaps.extend(f"classification:{dimension}" for dimension in missing)

    verdict = _first_string(explicit.get("verdict"))
    confidence = _first_string(explicit.get("confidence"))
    if not verdict:
        verdict = "blocked" if evidence_gaps else "feasible"
    if not confidence:
        confidence = "low" if evidence_gaps else "medium"

    needs_bridge = known.get("transport_type") in {"stdio", "bridge_required", "mixed"}
    needs_docker_proof = known.get("plan_type") == "dev_docker_proof" or known.get("approval_type") == "docker_dev_surface"
    return {
        "verdict": verdict,
        "confidence": confidence,
        "evidence_gaps": _unique(evidence_gaps),
        "bridge_or_transceiver_likely": needs_bridge,
        "dev_docker_proof_likely": needs_docker_proof,
        "notes": _string_list(explicit.get("notes")),
    }


def _strategy(
    source: Mapping[str, Any],
    classification: Mapping[str, Mapping[str, str | None]],
    feasibility: Mapping[str, Any],
) -> dict[str, Any]:
    explicit = _mapping(source.get("strategy"))
    known = _known_classifications(classification)
    localization = known.get("localization_type")
    transport = known.get("transport_type")
    plan = known.get("plan_type")

    if localization == "project_scoped":
        primary = "Project-scoped backend"
        rationale = "service reads or writes project-local state"
    elif localization == "credential_scoped":
        primary = "Credential-scoped backend"
        rationale = "service authority is credential/account scoped"
    elif localization == "client_local_session_scoped":
        primary = "Client-local or session-scoped backend"
        rationale = "service behavior depends on client-local or session state"
    elif transport in {"stdio", "bridge_required", "mixed"}:
        primary = "Package-provided bridge/transceiver"
        rationale = "service needs a transport front end before IP-to-IP ContextForge registration"
    elif plan == "dev_docker_proof" or feasibility.get("dev_docker_proof_likely"):
        primary = "Dev Docker sidecar"
        rationale = "service needs isolated development validation before live registration"
    elif transport in {"streamable_http", "sse", "rest_openapi", "native_hosted"}:
        primary = "Direct native registration"
        rationale = "service appears to expose a directly registerable transport"
    elif localization == "gateway_integrated_exception":
        primary = "Gateway-image exception"
        rationale = "descriptor requests gateway-integrated handling; approval and justification required"
    else:
        primary = "Unselected"
        rationale = "classification evidence is incomplete"

    rejected = _string_list(explicit.get("rejected_alternatives"))
    if primary != "Direct native registration" and transport in {"stdio", "bridge_required", "mixed"}:
        rejected.append("Direct native registration rejected until packetized HTTP/SSE endpoint evidence exists")
    if primary != "Gateway-image exception":
        rejected.append("Gateway-image exception rejected by default; backend-local sidecar/transceiver remains preferred")

    secondary = []
    if feasibility.get("bridge_or_transceiver_likely") and primary != "Package-provided bridge/transceiver":
        secondary.append("Package-provided bridge/transceiver")
    if feasibility.get("dev_docker_proof_likely") and primary != "Dev Docker sidecar":
        secondary.append("Dev Docker sidecar")

    return {
        "primary_paradigm": _first_string(explicit.get("primary_paradigm")) or primary,
        "secondary_validation_paradigms": _unique(_string_list(explicit.get("secondary_validation_paradigms")) + secondary),
        "rationale": _first_string(explicit.get("rationale")) or rationale,
        "rejected_alternatives": _unique(rejected),
    }


def _footprint(
    source: Mapping[str, Any],
    candidate_service: str | None,
    strategy: Mapping[str, Any],
    project_root: str | None,
) -> dict[str, Any]:
    explicit = _mapping(source.get("footprint_plan"))
    slug = _slug(_first_string(explicit.get("service_slug"), source.get("service_slug"), candidate_service))
    files = _string_list(explicit.get("files"))
    docs = _string_list(explicit.get("docs"))
    tests = _string_list(explicit.get("tests"))
    scripts = _string_list(explicit.get("scripts"))
    docker_surfaces = _string_list(explicit.get("docker_surfaces"))
    generated_artifacts = _string_list(explicit.get("generated_artifacts"))

    if slug and not any(item.startswith("server-instances/") for item in files):
        files.append(f"server-instances/{slug}/")
    if not docs:
        docs.append("docs/initiatives/contextforge-control-plane/service-onboarding-helper.md")
    if not tests:
        tests.append("tests/test_control_plane_service_onboarding_helper.py")

    return {
        "service_slug": slug,
        "project_root": project_root,
        "files": _unique(files),
        "scripts": _unique(scripts),
        "docs": _unique(docs),
        "tests": _unique(tests),
        "docker_surfaces": _unique(docker_surfaces),
        "generated_artifacts": _unique(generated_artifacts),
        "contextforge_surfaces": _string_list(explicit.get("contextforge_surfaces")),
        "client_surfaces": _string_list(explicit.get("client_surfaces")),
        "cleanup_or_rollback": _string_list(explicit.get("cleanup_or_rollback")) or [
            "record rollback or compensating action before runtime mutation"
        ],
        "strategy_owner": strategy["primary_paradigm"],
    }


def _approval_gate(classification: Mapping[str, Mapping[str, str | None]], strategy: Mapping[str, Any]) -> dict[str, Any]:
    approval_values = []
    approval_entry = classification.get("approval_type", {})
    value = approval_entry.get("value")
    if value:
        approval_values.append(value)
    for paradigm in strategy.get("secondary_validation_paradigms", []):
        if paradigm == "Dev Docker sidecar":
            approval_values.append("docker_dev_surface")

    approval_values = _unique(approval_values)
    source_only = {"source_only", "local_ignored_state"}
    required = [item for item in approval_values if item not in source_only]
    exact_text = [APPROVAL_TEXT[item] for item in required if item in APPROVAL_TEXT]
    return {
        "approval_required": bool(required),
        "approval_types": approval_values,
        "required_approval_types": required,
        "exact_approval_text": exact_text,
        "stop_condition": "stop before runtime/global/client mutation" if required else "source-only path may proceed",
    }


def _pre_runtime_workflow_gate(
    source: Mapping[str, Any],
    candidate_service: str | None,
    source_evidence: list[dict[str, Any]],
    classification: Mapping[str, Mapping[str, str | None]],
    feasibility: Mapping[str, Any],
    strategy: Mapping[str, Any],
    footprint: Mapping[str, Any],
    approvals: Mapping[str, Any],
    record_blockers: list[dict[str, str]],
) -> dict[str, Any]:
    planned_probe_layers = _planned_validation_probe_layers(source, classification, strategy, footprint, approvals)
    known = _known_classifications(classification)
    credential_required = (
        known.get("localization_type") == "credential_scoped"
        or known.get("state_type") == "credential_state"
    )
    credential_boundary = _first_string(
        source.get("credential_boundary"),
        source.get("credential_scope"),
        source.get("account_boundary"),
        source.get("tenant_boundary"),
        source.get("token_boundary"),
        source.get("installation_boundary"),
    )
    state_known = (
        classification["state_type"]["status"] == "known"
        and (
            known.get("state_type") == "stateless"
            or bool(
                footprint.get("files")
                or footprint.get("scripts")
                or footprint.get("generated_artifacts")
                or footprint.get("contextforge_surfaces")
                or footprint.get("client_surfaces")
                or footprint.get("docker_surfaces")
            )
        )
    )
    checks = [
        (
            "source_evidence",
            bool(source_evidence),
            "upstream docs, package names, commands, local paths, issue links, or source contracts",
        ),
        (
            "canonical_service_identity",
            bool(candidate_service and footprint.get("service_slug")),
            "candidate service name plus stable canonical service slug or documented equivalent",
        ),
        (
            "scope_locality",
            classification["localization_type"]["status"] == "known",
            "source-backed shared, project, user, credential, remote, dev, client-local, or gateway-exception locality",
        ),
        (
            "transport",
            classification["transport_type"]["status"] == "known",
            "native transport or bridge-required transport evidence from sources",
        ),
        (
            "credential_boundary",
            bool(credential_boundary) if credential_required else True,
            "credential, account, tenant, token, or installation boundary when credentials scope the service",
        ),
        (
            "state_footprint",
            state_known,
            "stateless declaration or concrete local/cache/registry/runtime state footprint",
        ),
        (
            "approval_boundary",
            classification["approval_type"]["status"] == "known" and bool(approvals.get("stop_condition")),
            "source-only, local ignored state, Docker, registry, live runtime, client/global, Pi, or cleanup approval boundary",
        ),
        (
            "validation_probe_plan",
            bool(planned_probe_layers),
            "planned validation probe layers only; no probes are run by this helper",
        ),
    ]

    known_dimensions = [name for name, is_known, _required in checks if is_known]
    missing_dimensions = [name for name, is_known, _required in checks if not is_known]
    required_pre_runtime_evidence = [
        {
            "dimension": name,
            "status": "known" if is_known else "missing",
            "required": required,
        }
        for name, is_known, required in checks
    ]
    blockers = [_pre_runtime_blocker(name) for name in missing_dimensions]
    gate_status = "blocked" if blockers or record_blockers else "ready_for_pre_runtime_handoff"
    if gate_status != "blocked" and approvals.get("approval_required"):
        gate_status = "approval_required_before_runtime"

    return {
        "runtime_work_allowed": False,
        "gate_status": gate_status,
        "known_dimensions": known_dimensions,
        "missing_dimensions": missing_dimensions,
        "required_pre_runtime_evidence": required_pre_runtime_evidence,
        "planned_validation_probe_layers": planned_probe_layers,
        "blockers": blockers,
        "non_actions": [
            "plan validation probes only",
            "do not run probes or start services from the pre-runtime gate",
        ],
    }


def _planned_validation_probe_layers(
    source: Mapping[str, Any],
    classification: Mapping[str, Mapping[str, str | None]],
    strategy: Mapping[str, Any],
    footprint: Mapping[str, Any],
    approvals: Mapping[str, Any],
) -> list[dict[str, Any]]:
    explicit = []
    for item in _as_list(source.get("validation_probe_plan")):
        if isinstance(item, Mapping):
            layer = _first_string(item.get("layer"), item.get("name"), item.get("type"))
            description = _first_string(item.get("description"), item.get("plan"), item.get("ref"))
            if layer:
                explicit.append(_probe_layer(layer, description or "operator-supplied source-only probe plan"))
        elif isinstance(item, str):
            explicit.append(_probe_layer(_normalize_token(item) or "operator_supplied_probe", item))
    if explicit:
        return explicit

    known = _known_classifications(classification)
    transport = known.get("transport_type")
    layers = []
    if transport in {"streamable_http", "sse", "rest_openapi", "native_hosted"}:
        layers.append(_probe_layer("native_transport_contract_readback", "later read endpoint metadata and list/call behavior for the native transport"))
    if transport in {"stdio", "bridge_required", "mixed"} or "Package-provided bridge/transceiver" in {
        strategy.get("primary_paradigm"),
        *strategy.get("secondary_validation_paradigms", []),
    }:
        layers.append(_probe_layer("bridge_transport_smoke_plan", "later verify the package bridge/transceiver exposes the missing HTTP or SSE side"))
    if known.get("localization_type") == "credential_scoped" or known.get("state_type") == "credential_state":
        layers.append(_probe_layer("credential_scope_negative_readback", "later prove the binding cannot cross credential or tenant boundaries"))
    if known.get("localization_type") == "client_local_session_scoped":
        layers.append(_probe_layer("client_session_scope_probe", "later validate behavior against the exact client-local session boundary"))
    if known.get("state_type") and known.get("state_type") != "stateless":
        layers.append(_probe_layer("state_footprint_readback", "later read back declared local/cache/registry/runtime evidence state without broadening scope"))
    if approvals.get("approval_required"):
        layers.append(_probe_layer("approval_scoped_runtime_readback", "later run only after exact approval for the listed runtime or client surface"))
    if footprint.get("generated_artifacts"):
        layers.append(_probe_layer("generated_artifact_review", "later inspect generated local evidence artifacts before promoting claims"))
    return _unique_probe_layers(layers)


def _probe_layer(layer: str, description: str) -> dict[str, Any]:
    return {
        "layer": layer,
        "status": "planned",
        "runtime_execution": False,
        "description": description,
    }


def _pre_runtime_blocker(dimension: str) -> dict[str, str]:
    questions = {
        "source_evidence": "What source evidence proves the service shape before runtime work?",
        "canonical_service_identity": "What canonical service identity and stable service slug should ContextForge use?",
        "scope_locality": "Which scope/locality evidence defines whether this is shared, project, credential, user, client-local, remote, dev, or gateway-exception?",
        "transport": "Which native transport or bridge-required transport evidence can be checked from sources?",
        "credential_boundary": "Which credential, account, tenant, token, or installation boundary defines this service binding?",
        "state_footprint": "Which state footprint evidence defines files, cache, registry, runtime evidence, or stateless behavior?",
        "approval_boundary": "Which approval boundary applies before runtime, client, global, registry, or cleanup work?",
        "validation_probe_plan": "Which validation probe layers should be planned from source evidence without running them?",
    }
    states = {
        "source_evidence": "source_discovery",
        "canonical_service_identity": "intake",
        "scope_locality": "classification",
        "transport": "feasibility_review",
        "credential_boundary": "classification",
        "state_footprint": "footprint_plan",
        "approval_boundary": "approval_gate",
        "validation_probe_plan": "feasibility_review",
    }
    return _blocker(states[dimension], f"pre_runtime_workflow_gate.{dimension}", questions[dimension])


def _compact_pre_runtime_workflow_gate(value: Any) -> dict[str, Any]:
    gate = _mapping(value)
    return {
        "runtime_work_allowed": False,
        "gate_status": _first_string(gate.get("gate_status")) or "unknown",
        "known_dimensions": _string_list(gate.get("known_dimensions")),
        "missing_dimensions": _string_list(gate.get("missing_dimensions")),
        "planned_validation_probe_layers": [
            {
                "layer": _first_string(layer.get("layer")),
                "status": _first_string(layer.get("status")) or "planned",
                "runtime_execution": bool(layer.get("runtime_execution")),
            }
            for layer in _as_list(gate.get("planned_validation_probe_layers"))
            if isinstance(layer, Mapping) and _first_string(layer.get("layer"))
        ],
        "blocker_fields": [
            _first_string(blocker.get("field"))
            for blocker in _as_list(gate.get("blockers"))
            if isinstance(blocker, Mapping) and _first_string(blocker.get("field"))
        ],
    }


def _blockers(
    candidate_service: str | None,
    operator_goal: str | None,
    source_evidence: list[dict[str, Any]],
    classification: Mapping[str, Mapping[str, str | None]],
    feasibility: Mapping[str, Any],
    footprint: Mapping[str, Any],
) -> list[dict[str, str]]:
    blockers = []
    if not candidate_service:
        blockers.append(_blocker("intake", "candidate_service", "What service is being onboarded?"))
    if not operator_goal:
        blockers.append(_blocker("intake", "operator_goal", "What operator outcome should this service support?"))
    if not source_evidence:
        blockers.append(
            _blocker(
                "source_discovery",
                "source_evidence",
                "What upstream docs, package names, commands, local paths, or issue links prove the service shape?",
            )
        )
    for dimension, entry in classification.items():
        if entry["status"] != "known":
            blockers.append(
                _blocker(
                    "classification",
                    f"classification.{dimension}",
                    str(entry["next_evidence_step"]),
                )
            )
    if feasibility["verdict"] == "blocked" and feasibility["evidence_gaps"]:
        blockers.append(
            _blocker(
                "feasibility_review",
                "feasibility.evidence_gaps",
                "Resolve feasibility evidence gaps before implementation planning.",
            )
        )
    if not footprint["service_slug"]:
        blockers.append(_blocker("footprint_plan", "footprint_plan.service_slug", "Choose a stable service slug."))
    return blockers


def _questions(
    blockers: list[dict[str, str]],
    classification: Mapping[str, Mapping[str, str | None]],
    strategy: Mapping[str, Any],
) -> list[str]:
    if blockers:
        return _unique([blocker["question"] for blocker in blockers])
    questions = []
    paradigms = {strategy["primary_paradigm"], *strategy.get("secondary_validation_paradigms", [])}
    if "Package-provided bridge/transceiver" in paradigms:
        questions.append("Which stock bridge/transceiver command exposes the missing HTTP/SSE transport?")
    if strategy["primary_paradigm"] == "Project-scoped backend":
        questions.append("What project-local state does the backend read or write, and how will it be isolated?")
    if strategy["primary_paradigm"] == "Credential-scoped backend":
        questions.append("Which credential, account, tenant, token, or installation boundary defines this service binding?")
    if strategy["primary_paradigm"] == "Client-local or session-scoped backend":
        questions.append("Which client-local state, live session, caller identity, or process authority defines this service binding?")
    if classification["approval_type"]["value"] not in {"source_only", "local_ignored_state"}:
        questions.append("Which exact approval packet should unlock the next runtime or client surface?")
    return _unique(questions)


def _residual_risks(
    source: Mapping[str, Any],
    blockers: list[dict[str, str]],
    approvals: Mapping[str, Any],
) -> list[str]:
    risks = _string_list(source.get("residual_risks"))
    if blockers:
        risks.append("onboarding record has unresolved evidence or classification gaps")
    if approvals["approval_required"]:
        risks.append("runtime/client/global mutation remains blocked until exact approval is granted")
    if not risks:
        risks.append("runtime behavior is unproven until the selected validation surface is exercised")
    return _unique(risks)


def _next_steps(status: str, candidate_service: str | None, approvals: Mapping[str, Any]) -> list[str]:
    service = candidate_service or "candidate service"
    if status == "needs_user_input":
        return [f"answer the helper's next questions for {service}", "rerun the helper with the updated descriptor"]
    if status == "approval_required":
        return [
            f"post the onboarding record to the tracking issue for {service}",
            "obtain exact approval for the listed required approval types before runtime/client mutation",
        ]
    return [
        f"open or update a focused issue/PR for {service}",
        "keep the first implementation slice source-only unless a later approval gate is met",
    ]


def _source_evidence(source: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = source.get("source_evidence")
    if raw is None:
        raw = source.get("sources")
    evidence = []
    for item in _as_list(raw):
        if isinstance(item, Mapping):
            evidence.append(_redact_for_record(_json_compatible_copy(item)))
        elif isinstance(item, str):
            evidence.append({"type": "source", "ref": item})
    return evidence


def _redact_for_record(value: Any) -> Any:
    if isinstance(value, Mapping):
        output = {}
        for key, child in value.items():
            key_str = str(key)
            if redaction.classify_sensitive_key(key_str):
                output[key_str] = "<redacted>"
            else:
                output[key_str] = _redact_for_record(child)
        return output
    if isinstance(value, list):
        return [_redact_for_record(item) for item in value]
    if isinstance(value, str) and redaction.classify_sensitive_value(value):
        return "<redacted>"
    return copy.deepcopy(value)


def _validate_no_secret_leaks(record: Mapping[str, Any]) -> None:
    for path, value in _walk(record):
        key = str(path[-1]) if path else ""
        if redaction.classify_sensitive_key(key) and value != "<redacted>":
            raise ServiceOnboardingInputError(f"secret-bearing field is not redacted: {'.'.join(path)}")
        if isinstance(value, str) and redaction.classify_sensitive_value(value):
            raise ServiceOnboardingInputError(f"secret-like value is not redacted: {'.'.join(path)}")


def _walk(value: Any, path: tuple[str, ...] = ()) -> list[tuple[tuple[str, ...], Any]]:
    items = [(path, value)]
    if isinstance(value, Mapping):
        for key, child in value.items():
            items.extend(_walk(child, (*path, str(key))))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            items.extend(_walk(child, (*path, str(index))))
    return items


def _blocker(state: str, field: str, question: str) -> dict[str, str]:
    return {"state": state, "field": field, "question": question}


def _known_classifications(classification: Mapping[str, Mapping[str, str | None]]) -> dict[str, str]:
    return {dimension: str(entry["value"]) for dimension, entry in classification.items() if entry.get("value")}


def _json_compatible_copy(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_compatible_copy(child) for key, child in value.items()}
    if isinstance(value, tuple):
        return [_json_compatible_copy(item) for item in value]
    if isinstance(value, list):
        return [_json_compatible_copy(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if value is None or isinstance(value, str | bool | int | float):
        return copy.deepcopy(value)
    return str(value)


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in overlay.items():
        if (
            key in result
            and isinstance(result[key], Mapping)
            and isinstance(value, Mapping)
        ):
            result[key] = _deep_merge(dict(result[key]), dict(value))
        elif key == "source_evidence" and isinstance(result.get(key), list) and isinstance(value, list):
            result[key] = result[key] + value
        else:
            result[key] = copy.deepcopy(value)
    return result


def _mapping(value: Any) -> dict[str, Any]:
    return copy.deepcopy(dict(value)) if isinstance(value, Mapping) else {}


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _string_list(value: Any) -> list[str]:
    return [str(item) for item in _as_list(value) if item is not None and str(item)]


def _first_string(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _normalize_token(value: str | None) -> str | None:
    if value is None:
        return None
    return re.sub(r"[^a-z0-9_]+", "_", value.strip().lower()).strip("_")


def _slug(value: str | None) -> str | None:
    if not value:
        return None
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or None


def _unique(values: list[str] | tuple[str, ...]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _unique_blockers(values: list[dict[str, str]]) -> list[dict[str, str]]:
    seen = set()
    result = []
    for value in values:
        key = (value.get("state"), value.get("field"), value.get("question"))
        if key not in seen:
            seen.add(key)
            result.append(value)
    return result


def _unique_probe_layers(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    result = []
    for value in values:
        layer = _first_string(value.get("layer"))
        if layer and layer not in seen:
            seen.add(layer)
            result.append(value)
    return result


def _load_descriptor(path: str, *, case_name: str | None = None) -> dict[str, Any]:
    if path == "-":
        data = json.load(sys.stdin)
    else:
        with Path(path).open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    if case_name is None:
        return data
    for case in _as_list(data.get("cases") if isinstance(data, Mapping) else None):
        if isinstance(case, Mapping) and case.get("name") == case_name:
            descriptor = case.get("descriptor")
            if isinstance(descriptor, Mapping):
                return dict(descriptor)
            raise ServiceOnboardingInputError(f"case has no descriptor mapping: {case_name}")
    raise ServiceOnboardingInputError(f"case not found: {case_name}")


def _load_record(path: str) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, Mapping):
        raise ServiceOnboardingInputError("previous record must be a JSON object")
    return dict(data)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a no-mutation ContextForge service-onboarding record.")
    parser.add_argument("--descriptor", default=None, help="JSON descriptor path, or '-' for stdin")
    parser.add_argument("--case", default=None, help="Optional fixture case name containing a descriptor")
    parser.add_argument("--project-root", default=None)
    parser.add_argument("--issue", default=None)
    parser.add_argument("--previous-record", default=None, help="Optional prior onboarding record to resume from")
    parser.add_argument("--resume-session", default=None, help="Load the previous record from the local ignored session store")
    parser.add_argument("--session-status", default=None, help="Emit a compact no-mutation status summary for a saved session")
    parser.add_argument("--list-sessions", action="store_true", help="List compact no-mutation summaries for saved sessions")
    parser.add_argument("--session-template", default=None, help="Emit a no-mutation descriptor patch scaffold for a saved session")
    parser.add_argument("--session-id", default=None, help="Stable session id to include in dialogue metadata")
    parser.add_argument("--session-dir", default=str(DEFAULT_SESSION_DIR), help="Project-local ignored session directory under run/")
    parser.add_argument("--save-session", action="store_true", help="Persist the emitted record to the local ignored session store")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)

    if args.list_sessions:
        if (
            args.descriptor
            or args.case
            or args.previous_record
            or args.resume_session
            or args.session_status
            or args.session_template
            or args.save_session
        ):
            raise ServiceOnboardingInputError("--list-sessions cannot be combined with descriptor, resume, status, or write options")
        session_dir = resolve_session_dir(args.session_dir, project_root=args.project_root)
        print(
            json.dumps(
                list_session_statuses(session_dir),
                indent=2 if args.pretty else None,
                sort_keys=True,
            )
            + "\n",
            end="",
        )
        return 0

    if args.session_template:
        if args.descriptor or args.case or args.previous_record or args.resume_session or args.session_status or args.save_session:
            raise ServiceOnboardingInputError("--session-template cannot be combined with descriptor, resume, status, list, or write options")
        session_dir = resolve_session_dir(args.session_dir, project_root=args.project_root)
        path = session_record_path(session_dir, args.session_template)
        print(
            json.dumps(
                build_session_template(load_session_record(session_dir, args.session_template), session_record_path=str(path)),
                indent=2 if args.pretty else None,
                sort_keys=True,
            )
            + "\n",
            end="",
        )
        return 0

    if args.session_status:
        if args.descriptor or args.case or args.previous_record or args.resume_session or args.session_template or args.save_session:
            raise ServiceOnboardingInputError("--session-status cannot be combined with descriptor, resume, or write options")
        session_dir = resolve_session_dir(args.session_dir, project_root=args.project_root)
        path = session_record_path(session_dir, args.session_status)
        print(
            json.dumps(
                build_session_status(load_session_record(session_dir, args.session_status), session_record_path=str(path)),
                indent=2 if args.pretty else None,
                sort_keys=True,
            )
            + "\n",
            end="",
        )
        return 0

    if not args.descriptor:
        raise ServiceOnboardingInputError("--descriptor is required unless a saved-session readback mode is used")
    if args.previous_record and args.resume_session:
        raise ServiceOnboardingInputError("use either --previous-record or --resume-session, not both")

    session_dir = resolve_session_dir(args.session_dir, project_root=args.project_root)
    previous_record = None
    if args.previous_record:
        previous_record = _load_record(args.previous_record)
    elif args.resume_session:
        previous_record = load_session_record(session_dir, args.resume_session)

    resolved_session_id = (
        args.session_id
        or _first_string(_mapping(previous_record.get("dialogue_session") if previous_record else None).get("session_id"))
    )
    if args.save_session and not resolved_session_id:
        raise ServiceOnboardingInputError("--save-session requires --session-id or --resume-session with a saved session_id")
    planned_record_path = (
        str(session_record_path(session_dir, resolved_session_id))
        if args.save_session and resolved_session_id
        else None
    )
    record = build_onboarding_record(
        _load_descriptor(args.descriptor, case_name=args.case),
        project_root=args.project_root,
        issue=args.issue,
        previous_record=previous_record,
        session_id=args.session_id,
        storage_mode=LOCAL_SESSION_STORAGE_MODE if args.save_session else "stdout_only",
        write_persistence=args.save_session,
        session_record_path=planned_record_path,
    )
    if args.save_session:
        save_session_record(record, session_dir)
    print(json.dumps(record, indent=2 if args.pretty else None, sort_keys=True) + "\n", end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
