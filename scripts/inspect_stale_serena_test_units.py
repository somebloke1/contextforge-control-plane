#!/usr/bin/env python3
"""Read-only stale Serena user-unit classifier.

This inspector supports issue #2. It deliberately has no cleanup mode: stopping,
disabling, deleting unit files, removing project trees, and registry cleanup are
separate approval-gated actions.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_URI = "contextforge://diagnostics/serena-stale-units/v1"
COMPATIBILITY_OPERATOR_UNIT = "contextforge-serena-cf-controlplane-d46fe58a2a20.service"
TEST_UNIT_PREFIX = "contextforge-serena-test-new-proj-"
SERENA_UNIT_PREFIX = "contextforge-serena-"
SYSTEMCTL_LIST_PATTERNS = ("contextforge-serena-test*", "contextforge*serena*")
NON_ACTIONS = (
    "read-only inspection; no systemd stop/disable/restart",
    "read-only inspection; no unit file deletion",
    "read-only inspection; no server-instance or project directory deletion",
    "read-only inspection; no ContextForge registry mutation",
)
APPROVAL_BOUNDARY = (
    "Stop, disable, unit-file removal, server-instance deletion, project-tree "
    "deletion, and ContextForge registry cleanup require separate explicit "
    "approval with exact unit/path identifiers."
)


def _run_systemctl(args: list[str]) -> str:
    completed = subprocess.run(
        ["systemctl", "--user", "--no-pager", "--plain", *args],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode not in (0, 1):
        raise RuntimeError(completed.stderr.strip() or f"systemctl exited {completed.returncode}")
    return completed.stdout


def _read_text(path: Path | None) -> str:
    if path is None:
        return ""
    return path.read_text(encoding="utf-8")


def _service_names(text: str) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("UNIT ", "0 loaded", "LOAD ")):
            continue
        first = stripped.split()[0]
        if first.endswith(".service") and first.startswith(SERENA_UNIT_PREFIX) and first not in seen:
            seen.add(first)
            names.append(first)
    return names


def _unit_file_states(text: str) -> dict[str, str]:
    states: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("UNIT FILE", "0 unit")):
            continue
        parts = stripped.split()
        if len(parts) >= 2 and parts[0].endswith(".service") and parts[0].startswith(SERENA_UNIT_PREFIX):
            states[parts[0]] = parts[1]
    return states


def _unit_load_state(unit: str, text: str) -> dict[str, str | None]:
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith(unit):
            continue
        parts = stripped.split(maxsplit=4)
        return {
            "load": parts[1] if len(parts) > 1 else None,
            "active": parts[2] if len(parts) > 2 else None,
            "sub": parts[3] if len(parts) > 3 else None,
        }
    return {"load": None, "active": None, "sub": None}


def _paths_from_text(text: str) -> list[str]:
    paths: list[str] = []
    seen: set[str] = set()
    for match in re.finditer(r"(/[^\s\"']+)", text):
        value = match.group(1).rstrip("\\")
        if value not in seen:
            seen.add(value)
            paths.append(value)
    return paths


def _instance_dir_from_paths(paths: list[str]) -> str | None:
    for path in paths:
        marker = "/server-instances/"
        if marker not in path:
            continue
        before, after = path.split(marker, 1)
        slug = after.split("/", 1)[0]
        if slug:
            return f"{before}{marker}{slug}"
    return None


def _manifest_project_root(manifest: dict[str, Any] | None) -> str | None:
    if manifest:
        for key in ("canonical_project_root", "project_root"):
            value = manifest.get(key)
            if isinstance(value, str) and value:
                return value
        scope = manifest.get("scope")
        if isinstance(scope, dict):
            value = scope.get("workspace_root")
            if isinstance(value, str) and value:
                return value
        backend = manifest.get("backend")
        args = backend.get("args") if isinstance(backend, dict) else None
        if isinstance(args, list):
            for index, item in enumerate(args):
                if item == "--project" and index + 1 < len(args) and isinstance(args[index + 1], str):
                    return args[index + 1]
    return None


def _unit_project_root(text: str) -> str | None:
    match = re.search(r"--project(?:=|\s+)(['\"]?)(/[^\s'\"]+)\1", text)
    if match:
        return match.group(2)
    for path in _paths_from_text(text):
        name = Path(path).name
        if name.startswith("test-new-proj"):
            return path
    return None


def _is_test_project_root(project_root: str | None) -> bool:
    return bool(project_root and Path(project_root).name.startswith("test-new-proj"))


def _path_state(path: str | None) -> dict[str, Any]:
    if not path:
        return {"exists": False, "type": None}
    candidate = Path(path)
    if candidate.is_dir():
        path_type = "directory"
    elif candidate.is_file():
        path_type = "file"
    elif candidate.exists():
        path_type = "other"
    else:
        path_type = None
    return {"exists": candidate.exists(), "type": path_type}


def _load_manifest(instance_dir: str | None) -> dict[str, Any] | None:
    if not instance_dir:
        return None
    path = Path(instance_dir) / "instance.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _unit_cat_from_dir(unit_cat_dir: Path | None, unit: str) -> str:
    if unit_cat_dir is None:
        return _run_systemctl(["cat", unit])
    for name in (unit, f"{unit}.txt"):
        candidate = unit_cat_dir / name
        if candidate.exists():
            return candidate.read_text(encoding="utf-8")
    return ""


def classify_unit(
    unit: str,
    *,
    list_units_text: str,
    unit_file_states: dict[str, str],
    unit_text: str,
) -> dict[str, Any]:
    paths = _paths_from_text(unit_text)
    instance_dir = _instance_dir_from_paths(paths)
    manifest = _load_manifest(instance_dir)
    manifest_project_root = _manifest_project_root(manifest)
    unit_project_root = _unit_project_root(unit_text)
    project_root = manifest_project_root or unit_project_root
    project_path_state = _path_state(project_root)
    manifest_port = manifest.get("port") if manifest else None
    reasons: list[str] = []

    classification = "review_required"
    if unit == COMPATIBILITY_OPERATOR_UNIT:
        classification = "retain_compatibility_operator"
        reasons.append("compatibility Serena unit must not be stopped by stale test-unit cleanup")
    elif unit.startswith(TEST_UNIT_PREFIX):
        evidence = {
            "unit_name_matches_test_pattern": True,
            "instance_dir_matches_test_pattern": bool(
                instance_dir and Path(instance_dir).name.startswith("serena-test-new-proj")
            ),
            "manifest_present": manifest is not None,
            "manifest_root_matches_test_pattern": _is_test_project_root(manifest_project_root),
            "unit_project_matches_manifest": bool(
                unit_project_root and manifest_project_root and unit_project_root == manifest_project_root
            ),
            "project_path_is_existing_directory": bool(
                project_path_state["exists"] and project_path_state["type"] == "directory"
            ),
            "manifest_port_present": isinstance(manifest_port, int),
        }
        if all(evidence.values()):
            classification = "disposable_candidate_requires_approval"
            reasons.append("unit name, instance path, manifest, project path, and port match test-new-proj evidence")
        else:
            missing = [key for key, value in evidence.items() if not value]
            reasons.append(f"unit name matches test-new-proj but evidence is incomplete: {', '.join(missing)}")
    elif unit.startswith(SERENA_UNIT_PREFIX):
        classification = "retain_project_scoped_or_unknown"
        reasons.append("Serena unit is not a test-new-proj candidate")

    if isinstance(manifest_port, int):
        port = manifest_port
    else:
        port = None

    return {
        "unit": unit,
        "classification": classification,
        "cleanup_allowed": False,
        "approval_required_for_cleanup": classification == "disposable_candidate_requires_approval",
        "unit_file_state": unit_file_states.get(unit),
        "systemd": _unit_load_state(unit, list_units_text),
        "instance_dir": instance_dir,
        "project_root": project_root,
        "manifest_project_root": manifest_project_root,
        "unit_project_root": unit_project_root,
        "project_path_state": project_path_state,
        "port": port,
        "paths": paths,
        "reasons": reasons,
    }


def build_report(
    *,
    list_units_text: str,
    list_unit_files_text: str,
    unit_cat_dir: Path | None = None,
) -> dict[str, Any]:
    states = _unit_file_states(list_unit_files_text)
    names = sorted(set(_service_names(list_units_text)) | set(states))
    units = [
        classify_unit(
            unit,
            list_units_text=list_units_text,
            unit_file_states=states,
            unit_text=_unit_cat_from_dir(unit_cat_dir, unit),
        )
        for unit in names
    ]
    counts: dict[str, int] = {}
    for unit in units:
        counts[unit["classification"]] = counts.get(unit["classification"], 0) + 1
    return {
        "schema_uri": SCHEMA_URI,
        "status": "review_required" if units else "no_serena_units_found",
        "summary": {
            "unit_count": len(units),
            "classification_counts": counts,
            "cleanup_candidate_units": [
                unit["unit"]
                for unit in units
                if unit["classification"] == "disposable_candidate_requires_approval"
            ],
        },
        "units": units,
        "approval_boundary": APPROVAL_BOUNDARY,
        "non_actions": list(NON_ACTIONS),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list-units-file", type=Path, help="Fixture output for systemctl list-units.")
    parser.add_argument("--list-unit-files-file", type=Path, help="Fixture output for systemctl list-unit-files.")
    parser.add_argument("--unit-cat-dir", type=Path, help="Directory containing fixture unit cat output by unit name.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    list_units_text = _read_text(args.list_units_file)
    list_unit_files_text = _read_text(args.list_unit_files_file)
    if args.list_units_file is None:
        list_units_text = _run_systemctl(["list-units", *SYSTEMCTL_LIST_PATTERNS])
    if args.list_unit_files_file is None:
        list_unit_files_text = _run_systemctl(["list-unit-files", *SYSTEMCTL_LIST_PATTERNS])
    print(
        json.dumps(
            build_report(
                list_units_text=list_units_text,
                list_unit_files_text=list_unit_files_text,
                unit_cat_dir=args.unit_cat_dir,
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
