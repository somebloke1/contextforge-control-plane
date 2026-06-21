#!/usr/bin/env python3
"""Run one comprehensive MCP service test through a real Pi/OpenCode client."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ACTIVATION_PROMPTS = ["hello", "all services", "python", "approve"]


def load_uc1_module() -> Any:
    path = Path(__file__).with_name("run-use-case-1-dialogue.py")
    spec = importlib.util.spec_from_file_location("use_case_1_runner", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_service_map(harness_root: Path) -> dict[str, dict[str, Any]]:
    data = json.loads((harness_root / "comprehensive-mcp-testing-services.json").read_text(encoding="utf-8"))
    return {str(item["slug"]): item for item in data["services"]}


def default_session_id(client: str, service: str, phase: str, timestamp: str) -> str:
    compact = timestamp.lower().replace("t", "").replace("z", "")
    if client == "opencode":
        safe = service.replace("-", "_")
        return f"ses_mcp_{safe}_{phase}_{compact}"
    return f"mcp-{service}-{phase}-{timestamp}"


def service_test_prompt(service: str, display: str, issue: int, global_issue: int) -> str:
    return (
        f"Please comprehensively test the {display} MCP service in this project. "
        "Use the available MCP tools for that service through this assistant session. "
        "Identify the available functions, call every safe read-only or no-op function you can, "
        "skip mutating functions unless there is a safe dry-run, fixture, or no-op target, "
        "and report a concise per-function outcome table. "
        f"If a failure appears shared across services, note that it belongs with issue #{global_issue}; "
        f"if it appears specific to {service}, note that it belongs with issue #{issue}."
    )


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client", choices=["pi", "opencode"], required=True)
    parser.add_argument("--service", required=True)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--no-build", action="store_true")
    args = parser.parse_args(argv)
    if args.timeout < 90:
        raise SystemExit("--timeout must be at least 90 seconds")

    uc1 = load_uc1_module()
    repo_root = Path(__file__).resolve().parents[3]
    harness_root = repo_root / "docker" / "client-harness"
    service_map = load_service_map(harness_root)
    if args.service not in service_map:
        raise SystemExit(f"unknown service {args.service!r}; see comprehensive-mcp-testing-services.json")
    service = service_map[args.service]
    global_issue = 316

    lock_file = uc1.acquire_harness_lock(harness_root)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_root = harness_root / "evidence" / "comprehensive-mcp" / args.service / args.client / timestamp
    output_root.mkdir(parents=True, exist_ok=True)
    container = f"cf-mcp-{args.service[:18].replace('-', '')}-{args.client}-{timestamp.lower().replace('z', '')}"
    activation_session = default_session_id(args.client, args.service, "activate", timestamp)
    test_session = default_session_id(args.client, args.service, "test", timestamp)
    commands: list[dict[str, Any]] = []

    try:
        reset = uc1.run(
            [
                sys.executable,
                str(harness_root / "scripts" / "reset-client-harness-state.py"),
                "--client",
                uc1.reset_client_name(args.client),
                "--reset-home-volume",
                "--evidence-dir",
                "docker/client-harness/evidence/comprehensive-mcp/prior",
            ],
            cwd=repo_root,
            timeout=120,
            commands=commands,
        )
        reset_json = uc1.parse_json_or_text(reset["stdout"])

        local_env = harness_root / "env" / "local-llama.env"
        if not local_env.exists():
            uc1.run([str(harness_root / "scripts" / "make-local-llama-env.sh")], cwd=harness_root, timeout=60, commands=commands)

        build_result = None
        if not args.no_build:
            build_result = uc1.run(
                ["docker", "compose", "-f", str(harness_root / "compose.yml"), "build", "base", uc1.build_service_name(args.client)],
                cwd=repo_root,
                timeout=600,
                commands=commands,
            )

        launch = uc1.run(
            [
                "docker",
                "compose",
                "-f",
                str(harness_root / "compose.yml"),
                "run",
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
        runtime = uc1.run(
            ["docker", "exec", container, "bash", "-lc", uc1.runtime_readback_command(args.client)],
            cwd=repo_root,
            timeout=120,
            commands=commands,
        )

        turns: list[dict[str, Any]] = []
        for index, prompt in enumerate(ACTIVATION_PROMPTS, start=1):
            command = uc1.target_client_command(
                args.client,
                activation_session,
                prompt,
                create_session=args.client == "opencode" and index == 1,
            )
            result = uc1.run(["docker", "exec", container, "bash", "-lc", command], cwd=repo_root, timeout=args.timeout, commands=commands)
            path = output_root / f"activation-turn-{index}.raw.txt"
            path.write_text(uc1.render_command_block(result), encoding="utf-8")
            turns.append({"phase": "activation", "turn": index, "prompt": prompt, "path": str(path), **result})
            if args.client == "opencode" and index == 1:
                discovered = uc1.extract_opencode_session_id(str(result.get("stdout") or ""))
                if discovered:
                    activation_session = discovered

        prompt = service_test_prompt(args.service, str(service["display"]), int(service["issue"]), global_issue)
        command = uc1.target_client_command(
            args.client,
            test_session,
            prompt,
            create_session=args.client == "opencode",
        )
        result = uc1.run(["docker", "exec", container, "bash", "-lc", command], cwd=repo_root, timeout=args.timeout, commands=commands)
        path = output_root / "service-test-turn.raw.txt"
        path.write_text(uc1.render_command_block(result), encoding="utf-8")
        turns.append({"phase": "service_test", "turn": 1, "prompt": prompt, "path": str(path), **result})
        if args.client == "opencode":
            discovered = uc1.extract_opencode_session_id(str(result.get("stdout") or ""))
            if discovered:
                test_session = discovered

        summary = {
            "schema_uri": "contextforge://client-harness/comprehensive-mcp-service-dialogue-run/v1",
            "ok_scope": "runner completed; semantic acceptance requires evaluator review",
            "semantic_acceptance": "requires_non_spark_evaluator",
            "client": args.client,
            "service": args.service,
            "service_issue": service["issue"],
            "global_issue": global_issue,
            "timestamp": timestamp,
            "container": container,
            "activation_session": activation_session,
            "test_session": test_session,
            "output_root": str(output_root),
            "reset": reset_json,
            "build_returncode": None if build_result is None else build_result["returncode"],
            "launch_returncode": launch["returncode"],
            "runtime_returncode": runtime["returncode"],
            "turns": [
                {
                    "phase": turn["phase"],
                    "turn": turn["turn"],
                    "prompt": turn["prompt"],
                    "path": turn["path"],
                    "returncode": turn["returncode"],
                    "timeout": turn["timeout"],
                }
                for turn in turns
            ],
            "command_ledger": commands,
            "deterministic_non_actions": [
                "runner does not score free-form assistant prose",
                "runner does not mutate host/global client config",
                "runner does not call service tools directly outside the tested client",
                "runner does not update GitHub issues or Project fields",
            ],
            "evaluator_required_narrative": [
                "judge whether all safe functions were actually exercised",
                "separate service-specific defects from cross-service wrapper/client defects",
                "triage findings to the service issue or #316",
                "identify any mutating functions skipped with acceptable rationale",
            ],
        }
        write_json(output_root / "run-summary.json", summary)
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0 if all(not turn["timeout"] and turn["returncode"] == 0 for turn in turns) else 1
    finally:
        lock_file.close()


if __name__ == "__main__":
    raise SystemExit(main())
