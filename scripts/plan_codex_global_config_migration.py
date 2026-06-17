#!/usr/bin/env python3
"""Plan and safely apply ContextForge user-global Codex config migration.

By default this report is non-mutating. It classifies stale
``/home/dgk/workspace/legacy-controlplane-archive`` entries in ``~/.codex/config.toml`` and
builds an approval-ready plan for moving active global Codex surfaces to the
clean ContextForge worktree.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


REPORT_SCHEMA_URI = "contextforge://control-plane/codex-global-config-migration-plan/v1"
DEFAULT_LEGACY_ROOT = Path("/home/dgk/workspace/legacy-controlplane-archive")
DEFAULT_CONFIG_PATH = Path("~/.codex/config.toml")
BACKUP_SUFFIX = ".contextforge-backup"


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


def _timestamp() -> str:
    return dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ")


def _default_backup_path(config_file: Path) -> Path:
    candidate = config_file.with_name(f"{config_file.name}{BACKUP_SUFFIX}-{_timestamp()}")
    if not candidate.exists():
        return candidate
    for counter in range(1, 1000):
        numbered = candidate.with_name(f"{candidate.name}-{counter}")
        if not numbered.exists():
            return numbered
    raise FileExistsError(f"could not allocate unique backup path near {candidate}")


def _validated_backup_path(path: str | Path) -> Path:
    backup = _canonical(path)
    if backup.exists():
        raise FileExistsError(f"backup path already exists: {backup}")
    return backup


def _replace_line_value(lines: list[str], *, key: str, old_value: str, new_value: str) -> bool:
    old_line = f'{key} = "{old_value}"'
    new_line = f'{key} = "{new_value}"'
    changed = False
    for index, line in enumerate(lines):
        if line.strip() == new_line:
            continue
        if line.strip() == old_line:
            prefix = line[: len(line) - len(line.lstrip())]
            lines[index] = f"{prefix}{new_line}"
            changed = True
    return changed


def _toml_section_bounds(lines: Sequence[str], header: str) -> tuple[int, int] | None:
    for index, line in enumerate(lines):
        if line.strip() != header:
            continue
        section_end = len(lines)
        for probe in range(index + 1, len(lines)):
            stripped = lines[probe].strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                section_end = probe
                break
        return index, section_end
    return None


def _replace_section_line_value(
    lines: list[str],
    *,
    header: str,
    key: str,
    old_value: str,
    new_value: str,
) -> bool:
    bounds = _toml_section_bounds(lines, header)
    if bounds is None:
        return False
    start, end = bounds
    section = lines[start:end]
    changed = _replace_line_value(section, key=key, old_value=old_value, new_value=new_value)
    if changed:
        lines[start:end] = section
    return changed


def _replace_args_line(lines: list[str], *, old_args: Sequence[str], new_args: Sequence[str]) -> bool:
    old_line = f"args = {json.dumps(list(old_args))}"
    new_line = f"args = {json.dumps(list(new_args))}"
    changed = False
    for index, line in enumerate(lines):
        if line.strip() == new_line:
            continue
        if line.strip() == old_line:
            prefix = line[: len(line) - len(line.lstrip())]
            lines[index] = f"{prefix}{new_line}"
            changed = True
    return changed


def _replace_section_args_line(
    lines: list[str],
    *,
    header: str,
    old_args: Sequence[str],
    new_args: Sequence[str],
) -> bool:
    bounds = _toml_section_bounds(lines, header)
    if bounds is None:
        return False
    start, end = bounds
    section = lines[start:end]
    changed = _replace_args_line(section, old_args=old_args, new_args=new_args)
    if changed:
        lines[start:end] = section
    return changed


def _ensure_project_trust(lines: list[str], *, project_root: Path) -> bool:
    header = f'[projects."{project_root}"]'
    for index, line in enumerate(lines):
        if line.strip() != header:
            continue
        section_end = len(lines)
        for probe in range(index + 1, len(lines)):
            stripped = lines[probe].strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                section_end = probe
                break
        for probe in range(index + 1, section_end):
            if lines[probe].strip() == 'trust_level = "trusted"':
                return False
            if lines[probe].strip().startswith("trust_level ="):
                lines[probe] = 'trust_level = "trusted"'
                return True
        lines.insert(section_end, 'trust_level = "trusted"')
        return True

    insert_at = len(lines)
    while insert_at > 0 and lines[insert_at - 1].strip() == "":
        insert_at -= 1
    block = ["", header, 'trust_level = "trusted"']
    lines[insert_at:insert_at] = block
    return True


def _remove_project_trust(lines: list[str], *, project_root: Path) -> bool:
    header = f'[projects."{project_root}"]'
    for index, line in enumerate(lines):
        if line.strip() != header:
            continue
        section_end = len(lines)
        for probe in range(index + 1, len(lines)):
            stripped = lines[probe].strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                section_end = probe
                break
        del lines[index:section_end]
        while index < len(lines) and lines[index].strip() == "":
            del lines[index]
        return True
    return False


def _hook_command_from_block(block: Sequence[str]) -> str | None:
    for line in block:
        stripped = line.strip()
        if stripped.startswith("command = "):
            try:
                value = tomllib.loads(f"command = {stripped.removeprefix('command = ')}\n")
            except tomllib.TOMLDecodeError:
                return None
            command = value.get("command")
            return command if isinstance(command, str) else None
    return None


def _replace_hook_commands(
    lines: list[str],
    *,
    event_name: str,
    old_command: str,
    new_command: str,
) -> bool:
    changed = False
    event_header = f"[[hooks.{event_name}]]"
    hook_header = f"[[hooks.{event_name}.hooks]]"

    new_present = False
    index = 0
    while index < len(lines):
        if lines[index].strip() != hook_header:
            index += 1
            continue
        block_end = len(lines)
        for probe in range(index + 1, len(lines)):
            stripped = lines[probe].strip()
            if stripped == hook_header or stripped == event_header:
                block_end = probe
                break
            if stripped.startswith("[[hooks.") and stripped.endswith("]]"):
                block_end = probe
                break
        if _hook_command_from_block(lines[index:block_end]) == new_command:
            new_present = True
            break
        index = block_end

    index = 0
    while index < len(lines):
        if lines[index].strip() != hook_header:
            index += 1
            continue
        block_end = len(lines)
        for probe in range(index + 1, len(lines)):
            stripped = lines[probe].strip()
            if stripped == hook_header or stripped == event_header:
                block_end = probe
                break
            if stripped.startswith("[[hooks.") and stripped.endswith("]]"):
                block_end = probe
                break
        block = lines[index:block_end]
        command = _hook_command_from_block(block)
        if command == new_command:
            index = block_end
            continue
        if command == old_command:
            if new_present:
                del lines[index:block_end]
                while index < len(lines) and lines[index].strip() == "":
                    del lines[index]
                changed = True
                continue
            for block_index in range(index, block_end):
                stripped = lines[block_index].strip()
                if stripped.startswith("command = "):
                    prefix = lines[block_index][: len(lines[block_index]) - len(lines[block_index].lstrip())]
                    lines[block_index] = f'{prefix}command = "{new_command}"'
                    changed = True
                    new_present = True
                    break
        index = block_end
    return changed


def _remove_hook_state(lines: list[str], *, root: Path) -> bool:
    changed = False
    root_text = str(root)
    index = 0
    while index < len(lines):
        stripped = lines[index].strip()
        if not (stripped.startswith('[hooks.state."') and root_text in stripped):
            index += 1
            continue
        section_end = len(lines)
        for probe in range(index + 1, len(lines)):
            next_stripped = lines[probe].strip()
            if next_stripped.startswith("[") and next_stripped.endswith("]"):
                section_end = probe
                break
        del lines[index:section_end]
        while index < len(lines) and lines[index].strip() == "":
            del lines[index]
        changed = True
    return changed


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


def _record_tags(record: Mapping[str, Any] | None) -> set[str]:
    if not record:
        return set()
    tags = record.get("tags")
    if isinstance(tags, list):
        collected: set[str] = set()
        for tag in tags:
            if isinstance(tag, str):
                collected.add(tag)
            elif isinstance(tag, Mapping):
                name = tag.get("name") or tag.get("label")
                if name:
                    collected.add(str(name))
        return collected
    return set()


def classify_prompt_resource_side_effect(
    *,
    prompt_record: Mapping[str, Any] | None,
    resource_record: Mapping[str, Any] | None,
    prompt_version: str,
    resource_uri: str,
) -> dict[str, Any]:
    reasons: list[str] = []
    if not prompt_record:
        reasons.append("project_init_prompt_missing")
    elif not prompt_record.get("id"):
        reasons.append("project_init_prompt_missing_id")
    elif prompt_version not in _record_tags(prompt_record):
        reasons.append("project_init_prompt_stale")

    if not resource_record:
        reasons.append("project_init_resource_missing")
    elif not resource_record.get("id"):
        reasons.append("project_init_resource_missing_id")
    elif resource_record.get("uri") != resource_uri or prompt_version not in _record_tags(resource_record):
        reasons.append("project_init_resource_stale")

    would_upsert = bool(reasons)
    return {
        "status": "would_upsert_prompt_resource" if would_upsert else "read_only_render_path",
        "would_call_upgrade_project_init_prompt": would_upsert,
        "reasons": reasons,
        "approval_required_before_hook_execution": would_upsert,
        "non_actions": ["classification only; no prompt/resource upsert performed"],
    }


def _not_inspected_prompt_resource_side_effect() -> dict[str, Any]:
    return {
        "status": "unknown_prompt_resource_readback_required",
        "would_call_upgrade_project_init_prompt": "unknown",
        "reasons": ["contextforge_prompt_resource_records_not_inspected"],
        "approval_required_before_hook_execution": True,
        "non_actions": ["classification only; no ContextForge API read or upsert performed"],
    }


def _read_contextforge_prompt_resource_side_effect() -> dict[str, Any]:
    import codex_project_init_hook as hook
    import contextforge_mcp_wrapper as gateway
    from project_init_common import PROMPT_VERSION, PROJECT_INIT_RESOURCE_URI

    env_token = os.environ.get("CONTEXTFORGE_BEARER_TOKEN")
    token = env_token.removeprefix("Bearer ").strip() if env_token else gateway._cached_token()
    if not token:
        raise RuntimeError("no existing bearer or cached token; refusing login/token-cache write during preflight")
    prompt = hook.get_prompt_record(token)
    resource = hook.get_project_init_resource_record(token)
    classified = classify_prompt_resource_side_effect(
        prompt_record=prompt,
        resource_record=resource,
        prompt_version=PROMPT_VERSION,
        resource_uri=PROJECT_INIT_RESOURCE_URI,
    )
    classified["prompt_record_present"] = bool(prompt)
    classified["resource_record_present"] = bool(resource)
    classified["non_actions"] = [
        "read-only ContextForge prompt/resource metadata inspection using existing token material only",
        "no prompt/resource upsert performed",
        "no login or token-cache write performed",
    ]
    return classified


def _hook_retarget_preflight(
    *,
    entries: Sequence[EntryPlan],
    legacy_hook_state: Mapping[str, Any],
    target_hook_state: Mapping[str, Any],
    inspect_contextforge_prompt_state: bool,
) -> dict[str, Any]:
    entry_map = {entry.entry_id: entry for entry in entries}
    affected = [
        {
            "event": "SessionStart",
            "entry_id": "global_session_start_project_init_hook",
            "current_commands": entry_map["global_session_start_project_init_hook"].current_value,
            "target_commands": entry_map["global_session_start_project_init_hook"].target_value,
            "lines": list(entry_map["global_session_start_project_init_hook"].lines),
        },
        {
            "event": "UserPromptSubmit",
            "entry_id": "global_user_prompt_project_init_hook",
            "current_commands": entry_map["global_user_prompt_project_init_hook"].current_value,
            "target_commands": entry_map["global_user_prompt_project_init_hook"].target_value,
            "lines": list(entry_map["global_user_prompt_project_init_hook"].lines),
        },
    ]
    if inspect_contextforge_prompt_state:
        try:
            prompt_resource = _read_contextforge_prompt_resource_side_effect()
        except Exception as exc:
            prompt_resource = {
                "status": "contextforge_prompt_resource_readback_failed",
                "would_call_upgrade_project_init_prompt": "unknown",
                "reasons": [f"{type(exc).__name__}: {exc}"],
                "approval_required_before_hook_execution": True,
                "non_actions": [
                    "attempted read-only ContextForge prompt/resource metadata inspection",
                    "no prompt/resource upsert performed",
                ],
            }
    else:
        prompt_resource = _not_inspected_prompt_resource_side_effect()
    return {
        "affected_hook_commands": affected,
        "legacy_hook_state_records": sorted(str(key) for key in legacy_hook_state),
        "clean_root_hook_state_records": sorted(str(key) for key in target_hook_state),
        "trust_state_effect": {
            "changed_global_hook_commands_may_require_new_hook_trust_or_operator_approval": True,
            "hook_trust_is_not_granted_or_revoked_by_this_tool": True,
            "legacy_hook_state_policy": "preserve_by_default",
        },
        "first_run_side_effect_model": {
            "hook_code_path": "codex_project_init_hook.main_for_events -> prompt/resource freshness check -> optional upgrade_project_init_prompt",
            "prompt_resource_readback": prompt_resource,
            "approval_boundary": "Hook execution and any prompt/resource upsert side effect require separate operator approval from global config file editing.",
        },
        "post_restart_readback": [
            "Inspect Codex hook trust/approval UI or hook-state readback after the retargeted command is observed.",
            "If prompt/resource metadata was missing or stale, record explicit approval before allowing first hook execution to upsert.",
            "Preserve legacy project-local hook-state provenance unless separate pruning approval is provided.",
        ],
        "non_actions": [
            "no hook trust is granted or revoked",
            "no hook is executed",
            "no prompt/resource upsert is performed",
        ],
    }


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
    inspect_contextforge_prompt_state: bool = False,
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
            "Add clean project trust first; retain legacy trust for rollback unless separate removal is explicitly approved.",
            "medium",
            "Global config readback shows the clean project stanza trusted; legacy project trust remains unless separately removed.",
            {"project": legacy_text, "trust": legacy_project},
            {
                "project": target_text,
                "trust": {"trust_level": "trusted"},
                "legacy_trust_policy": "retain_by_default",
            },
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
        "hook_retarget_preflight": _hook_retarget_preflight(
            entries=entries,
            legacy_hook_state=legacy_hook_state,
            target_hook_state=target_hook_state,
            inspect_contextforge_prompt_state=inspect_contextforge_prompt_state,
        ),
        "next_actions": [
            "Ask for explicit approval before editing user-global Codex config or trust.",
            "If approved, replace active global helper and project-init hook paths with the clean root and add clean project trust while retaining legacy trust unless separate removal is approved.",
            "Before executing retargeted hooks, review hook_retarget_preflight and require separate approval for hook trust/execution and any prompt/resource upsert side effect.",
            "Do not prune legacy hook-state provenance unless that cleanup is explicitly approved.",
            "After any approved file change, treat the result as pending_restart until the affected Codex surface is restarted by explicit user action and verified by readback.",
        ],
        "non_actions": [
            "read-only plan; no user-global config or trust file is written",
            "no hook trust is granted or revoked",
            "no Codex client reload or restart is performed",
            "no service, process, registry, catalog, Pi, or legacy checkout mutation is performed",
        ],
        "readback_commands": [
            "rg -n \"cf-controlplane|legacy-controlplane-slices|contextforge-helper|codex_project_init_hook\" ~/.codex/config.toml",
            "cd /home/dgk && codex mcp list --json",
            f"codex -C {target_text} mcp list --json",
        ],
    }


def apply_migration(
    *,
    config_path: str | Path = DEFAULT_CONFIG_PATH,
    target_root: str | Path,
    legacy_root: str | Path = DEFAULT_LEGACY_ROOT,
    approval_acknowledged: bool,
    approval_ref: str | None = None,
    backup_path: str | Path | None = None,
    remove_legacy_trust: bool = False,
    remove_legacy_trust_approved: bool = False,
    prune_legacy_hook_state: bool = False,
    prune_legacy_hook_state_approved: bool = False,
) -> dict[str, Any]:
    if not approval_acknowledged:
        raise PermissionError("explicit approval is required before writing user-global Codex config")
    if remove_legacy_trust and not remove_legacy_trust_approved:
        raise PermissionError("separate approval is required before removing legacy project trust")
    if prune_legacy_hook_state and not prune_legacy_hook_state_approved:
        raise PermissionError("separate approval is required before pruning legacy hook-state provenance")

    config_file = _canonical(config_path)
    target = _canonical(target_root)
    legacy = _canonical(legacy_root)
    before_text = config_file.read_text(encoding="utf-8")
    before_report = build_report(
        config_path=config_file,
        target_root=target,
        legacy_root=legacy,
        approval_acknowledged=approval_acknowledged,
        approval_ref=approval_ref,
    )
    lines = before_text.splitlines()
    actions: list[dict[str, Any]] = []

    helper_entries = {entry["entry_id"]: entry for entry in before_report["entries"]}
    helper = helper_entries["global_mcp_contextforge_helper"]
    helper_current = helper["current_value"]
    helper_target = helper["target_value"]
    if _replace_section_line_value(
        lines,
        header="[mcp_servers.contextforge-helper]",
        key="command",
        old_value=helper_current["command"],
        new_value=helper_target["command"],
    ):
        actions.append({"action": "replace_global_helper_command", "result": "changed"})
    if _replace_section_args_line(
        lines,
        header="[mcp_servers.contextforge-helper]",
        old_args=helper_current["args"],
        new_args=helper_target["args"],
    ):
        actions.append({"action": "replace_global_helper_args", "result": "changed"})

    if _ensure_project_trust(lines, project_root=target):
        actions.append({"action": "ensure_clean_project_trust", "result": "changed"})
    if remove_legacy_trust and _remove_project_trust(lines, project_root=legacy):
        actions.append({"action": "remove_legacy_project_trust", "result": "changed"})

    for event_name, entry_id in (
        ("SessionStart", "global_session_start_project_init_hook"),
        ("UserPromptSubmit", "global_user_prompt_project_init_hook"),
    ):
        entry = helper_entries[entry_id]
        for old_command, new_command in zip(entry["current_value"], entry["target_value"], strict=False):
            if _replace_hook_commands(
                lines,
                event_name=event_name,
                old_command=old_command,
                new_command=new_command,
            ):
                actions.append({"action": f"replace_{event_name}_project_init_hook", "result": "changed"})

    if prune_legacy_hook_state and _remove_hook_state(lines, root=legacy):
        actions.append({"action": "prune_legacy_hook_state", "result": "changed"})

    after_text = "\n".join(lines) + ("\n" if before_text.endswith("\n") else "")
    changed = after_text != before_text
    if backup_path:
        backup_candidate = _canonical(backup_path)
        if backup_candidate == config_file:
            raise ValueError("backup path must be different from config path")
        backup = _validated_backup_path(backup_candidate)
    else:
        backup = _default_backup_path(config_file)
    if backup == config_file:
        raise ValueError("backup path must be different from config path")
    if changed:
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_text(before_text, encoding="utf-8")
        config_file.write_text(after_text, encoding="utf-8")

    after_report = build_report(
        config_path=config_file,
        target_root=target,
        legacy_root=legacy,
        approval_acknowledged=approval_acknowledged,
        approval_ref=approval_ref,
    )
    return {
        "schema_uri": "contextforge://control-plane/codex-global-config-migration-apply/v1",
        "project_name": "ContextForge",
        "config_path": str(config_file),
        "status": "pending_restart" if changed else "already_converged",
        "changed": changed,
        "backup_path": str(backup) if changed else None,
        "approval": {"acknowledged": approval_acknowledged, "ref": approval_ref},
        "policies": {
            "legacy_project_trust": (
                "removed_by_separate_approval" if remove_legacy_trust else "retained_for_rollback"
            ),
            "legacy_hook_state": (
                "pruned_by_separate_approval" if prune_legacy_hook_state else "preserved_as_provenance"
            ),
        },
        "actions": actions,
        "post_apply_report": after_report,
        "non_actions": [
            "no hook trust is granted or revoked",
            "no Codex client reload or restart is performed",
            "no service, process, registry, catalog, Pi, or legacy checkout mutation is performed",
        ],
    }


def rollback_from_backup(
    *,
    config_path: str | Path = DEFAULT_CONFIG_PATH,
    backup_path: str | Path,
    approval_acknowledged: bool,
    approval_ref: str | None = None,
) -> dict[str, Any]:
    if not approval_acknowledged:
        raise PermissionError("explicit approval is required before restoring user-global Codex config")

    config_file = _canonical(config_path)
    backup = _canonical(backup_path)
    if backup == config_file:
        raise ValueError("rollback backup path must be different from config path")
    if not backup.exists():
        raise FileNotFoundError(f"backup does not exist: {backup}")
    before_text = config_file.read_text(encoding="utf-8") if config_file.exists() else ""
    restore_backup = _default_backup_path(config_file)
    restore_backup.write_text(before_text, encoding="utf-8")
    shutil.copyfile(backup, config_file)
    return {
        "schema_uri": "contextforge://control-plane/codex-global-config-migration-rollback/v1",
        "project_name": "ContextForge",
        "config_path": str(config_file),
        "status": "rolled_back_pending_restart",
        "restored_from": str(backup),
        "pre_rollback_backup_path": str(restore_backup),
        "approval": {"acknowledged": approval_acknowledged, "ref": approval_ref},
        "non_actions": [
            "no hook trust is granted or revoked",
            "no Codex client reload or restart is performed",
            "no service, process, registry, catalog, Pi, or legacy checkout mutation is performed",
        ],
    }


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-path", default=str(DEFAULT_CONFIG_PATH), help="User-global Codex config to inspect.")
    parser.add_argument("--target-root", default=str(Path.cwd()), help="Clean ContextForge root that would own active global references.")
    parser.add_argument("--legacy-root", default=str(DEFAULT_LEGACY_ROOT), help="Legacy checkout root to classify.")
    parser.add_argument("--approval-acknowledged", action="store_true", help="Report using an explicit approval already recorded for this pass.")
    parser.add_argument("--approval-ref", help="Human-readable approval reference.")
    parser.add_argument("--apply", action="store_true", help="Apply the approved staged migration to the selected config.")
    parser.add_argument("--backup-path", help="Backup path to create before --apply, or explicit destination for tests.")
    parser.add_argument("--remove-legacy-trust", action="store_true", help="With --apply, remove legacy project trust instead of retaining it for rollback.")
    parser.add_argument("--remove-legacy-trust-approved", action="store_true", help="Separate approval for --remove-legacy-trust.")
    parser.add_argument("--prune-legacy-hook-state", action="store_true", help="With --apply, prune legacy hook-state provenance.")
    parser.add_argument("--prune-legacy-hook-state-approved", action="store_true", help="Separate approval for --prune-legacy-hook-state.")
    parser.add_argument("--rollback-from", help="Restore the selected config from a prior backup path.")
    parser.add_argument(
        "--inspect-contextforge-prompt-state",
        action="store_true",
        help="Perform read-only ContextForge prompt/resource metadata inspection for hook side-effect preflight.",
    )
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.apply and args.rollback_from:
        print("--apply and --rollback-from are mutually exclusive", file=sys.stderr)
        return 2
    try:
        if args.rollback_from:
            report = rollback_from_backup(
                config_path=args.config_path,
                backup_path=args.rollback_from,
                approval_acknowledged=args.approval_acknowledged,
                approval_ref=args.approval_ref,
            )
        elif args.apply:
            report = apply_migration(
                config_path=args.config_path,
                target_root=args.target_root,
                legacy_root=args.legacy_root,
                approval_acknowledged=args.approval_acknowledged,
                approval_ref=args.approval_ref,
                backup_path=args.backup_path,
                remove_legacy_trust=args.remove_legacy_trust,
                remove_legacy_trust_approved=args.remove_legacy_trust_approved,
                prune_legacy_hook_state=args.prune_legacy_hook_state,
                prune_legacy_hook_state_approved=args.prune_legacy_hook_state_approved,
            )
        else:
            report = build_report(
                config_path=args.config_path,
                target_root=args.target_root,
                legacy_root=args.legacy_root,
                approval_acknowledged=args.approval_acknowledged,
                approval_ref=args.approval_ref,
                inspect_contextforge_prompt_state=args.inspect_contextforge_prompt_state,
            )
    except (FileExistsError, FileNotFoundError, PermissionError, tomllib.TOMLDecodeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2 if args.pretty else None, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
