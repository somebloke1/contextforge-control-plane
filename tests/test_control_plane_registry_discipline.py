from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
DISCIPLINE_DOC = REPO_ROOT / "docs" / "contextforge-registry-mutation-discipline.md"

import control_plane_registry_discipline as discipline


class RegistryMutationDisciplineTests(unittest.TestCase):
    def test_current_public_api_paths_are_allowed(self) -> None:
        for method, path in [
            ("GET", "/gateways?include_inactive=true&limit=1000"),
            ("POST", "/gateways"),
            ("PUT", "/gateways/gateway-1"),
            ("POST", "/gateways/gateway-1/tools/refresh"),
            ("GET", "/tools?include_inactive=true&limit=1000"),
            ("GET", "/servers?include_inactive=true&limit=1000"),
            ("POST", "/servers"),
            ("PUT", "/servers/server-1"),
            ("GET", "/resources?include_inactive=true&limit=1000"),
            ("POST", "/resources"),
            ("PUT", "/resources/resource-1"),
            ("GET", "/prompts?include_inactive=true&limit=1000"),
            ("POST", "/prompts"),
            ("PUT", "/prompts/prompt-1"),
        ]:
            with self.subTest(method=method, path=path):
                discipline.assert_public_contextforge_api_path(method, path)

    def test_direct_database_and_internal_paths_are_rejected(self) -> None:
        for method, path in [
            ("POST", "sqlite:///contextforge.db"),
            ("POST", "/database/registry"),
            ("PATCH", "/gateways/gateway-1"),
            ("PUT", "/admin/internal/gateways/gateway-1"),
            ("DELETE", "/servers/server-1"),
        ]:
            with self.subTest(method=method, path=path):
                with self.assertRaises(discipline.RegistryMutationDisciplineError):
                    discipline.assert_public_contextforge_api_path(method, path)

    def test_discipline_record_blocks_stored_id_authority(self) -> None:
        record = discipline.registry_mutation_discipline(
            owner="test",
            operations=[{"entity": "server", "operation": "upsert", "authority": "server name"}],
        )

        self.assertEqual("#140", record["issue"])
        self.assertFalse(record["direct_database_writes_allowed"])
        self.assertFalse(record["contextforge_internal_patches_allowed"])
        self.assertFalse(record["stored_ids_are_authority"])
        self.assertIn("server.name", record["canonical_authority_fields"])
        self.assertIn("direct_contextforge_database_write", record["forbidden_mutation_surfaces"])

    def test_documented_contract_names_helper_surfaces_and_non_actions(self) -> None:
        doc = DISCIPLINE_DOC.read_text(encoding="utf-8")

        for phrase in [
            "Issue: #140",
            "scripts/apply_contextforge_registry_recreation.py",
            "scripts/register_tool_guidance.py",
            "must not write the ContextForge database directly",
            "stored IDs as readback evidence and request targets",
            "does not approve live registry mutation",
            ".project/context_forge_state.json",
        ]:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, doc)


if __name__ == "__main__":
    unittest.main()
