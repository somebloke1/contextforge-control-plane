from __future__ import annotations

import copy
import json
import re
import sys
import unittest
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import control_plane_authorization as auth
import control_plane_contracts as contracts
import control_plane_project_state as project_state
import control_plane_verification as verification


FIXTURE_PATH = REPO_ROOT / "tests/fixtures/control_plane_apply_journal_cases.json"
SECRET_LIKE_RE = re.compile(
    r"(Bearer\s+[A-Za-z0-9._~+/=-]{8,}|"
    r"(?:sk|pk|ghp|gho|github_pat|xox[baprs]|ya29)[_-][A-Za-z0-9._-]{8,}|"
    r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}|"
    r"(?i:(api[_-]?key|auth[_-]?token|password|secret)\s*=\s*[^\\s'\"<>]+))"
)


class ControlPlaneApplyJournalFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with FIXTURE_PATH.open("r", encoding="utf-8") as handle:
            cls.fixture = json.load(handle)
        cls.cases = {case["name"]: case for case in cls.fixture["cases"]}
        cls.project_root = cls.fixture["project_root"]

    def base_state(self, *, revision: int | None = None, status: str = "uninitialized") -> dict[str, Any]:
        revision = self.fixture["base_revision"] if revision is None else revision
        return {
            "meta": {"revision": revision},
            "project": {
                "root": self.project_root,
                "root_hash": project_state.project_root_hash(self.project_root),
                "name": "cf-controlplane",
            },
            "status": status,
            "decisions": {},
            "services": {},
            "client_trust": {},
            "open_items": [],
        }

    def base_plan(self) -> dict[str, Any]:
        state = self.base_state()
        descriptor_digest = auth.stable_digest({"service_family": "context7", "scope": "shared"})
        return {
            "schema_version": 1,
            "surface": "propose_project_init",
            "planner": "control_plane_project_planner",
            "project": {
                "root": self.project_root,
                "root_hash": project_state.project_root_hash(self.project_root),
                "name": "cf-controlplane",
            },
            "plan_id": self.fixture["plan_id"],
            "status": "planned_non_mutating",
            "mutation_allowed": False,
            "required_consent_classes": [
                "project_state_write",
                "project_local_config_write",
                "service_provision",
            ],
            "forbidden_project_init_consent_classes": sorted(auth.FORBIDDEN_GENERIC_PROJECT_INIT_CLASSES),
            "stale_plan_inputs": {
                "project_root": self.project_root,
                "project_root_hash": project_state.project_root_hash(self.project_root),
                "base_project_state": {
                    "present": True,
                    "revision": state["meta"]["revision"],
                    "status": state["status"],
                    "digest": auth.stable_digest(state),
                },
                "catalog": {
                    "revision_or_etag": self.fixture["catalog_revision_or_etag"],
                    "digest": auth.stable_digest({"revision": self.fixture["catalog_revision_or_etag"]}),
                },
                "selected_service_descriptors": [
                    {
                        "descriptor_id": "context7",
                        "artifact_digest": descriptor_digest,
                        "service_family": "context7",
                    }
                ],
                "target_client_digests": copy.deepcopy(self.fixture["target_client_digests"]),
                "trust_state_digest": self.fixture["trust_state_digest"],
                "drift_findings": [],
            },
            "plan_steps": [
                {
                    "step_id": "provision-context7",
                    "operation": "plan_shared_service_registration",
                    "service_binding": self.fixture["service_binding"],
                    "required_consent_classes": ["service_provision"],
                    "stale_plan_inputs": {},
                }
            ],
            "service_management_handoffs": [],
            "open_items": [],
            "artifact_drafts": {"contract_cards": [], "capability_capsules": []},
        }

    def receipt_for(
        self,
        plan: dict[str, Any],
        consent_class: str,
        *,
        service_binding: str | None = None,
        target_clients: list[str] | None = None,
        persistent_target: str | None = None,
        replay_policy: str = "same_plan_resume",
        auth_strength: str | None = None,
    ) -> dict[str, Any]:
        receipt = auth.create_consent_receipt(
            plan=plan,
            consent_class=consent_class,
            actor=self.fixture["actor"],
            source_client=self.fixture["source_client"],
            source_client_auth_strength=auth_strength or self.fixture["source_client_auth_strength"],
            approval_event_ref="transcript:fixture-approval",
            approval_evidence="redacted approval summary",
            expires_at=self.fixture["expires_at"],
            approved_at=self.fixture["resolved_at"],
            replay_policy=replay_policy,
            scope={
                "project_root": self.project_root,
                "service_binding": service_binding,
                "target_clients": target_clients or self.fixture["target_clients"],
                "persistent_target": persistent_target,
            },
        )
        contracts.validate_artifact("consent_receipt", receipt)
        return receipt

    def authorize(self, plan: dict[str, Any], receipt: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
        return auth.authorize_operation(
            plan=plan,
            operation_class=case["operation_class"],
            actor=self.fixture["actor"],
            workflow_identity=self.fixture["workflow_identity"],
            source_client=self.fixture["source_client"],
            source_client_auth_strength=self.fixture["source_client_auth_strength"],
            target_clients=self.fixture["target_clients"],
            project_root=self.project_root,
            current_state=self.base_state(revision=case.get("current_state_revision")),
            current_target_client_digests=case.get("current_target_client_digests", self.fixture["target_client_digests"]),
            current_trust_digest=self.fixture["trust_state_digest"],
            current_catalog_revision_or_etag=self.fixture["catalog_revision_or_etag"],
            service_binding=self.fixture["service_binding"],
            persistent_target=self.fixture["persistent_target"],
            receipts=[receipt],
            replay_intent=case.get("replay_intent", "initial_apply"),
            approval_workflow="project_init",
            allowed_callers=[self.fixture["actor"]],
            allowed_workflows=[self.fixture["workflow_identity"]],
            now=self.fixture["resolved_at"],
        )

    def artifact_ref(self, fixture_key: str) -> dict[str, Any]:
        ref_fixture = self.fixture[fixture_key]
        return contracts.artifact_ref(
            ref_fixture["ref"],
            ref_fixture["payload"],
            resolved_at=self.fixture["resolved_at"],
        )

    def journal_entry(
        self,
        *,
        plan: dict[str, Any],
        receipt: dict[str, Any],
        journal: dict[str, Any],
        verification_trace_refs: list[dict[str, Any]] | None = None,
        result_hashes: list[str] | None = None,
    ) -> dict[str, Any]:
        entry = auth.build_plan_journal_entry(
            plan=plan,
            run_id=self.fixture["run_id"],
            step_id=journal["step_id"],
            operation_class="service_provision",
            actor=self.fixture["actor"],
            source_client=self.fixture["source_client"],
            base_revision=self.fixture["base_revision"],
            observed_revision=self.fixture["base_revision"],
            required_receipts=[receipt],
            observed_receipts=[receipt],
            service_contract_refs=[self.artifact_ref("service_contract_ref")],
            service_management_handoff_refs=[self.artifact_ref("service_management_handoff_ref")],
            redacted_output_summary=journal["redacted_output_summary"],
            status=journal["status"],
            replay_policy=journal["replay_policy"],
            recovery_outcome=journal["recovery_outcome"],
            verification_trace_refs=verification_trace_refs or [],
            result_hashes=result_hashes or [],
            created_at=self.fixture["resolved_at"],
        )
        self.assert_journal_audit_fields(entry, expect_trace_refs=bool(verification_trace_refs))
        return entry

    def assert_journal_audit_fields(self, entry: dict[str, Any], *, expect_trace_refs: bool) -> None:
        self.assertEqual("approved_plan_step", entry["journal_type"])
        self.assertEqual("redacted", entry["redaction_status"])
        self.assertTrue(entry["required_consent_receipts"])
        self.assertTrue(entry["observed_consent_receipts"])
        self.assertTrue(entry["service_contract_refs"])
        self.assertTrue(entry["service_management_handoff_refs"])
        self.assertIn(entry["status"], {"resumed", "failed", "blocked"})
        self.assertEqual("same_plan_resume", entry["replay_policy"])
        self.assertTrue(entry["recovery_outcome"])
        if expect_trace_refs:
            self.assertTrue(entry["verification_trace_refs"])
            self.assertTrue(entry["result_hashes"])
        contracts.validate_redacted(entry, require_status=True)
        self.assert_no_secret_like_fields(entry)

    def assert_no_secret_like_fields(self, data: Any) -> None:
        encoded = json.dumps(data, sort_keys=True)
        self.assertIsNone(SECRET_LIKE_RE.search(encoded), encoded)

    def test_fixture_names_cover_w5_c_required_cases(self) -> None:
        self.assertEqual(
            {
                "stale_plan_replay_blocks",
                "receipt_scope_change_blocks",
                "interrupted_run_resume_records_recovery",
                "failed_trace_transition_blocks_and_journals_refs",
                "owned_config_idempotency_boundaries",
                "generic_project_init_forbidden_classes_block",
            },
            set(self.cases),
        )

    def test_stale_plan_replay_blocks_and_journal_records_block(self) -> None:
        case = self.cases["stale_plan_replay_blocks"]
        plan = self.base_plan()
        receipt = self.receipt_for(
            plan,
            case["operation_class"],
            service_binding=self.fixture["service_binding"],
            persistent_target=self.fixture["persistent_target"],
        )

        decision = self.authorize(plan, receipt, case)

        self.assertEqual(case["expected_decision"], decision["decision"])
        reasons = " ".join(decision["reasons"])
        for fragment in case["expected_reason_fragments"]:
            self.assertIn(fragment, reasons)

    def test_receipt_scope_change_blocks_apply_replay(self) -> None:
        case = self.cases["receipt_scope_change_blocks"]
        plan = self.base_plan()
        for variant in case["scope_variants"]:
            with self.subTest(variant=variant["name"]):
                receipt = self.receipt_for(
                    plan,
                    case["operation_class"],
                    service_binding=variant["receipt_service_binding"],
                    target_clients=variant["receipt_target_clients"],
                    persistent_target=variant["receipt_persistent_target"],
                )
                check = auth.validate_consent_receipt(
                    receipt,
                    plan=plan,
                    operation_class=case["operation_class"],
                    actor=self.fixture["actor"],
                    source_client=self.fixture["source_client"],
                    source_client_auth_strength=self.fixture["source_client_auth_strength"],
                    project_root=self.project_root,
                    service_binding=self.fixture["service_binding"],
                    target_clients=self.fixture["target_clients"],
                    persistent_target=self.fixture["persistent_target"],
                    replay_intent="resume",
                    now=self.fixture["resolved_at"],
                )

                self.assertEqual(case["expected_decision"], check["decision"])
                self.assertIn(variant["expected_reason_fragment"], " ".join(check["reasons"]))

    def test_interrupted_run_resume_allows_and_records_recovery_journal(self) -> None:
        case = self.cases["interrupted_run_resume_records_recovery"]
        plan = self.base_plan()
        receipt = self.receipt_for(
            plan,
            case["operation_class"],
            service_binding=self.fixture["service_binding"],
            persistent_target=self.fixture["persistent_target"],
        )

        decision = self.authorize(plan, receipt, case)
        entry = self.journal_entry(plan=plan, receipt=receipt, journal=case["journal"])

        self.assertEqual(case["expected_decision"], decision["decision"])
        self.assertTrue(decision["allowed"])
        self.assertEqual("resumed", entry["status"])
        self.assertEqual("resume", entry["recovery_outcome"])

    def test_failed_or_missing_trace_blocks_transition_and_failed_trace_is_journaled(self) -> None:
        case = self.cases["failed_trace_transition_blocks_and_journals_refs"]
        plan = self.base_plan()
        receipt = self.receipt_for(
            plan,
            case["operation_class"],
            service_binding=self.fixture["service_binding"],
            persistent_target=self.fixture["persistent_target"],
        )
        trace_input = case["trace"]
        trace = verification.build_verification_trace(
            trace_id=trace_input["trace_id"],
            plan_id=plan["plan_id"],
            step_id=trace_input["step_id"],
            service_binding=self.fixture["service_binding"],
            layer=trace_input["layer"],
            probe_id=f"probe-{trace_input['layer']}",
            probe_type="readback",
            subject=f"{self.fixture['service_binding']}:{trace_input['layer']}",
            status=trace_input["status"],
            observations={"summary": "gateway readback failed", "http_status": 503},
            target_client=self.fixture["source_client"],
            failure_classification=trace_input["failure_classification"],
            generated_at=self.fixture["resolved_at"],
        )
        contracts.validate_artifact("verification_trace", trace)
        trace_ref = verification.build_verification_trace_ref(trace, resolved_at=self.fixture["resolved_at"])

        failed_decision = verification.validate_lifecycle_transition(
            plan_id=plan["plan_id"],
            step_id=trace_input["step_id"],
            service_binding=self.fixture["service_binding"],
            target_state=trace_input["target_state"],
            required_layers=trace_input["required_layers"],
            trace_refs=[trace_ref],
            trace_artifacts={trace_ref["ref"]: trace},
            target_client=self.fixture["source_client"],
        )
        missing = case["missing_trace"]
        missing_decision = verification.validate_lifecycle_transition(
            plan_id=plan["plan_id"],
            step_id=missing["step_id"],
            service_binding=self.fixture["service_binding"],
            target_state=missing["target_state"],
            required_layers=missing["required_layers"],
            trace_refs=[],
            trace_artifacts={},
            target_client=self.fixture["source_client"],
        )
        entry = self.journal_entry(
            plan=plan,
            receipt=receipt,
            journal=case["journal"],
            verification_trace_refs=[trace_ref],
            result_hashes=[trace["result_hash"]],
        )

        self.assertEqual(case["expected_decision"], failed_decision["decision"])
        self.assertEqual("failed", failed_decision["matrix"]["layers"]["contextforge_gateway"]["status"])
        self.assertEqual(case["expected_decision"], missing_decision["decision"])
        self.assertEqual("missing_trace_ref", missing_decision["reason"])
        self.assertEqual([trace_ref], entry["verification_trace_refs"])
        self.assertEqual([trace["result_hash"]], entry["result_hashes"])

    def test_owned_config_idempotency_boundaries(self) -> None:
        case = self.cases["owned_config_idempotency_boundaries"]
        plan = self.base_plan()
        receipt = self.receipt_for(
            plan,
            case["operation_class"],
            service_binding=None,
            persistent_target="file",
        )
        owned_block = copy.deepcopy(case["owned_block"])
        owned_block["content"] = copy.deepcopy(case["desired_content"])

        decisions = {
            "owned_same_content": auth.project_local_apply_preflight(
                operation_class=case["operation_class"],
                project_root=self.project_root,
                target_path=case["target_path"],
                desired_content=case["desired_content"],
                current_block=owned_block,
                receipt=receipt,
                plan=plan,
                replay_intent="resume",
                now=self.fixture["resolved_at"],
            ),
            "owned_different_content": auth.project_local_apply_preflight(
                operation_class=case["operation_class"],
                project_root=self.project_root,
                target_path=case["target_path"],
                desired_content=case["changed_content"],
                current_block=owned_block,
                receipt=receipt,
                plan=plan,
                replay_intent="initial_apply",
                now=self.fixture["resolved_at"],
            ),
            "unmanaged_same_name": auth.project_local_apply_preflight(
                operation_class=case["operation_class"],
                project_root=self.project_root,
                target_path=case["target_path"],
                desired_content=case["desired_content"],
                current_block=case["unmanaged_block"],
                receipt=receipt,
                plan=plan,
                replay_intent="initial_apply",
                now=self.fixture["resolved_at"],
            ),
        }

        for name, expected in case["expected"].items():
            with self.subTest(name=name):
                self.assertEqual(expected["decision"], decisions[name]["decision"])
                self.assertEqual(expected["action"], decisions[name]["action"])

    def test_generic_project_init_forbidden_classes_block(self) -> None:
        case = self.cases["generic_project_init_forbidden_classes_block"]
        plan = self.base_plan()
        for operation_class in case["operation_classes"]:
            with self.subTest(operation_class=operation_class):
                decision = auth.authorize_operation(
                    plan=plan,
                    operation_class=operation_class,
                    actor=self.fixture["actor"],
                    workflow_identity=self.fixture["workflow_identity"],
                    source_client=self.fixture["source_client"],
                    source_client_auth_strength="per_client_token",
                    target_clients=self.fixture["target_clients"],
                    project_root=self.project_root,
                    current_state=self.base_state(),
                    current_target_client_digests=self.fixture["target_client_digests"],
                    current_trust_digest=self.fixture["trust_state_digest"],
                    current_catalog_revision_or_etag=self.fixture["catalog_revision_or_etag"],
                    receipts=[],
                    approval_workflow="project_init",
                    now=self.fixture["resolved_at"],
                )

                self.assertEqual(case["expected_decision"], decision["decision"])
                self.assertIn(case["expected_reason_fragment"], " ".join(decision["reasons"]))

    def test_fixture_inputs_are_not_mutated_and_state_file_is_not_changed(self) -> None:
        state_path = project_state.project_state_path(self.project_root)
        existed_before = state_path.exists()
        fixture_before = copy.deepcopy(self.fixture)

        for name in self.cases:
            with self.subTest(case=name):
                copy.deepcopy(self.cases[name])

        self.assertEqual(fixture_before, self.fixture)
        self.assertEqual(existed_before, state_path.exists())

    def test_fixture_and_generated_audit_outputs_contain_no_secret_shaped_literals(self) -> None:
        self.assert_no_secret_like_fields(self.fixture)
        plan = self.base_plan()
        receipt = self.receipt_for(
            plan,
            "service_provision",
            service_binding=self.fixture["service_binding"],
            persistent_target=self.fixture["persistent_target"],
        )
        entry = self.journal_entry(
            plan=plan,
            receipt=receipt,
            journal=self.cases["interrupted_run_resume_records_recovery"]["journal"],
        )
        self.assert_no_secret_like_fields(receipt)
        self.assert_no_secret_like_fields(entry)


if __name__ == "__main__":
    unittest.main()
