#!/usr/bin/env python3
"""Preserve ContextForge continuity before Codex context compaction."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


SNAPSHOT_SCHEMA = "contextforge-precompact-continuity/v1"
STATE_DIR_PARTS = ("run", "codex-precompact-continuity")
SENSITIVE_KEY_FRAGMENTS = ("api_key", "apikey", "authorization", "bearer", "password", "secret", "token")
PROJECT_ROADMAP = "docs/project-status-roadmap-2026-06-16.md"
MAX_EVENT_SNAPSHOTS = 100
MAX_SESSION_SNAPSHOTS = 50


def load_payload() -> dict[str, Any]:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def pick_nested(mapping: dict[str, Any], paths: tuple[tuple[str, ...], ...]) -> Any:
    for path in paths:
        current: Any = mapping
        for key in path:
            if not isinstance(current, dict) or key not in current:
                current = None
                break
            current = current[key]
        if current not in (None, ""):
            return current
    return None


def event_name(payload: dict[str, Any]) -> str:
    value = pick_nested(payload, (("hook_event_name",), ("hookEventName",), ("event",), ("event_name",)))
    return value if isinstance(value, str) else ""


def compaction_trigger(payload: dict[str, Any]) -> str:
    value = pick_nested(
        payload,
        (
            ("compaction_trigger",),
            ("compactionTrigger",),
            ("trigger",),
            ("params", "compaction_trigger"),
            ("params", "compactionTrigger"),
            ("params", "trigger"),
            ("payload", "compaction_trigger"),
            ("payload", "compactionTrigger"),
        ),
    )
    if isinstance(value, str) and value in {"manual", "auto"}:
        return value
    return "unknown"


def session_id(payload: dict[str, Any]) -> str | None:
    value = pick_nested(
        payload,
        (
            ("session_id",),
            ("sessionId",),
            ("thread_id",),
            ("threadId",),
            ("session", "id"),
            ("thread", "id"),
        ),
    )
    return value if isinstance(value, str) and value.strip() else os.environ.get("CODEX_THREAD_ID")


def turn_id(payload: dict[str, Any]) -> str | None:
    value = pick_nested(payload, (("turn_id",), ("turnId",)))
    return value if isinstance(value, str) and value.strip() else None


def stable_event_id(payload: dict[str, Any], repo_root: Path) -> str:
    fingerprint = {
        "event": event_name(payload),
        "trigger": compaction_trigger(payload),
        "session_id": session_id(payload),
        "turn_id": turn_id(payload),
        "repo_root": str(repo_root),
        "payload_keys": sorted(redacted_payload_keys(payload)),
    }
    digest = hashlib.sha256(json.dumps(fingerprint, sort_keys=True).encode("utf-8")).hexdigest()
    return digest[:24]


def session_key(payload: dict[str, Any], repo_root: Path) -> str | None:
    value = session_id(payload)
    if not value:
        return None
    digest = hashlib.sha256(f"{repo_root}:{value}".encode("utf-8")).hexdigest()
    return digest[:24]


def safe_identifier(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in {"-", "_", "."} else "-" for char in value.strip())
    return cleaned[:96] or "unknown"


def redacted_payload_keys(payload: dict[str, Any]) -> list[str]:
    keys: list[str] = []
    for key in payload:
        key_text = str(key)
        lowered = key_text.lower()
        if any(fragment in lowered for fragment in SENSITIVE_KEY_FRAGMENTS):
            keys.append(f"{key_text}:redacted")
        else:
            keys.append(key_text)
    return keys


def find_repo_root(cwd: Path) -> Path:
    result = run_command(["git", "rev-parse", "--show-toplevel"], cwd=cwd)
    if result["returncode"] == 0 and result["stdout"]:
        return Path(result["stdout"].strip()).resolve()
    return cwd.resolve()


def run_command(args: list[str], *, cwd: Path, timeout: float = 2.0) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            args,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except Exception as exc:
        return {"returncode": None, "stdout": "", "stderr": f"{type(exc).__name__}: {exc}"}
    return {
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def bounded_lines(text: str, *, limit: int = 80) -> list[str]:
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) <= limit:
        return lines
    return lines[:limit] + [f"... truncated {len(lines) - limit} additional lines"]


def git_snapshot(repo_root: Path) -> dict[str, Any]:
    head = run_command(["git", "rev-parse", "--short=12", "HEAD"], cwd=repo_root)
    branch = run_command(["git", "branch", "--show-current"], cwd=repo_root)
    status = run_command(["git", "status", "--short", "--branch"], cwd=repo_root)
    worktrees = run_command(["git", "worktree", "list"], cwd=repo_root)
    return {
        "head": head["stdout"] if head["returncode"] == 0 else None,
        "branch": branch["stdout"] if branch["returncode"] == 0 else None,
        "status_short": bounded_lines(status["stdout"]) if status["returncode"] == 0 else [],
        "worktrees": bounded_lines(worktrees["stdout"], limit=40) if worktrees["returncode"] == 0 else [],
    }


def roadmap_refs(repo_root: Path) -> list[str]:
    refs = [
        "AGENTS.md",
        "README.md",
        PROJECT_ROADMAP,
        "docs/contextforge-wrapper-lifecycle-runbook.md",
        "DECISIONS.md",
        "ABEYANT_INTENTIONS.md",
        "OPEN_QUESTIONS.md",
    ]
    return [ref for ref in refs if (repo_root / ref).exists()]


def build_snapshot(payload: dict[str, Any], *, cwd: Path | None = None, now: str | None = None) -> dict[str, Any]:
    actual_cwd = (cwd or Path.cwd()).resolve()
    repo_root = find_repo_root(actual_cwd)
    event_id = stable_event_id(payload, repo_root)
    key = session_key(payload, repo_root)
    snapshot = {
        "schema": SNAPSHOT_SCHEMA,
        "event_id": event_id,
        "created_at": now or time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "event_name": event_name(payload) or "unknown",
        "compaction_trigger": compaction_trigger(payload),
        "session_id_present": key is not None,
        "session_key": key,
        "authority_scope": "session" if key else "event-only",
        "repo_root": str(repo_root),
        "cwd": str(actual_cwd),
        "project_name": "ContextForge",
        "legacy_path_name": "context-portal",
        "mission": (
            "Preserve ContextForge project-local continuity evidence without overriding the active task, "
            "the user-selected goal, or Codex's default compaction summary."
        ),
        "continuity_protocol": [
            "After compaction, re-anchor on ContextForge naming; treat context-portal as a legacy path/runtime identifier only.",
            "Refresh current evidence before trusting roadmap claims, memory, or stale summaries.",
            "Preserve unrelated dirty work and keep branch/PR slices isolated from dev-root.",
            "Keep the default Codex compaction prompt intact; this hook is additive continuity state only.",
            "Continue the active session's task; do not let another session's compaction snapshot redefine the mission.",
            "When operating as roadmap conductor, complete a goal-maintenance/refinement pass before moving to the next roadmap loop.",
        ],
        "roadmap_refs": roadmap_refs(repo_root),
        "git": git_snapshot(repo_root),
        "payload_keys": redacted_payload_keys(payload),
    }
    return snapshot


def render_markdown(snapshot: dict[str, Any]) -> str:
    git_info = snapshot.get("git") if isinstance(snapshot.get("git"), dict) else {}
    status_lines = git_info.get("status_short") if isinstance(git_info.get("status_short"), list) else []
    refs = snapshot.get("roadmap_refs") if isinstance(snapshot.get("roadmap_refs"), list) else []
    protocol = snapshot.get("continuity_protocol") if isinstance(snapshot.get("continuity_protocol"), list) else []
    lines = [
        "# ContextForge Pre-Compaction Continuity Snapshot",
        "",
        f"- created_at: `{snapshot.get('created_at')}`",
        f"- event_id: `{snapshot.get('event_id')}`",
        f"- compaction_trigger: `{snapshot.get('compaction_trigger')}`",
        f"- authority_scope: `{snapshot.get('authority_scope')}`",
        f"- session_key: `{snapshot.get('session_key')}`",
        f"- repo_root: `{snapshot.get('repo_root')}`",
        f"- branch: `{git_info.get('branch') or 'unknown'}`",
        f"- head: `{git_info.get('head') or 'unknown'}`",
        "",
        "## Mission",
        "",
        str(snapshot.get("mission") or ""),
        "",
        "## Continuity Protocol",
        "",
    ]
    lines.extend(f"{index}. {item}" for index, item in enumerate(protocol, start=1))
    lines.extend(["", "## Roadmap Refs", ""])
    lines.extend(f"- `{ref}`" for ref in refs)
    lines.extend(["", "## Git Status", ""])
    if status_lines:
        lines.extend(f"- `{line}`" for line in status_lines)
    else:
        lines.append("- clean or unavailable")
    lines.extend(
        [
            "",
            "## Compaction Quality Guard",
            "",
            "This project hook does not set `compact_prompt`, `experimental_compact_prompt_file`, or "
            "`model_auto_compact_token_limit`. Codex's default compaction prompt remains authoritative.",
            "",
        ]
    )
    return "\n".join(lines)


def write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temp_path.write_text(content, encoding="utf-8")
    temp_path.replace(path)


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    write_text_atomic(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def mtime_ns(path: Path) -> int:
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return 0


def prune_files_by_mtime(paths: list[Path], *, keep_path: Path, limit: int) -> None:
    limit = max(1, limit)
    ordered = sorted(paths, key=lambda path: (mtime_ns(path), path.name), reverse=True)
    survivors: list[Path] = []
    survivor_set: set[Path] = set()
    for path in [keep_path, *ordered]:
        resolved = path.resolve()
        if resolved in survivor_set:
            continue
        survivors.append(path)
        survivor_set.add(resolved)
        if len(survivors) >= limit:
            break
    for path in ordered:
        if path.resolve() in survivor_set:
            continue
        try:
            path.unlink()
        except OSError:
            pass


def session_dir_sort_key(path: Path) -> tuple[int, str]:
    return (mtime_ns(path / "latest.json") or mtime_ns(path), path.name)


def prune_session_dirs(sessions_dir: Path, *, keep_dir: Path | None, limit: int) -> None:
    if not sessions_dir.exists():
        return
    limit = max(1, limit)
    session_dirs = [path for path in sessions_dir.iterdir() if path.is_dir()]
    ordered = sorted(session_dirs, key=session_dir_sort_key, reverse=True)
    survivors: list[Path] = []
    survivor_set: set[Path] = set()
    if keep_dir is not None:
        survivors.append(keep_dir)
        survivor_set.add(keep_dir.resolve())
    for path in ordered:
        resolved = path.resolve()
        if resolved in survivor_set:
            continue
        survivors.append(path)
        survivor_set.add(resolved)
        if len(survivors) >= limit:
            break
    for path in ordered:
        if path.resolve() in survivor_set:
            continue
        try:
            shutil.rmtree(path)
        except OSError:
            pass


def remove_legacy_global_latest(state_dir: Path) -> None:
    for name in ("latest.json", "latest.md"):
        path = state_dir / name
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            pass


def enforce_retention(state_dir: Path, *, keep_event: Path, keep_session_dir: Path | None) -> None:
    remove_legacy_global_latest(state_dir)
    events_dir = state_dir / "events"
    if events_dir.exists():
        prune_files_by_mtime(list(events_dir.glob("*.json")), keep_path=keep_event, limit=MAX_EVENT_SNAPSHOTS)
    prune_session_dirs(state_dir / "sessions", keep_dir=keep_session_dir, limit=MAX_SESSION_SNAPSHOTS)


def persist_snapshot(snapshot: dict[str, Any], repo_root: Path) -> dict[str, str]:
    state_dir = repo_root.joinpath(*STATE_DIR_PARTS)
    lock_path = state_dir / "contextforge-precompact-continuity.local.lock"
    state_dir.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a", encoding="utf-8") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        event_id = safe_identifier(str(snapshot.get("event_id") or "unknown"))
        event_path = state_dir / "events" / f"{event_id}.json"
        session_value = snapshot.get("session_key")
        session_dir = state_dir / "sessions" / safe_identifier(str(session_value)) if session_value else None
        write_json_atomic(event_path, snapshot)
        paths = {"event": str(event_path.relative_to(repo_root))}
        if session_dir is not None:
            session_latest_json = session_dir / "latest.json"
            session_latest_md = session_dir / "latest.md"
            write_json_atomic(session_latest_json, snapshot)
            write_text_atomic(session_latest_md, render_markdown(snapshot))
            paths["session_latest_json"] = str(session_latest_json.relative_to(repo_root))
            paths["session_latest_markdown"] = str(session_latest_md.relative_to(repo_root))
        enforce_retention(state_dir, keep_event=event_path, keep_session_dir=session_dir)
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
    return paths


def additional_context(paths: dict[str, str]) -> str:
    latest = paths.get("session_latest_markdown")
    if not latest:
        event = paths.get("event", "run/codex-precompact-continuity/events/unknown.json")
        return (
            f"ContextForge event-only pre-compaction snapshot refreshed at `{event}`. "
            "No session id was supplied, so no post-compaction session pointer was written. "
            "Use Codex's default compaction summary and active goal as authoritative continuity state."
        )
    return (
        f"ContextForge session-scoped pre-compaction snapshot refreshed at `{latest}`. "
        "Use it as additive continuity evidence after compaction; keep Codex's default compaction prompt and active goal authoritative. "
        "Do not let ad-hoc session evidence redefine the project roadmap conductor state."
    )


def session_start_context(repo_root: Path, payload: dict[str, Any]) -> dict[str, Any] | None:
    key = session_key(payload, repo_root)
    if not key:
        return None
    latest_md = repo_root.joinpath(*STATE_DIR_PARTS, "sessions", safe_identifier(key), "latest.md")
    if not latest_md.exists():
        return None
    return {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": (
                "ContextForge compaction just completed. Read "
                f"`{latest_md.relative_to(repo_root)}` as session-scoped additive continuity evidence; "
                "keep Codex's default compaction summary and the active goal authoritative. "
                "Do not adopt another session's ad-hoc compaction snapshot as project mission state."
            ),
        }
    }


def run(payload: dict[str, Any], *, cwd: Path | None = None, now: str | None = None) -> dict[str, Any] | None:
    actual_cwd = (cwd or Path.cwd()).resolve()
    repo_root = find_repo_root(actual_cwd)
    name = event_name(payload)
    if name == "SessionStart":
        source = pick_nested(payload, (("source",),))
        if source == "compact":
            return session_start_context(repo_root, payload)
        return None
    if name and name != "PreCompact":
        return None
    snapshot = build_snapshot(payload, cwd=actual_cwd, now=now)
    repo_root = Path(str(snapshot["repo_root"]))
    paths = persist_snapshot(snapshot, repo_root)
    return {
        "systemMessage": additional_context(paths),
        "suppressOutput": True,
    }


def main() -> int:
    payload = load_payload()
    try:
        output = run(payload)
    except Exception:
        return 0
    if output:
        print(json.dumps(output, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
