from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import control_plane_contracts as contracts
import control_plane_service_handoffs as handoffs


PROJECT_ROOT = "/home/dgk/workspace/legacy-controlplane-archive"


def candidate_descriptor() -> dict[str, object]:
    sensitive_key = "_".join(("api", "key"))
    return {
        "candidate": True,
        "service_family": "invoiceapi",
        "canonical_service": "invoiceapi",
        "backend": {"transport": "stdio", "command": "invoice-mcp"},
        sensitive_key: "plain-test-value",
        "scope": {
            "runtime_scope": "host",
            "resource_scope": {"scope": "invoices"},
        },
        "client_config_names": ["codex_invoice_alias", "claude_invoice_alias"],
    }


class ControlPlaneServiceHandoffTests(unittest.TestCase):
    def test_catalog_candidate_handoff_is_redacted_valid_and_non_mutating(self) -> None:
        descriptor = candidate_descriptor()
        original = copy.deepcopy(descriptor)
        sensitive_key = "_".join(("api", "key"))

        handoff = handoffs.build_catalog_candidate_handoff(descriptor, project_root=PROJECT_ROOT)

        contracts.validate_artifact("service_management_handoff", handoff)
        self.assertEqual(original, descriptor)
        self.assertEqual("handoff-catalog_candidate-invoiceapi", handoff["handoff_id"])
        self.assertEqual("project_init", handoff["source"])
        self.assertEqual(PROJECT_ROOT, handoff["project_root"])
        self.assertEqual("redacted", handoff["redaction_status"])
        self.assertEqual("candidate_or_uncataloged_backend", handoff["suspected_instantiation_class"])
        self.assertEqual("service_management_plan", handoff["required_next_workflow"])
        self.assertEqual("<redacted>", handoff["candidate_descriptor"][sensitive_key])
        self.assertEqual("invoice-mcp", handoff["dedupe_keys"]["backend_package"])
        self.assertEqual("host", handoff["dedupe_keys"]["runtime_scope"])
        self.assertEqual("invoices", handoff["dedupe_keys"]["resource_scope"])
        self.assertEqual("stdio", handoff["dedupe_keys"]["transport_scope"])
        self.assertIn("catalog_promotion", handoff["forbidden_under_current_approval"])
        self.assertIn("project_state_service_record", handoff["forbidden_under_current_approval"])
        self.assertIn("contextforge_registration", handoff["forbidden_under_current_approval"])
        self.assertIn("backend_provision", handoff["forbidden_under_current_approval"])
        self.assertEqual("catalog_candidate", handoff["x_handoff_class"])
        self.assertEqual(
            "client config names are discovery evidence only",
            handoff["x_discovery_evidence"]["identity_policy"],
        )
        self.assertNotIn("codex_invoice_alias", handoff["handoff_id"])
        self.assertNotIn("codex_invoice_alias", handoff["dedupe_keys"].values())

    def test_catalog_repair_handoff_uses_extension_fields_for_repair_metadata(self) -> None:
        descriptor = {
            "service_family": "context7",
            "canonical_service": "context7",
            "backend": {"package": "context7-mcp", "native_transports": ["streamable-http", "sse"]},
            "scope": {"runtime_scope": "host", "resource_scope": {"scope": "docs"}},
        }
        sensitive_key = "".join(("auth", "_", "token"))
        repair_need = {
            "repair_type": "missing_contract_card",
            "catalog_entry": "context7",
            sensitive_key: "plain-test-value",
        }

        handoff = handoffs.build_catalog_repair_handoff(
            descriptor,
            project_root=PROJECT_ROOT,
            reason="catalog_contract_missing",
            repair_need=repair_need,
        )

        contracts.validate_artifact("service_management_handoff", handoff)
        self.assertEqual("catalog_read", handoff["source"])
        self.assertEqual("catalog_repair_need", handoff["x_handoff_class"])
        self.assertEqual("catalog_contract_missing", handoff["x_handoff_reason"])
        self.assertEqual("<redacted>", handoff["x_repair_need"][sensitive_key])
        self.assertEqual("context7-mcp", handoff["dedupe_keys"]["backend_package"])
        self.assertEqual("host", handoff["dedupe_keys"]["runtime_scope"])
        self.assertEqual("docs", handoff["dedupe_keys"]["resource_scope"])
        self.assertEqual("http", handoff["dedupe_keys"]["transport_scope"])
        self.assertIn("direct_catalog_repair", handoff["forbidden_under_current_approval"])
        self.assertIn("catalog_promotion", handoff["forbidden_under_current_approval"])
        self.assertNotIn("repair_need", handoff)

    def test_handoff_output_is_deterministic_and_json_compatible(self) -> None:
        descriptor = {
            "candidate": True,
            "service_family": "tuple-service",
            "backend": {"transport": "rest", "command": ("tuple", "command")},
            "native_transports": ("rest",),
            "scope": {"runtime_scope": "project", "workspace_root": Path(PROJECT_ROOT)},
        }

        first = handoffs.build_catalog_candidate_handoff(descriptor, project_root=PROJECT_ROOT, source="other")
        second = handoffs.build_catalog_candidate_handoff(descriptor, project_root=PROJECT_ROOT, source="other")

        self.assertEqual(first, second)
        self.assertEqual("project_init", first["source"])
        self.assertEqual(["tuple", "command"], first["candidate_descriptor"]["backend"]["command"])
        self.assertEqual(PROJECT_ROOT, first["candidate_descriptor"]["scope"]["workspace_root"])
        self.assertEqual("rest", first["dedupe_keys"]["transport_scope"])

    def test_descriptor_must_be_mapping(self) -> None:
        with self.assertRaises(handoffs.ServiceHandoffInputError):
            handoffs.build_catalog_candidate_handoff(["not", "a", "mapping"])  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
