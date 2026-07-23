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
import urllib.error
from unittest import mock
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import control_plane_contextforge_binding as binding
import control_plane_authorization as authorization
import control_plane_project_init_helper as helper
import contextforge_helper_mcp
import control_plane_service_onboarding_surfaces as onboarding_surfaces
import control_plane_project_state as project_state
import manage_pi_global_shim
import manage_serena_project_instance as serena_manager
import pi_contextforge_shim_dry_run
import pi_project_init_helper_cli
import project_init_common as common
import register_project_init_prompt as prompt_registration
import register_service_offerings as service_offering_registration


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


def registry_service_descriptor(
    name: str = "context7",
    *,
    binding: str | None = None,
    instantiation_class: str | None = None,
) -> dict[str, Any]:
    descriptor = service_descriptor(name)
    if binding is not None:
        descriptor["service_binding"] = binding
    if instantiation_class is not None:
        descriptor["instantiation_class"] = instantiation_class
    descriptor.update(
        {
            "catalog_source": "contextforge_registry",
            "helper_metadata_status": "derived_from_contextforge_registry",
            "description": f"{name} documentation lookup",
            "scope_model": "global",
        }
    )
    return descriptor


def service_offering_metadata(
    name: str = "context7",
    *,
    server_id: str = "vs-context7",
    gateway_id: str = "gw-context7",
    binding: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_uri": common.SERVICE_OFFERING_SCHEMA_URI,
        "metadata_version": 1,
        "resource_uri": f"contextforge://control-plane/service-offerings/{name}/v1",
        "offering_id": name,
        "service_family": name,
        "canonical_service": name,
        "display_name": name,
        "description": f"{name} documentation lookup",
        "aliases": [name],
        "scope_model": "global",
        "scope_type": "global",
        "instance_model": "shared_canonical",
        "instantiation_class": "shared_canonical",
        "binding": {"mode": "literal", "value": binding or f"{name}:canonical"},
        "runtime": {
            "server_id": server_id,
            "server_name": f"{common.normalize_codex_alias(name)}_server",
            "gateway_id": gateway_id,
            "gateway_name": name,
            "reload_required": True,
        },
        "helper": {
            "actions_supported": ["list", "enable", "disable", "remove", "repair", "details"],
            "required_context": {},
            "client_support": {},
        },
        "guidance": {},
        "lifecycle": "active",
        "provenance": {"source": "test"},
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


def npm_stdio_required_payload() -> dict[str, Any]:
    return {
        "packageRegistryType": "npm",
        "packageVersion": "1.0.0",
        "runtimeHint": "npx",
        "npmPackageConfirmed": True,
        "environmentVariablesReviewed": True,
        "packageArgumentsReviewed": True,
        "environmentVariables": [],
        "packageArguments": [],
        "requiredSecretNames": [],
        "toolSchemas": {
            "get_current_time": {
                "inputSchema": {
                    "type": "object",
                    "properties": {"timezone": {"type": "string"}},
                    "required": ["timezone"],
                }
            },
            "convert_time": {
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "source_timezone": {"type": "string"},
                        "target_timezone": {"type": "string"},
                        "time": {"type": "string"},
                    },
                    "required": ["source_timezone", "target_timezone", "time"],
                }
            },
        },
        "promptLibrary": {
            "abstract_prompt": "Time provides current-time and timezone conversion tools. Use it when users ask about time or timezone conversion.",
            "detail_prompts": {
                "usage": "Ask for the timezone when it is missing. Prefer IANA timezone names. Do not guess user-local time."
            },
        },
    }


def npm_stdio_required_kwargs() -> dict[str, Any]:
    payload = npm_stdio_required_payload()
    return {
        "package_registry_type": payload["packageRegistryType"],
        "package_version": payload["packageVersion"],
        "runtime_hint": payload["runtimeHint"],
        "npm_package_confirmed": payload["npmPackageConfirmed"],
        "environment_variables_reviewed": payload["environmentVariablesReviewed"],
        "package_arguments_reviewed": payload["packageArgumentsReviewed"],
        "environment_variables": payload["environmentVariables"],
        "package_arguments": payload["packageArguments"],
        "required_secret_names": payload["requiredSecretNames"],
        "tool_schemas": payload["toolSchemas"],
        "prompt_library": payload["promptLibrary"],
    }


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

    def test_contextforge_registry_service_offerings_require_server_metadata_not_local_manifests(self) -> None:
        servers = [
            {
                "id": "vs-context7",
                "name": "context7_local_server",
                "description": "Virtual server exposing context7-local.",
                "enabled": True,
                "tags": [{"label": "contextforge"}, {"label": "context7"}, {"label": "local-backend"}],
                "associatedTools": ["context7-local-resolve-library-id", "context7-local-query-docs"],
                "associatedResources": ["resource-context7-offering"],
            }
        ]
        gateways = [
            {
                "id": "gw-context7",
                "name": "context7-local",
                "description": "Canonical ContextForge gateway for context7.",
                "enabled": True,
                "tags": [{"label": "contextforge"}, {"label": "context7"}, {"label": "local-backend"}],
            }
        ]
        resources = [
            {
                "id": "resource-context7-offering",
                "uri": "contextforge://control-plane/service-offerings/context7/v1",
                "tags": ["contextforge-service-offering", "service-offering", "context7"],
                "content": json.dumps(service_offering_metadata()),
            }
        ]

        offerings = common.discover_contextforge_registry_service_offerings(
            project_root="/home/dgk/workspace/cf-controlplane",
            contextforge_servers=servers,
            contextforge_gateways=gateways,
            contextforge_resources=resources,
        )

        self.assertEqual(1, len(offerings))
        offering = offerings[0]
        self.assertEqual("contextforge_registry", offering["catalog_source"])
        self.assertEqual("context7:canonical", offering["service_binding"])
        self.assertEqual("context7", offering["service_family"])
        self.assertEqual("context7", offering["codex_alias"])
        self.assertEqual("context7_local_server", offering["virtual_server"])
        self.assertEqual("vs-context7", offering["contextforge_server_id"])
        self.assertEqual("resource-context7-offering", offering["helper_metadata_resource_id"])
        self.assertNotIn("backend_instance", offering)

    def test_contextforge_registry_service_offerings_omit_servers_without_service_metadata(self) -> None:
        servers = [
            {
                "id": "vs-context7",
                "name": "context7_local_server",
                "description": "Virtual server exposing context7-local.",
                "enabled": True,
                "tags": [{"label": "contextforge"}, {"label": "context7"}, {"label": "local-backend"}],
                "associatedTools": ["context7-local-resolve-library-id", "context7-local-query-docs"],
            }
        ]
        gateways = [
            {
                "id": "gw-context7",
                "name": "context7-local",
                "description": "Canonical ContextForge gateway for context7.",
                "enabled": True,
                "tags": [{"label": "contextforge"}, {"label": "context7"}, {"label": "local-backend"}],
            }
        ]

        offerings = common.discover_contextforge_registry_service_offerings(
            project_root="/home/dgk/workspace/cf-controlplane",
            contextforge_servers=servers,
            contextforge_gateways=gateways,
            contextforge_resources=[],
        )

        self.assertEqual([], offerings)

    def test_contextforge_registry_service_offerings_omit_invalid_metadata_content(self) -> None:
        servers = [
            {"id": "vs-bad-json", "name": "bad_json_server", "enabled": True, "associatedResources": ["resource-bad-json"]},
            {"id": "vs-wrong-schema", "name": "wrong_schema_server", "enabled": True, "associatedResources": ["resource-wrong-schema"]},
            {"id": "vs-missing-field", "name": "missing_field_server", "enabled": True, "associatedResources": ["resource-missing-field"]},
            {"id": "vs-inactive", "name": "inactive_server", "enabled": True, "associatedResources": ["resource-inactive"]},
            {"id": "vs-bad-binding", "name": "bad_binding_server", "enabled": True, "associatedResources": ["resource-bad-binding"]},
        ]
        wrong_schema = service_offering_metadata("wrong-schema", server_id="vs-wrong-schema")
        wrong_schema["schema_uri"] = "contextforge://schemas/service-offering/v0"
        missing_field = service_offering_metadata("missing-field", server_id="vs-missing-field")
        del missing_field["display_name"]
        inactive = service_offering_metadata("inactive", server_id="vs-inactive")
        inactive["lifecycle"] = "retired"
        bad_binding = service_offering_metadata("bad-binding", server_id="vs-bad-binding")
        bad_binding["binding"] = {"mode": "made_up"}
        resources = [
            {"id": "resource-bad-json", "tags": ["contextforge-service-offering"], "content": "{not json"},
            {"id": "resource-wrong-schema", "tags": ["contextforge-service-offering"], "content": json.dumps(wrong_schema)},
            {"id": "resource-missing-field", "tags": ["contextforge-service-offering"], "content": json.dumps(missing_field)},
            {"id": "resource-inactive", "tags": ["contextforge-service-offering"], "content": json.dumps(inactive)},
            {"id": "resource-bad-binding", "tags": ["contextforge-service-offering"], "content": json.dumps(bad_binding)},
        ]

        offerings = common.discover_contextforge_registry_service_offerings(
            project_root="/home/dgk/workspace/cf-controlplane",
            contextforge_servers=servers,
            contextforge_gateways=[],
            contextforge_resources=resources,
        )

        self.assertEqual([], offerings)

    def test_contextforge_registry_service_offerings_omit_runtime_server_mismatch(self) -> None:
        metadata = service_offering_metadata("context7", server_id="other-server")
        offerings = common.discover_contextforge_registry_service_offerings(
            project_root="/home/dgk/workspace/cf-controlplane",
            contextforge_servers=[{"id": "vs-context7", "name": "context7_server", "enabled": True, "associatedResources": ["resource-context7"]}],
            contextforge_gateways=[],
            contextforge_resources=[{"id": "resource-context7", "tags": ["contextforge-service-offering"], "content": json.dumps(metadata)}],
        )

        self.assertEqual([], offerings)

    def test_contextforge_registry_service_offerings_omit_duplicate_offering_or_binding_conflicts(self) -> None:
        duplicate_a = service_offering_metadata("context7", server_id="vs-a", binding="context7:a")
        duplicate_b = service_offering_metadata("context7", server_id="vs-b", binding="context7:b")
        binding_a = service_offering_metadata("alpha", server_id="vs-c", binding="shared:binding")
        binding_b = service_offering_metadata("beta", server_id="vs-d", binding="shared:binding")
        servers = [
            {"id": "vs-a", "name": "a_server", "enabled": True, "associatedResources": ["resource-a"]},
            {"id": "vs-b", "name": "b_server", "enabled": True, "associatedResources": ["resource-b"]},
            {"id": "vs-c", "name": "c_server", "enabled": True, "associatedResources": ["resource-c"]},
            {"id": "vs-d", "name": "d_server", "enabled": True, "associatedResources": ["resource-d"]},
        ]
        resources = [
            {"id": "resource-a", "tags": ["contextforge-service-offering"], "content": json.dumps(duplicate_a)},
            {"id": "resource-b", "tags": ["contextforge-service-offering"], "content": json.dumps(duplicate_b)},
            {"id": "resource-c", "tags": ["contextforge-service-offering"], "content": json.dumps(binding_a)},
            {"id": "resource-d", "tags": ["contextforge-service-offering"], "content": json.dumps(binding_b)},
        ]

        offerings = common.discover_contextforge_registry_service_offerings(
            project_root="/home/dgk/workspace/cf-controlplane",
            contextforge_servers=servers,
            contextforge_gateways=[],
            contextforge_resources=resources,
        )

        self.assertEqual([], offerings)

    def test_contextforge_registry_service_offerings_expand_project_hash_template_binding(self) -> None:
        metadata = service_offering_metadata("serena", server_id="vs-serena", binding="unused")
        metadata["scope_model"] = "per_project"
        metadata["instantiation_class"] = "instance_per_project"
        metadata["binding"] = {"mode": "project_hash_template", "template": "serena:{project_hash_12}"}
        metadata["runtime"]["gateway_id"] = ""

        offerings = common.discover_contextforge_registry_service_offerings(
            project_root="/home/dgk/workspace/cf-controlplane",
            contextforge_servers=[{"id": "vs-serena", "name": "serena_server", "enabled": True, "associatedResources": ["resource-serena"]}],
            contextforge_gateways=[],
            contextforge_resources=[{"id": "resource-serena", "tags": ["contextforge-service-offering"], "content": json.dumps(metadata)}],
        )

        self.assertEqual(1, len(offerings))
        self.assertEqual("serena:d46fe58a2a20", offerings[0]["service_binding"])

    def test_service_offering_metadata_exposes_nested_helper_runtime_and_guidance_fields(self) -> None:
        metadata = service_offering_metadata("web-search", server_id="vs-web", binding="web-search:credential_scoped")
        metadata["scope_model"] = "per_user"
        metadata["instantiation_class"] = "credential_scoped"
        metadata["scope_type"] = "provider_credential_and_request_scope"
        metadata["instance_model"] = "credential_scoped"
        metadata["runtime"]["gateway_id"] = ""
        metadata["runtime"]["reload_required"] = False
        metadata["helper"]["required_context"] = {"credential_scope": "required"}
        metadata["helper"]["client_support"] = {"pi": True, "opencode": True}
        metadata["helper"]["actions_supported"] = ["list", "enable", "details"]
        metadata["guidance"] = {"abstract_resource_uri": "contextforge://guidance/web-search/abstract"}

        offerings = common.discover_contextforge_registry_service_offerings(
            project_root="/home/dgk/workspace/cf-controlplane",
            contextforge_servers=[{"id": "vs-web", "name": "web_search_server", "enabled": True, "associatedResources": ["resource-web"]}],
            contextforge_gateways=[],
            contextforge_resources=[{"id": "resource-web", "tags": ["contextforge-service-offering"], "content": json.dumps(metadata)}],
        )

        self.assertEqual(1, len(offerings))
        offering = offerings[0]
        self.assertEqual("per_user", offering["scope_model"])
        self.assertEqual("provider_credential_and_request_scope", offering["scope_type"])
        self.assertEqual("credential_scoped", offering["instance_model"])
        self.assertEqual({"credential_scope": "required"}, offering["required_context"])
        self.assertEqual({"pi": True, "opencode": True}, offering["client_support"])
        self.assertEqual(["list", "enable", "details"], offering["actions_supported"])
        self.assertFalse(offering["reload_required"])
        self.assertEqual(metadata["guidance"], offering["guidance"])

    def test_service_offering_registrar_covers_current_service_families_and_scope_classes(self) -> None:
        self.assertTrue(
            {"chrome-devtools", "time", "serena", "mentality", "web-search"}
            <= service_offering_registration.CANONICAL_SEED_SERVICES
        )
        self.assertEqual("per_project", service_offering_registration._scope_model({}, "instance_per_project"))
        self.assertEqual("per_user", service_offering_registration._scope_model({}, "credential_scoped"))
        self.assertEqual("global", service_offering_registration._scope_model({}, "session_scoped"))
        self.assertEqual(
            {"project_root": "request_context_required"},
            service_offering_registration._required_context(
                {"scope": {"scope_type": "caller_supplied_local_repo"}},
                "global",
                "static_repo_local",
            ),
        )

    def test_service_offering_dry_run_reads_live_state_without_mutation(self) -> None:
        metadata = service_offering_metadata("context7", server_id="stale-server")
        metadata["runtime"]["server_name"] = "context7_server"
        offering = service_offering_registration.PlannedOffering(
            offering_id="context7",
            service_family="context7",
            instance_dir="context7",
            instance_path="server-instances/context7/instance.json",
            server_id="stale-server",
            resource_uri=metadata["resource_uri"],
            resource_body={"uri": metadata["resource_uri"], "content": json.dumps(metadata)},
            metadata=metadata,
        )
        resource = {
            "id": "22222222222222222222222222222222",
            "uri": metadata["resource_uri"],
            "content": json.dumps(metadata),
        }
        server = {
            "id": "live-server",
            "name": "context7_server",
            "associatedResourceIds": [resource["id"]],
        }

        def fake_items(path: str) -> list[dict[str, Any]]:
            if path.startswith("/resources"):
                return [resource]
            if path.startswith("/servers"):
                return [server]
            if path.startswith("/gateways"):
                return []
            raise AssertionError(path)

        with mock.patch.object(service_offering_registration, "_planned_offerings", return_value=([offering], [])), mock.patch.object(
            service_offering_registration, "_api_items", side_effect=fake_items
        ), mock.patch.object(
            service_offering_registration,
            "_hydrate_service_offering_resources",
            side_effect=lambda resources: resources,
        ), mock.patch.object(
            service_offering_registration,
            "_target_owner_email",
            return_value=service_offering_registration.OWNER,
        ), mock.patch.object(service_offering_registration, "_upsert_resource") as upsert, mock.patch.object(
            service_offering_registration, "_associate_resource"
        ) as associate:
            report = service_offering_registration.migrate(dry_run=True, services=["context7"])

        upsert.assert_not_called()
        associate.assert_not_called()
        self.assertEqual(["context7"], report.updated)
        self.assertEqual([], report.created)
        self.assertEqual([], report.associated)
        self.assertEqual("live-server", report.planned[0]["runtime_server_id"])
        self.assertEqual("update", report.planned[0]["resource_action"])
        self.assertEqual("preserve", report.planned[0]["association_action"])

    def test_service_offering_apply_blocks_before_mutation_when_any_live_target_is_missing(self) -> None:
        good_metadata = service_offering_metadata("context7", server_id="server-good")
        good_metadata["runtime"]["server_name"] = "context7_server"
        bad_metadata = service_offering_metadata("time", server_id="server-missing")
        bad_metadata["runtime"]["server_name"] = "time_server"

        def offering(metadata: dict[str, Any]) -> service_offering_registration.PlannedOffering:
            name = str(metadata["offering_id"])
            return service_offering_registration.PlannedOffering(
                offering_id=name,
                service_family=name,
                instance_dir=name,
                instance_path=f"server-instances/{name}/instance.json",
                server_id=str(metadata["runtime"]["server_id"]),
                resource_uri=str(metadata["resource_uri"]),
                resource_body=service_offering_registration._resource_body(metadata),
                metadata=metadata,
            )

        def fake_items(path: str) -> list[dict[str, Any]]:
            if path.startswith("/servers"):
                return [{"id": "server-good", "name": "context7_server"}]
            if path.startswith("/resources") or path.startswith("/gateways"):
                return []
            raise AssertionError(path)

        with mock.patch.object(
            service_offering_registration,
            "_planned_offerings",
            return_value=([offering(good_metadata), offering(bad_metadata)], []),
        ), mock.patch.object(service_offering_registration, "_api_items", side_effect=fake_items), mock.patch.object(
            service_offering_registration,
            "_target_owner_email",
            return_value=service_offering_registration.OWNER,
        ), mock.patch.object(
            service_offering_registration, "_upsert_resource"
        ) as upsert, mock.patch.object(service_offering_registration, "_associate_resource") as associate:
            report = service_offering_registration.migrate(
                dry_run=False,
                services=["context7", "time"],
            )

        upsert.assert_not_called()
        associate.assert_not_called()
        self.assertEqual([], report.created)
        self.assertEqual([], report.updated)
        self.assertEqual([], report.associated)
        self.assertEqual("time", report.errors[0]["service"])
        self.assertIn("apply blocked", report.skipped[-1])

    def test_service_offering_resource_upsert_is_idempotent_when_metadata_matches(self) -> None:
        instance = {
            "name": "context7",
            "scope": {"scope_type": "global_documentation_lookup"},
            "contextforge": {
                "virtual_server": {"id": "server-id", "name": "context7_server"},
                "gateway": {"id": "gateway-id", "name": "context7-local"},
            },
        }
        metadata = service_offering_registration._metadata_from_instance(instance, instance_dir="context7")
        offering = service_offering_registration.PlannedOffering(
            offering_id="context7",
            service_family="context7",
            instance_dir="context7",
            instance_path="server-instances/context7/instance.json",
            server_id="server-id",
            resource_uri=metadata["resource_uri"],
            resource_body=service_offering_registration._resource_body(metadata),
            metadata=metadata,
        )
        expected = offering.resource_body
        content_shapes = {
            "content": expected["content"],
            "text": expected["content"],
            "contents": [{"text": expected["content"]}],
        }
        for content_key, content_value in content_shapes.items():
            with self.subTest(content_key=content_key):
                existing = {
                    "id": "resource-id",
                    "uri": expected["uri"],
                    "name": expected["name"],
                    "title": expected["title"],
                    "description": expected["description"],
                    "mime_type": expected["mimeType"],
                    content_key: content_value,
                    "tags": [{"label": tag} for tag in expected["tags"]],
                    "visibility": expected["visibility"],
                    "ownerEmail": expected["owner_email"],
                }

                with mock.patch.object(service_offering_registration, "_request") as request:
                    action, resource_id = service_offering_registration._upsert_resource(offering, [existing])

                request.assert_not_called()
                self.assertEqual("unchanged", action)
                self.assertEqual("resource-id", resource_id)
        self.assertEqual(
            metadata,
            service_offering_registration._metadata_from_instance(instance, instance_dir="context7"),
        )

    def test_service_offering_resource_upsert_updates_any_drifted_managed_field(self) -> None:
        metadata = service_offering_metadata("context7", server_id="server-id")
        offering = service_offering_registration.PlannedOffering(
            offering_id="context7",
            service_family="context7",
            instance_dir="context7",
            instance_path="server-instances/context7/instance.json",
            server_id="server-id",
            resource_uri=metadata["resource_uri"],
            resource_body=service_offering_registration._resource_body(metadata),
            metadata=metadata,
        )
        expected = offering.resource_body
        existing = {
            "id": "resource-id",
            "uri": expected["uri"],
            "name": expected["name"],
            "title": expected["title"],
            "description": "stale description",
            "mimeType": expected["mimeType"],
            "text": expected["content"],
            "tags": [*expected["tags"], "stale-tag"],
            "visibility": expected["visibility"],
            "ownerEmail": expected["owner_email"],
        }

        with mock.patch.object(service_offering_registration, "_request", return_value={}) as request:
            action, resource_id = service_offering_registration._upsert_resource(offering, [existing])

        self.assertEqual("updated", action)
        self.assertEqual("resource-id", resource_id)
        request.assert_called_once_with("PUT", "/resources/resource-id", body=expected)
        self.assertEqual(
            ["description", "tags"],
            service_offering_registration._resource_contract_differences(existing, offering),
        )

    def test_service_offering_resource_upsert_updates_named_managed_resource_on_uri_drift(self) -> None:
        metadata = service_offering_metadata("context7", server_id="server-id")
        offering = service_offering_registration.PlannedOffering(
            offering_id="context7",
            service_family="context7",
            instance_dir="context7",
            instance_path="server-instances/context7/instance.json",
            server_id="server-id",
            resource_uri=metadata["resource_uri"],
            resource_body=service_offering_registration._resource_body(metadata),
            metadata=metadata,
        )
        expected = offering.resource_body
        existing = {
            "id": "managed-resource-id",
            "uri": "contextforge://control-plane/service-offerings/context7/v0",
            "name": expected["name"],
            "title": expected["title"],
            "description": expected["description"],
            "mimeType": expected["mimeType"],
            "text": expected["content"],
            "tags": ["stale-tag"],
            "visibility": expected["visibility"],
            "ownerEmail": expected["owner_email"],
        }

        with mock.patch.object(service_offering_registration, "_request", return_value={}) as request:
            action, resource_id = service_offering_registration._upsert_resource(
                offering,
                [existing],
            )

        self.assertEqual("updated", action)
        self.assertEqual("managed-resource-id", resource_id)
        request.assert_called_once_with(
            "PUT",
            "/resources/managed-resource-id",
            body=expected,
        )

    def test_service_offering_resource_lookup_rejects_conflicting_managed_identities(self) -> None:
        metadata = service_offering_metadata("context7", server_id="server-id")
        offering = service_offering_registration.PlannedOffering(
            offering_id="context7",
            service_family="context7",
            instance_dir="context7",
            instance_path="server-instances/context7/instance.json",
            server_id="server-id",
            resource_uri=metadata["resource_uri"],
            resource_body=service_offering_registration._resource_body(metadata),
            metadata=metadata,
        )
        resources = [
            {"id": "exact-uri", "uri": offering.resource_uri, "name": "other"},
            {
                "id": "managed-name",
                "uri": "contextforge://control-plane/service-offerings/context7/v0",
                "name": offering.resource_body["name"],
                "tags": offering.resource_body["tags"],
            },
        ]

        with mock.patch.object(service_offering_registration, "_request") as request, self.assertRaisesRegex(
            RuntimeError,
            "multiple Resources match managed offering identity",
        ):
            service_offering_registration._upsert_resource(offering, resources)

        request.assert_not_called()

    def test_service_offering_migration_reports_missing_required_families(self) -> None:
        with mock.patch.object(
            service_offering_registration,
            "_api_items",
            return_value=[],
        ):
            report = service_offering_registration.migrate(
                dry_run=True,
                services=["chrome-devtools"],
            )

        self.assertEqual(1, len(report.errors))
        self.assertEqual("chrome-devtools", report.errors[0]["service"])
        self.assertEqual("required_family_completeness", report.errors[0]["stage"])
        self.assertEqual("required_service_family_missing", report.errors[0]["classification"])
        self.assertFalse(report.target["env_values_recorded"])

    def test_service_offering_migration_reports_api_stage_and_target_without_traceback(self) -> None:
        api_error = service_offering_registration.ContextForgeApiError(
            method="GET",
            path="/resources?include_inactive=true&limit=1000",
            classification="http_error",
            message="Unauthorized",
            http_status=401,
        )
        with mock.patch.object(
            service_offering_registration,
            "_request",
            side_effect=api_error,
        ):
            report = service_offering_registration.migrate(
                dry_run=True,
                services=["context7"],
            )

        self.assertEqual("read_resources", report.errors[0]["stage"])
        self.assertEqual("GET", report.errors[0]["method"])
        self.assertEqual("/resources?include_inactive=true&limit=1000", report.errors[0]["path"])
        self.assertEqual(401, report.errors[0]["http_status"])
        self.assertEqual("error", report.api_diagnostics[0]["outcome"])
        self.assertEqual(report.target["base_url"], report.errors[0]["base_url"])

    def test_service_offering_api_diagnostics_redact_structured_and_plaintext_secrets(self) -> None:
        structured = service_offering_registration._safe_error_text(
            json.dumps(
                {
                    "detail": "authentication failed",
                    "access_token": "structured-secret",
                    "nested": {"password": "nested-secret"},
                }
            )
        )
        plain = service_offering_registration._safe_error_text(
            "Authorization: Bearer plaintext-secret PLATFORM_ADMIN_PASSWORD=env-secret"
        )

        self.assertIn("authentication failed", structured)
        self.assertNotIn("structured-secret", structured)
        self.assertNotIn("nested-secret", structured)
        self.assertNotIn("plaintext-secret", plain)
        self.assertNotIn("env-secret", plain)
        self.assertIn("[REDACTED]", structured)
        self.assertIn("[REDACTED]", plain)

    def test_service_offering_http_diagnostics_never_reflect_response_body_bearer_material(self) -> None:
        reflected_bearer = "qa-response-body-bearer-material"
        http_error = urllib.error.HTTPError(
            url="http://127.0.0.1:4445/resources",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=io.BytesIO(
                json.dumps({"detail": f"invalid token {reflected_bearer}"}).encode()
            ),
        )

        with mock.patch.object(
            service_offering_registration,
            "_token",
            return_value="request-token-not-logged",
        ), mock.patch.object(
            service_offering_registration.urllib.request,
            "urlopen",
            side_effect=http_error,
        ), self.assertRaises(service_offering_registration.ContextForgeApiError) as raised:
            service_offering_registration._request(
                "GET",
                "/resources?include_inactive=true&limit=1000",
            )

        diagnostic = str(raised.exception)
        self.assertNotIn(reflected_bearer, diagnostic)
        self.assertNotIn("request-token-not-logged", diagnostic)
        self.assertIn("Unauthorized", diagnostic)
        self.assertEqual(401, raised.exception.diagnostic["http_status"])

    def test_service_offering_registrar_preserves_server_associations_with_uuid_ids(self) -> None:
        requests: list[tuple[str, str, dict[str, Any] | None]] = []
        server = {
            "id": "server-id",
            "name": "context7_server",
            "associatedToolIds": ["11111111111111111111111111111111"],
            "associatedTools": ["context7-local-query-docs"],
            "associatedResources": ["22222222222222222222222222222222"],
            "associatedPrompts": ["33333333333333333333333333333333"],
            "associatedA2aAgents": ["44444444444444444444444444444444"],
            "ownerEmail": "owner@example.test",
            "visibility": "public",
        }
        metadata = service_offering_metadata("context7", server_id="server-id")
        offering = service_offering_registration.PlannedOffering(
            offering_id="context7",
            service_family="context7",
            instance_dir="context7",
            instance_path="server-instances/context7/instance.json",
            server_id="server-id",
            resource_uri=metadata["resource_uri"],
            resource_body={"uri": metadata["resource_uri"], "content": json.dumps(metadata)},
            metadata=metadata,
        )

        def fake_request(method: str, path: str, *, body: dict[str, Any] | None = None) -> dict[str, Any]:
            requests.append((method, path, body))
            return {}

        with mock.patch.object(service_offering_registration, "_request", side_effect=fake_request):
            service_offering_registration._associate_resource(offering, "55555555555555555555555555555555", [server])

        self.assertEqual([("PUT", "/servers/server-id")], [(method, path) for method, path, _body in requests])
        body = requests[0][2] or {}
        self.assertEqual(["11111111111111111111111111111111"], body["associatedTools"])
        self.assertNotIn("context7-local-query-docs", body["associatedTools"])
        self.assertEqual(
            ["22222222222222222222222222222222", "55555555555555555555555555555555"],
            body["associatedResources"],
        )
        self.assertEqual(["33333333333333333333333333333333"], body["associatedPrompts"])
        self.assertEqual(["44444444444444444444444444444444"], body["associatedA2aAgents"])

    def test_capability_menu_omits_missing_manifest_services_when_live_readback_supplied(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as project_tmp, tempfile.TemporaryDirectory(dir=REPO_ROOT) as instances_tmp:
            root = Path(project_tmp).resolve()
            instances = Path(instances_tmp)
            for service in ("context7", "time"):
                instance = instances / service
                instance.mkdir()
                (instance / "instance.json").write_text(
                    json.dumps(
                        {
                            "enabled": True,
                            "name": service,
                            "slug": service,
                            "service": service,
                            "contextforge": {
                                "gateway": {"name": f"{service}-gateway"},
                                "virtual_server": {"name": f"{common.normalize_codex_alias(service)}_server"},
                            },
                            "backend": {"transport": "stdio"},
                            "scope": {"scope_type": "shared_canonical"},
                        }
                    ),
                    encoding="utf-8",
                )

            capabilities = helper.list_available_capabilities(
                project_root=root,
                contextforge_servers=[{"name": "context7_server", "id": "vs-context7"}],
                server_instances_root=instances,
            )

        service_ids = {service["service_binding"] for service in capabilities["available_services"]}
        choice_ids = {choice["id"] for choice in capabilities["next_turn"]["choices"]}
        self.assertIn("context7:canonical", service_ids)
        self.assertIn("context7:canonical", choice_ids)
        self.assertNotIn("time:canonical", service_ids)
        self.assertNotIn("time:canonical", choice_ids)

    def test_capability_menu_keeps_project_scoped_serena_provisioning_with_live_readback(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as project_tmp, tempfile.TemporaryDirectory(dir=REPO_ROOT) as instances_tmp:
            root = Path(project_tmp).resolve()
            identity = common.project_identity(root)
            capabilities = helper.list_available_capabilities(
                project_root=root,
                contextforge_servers=[],
                server_instances_root=instances_tmp,
            )

        service_ids = {service["service_binding"] for service in capabilities["available_services"]}
        self.assertIn(f"serena:{identity.hash}", service_ids)

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
                "CONTEXTFORGE_CODEX_WRAPPER_CONFIG_ENV": "/run/contextforge-client-scoped/contextforge.env",
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
        self.assertIn('CONTEXTFORGE_CONFIG_ENV = "/run/contextforge-client-scoped/contextforge.env"', text)
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
                "CONTEXTFORGE_OPENCODE_WRAPPER_CONFIG_ENV": "/run/contextforge-client-scoped/contextforge.env",
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
        self.assertEqual("/run/contextforge-client-scoped/contextforge.env", entry["environment"]["CONTEXTFORGE_CONFIG_ENV"])
        self.assertEqual("http://host.docker.internal:4445", entry["environment"]["CONTEXTFORGE_BASE_URL"])
        self.assertEqual("/tmp/contextforge-wrapper-token.local.json", entry["environment"]["CONTEXTFORGE_TOKEN_CACHE"])
        self.assertEqual(
            "/tmp/contextforge-wrapper-token.local.json.lock",
            entry["environment"]["CONTEXTFORGE_TOKEN_LOCK"],
        )

    def test_opencode_config_plan_falls_back_to_client_scoped_wrapper_env(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "CONTEXTFORGE_BASE_URL": "http://127.0.0.1:4445",
                "CONTEXTFORGE_ENV": "/some/client-scoped/contextforge-4445.env",
                "CONTEXTFORGE_CLIENT_SCOPED_ENV": "/some/client-scoped/contextforge-4445.env",
                "CONTEXTFORGE_TOKEN_CACHE": "/some/client-scoped/contextforge-wrapper-token-4445.local.json",
            },
            clear=True,
        ):
            plan = binding.plan_project_init_opencode_config_write(
                "/home/dgk/workspace/legacy-controlplane-archive",
                [service_descriptor("context7")],
                existing_text='{"$schema":"https://opencode.ai/config.json"}\n',
                plugin_existing_text="",
            )

        entry = json.loads(plan["next_text"])["mcp"]["context7"]
        environment = entry["environment"]
        self.assertEqual("http://127.0.0.1:4445", environment["CONTEXTFORGE_BASE_URL"])
        self.assertEqual("/some/client-scoped/contextforge-4445.env", environment["CONTEXTFORGE_CONFIG_ENV"])
        self.assertEqual(
            "/some/client-scoped/contextforge-wrapper-token-4445.local.json",
            environment["CONTEXTFORGE_TOKEN_CACHE"],
        )
        self.assertEqual(
            "/some/client-scoped/contextforge-wrapper-token-4445.local.json.lock",
            environment["CONTEXTFORGE_TOKEN_LOCK"],
        )

    def test_opencode_wrapper_specific_env_overrides_generic_contextforge_env(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "CONTEXTFORGE_OPENCODE_WRAPPER_CONFIG_ENV": "/override/contextforge.env",
                "CONTEXTFORGE_CLIENT_SCOPED_ENV": "/client-scoped/contextforge.env",
                "CONTEXTFORGE_ENV": "/generic/contextforge.env",
                "CONTEXTFORGE_CONFIG_ENV": "/wrong/default/contextforge.env",
                "CONTEXTFORGE_OPENCODE_WRAPPER_BASE_URL": "http://127.0.0.1:4445",
                "CONTEXTFORGE_BASE_URL": "http://127.0.0.1:4444",
                "CONTEXTFORGE_OPENCODE_WRAPPER_TOKEN_CACHE": "/override/token-cache.local.json",
                "CONTEXTFORGE_TOKEN_CACHE": "/generic/token-cache.local.json",
            },
            clear=True,
        ):
            entry = binding.build_project_init_opencode_binding_entry(service_descriptor("context7"))

        environment = entry["environment"]
        self.assertEqual("/override/contextforge.env", environment["CONTEXTFORGE_CONFIG_ENV"])
        self.assertEqual("http://127.0.0.1:4445", environment["CONTEXTFORGE_BASE_URL"])
        self.assertEqual("/override/token-cache.local.json", environment["CONTEXTFORGE_TOKEN_CACHE"])
        self.assertEqual("/override/token-cache.local.json.lock", environment["CONTEXTFORGE_TOKEN_LOCK"])

    def test_opencode_project_init_apply_writes_matching_wrapper_env(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp, mock.patch.dict(
            os.environ,
            {
                "CONTEXTFORGE_BASE_URL": "http://127.0.0.1:4445",
                "CONTEXTFORGE_ENV": "/some/client-scoped/contextforge-4445.env",
                "CONTEXTFORGE_CLIENT_SCOPED_ENV": "/some/client-scoped/contextforge-4445.env",
                "CONTEXTFORGE_TOKEN_CACHE": "/some/client-scoped/contextforge-wrapper-token-4445.local.json",
            },
            clear=True,
        ):
            root = Path(tmp).resolve()
            contextforge_helper_mcp._clear_durable_cache(str(root))
            contextforge_helper_mcp._CACHED_PLANS.clear()
            contextforge_helper_mcp._CACHED_RECEIPTS.clear()
            proposal = contextforge_helper_mcp.cf_project_init_propose(
                str(root),
                [service_descriptor("context7")],
                client_type="opencode",
            )
            self.assertTrue(proposal["ok"], proposal)
            challenge = proposal["approval_challenge"]
            approved = contextforge_helper_mcp.cf_project_init_approve(
                str(root),
                challenge["challenge_id"],
                challenge["plan_digest"],
            )
            self.assertTrue(approved["ok"], approved)
            applied = contextforge_helper_mcp.cf_project_init_apply(str(root))
            self.assertTrue(applied["ok"], applied)
            opencode_config = json.loads((root / "opencode.json").read_text(encoding="utf-8"))

        environment = opencode_config["mcp"]["context7"]["environment"]
        self.assertEqual("http://127.0.0.1:4445", environment["CONTEXTFORGE_BASE_URL"])
        self.assertEqual("/some/client-scoped/contextforge-4445.env", environment["CONTEXTFORGE_CONFIG_ENV"])
        self.assertEqual(
            "/some/client-scoped/contextforge-wrapper-token-4445.local.json",
            environment["CONTEXTFORGE_TOKEN_CACHE"],
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

    def test_client_reload_report_rejects_validation_intent(self) -> None:
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

        self.assertEqual("reload_required", pending_job["x_client_reload_fsm"]["state"])
        self.assertEqual("reload_required", pending_client_state["reload_status"])
        self.assertEqual(written, after)

    def test_client_reload_report_rejects_presume_working_intent(self) -> None:
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
            repeat = helper.reset_current_project(project_root=root, client_type="codex")

            self.assertEqual("reset", result["status"])
            self.assertTrue(result["postcondition"])
            self.assertFalse(project_state.project_state_path(root).exists())
            self.assertTrue(Path(str(result["evidence_dir"])).exists())
            evidence_manifest = json.loads((Path(str(result["evidence_dir"])) / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual("reset", evidence_manifest["status"])
            self.assertTrue(evidence_manifest["postcondition"])
            self.assertIn("assistant_visible_response", evidence_manifest)
            codex_text = (root / ".codex" / "config.toml").read_text(encoding="utf-8")
            self.assertIn("[mcp_servers.keep]", codex_text)
            self.assertNotIn(binding.PROJECT_INIT_OWNER_MARKER, codex_text)
            opencode_config = json.loads((root / "opencode.json").read_text(encoding="utf-8"))
            self.assertEqual(["keep"], sorted(opencode_config["mcp"]))
            gemini_config = json.loads((root / ".gemini" / "settings.json").read_text(encoding="utf-8"))
            self.assertEqual(["keep"], sorted(gemini_config["mcpServers"]))
            self.assertEqual("reset", repeat["status"])
            self.assertEqual([], repeat["actions"])
            self.assertNotEqual(result["reset_id"], repeat["reset_id"])
            self.assertNotEqual(result["evidence_dir"], repeat["evidence_dir"])
            self.assertTrue(Path(str(repeat["evidence_dir"])).exists())

    def test_reset_current_project_removes_orphaned_helper_entries_without_state(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            selected = [service_descriptor("context7")]

            (root / ".codex").mkdir()
            codex_plan = binding.plan_project_init_target_client_activation(root, selected, target_client="codex")
            (root / ".codex" / "config.toml").write_text(str(codex_plan["next_text"]), encoding="utf-8")

            opencode_entry = binding.build_project_init_opencode_binding_entry(selected[0])
            (root / "opencode.json").write_text(
                json.dumps(
                    {
                        "mcp": {
                            "keep": {"type": "local", "command": ["keep"], "enabled": True},
                            "stale-contextforge": opencode_entry,
                        }
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            gemini_entry = binding.build_project_init_gemini_binding_entry(selected[0])
            (root / ".gemini").mkdir()
            (root / ".gemini" / "settings.json").write_text(
                json.dumps(
                    {
                        "mcpServers": {
                            "keep": {"command": "keep", "args": []},
                            "stale-contextforge": gemini_entry,
                        }
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            result = helper.reset_current_project(project_root=root, client_type="opencode")

            self.assertEqual("reset", result["status"])
            self.assertTrue(result["postcondition"])
            self.assertIn("Project reset complete", result["assistant_visible_response"])
            self.assertFalse((root / ".codex" / "config.toml").exists())
            opencode_config = json.loads((root / "opencode.json").read_text(encoding="utf-8"))
            self.assertEqual(["keep"], sorted(opencode_config["mcp"]))
            gemini_config = json.loads((root / ".gemini" / "settings.json").read_text(encoding="utf-8"))
            self.assertEqual(["keep"], sorted(gemini_config["mcpServers"]))
            operations = {action["operation"] for action in result["actions"]}
            self.assertIn("remove_orphaned_owned_codex_mcp_block", operations)
            self.assertIn("remove_orphaned_contextforge_json_mcp_entry", operations)

    def test_reset_current_project_preserves_unowned_wrapper_shaped_json_entries_without_state(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            wrapper_path = str(REPO_ROOT / "scripts" / "contextforge_mcp_wrapper.py")
            (root / "opencode.json").write_text(
                json.dumps(
                    {
                        "mcp": {
                            "manual-wrapper": {
                                "type": "local",
                                "command": [sys.executable, wrapper_path, "manual_server"],
                                "enabled": True,
                                "environment": {"MCP_WRAPPER_LOG_LEVEL": "INFO"},
                            }
                        }
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (root / ".gemini").mkdir()
            (root / ".gemini" / "settings.json").write_text(
                json.dumps(
                    {
                        "mcpServers": {
                            "manual-wrapper": {
                                "command": sys.executable,
                                "args": [wrapper_path, "manual_server"],
                                "env": {"MCP_WRAPPER_LOG_LEVEL": "INFO"},
                            }
                        }
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            result = helper.reset_current_project(project_root=root, client_type="opencode", preserve_evidence=False)

            self.assertEqual("reset", result["status"])
            self.assertTrue(result["postcondition"])
            opencode_config = json.loads((root / "opencode.json").read_text(encoding="utf-8"))
            self.assertEqual(["manual-wrapper"], sorted(opencode_config["mcp"]))
            gemini_config = json.loads((root / ".gemini" / "settings.json").read_text(encoding="utf-8"))
            self.assertEqual(["manual-wrapper"], sorted(gemini_config["mcpServers"]))
            refusal_reasons = {refusal["reason"] for refusal in result["refusals"]}
            self.assertEqual({"unmanaged_wrapper_json_mcp_entry_preserved"}, refusal_reasons)

    def test_project_reset_is_available_through_mcp_and_pi_cli(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            state = project_state.default_state(root)
            project_state.write_state_atomic(root, state)

            cwd = Path.cwd()
            try:
                os.chdir(root)
                mcp_result = contextforge_helper_mcp.cf_project_reset_current_project(
                    client_type="codex",
                    preserve_evidence=False,
                )
                project_state.write_state_atomic(root, state)
                cli_result = pi_project_init_helper_cli.dispatch(
                    "cf_project_reset_current_project",
                    {"client_type": "pi", "preserve_evidence": False},
                )
            finally:
                os.chdir(cwd)

            self.assertTrue(mcp_result["ok"])
            self.assertEqual("reset", mcp_result["status"])
            self.assertEqual(str(root), mcp_result["project_root"])
            self.assertIn("assistant_visible_response", mcp_result)
            self.assertTrue(cli_result["ok"])
            self.assertEqual("reset", cli_result["status"])
            self.assertEqual(str(root), cli_result["project_root"])
            self.assertIn("assistant_visible_response", cli_result)

    def test_project_reset_defaults_to_latest_user_message_cwd_before_process_cwd(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp, tempfile.TemporaryDirectory() as run_tmp:
            root = Path(tmp).resolve()
            state = project_state.default_state(root)
            project_state.write_state_atomic(root, state)
            approval_source = Path(run_tmp) / "latest-user-message.json"
            approval_source.write_text(json.dumps({"cwd": str(root), "text": "reset this project"}) + "\n", encoding="utf-8")

            with mock.patch.dict(os.environ, {"CONTEXTFORGE_HELPER_APPROVAL_SOURCE_PATH": str(approval_source)}):
                mcp_result = contextforge_helper_mcp.cf_project_reset_current_project(
                    client_type="codex",
                    preserve_evidence=False,
                )

        self.assertTrue(mcp_result["ok"], mcp_result)
        self.assertEqual("reset", mcp_result["status"])
        self.assertEqual(str(root), mcp_result["project_root"])

    def test_project_reset_refuses_unsafe_roots_on_reset_surface(self) -> None:
        denied_result = contextforge_helper_mcp.cf_project_reset_current_project(
            project_root=str(Path.home()),
            client_type="codex",
            preserve_evidence=False,
        )
        self.assertFalse(denied_result["ok"])
        self.assertEqual("RootValidationError", denied_result["error"]["type"])

        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            tmp_path = Path(tmp).resolve()
            link = tmp_path / "escape-link"
            link.symlink_to("/tmp")
            symlink_result = contextforge_helper_mcp.cf_project_reset_current_project(
                project_root=str(link),
                client_type="codex",
                preserve_evidence=False,
            )

        self.assertFalse(symlink_result["ok"])
        self.assertEqual("RootValidationError", symlink_result["error"]["type"])

    def test_pi_reload_report_does_not_change_normal_readback_contract(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp, mock.patch.object(
            contextforge_helper_mcp,
            "_contextforge_registry_service_offerings",
            return_value=[],
        ):
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
            report = record_pi_reload(root)
            reported_readback = contextforge_helper_mcp.project_state_readback(str(root), client_type="pi")
            reported_availability = contextforge_helper_mcp.project_tool_availability(str(root), client_type="pi")
            reported_summary = contextforge_helper_mcp.project_capability_summary(str(root), client_type="pi")

        self.assertEqual("reload_required", pending_readback["current_session_boundary"]["reload_status"])
        self.assertEqual("client_reload_report_ignored", report["status"])
        self.assertEqual("reload_required", report["reload_state"])
        for result in (reported_readback, reported_availability, reported_summary):
            with self.subTest(status=result["status"]):
                self.assertEqual("reload_required", result["current_session_boundary"]["reload_status"])
                self.assertEqual("reload_required", result["current_session_boundary"]["user_status"])
                self.assertTrue(result["current_session_boundary"]["requires_reload"])
                self.assertFalse(result["current_session_boundary"]["reload_acknowledged"])
                self.assertFalse(result["current_session_boundary"]["tools_registered_observed"])
                self.assertTrue(result["assistant_visible_response_policy"]["internal_status_terms_suppressed"])
        self.assertEqual(
            "projection recorded; client reload required",
            reported_readback["target_client_services"][0]["target_client_user_state"],
        )
        self.assertEqual(
            "shim_activation_planned",
            reported_readback["target_client_services"][0]["target_client_state"]["status"],
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
        self.assertNotIn("helperServiceOnboardingHowTo", text)
        self.assertNotIn('"get_service_onboarding_how_to"', text)
        self.assertNotIn("cf_project_service_onboarding_research_source", text)
        self.assertNotIn("use source_files[] as anchors", text)
        self.assertNotIn("npmPackageConfirmed", text)
        self.assertNotIn("environmentVariables", text)
        self.assertNotIn("MEMORY_FILE_PATH", text)
        self.assertNotIn("Do not put prose explanations in value", text)
        self.assertNotIn("runtimeApplyPackageId", text)
        self.assertNotIn("do not reconstruct the full package payload from memory", text)
        self.assertNotIn("normalized.runtime_apply_package_id = normalized.runtimeApplyPackageId", text)
        self.assertNotIn("runtime_apply_package_ref", text)
        self.assertNotIn("install_artifact_contract: result.install_artifact_contract", text)
        self.assertNotIn("agent_hidden_onboarding_how_to", text)
        self.assertNotIn("serviceOnboardingHowTo,", text)
        self.assertIn("result.ok === false && isObject(result.error)", text)
        self.assertIn('status: `${operation}_failed`', text)
        self.assertIn("If no prior service list is visible in the current transcript", text)
        self.assertIn("silently call cf_project_service_list", text)
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
        self.assertIn("using Pi's actual tool-call mechanism", text)
        self.assertIn("print(default_api...)", text)
        self.assertIn("<ctrl...> blocks", text)
        self.assertIn("Do not end with an empty assistant message after a successful route tool call.", text)
        self.assertIn("Do not end with an empty assistant message after this tool succeeds.", text)
        self.assertIn("plainUserFacingRouteResult", text)
        self.assertIn("isUserFacingReadbackOperation", text)
        self.assertIn('"service_list"', text)
        self.assertIn('"service_disable"', text)
        self.assertIn('"service_remove"', text)
        self.assertIn("const disabledServices = new Set<string>()", text)
        self.assertIn("disabledServices.has(effectiveBinding)", text)
        self.assertIn("staticServiceRouteReadbackTools", text)
        self.assertIn("staticReadbackTool", text)
        self.assertIn("cf_mentality_governance_list", text)
        self.assertIn("governance_list", text)
        self.assertIn("toolDefinition.renderResult = renderNothing", text)
        self.assertIn('"get_project_tool_availability"', text)
        self.assertIn("return message || undefined", text)
        self.assertIn("Which ContextForge services should I enable for this project?", text)
        self.assertIn('name: "cf_project_service_list"', text)
        self.assertIn('operation: "service_list"', text)
        self.assertIn('name: "cf_project_service_enable"', text)
        self.assertIn('operation: "service_enable"', text)
        self.assertIn('items: { type: "string" }', text)
        self.assertIn("minItems: 1", text)
        self.assertIn("next_turn.choices[].id", text)
        self.assertIn('for example \\"context7:canonical\\"', text)
        self.assertIn('client_type: "pi"', text)
        self.assertIn('dry_run: { type: "boolean" }', text)
        self.assertIn('selected_services: {', text)
        self.assertIn('project_root: { type: "string", description: "Alias for projectRoot." }', text)
        self.assertIn("normalizeProjectInitPayload", text)
        self.assertIn("normalized.selected_services = normalized.selectedServices", text)
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
        self.assertIn("abstractServiceSpecs", text)
        self.assertIn("isServiceAbstractSpecUri", text)
        self.assertIn("contextforge://service-specs/", text)
        self.assertIn("Use these compact service specs", text)
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
        self.assertIn('"service_enable"', text)
        self.assertIn('"service_repair"', text)
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

    def test_opencode_service_onboarding_route_is_removed(self) -> None:
        text = (REPO_ROOT / "docker/client-harness/config/opencode/plugins/contextforge-project-init.js").read_text(encoding="utf-8")

        self.assertNotIn("serviceOnboardingRuntimeApplyRoute", text)
        self.assertNotIn("serviceOnboardingContinuationRoute", text)
        self.assertNotIn("<contextforge-service-onboarding>", text)
        self.assertNotIn("serviceOnboardingHowTo", text)
        self.assertNotIn("asksForDirectClientMcpConfig", text)
        self.assertNotIn("install_artifact_contract", text)
        self.assertNotIn("non-mutating runtime/apply package", text)
        self.assertIn("transcriptShowsProjectInitContinuation", text)
        self.assertIn("approve or decline?", text)
        self.assertIn("sameRecordedSession || transcriptShowsProjectInitContinuation(output.messages)", text)

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

    def test_pi_helper_cli_rejects_service_onboarding_operations(self) -> None:
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

        self.assertNotEqual(0, result.returncode, result.stderr)
        parsed = json.loads(result.stdout)
        self.assertFalse(parsed["ok"])
        self.assertIn("unsupported operation", parsed["error"]["message"])

    def test_contextforge_helper_mcp_does_not_register_service_onboarding_tools(self) -> None:
        text = (REPO_ROOT / "scripts/contextforge_helper_mcp.py").read_text(encoding="utf-8")
        retired_tool_names = [
            "cf_project_service_onboarding_plan",
            "build_service_onboarding_plan",
            "cf_project_service_onboarding_research_source",
            "research_service_onboarding_source",
            "cf_project_service_onboarding_continue",
            "build_service_onboarding_continuation",
            "build_service_onboarding_continue",
            "cf_project_service_onboarding_runtime_draft",
            "cf_project_service_onboarding_runtime_apply",
            "cf_project_service_onboarding_runtime_execute",
            "build_service_onboarding_runtime_apply_package",
            "build_service_onboarding_runtime_apply",
            "build_service_onboarding_runtime_execute",
        ]

        for tool_name in retired_tool_names:
            with self.subTest(tool_name=tool_name):
                self.assertNotRegex(text, rf"@server\.tool\(\)\s*\ndef {tool_name}\(")

    def test_service_onboarding_runtime_apply_accepts_json_encoded_npm_structured_fields(self) -> None:
        payload = npm_stdio_required_payload()
        memory_tool_schemas = {
            "create_entities": {
                "description": "Create memory graph entities.",
                "inputSchema": {"type": "object", "properties": {"entities": {"type": "array"}}},
            },
            "read_graph": {
                "description": "Read the memory graph.",
                "inputSchema": {"type": "object", "properties": {}},
            },
        }
        memory_prompt_library = {
            "abstract_prompt": "Memory provides graph-backed entity and relation tools for user-approved persistent notes.",
            "detail_prompts": {"usage": "Use Memory only when the user asks to store, relate, or inspect durable facts."},
        }
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            result = onboarding_surfaces.build_service_onboarding_runtime_apply_package(
                str(root),
                {
                    "candidateService": "memory",
                    "operatorGoal": "Add the Memory MCP service.",
                    "sourcePath": "https://github.com/modelcontextprotocol/servers/tree/main/src/memory",
                    "backendPackage": "@modelcontextprotocol/server-memory",
                    "backendCommand": "npx",
                    "backendArgs": json.dumps(["-y", "@modelcontextprotocol/server-memory"]),
                    "transportType": "stdio",
                    "localizationType": "shared_canonical",
                    "functionalType": "governance_memory",
                    "stateType": "runtime_evidence_state",
                    "credentialBoundary": "no credentials required",
                    "expectedTools": ["create_entities", "read_graph"],
                    "packageRegistryType": payload["packageRegistryType"],
                    "packageVersion": payload["packageVersion"],
                    "runtimeHint": payload["runtimeHint"],
                    "npmPackageConfirmed": True,
                    "environmentVariablesReviewed": True,
                    "packageArgumentsReviewed": True,
                    "environmentVariables": json.dumps(payload["environmentVariables"]),
                    "packageArguments": json.dumps(["-y", "@modelcontextprotocol/server-memory"]),
                    "requiredSecretNames": json.dumps(payload["requiredSecretNames"]),
                    "toolSchemas": json.dumps(memory_tool_schemas),
                    "toolSchemaSummaries": json.dumps(["source-reviewed tool schemas"]),
                    "promptLibrary": json.dumps(memory_prompt_library),
                },
            )

        self.assertEqual("service_onboarding_runtime_apply_package", result["status"])
        self.assertNotIn("required_inputs", result)
        contract = result["install_artifact_contract"]["artifacts"]["npm_stdio_service_record"]["content"]
        self.assertEqual("@modelcontextprotocol/server-memory", contract["package"])
        self.assertEqual("npx", contract["stdio"]["command"])
        self.assertEqual(["-y", "@modelcontextprotocol/server-memory"], contract["stdio"]["args"])
        self.assertIn("create_entities", contract["tool_schemas"])
        self.assertEqual("Memory provides graph-backed entity and relation tools for user-approved persistent notes.", contract["prompt_library"]["abstract_prompt"])

    def test_service_onboarding_runtime_apply_accepts_project_local_structured_payload_path(self) -> None:
        payload = npm_stdio_required_payload()
        payload.update(
            {
                "candidateService": "memory",
                "operatorGoal": "Add the Memory MCP service.",
                "sourcePath": "https://github.com/modelcontextprotocol/servers/tree/main/src/memory",
                "serviceBinding": "memory:canonical",
                "backendPackage": "@modelcontextprotocol/server-memory",
                "backendCommand": "npx",
                "backendArgs": ["-y", "@modelcontextprotocol/server-memory"],
                "transportType": "stdio",
                "localizationType": "shared_canonical",
                "functionalType": "governance_memory",
                "stateType": "runtime_evidence_state",
                "credentialBoundary": "no credentials required",
                "expectedTools": ["create_entities", "read_graph"],
                "toolSchemas": {
                    "create_entities": {
                        "description": "Create memory graph entities.",
                        "inputSchema": {"type": "object", "properties": {"entities": {"type": "array"}}},
                    },
                    "read_graph": {
                        "description": "Read the memory graph.",
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                },
            }
        )
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            payload_path = root / ".contextforge" / "memory-runtime-payload.json"
            payload_path.parent.mkdir(parents=True, exist_ok=True)
            payload_path.write_text(json.dumps(payload), encoding="utf-8")
            result = onboarding_surfaces.build_service_onboarding_runtime_apply_package(
                str(root),
                {"structuredPayloadPath": str(payload_path)},
            )

        self.assertEqual("service_onboarding_runtime_apply_package", result["status"])
        self.assertNotIn("required_inputs", result)
        contract = result["install_artifact_contract"]["artifacts"]["npm_stdio_service_record"]["content"]
        self.assertEqual("@modelcontextprotocol/server-memory", contract["package"])
        self.assertIn("create_entities", contract["tool_schemas"])

    def test_service_onboarding_runtime_draft_composes_bounded_slices_then_builds_package(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            first = contextforge_helper_mcp.cf_project_service_onboarding_runtime_draft(
                projectRoot=str(root),
                candidateService="time",
                operatorGoal="Add the Time MCP service.",
                sourcePath="https://github.com/modelcontextprotocol/servers/tree/main/src/time",
                backendPackage="mcp-server-time",
                packageRegistryType="npm",
                packageVersion="1.0.0",
                npmPackageConfirmed=True,
                clientType="pi",
            )

            self.assertTrue(first["ok"])
            self.assertEqual("service_onboarding_runtime_apply_draft_incomplete", first["status"])
            self.assertFalse(first["mutation_allowed"])
            self.assertFalse(first["ready_to_build_runtime_apply_package"])
            self.assertEqual("transport", first["next_required_slice"]["id"])
            self.assertIn("Next bounded ask", first["assistant_visible_response"])
            self.assertIn("just-in-time", first["assistant_visible_response"])
            draft_id = first["runtime_apply_draft_id"]
            draft_path = Path(first["structured_payload_path"])
            self.assertTrue(draft_path.exists())

            second = contextforge_helper_mcp.cf_project_service_onboarding_runtime_draft(
                projectRoot=str(root),
                runtimeApplyDraftId=draft_id,
                backendCommand="uvx",
                backendArgs=["mcp-server-time", "--local-timezone", "UTC"],
                transportType="stdio",
                localizationType="shared_canonical",
                functionalType="time_timezone",
                stateType="stateless",
                credentialBoundary="no credentials required",
                expectedTools=["get_current_time", "convert_time"],
                runtimeHint="npx",
                environmentVariablesReviewed=True,
                packageArgumentsReviewed=True,
                environmentVariables=[],
                packageArguments=["mcp-server-time", "--local-timezone", "UTC"],
                requiredSecretNames=[],
                toolSchemaRecords=[
                    {
                        "name": "get_current_time",
                        "description": "Get the current time for an IANA timezone.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"timezone": {"type": "string"}},
                            "required": ["timezone"],
                        },
                    },
                    {
                        "name": "convert_time",
                        "description": "Convert a time between IANA timezones.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "source_timezone": {"type": "string"},
                                "target_timezone": {"type": "string"},
                                "time": {"type": "string"},
                            },
                            "required": ["source_timezone", "target_timezone", "time"],
                        },
                    },
                ],
                promptLibrary={
                    "abstract_prompt": "Time provides current-time and timezone conversion tools.",
                    "detail_prompts": {"usage": "Use IANA timezone names and ask when the timezone is ambiguous."},
                },
                clientType="pi",
            )

            self.assertTrue(second["ok"])
            self.assertEqual("service_onboarding_runtime_apply_draft_ready", second["status"])
            self.assertTrue(second["ready_to_build_runtime_apply_package"])
            self.assertEqual("build_package", second["next_required_slice"]["id"])
            self.assertEqual(str(draft_path), second["structured_payload_path"])
            self.assertIn("runtime/apply package preview", second["assistant_visible_response"])

            package = contextforge_helper_mcp.cf_project_service_onboarding_runtime_apply(
                projectRoot=str(root),
                structuredPayloadPath=str(draft_path),
                clientType="pi",
            )

        self.assertTrue(package["ok"])
        self.assertEqual("service_onboarding_runtime_apply_package", package["status"])
        self.assertIn("install_artifact_contract", package)
        self.assertIn("runtime_apply_package_id", package)
        contract = package["install_artifact_contract"]["artifacts"]["npm_stdio_service_record"]["content"]
        self.assertEqual("mcp-server-time", contract["package"])
        self.assertIn("get_current_time", contract["tool_schemas"])

    def test_service_onboarding_runtime_apply_accepts_tool_schema_records(self) -> None:
        payload = npm_stdio_required_payload()
        tool_schema_records = [
            {
                "name": "create_entities",
                "description": "Create memory graph entities.",
                "inputSchema": {"type": "object", "properties": {"entities": {"type": "array"}}, "required": ["entities"]},
                "sourceAnchor": "src/memory/index.ts:create_entities",
            },
            {
                "name": "read_graph",
                "description": "Read the memory graph.",
                "inputSchema": {"type": "object", "properties": {}, "required": []},
                "sourceAnchor": "src/memory/index.ts:read_graph",
            },
        ]
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            result = onboarding_surfaces.build_service_onboarding_runtime_apply_package(
                str(root),
                {
                    "candidateService": "memory",
                    "operatorGoal": "Add the Memory MCP service.",
                    "sourcePath": "https://github.com/modelcontextprotocol/servers/tree/main/src/memory",
                    "backendPackage": "@modelcontextprotocol/server-memory",
                    "backendCommand": "npx",
                    "backendArgs": ["-y", "@modelcontextprotocol/server-memory"],
                    "transportType": "stdio",
                    "localizationType": "shared_canonical",
                    "functionalType": "governance_memory",
                    "stateType": "runtime_evidence_state",
                    "credentialBoundary": "no credentials required",
                    "expectedTools": ["create_entities", "read_graph"],
                    "packageRegistryType": payload["packageRegistryType"],
                    "packageVersion": payload["packageVersion"],
                    "runtimeHint": payload["runtimeHint"],
                    "npmPackageConfirmed": True,
                    "environmentVariablesReviewed": True,
                    "packageArgumentsReviewed": True,
                    "environmentVariables": payload["environmentVariables"],
                    "packageArguments": ["-y", "@modelcontextprotocol/server-memory"],
                    "requiredSecretNames": payload["requiredSecretNames"],
                    "toolSchemaRecords": tool_schema_records,
                    "promptLibrary": {
                        "abstractPrompt": "Memory provides graph-backed entity and relation tools for user-approved persistent notes.",
                        "detailPrompts": {"usage": "Use Memory only when the user asks to store, relate, or inspect durable facts."},
                    },
                },
            )

        self.assertEqual("service_onboarding_runtime_apply_package", result["status"])
        contract = result["install_artifact_contract"]["artifacts"]["npm_stdio_service_record"]["content"]
        self.assertIn("create_entities", contract["tool_schemas"])
        self.assertEqual("src/memory/index.ts:create_entities", contract["tool_schemas"]["create_entities"]["source_anchor"])
        self.assertEqual(["-y", "@modelcontextprotocol/server-memory"], contract["stdio"]["args"])
        self.assertEqual("Memory provides graph-backed entity and relation tools for user-approved persistent notes.", contract["prompt_library"]["abstract_prompt"])

    def test_service_onboarding_source_research_fetches_github_files_with_anchors(self) -> None:
        listing = [
            {
                "type": "file",
                "name": "README.md",
                "path": "src/time/README.md",
                "download_url": "https://raw.example/README.md",
                "html_url": "https://github.example/README.md",
                "sha": "abc",
                "size": 27,
            }
        ]

        with mock.patch.object(onboarding_surfaces, "fetch_json_url", return_value=listing), mock.patch.object(
            onboarding_surfaces,
            "fetch_text_url",
            return_value=("# Time\n\nRun with uvx mcp-server-time\n", False),
        ):
            result = onboarding_surfaces.research_service_onboarding_source(
                "/workspace",
                {"source_path": "https://github.com/modelcontextprotocol/servers/tree/main/src/time"},
            )

        self.assertTrue(result["ok"])
        self.assertFalse(result["mutation_allowed"])
        self.assertEqual("service_onboarding_source_research", result["status"])
        self.assertEqual(1, result["retrieved_file_count"])
        self.assertEqual("modelcontextprotocol/servers:main:src/time/README.md", result["source_files"][0]["anchor"])
        self.assertIn("Run with uvx", result["source_files"][0]["content"])
        self.assertIn("source research only", result["assistant_visible_response"])

    def test_service_onboarding_source_research_adds_npm_metadata_from_package_json(self) -> None:
        listing = [
            {
                "type": "file",
                "name": "package.json",
                "path": "src/memory/package.json",
                "download_url": "https://raw.example/package.json",
                "html_url": "https://github.example/package.json",
                "sha": "abc",
                "size": 64,
            }
        ]
        package_metadata = {
            "description": "Memory MCP server",
            "dist-tags": {"latest": "2026.1.26"},
            "repository": {"type": "git", "url": "git+https://github.com/modelcontextprotocol/servers.git"},
        }

        with mock.patch.object(onboarding_surfaces, "fetch_json_url", side_effect=[listing, package_metadata]), mock.patch.object(
            onboarding_surfaces,
            "fetch_text_url",
            return_value=('{"name":"@modelcontextprotocol/server-memory","version":"0.6.3"}\n', False),
        ):
            result = onboarding_surfaces.research_service_onboarding_source(
                "/workspace",
                {"source_path": "https://github.com/modelcontextprotocol/servers/tree/main/src/memory"},
            )

        self.assertTrue(result["ok"])
        self.assertEqual("@modelcontextprotocol/server-memory", result["npm_package_metadata"]["package"])
        self.assertEqual("2026.1.26", result["npm_package_metadata"]["latest"])
        self.assertIn("NPM package metadata", result["assistant_visible_response"])

    def test_contextforge_helper_mcp_exposes_source_research_payload_to_client(self) -> None:
        listing = [
            {
                "type": "file",
                "name": "server.py",
                "path": "src/time/server.py",
                "download_url": "https://raw.example/server.py",
                "html_url": "https://github.example/server.py",
                "sha": "def",
                "size": 44,
            }
        ]
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            with mock.patch.object(onboarding_surfaces, "fetch_json_url", return_value=listing), mock.patch.object(
                onboarding_surfaces,
                "fetch_text_url",
                return_value=("@mcp.tool()\ndef get_current_time(timezone: str):\n", False),
            ):
                result = contextforge_helper_mcp.cf_project_service_onboarding_research_source(
                    project_root=str(root),
                    source_path="https://github.com/modelcontextprotocol/servers/tree/main/src/time",
                    client_type="opencode",
                )

        self.assertTrue(result["ok"])
        self.assertEqual("service_onboarding_source_research", result["status"])
        self.assertEqual(1, result["retrieved_file_count"])
        self.assertEqual("src/time/server.py", result["source_files"][0]["path"])
        self.assertIn("get_current_time", result["source_files"][0]["content"])
        self.assertTrue(result["copy_as_complete_visible_response"])
        self.assertTrue(result["do_not_summarize"])
        self.assertTrue(result["assistant_response_policy"]["copy_assistant_visible_response_exactly"])
        self.assertTrue(result["assistant_response_policy"]["do_not_write_direct_client_local_mcp_config"])
        self.assertNotIn("record", result)

    def test_pi_helper_cli_service_onboarding_how_to_operation_is_retired(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            result = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts/pi_project_init_helper_cli.py"),
                    "--operation",
                    "get_service_onboarding_how_to",
                    "--payload-json",
                    json.dumps({"project_root": str(root), "client_type": "opencode"}),
                ],
                cwd=REPO_ROOT,
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertNotEqual(0, result.returncode, result.stderr)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["ok"])
        self.assertIn("unsupported operation", payload["error"]["message"])

    def test_pi_helper_cli_service_onboarding_continuation_operation_is_retired(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            result = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts/pi_project_init_helper_cli.py"),
                    "--operation",
                    "build_service_onboarding_continuation",
                    "--payload-json",
                    json.dumps(
                        {
                            "project_root": str(root),
                            "candidateService": "time",
                            "operatorGoal": "Add the Time MCP service.",
                            "sourcePath": "https://github.com/modelcontextprotocol/servers/tree/main/src/time",
                            "backendPackage": "mcp-server-time",
                            "backendCommand": "mcp-server-time",
                            "transportType": "stdio",
                            "localizationType": "shared_canonical",
                            "functionalType": "time_timezone",
                            "stateType": "stateless",
                            "credentialBoundary": "no credentials required",
                            "expectedTools": ["get_current_time", "convert_time"],
                            "issue": "356",
                            **npm_stdio_required_payload(),
                        }
                    ),
                ],
                check=False,
                capture_output=True,
                text=True,
                cwd=REPO_ROOT,
            )

        self.assertNotEqual(0, result.returncode, result.stderr)
        parsed = json.loads(result.stdout)
        self.assertFalse(parsed["ok"])
        self.assertIn("unsupported operation", parsed["error"]["message"])

    def test_contextforge_helper_mcp_exposes_uncataloged_service_onboarding_continuation(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            result = contextforge_helper_mcp.cf_project_service_onboarding_continue(
                project_root=str(root),
                candidate_service="time",
                operator_goal="Add the Time MCP service.",
                source_path="https://github.com/modelcontextprotocol/servers/tree/main/src/time",
                backend_package="mcp-server-time",
                backend_command="mcp-server-time",
                transport_type="stdio",
                localization_type="shared_canonical",
                functional_type="time_timezone",
                state_type="stateless",
                credential_boundary="no credentials required",
                approval_type="source_only",
                expected_tools=["get_current_time", "convert_time"],
                issue="356",
                client_type="opencode",
            )

        self.assertTrue(result["ok"])
        self.assertEqual("service_onboarding_continuation_plan", result["status"])
        self.assertFalse(result["mutation_allowed"])
        self.assertNotIn("agent_hidden_onboarding_how_to", result)
        self.assertNotIn("agent_hidden_onboarding_how_to_source", result)
        self.assertNotIn("handoff", result)
        self.assertNotIn("service_management_result", result)
        self.assertIn("not a project-init service activation menu", result["assistant_visible_response"])
        self.assertIn("separate explicit approval is required before any ContextForge registry or catalog mutation", result["assistant_visible_response"])
        self.assertIn("next safe step", result["assistant_visible_response"])
        self.assertIn("non-mutating runtime package preview", result["assistant_visible_response"])

    def test_contextforge_helper_mcp_continuation_accepts_client_camelcase_npm_fields(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            result = contextforge_helper_mcp.cf_project_service_onboarding_continue(
                projectRoot=str(root),
                candidateService="time",
                operatorGoal="Add the Time MCP service.",
                sourcePath="https://github.com/modelcontextprotocol/servers/tree/main/src/time",
                backendPackage="mcp-server-time",
                command="uvx",
                backendArgs=["mcp-server-time", "--local-timezone", "UTC"],
                transportType="stdio",
                localizationType="shared_canonical",
                functionalType="time_timezone",
                stateType="stateless",
                credentialBoundary="no credentials required",
                approvalType="source_only",
                expectedTools=["get_current_time", "convert_time"],
                issueNumber="356",
                clientType="pi",
                **npm_stdio_required_payload(),
            )

        self.assertTrue(result["ok"])
        self.assertEqual("service_onboarding_continuation_plan", result["status"])
        self.assertFalse(result["mutation_allowed"])
        self.assertIn("not a project-init service activation menu", result["assistant_visible_response"])
        self.assertNotIn("must not have additional properties", json.dumps(result, sort_keys=True))

    def test_pi_helper_cli_service_onboarding_runtime_apply_package_operation_is_retired(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            result = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts/pi_project_init_helper_cli.py"),
                    "--operation",
                    "build_service_onboarding_runtime_apply_package",
                    "--payload-json",
                    json.dumps(
                        {
                            "project_root": str(root),
                            "candidateService": "time",
                            "operatorGoal": "Add the Time MCP service.",
                            "sourcePath": "https://github.com/modelcontextprotocol/servers/tree/main/src/time",
                            "backendPackage": "mcp-server-time",
                            "backendCommand": "uvx",
                            "backendArgs": ["mcp-server-time", "--local-timezone", "UTC"],
                            "transportType": "stdio",
                            "localizationType": "shared_canonical",
                            "functionalType": "time_timezone",
                            "stateType": "stateless",
                            "credentialBoundary": "no credentials required",
                            "expectedTools": ["get_current_time", "convert_time"],
                            "issue": "356",
                            **npm_stdio_required_payload(),
                        }
                    ),
                ],
                check=False,
                capture_output=True,
                text=True,
                cwd=REPO_ROOT,
            )

        self.assertNotEqual(0, result.returncode, result.stderr)
        parsed = json.loads(result.stdout)
        self.assertFalse(parsed["ok"])
        self.assertIn("unsupported operation", parsed["error"]["message"])

    def test_contextforge_helper_mcp_exposes_public_runtime_apply_package_without_internal_artifacts(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            approval_source = root / "latest-user.json"
            approval_source.write_text(
                json.dumps({"cwd": str(root), "text": "approve runtime execute for time through time-gateway"}),
                encoding="utf-8",
            )
            with mock.patch.dict(os.environ, {"CONTEXTFORGE_HELPER_APPROVAL_SOURCE_PATH": str(approval_source)}, clear=False):
                result = contextforge_helper_mcp.cf_project_service_onboarding_runtime_apply(
                    project_root=str(root),
                    candidate_service="time",
                    operator_goal="Add the Time MCP service.",
                    source_path="https://github.com/modelcontextprotocol/servers/tree/main/src/time",
                    backend_package="mcp-server-time",
                    backend_command="uvx",
                    backend_args=["mcp-server-time", "--local-timezone", "UTC"],
                    transport_type="stdio",
                    localization_type="shared_canonical",
                    functional_type="time_timezone",
                    state_type="stateless",
                    credential_boundary="no credentials required",
                    approval_type="runtime_registration",
                    expected_tools=["get_current_time", "convert_time"],
                    issue="356",
                    client_type="opencode",
                    **npm_stdio_required_kwargs(),
                )

        self.assertTrue(result["ok"])
        self.assertEqual("service_onboarding_runtime_apply_package", result["status"])
        self.assertFalse(result["mutation_allowed"])
        self.assertIn("install_artifact_contract", result)
        self.assertEqual(
            "/gateways",
            result["install_artifact_contract"]["artifacts"]["contextforge_api_json"]["content"]["gateway"]["path"],
        )
        self.assertNotIn("agent_hidden_onboarding_how_to", result)
        self.assertNotIn("handoff", result)
        self.assertNotIn("service_provision_plan", result)
        self.assertNotIn("contextforge_registration_plan", result)
        self.assertIn("runtime-apply package", result["assistant_visible_response"])
        self.assertIn("explicit approval for this exact recorded apply surface", result["assistant_visible_response"])
        self.assertIn("Exact approval phrase to proceed:", result["assistant_visible_response"])
        self.assertIn("runtime_apply_package_id", result["assistant_visible_response"])
        self.assertIn("Recorded ContextForge gateway: `time-gateway`", result["assistant_visible_response"])
        self.assertTrue(result["copy_as_complete_visible_response"])
        self.assertTrue(result["assistant_response_policy"]["direct_client_config_is_not_contextforge_onboarding"])
        self.assertIn("Do not write direct client-local MCP configuration", result["assistant_visible_response"])

    def test_contextforge_helper_mcp_runtime_apply_accepts_client_camelcase_npm_fields(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            approval_source = root / "latest-user.json"
            approval_source.write_text(
                json.dumps({"cwd": str(root), "text": "approve runtime execute for time through time-gateway"}),
                encoding="utf-8",
            )
            npm_payload = npm_stdio_required_payload()
            npm_payload["promptLibrary"] = {
                "abstract_prompt": npm_payload["promptLibrary"]["abstract_prompt"],
                "detailPrompts": npm_payload["promptLibrary"]["detail_prompts"],
            }
            with mock.patch.dict(os.environ, {"CONTEXTFORGE_HELPER_APPROVAL_SOURCE_PATH": str(approval_source)}, clear=False):
                result = contextforge_helper_mcp.cf_project_service_onboarding_runtime_apply(
                    projectRoot=str(root),
                    candidateService="time",
                    operatorGoal="Add the Time MCP service.",
                    sourcePath="https://github.com/modelcontextprotocol/servers/tree/main/src/time",
                    serviceBinding="time:canonical",
                    backendPackage="mcp-server-time",
                    command="uvx",
                    backendArgs=["mcp-server-time", "--local-timezone", "UTC"],
                    transportType="stdio",
                    localizationType="shared_canonical",
                    functionalType="time_timezone",
                    stateType="stateless",
                    credentialBoundary="no credentials required",
                    approvalType="runtime_registration",
                    expectedTools=["get_current_time", "convert_time"],
                    issueNumber="356",
                    clientType="pi",
                    **npm_payload,
                )

        self.assertTrue(result["ok"])
        self.assertEqual("service_onboarding_runtime_apply_package", result["status"])
        self.assertFalse(result["mutation_allowed"])
        self.assertIn("runtime_apply_package_id", result["assistant_visible_response"])
        self.assertIn("install_artifact_contract", result)
        self.assertNotIn("must not have additional properties", json.dumps(result, sort_keys=True))

    def test_contextforge_helper_mcp_runtime_apply_accepts_structured_payload_path(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            approval_source = root / "latest-user.json"
            approval_source.write_text(
                json.dumps({"cwd": str(root), "text": "approve runtime execute for memory through memory-gateway"}),
                encoding="utf-8",
            )
            payload = npm_stdio_required_payload()
            payload.update(
                {
                    "candidateService": "memory",
                    "operatorGoal": "Add the Memory MCP service.",
                    "sourcePath": "https://github.com/modelcontextprotocol/servers/tree/main/src/memory",
                    "serviceBinding": "memory:canonical",
                    "backendPackage": "@modelcontextprotocol/server-memory",
                    "command": "npx",
                    "backendArgs": ["-y", "@modelcontextprotocol/server-memory"],
                    "transportType": "stdio",
                    "localizationType": "shared_canonical",
                    "functionalType": "governance_memory",
                    "stateType": "runtime_evidence_state",
                    "credentialBoundary": "no credentials required",
                    "expectedTools": ["create_entities", "read_graph"],
                }
            )
            payload_path = root / ".contextforge" / "memory-runtime-payload.json"
            payload_path.parent.mkdir(parents=True, exist_ok=True)
            payload_path.write_text(json.dumps(payload), encoding="utf-8")
            with mock.patch.dict(os.environ, {"CONTEXTFORGE_HELPER_APPROVAL_SOURCE_PATH": str(approval_source)}, clear=False):
                result = contextforge_helper_mcp.cf_project_service_onboarding_runtime_apply(
                    projectRoot=str(root),
                    structuredPayloadPath=str(payload_path),
                    clientType="pi",
                )

        self.assertTrue(result["ok"])
        self.assertEqual("service_onboarding_runtime_apply_package", result["status"])
        self.assertIn("runtime_apply_package_id", result["assistant_visible_response"])
        self.assertIn("install_artifact_contract", result)

    def test_contextforge_helper_mcp_runtime_apply_blocks_missing_npm_stdio_fields(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            approval_source = root / "latest-user.json"
            approval_source.write_text(
                json.dumps({"cwd": str(root), "text": "approve runtime execute for time through time-gateway"}),
                encoding="utf-8",
            )
            with mock.patch.dict(os.environ, {"CONTEXTFORGE_HELPER_APPROVAL_SOURCE_PATH": str(approval_source)}, clear=False):
                result = contextforge_helper_mcp.cf_project_service_onboarding_runtime_apply(
                    project_root=str(root),
                    candidate_service="time",
                    source_path="https://github.com/modelcontextprotocol/servers/tree/main/src/time",
                    backend_package="mcp-server-time",
                    backend_command="uvx",
                    transport_type="stdio",
                    localization_type="shared_canonical",
                    functional_type="time_timezone",
                    state_type="stateless",
                    expected_tools=["get_current_time", "convert_time"],
                    client_type="opencode",
                )

        self.assertTrue(result["ok"])
        self.assertEqual("service_onboarding_runtime_apply_blocked", result["status"])
        self.assertFalse(result["mutation_allowed"])
        fields = {item["field"] for item in result["required_inputs"]}
        self.assertIn("npm_package_confirmed", fields)
        self.assertIn("package_registry_type", fields)
        self.assertIn("prompt_library.abstract_prompt", fields)
        self.assertIn("prompt_library.detail_prompts", fields)
        self.assertIn("tool_schemas", fields)
        self.assertIn("does not research missing service facts", result["assistant_visible_response"])
        self.assertIn("resubmit the complete source-derived field set", result["assistant_visible_response"])

    def test_contextforge_helper_mcp_runtime_execute_applies_through_recorded_dev_surface(self) -> None:
        class FakeExecutor:
            @staticmethod
            def run(**kwargs: Any) -> dict[str, Any]:
                self.assertEqual(onboarding_surfaces.npm_stdio_endpoint("time:canonical")["streamable_http_url"], kwargs["upstream_url"])
                self.assertEqual("time-gateway", kwargs["gateway_name"])
                self.assertEqual("time-server", kwargs["server_name"])
                self.assertTrue(kwargs["apply"])
                return {
                    "mutation_performed": True,
                    "package": {"service_binding": "time:canonical"},
                    "gateway": {"action": "created", "name": "time-gateway"},
                    "server": {"action": "created", "name": "time-server"},
                    "tool_names": ["time-dev-docker-get-current-time", "time-dev-docker-convert-time"],
                    "non_actions": [
                        "no Docker, process, systemd, project-state, client config, or secret mutation by this registry executor"
                    ],
                }

        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            approval_source = root / "latest-user.json"
            approval_source.write_text(
                json.dumps({"cwd": str(root), "text": "approve runtime execute for time through time-gateway"}),
                encoding="utf-8",
            )
            with (
                mock.patch.dict(os.environ, {"CONTEXTFORGE_HELPER_APPROVAL_SOURCE_PATH": str(approval_source)}, clear=False),
                mock.patch.object(onboarding_surfaces, "load_runtime_package_executor", return_value=FakeExecutor),
            ):
                result = contextforge_helper_mcp.cf_project_service_onboarding_runtime_execute(
                    project_root=str(root),
                    candidate_service="time",
                    operator_goal="Add the Time MCP service.",
                    source_path="https://github.com/modelcontextprotocol/servers/tree/main/src/time",
                    backend_package="mcp-server-time",
                    backend_command="uvx",
                    backend_args=["mcp-server-time", "--local-timezone", "UTC"],
                    transport_type="stdio",
                    localization_type="shared_canonical",
                    functional_type="time_timezone",
                    state_type="stateless",
                    credential_boundary="no credentials required",
                    approval_type="runtime_registration",
                    expected_tools=["get_current_time", "convert_time"],
                    issue="356",
                    client_type="opencode",
                    **npm_stdio_required_kwargs(),
                )

        self.assertTrue(result["ok"])
        self.assertEqual("service_onboarding_runtime_applied", result["status"])
        self.assertTrue(result["mutation_allowed"])
        self.assertTrue(result["mutation_performed"])
        self.assertEqual(["time-dev-docker-get-current-time", "time-dev-docker-convert-time"], result["tool_names"])
        self.assertNotIn("agent_hidden_onboarding_how_to", result)
        self.assertNotIn("executor_result", result)
        self.assertIn("ContextForge development surface", result["assistant_visible_response"])
        self.assertIn("new Pi/OpenCode session", result["assistant_visible_response"])
        self.assertIn("may have installed packages and started or restarted hosted service processes", result["assistant_visible_response"])
        self.assertIn("Target-client usability is not proven yet", result["assistant_visible_response"])

    def test_contextforge_helper_mcp_runtime_execute_can_use_recorded_package_id_without_repeated_payload(self) -> None:
        class FakeExecutor:
            @staticmethod
            def run(**kwargs: Any) -> dict[str, Any]:
                self.assertEqual("time-gateway", kwargs["gateway_name"])
                self.assertEqual("time-server", kwargs["server_name"])
                self.assertTrue(kwargs["apply"])
                return {
                    "mutation_performed": True,
                    "package": {"service_binding": "time:canonical"},
                    "gateway": {"action": "ready", "name": "time-gateway"},
                    "server": {"action": "ready", "name": "time-server"},
                    "tool_names": ["time-dev-docker-get-current-time", "time-dev-docker-convert-time"],
                }

        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            package = onboarding_surfaces.build_service_onboarding_runtime_apply_package(
                str(root),
                {
                    "candidate_service": "time",
                    "operator_goal": "Add the Time MCP service.",
                    "source_path": "https://github.com/modelcontextprotocol/servers/tree/main/src/time",
                    "backend_package": "mcp-server-time",
                    "backend_command": "uvx",
                    "backend_args": ["mcp-server-time", "--local-timezone", "UTC"],
                    "transport_type": "stdio",
                    "localization_type": "shared_canonical",
                    "functional_type": "time_timezone",
                    "state_type": "stateless",
                    "credential_boundary": "no credentials required",
                    "approval_type": "runtime_registration",
                    "expected_tools": ["get_current_time", "convert_time"],
                    **npm_stdio_required_kwargs(),
                },
            )
            package_id = package["runtime_apply_package_id"]
            self.assertTrue((root / ".contextforge/service-onboarding/runtime-apply-packages" / f"{package_id}.json").exists())
            self.assertIn("Runtime/apply package id", package["assistant_visible_response"])

            approval_source = root / "latest-user.json"
            approval_source.write_text(
                json.dumps({"cwd": str(root), "text": f"approve runtime execute for time through time-gateway using package {package_id}"}),
                encoding="utf-8",
            )
            with (
                mock.patch.dict(os.environ, {"CONTEXTFORGE_HELPER_APPROVAL_SOURCE_PATH": str(approval_source)}, clear=False),
                mock.patch.object(onboarding_surfaces, "load_runtime_package_executor", return_value=FakeExecutor),
            ):
                result = contextforge_helper_mcp.cf_project_service_onboarding_runtime_execute(
                    project_root=str(root),
                    runtime_apply_package_id=package_id,
                    client_type="opencode",
                )

        self.assertTrue(result["ok"])
        self.assertEqual("service_onboarding_runtime_applied", result["status"])
        self.assertEqual(package_id, result["runtime_apply_package_id"])
        self.assertEqual(["time-dev-docker-get-current-time", "time-dev-docker-convert-time"], result["tool_names"])

    def test_contextforge_helper_mcp_runtime_execute_rejects_stale_package_id_approval(self) -> None:
        class FakeExecutor:
            @staticmethod
            def run(**_kwargs: Any) -> dict[str, Any]:
                raise AssertionError("executor must not run when approval names a different package id")

        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            package = onboarding_surfaces.build_service_onboarding_runtime_apply_package(
                str(root),
                {
                    "candidate_service": "time",
                    "operator_goal": "Add the Time MCP service.",
                    "source_path": "https://github.com/modelcontextprotocol/servers/tree/main/src/time",
                    "backend_package": "mcp-server-time",
                    "backend_command": "uvx",
                    "backend_args": ["mcp-server-time", "--local-timezone", "UTC"],
                    "transport_type": "stdio",
                    "localization_type": "shared_canonical",
                    "functional_type": "time_timezone",
                    "state_type": "stateless",
                    "credential_boundary": "no credentials required",
                    "approval_type": "runtime_registration",
                    "expected_tools": ["get_current_time", "convert_time"],
                    **npm_stdio_required_kwargs(),
                },
            )
            package_id = package["runtime_apply_package_id"]
            approval_source = root / "latest-user.json"
            approval_source.write_text(
                json.dumps(
                    {
                        "cwd": str(root),
                        "text": "Approve runtime/apply for time:canonical using executor surface docker/contextforge-harness/scripts/apply_onboarding_runtime_package.py and runtime_apply_package_id rap_stale_previous.",
                    }
                ),
                encoding="utf-8",
            )
            with (
                mock.patch.dict(os.environ, {"CONTEXTFORGE_HELPER_APPROVAL_SOURCE_PATH": str(approval_source)}, clear=False),
                mock.patch.object(onboarding_surfaces, "load_runtime_package_executor", return_value=FakeExecutor),
            ):
                result = contextforge_helper_mcp.cf_project_service_onboarding_runtime_execute(
                    project_root=str(root),
                    runtime_apply_package_id=package_id,
                    client_type="opencode",
                )

        self.assertFalse(result["ok"])
        self.assertEqual("PermissionError", result["error"]["type"])
        self.assertIn("exact runtime/apply package id", result["error"]["message"])
        self.assertIn(package_id, result["error"]["message"])

    def test_runtime_apply_can_delegate_to_host_proxy_for_containerized_clients(self) -> None:
        package = {
            "status": "service_onboarding_runtime_apply_package",
            "service_provision_plan": {"service_binding": "time:canonical"},
            "contextforge_registration_plan": {"plan_id": "time-plan"},
        }
        target = {
            "upstream_url": "http://npm-stdio-host:20001/mcp",
            "gateway_name": "time-gateway",
            "virtual_server_name": "time-server",
            "executor_surface": "docker/contextforge-harness/scripts/apply_onboarding_runtime_package.py",
        }
        observed: dict[str, Any] = {}

        class FakeResponse:
            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, *_args: Any) -> None:
                return None

            def read(self) -> bytes:
                return json.dumps({"mutation_performed": True, "tool_names": ["time-dev-docker-get-current-time"]}).encode()

        def fake_urlopen(request: Any, timeout: int) -> FakeResponse:
            observed["timeout"] = timeout
            observed["authorization"] = request.headers.get("Authorization")
            observed["payload"] = json.loads(request.data.decode("utf-8"))
            return FakeResponse()

        with (
            mock.patch.dict(
                os.environ,
                {
                    "CONTEXTFORGE_RUNTIME_APPLY_PROXY_TOKEN": "proxy-token",
                    "CONTEXTFORGE_RUNTIME_APPLY_PROXY_BASE_URL": "http://127.0.0.1:4445",
                    "CONTEXTFORGE_RUNTIME_APPLY_PROXY_ENV_FILE": "/host/contextforge.env",
                },
                clear=False,
            ),
            mock.patch.object(onboarding_surfaces.urllib.request, "urlopen", side_effect=fake_urlopen),
        ):
            result = onboarding_surfaces.execute_runtime_apply_package_via_proxy(
                package,
                target,
                {"wait_attempts": 3},
                proxy_url="http://host.docker.internal:49152/runtime/apply",
            )

        self.assertTrue(result["mutation_performed"])
        self.assertEqual("Bearer proxy-token", observed["authorization"])
        payload = observed["payload"]
        self.assertEqual(package, payload["package"])
        self.assertEqual(target, payload["target"])
        self.assertEqual("http://127.0.0.1:4445", payload["base_url"])
        self.assertEqual("/host/contextforge.env", payload["env_file"])
        self.assertEqual(3, payload["wait_attempts"])

    def test_contextforge_helper_mcp_runtime_execute_reports_failed_apply_without_reload_claim(self) -> None:
        class FakeExecutor:
            @staticmethod
            def run(**_kwargs: Any) -> dict[str, Any]:
                return {
                    "mutation_performed": False,
                    "package": {"service_binding": "time:canonical"},
                    "failure_report": {
                        "failed_stage": "tool_refresh",
                        "sanitized_error": "expected tools were not discovered",
                        "rollback_actions_attempted": [
                            {"target": "time:canonical", "action": "rollback_npm_stdio_host_runtime", "ok": True}
                        ],
                        "rollback_result": "passed",
                        "residual_cleanup_risk": "",
                    },
                    "tool_names": [],
                    "non_actions": ["runtime/apply failed before service exposure"],
                }

        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            approval_source = root / "latest-user.json"
            approval_source.write_text(
                json.dumps({"cwd": str(root), "text": "approve runtime execute for time through time-gateway"}),
                encoding="utf-8",
            )
            with (
                mock.patch.dict(os.environ, {"CONTEXTFORGE_HELPER_APPROVAL_SOURCE_PATH": str(approval_source)}, clear=False),
                mock.patch.object(onboarding_surfaces, "load_runtime_package_executor", return_value=FakeExecutor),
            ):
                result = contextforge_helper_mcp.cf_project_service_onboarding_runtime_execute(
                    project_root=str(root),
                    candidate_service="time",
                    operator_goal="Add the Time MCP service.",
                    source_path="https://github.com/modelcontextprotocol/servers/tree/main/src/time",
                    backend_package="mcp-server-time",
                    backend_command="uvx",
                    backend_args=["mcp-server-time", "--local-timezone", "UTC"],
                    transport_type="stdio",
                    localization_type="shared_canonical",
                    functional_type="time_timezone",
                    state_type="stateless",
                    credential_boundary="no credentials required",
                    approval_type="runtime_registration",
                    expected_tools=["get_current_time", "convert_time"],
                    issue="356",
                    client_type="opencode",
                    **npm_stdio_required_kwargs(),
                )

        self.assertFalse(result["ok"])
        self.assertEqual("service_onboarding_runtime_apply_failed", result["status"])
        self.assertTrue(result["mutation_allowed"])
        self.assertFalse(result["mutation_performed"])
        self.assertEqual("tool_refresh", result["failed_stage"])
        self.assertEqual("passed", result["rollback_result"])
        self.assertEqual([], result["tool_names"])
        self.assertIn("was not applied", result["assistant_visible_response"])
        self.assertIn("no service was installed, registered, exposed, or made available", result["assistant_visible_response"])
        self.assertIn("Do not ask the user to reload", result["assistant_visible_response"])
        self.assertNotIn("new Pi/OpenCode session", result["assistant_visible_response"])

    def test_contextforge_helper_mcp_runtime_execute_blocks_missing_required_inputs_with_visible_message(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            approval_source = root / "latest-user.json"
            approval_source.write_text(
                json.dumps({"cwd": str(root), "text": "approve runtime execute for memory-server through memory-server-gateway"}),
                encoding="utf-8",
            )
            with mock.patch.dict(os.environ, {"CONTEXTFORGE_HELPER_APPROVAL_SOURCE_PATH": str(approval_source)}, clear=False):
                result = contextforge_helper_mcp.cf_project_service_onboarding_runtime_execute(
                    project_root=str(root),
                    candidate_service="memory-server",
                    operator_goal="Enable persistent knowledge graph memory via MCP.",
                    source_path="https://github.com/modelcontextprotocol/servers/tree/main/src/memory",
                    backend_package="@modelcontextprotocol/server-memory",
                    backend_command="npx",
                    transport_type="stdio",
                    localization_type="project_scoped",
                    functional_type="filesystem_content",
                    state_type="local_filesystem_state",
                    credential_boundary="no credentials required",
                    expected_tools=["read_graph"],
                    package_registry_type="npm",
                    npm_package_confirmed=True,
                    package_arguments=["-y", "@modelcontextprotocol/server-memory"],
                    environment_variables=[{"MEMORY_FILE_PATH": "/workspace/.contextforge/memory/memory.jsonl"}],
                    client_type="pi",
                )

        self.assertFalse(result["ok"])
        self.assertEqual("service_onboarding_runtime_apply_blocked", result["status"])
        self.assertFalse(result["mutation_allowed"])
        self.assertFalse(result["mutation_performed"])
        self.assertEqual("required_inputs", result["failed_stage"])
        self.assertIn("Required before continuing", result["assistant_visible_response"])
        self.assertIn("prompt_library.abstract_prompt", result["assistant_visible_response"])
        self.assertTrue(result["required_inputs"])

    def test_runtime_package_normalizes_natural_npm_args_and_env_mapping(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            result = onboarding_surfaces.build_service_onboarding_runtime_apply_package(
                str(root),
                {
                    "candidate_service": "memory-server",
                    "operator_goal": "Enable persistent knowledge graph memory via MCP.",
                    "source_path": "https://github.com/modelcontextprotocol/servers/tree/main/src/memory",
                    "backend_package": "@modelcontextprotocol/server-memory",
                    "backend_command": "npx",
                    "transport_type": "stdio",
                    "localization_type": "project_scoped",
                    "functional_type": "filesystem_content",
                    "state_type": "local_filesystem_state",
                    "credential_boundary": "no credentials required",
                    "expected_tools": ["read_graph"],
                    **{
                        **npm_stdio_required_kwargs(),
                        "environment_variables": [{"MEMORY_FILE_PATH": "/workspace/.contextforge/memory/memory.jsonl"}],
                        "package_arguments": ["-y", "@modelcontextprotocol/server-memory"],
                        "tool_schemas": {
                            "read_graph": {
                                "description": "Return the complete persisted knowledge graph.",
                                "inputSchema": {"type": "object", "properties": {}, "required": []},
                                "source_anchor": "https://github.com/modelcontextprotocol/servers/tree/main/src/memory",
                            },
                            "search_nodes": {
                                "description": "Search entities and relations by query string.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {"query": {"type": "string"}},
                                    "required": ["query"],
                                },
                                "source_anchor": "https://github.com/modelcontextprotocol/servers/tree/main/src/memory",
                            },
                        },
                        "tool_schema_summaries": [
                            "read_graph: no input; returns the full knowledge graph as JSON",
                            "search_nodes: query string; returns matching entities and relations",
                        ],
                    },
                },
            )

        record = result["install_artifact_contract"]["artifacts"]["npm_stdio_service_record"]["content"]
        self.assertEqual(["-y", "@modelcontextprotocol/server-memory"], record["package_arguments"])
        self.assertEqual("npx", record["stdio"]["command"])
        self.assertEqual(["-y", "@modelcontextprotocol/server-memory"], record["stdio"]["args"])
        self.assertEqual(
            {"MEMORY_FILE_PATH": "/workspace/.contextforge/memory/memory.jsonl"},
            record["environment"]["values"],
        )
        self.assertIn("read_graph", json.dumps(record["tool_schemas"]))

    def test_runtime_apply_package_normalizes_command_shaped_binding_from_known_package_alias(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            package = onboarding_surfaces.build_service_onboarding_runtime_apply_package(
                str(root),
                {
                    "candidate_service": "mcp-server-time",
                    "service_binding": "uvx mcp-server-time",
                    "backend_package": "mcp-server-time",
                    "backend_command": "uvx mcp-server-time",
                    "transport_type": "stdio",
                    "localization_type": "shared_canonical",
                    "functional_type": "time_timezone",
                    "state_type": "stateless",
                    "expected_tools": ["get_current_time", "convert_time"],
                    **npm_stdio_required_kwargs(),
                },
            )

        self.assertEqual("time:canonical", package["service_provision_plan"]["service_binding"])
        self.assertEqual(
            ["uvx", "mcp-server-time"],
            package["service_provision_plan"]["x_desired_artifacts"]["backend_manifest"]["content"]["backend_command"],
        )
        self.assertIn("Service binding: `time:canonical`", package["assistant_visible_response"])

    def test_runtime_execute_resolves_known_package_alias_when_source_not_carried_forward(self) -> None:
        class FakeExecutor:
            @staticmethod
            def run(**kwargs: Any) -> dict[str, Any]:
                self.assertEqual(onboarding_surfaces.npm_stdio_endpoint("time:canonical")["streamable_http_url"], kwargs["upstream_url"])
                self.assertEqual("time-gateway", kwargs["gateway_name"])
                self.assertEqual("time-server", kwargs["server_name"])
                self.assertTrue(kwargs["apply"])
                return {
                    "mutation_performed": True,
                    "package": {"service_binding": "time:canonical"},
                    "gateway": {"action": "ready", "name": "time-gateway"},
                    "server": {"action": "ready", "name": "time-server"},
                    "tool_names": ["time-dev-docker-get-current-time", "time-dev-docker-convert-time"],
                    "non_actions": [
                        "no Docker, process, systemd, project-state, client config, or secret mutation by this registry executor"
                    ],
                }

        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            approval_source = root / "latest-user.json"
            approval_source.write_text(
                json.dumps({"cwd": str(root), "text": "approve runtime execute for mcp-server-time through time-gateway"}),
                encoding="utf-8",
            )
            with (
                mock.patch.dict(os.environ, {"CONTEXTFORGE_HELPER_APPROVAL_SOURCE_PATH": str(approval_source)}, clear=False),
                mock.patch.object(onboarding_surfaces, "load_runtime_package_executor", return_value=FakeExecutor),
            ):
                result = contextforge_helper_mcp.cf_project_service_onboarding_runtime_execute(
                    project_root=str(root),
                    candidate_service="mcp-server-time",
                    service_binding="uvx mcp-server-time",
                    backend_command="uvx mcp-server-time",
                    transport_type="stdio",
                    localization_type="shared_canonical",
                    functional_type="time_timezone",
                    state_type="stateless",
                    expected_tools=["get_current_time", "convert_time"],
                    client_type="opencode",
                    backend_package="mcp-server-time",
                    **npm_stdio_required_kwargs(),
                )

        self.assertTrue(result["ok"])
        self.assertEqual("service_onboarding_runtime_applied", result["status"])
        self.assertEqual(["time-dev-docker-get-current-time", "time-dev-docker-convert-time"], result["tool_names"])
        self.assertIn("ContextForge development surface", result["assistant_visible_response"])

    def test_contextforge_helper_mcp_runtime_execute_requires_recorded_executor_surface_approval(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            approval_source = root / "latest-user.json"
            approval_source.write_text(
                json.dumps({"cwd": str(root), "text": "approve runtime apply and registration for time"}),
                encoding="utf-8",
            )
            with mock.patch.dict(os.environ, {"CONTEXTFORGE_HELPER_APPROVAL_SOURCE_PATH": str(approval_source)}, clear=False):
                result = contextforge_helper_mcp.cf_project_service_onboarding_runtime_execute(
                    project_root=str(root),
                    candidate_service="time",
                    operator_goal="Add the Time MCP service.",
                    source_path="https://github.com/modelcontextprotocol/servers/tree/main/src/time",
                    backend_package="mcp-server-time",
                    backend_command="uvx",
                    backend_args=["mcp-server-time", "--local-timezone", "UTC"],
                    transport_type="stdio",
                    localization_type="shared_canonical",
                    functional_type="time_timezone",
                    state_type="stateless",
                    credential_boundary="no credentials required",
                    approval_type="runtime_registration",
                    expected_tools=["get_current_time", "convert_time"],
                    issue="356",
                    client_type="opencode",
                    **npm_stdio_required_kwargs(),
                )

        self.assertFalse(result["ok"])
        self.assertEqual("PermissionError", result["error"]["type"])
        self.assertIn("recorded runtime executor surface", result["error"]["message"])
        self.assertIn("Exact approval phrase:", result["error"]["message"])
        self.assertIn("Approve runtime/apply for time:canonical using executor surface docker/contextforge-harness/scripts/apply_onboarding_runtime_package.py", result["error"]["message"])

    def test_contextforge_helper_mcp_runtime_execute_rejects_generic_runtime_approval_without_service_identity(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            approval_source = root / "latest-user.json"
            approval_source.write_text(
                json.dumps({"cwd": str(root), "text": "approve runtime apply and registration"}),
                encoding="utf-8",
            )
            with mock.patch.dict(os.environ, {"CONTEXTFORGE_HELPER_APPROVAL_SOURCE_PATH": str(approval_source)}, clear=False):
                result = contextforge_helper_mcp.cf_project_service_onboarding_runtime_execute(
                    project_root=str(root),
                    candidate_service="time",
                    source_path="https://github.com/modelcontextprotocol/servers/tree/main/src/time",
                    backend_package="mcp-server-time",
                    backend_command="uvx",
                    transport_type="stdio",
                    localization_type="shared_canonical",
                    functional_type="time_timezone",
                    state_type="stateless",
                    client_type="opencode",
                )

        self.assertFalse(result["ok"])
        self.assertEqual("PermissionError", result["error"]["type"])
        self.assertIn("does not identify the service", result["error"]["message"])
        self.assertIn("Exact approval phrase:", result["error"]["message"])

    def test_runtime_executor_target_rejects_conflicting_source_identity_before_executor_load(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            with self.assertRaisesRegex(RuntimeError, "no approved development runtime executor target"):
                onboarding_surfaces.apply_service_onboarding_runtime_package(
                    str(root),
                    {
                        "candidate_service": "time",
                        "source_path": "https://example.invalid/not-time",
                        "backend_package": "mcp-server-time",
                        "backend_command": "uvx",
                        "transport_type": "stdio",
                        "localization_type": "shared_canonical",
                        "functional_type": "time_timezone",
                        "state_type": "stateless",
                        "expected_tools": ["get_current_time", "convert_time"],
                        **npm_stdio_required_kwargs(),
                    },
                )

    def test_contextforge_helper_mcp_runtime_apply_preview_does_not_require_latest_runtime_approval(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            approval_source = root / "latest-user.json"
            approval_source.write_text(
                json.dumps({"cwd": str(root), "text": "please add the time mcp service"}),
                encoding="utf-8",
            )
            with mock.patch.dict(
                os.environ,
                {
                    "CONTEXTFORGE_HELPER_APPROVAL_SOURCE_PATH": str(approval_source),
                },
                clear=False,
            ):
                result = contextforge_helper_mcp.cf_project_service_onboarding_runtime_apply(
                    project_root=str(root),
                    candidate_service="time",
                    source_path="https://github.com/modelcontextprotocol/servers/tree/main/src/time",
                    backend_package="mcp-server-time",
                    backend_command="uvx",
                    transport_type="stdio",
                    localization_type="shared_canonical",
                    functional_type="time_timezone",
                    state_type="stateless",
                    client_type="opencode",
                )

        self.assertTrue(result["ok"])
        self.assertEqual("service_onboarding_runtime_apply_blocked", result["status"])
        self.assertFalse(result["mutation_allowed"])
        self.assertIn("Required before continuing", result["assistant_visible_response"])
        self.assertIn("No runtime, registry, Docker", result["assistant_visible_response"])

    def test_pi_helper_cli_runtime_execute_operation_is_retired(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            approval_source = root / "latest-user.json"
            approval_source.write_text(
                json.dumps({"cwd": str(root), "text": "please add the time mcp service"}),
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts/pi_project_init_helper_cli.py"),
                    "--operation",
                    "apply_service_onboarding_runtime_package",
                    "--payload-json",
                    json.dumps(
                        {
                            "project_root": str(root),
                            "client_type": "pi",
                            "candidateService": "time",
                            "sourcePath": "https://github.com/modelcontextprotocol/servers/tree/main/src/time",
                            "backendPackage": "mcp-server-time",
                            "backendCommand": "uvx",
                            "transportType": "stdio",
                            "localizationType": "shared_canonical",
                            "functionalType": "time_timezone",
                            "stateType": "stateless",
                            "expectedTools": ["get_current_time", "convert_time"],
                            **npm_stdio_required_payload(),
                        }
                    ),
                ],
                cwd=REPO_ROOT,
                check=False,
                capture_output=True,
                text=True,
                env={**os.environ, "CONTEXTFORGE_HELPER_APPROVAL_SOURCE_PATH": str(approval_source)},
            )

        self.assertEqual(1, result.returncode)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["ok"])
        self.assertEqual("ValueError", payload["error"]["type"])
        self.assertIn("unsupported operation", payload["error"]["message"])

    def test_contextforge_helper_mcp_accepts_natural_onboarding_aliases(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            approval_source = root / "latest-user.json"
            approval_source.write_text(
                json.dumps({"cwd": str(root), "text": "approve runtime apply and registration for time"}),
                encoding="utf-8",
            )
            continuation = contextforge_helper_mcp.build_service_onboarding_continue(
                project_root=str(root),
                candidate_service="time",
                source_path="https://github.com/modelcontextprotocol/servers/tree/main/src/time",
                backend_package="mcp-server-time",
                backend_command="uvx",
                transport_type="stdio",
                localization_type="shared_canonical",
                functional_type="time_timezone",
                state_type="stateless",
                credential_boundary="no credentials required",
                expected_tools=["get_current_time", "convert_time"],
                client_type="opencode",
            )
            with mock.patch.dict(os.environ, {"CONTEXTFORGE_HELPER_APPROVAL_SOURCE_PATH": str(approval_source)}, clear=False):
                runtime_apply = contextforge_helper_mcp.build_service_onboarding_runtime_apply(
                    project_root=str(root),
                    candidate_service="time",
                    source_path="https://github.com/modelcontextprotocol/servers/tree/main/src/time",
                    backend_package="mcp-server-time",
                    backend_command="uvx",
                    transport_type="stdio",
                    localization_type="shared_canonical",
                    functional_type="time_timezone",
                    state_type="stateless",
                    credential_boundary="no credentials required",
                    expected_tools=["get_current_time", "convert_time"],
                    client_type="opencode",
                    **npm_stdio_required_kwargs(),
                )

        self.assertEqual("service_onboarding_continuation_plan", continuation["status"])
        self.assertEqual("service_onboarding_runtime_apply_package", runtime_apply["status"])
        self.assertFalse(continuation["mutation_allowed"])
        self.assertFalse(runtime_apply["mutation_allowed"])

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
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp, mock.patch.object(
            contextforge_helper_mcp,
            "_contextforge_registry_service_offerings",
            return_value=[registry_service_descriptor("context7")],
        ):
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

    def test_helper_keeps_install_only_flow_blocked_after_reload_report(self) -> None:
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
        self.assertEqual("client_reload_report_ignored", ack["status"])
        self.assertEqual("client_reload_required", after_ack["status"])
        self.assertEqual("codex-project-init-installed", after_ack["next_turn"]["question_id"])

    def test_helper_blocks_new_selection_after_install_only_reload_report(self) -> None:
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
        self.assertEqual("client_reload_report_ignored", ack["status"])
        self.assertEqual("client_reload_required", capabilities["status"])
        self.assertEqual("client_reload_required", proposal["status"])
        self.assertEqual("codex-project-init-installed", proposal["next_turn"]["question_id"])

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
        self.assertEqual("client_reload_report_ignored", ack["status"])
        self.assertEqual("client_reload_required", after_ack["status"])
        self.assertEqual("codex-project-init-installed", after_ack["next_turn"]["question_id"])

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
        self.assertEqual("client_reload_report_ignored", ack["status"])
        self.assertEqual("client_reload_required", after_ack["status"])
        self.assertEqual("codex-project-init-installed", after_ack["next_turn"]["question_id"])
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

        self.assertEqual([], full_report["available_tools"])
        self.assertEqual(["context7-local-resolve-library-id", "context7-local-query-docs"], full_report["project_tool_policies"][0]["tool_policy_names"])
        self.assertEqual("reload_required", full_report["project_services"][0]["target_client_projection_status"])
        self.assertFalse(full_report["project_services"][0]["available_to_target_client"])
        self.assertTrue(result["ok"])
        self.assertEqual("available_tools_report", result["status"])
        self.assertIn("assistant_visible_response", result)
        self.assertEqual(result["assistant_visible_response"], result["message"])
        self.assertTrue(result["copy_as_complete_visible_response"])
        self.assertTrue(result["do_not_summarize"])
        self.assertNotIn("available_tools", result)
        self.assertNotIn("state_revision", result)
        visible = result["assistant_visible_response"]
        self.assertTrue(visible.startswith("ContextForge tool availability\n\nProject\n"))
        self.assertIn(f"- Root: `{root}`", visible)
        self.assertIn("- Revision: 1", visible)
        self.assertIn("- Target client: opencode", visible)
        self.assertIn("Project services\n- context7:canonical", visible)
        self.assertIn("Configured/imported tools for this client\n- no currently available target-client tools in this session", visible)
        self.assertIn("MCP runtime diagnostics\n- context7:canonical: reload_pending_before_mcp_startup", visible)
        self.assertIn("Readback limits\n- Client-visible tool use is not proven by this readback", visible)
        self.assertIn("Next step\n- After approved OpenCode project-local MCP config changes", visible)
        self.assertIn("no project-init proposal, approval, or apply", result["non_actions"])

    def test_pi_tool_availability_uses_current_runtime_readback_when_supplied(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
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
            runtime = {
                "tools": [
                    {
                        "serviceBinding": "context7:canonical",
                        "mcpName": "context7-local-resolve-library-id",
                        "piName": "cf_context7_s123__context7-local-resolve-library-id",
                        "blockedByDefault": False,
                    },
                    {
                        "serviceBinding": "context7:canonical",
                        "mcpName": "context7-local-query-docs",
                        "piName": "cf_context7_s123__context7-local-query-docs",
                        "blockedByDefault": False,
                    },
                ]
            }

            stale_report = contextforge_helper_mcp.project_tool_availability(str(root), client_type="pi")
            runtime_report = contextforge_helper_mcp.project_tool_availability(
                str(root),
                client_type="pi",
                target_client_runtime=runtime,
            )

        self.assertEqual([], stale_report["available_tools"])
        self.assertIn("reload_pending_before_mcp_startup", stale_report["assistant_visible_response"])
        self.assertEqual("tools_registered_observed", runtime_report["current_session_boundary"]["reload_status"])
        self.assertFalse(runtime_report["current_session_boundary"]["requires_reload"])
        self.assertEqual(["context7-local-resolve-library-id", "context7-local-query-docs"], runtime_report["available_tools"][0]["tool_names"])
        self.assertTrue(runtime_report["project_services"][0]["available_to_target_client"])
        self.assertEqual("visible_in_current_session", runtime_report["project_services"][0]["target_client_visibility_status"])
        self.assertIn("context7:canonical: context7-local-resolve-library-id, context7-local-query-docs", runtime_report["assistant_visible_response"])
        self.assertIn("mcp_available_or_partially_observed", runtime_report["assistant_visible_response"])
        self.assertIn("do not ask for another reload", runtime_report["assistant_visible_response"])

    def test_readback_helpers_handle_uninitialized_project_state_without_attribute_error(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            availability = contextforge_helper_mcp.get_project_tool_availability(str(root), client_type="opencode")
            readback = contextforge_helper_mcp.get_project_state_readback(str(root), client_type="opencode")

        self.assertTrue(availability["ok"])
        self.assertEqual("available_tools_report", availability["status"])
        self.assertIn("none recorded", availability["assistant_visible_response"])
        self.assertTrue(readback["ok"])
        self.assertEqual("project_state_readback", readback["status"])
        self.assertIn("- Status: uninitialized", readback["assistant_visible_response"])

    def test_pi_tool_availability_accepts_static_mentality_runtime_readback(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            mentality = service_descriptor("mentality")
            mentality["service_binding"] = "mentality:static_repo_local"
            mentality["instantiation_class"] = "static_repo_local"
            selected = [mentality]
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
            runtime = {
                "tools": [
                    {
                        "serviceBinding": "mentality:static_repo_local",
                        "mcpName": "governance_list",
                        "piName": "cf_mentality_governance_list",
                        "blockedByDefault": False,
                    },
                    {
                        "serviceBinding": "mentality:static_repo_local",
                        "mcpName": "governance_read",
                        "piName": "cf_mentality_governance_read",
                        "blockedByDefault": False,
                    },
                ]
            }

            runtime_report = contextforge_helper_mcp.project_tool_availability(
                str(root),
                client_type="pi",
                target_client_runtime=runtime,
            )

        self.assertEqual("tools_registered_observed", runtime_report["current_session_boundary"]["reload_status"])
        self.assertEqual(["governance_list", "governance_read"], runtime_report["available_tools"][0]["tool_names"])
        self.assertTrue(runtime_report["project_services"][0]["available_to_target_client"])
        self.assertEqual("visible_in_current_session", runtime_report["project_services"][0]["target_client_visibility_status"])
        self.assertIn("mentality:static_repo_local: governance_list, governance_read", runtime_report["assistant_visible_response"])
        self.assertIn("do not ask for another reload", runtime_report["assistant_visible_response"])

    def test_opencode_readback_distinguishes_mcp_startup_failure_from_reload_pending(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp, mock.patch.object(
            contextforge_helper_mcp,
            "_contextforge_registry_service_offerings",
            return_value=[],
        ):
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
        self.assertFalse(availability["project_services"][0]["available_to_target_client"])
        self.assertEqual([], availability["available_tools"])
        self.assertIn("do not ask for another reload", availability["assistant_visible_response"])
        self.assertNotIn("start a new OpenCode session", availability["assistant_visible_response"])
        self.assertIn("mcp_server_startup_failed", capabilities["assistant_visible_response"])
        self.assertIn("do not ask for another reload", capabilities["assistant_visible_response"])
        self.assertEqual(
            "mcp_server_startup_failed",
            readback["target_client_services"][0]["mcp_runtime_diagnostic"]["classification"],
        )
        self.assertFalse(readback["target_client_services"][0]["available_to_target_client"])
        self.assertEqual(
            "mcp_server_startup_failed",
            readback["target_client_services"][0]["readiness_layers"]["mcp_runtime"],
        )
        self.assertIn("MCP runtime mcp_server_startup_failed", readback["assistant_visible_response"])
        self.assertIn("do not ask for another reload", readback["assistant_visible_response"])
        self.assertIn("no validation, tool probe, backend mutation, or registry mutation", readback["non_actions"])

    def test_opencode_readback_classifies_auth_and_transport_errors_before_reload_pending(self) -> None:
        cases = [
            (
                {"error_message": "ContextForge returned HTTP 401 unauthorized"},
                "contextforge_auth_failed",
                "failed",
                "not_observed",
            ),
            (
                {"mcp_error_class": "unauthorized"},
                "contextforge_auth_failed",
                "failed",
                "not_observed",
            ),
            (
                {"stderr": "connect ECONNREFUSED 127.0.0.1:4445"},
                "contextforge_transport_failed",
                "not_observed",
                "failed",
            ),
            (
                {"transport_error": "connection_refused"},
                "contextforge_transport_failed",
                "not_observed",
                "failed",
            ),
        ]
        for diagnostics, classification, auth_status, transport_status in cases:
            with self.subTest(diagnostics=diagnostics):
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
                    state["services"]["context7:canonical"]["target_clients"]["opencode"]["mcp_runtime_diagnostics"] = diagnostics
                    project_state.write_state_atomic(root, state)

                    availability = contextforge_helper_mcp.project_tool_availability(str(root), client_type="opencode")
                    readback = contextforge_helper_mcp.project_state_readback(str(root), client_type="opencode")

                diagnostic = availability["mcp_runtime_diagnostics"][0]
                self.assertEqual(classification, diagnostic["classification"])
                self.assertTrue(diagnostic["attempted"])
                self.assertEqual(auth_status, diagnostic["auth_status"])
                self.assertEqual(transport_status, diagnostic["transport_status"])
                self.assertFalse(availability["project_services"][0]["available_to_target_client"])
                self.assertEqual([], availability["available_tools"])
                self.assertFalse(readback["target_client_services"][0]["available_to_target_client"])
                self.assertIn("do not ask for another reload", availability["assistant_visible_response"])
                self.assertIn(classification, readback["assistant_visible_response"])
                self.assertIn("do not ask for another reload", readback["assistant_visible_response"])

    def test_contextforge_helper_mcp_reports_missing_target_client_projection_without_available_tools(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp, mock.patch.object(
            contextforge_helper_mcp,
            "_contextforge_registry_service_offerings",
            return_value=[
                registry_service_descriptor("context7"),
                registry_service_descriptor("github"),
            ],
        ):
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
        self.assertIn("Project tool policy\n- context7:canonical: context7-local-resolve-library-id, context7-local-query-docs", readback["assistant_visible_response"])
        self.assertIn("Configured/imported tools for this client\n- none reported", readback["assistant_visible_response"])
        self.assertIn("projection missing; client state not_recorded", readback["assistant_visible_response"])

        self.assertEqual([], capabilities["available_now"])
        self.assertEqual(expected_actions, capabilities["missing_target_client_projection"])
        self.assertEqual("context7:canonical", capabilities["project_services"][0]["service_binding"])
        self.assertIn("Configured in current project state for opencode\n- none reported", capabilities["assistant_visible_response"])
        self.assertIn("Missing target-client projections\n- context7:canonical", capabilities["assistant_visible_response"])

    def test_target_client_projection_status_vocabulary_keeps_readiness_layers_separate(self) -> None:
        cases = [
            (
                "blocked",
                {"status": "blocked", "validation_status": "blocked", "reload_status": "not_required"},
                "blocked",
                False,
            ),
            (
                "stale",
                {"status": "stale", "validation_status": "installed", "reload_status": "not_required"},
                "stale",
                False,
            ),
            (
                "partial",
                {"status": "partial", "validation_status": "mixed", "reload_status": "not_required"},
                "partial",
                False,
            ),
            (
                "validation_pending",
                {"status": "validation_pending", "validation_status": "pending", "reload_status": "not_required"},
                "validation_pending",
                False,
            ),
            (
                "skipped",
                {"status": "installed", "validation_status": "skipped", "reload_status": "not_required"},
                "skipped",
                False,
            ),
            (
                "recorded_fallback",
                {"status": "project_local_config_planned", "validation_status": "unknown", "reload_status": "not_required"},
                "recorded",
                False,
            ),
            (
                "imported",
                {"status": "installed", "validation_status": "installed", "reload_status": "not_required"},
                "imported",
                True,
            ),
            (
                "reload_required",
                {"status": "installed", "validation_status": "installed", "reload_status": "reload_required"},
                "reload_required",
                False,
            ),
            (
                "verified",
                {
                    "status": "verified",
                    "validation_status": "passed",
                    "reload_status": "not_required",
                    "target_client_visible": True,
                    "proof_ref": "run/evidence/context7-codex-proof.json",
                },
                "verified",
                True,
            ),
        ]
        for label, target_state, expected_projection, expected_available in cases:
            with self.subTest(label=label):
                with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
                    root = Path(tmp).resolve()
                    selected = [service_descriptor("context7")]
                    config_plan = binding.plan_project_init_target_client_activation(root, selected, target_client="codex")
                    state = project_state.apply_project_init_activation_to_state(
                        project_state.default_state(root),
                        selected,
                        target_client="codex",
                        client_config_plan=config_plan,
                        validation_plan=binding.build_project_init_validation_plan(selected, validation_mode="installed", target_client="codex"),
                        validation_results={},
                        consent_receipt_refs=CONSENT_REFS,
                    )
                    job_id = state["project_init"]["current_job_id"]
                    if expected_projection != "reload_required":
                        state["project_init"]["activation_jobs"][job_id]["x_client_reload_fsm"] = {
                            "client_type": "codex",
                            "job_id": job_id,
                            "state": "tools_registered_observed",
                            "observed_at": "2026-06-20T00:00:00Z",
                            "proof_ref": "run/evidence/context7-codex-tool-list.json",
                        }
                    state["services"]["context7:canonical"]["target_clients"]["codex"].update(target_state)
                    project_state.write_state_atomic(root, state)

                    availability = contextforge_helper_mcp.project_tool_availability(str(root), client_type="codex")
                    readback = contextforge_helper_mcp.project_state_readback(str(root), client_type="codex")

                self.assertEqual(expected_projection, availability["project_services"][0]["target_client_projection_status"])
                self.assertEqual(expected_available, availability["project_services"][0]["available_to_target_client"])
                self.assertEqual(expected_projection, readback["target_client_services"][0]["target_client_projection_status"])
                self.assertEqual(expected_available, readback["target_client_services"][0]["available_to_target_client"])
                if expected_available:
                    self.assertEqual(["context7:canonical"], [item["service_binding"] for item in availability["available_tools"]])
                else:
                    self.assertEqual([], availability["available_tools"])

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
        self.assertEqual("reload_required", planned["project_init"]["client_states"]["opencode"]["status"])
        self.assertEqual("reload_required", planned["project_init"]["client_states"]["opencode"]["reload_status"])
        self.assertEqual(["context7:canonical", "github:canonical"], planned["project_init"]["client_states"]["opencode"]["selected_service_bindings"])
        self.assertNotIn("opencode", base_state["services"]["context7:canonical"]["target_clients"])
        self.assertNotIn("opencode", base_state["services"]["github:canonical"]["target_clients"])

    def test_alignment_import_continuation_turn_builds_opencode_approval_package(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp, tempfile.TemporaryDirectory() as run_tmp, mock.patch.object(
            contextforge_helper_mcp,
            "_contextforge_registry_service_offerings",
            return_value=[registry_service_descriptor("context7")],
        ):
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
        self.assertIn("plan ready for context7.", proposal["assistant_visible_response"].lower())
        self.assertNotIn("Plan ready for context7:canonical", proposal["assistant_visible_response"])
        self.assertIn("opencode.json", proposal["assistant_visible_response"])
        self.assertIn("Approve or decline?", proposal["assistant_visible_response"])
        self.assertIs(proposal["copy_as_complete_visible_response"], True)
        self.assertIs(proposal["do_not_summarize"], True)

    def test_alignment_import_offer_reports_unavailable_project_services_explicitly(self) -> None:
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
            state["services"]["github:canonical"]["provision_status"] = "failed"
            state["services"]["github:canonical"]["x_reason"] = "credential not configured"
            project_state.write_state_atomic(root, state)

            offer = helper.list_available_capabilities(project_root=root, client_type="opencode")

        self.assertEqual("alignment_import_offer", offer["status"])
        self.assertEqual(["context7:canonical"], offer["alignment_import_offer"]["project_service_bindings"])
        self.assertEqual(1, offer["alignment_import_offer"]["service_count"])
        self.assertEqual(1, offer["alignment_import_offer"]["unavailable_service_count"])
        self.assertEqual(
            [
                {
                    "service_binding": "github:canonical",
                    "status": "failed",
                    "reason": "credential not configured",
                    "alignment_status": "blocked",
                }
            ],
            offer["alignment_import_offer"]["unavailable_project_services"],
        )
        self.assertEqual(["context7:canonical"], [service["service_binding"] for service in offer["available_services"]])
        self.assertEqual(["context7:canonical", "none"], [choice["id"] for choice in offer["next_turn"]["choices"]])
        self.assertIn("Some project services cannot be imported", offer["assistant_visible_response"])
        self.assertIn("github:canonical: failed (credential not configured)", offer["assistant_visible_response"])
        self.assertIn("Import this project's existing ContextForge services for OpenCode?", offer["assistant_visible_response"])

    def test_alignment_import_offer_does_not_fall_back_to_generic_menu_when_all_project_services_unavailable(self) -> None:
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
            for binding_id, reason in {
                "context7:canonical": "server not running",
                "github:canonical": "credential not configured",
            }.items():
                state["services"][binding_id]["provision_status"] = "failed"
                state["services"][binding_id]["x_reason"] = reason
            project_state.write_state_atomic(root, state)

            offer = helper.list_available_capabilities(project_root=root, client_type="opencode")

        self.assertEqual("alignment_import_offer", offer["status"])
        self.assertEqual([], offer["available_services"])
        self.assertEqual([], offer["alignment_import_offer"]["project_service_bindings"])
        self.assertEqual([], offer["alignment_import_offer"]["missing_target_client_projection"])
        self.assertEqual(0, offer["alignment_import_offer"]["service_count"])
        self.assertEqual(2, offer["alignment_import_offer"]["unavailable_service_count"])
        self.assertEqual(
            {"context7:canonical", "github:canonical"},
            {item["service_binding"] for item in offer["alignment_import_offer"]["unavailable_project_services"]},
        )
        self.assertEqual("align-existing-project-services", offer["next_turn"]["question_id"])
        self.assertEqual(["none"], [choice["id"] for choice in offer["next_turn"]["choices"]])
        self.assertIn("already contains project services: context7:canonical, github:canonical", offer["assistant_visible_response"])
        self.assertIn("Importable or repairable target-client projections for OpenCode: none currently importable.", offer["assistant_visible_response"])
        self.assertIn("Some project services cannot be imported", offer["assistant_visible_response"])
        self.assertNotEqual("select-services", offer["next_turn"]["question_id"])

    def test_alignment_import_offer_represents_non_current_target_client_projection(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            selected = [service_descriptor("context7"), service_descriptor("github")]
            pi_plan = binding.plan_project_init_target_client_activation(root, selected, target_client="pi")
            state = project_state.apply_project_init_activation_to_state(
                project_state.default_state(root),
                selected,
                target_client="pi",
                client_config_plan=pi_plan,
                validation_plan=binding.build_project_init_validation_plan(selected, validation_mode="installed", target_client="pi"),
                validation_results={},
                consent_receipt_refs=CONSENT_REFS,
            )
            state["services"]["github:canonical"]["target_clients"]["opencode"] = {
                "client_type": "opencode",
                "status": "partial",
                "validation_status": "mixed",
                "reload_status": "not_required",
            }
            project_state.write_state_atomic(root, state)

            offer = helper.list_available_capabilities(project_root=root, client_type="opencode")

        self.assertEqual("alignment_import_offer", offer["status"])
        self.assertEqual(["context7:canonical", "github:canonical"], offer["alignment_import_offer"]["project_service_bindings"])
        self.assertEqual(
            ["context7:canonical", "github:canonical", "none"],
            [choice["id"] for choice in offer["next_turn"]["choices"]],
        )
        self.assertEqual(
            [{"action": "align_target_client_to_existing_project_service", "target_client": "opencode", "service_binding": "context7:canonical", "target_client_projection_status": "missing", "boundary": "Align/import opencode to the existing project service instance; do not create a new project service instance unless explicitly approved."}],
            offer["alignment_import_offer"]["missing_target_client_projection"],
        )
        self.assertEqual(
            [{"action": "align_target_client_to_existing_project_service", "target_client": "opencode", "service_binding": "github:canonical", "target_client_projection_status": "partial", "boundary": "Align/import opencode to the existing project service instance; do not create a new project service instance unless explicitly approved."}],
            offer["alignment_import_offer"]["non_current_target_client_projection"],
        )
        by_binding = {service["service_binding"]: service for service in offer["available_services"]}
        self.assertEqual("missing", by_binding["context7:canonical"]["target_client_projection_status"])
        self.assertEqual("partial", by_binding["github:canonical"]["target_client_projection_status"])
        self.assertEqual("Repair this project's existing github projection for opencode without provisioning a new project service instance.", by_binding["github:canonical"]["user_visible_effect"])

    def test_contextforge_helper_mcp_reports_project_capability_summary_read_only(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp, mock.patch.object(
            contextforge_helper_mcp,
            "_contextforge_registry_service_offerings",
            return_value=[
                registry_service_descriptor(
                    "exa-search",
                    binding="exa-search:credential_scoped",
                    instantiation_class="credential_scoped",
                )
            ],
        ):
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

        self.assertEqual([], full_report["available_now"])
        self.assertEqual("context7:canonical", full_report["project_services"][0]["service_binding"])
        self.assertEqual("reload_required", full_report["project_services"][0]["target_client_projection_status"])
        self.assertFalse(full_report["project_services"][0]["available_to_target_client"])
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
        self.assertTrue(visible.startswith("ContextForge capability summary\n\nSource\n"))
        self.assertIn("Configured in current project state for opencode\n- none reported", visible)
        self.assertIn("Project services\n- context7:canonical", visible)
        self.assertIn("Known but unavailable\n- web-search:credential_scoped", visible)
        self.assertIn("Available to enable or repair\n- exa-search", visible)
        self.assertIn("Client/session boundary\n- After approved OpenCode project-local MCP config changes", visible)
        self.assertIn("context7:canonical", visible)
        self.assertIn("web-search:credential_scoped", visible)
        self.assertIn("no arbitrary service onboarding", result["non_actions"])

    def test_project_capability_summary_uses_registry_catalog_not_local_manifests(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp, mock.patch.object(
            contextforge_helper_mcp,
            "_contextforge_registry_service_offerings",
            return_value=[registry_service_descriptor("context7")],
        ), mock.patch.object(
            contextforge_helper_mcp.common,
            "discover_contextforge_hosted_services",
            side_effect=AssertionError("capability summary must not use manifest-backed product discovery"),
        ):
            result = contextforge_helper_mcp.project_capability_summary(str(Path(tmp).resolve()), client_type="pi")

        self.assertTrue(result["ok"], result)
        self.assertEqual(["context7"], [item["capability"] for item in result["onboarding_needed"]])

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
        self.assertEqual([], full_report["imported_tools"])
        self.assertEqual(["context7-local-resolve-library-id", "context7-local-query-docs"], full_report["project_tool_policies"][0]["tool_policy_names"])
        self.assertEqual("reload_required", full_report["target_client_services"][0]["target_client_projection_status"])
        self.assertFalse(full_report["target_client_services"][0]["available_to_target_client"])
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
        self.assertTrue(visible.startswith("ContextForge project state\n\nProject\n"))
        self.assertIn("- Revision: 1", visible)
        self.assertIn("context7:canonical", visible)
        self.assertIn("Configured/imported tools for this client", visible)
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

            approval_source.write_text(json.dumps({"cwd": str(root), "text": "do not approve this plan"}) + "\n", encoding="utf-8")
            with mock.patch.dict(os.environ, guarded_env):
                negated_denied = contextforge_helper_mcp.cf_project_init_approve(
                    str(root),
                    challenge["challenge_id"],
                    challenge["plan_digest"],
                )

            self.assertFalse(negated_denied["ok"])
            self.assertEqual("PermissionError", negated_denied["error"]["type"])

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
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp, tempfile.TemporaryDirectory() as run_tmp, mock.patch.object(
            contextforge_helper_mcp,
            "_contextforge_registry_service_offerings",
            return_value=[registry_service_descriptor("context7")],
        ):
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
            self.assertEqual(["context7:canonical"], proposal["selected_service_bindings"])
            self.assertIn("plan ready for context7.", proposal["assistant_visible_response"].lower())
            self.assertNotIn("context7:canonical", proposal["assistant_visible_response"])
            self.assertIn("Approve or decline?", proposal["assistant_visible_response"])

    def test_opencode_continue_accepts_natural_service_selection(self) -> None:
        registry_offerings = [
            registry_service_descriptor("context7"),
            registry_service_descriptor("mentality", binding="mentality:static_repo_local", instantiation_class="static_repo_local"),
            registry_service_descriptor("ssh-tmux", binding="ssh-tmux:session_scoped", instantiation_class="session_scoped"),
        ]
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp, tempfile.TemporaryDirectory() as run_tmp, mock.patch.object(
            contextforge_helper_mcp,
            "_contextforge_registry_service_offerings",
            return_value=registry_offerings,
        ):
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
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp, tempfile.TemporaryDirectory() as run_tmp, mock.patch.object(
            contextforge_helper_mcp,
            "_contextforge_registry_service_offerings",
            return_value=[registry_service_descriptor("context7")],
        ):
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
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp, tempfile.TemporaryDirectory() as run_tmp, mock.patch.object(
            contextforge_helper_mcp,
            "_contextforge_registry_service_offerings",
            return_value=[registry_service_descriptor("context7"), registry_service_descriptor("serena")],
        ):
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
        registry_offerings = [
            registry_service_descriptor("context7"),
            registry_service_descriptor("exa-search", binding="exa-search:credential_scoped", instantiation_class="credential_scoped"),
            registry_service_descriptor("github", binding="github:credential_scoped", instantiation_class="credential_scoped"),
            registry_service_descriptor("mentality", binding="mentality:static_repo_local", instantiation_class="static_repo_local"),
            registry_service_descriptor("playwright"),
            registry_service_descriptor("ssh-tmux", binding="ssh-tmux:session_scoped", instantiation_class="session_scoped"),
            registry_service_descriptor("web-search", binding="web-search:credential_scoped", instantiation_class="credential_scoped"),
            registry_service_descriptor("serena"),
        ]
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp, tempfile.TemporaryDirectory() as run_tmp, mock.patch.object(
            contextforge_helper_mcp,
            "_contextforge_registry_service_offerings",
            return_value=registry_offerings,
        ):
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
            self.assertEqual(8, len(proposal["selected_service_bindings"]))
            self.assertNotIn("time:canonical", proposal["selected_service_bindings"])
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

        self.assertIn("Plan ready for context7.", public["assistant_visible_response"])
        self.assertNotIn("context7:canonical", public["assistant_visible_response"])
        self.assertIn("serena:abc123 language=python", public["assistant_visible_response"])
        self.assertNotIn("next_turn", public)

    def test_contextforge_helper_install_guidance_stops_after_reload_instruction(self) -> None:
        plan_doc = (
            REPO_ROOT / "docs/initiatives/contextforge-control-plane/contextforge-helper-project-init-plan.md"
        ).read_text(encoding="utf-8")

        self.assertIn("selected ContextForge tools are installed", plan_doc)
        self.assertIn("new session or reload", plan_doc)
        self.assertIn("Stop there", plan_doc)
        self.assertIn("Reload state is a three-value contract", plan_doc)
        self.assertIn("not_required", plan_doc)
        self.assertIn("reload_required", plan_doc)
        self.assertIn("tools_registered_observed", plan_doc)
        self.assertIn("Only this state can support claims", plan_doc)
        self.assertIn("No user acknowledgement is required or recorded", plan_doc)
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

    def test_contextforge_helper_mcp_apply_rejects_caller_supplied_receipt_replay_without_cached_receipts(self) -> None:
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

            contextforge_helper_mcp._CACHED_PLANS.clear()
            contextforge_helper_mcp._CACHED_RECEIPTS.clear()
            helper._APPROVED_RECEIPT_IDS_BY_PLAN.clear()
            contextforge_helper_mcp._write_durable_cache(str(root), {"plan": proposal})
            applied = contextforge_helper_mcp.cf_project_init_apply(str(root), receipts=approval["receipts"], dry_run=True)
            contextforge_helper_mcp._clear_durable_cache(str(root))

        self.assertTrue(proposal["ok"])
        self.assertTrue(approval["ok"])
        self.assertFalse(applied["ok"])
        self.assertEqual("ValueError", applied["error"]["type"])
        self.assertIn("cached project-init receipts", applied["error"]["message"])

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

    def test_service_management_list_uses_simple_status_surface(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp, mock.patch.object(
            contextforge_helper_mcp,
            "_contextforge_registry_service_offerings",
            return_value=[registry_service_descriptor("context7")],
        ):
            root = Path(tmp).resolve()
            result = contextforge_helper_mcp.service_management_list(str(root), client_type="pi")

        self.assertTrue(result["ok"])
        self.assertEqual("service_management_list", result["status"])
        self.assertEqual("Available", result["services"][0]["status"])
        self.assertEqual("context7", result["services"][0]["display_name"])
        self.assertIn("context7 - Available", result["assistant_visible_response"])
        self.assertNotIn("activation_class", result["assistant_visible_response"])
        self.assertNotIn("virtual server", result["assistant_visible_response"].lower())

    def test_service_management_list_does_not_use_manifest_discovery_as_product_truth(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp, mock.patch.object(
            contextforge_helper_mcp,
            "_contextforge_registry_service_offerings",
            return_value=[registry_service_descriptor("context7")],
        ), mock.patch.object(
            contextforge_helper_mcp.common,
            "discover_contextforge_hosted_services",
            side_effect=AssertionError("ordinary service menu must not read manifest-backed discovery"),
        ):
            root = Path(tmp).resolve()
            result = contextforge_helper_mcp.service_management_details(str(root), "context7", client_type="pi")

        self.assertTrue(result["ok"], result)
        self.assertEqual("service_management_details", result["status"])
        self.assertEqual("contextforge_registry", result["service"]["catalog_source"])

    def test_project_init_list_does_not_use_manifest_discovery_as_product_truth(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp, mock.patch.object(
            contextforge_helper_mcp,
            "_contextforge_registry_service_offerings",
            return_value=[registry_service_descriptor("context7")],
        ), mock.patch.object(
            contextforge_helper_mcp.common,
            "discover_contextforge_hosted_services",
            side_effect=AssertionError("project-init service menu must not read manifest-backed discovery"),
        ):
            root = Path(tmp).resolve()
            result = contextforge_helper_mcp.list_available_capabilities(str(root), client_type="pi")

        self.assertTrue(result["ok"], result)
        self.assertEqual("context7:canonical", result["available_services"][0]["service_binding"])
        self.assertIn("1. context7 - Available", result["assistant_visible_response"])

    def test_opencode_continue_initial_menu_uses_registry_offerings_only(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp, tempfile.TemporaryDirectory() as run_tmp, mock.patch.object(
            contextforge_helper_mcp,
            "_contextforge_registry_service_offerings",
            return_value=[registry_service_descriptor("context7")],
        ), mock.patch.object(
            contextforge_helper_mcp.common,
            "discover_contextforge_hosted_services",
            side_effect=AssertionError("project-init continuation menu must not read manifest-backed discovery"),
        ):
            root = Path(tmp).resolve()
            approval_source = Path(run_tmp) / "opencode-latest-user-message.json"
            approval_source.write_text(json.dumps({"cwd": str(root), "text": ""}) + "\n", encoding="utf-8")
            with mock.patch.dict(os.environ, {"CONTEXTFORGE_HELPER_APPROVAL_SOURCE_PATH": str(approval_source)}):
                result = contextforge_helper_mcp.cf_project_init_continue(str(root), client_type="opencode")

        self.assertTrue(result["ok"], result)
        self.assertEqual(["context7:canonical"], [item["service_binding"] for item in result["available_services"]])
        self.assertIn("1. context7 - Available", result["assistant_visible_response"])
        self.assertNotIn("time", result["assistant_visible_response"].lower())

    def test_opencode_continue_all_services_omits_manifest_only_services(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp, tempfile.TemporaryDirectory() as run_tmp, mock.patch.object(
            contextforge_helper_mcp,
            "_contextforge_registry_service_offerings",
            return_value=[registry_service_descriptor("context7"), registry_service_descriptor("github")],
        ), mock.patch.object(
            contextforge_helper_mcp.common,
            "discover_contextforge_hosted_services",
            side_effect=AssertionError("project-init continuation selection must not read manifest-backed discovery"),
        ):
            root = Path(tmp).resolve()
            approval_source = Path(run_tmp) / "opencode-latest-user-message.json"
            approval_source.write_text(json.dumps({"cwd": str(root), "text": "all services"}) + "\n", encoding="utf-8")
            with mock.patch.dict(os.environ, {"CONTEXTFORGE_HELPER_APPROVAL_SOURCE_PATH": str(approval_source)}):
                result = contextforge_helper_mcp.cf_project_init_continue(str(root), client_type="opencode")

        self.assertTrue(result["ok"], result)
        self.assertEqual(["context7:canonical", "github:canonical"], result["selected_service_bindings"])
        self.assertNotIn("time:canonical", result["selected_service_bindings"])

    def test_service_management_list_numbers_visible_service_choices(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp, mock.patch.object(
            contextforge_helper_mcp,
            "_contextforge_registry_service_offerings",
            return_value=[registry_service_descriptor("context7"), registry_service_descriptor("github")],
        ):
            root = Path(tmp).resolve()
            result = contextforge_helper_mcp.service_management_list(str(root), client_type="opencode")

        self.assertTrue(result["ok"], result)
        self.assertIn("1. context7 - Available", result["assistant_visible_response"])
        self.assertIn("2. github - Available", result["assistant_visible_response"])
        self.assertIn("Reply with service names or numbers", result["assistant_visible_response"])

    def test_service_management_list_does_not_resurrect_state_only_services(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp, mock.patch.object(
            contextforge_helper_mcp,
            "_contextforge_registry_service_offerings",
            return_value=[],
        ):
            root = Path(tmp).resolve()
            state = project_state.default_state(root, status="initialized")
            service = service_descriptor("context7")
            config_plan = binding.plan_project_init_codex_config_write(root, [service], existing_text="")
            validation_plan = binding.build_project_init_validation_plan([service], validation_mode="presume_working")
            state = project_state.apply_project_init_activation_to_state(
                state,
                [service],
                target_client="pi",
                client_config_plan=config_plan,
                validation_plan=validation_plan,
                consent_receipt_refs=CONSENT_REFS,
            )
            project_state.write_state_atomic(root, state, updated_by="test")
            result = contextforge_helper_mcp.service_management_list(str(root), client_type="pi")

        self.assertTrue(result["ok"], result)
        self.assertEqual([], result["services"])
        self.assertIn("No ContextForge services are available.", result["assistant_visible_response"])

    def test_service_management_list_reports_catalog_unavailable_without_empty_catalog_claim(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp, mock.patch.object(
            contextforge_helper_mcp,
            "_contextforge_registry_service_offerings",
            side_effect=contextforge_helper_mcp.ContextForgeCatalogUnavailable("http://host.docker.internal:4445", "HTTP 401 Unauthorized"),
        ):
            root = Path(tmp).resolve()
            result = contextforge_helper_mcp.service_management_list(str(root), client_type="pi")

        self.assertFalse(result["ok"], result)
        self.assertEqual("contextforge_catalog_unavailable", result["status"])
        self.assertEqual([], result["services"])
        self.assertIn("service catalog unavailable", result["assistant_visible_response"])
        self.assertIn("No project files or service configuration were changed.", result["assistant_visible_response"])
        self.assertNotIn("No ContextForge services are available.", result["assistant_visible_response"])

    def test_service_management_enable_reports_catalog_unavailable_before_service_lookup(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp, mock.patch.object(
            contextforge_helper_mcp,
            "_contextforge_registry_service_offerings",
            side_effect=contextforge_helper_mcp.ContextForgeCatalogUnavailable("http://host.docker.internal:4445", "HTTP 401 Unauthorized"),
        ):
            root = Path(tmp).resolve()
            result = contextforge_helper_mcp.service_management_enable(str(root), "context7", client_type="opencode", confirm=True)

        self.assertFalse(result["ok"], result)
        self.assertEqual("contextforge_catalog_unavailable", result["status"])
        self.assertNotIn("unknown ContextForge service", result["assistant_visible_response"])

    def test_every_catalog_reading_helper_boundary_returns_visible_unavailable_outcome(self) -> None:
        unavailable = contextforge_helper_mcp.ContextForgeCatalogUnavailable(
            "http://host.docker.internal:4445",
            "HTTP 401 Unauthorized",
        )
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp, mock.patch.object(
            contextforge_helper_mcp,
            "_contextforge_registry_service_offerings",
            side_effect=unavailable,
        ):
            root = Path(tmp).resolve()
            calls = {
                "capability_summary": lambda: contextforge_helper_mcp.project_capability_summary(
                    str(root),
                    client_type="opencode",
                ),
                "public_capability_summary": lambda: contextforge_helper_mcp.get_project_capability_summary(
                    str(root),
                    client_type="opencode",
                ),
                "project_init_list": lambda: contextforge_helper_mcp.list_available_capabilities(
                    str(root),
                    client_type="opencode",
                ),
                "project_init_continue": lambda: contextforge_helper_mcp.cf_project_init_continue(
                    str(root),
                    client_type="opencode",
                ),
            }
            for boundary, call in calls.items():
                with self.subTest(boundary=boundary):
                    result = call()
                    self.assertFalse(result["ok"], result)
                    self.assertEqual("contextforge_catalog_unavailable", result["status"])
                    self.assertEqual(
                        result["assistant_visible_response"],
                        result["message"],
                    )
                    self.assertTrue(result["copy_as_complete_visible_response"])
                    self.assertTrue(result["do_not_summarize"])
                    self.assertIn("service catalog unavailable", result["assistant_visible_response"])
                    self.assertNotIn("ContextForgeCatalogUnavailable", result["assistant_visible_response"])

            self.assertEqual([], list(root.iterdir()))

    def test_helper_catalog_collections_fail_visibly_on_malformed_api_shapes(self) -> None:
        request_type_error = object()
        malformed_detail = object()
        cases = [
            ("null", None),
            ("string", "wrong"),
            ("integer", 7),
            ("nan", float("nan")),
            ("empty_object", {}),
            ("null_items", {"items": None}),
            ("string_items", {"items": "wrong"}),
            ("non_object_item", {"items": [None]}),
            ("request_type_error", request_type_error),
            ("malformed_resource_detail", malformed_detail),
        ]
        with tempfile.NamedTemporaryFile("w", dir=REPO_ROOT, delete=False) as env_file:
            env_file.write("CONTEXTFORGE_BEARER_TOKEN=redacted-test-token\n")
            env_path = Path(env_file.name)
        try:
            for label, malformed in cases:
                with self.subTest(label=label), tempfile.TemporaryDirectory(
                    dir=project_state.WORKSPACE_ROOT
                ) as tmp:
                    root = Path(tmp).resolve()
                    contextforge_helper_mcp._CONTEXTFORGE_READBACK_CACHE.clear()

                    def fake_request(base_url: str, path: str, token: str) -> Any:
                        self.assertEqual("http://cf.example", base_url)
                        self.assertEqual("catalog-token", token)
                        if path.startswith("/resources?"):
                            if malformed is request_type_error:
                                raise TypeError("synthetic collection decoder failure")
                            if malformed is malformed_detail:
                                return {
                                    "items": [
                                        {
                                            "id": "resource-context7-offering",
                                            "uri": "contextforge://control-plane/service-offerings/context7/v1",
                                            "tags": ["contextforge-service-offering"],
                                        }
                                    ]
                                }
                            return malformed
                        if path == "/resources/resource-context7-offering":
                            return None
                        if path.startswith("/servers?") or path.startswith("/gateways?"):
                            return {"items": []}
                        raise AssertionError(path)

                    with mock.patch.object(
                        contextforge_helper_mcp,
                        "_contextforge_env_path",
                        return_value=env_path,
                    ), mock.patch.object(
                        contextforge_helper_mcp,
                        "_contextforge_base_url",
                        return_value="http://cf.example",
                    ), mock.patch(
                        "contextforge_mcp_wrapper._read_env",
                        return_value={"CONTEXTFORGE_BEARER_TOKEN": "redacted-test-token"},
                    ), mock.patch(
                        "contextforge_mcp_wrapper._token",
                        return_value="catalog-token",
                    ), mock.patch.object(
                        contextforge_helper_mcp,
                        "_contextforge_request",
                        side_effect=fake_request,
                    ), mock.patch.dict(
                        os.environ,
                        {"CONTEXTFORGE_HELPER_CATALOG_CACHE_SECONDS": "0"},
                        clear=False,
                    ):
                        result = contextforge_helper_mcp.service_management_list(
                            str(root),
                            client_type="opencode",
                        )

                    self.assertFalse(result["ok"], result)
                    self.assertEqual("contextforge_catalog_unavailable", result["status"])
                    self.assertEqual([], result["services"])
                    self.assertIn("service catalog unavailable", result["assistant_visible_response"])
                    self.assertNotIn("No ContextForge services are available", result["assistant_visible_response"])
                    self.assertEqual([], list(root.iterdir()))
        finally:
            env_path.unlink(missing_ok=True)

    def test_live_registry_readback_fetches_full_service_offering_resource_content(self) -> None:
        with tempfile.NamedTemporaryFile("w", dir=REPO_ROOT, delete=False) as env_file:
            env_file.write("CONTEXTFORGE_BEARER_TOKEN=redacted-test-token\n")
            env_path = Path(env_file.name)
        calls: list[str] = []

        def fake_request(base_url: str, path: str, token: str) -> Any:
            self.assertEqual("http://cf.example", base_url)
            self.assertEqual("token", token)
            calls.append(path)
            if path.startswith("/servers?"):
                return {"items": []}
            if path.startswith("/gateways?"):
                return {"items": []}
            if path.startswith("/resources?"):
                return {
                    "items": [
                        {
                            "id": "resource-context7-offering",
                            "uri": "contextforge://control-plane/service-offerings/context7/v1",
                            "tags": ["contextforge-service-offering"],
                        },
                        {"id": "ordinary-resource", "tags": ["service-guidance"]},
                    ]
                }
            if path == "/resources/resource-context7-offering":
                return {
                    "id": "resource-context7-offering",
                    "uri": "contextforge://control-plane/service-offerings/context7/v1",
                    "tags": ["contextforge-service-offering"],
                    "content": json.dumps(service_offering_metadata()),
                }
            raise AssertionError(path)

        try:
            with mock.patch.dict(
                os.environ,
                {"CONTEXTFORGE_CONFIG_ENV": str(env_path), "CONTEXTFORGE_BASE_URL": "http://cf.example"},
                clear=False,
            ), mock.patch("contextforge_mcp_wrapper._read_env", return_value={"CONTEXTFORGE_BEARER_TOKEN": "redacted-test-token"}), mock.patch(
                "contextforge_mcp_wrapper._token", return_value="token"
            ), mock.patch.object(contextforge_helper_mcp, "_contextforge_request", side_effect=fake_request):
                readback = contextforge_helper_mcp._live_contextforge_registry_readback()
        finally:
            env_path.unlink(missing_ok=True)

        self.assertIn("/resources/resource-context7-offering", calls)
        service_resources = [
            resource for resource in readback["resources"] if resource.get("id") == "resource-context7-offering"
        ]
        self.assertEqual(1, len(service_resources))
        self.assertIn("content", service_resources[0])

    def test_service_management_enable_confirm_applies_project_state(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp, mock.patch.object(
            contextforge_helper_mcp,
            "_contextforge_registry_service_offerings",
            return_value=[registry_service_descriptor("context7")],
        ), mock.patch.object(
            contextforge_helper_mcp.common,
            "discover_contextforge_hosted_services",
            side_effect=AssertionError("service-management enable must use CF metadata descriptor, not local manifest discovery"),
        ):
            root = Path(tmp).resolve()
            result = contextforge_helper_mcp.service_management_enable(
                str(root),
                "context7",
                client_type="opencode",
                confirm=True,
            )
            state = project_state.load_state(root)

        self.assertTrue(result["ok"], result)
        self.assertEqual("enabled", result["status"])
        self.assertIn("context7 is Enabled", result["assistant_visible_response"])
        self.assertIn("context7:canonical", state["services"])
        self.assertEqual("reload_required", state["project_init"]["client_states"]["opencode"]["reload_status"])

    def test_service_management_repair_enables_available_service(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp, mock.patch.object(
            contextforge_helper_mcp,
            "_contextforge_registry_service_offerings",
            return_value=[registry_service_descriptor("context7")],
        ), mock.patch.object(
            contextforge_helper_mcp.common,
            "discover_contextforge_hosted_services",
            return_value=[service_descriptor("context7")],
        ):
            root = Path(tmp).resolve()
            result = contextforge_helper_mcp.service_management_repair(
                str(root),
                "context7",
                client_type="opencode",
                confirm=True,
            )

        self.assertTrue(result["ok"], result)
        self.assertEqual("enabled", result["status"])

    def test_service_management_disable_removes_owned_opencode_exposure_and_preserves_state(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp, mock.patch.object(
            contextforge_helper_mcp,
            "_contextforge_registry_service_offerings",
            return_value=[registry_service_descriptor("context7")],
        ), mock.patch.object(
            contextforge_helper_mcp.common,
            "discover_contextforge_hosted_services",
            return_value=[service_descriptor("context7")],
        ):
            root = Path(tmp).resolve()
            enabled = contextforge_helper_mcp.service_management_enable(
                str(root),
                "context7",
                client_type="opencode",
                confirm=True,
            )
            self.assertTrue(enabled["ok"], enabled)
            self.assertIn("context7", json.loads((root / "opencode.json").read_text(encoding="utf-8"))["mcp"])

            disabled = contextforge_helper_mcp.service_management_disable(
                str(root),
                "context7",
                client_type="opencode",
                confirm=True,
            )
            config = json.loads((root / "opencode.json").read_text(encoding="utf-8"))
            state = project_state.load_state(root)
            listed = contextforge_helper_mcp.service_management_list(str(root), client_type="opencode")

        self.assertTrue(disabled["ok"], disabled)
        self.assertEqual("disabled", disabled["status"])
        self.assertNotIn("context7", config.get("mcp", {}))
        self.assertIn("context7:canonical", state["services"])
        self.assertEqual("disabled", state["decisions"]["context7:canonical"]["state"])
        self.assertEqual("Disabled", listed["services"][0]["status"])

    def test_service_management_remove_removes_owned_opencode_exposure_and_project_state(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp, mock.patch.object(
            contextforge_helper_mcp,
            "_contextforge_registry_service_offerings",
            return_value=[registry_service_descriptor("context7")],
        ), mock.patch.object(
            contextforge_helper_mcp.common,
            "discover_contextforge_hosted_services",
            return_value=[service_descriptor("context7")],
        ):
            root = Path(tmp).resolve()
            enabled = contextforge_helper_mcp.service_management_enable(
                str(root),
                "context7",
                client_type="opencode",
                confirm=True,
            )
            self.assertTrue(enabled["ok"], enabled)
            self.assertIn("context7", json.loads((root / "opencode.json").read_text(encoding="utf-8"))["mcp"])

            removed = contextforge_helper_mcp.service_management_remove(
                str(root),
                "context7",
                client_type="opencode",
                confirmation="context7",
            )
            config = json.loads((root / "opencode.json").read_text(encoding="utf-8"))
            state = project_state.load_state(root)

        self.assertTrue(removed["ok"], removed)
        self.assertEqual("removed_from_project", removed["status"])
        self.assertNotIn("context7", config.get("mcp", {}))
        self.assertNotIn("context7:canonical", state["services"])
        self.assertNotIn("context7:canonical", state["decisions"])

    def test_service_management_remove_requires_typed_service_name(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp, mock.patch.object(
            contextforge_helper_mcp,
            "_contextforge_registry_service_offerings",
            return_value=[registry_service_descriptor("context7")],
        ) as _catalog:
            root = Path(tmp).resolve()
            state = project_state.default_state(root, status="initialized")
            state["services"]["context7:canonical"] = service_descriptor("context7")
            with mock.patch.object(contextforge_helper_mcp.project_state, "read_or_default", return_value=state):
                preview = contextforge_helper_mcp.service_management_remove(str(root), "context7", client_type="pi")
                removed = contextforge_helper_mcp.service_management_remove(
                    str(root),
                    "context7",
                    client_type="pi",
                    confirmation="context7",
                    dry_run=True,
                )

        self.assertTrue(preview["ok"])
        self.assertEqual("remove_confirmation_required", preview["status"])
        self.assertIn('Type "context7" to confirm', preview["assistant_visible_response"])
        self.assertTrue(removed["ok"])
        self.assertEqual("removed_from_project", removed["status"])
        self.assertTrue(removed["dry_run"])

    def test_service_management_remove_rejects_available_service(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp, mock.patch.object(
            contextforge_helper_mcp,
            "_contextforge_registry_service_offerings",
            return_value=[registry_service_descriptor("context7")],
        ):
            root = Path(tmp).resolve()
            result = contextforge_helper_mcp.service_management_remove(
                str(root),
                "context7",
                client_type="pi",
                confirmation="context7",
                dry_run=True,
            )

        self.assertFalse(result["ok"])
        self.assertEqual("not_enabled", result["status"])

    def test_public_plan_message_uses_display_names_not_service_bindings(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            proposal = contextforge_helper_mcp.propose_project_init(
                str(root),
                ["context7:canonical"],
                client_type="opencode",
            )
            public = contextforge_helper_mcp.client_visible_project_init_plan_payload(proposal)

        self.assertIn("Plan ready for context7.", public["message"])
        self.assertNotIn("context7:canonical", public["message"])

    def test_contextforge_helper_registers_known_service_management_tools(self) -> None:
        source = (REPO_ROOT / "scripts/contextforge_helper_mcp.py").read_text(encoding="utf-8")

        for name in [
            "cf_project_service_list",
            "cf_project_service_status",
            "cf_project_service_details",
            "cf_project_service_enable",
            "cf_project_service_disable",
            "cf_project_service_remove",
            "cf_project_service_repair",
        ]:
            self.assertIn(f"def {name}", source)
        self.assertNotIn("@server.tool()\ndef cf_project_service_onboarding", source)

    def test_pi_cli_exposes_known_service_management_operations(self) -> None:
        source = (REPO_ROOT / "scripts/pi_project_init_helper_cli.py").read_text(encoding="utf-8")

        for operation in [
            "service_list",
            "service_status",
            "service_details",
            "service_enable",
            "service_disable",
            "service_remove",
            "service_repair",
        ]:
            self.assertIn(operation, source)

    def test_project_init_prompt_is_not_serena_only_and_preserves_approval_boundaries(self) -> None:
        text = prompt_registration.PROJECT_INIT_TEXT

        self.assertIn("Which ContextForge services should I enable for this project?", text)
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
