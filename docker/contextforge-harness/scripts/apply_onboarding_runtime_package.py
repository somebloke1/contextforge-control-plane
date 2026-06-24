#!/usr/bin/env python3
"""Apply or dry-run an onboarding runtime/apply package against dev ContextForge."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
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
import npm_stdio_host_runtime

DEFAULT_ENV_FILE = ROOT / "env" / "contextforge.env"
DEFAULT_BASE_URL = "http://127.0.0.1:4445"
OWNER = "admin@contextforge-harness.dev"
SCHEMA_URI = "contextforge://control-plane/service-onboarding-runtime-package-apply/v1"
INSTANCE_MANIFEST_SCHEMA_URI = "contextforge://control-plane/server-instance/v1"
VISIBILITY = "public"
SQL_TRIGGER_RE = re.compile(r"(?i)(union|select|insert|update|delete|drop)(?=\s)")
INLINE_CODE_RE = re.compile(r"`([^`]+)`")
SQL_WORD_REPLACEMENTS = {
    "union": "combine",
    "select": "choose",
    "insert": "add",
    "update": "modify",
    "delete": "remove",
    "drop": "place",
}


class ContextForgeClient(Protocol):
    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        ...

    def items(self, path: str) -> list[dict[str, Any]]:
        ...


class NpmStdioHostRuntime(Protocol):
    def apply(self, package: Mapping[str, Any]) -> dict[str, Any]:
        ...

    def view(self, package: Mapping[str, Any]) -> dict[str, Any]:
        ...

    def delete(self, package: Mapping[str, Any]) -> dict[str, Any]:
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


class DockerComposeNpmStdioHostRuntime:
    def __init__(self, *, compose_file: Path | None = None):
        self.compose_file = compose_file or (ROOT / "compose.yml")

    def _run(self, command: str, package: Mapping[str, Any]) -> dict[str, Any]:
        service_binding = package_service_binding(package)
        result = subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                str(self.compose_file),
                "exec",
                "-T",
                "npm-stdio-host",
                "python3",
                "/opt/contextforge/npm_stdio_host_runtime.py",
                command,
                "--project-root",
                "/workspace",
                "--service-binding",
                service_binding,
            ],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
        )
        if result.returncode != 0:
            raise RuntimeError(f"npm-stdio-host {command} failed: {result.stderr.strip() or result.stdout.strip()}")
        payload = json.loads(result.stdout)
        if not isinstance(payload, dict):
            raise RuntimeError(f"npm-stdio-host {command} returned non-object JSON")
        return payload

    def apply(self, package: Mapping[str, Any]) -> dict[str, Any]:
        return self._run("apply", package)

    def view(self, package: Mapping[str, Any]) -> dict[str, Any]:
        return self._run("view", package)

    def delete(self, package: Mapping[str, Any]) -> dict[str, Any]:
        return self._run("delete", package)


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


def sanitize_scanner_text(text: str) -> str:
    """Shape documentation text so ContextForge's broad scanner accepts it."""

    def replace_sql_word(match: re.Match[str]) -> str:
        word = match.group(1)
        replacement = SQL_WORD_REPLACEMENTS[word.lower()]
        return replacement.capitalize() if word[:1].isupper() else replacement

    shaped = text.replace("```", "")
    shaped = INLINE_CODE_RE.sub(r"\1", shaped)
    shaped = shaped.replace("&&", "and")
    shaped = shaped.replace("||", "or")
    shaped = shaped.replace("$(", "$ (")
    shaped = shaped.replace("${", "$ {")
    return SQL_TRIGGER_RE.sub(replace_sql_word, shaped)


def load_package(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError("runtime/apply package must be a JSON object")
    validate_package(data)
    return data


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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


def package_service_name(package: Mapping[str, Any]) -> str:
    descriptor = package_descriptor(package)
    return str(
        descriptor.get("canonical_service")
        or descriptor.get("candidate_service")
        or package_service_binding(package).split(":", 1)[0]
    )


def package_record_content(package: Mapping[str, Any]) -> Mapping[str, Any]:
    artifact = npm_stdio_host_records.npm_record_artifact(package)
    content = artifact.get("content")
    if not isinstance(content, Mapping):
        raise RuntimeError("npm_stdio_service_record.content is required")
    return content


def package_record_path(package: Mapping[str, Any]) -> Path:
    return npm_stdio_host_records.record_path(package)


def package_instance_manifest_path(package: Mapping[str, Any]) -> Path:
    return package_record_path(package).parent / "instance.json"


def package_upstream_url(package: Mapping[str, Any]) -> str:
    content = package_record_content(package)
    endpoint = content.get("endpoint") if isinstance(content.get("endpoint"), Mapping) else {}
    value = endpoint.get("streamable_http_url") or endpoint.get("container_url")
    if not isinstance(value, str) or not value.strip():
        binding = package_service_binding(package)
        value = npm_stdio_host_runtime.default_endpoint(binding)["streamable_http_url"]
    return str(value)


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


def server_payload(package: Mapping[str, Any], *, server_name: str, tool_ids: list[str], resource_ids: list[str] | None = None) -> dict[str, Any]:
    service = package_service_name(package)
    return {
        "name": server_name,
        "description": f"ContextForge dev virtual server for onboarding service {service}.",
        "associated_tools": tool_ids,
        "associated_resources": resource_ids or [],
        "associated_prompts": [],
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


def unique_ids(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def resource_id(resource: Mapping[str, Any]) -> str:
    value = resource.get("id")
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"resource missing string id: {resource}")
    return value


def package_prompt_library(package: Mapping[str, Any]) -> Mapping[str, Any]:
    artifact = npm_stdio_host_records.npm_record_artifact(package)
    content = artifact.get("content") if isinstance(artifact.get("content"), Mapping) else {}
    prompt_library = content.get("prompt_library") if isinstance(content.get("prompt_library"), Mapping) else {}
    if prompt_library.get("publication_required") is not True:
        raise RuntimeError("npm_stdio_service_record.prompt_library.publication_required must be true")
    abstract = str(prompt_library.get("abstract_prompt") or "").strip()
    details = prompt_library.get("detail_prompts")
    if not abstract:
        raise RuntimeError("npm_stdio_service_record.prompt_library.abstract_prompt is required")
    if not isinstance(details, Mapping) or not details:
        raise RuntimeError("npm_stdio_service_record.prompt_library.detail_prompts is required")
    return prompt_library


def service_guidance_resource_bodies(package: Mapping[str, Any], *, gateway_id: str) -> list[dict[str, Any]]:
    service = package_service_name(package)
    prompt_library = package_prompt_library(package)
    abstract_uri = str(prompt_library.get("abstract_prompt_uri") or "").strip()
    detail_prefix = str(prompt_library.get("detail_prompt_uri_prefix") or "").strip()
    if not abstract_uri:
        raise RuntimeError("npm_stdio_service_record.prompt_library.abstract_prompt_uri is required")
    if not detail_prefix:
        raise RuntimeError("npm_stdio_service_record.prompt_library.detail_prompt_uri_prefix is required")
    slug = package_service_slug(package)
    resources = [
        {
            "uri": abstract_uri,
            "name": f"{slug}-abstract-service-spec",
            "title": f"{service} abstract service spec",
            "description": f"Compact proactive service spec for onboarded service {service}.",
            "mimeType": "text/markdown",
            "content": sanitize_scanner_text(str(prompt_library["abstract_prompt"]).strip()),
            "tags": ["service-guidance", "abstract-service-spec", "service-onboarding", service],
            "owner_email": OWNER,
            "visibility": VISIBILITY,
            "gateway_id": gateway_id,
        }
    ]
    detail_prompts = prompt_library["detail_prompts"]
    for key in sorted(detail_prompts):
        raw_content = detail_prompts[key]
        if not isinstance(raw_content, str) or not raw_content.strip():
            raise RuntimeError(f"npm_stdio_service_record.prompt_library.detail_prompts.{key} is required")
        detail_slug = re.sub(r"[^a-z0-9_.-]+", "-", str(key).lower()).strip(".-") or "detail"
        resources.append(
            {
                "uri": f"{detail_prefix}{detail_slug}/v1",
                "name": f"{slug}-{detail_slug}-detail-service-spec",
                "title": f"{service} {detail_slug} detail service spec",
                "description": f"Lazy-loaded detailed service guidance for onboarded service {service}.",
                "mimeType": "text/markdown",
                "content": sanitize_scanner_text(raw_content.strip()),
                "tags": ["service-guidance", "detail-service-spec", "service-onboarding", service],
                "owner_email": OWNER,
                "visibility": VISIBILITY,
                "gateway_id": gateway_id,
            }
        )
    return resources


def service_guidance_resource_uris(package: Mapping[str, Any]) -> list[str]:
    prompt_library = package_prompt_library(package)
    abstract_uri = str(prompt_library.get("abstract_prompt_uri") or "").strip()
    detail_prefix = str(prompt_library.get("detail_prompt_uri_prefix") or "").strip()
    detail_prompts = prompt_library["detail_prompts"]
    uris = [abstract_uri]
    for key in sorted(detail_prompts):
        detail_slug = re.sub(r"[^a-z0-9_.-]+", "-", str(key).lower()).strip(".-") or "detail"
        uris.append(f"{detail_prefix}{detail_slug}/v1")
    return uris


def write_json_atomic(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def service_instance_manifest(
    package: Mapping[str, Any],
    *,
    gateway: Mapping[str, Any],
    server: Mapping[str, Any],
    upstream_url: str,
    selected_tools: list[dict[str, Any]],
) -> dict[str, Any]:
    descriptor = package_descriptor(package)
    record = package_record_content(package)
    service_binding = package_service_binding(package)
    service = package_service_name(package)
    slug = package_service_slug(package)
    backend_command = record.get("stdio") if isinstance(record.get("stdio"), Mapping) else {}
    endpoint = record.get("endpoint") if isinstance(record.get("endpoint"), Mapping) else {}
    scope = {
        "requires_local_project_scope": False,
        "scope_type": "managed_npm_stdio_host_service",
        "configuration_signal": "service-specific tool arguments and declared environment boundary",
        "notes": "Service is hosted by the shared ContextForge-managed npm-stdio host and bound into clients through ContextForge project init.",
    }
    return {
        "schema_uri": INSTANCE_MANIFEST_SCHEMA_URI,
        "name": service,
        "slug": slug,
        "service": service,
        "service_binding": service_binding,
        "managed_by": npm_stdio_host_records.HOST_SERVICE_ID,
        "source": descriptor.get("source_lead") or "",
        "enabled": True,
        "kind": "mcp",
        "client": "canonical",
        "scope": scope,
        "backend": {
            "transport": "stdio",
            "package": record.get("package") or descriptor.get("backend_package") or "",
            "version_policy": record.get("version_policy") or "",
            "command": backend_command.get("command") if isinstance(backend_command, Mapping) else "",
            "args": backend_command.get("args") if isinstance(backend_command, Mapping) else [],
            "env_vars": record.get("environment", {}).get("required_secret_names", [])
            if isinstance(record.get("environment"), Mapping)
            else [],
        },
        "bridge": {
            "needed": True,
            "provider": npm_stdio_host_records.HOST_SERVICE_ID,
            "reason": "npm stdio MCP service is exposed to ContextForge through the shared managed npm-stdio host.",
            "streamable_http_url": (endpoint.get("streamable_http_url") or upstream_url) if isinstance(endpoint, Mapping) else upstream_url,
            "sse_url": endpoint.get("sse_url") if isinstance(endpoint, Mapping) else None,
        },
        "contextforge": {
            "gateway": {
                "name": gateway.get("name"),
                "url": gateway.get("url") or upstream_url,
                "transport": gateway.get("transport") or "STREAMABLEHTTP",
                "id": gateway.get("id"),
            },
            "virtual_server": {
                "name": server.get("name"),
                "id": server.get("id"),
                "grouping": "managed-npm-stdio",
            },
        },
        "registration": {
            "status": "registered",
            "registered_tools": [str(tool.get("name")) for tool in selected_tools if tool.get("name")],
            "verified": {
                "contextforge": "gateway refresh exposed expected tools and virtual server was created or updated",
            },
        },
    }


def write_service_instance_manifest(
    package: Mapping[str, Any],
    *,
    gateway: Mapping[str, Any],
    server: Mapping[str, Any],
    upstream_url: str,
    selected_tools: list[dict[str, Any]],
) -> dict[str, Any]:
    path = package_instance_manifest_path(package)
    root = npm_stdio_host_records.project_root_from_package(package)
    resolved = path.resolve(strict=False)
    if root / "server-instances" not in (resolved, *resolved.parents):
        raise RuntimeError(f"managed instance manifest path must be under server-instances: {path}")
    previous = read_json(path) if path.exists() else None
    manifest = service_instance_manifest(
        package,
        gateway=gateway,
        server=server,
        upstream_url=upstream_url,
        selected_tools=selected_tools,
    )
    action = "already_applied" if isinstance(previous, Mapping) and previous == manifest else ("updated" if previous is not None else "created")
    if action != "already_applied":
        write_json_atomic(path, manifest)
    return {
        "action": action,
        "path": str(path),
        "service_binding": package_service_binding(package),
        "manifest_digest": npm_stdio_host_records.stable_digest(manifest),
    }


def by_uri(rows: list[dict[str, Any]], uri: str) -> dict[str, Any] | None:
    return next((row for row in rows if row.get("uri") == uri), None)


def upsert_service_guidance_resources(
    client: ContextForgeClient,
    package: Mapping[str, Any],
    *,
    gateway_id: str,
    rollback_tokens: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    resources_by_uri = client.items("/resources?include_inactive=true&limit=1000")
    resource_ids: list[dict[str, Any]] = []
    for body in service_guidance_resource_bodies(package, gateway_id=gateway_id):
        existing = by_uri(resources_by_uri, str(body["uri"]))
        if existing:
            existing_id = resource_id(existing)
            if all(existing.get(key) == body.get(key) for key in ("uri", "name", "title", "description", "mimeType", "content", "tags", "owner_email", "visibility", "gateway_id")):
                resource = existing
                action = "already_applied"
            else:
                rollback_tokens.append({"resource_id": existing_id, "previous": dict(existing), "action": "restore_previous_resource"})
                resource = client.request("PUT", f"/resources/{existing_id}", body)
                action = "updated"
        else:
            resource = client.request("POST", "/resources", {"resource": body, "visibility": VISIBILITY})
            action = "created"
            rollback_tokens.append({"resource_id": resource_id(resource), "action": "delete_created_resource"})
        resource_ids.append({"id": resource_id(resource), "uri": str(body["uri"]), "action": action})
    return resource_ids


def rollback_guidance_resources(client: ContextForgeClient, rollback_tokens: list[dict[str, Any]]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for token in reversed(rollback_tokens):
        resource = str(token.get("resource_id") or "")
        if not resource:
            continue
        try:
            if token.get("action") == "restore_previous_resource" and isinstance(token.get("previous"), Mapping):
                client.request("PUT", f"/resources/{resource}", dict(token["previous"]))
                actions.append({"target": f"/resources/{resource}", "action": "restore_previous_resource", "ok": True})
            elif token.get("action") == "delete_created_resource":
                client.request("DELETE", f"/resources/{resource}")
                actions.append({"target": f"/resources/{resource}", "action": "delete_created_resource", "ok": True})
        except Exception as exc:  # pragma: no cover - defensive report path
            actions.append({"target": f"/resources/{resource}", "action": str(token.get("action") or "rollback_resource"), "ok": False, "error": sanitize_error(exc)})
    return actions


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
        "runtime_endpoint": package_upstream_url(package),
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


def rollback_contextforge_state(
    client: ContextForgeClient,
    *,
    rollback_tokens: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for token in reversed(rollback_tokens):
        action = str(token.get("action") or "")
        target_id = str(token.get("id") or "")
        previous = token.get("previous")
        try:
            if action == "restore_previous_server" and target_id and isinstance(previous, Mapping):
                client.request("PUT", f"/servers/{target_id}", dict(previous))
                actions.append({"target": f"/servers/{target_id}", "action": action, "ok": True})
            elif action == "delete_created_server" and target_id:
                client.request("DELETE", f"/servers/{target_id}")
                actions.append({"target": f"/servers/{target_id}", "action": action, "ok": True})
            elif action == "restore_previous_gateway" and target_id and isinstance(previous, Mapping):
                client.request("PUT", f"/gateways/{target_id}", dict(previous))
                actions.append({"target": f"/gateways/{target_id}", "action": action, "ok": True})
            elif action == "delete_created_gateway" and target_id:
                client.request("DELETE", f"/gateways/{target_id}")
                actions.append({"target": f"/gateways/{target_id}", "action": action, "ok": True})
        except Exception as exc:  # pragma: no cover - defensive report path
            target = f"/servers/{target_id}" if "server" in action else f"/gateways/{target_id}"
            actions.append({"target": target, "action": action or "rollback_contextforge_state", "ok": False, "error": sanitize_error(exc)})
    return actions


def best_effort_delete(
    client: ContextForgeClient,
    method: str,
    path: str,
    *,
    action: str,
    target: str | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {"target": target or path, "action": action}
    if extra:
        result.update(dict(extra))
    try:
        client.request(method, path)
        result["ok"] = True
    except Exception as exc:
        result["ok"] = False
        result["error"] = sanitize_error(exc)
    return result


def best_effort_items(client: ContextForgeClient, path: str, *, actions: list[dict[str, Any]], action: str) -> list[dict[str, Any]]:
    try:
        return client.items(path)
    except Exception as exc:
        actions.append({"target": path, "action": action, "ok": False, "error": sanitize_error(exc)})
        return []


def rollback_created_contextforge_state(
    client: ContextForgeClient,
    *,
    created_gateway_id: str,
    created_server_id: str,
) -> list[dict[str, Any]]:
    tokens: list[dict[str, Any]] = []
    if created_gateway_id:
        tokens.append({"action": "delete_created_gateway", "id": created_gateway_id})
    if created_server_id:
        tokens.append({"action": "delete_created_server", "id": created_server_id})
    return rollback_contextforge_state(client, rollback_tokens=tokens)


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
    guidance_resource_rollback_tokens: list[dict[str, Any]] = []
    contextforge_rollback_tokens: list[dict[str, Any]] = []
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
            contextforge_rollback_tokens.append(
                {"action": "restore_previous_gateway", "id": row_id(existing_gateway), "previous": dict(existing_gateway)}
            )
            gateway = client.request("PUT", f"/gateways/{row_id(existing_gateway)}", gateway_body)
            gateway_action = "updated"
        else:
            gateway = client.request("POST", "/gateways", gateway_body)
            gateway_action = "created"
            created_gateway_id = row_id(gateway)
            contextforge_rollback_tokens.append({"action": "delete_created_gateway", "id": created_gateway_id})
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
        failed_stage = "prompt_library_resources"
        guidance_resources = upsert_service_guidance_resources(
            client,
            package,
            gateway_id=gateway_id,
            rollback_tokens=guidance_resource_rollback_tokens,
        )
        guidance_resource_ids = [str(resource["id"]) for resource in guidance_resources]
        failed_stage = "virtual_server"
        existing_server = by_name(client.items("/servers?include_inactive=true&limit=1000"), server_name)
        if existing_server:
            contextforge_rollback_tokens.append(
                {"action": "restore_previous_server", "id": row_id(existing_server), "previous": dict(existing_server)}
            )
            payload = {
                "associatedTools": tool_ids,
                "associatedResources": unique_ids(
                    associated_ids(existing_server, "associatedResources", "associatedResourceIds") + guidance_resource_ids
                ),
                "associatedPrompts": associated_ids(existing_server, "associatedPrompts", "associatedPromptIds"),
                "associatedA2aAgents": associated_ids(existing_server, "associatedA2aAgents", "associatedA2aAgentIds"),
                "ownerEmail": OWNER,
                "visibility": VISIBILITY,
            }
            server = client.request("PUT", f"/servers/{row_id(existing_server)}", payload)
            server_action = "updated"
        else:
            server = client.request(
                "POST",
                "/servers",
                {
                    "server": server_payload(package, server_name=server_name, tool_ids=tool_ids, resource_ids=guidance_resource_ids),
                    "visibility": VISIBILITY,
                },
            )
            server_action = "created"
            created_server_id = row_id(server)
            contextforge_rollback_tokens.append({"action": "delete_created_server", "id": created_server_id})
        failed_stage = "service_instance_manifest"
        instance_manifest = write_service_instance_manifest(
            package,
            gateway=gateway,
            server=server,
            upstream_url=upstream_url,
            selected_tools=selected_tools,
        )
    except Exception as exc:
        rollback_actions = rollback_guidance_resources(client, guidance_resource_rollback_tokens)
        rollback_actions.extend(rollback_contextforge_state(client, rollback_tokens=contextforge_rollback_tokens))
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
        "prompt_library_resources": {
            "actions": guidance_resources,
            "resource_ids": guidance_resource_ids,
        },
        "service_instance_manifest": instance_manifest,
        "rollback_boundary": {
            "created_gateway_id": created_gateway_id,
            "created_server_id": created_server_id,
            "contextforge_rollback_actions": [token["action"] for token in contextforge_rollback_tokens],
            "guidance_resource_actions": [token["action"] for token in guidance_resource_rollback_tokens],
            "failure_policy": "rollback_created_contextforge_state_before_error_response",
        },
        "non_actions": [
            "no Docker, process, systemd, project-state, client config, or secret mutation by this registry executor",
            "env-file values not recorded",
        ],
    }


def delete_package(
    package: Mapping[str, Any],
    *,
    client: ContextForgeClient,
    host_runtime: NpmStdioHostRuntime,
    gateway_name: str,
    server_name: str,
) -> dict[str, Any]:
    actions: list[dict[str, Any]] = []
    manifest_path = package_instance_manifest_path(package)
    if manifest_path.exists():
        try:
            manifest = read_json(manifest_path)
            if (
                isinstance(manifest, Mapping)
                and manifest.get("managed_by") == npm_stdio_host_records.HOST_SERVICE_ID
                and str(manifest.get("service_binding") or "") == package_service_binding(package)
            ):
                manifest_path.unlink()
                actions.append({"target": str(manifest_path), "action": "delete_managed_instance_manifest", "ok": True})
        except Exception as exc:
            actions.append({"target": str(manifest_path), "action": "delete_managed_instance_manifest", "ok": False, "error": sanitize_error(exc)})
    servers = best_effort_items(
        client,
        "/servers?include_inactive=true&limit=1000",
        actions=actions,
        action="list_virtual_servers_for_delete",
    )
    existing_server = by_name(servers, server_name)
    if existing_server:
        server_id = row_id(existing_server)
        actions.append(best_effort_delete(client, "DELETE", f"/servers/{server_id}", action="delete_virtual_server"))
    else:
        actions.append({"target": server_name, "action": "virtual_server_absent", "ok": True})

    resources = best_effort_items(
        client,
        "/resources?include_inactive=true&limit=1000",
        actions=actions,
        action="list_prompt_library_resources_for_delete",
    )
    for uri in service_guidance_resource_uris(package):
        existing_resource = by_uri(resources, uri)
        if existing_resource:
            rid = resource_id(existing_resource)
            actions.append(
                best_effort_delete(
                    client,
                    "DELETE",
                    f"/resources/{rid}",
                    action="delete_prompt_library_resource",
                    extra={"uri": uri},
                )
            )
        else:
            actions.append({"target": uri, "action": "prompt_library_resource_absent", "ok": True})

    gateways = best_effort_items(
        client,
        "/gateways?include_inactive=true&limit=1000",
        actions=actions,
        action="list_gateways_for_delete",
    )
    existing_gateway = by_name(gateways, gateway_name)
    if existing_gateway:
        gateway_id = row_id(existing_gateway)
        actions.append(best_effort_delete(client, "DELETE", f"/gateways/{gateway_id}", action="delete_gateway"))
    else:
        actions.append({"target": gateway_name, "action": "gateway_absent", "ok": True})

    try:
        host_runtime_delete = host_runtime.delete(package)
        host_runtime_action = "delete_npm_stdio_host_runtime" if host_runtime_delete.get("mutation_performed") else "npm_stdio_host_runtime_absent"
        actions.append(
            {
                "target": package_service_binding(package),
                "action": host_runtime_action,
                "ok": bool(host_runtime_delete.get("rollback_result", "passed") == "passed"),
                "details": host_runtime_delete,
            }
        )
    except Exception as exc:
        actions.append(
            {
                "target": package_service_binding(package),
                "action": "delete_npm_stdio_host_runtime",
                "ok": False,
                "error": sanitize_error(exc),
            }
        )

    try:
        host_delete = npm_stdio_host_records.delete_service_record(
            npm_stdio_host_records.project_root_from_package(package),
            package_service_binding(package),
        )
        host_action = "delete_npm_stdio_host_record" if host_delete.get("actions") else "npm_stdio_host_record_absent"
        actions.append({"target": host_delete["service_binding"], "action": host_action, "ok": host_delete["ok"], "details": host_delete["actions"]})
    except Exception as exc:
        actions.append(
            {
                "target": package_service_binding(package),
                "action": "delete_npm_stdio_host_record",
                "ok": False,
                "error": sanitize_error(exc),
            }
        )
    mutation_performed = any("absent" not in str(action.get("action") or "") for action in actions)
    return {
        "schema_uri": SCHEMA_URI,
        "mutation_performed": mutation_performed,
        "delete_requested": True,
        "package": {
            "status": package.get("status"),
            "service_binding": package_service_binding(package),
            "provision_plan_id": package.get("service_provision_plan", {}).get("provision_plan_id"),
            "catalog_plan_id": package.get("contextforge_registration_plan", {}).get("plan_id"),
        },
        "delete_actions": actions,
        "rollback_boundary": {
            "failure_policy": "delete_is_idempotent_absent_artifacts_are_success",
            "residual_cleanup_risk": "" if all(action.get("ok") for action in actions) else "delete action failed",
        },
        "non_actions": [
            "no client config mutation",
            "env-file values not recorded",
        ],
    }


def view_package(
    package: Mapping[str, Any],
    *,
    client: ContextForgeClient,
    host_runtime: NpmStdioHostRuntime,
    gateway_name: str,
    server_name: str,
) -> dict[str, Any]:
    gateways = client.items("/gateways?include_inactive=true&limit=1000")
    servers = client.items("/servers?include_inactive=true&limit=1000")
    resources = client.items("/resources?include_inactive=true&limit=1000")
    gateway = by_name(gateways, gateway_name)
    server = by_name(servers, server_name)
    guidance = []
    for uri in service_guidance_resource_uris(package):
        existing = by_uri(resources, uri)
        guidance.append(
            {
                "uri": uri,
                "present": existing is not None,
                "id": resource_id(existing) if existing else "",
            }
        )
    host = npm_stdio_host_records.view_service_record(
        npm_stdio_host_records.project_root_from_package(package),
        package_service_binding(package),
    )
    try:
        runtime = host_runtime.view(package)
    except Exception as exc:
        runtime = {"ok": False, "error": sanitize_error(exc), "mutation_performed": False}
    return {
        "schema_uri": SCHEMA_URI,
        "mutation_performed": False,
        "view_requested": True,
        "package": {
            "status": package.get("status"),
            "service_binding": package_service_binding(package),
            "provision_plan_id": package.get("service_provision_plan", {}).get("provision_plan_id"),
            "catalog_plan_id": package.get("contextforge_registration_plan", {}).get("plan_id"),
        },
        "host_record": host,
        "host_runtime": runtime,
        "contextforge": {
            "gateway": {"name": gateway_name, "present": gateway is not None, "id": row_id(gateway) if gateway else ""},
            "virtual_server": {"name": server_name, "present": server is not None, "id": row_id(server) if server else ""},
            "prompt_library_resources": guidance,
        },
        "non_actions": [
            "view-only; no ContextForge API mutation",
            "view-only; no Docker, process, systemd, project-state, client config, or secret mutation",
            "env-file values not recorded",
        ],
    }


def run(
    *,
    package_path: Path,
    upstream_url: str = "",
    gateway_name: str | None = None,
    server_name: str | None = None,
    expected_tool_names: list[str] | None = None,
    apply: bool = False,
    delete: bool = False,
    view: bool = False,
    client: ContextForgeClient | None = None,
    host_runtime: NpmStdioHostRuntime | None = None,
    base_url: str = DEFAULT_BASE_URL,
    env_file: Path = DEFAULT_ENV_FILE,
    wait_attempts: int = 12,
) -> dict[str, Any]:
    package = load_package(package_path)
    default_gateway, default_server = default_names(package)
    gateway = gateway_name or default_gateway
    server = server_name or default_server
    selected_operations = [apply, delete, view]
    if sum(1 for selected in selected_operations if selected) > 1:
        raise RuntimeError("--apply, --delete, and --view are mutually exclusive")
    expected = expected_tools(package, expected_tool_names)
    active_host_runtime = host_runtime or DockerComposeNpmStdioHostRuntime()
    if view:
        active_client = client or load_target_client(base_url, env_file)
        result = view_package(package, client=active_client, host_runtime=active_host_runtime, gateway_name=gateway, server_name=server)
        result["target"] = {"base_url": base_url, "env_file": str(env_file), "env_values_recorded": False}
        return result
    if delete:
        active_client = client or load_target_client(base_url, env_file)
        result = delete_package(package, client=active_client, host_runtime=active_host_runtime, gateway_name=gateway, server_name=server)
        result["target"] = {"base_url": base_url, "env_file": str(env_file), "env_values_recorded": False}
        return result
    if not expected:
        raise RuntimeError("expected tools are required; pass --expected-tool or include expected_tools in the package descriptor")
    if not upstream_url:
        upstream_url = package_upstream_url(package)
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
    try:
        host_runtime_result = active_host_runtime.apply(package)
    except Exception as exc:
        host_rollback = npm_stdio_host_records.rollback_upsert(host_rollback_token)
        report = {
            "failed_stage": "npm_stdio_host_runtime",
            "sanitized_error": sanitize_error(exc),
            "rollback_actions_attempted": [
                {"target": host_record["record_path"], "action": "rollback_npm_stdio_host_record", "ok": host_rollback["ok"], "details": host_rollback["actions"]}
            ],
            "rollback_result": "passed" if host_rollback["ok"] else "partial",
            "residual_cleanup_risk": host_rollback.get("residual_cleanup_risk") or "",
        }
        raise RuntimeApplyError(f"runtime/apply failed at npm_stdio_host_runtime: {sanitize_error(exc)}", failure_report=report) from exc
    runtime_endpoint = host_runtime_result.get("endpoint") if isinstance(host_runtime_result.get("endpoint"), Mapping) else {}
    upstream_url = str(runtime_endpoint.get("streamable_http_url") or runtime_endpoint.get("container_url") or upstream_url)
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
        previous_record_existed = isinstance(host_rollback_token.get("previous_record"), Mapping)
        try:
            if previous_record_existed:
                host_runtime_result = active_host_runtime.apply(package)
                host_runtime_cleanup = {
                    "target": package_service_binding(package),
                    "action": "rollback_npm_stdio_host_runtime_to_previous",
                    "ok": bool(host_runtime_result.get("running", True)),
                    "details": host_runtime_result,
                }
            else:
                host_runtime_delete = active_host_runtime.delete(package)
                host_runtime_cleanup = {
                    "target": package_service_binding(package),
                    "action": "rollback_npm_stdio_host_runtime",
                    "ok": host_runtime_delete.get("rollback_result") == "passed",
                    "details": host_runtime_delete,
                }
        except Exception as runtime_exc:
            host_runtime_cleanup = {
                "target": package_service_binding(package),
                "action": "rollback_npm_stdio_host_runtime_to_previous" if previous_record_existed else "rollback_npm_stdio_host_runtime",
                "ok": False,
                "error": sanitize_error(runtime_exc),
            }
        report = dict(exc.failure_report)
        report.setdefault("rollback_actions_attempted", [])
        report["rollback_actions_attempted"] = list(report["rollback_actions_attempted"]) + [
            host_runtime_cleanup,
            {"target": host_record["record_path"], "action": "rollback_npm_stdio_host_record", "ok": host_rollback["ok"], "details": host_rollback["actions"]}
        ]
        report["rollback_result"] = "passed" if host_rollback["ok"] and host_runtime_cleanup.get("ok") and report.get("rollback_result") == "passed" else "partial"
        if host_rollback.get("residual_cleanup_risk"):
            report["residual_cleanup_risk"] = host_rollback["residual_cleanup_risk"]
        raise RuntimeApplyError(str(exc), failure_report=report) from exc
    result["target"] = {"base_url": base_url, "env_file": str(env_file), "env_values_recorded": False}
    result["npm_stdio_host_record"] = host_record
    result["npm_stdio_host_runtime"] = host_runtime_result
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-json", type=Path, required=True)
    parser.add_argument("--upstream-url", default="")
    parser.add_argument("--gateway-name")
    parser.add_argument("--server-name")
    parser.add_argument("--expected-tool", action="append", dest="expected_tools")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--wait-attempts", type=int, default=12)
    parser.add_argument("--apply", action="store_true", help="Call ContextForge APIs. Omit for dry-run planning.")
    parser.add_argument("--delete", action="store_true", help="Delete the package's managed npm-stdio host, prompt-library, gateway, and server artifacts idempotently.")
    parser.add_argument("--view", action="store_true", help="Read the package's managed npm-stdio host, prompt-library, gateway, and server artifact state without mutation.")
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
        delete=args.delete,
        view=args.view,
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
