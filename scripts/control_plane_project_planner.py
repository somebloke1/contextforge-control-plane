#!/usr/bin/env python3
"""Pure project-init planner for the ContextForge control plane."""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import control_plane_contracts as contracts
import control_plane_project_state as project_state
import control_plane_service_classifier as classifier
import control_plane_service_handoffs as handoffs


PLANNER_VERSION = 1
DEFAULT_RESOLVED_AT = "2026-05-30T00:00:00Z"
FORBIDDEN_PROJECT_INIT_CONSENT_CLASSES = frozenset(
    {
        "catalog_promotion",
        "user_global_client_trust",
        "user_global_config_write",
        "secret_value_write",
        "token_material_change",
        "network_exposure_change",
    }
)


class ProjectPlannerInputError(ValueError):
    """Raised when planner inputs cannot produce a safe non-mutating plan."""


def plan_project_initialization(
    project_root: str | Path,
    *,
    state: Mapping[str, Any] | None = None,
    catalog: Mapping[str, Any] | None = None,
    service_descriptors: Iterable[Mapping[str, Any]] = (),
    target_client_digests: Mapping[str, Any] | None = None,
    trust_state_digest: str | None = None,
    missing_trust: Iterable[Mapping[str, Any] | str] = (),
    missing_language: Iterable[Mapping[str, Any] | str] = (),
    drift_findings: Iterable[Mapping[str, Any] | str] = (),
    require_workspace: bool = True,
    resolved_at: str = DEFAULT_RESOLVED_AT,
) -> dict[str, Any]:
    """Return a non-mutating project-init plan from supplied snapshots.

    The planner validates the root and consumes only injected state/catalog and
    descriptor inputs. It deliberately does not create or load durable project
    state, promote catalog candidates, register services, or alter client trust.
    """

    root = project_state.validate_project_root(project_root, require_workspace=require_workspace)
    state_copy = _json_compatible_copy(state) if state is not None else None
    catalog_copy = _json_compatible_copy(catalog or {})
    descriptors = [_json_compatible_copy(descriptor) for descriptor in service_descriptors]
    target_client_snapshot = _json_compatible_copy(target_client_digests or {})
    drift_snapshot = _json_compatible_copy(list(drift_findings))
    trust_digest = trust_state_digest or _trust_digest_from_state(state_copy)
    catalog_revision = _catalog_revision(catalog_copy)
    root_hash = project_state.project_root_hash(root)

    stale_inputs = {
        "project_root": str(root),
        "project_root_hash": root_hash,
        "base_project_state": _base_state_stale_input(state_copy),
        "catalog": {
            "revision_or_etag": catalog_revision,
            "digest": _digest_or_null(catalog_copy) if catalog_copy else None,
        },
        "selected_service_descriptors": [_descriptor_stale_input(descriptor) for descriptor in descriptors],
        "target_client_digests": target_client_snapshot,
        "trust_state_digest": trust_digest,
        "drift_findings": drift_snapshot,
    }

    plan_steps: list[dict[str, Any]] = []
    open_items: list[dict[str, Any]] = []
    service_management_handoffs: list[dict[str, Any]] = []
    artifact_drafts = {"contract_cards": [], "capability_capsules": []}

    if _state_status(state_copy) == "disabled":
        open_items.append(
            _open_item(
                "project-init-disabled",
                "service",
                "project",
                {"state_status": "disabled", "action": "no service planning while project init is disabled"},
                severity="blocking",
            )
        )
    else:
        for index, descriptor in enumerate(descriptors):
            descriptor_id = _descriptor_id(descriptor, index)
            classification = classifier.classify_service_binding(
                descriptor,
                project_root=str(root),
                source="project_init",
                resolved_at=resolved_at,
                catalog_revision_or_etag=catalog_revision,
            )
            decision = _decision_for_descriptor(state_copy, descriptor, classification)
            decision_state = str(decision.get("state", "unasked")) if decision else "unasked"

            if decision_state in {"declined", "disabled"}:
                open_items.append(
                    _open_item(
                        f"{descriptor_id}-{decision_state}",
                        "service",
                        classification.get("service_binding") or descriptor_id,
                        {
                            "status": "no_service",
                            "decision_state": decision_state,
                            "sticky": True,
                            "service_binding": classification.get("service_binding"),
                        },
                    )
                )
                continue

            if decision_state == "deferred":
                open_items.append(
                    _open_item(
                        f"{descriptor_id}-deferred",
                        "service",
                        classification.get("service_binding") or descriptor_id,
                        {
                            "status": "deferred",
                            "decision_state": "deferred",
                            "service_binding": classification.get("service_binding"),
                        },
                        severity="warning",
                    )
                )
                continue

            if classification["status"] == "handoff_required":
                handoff = handoffs.build_catalog_candidate_handoff(descriptor, project_root=str(root))
                service_management_handoffs.append(handoff)
                open_items.append(
                    _open_item(
                        f"{descriptor_id}-handoff-required",
                        "handoff_required",
                        descriptor_id,
                        {
                            "status": "service_management_required",
                            "handoff_id": handoff["handoff_id"],
                            "forbidden_under_project_init": handoff["forbidden_under_current_approval"],
                        },
                    )
                )
                continue

            if classification["status"] != "classified":
                open_items.append(
                    _open_item(
                        f"{descriptor_id}-classification-blocked",
                        "service",
                        descriptor_id,
                        {
                            "status": "blocked",
                            "blockers": classification.get("blockers", []),
                            "non_actions": classification.get("non_actions", []),
                        },
                    )
                )
                continue

            contract_card = classification["contract_card_draft"]
            contract_ref = _artifact_ref("service-bindings", contract_card["card_id"], contract_card, resolved_at, catalog_revision)
            capsule_ref = None
            capsule = classification.get("shared_service_capability_capsule")
            artifact_drafts["contract_cards"].append(contract_card)
            if isinstance(capsule, Mapping):
                capsule_ref = _artifact_ref("capability-capsules", capsule["capsule_id"], capsule, resolved_at, catalog_revision)
                artifact_drafts["capability_capsules"].append(capsule)

            consent_classes = _allowed_project_init_consents(contract_card["required_consent_classes"])
            plan_steps.append(
                {
                    "step_id": f"plan-{classification['service_binding']}",
                    "status": "planned",
                    "operation": _operation_for_class(classification["instantiation_class"]),
                    "service_binding": classification["service_binding"],
                    "service_family": classification["service_family"],
                    "canonical_service": classification["canonical_service"],
                    "instantiation_class": classification["instantiation_class"],
                    "contract_card_ref": contract_ref,
                    "capability_capsule_ref": capsule_ref,
                    "required_consent_classes": consent_classes,
                    "stale_plan_inputs": {
                        "project_root_hash": root_hash,
                        "base_project_state": stale_inputs["base_project_state"],
                        "catalog_revision_or_etag": catalog_revision,
                        "descriptor_digest": _stable_digest(descriptor),
                        "target_client_digests": target_client_snapshot,
                        "trust_state_digest": trust_digest,
                        "drift_findings": drift_snapshot,
                    },
                    "verification_requirements": classification["verification_requirements"],
                    "non_actions": classification["non_actions"],
                    "effect_summary": _effect_summary(classification, consent_classes),
                }
            )

    open_items.extend(_missing_trust_open_items(missing_trust, state_copy))
    open_items.extend(_missing_language_open_items(missing_language, state_copy))
    open_items.extend(_drift_open_items(drift_snapshot))

    consent_classes = _consent_union(plan_steps)
    plan = {
        "schema_version": PLANNER_VERSION,
        "surface": "propose_project_init",
        "planner": "control_plane_project_planner",
        "project": {"root": str(root), "root_hash": root_hash, "name": root.name},
        "plan_id": _plan_id(root_hash, stale_inputs, plan_steps, open_items),
        "status": _plan_status(state_copy, open_items, plan_steps),
        "mutation_allowed": False,
        "apply_requires": {
            "later_wave": "Wave 5",
            "required_before_apply": ["explicit approval", "consent receipts", "verification traces", "stale-plan validation"],
        },
        "required_consent_classes": consent_classes,
        "forbidden_project_init_consent_classes": sorted(FORBIDDEN_PROJECT_INIT_CONSENT_CLASSES),
        "stale_plan_inputs": stale_inputs,
        "plan_steps": plan_steps,
        "service_management_handoffs": service_management_handoffs,
        "open_items": open_items,
        "artifact_drafts": artifact_drafts,
        "non_actions": _plan_non_actions(plan_steps),
    }
    contracts.validate_redacted(plan)
    return plan


def _effect_summary(classification: Mapping[str, Any], consent_classes: list[str]) -> dict[str, Any]:
    instantiation_class = str(classification["instantiation_class"])
    if instantiation_class == "shared_canonical":
        return {
            "effect_type": "bind_verify_existing",
            "mutation_classes": [],
            "read_only": True,
            "project_state_service_record": False,
            "backend_instance": "existing_only",
            "contextforge_gateway": "existing_only",
            "virtual_server": "existing_only",
            "client_config_write": False,
            "service_provision": False,
            "forbidden_effects": [
                "per_project_backend",
                "per_project_gateway",
                "per_project_bridge",
                "per_project_wrapper",
                "per_project_port",
                "per_project_unit",
                "server_instance_directory",
            ],
        }
    effects = {
        "effect_type": "plan_only",
        "mutation_classes": [item for item in consent_classes if item != "read_only_inspection"],
        "read_only": consent_classes == ["read_only_inspection"],
        "project_state_service_record": "project_state_write" in consent_classes,
        "backend_instance": "planned_later" if "service_provision" in consent_classes else None,
        "contextforge_gateway": "planned_later" if "service_provision" in consent_classes else "verify_or_bind_later",
        "virtual_server": "planned_later" if "project_state_write" in consent_classes else None,
        "client_config_write": "project_local_config_write" in consent_classes,
        "service_provision": "service_provision" in consent_classes,
        "forbidden_effects": sorted(FORBIDDEN_PROJECT_INIT_CONSENT_CLASSES),
    }
    return effects


def _operation_for_class(instantiation_class: str) -> str:
    if instantiation_class == "shared_canonical":
        return "bind_verify_existing_shared_service"
    if instantiation_class == "instance_per_project":
        return "plan_project_scoped_service_provision"
    return "plan_project_service_binding"


def _allowed_project_init_consents(consents: Iterable[str]) -> list[str]:
    return [item for item in _unique(consents) if item not in FORBIDDEN_PROJECT_INIT_CONSENT_CLASSES]


def _consent_union(plan_steps: Iterable[Mapping[str, Any]]) -> list[str]:
    return _unique(
        consent
        for step in plan_steps
        for consent in step.get("required_consent_classes", [])
        if isinstance(consent, str) and consent not in FORBIDDEN_PROJECT_INIT_CONSENT_CLASSES
    )


def _plan_non_actions(plan_steps: Iterable[Mapping[str, Any]]) -> list[str]:
    base = [
        "do not mutate project state during planning",
        "do not create .project/context_forge_state.json during planning",
        "do not promote catalog candidates during project init",
        "do not change user-global client trust during project init",
        "do not write secret values during project init",
    ]
    for step in plan_steps:
        base.extend(item for item in step.get("non_actions", []) if isinstance(item, str))
    return _unique(base)


def _plan_status(
    state: Mapping[str, Any] | None,
    open_items: Iterable[Mapping[str, Any]],
    plan_steps: Iterable[Mapping[str, Any]],
) -> str:
    if _state_status(state) == "disabled":
        return "disabled_no_service"
    items = list(open_items)
    if any(item.get("severity") == "blocking" for item in items):
        return "blocked_open_items"
    if list(plan_steps):
        return "planned_non_mutating"
    if items:
        return "open_items_only"
    return "no_service"


def _state_status(state: Mapping[str, Any] | None) -> str:
    return str((state or {}).get("status", "uninitialized")).lower()


def _base_state_stale_input(state: Mapping[str, Any] | None) -> dict[str, Any]:
    if not state:
        return {"present": False, "revision": None, "status": None, "digest": None}
    meta = state.get("meta") if isinstance(state.get("meta"), Mapping) else {}
    return {
        "present": True,
        "revision": meta.get("revision"),
        "status": state.get("status"),
        "digest": _stable_digest(state),
    }


def _catalog_revision(catalog: Mapping[str, Any]) -> str | None:
    meta = catalog.get("meta") if isinstance(catalog.get("meta"), Mapping) else {}
    return _first_string(
        catalog.get("revision"),
        catalog.get("etag"),
        catalog.get("catalog_revision"),
        catalog.get("catalog_revision_or_etag"),
        meta.get("revision"),
        meta.get("etag"),
    )


def _descriptor_stale_input(descriptor: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "descriptor_id": _descriptor_id(descriptor, 0),
        "artifact_digest": _stable_digest(descriptor),
        "service_family": _first_string(descriptor.get("service_family")),
        "canonical_service": _first_string(descriptor.get("canonical_service")),
    }


def _decision_for_descriptor(
    state: Mapping[str, Any] | None,
    descriptor: Mapping[str, Any],
    classification: Mapping[str, Any],
) -> dict[str, Any] | None:
    decisions = (state or {}).get("decisions")
    if not isinstance(decisions, Mapping):
        return None
    keys = [
        classification.get("service_binding"),
        classification.get("canonical_service"),
        classification.get("service_family"),
        descriptor.get("service_binding"),
        descriptor.get("canonical_service"),
        descriptor.get("service_family"),
        descriptor.get("name"),
    ]
    for key in keys:
        if isinstance(key, str) and isinstance(decisions.get(key), Mapping):
            return dict(decisions[key])
    for record in decisions.values():
        if not isinstance(record, Mapping):
            continue
        if record.get("service_binding") == classification.get("service_binding"):
            return dict(record)
    return None


def _missing_trust_open_items(
    missing_trust: Iterable[Mapping[str, Any] | str],
    state: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    items = [_missing_item("trust", item, "user_global_client_trust requires separate explicit approval") for item in missing_trust]
    for item in (state or {}).get("open_items", []):
        if isinstance(item, Mapping) and item.get("type") in {"trust", "trust_broker"}:
            detail = dict(item)
            detail.pop("created_at", None)
            items.append(
                _open_item(
                    f"state-{item.get('id', 'missing-trust')}",
                    "trust",
                    item.get("resource", "client_trust"),
                    detail,
                    created_at=item.get("created_at"),
                )
            )
    return items


def _missing_language_open_items(
    missing_language: Iterable[Mapping[str, Any] | str],
    state: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    items = [_missing_item("language_profile_missing", item, "language profile must be selected before initialized status") for item in missing_language]
    for item in (state or {}).get("open_items", []):
        if isinstance(item, Mapping) and item.get("type") in {"language", "language_profile_missing"}:
            detail = dict(item)
            detail.pop("created_at", None)
            items.append(
                _open_item(
                    f"state-{item.get('id', 'missing-language')}",
                    "language_profile_missing",
                    item.get("resource", "language_profile"),
                    detail,
                    created_at=item.get("created_at"),
                )
            )
    return items


def _drift_open_items(drift_findings: Iterable[Any]) -> list[dict[str, Any]]:
    return [
        _open_item(
            f"drift-{index}",
            "drift",
            "stale_plan_inputs",
            {"finding": finding, "action": "refresh stale inputs before approval or apply"},
            severity="warning",
        )
        for index, finding in enumerate(drift_findings)
    ]


def _missing_item(item_type: str, value: Mapping[str, Any] | str, action: str) -> dict[str, Any]:
    detail = dict(value) if isinstance(value, Mapping) else {"name": str(value)}
    detail["action"] = action
    resource = _first_string(detail.get("client"), detail.get("service_binding"), detail.get("name")) or item_type
    return _open_item(f"missing-{item_type}-{_slug(resource)}", item_type, resource, detail)


def _open_item(
    item_id: str,
    item_type: str,
    resource: Any,
    detail: Mapping[str, Any],
    *,
    severity: str = "blocking",
    created_at: Any = None,
) -> dict[str, Any]:
    return {
        "id": _slug(item_id),
        "type": item_type,
        "severity": severity,
        "blocks_initialized": severity == "blocking",
        "resource": str(resource),
        "created_at": created_at if isinstance(created_at, str) and created_at else DEFAULT_RESOLVED_AT,
        "resolution_state": "open",
        "detail": _json_compatible_copy(detail),
    }


def _artifact_ref(
    namespace: str,
    artifact_id: str,
    artifact: Mapping[str, Any],
    resolved_at: str,
    catalog_revision: str | None,
) -> dict[str, Any]:
    return contracts.artifact_ref(
        f"contextforge://control-plane/{namespace}/{artifact_id}/v1",
        artifact,
        resolved_at=resolved_at,
        catalog_revision_or_etag=catalog_revision,
    )


def _trust_digest_from_state(state: Mapping[str, Any] | None) -> str | None:
    trust = (state or {}).get("client_trust")
    return _stable_digest(trust) if isinstance(trust, Mapping) and trust else None


def _digest_or_null(value: Mapping[str, Any] | None) -> str | None:
    return _stable_digest(value) if value else None


def _stable_digest(value: Any) -> str:
    encoded = json.dumps(_json_compatible_copy(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _plan_id(root_hash: str, stale_inputs: Mapping[str, Any], plan_steps: list[dict[str, Any]], open_items: list[dict[str, Any]]) -> str:
    digest = _stable_digest({"root_hash": root_hash, "stale_inputs": stale_inputs, "steps": plan_steps, "open_items": open_items})
    return f"project-init-{digest.removeprefix('sha256:')[:16]}"


def _descriptor_id(descriptor: Mapping[str, Any], index: int) -> str:
    return _slug(
        _first_string(
            descriptor.get("service_binding"),
            descriptor.get("canonical_service"),
            descriptor.get("service_family"),
            descriptor.get("candidate_name"),
            descriptor.get("name"),
        )
        or f"descriptor-{index}"
    )


def _first_string(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value:
            return value
    return None


def _slug(value: Any) -> str:
    text = str(value).strip().lower()
    output = []
    for char in text:
        if char.isalnum() or char in "_.:-":
            output.append(char)
        else:
            output.append("-")
    slug = "".join(output).strip("-._:")
    return slug or "item"


def _unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value not in seen:
            output.append(value)
            seen.add(value)
    return output


def _json_compatible_copy(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_compatible_copy(child) for key, child in value.items()}
    if isinstance(value, tuple):
        return [_json_compatible_copy(item) for item in value]
    if isinstance(value, list):
        return [_json_compatible_copy(item) for item in value]
    if value is None or isinstance(value, str | bool | int | float):
        return copy.deepcopy(value)
    return str(value)
