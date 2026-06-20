#!/usr/bin/env python3
"""Verify Use Case 5b readiness-matrix evidence structure."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REQUIRED_SERVICES = {
    "context7",
    "exa-search",
    "github",
    "mentality",
    "openzeppelin-solidity-contracts",
    "playwright",
    "ssh-tmux",
    "web-search",
    "serena",
}

REQUIRED_ISSUE_KEYS = {f"issue_{number}" for number in [247, 259, 270, *range(260, 269)]} | {"pr_271"}


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
    checks: dict[str, bool] = {}
    failures: list[str] = []

    services = matrix.get("services", [])
    service_names = {item.get("service") for item in services}
    taxonomy_types = {item.get("id") for item in taxonomy.get("types", [])}
    matrix_types = {item.get("taxonomy_type") for item in services}
    not_service_options = matrix.get("not_service_options", [])
    current_slice = [item.get("service") for item in services if item.get("current_slice")]

    check(args.evidence.exists() and args.evidence.stat().st_size > 0, checks, failures, "evidence_file_nonempty")
    check(args.metadata.exists() and args.metadata.stat().st_size > 0, checks, failures, "metadata_file_nonempty")
    check(metadata.get("use_case") == "use-case-5b", checks, failures, "metadata_use_case")
    check(metadata.get("semantic_acceptance") == "requires_agent_evaluation", checks, failures, "semantic_acceptance_declared")
    check(metadata.get("deterministic_boundary") == "structured_source_artifacts_only", checks, failures, "deterministic_boundary_declared")
    check(set(metadata.get("github_context", {})) >= REQUIRED_ISSUE_KEYS, checks, failures, "github_context_covers_required_issues")
    check(
        all(item.get("state") and item.get("title") and item.get("body") for item in metadata.get("github_context", {}).values()),
        checks,
        failures,
        "github_context_has_bodies",
    )
    check(matrix.get("schema") == "contextforge://control-plane/service-readiness-matrix/v1", checks, failures, "matrix_schema")
    check(
        matrix.get("matrix_semantics")
        == {
            "safe_probe_status": "probe_policy_or_probe_shape_only_not_service_readiness",
            "current_slice": "current_branch_readiness_focus_only_not_umbrella_acceptance",
            "active_service_readiness": "requires owner_issue evidence or explicit blocked/non-action result",
            "slice_progress": "controller progress ledger; does not replace per-issue evidence or accepted package reports",
        },
        checks,
        failures,
        "matrix_semantics_declared",
    )
    check(matrix.get("taxonomy_contract") == metadata["artifacts"]["taxonomy_contract"], checks, failures, "matrix_taxonomy_contract_link")
    check(matrix_types <= taxonomy_types, checks, failures, "matrix_taxonomy_types_known")
    check(service_names == REQUIRED_SERVICES, checks, failures, "matrix_required_service_coverage")
    check(
        all((item.get("taxonomy_type") == "not_a_service" and item.get("owner_issue") == 248) for item in not_service_options),
        checks,
        failures,
        "none_is_not_service_option",
    )
    check(not {"None", "none"} & service_names, checks, failures, "none_excluded_from_services")
    check(
        all(
            item.get("owner_issue")
            and item.get("display_name")
            and item.get("source_paths")
            and item.get("instantiation_path")
            and item.get("pi_visibility_expectation")
            and item.get("opencode_visibility_expectation")
            and item.get("safe_probe_status")
            and item.get("safe_probe")
            and item.get("blockers_or_non_actions")
            for item in services
        ),
        checks,
        failures,
        "per_service_fields_present",
    )
    check(current_slice == ["context7"], checks, failures, "current_slice_only_context7")
    progress = matrix.get("slice_progress", {})
    check(
        progress.get("accepted_source_lifecycle_slices") == [
            "context7",
            "mentality",
            "openzeppelin-solidity-contracts",
            "ssh-tmux",
        ],
        checks,
        failures,
        "slice_progress_records_accepted_source_slices",
    )
    check(
        progress.get("active_next_recommended_service") == "playwright",
        checks,
        failures,
        "slice_progress_recommends_next_service",
    )
    check(metadata.get("test_command", {}).get("returncode") == 0, checks, failures, "focused_test_passed")

    result = {
        "ok": not failures,
        "use_case": "use-case-5b",
        "checks": checks,
        "failures": failures,
        "ok_scope": "deterministic structure only; no semantic judgment over readiness adequacy",
        "deterministic_boundary": (
            "This verifier checks artifact existence, JSON parseability, required structured fields, "
            "enum relationships, issue-context shape, and focused test command status. It does not "
            "score prose meaning or service readiness adequacy."
        ),
        "requires_agent_evaluation": True,
        "semantic_evaluation_required": True,
        "semantic_criteria": [
            {
                "id": "matrix_satisfies_issue_259",
                "question": "Does the matrix satisfy #259's helper-offered service readiness planning purpose?"
            },
            {
                "id": "false_readiness_prevention",
                "question": "Does the matrix prevent #247 from counting services ready without proof or explicit blockers?"
            },
            {
                "id": "per_service_routing",
                "question": "Does every service have a clear owner/evidence path before all-services apply?"
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
