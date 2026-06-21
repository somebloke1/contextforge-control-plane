#!/usr/bin/env python3
"""Verify Use Case 14 readiness-report evidence structure."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REQUIRED_CLIENTS = {"pi", "opencode", "codex"}
REQUIRED_LAYERS = {
    "source_tests",
    "backend_container",
    "contextforge_route",
    "target_client_visibility",
    "ordinary_interactive_proof",
    "safe_call_proof",
    "handoff_readiness",
}


def failure(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def verify(metadata_path: Path) -> dict[str, Any]:
    failures: list[dict[str, str]] = []
    checks: dict[str, bool] = {"metadata_file_exists": metadata_path.exists() and metadata_path.is_file()}
    metadata: dict[str, Any] | None = None
    if not checks["metadata_file_exists"]:
        failures.append(failure("missing_metadata_file", "metadata JSON file must exist"))
    else:
        try:
            loaded = json.loads(metadata_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            failures.append(failure("invalid_metadata_json", f"metadata JSON must parse: {exc.msg}"))
        else:
            if isinstance(loaded, dict):
                metadata = loaded
            else:
                failures.append(failure("metadata_not_object", "metadata must be an object"))
    if metadata is None:
        return result(metadata_path, checks, failures)

    checks["use_case_matches"] = metadata.get("use_case") == "use-case-14"
    checks["structural_only_boundary"] = metadata.get("deterministic_checks_are_structural_only") is True
    checks["semantic_review_required"] = metadata.get("semantic_report_review_required") is True
    for key in ("use_case_matches", "structural_only_boundary", "semantic_review_required"):
        if not checks[key]:
            failures.append(failure(key, f"metadata failed required check {key}"))

    clients = metadata.get("clients")
    checks["clients_cover_required_set"] = isinstance(clients, list) and set(clients) == REQUIRED_CLIENTS
    if not checks["clients_cover_required_set"]:
        failures.append(failure("clients_missing", "clients must be exactly pi, opencode, codex"))

    claim_layers = metadata.get("claim_layers")
    checks["claim_layers_object"] = isinstance(claim_layers, dict)
    if not isinstance(claim_layers, dict):
        failures.append(failure("missing_claim_layers", "claim_layers must be an object"))
    else:
        layers = claim_layers.get("layers")
        checks["required_layers_present"] = isinstance(layers, dict) and REQUIRED_LAYERS <= set(layers)
        if not checks["required_layers_present"]:
            failures.append(failure("required_layers_missing", "claim ladder must include all required readiness layers"))
        client_claims = claim_layers.get("clients")
        checks["client_claims_present"] = isinstance(client_claims, dict) and REQUIRED_CLIENTS <= set(client_claims)
        if not checks["client_claims_present"]:
            failures.append(failure("client_claims_missing", "claim_layers.clients must include pi, opencode, codex"))
        overclaims = claim_layers.get("forbidden_overclaims")
        checks["forbidden_overclaims_false"] = (
            isinstance(overclaims, dict)
            and overclaims.get("release_ready") is False
            and overclaims.get("all_services_safe_called_in_all_clients") is False
            and overclaims.get("uc13_is_dialogue_success") is False
            and overclaims.get("live_legacy_contextforge_mutated") is False
        )
        if not checks["forbidden_overclaims_false"]:
            failures.append(failure("forbidden_overclaim_flags", "forbidden overclaim flags must all be false"))

    inventory = metadata.get("evidence_inventory")
    checks["evidence_inventory_list"] = isinstance(inventory, list) and bool(inventory)
    if not isinstance(inventory, list) or not inventory:
        failures.append(failure("missing_evidence_inventory", "evidence_inventory must be a non-empty list"))
    else:
        missing = [item for item in inventory if isinstance(item, dict) and item.get("required") is True and item.get("exists") is not True]
        checks["required_artifacts_exist"] = not missing
        if missing:
            failures.append(failure("required_artifacts_missing", f"{len(missing)} required evidence artifacts are missing"))
        bad_json = [item for item in inventory if isinstance(item, dict) and item.get("json_ok") is False]
        checks["json_artifacts_parse"] = not bad_json
        if bad_json:
            failures.append(failure("json_artifacts_invalid", f"{len(bad_json)} JSON evidence artifacts failed to parse"))

    groups = metadata.get("use_case_evidence_groups")
    checks["use_case_evidence_groups_list"] = isinstance(groups, list) and len(groups) == 13
    if not checks["use_case_evidence_groups_list"]:
        failures.append(failure("missing_use_case_evidence_groups", "use_case_evidence_groups must contain UC1 through UC13"))
    else:
        incomplete_groups = [
            group
            for group in groups
            if not isinstance(group, dict)
            or group.get("evidence_package_complete") is not True
            or group.get("semantic_evaluator_verdicts_required_for_acceptance") is not True
        ]
        checks["use_case_evidence_groups_complete"] = not incomplete_groups
        if incomplete_groups:
            failures.append(failure("use_case_evidence_groups_incomplete", f"{len(incomplete_groups)} use-case evidence groups are incomplete"))

    for key in ("readiness_report_path", "evaluation_package_path"):
        value = metadata.get(key)
        checks[f"{key}_declared"] = isinstance(value, str) and bool(value)
        if not checks[f"{key}_declared"]:
            failures.append(failure(f"{key}_missing", f"{key} must be declared"))

    return result(metadata_path, checks, failures)


def result(metadata_path: Path, checks: dict[str, bool], failures: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "ok": not failures,
        "ok_scope": "deterministic structure only; report prose requires non-Spark semantic evaluation",
        "requires_agent_evaluation_for_report_claims": True,
        "use_case": "use-case-14",
        "metadata": str(metadata_path),
        "checks": checks,
        "failures": failures,
        "deterministic_boundary": (
            "This verifier checks metadata shape, artifact presence, JSON parseability, clients, "
            "claim-layer fields, evidence-group fields, and overclaim flags. It does not judge report prose meaning "
            "or convert artifact presence into semantic acceptance."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata", type=Path, required=True)
    args = parser.parse_args(argv)
    verification = verify(args.metadata)
    print(json.dumps(verification, indent=2, sort_keys=True))
    return 0 if verification["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
