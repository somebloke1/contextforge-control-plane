#!/usr/bin/env python3
"""Assemble Use Case 5a taxonomy evidence for semantic evaluator review."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ISSUES = [247, 270, 259, 260]
PR_NUMBER = 271


def run(command: list[str], *, cwd: Path, timeout: int = 120) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    return {
        "command": command,
        "command_text": " ".join(command),
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "timeout": False,
    }


def parse_json(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw": text}


def command_block(item: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"COMMAND: {item['command_text']}",
            f"RETURNCODE: {item['returncode']}",
            f"TIMEOUT: {str(item['timeout']).lower()}",
            "",
            "STDOUT:",
            item.get("stdout") or "",
            "",
            "STDERR:",
            item.get("stderr") or "",
        ]
    )


def github_issue_context(repo_root: Path, commands: list[dict[str, Any]]) -> dict[str, Any]:
    context: dict[str, Any] = {}
    for number in ISSUES:
        result = run(
            [
                "gh",
                "issue",
                "view",
                str(number),
                "--json",
                "number,title,state,body,labels,projectItems,updatedAt,url",
            ],
            cwd=repo_root,
            timeout=60,
        )
        commands.append(result)
        parsed = parse_json(result["stdout"])
        context[f"issue_{number}"] = {
            "number": parsed.get("number") if isinstance(parsed, dict) else number,
            "title": parsed.get("title") if isinstance(parsed, dict) else None,
            "state": parsed.get("state") if isinstance(parsed, dict) else None,
            "body": parsed.get("body") if isinstance(parsed, dict) else None,
            "updatedAt": parsed.get("updatedAt") if isinstance(parsed, dict) else None,
            "url": parsed.get("url") if isinstance(parsed, dict) else None,
            "projectItems": parsed.get("projectItems") if isinstance(parsed, dict) else None,
            "returncode": result["returncode"],
        }
    pr = run(
        [
            "gh",
            "pr",
            "view",
            str(PR_NUMBER),
            "--json",
            "number,title,state,body,labels,projectItems,updatedAt,url,headRefName,baseRefName,mergeStateStatus,statusCheckRollup",
        ],
        cwd=repo_root,
        timeout=60,
    )
    commands.append(pr)
    parsed_pr = parse_json(pr["stdout"])
    context[f"pr_{PR_NUMBER}"] = {
        "number": parsed_pr.get("number") if isinstance(parsed_pr, dict) else PR_NUMBER,
        "title": parsed_pr.get("title") if isinstance(parsed_pr, dict) else None,
        "state": parsed_pr.get("state") if isinstance(parsed_pr, dict) else None,
        "body": parsed_pr.get("body") if isinstance(parsed_pr, dict) else None,
        "updatedAt": parsed_pr.get("updatedAt") if isinstance(parsed_pr, dict) else None,
        "url": parsed_pr.get("url") if isinstance(parsed_pr, dict) else None,
        "headRefName": parsed_pr.get("headRefName") if isinstance(parsed_pr, dict) else None,
        "baseRefName": parsed_pr.get("baseRefName") if isinstance(parsed_pr, dict) else None,
        "mergeStateStatus": parsed_pr.get("mergeStateStatus") if isinstance(parsed_pr, dict) else None,
        "projectItems": parsed_pr.get("projectItems") if isinstance(parsed_pr, dict) else None,
        "returncode": pr["returncode"],
    }
    return context


def file_summary(repo_root: Path, relative_path: str) -> dict[str, Any]:
    path = repo_root / relative_path
    return {
        "path": relative_path,
        "exists": path.exists(),
        "bytes": path.stat().st_size if path.exists() else 0,
    }


def render_evidence(
    *,
    timestamp: str,
    repo_root: Path,
    commands: list[dict[str, Any]],
    metadata: dict[str, Any],
    verifier_path: Path | None = None,
    verifier_json: dict[str, Any] | None = None,
) -> str:
    lines = [
        "# Use Case 5a Taxonomy Evidence",
        "",
        f"Timestamp: {timestamp}",
        "Use case: UC5a / issue #270 service localization taxonomy",
        "Evidence kind: source/docs/tests package; no target-client dialogue in this slice",
        "",
        "## Artifact Summary",
        "",
        "```json",
        json.dumps(metadata["artifact_summaries"], indent=2, sort_keys=True),
        "```",
        "",
        "## GitHub Context",
        "",
        "```json",
        json.dumps(metadata["github_context"], indent=2, sort_keys=True),
        "```",
        "",
        "## Test Command",
        "",
        "```text",
        command_block(metadata["test_command"]),
        "```",
        "",
        "## Command Ledger",
        "",
    ]
    for item in commands:
        lines.append(f"- `{item['command_text']}` -> rc={item['returncode']} timeout={item['timeout']}")
    if verifier_path is not None and verifier_json is not None:
        lines.extend(
            [
                "",
                "## Structural Verifier",
                "",
                f"Verifier: `{verifier_path}`",
                "",
                "```json",
                json.dumps(verifier_json, indent=2, sort_keys=True),
                "```",
            ]
        )
    return "\n".join(lines) + "\n"


def render_package(
    *,
    evidence_path: Path,
    metadata_path: Path,
    verifier_path: Path,
    verifier_json: dict[str, Any],
    metadata: dict[str, Any],
) -> str:
    return "\n".join(
        [
            "# Evaluation Package: Use Case 5a Taxonomy",
            "",
            "Use case: Service localization taxonomy for #247 readiness (#270).",
            f"Combined evidence: `{evidence_path}`",
            f"Metadata: `{metadata_path}`",
            f"Verifier: `{verifier_path}`",
            f"Deterministic verifier ok: `{bool(verifier_json.get('ok'))}`",
            "Deterministic verifier scope: `structured source artifacts, command facts, JSON shape; not semantic artifact acceptance`",
            "Acceptance status: `requires_agent_evaluator_scoring`",
            "",
            "## Methodology",
            "",
            "This source-evidence package localizes the holistic SuperLoop for a non-dialogue prerequisite slice. The runner assembles current issue/PR context, source artifact summaries, focused test output, metadata, and structural verifier output. It does not score the architecture or prose meaning of the taxonomy.",
            "",
            "## Source Artifacts",
            "",
            "```json",
            json.dumps(metadata["artifact_summaries"], indent=2, sort_keys=True),
            "```",
            "",
            "## Scorecard",
            "",
            "- issue_context_refreshed: 10",
            "- structured_taxonomy_contract: 20",
            "- menu_example_mapping: 15",
            "- readiness_matrix_consumability: 15",
            "- architecture_boundary: 15",
            "- evidence_requirements: 15",
            "- deterministic_boundary: 10",
            "",
            "Fatal failures: missing required lifecycle class, no structured taxonomy contract, helper menu omission, `None` treated as service readiness, client/global bootstrap conflated with project service activation, or deterministic semantic scoring of prose.",
            "",
            "Required evaluator narrative: summarize issue context, inspect the taxonomy and matrix artifacts, explain whether #259/#247 can consume the taxonomy safely, identify any false-readiness risk, score each criterion, and return PASS or FAIL.",
        ]
    ) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parents[3]
    harness_root = repo_root / "docker" / "client-harness"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_root = harness_root / "evidence" / "use-case-5a" / "taxonomy"
    output_root.mkdir(parents=True, exist_ok=True)
    commands: list[dict[str, Any]] = []

    github_context = github_issue_context(repo_root, commands)
    test_command = run(
        [
            sys.executable,
            "-m",
            "unittest",
            "tests.test_service_readiness_matrix",
            "-v",
        ],
        cwd=repo_root,
        timeout=args.timeout,
    )
    commands.append(test_command)

    artifacts = {
        "taxonomy_markdown": "docs/contextforge-service-localization-taxonomy.md",
        "taxonomy_contract": "docs/contextforge-service-localization-taxonomy.json",
        "readiness_matrix": "docs/contextforge-service-readiness-matrix.json",
        "source_test": "tests/test_service_readiness_matrix.py",
        "package": "docs/use-cases/use-case-5a/package.md",
    }
    metadata = {
        "use_case": "use-case-5a",
        "repo_root": str(repo_root),
        "timestamp": timestamp,
        "semantic_acceptance": "requires_agent_evaluation",
        "deterministic_boundary": "structured_source_artifacts_only",
        "artifacts": artifacts,
        "artifact_summaries": {key: file_summary(repo_root, value) for key, value in artifacts.items()},
        "github_context": github_context,
        "test_command": test_command,
    }

    metadata_path = output_root / f"taxonomy-metadata-{timestamp}.json"
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    evidence_path = output_root / f"taxonomy-use-case-5a-evidence-{timestamp}.md"
    evidence_path.write_text(render_evidence(timestamp=timestamp, repo_root=repo_root, commands=commands, metadata=metadata), encoding="utf-8")

    verifier_result = run(
        [
            sys.executable,
            str(harness_root / "scripts" / "verify-use-case-5a-taxonomy.py"),
            "--evidence",
            str(evidence_path),
            "--metadata",
            str(metadata_path),
        ],
        cwd=repo_root,
        timeout=60,
    )
    commands.append(verifier_result)
    verifier_json = parse_json(verifier_result["stdout"])
    verifier_path = output_root / f"taxonomy-verifier-{timestamp}.json"
    verifier_path.write_text(json.dumps(verifier_json, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    evidence_path.write_text(
        render_evidence(
            timestamp=timestamp,
            repo_root=repo_root,
            commands=commands,
            metadata=metadata,
            verifier_path=verifier_path,
            verifier_json=verifier_json if isinstance(verifier_json, dict) else {},
        ),
        encoding="utf-8",
    )
    package_path = output_root / f"taxonomy-evaluation-package-{timestamp}.md"
    package_path.write_text(
        render_package(
            evidence_path=evidence_path,
            metadata_path=metadata_path,
            verifier_path=verifier_path,
            verifier_json=verifier_json if isinstance(verifier_json, dict) else {},
            metadata=metadata,
        ),
        encoding="utf-8",
    )

    summary = {
        "ok": bool(isinstance(verifier_json, dict) and verifier_json.get("ok")) and test_command["returncode"] == 0,
        "ok_scope": "source evidence package assembled; not semantic acceptance",
        "semantic_acceptance": "requires_agent_evaluation",
        "use_case": "use-case-5a",
        "combined_evidence": str(evidence_path),
        "metadata": str(metadata_path),
        "evaluation_package_markdown": str(package_path),
        "verifier": str(verifier_path),
        "verifier_failures": verifier_json.get("failures") if isinstance(verifier_json, dict) else None,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
