#!/usr/bin/env python3
"""Read-only Codex runtime/project-context readback inspection for issue #31."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any, Mapping, Sequence


REPORT_SCHEMA_URI = "contextforge://control-plane/codex-runtime-readback-report/v1"
DEFAULT_PROJECT_ROOT = Path("/home/dgk/workspace/cf-controlplane")
DEFAULT_CONFIG_PATH = Path("~/.codex/config.toml")
DEFAULT_LEGACY_ROOTS = (
    Path("/home/dgk/workspace/context-portal"),
    Path("/home/dgk/workspace/contextforge-slices/repo-local-skills-and-governance"),
)
CODEX_RUNTIME_SCRIPT_NAMES = (
    "contextforge_helper_mcp.py",
    "contextforge_mcp_wrapper.py",
    "codex_project_init_hook.py",
)


def _canonical(path: str | Path) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _root_counts(text: str, roots: Sequence[Path]) -> dict[str, int]:
    return {str(root): text.count(str(root)) for root in roots}


def _first_matching_root(text: str, roots: Sequence[Path]) -> str | None:
    for root in roots:
        if str(root) in text:
            return str(root)
    return None


def _read_text(path: Path) -> tuple[str, str | None]:
    try:
        return path.read_text(encoding="utf-8"), None
    except (OSError, UnicodeDecodeError) as exc:
        return "", f"{type(exc).__name__}: {exc}"


def _load_toml(path: Path) -> tuple[dict[str, Any], str | None]:
    text, error = _read_text(path)
    if error:
        return {}, error
    try:
        parsed = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        return {}, f"{type(exc).__name__}: {exc}"
    return parsed, None


def _transport_text(transport: Mapping[str, Any], *, default_cwd: Path | None) -> str:
    command = str(transport.get("command") or "")
    args = transport.get("args") if isinstance(transport.get("args"), list) else []
    cwd = str(transport.get("cwd") or "")
    parts = [command, " ".join(str(arg) for arg in args), cwd]
    if default_cwd:
        for value in (command, *(str(arg) for arg in args)):
            candidate = Path(value).expanduser()
            if value and not candidate.is_absolute():
                parts.append(str((default_cwd / candidate).resolve(strict=False)))
    return " ".join(parts)


def summarize_mcp_payload(
    payload: Any,
    *,
    default_cwd: Path | None,
    target_root: Path,
    legacy_roots: Sequence[Path],
) -> dict[str, Any]:
    servers = payload if isinstance(payload, list) else []
    roots = (target_root, *legacy_roots)
    server_summaries: list[dict[str, Any]] = []
    for item in servers:
        if not isinstance(item, Mapping):
            continue
        transport = item.get("transport") if isinstance(item.get("transport"), Mapping) else {}
        text = _transport_text(transport, default_cwd=default_cwd)
        target_refs = text.count(str(target_root))
        legacy_counts = _root_counts(text, legacy_roots)
        matched_legacy = _first_matching_root(text, legacy_roots)
        if target_refs:
            root_class = "target"
        elif matched_legacy:
            root_class = "legacy"
        elif any(str(value or "").startswith(".") for value in (transport.get("command"), *(transport.get("args") or []))):
            root_class = "relative"
        else:
            root_class = "external_or_unknown"
        server_summaries.append(
            {
                "name": item.get("name"),
                "enabled": item.get("enabled"),
                "transport_type": transport.get("type"),
                "command": transport.get("command"),
                "args": transport.get("args") if isinstance(transport.get("args"), list) else [],
                "cwd": transport.get("cwd"),
                "root_class": root_class,
                "target_root_reference_count": target_refs,
                "legacy_root_reference_counts": legacy_counts,
                "matched_legacy_root": matched_legacy,
            }
        )
    raw_text = json.dumps(payload, sort_keys=True, default=str)
    if default_cwd:
        raw_text = raw_text + " " + " ".join(
            str((default_cwd / Path(value)).resolve(strict=False))
            for server in server_summaries
            for value in [str(server.get("command") or ""), *(str(arg) for arg in server.get("args") or [])]
            if value and not Path(value).expanduser().is_absolute()
        )
    return {
        "payload_type": type(payload).__name__,
        "server_count": len(server_summaries),
        "servers": server_summaries,
        "target_root_reference_count": raw_text.count(str(target_root)),
        "legacy_root_reference_counts": _root_counts(raw_text, legacy_roots),
        "non_target_servers": [
            server.get("name")
            for server in server_summaries
            if server.get("root_class") in {"legacy", "relative", "external_or_unknown"}
            and server.get("name") not in {"node_repl"}
        ],
    }


def _run_json_command(command: Sequence[str], *, cwd: Path, timeout: float) -> dict[str, Any]:
    try:
        result = subprocess.run(
            list(command),
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {
            "command": list(command),
            "cwd": str(cwd),
            "exit_code": None,
            "status": "command_failed",
            "error": f"{type(exc).__name__}: {exc}",
            "stdout": "",
            "stderr": "",
            "parsed": None,
        }
    parsed: Any = None
    parse_error = None
    if result.stdout.strip():
        try:
            parsed = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            parse_error = f"{type(exc).__name__}: {exc}"
    status = "ok" if result.returncode == 0 and parse_error is None else "failed"
    return {
        "command": list(command),
        "cwd": str(cwd),
        "exit_code": result.returncode,
        "status": status,
        "error": parse_error,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "parsed": parsed,
    }


def run_codex_mcp_readbacks(
    *,
    project_root: Path,
    legacy_roots: Sequence[Path],
    timeout: float,
) -> dict[str, Any]:
    readbacks: dict[str, Any] = {}
    commands = {
        "global_from_project_cwd": ["codex", "mcp", "list", "--json"],
        "project_explicit_root": ["codex", "-C", str(project_root), "mcp", "list", "--json"],
    }
    for key, command in commands.items():
        result = _run_json_command(command, cwd=project_root, timeout=timeout)
        summary = summarize_mcp_payload(
            result.get("parsed"),
            default_cwd=project_root,
            target_root=project_root,
            legacy_roots=legacy_roots,
        )
        result["summary"] = summary
        result["stdout"] = "<omitted; parsed summary retained>" if result.get("stdout") else ""
        result["parsed"] = "<omitted; parsed summary retained>" if result.get("parsed") is not None else None
        readbacks[key] = result
    return readbacks


def _hook_commands(config: Mapping[str, Any], event_name: str) -> list[str]:
    hooks = ((config.get("hooks") or {}).get(event_name) or [])
    if not isinstance(hooks, list):
        return []
    commands: list[str] = []
    for event in hooks:
        if not isinstance(event, Mapping):
            continue
        for hook in event.get("hooks") or []:
            if isinstance(hook, Mapping) and isinstance(hook.get("command"), str):
                commands.append(hook["command"])
    return commands


def summarize_global_config(
    *,
    config_path: Path,
    target_root: Path,
    legacy_roots: Sequence[Path],
) -> dict[str, Any]:
    parsed, error = _load_toml(config_path)
    text, read_error = _read_text(config_path)
    if error:
        return {
            "path": str(config_path),
            "exists": config_path.exists(),
            "status": "unreadable_or_unparseable",
            "error": error,
            "non_actions": ["read-only parse only; no config write"],
        }
    mcp_servers = parsed.get("mcp_servers") if isinstance(parsed.get("mcp_servers"), Mapping) else {}
    helper = mcp_servers.get("contextforge-helper") if isinstance(mcp_servers.get("contextforge-helper"), Mapping) else {}
    projects = parsed.get("projects") if isinstance(parsed.get("projects"), Mapping) else {}
    hooks_state = ((parsed.get("hooks") or {}).get("state") or {}) if isinstance(parsed.get("hooks"), Mapping) else {}
    session_start = _hook_commands(parsed, "SessionStart")
    user_prompt = _hook_commands(parsed, "UserPromptSubmit")
    return {
        "path": str(config_path),
        "exists": config_path.exists(),
        "status": "parsed",
        "read_error": read_error,
        "target_root_reference_count": text.count(str(target_root)),
        "legacy_root_reference_counts": _root_counts(text, legacy_roots),
        "contextforge_helper": {
            "command": helper.get("command"),
            "args": helper.get("args") if isinstance(helper.get("args"), list) else [],
            "target_root_reference_count": _transport_text(helper, default_cwd=None).count(str(target_root)),
            "legacy_root_reference_counts": _root_counts(_transport_text(helper, default_cwd=None), legacy_roots),
        },
        "project_trust": {
            "target_present": str(target_root) in projects,
            "target_trust_level": (projects.get(str(target_root)) or {}).get("trust_level")
            if isinstance(projects.get(str(target_root)), Mapping)
            else None,
            "legacy_present": {
                str(root): str(root) in projects
                for root in legacy_roots
            },
        },
        "project_init_hooks": {
            "SessionStart": [command for command in session_start if "codex_project_init_hook.py" in command],
            "UserPromptSubmit": [command for command in user_prompt if "codex_project_init_hook.py" in command],
        },
        "hook_state_counts": {
            "target": sum(1 for key in hooks_state if str(target_root) in str(key)),
            "legacy": {
                str(root): sum(1 for key in hooks_state if str(root) in str(key))
                for root in legacy_roots
            },
        },
        "non_actions": ["read-only parse only; no config write"],
    }


def _process_cwd(pid: str) -> str | None:
    try:
        return str((Path("/proc") / pid / "cwd").resolve(strict=True))
    except OSError:
        return None


def _script_source_root(script_path: str | Path) -> str | None:
    path = Path(script_path).expanduser().resolve(strict=False)
    if path.parent.name != "scripts":
        return None
    return str(path.parent.parent)


def _extract_process_script(command: str, *, cwd: str | None) -> tuple[str | None, str | None]:
    try:
        parts = shlex.split(command)
    except ValueError:
        parts = command.split()
    for part in parts:
        candidate = Path(part)
        if candidate.name not in CODEX_RUNTIME_SCRIPT_NAMES:
            continue
        script_path = candidate if candidate.is_absolute() else (Path(cwd) / candidate if cwd else candidate)
        script = str(script_path.expanduser().resolve(strict=False))
        return script, _script_source_root(script)
    return None, None


def list_codex_runtime_processes() -> list[dict[str, Any]]:
    try:
        result = subprocess.run(
            ["ps", "-eo", "pid=,ppid=,args="],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if result.returncode != 0:
        return []
    processes: list[dict[str, Any]] = []
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if not stripped or not any(name in stripped for name in CODEX_RUNTIME_SCRIPT_NAMES):
            continue
        parts = stripped.split(maxsplit=2)
        if len(parts) < 3:
            continue
        pid_text, ppid_text, command = parts
        cwd = _process_cwd(pid_text)
        script, source_root = _extract_process_script(command, cwd=cwd)
        processes.append(
            {
                "pid": int(pid_text) if pid_text.isdigit() else pid_text,
                "ppid": int(ppid_text) if ppid_text.isdigit() else ppid_text,
                "cwd": cwd,
                "script": script,
                "source_root": source_root,
                "command": command,
            }
        )
    return processes


def summarize_processes(
    processes: Sequence[Mapping[str, Any]],
    *,
    target_root: Path,
    legacy_roots: Sequence[Path],
) -> dict[str, Any]:
    summarized: list[dict[str, Any]] = []
    for process in processes:
        source_root = str(process.get("source_root") or "")
        if source_root == str(target_root):
            root_class = "target"
        elif source_root in {str(root) for root in legacy_roots}:
            root_class = "legacy"
        elif source_root:
            root_class = "foreign"
        else:
            root_class = "unknown"
        summarized.append({**dict(process), "root_class": root_class})
    return {
        "process_count": len(summarized),
        "processes": summarized,
        "target_count": sum(1 for process in summarized if process["root_class"] == "target"),
        "legacy_count": sum(1 for process in summarized if process["root_class"] == "legacy"),
        "foreign_count": sum(1 for process in summarized if process["root_class"] == "foreign"),
        "unknown_count": sum(1 for process in summarized if process["root_class"] == "unknown"),
        "legacy_source_roots": sorted({str(process.get("source_root")) for process in summarized if process["root_class"] == "legacy"}),
        "foreign_source_roots": sorted({str(process.get("source_root")) for process in summarized if process["root_class"] == "foreign"}),
    }


def _runtime_findings(
    *,
    global_config: Mapping[str, Any],
    codex_mcp_readbacks: Mapping[str, Any],
    process_summary: Mapping[str, Any],
) -> tuple[str, list[str], list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    next_actions: list[str] = []

    if global_config.get("status") != "parsed":
        warnings.append("global_codex_config_not_parsed")
    else:
        helper = global_config.get("contextforge_helper") if isinstance(global_config.get("contextforge_helper"), Mapping) else {}
        if any(int(count) for count in (helper.get("legacy_root_reference_counts") or {}).values()):
            warnings.append("global_contextforge_helper_legacy_root_reference")
        trust = global_config.get("project_trust") if isinstance(global_config.get("project_trust"), Mapping) else {}
        if trust.get("target_present") is not True:
            warnings.append("global_target_project_trust_not_present")
        hook_state = global_config.get("hook_state_counts") if isinstance(global_config.get("hook_state_counts"), Mapping) else {}
        if hook_state.get("target", 0) == 0:
            warnings.append("target_project_hook_state_not_seen")

    for name, readback in sorted(codex_mcp_readbacks.items()):
        if readback.get("status") != "ok":
            blockers.append(f"{name}_codex_mcp_readback_failed")
            next_actions.append("Rerun Codex MCP readback from the target project root before closing #31.")
            continue
        summary = readback.get("summary") if isinstance(readback.get("summary"), Mapping) else {}
        legacy_refs = sum(int(count) for count in (summary.get("legacy_root_reference_counts") or {}).values())
        if legacy_refs:
            blockers.append(f"{name}_codex_mcp_readback_legacy_root_reference")
            next_actions.append("Do not claim #31 verified while codex mcp readback still exposes legacy-root transports.")
        non_target = [server for server in summary.get("non_target_servers") or [] if server != "contextforge-helper"]
        if non_target:
            warnings.append(f"{name}_codex_mcp_non_target_servers_present")

    if int(process_summary.get("legacy_count") or 0):
        blockers.append("codex_runtime_legacy_helper_processes_present")
        next_actions.append("Do not kill helper/wrapper processes implicitly; require a Codex Desktop project reload/new-session boundary or explicit cleanup approval.")
    if int(process_summary.get("foreign_count") or 0):
        blockers.append("codex_runtime_foreign_helper_processes_present")
    if int(process_summary.get("unknown_count") or 0):
        warnings.append("codex_runtime_unknown_helper_process_source")
    if int(process_summary.get("target_count") or 0) == 0:
        warnings.append("codex_runtime_target_helper_process_not_seen")

    if blockers:
        status = "blocked"
    elif warnings:
        status = "attention_required"
    else:
        status = "readback_clean"
    return status, sorted(set(blockers)), sorted(set(warnings)), list(dict.fromkeys(next_actions))


def build_report(
    *,
    project_root: str | Path = DEFAULT_PROJECT_ROOT,
    config_path: str | Path = DEFAULT_CONFIG_PATH,
    legacy_roots: Sequence[str | Path] = DEFAULT_LEGACY_ROOTS,
    include_codex_mcp: bool = True,
    include_processes: bool = True,
    codex_mcp_readbacks: Mapping[str, Any] | None = None,
    process_snapshot: Sequence[Mapping[str, Any]] | None = None,
    timeout: float = 20.0,
) -> dict[str, Any]:
    target = _canonical(project_root)
    config = _canonical(config_path)
    legacy = tuple(_canonical(root) for root in legacy_roots)
    global_config = summarize_global_config(config_path=config, target_root=target, legacy_roots=legacy)
    if codex_mcp_readbacks is not None:
        readbacks = dict(codex_mcp_readbacks)
    elif include_codex_mcp:
        readbacks = run_codex_mcp_readbacks(project_root=target, legacy_roots=legacy, timeout=timeout)
    else:
        readbacks = {}
    raw_processes = list(process_snapshot) if process_snapshot is not None else (list_codex_runtime_processes() if include_processes else [])
    process_summary = summarize_processes(raw_processes, target_root=target, legacy_roots=legacy)
    status, blockers, warnings, next_actions = _runtime_findings(
        global_config=global_config,
        codex_mcp_readbacks=readbacks,
        process_summary=process_summary,
    )
    return {
        "schema_uri": REPORT_SCHEMA_URI,
        "issue": "#31",
        "project_root": str(target),
        "status": status,
        "blockers": blockers,
        "warnings": warnings,
        "global_config": global_config,
        "codex_mcp_readbacks": readbacks,
        "process_summary": process_summary,
        "next_actions": next_actions,
        "human_boundaries": [
            "Codex Desktop project open/reload/new-session action if active runtime is legacy-bound",
            "separate hook trust approval if Codex reports hook trust is required",
            "separate approval before any process termination, service restart, registry mutation, Pi global change, or legacy checkout mutation",
        ],
        "non_actions": [
            "read-only inspection; no global Codex config write",
            "no hook trust/state mutation",
            "no hook execution",
            "no process termination or restart",
            "no ContextForge service, registry, systemd, Pi global config, runtime secret, OAuth, or legacy checkout mutation",
        ],
    }


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default=str(Path.cwd()), help="Target Codex project root to inspect.")
    parser.add_argument("--config-path", default=str(DEFAULT_CONFIG_PATH), help="Codex config path to parse read-only.")
    parser.add_argument(
        "--legacy-root",
        action="append",
        default=[],
        help="Legacy root to classify as non-target runtime evidence. Defaults to known migration roots.",
    )
    parser.add_argument("--no-codex-mcp", action="store_true", help="Skip read-only `codex mcp list --json` probes.")
    parser.add_argument("--no-processes", action="store_true", help="Skip read-only process inspection.")
    parser.add_argument("--timeout", type=float, default=20.0, help="Timeout in seconds for each Codex CLI readback.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    legacy_roots = tuple(args.legacy_root) if args.legacy_root else DEFAULT_LEGACY_ROOTS
    report = build_report(
        project_root=args.project_root,
        config_path=args.config_path,
        legacy_roots=legacy_roots,
        include_codex_mcp=not args.no_codex_mcp,
        include_processes=not args.no_processes,
        timeout=args.timeout,
    )
    print(json.dumps(report, indent=2 if args.pretty else None, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
