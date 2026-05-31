from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import control_plane_authorization as auth
import control_plane_contracts as contracts
import control_plane_project_state as project_state
import control_plane_service_provision as provision


PROJECT_ROOT = "/home/dgk/workspace/context-portal"
STAMP = "2026-05-30T21:00:00Z"


def artifact_ref(name: str, payload: dict[str, object] | None = None) -> dict[str, object]:
    body = payload or {"name": name}
    return contracts.artifact_ref(name, body, resolved_at=STAMP)


def base_state() -> dict[str, object]:
    return {
        "meta": {"revision": 7},
        "project": {"root": PROJECT_ROOT, "root_hash": project_state.project_root_hash(PROJECT_ROOT), "name": "context-portal"},
        "status": "uninitialized",
        "decisions": {},
        "services": {},
        "client_trust": {},
        "open_items": [],
    }


def planner_plan() -> dict[str, object]:
    state = base_state()
    return {
        "schema_version": 1,
        "surface": "propose_project_init",
        "planner": "control_plane_project_planner",
        "project": {"root": PROJECT_ROOT, "root_hash": project_state.project_root_hash(PROJECT_ROOT), "name": "context-portal"},
        "plan_id": "project-init-fixture",
        "status": "planned_non_mutating",
        "mutation_allowed": False,
        "required_consent_classes": ["service_provision", "secret_placeholder_change"],
        "forbidden_project_init_consent_classes": sorted(auth.FORBIDDEN_GENERIC_PROJECT_INIT_CLASSES),
        "stale_plan_inputs": {
            "project_root": PROJECT_ROOT,
            "project_root_hash": project_state.project_root_hash(PROJECT_ROOT),
            "base_project_state": {
                "present": True,
                "revision": state["meta"]["revision"],
                "status": state["status"],
                "digest": auth.stable_digest(state),
            },
            "catalog": {"revision_or_etag": "catalog-r1", "digest": auth.stable_digest({"revision": "catalog-r1"})},
            "selected_service_descriptors": [
                {"descriptor_id": "proof", "artifact_digest": auth.stable_digest({"service_family": "proof"})}
            ],
            "target_client_digests": {"codex": "sha256:client-digest"},
            "trust_state_digest": "sha256:trust-digest",
            "drift_findings": [],
        },
        "plan_steps": [
            {
                "step_id": "plan-proof",
                "operation": "plan_project_scoped_service_provision",
                "service_binding": "proof:project",
                "required_consent_classes": ["service_provision"],
                "stale_plan_inputs": {},
            }
        ],
        "service_management_handoffs": [],
        "open_items": [],
        "artifact_drafts": {"contract_cards": [], "capability_capsules": []},
    }


def receipt_for(plan: dict[str, object]) -> dict[str, object]:
    return auth.create_consent_receipt(
        plan=plan,
        consent_class="service_provision",
        actor="user",
        source_client="codex",
        source_client_auth_strength="shared_token",
        approval_event_ref="transcript:fixture",
        approval_evidence="redacted approval summary",
        expires_at="2026-05-31T21:00:00Z",
        approved_at=STAMP,
        scope={
            "project_root": PROJECT_ROOT,
            "service_binding": "proof:project",
            "target_clients": ["codex"],
            "persistent_target": "systemd",
        },
    )


def owned_write_set() -> list[str]:
    home = provision.backend_home_path(PROJECT_ROOT, "proof:project")
    return [
        home,
        f"{home}/.env.placeholder",
        f"{home}/backend-manifest.json",
        "user-systemd:contextforge-proof-project.service",
    ]


def provision_plan() -> dict[str, object]:
    return provision.build_service_provision_plan(
        project_root=PROJECT_ROOT,
        service_binding="proof:project",
        plan_id="provision-proof-project",
        backend_command=["uv", "run", "proof-mcp"],
        owned_write_set=owned_write_set(),
        stale_input_refs=[artifact_ref("service-bindings/proof")],
        consent_receipt_refs=[artifact_ref("receipts/proof")],
        verification_trace_refs=[artifact_ref("traces/proof-backend")],
        ports=[{"port": 48765, "bind": "127.0.0.1", "owner": "proof:project"}],
        readiness_probes=[{"probe_id": "proof-health", "probe_type": "http", "target": "http://127.0.0.1:48765/health"}],
        required_env=["PROOF_ACCESS_HANDLE"],
        optional_env=["PROOF_LOG_LEVEL"],
        policy_refs=[artifact_ref("tool-policies/proof")],
        conformance_refs=[artifact_ref("client-adapters/codex")],
        upstream={"package": "proof-mcp", "api_token": "plain-test-value"},
    )


class ControlPlaneServiceProvisionTests(unittest.TestCase):
    def test_backend_manifest_plan_env_placeholder_and_unit_spec_are_generic_and_valid(self) -> None:
        plan = provision_plan()

        contracts.validate_artifact("service_provision_plan", plan)
        self.assertEqual("proof:project", plan["service_binding"])
        self.assertEqual("idempotent", plan["idempotency_mode"])
        self.assertEqual("forward_repair", plan["compensation_repair_mode"])
        self.assertIn("no_catalog_promotion", str(plan["service_provision_steps"]))
        self.assertNotIn(".project/context_forge_state.json", plan["write_set"])
        self.assertIn("server-instances/proof-project", plan["x_backend_home"])
        desired = plan["x_desired_artifacts"]
        self.assertEqual("contextforge-proof-project.service", desired["user_systemd_unit"]["unit_name"])
        self.assertEqual("user", desired["user_systemd_unit"]["unit_scope"])
        self.assertFalse(desired["user_systemd_unit"]["systemd_mutation_performed"])
        self.assertEqual(["PROOF_ACCESS_HANDLE"], desired["env_placeholder"]["placeholder_keys"]["required"])
        self.assertEqual("proof:project", desired["backend_manifest"]["content"]["service_binding"])
        self.assertEqual("<redacted>", desired["backend_manifest"]["content"]["upstream"]["api_token"])
        self.assertEqual(48765, desired["ports"][0]["port"])
        self.assertEqual("proof-health", desired["readiness_probes"][0]["probe_id"])

    def test_env_placeholder_policy_rejects_values_and_keeps_standalone_content_placeholder_only(self) -> None:
        placeholder = provision.build_env_placeholder(required_env=["PROOF_ACCESS_HANDLE"], optional_env=["PROOF_LOG_LEVEL"])

        self.assertIn("PROOF_ACCESS_HANDLE=${PROOF_ACCESS_HANDLE}", placeholder["content"])
        self.assertFalse(placeholder["secret_values_included"])
        with self.assertRaises(provision.ServiceProvisionInputError):
            provision.build_env_placeholder(required_env=["bad-key"])
        with self.assertRaises(provision.ServiceProvisionInputError):
            provision.build_env_placeholder(required_env=["PROOF_ACCESS_HANDLE"], optional_env=["PROOF_ACCESS_HANDLE"])

    def test_consent_stale_input_trace_refs_and_owned_write_set_are_required(self) -> None:
        kwargs = {
            "project_root": PROJECT_ROOT,
            "service_binding": "proof:project",
            "plan_id": "provision-proof-project",
            "backend_command": ["uv", "run", "proof-mcp"],
            "owned_write_set": owned_write_set(),
            "stale_input_refs": [artifact_ref("service-bindings/proof")],
            "consent_receipt_refs": [artifact_ref("receipts/proof")],
            "verification_trace_refs": [artifact_ref("traces/proof")],
        }
        for key in ("owned_write_set", "stale_input_refs", "consent_receipt_refs", "verification_trace_refs"):
            bad = copy.deepcopy(kwargs)
            bad[key] = []
            with self.subTest(key=key):
                with self.assertRaises(provision.ServiceProvisionInputError):
                    provision.build_service_provision_plan(**bad)

        bad_write_set = copy.deepcopy(kwargs)
        bad_write_set["owned_write_set"] = [".project/context_forge_state.json"]
        with self.assertRaises(provision.ServiceProvisionInputError):
            provision.build_service_provision_plan(**bad_write_set)

    def test_apply_prerequisites_require_fresh_approval_for_stale_or_bad_receipts(self) -> None:
        plan = provision_plan()

        stale = provision.validate_apply_prerequisites(
            plan,
            project_root=PROJECT_ROOT,
            service_binding="proof:project",
            owned_write_set=owned_write_set(),
            stale_inputs_valid=False,
            consent_receipts_valid=True,
            verification_traces_valid=True,
        )
        bad_receipt = provision.validate_apply_prerequisites(
            plan,
            project_root=PROJECT_ROOT,
            service_binding="proof:project",
            owned_write_set=owned_write_set(),
            stale_inputs_valid=True,
            consent_receipts_valid=False,
            verification_traces_valid=True,
        )

        self.assertEqual("fresh_approval_required", stale["outcome"])
        self.assertEqual("fresh_approval_required", bad_receipt["outcome"])

    def test_authorization_wrapper_binds_service_provision_receipt_scope(self) -> None:
        plan = planner_plan()
        receipt = receipt_for(plan)

        decision = provision.authorize_service_provision(
            plan=plan,
            actor="user",
            workflow_identity="project_init",
            source_client="codex",
            source_client_auth_strength="shared_token",
            target_clients=["codex"],
            project_root=PROJECT_ROOT,
            current_state=base_state(),
            current_target_client_digests={"codex": "sha256:client-digest"},
            current_trust_digest="sha256:trust-digest",
            current_catalog_revision_or_etag="catalog-r1",
            service_binding="proof:project",
            receipts=[receipt],
            now=STAMP,
        )

        self.assertEqual("allow", decision["decision"])
        self.assertTrue(decision["allowed"])

    def test_idempotency_classifies_already_applied_without_mutation(self) -> None:
        plan = provision_plan()
        desired = plan["x_desired_artifacts"]
        result = provision.classify_apply_outcomes(
            plan,
            current_artifacts={
                "backend_home": {"content_digest": provision.stable_digest(desired["backend_home"])},
                "env_placeholder": {"content_digest": desired["env_placeholder"]["content_digest"]},
                "backend_manifest": {"content_digest": desired["backend_manifest"]["content_digest"]},
            },
            unit_observation={
                "unit_name": desired["user_systemd_unit"]["unit_name"],
                "scope": "user",
                "content_digest": desired["user_systemd_unit"]["content_digest"],
                "status": "active",
            },
            port_observations={"48765": {"status": "occupied", "owner": "proof:project"}},
            readiness_observations={"proof-health": {"status": "passed"}},
        )

        self.assertEqual("already_applied", result["aggregate_outcome"])
        self.assertEqual("already_applied", result["component_outcomes"]["env_placeholder"]["outcome"])
        self.assertEqual("already_applied", result["component_outcomes"]["backend_manifest"]["outcome"])
        self.assertEqual("already_applied", result["component_outcomes"]["user_systemd_unit"]["outcome"])
        self.assertEqual("already_applied", result["component_outcomes"]["ports"]["outcome"])
        self.assertFalse(result["mutation_performed"])

    def test_port_conflict_stale_unit_and_readiness_failure_are_typed(self) -> None:
        plan = provision_plan()
        desired = plan["x_desired_artifacts"]
        result = provision.classify_apply_outcomes(
            plan,
            current_artifacts={
                "backend_home": {"content_digest": provision.stable_digest(desired["backend_home"])},
                "env_placeholder": {"content_digest": desired["env_placeholder"]["content_digest"]},
                "backend_manifest": {"content_digest": desired["backend_manifest"]["content_digest"]},
            },
            unit_observation={
                "unit_name": desired["user_systemd_unit"]["unit_name"],
                "scope": "user",
                "content_digest": "sha256:stale",
                "managed_by": "contextforge-control-plane",
            },
            port_observations={"48765": {"status": "occupied", "owner": "other-service"}},
            readiness_observations={"proof-health": {"status": "failed"}},
        )

        self.assertEqual("fresh_approval_required", result["aggregate_outcome"])
        self.assertEqual("forward_repair", result["component_outcomes"]["user_systemd_unit"]["outcome"])
        self.assertEqual("fresh_approval_required", result["component_outcomes"]["ports"]["outcome"])
        self.assertEqual("forward_repair", result["component_outcomes"]["readiness"]["outcome"])

    def test_catalog_promotion_separation_rejects_forbidden_operation_classes(self) -> None:
        with self.assertRaises(provision.ServiceProvisionInputError):
            provision._step(  # type: ignore[attr-defined]
                "promote",
                "contextforge",
                "catalog_promotion",
                "planned-to-registered",
                ["not allowed"],
                [],
                [],
                [],
            )

        plan = provision_plan()
        self.assertIn("catalog_promotion", plan["x_forbidden_effects"])
        for step in plan["service_provision_steps"]:
            self.assertNotEqual("catalog_promotion", step["operation_class"])


if __name__ == "__main__":
    unittest.main()
