#!/usr/bin/env python3
"""Verify Use Case 5h exa-search lifecycle evidence structure."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REQUIRED_ISSUE_KEYS = {"issue_247", "issue_261", "issue_259", "issue_260", "issue_263", "issue_264", "issue_265", "issue_266", "issue_270", "pr_271"}


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
    manifest = load_json(repo_root / metadata["artifacts"]["exa_search_manifest"])
    services = matrix.get("services", [])
    exa_rows = [item for item in services if item.get("service") == "exa-search"]
    exa_search = exa_rows[0] if len(exa_rows) == 1 else {}
    taxonomy_types = {item.get("id") for item in taxonomy.get("types", [])}
    non_actions = set(exa_search.get("blockers_or_non_actions") or [])
    env_vars = set(manifest.get("backend", {}).get("env_vars") or [])
    checks: dict[str, bool] = {}
    failures: list[str] = []

    check(args.evidence.exists() and args.evidence.stat().st_size > 0, checks, failures, "evidence_file_nonempty")
    check(args.metadata.exists() and args.metadata.stat().st_size > 0, checks, failures, "metadata_file_nonempty")
    check(metadata.get("use_case") == "use-case-5h-exa-search", checks, failures, "metadata_use_case")
    check(metadata.get("semantic_acceptance") == "requires_agent_evaluation", checks, failures, "semantic_acceptance_declared")
    check(metadata.get("deterministic_boundary") == "structured_source_artifacts_only", checks, failures, "deterministic_boundary_declared")
    check(set(metadata.get("github_context", {})) >= REQUIRED_ISSUE_KEYS, checks, failures, "github_context_covers_required_items")
    check(
        all(item.get("state") and item.get("title") and item.get("body") for item in metadata.get("github_context", {}).values()),
        checks,
        failures,
        "github_context_has_bodies",
    )
    check(len(exa_rows) == 1, checks, failures, "single_exa_search_matrix_row")
    check(exa_search.get("owner_issue") == 261, checks, failures, "exa_search_owner_issue")
    check(exa_search.get("taxonomy_type") == "credential_scoped", checks, failures, "exa_search_taxonomy_type")
    check(exa_search.get("taxonomy_type") in taxonomy_types, checks, failures, "exa_search_taxonomy_type_known")
    check(exa_search.get("service_binding") == "exa-search:credential_scoped", checks, failures, "exa_search_binding")
    check(exa_search.get("safe_probe_status") == "conditional_probe", checks, failures, "conditional_probe_status")
    check(
        {"do not write or expose API keys", "do not run broad internet probes", "do not claim readiness from provider availability alone"} <= non_actions,
        checks,
        failures,
        "exa_search_non_actions_present",
    )
    check(manifest.get("scope", {}).get("scope_type") == "provider_credential_scope", checks, failures, "manifest_credential_scope")
    check({"EXA_API_KEY", "GEMINI_API_KEY"} <= env_vars, checks, failures, "manifest_declares_provider_env_vars")
    check(metadata.get("test_command", {}).get("returncode") == 0, checks, failures, "focused_lifecycle_test_passed")
    test_output = (
        metadata.get("test_command", {}).get("stdout", "")
        + "\n"
        + metadata.get("test_command", {}).get("stderr", "")
    )
    check(
        "test_exa_search_pi_lifecycle_writes_only_project_state_and_stops_for_reload" in test_output,
        checks,
        failures,
        "pi_lifecycle_test_executed",
    )
    check(
        "test_exa_search_opencode_lifecycle_writes_project_config_state_and_stops_for_new_session" in test_output,
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
        "use_case": "use-case-5h-exa-search",
        "checks": checks,
        "failures": failures,
        "ok_scope": "deterministic structure only; no semantic judgment over lifecycle adequacy",
        "deterministic_boundary": (
            "This verifier checks artifact existence, JSON parseability, required structured fields, "
            "matrix routing for exa-search, issue-context shape, manifest credential scope, and focused test command status. "
            "It does not score prose meaning or claim target-client post-refresh tool invocation."
        ),
        "requires_agent_evaluation": True,
        "semantic_evaluation_required": True,
        "semantic_criteria": [
            {
                "id": "exa_search_satisfies_issue_261",
                "question": "Does the source evidence satisfy #261's exa-search lifecycle/apply proof purpose?"
            },
            {
                "id": "credential_boundary",
                "question": "Does the evidence preserve provider credential boundaries without copying, exposing, inventing, committing, or validating provider secrets?"
            },
            {
                "id": "pi_opencode_boundaries",
                "question": "Are Pi and OpenCode project-local write/reload boundaries correctly distinguished?"
            },
            {
                "id": "no_umbrella_overclaim",
                "question": "Does the package avoid claiming #247, #269, remaining services, provider runtime success, credential validity, or actual tool-use completion?"
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
