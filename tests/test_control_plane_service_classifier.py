from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import control_plane_contracts as contracts
import control_plane_service_classifier as classifier


PROJECT_ROOT = "/home/dgk/workspace/context-portal"


def descriptor(
    service_family: str = "context7",
    *,
    canonical_service: str | None = None,
    instantiation_class: str = "shared_canonical",
    native_transports: list[str] | None = None,
    scope: dict[str, object] | None = None,
    name: str | None = None,
) -> dict[str, object]:
    service = canonical_service or service_family
    return {
        "service_family": service_family,
        "canonical_service": service,
        "service": service,
        "name": name or f"client_alias_{service}",
        "client_config_names": [f"codex_{service}_alias", f"claude_{service}_alias"],
        "slug": service.replace("_", "-"),
        "instantiation_class": instantiation_class,
        "native_transports": native_transports or ["streamable_http", "sse"],
        "scope": scope or {},
        "contextforge": {
            "gateway": {"name": f"{service}-gateway"},
            "virtual_server": {"name": f"{service}-server"},
        },
        "registration": {"status": "registered"},
    }


class ControlPlaneServiceClassifierTests(unittest.TestCase):
    def assert_valid_contract(self, result: dict[str, object]) -> dict[str, object]:
        contract = result["contract_card_draft"]
        self.assertIsInstance(contract, dict)
        contracts.validate_artifact("service_binding_contract_card", contract)  # type: ignore[arg-type]
        return contract  # type: ignore[return-value]

    def test_shared_canonical_emits_capsule_and_project_non_actions(self) -> None:
        result = classifier.classify_service_binding(descriptor("context7"), project_root=PROJECT_ROOT)

        self.assertEqual("classified", result["status"])
        self.assertEqual("shared_canonical", result["instantiation_class"])
        self.assertEqual("context7:canonical", result["service_binding"])
        self.assertIn("no per-project backend", result["non_actions"])
        self.assertIn("no per-project server-instance directory", result["non_actions"])

        contract = self.assert_valid_contract(result)
        self.assertEqual("shared_canonical", contract["instantiation_class"])
        self.assertEqual({"mode": "availability_binding_only"}, contract["project_scope"])

        capsule = result["shared_service_capability_capsule"]
        self.assertIsInstance(capsule, dict)
        contracts.validate_artifact("shared_service_capability_capsule", capsule)  # type: ignore[arg-type]
        self.assertEqual(
            {
                "new_backend",
                "new_gateway",
                "new_bridge",
                "new_wrapper",
                "new_port",
                "new_unit",
                "server_instance_directory",
                "catalog_mutation",
            },
            set(capsule["forbidden_project_init_effects"]),  # type: ignore[index]
        )

    def test_instance_per_project_classifies_project_backend(self) -> None:
        result = classifier.classify_service_binding(
            descriptor(
                "serena",
                instantiation_class="instance_per_project",
                native_transports=["stdio"],
                scope={"scope_type": "single_workspace_code_intelligence", "workspace_root": PROJECT_ROOT},
            ),
            project_root=PROJECT_ROOT,
        )

        contract = self.assert_valid_contract(result)
        self.assertEqual("instance_per_project", result["instantiation_class"])
        self.assertEqual("stdio_to_http_sse", result["transport_profile"]["bridge_mode"])  # type: ignore[index]
        self.assertIsNone(result["shared_service_capability_capsule"])
        self.assertIn("service_provision", contract["required_consent_classes"])
        self.assertEqual(PROJECT_ROOT, contract["project_scope"]["project_root"])

    def test_static_repo_local_keeps_repo_governance_authority(self) -> None:
        result = classifier.classify_service_binding(
            descriptor(
                "mentality",
                instantiation_class="static_repo_local",
                scope={"scope_type": "repo_governance", "workspace_root": PROJECT_ROOT},
            ),
            project_root=PROJECT_ROOT,
        )

        contract = self.assert_valid_contract(result)
        self.assertEqual("static_repo_local", contract["instantiation_class"])
        self.assertIn("do not let client-local memory supersede governance ledgers", result["non_actions"])
        self.assertEqual(PROJECT_ROOT, contract["project_scope"]["project_root"])

    def test_caller_and_session_scoped_services_do_not_claim_project_ownership(self) -> None:
        for instantiation_class in ("caller_scoped", "session_scoped"):
            with self.subTest(instantiation_class=instantiation_class):
                result = classifier.classify_service_binding(
                    descriptor(
                        "ssh-tmux",
                        instantiation_class=instantiation_class,
                        scope={"authority": "active shell", f"{instantiation_class.split('_')[0]}_scope": True},
                    ),
                    project_root=PROJECT_ROOT,
                )

                contract = self.assert_valid_contract(result)
                self.assertEqual(instantiation_class, contract["instantiation_class"])
                self.assertIsNotNone(contract["caller_or_session_scope"])
                self.assertIn("do not claim durable project ownership of the live caller/session", result["non_actions"])
                self.assertFalse(result["mutation_allowed"])

    def test_credential_and_resource_scoped_boundaries_are_explicit(self) -> None:
        cases = [
            (
                "credential_scoped",
                {"credential_scope": {"scope": "github-installation"}},
                "credential_scope",
                {"scope": "github-installation"},
            ),
            (
                "resource_scoped",
                {"resource_scope": {"scope": "repo-allowlist"}},
                "resource_scope",
                {"scope": "repo-allowlist"},
            ),
        ]
        for instantiation_class, scope, field, expected in cases:
            with self.subTest(instantiation_class=instantiation_class):
                result = classifier.classify_service_binding(
                    descriptor("github", instantiation_class=instantiation_class, scope=scope),
                    project_root=PROJECT_ROOT,
                )
                contract = self.assert_valid_contract(result)
                self.assertEqual(instantiation_class, contract["instantiation_class"])
                self.assertEqual(expected, contract[field])
                self.assertIn("do not duplicate backend for client alias or project name convenience", result["non_actions"])

    def test_project_scoped_shared_backend_requires_isolation_then_classifies(self) -> None:
        missing = classifier.classify_service_binding(
            descriptor("project-index", instantiation_class="project_scoped_shared_backend"),
            project_root=PROJECT_ROOT,
        )

        self.assertEqual("blocked", missing["status"])
        self.assertIn("isolation_required", {blocker["type"] for blocker in missing["blockers"]})  # type: ignore[index]
        self.assertIsNone(missing["contract_card_draft"])

        result = classifier.classify_service_binding(
            descriptor(
                "project-index",
                instantiation_class="project_scoped_shared_backend",
                scope={"isolation_mechanism": "virtual_server_root_allowlist", "workspace_root": PROJECT_ROOT},
            ),
            project_root=PROJECT_ROOT,
        )

        contract = self.assert_valid_contract(result)
        self.assertEqual("project_scoped_shared_backend", result["instantiation_class"])
        self.assertEqual("virtual_server_root_allowlist", contract["project_scope"]["isolation_mechanism"])
        self.assertIn("prove project isolation mechanism with allowed and denied operations", result["verification_requirements"])

    def test_candidate_backend_emits_handoff_not_durable_service_record(self) -> None:
        result = classifier.classify_service_binding(
            {
                "candidate": True,
                "service_family": "invoiceapi",
                "canonical_service": "invoiceapi",
                "backend": {"transport": "stdio", "command": "invoice-mcp"},
                "api_key": "plain-test-value",
                "scope": {"runtime_scope": "host", "resource_scope": {"scope": "invoices"}},
            },
            project_root=PROJECT_ROOT,
        )

        self.assertEqual("handoff_required", result["status"])
        self.assertFalse(result["durable_project_state_record_allowed"])
        self.assertIsNone(result["contract_card_draft"])
        handoff = result["service_management_handoff"]
        self.assertIsInstance(handoff, dict)
        contracts.validate_artifact("service_management_handoff", handoff)  # type: ignore[arg-type]
        self.assertEqual("candidate_or_uncataloged_backend", handoff["suspected_instantiation_class"])  # type: ignore[index]
        self.assertEqual("<redacted>", handoff["candidate_descriptor"]["api_key"])  # type: ignore[index]
        self.assertIn("project_state_service_record", handoff["forbidden_under_current_approval"])  # type: ignore[index]

    def test_ambiguous_classification_blocks_mutation_without_guessing(self) -> None:
        result = classifier.classify_service_binding({"service_family": "unknown-docs"}, project_root=PROJECT_ROOT)

        self.assertEqual("blocked", result["status"])
        self.assertFalse(result["mutation_allowed"])
        self.assertIsNone(result["contract_card_draft"])
        self.assertIn("instantiation_class_ambiguous", {blocker["type"] for blocker in result["blockers"]})  # type: ignore[index]
        self.assertIn("do not mutate project state", result["non_actions"])

    def test_client_alias_is_ignored_for_identity(self) -> None:
        result = classifier.classify_service_binding(
            descriptor(
                "context7",
                canonical_service="context7",
                instantiation_class="shared_canonical",
                name="codex_context7_alias",
            ),
            project_root=PROJECT_ROOT,
        )

        self.assertEqual("context7", result["service_family"])
        self.assertEqual("context7", result["canonical_service"])
        self.assertEqual("context7:canonical", result["service_binding"])
        self.assertIn("codex_context7_alias", result["identity"]["client_aliases_ignored"])  # type: ignore[index]
        self.assertNotEqual("codex_context7_alias:canonical", result["service_binding"])

    def test_client_named_service_only_does_not_become_canonical_identity(self) -> None:
        result = classifier.classify_service_binding(
            {
                "service": "codex_context7",
                "instantiation_class": "shared_canonical",
                "client_config_names": ["codex_context7"],
            },
            project_root=PROJECT_ROOT,
        )

        self.assertEqual("blocked", result["status"])
        self.assertFalse(result["mutation_allowed"])
        self.assertIsNone(result["service_family"])
        self.assertIsNone(result["canonical_service"])
        self.assertIn("canonical_identity_required", {blocker["type"] for blocker in result["blockers"]})  # type: ignore[index]

    def test_client_named_service_binding_is_rejected(self) -> None:
        result = classifier.classify_service_binding(
            descriptor(
                "context7",
                canonical_service="context7",
                instantiation_class="shared_canonical",
                name="codex_context7_alias",
            )
            | {"service_binding": "codex_context7:canonical"},
            project_root=PROJECT_ROOT,
        )

        self.assertEqual("blocked", result["status"])
        self.assertFalse(result["mutation_allowed"])
        self.assertIsNone(result["contract_card_draft"])
        self.assertIn("service_binding_not_canonical", {blocker["type"] for blocker in result["blockers"]})  # type: ignore[index]

    def test_native_transport_preservation_and_missing_side_bridges_only(self) -> None:
        native = classifier.classify_service_binding(
            descriptor("docs", instantiation_class="shared_canonical", native_transports=["streamable_http", "sse"]),
            project_root=PROJECT_ROOT,
        )
        self.assertEqual("none", native["transport_profile"]["bridge_mode"])  # type: ignore[index]
        self.assertIsNone(native["transport_profile"]["package_bridge_ref"])  # type: ignore[index]
        self.assertIn("do not create bridge or wrapper for native HTTP/SSE access", native["non_actions"])

        http_only = classifier.classify_service_binding(
            descriptor("http-docs", instantiation_class="shared_canonical", native_transports=["streamable_http"]),
            project_root=PROJECT_ROOT,
        )
        self.assertEqual("http_to_sse", http_only["transport_profile"]["bridge_mode"])  # type: ignore[index]
        self.assertIn("bridge only the missing SSE side", http_only["transport_profile"]["forbidden_bridge_effects"])  # type: ignore[index]

        sse_only = classifier.classify_service_binding(
            descriptor("sse-docs", instantiation_class="shared_canonical", native_transports=["sse"]),
            project_root=PROJECT_ROOT,
        )
        self.assertEqual("sse_to_http", sse_only["transport_profile"]["bridge_mode"])  # type: ignore[index]
        self.assertIn("bridge only the missing streamable HTTP side", sse_only["transport_profile"]["forbidden_bridge_effects"])  # type: ignore[index]


if __name__ == "__main__":
    unittest.main()
