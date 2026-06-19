#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from pathlib import Path


SESSION_PATTERNS = [
    re.compile(r"Session ID:\s*([A-Za-z0-9_:-]+)"),
    re.compile(r'"session_id"\s*:\s*"([^"]+)"'),
    re.compile(r"\bses_[A-Za-z0-9_:-]+"),
]

DIRECT_SUBSTITUTION_PATTERNS = {
    "python_context7_module_substitute": re.compile(r"python3\s+-m\s+context7", re.I),
    "which_context7_cli_substitute": re.compile(r"\bwhich\s+context7-", re.I),
    "npx_context7_backend_substitute": re.compile(r"npx\s+-y\s+@upstash/context7-mcp", re.I),
    "direct_context7_stdio_substitute": re.compile(r'"method"\s*:\s*"tools/(list|call)"'),
    "direct_pi_context7_tool_substitute": re.compile(
        r"\b(?:cf_)?context7[_-][A-Za-z0-9_.:-]*context7-local-(?:resolve-library-id|query-docs)\b",
        re.I,
    ),
    "pi_bash_tool_validation_substitute": re.compile(r"(?m)^\s*Tool:\s*bash\b"),
    "pi_contextforge_state_file_inspection": re.compile(r"\b(?:cat|head|tail)\s+/workspace/\.project/context_forge_state\.json\b"),
    "pi_contextforge_state_direct_mutation": re.compile(
        r"open\(['\"]\.project/context_forge_state\.json['\"]\s*,\s*['\"]w['\"]\)|"
        r"json\.dump\(state,\s*f|"
        r"['\"](?:mode|validation_status)['\"]\]\s*=\s*['\"]presumed_working['\"]",
        re.I,
    ),
}

REJECTION_PATTERNS = {
    "validation_results_insufficient": re.compile(r"validation_results_insufficient"),
    "permission_intent_failure": re.compile(r"PermissionError|explicit validation intent", re.I),
    "tool_not_found": re.compile(r"TOOL_NOT_FOUND|No module named context7|Command exited with code 1"),
    "validation_could_not_run": re.compile(r"validation couldn't run|validation could not run", re.I),
}

PRESUMED_WORKING_ACTION_PATTERNS = [
    re.compile(r'"validation_mode"\s*:\s*"presume_working"'),
    re.compile(r'"validationMode"\s*:\s*"presume_working"'),
    re.compile(r"client_reload_recorded_presume_working_requested"),
    re.compile(r"record(?:ing)? validation as presume[sd]?[-_ ]working", re.I),
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify Use Case 1 full agent-session evidence.")
    parser.add_argument("--client", choices=["pi", "opencode"], required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--session-id", default="")
    parser.add_argument("--format", choices=["json"], default="json")
    args = parser.parse_args(argv)

    text = expand_embedded_session_export(args.evidence.read_text(encoding="utf-8", errors="replace"))
    result = verify(client=args.client, evidence_path=args.evidence, text=text, session_id=args.session_id)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


def verify(*, client: str, evidence_path: Path, text: str, session_id: str = "") -> dict[str, object]:
    failures: list[dict[str, str]] = []
    checks: dict[str, bool] = {}

    detected_session = session_id or detect_session_id(text)
    checks["stable_session_id"] = bool(detected_session)
    if not detected_session:
        failures.append(failure("missing_session_id", "evidence must include or supply a stable session id"))

    checks["workspace_surface"] = "/workspace" in text
    if not checks["workspace_surface"]:
        failures.append(failure("missing_workspace_surface", "evidence must show the /workspace project root"))

    checks["qwen_model_visible"] = "qwen3.6-a3b" in text or "Qwen 3.6" in text
    if not checks["qwen_model_visible"]:
        failures.append(failure("missing_qwen_model", "evidence must show the qwen3.6-a3b model surface"))

    checks["context7_selected"] = "context7:canonical" in text
    if not checks["context7_selected"]:
        failures.append(failure("missing_context7_selection", "evidence must show context7:canonical"))

    checks["observed_tool_outputs"] = any(marker in text for marker in ("**Output:**", '"role":"toolResult"', '"toolResult"', "Tool:"))
    if not checks["observed_tool_outputs"]:
        failures.append(failure("missing_observed_outputs", "evidence must include observed assistant/tool outputs"))

    checks.update(verify_persistent_container_surface(client, text, failures))

    for name, pattern in REJECTION_PATTERNS.items():
        if pattern.search(text):
            failures.append(failure(name, "passing gate evidence must not contain helper rejection or missing-tool recovery"))
    if any(pattern.search(text) for pattern in PRESUMED_WORKING_ACTION_PATTERNS):
        failures.append(failure("presumed_working_validation", "passing gate evidence must not record presumed-working validation"))

    if client == "pi":
        checks.update(verify_pi(text, failures))
    else:
        checks.update(verify_opencode(text, failures))

    return {
        "ok": not failures,
        "client": client,
        "evidence": str(evidence_path),
        "session_id": detected_session,
        "checks": checks,
        "failures": failures,
    }


def expand_embedded_session_export(text: str) -> str:
    match = re.search(
        r"<script[^>]*\bid=[\"']session-data[\"'][^>]*>([\s\S]*?)</script>",
        text,
        re.I,
    )
    if not match:
        return text
    payload = re.sub(r"\s+", "", match.group(1))
    try:
        decoded = base64.b64decode(payload).decode("utf-8", errors="replace")
        data = json.loads(decoded)
    except Exception:
        return text
    return "\n".join([text, "\n# decoded-session-data", render_session_data(data), decoded])


def render_session_data(data: object) -> str:
    if not isinstance(data, dict):
        return ""
    lines: list[str] = []
    header = data.get("header")
    if isinstance(header, dict):
        if header.get("id"):
            lines.append(f"Session ID: {header['id']}")
        if header.get("cwd"):
            lines.append(f"CWD: {header['cwd']}")
    calls_by_id: dict[str, str] = {}
    for entry in data.get("entries", []):
        if not isinstance(entry, dict):
            continue
        if entry.get("type") == "model_change" and entry.get("modelId"):
            lines.append(f"Model: {entry['modelId']}")
        if entry.get("type") == "custom_message" and entry.get("content"):
            lines.append(f"Custom: {entry['content']}")
        message = entry.get("message")
        if not isinstance(message, dict):
            continue
        role = message.get("role", "message")
        if message.get("model"):
            lines.append(f"Model: {message['model']}")
        content = message.get("content", [])
        if not isinstance(content, list):
            continue
        if role in {"user", "assistant"}:
            rendered_text = "\n".join(part.get("text", "") for part in content if isinstance(part, dict) and part.get("type") == "text")
            if rendered_text:
                lines.append(f"{str(role).title()}: {rendered_text}")
            for part in content:
                if not isinstance(part, dict) or part.get("type") != "toolCall":
                    continue
                tool_name = str(part.get("name", ""))
                if part.get("id"):
                    calls_by_id[str(part["id"])] = tool_name
                lines.append(f"Tool: {tool_name}")
                lines.append(f"Input: {json.dumps(part.get('arguments', {}), sort_keys=True)}")
        elif role == "toolResult":
            tool_name = str(message.get("toolName") or calls_by_id.get(str(message.get("toolCallId", "")), "unknown"))
            lines.append(f"ToolResult: {tool_name}")
            rendered_text = "\n".join(part.get("text", "") for part in content if isinstance(part, dict) and part.get("type") == "text")
            if rendered_text:
                lines.append(f"Output: {rendered_text}")
    return "\n".join(lines)


def verify_persistent_container_surface(client: str, text: str, failures: list[dict[str, str]]) -> dict[str, bool]:
    service = re.escape(client)
    client_cleanup_pattern = re.compile(rf"\bdocker\s+compose\b[^\n]*\brm\b[^\n]*\b{service}\b")
    reset_script_pattern = re.compile(
        rf"reset-client-harness-state\.py[^\n]*--client\s+{service}\b|"
        rf'"client"\s*:\s*"{service}"'
    )
    non_ephemeral_launch_pattern = re.compile(
        rf"\bdocker\s+compose\b[^\n]*\brun\b(?=[^\n]*\b{service}\b)(?![^\n]*\b{service}-ephemeral\b)(?![^\n]*\s--rm\b)"
    )
    reset_postcondition = (
        '"postcondition": true' in text
        or "client_reset.postcondition=true" in text
        or "client_reset.postcondition: true" in text
    )
    reset_workspace_postcondition = (
        '"workspace_reset"' in text
        or "workspace_reset.postcondition=true" in text
        or "workspace_reset.postcondition: true" in text
    )
    reset_script_cleanup = bool(reset_script_pattern.search(text)) and all(
        (reset_postcondition, reset_workspace_postcondition, "remaining_target_volume_containers" in text)
    )
    checks = {
        "client_stale_container_cleanup": bool(client_cleanup_pattern.search(text)) or reset_script_cleanup,
        "non_ephemeral_container_launch": bool(non_ephemeral_launch_pattern.search(text)),
        "no_ephemeral_container_launch": True,
    }
    if not checks["client_stale_container_cleanup"]:
        failures.append(
            failure(
                "missing_client_stale_container_cleanup",
                f"{client} evidence must show stale-container cleanup scoped to the target client",
            )
        )
    if not checks["non_ephemeral_container_launch"]:
        failures.append(
            failure(
                "missing_non_ephemeral_container_launch",
                f"{client} evidence must show non-ephemeral Docker client harness launch",
            )
        )
    launch_lines = [
        line for line in text.splitlines() if re.search(r"\bdocker\s+compose\b", line) and re.search(r"\brun\b", line)
    ]
    ephemeral_launches = [
        line
        for line in launch_lines
        if re.search(r"\b(?:pi|opencode)-ephemeral\b", line)
        or re.search(r"\s--rm\b", line)
        or re.search(r"\btmpfs\b", line, re.I)
    ]
    if ephemeral_launches:
        checks["no_ephemeral_container_launch"] = False
        failures.append(
            failure(
                "ephemeral_container_launch",
                "dialogue validation must not launch with --rm, ephemeral services, or tmpfs workspace modes",
            )
        )
    return checks


def verify_pi(text: str, failures: list[dict[str, str]]) -> dict[str, bool]:
    reload_index = first_tool_call_index(text, ["cf_project_init_record_client_reload"])
    validate_index = first_tool_call_index(text, ["cf_contextforge_pi_validate"])
    record_index = first_tool_call_index(text, ["cf_project_init_record_validation"])
    validation_complete_index = text.find("pi_validation_complete", validate_index) if validate_index >= 0 else -1
    validation_recorded_index = text.find("validation_recorded", record_index) if record_index >= 0 else -1
    project_initialized_index = first_index_from(text, ["project_status", "initialized"], record_index)
    checks = {
        "pi_reload_recorded": reload_index >= 0,
        "pi_validate_tool_called": validate_index >= 0,
        "pi_validation_complete": validation_complete_index >= 0,
        "record_validation_called": record_index >= 0,
        "record_validation_after_validate": record_index >= 0 and validate_index >= 0 and record_index > validate_index,
        "validation_recorded": validation_recorded_index >= 0,
        "project_initialized": project_initialized_index >= 0,
    }
    required_messages = {
        "pi_reload_recorded": "Pi gate requires cf_project_init_record_client_reload",
        "pi_validate_tool_called": "Pi gate requires cf_contextforge_pi_validate",
        "pi_validation_complete": "Pi gate requires pi_validation_complete output",
        "record_validation_called": "Pi gate requires cf_project_init_record_validation",
        "validation_recorded": "Pi gate requires status=validation_recorded",
        "project_initialized": "Pi gate requires project_status=initialized",
    }
    for check, message in required_messages.items():
        if not checks[check]:
            failures.append(failure(check, message))
    if not checks["record_validation_after_validate"]:
        failures.append(
            failure(
                "pi_record_validation_before_validate",
                "Pi passing evidence must call cf_contextforge_pi_validate before record-validation",
            )
        )

    for name, pattern in DIRECT_SUBSTITUTION_PATTERNS.items():
        if pattern.search(text):
            failures.append(failure(name, "Pi validation must use the Pi-visible ContextForge shim, not shell/backend substitutes"))
    return checks


def verify_opencode(text: str, failures: list[dict[str, str]]) -> dict[str, bool]:
    safe_probe_index = first_index(text, ["context7_context7-local-resolve-library-id", "context7_context7-local-query-docs"])
    record_index = first_index(text, ["cf_project_init_record_validation", "contextforge-helper_cf_project_init_record_validation"])
    checks = {
        "opencode_context_checked": any(
            marker in text
            for marker in (
                "cf_project_init_get_context",
                "contextforge-helper_cf_project_init_get_context",
                "contextforge-helper_get_project_context",
            )
        ),
        "opencode_reload_recorded": "cf_project_init_record_client_reload" in text,
        "opencode_safe_probe_called": safe_probe_index >= 0,
        "record_validation_called": record_index >= 0,
        "record_validation_after_safe_probe": record_index >= 0 and safe_probe_index >= 0 and record_index > safe_probe_index,
        "validation_recorded": "validation_recorded" in text,
        "project_initialized": "project_status" in text and "initialized" in text,
        "target_client_recorded": '"target_client": "opencode"' in text or '"target_client":"opencode"' in text,
    }
    required_messages = {
        "opencode_context_checked": "OpenCode gate requires helper context check",
        "opencode_reload_recorded": "OpenCode gate requires cf_project_init_record_client_reload",
        "opencode_safe_probe_called": "OpenCode gate requires an OpenCode-visible Context7 safe probe",
        "record_validation_called": "OpenCode gate requires cf_project_init_record_validation",
        "validation_recorded": "OpenCode gate requires status=validation_recorded",
        "project_initialized": "OpenCode gate requires project_status=initialized",
        "target_client_recorded": "OpenCode gate requires target_client=opencode in validation results",
    }
    for check, message in required_messages.items():
        if not checks[check]:
            failures.append(failure(check, message))
    if not checks["record_validation_after_safe_probe"]:
        failures.append(
            failure(
                "record_validation_before_safe_probe",
                "OpenCode passing evidence must call the Context7 safe probe before record-validation",
            )
        )
    return checks


def detect_session_id(text: str) -> str:
    for pattern in SESSION_PATTERNS:
        match = pattern.search(text)
        if match:
            if match.groups():
                return match.group(1)
            return match.group(0)
    return ""


def first_index(text: str, needles: list[str]) -> int:
    positions = [text.find(needle) for needle in needles if text.find(needle) >= 0]
    return min(positions) if positions else -1


def first_index_from(text: str, needles: list[str], start: int) -> int:
    if start < 0:
        return -1
    positions = [text.find(needle, start) for needle in needles if text.find(needle, start) >= 0]
    return max(positions) if len(positions) == len(needles) else -1


def first_tool_call_index(text: str, tool_names: list[str]) -> int:
    positions: list[int] = []
    for tool_name in tool_names:
        escaped = re.escape(tool_name)
        patterns = [
            re.compile(rf"(?m)^\s*Tool:\s*{escaped}\b"),
            re.compile(rf'"name"\s*:\s*"{escaped}"'),
            re.compile(rf'"toolName"\s*:\s*"{escaped}"'),
            re.compile(rf'"tool_name"\s*:\s*"{escaped}"'),
        ]
        for pattern in patterns:
            match = pattern.search(text)
            if match:
                positions.append(match.start())
    return min(positions) if positions else -1


def failure(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


if __name__ == "__main__":
    sys.exit(main())
