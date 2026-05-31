#!/usr/bin/env python3
"""Read-only control-plane view models for ContextForge project setup."""

from __future__ import annotations

import copy
import json
import re
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Any

import control_plane_project_state as project_state


REPO_ROOT = Path(__file__).resolve().parents[1]
INSTANCE_ROOT = REPO_ROOT / "server-instances"
READ_MODEL_VERSION = 1

_UNSET = object()
_REDACTED = "<redacted>"
SECRET_KEY_RE = re.compile(
    r"(api[_-]?key|auth(orization)?|auth[_-]?token|bearer|client[_-]?secret|credential|jwt|password|"
    r"private[_-]?key|refresh[_-]?token|secret|session[_-]?token|token)",
    re.IGNORECASE,
)
SECRET_VALUE_RE = re.compile(
    r"(-----BEGIN [A-Z ]*PRIVATE KEY-----|"
    r"\bBearer\s+[A-Za-z0-9._~+/=-]{12,}|"
    r"\b(?:sk|pk|ghp|gho|github_pat|xox[baprs]|ya29)[_-][A-Za-z0-9._-]{12,}|"
    r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}|"
    r"(?i:\b(?:api[_-]?key|token|password|secret)\s*=\s*[^\\s'\"<>]+))"
)


def redact_secrets(value: Any) -> Any:
    """Return a JSON-compatible copy with secret-looking fields redacted."""

    return _redact(value)


def get_project_context(
    project_root: str | Path,
    *,
    state: Mapping[str, Any] | None | object = _UNSET,
    require_workspace: bool = True,
    redactor: Callable[[Any], Any] = redact_secrets,
) -> dict[str, Any]:
    """Return a non-mutating project context view.

    Missing state is represented as absent and ``UNINITIALIZED``. This function
    deliberately calls ``load_state`` instead of ``read_or_default`` so it never
    creates, writes, or synthesizes durable project state.
    """

    root = project_state.validate_project_root(project_root, require_workspace=require_workspace)
    state_data = _resolve_state(root, state=state, require_workspace=require_workspace)
    state_present = state_data is not None
    artifact_refs = _artifact_refs(state_data)
    service_records = _state_services(state_data)

    return {
        "schema_version": READ_MODEL_VERSION,
        "surface": "get_project_context",
        "project": {
            "root": str(root),
            "root_hash": project_state.project_root_hash(root),
            "name": root.name,
        },
        "root_safety": {
            "accepted": True,
            "require_workspace": require_workspace,
            "denied_roots_checked": True,
        },
        "state_present": state_present,
        "state_status": str(state_data.get("status", "uninitialized")).upper() if state_data else "UNINITIALIZED",
        "state": redactor(state_data) if state_present else None,
        "related_instances": redactor(_related_instances(state_data)),
        "target_clients": _target_clients(state_data),
        "trust_visibility": redactor((state_data or {}).get("client_trust", {})),
        "artifact_refs": redactor(artifact_refs),
        "contract_card_refs": redactor(artifact_refs.get("contract_cards", [])),
        "capability_capsule_refs": redactor(artifact_refs.get("capability_capsules", [])),
        "semantic_tool_policy_refs": redactor(artifact_refs.get("semantic_tool_policies", [])),
        "latest_consent_receipts": redactor(artifact_refs.get("consent_receipts", [])),
        "latest_verification_traces": redactor(artifact_refs.get("verification_traces", [])),
        "services": redactor(service_records),
        "open_items": redactor((state_data or {}).get("open_items", [])),
        "migration": redactor((state_data or {}).get("migration", {})),
        "drift": redactor((state_data or {}).get("drift", {})),
        "trust_broker_state": redactor((state_data or {}).get("x_trust_broker", None)),
        "governance_reconciliation_warnings": redactor(_governance_warnings(state_data)),
    }


def list_catalog(
    *,
    catalog: Mapping[str, Any] | None = None,
    manifest_paths: Iterable[str | Path] | None = None,
    instance_root: str | Path = INSTANCE_ROOT,
    redactor: Callable[[Any], Any] = redact_secrets,
) -> dict[str, Any]:
    """Return a redacted host catalog summary from manifests or injected data."""

    raw_services = _catalog_services(catalog, manifest_paths=manifest_paths, instance_root=instance_root)
    services = [
        _service_summary_from_manifest(manifest, source_ref=source_ref, redactor=redactor)
        for manifest, source_ref in raw_services
    ]
    candidates = [_candidate_summary(candidate, redactor=redactor) for candidate in _catalog_list(catalog, "candidates")]

    return {
        "schema_version": READ_MODEL_VERSION,
        "surface": "list_catalog",
        "services": sorted(services, key=lambda item: (item.get("canonical_service") or "", item.get("instance_slug") or "")),
        "candidates": sorted(candidates, key=lambda item: item.get("candidate_name") or ""),
        "client_config_sources": redactor(_catalog_list(catalog, "client_config_sources")),
        "client_config_entries": redactor(_catalog_list(catalog, "client_config_entries")),
        "language_profiles": redactor(_catalog_list(catalog, "language_profiles")),
        "contract_card_refs": redactor(_catalog_refs(catalog, "contract_card_refs", "contract_cards")),
        "capability_capsule_refs": redactor(_catalog_refs(catalog, "capability_capsule_refs", "capability_capsules")),
        "semantic_tool_policy_refs": redactor(_catalog_refs(catalog, "semantic_tool_policy_refs", "semantic_tool_policies")),
        "client_adapter_conformance_packs": redactor(_catalog_list(catalog, "client_adapter_conformance_packs")),
        "memory_provider_capabilities": redactor(_catalog_list(catalog, "memory_provider_capabilities")),
        "identity_rule": "canonical services come from manifests/catalog records, not client config aliases",
    }


def list_available_capabilities(
    project_root: str | Path,
    *,
    state: Mapping[str, Any] | None | object = _UNSET,
    catalog: Mapping[str, Any] | None = None,
    manifest_paths: Iterable[str | Path] | None = None,
    require_workspace: bool = True,
    redactor: Callable[[Any], Any] = redact_secrets,
) -> dict[str, Any]:
    """Return project-relevant available capabilities without side effects."""

    root = project_state.validate_project_root(project_root, require_workspace=require_workspace)
    state_data = _resolve_state(root, state=state, require_workspace=require_workspace)
    catalog_view = catalog if _is_catalog_view(catalog) else list_catalog(
        catalog=catalog,
        manifest_paths=manifest_paths,
        redactor=redactor,
    )
    services = list(catalog_view.get("services", []))

    existing_shared = [
        _capability_from_service(service, "capability_capsule_required" if service.get("capability_capsule_ref") else "bind_existing")
        for service in services
        if _is_registered(service) and not _requires_local_project_scope(service)
    ]
    project_scoped = [
        _capability_from_service(service, "project_scoped")
        for service in services
        if _is_registered(service) and _service_matches_project(service, root)
    ]
    candidates = [_candidate_summary(candidate, redactor=redactor) for candidate in catalog_view.get("candidates", [])]
    candidates.extend(
        _capability_from_service(service, "service_management_handoff_required")
        for service in services
        if not _is_registered(service) and _service_relevant_to_project(service, root)
    )

    return {
        "schema_version": READ_MODEL_VERSION,
        "surface": "list_available_capabilities",
        "project": {
            "root": str(root),
            "root_hash": project_state.project_root_hash(root),
            "state_present": state_data is not None,
            "state_status": str(state_data.get("status", "uninitialized")).upper() if state_data else "UNINITIALIZED",
        },
        "existing_project_bindings": redactor(_state_services(state_data)),
        "existing_shared_services": redactor(sorted(existing_shared, key=lambda item: item.get("canonical_service") or "")),
        "project_scoped_services": redactor(sorted(project_scoped, key=lambda item: item.get("canonical_service") or "")),
        "candidates": redactor(sorted(candidates, key=lambda item: item.get("candidate_name") or item.get("canonical_service") or "")),
        "language_profiles": redactor(catalog_view.get("language_profiles", [])),
        "setup_gaps": redactor(_collect_gaps(root, state_data, catalog_view)),
    }


def report_project_gaps(
    project_root: str | Path,
    *,
    state: Mapping[str, Any] | None | object = _UNSET,
    catalog: Mapping[str, Any] | None = None,
    manifest_paths: Iterable[str | Path] | None = None,
    require_workspace: bool = True,
    redactor: Callable[[Any], Any] = redact_secrets,
) -> dict[str, Any]:
    """Return redacted project gaps from supplied state/catalog data only."""

    root = project_state.validate_project_root(project_root, require_workspace=require_workspace)
    state_data = _resolve_state(root, state=state, require_workspace=require_workspace)
    catalog_view = catalog if _is_catalog_view(catalog) else list_catalog(
        catalog=catalog,
        manifest_paths=manifest_paths,
        redactor=redactor,
    )
    gaps = _collect_gaps(root, state_data, catalog_view)
    return {
        "schema_version": READ_MODEL_VERSION,
        "surface": "report_project_gaps",
        "project": {
            "root": str(root),
            "root_hash": project_state.project_root_hash(root),
            "state_present": state_data is not None,
            "state_status": str(state_data.get("status", "uninitialized")).upper() if state_data else "UNINITIALIZED",
        },
        "gaps": redactor(gaps),
        "summary": {
            "total": len(gaps),
            "blocking": sum(1 for gap in gaps if gap.get("severity") == "blocking"),
            "warning": sum(1 for gap in gaps if gap.get("severity") == "warning"),
            "info": sum(1 for gap in gaps if gap.get("severity") == "info"),
        },
        "diagnostic_bundle": redactor(
            {
                "project_state": state_data,
                "drift": (state_data or {}).get("drift"),
                "catalog_services": catalog_view.get("services", []),
                "catalog_candidates": catalog_view.get("candidates", []),
            }
        ),
    }


def _resolve_state(
    root: Path,
    *,
    state: Mapping[str, Any] | None | object,
    require_workspace: bool,
) -> dict[str, Any] | None:
    if state is _UNSET:
        return project_state.load_state(root, require_workspace=require_workspace)
    if state is None:
        return None
    state_copy = copy.deepcopy(dict(state))
    project_state.validate_state_root(state_copy, root)
    project_state.validate_state(state_copy)
    return state_copy


def _catalog_services(
    catalog: Mapping[str, Any] | None,
    *,
    manifest_paths: Iterable[str | Path] | None,
    instance_root: str | Path,
) -> list[tuple[dict[str, Any], str | None]]:
    if catalog is not None:
        values = catalog.get("services", [])
        if isinstance(values, Mapping):
            iterable = values.values()
        else:
            iterable = values
        services = []
        for item in iterable if isinstance(iterable, Iterable) else []:
            if isinstance(item, Mapping):
                services.append((copy.deepcopy(dict(item)), item.get("source_ref")))
        return services

    paths = list(manifest_paths) if manifest_paths is not None else sorted(Path(instance_root).glob("*/instance.json"))
    services = []
    for raw_path in paths:
        path = Path(raw_path)
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            continue
        if isinstance(manifest, Mapping):
            services.append((copy.deepcopy(dict(manifest)), str(path)))
    return services


def _service_summary_from_manifest(
    manifest: Mapping[str, Any],
    *,
    source_ref: str | None,
    redactor: Callable[[Any], Any],
) -> dict[str, Any]:
    contextforge = manifest.get("contextforge") if isinstance(manifest.get("contextforge"), Mapping) else {}
    gateway = contextforge.get("gateway") if isinstance(contextforge.get("gateway"), Mapping) else {}
    virtual_server = contextforge.get("virtual_server") if isinstance(contextforge.get("virtual_server"), Mapping) else {}
    registration = manifest.get("registration") if isinstance(manifest.get("registration"), Mapping) else {}
    scope = manifest.get("scope") if isinstance(manifest.get("scope"), Mapping) else {}
    bridge = manifest.get("bridge") if isinstance(manifest.get("bridge"), Mapping) else {}
    backend = manifest.get("backend") if isinstance(manifest.get("backend"), Mapping) else {}
    instance_slug = _first_string(
        manifest.get("instance_slug"),
        manifest.get("slug"),
        _path_slug(source_ref),
        manifest.get("name"),
    )
    canonical_service = _first_string(manifest.get("service"), manifest.get("canonical_service"), manifest.get("name"), instance_slug)

    return {
        "identity_source": "instance_manifest",
        "source_ref": source_ref,
        "canonical_service": canonical_service,
        "canonical_gateway": _first_string(gateway.get("name"), manifest.get("gateway_name")),
        "canonical_virtual_server": _first_string(virtual_server.get("name"), manifest.get("server_name")),
        "instance_slug": instance_slug,
        "backend_home": str(Path("server-instances") / instance_slug) if instance_slug else None,
        "kind": manifest.get("kind"),
        "enabled": manifest.get("enabled"),
        "registration_status": registration.get("status"),
        "registered_tools": redactor(registration.get("registered_tools", [])),
        "scope": redactor(scope),
        "transport": backend.get("transport"),
        "native_transports": _native_transports(manifest),
        "bridge": redactor(bridge),
        "backend": redactor(_backend_summary(backend)),
        "project_root": manifest.get("canonical_project_root") or scope.get("workspace_root"),
        "project_root_hash": manifest.get("project_root_hash"),
        "contract_card_ref": manifest.get("contract_card_ref"),
        "capability_capsule_ref": manifest.get("capability_capsule_ref"),
        "semantic_tool_policy_ref": manifest.get("semantic_tool_policy_ref"),
        "contract_refs": redactor(manifest.get("contract_refs", [])),
        "policy_refs": redactor(manifest.get("policy_refs", [])),
        "verification": redactor(manifest.get("verification", {})),
        "client_config_names": redactor(_client_config_names(manifest)),
    }


def _backend_summary(backend: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "transport": backend.get("transport"),
        "command": backend.get("command"),
        "args": backend.get("args", []),
        "working_directory": backend.get("working_directory"),
        "env": backend.get("env", {}),
        "env_vars": backend.get("env_vars", []),
    }


def _candidate_summary(candidate: Mapping[str, Any], *, redactor: Callable[[Any], Any]) -> dict[str, Any]:
    candidate_name = _first_string(
        candidate.get("candidate_name"),
        candidate.get("canonical_service"),
        candidate.get("service"),
        candidate.get("name"),
        candidate.get("slug"),
    )
    return redactor(
        {
            "candidate_name": candidate_name,
            "service_family": candidate.get("service_family") or candidate.get("service"),
            "evidence": candidate.get("evidence"),
            "notes": candidate.get("notes"),
            "required_next_workflow": candidate.get("required_next_workflow", "service_management_handoff"),
            "contract_card_ref": candidate.get("contract_card_ref"),
            "capability_capsule_ref": candidate.get("capability_capsule_ref"),
            "semantic_tool_policy_ref": candidate.get("semantic_tool_policy_ref"),
        }
    )


def _collect_gaps(root: Path, state_data: Mapping[str, Any] | None, catalog_view: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    if state_data is None:
        gaps.append(
            _gap(
                "project_state_missing",
                "blocking",
                "project_state",
                "No project state exists for this canonical root.",
                {"expected_state": str(project_state.project_state_path(root))},
            )
        )
    else:
        migration = state_data.get("migration", {})
        if isinstance(migration, Mapping) and (
            migration.get("legacy_env_disposition") == "conflict" or migration.get("conflicts")
        ):
            gaps.append(_gap("migration", "blocking", "migration", "Migration conflicts require review.", migration))

        for item in state_data.get("open_items", []):
            if isinstance(item, Mapping) and item.get("resolution_state") == "open":
                gaps.append(
                    _gap(
                        str(item.get("type", "open_item")),
                        str(item.get("severity", "warning")),
                        str(item.get("resource", "project_state")),
                        f"Open project item: {item.get('id')}",
                        {"open_item": item},
                    )
                )

        drift = state_data.get("drift", {})
        if isinstance(drift, Mapping) and drift.get("status") == "drift_found":
            gaps.append(_gap("drift", "warning", "drift", "Project drift findings are unresolved.", drift))

        for client_name, trust in _mapping_items(state_data.get("client_trust", {})):
            trust_state = trust.get("state") if isinstance(trust, Mapping) else None
            if trust_state not in {"trusted", "not_required", "declined"}:
                gap_type = "restart" if trust_state == "trusted_requires_restart" else "trust"
                gaps.append(
                    _gap(
                        gap_type,
                        "blocking" if trust_state in {"unknown", "untrusted"} else "warning",
                        f"client_trust:{client_name}",
                        f"Client trust is not fully active for {client_name}.",
                        {"client": client_name, "state": trust_state, "trust": trust},
                    )
                )

        for binding, service in _mapping_items(state_data.get("services", {})):
            gaps.extend(_service_gaps(str(binding), service))

        artifact_refs = state_data.get("artifact_refs", {})
        if isinstance(artifact_refs, Mapping) and state_data.get("services"):
            if not artifact_refs.get("contract_cards"):
                gaps.append(_gap("contract_missing", "blocking", "artifact_refs", "No contract card refs recorded.", {}))
            if not artifact_refs.get("consent_receipts"):
                gaps.append(_gap("consent_required", "blocking", "artifact_refs", "No consent receipt refs recorded.", {}))
            if not artifact_refs.get("verification_traces"):
                gaps.append(_gap("trace_missing", "blocking", "artifact_refs", "No verification trace refs recorded.", {}))

    for candidate in (catalog_view or {}).get("candidates", []):
        if isinstance(candidate, Mapping):
            name = candidate.get("candidate_name") or candidate.get("service") or candidate.get("name")
            gaps.append(
                _gap(
                    "catalog_candidate",
                    "info",
                    f"catalog_candidate:{name}",
                    "Catalog candidate requires confirmation before promotion.",
                    candidate,
                )
            )
    return gaps


def _service_gaps(binding: str, service: Mapping[str, Any]) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    if not service.get("contract_card_ref"):
        gaps.append(_gap("contract_missing", "blocking", f"service:{binding}", "Service is missing a contract card ref.", service))
    if not service.get("semantic_tool_policy_ref"):
        gaps.append(_gap("tool_policy", "blocking", f"service:{binding}", "Service is missing a semantic tool policy ref.", service))
    if service.get("language_profile") is None:
        gaps.append(_gap("language_profile_missing", "warning", f"service:{binding}", "Service has no language profile.", service))

    status = service.get("provision_status")
    if status in {"none", "pending", "degraded", "failed"}:
        severity = "blocking" if status in {"failed", "degraded"} else "warning"
        gaps.append(_gap("service", severity, f"service:{binding}", f"Service provision status is {status}.", service))
    if not service.get("consent_receipt_refs"):
        gaps.append(_gap("consent_required", "blocking", f"service:{binding}", "Service has no consent receipt refs.", service))
    if not service.get("verification_trace_refs"):
        gaps.append(_gap("trace_missing", "blocking", f"service:{binding}", "Service has no verification trace refs.", service))

    required_layers = service.get("required_verification_layers", [])
    verification_layers = service.get("verification_layers", {})
    for layer in required_layers if isinstance(required_layers, list) else []:
        status_value = _verification_layer_status(verification_layers, str(layer))
        if status_value != "passed":
            gaps.append(
                _gap(
                    "verification",
                    "blocking",
                    f"service:{binding}:{layer}",
                    f"Required verification layer has not passed: {layer}.",
                    {"service_binding": binding, "layer": layer, "status": status_value},
                )
            )
    return gaps


def _gap(gap_type: str, severity: str, resource: str, message: str, detail: Any) -> dict[str, Any]:
    return {
        "type": gap_type,
        "severity": severity if severity in {"info", "warning", "blocking"} else "warning",
        "resource": resource,
        "message": message,
        "detail": detail,
    }


def _redact(value: Any, *, key: str | None = None) -> Any:
    if key is not None and SECRET_KEY_RE.search(key):
        return _REDACTED
    if isinstance(value, Mapping):
        return {str(child_key): _redact(child_value, key=str(child_key)) for child_key, child_value in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, tuple):
        return [_redact(item) for item in value]
    if isinstance(value, str) and SECRET_VALUE_RE.search(value):
        return _REDACTED
    return copy.deepcopy(value)


def _artifact_refs(state_data: Mapping[str, Any] | None) -> dict[str, list[dict[str, Any]]]:
    refs = (state_data or {}).get("artifact_refs", {})
    if not isinstance(refs, Mapping):
        return {}
    return {str(key): copy.deepcopy(value) for key, value in refs.items() if isinstance(value, list)}


def _related_instances(state_data: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    diagnostics = (state_data or {}).get("diagnostics", {})
    if isinstance(diagnostics, Mapping) and isinstance(diagnostics.get("related_instances"), list):
        return copy.deepcopy(diagnostics["related_instances"])
    return []


def _state_services(state_data: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    records = []
    for binding, service in _mapping_items((state_data or {}).get("services", {})):
        records.append(
            {
                "state_key": binding,
                "service_family": service.get("service_family"),
                "service_binding": service.get("service_binding"),
                "instantiation_class": service.get("instantiation_class"),
                "contract_card_ref": service.get("contract_card_ref"),
                "capability_capsule_ref": service.get("capability_capsule_ref"),
                "semantic_tool_policy_ref": service.get("semantic_tool_policy_ref"),
                "backend_instance": service.get("backend_instance"),
                "virtual_server": service.get("virtual_server"),
                "provision_status": service.get("provision_status"),
                "language_profile": service.get("language_profile"),
                "target_clients": service.get("target_clients", {}),
                "verification_trace_refs": service.get("verification_trace_refs", []),
                "consent_receipt_refs": service.get("consent_receipt_refs", []),
            }
        )
    return sorted(records, key=lambda item: item.get("service_binding") or item.get("state_key") or "")


def _target_clients(state_data: Mapping[str, Any] | None) -> list[str]:
    clients = set()
    client_trust = (state_data or {}).get("client_trust", {})
    if isinstance(client_trust, Mapping):
        clients.update(str(name) for name in client_trust)
    for _, service in _mapping_items((state_data or {}).get("services", {})):
        target_clients = service.get("target_clients", {})
        if isinstance(target_clients, Mapping):
            clients.update(str(name) for name in target_clients)
        elif isinstance(target_clients, list):
            clients.update(str(name) for name in target_clients)
    return sorted(clients)


def _governance_warnings(state_data: Mapping[str, Any] | None) -> list[Any]:
    artifact_refs = (state_data or {}).get("artifact_refs", {})
    warnings = []
    if isinstance(artifact_refs, Mapping):
        warnings.extend(artifact_refs.get("governance_reconciliation_packs", []))
    open_items = (state_data or {}).get("open_items", [])
    warnings.extend(
        item for item in open_items if isinstance(item, Mapping) and item.get("type") == "governance_reconciliation"
    )
    return copy.deepcopy(warnings)


def _catalog_list(catalog: Mapping[str, Any] | None, key: str) -> list[Any]:
    if catalog is None:
        return []
    value = catalog.get(key, [])
    if isinstance(value, list):
        return copy.deepcopy(value)
    if isinstance(value, Mapping):
        return copy.deepcopy(list(value.values()))
    return []


def _catalog_refs(catalog: Mapping[str, Any] | None, refs_key: str, artifacts_key: str) -> list[Any]:
    refs = _catalog_list(catalog, refs_key)
    if refs:
        return refs
    artifacts = _catalog_list(catalog, artifacts_key)
    output = []
    for artifact in artifacts:
        if isinstance(artifact, Mapping):
            ref = artifact.get("ref") or artifact.get("card_id") or artifact.get("capsule_id") or artifact.get("policy_id")
            if ref:
                output.append({"ref": ref})
    return output


def _native_transports(manifest: Mapping[str, Any]) -> list[str]:
    backend = manifest.get("backend") if isinstance(manifest.get("backend"), Mapping) else {}
    bridge = manifest.get("bridge") if isinstance(manifest.get("bridge"), Mapping) else {}
    transports = []
    if backend.get("transport"):
        transports.append(str(backend["transport"]))
    if bridge.get("needed") is False:
        if bridge.get("streamable_http_url"):
            transports.append("streamable_http")
        if bridge.get("sse_url"):
            transports.append("sse")
    return sorted(set(transports))


def _client_config_names(manifest: Mapping[str, Any]) -> list[str]:
    names = []
    for key in ("client", "codex_alias", "client_name"):
        value = manifest.get(key)
        if isinstance(value, str) and value not in {"canonical", ""}:
            names.append(value)
    return sorted(set(names))


def _capability_from_service(service: Mapping[str, Any], binding_mode: str) -> dict[str, Any]:
    return {
        "canonical_service": service.get("canonical_service"),
        "canonical_gateway": service.get("canonical_gateway"),
        "canonical_virtual_server": service.get("canonical_virtual_server"),
        "instance_slug": service.get("instance_slug"),
        "registration_status": service.get("registration_status"),
        "binding_mode": binding_mode,
        "contract_card_ref": service.get("contract_card_ref"),
        "capability_capsule_ref": service.get("capability_capsule_ref"),
        "semantic_tool_policy_ref": service.get("semantic_tool_policy_ref"),
        "project_root": service.get("project_root"),
        "project_root_hash": service.get("project_root_hash"),
    }


def _is_catalog_view(catalog: Mapping[str, Any] | None) -> bool:
    return isinstance(catalog, Mapping) and catalog.get("surface") == "list_catalog"


def _is_registered(service: Mapping[str, Any]) -> bool:
    return service.get("registration_status") == "registered"


def _requires_local_project_scope(service: Mapping[str, Any]) -> bool:
    scope = service.get("scope", {})
    return bool(isinstance(scope, Mapping) and scope.get("requires_local_project_scope"))


def _service_matches_project(service: Mapping[str, Any], root: Path) -> bool:
    if not _requires_local_project_scope(service):
        return False
    project_root_value = service.get("project_root")
    project_hash_value = service.get("project_root_hash")
    return project_root_value == str(root) or project_hash_value == project_state.project_root_hash(root)


def _service_relevant_to_project(service: Mapping[str, Any], root: Path) -> bool:
    return not _requires_local_project_scope(service) or _service_matches_project(service, root)


def _verification_layer_status(verification_layers: Any, layer: str) -> str | None:
    if not isinstance(verification_layers, Mapping):
        return None
    value = verification_layers.get(layer)
    if isinstance(value, Mapping):
        return value.get("status")  # type: ignore[return-value]
    if isinstance(value, str):
        return value
    if value is True:
        return "passed"
    return None


def _mapping_items(value: Any) -> list[tuple[str, Mapping[str, Any]]]:
    if not isinstance(value, Mapping):
        return []
    return [(str(key), child) for key, child in value.items() if isinstance(child, Mapping)]


def _first_string(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value:
            return value
    return None


def _path_slug(source_ref: str | None) -> str | None:
    if not source_ref:
        return None
    path = Path(source_ref)
    if path.name == "instance.json":
        return path.parent.name
    return None


__all__ = [
    "get_project_context",
    "list_catalog",
    "list_available_capabilities",
    "report_project_gaps",
    "redact_secrets",
]
