#!/usr/bin/env python3
"""Verify Use Case 15 handoff evidence structure."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REQUIRED_CLIENTS = {"pi", "opencode", "codex"}
REQUIRED_ISSUES = {"#285", "#286", "#287", "#289", "#280"}


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

    checks["use_case_matches"] = metadata.get("use_case") == "use-case-15"
    checks["structural_only_boundary"] = metadata.get("deterministic_checks_are_structural_only") is True
    checks["semantic_review_required"] = metadata.get("semantic_handoff_review_required") is True
    for key in ("use_case_matches", "structural_only_boundary", "semantic_review_required"):
        if not checks[key]:
            failures.append(failure(key, f"metadata failed required check {key}"))

    clients = metadata.get("clients")
    checks["clients_cover_required_set"] = isinstance(clients, list) and set(clients) == REQUIRED_CLIENTS
    if not checks["clients_cover_required_set"]:
        failures.append(failure("clients_missing", "clients must be exactly pi, opencode, codex"))

    handoff = metadata.get("handoff")
    checks["handoff_object"] = isinstance(handoff, dict)
    if not isinstance(handoff, dict):
        failures.append(failure("missing_handoff", "handoff must be an object"))
    else:
        notes = handoff.get("client_operating_notes")
        checks["client_notes_present"] = isinstance(notes, dict) and REQUIRED_CLIENTS <= set(notes)
        if not checks["client_notes_present"]:
            failures.append(failure("client_notes_missing", "handoff.client_operating_notes must include all clients"))
        elif isinstance(notes, dict):
            for client in REQUIRED_CLIENTS:
                note = notes.get(client)
                if not isinstance(note, dict) or not {"what_works", "how_to_use", "evidence", "gap", "next_action"} <= set(note):
                    failures.append(failure(f"{client}_note_incomplete", f"{client} note must include what_works, how_to_use, evidence, gap, next_action"))
        issue_owners = handoff.get("issue_owners")
        checks["issue_owners_present"] = isinstance(issue_owners, dict) and REQUIRED_ISSUES <= set(issue_owners)
        if not checks["issue_owners_present"]:
            failures.append(failure("issue_owners_missing", "handoff.issue_owners must include required follow-up issues"))
        flows = handoff.get("validated_flows")
        checks["validated_flows_present"] = isinstance(flows, dict) and len(flows) >= 5
        if not checks["validated_flows_present"]:
            failures.append(failure("validated_flows_missing", "handoff.validated_flows must summarize accepted flows"))
        non_claims = handoff.get("non_claims")
        checks["non_claims_present"] = isinstance(non_claims, list) and len(non_claims) >= 6
        if not checks["non_claims_present"]:
            failures.append(failure("non_claims_missing", "handoff.non_claims must preserve readiness boundaries"))

    issue_statuses = metadata.get("issue_statuses")
    checks["issue_status_readback_present"] = isinstance(issue_statuses, dict) and REQUIRED_ISSUES <= set(issue_statuses)
    if not checks["issue_status_readback_present"]:
        failures.append(failure("issue_status_readback_missing", "metadata.issue_statuses must include required follow-up issues"))

    for key in ("handoff_report_path", "evaluation_package_path", "uc14_readiness_report_path"):
        value = metadata.get(key)
        checks[f"{key}_exists"] = isinstance(value, str) and Path(value).exists()
        if not checks[f"{key}_exists"]:
            failures.append(failure(f"{key}_missing", f"{key} must exist"))

    return result(metadata_path, checks, failures)


def result(metadata_path: Path, checks: dict[str, bool], failures: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "ok": not failures,
        "ok_scope": "deterministic structure only; handoff prose requires non-Spark semantic evaluation",
        "requires_agent_evaluation_for_handoff_claims": True,
        "use_case": "use-case-15",
        "metadata": str(metadata_path),
        "checks": checks,
        "failures": failures,
        "deterministic_boundary": (
            "This verifier checks metadata shape, artifact presence, required clients, "
            "issue-owner fields, and non-claim declarations. It does not judge handoff prose meaning."
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
