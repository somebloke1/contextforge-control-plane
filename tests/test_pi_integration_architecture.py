from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DOC = REPO_ROOT / "docs" / "pi-contextforge-integration-architecture.md"


class PiIntegrationArchitectureDocTests(unittest.TestCase):
    def test_doc_preserves_pi_shim_api_transceiver_boundaries(self) -> None:
        text = DOC.read_text(encoding="utf-8")
        normalized = " ".join(text.split())

        required_phrases = [
            "global TypeScript extension shim",
            "does not use a project-local MCP config surface",
            "Ordinary project activation must not generate a fake Pi MCP config",
            "Direct ContextForge API calls are appropriate",
            "Direct API use is not, by itself, a Pi tool integration strategy",
            "python -m mcpgateway.translate --stdio",
            "development Docker surface",
            "writing `~/.pi/agent/extensions/`",
            "Pi `/reload`",
            "legacy/live ContextForge surface remains read-only",
        ]

        for phrase in required_phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, normalized)

    def test_doc_identifies_live_pi_acceptance_gate(self) -> None:
        text = DOC.read_text(encoding="utf-8")
        normalized = " ".join(text.split())

        self.assertIn("source checks are insufficient", normalized)
        self.assertIn("approved install/upgrade", normalized)
        self.assertIn("Pi-visible validation/readback", normalized)


if __name__ == "__main__":
    unittest.main()
