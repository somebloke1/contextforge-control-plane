from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DOC = REPO_ROOT / "docs" / "client-visible-activation-matrix.md"
CLIENT_HARNESS_README = REPO_ROOT / "docker" / "client-harness" / "README.md"


class ClientVisibleActivationMatrixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = DOC.read_text(encoding="utf-8")
        cls.normalized = " ".join(cls.text.split())

    def test_matrix_names_supported_clients_and_surfaces(self) -> None:
        for phrase in [
            "Issue: #89",
            "Codex",
            "Pi",
            "OpenCode",
            "Pi client Docker",
            "OpenCode client Docker",
            "ContextForge dev Docker",
            "legacy/live ContextForge surface is read-only",
        ]:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.normalized)

    def test_matrix_distinguishes_client_observables(self) -> None:
        required_phrases = [
            "Codex project context may show project-init hook/helper guidance",
            "No Codex-style hook banner is expected",
            "Pi should expose shim/helper tools and guidance",
            "OpenCode should receive project-local plugin/helper behavior",
            "Missing a Codex hook banner is expected for Pi",
            "Missing a Codex hook banner is expected for OpenCode",
        ]

        for phrase in required_phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.normalized)

    def test_matrix_defines_readback_paths(self) -> None:
        required_phrases = [
            "codex -C /home/dgk/workspace/cf-controlplane mcp list --json",
            "contextforge-helper",
            "cf_project_init_*",
            "cf_contextforge_pi_readback",
            "guidance lookup",
            "cf_contextforge_pi_validate",
            "opencode mcp list",
            "scripts/opencode_project_init_hook.py",
        ]

        for phrase in required_phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.normalized)

    def test_matrix_preserves_evidence_boundaries(self) -> None:
        required_phrases = [
            "Backend-only ContextForge health or registry readback is insufficient",
            "#62 provides source/test baseline launchers",
            "did not prove ordinary live first-prompt behavior",
            "#3 remains the host Pi global shim install",
            "Claim `Pi active` only from Pi-visible shim/helper/guidance",
            "Claim `OpenCode active` only from OpenCode-visible plugin/helper/MCP readback",
            "state that the source path is prepared and runtime validation remains unproven",
        ]

        for phrase in required_phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.normalized)

    def test_matrix_records_non_actions(self) -> None:
        for phrase in [
            "starting, stopping, rebuilding, or deleting Docker containers",
            "writing user-global Pi or OpenCode config",
            "installing or reloading host Pi extensions",
            "changing Codex hook trust/state",
            "mutating ContextForge services, registry, systemd, processes",
            "helper/project-init approve, apply, recovery",
            ".project/context_forge_state.json",
            "retired predecessor checkout",
        ]:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.text)

    def test_client_harness_readme_links_matrix(self) -> None:
        readme = CLIENT_HARNESS_README.read_text(encoding="utf-8")
        normalized = " ".join(readme.split())

        self.assertIn("../../docs/client-visible-activation-matrix.md", readme)
        self.assertIn("Pi and OpenCode are not expected to show a Codex-style hook banner", normalized)


if __name__ == "__main__":
    unittest.main()
