#!/usr/bin/env python3
"""Run Use Case 9 through target clients against one shared project fixture."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROMPT = "what ContextForge state are you using right now?"
CLIENTS = ("pi", "opencode", "codex")
CLIENT_KEY = "-".join(CLIENTS)
CLIENT_LABEL = "/".join("OpenCode" if client == "opencode" else client.title() for client in CLIENTS)


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
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--no-build", action="store_true")
    args = parser.parse_args(argv)
    if args.timeout < 90:
        raise SystemExit("--timeout must be at least 90 seconds for Use Case 9 dialogue evaluation")

    uc1 = load_runner("1")
    uc3 = load_runner("3")
    repo_root = Path(__file__).resolve().parents[3]
    harness_root = repo_root / "docker" / "client-harness"
    lock_file = uc3.acquire_harness_lock(harness_root)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_root = harness_root / "evidence" / "use-case-9"
    output_root.mkdir(parents=True, exist_ok=True)
    commands: list[dict[str, Any]] = []

    reset_results: dict[str, Any] = {}
    for client in CLIENTS:
        reset = uc3.run(
            [
                sys.executable,
                str(harness_root / "scripts" / "reset-client-harness-state.py"),
                "--client",
                uc3.reset_client_name(client),
                "--reset-home-volume",
                "--evidence-dir",
                "docker/client-harness/evidence/use-case-9/prior",
            ],
            cwd=repo_root,
            timeout=120,
            commands=commands,
        )
        reset_results[client] = uc3.parse_json_or_text(reset["stdout"])

    if any(client != "codex" for client in CLIENTS) and not (harness_root / "env" / "local-llama.env").exists():
        uc3.run([str(harness_root / "scripts" / "make-local-llama-env.sh")], cwd=harness_root, timeout=60, commands=commands)
    if not args.no_build:
        build_services = ["base", *dict.fromkeys(uc3.build_service_name(client) for client in CLIENTS)]
        uc3.run(["docker", "compose", "-f", str(harness_root / "compose.yml"), "build", *build_services], cwd=repo_root, timeout=600, commands=commands)

    setup_results: dict[str, dict[str, Any]] = {}
    for client in CLIENTS:
        setup_container = f"cf-uc9-{client}-setup-{timestamp.lower().replace('z', '')}"
        launch_env_args = uc3.codex_empty_api_key_env_args() if client == "codex" else []
        uc3.run(["docker", "compose", "-f", str(harness_root / "compose.yml"), "run", *launch_env_args, "--name", setup_container, "--no-deps", "-d", uc3.compose_service_name(client), "sleep", "infinity"], cwd=repo_root, timeout=120, commands=commands)
        setup_results[client] = uc3.run(["docker", "exec", setup_container, "bash", "-lc", uc3.initialized_fixture_command(client)], cwd=repo_root, timeout=180, commands=commands)
        uc3.run(["docker", "rm", "-f", setup_container], cwd=repo_root, timeout=60, commands=commands)

    for client in CLIENTS:
        uc3.reset_home_only(client, repo_root, commands)

    containers = {client: f"cf-uc9-{client}-runner-{timestamp.lower().replace('z', '')}" for client in CLIENTS}
    launch_results: dict[str, dict[str, Any]] = {}
    runtime_results: dict[str, dict[str, Any]] = {}
    fixture_results: dict[str, dict[str, Any]] = {}
    for client in CLIENTS:
        launch_env_args = uc3.codex_empty_api_key_env_args() if client == "codex" else []
        launch_results[client] = uc3.run(["docker", "compose", "-f", str(harness_root / "compose.yml"), "run", *launch_env_args, "--name", containers[client], "--no-deps", "-d", uc3.compose_service_name(client), "sleep", "infinity"], cwd=repo_root, timeout=120, commands=commands)
        runtime_results[client] = uc3.run(["docker", "exec", containers[client], "bash", "-lc", uc1.runtime_readback_command(client)], cwd=repo_root, timeout=120, commands=commands)
        fixture_results[client] = uc3.run(["docker", "exec", containers[client], "bash", "-lc", uc3.fixture_readback_command(client)], cwd=repo_root, timeout=120, commands=commands)

    session_ids = {client: (f"uc9-{client}-{timestamp}" if client != "codex" else "") for client in CLIENTS}
    turns: list[dict[str, Any]] = []
    for index, client in enumerate(CLIENTS, start=1):
        create_session = client == "opencode"
        client_cmd = uc1.target_client_command(client, session_ids[client], PROMPT, create_session=create_session)
        result = uc3.run(["docker", "exec", containers[client], "bash", "-lc", client_cmd], cwd=repo_root, timeout=args.timeout, commands=commands)
        if client == "opencode":
            discovered = uc1.extract_opencode_session_id(str(result.get("stdout") or ""))
            if discovered:
                session_ids[client] = discovered
        if client == "codex":
            discovered = uc1.extract_codex_session_id(str(result.get("stdout") or ""))
            if discovered:
                session_ids[client] = discovered
        turn_path = output_root / f"{client}-turn-{timestamp}.raw.txt"
        turn_path.write_text(uc1.render_command_block(result), encoding="utf-8")
        turns.append({"turn": index, "client": client, "prompt": PROMPT, "path": str(turn_path), **result})

    dialogue_summary = uc1.summarize_dialogue(turns)
    generation_report = build_cross_client_generation_report(uc1, session_ids, turns, dialogue_summary)
    state = load_state(harness_root / "workspace" / ".project" / "context_forge_state.json")
    comparison = build_cross_client_comparison(state, harness_root)
    session_id = "|".join(session_ids[client] for client in CLIENTS)
    reset_summary = combined_reset_summary(reset_results)

    combined_path = output_root / f"{CLIENT_KEY}-use-case-9-evidence-{timestamp}.md"
    combined_path.write_text(
        render_combined(
            timestamp=timestamp,
            session_ids=session_ids,
            containers=containers,
            commands=commands,
            reset_results=reset_results,
            setup_results=setup_results,
            runtime_results=runtime_results,
            fixture_results=fixture_results,
            turns=turns,
            dialogue_summary=dialogue_summary,
            generation_report=generation_report,
            comparison=comparison,
        ),
        encoding="utf-8",
    )
    metadata = build_metadata(
        session_id=session_id,
        containers=containers,
        reset_summary=reset_summary,
        reset_results=reset_results,
        generation_report=generation_report,
        commands=commands,
        setup_results=setup_results,
        launch_results=launch_results,
        runtime_results=runtime_results,
        fixture_results=fixture_results,
        turns=turns,
        comparison=comparison,
    )
    metadata_path = output_root / f"{CLIENT_KEY}-metadata-{timestamp}.json"
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    verifier = uc3.run(
        [
            sys.executable,
            str(harness_root / "scripts" / "verify-use-case-9-e2e-evidence.py"),
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
    verifier_path = output_root / f"{CLIENT_KEY}-verifier-{timestamp}.json"
    verifier_path.write_text(json.dumps(verifier_json, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    package_path = output_root / f"{CLIENT_KEY}-evaluation-package-{timestamp}.md"
    package_path.write_text(render_package(combined_path, verifier_path, verifier_json, generation_report, comparison), encoding="utf-8")

    turn_failures = [
        {"client": turn["client"], "returncode": turn["returncode"], "timeout": turn["timeout"]}
        for turn in turns
        if turn["returncode"] != 0 or turn["timeout"]
    ]
    summary = {
        "ok": bool(isinstance(verifier_json, dict) and verifier_json.get("ok")) and not turn_failures,
        "ok_scope": "harness package assembled; not semantic acceptance",
        "semantic_acceptance": "requires_agent_evaluation",
        "session_id": session_id,
        "containers": containers,
        "combined_evidence": str(combined_path),
        "metadata": str(metadata_path),
        "evaluation_package_markdown": str(package_path),
        "verifier": str(verifier_path),
        "verifier_failures": verifier_json.get("failures") if isinstance(verifier_json, dict) else None,
        "turn_failures": turn_failures,
        "cross_client_comparison": comparison,
        "generation_report": generation_report,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    lock_file.close()
    return 0 if summary["ok"] else 1


def load_state(path: Path) -> dict[str, Any]:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def build_cross_client_comparison(state: dict[str, Any], harness_root: Path) -> dict[str, Any]:
    services = state.get("services") if isinstance(state.get("services"), dict) else {}
    service = services.get("context7:canonical") if isinstance(services.get("context7:canonical"), dict) else {}
    target_clients = service.get("target_clients") if isinstance(service.get("target_clients"), dict) else {}
    enabled_services = sorted(
        str(binding)
        for binding, value in services.items()
        if isinstance(value, dict) and isinstance(value.get("target_clients"), dict)
    )
    decisions = state.get("decisions") if isinstance(state.get("decisions"), dict) else {}
    skipped = sorted(
        str(value.get("service_binding") or key)
        for key, value in decisions.items()
        if isinstance(value, dict) and str(value.get("state") or "") in {"declined", "deferred", "disabled"}
    )
    project = state.get("project") if isinstance(state.get("project"), dict) else {}
    meta = state.get("meta") if isinstance(state.get("meta"), dict) else {}
    opencode_config = harness_root / "workspace" / "opencode.json"
    codex_config = harness_root / "workspace" / ".codex" / "config.toml"
    expected_clients = set(CLIENTS)
    target_client_set = set(target_clients)
    return {
        "structured_comparison_only": True,
        "project_root": project.get("root"),
        "project_root_workspace": project.get("root") == "/workspace",
        "state_status": state.get("status"),
        "state_status_initialized": state.get("status") == "initialized",
        "state_revision": meta.get("revision"),
        "state_revision_present": isinstance(meta.get("revision"), int),
        "enabled_services": enabled_services,
        "enabled_services_aligned": enabled_services == ["context7:canonical"],
        "context7_enabled_for_both": {"pi", "opencode"}.issubset(target_client_set),
        "context7_enabled_for_all": expected_clients.issubset(target_client_set),
        "target_clients": sorted(str(key) for key in target_clients),
        "target_clients_include_pi_and_opencode": {"pi", "opencode"}.issubset(target_client_set),
        "target_clients_include_all_clients": expected_clients.issubset(target_client_set),
        "skipped_or_unavailable_decisions": skipped,
        "client_import_surfaces_present": opencode_config.exists() and codex_config.exists() and bool(target_clients.get("pi")),
        "opencode_config_present": opencode_config.exists(),
        "codex_config_present": codex_config.exists(),
    }


def combined_reset_summary(reset_results: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": all(isinstance(value, dict) and value.get("ok") is True for value in reset_results.values()),
        "client": CLIENT_KEY,
        "client_reset": {
            "postcondition": all(
                isinstance(value, dict)
                and isinstance(value.get("client_reset"), dict)
                and value["client_reset"].get("postcondition") is True
                for value in reset_results.values()
            )
        },
        "workspace_reset": {
            "postcondition": all(
                isinstance(value, dict)
                and isinstance(value.get("workspace_reset"), dict)
                and value["workspace_reset"].get("postcondition") is True
                for value in reset_results.values()
            )
        },
        "per_client": reset_results,
    }


def build_cross_client_generation_report(uc1: Any, session_ids: dict[str, str], turns: list[dict[str, Any]], dialogue_summary: dict[str, Any]) -> dict[str, Any]:
    report = uc1.build_generation_report(
        client=CLIENT_KEY,
        session_id="|".join(session_ids[client] for client in CLIENTS),
        turns=turns,
        dialogue_summary=dialogue_summary,
    )
    report["per_client_session_ids"] = session_ids
    return report


def build_metadata(
    *,
    session_id: str,
    containers: dict[str, str],
    reset_summary: dict[str, Any],
    reset_results: dict[str, Any],
    generation_report: dict[str, Any],
    commands: list[dict[str, Any]],
    setup_results: dict[str, dict[str, Any]],
    launch_results: dict[str, dict[str, Any]],
    runtime_results: dict[str, dict[str, Any]],
    fixture_results: dict[str, dict[str, Any]],
    turns: list[dict[str, Any]],
    comparison: dict[str, Any],
) -> dict[str, Any]:
    required_statuses: dict[str, dict[str, Any]] = {}
    for client in CLIENTS:
        required_statuses[f"setup_{client}"] = command_status(setup_results[client])
        required_statuses[f"launch_{client}"] = command_status(launch_results[client])
        required_statuses[f"runtime_{client}"] = command_status(runtime_results[client])
        required_statuses[f"fixture_{client}"] = command_status(fixture_results[client])
    for turn in turns:
        required_statuses[f"turn_{turn['client']}"] = command_status(turn)
    return {
        "use_case": "use-case-9",
        "client": CLIENT_KEY,
        "session_id": session_id,
        "containers": containers,
        "container": ",".join(containers.values()),
        "semantic_acceptance": "requires_agent_evaluation",
        "runner_contract": {
            "non_ephemeral_container": True,
            "reset_home_volume_requested": True,
            "virgin_workspace_reset_requested": True,
            "deterministic_checks_are_structural_only": True,
            "target_clients": list(CLIENTS),
            "compose_services": {client: uc3_compose_service_name(client) for client in CLIENTS},
            "post_setup_home_reset": {
                client: ("not_applicable_authenticated_image_no_disposable_home_volume" if client == "codex" else "performed")
                for client in CLIENTS
            },
        },
        "reset_json": reset_summary,
        "per_client_reset_json": reset_results,
        "generation_report": generation_report,
        "commands": commands,
        "required_command_statuses": required_statuses,
        "cross_client_comparison": comparison,
        "semantic_criteria": [
            "natural_user_prompts",
            "cross_client_state_consistency",
            "client_specific_tool_name_honesty",
            "same_project_no_onboarding_restart",
            "hidden_instruction_boundary",
            "non_actions",
        ],
    }


def command_status(result: dict[str, Any]) -> dict[str, Any]:
    return {"returncode": result.get("returncode"), "timeout": bool(result.get("timeout"))}


def render_combined(
    *,
    timestamp: str,
    session_ids: dict[str, str],
    containers: dict[str, str],
    commands: list[dict[str, Any]],
    reset_results: dict[str, Any],
    setup_results: dict[str, dict[str, Any]],
    runtime_results: dict[str, dict[str, Any]],
    fixture_results: dict[str, dict[str, Any]],
    turns: list[dict[str, Any]],
    dialogue_summary: dict[str, Any],
    generation_report: dict[str, Any],
    comparison: dict[str, Any],
) -> str:
    lines = [
        f"# Use Case 9 {CLIENT_LABEL} Dialogue Evidence",
        "",
        f"Timestamp: {timestamp}",
        f"Prompt: `{PROMPT}`",
        "",
        "## Sessions And Containers",
        "",
    ]
    for client in CLIENTS:
        lines.append(f"- {client}: session `{session_ids[client]}`, container `{containers[client]}`")
    lines.extend(
        [
        "",
        "## Command Ledger",
        "",
        ]
    )
    for item in commands:
        lines.append(f"- `{item['command_text']}` -> rc={item['returncode']} timeout={item['timeout']}")
    sections: list[tuple[str, Any]] = [
        ("Generation Report", generation_report),
        ("Structured Cross-Client Comparison", comparison),
        ("Dialogue Summary", dialogue_summary),
        ("Reset Readback", reset_results),
    ]
    for title, payload in sections:
        lines.extend(["", f"## {title}", "```json", json.dumps(payload, indent=2, sort_keys=True), "```"])
    for client in CLIENTS:
        lines.extend(["", f"## {client.title()} Setup Output", "```text", command_block(setup_results[client]), "```"])
        lines.extend(["", f"## {client.title()} Runtime Output", "```text", command_block(runtime_results[client]), "```"])
        lines.extend(["", f"## {client.title()} Fixture Output", "```text", command_block(fixture_results[client]), "```"])
        turn = next(item for item in turns if item["client"] == client)
        lines.extend(["", f"## {client.title()} Turn Output", "```text", command_block(turn), "```"])
    return "\n".join(lines) + "\n"


def command_block(result: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"COMMAND: {result['command_text']}",
            f"CWD: {result['cwd']}",
            f"RETURNCODE: {result['returncode']}",
            f"TIMEOUT: {str(result['timeout']).lower()}",
            "",
            "STDOUT:",
            str(result.get("stdout") or ""),
            "",
            "STDERR:",
            str(result.get("stderr") or ""),
            "",
        ]
    )


def render_package(
    combined_path: Path,
    verifier_path: Path,
    verifier_json: Any,
    generation_report: dict[str, Any],
    comparison: dict[str, Any],
) -> str:
    return "\n".join(
        [
            f"# Evaluation Package: {CLIENT_LABEL} Use Case 9",
            "",
            f"Use case: Use the same initialized project from {CLIENT_LABEL} and compare ContextForge state/capability readback.",
            f"Combined evidence: `{combined_path}`",
            f"Verifier: `{verifier_path}`",
            f"Deterministic verifier ok: `{bool(isinstance(verifier_json, dict) and verifier_json.get('ok'))}`",
            "Deterministic verifier scope: `harness, command status, structured state comparison; not semantic acceptance`",
            "Acceptance status: `requires_agent_evaluator_scoring`",
            "",
            "## Deterministic Boundary",
            "",
            "The runner reports and structures model generations but does not semantically accept them. Deterministic checks may validate commands, artifacts, JSON state fields, and adapter surface presence; free-form assistant behavior requires agent evaluator scoring.",
            "",
            "## Structured Cross-Client Comparison",
            "",
            "```json",
            json.dumps(comparison, indent=2, sort_keys=True),
            "```",
            "",
            "## Generation Report",
            "",
            "```json",
            json.dumps(generation_report, indent=2, sort_keys=True),
            "```",
            "",
            "Semantic evaluator must judge visible user-agent behavior first, then supporting traces.",
            f"Required narrative: setup, shared initialized fixture, {' prompt/reply, '.join(CLIENT_LABEL.split('/'))} prompt/reply, project root/revision alignment, service/capability alignment, skipped/error alignment, readiness honesty, non-actions, score, verdict.",
        ]
    )


def uc3_compose_service_name(client: str) -> str:
    return "codex-cli-authenticated" if client == "codex" else client


if __name__ == "__main__":
    raise SystemExit(main())
