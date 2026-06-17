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
            "/home/dgk/workspace/context-portal",
        ]:
            self.assertIn(forbidden_surface, self.doc)


if __name__ == "__main__":
    unittest.main()
