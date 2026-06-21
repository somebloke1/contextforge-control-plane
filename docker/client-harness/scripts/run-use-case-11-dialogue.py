#!/usr/bin/env python3
"""Run Use Case 11 project tool guidance through a real client CLI."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from harness_redaction import redact_text, redact_value


FIRST_PROMPT = "how should I use the project docs lookup capability for opencode configuration questions?"
FOLLOWUP_PROMPT = "use that approach to check what I should read about opencode config files"


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
        raise SystemExit("--timeout must be at least 90 seconds for Use Case 11 dialogue evaluation")

    uc1 = load_runner("1")
    uc3 = load_runner("3")
    repo_root = Path(__file__).resolve().parents[3]
    harness_root = repo_root / "docker" / "client-harness"
    lock_file = uc3.acquire_harness_lock(harness_root)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_root = harness_root / "evidence" / "use-case-11" / args.client
    output_root.mkdir(parents=True, exist_ok=True)
    setup_container = f"cf-uc11-{args.client}-setup-{timestamp.lower().replace('z', '')}"
    container = f"cf-uc11-{args.client}-runner-{timestamp.lower().replace('z', '')}"
    session_id = "" if args.client == "codex" else f"uc11-{args.client}-{timestamp}"
    commands: list[dict[str, Any]] = []

    reset = uc3.run(
        [
            sys.executable,
            str(harness_root / "scripts" / "reset-client-harness-state.py"),
            "--client",
            uc3.reset_client_name(args.client),
            "--reset-home-volume",
            "--evidence-dir",
            "docker/client-harness/evidence/use-case-11/prior",
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
    projection = uc3.run(["docker", "exec", container, "bash", "-lc", projection_readback_command(args.client, uc3)], cwd=repo_root, timeout=120, commands=commands)
    projection_json = uc3.parse_json_or_text(projection["stdout"])
    guidance = uc3.run(["docker", "exec", container, "bash", "-lc", guidance_readback_command(args.client, uc3)], cwd=repo_root, timeout=120, commands=commands)
    guidance_json = uc3.parse_json_or_text(guidance["stdout"])

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

    combined_path = output_root / f"{args.client}-use-case-11-evidence-{timestamp}.md"
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
            projection=projection,
            projection_json=projection_json,
            guidance=guidance,
            guidance_json=guidance_json,
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
        projection=projection,
        projection_json=projection_json,
        guidance=guidance,
        guidance_json=guidance_json,
        turns=turns,
    )
    metadata_path = output_root / f"{args.client}-metadata-{timestamp}.json"
    metadata_path.write_text(json.dumps(redact_value(metadata), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    verifier = uc3.run(
        [
            sys.executable,
            str(harness_root / "scripts" / "verify-use-case-11-e2e-evidence.py"),
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
    projection: dict[str, Any],
    projection_json: Any,
    guidance: dict[str, Any],
    guidance_json: Any,
    turns: list[dict[str, Any]],
) -> dict[str, Any]:
    required_statuses = {
        "setup": command_status(setup),
        "launch": command_status(launch),
        "runtime": command_status(runtime),
        "fixture": command_status(fixture),
        "projection": command_status(projection),
        "guidance": command_status(guidance),
    }
    for turn in turns:
        required_statuses[f"turn_{turn['turn']}"] = command_status(turn)
    projection_fields = build_projection_fields(client, projection_json)
    return {
        "use_case": "use-case-11",
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
            "post_setup_home_reset": "not_applicable_authenticated_image_no_disposable_home_volume" if client == "codex" else "performed",
        },
        "reset_json": reset_json,
        "generation_report": generation_report,
        **projection_fields,
        "guidance_metadata_readback": build_guidance_metadata(guidance_json),
        "commands": commands,
        "required_command_statuses": required_statuses,
        "semantic_criteria": [
            "clean_initialized_guidance_fixture",
            "project_graph_projection_separation",
            "non_ephemeral_same_session",
            "natural_guidance_prompt",
            "guidance_surface_used_or_honestly_available",
            "practical_project_specific_guidance",
            "implementation_noise_suppressed",
            "optional_followup_applies_guidance",
            "readiness_and_non_actions",
        ],
    }


def projection_readback_command(client: str, uc3: Any) -> str:
    helper_python = uc3.helper_python_path(client)
    code = f"""
import json
from pathlib import Path

client = {client!r}
service_binding = "context7:canonical"
state_path = Path("/workspace/.project/context_forge_state.json")
data = json.loads(state_path.read_text(encoding="utf-8"))
service_key = None
service = None
for key, value in (data.get("services") or {{}}).items():
    if isinstance(value, dict) and value.get("service_binding") == service_binding:
        service_key = key
        service = value
        break
target_clients = service.get("target_clients") if isinstance(service, dict) and isinstance(service.get("target_clients"), dict) else {{}}
target = target_clients.get(client)
service_identity = service.get("x_service_identity") if isinstance(service, dict) and isinstance(service.get("x_service_identity"), dict) else {{}}
out = {{
    "project_service_graph": {{
        "service_binding": service_binding,
        "present": isinstance(service, dict),
        "project_status": data.get("status"),
        "service_key": service_key,
        "service_identity_id": service_identity.get("id") if isinstance(service_identity, dict) else None,
        "project_scoped_instance_owner": "project",
    }},
    "target_client_projection": {{
        "client": client,
        "service_binding": service_binding,
        "present": isinstance(target, dict),
        "status": target.get("status") if isinstance(target, dict) else "missing",
        "validation_status": target.get("validation_status") if isinstance(target, dict) else "missing",
        "service_identity_id": target.get("service_identity_id") if isinstance(target, dict) else None,
        "surface": target.get("surface") if isinstance(target, dict) else None,
    }},
    "target_client_visibility": {{
        "client": client,
        "service_binding": service_binding,
        "status": "requires_semantic_evaluation",
        "structural_basis": "dialogue turns and tool traces captured separately",
    }},
    "target_client_proof": {{
        "client": client,
        "service_binding": service_binding,
        "status": "requires_semantic_evaluation",
        "proof_scope": "single_target_client",
        "semantic_evaluator_required": True,
    }},
}}
print(json.dumps(out, sort_keys=True))
"""
    return f"{helper_python} - <<'PY'\n{code.rstrip()}\nPY"


def build_projection_fields(client: str, projection_json: Any) -> dict[str, Any]:
    if not isinstance(projection_json, dict):
        return {
            "project_service_graph": {"service_binding": "context7:canonical", "present": False, "parse_error": True},
            "target_client_projection": {"client": client, "service_binding": "context7:canonical", "present": False, "parse_error": True},
            "target_client_visibility": {"client": client, "service_binding": "context7:canonical", "status": "requires_semantic_evaluation"},
            "target_client_proof": {
                "client": client,
                "service_binding": "context7:canonical",
                "status": "requires_semantic_evaluation",
                "proof_scope": "single_target_client",
                "semantic_evaluator_required": True,
            },
        }
    return {
        "project_service_graph": dict(projection_json.get("project_service_graph") or {}),
        "target_client_projection": dict(projection_json.get("target_client_projection") or {}),
        "target_client_visibility": dict(projection_json.get("target_client_visibility") or {}),
        "target_client_proof": dict(projection_json.get("target_client_proof") or {}),
    }


def guidance_readback_command(client: str, uc3: Any) -> str:
    helper_python = uc3.helper_python_path(client)
    code = """
import ast
import json
from pathlib import Path

source = Path("/repo/scripts/register_tool_guidance.py")
module = ast.parse(source.read_text(encoding="utf-8"))
assignments = {}
for node in module.body:
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in {"SERVICE_META", "PROMPTS"}:
                assignments[target.id] = ast.literal_eval(node.value)

prompts = assignments.get("PROMPTS", {})
context7_tools = {
    key: {
        "prompt_name": value[0],
        "template": value[1],
    }
    for key, value in prompts.items()
    if key in {"context7-local-resolve-library-id", "context7-local-query-docs"}
}
out = {
    "guidance_source": str(source),
    "service": "context7",
    "service_meta_present": "context7" in assignments.get("SERVICE_META", {}),
    "context7_tool_guidance": context7_tools,
    "required_tool_guidance_present": sorted(context7_tools) == [
        "context7-local-query-docs",
        "context7-local-resolve-library-id",
    ],
}
print(json.dumps(out, sort_keys=True))
"""
    return f"{helper_python} - <<'PY'\n{code.rstrip()}\nPY"


def build_guidance_metadata(guidance_json: Any) -> dict[str, Any]:
    if not isinstance(guidance_json, dict):
        return {
            "service": "context7",
            "source_readback_parse_error": True,
            "required_tool_guidance_present": False,
        }
    return {
        "service": guidance_json.get("service"),
        "guidance_source": guidance_json.get("guidance_source"),
        "service_meta_present": guidance_json.get("service_meta_present"),
        "required_tool_guidance_present": guidance_json.get("required_tool_guidance_present"),
        "context7_tool_guidance": dict(guidance_json.get("context7_tool_guidance") or {}),
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
    projection: dict[str, Any],
    projection_json: Any,
    guidance: dict[str, Any],
    guidance_json: Any,
    turns: list[dict[str, Any]],
    dialogue_summary: dict[str, Any],
    generation_report: dict[str, Any],
) -> str:
    lines = [
        f"# Use Case 11 Evidence: {client}",
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
            "## Project Graph And Target-Client Projection Readback",
            "",
            "```json",
            json.dumps(projection_json, indent=2, sort_keys=True),
            "```",
            "",
            "```text",
            render_command_block(projection),
            "```",
            "",
            "## Guidance Metadata Readback",
            "",
            "```json",
            json.dumps(guidance_json, indent=2, sort_keys=True),
            "```",
            "",
            "```text",
            render_command_block(guidance),
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
        f"# Evaluation Package: {client} Use Case 11",
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
        "Score the visible dialogue and supporting tool traces against `docs/use-cases/use-case-11/package.md`.",
        "Treat deterministic checks as structural evidence only.",
        "Decide whether the assistant surfaced practical project-specific guidance for the selected docs lookup capability.",
        "Keep project service graph, target-client projection, target-client visibility, and target-client proof as separate claims.",
        "Reject any all-client readiness, automatic alignment, or project-global proof claim that is not backed by this target-client evidence.",
        "If the second turn is present, decide whether it remains in the same session and applies the surfaced guidance to the OpenCode config docs task.",
        "Classify failures as package, runner, verifier, tested-client, implementation, environment, or inconclusive.",
        "Provide a step-by-step narrative with evidence references before giving a pass/fail recommendation.",
        "",
    ]
    return "\n".join(lines)


def render_command_block(result: dict[str, Any]) -> str:
    return load_runner("1").render_command_block(result)


if __name__ == "__main__":
    raise SystemExit(main())
