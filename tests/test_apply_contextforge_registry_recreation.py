from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import apply_contextforge_registry_recreation as apply_helper


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


def write_docker_plan(root: Path, slug: str, target_url: str) -> Path:
    return write_docker_plan_multi(root, [(slug, target_url, True)])


def write_docker_plan_multi(root: Path, services: list[tuple[str, str, bool]]) -> Path:
    path = root / "docker-plan.json"
    path.write_text(
        json.dumps(
            {
                "schema_uri": "contextforge://diagnostics/docker-successor-migration-plan/v1",
                "mutation_performed": False,
                "services": [
                    {
                        "slug": slug,
                        "target_upstream_url": target_url,
                        "locality": "host_gateway_projection",
                        "approval_state": "blocked_pending_review" if blocked else "approved_for_test",
                        "approval_blocked": blocked,
                        "docker_projection_required": True,
                        "unsafe_to_reuse_live_default": True,
                    }
                    for slug, target_url, blocked in services
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def write_docker_plan_with_state(root: Path, slug: str, target_url: str, approval_state: str, approval_blocked: bool) -> Path:
    path = root / "docker-plan.json"
    path.write_text(
        json.dumps(
            {
                "schema_uri": "contextforge://diagnostics/docker-successor-migration-plan/v1",
                "mutation_performed": False,
                "services": [
                    {
                        "slug": slug,
                        "target_upstream_url": target_url,
                        "locality": "compose_sidecar",
                        "approval_state": approval_state,
                        "approval_blocked": approval_blocked,
                        "docker_projection_required": True,
                        "unsafe_to_reuse_live_default": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


class FakeClient:
    def __init__(self) -> None:
        self.requests: list[tuple[str, str, dict | None]] = []
        self.gateways: list[dict] = []
        self.servers: list[dict] = []
        self.tools: list[dict] = []
        self.next_id = 1

    def _id(self, prefix: str) -> str:
        value = f"{prefix}-{self.next_id}"
        self.next_id += 1
        return value

    def request(self, method: str, path: str, body: dict | None = None):
        self.requests.append((method, path, body))
        if method == "POST" and path == "/gateways":
            row = {"id": self._id("gateway"), **(body or {})}
            self.gateways.append(row)
            return row
        if method == "PUT" and path.startswith("/gateways/"):
            gateway_id = path.rsplit("/", 1)[-1]
            row = next(gateway for gateway in self.gateways if gateway["id"] == gateway_id)
            row.update(body or {})
            return row
        if method == "POST" and path.endswith("/tools/refresh"):
            gateway_id = path.split("/")[2]
            if not any(tool.get("gateway_id") == gateway_id for tool in self.tools):
                self.tools.append({"id": self._id("tool"), "name": "example-tool", "gateway_id": gateway_id})
            return {"ok": True}
        if method == "POST" and path == "/servers":
            payload = dict((body or {})["server"])
            row = {"id": self._id("server"), **payload}
            self.servers.append(row)
            return row
        if method == "PUT" and path.startswith("/servers/"):
            server_id = path.rsplit("/", 1)[-1]
            row = next(server for server in self.servers if server["id"] == server_id)
            row.update(body or {})
            return row
        raise AssertionError(f"unexpected request {method} {path}")

    def items(self, path: str) -> list[dict]:
        if path.startswith("/gateways"):
            return list(self.gateways)
        if path.startswith("/tools"):
            return list(self.tools)
        if path.startswith("/servers"):
            return list(self.servers)
        raise AssertionError(f"unexpected items path {path}")


class ApplyRegistryRecreationTests(unittest.TestCase):
    def test_default_run_is_dry_run_and_filters_to_manifest_driven_services(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_manifest(root, "mentality", ["mentality-governance-list"])
            write_manifest(root, "github", ["github-search-code"])

            result = apply_helper.run(apply=False, manifests_root=root)

        self.assertFalse(result["mutation_performed"])
        self.assertFalse(result["registry_mutation_discipline"]["direct_database_writes_allowed"])
        self.assertFalse(result["registry_mutation_discipline"]["stored_ids_are_authority"])
        self.assertEqual(
            "public_contextforge_api_or_admin_ui_after_explicit_approval",
            result["registry_mutation_discipline"]["mutation_path"],
        )
        self.assertEqual(1, result["service_count"])
        self.assertEqual("mentality", result["services"][0]["slug"])
        self.assertEqual("dry-run; no ContextForge API calls", result["non_actions"][0])
        self.assertFalse(result["target"]["env_values_recorded"])

    def test_dry_run_can_project_docker_successor_urls_without_api_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_manifest(root, "mentality", ["mentality-governance-list"])
            docker_plan = write_docker_plan(root, "mentality", "http://mentality-transceiver:9201/mcp")

            result = apply_helper.run(apply=False, manifests_root=root, docker_migration_plan=docker_plan)

        self.assertFalse(result["mutation_performed"])
        operation = result["services"][0]["operations"][0]
        self.assertEqual("http://mentality-transceiver:9201/mcp", operation["payload"]["url"])
        self.assertTrue(result["services"][0]["docker_successor_profile"]["unsafe_to_reuse_live_default"])
        self.assertEqual(str(docker_plan), result["target"]["docker_migration_plan"])

    def test_apply_creates_gateway_refreshes_tools_and_creates_server(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_manifest(root, "mentality", ["example-tool"])
            client = FakeClient()

            result = apply_helper.run(apply=True, manifests_root=root, client=client)

        self.assertTrue(result["mutation_performed"])
        self.assertEqual(1, result["service_count"])
        self.assertEqual("created", result["services"][0]["gateway"]["action"])
        self.assertEqual("created", result["services"][0]["server"]["action"])
        self.assertEqual(
            [
                ("POST", "/gateways"),
                ("POST", "/gateways/gateway-1/tools/refresh"),
                ("POST", "/servers"),
            ],
            [(method, path) for method, path, _body in client.requests],
        )

    def test_apply_updates_existing_server_and_preserves_associations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_manifest(root, "mentality", ["example-tool"])
            client = FakeClient()
            client.gateways.append({"id": "gateway-existing", "name": "mentality", "url": "old"})
            client.tools.append({"id": "tool-existing", "name": "example-tool", "gateway_id": "gateway-existing"})
            client.servers.append(
                {
                    "id": "server-existing",
                    "name": "mentality_server",
                    "associatedResources": ["resource-id"],
                    "associatedPrompts": ["prompt-id"],
                    "associatedA2aAgents": ["agent-id"],
                }
            )

            result = apply_helper.run(apply=True, manifests_root=root, client=client)

        self.assertEqual("updated", result["services"][0]["gateway"]["action"])
        self.assertEqual("updated", result["services"][0]["server"]["action"])
        server_put = next(body for method, path, body in client.requests if method == "PUT" and path == "/servers/server-existing")
        self.assertEqual(["resource-id"], server_put["associatedResources"])
        self.assertEqual(["prompt-id"], server_put["associatedPrompts"])
        self.assertEqual(["agent-id"], server_put["associatedA2aAgents"])
        self.assertEqual(["tool-existing"], server_put["associatedTools"])

    def test_apply_updates_existing_gateway_by_url_for_docker_canonical_projection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_manifest(root, "mentality", ["example-tool"])
            docker_plan = write_docker_plan(root, "mentality", "http://mentality-transceiver:9201/mcp")
            client = FakeClient()
            client.gateways.append(
                {
                    "id": "gateway-existing",
                    "name": "mentality-dev-docker",
                    "url": "http://mentality-transceiver:9201/mcp",
                }
            )
            client.tools.append({"id": "tool-existing", "name": "example-tool", "gateway_id": "gateway-existing"})

            result = apply_helper.run(
                apply=True,
                manifests_root=root,
                docker_migration_plan=docker_plan,
                client=client,
                boundary_approved_slugs={"mentality"},
            )

        self.assertEqual("updated_from_url_match", result["services"][0]["gateway"]["action"])
        self.assertEqual("created", result["services"][0]["server"]["action"])
        gateway_put = next(body for method, path, body in client.requests if method == "PUT" and path == "/gateways/gateway-existing")
        self.assertEqual("mentality", gateway_put["name"])
        self.assertEqual("http://mentality-transceiver:9201/mcp", gateway_put["url"])

    def test_apply_skips_docker_approval_blocked_services_without_boundary_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_manifest(root, "mentality", ["example-tool"])
            docker_plan = write_docker_plan(root, "mentality", "http://mentality-transceiver:9201/mcp")
            client = FakeClient()

            result = apply_helper.run(apply=True, manifests_root=root, docker_migration_plan=docker_plan, client=client)

        self.assertFalse(result["mutation_performed"])
        self.assertTrue(result["apply_requested"])
        self.assertEqual([], result["services"])
        self.assertEqual("mentality", result["skipped_services"][0]["slug"])
        self.assertEqual("approval_blocked", result["skipped_services"][0]["reason"])
        self.assertEqual([], client.requests)
        self.assertIn("no ContextForge API calls", result["non_actions"])

    def test_apply_does_not_login_when_all_requested_services_are_blocked(self) -> None:
        calls: list[str] = []
        original = apply_helper.load_target_client

        def fake_load_target_client(base_url: str, env_file: Path):
            calls.append(base_url)
            raise AssertionError("target client should not load for a no-op blocked apply")

        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                write_manifest(root, "mentality", ["example-tool"])
                docker_plan = write_docker_plan(root, "mentality", "http://mentality-transceiver:9201/mcp")
                apply_helper.load_target_client = fake_load_target_client  # type: ignore[assignment]

                result = apply_helper.run(
                    apply=True,
                    manifests_root=root,
                    docker_migration_plan=docker_plan,
                    base_url="http://127.0.0.1:4445",
                    env_file=Path("not-read.env"),
                )
        finally:
            apply_helper.load_target_client = original  # type: ignore[assignment]

        self.assertEqual([], calls)
        self.assertFalse(result["mutation_performed"])
        self.assertEqual([], result["services"])
        self.assertEqual("approval_blocked", result["skipped_services"][0]["reason"])

    def test_apply_allows_explicitly_boundary_approved_service(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_manifest(root, "mentality", ["example-tool"])
            docker_plan = write_docker_plan(root, "mentality", "http://mentality-transceiver:9201/mcp")
            client = FakeClient()

            result = apply_helper.run(
                apply=True,
                manifests_root=root,
                docker_migration_plan=docker_plan,
                client=client,
                boundary_approved_slugs={"mentality"},
            )

        self.assertEqual("mentality", result["services"][0]["slug"])
        self.assertEqual([], result["skipped_services"])

    def test_apply_blocks_ready_after_preflight_even_if_plan_flag_is_false(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_manifest(root, "github", ["example-tool"])
            docker_plan = write_docker_plan_with_state(
                root,
                "github",
                "http://github-transceiver:9206/mcp",
                "ready_after_credential_env_preflight",
                False,
            )
            client = FakeClient()

            result = apply_helper.run(
                apply=True,
                manifests_root=root,
                docker_migration_plan=docker_plan,
                client=client,
                include_helper_services=True,
            )

        self.assertFalse(result["mutation_performed"])
        self.assertEqual([], result["services"])
        self.assertEqual("github", result["skipped_services"][0]["slug"])
        self.assertEqual("approval_blocked", result["skipped_services"][0]["reason"])
        self.assertEqual([], client.requests)

    def test_include_helper_services_allows_explicit_helper_backed_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_manifest(root, "github", ["github-search-repositories"])
            docker_plan = write_docker_plan(root, "github", "http://host.docker.internal:9106/mcp")

            without_helpers = apply_helper.run(
                apply=False,
                manifests_root=root,
                docker_migration_plan=docker_plan,
                slugs={"github"},
            )
            with_helpers = apply_helper.run(
                apply=False,
                manifests_root=root,
                docker_migration_plan=docker_plan,
                slugs={"github"},
                include_helper_services=True,
            )

        self.assertEqual([], without_helpers["services"])
        self.assertEqual("github", with_helpers["services"][0]["slug"])

    def test_apply_filters_refreshed_tools_to_manifest_expected_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_manifest(root, "mentality", ["expected-tool"])
            client = FakeClient()
            client.gateways.append({"id": "gateway-existing", "name": "mentality", "url": "old"})
            client.tools.append({"id": "tool-expected", "name": "expected-tool", "gateway_id": "gateway-existing"})
            client.tools.append({"id": "tool-extra", "name": "extra-tool", "gateway_id": "gateway-existing"})

            result = apply_helper.run(apply=True, manifests_root=root, client=client)

        self.assertEqual(["expected-tool"], result["services"][0]["tool_names"])
        self.assertEqual(1, result["services"][0]["tool_count"])

    def test_target_login_prefers_harness_login_endpoint(self) -> None:
        calls: list[str] = []
        original = apply_helper._target_request

        def fake_request(method: str, base_url: str, path: str, body: dict | None = None):
            calls.append(path)
            return {"access_token": "target-token"}

        try:
            apply_helper._target_request = fake_request  # type: ignore[assignment]
            token = apply_helper.target_login_token("http://127.0.0.1:4445", "admin@example.test", "password")
        finally:
            apply_helper._target_request = original  # type: ignore[assignment]

        self.assertEqual("target-token", token)
        self.assertEqual(["/auth/login"], calls)

    def test_cli_dry_run_outputs_clean_json(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "apply_contextforge_registry_recreation.py"),
                "--service",
                "mentality",
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
        self.assertEqual("#140", data["registry_mutation_discipline"]["issue"])

    def test_cli_accepts_explicit_target_metadata_in_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_manifest(root, "mentality", ["mentality-governance-list"])
            docker_plan = write_docker_plan(root, "mentality", "http://mentality-transceiver:9201/mcp")
            result = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "apply_contextforge_registry_recreation.py"),
                    "--manifests-root",
                    str(root),
                    "--docker-migration-plan",
                    str(docker_plan),
                    "--base-url",
                    "http://127.0.0.1:4445",
                    "--env-file",
                    "docker/contextforge-harness/env/contextforge.env",
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
        self.assertEqual("http://127.0.0.1:4445", data["target"]["base_url"])
        self.assertFalse(data["target"]["env_values_recorded"])
        self.assertEqual("http://mentality-transceiver:9201/mcp", data["services"][0]["operations"][0]["payload"]["url"])


if __name__ == "__main__":
    unittest.main()
