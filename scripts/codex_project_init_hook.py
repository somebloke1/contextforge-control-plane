#!/usr/bin/env python3
"""Codex hook that injects ContextForge project initialization guidance."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import contextforge_mcp_wrapper as gateway
import control_plane_project_state as project_state
import register_project_init_prompt as project_init_prompt

from project_init_common import (
    ENV_PROJECT_INIT_STATUS,
    ENV_SERENA_DECISION,
    ENV_SERENA_INSTANCE_SLUG,
    ENV_SERENA_PROVISION_STATUS,
    ENV_SERENA_SERVER_NAME,
    PROJECT_INIT_ACTIVE_STATES,
    PROJECT_INIT_PROMPT_NAME,
    PROJECT_INIT_RESOURCE_NAME,
    PROJECT_INIT_RESOURCE_URI,
    PROMPT_VERSION,
    RUN_ROOT,
    detect_project_root,
    project_identity,
    read_project_env,
    safe_workspace_project_root,
)


STATE_PATH = RUN_ROOT / "project-init-hook-state.local.json"
LOCK_PATH = RUN_ROOT / "project-init-hook-state.local.lock"
LOG_PATH = RUN_ROOT / "project-init-hook.local.log"
CODEX_HOOK_EVENTS = frozenset({"SessionStart", "UserPromptSubmit"})


def log_failure(message: str) -> None:
    try:
        RUN_ROOT.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} {message}\n")
    except Exception:
        pass


def read_payload() -> dict[str, Any] | None:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return None
        payload = json.loads(raw)
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def load_state_locked(handle: Any) -> dict[str, Any]:
    try:
        if STATE_PATH.exists():
            data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}
    return {}


def write_state_locked(state: dict[str, Any]) -> None:
    temp_path = STATE_PATH.with_suffix(".tmp")
    temp_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp_path.replace(STATE_PATH)


def idempotency_key(session_id: str, root_hash: str, *, target_client: str = "codex") -> str:
    raw = f"{target_client}:{session_id}:{root_hash}:{PROMPT_VERSION}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def should_inject(project_root: Path, values: dict[str, str], *, target_client: str = "codex") -> bool:
    inspection = project_state_inspection(project_root, target_client=target_client)
    if inspection.get("should_suppress_hook"):
        return False
    if inspection.get("recommended_action") in {"repair_project_init_state", "blocked_repair", "resume_validation"}:
        return True
    status = values.get(ENV_PROJECT_INIT_STATUS)
    if safe_workspace_project_root(project_root):
        return status is None or status in PROJECT_INIT_ACTIVE_STATES
    env_exists = (project_root / ".env").exists()
    return env_exists and status in PROJECT_INIT_ACTIVE_STATES


def project_state_inspection(project_root: Path, *, target_client: str | None = None) -> dict[str, Any]:
    try:
        return project_state.inspect_project_init_state(project_root, target_client=target_client)
    except Exception as exc:
        return {
            "lifecycle_status": "invalid_blocked",
            "raw_status": None,
            "schema_error": f"{type(exc).__name__}: {exc}",
            "project_init_present": False,
            "hook_prompt_state": project_state.HOOK_PROMPT_ACTIVE,
            "recommended_action": "blocked_repair",
            "should_suppress_hook": False,
        }


def project_state_status(project_root: Path, *, target_client: str | None = None) -> str:
    inspection = project_state_inspection(project_root, target_client=target_client)
    if inspection.get("lifecycle_status") == "missing":
        return "uninitialized"
    if inspection.get("lifecycle_status") != "valid":
        return str(inspection.get("lifecycle_status") or "invalid_or_unreadable")
    return str(inspection.get("raw_status") or "unknown")


def get_prompt_record(token: str) -> dict[str, Any] | None:
    prompts = gateway._items(gateway._request("GET", "/prompts?include_inactive=true&limit=1000", token=token))
    for prompt in prompts:
        if prompt.get("name") == PROJECT_INIT_PROMPT_NAME or prompt.get("customName") == PROJECT_INIT_PROMPT_NAME:
            return prompt
    return None


def get_prompt_id(token: str) -> str | None:
    prompt = get_prompt_record(token)
    return str(prompt.get("id")) if prompt and prompt.get("id") else None


def get_project_init_resource_record(token: str) -> dict[str, Any] | None:
    resources = gateway._items(gateway._request("GET", "/resources?include_inactive=true&limit=1000", token=token))
    for resource in resources:
        if resource.get("uri") == PROJECT_INIT_RESOURCE_URI:
            return resource
    return None


def _tag_names(values: Any) -> set[str]:
    if not isinstance(values, list):
        return set()
    tags: set[str] = set()
    for value in values:
        if isinstance(value, str):
            tags.add(value)
        elif isinstance(value, dict):
            name = value.get("name") or value.get("label")
            if name:
                tags.add(str(name))
    return tags


def prompt_record_is_fresh(prompt: dict[str, Any] | None) -> bool:
    if not prompt or not prompt.get("id"):
        return False
    return PROMPT_VERSION in _tag_names(prompt.get("tags"))


def resource_record_is_fresh(resource: dict[str, Any] | None) -> bool:
    if not resource or not resource.get("id"):
        return False
    if resource.get("uri") != PROJECT_INIT_RESOURCE_URI:
        return False
    return PROMPT_VERSION in _tag_names(resource.get("tags"))


def render_prompt(token: str, prompt_id: str, identity: Any, values: dict[str, str], *, target_client: str = "codex") -> str:
    args = prompt_args(identity, values, target_client=target_client)
    rendered = gateway._request("POST", f"/prompts/{prompt_id}", token=token, body=args)
    text = rendered_prompt_text(rendered)
    if prompt_text_is_fresh(text):
        return text
    log_failure("registered project_init_prompt is stale; attempting prompt/resource self-upgrade")
    upgraded_prompt_id = upgrade_project_init_prompt(token)
    if upgraded_prompt_id:
        try:
            rendered = gateway._request("POST", f"/prompts/{upgraded_prompt_id}", token=token, body=args)
            text = rendered_prompt_text(rendered)
            if prompt_text_is_fresh(text):
                log_failure("registered project_init_prompt self-upgrade succeeded")
                return text
        except Exception as exc:
            log_failure(f"registered project_init_prompt self-upgrade render failed: {type(exc).__name__}: {exc}")
    log_failure("registered project_init_prompt is stale; using local prompt template fallback")
    return render_local_prompt(args)


def upgrade_project_init_prompt(token: str) -> str | None:
    try:
        project_init_prompt.upsert_resource(
            token,
            name=PROJECT_INIT_RESOURCE_NAME,
            uri=PROJECT_INIT_RESOURCE_URI,
            content=project_init_prompt.PROJECT_INIT_TEXT,
            description="ContextForge project initialization guidance for Codex hooks.",
            tags=["contextforge", "project-init", PROMPT_VERSION],
        )
        prompt = project_init_prompt.upsert_prompt(
            token,
            name=PROJECT_INIT_PROMPT_NAME,
            template=project_init_prompt.PROJECT_INIT_TEXT,
            description="Render project initialization guidance for a detected Codex project.",
            tags=["contextforge", "project-init", PROMPT_VERSION],
        )
        return project_init_prompt.prompt_id(prompt)
    except Exception as exc:
        log_failure(f"registered project_init_prompt self-upgrade failed: {type(exc).__name__}: {exc}")
        return None


def prompt_args(identity: Any, values: dict[str, str], *, target_client: str = "codex") -> dict[str, str]:
    inspection = project_state_inspection(identity.root, target_client=target_client)
    return {
        "project_name": identity.root.name,
        "project_root": str(identity.root),
        "target_client": target_client,
        "project_root_hash": identity.root_hash,
        "dialogue_status": values.get(ENV_PROJECT_INIT_STATUS, "unasked"),
        "serena_decision": values.get(ENV_SERENA_DECISION, "unasked"),
        "serena_provision_status": values.get(ENV_SERENA_PROVISION_STATUS, "none"),
        "serena_instance_slug": values.get(ENV_SERENA_INSTANCE_SLUG, ""),
        "serena_server_name": values.get(ENV_SERENA_SERVER_NAME, ""),
        "project_state_path": str(project_state.project_state_path(identity.root)),
        "project_state_status": project_state_status(identity.root, target_client=target_client),
        "project_state_lifecycle_status": str(inspection.get("lifecycle_status") or "unknown"),
        "project_state_recommended_action": str(inspection.get("recommended_action") or "unknown"),
        "project_state_schema_error": str(inspection.get("schema_error") or ""),
        "project_init_hook_prompt_state": str(inspection.get("hook_prompt_state") or project_state.HOOK_PROMPT_ACTIVE),
        "prompt_version": PROMPT_VERSION,
    }


def rendered_prompt_text(rendered: Any) -> str:
    messages = rendered.get("messages") if isinstance(rendered, dict) else None
    if isinstance(messages, list) and messages:
        parts: list[str] = []
        for message in messages:
            content = message.get("content") if isinstance(message, dict) else None
            if isinstance(content, dict):
                text = content.get("text") or content.get("content")
            else:
                text = content
            if text:
                parts.append(str(text))
        text = "\n\n".join(parts).strip()
        if text:
            return text
    return str(rendered).strip()


def prompt_text_is_fresh(text: str) -> bool:
    required = (
        "This is model-visible control context. Do not echo this context to the user.",
        "hidden or structured prompt/context injection",
        "User-visible UI should be limited to information that requires user understanding or response",
        "On the first user prompt in a session with lifecycle missing / fresh_initialization",
        "before answering unrelated work or ordinary tool-list questions",
        "Ask exactly one question, then stop and wait",
        "Whenever presenting choices, use the helper-provided response_form or render a numbered option list",
        "Never choose service selections, approval, reload acknowledgement, validation, or skipped-service follow-up actions on behalf of the user",
        "If the user echoes your question, asks you to provide the selection numbers",
        "Prefer the contextforge-helper workflow tools when visible",
        "Do not invoke project-init helper scripts or Python modules through shell as a substitute for visible helper tools",
        "For every contextforge-helper project-init call, pass client_type=",
        "Which ContextForge services should I activate for this project?",
        ".project/context_forge_state.json is the project initialization authority",
        "Project init may write only target-client project-local activation state",
        "for Codex this is project-local .codex/config.toml",
        "for Gemini this is project-local .gemini/settings.json",
        "for OpenCode this is project-local opencode.json plus .project/context_forge_state.json",
        "global Gemini hook and contextforge-helper bootstrap entries",
        "user-home OpenCode ContextForge plugin and contextforge-helper bootstrap entries",
        "for Pi this is .project/context_forge_state.json records",
        "input-triggered hidden message",
        "cf_project_init_prompt and cf_contextforge_pi_readback are diagnostic only",
        "do not print or summarize raw cf_contextforge_pi_readback JSON",
        "client_reload_requirement that blocks validation",
        "explicit client reload or new-session action first and stop",
        "Codex launches configured MCP servers and exposes their tools when a session starts",
        "Gemini CLI launches configured MCP servers and exposes their tools when a session starts",
        "Gemini's user-global ContextForge hook injects this project-init guidance through SessionStart/BeforeAgent additionalContext",
        "OpenCode discovers configured MCP servers and loads user-home plugins when a session starts",
        "OpenCode's user-home ContextForge plugin uses the chat.message hook as the first-prompt trigger",
        "does not rely on experimental.chat.system.transform as the primary init mechanism",
        "/mcp is a status view, not an in-place MCP tool reload",
        "start a new Codex session from the project root before target-client-visible validation",
        "start a new Gemini CLI session from the project root before target-client-visible validation",
        "start a new OpenCode session from the project root before target-client-visible validation",
        'choose 1 or reply "validate" to run validation',
        "first call cf_project_init_record_client_reload",
        "with client_type=",
        "prefer that tool with client_type=opencode",
        "pass validation mode validate_now or presume_working to the reload call",
        "honor that choice instead of asking again",
        "the Pi agent must issue /reload before validation",
        "Choose 1 to validate now",
        "cf_contextforge_pi_validate for validate-now",
        "Do not call unlisted or unavailable validation tool names",
        "If a validation tool call is missing, not found, unavailable, or returns an error, validation did not pass",
        "Backend-only ContextForge health and \"tool exists\" availability are not enough",
        "Serena is one project-scoped option in this menu, not the whole flow",
        "pass the selected service ids/bindings back to contextforge-helper",
        "Do not invent or pass local_approval_event_ref strings",
        "prefer those cached id/digest tools over reconstructing a full plan object",
        "do not reconstruct the full plan object from visible text",
        "call cf_project_init_approve with the exact challenge id and plan digest",
        "call cf_project_init_apply using the cached plan and receipts",
        "status=config_conflict with an embedded recovery_plan",
        "call cf_project_init_recovery_approve with the exact recovery challenge id and recovery plan digest",
        "call cf_project_init_recovery_apply using the cached recovery plan and receipts",
        "Do not call apply_project_init_recovery with only plan_id, plan_digest, or receipt ids",
        "complete helper-returned recovery plan object and full receipt objects",
        "keep them together in the helper recovery approval/apply path",
        "If helper cache is missing or stale",
        "do not silently replace the challenge id",
        "Lifecycle:",
        "repair_project_init_state",
        "do not restart service selection",
    )
    return all(item in text for item in required)


def render_local_prompt(args: dict[str, str]) -> str:
    text = project_init_prompt.PROJECT_INIT_TEXT
    for key, value in args.items():
        text = text.replace("{{ " + key + " }}", value)
        text = text.replace("{{" + key + "}}", value)
        text = text.replace("{" + key + "}", value)
    return text


def render_helper_service_menu(project_root: Path, *, target_client: str) -> str:
    try:
        import control_plane_project_init_helper as helper

        capabilities = helper.list_available_capabilities(project_root=project_root, client_type=target_client)
    except Exception as exc:
        log_failure(f"helper capability menu render failed: {type(exc).__name__}: {exc}")
        return ""

    next_turn = capabilities.get("next_turn") if isinstance(capabilities, dict) else None
    choices = next_turn.get("choices") if isinstance(next_turn, dict) else None
    if not isinstance(choices, list) or not choices:
        return ""

    lines = [
        "OpenCode first-prompt service menu:",
        'Ask exactly: "Which ContextForge services should I activate for this project?"',
        "Then show this numbered list of helper-discovered choices and stop for the user's reply:",
    ]
    for index, choice in enumerate(choices, start=1):
        if not isinstance(choice, dict):
            continue
        label = str(choice.get("label") or choice.get("id") or f"Choice {index}")
        identifier = str(choice.get("id") or "").strip()
        effect = str(choice.get("effect") or choice.get("description") or "").strip()
        suffix = f" - {effect}" if effect else ""
        if identifier and identifier.lower() != label.lower():
            lines.append(f"{index}. {identifier} - {label}{suffix}")
        else:
            lines.append(f"{index}. {label}{suffix}")
    lines.extend(
        [
            "",
            "Do not write project state or target-client config during this first-prompt offer.",
            "Do not choose services for the user.",
        ]
    )
    return "\n".join(lines)


def should_render_fresh_initialization_locally(args: dict[str, str]) -> bool:
    return (
        args.get("project_state_lifecycle_status") == "missing"
        and args.get("project_state_recommended_action") == "fresh_initialization"
    )


def output_context(event_name: str, text: str, *, suppress_output: bool = False) -> None:
    payload: dict[str, Any] = {
        "hookSpecificOutput": {
            "hookEventName": event_name,
            "additionalContext": text,
        }
    }
    if suppress_output:
        payload["suppressOutput"] = True
    sys.stdout.write(json.dumps(payload, separators=(",", ":")))


def main_for_events(
    allowed_events: set[str] | frozenset[str],
    *,
    suppress_output: bool = False,
    target_client: str = "codex",
) -> int:
    payload = read_payload()
    if not payload:
        return 0

    event_name = str(payload.get("hook_event_name") or "")
    if event_name not in allowed_events:
        return 0
    session_id = str(payload.get("session_id") or "")
    cwd = payload.get("cwd") or os.getcwd()
    if not session_id:
        return 0

    try:
        project_root = detect_project_root(cwd)
        if project_root is None:
            return 0
        identity = project_identity(project_root)
        values = read_project_env(project_root)
        if not should_inject(project_root, values, target_client=target_client):
            return 0

        key = idempotency_key(session_id, identity.root_hash, target_client=target_client)
        RUN_ROOT.mkdir(parents=True, exist_ok=True)
        with LOCK_PATH.open("a+", encoding="utf-8") as lock_handle:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
            state = load_state_locked(lock_handle)
            entries = state.setdefault("injected", {})
            if key in entries:
                return 0

            args = prompt_args(identity, values, target_client=target_client)
            if should_render_fresh_initialization_locally(args):
                text = render_local_prompt(args)
                service_menu = render_helper_service_menu(identity.root, target_client=target_client)
                if target_client == "opencode" and service_menu:
                    text = f"{service_menu}\n\n{text}"
            else:
                env = gateway._read_env(gateway.CONFIG_ENV)
                token = gateway._token(env["PLATFORM_ADMIN_EMAIL"], env["PLATFORM_ADMIN_PASSWORD"])
                prompt = get_prompt_record(token)
                resource = get_project_init_resource_record(token)
                prompt_id = str(prompt.get("id")) if prompt and prompt.get("id") else None
                if prompt_id is None:
                    log_failure("registered project_init_prompt is missing; attempting prompt/resource self-upgrade")
                    prompt_id = upgrade_project_init_prompt(token)
                elif not prompt_record_is_fresh(prompt):
                    log_failure("registered project_init_prompt metadata is stale; attempting prompt/resource self-upgrade")
                    prompt_id = upgrade_project_init_prompt(token) or prompt_id
                elif not resource_record_is_fresh(resource):
                    log_failure("registered project_init_resource metadata is missing or stale; attempting prompt/resource self-upgrade")
                    prompt_id = upgrade_project_init_prompt(token) or prompt_id
                text = (
                    render_prompt(token, prompt_id, identity, values, target_client=target_client)
                    if prompt_id
                    else render_local_prompt(args)
                )
            if not text:
                return 0

            entries[key] = {
                "session_id": session_id,
                "project_root": str(identity.root),
                "project_root_hash": identity.root_hash,
                "prompt_version": PROMPT_VERSION,
                "target_client": target_client,
                "event_name": event_name,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            }
            write_state_locked(state)
        output_context(event_name, text, suppress_output=suppress_output)
    except Exception as exc:
        log_failure(f"fail-open {type(exc).__name__}: {exc}")
        return 0
    return 0


def main() -> int:
    return main_for_events(CODEX_HOOK_EVENTS)


if __name__ == "__main__":
    raise SystemExit(main())
