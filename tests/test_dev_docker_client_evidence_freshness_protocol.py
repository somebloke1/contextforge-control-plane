from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DOC = REPO_ROOT / "docs" / "dev-docker-client-evidence-freshness-protocol.md"


class DevDockerClientEvidenceFreshnessProtocolTests(unittest.TestCase):
    def test_protocol_distinguishes_all_four_contextforge_surfaces(self) -> None:
        text = DOC.read_text(encoding="utf-8")

        required_phrases = [
            "Legacy/live ContextForge",
            "ContextForge dev Docker",
            "Pi client Docker",
            "OpenCode client Docker",
            "Do not cite legacy/live ContextForge evidence as proof",
        ]

        for phrase in required_phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_protocol_covers_issue_58_refresh_acceptance(self) -> None:
        text = DOC.read_text(encoding="utf-8")

        required_phrases = [
            "gateway `health`, `ready`, version, admin login/readback",
            "`mentality-transceiver`",
            "`mentality_dev_docker_server`",
            "short-lived scoped probe tokens",
            "prove OpenCode through its remote MCP client surface",
            "`opencode mcp list` connection evidence",
            "known-safe governance list/read call",
            "same OpenCode client Docker run",
            "prove Pi through the extension/shim validation path",
            "local Qwen/llama.cpp as configuration",
            "exact advertised model",
            "mark the evidence `stale` when they differ",
        ]

        for phrase in required_phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_protocol_defines_local_and_promoted_evidence_rules(self) -> None:
        text = DOC.read_text(encoding="utf-8")

        required_phrases = [
            "docker/contextforge-harness/evidence/",
            "docker/client-harness/evidence/",
            "Tracked promotion is allowed only for sanitized summaries",
            "no raw token values",
            "`current`",
            "`historical`",
            "`comparison-only`",
            "`stale`",
            "`unverified`",
            "Empty files",
            "token revocation evidence",
        ]

        for phrase in required_phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_harness_readmes_link_to_protocol(self) -> None:
        link = "../../docs/dev-docker-client-evidence-freshness-protocol.md"

        for path in [
            REPO_ROOT / "docker" / "contextforge-harness" / "README.md",
            REPO_ROOT / "docker" / "client-harness" / "README.md",
        ]:
            with self.subTest(path=str(path)):
                self.assertIn(link, path.read_text(encoding="utf-8"))

    def test_protocol_preserves_client_visible_proof_boundary(self) -> None:
        text = DOC.read_text(encoding="utf-8")

        self.assertIn("Backend-only proof is insufficient for client claims", text)
        self.assertIn("target-client-visible proof", text)
        self.assertIn("matching client Docker surface", text)


if __name__ == "__main__":
    unittest.main()
