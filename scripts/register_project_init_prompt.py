#!/usr/bin/env python3
"""Register ContextForge project-init prompt/resource artifacts."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import urllib.error
import urllib.request

import contextforge_mcp_wrapper as gateway
import control_plane_registry_discipline as registry_discipline
from mcpgateway.services.content_security import get_content_security_service

from project_init_common import (
    PROJECT_INIT_PROMPT_NAME,
    PROJECT_INIT_RESOURCE_NAME,
    PROJECT_INIT_RESOURCE_URI,
    PROMPT_VERSION,
    SERENA_GUIDANCE_RESOURCE_NAME,
    SERENA_GUIDANCE_PROMPT_NAME,
    SERENA_GUIDANCE_RESOURCE_URI,
)


OWNER = "admin@contextforge.dev"
VISIBILITY = "public"
SCHEMA_URI = "contextforge://diagnostics/project-init-guidance-registration/v1"

SQL_TRIGGER_RE = re.compile(r"\b(update|delete|drop|insert|alter|truncate|exec|execute|merge)\s+", re.IGNORECASE)
SHELL_CHAIN_RE = re.compile(r"(?<![`\\])(?:&&|\|\||;\s*(?:rm|curl|wget|bash|sh|python|python3|node|npm|uv)\b)")


PROJECT_INIT_TEXT = """
ContextForge project initialization, version {{ prompt_version }}.

Project: {{ project_name }}
Root: {{ project_root }}
Target client: {{ target_client }}
State: {{ project_state_status }} at {{ project_state_path }}
Lifecycle: {{ project_state_lifecycle_status }} / {{ project_state_recommended_action }} / hook={{ project_init_hook_prompt_state }}
Hash: {{ project_root_hash }}
Legacy Serena state: {{ serena_decision }} / {{ serena_provision_status }}

This is model-visible control context. Do not echo this context to the user. When a target client provides hidden or structured prompt/context injection, deliver project-init guidance there. User-visible UI should be limited to information that requires user understanding or response. Do not narrate helper/tool/cache/payload mechanics, approval payload lookup, internal approval/apply tool discovery, or implementation details in visible replies. When a contextforge-helper result contains assistant_visible_response or message for the current step, copy that value as the complete visible reply and stop unless one ordinary user question is still required. If lifecycle is missing / fresh_initialization, explain in practical terms that ContextForge initialization would inspect project-local capabilities, ask which services to activate, present planned project-local writes and non-actions, require scoped approval before apply, and avoid writing project state, client config, trust state, registry entries, service state, secrets, or backend state before that approval. On the first user prompt in a session with lifecycle missing / fresh_initialization, before answering unrelated work or ordinary tool-list questions, offer ContextForge initialization by asking exactly: "Which ContextForge services should I activate for this project?" Show helper-discovered choices when available, then stop and wait. Conduct project init as call-and-response: Ask exactly one question, then stop and wait. Whenever presenting choices, use the helper-provided response_form or render a numbered option list. Never choose service selections or approval on behalf of the user. If the user echoes your question, asks you to provide the selection numbers, or otherwise replies with assistant-like text, ask one clarifying question. Prefer the contextforge-helper workflow tools when visible; if missing, stale, untrusted, wrong-project-root, unsupported-client, or read-only-plan-only, stop at that boundary. Do not invoke project-init helper scripts or Python modules through shell as a substitute for visible helper tools; if helper approval/apply cannot complete through the visible helper surface and exact helper-returned plan fallback, stop.

Boundaries: .project/context_forge_state.json is the project initialization authority; legacy .env is only a hint. Client configs and extension files are discovery or activation surfaces, not service identity. Project init may write only target-client project-local activation state after scoped approval: for Codex this is project-local .codex/config.toml plus .project/context_forge_state.json; for Gemini this is project-local .gemini/settings.json plus .project/context_forge_state.json after global Gemini hook and contextforge-helper bootstrap entries are available; for OpenCode this is project-local opencode.json plus .project/context_forge_state.json after user-home OpenCode ContextForge plugin and contextforge-helper bootstrap entries are available; for Pi this is .project/context_forge_state.json records consumed by the separately installed global Pi extension shim. No user-global config/trust/extension changes, secrets, live registry/catalog mutation, backend install, backend restart, or shared canonical per-project backend creation.

Dialogue:
1. Start with get_project_context/list_available_capabilities through contextforge-helper. For every contextforge-helper project-init call, pass client_type={{ target_client }}. If helper is missing, stale, untrusted, wrong-project-root, unsupported-client, or read-only-plan-only, stop; no fallback direct file writes. Lifecycle: if repair_project_init_state or state_repair_required, do not restart service selection; ask only to repair and resume.
2. If services are not selected and no repair/resume is pending, do read-only discovery, then ask only: "Which ContextForge services should I activate for this project?" Show discovered shared canonical services and project-scoped options. Serena is one project-scoped option in this menu, not the whole flow. When the user selects, pass the selected service ids/bindings back to contextforge-helper; do not reconstruct partial descriptors.
3. If a service needs input, ask one input. For Serena, run manage_serena_project_instance.py status --project-root PROJECT_ROOT --require-workspace first; ask language before approval when needed.
4. Present exact plan digest, challenge id, effects, planned writes, and non-actions; ask only for scoped approval. Do not invent or pass local_approval_event_ref strings; prefer those cached id/digest tools over reconstructing a full plan object; do not reconstruct the full plan object from visible text. Then call cf_project_init_approve with the exact challenge id and plan digest, then call cf_project_init_apply using the cached plan and receipts. If status=config_conflict with an embedded recovery_plan, present its exact recovery digest/challenge/effects, then call cf_project_init_recovery_approve with the exact recovery challenge id and recovery plan digest and call cf_project_init_recovery_apply using the cached recovery plan and receipts. Do not call apply_project_init_recovery with only plan_id, plan_digest, or receipt ids; it needs the complete helper-returned recovery plan object and full receipt objects. If recovery includes Serena service_provision and wrapper replacement, keep them together in the helper recovery approval/apply path. If helper cache is missing or stale, use exact helper-returned plan/receipts or stop; do not silently replace the challenge id.
5. After approved apply, report success clearly and succinctly: the selected ContextForge tools are installed for this project, and the user must start a new session or reload the client before the tools register. Stop there.

Client localization: Codex uses .codex/config.toml; Codex launches configured MCP servers and exposes their tools when a session starts; /mcp is a status view, not an in-place MCP tool reload; start a new Codex session from the project root after installation. Gemini uses .gemini/settings.json; Gemini's user-global ContextForge hook injects this project-init guidance through SessionStart/BeforeAgent additionalContext; Gemini CLI launches configured MCP servers and exposes their tools when a session starts; start a new Gemini CLI session from the project root after installation. OpenCode uses project-local opencode.json for selected MCP service bindings; OpenCode's user-home ContextForge plugin uses the messages transform hook as the first-prompt trigger and does not rely on experimental.chat.system.transform as the primary init mechanism; OpenCode discovers configured MCP servers and loads user-home plugins when a session starts; start a new OpenCode session from the project root after installation. Pi uses the global extension framework: input-triggered hidden message, cf_project_init_prompt and cf_contextforge_pi_readback are diagnostic only, do not print or summarize raw cf_contextforge_pi_readback JSON, do not dump readback data into chat, use pi.registerTool(), and the Pi agent must issue /reload after an approved global extension install or upgrade.
""".strip()


SERENA_GUIDANCE_TEXT = """
Serena project instance guidance, version {{ prompt_version }}.

This guidance applies only to real ContextForge Serena virtual servers. Each unrelated project gets one ContextForge-owned backend under the active control-plane repository's server-instances directory, named serena-<slug>-<hash>. Multiple Codex sessions in the same project may share that backend; unrelated projects must not share it. Do not use copied, migration, or legacy checkout paths as the active helper or backend root.

The deterministic identity is:
slug = normalized project basename
hash = first 12 hex characters of SHA-256 over uid:canonical_project_root
instance slug = serena-<slug>-<hash>
virtual server name = serena_<slug>_<hash>_server

Codex should see the local alias serena only from the project's .codex/config.toml. That alias must launch the ContextForge wrapper with the project-specific virtual server name. The direct Serena process is an upstream backend, not the Codex-facing MCP server.

ContextForge virtual server filtering must exclude only Serena project switching, activate_project. Keep get_current_config available because it proves the active project and language backend. Serena's own get_current_config text may still list activate_project among upstream internal active tools; that is not Codex exposure. Judge exposure only from the ContextForge virtual server tool list or the Codex app-server tool list. Do not enable Serena single_project mode in this version unless an equivalent current-config verification path is proven.

Before claiming setup success, verify the user systemd service, ContextForge gateway, ContextForge virtual server tools, project-local Codex config, absence of global Serena exposure, get_current_config active project, and an LSP-backed diagnostics or symbols result when a language is configured. The LSP probe must use a file path, never a directory such as ".". For empty projects, ask for a language and use the manager's --language flow before LSP verification.

Optional read-only LSP capabilities, such as find implementations, are advisory. If an optional probe reports unsupported method -32601, report it as unsupported by the LSP backend with optional-capability-gap severity. Do not call Serena editing tools during automatic LSP verification. LSP runtime scaffolding belongs inside the Serena instance directory under lsp-tools, and no package manager or network install may run unless a future curated approval path explicitly allows it.
""".strip()



def sanitize_scanner_text(text: str) -> str:
    text = text.replace("```", "~~~")
    text = SQL_TRIGGER_RE.sub(lambda match: f"{match.group(1)}_ ", text)
    text = SHELL_CHAIN_RE.sub(" and ", text)
    return text


def prompt_args(template: str) -> list[dict[str, Any]]:
    names = sorted(
        set(re.findall(r"{{\s*([A-Za-z_][A-Za-z0-9_]*)\s*}}", template))
        | set(re.findall(r"(?<!{){([A-Za-z_][A-Za-z0-9_]*)}(?!})", template))
    )
    return [{"name": name, "description": f"Runtime value for {name}.", "required": True} for name in names]


def rendered_messages_text(rendered: Any) -> str:
    messages = rendered.get("messages") if isinstance(rendered, dict) else None
    if not messages:
        return str(rendered)
    parts: list[str] = []
    for message in messages:
        content = message.get("content") if isinstance(message, dict) else None
        if isinstance(content, dict):
            parts.append(str(content.get("text") or content.get("content") or ""))
        elif isinstance(content, str):
            parts.append(content)
    return "\n".join(part for part in parts if part)


def target_request(method: str, base_url: str, path: str, payload: dict[str, Any] | None = None) -> Any:
    headers = {"Accept": "application/json"}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=data,
        headers=headers,
        method=method,
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read()
    return json.loads(body) if body else None


def target_login_token(base_url: str, email: str, password: str) -> str:
    for login_path in ("/auth/login", "/auth/email/login"):
        try:
            payload = target_request("POST", base_url, login_path, {"email": email, "password": password})
        except urllib.error.HTTPError as exc:
            if exc.code in {404, 405}:
                continue
            raise
        token = payload.get("access_token") if isinstance(payload, dict) else None
        if isinstance(token, str) and token:
            return token
    raise RuntimeError(f"ContextForge login did not return an access token for {base_url.rstrip('/')}")


def api_request(
    method: str,
    path: str,
    token: str,
    payload: dict[str, Any] | None = None,
    *,
    base_url: str | None = None,
) -> Any:
    registry_discipline.assert_public_contextforge_api_path(method, path)
    if base_url:
        headers = {"Accept": "application/json"}
        data = None
        if payload is not None:
            data = json.dumps(payload).encode()
            headers["Content-Type"] = "application/json"
        headers["Authorization"] = f"Bearer {token}"
        request = urllib.request.Request(
            f"{base_url.rstrip('/')}{path}",
            data=data,
            headers=headers,
            method=method,
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read()
        return json.loads(body) if body else None
    return gateway._request(method, path, token=token, body=payload)


def api_items(
    method: str,
    path: str,
    token: str,
    payload: dict[str, Any] | None = None,
    *,
    base_url: str | None = None,
) -> list[dict[str, Any]]:
    return gateway._items(api_request(method, path, token, payload=payload, base_url=base_url))


def by_resource_uri(resources: list[dict[str, Any]], uri: str) -> dict[str, Any] | None:
    for resource in resources:
        if resource.get("uri") == uri:
            return resource
    return None


def by_prompt_name(prompts: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    for prompt in prompts:
        if prompt.get("name") == name or prompt.get("customName") == name:
            return prompt
    return None


def preflight_resource(name: str, uri: str, content: str) -> None:
    security = get_content_security_service()
    security.validate_resource_size(content, uri=uri, user_email=OWNER)
    security.detect_malicious_patterns(content, content_type=name, user_email=OWNER)


def preflight_prompt(name: str, template: str) -> None:
    security = get_content_security_service()
    security.validate_prompt_size(template, name=name, user_email=OWNER)
    security.validate_prompt_template(template, name=name, user_email=OWNER)
    security.detect_malicious_patterns(template, content_type=name, user_email=OWNER)


def upsert_resource(
    token: str,
    *,
    name: str,
    uri: str,
    content: str,
    description: str,
    tags: list[str],
    base_url: str | None = None,
) -> dict[str, Any]:
    safe_content = sanitize_scanner_text(content)
    preflight_resource(name, uri, safe_content)
    resources = api_items("GET", "/resources?include_inactive=true&limit=1000", token, base_url=base_url)
    existing = by_resource_uri(resources, uri)
    payload = {
        "uri": uri,
        "name": name,
        "title": name,
        "description": description,
        "mimeType": "text/markdown",
        "content": safe_content,
        "tags": tags,
        "owner_email": OWNER,
        "visibility": VISIBILITY,
        "isActive": True,
        "annotations": {"audience": ["assistant"], "priority": 0.85},
    }
    if existing:
        return api_request("PUT", f"/resources/{existing['id']}", token, payload=payload, base_url=base_url)
    return api_request("POST", "/resources", token, payload={"resource": payload, "visibility": VISIBILITY}, base_url=base_url)


def upsert_prompt(
    token: str,
    *,
    name: str,
    template: str,
    description: str,
    tags: list[str],
    base_url: str | None = None,
) -> dict[str, Any]:
    safe_template = sanitize_scanner_text(template)
    preflight_prompt(name, safe_template)
    prompts = api_items("GET", "/prompts?include_inactive=true&limit=1000", token, base_url=base_url)
    existing = by_prompt_name(prompts, name)
    payload = {
        "name": name,
        "customName": name,
        "displayName": name.replace("_", " "),
        "title": name.replace("_", " ").title(),
        "description": description,
        "template": safe_template,
        "arguments": prompt_args(safe_template),
        "tags": tags,
        "ownerEmail": OWNER,
        "visibility": VISIBILITY,
        "isActive": True,
    }
    if existing:
        return api_request("PUT", f"/prompts/{existing['id']}", token, payload=payload, base_url=base_url)
    return api_request("POST", "/prompts", token, payload={"prompt": payload, "visibility": VISIBILITY}, base_url=base_url)


def prompt_id(prompt: dict[str, Any]) -> str:
    value = prompt.get("id")
    if not value:
        raise RuntimeError(f"prompt has no id: {prompt}")
    return str(value)


def resource_id(resource: dict[str, Any]) -> str:
    value = resource.get("id")
    if not value:
        raise RuntimeError(f"resource has no id: {resource}")
    return str(value)


def set_of_ids(server: dict[str, Any], key: str) -> set[str]:
    values = server.get(key) or []
    return {str(value) for value in values if value}


def tag_values(values: Any) -> set[str]:
    tags: set[str] = set()
    if not isinstance(values, list):
        return tags
    for value in values:
        if isinstance(value, str):
            tags.add(value)
        elif isinstance(value, dict) and value.get("name"):
            tags.add(str(value["name"]))
    return tags


def looks_like_serena_server(server: dict[str, Any]) -> bool:
    name = str(server.get("name") or "")
    tags = {tag.lower() for tag in tag_values(server.get("tags"))}
    description = str(server.get("description") or "").lower()
    return name.startswith("serena_") or name.startswith("serena-") or "serena" in tags or "serena" in description


def retired_registry_uri_prefix() -> str:
    return "contextforge://" + "-".join(("context", "portal"))


def retired_serena_guidance_resource_ids(resources: list[dict[str, Any]], keep_id: str) -> set[str]:
    retired_prefix = retired_registry_uri_prefix()
    ids: set[str] = set()
    for resource in resources:
        resource_id = str(resource.get("id") or "")
        if not resource_id or resource_id == keep_id:
            continue
        uri = str(resource.get("uri") or "")
        name = str(resource.get("name") or "")
        if uri.startswith(f"{retired_prefix}/serena-project-instance-guidance/") or (
            name.startswith("serena_project_instance_guidance_resource") and uri != SERENA_GUIDANCE_RESOURCE_URI
        ):
            ids.add(resource_id)
    return ids


def associate_serena_guidance(
    token: str,
    prompt: dict[str, Any],
    resource: dict[str, Any],
    *,
    base_url: str | None = None,
) -> list[str]:
    servers = api_items("GET", "/servers?include_inactive=true&limit=1000", token, base_url=base_url)
    resources = api_items("GET", "/resources?include_inactive=true&limit=1000", token, base_url=base_url)
    retired_resource_ids = retired_serena_guidance_resource_ids(resources, resource_id(resource))
    associated: list[str] = []
    for server in servers:
        if not looks_like_serena_server(server):
            continue
        tools = set_of_ids(server, "associatedToolIds") or set_of_ids(server, "associatedTools")
        resources = set_of_ids(server, "associatedResourceIds") or set_of_ids(server, "associatedResources")
        prompts = set_of_ids(server, "associatedPromptIds") or set_of_ids(server, "associatedPrompts")
        resources.difference_update(retired_resource_ids)
        resources.add(resource_id(resource))
        prompts.add(prompt_id(prompt))
        payload = {
            "associatedTools": sorted(tools),
            "associatedResources": sorted(resources),
            "associatedPrompts": sorted(prompts),
            "associatedA2aAgents": server.get("associatedA2aAgents") or [],
            "tags": sorted(tag_values(server.get("tags")) | {"serena", "project-instance"}),
            "ownerEmail": OWNER,
            "visibility": VISIBILITY,
        }
        api_request("PUT", f"/servers/{server['id']}", token, payload=payload, base_url=base_url)
        associated.append(str(server["name"]))
    return associated


def verify_prompt_render(token: str, prompt: dict[str, Any], *, base_url: str | None = None) -> None:
    args = {
        "project_name": "cf-controlplane",
        "project_root": "/home/dgk/workspace/cf-controlplane",
        "target_client": "codex",
        "project_root_hash": "verification",
        "dialogue_status": "unasked",
        "serena_decision": "unasked",
        "serena_provision_status": "none",
        "serena_instance_slug": "",
        "serena_server_name": "",
        "project_state_path": "/home/dgk/workspace/cf-controlplane/.project/context_forge_state.json",
        "project_state_status": "uninitialized",
        "project_state_lifecycle_status": "missing",
        "project_state_recommended_action": "start_project_init",
        "project_init_hook_prompt_state": "active",
        "prompt_version": PROMPT_VERSION,
    }
    rendered = api_request("POST", f"/prompts/{prompt_id(prompt)}", token, payload=args, base_url=base_url)
    text = rendered_messages_text(rendered)
    if "ContextForge project initialization" not in text:
        raise RuntimeError("project_init_prompt render did not include expected title")
    if "{project_root}" in text or "{{ project_root }}" in text:
        raise RuntimeError("project_init_prompt render left project_root placeholder unresolved")
    if args["project_root"] not in text:
        raise RuntimeError("project_init_prompt render did not include the supplied project root")


def preflight_all_artifacts() -> None:
    preflight_resource(PROJECT_INIT_RESOURCE_NAME, PROJECT_INIT_RESOURCE_URI, sanitize_scanner_text(PROJECT_INIT_TEXT))
    preflight_prompt(PROJECT_INIT_PROMPT_NAME, sanitize_scanner_text(PROJECT_INIT_TEXT))
    preflight_resource(SERENA_GUIDANCE_RESOURCE_NAME, SERENA_GUIDANCE_RESOURCE_URI, sanitize_scanner_text(SERENA_GUIDANCE_TEXT))
    preflight_prompt(SERENA_GUIDANCE_PROMPT_NAME, sanitize_scanner_text(SERENA_GUIDANCE_TEXT))


def target_metadata(base_url: str | None, env_file: Path | None) -> dict[str, Any]:
    return {
        "base_url": base_url or gateway.GATEWAY_BASE,
        "env_file": str(env_file) if env_file else str(gateway.CONFIG_ENV),
        "env_values_recorded": False,
    }


def dry_run_summary(base_url: str | None, env_file: Path | None) -> dict[str, Any]:
    return {
        "schema_uri": SCHEMA_URI,
        "apply_requested": False,
        "mutation_performed": False,
        "target": target_metadata(base_url, env_file),
        "resources": {"create_or_update": 2},
        "prompts": {"create_or_update": 2},
        "server_association": {"serena_guidance": "planned"},
        "non_actions": [
            "dry-run; no ContextForge API mutation",
            "dry-run; no prompt, resource, server, gateway, tool, Docker, systemd, or client mutation",
            "dry-run; target env values not read",
        ],
    }


def output_summary(summary: dict[str, Any], *, json_output: bool) -> None:
    if json_output:
        print(json.dumps(summary, indent=2, sort_keys=True))
        return
    if not summary.get("apply_requested"):
        print(f"would_register project_init_prompt name={PROJECT_INIT_PROMPT_NAME}")
        print(f"would_register project_init_resource uri={PROJECT_INIT_RESOURCE_URI}")
        print(f"would_register serena_project_instance_guidance name={SERENA_GUIDANCE_PROMPT_NAME}")
        print(f"would_register serena guidance resource uri={SERENA_GUIDANCE_RESOURCE_URI}")
        return
    print(f"registered project_init_prompt id={summary['ids']['project_prompt']}")
    print(f"registered project_init_resource id={summary['ids']['project_resource']}")
    print(f"registered serena_project_instance_guidance id={summary['ids']['serena_prompt']}")
    print(f"registered serena guidance resource id={summary['ids']['serena_resource']}")
    associated = summary.get("associated_serena_servers") or []
    print(f"associated_serena_servers={','.join(associated) if associated else '<none>'}")
    print(f"verified_render_at={summary['verified_render_at']}")


def load_token_for_target(base_url: str | None, env_file: Path | None) -> str:
    if bool(base_url) != bool(env_file):
        raise RuntimeError("--base-url and --env-file must be supplied together")
    if base_url and env_file:
        config = gateway._read_env(env_file)
        email = config.get("PLATFORM_ADMIN_EMAIL")
        password = config.get("PLATFORM_ADMIN_PASSWORD")
        if not email or not password:
            raise RuntimeError(f"missing PLATFORM_ADMIN_EMAIL or PLATFORM_ADMIN_PASSWORD in {env_file}")
        return target_login_token(base_url, email, password)
    env = gateway._read_env(gateway.CONFIG_ENV)
    return gateway._token(env["PLATFORM_ADMIN_EMAIL"], env["PLATFORM_ADMIN_PASSWORD"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Register ContextForge project-init prompt/resource artifacts.")
    parser.add_argument("--dry-run", action="store_true", help="Preflight generated prompt/resource text without mutating ContextForge.")
    parser.add_argument("--base-url", help="Target ContextForge base URL; omit to use wrapper defaults.")
    parser.add_argument("--env-file", type=Path, help="Target env file; omit to use wrapper defaults.")
    parser.add_argument("--json", action="store_true", help="Print structured JSON summary.")
    args = parser.parse_args(argv)
    if args.dry_run:
        preflight_all_artifacts()
        output_summary(dry_run_summary(args.base_url, args.env_file), json_output=args.json)
        return 0

    token = load_token_for_target(args.base_url, args.env_file)
    project_resource = upsert_resource(
        token,
        name=PROJECT_INIT_RESOURCE_NAME,
        uri=PROJECT_INIT_RESOURCE_URI,
        content=PROJECT_INIT_TEXT,
        description="ContextForge project initialization guidance for Codex hooks.",
        tags=["contextforge", "project-init", PROMPT_VERSION],
        base_url=args.base_url,
    )
    project_prompt = upsert_prompt(
        token,
        name=PROJECT_INIT_PROMPT_NAME,
        template=PROJECT_INIT_TEXT,
        description="Render project initialization guidance for a detected Codex project.",
        tags=["contextforge", "project-init", PROMPT_VERSION],
        base_url=args.base_url,
    )
    serena_resource = upsert_resource(
        token,
        name=SERENA_GUIDANCE_RESOURCE_NAME,
        uri=SERENA_GUIDANCE_RESOURCE_URI,
        content=SERENA_GUIDANCE_TEXT,
        description="Per-project Serena instance guidance for ContextForge virtual servers.",
        tags=["contextforge", "serena", "project-instance", PROMPT_VERSION],
        base_url=args.base_url,
    )
    serena_prompt = upsert_prompt(
        token,
        name=SERENA_GUIDANCE_PROMPT_NAME,
        template=SERENA_GUIDANCE_TEXT,
        description="Guidance attached only to real Serena virtual servers.",
        tags=["contextforge", "serena", "project-instance", PROMPT_VERSION],
        base_url=args.base_url,
    )
    associated = associate_serena_guidance(token, serena_prompt, serena_resource, base_url=args.base_url)
    verify_prompt_render(token, project_prompt, base_url=args.base_url)

    refreshed_at = datetime.now(timezone.utc).isoformat()
    output_summary(
        {
            "schema_uri": SCHEMA_URI,
            "apply_requested": True,
            "mutation_performed": True,
            "target": target_metadata(args.base_url, args.env_file),
            "ids": {
                "project_prompt": project_prompt["id"],
                "project_resource": project_resource["id"],
                "serena_prompt": serena_prompt["id"],
                "serena_resource": serena_resource["id"],
            },
            "resources": {"create_or_update": 2},
            "prompts": {"create_or_update": 2},
            "associated_serena_servers": associated,
            "verified_render_at": refreshed_at,
        },
        json_output=args.json,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
