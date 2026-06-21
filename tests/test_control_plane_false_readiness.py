from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import control_plane_false_readiness as false_readiness


FIXTURE_PATH = REPO_ROOT / "tests/fixtures/control_plane_false_readiness_cases.json"
GUARDRAILS_PATH = REPO_ROOT / "docs/readiness-claim-guardrails.md"


class ControlPlaneFalseReadinessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with FIXTURE_PATH.open("r", encoding="utf-8") as handle:
            cls.fixture = json.load(handle)
        cls.cases = {case["name"]: case for case in cls.fixture["cases"]}

    def evaluate_case(self, name: str) -> dict[str, Any]:
        return false_readiness.evaluate_false_readiness_case(
            self.cases[name],
            now=self.fixture["generated_at"],
        )

    def test_fixture_names_cover_requested_false_readiness_cases(self) -> None:
        self.assertEqual(
            {
                "supported_pi_target_client_ready",
                "stale_model_id_for_pi_claim",
                "absent_scoped_probe_token_for_pi_claim",
                "revoked_scoped_probe_token_for_pi_claim",
                "missing_pi_client_binding_fixture",
                "missing_opencode_client_binding_fixture",
                "backend_only_claimed_as_client_visible",
                "wrapper_tool_call_failure_for_opencode_claim",
                "stale_timestamp_for_pi_claim",
                "wrong_exercised_surface_for_opencode_claim",
            },
            set(self.cases),
        )

    def test_fixture_stays_on_approved_pi_opencode_qwen_surfaces(self) -> None:
        for name, case in self.cases.items():
            with self.subTest(case=name):
                claim = case["claim"]
                evidence = case["evidence"]
                self.assertIn(claim["target_client"], {"pi", "opencode"})
                self.assertEqual("qwen3.6-a3b", claim["expected_model_id"])
                self.assertNotIn("codex", json.dumps(case).lower())
                self.assertNotIn("gpt-5", json.dumps(case).lower())
                if claim["target_client"] == "pi":
                    self.assertEqual("contextforge-global-shim", claim["service_binding"])
                if claim["target_client"] == "opencode":
                    self.assertEqual("contextforge-helper", claim["service_binding"])
                self.assertIn(
                    evidence["client_binding_fixture"]["fixture_ref"],
                    {
                        None,
                        "docker/client-harness/config/pi/AGENTS.md#contextforge-global-shim",
                        "docker/client-harness/config/opencode/plugins/contextforge-project-init.js#contextforge-project-init",
                    },
                )

    def test_fixture_expected_reasons_are_valid_and_complete(self) -> None:
        validated = false_readiness.validate_false_readiness_cases(self.fixture)
        covered = {
            reason_id
            for case in validated["cases"]
            for reason_id in case["expected"]["failure_reason_ids"]
        }
        self.assertEqual(set(false_readiness.FAILURE_REASONS), covered)

    def test_each_case_reports_expected_decision_and_failure_reasons(self) -> None:
        for name, case in self.cases.items():
            with self.subTest(case=name):
                result = self.evaluate_case(name)
                self.assertEqual(case["expected"]["decision"], result["decision"])
                self.assertEqual(case["expected"]["failure_reason_ids"], result["failure_reason_ids"])
                if result["decision"] == "block_readiness_claim":
                    self.assertEqual("false_readiness", result["status"])
                    self.assertTrue(result["blockers"])
                else:
                    self.assertEqual("readiness_claim_supported", result["status"])
                    self.assertFalse(result["blockers"])

    def test_absent_and_revoked_scoped_probe_tokens_are_distinct(self) -> None:
        absent = self.evaluate_case("absent_scoped_probe_token_for_pi_claim")
        revoked = self.evaluate_case("revoked_scoped_probe_token_for_pi_claim")

        self.assertEqual(["absent_scoped_probe_token"], absent["failure_reason_ids"])
        self.assertEqual(["revoked_scoped_probe_token"], revoked["failure_reason_ids"])
        self.assertNotEqual(absent["blockers"][0]["detail"], revoked["blockers"][0]["detail"])

    def test_pi_and_opencode_missing_binding_fixtures_are_reported_by_client(self) -> None:
        pi = self.evaluate_case("missing_pi_client_binding_fixture")
        opencode = self.evaluate_case("missing_opencode_client_binding_fixture")

        self.assertEqual("pi", pi["target_client"])
        self.assertEqual("opencode", opencode["target_client"])
        self.assertEqual(["missing_client_binding_fixture"], pi["failure_reason_ids"])
        self.assertEqual(["missing_client_binding_fixture"], opencode["failure_reason_ids"])
        self.assertIn("pi client binding fixture", pi["blockers"][0]["detail"])
        self.assertIn("opencode client binding fixture", opencode["blockers"][0]["detail"])

    def test_backend_only_and_wrong_surface_are_not_collapsed(self) -> None:
        backend_only = self.evaluate_case("backend_only_claimed_as_client_visible")
        wrong_surface = self.evaluate_case("wrong_exercised_surface_for_opencode_claim")

        self.assertEqual(["backend_only_claimed_client_visible"], backend_only["failure_reason_ids"])
        self.assertEqual(["wrong_exercised_surface"], wrong_surface["failure_reason_ids"])
        self.assertEqual("backend", backend_only["observed_exercised_surface"])
        self.assertEqual("contextforge_dev_docker", wrong_surface["observed_exercised_surface"])

    def test_report_summarizes_failure_reasons_without_claiming_live_probes(self) -> None:
        report = false_readiness.build_false_readiness_report(self.fixture, now=self.fixture["generated_at"])
        summary = {item["reason_id"]: item for item in report["failure_reason_summary"]}

        self.assertEqual(10, report["decision_summary"]["total_cases"])
        self.assertEqual(9, report["decision_summary"]["blocked_claims"])
        self.assertEqual(1, report["decision_summary"]["allowed_claims"])
        self.assertEqual(set(false_readiness.FAILURE_REASONS), set(summary))
        for reason_id, item in summary.items():
            with self.subTest(reason=reason_id):
                self.assertTrue(item["case_names"])

        for case_result in report["case_results"]:
            self.assertIn("did_not_probe_live_contextforge", case_result["non_actions"])
            self.assertIn("did_not_mutate_client_config", case_result["non_actions"])
            self.assertIn("did_not_create_or_revoke_tokens", case_result["non_actions"])

    def test_fixture_inputs_are_not_mutated(self) -> None:
        before = copy.deepcopy(self.fixture)
        false_readiness.build_false_readiness_report(self.fixture, now=self.fixture["generated_at"])
        self.assertEqual(before, self.fixture)

    def test_malformed_fixture_cases_fail_closed(self) -> None:
        duplicate = copy.deepcopy(self.fixture)
        duplicate["cases"].append(copy.deepcopy(duplicate["cases"][0]))
        with self.assertRaises(false_readiness.FalseReadinessError):
            false_readiness.validate_false_readiness_cases(duplicate)

        missing_reason = copy.deepcopy(self.fixture)
        missing_reason["cases"] = [
            case
            for case in missing_reason["cases"]
            if case["name"] != "stale_model_id_for_pi_claim"
        ]
        with self.assertRaises(false_readiness.FalseReadinessError):
            false_readiness.validate_false_readiness_cases(missing_reason)

    def test_guardrail_doc_names_false_readiness_failure_reasons(self) -> None:
        doc = GUARDRAILS_PATH.read_text(encoding="utf-8")
        self.assertIn("False-Readiness Fixture Reasons", doc)
        self.assertIn("tests/fixtures/control_plane_false_readiness_cases.json", doc)
        for reason_id in false_readiness.FAILURE_REASONS:
            with self.subTest(reason=reason_id):
                self.assertIn(f"`{reason_id}`", doc)


if __name__ == "__main__":
    unittest.main()
