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
RUNTIME_EXECUTOR_DEFAULT_BASE_URL = "http://host.docker.internal:4445" if Path("/repo").exists() else "http://127.0.0.1:4445"
RUNTIME_EXECUTOR_DEFAULT_ENV_FILE = Path(
    os.environ.get(RUNTIME_EXECUTOR_ENV_FILE_ENV, REPO_ROOT / "docker" / "contextforge-harness" / "env" / "contextforge.env")
)
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
    return "\n".join(lines)


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
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            return [item for item in value]
    return []


def _mapping_field(data: Mapping[str, Any], *keys: str) -> dict[str, Any]:
    for key in keys:
        value = data.get(key)
        if isinstance(value, Mapping):
            return dict(value)
    return {}


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
    tool_schemas = _mapping_field(data, "tool_schemas", "toolSchemas")
    if tool_schemas:
        descriptor["tool_schemas"] = tool_schemas
    prompt_library = _mapping_field(data, "prompt_library", "promptLibrary")
    if prompt_library:
        descriptor["prompt_library"] = prompt_library
    if command:
        backend["command"] = str(command)
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
    if not isinstance(descriptor.get("tool_schemas"), Mapping) or not descriptor.get("tool_schemas"):
        gaps.append({"field": "tool_schemas", "reason": "tool schemas must be understood and supplied before prompt publication"})
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
    lines.extend(
        [
            "After those facts are supplied, ask me to build the runtime/apply package again.",
            "No runtime, registry, Docker, prompt-library, client config, or project activation mutation has been performed.",
        ]
    )
    return "\n".join(lines)


def build_service_onboarding_plan(project_root: str, data: Mapping[str, Any]) -> dict[str, Any]:
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
    visible = runtime_apply_visible_response(
        candidate=str(candidate),
        service_binding=service_binding,
        management_result=management_result,
        provision_plan=provision_plan,
        install_artifact_contract=install_contract,
        runtime_target=runtime_target,
        runtime_target_error=runtime_target_error,
    )
    return {
        "status": "service_onboarding_runtime_apply_package",
        "project_root": project_root,
        "mutation_allowed": False,
        "assistant_visible_response": visible,
        "message": visible,
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
    package_arguments = [
        str(item)
        for item in backend.get("package_arguments", [])
        if isinstance(item, str) and item.strip()
    ]
    required_secret_names = [
        str(item)
        for item in descriptor.get("required_secret_names", [])
        if str(item).strip()
    ]
    environment_variables = []
    environment_values: dict[str, str] = {}
    for item in backend.get("environment_variables", []):
        if isinstance(item, Mapping):
            name = str(item.get("name") or item.get("key") or "").strip()
            if not name:
                continue
            secret = bool(item.get("secret") or item.get("is_secret") or item.get("isSecret") or name in required_secret_names)
            entry: dict[str, Any] = {"name": name, "secret": secret}
            if item.get("description"):
                entry["description"] = str(item["description"])
            value = item.get("value")
            if not secret and value is not None:
                entry["value"] = str(value)
                environment_values[name] = str(value)
            environment_variables.append(entry)
        else:
            name = str(item).strip()
            if name:
                environment_variables.append({"name": name, "secret": name in required_secret_names})
    endpoint = npm_stdio_endpoint(service_binding, project_root=project_root)
    return {
        "schema_uri": "contextforge://control-plane/service-onboarding-install-artifact-contract/v1",
        "service_binding": service_binding,
        "purpose": "managed npm-stdio host service record plus ContextForge API JSON for reviewed service installation",
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
                    "non-secret environment placeholders only",
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
    package = build_service_onboarding_runtime_apply_package(project_root, data)
    target = dev_runtime_target_for_package(package, data)
    if data.get("require_executor_surface_approval"):
        require_runtime_executor_surface_approval(str(data.get("approval_text") or ""), target)
    executor = load_runtime_package_executor(target["executor_surface"])
    with tempfile.NamedTemporaryFile("w", suffix="-runtime-apply-package.json", encoding="utf-8", delete=True) as handle:
        json.dump(package, handle)
        handle.flush()
        result = executor.run(
            package_path=Path(handle.name),
            upstream_url=target["upstream_url"],
            gateway_name=target.get("gateway_name"),
            server_name=target.get("virtual_server_name"),
            apply=True,
            base_url=str(data.get("contextforge_base_url") or data.get("contextforgeBaseUrl") or os.environ.get(RUNTIME_EXECUTOR_BASE_URL_ENV, RUNTIME_EXECUTOR_DEFAULT_BASE_URL)),
            env_file=Path(str(data.get("contextforge_env_file") or data.get("contextforgeEnvFile") or RUNTIME_EXECUTOR_DEFAULT_ENV_FILE)),
            wait_attempts=int(data.get("wait_attempts") or data.get("waitAttempts") or 12),
        )
    candidate = (
        package.get("contextforge_registration_plan", {})
        .get("candidate_descriptor", {})
        .get("candidate_service")
        or package.get("service_provision_plan", {}).get("service_binding")
        or "the candidate service"
    )
    visible = runtime_execute_visible_response(str(candidate), result)
    return {
        "status": "service_onboarding_runtime_applied",
        "project_root": project_root,
        "mutation_allowed": True,
        "mutation_performed": bool(result.get("mutation_performed")),
        "assistant_visible_response": visible,
        "message": visible,
        "executor_result": result,
        "runtime_target": {
            "gateway_name": target.get("gateway_name"),
            "virtual_server_name": target.get("virtual_server_name"),
            "upstream_url_recorded": bool(target.get("upstream_url")),
            "executor_surface": target.get("executor_surface"),
        },
        "non_actions": result.get("non_actions") or [],
    }


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


def require_runtime_executor_surface_approval(approval_text: str, target: Mapping[str, str]) -> None:
    text = approval_text.strip().lower()
    if not text:
        raise PermissionError(
            "latest user message does not approve the recorded runtime executor surface; "
            "ask the user to approve or decline the named executor surface before runtime execution"
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
            "ask the user to approve or decline the named executor surface before runtime execution"
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
            "No client-local MCP config, project activation state, systemd unit, Docker service, or secret value was written by this step.",
            "Start a new Pi/OpenCode session from this project root so the newly registered ContextForge tools can be discovered, then use a safe service call to confirm behavior.",
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
        lines.append("Required approval before mutation: " + ", ".join(required) + ".")
    lines.extend(
        [
            "No service has been installed, registered, started, exposed, imported, or made available to this client.",
            "This surface stops before catalog promotion or runtime apply. A separate service-management apply surface is required before any ContextForge registry, runtime, or client-visible mutation.",
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
        "Expected implementation artifacts: a managed npm-stdio service record for the shared Docker host and a `contextforge-service.json` API definition for gateway refresh and virtual-server registration.",
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
            "The next executor still needs explicit approval for this exact recorded apply surface, then must prove backend readiness, ContextForge registration, a reload or new-session boundary, target-client-visible list-tools, and a safe service call."
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
