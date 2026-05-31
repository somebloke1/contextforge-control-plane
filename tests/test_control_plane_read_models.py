from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import control_plane_contracts as contracts
import control_plane_project_state as state_lib
import control_plane_read_models as read_models


DIGEST = "sha256:" + "a" * 64
STAMP = "2026-05-30T21:00:00Z"


def snapshot_ref(name: str) -> dict[str, object]:
    return {
        "ref": f"contextforge://control-plane/{name}/v1",
        "content_digest": DIGEST,
        "catalog_revision_or_etag": "rev-1",
        "resolved_at": STAMP,
    }


def open_item(item_id: str, item_type: str = "verification") -> dict[str, object]:
    return {
        "id": item_id,
        "type": item_type,
        "severity": "blocking",
        "blocks_initialized": True,
        "resource": "service:serena",
        "created_at": STAMP,
        "resolution_state": "open",
        "detail": {"reason": "test gap"},
    }


def service_record() -> dict[str, object]:
    return {
        "service_family": "serena",
        "service_binding": "serena:project-root",
        "instantiation_class": "instance_per_project",
        "contract_card_ref": "contextforge://control-plane/service-bindings/serena/v1",
        "capability_capsule_ref": None,
        "semantic_tool_policy_ref": "contextforge://control-plane/tool-policies/serena/v1",
        "backend_instance": "server-instances/serena-test",
        "virtual_server": "serena_test_server",
        "provision_status": "failed",
        "lifecycle": {},
        "language_profile": None,
        "required_verification_layers": ["backend", "target_client"],
        "verification_layers": {"backend": {"status": "failed"}},
        "target_clients": {"codex": {"enabled": True}},
        "verification_trace_refs": [],
        "consent_receipt_refs": [],
        "evidence": [],
    }


def manifest(
    name: str = "context7",
    *,
    service: str | None = None,
    registration_status: str = "registered",
    requires_scope: bool = False,
    project_root: str | None = None,
) -> dict[str, object]:
    return {
        "name": name,
        "service": service,
        "slug": name.replace("_", "-"),
        "client": "codex",
        "kind": "mcp",
        "enabled": True,
        "scope": {
            "requires_local_project_scope": requires_scope,
            "scope_type": "single_workspace_code_intelligence" if requires_scope else "global_documentation_lookup",
            "workspace_root": project_root,
        },
        "backend": {
            "transport": "stdio",
            "command": "npx",
            "args": ["-y", "@upstash/context7-mcp@latest"],
            "env": {
                "CONTEXT7_API_KEY": "ctx-secret-test-value",
                "SAFE_VALUE": "plain",
            },
            "env_vars": ["CONTEXT7_API_KEY"],
        },
        "bridge": {"needed": True, "streamable_http_url": "http://127.0.0.1:9103/mcp"},
        "contextforge": {
            "gateway": {"name": f"{name}-gateway"},
            "virtual_server": {"name": f"{name}_server"},
        },
        "registration": {
            "status": registration_status,
            "registered_tools": [f"{name}-tool"],
        },
        "contract_card_ref": f"contextforge://control-plane/service-bindings/{name}/v1",
        "capability_capsule_ref": f"contextforge://control-plane/capabilities/{name}/v1",
        "semantic_tool_policy_ref": f"contextforge://control-plane/tool-policies/{name}/v1",
    }


class ControlPlaneReadModelTests(unittest.TestCase):
    def workspace_project(self) -> tempfile.TemporaryDirectory[str]:
        return tempfile.TemporaryDirectory(dir=state_lib.WORKSPACE_ROOT)

    def test_get_project_context_missing_state_does_not_write_default(self) -> None:
        with self.workspace_project() as tmp:
            root = Path(tmp).resolve()
            state_path = state_lib.project_state_path(root)
            self.assertFalse(state_path.exists())

            view = read_models.get_project_context(root)

            self.assertFalse(view["state_present"])
            self.assertEqual("UNINITIALIZED", view["state_status"])
            self.assertIsNone(view["state"])
            self.assertFalse(state_path.exists())

    def test_get_project_context_rejects_unsafe_root(self) -> None:
        with self.assertRaises(state_lib.RootValidationError):
            read_models.get_project_context("/")

    def test_list_catalog_uses_manifest_identity_not_client_config_alias(self) -> None:
        catalog = {
            "services": [manifest("context7")],
            "client_config_entries": [{"name": "codex_context7_alias", "command": "npx"}],
        }

        view = read_models.list_catalog(catalog=catalog)

        service_names = {item["canonical_service"] for item in view["services"]}
        self.assertEqual({"context7"}, service_names)
        self.assertNotIn("codex_context7_alias", service_names)
        self.assertEqual("instance_manifest", view["services"][0]["identity_source"])
        self.assertEqual("context7_server", view["services"][0]["canonical_virtual_server"])

    def test_list_catalog_redacts_secret_like_fields_and_values(self) -> None:
        catalog = {
            "services": [manifest("context7")],
            "client_config_entries": [{"headers": {"Authorization": "plain bearer placeholder"}}],
        }

        view = read_models.list_catalog(catalog=catalog)

        backend_env = view["services"][0]["backend"]["env"]
        self.assertEqual("<redacted>", backend_env["CONTEXT7_API_KEY"])
        self.assertEqual("plain", backend_env["SAFE_VALUE"])
        self.assertEqual("<redacted>", view["client_config_entries"][0]["headers"]["Authorization"])

    def test_project_context_includes_state_refs_open_items_and_targets(self) -> None:
        with self.workspace_project() as tmp:
            root = Path(tmp).resolve()
            state = state_lib.default_state(root)
            state["artifact_refs"]["contract_cards"].append(snapshot_ref("service-bindings/serena"))
            state["artifact_refs"]["capability_capsules"].append(snapshot_ref("capabilities/serena"))
            state["artifact_refs"]["semantic_tool_policies"].append(snapshot_ref("tool-policies/serena"))
            state["open_items"].append(open_item("verify-serena"))
            state["services"]["serena"] = service_record()

            view = read_models.get_project_context(root, state=state)

            self.assertEqual(["codex"], view["target_clients"])
            self.assertEqual("verify-serena", view["open_items"][0]["id"])
            self.assertEqual("contextforge://control-plane/service-bindings/serena/v1", view["contract_card_refs"][0]["ref"])
            self.assertEqual("serena:project-root", view["services"][0]["service_binding"])

    def test_available_capabilities_separates_shared_services_from_candidates(self) -> None:
        with self.workspace_project() as tmp:
            root = Path(tmp).resolve()
            catalog = {
                "services": [manifest("context7")],
                "candidates": [{"name": "invoiceapi", "evidence": "/tmp/project/.claude/settings.json"}],
            }

            view = read_models.list_available_capabilities(root, state=None, catalog=catalog)

            self.assertEqual(["context7"], [item["canonical_service"] for item in view["existing_shared_services"]])
            self.assertEqual(["invoiceapi"], [item["candidate_name"] for item in view["candidates"]])
            self.assertEqual("UNINITIALIZED", view["project"]["state_status"])

    def test_report_project_gaps_reports_missing_state(self) -> None:
        with self.workspace_project() as tmp:
            root = Path(tmp).resolve()
            state_path = state_lib.project_state_path(root)

            view = read_models.report_project_gaps(root, catalog={"services": [], "candidates": []})

            self.assertEqual("UNINITIALIZED", view["project"]["state_status"])
            self.assertIn("project_state_missing", {gap["type"] for gap in view["gaps"]})
            self.assertFalse(state_path.exists())

    def test_report_project_gaps_reports_unresolved_items_and_state_gaps(self) -> None:
        with self.workspace_project() as tmp:
            root = Path(tmp).resolve()
            state = state_lib.default_state(root, status="in_progress")
            state["open_items"].append(open_item("restart-required", "restart"))
            state["migration"]["legacy_env_disposition"] = "conflict"
            state["migration"]["legacy_env_seen"] = True
            state["migration"]["conflicts"].append({"reason": "conflicting_legacy_env"})
            state["client_trust"]["codex"] = {
                "state": "trusted_requires_restart",
                "root": str(root),
                "trust_surface": "codex",
                "approval_record": None,
                "verified_at": None,
                "last_probe": None,
            }
            state["services"]["serena"] = service_record()

            view = read_models.report_project_gaps(root, state=state, catalog={"services": [], "candidates": []})
            gap_types = {gap["type"] for gap in view["gaps"]}

            self.assertIn("migration", gap_types)
            self.assertIn("restart", gap_types)
            self.assertIn("service", gap_types)
            self.assertIn("trace_missing", gap_types)
            self.assertIn("consent_required", gap_types)
            self.assertIn("verification", gap_types)

    def test_report_project_gaps_reports_catalog_candidates(self) -> None:
        with self.workspace_project() as tmp:
            root = Path(tmp).resolve()
            state = state_lib.default_state(root)
            catalog = {"services": [], "candidates": [{"name": "invoiceapi", "api_key": "plain-test-value"}]}

            view = read_models.report_project_gaps(root, state=state, catalog=catalog)

            candidate_gaps = [gap for gap in view["gaps"] if gap["type"] == "catalog_candidate"]
            self.assertEqual(1, len(candidate_gaps))
            self.assertNotIn("api_key", candidate_gaps[0]["detail"])
            self.assertNotIn("plain-test-value", repr(view))

    def test_redacted_catalog_output_passes_existing_redaction_validator(self) -> None:
        view = read_models.list_catalog(catalog={"services": [manifest("context7")]})
        contracts.validate_redacted(view)


if __name__ == "__main__":
    unittest.main()
