#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from dialogue_structural_verifier import verify_dialogue_structure


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify Use Case 6 dialogue evidence structure.")
    parser.add_argument("--client", choices=["pi", "opencode", "codex"], required=True)
    parser.add_argument("--shape", choices=["decline", "defer"], required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--session-id", default="")
    parser.add_argument("--format", choices=["json"], default="json")
    args = parser.parse_args(argv)

    result = verify_dialogue_structure(
        use_case="use-case-6",
        client=args.client,
        evidence_path=args.evidence,
        metadata_path=args.metadata,
        session_id=args.session_id,
        expected_prompt_count=4,
    )
    result["shape"] = args.shape
    failures = result.setdefault("failures", [])
    checks = result.setdefault("checks", {})
    metadata = load_metadata(args.metadata, failures)
    if metadata:
        checks.update(check_uc6_metadata(metadata, args.shape, failures))
    result["ok"] = not failures
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


def load_metadata(path: Path, failures: list[dict[str, str]]) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        failures.append({"code": "metadata_load_failed", "message": str(exc)})
        return None
    if not isinstance(value, dict):
        failures.append({"code": "metadata_not_object", "message": "metadata must be an object"})
        return None
    return value


def check_uc6_metadata(metadata: dict[str, Any], shape: str, failures: list[dict[str, str]]) -> dict[str, bool]:
    checks: dict[str, bool] = {}
    checks["metadata_shape_matches"] = metadata.get("shape") == shape
    if not checks["metadata_shape_matches"]:
        failures.append({"code": "metadata_shape_mismatch", "message": "metadata shape must match verifier shape"})

    expected_state = "declined" if shape == "decline" else "deferred"
    readback = metadata.get("decision_state_readback")
    checks["decision_state_readback_object"] = isinstance(readback, dict)
    if not isinstance(readback, dict):
        failures.append({"code": "missing_decision_state_readback", "message": "metadata must include decision_state_readback object"})
        return checks

    checks["decision_state_matches"] = readback.get("decision_state") == expected_state
    checks["decision_binding_present"] = isinstance(readback.get("decision_binding"), str) and bool(readback.get("decision_binding"))
    checks["active_service_absent"] = readback.get("active_service_absent") is True
    checks["target_client_active_import_absent"] = readback.get("target_client_active_import_absent") is True
    checks["state_status_initialized"] = readback.get("state_status") == "initialized"
    for key in (
        "decision_state_matches",
        "decision_binding_present",
        "active_service_absent",
        "target_client_active_import_absent",
        "state_status_initialized",
    ):
        if not checks[key]:
            failures.append({"code": key, "message": f"UC6 structured state check failed: {key}"})
    return checks


if __name__ == "__main__":
    raise SystemExit(main())
