from __future__ import annotations

import json
import contextlib
import io
import inspect
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
        "proof_kind": "pi_safe_probe_result",
        "safe_probe_result": "passed",
        "safe_probe_id": "resolve-library-id",
        "verification_trace_refs": [f"pi://contextforge-global-shim/tools/{tool_name}"],
    }


def record_pi_reload(root: Path) -> dict[str, Any]:
    return helper.record_project_init_client_reload(project_root=root, client_type="pi")


def record_codex_new_session(root: Path) -> dict[str, Any]:
    return helper.record_project_init_client_reload(project_root=root, client_type="codex")


def serena_descriptor() -> dict[str, Any]:
    service = service_descriptor("serena")
    service["service_binding"] = "serena:project"
    service["instantiation_class"] = "instance_per_project"
    service["activation_class"] = "client_local_project_scoped"
    service["display_name"] = "Serena"
    return service


class ProjectInitActivationWorkflowTests(unittest.TestCase):
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

    def test_opencode_config_plan_writes_managed_mcp_and_plugin(self) -> None:
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
        self.assertIn("contextforge-project-init-owner", plan["plugin_next_text"])
        self.assertIn("opencode_project_init_hook.py", plan["plugin_next_text"])
        self.assertIn("timeout: 10000", plan["plugin_next_text"])
        self.assertIn("does not write user-global OpenCode config or plugins", plan["non_actions"])

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
        self.assertEqual("in_progress", result["state_status"])
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
        self.assertIn("Before validating", readiness["client_reload_requirement"]["instruction"])
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

    def test_opencode_is_supported_with_project_local_config_and_plugin_writer(self) -> None:
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
        self.assertIn("experimental.chat.system.transform", config_plan["plugin_next_text"])
        self.assertIn("opencode_project_init_hook.py", config_plan["plugin_next_text"])
        self.assertIn(str(root / "opencode.json"), proposal["plan_summary"]["project_local_writes"])
        self.assertIn(str(root / ".opencode" / "plugins" / "contextforge-project-init.js"), proposal["plan_summary"]["project_local_writes"])
        self.assertEqual(
            [
                str(root / "opencode.json"),
                str(root / ".opencode" / "plugins" / "contextforge-project-init.js"),
                str(project_state.project_state_path(root)),
            ],
            result["writes"],
        )
        service = result["planned_state"]["services"]["context7:canonical"]
        self.assertNotIn("codex", service["target_clients"])
        self.assertEqual("project_local_opencode_config_planned", service["target_clients"]["opencode"]["status"])
        self.assertEqual(binding.OPENCODE_CONFIG_SURFACE, service["target_clients"]["opencode"]["surface"])
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
        self.assertIn(codex_resume["status"], {"config_repair_required", "client_reload_required", "resume_validation"})
        self.assertIn(gemini_resume["status"], {"config_repair_required", "client_reload_required", "resume_validation"})
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
        self.assertEqual("pi-client-reload-before-validation", result["next_turn"]["question_id"])
        self.assertEqual("/reload", result["client_reload_requirement"]["command"])
        self.assertIn("After the reload", result["next_turn"]["prompt"])
        self.assertIn('choose 1 or reply "validate"', result["next_turn"]["allowed_response_shape"])
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

    def test_pi_helper_resumes_pending_validation_when_shim_metadata_is_current(self) -> None:
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

            reload_required = helper.list_available_capabilities(project_root=root, client_type="pi")
            ack = record_pi_reload(root)
            capabilities = helper.list_available_capabilities(project_root=root, client_type="pi")
            proposal = helper.propose_project_init(project_root=root, selected_services=[service_descriptor("github")], client_type="pi")

        self.assertEqual("client_reload_required", reload_required["status"])
        self.assertEqual("pi-client-reload-before-validation", reload_required["next_turn"]["question_id"])
        self.assertEqual("client_reload_recorded", ack["status"])
        self.assertTrue(ack["current_job"]["client_reload_acknowledged"])
        self.assertEqual("resume_validation", capabilities["status"])
        self.assertEqual("validation-choice", capabilities["next_turn"]["question_id"])
        self.assertEqual(["context7:canonical"], capabilities["current_job"]["selected_service_bindings"])
        self.assertEqual("resume_validation", proposal["status"])
        self.assertEqual("validation-choice", proposal["next_turn"]["question_id"])

    def test_pi_helper_detects_and_repairs_pending_shim_metadata_drift(self) -> None:
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
            state["services"]["github:canonical"]["target_clients"].pop("pi")
            project_state.write_state_atomic(root, state)

            capabilities = helper.list_available_capabilities(project_root=root, client_type="pi")
            blocked_validation = helper.record_project_init_validation(
                project_root=root,
                client_type="pi",
                validation_mode="validate_now",
                validation_results={"context7:canonical": {"status": "passed", "target_client_visible": True}},
                dry_run=True,
            )
            repair = helper.repair_pending_project_init_config(project_root=root, client_type="pi")
            repaired_state = project_state.load_state(root)
            after = helper.list_available_capabilities(project_root=root, client_type="pi")
            ack = record_pi_reload(root)
            after_ack = helper.list_available_capabilities(project_root=root, client_type="pi")

        self.assertEqual("config_repair_required", capabilities["status"])
        self.assertEqual("repair-pi-shim-activation-metadata", capabilities["next_turn"]["question_id"])
        self.assertEqual(["github:canonical"], capabilities["config_repair"]["changed_service_bindings"])
        self.assertEqual("config_repair_required", blocked_validation["status"])
        self.assertEqual("config_repaired", repair["status"])
        self.assertFalse((root / ".codex/config.toml").exists())
        assert repaired_state is not None
        self.assertEqual("contextforge-global-shim", repaired_state["services"]["github:canonical"]["target_clients"]["pi"]["shim"])
        self.assertEqual("client_reload_required", after["status"])
        self.assertEqual("client_reload_recorded", ack["status"])
        self.assertEqual("resume_validation", after_ack["status"])
        self.assertEqual("validation-choice", after_ack["next_turn"]["question_id"])

    def test_pi_helper_records_validation_only_with_pi_visible_proof(self) -> None:
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

            blocked_before_reload = helper.record_project_init_validation(
                project_root=root,
                client_type="pi",
                validation_mode="validate_now",
                validation_results={"context7:canonical": pi_safe_probe_validation()},
                dry_run=True,
            )
            ack = record_pi_reload(root)
            backend_only = helper.record_project_init_validation(
                project_root=root,
                client_type="pi",
                validation_mode="validate_now",
                validation_results={"context7:canonical": {"status": "passed", "target_client_visible": False}},
                dry_run=True,
            )
            weak_visible = helper.record_project_init_validation(
                project_root=root,
                client_type="pi",
                validation_mode="validate_now",
                validation_results={
                    "context7:canonical": {
                        "status": "passed",
                        "target_client_visible": True,
                        "verification_trace_refs": ["pi://contextforge-global-shim/tools/cf_context7_s123__resolve"],
                    }
                },
                dry_run=True,
            )
            visible = helper.record_project_init_validation(
                project_root=root,
                client_type="pi",
                validation_mode="validate_now",
                validation_results={"context7:canonical": pi_safe_probe_validation()},
            )
            written = project_state.load_state(root)

        self.assertEqual("client_reload_required", blocked_before_reload["status"])
        self.assertEqual("pi-client-reload-before-validation", blocked_before_reload["next_turn"]["question_id"])
        self.assertEqual("client_reload_recorded", ack["status"])
        self.assertEqual("validation_recorded_dry_run", backend_only["status"])
        self.assertEqual("in_progress", backend_only["project_status"])
        self.assertEqual("validation_recorded_dry_run", weak_visible["status"])
        self.assertEqual("in_progress", weak_visible["project_status"])
        self.assertEqual("validation_recorded", visible["status"])
        self.assertEqual("initialized", visible["project_status"])
        self.assertFalse((root / ".codex/config.toml").exists())
        assert written is not None
        service = written["services"]["context7:canonical"]
        self.assertEqual("passed", service["target_clients"]["pi"]["validation_status"])
        self.assertEqual("passed", service["verification_layers"]["target_client"]["status"])

    def test_pi_helper_restores_safe_policy_from_state_with_null_policy(self) -> None:
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

        self.assertEqual("validation_recorded", result["status"])
        assert written is not None
        policy = written["services"]["context7:canonical"]["verification_layers"]["tool_policy"]["policy"]
        self.assertEqual(common.safe_validation_policy("context7"), policy)
        self.assertEqual("passed", written["services"]["context7:canonical"]["target_clients"]["pi"]["validation_status"])

    def test_pi_helper_can_revalidate_after_stale_skipped_readback(self) -> None:
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

            record_pi_reload(root)
            first = helper.record_project_init_validation(
                project_root=root,
                client_type="pi",
                validation_mode="validate_now",
                validation_results={
                    "context7:canonical": {
                        "status": "skipped",
                        "skipped_reason": "project state has no approved target_clients.pi service bindings",
                    }
                },
            )
            stale = project_state.load_state(root)
            assert stale is not None
            job = stale["project_init"]["activation_jobs"][stale["project_init"]["current_job_id"]]
            job["local_client_config_digest"] = "sha256:" + ("0" * 64)
            project_state.write_state_atomic(root, stale)

            resume = helper.list_available_capabilities(project_root=root, client_type="pi")
            result = helper.record_project_init_validation(
                project_root=root,
                client_type="pi",
                validation_mode="validate_now",
                validation_results={"context7:canonical": pi_safe_probe_validation()},
            )
            written = project_state.load_state(root)

        self.assertEqual("validation_recorded", first["status"])
        self.assertEqual("resume_validation", resume["status"])
        self.assertEqual("validation_recorded", result["status"])
        assert written is not None
        self.assertEqual("initialized", written["status"])
        job = written["project_init"]["activation_jobs"][written["project_init"]["current_job_id"]]
        self.assertNotEqual("sha256:" + ("0" * 64), job["local_client_config_digest"])
        self.assertEqual("passed", written["services"]["context7:canonical"]["verification_layers"]["target_client"]["status"])

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
        self.assertEqual("pi-client-reload-before-validation", plan["next_turn"]["question_id"])
        self.assertIn("After the reload", plan["next_turn"]["prompt"])
        self.assertIn('choose 1 or reply "validate"', plan["next_turn"]["allowed_response_shape"])
        self.assertEqual(1, plan["next_turn"]["choices"][0]["number"])
        self.assertEqual("installed_current", installed["status"])
        self.assertEqual("/reload", installed["client_reload"]["command"])
        self.assertIn("Before validating", installed["next_action"])

    def test_pi_extension_source_registers_bootstrap_helper_tools_without_bridge_reuse(self) -> None:
        text = (REPO_ROOT / "pi-extensions/contextforge-global-shim/index.ts").read_text(encoding="utf-8")

        self.assertIn("cf_project_init_list_capabilities", text)
        self.assertIn("cf_project_init_approve", text)
        self.assertIn("cf_project_init_record_client_reload", text)
        self.assertIn("pi_project_init_helper_cli.py", text)
        self.assertIn('pi.on("before_agent_start"', text)
        self.assertIn("injectProjectInitPrompt", text)
        self.assertIn("runHelperOperationJson", text)
        self.assertIn("projectInitCache", text)
        self.assertIn("resolveCachedPlan", text)
        self.assertIn("status: \"already_approved_from_pi_shim_cache\"", text)
        self.assertIn("status: \"already_applied_from_pi_shim_cache\"", text)
        self.assertIn("Supplying the full plan is optional", text)
        self.assertIn('renderShell: "self"', text)
        self.assertIn("renderNothing", text)
        self.assertIn("new Container()", text)
        self.assertIn("cf_project_init_prompt", text)
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
        self.assertIn("cf_contextforge_pi_validate", text)
        self.assertIn("cf_project_init_validate", text)
        self.assertIn("Compatibility alias for cf_contextforge_pi_validate", text)
        self.assertIn("runPiValidation", text)
        self.assertIn('proof_kind: "pi_safe_probe_result"', text)
        self.assertIn("safe_probe_result", text)
        self.assertIn("safe_probe_available", text)
        self.assertIn("Call cf_project_init_record_validation", text)
        self.assertIn("await activateProject(pi, projectRootFromParams(params, ctx), clients)", text)
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
        self.assertIn("defaultSafeOperationsFor", text)
        self.assertIn("safeProbeArgs", text)
        self.assertIn("fitArgsToSchema", text)
        self.assertIn('base.libraryName = "React"', text)
        self.assertIn('base.query = "modelcontextprotocol"', text)
        self.assertIn('base.ledger = "decisions"', text)
        self.assertIn("probeArgsAvailable", text)
        self.assertIn("acceptStderr(chunk)", text)
        self.assertIn("contextforge-root.json", text)
        self.assertIn("CONTEXTFORGE_PI_SHIM_WORKSPACE_ROOT", text)
        self.assertNotIn("pi.registerTool({", text)
        self.assertNotIn("DEFAULT_PORTAL_ROOT", text)
        self.assertNotIn("/home/dgk/workspace", text)
        self.assertNotIn("console.error", text)
        self.assertNotIn("mcp-bridge", text)
        self.assertNotIn("registerContext7Tools", text)

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
            self.assertEqual(list(range(1, len(turn["choices"]) + 1)), [choice["number"] for choice in turn["choices"]])
            self.assertEqual(turn["choices"], turn["response_form"]["options"])
            self.assertIn("selection number", turn["allowed_response_shape"])

        assert_numbered(helper.validation_choice_turn())
        assert_numbered(helper.client_reload_before_validation_turn(common.client_reload_requirement("pi", event="project_activation_apply") or {}))
        assert_numbered(helper.client_reload_before_validation_turn(common.client_reload_requirement("codex", event="project_activation_apply") or {}))
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

    def test_helper_resumes_pending_validation_instead_of_restarting_selection(self) -> None:
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
        self.assertEqual("codex-client-reload-before-validation", capabilities["next_turn"]["question_id"])
        self.assertEqual(["context7:canonical"], capabilities["current_job"]["selected_service_bindings"])
        self.assertEqual("client_reload_required", proposal["status"])
        self.assertEqual("codex-client-reload-before-validation", proposal["next_turn"]["question_id"])
        self.assertEqual("client_reload_recorded", ack["status"])
        self.assertEqual("resume_validation", after_ack["status"])
        self.assertEqual("validation-choice", after_ack["next_turn"]["question_id"])

    def test_helper_detects_and_repairs_pending_config_drift_before_validation(self) -> None:
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
        self.assertEqual("config_repair_required", blocked_validation["status"])
        self.assertEqual("config_repaired", repair["status"])
        self.assertIn("[mcp_servers.github]", config_text)
        self.assertEqual("client_reload_required", after["status"])
        self.assertEqual("codex-client-reload-before-validation", after["next_turn"]["question_id"])
        self.assertEqual("client_reload_recorded", ack["status"])
        self.assertEqual("resume_validation", after_ack["status"])
        self.assertEqual("validation-choice", after_ack["next_turn"]["question_id"])

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
        self.assertEqual("codex-client-reload-before-validation", resume["next_turn"]["question_id"])
        self.assertEqual("client_reload_recorded", ack["status"])
        self.assertEqual("resume_validation", after_ack["status"])
        self.assertEqual("validation_recorded", presumed["status"])
        self.assertEqual("in_progress", presumed["project_status"])
        assert written is not None
        self.assertEqual("completed_unverified", written["project_init"]["x_hook_prompt_state"])
        migration = written["migration"]["client_config_migrations"]["codex"]
        self.assertEqual("unmanaged_same_name", migration["ownership_class"])
        self.assertEqual("conflict", migration["disposition"])
        self.assertEqual("presumed_working", written["services"]["context7:canonical"]["verification_layers"]["target_client"]["status"])

    def test_helper_records_validation_results_after_config_is_current(self) -> None:
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
                    "context7:canonical": {
                        "status": "passed",
                        "target_client_visible": True,
                        "verification_trace_refs": ["contextforge://control-plane/traces/context7-target-client"],
                    },
                    "github:canonical": {
                        "status": "skipped",
                        "skipped_reason": "credentials unavailable in this client turn",
                    },
                },
            )
            written = project_state.load_state(root)

        self.assertEqual("validation_recorded", result["status"])
        self.assertEqual("in_progress", result["project_status"])
        assert written is not None
        job = written["project_init"]["activation_jobs"][written["project_init"]["current_job_id"]]
        self.assertEqual("validation_pending", job["status"])
        self.assertEqual("passed", written["services"]["context7:canonical"]["verification_layers"]["target_client"]["status"])
        self.assertEqual("skipped", written["services"]["github:canonical"]["verification_layers"]["target_client"]["status"])

    def test_helper_rejects_nested_validation_results_without_recording_state(self) -> None:
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

        self.assertEqual("validation_results_unmatched", result["status"])
        self.assertNotIn("state_revision", result)
        self.assertEqual(["services"], result["validation_diagnostic"]["unmatched_keys"])
        self.assertEqual([], result["validation_diagnostic"]["matched_keys"])
        self.assertIn("context7:canonical", result["expected_validation_results_shape"])
        expected_shape = result["expected_validation_results_shape"]["context7:canonical"]
        self.assertEqual("target_client_safe_probe_result", expected_shape["proof_kind"])
        self.assertEqual("passed", expected_shape["safe_probe_result"])
        self.assertEqual("resolve-library-id", expected_shape["safe_probe_id"])
        self.assertEqual(
            ["contextforge://control-plane/traces/context7:canonical-target-client"],
            expected_shape["verification_trace_refs"],
        )
        assert after is not None
        self.assertEqual(before["meta"]["revision"], after["meta"]["revision"])
        job = after["project_init"]["activation_jobs"][after["project_init"]["current_job_id"]]
        self.assertEqual("pending_user_choice", job["validation_records"][job["selected_service_ids"][0]]["status"])

    def test_helper_reports_unmatched_validation_result_keys_without_recording_state(self) -> None:
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

        self.assertEqual("validation_results_unmatched", result["status"])
        self.assertNotIn("state_revision", result)
        self.assertEqual(["unselected:canonical"], result["validation_diagnostic"]["unmatched_keys"])
        self.assertEqual(["context7:canonical"], result["validation_diagnostic"]["missing_keys"])
        assert after is not None
        self.assertEqual(before["meta"]["revision"], after["meta"]["revision"])

    def test_helper_rejects_validation_result_values_that_are_not_objects(self) -> None:
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

        self.assertEqual("validation_results_unmatched", result["status"])
        self.assertEqual([], result["validation_diagnostic"]["matched_keys"])
        self.assertEqual(["context7:canonical"], result["validation_diagnostic"]["invalid_value_keys"])
        assert after is not None
        self.assertEqual(before["meta"]["revision"], after["meta"]["revision"])

    def test_helper_valid_top_level_binding_keyed_validation_marks_service_passed(self) -> None:
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
                        "target_client_visible": True,
                        "verification_trace_refs": ["contextforge://control-plane/traces/context7-target-client"],
                    }
                },
            )
            written = project_state.load_state(root)

        self.assertEqual("validation_recorded", result["status"])
        self.assertEqual("initialized", result["project_status"])
        self.assertEqual(["context7:canonical"], result["validation_diagnostic"]["matched_keys"])
        expected_shape = result["expected_validation_results_shape"]["context7:canonical"]
        self.assertEqual("target_client_safe_probe_result", expected_shape["proof_kind"])
        self.assertEqual("passed", expected_shape["safe_probe_result"])
        self.assertEqual("resolve-library-id", expected_shape["safe_probe_id"])
        assert written is not None
        self.assertEqual("passed", written["services"]["context7:canonical"]["verification_layers"]["target_client"]["status"])

    def test_helper_mixed_validation_results_preserve_partial_pending_behavior(self) -> None:
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
                    "context7:canonical": {
                        "status": "passed",
                        "target_client_visible": True,
                        "verification_trace_refs": ["contextforge://control-plane/traces/context7-target-client"],
                    },
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

        self.assertEqual("validation_recorded", result["status"])
        self.assertEqual("validation_results only matched a subset of selected services", result["warning"])
        self.assertEqual(["unselected:canonical"], result["validation_diagnostic"]["unmatched_keys"])
        self.assertEqual(["web-search:canonical"], result["validation_diagnostic"]["missing_keys"])
        assert written is not None
        self.assertEqual("in_progress", written["status"])
        self.assertEqual("passed", written["services"]["context7:canonical"]["verification_layers"]["target_client"]["status"])
        self.assertEqual("skipped", written["services"]["github:canonical"]["verification_layers"]["target_client"]["status"])
        self.assertEqual("pending", written["services"]["web-search:canonical"]["verification_layers"]["target_client"]["status"])

    def test_contextforge_helper_mcp_exposes_readiness_tool(self) -> None:
        result = contextforge_helper_mcp.get_project_context("/home/dgk/workspace/legacy-controlplane-archive")

        self.assertTrue(result["ok"])
        self.assertEqual("contextforge-helper", result["helper"]["name"])
        self.assertEqual("available", result["helper"]["status"])
        self.assertEqual("codex", result["root_attestation"]["client_type"])

    def test_contextforge_helper_validation_guidance_exposes_safe_probe_shape(self) -> None:
        helper_doc = contextforge_helper_mcp.record_project_init_validation.__doc__ or ""
        plan_doc = (
            REPO_ROOT / "docs/initiatives/contextforge-control-plane/contextforge-helper-project-init-plan.md"
        ).read_text(encoding="utf-8")

        for text in (helper_doc, plan_doc):
            with self.subTest(surface=text[:40]):
                self.assertIn("target_client_safe_probe_result", text)
                self.assertIn("safe_probe_result", text)
                self.assertIn("safe_probe_id", text)
                self.assertIn("resolve-library-id", text)
                self.assertIn("contextforge://control-plane/traces/context7:canonical-target-client", text)

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
                return_value={"ok": True, "next_turn": {"question_id": "codex-client-reload-before-validation"}, "client_reload_requirement": {"command": "start_new_session"}},
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
        self.assertEqual("codex-client-reload-before-validation", applied["next_turn"]["question_id"])
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
        self.assertEqual("codex-client-reload-before-validation", applied["next_turn"]["question_id"])
        self.assertEqual("start_new_session", applied["client_reload_requirement"]["command"])

    def test_contextforge_helper_mcp_accepts_service_ids_and_expands_descriptors(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT) as tmp:
            root = Path(tmp).resolve()
            instances = root / "instances"
            for service, server, scope_type in (
                ("context7", "context7_local_server", "shared_canonical"),
                ("mentality", "mentality_server", "caller_supplied_local_repo"),
                ("playwright", "playwright_server", "isolated_browser_runtime"),
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
                            "contextforge": {"virtual_server": {"name": server}, "gateway": {"name": "contextforge"}},
                            "backend": {"transport": "stdio"},
                            "scope": {"scope_type": scope_type},
                        }
                    ),
                    encoding="utf-8",
                )

            proposal = contextforge_helper_mcp.propose_project_init(
                str(root),
                ["context7:canonical", {"id": "mentality:static_repo_local"}, "playwright"],
                contextforge_servers=[
                    {"name": "context7_local_server", "id": "vs-context7"},
                    {"name": "mentality_server", "id": "vs-mentality"},
                    {"name": "playwright_server", "id": "vs-playwright"},
                ],
                server_instances_root=str(instances),
                inputs={},
            )

        self.assertTrue(proposal["ok"])
        self.assertEqual(
            {"context7:canonical", "mentality:static_repo_local", "playwright:session_scoped"},
            {service["service_binding"] for service in proposal["selected_services"]},
        )
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
            self.assertEqual("codex-client-reload-before-validation", applied["next_turn"]["question_id"])

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

            self.assertEqual("codex-client-reload-before-validation", first_apply["next_turn"]["question_id"])
            self.assertEqual("client_reload_recorded", record_codex_new_session(root)["status"])
            self.assertEqual(
                "validation_recorded",
                helper.record_project_init_validation(
                    project_root=root,
                    validation_mode="validate_now",
                    validation_results={
                        first_binding: {
                            "status": "passed",
                            "target_client_visible": True,
                            "verification_trace_refs": ["contextforge://control-plane/traces/serena-target-client"],
                        }
                    },
                )["status"],
            )

            second_plan = helper.propose_project_init(
                project_root=root,
                selected_services=["serena"],
                inputs={"language": "python"},
            )
            second_binding = str(second_plan["selected_services"][0]["service_binding"])
            second_approval = helper.approve_project_init_plan(
                project_root=root,
                plan=second_plan,
                approval={
                    "decision": "approve",
                    "challenge_id": second_plan["approval_challenge"]["challenge_id"],
                    "plan_digest": second_plan["plan_digest"],
                },
                local_approval_event_ref=helper.record_local_approval_event(
                    project_root=root,
                    plan=second_plan,
                    issuer_token=helper._LOCAL_APPROVAL_ISSUER_TOKEN,
                    channel="interactive_user",
                )["event_ref"],
            )

            with mock.patch.object(helper, "_run_serena_project_provisioning", side_effect=fake_provision):
                second_apply = helper.apply_approved_project_init(
                    project_root=root,
                    plan=second_plan,
                    receipts=second_approval["receipts"],
                )

            config_text = (root / ".codex" / "config.toml").read_text(encoding="utf-8")
            state = project_state.load_state(root)

        self.assertEqual(first_binding, second_binding)
        self.assertEqual("codex-client-reload-before-validation", second_apply["next_turn"]["question_id"])
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
            self.assertEqual("codex-client-reload-before-validation", result["next_turn"]["question_id"])
            self.assertEqual("start_new_session", result["client_reload_requirement"]["command"])
            self.assertIn("Codex launches configured MCP servers", result["next_turn"]["prompt"])
            self.assertFalse((root / ".codex/config.toml").exists())
            job = result["planned_state"]["project_init"]["activation_jobs"][result["planned_state"]["project_init"]["current_job_id"]]
            self.assertEqual("applied_validation_choice_pending", job["status"])
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
        self.assertEqual("codex-client-reload-before-validation", resumed["next_turn"]["question_id"])
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
        self.assertIn("Choose 1 to validate now", text)
        self.assertIn("No user-global config/trust/extension changes", text)
        self.assertIn("for Codex this is project-local .codex/config.toml", text)
        self.assertIn("for Pi this is .project/context_forge_state.json records", text)
        self.assertIn("hidden or structured prompt/context injection", text)
        self.assertIn("before_agent_start system-prompt context", text)
        self.assertIn("cf_project_init_prompt and cf_contextforge_pi_readback are diagnostic only", text)
        self.assertIn("cf_contextforge_pi_validate for validate-now", text)
        self.assertIn("Do not call unlisted or unavailable validation tool names", text)
        self.assertIn("validation tool call is missing, not found, unavailable, or returns an error", text)
        self.assertIn("Skipped-service follow-up", text)
        self.assertIn("Do not substitute built-in web search, direct shell commands, direct SSH/tmux", text)
        self.assertIn("tool exists", text)
        self.assertIn("call cf_project_init_approve with the exact challenge id and plan digest", text)
        self.assertIn("call cf_project_init_apply using the cached plan and receipts", text)
        self.assertIn("status=config_conflict with an embedded recovery_plan", text)
        self.assertIn("call cf_project_init_recovery_approve with the exact recovery challenge id and recovery plan digest", text)
        self.assertIn("call cf_project_init_recovery_apply using the cached recovery plan and receipts", text)
        self.assertIn("Do not call apply_project_init_recovery with only plan_id, plan_digest, or receipt ids", text)
        self.assertIn("complete helper-returned recovery plan object and full receipt objects", text)
        self.assertIn("keep them together in the helper recovery approval/apply path", text)
        self.assertIn("Never choose service selections, approval, reload acknowledgement, validation", text)
        self.assertIn("If the user echoes your question, asks you to provide the selection numbers", text)
        self.assertIn("Do not invoke project-init helper scripts or Python modules through shell", text)
        self.assertIn("helper cache is missing or stale", text)
        self.assertIn("do not silently replace the challenge id", text)
        self.assertIn("prefer those cached id/digest tools over reconstructing a full plan object", text)
        self.assertIn("first call cf_project_init_record_client_reload", text)
        self.assertIn("honor that choice after recording the reload acknowledgement instead of asking again", text)
        self.assertIn("after the reload or new session, resume project init", text)
        self.assertIn("Codex launches configured MCP servers and exposes their tools when a session starts", text)
        self.assertIn("/mcp is a status view, not an in-place MCP tool reload", text)
        self.assertIn("start a new Codex session from the project root before target-client-visible validation", text)
        self.assertIn("the Pi agent must issue /reload before validation", text)
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
