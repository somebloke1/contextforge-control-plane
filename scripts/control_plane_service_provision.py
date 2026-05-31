#!/usr/bin/env python3
"""Pure project-scoped service provision helpers for the control plane."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

import control_plane_authorization as authorization
import control_plane_contracts as contracts
import control_plane_project_state as project_state


SCHEMA_URI = "contextforge://control-plane/schemas/service-provision-plan/v1"
PROVISION_HELPER_VERSION = 1
SERVER_INSTANCES_DIR = "server-instances"
ENV_PLACEHOLDER_FILENAME = ".env.placeholder"
MANIFEST_FILENAME = "backend-manifest.json"
SYSTEMD_TARGET_SUFFIX = ".service"
OUTCOMES = frozenset(
    {
        "applied",
        "already_applied",
        "blocked",
        "needs_resume",
        "forward_repair",
        "rollback_by_approved_workflow",
        "manual_recovery",
        "fresh_approval_required",
    }
)
FORBIDDEN_OPERATION_CLASSES = frozenset(
    {
        "catalog_promotion",
        "user_global_client_trust",
        "user_global_config_write",
        "secret_value_write",
        "token_material_change",
        "network_exposure_change",
    }
)
FORBIDDEN_WRITE_PATHS = frozenset(
    {
        ".project/context_forge_state.json",
        ".project/context_forge_state.lock",
    }
)
SECRET_KEY_RE = re.compile(r"(api[_-]?key|auth[_-]?token|bearer|client[_-]?secret|credential|jwt|password|secret|token)", re.I)
SAFE_ENV_KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
SAFE_SLUG_RE = re.compile(r"[^a-z0-9_.-]+")


class ServiceProvisionInputError(ValueError):
    """Raised when a provision helper receives unsafe or incomplete inputs."""


def stable_digest(value: Any) -> str:
    """Return a stable sha256 digest for JSON-compatible provision data."""

    encoded = json.dumps(_json_compatible_copy(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def service_slug(service_binding: str) -> str:
    """Return a deterministic filesystem-safe slug for a service binding."""

    if not service_binding:
        raise ServiceProvisionInputError("service_binding is required")
    slug = SAFE_SLUG_RE.sub("-", service_binding.lower().replace(":", "-")).strip(".-")
    if not slug:
        raise ServiceProvisionInputError("service_binding did not produce a usable slug")
    return slug


def backend_home_path(project_root: str | Path, service_binding: str) -> str:
    """Return the project-scoped backend home path without creating it."""

    root = project_state.validate_project_root(project_root, require_workspace=True)
    return str(root / SERVER_INSTANCES_DIR / service_slug(service_binding))


def build_env_placeholder(
    *,
    required_env: Iterable[str],
    optional_env: Iterable[str] = (),
    header: str = "# ContextForge project-scoped service placeholder\n",
) -> dict[str, Any]:
    """Build ignored env placeholder content without accepting secret values."""

    required = _normalized_env_keys(required_env)
    optional = _normalized_env_keys(optional_env)
    overlap = sorted(set(required) & set(optional))
    if overlap:
        raise ServiceProvisionInputError(f"env keys cannot be both required and optional: {', '.join(overlap)}")

    lines = [header.rstrip("\n")]
    for key in required:
        lines.append(f"{key}=${{{key}}}")
    for key in optional:
        lines.append(f"# {key}=${{{key}}}")
    content = "\n".join(lines) + "\n"
    return {
        "kind": "env_placeholder",
        "required_env": required,
        "optional_env": optional,
        "content": content,
        "content_digest": stable_digest(content),
        "secret_values_included": False,
    }


def build_user_systemd_unit_spec(
    *,
    unit_name: str,
    description: str,
    exec_start: Sequence[str] | str,
    working_directory: str | Path,
    env_file: str | Path | None = None,
    after: Iterable[str] = ("network-online.target",),
    wants: Iterable[str] = (),
    restart: str = "on-failure",
) -> dict[str, Any]:
    """Build a user-systemd unit spec as data, not as a file write."""

    name = _unit_name(unit_name)
    command = [exec_start] if isinstance(exec_start, str) else [str(part) for part in exec_start]
    if not command or any(not part for part in command):
        raise ServiceProvisionInputError("exec_start must name a command")
    spec = {
        "kind": "user_systemd_unit",
        "unit_name": name,
        "description": str(description),
        "unit_scope": "user",
        "exec_start": command,
        "working_directory": str(Path(working_directory).expanduser().resolve(strict=False)),
        "env_file": str(Path(env_file).expanduser().resolve(strict=False)) if env_file else None,
        "after": sorted(str(item) for item in after),
        "wants": sorted(str(item) for item in wants),
        "restart": restart,
        "systemd_mutation_performed": False,
    }
    spec["content_digest"] = stable_digest(spec)
    return spec


def build_backend_manifest(
    *,
    project_root: str | Path,
    service_binding: str,
    backend_command: Sequence[str] | str,
    ports: Iterable[Mapping[str, Any]] = (),
    readiness_probes: Iterable[Mapping[str, Any]] = (),
    required_env: Iterable[str] = (),
    optional_env: Iterable[str] = (),
    upstream: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build sanitized backend manifest content for a project-scoped service."""

    root = project_state.validate_project_root(project_root, require_workspace=True)
    binding = str(service_binding)
    slug = service_slug(binding)
    command = [backend_command] if isinstance(backend_command, str) else [str(part) for part in backend_command]
    if not command:
        raise ServiceProvisionInputError("backend_command is required")
    manifest = {
        "schema_version": PROVISION_HELPER_VERSION,
        "kind": "project_scoped_backend_manifest",
        "service_binding": binding,
        "service_slug": slug,
        "project_root": str(root),
        "project_root_hash": project_state.project_root_hash(root),
        "backend_home": str(root / SERVER_INSTANCES_DIR / slug),
        "backend_command": command,
        "ports": [_port_spec(port) for port in ports],
        "readiness_probes": [_probe_spec(probe) for probe in readiness_probes],
        "env": {
            "required": _normalized_env_keys(required_env),
            "optional": _normalized_env_keys(optional_env),
            "placeholder_values_only": True,
        },
        "upstream": _redacted_mapping(upstream or {}),
        "non_actions": [
            "no catalog promotion",
            "no shared canonical service identity mutation",
            "no ContextForge registry mutation in W7-A helper",
            "no filesystem mutation",
            "no systemd mutation",
            "no network mutation",
        ],
    }
    manifest["content_digest"] = stable_digest(manifest)
    contracts.validate_redacted(manifest)
    return manifest


def build_service_provision_plan(
    *,
    project_root: str | Path,
    service_binding: str,
    plan_id: str,
    backend_command: Sequence[str] | str,
    owned_write_set: Iterable[str],
    stale_input_refs: Iterable[Mapping[str, Any]],
    consent_receipt_refs: Iterable[Mapping[str, Any]],
    verification_trace_refs: Iterable[Mapping[str, Any]],
    ports: Iterable[Mapping[str, Any]] = (),
    readiness_probes: Iterable[Mapping[str, Any]] = (),
    required_env: Iterable[str] = (),
    optional_env: Iterable[str] = (),
    systemd_description: str | None = None,
    policy_refs: Iterable[Mapping[str, Any]] = (),
    conformance_refs: Iterable[Mapping[str, Any]] = (),
    produced_artifact_refs: Iterable[Mapping[str, Any]] = (),
    upstream: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a schema-valid, non-mutating project-scoped provision plan."""

    root = project_state.validate_project_root(project_root, require_workspace=True)
    binding = str(service_binding)
    slug = service_slug(binding)
    backend_home = root / SERVER_INSTANCES_DIR / slug
    stale_refs = _refs("stale_input_refs", stale_input_refs, require=True)
    receipt_refs = _refs("consent_receipt_refs", consent_receipt_refs, require=True)
    trace_refs = _refs("verification_trace_refs", verification_trace_refs, require=True)
    policy_ref_list = _refs("policy_refs", policy_refs, require=False)
    conformance_ref_list = _refs("conformance_refs", conformance_refs, require=False)
    produced_refs = _refs("produced_artifact_refs", produced_artifact_refs, require=False) + trace_refs

    env_placeholder = build_env_placeholder(required_env=required_env, optional_env=optional_env)
    manifest = build_backend_manifest(
        project_root=root,
        service_binding=binding,
        backend_command=backend_command,
        ports=ports,
        readiness_probes=readiness_probes,
        required_env=required_env,
        optional_env=optional_env,
        upstream=upstream,
    )
    unit = build_user_systemd_unit_spec(
        unit_name=f"contextforge-{slug}{SYSTEMD_TARGET_SUFFIX}",
        description=systemd_description or f"ContextForge project service {binding}",
        exec_start=backend_command,
        working_directory=backend_home,
        env_file=backend_home / ENV_PLACEHOLDER_FILENAME,
    )
    write_set = _validate_owned_write_set(root, owned_write_set)
    expected_write_set = _expected_write_set(root, backend_home, unit)
    missing_expected = sorted(set(expected_write_set) - set(write_set))
    if missing_expected:
        raise ServiceProvisionInputError(f"owned_write_set missing required project-scoped targets: {', '.join(missing_expected)}")

    steps = [
        _step(
            "backend-home",
            "backend_home",
            "service_provision",
            "planned-to-unit_written",
            ["project root hash matches", "owned backend home target approved"],
            policy_ref_list,
            conformance_ref_list,
            [{"check": "no_catalog_promotion"}, {"check": "no_shared_canonical_identity_mutation"}],
        ),
        _step(
            "env-placeholder",
            "backend_home",
            "secret_placeholder_change",
            "planned-to-unit_written",
            ["env placeholder contains placeholders only"],
            policy_ref_list,
            conformance_ref_list,
            [{"check": "no_secret_value_write"}],
        ),
        _step(
            "backend-manifest",
            "backend_home",
            "service_provision",
            "planned-to-unit_written",
            ["backend manifest is redacted"],
            policy_ref_list,
            conformance_ref_list,
            [{"check": "no_catalog_promotion"}],
        ),
        _step(
            "user-systemd-unit-spec",
            "systemd",
            "service_provision",
            "planned-to-unit_written",
            ["unit spec is user scoped", "unit name is project scoped"],
            policy_ref_list,
            conformance_ref_list,
            [{"check": "no_system_systemd_target"}],
        ),
        _step(
            "port-reservation",
            "network",
            "service_provision",
            "unit_written-to-backend_ready",
            ["requested ports are available or already owned"],
            policy_ref_list,
            conformance_ref_list,
            [{"check": "no_remote_network_exposure"}],
        ),
        _step(
            "readiness-probes",
            "backend_home",
            "service_provision",
            "unit_enabled-to-backend_ready",
            ["backend readiness traces are present"],
            policy_ref_list,
            conformance_ref_list,
            [{"check": "readiness_probe_passed"}],
        ),
    ]

    plan = {
        "provision_plan_id": str(plan_id),
        "schema_uri": SCHEMA_URI,
        "service_binding": binding,
        "service_provision_steps": steps,
        "stale_inputs": stale_refs,
        "write_set": write_set,
        "consent_receipt_refs": receipt_refs,
        "expected_readback": [
            "backend_home_manifest_digest_matches",
            "env_placeholder_contains_no_secret_values",
            "user_systemd_unit_name_matches_project_service",
            "ports_available_or_already_owned",
            "readiness_trace_passed_before_backend_ready",
        ],
        "idempotency_mode": "idempotent",
        "compensation_repair_mode": "forward_repair",
        "produced_artifact_refs": produced_refs,
        "redaction_status": "redacted",
        "x_helper": "control_plane_service_provision",
        "x_project": {"root": str(root), "root_hash": project_state.project_root_hash(root)},
        "x_backend_home": str(backend_home),
        "x_desired_artifacts": {
            "backend_home": {"kind": "directory", "path": str(backend_home)},
            "env_placeholder": {
                "kind": "file",
                "path": str(backend_home / ENV_PLACEHOLDER_FILENAME),
                "placeholder_keys": {
                    "required": env_placeholder["required_env"],
                    "optional": env_placeholder["optional_env"],
                },
                "content_digest": env_placeholder["content_digest"],
            },
            "backend_manifest": {
                "kind": "file",
                "path": str(backend_home / MANIFEST_FILENAME),
                "content": manifest,
                "content_digest": manifest["content_digest"],
            },
            "user_systemd_unit": unit,
            "ports": manifest["ports"],
            "readiness_probes": manifest["readiness_probes"],
        },
        "x_forbidden_effects": sorted(
            [
                "catalog_promotion",
                "shared_canonical_service_identity_mutation",
                "contextforge_registry_mutation",
                "client_visible_binding_write",
                "filesystem_mutation_by_helper",
                "systemd_mutation_by_helper",
                "network_mutation_by_helper",
                "project_state_file_write",
            ]
        ),
    }
    _validate_no_catalog_promotion(plan)
    contracts.validate_artifact("service_provision_plan", plan)
    return plan


def validate_apply_prerequisites(
    provision_plan: Mapping[str, Any],
    *,
    project_root: str | Path,
    service_binding: str,
    owned_write_set: Iterable[str],
    stale_inputs_valid: bool,
    consent_receipts_valid: bool,
    verification_traces_valid: bool,
    authorization_decision: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate apply gates before classifying in-memory provision outcomes."""

    reasons: list[str] = []
    root = project_state.validate_project_root(project_root, require_workspace=True)
    if provision_plan.get("service_binding") != service_binding:
        reasons.append("service_binding does not match provision plan")
    if provision_plan.get("x_project", {}).get("root_hash") != project_state.project_root_hash(root):
        reasons.append("project root hash does not match provision plan")
    if not provision_plan.get("stale_inputs"):
        reasons.append("missing stale input refs")
    if not stale_inputs_valid:
        reasons.append("stale input check failed")
    if not provision_plan.get("consent_receipt_refs"):
        reasons.append("missing consent receipt refs")
    if not consent_receipts_valid:
        reasons.append("consent receipt verification failed")
    if not verification_traces_valid:
        reasons.append("verification trace refs are missing or invalid")
    if authorization_decision is not None and authorization_decision.get("decision") not in {"allow", "resume", "repair"}:
        reasons.extend(f"authorization: {reason}" for reason in authorization_decision.get("reasons", []))

    plan_write_set = set(str(item) for item in provision_plan.get("write_set", []))
    supplied_write_set = set(_validate_owned_write_set(root, owned_write_set))
    if plan_write_set != supplied_write_set:
        reasons.append("explicit owned write set does not match provision plan")
    _validate_no_catalog_promotion(provision_plan)

    if not stale_inputs_valid or not consent_receipts_valid:
        outcome = "fresh_approval_required"
    elif reasons:
        outcome = "blocked"
    else:
        outcome = "applied"
    return _outcome(outcome, reasons)


def classify_apply_outcomes(
    provision_plan: Mapping[str, Any],
    *,
    current_artifacts: Mapping[str, Any] | None = None,
    port_observations: Mapping[str, Mapping[str, Any]] | None = None,
    unit_observation: Mapping[str, Any] | None = None,
    readiness_observations: Mapping[str, Mapping[str, Any]] | None = None,
    prerequisites: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Classify pure apply/readback outcomes without performing mutations."""

    prerequisite = prerequisites or _outcome("applied", [])
    if prerequisite.get("outcome") in {"blocked", "fresh_approval_required"}:
        blocked = _outcome(str(prerequisite["outcome"]), prerequisite.get("reasons", []))
        return {"aggregate_outcome": blocked["outcome"], "component_outcomes": {"prerequisites": blocked}, "mutation_performed": False}

    desired = provision_plan.get("x_desired_artifacts")
    if not isinstance(desired, Mapping):
        return {"aggregate_outcome": "blocked", "component_outcomes": {"plan": _outcome("blocked", ["missing desired artifact metadata"])}, "mutation_performed": False}

    artifacts = current_artifacts or {}
    ports = port_observations or {}
    readiness = readiness_observations or {}
    components = {
        "backend_home": _artifact_outcome(desired.get("backend_home"), artifacts.get("backend_home")),
        "env_placeholder": _artifact_outcome(desired.get("env_placeholder"), artifacts.get("env_placeholder")),
        "backend_manifest": _artifact_outcome(desired.get("backend_manifest"), artifacts.get("backend_manifest")),
        "user_systemd_unit": _unit_outcome(desired.get("user_systemd_unit"), unit_observation or {}),
        "ports": _ports_outcome(desired.get("ports", []), ports),
        "readiness": _readiness_outcome(desired.get("readiness_probes", []), readiness),
    }
    return {
        "aggregate_outcome": _aggregate_outcome(components.values()),
        "component_outcomes": components,
        "mutation_performed": False,
    }


def authorize_service_provision(
    *,
    plan: Mapping[str, Any],
    actor: str,
    workflow_identity: str,
    source_client: str,
    source_client_auth_strength: str,
    target_clients: Iterable[str],
    project_root: str | Path,
    current_state: Mapping[str, Any] | None,
    service_binding: str,
    receipts: Iterable[Mapping[str, Any]],
    replay_intent: str = "initial_apply",
    now: str | None = None,
    **stale_snapshots: Any,
) -> dict[str, Any]:
    """Thin service-provision authorization wrapper over Wave 6 apply gates."""

    return authorization.authorize_operation(
        plan=plan,
        operation_class="service_provision",
        actor=actor,
        workflow_identity=workflow_identity,
        source_client=source_client,
        source_client_auth_strength=source_client_auth_strength,
        target_clients=target_clients,
        project_root=project_root,
        current_state=current_state,
        service_binding=service_binding,
        persistent_target="systemd",
        receipts=receipts,
        replay_intent=replay_intent,
        approval_workflow="project_init",
        now=now,
        **stale_snapshots,
    )


def _step(
    name: str,
    persistent_target: str,
    operation_class: str,
    transition: str,
    preconditions: Sequence[str],
    policy_refs: Sequence[Mapping[str, Any]],
    conformance_refs: Sequence[Mapping[str, Any]],
    negative_checks: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if operation_class in FORBIDDEN_OPERATION_CLASSES:
        raise ServiceProvisionInputError(f"{operation_class} is not allowed in service_provision")
    return {
        "step_id": name,
        "preconditions": list(preconditions),
        "persistent_target": persistent_target,
        "operation_class": operation_class,
        "expected_state_transition": transition,
        "required_policy_refs": _json_compatible_copy(list(policy_refs)),
        "required_conformance_refs": _json_compatible_copy(list(conformance_refs)),
        "negative_checks": _json_compatible_copy(list(negative_checks)),
    }


def _expected_write_set(root: Path, backend_home: Path, unit: Mapping[str, Any]) -> list[str]:
    return [
        str(backend_home),
        str(backend_home / ENV_PLACEHOLDER_FILENAME),
        str(backend_home / MANIFEST_FILENAME),
        f"user-systemd:{unit['unit_name']}",
    ]


def _validate_owned_write_set(root: Path, write_set: Iterable[str]) -> list[str]:
    entries = sorted(dict.fromkeys(str(item) for item in write_set))
    if not entries:
        raise ServiceProvisionInputError("explicit owned_write_set is required")
    for entry in entries:
        normalized = entry.removeprefix(str(root) + "/")
        if normalized in FORBIDDEN_WRITE_PATHS:
            raise ServiceProvisionInputError("service provision must not write .project/context_forge_state.json")
        if entry.startswith("user-systemd:"):
            unit = entry.split(":", 1)[1]
            if not unit.endswith(SYSTEMD_TARGET_SUFFIX) or "/" in unit:
                raise ServiceProvisionInputError(f"unsafe user-systemd unit target: {entry}")
            continue
        path = Path(entry).expanduser()
        if not path.is_absolute():
            path = root / path
        resolved = path.resolve(strict=False)
        if not project_state.is_relative_to(resolved, root):
            raise ServiceProvisionInputError(f"owned write target is outside project root: {entry}")
        if not project_state.is_relative_to(resolved, root / SERVER_INSTANCES_DIR):
            raise ServiceProvisionInputError(f"service provision writes must stay under server-instances: {entry}")
    return entries


def _artifact_outcome(desired: Any, current: Any) -> dict[str, Any]:
    if not isinstance(desired, Mapping):
        return _outcome("blocked", ["desired artifact metadata missing"])
    if current is None:
        return _outcome("applied", ["artifact can be created by caller-owned apply"])
    if isinstance(current, Mapping) and current.get("managed_by") not in {None, "contextforge-control-plane"}:
        return _outcome("blocked", ["unmanaged artifact conflict"])
    desired_digest = desired.get("content_digest") or stable_digest(desired)
    current_digest = current.get("content_digest") if isinstance(current, Mapping) else stable_digest(current)
    if current_digest == desired_digest:
        return _outcome("already_applied", [])
    if isinstance(current, Mapping) and current.get("interrupted") is True:
        return _outcome("needs_resume", ["interrupted owned artifact write"])
    return _outcome("forward_repair", ["owned artifact content drift"])


def _unit_outcome(desired: Any, observation: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(desired, Mapping):
        return _outcome("blocked", ["desired unit metadata missing"])
    if not observation:
        return _outcome("applied", ["unit spec can be emitted by caller-owned apply"])
    if observation.get("unit_name") != desired.get("unit_name"):
        return _outcome("rollback_by_approved_workflow", ["stale unit identity mismatch"])
    if observation.get("scope") not in {None, "user"}:
        return _outcome("manual_recovery", ["non-user systemd unit requires manual recovery"])
    if observation.get("content_digest") == desired.get("content_digest"):
        status = observation.get("status")
        if status in {"enabled", "active", "started"}:
            return _outcome("already_applied", [])
        return _outcome("needs_resume", ["unit spec exists but enable/start is incomplete"])
    if observation.get("managed_by") == "contextforge-control-plane":
        return _outcome("forward_repair", ["owned unit spec is stale"])
    return _outcome("rollback_by_approved_workflow", ["stale unmanaged unit conflict"])


def _ports_outcome(desired_ports: Any, observations: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    conflicts: list[str] = []
    already_owned: list[str] = []
    available: list[str] = []
    for port in desired_ports or []:
        if not isinstance(port, Mapping):
            continue
        key = str(port["port"])
        observed = observations.get(key, {})
        if observed.get("status") in {None, "available"}:
            available.append(key)
            continue
        if observed.get("owner") == port.get("owner"):
            already_owned.append(key)
        else:
            conflicts.append(key)
    if conflicts:
        return _outcome("fresh_approval_required", [f"port conflict requires fresh approval: {', '.join(conflicts)}"])
    if available:
        return _outcome("applied", [f"port available for caller-owned reservation: {', '.join(available)}"])
    if already_owned:
        return _outcome("already_applied", [f"port already reserved by this service: {', '.join(already_owned)}"])
    return _outcome("applied", [])


def _readiness_outcome(desired_probes: Any, observations: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    if not desired_probes:
        return _outcome("applied", ["no readiness probes requested"])
    failed: list[str] = []
    missing: list[str] = []
    for probe in desired_probes:
        if not isinstance(probe, Mapping):
            continue
        probe_id = str(probe["probe_id"])
        observed = observations.get(probe_id)
        if not observed:
            missing.append(probe_id)
        elif observed.get("status") != "passed":
            failed.append(probe_id)
    if failed:
        return _outcome("forward_repair", [f"readiness probe failed: {', '.join(failed)}"])
    if missing:
        return _outcome("needs_resume", [f"readiness probe missing: {', '.join(missing)}"])
    return _outcome("already_applied", [])


def _aggregate_outcome(outcomes: Iterable[Mapping[str, Any]]) -> str:
    priority = [
        "manual_recovery",
        "fresh_approval_required",
        "rollback_by_approved_workflow",
        "blocked",
        "forward_repair",
        "needs_resume",
        "applied",
        "already_applied",
    ]
    present = {str(item.get("outcome")) for item in outcomes}
    for outcome in priority:
        if outcome in present:
            return outcome
    return "blocked"


def _outcome(outcome: str, reasons: Iterable[str]) -> dict[str, Any]:
    if outcome not in OUTCOMES:
        raise ServiceProvisionInputError(f"unknown service provision outcome: {outcome}")
    return {"outcome": outcome, "reasons": list(dict.fromkeys(str(reason) for reason in reasons))}


def _port_spec(port: Mapping[str, Any]) -> dict[str, Any]:
    number = int(port["port"])
    if number < 1 or number > 65535:
        raise ServiceProvisionInputError(f"invalid port: {number}")
    bind = str(port.get("bind") or "127.0.0.1")
    if bind not in {"127.0.0.1", "::1", "localhost"}:
        raise ServiceProvisionInputError("remote network exposure requires a separate workflow")
    return {
        "port": number,
        "bind": bind,
        "protocol": str(port.get("protocol") or "tcp"),
        "purpose": str(port.get("purpose") or "backend"),
        "owner": str(port.get("owner") or "contextforge-control-plane"),
    }


def _probe_spec(probe: Mapping[str, Any]) -> dict[str, Any]:
    probe_id = str(probe.get("probe_id") or probe.get("id") or "")
    if not probe_id:
        raise ServiceProvisionInputError("readiness probe_id is required")
    return {
        "probe_id": probe_id,
        "probe_type": str(probe.get("probe_type") or probe.get("type") or "http"),
        "target": str(probe.get("target") or probe.get("url") or probe_id),
        "expected_status": str(probe.get("expected_status") or "passed"),
    }


def _unit_name(value: str) -> str:
    name = str(value)
    if "/" in name or not name.endswith(SYSTEMD_TARGET_SUFFIX):
        raise ServiceProvisionInputError("user systemd unit name must be a basename ending in .service")
    return name


def _normalized_env_keys(keys: Iterable[str]) -> list[str]:
    normalized = []
    for key in keys:
        text = str(key)
        if not SAFE_ENV_KEY_RE.match(text):
            raise ServiceProvisionInputError(f"invalid env placeholder key: {text}")
        if SECRET_KEY_RE.search(text):
            normalized.append(text)
        else:
            normalized.append(text)
    return sorted(dict.fromkeys(normalized))


def _refs(name: str, refs: Iterable[Mapping[str, Any]], *, require: bool) -> list[dict[str, Any]]:
    ref_list = [_json_compatible_copy(dict(ref)) for ref in refs]
    if require and not ref_list:
        raise ServiceProvisionInputError(f"{name} is required")
    for item in ref_list:
        for key in ("ref", "content_digest", "resolved_at"):
            if not item.get(key):
                raise ServiceProvisionInputError(f"{name} entries must include {key}")
    return ref_list


def _validate_no_catalog_promotion(plan: Mapping[str, Any]) -> None:
    encoded = json.dumps(_json_compatible_copy(plan), sort_keys=True)
    forbidden = ["catalog_promotion", "shared_canonical_service_identity_mutation"]
    if any(term in encoded for term in forbidden) and "x_forbidden_effects" not in plan:
        raise ServiceProvisionInputError("catalog-promotion terms must appear only as forbidden effects")
    for step in plan.get("service_provision_steps", []) or []:
        if isinstance(step, Mapping) and step.get("operation_class") in FORBIDDEN_OPERATION_CLASSES:
            raise ServiceProvisionInputError("service_provision cannot include catalog/global/secret-value operation classes")


def _redacted_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    redacted = _json_compatible_copy(dict(value))
    for path, child in _walk(redacted):
        key = path[-1] if path else ""
        if SECRET_KEY_RE.search(key) and child not in {None, "", "<redacted>", "redacted", "placeholder"}:
            parent = _parent_at(redacted, path[:-1])
            if isinstance(parent, dict):
                parent[key] = "<redacted>"
    contracts.validate_redacted(redacted)
    return redacted


def _parent_at(value: Any, path: tuple[str, ...]) -> Any:
    current = value
    for part in path:
        current = current[int(part)] if isinstance(current, list) else current[part]
    return current


def _walk(value: Any, path: tuple[str, ...] = ()) -> Iterable[tuple[tuple[str, ...], Any]]:
    yield path, value
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield from _walk(child, (*path, str(key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, (*path, str(index)))


def _json_compatible_copy(value: Any) -> Any:
    return json.loads(json.dumps(copy.deepcopy(value), sort_keys=True, default=str))
