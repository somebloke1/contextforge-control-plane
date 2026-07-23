#!/usr/bin/env python3
"""Run one comprehensive MCP slice across a quorum of semantic model profiles."""

from __future__ import annotations

import argparse
import concurrent.futures
import importlib.util
import json
import os
import random
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MIN_MODEL_QUORUM = 3


def load_dialogue_runner() -> Any:
    path = Path(__file__).with_name("run-comprehensive-mcp-service-dialogue.py")
    spec = importlib.util.spec_from_file_location("comprehensive_mcp_service_dialogue", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def select_profiles(
    dialogue: Any,
    harness_root: Path,
    client: str,
    available_env: dict[str, str],
    requested: list[str],
    count: int,
    seed: int | None,
) -> list[dict[str, Any]]:
    eligible = [
        profile
        for profile in dialogue.load_semantic_model_profiles(harness_root)
        if dialogue.profile_supports_client(profile, client)
        and dialogue.profile_available(profile, available_env)
        and dialogue.profile_context_window(profile) >= dialogue.MIN_SEMANTIC_CONTEXT_WINDOW
        and dialogue.profile_multi_step_quorum_eligible(profile)
        and dialogue.profile_weight(profile) > 0
    ]
    by_id = {str(profile.get("id") or ""): profile for profile in eligible}
    if requested:
        missing = [profile_id for profile_id in requested if profile_id not in by_id]
        if missing:
            raise RuntimeError(f"requested profiles are not eligible for {client}: {', '.join(missing)}")
        selected = [by_id[profile_id] for profile_id in requested]
    else:
        if len(eligible) < count:
            raise RuntimeError(f"need {count} eligible profiles for {client}; found {len(eligible)}")
        rng = random.Random(seed)
        selected = rng.sample(eligible, count)
    ids = [str(profile.get("id") or "") for profile in selected]
    if len(set(ids)) != len(ids):
        raise RuntimeError("semantic model quorum requires distinct profile ids")
    if len(selected) < MIN_MODEL_QUORUM:
        raise RuntimeError(f"semantic model quorum requires at least {MIN_MODEL_QUORUM} profiles")
    return selected


def parse_summary(stdout: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def profile_record(dialogue: Any, profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "profile_id": profile.get("id"),
        "provider_kind": profile.get("provider_kind"),
        "provider_label": profile.get("provider_label"),
        "model": profile.get("model"),
        "context_window": dialogue.profile_context_window(profile),
        "route_preferences": dialogue.route_preferences(profile),
        "multi_step_quorum_eligible": dialogue.profile_multi_step_quorum_eligible(profile),
        "usage_modes": profile.get("usage_modes"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client", choices=["pi", "opencode"], required=True)
    parser.add_argument("--service", required=True)
    parser.add_argument("--timeout", type=int, default=420)
    parser.add_argument("--count", type=int, default=MIN_MODEL_QUORUM)
    parser.add_argument("--profile", action="append", default=[], help="Explicit profile id; repeat for quorum.")
    parser.add_argument("--seed", type=int, default=None, help="Optional random seed for reproducible selection.")
    parser.add_argument("--jobs", type=int, default=0, help="Concurrent profile runs; default is one job per selected profile.")
    parser.add_argument("--no-build", action="store_true")
    parser.add_argument(
        "--service-test-prompt",
        help="Override the default natural service-test prompt for each model-profile run.",
    )
    parser.add_argument("--contextforge-host-base-url", default=os.environ.get("CONTEXTFORGE_HOST_BASE_URL"))
    parser.add_argument("--contextforge-container-base-url", default=os.environ.get("CONTEXTFORGE_CONTAINER_BASE_URL"))
    parser.add_argument(
        "--contextforge-env-file",
        type=Path,
        default=Path(os.environ["CONTEXTFORGE_DEV_ENV_FILE"]) if os.environ.get("CONTEXTFORGE_DEV_ENV_FILE") else None,
    )
    args = parser.parse_args(argv)

    if args.count < MIN_MODEL_QUORUM:
        raise SystemExit(f"--count must be at least {MIN_MODEL_QUORUM}")
    if args.profile and len(args.profile) < MIN_MODEL_QUORUM:
        raise SystemExit(f"provide at least {MIN_MODEL_QUORUM} --profile values")

    dialogue = load_dialogue_runner()
    uc1 = dialogue.load_uc1_module()
    repo_root = Path(__file__).resolve().parents[3]
    harness_root = repo_root / "docker" / "client-harness"
    service_map = dialogue.load_service_map(harness_root)
    if args.service not in service_map:
        raise SystemExit(f"unknown service {args.service!r}; see comprehensive-mcp-testing-services.json")

    semantic_env_file = harness_root / "env" / "semantic-model.env"
    if not semantic_env_file.exists():
        raise SystemExit(f"{semantic_env_file} is missing; run docker/client-harness/scripts/make-semantic-model-env.sh")
    available_env = dialogue.read_env(semantic_env_file)
    profiles = select_profiles(
        dialogue,
        harness_root,
        args.client,
        available_env,
        args.profile,
        args.count,
        args.seed,
    )

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_root = harness_root / "evidence" / "comprehensive-mcp-quorum" / args.service / args.client / timestamp
    output_root.mkdir(parents=True, exist_ok=True)
    jobs = args.jobs or len(profiles)
    if jobs < 1:
        raise SystemExit("--jobs must be at least 1")

    prebuild: dict[str, Any] | None = None
    if not args.no_build:
        build_command = [
            "docker",
            "compose",
            "-f",
            str(harness_root / "compose.yml"),
            "build",
            "base",
            uc1.build_service_name(args.client),
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
                "schema_uri": "contextforge://client-harness/comprehensive-mcp-model-quorum/v1",
                "ok_scope": "structural model-quorum execution package only",
                "semantic_acceptance": "requires_non_spark_evaluator_per_model_and_quorum",
                "quorum_status": "prebuild_failed",
                "minimum_model_quorum": MIN_MODEL_QUORUM,
                "client": args.client,
                "service": args.service,
                "service_issue": service_map[args.service]["issue"],
                "global_issue": service_map.get("global_issue", 316),
                "timestamp": timestamp,
                "output_root": str(output_root),
                "prebuild": prebuild,
                "selected_profiles": [profile_record(dialogue, profile) for profile in profiles],
                "completed_profile_count": 0,
                "runs": [],
            }
            write_json(output_root / "quorum-summary.json", summary)
            print(json.dumps(summary, indent=2, sort_keys=True))
            return 1

    def run_profile(index: int, profile: dict[str, Any]) -> dict[str, Any]:
        profile_id = str(profile["id"])
        command = [
            sys.executable,
            str(harness_root / "scripts" / "run-comprehensive-mcp-service-dialogue.py"),
            "--client",
            args.client,
            "--service",
            args.service,
            "--timeout",
            str(args.timeout),
            "--semantic-model-profile",
            profile_id,
        ]
        run_suffix = f"{index:02d}-{profile_id}"
        command.extend(["--run-suffix", run_suffix])
        command.append("--no-build")
        if jobs > 1:
            command.extend(["--isolation-root", str(output_root / "isolated" / run_suffix)])
        if args.contextforge_host_base_url:
            command.extend(["--contextforge-host-base-url", args.contextforge_host_base_url])
        if args.contextforge_container_base_url:
            command.extend(["--contextforge-container-base-url", args.contextforge_container_base_url])
        if args.contextforge_env_file is not None:
            command.extend(["--contextforge-env-file", str(args.contextforge_env_file)])
        if args.service_test_prompt:
            command.extend(["--service-test-prompt", args.service_test_prompt])

        result = subprocess.run(command, cwd=repo_root, text=True, capture_output=True, timeout=args.timeout + 180)
        stdout_path = output_root / f"{index:02d}-{profile_id}.stdout.json"
        stderr_path = output_root / f"{index:02d}-{profile_id}.stderr.txt"
        stdout_path.write_text(result.stdout, encoding="utf-8")
        stderr_path.write_text(result.stderr, encoding="utf-8")
        run_summary = parse_summary(result.stdout)
        run_record = {
            "index": index,
            "profile": profile_record(dialogue, profile),
            "returncode": result.returncode,
            "stdout_path": str(stdout_path),
            "stderr_path": str(stderr_path),
            "dialogue_output_root": None if run_summary is None else run_summary.get("output_root"),
            "dialogue_run_summary": None
            if run_summary is None or not run_summary.get("output_root")
            else str(Path(str(run_summary["output_root"])) / "run-summary.json"),
            "dialogue_semantic_acceptance": None if run_summary is None else run_summary.get("semantic_acceptance"),
            "dialogue_ok_scope": None if run_summary is None else run_summary.get("ok_scope"),
            "service_test_executed": None if run_summary is None else run_summary.get("service_test_executed"),
            "run_suffix": run_suffix,
            "isolation_root": None if jobs <= 1 else str(output_root / "isolated" / run_suffix),
        }
        return run_record

    if jobs == 1:
        runs = [run_profile(index, profile) for index, profile in enumerate(profiles, start=1)]
    else:
        runs_by_index: dict[int, dict[str, Any]] = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(jobs, len(profiles))) as executor:
            futures = {
                executor.submit(run_profile, index, profile): index
                for index, profile in enumerate(profiles, start=1)
            }
            for future in concurrent.futures.as_completed(futures):
                index = futures[future]
                runs_by_index[index] = future.result()
        runs = [runs_by_index[index] for index in sorted(runs_by_index)]

    completed = [run for run in runs if run["returncode"] == 0 and run["dialogue_run_summary"]]
    summary = {
        "schema_uri": "contextforge://client-harness/comprehensive-mcp-model-quorum/v1",
        "ok_scope": "structural model-quorum execution package only",
        "semantic_acceptance": "requires_non_spark_evaluator_per_model_and_quorum",
        "quorum_status": "ready_for_evaluator" if len(completed) >= MIN_MODEL_QUORUM else "quorum_run_incomplete",
        "minimum_model_quorum": MIN_MODEL_QUORUM,
        "client": args.client,
        "service": args.service,
        "service_issue": service_map[args.service]["issue"],
        "global_issue": service_map.get("global_issue", 316),
        "timestamp": timestamp,
        "output_root": str(output_root),
        "execution_mode": "parallel_isolated" if jobs > 1 else "sequential",
        "jobs": jobs,
        "prebuild": prebuild,
        "selected_profiles": [profile_record(dialogue, profile) for profile in profiles],
        "service_test_prompt_override_used": bool(args.service_test_prompt),
        "completed_profile_count": len(completed),
        "runs": runs,
        "deterministic_non_actions": [
            "quorum runner does not score free-form assistant prose",
            "quorum runner does not hide failed model-profile runs",
            "quorum runner varies only semantic model profile across runs",
        ],
        "evaluator_required_narrative": [
            "judge each model run for client-visible ContextForge tool route use",
            "classify every failed profile before replacement or acceptance",
            "accept quorum only if at least three distinct eligible profiles pass semantically",
        ],
    }
    write_json(output_root / "quorum-summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if len(completed) >= MIN_MODEL_QUORUM else 1


if __name__ == "__main__":
    raise SystemExit(main())
