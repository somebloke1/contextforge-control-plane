#!/usr/bin/env python3
from __future__ import annotations

import argparse
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
}

REJECTION_PATTERNS = {
    "validation_results_insufficient": re.compile(r"validation_results_insufficient"),
    "permission_intent_failure": re.compile(r"PermissionError|explicit validation intent", re.I),
    "tool_not_found": re.compile(r"TOOL_NOT_FOUND|No module named context7|Command exited with code 1"),
    "validation_could_not_run": re.compile(r"validation couldn't run|validation could not run", re.I),
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify Use Case 1 full agent-session evidence.")
    parser.add_argument("--client", choices=["pi", "opencode"], required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--session-id", default="")
    parser.add_argument("--format", choices=["json"], default="json")
    args = parser.parse_args(argv)

    text = args.evidence.read_text(encoding="utf-8", errors="replace")
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

    for name, pattern in REJECTION_PATTERNS.items():
        if pattern.search(text):
            failures.append(failure(name, "passing gate evidence must not contain helper rejection or missing-tool recovery"))

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


def verify_pi(text: str, failures: list[dict[str, str]]) -> dict[str, bool]:
    checks = {
        "pi_reload_recorded": "cf_project_init_record_client_reload" in text,
        "pi_validate_tool_called": "cf_contextforge_pi_validate" in text,
        "pi_validation_complete": "pi_validation_complete" in text,
        "record_validation_called": "cf_project_init_record_validation" in text,
        "validation_recorded": "validation_recorded" in text,
        "project_initialized": "project_status" in text and "initialized" in text,
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

    for name, pattern in DIRECT_SUBSTITUTION_PATTERNS.items():
        if pattern.search(text):
            failures.append(failure(name, "Pi validation must use the Pi-visible ContextForge shim, not shell/backend substitutes"))
    return checks


def verify_opencode(text: str, failures: list[dict[str, str]]) -> dict[str, bool]:
    safe_probe_index = first_index(text, ["context7_context7-local-resolve-library-id", "context7_context7-local-query-docs"])
    record_index = first_index(text, ["cf_project_init_record_validation", "contextforge-helper_cf_project_init_record_validation"])
    checks = {
        "opencode_context_checked": "cf_project_init_get_context" in text or "contextforge-helper_cf_project_init_get_context" in text,
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


def failure(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


if __name__ == "__main__":
    sys.exit(main())
