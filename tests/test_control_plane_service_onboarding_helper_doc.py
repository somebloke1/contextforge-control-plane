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
            "answered questions, next questions, next resume inputs",
            "`mutation_allowed: false`",
            "cannot be combined with descriptor input",
            "previous-record input",
            "session resume input",
            "`--save-session`",
        ]:
            self.assertIn(phrase, self.doc)


if __name__ == "__main__":
    unittest.main()
