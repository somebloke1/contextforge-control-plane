from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import control_plane_contracts as contracts
import control_plane_service_classifier as classifier


FIXTURE_PATH = REPO_ROOT / "tests/fixtures/control_plane_service_classification_cases.json"


class ControlPlaneServiceClassificationFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with FIXTURE_PATH.open("r", encoding="utf-8") as handle:
            cls.fixture = json.load(handle)
        cls.project_root = cls.fixture["project_root"]
        cls.cases = {case["name"]: case for case in cls.fixture["cases"]}

    def classify(self, name: str) -> dict[str, Any]:
        case = self.cases[name]
        return classifier.classify_service_binding(
            case["descriptor"],
            project_root=self.project_root,
            resolved_at=self.fixture["resolved_at"],
        )

    def assert_valid_contract_card(self, result: dict[str, Any]) -> dict[str, Any]:
        contract = result["contract_card_draft"]
        self.assertIsInstance(contract, dict)
        contracts.validate_artifact("service_binding_contract_card", contract)
        return contract

    def assert_no_project_specific_shared_effects(self, result: dict[str, Any]) -> None:
        self.assertFalse(result["mutation_allowed"])
        self.assertIn("no per-project backend", result["non_actions"])
        self.assertIn("no per-project gateway", result["non_actions"])
        self.assertIn("no per-project bridge", result["non_actions"])
        self.assertIn("no per-project wrapper", result["non_actions"])
        self.assertIn("no per-project port", result["non_actions"])
        self.assertIn("no per-project unit", result["non_actions"])
        self.assertIn("no per-project server-instance directory", result["non_actions"])

    def test_fixture_names_and_evidence_are_present(self) -> None:
        expected = {
            "context7_real_shared_canonical_capsule",
            "ssh_tmux_session_scoped_availability",
            "mentality_static_repo_local_governance",
            "serena_cf_controlplane_instance_per_project_fixture_only",
            "catalog_candidate_pi_web_access_handoff",
            "ambiguous_docs_service_blocks_mutation",
        }
        self.assertEqual(expected, set(self.cases))
        for case in self.cases.values():
            with self.subTest(case=case["name"]):
                self.assertIn("descriptor", case)
                self.assertTrue(case["evidence"]["source_paths"])
                for source_path in case["evidence"]["source_paths"]:
                    self.assertTrue((REPO_ROOT / source_path).exists(), source_path)

    def test_context7_real_shared_canonical_case_emits_valid_capsule(self) -> None:
        case = self.cases["context7_real_shared_canonical_capsule"]
        self.assertIn("server-instances/context7/instance.json", case["evidence"]["source_paths"])

        result = self.classify("context7_real_shared_canonical_capsule")

        self.assertEqual("classified", result["status"])
        self.assertEqual("shared_canonical", result["instantiation_class"])
        self.assertEqual("context7", result["service_family"])
        self.assertEqual("context7", result["canonical_service"])
        self.assertEqual("context7:canonical", result["service_binding"])
        self.assert_no_project_specific_shared_effects(result)
        self.assertEqual("stdio_to_http_sse", result["transport_profile"]["bridge_mode"])
        self.assertIsNotNone(result["transport_profile"]["package_bridge_ref"])
        self.assertIn("do not wrap transports beyond the missing required side", result["non_actions"])
        self.assertEqual({"mode": "availability_binding_only"}, result["project_scope"])

        contract = self.assert_valid_contract_card(result)
        self.assertEqual("shared_canonical", contract["instantiation_class"])
        self.assertEqual(["read_only_inspection"], contract["required_consent_classes"])

        capsule = result["shared_service_capability_capsule"]
        self.assertIsInstance(capsule, dict)
        contracts.validate_artifact("shared_service_capability_capsule", capsule)
        self.assertEqual("context7", capsule["canonical_service"])
        self.assertEqual(
            {
                "new_backend",
                "new_gateway",
                "new_bridge",
                "new_wrapper",
                "new_port",
                "new_unit",
                "server_instance_directory",
                "catalog_mutation",
            },
            set(capsule["forbidden_project_init_effects"]),
        )
        self.assertIn("codex_context7_alias", result["identity"]["client_aliases_ignored"])
        self.assertNotIn("codex", result["service_binding"])

    def test_ssh_tmux_is_session_scoped_without_project_ownership(self) -> None:
        result = self.classify("ssh_tmux_session_scoped_availability")

        contract = self.assert_valid_contract_card(result)
        self.assertEqual("classified", result["status"])
        self.assertEqual("session_scoped", result["instantiation_class"])
        self.assertEqual("session_scoped", contract["instantiation_class"])
        self.assertIsNone(contract["project_scope"])
        self.assertIsNone(result["shared_service_capability_capsule"])
        self.assertFalse(result["mutation_allowed"])
        self.assertIn("do not claim durable project ownership of the live caller/session", result["non_actions"])
        self.assertEqual("active shell tmux session", contract["caller_or_session_scope"]["authority"])
        self.assertEqual("remote target and path arguments", contract["caller_or_session_scope"]["resource_scope"])
        self.assertEqual("local host tmux process", contract["caller_or_session_scope"]["host_scope"])
        self.assertIn("verify live caller/session authority without claiming project ownership", result["verification_requirements"])

    def test_mentality_is_static_repo_local_and_governance_scoped(self) -> None:
        result = self.classify("mentality_static_repo_local_governance")

        contract = self.assert_valid_contract_card(result)
        self.assertEqual("classified", result["status"])
        self.assertEqual("static_repo_local", result["instantiation_class"])
        self.assertEqual("static_repo_local", contract["instantiation_class"])
        self.assertEqual(self.project_root, contract["project_scope"]["project_root"])
        self.assertEqual("repo_governance", contract["project_scope"]["scope_type"])
        self.assertIsNone(result["shared_service_capability_capsule"])
        self.assertFalse(result["mutation_allowed"])
        self.assertIn("do not let client-local memory supersede governance ledgers", result["non_actions"])

    def test_serena_is_instance_per_project_but_fixture_only(self) -> None:
        result = self.classify("serena_cf_controlplane_instance_per_project_fixture_only")

        contract = self.assert_valid_contract_card(result)
        self.assertEqual("classified", result["status"])
        self.assertEqual("instance_per_project", result["instantiation_class"])
        self.assertEqual("instance_per_project", contract["instantiation_class"])
        self.assertEqual(self.project_root, contract["project_scope"]["project_root"])
        self.assertIn("service_provision", contract["required_consent_classes"])
        self.assertFalse(result["mutation_allowed"])
        self.assertIsNone(result["shared_service_capability_capsule"])
        self.assertEqual("http_to_sse", result["transport_profile"]["bridge_mode"])

    def test_catalog_candidate_emits_handoff_and_stops(self) -> None:
        result = self.classify("catalog_candidate_pi_web_access_handoff")

        self.assertEqual("handoff_required", result["status"])
        self.assertEqual("candidate_or_uncataloged_backend", result["instantiation_class"])
        self.assertFalse(result["mutation_allowed"])
        self.assertFalse(result["durable_project_state_record_allowed"])
        self.assertIsNone(result["contract_card_draft"])
        self.assertIsNone(result["shared_service_capability_capsule"])
        self.assertIn("do not create project-state service record", result["non_actions"])
        self.assertIn("do not register ContextForge gateway", result["non_actions"])
        self.assertIn("do not provision backend", result["non_actions"])

        handoff = result["service_management_handoff"]
        self.assertIsInstance(handoff, dict)
        contracts.validate_artifact("service_management_handoff", handoff)
        self.assertEqual("candidate_or_uncataloged_backend", handoff["suspected_instantiation_class"])
        self.assertIn("project_state_service_record", handoff["forbidden_under_current_approval"])
        self.assertIn("contextforge_registration", handoff["forbidden_under_current_approval"])
        self.assertIn("backend_provision", handoff["forbidden_under_current_approval"])

    def test_ambiguous_classification_blocks_mutation(self) -> None:
        result = self.classify("ambiguous_docs_service_blocks_mutation")

        self.assertEqual("blocked", result["status"])
        self.assertEqual("blocked", result["confidence"])
        self.assertFalse(result["mutation_allowed"])
        self.assertFalse(result["durable_project_state_record_allowed"])
        self.assertIsNone(result["contract_card_draft"])
        self.assertIsNone(result["shared_service_capability_capsule"])
        self.assertIsNone(result["service_management_handoff"])
        self.assertIn("do not mutate project state", result["non_actions"])
        self.assertIn("do not provision backend", result["non_actions"])
        self.assertIn("do not register ContextForge service", result["non_actions"])
        self.assertIn("instantiation_class_ambiguous", {blocker["type"] for blocker in result["blockers"]})


if __name__ == "__main__":
    unittest.main()
