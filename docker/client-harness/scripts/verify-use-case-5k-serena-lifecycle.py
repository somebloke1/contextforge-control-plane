#!/usr/bin/env python3
"""Verify Use Case 5k Serena lifecycle evidence structure."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REQUIRED_ISSUE_KEYS = {
    "issue_247",
    "issue_268",
    "issue_267",
    "issue_259",
    "issue_260",
    "issue_261",
    "issue_262",
    "issue_263",
    "issue_264",
    "issue_265",
    "issue_266",
    "issue_270",
    "pr_271",
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
    manifest = load_json(repo_root / metadata["artifacts"]["serena_manifest"])
    services = matrix.get("services", [])
    serena_rows = [item for item in services if item.get("service") == "serena"]
    serena = serena_rows[0] if len(serena_rows) == 1 else {}
    taxonomy_types = {item.get("id") for item in taxonomy.get("types", [])}
    non_actions = set(serena.get("blockers_or_non_actions") or [])
    checks: dict[str, bool] = {}
    failures: list[str] = []

    check(args.evidence.exists() and args.evidence.stat().st_size > 0, checks, failures, "evidence_file_nonempty")
    check(args.metadata.exists() and args.metadata.stat().st_size > 0, checks, failures, "metadata_file_nonempty")
    check(metadata.get("use_case") == "use-case-5k-serena", checks, failures, "metadata_use_case")
    check(metadata.get("semantic_acceptance") == "requires_agent_evaluation", checks, failures, "semantic_acceptance_declared")
    check(metadata.get("deterministic_boundary") == "structured_source_artifacts_only", checks, failures, "deterministic_boundary_declared")
    check(set(metadata.get("github_context", {})) >= REQUIRED_ISSUE_KEYS, checks, failures, "github_context_covers_required_items")
    check(
        all(item.get("state") and item.get("title") and item.get("body") for item in metadata.get("github_context", {}).values()),
        checks,
        failures,
        "github_context_has_bodies",
    )
    check(len(serena_rows) == 1, checks, failures, "single_serena_matrix_row")
    check(serena.get("owner_issue") == 268, checks, failures, "serena_owner_issue")
    check(serena.get("taxonomy_type") == "project_scoped", checks, failures, "serena_taxonomy_type")
    check(serena.get("taxonomy_type") in taxonomy_types, checks, failures, "serena_taxonomy_type_known")
    check(serena.get("service_binding_pattern") == "serena:<project-root-hash-prefix>", checks, failures, "serena_binding_pattern")
    check(serena.get("safe_probe_status") == "conditional_probe", checks, failures, "conditional_probe_status")
    check(
        {
            "no Serena provisioning in this taxonomy/matrix slice",
            "no LSP writes",
            "no global config mutation",
            "no broad project scan as validation proof",
        }
        <= non_actions,
        checks,
        failures,
        "serena_non_actions_present",
    )
    check(manifest.get("scope", {}).get("scope_type") == "single_workspace_code_intelligence", checks, failures, "manifest_project_scope")
    check(manifest.get("scope", {}).get("requires_local_project_scope") is True, checks, failures, "manifest_requires_local_project_scope")
    check(manifest.get("service") == "serena", checks, failures, "manifest_service_is_serena")
    check(manifest.get("tool_policy", {}).get("contextforge_excluded_original_tool_names") == ["activate_project"], checks, failures, "manifest_excludes_activate_project")
    check(metadata.get("test_command", {}).get("returncode") == 0, checks, failures, "focused_lifecycle_test_passed")
    test_output = (
        metadata.get("test_command", {}).get("stdout", "")
        + "\n"
        + metadata.get("test_command", {}).get("stderr", "")
    )
    check(
        "test_serena_selection_stops_for_language_before_approval" in test_output,
        checks,
        failures,
        "language_input_test_executed",
    )
    check(
        "test_serena_pi_lifecycle_provisions_then_writes_only_project_state" in test_output,
        checks,
        failures,
        "pi_lifecycle_test_executed",
    )
    check(
        "test_serena_opencode_lifecycle_provisions_then_writes_project_config_state" in test_output,
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
        "use_case": "use-case-5k-serena",
        "checks": checks,
        "failures": failures,
        "ok_scope": "deterministic structure only; no semantic judgment over lifecycle adequacy",
        "deterministic_boundary": (
            "This verifier checks artifact existence, JSON parseability, required structured fields, "
            "matrix routing for Serena, issue-context shape, manifest project scope, and focused test command status. "
            "It does not score prose meaning or claim target-client post-refresh tool invocation."
        ),
        "requires_agent_evaluation": True,
        "semantic_evaluation_required": True,
        "semantic_criteria": [
            {
                "id": "serena_satisfies_issue_268",
                "question": "Does the source evidence satisfy #268's Serena lifecycle/apply proof purpose?"
            },
            {
                "id": "project_scoped_provisioning_boundary",
                "question": "Does the evidence preserve Serena project-scoped provisioning, language selection, and no-global/no-runtime-overclaim boundaries?"
            },
            {
                "id": "pi_opencode_boundaries",
                "question": "Are Pi and OpenCode project-local write/reload boundaries correctly distinguished?"
            },
            {
                "id": "no_umbrella_overclaim",
                "question": "Does the package avoid claiming #247, #269, target-client post-refresh visibility, Serena runtime/LSP/indexing success, or actual tool-use completion?"
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
