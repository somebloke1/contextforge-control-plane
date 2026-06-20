#!/usr/bin/env python3
"""Verify Use Case 5f ssh-tmux lifecycle evidence structure."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REQUIRED_ISSUE_KEYS = {"issue_247", "issue_266", "issue_259", "issue_260", "issue_263", "issue_264", "issue_270", "pr_271"}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def check(condition: bool, checks: dict[str, bool], failures: list[str], name: str) -> None:
    checks[name] = bool(condition)
    if not condition:
        failures.append(name)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    args = parser.parse_args(argv)

    metadata = load_json(args.metadata)
    repo_root = Path(metadata["repo_root"])
    matrix = load_json(repo_root / metadata["artifacts"]["readiness_matrix"])
    taxonomy = load_json(repo_root / metadata["artifacts"]["taxonomy_contract"])
    manifest = load_json(repo_root / metadata["artifacts"]["ssh_tmux_manifest"])
    services = matrix.get("services", [])
    ssh_rows = [item for item in services if item.get("service") == "ssh-tmux"]
    ssh_tmux = ssh_rows[0] if len(ssh_rows) == 1 else {}
    taxonomy_types = {item.get("id") for item in taxonomy.get("types", [])}
    non_actions = set(ssh_tmux.get("blockers_or_non_actions") or [])
    checks: dict[str, bool] = {}
    failures: list[str] = []

    check(args.evidence.exists() and args.evidence.stat().st_size > 0, checks, failures, "evidence_file_nonempty")
    check(args.metadata.exists() and args.metadata.stat().st_size > 0, checks, failures, "metadata_file_nonempty")
    check(metadata.get("use_case") == "use-case-5f-ssh-tmux", checks, failures, "metadata_use_case")
    check(metadata.get("semantic_acceptance") == "requires_agent_evaluation", checks, failures, "semantic_acceptance_declared")
    check(metadata.get("deterministic_boundary") == "structured_source_artifacts_only", checks, failures, "deterministic_boundary_declared")
    check(set(metadata.get("github_context", {})) >= REQUIRED_ISSUE_KEYS, checks, failures, "github_context_covers_required_items")
    check(
        all(item.get("state") and item.get("title") and item.get("body") for item in metadata.get("github_context", {}).values()),
        checks,
        failures,
        "github_context_has_bodies",
    )
    check(len(ssh_rows) == 1, checks, failures, "single_ssh_tmux_matrix_row")
    check(ssh_tmux.get("owner_issue") == 266, checks, failures, "ssh_tmux_owner_issue")
    check(ssh_tmux.get("taxonomy_type") == "session_scoped", checks, failures, "ssh_tmux_taxonomy_type")
    check(ssh_tmux.get("taxonomy_type") in taxonomy_types, checks, failures, "ssh_tmux_taxonomy_type_known")
    check(ssh_tmux.get("service_binding") == "ssh-tmux:session_scoped", checks, failures, "ssh_tmux_binding")
    check(ssh_tmux.get("safe_probe_status") == "known_safe_probe", checks, failures, "known_safe_probe_status")
    check(
        {"no opening sessions", "no command or key sending", "no remote file mutation", "no cleanup or close operations"} <= non_actions,
        checks,
        failures,
        "ssh_tmux_non_actions_present",
    )
    check(manifest.get("scope", {}).get("scope_type") == "ssh_target_and_tmux_session", checks, failures, "manifest_session_scope")
    check("ssh-tmux-open-session" in manifest.get("registration", {}).get("registered_tools", []), checks, failures, "manifest_exposes_mutating_tools")
    check(metadata.get("test_command", {}).get("returncode") == 0, checks, failures, "focused_lifecycle_test_passed")
    test_output = (
        metadata.get("test_command", {}).get("stdout", "")
        + "\n"
        + metadata.get("test_command", {}).get("stderr", "")
    )
    check(
        "test_ssh_tmux_pi_lifecycle_writes_only_project_state_and_stops_for_reload" in test_output,
        checks,
        failures,
        "pi_lifecycle_test_executed",
    )
    check(
        "test_ssh_tmux_opencode_lifecycle_writes_project_config_state_and_stops_for_new_session" in test_output,
        checks,
        failures,
        "opencode_lifecycle_test_executed",
    )
    check(
        all((repo_root / path).exists() for path in metadata.get("artifacts", {}).values()),
        checks,
        failures,
        "declared_artifacts_exist",
    )

    result = {
        "ok": not failures,
        "use_case": "use-case-5f-ssh-tmux",
        "checks": checks,
        "failures": failures,
        "ok_scope": "deterministic structure only; no semantic judgment over lifecycle adequacy",
        "deterministic_boundary": (
            "This verifier checks artifact existence, JSON parseability, required structured fields, "
            "matrix routing for ssh-tmux, issue-context shape, manifest scope, and focused test command status. "
            "It does not score prose meaning or claim target-client post-refresh tool invocation."
        ),
        "requires_agent_evaluation": True,
        "semantic_evaluation_required": True,
        "semantic_criteria": [
            {
                "id": "ssh_tmux_satisfies_issue_266",
                "question": "Does the source evidence satisfy #266's ssh-tmux lifecycle/apply proof purpose?"
            },
            {
                "id": "session_scope_boundary",
                "question": "Does the evidence preserve session-scoped read-only list/get behavior without opening sessions, sending commands, remote file mutation, cleanup, or close operations?"
            },
            {
                "id": "pi_opencode_boundaries",
                "question": "Are Pi and OpenCode project-local write/reload boundaries correctly distinguished?"
            },
            {
                "id": "no_umbrella_overclaim",
                "question": "Does the package avoid claiming #247, #269, remaining services, remote SSH connectivity, or actual tool-use completion?"
            },
            {
                "id": "deterministic_boundary",
                "question": "Did deterministic checks stay structural and avoid judging prose meaning?"
            }
        ],
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
