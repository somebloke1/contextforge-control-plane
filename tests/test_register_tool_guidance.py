from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import register_tool_guidance as guidance


class RegisterToolGuidanceTests(unittest.TestCase):
    def test_all_services_extra_check_ignores_project_init_managed_serena_tools(self) -> None:
        tools = {
            "mentality-governance-list": {"name": "mentality-governance-list"},
            "serena-cf-controlplane-d46fe58a2a20-activate-project": {
                "name": "serena-cf-controlplane-d46fe58a2a20-activate-project"
            },
            "serena-cf-controlplane-d46fe58a2a20-search-for-pattern": {
                "name": "serena-cf-controlplane-d46fe58a2a20-search-for-pattern"
            },
        }

        self.assertEqual([], guidance.unmapped_extra_tools(tools))

    def test_all_services_extra_check_keeps_unknown_non_serena_tools(self) -> None:
        tools = {
            "ssh-tmux-cleanup-dead-sessions": {"name": "ssh-tmux-cleanup-dead-sessions"},
            "unknown-service-new-tool": {"name": "unknown-service-new-tool"},
        }

        self.assertEqual(["unknown-service-new-tool"], guidance.unmapped_extra_tools(tools))

    def test_ssh_tmux_cleanup_dead_sessions_has_guidance(self) -> None:
        self.assertIn("ssh-tmux-cleanup-dead-sessions", guidance.PROMPTS)
        prompt_name, template = guidance.PROMPTS["ssh-tmux-cleanup-dead-sessions"]
        self.assertEqual("ssh_tmux_cleanup_dead_sessions", prompt_name)
        self.assertIn("dry_run", template)

    def test_api_request_rejects_non_public_registry_paths_before_gateway_call(self) -> None:
        with self.assertRaises(guidance.registry_discipline.RegistryMutationDisciplineError):
            guidance.api_request("POST", "/database/registry", token="unused", body={"unsafe": True})


if __name__ == "__main__":
    unittest.main()
