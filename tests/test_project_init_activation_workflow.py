from __future__ import annotations

import json
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import control_plane_contextforge_binding as binding
import control_plane_project_state as project_state
import project_init_common as common
import register_project_init_prompt as prompt_registration


def service_descriptor(name: str = "context7") -> dict[str, Any]:
    return {
        "service_family": name,
        "canonical_service": name,
        "service_binding": f"{name}:canonical",
        "codex_alias": common.normalize_codex_alias(name),
        "instantiation_class": "shared_canonical",
        "backend_instance": f"server-instances/{name}",
        "virtual_server": f"{common.normalize_codex_alias(name)}_server",
        "contextforge_readback_status": "matched",
        "gateway": f"{name}-gateway",
        "validation_policy": common.safe_validation_policy(name),
        "non_actions": [
            "do not create a per-project backend",
            "do not mutate user-global Codex config or trust",
        ],
    }


class ProjectInitActivationWorkflowTests(unittest.TestCase):
    def test_discovery_joins_manifests_to_contextforge_readback_without_client_identity(self) -> None:
        readback = [
            {"name": "context7_local_server", "id": "vs-context7"},
            {"name": "web_search_server", "id": "vs-web"},
        ]

        services = common.discover_contextforge_hosted_services(
            project_root="/home/dgk/workspace/context-portal",
            contextforge_servers=readback,
        )
        by_alias = {service["codex_alias"]: service for service in services}

        self.assertIn("context7", by_alias)
        self.assertIn("web_search", by_alias)
        self.assertEqual("matched", by_alias["context7"]["contextforge_readback_status"])
        self.assertEqual("context7:canonical", by_alias["context7"]["service_binding"])
        self.assertEqual("server-instances/context7", by_alias["context7"]["backend_instance"])
        self.assertNotIn("client", by_alias["context7"])
        self.assertIn("do not create a per-project backend", by_alias["context7"]["non_actions"])

    def test_codex_config_plan_writes_only_managed_project_local_wrapper_blocks(self) -> None:
        services = [service_descriptor("context7"), service_descriptor("web-search")]
        plan = binding.plan_project_init_codex_config_write(
            "/home/dgk/workspace/context-portal",
            services,
            existing_text="# existing local config\n",
        )

        self.assertEqual("allow_owned_project_local_write", plan["decision"])
        self.assertEqual(".codex/config.toml", plan["surface"])
        self.assertIn("contextforge_mcp_wrapper.py", plan["next_text"])
        self.assertIn("[mcp_servers.context7]", plan["next_text"])
        self.assertIn("[mcp_servers.web_search]", plan["next_text"])
        self.assertIn("does not write user-global Codex config", plan["non_actions"])

    def test_codex_config_plan_blocks_unmanaged_same_name(self) -> None:
        plan = binding.plan_project_init_codex_config_write(
            "/home/dgk/workspace/context-portal",
            [service_descriptor("context7")],
            existing_text="[mcp_servers.context7]\ncommand = \"npx\"\n",
        )

        self.assertEqual("block", plan["decision"])
        self.assertIn("client_config_conflict", {item["type"] for item in plan["blockers"]})

    def test_state_records_presumed_validation_without_marking_target_client_verified(self) -> None:
        state = project_state.default_state("/home/dgk/workspace/context-portal")
        service = service_descriptor("context7")
        config_plan = binding.plan_project_init_codex_config_write(
            "/home/dgk/workspace/context-portal",
            [service],
            existing_text="",
        )
        validation_plan = binding.build_project_init_validation_plan([service], validation_mode="presume_working")

        next_state = project_state.apply_project_init_activation_to_state(
            state,
            [service],
            target_client="codex",
            client_config_plan=config_plan,
            validation_plan=validation_plan,
            validation_results={},
        )

        self.assertEqual("in_progress", next_state["status"])
        record = next_state["services"]["context7:canonical"]
        self.assertEqual("presumed_working", record["verification_layers"]["target_client"]["status"])
        self.assertFalse(record["evidence"][0]["client_configs_are_service_identities"])
        self.assertEqual("deferred", next_state["open_items"][0]["resolution_state"])
        project_state.validate_state(next_state)

    def test_state_marks_initialized_only_with_target_client_visible_validation(self) -> None:
        state = project_state.default_state("/home/dgk/workspace/context-portal")
        service = service_descriptor("context7")
        config_plan = binding.plan_project_init_codex_config_write(
            "/home/dgk/workspace/context-portal",
            [service],
            existing_text="",
        )
        validation_plan = binding.build_project_init_validation_plan([service], validation_mode="validate_now")

        next_state = project_state.apply_project_init_activation_to_state(
            state,
            [service],
            target_client="codex",
            client_config_plan=config_plan,
            validation_plan=validation_plan,
            validation_results={
                "context7:canonical": {
                    "status": "passed",
                    "target_client_visible": True,
                    "verification_trace_refs": ["contextforge://control-plane/traces/context7-target-client"],
                }
            },
        )

        self.assertEqual("initialized", next_state["status"])
        self.assertEqual("verified", next_state["services"]["context7:canonical"]["provision_status"])
        self.assertEqual("passed", next_state["services"]["context7:canonical"]["verification_layers"]["target_client"]["status"])
        project_state.validate_state(next_state)

    def test_apply_activation_dry_run_does_not_write_files(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            result = binding.apply_project_init_service_activation(
                root,
                [service_descriptor("context7")],
                validation_mode="presume_working",
                approval_scope=binding.PROJECT_INIT_APPROVAL_SCOPE,
                dry_run=True,
            )

            self.assertTrue(result["dry_run"])
            self.assertFalse((root / ".codex/config.toml").exists())
            self.assertFalse(project_state.project_state_path(root).exists())
            self.assertEqual("in_progress", result["planned_state"]["status"])

    def test_project_init_prompt_is_not_serena_only_and_preserves_approval_boundaries(self) -> None:
        text = prompt_registration.PROJECT_INIT_TEXT

        self.assertIn("Which ContextForge services should I activate for this project?", text)
        self.assertIn("discovered shared canonical services and project-scoped options", text)
        self.assertIn("Serena is one project-scoped option in this menu, not the whole flow", text)
        self.assertIn("Validate service functionality now, or record it as presumed working?", text)
        self.assertIn("No user-global config/trust changes", text)
        self.assertIn("Project init may write only project-local .codex/config.toml", text)

    def test_cli_dry_run_uses_scoped_approval_and_selected_services(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp, tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as readback:
            root = Path(tmp).resolve()
            json.dump([{"name": "context7_local_server", "id": "vs-context7"}], readback)
            readback_path = readback.name
        try:
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = binding.main(
                    [
                        "--project-root",
                        str(root),
                        "--service",
                        "context7",
                        "--validation-mode",
                        "presume_working",
                        "--approval-scope",
                        binding.PROJECT_INIT_APPROVAL_SCOPE,
                        "--contextforge-readback-json",
                        readback_path,
                        "--dry-run",
                    ]
                )
            self.assertEqual(0, code)
            self.assertEqual("context7:canonical", json.loads(stdout.getvalue())["selected_service_bindings"][0])
            self.assertFalse((root / ".codex/config.toml").exists())
        finally:
            Path(readback_path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
