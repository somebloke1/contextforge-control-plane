#!/usr/bin/env python3
"""Run Use Case 10 refresh behavior through target clients."""

from __future__ import annotations

import argparse
import importlib.util
import json
import shlex
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BASELINE_PROMPT = "what ContextForge state are you using right now?"
REFRESH_PROMPT = "refresh ContextForge state"
CLIENTS = ("pi", "opencode", "codex")
CLIENT_KEY = "-".join(CLIENTS)
CLIENT_LABEL = "/".join("OpenCode" if client == "opencode" else client.title() for client in CLIENTS)
BASELINE_SERVICE = "context7:canonical"
ADDED_SERVICE = "mentality:static_repo_local"


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
        raise SystemExit("--timeout must be at least 90 seconds for Use Case 10 dialogue evaluation")

    uc1 = load_runner("1")
    uc3 = load_runner("3")
    repo_root = Path(__file__).resolve().parents[3]
    harness_root = repo_root / "docker" / "client-harness"
    lock_file = uc3.acquire_harness_lock(harness_root)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_root = harness_root / "evidence" / "use-case-10"
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
                "docker/client-harness/evidence/use-case-10/prior",
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
        setup_container = f"cf-uc10-{client}-setup-{timestamp.lower().replace('z', '')}"
        launch_env_args = uc3.codex_empty_api_key_env_args() if client == "codex" else []
        uc3.run(["docker", "compose", "-f", str(harness_root / "compose.yml"), "run", *launch_env_args, "--name", setup_container, "--no-deps", "-d", uc3.compose_service_name(client), "sleep", "infinity"], cwd=repo_root, timeout=120, commands=commands)
        setup_results[client] = uc3.run(["docker", "exec", setup_container, "bash", "-lc", uc3.initialized_fixture_command(client)], cwd=repo_root, timeout=180, commands=commands)
        uc3.run(["docker", "rm", "-f", setup_container], cwd=repo_root, timeout=60, commands=commands)

    for client in CLIENTS:
        uc3.reset_home_only(client, repo_root, commands)

    containers = {client: f"cf-uc10-{client}-runner-{timestamp.lower().replace('z', '')}" for client in CLIENTS}
    launch_results: dict[str, dict[str, Any]] = {}
    runtime_results: dict[str, dict[str, Any]] = {}
    fixture_results: dict[str, dict[str, Any]] = {}
    reload_ack_results: dict[str, dict[str, Any]] = {}
    for client in CLIENTS:
        launch_env_args = uc3.codex_empty_api_key_env_args() if client == "codex" else []
        launch_results[client] = uc3.run(["docker", "compose", "-f", str(harness_root / "compose.yml"), "run", *launch_env_args, "--name", containers[client], "--no-deps", "-d", uc3.compose_service_name(client), "sleep", "infinity"], cwd=repo_root, timeout=120, commands=commands)
        runtime_results[client] = uc3.run(["docker", "exec", containers[client], "bash", "-lc", uc1.runtime_readback_command(client)], cwd=repo_root, timeout=120, commands=commands)
        fixture_results[client] = uc3.run(["docker", "exec", containers[client], "bash", "-lc", uc3.fixture_readback_command(client)], cwd=repo_root, timeout=120, commands=commands)
        reload_ack_results[client] = uc3.run(["docker", "exec", containers[client], "bash", "-lc", reload_ack_command(uc3, client)], cwd=repo_root, timeout=120, commands=commands)

    session_ids = {client: (f"uc10-{client}-{timestamp}" if client != "codex" else "") for client in CLIENTS}
    turns: list[dict[str, Any]] = []
    turns.extend(run_prompt_pair(uc1, uc3, repo_root, commands, containers, session_ids, BASELINE_PROMPT, 1, args.timeout, output_root, timestamp, create_opencode=True))

    baseline_state = state_snapshot(harness_root / "workspace" / ".project" / "context_forge_state.json")
    change_results = {
        client: uc3.run(["docker", "exec", containers[client], "bash", "-lc", activation_command(uc3, client, ADDED_SERVICE, f"uc10-{client}-state-change.json")], cwd=repo_root, timeout=180, commands=commands)
        for client in CLIENTS
    }
    after_state = state_snapshot(harness_root / "workspace" / ".project" / "context_forge_state.json")
    fixture_after_results = {
        client: uc3.run(["docker", "exec", containers[client], "bash", "-lc", uc3.fixture_readback_command(client)], cwd=repo_root, timeout=120, commands=commands)
        for client in CLIENTS
    }

    turns.extend(run_prompt_pair(uc1, uc3, repo_root, commands, containers, session_ids, REFRESH_PROMPT, len(CLIENTS) + 1, args.timeout, output_root, timestamp, create_opencode=False))

    dialogue_summary = uc1.summarize_dialogue(turns)
    generation_report = uc1.build_generation_report(
        client=CLIENT_KEY,
        session_id="|".join(session_ids[client] for client in CLIENTS),
        turns=turns,
        dialogue_summary=dialogue_summary,
    )
    generation_report["per_client_session_ids"] = session_ids
    comparison = build_refresh_comparison(baseline_state, after_state)
    session_id = "|".join(session_ids[client] for client in CLIENTS)
    reset_summary = combined_reset_summary(reset_results)

    combined_path = output_root / f"{CLIENT_KEY}-use-case-10-evidence-{timestamp}.md"
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
            reload_ack_results=reload_ack_results,
            change_results=change_results,
            fixture_after_results=fixture_after_results,
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
        reload_ack_results=reload_ack_results,
        change_results=change_results,
        fixture_after_results=fixture_after_results,
        turns=turns,
        comparison=comparison,
    )
    metadata_path = output_root / f"{CLIENT_KEY}-metadata-{timestamp}.json"
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    verifier = uc3.run(
        [
            sys.executable,
            str(harness_root / "scripts" / "verify-use-case-10-e2e-evidence.py"),
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
        {"client": turn["client"], "turn": turn["turn"], "returncode": turn["returncode"], "timeout": turn["timeout"]}
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
        "refresh_comparison": comparison,
        "generation_report": generation_report,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    lock_file.close()
    return 0 if summary["ok"] else 1


def run_prompt_pair(
    uc1: Any,
    uc3: Any,
    repo_root: Path,
    commands: list[dict[str, Any]],
    containers: dict[str, str],
    session_ids: dict[str, str],
    prompt: str,
    first_turn: int,
    timeout: int,
    output_root: Path,
    timestamp: str,
    *,
    create_opencode: bool,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for offset, client in enumerate(CLIENTS):
        turn_no = first_turn + offset
        client_cmd = uc1.target_client_command(client, session_ids[client], prompt, create_session=client == "opencode" and create_opencode)
        result = uc3.run(["docker", "exec", containers[client], "bash", "-lc", client_cmd], cwd=repo_root, timeout=timeout, commands=commands)
        if client == "opencode":
            discovered = uc1.extract_opencode_session_id(str(result.get("stdout") or ""))
            if discovered:
                session_ids[client] = discovered
        if client == "codex":
            discovered = uc1.extract_codex_session_id(str(result.get("stdout") or ""))
            if discovered:
                session_ids[client] = discovered
        turn_path = output_root / f"{client}-turn{turn_no}-{timestamp}.raw.txt"
        turn_path.write_text(uc1.render_command_block(result), encoding="utf-8")
        results.append({"turn": turn_no, "client": client, "prompt": prompt, "path": str(turn_path), **result})
    return results


def activation_command(uc3: Any, client: str, service_id: str, approval_name: str) -> str:
    approval = f"/home/agent/.local/state/contextforge-client-harness-runtime/project-init/{approval_name}"
    payload = json.dumps({"project_root": "/workspace", "client_type": client, "selected_services": [service_id]})
    helper_python = uc3.helper_python_path(client)
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


def reload_ack_command(uc3: Any, client: str) -> str:
    helper_python = uc3.helper_python_path(client)
    payload = json.dumps({"project_root": "/workspace", "client_type": client})
    return " && ".join(
        [
            "cd /workspace",
            f"{helper_python} /repo/scripts/pi_project_init_helper_cli.py --operation record_project_init_client_reload --payload-json {shlex.quote(payload)}",
        ]
    )


def state_snapshot(path: Path) -> dict[str, Any]:
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"exists": False}
    services = state.get("services") if isinstance(state.get("services"), dict) else {}
    target_clients: dict[str, list[str]] = {}
    for binding, value in services.items():
        if not isinstance(value, dict):
            continue
        clients = value.get("target_clients") if isinstance(value.get("target_clients"), dict) else {}
        target_clients[str(binding)] = sorted(str(key) for key in clients)
    return {
        "exists": True,
        "project_root": ((state.get("project") or {}) if isinstance(state.get("project"), dict) else {}).get("root"),
        "state_status": state.get("status"),
        "state_revision": ((state.get("meta") or {}) if isinstance(state.get("meta"), dict) else {}).get("revision"),
        "enabled_services": sorted(str(key) for key in services),
        "target_clients_by_service": target_clients,
    }


def build_refresh_comparison(baseline: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    baseline_services = baseline.get("enabled_services") if isinstance(baseline.get("enabled_services"), list) else []
    after_services = after.get("enabled_services") if isinstance(after.get("enabled_services"), list) else []
    target_clients = after.get("target_clients_by_service") if isinstance(after.get("target_clients_by_service"), dict) else {}
    after_clients_flat = {
        client
        for clients in target_clients.values()
        if isinstance(clients, list)
        for client in clients
    }
    return {
        "structured_comparison_only": True,
        "project_root": after.get("project_root"),
        "project_root_workspace": baseline.get("project_root") == "/workspace" and after.get("project_root") == "/workspace",
        "baseline_state_status": baseline.get("state_status"),
        "after_state_status": after.get("state_status"),
        "baseline_initialized": baseline.get("state_status") == "initialized",
        "after_initialized": after.get("state_status") == "initialized",
        "baseline_revision": baseline.get("state_revision"),
        "after_revision": after.get("state_revision"),
        "revision_increased": isinstance(baseline.get("state_revision"), int) and isinstance(after.get("state_revision"), int) and after["state_revision"] > baseline["state_revision"],
        "baseline_enabled_services": baseline_services,
        "after_enabled_services": after_services,
        "enabled_services_changed": baseline_services != after_services,
        "baseline_context7_only": baseline_services == [BASELINE_SERVICE],
        "after_includes_context7_and_mentality": BASELINE_SERVICE in after_services and ADDED_SERVICE in after_services,
        "target_clients_by_service": target_clients,
        "target_clients_include_pi_and_opencode": {"pi", "opencode"}.issubset(after_clients_flat),
        "target_clients_include_all_clients": set(CLIENTS).issubset(after_clients_flat),
        "added_service": ADDED_SERVICE,
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
    reload_ack_results: dict[str, dict[str, Any]],
    change_results: dict[str, dict[str, Any]],
    fixture_after_results: dict[str, dict[str, Any]],
    turns: list[dict[str, Any]],
    comparison: dict[str, Any],
) -> dict[str, Any]:
    required_statuses: dict[str, dict[str, Any]] = {}
    for client in CLIENTS:
        required_statuses[f"setup_{client}"] = command_status(setup_results[client])
        required_statuses[f"launch_{client}"] = command_status(launch_results[client])
        required_statuses[f"runtime_{client}"] = command_status(runtime_results[client])
        required_statuses[f"fixture_{client}"] = command_status(fixture_results[client])
        required_statuses[f"reload_ack_{client}"] = command_status(reload_ack_results[client])
        required_statuses[f"state_change_{client}"] = command_status(change_results[client])
        required_statuses[f"fixture_after_{client}"] = command_status(fixture_after_results[client])
    for turn in turns:
        required_statuses[f"turn_{turn['turn']}_{turn['client']}"] = command_status(turn)
    return {
        "use_case": "use-case-10",
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
        "refresh_comparison": comparison,
        "semantic_criteria": [
            "natural_user_prompts",
            "state_change_refresh_detected",
            "updated_capabilities_visible_or_bounded",
            "stale_tools_not_presented_as_current",
            "hidden_instruction_boundary",
            "non_actions",
        ],
    }


def command_status(result: dict[str, Any]) -> dict[str, Any]:
    return {"returncode": result.get("returncode"), "timeout": bool(result.get("timeout"))}


def render_combined(**kwargs: Any) -> str:
    lines = [
        f"# Use Case 10 {CLIENT_LABEL} Refresh Evidence",
        "",
        f"Timestamp: {kwargs['timestamp']}",
        f"Baseline prompt: `{BASELINE_PROMPT}`",
        f"Refresh prompt: `{REFRESH_PROMPT}`",
        "",
        "## Sessions And Containers",
        "",
    ]
    for client in CLIENTS:
        lines.append(f"- {client}: session `{kwargs['session_ids'][client]}`, container `{kwargs['containers'][client]}`")
    lines.extend(
        [
        "",
        "## Command Ledger",
        "",
        ]
    )
    for item in kwargs["commands"]:
        lines.append(f"- `{item['command_text']}` -> rc={item['returncode']} timeout={item['timeout']}")
    for title, payload in (
        ("Generation Report", kwargs["generation_report"]),
        ("Structured Refresh Comparison", kwargs["comparison"]),
        ("Dialogue Summary", kwargs["dialogue_summary"]),
        ("Reset Readback", kwargs["reset_results"]),
    ):
        lines.extend(["", f"## {title}", "```json", json.dumps(payload, indent=2, sort_keys=True), "```"])
    for client in CLIENTS:
        lines.extend(["", f"## {client.title()} Setup Output", "```text", command_block(kwargs["setup_results"][client]), "```"])
        lines.extend(["", f"## {client.title()} Runtime Output", "```text", command_block(kwargs["runtime_results"][client]), "```"])
        lines.extend(["", f"## {client.title()} Fixture Before Change Output", "```text", command_block(kwargs["fixture_results"][client]), "```"])
        lines.extend(["", f"## {client.title()} Reload Acknowledgment Output", "```text", command_block(kwargs["reload_ack_results"][client]), "```"])
        lines.extend(["", f"## {client.title()} State Change Output", "```text", command_block(kwargs["change_results"][client]), "```"])
        lines.extend(["", f"## {client.title()} Fixture After Change Output", "```text", command_block(kwargs["fixture_after_results"][client]), "```"])
        for turn in [item for item in kwargs["turns"] if item["client"] == client]:
            lines.extend(["", f"## {client.title()} Turn {turn['turn']} Output", "```text", command_block(turn), "```"])
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


def render_package(combined_path: Path, verifier_path: Path, verifier_json: Any, generation_report: dict[str, Any], comparison: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# Evaluation Package: {CLIENT_LABEL} Use Case 10",
            "",
            "Use case: Refresh tools/capabilities after project-state changes.",
            f"Combined evidence: `{combined_path}`",
            f"Verifier: `{verifier_path}`",
            f"Deterministic verifier ok: `{bool(isinstance(verifier_json, dict) and verifier_json.get('ok'))}`",
            "Deterministic verifier scope: `harness, command status, structured before/after state comparison; not semantic acceptance`",
            "Acceptance status: `requires_agent_evaluator_scoring`",
            "",
            "## Deterministic Boundary",
            "",
            "The runner reports and structures model generations but does not semantically accept them. Deterministic checks may validate commands, artifacts, JSON state fields, and before/after comparison fields; free-form assistant behavior requires agent evaluator scoring.",
            "",
            "## Structured Refresh Comparison",
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
            f"Required narrative: setup, baseline fixture, baseline {CLIENT_LABEL} replies, helper-owned project-state change, refresh {CLIENT_LABEL} replies, revision/service-set change, stale-tool boundary, client-specific session boundary, non-actions, score, verdict.",
        ]
    )


def uc3_compose_service_name(client: str) -> str:
    return "codex-cli-authenticated" if client == "codex" else client


if __name__ == "__main__":
    raise SystemExit(main())
