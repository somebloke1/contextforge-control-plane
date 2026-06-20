#!/usr/bin/env python3
"""Verify Use Case 5a source-evidence structure without semantic scoring."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REQUIRED_TYPES = {
    "shared_canonical",
    "credential_scoped",
    "project_scoped",
    "session_scoped",
    "repo_local_static",
    "client_global_bootstrap",
    "not_a_service",
}

REQUIRED_MENU_ITEMS = {
    "context7",
    "exa-search",
    "github",
    "mentality",
    "openzeppelin-solidity-contracts",
    "playwright",
    "ssh-tmux",
    "web-search",
    "serena",
    "None",
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
    taxonomy_path = repo_root / metadata["artifacts"]["taxonomy_contract"]
    matrix_path = repo_root / metadata["artifacts"]["readiness_matrix"]
    checks: dict[str, bool] = {}
    failures: list[str] = []

    check(args.evidence.exists() and args.evidence.stat().st_size > 0, checks, failures, "evidence_file_nonempty")
    check(args.metadata.exists() and args.metadata.stat().st_size > 0, checks, failures, "metadata_file_nonempty")
    check(metadata.get("use_case") == "use-case-5a", checks, failures, "metadata_use_case")
    check(metadata.get("semantic_acceptance") == "requires_agent_evaluation", checks, failures, "semantic_acceptance_declared")
    check(metadata.get("deterministic_boundary") == "structured_source_artifacts_only", checks, failures, "deterministic_boundary_declared")

    taxonomy = load_json(taxonomy_path)
    matrix = load_json(matrix_path)
    type_ids = {item.get("id") for item in taxonomy.get("types", [])}
    menu_items = {item.get("menu_item") for item in taxonomy.get("menu_examples", [])}
    matrix_types = {item.get("taxonomy_type") for item in matrix.get("services", [])}
    matrix_types.update(item.get("taxonomy_type") for item in matrix.get("not_service_options", []))

    check(taxonomy.get("schema") == "contextforge://control-plane/service-localization-taxonomy/v1", checks, failures, "taxonomy_schema")
    check(
        taxonomy.get("interpretation_rules")
        == {
            "service_binding_suffix_authority": "identifier_only",
            "lifecycle_authority": "taxonomy_type",
        },
        checks,
        failures,
        "taxonomy_interpretation_rules",
    )
    check(REQUIRED_TYPES == type_ids, checks, failures, "taxonomy_required_type_ids")
    check(
        all(item.get("meaning") and item.get("instantiation_rule") and item.get("readiness_evidence") for item in taxonomy.get("types", [])),
        checks,
        failures,
        "taxonomy_type_fields_present",
    )
    check(REQUIRED_MENU_ITEMS == menu_items, checks, failures, "taxonomy_menu_items")
    check(bool(taxonomy.get("mapping_rules")), checks, failures, "taxonomy_mapping_rules_present")
    check(matrix.get("taxonomy_contract") == metadata["artifacts"]["taxonomy_contract"], checks, failures, "matrix_taxonomy_contract_link")
    check(matrix_types <= type_ids, checks, failures, "matrix_taxonomy_types_known")
    check(metadata.get("test_command", {}).get("returncode") == 0, checks, failures, "focused_test_passed")
    check(
        all(item.get("state") and item.get("title") for item in metadata.get("github_context", {}).values()),
        checks,
        failures,
        "github_context_present",
    )

    result = {
        "ok": not failures,
        "use_case": "use-case-5a",
        "checks": checks,
        "failures": failures,
        "ok_scope": "deterministic structure only; no semantic judgment over taxonomy prose or architectural adequacy",
        "deterministic_boundary": (
            "This verifier checks artifact existence, JSON parseability, required structured fields, "
            "enum relationships, issue-context shape, and focused test command status. It does not "
            "score prose meaning or architectural adequacy."
        ),
        "requires_agent_evaluation": True,
        "semantic_evaluation_required": True,
        "semantic_criteria": [
            {
                "id": "taxonomy_satisfies_issue_270",
                "question": "Does the taxonomy satisfy #270's lifecycle/localization purpose?"
            },
            {
                "id": "supports_259_247",
                "question": "Can #259 and #247 directly consume the taxonomy without false readiness claims?"
            },
            {
                "id": "boundary_honesty",
                "question": "Does the taxonomy keep service, client hook, credential, project, session, and not-a-service boundaries distinct?"
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
