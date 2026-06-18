from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUARDRAILS = ROOT / "docs" / "readiness-claim-guardrails.md"
MATRIX = ROOT / "docs" / "client-visible-activation-matrix.md"
SAFE_PROBES = ROOT / "docs" / "safe-client-visible-validation-probes.md"
SURFACE_LABELS = ROOT / "docs" / "evidence-surface-labels.md"


class ReadinessClaimGuardrailTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.doc = GUARDRAILS.read_text(encoding="utf-8")
        cls.normalized = " ".join(cls.doc.split())
        cls.matrix = MATRIX.read_text(encoding="utf-8")
        cls.safe_probes = SAFE_PROBES.read_text(encoding="utf-8")
        cls.surface_labels = SURFACE_LABELS.read_text(encoding="utf-8")

    def test_guardrail_declares_issue_and_non_mutating_scope(self) -> None:
        for phrase in [
            "Issue: #161",
            "source/docs/tests contract",
            "does not validate runtime behavior",
            "does not approve service changes",
            "hook trust/state changes",
            ".project/context_forge_state.json",
        ]:
            self.assertIn(phrase, self.doc)

        for phrase in [
            "does not approve runtime/client validation",
            "Docker/container start/stop/rebuild",
        ]:
            self.assertIn(phrase, self.normalized)

    def test_guardrail_names_required_status_vocabulary(self) -> None:
        for status in [
            "`planned`",
            "`created`",
            "`pending_restart`",
            "`initialized`",
            "`source_ready`",
            "`backend_ready`",
            "`contextforge_ready`",
            "`target_client_ready`",
            "`presumed_working`",
            "`verified`",
            "`degraded`",
            "`failed`",
            "`removed`",
        ]:
            with self.subTest(status=status):
                self.assertIn(status, self.doc)

    def test_guardrail_preserves_layer_ordering(self) -> None:
        for earlier, later in [
            ("`source_ready`", "`backend_ready`"),
            ("`backend_ready`", "`contextforge_ready`"),
            ("`contextforge_ready`", "`target_client_ready`"),
            ("`target_client_ready`", "`verified`"),
        ]:
            with self.subTest(earlier=earlier, later=later):
                self.assertLess(self.doc.index(earlier), self.doc.index(later))

        self.assertIn("A source-only PR should usually stop at\n`source_ready`.", self.doc)
        self.assertIn("A target-client claim must not skip the\nclient-visible layer.", self.doc)

    def test_guardrail_blocks_common_overclaims(self) -> None:
        for phrase in [
            "`verified` from `source_ready`",
            "`target_client_ready` from `contextforge_ready`",
            "`contextforge_ready` from `backend_ready`",
            "`backend_ready` from tracked source or Dockerfile presence",
            "host Pi readiness from Pi client Docker proof",
            "Pi or OpenCode readiness from a Codex hook banner",
            "runtime readiness from roadmap, issue, PR, or Project #6 state",
            "validation success from a skipped probe",
        ]:
            self.assertIn(phrase, self.doc)

    def test_claim_template_requires_scope_evidence_and_missing_stronger_layer(self) -> None:
        for phrase in [
            "<object> is <status> for <surface/scope> based on <evidence>",
            "It is not\n<stronger-status> because <missing proof or boundary>.",
            "object or service name",
            "layer/status",
            "exercised surface",
            "missing stronger layer",
            "non-actions and boundaries",
        ]:
            self.assertIn(phrase, self.doc)

    def test_surface_label_standard_names_canonical_trace_surfaces(self) -> None:
        self.assertIn("docs/evidence-surface-labels.md", self.doc)
        self.assertIn("Issue: #158", self.surface_labels)
        for label in [
            "`legacy_live_read_only`",
            "`contextforge_dev_docker`",
            "`pi_client_docker`",
            "`opencode_client_docker`",
            "`local_source`",
            "`target_client`",
            "`generated_run_evidence`",
        ]:
            with self.subTest(label=label):
                self.assertIn(label, self.surface_labels)

    def test_existing_validation_docs_link_to_guardrails(self) -> None:
        for text in [self.matrix, self.safe_probes]:
            with self.subTest(doc=text[:40]):
                self.assertIn("docs/readiness-claim-guardrails.md", text)
                self.assertIn("source_ready", text)
                self.assertIn("target_client_ready", text)


if __name__ == "__main__":
    unittest.main()
