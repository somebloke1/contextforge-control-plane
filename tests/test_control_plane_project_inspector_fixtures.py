from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Mapping
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import control_plane_contextforge_binding as binding
import control_plane_contracts as contracts
import control_plane_project_adapter as adapter
import control_plane_project_inspector as inspector_lib
import control_plane_project_inspector_seed as seed_lib
import control_plane_project_state as state_lib


FIXTURE_PATH = REPO_ROOT / "tests/fixtures/control_plane_project_inspector_cases.json"


class ControlPlaneProjectInspectorFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with FIXTURE_PATH.open("r", encoding="utf-8") as handle:
            cls.fixture = json.load(handle)
        cls.runtime_cases = {case["name"]: case for case in cls.fixture["runtime_cases"]}
        cls.proof_cases = {case["name"]: case for case in cls.fixture["proof_cases"]}

    def workspace_project(self) -> tempfile.TemporaryDirectory[str]:
        return tempfile.TemporaryDirectory(dir=state_lib.WORKSPACE_ROOT)

    def test_fixture_names_cover_w9_c_required_surface(self) -> None:
        self.assertEqual(
            {
                "empty_root",
                "nested_root",
                "symlink_path_escape",
                "ignored_path",
                "dirty_worktree_root",
                "useful_root_bound_read_only_tools",
                "no_shell_or_file_exfiltration",
            },
            set(self.runtime_cases),
        )
        self.assertEqual(
            {
                "rfc_seeded_project_inspector_not_catalog_candidate",
                "generic_project_init_acceptance_does_not_promote_catalog",
                "client_binding_seed_blocked_until_runtime_proof",
                "client_binding_allowed_after_conformance_readbacks_and_traces",
            },
            set(self.proof_cases),
        )

    def test_runtime_fixture_cases_match_project_inspector_behavior(self) -> None:
        for name in self.runtime_cases:
            with self.subTest(case=name):
                getattr(self, f"assert_{name}")(self.runtime_cases[name])

    def test_seed_fixture_proves_rfc_named_proof_not_catalog_candidate(self) -> None:
        case = self.proof_cases["rfc_seeded_project_inspector_not_catalog_candidate"]
        expected = case["expected"]
        result = self.project_inspector_seed()
        catalog_status = result["catalog_status"]
        operation_classes = {
            step["operation_class"]
            for step in result["service_provision_plan"]["service_provision_steps"]
        }

        self.assertEqual(expected["proof_status"], result["proof_status"])
        self.assertEqual(expected["service_family"], result["service_family"])
        self.assertEqual(expected["service_binding"], result["service_binding"])
        self.assertEqual(expected["proof_status"], catalog_status["status"])
        self.assertEqual(expected["catalog_candidate"], catalog_status["catalog_candidate"])
        self.assertEqual(expected["catalog_promotion_allowed"], catalog_status["catalog_promotion_allowed"])
        self.assertEqual(expected["instantiation_class"], result["contract_card"]["instantiation_class"])
        self.assertNotEqual(
            expected["forbidden_instantiation_class"],
            result["contract_card"]["instantiation_class"],
        )
        self.assertTrue(result["service_provision_plan"]["x_rfc_seeded_proof"])
        self.assertFalse(result["service_provision_plan"]["x_catalog_candidate"])
        self.assertEqual(
            set(expected["forbidden_operation_classes"]) & operation_classes,
            set(),
        )
        contracts.validate_redacted(result)

    def test_generic_project_init_acceptance_does_not_promote_catalog(self) -> None:
        case = self.proof_cases["generic_project_init_acceptance_does_not_promote_catalog"]
        expected = case["expected"]
        spec = self.project_inspector_spec()
        policy = self.project_inspector_policy(spec)
        plan = adapter.plan_project_scoped_adapter(
            spec,
            project_service_decision=case["project_service_decision"],
            semantic_tool_policy=policy,
            conformance_result=self.conformance(spec),
            consent_receipt_refs=self.consent_receipt_refs(case["receipts"]),
            verification_trace_refs=self.trace_refs(case["trace_layers"]),
            generated_at=self.fixture["generated_at"],
        )

        self.assertEqual(expected["status"], plan["status"])
        self.assertEqual(expected["mutation_allowed"], plan["mutation_allowed"])
        self.assertEqual(expected["mutation_performed"], plan["mutation_performed"])
        self.assertEqual(expected["identity_source"], spec["identity"]["source"])
        self.assertEqual(
            expected["client_configs_are_discovery_only"],
            spec["identity"]["client_configs_are_discovery_only"],
        )
        self.assertTrue(plan["planned_sections"])
        self.assertNotIn("catalog_promotion", json.dumps(plan, sort_keys=True))
        self.assertNotIn("user_global_client_trust", json.dumps(plan, sort_keys=True))

    def test_seed_client_binding_is_blocked_until_runtime_proof(self) -> None:
        case = self.proof_cases["client_binding_seed_blocked_until_runtime_proof"]
        expected = case["expected"]
        result = self.project_inspector_seed()
        intent = result["contextforge_binding_intents"]["client_binding"]

        self.assertEqual(expected["decision"], intent["decision"])
        self.assertEqual(expected["eligible_for_client_visible_binding"], intent["eligible_for_client_visible_binding"])
        self.assertLessEqual(set(expected["blocker_types"]), {item["type"] for item in intent["blockers"]})
        self.assertEqual(
            expected["consent_classes"],
            sorted(item["x_consent_class"] for item in result["refs"]["consent_receipt_refs"]),
        )
        self.assertEqual(
            expected["verification_layers"],
            sorted(item["x_verification_layer"] for item in result["refs"]["verification_trace_refs"]),
        )

    def test_client_binding_allowed_after_conformance_readbacks_and_traces(self) -> None:
        case = self.proof_cases["client_binding_allowed_after_conformance_readbacks_and_traces"]
        expected = case["expected"]
        result = self.project_inspector_seed()
        policy = result["semantic_tool_policy"]
        readbacks = self.passed_readbacks(policy)
        virtual_server_ref = self.artifact_ref(
            f"virtual-servers/{result['adapter_spec']['virtual_server']['name']}",
            {"service_binding": result["service_binding"]},
        )

        intent = binding.build_client_binding_intent(
            plan_id=result["service_provision_plan"]["provision_plan_id"],
            project_root=str(Path(self.fixture["project_root"]).resolve(strict=False)),
            service_binding=result["service_binding"],
            target_client=self.fixture["target_client"],
            virtual_server_ref=virtual_server_ref,
            semantic_tool_policy=policy,
            conformance_result=self.conformance(result["adapter_spec"]),
            consent_receipt_refs=result["refs"]["consent_receipt_refs"],
            negative_check_readbacks=readbacks,
            trace_refs=self.trace_refs(["contextforge_gateway", "virtual_server", "tool_policy", "target_client", "redaction"]),
            expected_gateway_digest=self.fixture["gateway_revision"],
            current_gateway_digest=self.fixture["gateway_revision"],
            expected_client_digest=self.fixture["target_client_digest"],
            current_client_digest=self.fixture["target_client_digest"],
            generated_at=self.fixture["generated_at"],
        )

        self.assertEqual(expected["decision"], intent["decision"])
        self.assertEqual(expected["eligible_for_client_visible_binding"], intent["eligible_for_client_visible_binding"])
        self.assertEqual(expected["binding_surface"], intent["binding_intent"]["surface"])
        self.assertEqual(expected["write_set"], intent["write_set"])
        for non_action in expected["non_actions"]:
            self.assertIn(non_action, intent["non_actions"])

    def assert_empty_root(self, case: Mapping[str, Any]) -> None:
        expected = case["expected"]
        with self.workspace_project() as tmp:
            root = Path(tmp).resolve()
            report = inspector_lib.inspect_project(root)

        self.assertEqual(str(root), report["project"]["root"])
        self.assertEqual(expected["root_bound"], report["safety"]["root_bound"])
        self.assertEqual(expected["read_only"], report["safety"]["read_only"])
        self.assertEqual(expected["shell_allowed"], report["safety"]["shell_allowed"])
        self.assertEqual(expected["mutation_allowed"], report["safety"]["mutation_allowed"])
        self.assertEqual(expected["input_path_count"], report["detected_languages"]["input_path_count"])
        self.assertIn(expected["non_action"], report["detected_languages"]["non_actions"])
        self.assertIn(expected["open_item_type"], {item["type"] for item in report["detected_languages"]["open_items"]})

    def assert_nested_root(self, case: Mapping[str, Any]) -> None:
        expected = case["expected"]
        with self.workspace_project() as tmp:
            outer = Path(tmp).resolve()
            inner = outer / case["setup"]["nested_relative"]
            inner.mkdir(parents=True)
            outer_project = inspector_lib.ProjectInspector.for_root(outer).project_identity()["project"]
            inner_project = inspector_lib.ProjectInspector.for_root(inner).project_identity()["project"]

        self.assertEqual(expected["identity_source"], outer_project["identity_source"])
        self.assertEqual(expected["identity_source"], inner_project["identity_source"])
        self.assertNotEqual(outer_project["root"], inner_project["root"])
        self.assertNotEqual(outer_project["root_hash"], inner_project["root_hash"])
        self.assertTrue(inner_project["root"].endswith(expected["nested_relative"]))

    def assert_symlink_path_escape(self, case: Mapping[str, Any]) -> None:
        expected = case["expected"]
        with self.workspace_project() as tmp, tempfile.TemporaryDirectory() as outside_tmp:
            root = Path(tmp).resolve()
            outside = Path(outside_tmp).resolve()
            (outside / case["setup"]["outside_file"]).write_text("outside\n", encoding="utf-8")
            (root / case["setup"]["link_name"]).symlink_to(outside)
            project = inspector_lib.ProjectInspector.for_root(root)

            with self.assertRaises(inspector_lib.ProjectInspectorAccessError) as raised:
                project.classify_path(expected["blocked_path"])

        self.assertIn(expected["error_fragment"], str(raised.exception))

    def assert_ignored_path(self, case: Mapping[str, Any]) -> None:
        setup = case["setup"]
        expected = case["expected"]
        with self.workspace_project() as tmp:
            root = Path(tmp).resolve()
            target = root / setup["file"]
            target.parent.mkdir(parents=True)
            target.write_text("ignored\n", encoding="utf-8")
            project = inspector_lib.ProjectInspector.for_root(root, evidence={"ignored_paths": setup["ignored_paths"]})

            classification = project.classify_path(setup["file"])
            summary = project.ignored_path_summary()
            with self.assertRaises(inspector_lib.ProjectInspectorAccessError):
                project.file_metadata(setup["file"])

        self.assertEqual(expected["classification_status"], classification["status"])
        self.assertEqual(expected["summary_source"], summary["source"])
        self.assertEqual(set(setup["ignored_paths"]), set(summary["ignored_paths"]))

    def assert_dirty_worktree_root(self, case: Mapping[str, Any]) -> None:
        setup = case["setup"]
        expected = case["expected"]
        with self.workspace_project() as tmp:
            root = Path(tmp).resolve()
            project = inspector_lib.ProjectInspector.for_root(
                root,
                evidence={
                    "ignored_paths": setup["ignored_paths"],
                    "dirty_worktree": setup["dirty_worktree"],
                },
            )
            summary = project.dirty_worktree_summary()

        self.assertEqual(expected["source"], summary["source"])
        self.assertEqual(expected["clean"], summary["clean"])
        self.assertEqual(expected["entry_count"], summary["entry_count"])
        self.assertEqual(expected["visible_path"], summary["entries"][0]["path"])
        self.assertEqual(expected["shell_executed"], summary["shell_executed"])

    def assert_useful_root_bound_read_only_tools(self, case: Mapping[str, Any]) -> None:
        setup = case["setup"]
        expected = case["expected"]
        with self.workspace_project() as tmp:
            root = Path(tmp).resolve()
            for relative, content in setup["files"].items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            project = inspector_lib.ProjectInspector.for_root(root)

            with mock.patch.object(subprocess, "run", side_effect=AssertionError("shell called")):
                with mock.patch.object(os, "system", side_effect=AssertionError("shell called")):
                    identity = project.handle_request("get_project_identity")
                    languages = project.handle_request("get_detected_languages")
                    metadata = project.handle_request("get_file_metadata", {"path": expected["metadata_path"]})

        self.assertEqual(str(root), identity["project"]["root"])
        self.assertEqual(expected["selected_language"], languages["selected_primary_profile"]["language_id"])
        self.assertEqual(expected["metadata_path"], metadata["relative_path"])
        self.assertEqual(expected["metadata_kind"], metadata["kind"])
        self.assertEqual(expected["content_digest_status"], metadata["content_digest_status"])

    def assert_no_shell_or_file_exfiltration(self, case: Mapping[str, Any]) -> None:
        setup = case["setup"]
        expected = case["expected"]
        with self.workspace_project() as tmp:
            root = Path(tmp).resolve()
            (root / setup["file"]).write_text(setup["content"], encoding="utf-8")
            project = inspector_lib.ProjectInspector.for_root(root)
            metadata = project.file_metadata(setup["file"])

            for tool_name in expected["forbidden_tools"]:
                with self.subTest(tool_name=tool_name):
                    with self.assertRaises(inspector_lib.ProjectInspectorRequestError):
                        project.handle_request(tool_name, {"path": setup["file"]})

        self.assertEqual(expected["redacted_path"], metadata["relative_path"])
        self.assertNotIn("snippet", metadata)
        self.assertNotIn(expected["not_contains"], json.dumps(metadata, sort_keys=True))

    def project_inspector_seed(self) -> dict[str, Any]:
        return seed_lib.build_project_inspector_seed(
            project_root=self.fixture["project_root"],
            target_client=self.fixture["target_client"],
            generated_at=self.fixture["generated_at"],
            gateway_revision=self.fixture["gateway_revision"],
            target_client_digest=self.fixture["target_client_digest"],
        )

    def project_inspector_spec(self) -> dict[str, Any]:
        return adapter.build_project_inspector_adapter_spec(
            project_root=self.fixture["project_root"],
            target_client=self.fixture["target_client"],
            identity_source="rfc_seed",
        )

    def project_inspector_policy(self, spec: Mapping[str, Any]) -> dict[str, Any]:
        return adapter.compile_adapter_tool_policy(
            spec,
            expected_gateway_revision=self.fixture["gateway_revision"],
            current_gateway_revision=self.fixture["gateway_revision"],
            expected_target_client_digest=self.fixture["target_client_digest"],
            current_target_client_digest=self.fixture["target_client_digest"],
            compiled_at=self.fixture["generated_at"],
        )

    def conformance(self, spec: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "pack_id": f"{self.fixture['target_client']}/project-inspector/passing-fixture",
            "client_name": self.fixture["target_client"],
            "status": "passing_conformance",
            "decision": "allow_target_client_proof",
            "service_binding": spec["service_binding"],
            "project_root": str(Path(self.fixture["project_root"]).resolve(strict=False)),
            "blockers": [],
            "redaction_status": "passed",
        }

    def consent_receipt_refs(self, classes: list[str]) -> list[dict[str, Any]]:
        return [
            {
                **self.artifact_ref(f"consent-receipts/project-inspector/{name}", {"consent_class": name}),
                "consent_class": name,
            }
            for name in classes
        ]

    def trace_refs(self, layers: list[str]) -> list[dict[str, Any]]:
        return [
            {
                **self.artifact_ref(f"verification-traces/project-inspector/{layer}", {"layer": layer}),
                "layer": layer,
                "target_client": self.fixture["target_client"] if layer == "target_client" else None,
                "result": "passed",
            }
            for layer in layers
        ]

    def passed_readbacks(self, policy: Mapping[str, Any]) -> list[dict[str, Any]]:
        readbacks = copy.deepcopy(list(policy["negative_checks"]))
        for item in readbacks:
            item["status"] = "passed"
        return readbacks

    def artifact_ref(self, name: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        return contracts.artifact_ref(
            f"contextforge://control-plane/{name}",
            payload,
            resolved_at=self.fixture["generated_at"],
            catalog_revision_or_etag="fixture",
        )


if __name__ == "__main__":
    unittest.main()
