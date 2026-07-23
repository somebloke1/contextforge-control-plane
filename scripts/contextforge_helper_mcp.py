#!/usr/bin/env python3
"""MCP wrapper for ContextForge helper project-init workflow tools."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import ssl
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Mapping, Sequence

from mcp.server.fastmcp import FastMCP

import control_plane_project_init_helper as helper
import control_plane_project_state as project_state
import control_plane_service_onboarding_surfaces as service_onboarding_surfaces
import project_init_common as common


server = FastMCP("contextforge-helper")

_CACHED_PLANS: dict[str, dict[str, Any]] = {}
_CACHED_RECEIPTS: dict[str, list[dict[str, Any]]] = {}
_CACHED_RECOVERY_PLANS: dict[str, dict[str, Any]] = {}
_CACHED_RECOVERY_RECEIPTS: dict[str, list[dict[str, Any]]] = {}
_CONTEXTFORGE_READBACK_CACHE: dict[str, tuple[float, dict[str, list[dict[str, Any]]]]] = {}
DEFAULT_CLIENT_TYPE = os.environ.get("CONTEXTFORGE_HELPER_DEFAULT_CLIENT_TYPE", "codex").strip() or "codex"
class ContextForgeCatalogUnavailable(RuntimeError):
    """Raised when the helper cannot read ContextForge registry/catalog truth."""

    def __init__(self, base_url: str, reason: str):
        self.base_url = base_url.rstrip("/") if base_url else "unknown"
        self.reason = reason
        super().__init__(f"ContextForge catalog unavailable at {self.base_url}: {reason}")


def _cache_dir() -> Path:
    root = Path(os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir())
    return root / "contextforge-helper" / "project-init-cache"


def _cache_path(project_root: str) -> Path:
    digest = hashlib.sha256(_cache_key(project_root).encode("utf-8")).hexdigest()[:32]
    return _cache_dir() / f"{digest}.json"


def _read_durable_cache(project_root: str) -> dict[str, Any]:
    path = _cache_path(project_root)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict) or data.get("project_root") != _cache_key(project_root):
        return {}
    return data


def _write_durable_cache(project_root: str, data: dict[str, Any]) -> None:
    path = _cache_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"project_root": _cache_key(project_root), **data}
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(temp_path, 0o600)
    temp_path.replace(path)


def _clear_durable_cache(project_root: str) -> None:
    try:
        _cache_path(project_root).unlink()
    except FileNotFoundError:
        pass


def _error(exc: Exception) -> dict[str, Any]:
    return {
        "ok": False,
        "error": {
            "type": exc.__class__.__name__,
            "message": str(exc),
        },
    }


def _contextforge_target() -> tuple[Path | None, str]:
    import contextforge_mcp_wrapper as gateway

    if gateway.TARGET_CONFIGURATION_ERROR:
        raise ContextForgeCatalogUnavailable(
            gateway.GATEWAY_BASE,
            gateway.TARGET_CONFIGURATION_ERROR,
        )
    env_path = gateway.CONFIG_ENV
    return (env_path if env_path.exists() else None), gateway.GATEWAY_BASE


def _contextforge_request(base_url: str, path: str, token: str) -> Any:
    headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
    request = urllib.request.Request(f"{base_url}{path}", headers=headers, method="GET")
    kwargs: dict[str, Any] = {"timeout": 10}
    if base_url.startswith("https://"):
        cert = common.REPO_ROOT / "config" / "tls" / "contextforge-local.crt"
        kwargs["context"] = ssl.create_default_context(cafile=str(cert)) if cert.exists() else ssl.create_default_context()
    with urllib.request.urlopen(request, **kwargs) as response:
        payload = response.read()
    return json.loads(payload) if payload else None


def _api_items(data: Any, *, endpoint: str) -> list[dict[str, Any]]:
    if isinstance(data, dict):
        items = data.get("items")
        if not isinstance(items, list):
            raise TypeError(f"{endpoint} returned an object without an items array")
    elif isinstance(data, list):
        items = data
    else:
        raise TypeError(
            f"{endpoint} returned {type(data).__name__}; expected an array or an object with an items array"
        )
    if any(not isinstance(item, dict) for item in items):
        raise TypeError(f"{endpoint} items must all be objects")
    return list(items)


def _resource_tags(resource: Mapping[str, Any]) -> set[str]:
    tags = resource.get("tags")
    if not isinstance(tags, list):
        return set()
    values: set[str] = set()
    for tag in tags:
        if isinstance(tag, Mapping):
            value = tag.get("label") or tag.get("name") or tag.get("id")
        else:
            value = tag
        if value is not None and str(value):
            values.add(str(value).lower())
    return values


def _is_service_offering_resource(resource: Mapping[str, Any]) -> bool:
    return bool(_resource_tags(resource).intersection(common.SERVICE_OFFERING_TAGS))


def _resource_with_content(base_url: str, token: str, resource: dict[str, Any]) -> dict[str, Any]:
    if not _is_service_offering_resource(resource):
        return resource
    resource_id = resource.get("id")
    if not isinstance(resource_id, str) or not resource_id.strip() or resource_id != resource_id.strip():
        raise TypeError("tagged service-offering Resource list rows require a native nonblank string id")
    full = _contextforge_request(base_url, f"/resources/{resource_id}", token)
    if type(full) is not dict:
        raise TypeError(f"/resources/{resource_id} returned {type(full).__name__}; expected an object")
    detail_id = full.get("id")
    if not isinstance(detail_id, str) or not detail_id.strip() or detail_id != detail_id.strip():
        raise TypeError(f"/resources/{resource_id} returned an object without a string id")
    if detail_id != resource_id:
        raise ValueError(f"/resources/{resource_id} returned Resource id {detail_id!r}")
    selected_key = ""
    selected_content: Any = None
    for key in ("content", "text", "contents"):
        candidate = full.get(key)
        if candidate:
            selected_key = key
            selected_content = candidate
            break
    if type(selected_content) not in (str, dict):
        raise TypeError(f"/resources/{resource_id} returned an object without Resource content")
    if isinstance(selected_content, dict):
        try:
            full[selected_key] = json.loads(json.dumps(selected_content, allow_nan=False))
        except (TypeError, ValueError) as exc:
            raise TypeError(f"/resources/{resource_id} returned non-JSON Resource content") from exc
    merged = dict(resource)
    for key in ("content", "text", "contents", "uri", "name", "title", "description", "mimeType", "mime_type", "tags", "enabled"):
        if key in full:
            merged[key] = full[key]
    return merged


def _contextforge_catalog_cache_seconds() -> float:
    raw = os.environ.get("CONTEXTFORGE_HELPER_CATALOG_CACHE_SECONDS", "30").strip()
    try:
        value = float(raw)
    except ValueError:
        return 30.0
    return max(0.0, min(value, 300.0))


def _cached_readback_copy(value: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    return copy.deepcopy(value)


def _live_contextforge_registry_readback() -> dict[str, list[dict[str, Any]]]:
    env_path, base_url = _contextforge_target()
    if env_path is None:
        raise ContextForgeCatalogUnavailable(base_url, "no ContextForge client-scoped env file was found")
    cache_key = ""
    cached: tuple[float, dict[str, list[dict[str, Any]]]] | None = None
    ttl = _contextforge_catalog_cache_seconds()
    try:
        import contextforge_mcp_wrapper as gateway

        env = gateway._read_env(env_path)
        token = gateway._token(
            env.get("PLATFORM_ADMIN_EMAIL"),
            env.get("PLATFORM_ADMIN_PASSWORD"),
            bearer_token=env.get("CONTEXTFORGE_BEARER_TOKEN"),
        )
        token_digest = hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]
        cache_key = f"{base_url}|{env_path}|{token_digest}"
        now = time.monotonic()
        cached = _CONTEXTFORGE_READBACK_CACHE.get(cache_key)
        if ttl > 0 and cached is not None and now - cached[0] <= ttl:
            return _cached_readback_copy(cached[1])
        resources_path = "/resources?include_inactive=true&limit=1000"
        servers_path = "/servers?include_inactive=true&limit=1000"
        gateways_path = "/gateways?include_inactive=true&limit=1000"
        resources = _api_items(
            _contextforge_request(base_url, resources_path, token),
            endpoint=resources_path,
        )
        resources = [_resource_with_content(base_url, token, resource) for resource in resources]
        readback = {
            "servers": _api_items(
                _contextforge_request(base_url, servers_path, token),
                endpoint=servers_path,
            ),
            "gateways": _api_items(
                _contextforge_request(base_url, gateways_path, token),
                endpoint=gateways_path,
            ),
            "resources": resources,
        }
        if ttl > 0:
            _CONTEXTFORGE_READBACK_CACHE[cache_key] = (now, _cached_readback_copy(readback))
        return readback
    except urllib.error.HTTPError as exc:
        if exc.code == 429 and cached is not None and time.monotonic() - cached[0] <= max(ttl, 300.0):
            return _cached_readback_copy(cached[1])
        raise ContextForgeCatalogUnavailable(base_url, f"HTTP {exc.code} {exc.reason}") from exc
    except Exception as exc:
        raise ContextForgeCatalogUnavailable(base_url, f"{exc.__class__.__name__}: {exc}") from exc


def _contextforge_registry_service_offerings(root: Path) -> list[dict[str, Any]]:
    readback = _live_contextforge_registry_readback()
    return common.discover_contextforge_registry_service_offerings(
        project_root=root,
        contextforge_servers=readback.get("servers") or [],
        contextforge_gateways=readback.get("gateways") or [],
        contextforge_resources=readback.get("resources") or [],
    )


def _visible_item_list(items: Sequence[str], *, empty: str = "none recorded") -> list[str]:
    values = [str(item) for item in items if str(item)]
    if not values:
        return [f"- {empty}"]
    return [f"- {item}" for item in values]


def _visible_section(title: str, lines: Sequence[str]) -> str:
    return "\n".join([title, *lines])


def _visible_helper_response(title: str, sections: Sequence[str]) -> str:
    return "\n\n".join([title, *sections])


def _unwrap_tool_envelope(value: dict[str, Any]) -> dict[str, Any]:
    """Remove MCP response metadata before passing a plan back to pure helpers."""

    if value.get("ok") is True:
        return {key: item for key, item in value.items() if key != "ok"}
    return value


_CLIENT_HIDDEN_KEYS = frozenset(
    {
        "planned_state",
        "validation_plan",
        "validation_policy",
        "validation_records",
        "validation_results",
        "validation_result_shape",
        "validation_mode",
        "validation_status",
        "x_validation_mode",
        "safe_default",
        "safe_operations",
        "safe_probe_id",
        "safe_probe_result",
        "probe_contract",
        "proof_kind",
        "target_client_proof_layers",
        "accepted_proof_kinds",
        "allowed_tool_name_patterns",
        "default_probe",
        "client_reload_requirement",
        "job",
        "recovery_state",
        "approval_challenge",
        "challenge_id",
        "plan_digest",
        "plan_id",
        "receipt_refs",
        "receipts",
    }
)


def client_visible_project_init_apply_payload(value: dict[str, Any]) -> dict[str, Any]:
    """Return the narrow install-only public DTO for apply-style results."""

    cleaned = client_visible_project_init_payload(value)
    keep_keys = [
        "ok",
        "project_root",
        "dry_run",
        "approval_scope",
        "state_status",
        "selected_service_bindings",
        "writes",
        "non_actions",
        "state_revision",
        "installation_mode",
        "installation_status",
        "installed_service_bindings",
        "message",
        "next_turn",
        "status",
        "error",
    ]
    public = {key: cleaned[key] for key in keep_keys if key in cleaned}
    if cleaned.get("installation_status") == "installed":
        installed = [str(binding) for binding in cleaned.get("installed_service_bindings") or [] if str(binding)]
        installed_text = ", ".join(installed)
        next_turn_value = cleaned.get("next_turn") if isinstance(cleaned.get("next_turn"), Mapping) else {}
        reload_prompt = str(next_turn_value.get("prompt") or "").strip()
        if reload_prompt.startswith("ContextForge tools are installed for this project. "):
            reload_prompt = reload_prompt.removeprefix("ContextForge tools are installed for this project. ")
        if installed_text:
            public["message"] = (
                f"ContextForge tools are installed for this project: {installed_text}. "
                f"{reload_prompt or 'A new session or reload is required before the tools register in the client.'}"
            )
        elif "message" not in public:
            public["message"] = "ContextForge tools are installed for this project. A new session or reload is required before the tools register in the client."
    return public


def client_visible_project_init_list_payload(value: dict[str, Any]) -> dict[str, Any]:
    """Return only the service menu needed for client-facing selection."""

    cleaned = client_visible_project_init_payload(value)
    public: dict[str, Any] = {
        key: cleaned[key]
        for key in ("ok", "client_type", "root_attestation", "status", "assistant_visible_response", "alignment_import_offer", "next_turn", "non_actions", "error")
        if key in cleaned
    }
    services = []
    for service in cleaned.get("available_services") or []:
        if not isinstance(service, dict):
            continue
        services.append(
            {
                key: service[key]
                for key in (
                    "service_binding",
                    "display_name",
                    "scope_label",
                    "user_visible_effect",
                    "project_service_state",
                    "target_client_projection_status",
                    "target_client_state",
                    "available_to_target_client",
                    "recommended_action",
                )
                if key in service
            }
        )
    is_alignment_import = bool(cleaned.get("alignment_import_offer"))
    if services:
        public["available_services"] = services
    if services and not is_alignment_import:
        service_lines = []
        for index, service in enumerate(services, start=1):
            binding = str(service.get("service_binding") or "")
            service_name = binding.split(":", 1)[0] if binding else str(service.get("display_name") or "")
            if not service_name:
                continue
            service_lines.append(f"{index}. {service_name} - Available - {_capability_label(service_name)}.")
        public["assistant_visible_response"] = _visible_helper_response(
            "ContextForge services",
            [
                "\n".join(service_lines),
                "Reply with service names or numbers to enable them, or choose none.",
            ],
        )
        public["message"] = public["assistant_visible_response"]
        public["copy_as_complete_visible_response"] = True
        public["do_not_summarize"] = True
    next_turn_value = public.get("next_turn")
    if isinstance(next_turn_value, dict) and not is_alignment_import:
        choices = []
        for choice in next_turn_value.get("choices") or []:
            if not isinstance(choice, dict):
                continue
            choices.append(
                {
                    key: choice[key]
                    for key in ("number", "id", "label", "effect")
                    if key in choice
                }
            )
        next_turn_value["prompt"] = "Which ContextForge services should I enable for this project?"
        next_turn_value["choices"] = choices
        response_form = next_turn_value.get("response_form")
        if isinstance(response_form, dict):
            response_form["options"] = choices
            response_form["respond_with"] = "service name, selection number, or option id"
        next_turn_value["allowed_response_shape"] = "service name(s), selection number(s), service id(s), or choose none"
    return public


def client_visible_project_init_plan_payload(value: dict[str, Any], *, include_next_turn: bool = True) -> dict[str, Any]:
    """Return the narrow approval package needed for client-facing consent."""

    cleaned = client_visible_project_init_payload(value)
    keep_keys = [
        "ok",
        "workflow",
        "client_type",
        "project_root",
        "required_inputs",
        "skipped_services",
        "plan_summary",
        "installation_mode",
        "non_actions",
        "next_turn",
        "status",
        "error",
    ]
    public = {key: cleaned[key] for key in keep_keys if key in cleaned}
    if "selected_service_bindings" not in public:
        public["selected_service_bindings"] = [
            str(service.get("service_binding"))
            for service in cleaned.get("selected_services") or []
            if isinstance(service, dict) and service.get("service_binding")
        ]
    if "message" not in public and isinstance(cleaned.get("plan_summary"), dict):
        summary = cleaned["plan_summary"]
        bindings = summary.get("bindings") if isinstance(summary.get("bindings"), list) else []
        display_by_binding = {
            str(service.get("service_binding")): str(
                service.get("display_name")
                or service.get("canonical_service")
                or service.get("service_family")
                or str(service.get("service_binding")).split(":", 1)[0]
            )
            for service in cleaned.get("selected_services") or []
            if isinstance(service, dict) and service.get("service_binding")
        }
        service_names = ", ".join(
            display_by_binding.get(
                str(binding.get("service_binding") or ""),
                str(binding.get("display_name") or binding.get("service_binding") or "").split(":", 1)[0],
            )
            for binding in bindings
            if isinstance(binding, dict) and binding.get("service_binding")
        ) or ", ".join(str(item).split(":", 1)[0] for item in public.get("selected_service_bindings") or [])
        writes = summary.get("project_local_writes") if isinstance(summary.get("project_local_writes"), list) else []
        writes_text = ", ".join(str(path) for path in writes) or "project-local ContextForge state"
        required_inputs = _visible_required_input_summary(cleaned.get("required_inputs"))
        input_text = f" Required inputs: {required_inputs}." if required_inputs else ""
        public["message"] = (
            f"Plan ready for {service_names}. It will write {writes_text}; "
            "it will not mutate user-global config, secrets, backend services, or the ContextForge registry."
            f"{input_text} "
            "\n\nApprove or decline?"
        )
    if "message" not in public and isinstance(cleaned.get("next_turn"), dict):
        next_turn_value = cleaned["next_turn"]
        prompt = str(next_turn_value.get("prompt") or "").strip()
        choices = next_turn_value.get("choices") if isinstance(next_turn_value.get("choices"), list) else []
        rendered_choices = []
        for choice in choices:
            if not isinstance(choice, Mapping):
                continue
            number = choice.get("number")
            label = str(choice.get("label") or choice.get("id") or "").strip()
            effect = str(choice.get("effect") or "").strip()
            if isinstance(number, int) and label:
                rendered_choices.append(f"{number}. {label}" + (f" - {effect}" if effect else ""))
        if prompt:
            public["message"] = "\n".join([prompt, *rendered_choices]) if rendered_choices else prompt
    if public.get("message"):
        visible_message = str(public["message"])
        reordered: dict[str, Any] = {
            "ok": public.get("ok", True),
            "assistant_visible_response": visible_message,
            "message": visible_message,
            "copy_as_complete_visible_response": True,
            "do_not_summarize": True,
        }
        for key in (
            "workflow",
            "client_type",
            "project_root",
            "selected_service_bindings",
            "installation_mode",
            "non_actions",
            "status",
            "error",
        ):
            if key in public and key not in reordered:
                reordered[key] = public[key]
        if public.get("required_inputs"):
            for key, item in public.items():
                if key not in reordered:
                    reordered[key] = item
        public = reordered
    if not include_next_turn:
        public.pop("next_turn", None)
    return public


def _visible_required_input_summary(value: Any) -> str:
    if not isinstance(value, Mapping):
        return ""
    parts: list[str] = []
    for service_binding, service_inputs in value.items():
        if not isinstance(service_inputs, Mapping):
            continue
        rendered = ", ".join(
            f"{key}={service_inputs[key]}"
            for key in sorted(service_inputs)
            if service_inputs.get(key)
        )
        if rendered:
            parts.append(f"{service_binding} {rendered}")
    return "; ".join(parts)


def client_visible_project_init_decision_payload(value: dict[str, Any]) -> dict[str, Any]:
    """Return the narrow public DTO for decline/defer decisions."""

    cleaned = client_visible_project_init_payload(value)
    keep_keys = [
        "ok",
        "assistant_visible_response",
        "message",
        "copy_as_complete_visible_response",
        "do_not_summarize",
        "project_root",
        "client_type",
        "decision_state",
        "selected_service_bindings",
        "state_revision",
        "non_actions",
        "status",
        "error",
    ]
    public = {key: cleaned[key] for key in keep_keys if key in cleaned}
    if "assistant_visible_response" in public:
        public["message"] = public["assistant_visible_response"]
        public["copy_as_complete_visible_response"] = True
        public["do_not_summarize"] = True
    return public


def client_visible_project_tool_availability_payload(value: dict[str, Any]) -> dict[str, Any]:
    """Return the normal-use read-only availability DTO for initialized projects."""

    cleaned = client_visible_project_init_payload(value)
    keep_keys = [
        "ok",
        "assistant_visible_response",
        "message",
        "copy_as_complete_visible_response",
        "do_not_summarize",
        "non_actions",
        "status",
        "error",
    ]
    public = {key: cleaned[key] for key in keep_keys if key in cleaned}
    if "assistant_visible_response" in public:
        public["message"] = public["assistant_visible_response"]
        public["copy_as_complete_visible_response"] = True
        public["do_not_summarize"] = True
    return public


def client_visible_project_capability_summary_payload(value: dict[str, Any]) -> dict[str, Any]:
    """Return the normal-use read-only capability-summary DTO."""

    cleaned = client_visible_project_init_payload(value)
    keep_keys = [
        "ok",
        "assistant_visible_response",
        "message",
        "copy_as_complete_visible_response",
        "do_not_summarize",
        "non_actions",
        "status",
        "error",
    ]
    public = {key: cleaned[key] for key in keep_keys if key in cleaned}
    if "assistant_visible_response" in public:
        public["message"] = public["assistant_visible_response"]
        public["copy_as_complete_visible_response"] = True
        public["do_not_summarize"] = True
    return public


def client_visible_project_state_readback_payload(value: dict[str, Any]) -> dict[str, Any]:
    """Return the normal-use read-only project-state readback DTO."""

    cleaned = client_visible_project_init_payload(value)
    keep_keys = [
        "ok",
        "assistant_visible_response",
        "message",
        "copy_as_complete_visible_response",
        "do_not_summarize",
        "non_actions",
        "status",
        "error",
    ]
    public = {key: cleaned[key] for key in keep_keys if key in cleaned}
    if "assistant_visible_response" in public:
        public["message"] = public["assistant_visible_response"]
        public["copy_as_complete_visible_response"] = True
        public["do_not_summarize"] = True
    return public


def client_visible_project_init_payload(value: Any) -> Any:
    """Remove retired project-init check/probe internals from client tool output."""

    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            if key in _CLIENT_HIDDEN_KEYS:
                continue
            if key == "verification_layers" and isinstance(item, dict):
                visible_layers = {
                    layer_key: client_visible_project_init_payload(layer_value)
                    for layer_key, layer_value in item.items()
                    if layer_key != "tool_policy"
                }
                if visible_layers:
                    cleaned[key] = visible_layers
                continue
            cleaned[key] = client_visible_project_init_payload(item)
        return cleaned
    if isinstance(value, list):
        return [client_visible_project_init_payload(item) for item in value]
    return value


def client_visible_service_onboarding_payload(value: dict[str, Any]) -> dict[str, Any]:
    """Return the narrow service-onboarding DTO intended for assistant tool use."""

    visible = str(value.get("assistant_visible_response") or value.get("message") or "").strip()
    public = {
        "ok": value.get("ok", True),
        "status": value.get("status"),
        "project_root": value.get("project_root"),
        "mutation_allowed": False,
        "assistant_visible_response": visible,
        "message": visible,
        "copy_as_complete_visible_response": bool(visible),
        "do_not_summarize": bool(visible),
        "assistant_response_policy": {
            "copy_assistant_visible_response_exactly": bool(visible),
            "stop_after_visible_response": bool(visible),
            "do_not_write_direct_client_local_mcp_config": True,
            "direct_client_config_is_not_contextforge_onboarding": True,
        },
        "non_actions": value.get("non_actions") or [],
    }
    if value.get("status") == "service_onboarding_source_research":
        public.update(
            {
                "source_path": value.get("source_path"),
                "source_kind": value.get("source_kind"),
                "github": value.get("github"),
                "source_files": value.get("source_files") or [],
                "retrieved_file_count": value.get("retrieved_file_count"),
                "retrieved_content_bytes": value.get("retrieved_content_bytes"),
                "warnings": value.get("warnings") or [],
            }
        )
    if value.get("status") == "service_onboarding_runtime_apply_package":
        public["install_artifact_contract"] = value.get("install_artifact_contract")
        public["runtime_apply_package_id"] = value.get("runtime_apply_package_id")
        public["runtime_apply_package_ref"] = {
            "id": value.get("runtime_apply_package_id"),
            "use_after_explicit_approval": "call cf_project_service_onboarding_runtime_execute with runtime_apply_package_id; do not reconstruct the full package payload from memory",
        }
    if value.get("status") in {
        "service_onboarding_runtime_apply_draft_incomplete",
        "service_onboarding_runtime_apply_draft_ready",
    }:
        public["runtime_apply_draft_id"] = value.get("runtime_apply_draft_id")
        public["structured_payload_path"] = value.get("structured_payload_path")
        public["ready_to_build_runtime_apply_package"] = value.get("ready_to_build_runtime_apply_package")
        public["accepted_fields"] = value.get("accepted_fields") or []
        public["required_inputs"] = value.get("required_inputs") or []
        public["next_required_slice"] = value.get("next_required_slice") or {}
    if value.get("status") == "service_onboarding_runtime_apply_blocked":
        public["required_inputs"] = value.get("required_inputs") or []
    return {key: item for key, item in public.items() if item not in (None, "")}


def _tool_names_for_service(service_family: str) -> list[str]:
    policy = common.safe_validation_policy(service_family)
    contract = policy.get("probe_contract") if isinstance(policy.get("probe_contract"), Mapping) else {}
    names = contract.get("allowed_tool_name_patterns") if isinstance(contract.get("allowed_tool_name_patterns"), list) else []
    return [str(name) for name in names if str(name)]


def _service_family_from_state(binding_id: str, service: Mapping[str, Any]) -> str:
    return str(
        service.get("service_family")
        or service.get("canonical_service")
        or binding_id.split(":", 1)[0]
        or binding_id
    )


def _state_skipped_or_unavailable(service: Mapping[str, Any]) -> dict[str, Any] | None:
    status = str(
        service.get("status")
        or service.get("contextforge_readback_status")
        or service.get("provision_status")
        or ""
    ).lower()
    if status in {"skipped", "unavailable", "missing", "blocked", "failed"}:
        return {
            "service_binding": str(service.get("service_binding") or ""),
            "status": status,
            "reason": str(service.get("skipped_reason") or service.get("reason") or service.get("x_reason") or "reported unavailable"),
        }
    return None


def _tool_policy_status_for_service(service: Mapping[str, Any], tool_names: list[str]) -> str:
    layers = service.get("verification_layers")
    if isinstance(layers, Mapping):
        tool_policy = layers.get("tool_policy")
        if isinstance(tool_policy, Mapping) and tool_policy.get("status"):
            return str(tool_policy.get("status"))
    return "known" if tool_names else "not_recorded"


def _target_client_projection_status(
    target_client_state: Mapping[str, Any],
    session_boundary: Mapping[str, Any] | None = None,
) -> str:
    status = str(target_client_state.get("status") or "not_recorded")
    validation_status = str(target_client_state.get("validation_status") or "")
    reload_status = str(target_client_state.get("reload_status") or "")
    session_boundary = session_boundary or {}
    if status in {"not_recorded", "uninitialized"}:
        return "missing"
    if status in {"blocked", "failed"} or validation_status == "blocked":
        return "blocked"
    if status == "skipped" or validation_status == "skipped":
        return "skipped"
    if status in {"stale", "stale_projection"} or target_client_state.get("stale") is True:
        return "stale"
    if status in {"partial", "partial_projection"} or validation_status == "mixed":
        return "partial"
    if (
        status == "reload_required"
        or reload_status in {"required", "pending_reload", "reload_observed", "acknowledged", "reload_acknowledged", "reload_required"}
        or session_boundary.get("requires_reload") is True
    ):
        return "reload_required"
    if status in {"activation_pending", "validation_pending"} or validation_status in {"not_started", "pending"}:
        return "validation_pending"
    if (
        status == "verified"
        or validation_status == "passed"
        or bool(target_client_state.get("proof_ref"))
        or target_client_state.get("target_client_visible") is True
    ):
        return "verified"
    if status in {"installed", "presumed_working"} or validation_status in {"installed", "presumed_working"}:
        return "imported"
    return "recorded"


def _target_client_visibility_status(target_client_state: Mapping[str, Any]) -> str:
    if _target_client_projection_status(target_client_state) == "missing":
        return "not_claimed"
    if target_client_state.get("target_client_visible") is True:
        return "visible_proof_recorded"
    return "not_proven_by_readback"


def _target_client_proof_status(target_client_state: Mapping[str, Any]) -> str:
    if _target_client_projection_status(target_client_state) == "missing":
        return "not_recorded"
    if target_client_state.get("proof_ref"):
        return "proof_ref_recorded"
    return "not_claimed_by_readback"


def _projection_status_allows_target_client_availability(status: str) -> bool:
    return status in {"imported", "verified"}


def _runtime_observed_tools_by_service(runtime_readback: Mapping[str, Any] | None) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(runtime_readback, Mapping):
        return {}
    tools = runtime_readback.get("tools")
    if not isinstance(tools, Sequence) or isinstance(tools, (str, bytes)):
        return {}
    by_service: dict[str, list[dict[str, Any]]] = {}
    for raw_tool in tools:
        if not isinstance(raw_tool, Mapping):
            continue
        service_binding = str(raw_tool.get("serviceBinding") or raw_tool.get("service_binding") or "")
        mcp_name = str(raw_tool.get("mcpName") or raw_tool.get("mcp_name") or "")
        pi_name = str(raw_tool.get("piName") or raw_tool.get("pi_name") or "")
        if not service_binding or not mcp_name:
            continue
        by_service.setdefault(service_binding, []).append(
            {
                "mcp_name": mcp_name,
                "pi_name": pi_name,
                "blocked_by_default": bool(raw_tool.get("blockedByDefault") or raw_tool.get("blocked_by_default")),
            }
        )
    return by_service


def _normalize_mcp_status(value: Any) -> str:
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if text in {"ok", "pass", "passed", "success", "started", "running", "available", "listed"}:
        return "passed"
    if text in {"fail", "failed", "error", "errored", "unavailable", "not_running", "not_started", "timeout", "timed_out"}:
        return "failed"
    if text in {"unknown", "not_checked", "not_observed", "not_claimed", "pending", ""}:
        return "not_observed"
    return text


def _mcp_runtime_error_text(diagnostics: Mapping[str, Any], target_client_state: Mapping[str, Any]) -> str:
    values: list[str] = []
    for source in (diagnostics, target_client_state):
        for key in (
            "error",
            "error_class",
            "error_message",
            "last_error",
            "message",
            "mcp_error",
            "mcp_error_class",
            "mcp_error_message",
            "stderr",
            "startup_error",
            "transport_error",
        ):
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                values.append(value)
    return " ".join(values).lower().replace("-", "_")


def _target_client_mcp_runtime_diagnostic(target_client_state: Mapping[str, Any], session_boundary: Mapping[str, Any]) -> dict[str, Any]:
    raw = target_client_state.get("mcp_runtime_diagnostics")
    diagnostics = dict(raw) if isinstance(raw, Mapping) else {}
    startup_status = _normalize_mcp_status(diagnostics.get("startup_status") or target_client_state.get("mcp_startup_status"))
    auth_status = _normalize_mcp_status(diagnostics.get("auth_status") or target_client_state.get("mcp_auth_status"))
    transport_status = _normalize_mcp_status(diagnostics.get("transport_status") or target_client_state.get("mcp_transport_status"))
    tool_listing_status = _normalize_mcp_status(diagnostics.get("tool_listing_status") or target_client_state.get("mcp_tool_listing_status"))
    error_text = _mcp_runtime_error_text(diagnostics, target_client_state)
    attempted = bool(
        diagnostics.get("attempted")
        or target_client_state.get("mcp_startup_attempted")
        or any(status != "not_observed" for status in (startup_status, auth_status, transport_status, tool_listing_status))
        or error_text
    )
    auth_error_observed = any(
        needle in error_text
        for needle in (
            "401",
            "403",
            "auth_failed",
            "authentication_failed",
            "authorization_failed",
            "forbidden",
            "invalid_token",
            "permission_denied",
            "unauthorized",
        )
    )
    transport_error_observed = any(
        needle in error_text
        for needle in (
            "connection refused",
            "connection_refused",
            "connect_econnrefused",
            "connection reset",
            "connection_reset",
            "econnrefused",
            "socket hang up",
            "transport_error",
            "transport_failed",
        )
    )
    startup_error_observed = any(
        needle in error_text
        for needle in (
            "command_not_found",
            "enoent",
            "process_exit",
            "server process exited",
            "startup_failed",
        )
    )
    if startup_status == "failed" or startup_error_observed:
        classification = "mcp_server_startup_failed"
    elif auth_status == "failed" or auth_error_observed:
        auth_status = "failed" if auth_status == "not_observed" else auth_status
        classification = "contextforge_auth_failed"
    elif transport_status == "failed" or transport_error_observed:
        transport_status = "failed" if transport_status == "not_observed" else transport_status
        classification = "contextforge_transport_failed"
    elif tool_listing_status == "failed":
        classification = "tool_listing_failed"
    elif attempted and all(status in {"passed", "not_observed"} for status in (startup_status, auth_status, transport_status, tool_listing_status)):
        classification = "mcp_available_or_partially_observed"
    elif session_boundary.get("requires_reload"):
        classification = "reload_pending_before_mcp_startup"
    elif session_boundary.get("tools_registered_observed"):
        classification = "tools_registered_observed_without_mcp_startup_diagnostic"
    else:
        classification = "no_mcp_startup_observation"
    evidence_ref = diagnostics.get("evidence_ref") or target_client_state.get("mcp_evidence_ref")
    error_class = diagnostics.get("error_class") or target_client_state.get("mcp_error_class")
    result: dict[str, Any] = {
        "classification": classification,
        "attempted": attempted,
        "startup_status": startup_status,
        "auth_status": auth_status,
        "transport_status": transport_status,
        "tool_listing_status": tool_listing_status,
        "secret_values_redacted": True,
        "validation_proof": "not_claimed",
    }
    if evidence_ref:
        result["evidence_ref"] = str(evidence_ref)
    if error_class:
        result["error_class"] = str(error_class)
    return result


def _mcp_runtime_diagnostic_note(diagnostics: Sequence[Mapping[str, Any]], session_boundary: Mapping[str, Any], client_type: str) -> str:
    failures = [
        item
        for item in diagnostics
        if str(item.get("classification") or "")
        in {"mcp_server_startup_failed", "contextforge_auth_failed", "contextforge_transport_failed", "tool_listing_failed"}
    ]
    if failures:
        classes = ", ".join(sorted({str(item.get("classification")) for item in failures}))
        return (
            f"{client_type} has already attempted MCP startup; do not ask for another reload before diagnosing "
            f"the recorded MCP startup/auth/transport status ({classes})."
        )
    return str(session_boundary.get("instruction") or "")


def _mcp_runtime_diagnostic_blocks_availability(diagnostic: Mapping[str, Any]) -> bool:
    return str(diagnostic.get("classification") or "") in {
        "mcp_server_startup_failed",
        "contextforge_auth_failed",
        "contextforge_transport_failed",
        "tool_listing_failed",
    }


def _missing_projection_action(service_binding: str, client_type: str) -> dict[str, str]:
    return {
        "action": "align_target_client_to_existing_project_service",
        "target_client": client_type,
        "service_binding": service_binding,
        "boundary": (
            f"Align/import {client_type} to the existing project service instance; "
            "do not create a new project service instance unless explicitly approved."
        ),
    }


def _project_client_reload_state(state: Mapping[str, Any], client_type: str) -> dict[str, Any]:
    project_init = state.get("project_init") if isinstance(state.get("project_init"), Mapping) else {}
    client_states = project_init.get("client_states") if isinstance(project_init.get("client_states"), Mapping) else {}
    client_state = client_states.get(client_type) if isinstance(client_states.get(client_type), Mapping) else {}
    reload_status = str(client_state.get("reload_status") or "unknown")
    if reload_status == "tools_registered_observed":
        canonical_status = "tools_registered_observed"
    elif reload_status == "not_required":
        canonical_status = "not_required"
    elif reload_status in {"required", "pending_reload", "reload_observed", "acknowledged", "reload_acknowledged", "reload_required"}:
        canonical_status = "reload_required"
    else:
        canonical_status = "unknown"
    requires_reload = canonical_status == "reload_required"
    tools_registered_observed = canonical_status == "tools_registered_observed"
    if requires_reload:
        user_status = "reload_required"
    elif tools_registered_observed:
        user_status = "tools_registered_observed"
    elif canonical_status == "not_required":
        user_status = "reload_not_required"
    else:
        user_status = "reload_status_unknown"
    return {
        "client_type": client_type,
        "reload_status": canonical_status,
        "user_status": user_status,
        "requires_reload": requires_reload,
        "reload_acknowledged": False,
        "tools_registered_observed": tools_registered_observed,
    }


def _client_session_boundary(state: Mapping[str, Any], client_type: str) -> dict[str, Any]:
    reload_state = _project_client_reload_state(state, client_type)
    reload_requirement = common.client_reload_requirement(client_type, event="project_activation_apply")
    if reload_state["tools_registered_observed"]:
        instruction = "The target-client session has observed the installed ContextForge tools; no reload reminder is pending."
    elif reload_state["requires_reload"] and isinstance(reload_requirement, Mapping):
        instruction = str(reload_requirement.get("instruction") or "")
    elif reload_state["requires_reload"]:
        instruction = "A client reload or new session is required before the installed ContextForge tools register."
    elif isinstance(reload_requirement, Mapping):
        instruction = str(reload_requirement.get("instruction") or "")
    else:
        instruction = "This client can use the current project-state readback without a separate reload requirement recorded for project activation."
    return {
        **reload_state,
        "instruction": instruction,
    }


def _target_client_user_state(target_client_state: Mapping[str, Any], session_boundary: Mapping[str, Any]) -> str:
    if session_boundary.get("tools_registered_observed"):
        return "projection recorded; tools registered observed"
    status = str(target_client_state.get("status") or "recorded")
    if session_boundary.get("requires_reload"):
        return "projection recorded; client reload required"
    if status == "not_recorded":
        return "client state not_recorded"
    if status == "blocked":
        return "blocked"
    return "projection recorded"


def project_tool_availability(
    project_root: str,
    client_type: str = DEFAULT_CLIENT_TYPE,
    target_client_runtime: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Read initialized project state and summarize client-visible ContextForge tools."""

    root = project_state.validate_project_root(project_root, require_workspace=True)
    state = project_state.read_or_default(root)
    services = state.get("services") if isinstance(state.get("services"), Mapping) else {}
    available_tools: list[dict[str, Any]] = []
    project_services: list[dict[str, Any]] = []
    project_tool_policies: list[dict[str, Any]] = []
    missing_target_client_projection: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    approved: list[str] = []
    session_boundary = _client_session_boundary(state, client_type)
    runtime_tools_by_service = _runtime_observed_tools_by_service(target_client_runtime)
    if runtime_tools_by_service:
        session_boundary = {
            **session_boundary,
            "requires_reload": False,
            "reload_status": "tools_registered_observed",
            "user_status": "tools_registered_observed",
            "tools_registered_observed": True,
            "instruction": "The current target-client session has observed imported ContextForge tools; do not ask for another reload.",
        }
    mcp_runtime_diagnostics: list[dict[str, Any]] = []
    decision_bindings: set[str] = set()
    decisions = state.get("decisions") if isinstance(state.get("decisions"), Mapping) else {}
    for decision_key, decision_value in decisions.items():
        if not isinstance(decision_value, Mapping):
            continue
        decision_state = str(decision_value.get("state") or "")
        if decision_state not in {"declined", "deferred", "disabled"}:
            continue
        binding = str(decision_value.get("service_binding") or decision_key)
        if not binding:
            continue
        decision_bindings.add(binding)
        skipped.append(
            {
                "service_binding": binding,
                "status": decision_state,
                "reason": str(decision_value.get("notes") or f"service was {decision_state} by project-local user decision"),
            }
        )
    for binding_id, service_value in services.items():
        if not isinstance(service_value, Mapping):
            continue
        service = dict(service_value)
        service.setdefault("service_binding", str(binding_id))
        service_binding = str(service.get("service_binding") or binding_id)
        if service_binding in decision_bindings:
            continue
        approved.append(service_binding)
        service_family = _service_family_from_state(service_binding, service)
        skipped_item = _state_skipped_or_unavailable(service)
        if skipped_item:
            skipped.append(skipped_item)
            continue
        tool_names = _tool_names_for_service(service_family)
        target_client_state = _client_state_for_service(service, client_type)
        runtime_observed_tools = runtime_tools_by_service.get(service_binding, [])
        projection_status = _target_client_projection_status(target_client_state, session_boundary)
        tool_policy_status = _tool_policy_status_for_service(service, tool_names)
        mcp_diagnostic = _target_client_mcp_runtime_diagnostic(target_client_state, session_boundary)
        if runtime_observed_tools:
            observed_tool_names = [item["mcp_name"] for item in runtime_observed_tools if not item["blocked_by_default"]]
            if observed_tool_names:
                tool_names = observed_tool_names
            projection_status = "verified"
            mcp_diagnostic = {
                **mcp_diagnostic,
                "classification": "mcp_available_or_partially_observed",
                "attempted": True,
                "startup_status": "passed",
                "tool_listing_status": "passed",
                "validation_proof": "runtime_readback_observed",
                "runtime_observed_pi_tools": [item["pi_name"] for item in runtime_observed_tools if item["pi_name"]],
            }
        runtime_blocks_availability = _mcp_runtime_diagnostic_blocks_availability(mcp_diagnostic)
        available_to_target_client = bool(
            _projection_status_allows_target_client_availability(projection_status)
            and tool_names
            and not runtime_blocks_availability
        )
        mcp_runtime_diagnostics.append({"service_binding": service_binding, **mcp_diagnostic})
        availability_item = {
            "service_binding": service_binding,
            "service_family": service_family,
            "project_service_state": "present",
            "provision_status": str(service.get("provision_status") or "unknown"),
            "target_client_state": target_client_state,
            "target_client_projection_status": projection_status,
            "tool_policy_status": tool_policy_status,
            "tool_policy_names": tool_names,
            "target_client_visibility_status": "visible_in_current_session" if runtime_observed_tools else _target_client_visibility_status(target_client_state),
            "target_client_proof_status": "runtime_readback_observed" if runtime_observed_tools else _target_client_proof_status(target_client_state),
            "mcp_runtime_diagnostic": mcp_diagnostic,
            "available_to_target_client": available_to_target_client,
        }
        if projection_status == "missing":
            action = _missing_projection_action(service_binding, client_type)
            availability_item["recommended_action"] = action
            missing_target_client_projection.append(action)
        project_services.append(availability_item)
        project_tool_policies.append(
            {
                "service_binding": service_binding,
                "service_family": service_family,
                "project_service_state": "present",
                "tool_policy_status": tool_policy_status,
                "tool_policy_names": tool_names,
            }
        )
        if tool_names:
            if available_to_target_client:
                available_tools.append(
                    {
                        "service_binding": service_binding,
                        "service_family": service_family,
                        "tool_names": tool_names,
                        "project_service_state": "present",
                        "target_client_state": target_client_state,
                        "target_client_projection_status": projection_status,
                        "tool_policy_status": tool_policy_status,
                        "tool_policy_names": tool_names,
                        "mcp_runtime_diagnostic": mcp_diagnostic,
                        "available_to_target_client": True,
                    }
                )
    skipped_text = (
        "none reported"
        if not skipped
        else "; ".join(f"{item['service_binding']}: {item['status']} ({item['reason']})" for item in skipped)
    )
    project_service_text = (
        ", ".join(item["service_binding"] for item in project_services)
        or "none recorded"
    )
    if available_tools:
        tool_text = "; ".join(
            f"{item['service_binding']} exposes {', '.join(item['tool_names'])}"
            for item in available_tools
        )
    elif project_services and len(missing_target_client_projection) == len(project_services):
        tool_text = "no target-client projection/import recorded for the approved project services"
    elif project_services:
        tool_text = "no currently available target-client tools in this session"
    else:
        tool_text = "none reported"
    missing_projection_text = (
        "; ".join(
            f"{item['service_binding']}: align/import existing project service instance for {client_type}; do not create a new project service instance without explicit approval"
            for item in missing_target_client_projection
        )
        or "none recorded"
    )
    mcp_diagnostic_text = (
        "; ".join(
            f"{item['service_binding']}: {item['classification']}"
            for item in mcp_runtime_diagnostics
        )
        or "none recorded"
    )
    revision = project_state.state_revision(state)
    refresh_boundary = _mcp_runtime_diagnostic_note(mcp_runtime_diagnostics, session_boundary, client_type)
    visible_response = _visible_helper_response(
        "ContextForge tool availability",
        [
            _visible_section(
                "Project",
                [
                    f"- Root: `{str(root)}`",
                    "- Status: initialized",
                    f"- Revision: {revision}",
                    f"- Target client: {client_type}",
                ],
            ),
            _visible_section(
                "Project services",
                _visible_item_list([item["service_binding"] for item in project_services]),
            ),
            _visible_section(
                "Configured/imported tools for this client",
                _visible_item_list(
                    [
                        f"{item['service_binding']}: {', '.join(item['tool_names'])}"
                        for item in available_tools
                    ],
                    empty=tool_text,
                ),
            ),
            _visible_section(
                "Missing target-client projections",
                _visible_item_list(
                    [
                        f"{item['service_binding']}: align/import existing project service instance for {client_type}; do not create a new project service instance without explicit approval"
                        for item in missing_target_client_projection
                    ]
                ),
            ),
            _visible_section(
                "Skipped or unavailable services",
                _visible_item_list(
                    [
                        f"{item['service_binding']}: {item['status']} ({item['reason']})"
                        for item in skipped
                    ],
                    empty=skipped_text,
                ),
            ),
            _visible_section(
                "MCP runtime diagnostics",
                _visible_item_list(
                    [
                        f"{item['service_binding']}: {item['classification']}"
                        for item in mcp_runtime_diagnostics
                    ],
                    empty=mcp_diagnostic_text,
                ),
            ),
            _visible_section(
                "Readback limits",
                [
                    "- Client-visible tool use is not proven by this readback; target-client-visible=false states remain unproven.",
                    "- This is a read-only project-state readback; interactive proof is not claimed by this readback.",
                ],
            ),
            _visible_section("Next step", [f"- {refresh_boundary}"]),
        ],
    )
    return {
        "ok": True,
        "status": "available_tools_report",
        "client_type": client_type,
        "project_root": str(root),
        "state_status": state.get("status"),
        "state_revision": revision,
        "approved_service_bindings": approved,
        "available_tools": available_tools,
        "project_services": project_services,
        "project_tool_policies": project_tool_policies,
        "missing_target_client_projection": missing_target_client_projection,
        "skipped_or_unavailable_services": skipped,
        "current_session_boundary": session_boundary,
        "mcp_runtime_diagnostics": mcp_runtime_diagnostics,
        "assistant_visible_response_policy": {
            "internal_status_terms_suppressed": True,
            "diagnostic_state_retained_in_structured_fields": True,
        },
        "assistant_visible_response": visible_response,
        "non_actions": [
            "read-only initialized-project availability report",
            "no service selection",
            "no project-init proposal, approval, or apply",
            "no tool probe or backend mutation",
        ],
    }


def project_capability_summary(project_root: str, client_type: str = DEFAULT_CLIENT_TYPE) -> dict[str, Any]:
    """Read project state and catalog candidates into a normal-language capability summary."""

    root = project_state.validate_project_root(project_root, require_workspace=True)
    state = project_state.read_or_default(root)
    tool_report = project_tool_availability(project_root=str(root), client_type=client_type)
    approved = set(str(item) for item in tool_report.get("approved_service_bindings") or [])
    project_services = [
        item
        for item in tool_report.get("project_services") or []
        if isinstance(item, Mapping)
    ]
    missing_projection = [
        item
        for item in tool_report.get("missing_target_client_projection") or []
        if isinstance(item, Mapping)
    ]
    unavailable_bindings = {
        str(item.get("service_binding") or "")
        for item in tool_report.get("skipped_or_unavailable_services") or []
        if isinstance(item, Mapping)
    }
    available_now = [
        {
            "service_binding": str(item.get("service_binding")),
            "capability": _capability_label(str(item.get("service_family") or item.get("service_binding"))),
            "tool_names": [str(name) for name in item.get("tool_names") or []],
            "provenance": "approved project state plus recorded target-client projection and ContextForge tool policy",
        }
        for item in tool_report.get("available_tools") or []
        if isinstance(item, Mapping)
    ]
    known_unavailable = [
        {
            "service_binding": str(item.get("service_binding")),
            "status": str(item.get("status")),
            "reason": str(item.get("reason")),
            "provenance": "project state unavailable/skipped service record",
        }
        for item in tool_report.get("skipped_or_unavailable_services") or []
        if isinstance(item, Mapping)
    ]
    onboarding_needed: list[dict[str, str]] = []
    try:
        catalog_services = _contextforge_registry_service_offerings(root)
    except ContextForgeCatalogUnavailable as exc:
        return _catalog_unavailable_payload(root, client_type, exc)
    for candidate in catalog_services:
        if not isinstance(candidate, Mapping):
            continue
        binding = str(candidate.get("service_binding") or "")
        if not binding or binding in approved or binding in unavailable_bindings:
            continue
        onboarding_needed.append(
            {
                "service_binding": binding,
                "capability": str(candidate.get("display_name") or candidate.get("canonical_service") or binding.split(":", 1)[0]),
                "scope": str(candidate.get("scope_label") or candidate.get("activation_class") or candidate.get("instantiation_class") or "known catalog service"),
                "provenance": "ContextForge catalog; available to enable or repair for this project state",
            }
        )
    revision = project_state.state_revision(state)
    available_text = (
        "; ".join(
            f"{item['capability']} via {item['service_binding']}"
            for item in available_now
        )
        or "none reported"
    )
    project_service_text = (
        ", ".join(str(item.get("service_binding") or "") for item in project_services if item.get("service_binding"))
        or "none recorded"
    )
    missing_projection_text = (
        "; ".join(
            f"{item.get('service_binding')}: align/import existing project service instance for {client_type}; no new project service instance without explicit approval"
            for item in missing_projection
        )
        or "none recorded"
    )
    unavailable_text = (
        "; ".join(
            f"{item['service_binding']} ({item['status']}: {item['reason']})"
            for item in known_unavailable
        )
        or "none reported"
    )
    onboarding_text = (
        ", ".join(
            item["capability"]
            for item in onboarding_needed
        )
        or "none reported"
    )
    session_boundary = _client_session_boundary(state, client_type)
    mcp_runtime_diagnostics = [
        item
        for item in tool_report.get("mcp_runtime_diagnostics") or []
        if isinstance(item, Mapping)
    ]
    refresh_boundary = _mcp_runtime_diagnostic_note(mcp_runtime_diagnostics, session_boundary, client_type)
    mcp_diagnostic_text = (
        "; ".join(
            f"{item.get('service_binding')}: {item.get('classification')}"
            for item in mcp_runtime_diagnostics
        )
        or "none recorded"
    )
    return {
        "ok": True,
        "status": "project_capability_summary",
        "client_type": client_type,
        "project_root": str(root),
        "state_status": state.get("status"),
        "state_revision": revision,
        "project_services": project_services,
        "available_now": available_now,
        "known_unavailable": known_unavailable,
        "onboarding_needed": onboarding_needed,
        "missing_target_client_projection": missing_projection,
        "current_session_boundary": session_boundary,
        "mcp_runtime_diagnostics": mcp_runtime_diagnostics,
        "assistant_visible_response_policy": {
            "internal_status_terms_suppressed": True,
            "diagnostic_state_retained_in_structured_fields": True,
        },
        "assistant_visible_response": _visible_helper_response(
            "ContextForge capability summary",
            [
                _visible_section(
                    "Source",
                    [
                        "- Project state plus ContextForge catalog.",
                        "- No changes were made.",
                    ],
                ),
                _visible_section(
                    "Project",
                    [
                        f"- Root: `{str(root)}`",
                        "- Status: initialized",
                        f"- Revision: {revision}",
                        f"- Target client: {client_type}",
                    ],
                ),
                _visible_section("Client/session boundary", [f"- {refresh_boundary}"]),
                _visible_section(
                    "Project services",
                    _visible_item_list([item["service_binding"] for item in project_services], empty=project_service_text),
                ),
                _visible_section(
                    f"Configured in current project state for {client_type}",
                    _visible_item_list(
                        [
                            f"{item.get('service_binding')}: {', '.join(str(name) for name in item.get('tool_names') or [])}"
                            for item in available_now
                            if isinstance(item, Mapping)
                        ],
                        empty=available_text,
                    ),
                ),
                _visible_section(
                    "Missing target-client projections",
                    _visible_item_list(
                        [
                            f"{item.get('service_binding')}: align/import existing project service instance for {client_type}; no new project service instance without explicit approval"
                            for item in missing_projection
                            if isinstance(item, Mapping)
                        ],
                        empty=missing_projection_text,
                    ),
                ),
                _visible_section(
                    "Known but unavailable",
                    _visible_item_list(
                        [
                            f"{item['service_binding']} ({item['status']}: {item['reason']})"
                            for item in known_unavailable
                        ],
                        empty=unavailable_text,
                    ),
                ),
                _visible_section(
                    "MCP runtime diagnostics",
                    _visible_item_list(
                        [
                            f"{item.get('service_binding')}: {item.get('classification')}"
                            for item in mcp_runtime_diagnostics
                        ],
                        empty=mcp_diagnostic_text,
                    ),
                ),
                _visible_section(
                    "Available to enable or repair",
                    _visible_item_list([item["capability"] for item in onboarding_needed], empty=onboarding_text),
                ),
            ],
        ),
        "non_actions": [
            "read-only project capability summary",
            "no service selection",
            "no project-init proposal, approval, or apply",
            "no tool probe or backend mutation",
            "no arbitrary service onboarding",
        ],
    }


def _service_management_catalog_rows(root: Path, client_type: str) -> list[dict[str, Any]]:
    state = project_state.read_or_default(root)
    services = state.get("services") if isinstance(state.get("services"), Mapping) else {}
    decisions = state.get("decisions") if isinstance(state.get("decisions"), Mapping) else {}
    disabled = {
        str((decision.get("service_binding") if isinstance(decision, Mapping) else "") or key)
        for key, decision in decisions.items()
        if isinstance(decision, Mapping) and str(decision.get("state") or "") == "disabled"
    }
    rows_by_binding: dict[str, dict[str, Any]] = {}

    for candidate in _contextforge_registry_service_offerings(root):
        if not isinstance(candidate, Mapping):
            continue
        binding = str(candidate.get("service_binding") or "")
        if not binding:
            continue
        family = str(candidate.get("canonical_service") or candidate.get("service_family") or binding.split(":", 1)[0])
        status = "Enabled" if binding in services and binding not in disabled else "Disabled" if binding in disabled else "Available"
        rows_by_binding[binding] = {
            "service_binding": binding,
            "display_name": str(candidate.get("display_name") or family),
            "status": status,
            "description": str(candidate.get("description") or _capability_label(family)).rstrip("."),
            "scope": str(candidate.get("scope_label") or candidate.get("scope_model") or candidate.get("activation_class") or candidate.get("instantiation_class") or "global"),
            "client_type": client_type,
            "service_family": family,
            "codex_alias": str(candidate.get("codex_alias") or family),
            "virtual_server": str(candidate.get("virtual_server") or ""),
            "catalog_source": str(candidate.get("catalog_source") or "contextforge_registry"),
            "helper_metadata_status": str(candidate.get("helper_metadata_status") or "unknown"),
            "contextforge_server_id": str(candidate.get("contextforge_server_id") or ""),
            "descriptor": dict(candidate),
        }

    order = {"Enabled": 0, "Available": 1, "Disabled": 2}
    return sorted(rows_by_binding.values(), key=lambda row: (order.get(str(row["status"]), 9), str(row["display_name"]).lower()))


def _service_management_row(root: Path, client_type: str, service: str) -> dict[str, Any]:
    wanted = service.strip().lower()
    if not wanted:
        raise ValueError("service is required")
    rows = _service_management_catalog_rows(root, client_type)
    for row in rows:
        aliases = {
            str(row.get("display_name") or "").lower(),
            str(row.get("service_binding") or "").lower(),
            str(row.get("service_binding") or "").split(":", 1)[0].lower(),
        }
        if wanted in aliases:
            return row
    raise ValueError(f"unknown ContextForge service: {service}")


def _public_service_management_row(row: Mapping[str, Any], *, status: str | None = None) -> dict[str, Any]:
    public = {
        key: row[key]
        for key in (
            "service_binding",
            "display_name",
            "status",
            "description",
            "scope",
            "client_type",
            "service_family",
            "codex_alias",
            "virtual_server",
            "catalog_source",
            "helper_metadata_status",
            "contextforge_server_id",
        )
        if key in row
    }
    descriptor = row.get("descriptor") if isinstance(row.get("descriptor"), Mapping) else {}
    digest = row.get("descriptor_digest") or descriptor.get("descriptor_digest")
    if digest:
        public["descriptor_digest"] = digest
    if status is not None:
        public["status"] = status
    return public


def _public_service_management_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [_public_service_management_row(row) for row in rows]


def _service_menu_name(row: Mapping[str, Any]) -> str:
    binding = str(row.get("service_binding") or "")
    if binding:
        return binding.split(":", 1)[0]
    family = str(row.get("service_family") or "")
    if family:
        return family
    return str(row.get("display_name") or "")


def _simple_service_lines(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    lines: list[str] = []
    for index, row in enumerate(rows, start=1):
        service_name = _service_menu_name(row)
        if service_name and row.get("status") and row.get("description"):
            lines.append(f"{index}. {service_name} - {row['status']} - {row['description']}.")
    return lines


def _client_reload_line(client_type: str) -> str:
    requirement = common.client_reload_requirement(client_type, event="project_activation_apply")
    if isinstance(requirement, Mapping):
        command = str(requirement.get("command") or "reload")
        return f"Reload after changes: {command}."
    return "Reload after changes if your client does not show the updated tools."


def _catalog_unavailable_payload(root: Path, client_type: str, exc: ContextForgeCatalogUnavailable) -> dict[str, Any]:
    visible = _visible_helper_response(
        "ContextForge service catalog unavailable",
        [
            f"I could not read the ContextForge registry at {exc.base_url}.",
            "Check ContextForge authentication/connectivity, then retry.",
            "No project files or service configuration were changed.",
        ],
    )
    return {
        "ok": False,
        "status": "contextforge_catalog_unavailable",
        "client_type": client_type,
        "project_root": str(root),
        "services": [],
        "catalog_error": {
            "type": exc.__class__.__name__,
            "base_url": exc.base_url,
            "reason": exc.reason,
        },
        "assistant_visible_response": visible,
        "message": visible,
        "copy_as_complete_visible_response": True,
        "do_not_summarize": True,
        "non_actions": ["read-only catalog attempt", "no service mutation"],
    }


def service_management_list(project_root: str, client_type: str = DEFAULT_CLIENT_TYPE) -> dict[str, Any]:
    root = project_state.validate_project_root(project_root, require_workspace=True)
    try:
        rows = _service_management_catalog_rows(root, client_type)
    except ContextForgeCatalogUnavailable as exc:
        return _catalog_unavailable_payload(root, client_type, exc)
    visible = _visible_helper_response(
        "ContextForge services",
        [
            "\n".join(_simple_service_lines(rows) or ["No ContextForge services are available."]),
            "Reply with service names or numbers to enable them, or choose none.",
        ],
    )
    return {
        "ok": True,
        "status": "service_management_list",
        "client_type": client_type,
        "project_root": str(root),
        "services": _public_service_management_rows(rows),
        "assistant_visible_response": visible,
        "message": visible,
        "copy_as_complete_visible_response": True,
        "do_not_summarize": True,
        "non_actions": ["read-only service list", "no service mutation"],
    }


def service_management_details(project_root: str, service: str, client_type: str = DEFAULT_CLIENT_TYPE) -> dict[str, Any]:
    root = project_state.validate_project_root(project_root, require_workspace=True)
    try:
        row = _service_management_row(root, client_type, service)
    except ContextForgeCatalogUnavailable as exc:
        return _catalog_unavailable_payload(root, client_type, exc)
    visible = _visible_helper_response(
        f"{row['display_name']} details",
        [
            f"Status: {row['status']}",
            f"Description: {row['description']}.",
            f"Scope: {row['scope']}.",
            f"Service id: {row['service_binding']}.",
            _client_reload_line(client_type),
        ],
    )
    return {
        "ok": True,
        "status": "service_management_details",
        "client_type": client_type,
        "project_root": str(root),
        "service": _public_service_management_row(row),
        "assistant_visible_response": visible,
        "message": visible,
        "copy_as_complete_visible_response": True,
        "do_not_summarize": True,
        "non_actions": ["read-only service details", "no service mutation"],
    }


def service_management_status(project_root: str, service: str = "", client_type: str = DEFAULT_CLIENT_TYPE) -> dict[str, Any]:
    if service.strip():
        return service_management_details(project_root, service, client_type=client_type)
    return service_management_list(project_root, client_type=client_type)


def _write_disabled_decision(root: Path, row: Mapping[str, Any], *, dry_run: bool, notes: str) -> dict[str, Any]:
    state = project_state.read_or_default(root)
    binding = str(row["service_binding"])
    decisions = state.setdefault("decisions", {})
    decision = project_state.decision_record("disabled", notes=notes)
    decision["service_binding"] = binding
    decision["decided_by"] = "contextforge_helper_service_management"
    decisions[binding] = decision
    if dry_run:
        return state
    return project_state.write_state_atomic(root, state, updated_by="contextforge_helper_service_management")


def _write_removed_service_state(root: Path, row: Mapping[str, Any], *, dry_run: bool) -> dict[str, Any]:
    state = project_state.read_or_default(root)
    binding = str(row["service_binding"])
    services = state.get("services") if isinstance(state.get("services"), dict) else {}
    decisions = state.get("decisions") if isinstance(state.get("decisions"), dict) else {}
    services.pop(binding, None)
    decisions.pop(binding, None)
    if dry_run:
        return state
    return project_state.write_state_atomic(root, state, updated_by="contextforge_helper_service_management")


def _remove_opencode_service_entry(root: Path, row: Mapping[str, Any], *, dry_run: bool) -> dict[str, Any]:
    config_path = root / "opencode.json"
    if not config_path.exists():
        return {"actions": [], "refusals": []}
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"actions": [], "refusals": [{"surface": str(config_path), "reason": "invalid_json_preserved", "message": str(exc)}]}
    if not isinstance(config, dict):
        return {"actions": [], "refusals": [{"surface": str(config_path), "reason": "non_object_json_preserved"}]}
    mcp = config.get("mcp")
    if not isinstance(mcp, dict):
        return {"actions": [], "refusals": []}
    alias = common.normalize_codex_alias(str(row.get("codex_alias") or row.get("service_family") or str(row.get("service_binding") or "").split(":", 1)[0]))
    if not alias or alias not in mcp:
        return {"actions": [], "refusals": []}
    existing = mcp.get(alias)
    if not helper._json_mcp_entry_is_contextforge_owned(existing):
        return {
            "actions": [],
            "refusals": [
                {
                    "surface": str(config_path),
                    "alias": alias,
                    "reason": "unmanaged_or_drifted_opencode_mcp_entry_preserved",
                }
            ],
        }
    if not dry_run:
        del mcp[alias]
        if not mcp:
            config.pop("mcp", None)
        config_path.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "actions": [
            {
                "surface": str(config_path),
                "alias": alias,
                "operation": "remove_owned_opencode_mcp_entry",
                "dry_run": dry_run,
            }
        ],
        "refusals": [],
    }


def _remove_service_client_exposure(root: Path, row: Mapping[str, Any], *, client_type: str, dry_run: bool) -> dict[str, Any]:
    if client_type == "opencode":
        return _remove_opencode_service_entry(root, row, dry_run=dry_run)
    return {"actions": [], "refusals": [], "non_actions": [f"no project-local client config removal implemented for {client_type}"]}


def service_management_disable(
    project_root: str,
    service: str,
    client_type: str = DEFAULT_CLIENT_TYPE,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    root = project_state.validate_project_root(project_root, require_workspace=True)
    try:
        row = _service_management_row(root, client_type, service)
    except ContextForgeCatalogUnavailable as exc:
        return _catalog_unavailable_payload(root, client_type, exc)
    if row["status"] != "Enabled":
        visible = f"{row['display_name']} is not enabled for this project."
        return {"ok": False, "status": "not_enabled", "assistant_visible_response": visible, "message": visible}
    if not confirm:
        visible = f"Disable {row['display_name']}? This will stop exposing it to this project and preserve backing state. Reply approve to continue."
        return {"ok": True, "status": "disable_preview", "service": _public_service_management_row(row), "assistant_visible_response": visible, "message": visible, "copy_as_complete_visible_response": True, "do_not_summarize": True}
    client_exposure = _remove_service_client_exposure(root, row, client_type=client_type, dry_run=dry_run)
    written = _write_disabled_decision(root, row, dry_run=dry_run, notes="disabled by known-service management helper")
    visible = f"{row['display_name']} is Disabled for this project. {_client_reload_line(client_type)}"
    return {"ok": True, "status": "disabled", "service": _public_service_management_row(row, status="Disabled"), "state_revision": project_state.state_revision(written), "client_exposure": client_exposure, "dry_run": dry_run, "assistant_visible_response": visible, "message": visible, "copy_as_complete_visible_response": True, "do_not_summarize": True}


def service_management_remove(
    project_root: str,
    service: str,
    client_type: str = DEFAULT_CLIENT_TYPE,
    confirmation: str = "",
    dry_run: bool = False,
) -> dict[str, Any]:
    root = project_state.validate_project_root(project_root, require_workspace=True)
    try:
        row = _service_management_row(root, client_type, service)
    except ContextForgeCatalogUnavailable as exc:
        return _catalog_unavailable_payload(root, client_type, exc)
    if row["status"] == "Available":
        visible = f"{row['display_name']} is not enabled for this project."
        return {"ok": False, "status": "not_enabled", "assistant_visible_response": visible, "message": visible}
    expected = str(row["display_name"])
    if confirmation != expected and confirmation != str(row["service_binding"]):
        visible = f'Remove {expected}? This may delete project-scoped service state. Type "{expected}" to confirm.'
        return {"ok": True, "status": "remove_confirmation_required", "service": _public_service_management_row(row), "assistant_visible_response": visible, "message": visible, "copy_as_complete_visible_response": True, "do_not_summarize": True}
    client_exposure = _remove_service_client_exposure(root, row, client_type=client_type, dry_run=dry_run)
    written = _write_removed_service_state(root, row, dry_run=dry_run)
    visible = f"{expected} was removed from this project. {_client_reload_line(client_type)}"
    return {"ok": True, "status": "removed_from_project", "service": _public_service_management_row(row, status="Available"), "state_revision": project_state.state_revision(written), "client_exposure": client_exposure, "dry_run": dry_run, "assistant_visible_response": visible, "message": visible, "copy_as_complete_visible_response": True, "do_not_summarize": True}


def service_management_enable(
    project_root: str,
    service: str,
    client_type: str = DEFAULT_CLIENT_TYPE,
    confirm: bool = False,
    dry_run: bool = False,
    language: str = "",
) -> dict[str, Any]:
    root = project_state.validate_project_root(project_root, require_workspace=True)
    try:
        row = _service_management_row(root, client_type, service)
    except ContextForgeCatalogUnavailable as exc:
        return _catalog_unavailable_payload(root, client_type, exc)
    if row["status"] == "Enabled":
        visible = f"{row['display_name']} is already Enabled for this project."
        return {"ok": True, "status": "already_enabled", "service": _public_service_management_row(row), "assistant_visible_response": visible, "message": visible, "copy_as_complete_visible_response": True, "do_not_summarize": True}
    if not confirm:
        visible = f"Enable {row['display_name']}? This will update project configuration for this client. {_client_reload_line(client_type)} Reply approve to continue."
        return {"ok": True, "status": "enable_preview", "service": _public_service_management_row(row), "assistant_visible_response": visible, "message": visible, "copy_as_complete_visible_response": True, "do_not_summarize": True}
    if dry_run:
        visible = f"Enable {row['display_name']}? Dry run only; no project files were changed. {_client_reload_line(client_type)}"
        return {"ok": True, "status": "enable_preview", "service": _public_service_management_row(row), "dry_run": True, "assistant_visible_response": visible, "message": visible, "copy_as_complete_visible_response": True, "do_not_summarize": True}
    descriptor = row.get("descriptor") if isinstance(row.get("descriptor"), Mapping) else row
    proposal_inputs: dict[str, Any] = {"restart_project_init": True}
    if str(row.get("service_family") or "") == "serena":
        language_choice = language.strip().lower()
        if not language_choice:
            try:
                latest = _read_latest_user_message_text(str(root))
            except Exception:
                latest = ""
            language_choice = _language_input_from_text(
                latest,
                {"selected_services": [descriptor], "input_name": "language"},
            ) or ""
        if language_choice and language_choice != "defer":
            proposal_inputs["language"] = language_choice
    try:
        clean_plan = helper.propose_project_init(
            project_root=str(root),
            selected_services=[descriptor],
            client_type=client_type,
            inputs=proposal_inputs,
            contextforge_service_offerings=[descriptor],
        )
    except Exception as exc:
        return _error(exc)
    if clean_plan.get("status") == "needs_input":
        _remember_pending_project_init_input(str(root), [descriptor])
        return client_visible_project_init_payload({"ok": True, **clean_plan})
    challenge = clean_plan.get("approval_challenge") if isinstance(clean_plan.get("approval_challenge"), Mapping) else {}
    helper.restore_process_local_approval_session(project_root=str(root), plan=clean_plan)
    local_event = helper.record_local_approval_event(
        project_root=str(root),
        plan=clean_plan,
        issuer_token=helper._LOCAL_APPROVAL_ISSUER_TOKEN,
        channel="interactive_user",
    )
    approval = {
        "decision": "approve",
        "challenge_id": str(challenge.get("challenge_id") or ""),
        "plan_digest": str(clean_plan.get("plan_digest") or ""),
    }
    approved = {
        "ok": True,
        **helper.approve_project_init_plan(
            project_root=str(root),
            plan=clean_plan,
            approval=approval,
            local_approval_event_ref=str(local_event["event_ref"]),
            actor="developer",
            source_client=client_type,
            source_client_auth_strength="shared_token",
        ),
    }
    if approved.get("decision") not in {"allow", "approve"}:
        visible_error = "; ".join(str(reason) for reason in approved.get("reasons") or []) or "enable approval failed"
        return {"ok": False, "status": "enable_blocked", "service": row, "assistant_visible_response": visible_error, "message": visible_error, "approval": approved}
    _remember_plan(str(root), clean_plan)
    _remember_receipts(str(root), list(approved.get("receipts") or []))
    applied = apply_approved_project_init(str(root), clean_plan, approved.get("receipts") or [], dry_run=False)
    if not applied.get("ok"):
        return applied
    visible = f"{row['display_name']} is Enabled for this project. {_client_reload_line(client_type)}"
    return {
        "ok": True,
        "status": "enabled",
        "service": _public_service_management_row(row, status="Enabled"),
        "assistant_visible_response": visible,
        "message": visible,
        "copy_as_complete_visible_response": True,
        "do_not_summarize": True,
        "apply_result": client_visible_project_init_apply_payload(applied),
    }


def service_management_repair(
    project_root: str,
    service: str,
    client_type: str = DEFAULT_CLIENT_TYPE,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    root = project_state.validate_project_root(project_root, require_workspace=True)
    try:
        row = _service_management_row(root, client_type, service)
    except ContextForgeCatalogUnavailable as exc:
        return _catalog_unavailable_payload(root, client_type, exc)
    if not confirm:
        visible = f"Repair {row['display_name']}? This will recreate missing project configuration where possible and refresh the client service record. {_client_reload_line(client_type)} Reply approve to continue."
        return {"ok": True, "status": "repair_preview", "service": row, "assistant_visible_response": visible, "message": visible, "copy_as_complete_visible_response": True, "do_not_summarize": True}
    if row["status"] == "Enabled":
        repaired = repair_pending_project_init_config(str(root), client_type=client_type, dry_run=dry_run)
        if repaired.get("ok"):
            visible = f"{row['display_name']} repair completed. {_client_reload_line(client_type)}"
            repaired["assistant_visible_response"] = visible
            repaired["message"] = visible
            repaired["copy_as_complete_visible_response"] = True
            repaired["do_not_summarize"] = True
        return repaired
    return service_management_enable(str(root), str(row["service_binding"]), client_type=client_type, confirm=True, dry_run=dry_run)


def _layer_status(service: Mapping[str, Any], *names: str) -> str:
    layers = service.get("verification_layers")
    if not isinstance(layers, Mapping):
        return "not_claimed"
    for name in names:
        value = layers.get(name)
        if isinstance(value, Mapping):
            status = value.get("status") or value.get("state")
            if status:
                return str(status)
    return "not_claimed"


def _client_state_for_service(service: Mapping[str, Any], client_type: str) -> dict[str, Any]:
    clients = service.get("target_clients")
    if not isinstance(clients, Mapping):
        return {"status": "not_recorded"}
    state = clients.get(client_type)
    if not isinstance(state, Mapping):
        return {"status": "not_recorded"}
    keep = [
        "status",
        "validation_status",
        "reload_status",
        "surface",
        "shim",
        "virtual_server",
        "service_identity_id",
        "contextforge_server_id",
        "alias",
        "tool_prefix",
        "pi_tool_prefix",
        "global_trigger_surface",
        "target_client_visible",
        "proof_ref",
        "safe_probe_id",
        "x_proof_kind",
        "x_safe_probe_result",
        "mcp_runtime_diagnostics",
        "mcp_startup_status",
        "mcp_auth_status",
        "mcp_transport_status",
        "mcp_tool_listing_status",
        "mcp_startup_attempted",
        "mcp_evidence_ref",
        "mcp_error_class",
    ]
    return {key: state[key] for key in keep if key in state}


def project_state_readback(project_root: str, client_type: str = DEFAULT_CLIENT_TYPE) -> dict[str, Any]:
    """Read current project state and return an honest target-client readback."""

    root = project_state.validate_project_root(project_root, require_workspace=True)
    state = project_state.read_or_default(root)
    tool_report = project_tool_availability(project_root=str(root), client_type=client_type)
    services = state.get("services") if isinstance(state.get("services"), Mapping) else {}
    session_boundary = _client_session_boundary(state, client_type)
    service_readbacks: list[dict[str, Any]] = []
    mcp_runtime_diagnostics: list[dict[str, Any]] = []
    for binding_id, service_value in services.items():
        if not isinstance(service_value, Mapping):
            continue
        service = dict(service_value)
        service_binding = str(service.get("service_binding") or binding_id)
        service_family = _service_family_from_state(service_binding, service)
        tool_names = _tool_names_for_service(service_family)
        target_client_state = _client_state_for_service(service, client_type)
        projection_status = _target_client_projection_status(target_client_state, session_boundary)
        tool_policy_status = _tool_policy_status_for_service(service, tool_names)
        target_client_user_state = _target_client_user_state(target_client_state, session_boundary)
        mcp_diagnostic = _target_client_mcp_runtime_diagnostic(target_client_state, session_boundary)
        runtime_blocks_availability = _mcp_runtime_diagnostic_blocks_availability(mcp_diagnostic)
        available_to_target_client = bool(
            _projection_status_allows_target_client_availability(projection_status)
            and tool_names
            and not runtime_blocks_availability
        )
        mcp_runtime_diagnostics.append({"service_binding": service_binding, **mcp_diagnostic})
        readback_item = {
            "service_binding": service_binding,
            "service_family": service_family,
            "project_service_state": "present",
            "provision_status": str(service.get("provision_status") or "unknown"),
            "backend_instance": service.get("backend_instance"),
            "virtual_server": service.get("virtual_server"),
            "target_client_state": target_client_state,
            "target_client_projection_status": projection_status,
            "target_client_user_state": target_client_user_state,
            "tool_policy_status": tool_policy_status,
            "tool_policy_names": tool_names,
            "target_client_visibility_status": _target_client_visibility_status(target_client_state),
            "target_client_proof_status": _target_client_proof_status(target_client_state),
            "mcp_runtime_diagnostic": mcp_diagnostic,
            "available_to_target_client": available_to_target_client,
            "readiness_layers": {
                "source_ready": "present_in_project_state",
                "backend_ready": _layer_status(service, "backend", "upstream_backend", "service_backend"),
                "contextforge_ready": _layer_status(service, "contextforge", "contextforge_route", "registry", "gateway"),
                "client_visible": _layer_status(service, "target_client"),
                "mcp_runtime": mcp_diagnostic["classification"],
                "interactive_proof": "not_claimed_by_readback",
            },
        }
        if projection_status == "missing":
            readback_item["recommended_action"] = _missing_projection_action(service_binding, client_type)
        service_readbacks.append(
            readback_item
        )
    revision = project_state.state_revision(state)
    selected = [item["service_binding"] for item in service_readbacks]
    project_tool_policies = tool_report.get("project_tool_policies") if isinstance(tool_report.get("project_tool_policies"), list) else []
    missing_projection = tool_report.get("missing_target_client_projection") if isinstance(tool_report.get("missing_target_client_projection"), list) else []
    imported_tools = tool_report.get("available_tools") if isinstance(tool_report.get("available_tools"), list) else []
    skipped = tool_report.get("skipped_or_unavailable_services") if isinstance(tool_report.get("skipped_or_unavailable_services"), list) else []
    bounded_errors = [
        {
            "service_binding": str(item.get("service_binding") or ""),
            "status": str(item.get("status") or "unavailable"),
            "reason": str(item.get("reason") or "reported unavailable"),
        }
        for item in skipped
        if isinstance(item, Mapping)
    ]
    service_text = ", ".join(selected) or "none recorded"
    tools_text = (
        "; ".join(
            f"{item.get('service_binding')}: {', '.join(str(name) for name in item.get('tool_names') or [])}"
            for item in imported_tools
            if isinstance(item, Mapping)
        )
        or "none reported"
    )
    policy_text = (
        "; ".join(
            f"{item.get('service_binding')}: {', '.join(str(name) for name in item.get('tool_policy_names') or [])}"
            for item in project_tool_policies
            if isinstance(item, Mapping)
        )
        or "none recorded"
    )
    missing_projection_text = (
        "; ".join(
            f"{item.get('service_binding')}: align/import existing project service instance for {client_type}; no new project service instance without explicit approval"
            for item in missing_projection
            if isinstance(item, Mapping)
        )
        or "none recorded"
    )
    skipped_text = (
        "none reported"
        if not skipped
        else "; ".join(
            f"{item.get('service_binding')} ({item.get('status')}: {item.get('reason')})"
            for item in skipped
            if isinstance(item, Mapping)
        )
    )
    refresh_boundary = _mcp_runtime_diagnostic_note(mcp_runtime_diagnostics, session_boundary, client_type)
    target_summaries = (
        "; ".join(
            f"{item['service_binding']} projection {item['target_client_projection_status']}; "
            f"{item['target_client_user_state']}; "
            f"MCP runtime {item['mcp_runtime_diagnostic']['classification']}"
            for item in service_readbacks
        )
        or "none recorded"
    )
    return {
        "ok": True,
        "status": "project_state_readback",
        "client_type": client_type,
        "project_root": str(root),
        "state_status": state.get("status"),
        "state_revision": revision,
        "selected_service_bindings": selected,
        "project_tool_policies": project_tool_policies,
        "imported_tools": imported_tools,
        "missing_target_client_projection": missing_projection,
        "skipped_or_unavailable_services": skipped,
        "bounded_errors": bounded_errors,
        "target_client_services": service_readbacks,
        "current_session_boundary": session_boundary,
        "mcp_runtime_diagnostics": mcp_runtime_diagnostics,
        "assistant_visible_response_policy": {
            "internal_status_terms_suppressed": True,
            "diagnostic_state_retained_in_structured_fields": True,
        },
        "claim_layers": {
            "source_ready": "project-state file loaded and schema revision read",
            "backend_ready": "reported only from recorded service readiness fields when present",
            "contextforge_ready": "reported only from recorded ContextForge route/readiness fields when present",
            "client_visible": "reported only from recorded target-client projection state; project tool policy alone is not target-client availability",
            "interactive_proof": "not claimed by this readback; requires a separate ordinary tool-use transcript",
        },
        "assistant_visible_response": _visible_helper_response(
            "ContextForge project state",
            [
                _visible_section(
                    "Project",
                    [
                        f"- Root: `{str(root)}`",
                        f"- Status: {state.get('status')}",
                        f"- Revision: {revision}",
                        f"- Target client: {client_type}",
                    ],
                ),
                _visible_section("Selected services", _visible_item_list(selected, empty=service_text)),
                _visible_section(
                    "Project tool policy",
                    _visible_item_list(
                        [
                            f"{item.get('service_binding')}: {', '.join(str(name) for name in item.get('tool_policy_names') or []) or 'none reported'}"
                            for item in project_tool_policies
                            if isinstance(item, Mapping)
                        ],
                        empty=policy_text,
                    ),
                ),
                _visible_section(
                    "Configured/imported tools for this client",
                    _visible_item_list(
                        [
                            f"{item.get('service_binding')}: {', '.join(str(name) for name in item.get('tool_names') or []) or 'none reported'}"
                            for item in imported_tools
                            if isinstance(item, Mapping)
                        ],
                        empty=tools_text,
                    ),
                ),
                _visible_section(
                    "Missing target-client projections",
                    _visible_item_list(
                        [
                            f"{item.get('service_binding')}: align/import existing project service instance for {client_type}; no new project service instance without explicit approval"
                            for item in missing_projection
                            if isinstance(item, Mapping)
                        ],
                        empty=missing_projection_text,
                    ),
                ),
                _visible_section(
                    "Skipped or unavailable services",
                    _visible_item_list(
                        [
                            f"{item.get('service_binding')} ({item.get('status')}: {item.get('reason')})"
                            for item in skipped
                            if isinstance(item, Mapping)
                        ],
                        empty=skipped_text,
                    ),
                ),
                _visible_section(
                    "Target-client binding state",
                    _visible_item_list(
                        [
                            f"{item['service_binding']}: projection {item['target_client_projection_status']}; "
                            f"{item['target_client_user_state']}; "
                            f"MCP runtime {item['mcp_runtime_diagnostic']['classification']}"
                            for item in service_readbacks
                        ],
                        empty=target_summaries,
                    ),
                ),
                _visible_section(
                    "Readback limits",
                    [
                        "- Client-visible tool use is not proven by this readback; target-client-visible=false states remain unproven.",
                        "- This is a read-only project-state readback; interactive proof is not claimed by this readback.",
                    ],
                ),
                _visible_section("Next step", [f"- {refresh_boundary}"]),
            ],
        ),
        "non_actions": [
            "read-only project-state readback",
            "no service selection",
            "no project-init proposal, approval, or apply",
            "no validation, tool probe, backend mutation, or registry mutation",
            "no claim of interactive proof",
            "no claim of interactive proof from local state alone",
        ],
    }


def _capability_label(service_family: str) -> str:
    labels = {
        "context7": "Context7 documentation lookup",
        "exa-search": "Exa search",
        "github": "GitHub project integration",
        "mentality": "project governance readback",
        "openzeppelin-solidity-contracts": "OpenZeppelin Solidity contracts reference",
        "playwright": "browser automation",
        "ssh-tmux": "SSH/tmux operations",
        "web-search": "web search",
        "serena": "project-scoped code navigation",
    }
    return labels.get(service_family, service_family)


def _cache_key(project_root: str) -> str:
    return str(Path(project_root).expanduser().resolve(strict=False))


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _approval_source_path() -> Path | None:
    raw = os.environ.get("CONTEXTFORGE_HELPER_APPROVAL_SOURCE_PATH", "").strip()
    return Path(raw).expanduser() if raw else None


def _read_latest_user_message_text(project_root: str) -> str:
    path = _approval_source_path()
    if path is None:
        return ""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    if not isinstance(data, dict):
        return ""
    cwd = data.get("cwd")
    if cwd and _cache_key(str(cwd)) != _cache_key(project_root):
        return ""
    text = data.get("text")
    return text if isinstance(text, str) else ""


def _read_latest_user_message_cwd() -> str:
    path = _approval_source_path()
    if path is None:
        return ""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    if not isinstance(data, dict):
        return ""
    cwd = data.get("cwd")
    return cwd if isinstance(cwd, str) else ""


def _continuation_project_root(project_root: str, client_type: str) -> str:
    if client_type != "opencode":
        return project_root
    supplied = str(project_root or "").strip()
    if supplied and _cache_key(supplied) != _cache_key("/"):
        return project_root
    cwd = _read_latest_user_message_cwd().strip()
    if cwd and _cache_key(cwd) != _cache_key("/"):
        return cwd
    return project_root


def _current_session_project_root(project_root: str) -> str:
    supplied = str(project_root or "").strip()
    if supplied and _cache_key(supplied) != _cache_key("/"):
        return supplied
    cwd = _read_latest_user_message_cwd().strip()
    if cwd and _cache_key(cwd) != _cache_key("/"):
        return cwd
    return os.getcwd()


def _require_latest_user_text(project_root: str, *, env_name: str, purpose: str, keywords: set[str]) -> None:
    if not _env_truthy(env_name):
        return
    text = _read_latest_user_message_text(project_root)
    lowered = text.lower()
    if any(keyword in lowered for keyword in keywords):
        return
    raise PermissionError(f"latest user message does not contain explicit {purpose} intent")


def _contains_selection_number(text: str, selection_number: int) -> bool:
    return re.search(rf"(?<!\d){selection_number}(?!\d)", text) is not None


def _latest_text_is_approval(text: str) -> bool:
    lowered = text.strip().lower()
    if _latest_text_has_approval_negation(lowered):
        return False
    return (
        lowered in {"approve", "approved", "yes approve", "i approve", "ok approve", "okay approve"}
        or lowered.startswith("approve ")
        or lowered.startswith("approved ")
    )


def _latest_text_has_approval_negation(text: str) -> bool:
    lowered = text.strip().lower()
    return bool(
        re.search(r"\b(?:do\s+not|don't|dont|not|never|no)\s+approve\b", lowered)
        or re.search(r"\bi\s+(?:do\s+not|don't|dont)\s+approve\b", lowered)
        or re.search(r"\bdecline\b", lowered)
        or re.search(r"\bdefer\b", lowered)
    )


def _latest_text_is_decline(text: str) -> bool:
    lowered = text.strip().lower()
    return lowered in {"decline", "declined", "no", "no thanks", "do not install"} or re.search(r"\bdecline\b", lowered) is not None


def _latest_text_is_defer(text: str) -> bool:
    lowered = text.strip().lower()
    return lowered in {"defer", "deferred", "later", "not now"} or re.search(r"\bdefer\b", lowered) is not None


def _selected_service_ids_from_text(text: str, capabilities: Mapping[str, Any]) -> list[str]:
    stripped = text.strip()
    if not stripped:
        return []
    lowered = stripped.lower()
    next_turn_value = capabilities.get("next_turn") if isinstance(capabilities.get("next_turn"), Mapping) else {}
    choices = next_turn_value.get("choices") if isinstance(next_turn_value.get("choices"), list) else []
    numeric_selection_text = re.fullmatch(r"[\d,\s]+", stripped) is not None
    if "all" in lowered and re.search(r"\bservices?\b", lowered):
        return [
            str(choice.get("id") or "")
            for choice in choices
            if isinstance(choice, Mapping) and choice.get("id") and str(choice.get("id")) != "none"
        ]
    selected: list[str] = []
    for choice in choices:
        if not isinstance(choice, Mapping):
            continue
        choice_id = str(choice.get("id") or "")
        if not choice_id or choice_id == "none":
            continue
        label = str(choice.get("label") or "").lower()
        number = choice.get("number")
        if (
            (numeric_selection_text and isinstance(number, int) and _contains_selection_number(stripped, number))
            or choice_id.lower() in lowered
            or (label and re.search(rf"\b{re.escape(label)}\b", lowered))
        ):
            selected.append(choice_id)
    return selected


def _is_serena_service_ref(item: Any) -> bool:
    if isinstance(item, Mapping):
        binding = str(item.get("service_binding") or "")
        family = str(item.get("service_family") or item.get("canonical_service") or item.get("codex_alias") or "")
        return binding.startswith("serena:") or family == "serena" or family.startswith("serena:")
    ref = str(item)
    return ref == "serena" or ref.startswith("serena:")


def _pending_service_refs(pending_input: Mapping[str, Any] | None) -> list[Any]:
    return [
        item
        for item in (pending_input or {}).get("selected_services") or []
        if item
    ]


def _language_input_from_text(text: str, pending_input: Mapping[str, Any] | None = None) -> str | None:
    lowered = text.strip().lower()
    if (pending_input or {}).get("input_name") == "language":
        numeric_choices = {"1": "python", "2": "typescript", "3": "defer"}
        if lowered in numeric_choices:
            return numeric_choices[lowered]
    if lowered in {"python", "typescript", "defer"}:
        return lowered
    return None


def _require_user_approval_text(project_root: str, challenge_id: str | None, plan_digest: str | None) -> None:
    if not _env_truthy("CONTEXTFORGE_HELPER_REQUIRE_USER_APPROVAL_TEXT"):
        return
    text = _read_latest_user_message_text(project_root)
    lowered = text.strip().lower()
    approved = (
        _latest_text_is_approval(text)
        or (bool(challenge_id) and str(challenge_id) in text)
        or (bool(plan_digest) and str(plan_digest) in text)
    )
    if _latest_text_has_approval_negation(lowered) or not approved:
        raise PermissionError(
            "latest user message does not contain explicit approval text; "
            "ask the user to approve or decline the listed project-local effects before calling approval tools"
        )


def _runtime_apply_identity_terms(*values: str) -> set[str]:
    terms: set[str] = set()
    for value in values:
        text = str(value or "").strip().lower()
        if not text:
            continue
        terms.add(text)
        if ":" in text:
            terms.add(text.split(":", 1)[0])
        if "/" in text:
            tail = text.rstrip("/").rsplit("/", 1)[-1]
            if tail:
                terms.add(tail)
        if text.startswith("mcp-server-"):
            terms.add(text.removeprefix("mcp-server-"))
    return {term for term in terms if len(term) >= 3}


def _text_contains_runtime_identity(text: str, identity_terms: set[str]) -> bool:
    for term in identity_terms:
        if re.search(rf"(?<![a-z0-9_-]){re.escape(term)}(?![a-z0-9_-])", text):
            return True
    return False


def _runtime_apply_exact_approval_phrase(
    *,
    service_binding: str = "",
    runtime_apply_package_id: str = "",
    executor_surface: str = "",
) -> str:
    binding = service_binding or "the named service"
    surface = executor_surface or "the recorded ContextForge runtime/apply executor surface"
    package_id = runtime_apply_package_id or "the recorded runtime/apply package id"
    return (
        f"Approve runtime/apply for {binding} using executor surface "
        f"{surface} and runtime_apply_package_id {package_id}."
    )


def _require_runtime_apply_approval_text(
    project_root: str,
    *,
    candidate_service: str = "",
    service_binding: str = "",
    source_path: str = "",
    backend_package: str = "",
    runtime_apply_package_id: str = "",
    executor_surface: str = "",
) -> None:
    if _env_truthy("CONTEXTFORGE_HELPER_ALLOW_UNGATED_RUNTIME_APPLY_PACKAGE"):
        return
    if _approval_source_path() is None:
        raise PermissionError(
            "runtime/apply package tool requires latest-user approval evidence; "
            "configure CONTEXTFORGE_HELPER_APPROVAL_SOURCE_PATH or use the pure helper CLI package builder for non-client planning"
        )
    text = _read_latest_user_message_text(project_root)
    lowered = text.strip().lower()
    approval_terms = {"approve", "approved", "proceed", "continue"}
    has_approval = _latest_text_is_approval(text) or any(term in lowered for term in approval_terms)
    has_runtime_intent = bool(
        re.search(r"\b(?:runtime|apply|implement|implementation|register|registration|install|start|execute)\b", lowered)
    )
    exact_phrase = _runtime_apply_exact_approval_phrase(
        service_binding=service_binding,
        runtime_apply_package_id=runtime_apply_package_id,
        executor_surface=executor_surface,
    )
    if _latest_text_has_approval_negation(lowered) or not (has_approval and has_runtime_intent):
        raise PermissionError(
            "latest user message does not contain explicit runtime/apply approval intent; "
            "ask the user to approve or decline the runtime/apply package before calling this tool. "
            f"Exact approval phrase: {exact_phrase}"
        )
    if runtime_apply_package_id and runtime_apply_package_id.lower() not in lowered:
        raise PermissionError(
            "latest user message does not identify the exact runtime/apply package id being executed; "
            "ask the user to approve runtime/apply for this exact recorded package before calling this tool. "
            f"Exact approval phrase: {exact_phrase}"
        )
    identity_terms = _runtime_apply_identity_terms(candidate_service, service_binding, source_path, backend_package)
    if identity_terms and not _text_contains_runtime_identity(lowered, identity_terms):
        raise PermissionError(
            "latest user message does not identify the service being approved for runtime/apply; "
            "ask the user to approve runtime/apply for the named service before calling this tool. "
            f"Exact approval phrase: {exact_phrase}"
        )


def _remember_plan(project_root: str, plan: dict[str, Any]) -> dict[str, Any]:
    _CACHED_PLANS[_cache_key(project_root)] = dict(plan)
    current = _read_durable_cache(project_root)
    current.pop("pending_input", None)
    _write_durable_cache(project_root, {**current, "plan": dict(plan)})
    return plan


def _remember_pending_project_init_input(project_root: str, selected_services: list[Any]) -> None:
    normalized: list[Any] = []
    for item in selected_services:
        if isinstance(item, Mapping):
            normalized.append(dict(item))
            continue
        else:
            ref = str(item)
        if ref:
            normalized.append(ref)
    current = _read_durable_cache(project_root)
    _write_durable_cache(
        project_root,
        {
            **current,
            "pending_input": {
                "selected_services": normalized,
                "input_name": "language",
            },
        },
    )


def _clear_pending_project_init_input(project_root: str) -> None:
    current = _read_durable_cache(project_root)
    if "pending_input" not in current:
        return
    current.pop("pending_input", None)
    _write_durable_cache(project_root, current)


def _pending_project_init_input(project_root: str) -> dict[str, Any] | None:
    pending = _read_durable_cache(project_root).get("pending_input")
    return dict(pending) if isinstance(pending, dict) else None


def _remember_receipts(project_root: str, receipts: list[dict[str, Any]]) -> None:
    _CACHED_RECEIPTS[_cache_key(project_root)] = list(receipts)
    current = _read_durable_cache(project_root)
    _write_durable_cache(project_root, {**current, "receipts": list(receipts)})


def _receipts_match_current_plan(receipts: Any, plan: dict[str, Any]) -> bool:
    if not isinstance(receipts, list):
        return False
    plan_id = str(plan.get("plan_id") or "")
    plan_digest = str(plan.get("plan_digest") or "")
    required = {str(item) for item in plan.get("required_consent_classes") or []}
    if not plan_id or not plan_digest:
        return False
    if not required:
        return receipts == []
    if len(receipts) != len(required):
        return False
    observed: set[str] = set()
    for receipt in receipts:
        if not isinstance(receipt, dict):
            return False
        if str(receipt.get("plan_id") or "") != plan_id:
            return False
        if str(receipt.get("plan_digest") or "") != plan_digest:
            return False
        if not str(receipt.get("plan_presented_digest") or ""):
            return False
        observed.add(str(receipt.get("consent_class") or ""))
    return observed == required


def _matching_cached_receipts(project_root: str, plan: dict[str, Any]) -> list[dict[str, Any]] | None:
    cached_receipts = _CACHED_RECEIPTS.get(_cache_key(project_root))
    if _receipts_match_current_plan(cached_receipts, plan):
        return list(cached_receipts or [])
    durable = _read_durable_cache(project_root)
    durable_receipts = durable.get("receipts") if isinstance(durable.get("receipts"), list) else None
    if _receipts_match_current_plan(durable_receipts, plan):
        remembered = list(durable_receipts or [])
        _CACHED_RECEIPTS[_cache_key(project_root)] = remembered
        return remembered
    return None


def _remember_recovery_plan(project_root: str, plan: dict[str, Any]) -> dict[str, Any]:
    _CACHED_RECOVERY_PLANS[_cache_key(project_root)] = dict(plan)
    current = _read_durable_cache(project_root)
    _write_durable_cache(project_root, {**current, "recovery_plan": dict(plan)})
    return plan


def _remember_recovery_receipts(project_root: str, receipts: list[dict[str, Any]]) -> None:
    _CACHED_RECOVERY_RECEIPTS[_cache_key(project_root)] = list(receipts)
    current = _read_durable_cache(project_root)
    _write_durable_cache(project_root, {**current, "recovery_receipts": list(receipts)})


def _remember_project_init_result(project_root: str, result: dict[str, Any]) -> None:
    clean = _unwrap_tool_envelope(result)
    recovery_plan = clean.get("recovery_plan") if isinstance(clean.get("recovery_plan"), dict) else None
    if recovery_plan:
        _remember_recovery_plan(project_root, recovery_plan)
    if clean.get("workflow") == "project_init" and clean.get("plan_id"):
        _remember_plan(project_root, clean)


def _clear_durable_recovery_cache(project_root: str, *, keep_plan: bool = False) -> None:
    current = _read_durable_cache(project_root)
    if not current:
        return
    if not keep_plan:
        current.pop("recovery_plan", None)
    current.pop("recovery_receipts", None)
    _write_durable_cache(project_root, current)


def _matching_cached_plan(project_root: str, challenge_id: str | None, plan_digest: str | None) -> dict[str, Any]:
    plan = _CACHED_PLANS.get(_cache_key(project_root))
    if not plan:
        durable = _read_durable_cache(project_root)
        durable_plan = durable.get("plan") if isinstance(durable.get("plan"), dict) else None
        if durable_plan:
            plan = dict(durable_plan)
            _CACHED_PLANS[_cache_key(project_root)] = plan
    if not plan:
        raise ValueError("no cached project-init plan is available; call propose_project_init or cf_project_init_propose first")
    challenge = plan.get("approval_challenge") if isinstance(plan.get("approval_challenge"), dict) else {}
    if challenge_id and challenge.get("challenge_id") != challenge_id:
        raise ValueError("cached project-init plan challenge id does not match")
    if plan_digest and plan.get("plan_digest") != plan_digest:
        raise ValueError("cached project-init plan digest does not match")
    return plan


def _cached_project_init_plan_or_none(project_root: str) -> dict[str, Any] | None:
    try:
        return _matching_cached_plan(project_root, None, None)
    except Exception:
        return None


def _matching_cached_recovery_plan(project_root: str, challenge_id: str | None, plan_digest: str | None) -> dict[str, Any]:
    plan = _CACHED_RECOVERY_PLANS.get(_cache_key(project_root))
    if not plan:
        durable = _read_durable_cache(project_root)
        durable_plan = durable.get("recovery_plan") if isinstance(durable.get("recovery_plan"), dict) else None
        if durable_plan:
            plan = dict(durable_plan)
            _CACHED_RECOVERY_PLANS[_cache_key(project_root)] = plan
    if not plan:
        raise ValueError("no cached project-init recovery plan is available; call cf_project_init_recovery_propose first")
    challenge = plan.get("approval_challenge") if isinstance(plan.get("approval_challenge"), dict) else {}
    if challenge_id and challenge.get("challenge_id") != challenge_id:
        raise ValueError("cached project-init recovery plan challenge id does not match")
    if plan_digest and plan.get("plan_digest") != plan_digest:
        raise ValueError("cached project-init recovery plan digest does not match")
    return plan


def _cached_recovery_continuation_plan(project_root: str, activation_plan: dict[str, Any]) -> dict[str, Any] | None:
    plan = _CACHED_RECOVERY_PLANS.get(_cache_key(project_root))
    if not plan:
        durable = _read_durable_cache(project_root)
        durable_plan = durable.get("recovery_plan") if isinstance(durable.get("recovery_plan"), dict) else None
        if durable_plan:
            plan = dict(durable_plan)
            _CACHED_RECOVERY_PLANS[_cache_key(project_root)] = plan
    if not isinstance(plan, dict):
        return None
    source = plan.get("source_activation_plan") if isinstance(plan.get("source_activation_plan"), dict) else {}
    if source.get("plan_id") != activation_plan.get("plan_id") or source.get("plan_digest") != activation_plan.get("plan_digest"):
        return None
    return plan


@server.tool()
def get_project_context(project_root: str, client_type: str = DEFAULT_CLIENT_TYPE) -> dict[str, Any]:
    """Return helper readiness and local project-root attestation."""
    try:
        result = {"ok": True, **helper.helper_readiness(project_root=project_root, client_type=client_type)}
        return client_visible_project_init_payload(result)
    except Exception as exc:
        return _error(exc)


@server.tool()
def cf_project_init_get_context(project_root: str, client_type: str = DEFAULT_CLIENT_TYPE) -> dict[str, Any]:
    """Alias for get_project_context with the project-init tool id."""
    return get_project_context(project_root=project_root, client_type=client_type)


@server.tool()
def get_project_tool_availability(project_root: str, client_type: str = DEFAULT_CLIENT_TYPE) -> dict[str, Any]:
    """Return a read-only initialized-project report; copy assistant_visible_response exactly."""
    try:
        return client_visible_project_tool_availability_payload(
            project_tool_availability(project_root=project_root, client_type=client_type)
        )
    except Exception as exc:
        return _error(exc)


@server.tool()
def cf_project_tool_availability(project_root: str, client_type: str = DEFAULT_CLIENT_TYPE) -> dict[str, Any]:
    """Normal-use availability report; copy assistant_visible_response exactly as the complete reply."""
    return get_project_tool_availability(project_root=project_root, client_type=client_type)


@server.tool()
def get_project_capability_summary(project_root: str, client_type: str = DEFAULT_CLIENT_TYPE) -> dict[str, Any]:
    """Return a read-only initialized-project capability summary; copy assistant_visible_response exactly."""
    try:
        return client_visible_project_capability_summary_payload(
            project_capability_summary(project_root=project_root, client_type=client_type)
        )
    except Exception as exc:
        return _error(exc)


@server.tool()
def cf_project_capability_summary(project_root: str, client_type: str = DEFAULT_CLIENT_TYPE) -> dict[str, Any]:
    """Normal-use capability summary; copy assistant_visible_response exactly as the complete reply."""
    return get_project_capability_summary(project_root=project_root, client_type=client_type)


@server.tool()
def get_project_state_readback(project_root: str, client_type: str = DEFAULT_CLIENT_TYPE) -> dict[str, Any]:
    """Return a read-only project-state readback; copy assistant_visible_response exactly."""
    try:
        return client_visible_project_state_readback_payload(
            project_state_readback(project_root=project_root, client_type=client_type)
        )
    except Exception as exc:
        return _error(exc)


@server.tool()
def cf_project_state_readback(project_root: str, client_type: str = DEFAULT_CLIENT_TYPE) -> dict[str, Any]:
    """Normal-use project-state readback; copy assistant_visible_response exactly as the complete reply."""
    return get_project_state_readback(project_root=project_root, client_type=client_type)


def cf_project_service_onboarding_plan(
    project_root: str,
    candidate_service: str = "",
    operator_goal: str = "",
    source_path: str = "",
    backend_package: str = "",
    backend_command: str = "",
    backend_args: list[str] | None = None,
    transport_type: str = "",
    localization_type: str = "",
    functional_type: str = "",
    state_type: str = "",
    credential_boundary: str = "",
    credential_required: bool | None = None,
    approval_type: str = "",
    expected_tools: list[str] | None = None,
    package_registry_type: str = "",
    package_version: str = "",
    runtime_hint: str = "",
    npm_package_confirmed: bool = False,
    environment_variables_reviewed: bool = False,
    package_arguments_reviewed: bool = False,
    environment_variables: list[Any] | None = None,
    package_arguments: list[Any] | None = None,
    required_secret_names: list[str] | None = None,
    tool_schemas: dict[str, Any] | None = None,
    tool_schema_records: list[Any] | None = None,
    tool_schema_summaries: Any = None,
    prompt_library: dict[str, Any] | None = None,
    issue: str = "",
    session_id: str = "",
    client_type: str = DEFAULT_CLIENT_TYPE,
) -> dict[str, Any]:
    """Build a no-mutation source-only onboarding plan for an uncataloged MCP service."""
    try:
        root = _continuation_project_root(project_root, client_type)
        result = service_onboarding_surfaces.build_service_onboarding_plan(
            root,
            {
                "candidate_service": candidate_service,
                "operator_goal": operator_goal,
                "source_path": source_path,
                "backend_package": backend_package,
                "backend_command": backend_command,
                "backend_args": backend_args or [],
                "transport_type": transport_type,
                "localization_type": localization_type,
                "functional_type": functional_type,
                "state_type": state_type,
                "credential_boundary": credential_boundary,
                "credential_required": credential_required,
                "approval_type": approval_type,
                "expected_tools": expected_tools or [],
                "package_registry_type": package_registry_type,
                "package_version": package_version,
                "runtime_hint": runtime_hint,
                "npm_package_confirmed": npm_package_confirmed,
                "environment_variables_reviewed": environment_variables_reviewed,
                "package_arguments_reviewed": package_arguments_reviewed,
                "environment_variables": environment_variables or [],
                "package_arguments": package_arguments or [],
                "required_secret_names": required_secret_names or [],
                "tool_schemas": tool_schemas or {},
                "tool_schema_records": tool_schema_records or [],
                "tool_schema_summaries": tool_schema_summaries or [],
                "prompt_library": prompt_library or {},
                "issue": issue,
                "session_id": session_id,
            },
        )
        return client_visible_service_onboarding_payload({"ok": True, **result})
    except Exception as exc:
        return _error(exc)


def build_service_onboarding_plan(
    project_root: str,
    candidate_service: str = "",
    operator_goal: str = "",
    source_path: str = "",
    backend_package: str = "",
    backend_command: str = "",
    backend_args: list[str] | None = None,
    transport_type: str = "",
    localization_type: str = "",
    functional_type: str = "",
    state_type: str = "",
    credential_boundary: str = "",
    credential_required: bool | None = None,
    approval_type: str = "",
    expected_tools: list[str] | None = None,
    package_registry_type: str = "",
    package_version: str = "",
    runtime_hint: str = "",
    npm_package_confirmed: bool = False,
    environment_variables_reviewed: bool = False,
    package_arguments_reviewed: bool = False,
    environment_variables: list[Any] | None = None,
    package_arguments: list[Any] | None = None,
    required_secret_names: list[str] | None = None,
    tool_schemas: dict[str, Any] | None = None,
    tool_schema_records: list[Any] | None = None,
    tool_schema_summaries: Any = None,
    prompt_library: dict[str, Any] | None = None,
    issue: str = "",
    session_id: str = "",
    client_type: str = DEFAULT_CLIENT_TYPE,
) -> dict[str, Any]:
    """Alias for cf_project_service_onboarding_plan."""
    return cf_project_service_onboarding_plan(
        project_root=project_root,
        candidate_service=candidate_service,
        operator_goal=operator_goal,
        source_path=source_path,
        backend_package=backend_package,
        backend_command=backend_command,
        backend_args=backend_args,
        transport_type=transport_type,
        localization_type=localization_type,
        functional_type=functional_type,
        state_type=state_type,
        credential_boundary=credential_boundary,
        credential_required=credential_required,
        approval_type=approval_type,
        expected_tools=expected_tools,
        package_registry_type=package_registry_type,
        package_version=package_version,
        runtime_hint=runtime_hint,
        npm_package_confirmed=npm_package_confirmed,
        environment_variables_reviewed=environment_variables_reviewed,
        package_arguments_reviewed=package_arguments_reviewed,
        environment_variables=environment_variables,
        package_arguments=package_arguments,
        required_secret_names=required_secret_names,
        tool_schemas=tool_schemas,
        tool_schema_records=tool_schema_records,
        tool_schema_summaries=tool_schema_summaries,
        prompt_library=prompt_library,
        issue=issue,
        session_id=session_id,
        client_type=client_type,
    )


def cf_project_service_onboarding_research_source(
    project_root: str,
    source_path: str = "",
    client_type: str = DEFAULT_CLIENT_TYPE,
) -> dict[str, Any]:
    """Fetch read-only file-level source evidence for an uncataloged MCP service lead."""
    try:
        root = _continuation_project_root(project_root, client_type)
        result = service_onboarding_surfaces.research_service_onboarding_source(
            root,
            {
                "source_path": source_path,
                "client_type": client_type,
            },
        )
        return client_visible_service_onboarding_payload({"ok": True, **result})
    except Exception as exc:
        return _error(exc)


def research_service_onboarding_source(
    project_root: str,
    source_path: str = "",
    client_type: str = DEFAULT_CLIENT_TYPE,
) -> dict[str, Any]:
    """Alias for cf_project_service_onboarding_research_source."""
    return cf_project_service_onboarding_research_source(
        project_root=project_root,
        source_path=source_path,
        client_type=client_type,
    )


def cf_project_service_onboarding_continue(
    project_root: str = "",
    projectRoot: str = "",
    candidate_service: str = "",
    candidateService: str = "",
    operator_goal: str = "",
    operatorGoal: str = "",
    source_path: str = "",
    sourcePath: str = "",
    backend_package: str = "",
    backendPackage: str = "",
    backend_command: str = "",
    backendCommand: str = "",
    command: str = "",
    backendArgs: list[str] | None = None,
    transport_type: str = "",
    transportType: str = "",
    localization_type: str = "",
    localizationType: str = "",
    functional_type: str = "",
    functionalType: str = "",
    state_type: str = "",
    stateType: str = "",
    credential_boundary: str = "",
    credentialBoundary: str = "",
    approval_type: str = "",
    approvalType: str = "",
    expected_tools: list[str] | None = None,
    expectedTools: list[str] | None = None,
    package_registry_type: str = "",
    packageRegistryType: str = "",
    package_version: str = "",
    packageVersion: str = "",
    runtime_hint: str = "",
    runtimeHint: str = "",
    npm_package_confirmed: bool = False,
    npmPackageConfirmed: bool = False,
    environment_variables_reviewed: bool = False,
    environmentVariablesReviewed: bool = False,
    package_arguments_reviewed: bool = False,
    packageArgumentsReviewed: bool = False,
    environment_variables: list[Any] | None = None,
    environmentVariables: list[Any] | None = None,
    package_arguments: list[Any] | None = None,
    packageArguments: list[Any] | None = None,
    required_secret_names: list[str] | None = None,
    requiredSecretNames: list[str] | None = None,
    tool_schemas: dict[str, Any] | None = None,
    toolSchemas: dict[str, Any] | None = None,
    tool_schema_records: list[Any] | None = None,
    toolSchemaRecords: list[Any] | None = None,
    tool_schema_summaries: Any = None,
    toolSchemaSummaries: Any = None,
    prompt_library: dict[str, Any] | None = None,
    promptLibrary: dict[str, Any] | None = None,
    structured_payload_path: str = "",
    structuredPayloadPath: str = "",
    issue: str = "",
    issueNumber: str = "",
    client_type: str = DEFAULT_CLIENT_TYPE,
    clientType: str = "",
) -> dict[str, Any]:
    """Build a non-mutating service-management continuation package for an approved uncataloged service."""
    try:
        project_root = project_root or projectRoot
        client_type = client_type or clientType or DEFAULT_CLIENT_TYPE
        candidate_service = candidate_service or candidateService
        operator_goal = operator_goal or operatorGoal
        source_path = source_path or sourcePath
        backend_package = backend_package or backendPackage
        backend_command = backend_command or backendCommand or command
        transport_type = transport_type or transportType
        localization_type = localization_type or localizationType
        functional_type = functional_type or functionalType
        state_type = state_type or stateType
        credential_boundary = credential_boundary or credentialBoundary
        approval_type = approval_type or approvalType
        expected_tools = expected_tools or expectedTools
        package_registry_type = package_registry_type or packageRegistryType
        package_version = package_version or packageVersion
        runtime_hint = runtime_hint or runtimeHint
        npm_package_confirmed = npm_package_confirmed or npmPackageConfirmed
        environment_variables_reviewed = environment_variables_reviewed or environmentVariablesReviewed
        package_arguments_reviewed = package_arguments_reviewed or packageArgumentsReviewed
        environment_variables = environment_variables or environmentVariables
        package_arguments = package_arguments or packageArguments
        backend_args = backendArgs or []
        required_secret_names = required_secret_names or requiredSecretNames
        tool_schemas = tool_schemas or toolSchemas
        tool_schema_records = tool_schema_records or toolSchemaRecords
        tool_schema_summaries = tool_schema_summaries or toolSchemaSummaries
        prompt_library = prompt_library or promptLibrary
        issue = issue or issueNumber
        root = _continuation_project_root(project_root, client_type)
        payload = {
            "candidate_service": candidate_service,
            "operator_goal": operator_goal,
            "source_path": source_path,
            "backend_package": backend_package,
            "backend_command": backend_command,
            "backend_args": backend_args,
            "transport_type": transport_type,
            "localization_type": localization_type,
            "functional_type": functional_type,
            "state_type": state_type,
            "credential_boundary": credential_boundary,
            "approval_type": approval_type,
            "expected_tools": expected_tools or [],
            "package_registry_type": package_registry_type,
            "package_version": package_version,
            "runtime_hint": runtime_hint,
            "npm_package_confirmed": npm_package_confirmed,
            "environment_variables_reviewed": environment_variables_reviewed,
            "package_arguments_reviewed": package_arguments_reviewed,
            "environment_variables": environment_variables or [],
            "package_arguments": package_arguments or [],
            "required_secret_names": required_secret_names or [],
            "tool_schemas": tool_schemas or {},
            "tool_schema_records": tool_schema_records or [],
            "tool_schema_summaries": tool_schema_summaries or [],
            "prompt_library": prompt_library or {},
            "structured_payload_path": structured_payload_path or structuredPayloadPath,
            "issue": issue,
        }
        result = service_onboarding_surfaces.build_service_onboarding_continuation(root, payload)
        return client_visible_service_onboarding_payload({"ok": True, **result})
    except Exception as exc:
        return _error(exc)


def build_service_onboarding_continuation(
    project_root: str,
    candidate_service: str = "",
    operator_goal: str = "",
    source_path: str = "",
    backend_package: str = "",
    backend_command: str = "",
    transport_type: str = "",
    localization_type: str = "",
    functional_type: str = "",
    state_type: str = "",
    credential_boundary: str = "",
    approval_type: str = "",
    expected_tools: list[str] | None = None,
    package_registry_type: str = "",
    package_version: str = "",
    runtime_hint: str = "",
    npm_package_confirmed: bool = False,
    environment_variables_reviewed: bool = False,
    package_arguments_reviewed: bool = False,
    environment_variables: list[Any] | None = None,
    package_arguments: list[Any] | None = None,
    required_secret_names: list[str] | None = None,
    tool_schemas: dict[str, Any] | None = None,
    tool_schema_records: list[Any] | None = None,
    tool_schema_summaries: Any = None,
    prompt_library: dict[str, Any] | None = None,
    issue: str = "",
    client_type: str = DEFAULT_CLIENT_TYPE,
) -> dict[str, Any]:
    """Alias for cf_project_service_onboarding_continue."""
    return cf_project_service_onboarding_continue(
        project_root=project_root,
        candidate_service=candidate_service,
        operator_goal=operator_goal,
        source_path=source_path,
        backend_package=backend_package,
        backend_command=backend_command,
        transport_type=transport_type,
        localization_type=localization_type,
        functional_type=functional_type,
        state_type=state_type,
        credential_boundary=credential_boundary,
        approval_type=approval_type,
        expected_tools=expected_tools,
        package_registry_type=package_registry_type,
        package_version=package_version,
        runtime_hint=runtime_hint,
        npm_package_confirmed=npm_package_confirmed,
        environment_variables_reviewed=environment_variables_reviewed,
        package_arguments_reviewed=package_arguments_reviewed,
        environment_variables=environment_variables,
        package_arguments=package_arguments,
        required_secret_names=required_secret_names,
        tool_schemas=tool_schemas,
        tool_schema_records=tool_schema_records,
        tool_schema_summaries=tool_schema_summaries,
        prompt_library=prompt_library,
        issue=issue,
        client_type=client_type,
    )


def build_service_onboarding_continue(
    project_root: str,
    candidate_service: str = "",
    operator_goal: str = "",
    source_path: str = "",
    backend_package: str = "",
    backend_command: str = "",
    transport_type: str = "",
    localization_type: str = "",
    functional_type: str = "",
    state_type: str = "",
    credential_boundary: str = "",
    approval_type: str = "",
    expected_tools: list[str] | None = None,
    package_registry_type: str = "",
    package_version: str = "",
    runtime_hint: str = "",
    npm_package_confirmed: bool = False,
    environment_variables_reviewed: bool = False,
    package_arguments_reviewed: bool = False,
    environment_variables: list[Any] | None = None,
    package_arguments: list[Any] | None = None,
    required_secret_names: list[str] | None = None,
    tool_schemas: dict[str, Any] | None = None,
    tool_schema_records: list[Any] | None = None,
    tool_schema_summaries: Any = None,
    prompt_library: dict[str, Any] | None = None,
    issue: str = "",
    client_type: str = DEFAULT_CLIENT_TYPE,
) -> dict[str, Any]:
    """Natural alias for cf_project_service_onboarding_continue."""
    return cf_project_service_onboarding_continue(
        project_root=project_root,
        candidate_service=candidate_service,
        operator_goal=operator_goal,
        source_path=source_path,
        backend_package=backend_package,
        backend_command=backend_command,
        transport_type=transport_type,
        localization_type=localization_type,
        functional_type=functional_type,
        state_type=state_type,
        credential_boundary=credential_boundary,
        approval_type=approval_type,
        expected_tools=expected_tools,
        package_registry_type=package_registry_type,
        package_version=package_version,
        runtime_hint=runtime_hint,
        npm_package_confirmed=npm_package_confirmed,
        environment_variables_reviewed=environment_variables_reviewed,
        package_arguments_reviewed=package_arguments_reviewed,
        environment_variables=environment_variables,
        package_arguments=package_arguments,
        required_secret_names=required_secret_names,
        tool_schemas=tool_schemas,
        tool_schema_records=tool_schema_records,
        tool_schema_summaries=tool_schema_summaries,
        prompt_library=prompt_library,
        issue=issue,
        client_type=client_type,
    )


def cf_project_service_onboarding_runtime_draft(
    project_root: str = "",
    projectRoot: str = "",
    runtime_apply_draft_id: str = "",
    runtimeApplyDraftId: str = "",
    draft_id: str = "",
    draftId: str = "",
    candidate_service: str = "",
    candidateService: str = "",
    operator_goal: str = "",
    operatorGoal: str = "",
    source_path: str = "",
    sourcePath: str = "",
    service_binding: str = "",
    serviceBinding: str = "",
    backend_package: str = "",
    backendPackage: str = "",
    backend_command: str = "",
    backendCommand: str = "",
    command: str = "",
    backend_args: list[str] | None = None,
    backendArgs: list[str] | None = None,
    transport_type: str = "",
    transportType: str = "",
    localization_type: str = "",
    localizationType: str = "",
    functional_type: str = "",
    functionalType: str = "",
    state_type: str = "",
    stateType: str = "",
    credential_boundary: str = "",
    credentialBoundary: str = "",
    approval_type: str = "",
    approvalType: str = "",
    expected_tools: list[str] | None = None,
    expectedTools: list[str] | None = None,
    package_registry_type: str = "",
    packageRegistryType: str = "",
    package_version: str = "",
    packageVersion: str = "",
    runtime_hint: str = "",
    runtimeHint: str = "",
    npm_package_confirmed: bool = False,
    npmPackageConfirmed: bool = False,
    environment_variables_reviewed: bool = False,
    environmentVariablesReviewed: bool = False,
    package_arguments_reviewed: bool = False,
    packageArgumentsReviewed: bool = False,
    environment_variables: list[Any] | None = None,
    environmentVariables: list[Any] | None = None,
    package_arguments: list[Any] | None = None,
    packageArguments: list[Any] | None = None,
    required_secret_names: list[str] | None = None,
    requiredSecretNames: list[str] | None = None,
    tool_schemas: dict[str, Any] | None = None,
    toolSchemas: dict[str, Any] | None = None,
    tool_schema_records: list[Any] | None = None,
    toolSchemaRecords: list[Any] | None = None,
    tool_schema_summaries: Any = None,
    toolSchemaSummaries: Any = None,
    prompt_library: dict[str, Any] | None = None,
    promptLibrary: dict[str, Any] | None = None,
    structured_payload_path: str = "",
    structuredPayloadPath: str = "",
    issue: str = "",
    issueNumber: str = "",
    client_type: str = DEFAULT_CLIENT_TYPE,
    clientType: str = "",
) -> dict[str, Any]:
    """Create or update a non-mutating runtime/apply draft one bounded slice at a time."""
    try:
        project_root = project_root or projectRoot
        client_type = client_type or clientType or DEFAULT_CLIENT_TYPE
        root = _continuation_project_root(project_root, client_type)
        payload = {
            "runtime_apply_draft_id": runtime_apply_draft_id or runtimeApplyDraftId or draft_id or draftId,
            "candidate_service": candidate_service or candidateService,
            "operator_goal": operator_goal or operatorGoal,
            "source_path": source_path or sourcePath,
            "service_binding": service_binding or serviceBinding,
            "backend_package": backend_package or backendPackage,
            "backend_command": backend_command or backendCommand or command,
            "backend_args": backend_args or backendArgs or [],
            "transport_type": transport_type or transportType,
            "localization_type": localization_type or localizationType,
            "functional_type": functional_type or functionalType,
            "state_type": state_type or stateType,
            "credential_boundary": credential_boundary or credentialBoundary,
            "approval_type": approval_type or approvalType,
            "expected_tools": expected_tools or expectedTools or [],
            "package_registry_type": package_registry_type or packageRegistryType,
            "package_version": package_version or packageVersion,
            "runtime_hint": runtime_hint or runtimeHint,
            "npm_package_confirmed": npm_package_confirmed or npmPackageConfirmed,
            "environment_variables_reviewed": environment_variables_reviewed or environmentVariablesReviewed,
            "package_arguments_reviewed": package_arguments_reviewed or packageArgumentsReviewed,
            "environment_variables": environment_variables or environmentVariables or [],
            "package_arguments": package_arguments or packageArguments or [],
            "required_secret_names": required_secret_names or requiredSecretNames or [],
            "tool_schemas": tool_schemas or toolSchemas or {},
            "tool_schema_records": tool_schema_records or toolSchemaRecords or [],
            "tool_schema_summaries": tool_schema_summaries or toolSchemaSummaries or [],
            "prompt_library": prompt_library or promptLibrary or {},
            "structured_payload_path": structured_payload_path or structuredPayloadPath,
            "issue": issue or issueNumber,
        }
        result = service_onboarding_surfaces.runtime_apply_draft_status(root, payload)
        return client_visible_service_onboarding_payload({"ok": True, **result})
    except Exception as exc:
        return _error(exc)


def cf_project_service_onboarding_runtime_apply(
    project_root: str = "",
    projectRoot: str = "",
    candidate_service: str = "",
    candidateService: str = "",
    operator_goal: str = "",
    operatorGoal: str = "",
    source_path: str = "",
    sourcePath: str = "",
    service_binding: str = "",
    serviceBinding: str = "",
    backend_package: str = "",
    backendPackage: str = "",
    backend_command: str = "",
    backendCommand: str = "",
    command: str = "",
    backend_args: list[str] | None = None,
    backendArgs: list[str] | None = None,
    transport_type: str = "",
    transportType: str = "",
    localization_type: str = "",
    localizationType: str = "",
    functional_type: str = "",
    functionalType: str = "",
    state_type: str = "",
    stateType: str = "",
    credential_boundary: str = "",
    credentialBoundary: str = "",
    approval_type: str = "",
    approvalType: str = "",
    expected_tools: list[str] | None = None,
    expectedTools: list[str] | None = None,
    package_registry_type: str = "",
    packageRegistryType: str = "",
    package_version: str = "",
    packageVersion: str = "",
    runtime_hint: str = "",
    runtimeHint: str = "",
    npm_package_confirmed: bool = False,
    npmPackageConfirmed: bool = False,
    environment_variables_reviewed: bool = False,
    environmentVariablesReviewed: bool = False,
    package_arguments_reviewed: bool = False,
    packageArgumentsReviewed: bool = False,
    environment_variables: list[Any] | None = None,
    environmentVariables: list[Any] | None = None,
    package_arguments: list[Any] | None = None,
    packageArguments: list[Any] | None = None,
    required_secret_names: list[str] | None = None,
    requiredSecretNames: list[str] | None = None,
    tool_schemas: dict[str, Any] | None = None,
    toolSchemas: dict[str, Any] | None = None,
    tool_schema_records: list[Any] | None = None,
    toolSchemaRecords: list[Any] | None = None,
    tool_schema_summaries: Any = None,
    toolSchemaSummaries: Any = None,
    prompt_library: dict[str, Any] | None = None,
    promptLibrary: dict[str, Any] | None = None,
    structured_payload_path: str = "",
    structuredPayloadPath: str = "",
    issue: str = "",
    issueNumber: str = "",
    client_type: str = DEFAULT_CLIENT_TYPE,
    clientType: str = "",
) -> dict[str, Any]:
    """Build a non-mutating runtime-apply package preview for an uncataloged service."""
    try:
        project_root = project_root or projectRoot
        client_type = client_type or clientType or DEFAULT_CLIENT_TYPE
        candidate_service = candidate_service or candidateService
        operator_goal = operator_goal or operatorGoal
        source_path = source_path or sourcePath
        service_binding = service_binding or serviceBinding
        backend_package = backend_package or backendPackage
        backend_command = backend_command or backendCommand or command
        backend_args = backend_args or backendArgs
        transport_type = transport_type or transportType
        localization_type = localization_type or localizationType
        functional_type = functional_type or functionalType
        state_type = state_type or stateType
        credential_boundary = credential_boundary or credentialBoundary
        approval_type = approval_type or approvalType
        expected_tools = expected_tools or expectedTools
        package_registry_type = package_registry_type or packageRegistryType
        package_version = package_version or packageVersion
        runtime_hint = runtime_hint or runtimeHint
        npm_package_confirmed = npm_package_confirmed or npmPackageConfirmed
        environment_variables_reviewed = environment_variables_reviewed or environmentVariablesReviewed
        package_arguments_reviewed = package_arguments_reviewed or packageArgumentsReviewed
        environment_variables = environment_variables or environmentVariables
        package_arguments = package_arguments or packageArguments
        required_secret_names = required_secret_names or requiredSecretNames
        tool_schemas = tool_schemas or toolSchemas
        tool_schema_records = tool_schema_records or toolSchemaRecords
        tool_schema_summaries = tool_schema_summaries or toolSchemaSummaries
        prompt_library = prompt_library or promptLibrary
        issue = issue or issueNumber
        root = _continuation_project_root(project_root, client_type)
        payload = service_onboarding_surfaces.merge_structured_payload_artifact(
            root,
            {
                "candidate_service": candidate_service,
                "operator_goal": operator_goal,
                "source_path": source_path,
                "service_binding": service_binding,
                "backend_package": backend_package,
                "backend_command": backend_command,
                "backend_args": backend_args or [],
                "transport_type": transport_type,
                "localization_type": localization_type,
                "functional_type": functional_type,
                "state_type": state_type,
                "credential_boundary": credential_boundary,
                "approval_type": approval_type,
                "expected_tools": expected_tools or [],
                "package_registry_type": package_registry_type,
                "package_version": package_version,
                "runtime_hint": runtime_hint,
                "npm_package_confirmed": npm_package_confirmed,
                "environment_variables_reviewed": environment_variables_reviewed,
                "package_arguments_reviewed": package_arguments_reviewed,
                "environment_variables": environment_variables or [],
                "package_arguments": package_arguments or [],
                "required_secret_names": required_secret_names or [],
                "tool_schemas": tool_schemas or {},
                "tool_schema_records": tool_schema_records or [],
                "tool_schema_summaries": tool_schema_summaries or [],
                "prompt_library": prompt_library or {},
                "structured_payload_path": structured_payload_path or structuredPayloadPath,
                "issue": issue,
            },
        )
        result = service_onboarding_surfaces.build_service_onboarding_runtime_apply_package(root, payload)
        return client_visible_service_onboarding_payload({"ok": True, **result})
    except Exception as exc:
        return _error(exc)


def cf_project_service_onboarding_runtime_execute(
    project_root: str = "",
    projectRoot: str = "",
    runtime_apply_package_id: str = "",
    runtimeApplyPackageId: str = "",
    candidate_service: str = "",
    candidateService: str = "",
    operator_goal: str = "",
    operatorGoal: str = "",
    source_path: str = "",
    sourcePath: str = "",
    service_binding: str = "",
    serviceBinding: str = "",
    backend_package: str = "",
    backendPackage: str = "",
    backend_command: str = "",
    backendCommand: str = "",
    command: str = "",
    backend_args: list[str] | None = None,
    backendArgs: list[str] | None = None,
    transport_type: str = "",
    transportType: str = "",
    localization_type: str = "",
    localizationType: str = "",
    functional_type: str = "",
    functionalType: str = "",
    state_type: str = "",
    stateType: str = "",
    credential_boundary: str = "",
    credentialBoundary: str = "",
    approval_type: str = "",
    approvalType: str = "",
    expected_tools: list[str] | None = None,
    expectedTools: list[str] | None = None,
    package_registry_type: str = "",
    packageRegistryType: str = "",
    package_version: str = "",
    packageVersion: str = "",
    runtime_hint: str = "",
    runtimeHint: str = "",
    npm_package_confirmed: bool = False,
    npmPackageConfirmed: bool = False,
    environment_variables_reviewed: bool = False,
    environmentVariablesReviewed: bool = False,
    package_arguments_reviewed: bool = False,
    packageArgumentsReviewed: bool = False,
    environment_variables: list[Any] | None = None,
    environmentVariables: list[Any] | None = None,
    package_arguments: list[Any] | None = None,
    packageArguments: list[Any] | None = None,
    required_secret_names: list[str] | None = None,
    requiredSecretNames: list[str] | None = None,
    tool_schemas: dict[str, Any] | None = None,
    toolSchemas: dict[str, Any] | None = None,
    tool_schema_records: list[Any] | None = None,
    toolSchemaRecords: list[Any] | None = None,
    tool_schema_summaries: Any = None,
    toolSchemaSummaries: Any = None,
    prompt_library: dict[str, Any] | None = None,
    promptLibrary: dict[str, Any] | None = None,
    structured_payload_path: str = "",
    structuredPayloadPath: str = "",
    issue: str = "",
    issueNumber: str = "",
    client_type: str = DEFAULT_CLIENT_TYPE,
    clientType: str = "",
) -> dict[str, Any]:
    """Apply an approved runtime package through the recorded dev ContextForge executor surface."""
    try:
        project_root = project_root or projectRoot
        client_type = client_type or clientType or DEFAULT_CLIENT_TYPE
        runtime_apply_package_id = runtime_apply_package_id or runtimeApplyPackageId
        candidate_service = candidate_service or candidateService
        operator_goal = operator_goal or operatorGoal
        source_path = source_path or sourcePath
        service_binding = service_binding or serviceBinding
        backend_package = backend_package or backendPackage
        backend_command = backend_command or backendCommand or command
        backend_args = backend_args or backendArgs
        transport_type = transport_type or transportType
        localization_type = localization_type or localizationType
        functional_type = functional_type or functionalType
        state_type = state_type or stateType
        credential_boundary = credential_boundary or credentialBoundary
        approval_type = approval_type or approvalType
        expected_tools = expected_tools or expectedTools
        package_registry_type = package_registry_type or packageRegistryType
        package_version = package_version or packageVersion
        runtime_hint = runtime_hint or runtimeHint
        npm_package_confirmed = npm_package_confirmed or npmPackageConfirmed
        environment_variables_reviewed = environment_variables_reviewed or environmentVariablesReviewed
        package_arguments_reviewed = package_arguments_reviewed or packageArgumentsReviewed
        environment_variables = environment_variables or environmentVariables
        package_arguments = package_arguments or packageArguments
        required_secret_names = required_secret_names or requiredSecretNames
        tool_schemas = tool_schemas or toolSchemas
        tool_schema_records = tool_schema_records or toolSchemaRecords
        tool_schema_summaries = tool_schema_summaries or toolSchemaSummaries
        prompt_library = prompt_library or promptLibrary
        issue = issue or issueNumber
        root = _continuation_project_root(project_root, client_type)
        approval_text = _read_latest_user_message_text(root)
        payload = service_onboarding_surfaces.merge_structured_payload_artifact(
            root,
            {
                "runtime_apply_package_id": runtime_apply_package_id,
                "candidate_service": candidate_service,
                "operator_goal": operator_goal,
                "source_path": source_path,
                "service_binding": service_binding,
                "backend_package": backend_package,
                "backend_command": backend_command,
                "backend_args": backend_args or [],
                "transport_type": transport_type,
                "localization_type": localization_type,
                "functional_type": functional_type,
                "state_type": state_type,
                "credential_boundary": credential_boundary,
                "approval_type": approval_type,
                "expected_tools": expected_tools or [],
                "package_registry_type": package_registry_type,
                "package_version": package_version,
                "runtime_hint": runtime_hint,
                "npm_package_confirmed": npm_package_confirmed,
                "environment_variables_reviewed": environment_variables_reviewed,
                "package_arguments_reviewed": package_arguments_reviewed,
                "environment_variables": environment_variables or [],
                "package_arguments": package_arguments or [],
                "required_secret_names": required_secret_names or [],
                "tool_schemas": tool_schemas or {},
                "tool_schema_records": tool_schema_records or [],
                "tool_schema_summaries": tool_schema_summaries or [],
                "prompt_library": prompt_library or {},
                "structured_payload_path": structured_payload_path or structuredPayloadPath,
                "issue": issue,
            },
        )
        runtime_apply_package_id = runtime_apply_package_id or str(payload.get("runtime_apply_package_id") or payload.get("runtimeApplyPackageId") or "")
        candidate_service = candidate_service or str(payload.get("candidate_service") or payload.get("candidateService") or "")
        service_binding = service_binding or str(payload.get("service_binding") or payload.get("serviceBinding") or "")
        source_path = source_path or str(payload.get("source_path") or payload.get("sourcePath") or "")
        backend_package = backend_package or str(payload.get("backend_package") or payload.get("backendPackage") or "")
        package_identity: Mapping[str, str] = {}
        if runtime_apply_package_id:
            package_identity = service_onboarding_surfaces.runtime_apply_package_identity(root, runtime_apply_package_id)
        _require_runtime_apply_approval_text(
            root,
            candidate_service=candidate_service or package_identity.get("candidate_service", ""),
            service_binding=service_binding or package_identity.get("service_binding", ""),
            source_path=source_path or package_identity.get("source_path", ""),
            backend_package=backend_package or package_identity.get("backend_package", ""),
            runtime_apply_package_id=runtime_apply_package_id,
            executor_surface=package_identity.get("executor_surface", ""),
        )
        result = service_onboarding_surfaces.apply_service_onboarding_runtime_package(
            root,
            {
                **payload,
                "runtime_apply_package_id": runtime_apply_package_id,
                "candidate_service": candidate_service,
                "service_binding": service_binding,
                "source_path": source_path,
                "backend_package": backend_package,
                "approval_text": approval_text,
                "require_executor_surface_approval": True,
            },
        )
        visible = str(result.get("assistant_visible_response") or result.get("message") or "").strip()
        mutation_performed = bool(result.get("mutation_performed"))
        executor_result = result.get("executor_result") if isinstance(result.get("executor_result"), Mapping) else {}
        failure_report = executor_result.get("failure_report") if isinstance(executor_result.get("failure_report"), Mapping) else {}
        return {
            "ok": mutation_performed,
            "status": result.get("status"),
            "project_root": result.get("project_root"),
            "mutation_allowed": bool(result.get("mutation_allowed")),
            "mutation_performed": mutation_performed,
            "assistant_visible_response": visible,
            "message": visible,
            "non_actions": result.get("non_actions") or [],
            "runtime_apply_package_id": result.get("runtime_apply_package_id"),
            "runtime_target": result.get("runtime_target") or {},
            "tool_names": executor_result.get("tool_names") or [],
            "failed_stage": failure_report.get("failed_stage"),
            "rollback_result": failure_report.get("rollback_result"),
            "residual_cleanup_risk": failure_report.get("residual_cleanup_risk"),
            "required_inputs": result.get("required_inputs") or [],
        }
    except Exception as exc:
        return _error(exc)


def build_service_onboarding_runtime_apply_package(
    project_root: str,
    candidate_service: str = "",
    operator_goal: str = "",
    source_path: str = "",
    service_binding: str = "",
    backend_package: str = "",
    backend_command: str = "",
    backend_args: list[str] | None = None,
    transport_type: str = "",
    localization_type: str = "",
    functional_type: str = "",
    state_type: str = "",
    credential_boundary: str = "",
    approval_type: str = "",
    expected_tools: list[str] | None = None,
    package_registry_type: str = "",
    package_version: str = "",
    runtime_hint: str = "",
    npm_package_confirmed: bool = False,
    environment_variables_reviewed: bool = False,
    package_arguments_reviewed: bool = False,
    environment_variables: list[Any] | None = None,
    package_arguments: list[Any] | None = None,
    required_secret_names: list[str] | None = None,
    tool_schemas: dict[str, Any] | None = None,
    tool_schema_records: list[Any] | None = None,
    tool_schema_summaries: Any = None,
    prompt_library: dict[str, Any] | None = None,
    structured_payload_path: str = "",
    issue: str = "",
    client_type: str = DEFAULT_CLIENT_TYPE,
) -> dict[str, Any]:
    """Alias for cf_project_service_onboarding_runtime_apply."""
    return cf_project_service_onboarding_runtime_apply(
        project_root=project_root,
        candidate_service=candidate_service,
        operator_goal=operator_goal,
        source_path=source_path,
        service_binding=service_binding,
        backend_package=backend_package,
        backend_command=backend_command,
        backend_args=backend_args,
        transport_type=transport_type,
        localization_type=localization_type,
        functional_type=functional_type,
        state_type=state_type,
        credential_boundary=credential_boundary,
        approval_type=approval_type,
        expected_tools=expected_tools,
        package_registry_type=package_registry_type,
        package_version=package_version,
        runtime_hint=runtime_hint,
        npm_package_confirmed=npm_package_confirmed,
        environment_variables_reviewed=environment_variables_reviewed,
        package_arguments_reviewed=package_arguments_reviewed,
        environment_variables=environment_variables,
        package_arguments=package_arguments,
        required_secret_names=required_secret_names,
        tool_schemas=tool_schemas,
        tool_schema_records=tool_schema_records,
        tool_schema_summaries=tool_schema_summaries,
        prompt_library=prompt_library,
        structured_payload_path=structured_payload_path,
        issue=issue,
        client_type=client_type,
    )


def build_service_onboarding_runtime_apply(
    project_root: str,
    candidate_service: str = "",
    operator_goal: str = "",
    source_path: str = "",
    service_binding: str = "",
    backend_package: str = "",
    backend_command: str = "",
    backend_args: list[str] | None = None,
    transport_type: str = "",
    localization_type: str = "",
    functional_type: str = "",
    state_type: str = "",
    credential_boundary: str = "",
    approval_type: str = "",
    expected_tools: list[str] | None = None,
    package_registry_type: str = "",
    package_version: str = "",
    runtime_hint: str = "",
    npm_package_confirmed: bool = False,
    environment_variables_reviewed: bool = False,
    package_arguments_reviewed: bool = False,
    environment_variables: list[Any] | None = None,
    package_arguments: list[Any] | None = None,
    required_secret_names: list[str] | None = None,
    tool_schemas: dict[str, Any] | None = None,
    tool_schema_records: list[Any] | None = None,
    tool_schema_summaries: Any = None,
    prompt_library: dict[str, Any] | None = None,
    structured_payload_path: str = "",
    issue: str = "",
    client_type: str = DEFAULT_CLIENT_TYPE,
) -> dict[str, Any]:
    """Natural alias for cf_project_service_onboarding_runtime_apply."""
    return cf_project_service_onboarding_runtime_apply(
        project_root=project_root,
        candidate_service=candidate_service,
        operator_goal=operator_goal,
        source_path=source_path,
        service_binding=service_binding,
        backend_package=backend_package,
        backend_command=backend_command,
        backend_args=backend_args,
        transport_type=transport_type,
        localization_type=localization_type,
        functional_type=functional_type,
        state_type=state_type,
        credential_boundary=credential_boundary,
        approval_type=approval_type,
        expected_tools=expected_tools,
        package_registry_type=package_registry_type,
        package_version=package_version,
        runtime_hint=runtime_hint,
        npm_package_confirmed=npm_package_confirmed,
        environment_variables_reviewed=environment_variables_reviewed,
        package_arguments_reviewed=package_arguments_reviewed,
        environment_variables=environment_variables,
        package_arguments=package_arguments,
        required_secret_names=required_secret_names,
        tool_schemas=tool_schemas,
        tool_schema_records=tool_schema_records,
        tool_schema_summaries=tool_schema_summaries,
        prompt_library=prompt_library,
        structured_payload_path=structured_payload_path,
        issue=issue,
        client_type=client_type,
    )


def build_service_onboarding_runtime_execute(
    project_root: str,
    runtime_apply_package_id: str = "",
    candidate_service: str = "",
    operator_goal: str = "",
    source_path: str = "",
    service_binding: str = "",
    backend_package: str = "",
    backend_command: str = "",
    backend_args: list[str] | None = None,
    transport_type: str = "",
    localization_type: str = "",
    functional_type: str = "",
    state_type: str = "",
    credential_boundary: str = "",
    approval_type: str = "",
    expected_tools: list[str] | None = None,
    package_registry_type: str = "",
    package_version: str = "",
    runtime_hint: str = "",
    npm_package_confirmed: bool = False,
    environment_variables_reviewed: bool = False,
    package_arguments_reviewed: bool = False,
    environment_variables: list[Any] | None = None,
    package_arguments: list[Any] | None = None,
    required_secret_names: list[str] | None = None,
    tool_schemas: dict[str, Any] | None = None,
    tool_schema_records: list[Any] | None = None,
    tool_schema_summaries: Any = None,
    prompt_library: dict[str, Any] | None = None,
    structured_payload_path: str = "",
    issue: str = "",
    client_type: str = DEFAULT_CLIENT_TYPE,
) -> dict[str, Any]:
    """Natural alias for cf_project_service_onboarding_runtime_execute."""
    return cf_project_service_onboarding_runtime_execute(
        project_root=project_root,
        runtime_apply_package_id=runtime_apply_package_id,
        candidate_service=candidate_service,
        operator_goal=operator_goal,
        source_path=source_path,
        service_binding=service_binding,
        backend_package=backend_package,
        backend_command=backend_command,
        backend_args=backend_args,
        transport_type=transport_type,
        localization_type=localization_type,
        functional_type=functional_type,
        state_type=state_type,
        credential_boundary=credential_boundary,
        approval_type=approval_type,
        expected_tools=expected_tools,
        package_registry_type=package_registry_type,
        package_version=package_version,
        runtime_hint=runtime_hint,
        npm_package_confirmed=npm_package_confirmed,
        environment_variables_reviewed=environment_variables_reviewed,
        package_arguments_reviewed=package_arguments_reviewed,
        environment_variables=environment_variables,
        package_arguments=package_arguments,
        required_secret_names=required_secret_names,
        tool_schemas=tool_schemas,
        tool_schema_records=tool_schema_records,
        tool_schema_summaries=tool_schema_summaries,
        prompt_library=prompt_library,
        structured_payload_path=structured_payload_path,
        issue=issue,
        client_type=client_type,
    )



@server.tool()
def cf_project_reset_current_project(
    project_root: str = "",
    client_type: str = DEFAULT_CLIENT_TYPE,
    profile: str = "project_init_base",
    preserve_evidence: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Reset helper-owned project-init state for this project root only."""
    try:
        resolved_root = _current_session_project_root(project_root)
        result = {
            "ok": True,
            **helper.reset_current_project(
                project_root=resolved_root,
                client_type=client_type,
                profile=profile,
                preserve_evidence=preserve_evidence,
                dry_run=dry_run,
            ),
        }
        if not dry_run:
            cache_root = str(result.get("project_root") or resolved_root)
            _clear_durable_cache(cache_root)
            _clear_durable_recovery_cache(cache_root)
            _clear_pending_project_init_input(cache_root)
        return client_visible_project_init_payload(result)
    except Exception as exc:
        return _error(exc)


@server.tool()
def reset_current_project(
    project_root: str = "",
    client_type: str = DEFAULT_CLIENT_TYPE,
    profile: str = "project_init_base",
    preserve_evidence: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Alias for cf_project_reset_current_project."""
    return cf_project_reset_current_project(
        project_root=project_root,
        client_type=client_type,
        profile=profile,
        preserve_evidence=preserve_evidence,
        dry_run=dry_run,
    )


@server.tool()
def list_available_capabilities(
    project_root: str,
    client_type: str = DEFAULT_CLIENT_TYPE,
    contextforge_servers: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """List activation candidates and one service-selection next_turn."""
    try:
        root = project_state.validate_project_root(project_root, require_workspace=True)
        if contextforge_servers is None:
            service_offerings = _contextforge_registry_service_offerings(root)
        else:
            service_offerings = common.discover_contextforge_registry_service_offerings(
                project_root=root,
                contextforge_servers=contextforge_servers,
                contextforge_gateways=[],
                contextforge_resources=[],
            )
        result = {
            "ok": True,
            **helper.list_available_capabilities(
                project_root=root,
                client_type=client_type,
                contextforge_servers=contextforge_servers,
                contextforge_service_offerings=service_offerings,
            ),
        }
        return client_visible_project_init_list_payload(result)
    except ContextForgeCatalogUnavailable as exc:
        return _catalog_unavailable_payload(root, client_type, exc)
    except Exception as exc:
        return _error(exc)


@server.tool()
def cf_project_init_list_capabilities(
    project_root: str,
    client_type: str = DEFAULT_CLIENT_TYPE,
    contextforge_servers: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Alias for list_available_capabilities with the project-init tool id."""
    return list_available_capabilities(
        project_root=project_root,
        client_type=client_type,
        contextforge_servers=contextforge_servers,
    )


@server.tool()
def cf_project_service_list(project_root: str, client_type: str = DEFAULT_CLIENT_TYPE) -> dict[str, Any]:
    """List known ContextForge services with simple Available/Enabled/Disabled status."""
    try:
        return service_management_list(project_root=project_root, client_type=client_type)
    except Exception as exc:
        return _error(exc)


@server.tool()
def cf_project_service_status(project_root: str, service: str = "", client_type: str = DEFAULT_CLIENT_TYPE) -> dict[str, Any]:
    """Show simple service status for all services or one known service."""
    try:
        return service_management_status(project_root=project_root, service=service, client_type=client_type)
    except Exception as exc:
        return _error(exc)


@server.tool()
def cf_project_service_details(project_root: str, service: str, client_type: str = DEFAULT_CLIENT_TYPE) -> dict[str, Any]:
    """Show details for one known ContextForge service."""
    try:
        return service_management_details(project_root=project_root, service=service, client_type=client_type)
    except Exception as exc:
        return _error(exc)


@server.tool()
def cf_project_service_enable(
    project_root: str,
    service: str,
    client_type: str = DEFAULT_CLIENT_TYPE,
    confirm: bool = False,
    dry_run: bool = False,
    language: str = "",
) -> dict[str, Any]:
    """Enable a known ContextForge service for this project. For Serena, set language or reply with a language such as python."""
    try:
        return service_management_enable(project_root=project_root, service=service, client_type=client_type, confirm=confirm, dry_run=dry_run, language=language)
    except Exception as exc:
        return _error(exc)


@server.tool()
def cf_project_service_disable(
    project_root: str,
    service: str,
    client_type: str = DEFAULT_CLIENT_TYPE,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Disable a known ContextForge service for this project without deleting backing state."""
    try:
        return service_management_disable(project_root=project_root, service=service, client_type=client_type, confirm=confirm, dry_run=dry_run)
    except Exception as exc:
        return _error(exc)


@server.tool()
def cf_project_service_remove(
    project_root: str,
    service: str,
    confirmation: str = "",
    client_type: str = DEFAULT_CLIENT_TYPE,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Remove a known ContextForge service from this project with typed confirmation."""
    try:
        return service_management_remove(project_root=project_root, service=service, client_type=client_type, confirmation=confirmation, dry_run=dry_run)
    except Exception as exc:
        return _error(exc)


@server.tool()
def cf_project_service_repair(
    project_root: str,
    service: str,
    client_type: str = DEFAULT_CLIENT_TYPE,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Repair known ContextForge service configuration for this project."""
    try:
        return service_management_repair(project_root=project_root, service=service, client_type=client_type, confirm=confirm, dry_run=dry_run)
    except Exception as exc:
        return _error(exc)


def propose_project_init(
    project_root: str,
    selected_services: list[dict[str, Any] | str],
    client_type: str = DEFAULT_CLIENT_TYPE,
    inputs: dict[str, Any] | None = None,
    contextforge_servers: list[dict[str, Any]] | None = None,
    contextforge_service_offerings: list[dict[str, Any]] | None = None,
    server_instances_root: str | None = None,
) -> dict[str, Any]:
    """Build a non-mutating activation plan or the next required input turn."""
    try:
        result = {
            "ok": True,
            **helper.propose_project_init(
                project_root=project_root,
                selected_services=selected_services,
                client_type=client_type,
                inputs=inputs,
                contextforge_servers=contextforge_servers,
                contextforge_service_offerings=contextforge_service_offerings,
                server_instances_root=server_instances_root,
            ),
        }
        if result.get("status") == "needs_input":
            _remember_pending_project_init_input(project_root, selected_services)
        _remember_project_init_result(project_root, result)
        return result
    except Exception as exc:
        return _error(exc)


def cf_project_init_propose(
    project_root: str,
    selected_services: list[dict[str, Any] | str],
    client_type: str = DEFAULT_CLIENT_TYPE,
    inputs: dict[str, Any] | None = None,
    contextforge_servers: list[dict[str, Any]] | None = None,
    server_instances_root: str | None = None,
) -> dict[str, Any]:
    """Build and cache a project-init plan for later id/digest approval."""
    return propose_project_init(
        project_root=project_root,
        selected_services=selected_services,
        client_type=client_type,
        inputs=inputs,
        contextforge_servers=contextforge_servers,
        server_instances_root=server_instances_root,
    )


@server.tool()
def cf_project_init_record_service_decision(
    project_root: str,
    selected_services: list[dict[str, Any] | str] | None = None,
    decision_state: str = "declined",
    client_type: str = DEFAULT_CLIENT_TYPE,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Record a project-local decline/defer decision without active import."""
    try:
        project_root = _continuation_project_root(project_root, client_type)
        selected = selected_services
        source_plan_id = None
        if not selected:
            plan = _cached_project_init_plan_or_none(project_root)
            if isinstance(plan, dict):
                selected = [
                    dict(service)
                    for service in plan.get("selected_services") or []
                    if isinstance(service, dict)
                ]
                source_plan_id = str(plan.get("plan_id") or "") or None
        if not selected:
            pending = _pending_project_init_input(project_root)
            selected = [
                item
                for item in (pending or {}).get("selected_services") or []
                if item
            ]
        result = helper.record_project_init_service_decision(
            project_root=project_root,
            selected_services=selected or [],
            decision_state=decision_state,
            client_type=client_type,
            source_plan_id=source_plan_id,
            dry_run=dry_run,
        )
        if not dry_run:
            _clear_pending_project_init_input(project_root)
        return client_visible_project_init_decision_payload(result)
    except Exception as exc:
        return _error(exc)


@server.tool()
def cf_project_init_continue(
    project_root: str,
    client_type: str = DEFAULT_CLIENT_TYPE,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Continue project init from the latest plain user reply.

    This is the narrow client-facing OpenCode tool: selection text proposes a
    plan, explicit approval applies it, and any other text returns the service
    menu. Direct approve/apply tools remain helper internals.
    """
    try:
        project_root = _continuation_project_root(project_root, client_type)
        latest = _read_latest_user_message_text(project_root)
        pending_input = _pending_project_init_input(project_root)
        language = _language_input_from_text(latest, pending_input)
        service_offerings_cache: list[dict[str, Any]] | None = None

        def service_offerings_for_continue() -> list[dict[str, Any]]:
            nonlocal service_offerings_cache
            if service_offerings_cache is None:
                root = project_state.validate_project_root(project_root, require_workspace=True)
                service_offerings_cache = _contextforge_registry_service_offerings(root)
            return service_offerings_cache

        if pending_input and language:
            pending_services = _pending_service_refs(pending_input)
            if language == "defer":
                non_serena_services = [
                    item
                    for item in pending_services
                    if not _is_serena_service_ref(item)
                ]
                if non_serena_services:
                    result = propose_project_init(
                        project_root=project_root,
                        selected_services=non_serena_services,
                        client_type=client_type,
                        contextforge_service_offerings=service_offerings_for_continue(),
                    )
                    if result.get("status") != "needs_input":
                        _clear_pending_project_init_input(project_root)
                    return client_visible_project_init_plan_payload(result, include_next_turn=client_type != "codex")
                serena_services = [
                    item
                    for item in pending_services
                    if _is_serena_service_ref(item)
                ]
                return cf_project_init_record_service_decision(
                    project_root=project_root,
                    selected_services=serena_services or None,
                    decision_state="deferred",
                    client_type=client_type,
                    dry_run=dry_run,
                )
            if pending_services:
                result = propose_project_init(
                    project_root=project_root,
                    selected_services=pending_services,
                    client_type=client_type,
                    inputs={"language": language},
                    contextforge_service_offerings=service_offerings_for_continue(),
                )
                if result.get("status") != "needs_input":
                    _clear_pending_project_init_input(project_root)
                return client_visible_project_init_plan_payload(result, include_next_turn=client_type != "codex")
        if _latest_text_is_decline(latest):
            return cf_project_init_record_service_decision(
                project_root=project_root,
                decision_state="declined",
                client_type=client_type,
                dry_run=dry_run,
            )
        if _latest_text_is_defer(latest):
            pending_services = _pending_service_refs(pending_input)
            serena_services = [
                item
                for item in pending_services
                if _is_serena_service_ref(item)
            ]
            return cf_project_init_record_service_decision(
                project_root=project_root,
                selected_services=serena_services or None,
                decision_state="deferred",
                client_type=client_type,
                dry_run=dry_run,
            )
        if _latest_text_is_approval(latest):
            approval = cf_project_init_approve(project_root=project_root)
            if approval.get("ok") is False:
                return approval
            result = cf_project_init_apply(
                project_root=project_root,
                dry_run=dry_run,
            )
            return client_visible_project_init_apply_payload(result)
        service_offerings = service_offerings_for_continue()
        capabilities = helper.list_available_capabilities(
            project_root=project_root,
            client_type=client_type,
            contextforge_service_offerings=service_offerings,
        )
        selected = _selected_service_ids_from_text(latest, capabilities)
        if selected:
            result = propose_project_init(
                project_root=project_root,
                selected_services=selected,
                client_type=client_type,
                contextforge_service_offerings=service_offerings,
            )
            if result.get("status") == "needs_input":
                _remember_pending_project_init_input(project_root, selected)
            return client_visible_project_init_plan_payload(result, include_next_turn=client_type != "codex")
        return client_visible_project_init_list_payload({"ok": True, **capabilities})
    except ContextForgeCatalogUnavailable as exc:
        root = project_state.validate_project_root(project_root, require_workspace=True)
        return _catalog_unavailable_payload(root, client_type, exc)
    except Exception as exc:
        return _error(exc)


def propose_project_init_recovery(
    project_root: str,
    client_type: str = DEFAULT_CLIENT_TYPE,
    contextforge_servers: list[dict[str, Any]] | None = None,
    server_instances_root: str | None = None,
    inputs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build and cache a recovery project-init plan."""
    try:
        recovery_inputs = dict(inputs or {})
        if not any(key in recovery_inputs for key in ("activation_plan", "project_init_plan", "source_activation_plan", "plan")):
            cached_activation_plan = _CACHED_PLANS.get(_cache_key(project_root))
            if not cached_activation_plan:
                durable = _read_durable_cache(project_root)
                durable_plan = durable.get("plan") if isinstance(durable.get("plan"), dict) else None
                if durable_plan:
                    cached_activation_plan = dict(durable_plan)
            if isinstance(cached_activation_plan, dict) and cached_activation_plan.get("workflow") == "project_init":
                recovery_inputs["activation_plan"] = cached_activation_plan
            elif not recovery_inputs:
                cached_recovery_plan = _CACHED_RECOVERY_PLANS.get(_cache_key(project_root))
                if not cached_recovery_plan:
                    durable = _read_durable_cache(project_root)
                    durable_recovery_plan = durable.get("recovery_plan") if isinstance(durable.get("recovery_plan"), dict) else None
                    if durable_recovery_plan:
                        cached_recovery_plan = dict(durable_recovery_plan)
                        _CACHED_RECOVERY_PLANS[_cache_key(project_root)] = cached_recovery_plan
                if cached_recovery_plan:
                    return {"ok": True, **cached_recovery_plan}
        result = {
            "ok": True,
            **helper.propose_project_init_recovery(
                project_root=project_root,
                client_type=client_type,
                contextforge_servers=contextforge_servers,
                server_instances_root=server_instances_root,
                inputs=recovery_inputs,
            ),
        }
        _remember_recovery_plan(project_root, _unwrap_tool_envelope(result))
        return result
    except Exception as exc:
        return _error(exc)


def cf_project_init_recovery_propose(
    project_root: str,
    client_type: str = DEFAULT_CLIENT_TYPE,
    contextforge_servers: list[dict[str, Any]] | None = None,
    server_instances_root: str | None = None,
    inputs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Alias for recovery plan creation with the project-init tool id."""
    return propose_project_init_recovery(
        project_root=project_root,
        client_type=client_type,
        contextforge_servers=contextforge_servers,
        server_instances_root=server_instances_root,
        inputs=inputs,
    )


def approve_project_init_plan(
    project_root: str,
    plan: dict[str, Any],
    approval: dict[str, Any],
) -> dict[str, Any]:
    """Issue helper-owned consent receipts for approved project-local effects."""
    try:
        clean_plan = _unwrap_tool_envelope(plan)
        challenge = clean_plan.get("approval_challenge") if isinstance(clean_plan.get("approval_challenge"), dict) else {}
        approval_challenge_id = (
            approval.get("challenge_id")
            if isinstance(approval, dict) and approval.get("challenge_id")
            else challenge.get("challenge_id")
        )
        approval_plan_digest = (
            approval.get("plan_digest")
            if isinstance(approval, dict) and approval.get("plan_digest")
            else clean_plan.get("plan_digest")
        )
        _require_user_approval_text(project_root, str(approval_challenge_id or ""), str(approval_plan_digest or ""))
        helper.restore_process_local_approval_session(project_root=project_root, plan=clean_plan)
        local_event = helper.record_local_approval_event(
            project_root=project_root,
            plan=clean_plan,
            issuer_token=helper._LOCAL_APPROVAL_ISSUER_TOKEN,
            channel="interactive_user",
        )
        result = {
            "ok": True,
            **helper.approve_project_init_plan(
                project_root=project_root,
                plan=clean_plan,
                approval=approval,
                local_approval_event_ref=local_event["event_ref"],
                actor="developer",
                source_client=str(clean_plan.get("client_type") or "codex"),
                source_client_auth_strength="shared_token",
            ),
        }
        _remember_plan(project_root, clean_plan)
        _remember_receipts(project_root, list(result.get("receipts") or []))
        return result
    except Exception as exc:
        return _error(exc)


def approve_project_init_recovery_plan(
    project_root: str,
    plan: dict[str, Any],
    approval: dict[str, Any],
) -> dict[str, Any]:
    """Issue helper-owned recovery consent receipts for approved recovery effects."""
    try:
        clean_plan = _unwrap_tool_envelope(plan)
        challenge = clean_plan.get("approval_challenge") if isinstance(clean_plan.get("approval_challenge"), dict) else {}
        approval_challenge_id = (
            approval.get("challenge_id")
            if isinstance(approval, dict) and approval.get("challenge_id")
            else challenge.get("challenge_id")
        )
        approval_plan_digest = (
            approval.get("plan_digest")
            if isinstance(approval, dict) and approval.get("plan_digest")
            else clean_plan.get("plan_digest")
        )
        _require_user_approval_text(project_root, str(approval_challenge_id or ""), str(approval_plan_digest or ""))
        helper.restore_process_local_approval_session(project_root=project_root, plan=clean_plan)
        local_event = helper.record_local_approval_event(
            project_root=project_root,
            plan=clean_plan,
            issuer_token=helper._LOCAL_APPROVAL_ISSUER_TOKEN,
            channel="interactive_user",
        )
        result = {
            "ok": True,
            **helper.approve_project_init_recovery_plan(
                project_root=project_root,
                plan=clean_plan,
                approval=approval,
                local_approval_event_ref=local_event["event_ref"],
                actor="developer",
                source_client=str(clean_plan.get("client_type") or "codex"),
                source_client_auth_strength="shared_token",
            ),
        }
        _remember_recovery_plan(project_root, clean_plan)
        _remember_recovery_receipts(project_root, list(result.get("receipts") or []))
        return client_visible_project_init_payload(result)
    except Exception as exc:
        return _error(exc)


def cf_project_init_recovery_approve(
    project_root: str,
    challenge_id: str = "",
    plan_digest: str = "",
) -> dict[str, Any]:
    """Approve the latest cached recovery plan after explicit user approval."""
    try:
        plan = _matching_cached_recovery_plan(project_root, challenge_id or None, plan_digest or None)
        challenge = plan.get("approval_challenge") if isinstance(plan.get("approval_challenge"), dict) else {}
        actual_challenge_id = str(challenge.get("challenge_id") or "")
        actual_plan_digest = str(plan.get("plan_digest") or "")
        _require_user_approval_text(project_root, actual_challenge_id, actual_plan_digest)
        helper.restore_process_local_approval_session(project_root=project_root, plan=plan)
        local_event = helper.record_local_approval_event(
            project_root=project_root,
            plan=plan,
            issuer_token=helper._LOCAL_APPROVAL_ISSUER_TOKEN,
            channel="interactive_user",
        )
        approval = {"decision": "approve", "challenge_id": actual_challenge_id, "plan_digest": actual_plan_digest}
        result = {
            "ok": True,
            **helper.approve_project_init_recovery_plan(
                project_root=project_root,
                plan=plan,
                approval=approval,
                local_approval_event_ref=local_event["event_ref"],
                actor="developer",
                source_client=str(plan.get("client_type") or "codex"),
                source_client_auth_strength="shared_token",
            ),
        }
        _remember_recovery_plan(project_root, plan)
        _remember_recovery_receipts(project_root, list(result.get("receipts") or []))
        return client_visible_project_init_payload(result)
    except Exception as exc:
        return _error(exc)


def apply_project_init_recovery(
    project_root: str,
    plan: dict[str, Any],
    receipts: list[dict[str, Any]],
    contextforge_servers: list[dict[str, Any]] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Apply a helper-approved recovery plan and return the install/reload next turn."""
    try:
        clean_plan = _unwrap_tool_envelope(plan)
        helper.restore_process_local_approval_session(project_root=project_root, plan=clean_plan, receipts=receipts)
        result = {
            "ok": True,
            **helper.apply_project_init_recovery(
                project_root=project_root,
                plan=clean_plan,
                receipts=receipts,
                contextforge_servers=contextforge_servers,
                dry_run=dry_run,
            ),
        }
        return result
    except Exception as exc:
        return _error(exc)


def cf_project_init_recovery_apply(
    project_root: str,
    receipts: list[dict[str, Any]] | None = None,
    contextforge_servers: list[dict[str, Any]] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Apply the cached recovery plan and receipts."""
    try:
        plan = _matching_cached_recovery_plan(project_root, None, None)
        cached_receipts = receipts if receipts is not None else _CACHED_RECOVERY_RECEIPTS.get(_cache_key(project_root))
        if cached_receipts is None:
            durable = _read_durable_cache(project_root)
            durable_receipts = durable.get("recovery_receipts") if isinstance(durable.get("recovery_receipts"), list) else None
            if durable_receipts is not None:
                cached_receipts = list(durable_receipts)
                _CACHED_RECOVERY_RECEIPTS[_cache_key(project_root)] = cached_receipts
        if not isinstance(cached_receipts, list):
            raise ValueError("no cached project-init receipts are available; call cf_project_init_recovery_approve first")
        helper.restore_process_local_approval_session(project_root=project_root, plan=plan, receipts=cached_receipts)
        result = {
            "ok": True,
            **helper.apply_project_init_recovery(
                project_root=project_root,
                plan=plan,
                receipts=cached_receipts,
                contextforge_servers=contextforge_servers,
                dry_run=dry_run,
            ),
        }
        if not dry_run:
            _clear_durable_recovery_cache(project_root, keep_plan=True)
        return result
    except Exception as exc:
        return _error(exc)


def cf_project_init_approve(
    project_root: str,
    challenge_id: str = "",
    plan_digest: str = "",
) -> dict[str, Any]:
    """Approve the latest cached project-init plan after explicit user approval."""
    try:
        plan = _matching_cached_plan(project_root, challenge_id or None, plan_digest or None)
        challenge = plan.get("approval_challenge") if isinstance(plan.get("approval_challenge"), dict) else {}
        actual_challenge_id = str(challenge.get("challenge_id") or "")
        actual_plan_digest = str(plan.get("plan_digest") or "")
        _require_user_approval_text(project_root, actual_challenge_id, actual_plan_digest)
        helper.restore_process_local_approval_session(project_root=project_root, plan=plan)
        local_event = helper.record_local_approval_event(
            project_root=project_root,
            plan=plan,
            issuer_token=helper._LOCAL_APPROVAL_ISSUER_TOKEN,
            channel="interactive_user",
        )
        approval = {"decision": "approve", "challenge_id": actual_challenge_id, "plan_digest": actual_plan_digest}
        result = {
            "ok": True,
            **helper.approve_project_init_plan(
                project_root=project_root,
                plan=plan,
                approval=approval,
                local_approval_event_ref=local_event["event_ref"],
                actor="developer",
                source_client=str(plan.get("client_type") or "codex"),
                source_client_auth_strength="shared_token",
            ),
        }
        _remember_plan(project_root, plan)
        _remember_receipts(project_root, list(result.get("receipts") or []))
        return result
    except Exception as exc:
        return _error(exc)


def apply_approved_project_init(
    project_root: str,
    plan: dict[str, Any],
    receipts: list[dict[str, Any]],
    contextforge_servers: list[dict[str, Any]] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Apply a helper-approved project-init plan and return installed/reload-required next_turn."""
    try:
        clean_plan = _unwrap_tool_envelope(plan)
        helper.restore_process_local_approval_session(project_root=project_root, plan=clean_plan, receipts=receipts)
        result = {
            "ok": True,
            **helper.apply_approved_project_init(
                project_root=project_root,
                plan=clean_plan,
                receipts=receipts,
                contextforge_servers=contextforge_servers,
                recovery_plan=_cached_recovery_continuation_plan(project_root, clean_plan),
                dry_run=dry_run,
            ),
        }
        _remember_project_init_result(project_root, result)
        return result
    except Exception as exc:
        return _error(exc)


def cf_project_init_apply(
    project_root: str,
    receipts: list[dict[str, Any]] | None = None,
    contextforge_servers: list[dict[str, Any]] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Apply the cached approved project-init plan and receipts."""
    try:
        plan = _matching_cached_plan(project_root, None, None)
        cached_receipts = _matching_cached_receipts(project_root, plan)
        if not isinstance(cached_receipts, list):
            raise ValueError("no cached project-init receipts are available; approve the plan before calling cf_project_init_apply")
        helper.restore_process_local_approval_session(project_root=project_root, plan=plan, receipts=cached_receipts)
        recovery_plan = _cached_recovery_continuation_plan(project_root, plan)
        result_payload = helper.apply_approved_project_init(
            project_root=project_root,
            plan=plan,
            receipts=cached_receipts,
            contextforge_servers=contextforge_servers,
            recovery_plan=recovery_plan,
            dry_run=dry_run,
        )
        result = {
            "ok": True,
            **result_payload,
        }
        _remember_project_init_result(project_root, result)
        if not dry_run and result_payload.get("status") != "config_recovery_required":
            _clear_durable_cache(project_root)
        return result
    except Exception as exc:
        return _error(exc)


def repair_pending_project_init_config(
    project_root: str,
    client_type: str = DEFAULT_CLIENT_TYPE,
    contextforge_servers: list[dict[str, Any]] | None = None,
    server_instances_root: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Repair an approved project-init job whose project-local config is incomplete."""
    try:
        result = {
            "ok": True,
            **helper.repair_pending_project_init_config(
                project_root=project_root,
                client_type=client_type,
                contextforge_servers=contextforge_servers,
                server_instances_root=server_instances_root,
                dry_run=dry_run,
            ),
        }
        return client_visible_project_init_payload(result)
    except Exception as exc:
        return _error(exc)


def cf_project_init_repair(
    project_root: str,
    client_type: str = DEFAULT_CLIENT_TYPE,
    contextforge_servers: list[dict[str, Any]] | None = None,
    server_instances_root: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Alias for repair_pending_project_init_config with the project-init tool id."""
    return repair_pending_project_init_config(
        project_root=project_root,
        client_type=client_type,
        contextforge_servers=contextforge_servers,
        server_instances_root=server_instances_root,
        dry_run=dry_run,
    )


if __name__ == "__main__":
    server.run()
