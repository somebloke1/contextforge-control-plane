from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import inspect_contextforge_cleanup as inspector

RETIRED_PORTAL_SLUG = "-".join(("context", "portal"))
RETIRED_REGISTRY_URI = "contextforge://" + RETIRED_PORTAL_SLUG + "/project-init/v15"


def _tool(
    tool_id: str,
    name: str,
    gateway_id: str,
    gateway_slug: str,
    *,
    original_name: str | None = None,
) -> dict[str, object]:
    return {
        "id": tool_id,
        "name": name,
        "originalName": original_name or name,
        "enabled": True,
        "gatewayId": gateway_id,
        "gatewaySlug": gateway_slug,
    }


def _instance(root: Path, slug: str, *, service: str, gateway_id: str, project_root: str | None = None) -> None:
    path = root / slug
    path.mkdir(parents=True)
    payload = {
        "slug": slug,
        "service": service,
        "canonical_project_root": project_root,
        "contextforge": {
            "gateway": {"id": gateway_id, "name": slug},
            "virtual_server": {"name": f"{slug.replace('-', '_')}_server"},
        },
    }
    (path / "instance.json").write_text(json.dumps(payload), encoding="utf-8")


class ContextForgeCleanupInspectorTests(unittest.TestCase):
    def test_manifest_classifies_cleanup_candidates_without_mutation(self) -> None:
        live = {
            "tools": [
                _tool("tool-current", "serena-cf-controlplane-d46fe58a2a20-search", "gw-serena-current", "serena-cf-controlplane-d46fe58a2a20"),
                _tool("tool-stale", "serena-test-search", "gw-serena-stale", "serena-test-new-proj-01"),
                _tool("tool-phronesis", "serena-phronesis-search", "gw-serena-phronesis", "serena-phronesis-devstack"),
                _tool("tool-orphan", "ssh-tmux-cleanup-dead-sessions", "gw-ssh", "ssh-tmux", original_name="cleanup_dead_sessions"),
                _tool("tool-keep", "ssh-tmux-list-sessions", "gw-ssh", "ssh-tmux"),
            ],
            "servers": [
                {
                    "id": "server-serena-current",
                    "name": "serena_cf_controlplane_d46fe58a2a20_server",
                    "associatedToolIds": ["tool-current"],
                    "associatedPrompts": [],
                    "associatedResources": [],
                },
                {
                    "id": "server-ssh",
                    "name": "ssh_tmux_server",
                    "associatedToolIds": ["tool-keep"],
                    "associatedPrompts": ["prompt-associated"],
                    "associatedResources": ["resource-associated"],
                },
            ],
            "prompts": [
                {"id": "prompt-associated", "name": "ssh prompt", "customName": "ssh_prompt", "enabled": True},
                {"id": "prompt-orphan", "name": "old project init", "customName": "old_project_init", "enabled": True},
                {
                    "id": "prompt-project-init-current",
                    "name": inspector.PROJECT_INIT_PROMPT_NAME,
                    "customName": inspector.PROJECT_INIT_PROMPT_NAME,
                    "enabled": True,
                },
            ],
            "resources": [
                {"id": "resource-associated", "name": "ssh resource", "uri": "contextforge://ssh/current"},
                {"id": "resource-orphan", "name": "old resource", "uri": "contextforge://project-init/old"},
                {"id": "resource-retired", "name": "retired resource", "uri": RETIRED_REGISTRY_URI},
                {
                    "id": "resource-project-init-current",
                    "name": "current project init resource",
                    "uri": inspector.PROJECT_INIT_RESOURCE_URI,
                },
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            current_instances = root / "current"
            legacy_instances = root / "legacy"
            _instance(
                current_instances,
                "serena-cf-controlplane-d46fe58a2a20",
                service="serena",
                gateway_id="gw-serena-current",
                project_root="/home/dgk/workspace/cf-controlplane",
            )
            _instance(current_instances, "ssh-tmux", service="ssh-tmux", gateway_id="gw-ssh")
            _instance(
                legacy_instances,
                "serena-test-new-proj-01",
                service="serena",
                gateway_id="gw-serena-stale",
                project_root="/home/dgk/workspace/test-new-proj-01",
            )
            _instance(
                legacy_instances,
                "serena-phronesis-devstack",
                service="serena",
                gateway_id="gw-serena-phronesis",
                project_root="/home/dgk/workspace/phronesis-devstack",
            )

            manifest = inspector.build_manifest(
                live,
                inspector.load_instance_manifests([current_instances, legacy_instances]),
                [current_instances, legacy_instances],
            )

        by_id = {row["id"]: row for row in manifest["tool_classification"]}
        self.assertEqual("keep_project_scoped", by_id["tool-current"]["classification"])
        self.assertEqual("stale_project_scoped", by_id["tool-stale"]["classification"])
        self.assertEqual("retain_project_scoped_or_unknown", by_id["tool-phronesis"]["classification"])
        self.assertEqual("orphaned", by_id["tool-orphan"]["classification"])
        self.assertEqual("keep_canonical", by_id["tool-keep"]["classification"])
        operations = manifest["summary"]["cleanup_candidates_by_operation"]
        self.assertEqual(2, operations["DELETE /tools/{tool_id}"])
        self.assertEqual(1, operations["DELETE /prompts/{prompt_id}"])
        self.assertEqual(1, operations["DELETE /resources/{resource_id}"])
        self.assertEqual(
            [],
            [
                candidate
                for candidate in manifest["cleanup_candidates"]
                if candidate.get("prompt_id") == "prompt-project-init-current"
                or candidate.get("resource_id") == "resource-project-init-current"
            ],
        )
        self.assertEqual(1, manifest["summary"]["retired_registry_surface_records"])
        self.assertEqual(
            [],
            [
                candidate
                for candidate in manifest["cleanup_candidates"]
                if candidate.get("resource_id") == "resource-retired"
            ],
        )
        self.assertEqual(
            [
                {
                    "record_type": "resource",
                    "id": "resource-retired",
                    "name": "retired resource",
                    "uri": RETIRED_REGISTRY_URI,
                    "reason": "orphaned registry record still references the retired project surface",
                }
            ],
            manifest["retired_registry_surface_records"],
        )
        self.assertFalse(manifest["live_mutation_performed"])
        self.assertIn("read-only inspection; no ContextForge registry mutation", manifest["non_actions"])

    def test_cli_fixture_mode_writes_manifest_without_live_registry(self) -> None:
        live = {
            "tools": [_tool("tool-stale", "serena-test-search", "gw-serena-stale", "serena-test-new-proj-01")],
            "servers": [],
            "prompts": [],
            "resources": [],
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            live_json = root / "live.json"
            output = root / "manifest.json"
            legacy_instances = root / "legacy"
            live_json.write_text(json.dumps(live), encoding="utf-8")
            _instance(
                legacy_instances,
                "serena-test-new-proj-01",
                service="serena",
                gateway_id="gw-serena-stale",
                project_root="/home/dgk/workspace/test-new-proj-01",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "inspect_contextforge_cleanup.py"),
                    "--live-json",
                    str(live_json),
                    "--instance-root",
                    str(legacy_instances),
                    "--output",
                    str(output),
                ],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=20,
            )
            manifest = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("", result.stderr)
        self.assertEqual(inspector.SCHEMA_URI, manifest["schema_uri"])
        self.assertTrue(manifest["dry_run"])
        self.assertEqual(["DELETE /tools/{tool_id}"], list(manifest["summary"]["cleanup_candidates_by_operation"]))


if __name__ == "__main__":
    unittest.main()
