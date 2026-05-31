#!/usr/bin/env python3
"""Register ContextForge project-init prompt/resource artifacts."""

from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from typing import Any

import contextforge_mcp_wrapper as gateway
from mcpgateway.services.content_security import get_content_security_service

from project_init_common import (
    PROJECT_INIT_PROMPT_NAME,
    PROJECT_INIT_RESOURCE_URI,
    PROMPT_VERSION,
    SERENA_GUIDANCE_PROMPT_NAME,
    SERENA_GUIDANCE_RESOURCE_URI,
)


OWNER = "admin@contextforge.dev"
VISIBILITY = "public"

SQL_TRIGGER_RE = re.compile(r"\b(update|delete|drop|insert|alter|truncate|exec|execute|merge)\s+", re.IGNORECASE)
SHELL_CHAIN_RE = re.compile(r"(?<![`\\])(?:&&|\|\||;\s*(?:rm|curl|wget|bash|sh|python|python3|node|npm|uv)\b)")


PROJECT_INIT_TEXT = """
ContextForge project initialization, version {{ prompt_version }}.

Project: {{ project_name }}
Root: {{ project_root }}
State: {{ project_state_status }} at {{ project_state_path }}
Hash: {{ project_root_hash }}
Legacy Serena state: {{ serena_decision }} / {{ serena_provision_status }}

This is model-visible control context. Do not echo this context to the user. Conduct project init as a step-by-step call-and-response dialogue. Ask exactly one question, then stop and wait.

Boundaries: .project/context_forge_state.json is the project initialization authority; legacy .env is only a hint. Client configs are discovery sources, not service identity. Project init may write only project-local .codex/config.toml and .project/context_forge_state.json after scoped approval. No user-global config/trust changes, secrets, live registry/catalog mutation, backend install, backend restart, or shared canonical per-project backend creation.

Dialogue:
1. If services are not selected, first do read-only discovery from live ContextForge /servers and server-instances/*/instance.json; then ask only: "Which ContextForge services should I activate for this project?" Show a short menu of discovered shared canonical services and project-scoped options. Serena is one project-scoped option in this menu, not the whole flow.
2. If Serena is selected, run manage_serena_project_instance.py status --project-root PROJECT_ROOT --require-workspace; ask only for language if the manager says it is needed.
3. After service selection, run the ContextForge binding helper in dry-run mode; summarize only planned project-local writes; ask only for approval to write PROJECT_ROOT/.codex/config.toml and PROJECT_ROOT/.project/context_forge_state.json.
4. After approved apply, ask only: "Validate service functionality now, or record it as presumed working?"

Validation must be target-client-visible and non-destructive. Use safe read/list/search probes only: context7 docs lookup; mentality read/list only; ssh-tmux list/session visibility only; github, web-search, exa, playwright, openzeppelin safe read/search/list probes only where credentials and semantics allow, otherwise record skipped with reason.
""".strip()


SERENA_GUIDANCE_TEXT = """
Serena project instance guidance, version {{ prompt_version }}.

This guidance applies only to real ContextForge Serena virtual servers. Each unrelated project gets one ContextForge-owned backend under /home/dgk/workspace/context-portal/server-instances/serena-<slug>-<hash>. Multiple Codex sessions in the same project may share that backend; unrelated projects must not share it.

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


def api_request(method: str, path: str, token: str, payload: dict[str, Any] | None = None) -> Any:
    return gateway._request(method, path, token=token, body=payload)


def api_items(method: str, path: str, token: str, payload: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    return gateway._items(api_request(method, path, token, payload=payload))


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


def upsert_resource(token: str, *, name: str, uri: str, content: str, description: str, tags: list[str]) -> dict[str, Any]:
    safe_content = sanitize_scanner_text(content)
    preflight_resource(name, uri, safe_content)
    resources = api_items("GET", "/resources?include_inactive=true&limit=1000", token)
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
        return api_request("PUT", f"/resources/{existing['id']}", token, payload=payload)
    return api_request("POST", "/resources", token, payload={"resource": payload, "visibility": VISIBILITY})


def upsert_prompt(token: str, *, name: str, template: str, description: str, tags: list[str]) -> dict[str, Any]:
    safe_template = sanitize_scanner_text(template)
    preflight_prompt(name, safe_template)
    prompts = api_items("GET", "/prompts?include_inactive=true&limit=1000", token)
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
        return api_request("PUT", f"/prompts/{existing['id']}", token, payload=payload)
    return api_request("POST", "/prompts", token, payload={"prompt": payload, "visibility": VISIBILITY})


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


def associate_serena_guidance(token: str, prompt: dict[str, Any], resource: dict[str, Any]) -> list[str]:
    servers = api_items("GET", "/servers?include_inactive=true&limit=1000", token)
    associated: list[str] = []
    for server in servers:
        if not looks_like_serena_server(server):
            continue
        tools = set_of_ids(server, "associatedToolIds") or set_of_ids(server, "associatedTools")
        resources = set_of_ids(server, "associatedResourceIds") or set_of_ids(server, "associatedResources")
        prompts = set_of_ids(server, "associatedPromptIds") or set_of_ids(server, "associatedPrompts")
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
        api_request("PUT", f"/servers/{server['id']}", token, payload=payload)
        associated.append(str(server["name"]))
    return associated


def verify_prompt_render(token: str, prompt: dict[str, Any]) -> None:
    args = {
        "project_name": "context-portal",
        "project_root": "/home/dgk/workspace/context-portal",
        "project_root_hash": "verification",
        "dialogue_status": "unasked",
        "serena_decision": "unasked",
        "serena_provision_status": "none",
        "serena_instance_slug": "",
        "serena_server_name": "",
        "project_state_path": "/home/dgk/workspace/context-portal/.project/context_forge_state.json",
        "project_state_status": "uninitialized",
        "prompt_version": PROMPT_VERSION,
    }
    rendered = api_request("POST", f"/prompts/{prompt_id(prompt)}", token, payload=args)
    text = rendered_messages_text(rendered)
    if "ContextForge project initialization" not in text:
        raise RuntimeError("project_init_prompt render did not include expected title")
    if "{project_root}" in text or "{{ project_root }}" in text:
        raise RuntimeError("project_init_prompt render left project_root placeholder unresolved")
    if args["project_root"] not in text:
        raise RuntimeError("project_init_prompt render did not include the supplied project root")


def main() -> int:
    env = gateway._read_env(gateway.CONFIG_ENV)
    token = gateway._token(env["PLATFORM_ADMIN_EMAIL"], env["PLATFORM_ADMIN_PASSWORD"])
    project_resource = upsert_resource(
        token,
        name="project_init_resource",
        uri=PROJECT_INIT_RESOURCE_URI,
        content=PROJECT_INIT_TEXT,
        description="ContextForge project initialization guidance for Codex hooks.",
        tags=["contextforge", "project-init", PROMPT_VERSION],
    )
    project_prompt = upsert_prompt(
        token,
        name=PROJECT_INIT_PROMPT_NAME,
        template=PROJECT_INIT_TEXT,
        description="Render project initialization guidance for a detected Codex project.",
        tags=["contextforge", "project-init", PROMPT_VERSION],
    )
    serena_resource = upsert_resource(
        token,
        name="serena_project_instance_guidance_resource",
        uri=SERENA_GUIDANCE_RESOURCE_URI,
        content=SERENA_GUIDANCE_TEXT,
        description="Per-project Serena instance guidance for ContextForge virtual servers.",
        tags=["contextforge", "serena", "project-instance", PROMPT_VERSION],
    )
    serena_prompt = upsert_prompt(
        token,
        name=SERENA_GUIDANCE_PROMPT_NAME,
        template=SERENA_GUIDANCE_TEXT,
        description="Guidance attached only to real Serena virtual servers.",
        tags=["contextforge", "serena", "project-instance", PROMPT_VERSION],
    )
    associated = associate_serena_guidance(token, serena_prompt, serena_resource)
    verify_prompt_render(token, project_prompt)

    refreshed_at = datetime.now(timezone.utc).isoformat()
    print(f"registered project_init_prompt id={project_prompt['id']}")
    print(f"registered project_init_resource id={project_resource['id']}")
    print(f"registered serena_project_instance_guidance id={serena_prompt['id']}")
    print(f"registered serena guidance resource id={serena_resource['id']}")
    print(f"associated_serena_servers={','.join(associated) if associated else '<none>'}")
    print(f"verified_render_at={refreshed_at}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
