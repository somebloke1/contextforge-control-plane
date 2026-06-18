from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import control_plane_contracts as contracts


DIGEST = "sha256:" + "a" * 64
OTHER_DIGEST = "sha256:" + "b" * 64
STAMP = "2026-05-30T21:00:00Z"


def ref(name: str = "artifact") -> dict[str, object]:
    return {
        "ref": f"contextforge://control-plane/{name}/v1",
        "content_digest": DIGEST,
        "catalog_revision_or_etag": "rev-1",
        "resolved_at": STAMP,
    }


def transport_profile() -> dict[str, object]:
    return {
        "native_transports": ["http"],
        "required_client_transports": ["http", "sse"],
        "bridge_mode": "none",
        "package_bridge_ref": None,
        "forbidden_bridge_effects": ["do_not_wrap_native_http"],
        "required_endpoint_verification": ["/mcp", "/sse"],
    }


def service_binding_contract_card() -> dict[str, object]:
    return {
        "card_id": "card-context7",
        "schema_uri": "contextforge://control-plane/schemas/service-binding-contract-card/v1",
        "service_family": "context7",
        "service_binding": "context7:canonical",
        "instantiation_class": "shared_canonical",
        "authority_boundary": "ContextForge catalog owns canonical service identity.",
        "project_scope": {"mode": "availability_only"},
        "credential_scope": {"scope": "redacted"},
        "resource_scope": None,
        "caller_or_session_scope": None,
        "backend_instance_ref": None,
        "contextforge_gateway": {"canonical_name": "context7"},
        "virtual_server": {"canonical_name": "context7_project_view"},
        "client_adapter_refs": [ref("client-adapters/codex")],
        "semantic_tool_policy_ref": ref("tool-policies/context7"),
        "transport_profile": transport_profile(),
        "required_consent_classes": ["read_only_inspection"],
        "verification_matrix": {"required_layers": ["contextforge_gateway", "target_client", "redaction"]},
        "non_actions": ["no_project_backend"],
        "evidence_requirements": ["gateway_readback", "client_list_tools"],
    }


def shared_service_capability_capsule() -> dict[str, object]:
    return {
        "capsule_id": "capsule-context7",
        "schema_uri": "contextforge://control-plane/schemas/shared-service-capability-capsule/v1",
        "service_family": "context7",
        "canonical_service": "context7",
        "allowed_project_binding_modes": ["record_availability", "bind_existing", "verify_existing"],
        "project_state_recording_policy": "record refs and traces only; do not claim backend ownership",
        "verification_requirements": ["canonical gateway readback", "target client call-tool"],
        "consent_requirements": ["read_only_inspection"],
        "transport_profile": transport_profile(),
        "forbidden_project_init_effects": ["new_backend", "new_bridge", "server_instance_directory"],
        "contract_card_refs": [ref("service-bindings/context7")],
    }


def semantic_tool_policy() -> dict[str, object]:
    return {
        "policy_id": "policy-context7",
        "schema_uri": "contextforge://control-plane/schemas/semantic-tool-policy/v1",
        "service_binding": "context7:canonical",
        "risk_classes": ["read_only", "unknown"],
        "scope_impacts": ["documentation_lookup"],
        "approval_gates": [],
        "allowed_tool_selectors": [{"selector_type": "tag", "value": "docs", "fail_closed": True}],
        "excluded_tool_selectors": [{"selector_type": "risk_class", "value": "unknown", "fail_closed": True}],
        "manual_overrides": [],
        "compiled_tool_ids": [],
        "negative_checks": [{"check": "unknown_tools_hidden"}],
        "last_compiled_at": None,
        "last_readback_trace_ref": None,
    }


def service_management_handoff() -> dict[str, object]:
    return {
        "handoff_id": "handoff-web-search",
        "schema_uri": "contextforge://control-plane/schemas/service-management-handoff/v1",
        "source": "project_init",
        "project_root": "/home/dgk/workspace/legacy-controlplane-archive",
        "candidate_descriptor": {"package": "redacted", "argv": "redacted"},
        "redaction_status": "redacted",
        "dedupe_keys": {
            "backend_package": "web-search",
            "runtime_scope": "host",
            "credential_scope": "redacted",
            "resource_scope": "web",
            "transport_scope": "stdio",
        },
        "suspected_instantiation_class": "candidate_or_uncataloged_backend",
        "required_next_workflow": "service_management_plan",
        "forbidden_under_current_approval": ["catalog_promotion"],
    }


def service_management_result() -> dict[str, object]:
    return {
        "result_id": "service-management-result-web-search",
        "schema_uri": "contextforge://control-plane/schemas/service-management-result/v1",
        "handoff_id": "handoff-web-search",
        "status": "dedupe_existing",
        "contract_card_refs": [ref("service-bindings/web-search")],
        "capsule_refs": [],
        "semantic_tool_policy_refs": [ref("tool-policies/web-search")],
        "canonical_names": ["web_search"],
        "catalog_revision": "rev-2",
        "consent_receipt_refs": [],
        "verification_trace_refs": [ref("traces/web-search")],
        "redaction_status": "redacted",
        "forbidden_follow_up_effects": ["project_init_catalog_mutation"],
    }


def service_provision_plan() -> dict[str, object]:
    return {
        "provision_plan_id": "plan-serena",
        "schema_uri": "contextforge://control-plane/schemas/service-provision-plan/v1",
        "service_binding": "serena:project-root",
        "service_provision_steps": [
            {
                "step_id": "write-project-state",
                "preconditions": ["contract card resolved"],
                "persistent_target": "project_state",
                "operation_class": "project_state_write",
                "expected_state_transition": "planned-to-pending",
                "required_policy_refs": [ref("tool-policies/serena")],
                "required_conformance_refs": [ref("client-adapters/codex")],
                "negative_checks": [{"check": "no_catalog_promotion"}],
            }
        ],
        "stale_inputs": [ref("service-bindings/serena")],
        "write_set": [".project/context_forge_state.json"],
        "consent_receipt_refs": [ref("receipts/serena")],
        "expected_readback": ["project_state_revision_incremented"],
        "idempotency_mode": "idempotent",
        "compensation_repair_mode": "forward_repair",
        "produced_artifact_refs": [ref("traces/serena")],
        "redaction_status": "redacted",
    }


def consent_receipt() -> dict[str, object]:
    return {
        "receipt_id": "receipt-serena",
        "schema_uri": "contextforge://control-plane/schemas/consent-receipt/v1",
        "plan_id": "plan-serena",
        "plan_digest": DIGEST,
        "plan_presented_digest": OTHER_DIGEST,
        "consent_class": "service_provision",
        "scope": {
            "project_root": "/home/dgk/workspace/legacy-controlplane-archive",
            "service_binding": "serena:project-root",
            "client": "codex",
            "persistent_target": "systemd",
        },
        "actor": "user",
        "source_client": "codex",
        "source_client_auth_strength": "asserted",
        "approval_nonce": "nonce-1",
        "approval_channel": "interactive_user",
        "approval_event_ref": "transcript:1",
        "issued_by": "approve_plan",
        "approved_at": STAMP,
        "approval_evidence": "redacted approval summary",
        "expires_at": "2026-05-31T21:00:00Z",
        "replay_policy": "same_plan_resume",
        "redaction_status": "redacted",
    }


def verification_trace() -> dict[str, object]:
    return {
        "trace_id": "trace-serena",
        "schema_uri": "contextforge://control-plane/schemas/verification-trace/v1",
        "plan_id": "plan-serena",
        "service_binding": "serena:project-root",
        "exercised_surface": "contextforge_dev_docker",
        "target_client": "codex",
        "adapter_conformance_pack": ref("client-adapters/codex"),
        "probe_events": [
            {"probe_id": "probe-contextforge", "layer": "contextforge_gateway", "status": "passed", "evidence_hash": DIGEST}
        ],
        "negative_checks": [{"check": "excluded_tool_absent", "status": "passed"}],
        "redaction_checks": [{"check": "no_secret_values", "status": "passed"}],
        "result": "passed",
        "failed_layer": None,
        "result_hash": DIGEST,
        "generated_at": STAMP,
        "redaction_status": "passed",
    }


def client_adapter_conformance_pack() -> dict[str, object]:
    return {
        "pack_id": "codex-v1",
        "schema_uri": "contextforge://control-plane/schemas/client-adapter-conformance-pack/v1",
        "client_name": "codex",
        "version_constraints": ["desktop>=2026.05"],
        "config_surface_fixtures": [{"surface": ".codex/config.toml"}],
        "owned_block_classes": ["owned", "legacy_owned", "absent"],
        "direct_http_header_support": True,
        "stdio_wrapper_behavior": {"required": False},
        "trust_requirements": {"global_trust_required": True},
        "trust_broker_interface": {"probe": "codex_trust_readback"},
        "restart_model": {"restart_blocks_initialized": True},
        "stale_config_probes": [{"probe": "config_generation"}],
        "list_tools_probes": [{"probe": "list_tools"}],
        "call_tool_probes": [{"probe": "call_tool"}],
        "token_source_constraints": ["no tokens in argv or logs"],
        "negative_tool_policy_visibility_checks": [{"probe": "forbidden_tool_hidden"}],
        "known_unsupported_behaviors": [],
        "redaction_status": "passed",
    }


def requirement_scenario() -> dict[str, object]:
    return {
        "scenario_id": "cfcp-scenario-001",
        "schema_uri": "contextforge://control-plane/schemas/requirement-scenario/v1",
        "requirement_ids": ["cfcp-req-0001"],
        "tested_agent_view": {
            "cwd": "/home/dgk/workspace/legacy-controlplane-archive",
            "user_prompt": "Initialize the project-local ContextForge service.",
            "available_tools": [{"name": "shell"}],
            "visible_files": ["AGENTS.md"],
        },
        "hidden_initial_conditions": {
            "filesystem": {},
            "contextforge_catalog": {},
            "client_configs": {},
            "trust_state": {},
            "ports_units": {},
            "project_state": {},
        },
        "during_test_events": [
            {
                "event_id": "event-1",
                "actor": "tool",
                "visible_to": ["tested_agent"],
                "payload": {"stdout": "service not yet registered"},
                "hidden_state_delta": {},
                "tool_output_visibility": "tested_agent",
                "evaluator_only": False,
            }
        ],
        "allowed_mutations": [{"path": ".project/context_forge_state.json"}],
        "forbidden_mutations": [{"path": "DECISIONS.md"}],
        "expected_outcomes": {
            "state": {"status": "in_progress"},
            "open_items": [],
            "non_actions": ["no catalog mutation"],
            "required_traces": ["trace-serena"],
            "required_receipts": ["receipt-serena"],
        },
        "deterministic_assertions": [{"assertion": "schema-valid"}],
        "inference_rubric": [{"requirement_id": "cfcp-req-0001"}],
    }


def evaluator_verdict(verdict: str = "pass") -> dict[str, object]:
    return {
        "verdict_id": "verdict-1",
        "schema_uri": "contextforge://control-plane/schemas/evaluator-verdict/v1",
        "created_at": STAMP,
        "evaluator_run": {"model_or_agent": "eval-agent", "prompt_digest": DIGEST},
        "verdict": verdict,
        "scenario_id": "cfcp-scenario-001",
        "requirement_ids": ["cfcp-req-0001"],
        "evaluated_artifact_refs": [ref("scenario/cfcp-scenario-001")],
        "deterministic_assertion_refs": [ref("assertions/schema-valid")],
        "failed_requirements": ["cfcp-req-0001"] if verdict == "fail" else [],
        "evidence": [
            {"source": "trace", "reference": "trace-serena", "summary": "redacted trace passed", "evidence_hash": DIGEST}
        ],
        "likely_cause": "implementation_failure" if verdict == "fail" else "flaky_environment",
        "remediation_target": "code",
        "redaction_status": "passed",
        "evidence_hashes": [DIGEST],
        "requirement_gap_proposal": "clarify requirement" if verdict == "requirement_gap" else None,
    }


def evidence_ledger() -> dict[str, object]:
    return {
        "ledger_id": "ledger-1",
        "schema_uri": "contextforge://control-plane/schemas/evidence-ledger/v1",
        "run_id": "run-1",
        "requirement_ids": ["cfcp-req-0001"],
        "scenario_ref": "cfcp-scenario-001",
        "tested_agent_transcript_ref": "run/redacted/transcript.json",
        "deterministic_assertion_results": [{"assertion": "schema-valid", "result": "passed"}],
        "consent_receipt_refs": [ref("receipts/serena")],
        "verification_trace_refs": [ref("traces/serena")],
        "world_state_diff_ref": "run/redacted/world-state-diff.json",
        "evaluator_verdict_refs": [ref("verdicts/1")],
        "remediation_refs": [],
        "redaction_status": "passed",
        "evidence_hashes": [DIGEST],
    }


def governance_reconciliation_pack() -> dict[str, object]:
    return {
        "pack_id": "gov-pack-1",
        "schema_uri": "contextforge://control-plane/schemas/governance-reconciliation-pack/v1",
        "rfc_digest": DIGEST,
        "ledger_digests": {"DECISIONS.md": DIGEST, "OPEN_QUESTIONS.md": OTHER_DIGEST},
        "decisions_missing_from_ledgers": [{"decision": "control-plane authority"}],
        "open_questions_answered_or_narrowed": [],
        "abeyant_intentions_needing_updates": [],
        "service_memory_conflicts": [],
        "suggested_governance_crud_operations": [{"operation": "propose"}],
        "advisory_only": True,
        "forbidden_effects": ["edit_ledgers", "bypass_governance_crud", "bypass_mentality"],
        "redaction_status": "passed",
        "evidence_hashes": [DIGEST],
    }


FACTORIES = {
    "service_binding_contract_card": service_binding_contract_card,
    "shared_service_capability_capsule": shared_service_capability_capsule,
    "semantic_tool_policy": semantic_tool_policy,
    "service_management_handoff": service_management_handoff,
    "service_management_result": service_management_result,
    "service_provision_plan": service_provision_plan,
    "consent_receipt": consent_receipt,
    "verification_trace": verification_trace,
    "client_adapter_conformance_pack": client_adapter_conformance_pack,
    "requirement_scenario": requirement_scenario,
    "evaluator_verdict": evaluator_verdict,
    "evidence_ledger": evidence_ledger,
    "governance_reconciliation_pack": governance_reconciliation_pack,
}


class ContractArtifactTests(unittest.TestCase):
    def test_schema_loads_as_draft_2020_12(self) -> None:
        contracts.schema_validator()

    def test_all_artifact_happy_paths_validate(self) -> None:
        for kind, factory in FACTORIES.items():
            with self.subTest(kind=kind):
                artifact = factory()
                self.assertIs(contracts.validate_artifact(kind, artifact), artifact)

    def test_unknown_kind_is_rejected(self) -> None:
        with self.assertRaises(contracts.UnknownArtifactKindError):
            contracts.validate_artifact("unknown", {})

    def test_missing_required_field_is_rejected(self) -> None:
        artifact = service_binding_contract_card()
        artifact.pop("authority_boundary")
        with self.assertRaises(contracts.SchemaValidationError):
            contracts.validate_artifact("service_binding_contract_card", artifact)

    def test_enum_validation_rejects_invalid_consent_class(self) -> None:
        artifact = consent_receipt()
        artifact["consent_class"] = "generic_approval"
        with self.assertRaises(contracts.SchemaValidationError):
            contracts.validate_artifact("consent_receipt", artifact)

    def test_invalid_digest_ref_is_rejected(self) -> None:
        artifact = evidence_ledger()
        artifact["verification_trace_refs"][0]["content_digest"] = "not-sha256"
        with self.assertRaises(contracts.SchemaValidationError):
            contracts.validate_artifact("evidence_ledger", artifact)

    def test_secret_leakage_is_rejected(self) -> None:
        artifact = service_management_handoff()
        artifact["candidate_descriptor"] = {"api_key": "plain-test-value"}
        with self.assertRaises(contracts.RedactionValidationError):
            contracts.validate_artifact("service_management_handoff", artifact)

    def test_service_management_handoff_requires_redacted_status(self) -> None:
        artifact = service_management_handoff()
        artifact["redaction_status"] = "failed"
        with self.assertRaises(contracts.SchemaValidationError):
            contracts.validate_artifact("service_management_handoff", artifact)

    def test_scenario_hidden_state_leak_into_tested_agent_view_is_rejected(self) -> None:
        artifact = requirement_scenario()
        artifact["tested_agent_view"]["user_prompt"] = "Use the hidden_initial_conditions from the test harness."
        with self.assertRaises(contracts.InferentialIsolationError):
            contracts.validate_artifact("requirement_scenario", artifact)

    def test_scenario_evaluator_only_event_visible_to_tested_agent_is_rejected(self) -> None:
        artifact = requirement_scenario()
        artifact["during_test_events"][0]["evaluator_only"] = True
        with self.assertRaises(contracts.InferentialIsolationError):
            contracts.validate_artifact("requirement_scenario", artifact)

    def test_evaluator_verdict_non_pass_requires_evidence(self) -> None:
        artifact = evaluator_verdict("fail")
        artifact["evidence"] = []
        with self.assertRaises(contracts.SchemaValidationError):
            contracts.validate_artifact("evaluator_verdict", artifact)

    def test_evaluator_verdict_failure_requires_failed_requirements(self) -> None:
        artifact = evaluator_verdict("fail")
        artifact["failed_requirements"] = []
        with self.assertRaises(contracts.SchemaValidationError):
            contracts.validate_artifact("evaluator_verdict", artifact)

    def test_governance_reconciliation_is_advisory_only(self) -> None:
        artifact = governance_reconciliation_pack()
        artifact["advisory_only"] = False
        with self.assertRaises(contracts.SchemaValidationError):
            contracts.validate_artifact("governance_reconciliation_pack", artifact)

    def test_unknown_tools_can_fail_closed_in_semantic_policy(self) -> None:
        artifact = semantic_tool_policy()
        artifact["excluded_tool_selectors"].append(
            {"selector_type": "unknown", "value": "missing-risk-metadata", "fail_closed": True}
        )
        contracts.validate_artifact("semantic_tool_policy", artifact)

    def test_artifact_ref_helper_records_snapshot_digest(self) -> None:
        artifact = consent_receipt()
        snapshot = contracts.artifact_ref("run/example/consent-receipt.json", artifact, resolved_at=STAMP)
        self.assertEqual(contracts.artifact_digest(artifact), snapshot["content_digest"])
        contracts.validate_redacted(snapshot)


if __name__ == "__main__":
    unittest.main()
