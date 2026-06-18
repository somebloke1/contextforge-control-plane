from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import inventory_mcp


class InventoryMcpTests(unittest.TestCase):
    def test_client_config_entry_is_discovery_only_with_dedupe_hints(self) -> None:
        entry = inventory_mcp.inventory_entry(
            "codex-project",
            Path("/tmp/project/.codex/config.toml"),
            "codex_context7_alias",
            {
                "command": "npx",
                "args": ["-y", "@upstash/context7-mcp@latest"],
                "env": {"CONTEXT7_API_KEY": "plain-test-value"},
            },
            ("mcp_servers",),
        )

        self.assertEqual("client_config_entry", entry["discovery"]["role"])
        self.assertEqual("client_config_alias", entry["discovery"]["name_role"])
        self.assertEqual(
            "contextforge_catalog_or_instance_manifest",
            entry["discovery"]["identity_authority"],
        )
        self.assertEqual("requires_service_management_classification", entry["dedupe_hints"]["dedupe_status"])
        self.assertEqual("command", entry["dedupe_hints"]["backend_kind"])
        self.assertEqual("npx", entry["dedupe_hints"]["backend_hint"])
        self.assertIn("catalog_promotion", entry["discovery"]["forbidden_effects"])
        self.assertNotIn("canonical_service", entry)
        self.assertNotIn("service_binding", entry)
        self.assertEqual("<redacted>", entry["config"]["env"]["CONTEXT7_API_KEY"])

    def test_dedupe_backend_hint_redacts_secret_like_values(self) -> None:
        entry = inventory_mcp.inventory_entry(
            "opencode-project",
            Path("/tmp/project/opencode.json"),
            "private_docs",
            {"url": "https://example.invalid/mcp?api_key=plain-test-value"},
            ("mcp",),
        )

        self.assertEqual("url", entry["dedupe_hints"]["backend_kind"])
        self.assertEqual("<redacted>", entry["dedupe_hints"]["backend_hint"])
        self.assertEqual("<redacted>", entry["config"]["url"])

    def test_pi_package_entry_remains_assistant_package_evidence(self) -> None:
        entry = inventory_mcp.pi_package_entry(
            "pi-coding-assistant",
            Path("/tmp/project/.pi/settings.json"),
            "npm:pi-web-access",
            ("extensions", "packages"),
        )

        self.assertEqual("assistant_package_entry", entry["discovery"]["role"])
        self.assertEqual("assistant_package", entry["dedupe_hints"]["backend_kind"])
        self.assertEqual("pi-web-access", entry["dedupe_hints"]["backend_hint"])
        self.assertEqual("discovered_only", entry["discovery"]["candidate_status"])
        self.assertNotIn("canonical_service", entry)
        self.assertNotIn("service_binding", entry)

    def test_add_entries_from_config_marks_config_aliases_without_promoting(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mcp.json"
            path.write_text(
                json.dumps(
                    {
                        "mcpServers": {
                            "invoiceapi": {
                                "url": "https://example.invalid/mcp",
                                "headers": {"Authorization": "Bearer plain-test-value"},
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            entries: list[dict[str, object]] = []
            source = inventory_mcp.source_record("claude-code-project", path, exists=True)

            inventory_mcp.add_entries_from_config(entries, source, "claude-code-project", path)

        self.assertEqual(1, len(entries))
        entry = entries[0]
        self.assertEqual("invoiceapi", entry["name"])
        self.assertEqual("streamable_http", entry["transport"])
        self.assertEqual("url", entry["dedupe_hints"]["backend_kind"])
        self.assertEqual("https://example.invalid/mcp", entry["dedupe_hints"]["backend_hint"])
        self.assertEqual("<redacted>", entry["config"]["headers"]["Authorization"])
        self.assertEqual("client_config_source", source["discovery_role"])
        self.assertIn("registry_mutation", source["forbidden_effects"])

    def test_discover_output_includes_inventory_contract_and_no_canonicalized_entries(self) -> None:
        with mock.patch.object(inventory_mcp, "CONFIG_CANDIDATES", []), mock.patch.object(
            inventory_mcp, "workspace_config_paths", return_value=[]
        ), mock.patch.object(inventory_mcp, "workspace_source_hints", return_value=[]):
            result = inventory_mcp.discover()

        self.assertEqual("read_only_discovery_evidence", result["inventory_contract"]["role"])
        self.assertEqual(
            "aliases_or_consumption_surfaces_not_service_identities",
            result["inventory_contract"]["client_config_names_are"],
        )
        self.assertIn("catalog_promotion", result["inventory_contract"]["forbidden_effects"])
        self.assertEqual(1, len(result["entries"]))
        entry = result["entries"][0]
        self.assertEqual("static_repo_local_source", entry["discovery"]["role"])
        self.assertNotIn("canonical_service", entry)
        self.assertNotIn("service_binding", entry)


if __name__ == "__main__":
    unittest.main()
