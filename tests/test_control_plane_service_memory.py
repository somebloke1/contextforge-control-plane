from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import control_plane_contracts as contracts
import control_plane_service_memory as memory


def serena_provider() -> dict[str, object]:
    return memory.build_service_memory_provider_metadata(
        provider_name="serena",
        service_binding="serena:project-root",
        provider_scope="project",
        durability="project_persistent",
        storage_location_class="service_local_store",
        supported_operations=["list", "read", "write", "update", "delete", "rename"],
        writes_require_approval=True,
    )


class ControlPlaneServiceMemoryTests(unittest.TestCase):
    def test_provider_metadata_is_contract_valid_and_reference_proposal_only(self) -> None:
        provider = serena_provider()

        contracts.validate_artifact("service_memory_provider", provider)
        self.assertEqual("serena", provider["provider_name"])
        self.assertEqual("serena:project-root", provider["service_binding"])
        self.assertEqual("project", provider["provider_scope"])
        self.assertTrue(provider["writes_require_approval"])
        self.assertTrue(provider["advisory_only"])
        self.assertFalse(provider["governance_reference_policy"]["generated_governance_projection_allowed"])
        self.assertFalse(provider["governance_reference_policy"]["bidirectional_sync_allowed"])
        self.assertEqual("governance_ledger", provider["conflict_flag_behavior"]["authority"])
        self.assertIn("governance_reference", provider["allowed_record_classes"])
        self.assertIn("governance_proposal", provider["allowed_record_classes"])

    def test_serena_is_generic_service_memory_provider_not_privileged(self) -> None:
        provider = serena_provider()

        self.assertEqual("service_memory_provider", provider["schema_uri"].rsplit("/", 2)[-2].replace("-", "_"))
        self.assertNotIn("serena", provider["forbidden_effects"])
        self.assertEqual("memory-provider-serena", provider["provider_id"])

    def test_mutating_memory_operations_require_approval(self) -> None:
        with self.assertRaises(memory.ServiceMemoryError):
            memory.build_service_memory_provider_metadata(
                provider_name="notes",
                service_binding="notes:project",
                provider_scope="project",
                durability="project_persistent",
                storage_location_class="service_local_store",
                supported_operations=["read", "write"],
                writes_require_approval=False,
            )

        provider = serena_provider()
        provider["writes_require_approval"] = False
        with self.assertRaises(contracts.SchemaValidationError):
            contracts.validate_artifact("service_memory_provider", provider)

    def test_governance_reference_allows_only_ledger_id_prefixes(self) -> None:
        provider = serena_provider()
        reference = memory.build_governance_reference(
            provider,
            "dec-20260530-0001",
            summary="See authoritative control-plane decision.",
        )

        self.assertEqual("governance_reference", reference["record_class"])
        self.assertEqual("DECISIONS.md", reference["ledger"])
        self.assertEqual("governance_ledger", reference["authoritative_source"])
        self.assertFalse(reference["settles_governance"])
        self.assertFalse(reference["mutates_governance"])
        contracts.validate_redacted(reference, require_status=True)

        with self.assertRaises(memory.ServiceMemoryError):
            memory.build_governance_reference(provider, "policy-20260530-0001")

    def test_governance_proposal_cannot_settle_governance(self) -> None:
        provider = serena_provider()
        proposal = memory.build_governance_proposal(
            provider,
            proposal_type="open_question",
            summary="Memory suggests this question may be narrowed; review ledger before any update.",
            governance_ids=["oq-20260528-0001"],
        )

        self.assertEqual("governance_proposal", proposal["record_class"])
        self.assertEqual("proposed_only", proposal["proposal_status"])
        self.assertTrue(proposal["writes_require_approval"])
        self.assertTrue(proposal["advisory_only"])
        self.assertFalse(proposal["settles_governance"])
        self.assertFalse(proposal["mutates_governance"])
        self.assertEqual("mentality_or_governance_crud_after_user_approval", proposal["required_write_path"])
        self.assertIn("settle_open_question", proposal["forbidden_effects"])
        contracts.validate_redacted(proposal, require_status=True)

    def test_conflict_flag_prefers_governance_and_only_proposes_review(self) -> None:
        provider = serena_provider()
        flag = memory.flag_governance_conflict(
            provider,
            governance_id="ai-20260530-0001",
            memory_summary="Service memory says the work is complete.",
            governance_summary="Ledger still parks the intention pending verification.",
        )

        self.assertEqual("conflict_flag", flag["record_class"])
        self.assertEqual("ABEYANT_INTENTIONS.md", flag["ledger"])
        self.assertEqual("governance_ledger", flag["authority"])
        self.assertEqual("governance_ledger", flag["selected_value_source"])
        self.assertFalse(flag["memory_value_used_as_authority"])
        self.assertFalse(flag["settles_governance"])
        self.assertFalse(flag["mutates_governance"])
        self.assertEqual("governance_proposal", flag["proposal"]["record_class"])
        self.assertFalse(flag["proposal"]["mutates_governance"])
        contracts.validate_redacted(flag, require_status=True)

    def test_metadata_and_records_are_sanitized_without_secret_values(self) -> None:
        provider = memory.build_service_memory_provider_metadata(
            provider_name="provider with spaces",
            service_binding="secret-notes:project",
            provider_scope="project",
            durability="project_persistent",
            storage_location_class="service_local_store",
            supported_operations=["list", "read"],
            verification_probe={"probe_type": "readback", "x_api_key": "plain-test-value"},
        )
        self.assertEqual("memory-provider-provider-with-spaces", provider["provider_id"])
        self.assertEqual("provider with spaces", provider["provider_name"])
        self.assertEqual("redacted", provider["redaction_status"])
        self.assertEqual("<redacted>", provider["verification_probe"]["x_api_key"])
        contracts.validate_artifact("service_memory_provider", provider)

        payload = memory.sanitize_memory_provider_payload({"api_key": "plain-test-value", "note": "ok"})
        self.assertEqual("<redacted>", payload["api_key"])
        contracts.validate_redacted(payload)

    def test_none_operation_cannot_be_combined_with_real_operations(self) -> None:
        with self.assertRaises(memory.ServiceMemoryError):
            memory.build_service_memory_provider_metadata(
                provider_name="readonly",
                service_binding="readonly:host",
                provider_scope="host",
                durability="ephemeral",
                storage_location_class="unknown",
                supported_operations=["none", "read"],
            )


if __name__ == "__main__":
    unittest.main()
