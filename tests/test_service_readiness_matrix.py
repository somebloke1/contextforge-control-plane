import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = ROOT / "docs" / "contextforge-service-readiness-matrix.json"
TAXONOMY_PATH = ROOT / "docs" / "contextforge-service-localization-taxonomy.md"


class ServiceReadinessMatrixTests(unittest.TestCase):
    def load_matrix(self) -> dict:
        return json.loads(MATRIX_PATH.read_text(encoding="utf-8"))

    def test_taxonomy_doc_defines_required_types(self) -> None:
        text = TAXONOMY_PATH.read_text(encoding="utf-8")
        for taxonomy_type in [
            "shared_canonical",
            "credential_scoped",
            "project_scoped",
            "session_scoped",
            "repo_local_static",
            "client_global_bootstrap",
            "not_a_service",
        ]:
            self.assertIn(taxonomy_type, text)

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


if __name__ == "__main__":
    unittest.main()
