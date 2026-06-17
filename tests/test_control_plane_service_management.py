from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import control_plane_contracts as contracts
import control_plane_service_handoffs as handoffs
import control_plane_service_management as management


PROJECT_ROOT = "/home/dgk/workspace/legacy-controlplane-archive"
STAMP = "2026-05-30T23:00:00Z"


def ref(name: str) -> dict[str, Any]:
    return {
        "ref": f"contextforge://control-plane/{name}",
        "content_digest": management.stable_digest({"name": name}),
        "catalog_revision_or_etag": None,
        "resolved_at": STAMP,
    }


def candidate_descriptor(*, native_transports: list[str] | None = None) -> dict[str, Any]:
    sensitive_key = "_".join(("api", "key"))
    return {
        "candidate": True,
        "service_family": "invoiceapi",
        "canonical_service": "invoiceapi",
        "backend": {
            "command": "invoice-mcp",
            "package": "invoice-mcp",
            "native_transports": native_transports or ["stdio"],
        },
        sensitive_key: "plain-test-value",
        "scope": {
            "runtime_scope": "host",
            "credential_scope": {"scope": "tenant-a"},
            "resource_scope": {"scope": "invoices"},
        },
        "client_config_names": ["codex_invoice_alias", "claude_invoice_alias"],
    }


def handoff(*, native_transports: list[str] | None = None) -> dict[str, Any]:
    return handoffs.build_catalog_candidate_handoff(
        candidate_descriptor(native_transports=native_transports),
        project_root=PROJECT_ROOT,
    )


def existing_service() -> dict[str, Any]:
    return {
        "canonical_names": ["invoiceapi-gateway", "invoiceapi-server"],
        "catalog_revision": "catalog-r7",
        "dedupe_keys": {
            "backend_package": "invoice-mcp",
            "x_backend_command": "invoice-mcp",
            "runtime_scope": "host",
            "credential_scope": "tenant-a",
            "resource_scope": "invoices",
            "transport_scope": "stdio",
        },
        "contract_card_refs": [ref("service-bindings/invoiceapi")],
        "capsule_refs": [ref("capability-capsules/invoiceapi")],
        "semantic_tool_policy_refs": [ref("semantic-tool-policies/invoiceapi")],
        "verification_trace_refs": [ref("verification-traces/invoiceapi")],
    }


class ControlPlaneServiceManagementTests(unittest.TestCase):
    def test_handoff_plan_is_non_mutating_and_uses_contextforge_api_operations(self) -> None:
        candidate = handoff(native_transports=["streamable_http", "sse"])
        original = copy.deepcopy(candidate)

        result = management.plan_service_management_from_handoff(
            candidate,
            contract_card_refs=[ref("service-bindings/invoiceapi-draft")],
            semantic_tool_policy_refs=[ref("semantic-tool-policies/invoiceapi-draft")],
            catalog_revision="catalog-r1",
            generated_at=STAMP,
        )

        contracts.validate_artifact("service_management_result", result)
        self.assertEqual(original, candidate)
        self.assertEqual("plan_only", result["status"])
        self.assertFalse(management.completion_record_consumable(result))
        plan = result["x_catalog_plan"]
        self.assertFalse(plan["mutation_allowed"])
        self.assertTrue(plan["requires_explicit_approval"])
        self.assertFalse(plan["generic_project_init_approval_accepted"])
        self.assertEqual("ContextForge", plan["contextforge_authority"]["canonical_registry"])
        self.assertFalse(plan["contextforge_authority"]["direct_database_writes_allowed"])
        self.assertIn("POST /gateways", {operation["api"] for operation in plan["contextforge_api_operations"]})
        self.assertIn("GET /servers/{id}/tools", {operation["api"] for operation in plan["contextforge_api_operations"]})
        self.assertEqual("native_http_sse", plan["transport_decision"]["decision"])
        self.assertFalse(plan["transport_decision"]["bridge_required"])
        self.assertIn("preserves native HTTP and SSE access", plan["non_actions"])
        self.assertIn("project_init_catalog_mutation", result["forbidden_follow_up_effects"])
        self.assertNotIn("plain-test-value", str(result))
        self.assertNotIn("codex_invoice_alias-gateway", str(plan["canonical_names"]))

    def test_dedupe_existing_result_matches_backend_and_scope_and_is_consumable(self) -> None:
        result = management.plan_service_management_from_handoff(
            handoff(),
            existing_services=[existing_service()],
            generated_at=STAMP,
        )

        contracts.validate_artifact("service_management_result", result)
        self.assertEqual("dedupe_existing", result["status"])
        self.assertTrue(management.completion_record_consumable(result))
        self.assertEqual(["invoiceapi-gateway", "invoiceapi-server"], result["canonical_names"])
        self.assertEqual("tenant-a", result["x_dedupe_identity"]["credential_scope"])
        self.assertEqual("invoices", result["x_dedupe_identity"]["resource_scope"])
        self.assertEqual("stdio", result["x_dedupe_identity"]["transport_scope"])
        self.assertNotIn("plain-test-value", str(result))

    def test_dedupe_requires_refs_and_verification_evidence(self) -> None:
        incomplete = existing_service()
        incomplete["verification_trace_refs"] = []

        with self.assertRaises(management.ServiceManagementInputError):
            management.plan_service_management_from_handoff(
                handoff(),
                existing_services=[incomplete],
                generated_at=STAMP,
            )

    def test_transport_gap_preserves_native_side_and_recommends_only_missing_bridge(self) -> None:
        cases = [
            (["stdio"], "package_bridge_stdio_to_http_sse", "--stdio ... --expose-sse --expose-streamable-http"),
            (["sse"], "package_bridge_sse_to_http", "--connect-sse ... --expose-streamable-http"),
            (["streamable_http"], "package_bridge_http_to_sse", "--connect-streamable-http ... --expose-sse"),
            (["rest"], "native_rest_api_tool_registration", None),
        ]
        for native, expected_decision, command_part in cases:
            with self.subTest(native=native):
                plan = management.build_catalog_plan(handoff(native_transports=native), generated_at=STAMP)
                decision = plan["transport_decision"]
                self.assertEqual(expected_decision, decision["decision"])
                self.assertNotIn("unnecessary", " ".join(str(op) for op in plan["contextforge_api_operations"]).lower())
                if command_part:
                    self.assertTrue(decision["bridge_required"])
                    self.assertIn(command_part, decision["package_bridge_ref"])
                    self.assertIn("does not wrap transports beyond the missing required side", plan["non_actions"])
                else:
                    self.assertFalse(decision["bridge_required"])
                    self.assertIsNone(decision["package_bridge_ref"])

    def test_generic_project_init_approval_is_refused_for_catalog_promotion(self) -> None:
        result = management.plan_service_management_from_handoff(
            handoff(),
            approval_context={"approval_class": "project_init", "explicit": True, "approval_ref": "transcript:redacted"},
            generated_at=STAMP,
        )

        self.assertEqual("refused", result["status"])
        self.assertFalse(management.completion_record_consumable(result))
        self.assertEqual(
            "reason-generic_project_init_approval_cannot_promote_catalog_candidate",
            result["x_refusal"]["reason"],
        )

        with self.assertRaises(management.ServiceManagementInputError):
            management.build_catalog_plan(
                handoff(),
                approval_context={"approval_class": "generic_project_init", "explicit": True},
                generated_at=STAMP,
            )

    def test_approved_completion_result_requires_explicit_catalog_approval_and_refs(self) -> None:
        result = management.build_approved_completion_result(
            handoff(),
            canonical_names=["invoiceapi-gateway", "invoiceapi-server"],
            contract_card_refs=[ref("service-bindings/invoiceapi")],
            semantic_tool_policy_refs=[ref("semantic-tool-policies/invoiceapi")],
            verification_trace_refs=[ref("verification-traces/invoiceapi")],
            consent_receipt_refs=[ref("consent-receipts/invoiceapi-catalog")],
            capsule_refs=[ref("capability-capsules/invoiceapi")],
            catalog_revision="catalog-r2",
            approval_context={"approval_class": "catalog_promotion", "explicit": True, "approval_ref": "transcript:redacted"},
            generated_at=STAMP,
        )

        contracts.validate_artifact("service_management_result", result)
        self.assertEqual("approved_completed", result["status"])
        self.assertTrue(management.completion_record_consumable(result))
        self.assertEqual("catalog-r2", result["catalog_revision"])
        self.assertIn("invoiceapi-gateway", result["canonical_names"])

        with self.assertRaises(management.ServiceManagementInputError):
            management.build_approved_completion_result(
                handoff(),
                canonical_names=["invoiceapi-gateway"],
                contract_card_refs=[ref("service-bindings/invoiceapi")],
                semantic_tool_policy_refs=[ref("semantic-tool-policies/invoiceapi")],
                verification_trace_refs=[ref("verification-traces/invoiceapi")],
                consent_receipt_refs=[ref("consent-receipts/invoiceapi-catalog")],
                approval_context={"approval_class": "project_init", "explicit": True},
                generated_at=STAMP,
            )

    def test_secret_bearing_plan_inputs_are_rejected(self) -> None:
        bad_ref = ref("service-bindings/invoiceapi")
        bad_ref["_".join(("api", "key"))] = "plain-test-value"

        with self.assertRaises(management.ServiceManagementInputError):
            management.plan_service_management_from_handoff(
                handoff(),
                contract_card_refs=[bad_ref],
                generated_at=STAMP,
            )


if __name__ == "__main__":
    unittest.main()
