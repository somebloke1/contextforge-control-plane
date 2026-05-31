#!/usr/bin/env python3
"""Generic project-scoped service adapter plans for the control plane.

The helpers in this module are intentionally pure.  They build adapter specs
and planning records that can be consumed by later provision/binding layers,
but they never write backend homes, ContextForge state, client configs, trust
state, server-instances, or project state.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import control_plane_language_profiles as language_profiles
import control_plane_project_state as project_state
import control_plane_tool_policy as tool_policy


SCHEMA_URI = "contextforge://control-plane/schemas/project-scoped-adapter-plan/v1"
SPEC_SCHEMA_URI = "contextforge://control-plane/schemas/project-scoped-adapter-spec/v1"
HELPER_VERSION = 1
DEFAULT_GENERATED_AT = "2026-05-30T20:21:54Z"
PROJECT_SCOPED_INSTANTIATION_CLASSES = frozenset({"instance_per_project", "project_scoped_shared_backend"})
CANONICAL_IDENTITY_SOURCES = frozenset({"rfc_seed", "catalog", "manifest", "contextforge_registry"})
CLIENT_DERIVED_IDENTITY_SOURCES = frozenset({"client_config", "codex_config", "claude_config", "gemini_config", "opencode_config"})
PROJECT_SCOPED_DECISIONS = frozenset({"accepted", "declined", "disabled", "deferred", "unasked"})
REQUIRED_CONSENT_CLASSES = ("service_provision", "project_local_config_write")
REQUIRED_TRACE_LAYERS = ("backend", "contextforge_gateway", "virtual_server", "tool_policy", "target_client", "redaction")
SAFE_SLUG_RE = re.compile(r"[^a-z0-9_.-]+")


class ProjectAdapterInputError(ValueError):
    """Raised when adapter inputs are malformed."""


def stable_digest(value: Any) -> str:
    """Return a stable sha256 digest for JSON-compatible adapter data."""

    encoded = json.dumps(_json_copy(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def build_project_identity(project_root: str | Path, *, project_name: str | None = None) -> dict[str, Any]:
    """Build canonical project identity without mutating project state."""

    root = project_state.validate_project_root(project_root, require_workspace=True)
    return {
        "root": str(root),
        "root_hash": project_state.project_root_hash(root),
        "name": project_name or root.name,
        "identity_source": "canonical_realpath_plus_uid",
    }


def build_serena_adapter_spec(
    *,
    project_root: str | Path,
    selected_language_profile_id: str | None,
    target_client: str = "codex",
    identity_source: str = "rfc_seed",
) -> dict[str, Any]:
    """Build the Serena adapter spec using language-profile references only."""

    project = build_project_identity(project_root)
    service_binding = "serena:project"
    profile = _language_profile_requirement(
        required=True,
        selected_language_profile_id=selected_language_profile_id,
        reason="Serena requires a selected project language profile for LSP/tooling verification.",
    )
    return _adapter_spec(
        adapter_id="serena",
        service_family="serena",
        canonical_service=f"serena-{_slug(project['name'])}",
        service_binding=service_binding,
        display_name="Serena project code intelligence",
        project=project,
        identity_source=identity_source,
        instantiation_class="instance_per_project",
        backend_command=["serena", "start-mcp-server", "--project", project["root"]],
        backend_kind="stdio_mcp_project_backend",
        target_client=target_client,
        language_requirement=profile,
        tools=[
            _tool(
                "serena-read-file",
                service_binding=service_binding,
                original_name="read_file",
                exposed_name="serena__read_file",
                risk_classes=["read_only"],
                scope_impacts=["project_bound_read"],
                target_client=target_client,
            ),
            _tool(
                "serena-find-symbol",
                service_binding=service_binding,
                original_name="find_symbol",
                exposed_name="serena__find_symbol",
                risk_classes=["read_only"],
                scope_impacts=["project_bound_read"],
                target_client=target_client,
            ),
            _tool(
                "serena-activate-project",
                service_binding=service_binding,
                original_name="activate_project",
                exposed_name="serena__activate_project",
                risk_classes=["scope_changing"],
                scope_impacts=["active_project", "workspace_root", "backend_operating_scope"],
                target_client=target_client,
                filter_reason="scope-changing active project mutation is not exposed through project virtual servers",
                approval_gates=["service_provision"],
            ),
        ],
        required_env=[],
        optional_env=["SERENA_LOG_LEVEL"],
        ports=[],
        readiness_probes=[
            {"probe_id": "serena-mcp-health", "probe_type": "mcp", "target": "stdio initialize/list_tools"}
        ],
        recovery_behaviors=["resume", "forward_repair", "fresh_approval_required", "manual_recovery"],
    )


def build_project_inspector_adapter_spec(
    *,
    project_root: str | Path,
    selected_language_profile_id: str | None = None,
    target_client: str = "codex",
    language_profile_required: bool = False,
    identity_source: str = "rfc_seed",
) -> dict[str, Any]:
    """Build the RFC-seeded read-only project-inspector adapter spec."""

    project = build_project_identity(project_root)
    service_binding = "project-inspector:project"
    return _adapter_spec(
        adapter_id="project-inspector",
        service_family="project-inspector",
        canonical_service=f"project-inspector-{_slug(project['name'])}",
        service_binding=service_binding,
        display_name="Project inspector",
        project=project,
        identity_source=identity_source,
        instantiation_class="instance_per_project",
        backend_command=["contextforge-project-inspector", "--project-root", project["root"]],
        backend_kind="read_only_project_mcp_backend",
        target_client=target_client,
        language_requirement=_language_profile_requirement(
            required=language_profile_required,
            selected_language_profile_id=selected_language_profile_id,
            reason="Project inspector can optionally consume the selected profile for read-only language facts.",
        ),
        tools=[
            _tool(
                "project-inspector-root",
                service_binding=service_binding,
                original_name="get_project_identity",
                exposed_name="project_inspector__get_project_identity",
                risk_classes=["read_only"],
                scope_impacts=["project_bound_read"],
                target_client=target_client,
            ),
            _tool(
                "project-inspector-languages",
                service_binding=service_binding,
                original_name="get_detected_languages",
                exposed_name="project_inspector__get_detected_languages",
                risk_classes=["read_only"],
                scope_impacts=["project_bound_read"],
                target_client=target_client,
            ),
        ],
        required_env=[],
        optional_env=[],
        ports=[],
        readiness_probes=[
            {"probe_id": "project-inspector-list-tools", "probe_type": "mcp", "target": "stdio initialize/list_tools"}
        ],
        recovery_behaviors=["resume", "forward_repair", "manual_recovery"],
    )


def compile_adapter_tool_policy(
    spec: Mapping[str, Any],
    *,
    expected_gateway_revision: str,
    current_gateway_revision: str,
    expected_target_client_digest: str,
    current_target_client_digest: str,
    compiled_at: str = DEFAULT_GENERATED_AT,
) -> dict[str, Any]:
    """Compile a spec's tool fixtures through the generic semantic policy compiler."""

    service_binding = _require_string(spec, "service_binding")
    return tool_policy.compile_tool_policy(
        service_binding=service_binding,
        virtual_server_id=str(spec.get("virtual_server", {}).get("name") or f"{service_binding}-virtual"),
        target_client=str(spec.get("client_binding", {}).get("target_client") or "codex"),
        tools=list(spec.get("tool_policy", {}).get("tool_fixtures") or []),
        expected_gateway_revision=expected_gateway_revision,
        current_gateway_revision=current_gateway_revision,
        expected_target_client_digest=expected_target_client_digest,
        current_target_client_digest=current_target_client_digest,
        compiled_at=compiled_at,
    )


def plan_project_scoped_adapter(
    spec: Mapping[str, Any],
    *,
    project_service_decision: str,
    semantic_tool_policy: Mapping[str, Any] | None,
    conformance_result: Mapping[str, Any] | None,
    consent_receipt_refs: Sequence[Mapping[str, Any]],
    verification_trace_refs: Sequence[Mapping[str, Any]],
    generated_at: str = DEFAULT_GENERATED_AT,
) -> dict[str, Any]:
    """Build a non-mutating adapter plan and fail closed on missing proof gates."""

    if project_service_decision not in PROJECT_SCOPED_DECISIONS:
        raise ProjectAdapterInputError(f"unknown project service decision: {project_service_decision}")
    spec_copy = _json_copy(spec)
    service_binding = _require_string(spec_copy, "service_binding")
    blockers: list[dict[str, Any]] = []
    open_items: list[dict[str, Any]] = []

    if project_service_decision == "declined":
        blocker = _blocker("service_declined", f"{service_binding} is explicitly declined for this project.")
        blockers.append(blocker)
        open_items.append(_open_item("service_declined", "blocking", blocker["message"], {"service_binding": service_binding}))
        return _adapter_plan(
            spec_copy,
            generated_at=generated_at,
            status="blocked_declined",
            decision="declined",
            blockers=blockers,
            open_items=open_items,
            semantic_tool_policy=None,
            conformance_result=None,
            consent_receipt_refs=[],
            verification_trace_refs=[],
            mutating_sections_enabled=False,
        )

    blockers.extend(_identity_blockers(spec_copy))
    blockers.extend(_language_blockers(spec_copy))
    blockers.extend(_tool_policy_blockers(spec_copy, semantic_tool_policy))
    blockers.extend(_conformance_blockers(spec_copy, conformance_result))
    blockers.extend(_receipt_blockers(consent_receipt_refs))
    blockers.extend(_trace_blockers(verification_trace_refs))
    for blocker in blockers:
        open_items.append(_open_item(blocker["type"], "blocking", blocker["message"], {"service_binding": service_binding}))

    status = "planned_non_mutating" if project_service_decision == "accepted" and not blockers else "blocked"
    return _adapter_plan(
        spec_copy,
        generated_at=generated_at,
        status=status,
        decision=project_service_decision,
        blockers=_dedupe_blockers(blockers),
        open_items=_dedupe_open_items(open_items),
        semantic_tool_policy=semantic_tool_policy,
        conformance_result=conformance_result,
        consent_receipt_refs=consent_receipt_refs,
        verification_trace_refs=verification_trace_refs,
        mutating_sections_enabled=not blockers and project_service_decision == "accepted",
    )


def _adapter_spec(
    *,
    adapter_id: str,
    service_family: str,
    canonical_service: str,
    service_binding: str,
    display_name: str,
    project: Mapping[str, Any],
    identity_source: str,
    instantiation_class: str,
    backend_command: Sequence[str],
    backend_kind: str,
    target_client: str,
    language_requirement: Mapping[str, Any],
    tools: Sequence[Mapping[str, Any]],
    required_env: Sequence[str],
    optional_env: Sequence[str],
    ports: Sequence[Mapping[str, Any]],
    readiness_probes: Sequence[Mapping[str, Any]],
    recovery_behaviors: Sequence[str],
) -> dict[str, Any]:
    if instantiation_class not in PROJECT_SCOPED_INSTANTIATION_CLASSES:
        raise ProjectAdapterInputError(f"unsupported project-scoped instantiation class: {instantiation_class}")
    backend_slug = _slug(service_binding.replace(":", "-"))
    virtual_server_name = f"{backend_slug}-{project['root_hash'][:12]}"
    spec = {
        "schema_uri": SPEC_SCHEMA_URI,
        "helper_version": HELPER_VERSION,
        "adapter_id": adapter_id,
        "display_name": display_name,
        "service_family": service_family,
        "canonical_service": canonical_service,
        "service_binding": service_binding,
        "instantiation_class": instantiation_class,
        "identity": {
            "source": identity_source,
            "canonical_service": canonical_service,
            "client_configs_are_discovery_only": True,
            "client_derived_identity_allowed": False,
        },
        "project_identity": dict(project),
        "backend_instance": {
            "kind": backend_kind,
            "slug": backend_slug,
            "home": f"{project['root']}/server-instances/{backend_slug}",
            "command": list(backend_command),
            "required_env": list(required_env),
            "optional_env": list(optional_env),
            "ports": _json_copy(list(ports)),
            "readiness_probes": _json_copy(list(readiness_probes)),
        },
        "contextforge_registration": {
            "gateway_name": f"{backend_slug}-gateway",
            "upstream_transport": "stdio",
            "registration_path": "contextforge_api_or_admin_behavior",
            "native_transport_preserved": True,
        },
        "virtual_server": {
            "name": virtual_server_name,
            "scope": "project",
            "tool_association_source": "compiled_semantic_tool_policy",
            "globally_exposed": False,
        },
        "tool_policy": {
            "compiler": "control_plane_tool_policy",
            "scope_changing_tools_are_semantic_exclusions": True,
            "tool_fixtures": _json_copy(list(tools)),
        },
        "client_binding": {
            "target_client": target_client,
            "scope": "project_local",
            "requires_conformance_pack": True,
            "trust_mutation_bundled": False,
        },
        "language_requirement": dict(language_requirement),
        "consent_requirements": list(REQUIRED_CONSENT_CLASSES),
        "verification_trace_requirements": list(REQUIRED_TRACE_LAYERS),
        "recovery_behavior": list(recovery_behaviors),
        "non_actions": [
            "does not provision backend",
            "does not call ContextForge APIs",
            "does not write client config",
            "does not grant trust",
            "does not write project state",
            "does not mutate server-instances",
        ],
    }
    spec["spec_digest"] = stable_digest(spec)
    return spec


def _language_profile_requirement(*, required: bool, selected_language_profile_id: str | None, reason: str) -> dict[str, Any]:
    if not required and not selected_language_profile_id:
        return {
            "required": False,
            "selected_language_profile_id": None,
            "language_profile_ref": None,
            "consumed_from": "control_plane_language_profiles",
            "service_local_language_policy": False,
            "reason": reason,
        }
    if not selected_language_profile_id:
        return {
            "required": required,
            "selected_language_profile_id": None,
            "language_profile_ref": None,
            "consumed_from": "control_plane_language_profiles",
            "service_local_language_policy": False,
            "reason": reason,
        }
    profile = language_profiles.get_language_profile(selected_language_profile_id)
    return {
        "required": required,
        "selected_language_profile_id": profile["language_id"],
        "language_profile_ref": {
            "ref": language_profiles.language_profile_uri(profile["language_id"]),
            "content_digest": language_profiles.stable_digest(profile),
        },
        "profile_display_name": profile["display_name"],
        "service_requirements": _json_copy(profile["service_requirements"]),
        "baseline_probes": _json_copy(profile["baseline_probes"]),
        "verification_evidence_expectations": _json_copy(profile["verification_evidence_expectations"]),
        "probe_artifact_policy": _json_copy(profile["probe_artifact_policy"]),
        "backend_options": _json_copy(profile["backend_options"]),
        "install_policy": _json_copy(profile["install_policy"]),
        "consumed_from": "control_plane_language_profiles",
        "service_local_language_policy": False,
        "reason": reason,
    }


def _adapter_plan(
    spec: Mapping[str, Any],
    *,
    generated_at: str,
    status: str,
    decision: str,
    blockers: Sequence[Mapping[str, Any]],
    open_items: Sequence[Mapping[str, Any]],
    semantic_tool_policy: Mapping[str, Any] | None,
    conformance_result: Mapping[str, Any] | None,
    consent_receipt_refs: Sequence[Mapping[str, Any]],
    verification_trace_refs: Sequence[Mapping[str, Any]],
    mutating_sections_enabled: bool,
) -> dict[str, Any]:
    service_binding = str(spec["service_binding"])
    mutating_sections = {
        "backend_instance": _json_copy(spec.get("backend_instance")),
        "contextforge_registration": _json_copy(spec.get("contextforge_registration")),
        "virtual_server": _json_copy(spec.get("virtual_server")),
        "client_binding": _json_copy(spec.get("client_binding")),
        "server_instance_home": spec.get("backend_instance", {}).get("home"),
        "project_state_record": {
            "service_binding": service_binding,
            "canonical_service": spec.get("canonical_service"),
            "virtual_server_name": spec.get("virtual_server", {}).get("name"),
        },
    }
    plan = {
        "schema_uri": SCHEMA_URI,
        "helper_version": HELPER_VERSION,
        "planner": "control_plane_project_adapter",
        "status": status,
        "project_service_decision": decision,
        "mutation_allowed": False,
        "mutation_performed": False,
        "service_binding": service_binding,
        "service_family": spec.get("service_family"),
        "canonical_service": spec.get("canonical_service"),
        "project_identity": _json_copy(spec.get("project_identity")),
        "adapter_spec_ref": {
            "ref": f"contextforge://control-plane/project-adapters/{spec.get('adapter_id')}/v1",
            "content_digest": stable_digest(spec),
            "resolved_at": generated_at,
        },
        "adapter_spec": _json_copy(spec),
        "language_requirement": _json_copy(spec.get("language_requirement")),
        "tool_policy": {
            "required": True,
            "semantic_tool_policy": _json_copy(semantic_tool_policy) if semantic_tool_policy else None,
        },
        "client_binding_gate_inputs": {
            "conformance_result": _json_copy(conformance_result) if conformance_result else None,
            "consent_receipt_refs": _json_copy(list(consent_receipt_refs)),
            "verification_trace_refs": _json_copy(list(verification_trace_refs)),
        },
        "planned_sections": mutating_sections if mutating_sections_enabled else {},
        "declined_preservation": {
            "preserves_decline": decision == "declined",
            "no_backend_contextforge_client_trust_server_instance_or_project_mutation": decision == "declined",
        },
        "blockers": _json_copy(list(blockers)),
        "open_items": _json_copy(list(open_items)),
        "recovery_behavior": _json_copy(spec.get("recovery_behavior") or []),
        "non_actions": [
            "does not provision Serena or any project-scoped service",
            "does not call ContextForge APIs or systemd",
            "does not write backend homes, client configs, trust files, server-instances, or .project",
            "client configs are discovery sources, not service identities",
        ],
        "generated_at": generated_at,
        "plan_digest": "",
    }
    plan["plan_digest"] = stable_digest({key: value for key, value in plan.items() if key != "plan_digest"})
    return plan


def _identity_blockers(spec: Mapping[str, Any]) -> list[dict[str, Any]]:
    identity = spec.get("identity")
    source = str(identity.get("source") if isinstance(identity, Mapping) else "")
    blockers: list[dict[str, Any]] = []
    if source in CLIENT_DERIVED_IDENTITY_SOURCES:
        blockers.append(_blocker("client_derived_identity", "client configs are discovery evidence only and cannot define canonical service identity."))
    elif source not in CANONICAL_IDENTITY_SOURCES:
        blockers.append(_blocker("canonical_identity_required", "adapter identity must come from an RFC seed, catalog, manifest, or ContextForge registry."))
    if not spec.get("canonical_service") or not spec.get("service_family") or not spec.get("service_binding"):
        blockers.append(_blocker("canonical_identity_required", "service_family, canonical_service, and service_binding are required."))
    return blockers


def _language_blockers(spec: Mapping[str, Any]) -> list[dict[str, Any]]:
    requirement = spec.get("language_requirement")
    if not isinstance(requirement, Mapping):
        return [_blocker("language_requirement_missing", "adapter must declare language-profile consumption requirements.")]
    if requirement.get("service_local_language_policy") is not False:
        return [_blocker("service_local_language_policy_forbidden", "language policy must be consumed from control_plane_language_profiles.")]
    if requirement.get("required") and not requirement.get("language_profile_ref"):
        return [_blocker("language_profile_missing", "language-dependent adapter requires a selected language profile ref.")]
    return []


def _tool_policy_blockers(spec: Mapping[str, Any], policy: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if not policy:
        return [_blocker("missing_semantic_tool_policy", "compiled semantic tool policy is required.")]
    blockers: list[dict[str, Any]] = []
    if policy.get("service_binding") != spec.get("service_binding"):
        blockers.append(_blocker("policy_service_binding_mismatch", "semantic policy service binding does not match adapter."))
    if policy.get("x_status") != "compiled":
        blockers.append(_blocker("semantic_tool_policy_not_compiled", "semantic tool policy must compile without blockers."))
    excluded_tools = list(policy.get("x_excluded_tools") or [])
    if excluded_tools and not policy.get("negative_checks"):
        blockers.append(_blocker("missing_negative_checks", "semantic policy must include negative checks for excluded tools."))
    for blocker in policy.get("x_blockers") or []:
        blockers.append(_blocker(str(blocker.get("type") or "tool_policy_blocker"), str(blocker.get("message") or "tool policy blocker")))
    return blockers


def _conformance_blockers(spec: Mapping[str, Any], conformance: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if not conformance:
        return [_blocker("missing_conformance", "passing client adapter conformance is required.")]
    blockers: list[dict[str, Any]] = []
    target_client = str(spec.get("client_binding", {}).get("target_client") or "")
    if conformance.get("status") != "passing_conformance" or conformance.get("decision") != "allow_target_client_proof":
        blockers.append(_blocker("failed_conformance", "target client conformance has not passed."))
    if conformance.get("client_name") and conformance.get("client_name") != target_client:
        blockers.append(_blocker("target_client_mismatch", "conformance client does not match adapter target client."))
    if conformance.get("service_binding") and conformance.get("service_binding") != spec.get("service_binding"):
        blockers.append(_blocker("conformance_service_binding_mismatch", "conformance service binding does not match adapter."))
    return blockers


def _receipt_blockers(refs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    classes = {str(item.get("consent_class") or item.get("x_consent_class") or "") for item in refs}
    blockers = []
    for required in REQUIRED_CONSENT_CLASSES:
        if required not in classes:
            blockers.append(_blocker(f"missing_{required}_receipt", f"{required} consent receipt ref is required."))
    return blockers


def _trace_blockers(refs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    layers = {str(item.get("layer") or item.get("x_verification_layer") or "") for item in refs if item.get("result") == "passed"}
    missing = sorted(set(REQUIRED_TRACE_LAYERS) - layers)
    if missing:
        return [_blocker("trace_missing", "required verification trace refs are missing.", missing=missing)]
    return []


def _tool(
    tool_id: str,
    *,
    service_binding: str,
    original_name: str,
    exposed_name: str,
    risk_classes: Sequence[str],
    scope_impacts: Sequence[str],
    target_client: str,
    filter_reason: str | None = None,
    approval_gates: Sequence[str] = (),
) -> dict[str, Any]:
    return {
        "tool_id": tool_id,
        "service_binding": service_binding,
        "original_name": original_name,
        "exposed_name": exposed_name,
        "risk_classes": list(risk_classes),
        "semantic_risk_classes": list(risk_classes),
        "scope_impacts": list(scope_impacts),
        "target_clients": [target_client],
        "filter_reason": filter_reason,
        "approval_gates": list(approval_gates),
    }


def _blocker(blocker_type: str, message: str, **extra: Any) -> dict[str, Any]:
    result = {"type": blocker_type, "message": message}
    result.update(extra)
    return result


def _open_item(item_type: str, severity: str, message: str, evidence: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return {"type": item_type, "severity": severity, "message": message, "evidence": _json_copy(evidence or {})}


def _dedupe_blockers(blockers: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    result = []
    for blocker in blockers:
        key = (str(blocker.get("type")), str(blocker.get("message")), json.dumps(_json_copy(blocker.get("missing")), sort_keys=True))
        if key in seen:
            continue
        seen.add(key)
        result.append(_json_copy(blocker))
    return result


def _dedupe_open_items(items: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    result = []
    for item in items:
        key = (str(item.get("type")), str(item.get("message")))
        if key in seen:
            continue
        seen.add(key)
        result.append(_json_copy(item))
    return result


def _require_string(data: Mapping[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise ProjectAdapterInputError(f"{key} is required")
    return value


def _slug(value: str) -> str:
    slug = SAFE_SLUG_RE.sub("-", value.lower().replace(":", "-")).strip(".-")
    if not slug:
        raise ProjectAdapterInputError("value did not produce a usable slug")
    return slug


def _json_copy(value: Any) -> Any:
    return copy.deepcopy(value)
