from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import control_plane_contracts as contracts
import control_plane_verification as verification


STAMP = "2026-05-30T22:00:00Z"
DIGEST = "sha256:" + "a" * 64
SECRET_VALUE = "Bearer " + ("A" * 24)


def trace_ref(trace: dict[str, object]) -> dict[str, object]:
    return verification.build_verification_trace_ref(trace, resolved_at=STAMP)


class ControlPlaneVerificationTests(unittest.TestCase):
    def build_trace(
        self,
        *,
        trace_id: str = "trace-contextforge",
        plan_id: str | None = "plan-serena",
        step_id: str = "verify-serena",
        service_binding: str = "serena:project-root",
        layer: str = "contextforge_gateway",
        status: str = "passed",
        target_client: str | None = "codex",
        failure_classification: str | None = None,
        observations: object | None = None,
    ) -> dict[str, object]:
        return verification.build_verification_trace(
            trace_id=trace_id,
            plan_id=plan_id,
            step_id=step_id,
            service_binding=service_binding,
            layer=layer,
            probe_id=f"probe-{layer}",
            probe_type="readback",
            subject=f"{service_binding}:{layer}",
            status=status,
            observations=observations
            if observations is not None
            else {"summary": "probe passed", "http_status": 200, "body": {"tools": ["list_projects"]}},
            target_client=target_client,
            failure_classification=failure_classification,
            generated_at=STAMP,
        )

    def test_passing_trace_validates_and_includes_redacted_observation_digest(self) -> None:
        trace = self.build_trace()

        contracts.validate_artifact("verification_trace", trace)

        event = trace["probe_events"][0]
        self.assertEqual(trace["result"], "passed")
        self.assertEqual(trace["exercised_surface"], "contextforge_dev_docker")
        self.assertEqual(trace["x_exercised_surface"], "contextforge_dev_docker")
        self.assertEqual(trace["redaction_status"], "redacted")
        self.assertRegex(event["x_observation_digest"], r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(event["evidence_hash"], event["x_observation_digest"])
        self.assertRegex(trace["result_hash"], r"^sha256:[0-9a-f]{64}$")

    def test_trace_normalizes_exercised_surface_aliases(self) -> None:
        trace = verification.build_verification_trace(
            trace_id="trace-pi-client",
            plan_id="plan-serena",
            step_id="verify-serena",
            service_binding="serena:project-root",
            layer="target_client",
            probe_id="probe-target-client",
            probe_type="readback",
            subject="serena:project-root:target_client",
            status="passed",
            observations={"summary": "Pi client listed helper tools"},
            exercised_surface="Pi client Docker",
            target_client="pi",
            generated_at=STAMP,
        )

        contracts.validate_artifact("verification_trace", trace)
        self.assertEqual("pi_client_docker", trace["exercised_surface"])

    def test_failed_and_stale_traces_validate_and_carry_failure_classification(self) -> None:
        failed = self.build_trace(status="failed", failure_classification="gateway_readback_failed")
        stale = self.build_trace(
            trace_id="trace-stale",
            layer="backend",
            status="stale",
            failure_classification="probe_expired",
        )

        contracts.validate_artifact("verification_trace", failed)
        contracts.validate_artifact("verification_trace", stale)

        self.assertEqual(failed["result"], "failed")
        self.assertEqual(failed["failed_layer"], "contextforge_gateway")
        self.assertEqual(failed["x_failure_classification"], "gateway_readback_failed")
        self.assertEqual(stale["result"], "inconclusive")
        self.assertEqual(stale["x_result_status"], "stale")
        self.assertEqual(stale["x_failure_classification"], "probe_expired")

    def test_verified_lifecycle_transition_requires_passed_matching_trace_ref(self) -> None:
        trace = self.build_trace()
        ref = trace_ref(trace)

        decision = verification.validate_lifecycle_transition(
            plan_id="plan-serena",
            step_id="verify-serena",
            service_binding="serena:project-root",
            target_state="verified",
            required_layers=["contextforge_gateway"],
            trace_refs=[ref],
            trace_artifacts={ref["ref"]: trace},
            target_client="codex",
        )

        self.assertTrue(decision["valid"])
        self.assertEqual(decision["decision"], "allow")
        self.assertEqual(decision["matrix"]["layers"]["contextforge_gateway"]["status"], "passed")

    def test_missing_trace_blocks_verified_transition(self) -> None:
        decision = verification.validate_lifecycle_transition(
            plan_id="plan-serena",
            step_id="verify-serena",
            service_binding="serena:project-root",
            target_state="verified",
            required_layers=["contextforge_gateway"],
            trace_refs=[],
            trace_artifacts={},
            target_client="codex",
        )

        self.assertFalse(decision["valid"])
        self.assertEqual(decision["decision"], "block")
        self.assertEqual(decision["reason"], "missing_trace_ref")

    def test_failed_or_mismatched_trace_blocks_transition(self) -> None:
        failed = self.build_trace(status="failed", failure_classification="gateway_readback_failed")
        failed_ref = trace_ref(failed)
        failed_decision = verification.validate_lifecycle_transition(
            plan_id="plan-serena",
            step_id="verify-serena",
            service_binding="serena:project-root",
            target_state="verified",
            required_layers=["contextforge_gateway"],
            trace_refs=[failed_ref],
            trace_artifacts={failed_ref["ref"]: failed},
            target_client="codex",
        )

        mismatched = self.build_trace(trace_id="trace-other-step", step_id="other-step")
        mismatched_ref = trace_ref(mismatched)
        mismatched_decision = verification.validate_lifecycle_transition(
            plan_id="plan-serena",
            step_id="verify-serena",
            service_binding="serena:project-root",
            target_state="verified",
            required_layers=["contextforge_gateway"],
            trace_refs=[mismatched_ref],
            trace_artifacts={mismatched_ref["ref"]: mismatched},
            target_client="codex",
        )

        self.assertFalse(failed_decision["valid"])
        self.assertEqual(failed_decision["matrix"]["layers"]["contextforge_gateway"]["status"], "failed")
        self.assertFalse(mismatched_decision["valid"])
        self.assertEqual(mismatched_decision["matrix"]["layers"]["contextforge_gateway"]["status"], "mismatched")

    def test_trace_ref_content_digest_mismatch_blocks_transition(self) -> None:
        failed = self.build_trace(status="failed", failure_classification="gateway_readback_failed")
        ref_for_failed = trace_ref(failed)
        tampered_passed = self.build_trace()

        decision = verification.validate_lifecycle_transition(
            plan_id="plan-serena",
            step_id="verify-serena",
            service_binding="serena:project-root",
            target_state="verified",
            required_layers=["contextforge_gateway"],
            trace_refs=[ref_for_failed],
            trace_artifacts={ref_for_failed["ref"]: tampered_passed},
            target_client="codex",
        )

        self.assertFalse(decision["valid"])
        self.assertEqual("block", decision["decision"])
        self.assertEqual("trace_ref_digest_mismatch", decision["reason"])
        self.assertEqual("mismatched", decision["matrix"]["layers"]["contextforge_gateway"]["status"])

    def test_surface_mismatch_blocks_lifecycle_overclaim(self) -> None:
        trace = verification.build_verification_trace(
            trace_id="trace-wrong-surface",
            plan_id="plan-serena",
            step_id="verify-serena",
            service_binding="serena:project-root",
            layer="contextforge_gateway",
            probe_id="probe-contextforge_gateway",
            probe_type="readback",
            subject="serena:project-root:contextforge_gateway",
            status="passed",
            observations={"summary": "Pi helper saw a banner, not ContextForge gateway routing"},
            exercised_surface="pi_client_docker",
            target_client="pi",
            generated_at=STAMP,
        )
        ref = trace_ref(trace)

        decision = verification.validate_lifecycle_transition(
            plan_id="plan-serena",
            step_id="verify-serena",
            service_binding="serena:project-root",
            target_state="verified",
            required_layers=["contextforge_gateway"],
            trace_refs=[ref],
            trace_artifacts={ref["ref"]: trace},
            target_client="pi",
        )

        self.assertFalse(decision["valid"])
        self.assertEqual("surface_cannot_support_required_layer", decision["reason"])
        self.assertEqual("block", decision["surface_claim"]["decision"])
        self.assertEqual(
            {
                "trace_ref": ref["ref"],
                "trace_id": "trace-wrong-surface",
                "layer": "contextforge_gateway",
                "exercised_surface": "pi_client_docker",
                "reason": "pi_client_docker evidence cannot prove contextforge_gateway",
            },
            decision["surface_claim"]["unsupported_surfaces"][0],
        )

    def test_multiple_required_layers_matrix_classifies_pass_fail_and_stale(self) -> None:
        backend = self.build_trace(trace_id="trace-backend", layer="backend")
        gateway = self.build_trace(
            trace_id="trace-gateway",
            layer="contextforge_gateway",
            status="failed",
            failure_classification="gateway_unreachable",
        )
        client = self.build_trace(
            trace_id="trace-client",
            layer="target_client",
            status="stale",
            failure_classification="client_restart_required",
        )
        refs = [trace_ref(backend), trace_ref(gateway), trace_ref(client)]
        traces = {ref["ref"]: trace for ref, trace in zip(refs, [backend, gateway, client])}

        matrix = verification.build_verification_matrix(
            plan_id="plan-serena",
            step_id="verify-serena",
            service_binding="serena:project-root",
            required_layers=["backend", "contextforge_gateway", "target_client", "tool_policy"],
            trace_refs=refs,
            trace_artifacts=traces,
            target_client="codex",
        )

        self.assertEqual(matrix["layers"]["backend"]["status"], "passed")
        self.assertEqual(matrix["layers"]["contextforge_gateway"]["status"], "failed")
        self.assertEqual(matrix["layers"]["target_client"]["status"], "stale")
        self.assertEqual(matrix["layers"]["tool_policy"]["status"], "missing")
        self.assertEqual(matrix["summary"]["passed"], 1)
        self.assertEqual(matrix["summary"]["failed"], 1)
        self.assertEqual(matrix["summary"]["stale"], 1)
        self.assertEqual(matrix["summary"]["missing"], 1)

    def test_trace_outputs_do_not_contain_secret_values_or_secret_shaped_literals(self) -> None:
        trace = self.build_trace(
            observations={
                "summary": "token-bearing output was captured",
                "authorization": SECRET_VALUE,
                "body": f"runtime returned {SECRET_VALUE}",
                "nested": {"api_key": "sk-" + ("B" * 24)},
            },
        )
        encoded = json.dumps(trace, sort_keys=True)

        contracts.validate_artifact("verification_trace", trace)
        self.assertNotIn(SECRET_VALUE, encoded)
        self.assertNotIn("sk-" + ("B" * 24), encoded)
        self.assertIn("redacted_observation_digest", encoded)
        self.assertIn("<redacted>", encoded)

    def test_secret_shaped_trace_metadata_is_rejected(self) -> None:
        with self.assertRaises(verification.VerificationTraceError):
            verification.build_verification_trace(
                trace_id="trace-secret-subject",
                plan_id="plan-serena",
                step_id="verify-serena",
                service_binding="serena:project-root",
                layer="contextforge_gateway",
                probe_id="probe-contextforge_gateway",
                probe_type="readback",
                subject=SECRET_VALUE,
                status="passed",
                observations={"summary": "probe passed"},
                target_client="codex",
                generated_at=STAMP,
            )


if __name__ == "__main__":
    unittest.main()
