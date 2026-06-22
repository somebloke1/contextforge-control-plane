from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import control_plane_project_state as project_state
import control_plane_service_onboarding_surfaces as surfaces


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
            "get_current_time": {"inputSchema": {"type": "object", "properties": {"timezone": {"type": "string"}}, "required": ["timezone"]}},
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
            "abstract_prompt": "Time provides current-time and timezone conversion tools.",
            "detail_prompts": {"usage": "Use IANA timezone names."},
        },
    }


def load_executor():
    path = REPO_ROOT / "docker/contextforge-harness/scripts/apply_onboarding_runtime_package.py"
    spec = importlib.util.spec_from_file_location("apply_onboarding_runtime_package_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def write_time_package(path: Path, project_root: Path) -> dict[str, Any]:
    package = surfaces.build_service_onboarding_runtime_apply_package(
        str(project_root),
        {
            "candidateService": "time",
            "operatorGoal": "Add Time MCP service.",
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
        },
    )
    path.write_text(json.dumps(package), encoding="utf-8")
    return package


class FakeClient:
    def __init__(self) -> None:
        self.requests: list[tuple[str, str, dict | None]] = []
        self.gateways: list[dict[str, Any]] = []
        self.servers: list[dict[str, Any]] = []
        self.tools: list[dict[str, Any]] = []
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
                self.tools.extend(
                    [
                        {"id": self._id("tool"), "name": "time-dev-docker-get-current-time", "gateway_id": gateway_id},
                        {"id": self._id("tool"), "name": "time-dev-docker-convert-time", "gateway_id": gateway_id},
                        {"id": self._id("tool"), "name": "unrelated-tool", "gateway_id": gateway_id},
                    ]
                )
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
        if method == "DELETE" and path.startswith("/servers/"):
            server_id = path.rsplit("/", 1)[-1]
            self.servers = [server for server in self.servers if server.get("id") != server_id]
            return {"ok": True}
        if method == "DELETE" and path.startswith("/gateways/"):
            gateway_id = path.rsplit("/", 1)[-1]
            self.gateways = [gateway for gateway in self.gateways if gateway.get("id") != gateway_id]
            self.tools = [tool for tool in self.tools if tool.get("gateway_id") != gateway_id and tool.get("gatewayId") != gateway_id]
            return {"ok": True}
        raise AssertionError(f"unexpected request {method} {path}")

    def items(self, path: str) -> list[dict[str, Any]]:
        if path.startswith("/gateways"):
            return list(self.gateways)
        if path.startswith("/tools"):
            return list(self.tools)
        if path.startswith("/servers"):
            return list(self.servers)
        raise AssertionError(f"unexpected items path {path}")


class DelayedToolClient(FakeClient):
    def __init__(self) -> None:
        super().__init__()
        self.tool_reads = 0

    def request(self, method: str, path: str, body: dict | None = None):
        self.requests.append((method, path, body))
        if method == "POST" and path == "/gateways":
            row = {"id": "gateway-delayed", **(body or {})}
            self.gateways.append(row)
            return row
        if method == "POST" and path.endswith("/tools/refresh"):
            return {"ok": True}
        if method == "POST" and path == "/servers":
            payload = dict((body or {})["server"])
            row = {"id": "server-delayed", **payload}
            self.servers.append(row)
            return row
        return super().request(method, path, body)

    def items(self, path: str) -> list[dict[str, Any]]:
        if path.startswith("/tools"):
            self.tool_reads += 1
            if self.tool_reads < 2:
                return []
            return [
                {"id": "tool-current", "name": "time-dev-docker-get-current-time", "gateway_id": "gateway-delayed"},
                {"id": "tool-convert", "name": "time-dev-docker-convert-time", "gateway_id": "gateway-delayed"},
            ]
        return super().items(path)


class RefreshRetryClient(FakeClient):
    def __init__(self) -> None:
        super().__init__()
        self.refresh_count = 0

    def request(self, method: str, path: str, body: dict | None = None):
        self.requests.append((method, path, body))
        if method == "POST" and path == "/gateways":
            row = {"id": "gateway-refresh", **(body or {})}
            self.gateways.append(row)
            return row
        if method == "POST" and path.endswith("/tools/refresh"):
            self.refresh_count += 1
            if self.refresh_count == 1:
                raise RuntimeError("temporary refresh failure")
            self.tools.extend(
                [
                    {"id": "tool-current", "name": "time-dev-docker-get-current-time", "gateway_id": "gateway-refresh"},
                    {"id": "tool-convert", "name": "time-dev-docker-convert-time", "gateway_id": "gateway-refresh"},
                ]
            )
            return {"ok": True}
        if method == "POST" and path == "/servers":
            payload = dict((body or {})["server"])
            row = {"id": "server-refresh", **payload}
            self.servers.append(row)
            return row
        return super().request(method, path, body)


class FailingRefreshClient(FakeClient):
    def request(self, method: str, path: str, body: dict | None = None):
        self.requests.append((method, path, body))
        if method == "POST" and path == "/gateways":
            row = {"id": "gateway-failing", **(body or {})}
            self.gateways.append(row)
            return row
        if method == "POST" and path.endswith("/tools/refresh"):
            raise RuntimeError("simulated refresh failure")
        if method == "DELETE" and path.startswith("/gateways/"):
            gateway_id = path.rsplit("/", 1)[-1]
            self.gateways = [gateway for gateway in self.gateways if gateway.get("id") != gateway_id]
            return {"ok": True}
        return super().request(method, path, body)


class OnboardingRuntimePackageExecutorTests(unittest.TestCase):
    def test_dry_run_consumes_runtime_package_without_api_or_env_reads(self) -> None:
        executor = load_executor()
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            package_path = root / "time-package.json"
            write_time_package(package_path, root)

            result = executor.run(
                package_path=package_path,
                upstream_url="http://time-transceiver:9209/mcp",
                gateway_name="time-dev-docker",
                server_name="time_dev_docker_server",
            )

        self.assertFalse(result["mutation_performed"])
        self.assertFalse(result["apply_requested"])
        self.assertEqual("time:canonical", result["package"]["service_binding"])
        self.assertEqual("time-dev-docker", result["registry_request"]["gateway_name"])
        self.assertEqual("time_dev_docker_server", result["registry_request"]["server_name"])
        self.assertEqual("http://time-transceiver:9209/mcp", result["registry_request"]["upstream_url"])
        self.assertEqual(["get_current_time", "convert_time"], result["registry_request"]["expected_tools"])
        self.assertEqual("npm-stdio-host", result["npm_stdio_host_request"]["host_service"])
        self.assertIn("server-instances/time-canonical/npm-stdio-service.json", result["npm_stdio_host_request"]["record_path"])
        self.assertFalse(result["target"]["env_values_recorded"])
        self.assertIn("dry-run; no ContextForge API calls", result["non_actions"])

    def test_apply_registers_gateway_refreshes_tools_and_creates_server(self) -> None:
        executor = load_executor()
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            package_path = root / "time-package.json"
            write_time_package(package_path, root)
            client = FakeClient()

            result = executor.run(
                package_path=package_path,
                upstream_url="http://time-transceiver:9209/mcp",
                gateway_name="time-dev-docker",
                server_name="time_dev_docker_server",
                apply=True,
                client=client,
                wait_attempts=1,
            )

            self.assertTrue(result["mutation_performed"])
            self.assertEqual("created", result["gateway"]["action"])
            self.assertEqual("created", result["server"]["action"])
            self.assertEqual(["time-dev-docker-get-current-time", "time-dev-docker-convert-time"], result["tool_names"])
            self.assertEqual(
                [
                    ("POST", "/gateways"),
                    ("POST", "/gateways/gateway-1/tools/refresh"),
                    ("POST", "/servers"),
                ],
                [(method, path) for method, path, _body in client.requests],
            )
            record_path = Path(result["npm_stdio_host_record"]["record_path"])
            self.assertTrue(record_path.exists())
            self.assertEqual("created", result["npm_stdio_host_record"]["action"])
            self.assertEqual("mcp-server-time", json.loads(record_path.read_text(encoding="utf-8"))["package"])

            second = executor.run(
                package_path=package_path,
                upstream_url="http://time-transceiver:9209/mcp",
                gateway_name="time-dev-docker",
                server_name="time_dev_docker_server",
                apply=True,
                client=client,
                wait_attempts=1,
            )
            self.assertEqual("already_applied", second["npm_stdio_host_record"]["action"])
            self.assertEqual(1, len(client.gateways))
            self.assertEqual(1, len(client.servers))

    def test_apply_rolls_back_created_host_record_and_gateway_on_refresh_failure(self) -> None:
        executor = load_executor()
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            package_path = root / "time-package.json"
            package = write_time_package(package_path, root)
            client = FailingRefreshClient()
            record_path = Path(
                package["install_artifact_contract"]["artifacts"]["npm_stdio_service_record"]["path"]
            )

            with self.assertRaises(executor.RuntimeApplyError) as ctx:
                executor.run(
                    package_path=package_path,
                    upstream_url="http://time-transceiver:9209/mcp",
                    gateway_name="time-dev-docker",
                    server_name="time_dev_docker_server",
                    apply=True,
                    client=client,
                    wait_attempts=1,
                )

            self.assertFalse(record_path.exists())
            self.assertEqual([], client.gateways)
            self.assertIn(("DELETE", "/gateways/gateway-failing"), [(method, path) for method, path, _body in client.requests])
            report = ctx.exception.failure_report
            self.assertEqual("tool_refresh", report["failed_stage"])
            self.assertEqual("passed", report["rollback_result"])
            self.assertTrue(
                any(action.get("action") == "rollback_npm_stdio_host_record" for action in report["rollback_actions_attempted"])
            )

    def test_apply_waits_for_delayed_expected_tool_visibility(self) -> None:
        executor = load_executor()
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            package_path = root / "time-package.json"
            write_time_package(package_path, root)
            client = DelayedToolClient()

            result = executor.run(
                package_path=package_path,
                upstream_url="http://time-transceiver:9209/mcp",
                gateway_name="time-dev-docker",
                server_name="time_dev_docker_server",
                apply=True,
                client=client,
                wait_attempts=2,
            )

        self.assertTrue(result["mutation_performed"])
        self.assertEqual(2, client.tool_reads)
        self.assertEqual(["time-dev-docker-get-current-time", "time-dev-docker-convert-time"], result["tool_names"])

    def test_apply_retries_transient_tool_refresh_failure(self) -> None:
        executor = load_executor()
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            package_path = root / "time-package.json"
            write_time_package(package_path, root)
            client = RefreshRetryClient()

            result = executor.run(
                package_path=package_path,
                upstream_url="http://time-transceiver:9209/mcp",
                gateway_name="time-dev-docker",
                server_name="time_dev_docker_server",
                apply=True,
                client=client,
                wait_attempts=2,
            )

        self.assertTrue(result["mutation_performed"])
        self.assertEqual(2, client.refresh_count)
        self.assertEqual(["time-dev-docker-get-current-time", "time-dev-docker-convert-time"], result["tool_names"])

    def test_apply_updates_existing_server_and_preserves_prompt_resource_associations(self) -> None:
        executor = load_executor()
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            package_path = root / "time-package.json"
            write_time_package(package_path, root)
            client = FakeClient()
            client.gateways.append({"id": "gateway-existing", "name": "time-dev-docker", "url": "old"})
            client.tools.append({"id": "tool-time-current", "name": "time-dev-docker-get-current-time", "gateway_id": "gateway-existing"})
            client.tools.append({"id": "tool-time-convert", "name": "time-dev-docker-convert-time", "gateway_id": "gateway-existing"})
            client.servers.append(
                {
                    "id": "server-existing",
                    "name": "time_dev_docker_server",
                    "associatedResources": ["resource-id"],
                    "associatedPrompts": ["prompt-id"],
                    "associatedA2aAgents": ["agent-id"],
                }
            )

            result = executor.run(
                package_path=package_path,
                upstream_url="http://time-transceiver:9209/mcp",
                gateway_name="time-dev-docker",
                server_name="time_dev_docker_server",
                apply=True,
                client=client,
                wait_attempts=1,
            )

        self.assertEqual("updated", result["gateway"]["action"])
        self.assertEqual("updated", result["server"]["action"])
        server_put = next(body for method, path, body in client.requests if method == "PUT" and path == "/servers/server-existing")
        self.assertEqual(["resource-id"], server_put["associatedResources"])
        self.assertEqual(["prompt-id"], server_put["associatedPrompts"])
        self.assertEqual(["agent-id"], server_put["associatedA2aAgents"])
        self.assertEqual(["tool-time-current", "tool-time-convert"], server_put["associatedTools"])

    def test_apply_rejects_url_match_with_different_gateway_name(self) -> None:
        executor = load_executor()
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            package_path = root / "time-package.json"
            write_time_package(package_path, root)
            client = FakeClient()
            client.gateways.append(
                {
                    "id": "gateway-existing",
                    "name": "different-time-name",
                    "url": "http://time-transceiver:9209/mcp",
                }
            )

            with self.assertRaisesRegex(RuntimeError, "refusing to rename or retag"):
                executor.run(
                    package_path=package_path,
                    upstream_url="http://time-transceiver:9209/mcp",
                    gateway_name="time-dev-docker",
                    server_name="time_dev_docker_server",
                    apply=True,
                    client=client,
                )

        self.assertFalse([request for request in client.requests if request[0] == "PUT"])

    def test_apply_rejects_name_match_when_url_belongs_to_different_gateway(self) -> None:
        executor = load_executor()
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            package_path = root / "time-package.json"
            write_time_package(package_path, root)
            client = FakeClient()
            client.gateways.append({"id": "gateway-name-match", "name": "time-dev-docker", "url": "http://old-time/mcp"})
            client.gateways.append({"id": "gateway-url-owner", "name": "other-time-gateway", "url": "http://time-transceiver:9209/mcp"})

            with self.assertRaisesRegex(RuntimeError, "refusing to also assign"):
                executor.run(
                    package_path=package_path,
                    upstream_url="http://time-transceiver:9209/mcp",
                    gateway_name="time-dev-docker",
                    server_name="time_dev_docker_server",
                    apply=True,
                    client=client,
                )

        self.assertFalse([request for request in client.requests if request[0] == "PUT"])

    def test_rejects_missing_expected_tools_in_package(self) -> None:
        executor = load_executor()
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            package_path = root / "time-package.json"
            package = write_time_package(package_path, root)
            package["contextforge_registration_plan"]["candidate_descriptor"]["expected_tools"] = []
            package_path.write_text(json.dumps(package), encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "expected tools are required"):
                executor.run(
                    package_path=package_path,
                    upstream_url="http://time-transceiver:9209/mcp",
                    gateway_name="time-dev-docker",
                    server_name="time_dev_docker_server",
                )

    def test_rejects_ambiguous_expected_tool_matches(self) -> None:
        executor = load_executor()
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            package_path = root / "time-package.json"
            write_time_package(package_path, root)
            client = FakeClient()
            client.gateways.append({"id": "gateway-existing", "name": "time-dev-docker", "url": "http://time-transceiver:9209/mcp"})
            client.tools.append({"id": "tool-current", "name": "time-dev-docker-get-current-time", "gateway_id": "gateway-existing"})
            client.tools.append({"id": "tool-current-shadow", "name": "shadow-get-current-time", "gateway_id": "gateway-existing"})
            client.tools.append({"id": "tool-convert", "name": "time-dev-docker-convert-time", "gateway_id": "gateway-existing"})

            with self.assertRaisesRegex(RuntimeError, "matched multiple gateway tools"):
                executor.run(
                    package_path=package_path,
                    upstream_url="http://time-transceiver:9209/mcp",
                    gateway_name="time-dev-docker",
                    server_name="time_dev_docker_server",
                    apply=True,
                    client=client,
                    wait_attempts=1,
                )

    def test_rejects_mutating_or_wrong_status_package(self) -> None:
        executor = load_executor()
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            package_path = root / "time-package.json"
            package = write_time_package(package_path, root)
            package["mutation_allowed"] = True
            package_path.write_text(json.dumps(package), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "must be non-mutating"):
                executor.run(package_path=package_path, upstream_url="http://time-transceiver:9209/mcp")

            package["mutation_allowed"] = False
            package["status"] = "source_only_onboarding_plan"
            package_path.write_text(json.dumps(package), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "package status"):
                executor.run(package_path=package_path, upstream_url="http://time-transceiver:9209/mcp")

    def test_rejects_runtime_package_without_npm_stdio_host_record_artifact(self) -> None:
        executor = load_executor()
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            package_path = root / "time-package.json"
            package = write_time_package(package_path, root)
            del package["install_artifact_contract"]["artifacts"]["npm_stdio_service_record"]
            package_path.write_text(json.dumps(package), encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "npm_stdio_service_record is required"):
                executor.run(package_path=package_path, upstream_url="http://time-transceiver:9209/mcp")

    def test_cli_dry_run_outputs_clean_json(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            package_path = root / "time-package.json"
            write_time_package(package_path, root)
            result = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "docker/contextforge-harness/scripts/apply_onboarding_runtime_package.py"),
                    "--package-json",
                    str(package_path),
                    "--upstream-url",
                    "http://time-transceiver:9209/mcp",
                    "--gateway-name",
                    "time-dev-docker",
                    "--server-name",
                    "time_dev_docker_server",
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
        self.assertEqual("time-dev-docker", data["registry_request"]["gateway_name"])

    def test_npm_stdio_host_records_cli_upserts_and_deletes_record(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            package_path = root / "time-package.json"
            write_time_package(package_path, root)
            script = REPO_ROOT / "docker/contextforge-harness/scripts/npm_stdio_host_records.py"

            upsert = subprocess.run(
                [sys.executable, str(script), "upsert", "--package-json", str(package_path)],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=20,
            )

            self.assertEqual(0, upsert.returncode, upsert.stderr)
            upsert_payload = json.loads(upsert.stdout)
            record_path = Path(upsert_payload["record_path"])
            self.assertTrue(record_path.exists())
            self.assertEqual("created", upsert_payload["action"])

            delete = subprocess.run(
                [sys.executable, str(script), "delete", "--project-root", str(root), "--service-binding", "time:canonical"],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=20,
            )

            self.assertEqual(0, delete.returncode, delete.stderr)
            self.assertFalse(record_path.exists())
            self.assertTrue(json.loads(delete.stdout)["ok"])


if __name__ == "__main__":
    unittest.main()
