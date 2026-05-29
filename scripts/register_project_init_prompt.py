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

Current project:
Project name: {{ project_name }}
Project root: {{ project_root }}
Canonical project hash: {{ project_root_hash }}

Initialization state from project .env when present; otherwise hook defaults:
Dialogue status: {{ dialogue_status }}
Serena decision: {{ serena_decision }}
Serena provision status: {{ serena_provision_status }}
Serena instance slug: {{ serena_instance_slug }}
Serena virtual server: {{ serena_server_name }}

Operate from current live evidence before making claims. Treat these values as advisory state only. If no project .env exists and the values are unasked or none, that is normal first-run hook default state, not a mismatch. Reconcile against ContextForge registry, user systemd units, server-instances manifests, project-local .codex/config.toml, and live MCP probes.

Ask the user whether to enable a project-local Serena backend when the decision is unasked. If they decline, preserve the ability to reverse that later by setting only the Serena decision state to declined. If they accept, provision through ContextForge-owned scripts from /home/dgk/workspace/context-portal and keep ContextForge in the path.

Before accepted Serena setup, run /home/dgk/workspace/context-portal/.venv/bin/python /home/dgk/workspace/context-portal/scripts/manage_serena_project_instance.py status --project-root with the canonical project root and --require-workspace. If status reports needs_user_language_choice, ask the user for Serena enablement and language before provisioning. Then use the reported recommended_command pattern, replacing LANGUAGE with the chosen language.

For accepted Serena setup, use /home/dgk/workspace/context-portal/.venv/bin/python /home/dgk/workspace/context-portal/scripts/manage_serena_project_instance.py create --project-root with the canonical project root, --require-workspace, --language when status requested it, --verify, and --app-server. The manager is responsible for one central Serena backend per project, ContextForge gateway and virtual server registration, project-local Codex .codex/config.toml binding, language-aware verification, and .env state updates after probes pass. Do not hand-write Codex app-server probe scripts unless the manager itself is broken.

If the project is empty and status reports needs_user_language_choice, do not silently default to Python and do not provision first. Ask for the Serena language up front, using recommended_language_examples as the user-facing examples.

Active Serena services for parent or child directories may appear in diagnostics. Treat them as related instances only. They must never satisfy setup for the canonical project root shown above unless the manifest project root exactly matches this root.

Never configure Serena globally. Never let Serena treat /, /home/dgk, or /home/dgk/workspace as the project. Do not use direct Serena stdio as the Codex-facing path. The Codex local alias may be serena, but the upstream virtual server name must be project-specific.

Completion evidence for this dialogue requires current proof that global Serena is absent from /home/dgk, project-local Serena points at the project-specific ContextForge virtual server, activate_project is filtered from the ContextForge/Codex exposed tool list, and the active project is the canonical root shown above. Prefer the manager's --verify --app-server JSON for these checks. If manual codex mcp get serena checks are needed, run project-local success and /home/dgk expected failure as separate commands so the expected global failure is not mistaken for an overall verification failure. LSP diagnostics or symbols must work through the actual exposed tool path when a language is configured; for empty projects without a selected language, report the manager's needs_user_language_choice state instead of claiming completion.
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
