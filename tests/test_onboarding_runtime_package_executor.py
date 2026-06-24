from __future__ import annotations

import importlib.util
import json
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import control_plane_project_state as project_state
import control_plane_service_onboarding_surfaces as surfaces
import project_init_common as common


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
    with mock.patch.object(
        surfaces,
        "fetch_npm_package_metadata",
        return_value={
            "registry": "npm",
            "package": "mcp-server-time",
            "latest": "1.0.1",
            "dist_tags": {"latest": "1.0.1"},
            "published_versions": ["1.0.0", "1.0.1"],
            "published_version_count": 2,
        },
    ):
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
        self.resources: list[dict[str, Any]] = []
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
        if method == "POST" and path == "/resources":
            payload = dict((body or {})["resource"])
            row = {"id": self._id("resource"), **payload}
            self.resources.append(row)
            return row
        if method == "PUT" and path.startswith("/resources/"):
            resource_id = path.rsplit("/", 1)[-1]
            row = next(resource for resource in self.resources if resource["id"] == resource_id)
            row.clear()
            row.update({"id": resource_id, **(body or {})})
            return row
        if method == "DELETE" and path.startswith("/resources/"):
            resource_id = path.rsplit("/", 1)[-1]
            self.resources = [resource for resource in self.resources if resource.get("id") != resource_id]
            return {"ok": True}
        raise AssertionError(f"unexpected request {method} {path}")

    def items(self, path: str) -> list[dict[str, Any]]:
        if path.startswith("/gateways"):
            return list(self.gateways)
        if path.startswith("/tools"):
            return list(self.tools)
        if path.startswith("/servers"):
            return list(self.servers)
        if path.startswith("/resources"):
            return list(self.resources)
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


class FailingServerClient(FakeClient):
    def request(self, method: str, path: str, body: dict | None = None):
        if method == "POST" and path == "/servers":
            self.requests.append((method, path, body))
            raise RuntimeError("simulated server creation failure")
        return super().request(method, path, body)


class FailingResourceCreateClient(FakeClient):
    def request(self, method: str, path: str, body: dict | None = None):
        if method == "POST" and path == "/resources":
            self.requests.append((method, path, body))
            raise RuntimeError("simulated resource creation failure")
        return super().request(method, path, body)


class SwitchableResourceFailureClient(FakeClient):
    def __init__(self) -> None:
        super().__init__()
        self.fail_resource_mutation = False

    def request(self, method: str, path: str, body: dict | None = None):
        if self.fail_resource_mutation and method in {"POST", "PUT"} and path.startswith("/resources"):
            self.requests.append((method, path, body))
            raise RuntimeError("simulated resource mutation failure")
        return super().request(method, path, body)


class FailingDeleteClient(FakeClient):
    def request(self, method: str, path: str, body: dict | None = None):
        if method == "DELETE" and (path.startswith("/resources/") or path.startswith("/gateways/")):
            self.requests.append((method, path, body))
            raise RuntimeError(f"simulated delete failure for {path}")
        return super().request(method, path, body)


class FakeHostRuntime:
    def __init__(self, *, fail_apply: bool = False) -> None:
        self.fail_apply = fail_apply
        self.applied = False
        self.deleted = False
        self.calls: list[str] = []
        self.applied_version_policies: list[str] = []

    def _endpoint(self, package: dict[str, Any]) -> dict[str, Any]:
        content = package["install_artifact_contract"]["artifacts"]["npm_stdio_service_record"]["content"]
        return dict(content["endpoint"])

    def apply(self, package: dict[str, Any]) -> dict[str, Any]:
        self.calls.append("apply")
        if self.fail_apply:
            raise RuntimeError("simulated host runtime failure")
        record_path = Path(package["install_artifact_contract"]["artifacts"]["npm_stdio_service_record"]["path"])
        record = json.loads(record_path.read_text(encoding="utf-8")) if record_path.exists() else {}
        self.applied_version_policies.append(str(record.get("version_policy") or ""))
        self.applied = True
        self.deleted = False
        return {
            "schema_uri": "contextforge://control-plane/npm-stdio-host-runtime/v1",
            "service_binding": package["service_provision_plan"]["service_binding"],
            "action": "created",
            "mutation_performed": True,
            "endpoint": self._endpoint(package),
            "running": True,
            "record_version_policy": str(record.get("version_policy") or ""),
        }

    def view(self, package: dict[str, Any]) -> dict[str, Any]:
        self.calls.append("view")
        return {
            "schema_uri": "contextforge://control-plane/npm-stdio-host-runtime/v1",
            "service_binding": package["service_provision_plan"]["service_binding"],
            "mutation_performed": False,
            "running": self.applied and not self.deleted,
            "endpoint": self._endpoint(package),
        }

    def delete(self, package: dict[str, Any]) -> dict[str, Any]:
        self.calls.append("delete")
        was_applied = self.applied and not self.deleted
        self.deleted = True
        return {
            "schema_uri": "contextforge://control-plane/npm-stdio-host-runtime/v1",
            "service_binding": package["service_provision_plan"]["service_binding"],
            "mutation_performed": was_applied,
            "rollback_result": "passed",
            "actions": [{"action": "remove_runtime_dir" if was_applied else "runtime_dir_absent", "ok": True}],
        }


class FakeProcess:
    pid = 999999
    returncode = None

    def poll(self):
        return None


class OnboardingRuntimePackageExecutorTests(unittest.TestCase):
    def test_dry_run_consumes_runtime_package_without_api_or_env_reads(self) -> None:
        executor = load_executor()
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            package_path = root / "time-package.json"
            package = write_time_package(package_path, root)
            endpoint_url = package["install_artifact_contract"]["artifacts"]["npm_stdio_service_record"]["content"]["endpoint"]["streamable_http_url"]

            result = executor.run(
                package_path=package_path,
                gateway_name="time-gateway",
                server_name="time-server",
            )

        self.assertFalse(result["mutation_performed"])
        self.assertFalse(result["apply_requested"])
        self.assertEqual("time:canonical", result["package"]["service_binding"])
        self.assertEqual("time-gateway", result["registry_request"]["gateway_name"])
        self.assertEqual("time-server", result["registry_request"]["server_name"])
        self.assertEqual(endpoint_url, result["registry_request"]["upstream_url"])
        self.assertEqual(["get_current_time", "convert_time"], result["registry_request"]["expected_tools"])
        self.assertEqual("npm-stdio-host", result["npm_stdio_host_request"]["host_service"])
        self.assertIn("server-instances/time-canonical/npm-stdio-service.json", result["npm_stdio_host_request"]["record_path"])
        self.assertEqual(endpoint_url, result["npm_stdio_host_request"]["runtime_endpoint"])
        self.assertFalse(result["target"]["env_values_recorded"])
        self.assertIn("dry-run; no ContextForge API calls", result["non_actions"])

    def test_apply_registers_gateway_refreshes_tools_and_creates_server(self) -> None:
        executor = load_executor()
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            package_path = root / "time-package.json"
            write_time_package(package_path, root)
            client = FakeClient()
            host_runtime = FakeHostRuntime()

            result = executor.run(
                package_path=package_path,
                gateway_name="time-gateway",
                server_name="time-server",
                apply=True,
                client=client,
                host_runtime=host_runtime,
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
                    ("POST", "/resources"),
                    ("POST", "/resources"),
                    ("POST", "/servers"),
                ],
                [(method, path) for method, path, _body in client.requests],
            )
            self.assertEqual(["apply"], host_runtime.calls)
            self.assertEqual(2, len(client.resources))
            self.assertEqual(
                [
                    "contextforge://service-specs/time/abstract/v1",
                    "contextforge://service-specs/time/details/usage/v1",
                ],
                [resource["uri"] for resource in client.resources],
            )
            server_post = next(body for method, path, body in client.requests if method == "POST" and path == "/servers")
            self.assertEqual(["resource-5", "resource-6"], server_post["server"]["associated_resources"])
            record_path = Path(result["npm_stdio_host_record"]["record_path"])
            self.assertTrue(record_path.exists())
            self.assertEqual("created", result["npm_stdio_host_record"]["action"])
            self.assertEqual("mcp-server-time", json.loads(record_path.read_text(encoding="utf-8"))["package"])
            manifest_path = record_path.parent / "instance.json"
            self.assertEqual(str(manifest_path), result["service_instance_manifest"]["path"])
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual("npm-stdio-host", manifest["managed_by"])
            self.assertEqual("time:canonical", manifest["service_binding"])
            self.assertEqual("time-server", manifest["contextforge"]["virtual_server"]["name"])
            self.assertEqual("gateway-1", manifest["contextforge"]["gateway"]["id"])
            discovered = common.discover_contextforge_hosted_services(
                project_root=root,
                server_instances_root=root / "server-instances",
            )
            services = {service["service_binding"]: service for service in discovered}
            self.assertIn("time:canonical", services)
            self.assertEqual("time-server", services["time:canonical"]["virtual_server"])

            second = executor.run(
                package_path=package_path,
                gateway_name="time-gateway",
                server_name="time-server",
                apply=True,
                client=client,
                host_runtime=host_runtime,
                wait_attempts=1,
            )
            self.assertEqual("already_applied", second["npm_stdio_host_record"]["action"])
            self.assertEqual("already_applied", second["service_instance_manifest"]["action"])
            self.assertEqual(1, len(client.gateways))
            self.assertEqual(1, len(client.servers))

    def test_apply_rolls_back_created_host_record_and_gateway_on_refresh_failure(self) -> None:
        executor = load_executor()
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            package_path = root / "time-package.json"
            package = write_time_package(package_path, root)
            client = FailingRefreshClient()
            host_runtime = FakeHostRuntime()
            record_path = Path(
                package["install_artifact_contract"]["artifacts"]["npm_stdio_service_record"]["path"]
            )

            with self.assertRaises(executor.RuntimeApplyError) as ctx:
                executor.run(
                    package_path=package_path,
                    gateway_name="time-gateway",
                    server_name="time-server",
                    apply=True,
                    client=client,
                    host_runtime=host_runtime,
                    wait_attempts=1,
                )

            self.assertFalse(record_path.exists())
            self.assertEqual(["apply", "delete"], host_runtime.calls)
            self.assertEqual([], client.gateways)
            self.assertIn(("DELETE", "/gateways/gateway-failing"), [(method, path) for method, path, _body in client.requests])
            report = ctx.exception.failure_report
            self.assertEqual("tool_refresh", report["failed_stage"])
            self.assertEqual("passed", report["rollback_result"])
            self.assertTrue(
                any(action.get("action") == "rollback_npm_stdio_host_record" for action in report["rollback_actions_attempted"])
            )

    def test_apply_rolls_back_prompt_library_resources_on_server_failure(self) -> None:
        executor = load_executor()
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            package_path = root / "time-package.json"
            write_time_package(package_path, root)
            client = FailingServerClient()
            host_runtime = FakeHostRuntime()

            with self.assertRaises(executor.RuntimeApplyError) as ctx:
                executor.run(
                    package_path=package_path,
                    gateway_name="time-gateway",
                    server_name="time-server",
                    apply=True,
                    client=client,
                    host_runtime=host_runtime,
                    wait_attempts=1,
                )

            self.assertEqual([], client.resources)
            self.assertEqual([], client.gateways)
            self.assertEqual(["apply", "delete"], host_runtime.calls)
            report = ctx.exception.failure_report
            self.assertEqual("virtual_server", report["failed_stage"])
            self.assertEqual("passed", report["rollback_result"])
            actions = [action.get("action") for action in report["rollback_actions_attempted"]]
            self.assertIn("delete_created_resource", actions)
            self.assertIn("rollback_npm_stdio_host_record", actions)

    def test_apply_restores_existing_gateway_when_later_stage_fails(self) -> None:
        executor = load_executor()
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            package_path = root / "time-package.json"
            write_time_package(package_path, root)
            client = FailingResourceCreateClient()
            host_runtime = FakeHostRuntime()
            original_gateway = {"id": "gateway-existing", "name": "time-gateway", "url": "http://old-time/mcp", "tags": ["old"]}
            client.gateways.append(dict(original_gateway))
            client.tools.append({"id": "tool-current", "name": "time-dev-docker-get-current-time", "gateway_id": "gateway-existing"})
            client.tools.append({"id": "tool-convert", "name": "time-dev-docker-convert-time", "gateway_id": "gateway-existing"})

            with self.assertRaises(executor.RuntimeApplyError) as ctx:
                executor.run(
                    package_path=package_path,
                    gateway_name="time-gateway",
                    server_name="time-server",
                    apply=True,
                    client=client,
                    host_runtime=host_runtime,
                    wait_attempts=1,
                )

            self.assertEqual(original_gateway["url"], client.gateways[0]["url"])
            self.assertEqual(original_gateway["tags"], client.gateways[0]["tags"])
            self.assertEqual(["apply", "delete"], host_runtime.calls)
            actions = [action.get("action") for action in ctx.exception.failure_report["rollback_actions_attempted"]]
            self.assertIn("restore_previous_gateway", actions)

    def test_apply_failure_restores_existing_host_runtime_instead_of_deleting_it(self) -> None:
        executor = load_executor()
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            package_path = root / "time-package.json"
            package = write_time_package(package_path, root)
            client = SwitchableResourceFailureClient()
            host_runtime = FakeHostRuntime()

            executor.run(
                package_path=package_path,
                gateway_name="time-gateway",
                server_name="time-server",
                apply=True,
                client=client,
                host_runtime=host_runtime,
                wait_attempts=1,
            )
            record_path = Path(package["install_artifact_contract"]["artifacts"]["npm_stdio_service_record"]["path"])
            self.assertEqual("1.0.0", json.loads(record_path.read_text(encoding="utf-8"))["version_policy"])

            updated_package = json.loads(json.dumps(package))
            updated_record = updated_package["install_artifact_contract"]["artifacts"]["npm_stdio_service_record"]
            updated_record["content"]["version_policy"] = "1.0.1"
            updated_record["content"]["prompt_library"]["abstract_prompt"] = "Updated prompt content."
            package_path.write_text(json.dumps(updated_package), encoding="utf-8")
            client.fail_resource_mutation = True

            with self.assertRaises(executor.RuntimeApplyError) as ctx:
                executor.run(
                    package_path=package_path,
                    gateway_name="time-gateway",
                    server_name="time-server",
                    apply=True,
                    client=client,
                    host_runtime=host_runtime,
                    wait_attempts=1,
                )

            self.assertEqual("1.0.0", json.loads(record_path.read_text(encoding="utf-8"))["version_policy"])
            self.assertEqual(["apply", "apply", "apply"], host_runtime.calls)
            self.assertEqual(["1.0.0", "1.0.1", "1.0.0"], host_runtime.applied_version_policies)
            self.assertNotIn("delete", host_runtime.calls)
            actions = [action.get("action") for action in ctx.exception.failure_report["rollback_actions_attempted"]]
            self.assertIn("rollback_npm_stdio_host_runtime_to_previous", actions)

    def test_delete_removes_server_prompt_library_resources_gateway_and_host_record(self) -> None:
        executor = load_executor()
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            package_path = root / "time-package.json"
            write_time_package(package_path, root)
            client = FakeClient()
            host_runtime = FakeHostRuntime()
            empty_view = executor.run(
                package_path=package_path,
                gateway_name="time-gateway",
                server_name="time-server",
                view=True,
                client=client,
                host_runtime=host_runtime,
            )
            self.assertFalse(empty_view["mutation_performed"])
            self.assertFalse(empty_view["host_record"]["record_exists"])
            self.assertFalse(empty_view["contextforge"]["gateway"]["present"])
            self.assertFalse(empty_view["contextforge"]["virtual_server"]["present"])
            created = executor.run(
                package_path=package_path,
                gateway_name="time-gateway",
                server_name="time-server",
                apply=True,
                client=client,
                host_runtime=host_runtime,
                wait_attempts=1,
            )
            record_path = Path(created["npm_stdio_host_record"]["record_path"])
            self.assertTrue(record_path.exists())
            self.assertTrue((record_path.parent / "instance.json").exists())
            self.assertEqual(1, len(client.gateways))
            self.assertEqual(1, len(client.servers))
            self.assertEqual(2, len(client.resources))
            applied_view = executor.run(
                package_path=package_path,
                gateway_name="time-gateway",
                server_name="time-server",
                view=True,
                client=client,
                host_runtime=host_runtime,
            )
            self.assertFalse(applied_view["mutation_performed"])
            self.assertTrue(applied_view["host_record"]["record_exists"])
            self.assertTrue(applied_view["contextforge"]["gateway"]["present"])
            self.assertTrue(applied_view["contextforge"]["virtual_server"]["present"])
            self.assertEqual([True, True], [item["present"] for item in applied_view["contextforge"]["prompt_library_resources"]])

            deleted = executor.run(
                package_path=package_path,
                gateway_name="time-gateway",
                server_name="time-server",
                delete=True,
                client=client,
                host_runtime=host_runtime,
            )

            self.assertTrue(deleted["mutation_performed"])
            self.assertEqual([], client.gateways)
            self.assertEqual([], client.servers)
            self.assertEqual([], client.resources)
            self.assertFalse(record_path.exists())
            self.assertFalse((record_path.parent / "instance.json").exists())
            actions = [action["action"] for action in deleted["delete_actions"]]
            self.assertIn("delete_managed_instance_manifest", actions)
            self.assertIn("delete_virtual_server", actions)
            self.assertIn("delete_prompt_library_resource", actions)
            self.assertIn("delete_gateway", actions)
            self.assertIn("delete_npm_stdio_host_runtime", actions)
            self.assertIn("delete_npm_stdio_host_record", actions)

            deleted_again = executor.run(
                package_path=package_path,
                gateway_name="time-gateway",
                server_name="time-server",
                delete=True,
                client=client,
                host_runtime=host_runtime,
            )
            self.assertFalse(deleted_again["mutation_performed"])
            absent_actions = [action["action"] for action in deleted_again["delete_actions"]]
            self.assertIn("virtual_server_absent", absent_actions)
            self.assertIn("prompt_library_resource_absent", absent_actions)
            self.assertIn("gateway_absent", absent_actions)
            self.assertIn("npm_stdio_host_record_absent", absent_actions)

    def test_delete_continues_after_contextforge_delete_failure(self) -> None:
        executor = load_executor()
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            package_path = root / "time-package.json"
            created = write_time_package(package_path, root)
            client = FailingDeleteClient()
            host_runtime = FakeHostRuntime()
            executor.run(
                package_path=package_path,
                gateway_name="time-gateway",
                server_name="time-server",
                apply=True,
                client=client,
                host_runtime=host_runtime,
                wait_attempts=1,
            )
            record_path = Path(created["install_artifact_contract"]["artifacts"]["npm_stdio_service_record"]["path"])

            deleted = executor.run(
                package_path=package_path,
                gateway_name="time-gateway",
                server_name="time-server",
                delete=True,
                client=client,
                host_runtime=host_runtime,
            )

            self.assertFalse(record_path.exists())
            self.assertEqual(["apply", "delete"], host_runtime.calls)
            self.assertTrue(any(action["action"] == "delete_gateway" and not action["ok"] for action in deleted["delete_actions"]))
            self.assertTrue(any(action["action"] == "delete_prompt_library_resource" and not action["ok"] for action in deleted["delete_actions"]))
            self.assertTrue(any(action["action"] == "delete_npm_stdio_host_record" and action["ok"] for action in deleted["delete_actions"]))
            self.assertEqual("delete action failed", deleted["rollback_boundary"]["residual_cleanup_risk"])

    def test_apply_waits_for_delayed_expected_tool_visibility(self) -> None:
        executor = load_executor()
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            package_path = root / "time-package.json"
            write_time_package(package_path, root)
            client = DelayedToolClient()
            host_runtime = FakeHostRuntime()

            result = executor.run(
                package_path=package_path,
                gateway_name="time-gateway",
                server_name="time-server",
                apply=True,
                client=client,
                host_runtime=host_runtime,
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
            host_runtime = FakeHostRuntime()

            result = executor.run(
                package_path=package_path,
                gateway_name="time-gateway",
                server_name="time-server",
                apply=True,
                client=client,
                host_runtime=host_runtime,
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
            host_runtime = FakeHostRuntime()
            client.gateways.append({"id": "gateway-existing", "name": "time-gateway", "url": "old"})
            client.tools.append({"id": "tool-time-current", "name": "time-dev-docker-get-current-time", "gateway_id": "gateway-existing"})
            client.tools.append({"id": "tool-time-convert", "name": "time-dev-docker-convert-time", "gateway_id": "gateway-existing"})
            client.servers.append(
                {
                    "id": "server-existing",
                    "name": "time-server",
                    "associatedResources": ["resource-id"],
                    "associatedPrompts": ["prompt-id"],
                    "associatedA2aAgents": ["agent-id"],
                }
            )

            result = executor.run(
                package_path=package_path,
                gateway_name="time-gateway",
                server_name="time-server",
                apply=True,
                client=client,
                host_runtime=host_runtime,
                wait_attempts=1,
            )

        self.assertEqual("updated", result["gateway"]["action"])
        self.assertEqual("updated", result["server"]["action"])
        server_put = next(body for method, path, body in client.requests if method == "PUT" and path == "/servers/server-existing")
        self.assertEqual(["resource-id", "resource-1", "resource-2"], server_put["associatedResources"])
        self.assertEqual(["prompt-id"], server_put["associatedPrompts"])
        self.assertEqual(["agent-id"], server_put["associatedA2aAgents"])
        self.assertEqual(["tool-time-current", "tool-time-convert"], server_put["associatedTools"])

    def test_apply_rejects_url_match_with_different_gateway_name(self) -> None:
        executor = load_executor()
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            package_path = root / "time-package.json"
            package = write_time_package(package_path, root)
            client = FakeClient()
            host_runtime = FakeHostRuntime()
            endpoint_url = package["install_artifact_contract"]["artifacts"]["npm_stdio_service_record"]["content"]["endpoint"]["streamable_http_url"]
            client.gateways.append(
                {
                    "id": "gateway-existing",
                    "name": "different-time-name",
                    "url": endpoint_url,
                }
            )

            with self.assertRaisesRegex(RuntimeError, "refusing to rename or retag"):
                executor.run(
                    package_path=package_path,
                    gateway_name="time-gateway",
                    server_name="time-server",
                    apply=True,
                    client=client,
                    host_runtime=host_runtime,
                )

        self.assertFalse([request for request in client.requests if request[0] == "PUT"])

    def test_apply_rejects_name_match_when_url_belongs_to_different_gateway(self) -> None:
        executor = load_executor()
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            package_path = root / "time-package.json"
            package = write_time_package(package_path, root)
            client = FakeClient()
            host_runtime = FakeHostRuntime()
            endpoint_url = package["install_artifact_contract"]["artifacts"]["npm_stdio_service_record"]["content"]["endpoint"]["streamable_http_url"]
            client.gateways.append({"id": "gateway-name-match", "name": "time-gateway", "url": "http://old-time/mcp"})
            client.gateways.append({"id": "gateway-url-owner", "name": "other-time-gateway", "url": endpoint_url})

            with self.assertRaisesRegex(RuntimeError, "refusing to also assign"):
                executor.run(
                    package_path=package_path,
                    gateway_name="time-gateway",
                    server_name="time-server",
                    apply=True,
                    client=client,
                    host_runtime=host_runtime,
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
                    gateway_name="time-gateway",
                    server_name="time-server",
                )

    def test_rejects_ambiguous_expected_tool_matches(self) -> None:
        executor = load_executor()
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            package_path = root / "time-package.json"
            package = write_time_package(package_path, root)
            client = FakeClient()
            host_runtime = FakeHostRuntime()
            endpoint_url = package["install_artifact_contract"]["artifacts"]["npm_stdio_service_record"]["content"]["endpoint"]["streamable_http_url"]
            client.gateways.append({"id": "gateway-existing", "name": "time-gateway", "url": endpoint_url})
            client.tools.append({"id": "tool-current", "name": "time-dev-docker-get-current-time", "gateway_id": "gateway-existing"})
            client.tools.append({"id": "tool-current-shadow", "name": "shadow-get-current-time", "gateway_id": "gateway-existing"})
            client.tools.append({"id": "tool-convert", "name": "time-dev-docker-convert-time", "gateway_id": "gateway-existing"})

            with self.assertRaisesRegex(RuntimeError, "matched multiple gateway tools"):
                executor.run(
                    package_path=package_path,
                    gateway_name="time-gateway",
                    server_name="time-server",
                    apply=True,
                    client=client,
                    host_runtime=host_runtime,
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
                executor.run(package_path=package_path)

            package["mutation_allowed"] = False
            package["status"] = "source_only_onboarding_plan"
            package_path.write_text(json.dumps(package), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "package status"):
                executor.run(package_path=package_path)

    def test_rejects_runtime_package_without_npm_stdio_host_record_artifact(self) -> None:
        executor = load_executor()
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            package_path = root / "time-package.json"
            package = write_time_package(package_path, root)
            del package["install_artifact_contract"]["artifacts"]["npm_stdio_service_record"]
            package_path.write_text(json.dumps(package), encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "npm_stdio_service_record is required"):
                executor.run(package_path=package_path)

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
                    "--gateway-name",
                    "time-gateway",
                    "--server-name",
                    "time-server",
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
        self.assertEqual("time-gateway", data["registry_request"]["gateway_name"])

    def test_runtime_package_parser_allows_view_and_delete_without_upstream_url(self) -> None:
        executor = load_executor()

        view_args = executor.build_parser().parse_args(["--package-json", "time-package.json", "--view"])
        delete_args = executor.build_parser().parse_args(["--package-json", "time-package.json", "--delete"])

        self.assertEqual("", view_args.upstream_url)
        self.assertTrue(view_args.view)
        self.assertEqual("", delete_args.upstream_url)
        self.assertTrue(delete_args.delete)

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

            view = subprocess.run(
                [sys.executable, str(script), "view", "--project-root", str(root), "--service-binding", "time:canonical"],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=20,
            )

            self.assertEqual(0, view.returncode, view.stderr)
            view_payload = json.loads(view.stdout)
            self.assertFalse(view_payload["mutation_performed"])
            self.assertTrue(view_payload["record_exists"])
            self.assertEqual("mcp-server-time", view_payload["record"]["package"])

            package = json.loads(package_path.read_text(encoding="utf-8"))
            record = package["install_artifact_contract"]["artifacts"]["npm_stdio_service_record"]
            record["content"]["version_policy"] = "1.0.1"
            package_path.write_text(json.dumps(package), encoding="utf-8")
            update = subprocess.run(
                [sys.executable, str(script), "upsert", "--package-json", str(package_path)],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=20,
            )

            self.assertEqual(0, update.returncode, update.stderr)
            update_payload = json.loads(update.stdout)
            self.assertEqual("updated", update_payload["action"])
            self.assertEqual(str(record_path), update_payload["record_path"])

            updated_view = subprocess.run(
                [sys.executable, str(script), "view", "--project-root", str(root), "--service-binding", "time:canonical"],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=20,
            )

            self.assertEqual(0, updated_view.returncode, updated_view.stderr)
            updated_payload = json.loads(updated_view.stdout)
            self.assertEqual("1.0.1", updated_payload["record"]["version_policy"])

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
            self.assertFalse(record_path.parent.exists())
            self.assertTrue(json.loads(delete.stdout)["ok"])

    def test_npm_stdio_host_runtime_materializes_record_into_bridge_state(self) -> None:
        runtime = load_executor().npm_stdio_host_runtime
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            package_path = root / "time-package.json"
            package = write_time_package(package_path, root)
            record_content = package["install_artifact_contract"]["artifacts"]["npm_stdio_service_record"]["content"]
            record_content["environment"] = {
                "required_secret_names": ["SECRET_ENV"],
                "variables": [
                    {"name": "VISIBLE_ENV", "secret": False, "value": "visible-value"},
                    {"name": "SECOND_VISIBLE_ENV", "secret": False, "value": "second-value"},
                    {"name": "SECRET_ENV", "secret": True, "value": "do-not-pass"},
                ],
                "values": {"VISIBLE_ENV": "visible-value"},
                "non_secret_placeholders_only": True,
            }
            package_path.write_text(json.dumps(package), encoding="utf-8")
            record_result, _rollback = runtime.npm_stdio_host_records.upsert_from_runtime_package(package)
            calls: list[list[str]] = []
            popen_envs: list[dict[str, str]] = []

            def fake_run(command, **_kwargs):
                calls.append(list(command))
                return subprocess.CompletedProcess(command, 0, "", "")

            def fake_popen(command, **kwargs):
                calls.append(list(command))
                popen_envs.append(dict(kwargs.get("env") or {}))
                return FakeProcess()

            original_wait = runtime.wait_for_bridge_endpoint
            runtime.wait_for_bridge_endpoint = lambda endpoint, process: {"ready": True, "attempts": 1}
            try:
                applied = runtime.apply_service(root, "time:canonical", runner=fake_run, popen=fake_popen)
            finally:
                runtime.wait_for_bridge_endpoint = original_wait

            self.assertEqual("created", applied["action"])
            self.assertEqual("time:canonical", applied["service_binding"])
            self.assertEqual(record_result["record_path"], applied["record_path"])
            self.assertEqual(package["install_artifact_contract"]["artifacts"]["npm_stdio_service_record"]["content"]["endpoint"], applied["endpoint"])
            self.assertTrue(Path(applied["runtime_dir"]).exists())
            self.assertTrue(Path(applied["log_path"]).exists())
            self.assertEqual("npm", calls[0][0])
            self.assertIn("mcp-server-time@1.0.0", calls[0])
            self.assertIn("mcpgateway.translate", calls[1])
            self.assertIn("uvx mcp-server-time --local-timezone UTC", calls[1])
            self.assertIn(str(Path(applied["runtime_dir"]) / "package" / "node_modules" / ".bin"), popen_envs[0]["PATH"])
            self.assertEqual("visible-value", popen_envs[0]["VISIBLE_ENV"])
            self.assertEqual("second-value", popen_envs[0]["SECOND_VISIBLE_ENV"])
            self.assertNotEqual("do-not-pass", popen_envs[0].get("SECRET_ENV"))

            updated_package = json.loads(json.dumps(package))
            updated_record = updated_package["install_artifact_contract"]["artifacts"]["npm_stdio_service_record"]
            updated_record["content"]["stdio"]["args"] = ["mcp-server-time", "--local-timezone", "America/Chicago"]
            runtime.npm_stdio_host_records.upsert_from_runtime_package(updated_package)
            runtime.wait_for_bridge_endpoint = lambda endpoint, process: {"ready": True, "attempts": 1}
            try:
                updated = runtime.apply_service(root, "time:canonical", runner=fake_run, popen=fake_popen)
            finally:
                runtime.wait_for_bridge_endpoint = original_wait

            self.assertEqual("updated", updated["action"])
            self.assertNotEqual(applied["content_digest"], updated["content_digest"])
            self.assertIn("uvx mcp-server-time --local-timezone America/Chicago", calls[-1])

            viewed = runtime.view_service(root, "time:canonical")
            self.assertFalse(viewed["mutation_performed"])
            self.assertEqual("time:canonical", viewed["service_binding"])

            deleted = runtime.delete_service(root, "time:canonical")
            self.assertEqual("passed", deleted["rollback_result"])
            self.assertFalse(Path(applied["runtime_dir"]).exists())

    def test_npm_stdio_host_runtime_resolves_package_id_command_to_installed_bin(self) -> None:
        runtime = load_executor().npm_stdio_host_runtime
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            package_path = root / "memory-package.json"
            package = surfaces.build_service_onboarding_runtime_apply_package(
                str(root),
                {
                    "candidate_service": "memory",
                    "operator_goal": "Add project memory.",
                    "source_path": "https://github.com/modelcontextprotocol/servers/tree/main/src/memory",
                    "backend_package": "@modelcontextprotocol/server-memory",
                    "transport_type": "stdio",
                    "localization_type": "project_scoped",
                    "functional_type": "filesystem_content",
                    "state_type": "local_filesystem_state",
                    "credential_boundary": "no credentials required",
                    "expected_tools": ["read_graph"],
                    **{
                        **npm_stdio_required_payload(),
                        "package_version": "2026.1.26",
                        "package_arguments": ["-y", "@modelcontextprotocol/server-memory"],
                        "tool_schemas": {
                            "read_graph": {
                                "description": "Return the complete persisted knowledge graph.",
                                "inputSchema": {"type": "object", "properties": {}, "required": []},
                            }
                        },
                    },
                },
            )
            record = package["install_artifact_contract"]["artifacts"]["npm_stdio_service_record"]["content"]
            service_binding = str(record["service_binding"])
            record["stdio"]["command"] = "@modelcontextprotocol/server-memory"
            record["stdio"]["args"] = ["-y", "@modelcontextprotocol/server-memory"]
            package_path.write_text(json.dumps(package), encoding="utf-8")
            runtime.npm_stdio_host_records.upsert_from_runtime_package(package)
            metadata_path = (
                runtime.service_dir(root, service_binding)
                / "package"
                / "node_modules"
                / "@modelcontextprotocol"
                / "server-memory"
                / "package.json"
            )
            metadata_path.parent.mkdir(parents=True, exist_ok=True)
            metadata_path.write_text(
                json.dumps({"name": "@modelcontextprotocol/server-memory", "bin": {"mcp-server-memory": "dist/index.js"}}),
                encoding="utf-8",
            )
            calls: list[list[str]] = []

            def fake_run(command, **_kwargs):
                calls.append(list(command))
                return subprocess.CompletedProcess(command, 0, "", "")

            def fake_popen(command, **kwargs):
                calls.append(list(command))
                return FakeProcess()

            original_wait = runtime.wait_for_bridge_endpoint
            runtime.wait_for_bridge_endpoint = lambda endpoint, process: {"ready": True, "attempts": 1}
            try:
                applied = runtime.apply_service(root, service_binding, runner=fake_run, popen=fake_popen)
            finally:
                runtime.wait_for_bridge_endpoint = original_wait

            self.assertEqual("created", applied["action"])
            self.assertIn("mcp-server-memory", calls[1])
            self.assertNotIn("@modelcontextprotocol/server-memory -y @modelcontextprotocol/server-memory", calls[1])

    def test_npm_stdio_host_runtime_fails_closed_when_endpoint_port_is_occupied(self) -> None:
        runtime = load_executor().npm_stdio_host_runtime
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp, socket.socket() as listener:
            root = Path(tmp).resolve()
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            occupied_port = listener.getsockname()[1]
            package_path = root / "time-package.json"
            package = write_time_package(package_path, root)
            record = package["install_artifact_contract"]["artifacts"]["npm_stdio_service_record"]["content"]
            record["endpoint"] = {
                "host": "127.0.0.1",
                "port": occupied_port,
                "container_url": f"http://npm-stdio-host:{occupied_port}/mcp",
                "streamable_http_url": f"http://npm-stdio-host:{occupied_port}/mcp",
                "sse_url": f"http://npm-stdio-host:{occupied_port}/sse",
            }
            package_path.write_text(json.dumps(package), encoding="utf-8")
            runtime.npm_stdio_host_records.upsert_from_runtime_package(package)
            popen_called = False

            def fake_run(command, **_kwargs):
                return subprocess.CompletedProcess(command, 0, "", "")

            def fake_popen(command, **kwargs):
                nonlocal popen_called
                popen_called = True
                return FakeProcess()

            with self.assertRaisesRegex(RuntimeError, "endpoint port is already in use"):
                runtime.apply_service(root, "time:canonical", runner=fake_run, popen=fake_popen)

            self.assertFalse(popen_called)
            self.assertIsNone(runtime.read_state(root, "time:canonical"))

    def test_service_guidance_resources_shape_contextforge_scanner_trigger_words(self) -> None:
        executor = load_executor()
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            package_path = root / "time-package.json"
            package = write_time_package(package_path, root)
            record = package["install_artifact_contract"]["artifacts"]["npm_stdio_service_record"]["content"]
            record["prompt_library"]["abstract_prompt"] = "Select time tools and delete stale assumptions."
            record["prompt_library"]["detail_prompts"]["usage"] = "Delete nothing; select one timezone."

            resources = executor.service_guidance_resource_bodies(package, gateway_id="gateway-1")

        contents = "\n".join(resource["content"] for resource in resources).lower()
        self.assertNotIn("select ", contents)
        self.assertNotIn("delete ", contents)
        self.assertIn("choose time tools", contents)
        self.assertIn("remove stale assumptions", contents)

    def test_npm_stdio_host_runtime_restores_previous_bridge_after_failed_modify_launch(self) -> None:
        runtime = load_executor().npm_stdio_host_runtime
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            package_path = root / "time-package.json"
            package = write_time_package(package_path, root)
            runtime.npm_stdio_host_records.upsert_from_runtime_package(package)

            def fake_run(command, **_kwargs):
                return subprocess.CompletedProcess(command, 0, "", "")

            def fake_popen_ok(command, **kwargs):
                return FakeProcess()

            original_running = runtime.bridge_state_running
            original_wait = runtime.wait_for_bridge_endpoint
            try:
                runtime.bridge_state_running = lambda state: bool(state)
                runtime.wait_for_bridge_endpoint = lambda endpoint, process: {"ready": True, "attempts": 1}
                applied = runtime.apply_service(root, "time:canonical", runner=fake_run, popen=fake_popen_ok)
                updated_package = json.loads(json.dumps(package))
                updated_record = updated_package["install_artifact_contract"]["artifacts"]["npm_stdio_service_record"]
                updated_record["content"]["stdio"]["args"] = ["mcp-server-time", "--local-timezone", "America/Chicago"]
                runtime.npm_stdio_host_records.upsert_from_runtime_package(updated_package)
                calls = {"count": 0}

                class FailedProcess:
                    pid = 1000000
                    returncode = 2

                    def poll(self):
                        return 2

                def fake_popen_fail_then_ok(command, **kwargs):
                    calls["count"] += 1
                    return FailedProcess() if calls["count"] == 1 else FakeProcess()

                with self.assertRaisesRegex(RuntimeError, "previous runtime restored"):
                    runtime.apply_service(root, "time:canonical", runner=fake_run, popen=fake_popen_fail_then_ok)

                state = runtime.read_state(root, "time:canonical")
                self.assertEqual("rollback_restored_previous_runtime", state["action"])
                self.assertEqual(applied["content_digest"], state["content_digest"])
            finally:
                runtime.wait_for_bridge_endpoint = original_wait
                runtime.bridge_state_running = original_running

    def test_npm_stdio_endpoint_allocation_avoids_existing_record_port(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            first = surfaces.npm_stdio_endpoint_port("service12:canonical")
            index_dir = root / "server-instances" / "npm-stdio-host"
            other_record = root / "server-instances" / "service12-canonical" / "npm-stdio-service.json"
            other_record.parent.mkdir(parents=True, exist_ok=True)
            other_record.write_text(json.dumps({"endpoint": {"port": first}}), encoding="utf-8")
            index_dir.mkdir(parents=True, exist_ok=True)
            (index_dir / "index.json").write_text(
                json.dumps(
                    {
                        "records": {
                            "service12:canonical": {
                                "record_path": str(other_record.relative_to(root)),
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )

            self.assertNotEqual(first, surfaces.npm_stdio_endpoint_port("service13:canonical", project_root=root))
            self.assertNotEqual(
                surfaces.npm_stdio_endpoint_port("service12:canonical"),
                surfaces.npm_stdio_endpoint_port("service13:canonical"),
            )


if __name__ == "__main__":
    unittest.main()
