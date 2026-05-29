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

from project_init_common import (
    ENV_PROJECT_INIT_STATUS,
    ENV_SERENA_DECISION,
    ENV_SERENA_INSTANCE_SLUG,
    ENV_SERENA_PROVISION_STATUS,
    ENV_SERENA_SERVER_NAME,
    PROJECT_INIT_ACTIVE_STATES,
    PROJECT_INIT_PROMPT_NAME,
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


def idempotency_key(session_id: str, root_hash: str) -> str:
    raw = f"{session_id}:{root_hash}:{PROMPT_VERSION}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def should_inject(project_root: Path, values: dict[str, str]) -> bool:
    status = values.get(ENV_PROJECT_INIT_STATUS)
    if safe_workspace_project_root(project_root):
        return status is None or status in PROJECT_INIT_ACTIVE_STATES
    env_exists = (project_root / ".env").exists()
    return env_exists and status in PROJECT_INIT_ACTIVE_STATES


def get_prompt_id(token: str) -> str | None:
    prompts = gateway._items(gateway._request("GET", "/prompts?include_inactive=true&limit=1000", token=token))
    for prompt in prompts:
        if prompt.get("name") == PROJECT_INIT_PROMPT_NAME or prompt.get("customName") == PROJECT_INIT_PROMPT_NAME:
            return str(prompt.get("id"))
    return None


def render_prompt(token: str, prompt_id: str, identity: Any, values: dict[str, str]) -> str:
    args = {
        "project_name": identity.root.name,
        "project_root": str(identity.root),
        "project_root_hash": identity.root_hash,
        "dialogue_status": values.get(ENV_PROJECT_INIT_STATUS, "unasked"),
        "serena_decision": values.get(ENV_SERENA_DECISION, "unasked"),
        "serena_provision_status": values.get(ENV_SERENA_PROVISION_STATUS, "none"),
        "serena_instance_slug": values.get(ENV_SERENA_INSTANCE_SLUG, ""),
        "serena_server_name": values.get(ENV_SERENA_SERVER_NAME, ""),
        "prompt_version": PROMPT_VERSION,
    }
    rendered = gateway._request("POST", f"/prompts/{prompt_id}", token=token, body=args)
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


def output_context(event_name: str, text: str) -> None:
    sys.stdout.write(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": event_name,
                    "additionalContext": text,
                }
            },
            separators=(",", ":"),
        )
    )


def main() -> int:
    payload = read_payload()
    if not payload:
        return 0

    event_name = str(payload.get("hook_event_name") or "")
    if event_name not in {"SessionStart", "UserPromptSubmit"}:
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
        if not should_inject(project_root, values):
            return 0

        key = idempotency_key(session_id, identity.root_hash)
        RUN_ROOT.mkdir(parents=True, exist_ok=True)
        with LOCK_PATH.open("a+", encoding="utf-8") as lock_handle:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
            state = load_state_locked(lock_handle)
            entries = state.setdefault("injected", {})
            if key in entries:
                return 0

            env = gateway._read_env(gateway.CONFIG_ENV)
            token = gateway._token(env["PLATFORM_ADMIN_EMAIL"], env["PLATFORM_ADMIN_PASSWORD"])
            prompt_id = get_prompt_id(token)
            if prompt_id is None:
                return 0
            text = render_prompt(token, prompt_id, identity, values)
            if not text:
                return 0

            entries[key] = {
                "session_id": session_id,
                "project_root": str(identity.root),
                "project_root_hash": identity.root_hash,
                "prompt_version": PROMPT_VERSION,
                "event_name": event_name,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            }
            write_state_locked(state)
        output_context(event_name, text)
    except Exception as exc:
        log_failure(f"fail-open {type(exc).__name__}: {exc}")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
