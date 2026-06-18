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
import control_plane_tool_policy as tool_policy


FIXTURE_PATH = REPO_ROOT / "tests/fixtures/control_plane_tool_policy_cases.json"


class ControlPlaneToolPolicyFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with FIXTURE_PATH.open("r", encoding="utf-8") as handle:
            cls.fixture = json.load(handle)
        cls.cases = {case["name"]: case for case in cls.fixture["cases"]}

    def compile_case(self, name: str) -> dict[str, Any]:
        case = self.cases[name]
        inputs = case["inputs"]
        return tool_policy.compile_tool_policy(
            service_binding=self.fixture["service_binding"],
            virtual_server_id=self.fixture["virtual_server_id"],
            target_client=self.fixture["target_client"],
            tools=inputs["tools"],
            manual_overrides=inputs.get("manual_overrides", []),
            expected_gateway_revision=inputs.get("expected_gateway_revision", self.fixture["expected_gateway_revision"]),
            current_gateway_revision=inputs.get("current_gateway_revision", self.fixture["current_gateway_revision"]),
            expected_target_client_digest=inputs.get("expected_target_client_digest", self.fixture["expected_target_client_digest"]),
            current_target_client_digest=inputs.get("current_target_client_digest", self.fixture["current_target_client_digest"]),
            compiled_at=self.fixture["resolved_at"],
        )

    def assert_case_expectations(self, result: dict[str, Any], expected: dict[str, Any]) -> None:
        contracts.validate_artifact("semantic_tool_policy", result)
        self.assertEqual(expected["status"], result["x_status"])
        self.assertEqual(expected["compiled_tool_ids"], result["compiled_tool_ids"])
        self.assertEqual(expected["excluded_tool_ids"], sorted(item["tool_id"] for item in result["x_excluded_tools"]))
        self.assertEqual(expected["negative_check_count"], len(result["negative_checks"]))
        self.assertEqual(set(expected["blocker_types"]), {item["type"] for item in result["x_blockers"]})
        self.assertEqual(bool(result["x_blockers"]), result["x_repair_plan_trigger"])
        self.assertEqual(len(result["x_blockers"]), len(result["x_open_items"]))

    def test_fixture_names_cover_w6_c_required_cases(self) -> None:
        self.assertEqual(
            {
                "read_only_tools_compile_to_allowed_associations",
                "semantic_scope_changing_and_admin_risks_are_excluded",
                "unknown_missing_metadata_and_service_binding_fail_closed",
                "validation_probe_request_redirects_mutating_tool_to_safe_read",
                "target_client_mismatch_and_stale_inputs_fail_closed",
                "manual_allow_without_required_evidence_stays_excluded",
                "manual_allow_with_consent_requirement_and_negative_checks_can_allow",
            },
            set(self.cases),
        )

    def test_fixture_cases_match_expected_outputs(self) -> None:
        for name, case in self.cases.items():
            with self.subTest(case=name):
                original_inputs = copy.deepcopy(case["inputs"])
                result = self.compile_case(name)
                self.assert_case_expectations(result, case["expected"])
                self.assertEqual(original_inputs, case["inputs"])

    def test_allowed_policy_is_deterministic_and_preserves_contextforge_as_authority(self) -> None:
        result = self.compile_case("read_only_tools_compile_to_allowed_associations")
        result_again = self.compile_case("read_only_tools_compile_to_allowed_associations")

        self.assertEqual(result, result_again)
        self.assertEqual(["cf-tool-list-files", "cf-tool-read-file"], result["compiled_tool_ids"])
        self.assertEqual(
            [
                {"selector_type": "tool_id", "value": "cf-tool-list-files", "fail_closed": True},
                {"selector_type": "tool_id", "value": "cf-tool-read-file", "fail_closed": True},
            ],
            result["allowed_tool_selectors"],
        )
        self.assertEqual(self.fixture["service_binding"], result["service_binding"])
        self.assertNotIn("codex", result["service_binding"])

    def test_semantic_exclusions_emit_both_negative_check_layers(self) -> None:
        result = self.compile_case("semantic_scope_changing_and_admin_risks_are_excluded")

        excluded_by_tool = {item["tool_id"]: item for item in result["x_excluded_tools"]}
        self.assertIn("scope_changing", excluded_by_tool["cf-tool-activate-project"]["semantic_risk_classes"])
        self.assertIn("catalog_admin", excluded_by_tool["cf-tool-catalog-refresh"]["semantic_risk_classes"])
        self.assertIn("trust", excluded_by_tool["cf-tool-trust-grant"]["semantic_risk_classes"])
        self.assertIn("remote_exposure", excluded_by_tool["cf-tool-open-tunnel"]["semantic_risk_classes"])

        absent_checks = [item for item in result["negative_checks"] if item["check"] == "excluded_tool_absent"]
        layers_by_tool: dict[str, set[str]] = {}
        for check in absent_checks:
            layers_by_tool.setdefault(check["tool_id"], set()).add(check["layer"])
            self.assertEqual("pending", check["status"])
            self.assertEqual("absent", check["expected"])
            self.assertIn(check["original_name"], check["negative_match_names"])
            self.assertIn(check["exposed_name"], check["negative_match_names"])
        self.assertEqual(
            {
                "cf-tool-activate-project": {"contextforge_virtual_server", "target_client"},
                "cf-tool-catalog-refresh": {"contextforge_virtual_server", "target_client"},
                "cf-tool-open-tunnel": {"contextforge_virtual_server", "target_client"},
                "cf-tool-trust-grant": {"contextforge_virtual_server", "target_client"},
            },
            layers_by_tool,
        )

    def test_unknown_missing_metadata_and_mismatches_create_blocking_open_items(self) -> None:
        result = self.compile_case("unknown_missing_metadata_and_service_binding_fail_closed")

        blocker_types = {item["type"] for item in result["x_blockers"]}
        self.assertIn("missing_risk_metadata", blocker_types)
        self.assertIn("missing_service_binding", blocker_types)
        self.assertIn("unknown_risk_class", blocker_types)
        self.assertTrue(all(item["type"] == "tool_policy" for item in result["x_open_items"]))
        self.assertTrue(all(item["severity"] == "blocking" for item in result["x_open_items"]))

    def test_mutating_validation_probe_redirects_to_safe_read_alternative(self) -> None:
        result = self.compile_case("validation_probe_request_redirects_mutating_tool_to_safe_read")

        decision = tool_policy.classify_validation_probe_request(
            result,
            "governance_create_decision",
            safe_probe_candidates=["governance_list"],
        )

        self.assertEqual("redirected", decision["status"])
        self.assertEqual("excluded_unsafe_for_validation", decision["requested_tool_status"])
        self.assertEqual("mutating_validation_probe_rejected", decision["reason"])
        self.assertEqual("pending", decision["validation_result_status"])
        self.assertEqual("not_verified", decision["readiness_effect"])
        self.assertEqual("cf-tool-governance-create", decision["requested_tool"]["tool_id"])
        self.assertEqual("cf-tool-governance-list", decision["safe_alternative"]["tool_id"])
        self.assertEqual(["read_only"], decision["safe_alternative"]["semantic_risk_classes"])

    def test_manual_allowed_mutating_tool_is_still_not_a_validation_probe(self) -> None:
        result = self.compile_case("manual_allow_with_consent_requirement_and_negative_checks_can_allow")

        decision = tool_policy.classify_validation_probe_request(result, "write_project_state")

        self.assertEqual("skipped", decision["status"])
        self.assertEqual("allowed_unsafe_for_validation", decision["requested_tool_status"])
        self.assertEqual("mutating_validation_probe_rejected", decision["reason"])
        self.assertEqual("skipped", decision["validation_result_status"])
        self.assertEqual("not_verified", decision["readiness_effect"])
        self.assertIsNone(decision["safe_alternative"])
        self.assertEqual([], decision["safe_alternatives"])

    def test_missing_validation_probe_is_skipped_not_verified(self) -> None:
        result = self.compile_case("read_only_tools_compile_to_allowed_associations")

        decision = tool_policy.classify_validation_probe_request(result, "missing_safe_probe")

        self.assertEqual("skipped", decision["status"])
        self.assertEqual("missing", decision["requested_tool_status"])
        self.assertEqual("requested_validation_tool_missing", decision["reason"])
        self.assertEqual("skipped", decision["validation_result_status"])
        self.assertEqual("not_verified", decision["readiness_effect"])

    def test_stale_inputs_block_even_otherwise_read_only_tools(self) -> None:
        result = self.compile_case("target_client_mismatch_and_stale_inputs_fail_closed")

        self.assertEqual([], result["compiled_tool_ids"])
        self.assertTrue(result["x_stale_policy_inputs"]["stale"])
        self.assertIn("target_client_mismatch", {item["type"] for item in result["x_blockers"]})
        self.assertIn("stale_policy_inputs", {item["type"] for item in result["x_blockers"]})

    def test_manual_allow_requires_consent_requirement_risk_and_negative_checks(self) -> None:
        missing = self.compile_case("manual_allow_without_required_evidence_stays_excluded")
        present = self.compile_case("manual_allow_with_consent_requirement_and_negative_checks_can_allow")

        self.assertEqual("blocked", missing["x_status"])
        self.assertIn("manual_allow_missing_evidence", {item["type"] for item in missing["x_blockers"]})
        self.assertEqual("compiled", present["x_status"])
        self.assertEqual(["cf-tool-write-state"], present["compiled_tool_ids"])
        self.assertEqual(["service_provision"], present["approval_gates"])

    def test_unmatched_manual_override_fails_closed(self) -> None:
        result = tool_policy.compile_tool_policy(
            service_binding=self.fixture["service_binding"],
            virtual_server_id=self.fixture["virtual_server_id"],
            target_client=self.fixture["target_client"],
            tools=[],
            manual_overrides=[
                {
                    "tool_selector": {"selector_type": "tool_id", "value": "missing-tool", "fail_closed": True},
                    "decision": "deny",
                    "consent_receipt_ref": {
                        "ref": "contextforge://control-plane/consent-receipts/receipt-deny",
                        "content_digest": "sha256:" + "d" * 64,
                        "catalog_revision_or_etag": None,
                        "resolved_at": self.fixture["resolved_at"],
                    },
                }
            ],
            compiled_at=self.fixture["resolved_at"],
        )

        self.assertEqual("blocked", result["x_status"])
        self.assertEqual([], result["compiled_tool_ids"])
        self.assertIn("unmatched_manual_override", {item["type"] for item in result["x_blockers"]})


if __name__ == "__main__":
    unittest.main()
