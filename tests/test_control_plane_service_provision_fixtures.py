from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import control_plane_contextforge_binding as binding
import control_plane_contracts as contracts
import control_plane_project_state as project_state
import control_plane_service_provision as provision


FIXTURE_PATH = REPO_ROOT / "tests/fixtures/control_plane_service_provision_cases.json"


class ControlPlaneServiceProvisionFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with FIXTURE_PATH.open("r", encoding="utf-8") as handle:
            cls.fixture = json.load(handle)
        cls.apply_cases = {case["name"]: case for case in cls.fixture["apply_outcome_cases"]}
        cls.recovery_cases = {case["name"]: case for case in cls.fixture["contextforge_recovery_cases"]}
        cls.client_cases = {case["name"]: case for case in cls.fixture["client_binding_cases"]}
        cls.exposure_cases = {case["name"]: case for case in cls.fixture["exposure_gate_cases"]}

    def test_fixture_names_cover_w7c_recovery_surface(self) -> None:
        self.assertEqual(
            {
                "interrupted_provision_needs_resume",
                "port_conflict_fresh_approval_required",
                "stale_owned_unit_forward_repair",
                "stale_unmanaged_unit_rollback_workflow",
                "stale_system_unit_manual_recovery",
                "readiness_failure_forward_repair",
            },
            set(self.apply_cases),
        )
        self.assertEqual(
            {
                "partial_contextforge_registration_missing_resume",
                "partial_stale_virtual_server_policy_forward_repair",
                "client_config_conflict_helper_mediated_recovery",
                "stale_target_client_digest_fresh_approval_required",
            },
            set(self.recovery_cases),
        )

    def test_service_provision_recovery_apply_fixtures_match_expected_outcomes(self) -> None:
        plan = self.provision_plan()
        contracts.validate_artifact("service_provision_plan", plan)

        for name, case in self.apply_cases.items():
            with self.subTest(case=name):
                result = provision.classify_apply_outcomes(
                    plan,
                    current_artifacts=self.current_artifacts(plan, case["current_artifacts"]),
                    unit_observation=self.unit_observation(plan, case["unit_observation"]),
                    port_observations=self.port_observations(case["ports"]),
                    readiness_observations=self.readiness_observations(case["readiness"]),
                )
                expected = case["expected"]
                self.assertEqual(expected["aggregate_outcome"], result["aggregate_outcome"])
                for component, outcome in expected.get("components", {}).items():
                    self.assertEqual(outcome, result["component_outcomes"][component]["outcome"])
                self.assertFalse(result["mutation_performed"])

    def test_contextforge_partial_recovery_fixtures_are_typed(self) -> None:
        for name, case in self.recovery_cases.items():
            with self.subTest(case=name):
                recovery = binding.classify_recovery(case["failure_type"])
                self.assertEqual(case["expected_recovery"], recovery["recovery_outcome"])
                self.assertIn(recovery["recovery_outcome"], recovery["allowed_outcomes"])
                self.assertEqual(
                    case["expected_recovery"] == "fresh_approval_required",
                    recovery["requires_new_consent"],
                )

    def test_client_binding_conflict_and_stale_digest_recovery_fixtures(self) -> None:
        for name, case in self.client_cases.items():
            with self.subTest(case=name):
                intent = self.client_binding_intent(current_client_digest=case.get("current_client_digest", "sha256:client-r1"))
                if case["mode"] == "write_hook":
                    result = binding.build_client_write_hook_preflight(
                        client_binding_intent=intent,
                        owned_block_class=case["owned_block_class"],
                        config_scope="project_local",
                    )
                else:
                    result = intent

                self.assertEqual(case["expected_decision"], result["decision"])
                blockers = self.blockers_by_type(result)
                for blocker_type in case["expected_blockers"]:
                    self.assertIn(blocker_type, blockers)
                    self.assertEqual(case["expected_recovery"], blockers[blocker_type]["recovery"])

    def test_client_exposure_is_blocked_until_all_gates_pass(self) -> None:
        for name, case in self.exposure_cases.items():
            with self.subTest(case=name):
                intent = self.client_binding_intent(
                    policy=self.semantic_policy(status=case.get("policy_status", "compiled")),
                    conformance_result=self.conformance(status=case.get("conformance_status", "passing_conformance")),
                    consent_classes=case.get("consent_refs"),
                    readbacks_mode=case.get("negative_readbacks", "passed"),
                    trace_layers=case.get("trace_layers"),
                )
                expected_decision = case.get("expected_decision", "block")
                self.assertEqual(expected_decision, intent["decision"])
                self.assertEqual(case.get("expected_eligible", False), intent["eligible_for_client_visible_binding"])
                blockers = self.blockers_by_type(intent)
                for blocker_type in case.get("expected_blockers", []):
                    self.assertIn(blocker_type, blockers)

    def test_generated_state_and_intents_reference_consent_receipts_and_verification_traces(self) -> None:
        case = self.fixture["state_reference_case"]
        plan = self.provision_plan()
        registration = self.registration_intent()
        virtual_server = self.virtual_server_intent()
        client_binding = self.client_binding_intent()
        service_state = self.generated_service_state(plan, client_binding)

        self.assertEqual(case["expected_lifecycle_state"], service_state["lifecycle"]["current_state"])
        self.assertEqual(case["expected_recovery_outcome"], service_state["lifecycle"]["recovery_outcome"])
        self.assertEqual(case["expected_receipt_ref_count"], len(service_state["consent_receipt_refs"]))
        self.assertEqual(case["expected_trace_layers"], [item["x_layer"] for item in service_state["verification_trace_refs"]])
        self.assertEqual(service_state["consent_receipt_refs"], plan["consent_receipt_refs"])
        self.assertEqual(service_state["verification_trace_refs"], plan["produced_artifact_refs"])

        for intent in (registration, virtual_server, client_binding):
            self.assertTrue(intent["required_consent_receipt_refs"])
        self.assertEqual(
            sorted(["contextforge_gateway", "virtual_server", "tool_policy", "redaction"]),
            sorted(registration["trace_requirements"]["required_layers"]),
        )
        self.assertEqual(
            sorted(["contextforge_gateway", "virtual_server", "tool_policy", "redaction"]),
            sorted(virtual_server["trace_requirements"]["required_layers"]),
        )
        self.assertEqual(
            sorted(["contextforge_gateway", "virtual_server", "tool_policy", "target_client", "redaction"]),
            sorted(item["layer"] for item in client_binding["required_trace_refs"]),
        )

    def provision_plan(self) -> dict[str, Any]:
        root = self.fixture["project_root"]
        service_binding = self.fixture["service_binding"]
        backend_home = provision.backend_home_path(root, service_binding)
        return provision.build_service_provision_plan(
            project_root=root,
            service_binding=service_binding,
            plan_id=self.fixture["plan_id"],
            backend_command=self.fixture["backend_command"],
            owned_write_set=[
                backend_home,
                f"{backend_home}/.env.placeholder",
                f"{backend_home}/backend-manifest.json",
                "user-systemd:contextforge-proof-project.service",
            ],
            stale_input_refs=self.refs("stale_input_refs"),
            consent_receipt_refs=self.consent_receipt_refs(),
            verification_trace_refs=self.verification_trace_refs(include_backend=True, schema_extensions=True),
            ports=[
                {
                    "port": self.fixture["port"],
                    "bind": "127.0.0.1",
                    "owner": service_binding,
                }
            ],
            readiness_probes=[
                {
                    "probe_id": "proof-health",
                    "probe_type": "http",
                    "target": f"http://127.0.0.1:{self.fixture['port']}/health",
                }
            ],
            required_env=self.fixture["required_env"],
            optional_env=self.fixture["optional_env"],
            policy_refs=self.refs("policy_refs"),
            conformance_refs=self.refs("conformance_refs"),
            upstream={"package": "proof-mcp"},
        )

    def current_artifacts(self, plan: Mapping[str, Any], modes: Mapping[str, str]) -> dict[str, Any]:
        desired = plan["x_desired_artifacts"]
        return {
            name: self.artifact_observation(desired[name], mode)
            for name, mode in modes.items()
            if mode != "absent"
        }

    def artifact_observation(self, desired: Mapping[str, Any], mode: str) -> dict[str, Any]:
        if mode == "match":
            return {"content_digest": desired.get("content_digest") or provision.stable_digest(desired)}
        if mode == "interrupted":
            return {
                "content_digest": "sha256:interrupted",
                "managed_by": "contextforge-control-plane",
                "interrupted": True,
            }
        if mode == "stale":
            return {"content_digest": "sha256:stale", "managed_by": "contextforge-control-plane"}
        raise AssertionError(f"unknown artifact observation mode: {mode}")

    def unit_observation(self, plan: Mapping[str, Any], mode: str) -> dict[str, Any]:
        desired = plan["x_desired_artifacts"]["user_systemd_unit"]
        if mode == "active_match":
            return {
                "unit_name": desired["unit_name"],
                "scope": "user",
                "content_digest": desired["content_digest"],
                "status": "active",
                "managed_by": "contextforge-control-plane",
            }
        if mode == "stale_owned":
            return {
                "unit_name": desired["unit_name"],
                "scope": "user",
                "content_digest": "sha256:stale",
                "managed_by": "contextforge-control-plane",
            }
        if mode == "stale_unmanaged":
            return {
                "unit_name": desired["unit_name"],
                "scope": "user",
                "content_digest": "sha256:stale",
                "managed_by": "operator-local",
            }
        if mode == "system_scope":
            return {
                "unit_name": desired["unit_name"],
                "scope": "system",
                "content_digest": "sha256:stale",
                "managed_by": "contextforge-control-plane",
            }
        raise AssertionError(f"unknown unit observation mode: {mode}")

    def port_observations(self, mode: str) -> dict[str, dict[str, Any]]:
        key = str(self.fixture["port"])
        if mode == "already_owned":
            return {key: {"status": "occupied", "owner": self.fixture["service_binding"]}}
        if mode == "other_owner":
            return {key: {"status": "occupied", "owner": "other-contextforge-service"}}
        if mode == "available":
            return {key: {"status": "available"}}
        raise AssertionError(f"unknown port observation mode: {mode}")

    def readiness_observations(self, mode: str) -> dict[str, dict[str, str]]:
        if mode == "passed":
            return {"proof-health": {"status": "passed"}}
        if mode == "failed":
            return {"proof-health": {"status": "failed"}}
        if mode == "missing":
            return {}
        raise AssertionError(f"unknown readiness observation mode: {mode}")

    def registration_intent(self) -> dict[str, Any]:
        return binding.build_contextforge_registration_intent(
            plan_id=self.fixture["plan_id"],
            service_binding=self.fixture["service_binding"],
            contract_card=self.contract_card(),
            backend_manifest_ref=self.ref("backend-manifests/proof-project"),
            gateway_name="proof-project",
            gateway_url=f"http://127.0.0.1:{self.fixture['port']}/mcp",
            upstream_transport="streamable_http",
            consent_receipt_refs=self.consent_receipt_refs(),
            generated_at=self.fixture["resolved_at"],
        )

    def virtual_server_intent(self) -> dict[str, Any]:
        return binding.build_virtual_server_association_intent(
            plan_id=self.fixture["plan_id"],
            service_binding=self.fixture["service_binding"],
            contract_card=self.contract_card(),
            virtual_server_name="proof-project-codex",
            gateway_ref=self.ref("gateways/proof-project"),
            semantic_tool_policy=self.semantic_policy(),
            consent_receipt_refs=self.consent_receipt_refs(),
            generated_at=self.fixture["resolved_at"],
        )

    def client_binding_intent(
        self,
        *,
        policy: Mapping[str, Any] | None = None,
        conformance_result: Mapping[str, Any] | None = None,
        consent_classes: list[str] | None = None,
        readbacks_mode: str = "passed",
        trace_layers: list[str] | None = None,
        current_client_digest: str = "sha256:client-r1",
    ) -> dict[str, Any]:
        return binding.build_client_binding_intent(
            plan_id=self.fixture["plan_id"],
            project_root=self.fixture["project_root"],
            service_binding=self.fixture["service_binding"],
            target_client=self.fixture["target_client"],
            virtual_server_ref=self.ref("virtual-servers/proof-project-codex"),
            semantic_tool_policy=policy or self.semantic_policy(),
            conformance_result=conformance_result or self.conformance(),
            consent_receipt_refs=self.consent_receipt_refs(consent_classes),
            negative_check_readbacks=self.negative_checks(status=readbacks_mode),
            trace_refs=self.verification_trace_refs(layers=trace_layers),
            expected_gateway_digest="sha256:gateway-r1",
            current_gateway_digest="sha256:gateway-r1",
            expected_client_digest="sha256:client-r1",
            current_client_digest=current_client_digest,
            generated_at=self.fixture["resolved_at"],
        )

    def contract_card(self) -> dict[str, Any]:
        return {
            "service_family": "proof",
            "service_binding": self.fixture["service_binding"],
            "instantiation_class": "instance_per_project",
            "x_mutates_shared_canonical_identity": False,
        }

    def semantic_policy(self, *, status: str = "compiled") -> dict[str, Any]:
        blocked = status != "compiled"
        return {
            "policy_id": "proof-policy",
            "service_binding": self.fixture["service_binding"],
            "compiled_tool_ids": ["cf-tool-proof-read"],
            "negative_checks": self.negative_checks(status="passed"),
            "last_compiled_at": self.fixture["resolved_at"],
            "x_status": status,
            "x_target_client": self.fixture["target_client"],
            "x_blockers": [{"type": "missing_risk_metadata", "message": "blocked"}] if blocked else [],
            "x_stale_policy_inputs": {"stale": False},
        }

    def conformance(self, *, status: str = "passing_conformance") -> dict[str, Any]:
        passing = status == "passing_conformance"
        return {
            "pack_id": "codex/v1",
            "client_name": self.fixture["target_client"],
            "status": status,
            "decision": "allow_target_client_proof" if passing else "block_target_client_proof",
            "project_root": self.fixture["project_root"],
            "service_binding": self.fixture["service_binding"],
            "blockers": [] if passing else [{"name": "list_tools_proof", "message": "missing"}],
            "generated_at": self.fixture["resolved_at"],
            "redaction_status": "passed",
        }

    def negative_checks(self, *, status: str) -> list[dict[str, Any]]:
        if status == "missing":
            return []
        check_status = "passed" if status == "passed" else "failed"
        return [
            {
                "check": "excluded_tool_absent",
                "layer": "contextforge_virtual_server",
                "probe": "readback_server_tools",
                "service_binding": self.fixture["service_binding"],
                "tool_id": "cf-tool-proof-write",
                "expected": "absent",
                "status": check_status,
            },
            {
                "check": "excluded_tool_absent",
                "layer": "target_client",
                "probe": "list_tools_and_call_tool",
                "service_binding": self.fixture["service_binding"],
                "target_client": self.fixture["target_client"],
                "tool_id": "cf-tool-proof-write",
                "expected": "absent",
                "status": check_status,
            },
        ]

    def consent_receipt_refs(self, classes: list[str] | None = None) -> list[dict[str, Any]]:
        classes = classes or ["service_provision", "project_local_config_write"]
        return [
            {
                **self.ref(f"receipts/{consent_class}"),
                "x_consent_class": consent_class,
            }
            for consent_class in classes
        ]

    def verification_trace_refs(
        self,
        *,
        layers: list[str] | None = None,
        include_backend: bool = False,
        schema_extensions: bool = False,
    ) -> list[dict[str, Any]]:
        selected = layers or ["contextforge_gateway", "virtual_server", "tool_policy", "target_client", "redaction"]
        if include_backend:
            selected = ["backend", *selected]
        refs = []
        for layer in selected:
            metadata = {
                "layer": layer,
                "target_client": self.fixture["target_client"] if layer == "target_client" else None,
                "result": "passed",
            }
            if schema_extensions:
                metadata = {f"x_{key}": value for key, value in metadata.items()}
            refs.append({**self.ref(f"traces/{layer}"), **metadata})
        return refs

    def refs(self, fixture_key: str) -> list[dict[str, Any]]:
        return [self.ref(name) for name in self.fixture["fixture_refs"][fixture_key]]

    def ref(self, name: str) -> dict[str, Any]:
        return contracts.artifact_ref(
            f"contextforge://control-plane/{name}",
            {"name": name, "run_id": self.fixture["run_id"]},
            resolved_at=self.fixture["resolved_at"],
        )

    def generated_service_state(self, plan: Mapping[str, Any], client_binding: Mapping[str, Any]) -> dict[str, Any]:
        state = {
            "service_binding": self.fixture["service_binding"],
            "project": {
                "root": self.fixture["project_root"],
                "root_hash": project_state.project_root_hash(self.fixture["project_root"]),
            },
            "provision_status": "verified",
            "lifecycle": {
                "current_state": "backend_ready",
                "previous_state": "unit_enabled",
                "allowed_next_states": ["registered", "verified", "failed"],
                "transition_journal_ref": self.ref("journals/proof-backend-ready"),
                "evidence_refs": copy.deepcopy(client_binding["required_trace_refs"]),
                "recovery_outcome": "resume",
            },
            "consent_receipt_refs": copy.deepcopy(plan["consent_receipt_refs"]),
            "verification_trace_refs": copy.deepcopy(plan["produced_artifact_refs"]),
            "redaction_status": "redacted",
        }
        contracts.validate_redacted(state, require_status=True)
        return state

    def blockers_by_type(self, result: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
        return {str(blocker["type"]): dict(blocker) for blocker in result.get("blockers", [])}


if __name__ == "__main__":
    unittest.main()
