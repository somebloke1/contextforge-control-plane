from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import control_plane_authorization as authorization
import control_plane_project_state as project_state
import control_plane_trust_broker as broker


FIXTURE_PATH = REPO_ROOT / "tests/fixtures/control_plane_trust_broker_cases.json"
PROJECT_ROOT = "/home/dgk/workspace/legacy-controlplane-archive"
STAMP = "2026-05-30T22:30:00Z"
FUTURE = "2026-05-31T22:30:00Z"
PAST = "2026-05-29T22:30:00Z"
SECRET_VALUE = "Bearer " + ("A" * 24)


def base_plan() -> dict[str, Any]:
    state = {
        "meta": {"revision": 1},
        "project": {"root": PROJECT_ROOT, "root_hash": project_state.project_root_hash(PROJECT_ROOT), "name": "cf-controlplane"},
        "status": "uninitialized",
        "decisions": {},
        "services": {},
        "client_trust": {},
        "open_items": [],
    }
    return {
        "schema_version": 1,
        "surface": "codex_trust_broker",
        "planner": "control_plane_trust_broker",
        "project": {"root": PROJECT_ROOT, "root_hash": project_state.project_root_hash(PROJECT_ROOT), "name": "cf-controlplane"},
        "plan_id": "trust-plan-fixture",
        "status": "trust_approval_requested",
        "mutation_allowed": False,
        "required_consent_classes": [broker.TRUST_CONSENT_CLASS],
        "forbidden_project_init_consent_classes": sorted(authorization.FORBIDDEN_GENERIC_PROJECT_INIT_CLASSES),
        "stale_plan_inputs": {
            "project_root": PROJECT_ROOT,
            "project_root_hash": project_state.project_root_hash(PROJECT_ROOT),
            "base_project_state": {
                "present": True,
                "revision": state["meta"]["revision"],
                "status": state["status"],
                "digest": authorization.stable_digest(state),
            },
            "target_client_digests": {"codex": "sha256:client-digest"},
            "trust_state_digest": "sha256:trust-digest-before-approval",
            "catalog": {"revision_or_etag": "catalog-r1", "digest": "sha256:catalog"},
            "selected_service_descriptors": [],
            "drift_findings": [],
        },
        "plan_steps": [],
        "open_items": [],
    }


def approval_record(**overrides: Any) -> dict[str, Any]:
    receipt = overrides.pop("consent_receipt", None)
    if receipt is None:
        receipt = broker.create_trust_consent_receipt(
            plan=base_plan(),
            project_root=PROJECT_ROOT,
            client="codex",
            trust_surface=broker.DEFAULT_TRUST_SURFACE,
            actor="user",
            approval_event_ref="transcript:trust-approval",
            approval_evidence={"summary": "operator approved Codex project-root trust"},
            approved_at=STAMP,
            expires_at=FUTURE,
        )
    params = {
        "project_root": PROJECT_ROOT,
        "client": "codex",
        "trust_surface": broker.DEFAULT_TRUST_SURFACE,
        "actor": "user",
        "approval_evidence": {"summary": "operator approved Codex project-root trust"},
        "approved_at": STAMP,
        "expires_at": FUTURE,
        "consent_receipt": receipt,
        "approval_event_ref": "transcript:trust-approval",
    }
    params.update(overrides)
    return broker.build_trust_approval_record(**params)


class ControlPlaneTrustBrokerTests(unittest.TestCase):
    def test_fixture_cases_report_trust_state_and_open_items_without_mutation(self) -> None:
        with FIXTURE_PATH.open("r", encoding="utf-8") as handle:
            fixture = json.load(handle)

        for case in fixture["cases"]:
            with self.subTest(case=case["name"]):
                report = broker.inspect_codex_trust_state(
                    case["evidence"],
                    project_root=fixture["project_root"],
                    client=fixture["client"],
                    trust_surface=fixture["trust_surface"],
                    observed_at=fixture["resolved_at"],
                )
                expected = case["expected"]
                self.assertEqual(expected["state"], report["state"])
                self.assertFalse(report["mutation_allowed"])
                self.assertIn("no user-global trust mutation", report["non_actions"])
                self.assertEqual(expected["open_item_types"], [item["type"] for item in report["open_items"]])

                decision = broker.verify_trust_report(
                    report,
                    project_root=fixture["project_root"],
                    client=fixture["client"],
                    trust_surface=fixture["trust_surface"],
                    now=fixture["resolved_at"],
                )
                self.assertEqual(expected["verify_decision"], decision["decision"])

    def test_approval_request_and_record_name_exact_boundary_and_redact_evidence(self) -> None:
        request = broker.build_trust_approval_request(
            project_root=PROJECT_ROOT,
            actor="user",
            approval_evidence={"summary": "approve trust", "authorization": SECRET_VALUE},
            consent_receipt_ref="run/consent-receipts/trust.json",
            requested_at=STAMP,
            raw_sensitive_values=[SECRET_VALUE],
        )
        record = approval_record(approval_evidence={"summary": "approve trust", "authorization": SECRET_VALUE}, raw_sensitive_values=[SECRET_VALUE])
        encoded = json.dumps({"request": request, "record": record}, sort_keys=True)

        self.assertEqual(PROJECT_ROOT, request["project_root"])
        self.assertEqual("codex", request["client"])
        self.assertEqual(broker.DEFAULT_TRUST_SURFACE, request["trust_surface"])
        self.assertEqual("user", request["actor"])
        self.assertEqual(broker.TRUST_CONSENT_CLASS, request["consent_class"])
        self.assertEqual(broker.TRUST_PERSISTENT_TARGET, record["persistent_target"])
        self.assertNotIn(SECRET_VALUE, encoded)
        self.assertIn('"redacted": true', encoded)
        self.assertIn("does not grant trust", record["non_actions"])

    def test_valid_approval_record_verifies_with_embedded_consent_receipt(self) -> None:
        record = approval_record()

        decision = broker.verify_trust_approval_record(
            record,
            project_root=PROJECT_ROOT,
            client="codex",
            trust_surface=broker.DEFAULT_TRUST_SURFACE,
            actor="user",
            now=STAMP,
            plan=base_plan(),
        )

        self.assertEqual("allow", decision["decision"])
        self.assertTrue(decision["allowed"])

    def test_missing_stale_wrong_scope_or_tampered_approval_records_fail_closed(self) -> None:
        valid = approval_record()
        missing = broker.verify_trust_approval_record(None, project_root=PROJECT_ROOT, now=STAMP)
        stale = broker.verify_trust_approval_record(valid, project_root=PROJECT_ROOT, now="2026-06-10T22:30:00Z", max_age_seconds=60)
        wrong_root = broker.verify_trust_approval_record(valid, project_root="/tmp/other-project", now=STAMP)
        wrong_client = broker.verify_trust_approval_record(valid, project_root=PROJECT_ROOT, client="claude", now=STAMP)
        wrong_surface = broker.verify_trust_approval_record(valid, project_root=PROJECT_ROOT, trust_surface="other_surface", now=STAMP)
        tampered = copy.deepcopy(valid)
        tampered["actor"] = "assistant"
        tampered_decision = broker.verify_trust_approval_record(tampered, project_root=PROJECT_ROOT, now=STAMP)

        self.assertEqual("block", missing["decision"])
        self.assertIn("missing trust approval record", missing["reasons"])
        self.assertEqual("block", stale["decision"])
        self.assertIn("record approval is stale", stale["reasons"])
        self.assertEqual("block", wrong_root["decision"])
        self.assertIn("record project root scope does not match", wrong_root["reasons"])
        self.assertEqual("block", wrong_client["decision"])
        self.assertIn("record client scope does not match", wrong_client["reasons"])
        self.assertEqual("block", wrong_surface["decision"])
        self.assertIn("record trust surface scope does not match", wrong_surface["reasons"])
        self.assertEqual("block", tampered_decision["decision"])
        self.assertIn("record integrity check failed", tampered_decision["reasons"])

    def test_declines_expired_and_wrong_receipts_fail_closed(self) -> None:
        expired_receipt = broker.create_trust_consent_receipt(
            plan=base_plan(),
            project_root=PROJECT_ROOT,
            actor="user",
            approval_event_ref="transcript:expired",
            approval_evidence="operator approved trust",
            approved_at=PAST,
            expires_at=PAST,
        )
        expired_record = approval_record(consent_receipt=expired_receipt, approved_at=PAST, expires_at=FUTURE)
        wrong_receipt = authorization.create_consent_receipt(
            plan=base_plan(),
            consent_class="service_provision",
            actor="user",
            source_client="codex",
            source_client_auth_strength="wrapper_bound",
            approval_event_ref="transcript:service",
            approval_evidence="operator approved service only",
            approved_at=STAMP,
            expires_at=FUTURE,
            scope={
                "project_root": PROJECT_ROOT,
                "client": "codex",
                "target_clients": ["codex"],
                "persistent_target": "systemd",
                "service_binding": "serena:project",
            },
        )
        wrong_record = approval_record(consent_receipt=wrong_receipt)

        expired_decision = broker.verify_trust_approval_record(expired_record, project_root=PROJECT_ROOT, now=STAMP, plan=base_plan())
        wrong_decision = broker.verify_trust_approval_record(wrong_record, project_root=PROJECT_ROOT, now=STAMP, plan=base_plan())

        self.assertEqual("block", expired_decision["decision"])
        self.assertIn("expired", " ".join(expired_decision["reasons"]))
        self.assertEqual("block", wrong_decision["decision"])
        self.assertIn("not user-global client trust", " ".join(wrong_decision["reasons"]))

    def test_service_or_project_init_bundled_approval_cannot_authorize_trust(self) -> None:
        project_init = approval_record(approval_workflow="project_init")
        bundled = approval_record(bundled_consent_classes=["service_provision"])
        ref_only = broker.build_trust_approval_record(
            project_root=PROJECT_ROOT,
            actor="user",
            approval_evidence={"summary": "trust approved separately"},
            approved_at=STAMP,
            expires_at=FUTURE,
            consent_receipt_ref="run/consent-receipts/trust.json",
        )

        project_init_decision = broker.verify_trust_approval_record(project_init, project_root=PROJECT_ROOT, now=STAMP)
        bundled_decision = broker.verify_trust_approval_record(bundled, project_root=PROJECT_ROOT, now=STAMP)
        ref_only_decision = broker.verify_trust_approval_record(ref_only, project_root=PROJECT_ROOT, now=STAMP)

        self.assertEqual("block", project_init_decision["decision"])
        self.assertIn("conflated", " ".join(project_init_decision["reasons"]))
        self.assertEqual("block", bundled_decision["decision"])
        self.assertIn("trust approval bundles service/project-init consent", bundled_decision["reasons"])
        self.assertEqual("allow", ref_only_decision["decision"])

    def test_inspection_redacts_secret_like_evidence_and_flags_mutation_attempts(self) -> None:
        report = broker.inspect_codex_trust_state(
            {
                "state": "trusted",
                "root": PROJECT_ROOT,
                "client": "codex",
                "trust_surface": broker.DEFAULT_TRUST_SURFACE,
                "authorization": SECRET_VALUE,
                "user_global_trust_mutated": True,
            },
            project_root=PROJECT_ROOT,
            observed_at=STAMP,
            raw_sensitive_values=[SECRET_VALUE],
        )
        encoded = json.dumps(report, sort_keys=True)

        self.assertNotIn(SECRET_VALUE, encoded)
        self.assertFalse(report["mutation_allowed"])
        self.assertIn("attempted user-global trust mutation", " ".join(report["gaps"]))

        decision = broker.verify_trust_report(report, project_root=PROJECT_ROOT, now=STAMP)
        self.assertEqual("block", decision["decision"])
        self.assertIn("attempted user-global trust mutation", " ".join(decision["reasons"]))


if __name__ == "__main__":
    unittest.main()
