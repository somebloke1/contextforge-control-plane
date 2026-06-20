import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = ROOT / "docs" / "contextforge-service-readiness-matrix.json"
TAXONOMY_CONTRACT_PATH = ROOT / "docs" / "contextforge-service-localization-taxonomy.json"


class ServiceReadinessMatrixTests(unittest.TestCase):
    def load_matrix(self) -> dict:
        return json.loads(MATRIX_PATH.read_text(encoding="utf-8"))

    def load_taxonomy(self) -> dict:
        return json.loads(TAXONOMY_CONTRACT_PATH.read_text(encoding="utf-8"))

    def test_taxonomy_contract_defines_required_types(self) -> None:
        taxonomy = self.load_taxonomy()
        type_ids = {item["id"] for item in taxonomy["types"]}
        self.assertEqual(
            {
                "shared_canonical",
                "credential_scoped",
                "project_scoped",
                "session_scoped",
                "repo_local_static",
                "client_global_bootstrap",
                "not_a_service",
            },
            type_ids,
        )
        for item in taxonomy["types"]:
            with self.subTest(taxonomy_type=item["id"]):
                self.assertTrue(item["meaning"])
                self.assertTrue(item["instantiation_rule"])
                self.assertTrue(item["readiness_evidence"])

    def test_taxonomy_contract_maps_current_menu_examples(self) -> None:
        taxonomy = self.load_taxonomy()
        examples = {item["menu_item"]: item for item in taxonomy["menu_examples"]}
        self.assertEqual(
            {
                "context7",
                "exa-search",
                "github",
                "mentality",
                "openzeppelin-solidity-contracts",
                "playwright",
                "ssh-tmux",
                "web-search",
                "serena",
                "None",
            },
            set(examples),
        )
        expected_types = {
            "context7": "shared_canonical",
            "exa-search": "credential_scoped",
            "github": "credential_scoped",
            "mentality": "repo_local_static",
            "openzeppelin-solidity-contracts": "shared_canonical",
            "playwright": "session_scoped",
            "ssh-tmux": "session_scoped",
            "web-search": "credential_scoped",
            "serena": "project_scoped",
            "None": "not_a_service",
        }
        self.assertEqual(expected_types, {key: value["taxonomy_type"] for key, value in examples.items()})

    def test_taxonomy_contract_makes_lifecycle_authority_explicit(self) -> None:
        taxonomy = self.load_taxonomy()
        self.assertEqual(
            {
                "service_binding_suffix_authority": "identifier_only",
                "lifecycle_authority": "taxonomy_type",
            },
            taxonomy["interpretation_rules"],
        )

    def test_matrix_uses_structured_taxonomy_contract(self) -> None:
        matrix = self.load_matrix()
        taxonomy = self.load_taxonomy()
        self.assertEqual("docs/contextforge-service-localization-taxonomy.json", matrix["taxonomy_contract"])
        self.assertEqual(
            {
                "safe_probe_status": "probe_policy_or_probe_shape_only_not_service_readiness",
                "current_slice": "current_branch_readiness_focus_only_not_umbrella_acceptance",
                "active_service_readiness": "requires owner_issue evidence or explicit blocked/non-action result",
                "slice_progress": "controller progress ledger; does not replace per-issue evidence or accepted package reports",
            },
            matrix["matrix_semantics"],
        )
        service_types = {item["taxonomy_type"] for item in matrix["services"]}
        service_types.update(item["taxonomy_type"] for item in matrix["not_service_options"])
        taxonomy_types = {item["id"] for item in taxonomy["types"]}
        self.assertTrue(service_types <= taxonomy_types)

    def test_matrix_covers_helper_offered_services_and_excludes_none(self) -> None:
        matrix = self.load_matrix()
        services = {item["service"]: item for item in matrix["services"]}
        self.assertEqual(
            {
                "context7",
                "exa-search",
                "github",
                "mentality",
                "openzeppelin-solidity-contracts",
                "playwright",
                "ssh-tmux",
                "web-search",
                "serena",
            },
            set(services),
        )
        self.assertNotIn("None", services)
        self.assertNotIn("none", services)
        self.assertEqual("not_a_service", matrix["not_service_options"][0]["taxonomy_type"])

    def test_each_service_has_required_readiness_fields(self) -> None:
        matrix = self.load_matrix()
        allowed_types = {
            "shared_canonical",
            "credential_scoped",
            "project_scoped",
            "session_scoped",
            "repo_local_static",
        }
        allowed_probe_statuses = {"known_safe_probe", "conditional_probe", "skip_until_probe_exists"}
        for service in matrix["services"]:
            with self.subTest(service=service["service"]):
                self.assertIn(service["taxonomy_type"], allowed_types)
                self.assertTrue(service["display_name"])
                self.assertIsInstance(service["owner_issue"], int)
                self.assertTrue(service["source_paths"])
                self.assertTrue(service["instantiation_path"])
                self.assertTrue(service["pi_visibility_expectation"])
                self.assertTrue(service["opencode_visibility_expectation"])
                self.assertIn(service["safe_probe_status"], allowed_probe_statuses)
                self.assertTrue(service["safe_probe"])
                self.assertTrue(service["blockers_or_non_actions"])

    def test_context7_is_the_only_current_first_slice(self) -> None:
        matrix = self.load_matrix()
        current = [item for item in matrix["services"] if item.get("current_slice")]
        self.assertEqual(["context7"], [item["service"] for item in current])
        context7 = current[0]
        self.assertEqual("context7:canonical", context7["service_binding"])
        self.assertEqual("shared_canonical", context7["taxonomy_type"])
        self.assertEqual("known_safe_probe", context7["safe_probe_status"])
        self.assertEqual("context7-local-resolve-library-id", context7["safe_probe"]["tool_name_hint"])
        self.assertEqual(
            {
                "libraryName": "python",
                "query": "standard library documentation lookup",
            },
            context7["safe_probe"]["arguments"],
        )

    def test_slice_progress_distinguishes_first_slice_from_live_queue(self) -> None:
        matrix = self.load_matrix()
        progress = matrix["slice_progress"]
        self.assertEqual(
            [
                "context7",
                "mentality",
                "openzeppelin-solidity-contracts",
                "ssh-tmux",
                "playwright",
                "exa-search",
                "github",
                "web-search",
                "serena",
            ],
            progress["accepted_source_lifecycle_slices"],
        )
        self.assertIsNone(progress["active_next_recommended_service"])
        self.assertEqual(269, progress["active_next_recommended_issue"])
        self.assertIn("not the live controller queue pointer", progress["current_slice_field_note"])


if __name__ == "__main__":
    unittest.main()
