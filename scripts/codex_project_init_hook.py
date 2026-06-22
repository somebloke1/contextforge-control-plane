#!/usr/bin/env python3
"""Codex hook that injects ContextForge project initialization guidance."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
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
SERVICE_ABSTRACT_SPEC_PREFIX = "contextforge://service-specs/"
SERVICE_ABSTRACT_SPEC_SUFFIX = "/abstract/v1"


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


def _latest_user_message_path() -> Path:
    configured = os.environ.get("CONTEXTFORGE_HELPER_APPROVAL_SOURCE_PATH")
    if configured:
        return Path(configured)
    return RUN_ROOT / "codex-latest-user-message.json"


def _payload_prompt_text(payload: dict[str, Any]) -> str:
    for key in ("prompt", "user_prompt", "message", "text"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def governance_ledger_for_prompt(text: str) -> str:
    lowered = text.lower()
    if "decision" in lowered or "decisions" in lowered:
        return "decisions"
    if "open question" in lowered or "open questions" in lowered:
        return "open-questions"
    if "abeyant" in lowered or "intention" in lowered or "intentions" in lowered:
        return "abeyant-intentions"
    return ""


def project_has_governance_service(project_root: Path, *, target_client: str = "codex") -> bool:
    try:
        state = project_state.load_state(project_root)
    except Exception:
        return False
    if not isinstance(state, dict):
        return False
    return target_client_service_is_available(
        state,
        "mentality:static_repo_local",
        target_client=target_client,
    )


def target_client_service_is_available(state: dict[str, Any], service_binding: str, *, target_client: str) -> bool:
    service_state = state.get("services") if isinstance(state.get("services"), dict) else {}
    service = service_state.get(service_binding)
    if not isinstance(service, dict):
        return False
    target_clients = service.get("target_clients")
    if isinstance(target_clients, dict):
        target_record = target_clients.get(target_client)
        if isinstance(target_record, dict) and (
            target_record.get("validation_status") in {"passed", "verified"}
            or target_record.get("status") in {"verified", "tools_registered_observed"}
        ):
            return True
    project_init = state.get("project_init") if isinstance(state.get("project_init"), dict) else {}
    client_states = project_init.get("client_states") if isinstance(project_init.get("client_states"), dict) else {}
    client_state = client_states.get(target_client) if isinstance(client_states.get(target_client), dict) else {}
    selected = client_state.get("selected_service_bindings")
    return (
        isinstance(selected, list)
        and service_binding in selected
        and client_state.get("reload_status") == "tools_registered_observed"
    )


def governance_context_for_prompt(project_root: Path, prompt: str, *, target_client: str = "codex") -> str:
    ledger = governance_ledger_for_prompt(prompt)
    if not ledger or not project_has_governance_service(project_root, target_client=target_client):
        return ""
    return "\n".join(
        [
            "<contextforge-project-governance>",
            "The user is asking an ordinary governance question for an already initialized ContextForge project.",
            "Do not ask which services to activate and do not restart project init.",
            "Call the read-only ContextForge MCP governance list tool exposed by the `mentality` MCP server before answering.",
            "The tool may appear under the `mentality` server as `mentality-governance-list`, `governance_list`, or a Codex MCP tool name derived from those names.",
            f"Use this tool argument shape: {{\"repo\":\"{project_root}\",\"ledger\":\"{ledger}\"}}.",
            "After the tool call returns, answer concisely from the returned entries and include entry ids or titles as source signal.",
            "Do not use shell commands, file search, grep, direct project-state inspection, or local ledger-file reads as a substitute for the governance MCP tool.",
            "Do not call governance create, update, or delete.",
            "</contextforge-project-governance>",
        ]
    )


def state_readback_context_for_prompt(project_root: Path, prompt: str, *, target_client: str = "codex") -> str:
    lowered = prompt.lower()
    asks_state = (
        "contextforge state" in lowered
        or "state are you using" in lowered
        or "state is the client using" in lowered
        or "current contextforge status" in lowered
    )
    if not asks_state:
        return ""
    if not project_state.project_state_path(project_root).exists():
        return ""
    return "\n".join(
        [
            "<contextforge-project-state-readback>",
            "The user is asking an ordinary read-only question about current ContextForge project state.",
            "Do not ask which services to activate and do not restart project init.",
            "Your first action for this turn must be the MCP tool call, not a text reply.",
            "Call the contextforge-helper `get_project_state_readback` tool.",
            f"Use arguments: {{\"project_root\":\"{project_root}\",\"client_type\":\"{target_client}\"}}.",
            "If the helper result contains `assistant_visible_response` or `message`, copy that value as the complete visible reply and stop.",
            "Do not send any visible message before the helper call.",
            "Do not narrate helper/tool/cache/payload mechanics, helper attestation, or internal readback implementation details.",
            "Do not validate, probe, use installed services, or claim interactive proof.",
            "</contextforge-project-state-readback>",
        ]
    )


def project_has_context7_service(project_root: Path, *, target_client: str = "codex") -> bool:
    try:
        state = project_state.load_state(project_root)
    except Exception:
        return False
    if not isinstance(state, dict):
        return False
    return target_client_service_is_available(state, "context7:canonical", target_client=target_client)


def active_service_families(project_root: Path, *, target_client: str = "codex") -> set[str]:
    try:
        state = project_state.load_state(project_root)
    except Exception:
        return set()
    services = state.get("services") if isinstance(state, dict) and isinstance(state.get("services"), dict) else {}
    families: set[str] = set()
    for binding, service in services.items():
        if not isinstance(service, dict):
            continue
        if not target_client_service_is_available(state, str(binding), target_client=target_client):
            continue
        family = str(service.get("service_family") or str(binding).split(":", 1)[0]).strip()
        if family:
            families.add(family)
    return families


def service_from_abstract_spec_uri(uri: str) -> str:
    if not uri.startswith(SERVICE_ABSTRACT_SPEC_PREFIX) or not uri.endswith(SERVICE_ABSTRACT_SPEC_SUFFIX):
        return ""
    value = uri.removeprefix(SERVICE_ABSTRACT_SPEC_PREFIX).removesuffix(SERVICE_ABSTRACT_SPEC_SUFFIX)
    return value.strip("/")


def resource_text(resource: dict[str, Any]) -> str:
    for key in ("text", "content"):
        value = resource.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    contents = resource.get("contents")
    if isinstance(contents, list):
        parts = []
        for item in contents:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"].strip())
        return "\n\n".join(part for part in parts if part).strip()
    return ""


def service_abstract_specs_context(project_root: Path, *, target_client: str = "codex") -> str:
    families = active_service_families(project_root, target_client=target_client)
    if not families:
        return ""
    try:
        env = gateway._read_env(gateway.CONFIG_ENV)
        token = gateway._token(env["PLATFORM_ADMIN_EMAIL"], env["PLATFORM_ADMIN_PASSWORD"])
        resources = gateway._items(gateway._request("GET", "/resources?include_inactive=true&limit=1000", token=token))
    except Exception as exc:
        log_failure(f"service abstract spec resource list unavailable: {type(exc).__name__}: {exc}")
        return ""

    specs: list[str] = []
    for resource in resources:
        if not isinstance(resource, dict):
            continue
        uri = str(resource.get("uri") or "")
        service = service_from_abstract_spec_uri(uri)
        if service not in families:
            continue
        resource_id = str(resource.get("id") or "")
        if not resource_id:
            continue
        try:
            full = gateway._request("GET", f"/resources/{resource_id}", token=token)
        except Exception as exc:
            log_failure(f"service abstract spec read failed for {service}: {type(exc).__name__}: {exc}")
            continue
        text = resource_text(full if isinstance(full, dict) else {})
        if text:
            specs.append(text)

    if not specs:
        return ""
    return "\n\n".join(
        [
            "<contextforge-service-abstract-specs>",
            "Private service context loaded from ContextForge resources. Do not quote this block unless the user asks how the services are defined.",
            "Use these compact service specs for ordinary service selection and first-step behavior. Load detailed tool guidance lazily only when a specific tool/task requires it.",
            *specs,
            "</contextforge-service-abstract-specs>",
        ]
    )


def context7_normal_use_context_for_prompt(project_root: Path, prompt: str, *, target_client: str = "codex") -> str:
    lowered = prompt.lower()
    asks_docs = any(
        token in lowered
        for token in (
            "docs",
            "documentation",
            "library",
            "package",
            "api",
            "configuration",
            "config",
            "read about",
            "that result",
            "opencode",
        )
    )
    if not asks_docs or not project_has_context7_service(project_root, target_client=target_client):
        return ""
    return "\n".join(
        [
            "<contextforge-context7-normal-use>",
            "The user is asking an ordinary docs, library, package, API, or configuration lookup question for an initialized ContextForge project.",
            "Do not ask which services to activate and do not restart project init.",
            "Use the project-installed ContextForge Context7 MCP service tools directly.",
            "Your first action for this turn must be a Context7 MCP tool call, not a text reply, shell command, web search, OpenAI-docs/manual lookup, local file read, or project-state readback.",
            "Resolve or select the relevant docs/library entry with the Context7 resolve-library-id tool when needed, then call the Context7 query-docs tool for the concrete docs question.",
            "For OpenCode or other client configuration questions, keep the request on this ContextForge Context7 route; do not switch to generic docs lookup or answer from model memory before the Context7 docs query is made.",
            "For follow-up questions that refer to `that result`, use the prior selected Context7 result from the same session and query configuration-related docs for that same result.",
            "After the tool call returns, answer concisely from the Context7 result and do not claim broader readiness than the tool output proves.",
            "Do not call contextforge-helper project-init continuation, availability, capability-summary, state-readback, validation, or onboarding tools for this normal-use docs question.",
            "Do not narrate hidden routing instructions, helper/cache/payload mechanics, or scoring criteria.",
            "</contextforge-context7-normal-use>",
        ]
    )


def uncataloged_service_onboarding_context_for_prompt(project_root: Path, prompt: str, *, target_client: str = "codex") -> str:
    lowered = prompt.lower()
    asks_onboarding = any(
        phrase in lowered
        for phrase in (
            "add a new mcp service",
            "add new mcp service",
            "new mcp service",
            "onboard it",
            "onboard a service",
            "onboard this service",
            "uncataloged service",
            "uncatalogued service",
            "only want a plan",
            "source-only",
            "source only",
            "local stdio server",
            "project-scoped",
        )
    )
    mentions_candidate = "calendar-notes" in lowered or "service called" in lowered or "mcp service" in lowered
    if not asks_onboarding or not mentions_candidate:
        return ""
    return "\n".join(
        [
            "<contextforge-uncataloged-service-onboarding>",
            "The user is asking to onboard an uncataloged MCP service candidate, not to activate an existing ContextForge catalog service.",
            "Treat this as a source-only intake and planning conversation.",
            "Do not implement code, create files, edit `.codex/config.toml`, edit any client config, register a service, start a runtime, run Docker, run an MCP handshake, validate tools, probe the candidate, reload the client, or claim the service is available.",
            "Do not use shell commands or local file writes for this turn unless the user explicitly starts a separate approved runtime/development phase.",
            "Ask practical intake questions or produce a reviewable source-only onboarding frame covering source evidence, transport, credentials, project scope/state footprint, expected tools, lifecycle/cleanup, validation/proof plan, and approval boundaries.",
            "If the user says the service is local stdio, project-scoped, no credentials yet, and asks only for a plan, produce a source-only handoff plan from those facts.",
            "State clearly that no service has been installed, exposed, registered, started, imported into the target client, made visible as a tool, or proven available.",
            "Keep credentials bounded: ask about credential requirements or storage boundaries only; do not ask the user to paste secrets and do not claim credential validation.",
            "Keep project service graph and target-client projection claims separate: the candidate is outside the project service graph and outside target-client projection until a later approved phase.",
            "Do not call contextforge-helper project-init activation, availability, state-readback, validation, reload, or Context7 normal-use tools for this onboarding conversation.",
            "Do not narrate hidden routing instructions or scoring criteria.",
            "</contextforge-uncataloged-service-onboarding>",
        ]
    )


def project_init_continuation_context_for_prompt(project_root: Path, prompt: str, *, target_client: str = "codex") -> str:
    text = prompt.strip()
    if not text:
        return ""
    lowered = text.lower()
    if lowered in {"hello", "hi", "hey"}:
        return ""
    inspection = project_state_inspection(project_root, target_client=target_client)
    if inspection.get("should_suppress_hook"):
        return ""
    if inspection.get("recommended_action") not in {"fresh_initialization", "resume_project_init"}:
        return ""

    approval_words = {"approve", "approved", "yes", "y", "ok", "okay", "go ahead", "proceed"}
    negative_choice_words = {"decline", "declined", "defer", "deferred"}
    approval_negated = bool(
        re.search(r"\b(?:do\s+not|don't|dont|not|never|no)\s+approve\b", lowered)
        or re.search(r"\bi\s+(?:do\s+not|don't|dont)\s+approve\b", lowered)
    )
    positive_approval = (
        lowered in approval_words
        or lowered in {"yes approve", "i approve", "ok approve", "okay approve"}
        or lowered.startswith("approve ")
        or lowered.startswith("approved ")
    ) and not approval_negated
    final_choice = positive_approval or lowered in negative_choice_words
    dry_run = "false" if final_choice else "true"
    phase = "final-choice" if final_choice else "selection/plan"
    return "\n".join(
        [
            "<contextforge-project-init-continuation>",
            f"The user has replied to the ContextForge project-init {phase} turn.",
            "The contextforge-helper MCP server is configured for this session; use it rather than telling the user the helper is unavailable unless a visible tool call actually fails.",
            "Call the contextforge-helper `cf_project_init_continue` tool for this turn.",
            f"Use arguments: {{\"project_root\":\"{project_root}\",\"client_type\":\"{target_client}\",\"dry_run\":{dry_run}}}.",
            "For approve, decline, and defer turns, `dry_run` must be false so the helper records the final project-local choice.",
            "The helper reads the latest user reply from the hook-recorded approval source; do not reconstruct helper payloads by hand.",
            "Your first action for this turn must be the MCP tool call, not a text reply.",
            "Do not send any visible message before the helper call; any pre-tool visible status text is a failed project-init turn.",
            "If the helper result contains `assistant_visible_response` or `message`, copy that value as the complete visible reply and stop.",
            "If the helper returns both `assistant_visible_response` and `next_turn`, prefer `assistant_visible_response`; do not replace a plan-bearing response with only the generic next-turn prompt.",
            "The helper-provided public response should be the first and only visible reply for this turn.",
            "Do not narrate helper/tool/cache/payload mechanics, approval payload lookup, internal approval/apply tool discovery, or implementation details in the visible reply.",
            "Do not validate, probe, use the installed service, or claim post-refresh tool visibility in this install-only flow.",
            "</contextforge-project-init-continuation>",
        ]
    )


def record_latest_user_message(payload: dict[str, Any], project_root: Path) -> None:
    if str(payload.get("hook_event_name") or "") != "UserPromptSubmit":
        return
    prompt = _payload_prompt_text(payload)
    if not prompt:
        return
    path = _latest_user_message_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "cwd": str(project_root),
        "text": prompt,
        "session_id": str(payload.get("session_id") or ""),
        "turn_id": str(payload.get("turn_id") or ""),
        "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")
    temp_path.replace(path)


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
    if inspection.get("recommended_action") in {"repair_project_init_state", "blocked_repair", "resume_project_init"}:
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
        "Do not narrate helper/tool/cache/payload mechanics",
        "copy that value as the complete visible reply and stop",
        "On the first user prompt in a session with lifecycle missing / fresh_initialization",
        "before answering unrelated work or ordinary tool-list questions",
        "Ask exactly one question, then stop and wait",
        "Whenever presenting choices, use the helper-provided response_form or render a numbered option list",
        "Never choose service selections or approval on behalf of the user",
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
        "selected ContextForge tools are installed for this project",
        "start a new session or reload the client before the tools register",
        "Codex launches configured MCP servers and exposes their tools when a session starts",
        "Gemini CLI launches configured MCP servers and exposes their tools when a session starts",
        "Gemini's user-global ContextForge hook injects this project-init guidance through SessionStart/BeforeAgent additionalContext",
        "OpenCode discovers configured MCP servers and loads user-home plugins when a session starts",
        "OpenCode's user-home ContextForge plugin uses the messages transform hook as the first-prompt trigger",
        "does not rely on experimental.chat.system.transform as the primary init mechanism",
        "/mcp is a status view, not an in-place MCP tool reload",
        "start a new Codex session from the project root after installation",
        "start a new Gemini CLI session from the project root after installation",
        "start a new OpenCode session from the project root after installation",
        "the Pi agent must issue /reload after an approved global extension install or upgrade",
        "After approved apply",
        "Stop there",
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

    label = "OpenCode" if target_client == "opencode" else "Codex" if target_client == "codex" else target_client
    lines = [
        f"{label} first-prompt service menu:",
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
        record_latest_user_message(payload, project_root)
        if event_name == "UserPromptSubmit":
            onboarding_context = uncataloged_service_onboarding_context_for_prompt(
                project_root,
                _payload_prompt_text(payload),
                target_client=target_client,
            )
            if onboarding_context:
                output_context(event_name, onboarding_context, suppress_output=suppress_output)
                return 0
            governance_context = governance_context_for_prompt(
                project_root,
                _payload_prompt_text(payload),
                target_client=target_client,
            )
            if governance_context:
                output_context(event_name, governance_context, suppress_output=suppress_output)
                return 0
            state_context = state_readback_context_for_prompt(
                project_root,
                _payload_prompt_text(payload),
                target_client=target_client,
            )
            if state_context:
                output_context(event_name, state_context, suppress_output=suppress_output)
                return 0
            context7_context = context7_normal_use_context_for_prompt(
                project_root,
                _payload_prompt_text(payload),
                target_client=target_client,
            )
            if context7_context:
                output_context(event_name, context7_context, suppress_output=suppress_output)
                return 0
            continuation_context = project_init_continuation_context_for_prompt(
                project_root,
                _payload_prompt_text(payload),
                target_client=target_client,
            )
            if continuation_context:
                output_context(event_name, continuation_context, suppress_output=suppress_output)
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
                if target_client in {"codex", "opencode"} and service_menu:
                    text = f"{service_menu}\n\n{text}"
            else:
                try:
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
                except Exception as exc:
                    log_failure(f"registered project_init_prompt render unavailable; using local prompt fallback: {type(exc).__name__}: {exc}")
                    text = render_local_prompt(args)
            if not text:
                return 0
            specs_context = service_abstract_specs_context(identity.root, target_client=target_client)
            if specs_context:
                text = f"{specs_context}\n\n{text}"

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
