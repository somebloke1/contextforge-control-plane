"""Shared user-facing surfaces for service onboarding helper adapters."""

from __future__ import annotations

import importlib.util
import hashlib
import json
import re
import os
import shlex
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Mapping, Sequence

import control_plane_service_handoffs as service_handoffs
import control_plane_service_management as service_management
import control_plane_service_onboarding_helper as service_onboarding
import control_plane_service_provision as service_provision
from project_init_common import (
    SERVICE_ONBOARDING_HOW_TO_DEFAULT_URL,
    SERVICE_ONBOARDING_HOW_TO_URL_ENV,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
MAX_ONBOARDING_HOW_TO_BYTES = 20_000
_ONBOARDING_HOW_TO_CACHE: dict[str, dict[str, Any]] = {}
MAX_SOURCE_RESEARCH_FILES = 12
MAX_SOURCE_RESEARCH_FILE_BYTES = 16_000
MAX_SOURCE_RESEARCH_TOTAL_BYTES = 60_000
MAX_SOURCE_RESEARCH_DEPTH = 3
RUNTIME_EXECUTOR_BASE_URL_ENV = "CONTEXTFORGE_RUNTIME_EXECUTOR_BASE_URL"
RUNTIME_EXECUTOR_ENV_FILE_ENV = "CONTEXTFORGE_RUNTIME_EXECUTOR_ENV_FILE"
RUNTIME_EXECUTOR_PROXY_URL_ENV = "CONTEXTFORGE_RUNTIME_APPLY_PROXY_URL"
RUNTIME_EXECUTOR_PROXY_TOKEN_ENV = "CONTEXTFORGE_RUNTIME_APPLY_PROXY_TOKEN"
RUNTIME_EXECUTOR_PROXY_BASE_URL_ENV = "CONTEXTFORGE_RUNTIME_APPLY_PROXY_BASE_URL"
RUNTIME_EXECUTOR_PROXY_ENV_FILE_ENV = "CONTEXTFORGE_RUNTIME_APPLY_PROXY_ENV_FILE"
RUNTIME_EXECUTOR_DEFAULT_BASE_URL = "http://host.docker.internal:4445" if Path("/repo").exists() else "http://127.0.0.1:4445"
RUNTIME_EXECUTOR_DEFAULT_ENV_FILE = Path(
    os.environ.get(RUNTIME_EXECUTOR_ENV_FILE_ENV, REPO_ROOT / "docker" / "contextforge-harness" / "env" / "contextforge.env")
)
RUNTIME_APPLY_PACKAGE_CACHE_DIR = ".contextforge/service-onboarding/runtime-apply-packages"
RUNTIME_APPLY_DRAFT_CACHE_DIR = ".contextforge/service-onboarding/runtime-drafts"
NPM_STDIO_PORT_BASE = 20_000
NPM_STDIO_PORT_SPAN = 30_000
SERVICE_BINDING_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]*:[a-z0-9][a-z0-9_.-]*$")
GITHUB_TREE_RE = re.compile(r"^https?://github\.com/([^/]+)/([^/]+)/(tree|blob)/([^/]+)/(.+)$")
SOURCE_RESEARCH_ALLOWED_FILENAMES = {"Dockerfile", "README", "README.md", "pyproject.toml", "package.json"}
SOURCE_RESEARCH_ALLOWED_SUFFIXES = {".py", ".ts", ".js", ".json", ".toml", ".yaml", ".yml", ".md", ".txt"}
SOURCE_RESEARCH_SKIP_NAMES = {"uv.lock", "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "poetry.lock"}


def npm_stdio_existing_ports(project_root: str | Path | None, service_binding: str) -> set[int]:
    if not project_root:
        return set()
    root = Path(project_root).resolve(strict=False)
    index_path = root / "server-instances" / "npm-stdio-host" / "index.json"
    if not index_path.exists():
        return set()
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    ports: set[int] = set()
    for other_binding, entry in (index.get("records") or {}).items():
        if other_binding == service_binding or not isinstance(entry, Mapping):
            continue
        try:
            record_path = (root / str(entry["record_path"])).resolve(strict=False)
            record = json.loads(record_path.read_text(encoding="utf-8"))
            endpoint = record.get("endpoint") if isinstance(record.get("endpoint"), Mapping) else {}
            ports.add(int(endpoint.get("port")))
        except (KeyError, OSError, ValueError, TypeError, json.JSONDecodeError):
            continue
    return ports


def npm_stdio_endpoint_port(service_binding: str, *, project_root: str | Path | None = None) -> int:
    digest = hashlib.sha256(service_binding.encode("utf-8")).hexdigest()
    start = NPM_STDIO_PORT_BASE + (int(digest[:8], 16) % NPM_STDIO_PORT_SPAN)
    used = npm_stdio_existing_ports(project_root, service_binding)
    for offset in range(NPM_STDIO_PORT_SPAN):
        candidate = NPM_STDIO_PORT_BASE + ((start - NPM_STDIO_PORT_BASE + offset) % NPM_STDIO_PORT_SPAN)
        if candidate not in used:
            return candidate
    raise RuntimeError("no available npm-stdio host endpoint ports remain")


def npm_stdio_endpoint(service_binding: str, *, project_root: str | Path | None = None) -> dict[str, Any]:
    port = npm_stdio_endpoint_port(service_binding, project_root=project_root)
    return {
        "host": "0.0.0.0",
        "port": port,
        "container_url": f"http://npm-stdio-host:{port}/mcp",
        "streamable_http_url": f"http://npm-stdio-host:{port}/mcp",
        "sse_url": f"http://npm-stdio-host:{port}/sse",
    }


def onboarding_how_to_url(data: Mapping[str, Any] | None = None) -> str:
    if data:
        value = data.get("onboarding_how_to_url") or data.get("onboardingHowToUrl")
        if value:
            return str(value)
    return os.environ.get(SERVICE_ONBOARDING_HOW_TO_URL_ENV, SERVICE_ONBOARDING_HOW_TO_DEFAULT_URL)


def load_onboarding_how_to_prompt(data: Mapping[str, Any] | None = None) -> dict[str, Any]:
    url = onboarding_how_to_url(data)
    cached = _ONBOARDING_HOW_TO_CACHE.get(url)
    if cached:
        return dict(cached)
    result: dict[str, Any] = {
        "url": url,
        "loaded": False,
        "text": "",
        "error": "",
    }
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "cf-controlplane-onboarding-helper/1"})
        with urllib.request.urlopen(request, timeout=5) as response:
            raw = response.read(MAX_ONBOARDING_HOW_TO_BYTES + 1)
        if len(raw) > MAX_ONBOARDING_HOW_TO_BYTES:
            raise ValueError(f"onboarding how-to prompt exceeds {MAX_ONBOARDING_HOW_TO_BYTES} bytes")
        text = raw.decode("utf-8")
        result.update({"loaded": True, "text": text, "chars": len(text)})
    except (OSError, UnicodeDecodeError, urllib.error.URLError, ValueError) as exc:
        result.update({"error": f"{exc.__class__.__name__}: {exc}"})
    _ONBOARDING_HOW_TO_CACHE[url] = dict(result)
    return result


def hidden_onboarding_guidance(data: Mapping[str, Any] | None = None) -> dict[str, Any]:
    prompt = load_onboarding_how_to_prompt(data)
    source = {key: prompt[key] for key in ("url", "loaded", "error", "chars") if key in prompt}
    return {
        "agent_hidden_onboarding_how_to": prompt.get("text", ""),
        "agent_hidden_onboarding_how_to_source": source,
    }


def parse_github_source_lead(source_path: str) -> dict[str, str] | None:
    match = GITHUB_TREE_RE.match(source_path.strip())
    if not match:
        return None
    owner, repo, kind, ref, path = match.groups()
    return {
        "owner": owner,
        "repo": repo.removesuffix(".git"),
        "kind": kind,
        "ref": ref,
        "path": path.strip("/"),
    }


def fetch_json_url(url: str) -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "cf-controlplane-source-research/1",
        },
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_text_url(url: str, *, max_bytes: int = MAX_SOURCE_RESEARCH_FILE_BYTES) -> tuple[str, bool]:
    request = urllib.request.Request(url, headers={"User-Agent": "cf-controlplane-source-research/1"})
    with urllib.request.urlopen(request, timeout=10) as response:
        raw = response.read(max_bytes + 1)
    truncated = len(raw) > max_bytes
    return raw[:max_bytes].decode("utf-8", errors="replace"), truncated


def fetch_npm_package_metadata(package_name: str) -> dict[str, Any]:
    encoded = urllib.parse.quote(package_name, safe="")
    metadata = fetch_json_url(f"https://registry.npmjs.org/{encoded}")
    if not isinstance(metadata, Mapping):
        return {}
    latest = ""
    dist_tags = metadata.get("dist-tags") if isinstance(metadata.get("dist-tags"), Mapping) else {}
    if dist_tags:
        latest = str(dist_tags.get("latest") or "")
    return {
        "registry": "npm",
        "package": package_name,
        "latest": latest,
        "dist_tags": dict(dist_tags),
        "description": str(metadata.get("description") or ""),
        "repository": metadata.get("repository") if isinstance(metadata.get("repository"), Mapping) else {},
    }


def github_contents_api_url(parsed: Mapping[str, str], path: str) -> str:
    quoted_path = urllib.parse.quote(path.strip("/"))
    ref = urllib.parse.quote(parsed["ref"])
    return f"https://api.github.com/repos/{parsed['owner']}/{parsed['repo']}/contents/{quoted_path}?ref={ref}"


def should_fetch_source_file(entry: Mapping[str, Any]) -> bool:
    name = str(entry.get("name") or "")
    if not name or name.startswith(".") or name in SOURCE_RESEARCH_SKIP_NAMES:
        return False
    suffix = Path(name).suffix
    return name in SOURCE_RESEARCH_ALLOWED_FILENAMES or suffix in SOURCE_RESEARCH_ALLOWED_SUFFIXES


def source_research_visible_response(result: Mapping[str, Any]) -> str:
    if not result.get("ok"):
        return str(result.get("message") or "Source research failed.")
    files = result.get("source_files")
    file_count = len(files) if isinstance(files, list) else 0
    source_path = str(result.get("source_path") or "the source lead")
    lines = [
        f"Fetched source evidence for `{source_path}`.",
        f"Anchored files available: {file_count}.",
        "Use the returned `source_files[]` entries as source anchors before making implementation claims.",
        "This is source research only; no service was installed, registered, started, exposed, probed, or made available.",
    ]
    warnings = result.get("warnings")
    if isinstance(warnings, list) and warnings:
        lines.append("Warnings: " + "; ".join(str(item) for item in warnings[:3]))
    npm_metadata = result.get("npm_package_metadata")
    if isinstance(npm_metadata, Mapping) and npm_metadata.get("package"):
        latest = f" latest `{npm_metadata.get('latest')}`" if npm_metadata.get("latest") else ""
        lines.append(f"NPM package metadata: `{npm_metadata.get('package')}`{latest}.")
    return "\n".join(lines)


def package_name_from_source_files(source_files: Sequence[Mapping[str, Any]]) -> str:
    for item in source_files:
        if not str(item.get("path") or "").endswith("package.json"):
            continue
        try:
            parsed = json.loads(str(item.get("content") or "{}"))
        except json.JSONDecodeError:
            continue
        name = str(parsed.get("name") or "").strip() if isinstance(parsed, Mapping) else ""
        if name:
            return name
    return ""


def research_service_onboarding_source(project_root: str, data: Mapping[str, Any]) -> dict[str, Any]:
    source_path = str(data.get("source_path") or data.get("sourcePath") or data.get("url") or "").strip()
    result: dict[str, Any] = {
        "status": "service_onboarding_source_research",
        "project_root": project_root,
        "source_path": source_path,
        "mutation_allowed": False,
        "source_files": [],
        "warnings": [],
        "non_actions": [
            "does not install packages",
            "does not start, stop, build, or rebuild services",
            "does not call ContextForge registration APIs",
            "does not write client, project, global, registry, or runtime config",
        ],
    }
    if not source_path:
        result.update({"ok": False, "message": "source_path is required for source research."})
        result["assistant_visible_response"] = source_research_visible_response(result)
        return result
    parsed = parse_github_source_lead(source_path)
    if not parsed:
        result.update(
            {
                "ok": False,
                "message": "Only GitHub tree/blob source leads are currently supported for file-level source research.",
                "unsupported_source_path": source_path,
            }
        )
        result["assistant_visible_response"] = source_research_visible_response(result)
        return result
    total_bytes = 0
    try:
        queue: list[tuple[str, int]] = [(parsed["path"], 0)]
        while queue:
            current_path, depth = queue.pop(0)
            listing = fetch_json_url(github_contents_api_url(parsed, current_path))
            entries = listing if isinstance(listing, list) else [listing]
            for entry in entries:
                if not isinstance(entry, Mapping):
                    continue
                entry_type = str(entry.get("type") or "")
                entry_path = str(entry.get("path") or entry.get("name") or "")
                if entry_type == "dir" and depth < MAX_SOURCE_RESEARCH_DEPTH:
                    queue.append((entry_path, depth + 1))
                    continue
                if entry_type != "file" or not should_fetch_source_file(entry):
                    continue
                download_url = str(entry.get("download_url") or "")
                if not download_url:
                    continue
                if len(result["source_files"]) >= MAX_SOURCE_RESEARCH_FILES:
                    result["warnings"].append(f"file limit reached at {MAX_SOURCE_RESEARCH_FILES}")
                    queue.clear()
                    break
                remaining = MAX_SOURCE_RESEARCH_TOTAL_BYTES - total_bytes
                if remaining <= 0:
                    result["warnings"].append(f"total byte limit reached at {MAX_SOURCE_RESEARCH_TOTAL_BYTES}")
                    queue.clear()
                    break
                text, truncated = fetch_text_url(download_url, max_bytes=min(MAX_SOURCE_RESEARCH_FILE_BYTES, remaining))
                total_bytes += len(text.encode("utf-8", errors="replace"))
                result["source_files"].append(
                    {
                        "path": entry_path,
                        "download_url": download_url,
                        "html_url": str(entry.get("html_url") or ""),
                        "sha": str(entry.get("sha") or ""),
                        "bytes": entry.get("size"),
                        "content": text,
                        "truncated": truncated,
                        "anchor": f"{parsed['owner']}/{parsed['repo']}:{parsed['ref']}:{entry_path}",
                    }
                )
        result.update(
            {
                "ok": True,
                "source_kind": "github_contents_api",
                "github": parsed,
                "retrieved_file_count": len(result["source_files"]),
                "retrieved_content_bytes": total_bytes,
            }
        )
        package_name = package_name_from_source_files(result["source_files"])
        if package_name:
            try:
                metadata = fetch_npm_package_metadata(package_name)
                if metadata:
                    result["npm_package_metadata"] = metadata
            except (OSError, urllib.error.URLError, json.JSONDecodeError, UnicodeDecodeError) as exc:
                result["warnings"].append(f"npm metadata fetch failed for {package_name}: {exc.__class__.__name__}: {exc}")
    except (OSError, urllib.error.URLError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        result.update({"ok": False, "error": f"{exc.__class__.__name__}: {exc}", "message": "Source research fetch failed."})
    result["assistant_visible_response"] = source_research_visible_response(result)
    return result


def canonical_binding(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text if SERVICE_BINDING_RE.fullmatch(text) else ""


def package_alias(value: Any) -> str:
    return re.sub(r"[^a-z0-9_.-]+", "-", str(value or "").lower()).strip(".-")


def instance_identity_aliases(instance: Mapping[str, Any]) -> set[str]:
    aliases = {
        package_alias(instance.get("name")),
        package_alias(instance.get("slug")),
        package_alias(instance.get("service")),
        package_alias(str(instance.get("service_binding") or "").split(":", 1)[0]),
    }
    backend = instance.get("backend") if isinstance(instance.get("backend"), Mapping) else {}
    aliases.add(package_alias(backend.get("package")))
    aliases.add(package_alias(backend.get("command")))
    for arg in backend.get("args") or []:
        aliases.add(package_alias(arg))
    return {alias for alias in aliases if alias}


def iter_service_instances() -> list[dict[str, Any]]:
    instances: list[dict[str, Any]] = []
    for instance_path in sorted((REPO_ROOT / "server-instances").glob("*/instance.json")):
        try:
            instance = json.loads(instance_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(instance, Mapping):
            instances.append(dict(instance))
    return instances


def service_onboarding_descriptor(data: Mapping[str, Any]) -> dict[str, Any]:
    descriptor = data.get("descriptor")
    if isinstance(descriptor, Mapping):
        return dict(descriptor)
    service = data.get("candidate_service") or data.get("candidateService") or data.get("service")
    source_path = data.get("source_path") or data.get("sourcePath") or data.get("path")
    expected_tools = data.get("expected_tools") or data.get("expectedTools")
    if isinstance(expected_tools, str):
        expected_tools = [expected_tools]
    source_evidence = []
    if source_path and not synthetic_source_summary(str(source_path)):
        source_evidence.append({"type": lead_type(str(source_path)), "ref": str(source_path)})
    operator_goal = data.get("operator_goal") or data.get("operatorGoal") or data.get("goal")
    if not operator_goal and service:
        operator_goal = f"Prepare a source-only onboarding plan for the uncataloged MCP service {service}."
    return {
        "candidate_service": str(service) if service else None,
        "operator_goal": operator_goal,
        "source_evidence": source_evidence,
        "classification": {
            "plan_type": data.get("plan_type") or data.get("planType") or "source_only_scaffolding",
            "localization_type": data.get("localization_type") or data.get("localizationType"),
            "functional_type": data.get("functional_type") or data.get("functionalType"),
            "transport_type": data.get("transport_type") or data.get("transportType"),
            "state_type": data.get("state_type") or data.get("stateType"),
            "approval_type": data.get("approval_type") or data.get("approvalType") or "source_only",
        },
        "credential_boundary": data.get("credential_boundary") or data.get("credentialBoundary"),
        "credential_required": data.get("credential_required") or data.get("credentialRequired"),
        "expected_tools": expected_tools if isinstance(expected_tools, list) else [],
        "validation_probe_plan": data.get("validation_probe_plan") or data.get("validationProbePlan") or [],
        "footprint": data.get("footprint") if isinstance(data.get("footprint"), Mapping) else {},
    }


def _list_field(data: Mapping[str, Any], *keys: str) -> list[Any]:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, Sequence) and not isinstance(parsed, (str, bytes, bytearray)):
                return [item for item in parsed]
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            return [item for item in value]
    return []


def _argument_text(item: Any) -> str:
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, Mapping):
        value = item.get("arg") or item.get("value") or item.get("argument") or item.get("name")
        if value is not None:
            return str(value).strip()
    return ""


def _meaningful_payload_items(data: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in data.items():
        if value is None:
            continue
        if isinstance(value, bool):
            if value:
                result[key] = value
            continue
        if value in ("", [], {}):
            continue
        result[key] = value
    return result


def _structured_payload_artifact_path(data: Mapping[str, Any]) -> str:
    for key in (
        "structured_payload_path",
        "structuredPayloadPath",
        "runtime_apply_payload_path",
        "runtimeApplyPayloadPath",
        "onboarding_payload_path",
        "onboardingPayloadPath",
    ):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _project_local_artifact_path(project_root: str | Path, raw_path: str) -> Path:
    root = Path(project_root).resolve(strict=False)
    path = Path(raw_path)
    if not path.is_absolute():
        path = root / path
    resolved = path.resolve(strict=False)
    if root not in (resolved, *resolved.parents):
        raise ValueError(f"structured_payload_path must stay under project_root: {raw_path}")
    return resolved


def merge_structured_payload_artifact(project_root: str | Path, data: Mapping[str, Any]) -> dict[str, Any]:
    path_value = _structured_payload_artifact_path(data)
    if not path_value:
        return dict(data)
    path = _project_local_artifact_path(project_root, path_value)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"structured_payload_path must contain a JSON object: {path}")
    merged = {**dict(payload), **_meaningful_payload_items(data)}
    merged["structured_payload_path"] = str(path)
    return merged


def _environment_entry(item: Any, required_secret_names: set[str]) -> dict[str, Any] | None:
    if isinstance(item, Mapping):
        name = str(item.get("name") or item.get("key") or "").strip()
        value = item.get("value")
        if not name and len(item) == 1:
            name, value = next(iter(item.items()))
            name = str(name).strip()
        if not name:
            return None
        secret = bool(item.get("secret") or item.get("is_secret") or item.get("isSecret") or name in required_secret_names)
        entry: dict[str, Any] = {"name": name, "secret": secret}
        if item.get("description"):
            entry["description"] = str(item["description"])
        if not secret and value is not None:
            entry["value"] = str(value)
        return entry
    name = str(item).strip()
    if not name:
        return None
    return {"name": name, "secret": name in required_secret_names}


def _mapping_field(data: Mapping[str, Any], *keys: str) -> dict[str, Any]:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, Mapping):
                return dict(parsed)
        if isinstance(value, Mapping):
            return dict(value)
    return {}


def _tool_schema_field(data: Mapping[str, Any]) -> dict[str, Any]:
    mapping = _mapping_field(data, "tool_schemas", "toolSchemas")
    if mapping:
        return mapping
    records = _tool_schema_records_field(data)
    if records:
        return records
    return {}


def _tool_schema_records_field(data: Mapping[str, Any]) -> dict[str, Any]:
    records = data.get("tool_schema_records") or data.get("toolSchemaRecords")
    if isinstance(records, str) and records.strip():
        try:
            records = json.loads(records)
        except json.JSONDecodeError:
            return {}
    if not isinstance(records, Sequence) or isinstance(records, (str, bytes, bytearray)):
        return {}
    result: dict[str, Any] = {}
    for item in records:
        if not isinstance(item, Mapping):
            continue
        name = str(item.get("name") or item.get("tool") or item.get("tool_name") or item.get("toolName") or "").strip()
        if not name:
            continue
        schema: dict[str, Any] = {}
        description = str(item.get("description") or "").strip()
        if description:
            schema["description"] = description
        input_schema = item.get("input_schema") if "input_schema" in item else item.get("inputSchema")
        if isinstance(input_schema, Mapping):
            schema["inputSchema"] = dict(input_schema)
        elif isinstance(item.get("schema"), Mapping):
            schema["inputSchema"] = dict(item["schema"])
        source_anchor = item.get("source_anchor") or item.get("sourceAnchor") or item.get("source")
        if source_anchor:
            schema["source_anchor"] = str(source_anchor)
        if schema:
            result[name] = schema
    return result


def _tool_schema_summaries_field(data: Mapping[str, Any]) -> dict[str, Any]:
    summaries = data.get("tool_schema_summaries") or data.get("toolSchemaSummaries")
    if isinstance(summaries, str) and summaries.strip():
        try:
            summaries = json.loads(summaries)
        except json.JSONDecodeError:
            return {"_summary": summaries.strip()}
    if isinstance(summaries, Mapping):
        return dict(summaries)
    if isinstance(summaries, Sequence) and not isinstance(summaries, (str, bytes, bytearray)):
        result: dict[str, Any] = {}
        for index, item in enumerate(summaries, start=1):
            if isinstance(item, Mapping):
                name = str(item.get("name") or item.get("tool") or f"tool_{index}").strip()
                if name:
                    result[name] = {
                        key: value
                        for key, value in item.items()
                        if key in {"description", "input", "input_summary", "inputSummary", "output", "output_summary", "outputSummary"}
                    } or str(item)
            elif str(item).strip():
                result[f"tool_{index}"] = {"summary": str(item).strip()}
        return result
    return {}


def _valid_tool_schema_mapping(value: Any) -> bool:
    if not isinstance(value, Mapping) or not value:
        return False
    for name, schema in value.items():
        if not str(name).strip() or not isinstance(schema, Mapping) or not schema:
            return False
        if not any(key in schema for key in ("description", "input_schema", "inputSchema", "input", "schema", "type", "properties")):
            return False
    return True


def _bool_field(data: Mapping[str, Any], *keys: str) -> bool:
    for key in keys:
        value = data.get(key)
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.lower() in {"true", "yes", "1"}:
            return True
    return False


def service_management_descriptor(data: Mapping[str, Any]) -> dict[str, Any]:
    descriptor = service_onboarding_descriptor(data)
    service = (
        descriptor.get("candidate_service")
        or data.get("candidate_service")
        or data.get("candidateService")
        or data.get("service")
    )
    if service:
        descriptor["service_family"] = str(service)
        descriptor["canonical_service"] = str(service)

    backend = dict(descriptor.get("backend") or {})
    package = (
        data.get("backend_package")
        or data.get("backendPackage")
        or data.get("package")
        or data.get("packageName")
    )
    command = (
        data.get("backend_command")
        or data.get("backendCommand")
        or data.get("command")
        or data.get("commandName")
    )
    transport = (
        data.get("transport_type")
        or data.get("transportType")
        or descriptor.get("classification", {}).get("transport_type")
    )
    if package:
        backend["package"] = str(package)
    package_registry_type = data.get("package_registry_type") or data.get("packageRegistryType")
    if package_registry_type:
        backend["package_registry_type"] = str(package_registry_type)
    package_version = data.get("package_version") or data.get("packageVersion") or data.get("backend_version") or data.get("backendVersion")
    if package_version:
        backend["package_version"] = str(package_version)
    runtime_hint = data.get("runtime_hint") or data.get("runtimeHint")
    if runtime_hint:
        backend["runtime_hint"] = str(runtime_hint)
    package_arguments = _list_field(data, "package_arguments", "packageArguments")
    if package_arguments:
        backend["package_arguments"] = package_arguments
    backend_args = _list_field(data, "backend_args", "backendArgs")
    if backend_args:
        backend["runtime_arguments"] = backend_args
    runtime_arguments = _list_field(data, "runtime_arguments", "runtimeArguments")
    if runtime_arguments:
        backend["runtime_arguments"] = runtime_arguments
    environment_variables = _list_field(data, "environment_variables", "environmentVariables")
    if environment_variables:
        backend["environment_variables"] = environment_variables
    required_secret_names = _list_field(data, "required_secret_names", "requiredSecretNames")
    if required_secret_names:
        descriptor["required_secret_names"] = [str(item) for item in required_secret_names if str(item).strip()]
    descriptor["npm_package_confirmed"] = _bool_field(data, "npm_package_confirmed", "npmPackageConfirmed")
    descriptor["environment_variables_reviewed"] = _bool_field(data, "environment_variables_reviewed", "environmentVariablesReviewed")
    descriptor["package_arguments_reviewed"] = _bool_field(data, "package_arguments_reviewed", "packageArgumentsReviewed")
    tool_schemas = _tool_schema_field(data)
    if tool_schemas:
        descriptor["tool_schemas"] = tool_schemas
    tool_schema_summaries = _tool_schema_summaries_field(data)
    if tool_schema_summaries:
        descriptor["tool_schema_summaries"] = tool_schema_summaries
    prompt_library = _mapping_field(data, "prompt_library", "promptLibrary")
    if prompt_library:
        if "abstractPrompt" in prompt_library and "abstract_prompt" not in prompt_library:
            prompt_library["abstract_prompt"] = prompt_library["abstractPrompt"]
        if "detailPrompts" in prompt_library and "detail_prompts" not in prompt_library:
            prompt_library["detail_prompts"] = prompt_library["detailPrompts"]
        descriptor["prompt_library"] = prompt_library
    if command:
        backend["command"] = str(command)
    elif package and str(runtime_hint or "").strip().lower() == "npx":
        backend["command"] = "npx"
    elif package:
        backend["command"] = str(package)
    if transport:
        backend["transport"] = str(transport)
        backend["native_transports"] = [str(transport)]
    if backend:
        descriptor["backend"] = backend

    localization = (
        data.get("localization_type")
        or data.get("localizationType")
        or descriptor.get("classification", {}).get("localization_type")
    )
    scope = dict(descriptor.get("scope") or {})
    if localization == "project_scoped":
        scope["runtime_scope"] = "project"
    elif localization in {"shared_canonical", "remote_native_hosted"}:
        scope["runtime_scope"] = "host"
    elif localization == "credential_scoped":
        scope["runtime_scope"] = "credential"
    elif localization == "client_local_session_scoped":
        scope["runtime_scope"] = "session"
    credential_boundary = data.get("credential_boundary") or data.get("credentialBoundary")
    if credential_boundary:
        scope["credential_scope"] = str(credential_boundary)
    if scope:
        descriptor["scope"] = scope

    source_path = data.get("source_path") or data.get("sourcePath") or data.get("path")
    if source_path:
        descriptor["source_lead"] = str(source_path)
    issue = data.get("issue") or data.get("issue_number") or data.get("issueNumber")
    if issue:
        descriptor["issue"] = str(issue)
    return descriptor


def runtime_apply_required_input_gaps(descriptor: Mapping[str, Any]) -> list[dict[str, str]]:
    backend = descriptor.get("backend") if isinstance(descriptor.get("backend"), Mapping) else {}
    prompt_library = descriptor.get("prompt_library") if isinstance(descriptor.get("prompt_library"), Mapping) else {}
    gaps: list[dict[str, str]] = []
    if not descriptor.get("npm_package_confirmed"):
        gaps.append(
            {
                "field": "npm_package_confirmed",
                "reason": "the assistant must confirm the exact npm package with the user before install/register packaging",
            }
        )
    if not str(backend.get("package") or "").strip():
        gaps.append({"field": "backend_package", "reason": "exact npm package identifier is required"})
    if str(backend.get("package_registry_type") or "").lower() != "npm":
        gaps.append({"field": "package_registry_type", "reason": "initial managed-host target accepts npm packages only"})
    if str(backend.get("transport") or "").lower() != "stdio":
        gaps.append({"field": "transport_type", "reason": "initial managed-host target accepts stdio MCP transports only"})
    if not descriptor.get("environment_variables_reviewed"):
        gaps.append(
            {
                "field": "environment_variables_reviewed",
                "reason": "assistant must research/determine required, optional, and secret environment variables, even when the result is none",
            }
        )
    if not descriptor.get("package_arguments_reviewed"):
        gaps.append(
            {
                "field": "package_arguments_reviewed",
                "reason": "assistant must research/determine package/runtime arguments, even when the result is none",
            }
        )
    if not _valid_tool_schema_mapping(descriptor.get("tool_schemas")):
        gaps.append(
            {
                "field": "tool_schemas",
                "reason": "structured tool schemas are required as an object mapping tool name to source-derived schema object, or as tool_schema_records/toolSchemaRecords array entries with name, description, and input_schema/inputSchema; summaries or string arrays are not accepted as a substitute",
            }
        )
    if not str(prompt_library.get("abstract_prompt") or "").strip():
        gaps.append({"field": "prompt_library.abstract_prompt", "reason": "standard abstract prompt content is mandatory"})
    detail_prompts = prompt_library.get("detail_prompts")
    if not isinstance(detail_prompts, Mapping) or not detail_prompts:
        gaps.append({"field": "prompt_library.detail_prompts", "reason": "lazy-loaded detailed prompt content is mandatory"})
    return gaps


def runtime_apply_blocked_response(candidate: str, gaps: Sequence[Mapping[str, str]]) -> str:
    lines = [
        f"I cannot prepare the runtime install/register package for `{candidate}` yet.",
        "The helper does not research missing service facts; the code assistant must provide source-derived information before install/register packaging.",
        "Required before continuing:",
    ]
    for gap in gaps:
        lines.append(f"- `{gap.get('field')}`: {gap.get('reason')}")
    lines.append(
        "When retrying, resubmit the complete source-derived field set in one call; "
        "the helper does not merge accepted values from earlier failed attempts."
    )
    if any(str(gap.get("field") or "") in {"tool_schemas", "prompt_library.detail_prompts"} for gap in gaps):
        lines.append(
            "For large structured payloads, the assistant may write a project-local JSON object containing the "
            "complete source-derived field set and pass its path as `structured_payload_path`/`structuredPayloadPath`; "
            "that file may include `toolSchemas` or `toolSchemaRecords` plus `promptLibrary`."
        )
    lines.extend(
        [
            "After those facts are supplied, ask me to build the runtime/apply package again.",
            "No runtime, registry, Docker, prompt-library, client config, or project activation mutation has been performed.",
        ]
    )
    return "\n".join(lines)


RUNTIME_APPLY_DRAFT_SLICES: list[dict[str, Any]] = [
    {
        "id": "identity",
        "title": "Service and package identity",
        "fields": [
            "candidate_service",
            "operator_goal",
            "source_path",
            "backend_package",
            "package_registry_type",
            "package_version",
            "npm_package_confirmed",
        ],
    },
    {
        "id": "transport",
        "title": "Transport and command",
        "fields": [
            "transport_type",
            "backend_command",
            "backend_args",
            "runtime_hint",
            "package_arguments_reviewed",
            "package_arguments",
        ],
    },
    {
        "id": "environment",
        "title": "Environment and credential boundary",
        "fields": [
            "credential_boundary",
            "environment_variables_reviewed",
            "environment_variables",
            "required_secret_names",
        ],
    },
    {
        "id": "tool_schemas",
        "title": "Tool schemas",
        "fields": [
            "expected_tools",
            "tool_schema_records",
            "tool_schemas",
            "tool_schema_summaries",
        ],
    },
    {
        "id": "prompt_library",
        "title": "Prompt library and classification",
        "fields": [
            "localization_type",
            "functional_type",
            "state_type",
            "approval_type",
            "prompt_library",
        ],
    },
]


def runtime_apply_draft_cache_dir(project_root: str | Path) -> Path:
    return Path(project_root).resolve(strict=False) / RUNTIME_APPLY_DRAFT_CACHE_DIR


def runtime_apply_draft_id(data: Mapping[str, Any]) -> str:
    for key in ("runtime_apply_draft_id", "runtimeApplyDraftId", "draft_id", "draftId"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            normalized = value.strip()
            if not re.fullmatch(r"rad_[a-z0-9_.-]+", normalized):
                raise ValueError("runtime_apply_draft_id must start with rad_ and contain only letters, digits, underscores, dots, or dashes")
            return normalized
    service = str(data.get("candidate_service") or data.get("candidateService") or data.get("service") or "").strip()
    package = str(data.get("backend_package") or data.get("backendPackage") or data.get("package") or "").strip()
    source = str(data.get("source_path") or data.get("sourcePath") or "").strip()
    material = service or package or source or "unnamed-service"
    return "rad_" + package_alias(material)[:80].strip(".-")


def runtime_apply_draft_path(project_root: str | Path, draft_id: str) -> Path:
    if not re.fullmatch(r"rad_[a-z0-9_.-]+", draft_id):
        raise ValueError("runtime_apply_draft_id must start with rad_ and contain only letters, digits, underscores, dots, or dashes")
    return runtime_apply_draft_cache_dir(project_root) / f"{draft_id}.json"


def load_runtime_apply_draft(project_root: str | Path, draft_id: str) -> dict[str, Any]:
    path = runtime_apply_draft_path(project_root, draft_id)
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"runtime apply draft is not a JSON object: {path}")
    return dict(payload)


def store_runtime_apply_draft(project_root: str | Path, draft_id: str, payload: Mapping[str, Any]) -> Path:
    cache_dir = runtime_apply_draft_cache_dir(project_root)
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = runtime_apply_draft_path(project_root, draft_id)
    content = dict(payload)
    content["runtime_apply_draft_id"] = draft_id
    path.write_text(json.dumps(content, indent=2, sort_keys=True), encoding="utf-8")
    return path


def runtime_apply_draft_slice_for_gap(field: str) -> dict[str, Any]:
    root = field.split(".", 1)[0]
    for item in RUNTIME_APPLY_DRAFT_SLICES:
        if field in item["fields"] or root in item["fields"]:
            return item
    return RUNTIME_APPLY_DRAFT_SLICES[0]


def runtime_apply_draft_status(project_root: str, data: Mapping[str, Any]) -> dict[str, Any]:
    draft_id = runtime_apply_draft_id(data)
    previous = load_runtime_apply_draft(project_root, draft_id)
    merged = {**previous, **_meaningful_payload_items(merge_structured_payload_artifact(project_root, data))}
    merged.pop("structured_payload_path", None)
    merged.pop("structuredPayloadPath", None)
    merged.pop("runtimeApplyDraftId", None)
    merged.pop("draftId", None)
    merged["runtime_apply_draft_id"] = draft_id
    draft_path = store_runtime_apply_draft(project_root, draft_id, merged)
    descriptor = service_management_descriptor(merged)
    gaps = runtime_apply_required_input_gaps(descriptor)
    accepted_fields = sorted(key for key, value in _meaningful_payload_items(merged).items() if key != "runtime_apply_draft_id")
    if gaps:
        next_slice = runtime_apply_draft_slice_for_gap(str(gaps[0].get("field") or ""))
        ready = False
        status = "service_onboarding_runtime_apply_draft_incomplete"
    else:
        next_slice = {
            "id": "build_package",
            "title": "Build runtime/apply package",
            "fields": ["structuredPayloadPath"],
        }
        ready = True
        status = "service_onboarding_runtime_apply_draft_ready"
    visible = runtime_apply_draft_visible_response(
        draft_id=draft_id,
        draft_path=draft_path,
        ready=ready,
        next_slice=next_slice,
        gaps=gaps,
    )
    return {
        "status": status,
        "project_root": project_root,
        "mutation_allowed": False,
        "runtime_apply_draft_id": draft_id,
        "structured_payload_path": str(draft_path),
        "ready_to_build_runtime_apply_package": ready,
        "accepted_fields": accepted_fields,
        "required_inputs": gaps,
        "next_required_slice": next_slice,
        "assistant_visible_response": visible,
        "message": visible,
        "non_actions": [
            "does not call ContextForge APIs",
            "does not mutate the shared npm-stdio host",
            "does not write prompt-library content",
            "does not write client-local MCP config",
            "does not build or execute the runtime/apply package",
        ],
    }


def runtime_apply_draft_visible_response(
    *,
    draft_id: str,
    draft_path: Path,
    ready: bool,
    next_slice: Mapping[str, Any],
    gaps: Sequence[Mapping[str, str]],
) -> str:
    lines = [
        f"Updated the onboarding draft `{draft_id}`.",
        f"Draft payload path: `{draft_path}`.",
        "This is a non-mutating just-in-time draft step.",
    ]
    if ready:
        lines.extend(
            [
                "The draft now has the required source-derived fields for runtime/apply package preview.",
                "Next step: call the runtime/apply package preview with `structuredPayloadPath` set to the draft payload path.",
                "Do not claim runtime, ContextForge, target-client, or safe-call readiness from this draft step.",
            ]
        )
    else:
        lines.extend(
            [
                f"Next bounded ask: {next_slice.get('title')}.",
                "Provide only that slice if possible; the helper will keep composing the draft.",
                "Still required:",
            ]
        )
        for gap in gaps[:8]:
            lines.append(f"- `{gap.get('field')}`: {gap.get('reason')}")
    lines.append("No runtime, registry, Docker, prompt-library, client config, or project activation mutation has been performed.")
    return "\n".join(lines)


def runtime_apply_package_cache_dir(project_root: str | Path) -> Path:
    return Path(project_root).resolve(strict=False) / RUNTIME_APPLY_PACKAGE_CACHE_DIR


def runtime_apply_package_id(package: Mapping[str, Any]) -> str:
    material = {
        "schema": "contextforge://control-plane/service-onboarding-runtime-apply-package-id/v1",
        "service_provision_plan": package.get("service_provision_plan"),
        "contextforge_registration_plan": package.get("contextforge_registration_plan"),
        "install_artifact_contract": package.get("install_artifact_contract"),
    }
    return "rap_" + hashlib.sha256(json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()[:24]


def store_runtime_apply_package(project_root: str | Path, package: Mapping[str, Any]) -> dict[str, str]:
    package_id = runtime_apply_package_id(package)
    cache_dir = runtime_apply_package_cache_dir(project_root)
    cache_dir.mkdir(parents=True, exist_ok=True)
    package_path = cache_dir / f"{package_id}.json"
    content = dict(package)
    content["runtime_apply_package_id"] = package_id
    package_path.write_text(json.dumps(content, indent=2, sort_keys=True), encoding="utf-8")
    return {"runtime_apply_package_id": package_id, "runtime_apply_package_path": str(package_path)}


def load_runtime_apply_package(project_root: str | Path, package_id: str) -> dict[str, Any]:
    normalized = str(package_id or "").strip()
    if not re.fullmatch(r"rap_[a-f0-9]{24}", normalized):
        raise ValueError("runtime_apply_package_id must be a recorded rap_<digest> id from cf_project_service_onboarding_runtime_apply")
    package_path = runtime_apply_package_cache_dir(project_root) / f"{normalized}.json"
    if not package_path.exists():
        raise FileNotFoundError(f"recorded runtime_apply_package_id was not found: {normalized}")
    package = json.loads(package_path.read_text(encoding="utf-8"))
    if not isinstance(package, Mapping):
        raise ValueError(f"recorded runtime_apply_package_id is not an object: {normalized}")
    return dict(package)


def runtime_apply_package_identity(project_root: str | Path, package_id: str) -> dict[str, str]:
    package = load_runtime_apply_package(project_root, package_id)
    provision = package.get("service_provision_plan") if isinstance(package.get("service_provision_plan"), Mapping) else {}
    registration = package.get("contextforge_registration_plan") if isinstance(package.get("contextforge_registration_plan"), Mapping) else {}
    boundary = package.get("runtime_apply_boundary") if isinstance(package.get("runtime_apply_boundary"), Mapping) else {}
    descriptor = registration.get("candidate_descriptor") if isinstance(registration.get("candidate_descriptor"), Mapping) else {}
    backend = descriptor.get("backend") if isinstance(descriptor.get("backend"), Mapping) else {}
    return {
        "candidate_service": str(descriptor.get("candidate_service") or descriptor.get("canonical_service") or ""),
        "service_binding": str(provision.get("service_binding") or ""),
        "source_path": str(descriptor.get("source_lead") or ""),
        "backend_package": str(backend.get("package") or ""),
        "executor_surface": str(boundary.get("recorded_executor_surface") or ""),
    }


def build_service_onboarding_plan(project_root: str, data: Mapping[str, Any]) -> dict[str, Any]:
    data = merge_structured_payload_artifact(project_root, data)
    record = service_onboarding.build_onboarding_record(
        service_onboarding_descriptor(data),
        project_root=project_root,
        issue=str(data.get("issue") or data.get("issue_number") or data.get("issueNumber") or ""),
        session_id=str(data.get("session_id") or data.get("sessionId") or "") or None,
    )
    visible = service_onboarding_visible_response(record)
    return {
        "status": "source_only_onboarding_plan",
        "project_root": project_root,
        "mutation_allowed": False,
        "assistant_visible_response": visible,
        "message": visible,
        **hidden_onboarding_guidance(data),
        "record": record,
        "non_actions": record.get("non_actions") or [],
    }


def build_service_onboarding_continuation(project_root: str, data: Mapping[str, Any]) -> dict[str, Any]:
    data = merge_structured_payload_artifact(project_root, data)
    descriptor = service_management_descriptor(data)
    handoff = service_handoffs.build_catalog_candidate_handoff(
        descriptor,
        project_root=project_root,
        source="project_init",
        reason="approved_uncataloged_onboarding_continuation",
    )
    result = service_management.plan_service_management_from_handoff(handoff)
    candidate = (
        descriptor.get("candidate_service")
        or descriptor.get("canonical_service")
        or descriptor.get("service_family")
        or "the candidate service"
    )
    visible = service_management_visible_response(result, str(candidate))
    return {
        "status": "service_onboarding_continuation_plan",
        "project_root": project_root,
        "mutation_allowed": False,
        "assistant_visible_response": visible,
        "message": visible,
        **hidden_onboarding_guidance(data),
        "handoff": handoff,
        "service_management_result": result,
        "non_actions": [
            "does not call ContextForge APIs",
            "does not start, stop, build, or rebuild Docker containers",
            "does not write client or project activation config",
            "does not claim target-client-visible service availability",
        ],
    }


def build_service_onboarding_runtime_apply_package(project_root: str, data: Mapping[str, Any]) -> dict[str, Any]:
    data = merge_structured_payload_artifact(project_root, data)
    descriptor = service_management_descriptor(data)
    candidate = (
        descriptor.get("candidate_service")
        or descriptor.get("canonical_service")
        or descriptor.get("service_family")
        or service_binding_for_descriptor(data, descriptor)
    )
    required_input_gaps = runtime_apply_required_input_gaps(descriptor)
    if required_input_gaps:
        visible = runtime_apply_blocked_response(str(candidate), required_input_gaps)
        return {
            "status": "service_onboarding_runtime_apply_blocked",
            "project_root": project_root,
            "mutation_allowed": False,
            "assistant_visible_response": visible,
            "message": visible,
            **hidden_onboarding_guidance(data),
            "required_inputs": required_input_gaps,
            "non_actions": [
                "does not call ContextForge APIs",
                "does not mutate the shared npm-stdio host",
                "does not write prompt-library content",
                "does not write client-local MCP config",
            ],
        }
    service_binding = service_binding_for_descriptor(data, descriptor)
    canonical_family = service_binding.split(":", 1)[0]
    descriptor = dict(descriptor)
    descriptor["canonical_service"] = canonical_family
    descriptor["service_family"] = canonical_family
    handoff = service_handoffs.build_catalog_candidate_handoff(
        descriptor,
        project_root=project_root,
        source="project_init",
        reason="approved_uncataloged_onboarding_runtime_apply_package",
    )
    management_result = service_management.plan_service_management_from_handoff(handoff)
    catalog_plan = management_result.get("x_catalog_plan") if isinstance(management_result.get("x_catalog_plan"), Mapping) else {}
    backend_command = backend_command_for_descriptor(data, descriptor)
    backend_home = service_provision.backend_home_path(project_root, service_binding)
    provision_plan = service_provision.build_service_provision_plan(
        project_root=project_root,
        service_binding=service_binding,
        plan_id=str(data.get("plan_id") or data.get("planId") or f"service-onboarding-runtime-apply-{service_provision.service_slug(service_binding)}"),
        backend_command=backend_command,
        owned_write_set=[
            backend_home,
            f"{backend_home}/{service_provision.ENV_PLACEHOLDER_FILENAME}",
            f"{backend_home}/{service_provision.MANIFEST_FILENAME}",
            f"user-systemd:contextforge-{service_provision.service_slug(service_binding)}.service",
        ],
        stale_input_refs=[artifact_ref("stale-inputs/source-onboarding-handoff", handoff)],
        consent_receipt_refs=[artifact_ref("planned-consent/runtime-apply-approval", {"service_binding": service_binding})],
        verification_trace_refs=[artifact_ref("planned-traces/backend-readiness", {"service_binding": service_binding})],
        ports=ports_for_descriptor(data, descriptor),
        readiness_probes=readiness_probes_for_descriptor(data, descriptor),
        required_env=env_keys_for_descriptor(data, descriptor, key="required_env"),
        optional_env=env_keys_for_descriptor(data, descriptor, key="optional_env"),
        policy_refs=[artifact_ref("planned-policies/service-tool-policy", {"service_binding": service_binding})],
        conformance_refs=[artifact_ref("planned-conformance/target-client-reload", {"service_binding": service_binding})],
        upstream={
            "source": descriptor.get("source_lead"),
            "backend": descriptor.get("backend") or {},
            "expected_tools": descriptor.get("expected_tools") or [],
        },
    )
    candidate = candidate or service_binding
    preview_package = {
        "contextforge_registration_plan": catalog_plan,
        "service_provision_plan": provision_plan,
    }
    runtime_target: dict[str, str] = {}
    runtime_target_error = ""
    try:
        runtime_target = dev_runtime_target_for_package(preview_package, data)
    except RuntimeError as exc:
        runtime_target_error = str(exc)
    install_contract = install_artifact_contract(
        service_binding=service_binding,
        descriptor=descriptor,
        provision_plan=provision_plan,
        catalog_plan=catalog_plan,
        runtime_target=runtime_target,
        backend_command=backend_command,
        project_root=project_root,
    )
    package: dict[str, Any] = {
        "status": "service_onboarding_runtime_apply_package",
        "project_root": project_root,
        "mutation_allowed": False,
        **hidden_onboarding_guidance(data),
        "handoff": handoff,
        "service_management_result": management_result,
        "service_provision_plan": provision_plan,
        "contextforge_registration_plan": catalog_plan,
        "install_artifact_contract": install_contract,
        "runtime_apply_boundary": {
            "runtime_executor_approval_required": True,
            "recorded_executor_surface": runtime_target.get("executor_surface", ""),
            "recorded_gateway_name": runtime_target.get("gateway_name", ""),
            "recorded_virtual_server_name": runtime_target.get("virtual_server_name", ""),
            "recorded_upstream_url": runtime_target.get("upstream_url", ""),
            "runtime_target_error": runtime_target_error,
            "remaining_layers": [
                "backend_ready",
                "contextforge_ready",
                "target_client_ready",
                "verified",
            ],
            "executor_must_use": "approved ContextForge development surface and public API/operator scripts",
            "executor_must_not_use": "direct client-local MCP config workaround",
        },
        "non_actions": [
            "does not call ContextForge APIs",
            "does not start, stop, build, or rebuild Docker containers",
            "does not write backend homes, systemd units, client config, or project activation state",
            "does not claim target-client-visible service availability",
        ],
    }
    package_ref = store_runtime_apply_package(project_root, package)
    package.update(package_ref)
    visible = runtime_apply_visible_response(
        candidate=str(candidate),
        service_binding=service_binding,
        management_result=management_result,
        provision_plan=provision_plan,
        install_artifact_contract=install_contract,
        runtime_target=runtime_target,
        runtime_target_error=runtime_target_error,
        runtime_apply_package_id=package_ref["runtime_apply_package_id"],
    )
    package["assistant_visible_response"] = visible
    package["message"] = visible
    return package


def install_artifact_contract(
    *,
    service_binding: str,
    descriptor: Mapping[str, Any],
    provision_plan: Mapping[str, Any],
    catalog_plan: Mapping[str, Any],
    runtime_target: Mapping[str, str],
    backend_command: Sequence[str],
    project_root: str | Path | None = None,
) -> dict[str, Any]:
    backend_home = str(provision_plan.get("x_backend_home") or "")
    service = str(
        descriptor.get("canonical_service")
        or descriptor.get("candidate_service")
        or service_binding.split(":", 1)[0]
    )
    expected = [str(tool) for tool in descriptor.get("expected_tools") or [] if tool]
    prompt_library = descriptor.get("prompt_library") if isinstance(descriptor.get("prompt_library"), Mapping) else {}
    backend = descriptor.get("backend") if isinstance(descriptor.get("backend"), Mapping) else {}
    gateway_name = str(
        runtime_target.get("gateway_name")
        or (catalog_plan.get("canonical_names") or {}).get("gateway")
        or f"{service.replace(':', '-')}-gateway"
    )
    virtual_server_name = str(
        runtime_target.get("virtual_server_name")
        or (catalog_plan.get("canonical_names") or {}).get("virtual_server")
        or f"{service.replace(':', '-')}-server"
    )
    upstream_url = str(runtime_target.get("upstream_url") or "<service-container-streamable-http-url>")
    package_arguments = [text for item in backend.get("package_arguments", []) if (text := _argument_text(item))]
    required_secret_names = [
        str(item)
        for item in descriptor.get("required_secret_names", [])
        if str(item).strip()
    ]
    required_secret_name_set = set(required_secret_names)
    environment_variables = []
    environment_values: dict[str, str] = {}
    for item in backend.get("environment_variables", []):
        entry = _environment_entry(item, required_secret_name_set)
        if not entry:
            continue
        if entry.get("value") is not None:
            environment_values[str(entry["name"])] = str(entry["value"])
        environment_variables.append(entry)
    endpoint = npm_stdio_endpoint(service_binding, project_root=project_root)
    runtime_apply_payload_contract = {
        "required_fields": [
            "candidate_service",
            "backend_package",
            "package_registry_type",
            "transport_type",
            "npm_package_confirmed",
            "environment_variables_reviewed",
            "package_arguments_reviewed",
            "tool_schemas",
            "prompt_library.abstract_prompt",
            "prompt_library.detail_prompts",
        ],
        "tool_schemas_shape": {
            "type": "object",
            "description": "Object mapping exact tool name to a source-derived JSON-schema-like object. Do not send an array of strings and do not rely on summaries as the schema.",
            "additionalProperties": {
                "type": "object",
                "recommended_fields": [
                    "description",
                    "input_schema",
                    "source_anchor",
                ],
                "input_schema": "JSON Schema object for the tool input, for example {\"type\":\"object\",\"properties\":{},\"required\":[]}.",
            },
        },
        "tool_schema_records_shape": {
            "type": "array",
            "description": "Compact accepted equivalent for clients that struggle with one large nested object: array of per-tool source-derived records.",
            "items": {
                "type": "object",
                "required": ["name", "description", "inputSchema"],
                "properties": {
                    "name": "Exact tool name.",
                    "description": "Source-derived tool description.",
                    "inputSchema": "JSON Schema object for the tool input.",
                    "sourceAnchor": "Optional source file, URL, or symbol anchor.",
                },
            },
        },
        "tool_schema_summaries_policy": "Accepted only as review notes; summaries do not satisfy the required tool_schemas field.",
        "prompt_library_shape": {
            "abstract_prompt": "Concise proactive service abstract.",
            "detail_prompts": "Object mapping detail prompt id to lazy-loaded task guidance.",
        },
    }
    return {
        "schema_uri": "contextforge://control-plane/service-onboarding-install-artifact-contract/v1",
        "service_binding": service_binding,
        "purpose": "managed npm-stdio host service record plus ContextForge API JSON for reviewed service installation",
        "runtime_apply_payload_contract": runtime_apply_payload_contract,
        "runtime_substrate": {
            "kind": "shared_docker_service",
            "id": "npm-stdio-host",
            "scope": "central ContextForge-managed npm stdio MCP runtime",
            "responsibilities": [
                "install and run npm-published stdio MCP services from managed records",
                "bind declared non-secret environment values and required secret names without exposing secret values",
                "bridge each stdio service to a ContextForge-consumable streamable HTTP/SSE endpoint",
                "support helper-driven CRUD: onboard, read, update, disable, delete",
                "perform idempotent create/update/delete without duplicate hosted-service, bridge, ContextForge, or prompt-library state",
                "roll back partial install/register state before returning failure errors",
            ],
            "non_responsibilities": [
                "stock ContextForge API does not directly install npm packages",
                "target clients must not receive direct client-local MCP config as a workaround",
            ],
        },
        "artifacts": {
            "npm_stdio_service_record": {
                "kind": "file",
                "path": f"{backend_home}/npm-stdio-service.json" if backend_home else "server-instances/<service-slug>/npm-stdio-service.json",
                "must_define": [
                    "npm package identifier and approved version or version policy",
                    "runtime hint such as npx when known",
                    "stdio command arguments and package arguments",
                    "concrete non-secret environment values, or descriptions for optional variables without chosen values",
                    "required secret names and credential boundary without secret values",
                    "shared npm-stdio host endpoint allocation",
                    "no client-local MCP configuration",
                ],
                "content": {
                    "schema_uri": "contextforge://control-plane/managed-npm-stdio-service/v1",
                    "service_binding": service_binding,
                    "host_service": "npm-stdio-host",
                    "idempotency": {
                        "operation_key": service_binding,
                        "duplicate_policy": "converge_on_existing_record",
                        "failure_policy": "rollback_partial_state_before_error_response",
                        "failure_report_must_include": [
                            "failed_stage",
                            "sanitized_error",
                            "rollback_actions_attempted",
                            "rollback_result",
                            "residual_cleanup_risk",
                        ],
                    },
                    "package": str(backend.get("package") or descriptor.get("backend_package") or descriptor.get("package") or ""),
                    "version_policy": str(
                        backend.get("package_version")
                        or descriptor.get("backend_version")
                        or descriptor.get("version")
                        or "source-verified-or-pinned"
                    ),
                    "transport": "stdio",
                    "stdio": {
                        "command": backend_command[0] if backend_command else "",
                        "args": backend_command[1:] if len(backend_command) > 1 else package_arguments,
                    },
                    "package_arguments": package_arguments,
                    "endpoint": endpoint,
                    "expected_tools": expected,
                    "tool_schemas": descriptor.get("tool_schemas") if isinstance(descriptor.get("tool_schemas"), Mapping) else {},
                    "tool_schema_summaries": descriptor.get("tool_schema_summaries") if isinstance(descriptor.get("tool_schema_summaries"), Mapping) else {},
                    "prompt_library": {
                        "abstract_prompt": str(prompt_library.get("abstract_prompt") or ""),
                        "detail_prompts": prompt_library.get("detail_prompts") if isinstance(prompt_library.get("detail_prompts"), Mapping) else {},
                        "publication_required": True,
                        "abstract_prompt_uri": f"contextforge://service-specs/{service}/abstract/v1",
                        "detail_prompt_uri_prefix": f"contextforge://service-specs/{service}/details/",
                    },
                    "credential_boundary": str(descriptor.get("credential_boundary") or "unknown"),
                    "environment": {
                        "required_secret_names": required_secret_names,
                        "variables": environment_variables,
                        "values": environment_values,
                        "non_secret_placeholders_only": True,
                    },
                },
            },
            "contextforge_api_json": {
                "kind": "file",
                "path": f"{backend_home}/contextforge-service.json" if backend_home else "server-instances/<service-slug>/contextforge-service.json",
                "content": {
                    "schema_uri": "contextforge://control-plane/service-onboarding-contextforge-api/v1",
                    "service_binding": service_binding,
                    "expected_tools": expected,
                    "gateway": {
                        "method": "POST",
                        "path": "/gateways",
                        "body": {
                            "name": gateway_name,
                            "url": upstream_url,
                            "transport": "STREAMABLEHTTP",
                            "gateway_mode": "cache",
                            "visibility": "public",
                            "tags": ["contextforge", "service-onboarding", service],
                        },
                    },
                    "tool_refresh": {
                        "method": "POST",
                        "path": "/gateways/{gateway_id}/tools/refresh",
                        "expected_tools": expected,
                    },
                    "virtual_server": {
                        "method": "POST",
                        "path": "/servers",
                        "body": {
                            "server": {
                                "name": virtual_server_name,
                                "associated_tools": "{tool_ids_from_expected_tools}",
                                "visibility": "public",
                                "tags": ["contextforge", "service-onboarding", service],
                            },
                            "visibility": "public",
                        },
                    },
                    "rollback": {
                        "delete_virtual_server": virtual_server_name,
                        "delete_gateway": gateway_name,
                        "remove_discovered_tools_for_gateway": True,
                    },
                },
            },
        },
        "non_actions": [
            "artifact contract does not call ContextForge APIs",
            "artifact contract does not mutate the shared npm-stdio host",
            "artifact contract does not write client-local MCP config",
        ],
    }


def apply_service_onboarding_runtime_package(project_root: str, data: Mapping[str, Any]) -> dict[str, Any]:
    runtime_apply_package_id = str(data.get("runtime_apply_package_id") or data.get("runtimeApplyPackageId") or "").strip()
    package = (
        load_runtime_apply_package(project_root, runtime_apply_package_id)
        if runtime_apply_package_id
        else build_service_onboarding_runtime_apply_package(project_root, data)
    )
    if package.get("status") == "service_onboarding_runtime_apply_blocked":
        failure_report = {
            "failed_stage": "required_inputs",
            "sanitized_error": "runtime/apply cannot proceed until required source-derived onboarding fields are supplied",
            "rollback_actions_attempted": [],
            "rollback_result": "not_run",
            "residual_cleanup_risk": "",
        }
        return {
            "status": package.get("status"),
            "project_root": project_root,
            "mutation_allowed": False,
            "mutation_performed": False,
            "assistant_visible_response": package.get("assistant_visible_response") or package.get("message") or "",
            "message": package.get("message") or package.get("assistant_visible_response") or "",
            "executor_result": {
                "mutation_performed": False,
                "apply_requested": False,
                "failure_report": failure_report,
                "tool_names": [],
                "non_actions": package.get("non_actions") or [],
            },
            "runtime_target": {},
            "required_inputs": package.get("required_inputs") or [],
            "non_actions": package.get("non_actions") or [],
        }
    if runtime_apply_package_id:
        package["runtime_apply_package_id"] = runtime_apply_package_id
    target = dev_runtime_target_for_package(package, data)
    if data.get("require_executor_surface_approval"):
        provision = package.get("service_provision_plan") if isinstance(package.get("service_provision_plan"), Mapping) else {}
        require_runtime_executor_surface_approval(
            str(data.get("approval_text") or ""),
            target,
            service_binding=str(provision.get("service_binding") or ""),
            runtime_apply_package_id=str(package.get("runtime_apply_package_id") or runtime_apply_package_id),
        )
    try:
        result = execute_runtime_apply_package(package, target, data)
    except Exception as exc:
        failure_report = getattr(exc, "failure_report", None)
        if not isinstance(failure_report, Mapping):
            failure_report = {
                "failed_stage": "runtime_apply",
                "sanitized_error": str(exc),
                "rollback_actions_attempted": [],
                "rollback_result": "not_run",
                "residual_cleanup_risk": "runtime/apply failed before structured rollback evidence was returned",
            }
        result = {
            "schema_uri": "contextforge://control-plane/service-onboarding-runtime-package-apply/v1",
            "mutation_performed": False,
            "apply_requested": True,
            "package": {
                "status": package.get("status"),
                "service_binding": package.get("service_provision_plan", {}).get("service_binding"),
                "provision_plan_id": package.get("service_provision_plan", {}).get("provision_plan_id"),
                "catalog_plan_id": package.get("contextforge_registration_plan", {}).get("plan_id"),
            },
            "failure_report": dict(failure_report),
            "non_actions": [
                "runtime/apply failed; no target-client-visible service availability claim is available from this step",
            ],
        }
    if not bool(result.get("mutation_performed")) and not isinstance(result.get("failure_report"), Mapping):
        result = dict(result)
        result["failure_report"] = {
            "failed_stage": "runtime_apply",
            "sanitized_error": "runtime executor returned mutation_performed=false without a structured failure_report",
            "rollback_actions_attempted": [],
            "rollback_result": "unknown",
            "residual_cleanup_risk": "executor did not report rollback status",
        }
        result["non_actions"] = result.get("non_actions") or [
            "runtime/apply failed; no target-client-visible service availability claim is available from this step"
        ]
    candidate = (
        package.get("contextforge_registration_plan", {})
        .get("candidate_descriptor", {})
        .get("candidate_service")
        or package.get("service_provision_plan", {}).get("service_binding")
        or "the candidate service"
    )
    visible = runtime_execute_visible_response(str(candidate), result)
    return {
        "status": "service_onboarding_runtime_applied" if bool(result.get("mutation_performed")) else "service_onboarding_runtime_apply_failed",
        "project_root": project_root,
        "mutation_allowed": True,
        "mutation_performed": bool(result.get("mutation_performed")),
        "assistant_visible_response": visible,
        "message": visible,
        "executor_result": result,
        "runtime_apply_package_id": package.get("runtime_apply_package_id"),
        "runtime_target": {
            "gateway_name": target.get("gateway_name"),
            "virtual_server_name": target.get("virtual_server_name"),
            "upstream_url_recorded": bool(target.get("upstream_url")),
            "executor_surface": target.get("executor_surface"),
        },
        "non_actions": result.get("non_actions") or [],
    }


def runtime_executor_base_url(data: Mapping[str, Any]) -> str:
    return str(
        data.get("contextforge_base_url")
        or data.get("contextforgeBaseUrl")
        or os.environ.get(RUNTIME_EXECUTOR_BASE_URL_ENV)
        or RUNTIME_EXECUTOR_DEFAULT_BASE_URL
    )


def runtime_executor_env_file(data: Mapping[str, Any]) -> Path:
    return Path(
        str(
            data.get("contextforge_env_file")
            or data.get("contextforgeEnvFile")
            or os.environ.get(RUNTIME_EXECUTOR_ENV_FILE_ENV)
            or RUNTIME_EXECUTOR_DEFAULT_ENV_FILE
        )
    )


def execute_runtime_apply_package(package: Mapping[str, Any], target: Mapping[str, str], data: Mapping[str, Any]) -> dict[str, Any]:
    proxy_url = os.environ.get(RUNTIME_EXECUTOR_PROXY_URL_ENV, "").strip()
    if proxy_url:
        return execute_runtime_apply_package_via_proxy(package, target, data, proxy_url=proxy_url)
    executor = load_runtime_package_executor(target["executor_surface"])
    with tempfile.NamedTemporaryFile("w", suffix="-runtime-apply-package.json", encoding="utf-8", delete=True) as handle:
        json.dump(package, handle)
        handle.flush()
        return executor.run(
            package_path=Path(handle.name),
            upstream_url=target["upstream_url"],
            gateway_name=target.get("gateway_name"),
            server_name=target.get("virtual_server_name"),
            apply=True,
            base_url=runtime_executor_base_url(data),
            env_file=runtime_executor_env_file(data),
            wait_attempts=int(data.get("wait_attempts") or data.get("waitAttempts") or 12),
        )


def execute_runtime_apply_package_via_proxy(
    package: Mapping[str, Any],
    target: Mapping[str, str],
    data: Mapping[str, Any],
    *,
    proxy_url: str,
) -> dict[str, Any]:
    token = os.environ.get(RUNTIME_EXECUTOR_PROXY_TOKEN_ENV, "").strip()
    if not token:
        raise RuntimeError("runtime/apply host proxy is configured without a proxy token")
    body = {
        "package": package,
        "target": dict(target),
        "apply": True,
        "base_url": os.environ.get(RUNTIME_EXECUTOR_PROXY_BASE_URL_ENV, "http://127.0.0.1:4445"),
        "env_file": os.environ.get(
            RUNTIME_EXECUTOR_PROXY_ENV_FILE_ENV,
            str(REPO_ROOT / "docker" / "contextforge-harness" / "env" / "contextforge.env"),
        ),
        "wait_attempts": int(data.get("wait_attempts") or data.get("waitAttempts") or 12),
    }
    request = urllib.request.Request(
        proxy_url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=240) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise RuntimeError(f"runtime/apply host proxy failed: HTTP {exc.code} {exc.reason}: {detail}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("runtime/apply host proxy returned non-object JSON")
    if payload.get("ok") is False and isinstance(payload.get("failure_report"), Mapping):
        class ProxyRuntimeApplyError(RuntimeError):
            pass

        error = ProxyRuntimeApplyError(str(payload.get("error") or "runtime/apply host proxy failed"))
        error.failure_report = dict(payload["failure_report"])  # type: ignore[attr-defined]
        raise error
    return payload


def dev_runtime_target_for_package(package: Mapping[str, Any], data: Mapping[str, Any]) -> dict[str, str]:
    descriptor = {}
    registration = package.get("contextforge_registration_plan")
    if isinstance(registration, Mapping) and isinstance(registration.get("candidate_descriptor"), Mapping):
        descriptor = dict(registration["candidate_descriptor"])
    backend = descriptor.get("backend") if isinstance(descriptor.get("backend"), Mapping) else {}
    service_binding = canonical_binding(
        package.get("service_provision_plan", {}).get("service_binding")
        or data.get("service_binding")
        or data.get("serviceBinding")
        or ""
    )
    source_path = str(data.get("source_path") or data.get("sourcePath") or descriptor.get("source_lead") or "")
    candidate_values = [
        data.get("candidate_service"),
        data.get("candidateService"),
        descriptor.get("candidate_service"),
        descriptor.get("canonical_service"),
        descriptor.get("service_family"),
        data.get("backend_package"),
        data.get("backendPackage"),
        backend.get("package"),
    ]
    candidate_aliases = {package_alias(value) for value in candidate_values if value}
    for instance in iter_service_instances():
        instance_binding = canonical_binding(instance.get("service_binding"))
        identity_matches = bool(service_binding and instance_binding == service_binding)
        if not identity_matches and candidate_aliases:
            identity_matches = bool(candidate_aliases & instance_identity_aliases(instance))
        if not identity_matches or not source_path:
            continue
        instance_source = str(instance.get("source") or "").rstrip("/")
        if instance_source and instance_source != source_path.rstrip("/"):
            raise RuntimeError(
                "no approved development runtime executor target is recorded for this service; "
                "source identity conflicts with an existing service instance"
            )
    if (
        service_binding
        and str(backend.get("package_registry_type") or "").lower() == "npm"
        and str(backend.get("transport") or "").lower() == "stdio"
    ):
        canonical = registration.get("canonical_names") if isinstance(registration, Mapping) else {}
        endpoint = npm_stdio_endpoint(service_binding, project_root=package.get("project_root") if isinstance(package.get("project_root"), str) else None)
        service = service_binding.split(":", 1)[0]
        return {
            "upstream_url": str(endpoint["streamable_http_url"]),
            "gateway_name": str(canonical.get("gateway") if isinstance(canonical, Mapping) else "") or f"{service.replace(':', '-')}-gateway",
            "virtual_server_name": str(canonical.get("virtual_server") if isinstance(canonical, Mapping) else "") or f"{service.replace(':', '-')}-server",
            "executor_surface": "docker/contextforge-harness/scripts/apply_onboarding_runtime_package.py",
        }
    candidate = str(
        data.get("candidate_service")
        or data.get("candidateService")
        or descriptor.get("candidate_service")
        or descriptor.get("canonical_service")
        or ""
    )
    for instance in iter_service_instances():
        if not runtime_instance_matches(instance, service_binding=service_binding, source_path=source_path, candidate=candidate):
            continue
        foil = instance.get("development_foil")
        target = foil.get("contextforge_dev_runtime") if isinstance(foil, Mapping) else None
        if not isinstance(target, Mapping):
            continue
        upstream_url = str(target.get("upstream_url") or "")
        if not upstream_url:
            continue
        return {
            "upstream_url": upstream_url,
            "gateway_name": str(target.get("gateway_name") or ""),
            "virtual_server_name": str(target.get("virtual_server_name") or ""),
            "executor_surface": str(target.get("executor_surface") or "docker/contextforge-harness/scripts/apply_onboarding_runtime_package.py"),
        }
    raise RuntimeError(
        "no approved development runtime executor target is recorded for this service; "
        "runtime/apply cannot proceed through ContextForge yet"
    )


def require_runtime_executor_surface_approval(
    approval_text: str,
    target: Mapping[str, str],
    *,
    service_binding: str = "",
    runtime_apply_package_id: str = "",
) -> None:
    text = approval_text.strip().lower()
    exact_phrase = runtime_apply_approval_phrase(
        service_binding=service_binding or "the named service",
        runtime_target=target,
        runtime_apply_package_id=runtime_apply_package_id,
    )
    if not text:
        raise PermissionError(
            "latest user message does not approve the recorded runtime executor surface; "
            "ask the user to approve or decline the named executor surface before runtime execution. "
            f"Exact approval phrase: {exact_phrase}"
        )
    terms = {
        str(target.get("gateway_name") or "").strip().lower(),
        str(target.get("virtual_server_name") or "").strip().lower(),
        str(target.get("executor_surface") or "").strip().lower(),
    }
    surface = str(target.get("executor_surface") or "").lower()
    upstream = str(target.get("upstream_url") or "").lower()
    if "docker" in surface or "docker" in upstream:
        terms.update({"docker", "dev docker", "development surface"})
    terms = {term for term in terms if len(term) >= 3}
    if terms and not any(term in text for term in terms):
        raise PermissionError(
            "latest user message approves runtime/apply in general but does not approve the recorded runtime executor surface; "
            "ask the user to approve or decline the named executor surface before runtime execution. "
            f"Exact approval phrase: {exact_phrase}"
        )


def runtime_apply_approval_phrase(
    *,
    service_binding: str,
    runtime_target: Mapping[str, str] | None,
    runtime_apply_package_id: str,
) -> str:
    executor_surface = str((runtime_target or {}).get("executor_surface") or "").strip()
    if not executor_surface:
        executor_surface = "the recorded ContextForge runtime/apply executor surface"
    package_id = runtime_apply_package_id or "the recorded runtime/apply package id"
    return (
        f"Approve runtime/apply for {service_binding} using executor surface "
        f"{executor_surface} and runtime_apply_package_id {package_id}."
    )


def runtime_instance_matches(instance: Mapping[str, Any], *, service_binding: str, source_path: str, candidate: str) -> bool:
    matched = False
    if service_binding:
        if canonical_binding(instance.get("service_binding")) != service_binding:
            return False
        matched = True
    if source_path:
        if str(instance.get("source") or "").rstrip("/") != source_path.rstrip("/"):
            return False
        matched = True
    if candidate:
        if package_alias(candidate) not in instance_identity_aliases(instance):
            return False
        matched = True
    return matched


def load_runtime_package_executor(surface: str):
    path = Path(surface)
    if not path.is_absolute():
        path = REPO_ROOT / path
    spec = importlib.util.spec_from_file_location("contextforge_onboarding_runtime_executor", path)
    if not spec or not spec.loader:
        raise RuntimeError(f"unable to load runtime executor surface at {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    if not hasattr(module, "run"):
        raise RuntimeError(f"runtime executor surface at {path} has no run function")
    return module


def runtime_execute_visible_response(candidate: str, result: Mapping[str, Any]) -> str:
    mutation_performed = bool(result.get("mutation_performed"))
    if not mutation_performed:
        failure_report = result.get("failure_report") if isinstance(result.get("failure_report"), Mapping) else {}
        failed_stage = str(failure_report.get("failed_stage") or result.get("failed_stage") or "runtime_apply")
        sanitized_error = str(failure_report.get("sanitized_error") or result.get("sanitized_error") or "").strip()
        rollback_result = str(failure_report.get("rollback_result") or result.get("rollback_result") or "unknown")
        residual_cleanup_risk = str(failure_report.get("residual_cleanup_risk") or result.get("residual_cleanup_risk") or "").strip()
        lines = [
            f"`{candidate}` was not applied to the ContextForge development surface.",
            "Runtime/apply did not complete; no service was installed, registered, exposed, or made available to this client by this step.",
            f"Failed stage: `{failed_stage}`.",
        ]
        if sanitized_error:
            lines.append(f"Observed error: {sanitized_error}")
        lines.append(f"Rollback result: `{rollback_result}`.")
        if residual_cleanup_risk:
            lines.append(f"Residual cleanup risk: {residual_cleanup_risk}")
        lines.extend(
            [
                "Do not ask the user to reload for this service yet, and do not claim target-client-visible tools are available.",
                "Research the required correction from source evidence and submit a complete corrected runtime package before trying again.",
            ]
        )
        return "\n".join(lines)
    binding = result.get("package", {}).get("service_binding") if isinstance(result.get("package"), Mapping) else ""
    gateway = result.get("gateway") if isinstance(result.get("gateway"), Mapping) else {}
    server = result.get("server") if isinstance(result.get("server"), Mapping) else {}
    tools = [str(tool) for tool in result.get("tool_names", []) if isinstance(tool, str)]
    lines = [
        f"`{candidate}` has been applied to the ContextForge development surface.",
    ]
    if binding:
        lines.append(f"Service binding: `{binding}`.")
    if gateway.get("name"):
        lines.append(f"Gateway: `{gateway.get('name')}` ({gateway.get('action', 'ready')}).")
    if server.get("name"):
        lines.append(f"Virtual server: `{server.get('name')}` ({server.get('action', 'ready')}).")
    if tools:
        lines.append("Tools registered: " + ", ".join(f"`{tool}`" for tool in tools) + ".")
    lines.extend(
        [
            "This step may have installed packages and started or restarted hosted service processes inside the shared npm-stdio host; do not say no runtime process was started unless the executor result explicitly proves that.",
            "No client-local MCP config, project activation state, systemd unit, new Docker service, or secret value was written by this step.",
            "Target-client usability is not proven yet. Start a new Pi/OpenCode session from this project root, confirm the tools are visible there, then use a safe service call before claiming the service is usable.",
        ]
    )
    return "\n".join(lines)


def service_onboarding_visible_response(record: Mapping[str, Any]) -> str:
    candidate = record.get("candidate_service") or "the candidate service"
    status = record.get("status") or "unknown"
    blockers = record.get("blockers")
    if status == "needs_user_input" or (isinstance(blockers, list) and blockers):
        questions = _string_items(record.get("next_questions", []))
        lines = [
            f"I can help onboard `{candidate}` as an uncataloged MCP service, and this will stay source-only until a later explicit runtime approval.",
            "Please provide the source reference or local path, transport type, credential boundary, project or user scope, expected tools, lifecycle/cleanup expectations, and proof plan.",
            "No service has been installed, registered, started, exposed, imported, validated, probed, or made available to this client.",
        ]
        if questions:
            lines.append("Next questions: " + " ".join(questions[:4]))
        return "\n".join(lines)
    known = compact_known_classifications(record)
    questions = _string_items(record.get("next_questions", []))
    gate = record.get("pre_runtime_workflow_gate")
    missing = _string_items(gate.get("missing_dimensions", []) if isinstance(gate, Mapping) else [])
    lines = [
        f"I have a source-only onboarding plan for `{candidate}`.",
        f"Status: `{status}`.",
        "Credentials: no secret values were requested, stored, or validated; credential handling remains source-evidence only.",
    ]
    if known:
        lines.append("Known classifications: " + ", ".join(known) + ".")
    if missing:
        lines.append("Still needed before runtime work: " + ", ".join(missing) + ".")
    if questions:
        lines.append("Next questions: " + " ".join(questions[:4]))
    lines.extend(
        [
            "No service has been installed, registered, started, exposed, imported, or made available to this client.",
            "A later runtime phase would need explicit approval plus source evidence, transport proof, lifecycle/cleanup boundaries, and a bounded proof plan.",
        ]
    )
    return "\n".join(lines)


def service_management_visible_response(result: Mapping[str, Any], candidate: str) -> str:
    status = str(result.get("status") or "unknown")
    plan = result.get("x_catalog_plan") if isinstance(result.get("x_catalog_plan"), Mapping) else {}
    plan_id = str(plan.get("plan_id") or result.get("result_id") or "unavailable")
    required = _string_items(plan.get("required_approval_classes", []) if isinstance(plan, Mapping) else [])
    lines = [
        f"I prepared the service-management continuation package for `{candidate}`.",
        f"Status: `{status}`.",
        f"Plan id: `{plan_id}`.",
        "This is not a project-init service activation menu, and no cataloged-service selection was made.",
    ]
    if required:
        lines.append("A separate explicit approval is required before any ContextForge registry or catalog mutation.")
    lines.extend(
        [
            "No service has been installed, registered, started, exposed, imported, or made available to this client.",
            "The next safe step, if you want to continue, is a non-mutating runtime package preview for review. That preview still does not install or register anything.",
            "Actual runtime execution remains a later approval step after reviewing the recorded package and executor surface.",
            "Do not use project-init activation or the existing service menu for this uncataloged service.",
        ]
    )
    return "\n".join(lines)


def runtime_apply_visible_response(
    *,
    candidate: str,
    service_binding: str,
    management_result: Mapping[str, Any],
    provision_plan: Mapping[str, Any],
    install_artifact_contract: Mapping[str, Any] | None = None,
    runtime_target: Mapping[str, str] | None = None,
    runtime_target_error: str = "",
    runtime_apply_package_id: str = "",
) -> str:
    plan = management_result.get("x_catalog_plan") if isinstance(management_result.get("x_catalog_plan"), Mapping) else {}
    catalog_plan_id = str(plan.get("plan_id") or management_result.get("result_id") or "unavailable")
    provision_plan_id = str(provision_plan.get("provision_plan_id") or "unavailable")
    backend_home = str(provision_plan.get("x_backend_home") or "unavailable")
    lines = [
        f"I prepared the runtime-apply package for `{candidate}`.",
        f"Service binding: `{service_binding}`.",
        f"Catalog plan id: `{catalog_plan_id}`.",
        f"Provision plan id: `{provision_plan_id}`.",
        f"Backend home target: `{backend_home}`.",
        f"Runtime/apply package id: `{runtime_apply_package_id or 'unavailable'}`.",
        "Expected implementation artifacts: a managed npm-stdio service record for the shared Docker host and a `contextforge-service.json` API definition for gateway refresh and virtual-server registration.",
        "Use `install_artifact_contract.runtime_apply_payload_contract` for the exact accepted runtime/apply payload shape; `tool_schemas` must be an object mapping tool names to structured schema objects, not an array of strings or summaries.",
        "No runtime, registry, client config, or project activation mutation has been performed by this helper call.",
    ]
    if install_artifact_contract:
        artifacts = install_artifact_contract.get("artifacts") if isinstance(install_artifact_contract.get("artifacts"), Mapping) else {}
        npm_record = artifacts.get("npm_stdio_service_record") if isinstance(artifacts.get("npm_stdio_service_record"), Mapping) else {}
        api_json = artifacts.get("contextforge_api_json") if isinstance(artifacts.get("contextforge_api_json"), Mapping) else {}
        if npm_record.get("path"):
            lines.append(f"Managed npm-stdio service record target: `{npm_record.get('path')}`.")
        if api_json.get("path"):
            lines.append(f"ContextForge API JSON target: `{api_json.get('path')}`.")
    if runtime_target:
        if runtime_target.get("executor_surface"):
            lines.append(f"Recorded executor surface: `{runtime_target.get('executor_surface')}`.")
        if runtime_target.get("gateway_name"):
            lines.append(f"Recorded ContextForge gateway: `{runtime_target.get('gateway_name')}`.")
        if runtime_target.get("virtual_server_name"):
            lines.append(f"Recorded virtual server: `{runtime_target.get('virtual_server_name')}`.")
        if runtime_target.get("upstream_url"):
            lines.append(f"Recorded upstream URL: `{runtime_target.get('upstream_url')}`.")
        lines.append(
            "Exact approval phrase to proceed: "
            f"`{runtime_apply_approval_phrase(service_binding=service_binding, runtime_target=runtime_target, runtime_apply_package_id=runtime_apply_package_id)}`"
        )
        lines.append(
            "The next executor still needs explicit approval for this exact recorded apply surface. After that approval, call the runtime executor with this runtime/apply package id, then prove backend readiness, ContextForge registration, a reload or new-session boundary, target-client-visible list-tools, and a safe service call."
        )
    else:
        lines.append(
            "No recorded runtime executor target is available yet; runtime execution must stop until an approved apply surface is recorded."
        )
        if runtime_target_error:
            lines.append(f"Runtime target blocker: {runtime_target_error}")
    lines.append("Do not write direct client-local MCP configuration as a substitute for this ContextForge apply path.")
    return "\n".join(lines)


def known_runtime_instance_for_descriptor(data: Mapping[str, Any], descriptor: Mapping[str, Any]) -> dict[str, Any] | None:
    service_binding = canonical_binding(data.get("service_binding") or data.get("serviceBinding"))
    source_path = str(data.get("source_path") or data.get("sourcePath") or descriptor.get("source_lead") or "")
    candidate_values = [
        data.get("candidate_service"),
        data.get("candidateService"),
        descriptor.get("candidate_service"),
        descriptor.get("canonical_service"),
        descriptor.get("service_family"),
        data.get("backend_package"),
        data.get("backendPackage"),
        data.get("package"),
        data.get("packageName"),
    ]
    candidate_aliases = {package_alias(value) for value in candidate_values if value}
    for instance in iter_service_instances():
        if service_binding and canonical_binding(instance.get("service_binding")) != service_binding:
            continue
        if source_path and str(instance.get("source") or "").rstrip("/") != source_path.rstrip("/"):
            continue
        if candidate_aliases and not (candidate_aliases & instance_identity_aliases(instance)):
            continue
        if service_binding or source_path or candidate_aliases:
            return instance
    return None


def service_binding_for_descriptor(data: Mapping[str, Any], descriptor: Mapping[str, Any]) -> str:
    explicit = canonical_binding(data.get("service_binding") or data.get("serviceBinding"))
    if explicit:
        return explicit
    target = known_runtime_instance_for_descriptor(data, descriptor)
    if target and canonical_binding(target.get("service_binding")):
        return canonical_binding(target.get("service_binding"))
    invalid_explicit = data.get("service_binding") or data.get("serviceBinding")
    if invalid_explicit:
        raise ValueError(
            "service_binding must be a ContextForge binding such as `time:canonical`; "
            "put executable commands in backend_command and backend_args, not service_binding. "
            "Do not write direct client-local MCP configuration as a workaround."
        )
    name = (
        descriptor.get("canonical_service")
        or descriptor.get("service_family")
        or descriptor.get("candidate_service")
        or data.get("candidate_service")
        or data.get("candidateService")
        or "uncataloged"
    )
    base = re.sub(r"[^a-z0-9_.-]+", "-", str(name).lower()).strip(".-") or "uncataloged"
    localization = (
        data.get("localization_type")
        or data.get("localizationType")
        or descriptor.get("classification", {}).get("localization_type")
    )
    suffix_by_localization = {
        "project_scoped": "project",
        "credential_scoped": "credential_scoped",
        "client_local_session_scoped": "session_scoped",
    }
    return f"{base}:{suffix_by_localization.get(str(localization), 'canonical')}"


def backend_command_for_descriptor(data: Mapping[str, Any], descriptor: Mapping[str, Any]) -> list[str]:
    command_value = data.get("backend_command") or data.get("backendCommand") or data.get("command")
    args_value = data.get("backend_args") or data.get("backendArgs") or data.get("args")
    backend = descriptor.get("backend") if isinstance(descriptor.get("backend"), Mapping) else {}
    if not command_value:
        command_value = backend.get("command") or backend.get("package") or descriptor.get("candidate_service") or "uncataloged-mcp"
    if command_value and not args_value:
        split = shlex.split(str(command_value))
        if len(split) > 1:
            command = split
        else:
            command = [str(command_value)]
    else:
        command = [str(command_value)]
    if isinstance(args_value, Sequence) and not isinstance(args_value, (str, bytes, bytearray)):
        command.extend(str(item) for item in args_value if isinstance(item, str) and item)
    return command


def ports_for_descriptor(data: Mapping[str, Any], descriptor: Mapping[str, Any]) -> list[dict[str, Any]]:
    ports = data.get("ports")
    if isinstance(ports, Sequence) and not isinstance(ports, (str, bytes, bytearray)):
        return [dict(item) for item in ports if isinstance(item, Mapping)]
    bridge = descriptor.get("bridge") if isinstance(descriptor.get("bridge"), Mapping) else {}
    port = bridge.get("port") or data.get("port")
    if isinstance(port, int):
        binding = service_binding_for_descriptor(data, descriptor)
        return [{"port": port, "bind": str(bridge.get("host") or "127.0.0.1"), "owner": binding}]
    return []


def readiness_probes_for_descriptor(data: Mapping[str, Any], descriptor: Mapping[str, Any]) -> list[dict[str, Any]]:
    probes = data.get("readiness_probes") or data.get("readinessProbes")
    if isinstance(probes, Sequence) and not isinstance(probes, (str, bytes, bytearray)):
        return [dict(item) for item in probes if isinstance(item, Mapping)]
    return []


def env_keys_for_descriptor(data: Mapping[str, Any], descriptor: Mapping[str, Any], *, key: str) -> list[str]:
    value = data.get(key) or data.get(key.replace("_", ""))
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [str(item) for item in value if isinstance(item, str) and item.strip()]
    backend = descriptor.get("backend") if isinstance(descriptor.get("backend"), Mapping) else {}
    env_vars = backend.get("env_vars")
    if key == "optional_env" and isinstance(env_vars, Sequence) and not isinstance(env_vars, (str, bytes, bytearray)):
        return [str(item) for item in env_vars if isinstance(item, str) and item.strip()]
    return []


def artifact_ref(name: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "ref": f"contextforge://control-plane/{name}",
        "content_digest": service_management.stable_digest(payload),
        "catalog_revision_or_etag": None,
        "resolved_at": service_management.now_timestamp(),
    }


def compact_known_classifications(record: Mapping[str, Any]) -> list[str]:
    items: list[str] = []
    classification = record.get("classification")
    if not isinstance(classification, Mapping):
        return items
    labels = {
        "plan_type": "plan",
        "localization_type": "scope",
        "functional_type": "function",
        "transport_type": "transport",
        "state_type": "state footprint",
        "approval_type": "approval boundary",
    }
    values = {
        "source_only_scaffolding": "source-only planning",
        "project_scoped": "project-scoped",
        "shared_canonical": "shared canonical",
        "credential_scoped": "credential-scoped",
        "search_retrieval": "search/retrieval",
        "time_timezone": "time/timezone",
        "stdio": "stdio",
        "sse": "SSE",
        "streamable_http": "streamable HTTP",
        "project_metadata": "project metadata",
        "stateless": "stateless",
        "local_filesystem_state": "local filesystem state",
        "source_only": "source-only",
    }
    for key, value in classification.items():
        if isinstance(value, Mapping) and value.get("status") == "known" and value.get("value"):
            label = labels.get(str(key), str(key).replace("_", " "))
            display = values.get(str(value["value"]), str(value["value"]).replace("_", " "))
            items.append(f"{label}: {display}")
    return items


def synthetic_source_summary(value: str) -> bool:
    lowered = value.strip().lower()
    return (
        lowered.startswith("user-supplied:")
        or lowered.startswith("description:")
        or lowered.startswith("summary:")
    )


def lead_type(value: str) -> str:
    lowered = value.strip().lower()
    if lowered.startswith(("http://", "https://")):
        if "github.com/" in lowered:
            return "github_url"
        return "url"
    if lowered.startswith(("/", "./", "../")):
        return "local_path"
    if lowered.startswith("#") or re.fullmatch(r"[A-Za-z0-9_.-]+#[0-9]+", lowered):
        return "issue"
    return "lead"


def _string_items(value: Sequence[Any] | Any) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [str(item) for item in value if isinstance(item, str) and item.strip()]
