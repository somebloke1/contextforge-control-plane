#!/usr/bin/env python3
"""Verify Use Case 13 controlled-dev evidence structure."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def failure(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def check_status_object(name: str, value: Any, failures: list[dict[str, str]]) -> bool:
    if not isinstance(value, dict):
        failures.append(failure(f"{name}_missing", f"{name} must be an object"))
        return False
    ok = True
    if not isinstance(value.get("returncode"), int):
        failures.append(failure(f"{name}_returncode_missing", f"{name}.returncode must be an integer"))
        ok = False
    if not isinstance(value.get("timeout"), bool):
        failures.append(failure(f"{name}_timeout_missing", f"{name}.timeout must be boolean"))
        ok = False
    if value.get("required") is True and value.get("returncode") != 0:
        failures.append(failure(f"{name}_nonzero", f"{name} is required and must have returncode 0"))
        ok = False
    if value.get("required") is True and value.get("timeout") is not False:
        failures.append(failure(f"{name}_timed_out", f"{name} is required and must not time out"))
        ok = False
    return ok


def verify(metadata_path: Path) -> dict[str, Any]:
    failures: list[dict[str, str]] = []
    checks: dict[str, bool] = {
        "metadata_file_exists": metadata_path.exists() and metadata_path.is_file(),
    }
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
                failures.append(failure("metadata_not_object", "metadata JSON must be an object"))

    if metadata is None:
        return result(metadata_path, checks, failures)

    checks["use_case_matches"] = metadata.get("use_case") == "use-case-13"
    checks["semantic_boundary_declared"] = metadata.get("semantic_acceptance") == "not_a_dialogue_semantic_acceptance"
    checks["deterministic_boundary_declared"] = metadata.get("deterministic_checks_are_structural_only") is True
    for key in ("use_case_matches", "semantic_boundary_declared", "deterministic_boundary_declared"):
        if not checks[key]:
            failures.append(failure(key, f"metadata failed required structural check {key}"))

    python_surface = metadata.get("python_surface")
    checks["python_surface_object"] = isinstance(python_surface, dict)
    if isinstance(python_surface, dict):
        checks["python_surface_current_worktree"] = python_surface.get("current_worktree_test_venv") is True
        checks["python_surface_not_sibling_venv"] = python_surface.get("sibling_venv_substitution") is False
        if not checks["python_surface_current_worktree"]:
            failures.append(failure("python_surface_not_current_worktree", "host Python must be the current-worktree test venv"))
        if not checks["python_surface_not_sibling_venv"]:
            failures.append(failure("python_surface_sibling_venv", "sibling venv substitution must be false"))
    else:
        failures.append(failure("missing_python_surface", "metadata must include python_surface object"))

    dev_surface = metadata.get("dev_surface")
    checks["dev_surface_object"] = isinstance(dev_surface, dict)
    if isinstance(dev_surface, dict):
        checks["dev_surface_host_base_url_declared"] = isinstance(dev_surface.get("host_base_url"), str) and bool(dev_surface.get("host_base_url"))
        checks["dev_surface_container_base_url_declared"] = isinstance(dev_surface.get("container_base_url"), str) and bool(dev_surface.get("container_base_url"))
        checks["dev_surface_legacy_live_mutation_false"] = dev_surface.get("legacy_live_contextforge_mutated") is False
        if not checks["dev_surface_host_base_url_declared"]:
            failures.append(failure("missing_dev_host_base_url", "dev_surface.host_base_url must be present"))
        if not checks["dev_surface_container_base_url_declared"]:
            failures.append(failure("missing_dev_container_base_url", "dev_surface.container_base_url must be present"))
        if not checks["dev_surface_legacy_live_mutation_false"]:
            failures.append(failure("legacy_live_mutation_not_false", "dev_surface.legacy_live_contextforge_mutated must be false"))
    else:
        failures.append(failure("missing_dev_surface", "metadata must include dev_surface object"))

    clients = metadata.get("clients")
    checks["clients_object"] = isinstance(clients, dict)
    if not isinstance(clients, dict):
        failures.append(failure("missing_clients", "metadata must include clients object"))
    else:
        expected_reset_client = {"pi": "pi", "opencode": "opencode", "codex": "codex-cli"}
        for client in ("pi", "opencode", "codex"):
            client_record = clients.get(client)
            checks[f"{client}_record_object"] = isinstance(client_record, dict)
            if not isinstance(client_record, dict):
                failures.append(failure(f"missing_{client}_record", f"clients.{client} must be an object"))
                continue
            reset_json = client_record.get("reset_json")
            checks[f"{client}_reset_json_object"] = isinstance(reset_json, dict)
            if isinstance(reset_json, dict):
                checks[f"{client}_reset_ok"] = reset_json.get("ok") is True
                checks[f"{client}_reset_client_matches"] = reset_json.get("client") == expected_reset_client[client]
                if not checks[f"{client}_reset_ok"]:
                    failures.append(failure(f"{client}_reset_not_ok", f"{client} reset_json.ok must be true"))
                if not checks[f"{client}_reset_client_matches"]:
                    failures.append(
                        failure(
                            f"{client}_reset_client_mismatch",
                            f"{client} reset_json.client must match {expected_reset_client[client]}",
                        )
                    )
            else:
                failures.append(failure(f"{client}_missing_reset_json", f"{client} must include reset_json"))
            artifact = client_record.get("evidence_artifact")
            checks[f"{client}_evidence_artifact_declared"] = isinstance(artifact, str) and bool(artifact)
            if not checks[f"{client}_evidence_artifact_declared"]:
                failures.append(failure(f"{client}_missing_evidence_artifact", f"{client} evidence artifact path must be declared"))
            check_status_object(f"{client}_smoke", client_record.get("smoke_status"), failures)
            checks[f"{client}_host_global_mutation_false"] = client_record.get("host_global_client_mutated") is False
            if not checks[f"{client}_host_global_mutation_false"]:
                failures.append(failure(f"{client}_host_global_mutation", f"{client} host_global_client_mutated must be false"))

    statuses = metadata.get("command_statuses")
    checks["command_statuses_object"] = isinstance(statuses, dict) and bool(statuses)
    if not isinstance(statuses, dict) or not statuses:
        failures.append(failure("missing_command_statuses", "metadata must include command_statuses object"))
    else:
        for name, status in statuses.items():
            check_status_object(f"command_{name}", status, failures)

    selected = metadata.get("selected_use_case_dialogue_evidence")
    checks["selected_dialogue_evidence_list"] = isinstance(selected, list)
    if not isinstance(selected, list):
        failures.append(failure("selected_dialogue_evidence_missing", "metadata must include selected_use_case_dialogue_evidence list"))
    else:
        for index, item in enumerate(selected, start=1):
            if not isinstance(item, dict):
                failures.append(failure("selected_dialogue_item_not_object", f"selected dialogue item {index} must be an object"))
                continue
            if item.get("semantic_evaluator_required") is not True:
                failures.append(failure("selected_dialogue_requires_evaluator", f"selected dialogue item {index} must require semantic evaluator review"))

    return result(metadata_path, checks, failures)


def result(metadata_path: Path, checks: dict[str, bool], failures: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "ok": not failures,
        "ok_scope": "deterministic structure only; no semantic judgment over generated prose",
        "requires_agent_evaluation_for_dialogue_claims": True,
        "use_case": "use-case-13",
        "metadata": str(metadata_path),
        "checks": checks,
        "failures": failures,
        "deterministic_boundary": (
            "This verifier checks JSON structure, command status, reset status, declared surfaces, "
            "and claim-boundary fields. It does not score free-form assistant meaning."
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
