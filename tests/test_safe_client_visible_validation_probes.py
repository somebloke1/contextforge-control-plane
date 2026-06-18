from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/safe-client-visible-validation-probes.md"
OPEN_QUESTIONS = ROOT / "OPEN_QUESTIONS.md"
MATRIX = ROOT / "docs/client-visible-activation-matrix.md"


class SafeClientVisibleValidationProbeCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.doc = DOC.read_text(encoding="utf-8")
        cls.normalized = " ".join(cls.doc.split())
        cls.normalized_lower = cls.normalized.lower()

    def test_catalog_links_issue_and_open_question(self) -> None:
        self.assertIn("Issue: #97", self.doc)
        self.assertIn("Open question: `oq-20260531-0001`", self.doc)
        self.assertIn("safe default probe payload", OPEN_QUESTIONS.read_text(encoding="utf-8"))
        self.assertIn("docs/safe-client-visible-validation-probes.md", MATRIX.read_text(encoding="utf-8"))

    def test_catalog_distinguishes_client_surfaces(self) -> None:
        for phrase in [
            "Codex-visible MCP list/call proof",
            "Pi-visible shim/helper/guidance",
            "OpenCode-visible plugin/helper/MCP behavior",
            "Host Pi extension/shim readback",
            "direct backend checks",
            "Codex hook banners",
            "Pi client Docker evidence or source fixture evidence alone",
        ]:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.normalized)
        self.assertIn("not sufficient", self.normalized_lower)

    def test_catalog_classifies_known_safe_probes(self) -> None:
        for service in ["context7", "mentality", "ssh-tmux"]:
            with self.subTest(service=service):
                self.assertIn(service, self.doc)

        for phrase in [
            "`known_safe_probe`",
            "small read-only documentation lookup",
            "Target-client list/read proof for governance records only",
            "Target-client list-sessions or session metadata readback only",
            "Decision writes",
            "Opening sessions",
            "sending commands",
            "shell process mutation",
        ]:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.doc)

    def test_catalog_classifies_conditional_and_skipped_probes(self) -> None:
        for service in [
            "OpenZeppelin Solidity Contracts",
            "web-search",
            "Exa Search",
            "GitHub",
            "Playwright",
            "Serena/project-scoped services",
            "Pi/OpenCode activation helpers",
            "Any unlisted service",
        ]:
            with self.subTest(service=service):
                self.assertIn(service, self.doc)

        for phrase in [
            "`conditional_probe`",
            "`skip_until_probe_exists`",
            "credentials, cost, environment, target resource, or side effects",
            "credential scope confirmed",
            "controlled fixture page",
            "must remain skipped or presumed-working",
            "another service's probe",
        ]:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.normalized)

    def test_claim_rules_preserve_no_fake_validation_policy(self) -> None:
        for phrase in [
            "Record `validated` only after the exact target client lists",
            "Record `skipped` when no safe payload exists",
            "Record `presumed_working` only when the operator explicitly chooses that state",
            "no target-client proof is claimed",
            "Keep credentials, bearer tokens, OAuth state, trust tokens",
            "one service, one client surface, one safe payload",
            "does not approve live runtime/client validation",
            ".project/context_forge_state.json",
            "retired legacy checkout mutation",
        ]:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.normalized)


if __name__ == "__main__":
    unittest.main()
