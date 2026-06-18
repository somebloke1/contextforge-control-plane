from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import plan_contextforge_registry_recreation as planner


def write_manifest(root: Path, slug: str, *, tools: list[str], env: str | None = None) -> None:
    directory = root / slug
    directory.mkdir(parents=True)
    backend: dict[str, object] = {"transport": "stdio", "command": "example", "args": []}
    if env:
        backend["env"] = env
    (directory / "instance.json").write_text(
        json.dumps(
            {
                "name": slug,
                "slug": slug,
                "backend": backend,
                "registration": {"registered_tools": tools},
            }
        ),
        encoding="utf-8",
    )


class RegistryRecreationPlanTests(unittest.TestCase):
    def test_manifest_driven_services_are_classified_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_manifest(root, "mentality", tools=["mentality-governance-list"])
            write_manifest(root, "github", tools=["github-search-code"])
            write_manifest(root, "unknown-service", tools=[])

            plan = planner.build_plan(manifests_root=root)

        self.assertEqual(planner.SCHEMA_URI, plan["schema_uri"])
        self.assertFalse(plan["mutation_performed"])
        self.assertIn("read-only plan; no ContextForge API calls", plan["non_actions"])
        by_slug = {service["slug"]: service for service in plan["services"]}
        self.assertEqual("needs_manifest_driven_api_recreation", by_slug["mentality"]["classification"])
        self.assertEqual("covered_by_existing_helper", by_slug["github"]["classification"])
        self.assertEqual(
            "unsupported_manifest_requires_manual_plan",
            by_slug["unknown-service"]["classification"],
        )

    def test_export_artifact_adds_existing_state_and_tool_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_manifest(root, "mentality", tools=["manifest-tool"])
            export_path = root / "export.json"
            export_path.write_text(
                json.dumps(
                    {
                        "entities": {
                            "gateways": [{"name": "mentality"}],
                            "servers": [{"name": "mentality_server"}],
                        },
                        "metadata": {
                            "dependencies": {
                                "servers_to_tools": {"mentality_server": ["export-tool"]}
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            plan = planner.build_plan(manifests_root=root, export_path=export_path)

        service = plan["services"][0]
        self.assertTrue(service["existing_export_gateway"])
        self.assertTrue(service["existing_export_server"])
        self.assertEqual(["export-tool"], service["export_dependency_tool_names"])
        self.assertTrue(service["tool_name_drift"])
        self.assertEqual(["mentality"], plan["summary"]["services_with_tool_name_drift"])

    def test_env_refs_report_existence_without_secret_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_manifest(root, "exa-search", tools=[], env="server-instances/exa-search/not-real-test.env")
            plan = planner.build_plan(manifests_root=root)

        service = plan["services"][0]
        self.assertFalse(service["env_refs"][0]["exists"])
        self.assertIn("not-real-test.env", service["env_refs"][0]["path"])

    def test_cli_outputs_clean_json(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "plan_contextforge_registry_recreation.py"),
            ],
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=20,
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("", result.stderr)
        data = json.loads(result.stdout)
        self.assertFalse(data["mutation_performed"])
        self.assertGreaterEqual(data["summary"]["service_count"], 1)


if __name__ == "__main__":
    unittest.main()
