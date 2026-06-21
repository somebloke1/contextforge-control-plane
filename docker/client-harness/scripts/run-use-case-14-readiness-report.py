#!/usr/bin/env python3
"""Generate Use Case 14 readiness-report evidence."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CLIENTS = ("pi", "opencode", "codex")


def artifact(path: Path, *, required: bool = True, kind: str = "file") -> dict[str, Any]:
    exists = path.exists() and path.is_file()
    record: dict[str, Any] = {
        "path": str(path),
        "kind": kind,
        "required": required,
        "exists": exists,
        "size_bytes": path.stat().st_size if exists else 0,
    }
    if exists and path.suffix == ".json":
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            record["json_ok"] = False
            record["json_error"] = exc.msg
        else:
            record["json_ok"] = True
            if isinstance(loaded, dict) and "ok" in loaded:
                record["declared_ok"] = loaded.get("ok")
    return record


def latest(root: Path, pattern: str) -> Path | None:
    matches = sorted(root.glob(pattern))
    return matches[-1] if matches else None


def add_latest(items: list[dict[str, Any]], root: Path, pattern: str, *, label: str, required: bool = True) -> None:
    path = latest(root, pattern)
    if path is None:
        items.append({"label": label, "path": str(root / pattern), "required": required, "exists": False, "kind": "glob"})
        return
    record = artifact(path, required=required, kind="latest_glob")
    record["label"] = label
    record["pattern"] = pattern
    items.append(record)


def build_evidence_inventory(repo_root: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    reports = repo_root / "run" / "holistic-orchestrator" / "reports"
    for uc in range(1, 14):
        for pattern in (f"uc{uc}-controller-acceptance-*.md", f"uc{uc}-codex-parity-acceptance-*.md"):
            add_latest(items, reports, pattern, label=f"uc{uc}_{pattern.removesuffix('-*.md')}", required=False)
        package = repo_root / "docs" / "use-cases" / f"use-case-{uc}" / "package.md"
        record = artifact(package, required=True, kind="package")
        record["label"] = f"uc{uc}_package"
        items.append(record)
        acceptance = repo_root / "docs" / "use-cases" / f"use-case-{uc}" / "controller-acceptance-20260620.md"
        record = artifact(acceptance, required=False, kind="controller_acceptance")
        record["label"] = f"uc{uc}_controller_acceptance_doc"
        items.append(record)
    for uc in (9, 10, 13):
        add_latest(
            items,
            repo_root / "docker" / "client-harness" / "evidence" / f"use-case-{uc}",
            f"*verifier-*.json",
            label=f"uc{uc}_latest_structural_verifier",
        )
    for client in CLIENTS:
        add_latest(
            items,
            repo_root / "docker" / "client-harness" / "evidence" / "use-case-12" / client,
            f"{client}-verifier-*.json",
            label=f"uc12_{client}_latest_structural_verifier",
        )
    for name in (
        "pi-contextforge-dev-smoke.txt",
        "opencode-contextforge-dev-smoke.txt",
        "codex-contextforge-dev-smoke.txt",
    ):
        record = artifact(repo_root / "docker" / "client-harness" / "evidence" / name, required=True, kind="smoke")
        record["label"] = name.removesuffix(".txt")
        items.append(record)
    return items


def build_use_case_evidence_groups(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    for uc in range(1, 14):
        prefix = f"uc{uc}_"
        package = [item for item in evidence if item.get("label") == f"uc{uc}_package"]
        controller_review = [
            item
            for item in evidence
            if str(item.get("label", "")).startswith(prefix)
            and (
                "acceptance" in str(item.get("label"))
                or item.get("kind") == "controller_acceptance"
            )
            and item.get("exists") is True
        ]
        groups.append(
            {
                "use_case": f"UC{uc}",
                "package_present": bool(package and package[0].get("exists") is True),
                "controller_review_artifact_count": len(controller_review),
                "evidence_package_complete": bool(package and package[0].get("exists") is True and controller_review),
                "controller_review_artifacts": [item.get("path") for item in controller_review],
                "semantic_evaluator_verdict_refs": [],
                "semantic_evaluator_verdicts_required_for_acceptance": True,
            }
        )
    return groups


def build_claim_layers() -> dict[str, Any]:
    return {
        "overall": {
            "status": "ready_for_readiness_review_not_release_complete",
            "summary": "SuperLoop evidence supports a scoped readiness report, not final release readiness.",
        },
        "layers": {
            "source_tests": {
                "status": "proven_for_current_harness_slice",
                "basis": "current-worktree py_compile, unittest, and structural verifier runs",
            },
            "backend_container": {
                "status": "proven_for_dev_contextforge_surface",
                "basis": "UC13 dev Docker gateway and sidecar evidence on 127.0.0.1:4445",
            },
            "contextforge_route": {
                "status": "proven_for_selected_routes_and_services",
                "basis": "packaged controller-review evidence for UC4/UC5/UC8/UC11/UC13; not all services in all clients",
            },
            "target_client_visibility": {
                "status": "proven_for_pi_opencode_codex_project_init_surfaces",
                "basis": "accepted Codex parity reports through UC13 plus Pi/OpenCode earlier evidence",
            },
            "ordinary_interactive_proof": {
                "status": "proven_by_use_case_not_global_release",
                "basis": "dialogue packages plus semantic evaluator/controller-review artifacts for selected ordinary use cases",
            },
            "safe_call_proof": {
                "status": "partial",
                "basis": "selected tool-use cases have proof; OpenCode/Codex UC13 dev surfaces remain list/config-readback only",
            },
            "handoff_readiness": {
                "status": "not_yet_claimed",
                "basis": "UC15 remains pending",
            },
        },
        "clients": {
            "pi": {
                "strongest_layer": "ordinary_interactive_proof_for_selected_use_cases",
                "gap": "not a blanket all-service release claim",
            },
            "opencode": {
                "strongest_layer": "ordinary_interactive_proof_for_selected_use_cases",
                "gap": "UC13 dev surface is list-only without safe-call proof",
            },
            "codex": {
                "strongest_layer": "ordinary_interactive_proof_for_codex_parity_slices_and_config_readback_for_uc13",
                "gap": "UC13 dev surface is config/list-readback only without safe-call proof",
            },
        },
        "forbidden_overclaims": {
            "release_ready": False,
            "all_services_safe_called_in_all_clients": False,
            "uc13_is_dialogue_success": False,
            "live_legacy_contextforge_mutated": False,
        },
    }


def render_report(metadata: dict[str, Any]) -> str:
    layers = metadata["claim_layers"]["layers"]
    clients = metadata["claim_layers"]["clients"]
    missing = metadata["missing_required_artifacts"]
    lines = [
        "# Use Case 14 Readiness Report",
        "",
        "## Bottom Line",
        "",
        "The ContextForge project-init harness is ready for continued supervised use-case progression and review, but it is not yet a final release or handoff claim.",
        "",
        "The strongest current claim is scoped: Pi, OpenCode, and Codex have packaged controller-review evidence across the project-init SuperLoop slices, and the controlled development surface now includes all three clients. OpenCode and Codex still have explicit safe-call gaps where UC13 records only list/config-readback evidence.",
        "",
        "## Claim Ladder",
        "",
        "| Layer | Status | Basis |",
        "| --- | --- | --- |",
    ]
    for name, layer in layers.items():
        lines.append(f"| `{name}` | `{layer['status']}` | {layer['basis']} |")
    lines.extend(["", "## Client Readiness", "", "| Client | Strongest proven layer | Gap |", "| --- | --- | --- |"])
    for client, record in clients.items():
        lines.append(f"| `{client}` | `{record['strongest_layer']}` | {record['gap']} |")
    lines.extend(
        [
            "",
            "## Evidence Package",
            "",
            f"- Metadata: `{metadata['metadata_path']}`",
            f"- Verifier: `{metadata['verifier_path']}`",
            f"- Missing required artifacts: `{len(missing)}`",
            "",
            "## Non-Claims",
            "",
            "- This is not a final release-ready claim.",
            "- This is not a claim that every service has been safe-called in every client.",
            "- This is not a claim that UC13 proves semantic dialogue behavior.",
            "- This is not a claim that the live/legacy ContextForge surface was mutated.",
            "- This is not a claim that UC10 proves same-session hot MCP registration.",
            "- This is not a claim that UC12 registered, started, imported, or proved runtime readiness for `calendar-notes`.",
            "- This is not a claim that credential-scoped services have valid live credentials or provider behavior.",
            "- This is not a claim that Serena runtime indexing or LSP health is proven.",
            "",
            "## Next Step",
            "",
            "Proceed to UC15 only after this readiness report is reviewed and any blocking gaps are either remediated or explicitly carried as handoff risks.",
            "",
        ]
    )
    return "\n".join(lines)


def render_package(metadata: dict[str, Any], verifier: dict[str, Any], report_path: Path) -> str:
    return "\n".join(
        [
            "# Use Case 14 Readiness Evaluation Package",
            "",
            "## Generated Readiness Report",
            "",
            f"- `{report_path}`",
            "",
            "## Metadata",
            "",
            "```json",
            json.dumps(metadata, indent=2, sort_keys=True),
            "```",
            "",
            "## Verifier",
            "",
            "```json",
            json.dumps(verifier, indent=2, sort_keys=True),
            "```",
            "",
            "## Evaluator Instructions",
            "",
            "Review the generated readiness report against `docs/use-cases/use-case-14/package.md`.",
            "Judge whether it separates proven layers from gaps and avoids release, safe-call, or dialogue overclaims.",
            "Do not treat the deterministic verifier as a semantic judge of report prose.",
            "",
        ]
    )


def run_verifier(repo_root: Path, python: Path, metadata_path: Path) -> dict[str, Any]:
    completed = subprocess.run(
        [
            str(python),
            str(repo_root / "docker" / "client-harness" / "scripts" / "verify-use-case-14-readiness-evidence.py"),
            "--metadata",
            str(metadata_path),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        try:
            return json.loads(completed.stdout)
        except json.JSONDecodeError:
            return {
                "ok": False,
                "failures": [
                    {
                        "code": "verifier_command_failed",
                        "message": completed.stderr or completed.stdout or "verifier failed",
                    }
                ],
            }
    return json.loads(completed.stdout)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parents[3]
    python = repo_root / "run" / "test-venvs" / "project-init-workflow" / "bin" / "python"
    if Path(sys.executable).resolve() != python.resolve():
        raise SystemExit(f"run with {python}, not {sys.executable}")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_root = repo_root / "docker" / "client-harness" / "evidence" / "use-case-14"
    output_root.mkdir(parents=True, exist_ok=True)
    metadata_path = output_root / f"use-case-14-metadata-{timestamp}.json"
    verifier_path = output_root / f"use-case-14-verifier-{timestamp}.json"
    report_path = output_root / f"use-case-14-readiness-report-{timestamp}.md"
    package_path = output_root / f"use-case-14-evaluation-package-{timestamp}.md"

    evidence = build_evidence_inventory(repo_root)
    evidence_groups = build_use_case_evidence_groups(evidence)
    missing = [item for item in evidence if item.get("required") is True and item.get("exists") is not True]
    incomplete_groups = [group for group in evidence_groups if group.get("evidence_package_complete") is not True]
    metadata: dict[str, Any] = {
        "use_case": "use-case-14",
        "issue": 256,
        "timestamp": timestamp,
        "deterministic_checks_are_structural_only": True,
        "semantic_report_review_required": True,
        "clients": list(CLIENTS),
        "claim_layers": build_claim_layers(),
        "evidence_inventory": evidence,
        "use_case_evidence_groups": evidence_groups,
        "missing_required_artifacts": missing,
        "incomplete_use_case_evidence_groups": incomplete_groups,
        "metadata_path": str(metadata_path),
        "verifier_path": str(verifier_path),
        "readiness_report_path": str(report_path),
        "evaluation_package_path": str(package_path),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    verifier_result = run_verifier(repo_root, python, metadata_path)
    verifier_path.write_text(json.dumps(verifier_result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(render_report(metadata), encoding="utf-8")
    package_path.write_text(render_package(metadata, verifier_result, report_path), encoding="utf-8")

    summary = {
        "ok": bool(verifier_result.get("ok")),
        "metadata": str(metadata_path),
        "verifier": str(verifier_path),
        "readiness_report": str(report_path),
        "evaluation_package_markdown": str(package_path),
        "missing_required_artifacts": len(missing),
        "ok_scope": "readiness report structure only; semantic report judgment requires non-Spark evaluator",
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
