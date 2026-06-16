#!/usr/bin/env python3
"""Read-only planner for ContextForge user-global Codex config migration.

This report is intentionally non-mutating. It classifies stale
``/home/dgk/workspace/context-portal`` entries in ``~/.codex/config.toml`` and
builds an approval-ready plan for moving active global Codex surfaces to the
clean ContextForge worktree.
"""

from __future__ import annotations

import argparse
import json
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


REPORT_SCHEMA_URI = "contextforge://control-plane/codex-global-config-migration-plan/v1"
DEFAULT_LEGACY_ROOT = Path("/home/dgk/workspace/context-portal")
DEFAULT_CONFIG_PATH = Path("~/.codex/config.toml")


@dataclass(frozen=True)
class EntryPlan:
    entry_id: str
    bucket: str
    recommendation: str
    risk: str
    readback_check: str
    current_value: Any
    target_value: Any
    lines: tuple[int, ...] = ()


def _canonical(path: str | Path) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _line_numbers(text: str, *needles: str) -> tuple[int, ...]:
    lines: list[int] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if any(needle and needle in line for needle in needles):
            lines.append(number)
    return tuple(lines)


def _toml_table_lines(text: str, header: str) -> tuple[int, ...]:
    lines = text.splitlines()
    collected: list[int] = []
    inside = False
    for number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped == header:
            inside = True
            collected.append(number)
            continue
        if inside and stripped.startswith("[") and stripped.endswith("]"):
            break
        if inside and stripped:
            collected.append(number)
    return tuple(collected)


def _hook_event_command_lines(text: str, event_name: str, script_name: str) -> tuple[int, ...]:
    lines = text.splitlines()
    collected: list[int] = []
    inside = False
    event_prefix = f"[[hooks.{event_name}"
    for number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped == f"[[hooks.{event_name}]]":
            inside = True
            continue
        if inside and stripped.startswith("[[hooks.") and not stripped.startswith(event_prefix):
            break
        if inside and script_name in stripped:
            collected.append(number)
    return tuple(collected)


def _legacy_replaced(value: str, *, legacy_root: Path, target_root: Path) -> str:
    return value.replace(str(legacy_root), str(target_root))


def _hook_commands(config: Mapping[str, Any], event_name: str) -> list[str]:
    hooks = ((config.get("hooks") or {}).get(event_name) or [])
    commands: list[str] = []
    if not isinstance(hooks, list):
        return commands
    for event in hooks:
        if not isinstance(event, Mapping):
            continue
        for hook in event.get("hooks") or []:
            if isinstance(hook, Mapping) and isinstance(hook.get("command"), str):
                commands.append(hook["command"])
    return commands


def _hook_state(config: Mapping[str, Any]) -> Mapping[str, Any]:
    hooks = config.get("hooks") if isinstance(config.get("hooks"), Mapping) else {}
    state = hooks.get("state") if isinstance(hooks.get("state"), Mapping) else {}
    return state if isinstance(state, Mapping) else {}


def _entry_dict(entry: EntryPlan) -> dict[str, Any]:
    return {
        "entry_id": entry.entry_id,
        "bucket": entry.bucket,
        "recommendation": entry.recommendation,
        "risk": entry.risk,
        "readback_check": entry.readback_check,
        "current_value": entry.current_value,
        "target_value": entry.target_value,
        "lines": list(entry.lines),
        "requires_approval": True,
    }


def build_report(
    *,
    config_path: str | Path = DEFAULT_CONFIG_PATH,
    target_root: str | Path,
    legacy_root: str | Path = DEFAULT_LEGACY_ROOT,
    approval_acknowledged: bool = False,
    approval_ref: str | None = None,
) -> dict[str, Any]:
    config_file = _canonical(config_path)
    target = _canonical(target_root)
    legacy = _canonical(legacy_root)
    text = config_file.read_text(encoding="utf-8")
    config = tomllib.loads(text)
    legacy_text = str(legacy)
    target_text = str(target)

    mcp_servers = config.get("mcp_servers") if isinstance(config.get("mcp_servers"), Mapping) else {}
    helper = mcp_servers.get("contextforge-helper") if isinstance(mcp_servers.get("contextforge-helper"), Mapping) else {}
    helper_command = str(helper.get("command") or "")
    helper_args = [str(arg) for arg in helper.get("args") or []]

    projects = config.get("projects") if isinstance(config.get("projects"), Mapping) else {}
    legacy_project = projects.get(legacy_text) if isinstance(projects.get(legacy_text), Mapping) else None
    target_project = projects.get(target_text) if isinstance(projects.get(target_text), Mapping) else None

    session_start_commands = _hook_commands(config, "SessionStart")
    user_prompt_commands = _hook_commands(config, "UserPromptSubmit")
    session_start_project_init = [cmd for cmd in session_start_commands if "codex_project_init_hook.py" in cmd]
    user_prompt_project_init = [cmd for cmd in user_prompt_commands if "codex_project_init_hook.py" in cmd]
    state = _hook_state(config)
    legacy_hook_state = {key: value for key, value in state.items() if legacy_text in str(key)}
    target_hook_state = {key: value for key, value in state.items() if target_text in str(key)}

    entries = [
        EntryPlan(
            "global_mcp_contextforge_helper",
            "replace_with_clean_root",
            "Replace the user-global contextforge-helper command and args with the clean ContextForge worktree path.",
            "medium",
            "codex mcp list --json shows contextforge-helper command and args under the clean root.",
            {"command": helper_command, "args": helper_args},
            {
                "command": _legacy_replaced(helper_command, legacy_root=legacy, target_root=target),
                "args": [_legacy_replaced(arg, legacy_root=legacy, target_root=target) for arg in helper_args],
            },
            _toml_table_lines(text, "[mcp_servers.contextforge-helper]"),
        ),
        EntryPlan(
            "legacy_project_trust",
            "replace_with_clean_root",
            "Replace legacy project trust with the clean project root only after explicit user-global trust approval.",
            "medium",
            "Global config readback shows the legacy project stanza absent and the clean project stanza trusted.",
            {"project": legacy_text, "trust": legacy_project},
            {"project": target_text, "trust": {"trust_level": "trusted"}},
            _toml_table_lines(text, f'[projects."{legacy_text}"]'),
        ),
        EntryPlan(
            "global_session_start_project_init_hook",
            "replace_with_clean_root",
            "Replace the global SessionStart project-init hook command with the clean root script path.",
            "medium_high",
            "Global config readback shows SessionStart project-init hook command under the clean root and no legacy path.",
            session_start_project_init,
            [_legacy_replaced(cmd, legacy_root=legacy, target_root=target) for cmd in session_start_project_init],
            _hook_event_command_lines(text, "SessionStart", "codex_project_init_hook.py"),
        ),
        EntryPlan(
            "global_user_prompt_project_init_hook",
            "replace_with_clean_root",
            "Replace the global UserPromptSubmit project-init hook command with the clean root script path.",
            "medium",
            "Global config readback shows UserPromptSubmit project-init hook command under the clean root and no legacy path.",
            user_prompt_project_init,
            [_legacy_replaced(cmd, legacy_root=legacy, target_root=target) for cmd in user_prompt_project_init],
            _hook_event_command_lines(text, "UserPromptSubmit", "codex_project_init_hook.py"),
        ),
        EntryPlan(
            "legacy_project_local_hook_state",
            "preserve_or_prune_decision_required",
            "Treat legacy project-local hook state as provenance by default; prune it only with explicit cleanup approval.",
            "low_medium",
            "Global config readback either preserves legacy hook-state entries as explicit provenance or removes them by approved cleanup.",
            legacy_hook_state,
            {
                "default": "preserve_as_legacy_trust_evidence",
                "optional_approved_cleanup": "remove legacy hook-state entries after clean-root hook trust is established",
            },
            _line_numbers(text, *legacy_hook_state.keys()),
        ),
    ]

    active_legacy_entries = [entry.entry_id for entry in entries if legacy_text in json.dumps(entry.current_value, sort_keys=True)]
    blockers = [] if approval_acknowledged else ["approval_required_before_user_global_codex_config_or_trust_mutation"]
    warnings: list[str] = []
    if target_project is None:
        warnings.append("clean_root_project_trust_missing")
    if not target_hook_state:
        warnings.append("clean_root_project_local_hook_state_missing")
    if not active_legacy_entries:
        warnings.append("no_legacy_entries_found")

    return {
        "schema_uri": REPORT_SCHEMA_URI,
        "project_name": "ContextForge",
        "config_path": str(config_file),
        "target_root": target_text,
        "legacy_root": legacy_text,
        "status": "blocked" if blockers else "ready",
        "approval_required": bool(blockers),
        "approval": {
            "acknowledged": approval_acknowledged,
            "ref": approval_ref,
            "required_before_mutation": bool(blockers),
        },
        "blockers": blockers,
        "warnings": warnings,
        "active_legacy_entries": active_legacy_entries,
        "clean_root_presence": {
            "project_trust_present": target_project is not None,
            "project_trust": target_project,
            "project_local_hook_state_count": len(target_hook_state),
            "global_helper_already_targets_clean_root": target_text in json.dumps(helper, sort_keys=True),
        },
        "entries": [_entry_dict(entry) for entry in entries],
        "next_actions": [
            "Ask for explicit approval before editing user-global Codex config or trust.",
            "If approved, replace active global helper and project-init hook paths with the clean root and migrate project trust deliberately.",
            "Do not prune legacy hook-state provenance unless that cleanup is explicitly approved.",
            "After any approved change, restart/reload the affected Codex surface only with explicit user action and verify readback.",
        ],
        "non_actions": [
            "read-only plan; no user-global config or trust file is written",
            "no hook trust is granted or revoked",
            "no Codex client reload or restart is performed",
            "no service, process, registry, catalog, Pi, or legacy checkout mutation is performed",
        ],
        "readback_commands": [
            "rg -n \"context-portal|contextforge-slices\" ~/.codex/config.toml",
            "codex -C /home/dgk/workspace/contextforge-slices/repo-local-skills-and-governance mcp list --json",
        ],
    }


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-path", default=str(DEFAULT_CONFIG_PATH), help="User-global Codex config to inspect.")
    parser.add_argument("--target-root", default=str(Path.cwd()), help="Clean ContextForge root that would own active global references.")
    parser.add_argument("--legacy-root", default=str(DEFAULT_LEGACY_ROOT), help="Legacy checkout root to classify.")
    parser.add_argument("--approval-acknowledged", action="store_true", help="Report using an explicit approval already recorded for this pass.")
    parser.add_argument("--approval-ref", help="Human-readable approval reference.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_report(
        config_path=args.config_path,
        target_root=args.target_root,
        legacy_root=args.legacy_root,
        approval_acknowledged=args.approval_acknowledged,
        approval_ref=args.approval_ref,
    )
    print(json.dumps(report, indent=2 if args.pretty else None, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
