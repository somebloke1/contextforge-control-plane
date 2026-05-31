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
import control_plane_project_planner as planner
import control_plane_project_state as project_state


FIXTURE_PATH = REPO_ROOT / "tests/fixtures/control_plane_project_planner_cases.json"


class ControlPlaneProjectPlannerFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with FIXTURE_PATH.open("r", encoding="utf-8") as handle:
            cls.fixture = json.load(handle)
        cls.project_root = cls.fixture["project_root"]
        cls.cases = {case["name"]: case for case in cls.fixture["cases"]}

    def plan_case(self, name: str) -> dict[str, Any]:
        case = self.cases[name]
        inputs = case["inputs"]
        return planner.plan_project_initialization(
            self.project_root,
            state=inputs.get("state"),
            catalog=inputs.get("catalog"),
            service_descriptors=inputs.get("service_descriptors", []),
            target_client_digests=inputs.get("target_client_digests"),
            trust_state_digest=inputs.get("trust_state_digest"),
            missing_trust=inputs.get("missing_trust", []),
            missing_language=inputs.get("missing_language", []),
            drift_findings=inputs.get("drift_findings", []),
            resolved_at=self.fixture["resolved_at"],
        )

    def assert_basic_expectations(self, plan: dict[str, Any], expected: dict[str, Any]) -> None:
        self.assertFalse(plan["mutation_allowed"])
        self.assertEqual(expected["status"], plan["status"])
        self.assertEqual(expected.get("required_consent_classes", []), plan["required_consent_classes"])
        self.assertEqual(expected["plan_step_count"], len(plan["plan_steps"]))
        self.assertEqual(expected["handoff_count"], len(plan["service_management_handoffs"]))
        self.assertEqual(set(expected.get("open_item_types", [])), {item["type"] for item in plan["open_items"]})
        for consent_class in expected.get("forbidden_consent_absent", []):
            self.assertNotIn(consent_class, plan["required_consent_classes"])
        for non_action in expected.get("expected_non_actions", []):
            self.assertIn(non_action, plan["non_actions"])

    def assert_plan_step_expectations(self, plan: dict[str, Any], expected: dict[str, Any]) -> None:
        for index, step_expected in enumerate(expected.get("plan_steps", [])):
            step = plan["plan_steps"][index]
            self.assertEqual(step_expected["service_binding"], step["service_binding"])
            self.assertEqual(step_expected["operation"], step["operation"])
            self.assertEqual(step_expected["instantiation_class"], step["instantiation_class"])
            self.assertEqual(step_expected["required_consent_classes"], step["required_consent_classes"])
            if step_expected.get("requires_contract_card_ref"):
                self.assertIsInstance(step["contract_card_ref"], dict)
                self.assertTrue(step["contract_card_ref"]["ref"].startswith("contextforge://control-plane/service-bindings/"))
                self.assertTrue(step["contract_card_ref"]["content_digest"].startswith("sha256:"))
            if step_expected.get("requires_capability_capsule_ref"):
                self.assertIsInstance(step["capability_capsule_ref"], dict)
                self.assertTrue(step["capability_capsule_ref"]["ref"].startswith("contextforge://control-plane/capability-capsules/"))
                self.assertTrue(step["capability_capsule_ref"]["content_digest"].startswith("sha256:"))
            for key, value in step_expected.get("effect_summary", {}).items():
                self.assertEqual(value, step["effect_summary"][key])
            for non_action in step_expected.get("required_non_actions", []):
                self.assertIn(non_action, step["non_actions"])
            for requirement in step_expected.get("required_verification_requirements", []):
                self.assertIn(requirement, step["verification_requirements"])

    def assert_open_item_expectations(self, plan: dict[str, Any], expected: dict[str, Any]) -> None:
        open_item_ids = {item["id"] for item in plan["open_items"]}
        for item_id in expected.get("open_item_ids", []):
            self.assertIn(item_id, open_item_ids)
        for expected_detail in expected.get("open_item_details", []):
            self.assertTrue(
                any(all(item["detail"].get(key) == value for key, value in expected_detail.items()) for item in plan["open_items"]),
                expected_detail,
            )

    def assert_handoff_expectations(self, plan: dict[str, Any], expected: dict[str, Any]) -> None:
        handoff_expected = expected.get("handoff")
        if not handoff_expected:
            return
        handoff = plan["service_management_handoffs"][0]
        contracts.validate_artifact("service_management_handoff", handoff)
        self.assertEqual(handoff_expected["x_handoff_class"], handoff["x_handoff_class"])
        self.assertEqual(handoff_expected["required_next_workflow"], handoff["required_next_workflow"])
        self.assertEqual(handoff_expected["redaction_status"], handoff["redaction_status"])
        self.assertEqual(handoff_expected["suspected_instantiation_class"], handoff["suspected_instantiation_class"])
        for forbidden_effect in handoff_expected["forbidden_under_current_approval"]:
            self.assertIn(forbidden_effect, handoff["forbidden_under_current_approval"])
        for key, value in handoff_expected["dedupe_keys"].items():
            self.assertEqual(value, handoff["dedupe_keys"][key])

    def assert_stale_input_expectations(self, plan: dict[str, Any], expected: dict[str, Any]) -> None:
        stale_inputs = plan["stale_plan_inputs"]
        if "stale_input_keys" in expected:
            self.assertEqual(set(expected["stale_input_keys"]), set(stale_inputs))
        if "base_state_revision" in expected:
            self.assertEqual(expected["base_state_revision"], stale_inputs["base_project_state"]["revision"])
        if "catalog_revision_or_etag" in expected:
            self.assertEqual(expected["catalog_revision_or_etag"], stale_inputs["catalog"]["revision_or_etag"])
            self.assertEqual(
                expected["catalog_revision_or_etag"],
                plan["plan_steps"][0]["stale_plan_inputs"]["catalog_revision_or_etag"],
            )
        if "target_client_digests" in expected:
            self.assertEqual(expected["target_client_digests"], stale_inputs["target_client_digests"])
            self.assertEqual(expected["target_client_digests"], plan["plan_steps"][0]["stale_plan_inputs"]["target_client_digests"])
        if "trust_state_digest" in expected:
            self.assertEqual(expected["trust_state_digest"], stale_inputs["trust_state_digest"])
            self.assertEqual(expected["trust_state_digest"], plan["plan_steps"][0]["stale_plan_inputs"]["trust_state_digest"])
        if expected.get("requires_descriptor_digest"):
            descriptor_input = stale_inputs["selected_service_descriptors"][0]
            step_input = plan["plan_steps"][0]["stale_plan_inputs"]
            self.assertTrue(descriptor_input["artifact_digest"].startswith("sha256:"))
            self.assertTrue(step_input["descriptor_digest"].startswith("sha256:"))
        if "drift_finding_id" in expected:
            self.assertEqual(expected["drift_finding_id"], stale_inputs["drift_findings"][0]["id"])
            self.assertEqual(expected["drift_finding_id"], plan["plan_steps"][0]["stale_plan_inputs"]["drift_findings"][0]["id"])
            self.assertTrue(any(item["type"] == "drift" for item in plan["open_items"]))
        self.assertEqual(project_state.project_root_hash(self.project_root), stale_inputs["project_root_hash"])

    def assert_artifact_drafts_validate(self, plan: dict[str, Any]) -> None:
        for contract_card in plan["artifact_drafts"]["contract_cards"]:
            contracts.validate_artifact("service_binding_contract_card", contract_card)
        for capsule in plan["artifact_drafts"]["capability_capsules"]:
            contracts.validate_artifact("shared_service_capability_capsule", capsule)

    def test_fixture_names_cover_w4_c_required_cases(self) -> None:
        self.assertEqual(
            {
                "accepted_context7_shared_binding_read_only",
                "serena_sticky_decline_fixture_only",
                "disabled_project_state_no_service",
                "catalog_candidate_pi_web_access_handoff",
                "missing_trust_and_language_block_without_global_consent",
                "stale_state_and_drift_inputs_represented",
            },
            set(self.cases),
        )

    def test_planner_fixture_cases_match_expected_outputs(self) -> None:
        for name, case in self.cases.items():
            with self.subTest(case=name):
                plan = self.plan_case(name)
                expected = case["expected"]
                self.assert_basic_expectations(plan, expected)
                self.assert_plan_step_expectations(plan, expected)
                self.assert_open_item_expectations(plan, expected)
                self.assert_handoff_expectations(plan, expected)
                self.assert_stale_input_expectations(plan, expected)
                self.assert_artifact_drafts_validate(plan)

    def test_fixture_inputs_are_not_mutated_and_state_file_is_not_changed(self) -> None:
        state_path = project_state.project_state_path(self.project_root)
        existed_before = state_path.exists()
        for name, case in self.cases.items():
            with self.subTest(case=name):
                original_inputs = copy.deepcopy(case["inputs"])
                self.plan_case(name)
                self.assertEqual(original_inputs, case["inputs"])
                self.assertEqual(existed_before, state_path.exists())


if __name__ == "__main__":
    unittest.main()
