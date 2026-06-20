#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from dialogue_structural_verifier import verify_dialogue_structure


TARGET_CLIENTS = ("pi", "opencode", "codex")
CLIENT_KEY = "-".join(TARGET_CLIENTS)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify Use Case 10 refresh evidence structure.")
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--session-id", default="")
    args = parser.parse_args(argv)

    result = verify_dialogue_structure(
        use_case="use-case-10",
        client=CLIENT_KEY,
        evidence_path=args.evidence,
        metadata_path=args.metadata,
        session_id=args.session_id,
        expected_prompt_count=len(TARGET_CLIENTS) * 2,
    )
    metadata = load_metadata(args.metadata)
    result["refresh_checks"] = check_refresh_comparison(metadata)
    result["ok"] = bool(result["ok"] and result["refresh_checks"]["ok"])
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


def load_metadata(path: Path) -> dict[str, Any]:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def check_refresh_comparison(metadata: dict[str, Any]) -> dict[str, Any]:
    failures: list[dict[str, str]] = []
    comparison = metadata.get("refresh_comparison")
    if not isinstance(comparison, dict):
        return {
            "ok": False,
            "failures": [{"code": "missing_refresh_comparison", "message": "metadata must include structured refresh_comparison"}],
        }

    required_true = [
        "project_root_workspace",
        "baseline_initialized",
        "after_initialized",
        "revision_increased",
        "enabled_services_changed",
        "baseline_context7_only",
        "after_includes_context7_and_mentality",
        "target_clients_include_all_clients",
        "structured_comparison_only",
    ]
    checks: dict[str, bool] = {}
    for key in required_true:
        checks[key] = comparison.get(key) is True
        if not checks[key]:
            failures.append({"code": key, "message": f"refresh_comparison.{key} must be true"})

    return {
        "ok": not failures,
        "checks": checks,
        "failures": failures,
        "deterministic_boundary": "structured before/after state comparison only; visible reply meaning requires semantic evaluator",
    }


if __name__ == "__main__":
    raise SystemExit(main())
