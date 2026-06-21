from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import plan_contextforge_docker_migration as docker_plan
import plan_contextforge_registry_recreation as registry_plan


def write_manifest(root: Path, slug: str, tools: list[str]) -> None:
    directory = root / slug
    directory.mkdir(parents=True)
    (directory / "instance.json").write_text(
        json.dumps(
            {
                "slug": slug,
                "name": slug,
                "backend": {"transport": "stdio", "command": "example", "args": []},
                "registration": {"registered_tools": tools},
            }
        ),
        encoding="utf-8",
    )


def endpoint(rows: list[dict]) -> dict:
    return {"ok": True, "status": 200, "count": len(rows), "all": rows}


def server(name: str, *, tools: int = 0, prompts: int = 0, resources: int = 0) -> dict:
    return {
        "id": f"{name}-id",
        "name": name,
        "associatedTools": [f"{name}-tool-{index}" for index in range(tools)],
        "associatedPrompts": [f"{name}-prompt-{index}" for index in range(prompts)],
        "associatedResources": [f"{name}-resource-{index}" for index in range(resources)],
    }


def tool(name: str) -> dict:
    return {"id": f"{name}-id", "name": name}


def prompt(name: str, tool_tag: str) -> dict:
    return {
        "id": f"{name}-id",
        "name": name,
        "tags": [{"label": "tool-guidance"}, {"label": tool_tag}],
    }


def resource(uri: str, tool_tag: str) -> dict:
    return {
        "id": f"{tool_tag}-resource-id",
        "uri": uri,
        "tags": [{"label": "tool-guidance"}, {"label": tool_tag}],
    }


def write_readbacks(root: Path) -> tuple[Path, Path]:
    baseline_servers = [
        server(defaults["server_name"], tools=1, prompts=1, resources=1)
        for defaults in registry_plan.CANONICAL_SERVICE_DEFAULTS.values()
    ]
    target_servers = [
        server("context7_local_server", tools=2),
        server("mentality_dev_docker_server", tools=5),
    ]
    baseline = {
        "bases": {
            "host_4444": {
                "endpoints": {
                    "servers": endpoint(baseline_servers),
                    "tools": endpoint([tool("context7-local-resolve-library-id"), tool("mentality-governance-list")]),
                    "prompts": endpoint(
                        [
                            prompt("resolve_context7_library_id", "context7-local-resolve-library-id"),
                            prompt("mentality_governance_list_entries", "mentality-governance-list"),
                        ]
                    ),
                    "resources": endpoint(
                        [
                            resource("context7://tools/context7-local-resolve-library-id", "context7-local-resolve-library-id"),
                            resource("mentality://governance/list", "mentality-governance-list"),
                        ]
                    ),
                }
            }
        }
    }
    target = {
        "docker_4445": {
            "endpoints": {
                "servers": endpoint(target_servers),
                "tools": endpoint(
                    [
                        tool("context7-local-resolve-library-id"),
                        tool("context7-local-query-docs"),
                        tool("mentality-dev-docker-governance-list"),
                    ]
                ),
                "prompts": endpoint([]),
                "resources": endpoint([]),
            }
        }
    }
    baseline_path = root / "baseline.json"
    target_path = root / "target.json"
    baseline_path.write_text(json.dumps(baseline), encoding="utf-8")
    target_path.write_text(json.dumps(target), encoding="utf-8")
    return baseline_path, target_path


class DockerMigrationPlanTests(unittest.TestCase):
    def test_planner_classifies_all_canonical_services_without_mutation(self) -> None:
        plan = docker_plan.build_plan()

        self.assertEqual(docker_plan.SCHEMA_URI, plan["schema_uri"])
        self.assertFalse(plan["mutation_performed"])
        self.assertEqual(9, plan["summary"]["target_service_count"])
        self.assertEqual(
            sorted(registry_plan.CANONICAL_SERVICE_DEFAULTS),
            sorted(service["slug"] for service in plan["services"]),
        )
        self.assertIn("read-only plan; no ContextForge API calls", plan["non_actions"])

    def test_readback_gap_and_guidance_delta_are_structured(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            baseline_path, target_path = write_readbacks(Path(tmp))
            plan = docker_plan.build_plan(
                baseline_readback_path=baseline_path,
                target_readback_path=target_path,
            )

        self.assertEqual({"servers": 9, "tools": 2, "prompts": 2, "resources": 2}, plan["summary"]["baseline_counts"])
        self.assertEqual({"servers": 2, "tools": 3, "prompts": 0, "resources": 0}, plan["summary"]["current_4445_counts"])
        self.assertEqual(8, len(plan["endpoint_gaps"]["servers"]["missing_on_4445"]))
        self.assertEqual(2, plan["guidance_tag_gap"]["baseline_prompt_tool_guidance_tags"])
        self.assertEqual(0, plan["guidance_tag_gap"]["target_prompt_tool_guidance_tags"])
        self.assertEqual(81, plan["guidance_tag_gap"]["expected_source_tool_guidance_tags"])
        self.assertEqual(
            ["context7-local-resolve-library-id", "mentality-governance-list"],
            plan["guidance_tag_gap"]["prompt_tags_missing_on_4445"],
        )
        self.assertIn(
            "openzeppelin-solidity-contracts-solidity-stablecoin",
            plan["guidance_tag_gap"]["baseline_prompt_tools_missing_expected_source"],
        )

    def test_host_local_defaults_are_flagged_for_docker_projection(self) -> None:
        plan = docker_plan.build_plan()
        services = {service["slug"]: service for service in plan["services"]}

        for slug in ["github", "mentality", "serena-cf-controlplane-d46fe58a2a20", "ssh-tmux", "web-search"]:
            with self.subTest(slug=slug):
                self.assertNotIn("127.0.0.1:910", services[slug]["target_upstream_url"])
                self.assertTrue(services[slug]["docker_projection_required"])
                self.assertTrue(services[slug]["unsafe_to_reuse_live_default"])

        self.assertEqual("compose_sidecar", services["playwright"]["locality"])
        self.assertEqual("http://playwright-transceiver:9204/mcp", services["playwright"]["target_upstream_url"])
        self.assertEqual("available_in_isolated_browser_sidecar", services["playwright"]["approval_state"])
        self.assertFalse(services["playwright"]["approval_blocked"])
        self.assertTrue(services["playwright"]["docker_projection_required"])
        self.assertTrue(services["playwright"]["unsafe_to_reuse_live_default"])
        self.assertEqual("compose_sidecar", services["exa-search"]["locality"])
        self.assertEqual("http://exa-search-transceiver:9205/mcp", services["exa-search"]["target_upstream_url"])
        self.assertEqual("ready_after_credential_env_preflight", services["exa-search"]["approval_state"])
        self.assertFalse(services["exa-search"]["approval_blocked"])
        self.assertTrue(services["exa-search"]["docker_projection_required"])
        self.assertTrue(services["exa-search"]["unsafe_to_reuse_live_default"])
        self.assertFalse(services["openzeppelin-solidity-contracts"]["unsafe_to_reuse_live_default"])
        self.assertEqual(9, len(services["ssh-tmux"]["expected_tool_names"]))
        self.assertIn("ssh-tmux-cleanup-dead-sessions", services["ssh-tmux"]["expected_tool_names"])
        self.assertEqual("compose_sidecar", services["github"]["locality"])
        self.assertEqual("http://github-transceiver:9206/mcp", services["github"]["target_upstream_url"])
        self.assertEqual("ready_after_credential_env_preflight", services["github"]["approval_state"])
        self.assertFalse(services["github"]["approval_blocked"])
        self.assertTrue(services["github"]["docker_projection_required"])
        self.assertTrue(services["github"]["unsafe_to_reuse_live_default"])
        self.assertIn("ssh-tmux", plan["summary"]["approval_blocked_services"])
        self.assertIn("serena-cf-controlplane-d46fe58a2a20", plan["summary"]["approval_blocked_services"])

    def test_helper_dispositions_mark_unsafe_apply_paths(self) -> None:
        plan = docker_plan.build_plan()

        self.assertEqual(
            "unsafe_as_is_for_4445_apply",
            plan["helper_dispositions"]["scripts/apply_contextforge_registry_recreation.py"]["disposition"],
        )
        self.assertEqual(
            "reusable_after_target_parameterization",
            plan["helper_dispositions"]["scripts/register_tool_guidance.py"]["disposition"],
        )

    def test_cli_outputs_clean_read_only_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            baseline_path, target_path = write_readbacks(Path(tmp))
            result = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "plan_contextforge_docker_migration.py"),
                    "--baseline-readback",
                    str(baseline_path),
                    "--target-readback",
                    str(target_path),
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
        self.assertEqual("http://127.0.0.1:4445", data["target_surface"]["base_url"])
        self.assertFalse(data["target_surface"]["env_values_read"])


if __name__ == "__main__":
    unittest.main()
