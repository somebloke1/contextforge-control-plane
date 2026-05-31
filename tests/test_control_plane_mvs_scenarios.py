from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import control_plane_mvs_scenarios as mvs
import control_plane_test_harness as harness


class ControlPlaneMvsScenarioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = mvs.load_mvs_fixture()
        cls.evidence = mvs.execute_mvs_scenarios(cls.fixture)
        cls.requirements = harness.load_requirements()

    def test_fixture_shape_and_required_scope_topics(self) -> None:
        self.assertEqual(1, self.fixture["version"])
        scenario_ids = {scenario["scenario_id"] for scenario in self.fixture["scenarios"]}
        self.assertEqual(len(scenario_ids), len(self.fixture["scenarios"]))

        topics = {
            topic
            for scenario in self.fixture["scenarios"]
            for topic in scenario["scope_topics"]
        }
        expected_topics = {
            "project-state",
            "sticky declines",
            "disabled/no-service state",
            "planning",
            "consent",
            "apply",
            "journal recovery",
            "Codex trust",
            "semantic tool policy",
            "declined Serena",
            "generic project adapter",
            "project-inspector",
            "shared-service capsule",
            "service-management handoff",
            "language-profile behavior",
            "service-memory governance boundary",
            "governance reconciliation",
            "malicious metadata",
            "prompt injection",
            "auth wrappers",
            "auth profiles",
            "remote exposure gates",
        }
        self.assertLessEqual(expected_topics, topics)

    def test_executor_does_not_mutate_fixture_inputs(self) -> None:
        original = copy.deepcopy(self.fixture)
        mvs.execute_mvs_scenarios(self.fixture)
        self.assertEqual(original, self.fixture)

    def test_evidence_schema_shape_and_delegates_inference_to_w12_b(self) -> None:
        evidence = self.evidence
        self.assertEqual(1, evidence["version"])
        self.assertEqual("W12-A", evidence["agent"])
        self.assertEqual("passed", evidence["redaction_status"])
        self.assertTrue(evidence["content_digest"].startswith("sha256:"))
        self.assertFalse(evidence["inference_inclusive"]["executed_by_w12_a"])
        self.assertEqual("W12-B", evidence["inference_inclusive"]["delegated_owner"])
        self.assertEqual("delegated", evidence["inference_inclusive"]["status"])
        self.assertTrue(evidence["scenarios"])
        self.assertTrue(all(scenario["status"] == "passed" for scenario in evidence["scenarios"]))

    def test_every_must_pass_mvs_requirement_has_deterministic_and_probe_evidence(self) -> None:
        coverage = self.evidence["coverage"]
        self.assertTrue(coverage["mvs_deterministic_probe_complete"])
        rows = {row["requirement_id"]: row for row in coverage["requirements"]}
        required = {
            item["requirement_id"]
            for item in self.requirements["requirements"]
            if item["mvs_required"] and item["acceptance_gate"] == "must_pass_mvs"
        }
        self.assertEqual(required, set(rows))
        for requirement_id, row in rows.items():
            with self.subTest(requirement=requirement_id):
                self.assertTrue(row["deterministic"])
                self.assertTrue(row["probe"])
                self.assertEqual([], row["gaps"])
                self.assertEqual("delegated", row["inference_inclusive"]["status"])

    def test_no_secret_shaped_outputs_and_no_mutation(self) -> None:
        mvs.assert_no_secret_shaped_outputs(self.evidence)
        self.assertEqual("passed", self.evidence["secret_scan"]["status"])
        attestation = self.evidence["no_mutation_attestation"]
        self.assertEqual("passed", attestation["status"])
        self.assertFalse(attestation["live_mutation_performed"])
        self.assertEqual(attestation["sentinel_before"], attestation["sentinel_after"])
        for scenario in self.evidence["scenarios"]:
            for check in scenario["checks"]:
                with self.subTest(check=check["check_id"]):
                    self.assertFalse(check["mutation_performed"])

    def test_adversarial_malicious_metadata_case_fails_closed(self) -> None:
        checks = {
            check["check_id"]: check
            for scenario in self.evidence["scenarios"]
            for check in scenario["checks"]
        }
        check = checks["w12a-malicious-metadata-prompt-injection"]
        observed = check["observed"]

        self.assertEqual("passed", check["result"])
        self.assertTrue(observed["adversarial_case"])
        self.assertEqual("blocked", observed["status"])
        self.assertEqual(["cf-tool-malicious-metadata"], observed["excluded_tool_ids"])
        self.assertEqual(["contextforge_virtual_server", "target_client"], observed["negative_check_layers"])

    def test_all_checks_cite_requirements_layers_and_source_refs(self) -> None:
        known_requirements = {item["requirement_id"] for item in self.requirements["requirements"]}
        for scenario in self.evidence["scenarios"]:
            for check in scenario["checks"]:
                with self.subTest(check=check["check_id"]):
                    self.assertTrue(set(check["requirement_ids"]) <= known_requirements)
                    self.assertTrue(set(check["layers"]) <= {"deterministic", "probe"})
                    self.assertTrue(check["source_refs"])
                    self.assertEqual("passed", check["redaction_status"])
                    self.assertTrue(check["content_digest"].startswith("sha256:"))

    def test_write_evidence_round_trip_shape(self) -> None:
        target = REPO_ROOT / "run/contextforge-control-plane-implementation/20260530T202154Z/wave12/w12-a-deterministic-evidence.json"
        encoded = json.dumps(self.evidence, indent=2, sort_keys=True)
        decoded = json.loads(encoded)
        self.assertEqual(self.evidence["content_digest"], decoded["content_digest"])
        self.assertTrue(str(target).endswith("w12-a-deterministic-evidence.json"))


if __name__ == "__main__":
    unittest.main()
