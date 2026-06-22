#!/usr/bin/env python3
"""Apply or dry-run an onboarding runtime/apply package against dev ContextForge."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Mapping, Protocol


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import npm_stdio_host_records

DEFAULT_ENV_FILE = ROOT / "env" / "contextforge.env"
DEFAULT_BASE_URL = "http://127.0.0.1:4445"
OWNER = "admin@contextforge-harness.dev"
SCHEMA_URI = "contextforge://control-plane/service-onboarding-runtime-package-apply/v1"
VISIBILITY = "public"


class ContextForgeClient(Protocol):
    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        ...

    def items(self, path: str) -> list[dict[str, Any]]:
        ...


class RuntimeApplyError(RuntimeError):
    def __init__(self, message: str, *, failure_report: dict[str, Any]):
        super().__init__(message)
        self.failure_report = failure_report


class HttpContextForgeClient:
    def __init__(self, token: str, *, base_url: str):
        self.token = token
        self.base_url = base_url.rstrip("/")

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        headers = {"Accept": "application/json", "Authorization": f"Bearer {self.token}"}
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(f"{self.base_url}{path}", data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            raise RuntimeError(f"{method} {path} failed: HTTP {exc.code} {exc.reason}: {detail}") from exc
        return json.loads(payload) if payload else None

    def items(self, path: str) -> list[dict[str, Any]]:
        return items(self.request("GET", path))


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value.strip().strip("\"'")
    return values


def login(base_url: str, env: Mapping[str, str]) -> str:
    email = env.get("PLATFORM_ADMIN_EMAIL")
    password = env.get("PLATFORM_ADMIN_PASSWORD")
    if not email or not password:
        raise RuntimeError("missing PLATFORM_ADMIN_EMAIL or PLATFORM_ADMIN_PASSWORD in harness env")
    response = target_request("POST", base_url, "/auth/login", body={"email": email, "password": password})
    token = response.get("access_token") if isinstance(response, dict) else None
    if not isinstance(token, str) or not token:
        raise RuntimeError("ContextForge login did not return an access token")
    return token


def target_request(method: str, base_url: str, path: str, body: dict[str, Any] | None = None) -> Any:
    headers = {"Accept": "application/json"}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(f"{base_url.rstrip('/')}{path}", data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = response.read()
    return json.loads(payload) if payload else None


def load_target_client(base_url: str, env_file: Path) -> HttpContextForgeClient:
    return HttpContextForgeClient(login(base_url, read_env(env_file)), base_url=base_url)


def items(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        return [item for item in data["items"] if isinstance(item, dict)]
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return []


def row_id(row: Mapping[str, Any]) -> str:
    value = row.get("id")
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"row missing string id: {row}")
    return value


def by_name(rows: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    return next((row for row in rows if row.get("name") == name), None)


def by_url(rows: list[dict[str, Any]], url: str) -> dict[str, Any] | None:
    return next((row for row in rows if row.get("url") == url), None)


def tool_gateway_id(tool: Mapping[str, Any]) -> str | None:
    value = tool.get("gatewayId") or tool.get("gateway_id")
    return str(value) if value else None


def associated_ids(existing: Mapping[str, Any], camel: str, snake: str) -> list[str]:
    values = existing.get(camel) or existing.get(snake) or []
    return [str(value) for value in values if isinstance(value, str)]


def sanitize_error(exc: BaseException) -> str:
    return re.sub(r"Bearer\s+[A-Za-z0-9._~+/=-]+", "Bearer <redacted>", str(exc))


def load_package(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError("runtime/apply package must be a JSON object")
    validate_package(data)
    return data


def validate_package(package: Mapping[str, Any]) -> None:
    if package.get("status") != "service_onboarding_runtime_apply_package":
        raise RuntimeError("package status must be service_onboarding_runtime_apply_package")
    if package.get("mutation_allowed") is not False:
        raise RuntimeError("runtime/apply package must be non-mutating")
    if not isinstance(package.get("service_provision_plan"), Mapping):
        raise RuntimeError("runtime/apply package is missing service_provision_plan")
    if not isinstance(package.get("contextforge_registration_plan"), Mapping):
        raise RuntimeError("runtime/apply package is missing contextforge_registration_plan")
    if not isinstance(package.get("install_artifact_contract"), Mapping):
        raise RuntimeError("runtime/apply package is missing install_artifact_contract")
    npm_stdio_host_records.npm_record_artifact(package)
    npm_stdio_host_records.record_path(package)


def package_descriptor(package: Mapping[str, Any]) -> dict[str, Any]:
    registration = package["contextforge_registration_plan"]
    descriptor = registration.get("candidate_descriptor") if isinstance(registration, Mapping) else {}
    return dict(descriptor) if isinstance(descriptor, Mapping) else {}


def package_service_binding(package: Mapping[str, Any]) -> str:
    provision = package["service_provision_plan"]
    binding = provision.get("service_binding") if isinstance(provision, Mapping) else None
    if not isinstance(binding, str) or not binding:
        raise RuntimeError("service_provision_plan.service_binding is required")
    return binding


def package_service_slug(package: Mapping[str, Any]) -> str:
    binding = package_service_binding(package)
    return re.sub(r"[^a-z0-9_.-]+", "-", binding.lower().replace(":", "-")).strip(".-")


def default_names(package: Mapping[str, Any]) -> tuple[str, str]:
    registration = package["contextforge_registration_plan"]
    canonical = registration.get("canonical_names") if isinstance(registration, Mapping) else {}
    gateway_name = canonical.get("gateway") if isinstance(canonical, Mapping) else None
    server_name = canonical.get("virtual_server") if isinstance(canonical, Mapping) else None
    slug = package_service_slug(package)
    return str(gateway_name or f"{slug}-gateway"), str(server_name or f"{slug}-server")


def expected_tools(package: Mapping[str, Any], explicit: list[str] | None = None) -> list[str]:
    if explicit:
        return explicit
    descriptor = package_descriptor(package)
    tools = descriptor.get("expected_tools")
    if isinstance(tools, list):
        return [str(tool) for tool in tools if isinstance(tool, str) and tool]
    return []


def gateway_payload(package: Mapping[str, Any], *, gateway_name: str, upstream_url: str) -> dict[str, Any]:
    descriptor = package_descriptor(package)
    service = str(descriptor.get("canonical_service") or descriptor.get("candidate_service") or package_service_slug(package))
    return {
        "name": gateway_name,
        "url": upstream_url,
        "description": f"ContextForge dev onboarding gateway for {service}.",
        "transport": "STREAMABLEHTTP",
        "tags": ["contextforge", "dev-docker", "service-onboarding", service],
        "visibility": VISIBILITY,
        "owner_email": OWNER,
        "gateway_mode": "cache",
    }


def server_payload(package: Mapping[str, Any], *, server_name: str, tool_ids: list[str]) -> dict[str, Any]:
    descriptor = package_descriptor(package)
    service = str(descriptor.get("canonical_service") or descriptor.get("candidate_service") or package_service_slug(package))
    return {
        "name": server_name,
        "description": f"ContextForge dev virtual server for onboarding service {service}.",
        "associated_tools": tool_ids,
        "tags": ["contextforge", "dev-docker", "service-onboarding", service],
        "owner_email": OWNER,
        "visibility": VISIBILITY,
    }


def normalize_tool_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def filter_expected_tools(tools: list[dict[str, Any]], expected: list[str]) -> list[dict[str, Any]]:
    if not expected:
        raise RuntimeError("expected tools are required; refusing to expose all gateway tools implicitly")
    selected: list[dict[str, Any]] = []
    missing: list[str] = []
    observed = [(tool, normalize_tool_name(str(tool.get("name") or ""))) for tool in tools]
    for item in expected:
        needle = normalize_tool_name(item)
        matches = [tool for tool, normalized in observed if normalized == needle or normalized.endswith(needle)]
        if len(matches) == 1:
            selected.append(matches[0])
        elif len(matches) > 1:
            names = sorted(str(tool.get("name")) for tool in matches)
            raise RuntimeError(f"expected tool {item!r} matched multiple gateway tools: {names}")
        else:
            missing.append(item)
    if missing:
        names = sorted(str(tool.get("name")) for tool in tools)
        raise RuntimeError(f"gateway did not expose expected tools {missing}; observed {names}")
    return selected


def plan_result(
    package: Mapping[str, Any],
    *,
    gateway_name: str,
    server_name: str,
    upstream_url: str,
    expected_tool_names: list[str],
    base_url: str,
    env_file: Path,
    apply: bool,
) -> dict[str, Any]:
    artifact = npm_stdio_host_records.npm_record_artifact(package)
    host_record_request = {
        "host_service": npm_stdio_host_records.HOST_SERVICE_ID,
        "record_path": str(npm_stdio_host_records.record_path(package)),
        "service_binding": package_service_binding(package),
        "content_digest": npm_stdio_host_records.stable_digest(artifact["content"]),
    }
    return {
        "schema_uri": SCHEMA_URI,
        "mutation_performed": False,
        "apply_requested": apply,
        "target": {
            "base_url": base_url,
            "env_file": str(env_file),
            "env_values_recorded": False,
        },
        "package": {
            "status": package.get("status"),
            "service_binding": package_service_binding(package),
            "provision_plan_id": package.get("service_provision_plan", {}).get("provision_plan_id"),
            "catalog_plan_id": package.get("contextforge_registration_plan", {}).get("plan_id"),
        },
        "registry_request": {
            "gateway_name": gateway_name,
            "server_name": server_name,
            "upstream_url": upstream_url,
            "expected_tools": expected_tool_names,
            "gateway_payload": gateway_payload(package, gateway_name=gateway_name, upstream_url=upstream_url),
        },
        "npm_stdio_host_request": host_record_request,
        "non_actions": [
            "dry-run; no ContextForge API calls",
            "dry-run; no Docker, process, systemd, project-state, client config, or secret mutation",
            "dry-run; no env-file contents read",
        ],
    }


def rollback_created_contextforge_state(
    client: ContextForgeClient,
    *,
    created_gateway_id: str,
    created_server_id: str,
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    if created_server_id:
        try:
            client.request("DELETE", f"/servers/{created_server_id}")
            actions.append({"target": f"/servers/{created_server_id}", "action": "delete_created_server", "ok": True})
        except Exception as exc:  # pragma: no cover - defensive report path
            actions.append({"target": f"/servers/{created_server_id}", "action": "delete_created_server", "ok": False, "error": sanitize_error(exc)})
    if created_gateway_id:
        try:
            client.request("DELETE", f"/gateways/{created_gateway_id}")
            actions.append({"target": f"/gateways/{created_gateway_id}", "action": "delete_created_gateway", "ok": True})
        except Exception as exc:  # pragma: no cover - defensive report path
            actions.append({"target": f"/gateways/{created_gateway_id}", "action": "delete_created_gateway", "ok": False, "error": sanitize_error(exc)})
    return actions


def apply_package(
    package: Mapping[str, Any],
    *,
    client: ContextForgeClient,
    gateway_name: str,
    server_name: str,
    upstream_url: str,
    expected_tool_names: list[str],
    wait_attempts: int = 12,
) -> dict[str, Any]:
    gateway_body = gateway_payload(package, gateway_name=gateway_name, upstream_url=upstream_url)
    created_gateway_id = ""
    created_server_id = ""
    failed_stage = "preflight"
    try:
        gateways = client.items("/gateways?include_inactive=true&limit=1000")
        existing_gateway = by_name(gateways, gateway_name)
        url_match = by_url(gateways, upstream_url)
        if existing_gateway and url_match and row_id(url_match) != row_id(existing_gateway):
            raise RuntimeError(
                "upstream URL already belongs to gateway "
                f"{url_match.get('name')!r}; refusing to also assign it to {gateway_name!r}"
            )
        if not existing_gateway:
            if url_match:
                raise RuntimeError(
                    "upstream URL already belongs to gateway "
                    f"{url_match.get('name')!r}; refusing to rename or retag it as {gateway_name!r}"
                )
        failed_stage = "gateway"
        if existing_gateway:
            gateway = client.request("PUT", f"/gateways/{row_id(existing_gateway)}", gateway_body)
            gateway_action = "updated"
        else:
            gateway = client.request("POST", "/gateways", gateway_body)
            gateway_action = "created"
            created_gateway_id = row_id(gateway)
        gateway_id = row_id(gateway)

        selected_tools: list[dict[str, Any]] = []
        last_tool_error: RuntimeError | None = None
        failed_stage = "tool_refresh"
        for attempt in range(wait_attempts):
            try:
                client.request("POST", f"/gateways/{gateway_id}/tools/refresh")
            except RuntimeError as exc:
                last_tool_error = exc
                if attempt + 1 < wait_attempts:
                    time.sleep(1)
                    continue
                raise
            gateway_tools = [tool for tool in client.items("/tools?include_inactive=true&limit=1000") if tool_gateway_id(tool) == gateway_id]
            try:
                selected_tools = filter_expected_tools(gateway_tools, expected_tool_names)
                last_tool_error = None
            except RuntimeError as exc:
                selected_tools = []
                last_tool_error = exc
            if selected_tools:
                break
            if attempt + 1 < wait_attempts:
                time.sleep(1)
        if not selected_tools:
            if last_tool_error:
                raise last_tool_error
            raise RuntimeError(f"gateway {gateway_name} ({gateway_id}) did not expose tools after refresh")

        tool_ids = [row_id(tool) for tool in selected_tools]
        failed_stage = "virtual_server"
        existing_server = by_name(client.items("/servers?include_inactive=true&limit=1000"), server_name)
        if existing_server:
            payload = {
                "associatedTools": tool_ids,
                "associatedResources": associated_ids(existing_server, "associatedResources", "associatedResourceIds"),
                "associatedPrompts": associated_ids(existing_server, "associatedPrompts", "associatedPromptIds"),
                "associatedA2aAgents": associated_ids(existing_server, "associatedA2aAgents", "associatedA2aAgentIds"),
                "ownerEmail": OWNER,
                "visibility": VISIBILITY,
            }
            server = client.request("PUT", f"/servers/{row_id(existing_server)}", payload)
            server_action = "updated"
        else:
            server = client.request("POST", "/servers", {"server": server_payload(package, server_name=server_name, tool_ids=tool_ids), "visibility": VISIBILITY})
            server_action = "created"
            created_server_id = row_id(server)
    except Exception as exc:
        rollback_actions = rollback_created_contextforge_state(
            client,
            created_gateway_id=created_gateway_id,
            created_server_id=created_server_id,
        )
        failure_report = {
            "failed_stage": failed_stage,
            "sanitized_error": sanitize_error(exc),
            "rollback_actions_attempted": rollback_actions,
            "rollback_result": "passed" if all(action.get("ok") for action in rollback_actions) else "partial",
            "residual_cleanup_risk": "" if all(action.get("ok") for action in rollback_actions) else "ContextForge cleanup action failed",
        }
        raise RuntimeApplyError(f"runtime/apply failed at {failed_stage}: {sanitize_error(exc)}", failure_report=failure_report) from exc

    return {
        "schema_uri": SCHEMA_URI,
        "mutation_performed": True,
        "apply_requested": True,
        "package": {
            "status": package.get("status"),
            "service_binding": package_service_binding(package),
            "provision_plan_id": package.get("service_provision_plan", {}).get("provision_plan_id"),
            "catalog_plan_id": package.get("contextforge_registration_plan", {}).get("plan_id"),
        },
        "gateway": {"action": gateway_action, "id": gateway_id, "name": gateway_name, "url": upstream_url},
        "server": {"action": server_action, "id": row_id(server), "name": server_name},
        "tool_count": len(selected_tools),
        "tool_names": [str(tool.get("name")) for tool in selected_tools],
        "rollback_boundary": {
            "created_gateway_id": created_gateway_id,
            "created_server_id": created_server_id,
            "failure_policy": "rollback_created_contextforge_state_before_error_response",
        },
        "non_actions": [
            "no Docker, process, systemd, project-state, client config, or secret mutation by this registry executor",
            "env-file values not recorded",
        ],
    }


def run(
    *,
    package_path: Path,
    upstream_url: str,
    gateway_name: str | None = None,
    server_name: str | None = None,
    expected_tool_names: list[str] | None = None,
    apply: bool = False,
    client: ContextForgeClient | None = None,
    base_url: str = DEFAULT_BASE_URL,
    env_file: Path = DEFAULT_ENV_FILE,
    wait_attempts: int = 12,
) -> dict[str, Any]:
    package = load_package(package_path)
    default_gateway, default_server = default_names(package)
    gateway = gateway_name or default_gateway
    server = server_name or default_server
    expected = expected_tools(package, expected_tool_names)
    if not expected:
        raise RuntimeError("expected tools are required; pass --expected-tool or include expected_tools in the package descriptor")
    if not upstream_url:
        raise RuntimeError("upstream_url is required")
    if not apply:
        return plan_result(
            package,
            gateway_name=gateway,
            server_name=server,
            upstream_url=upstream_url,
            expected_tool_names=expected,
            base_url=base_url,
            env_file=env_file,
            apply=apply,
        )
    host_record, host_rollback_token = npm_stdio_host_records.upsert_from_runtime_package(package)
    active_client = client or load_target_client(base_url, env_file)
    try:
        result = apply_package(
            package,
            client=active_client,
            gateway_name=gateway,
            server_name=server,
            upstream_url=upstream_url,
            expected_tool_names=expected,
            wait_attempts=wait_attempts,
        )
    except RuntimeApplyError as exc:
        host_rollback = npm_stdio_host_records.rollback_upsert(host_rollback_token)
        report = dict(exc.failure_report)
        report.setdefault("rollback_actions_attempted", [])
        report["rollback_actions_attempted"] = list(report["rollback_actions_attempted"]) + [
            {"target": host_record["record_path"], "action": "rollback_npm_stdio_host_record", "ok": host_rollback["ok"], "details": host_rollback["actions"]}
        ]
        report["rollback_result"] = "passed" if host_rollback["ok"] and report.get("rollback_result") == "passed" else "partial"
        if host_rollback.get("residual_cleanup_risk"):
            report["residual_cleanup_risk"] = host_rollback["residual_cleanup_risk"]
        raise RuntimeApplyError(str(exc), failure_report=report) from exc
    result["target"] = {"base_url": base_url, "env_file": str(env_file), "env_values_recorded": False}
    result["npm_stdio_host_record"] = host_record
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-json", type=Path, required=True)
    parser.add_argument("--upstream-url", required=True)
    parser.add_argument("--gateway-name")
    parser.add_argument("--server-name")
    parser.add_argument("--expected-tool", action="append", dest="expected_tools")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--wait-attempts", type=int, default=12)
    parser.add_argument("--apply", action="store_true", help="Call ContextForge APIs. Omit for dry-run planning.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run(
        package_path=args.package_json,
        upstream_url=args.upstream_url,
        gateway_name=args.gateway_name,
        server_name=args.server_name,
        expected_tool_names=args.expected_tools,
        apply=args.apply,
        base_url=args.base_url,
        env_file=args.env_file,
        wait_attempts=args.wait_attempts,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeApplyError as exc:
        print(json.dumps({"ok": False, "error": sanitize_error(exc), "failure_report": exc.failure_report}, indent=2, sort_keys=True), file=sys.stderr)
        raise SystemExit(1)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
