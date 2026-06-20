#!/usr/bin/env python3
"""Run Use Case 7 through a real client CLI and package evaluation evidence."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROMPT = "what ContextForge state are you using right now?"


def load_uc3_module() -> Any:
    path = Path(__file__).with_name("run-use-case-3-dialogue.py")
    spec = importlib.util.spec_from_file_location("use_case_3_runner", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client", choices=["pi", "opencode"], required=True)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--no-build", action="store_true")
    args = parser.parse_args(argv)
    if args.timeout < 90:
        raise SystemExit("--timeout must be at least 90 seconds for Use Case 7 dialogue evaluation")

    uc3 = load_uc3_module()
    repo_root = Path(__file__).resolve().parents[3]
    harness_root = repo_root / "docker" / "client-harness"
    lock_file = uc3.acquire_harness_lock(harness_root)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_root = harness_root / "evidence" / "use-case-7" / args.client
    output_root.mkdir(parents=True, exist_ok=True)
    setup_container = f"cf-uc7-{args.client}-setup-{timestamp.lower().replace('z', '')}"
    container = f"cf-uc7-{args.client}-runner-{timestamp.lower().replace('z', '')}"
    session_id = f"uc7-{args.client}-{timestamp}" if args.client == "pi" else ""
    commands: list[dict[str, Any]] = []

    reset = uc3.run(
        [
            sys.executable,
            str(harness_root / "scripts" / "reset-client-harness-state.py"),
            "--client",
            args.client,
            "--reset-home-volume",
            "--evidence-dir",
            "docker/client-harness/evidence/use-case-7/prior",
        ],
        cwd=repo_root,
        timeout=120,
        commands=commands,
    )
    reset_json = uc3.parse_json_or_text(reset["stdout"])

    if not (harness_root / "env" / "local-llama.env").exists():
        uc3.run([str(harness_root / "scripts" / "make-local-llama-env.sh")], cwd=harness_root, timeout=60, commands=commands)
    if not args.no_build:
        uc3.run(["docker", "compose", "-f", str(harness_root / "compose.yml"), "build", "base", args.client], cwd=repo_root, timeout=600, commands=commands)

    uc3.run(["docker", "compose", "-f", str(harness_root / "compose.yml"), "run", "--name", setup_container, "--no-deps", "-d", args.client, "sleep", "infinity"], cwd=repo_root, timeout=120, commands=commands)
    setup = uc3.run(["docker", "exec", setup_container, "bash", "-lc", uc3.initialized_fixture_command(args.client)], cwd=repo_root, timeout=180, commands=commands)
    uc3.run(["docker", "rm", "-f", setup_container], cwd=repo_root, timeout=60, commands=commands)
    uc3.reset_home_only(args.client, repo_root, commands)

    launch = uc3.run(["docker", "compose", "-f", str(harness_root / "compose.yml"), "run", "--name", container, "--no-deps", "-d", args.client, "sleep", "infinity"], cwd=repo_root, timeout=120, commands=commands)
    runtime = uc3.run(["docker", "exec", container, "bash", "-lc", uc3.runtime_readback_command(args.client)], cwd=repo_root, timeout=120, commands=commands)
    fixture = uc3.run(["docker", "exec", container, "bash", "-lc", uc3.fixture_readback_command(args.client)], cwd=repo_root, timeout=120, commands=commands)
    turn = uc3.run(["docker", "exec", container, "bash", "-lc", uc3.target_client_command(args.client, session_id, PROMPT)], cwd=repo_root, timeout=args.timeout, commands=commands)
    if args.client == "opencode":
        session_id = uc3.extract_opencode_session_id(turn.get("stdout") or "")
    generation_report = uc3.build_generation_report(client=args.client, session_id=session_id, prompt=PROMPT, turn=turn)

    combined_path = output_root / f"{args.client}-use-case-7-evidence-{timestamp}.md"
    combined_path.write_text(render_combined(uc3, args.client, timestamp, session_id, container, commands, reset_json, setup, runtime, fixture, turn, generation_report), encoding="utf-8")
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
    verifier = uc3.run(
        [
            sys.executable,
            str(harness_root / "scripts" / "verify-use-case-7-e2e-evidence.py"),
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


def render_combined(
    uc3: Any,
    client: str,
    timestamp: str,
    session_id: str,
    container: str,
    commands: list[dict[str, Any]],
    reset_json: Any,
    setup: dict[str, Any],
    runtime: dict[str, Any],
    fixture: dict[str, Any],
    turn: dict[str, Any],
    generation_report: dict[str, Any],
) -> str:
    lines = [
        f"# Use Case 7 {client} Dialogue Evidence",
        "",
        f"Timestamp: {timestamp}",
        f"Client: {client}",
        f"Session ID: {session_id}",
        f"Container: {container}",
        f"Prompt: `{PROMPT}`",
        "",
        "## Command Ledger",
        "",
    ]
    for item in commands:
        lines.append(f"- `{item['command_text']}` -> rc={item['returncode']} timeout={item['timeout']}")
    lines.extend(["", "## Generation Report", "```json", json.dumps(generation_report, indent=2, sort_keys=True), "```", ""])
    lines.extend(["", "## Reset Readback", "```json", json.dumps(reset_json, indent=2, sort_keys=True), "```", ""])
    for label, value in (("setup", setup), ("runtime", runtime), ("fixture", fixture), ("turn", turn)):
        lines.extend([f"## {label.title()} Output", "```text", uc3.command_block(value), "```", ""])
    return "\n".join(lines)


def render_package(client: str, combined_path: Path, verifier_path: Path, verifier_json: Any, generation_report: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# Evaluation Package: {client} Use Case 7",
            "",
            "Use case: Ask what ContextForge state the client is using right now.",
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
            "Required narrative: setup, initialized fixture, prompt, visible state readback, selected services, imported tools, skipped services, bounded errors, readiness-layer honesty, non-actions, score, verdict.",
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
        "use_case": "use-case-7",
        "client": client,
        "session_id": session_id,
        "container": container,
        "semantic_acceptance": "requires_agent_evaluation",
        "runner_contract": {
            "non_ephemeral_container": True,
            "reset_home_volume_requested": True,
            "virgin_workspace_reset_requested": True,
            "deterministic_checks_are_structural_only": True,
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
            "project_state_readback_honesty",
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
