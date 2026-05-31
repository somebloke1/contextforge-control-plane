from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import control_plane_contracts as contracts
import control_plane_test_harness as harness


class ControlPlaneTestHarnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.requirements = harness.load_requirements()
        cls.requirement_ids = {item["requirement_id"] for item in cls.requirements["requirements"]}
        cls.scenarios = harness.load_scenarios(requirement_ids=cls.requirement_ids)

    def test_requirement_registry_validates_mvs_fields(self) -> None:
        self.assertEqual(1, self.requirements["version"])
        expected = {
            "cfcp-req-contextforge-authority",
            "cfcp-req-project-state-authority",
            "cfcp-req-consent-boundaries",
            "cfcp-req-trust-separation",
            "cfcp-req-secret-exclusion",
            "cfcp-req-target-client-verification",
            "cfcp-req-tool-policy-negative-checks",
            "cfcp-req-service-instantiation-distinction",
            "cfcp-req-inference-isolation",
        }
        self.assertEqual(expected, self.requirement_ids)
        for requirement in self.requirements["requirements"]:
            self.assertTrue(requirement["mvs_required"])
            self.assertEqual("non_deferrable", requirement["deferrability"])
            self.assertEqual("must_pass_mvs", requirement["acceptance_gate"])
            self.assertIn("deterministic", requirement["required_layers"])

    def test_requirement_registry_rejects_duplicate_requirement_ids(self) -> None:
        registry = copy.deepcopy(self.requirements)
        registry["requirements"].append(copy.deepcopy(registry["requirements"][0]))
        with self.assertRaises(harness.HarnessValidationError):
            harness.validate_requirement_registry(registry)

    def test_coverage_matrix_reports_complete_slots_and_explicit_gaps(self) -> None:
        matrix = harness.build_coverage_matrix(self.requirements, self.scenarios)
        self.assertTrue(matrix["coverage_complete"])
        self.assertFalse(any(row["governance_waiver_ref"] for row in matrix["requirements"]))

        gapped_scenarios = copy.deepcopy(self.scenarios)
        gapped_scenarios["scenarios"] = [
            scenario
            for scenario in gapped_scenarios["scenarios"]
            if "cfcp-req-inference-isolation" not in scenario["requirement_ids"]
        ]
        gapped = harness.build_coverage_matrix(self.requirements, gapped_scenarios)
        isolation_row = next(
            row for row in gapped["requirements"] if row["requirement_id"] == "cfcp-req-inference-isolation"
        )
        self.assertFalse(gapped["coverage_complete"])
        self.assertEqual({"deterministic", "probe", "inference_inclusive"}, {gap["slot"] for gap in isolation_row["gaps"]})
        self.assertIsNone(isolation_row["governance_waiver_ref"])

    def test_scenario_isolation_rejection_for_visible_role_private_context(self) -> None:
        scenarios = copy.deepcopy(self.scenarios)
        scenarios["scenarios"][0]["tested_agent_view"]["user_prompt"] = "Use the hidden evaluator notes."
        with self.assertRaises(contracts.InferentialIsolationError):
            harness.validate_scenario_registry(scenarios, requirement_ids=self.requirement_ids)

    def test_deterministic_runner_emits_schema_valid_ledgers_without_assistant_execution(self) -> None:
        results = harness.run_deterministic_scenarios(
            self.requirements,
            self.scenarios,
            run_id="run-unit-001",
            timestamp=harness.STAMP,
        )
        self.assertEqual(len(self.scenarios["scenarios"]), len(results))
        for result in results:
            with self.subTest(scenario=result.scenario_id):
                self.assertFalse(result.assistant_executed)
                self.assertTrue(result.passed)
                self.assertEqual(list(result.requirement_ids), result.ledger["requirement_ids"])
                self.assertTrue(result.ledger["evidence_hashes"])
                contracts.validate_artifact("evidence_ledger", result.ledger)
                transcript = result.transcript_capture["capture"]
                self.assertFalse(transcript["hidden_state_included"])
                self.assertFalse(transcript["remediation_context_included"])

    def test_evaluator_verdict_shape_cites_requirements_and_redacted_refs(self) -> None:
        result = harness.run_deterministic_scenarios(self.requirements, self.scenarios, run_id="run-unit-002")[0]
        verdict = harness.build_evaluator_verdict(
            self.scenarios["scenarios"][0],
            result.ledger,
            verdict="fail",
            failed_requirements=["cfcp-req-contextforge-authority"],
        )
        self.assertEqual("fail", verdict["verdict"])
        self.assertEqual(["cfcp-req-contextforge-authority"], verdict["failed_requirements"])
        self.assertEqual("passed", verdict["redaction_status"])
        self.assertTrue(verdict["evaluated_artifact_refs"])
        self.assertTrue(verdict["deterministic_assertion_refs"])
        contracts.validate_artifact("evaluator_verdict", verdict)

    def test_remediation_handoff_shape_limits_context(self) -> None:
        result = harness.run_deterministic_scenarios(self.requirements, self.scenarios, run_id="run-unit-003")[0]
        verdict = harness.build_evaluator_verdict(
            self.scenarios["scenarios"][0],
            result.ledger,
            verdict="fail",
            failed_requirements=["cfcp-req-contextforge-authority"],
        )
        handoff = harness.build_remediation_handoff(self.scenarios["scenarios"][0], verdict)
        self.assertEqual(verdict["failed_requirements"], handoff["failed_requirements"])
        self.assertEqual("passed", handoff["redaction_status"])
        self.assertIn("oracle mutation", handoff["forbidden_context"])
        self.assertNotIn("hidden_initial_conditions", " ".join(handoff["allowed_context"]))
        self.assertTrue(handoff["verdict_ref"]["content_digest"].startswith("sha256:"))


if __name__ == "__main__":
    unittest.main()
