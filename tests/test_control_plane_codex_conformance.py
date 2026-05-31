from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import control_plane_codex_conformance as codex_conformance
import control_plane_contracts as contracts


FIXTURE_PATH = REPO_ROOT / "tests/fixtures/control_plane_codex_conformance_cases.json"


class ControlPlaneCodexConformanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with FIXTURE_PATH.open("r", encoding="utf-8") as handle:
            cls.fixture = json.load(handle)
        cls.cases = {case["name"]: case for case in cls.fixture["cases"]}

    def run_case(self, name: str) -> dict[str, Any]:
        case = self.cases[name]
        return codex_conformance.run_fixture_case(case, generated_at=self.fixture["generated_at"])

    def test_codex_pack_is_schema_valid_and_declines_mutating_trust_or_serena_assumptions(self) -> None:
        pack = codex_conformance.build_codex_conformance_pack(generated_at=self.fixture["generated_at"])

        contracts.validate_artifact("client_adapter_conformance_pack", pack)

        self.assertEqual("codex/v1", pack["pack_id"])
        self.assertTrue(pack["trust_requirements"]["global_trust_required"])
        self.assertFalse(pack["trust_requirements"]["mutation_allowed_by_pack"])
        unsupported = {item["behavior"]: item["status"] for item in pack["known_unsupported_behaviors"]}
        self.assertEqual("declined_in_w6_a", unsupported["automatic_user_global_trust_mutation"])
        self.assertEqual("declined_in_w6_a", unsupported["serena_service_provisioning_assumption"])
        self.assertIn("list_tools_proof", pack["x_required_checks"])
        self.assertIn("call_tool_proof", pack["x_required_checks"])

    def test_fixture_names_cover_w6_a_required_cases(self) -> None:
        self.assertEqual(
            {
                "codex_project_local_config_trusted_and_verified",
                "codex_trust_missing_blocks_without_mutation",
                "codex_stale_config_and_restart_required_blocks",
                "codex_backend_health_without_target_client_proof_fails",
                "codex_wrong_auth_material_source_fails_closed",
                "codex_unmanaged_owned_block_blocks_mutation",
                "codex_wrong_root_visibility_fails_negative_check",
            },
            set(self.cases),
        )

    def test_fixture_cases_match_expected_status_decision_and_blockers(self) -> None:
        for name, case in self.cases.items():
            with self.subTest(case=name):
                result = self.run_case(name)
                expected = case["expected"]

                self.assertEqual(expected["status"], result["status"])
                self.assertEqual(expected["decision"], result["decision"])
                self.assertEqual(set(expected["blocker_names"]), {item["name"] for item in result["blockers"]})
                if "trust_state" in expected:
                    self.assertEqual(expected["trust_state"], result["trust_report"]["state"])
                if "backend_health_observed" in expected:
                    self.assertEqual(expected["backend_health_observed"], result["backend_health_observed"])
                self.assertFalse(result["trust_report"]["mutation_allowed"])
                self.assertFalse(result["trust_report"]["mutation_performed"])

    def test_passing_case_requires_project_local_config_list_tools_and_call_tool(self) -> None:
        result = self.run_case("codex_project_local_config_trusted_and_verified")
        checks = {item["name"]: item for item in result["checks"]}

        self.assertEqual("passing_conformance", result["status"])
        self.assertEqual("allow_target_client_proof", result["decision"])
        self.assertEqual("passed", checks["project_local_config_loaded"]["status"])
        self.assertEqual("passed", checks["list_tools_proof"]["status"])
        self.assertEqual("passed", checks["call_tool_proof"]["status"])
        self.assertEqual(self.fixture["project_root"], result["project_root"])
        self.assertRegex(result["project_root_hash"], r"^[0-9a-f]{64}$")

    def test_backend_health_alone_cannot_satisfy_codex_target_client_proof(self) -> None:
        result = self.run_case("codex_backend_health_without_target_client_proof_fails")
        blocker_names = {item["name"] for item in result["blockers"]}

        self.assertTrue(result["backend_health_observed"])
        self.assertEqual("failed_conformance", result["status"])
        self.assertIn("list_tools_proof", blocker_names)
        self.assertIn("call_tool_proof", blocker_names)
        self.assertIn("target_client_visibility", blocker_names)

    def test_fail_closed_for_missing_or_mismatched_evidence(self) -> None:
        base = copy.deepcopy(self.cases["codex_project_local_config_trusted_and_verified"])
        missing_list_tools = copy.deepcopy(base)
        missing_list_tools["evidence"].pop("list_tools")
        wrong_root = copy.deepcopy(base)
        wrong_root["evidence"]["client"]["project_root"] = "/home/dgk/workspace/other-project"
        wrong_probe_root = copy.deepcopy(base)
        wrong_probe_root["evidence"]["list_tools"]["project_root"] = "/home/dgk/workspace/other-project"
        wrong_probe_root["evidence"]["call_tool"]["project_root"] = "/home/dgk/workspace/other-project"
        unauthenticated = copy.deepcopy(base)
        unauthenticated["evidence"]["auth"]["strength"] = "none"

        variants = {
            "missing_list_tools": missing_list_tools,
            "wrong_root": wrong_root,
            "wrong_probe_root": wrong_probe_root,
            "unauthenticated": unauthenticated,
        }
        for name, case in variants.items():
            with self.subTest(variant=name):
                result = codex_conformance.run_fixture_case(case, generated_at=self.fixture["generated_at"])
                self.assertEqual("block_target_client_proof", result["decision"])
                self.assertNotEqual("passing_conformance", result["status"])

    def test_trust_approval_without_loaded_verification_is_blocking_not_passing(self) -> None:
        case = copy.deepcopy(self.cases["codex_project_local_config_trusted_and_verified"])
        case["evidence"]["trust"]["state"] = "approved"
        case["evidence"]["config"]["loaded_by_client"] = False

        result = codex_conformance.run_fixture_case(case, generated_at=self.fixture["generated_at"])

        self.assertEqual("blocked_limitation", result["status"])
        self.assertEqual("block_target_client_proof", result["decision"])
        self.assertEqual(
            {"project_local_config_loaded", "trust_state_allows_loading"},
            {item["name"] for item in result["blockers"]},
        )

    def test_fixture_inputs_are_not_mutated(self) -> None:
        before = copy.deepcopy(self.fixture)
        for name in self.cases:
            with self.subTest(case=name):
                self.run_case(name)
        self.assertEqual(before, self.fixture)

    def test_result_contains_no_secret_shaped_literals(self) -> None:
        result = self.run_case("codex_project_local_config_trusted_and_verified")
        encoded = json.dumps(result, sort_keys=True)

        self.assertNotIn("Bearer ", encoded)
        self.assertNotIn("sk-", encoded)
        contracts.validate_artifact("client_adapter_conformance_pack", result["conformance_pack"])


if __name__ == "__main__":
    unittest.main()
