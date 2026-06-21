#!/usr/bin/env python3
"""Run Use Case 8 same-session tool follow-up through a real client CLI."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from harness_redaction import redact_text, redact_value


FIRST_PROMPT = "look up the docs entry for opencode and tell me which result is best"
FOLLOWUP_PROMPT = "using that result, what should I read about configuration?"


def load_runner(name: str) -> Any:
    path = Path(__file__).with_name(f"run-use-case-{name}-dialogue.py")
    spec = importlib.util.spec_from_file_location(f"use_case_{name}_runner", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client", choices=["pi", "opencode", "codex"], required=True)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--no-build", action="store_true")
    args = parser.parse_args(argv)
    if args.timeout < 90:
        raise SystemExit("--timeout must be at least 90 seconds for Use Case 8 dialogue evaluation")

    uc1 = load_runner("1")
    uc3 = load_runner("3")
    repo_root = Path(__file__).resolve().parents[3]
    harness_root = repo_root / "docker" / "client-harness"
    lock_file = uc3.acquire_harness_lock(harness_root)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_root = harness_root / "evidence" / "use-case-8" / args.client
    output_root.mkdir(parents=True, exist_ok=True)
    setup_container = f"cf-uc8-{args.client}-setup-{timestamp.lower().replace('z', '')}"
    container = f"cf-uc8-{args.client}-runner-{timestamp.lower().replace('z', '')}"
    session_id = "" if args.client == "codex" else f"uc8-{args.client}-{timestamp}"
    commands: list[dict[str, Any]] = []

    reset = uc3.run(
        [
            sys.executable,
            str(harness_root / "scripts" / "reset-client-harness-state.py"),
            "--client",
            uc3.reset_client_name(args.client),
            "--reset-home-volume",
            "--evidence-dir",
            "docker/client-harness/evidence/use-case-8/prior",
        ],
        cwd=repo_root,
        timeout=120,
        commands=commands,
    )
    reset_json = uc3.parse_json_or_text(reset["stdout"])

    uc3.ensure_semantic_model_env(harness_root, client=args.client, commands=commands, runner=uc3.run)
    if not args.no_build:
        uc3.run(["docker", "compose", "-f", str(harness_root / "compose.yml"), "build", "base", uc3.build_service_name(args.client)], cwd=repo_root, timeout=600, commands=commands)

    launch_env_args = uc3.codex_empty_api_key_env_args() if args.client == "codex" else []
    uc3.run(["docker", "compose", "-f", str(harness_root / "compose.yml"), "run", *launch_env_args, "--name", setup_container, "--no-deps", "-d", uc3.compose_service_name(args.client), "sleep", "infinity"], cwd=repo_root, timeout=120, commands=commands)
    setup = uc3.run(["docker", "exec", setup_container, "bash", "-lc", uc3.initialized_fixture_command(args.client)], cwd=repo_root, timeout=180, commands=commands)
    uc3.run(["docker", "rm", "-f", setup_container], cwd=repo_root, timeout=60, commands=commands)
    uc3.reset_home_only(args.client, repo_root, commands)

    launch = uc3.run(["docker", "compose", "-f", str(harness_root / "compose.yml"), "run", *launch_env_args, "--name", container, "--no-deps", "-d", uc3.compose_service_name(args.client), "sleep", "infinity"], cwd=repo_root, timeout=120, commands=commands)
    runtime = uc3.run(["docker", "exec", container, "bash", "-lc", uc1.runtime_readback_command(args.client)], cwd=repo_root, timeout=120, commands=commands)
    fixture = uc3.run(["docker", "exec", container, "bash", "-lc", uc3.fixture_readback_command(args.client)], cwd=repo_root, timeout=120, commands=commands)

    turns: list[dict[str, Any]] = []
    first_cmd = uc1.target_client_command(args.client, session_id, FIRST_PROMPT, create_session=args.client == "opencode")
    first = uc3.run(["docker", "exec", container, "bash", "-lc", first_cmd], cwd=repo_root, timeout=args.timeout, commands=commands)
    if args.client == "opencode":
        discovered = uc1.extract_opencode_session_id(str(first.get("stdout") or ""))
        if discovered:
            session_id = discovered
    if args.client == "codex":
        discovered = uc1.extract_codex_session_id(str(first.get("stdout") or ""))
        if discovered:
            session_id = discovered
    first_path = output_root / f"{args.client}-turn1-{timestamp}.raw.txt"
    first_path.write_text(uc1.render_command_block(first), encoding="utf-8")
    turns.append({"turn": 1, "client": args.client, "prompt": FIRST_PROMPT, "path": str(first_path), **first})

    followup_cmd = uc1.target_client_command(args.client, session_id, FOLLOWUP_PROMPT, create_session=False)
    followup = uc3.run(["docker", "exec", container, "bash", "-lc", followup_cmd], cwd=repo_root, timeout=args.timeout, commands=commands)
    followup_path = output_root / f"{args.client}-turn2-{timestamp}.raw.txt"
    followup_path.write_text(uc1.render_command_block(followup), encoding="utf-8")
    turns.append({"turn": 2, "client": args.client, "prompt": FOLLOWUP_PROMPT, "path": str(followup_path), **followup})

    dialogue_summary = uc1.summarize_dialogue(turns)
    generation_report = uc1.build_generation_report(
        client=args.client,
        session_id=session_id,
        turns=turns,
        dialogue_summary=dialogue_summary,
    )

    combined_path = output_root / f"{args.client}-use-case-8-evidence-{timestamp}.md"
    combined_path.write_text(
        render_combined(
            client=args.client,
            timestamp=timestamp,
            session_id=session_id,
            container=container,
            commands=commands,
            reset_json=reset_json,
            setup=setup,
            runtime=runtime,
            fixture=fixture,
            turns=turns,
            dialogue_summary=dialogue_summary,
            generation_report=generation_report,
        ),
        encoding="utf-8",
    )
    metadata = build_metadata(
        uc3=uc3,
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
        turns=turns,
    )
    metadata_path = output_root / f"{args.client}-metadata-{timestamp}.json"
    metadata_path.write_text(json.dumps(redact_value(metadata), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    verifier = uc3.run(
        [
            sys.executable,
            str(harness_root / "scripts" / "verify-use-case-8-e2e-evidence.py"),
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
    verifier_json = uc3.parse_json_or_text(verifier["stdout"])
    verifier_path = output_root / f"{args.client}-verifier-{timestamp}.json"
    verifier_path.write_text(json.dumps(redact_value(verifier_json), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    package_path = output_root / f"{args.client}-evaluation-package-{timestamp}.md"
    package_path.write_text(render_package(args.client, combined_path, verifier_path, verifier_json, generation_report, dialogue_summary), encoding="utf-8")

    turn_failures = [
        {"turn": turn["turn"], "prompt": turn["prompt"], "returncode": turn["returncode"], "timeout": turn["timeout"]}
        for turn in turns
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
        "evaluation_package_markdown": str(package_path),
        "verifier": str(verifier_path),
        "verifier_failures": verifier_json.get("failures") if isinstance(verifier_json, dict) else None,
        "turn_failures": turn_failures,
        "generation_report": generation_report,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    lock_file.close()
    return 0 if summary["ok"] else 1


def command_status(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "returncode": result.get("returncode"),
        "timeout": bool(result.get("timeout")),
    }


def build_metadata(
    *,
    uc3: Any,
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
    turns: list[dict[str, Any]],
) -> dict[str, Any]:
    required_statuses = {
        "setup": command_status(setup),
        "launch": command_status(launch),
        "runtime": command_status(runtime),
        "fixture": command_status(fixture),
    }
    for turn in turns:
        required_statuses[f"turn_{turn['turn']}"] = command_status(turn)
    return {
        "use_case": "use-case-8",
        "client": client,
        "session_id": session_id,
        "container": container,
        "semantic_acceptance": "requires_agent_evaluation",
        "runner_contract": {
            "non_ephemeral_container": True,
            "reset_home_volume_requested": True,
            "virgin_workspace_reset_requested": True,
            "deterministic_checks_are_structural_only": True,
            "same_session_required": True,
            "reset_client": uc3.reset_client_name(client),
            "compose_service": uc3.compose_service_name(client),
        },
        "reset_json": reset_json,
        "generation_report": generation_report,
        "commands": commands,
        "required_command_statuses": required_statuses,
        "semantic_criteria": [
            "clean_initialized_tool_fixture",
            "non_ephemeral_same_session",
            "natural_tool_and_followup_prompts",
            "first_turn_uses_contextforge_tool",
            "followup_uses_prior_result",
            "coherent_user_facing_workflow",
            "readiness_and_non_actions",
        ],
    }


def render_combined(
    *,
    client: str,
    timestamp: str,
    session_id: str,
    container: str,
    commands: list[dict[str, Any]],
    reset_json: Any,
    setup: dict[str, Any],
    runtime: dict[str, Any],
    fixture: dict[str, Any],
    turns: list[dict[str, Any]],
    dialogue_summary: dict[str, Any],
    generation_report: dict[str, Any],
) -> str:
    lines = [
        f"# Use Case 8 Evidence: {client}",
        "",
        f"Timestamp: `{timestamp}`",
        f"Session ID: `{session_id}`",
        f"Container: `{container}`",
        "",
        "## Prompts",
        "",
    ]
    for turn in turns:
        lines.append(f"{turn['turn']}. `{turn['prompt']}`")
    lines.extend(
        [
            "",
            "## Deterministic Boundary",
            "",
            "This evidence captures structure, commands, transcripts, session identity, and tool-call indexes. It does not score generated prose.",
            "",
            "## Command Ledger",
            "",
            "```json",
            json.dumps(redact_value(commands), indent=2, sort_keys=True),
            "```",
            "",
            "## Reset JSON",
            "",
            "```json",
            json.dumps(redact_value(reset_json), indent=2, sort_keys=True),
            "```",
            "",
            "## Setup Command",
            "",
            "```text",
            render_command_block(setup),
            "```",
            "",
            "## Runtime Readback",
            "",
            "```text",
            render_command_block(runtime),
            "```",
            "",
            "## Fixture Readback",
            "",
            "```text",
            render_command_block(fixture),
            "```",
            "",
            "## Dialogue Summary",
            "",
            "```json",
            json.dumps(redact_value(dialogue_summary), indent=2, sort_keys=True),
            "```",
            "",
            "## Generation Report",
            "",
            "```json",
            json.dumps(redact_value(generation_report), indent=2, sort_keys=True),
            "```",
            "",
        ]
    )
    for turn in turns:
        lines.extend(
            [
                f"## Turn {turn['turn']} Raw Output",
                "",
                "```text",
                render_command_block(turn),
                "```",
                "",
            ]
        )
    return "\n".join(lines)


def render_package(
    client: str,
    combined_path: Path,
    verifier_path: Path,
    verifier_json: Any,
    generation_report: dict[str, Any],
    dialogue_summary: dict[str, Any],
) -> str:
    lines = [
        f"# Evaluation Package: {client} Use Case 8",
        "",
        "## Artifacts",
        "",
        f"- Combined evidence: `{combined_path}`",
        f"- Verifier JSON: `{verifier_path}`",
        "",
        "## Deterministic Verifier",
        "",
        "```json",
        json.dumps(redact_value(verifier_json), indent=2, sort_keys=True),
        "```",
        "",
        "## Generation Report",
        "",
        "```json",
        json.dumps(redact_value(generation_report), indent=2, sort_keys=True),
        "```",
        "",
        "## Dialogue Summary",
        "",
        "```json",
        json.dumps(redact_value(dialogue_summary), indent=2, sort_keys=True),
        "```",
        "",
        "## Evaluator Instructions",
        "",
        "Score the visible dialogue and supporting tool traces against `docs/use-cases/use-case-8/package.md`.",
        "Treat deterministic checks as structural evidence only.",
        "Decide whether the first turn actually uses the ContextForge docs capability and whether the second turn remains in the same session and relies on the previous result.",
        "Classify failures as package, runner, verifier, tested-client, implementation, environment, or inconclusive.",
        "Provide a step-by-step narrative with evidence references before giving a pass/fail recommendation.",
        "",
    ]
    return "\n".join(lines)


def render_command_block(result: dict[str, Any]) -> str:
    return load_runner("1").render_command_block(result)


if __name__ == "__main__":
    raise SystemExit(main())
