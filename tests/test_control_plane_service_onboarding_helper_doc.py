from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/initiatives/contextforge-control-plane/service-onboarding-helper.md"


class ServiceOnboardingHelperDocTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.doc = DOC.read_text(encoding="utf-8")

    def test_doc_records_stateful_dialogue_flow(self) -> None:
        for state in [
            "`intake`",
            "`source_discovery`",
            "`feasibility_review`",
            "`classification`",
            "`strategy_selection`",
            "`footprint_plan`",
            "`approval_gate`",
            "`handoff`",
        ]:
            self.assertIn(state, self.doc)

        self.assertIn("stateful", self.doc)
        self.assertIn("resumable", self.doc)
        self.assertIn("operator and the model", self.doc)

    def test_doc_locks_required_classification_dimensions(self) -> None:
        for dimension in [
            "### `plan_type`",
            "### `localization_type`",
            "### `functional_type`",
            "### `transport_type`",
            "### `state_type`",
            "### `approval_type`",
        ]:
            self.assertIn(dimension, self.doc)

        for value in [
            "`source_only_scaffolding`",
            "`dev_docker_proof`",
            "`project_scoped`",
            "`client_local_session_scoped`",
            "`code_intelligence`",
            "`service_management`",
            "`streamable_http`",
            "`bridge_required`",
            "`project_metadata`",
            "`credential_state`",
            "`live_runtime_service`",
            "`destructive_cleanup`",
        ]:
            self.assertIn(value, self.doc)

    def test_doc_maps_services_to_controlplane_paradigms(self) -> None:
        for paradigm in [
            "Direct native registration",
            "Package-provided bridge/transceiver",
            "Dev Docker sidecar",
            "Project-scoped backend",
            "Credential-scoped backend",
            "Client-local or session-scoped backend",
            "Gateway-image exception",
        ]:
            self.assertIn(paradigm, self.doc)

        self.assertIn("One backend or transceiver per project", self.doc)
        self.assertIn("One backend or transceiver per client-local state boundary", self.doc)
        self.assertIn("not inside the gateway image by default", self.doc)

    def test_doc_requires_reviewable_onboarding_record(self) -> None:
        for phrase in [
            "candidate service name and operator goal",
            "source evidence and unresolved source questions",
            "feasibility verdict and confidence",
            "chosen integration paradigm and rejected alternatives",
            "server-instances/<service-slug>/",
            "required files, scripts, docs, tests, fixtures, Docker surfaces",
            "non-actions already preserved",
            "residual risks, retirement conditions, and next issue/PR steps",
        ]:
            self.assertIn(phrase, self.doc)

    def test_doc_records_pre_runtime_workflow_gate_contract(self) -> None:
        for phrase in [
            "Pre-Runtime Workflow Gate",
            "`pre_runtime_workflow_gate`",
            "`runtime_work_allowed: false`",
            "source evidence, canonical service identity",
            "scope/locality, transport, credential boundary",
            "state footprint, approval",
            "required pre-runtime evidence",
            "planned validation probe layers",
            "native transport contract readback",
            "bridge transport smoke plan",
            "credential scope negative readback",
            "client session scope probe",
            "only plans probes",
            "does not call ContextForge",
            "run Docker",
            "execute validation",
        ]:
            self.assertIn(phrase, self.doc)

    def test_doc_preserves_non_mutation_default(self) -> None:
        for forbidden_surface in [
            "register services",
            "start or stop containers",
            "mutate systemd units",
            "write global/client config",
            "copy secrets",
            "change trust state",
            "clean registry records",
            "/home/dgk/workspace/legacy-controlplane-archive",
        ]:
            self.assertIn(forbidden_surface, self.doc)

    def test_doc_records_fixture_coverage_for_scoped_service_classes(self) -> None:
        for case_name in [
            "`shared_stdio_bridge_dev_docker_gate`",
            "`github_credential_scoped_registry_gate`",
            "`ssh_tmux_client_session_local_bridge`",
            "`openzeppelin_remote_native_hosted_source_only`",
            "`serena_source_only_project_scoped_abeyant_provisioning`",
        ]:
            self.assertIn(case_name, self.doc)

        for phrase in [
            "stock bridge/transceiver command",
            "credential, account, tenant, token, or installation boundary",
            "client-local state, live session, caller identity, or process authority",
            "without claiming durable project ownership",
            "without claiming live",
            "generated-code audit",
            "deployment readiness",
            "registry",
        ]:
            self.assertIn(phrase, self.doc)

    def test_doc_records_serena_source_only_abeyant_provisioning_fixture(self) -> None:
        for phrase in [
            "backend exists in the repository but provisioning is still abeyant.",
            "hard-require the same Serena",
            "later approved runtime turn",
        ]:
            self.assertIn(phrase, self.doc)

    def test_doc_records_source_only_resume_envelope(self) -> None:
        for phrase in [
            "Source-Only Resume Envelope",
            "--previous-record",
            "--session-id",
            "`dialogue_session`",
            "`turn_index`",
            "`state_history`",
            "`answered_questions`",
            "`decision_log`",
            "`storage_mode: stdout_only`",
            "`write_persistence: false`",
            "introducing hidden local files",
            "Long-running helper behavior",
        ]:
            self.assertIn(phrase, self.doc)

    def test_doc_records_local_ignored_session_store_boundaries(self) -> None:
        for phrase in [
            "Local Ignored Session Store",
            "run/service-onboarding-sessions/",
            "--resume-session",
            "--save-session",
            "`storage_mode: local_ignored_session_file`",
            "`write_persistence: true`",
            "`session_record_path`",
            "project-local ignored `run/` tree",
            "the helper remains stdout-only",
            "not a daemon",
            "service runtime",
            "Docker state",
            "client installation",
            "secret store",
            "approval bypass",
        ]:
            self.assertIn(phrase, self.doc)

    def test_doc_records_session_status_readback_contract(self) -> None:
        for phrase in [
            "Session Status Readback",
            "--session-status",
            "without a descriptor",
            "without rewriting the",
            "`turn_index`",
            "known and open classification dimensions",
            "primary and secondary integration paradigms",
            "approval requirement and required approval types",
            "compact `pre_runtime_workflow_gate` state",
            "planned validation probe layers",
            "answered questions, next questions, next resume inputs",
            "`mutation_allowed: false`",
            "cannot be combined with descriptor input",
            "previous-record input",
            "session resume input",
            "`--save-session`",
        ]:
            self.assertIn(phrase, self.doc)

    def test_doc_records_session_list_readback_contract(self) -> None:
        for phrase in [
            "--list-sessions",
            "without descriptor input",
            "without rewriting any session record",
            "`service_onboarding_session_list`",
            "compact status summaries",
            "sorted by saved session record name",
            "absent session directory returns an empty list",
            "single-session status input",
            "`--save-session`",
        ]:
            self.assertIn(phrase, self.doc)

    def test_doc_records_session_template_readback_contract(self) -> None:
        for phrase in [
            "--session-template",
            "`service_onboarding_resume_template`",
            "compact session context",
            "next questions",
            "descriptor patch scaffold",
            "missing source evidence",
            "classification values",
            "feasibility notes",
            "footprint fields",
            "missing pre-runtime gate inputs",
            "credential boundary",
            "validation probe plan",
            "rerun guidance for `--resume-session`",
            "does not rewrite the session",
            "list input",
            "`--save-session`",
        ]:
            self.assertIn(phrase, self.doc)

    def test_doc_records_research_packet_readback_contract(self) -> None:
        for phrase in [
            "--research-packet",
            "`service_onboarding_research_packet`",
            "source-level claim boundary",
            "seed leads and research-agent instruction",
            "allowed read-only actions and forbidden mutations",
            "descriptor patch contract",
            "final stepwise narrative requirement",
            "`backend_ready`",
            "`contextforge_ready`",
            "`target_client_ready`",
            "semantic acceptance",
        ]:
            self.assertIn(phrase, self.doc)

    def test_doc_records_ordered_onboarding_development_foil_ladder(self) -> None:
        expected_order = [
            "`time` - stateless baseline",
            "`fetch` - basic network I/O",
            "`sequentialthinking` - state persistence",
            "`filesystem` - local security constraints",
            "`sqlite` - structured data handling",
            "`kubernetes` - dynamic massive schemas and advanced auth",
            "`docker` - system daemon mounting and external process orchestration",
        ]
        positions = [self.doc.index(item) for item in expected_order]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("development foils", self.doc)
        self.assertIn("This is not a", self.doc)
        self.assertIn("canonical post-development service set", self.doc)
        self.assertIn("`time` must be completed before `fetch`", self.doc)
        self.assertIn("begins.", self.doc)
        for url in [
            "github.com/modelcontextprotocol/servers/tree/main/src/time",
            "github.com/modelcontextprotocol/servers/tree/main/src/fetch",
            "github.com/modelcontextprotocol/servers/tree/main/src/sequentialthinking",
            "github.com/modelcontextprotocol/servers/tree/main/src/filesystem",
            "github.com/modelcontextprotocol/servers/tree/main/src/sqlite",
            "github.com/feiskyer/mcp-kubernetes-server",
            "github.com/ckreiling/mcp-server-docker",
        ]:
            self.assertIn(url, self.doc)

    def test_doc_records_pre_implementation_decision_gate(self) -> None:
        for phrase in [
            "Before implementation or runtime/client work",
            "present them methodically for user",
            "canonical service identity",
            "backend home",
            "transport and bridge strategy",
            "scope and locality",
            "state footprint",
            "credential and auth boundary",
            "ContextForge registration plan",
            "client exposure plan",
            "reset and proof strategy",
            "rollback and cleanup",
        ]:
            self.assertIn(phrase, self.doc)


if __name__ == "__main__":
    unittest.main()
