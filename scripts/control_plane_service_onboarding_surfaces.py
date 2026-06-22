"""Shared user-facing surfaces for service onboarding helper adapters."""

from __future__ import annotations

import importlib.util
import json
import re
import os
import tempfile
import urllib.error
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
RUNTIME_EXECUTOR_BASE_URL_ENV = "CONTEXTFORGE_RUNTIME_EXECUTOR_BASE_URL"
RUNTIME_EXECUTOR_ENV_FILE_ENV = "CONTEXTFORGE_RUNTIME_EXECUTOR_ENV_FILE"
RUNTIME_EXECUTOR_DEFAULT_BASE_URL = "http://host.docker.internal:4445" if Path("/repo").exists() else "http://127.0.0.1:4445"
RUNTIME_EXECUTOR_DEFAULT_ENV_FILE = Path(
    os.environ.get(RUNTIME_EXECUTOR_ENV_FILE_ENV, REPO_ROOT / "docker" / "contextforge-harness" / "env" / "contextforge.env")
)


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
    handoff = service_handoffs.build_catalog_candidate_handoff(
        descriptor,
        project_root=project_root,
        source="project_init",
        reason="approved_uncataloged_onboarding_runtime_apply_package",
    )
    management_result = service_management.plan_service_management_from_handoff(handoff)
    catalog_plan = management_result.get("x_catalog_plan") if isinstance(management_result.get("x_catalog_plan"), Mapping) else {}
    service_binding = service_binding_for_descriptor(data, descriptor)
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
    candidate = (
        descriptor.get("candidate_service")
        or descriptor.get("canonical_service")
        or descriptor.get("service_family")
        or service_binding
    )
    visible = runtime_apply_visible_response(
        candidate=str(candidate),
        service_binding=service_binding,
        management_result=management_result,
        provision_plan=provision_plan,
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
        "runtime_apply_boundary": {
            "runtime_executor_approval_required": True,
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


def apply_service_onboarding_runtime_package(project_root: str, data: Mapping[str, Any]) -> dict[str, Any]:
    package = build_service_onboarding_runtime_apply_package(project_root, data)
    target = dev_runtime_target_for_package(package, data)
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
    service_binding = str(
        data.get("service_binding")
        or data.get("serviceBinding")
        or package.get("service_provision_plan", {}).get("service_binding")
        or ""
    )
    source_path = str(data.get("source_path") or data.get("sourcePath") or descriptor.get("source_lead") or "")
    candidate = str(
        data.get("candidate_service")
        or data.get("candidateService")
        or descriptor.get("candidate_service")
        or descriptor.get("canonical_service")
        or ""
    ).lower()
    for instance_path in sorted((REPO_ROOT / "server-instances").glob("*/instance.json")):
        try:
            instance = json.loads(instance_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
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


def runtime_instance_matches(instance: Mapping[str, Any], *, service_binding: str, source_path: str, candidate: str) -> bool:
    matched = False
    if service_binding:
        if str(instance.get("service_binding") or "") != service_binding:
            return False
        matched = True
    if source_path:
        if str(instance.get("source") or "").rstrip("/") != source_path.rstrip("/"):
            return False
        matched = True
    names = {
        str(instance.get("name") or "").lower(),
        str(instance.get("slug") or "").lower(),
        str(instance.get("service") or "").lower(),
    }
    if candidate:
        if candidate not in names:
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
        "No runtime, registry, client config, or project activation mutation has been performed by this helper call.",
        "The next executor still needs explicit approval for the exact apply surface, must use the approved ContextForge development surface, then prove backend readiness, ContextForge registration, a reload or new-session boundary, target-client-visible list-tools, and a safe service call.",
        "Do not write direct client-local MCP configuration as a substitute for this ContextForge apply path.",
    ]
    return "\n".join(lines)


def service_binding_for_descriptor(data: Mapping[str, Any], descriptor: Mapping[str, Any]) -> str:
    explicit = data.get("service_binding") or data.get("serviceBinding")
    if explicit:
        return str(explicit)
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
