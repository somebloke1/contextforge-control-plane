from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import control_plane_contracts as contracts
import control_plane_language_profiles as language_profiles
import control_plane_project_planner as planner
import control_plane_service_handoffs as handoffs
import control_plane_service_management as management
import control_plane_service_memory as memory


FIXTURE_PATH = REPO_ROOT / "tests/fixtures/control_plane_service_management_cases.json"


class ControlPlaneServiceManagementFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with FIXTURE_PATH.open("r", encoding="utf-8") as handle:
            cls.fixture = json.load(handle)
        cls.project_root = cls.fixture["project_root"]
        cls.resolved_at = cls.fixture["resolved_at"]

    def ref(self, name: str) -> dict[str, Any]:
        return copy.deepcopy(self.fixture["artifact_refs"][name])

    def handoff_for(self, descriptor_key: str = "candidate_descriptor") -> dict[str, Any]:
        return handoffs.build_catalog_candidate_handoff(
            copy.deepcopy(self.fixture[descriptor_key]),
            project_root=self.project_root,
        )

    def test_fixture_payloads_are_deterministic_sanitized_and_contract_valid(self) -> None:
        contracts.validate_redacted(self.fixture)
        contracts.validate_artifact("governance_reconciliation_pack", self.fixture["governance_reconciliation_pack"])
        self.assertEqual(1, self.fixture["version"])
        self.assertNotIn("serena", json.dumps(self.fixture).lower())

    def test_service_memory_metadata_and_governance_records_are_advisory_only(self) -> None:
        provider = memory.build_service_memory_provider_metadata(**self.fixture["service_memory_provider_input"])
        contracts.validate_artifact("service_memory_provider", provider)

        reference = memory.build_governance_reference(
            provider,
            "dec-20260530-1001",
            summary="Canonical service binding requires service-management completion.",
        )
        proposal = memory.build_governance_proposal(
            provider,
            proposal_type="open_question",
            summary="Review whether a service-memory note should become a governance update.",
            governance_ids=["oq-20260530-1001"],
        )
        conflict = memory.flag_governance_conflict(
            provider,
            governance_id="ai-20260530-1001",
            memory_summary="Local note says the catalog promotion is complete.",
            governance_summary="Governance ledger still requires verification.",
        )

        self.assertTrue(provider["advisory_only"])
        self.assertFalse(provider["governance_reference_policy"]["generated_governance_projection_allowed"])
        self.assertEqual("governance_ledger", provider["conflict_flag_behavior"]["authority"])
        for record in (reference, proposal, conflict, conflict["proposal"]):
            self.assertTrue(record["advisory_only"])
            self.assertFalse(record["settles_governance"])
            self.assertFalse(record["mutates_governance"])
            self.assertIn("edit_governance_ledgers", record["forbidden_effects"])

    def test_service_management_plan_uses_contextforge_apis_without_db_or_unneeded_bridge(self) -> None:
        candidate_handoff = self.handoff_for()
        original = copy.deepcopy(candidate_handoff)

        result = management.plan_service_management_from_handoff(
            candidate_handoff,
            contract_card_refs=[self.ref("contract_card")],
            semantic_tool_policy_refs=[self.ref("policy")],
            catalog_revision=self.fixture["expected"]["catalog_revision"],
            generated_at=self.resolved_at,
        )

        contracts.validate_artifact("service_management_result", result)
        self.assertEqual(original, candidate_handoff)
        self.assertEqual("plan_only", result["status"])
        self.assertFalse(management.completion_record_consumable(result))
        self.assertEqual(self.fixture["expected"]["native_transport_decision"], result["x_catalog_plan"]["transport_decision"]["decision"])
        self.assertFalse(result["x_catalog_plan"]["transport_decision"]["bridge_required"])
        self.assertFalse(result["x_catalog_plan"]["contextforge_authority"]["direct_database_writes_allowed"])
        self.assertIn("does not write the ContextForge database", result["x_catalog_plan"]["non_actions"])
        self.assertIn("does not wrap native HTTP/SSE or REST/API service unnecessarily", result["x_catalog_plan"]["non_actions"])
        self.assertEqual(
            {"public_contextforge_api"},
            {operation["authority"] for operation in result["x_catalog_plan"]["contextforge_api_operations"]},
        )
        for forbidden_effect in self.fixture["expected"]["forbidden_follow_up_effects"]:
            self.assertIn(forbidden_effect, result["forbidden_follow_up_effects"])

    def test_package_bridge_is_used_only_for_missing_stdio_transports(self) -> None:
        stdio_plan = management.build_catalog_plan(self.handoff_for("stdio_candidate_descriptor"), generated_at=self.resolved_at)
        native_plan = management.build_catalog_plan(self.handoff_for(), generated_at=self.resolved_at)

        self.assertEqual(self.fixture["expected"]["stdio_transport_decision"], stdio_plan["transport_decision"]["decision"])
        self.assertTrue(stdio_plan["transport_decision"]["bridge_required"])
        self.assertIn("--stdio ... --expose-sse --expose-streamable-http", stdio_plan["transport_decision"]["package_bridge_ref"])
        self.assertIn("does not wrap transports beyond the missing required side", stdio_plan["non_actions"])
        self.assertEqual(self.fixture["expected"]["native_transport_decision"], native_plan["transport_decision"]["decision"])
        self.assertFalse(native_plan["transport_decision"]["bridge_required"])
        self.assertIsNone(native_plan["transport_decision"]["package_bridge_ref"])

    def test_candidate_handoff_cannot_become_project_state_service_without_typed_result(self) -> None:
        plan = planner.plan_project_initialization(
            self.project_root,
            service_descriptors=[copy.deepcopy(self.fixture["candidate_descriptor"])],
            resolved_at=self.resolved_at,
        )

        self.assertFalse(plan["mutation_allowed"])
        self.assertEqual([], plan["plan_steps"])
        self.assertEqual(1, len(plan["service_management_handoffs"]))
        planner_handoff = plan["service_management_handoffs"][0]
        contracts.validate_artifact("service_management_handoff", planner_handoff)
        self.assertIn("project_state_service_record", planner_handoff["forbidden_under_current_approval"])
        with self.assertRaises(management.ServiceManagementInputError):
            management.completion_record_consumable(planner_handoff)

        plan_only_result = management.plan_service_management_from_handoff(planner_handoff, generated_at=self.resolved_at)
        self.assertEqual("plan_only", plan_only_result["status"])
        self.assertFalse(management.completion_record_consumable(plan_only_result))

    def test_completion_records_are_consumable_only_with_canonical_refs_and_traces(self) -> None:
        dedupe_result = management.plan_service_management_from_handoff(
            self.handoff_for(),
            existing_services=[copy.deepcopy(self.fixture["existing_service"])],
            generated_at=self.resolved_at,
        )
        approved_result = management.build_approved_completion_result(
            self.handoff_for(),
            canonical_names=self.fixture["expected"]["canonical_names"],
            contract_card_refs=[self.ref("contract_card")],
            semantic_tool_policy_refs=[self.ref("policy")],
            verification_trace_refs=[self.ref("verification_trace")],
            consent_receipt_refs=[self.ref("consent_receipt")],
            capsule_refs=[self.ref("capsule")],
            catalog_revision=self.fixture["expected"]["catalog_revision"],
            approval_context={"approval_class": "catalog_promotion", "explicit": True, "approval_ref": "transcript:redacted"},
            generated_at=self.resolved_at,
        )
        refused_result = management.plan_service_management_from_handoff(
            self.handoff_for("stdio_candidate_descriptor"),
            approval_context={"approval_class": "project_init", "explicit": True, "approval_ref": "transcript:redacted"},
            generated_at=self.resolved_at,
        )
        incomplete_result = copy.deepcopy(approved_result)
        incomplete_result["contract_card_refs"] = []

        for result in (dedupe_result, approved_result):
            contracts.validate_artifact("service_management_result", result)
            self.assertIn(result["status"], {"dedupe_existing", "approved_completed"})
            self.assertTrue(management.completion_record_consumable(result))
            self.assertEqual(self.fixture["expected"]["canonical_names"], result["canonical_names"])
            self.assertTrue(result["contract_card_refs"])
            self.assertTrue(result["semantic_tool_policy_refs"])
            self.assertTrue(result["verification_trace_refs"])

        self.assertEqual("refused", refused_result["status"])
        self.assertFalse(management.completion_record_consumable(refused_result))
        self.assertFalse(management.completion_record_consumable(incomplete_result))

    def test_language_profiles_stay_plan_first_until_service_management_completion(self) -> None:
        case = self.fixture["language_profile_case"]
        detection = language_profiles.detect_language_profiles(case["project_paths"])
        selection = language_profiles.build_profile_selection_plan(
            current_selected_profile_id=None,
            requested_profile_id=case["selected_profile_id"],
            detection_report=detection,
        )
        handoff_result = management.plan_service_management_from_handoff(self.handoff_for(), generated_at=self.resolved_at)
        completion = management.build_approved_completion_result(
            self.handoff_for(),
            canonical_names=self.fixture["expected"]["canonical_names"],
            contract_card_refs=[self.ref("contract_card")],
            semantic_tool_policy_refs=[self.ref("policy")],
            verification_trace_refs=[self.ref("verification_trace")],
            consent_receipt_refs=[self.ref("consent_receipt")],
            catalog_revision=self.fixture["expected"]["catalog_revision"],
            approval_context={"approval_class": "catalog_promotion", "explicit": True, "approval_ref": "transcript:redacted"},
            generated_at=self.resolved_at,
        )

        self.assertEqual(case["expected_language_id"], detection["selected_primary_profile"]["language_id"])
        self.assertEqual([], detection["service_acceptance_decisions"])
        self.assertEqual([], selection["service_acceptance_decisions"])
        self.assertIn("does not accept services", selection["non_actions"])
        self.assertFalse(management.completion_record_consumable(handoff_result))
        self.assertTrue(management.completion_record_consumable(completion))
        self.assertEqual(self.fixture["expected"]["canonical_names"], completion["canonical_names"])

    def test_governance_reconciliation_warnings_are_proposal_only_and_do_not_edit_ledgers(self) -> None:
        pack = self.fixture["governance_reconciliation_pack"]
        contracts.validate_artifact("governance_reconciliation_pack", pack)

        self.assertTrue(pack["advisory_only"])
        self.assertIn("edit_ledgers", pack["forbidden_effects"])
        self.assertIn("bypass_governance_crud", pack["forbidden_effects"])
        self.assertIn("bypass_mentality", pack["forbidden_effects"])
        self.assertTrue(pack["service_memory_conflicts"])
        self.assertFalse(pack["service_memory_conflicts"][0]["memory_value_used_as_authority"])
        self.assertEqual("governance_ledger", pack["service_memory_conflicts"][0]["selected_value_source"])
        self.assertEqual(
            [False],
            [operation["mutation_performed"] for operation in pack["suggested_governance_crud_operations"]],
        )


if __name__ == "__main__":
    unittest.main()
