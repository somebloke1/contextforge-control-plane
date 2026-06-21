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

    def test_tool_guidance_tag_uses_exact_name_when_contextforge_accepts_it(self) -> None:
        self.assertEqual(
            "openzeppelin-solidity-contracts-solidity-governor",
            guidance.tool_guidance_tag("openzeppelin-solidity-contracts-solidity-governor"),
        )

    def test_tool_guidance_tag_uses_short_key_for_over_limit_names(self) -> None:
        name = "openzeppelin-solidity-contracts-solidity-stablecoin"
        tag = guidance.tool_guidance_tag(name)

        self.assertLessEqual(len(tag), guidance.MAX_CONTEXTFORGE_TAG_LENGTH)
        self.assertTrue(tag.startswith("tool-"))
        self.assertNotEqual(name, tag)

    def test_api_request_rejects_non_public_registry_paths_before_gateway_call(self) -> None:
        with self.assertRaises(guidance.registry_discipline.RegistryMutationDisciplineError):
            guidance.api_request("POST", "/database/registry", token="unused", body={"unsafe": True})

    def test_live_gateway_readback_overrides_static_gateway_ids(self) -> None:
        resolved = guidance.resolve_service_meta(
            {
                "context7-local": {"id": "gateway-context7-target", "name": "context7-local"},
                "mentality": {"id": "gateway-mentality-target", "name": "mentality"},
            }
        )

        self.assertEqual("gateway-context7-target", resolved["context7"]["gateway"])
        self.assertEqual("gateway-mentality-target", resolved["mentality"]["gateway"])
        self.assertEqual(guidance.SERVICE_META["github"]["gateway"], resolved["github"]["gateway"])

    def test_guidance_items_use_resolved_gateway_and_owner(self) -> None:
        tools_by_name = {
            "context7-local-resolve-library-id": {
                "id": "tool-context7",
                "name": "context7-local-resolve-library-id",
                "description": "Resolve library ids.",
            }
        }
        service_meta = guidance.resolve_service_meta(
            {"context7-local": {"id": "gateway-context7-target", "name": "context7-local"}}
        )

        items, _existing = guidance.build_guidance_items(
            tools_by_name,
            resources_by_uri={},
            prompts_by_custom={},
            prompts_by_name={},
            prompt_defs={
                "context7-local-resolve-library-id": guidance.PROMPTS["context7-local-resolve-library-id"]
            },
            service_meta=service_meta,
            owner_email="admin@contextforge-harness.dev",
        )

        self.assertEqual("gateway-context7-target", items[0].resource_body["gateway_id"])
        self.assertEqual("gateway-context7-target", items[0].prompt_body["gatewayId"])
        self.assertEqual("admin@contextforge-harness.dev", items[0].resource_body["owner_email"])
        self.assertEqual("admin@contextforge-harness.dev", items[0].prompt_body["ownerEmail"])

    def test_target_login_prefers_harness_login_endpoint(self) -> None:
        calls: list[str] = []
        original = guidance.target_request

        def fake_request(method: str, base_url: str, path: str, *, token=None, body=None):
            calls.append(path)
            return {"access_token": "target-token"}

        try:
            guidance.target_request = fake_request  # type: ignore[assignment]
            token = guidance.target_login_token("http://127.0.0.1:4445", "admin@example.test", "password")
        finally:
            guidance.target_request = original  # type: ignore[assignment]

        self.assertEqual("target-token", token)
        self.assertEqual(["/auth/login"], calls)


if __name__ == "__main__":
    unittest.main()
