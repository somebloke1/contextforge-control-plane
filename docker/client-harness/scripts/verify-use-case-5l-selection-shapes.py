#!/usr/bin/env python3
"""Verify Use Case 5l selection-shape evidence structure."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REQUIRED_CONTEXT_KEYS = {
    "issue_247",
    "issue_269",
    "issue_259",
    "issue_260",
    "issue_261",
    "issue_262",
    "issue_263",
    "issue_264",
    "issue_265",
    "issue_266",
    "issue_267",
    "issue_268",
    "issue_270",
    "pr_271",
}
EXPECTED_ALL_SERVICES = {
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
    matrix_services = {service.get("service") for service in matrix.get("services", [])}
    taxonomy_types = {item.get("id") for item in taxonomy.get("types", [])}
    shapes = metadata.get("selection_shapes", {})
    test_output = (
        metadata.get("test_command", {}).get("stdout", "")
        + "\n"
        + metadata.get("test_command", {}).get("stderr", "")
    )
    checks: dict[str, bool] = {}
    failures: list[str] = []

    check(args.evidence.exists() and args.evidence.stat().st_size > 0, checks, failures, "evidence_file_nonempty")
    check(args.metadata.exists() and args.metadata.stat().st_size > 0, checks, failures, "metadata_file_nonempty")
    check(metadata.get("use_case") == "use-case-5l-selection-shapes", checks, failures, "metadata_use_case")
    check(metadata.get("semantic_acceptance") == "requires_agent_evaluation", checks, failures, "semantic_acceptance_declared")
    check(metadata.get("deterministic_boundary") == "structured_source_artifacts_only", checks, failures, "deterministic_boundary_declared")
    check(set(metadata.get("github_context", {})) >= REQUIRED_CONTEXT_KEYS, checks, failures, "github_context_covers_required_items")
    check(
        all(item.get("state") and item.get("title") and item.get("body") for item in metadata.get("github_context", {}).values()),
        checks,
        failures,
        "github_context_has_bodies",
    )
    check(matrix_services == EXPECTED_ALL_SERVICES, checks, failures, "readiness_matrix_service_set")
    check(
        {service.get("taxonomy_type") for service in matrix.get("services", [])} <= taxonomy_types,
        checks,
        failures,
        "matrix_taxonomy_types_known",
    )
    check(shapes.get("single") == ["context7:canonical"], checks, failures, "single_shape_declared")
    check(
        shapes.get("curated") == ["context7:canonical", "mentality:static_repo_local", "ssh-tmux:session_scoped"],
        checks,
        failures,
        "curated_shape_declared",
    )
    check(len(shapes.get("all_services", [])) == 9, checks, failures, "all_services_shape_count")
    check("serena" in shapes.get("all_services", []), checks, failures, "all_services_includes_serena_dynamic_selection")
    check(metadata.get("test_command", {}).get("returncode") == 0, checks, failures, "focused_selection_shape_tests_passed")
    check(
        "test_single_service_selection_applies_for_pi_and_opencode" in test_output,
        checks,
        failures,
        "single_shape_test_executed",
    )
    check(
        "test_curated_multi_service_selection_spans_service_classes_without_omissions" in test_output,
        checks,
        failures,
        "curated_shape_test_executed",
    )
    check(
        "test_all_services_selection_applies_every_readiness_matrix_service" in test_output,
        checks,
        failures,
        "all_services_shape_test_executed",
    )
    check(
        all((repo_root / path).exists() for path in metadata.get("artifacts", {}).values()),
        checks,
        failures,
        "declared_artifacts_exist",
    )

    result = {
        "ok": not failures,
        "use_case": "use-case-5l-selection-shapes",
        "checks": checks,
        "failures": failures,
        "ok_scope": "deterministic structure only; no semantic judgment over selection-shape adequacy",
        "deterministic_boundary": (
            "This verifier checks artifact existence, JSON parseability, required structured fields, "
            "readiness-matrix service coverage, issue-context shape, and focused test command status. "
            "It does not score generated prose or claim target-client post-refresh tool invocation."
        ),
        "requires_agent_evaluation": True,
        "semantic_evaluation_required": True,
        "semantic_criteria": [
            {
                "id": "selection_shapes_satisfy_issue_269",
                "question": "Does the source evidence satisfy #269's single, curated multi-service, and all-services selection-shape purpose?"
            },
            {
                "id": "no_silent_omissions",
                "question": "Does all-services coverage include every helper-offered real service from the readiness matrix, with Serena handled as a dynamic project-scoped binding?"
            },
            {
                "id": "pi_opencode_boundaries",
                "question": "Are Pi and OpenCode project-local write/reload boundaries correctly distinguished?"
            },
            {
                "id": "no_umbrella_or_tool_use_overclaim",
                "question": "Does the package avoid claiming #247, post-refresh target-client visibility, provider runtime success, or actual tool-use completion?"
            },
            {
                "id": "deterministic_boundary",
                "question": "Did deterministic checks stay structural and avoid judging prose meaning?"
            },
        ],
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
