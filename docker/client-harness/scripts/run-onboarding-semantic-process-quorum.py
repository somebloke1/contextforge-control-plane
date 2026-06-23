#!/usr/bin/env python3
"""Run onboarding semantic-process dialogue across model/persona quorum."""

from __future__ import annotations

import argparse
import concurrent.futures
import importlib.util
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MIN_MODEL_QUORUM = 3
DEFAULT_ONBOARDING_TURNS = 32
DEFAULT_DIALOGUE_SECONDS = 600
DEFAULT_HUMAN_HELP_DETERMINATION = 15
TURN_BUDGET_POLICY = (
    "capture each live interaction without evaluator calls until it reaches a "
    "completion point or safety bound; default safety bounds are 32 turns or "
    "600 seconds, after which a semantic evaluator reviews every turn and the "
    "whole session from the completed evidence package"
)


def load_script_module(filename: str, module_name: str) -> Any:
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def profile_record(service_runner: Any, profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "profile_id": profile.get("id"),
        "provider_kind": profile.get("provider_kind"),
        "provider_label": profile.get("provider_label"),
        "model": profile.get("model"),
        "context_window": service_runner.profile_context_window(profile),
        "route_preferences": service_runner.route_preferences(profile),
        "multi_step_quorum_eligible": service_runner.profile_multi_step_quorum_eligible(profile),
        "usage_modes": profile.get("usage_modes"),
    }


def select_profiles(
    service_runner: Any,
    harness_root: Path,
    client: str,
    requested: list[str],
    count: int,
    seed: int | None,
) -> list[dict[str, Any]]:
    semantic_env_file = harness_root / "env" / "semantic-model.env"
    if not semantic_env_file.exists():
        raise RuntimeError(f"{semantic_env_file} is missing; run make-semantic-model-env.sh")
    available_env = service_runner.read_env(semantic_env_file)
    profiles = [
        profile
        for profile in service_runner.load_semantic_model_profiles(harness_root)
        if service_runner.profile_supports_client(profile, client)
        and service_runner.profile_available(profile, available_env)
        and service_runner.profile_context_window(profile) >= service_runner.MIN_SEMANTIC_CONTEXT_WINDOW
        and service_runner.profile_multi_step_quorum_eligible(profile)
        and service_runner.profile_weight(profile) > 0
    ]
    by_id = {str(profile.get("id") or ""): profile for profile in profiles}
    if requested:
        missing = [profile_id for profile_id in requested if profile_id not in by_id]
        if missing:
            raise RuntimeError(f"requested profiles are not eligible for {client}: {', '.join(missing)}")
        selected = [by_id[profile_id] for profile_id in requested]
    else:
        import random

        if len(profiles) < count:
            raise RuntimeError(f"need {count} eligible profiles for {client}; found {len(profiles)}")
        selected = random.Random(seed).sample(profiles, count)
    ids = [str(profile.get("id") or "") for profile in selected]
    if len(set(ids)) != len(ids):
        raise RuntimeError("onboarding semantic model quorum requires distinct profile ids")
    if len(selected) < MIN_MODEL_QUORUM:
        raise RuntimeError(f"onboarding semantic model quorum requires at least {MIN_MODEL_QUORUM} profiles")
    return selected


def persona_coverage(personas: list[dict[str, str]]) -> dict[str, Any]:
    knowledge_values = {persona.get("domain_knowledge") for persona in personas}
    risk_values = {persona.get("risk_posture") for persona in personas}
    has_low_knowledge = "ignorant" in knowledge_values
    has_higher_knowledge = bool({"generally_technical", "mcp_contextforge_aware"} & knowledge_values)
    has_two_risks = len(risk_values) >= 2
    return {
        "has_low_knowledge": has_low_knowledge,
        "has_higher_knowledge": has_higher_knowledge,
        "risk_posture_count": len(risk_values),
        "ready_for_acceptance_matrix": bool(has_low_knowledge and has_higher_knowledge and has_two_risks),
    }


def select_persona_indices(dialogue: Any, scenarios: dict[str, Any], count: int, seed: int | None) -> list[int]:
    # Keep random composition per run, but search deterministic index space until
    # the sampled set covers the minimum acceptance dimensions.
    max_attempts = 1000
    start = 1 if seed is None else abs(seed) % 997 + 1
    for offset in range(max_attempts):
        indices = [start + offset * count + index for index in range(count)]
        personas = [dialogue.compose_persona(scenarios, seed=seed, index=index) for index in indices]
        if persona_coverage(personas)["ready_for_acceptance_matrix"]:
            return indices
    raise RuntimeError("could not sample persona indices satisfying onboarding coverage requirements")


def parse_summary(stdout: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def dialogue_summary_acceptance_eligible(summary: dict[str, Any] | None) -> bool:
    eligibility = summary.get("acceptance_matrix_eligibility") if isinstance(summary, dict) else None
    return bool(isinstance(eligibility, dict) and eligibility.get("eligible") is True)


def bounded_help_determination(value: int) -> int:
    return max(1, min(20, int(value)))


def structural_onboarding_successful(summary: dict[str, Any] | None) -> bool:
    if not isinstance(summary, dict):
        return False
    proof = summary.get("structural_onboarding_proof")
    if not isinstance(proof, dict):
        return False
    runtime = proof.get("runtime_apply")
    post_apply = proof.get("post_apply_target_client_evidence")
    if not isinstance(runtime, dict) or not isinstance(post_apply, dict):
        return False
    return bool(
        runtime.get("success_detected") is True
        and post_apply.get("fresh_session_after_runtime_apply_detected") is True
        and post_apply.get("candidate_target_client_service_tool_call_detected") is True
    )


def next_batch_help_determination(current: int, *, failure_count: int) -> int:
    current = bounded_help_determination(current)
    if failure_count <= 0:
        return bounded_help_determination(current - 1)
    if failure_count == 1:
        return current
    if failure_count == 2:
        return bounded_help_determination(current + 1)
    return bounded_help_determination(current + 2)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client", choices=["pi", "opencode"], required=True)
    parser.add_argument("--foil", default="time")
    parser.add_argument("--timeout", type=int, default=420)
    parser.add_argument("--count", type=int, default=MIN_MODEL_QUORUM)
    parser.add_argument("--profile", action="append", default=[])
    parser.add_argument("--seed", type=int)
    parser.add_argument("--jobs", type=int, default=0)
    parser.add_argument("--max-turns", type=int, default=DEFAULT_ONBOARDING_TURNS)
    parser.add_argument("--max-dialogue-seconds", type=int, default=DEFAULT_DIALOGUE_SECONDS)
    parser.add_argument(
        "--human-help-determination-start",
        type=int,
        default=int(os.environ.get("CONTEXTFORGE_HUMAN_HELP_DETERMINATION_START", DEFAULT_HUMAN_HELP_DETERMINATION)),
        help="Starting simulated-human determination to help, from 1 to 20. Defaults to 15/20.",
    )
    parser.add_argument(
        "--disable-adaptive-human-help-determination",
        action="store_true",
        help="Disable next-batch n adjustment from the prior three-model quorum outcome.",
    )
    parser.add_argument(
        "--responder-mode",
        choices=["pi", "model", "seeded"],
        default="pi",
        help="Use Pi gpt-5.5 simulated human responders by default; seeded mode is debug scaffolding.",
    )
    parser.add_argument("--responder-pi-image", default=os.environ.get("CONTEXTFORGE_PI_HUMAN_SIM_IMAGE", "contextforge-client-pi:human-sim-authenticated"))
    parser.add_argument("--responder-pi-provider", default=os.environ.get("CONTEXTFORGE_PI_HUMAN_SIM_PROVIDER", "openai-codex"))
    parser.add_argument("--responder-pi-model", default=os.environ.get("CONTEXTFORGE_PI_HUMAN_SIM_MODEL", "gpt-5.5"))
    parser.add_argument(
        "--responder-pi-thinking",
        choices=["off", "minimal", "low", "medium", "high", "xhigh"],
        default=os.environ.get("CONTEXTFORGE_PI_HUMAN_SIM_THINKING", "low"),
    )
    parser.add_argument("--no-build", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if args.count < MIN_MODEL_QUORUM:
        raise SystemExit(f"--count must be at least {MIN_MODEL_QUORUM}")
    if args.profile and len(args.profile) < MIN_MODEL_QUORUM:
        raise SystemExit(f"provide at least {MIN_MODEL_QUORUM} --profile values")
    args.human_help_determination_start = bounded_help_determination(args.human_help_determination_start)

    repo_root = Path(__file__).resolve().parents[3]
    harness_root = repo_root / "docker" / "client-harness"
    service_runner = load_script_module("run-comprehensive-mcp-service-dialogue.py", "comprehensive_service_runner")
    dialogue = load_script_module("run-onboarding-semantic-process-dialogue.py", "onboarding_semantic_dialogue")
    scenarios = dialogue.load_scenarios(harness_root)
    foil = dialogue.foil_record(scenarios, args.foil)
    profiles = select_profiles(service_runner, harness_root, args.client, args.profile, args.count, args.seed)
    persona_indices = select_persona_indices(dialogue, scenarios, len(profiles), args.seed)
    personas = [dialogue.compose_persona(scenarios, seed=args.seed, index=index) for index in persona_indices]
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_root = harness_root / "evidence" / "onboarding-semantic-process-quorum" / args.foil / args.client / timestamp
    output_root.mkdir(parents=True, exist_ok=True)
    jobs = args.jobs or len(profiles)

    prebuild: dict[str, Any] | None = None
    if not args.no_build and not args.dry_run:
        build_command = [
            "docker",
            "compose",
            "-f",
            str(harness_root / "compose.yml"),
            "build",
            "base",
            service_runner.load_uc1_module().build_service_name(args.client),
        ]
        build_result = subprocess.run(build_command, cwd=repo_root, text=True, capture_output=True, timeout=600)
        prebuild = {
            "command": " ".join(build_command),
            "returncode": build_result.returncode,
            "stdout_path": str(output_root / "prebuild.stdout.txt"),
            "stderr_path": str(output_root / "prebuild.stderr.txt"),
        }
        (output_root / "prebuild.stdout.txt").write_text(build_result.stdout, encoding="utf-8")
        (output_root / "prebuild.stderr.txt").write_text(build_result.stderr, encoding="utf-8")
        if build_result.returncode != 0:
            summary = {
                "schema_uri": "contextforge://client-harness/onboarding-semantic-process-quorum/v1",
                "ok_scope": "structural onboarding process quorum package only",
                "semantic_acceptance": "requires_non_spark_evaluator_per_model_and_quorum",
                "quorum_status": "prebuild_failed",
                "client": args.client,
                "foil": args.foil,
                "source_lead": foil["source_lead"],
                "output_root": str(output_root),
                "prebuild": prebuild,
                "runs": [],
            }
            write_json(output_root / "quorum-summary.json", summary)
            print(json.dumps(summary, indent=2, sort_keys=True))
            return 1

    def run_profile(index: int, profile: dict[str, Any], persona_index: int, help_determination: int) -> dict[str, Any]:
        profile_id = str(profile["id"])
        run_suffix = f"{index:02d}-{profile_id}-persona-{persona_index}"
        command = [
            sys.executable,
            str(harness_root / "scripts" / "run-onboarding-semantic-process-dialogue.py"),
            "--client",
            args.client,
            "--foil",
            args.foil,
            "--timeout",
            str(args.timeout),
            "--max-turns",
            str(args.max_turns),
            "--max-dialogue-seconds",
            str(args.max_dialogue_seconds),
            "--responder-mode",
            args.responder_mode,
            "--responder-pi-image",
            args.responder_pi_image,
            "--responder-pi-provider",
            args.responder_pi_provider,
            "--responder-pi-model",
            args.responder_pi_model,
            "--responder-pi-thinking",
            args.responder_pi_thinking,
            "--human-help-determination",
            str(help_determination),
            "--semantic-model-profile",
            profile_id,
            "--persona-index",
            str(persona_index),
            "--run-suffix",
            run_suffix,
            "--isolation-root",
            str(output_root / "isolated" / run_suffix),
        ]
        if args.seed is not None:
            command.extend(["--persona-seed", str(args.seed)])
        command.append("--no-build")
        if args.dry_run:
            command.append("--dry-run")
        result = subprocess.run(command, cwd=repo_root, text=True, capture_output=True, timeout=args.timeout + 180)
        stdout_path = output_root / f"{index:02d}-{profile_id}.stdout.json"
        stderr_path = output_root / f"{index:02d}-{profile_id}.stderr.txt"
        stdout_path.write_text(result.stdout, encoding="utf-8")
        stderr_path.write_text(result.stderr, encoding="utf-8")
        run_summary = parse_summary(result.stdout)
        acceptance_matrix_eligible = dialogue_summary_acceptance_eligible(run_summary)
        onboarding_successful = structural_onboarding_successful(run_summary)
        return {
            "index": index,
            "profile": profile_record(service_runner, profile),
            "persona_index": persona_index,
            "persona": dialogue.compose_persona(scenarios, seed=args.seed, index=persona_index),
            "human_help_determination": help_determination,
            "structural_onboarding_successful": onboarding_successful,
            "returncode": result.returncode,
            "acceptance_matrix_eligible": acceptance_matrix_eligible,
            "acceptance_matrix_eligibility": None if run_summary is None else run_summary.get("acceptance_matrix_eligibility"),
            "stdout_path": str(stdout_path),
            "stderr_path": str(stderr_path),
            "dialogue_output_root": None if run_summary is None else run_summary.get("output_root"),
            "dialogue_run_summary": None
            if run_summary is None or not run_summary.get("output_root")
            else str(Path(str(run_summary["output_root"])) / "run-summary.json"),
            "run_suffix": run_suffix,
        }

    adaptive_help = not args.disable_adaptive_human_help_determination
    batch_help = args.human_help_determination_start
    if args.dry_run or jobs == 1:
        runs = []
        for index, profile in enumerate(profiles, start=1):
            run = run_profile(index, profile, persona_indices[index - 1], batch_help)
            runs.append(run)
    else:
        runs_by_index: dict[int, dict[str, Any]] = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(jobs, len(profiles))) as executor:
            futures = {
                executor.submit(run_profile, index, profile, persona_indices[index - 1], batch_help): index
                for index, profile in enumerate(profiles, start=1)
            }
            for future in concurrent.futures.as_completed(futures):
                index = futures[future]
                runs_by_index[index] = future.result()
        runs = [runs_by_index[index] for index in sorted(runs_by_index)]

    structurally_successful_runs = [run for run in runs if run.get("structural_onboarding_successful")]
    structural_failure_count = max(0, MIN_MODEL_QUORUM - min(len(structurally_successful_runs), MIN_MODEL_QUORUM))
    next_batch_help = (
        batch_help
        if args.dry_run or not adaptive_help
        else next_batch_help_determination(batch_help, failure_count=structural_failure_count)
    )
    successful = [run for run in runs if run["returncode"] == 0 and run["dialogue_run_summary"]]
    completed = [run for run in successful if run.get("acceptance_matrix_eligible")]
    coverage = persona_coverage([run["persona"] for run in runs])
    if args.dry_run:
        quorum_status = "dry_run_structural_package_only"
    elif len(completed) >= MIN_MODEL_QUORUM and coverage["ready_for_acceptance_matrix"]:
        quorum_status = "ready_for_evaluator"
    else:
        quorum_status = "quorum_run_incomplete"
    summary = {
        "schema_uri": "contextforge://client-harness/onboarding-semantic-process-quorum/v1",
        "ok_scope": "structural onboarding process quorum package only",
        "semantic_acceptance": "requires_non_spark_evaluator_per_model_and_quorum",
        "deterministic_semantic_oracles_allowed": False,
        "quorum_status": quorum_status,
        "minimum_model_quorum_per_client": MIN_MODEL_QUORUM,
        "client": args.client,
        "foil": args.foil,
        "source_lead": foil["source_lead"],
        "timestamp": timestamp,
        "output_root": str(output_root),
        "execution_mode": "parallel_isolated" if jobs > 1 and not args.dry_run else "sequential_or_dry_run",
        "jobs": jobs,
        "prebuild": prebuild,
        "selected_profiles": [profile_record(service_runner, profile) for profile in profiles],
        "persona_seed": args.seed,
        "persona_indices": persona_indices,
        "persona_coverage": coverage,
        "default_turn_budget": DEFAULT_ONBOARDING_TURNS,
        "default_dialogue_seconds": DEFAULT_DIALOGUE_SECONDS,
        "configured_max_turns": args.max_turns,
        "configured_max_dialogue_seconds": args.max_dialogue_seconds,
        "human_help_determination_policy": {
            "start": args.human_help_determination_start,
            "this_batch": batch_help,
            "structural_failure_count_for_first_three": structural_failure_count,
            "next_batch": next_batch_help,
            "scale": "n/20",
            "adaptive": adaptive_help,
            "adjustment_rules": {
                "all_three_fail": "+2 for all human simulators in the next quorum run",
                "two_fail": "+1 for all human simulators in the next quorum run",
                "one_fails": "no change for the next quorum run",
                "all_three_succeed": "-1 for all human simulators in the next quorum run",
            },
            "bounds": "ratings are clamped to 1..20",
            "parallel_note": "all runs in the same quorum batch receive this_batch rating; adaptation applies to the next batch",
        },
        "structural_onboarding_successful_count": len(structurally_successful_runs),
        "responder_mode": args.responder_mode,
        "turn_budget_policy": TURN_BUDGET_POLICY,
        "successful_profile_count": len(successful),
        "eligible_completed_profile_count": len(completed),
        "completed_profile_count": len(completed),
        "real_dialogue_completed_profile_count": 0 if args.dry_run else len(completed),
        "runs": runs,
        "deterministic_non_actions": [
            "quorum runner does not score free-form assistant prose",
            "quorum runner does not use Codex as tested assistant",
            "quorum runner does not hide failed model-profile or persona runs",
            "quorum runner varies model profile and persona across isolated runs",
        ],
        "evaluator_required_narrative": [
            "after each live dialogue ends or hits a safety bound, evaluate every user/assistant turn and the whole session in one after-action review",
            "judge each client/model/persona run behind the source-lead-only veil",
            "accept quorum only if at least three distinct eligible profiles pass semantically",
            "judge interaction efficiency relative to each sampled persona overhead and required outcome",
            "classify every failed run before replacement or acceptance",
            "aggregate persona coverage and route/claim-boundary findings",
        ],
    }
    write_json(output_root / "quorum-summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if len(completed) >= MIN_MODEL_QUORUM and coverage["ready_for_acceptance_matrix"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
