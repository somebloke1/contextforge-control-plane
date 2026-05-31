from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import control_plane_language_profiles as profiles


FIXTURE_PATH = REPO_ROOT / "tests/fixtures/control_plane_language_profiles_cases.json"


class ControlPlaneLanguageProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with FIXTURE_PATH.open("r", encoding="utf-8") as handle:
            cls.fixture = json.load(handle)
        cls.detection_cases = {case["name"]: case for case in cls.fixture["detection_cases"]}
        cls.selection_cases = {case["name"]: case for case in cls.fixture["selection_cases"]}
        cls.install_cases = {case["name"]: case for case in cls.fixture["install_cases"]}

    def test_exact_v1_profile_ids_and_contextforge_resource_shape(self) -> None:
        self.assertEqual(tuple(self.fixture["expected_profile_ids"]), profiles.PROFILE_IDS)
        resources = profiles.build_language_profile_resources()

        self.assertEqual(list(self.fixture["expected_profile_ids"]), [item["content"]["language_id"] for item in resources])
        for resource in resources:
            profiles.validate_language_profile_resource(resource)
            language_id = resource["content"]["language_id"]
            self.assertEqual(
                f"contextforge://control-plane/language-profiles/{language_id}/v1",
                resource["uri"],
            )
            self.assertIn("language-profile", resource["tags"])
            self.assertEqual("application/json", resource["mime_type"])

    def test_profile_metadata_contains_install_and_probe_artifact_policy(self) -> None:
        for profile_id in profiles.PROFILE_IDS:
            with self.subTest(profile_id=profile_id):
                profile = profiles.get_language_profile(profile_id)
                profiles.validate_language_profile(profile)
                self.assertTrue(profile["install_policy"]["plan_first"])
                self.assertFalse(profile["install_policy"]["execute_silently"])
                self.assertTrue(profile["install_policy"]["instance_local_by_default"])
                self.assertFalse(profile["install_policy"]["global_mutation_default"])
                self.assertEqual("emit_plan_open_items_and_choices", profile["install_policy"]["missing_tooling_behavior"])

                artifact_policy = profile["probe_artifact_policy"]
                self.assertTrue(artifact_policy["path"].startswith(f"generated/language-probes/{profile_id}/"))
                self.assertEqual("project_state_write", artifact_policy["consent_class"])
                self.assertIn("cleanup", artifact_policy)
                self.assertIn("gitignore_status", artifact_policy)
                self.assertIn("failure_blocks_verification", artifact_policy)

                evidence = profile["verification_evidence_expectations"]
                self.assertFalse(evidence["records_service_acceptance"])
                self.assertIn("selected_primary_profile", evidence["required_fields"])

    def test_fixture_detection_cases_are_deterministic_and_non_mutating(self) -> None:
        for name, case in self.detection_cases.items():
            with self.subTest(case=name):
                original = copy.deepcopy(case)
                report = profiles.detect_language_profiles(
                    case["paths"],
                    selected_profile_id=case.get("selected_profile_id"),
                )
                expected = case["expected"]
                self.assertEqual(expected["matched_profile_ids"], [item["language_id"] for item in report["matched_profiles"]])
                selected = report["selected_primary_profile"]
                self.assertEqual(expected["selected_profile_id"], selected["language_id"] if selected else None)
                self.assertEqual(expected["open_item_types"], [item["type"] for item in report["open_items"]])
                self.assertEqual([], report["service_acceptance_decisions"])
                self.assertIn("does not install language tooling", report["non_actions"])
                self.assertEqual(original, case)

    def test_empty_project_does_not_silently_select_python(self) -> None:
        report = profiles.detect_language_profiles([])

        self.assertEqual([], report["matched_profiles"])
        self.assertIsNone(report["selected_primary_profile"])
        self.assertEqual(["empty_project_requires_explicit_language_selection"], [item["type"] for item in report["open_items"]])
        self.assertIn("does not default empty projects to python", report["non_actions"])

    def test_selected_primary_profile_is_separate_from_service_acceptance(self) -> None:
        report = profiles.detect_language_profiles(["package.json", "src/index.ts"], selected_profile_id="typescript_javascript")

        self.assertEqual("typescript_javascript", report["selected_primary_profile"]["language_id"])
        self.assertEqual("explicit_user_or_approved_plan", report["selected_primary_profile"]["selection_source"])
        self.assertEqual([], report["service_acceptance_decisions"])

    def test_selection_fixture_cases_require_approval_for_profile_change(self) -> None:
        detection_report = profiles.detect_language_profiles(["pyproject.toml", "src/app.py"])
        for name, case in self.selection_cases.items():
            with self.subTest(case=name):
                plan = profiles.build_profile_selection_plan(
                    current_selected_profile_id=case["current_selected_profile_id"],
                    requested_profile_id=case["requested_profile_id"],
                    detection_report=detection_report,
                    approval_ref=case.get("approval_ref"),
                )
                expected = case["expected"]
                self.assertEqual(expected["decision"], plan["decision"])
                self.assertEqual(expected["approval_required"], plan["approval_required"])
                self.assertEqual(expected["open_item_types"], [item["type"] for item in plan["open_items"]])
                self.assertEqual([], plan["service_acceptance_decisions"])
                self.assertIn("does not mutate project state", plan["non_actions"])

    def test_install_workflow_fixture_cases_are_plan_first_and_return_choices(self) -> None:
        for name, case in self.install_cases.items():
            with self.subTest(case=name):
                plan = profiles.build_install_workflow_plan(
                    profile_id=case["profile_id"],
                    missing_tool_ids=case["missing_tool_ids"],
                    requested_scope=case["requested_scope"],
                    execution_approved=case["execution_approved"],
                    global_mutation_approved=case["global_mutation_approved"],
                )
                expected = case["expected"]
                self.assertEqual(expected["decision"], plan["decision"])
                self.assertEqual(expected["blockers"], plan["blockers"])
                self.assertEqual(expected["open_item_types"], [item["type"] for item in plan["open_items"]])
                self.assertTrue(plan["choices"])
                self.assertTrue(all(choice["plan_first"] for choice in plan["choices"]))
                self.assertTrue(all(choice["execute_without_approval"] is False for choice in plan["choices"]))
                self.assertIn("does not run install commands", plan["non_actions"])
                self.assertIn("does not mutate global language tooling", plan["non_actions"])

    def test_unknown_profile_ids_fail_closed(self) -> None:
        with self.assertRaises(profiles.LanguageProfileError):
            profiles.get_language_profile("typescript")
        with self.assertRaises(profiles.LanguageProfileError):
            profiles.detect_language_profiles(["main.go"], selected_profile_id="go")


if __name__ == "__main__":
    unittest.main()
