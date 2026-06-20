#!/usr/bin/env python3
"""Run Use Case 6 decline/defer dialogue through a real client CLI."""

from __future__ import annotations

import argparse
import importlib.util
import json
import shlex
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SHAPES: dict[str, dict[str, Any]] = {
    "decline": {
        "title": "decline installation package",
        "prompts": ["hello", "context7", "decline", "what ContextForge state are you using right now?"],
        "expected_decision_state": "declined",
        "expected_binding_prefix": "context7:canonical",
        "expected_story": [
            "The assistant presents the ContextForge service list.",
            "The user selects context7 using ordinary language.",
            "The assistant presents a project-local package and asks for approval or decline.",
            "The user declines.",
            "The assistant records a project-local declined decision and confirms the service was not installed or imported.",
            "The assistant answers a follow-up state question and reports the declined service without claiming active import.",
        ],
    },
    "defer": {
        "title": "defer project-scoped Serena",
        "prompts": ["hello", "serena", "defer", "what ContextForge state are you using right now?"],
        "expected_decision_state": "deferred",
        "expected_binding_prefix": "serena:",
        "expected_story": [
            "The assistant presents the ContextForge service list.",
            "The user selects Serena using ordinary language.",
            "The assistant asks for Serena language or defer.",
            "The user defers.",
            "The assistant records a project-local deferred decision and confirms Serena was not provisioned, installed, or imported.",
            "The assistant answers a follow-up state question and reports the deferred service without claiming active import.",
        ],
    },
}


SCORECARD = [
    ("clean_start", 10, "fresh target-client home/session state and virgin workspace"),
    ("natural_prompts", 10, "minimal ordinary prompts without helper/tool coaching"),
    ("service_menu", 10, "service list presented before selection"),
    ("negative_choice_handling", 15, "decline/defer is handled as a negative choice, not approval"),
    ("project_local_decision_record", 15, "declined/deferred decision is recorded in project-local state"),
    ("active_import_suppression", 15, "selected service is not imported as an active client tool"),
    ("follow_up_readback", 15, "state follow-up reports the negative choice honestly"),
    ("no_overclaim_or_unnecessary_reload", 5, "no installed/reload claim for declined/deferred service"),
    ("hidden_boundary_and_non_actions", 5, "no hidden guidance leakage or forbidden mutation"),
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
        raise SystemExit("--timeout must be at least 90 seconds for Use Case 6 dialogue evaluation")

    uc1 = load_uc1_module()
    shape = SHAPES[args.shape]
    repo_root = Path(__file__).resolve().parents[3]
    harness_root = repo_root / "docker" / "client-harness"
    lock_file = uc1.acquire_harness_lock(harness_root)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_root = harness_root / "evidence" / "use-case-6" / args.shape / args.client
    output_root.mkdir(parents=True, exist_ok=True)
    session_id = args.session_id or default_session_id(args.client, args.shape, timestamp)
    container = f"cf-uc6-{args.shape}-{args.client}-{timestamp.lower().replace('z', '')}"
    commands: list[dict[str, Any]] = []

    reset = uc1.run(
        [
            sys.executable,
            str(harness_root / "scripts" / "reset-client-harness-state.py"),
            "--client",
            uc1.reset_client_name(args.client),
            "--reset-home-volume",
            "--evidence-dir",
            "docker/client-harness/evidence/use-case-6/prior",
        ],
        cwd=repo_root,
        timeout=120,
        commands=commands,
    )
    reset_json = uc1.parse_json_or_text(reset["stdout"])

    local_env = harness_root / "env" / "local-llama.env"
    if args.client != "codex" and not local_env.exists():
        uc1.run([str(harness_root / "scripts" / "make-local-llama-env.sh")], cwd=harness_root, timeout=60, commands=commands)
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

    state_readback = uc1.run(
        [
            "docker",
            "exec",
            container,
            "bash",
            "-lc",
            state_readback_command(args.client, str(shape["expected_binding_prefix"])),
        ],
        cwd=repo_root,
        timeout=120,
        commands=commands,
    )
    decision_state_readback = uc1.parse_json_or_text(state_readback["stdout"])
    dialogue_summary = uc1.summarize_dialogue(turn_results)
    generation_report = uc1.build_generation_report(
        client=args.client,
        session_id=session_id,
        turns=turn_results,
        dialogue_summary=dialogue_summary,
    )
    combined_path = output_root / f"{args.client}-{args.shape}-use-case-6-evidence-{timestamp}.md"
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
            state_readback=state_readback,
            decision_state_readback=decision_state_readback,
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
        state_readback=state_readback,
        decision_state_readback=decision_state_readback,
        turns=turn_results,
    )
    metadata_path = output_root / f"{args.client}-{args.shape}-metadata-{timestamp}.json"
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    verifier = uc1.run(
        [
            sys.executable,
            str(harness_root / "scripts" / "verify-use-case-6-e2e-evidence.py"),
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
        render_package(args.client, args.shape, shape, combined_path, verifier_path, verifier_json, generation_report, decision_state_readback),
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
        "decision_state_readback": decision_state_readback,
        "generation_report": generation_report,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    lock_file.close()
    return 0 if summary["ok"] else 1


def default_session_id(client: str, shape: str, timestamp: str) -> str:
    compact = timestamp.lower().replace("t", "").replace("z", "")
    if client == "opencode":
        return f"ses_uc6_{shape}_{compact}"
    if client == "codex":
        return ""
    return f"uc6-{shape}-pi-{timestamp}"


def state_readback_command(client: str, expected_binding_prefix: str) -> str:
    script = r"""
import json
from pathlib import Path

client = __CLIENT__
expected = __EXPECTED__
path = Path("/workspace/.project/context_forge_state.json")
payload = {
    "state_exists": path.exists(),
    "client": client,
    "expected_binding_prefix": expected,
    "state_status": None,
    "state_revision": None,
    "decision_binding": None,
    "decision_state": None,
    "services_keys": [],
    "active_service_absent": False,
    "target_client_active_import_absent": False,
}
if path.exists():
    state = json.loads(path.read_text(encoding="utf-8"))
    payload["state_status"] = state.get("status")
    payload["state_revision"] = (state.get("meta") or {}).get("revision")
    decisions = state.get("decisions") if isinstance(state.get("decisions"), dict) else {}
    for key, decision in decisions.items():
        if not isinstance(decision, dict):
            continue
        binding = str(decision.get("service_binding") or key)
        if binding.startswith(expected):
            payload["decision_binding"] = binding
            payload["decision_state"] = decision.get("state")
            break
    services = state.get("services") if isinstance(state.get("services"), dict) else {}
    payload["services_keys"] = sorted(services)
    active = []
    target_active = []
    for key, service in services.items():
        if not isinstance(service, dict):
            continue
        binding = str(service.get("service_binding") or key)
        if binding.startswith(expected):
            active.append(binding)
            targets = service.get("target_clients") if isinstance(service.get("target_clients"), dict) else {}
            if isinstance(targets.get(client), dict):
                target_active.append(binding)
    payload["active_service_absent"] = not active
    payload["target_client_active_import_absent"] = not target_active
print(json.dumps(payload, indent=2, sort_keys=True))
"""
    script = script.replace("__CLIENT__", json.dumps(client)).replace("__EXPECTED__", json.dumps(expected_binding_prefix))
    return "python3 - <<'PY'\n" + script + "\nPY"


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
    state_readback: dict[str, Any],
    decision_state_readback: Any,
    turns: list[dict[str, Any]],
    commands: list[dict[str, Any]],
) -> str:
    lines = [
        f"# Use Case 6 {shape_id} {client} Dialogue Evidence",
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
    lines.extend(["", "## Decision State Readback", "", "```json", json.dumps(decision_state_readback, indent=2, sort_keys=True), "```", ""])
    lines.extend(["", "## Reset Readback", "", "```json", json.dumps(reset_json, indent=2, sort_keys=True), "```", ""])
    for label, value in (
        ("Reset Command Output", reset),
        ("Build Output", build_result),
        ("Launch Output", launch),
        ("Runtime Readback", runtime),
        ("State Readback Command", state_readback),
    ):
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
    state_readback: dict[str, Any],
    decision_state_readback: Any,
    turns: list[dict[str, Any]],
) -> dict[str, Any]:
    statuses = {
        "reset": command_status(reset),
        "launch": command_status(launch),
        "runtime": command_status(runtime),
        "state_readback": command_status(state_readback),
    }
    for turn in turns:
        statuses[f"turn_{turn['turn']}"] = command_status(turn)
    return {
        "use_case": "use-case-6",
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
        "decision_state_readback": decision_state_readback,
        "semantic_criteria": [
            "natural_user_prompts",
            "decline_or_defer_recorded_without_import",
            "continued_available_capabilities",
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
    decision_state_readback: Any,
) -> str:
    lines = [
        f"# Evaluation Package: {client} Use Case 6 {shape_id}",
        "",
        f"Shape: `{shape_id}` - {shape['title']}",
        f"Combined evidence: `{combined_path}`",
        f"Verifier: `{verifier_path}`",
        f"Deterministic verifier ok: `{bool(isinstance(verifier_json, dict) and verifier_json.get('ok'))}`",
        "Deterministic verifier scope: `harness, generation-report shape, and structured state facts; not semantic acceptance`",
        "Acceptance status: `requires_agent_evaluator_scoring`",
        "",
        "## Expected Visible Story",
        "",
    ]
    for item in shape["expected_story"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Structured State Readback", "", "```json", json.dumps(decision_state_readback, indent=2, sort_keys=True), "```", ""])
    lines.extend(["## Scorecard", ""])
    for criterion, points, expected in SCORECARD:
        lines.append(f"- {criterion}: {points} pts - {expected}")
    lines.extend(
        [
            "",
            "Fatal failures: coached prompts, missing service list, selected service omission, decline/defer treated as approval, approval/apply after decline/defer, active import after negative choice, missing decision state, hidden readback, forbidden mutation, deterministic semantic scoring of prose.",
            "",
            "Required evaluator narrative: setup/clean state, each prompt and visible reply, supporting tool traces, decline/defer handling, structured state readback, active import suppression, follow-up state answer, non-actions, failure classification, score, and final PASS or FAIL.",
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
