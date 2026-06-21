#!/usr/bin/env python3
"""Assemble Use Case 5l selection-shape evidence for evaluator review."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from harness_redaction import redact_text, redact_value


ISSUES = [247, 269, 259, 260, 261, 262, 263, 264, 265, 266, 267, 268, 270]
PR_NUMBER = 271


def run(command: list[str], *, cwd: Path, timeout: int = 120) -> dict[str, Any]:
    completed = subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=timeout, check=False)
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
            f"COMMAND: {redact_text(str(item['command_text']))}",
            f"RETURNCODE: {item['returncode']}",
            f"TIMEOUT: {str(item['timeout']).lower()}",
            "",
            "STDOUT:",
            redact_text(str(item.get("stdout") or "")),
            "",
            "STDERR:",
            redact_text(str(item.get("stderr") or "")),
        ]
    )


def github_context(repo_root: Path, commands: list[dict[str, Any]]) -> dict[str, Any]:
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
    pr_result = run(
        [
            "gh",
            "pr",
            "view",
            str(PR_NUMBER),
            "--json",
            "number,title,state,body,labels,projectItems,updatedAt,url,headRefName,baseRefName,mergeStateStatus",
        ],
        cwd=repo_root,
        timeout=60,
    )
    commands.append(pr_result)
    parsed_pr = parse_json(pr_result["stdout"])
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
        "returncode": pr_result["returncode"],
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
    commands: list[dict[str, Any]],
    metadata: dict[str, Any],
    verifier_path: Path | None = None,
    verifier_json: dict[str, Any] | None = None,
) -> str:
    lines = [
        "# Use Case 5l Selection-Shape Evidence",
        "",
        f"Timestamp: {timestamp}",
        "Use case: UC5l / issue #269 single, curated multi-service, and all-services selection-shape validation",
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
        lines.append(f"- `{redact_text(item['command_text'])}` -> rc={item['returncode']} timeout={item['timeout']}")
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
            "# Evaluation Package: Use Case 5l Selection Shapes",
            "",
            "Use case: single, curated multi-service, and all-services selection-shape validation for #247 (#269).",
            f"Combined evidence: `{evidence_path}`",
            f"Metadata: `{metadata_path}`",
            f"Verifier: `{verifier_path}`",
            f"Deterministic verifier ok: `{bool(verifier_json.get('ok'))}`",
            "Deterministic verifier scope: `structured source artifacts, command facts, JSON shape; not semantic selection-shape acceptance`",
            "Acceptance status: `requires_agent_evaluator_scoring`",
            "",
            "## Methodology",
            "",
            "This source-evidence package localizes the holistic SuperLoop for #269 selection-shape validation. The runner assembles current issue/PR bodies, source artifact summaries, focused test output, metadata, and structural verifier output. It does not score dialogue adequacy.",
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
            "- shape_coverage_single_curated_all: 20",
            "- pi_apply_readback: 15",
            "- opencode_apply_readback: 15",
            "- no_silent_omissions: 20",
            "- source_boundary: 10",
            "- deterministic_boundary: 10",
            "",
            "Fatal failures: missing any required selection shape, missing Pi/OpenCode coverage, all-services silent omission, skipped Serena language/provisioning boundary, global/client-home/trust/secret/live ContextForge mutation, provider credential exposure, #247 umbrella overclaim, target-client post-refresh tool-use overclaim, or deterministic semantic scoring of prose.",
            "",
            "Required evaluator narrative: summarize issue context, inspect the selection-shape evidence, assess single/curated/all shape coverage, assess Pi and OpenCode apply/readback boundaries, assess no-silent-omissions against the readiness matrix, score each criterion, and return PASS or FAIL.",
        ]
    ) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parents[3]
    harness_root = repo_root / "docker" / "client-harness"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_root = harness_root / "evidence" / "use-case-5l" / "selection-shapes"
    output_root.mkdir(parents=True, exist_ok=True)
    commands: list[dict[str, Any]] = []

    context = github_context(repo_root, commands)
    test_command = run(
        [sys.executable, "-m", "unittest", "tests.test_selection_shape_lifecycle", "-v"],
        cwd=repo_root,
        timeout=args.timeout,
    )
    commands.append(test_command)

    artifacts = {
        "taxonomy_contract": "docs/contextforge-service-localization-taxonomy.json",
        "readiness_matrix": "docs/contextforge-service-readiness-matrix.json",
        "source_test": "tests/test_selection_shape_lifecycle.py",
        "package": "docs/use-cases/use-case-5l-selection-shapes/package.md",
        "project_state_schema": "schemas/control-plane/project-state.schema.json",
        "helper": "scripts/control_plane_project_init_helper.py",
        "binding": "scripts/control_plane_contextforge_binding.py",
    }
    metadata = {
        "use_case": "use-case-5l-selection-shapes",
        "repo_root": str(repo_root),
        "timestamp": timestamp,
        "semantic_acceptance": "requires_agent_evaluation",
        "deterministic_boundary": "structured_source_artifacts_only",
        "selection_shapes": {
            "single": ["context7:canonical"],
            "curated": ["context7:canonical", "mentality:static_repo_local", "ssh-tmux:session_scoped"],
            "all_services": [
                "context7:canonical",
                "exa-search:credential_scoped",
                "github:canonical",
                "mentality:static_repo_local",
                "openzeppelin-solidity-contracts:canonical",
                "playwright:session_scoped",
                "ssh-tmux:session_scoped",
                "web-search:credential_scoped",
                "serena",
            ],
        },
        "artifacts": artifacts,
        "artifact_summaries": {key: file_summary(repo_root, value) for key, value in artifacts.items()},
        "github_context": context,
        "test_command": test_command,
    }

    metadata = redact_value(metadata)
    metadata_path = output_root / f"selection-shapes-metadata-{timestamp}.json"
    evidence_path = output_root / f"selection-shapes-use-case-5l-evidence-{timestamp}.md"
    package_path = output_root / f"selection-shapes-evaluation-package-{timestamp}.md"
    verifier_path = output_root / f"selection-shapes-verifier-{timestamp}.json"

    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    evidence_path.write_text(render_evidence(timestamp=timestamp, commands=commands, metadata=metadata), encoding="utf-8")
    verifier_script = Path(__file__).with_name("verify-use-case-5l-selection-shapes.py")
    verifier_command = run(
        [
            sys.executable,
            str(verifier_script),
            "--evidence",
            str(evidence_path),
            "--metadata",
            str(metadata_path),
        ],
        cwd=repo_root,
        timeout=args.timeout,
    )
    commands.append(verifier_command)
    verifier_json = parse_json(verifier_command["stdout"])
    if not isinstance(verifier_json, dict):
        verifier_json = {"ok": False, "failures": ["invalid_verifier_json"], "raw": verifier_json}
    verifier_path.write_text(json.dumps(verifier_json, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    evidence_path.write_text(
        render_evidence(
            timestamp=timestamp,
            commands=commands,
            metadata=metadata,
            verifier_path=verifier_path,
            verifier_json=verifier_json,
        ),
        encoding="utf-8",
    )
    package_path.write_text(
        render_package(
            evidence_path=evidence_path,
            metadata_path=metadata_path,
            verifier_path=verifier_path,
            verifier_json=verifier_json,
            metadata=metadata,
        ),
        encoding="utf-8",
    )

    ok = test_command["returncode"] == 0 and verifier_json.get("ok") is True
    print(
        json.dumps(
            {
                "use_case": "use-case-5l-selection-shapes",
                "evidence": str(evidence_path),
                "metadata": str(metadata_path),
                "evaluation_package": str(package_path),
                "verifier": str(verifier_path),
                "test_returncode": test_command["returncode"],
                "verifier_returncode": verifier_command["returncode"],
                "verifier_failures": verifier_json.get("failures"),
                "ok": ok,
                "requires_agent_evaluation": True,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
