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
    blockers = _blockers(candidate_service, operator_goal, source_evidence, classification, feasibility, footprint)
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
    parser.add_argument("--descriptor", required=True, help="JSON descriptor path, or '-' for stdin")
    parser.add_argument("--case", default=None, help="Optional fixture case name containing a descriptor")
    parser.add_argument("--project-root", default=None)
    parser.add_argument("--issue", default=None)
    parser.add_argument("--previous-record", default=None, help="Optional prior onboarding record to resume from")
    parser.add_argument("--resume-session", default=None, help="Load the previous record from the local ignored session store")
    parser.add_argument("--session-id", default=None, help="Stable session id to include in dialogue metadata")
    parser.add_argument("--session-dir", default=str(DEFAULT_SESSION_DIR), help="Project-local ignored session directory under run/")
    parser.add_argument("--save-session", action="store_true", help="Persist the emitted record to the local ignored session store")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)

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
