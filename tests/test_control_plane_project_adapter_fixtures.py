from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import control_plane_project_adapter as adapter
import control_plane_verification as verification


FIXTURE_PATH = REPO_ROOT / "tests/fixtures/control_plane_project_adapter_cases.json"


class ControlPlaneProjectAdapterFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with FIXTURE_PATH.open("r", encoding="utf-8") as handle:
            cls.fixture = json.load(handle)
        cls.cases = {case["name"]: case for case in cls.fixture["cases"]}

    def test_fixture_names_cover_w8_c_required_cases(self) -> None:
        self.assertEqual(
            {
                "serena_current_run_declined_preserves_no_mutation",
                "serena_accepted_shape_is_language_profile_backed_and_non_mutating",
                "serena_activate_project_semantic_scope_changing_filtered",
                "client_visible_verification_missing_target_client_proof_blocks",
                "client_visible_verification_stale_target_client_proof_blocks",
                "scope_changing_tool_remains_filtered_after_refresh_events",
                "project_inspector_uses_same_generic_adapter_without_serena_logic",
            },
            set(self.cases),
        )

    def test_adapter_plan_fixture_cases_match_expected_outputs(self) -> None:
        for name in (
            "serena_current_run_declined_preserves_no_mutation",
            "serena_accepted_shape_is_language_profile_backed_and_non_mutating",
            "client_visible_verification_missing_target_client_proof_blocks",
            "client_visible_verification_stale_target_client_proof_blocks",
            "project_inspector_uses_same_generic_adapter_without_serena_logic",
        ):
            with self.subTest(case=name):
                case = self.cases[name]
                original = copy.deepcopy(case)
                plan = self.plan_case(case)
                self.assert_plan_expectations(plan, case["expected"])
                self.assertEqual(original, case)

    def test_current_run_serena_decline_is_modeled_and_preserved(self) -> None:
        case = self.cases["serena_current_run_declined_preserves_no_mutation"]
        env_decision = case["expected"]["env_decision"]

        self.assertEqual("declined", env_decision)
        self.assertEqual(env_decision, case["project_service_decision"])
        plan = self.plan_case(case)
        self.assertEqual("blocked_declined", plan["status"])
        self.assertEqual({}, plan["planned_sections"])
        self.assertTrue(plan["declined_preservation"]["preserves_decline"])
        self.assertTrue(
            plan["declined_preservation"][
                "no_backend_contextforge_client_trust_server_instance_or_project_mutation"
            ]
        )

    def test_serena_accepted_shape_consumes_language_profile_but_stays_non_mutating(self) -> None:
        case = self.cases["serena_accepted_shape_is_language_profile_backed_and_non_mutating"]
        plan = self.plan_case(case)
        expected = case["expected"]
        language = plan["language_requirement"]

        self.assertEqual("blocked", plan["status"])
        self.assertFalse(plan["mutation_allowed"])
        self.assertFalse(plan["mutation_performed"])
        self.assertEqual(expected["language_profile_id"], language["selected_language_profile_id"])
        self.assertEqual(expected["language_consumed_from"], language["consumed_from"])
        self.assertEqual(expected["service_local_language_policy"], language["service_local_language_policy"])
        self.assertLessEqual(
            set(expected["required_probe_ids"]),
            {probe["probe_id"] for probe in language["baseline_probes"]},
        )
        self.assertEqual({}, plan["planned_sections"])
        self.assertIn("semantic_risk_excluded", {item["type"] for item in plan["blockers"]})

    def test_activate_project_scope_changing_filter_and_negative_visibility_checks(self) -> None:
        case = self.cases["serena_activate_project_semantic_scope_changing_filtered"]
        policy = self.compile_policy(self.build_spec(case))
        expected = case["expected"]
        excluded = {item["tool_id"]: item for item in policy["x_excluded_tools"]}

        self.assertIn(expected["excluded_tool_id"], excluded)
        activate = excluded[expected["excluded_tool_id"]]
        self.assertEqual(expected["excluded_original_name"], activate["original_name"])
        self.assertIn(expected["semantic_risk_class"], activate["semantic_risk_classes"])
        self.assertLessEqual(set(expected["scope_impacts"]), set(activate["scope_impacts"]))
        self.assertNotIn(expected["not_compiled_tool_id"], policy["compiled_tool_ids"])
        self.assertEqual(
            set(expected["negative_check_layers"]),
            {check["layer"] for check in policy["negative_checks"] if check.get("tool_id") == expected["excluded_tool_id"]},
        )

    def test_client_visible_verification_blocks_missing_or_stale_target_client_proof(self) -> None:
        for name in (
            "client_visible_verification_missing_target_client_proof_blocks",
            "client_visible_verification_stale_target_client_proof_blocks",
        ):
            with self.subTest(case=name):
                case = self.cases[name]
                plan = self.plan_case(case)
                expected = case["expected"]
                transition = self.lifecycle_transition(case)

                self.assertEqual(expected["status"], plan["status"])
                self.assertLessEqual(set(expected["blocker_types"]), {item["type"] for item in plan["blockers"]})
                trace_blocker = next(item for item in plan["blockers"] if item["type"] == "trace_missing")
                self.assertEqual(expected["missing_trace_layers"], trace_blocker["missing"])
                self.assertEqual(expected["verification_decision"], transition["decision"])
                self.assertEqual(expected["verification_reason"], transition["reason"])
                self.assertEqual(
                    expected["target_client_matrix_status"],
                    transition["matrix"]["layers"]["target_client"]["status"],
                )

    def test_scope_changing_tools_remain_filtered_after_modeled_refresh_events(self) -> None:
        case = self.cases["scope_changing_tool_remains_filtered_after_refresh_events"]
        expected = case["expected"]
        spec = self.build_spec(case)

        for event in case["refresh_events"]:
            with self.subTest(event=event):
                policy = self.compile_policy(spec, current_gateway_revision=f"{event}-gateway-r1")
                excluded = {item["tool_id"]: item for item in policy["x_excluded_tools"]}
                self.assertEqual(expected["event_policy_status"][event], policy["x_status"])
                self.assertIn(expected["excluded_tool_id"], excluded)
                self.assertIn(expected["semantic_risk_class"], excluded[expected["excluded_tool_id"]]["semantic_risk_classes"])
                self.assertEqual(
                    set(expected["negative_check_layers"]),
                    {
                        check["layer"]
                        for check in policy["negative_checks"]
                        if check.get("tool_id") == expected["excluded_tool_id"]
                    },
                )

    def test_project_inspector_uses_same_generic_adapter_without_serena_specific_logic(self) -> None:
        case = self.cases["project_inspector_uses_same_generic_adapter_without_serena_logic"]
        spec = self.build_spec(case)
        policy = self.compile_policy(spec)
        plan = self.plan_case(case)
        expected = case["expected"]

        self.assertEqual(expected["adapter_id"], spec["adapter_id"])
        self.assertEqual(expected["service_binding"], plan["service_binding"])
        self.assertEqual(expected["compiled_tool_ids"], policy["compiled_tool_ids"])
        self.assertEqual(expected["language_profile_id"], spec["language_requirement"]["selected_language_profile_id"])
        self.assertEqual(expected["language_consumed_from"], spec["language_requirement"]["consumed_from"])
        self.assertNotIn(expected["forbidden_command_fragment"], " ".join(spec["backend_instance"]["command"]))
        self.assertEqual("planned_non_mutating", plan["status"])

    def build_spec(self, case: dict[str, Any]) -> dict[str, Any]:
        if case["adapter"] == "serena":
            return adapter.build_serena_adapter_spec(
                project_root=self.fixture["project_root"],
                selected_language_profile_id=case.get("selected_language_profile_id"),
            )
        if case["adapter"] == "project-inspector":
            return adapter.build_project_inspector_adapter_spec(
                project_root=self.fixture["project_root"],
                selected_language_profile_id=case.get("selected_language_profile_id"),
                language_profile_required=case.get("language_profile_required", False),
            )
        raise AssertionError(f"unknown adapter fixture: {case['adapter']}")

    def compile_policy(
        self,
        spec: dict[str, Any],
        *,
        current_gateway_revision: str | None = None,
        current_target_client_digest: str | None = None,
    ) -> dict[str, Any]:
        return adapter.compile_adapter_tool_policy(
            spec,
            expected_gateway_revision=self.fixture["gateway_revision"],
            current_gateway_revision=current_gateway_revision or self.fixture["gateway_revision"],
            expected_target_client_digest=self.fixture["target_client_digest"],
            current_target_client_digest=current_target_client_digest or self.fixture["target_client_digest"],
            compiled_at=self.fixture["resolved_at"],
        )

    def plan_case(self, case: dict[str, Any]) -> dict[str, Any]:
        spec = self.build_spec(case)
        policy = self.compile_policy(spec) if case.get("policy") == "fresh" else None
        return adapter.plan_project_scoped_adapter(
            spec,
            project_service_decision=case["project_service_decision"],
            semantic_tool_policy=policy,
            conformance_result=self.conformance(case, spec),
            consent_receipt_refs=self.receipt_refs(case.get("receipts", [])),
            verification_trace_refs=self.trace_refs(case.get("trace_layers", []), case.get("trace_result_by_layer", {})),
            generated_at=self.fixture["resolved_at"],
        )

    def conformance(self, case: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any] | None:
        mode = case.get("conformance")
        if mode == "omitted" or not mode:
            return None
        if mode == "passing":
            return {
                "client_name": spec["client_binding"]["target_client"],
                "status": "passing_conformance",
                "decision": "allow_target_client_proof",
                "service_binding": spec["service_binding"],
                "project_root": self.fixture["project_root"],
                "blockers": [],
            }
        if mode == "stale":
            return {
                "client_name": spec["client_binding"]["target_client"],
                "status": "stale",
                "decision": "block_stale_target_client_proof",
                "service_binding": spec["service_binding"],
                "project_root": self.fixture["project_root"],
                "blockers": [{"type": "target_client_proof_stale"}],
            }
        raise AssertionError(f"unknown conformance fixture: {mode}")

    def receipt_refs(self, classes: list[str]) -> list[dict[str, Any]]:
        return [
            {
                "ref": f"contextforge://control-plane/receipts/{name}",
                "content_digest": self.digest(name),
                "resolved_at": self.fixture["resolved_at"],
                "consent_class": name,
            }
            for name in classes
        ]

    def trace_refs(self, layers: list[str], result_by_layer: dict[str, str]) -> list[dict[str, Any]]:
        return [
            {
                "ref": f"contextforge://control-plane/traces/{layer}",
                "content_digest": self.digest(layer),
                "resolved_at": self.fixture["resolved_at"],
                "layer": layer,
                "result": result_by_layer.get(layer, "passed"),
            }
            for layer in layers
        ]

    def lifecycle_transition(self, case: dict[str, Any]) -> dict[str, Any]:
        spec = self.build_spec(case)
        transition = case["verification_transition"]
        traces = []
        for layer, status in transition["trace_status_by_layer"].items():
            failure_classification = "target_client_proof_stale" if status == "stale" else None
            trace = verification.build_verification_trace(
                trace_id=f"{case['name']}:{layer}",
                plan_id="adapter-fixture-plan",
                step_id="client-visible-proof",
                service_binding=spec["service_binding"],
                layer=layer,
                probe_id=f"{layer}-probe",
                probe_type="fixture",
                subject=f"{layer} client-visible verification",
                status=status,
                observations={"summary": f"{layer} fixture status {status}"},
                target_client=spec["client_binding"]["target_client"],
                adapter_conformance_pack=None,
                failure_classification=failure_classification,
                generated_at=self.fixture["resolved_at"],
            )
            traces.append(trace)

        trace_refs = [
            verification.build_verification_trace_ref(trace, resolved_at=self.fixture["resolved_at"])
            for trace in traces
        ]
        return verification.validate_lifecycle_transition(
            plan_id="adapter-fixture-plan",
            step_id="client-visible-proof",
            service_binding=spec["service_binding"],
            target_state="verified",
            required_layers=transition["required_layers"],
            trace_refs=trace_refs,
            trace_artifacts=traces,
            target_client=spec["client_binding"]["target_client"],
        )

    def assert_plan_expectations(self, plan: dict[str, Any], expected: dict[str, Any]) -> None:
        self.assertEqual(expected["status"], plan["status"])
        if "mutation_allowed" in expected:
            self.assertEqual(expected["mutation_allowed"], plan["mutation_allowed"])
        if "mutation_performed" in expected:
            self.assertEqual(expected["mutation_performed"], plan["mutation_performed"])
        if "project_service_decision" in expected:
            self.assertEqual(expected["project_service_decision"], plan["project_service_decision"])
        if "planned_section_keys" in expected:
            self.assertEqual(set(expected["planned_section_keys"]), set(plan["planned_sections"]))
        if "blocker_types" in expected:
            self.assertLessEqual(set(expected["blocker_types"]), {item["type"] for item in plan["blockers"]})
        if expected.get("declined_preserved"):
            self.assertTrue(plan["declined_preservation"]["preserves_decline"])
        if "non_action_fragments" in expected:
            encoded_non_actions = "\n".join(plan["non_actions"])
            for fragment in expected["non_action_fragments"]:
                self.assertIn(fragment, encoded_non_actions)

    @staticmethod
    def digest(value: str) -> str:
        seed = "".join(ch for ch in value.lower() if ch.isalnum())[:1] or "a"
        return "sha256:" + seed * 64


if __name__ == "__main__":
    unittest.main()
