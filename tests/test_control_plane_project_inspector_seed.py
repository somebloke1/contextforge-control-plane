from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import control_plane_contracts as contracts
import control_plane_project_inspector_seed as seed


PROJECT_ROOT = "/home/dgk/workspace/context-portal"
STAMP = "2026-05-30T20:21:54Z"


class ControlPlaneProjectInspectorSeedTests(unittest.TestCase):
    def project_inspector_seed(self) -> dict[str, object]:
        return seed.build_project_inspector_seed(project_root=PROJECT_ROOT, generated_at=STAMP)

    def test_seed_status_is_rfc_seeded_proof_not_catalog_candidate_or_promotion(self) -> None:
        result = self.project_inspector_seed()
        catalog_status = result["catalog_status"]

        self.assertEqual("project-inspector", result["service_family"])
        self.assertEqual("project-inspector:project", result["service_binding"])
        self.assertEqual("rfc_seeded_proof", result["proof_status"])
        self.assertEqual("rfc_seeded_proof", catalog_status["status"])
        self.assertFalse(catalog_status["catalog_candidate"])
        self.assertFalse(catalog_status["catalog_promotion_allowed"])
        self.assertTrue(catalog_status["service_management_override_required_for_status_change"])
        self.assertNotEqual("candidate_or_uncataloged_backend", result["contract_card"]["instantiation_class"])

        operation_classes = {step["operation_class"] for step in result["service_provision_plan"]["service_provision_steps"]}
        self.assertNotIn("catalog_promotion", operation_classes)
        self.assertNotIn("user_global_client_trust", operation_classes)

    def test_contract_card_and_provision_plan_use_generic_project_scoped_path(self) -> None:
        result = self.project_inspector_seed()
        card = result["contract_card"]
        plan = result["service_provision_plan"]
        intents = result["contextforge_binding_intents"]

        contracts.validate_artifact("service_binding_contract_card", card)
        contracts.validate_artifact("service_provision_plan", plan)
        self.assertEqual("instance_per_project", card["instantiation_class"])
        self.assertEqual("project-inspector:project", plan["service_binding"])
        self.assertTrue(plan["x_rfc_seeded_proof"])
        self.assertTrue(plan["x_seed_only_no_runtime_tool_behavior"])
        self.assertIn("server-instances/project-inspector-project", plan["x_backend_home"])
        self.assertEqual("intend", intents["registration"]["decision"])
        self.assertEqual("intend", intents["virtual_server_association"]["decision"])
        self.assertEqual("block", intents["client_binding"]["decision"])
        self.assertIn("failed_conformance", {item["type"] for item in intents["client_binding"]["blockers"]})

    def test_root_bound_read_only_no_secrets_shell_exfiltration_or_global_trust(self) -> None:
        result = self.project_inspector_seed()
        safety = result["safety_contract"]
        card = result["contract_card"]
        spec = result["adapter_spec"]
        manifest = result["service_provision_plan"]["x_desired_artifacts"]["backend_manifest"]["content"]

        self.assertTrue(safety["root_bound"])
        self.assertTrue(safety["read_only"])
        self.assertFalse(safety["external_secrets_required"])
        self.assertFalse(safety["shell_execution_claimed"])
        self.assertFalse(safety["raw_file_exfiltration_claimed"])
        self.assertFalse(safety["shared_canonical_identity_mutation_allowed"])
        self.assertFalse(safety["user_global_trust_bundling_allowed"])
        self.assertEqual([], spec["backend_instance"]["required_env"])
        self.assertEqual([], spec["backend_instance"]["optional_env"])
        self.assertEqual([], manifest["env"]["required"])
        self.assertEqual([], manifest["env"]["optional"])
        self.assertFalse(card["resource_scope"]["raw_file_content_export"])
        self.assertFalse(card["resource_scope"]["shell_execution"])
        self.assertIn("no user-global trust mutation", card["non_actions"])
        contracts.validate_redacted(result)

    def test_refs_cover_consent_policy_conformance_traces_and_stale_inputs(self) -> None:
        result = self.project_inspector_seed()
        refs = result["refs"]

        self.assertEqual("contextforge://control-plane/service-bindings/project-inspector-rfc-seed/v1", refs["contract_card_ref"]["ref"])
        self.assertEqual("contextforge://control-plane/semantic-tool-policies/project-inspector-rfc-seed/v1", refs["semantic_tool_policy_ref"]["ref"])
        self.assertEqual(
            {"service_provision", "project_local_config_write"},
            {item["x_consent_class"] for item in refs["consent_receipt_refs"]},
        )
        self.assertEqual(1, len(refs["conformance_refs"]))
        self.assertIn("/project-inspector/planned", refs["conformance_refs"][0]["ref"])
        self.assertEqual(
            {"backend", "contextforge_gateway", "virtual_server", "tool_policy", "target_client", "redaction"},
            {item["x_verification_layer"] for item in refs["verification_trace_refs"]},
        )
        self.assertTrue(result["stale_input_expectations"]["reject_if_contract_card_digest_changes"])
        self.assertTrue(result["stale_input_expectations"]["reject_if_gateway_revision_changes"])
        self.assertGreaterEqual(len(refs["stale_input_refs"]), 5)

    def test_seed_builder_is_deterministic_and_non_mutating(self) -> None:
        first = self.project_inspector_seed()
        first_before = copy.deepcopy(first)
        second = self.project_inspector_seed()

        self.assertEqual(first, second)
        self.assertEqual(first_before, first)
        self.assertFalse(first["non_mutation"]["mutation_allowed"])
        self.assertFalse(first["non_mutation"]["mutation_performed"])
        self.assertEqual([], first["non_mutation"]["writes_performed"])
        self.assertIn(".project", first["non_mutation"]["forbidden_write_surfaces"])
        self.assertIn(".codex", first["non_mutation"]["forbidden_write_surfaces"])
        self.assertFalse((REPO_ROOT / "server-instances/project-inspector-project").exists())

    def test_project_inspector_policy_allows_only_read_only_seed_tools(self) -> None:
        result = self.project_inspector_seed()
        policy = result["semantic_tool_policy"]

        self.assertEqual("compiled", policy["x_status"])
        self.assertEqual(["project-inspector-languages", "project-inspector-root"], policy["compiled_tool_ids"])
        self.assertEqual([], policy["x_excluded_tools"])
        self.assertEqual({"read_only"}, set(policy["risk_classes"]))
        for tool in policy["x_allowed_tools"]:
            self.assertEqual(["read_only"], tool["semantic_risk_classes"])
            self.assertEqual(["project_bound_read"], tool["scope_impacts"])


if __name__ == "__main__":
    unittest.main()
