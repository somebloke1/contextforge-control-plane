#!/usr/bin/env python3
"""Run Use Case 5 selection-shape dialogue through a real client CLI."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SHAPES: dict[str, dict[str, Any]] = {
    "single": {
        "title": "single-service selection",
        "prompts": ["hello", "context7", "approve"],
        "selected_services": ["context7:canonical"],
        "expected_story": [
            "The assistant presents the ContextForge service list.",
            "The user selects context7 using ordinary language.",
            "The assistant presents a clear project-local plan and asks for approval.",
            "The user approves.",
            "The assistant applies the project-local package, reports success, and states reload/new-session requirements.",
        ],
    },
    "curated": {
        "title": "curated multi-service selection",
        "prompts": ["hello", "context7, mentality, and ssh-tmux", "approve"],
        "selected_services": ["context7:canonical", "mentality:static_repo_local", "ssh-tmux:session_scoped"],
        "expected_story": [
            "The assistant presents the ContextForge service list.",
            "The user selects a small mixed service set using ordinary language.",
            "The assistant presents a plan covering context7, mentality, and ssh-tmux without silently dropping a selected service.",
            "The user approves.",
            "The assistant applies the project-local package, reports success, and states reload/new-session requirements.",
        ],
    },
    "all": {
        "title": "all-services selection",
        "prompts": ["hello", "all services", "python", "approve"],
        "selected_services": [
            "context7:canonical",
            "exa-search:credential_scoped",
            "github:canonical",
            "mentality:static_repo_local",
            "openzeppelin-solidity-contracts:canonical",
            "playwright:session_scoped",
            "ssh-tmux:session_scoped",
            "web-search:credential_scoped",
            "serena:<project-hash>",
        ],
        "expected_story": [
            "The assistant presents the ContextForge service list.",
            "The user selects all services using ordinary language.",
            "The assistant requests required Serena language input before approval.",
            "The user supplies a normal language value.",
            "The assistant presents a complete plan for all helper-offered real services or explicit per-service blocked/non-action results.",
            "The user approves.",
            "The assistant applies the project-local package, reports success or explicit blocks, and states reload/new-session requirements.",
        ],
    },
}


SCORECARD = [
    ("clean_start", 10, "fresh target-client home/session state and virgin workspace"),
    ("natural_prompts", 10, "minimal ordinary prompts without helper/tool coaching"),
    ("service_menu", 10, "service list presented before selection"),
    ("selection_shape", 15, "selected shape is represented without silent omissions"),
    ("plan_review", 15, "assistant presents clear project-local plan/non-actions before approval"),
    ("approval_apply_order", 15, "approval and apply occur only after the user approves"),
    ("post_apply_readback", 10, "assistant reports applied project-local result"),
    ("reload_boundary", 10, "assistant states reload/new-session requirement"),
    ("no_overclaim", 5, "no post-refresh tool-use/provider-runtime overclaim"),
]


def load_uc1_module() -> Any:
    path = Path(__file__).with_name("run-use-case-1-dialogue.py")
    spec = importlib.util.spec_from_file_location("use_case_1_runner", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client", choices=["pi", "opencode", "codex"], required=True)
    parser.add_argument("--shape", choices=sorted(SHAPES), required=True)
    parser.add_argument("--session-id", default="")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--no-build", action="store_true")
    args = parser.parse_args(argv)
    if args.timeout < 90:
        raise SystemExit("--timeout must be at least 90 seconds for Use Case 5 dialogue evaluation")

    uc1 = load_uc1_module()
    shape = SHAPES[args.shape]
    repo_root = Path(__file__).resolve().parents[3]
    harness_root = repo_root / "docker" / "client-harness"
    lock_file = uc1.acquire_harness_lock(harness_root)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_root = harness_root / "evidence" / "use-case-5" / args.shape / args.client
    output_root.mkdir(parents=True, exist_ok=True)
    session_id = args.session_id or default_session_id(args.client, args.shape, timestamp)
    container = f"cf-uc5-{args.shape}-{args.client}-{timestamp.lower().replace('z', '')}"
    commands: list[dict[str, Any]] = []

    reset = uc1.run(
        [
            sys.executable,
            str(harness_root / "scripts" / "reset-client-harness-state.py"),
            "--client",
            uc1.reset_client_name(args.client),
            "--reset-home-volume",
            "--evidence-dir",
            "docker/client-harness/evidence/use-case-5/prior",
        ],
        cwd=repo_root,
        timeout=120,
        commands=commands,
    )
    reset_json = uc1.parse_json_or_text(reset["stdout"])

    uc1.ensure_semantic_model_env(harness_root, client=args.client, commands=commands, runner=uc1.run)
    build_result = None
    if not args.no_build:
        build_result = uc1.run(
            ["docker", "compose", "-f", str(harness_root / "compose.yml"), "build", "base", uc1.build_service_name(args.client)],
            cwd=repo_root,
            timeout=600,
            commands=commands,
        )

    launch_env_args = uc1.codex_empty_api_key_env_args() if args.client == "codex" else []
    launch = uc1.run(
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
            uc1.compose_service_name(args.client),
            "sleep",
            "infinity",
        ],
        cwd=repo_root,
        timeout=120,
        commands=commands,
    )
    runtime = uc1.run(["docker", "exec", container, "bash", "-lc", uc1.runtime_readback_command(args.client)], cwd=repo_root, timeout=120, commands=commands)

    turn_results: list[dict[str, Any]] = []
    for index, prompt in enumerate(shape["prompts"], start=1):
        client_cmd = uc1.target_client_command(
            args.client,
            session_id,
            prompt,
            create_session=args.client == "opencode" and index == 1 and not args.session_id,
        )
        result = uc1.run(["docker", "exec", container, "bash", "-lc", client_cmd], cwd=repo_root, timeout=args.timeout, commands=commands)
        turn_path = output_root / f"{args.client}-{args.shape}-turn{index}-{timestamp}.raw.txt"
        turn_path.write_text(uc1.render_command_block(result), encoding="utf-8")
        turn_results.append({"turn": index, "prompt": prompt, "path": str(turn_path), **result})
        if args.client == "opencode" and index == 1 and not args.session_id:
            discovered = uc1.extract_opencode_session_id(str(result.get("stdout") or ""))
            if discovered:
                session_id = discovered
        if args.client == "codex" and index == 1 and not args.session_id:
            discovered = uc1.extract_codex_session_id(str(result.get("stdout") or ""))
            if discovered:
                session_id = discovered

    dialogue_summary = uc1.summarize_dialogue(turn_results)
    generation_report = uc1.build_generation_report(
        client=args.client,
        session_id=session_id,
        turns=turn_results,
        dialogue_summary=dialogue_summary,
    )
    combined_path = output_root / f"{args.client}-{args.shape}-use-case-5-evidence-{timestamp}.md"
    combined_path.write_text(
        render_combined(
            uc1=uc1,
            client=args.client,
            shape_id=args.shape,
            shape=shape,
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
        ),
        encoding="utf-8",
    )
    metadata = build_metadata(
        uc1=uc1,
        client=args.client,
        shape_id=args.shape,
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
    metadata_path = output_root / f"{args.client}-{args.shape}-metadata-{timestamp}.json"
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    verifier = uc1.run(
        [
            sys.executable,
            str(harness_root / "scripts" / "verify-use-case-5-e2e-evidence.py"),
            "--client",
            args.client,
            "--shape",
            args.shape,
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
    verifier_json = uc1.parse_json_or_text(verifier["stdout"])
    verifier_path = output_root / f"{args.client}-{args.shape}-verifier-{timestamp}.json"
    verifier_path.write_text(json.dumps(verifier_json, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    package_path = output_root / f"{args.client}-{args.shape}-evaluation-package-{timestamp}.md"
    package_path.write_text(
        render_package(args.client, args.shape, shape, combined_path, verifier_path, verifier_json, generation_report),
        encoding="utf-8",
    )

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
        "shape": args.shape,
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


def default_session_id(client: str, shape: str, timestamp: str) -> str:
    compact = timestamp.lower().replace("t", "").replace("z", "")
    if client == "opencode":
        return f"ses_uc5_{shape}_{compact}"
    if client == "codex":
        return ""
    return f"uc5-{shape}-pi-{timestamp}"


def render_combined(
    *,
    uc1: Any,
    client: str,
    shape_id: str,
    shape: dict[str, Any],
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
        f"# Use Case 5 {shape_id} {client} Dialogue Evidence",
        "",
        f"Timestamp: {timestamp}",
        f"Client: {client}",
        f"Shape: {shape_id} - {shape['title']}",
        f"Session ID: {session_id}",
        f"Container: {container}",
        "Prompt sequence: `" + "`, `".join(shape["prompts"]) + "`",
        "",
        "## Command Ledger",
        "",
    ]
    for item in commands:
        lines.append(f"- `{item['command_text']}` -> rc={item['returncode']} timeout={item['timeout']}")
    lines.extend(uc1.render_dialogue_summary_markdown(dialogue_summary))
    lines.extend(["", "## Generation Report", "", "```json", json.dumps(generation_report, indent=2, sort_keys=True), "```", ""])
    lines.extend(["", "## Reset Readback", "", "```json", json.dumps(reset_json, indent=2, sort_keys=True), "```", ""])
    for label, value in (("Reset Command Output", reset), ("Build Output", build_result), ("Launch Output", launch), ("Runtime Readback", runtime)):
        if value is None:
            continue
        lines.extend([f"## {label}", "", "```text", uc1.render_command_block(value), "```", ""])
    for turn in turns:
        lines.extend(
            [
                f"## Turn {turn['turn']}: {turn['prompt']}",
                "",
                f"User: {turn['prompt']}",
                "",
                "```text",
                uc1.render_command_block(turn),
                "```",
                "",
            ]
        )
    return "\n".join(lines)


def build_metadata(
    *,
    uc1: Any,
    client: str,
    shape_id: str,
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
    statuses = {
        "reset": command_status(reset),
        "launch": command_status(launch),
        "runtime": command_status(runtime),
    }
    for turn in turns:
        statuses[f"turn_{turn['turn']}"] = command_status(turn)
    return {
        "use_case": "use-case-5",
        "shape": shape_id,
        "client": client,
        "session_id": session_id,
        "container": container,
        "semantic_acceptance": "requires_agent_evaluation",
        "runner_contract": {
            "non_ephemeral_container": True,
            "reset_home_volume_requested": True,
            "virgin_workspace_reset_requested": True,
            "deterministic_checks_are_structural_only": True,
            "reset_client": uc1.reset_client_name(client),
            "compose_service": uc1.compose_service_name(client),
        },
        "reset_json": reset_json,
        "generation_report": generation_report,
        "commands": commands,
        "required_command_statuses": statuses,
        "semantic_criteria": [
            "natural_user_prompts",
            "service_selection_plan_apply_readback",
            "shape_coverage",
            "reload_or_new_session_boundary",
            "hidden_instruction_boundary",
            "non_actions",
        ],
    }


def command_status(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "returncode": result.get("returncode"),
        "timeout": bool(result.get("timeout")),
    }


def render_package(
    client: str,
    shape_id: str,
    shape: dict[str, Any],
    combined_path: Path,
    verifier_path: Path,
    verifier_json: Any,
    generation_report: dict[str, Any],
) -> str:
    lines = [
        f"# Evaluation Package: {client} Use Case 5 {shape_id}",
        "",
        f"Shape: `{shape_id}` - {shape['title']}",
        f"Selected services: `{', '.join(shape['selected_services'])}`",
        f"Combined evidence: `{combined_path}`",
        f"Verifier: `{verifier_path}`",
        f"Deterministic verifier ok: `{bool(isinstance(verifier_json, dict) and verifier_json.get('ok'))}`",
        "Deterministic verifier scope: `harness and structured-evidence support; not semantic acceptance`",
        "Acceptance status: `requires_agent_evaluator_scoring`",
        "",
        "## Expected Visible Story",
        "",
    ]
    for item in shape["expected_story"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Scorecard",
            "",
        ]
    )
    for criterion, points, expected in SCORECARD:
        lines.append(f"- {criterion}: {points} pts - {expected}")
    lines.extend(
        [
            "",
            "Fatal failures: coached prompts, missing service list, selected service omission, approval/apply before user approval, missing project-local plan, missing post-apply readback, missing reload/new-session boundary, forbidden global/secret/runtime/registry mutation, post-refresh tool-use overclaim, deterministic semantic scoring of prose.",
            "",
            "Required evaluator narrative: setup/clean state, each prompt and visible reply, supporting tool traces, selection-shape coverage, approval/apply order, applied state/readback, reload/new-session boundary, non-actions, failure classification, score, and final PASS or FAIL.",
            "",
            "## Generation Report",
            "",
            "```json",
            json.dumps(generation_report, indent=2, sort_keys=True),
            "```",
        ]
    )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
