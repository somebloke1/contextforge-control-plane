from __future__ import annotations

import json
import contextlib
import io
import inspect
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import control_plane_contextforge_binding as binding
import control_plane_authorization as authorization
import control_plane_project_init_helper as helper
import contextforge_helper_mcp
import control_plane_project_state as project_state
import manage_pi_global_shim
import manage_serena_project_instance as serena_manager
import pi_contextforge_shim_dry_run
import pi_project_init_helper_cli
import project_init_common as common
import register_project_init_prompt as prompt_registration


CONSENT_REFS = [
    "run/consent-receipts/receipt-project-local-config.json",
    "run/consent-receipts/receipt-project-state.json",
]


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


def pi_safe_probe_validation(tool_name: str = "cf_context7_s123__context7-local-resolve-library-id") -> dict[str, Any]:
    return {
        "status": "passed",
        "target_client_visible": True,
        "target_client": "pi",
        "proof_kind": "pi_safe_probe_result",
        "safe_probe_result": "passed",
        "safe_probe_id": "resolve-library-id",
        "tool_name": tool_name,
        "result_summary": "resolved python standard library documentation through Pi-visible ContextForge tool",
        "verification_trace_refs": [f"pi://contextforge-global-shim/tools/{tool_name}"],
    }


def context7_safe_probe_validation(target_client: str = "codex") -> dict[str, Any]:
    return common.build_safe_probe_validation_result(
        "context7",
        target_client=target_client,
        tool_name="context7_context7-local-resolve-library-id",
        verification_trace_refs=[f"contextforge://control-plane/traces/context7-{target_client}-target-client"],
        result_summary="resolved python standard library documentation through target-client-visible context7 tool",
    )


def record_pi_reload(root: Path, *, validation_mode: str | None = None) -> dict[str, Any]:
    return helper.record_project_init_client_reload(project_root=root, client_type="pi", validation_mode=validation_mode)


def record_codex_new_session(root: Path, *, validation_mode: str | None = None) -> dict[str, Any]:
    return helper.record_project_init_client_reload(project_root=root, client_type="codex", validation_mode=validation_mode)


def serena_descriptor() -> dict[str, Any]:
    service = service_descriptor("serena")
    service["service_binding"] = "serena:project"
    service["instantiation_class"] = "instance_per_project"
    service["activation_class"] = "client_local_project_scoped"
    service["display_name"] = "Serena"
    return service


class ProjectInitActivationWorkflowTests(unittest.TestCase):
    def assert_validation_operation_retired(self, result: dict[str, Any]) -> None:
        self.assertFalse(result["ok"])
        self.assertEqual("project_init_validation_retired", result["status"])
        self.assertIn("Project init is install-only.", result["message"])
        self.assertNotIn("state_revision", result)

    def test_client_local_adapters_define_activation_contracts(self) -> None:
        adapters = binding.project_init_client_adapters()

        self.assertEqual({"codex", "gemini", "opencode", "pi"}, set(binding.supported_project_init_clients()))
        self.assertEqual(set(binding.supported_project_init_clients()), set(adapters))
        self.assertTrue(adapters["codex"]["supports_stale_owned_replacement"])
        self.assertFalse(adapters["opencode"]["supports_stale_owned_replacement"])
        self.assertEqual("project_state_shim_metadata", adapters["pi"]["plan_kind"])

        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            service = service_descriptor("context7")
            for client_type, adapter in adapters.items():
                with self.subTest(client_type=client_type):
                    plan = binding.plan_project_init_target_client_activation(root, [service], target_client=client_type)

                    self.assertEqual(adapter["surface"], plan["surface"])
                    self.assertEqual(adapter["scope"], plan["scope"])
                    self.assertEqual(adapter["non_actions"], plan["non_actions"])
                    self.assertEqual("redacted", plan["redaction_status"])
                    self.assertEqual([], plan["blockers"])
                    self.assertTrue(plan["write_allowed"])
                    for key in ("decision", "changes", "before_digest", "after_digest"):
                        self.assertIn(key, plan)

    def test_discovery_joins_manifests_to_contextforge_readback_without_client_identity(self) -> None:
        readback = [
            {"name": "context7_local_server", "id": "vs-context7"},
            {"name": "web_search_server", "id": "vs-web"},
        ]

        services = common.discover_contextforge_hosted_services(
            project_root="/home/dgk/workspace/legacy-controlplane-archive",
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

    def test_discovery_adds_unprovisioned_serena_candidate_for_new_workspace_project(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            identity = common.project_identity(root)
            capabilities = helper.list_available_capabilities(project_root=root)

        services = {service["service_binding"]: service for service in capabilities["available_services"]}
        serena_binding = f"serena:{identity.hash}"
        self.assertIn(serena_binding, services)
        self.assertIn(serena_binding, {choice["id"] for choice in capabilities["next_turn"]["choices"]})
        self.assertEqual("serena", services[serena_binding]["codex_alias"])
        self.assertEqual("client_local_project_scoped", services[serena_binding]["activation_class"])
        self.assertEqual("project_scoped_provisioning", services[serena_binding]["menu_group"])
        self.assertEqual(f"server-instances/{identity.instance_slug}", services[serena_binding]["backend_instance"])
        self.assertEqual(identity.server_name, services[serena_binding]["virtual_server"])
        self.assertEqual("required", services[serena_binding]["provisioning"]["status"])

    def test_discovery_marks_partial_serena_manifest_as_provision_required(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as project_tmp, tempfile.TemporaryDirectory(dir=REPO_ROOT) as instances_tmp:
            root = Path(project_tmp).resolve()
            identity = common.project_identity(root)
            instance = Path(instances_tmp) / identity.instance_slug
            instance.mkdir()
            (instance / "instance.json").write_text(
                json.dumps(
                    {
                        "service": "serena",
                        "canonical_project_root": str(root),
                        "server_name": identity.server_name,
                        "instance_slug": identity.instance_slug,
                        "hash": identity.hash,
                        "codex_alias": "serena",
                    }
                ),
                encoding="utf-8",
            )

            services = common.discover_contextforge_hosted_services(
                project_root=root,
                server_instances_root=instances_tmp,
            )

        self.assertEqual(1, len(services))
        service = services[0]
        self.assertEqual(f"serena:{identity.hash}", service["service_binding"])
        self.assertEqual("not_provisioned", service["contextforge_readback_status"])
        self.assertEqual("required", service["provisioning"]["status"])
        self.assertEqual(str(root), service["scope"]["workspace_root"])
        self.assertFalse(service["bridge"]["needed"])

    def test_codex_config_plan_writes_only_managed_project_local_wrapper_blocks(self) -> None:
        services = [service_descriptor("context7"), service_descriptor("web-search")]
        plan = binding.plan_project_init_codex_config_write(
            "/home/dgk/workspace/legacy-controlplane-archive",
            services,
            existing_text="# existing local config\n",
        )

        self.assertEqual("allow_owned_project_local_write", plan["decision"])
        self.assertEqual(".codex/config.toml", plan["surface"])
        self.assertIn("contextforge_mcp_wrapper.py", plan["next_text"])
        self.assertIn("[mcp_servers.context7]", plan["next_text"])
        self.assertIn("[mcp_servers.web_search]", plan["next_text"])
        self.assertIn("does not write user-global Codex config", plan["non_actions"])

    def test_codex_config_plan_replaces_multiple_owned_blocks_without_merging_sections(self) -> None:
        services = [service_descriptor("context7"), service_descriptor("github")]
        first = binding.plan_project_init_codex_config_write(
            "/home/dgk/workspace/legacy-controlplane-archive",
            services,
            existing_text="",
        )
        second = binding.plan_project_init_codex_config_write(
            "/home/dgk/workspace/legacy-controlplane-archive",
            services,
            existing_text=first["next_text"],
        )

        self.assertEqual("allow_owned_project_local_write", second["decision"])
        self.assertEqual(first["after_digest"], second["after_digest"])
        self.assertIn("tool_timeout_ms = 120000\n\n# contextforge-project-init-owner", second["next_text"])
        self.assertNotIn("120000# contextforge-project-init-owner", second["next_text"])

    def test_codex_config_plan_blocks_unmanaged_same_name(self) -> None:
        plan = binding.plan_project_init_codex_config_write(
            "/home/dgk/workspace/legacy-controlplane-archive",
            [service_descriptor("context7")],
            existing_text="[mcp_servers.context7]\ncommand = \"npx\"\n",
        )

        self.assertEqual("block", plan["decision"])
        self.assertIn("client_config_conflict", {item["type"] for item in plan["blockers"]})

    def test_codex_config_plan_replaces_unmanaged_serena_with_managed_block(self) -> None:
        managed_block = binding.build_project_init_codex_binding_block(serena_descriptor()).rstrip()
        existing_text = (
            "[mcp_servers.context7]\n"
            "command = \"npx\"\n"
            "url = \"https://example.invalid/context7\"\n\n"
            "[mcp_servers.serena]\n"
            "command = \"npx\"\n\n"
            "[resources.local]\n"
            "type = \"local\"\n"
        )
        plan = binding.plan_project_init_codex_config_write(
            "/home/dgk/workspace/legacy-controlplane-archive",
            [serena_descriptor()],
            existing_text=existing_text,
            replace_unmanaged_conflicts=True,
        )

        self.assertEqual("allow_owned_project_local_write", plan["decision"])
        self.assertEqual(1, len(plan["changes"]))
        self.assertIn("unmanaged_same_name", {change["owned_block_class"] for change in plan["changes"]})
        self.assertIn("replace", {change["operation"] for change in plan["changes"]})
        self.assertIn("[resources.local]", plan["next_text"])
        self.assertIn("[mcp_servers.serena]", plan["next_text"])
        self.assertIn("[mcp_servers.context7]", plan["next_text"])
        self.assertIn(managed_block, plan["next_text"])
        self.assertIsNotNone(plan["changes"][0]["existing_block_digest"])
        self.assertNotEqual(plan["changes"][0]["expected_block_digest"], plan["changes"][0]["existing_block_digest"])

    def test_codex_config_plan_noop_when_unmanaged_serena_block_already_matches_managed_block(self) -> None:
        first = binding.plan_project_init_codex_config_write(
            "/home/dgk/workspace/legacy-controlplane-archive",
            [serena_descriptor()],
            existing_text="",
        )
        second = binding.plan_project_init_codex_config_write(
            "/home/dgk/workspace/legacy-controlplane-archive",
            [serena_descriptor()],
            existing_text=first["next_text"],
            replace_unmanaged_conflicts=True,
        )

        self.assertEqual("allow_owned_project_local_write", second["decision"])
        self.assertEqual(first["next_text"], second["next_text"])
        self.assertEqual("unchanged", second["changes"][0]["operation"])
        self.assertEqual(first["after_digest"], second["before_digest"])
        self.assertEqual(first["after_digest"], second["after_digest"])
        self.assertEqual(second["changes"][0]["expected_block_digest"], second["changes"][0]["existing_block_digest"])

    def test_codex_config_plan_honors_docker_wrapper_overrides(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "CONTEXTFORGE_CODEX_WRAPPER_PYTHON": "/opt/contextforge-helper-venv/bin/python",
                "CONTEXTFORGE_CODEX_WRAPPER_SCRIPT": "/repo/scripts/contextforge_mcp_wrapper.py",
                "CONTEXTFORGE_CODEX_WRAPPER_CONFIG_ENV": "/config/contextforge/contextforge.env",
                "CONTEXTFORGE_CODEX_WRAPPER_BASE_URL": "http://host.docker.internal:4445",
                "CONTEXTFORGE_CODEX_WRAPPER_TOKEN_CACHE": "/tmp/contextforge-wrapper-token.local.json",
            },
            clear=False,
        ):
            plan = binding.plan_project_init_codex_config_write(
                "/home/dgk/workspace/legacy-controlplane-archive",
                [service_descriptor("context7")],
                existing_text="",
            )

        text = plan["next_text"]
        self.assertIn('command = "/opt/contextforge-helper-venv/bin/python"', text)
        self.assertIn('args = ["/repo/scripts/contextforge_mcp_wrapper.py", "context7_server"]', text)
        self.assertIn('CONTEXTFORGE_CONFIG_ENV = "/config/contextforge/contextforge.env"', text)
        self.assertIn('CONTEXTFORGE_BASE_URL = "http://host.docker.internal:4445"', text)
        self.assertIn('CONTEXTFORGE_TOKEN_CACHE = "/tmp/contextforge-wrapper-token.local.json"', text)
        self.assertIn('CONTEXTFORGE_TOKEN_LOCK = "/tmp/contextforge-wrapper-token.local.json.lock"', text)

    def test_opencode_config_plan_writes_managed_project_mcp_only(self) -> None:
        plan = binding.plan_project_init_opencode_config_write(
            "/home/dgk/workspace/legacy-controlplane-archive",
            [service_descriptor("context7")],
            existing_text='{"$schema":"https://opencode.ai/config.json"}\n',
            plugin_existing_text="",
        )

        parsed = json.loads(plan["next_text"])
        self.assertEqual("allow_owned_project_local_write", plan["decision"])
        self.assertEqual(binding.OPENCODE_CONFIG_SURFACE, plan["surface"])
        self.assertEqual("local", parsed["mcp"]["context7"]["type"])
        self.assertTrue(parsed["mcp"]["context7"]["enabled"])
        self.assertIn("contextforge_mcp_wrapper.py", " ".join(parsed["mcp"]["context7"]["command"]))
        self.assertEqual(binding.OPENCODE_GLOBAL_TRIGGER_SURFACE, plan["global_trigger_surface"])
        self.assertNotIn("plugin_next_text", plan)
        self.assertNotIn("plugin_change", plan)
        self.assertIn("does not write user-global OpenCode config, plugin, or trust", plan["non_actions"])

    def test_opencode_config_plan_honors_docker_wrapper_overrides(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "CONTEXTFORGE_OPENCODE_WRAPPER_PYTHON": "/opt/contextforge-helper-venv/bin/python",
                "CONTEXTFORGE_OPENCODE_WRAPPER_SCRIPT": "/repo/scripts/contextforge_mcp_wrapper.py",
                "CONTEXTFORGE_OPENCODE_WRAPPER_CONFIG_ENV": "/config/contextforge/contextforge.env",
                "CONTEXTFORGE_OPENCODE_WRAPPER_BASE_URL": "http://host.docker.internal:4445",
                "CONTEXTFORGE_OPENCODE_WRAPPER_TOKEN_CACHE": "/tmp/contextforge-wrapper-token.local.json",
            },
            clear=False,
        ):
            plan = binding.plan_project_init_opencode_config_write(
                "/home/dgk/workspace/legacy-controlplane-archive",
                [service_descriptor("context7")],
                existing_text='{"$schema":"https://opencode.ai/config.json"}\n',
                plugin_existing_text="",
            )

        entry = json.loads(plan["next_text"])["mcp"]["context7"]
        self.assertEqual(
            [
                "/opt/contextforge-helper-venv/bin/python",
                "/repo/scripts/contextforge_mcp_wrapper.py",
                "context7_server",
            ],
            entry["command"],
        )
        self.assertEqual("/config/contextforge/contextforge.env", entry["environment"]["CONTEXTFORGE_CONFIG_ENV"])
        self.assertEqual("http://host.docker.internal:4445", entry["environment"]["CONTEXTFORGE_BASE_URL"])
        self.assertEqual("/tmp/contextforge-wrapper-token.local.json", entry["environment"]["CONTEXTFORGE_TOKEN_CACHE"])
        self.assertEqual(
            "/tmp/contextforge-wrapper-token.local.json.lock",
            entry["environment"]["CONTEXTFORGE_TOKEN_LOCK"],
        )

    def test_project_init_bindings_do_not_embed_contextforge_bearer_token_material(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            services = [service_descriptor("context7")]

            codex_plan = binding.plan_project_init_target_client_activation(root, services, target_client="codex")
            opencode_plan = binding.plan_project_init_target_client_activation(root, services, target_client="opencode")
            gemini_plan = binding.plan_project_init_target_client_activation(root, services, target_client="gemini")

        self.assertIn("contextforge_mcp_wrapper.py", codex_plan["next_text"])
        self.assertIn("contextforge_mcp_wrapper.py", opencode_plan["next_text"])
        self.assertIn("contextforge_mcp_wrapper.py", gemini_plan["next_text"])
        combined = "\n".join([codex_plan["next_text"], opencode_plan["next_text"], gemini_plan["next_text"]])
        self.assertNotIn("CONTEXTFORGE_BEARER_TOKEN", combined)
        self.assertNotIn("MCP_AUTH", combined)
        self.assertNotIn("Authorization", combined)

    def test_opencode_config_plan_blocks_unmanaged_same_name(self) -> None:
        plan = binding.plan_project_init_opencode_config_write(
            "/home/dgk/workspace/legacy-controlplane-archive",
            [service_descriptor("context7")],
            existing_text=json.dumps({"mcp": {"context7": {"type": "remote", "url": "https://example.invalid/mcp"}}}),
            plugin_existing_text="",
        )

        self.assertEqual("block", plan["decision"])
        self.assertIn("client_config_conflict", {item["type"] for item in plan["blockers"]})

    def test_state_records_presumed_validation_without_marking_target_client_verified(self) -> None:
        state = project_state.default_state("/home/dgk/workspace/legacy-controlplane-archive")
        service = service_descriptor("context7")
        config_plan = binding.plan_project_init_codex_config_write(
            "/home/dgk/workspace/legacy-controlplane-archive",
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
            consent_receipt_refs=CONSENT_REFS,
        )

        self.assertEqual("in_progress", next_state["status"])
        self.assertEqual("completed_unverified", next_state["project_init"]["x_hook_prompt_state"])
        record = next_state["services"]["context7:canonical"]
        self.assertEqual("presumed_working", record["verification_layers"]["target_client"]["status"])
        self.assertFalse(record["evidence"][0]["client_configs_are_service_identities"])
        self.assertRegex(record["x_service_identity"]["id"], r"^contextforge-service-[a-f0-9]{24}$")
        self.assertEqual(record["x_service_identity"]["id"], record["target_clients"]["codex"]["service_identity_id"])
        self.assertEqual("deferred", next_state["open_items"][0]["resolution_state"])
        project_state.validate_state(next_state)

    def test_state_removes_contextforge_server_id_absent_from_current_readback(self) -> None:
        state = project_state.default_state("/home/dgk/workspace/legacy-controlplane-archive")
        service = service_descriptor("context7")
        service["contextforge_server_id"] = "ctx-old"
        config_plan = binding.plan_project_init_codex_config_write(
            "/home/dgk/workspace/legacy-controlplane-archive",
            [service],
            existing_text="",
        )
        validation_plan = binding.build_project_init_validation_plan([service], validation_mode="presume_working")
        first_state = project_state.apply_project_init_activation_to_state(
            state,
            [service],
            target_client="codex",
            client_config_plan=config_plan,
            validation_plan=validation_plan,
            validation_results={},
            consent_receipt_refs=CONSENT_REFS,
        )

        missing = service_descriptor("context7")
        missing["contextforge_readback_status"] = "missing"
        second_state = project_state.apply_project_init_activation_to_state(
            first_state,
            [missing],
            target_client="codex",
            client_config_plan=config_plan,
            validation_plan=validation_plan,
            validation_results={},
            consent_receipt_refs=CONSENT_REFS,
        )

        record = second_state["services"]["context7:canonical"]
        self.assertNotIn("x_contextforge_server_id", record)
        self.assertIsNone(record["x_service_identity"]["contextforge_server_id"])
        stale_ids = second_state["drift"]["stale_ids"]
        self.assertTrue(any(item["id"] == "ctx-old" and item["id_kind"] == "contextforge_server" for item in stale_ids))
        project_state.validate_state(second_state)

    def test_legacy_activation_job_bindings_normalize_to_service_ids(self) -> None:
        state = project_state.default_state("/home/dgk/workspace/legacy-controlplane-archive")
        service = service_descriptor("context7")
        config_plan = binding.plan_project_init_codex_config_write(
            "/home/dgk/workspace/legacy-controlplane-archive",
            [service],
            existing_text="",
        )
        validation_plan = binding.build_project_init_validation_plan([service], validation_mode="pending_choice")
        state = project_state.apply_project_init_activation_to_state(
            state,
            [service],
            target_client="codex",
            client_config_plan=config_plan,
            validation_plan=validation_plan,
            validation_results={},
            consent_receipt_refs=CONSENT_REFS,
        )
        job = state["project_init"]["activation_jobs"][state["project_init"]["current_job_id"]]
        legacy_id = job["selected_service_ids"][0]
        job.pop("selected_service_ids")
        legacy_record = job["validation_records"].pop(legacy_id)
        job["validation_records"]["context7:canonical"] = legacy_record

        project_state.validate_state(state)

        normalized_job = state["project_init"]["activation_jobs"][state["project_init"]["current_job_id"]]
        normalized_id = normalized_job["selected_service_ids"][0]
        self.assertRegex(normalized_id, r"^contextforge-service-[a-f0-9]{24}$")
        self.assertIn(normalized_id, normalized_job["validation_records"])
        self.assertEqual("context7:canonical", normalized_job["validation_records"][normalized_id]["x_service_binding"])

    def test_state_rekeys_existing_service_record_by_binding_during_activation(self) -> None:
        state = project_state.default_state("/home/dgk/workspace/legacy-controlplane-archive")
        state["services"]["context7"] = {
            "service_family": "context7",
            "service_binding": "context7:canonical",
            "instantiation_class": "shared_canonical",
            "backend_instance": "server-instances/context7",
            "virtual_server": "context7_server",
            "target_clients": {},
            "consent_receipt_refs": ["run/consent-receipts/imported-existing-state.json"],
            "evidence": [{"name": "existing_readback", "status": "passed"}],
        }
        service = service_descriptor("context7")
        config_plan = binding.plan_project_init_codex_config_write(
            "/home/dgk/workspace/legacy-controlplane-archive",
            [service],
            existing_text="",
        )
        validation_plan = binding.build_project_init_validation_plan([service], validation_mode="pending_choice")

        next_state = project_state.apply_project_init_activation_to_state(
            state,
            [service],
            target_client="codex",
            client_config_plan=config_plan,
            validation_plan=validation_plan,
            validation_results={},
            consent_receipt_refs=CONSENT_REFS,
        )

        self.assertNotIn("context7", next_state["services"])
        self.assertIn("context7:canonical", next_state["services"])
        record = next_state["services"]["context7:canonical"]
        self.assertIn("run/consent-receipts/imported-existing-state.json", record["consent_receipt_refs"])
        self.assertEqual("existing_readback", record["evidence"][0]["name"])
        project_state.validate_state(next_state)

    def test_state_marks_initialized_only_with_target_client_visible_validation(self) -> None:
        state = project_state.default_state("/home/dgk/workspace/legacy-controlplane-archive")
        service = service_descriptor("context7")
        config_plan = binding.plan_project_init_codex_config_write(
            "/home/dgk/workspace/legacy-controlplane-archive",
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
            consent_receipt_refs=CONSENT_REFS,
        )

        self.assertEqual("initialized", next_state["status"])
        self.assertEqual("completed_verified", next_state["project_init"]["x_hook_prompt_state"])
        self.assertEqual("none", next_state["services"]["context7:canonical"]["provision_status"])
        self.assertEqual("passed", next_state["services"]["context7:canonical"]["verification_layers"]["target_client"]["status"])
        project_state.validate_state(next_state)

    def test_backend_only_validation_does_not_mark_initialized(self) -> None:
        state = project_state.default_state("/home/dgk/workspace/legacy-controlplane-archive")
        service = service_descriptor("context7")
        config_plan = binding.plan_project_init_codex_config_write(
            "/home/dgk/workspace/legacy-controlplane-archive",
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
                    "target_client_visible": False,
                    "backend_probe": "passed",
                }
            },
            consent_receipt_refs=CONSENT_REFS,
        )

        self.assertEqual("in_progress", next_state["status"])
        self.assertEqual("pending", next_state["services"]["context7:canonical"]["verification_layers"]["target_client"]["status"])
        record = next_state["project_init"]["activation_jobs"][next_state["project_init"]["current_job_id"]]
        self.assertEqual("validation_pending", record["status"])
        project_state.validate_state(next_state)

    def test_context7_builder_output_controls_project_init_validation_state(self) -> None:
        root = "/home/dgk/workspace/legacy-controlplane-archive"
        state = project_state.default_state(root)
        service = service_descriptor("context7")
        config_plan = binding.plan_project_init_codex_config_write(root, [service], existing_text="")
        validation_plan = binding.build_project_init_validation_plan([service], validation_mode="validate_now")

        passing = common.build_safe_probe_validation_result(
            "context7",
            target_client="codex",
            tool_name="context7-local-resolve-library-id",
            verification_trace_refs=["contextforge://control-plane/traces/context7-target-client"],
        )
        passing_state = project_state.apply_project_init_activation_to_state(
            state,
            [service],
            target_client="codex",
            client_config_plan=config_plan,
            validation_plan=validation_plan,
            validation_results={"context7:canonical": passing},
            consent_receipt_refs=CONSENT_REFS,
        )

        self.assertEqual("initialized", passing_state["status"])
        record = passing_state["services"]["context7:canonical"]["verification_layers"]["target_client"]
        self.assertEqual("passed", record["status"])
        job = passing_state["project_init"]["activation_jobs"][passing_state["project_init"]["current_job_id"]]
        validation_record = job["validation_records"][job["selected_service_ids"][0]]
        self.assertEqual("target_client_safe_probe_result", validation_record["x_proof_kind"])
        self.assertEqual("passed", validation_record["x_safe_probe_result"])

        rejected = common.build_safe_probe_validation_result(
            "context7",
            target_client="codex",
            tool_name="local-package-lookup",
            verification_trace_refs=["contextforge://control-plane/traces/context7-target-client"],
            proof_kind="backend_health",
        )
        rejected_state = project_state.apply_project_init_activation_to_state(
            state,
            [service],
            target_client="codex",
            client_config_plan=config_plan,
            validation_plan=validation_plan,
            validation_results={"context7:canonical": rejected},
            consent_receipt_refs=CONSENT_REFS,
        )

        self.assertEqual("in_progress", rejected_state["status"])
        rejected_record = rejected_state["services"]["context7:canonical"]["verification_layers"]["target_client"]
        self.assertEqual("pending", rejected_record["status"])
        self.assertIs(rejected["target_client_visible"], False)

    def test_mentality_builder_output_controls_project_init_validation_state(self) -> None:
        root = "/home/dgk/workspace/legacy-controlplane-archive"
        state = project_state.default_state(root)
        service = service_descriptor("mentality")
        config_plan = binding.plan_project_init_codex_config_write(root, [service], existing_text="")
        validation_plan = binding.build_project_init_validation_plan([service], validation_mode="validate_now")

        passing = common.build_safe_probe_validation_result(
            "mentality",
            target_client="codex",
            tool_name="mentality-governance-list",
            verification_trace_refs=["contextforge://control-plane/traces/mentality-target-client"],
        )
        passing_state = project_state.apply_project_init_activation_to_state(
            state,
            [service],
            target_client="codex",
            client_config_plan=config_plan,
            validation_plan=validation_plan,
            validation_results={"mentality:canonical": passing},
            consent_receipt_refs=CONSENT_REFS,
        )

        self.assertEqual("initialized", passing_state["status"])
        record = passing_state["services"]["mentality:canonical"]["verification_layers"]["target_client"]
        self.assertEqual("passed", record["status"])
        job = passing_state["project_init"]["activation_jobs"][passing_state["project_init"]["current_job_id"]]
        validation_record = job["validation_records"][job["selected_service_ids"][0]]
        self.assertEqual("target_client_safe_probe_result", validation_record["x_proof_kind"])
        self.assertEqual("passed", validation_record["x_safe_probe_result"])
        self.assertEqual("governance-list", validation_record["safe_probe_id"])

        rejected = common.build_safe_probe_validation_result(
            "mentality",
            target_client="codex",
            tool_name="cat DECISIONS.md",
            verification_trace_refs=["file://DECISIONS.md"],
        )
        rejected_state = project_state.apply_project_init_activation_to_state(
            state,
            [service],
            target_client="codex",
            client_config_plan=config_plan,
            validation_plan=validation_plan,
            validation_results={"mentality:canonical": rejected},
            consent_receipt_refs=CONSENT_REFS,
        )

        self.assertEqual("in_progress", rejected_state["status"])
        rejected_record = rejected_state["services"]["mentality:canonical"]["verification_layers"]["target_client"]
        self.assertEqual("pending", rejected_record["status"])
        self.assertIs(rejected["target_client_visible"], False)

    def test_ssh_tmux_builder_output_controls_project_init_validation_state(self) -> None:
        root = "/home/dgk/workspace/legacy-controlplane-archive"
        state = project_state.default_state(root)
        service = service_descriptor("ssh-tmux")
        config_plan = binding.plan_project_init_codex_config_write(root, [service], existing_text="")
        validation_plan = binding.build_project_init_validation_plan([service], validation_mode="validate_now")

        passing = common.build_safe_probe_validation_result(
            "ssh-tmux",
            target_client="codex",
            tool_name="ssh-tmux-list-sessions",
            verification_trace_refs=["contextforge://control-plane/traces/ssh-tmux-target-client"],
        )
        passing_state = project_state.apply_project_init_activation_to_state(
            state,
            [service],
            target_client="codex",
            client_config_plan=config_plan,
            validation_plan=validation_plan,
            validation_results={"ssh-tmux:canonical": passing},
            consent_receipt_refs=CONSENT_REFS,
        )

        self.assertEqual("initialized", passing_state["status"])
        record = passing_state["services"]["ssh-tmux:canonical"]["verification_layers"]["target_client"]
        self.assertEqual("passed", record["status"])
        job = passing_state["project_init"]["activation_jobs"][passing_state["project_init"]["current_job_id"]]
        validation_record = job["validation_records"][job["selected_service_ids"][0]]
        self.assertEqual("target_client_safe_probe_result", validation_record["x_proof_kind"])
        self.assertEqual("passed", validation_record["x_safe_probe_result"])
        self.assertEqual("list-sessions", validation_record["safe_probe_id"])

        rejected = common.build_safe_probe_validation_result(
            "ssh-tmux",
            target_client="codex",
            tool_name="tmux list-sessions",
            verification_trace_refs=["shell://tmux/list-sessions"],
        )
        rejected_state = project_state.apply_project_init_activation_to_state(
            state,
            [service],
            target_client="codex",
            client_config_plan=config_plan,
            validation_plan=validation_plan,
            validation_results={"ssh-tmux:canonical": rejected},
            consent_receipt_refs=CONSENT_REFS,
        )

        self.assertEqual("in_progress", rejected_state["status"])
        rejected_record = rejected_state["services"]["ssh-tmux:canonical"]["verification_layers"]["target_client"]
        self.assertEqual("pending", rejected_record["status"])
        self.assertIs(rejected["target_client_visible"], False)

    def test_openzeppelin_builder_output_controls_project_init_validation_state(self) -> None:
        root = "/home/dgk/workspace/legacy-controlplane-archive"
        state = project_state.default_state(root)
        service = service_descriptor("openzeppelin-solidity-contracts")
        config_plan = binding.plan_project_init_codex_config_write(root, [service], existing_text="")
        validation_plan = binding.build_project_init_validation_plan([service], validation_mode="validate_now")

        passing = common.build_safe_probe_validation_result(
            "openzeppelin-solidity-contracts",
            target_client="codex",
            tool_name="openzeppelin-solidity-contracts-solidity-erc20",
            verification_trace_refs=["contextforge://control-plane/traces/openzeppelin-target-client"],
        )
        passing_state = project_state.apply_project_init_activation_to_state(
            state,
            [service],
            target_client="codex",
            client_config_plan=config_plan,
            validation_plan=validation_plan,
            validation_results={"openzeppelin-solidity-contracts:canonical": passing},
            consent_receipt_refs=CONSENT_REFS,
        )

        self.assertEqual("initialized", passing_state["status"])
        record = passing_state["services"]["openzeppelin-solidity-contracts:canonical"]["verification_layers"]["target_client"]
        self.assertEqual("passed", record["status"])
        job = passing_state["project_init"]["activation_jobs"][passing_state["project_init"]["current_job_id"]]
        validation_record = job["validation_records"][job["selected_service_ids"][0]]
        self.assertEqual("target_client_safe_probe_result", validation_record["x_proof_kind"])
        self.assertEqual("passed", validation_record["x_safe_probe_result"])
        self.assertEqual("solidity-erc20-preview", validation_record["safe_probe_id"])

        rejected = common.build_safe_probe_validation_result(
            "openzeppelin-solidity-contracts",
            target_client="codex",
            tool_name="curl https://mcp.openzeppelin.com/contracts/solidity/mcp",
            verification_trace_refs=["https://mcp.openzeppelin.com/contracts/solidity/mcp"],
        )
        rejected_state = project_state.apply_project_init_activation_to_state(
            state,
            [service],
            target_client="codex",
            client_config_plan=config_plan,
            validation_plan=validation_plan,
            validation_results={"openzeppelin-solidity-contracts:canonical": rejected},
            consent_receipt_refs=CONSENT_REFS,
        )

        self.assertEqual("in_progress", rejected_state["status"])
        rejected_record = rejected_state["services"]["openzeppelin-solidity-contracts:canonical"]["verification_layers"]["target_client"]
        self.assertEqual("pending", rejected_record["status"])
        self.assertIs(rejected["target_client_visible"], False)

    def test_pending_validation_choice_records_job_without_verified_status(self) -> None:
        state = project_state.default_state("/home/dgk/workspace/legacy-controlplane-archive")
        service = service_descriptor("context7")
        config_plan = binding.plan_project_init_codex_config_write(
            "/home/dgk/workspace/legacy-controlplane-archive",
            [service],
            existing_text="",
        )
        validation_plan = binding.build_project_init_validation_plan([service], validation_mode="pending_choice")

        next_state = project_state.apply_project_init_activation_to_state(
            state,
            [service],
            target_client="codex",
            client_config_plan=config_plan,
            validation_plan=validation_plan,
            validation_results={},
            consent_receipt_refs=["run/consent-receipts/receipt-project-local-config.json"],
        )

        self.assertEqual("in_progress", next_state["status"])
        job = next_state["project_init"]["activation_jobs"][next_state["project_init"]["current_job_id"]]
        self.assertEqual("applied_validation_choice_pending", job["status"])
        self.assertEqual("local_written_validation_pending", job["recovery_state"])
        self.assertEqual("pending_user_choice", job["validation_records"][job["selected_service_ids"][0]]["status"])
        self.assertEqual("context7:canonical", job["validation_records"][job["selected_service_ids"][0]]["x_service_binding"])
        self.assertIn("run/consent-receipts/receipt-project-local-config.json", job["consent_receipt_refs"])
        project_state.validate_state(next_state)

    def test_apply_activation_dry_run_does_not_write_files(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT) as tmp:
            root = Path(tmp).resolve()
            result = binding.apply_project_init_service_activation(
                root,
                [service_descriptor("context7")],
                validation_mode="presume_working",
                approval_scope=binding.PROJECT_INIT_APPROVAL_SCOPE,
                consent_receipt_refs=CONSENT_REFS,
                dry_run=True,
            )

            self.assertTrue(result["dry_run"])
            self.assertFalse((root / ".codex/config.toml").exists())
            self.assertFalse(project_state.project_state_path(root).exists())
            self.assertEqual("in_progress", result["planned_state"]["status"])

    def test_helper_unavailable_stops_without_direct_write_fallback(self) -> None:
        for state in ["missing", "stale", "untrusted", "wrong_project_root", "read_only_plan_only"]:
            readiness = helper.helper_readiness(
                project_root="/home/dgk/workspace/legacy-controlplane-archive",
                helper_state=state,
            )

            self.assertEqual(state, readiness["helper"]["status"])
            self.assertFalse(readiness["can_mutate"])
            self.assertTrue(readiness["next_turn"]["must_stop"])
            self.assertIn("do not write local files directly", readiness["non_actions"][0])

    def test_helper_replaces_invalid_stale_project_state_only_after_scoped_approval(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            state_path = project_state.project_state_path(root)
            state_path.parent.mkdir(parents=True)
            state_path.write_text(json.dumps({"status": "in_progress", "x_stale_fixture": True}) + "\n", encoding="utf-8")

            proposal = helper.propose_project_init(
                project_root=root,
                selected_services=[service_descriptor("context7")],
                client_type="pi",
            )
            planned_state = proposal["stale_plan_inputs"]["base_project_state"]
            local_event = helper.record_local_approval_event(
                project_root=root,
                plan=proposal,
                issuer_token=helper._LOCAL_APPROVAL_ISSUER_TOKEN,
                channel="interactive_user",
            )
            approval = helper.approve_project_init_plan(
                project_root=root,
                plan=proposal,
                approval={
                    "decision": "approve",
                    "challenge_id": proposal["approval_challenge"]["challenge_id"],
                    "plan_digest": proposal["plan_digest"],
                },
                local_approval_event_ref=local_event["event_ref"],
                actor="developer",
                source_client="pi",
                source_client_auth_strength="shared_token",
            )
            result = helper.apply_approved_project_init(
                project_root=root,
                plan=proposal,
                receipts=approval["receipts"],
            )
            written = project_state.load_state(root)

        self.assertEqual("invalid", planned_state["artifact_status"])
        self.assertEqual("replace_after_scoped_project_init_approval", planned_state["recovery"])
        self.assertIn("project_state_recovery", proposal["plan_summary"])
        self.assertEqual("invalid", proposal["plan_summary"]["project_state_recovery"]["artifact_status"])
        self.assertEqual("initialized", result["state_status"])
        assert written is not None
        self.assertIn("context7:canonical", written["services"])
        self.assertNotIn("x_stale_fixture", written)

    def test_pi_is_supported_without_reusing_codex_config_writer(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            readiness = helper.helper_readiness(project_root=root, client_type="pi")
            proposal = helper.propose_project_init(
                project_root=root,
                selected_services=[service_descriptor("context7")],
                client_type="pi",
            )
            result = binding.apply_project_init_service_activation(
                root,
                [service_descriptor("context7")],
                validation_mode="pending_choice",
                approval_scope=binding.PROJECT_INIT_APPROVAL_SCOPE,
                target_client="pi",
                consent_receipt_refs=["run/consent-receipts/receipt-project-state.json"],
                dry_run=True,
            )

        self.assertEqual("available", readiness["helper"]["status"])
        self.assertEqual("/reload", readiness["client_reload_requirement"]["command"])
        self.assertIn("issue /reload in Pi", readiness["client_reload_requirement"]["instruction"])
        self.assertEqual(["project_state_write"], proposal["required_consent_classes"])
        self.assertEqual(binding.PI_SHIM_SURFACE, proposal["config_plan"]["surface"])
        self.assertIsNone(proposal["config_plan"]["config_path"])
        self.assertNotIn(str(root / ".codex" / "config.toml"), proposal["plan_summary"]["project_local_writes"])
        self.assertIn(str(project_state.project_state_path(root)), proposal["plan_summary"]["project_local_writes"])
        self.assertFalse((root / ".codex/config.toml").exists())
        self.assertEqual([str(project_state.project_state_path(root))], result["writes"])
        service = result["planned_state"]["services"]["context7:canonical"]
        self.assertNotIn("codex", service["target_clients"])
        self.assertEqual("shim_activation_planned", service["target_clients"]["pi"]["status"])
        self.assertEqual("contextforge-global-shim", service["target_clients"]["pi"]["shim"])
        project_state.validate_state(result["planned_state"])

    def test_gemini_is_supported_with_project_local_settings_writer(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            readiness = helper.helper_readiness(project_root=root, client_type="gemini")
            proposal = helper.propose_project_init(
                project_root=root,
                selected_services=[service_descriptor("context7")],
                client_type="gemini",
            )
            config_plan = binding.plan_project_init_gemini_config_write(root, [service_descriptor("context7")])
            result = binding.apply_project_init_service_activation(
                root,
                [service_descriptor("context7")],
                validation_mode="pending_choice",
                approval_scope=binding.PROJECT_INIT_APPROVAL_SCOPE,
                target_client="gemini",
                consent_receipt_refs=CONSENT_REFS,
                dry_run=True,
            )

        self.assertEqual("available", readiness["helper"]["status"])
        self.assertEqual("start_new_session", readiness["client_reload_requirement"]["command"])
        self.assertEqual(["project_local_config_write", "project_state_write"], proposal["required_consent_classes"])
        self.assertEqual(".gemini/settings.json", proposal["config_plan"]["surface"])
        self.assertIn("contextforge_mcp_wrapper.py", config_plan["next_text"])
        self.assertIn(str(root / ".gemini" / "settings.json"), proposal["plan_summary"]["project_local_writes"])
        self.assertEqual(
            [str(root / ".gemini" / "settings.json"), str(project_state.project_state_path(root))],
            result["writes"],
        )
        service = result["planned_state"]["services"]["context7:canonical"]
        self.assertNotIn("codex", service["target_clients"])
        self.assertEqual("project_local_settings_planned", service["target_clients"]["gemini"]["status"])
        self.assertEqual(".gemini/settings.json", service["target_clients"]["gemini"]["surface"])
        self.assertEqual("shared_contextforge_service", service["lifecycle"]["activation"])
        project_state.validate_state(result["planned_state"])

    def test_opencode_is_supported_with_project_local_config_and_global_trigger_prerequisite(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            readiness = helper.helper_readiness(project_root=root, client_type="opencode")
            proposal = helper.propose_project_init(
                project_root=root,
                selected_services=[service_descriptor("context7")],
                client_type="opencode",
            )
            config_plan = binding.plan_project_init_opencode_config_write(root, [service_descriptor("context7")])
            result = binding.apply_project_init_service_activation(
                root,
                [service_descriptor("context7")],
                validation_mode="pending_choice",
                approval_scope=binding.PROJECT_INIT_APPROVAL_SCOPE,
                target_client="opencode",
                consent_receipt_refs=CONSENT_REFS,
                dry_run=True,
            )

        parsed_config = json.loads(config_plan["next_text"])
        self.assertEqual("available", readiness["helper"]["status"])
        self.assertEqual("start_new_session", readiness["client_reload_requirement"]["command"])
        self.assertEqual(["project_local_config_write", "project_state_write"], proposal["required_consent_classes"])
        self.assertEqual(binding.OPENCODE_CONFIG_SURFACE, proposal["config_plan"]["surface"])
        self.assertEqual("local", parsed_config["mcp"]["context7"]["type"])
        self.assertIn("contextforge_mcp_wrapper.py", " ".join(parsed_config["mcp"]["context7"]["command"]))
        self.assertEqual(binding.OPENCODE_GLOBAL_TRIGGER_SURFACE, config_plan["global_trigger_surface"])
        self.assertNotIn("plugin_next_text", config_plan)
        self.assertIn(str(root / "opencode.json"), proposal["plan_summary"]["project_local_writes"])
        self.assertNotIn(str(root / ".opencode" / "plugins" / "contextforge-project-init.js"), proposal["plan_summary"]["project_local_writes"])
        self.assertEqual(
            [
                str(root / "opencode.json"),
                str(project_state.project_state_path(root)),
            ],
            result["writes"],
        )
        service = result["planned_state"]["services"]["context7:canonical"]
        self.assertNotIn("codex", service["target_clients"])
        self.assertEqual("project_local_opencode_config_planned", service["target_clients"]["opencode"]["status"])
        self.assertEqual(binding.OPENCODE_CONFIG_SURFACE, service["target_clients"]["opencode"]["surface"])
        self.assertEqual(binding.OPENCODE_GLOBAL_TRIGGER_SURFACE, service["target_clients"]["opencode"]["global_trigger_surface"])
        self.assertEqual("shared_contextforge_service", service["lifecycle"]["activation"])
        project_state.validate_state(result["planned_state"])

    def test_pending_validation_resume_uses_client_specific_job_state(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            service = service_descriptor("context7")
            codex_plan = binding.plan_project_init_codex_config_write(root, [service], existing_text="")
            codex_state = project_state.apply_project_init_activation_to_state(
                project_state.default_state(root),
                [service],
                target_client="codex",
                client_config_plan=codex_plan,
                validation_plan=binding.build_project_init_validation_plan([service], validation_mode="pending_choice", target_client="codex"),
                validation_results={},
                consent_receipt_refs=CONSENT_REFS,
            )
            gemini_plan = binding.plan_project_init_gemini_config_write(root, [service])
            gemini_state = project_state.apply_project_init_activation_to_state(
                codex_state,
                [service],
                target_client="gemini",
                client_config_plan=gemini_plan,
                validation_plan=binding.build_project_init_validation_plan([service], validation_mode="pending_choice", target_client="gemini"),
                validation_results={},
                consent_receipt_refs=CONSENT_REFS,
            )
            project_state.write_state_atomic(root, gemini_state)

            codex_resume = helper.pending_validation_resume(project_root=root, client_type="codex")
            gemini_resume = helper.pending_validation_resume(project_root=root, client_type="gemini")

        assert codex_resume is not None
        assert gemini_resume is not None
        self.assertIn(codex_resume["status"], {"config_repair_required", "client_reload_required", "installed_reload_required"})
        self.assertIn(gemini_resume["status"], {"config_repair_required", "client_reload_required", "installed_reload_required"})
        self.assertEqual(
            codex_state["project_init"]["client_states"]["codex"]["current_job_id"],
            codex_resume["current_job"]["job_id"],
        )
        self.assertEqual(
            gemini_state["project_init"]["client_states"]["gemini"]["current_job_id"],
            gemini_resume["current_job"]["job_id"],
        )

    def test_pi_helper_approval_and_apply_dry_run_are_parity_scoped(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            plan = helper.propose_project_init(project_root=root, selected_services=[service_descriptor("context7")], client_type="pi")
            event = helper.record_local_approval_event(
                project_root=root,
                plan=plan,
                issuer_token=helper._LOCAL_APPROVAL_ISSUER_TOKEN,
            )
            approval = helper.approve_project_init_plan(
                project_root=root,
                plan=plan,
                approval={
                    "decision": "approve",
                    "challenge_id": plan["approval_challenge"]["challenge_id"],
                    "plan_digest": plan["plan_digest"],
                },
                local_approval_event_ref=event["event_ref"],
            )
            result = helper.apply_approved_project_init(project_root=root, plan=plan, receipts=approval["receipts"], dry_run=True)

        self.assertEqual("allow", approval["decision"])
        self.assertEqual({"project_state_write"}, {receipt["consent_class"] for receipt in approval["receipts"]})
        self.assertEqual({"pi"}, {receipt["source_client"] for receipt in approval["receipts"]})
        self.assertTrue(result["dry_run"])
        self.assertEqual("pi-project-init-installed", result["next_turn"]["question_id"])
        self.assertEqual("/reload", result["client_reload_requirement"]["command"])
        self.assertIn("tools are installed", result["next_turn"]["prompt"])
        self.assertIn("/reload", result["next_turn"]["prompt"])
        self.assertNotIn("validate", result["next_turn"]["allowed_response_shape"])
        self.assertNotIn("skip validation", result["next_turn"]["allowed_response_shape"])
        self.assertEqual("single_select", result["next_turn"]["response_form"]["type"])
        self.assertFalse((root / ".codex/config.toml").exists())
        service = result["planned_state"]["services"]["context7:canonical"]
        self.assertEqual("shared_contextforge_service", service["lifecycle"]["activation"])
        self.assertEqual("shim_activation_planned", service["target_clients"]["pi"]["status"])

    def test_pi_shim_dry_run_imports_project_state_bindings_and_blocks_mutating_defaults(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            selected = [service_descriptor("context7"), service_descriptor("github")]
            config_plan = binding.plan_project_init_target_client_activation(root, selected, target_client="pi")
            validation_plan = binding.build_project_init_validation_plan(selected, validation_mode="pending_choice", target_client="pi")
            state = project_state.apply_project_init_activation_to_state(
                project_state.default_state(root),
                selected,
                target_client="pi",
                client_config_plan=config_plan,
                validation_plan=validation_plan,
                validation_results={},
                consent_receipt_refs=["run/consent-receipts/receipt-project-state.json"],
            )
            project_state.write_state_atomic(root, state)
            result = pi_contextforge_shim_dry_run.dry_run(
                root,
                {
                    "context7_server": [{"name": "context7-local-resolve-library-id"}],
                    "github_server": [{"name": "github-search-repositories"}, {"name": "github-create-issue"}],
                },
            )

        names = {tool["pi_name"] for tool in result["registered_tools"]}
        blocked = {tool["mcp_name"] for tool in result["registered_tools"] if tool["blocked_by_default"]}
        validation_by_service = {item["service_binding"]: item for item in result["validation_signals"]}
        self.assertTrue(any(name.startswith("cf_context7_s") and name.endswith("__context7-local-resolve-library-id") for name in names))
        self.assertTrue(any(name.startswith("cf_github_s") and name.endswith("__github-search-repositories") for name in names))
        self.assertIn("github-create-issue", blocked)
        self.assertEqual("safe_probe_available", validation_by_service["context7:canonical"]["status"])
        self.assertEqual("context7-local-resolve-library-id", validation_by_service["context7:canonical"]["mcp_name"])
        self.assertEqual("safe_probe_available", validation_by_service["github:canonical"]["status"])
        self.assertEqual("github-search-repositories", validation_by_service["github:canonical"]["mcp_name"])
        self.assertTrue(result["target_client_visible"])

    def test_pi_shim_dry_run_reports_explicit_validation_skip_when_no_safe_tool_matches(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            selected = [service_descriptor("context7")]
            config_plan = binding.plan_project_init_target_client_activation(root, selected, target_client="pi")
            validation_plan = binding.build_project_init_validation_plan(selected, validation_mode="pending_choice", target_client="pi")
            state = project_state.apply_project_init_activation_to_state(
                project_state.default_state(root),
                selected,
                target_client="pi",
                client_config_plan=config_plan,
                validation_plan=validation_plan,
                validation_results={},
                consent_receipt_refs=["run/consent-receipts/receipt-project-state.json"],
            )
            project_state.write_state_atomic(root, state)
            result = pi_contextforge_shim_dry_run.dry_run(
                root,
                {"context7_server": [{"name": "context7-local-dangerous-write"}]},
            )

        self.assertEqual("skipped", result["validation_signals"][0]["status"])
        self.assertEqual("no_matching_safe_pi_tool", result["validation_signals"][0]["skipped_reason"])

    def test_pi_helper_reports_installed_when_shim_metadata_is_current(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            selected = [service_descriptor("context7")]
            config_plan = binding.plan_project_init_target_client_activation(root, selected, target_client="pi")
            validation_plan = binding.build_project_init_validation_plan(selected, validation_mode="installed", target_client="pi")
            state = project_state.apply_project_init_activation_to_state(
                project_state.default_state(root),
                selected,
                target_client="pi",
                client_config_plan=config_plan,
                validation_plan=validation_plan,
                validation_results={},
                consent_receipt_refs=["run/consent-receipts/receipt-project-state.json"],
            )
            project_state.write_state_atomic(root, state)

            capabilities = helper.list_available_capabilities(project_root=root, client_type="pi")
            proposal = helper.propose_project_init(project_root=root, selected_services=[service_descriptor("github")], client_type="pi")

        self.assertEqual("client_reload_required", capabilities["status"])
        self.assertEqual("pi-project-init-installed", capabilities["next_turn"]["question_id"])
        self.assertEqual(["context7:canonical"], capabilities["current_job"]["selected_service_bindings"])
        self.assertEqual("client_reload_required", proposal["status"])
        self.assertEqual("pi-project-init-installed", proposal["next_turn"]["question_id"])

    def test_client_reload_acknowledgement_rejects_validation_intent(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            selected = [service_descriptor("context7")]
            config_plan = binding.plan_project_init_target_client_activation(root, selected, target_client="opencode")
            (root / "opencode.json").write_text(str(config_plan["next_text"]), encoding="utf-8")
            validation_plan = binding.build_project_init_validation_plan(selected, validation_mode="pending_choice", target_client="opencode")
            state = project_state.apply_project_init_activation_to_state(
                project_state.default_state(root),
                selected,
                target_client="opencode",
                client_config_plan=config_plan,
                validation_plan=validation_plan,
                validation_results={},
                consent_receipt_refs=["run/consent-receipts/receipt-project-state.json"],
            )
            written = project_state.write_state_atomic(root, state)

            job_id = written["project_init"]["current_job_id"]
            pending_job = written["project_init"]["activation_jobs"][job_id]
            pending_client_state = written["project_init"]["client_states"]["opencode"]
            with self.assertRaisesRegex(helper.ProjectInitHelperError, "install-only"):
                helper.record_project_init_client_reload(
                    project_root=root,
                    client_type="opencode",
                    validation_mode="validate_now",
                )
            after = project_state.load_state(root)

        self.assertEqual("pending_reload", pending_job["x_client_reload_fsm"]["state"])
        self.assertEqual("pending_reload", pending_client_state["reload_status"])
        self.assertEqual(written, after)

    def test_client_reload_acknowledgement_rejects_presume_working_intent(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            selected = [service_descriptor("context7")]
            config_plan = binding.plan_project_init_target_client_activation(root, selected, target_client="pi")
            validation_plan = binding.build_project_init_validation_plan(selected, validation_mode="pending_choice", target_client="pi")
            state = project_state.apply_project_init_activation_to_state(
                project_state.default_state(root),
                selected,
                target_client="pi",
                client_config_plan=config_plan,
                validation_plan=validation_plan,
                validation_results={},
                consent_receipt_refs=["run/consent-receipts/receipt-project-state.json"],
            )
            project_state.write_state_atomic(root, state)
            before = project_state.load_state(root)

            with self.assertRaisesRegex(helper.ProjectInitHelperError, "install-only"):
                record_pi_reload(root, validation_mode="presume_working")
            after = project_state.load_state(root)

        self.assertEqual(before, after)

    def test_reset_current_project_removes_helper_owned_project_init_surfaces(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            selected = [service_descriptor("context7")]

            (root / ".codex").mkdir()
            (root / ".codex" / "config.toml").write_text('[mcp_servers.keep]\ncommand = "keep"\n', encoding="utf-8")
            codex_plan = binding.plan_project_init_target_client_activation(root, selected, target_client="codex")
            (root / ".codex" / "config.toml").write_text(str(codex_plan["next_text"]), encoding="utf-8")

            (root / "opencode.json").write_text(
                json.dumps({"mcp": {"keep": {"type": "local", "command": ["keep"], "enabled": True}}}) + "\n",
                encoding="utf-8",
            )
            opencode_plan = binding.plan_project_init_target_client_activation(root, selected, target_client="opencode")
            (root / "opencode.json").write_text(str(opencode_plan["next_text"]), encoding="utf-8")

            (root / ".gemini").mkdir()
            (root / ".gemini" / "settings.json").write_text(
                json.dumps({"mcpServers": {"keep": {"command": "keep", "args": []}}}) + "\n",
                encoding="utf-8",
            )
            gemini_plan = binding.plan_project_init_target_client_activation(root, selected, target_client="gemini")
            (root / ".gemini" / "settings.json").write_text(str(gemini_plan["next_text"]), encoding="utf-8")

            state = project_state.default_state(root)
            for target_client, config_plan in (
                ("codex", codex_plan),
                ("opencode", opencode_plan),
                ("gemini", gemini_plan),
            ):
                state = project_state.apply_project_init_activation_to_state(
                    state,
                    selected,
                    target_client=target_client,
                    client_config_plan=config_plan,
                    validation_plan=binding.build_project_init_validation_plan(
                        selected,
                        validation_mode="installed",
                        target_client=target_client,
                    ),
                    validation_results={},
                    consent_receipt_refs=CONSENT_REFS,
                )
            project_state.write_state_atomic(root, state)

            result = helper.reset_current_project(project_root=root, client_type="codex")
            repeat = helper.reset_current_project(project_root=root, client_type="codex", preserve_evidence=False)

            self.assertEqual("reset", result["status"])
            self.assertTrue(result["postcondition"])
            self.assertFalse(project_state.project_state_path(root).exists())
            self.assertTrue(Path(str(result["evidence_dir"])).exists())
            self.assertTrue((Path(str(result["evidence_dir"])) / "manifest.json").exists())
            codex_text = (root / ".codex" / "config.toml").read_text(encoding="utf-8")
            self.assertIn("[mcp_servers.keep]", codex_text)
            self.assertNotIn(binding.PROJECT_INIT_OWNER_MARKER, codex_text)
            opencode_config = json.loads((root / "opencode.json").read_text(encoding="utf-8"))
            self.assertEqual(["keep"], sorted(opencode_config["mcp"]))
            gemini_config = json.loads((root / ".gemini" / "settings.json").read_text(encoding="utf-8"))
            self.assertEqual(["keep"], sorted(gemini_config["mcpServers"]))
            self.assertEqual("reset", repeat["status"])
            self.assertEqual([], repeat["actions"])

    def test_project_reset_is_available_through_mcp_and_pi_cli(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            state = project_state.default_state(root)
            project_state.write_state_atomic(root, state)

            mcp_result = contextforge_helper_mcp.cf_project_reset_current_project(
                str(root),
                client_type="codex",
                preserve_evidence=False,
            )
            project_state.write_state_atomic(root, state)
            cli_result = pi_project_init_helper_cli.dispatch(
                "cf_project_reset_current_project",
                {"project_root": str(root), "client_type": "pi", "preserve_evidence": False},
            )

            self.assertTrue(mcp_result["ok"])
            self.assertEqual("reset", mcp_result["status"])
            self.assertTrue(cli_result["ok"])
            self.assertEqual("reset", cli_result["status"])

    def test_pi_reload_acknowledgement_changes_normal_readback_contract(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            selected = [service_descriptor("context7")]
            config_plan = binding.plan_project_init_target_client_activation(root, selected, target_client="pi")
            validation_plan = binding.build_project_init_validation_plan(selected, validation_mode="installed", target_client="pi")
            state = project_state.apply_project_init_activation_to_state(
                project_state.default_state(root),
                selected,
                target_client="pi",
                client_config_plan=config_plan,
                validation_plan=validation_plan,
                validation_results={},
                consent_receipt_refs=["run/consent-receipts/receipt-project-state.json"],
            )
            project_state.write_state_atomic(root, state)

            pending_readback = contextforge_helper_mcp.project_state_readback(str(root), client_type="pi")
            ack = record_pi_reload(root)
            acknowledged_readback = contextforge_helper_mcp.project_state_readback(str(root), client_type="pi")
            acknowledged_availability = contextforge_helper_mcp.project_tool_availability(str(root), client_type="pi")
            acknowledged_summary = contextforge_helper_mcp.project_capability_summary(str(root), client_type="pi")

        self.assertEqual("pending_reload", pending_readback["current_session_boundary"]["reload_status"])
        self.assertEqual("reload_acknowledged", ack["current_job"]["client_reload_fsm"]["state"])
        for result in (acknowledged_readback, acknowledged_availability, acknowledged_summary):
            with self.subTest(status=result["status"]):
                self.assertEqual("reload_acknowledged", result["current_session_boundary"]["reload_status"])
                self.assertEqual("reload_acknowledged", result["current_session_boundary"]["user_status"])
                self.assertFalse(result["current_session_boundary"]["requires_reload"])
                self.assertTrue(result["current_session_boundary"]["reload_acknowledged"])
                self.assertTrue(result["assistant_visible_response_policy"]["internal_status_terms_suppressed"])
        self.assertEqual(
            "projection recorded; reload acknowledged",
            acknowledged_readback["target_client_services"][0]["target_client_user_state"],
        )
        self.assertEqual(
            "shim_activation_planned",
            acknowledged_readback["target_client_services"][0]["target_client_state"]["status"],
        )

    def test_pi_helper_detects_and_repairs_installed_shim_metadata_drift(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            selected = [service_descriptor("context7"), service_descriptor("github")]
            config_plan = binding.plan_project_init_target_client_activation(root, selected, target_client="pi")
            validation_plan = binding.build_project_init_validation_plan(selected, validation_mode="installed", target_client="pi")
            state = project_state.apply_project_init_activation_to_state(
                project_state.default_state(root),
                selected,
                target_client="pi",
                client_config_plan=config_plan,
                validation_plan=validation_plan,
                validation_results={},
                consent_receipt_refs=["run/consent-receipts/receipt-project-state.json"],
            )
            state["services"]["github:canonical"]["target_clients"].pop("pi")
            project_state.write_state_atomic(root, state)

            capabilities = helper.list_available_capabilities(project_root=root, client_type="pi")
            repair = helper.repair_pending_project_init_config(project_root=root, client_type="pi")
            repaired_state = project_state.load_state(root)
            after = helper.list_available_capabilities(project_root=root, client_type="pi")

        self.assertEqual("config_repair_required", capabilities["status"])
        self.assertEqual("repair-pi-shim-activation-metadata", capabilities["next_turn"]["question_id"])
        self.assertEqual(["github:canonical"], capabilities["config_repair"]["changed_service_bindings"])
        self.assertEqual("config_repaired", repair["status"])
        self.assertFalse((root / ".codex/config.toml").exists())
        assert repaired_state is not None
        self.assertEqual("contextforge-global-shim", repaired_state["services"]["github:canonical"]["target_clients"]["pi"]["shim"])
        self.assertEqual("client_reload_required", after["status"])
        self.assertEqual("pi-project-init-installed", after["next_turn"]["question_id"])

    def test_pi_helper_records_installation_without_post_install_validation(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            selected = [service_descriptor("context7")]
            config_plan = binding.plan_project_init_target_client_activation(root, selected, target_client="pi")
            validation_plan = binding.build_project_init_validation_plan(selected, validation_mode="installed", target_client="pi")
            state = project_state.apply_project_init_activation_to_state(
                project_state.default_state(root),
                selected,
                target_client="pi",
                client_config_plan=config_plan,
                validation_plan=validation_plan,
                validation_results={},
                consent_receipt_refs=["run/consent-receipts/receipt-project-state.json"],
            )
            project_state.write_state_atomic(root, state)
            written = project_state.load_state(root)

        self.assertFalse((root / ".codex/config.toml").exists())
        assert written is not None
        self.assertEqual("initialized", written["status"])
        service = written["services"]["context7:canonical"]
        self.assertEqual("installed", service["target_clients"]["pi"]["validation_status"])
        self.assertEqual("installed", service["verification_layers"]["target_client"]["status"])

    def test_pi_helper_retired_validation_operation_does_not_restore_safe_policy(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            selected = [service_descriptor("context7")]
            config_plan = binding.plan_project_init_target_client_activation(root, selected, target_client="pi")
            validation_plan = binding.build_project_init_validation_plan(selected, validation_mode="pending_choice", target_client="pi")
            state = project_state.apply_project_init_activation_to_state(
                project_state.default_state(root),
                selected,
                target_client="pi",
                client_config_plan=config_plan,
                validation_plan=validation_plan,
                validation_results={},
                consent_receipt_refs=["run/consent-receipts/receipt-project-state.json"],
            )
            state["services"]["context7:canonical"]["verification_layers"]["tool_policy"]["policy"] = None
            project_state.write_state_atomic(root, state)

            record_pi_reload(root)
            result = helper.record_project_init_validation(
                project_root=root,
                client_type="pi",
                validation_mode="validate_now",
                validation_results={"context7:canonical": pi_safe_probe_validation()},
            )
            written = project_state.load_state(root)

        self.assert_validation_operation_retired(result)
        assert written is not None
        policy = written["services"]["context7:canonical"]["verification_layers"]["tool_policy"]["policy"]
        self.assertIsNone(policy)
        self.assertNotEqual("passed", written["services"]["context7:canonical"]["target_clients"]["pi"]["validation_status"])


    def test_pi_global_shim_install_plan_is_explicit_and_non_mutating_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            target = Path(tmp) / "target"
            source.mkdir()
            (source / "index.ts").write_text("export default function shim() {}\n", encoding="utf-8")
            (source / "README.md").write_text("# shim\n", encoding="utf-8")
            (source / "package.json").write_text('{"type":"module"}\n', encoding="utf-8")
            plan = manage_pi_global_shim.install_plan(source, target)
            status = manage_pi_global_shim.directory_status(source, target)
            with self.assertRaisesRegex(ValueError, "refusing user-global Pi extension write"):
                manage_pi_global_shim.apply_install(source, target, confirmation=None)
            installed = manage_pi_global_shim.apply_install(
                source,
                target,
                confirmation=manage_pi_global_shim.CONFIRM_FLAG,
            )
            root_config = json.loads((target / "contextforge-root.json").read_text(encoding="utf-8"))

        self.assertEqual("not_installed", status["status"])
        self.assertEqual("install_or_upgrade_user_global_pi_extension", plan["operation"])
        self.assertIn("I_APPROVE_USER_GLOBAL_PI_EXTENSION_WRITE", plan["requires_explicit_confirmation"])
        self.assertIn(str(target / "contextforge-root.json"), plan["planned_writes"])
        self.assertIn(str(Path.home() / ".pi" / "agent" / "extensions" / "mcp-bridge"), plan["planned_non_writes"])
        self.assertEqual(str(REPO_ROOT), root_config["portalRoot"])
        self.assertEqual("/reload", plan["client_reload"]["command"])
        self.assertEqual("pi-client-reload-after-install", plan["next_turn"]["question_id"])
        self.assertIn("newly installed ContextForge tools register", plan["next_turn"]["prompt"])
        self.assertIn("/reload", plan["next_turn"]["prompt"])
        self.assertNotIn("validate", plan["next_turn"]["allowed_response_shape"])
        self.assertNotIn("skip validation", plan["next_turn"]["allowed_response_shape"])
        self.assertEqual(1, plan["next_turn"]["choices"][0]["number"])
        self.assertEqual("installed_current", installed["status"])
        self.assertEqual("/reload", installed["client_reload"]["command"])
        self.assertIn("issue /reload in Pi", installed["next_action"])

    def test_pi_extension_source_registers_bootstrap_helper_tools_without_bridge_reuse(self) -> None:
        text = (REPO_ROOT / "pi-extensions/contextforge-global-shim/index.ts").read_text(encoding="utf-8")

        self.assertIn("cf_project_init_list_capabilities", text)
        self.assertIn("cf_project_init_approve", text)
        self.assertNotIn("cf_project_init_record_client_reload", text)
        self.assertIn("pi_project_init_helper_cli.py", text)
        self.assertNotIn('pi.on("input"', text)
        self.assertNotIn('action: "transform"', text)
        self.assertIn('pi.on("before_agent_start"', text)
        self.assertIn("injectProjectInitPrompt", text)
        self.assertIn("contextforge-project-init-first-prompt", text)
        self.assertIn("firstPromptInitOffered", text)
        self.assertIn("display: false", text)
        self.assertIn("Use the current Pi session transcript to decide whether this is the first project-init turn or a continuation", text)
        self.assertIn("call only `cf_project_init_continue`", text)
        self.assertIn("Serena language replies such as `python`", text)
        self.assertIn("Do not call direct propose, approve, or apply tools", text)
        self.assertIn("do not emit visible text before the call", text)
        self.assertIn("Visible answer banlist during project init", text)
        self.assertIn("name: \"cf_project_init_continue\"", text)
        self.assertIn("Primary Pi project setup continuation", text)
        self.assertIn("Internal fallback only when cf_project_init_continue is unavailable", text)
        self.assertIn("A numeric service selection is never approval", text)
        self.assertIn("Do not answer, resume, or return to the user's original ordinary prompt", text)
        self.assertIn("Do not invent, rename, summarize, or substitute service names from memory", text)
        self.assertIn("do not invent a service list", text)
        self.assertIn("Which ContextForge services should I activate for this project?", text)
        self.assertIn('items: { type: "string" }', text)
        self.assertIn("minItems: 1", text)
        self.assertIn("next_turn.choices[].id", text)
        self.assertIn('for example \\"context7:canonical\\"', text)
        self.assertIn('client_type: "pi"', text)
        self.assertIn("root === workspaceRoot", text)
        self.assertNotIn("systemPrompt:", text)
        self.assertIn("runHelperOperationJson", text)
        self.assertIn("projectInitCache", text)
        self.assertIn("resolveCachedPlan", text)
        self.assertIn('operation === "cf_project_init_approve"', text)
        self.assertIn('operation === "cf_project_init_apply"', text)
        self.assertIn("status: \"already_approved_from_pi_shim_cache\"", text)
        self.assertIn("status: \"already_applied_from_pi_shim_cache\"", text)
        self.assertIn('renderShell: "self"', text)
        self.assertIn("renderNothing", text)
        self.assertIn("new Container()", text)
        self.assertIn("cf_project_init_prompt", text)
        self.assertIn("record_project_init_client_reload", text)
        self.assertIn("acknowledgeReload: true", text)
        self.assertIn("piProjectReloadPending", text)
        self.assertIn("Diagnostic only", text)
        self.assertIn("cf_contextforge_pi_readback", text)
        self.assertIn("cf_contextforge_guidance_lookup", text)
        self.assertIn("listPrompts", text)
        self.assertIn("getPrompt", text)
        self.assertIn("listResources", text)
        self.assertIn("readResource", text)
        self.assertIn("prompts/list", text)
        self.assertIn("prompts/get", text)
        self.assertIn("resources/list", text)
        self.assertIn("resources/read", text)
        self.assertIn("readback.prompts", text)
        self.assertIn("readback.resources", text)
        self.assertIn("lookupGuidance", text)
        self.assertIn("guidanceLookupKeys", text)
        self.assertNotIn("cf_contextforge_pi_validate", text)
        self.assertNotIn("cf_project_init_validate", text)
        self.assertNotIn("runPiValidation", text)
        self.assertNotIn("Call cf_project_init_record_validation", text)
        self.assertIn("await activateProject(pi, projectRootFromParams(params, ctx), clients, { acknowledgeReload: true })", text)
        self.assertIn("routeNamesByKey", text)
        self.assertIn("stableRouteToolName", text)
        self.assertIn("routeKeyFor(service, mcpTool)", text)
        self.assertIn("service.contextforgeServerId", text)
        self.assertIn("GLOBAL_STATE_KEY", text)
        self.assertIn("globalThis", text)
        self.assertIn("registerToolOnce", text)
        self.assertIn("registeredToolNames.has(name)", text)
        self.assertIn("projectInitHookPromptState", text)
        self.assertIn("completed_unverified", text)
        self.assertIn("serviceIdentityToolSegment", text)
        self.assertIn("shouldRefreshAfterHelperOperation", text)
        self.assertIn("acceptStderr(chunk)", text)
        self.assertIn("contextforge-root.json", text)
        self.assertIn("CONTEXTFORGE_PI_SHIM_WORKSPACE_ROOT", text)
        self.assertNotIn("pi.registerTool({", text)
        self.assertNotIn("DEFAULT_PORTAL_ROOT", text)
        self.assertNotIn("/home/dgk/workspace", text)
        self.assertNotIn("console.error", text)
        self.assertNotIn("mcp-bridge", text)
        self.assertNotIn("registerContext7Tools", text)

    def test_pi_project_init_source_has_no_record_validation_payload_template(self) -> None:
        text = (REPO_ROOT / "pi-extensions/contextforge-global-shim/index.ts").read_text(encoding="utf-8")

        self.assertNotIn("function recordValidationResult", text)
        self.assertNotIn("validation_results", text)
        self.assertNotIn("copy this exact top-level validation_results object", text)
        self.assertIn("cf_project_init_apply", text)
        self.assertIn("ContextForge tools are installed", text)

    def test_pi_helper_cli_stdout_is_clean_json(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            result = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts/pi_project_init_helper_cli.py"),
                    "--operation",
                    "get_project_context",
                    "--payload-json",
                    json.dumps({"project_root": str(root)}),
                ],
                check=False,
                capture_output=True,
                text=True,
                cwd=REPO_ROOT,
            )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue(result.stdout.startswith("{"), result.stdout[:200])
        parsed = json.loads(result.stdout)
        self.assertTrue(parsed["ok"])
        self.assertEqual("pi", parsed["client_type"])

    def test_pi_helper_cli_service_onboarding_plan_rejects_synthetic_source_summary(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            result = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts/pi_project_init_helper_cli.py"),
                    "--operation",
                    "build_service_onboarding_plan",
                    "--payload-json",
                    json.dumps(
                        {
                            "project_root": str(root),
                            "candidateService": "calendar-notes",
                            "sourcePath": "user-supplied: reads project notes and exposes search over meeting summaries",
                            "transportType": "stdio",
                            "localizationType": "project_scoped",
                            "functionalType": "search_retrieval",
                            "stateType": "local_filesystem_state",
                            "approvalType": "source_only",
                            "credentialRequired": False,
                        }
                    ),
                ],
                check=False,
                capture_output=True,
                text=True,
                cwd=REPO_ROOT,
            )

        self.assertEqual(0, result.returncode, result.stderr)
        parsed = json.loads(result.stdout)
        self.assertTrue(parsed["ok"])
        self.assertEqual("source_only_onboarding_plan", parsed["status"])
        self.assertFalse(parsed["mutation_allowed"])
        self.assertEqual("needs_user_input", parsed["record"]["status"])
        self.assertEqual([], parsed["record"]["source_evidence"])
        self.assertIn("Please provide the source reference or local path", parsed["assistant_visible_response"])
        self.assertIn("No service has been installed, registered, started, exposed, imported, validated, probed, or made available", parsed["assistant_visible_response"])

    def test_contextforge_helper_mcp_exposes_cached_project_init_id_digest_tools(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            proposal = contextforge_helper_mcp.cf_project_init_propose(
                project_root=str(root),
                selected_services=["context7:canonical"],
                client_type="codex",
            )
            challenge = proposal["approval_challenge"]
            approval = contextforge_helper_mcp.cf_project_init_approve(
                project_root=str(root),
                challenge_id=challenge["challenge_id"],
                plan_digest=proposal["plan_digest"],
            )
            applied = contextforge_helper_mcp.cf_project_init_apply(project_root=str(root), dry_run=True)

        self.assertTrue(proposal["ok"])
        self.assertEqual("allow", approval["decision"])
        self.assertTrue(applied["ok"])
        self.assertIn("next_turn", applied)

    def test_helper_lists_capabilities_with_single_selection_turn(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            capabilities = helper.list_available_capabilities(
                project_root=Path(tmp).resolve(),
                contextforge_servers=[{"name": "context7_local_server", "id": "vs-context7"}],
            )

        self.assertTrue(capabilities["next_turn"]["must_stop"])
        self.assertEqual("select-services", capabilities["next_turn"]["question_id"])
        self.assertEqual("multi_select", capabilities["next_turn"]["response_form"]["type"])
        self.assertTrue(all("number" in choice for choice in capabilities["next_turn"]["choices"]))
        self.assertIn("context7:canonical", {choice["id"] for choice in capabilities["next_turn"]["choices"]})
        self.assertIn("discovery is read-only", capabilities["non_actions"])
        context7 = next(item for item in capabilities["available_services"] if item["service_binding"] == "context7:canonical")
        self.assertEqual("shared_canonical", context7["menu_group"])
        self.assertEqual("shared canonical binding", context7["scope_label"])

    def test_all_project_init_next_turn_choices_are_numbered(self) -> None:
        def assert_numbered(turn: dict[str, Any]) -> None:
            self.assertTrue(turn["choices"])
            self.assertEqual(turn["choices"], turn["response_form"]["options"])
            if "selection numbers are not accepted" in turn["allowed_response_shape"]:
                self.assertTrue(all("number" not in choice for choice in turn["choices"]))
            else:
                self.assertEqual(list(range(1, len(turn["choices"]) + 1)), [choice["number"] for choice in turn["choices"]])
                self.assertIn("selection number", turn["allowed_response_shape"])

        assert_numbered(helper.installation_complete_turn(client_type="pi", reload_requirement=common.client_reload_requirement("pi", event="project_activation_apply")))
        assert_numbered(helper.installation_complete_turn(client_type="codex", reload_requirement=common.client_reload_requirement("codex", event="project_activation_apply")))
        assert_numbered(helper.config_repair_turn(client_type="pi"))
        assert_numbered(helper.config_repair_turn(client_type="codex"))
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            capabilities = helper.list_available_capabilities(
                project_root=root,
                contextforge_servers=[{"name": "context7_local_server", "id": "vs-context7"}],
            )
            proposal = helper.propose_project_init(project_root=root, selected_services=[service_descriptor("context7")])
        assert_numbered(capabilities["next_turn"])
        self.assertEqual("multi_select", capabilities["next_turn"]["response_form"]["type"])
        assert_numbered(proposal["next_turn"])

    def test_declined_service_decision_blocks_active_import_and_remains_readable(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            result = helper.record_project_init_service_decision(
                project_root=root,
                selected_services=[service_descriptor("context7")],
                decision_state="declined",
                client_type="pi",
            )
            state = project_state.load_state(root)
            availability = contextforge_helper_mcp.project_tool_availability(project_root=str(root), client_type="pi")
            capabilities = contextforge_helper_mcp.project_capability_summary(project_root=str(root), client_type="pi")

        self.assertTrue(result["ok"])
        self.assertEqual("service_declined", result["status"])
        self.assertEqual("initialized", state["status"])
        self.assertEqual("declined", state["decisions"]["context7:canonical"]["state"])
        self.assertNotIn("context7:canonical", state["services"])
        self.assertEqual([], availability["approved_service_bindings"])
        self.assertEqual("declined", availability["skipped_or_unavailable_services"][0]["status"])
        self.assertNotIn("context7:canonical", {item["service_binding"] for item in capabilities["onboarding_needed"]})

    def test_declined_service_decision_suppresses_inconsistent_active_service_state(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            service = service_descriptor("context7")
            state = project_state.apply_project_init_activation_to_state(
                project_state.default_state(root),
                [service],
                target_client="pi",
                client_config_plan={
                    "surface": "project_state_shim_metadata",
                    "scope": "project_local",
                    "decision": "allow_project_state_shim_binding",
                    "changes": [],
                    "writes": [],
                    "non_actions": [],
                },
                validation_plan=binding.build_project_init_validation_plan([service], validation_mode="pending_choice"),
                consent_receipt_refs=CONSENT_REFS,
            )
            state = project_state.apply_project_init_decisions_to_state(
                state,
                [service],
                target_client="pi",
                decision_state="declined",
            )
            project_state.write_state_atomic(root, state)

            availability = contextforge_helper_mcp.project_tool_availability(project_root=str(root), client_type="pi")

        self.assertEqual([], availability["approved_service_bindings"])
        self.assertEqual([], availability["available_tools"])
        self.assertEqual("declined", availability["skipped_or_unavailable_services"][0]["status"])

    def test_mcp_continuation_decline_records_cached_plan_decision(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            approval_source = root / "latest-user.json"
            with mock.patch.dict(os.environ, {"CONTEXTFORGE_HELPER_APPROVAL_SOURCE_PATH": str(approval_source)}, clear=False):
                proposal = contextforge_helper_mcp.cf_project_init_propose(
                    project_root=str(root),
                    selected_services=["context7:canonical"],
                    client_type="opencode",
                )
                approval_source.write_text(json.dumps({"cwd": str(root), "text": "decline"}), encoding="utf-8")
                result = contextforge_helper_mcp.cf_project_init_continue(project_root=str(root), client_type="opencode")
                state = project_state.load_state(root)

        self.assertTrue(proposal["ok"])
        self.assertTrue(result["ok"])
        self.assertEqual("declined", result["decision_state"])
        self.assertIn("assistant_visible_response", result)
        self.assertEqual("declined", state["decisions"]["context7:canonical"]["state"])
        self.assertNotIn("context7:canonical", state["services"])

    def test_mcp_continuation_defer_records_pending_serena_decision(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            approval_source = root / "latest-user.json"
            with mock.patch.dict(os.environ, {"CONTEXTFORGE_HELPER_APPROVAL_SOURCE_PATH": str(approval_source)}, clear=False):
                proposal = contextforge_helper_mcp.cf_project_init_propose(
                    project_root=str(root),
                    selected_services=[serena_descriptor()],
                    client_type="pi",
                )
                approval_source.write_text(json.dumps({"cwd": str(root), "text": "defer"}), encoding="utf-8")
                result = contextforge_helper_mcp.cf_project_init_continue(project_root=str(root), client_type="pi")
                state = project_state.load_state(root)

        self.assertTrue(proposal["ok"])
        self.assertEqual("needs_input", proposal["status"])
        self.assertTrue(result["ok"])
        serena_key = next(key for key in state["decisions"] if key.startswith("serena:"))
        self.assertEqual("deferred", state["decisions"][serena_key]["state"])
        self.assertEqual({}, state["services"])

    def test_helper_completes_install_only_flow_after_reload_acknowledgment(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            service = service_descriptor("context7")
            config_plan = binding.plan_project_init_codex_config_write(root, [service], existing_text="")
            (root / ".codex").mkdir()
            (root / ".codex/config.toml").write_text(config_plan["next_text"], encoding="utf-8")
            validation_plan = binding.build_project_init_validation_plan([service], validation_mode="pending_choice")
            state = project_state.apply_project_init_activation_to_state(
                project_state.default_state(root),
                [service],
                target_client="codex",
                client_config_plan=config_plan,
                validation_plan=validation_plan,
                validation_results={},
                consent_receipt_refs=CONSENT_REFS,
            )
            project_state.write_state_atomic(root, state)

            capabilities = helper.list_available_capabilities(project_root=root)
            proposal = helper.propose_project_init(project_root=root, selected_services=[service_descriptor("github")])
            ack = helper.record_project_init_client_reload(project_root=root, client_type="codex")
            after_ack = helper.list_available_capabilities(project_root=root)

        self.assertEqual("client_reload_required", capabilities["status"])
        self.assertEqual("codex-project-init-installed", capabilities["next_turn"]["question_id"])
        self.assertEqual(["context7:canonical"], capabilities["current_job"]["selected_service_bindings"])
        self.assertEqual("client_reload_required", proposal["status"])
        self.assertEqual("codex-project-init-installed", proposal["next_turn"]["question_id"])
        self.assertEqual("client_reload_recorded", ack["status"])
        self.assertIn("available_services", after_ack)
        self.assertNotEqual("installed_reload_required", after_ack.get("status"))

    def test_helper_allows_new_selection_after_install_only_reload_acknowledgment(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            service = service_descriptor("context7")
            config_plan = binding.plan_project_init_codex_config_write(root, [service], existing_text="")
            (root / ".codex").mkdir()
            (root / ".codex/config.toml").write_text(config_plan["next_text"], encoding="utf-8")
            validation_plan = binding.build_project_init_validation_plan([service], validation_mode="installed", target_client="codex")
            state = project_state.apply_project_init_activation_to_state(
                project_state.default_state(root),
                [service],
                target_client="codex",
                client_config_plan=config_plan,
                validation_plan=validation_plan,
                validation_results={},
                consent_receipt_refs=CONSENT_REFS,
            )
            project_state.write_state_atomic(root, state)

            blocked = helper.propose_project_init(project_root=root, selected_services=[service_descriptor("github")])
            ack = helper.record_project_init_client_reload(project_root=root, client_type="codex")
            capabilities = helper.list_available_capabilities(project_root=root)
            proposal = helper.propose_project_init(project_root=root, selected_services=[service_descriptor("github")])

        self.assertEqual("client_reload_required", blocked["status"])
        self.assertEqual("client_reload_recorded", ack["status"])
        self.assertNotIn("next_turn", ack)
        self.assertIn("available_services", capabilities)
        self.assertEqual("approve-project-init-plan", proposal["next_turn"]["question_id"])
        self.assertEqual("github:canonical", proposal["plan_summary"]["bindings"][0]["service_binding"])

    def test_helper_detects_and_repairs_pending_config_drift_before_install_completion(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            selected = [service_descriptor("context7"), service_descriptor("github")]
            partial = binding.plan_project_init_codex_config_write(root, [selected[0]], existing_text="")
            full = binding.plan_project_init_codex_config_write(root, selected, existing_text="")
            (root / ".codex").mkdir()
            (root / ".codex/config.toml").write_text(partial["next_text"], encoding="utf-8")
            validation_plan = binding.build_project_init_validation_plan(selected, validation_mode="pending_choice")
            state = project_state.apply_project_init_activation_to_state(
                project_state.default_state(root),
                selected,
                target_client="codex",
                client_config_plan=full,
                validation_plan=validation_plan,
                validation_results={},
                consent_receipt_refs=CONSENT_REFS,
            )
            project_state.write_state_atomic(root, state)

            capabilities = helper.list_available_capabilities(project_root=root)
            blocked_validation = helper.record_project_init_validation(
                project_root=root,
                validation_mode="validate_now",
                validation_results={"context7:canonical": {"status": "passed", "target_client_visible": True}},
                dry_run=True,
            )
            repair = helper.repair_pending_project_init_config(project_root=root)
            config_text = (root / ".codex/config.toml").read_text(encoding="utf-8")
            after = helper.list_available_capabilities(project_root=root)
            ack = helper.record_project_init_client_reload(project_root=root, client_type="codex")
            after_ack = helper.list_available_capabilities(project_root=root)

        self.assertEqual("config_repair_required", capabilities["status"])
        self.assertEqual("repair-project-local-config", capabilities["next_turn"]["question_id"])
        self.assert_validation_operation_retired(blocked_validation)
        self.assertEqual("config_repaired", repair["status"])
        self.assertIn("[mcp_servers.github]", config_text)
        self.assertEqual("client_reload_required", after["status"])
        self.assertEqual("codex-project-init-installed", after["next_turn"]["question_id"])
        self.assertEqual("client_reload_recorded", ack["status"])
        self.assertIn("available_services", after_ack)
        self.assertNotEqual("installed_reload_required", after_ack.get("status"))

    def test_helper_repairs_missing_project_init_state_without_overwriting_unmanaged_codex_config(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            service = service_descriptor("context7")
            unmanaged_config = "[mcp_servers.context7]\ncommand = \"npx\"\n"
            (root / ".codex").mkdir()
            (root / ".codex/config.toml").write_text(unmanaged_config, encoding="utf-8")
            config_plan = binding.plan_project_init_codex_config_write(root, [service], existing_text=unmanaged_config)
            validation_plan = binding.build_project_init_validation_plan([service], validation_mode="pending_choice")
            raw = project_state.apply_project_init_activation_to_state(
                project_state.default_state(root),
                [service],
                target_client="codex",
                client_config_plan=config_plan,
                validation_plan=validation_plan,
                validation_results={},
                consent_receipt_refs=CONSENT_REFS,
            )
            raw.pop("project_init")
            project_state.project_state_path(root).parent.mkdir(parents=True)
            project_state.project_state_path(root).write_text(json.dumps(raw), encoding="utf-8")

            capabilities = helper.list_available_capabilities(project_root=root)
            repaired = helper.repair_pending_project_init_config(project_root=root)
            config_after = (root / ".codex/config.toml").read_text(encoding="utf-8")
            resume = helper.list_available_capabilities(project_root=root)
            ack = record_codex_new_session(root)
            after_ack = helper.list_available_capabilities(project_root=root)
            presumed = helper.record_project_init_validation(project_root=root, validation_mode="presume_working")
            written = project_state.load_state(root)

        self.assertEqual("state_repair_required", capabilities["status"])
        self.assertEqual("repair-project-init-state", capabilities["next_turn"]["question_id"])
        self.assertEqual("state_repaired", repaired["status"])
        self.assertEqual(unmanaged_config, config_after)
        self.assertEqual("client_reload_required", resume["status"])
        self.assertEqual("codex-project-init-installed", resume["next_turn"]["question_id"])
        self.assertEqual("client_reload_recorded", ack["status"])
        self.assertIn("available_services", after_ack)
        self.assertNotEqual("installed_reload_required", after_ack.get("status"))
        self.assert_validation_operation_retired(presumed)
        assert written is not None
        self.assertEqual("completed_unverified", written["project_init"]["x_hook_prompt_state"])
        migration = written["migration"]["client_config_migrations"]["codex"]
        self.assertEqual("unmanaged_same_name", migration["ownership_class"])
        self.assertEqual("conflict", migration["disposition"])
        self.assertNotEqual("presumed_working", written["services"]["context7:canonical"]["verification_layers"]["target_client"]["status"])

    def test_retired_validation_operation_ignores_results_after_config_is_current(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            selected = [service_descriptor("context7"), service_descriptor("github")]
            config_plan = binding.plan_project_init_codex_config_write(root, selected, existing_text="")
            (root / ".codex").mkdir()
            (root / ".codex/config.toml").write_text(config_plan["next_text"], encoding="utf-8")
            validation_plan = binding.build_project_init_validation_plan(selected, validation_mode="pending_choice")
            state = project_state.apply_project_init_activation_to_state(
                project_state.default_state(root),
                selected,
                target_client="codex",
                client_config_plan=config_plan,
                validation_plan=validation_plan,
                validation_results={},
                consent_receipt_refs=CONSENT_REFS,
            )
            project_state.write_state_atomic(root, state)
            record_codex_new_session(root)

            result = helper.record_project_init_validation(
                project_root=root,
                validation_mode="validate_now",
                validation_results={
                    "context7:canonical": context7_safe_probe_validation(),
                    "github:canonical": {
                        "status": "skipped",
                        "skipped_reason": "credentials unavailable in this client turn",
                    },
                },
            )
            written = project_state.load_state(root)

        self.assert_validation_operation_retired(result)
        assert written is not None
        job = written["project_init"]["activation_jobs"][written["project_init"]["current_job_id"]]
        self.assertNotEqual("verified", job["status"])
        self.assertNotEqual("passed", written["services"]["context7:canonical"]["verification_layers"]["target_client"]["status"])
        self.assertNotEqual("skipped", written["services"]["github:canonical"]["verification_layers"]["target_client"]["status"])

    def test_retired_validation_operation_ignores_nested_results_without_recording_state(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            selected = [service_descriptor("context7")]
            config_plan = binding.plan_project_init_codex_config_write(root, selected, existing_text="")
            (root / ".codex").mkdir()
            (root / ".codex/config.toml").write_text(config_plan["next_text"], encoding="utf-8")
            state = project_state.apply_project_init_activation_to_state(
                project_state.default_state(root),
                selected,
                target_client="codex",
                client_config_plan=config_plan,
                validation_plan=binding.build_project_init_validation_plan(selected, validation_mode="pending_choice"),
                validation_results={},
                consent_receipt_refs=CONSENT_REFS,
            )
            before = project_state.write_state_atomic(root, state)
            record_codex_new_session(root)
            before = project_state.load_state(root)

            result = helper.record_project_init_validation(
                project_root=root,
                validation_mode="validate_now",
                validation_results={
                    "services": {
                        "context7:canonical": {
                            "status": "passed",
                            "target_client_visible": True,
                        }
                    }
                },
            )
            after = project_state.load_state(root)

        self.assert_validation_operation_retired(result)
        assert after is not None
        self.assertEqual(before["meta"]["revision"], after["meta"]["revision"])

    def test_retired_validation_operation_requires_no_results_and_records_no_state(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            selected = [service_descriptor("context7")]
            config_plan = binding.plan_project_init_codex_config_write(root, selected, existing_text="")
            (root / ".codex").mkdir()
            (root / ".codex/config.toml").write_text(config_plan["next_text"], encoding="utf-8")
            state = project_state.apply_project_init_activation_to_state(
                project_state.default_state(root),
                selected,
                target_client="codex",
                client_config_plan=config_plan,
                validation_plan=binding.build_project_init_validation_plan(selected, validation_mode="pending_choice"),
                validation_results={},
                consent_receipt_refs=CONSENT_REFS,
            )
            before = project_state.write_state_atomic(root, state)
            record_codex_new_session(root)
            before = project_state.load_state(root)

            result = helper.record_project_init_validation(
                project_root=root,
                validation_mode="validate_now",
            )
            after = project_state.load_state(root)

        self.assert_validation_operation_retired(result)
        assert after is not None
        self.assertEqual(before["meta"]["revision"], after["meta"]["revision"])

    def test_retired_validation_operation_ignores_unmatched_result_keys_without_recording_state(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            selected = [service_descriptor("context7")]
            config_plan = binding.plan_project_init_codex_config_write(root, selected, existing_text="")
            (root / ".codex").mkdir()
            (root / ".codex/config.toml").write_text(config_plan["next_text"], encoding="utf-8")
            state = project_state.apply_project_init_activation_to_state(
                project_state.default_state(root),
                selected,
                target_client="codex",
                client_config_plan=config_plan,
                validation_plan=binding.build_project_init_validation_plan(selected, validation_mode="pending_choice"),
                validation_results={},
                consent_receipt_refs=CONSENT_REFS,
            )
            before = project_state.write_state_atomic(root, state)
            record_codex_new_session(root)
            before = project_state.load_state(root)

            result = helper.record_project_init_validation(
                project_root=root,
                validation_mode="validate_now",
                validation_results={
                    "unselected:canonical": {
                        "status": "passed",
                        "target_client_visible": True,
                    }
                },
            )
            after = project_state.load_state(root)

        self.assert_validation_operation_retired(result)
        assert after is not None
        self.assertEqual(before["meta"]["revision"], after["meta"]["revision"])

    def test_retired_validation_operation_ignores_result_values_that_are_not_objects(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            selected = [service_descriptor("context7")]
            config_plan = binding.plan_project_init_codex_config_write(root, selected, existing_text="")
            (root / ".codex").mkdir()
            (root / ".codex/config.toml").write_text(config_plan["next_text"], encoding="utf-8")
            state = project_state.apply_project_init_activation_to_state(
                project_state.default_state(root),
                selected,
                target_client="codex",
                client_config_plan=config_plan,
                validation_plan=binding.build_project_init_validation_plan(selected, validation_mode="pending_choice"),
                validation_results={},
                consent_receipt_refs=CONSENT_REFS,
            )
            before = project_state.write_state_atomic(root, state)
            record_codex_new_session(root)
            before = project_state.load_state(root)

            result = helper.record_project_init_validation(
                project_root=root,
                validation_mode="validate_now",
                validation_results={"context7:canonical": "passed"},
            )
            after = project_state.load_state(root)

        self.assert_validation_operation_retired(result)
        assert after is not None
        self.assertEqual(before["meta"]["revision"], after["meta"]["revision"])

    def test_retired_validation_operation_ignores_complete_agent_working_report(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            selected = [service_descriptor("context7")]
            config_plan = binding.plan_project_init_codex_config_write(root, selected, existing_text="")
            (root / ".codex").mkdir()
            (root / ".codex/config.toml").write_text(config_plan["next_text"], encoding="utf-8")
            state = project_state.apply_project_init_activation_to_state(
                project_state.default_state(root),
                selected,
                target_client="codex",
                client_config_plan=config_plan,
                validation_plan=binding.build_project_init_validation_plan(selected, validation_mode="pending_choice"),
                validation_results={},
                consent_receipt_refs=CONSENT_REFS,
            )
            project_state.write_state_atomic(root, state)
            record_codex_new_session(root)

            result = helper.record_project_init_validation(
                project_root=root,
                validation_mode="validate_now",
                validation_results={
                    "context7:canonical": {
                        "status": "passed",
                        "target_client": "codex",
                        "safe_probe_result": "passed",
                        "safe_probe_id": "resolve-library-id",
                        "tool_name": "context7_context7-local-resolve-library-id",
                        "result_summary": "resolved the python library id through context7",
                    }
                },
            )
            after = project_state.load_state(root)

        self.assert_validation_operation_retired(result)
        assert after is not None
        self.assertNotEqual("passed", after["services"]["context7:canonical"]["verification_layers"]["target_client"]["status"])

    def test_retired_validation_operation_does_not_mark_service_passed(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            selected = [service_descriptor("context7")]
            config_plan = binding.plan_project_init_codex_config_write(root, selected, existing_text="")
            (root / ".codex").mkdir()
            (root / ".codex/config.toml").write_text(config_plan["next_text"], encoding="utf-8")
            state = project_state.apply_project_init_activation_to_state(
                project_state.default_state(root),
                selected,
                target_client="codex",
                client_config_plan=config_plan,
                validation_plan=binding.build_project_init_validation_plan(selected, validation_mode="pending_choice"),
                validation_results={},
                consent_receipt_refs=CONSENT_REFS,
            )
            project_state.write_state_atomic(root, state)
            record_codex_new_session(root)

            result = helper.record_project_init_validation(
                project_root=root,
                validation_mode="validate_now",
                validation_results={"context7:canonical": context7_safe_probe_validation()},
            )
            written = project_state.load_state(root)

        self.assert_validation_operation_retired(result)
        assert written is not None
        self.assertNotEqual("passed", written["services"]["context7:canonical"]["verification_layers"]["target_client"]["status"])

    def test_retired_validation_operation_ignores_mixed_results(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            selected = [service_descriptor("context7"), service_descriptor("github"), service_descriptor("web-search")]
            config_plan = binding.plan_project_init_codex_config_write(root, selected, existing_text="")
            (root / ".codex").mkdir()
            (root / ".codex/config.toml").write_text(config_plan["next_text"], encoding="utf-8")
            state = project_state.apply_project_init_activation_to_state(
                project_state.default_state(root),
                selected,
                target_client="codex",
                client_config_plan=config_plan,
                validation_plan=binding.build_project_init_validation_plan(selected, validation_mode="pending_choice"),
                validation_results={},
                consent_receipt_refs=CONSENT_REFS,
            )
            project_state.write_state_atomic(root, state)
            record_codex_new_session(root)

            result = helper.record_project_init_validation(
                project_root=root,
                validation_mode="validate_now",
                validation_results={
                    "context7:canonical": context7_safe_probe_validation(),
                    "github:canonical": {
                        "status": "skipped",
                        "skipped_reason": "credentials unavailable in this client turn",
                    },
                    "unselected:canonical": {
                        "status": "passed",
                        "target_client_visible": True,
                    },
                },
            )
            written = project_state.load_state(root)

        self.assert_validation_operation_retired(result)
        assert written is not None
        self.assertEqual("in_progress", written["status"])
        self.assertNotEqual("passed", written["services"]["context7:canonical"]["verification_layers"]["target_client"]["status"])
        self.assertNotEqual("skipped", written["services"]["github:canonical"]["verification_layers"]["target_client"]["status"])
        self.assertEqual("pending", written["services"]["web-search:canonical"]["verification_layers"]["target_client"]["status"])

    def test_contextforge_helper_mcp_exposes_readiness_tool(self) -> None:
        result = contextforge_helper_mcp.get_project_context("/home/dgk/workspace/legacy-controlplane-archive")

        self.assertTrue(result["ok"])
        self.assertEqual("contextforge-helper", result["helper"]["name"])
        self.assertEqual("available", result["helper"]["status"])
        self.assertEqual("codex", result["root_attestation"]["client_type"])

    def test_contextforge_helper_mcp_reports_initialized_tool_availability_read_only(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            selected = [service_descriptor("context7")]
            config_plan = binding.plan_project_init_target_client_activation(root, selected, target_client="opencode")
            state = project_state.apply_project_init_activation_to_state(
                project_state.default_state(root),
                selected,
                target_client="opencode",
                client_config_plan=config_plan,
                validation_plan=binding.build_project_init_validation_plan(selected, validation_mode="installed", target_client="opencode"),
                validation_results={},
                consent_receipt_refs=CONSENT_REFS,
            )
            project_state.write_state_atomic(root, state)

            full_report = contextforge_helper_mcp.project_tool_availability(str(root), client_type="opencode")
            result = contextforge_helper_mcp.get_project_tool_availability(str(root), client_type="opencode")

        self.assertEqual(["context7-local-resolve-library-id", "context7-local-query-docs"], full_report["available_tools"][0]["tool_names"])
        self.assertTrue(result["ok"])
        self.assertEqual("available_tools_report", result["status"])
        self.assertIn("assistant_visible_response", result)
        self.assertEqual(result["assistant_visible_response"], result["message"])
        self.assertTrue(result["copy_as_complete_visible_response"])
        self.assertTrue(result["do_not_summarize"])
        self.assertNotIn("available_tools", result)
        self.assertNotIn("state_revision", result)
        self.assertEqual(
            (
                f"ContextForge state for {root} is initialized at revision 1. "
                "Project services present: context7:canonical. "
                "Configured/imported-tool policy for this client: context7:canonical exposes "
                "context7-local-resolve-library-id, context7-local-query-docs. "
                "Missing target-client projections: none recorded. "
                "Skipped or unavailable services: none reported. "
                "MCP runtime diagnostics: context7:canonical: reload_pending_before_mcp_startup. "
                "client-visible tool use is not proven by this readback; target-client-visible=false states remain unproven. "
                "This is a read-only project-state readback; interactive proof is not claimed by this readback. "
                "Note: After approved OpenCode project-local MCP config changes, start a new OpenCode session from the project root before relying on the newly installed tools. "
                "OpenCode discovers project-local MCP servers and loads the user-home ContextForge plugin when a session starts."
            ),
            result["assistant_visible_response"],
        )
        self.assertIn("no project-init proposal, approval, or apply", result["non_actions"])

    def test_opencode_readback_distinguishes_mcp_startup_failure_from_reload_pending(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            selected = [service_descriptor("context7")]
            config_plan = binding.plan_project_init_target_client_activation(root, selected, target_client="opencode")
            state = project_state.apply_project_init_activation_to_state(
                project_state.default_state(root),
                selected,
                target_client="opencode",
                client_config_plan=config_plan,
                validation_plan=binding.build_project_init_validation_plan(selected, validation_mode="installed", target_client="opencode"),
                validation_results={},
                consent_receipt_refs=CONSENT_REFS,
            )
            state["services"]["context7:canonical"]["target_clients"]["opencode"]["mcp_runtime_diagnostics"] = {
                "attempted": True,
                "startup_status": "failed",
                "auth_status": "not_checked",
                "transport_status": "not_checked",
                "tool_listing_status": "not_checked",
                "error_class": "process_exit",
                "evidence_ref": "docker/client-harness/evidence/opencode-redacted-startup.log",
            }
            project_state.write_state_atomic(root, state)

            availability = contextforge_helper_mcp.project_tool_availability(str(root), client_type="opencode")
            capabilities = contextforge_helper_mcp.project_capability_summary(str(root), client_type="opencode")
            readback = contextforge_helper_mcp.project_state_readback(str(root), client_type="opencode")

        diagnostic = availability["mcp_runtime_diagnostics"][0]
        self.assertEqual("mcp_server_startup_failed", diagnostic["classification"])
        self.assertTrue(diagnostic["attempted"])
        self.assertTrue(diagnostic["secret_values_redacted"])
        self.assertEqual("not_claimed", diagnostic["validation_proof"])
        self.assertEqual("process_exit", diagnostic["error_class"])
        self.assertIn("do not ask for another reload", availability["assistant_visible_response"])
        self.assertNotIn("start a new OpenCode session", availability["assistant_visible_response"])
        self.assertIn("mcp_server_startup_failed", capabilities["assistant_visible_response"])
        self.assertIn("do not ask for another reload", capabilities["assistant_visible_response"])
        self.assertEqual(
            "mcp_server_startup_failed",
            readback["target_client_services"][0]["mcp_runtime_diagnostic"]["classification"],
        )
        self.assertEqual(
            "mcp_server_startup_failed",
            readback["target_client_services"][0]["readiness_layers"]["mcp_runtime"],
        )
        self.assertIn("MCP runtime mcp_server_startup_failed", readback["assistant_visible_response"])
        self.assertIn("do not ask for another reload", readback["assistant_visible_response"])
        self.assertIn("no validation, tool probe, backend mutation, or registry mutation", readback["non_actions"])

    def test_contextforge_helper_mcp_reports_missing_target_client_projection_without_available_tools(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            selected = [service_descriptor("context7"), service_descriptor("github")]
            config_plan = binding.plan_project_init_target_client_activation(root, selected, target_client="pi")
            state = project_state.apply_project_init_activation_to_state(
                project_state.default_state(root),
                selected,
                target_client="pi",
                client_config_plan=config_plan,
                validation_plan=binding.build_project_init_validation_plan(selected, validation_mode="installed", target_client="pi"),
                validation_results={},
                consent_receipt_refs=CONSENT_REFS,
            )
            project_state.write_state_atomic(root, state)

            availability = contextforge_helper_mcp.project_tool_availability(str(root), client_type="opencode")
            client_caps = contextforge_helper_mcp.list_available_capabilities(str(root), client_type="opencode")
            readback = contextforge_helper_mcp.project_state_readback(str(root), client_type="opencode")
            capabilities = contextforge_helper_mcp.project_capability_summary(str(root), client_type="opencode")

        expected_actions = [
            {
            "action": "align_target_client_to_existing_project_service",
            "target_client": "opencode",
                "service_binding": service_binding,
            "boundary": (
                "Align/import opencode to the existing project service instance; "
                "do not create a new project service instance unless explicitly approved."
            ),
            }
            for service_binding in ["context7:canonical", "github:canonical"]
        ]
        self.assertEqual("available_tools_report", availability["status"])
        self.assertEqual("alignment_import_offer", client_caps["status"])
        self.assertIn("alignment_import_offer", client_caps)
        self.assertEqual("align-existing-project-services", client_caps["next_turn"]["question_id"])
        self.assertEqual(2, len(client_caps["available_services"]))
        self.assertEqual(
            ["context7:canonical", "github:canonical"],
            client_caps["alignment_import_offer"]["project_service_bindings"],
        )
        self.assertEqual(
            {"context7:canonical", "github:canonical"},
            {item["service_binding"] for item in client_caps["alignment_import_offer"]["missing_target_client_projection"]},
        )
        self.assertEqual("present", client_caps["available_services"][0]["project_service_state"])
        self.assertEqual("missing", client_caps["available_services"][0]["target_client_projection_status"])
        self.assertEqual({"status": "not_recorded"}, client_caps["available_services"][0]["target_client_state"])
        self.assertFalse(client_caps["available_services"][0]["available_to_target_client"])
        self.assertEqual("Project services are already present. Import this project's existing ContextForge services for OpenCode?", client_caps["next_turn"]["prompt"])
        self.assertIn("ContextForge state for", client_caps["assistant_visible_response"])
        self.assertIn("already contains project services", client_caps["assistant_visible_response"])
        self.assertIn("Missing target-client projections for OpenCode", client_caps["assistant_visible_response"])

        self.assertEqual([], readback["imported_tools"])
        self.assertEqual(expected_actions, readback["missing_target_client_projection"])
        self.assertEqual("missing", readback["target_client_services"][0]["target_client_projection_status"])
        self.assertEqual("not_claimed", readback["target_client_services"][0]["target_client_visibility_status"])
        self.assertEqual("not_recorded", readback["target_client_services"][0]["target_client_proof_status"])
        self.assertEqual(expected_actions[0], readback["target_client_services"][0]["recommended_action"])
        self.assertIn("Project tool policy: context7:canonical: context7-local-resolve-library-id, context7-local-query-docs", readback["assistant_visible_response"])
        self.assertIn("Configured/imported-tool policy for this client: none reported.", readback["assistant_visible_response"])
        self.assertIn("projection missing; client state not_recorded", readback["assistant_visible_response"])

        self.assertEqual([], capabilities["available_now"])
        self.assertEqual(expected_actions, capabilities["missing_target_client_projection"])
        self.assertEqual("context7:canonical", capabilities["project_services"][0]["service_binding"])
        self.assertIn("Configured in current project state for opencode: none reported.", capabilities["assistant_visible_response"])
        self.assertIn("Missing target-client projections: context7:canonical", capabilities["assistant_visible_response"])

    def test_alignment_import_apply_records_opencode_projection_without_mutating_pi_projection(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            selected = [service_descriptor("context7"), service_descriptor("github")]
            pi_plan = binding.plan_project_init_target_client_activation(root, selected, target_client="pi")
            pi_validation_plan = binding.build_project_init_validation_plan(selected, validation_mode="installed", target_client="pi")
            base_state = project_state.apply_project_init_activation_to_state(
                project_state.default_state(root),
                selected,
                target_client="pi",
                client_config_plan=pi_plan,
                validation_plan=pi_validation_plan,
                validation_results={},
                consent_receipt_refs=CONSENT_REFS,
            )
            project_state.write_state_atomic(root, base_state)

            availability = helper.list_available_capabilities(project_root=root, client_type="opencode")
            apply_result = binding.apply_project_init_service_activation(
                root,
                selected,
                validation_mode="installed",
                approval_scope=binding.PROJECT_INIT_APPROVAL_SCOPE,
                target_client="opencode",
                consent_receipt_refs=CONSENT_REFS,
                dry_run=True,
            )

        self.assertEqual("alignment_import_offer", availability["status"])
        self.assertEqual("align-existing-project-services", availability["next_turn"]["question_id"])
        self.assertEqual(["context7:canonical", "github:canonical"], availability["alignment_import_offer"]["project_service_bindings"])
        planned = apply_result["planned_state"]
        self.assertEqual({"context7:canonical", "github:canonical"}, set(planned["services"]))
        self.assertEqual(
            base_state["services"]["context7:canonical"]["x_service_identity"]["id"],
            planned["services"]["context7:canonical"]["x_service_identity"]["id"],
        )
        self.assertEqual(
            base_state["services"]["github:canonical"]["x_service_identity"]["id"],
            planned["services"]["github:canonical"]["x_service_identity"]["id"],
        )
        self.assertEqual(
            base_state["services"]["context7:canonical"]["target_clients"]["pi"],
            planned["services"]["context7:canonical"]["target_clients"]["pi"],
        )
        self.assertEqual(
            base_state["services"]["github:canonical"]["target_clients"]["pi"],
            planned["services"]["github:canonical"]["target_clients"]["pi"],
        )
        self.assertEqual("project_local_opencode_config_planned", planned["services"]["context7:canonical"]["target_clients"]["opencode"]["status"])
        self.assertEqual("installed", planned["services"]["context7:canonical"]["target_clients"]["opencode"]["validation_status"])
        self.assertEqual("project_local_opencode_config_planned", planned["services"]["github:canonical"]["target_clients"]["opencode"]["status"])
        self.assertEqual("installed", planned["services"]["github:canonical"]["target_clients"]["opencode"]["validation_status"])
        self.assertEqual("installed", planned["project_init"]["client_states"]["opencode"]["status"])
        self.assertEqual(["context7:canonical", "github:canonical"], planned["project_init"]["client_states"]["opencode"]["selected_service_bindings"])
        self.assertNotIn("opencode", base_state["services"]["context7:canonical"]["target_clients"])
        self.assertNotIn("opencode", base_state["services"]["github:canonical"]["target_clients"])

    def test_alignment_import_continuation_turn_builds_opencode_approval_package(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp, tempfile.TemporaryDirectory() as run_tmp:
            root = Path(tmp).resolve()
            selected = [service_descriptor("context7")]
            config_plan = binding.plan_project_init_target_client_activation(root, selected, target_client="pi")
            state = project_state.apply_project_init_activation_to_state(
                project_state.default_state(root),
                selected,
                target_client="pi",
                client_config_plan=config_plan,
                validation_plan=binding.build_project_init_validation_plan(selected, validation_mode="installed", target_client="pi"),
                validation_results={},
                consent_receipt_refs=CONSENT_REFS,
            )
            project_state.write_state_atomic(root, state)
            approval_source = Path(run_tmp) / "opencode-latest-user-message.json"
            approval_source.write_text(
                json.dumps({"cwd": str(root), "text": "context7"}) + "\n",
                encoding="utf-8",
            )

            with mock.patch.dict(os.environ, {"CONTEXTFORGE_HELPER_APPROVAL_SOURCE_PATH": str(approval_source)}):
                offer = contextforge_helper_mcp.list_available_capabilities(str(root), client_type="opencode")
                proposal = contextforge_helper_mcp.cf_project_init_continue(str(root), client_type="opencode")

        self.assertTrue(offer["ok"], offer)
        self.assertEqual("alignment_import_offer", offer["status"])
        self.assertEqual(["context7:canonical"], offer["alignment_import_offer"]["project_service_bindings"])
        self.assertEqual("align-existing-project-services", offer["next_turn"]["question_id"])
        self.assertTrue(proposal["ok"], proposal)
        self.assertEqual(["context7:canonical"], proposal["selected_service_bindings"])
        self.assertIn("Plan ready for context7:canonical", proposal["assistant_visible_response"])
        self.assertIn("opencode.json", proposal["assistant_visible_response"])
        self.assertIn("Approve or decline?", proposal["assistant_visible_response"])

    def test_contextforge_helper_mcp_reports_project_capability_summary_read_only(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            selected = [service_descriptor("context7")]
            config_plan = binding.plan_project_init_target_client_activation(root, selected, target_client="opencode")
            state = project_state.apply_project_init_activation_to_state(
                project_state.default_state(root),
                selected,
                target_client="opencode",
                client_config_plan=config_plan,
                validation_plan=binding.build_project_init_validation_plan(selected, validation_mode="installed", target_client="opencode"),
                validation_results={},
                consent_receipt_refs=CONSENT_REFS,
            )
            skipped = json.loads(json.dumps(state["services"]["context7:canonical"]))
            skipped["service_family"] = "web-search"
            skipped["service_binding"] = "web-search:credential_scoped"
            skipped["provision_status"] = "failed"
            skipped["x_reason"] = "credential not configured"
            skipped["x_service_identity_id"] = "contextforge-service-web-search-unavailable"
            skipped["x_service_identity"]["id"] = "contextforge-service-web-search-unavailable"
            state["services"]["web-search:credential_scoped"] = skipped
            project_state.write_state_atomic(root, state)

            full_report = contextforge_helper_mcp.project_capability_summary(str(root), client_type="opencode")
            result = contextforge_helper_mcp.get_project_capability_summary(str(root), client_type="opencode")

        self.assertTrue(full_report["available_now"])
        self.assertTrue(full_report["known_unavailable"])
        self.assertTrue(full_report["onboarding_needed"])
        self.assertTrue(result["ok"])
        self.assertEqual("project_capability_summary", result["status"])
        self.assertIn("assistant_visible_response", result)
        self.assertEqual(result["assistant_visible_response"], result["message"])
        self.assertTrue(result["copy_as_complete_visible_response"])
        self.assertTrue(result["do_not_summarize"])
        self.assertNotIn("available_now", result)
        self.assertNotIn("onboarding_needed", result)
        visible = result["assistant_visible_response"]
        self.assertIn("Configured in current project state for opencode:", visible)
        self.assertIn("Known but unavailable:", visible)
        self.assertIn("Could be onboarded with approval:", visible)
        self.assertIn("Important client/session boundary for opencode:", visible)
        self.assertIn("context7:canonical", visible)
        self.assertIn("web-search:credential_scoped", visible)
        self.assertIn("no service onboarding", result["non_actions"])

    def test_contextforge_helper_mcp_reports_project_state_readback_read_only(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            selected = [service_descriptor("context7")]
            config_plan = binding.plan_project_init_target_client_activation(root, selected, target_client="opencode")
            state = project_state.apply_project_init_activation_to_state(
                project_state.default_state(root),
                selected,
                target_client="opencode",
                client_config_plan=config_plan,
                validation_plan=binding.build_project_init_validation_plan(selected, validation_mode="installed", target_client="opencode"),
                validation_results={},
                consent_receipt_refs=CONSENT_REFS,
            )
            project_state.write_state_atomic(root, state)

            full_report = contextforge_helper_mcp.project_state_readback(str(root), client_type="opencode")
            result = contextforge_helper_mcp.get_project_state_readback(str(root), client_type="opencode")

        self.assertTrue(full_report["ok"])
        self.assertEqual("project_state_readback", full_report["status"])
        self.assertEqual("initialized", full_report["state_status"])
        self.assertEqual(["context7:canonical"], full_report["selected_service_bindings"])
        self.assertEqual(["context7-local-resolve-library-id", "context7-local-query-docs"], full_report["imported_tools"][0]["tool_names"])
        self.assertEqual("not_claimed_by_readback", full_report["target_client_services"][0]["readiness_layers"]["interactive_proof"])
        self.assertIn("interactive proof is not claimed", full_report["assistant_visible_response"])
        self.assertTrue(result["ok"])
        self.assertEqual("project_state_readback", result["status"])
        self.assertIn("assistant_visible_response", result)
        self.assertEqual(result["assistant_visible_response"], result["message"])
        self.assertTrue(result["copy_as_complete_visible_response"])
        self.assertTrue(result["do_not_summarize"])
        self.assertNotIn("target_client_services", result)
        self.assertNotIn("state_revision", result)
        visible = result["assistant_visible_response"]
        self.assertIn(str(root), visible)
        self.assertIn("revision", visible)
        self.assertIn("context7:canonical", visible)
        self.assertIn("Configured/imported-tool policy", visible)
        self.assertIn("client-visible", visible)
        self.assertIn("not proven by this readback", visible)
        self.assertIn("target-client-visible=false states remain unproven", visible)
        self.assertIn("interactive proof is not claimed", visible)
        self.assertIn("no claim of interactive proof", result["non_actions"])

    def test_contextforge_helper_mcp_default_client_type_can_be_set_by_env(self) -> None:
        self.assertEqual(
            "codex",
            inspect.signature(contextforge_helper_mcp.list_available_capabilities).parameters["client_type"].default,
        )
        env = dict(os.environ)
        env["PYTHONPATH"] = str(REPO_ROOT / "scripts")
        env["CONTEXTFORGE_HELPER_DEFAULT_CLIENT_TYPE"] = "opencode"
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import inspect, contextforge_helper_mcp; "
                    "print(inspect.signature(contextforge_helper_mcp.list_available_capabilities)"
                    ".parameters['client_type'].default)"
                ),
            ],
            capture_output=True,
            text=True,
            env=env,
            timeout=20,
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("opencode", result.stdout.strip())

    def test_contextforge_helper_mcp_approval_guard_requires_latest_user_approval_text(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp, tempfile.TemporaryDirectory() as run_tmp:
            root = Path(tmp).resolve()
            approval_source = Path(run_tmp) / "opencode-latest-user-message.json"
            contextforge_helper_mcp._clear_durable_cache(str(root))
            contextforge_helper_mcp._CACHED_PLANS.clear()
            contextforge_helper_mcp._CACHED_RECEIPTS.clear()
            proposal = contextforge_helper_mcp.cf_project_init_propose(
                str(root),
                [service_descriptor("context7")],
                client_type="opencode",
            )
            challenge = proposal["approval_challenge"]
            guarded_env = {
                "CONTEXTFORGE_HELPER_REQUIRE_USER_APPROVAL_TEXT": "1",
                "CONTEXTFORGE_HELPER_APPROVAL_SOURCE_PATH": str(approval_source),
            }

            approval_source.write_text(
                json.dumps({"cwd": str(root), "text": "Activate context7:canonical only."}) + "\n",
                encoding="utf-8",
            )
            with mock.patch.dict(os.environ, guarded_env):
                denied = contextforge_helper_mcp.cf_project_init_approve(
                    str(root),
                    challenge["challenge_id"],
                    challenge["plan_digest"],
                )

            self.assertFalse(denied["ok"])
            self.assertEqual("PermissionError", denied["error"]["type"])

            approval_source.write_text(json.dumps({"cwd": str(root), "text": "1"}) + "\n", encoding="utf-8")
            with mock.patch.dict(os.environ, guarded_env):
                numeric_denied = contextforge_helper_mcp.cf_project_init_approve(
                    str(root),
                    challenge["challenge_id"],
                    challenge["plan_digest"],
                )

            self.assertFalse(numeric_denied["ok"])
            self.assertEqual("PermissionError", numeric_denied["error"]["type"])

    def test_contextforge_helper_mcp_approval_guard_accepts_approval_text(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp, tempfile.TemporaryDirectory() as run_tmp:
            root = Path(tmp).resolve()
            approval_source = Path(run_tmp) / "opencode-latest-user-message.json"
            contextforge_helper_mcp._clear_durable_cache(str(root))
            contextforge_helper_mcp._CACHED_PLANS.clear()
            contextforge_helper_mcp._CACHED_RECEIPTS.clear()
            proposal = contextforge_helper_mcp.cf_project_init_propose(
                str(root),
                [service_descriptor("context7")],
                client_type="opencode",
            )
            challenge = proposal["approval_challenge"]
            guarded_env = {
                "CONTEXTFORGE_HELPER_REQUIRE_USER_APPROVAL_TEXT": "1",
                "CONTEXTFORGE_HELPER_REQUIRE_USER_RELOAD_TEXT": "1",
                "CONTEXTFORGE_HELPER_REQUIRE_USER_VALIDATION_TEXT": "1",
                "CONTEXTFORGE_HELPER_RECORD_RELOAD_ON_VALIDATION_REQUEST": "1",
                "CONTEXTFORGE_HELPER_APPROVAL_SOURCE_PATH": str(approval_source),
            }

            approval_source.write_text(
                json.dumps({"cwd": str(root), "text": "Approve this exact ContextForge activation plan."}) + "\n",
                encoding="utf-8",
            )
            with mock.patch.dict(os.environ, guarded_env):
                approved = contextforge_helper_mcp.cf_project_init_approve(
                    str(root),
                    challenge["challenge_id"],
                    challenge["plan_digest"],
                )

            self.assertTrue(approved["ok"])
            applied = contextforge_helper_mcp.cf_project_init_apply(str(root))
            self.assertTrue(applied["ok"])

            self.assertEqual("opencode-project-init-installed", applied["next_turn"]["question_id"])
            self.assertIn("new session", applied["next_turn"]["prompt"].lower())

    def test_opencode_continue_recovers_recorded_cwd_when_model_supplies_root_slash(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp, tempfile.TemporaryDirectory() as run_tmp:
            root = Path(tmp).resolve()
            approval_source = Path(run_tmp) / "opencode-latest-user-message.json"
            contextforge_helper_mcp._clear_durable_cache(str(root))
            contextforge_helper_mcp._CACHED_PLANS.clear()
            contextforge_helper_mcp._CACHED_RECEIPTS.clear()
            approval_source.write_text(
                json.dumps({"cwd": str(root), "text": "1"}) + "\n",
                encoding="utf-8",
            )

            with mock.patch.dict(os.environ, {"CONTEXTFORGE_HELPER_APPROVAL_SOURCE_PATH": str(approval_source)}):
                proposal = contextforge_helper_mcp.cf_project_init_continue(
                    "/",
                    client_type="opencode",
                )

            self.assertTrue(proposal["ok"], proposal)
            self.assertEqual(str(root), proposal["project_root"])
            self.assertIn("assistant_visible_response", proposal)
            self.assertIn("context7:canonical", proposal["assistant_visible_response"])
            self.assertIn("Approve or decline?", proposal["assistant_visible_response"])

    def test_opencode_continue_accepts_natural_service_selection(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp, tempfile.TemporaryDirectory() as run_tmp:
            root = Path(tmp).resolve()
            approval_source = Path(run_tmp) / "opencode-latest-user-message.json"
            contextforge_helper_mcp._clear_durable_cache(str(root))
            contextforge_helper_mcp._CACHED_PLANS.clear()
            contextforge_helper_mcp._CACHED_RECEIPTS.clear()
            approval_source.write_text(
                json.dumps({"cwd": str(root), "text": "context7"}) + "\n",
                encoding="utf-8",
            )

            with mock.patch.dict(os.environ, {"CONTEXTFORGE_HELPER_APPROVAL_SOURCE_PATH": str(approval_source)}):
                single_proposal = contextforge_helper_mcp.cf_project_init_continue(
                    str(root),
                    client_type="opencode",
                )

            self.assertTrue(single_proposal["ok"], single_proposal)
            self.assertEqual(["context7:canonical"], single_proposal["selected_service_bindings"])

            contextforge_helper_mcp._clear_durable_cache(str(root))
            contextforge_helper_mcp._CACHED_PLANS.clear()
            contextforge_helper_mcp._CACHED_RECEIPTS.clear()
            approval_source.write_text(
                json.dumps({"cwd": str(root), "text": "context7, mentality, and ssh-tmux"}) + "\n",
                encoding="utf-8",
            )

            with mock.patch.dict(os.environ, {"CONTEXTFORGE_HELPER_APPROVAL_SOURCE_PATH": str(approval_source)}):
                proposal = contextforge_helper_mcp.cf_project_init_continue(
                    str(root),
                    client_type="opencode",
                )

            self.assertTrue(proposal["ok"], proposal)
            self.assertEqual(
                ["context7:canonical", "mentality:static_repo_local", "ssh-tmux:session_scoped"],
                proposal["selected_service_bindings"],
            )
            self.assertIn("assistant_visible_response", proposal)
            self.assertIn("Approve or decline?", proposal["assistant_visible_response"])

    def test_pi_continue_accepts_recorded_natural_service_selection(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp, tempfile.TemporaryDirectory() as run_tmp:
            root = Path(tmp).resolve()
            approval_source = Path(run_tmp) / "pi-latest-user-message.json"
            contextforge_helper_mcp._clear_durable_cache(str(root))
            contextforge_helper_mcp._CACHED_PLANS.clear()
            contextforge_helper_mcp._CACHED_RECEIPTS.clear()
            approval_source.write_text(
                json.dumps({"cwd": str(root), "text": "context7"}) + "\n",
                encoding="utf-8",
            )

            with mock.patch.dict(os.environ, {"CONTEXTFORGE_HELPER_APPROVAL_SOURCE_PATH": str(approval_source)}):
                proposal = contextforge_helper_mcp.cf_project_init_continue(
                    str(root),
                    client_type="pi",
                )

            self.assertTrue(proposal["ok"], proposal)
            self.assertEqual(["context7:canonical"], proposal["selected_service_bindings"])
            self.assertIn("assistant_visible_response", proposal)
            self.assertIn("Approve or decline?", proposal["assistant_visible_response"])

    def test_pi_continue_maps_pending_serena_numeric_defer_to_non_serena_plan(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp, tempfile.TemporaryDirectory() as run_tmp:
            root = Path(tmp).resolve()
            approval_source = Path(run_tmp) / "pi-latest-user-message.json"
            contextforge_helper_mcp._clear_durable_cache(str(root))
            contextforge_helper_mcp._CACHED_PLANS.clear()
            contextforge_helper_mcp._CACHED_RECEIPTS.clear()

            with mock.patch.dict(os.environ, {"CONTEXTFORGE_HELPER_APPROVAL_SOURCE_PATH": str(approval_source)}):
                approval_source.write_text(json.dumps({"cwd": str(root), "text": "context7 and serena"}) + "\n", encoding="utf-8")
                language_turn = contextforge_helper_mcp.cf_project_init_continue(str(root), client_type="pi")
                pending_after_language_turn = contextforge_helper_mcp._pending_project_init_input(str(root))
                approval_source.write_text(json.dumps({"cwd": str(root), "text": "3"}) + "\n", encoding="utf-8")
                proposal = contextforge_helper_mcp.cf_project_init_continue(str(root), client_type="pi")
                cached_plan = contextforge_helper_mcp._matching_cached_plan(str(root), None, None)
                pending_input = contextforge_helper_mcp._pending_project_init_input(str(root))

        self.assertTrue(language_turn["ok"], language_turn)
        self.assertEqual("needs_input", language_turn["status"])
        self.assertEqual("language", pending_after_language_turn["input_name"])
        self.assertIn("context7:canonical", pending_after_language_turn["selected_services"])
        self.assertTrue(any(str(item).startswith("serena:") for item in pending_after_language_turn["selected_services"]))
        self.assertTrue(proposal["ok"], proposal)
        self.assertEqual("project_init", proposal["workflow"])
        self.assertEqual(["context7:canonical"], proposal["selected_service_bindings"])
        self.assertNotIn("serena:", " ".join(proposal["selected_service_bindings"]))
        self.assertEqual("approve-project-init-plan", cached_plan["next_turn"]["question_id"])
        self.assertEqual(["context7:canonical"], [service["service_binding"] for service in cached_plan["selected_services"]])
        self.assertIsNone(pending_input)

    def test_opencode_continue_preserves_all_services_selection_through_language_input(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp, tempfile.TemporaryDirectory() as run_tmp:
            root = Path(tmp).resolve()
            approval_source = Path(run_tmp) / "opencode-latest-user-message.json"
            contextforge_helper_mcp._clear_durable_cache(str(root))
            contextforge_helper_mcp._CACHED_PLANS.clear()
            contextforge_helper_mcp._CACHED_RECEIPTS.clear()

            with mock.patch.dict(os.environ, {"CONTEXTFORGE_HELPER_APPROVAL_SOURCE_PATH": str(approval_source)}):
                approval_source.write_text(json.dumps({"cwd": str(root), "text": "all services"}) + "\n", encoding="utf-8")
                language_turn = contextforge_helper_mcp.cf_project_init_continue(str(root), client_type="opencode")
                approval_source.write_text(json.dumps({"cwd": str(root), "text": "python"}) + "\n", encoding="utf-8")
                proposal = contextforge_helper_mcp.cf_project_init_continue(str(root), client_type="opencode")

            self.assertTrue(language_turn["ok"], language_turn)
            self.assertEqual("needs_input", language_turn["status"])
            self.assertIn("Which language", language_turn["assistant_visible_response"])
            self.assertTrue(proposal["ok"], proposal)
            self.assertEqual("project_init", proposal["workflow"])
            self.assertEqual(9, len(proposal["selected_service_bindings"]))
            self.assertIn("serena:", " ".join(proposal["selected_service_bindings"]))
            self.assertIn("language=python", proposal["assistant_visible_response"])
            self.assertIn("Approve or decline?", proposal["assistant_visible_response"])

    def test_contextforge_helper_public_apply_message_lists_installed_bindings(self) -> None:
        public = contextforge_helper_mcp.client_visible_project_init_apply_payload(
            {
                "ok": True,
                "installation_status": "installed",
                "installed_service_bindings": ["context7:canonical", "serena:abc123"],
                "next_turn": {
                    "prompt": "ContextForge tools are installed for this project. Start a new session from this project root for the tools to register."
                },
            }
        )

        self.assertIn("context7:canonical, serena:abc123", public["message"])
        self.assertIn("Start a new session from this project root", public["message"])

    def test_contextforge_helper_can_omit_next_turn_from_codex_plan_payload(self) -> None:
        public = contextforge_helper_mcp.client_visible_project_init_plan_payload(
            {
                "ok": True,
                "workflow": "project_init",
                "selected_services": [service_descriptor("context7")],
                "required_inputs": {"serena:abc123": {"language": "python"}},
                "plan_summary": {
                    "project_local_writes": ["/workspace/.codex/config.toml"],
                    "bindings": [{"service_binding": "context7:canonical"}],
                },
                "next_turn": {"prompt": "Approve the listed project-local ContextForge activation effects?"},
            },
            include_next_turn=False,
        )

        self.assertIn("Plan ready for context7:canonical", public["assistant_visible_response"])
        self.assertIn("serena:abc123 language=python", public["assistant_visible_response"])
        self.assertNotIn("next_turn", public)

    def test_contextforge_helper_install_guidance_stops_after_reload_instruction(self) -> None:
        plan_doc = (
            REPO_ROOT / "docs/initiatives/contextforge-control-plane/contextforge-helper-project-init-plan.md"
        ).read_text(encoding="utf-8")

        self.assertIn("selected ContextForge tools are installed", plan_doc)
        self.assertIn("new session or reload", plan_doc)
        self.assertIn("Stop there", plan_doc)
        self.assertNotIn("ACTUAL_TARGET_CLIENT_TOOL_NAME", plan_doc)
        self.assertNotIn("validation_results", plan_doc)

    def test_contextforge_helper_mcp_binds_approval_event_without_agent_supplied_ref(self) -> None:
        approval_params = set(inspect.signature(contextforge_helper_mcp.approve_project_init_plan).parameters)

        self.assertNotIn("local_approval_event_ref", approval_params)
        self.assertNotIn("actor", approval_params)
        self.assertNotIn("source_client", approval_params)
        self.assertNotIn("source_client_auth_strength", approval_params)

        with tempfile.TemporaryDirectory(dir=REPO_ROOT) as tmp:
            root = Path(tmp).resolve()
            proposal = contextforge_helper_mcp.propose_project_init(
                str(root),
                [service_descriptor("context7")],
            )

            approval = contextforge_helper_mcp.approve_project_init_plan(
                str(root),
                proposal,
                {
                    "decision": "approve",
                    "challenge_id": proposal["approval_challenge"]["challenge_id"],
                    "plan_digest": proposal["plan_digest"],
                },
            )

        self.assertTrue(approval["ok"])
        self.assertEqual("allow", approval["decision"])
        self.assertEqual({"project_local_config_write", "project_state_write"}, {r["consent_class"] for r in approval["receipts"]})

    def test_contextforge_helper_mcp_binds_recovery_approval_event_without_agent_supplied_ref(self) -> None:
        approval_params = set(inspect.signature(contextforge_helper_mcp.approve_project_init_recovery_plan).parameters)

        self.assertNotIn("local_approval_event_ref", approval_params)
        self.assertNotIn("actor", approval_params)
        self.assertNotIn("source_client", approval_params)
        self.assertNotIn("source_client_auth_strength", approval_params)

    def test_contextforge_helper_mcp_exposes_recovery_project_init_id_digest_tools(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT) as tmp:
            project_root = str(Path(tmp).resolve())
            with mock.patch.object(
                helper,
                "propose_project_init_recovery",
                return_value={"plan_id": "project-init-recovery-plan", "plan_digest": "sha256:abcd", "approval_challenge": {"challenge_id": "challenge", "plan_digest": "sha256:abcd"}},
                create=True,
            ) as fake_propose, mock.patch.object(
                helper,
                "restore_process_local_approval_session",
                return_value={"status": "approval_session_restored"},
                create=True,
            ) as fake_restore, mock.patch.object(
                helper,
                "record_local_approval_event",
                return_value={"event_ref": "local-approval-token"},
                create=True,
            ) as fake_event, mock.patch.object(
                helper,
                "approve_project_init_recovery_plan",
                return_value={
                    "decision": "allow",
                    "plan_id": "project-init-recovery-plan",
                    "plan_digest": "sha256:abcd",
                    "receipts": [{"receipt_id": "r1", "consent_class": "project_state_write", "source_client": "codex"}],
                },
                create=True,
            ) as fake_approve, mock.patch.object(
                helper,
                "apply_project_init_recovery",
                return_value={"ok": True, "next_turn": {"question_id": "codex-project-init-installed"}, "client_reload_requirement": {"command": "start_new_session"}},
                create=True,
            ) as fake_apply:

                contextforge_helper_mcp._clear_durable_cache(project_root)
                contextforge_helper_mcp._CACHED_PLANS.clear()
                contextforge_helper_mcp._CACHED_RECEIPTS.clear()

                proposal = contextforge_helper_mcp.cf_project_init_recovery_propose(project_root)
                self.assertTrue(proposal["ok"])

                contextforge_helper_mcp._CACHED_PLANS.clear()
                contextforge_helper_mcp._CACHED_RECEIPTS.clear()
                approval = contextforge_helper_mcp.cf_project_init_recovery_approve(project_root, "challenge", "sha256:abcd")
                contextforge_helper_mcp._CACHED_PLANS.clear()
                contextforge_helper_mcp._CACHED_RECEIPTS.clear()
                applied = contextforge_helper_mcp.cf_project_init_recovery_apply(project_root, dry_run=True)

        self.assertEqual("allow", approval["decision"])
        self.assertTrue(applied["ok"])
        fake_propose.assert_called_once()
        fake_restore.assert_called()
        fake_event.assert_called()
        fake_approve.assert_called_once()
        fake_apply.assert_called_once()
        fake_approve_call = fake_approve.mock_calls[0].kwargs
        fake_apply_call = fake_apply.mock_calls[0].kwargs
        self.assertEqual(project_root, fake_approve_call["project_root"])
        self.assertEqual(project_root, fake_apply_call["project_root"])

    def test_contextforge_helper_mcp_restores_exact_plan_for_short_lived_helper_processes(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT) as tmp:
            root = Path(tmp).resolve()
            proposal = contextforge_helper_mcp.propose_project_init(
                str(root),
                [service_descriptor("context7")],
            )

            contextforge_helper_mcp._CACHED_PLANS.clear()
            contextforge_helper_mcp._CACHED_RECEIPTS.clear()
            helper._PENDING_CHALLENGES.clear()
            helper._LOCAL_APPROVAL_EVENTS.clear()

            approval = contextforge_helper_mcp.approve_project_init_plan(
                str(root),
                proposal,
                {
                    "decision": "approve",
                    "challenge_id": proposal["approval_challenge"]["challenge_id"],
                    "plan_digest": proposal["plan_digest"],
                },
            )

            helper._APPROVED_RECEIPT_IDS_BY_PLAN.clear()
            applied = contextforge_helper_mcp.apply_approved_project_init(
                str(root),
                proposal,
                approval["receipts"],
                dry_run=True,
            )

        self.assertTrue(approval["ok"])
        self.assertEqual("allow", approval["decision"])
        self.assertTrue(applied["ok"])
        self.assertEqual("codex-project-init-installed", applied["next_turn"]["question_id"])
        self.assertEqual("start_new_session", applied["client_reload_requirement"]["command"])

    def test_contextforge_helper_mcp_cached_id_tools_survive_short_lived_processes(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT) as tmp:
            root = Path(tmp).resolve()
            contextforge_helper_mcp._clear_durable_cache(str(root))
            proposal = contextforge_helper_mcp.cf_project_init_propose(
                str(root),
                [service_descriptor("context7")],
            )
            challenge = proposal["approval_challenge"]

            contextforge_helper_mcp._CACHED_PLANS.clear()
            contextforge_helper_mcp._CACHED_RECEIPTS.clear()
            helper._PENDING_CHALLENGES.clear()
            helper._LOCAL_APPROVAL_EVENTS.clear()

            approval = contextforge_helper_mcp.cf_project_init_approve(
                str(root),
                challenge["challenge_id"],
                proposal["plan_digest"],
            )

            contextforge_helper_mcp._CACHED_PLANS.clear()
            contextforge_helper_mcp._CACHED_RECEIPTS.clear()
            helper._APPROVED_RECEIPT_IDS_BY_PLAN.clear()
            applied = contextforge_helper_mcp.cf_project_init_apply(str(root), dry_run=True)
            contextforge_helper_mcp._clear_durable_cache(str(root))

        self.assertTrue(proposal["ok"])
        self.assertTrue(approval["ok"])
        self.assertEqual("allow", approval["decision"])
        self.assertTrue(applied["ok"])
        self.assertEqual("codex-project-init-installed", applied["next_turn"]["question_id"])
        self.assertEqual("start_new_session", applied["client_reload_requirement"]["command"])

    def test_pi_project_init_cli_id_digest_tools_survive_separate_processes(self) -> None:
        def run_cli(operation: str, payload: dict[str, Any]) -> dict[str, Any]:
            env = dict(os.environ)
            env["PYTHONPATH"] = str(REPO_ROOT / "scripts")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "pi_project_init_helper_cli.py"),
                    "--operation",
                    operation,
                    "--payload-json",
                    json.dumps(payload),
                ],
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                timeout=30,
            )
            try:
                parsed = json.loads(completed.stdout)
            except json.JSONDecodeError as exc:
                self.fail(f"{operation} returned non-JSON stdout={completed.stdout!r} stderr={completed.stderr!r}: {exc}")
            self.assertEqual(0, completed.returncode, f"{operation} stderr={completed.stderr} stdout={completed.stdout}")
            return parsed

        with tempfile.TemporaryDirectory(dir=REPO_ROOT) as tmp:
            root = Path(tmp).resolve()
            contextforge_helper_mcp._clear_durable_cache(str(root))
            contextforge_helper_mcp._CACHED_PLANS.clear()
            contextforge_helper_mcp._CACHED_RECEIPTS.clear()
            helper._PENDING_CHALLENGES.clear()
            helper._LOCAL_APPROVAL_EVENTS.clear()

            proposal = run_cli(
                "propose_project_init",
                {"project_root": str(root), "client_type": "pi", "selected_services": [service_descriptor("context7")]},
            )
            challenge = proposal["approval_challenge"]
            contextforge_helper_mcp._CACHED_PLANS.clear()
            contextforge_helper_mcp._CACHED_RECEIPTS.clear()
            helper._PENDING_CHALLENGES.clear()
            helper._LOCAL_APPROVAL_EVENTS.clear()

            approval = run_cli(
                "cf_project_init_approve",
                {
                    "project_root": str(root),
                    "client_type": "pi",
                    "challenge_id": challenge["challenge_id"],
                    "plan_digest": proposal["plan_digest"],
                },
            )
            contextforge_helper_mcp._CACHED_PLANS.clear()
            contextforge_helper_mcp._CACHED_RECEIPTS.clear()
            helper._APPROVED_RECEIPT_IDS_BY_PLAN.clear()

            applied = run_cli(
                "cf_project_init_apply",
                {"project_root": str(root), "client_type": "pi", "dry_run": True},
            )
            contextforge_helper_mcp._clear_durable_cache(str(root))

        self.assertTrue(proposal["ok"])
        self.assertTrue(approval["ok"])
        self.assertEqual("allow", approval["decision"])
        self.assertTrue(applied["ok"], applied.get("error"))
        self.assertEqual("pi-project-init-installed", applied["next_turn"]["question_id"])
        self.assertEqual("/reload", applied["client_reload_requirement"]["command"])

    def test_contextforge_helper_mcp_apply_requires_cached_approval_receipts(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT) as tmp:
            root = Path(tmp).resolve()
            contextforge_helper_mcp._clear_durable_cache(str(root))
            contextforge_helper_mcp._CACHED_PLANS.clear()
            contextforge_helper_mcp._CACHED_RECEIPTS.clear()
            proposal = contextforge_helper_mcp.cf_project_init_propose(
                str(root),
                [service_descriptor("context7")],
                client_type="pi",
            )
            applied = contextforge_helper_mcp.cf_project_init_apply(str(root), dry_run=True)
            contextforge_helper_mcp._clear_durable_cache(str(root))

        self.assertTrue(proposal["ok"])
        self.assertFalse(applied["ok"])
        self.assertEqual("ValueError", applied["error"]["type"])
        self.assertIn("approve the plan before calling cf_project_init_apply", applied["error"]["message"])

    def test_contextforge_helper_mcp_apply_prefers_cached_full_receipts_over_lossy_replay(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT) as tmp:
            root = Path(tmp).resolve()
            contextforge_helper_mcp._clear_durable_cache(str(root))
            contextforge_helper_mcp._CACHED_PLANS.clear()
            contextforge_helper_mcp._CACHED_RECEIPTS.clear()
            proposal = contextforge_helper_mcp.cf_project_init_propose(
                str(root),
                [service_descriptor("context7")],
                client_type="opencode",
            )
            challenge = proposal["approval_challenge"]
            approval = contextforge_helper_mcp.cf_project_init_approve(
                str(root),
                challenge["challenge_id"],
                proposal["plan_digest"],
            )
            lossy_receipts = json.loads(json.dumps(approval["receipts"]))
            for receipt in lossy_receipts:
                receipt.pop("plan_presented_digest", None)

            contextforge_helper_mcp._CACHED_PLANS.clear()
            contextforge_helper_mcp._CACHED_RECEIPTS.clear()
            helper._APPROVED_RECEIPT_IDS_BY_PLAN.clear()
            applied = contextforge_helper_mcp.cf_project_init_apply(str(root), receipts=lossy_receipts, dry_run=True)
            contextforge_helper_mcp._clear_durable_cache(str(root))

        self.assertTrue(proposal["ok"])
        self.assertTrue(approval["ok"])
        self.assertEqual("allow", approval["decision"])
        self.assertTrue(applied["ok"], applied.get("error"))
        self.assertEqual("opencode-project-init-installed", applied["next_turn"]["question_id"])

    def test_contextforge_helper_mcp_accepts_service_ids_and_expands_descriptors(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT) as tmp:
            root = Path(tmp).resolve()
            instances = root / "instances"
            for service, server, scope_type, extra in (
                ("context7", "context7_local_server", "shared_canonical", {}),
                ("mentality", "mentality_server", "caller_supplied_local_repo", {}),
                ("playwright", "playwright_server", "isolated_browser_runtime", {}),
                ("github", "github_server", "github_account_and_request_repo", {"service_binding": "github:canonical"}),
            ):
                instance = instances / service
                instance.mkdir(parents=True)
                (instance / "instance.json").write_text(
                    json.dumps(
                        {
                            "enabled": True,
                            "name": service,
                            "slug": service,
                            "service": service,
                            **extra,
                            "contextforge": {"virtual_server": {"name": server}, "gateway": {"name": "contextforge"}},
                            "backend": {"transport": "stdio"},
                            "scope": {"scope_type": scope_type},
                        }
                    ),
                    encoding="utf-8",
                )

            proposal = contextforge_helper_mcp.propose_project_init(
                str(root),
                ["context7:canonical", {"id": "mentality:static_repo_local"}, "playwright", "github"],
                contextforge_servers=[
                    {"name": "context7_local_server", "id": "vs-context7"},
                    {"name": "mentality_server", "id": "vs-mentality"},
                    {"name": "playwright_server", "id": "vs-playwright"},
                    {"name": "github_server", "id": "vs-github"},
                ],
                server_instances_root=str(instances),
                inputs={},
            )

        self.assertTrue(proposal["ok"])
        self.assertEqual(
            {"context7:canonical", "mentality:static_repo_local", "playwright:session_scoped", "github:canonical"},
            {service["service_binding"] for service in proposal["selected_services"]},
        )
        github = next(service for service in proposal["selected_services"] if service["service_family"] == "github")
        self.assertEqual("github:canonical", github["service_binding"])
        self.assertEqual("credential_scoped", github["instantiation_class"])
        self.assertEqual("credential-scoped hosted binding", github["scope_label"])
        self.assertNotIn("service_provision", proposal["required_consent_classes"])
        self.assertEqual({"shared_canonical"}, {service["activation_class"] for service in proposal["selected_services"]})

    def test_helper_rechecks_manifest_descriptor_freshness_at_apply(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT) as tmp:
            root = Path(tmp).resolve()
            instances = root / "instances"
            instance = instances / "context7"
            instance.mkdir(parents=True)
            manifest = {
                "enabled": True,
                "name": "context7",
                "slug": "context7",
                "service": "context7",
                "contextforge": {"virtual_server": {"name": "context7_server"}, "gateway": {"name": "contextforge"}},
                "backend": {"transport": "stdio"},
                "scope": {"scope_type": "shared_canonical"},
            }
            (instance / "instance.json").write_text(json.dumps(manifest), encoding="utf-8")
            service = common.discover_contextforge_hosted_services(
                project_root=root,
                server_instances_root=instances,
            )[0]
            plan = helper.propose_project_init(project_root=root, selected_services=[service])
            approval = helper.approve_project_init_plan(
                project_root=root,
                plan=plan,
                approval={
                    "decision": "approve",
                    "challenge_id": plan["approval_challenge"]["challenge_id"],
                    "plan_digest": plan["plan_digest"],
                },
                local_approval_event_ref=helper.record_local_approval_event(
                    project_root=root,
                    plan=plan,
                    issuer_token=helper._LOCAL_APPROVAL_ISSUER_TOKEN,
                )["event_ref"],
            )
            manifest["backend"]["transport"] = "streamable-http"
            (instance / "instance.json").write_text(json.dumps(manifest), encoding="utf-8")

            with self.assertRaisesRegex(helper.ProjectInitHelperError, "stale plan"):
                helper.apply_approved_project_init(
                    project_root=root,
                    plan=plan,
                    receipts=approval["receipts"],
                    server_instances_root=instances,
                    dry_run=True,
                )

    def test_helper_collects_serena_language_before_approval(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            proposal = helper.propose_project_init(
                project_root=Path(tmp).resolve(),
                selected_services=[serena_descriptor()],
            )

        self.assertEqual("needs_input", proposal["status"])
        self.assertEqual("language", proposal["required_input"])
        self.assertTrue(proposal["next_turn"]["must_stop"])
        self.assertNotIn("approval_challenge", proposal)

    def test_helper_accepts_service_scoped_serena_language_input(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            identity = common.project_identity(root)
            proposal = helper.propose_project_init(
                project_root=root,
                selected_services=["serena"],
                inputs={f"serena:{identity.hash}": {"language": "typescript"}},
            )

        self.assertNotEqual("needs_input", proposal.get("status"))
        self.assertEqual("project_init", proposal["workflow"])
        self.assertIn("service_provision", proposal["required_consent_classes"])
        self.assertEqual({"language": "typescript"}, proposal["required_inputs"][f"serena:{identity.hash}"])

    def test_helper_accepts_pi_scalar_serena_language_input_shapes(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            identity = common.project_identity(root)
            selected = ["context7:canonical", f"serena:{identity.hash}"]
            direct = helper.propose_project_init(
                project_root=root,
                selected_services=selected,
                inputs={f"serena:{identity.hash}": "python"},
            )
            suffixed = helper.propose_project_init(
                project_root=root,
                selected_services=selected,
                inputs={f"serena:{identity.hash}-language": "python"},
            )

        self.assertNotEqual("needs_input", direct.get("status"))
        self.assertNotEqual("needs_input", suffixed.get("status"))
        self.assertEqual({"language": "python"}, direct["required_inputs"][f"serena:{identity.hash}"])
        self.assertEqual({"language": "python"}, suffixed["required_inputs"][f"serena:{identity.hash}"])

    def test_helper_applies_serena_provisioning_and_wrapper_as_one_initialization(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            identity = common.project_identity(root)
            plan = helper.propose_project_init(
                project_root=root,
                selected_services=["context7:canonical", "serena"],
                inputs={"language": "python"},
            )
            self.assertIn("service_provision", plan["required_consent_classes"])
            approval = helper.approve_project_init_plan(
                project_root=root,
                plan=plan,
                approval={
                    "decision": "approve",
                    "challenge_id": plan["approval_challenge"]["challenge_id"],
                    "plan_digest": plan["plan_digest"],
                },
                local_approval_event_ref=helper.record_local_approval_event(
                    project_root=root,
                    plan=plan,
                    issuer_token=helper._LOCAL_APPROVAL_ISSUER_TOKEN,
                    channel="interactive_user",
                )["event_ref"],
            )
            provision_result = {
                "service_binding": f"serena:{identity.hash}",
                "status": "completed",
                "operation_type": "provision_project_scoped_serena",
                "pre_digest": None,
                "post_digest": common.stable_digest({"instance_slug": identity.instance_slug}),
            }

            def fake_provision(provision_root: Path, service: dict[str, Any], *, language: str, client_type: str) -> dict[str, Any]:
                serena_config = binding.plan_project_init_codex_config_write(
                    provision_root,
                    [service],
                    existing_text="",
                )
                (provision_root / ".codex").mkdir()
                (provision_root / ".codex" / "config.toml").write_text(serena_config["next_text"], encoding="utf-8")
                return provision_result

            with mock.patch.object(helper, "_run_serena_project_provisioning", side_effect=fake_provision) as provision:
                applied = helper.apply_approved_project_init(
                    project_root=root,
                    plan=plan,
                    receipts=approval["receipts"],
                )

            provision.assert_called_once()
            self.assertEqual("python", provision.call_args.kwargs["language"])
            self.assertEqual("codex", provision.call_args.kwargs["client_type"])
            config_text = (root / ".codex" / "config.toml").read_text(encoding="utf-8")
            self.assertIn("[mcp_servers.serena]", config_text)
            self.assertIn("[mcp_servers.context7]", config_text)
            self.assertIn(identity.server_name, config_text)
            self.assertIn("contextforge_mcp_wrapper.py", config_text)
            step_types = [step["operation_type"] for step in applied["job"]["step_statuses"]]
            self.assertLess(step_types.index("provision_project_scoped_serena"), step_types.index("write_managed_client_config"))
            self.assertEqual("codex-project-init-installed", applied["next_turn"]["question_id"])

    def test_helper_passes_no_systemd_mode_to_serena_manager_when_env_enabled(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            identity = common.project_identity(root)
            manifest = {
                "instance_slug": identity.instance_slug,
                "server_name": identity.server_name,
                "canonical_project_root": str(root),
                "port": 9110,
                "_manifest_path": str(REPO_ROOT / "server-instances" / identity.instance_slug / "instance.json"),
            }
            create_args: list[Any] = []

            def fake_create(args: Any) -> int:
                create_args.append(args)
                return 0

            with mock.patch.object(serena_manager, "existing_manifest_for_project", side_effect=[None, manifest]), mock.patch.object(
                serena_manager,
                "create",
                side_effect=fake_create,
            ), mock.patch.dict(os.environ, {"CONTEXTFORGE_SERENA_NO_SYSTEMD": "1"}):
                result = helper._run_serena_project_provisioning(
                    root,
                    {"service_binding": f"serena:{identity.hash}", "virtual_server": identity.server_name},
                    language="python",
                    client_type="opencode",
                )

        self.assertTrue(create_args)
        self.assertTrue(create_args[0].no_systemd)
        self.assertEqual("completed", result["status"])
        self.assertEqual(identity.instance_slug, result["instance_slug"])

    def test_helper_passes_no_systemd_mode_to_serena_manager_when_systemctl_missing(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            identity = common.project_identity(root)
            manifest = {
                "instance_slug": identity.instance_slug,
                "server_name": identity.server_name,
                "canonical_project_root": str(root),
                "port": 9110,
                "_manifest_path": str(REPO_ROOT / "server-instances" / identity.instance_slug / "instance.json"),
            }
            create_args: list[Any] = []

            def fake_create(args: Any) -> int:
                create_args.append(args)
                return 0

            with mock.patch.object(serena_manager, "existing_manifest_for_project", side_effect=[None, manifest]), mock.patch.object(
                serena_manager,
                "create",
                side_effect=fake_create,
            ), mock.patch.object(helper.shutil, "which", return_value=None), mock.patch.dict(
                os.environ,
                {"CONTEXTFORGE_SERENA_NO_SYSTEMD": ""},
                clear=False,
            ):
                result = helper._run_serena_project_provisioning(
                    root,
                    {"service_binding": f"serena:{identity.hash}", "virtual_server": identity.server_name},
                    language="python",
                    client_type="codex",
                )

        self.assertTrue(create_args)
        self.assertTrue(create_args[0].no_systemd)
        self.assertEqual("completed", result["status"])
        self.assertEqual(identity.instance_slug, result["instance_slug"])

    def test_helper_serena_repeated_init_converges_without_duplicate_wrapper_or_service_entries(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            identity = common.project_identity(root)

            first_plan = helper.propose_project_init(
                project_root=root,
                selected_services=["serena"],
                inputs={"language": "python"},
            )
            first_binding = str(first_plan["selected_services"][0]["service_binding"])
            first_approval = helper.approve_project_init_plan(
                project_root=root,
                plan=first_plan,
                approval={
                    "decision": "approve",
                    "challenge_id": first_plan["approval_challenge"]["challenge_id"],
                    "plan_digest": first_plan["plan_digest"],
                },
                local_approval_event_ref=helper.record_local_approval_event(
                    project_root=root,
                    plan=first_plan,
                    issuer_token=helper._LOCAL_APPROVAL_ISSUER_TOKEN,
                    channel="interactive_user",
                )["event_ref"],
            )

            def fake_provision(provision_root: Path, service: dict[str, Any], *, language: str, client_type: str) -> dict[str, Any]:
                return {
                    "service_binding": f"serena:{identity.hash}",
                    "status": "completed",
                    "operation_type": "provision_project_scoped_serena",
                    "language": language,
                    "instance_slug": identity.instance_slug,
                    "server_name": identity.server_name,
                    "pre_digest": None,
                    "post_digest": common.stable_digest({"instance_slug": identity.instance_slug, "language": language}),
                }

            with mock.patch.object(helper, "_run_serena_project_provisioning", side_effect=fake_provision):
                first_apply = helper.apply_approved_project_init(
                    project_root=root,
                    plan=first_plan,
                    receipts=first_approval["receipts"],
                )

            self.assertEqual("codex-project-init-installed", first_apply["next_turn"]["question_id"])
            first_written = project_state.load_state(root)
            assert first_written is not None
            self.assertEqual("initialized", first_written["status"])

            second_plan = helper.propose_project_init(
                project_root=root,
                selected_services=["serena"],
                inputs={"language": "python"},
            )
            config_text = (root / ".codex" / "config.toml").read_text(encoding="utf-8")
            state = project_state.load_state(root)

        self.assertIn(second_plan["status"], {"client_reload_required", "installed_reload_required"})
        self.assertEqual([first_binding], second_plan["current_job"]["selected_service_bindings"])
        self.assertEqual("codex-project-init-installed", second_plan["next_turn"]["question_id"])
        self.assertEqual(1, config_text.count("[mcp_servers.serena]"))
        self.assertEqual(1, len(state["services"]))
        self.assertEqual("serena", state["services"][next(iter(state["services"]))]["service_family"])

    def test_helper_repairs_missing_serena_wrapper_without_manual_cleanup(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            identity = common.project_identity(root)
            plan = helper.propose_project_init(
                project_root=root,
                selected_services=["serena"],
                inputs={"language": "python"},
            )
            approval = helper.approve_project_init_plan(
                project_root=root,
                plan=plan,
                approval={
                    "decision": "approve",
                    "challenge_id": plan["approval_challenge"]["challenge_id"],
                    "plan_digest": plan["plan_digest"],
                },
                local_approval_event_ref=helper.record_local_approval_event(
                    project_root=root,
                    plan=plan,
                    issuer_token=helper._LOCAL_APPROVAL_ISSUER_TOKEN,
                    channel="interactive_user",
                )["event_ref"],
            )

            def fake_provision(provision_root: Path, service: dict[str, Any], *, language: str, client_type: str) -> dict[str, Any]:
                return {
                    "service_binding": f"serena:{identity.hash}",
                    "status": "completed",
                    "operation_type": "provision_project_scoped_serena",
                    "language": language,
                    "instance_slug": identity.instance_slug,
                    "server_name": identity.server_name,
                    "pre_digest": None,
                    "post_digest": common.stable_digest({"instance_slug": identity.instance_slug, "language": language}),
                }

            with mock.patch.object(helper, "_run_serena_project_provisioning", side_effect=fake_provision):
                helper.apply_approved_project_init(
                    project_root=root,
                    plan=plan,
                    receipts=approval["receipts"],
                )

            config_path = root / ".codex" / "config.toml"
            config_path.unlink()
            capabilities = helper.list_available_capabilities(project_root=root)
            repair = helper.repair_pending_project_init_config(project_root=root)
            restored_text = config_path.read_text(encoding="utf-8")

        self.assertEqual("config_repair_required", capabilities["status"])
        self.assertEqual("repair-project-local-config", capabilities["next_turn"]["question_id"])
        self.assertEqual("config_repaired", repair["status"])
        self.assertIn("[mcp_servers.serena]", restored_text)
        self.assertIn("contextforge_mcp_wrapper.py", restored_text)

    def test_helper_plan_approval_and_apply_dry_run_are_scoped_and_resumable(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            plan = helper.propose_project_init(project_root=root, selected_services=[service_descriptor("context7")])
            self.assertEqual(["project_local_config_write", "project_state_write"], plan["required_consent_classes"])
            self.assertTrue(plan["next_turn"]["must_stop"])
            self.assertIn("stale_plan_inputs", plan)

            fabricated = helper.approve_project_init_plan(
                project_root=root,
                plan=plan,
                approval={"decision": "approve", "challenge_id": "fake", "plan_digest": plan["plan_digest"]},
            )
            self.assertEqual("block", fabricated["decision"])

            approval = helper.approve_project_init_plan(
                project_root=root,
                plan=plan,
                approval={
                    "decision": "approve",
                    "challenge_id": plan["approval_challenge"]["challenge_id"],
                    "plan_digest": plan["plan_digest"],
                    "approval_event_ref": "local-ui:test",
                },
                local_approval_event_ref=helper.record_local_approval_event(
                    project_root=root,
                    plan=plan,
                    issuer_token=helper._LOCAL_APPROVAL_ISSUER_TOKEN,
                )["event_ref"],
            )
            self.assertEqual("allow", approval["decision"])
            self.assertEqual({"project_local_config_write", "project_state_write"}, {r["consent_class"] for r in approval["receipts"]})

            result = helper.apply_approved_project_init(
                project_root=root,
                plan=plan,
                receipts=approval["receipts"],
                dry_run=True,
            )
            self.assertTrue(result["dry_run"])
            self.assertEqual("codex-project-init-installed", result["next_turn"]["question_id"])
            self.assertEqual("start_new_session", result["client_reload_requirement"]["command"])
            self.assertIn("tools are installed", result["next_turn"]["prompt"])
            self.assertFalse((root / ".codex/config.toml").exists())
            job = result["planned_state"]["project_init"]["activation_jobs"][result["planned_state"]["project_init"]["current_job_id"]]
            self.assertEqual("installed", job["status"])
            self.assertTrue(job["consent_receipt_refs"])
            project_state.validate_state(result["planned_state"])

    def test_helper_rejects_plan_tampering_fabricated_receipts_and_stale_config(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            plan = helper.propose_project_init(project_root=root, selected_services=[service_descriptor("context7")])

            tampered = json.loads(json.dumps(plan))
            tampered["selected_services"][0]["virtual_server"] = "attacker_server"
            tampered_approval = helper.approve_project_init_plan(
                project_root=root,
                plan=tampered,
                approval={
                    "decision": "approve",
                    "challenge_id": plan["approval_challenge"]["challenge_id"],
                    "plan_digest": plan["plan_digest"],
                },
            )
            self.assertEqual("block", tampered_approval["decision"])
            self.assertIn("plan digest", " ".join(tampered_approval["reasons"]))

            forged_receipts = [
                authorization.create_consent_receipt(
                    plan=helper._authorization_plan(plan),
                    consent_class=klass,
                    actor="developer",
                    source_client="codex",
                    source_client_auth_strength="shared_token",
                    approval_event_ref="forged",
                    approval_evidence="forged receipt shape",
                    expires_at=plan["approval_challenge"]["expires_at"],
                    approval_nonce=plan["approval_challenge"]["nonce"],
                    scope={"project_root": str(root), "client": "codex"},
                )
                for klass in plan["required_consent_classes"]
            ]
            with self.assertRaisesRegex(helper.ProjectInitHelperError, "not issued by this helper"):
                helper.apply_approved_project_init(project_root=root, plan=plan, receipts=forged_receipts, dry_run=True)

            approval = helper.approve_project_init_plan(
                project_root=root,
                plan=plan,
                approval={
                    "decision": "approve",
                    "challenge_id": plan["approval_challenge"]["challenge_id"],
                    "plan_digest": plan["plan_digest"],
                    "approval_event_ref": "local-ui:test",
                },
                local_approval_event_ref=helper.record_local_approval_event(
                    project_root=root,
                    plan=plan,
                    issuer_token=helper._LOCAL_APPROVAL_ISSUER_TOKEN,
                )["event_ref"],
            )
            (root / ".codex").mkdir()
            (root / ".codex/config.toml").write_text("# user changed config after approval\n", encoding="utf-8")
            with self.assertRaisesRegex(helper.ProjectInitHelperError, "stale plan"):
                helper.apply_approved_project_init(project_root=root, plan=plan, receipts=approval["receipts"], dry_run=True)

    def test_helper_requires_local_approval_event_and_ignores_tampered_challenge_fields(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            plan = helper.propose_project_init(project_root=root, selected_services=[service_descriptor("context7")])

            missing_local = helper.approve_project_init_plan(
                project_root=root,
                plan=plan,
                approval={
                    "decision": "approve",
                    "challenge_id": plan["approval_challenge"]["challenge_id"],
                    "plan_digest": plan["plan_digest"],
                },
            )
            self.assertEqual("block", missing_local["decision"])
            self.assertIn("missing local approval event", " ".join(missing_local["reasons"]))

            tampered = json.loads(json.dumps(plan))
            tampered["approval_challenge"]["expires_at"] = "2999-01-01T00:00:00Z"
            approval = helper.approve_project_init_plan(
                project_root=root,
                plan=tampered,
                approval={
                    "decision": "approve",
                    "challenge_id": plan["approval_challenge"]["challenge_id"],
                    "plan_digest": plan["plan_digest"],
                },
                local_approval_event_ref=helper.record_local_approval_event(
                    project_root=root,
                    plan=plan,
                    issuer_token=helper._LOCAL_APPROVAL_ISSUER_TOKEN,
                )["event_ref"],
            )
            self.assertEqual("allow", approval["decision"])
            self.assertNotEqual("2999-01-01T00:00:00Z", approval["receipts"][0]["expires_at"])

    def test_local_approval_event_requires_unexposed_issuer_capability(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            plan = helper.propose_project_init(project_root=root, selected_services=[service_descriptor("context7")])

            with self.assertRaisesRegex(helper.ProjectInitHelperError, "issuer is not authorized"):
                helper.record_local_approval_event(project_root=root, plan=plan, issuer_token="caller-supplied")

    def test_direct_binding_apply_is_dry_run_only_without_helper_authorization(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            with self.assertRaisesRegex(binding.ProjectInitApplyError, "contextforge-helper"):
                binding.apply_project_init_service_activation(
                    root,
                    [service_descriptor("context7")],
                    validation_mode="pending_choice",
                    approval_scope=binding.PROJECT_INIT_APPROVAL_SCOPE,
                    consent_receipt_refs=CONSENT_REFS,
                    dry_run=False,
                )

    def test_helper_returns_config_conflict_turn_before_approval(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            (root / ".codex").mkdir()
            (root / ".codex/config.toml").write_text("[mcp_servers.context7]\ncommand = \"npx\"\n", encoding="utf-8")

            proposal = helper.propose_project_init(project_root=root, selected_services=[service_descriptor("context7")])

            self.assertEqual("config_conflict", proposal["status"])
            self.assertEqual("resolve-config-conflict", proposal["next_turn"]["question_id"])
            self.assertTrue(proposal["next_turn"]["must_stop"])
            self.assertNotIn("approval_challenge", proposal)

    def test_helper_skip_conflicting_service_filters_selection_inside_helper(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            (root / ".codex").mkdir()
            (root / ".codex/config.toml").write_text("[mcp_servers.mentality]\ncommand = \"python\"\n", encoding="utf-8")

            proposal = helper.propose_project_init(
                project_root=root,
                selected_services=[service_descriptor("context7"), service_descriptor("mentality"), service_descriptor("playwright")],
                inputs={"resolve-config-conflict": "skip_conflicting_service"},
            )

        self.assertIn("plan_id", proposal)
        self.assertEqual(
            ["context7:canonical", "playwright:canonical"],
            [service["service_binding"] for service in proposal["selected_services"]],
        )
        self.assertEqual(["mentality:canonical"], [service["service_binding"] for service in proposal["skipped_services"]])
        self.assertEqual("approve-project-init-plan", proposal["next_turn"]["question_id"])
        self.assertIn("selection numbers are not accepted", proposal["next_turn"]["allowed_response_shape"])
        self.assertTrue(all("number" not in choice for choice in proposal["next_turn"]["choices"]))
        self.assertTrue(all("number" not in option for option in proposal["next_turn"]["response_form"]["options"]))

    def test_helper_keep_existing_conflict_blocks_without_approval(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            (root / ".codex").mkdir()
            (root / ".codex/config.toml").write_text("[mcp_servers.mentality]\ncommand = \"python\"\n", encoding="utf-8")

            proposal = helper.propose_project_init(
                project_root=root,
                selected_services=[service_descriptor("mentality")],
                inputs={"resolve-config-conflict": "keep_existing_block"},
            )

        self.assertEqual("activation_blocked", proposal["status"])
        self.assertNotIn("approval_challenge", proposal)
        self.assertEqual("mentality", proposal["blocked_services"][0]["alias"])

    def test_helper_recovery_replaces_unmanaged_project_local_conflict_with_approval(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            plan = contextforge_helper_mcp.propose_project_init(str(root), [service_descriptor("context7")])
            self.assertTrue(plan["ok"])
            (root / ".codex").mkdir(exist_ok=True)
            (root / ".codex/config.toml").write_text("[mcp_servers.context7]\ncommand = \"npx\"\n", encoding="utf-8")

            recovery = contextforge_helper_mcp.cf_project_init_recovery_propose(str(root))
            challenge = recovery["approval_challenge"]
            approval = contextforge_helper_mcp.cf_project_init_recovery_approve(
                str(root),
                challenge["challenge_id"],
                recovery["plan_digest"],
            )
            applied = contextforge_helper_mcp.cf_project_init_recovery_apply(str(root))
            config_text = (root / ".codex/config.toml").read_text(encoding="utf-8")
            cached_activation = contextforge_helper_mcp._matching_cached_plan(str(root), plan["approval_challenge"]["challenge_id"], plan["plan_digest"])

        self.assertEqual("recovery_plan_ready", recovery["status"])
        self.assertEqual(["project_local_config_write"], recovery["required_consent_classes"])
        self.assertEqual("allow", approval["decision"])
        self.assertEqual("project_init_recovery_applied", applied["status"])
        self.assertIn(binding.PROJECT_INIT_OWNER_MARKER, config_text)
        self.assertIn("[mcp_servers.context7]", config_text)
        self.assertIn("contextforge_mcp_wrapper.py", config_text)
        self.assertNotIn('command = "npx"', config_text)
        self.assertEqual("resume-approved-project-init-apply", applied["next_turn"]["question_id"])
        self.assertEqual(plan["plan_id"], cached_activation["plan_id"])

    def test_helper_caches_embedded_recovery_plan_from_config_conflict(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            contextforge_helper_mcp._clear_durable_cache(str(root))
            contextforge_helper_mcp._CACHED_PLANS.clear()
            contextforge_helper_mcp._CACHED_RECEIPTS.clear()
            contextforge_helper_mcp._CACHED_RECOVERY_PLANS.clear()
            contextforge_helper_mcp._CACHED_RECOVERY_RECEIPTS.clear()
            (root / ".codex").mkdir()
            (root / ".codex/config.toml").write_text("[mcp_servers.context7]\ncommand = \"npx\"\n", encoding="utf-8")

            conflict = contextforge_helper_mcp.cf_project_init_propose(str(root), [service_descriptor("context7")])
            recovery_plan = conflict["recovery_plan"]
            challenge = recovery_plan["approval_challenge"]
            cached_recovery = contextforge_helper_mcp.cf_project_init_recovery_propose(str(root))
            approval = contextforge_helper_mcp.cf_project_init_recovery_approve(
                str(root),
                challenge["challenge_id"],
                recovery_plan["plan_digest"],
            )

        self.assertEqual("config_conflict", conflict["status"])
        self.assertEqual("recovery_plan_ready", recovery_plan["status"])
        self.assertEqual(recovery_plan["plan_digest"], cached_recovery["plan_digest"])
        self.assertEqual("allow", approval["decision"])

    def test_helper_serena_recovery_ensures_backend_when_live_readback_is_missing(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as project_tmp, tempfile.TemporaryDirectory(dir=REPO_ROOT) as instances_tmp:
            root = Path(project_tmp).resolve()
            identity = common.project_identity(root)
            instance = Path(instances_tmp) / identity.instance_slug
            instance.mkdir(parents=True)
            (instance / "instance.json").write_text(
                json.dumps(
                    {
                        "service": "serena",
                        "name": identity.instance_slug,
                        "slug": identity.instance_slug,
                        "canonical_project_root": str(root),
                        "server_name": identity.server_name,
                        "contextforge": {
                            "gateway": {"id": "gateway-1", "name": "contextforge"},
                            "virtual_server": {"id": "server-1", "name": identity.server_name},
                        },
                        "scope": {"workspace_root": str(root), "scope_type": "single_workspace_code_intelligence"},
                        "backend": {"transport": "streamable-http"},
                    }
                ),
                encoding="utf-8",
            )
            (root / ".codex").mkdir()
            (root / ".codex/config.toml").write_text("[mcp_servers.serena]\ncommand = \"serena\"\n", encoding="utf-8")
            service = common.discover_contextforge_hosted_services(
                project_root=root,
                contextforge_servers=[],
                server_instances_root=instances_tmp,
            )[0]
            proposal = helper.propose_project_init(
                project_root=root,
                selected_services=[service],
                inputs={"language": "typescript"},
                contextforge_servers=[],
                server_instances_root=instances_tmp,
            )

        self.assertEqual("missing", service["contextforge_readback_status"])
        self.assertEqual("required", service["provisioning"]["status"])
        self.assertEqual("config_conflict", proposal["status"])
        recovery_plan = proposal["recovery_plan"]
        self.assertEqual({"project_local_config_write", "service_provision"}, set(recovery_plan["required_consent_classes"]))
        ensure_ops = [
            operation
            for operation in recovery_plan["service_recovery_plan"]
            if operation["operation"] == "ensure_project_scoped_serena_instance"
        ]
        self.assertEqual(1, len(ensure_ops))
        self.assertTrue(ensure_ops[0]["recovery_required"])
        self.assertEqual("typescript", ensure_ops[0]["language"])

    def test_helper_recovery_handles_serena_wrapper_and_provisioning_together(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            identity = common.project_identity(root)
            contextforge_helper_mcp._clear_durable_cache(str(root))
            contextforge_helper_mcp._CACHED_PLANS.clear()
            contextforge_helper_mcp._CACHED_RECEIPTS.clear()
            contextforge_helper_mcp._CACHED_RECOVERY_PLANS.clear()
            contextforge_helper_mcp._CACHED_RECOVERY_RECEIPTS.clear()
            (root / ".codex").mkdir()
            (root / ".codex/config.toml").write_text("[mcp_servers.serena]\ncommand = \"serena\"\n", encoding="utf-8")

            conflict = contextforge_helper_mcp.cf_project_init_propose(
                str(root),
                ["serena"],
                inputs={"language": "typescript"},
            )
            recovery_plan = conflict["recovery_plan"]
            challenge = recovery_plan["approval_challenge"]
            approval = contextforge_helper_mcp.cf_project_init_recovery_approve(
                str(root),
                challenge["challenge_id"],
                recovery_plan["plan_digest"],
            )

            def fake_provision(provision_root: Path, service: dict[str, Any], *, language: str, client_type: str) -> dict[str, Any]:
                return {
                    "service_binding": f"serena:{identity.hash}",
                    "status": "completed",
                    "operation_type": "provision_project_scoped_serena",
                    "language": language,
                    "instance_slug": identity.instance_slug,
                    "server_name": identity.server_name,
                    "pre_digest": None,
                    "post_digest": common.stable_digest({"instance_slug": identity.instance_slug, "language": language}),
                }

            with mock.patch.object(helper, "_run_serena_project_provisioning", side_effect=fake_provision) as provision:
                applied = contextforge_helper_mcp.cf_project_init_recovery_apply(str(root))
            config_text = (root / ".codex/config.toml").read_text(encoding="utf-8")

        self.assertEqual("config_conflict", conflict["status"])
        self.assertEqual({"project_local_config_write", "service_provision"}, set(recovery_plan["required_consent_classes"]))
        ensure_ops = [
            operation
            for operation in recovery_plan["service_recovery_plan"]
            if operation["operation"] == "ensure_project_scoped_serena_instance"
        ]
        self.assertEqual(1, len(ensure_ops))
        self.assertEqual("typescript", ensure_ops[0]["language"])
        self.assertEqual("allow", approval["decision"])
        provision.assert_called_once()
        self.assertEqual("typescript", provision.call_args.kwargs["language"])
        self.assertEqual("project_init_recovery_applied", applied["status"])
        self.assertIn("[mcp_servers.serena]", config_text)
        self.assertIn("contextforge_mcp_wrapper.py", config_text)
        self.assertIn(identity.server_name, config_text)
        self.assertNotIn('command = "serena"', config_text)

    def test_helper_serena_reset_recovery_removes_stale_instance_before_reprovision(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            identity = common.project_identity(root)
            (root / ".codex").mkdir()
            (root / ".codex/config.toml").write_text("[mcp_servers.serena]\ncommand = \"serena\"\n", encoding="utf-8")
            plan = helper.propose_project_init(
                project_root=root,
                selected_services=["serena"],
                inputs={"language": "typescript", "reset_project_scoped_services": True},
            )
            recovery_plan = plan["recovery_plan"]
            challenge = recovery_plan["approval_challenge"]
            approval = helper.approve_project_init_recovery_plan(
                project_root=root,
                plan=recovery_plan,
                approval={
                    "decision": "approve",
                    "challenge_id": challenge["challenge_id"],
                    "plan_digest": recovery_plan["plan_digest"],
                },
                local_approval_event_ref=helper.record_local_approval_event(
                    project_root=root,
                    plan=recovery_plan,
                    issuer_token=helper._LOCAL_APPROVAL_ISSUER_TOKEN,
                    channel="interactive_user",
                )["event_ref"],
            )

            removal_calls: list[dict[str, Any]] = []
            provision_calls: list[dict[str, Any]] = []

            def fake_remove(removal_root: Path, operation: dict[str, Any]) -> dict[str, Any]:
                removal_calls.append(dict(operation))
                return {
                    "service_binding": operation["service_binding"],
                    "operation": operation["operation"],
                    "status": "completed",
                    "stdout": {"removed_unit": identity.instance_slug},
                }

            def fake_provision(provision_root: Path, service: dict[str, Any], *, language: str, client_type: str) -> dict[str, Any]:
                provision_calls.append({"language": language, "client_type": client_type, "service_binding": service["service_binding"]})
                return {
                    "service_binding": f"serena:{identity.hash}",
                    "status": "completed",
                    "operation_type": "provision_project_scoped_serena",
                    "language": language,
                    "instance_slug": identity.instance_slug,
                    "server_name": identity.server_name,
                    "pre_digest": None,
                    "post_digest": common.stable_digest({"instance_slug": identity.instance_slug, "language": language}),
                }

            with mock.patch.object(helper, "_run_serena_project_removal", side_effect=fake_remove), mock.patch.object(
                helper,
                "_run_serena_project_provisioning",
                side_effect=fake_provision,
            ):
                applied = helper.apply_project_init_recovery(
                    project_root=root,
                    plan=recovery_plan,
                    receipts=approval["receipts"],
                    dry_run=False,
                )

            config_text = (root / ".codex" / "config.toml").read_text(encoding="utf-8")

        self.assertEqual("recovery_plan_ready", recovery_plan["status"])
        self.assertEqual({"project_local_config_write", "service_provision"}, set(recovery_plan["required_consent_classes"]))
        self.assertEqual(1, len([op for op in recovery_plan["service_recovery_plan"] if op["operation"] == "remove_stale_project_scoped_serena_instance"]))
        self.assertEqual(1, len([op for op in recovery_plan["service_recovery_plan"] if op["operation"] == "ensure_project_scoped_serena_instance"]))
        self.assertEqual(1, len(removal_calls))
        self.assertEqual(1, len(provision_calls))
        self.assertEqual("typescript", provision_calls[0]["language"])
        self.assertEqual("project_init_recovery_applied", applied["status"])
        self.assertIn("[mcp_servers.serena]", config_text)
        self.assertIn("contextforge_mcp_wrapper.py", config_text)
        self.assertNotIn('command = "serena"', config_text)

    def test_apply_time_recovery_resumes_cached_apply_after_provision_conflict(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            identity = common.project_identity(root)
            contextforge_helper_mcp._clear_durable_cache(str(root))
            contextforge_helper_mcp._CACHED_PLANS.clear()
            contextforge_helper_mcp._CACHED_RECEIPTS.clear()
            contextforge_helper_mcp._CACHED_RECOVERY_PLANS.clear()
            contextforge_helper_mcp._CACHED_RECOVERY_RECEIPTS.clear()
            plan = contextforge_helper_mcp.cf_project_init_propose(
                str(root),
                ["context7:canonical", "serena"],
                inputs={"language": "python"},
            )
            approval = contextforge_helper_mcp.cf_project_init_approve(
                str(root),
                plan["approval_challenge"]["challenge_id"],
                plan["plan_digest"],
            )
            provision_calls: list[dict[str, Any]] = []

            def fake_provision(provision_root: Path, service: dict[str, Any], *, language: str, client_type: str) -> dict[str, Any]:
                provision_calls.append({"language": language, "client_type": client_type, "service_binding": service["service_binding"]})
                if len(provision_calls) == 1:
                    (provision_root / ".codex").mkdir(exist_ok=True)
                    (provision_root / ".codex/config.toml").write_text("[mcp_servers.serena]\ncommand = \"serena\"\n", encoding="utf-8")
                return {
                    "service_binding": f"serena:{identity.hash}",
                    "status": "completed",
                    "operation_type": "provision_project_scoped_serena",
                    "language": language,
                    "instance_slug": identity.instance_slug,
                    "server_name": identity.server_name,
                    "pre_digest": None,
                    "post_digest": common.stable_digest({"instance_slug": identity.instance_slug, "language": language}),
                }

            with mock.patch.object(helper, "_run_serena_project_provisioning", side_effect=fake_provision):
                result = contextforge_helper_mcp.cf_project_init_apply(str(root))
            activation_receipt_unconsumed_after_conflict = approval["receipts"][0]["receipt_id"] not in helper._CONSUMED_RECEIPT_IDS
            recovery_plan = result["recovery_plan"]
            recovery_approval = contextforge_helper_mcp.cf_project_init_recovery_approve(
                str(root),
                recovery_plan["approval_challenge"]["challenge_id"],
                recovery_plan["plan_digest"],
            )
            with mock.patch.object(helper, "_run_serena_project_provisioning", side_effect=fake_provision):
                recovery = contextforge_helper_mcp.cf_project_init_recovery_apply(str(root))

            contextforge_helper_mcp._CACHED_PLANS.clear()
            contextforge_helper_mcp._CACHED_RECEIPTS.clear()
            contextforge_helper_mcp._CACHED_RECOVERY_PLANS.clear()
            contextforge_helper_mcp._CACHED_RECOVERY_RECEIPTS.clear()
            helper._APPROVED_RECEIPT_IDS_BY_PLAN.clear()
            with mock.patch.object(helper, "_run_serena_project_provisioning", side_effect=fake_provision):
                resumed = contextforge_helper_mcp.cf_project_init_apply(str(root))
            config_text = (root / ".codex" / "config.toml").read_text(encoding="utf-8")
            written = project_state.load_state(root)

        self.assertTrue(plan["ok"])
        self.assertEqual("allow", approval["decision"])
        self.assertEqual("config_recovery_required", result["status"])
        self.assertEqual("serena", result["blocked_services"][0]["alias"])
        self.assertEqual("approve-project-init-config-recovery", result["next_turn"]["question_id"])
        self.assertIn("recovery_plan", result)
        self.assertTrue(activation_receipt_unconsumed_after_conflict)
        self.assertEqual("allow", recovery_approval["decision"])
        self.assertEqual("project_init_recovery_applied", recovery["status"])
        self.assertEqual("resume-approved-project-init-apply", recovery["next_turn"]["question_id"])
        self.assertTrue(resumed["ok"])
        self.assertEqual("codex-project-init-installed", resumed["next_turn"]["question_id"])
        self.assertIn("[mcp_servers.serena]", config_text)
        self.assertIn("contextforge_mcp_wrapper.py", config_text)
        self.assertNotIn('command = "serena"', config_text)
        self.assertEqual(2, len(provision_calls))
        assert written is not None
        self.assertTrue(any(binding_id.startswith("serena:") for binding_id in written["services"]))

    def test_helper_plan_summary_includes_exact_alias_virtual_server_bindings(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            proposal = helper.propose_project_init(project_root=root, selected_services=[service_descriptor("context7")])

        summary = proposal["plan_summary"]
        self.assertEqual([str(root / ".codex" / "config.toml"), str(project_state.project_state_path(root))], summary["project_local_writes"])
        self.assertEqual("context7", summary["bindings"][0]["codex_alias"])
        self.assertEqual("context7_server", summary["bindings"][0]["virtual_server"])
        self.assertEqual("append", summary["bindings"][0]["config_operation"])

    def test_project_init_prompt_is_not_serena_only_and_preserves_approval_boundaries(self) -> None:
        text = prompt_registration.PROJECT_INIT_TEXT

        self.assertIn("Which ContextForge services should I activate for this project?", text)
        self.assertIn("discovered shared canonical services and project-scoped options", text)
        self.assertIn("Serena is one project-scoped option in this menu, not the whole flow", text)
        self.assertIn("After approved apply, report success clearly and succinctly", text)
        self.assertIn("No user-global config/trust/extension changes", text)
        self.assertIn("for Codex this is project-local .codex/config.toml", text)
        self.assertIn("for Pi this is .project/context_forge_state.json records", text)
        self.assertIn("hidden or structured prompt/context injection", text)
        self.assertIn("Do not narrate helper/tool/cache/payload mechanics", text)
        self.assertIn("copy that value as the complete visible reply and stop", text)
        self.assertIn("input-triggered hidden message", text)
        self.assertIn("cf_project_init_prompt and cf_contextforge_pi_readback are diagnostic only", text)
        self.assertIn("After approved apply", text)
        self.assertIn("selected ContextForge tools are installed", text)
        self.assertIn("must start a new session or reload", text)
        self.assertIn("Stop there", text)
        self.assertNotIn("Do not substitute built-in web search, direct shell commands, direct SSH/tmux", text)
        self.assertNotIn("validate_now", text)
        self.assertIn("call cf_project_init_approve with the exact challenge id and plan digest", text)
        self.assertIn("call cf_project_init_apply using the cached plan and receipts", text)
        self.assertIn("status=config_conflict with an embedded recovery_plan", text)
        self.assertIn("call cf_project_init_recovery_approve with the exact recovery challenge id and recovery plan digest", text)
        self.assertIn("call cf_project_init_recovery_apply using the cached recovery plan and receipts", text)
        self.assertIn("Do not call apply_project_init_recovery with only plan_id, plan_digest, or receipt ids", text)
        self.assertIn("complete helper-returned recovery plan object and full receipt objects", text)
        self.assertIn("keep them together in the helper recovery approval/apply path", text)
        self.assertIn("Never choose service selections or approval", text)
        self.assertIn("If the user echoes your question, asks you to provide the selection numbers", text)
        self.assertIn("Do not invoke project-init helper scripts or Python modules through shell", text)
        self.assertIn("helper cache is missing or stale", text)
        self.assertIn("do not silently replace the challenge id", text)
        self.assertIn("prefer those cached id/digest tools over reconstructing a full plan object", text)
        self.assertIn("Stop there", text)
        self.assertIn("Codex launches configured MCP servers and exposes their tools when a session starts", text)
        self.assertIn("/mcp is a status view, not an in-place MCP tool reload", text)
        self.assertIn("start a new Codex session from the project root after installation", text)
        self.assertIn("the Pi agent must issue /reload after an approved global extension install or upgrade", text)
        self.assertIn("pi.registerTool()", text)

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
                        "--consent-receipt-ref",
                        CONSENT_REFS[0],
                        "--consent-receipt-ref",
                        CONSENT_REFS[1],
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
