from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import control_plane_contextforge_binding as binding
import control_plane_contracts as contracts


PROJECT_ROOT = "/home/dgk/workspace/context-portal"
STAMP = "2026-05-30T22:00:00Z"


def contract_card(*, instantiation_class: str = "instance_per_project", mutates_shared: bool = False) -> dict[str, Any]:
    return {
        "card_id": "project-inspector-context-portal",
        "schema_uri": "contextforge://control-plane/schemas/service-binding-contract-card/v1",
        "service_family": "project-inspector",
        "service_binding": "project-inspector:context-portal",
        "instantiation_class": instantiation_class,
        "authority_boundary": "project root bound backend and ContextForge virtual server",
        "project_scope": {"root": PROJECT_ROOT},
        "credential_scope": None,
        "resource_scope": None,
        "caller_or_session_scope": None,
        "backend_instance_ref": ref("backend-manifests/project-inspector-context-portal"),
        "contextforge_gateway": {"canonical_name": "project-inspector-context-portal"},
        "virtual_server": {"canonical_name": "project-inspector-context-portal-codex"},
        "client_adapter_refs": [ref("client-adapters/codex-v1")],
        "semantic_tool_policy_ref": ref("semantic-tool-policies/project-inspector-context-portal"),
        "transport_profile": {
            "native_transports": ["streamable_http", "sse"],
            "required_endpoint_verification": ["/mcp", "/sse"],
            "bridge_required": False,
        },
        "required_consent_classes": ["service_provision", "project_local_config_write"],
        "verification_matrix": {
            "required_layers": ["backend", "contextforge_gateway", "virtual_server", "target_client", "tool_policy", "redaction"]
        },
        "non_actions": ["no catalog promotion", "no user-global trust mutation"],
        "evidence_requirements": ["gateway readback", "virtual server tool readback", "target-client proof"],
        "x_mutates_shared_canonical_identity": mutates_shared,
    }


def semantic_policy(*, status: str = "compiled", target_client: str = "codex", stale: bool = False) -> dict[str, Any]:
    return {
        "policy_id": "project-inspector-policy",
        "schema_uri": "contextforge://control-plane/schemas/semantic-tool-policy/v1",
        "service_binding": "project-inspector:context-portal",
        "risk_classes": ["read_only"],
        "scope_impacts": ["none"],
        "approval_gates": [],
        "allowed_tool_selectors": [{"selector_type": "tool_id", "value": "cf-tool-root-info", "fail_closed": True}],
        "excluded_tool_selectors": [{"selector_type": "tool_id", "value": "cf-tool-set-root", "fail_closed": True}],
        "manual_overrides": [],
        "compiled_tool_ids": ["cf-tool-root-info"],
        "negative_checks": negative_checks(status="pending"),
        "last_compiled_at": STAMP,
        "last_readback_trace_ref": None,
        "x_compiler_version": 1,
        "x_status": status,
        "x_virtual_server_id": "vs-project-inspector",
        "x_target_client": target_client,
        "x_allowed_tools": [],
        "x_excluded_tools": [],
        "x_blockers": [] if status == "compiled" else [{"type": "missing_risk_metadata", "message": "blocked"}],
        "x_open_items": [],
        "x_repair_plan_trigger": status != "compiled",
        "x_stale_policy_inputs": {
            "expected_gateway_revision": "gw-r1",
            "current_gateway_revision": "gw-r2" if stale else "gw-r1",
            "expected_target_client_digest": "sha256:client-r1",
            "current_target_client_digest": "sha256:client-r1",
            "stale": stale,
        },
    }


def conformance(*, status: str = "passing_conformance", client_name: str = "codex") -> dict[str, Any]:
    return {
        "pack_id": "codex/v1",
        "client_name": client_name,
        "status": status,
        "decision": "allow_target_client_proof" if status == "passing_conformance" else "block_target_client_proof",
        "project_root": PROJECT_ROOT,
        "service_binding": "project-inspector:context-portal",
        "blockers": [] if status == "passing_conformance" else [{"name": "list_tools_proof", "message": "missing"}],
        "generated_at": STAMP,
        "redaction_status": "passed",
    }


def negative_checks(*, status: str = "passed") -> list[dict[str, Any]]:
    return [
        {
            "check": "excluded_tool_absent",
            "layer": "contextforge_virtual_server",
            "probe": "readback_server_tools",
            "service_binding": "project-inspector:context-portal",
            "virtual_server_id": "vs-project-inspector",
            "target_client": None,
            "tool_id": "cf-tool-set-root",
            "original_name": "set_root",
            "exposed_name": "set_root",
            "negative_match_names": ["set_root"],
            "risk_classes": ["scope_changing"],
            "expected": "absent",
            "status": status,
        },
        {
            "check": "excluded_tool_absent",
            "layer": "target_client",
            "probe": "list_tools_and_call_tool",
            "service_binding": "project-inspector:context-portal",
            "virtual_server_id": "vs-project-inspector",
            "target_client": "codex",
            "tool_id": "cf-tool-set-root",
            "original_name": "set_root",
            "exposed_name": "set_root",
            "negative_match_names": ["set_root"],
            "risk_classes": ["scope_changing"],
            "expected": "absent",
            "status": status,
        },
        {
            "check": "compiled_association_exact_match",
            "layer": "contextforge_virtual_server",
            "probe": "readback_server_tools",
            "service_binding": "project-inspector:context-portal",
            "virtual_server_id": "vs-project-inspector",
            "expected_tool_ids": ["cf-tool-root-info"],
            "status": status,
        },
    ]


def receipt_refs(*, include_forbidden: bool = False) -> list[dict[str, Any]]:
    refs = [
        {**ref("receipts/service-provision"), "consent_class": "service_provision"},
        {**ref("receipts/project-local-config"), "consent_class": "project_local_config_write"},
    ]
    if include_forbidden:
        refs.append({**ref("receipts/trust"), "consent_class": "user_global_client_trust"})
    return refs


def trace_refs(*, target_client: str = "codex") -> list[dict[str, Any]]:
    return [
        {**ref(f"traces/{layer}"), "layer": layer, "target_client": target_client if layer == "target_client" else None, "result": "passed"}
        for layer in ["contextforge_gateway", "virtual_server", "tool_policy", "target_client", "redaction"]
    ]


def ref(name: str) -> dict[str, Any]:
    return {
        "ref": f"contextforge://control-plane/{name}",
        "content_digest": "sha256:" + binding.stable_digest({"name": name})[7:],
        "catalog_revision_or_etag": None,
        "resolved_at": STAMP,
    }


class ControlPlaneContextForgeBindingTests(unittest.TestCase):
    def test_registration_intent_preserves_contextforge_as_authority(self) -> None:
        intent = binding.build_contextforge_registration_intent(
            plan_id="plan-project-inspector",
            service_binding="project-inspector:context-portal",
            contract_card=contract_card(),
            backend_manifest_ref=ref("backend-manifests/project-inspector-context-portal"),
            gateway_name="project-inspector-context-portal",
            gateway_url="http://127.0.0.1:7890/mcp",
            upstream_transport="streamable_http",
            consent_receipt_refs=receipt_refs(),
            generated_at=STAMP,
        )

        self.assertEqual("intend", intent["decision"])
        self.assertEqual("ContextForge", intent["contextforge_authority"]["canonical_registry"])
        self.assertFalse(intent["contextforge_authority"]["client_configs_are_service_identities"])
        self.assertIn("does not call ContextForge APIs", intent["non_actions"])
        self.assertEqual(["contextforge:gateways"], intent["write_set"])

    def test_virtual_server_association_uses_compiled_policy_and_trace_requirements(self) -> None:
        intent = binding.build_virtual_server_association_intent(
            plan_id="plan-project-inspector",
            service_binding="project-inspector:context-portal",
            contract_card=contract_card(),
            virtual_server_name="project-inspector-context-portal-codex",
            gateway_ref=ref("gateways/project-inspector-context-portal"),
            semantic_tool_policy=semantic_policy(),
            consent_receipt_refs=receipt_refs(),
            generated_at=STAMP,
        )

        self.assertEqual("intend", intent["decision"])
        self.assertEqual(["cf-tool-root-info"], intent["virtual_server_update"]["associated_tool_ids"])
        self.assertEqual("compiled_semantic_tool_policy", intent["virtual_server_update"]["association_source"])
        self.assertIn("tool_policy", intent["trace_requirements"]["required_layers"])

    def test_client_binding_intent_is_allowed_only_after_all_gates_pass(self) -> None:
        intent = self.client_binding_intent()

        self.assertEqual("intend", intent["decision"])
        self.assertTrue(intent["eligible_for_client_visible_binding"])
        self.assertEqual(".codex/config.toml", intent["binding_intent"]["surface"])
        self.assertIn("does not write client config", intent["non_actions"])

        hook = binding.build_client_write_hook_preflight(
            client_binding_intent=intent,
            owned_block_class="owned",
            config_scope="project_local",
        )
        self.assertEqual("allow_owned_project_local_write", hook["decision"])
        self.assertFalse(hook["non_actions"] == [])

    def test_missing_or_failed_policy_and_conformance_block_client_binding(self) -> None:
        blocked_policy = self.client_binding_intent(policy=semantic_policy(status="blocked"))
        failed_conformance = self.client_binding_intent(conformance_result=conformance(status="failed_conformance"))

        self.assertEqual("block", blocked_policy["decision"])
        self.assertIn("semantic_tool_policy_not_compiled", blocker_types(blocked_policy))
        self.assertIn("missing_risk_metadata", blocker_types(blocked_policy))
        self.assertEqual("block", failed_conformance["decision"])
        self.assertIn("failed_conformance", blocker_types(failed_conformance))
        self.assertIn("list_tools_proof", blocker_types(failed_conformance))

    def test_missing_or_failed_negative_check_readback_blocks(self) -> None:
        missing = self.client_binding_intent(readbacks=[])
        failed = self.client_binding_intent(readbacks=negative_checks(status="failed"))

        self.assertEqual("block", missing["decision"])
        self.assertIn("missing_negative_check_readback", blocker_types(missing))
        self.assertEqual("block", failed["decision"])
        self.assertIn("failed_negative_check_readback", blocker_types(failed))

    def test_stale_inputs_and_target_client_mismatch_block(self) -> None:
        stale_gateway = self.client_binding_intent(current_gateway_digest="sha256:changed")
        stale_client = self.client_binding_intent(current_client_digest="sha256:changed")
        wrong_policy_client = self.client_binding_intent(policy=semantic_policy(target_client="claude"))
        wrong_conformance_client = self.client_binding_intent(conformance_result=conformance(client_name="claude"))

        self.assertIn("stale_gateway_digest", blocker_types(stale_gateway))
        self.assertIn("stale_client_digest", blocker_types(stale_client))
        self.assertIn("target_client_mismatch", blocker_types(wrong_policy_client))
        self.assertIn("target_client_mismatch", blocker_types(wrong_conformance_client))

    def test_catalog_promotion_shared_identity_mutation_and_global_trust_bundling_block(self) -> None:
        promotion = binding.build_contextforge_registration_intent(
            plan_id="plan-project-inspector",
            service_binding="project-inspector:context-portal",
            contract_card=contract_card(),
            backend_manifest_ref=ref("backend-manifests/project-inspector-context-portal"),
            gateway_name="project-inspector-context-portal",
            gateway_url="http://127.0.0.1:7890/mcp",
            upstream_transport="streamable_http",
            requested_operation_class="catalog_promotion",
            generated_at=STAMP,
        )
        shared_mutation = binding.build_virtual_server_association_intent(
            plan_id="plan-project-inspector",
            service_binding="project-inspector:context-portal",
            contract_card=contract_card(instantiation_class="shared_canonical", mutates_shared=True),
            virtual_server_name="project-inspector-context-portal-codex",
            gateway_ref=ref("gateways/project-inspector-context-portal"),
            semantic_tool_policy=semantic_policy(),
            generated_at=STAMP,
        )
        bundled_trust = self.client_binding_intent(receipts=receipt_refs(include_forbidden=True))

        self.assertEqual("block", promotion["decision"])
        self.assertIn("catalog_promotion_requested", blocker_types(promotion))
        self.assertEqual("block", shared_mutation["decision"])
        self.assertIn("shared_canonical_identity_mutation", blocker_types(shared_mutation))
        self.assertIn("not_project_scoped_service", blocker_types(shared_mutation))
        self.assertEqual("block", bundled_trust["decision"])
        self.assertIn("user_global_trust_bundled", blocker_types(bundled_trust))

    def test_client_write_hook_blocks_conflicts_global_scope_and_trust_mutation(self) -> None:
        intent = self.client_binding_intent()
        preflight = binding.build_client_write_hook_preflight(
            client_binding_intent=intent,
            owned_block_class="unmanaged_same_name",
            config_scope="user_global",
            trust_mutation_requested=True,
        )

        self.assertEqual("block", preflight["decision"])
        self.assertIn("client_config_conflict", blocker_types(preflight))
        self.assertIn("user_global_config_write_requested", blocker_types(preflight))
        self.assertIn("user_global_trust_bundled", blocker_types(preflight))

    def test_recovery_classifications_are_typed_for_later_fixtures(self) -> None:
        self.assertEqual("resume", binding.classify_recovery("registration_missing")["recovery_outcome"])
        self.assertEqual("forward_repair", binding.classify_recovery("virtual_server_policy_mismatch")["recovery_outcome"])
        self.assertEqual("manual_recovery", binding.classify_recovery("client_binding_config_conflict")["recovery_outcome"])
        self.assertEqual("fresh_approval_required", binding.classify_recovery("target_client_mismatch")["recovery_outcome"])
        self.assertIn("rollback_by_approved_workflow", binding.classify_recovery("unknown")["allowed_outcomes"])

    def test_helpers_are_deterministic_and_do_not_mutate_inputs(self) -> None:
        policy = semantic_policy()
        policy_before = copy.deepcopy(policy)
        intent_one = self.client_binding_intent(policy=policy)
        intent_two = self.client_binding_intent(policy=policy)

        self.assertEqual(intent_one, intent_two)
        self.assertEqual(policy_before, policy)
        contracts.validate_redacted(intent_one, require_status=True)

    def client_binding_intent(
        self,
        *,
        policy: dict[str, Any] | None = None,
        conformance_result: dict[str, Any] | None = None,
        receipts: list[dict[str, Any]] | None = None,
        readbacks: list[dict[str, Any]] | None = None,
        current_gateway_digest: str = "sha256:gateway-r1",
        current_client_digest: str = "sha256:client-r1",
    ) -> dict[str, Any]:
        return binding.build_client_binding_intent(
            plan_id="plan-project-inspector",
            project_root=PROJECT_ROOT,
            service_binding="project-inspector:context-portal",
            target_client="codex",
            virtual_server_ref=ref("virtual-servers/project-inspector-context-portal-codex"),
            semantic_tool_policy=policy or semantic_policy(),
            conformance_result=conformance_result or conformance(),
            consent_receipt_refs=receipts or receipt_refs(),
            negative_check_readbacks=readbacks if readbacks is not None else negative_checks(status="passed"),
            trace_refs=trace_refs(),
            expected_gateway_digest="sha256:gateway-r1",
            current_gateway_digest=current_gateway_digest,
            expected_client_digest="sha256:client-r1",
            current_client_digest=current_client_digest,
            generated_at=STAMP,
        )


def blocker_types(result: Mapping[str, Any]) -> set[str]:
    return {str(item["type"]) for item in result["blockers"]}


if __name__ == "__main__":
    unittest.main()
