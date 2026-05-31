from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import control_plane_schema_fixtures as fixtures


REQUIRED_PROJECT_STATE_CASES = {
    "root_safety_denied_workspace_root",
    "root_safety_symlink_escape_rejected",
    "default_state_valid_without_repo_write",
    "migration_classifies_invalid_legacy_value_as_conflict",
    "sticky_decline_imports_from_legacy_env",
    "disabled_no_service_imports_without_initialized_status",
    "secret_exclusion_rejects_secret_like_state_field",
    "invalid_enum_rejects_project_status",
    "schema_evolution_rejects_unsupported_major",
    "stale_lock_recovers_on_temp_project",
}

REQUIRED_CONTRACT_CASES = {
    "contract_artifact_redaction_rejects_unredacted_secret_field",
    "scenario_isolation_rejects_visible_hidden_state_delta",
    "contract_schema_rejects_invalid_consent_enum",
}


class ControlPlaneSchemaFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture_data = fixtures.load_fixture_cases()

    def test_fixture_file_covers_wave_1_required_cases(self) -> None:
        project_names = {case["name"] for case in self.fixture_data["project_state_cases"]}
        contract_names = {case["name"] for case in self.fixture_data["contract_artifact_cases"]}
        self.assertEqual(set(), REQUIRED_PROJECT_STATE_CASES - project_names)
        self.assertEqual(set(), REQUIRED_CONTRACT_CASES - contract_names)

        happy_kinds = {
            case["kind"]
            for case in self.fixture_data["contract_artifact_cases"]
            if case.get("expect") == "pass"
        }
        self.assertEqual(fixtures.contracts.ARTIFACT_KINDS, happy_kinds)

    def test_project_state_fixture_cases(self) -> None:
        snapshot = fixtures.repo_project_state_snapshot()
        try:
            for case in self.fixture_data["project_state_cases"]:
                with self.subTest(case=case["name"]):
                    result = fixtures.run_project_state_case(case)
                    self.assertTrue(result.passed, result.detail)
        finally:
            fixtures.assert_repo_project_state_unchanged(snapshot)
            self.assertEqual([], list(fixtures.project_state.WORKSPACE_ROOT.glob("cfcp-schema-fixture-*")))

    def test_contract_artifact_fixture_cases(self) -> None:
        for case in self.fixture_data["contract_artifact_cases"]:
            with self.subTest(case=case["name"]):
                result = fixtures.run_contract_artifact_case(case, self.fixture_data)
                self.assertTrue(result.passed, result.detail)


if __name__ == "__main__":
    unittest.main()
