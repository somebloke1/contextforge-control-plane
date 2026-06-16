from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import control_plane_project_adapter as adapter


PROJECT_ROOT = "/home/dgk/workspace/context-portal"
STAMP = "2026-05-30T20:21:54Z"


def ref(name: str, *, consent_class: str | None = None, layer: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ref": f"contextforge://control-plane/{name}",
        "content_digest": "sha256:" + (name.replace("/", "")[:1] or "a") * 64,
        "resolved_at": STAMP,
    }
    if consent_class:
        result["consent_class"] = consent_class
    if layer:
        result["layer"] = layer
        result["result"] = "passed"
    return result


def receipt_refs() -> list[dict[str, Any]]:
    return [
        ref("receipts/service-provision", consent_class="service_provision"),
        ref("receipts/project-local-config", consent_class="project_local_config_write"),
    ]


def trace_refs() -> list[dict[str, Any]]:
    return [ref(f"traces/{layer}", layer=layer) for layer in adapter.REQUIRED_TRACE_LAYERS]


def passing_conformance(service_binding: str, *, target_client: str = "codex") -> dict[str, Any]:
    return {
        "client_name": target_client,
        "status": "passing_conformance",
        "decision": "allow_target_client_proof",
        "service_binding": service_binding,
        "project_root": PROJECT_ROOT,
        "blockers": [],
    }


def compiled_policy(spec: dict[str, Any]) -> dict[str, Any]:
    return adapter.compile_adapter_tool_policy(
        spec,
        expected_gateway_revision="gateway-r1",
        current_gateway_revision="gateway-r1",
        expected_target_client_digest="sha256:client-r1",
        current_target_client_digest="sha256:client-r1",
        compiled_at=STAMP,
    )


class ControlPlaneProjectAdapterTests(unittest.TestCase):
    def test_declined_serena_plan_preserves_decline_and_has_no_mutating_sections(self) -> None:
        spec = adapter.build_serena_adapter_spec(project_root=PROJECT_ROOT, selected_language_profile_id="python")
        spec_before = copy.deepcopy(spec)

        plan = adapter.plan_project_scoped_adapter(
            spec,
            project_service_decision="declined",
            semantic_tool_policy=None,
            conformance_result=None,
            consent_receipt_refs=[],
            verification_trace_refs=[],
            generated_at=STAMP,
        )

        self.assertEqual(spec_before, spec)
        self.assertEqual("blocked_declined", plan["status"])
        self.assertEqual("declined", plan["project_service_decision"])
        self.assertFalse(plan["mutation_allowed"])
        self.assertFalse(plan["mutation_performed"])
        self.assertEqual({}, plan["planned_sections"])
        self.assertTrue(plan["declined_preservation"]["preserves_decline"])
        self.assertTrue(plan["declined_preservation"]["no_backend_contextforge_client_trust_server_instance_or_project_mutation"])
        self.assertIn("service_declined", {item["type"] for item in plan["blockers"]})
        encoded = str(plan)
        self.assertIn("does not write backend homes", encoded)
        self.assertNotIn("mutation_performed': True", encoded)

    def test_current_run_serena_decline_blocks_serena_planning(self) -> None:
        spec = adapter.build_serena_adapter_spec(project_root=PROJECT_ROOT, selected_language_profile_id="python")
        plan = adapter.plan_project_scoped_adapter(
            spec,
            project_service_decision="declined",
            semantic_tool_policy=None,
            conformance_result=None,
            consent_receipt_refs=[],
            verification_trace_refs=[],
            generated_at=STAMP,
        )

        self.assertEqual("blocked_declined", plan["status"])
        self.assertEqual({}, plan["planned_sections"])
        self.assertFalse(plan["mutation_allowed"])

    def test_project_inspector_accepted_plan_shape_is_generic_and_non_mutating(self) -> None:
        spec = adapter.build_project_inspector_adapter_spec(project_root=PROJECT_ROOT)
        policy = compiled_policy(spec)

        plan = adapter.plan_project_scoped_adapter(
            spec,
            project_service_decision="accepted",
            semantic_tool_policy=policy,
            conformance_result=passing_conformance(spec["service_binding"]),
            consent_receipt_refs=receipt_refs(),
            verification_trace_refs=trace_refs(),
            generated_at=STAMP,
        )

        self.assertEqual("planned_non_mutating", plan["status"])
        self.assertFalse(plan["mutation_allowed"])
        self.assertFalse(plan["mutation_performed"])
        self.assertEqual([], plan["blockers"])
        self.assertEqual("project-inspector:project", plan["service_binding"])
        self.assertIn("backend_instance", plan["planned_sections"])
        self.assertIn("contextforge_registration", plan["planned_sections"])
        self.assertIn("virtual_server", plan["planned_sections"])
        self.assertIn("client_binding", plan["planned_sections"])
        self.assertEqual("control_plane_tool_policy", plan["adapter_spec"]["tool_policy"]["compiler"])
        self.assertEqual("project_local", plan["planned_sections"]["client_binding"]["scope"])
        self.assertEqual("contextforge_api_or_admin_behavior", plan["planned_sections"]["contextforge_registration"]["registration_path"])
        self.assertEqual("server-instances/project-inspector-project", plan["planned_sections"]["server_instance_home"].split(f"{PROJECT_ROOT}/", 1)[1])

    def test_serena_consumes_language_profile_metadata_not_service_local_policy(self) -> None:
        spec = adapter.build_serena_adapter_spec(project_root=PROJECT_ROOT, selected_language_profile_id="rust")
        requirement = spec["language_requirement"]

        self.assertTrue(requirement["required"])
        self.assertEqual("rust", requirement["selected_language_profile_id"])
        self.assertEqual("control_plane_language_profiles", requirement["consumed_from"])
        self.assertFalse(requirement["service_local_language_policy"])
        self.assertEqual("contextforge://control-plane/language-profiles/rust/v1", requirement["language_profile_ref"]["ref"])
        self.assertIn("rustc-version", {item["probe_id"] for item in requirement["baseline_probes"]})
        self.assertIn("rust-analyzer-version", {item["probe_id"] for item in requirement["baseline_probes"]})

    def test_activate_project_is_a_semantic_scope_changing_tool_exclusion(self) -> None:
        spec = adapter.build_serena_adapter_spec(project_root=PROJECT_ROOT, selected_language_profile_id="python")
        policy = compiled_policy(spec)
        excluded = {item["original_name"]: item for item in policy["x_excluded_tools"]}

        self.assertIn("activate_project", excluded)
        self.assertIn("scope_changing", excluded["activate_project"]["semantic_risk_classes"])
        self.assertIn("active_project", excluded["activate_project"]["scope_impacts"])
        self.assertNotIn("activate_project", policy["compiled_tool_ids"])
        self.assertTrue(any(check["tool_id"] == "serena-activate-project" for check in policy["negative_checks"]))
        tool_fixture = next(item for item in spec["tool_policy"]["tool_fixtures"] if item["original_name"] == "activate_project")
        self.assertEqual(["scope_changing"], tool_fixture["semantic_risk_classes"])

    def test_second_service_supports_optional_or_read_only_language_profile_without_serena_logic(self) -> None:
        no_language = adapter.build_project_inspector_adapter_spec(project_root=PROJECT_ROOT)
        read_only_language = adapter.build_project_inspector_adapter_spec(
            project_root=PROJECT_ROOT,
            selected_language_profile_id="typescript_javascript",
            language_profile_required=True,
        )

        self.assertEqual("project-inspector", no_language["adapter_id"])
        self.assertFalse(no_language["language_requirement"]["required"])
        self.assertIsNone(no_language["language_requirement"]["language_profile_ref"])
        self.assertEqual("project-inspector", read_only_language["adapter_id"])
        self.assertEqual("typescript_javascript", read_only_language["language_requirement"]["selected_language_profile_id"])
        self.assertEqual("control_plane_language_profiles", read_only_language["language_requirement"]["consumed_from"])
        self.assertNotIn("serena", str(read_only_language["backend_instance"]["command"]))

    def test_missing_language_profile_blocks_language_dependent_adapter(self) -> None:
        spec = adapter.build_serena_adapter_spec(project_root=PROJECT_ROOT, selected_language_profile_id=None)
        plan = adapter.plan_project_scoped_adapter(
            spec,
            project_service_decision="accepted",
            semantic_tool_policy=compiled_policy(spec),
            conformance_result=passing_conformance(spec["service_binding"]),
            consent_receipt_refs=receipt_refs(),
            verification_trace_refs=trace_refs(),
            generated_at=STAMP,
        )

        self.assertEqual("blocked", plan["status"])
        self.assertIn("language_profile_missing", {item["type"] for item in plan["blockers"]})

    def test_missing_policy_conformance_receipts_and_traces_fail_closed(self) -> None:
        spec = adapter.build_project_inspector_adapter_spec(project_root=PROJECT_ROOT)
        plan = adapter.plan_project_scoped_adapter(
            spec,
            project_service_decision="accepted",
            semantic_tool_policy=None,
            conformance_result=None,
            consent_receipt_refs=[],
            verification_trace_refs=[],
            generated_at=STAMP,
        )

        blocker_types = {item["type"] for item in plan["blockers"]}
        self.assertEqual("blocked", plan["status"])
        self.assertIn("missing_semantic_tool_policy", blocker_types)
        self.assertIn("missing_conformance", blocker_types)
        self.assertIn("missing_service_provision_receipt", blocker_types)
        self.assertIn("missing_project_local_config_write_receipt", blocker_types)
        self.assertIn("trace_missing", blocker_types)
        self.assertEqual({}, plan["planned_sections"])

    def test_client_derived_service_identity_is_rejected_even_when_other_gates_pass(self) -> None:
        spec = adapter.build_project_inspector_adapter_spec(project_root=PROJECT_ROOT, identity_source="client_config")
        policy = compiled_policy(spec)
        plan = adapter.plan_project_scoped_adapter(
            spec,
            project_service_decision="accepted",
            semantic_tool_policy=policy,
            conformance_result=passing_conformance(spec["service_binding"]),
            consent_receipt_refs=receipt_refs(),
            verification_trace_refs=trace_refs(),
            generated_at=STAMP,
        )

        self.assertEqual("blocked", plan["status"])
        self.assertIn("client_derived_identity", {item["type"] for item in plan["blockers"]})
        self.assertTrue(plan["adapter_spec"]["identity"]["client_configs_are_discovery_only"])


if __name__ == "__main__":
    unittest.main()
