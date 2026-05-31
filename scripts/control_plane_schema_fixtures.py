#!/usr/bin/env python3
"""Deterministic fixture runner for Wave 1 control-plane schema contracts."""

from __future__ import annotations

import copy
import json
import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import control_plane_contracts as contracts
import control_plane_project_state as project_state


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE_PATH = REPO_ROOT / "tests/fixtures/control_plane_schema_cases.json"
FIXED_TIMESTAMP = "2026-05-30T21:00:00Z"


@dataclass(frozen=True)
class FixtureCaseResult:
    """Result for one fixture case execution."""

    name: str
    passed: bool
    detail: str


PROJECT_STATE_ERRORS = {
    "RootValidationError": project_state.RootValidationError,
    "StateValidationError": project_state.StateValidationError,
    "StateLockError": project_state.StateLockError,
}

CONTRACT_ERRORS = {
    "ContractValidationError": contracts.ContractValidationError,
    "SchemaValidationError": contracts.SchemaValidationError,
    "RedactionValidationError": contracts.RedactionValidationError,
    "InferentialIsolationError": contracts.InferentialIsolationError,
    "UnknownArtifactKindError": contracts.UnknownArtifactKindError,
}


def load_fixture_cases(path: str | Path = DEFAULT_FIXTURE_PATH) -> dict[str, Any]:
    """Load fixture cases from JSON and validate the top-level fixture shape."""

    fixture_path = Path(path)
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"fixture file must contain a JSON object: {fixture_path}")
    for key in ("project_state_cases", "contract_artifact_cases"):
        if not isinstance(data.get(key), list):
            raise ValueError(f"fixture file missing list: {key}")
    if not isinstance(data.get("contract_artifact_templates"), dict):
        raise ValueError("fixture file missing object: contract_artifact_templates")
    return data


def repo_project_state_snapshot() -> tuple[bool, bytes | None, int | None]:
    """Snapshot the real repo project-state file so fixture runs can prove no writes."""

    path = project_state.project_state_path(REPO_ROOT)
    if not path.exists():
        return (False, None, None)
    stat = path.stat()
    return (True, path.read_bytes(), stat.st_mtime_ns)


def assert_repo_project_state_unchanged(snapshot: tuple[bool, bytes | None, int | None]) -> None:
    """Raise if fixture execution touched the real repo project-state file."""

    path = project_state.project_state_path(REPO_ROOT)
    exists, content, mtime_ns = snapshot
    if exists != path.exists():
        raise AssertionError(f"real repo project-state existence changed: {path}")
    if not exists:
        return
    stat = path.stat()
    if path.read_bytes() != content or stat.st_mtime_ns != mtime_ns:
        raise AssertionError(f"real repo project-state changed: {path}")


def run_project_state_case(case: Mapping[str, Any]) -> FixtureCaseResult:
    """Run one project-state fixture case against the frozen W1-A interface."""

    snapshot = repo_project_state_snapshot()
    try:
        return _run_expected_case(case, PROJECT_STATE_ERRORS, lambda: _execute_project_state_case(case))
    finally:
        assert_repo_project_state_unchanged(snapshot)


def run_contract_artifact_case(case: Mapping[str, Any], fixtures: Mapping[str, Any]) -> FixtureCaseResult:
    """Run one contract-artifact fixture case against the frozen W1-B interface."""

    return _run_expected_case(case, CONTRACT_ERRORS, lambda: _execute_contract_artifact_case(case, fixtures))


def _run_expected_case(
    case: Mapping[str, Any],
    error_map: Mapping[str, type[BaseException]],
    execute: Any,
) -> FixtureCaseResult:
    name = _case_name(case)
    expected = case.get("expect", "pass")
    if expected not in {"pass", "fail"}:
        raise ValueError(f"{name}: expect must be pass or fail")
    expected_error_name = case.get("error")
    expected_error = error_map.get(expected_error_name) if isinstance(expected_error_name, str) else None

    try:
        execute()
    except Exception as exc:  # noqa: BLE001 - fixture runner reports expected failures.
        if expected == "fail" and (expected_error is None or isinstance(exc, expected_error)):
            return FixtureCaseResult(name, True, f"failed as expected with {type(exc).__name__}")
        return FixtureCaseResult(name, False, f"unexpected {type(exc).__name__}: {exc}")

    if expected == "fail":
        return FixtureCaseResult(name, False, f"expected failure {expected_error_name or '<any>'}, but passed")
    return FixtureCaseResult(name, True, "passed")


def _execute_project_state_case(case: Mapping[str, Any]) -> None:
    operation = case.get("operation")
    if operation == "validate_root":
        root = _root_ref(case.get("root_ref"))
        project_state.validate_project_root(root, require_workspace=bool(case.get("require_workspace", False)))
    elif operation == "load_symlink_escape":
        _run_symlink_escape_case()
    elif operation == "default_state_validate":
        with _workspace_project_root() as root:
            state = _normalized_default_state(root)
            project_state.validate_state(state)
            if project_state.project_state_path(root).exists():
                raise AssertionError("default_state_validate wrote a project-state file")
            _assert_state_expectations(state, case.get("expected", {}))
    elif operation == "legacy_env_classification":
        migration = project_state.classify_legacy_env(dict(case.get("values", {})), malformed=list(case.get("malformed", [])))
        _assert_migration_expectations(migration, case.get("expected", {}))
    elif operation == "apply_legacy_env_migration_validate":
        with _workspace_project_root() as root:
            migration = project_state.classify_legacy_env(
                dict(case.get("values", {})),
                malformed=list(case.get("malformed", [])),
            )
            state = project_state.apply_legacy_migration(_normalized_default_state(root), migration)
            _normalize_project_state(state)
            project_state.validate_state(state)
            _assert_migration_expectations(migration, case.get("expected", {}))
            _assert_state_expectations(state, case.get("expected", {}))
    elif operation == "validate_state":
        with _workspace_project_root() as root:
            state = _normalized_default_state(root)
            _apply_mutations(state, case.get("mutations", []))
            project_state.validate_state(state)
            _assert_state_expectations(state, case.get("expected", {}))
    elif operation == "write_state_with_stale_lock":
        with _workspace_project_root() as root:
            lock_path = project_state.project_state_lock_path(root)
            lock_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            lock_path.write_text("stale\n", encoding="utf-8")
            age_seconds = float(case.get("lock_age_seconds", 120))
            old = time.time() - age_seconds
            os.utime(lock_path, (old, old))
            written = project_state.write_state_atomic(
                root,
                _normalized_default_state(root),
                stale_after_seconds=float(case.get("stale_after_seconds", 1)),
            )
            if lock_path.exists():
                raise AssertionError("stale lock was not removed")
            _assert_state_expectations(written, case.get("expected", {}))
    else:
        raise ValueError(f"{_case_name(case)}: unknown project-state operation {operation!r}")


def _execute_contract_artifact_case(case: Mapping[str, Any], fixtures: Mapping[str, Any]) -> None:
    templates = fixtures.get("contract_artifact_templates", {})
    if not isinstance(templates, Mapping):
        raise ValueError("contract_artifact_templates must be an object")
    template_name = case.get("template")
    if not isinstance(template_name, str) or template_name not in templates:
        raise ValueError(f"{_case_name(case)}: unknown contract artifact template {template_name!r}")
    artifact = copy.deepcopy(templates[template_name])
    _apply_mutations(artifact, case.get("mutations", []))
    contracts.validate_artifact(str(case.get("kind")), artifact)


def _workspace_project_root() -> tempfile.TemporaryDirectory[str]:
    return tempfile.TemporaryDirectory(prefix="cfcp-schema-fixture-", dir=str(project_state.WORKSPACE_ROOT))


def _root_ref(ref: Any) -> Path:
    if ref == "filesystem_root":
        return Path("/")
    if ref == "home":
        return Path.home()
    if ref == "workspace_root":
        return project_state.WORKSPACE_ROOT
    raise ValueError(f"unknown root_ref: {ref!r}")


def _run_symlink_escape_case() -> None:
    with _workspace_project_root() as tmp:
        link = Path(tmp) / "escaped-root"
        link.symlink_to("/tmp")
        project_state.load_state(link, require_workspace=True)


def _normalized_default_state(root: str | Path) -> dict[str, Any]:
    state = project_state.default_state(root)
    _normalize_project_state(state)
    return state


def _normalize_project_state(state: dict[str, Any]) -> None:
    meta = state.get("meta", {})
    if isinstance(meta, dict):
        meta["created_at"] = FIXED_TIMESTAMP
        meta["updated_at"] = FIXED_TIMESTAMP
    migration = state.get("migration", {})
    if isinstance(migration, dict) and migration.get("imported_at") is not None:
        migration["imported_at"] = FIXED_TIMESTAMP
    for decision in state.get("decisions", {}).values():
        if isinstance(decision, dict):
            decision["decided_at"] = FIXED_TIMESTAMP
    for item in state.get("open_items", []):
        if isinstance(item, dict):
            item["created_at"] = FIXED_TIMESTAMP


def _apply_mutations(target: Any, mutations: Any) -> None:
    if not isinstance(mutations, list):
        raise ValueError("mutations must be a list")
    for mutation in mutations:
        if not isinstance(mutation, Mapping):
            raise ValueError("mutation must be an object")
        op = mutation.get("op")
        path = mutation.get("path")
        if not isinstance(path, list) or not path:
            raise ValueError("mutation path must be a non-empty list")
        if op == "set":
            _set_path(target, path, copy.deepcopy(mutation.get("value")))
        elif op == "remove":
            _remove_path(target, path)
        else:
            raise ValueError(f"unknown mutation op: {op!r}")


def _set_path(target: Any, path: list[Any], value: Any) -> None:
    parent = _path_parent(target, path)
    key = path[-1]
    if isinstance(parent, list):
        parent[int(key)] = value
    else:
        parent[str(key)] = value


def _remove_path(target: Any, path: list[Any]) -> None:
    parent = _path_parent(target, path)
    key = path[-1]
    if isinstance(parent, list):
        parent.pop(int(key))
    else:
        parent.pop(str(key))


def _path_parent(target: Any, path: list[Any]) -> Any:
    current = target
    for key in path[:-1]:
        if isinstance(current, list):
            current = current[int(key)]
        else:
            current = current[str(key)]
    return current


def _assert_migration_expectations(migration: project_state.LegacyEnvMigration, expected: Any) -> None:
    if not isinstance(expected, Mapping):
        return
    _assert_equal("disposition", migration.disposition, expected.get("disposition"))
    _assert_equal("keys_seen", list(migration.keys_seen), expected.get("keys_seen"))
    _assert_equal("digest_present", migration.digest is not None, expected.get("digest_present"))
    if "decision_state" in expected:
        decision = migration.decisions.get(str(expected.get("decision_key", "serena")), {})
        _assert_equal("decision_state", decision.get("state"), expected.get("decision_state"))
    if "decision_notes_contains" in expected:
        decision = migration.decisions.get(str(expected.get("decision_key", "serena")), {})
        notes = str(decision.get("notes"))
        if str(expected["decision_notes_contains"]) not in notes:
            raise AssertionError(f"decision notes did not contain {expected['decision_notes_contains']!r}: {notes!r}")
    if "conflict_reason" in expected:
        reasons = [item.get("reason") for item in migration.conflicts]
        if expected["conflict_reason"] not in reasons:
            raise AssertionError(f"missing conflict_reason {expected['conflict_reason']!r}: {reasons!r}")
    if "open_item_severity" in expected:
        severities = [item.get("severity") for item in migration.open_items]
        if expected["open_item_severity"] not in severities:
            raise AssertionError(f"missing open_item_severity {expected['open_item_severity']!r}: {severities!r}")


def _assert_state_expectations(state: Mapping[str, Any], expected: Any) -> None:
    if not isinstance(expected, Mapping):
        return
    _assert_equal("status", state.get("status"), expected.get("status"))
    _assert_equal("revision", state.get("meta", {}).get("revision"), expected.get("revision"))
    if "migration_seen" in expected:
        _assert_equal("migration_seen", state.get("migration", {}).get("legacy_env_seen"), expected.get("migration_seen"))
    if "imported_at_present" in expected:
        imported_at = state.get("migration", {}).get("imported_at")
        _assert_equal("imported_at_present", imported_at is not None, expected.get("imported_at_present"))
    if "decision_state" in expected:
        decision = state.get("decisions", {}).get(str(expected.get("decision_key", "serena")), {})
        _assert_equal("state decision_state", decision.get("state"), expected.get("decision_state"))


def _assert_equal(label: str, actual: Any, expected: Any) -> None:
    if expected is not None and actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def _case_name(case: Mapping[str, Any]) -> str:
    name = case.get("name")
    if not isinstance(name, str) or not name:
        raise ValueError("fixture case missing non-empty name")
    return name
