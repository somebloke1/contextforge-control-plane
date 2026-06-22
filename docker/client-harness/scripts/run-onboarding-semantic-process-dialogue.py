#!/usr/bin/env python3
"""Run one source-lead-only onboarding process dialogue through Pi/OpenCode."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def load_script_module(filename: str, module_name: str) -> Any:
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_scenarios(harness_root: Path) -> dict[str, Any]:
    return json.loads((harness_root / "onboarding-semantic-process-scenarios.json").read_text(encoding="utf-8"))


def foil_record(scenarios: dict[str, Any], foil_id: str) -> dict[str, Any]:
    matches = [foil for foil in scenarios.get("foils", []) if foil.get("id") == foil_id]
    if len(matches) != 1:
        raise RuntimeError(f"expected one onboarding foil {foil_id!r}, found {len(matches)}")
    return matches[0]


def persona_dimensions(scenarios: dict[str, Any]) -> list[dict[str, Any]]:
    dimensions = scenarios.get("persona_sampling", {}).get("dimensions")
    if not isinstance(dimensions, list) or not dimensions:
        raise RuntimeError("scenario package must define persona_sampling.dimensions")
    return [dimension for dimension in dimensions if isinstance(dimension, dict)]


def compose_persona(scenarios: dict[str, Any], *, seed: int | None, index: int) -> dict[str, str]:
    rng = random.Random(None if seed is None else f"{seed}:{index}")
    persona: dict[str, str] = {}
    for dimension in persona_dimensions(scenarios):
        dimension_id = str(dimension["id"])
        values = [str(value) for value in dimension.get("values", [])]
        if not values:
            raise RuntimeError(f"persona dimension {dimension_id!r} has no values")
        persona[dimension_id] = rng.choice(values)
    return persona


def persona_initial_prompt(foil: dict[str, Any], persona: dict[str, str]) -> str:
    source_lead = str(foil["source_lead"])
    goal = persona.get("goal_specificity", "outcome_oriented")
    risk = persona.get("risk_posture", "cautious")
    fluency = persona.get("technical_fluency", "command_comfortable")

    if goal == "vague":
        prompt = f"I want to add this MCP service to the project: {source_lead}"
    elif goal == "detailed_requirements":
        prompt = (
            "I want to onboard a new MCP service from this source lead: "
            f"{source_lead}. Please research it, identify the key decisions, and keep claims bounded."
        )
    else:
        prompt = (
            "I want this project to be able to use the MCP service described here: "
            f"{source_lead}. Please guide the onboarding."
        )

    if risk == "strict_approval_rollback":
        prompt += " Do not make global or irreversible changes without presenting the plan and rollback boundary first."
    elif risk == "cautious":
        prompt += " Please ask before making runtime or client changes."
    if fluency == "nontechnical":
        prompt += " Keep the explanation plain."
    return prompt


def persona_followup_prompt(persona: dict[str, str], turn_index: int) -> str:
    knowledge = persona.get("domain_knowledge", "ignorant")
    risk = persona.get("risk_posture", "cautious")
    style = persona.get("interaction_style", "cooperative")

    if turn_index == 2:
        if knowledge == "ignorant":
            base = "I do not know the implementation details; please decide from the source research."
        elif knowledge == "mcp_contextforge_aware":
            base = "Use the generic ContextForge onboarding process and tell me the decision points before mutation."
        else:
            base = "I can follow commands, but please identify the safe next step and why it is bounded."
    else:
        base = "Continue with the next safe onboarding step, keeping the claim boundary explicit."

    if risk == "strict_approval_rollback":
        base += " Do not mutate runtime, registry, or client state until the approval boundary is explicit."
    elif risk == "cautious":
        base += " Prefer a reversible project-local or dev-harness step."
    if style == "terse":
        base += " Be concise."
    elif style == "demanding":
        base += " Be precise about what is proven and what is not."
    return base


def persona_prompt_sequence(foil: dict[str, Any], persona: dict[str, str], max_turns: int) -> list[str]:
    prompts = [persona_initial_prompt(foil, persona)]
    for index in range(2, max_turns + 1):
        prompts.append(persona_followup_prompt(persona, index))
    return prompts


def read_prompt_file(path: Path) -> list[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not all(isinstance(item, str) and item.strip() for item in data):
        raise RuntimeError("--prompt-file must contain a JSON list of non-empty strings")
    return [str(item) for item in data]


def selected_prompts(args: argparse.Namespace, foil: dict[str, Any], persona: dict[str, str]) -> tuple[list[str], str]:
    prompt_args = list(args.prompt or [])
    if args.prompt_file is not None and prompt_args:
        raise RuntimeError("use either --prompt-file or repeated --prompt, not both")
    if args.prompt_file is not None:
        return read_prompt_file(args.prompt_file), "agent_supplied_prompt_file"
    if prompt_args:
        return prompt_args, "agent_supplied_prompt_sequence"
    return persona_prompt_sequence(foil, persona, args.max_turns), "seeded_default_persona_prompts"


def profile_summary(service_runner: Any, profile: dict[str, Any] | None, env: dict[str, str], secret_keys: list[str], selector: str, available_env: dict[str, str]) -> dict[str, Any]:
    return service_runner.redacted_profile_summary(profile, env, secret_keys, selector, available_env)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client", choices=["pi", "opencode"], required=True)
    parser.add_argument("--foil", default="time")
    parser.add_argument("--timeout", type=int, default=420)
    parser.add_argument("--max-turns", type=int, default=2)
    parser.add_argument(
        "--prompt",
        action="append",
        help=(
            "User prompt from the simulated human responder; repeat to provide an agent-authored "
            "persona-consistent sequence. If omitted, the runner emits a seeded default sequence."
        ),
    )
    parser.add_argument("--prompt-file", type=Path, help="JSON list of agent-authored simulated-human prompts.")
    parser.add_argument("--semantic-model-profile", default=os.environ.get("CONTEXTFORGE_SEMANTIC_MODEL_PROFILE", "random"))
    parser.add_argument("--persona-seed", type=int)
    parser.add_argument("--persona-index", type=int, default=1)
    parser.add_argument("--run-suffix", default="")
    parser.add_argument("--isolation-root", type=Path)
    parser.add_argument("--no-build", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if args.timeout < 90:
        raise SystemExit("--timeout must be at least 90 seconds")
    if args.max_turns < 1:
        raise SystemExit("--max-turns must be at least 1")

    repo_root = Path(__file__).resolve().parents[3]
    harness_root = repo_root / "docker" / "client-harness"
    scenarios = load_scenarios(harness_root)
    foil = foil_record(scenarios, args.foil)
    persona = compose_persona(scenarios, seed=args.persona_seed, index=args.persona_index)
    prompts, responder_mode = selected_prompts(args, foil, persona)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_suffix = "".join(ch.lower() if ch.isalnum() else "-" for ch in args.run_suffix).strip("-")
    run_id = timestamp if not run_suffix else f"{timestamp}-{run_suffix}"
    output_root = harness_root / "evidence" / "onboarding-semantic-process" / args.foil / args.client / run_id
    output_root.mkdir(parents=True, exist_ok=True)

    service_runner = load_script_module("run-comprehensive-mcp-service-dialogue.py", "comprehensive_service_runner")
    uc1 = service_runner.load_uc1_module()
    commands: list[dict[str, Any]] = []
    compose_env: dict[str, str] = {}
    isolated_reset: dict[str, Any] | None = None
    reset_json: Any = None
    lock_file = None

    if not args.dry_run:
        if args.isolation_root is not None:
            compose_env, isolated_reset, _client_scoped_dir = service_runner.prepare_isolated_harness(args, harness_root)
            reset_json = isolated_reset
            commands.append(
                {
                    "command_text": f"isolated-harness-reset {args.isolation_root}",
                    "cwd": str(repo_root),
                    "returncode": 0 if isolated_reset.get("postcondition") else 1,
                    "timeout": False,
                }
            )
        else:
            lock_file = uc1.acquire_harness_lock(harness_root)
            reset = uc1.run(
                [
                    sys.executable,
                    str(harness_root / "scripts" / "reset-client-harness-state.py"),
                    "--client",
                    uc1.reset_client_name(args.client),
                    "--reset-home-volume",
                    "--evidence-dir",
                    "docker/client-harness/evidence/onboarding-semantic-process/prior",
                ],
                cwd=repo_root,
                timeout=120,
                commands=commands,
            )
            reset_json = uc1.parse_json_or_text(reset["stdout"])

        uc1.ensure_semantic_model_env(harness_root, client=args.client, commands=commands, runner=uc1.run)
    semantic_env_file = harness_root / "env" / "semantic-model.env"
    available_model_env = service_runner.read_env(semantic_env_file) if semantic_env_file.exists() else {}
    selected_profile = service_runner.choose_semantic_model_profile(
        harness_root,
        args.client,
        args.semantic_model_profile,
        available_model_env,
    )
    if selected_profile is None:
        semantic_overrides = service_runner.semantic_model_env_overrides()
        selected_secret_env_keys: list[str] = []
    else:
        semantic_overrides, selected_secret_env_keys = service_runner.selected_profile_env(
            selected_profile,
            args.client,
            available_model_env,
        )
    secret_env_keys = sorted(set(selected_secret_env_keys))
    secret_env_keys_to_pass = [key for key in secret_env_keys if os.environ.get(key)]
    semantic_profile = profile_summary(
        service_runner,
        selected_profile,
        semantic_overrides,
        secret_env_keys,
        args.semantic_model_profile,
        available_model_env,
    )

    summary_base = {
        "schema_uri": "contextforge://client-harness/onboarding-semantic-process-dialogue-run/v1",
        "ok_scope": "runner package only; semantic acceptance requires evaluator review",
        "semantic_acceptance": "requires_non_spark_evaluator",
        "deterministic_semantic_oracles_allowed": False,
        "client": args.client,
        "foil": args.foil,
        "source_lead": foil["source_lead"],
        "timestamp": timestamp,
        "run_id": run_id,
        "output_root": str(output_root),
        "persona_seed": args.persona_seed,
        "persona_index": args.persona_index,
        "persona": persona,
        "simulated_human_responder_mode": responder_mode,
        "separate_simulated_human_responder_required": True,
        "prompt_count": len(prompts),
        "prompts": prompts,
        "semantic_model_profile": semantic_profile,
        "reset": reset_json,
        "isolation": isolated_reset,
        "gate_reference": "docker/client-harness/ONBOARDING_SEMANTIC_PROCESS_GATE.md",
        "scenario_reference": "docker/client-harness/onboarding-semantic-process-scenarios.json",
        "deterministic_non_actions": [
            "runner does not score free-form assistant prose",
            "runner does not use Codex as tested assistant",
            "runner default prompts are structural scaffolding, not semantic human-response acceptance",
            "runner does not provide service-specific package names, tool names, bridge commands, or probe payloads",
            "runner does not mutate live legacy ContextForge",
        ],
        "evaluator_required_narrative": [
            "judge whether the tested assistant stayed behind the source-lead-only veil",
            "judge whether persona answers stayed bounded and non-coaching",
            "judge whether implementation decisions and claim boundaries were surfaced",
            "judge whether any target-client-visible list-tools and safe-call claims are proven",
            "classify failures as runner, simulated-human, tested-client, generic-support, model, service-specific, or environment defects",
        ],
    }

    if args.dry_run:
        summary = {**summary_base, "dry_run": True, "turns": [], "command_ledger": commands}
        write_json(output_root / "run-summary.json", summary)
        print(json.dumps(summary, indent=2, sort_keys=True))
        if lock_file is not None:
            lock_file.close()
        return 0

    build_result = None
    if not args.no_build:
        build_result = uc1.run(
            ["docker", "compose", "-f", str(harness_root / "compose.yml"), "build", "base", uc1.build_service_name(args.client)],
            cwd=repo_root,
            timeout=600,
            commands=commands,
            env=compose_env or None,
        )

    container_run_id = run_id.lower().replace("z", "").replace("_", "-")
    container = f"cf-onboard-{args.foil[:10]}-{args.client}-{container_run_id}"
    launch_command = [
        "docker",
        "compose",
        "-f",
        str(harness_root / "compose.yml"),
        "run",
        "--name",
        container,
        "--no-deps",
        "-d",
    ]
    for key, value in sorted(semantic_overrides.items()):
        launch_command.extend(["-e", f"{key}={value}"])
    for key in secret_env_keys_to_pass:
        launch_command.extend(["-e", key])
    launch_command.extend([uc1.compose_service_name(args.client), "sleep", "infinity"])
    launch = uc1.run(launch_command, cwd=repo_root, timeout=120, commands=commands, env=compose_env or None)
    runtime = uc1.run(
        ["docker", "exec", container, "bash", "-lc", uc1.runtime_readback_command(args.client)],
        cwd=repo_root,
        timeout=120,
        commands=commands,
    )

    session_id = f"onboarding-{args.foil}-{args.client}-{run_id}"
    turns: list[dict[str, Any]] = []
    for index, prompt in enumerate(prompts, start=1):
        command = uc1.target_client_command(
            args.client,
            session_id,
            prompt,
            create_session=args.client == "opencode" and index == 1,
        )
        result = uc1.run(["docker", "exec", container, "bash", "-lc", command], cwd=repo_root, timeout=args.timeout, commands=commands)
        if args.client == "opencode" and index == 1:
            discovered = uc1.extract_opencode_session_id(str(result.get("stdout") or ""))
            if discovered:
                session_id = discovered
        path = output_root / f"turn-{index}.raw.txt"
        path.write_text(uc1.render_command_block(result), encoding="utf-8")
        turns.append(
            {
                "turn": index,
                "prompt": prompt,
                "path": str(path),
                "returncode": result["returncode"],
                "timeout": result["timeout"],
            }
        )

    summary = {
        **summary_base,
        "dry_run": False,
        "container": container,
        "session_id": session_id,
        "build_returncode": None if build_result is None else build_result["returncode"],
        "launch_returncode": launch["returncode"],
        "runtime_returncode": runtime["returncode"],
        "turns": turns,
        "command_ledger": commands,
    }
    write_json(output_root / "run-summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    if lock_file is not None:
        lock_file.close()
    ok = launch["returncode"] == 0 and runtime["returncode"] == 0 and all(not turn["timeout"] and turn["returncode"] == 0 for turn in turns)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
