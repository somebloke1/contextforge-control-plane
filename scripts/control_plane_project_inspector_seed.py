#!/usr/bin/env python3
"""RFC seed records for the project-inspector proof service.

This module is deliberately pure.  It predeclares the RFC-named
project-inspector proof service and composes the existing generic
project-adapter, service-provision, and ContextForge-binding planning helpers.
It does not implement inspector tools and does not write backend homes,
ContextForge state, client config, trust state, server-instances, .project, or
.codex files.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import control_plane_contextforge_binding as binding
import control_plane_contracts as contracts
import control_plane_project_adapter as adapter
import control_plane_service_provision as provision


DEFAULT_GENERATED_AT = "2026-05-30T20:21:54Z"
DEFAULT_TARGET_CLIENT = "codex"
SERVICE_FAMILY = "project-inspector"
SERVICE_BINDING = "project-inspector:project"
PROOF_STATUS = "rfc_seeded_proof"
SEED_SOURCE = "design-rfc:D12:Dedicated Project-Scoped Non-Serena Proof Candidate"


def build_project_inspector_seed(
    *,
    project_root: str | Path,
    target_client: str = DEFAULT_TARGET_CLIENT,
    generated_at: str = DEFAULT_GENERATED_AT,
    gateway_revision: str = "gateway-rfc-seed",
    target_client_digest: str = "sha256:codex-rfc-seed",
) -> dict[str, Any]:
    """Build the deterministic project-inspector seed bundle.

    The returned object is planning data only.  It is safe to call from tests or
    read surfaces because all downstream helpers used here are pure builders.
    """

    spec = adapter.build_project_inspector_adapter_spec(
        project_root=project_root,
        target_client=target_client,
        identity_source="rfc_seed",
    )
    if spec["service_binding"] != SERVICE_BINDING:
        raise ProjectInspectorSeedError("generic adapter project-inspector binding changed unexpectedly")

    semantic_policy = adapter.compile_adapter_tool_policy(
        spec,
        expected_gateway_revision=gateway_revision,
        current_gateway_revision=gateway_revision,
        expected_target_client_digest=target_client_digest,
        current_target_client_digest=target_client_digest,
        compiled_at=generated_at,
    )
    contract_card = build_project_inspector_contract_card(
        adapter_spec=spec,
        semantic_tool_policy=semantic_policy,
        generated_at=generated_at,
    )
    contract_ref = contracts.artifact_ref(
        "contextforge://control-plane/service-bindings/project-inspector-rfc-seed/v1",
        contract_card,
        resolved_at=generated_at,
        catalog_revision_or_etag=PROOF_STATUS,
    )
    policy_ref = contracts.artifact_ref(
        "contextforge://control-plane/semantic-tool-policies/project-inspector-rfc-seed/v1",
        semantic_policy,
        resolved_at=generated_at,
        catalog_revision_or_etag=PROOF_STATUS,
    )
    backend_manifest_ref = contracts.artifact_ref(
        "contextforge://control-plane/backend-manifests/project-inspector-project/planned",
        {"service_binding": SERVICE_BINDING, "source": PROOF_STATUS},
        resolved_at=generated_at,
        catalog_revision_or_etag=PROOF_STATUS,
    )
    gateway_ref = contracts.artifact_ref(
        "contextforge://control-plane/gateways/project-inspector-project/planned",
        {"service_binding": SERVICE_BINDING, "source": PROOF_STATUS},
        resolved_at=generated_at,
        catalog_revision_or_etag=PROOF_STATUS,
    )
    virtual_server_ref = contracts.artifact_ref(
        f"contextforge://control-plane/virtual-servers/{spec['virtual_server']['name']}/planned",
        {"service_binding": SERVICE_BINDING, "virtual_server": spec["virtual_server"]["name"]},
        resolved_at=generated_at,
        catalog_revision_or_etag=PROOF_STATUS,
    )
    conformance_ref = contracts.artifact_ref(
        f"contextforge://control-plane/client-conformance/{target_client}/project-inspector/planned",
        {"service_binding": SERVICE_BINDING, "target_client": target_client, "source": PROOF_STATUS},
        resolved_at=generated_at,
        catalog_revision_or_etag=PROOF_STATUS,
    )
    consent_refs = _consent_refs(generated_at=generated_at, target_client=target_client)
    trace_refs = _trace_refs(generated_at=generated_at, target_client=target_client)
    stale_refs = [
        contract_ref,
        policy_ref,
        conformance_ref,
        contracts.artifact_ref(
            "contextforge://control-plane/stale-inputs/project-inspector-target-client-digest",
            {"target_client": target_client, "target_client_digest": target_client_digest},
            resolved_at=generated_at,
            catalog_revision_or_etag=PROOF_STATUS,
        ),
        contracts.artifact_ref(
            "contextforge://control-plane/stale-inputs/project-inspector-gateway-revision",
            {"gateway_revision": gateway_revision},
            resolved_at=generated_at,
            catalog_revision_or_etag=PROOF_STATUS,
        ),
    ]

    provision_plan = _build_provision_plan(
        project_root=project_root,
        spec=spec,
        stale_refs=stale_refs,
        consent_refs=consent_refs,
        trace_refs=trace_refs,
        policy_ref=policy_ref,
        conformance_ref=conformance_ref,
    )
    registration_intent = binding.build_contextforge_registration_intent(
        plan_id=provision_plan["provision_plan_id"],
        service_binding=SERVICE_BINDING,
        contract_card=contract_card,
        backend_manifest_ref=backend_manifest_ref,
        gateway_name=spec["contextforge_registration"]["gateway_name"],
        gateway_url=f"stdio://{spec['backend_instance']['slug']}",
        upstream_transport="stdio",
        consent_receipt_refs=consent_refs,
        stale_inputs={"gateway_revision": gateway_revision, "stale": False},
        generated_at=generated_at,
    )
    virtual_server_intent = binding.build_virtual_server_association_intent(
        plan_id=provision_plan["provision_plan_id"],
        service_binding=SERVICE_BINDING,
        contract_card=contract_card,
        virtual_server_name=spec["virtual_server"]["name"],
        gateway_ref=gateway_ref,
        semantic_tool_policy=semantic_policy,
        consent_receipt_refs=consent_refs,
        stale_inputs={"gateway_revision": gateway_revision, "stale": False},
        generated_at=generated_at,
    )
    conformance_placeholder = _planned_conformance(target_client=target_client, project_root=str(project_root))
    client_binding_intent = binding.build_client_binding_intent(
        plan_id=provision_plan["provision_plan_id"],
        project_root=str(Path(project_root).expanduser().resolve(strict=False)),
        service_binding=SERVICE_BINDING,
        target_client=target_client,
        virtual_server_ref=virtual_server_ref,
        semantic_tool_policy=semantic_policy,
        conformance_result=conformance_placeholder,
        consent_receipt_refs=consent_refs,
        negative_check_readbacks=[],
        trace_refs=[],
        expected_gateway_digest=gateway_revision,
        current_gateway_digest=gateway_revision,
        expected_client_digest=target_client_digest,
        current_client_digest=target_client_digest,
        generated_at=generated_at,
    )

    seed = {
        "schema_uri": "contextforge://control-plane/project-inspector-rfc-seed/v1",
        "seed_id": "project-inspector-rfc-seed",
        "seed_source": SEED_SOURCE,
        "generated_at": generated_at,
        "service_family": SERVICE_FAMILY,
        "service_binding": SERVICE_BINDING,
        "proof_status": PROOF_STATUS,
        "catalog_status": {
            "status": PROOF_STATUS,
            "catalog_candidate": False,
            "catalog_promotion_allowed": False,
            "service_management_override_required_for_status_change": True,
            "client_configs_are_discovery_sources_only": True,
        },
        "safety_contract": {
            "root_bound": True,
            "read_only": True,
            "external_secrets_required": False,
            "shell_execution_claimed": False,
            "raw_file_exfiltration_claimed": False,
            "catalog_promotion_allowed": False,
            "shared_canonical_identity_mutation_allowed": False,
            "user_global_trust_bundling_allowed": False,
        },
        "adapter_spec": spec,
        "contract_card": contract_card,
        "semantic_tool_policy": semantic_policy,
        "service_provision_plan": provision_plan,
        "contextforge_binding_intents": {
            "registration": registration_intent,
            "virtual_server_association": virtual_server_intent,
            "client_binding": client_binding_intent,
        },
        "refs": {
            "contract_card_ref": contract_ref,
            "semantic_tool_policy_ref": policy_ref,
            "consent_receipt_refs": consent_refs,
            "conformance_refs": [conformance_ref],
            "verification_trace_refs": trace_refs,
            "stale_input_refs": stale_refs,
        },
        "stale_input_expectations": {
            "reject_if_project_root_hash_changes": True,
            "reject_if_contract_card_digest_changes": True,
            "reject_if_semantic_policy_digest_changes": True,
            "reject_if_gateway_revision_changes": True,
            "reject_if_target_client_digest_changes": True,
            "fresh_approval_required_after_stale_consent_or_trace": True,
        },
        "recovery_behavior": {
            "registration_missing": "resume",
            "registration_stale": "forward_repair",
            "virtual_server_policy_mismatch": "forward_repair",
            "client_binding_config_conflict": "manual_recovery",
            "target_client_mismatch": "fresh_approval_required",
        },
        "non_mutation": {
            "mutation_allowed": False,
            "mutation_performed": False,
            "writes_performed": [],
            "forbidden_write_surfaces": [
                "backend home",
                "ContextForge API",
                "client config",
                "server-instances",
                ".project",
                ".codex",
                "trust state",
            ],
        },
    }
    contracts.validate_redacted(seed)
    return seed


def build_project_inspector_contract_card(
    *,
    adapter_spec: Mapping[str, Any],
    semantic_tool_policy: Mapping[str, Any],
    generated_at: str = DEFAULT_GENERATED_AT,
) -> dict[str, Any]:
    """Build the RFC-seeded service binding contract card."""

    project = adapter_spec["project_identity"]
    backend = adapter_spec["backend_instance"]
    virtual_server = adapter_spec["virtual_server"]
    gateway = adapter_spec["contextforge_registration"]
    backend_manifest_ref = contracts.artifact_ref(
        "contextforge://control-plane/backend-manifests/project-inspector-project/planned",
        {"service_binding": SERVICE_BINDING, "backend_home": backend["home"], "source": PROOF_STATUS},
        resolved_at=generated_at,
        catalog_revision_or_etag=PROOF_STATUS,
    )
    policy_ref = contracts.artifact_ref(
        "contextforge://control-plane/semantic-tool-policies/project-inspector-rfc-seed/v1",
        semantic_tool_policy,
        resolved_at=generated_at,
        catalog_revision_or_etag=PROOF_STATUS,
    )
    client_ref = contracts.artifact_ref(
        "contextforge://control-plane/client-adapters/codex/conformance/planned",
        {"target_client": adapter_spec["client_binding"]["target_client"], "service_binding": SERVICE_BINDING},
        resolved_at=generated_at,
        catalog_revision_or_etag=PROOF_STATUS,
    )
    card = {
        "card_id": "project-inspector-rfc-seed",
        "schema_uri": "contextforge://control-plane/schemas/service-binding-contract-card/v1",
        "service_family": SERVICE_FAMILY,
        "service_binding": SERVICE_BINDING,
        "instantiation_class": "instance_per_project",
        "authority_boundary": "RFC-seeded root-bound read-only project backend exposed through a project virtual server.",
        "project_scope": {
            "root": project["root"],
            "root_hash": project["root_hash"],
            "binding_mode": "canonical_root_bound",
            "scope_change_allowed": False,
        },
        "credential_scope": {
            "external_secrets_required": False,
            "secret_values_allowed": False,
            "placeholder_env_only": True,
        },
        "resource_scope": {
            "allowed": [
                "canonical root identity",
                "root hash",
                "symlink and nested-project relationships",
                "ignored path summaries",
                "marker files",
                "detected languages",
                "package manifests",
                "worktree status",
            ],
            "raw_file_content_export": False,
            "shell_execution": False,
        },
        "caller_or_session_scope": None,
        "backend_instance_ref": backend_manifest_ref,
        "contextforge_gateway": {
            "canonical_name": gateway["gateway_name"],
            "upstream_transport": gateway["upstream_transport"],
            "registration_path": gateway["registration_path"],
            "rfc_seeded": True,
        },
        "virtual_server": {
            "canonical_name": virtual_server["name"],
            "scope": "project",
            "tool_association_source": "compiled_semantic_tool_policy",
        },
        "client_adapter_refs": [client_ref],
        "semantic_tool_policy_ref": policy_ref,
        "transport_profile": {
            "native_transports": ["stdio"],
            "required_client_transports": ["streamable_http", "sse"],
            "bridge_mode": "stdio_to_http_sse",
            "package_bridge_ref": "python -m mcpgateway.translate --stdio ... --expose-sse --expose-streamable-http",
            "forbidden_bridge_effects": ["no native HTTP/SSE wrapping unless transport is missing"],
            "required_endpoint_verification": ["/mcp", "/sse"],
        },
        "required_consent_classes": ["service_provision", "project_local_config_write"],
        "verification_matrix": {
            "required_layers": ["backend", "contextforge_gateway", "virtual_server", "target_client", "tool_policy", "redaction"]
        },
        "non_actions": [
            "not a discovered catalog candidate",
            "no catalog promotion",
            "no shared canonical service identity mutation",
            "no user-global trust mutation",
            "no external secret values",
            "no shell execution claim",
            "no raw file exfiltration claim",
        ],
        "evidence_requirements": [
            "consent receipt refs",
            "semantic tool policy refs",
            "client conformance refs",
            "adapter-independent verification trace refs",
            "ContextForge gateway readback",
            "virtual server tool-policy readback",
            "target-client-visible proof after W9-B runtime exists",
        ],
        "x_seed_source": SEED_SOURCE,
        "x_proof_status": PROOF_STATUS,
        "x_catalog_candidate": False,
        "x_mutates_shared_canonical_identity": False,
    }
    contracts.validate_artifact("service_binding_contract_card", card)
    return card


class ProjectInspectorSeedError(ValueError):
    """Raised when the project-inspector seed cannot be built safely."""


def _build_provision_plan(
    *,
    project_root: str | Path,
    spec: Mapping[str, Any],
    stale_refs: list[dict[str, Any]],
    consent_refs: list[dict[str, Any]],
    trace_refs: list[dict[str, Any]],
    policy_ref: Mapping[str, Any],
    conformance_ref: Mapping[str, Any],
) -> dict[str, Any]:
    backend_home = provision.backend_home_path(project_root, SERVICE_BINDING)
    owned_write_set = [
        backend_home,
        f"{backend_home}/{provision.ENV_PLACEHOLDER_FILENAME}",
        f"{backend_home}/{provision.MANIFEST_FILENAME}",
        "user-systemd:contextforge-project-inspector-project.service",
    ]
    plan = provision.build_service_provision_plan(
        project_root=project_root,
        service_binding=SERVICE_BINDING,
        plan_id="provision-project-inspector-rfc-seed",
        backend_command=spec["backend_instance"]["command"],
        owned_write_set=owned_write_set,
        stale_input_refs=stale_refs,
        consent_receipt_refs=consent_refs,
        verification_trace_refs=trace_refs,
        ports=spec["backend_instance"]["ports"],
        readiness_probes=spec["backend_instance"]["readiness_probes"],
        required_env=spec["backend_instance"]["required_env"],
        optional_env=spec["backend_instance"]["optional_env"],
        systemd_description="ContextForge RFC-seeded project-inspector proof service",
        policy_refs=[policy_ref],
        conformance_refs=[conformance_ref],
        upstream={
            "seed_source": SEED_SOURCE,
            "proof_status": PROOF_STATUS,
            "runtime_behavior_owner": "W9-B",
            "external_secrets_required": False,
        },
    )
    plan["x_rfc_seeded_proof"] = True
    plan["x_catalog_candidate"] = False
    plan["x_service_management_override_required_for_catalog_status_change"] = True
    plan["x_seed_only_no_runtime_tool_behavior"] = True
    contracts.validate_artifact("service_provision_plan", plan)
    return plan


def _consent_refs(*, generated_at: str, target_client: str) -> list[dict[str, Any]]:
    return [
        {
            **contracts.artifact_ref(
                "contextforge://control-plane/consent-receipts/project-inspector/service-provision/planned",
                {"service_binding": SERVICE_BINDING, "consent_class": "service_provision", "target_client": target_client},
                resolved_at=generated_at,
                catalog_revision_or_etag=PROOF_STATUS,
            ),
            "x_consent_class": "service_provision",
        },
        {
            **contracts.artifact_ref(
                "contextforge://control-plane/consent-receipts/project-inspector/project-local-config/planned",
                {"service_binding": SERVICE_BINDING, "consent_class": "project_local_config_write", "target_client": target_client},
                resolved_at=generated_at,
                catalog_revision_or_etag=PROOF_STATUS,
            ),
            "x_consent_class": "project_local_config_write",
        },
    ]


def _trace_refs(*, generated_at: str, target_client: str) -> list[dict[str, Any]]:
    refs = []
    for layer in adapter.REQUIRED_TRACE_LAYERS:
        refs.append(
            {
                **contracts.artifact_ref(
                    f"contextforge://control-plane/verification-traces/project-inspector/{layer}/planned",
                    {"service_binding": SERVICE_BINDING, "layer": layer, "target_client": target_client},
                    resolved_at=generated_at,
                    catalog_revision_or_etag=PROOF_STATUS,
                ),
                "x_verification_layer": layer,
                "x_target_client": target_client if layer == "target_client" else None,
                "x_result": "planned",
            }
        )
    return refs


def _planned_conformance(*, target_client: str, project_root: str) -> dict[str, Any]:
    return {
        "pack_id": f"{target_client}/project-inspector/planned",
        "client_name": target_client,
        "status": "planned",
        "decision": "block_target_client_proof",
        "project_root": str(Path(project_root).expanduser().resolve(strict=False)),
        "service_binding": SERVICE_BINDING,
        "blockers": [{"name": "runtime_not_implemented", "message": "W9-B owns project-inspector runtime behavior."}],
        "redaction_status": "passed",
    }


def clone_seed(seed: Mapping[str, Any]) -> dict[str, Any]:
    """Return a defensive JSON-compatible copy of a seed bundle."""

    return copy.deepcopy(dict(seed))
