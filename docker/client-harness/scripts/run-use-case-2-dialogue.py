#!/usr/bin/env python3
"""Run Use Case 2 through a real client CLI and package evaluation evidence."""

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


PROMPT = "what ContextForge tools are available?"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client", choices=["pi", "opencode", "codex"], required=True)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--no-build", action="store_true")
    args = parser.parse_args(argv)
    if args.timeout < 90:
        raise SystemExit("--timeout must be at least 90 seconds for Use Case 2 dialogue evaluation")

    repo_root = Path(__file__).resolve().parents[3]
    harness_root = repo_root / "docker" / "client-harness"
    lock_file = acquire_harness_lock(harness_root)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_root = harness_root / "evidence" / "use-case-2" / args.client
    output_root.mkdir(parents=True, exist_ok=True)
    setup_container = f"cf-uc2-{args.client}-setup-{timestamp.lower().replace('z', '')}"
    container = f"cf-uc2-{args.client}-runner-{timestamp.lower().replace('z', '')}"
    session_id = default_session_id(args.client, timestamp)
    commands: list[dict[str, Any]] = []

    reset = run(
        [
            sys.executable,
            str(harness_root / "scripts" / "reset-client-harness-state.py"),
            "--client",
            reset_client_name(args.client),
            "--reset-home-volume",
            "--evidence-dir",
            "docker/client-harness/evidence/use-case-2/prior",
        ],
        cwd=repo_root,
        timeout=120,
        commands=commands,
    )
    reset_json = parse_json_or_text(reset["stdout"])

    if args.client != "codex" and not (harness_root / "env" / "local-llama.env").exists():
        run([str(harness_root / "scripts" / "make-local-llama-env.sh")], cwd=harness_root, timeout=60, commands=commands)
    if not args.no_build:
        run(["docker", "compose", "-f", str(harness_root / "compose.yml"), "build", "base", build_service_name(args.client)], cwd=repo_root, timeout=600, commands=commands)

    launch_env_args = codex_empty_api_key_env_args() if args.client == "codex" else []
    run(
        [
            "docker",
            "compose",
            "-f",
            str(harness_root / "compose.yml"),
            "run",
            *launch_env_args,
            "--name",
            setup_container,
            "--no-deps",
            "-d",
            compose_service_name(args.client),
            "sleep",
            "infinity",
        ],
        cwd=repo_root,
        timeout=120,
        commands=commands,
    )
    setup = run(["docker", "exec", setup_container, "bash", "-lc", initialized_fixture_command(args.client)], cwd=repo_root, timeout=180, commands=commands)
    run(["docker", "rm", "-f", setup_container], cwd=repo_root, timeout=60, commands=commands)
    reset_home_only(args.client, repo_root, commands)

    launch = run(
        [
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
        ],
        cwd=repo_root,
        timeout=120,
        commands=commands,
    )
    runtime = run(["docker", "exec", container, "bash", "-lc", runtime_readback_command(args.client)], cwd=repo_root, timeout=120, commands=commands)
    fixture = run(["docker", "exec", container, "bash", "-lc", fixture_readback_command(args.client)], cwd=repo_root, timeout=120, commands=commands)
    prompt_cmd = target_client_command(args.client, session_id, PROMPT)
    turn = run(["docker", "exec", container, "bash", "-lc", prompt_cmd], cwd=repo_root, timeout=args.timeout, commands=commands)
    if args.client == "opencode":
        session_id = extract_opencode_session_id(turn.get("stdout") or "")
    if args.client == "codex":
        session_id = extract_codex_session_id(turn.get("stdout") or "")
    generation_report = build_generation_report(
        client=args.client,
        session_id=session_id,
        prompt=PROMPT,
        turn=turn,
    )

    combined_path = output_root / f"{args.client}-use-case-2-evidence-{timestamp}.md"
    combined_text = render_combined(
        client=args.client,
        timestamp=timestamp,
        session_id=session_id,
        container=container,
        commands=commands,
        reset_json=reset_json,
        setup=setup,
        runtime=runtime,
        fixture=fixture,
        turn=turn,
        generation_report=generation_report,
    )
    combined_path.write_text(combined_text, encoding="utf-8")
    metadata_path = output_root / f"{args.client}-metadata-{timestamp}.json"
    metadata_path.write_text(
        json.dumps(
            build_structural_metadata(
                client=args.client,
                session_id=session_id,
                container=container,
                reset_json=reset_json,
                generation_report=generation_report,
                commands=commands,
                setup=setup,
                launch=launch,
                runtime=runtime,
                fixture=fixture,
                turn=turn,
            ),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    verifier = run(
        [
            sys.executable,
            str(harness_root / "scripts" / "verify-use-case-2-e2e-evidence.py"),
            "--client",
            args.client,
            "--evidence",
            str(combined_path),
            "--metadata",
            str(metadata_path),
            "--session-id",
            session_id,
        ],
        cwd=repo_root,
        timeout=120,
        commands=commands,
    )
    verifier_json = parse_json_or_text(verifier["stdout"])
    verifier_path = output_root / f"{args.client}-verifier-{timestamp}.json"
    verifier_path.write_text(json.dumps(verifier_json, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    package_path = output_root / f"{args.client}-evaluation-package-{timestamp}.md"
    package_path.write_text(render_package(args.client, combined_path, verifier_path, verifier_json, generation_report), encoding="utf-8")
    summary = {
        "ok": (
            bool(isinstance(verifier_json, dict) and verifier_json.get("ok"))
            and setup["returncode"] == 0
            and not setup["timeout"]
            and turn["returncode"] == 0
            and not turn["timeout"]
        ),
        "ok_scope": "harness package assembled; not semantic acceptance",
        "semantic_acceptance": "requires_agent_evaluation",
        "client": args.client,
        "session_id": session_id,
        "container": container,
        "combined_evidence": str(combined_path),
        "metadata": str(metadata_path),
        "evaluation_package_markdown": str(package_path),
        "verifier": str(verifier_path),
        "verifier_failures": verifier_json.get("failures") if isinstance(verifier_json, dict) else None,
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


def initialized_fixture_command(client: str) -> str:
    approval = "/home/agent/.local/state/contextforge-client-harness-runtime/project-init/uc2-approval.json"
    payload = json.dumps({"project_root": "/workspace", "client_type": client, "selected_services": ["context7:canonical"]})
    helper_python = helper_python_path(client)
    return " && ".join(
        [
            "cd /workspace",
            f"mkdir -p {shlex.quote(str(Path(approval).parent))}",
            f"printf '%s\\n' {shlex.quote(json.dumps({'cwd': '/workspace', 'text': 'approve'}))} > {shlex.quote(approval)}",
            "export XDG_RUNTIME_DIR=/home/agent/.local/state/contextforge-client-harness-runtime",
            f"export CONTEXTFORGE_HELPER_APPROVAL_SOURCE_PATH={shlex.quote(approval)}",
            "export CONTEXTFORGE_HELPER_REQUIRE_USER_APPROVAL_TEXT=1",
            f"{helper_python} /repo/scripts/pi_project_init_helper_cli.py --operation propose_project_init --payload-json {shlex.quote(payload)}",
            f"{helper_python} /repo/scripts/pi_project_init_helper_cli.py --operation cf_project_init_approve --payload-json {shlex.quote(json.dumps({'project_root': '/workspace', 'client_type': client}))}",
            f"{helper_python} /repo/scripts/pi_project_init_helper_cli.py --operation cf_project_init_apply --payload-json {shlex.quote(json.dumps({'project_root': '/workspace', 'client_type': client}))}",
        ]
    )


def helper_python_path(client: str) -> str:
    if client == "pi":
        return "/opt/contextforge-wrapper-venv/bin/python"
    return "/opt/contextforge-helper-venv/bin/python"


def default_session_id(client: str, timestamp: str) -> str:
    if client == "pi":
        return f"uc2-pi-{timestamp}"
    return ""


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


def reset_home_only(client: str, repo_root: Path, commands: list[dict[str, Any]]) -> None:
    if client == "codex":
        return
    volume = f"contextforge-client-harness_{client}-home"
    ids_result = run(["docker", "ps", "-aq", "--filter", f"volume={volume}"], cwd=repo_root, timeout=60, commands=commands)
    ids = [line.strip() for line in str(ids_result.get("stdout") or "").splitlines() if line.strip()]
    if ids:
        run(["docker", "rm", "-f", *ids], cwd=repo_root, timeout=60, commands=commands)
    run(["docker", "volume", "rm", volume], cwd=repo_root, timeout=60, commands=commands)


def runtime_readback_command(client: str) -> str:
    if client == "pi":
        version = "pi --version || true"
    elif client == "codex":
        version = "codex --version; codex login status; codex mcp list --json || true"
    else:
        version = "opencode --version || true"
    return f"pwd; whoami; hostname; {version}; ls -la /workspace"


def fixture_readback_command(client: str) -> str:
    if client == "opencode":
        return "pwd; sed -n '1,220p' /workspace/.project/context_forge_state.json; sed -n '1,120p' /workspace/opencode.json"
    if client == "codex":
        return "pwd; sed -n '1,220p' /workspace/.project/context_forge_state.json; sed -n '1,180p' /workspace/.codex/config.toml"
    return "pwd; sed -n '1,220p' /workspace/.project/context_forge_state.json"


def target_client_command(client: str, session_id: str, prompt: str) -> str:
    quoted = shlex.quote(prompt)
    if client == "pi":
        return f"cd /workspace && pi --provider local-llama-qwen --model qwen3.6-a3b --session-id {shlex.quote(session_id)} --mode json -p {quoted}"
    if client == "codex":
        codex_flags = "--json --dangerously-bypass-hook-trust --dangerously-bypass-approvals-and-sandbox --skip-git-repo-check"
        if session_id:
            return f"cd /workspace && codex exec resume {codex_flags} {shlex.quote(session_id)} {quoted} </dev/null"
        return f"cd /workspace && codex exec {codex_flags} {quoted} </dev/null"
    return 'cd /workspace && opencode run --dangerously-skip-permissions --model "llama.cpp/${LOCAL_LLAMA_MODEL:-qwen3.6-a3b}" --agent build --format json ' + quoted


def run(cmd: list[str], *, cwd: Path, timeout: int, commands: list[dict[str, Any]]) -> dict[str, Any]:
    command_text = " ".join(shlex.quote(part) for part in cmd)
    try:
        completed = subprocess.run(cmd, cwd=str(cwd), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, check=False)
        result = {"command_text": command_text, "cwd": str(cwd), "returncode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr, "timeout": False}
    except subprocess.TimeoutExpired as exc:
        result = {"command_text": command_text, "cwd": str(cwd), "returncode": 124, "stdout": coerce(exc.stdout), "stderr": coerce(exc.stderr), "timeout": True}
    commands.append({key: result[key] for key in ("command_text", "cwd", "returncode", "timeout")})
    return result


def coerce(value: str | bytes | None) -> str:
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


def extract_opencode_session_id(text: str) -> str:
    match = re.search(r'"sessionID"\s*:\s*"([^"]+)"', text)
    return match.group(1) if match else ""


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


def command_block(result: dict[str, Any]) -> str:
    return "\n".join([f"COMMAND: {result['command_text']}", f"CWD: {result['cwd']}", f"RETURNCODE: {result['returncode']}", f"TIMEOUT: {str(result['timeout']).lower()}", "", "STDOUT:", str(result.get("stdout") or ""), "", "STDERR:", str(result.get("stderr") or ""), ""])


def build_generation_report(*, client: str, session_id: str, prompt: str, turn: dict[str, Any]) -> dict[str, Any]:
    stdout = str(turn.get("stdout") or "")
    stderr = str(turn.get("stderr") or "")
    event_count = sum(1 for line in stdout.splitlines() if line.strip().startswith("{"))
    surfaces = extract_generation_surfaces(stdout)
    assistant_text_chars = surfaces["assistant_text_chars"]
    assistant_generation_count = surfaces["assistant_generation_count"]
    token_usages = surfaces["token_usages"]
    tool_event_count = surfaces["tool_event_count"]
    token_totals = sum_token_usages(token_usages)
    step = {
        "turn": 1,
        "prompt": prompt,
        "model_dependent": True,
        "client": client,
        "session_id": session_id,
        "returncode": turn.get("returncode"),
        "timeout": bool(turn.get("timeout")),
        "stdout_chars": len(stdout),
        "stderr_chars": len(stderr),
        "assistant_visible_generation_count": assistant_generation_count,
        "assistant_visible_chars": assistant_text_chars,
        "json_event_count": event_count,
        "tool_event_count": tool_event_count,
        "token_usage_events": token_usages,
        "token_totals": token_totals,
        "deterministic_evaluation": "not_semantic; counts and structured facts only",
    }
    return {
        "model_dependent": True,
        "client": client,
        "session_id": session_id,
        "step_generations": [step],
        "totals": {
            "prompt_count": 1,
            "generation_step_count": 1,
            "assistant_visible_generation_count": assistant_generation_count,
            "assistant_visible_chars": assistant_text_chars,
            "stdout_chars": len(stdout),
            "stderr_chars": len(stderr),
            "json_event_count": event_count,
            "tool_event_count": tool_event_count,
            "token_totals": token_totals,
        },
        "evaluation_requirement": (
            "Agent evaluator must score the step generation and total session. "
            "These counts are reported evidence, not semantic pass/fail."
        ),
    }


def extract_generation_surfaces(stdout: str) -> dict[str, Any]:
    assistant_text_chars = 0
    assistant_generation_count = 0
    tool_event_count = 0
    token_usages: list[dict[str, int]] = []
    seen_assistant_messages: set[str] = set()
    for line in stdout.splitlines():
        if not line.strip().startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        event_type = event.get("type")
        if event_type == "item.completed" and isinstance(event.get("item"), dict):
            item = event["item"]
            item_type = item.get("type")
            if item_type == "agent_message":
                text = str(item.get("text") or "")
                if text:
                    assistant_generation_count += 1
                    assistant_text_chars += len(text)
            elif item_type == "mcp_tool_call":
                tool_event_count += 1
        if event_type == "text" and isinstance(event.get("part"), dict):
            text = str(event["part"].get("text") or "")
            if text:
                assistant_generation_count += 1
                assistant_text_chars += len(text)
        if event_type == "tool_use":
            tool_event_count += 1
        if event_type in {"tool_execution_start", "tool_execution_end"}:
            tool_event_count += 1
        if event_type in {"message_end", "turn_end"} and isinstance(event.get("message"), dict):
            message = event["message"]
            if message.get("role") == "assistant":
                marker = assistant_message_marker(message)
                if marker not in seen_assistant_messages:
                    seen_assistant_messages.add(marker)
                    texts = assistant_message_texts(message)
                    text_len = sum(len(text) for text in texts)
                    if text_len:
                        assistant_generation_count += len(texts)
                        assistant_text_chars += text_len
                    usage = normalize_token_usage(message.get("usage"))
                    if usage:
                        token_usages.append(usage)
        if event_type == "event_msg" and isinstance(event.get("payload"), dict):
            payload = event["payload"]
            if payload.get("type") == "token_count" and isinstance(payload.get("info"), dict):
                usage = payload["info"].get("last_token_usage")
                if isinstance(usage, dict):
                    token_usages.append(
                        {
                            "total": int(usage.get("total_tokens") or 0),
                            "input": int(usage.get("input_tokens") or 0),
                            "output": int(usage.get("output_tokens") or 0),
                            "reasoning": int(usage.get("reasoning_output_tokens") or 0),
                        }
                    )
        if event_type == "step_finish" and isinstance(event.get("part"), dict):
            tokens = event["part"].get("tokens")
            if isinstance(tokens, dict):
                usage = normalize_token_usage(tokens)
                if usage:
                    token_usages.append(usage)
    return {
        "assistant_text_chars": assistant_text_chars,
        "assistant_generation_count": assistant_generation_count,
        "tool_event_count": tool_event_count,
        "token_usages": token_usages,
    }


def sum_token_usages(usages: list[dict[str, Any]]) -> dict[str, int]:
    totals = {"total": 0, "input": 0, "output": 0, "reasoning": 0}
    for usage in usages:
        for key in totals:
            value = usage.get(key)
            if isinstance(value, int):
                totals[key] += value
    return totals


def assistant_message_texts(message: dict[str, Any]) -> list[str]:
    content = message.get("content")
    if not isinstance(content, list):
        return []
    return [
        str(part.get("text") or "")
        for part in content
        if isinstance(part, dict) and part.get("type") == "text" and str(part.get("text") or "")
    ]


def assistant_message_marker(message: dict[str, Any]) -> str:
    response_id = message.get("responseId")
    if response_id:
        return f"response:{response_id}"
    content = message.get("content")
    try:
        return "content:" + json.dumps(content, sort_keys=True)
    except TypeError:
        return "content:" + str(content)


def normalize_token_usage(usage: Any) -> dict[str, int]:
    if not isinstance(usage, dict):
        return {}
    normalized = {"total": 0, "input": 0, "output": 0, "reasoning": 0}
    total = usage.get("total")
    if not isinstance(total, int):
        total = usage.get("totalTokens")
    if isinstance(total, int):
        normalized["total"] = total
    for key in ("input", "output", "reasoning"):
        value = usage.get(key)
        if isinstance(value, int):
            normalized[key] = value
    return normalized


def render_combined(**kwargs: Any) -> str:
    lines = [
        f"# Use Case 2 {kwargs['client']} Dialogue Evidence",
        "",
        f"Timestamp: {kwargs['timestamp']}",
        f"Client: {kwargs['client']}",
        f"Session ID: {kwargs['session_id']}",
        f"Container: {kwargs['container']}",
        f"Prompt: `{PROMPT}`",
        "",
        "## Command Ledger",
        "",
    ]
    for item in kwargs["commands"]:
        lines.append(f"- `{item['command_text']}` -> rc={item['returncode']} timeout={item['timeout']}")
    lines.extend(["", "## Generation Report", "```json", json.dumps(kwargs["generation_report"], indent=2, sort_keys=True), "```", ""])
    lines.extend(["", "## Reset Readback", "```json", json.dumps(kwargs["reset_json"], indent=2, sort_keys=True), "```", ""])
    for label in ("setup", "runtime", "fixture", "turn"):
        lines.extend([f"## {label.title()} Output", "```text", command_block(kwargs[label]), "```", ""])
    return "\n".join(lines)


def render_package(client: str, combined_path: Path, verifier_path: Path, verifier_json: Any, generation_report: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# Evaluation Package: {client} Use Case 2",
            "",
            "Use case: Resume an initialized project and report available ContextForge tools.",
            f"Combined evidence: `{combined_path}`",
            f"Verifier: `{verifier_path}`",
            f"Deterministic verifier ok: `{bool(isinstance(verifier_json, dict) and verifier_json.get('ok'))}`",
            "Deterministic verifier scope: `harness and structured-evidence support; not semantic acceptance`",
            "Acceptance status: `requires_agent_evaluator_scoring`",
            "",
            "## Deterministic Boundary",
            "",
            "The runner reports and structures model generations but does not semantically accept them. Deterministic checks may validate commands, artifacts, and declared structured outputs; free-form assistant behavior requires agent evaluator scoring.",
            "",
            "## Generation Report",
            "",
            "```json",
            json.dumps(generation_report, indent=2, sort_keys=True),
            "```",
            "",
            "Semantic evaluator must judge visible user-agent behavior first, then tool traces.",
            "Required narrative: setup, initialized fixture, prompt, visible tool report, non-actions, score, verdict.",
        ]
    )


def build_structural_metadata(
    *,
    client: str,
    session_id: str,
    container: str,
    reset_json: Any,
    generation_report: dict[str, Any],
    commands: list[dict[str, Any]],
    setup: dict[str, Any],
    launch: dict[str, Any],
    runtime: dict[str, Any],
    fixture: dict[str, Any],
    turn: dict[str, Any],
) -> dict[str, Any]:
    return {
        "use_case": "use-case-2",
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
        "reset_json": reset_json,
        "generation_report": generation_report,
        "commands": commands,
        "required_command_statuses": {
            "setup": command_status(setup),
            "launch": command_status(launch),
            "runtime": command_status(runtime),
            "fixture": command_status(fixture),
            "turn": command_status(turn),
        },
        "semantic_criteria": [
            "natural_user_prompts",
            "initialized_tool_availability",
            "hidden_instruction_boundary",
            "non_actions",
        ],
    }


def command_status(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "returncode": result.get("returncode"),
        "timeout": bool(result.get("timeout")),
    }


if __name__ == "__main__":
    raise SystemExit(main())
