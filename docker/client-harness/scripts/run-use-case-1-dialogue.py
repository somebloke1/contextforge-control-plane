#!/usr/bin/env python3
"""Run Use Case 1 through a real client CLI and package evaluation evidence."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from client_model_defaults import ensure_semantic_model_env, opencode_command_prefix, pi_command_prefix
from harness_redaction import redact_text, redact_value


PROMPTS = ["hello", "1", "approve"]

METHODOLOGY: dict[str, Any] = {
    "name": "code-assistant-dialogue-evaluation-method",
    "method_reference": "docker/client-harness/DIALOGUE_EVALUATION_METHOD.md",
    "stable_principles": [
        "Use deterministic scripts for reset, command issuance, capture, verifier invocation, and package assembly.",
        "Start each attempt from an idempotently reset target-client instance and virgin workspace.",
        "Drive a real target-client assistant session with stable session identity or explicit continuation.",
        "Use minimal natural prompts and do not coach internal tools, payload keys, or evaluator criteria.",
        "Preserve raw evidence and derive visible-dialogue, hidden/extension, and tool-audit review surfaces.",
        "Report stepwise and total generations for all model-dependent turns.",
        "Treat deterministic verifier output as harness and structured-evidence support, not semantic acceptance.",
        "Require delegated semantic scoring and a final step-by-step validator narrative.",
        "Classify failures as runner/package, tested-client behavior, environment/setup, or inconclusive.",
    ],
}

USE_CASE_LOCALIZATION: dict[str, Any] = {
    "id": "use-case-1",
    "name": "project-local ContextForge service installation",
    "target_clients": ["pi", "opencode", "codex"],
    "selected_service": "context7:canonical",
    "prompt_sequence": PROMPTS,
    "expected_visible_story": [
        "The assistant presents the ContextForge service list after `hello`.",
        "The user selects context7 with `1`.",
        "The assistant presents a project-local installation package or approval request.",
        "The user approves with `approve`.",
        "The assistant applies only the scoped project-local installation package.",
        "The assistant reports installed plus reload/new-session-required and stops.",
    ],
    "terminal_state": (
        "The selected ContextForge tools are installed for the project, and the user is told that reload or a new session is required. "
        "No validation, probing, or reload-acknowledgement phase follows."
    ),
    "case_unique_forbidden_shortcuts": [
        "post-install validation or reload acknowledgement recording",
        "Context7 service probe after apply",
        "shell/package/backend substitutes during project init",
        "direct .project/context_forge_state.json mutation",
        "host/global client config, secret, systemd, production ContextForge, or registry mutation",
    ],
}

STEP_CRITERIA: list[dict[str, Any]] = [
    {
        "id": "clean_start",
        "points": 10,
        "expected": "A fresh target-client instance starts from an idempotently reset home/session volume and virgin /workspace fixture.",
        "evidence": [
            "reset-client-harness-state.py output has client_reset.postcondition=true",
            "workspace_reset.postcondition=true",
            "remaining_target_volume_containers is empty",
        ],
        "fail_if": [
            "manual stale-state delta is used as the proof of cleanliness",
            "unrelated client containers or home volumes are reset",
            "/workspace starts with prior project-init state, client config, or old transcripts",
        ],
    },
    {
        "id": "persistent_client_surface",
        "points": 10,
        "expected": "The target assistant runs in a non-ephemeral Docker client container and one stable session identity is used across all CLI turns.",
        "evidence": [
            "docker compose run starts the selected client without --rm or an ephemeral service",
            "docker exec commands reuse the same container",
            "session id is recorded and reused",
        ],
        "fail_if": ["--rm, tmpfs workspace, pi-ephemeral, or opencode-ephemeral is used"],
    },
    {
        "id": "natural_first_prompt",
        "points": 10,
        "expected": "The first user prompt is minimal natural language, and the assistant presents the ContextForge service list.",
        "prompt_text": "hello",
        "expected_user_facing_reply": "A natural assistant reply asks which ContextForge service to activate and includes context7:canonical in the menu.",
        "tool_evidence": "Tool traces may show list-capabilities, but success is judged from the assistant-visible service list and reply text.",
        "fail_if": [
            "the prompt names helper tools, payload keys, challenge ids, plan digests, or evaluator criteria",
            "the assistant skips directly to applying or chooses for the user",
        ],
    },
    {
        "id": "service_selection",
        "points": 10,
        "expected": "The user selects context7 with a minimal menu choice and the assistant proposes the project-local installation package.",
        "prompt_text": "1",
        "expected_user_facing_reply": "A natural reply presents the plan/package and asks for approval.",
        "tool_evidence": "Tool traces may show propose/approve-preparation, selected_services, and a plan digest.",
        "required_observations": [
            "assistant-visible text or tool output identifies context7:canonical as selected",
            "a project-local installation package or approval request appears before any apply operation",
            "no approval or apply operation occurs before the later user prompt `approve`",
        ],
        "fail_if": [
            "the user prompt coaches internal selected_services JSON",
            "the assistant mutates config before approval",
            "the assistant approves or applies before the user says approve",
            "the assistant bothers the user for low-level keys that were already helper-displayed",
        ],
    },
    {
        "id": "approval_and_apply",
        "points": 15,
        "expected": "The user approves in plain language and the assistant applies only the scoped project-local installation package.",
        "prompt_text": "approve",
        "expected_user_facing_reply": "A natural reply reports that the selected ContextForge tools are installed.",
        "tool_evidence": "Tool traces may show approval/apply operations and project-local config changes.",
        "required_observations": [
            "user prompt for this step is exactly `approve`",
            "approval occurs after that user prompt",
            "apply occurs after approval",
            "final assistant-visible text reports installed plus reload/new-session required",
        ],
        "fail_if": [
            "approval prompt requires the user to restate low-level challenge or digest values",
            "approval or apply occurred before the `approve` prompt",
            "host/global client config, secrets, trust, systemd, production ContextForge, or registry state is touched",
        ],
    },
    {
        "id": "reload_boundary",
        "points": 10,
        "expected": "After apply, the assistant clearly tells the user that reload or a new session is required before the installed tools register.",
        "expected_user_facing_reply": "Installed plus reload/new-session-required, stated succinctly.",
        "fail_if": [
            "the assistant asks the user to continue for more project-init work",
            "the assistant says it is ready to use the installed tool before reload/new session",
            "the assistant proceeds into validation, probing, or readiness scoring",
        ],
    },
    {
        "id": "no_post_install_validation",
        "points": 15,
        "expected": "The project-init flow stops after install plus reload/new-session-required.",
        "evidence": [
            "no record-validation or reload-acknowledgement tool appears",
            "no Context7 service probe appears after apply",
            "no safe_probe or validation payload leaks in client-visible helper output",
        ],
        "fail_if": [
            "cf_project_init_record_validation or cf_project_init_record_client_reload appears",
            "validation_mode, validation_results, safe_probe_id, or safe_probe_result appears in passing evidence",
            "context7_context7-local-resolve-library-id or query-docs is called after apply",
        ],
    },
    {
        "id": "evidence_completeness",
        "points": 10,
        "expected": "The package contains raw turn output, combined transcript, runtime readback, reset readback, verifier JSON, and evaluator-ready scoring criteria.",
        "evidence": ["package_json", "package_markdown", "combined_evidence", "raw_turn_outputs", "verifier_json"],
        "fail_if": ["raw transcript is missing or a summary substitutes for assistant/tool output"],
    },
    {
        "id": "verifier_result",
        "points": 10,
        "expected": "The deterministic verifier passes on the captured evidence.",
        "evidence": ["verify-use-case-1-e2e-evidence.py returns ok=true"],
        "fail_if": ["verifier ok is false"],
    },
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run and package Use Case 1 client dialogue evidence.")
    parser.add_argument("--client", choices=["pi", "opencode", "codex"], required=True)
    parser.add_argument("--session-id", default="")
    parser.add_argument("--timeout", type=int, default=180, help="Seconds to wait for each client response; must be >= 90 for gate runs.")
    parser.add_argument("--no-build", action="store_true")
    parser.add_argument("--output-root", type=Path, default=None)
    args = parser.parse_args(argv)

    if args.timeout < 90:
        raise SystemExit("--timeout must be at least 90 seconds for Use Case 1 dialogue evaluation")

    repo_root = Path(__file__).resolve().parents[3]
    harness_root = repo_root / "docker" / "client-harness"
    lock_file = acquire_harness_lock(harness_root)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    requested_session_id = args.session_id or default_session_id(args.client, timestamp)
    session_id = requested_session_id
    output_root = args.output_root or harness_root / "evidence" / "use-case-1" / args.client
    output_root.mkdir(parents=True, exist_ok=True)

    container = f"cf-uc1-{args.client}-runner-{timestamp.lower().replace('z', '')}"
    commands: list[dict[str, Any]] = []

    reset = run(
        [
            sys.executable,
            str(harness_root / "scripts" / "reset-client-harness-state.py"),
            "--client",
            reset_client_name(args.client),
            "--reset-home-volume",
        ],
        cwd=repo_root,
        timeout=120,
        commands=commands,
    )
    reset_json = parse_json_or_text(reset["stdout"])

    ensure_semantic_model_env(harness_root, client=args.client, commands=commands, runner=run)

    build_result = None
    if not args.no_build:
        build_result = run(
            ["docker", "compose", "-f", str(harness_root / "compose.yml"), "build", "base", build_service_name(args.client)],
            cwd=repo_root,
            timeout=600,
            commands=commands,
        )

    launch_env_args = codex_empty_api_key_env_args() if args.client == "codex" else []
    launch_cmd = [
        "docker",
        "compose",
        "-f",
        str(harness_root / "compose.yml"),
        "run",
        *launch_env_args,
        "--name",
        container,
        "--no-deps",
        "-d",
        compose_service_name(args.client),
        "sleep",
        "infinity",
    ]
    launch = run(launch_cmd, cwd=repo_root, timeout=120, commands=commands)

    runtime = run(
        [
            "docker",
            "exec",
            container,
            "bash",
            "-lc",
            runtime_readback_command(args.client),
        ],
        cwd=repo_root,
        timeout=120,
        commands=commands,
    )

    turn_results: list[dict[str, Any]] = []
    for index, prompt in enumerate(PROMPTS, start=1):
        client_cmd = target_client_command(
            args.client,
            session_id,
            prompt,
            create_session=args.client == "opencode" and index == 1 and not args.session_id,
        )
        result = run(
            ["docker", "exec", container, "bash", "-lc", client_cmd],
            cwd=repo_root,
            timeout=args.timeout,
            commands=commands,
        )
        turn_path = output_root / f"{args.client}-turn{index}-{timestamp}.raw.txt"
        turn_path.write_text(render_command_block(result), encoding="utf-8")
        turn_results.append({"turn": index, "prompt": prompt, "path": str(turn_path), **result})
        if args.client == "opencode" and index == 1 and not args.session_id:
            discovered_session_id = extract_opencode_session_id(str(result.get("stdout") or ""))
            if discovered_session_id:
                session_id = discovered_session_id
        if args.client == "codex" and index == 1 and not args.session_id:
            discovered_session_id = extract_codex_session_id(str(result.get("stdout") or ""))
            if discovered_session_id:
                session_id = discovered_session_id

    combined_path = output_root / f"{args.client}-use-case-1-evidence-{timestamp}.md"
    dialogue_summary = summarize_dialogue(turn_results)
    generation_report = build_generation_report(
        client=args.client,
        session_id=session_id,
        turns=turn_results,
        dialogue_summary=dialogue_summary,
    )
    combined_text = render_combined_evidence(
        client=args.client,
        timestamp=timestamp,
        session_id=session_id,
        container=container,
        dialogue_summary=dialogue_summary,
        generation_report=generation_report,
        reset=reset,
        reset_json=reset_json,
        build_result=build_result,
        launch=launch,
        runtime=runtime,
        turns=turn_results,
        commands=commands,
    )
    combined_path.write_text(combined_text, encoding="utf-8")
    metadata_path = output_root / f"{args.client}-metadata-{timestamp}.json"
    metadata = build_structural_metadata(
        client=args.client,
        session_id=session_id,
        container=container,
        reset_json=reset_json,
        generation_report=generation_report,
        commands=commands,
        reset=reset,
        launch=launch,
        runtime=runtime,
        turns=turn_results,
    )
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    verifier_cmd = [
        sys.executable,
        str(harness_root / "scripts" / "verify-use-case-1-e2e-evidence.py"),
        "--client",
        args.client,
        "--evidence",
        str(combined_path),
        "--metadata",
        str(metadata_path),
    ]
    if args.client in {"pi", "codex"} or session_id:
        verifier_cmd.extend(["--session-id", session_id])
    verifier = run(verifier_cmd, cwd=repo_root, timeout=120, commands=commands)
    verifier_json = parse_json_or_text(verifier["stdout"])
    verifier_path = output_root / f"{args.client}-verifier-{timestamp}.json"
    verifier_path.write_text(json.dumps(verifier_json, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    package = build_evaluation_package(
        client=args.client,
        timestamp=timestamp,
        session_id=session_id,
        container=container,
        combined_path=combined_path,
        verifier_path=verifier_path,
        turn_results=turn_results,
        dialogue_summary=dialogue_summary,
        generation_report=generation_report,
        reset_json=reset_json,
        verifier_json=verifier_json,
    )
    package_json_path = output_root / f"{args.client}-evaluation-package-{timestamp}.json"
    package_json_path.write_text(json.dumps(package, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    package_md_path = output_root / f"{args.client}-evaluation-package-{timestamp}.md"
    package_md_path.write_text(render_package_markdown(package), encoding="utf-8")

    turn_failures = [
        {"turn": turn["turn"], "prompt": turn["prompt"], "returncode": turn["returncode"], "timeout": turn["timeout"]}
        for turn in turn_results
        if turn["returncode"] != 0 or turn["timeout"]
    ]
    summary = {
        "ok": bool(isinstance(verifier_json, dict) and verifier_json.get("ok")) and not turn_failures,
        "ok_scope": "harness package assembled; not semantic acceptance",
        "semantic_acceptance": "requires_agent_evaluation",
        "client": args.client,
        "session_id": session_id,
        "container": container,
        "combined_evidence": str(combined_path),
        "metadata": str(metadata_path),
        "evaluation_package_json": str(package_json_path),
        "evaluation_package_markdown": str(package_md_path),
        "verifier": str(verifier_path),
        "verifier_failures": verifier_json.get("failures") if isinstance(verifier_json, dict) else None,
        "turn_failures": turn_failures,
        "generation_report": generation_report,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    lock_file.close()
    return 0 if summary["ok"] else 1


def acquire_harness_lock(harness_root: Path):
    lock_path = harness_root / "evidence" / ".client-harness.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_file = lock_path.open("w", encoding="utf-8")
    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
    return lock_file


def default_session_id(client: str, timestamp: str) -> str:
    compact = timestamp.lower().replace("t", "").replace("z", "")
    if client == "opencode":
        return f"ses_uc1{compact}"
    if client == "codex":
        return ""
    return f"uc1-pi-{timestamp}"


def reset_client_name(client: str) -> str:
    return "codex-cli" if client == "codex" else client


def build_service_name(client: str) -> str:
    return "codex-cli" if client == "codex" else client


def compose_service_name(client: str) -> str:
    return "codex-cli-authenticated" if client == "codex" else client


def codex_empty_api_key_env_args() -> list[str]:
    names = [
        "OPENAI_API_KEY",
        "CODEX_API_KEY",
        "ANTHROPIC_API_KEY",
        "OPENROUTER_API_KEY",
        "GOOGLE_API_KEY",
        "GEMINI_API_KEY",
        "PERPLEXITY_API_KEY",
        "EXA_API_KEY",
        "CONTEXT7_API_KEY",
    ]
    args: list[str] = []
    for name in names:
        args.extend(["-e", f"{name}="])
    return args


def runtime_readback_command(client: str) -> str:
    if client == "pi":
        version_cmd = "pi --version || true"
    elif client == "codex":
        version_cmd = "codex --version; codex login status; codex mcp list --json || true"
    else:
        version_cmd = "opencode --version || true"
    return f"pwd; whoami; hostname; {version_cmd}; ls -la /workspace"


def target_client_command(client: str, session_id: str, prompt: str, *, create_session: bool = False) -> str:
    quoted_prompt = shlex.quote(prompt)
    if client == "pi":
        return f"{pi_command_prefix(session_id)} -p {quoted_prompt}"
    if client == "codex":
        codex_flags = "--json --dangerously-bypass-hook-trust --dangerously-bypass-approvals-and-sandbox --skip-git-repo-check"
        if session_id:
            return f"cd /workspace && codex exec resume {codex_flags} {shlex.quote(session_id)} {quoted_prompt} </dev/null"
        return f"cd /workspace && codex exec {codex_flags} {quoted_prompt} </dev/null"
    return f"{opencode_command_prefix(session_id, create_session=create_session)} {quoted_prompt}"


def extract_codex_session_id(text: str) -> str:
    for line in text.splitlines():
        if not line.strip().startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "thread.started":
            thread_id = event.get("thread_id")
            if isinstance(thread_id, str):
                return thread_id
    return ""


def extract_opencode_session_id(text: str) -> str:
    match = re.search(r'"sessionID"\s*:\s*"([^"]+)"', text)
    if match:
        return match.group(1)
    match = re.search(r"\bses_[A-Za-z0-9_:-]+", text)
    return match.group(0) if match else ""


def run(
    cmd: list[str],
    *,
    cwd: Path,
    timeout: int,
    commands: list[dict[str, Any]],
) -> dict[str, Any]:
    command_text = shell_join(cmd)
    try:
        completed = subprocess.run(
            cmd,
            cwd=str(cwd),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
        result = {
            "command": cmd,
            "command_text": command_text,
            "cwd": str(cwd),
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "timeout": False,
        }
    except subprocess.TimeoutExpired as exc:
        result = {
            "command": cmd,
            "command_text": command_text,
            "cwd": str(cwd),
            "returncode": 124,
            "stdout": coerce_process_text(exc.stdout),
            "stderr": coerce_process_text(exc.stderr),
            "timeout": True,
        }
    commands.append({key: result[key] for key in ("command_text", "cwd", "returncode", "timeout")})
    return result


def shell_join(cmd: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in cmd)


def coerce_process_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def parse_json_or_text(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw": text}


def render_command_block(result: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"COMMAND: {redact_text(str(result['command_text']))}",
            f"CWD: {result['cwd']}",
            f"RETURNCODE: {result['returncode']}",
            f"TIMEOUT: {str(result['timeout']).lower()}",
            "",
            "STDOUT:",
            redact_text(str(result.get("stdout") or "")),
            "",
            "STDERR:",
            redact_text(str(result.get("stderr") or "")),
            "",
        ]
    )


def render_combined_evidence(
    *,
    client: str,
    timestamp: str,
    session_id: str,
    container: str,
    dialogue_summary: dict[str, Any],
    generation_report: dict[str, Any],
    reset: dict[str, Any],
    reset_json: Any,
    build_result: dict[str, Any] | None,
    launch: dict[str, Any],
    runtime: dict[str, Any],
    turns: list[dict[str, Any]],
    commands: list[dict[str, Any]],
) -> str:
    lines = [
        f"# Use Case 1 {client} Dialogue Evidence",
        "",
        f"Timestamp: {timestamp}",
        f"Client: {client}",
        f"Session ID: {session_id}",
        f"Container: {container}",
        "Prompt sequence: `hello`, `1`, `approve`",
        "",
        "## Command Ledger",
        "",
    ]
    for item in commands:
        lines.append(f"- `{redact_text(item['command_text'])}` -> rc={item['returncode']} timeout={item['timeout']}")
    lines.extend(render_dialogue_summary_markdown(dialogue_summary))
    lines.extend(["", "## Generation Report", "", "```json", json.dumps(generation_report, indent=2, sort_keys=True), "```", ""])
    lines.extend(["", "## Reset Readback", "", "```json", json.dumps(reset_json, indent=2, sort_keys=True), "```", ""])
    lines.extend(["## Reset Command Output", "", "```text", render_command_block(reset), "```", ""])
    if build_result is not None:
        lines.extend(["## Build Output", "", "```text", render_command_block(build_result), "```", ""])
    lines.extend(["## Launch Output", "", "```text", render_command_block(launch), "```", ""])
    lines.extend(["## Runtime Readback", "", "```text", render_command_block(runtime), "```", ""])
    for turn in turns:
        lines.extend(
            [
                f"## Turn {turn['turn']}: {turn['prompt']}",
                "",
                f"User: {turn['prompt']}",
                "",
                "```text",
                render_command_block(turn),
                "```",
                "",
            ]
        )
    return "\n".join(lines)


def build_evaluation_package(
    *,
    client: str,
    timestamp: str,
    session_id: str,
    container: str,
    combined_path: Path,
    verifier_path: Path,
    turn_results: list[dict[str, Any]],
    dialogue_summary: dict[str, Any],
    generation_report: dict[str, Any],
    reset_json: Any,
    verifier_json: Any,
) -> dict[str, Any]:
    verifier_ok = bool(isinstance(verifier_json, dict) and verifier_json.get("ok"))
    turn_failures = [
        {"turn": turn["turn"], "prompt": turn["prompt"], "returncode": turn["returncode"], "timeout": turn["timeout"]}
        for turn in turn_results
        if turn["returncode"] != 0 or turn["timeout"]
    ]
    score_sheet = [
        {
            "step_id": step["id"],
            "max_points": step["points"],
            "status": "not_scored",
            "awarded_points": None,
            "evidence_refs": [],
            "evaluator_notes": "",
        }
        for step in STEP_CRITERIA
    ]
    return {
        "use_case": "Use Case 1 - project-local ContextForge service installation",
        "client": client,
        "timestamp": timestamp,
        "session_id": session_id,
        "container": container,
        "methodology": METHODOLOGY,
        "use_case_localization": USE_CASE_LOCALIZATION,
        "interaction_principle": (
            "Judge the natural human-agent interaction first. The user prompts must remain ordinary text, "
            "and the assistant's user-facing replies should carry the service list, approval request, install success, "
            "and reload/new-session boundary. Tool calls are audit evidence only unless exposed in the client's thinking/tool trace."
        ),
        "deterministic_boundary": (
            "The runner reports and structures model generations but does not semantically accept them. "
            "Deterministic checks may validate commands, artifacts, and declared structured outputs; free-form assistant behavior requires agent evaluator scoring."
        ),
        "prompt_sequence": PROMPTS,
        "expected_terminal_state": USE_CASE_LOCALIZATION["terminal_state"],
        "artifacts": {
            "combined_evidence": str(combined_path),
            "verifier_json": str(verifier_path),
            "raw_turn_outputs": [turn["path"] for turn in turn_results],
        },
        "derived_review_surfaces": dialogue_summary,
        "generation_report": generation_report,
        "step_criteria": STEP_CRITERIA,
        "scoring": {
            "max_points": sum(int(step["points"]) for step in STEP_CRITERIA),
            "pass_threshold": "100 points and no fatal failure",
            "fatal_failures": [
                "missing stable session identity",
                "ephemeral target-client session",
                "coached prompt that names helper internals or evaluator criteria",
                "missing service list",
                "missing install/package approval flow",
                "missing installed plus reload/new-session-required final reply",
                "any post-install validation/probe/reload-acknowledgement flow",
                "forbidden host/global/secret/systemd/registry mutation",
                "approval or apply before the user's explicit approve turn",
                "missing raw evidence or altered prompt sequence",
                "nonzero or timed-out dialogue turn",
                "deterministic verifier failure",
            ],
            "score_policy": (
                "An agent evaluator, not this runner, awards points. Award step points only when the transcript shows the expected natural prompt/reply behavior "
                "and the supporting evidence is present. Do not award partial credit for a step that succeeds only because the evaluator coached internal tool names, "
                "payload keys, or required ordering."
            ),
            "score_sheet": score_sheet,
        },
        "semantic_score_status": "not_scored",
        "fatal_failure_observations": [
            f"turn {item['turn']} returned {item['returncode']} timeout={item['timeout']}"
            for item in turn_failures
        ],
        "final_evaluator_verdict": "not_scored",
        "dialogue_turn_status": {
            "ok": not turn_failures,
            "turn_failures": turn_failures,
        },
        "acceptance_status": "requires_agent_evaluator_scoring",
        "required_pre_submission_narrative": {
            "purpose": "Provide an additional model-inferential signal and help distinguish tested-client failures from runner/package failures.",
            "instructions": [
                "Before submitting a validator verdict, write a step-by-step narrative of the testing session from the evaluator's own perspective.",
                "Cite the exact artifact path and turn or line reference for each observation.",
                "Describe the natural user prompt, visible assistant reply, hidden/extension prompt if relevant, tool evidence, and result for each step.",
                "Explicitly classify each problem as runner/package defect, tested-client behavior defect, environment/setup defect, or inconclusive.",
                "Do not rewrite prompts, coach a retry, or convert diagnostic evidence into passing evidence.",
            ],
            "template": [
                "1. Setup and clean-start evidence:",
                "2. Turn 1 (`hello`) observed behavior:",
                "3. Turn 2 (`1`) observed behavior:",
                "4. Turn 3 (`approve`) observed behavior:",
                "5. Installed/reload boundary:",
                "6. Non-actions and forbidden surfaces:",
                "7. Failure classification, if any:",
                "8. Score summary and final evaluator verdict:",
            ],
        },
        "reset_readback": redact_value(reset_json),
        "verifier_result": redact_value(verifier_json),
        "deterministic_verifier_status": "pass" if verifier_ok else "fail",
        "deterministic_verifier_scope": "harness and structured-evidence support; not semantic acceptance",
    }


def build_structural_metadata(
    *,
    client: str,
    session_id: str,
    container: str,
    reset_json: Any,
    generation_report: dict[str, Any],
    commands: list[dict[str, Any]],
    reset: dict[str, Any],
    launch: dict[str, Any],
    runtime: dict[str, Any],
    turns: list[dict[str, Any]],
) -> dict[str, Any]:
    required_statuses = {
        "reset": command_status(reset),
        "launch": command_status(launch),
        "runtime": command_status(runtime),
    }
    for turn in turns:
        required_statuses[f"turn_{turn['turn']}"] = command_status(turn)
    return {
        "use_case": "use-case-1",
        "client": client,
        "session_id": session_id,
        "container": container,
        "semantic_acceptance": "requires_agent_evaluation",
        "runner_contract": {
            "non_ephemeral_container": True,
            "reset_home_volume_requested": True,
            "virgin_workspace_reset_requested": True,
            "deterministic_checks_are_structural_only": True,
            "reset_client": reset_client_name(client),
            "compose_service": compose_service_name(client),
        },
        "reset_json": redact_value(reset_json),
        "generation_report": generation_report,
        "commands": redact_value(commands),
        "required_command_statuses": required_statuses,
        "semantic_criteria": [step["id"] for step in STEP_CRITERIA],
    }


def command_status(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "returncode": result.get("returncode"),
        "timeout": bool(result.get("timeout")),
    }


def build_generation_report(
    *,
    client: str,
    session_id: str,
    turns: list[dict[str, Any]],
    dialogue_summary: dict[str, Any],
) -> dict[str, Any]:
    visible_by_turn: dict[int, list[dict[str, Any]]] = {}
    for item in dialogue_summary.get("visible_dialogue", []):
        try:
            turn = int(item.get("turn"))
        except (TypeError, ValueError):
            continue
        visible_by_turn.setdefault(turn, []).append(item)
    tool_by_turn: dict[int, list[dict[str, Any]]] = {}
    for item in dialogue_summary.get("tool_audit_index", []):
        try:
            turn = int(item.get("turn"))
        except (TypeError, ValueError):
            continue
        tool_by_turn.setdefault(turn, []).append(item)

    steps: list[dict[str, Any]] = []
    total_stdout_chars = 0
    total_stderr_chars = 0
    total_assistant_chars = 0
    total_event_count = 0
    total_tool_events = 0
    session_token_totals = {"total": 0, "input": 0, "output": 0, "reasoning": 0}
    for turn in turns:
        turn_no = int(turn["turn"])
        stdout = str(turn.get("stdout") or "")
        stderr = str(turn.get("stderr") or "")
        assistant_texts = [
            str(item.get("text") or "")
            for item in visible_by_turn.get(turn_no, [])
            if item.get("role") == "assistant"
        ]
        event_count = sum(1 for line in stdout.splitlines() if line.strip().startswith("{"))
        tool_events = len(tool_by_turn.get(turn_no, []))
        token_usages = token_usage_events(stdout)
        token_totals = sum_token_usages(token_usages)
        for key in session_token_totals:
            session_token_totals[key] += token_totals[key]
        assistant_chars = sum(len(text) for text in assistant_texts)
        stdout_chars = len(stdout)
        stderr_chars = len(stderr)
        total_stdout_chars += stdout_chars
        total_stderr_chars += stderr_chars
        total_assistant_chars += assistant_chars
        total_event_count += event_count
        total_tool_events += tool_events
        steps.append(
            {
                "turn": turn_no,
                "prompt": turn["prompt"],
                "model_dependent": True,
                "client": client,
                "session_id": session_id,
                "raw_artifact": turn.get("path"),
                "returncode": turn.get("returncode"),
                "timeout": bool(turn.get("timeout")),
                "stdout_chars": stdout_chars,
                "stderr_chars": stderr_chars,
                "assistant_visible_generation_count": len(assistant_texts),
                "assistant_visible_chars": assistant_chars,
                "json_event_count": event_count,
                "tool_event_count": tool_events,
                "token_usage_events": token_usages,
                "token_totals": token_totals,
                "deterministic_evaluation": "not_semantic; counts and structured facts only",
            }
        )
    return {
        "model_dependent": True,
        "client": client,
        "session_id": session_id,
        "step_generations": steps,
        "totals": {
            "prompt_count": len(turns),
            "generation_step_count": len(steps),
            "assistant_visible_generation_count": sum(
                int(step["assistant_visible_generation_count"]) for step in steps
            ),
            "assistant_visible_chars": total_assistant_chars,
            "stdout_chars": total_stdout_chars,
            "stderr_chars": total_stderr_chars,
            "json_event_count": total_event_count,
            "tool_event_count": total_tool_events,
            "token_totals": session_token_totals,
        },
        "evaluation_requirement": (
            "Agent evaluator must score each step generation and the total session. "
            "These counts are reported evidence, not semantic pass/fail."
        ),
    }


def token_usage_events(stdout: str) -> list[dict[str, Any]]:
    usages: list[dict[str, Any]] = []
    for line in stdout.splitlines():
        if not line.strip().startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "event_msg" and isinstance(event.get("payload"), dict):
            payload = event["payload"]
            if payload.get("type") == "token_count" and isinstance(payload.get("info"), dict):
                usage = payload["info"].get("last_token_usage")
                if isinstance(usage, dict):
                    usages.append(
                        {
                            "total": int(usage.get("total_tokens") or 0),
                            "input": int(usage.get("input_tokens") or 0),
                            "output": int(usage.get("output_tokens") or 0),
                            "reasoning": int(usage.get("reasoning_output_tokens") or 0),
                        }
                    )
        if event.get("type") == "step_finish" and isinstance(event.get("part"), dict):
            tokens = event["part"].get("tokens")
            if isinstance(tokens, dict):
                usages.append(tokens)
    return usages


def sum_token_usages(usages: list[dict[str, Any]]) -> dict[str, int]:
    totals = {"total": 0, "input": 0, "output": 0, "reasoning": 0}
    for usage in usages:
        for key in totals:
            value = usage.get(key)
            if isinstance(value, int):
                totals[key] += value
    return totals


def render_package_markdown(package: dict[str, Any]) -> str:
    lines = [
        f"# Evaluation Package: {package['client']} Use Case 1",
        "",
        f"Session ID: `{package['session_id']}`",
        f"Container: `{package['container']}`",
            f"Deterministic verifier status: `{package['deterministic_verifier_status']}`",
            f"Deterministic verifier scope: `{package['deterministic_verifier_scope']}`",
            f"Semantic score status: `{package['semantic_score_status']}`",
            f"Acceptance status: `{package['acceptance_status']}`",
            "",
            "## Deterministic Boundary",
            "",
            package["deterministic_boundary"],
            "",
            "## Interaction Principle",
        "",
        package["interaction_principle"],
        "",
        "## Methodology",
        "",
        f"Reference: `{package['methodology']['method_reference']}`",
        "",
        "Stable principles:",
    ]
    for principle in package["methodology"]["stable_principles"]:
        lines.append(f"- {principle}")
    lines.extend(
        [
            "",
            "## Use-Case Localization",
            "",
            f"Use case: `{package['use_case_localization']['id']}` - {package['use_case_localization']['name']}",
            f"Selected service: `{package['use_case_localization']['selected_service']}`",
            f"Prompt sequence: `{', '.join(package['use_case_localization']['prompt_sequence'])}`",
            "",
            "Expected visible story:",
        ]
    )
    for item in package["use_case_localization"]["expected_visible_story"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "Case-unique forbidden shortcuts:",
        ]
    )
    for item in package["use_case_localization"]["case_unique_forbidden_shortcuts"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
        "## Step Criteria",
        "",
        ]
    )
    lines.extend(["", "## Generation Report", "", "```json", json.dumps(package["generation_report"], indent=2, sort_keys=True), "```", ""])
    for step in package["step_criteria"]:
        lines.extend(
            [
                f"### {step['id']} ({step['points']} pts)",
                "",
                f"Expected: {step['expected']}",
            ]
        )
        if step.get("prompt_text"):
            lines.append(f"Prompt text: `{step['prompt_text']}`")
        if step.get("expected_user_facing_reply"):
            lines.append(f"User-facing reply: {step['expected_user_facing_reply']}")
        if step.get("tool_evidence"):
            lines.append(f"Tool evidence: {step['tool_evidence']}")
        if step.get("required_observations"):
            lines.append("Required observations: " + "; ".join(step["required_observations"]))
        if step.get("evidence"):
            lines.append("Evidence: " + "; ".join(step["evidence"]))
        if step.get("fail_if"):
            lines.append("Fail if: " + "; ".join(step["fail_if"]))
        lines.append("")
    lines.extend(
        [
            "## Scoring",
            "",
            f"Max points: {package['scoring']['max_points']}",
            f"Pass threshold: {package['scoring']['pass_threshold']}",
            f"Score policy: {package['scoring']['score_policy']}",
            "",
            "Manual score sheet status: not scored by runner",
            "",
            "Fatal failures:",
        ]
    )
    for failure in package["scoring"]["fatal_failures"]:
        lines.append(f"- {failure}")
    lines.extend(
        [
            "",
            "## Required Pre-Submission Narrative",
            "",
            package["required_pre_submission_narrative"]["purpose"],
            "",
            "Instructions:",
        ]
    )
    for instruction in package["required_pre_submission_narrative"]["instructions"]:
        lines.append(f"- {instruction}")
    lines.extend(["", "Template:"])
    for item in package["required_pre_submission_narrative"]["template"]:
        lines.append(f"- {item}")
    lines.extend(render_dialogue_summary_markdown(package["derived_review_surfaces"]))
    lines.extend(
        [
            "",
            "## Artifacts",
            "",
            f"- Combined evidence: `{package['artifacts']['combined_evidence']}`",
            f"- Verifier JSON: `{package['artifacts']['verifier_json']}`",
        ]
    )
    for path in package["artifacts"]["raw_turn_outputs"]:
        lines.append(f"- Raw turn output: `{path}`")
    return "\n".join(lines) + "\n"


def summarize_dialogue(turns: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {"visible_dialogue": [], "hidden_or_extension_messages": [], "tool_audit_index": []}

    def add_visible(turn_no: int, role: str, text: str) -> None:
        normalized = redact_text(text).strip()
        if not normalized:
            return
        item = {"turn": turn_no, "role": role, "text": normalized}
        if item in summary["visible_dialogue"]:
            return
        summary["visible_dialogue"].append(item)

    for turn in turns:
        turn_no = turn["turn"]
        prompt = turn["prompt"]
        add_visible(turn_no, "user", prompt)
        stdout = str(turn.get("stdout") or "")
        for line in stdout.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") == "item.completed" and isinstance(event.get("item"), dict):
                item = event["item"]
                item_type = item.get("type")
                if item_type == "agent_message":
                    add_visible(turn_no, "assistant", str(item.get("text") or ""))
                elif item_type == "mcp_tool_call":
                    summary["tool_audit_index"].append(
                        {
                            "turn": turn_no,
                            "tool": f"{item.get('server')}/{item.get('tool')}",
                            "event": "mcp_tool_call",
                            "status": item.get("status"),
                            "is_error": bool(item.get("error")),
                        }
                    )
            if event.get("type") == "text" and isinstance(event.get("part"), dict):
                text = str(event["part"].get("text") or "")
                add_visible(turn_no, "assistant", text)
            elif event.get("type") == "tool_use" and isinstance(event.get("part"), dict):
                part = event["part"]
                summary["tool_audit_index"].append(
                    {
                        "turn": turn_no,
                        "tool": part.get("tool"),
                        "event": "tool_use",
                        "status": ((part.get("state") or {}) if isinstance(part.get("state"), dict) else {}).get("status"),
                    }
                )
            elif event.get("type") == "tool_execution_start":
                summary["tool_audit_index"].append(
                    {"turn": turn_no, "tool": event.get("toolName"), "event": "tool_execution_start"}
                )
            elif event.get("type") == "tool_execution_end":
                summary["tool_audit_index"].append(
                    {"turn": turn_no, "tool": event.get("toolName"), "event": "tool_execution_end", "is_error": event.get("isError")}
                )
            elif event.get("type") == "message_end" and isinstance(event.get("message"), dict):
                message = event["message"]
                role = message.get("role")
                content = message.get("content")
                if role == "custom":
                    summary["hidden_or_extension_messages"].append(
                        {
                            "turn": turn_no,
                            "custom_type": message.get("customType"),
                            "display": message.get("display"),
                            "text_excerpt": redact_text(str(message.get("content") or ""))[:500],
                        }
                    )
                elif role in {"assistant", "user"} and isinstance(content, list):
                    texts = [str(part.get("text") or "") for part in content if isinstance(part, dict) and part.get("type") == "text"]
                    for text in texts:
                        add_visible(turn_no, str(role), text)
                    for part in content:
                        if isinstance(part, dict) and part.get("type") == "toolCall":
                            summary["tool_audit_index"].append(
                                {"turn": turn_no, "tool": part.get("name"), "event": "tool_call", "id": part.get("id")}
                            )
    return summary


def render_dialogue_summary_markdown(summary: dict[str, Any]) -> list[str]:
    lines = ["", "## Visible Dialogue", ""]
    for item in summary.get("visible_dialogue", []):
        lines.append(f"- Turn {item.get('turn')} {item.get('role')}: {str(item.get('text') or '').strip()}")
    lines.extend(["", "## Hidden/Extension Messages", ""])
    hidden = summary.get("hidden_or_extension_messages", [])
    if hidden:
        for item in hidden:
            lines.append(
                f"- Turn {item.get('turn')} {item.get('custom_type') or 'hidden'} display={item.get('display')}: "
                f"{str(item.get('text_excerpt') or '').strip()}"
            )
    else:
        lines.append("- None observed in parsed events.")
    lines.extend(["", "## Tool Audit Index", ""])
    tools = summary.get("tool_audit_index", [])
    if tools:
        for item in tools:
            suffix = f" status={item.get('status')}" if item.get("status") else ""
            lines.append(f"- Tool: {item.get('tool')} turn={item.get('turn')} event={item.get('event')}{suffix}")
    else:
        lines.append("- None observed in parsed events.")
    return lines


if __name__ == "__main__":
    raise SystemExit(main())
