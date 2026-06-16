#!/usr/bin/env python3
"""Read-only preflight planner for retiring the legacy dirty checkout.

The report is intentionally non-mutating. It inventories path-bound operating
surfaces that would participate in an approved issue #15 rebind, then embeds
the existing project-init readiness reconciliation so approval can be based on
current evidence rather than prose.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import control_plane_project_state as project_state
import inspect_project_init_readiness as readiness


REPORT_SCHEMA_URI = "contextforge://control-plane/dirty-checkout-rebind-preflight/v1"
DEFAULT_LEGACY_ROOT = Path("/home/dgk/workspace/context-portal")
DEFAULT_STRATEGY = "compatibility_rebind"
COMPATIBILITY_SLUG = "context-portal"


@dataclass(frozen=True)
class SurfaceSpec:
    surface_id: str
    relative_path: str
    kind: str
    role: str
    required: bool = True
    safe_to_leave_compatibility_slug: bool = False


SURFACE_SPECS: tuple[SurfaceSpec, ...] = (
    SurfaceSpec(
        "codex_project_config",
        ".codex/config.toml",
        "codex_config",
        "Project-local Codex MCP and hook activation surface.",
    ),
    SurfaceSpec(
        "project_state",
        ".project/context_forge_state.json",
        "project_state",
        "Project-init authority containing root and root hash.",
    ),
    SurfaceSpec(
        "serena_manifest",
        "server-instances/serena-context-portal/instance.json",
        "service_manifest",
        "Serena backend manifest and ContextForge registration metadata.",
        safe_to_leave_compatibility_slug=True,
    ),
    SurfaceSpec(
        "serena_launcher",
        "server-instances/serena-context-portal/run-server.sh",
        "service_launcher",
        "User-systemd Serena backend launch script.",
        safe_to_leave_compatibility_slug=True,
    ),
    SurfaceSpec(
        "serena_lsp_env",
        "server-instances/serena-context-portal/lsp.env",
        "local_runtime_env",
        "Local LSP environment used by the Serena backend.",
        safe_to_leave_compatibility_slug=True,
    ),
    SurfaceSpec(
        "mentality_manifest",
        "server-instances/mentality/instance.json",
        "service_manifest",
        "Governance service manifest with backend working directory.",
    ),
    SurfaceSpec(
        "serena_project_metadata",
        ".serena/project.yml",
        "serena_project_metadata",
        "Serena project metadata and compatibility project name.",
        safe_to_leave_compatibility_slug=True,
    ),
    SurfaceSpec(
        "project_local_skills",
        ".codex/skills",
        "agent_operating_instructions",
        "Repo-local skills that can retrain agents back to a legacy root.",
    ),
    SurfaceSpec(
        "project_init_prompt_registration",
        "scripts/register_project_init_prompt.py",
        "contextforge_registration_script",
        "Registered project-init guidance examples and prompt content.",
    ),
    SurfaceSpec(
        "serena_registration_script",
        "scripts/register_serena_context_portal_service.py",
        "contextforge_registration_script",
        "Serena ContextForge registration helper.",
        required=False,
        safe_to_leave_compatibility_slug=True,
    ),
    SurfaceSpec(
        "systemd_unit_generator",
        "scripts/install_user_systemd.py",
        "service_management_script",
        "User systemd unit generator for ContextForge services.",
        safe_to_leave_compatibility_slug=True,
    ),
)


def _canonical(path: str | Path) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _text_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if not path.is_dir():
        return []
    return sorted(
        candidate
        for candidate in path.rglob("*")
        if candidate.is_file() and ".git" not in candidate.parts and "__pycache__" not in candidate.parts
    )


def _read_text(path: Path) -> tuple[str, str | None]:
    try:
        return path.read_text(encoding="utf-8"), None
    except UnicodeDecodeError as exc:
        return "", f"{exc.__class__.__name__}: {exc}"
    except OSError as exc:
        return "", f"{exc.__class__.__name__}: {exc}"


def _line_hits(path: Path, needle: str, *, limit: int = 6) -> list[dict[str, Any]]:
    if not needle:
        return []
    text, error = _read_text(path)
    if error:
        return []
    hits: list[dict[str, Any]] = []
    for index, line in enumerate(text.splitlines(), start=1):
        if needle in line:
            hits.append({"path": str(path), "line": index, "text": line.strip()[:240]})
            if len(hits) >= limit:
                break
    return hits


def _collect_reference_hits(files: Sequence[Path], needle: str) -> tuple[int, list[dict[str, Any]]]:
    count = 0
    samples: list[dict[str, Any]] = []
    for path in files:
        text, error = _read_text(path)
        if error:
            continue
        file_count = text.count(needle)
        if file_count:
            count += file_count
            samples.extend(_line_hits(path, needle, limit=max(0, 6 - len(samples))))
    return count, samples[:6]


def _project_state_facts(path: Path, target_root: Path) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    evidence: list[dict[str, Any]] = []
    blockers: list[str] = []
    warnings: list[str] = []
    if not path.exists():
        return evidence, ["project_state_missing"], warnings
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return evidence, ["project_state_unreadable"], [f"{exc.__class__.__name__}: {exc}"]
    if not isinstance(raw, dict):
        return evidence, ["project_state_not_object"], warnings

    project = raw.get("project") if isinstance(raw.get("project"), Mapping) else {}
    root_match = project_state.root_match_details(raw, target_root)
    expected_hash = project_state.project_root_hash(target_root)
    evidence.extend(
        [
            {"name": "project.root", "observed": project.get("root"), "expected": str(target_root)},
            {"name": "project.root_hash", "observed": project.get("root_hash"), "expected": expected_hash},
            {"name": "root_match", "observed": root_match},
        ]
    )
    if root_match.get("root_matches") is False or root_match.get("root_hash_matches") is False:
        blockers.append("project_state_root_mismatch")
        blockers.append("direct_project_state_string_replacement_forbidden")
    return evidence, blockers, warnings


def _inspect_surface(
    spec: SurfaceSpec,
    *,
    target_root: Path,
    legacy_root: Path,
) -> dict[str, Any]:
    path = target_root / spec.relative_path
    files = _text_files(path)
    legacy_root_refs, legacy_samples = _collect_reference_hits(files, str(legacy_root))
    target_root_refs, target_samples = _collect_reference_hits(files, str(target_root))
    compatibility_slug_refs, slug_samples = _collect_reference_hits(files, COMPATIBILITY_SLUG)
    exists = path.exists()
    blockers: list[str] = []
    warnings: list[str] = []
    evidence: list[dict[str, Any]] = [
        {"name": "exists", "observed": exists, "expected": True},
        {"name": "legacy_root_reference_count", "observed": legacy_root_refs, "expected": 0},
        {"name": "target_root_reference_count", "observed": target_root_refs, "expected": "nonzero where this surface owns active launch paths"},
        {
            "name": "compatibility_slug_reference_count",
            "observed": compatibility_slug_refs,
            "expected": "allowed only for historical/runtime compatibility identifiers",
        },
    ]
    if not exists and spec.required:
        blockers.append("surface_missing")
    if not exists and not spec.required:
        warnings.append("optional_surface_missing")
    if legacy_root_refs:
        blockers.append("surface_legacy_root_reference")
    if compatibility_slug_refs > legacy_root_refs and not spec.safe_to_leave_compatibility_slug:
        warnings.append("surface_contains_legacy_compatibility_slug")

    if spec.surface_id == "project_state":
        project_evidence, project_blockers, project_warnings = _project_state_facts(path, target_root)
        evidence.extend(project_evidence)
        blockers.extend(project_blockers)
        warnings.extend(project_warnings)

    status = "missing" if not exists else "ready"
    if blockers:
        status = "blocked"
    elif warnings:
        status = "attention_required"
    elif legacy_root_refs:
        status = "rebind_required"

    samples = {
        "legacy_root": legacy_samples,
        "target_root": target_samples,
        "compatibility_slug": slug_samples,
    }
    recommended_action = "no_action"
    if blockers:
        recommended_action = "approval_required_before_rebind"
    elif warnings:
        recommended_action = "review_compatibility_slug"

    return {
        "surface_id": spec.surface_id,
        "path": str(path),
        "kind": spec.kind,
        "role": spec.role,
        "exists": exists,
        "required": spec.required,
        "current_root": str(legacy_root) if legacy_root_refs else None,
        "expected_root": str(target_root),
        "expected_root_hash": project_state.project_root_hash(target_root),
        "status": status,
        "recommended_action": recommended_action,
        "rebind_required": bool(legacy_root_refs or "project_state_root_mismatch" in blockers),
        "safe_to_leave_compatibility_slug": spec.safe_to_leave_compatibility_slug,
        "blockers": sorted(set(blockers)),
        "warnings": sorted(set(warnings)),
        "evidence": evidence,
        "samples": samples,
    }


def _dedupe(values: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _status_from_findings(blockers: Sequence[str], warnings: Sequence[str]) -> str:
    if blockers:
        return "blocked"
    if warnings:
        return "attention_required"
    return "ready"


def build_report(
    *,
    target_root: str | Path,
    legacy_root: str | Path = DEFAULT_LEGACY_ROOT,
    strategy: str = DEFAULT_STRATEGY,
    include_processes: bool = True,
    client_types: Sequence[str] = ("codex", "pi"),
    process_snapshot: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    target = _canonical(target_root)
    legacy = _canonical(legacy_root)
    surfaces = [
        _inspect_surface(spec, target_root=target, legacy_root=legacy)
        for spec in SURFACE_SPECS
    ]
    readiness_report = readiness.build_report(
        project_root=target,
        compare_roots=[legacy],
        client_types=client_types,
        include_processes=include_processes,
        process_snapshot=process_snapshot,
    )
    blockers = ["approval_required_before_rebind"]
    warnings: list[str] = []
    for surface in surfaces:
        blockers.extend(f"{surface['surface_id']}:{blocker}" for blocker in surface["blockers"])
        warnings.extend(f"{surface['surface_id']}:{warning}" for warning in surface["warnings"])
    blockers.extend(str(blocker) for blocker in readiness_report.get("blockers", []))
    warnings.extend(str(warning) for warning in readiness_report.get("warnings", []))
    inspected_files = [
        str(path)
        for spec in SURFACE_SPECS
        for path in _text_files(target / spec.relative_path)
    ]
    return {
        "schema_uri": REPORT_SCHEMA_URI,
        "project_name": "ContextForge",
        "strategy": strategy,
        "target_root": str(target),
        "legacy_root": str(legacy),
        "approval_required": True,
        "status": _status_from_findings(blockers, warnings),
        "blockers": _dedupe(blockers),
        "warnings": _dedupe(warnings),
        "surfaces": surfaces,
        "roots": readiness_report.get("roots", []),
        "helper_processes": readiness_report.get("helper_processes", []),
        "next_actions": _dedupe(
            [
                "Ask the user to approve Strategy 1 compatibility rebind, Strategy 2 new root identity, or Strategy 3 archival-only deferral.",
                "Do not mutate project state, client config, service units, registry entries, hook trust, or processes from this report alone.",
                *[str(action) for action in readiness_report.get("next_actions", [])],
            ]
        ),
        "non_actions": [
            "read-only preflight; no project files are written",
            "no project-init helper approval/apply workflow is invoked",
            "no service, process, registry, hook trust, user-global config, or client config state is mutated",
            "no dirty checkout reset, clean, delete, rename, rebase, or archival action is performed",
        ],
        "inspected_files": inspected_files,
        "inspected_commands": [
            "read text files under path-bound operating surfaces",
            "inspect_project_init_readiness.build_report",
        ],
    }


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-root", default=str(Path.cwd()), help="Clean root that would receive the rebind.")
    parser.add_argument("--legacy-root", default=str(DEFAULT_LEGACY_ROOT), help="Legacy dirty checkout root.")
    parser.add_argument("--strategy", default=DEFAULT_STRATEGY, choices=(DEFAULT_STRATEGY, "new_root_identity", "archival_only"))
    parser.add_argument("--client-type", action="append", help="Client type for embedded readiness reconciliation. May repeat.")
    parser.add_argument("--no-processes", action="store_true", help="Skip read-only helper process source inspection.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_report(
        target_root=args.target_root,
        legacy_root=args.legacy_root,
        strategy=args.strategy,
        include_processes=not args.no_processes,
        client_types=tuple(args.client_type or ("codex", "pi")),
    )
    print(json.dumps(report, indent=2 if args.pretty else None, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
