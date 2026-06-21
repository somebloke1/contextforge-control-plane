#!/usr/bin/env python3
"""Generate Use Case 15 handoff evidence."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from harness_redaction import redact_text, redact_value


CLIENTS = ("pi", "opencode", "codex")
FOLLOW_UP_ISSUES = ("285", "286", "287", "289", "280", "257")


def latest(root: Path, pattern: str) -> Path:
    matches = sorted(root.glob(pattern))
    if not matches:
        raise SystemExit(f"missing required artifact matching {root / pattern}")
    return matches[-1]


def build_handoff() -> dict[str, Any]:
    return {
        "summary": "Use-case evidence supports continued supervised operation and handoff planning, not release promotion.",
        "client_operating_notes": {
            "pi": {
                "what_works": "Pi has reviewed ordinary dialogue evidence across the project-init path, including selected read-only tool use.",
                "how_to_use": "Use the Docker client harness runners for repeatable tests, for example `run-use-case-8-dialogue.py --client pi` for Context7 tool-use behavior.",
                "evidence": [
                    "run/holistic-orchestrator/reports/uc1-controller-acceptance-20260620T010301Z.md",
                    "run/holistic-orchestrator/reports/uc8-codex-parity-acceptance-20260620T185331Z.md",
                    "docker/client-harness/evidence/pi-contextforge-dev-smoke.txt",
                ],
                "gap": "not a blanket all-service or credential-validity claim",
                "next_action": "Use Pi as the strongest interactive foil for regressions that need ordinary dialogue behavior.",
            },
            "opencode": {
                "what_works": "OpenCode has reviewed ordinary dialogue evidence for the scoped use cases and controlled dev MCP list evidence.",
                "how_to_use": "Use Docker harness runners, for example `run-use-case-8-dialogue.py --client opencode`; treat UC13 dev smoke as list-only unless a reviewed safe-call command is supplied.",
                "evidence": [
                    "docs/use-cases/use-case-8/controller-acceptance-20260620.md",
                    "run/holistic-orchestrator/reports/uc10-codex-parity-acceptance-20260620T193900Z.md",
                    "docker/client-harness/evidence/opencode-contextforge-dev-smoke.txt",
                ],
                "gap": "UC13 OpenCode dev surface is not safe-call proof",
                "next_action": "Add reviewed safe-call proof only through a later bounded issue or use case.",
            },
            "codex": {
                "what_works": "Codex has parity evidence through UC14 using Docker-only OAuth/subscription auth and `gpt-5.4-mini`.",
                "how_to_use": "Use the authenticated Docker baseline only; do not use host Codex or API-key auth. Use `run-codex-authenticated.sh` or UC runners with `--client codex`.",
                "evidence": [
                    "run/holistic-orchestrator/reports/uc13-codex-parity-acceptance-20260620T200100Z.md",
                    "run/holistic-orchestrator/reports/uc14-controller-acceptance-20260620T201400Z.md",
                    "docker/client-harness/evidence/codex-contextforge-dev-smoke.txt",
                ],
                "gap": "UC13 Codex dev surface is config/list-readback only without safe-call proof",
                "next_action": "Keep Codex changes Docker-only until a separate host-safe client promotion decision exists.",
            },
        },
        "covered_flow_claims": {
            "activation": "UC1 install/reload boundary has packaged review evidence for Pi/OpenCode/Codex.",
            "readback_and_capabilities": "UC2/UC3/UC7 have packaged initialized-state and capability/readiness-layer readback evidence.",
            "tool_use": "UC4 and UC8/UC11 provide reviewed evidence for selected read-only governance/Context7 tool-use paths, not every service.",
            "cross_client_state": "UC9/UC10 provide reviewed evidence for pre-aligned cross-client readback and refresh behavior, not automatic new-client alignment.",
            "service_onboarding": "UC12 provides reviewed source-only onboarding handoff evidence, not runtime registration for calendar-notes.",
            "readiness": "UC14 is the current scoped readiness artifact.",
        },
        "issue_owners": {
            "#285": "explicit client alignment/import helper follow-up",
            "#286": "cross-client disparity/readback vocabulary follow-up",
            "#287": "project graph/projection architecture follow-up",
            "#289": "placeholder or low-quality response regression guard",
            "#280": "venv-friction historical issue; read current labels before relying on it for service-set parity",
        },
        "next_actions": [
            "Use UC14 readiness report as the current scoped readiness artifact.",
            "Keep #285/#286/#287 visible before making stronger cross-client projection claims.",
            "Do not close or release-promote without PR review and current Project readback.",
        ],
        "non_claims": [
            "not release readiness",
            "not all-service safe-call proof",
            "not credential validity",
            "not Serena runtime indexing or LSP health",
            "not UC10 same-session hot registration",
            "not UC12 calendar-notes runtime readiness",
            "not live/legacy ContextForge mutation",
        ],
    }


def read_issue_statuses(repo_root: Path) -> dict[str, Any]:
    statuses: dict[str, Any] = {}
    for number in FOLLOW_UP_ISSUES:
        completed = subprocess.run(
            ["gh", "issue", "view", number, "--json", "number,title,state,url,labels,projectItems"],
            cwd=repo_root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if completed.returncode != 0:
            statuses[f"#{number}"] = {"read_ok": False, "error": completed.stderr.strip()}
            continue
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            statuses[f"#{number}"] = {"read_ok": False, "error": exc.msg}
            continue
        statuses[f"#{number}"] = {
            "read_ok": True,
            "number": payload.get("number"),
            "title": payload.get("title"),
            "state": payload.get("state"),
            "url": payload.get("url"),
            "project_items": payload.get("projectItems"),
            "labels": [label.get("name") for label in payload.get("labels", []) if isinstance(label, dict)],
        }
    return statuses


def render_handoff(metadata: dict[str, Any]) -> str:
    handoff = metadata["handoff"]
    lines = [
        "# Use Case 15 Project Handoff",
        "",
        "## Current Status",
        "",
        handoff["summary"],
        "",
        f"Readiness report: `{metadata['uc14_readiness_report_path']}`",
        "",
        "## Client Operating Notes",
        "",
    ]
    for client, note in handoff["client_operating_notes"].items():
        lines.extend(
            [
                f"### {client}",
                "",
                f"- What works: {note['what_works']}",
                f"- How to use: {note['how_to_use']}",
                f"- Gap: {note['gap']}",
                f"- Next action: {note['next_action']}",
                "- Evidence:",
            ]
        )
        for evidence in note["evidence"]:
            lines.append(f"  - `{evidence}`")
        lines.append("")
    lines.extend(["## Covered Flow Claims", ""])
    for flow, summary in handoff["covered_flow_claims"].items():
        lines.append(f"- `{flow}`: {summary}")
    lines.extend(["", "## Follow-Up Ownership", ""])
    for issue, owner in handoff["issue_owners"].items():
        status = metadata["issue_statuses"].get(issue, {})
        status_text = f"{status.get('state', 'unknown')} - {status.get('title', 'unread')}" if status.get("read_ok") else "readback unavailable"
        lines.append(f"- `{issue}`: {owner}; status: {status_text}")
    lines.extend(["", "## Next Actions", ""])
    for action in handoff["next_actions"]:
        lines.append(f"- {action}")
    lines.extend(["", "## Non-Claims", ""])
    for non_claim in handoff["non_claims"]:
        lines.append(f"- {non_claim}")
    lines.append("")
    return "\n".join(lines)


def run_verifier(repo_root: Path, python: Path, metadata_path: Path) -> dict[str, Any]:
    completed = subprocess.run(
        [
            str(python),
            str(repo_root / "docker" / "client-harness" / "scripts" / "verify-use-case-15-handoff-evidence.py"),
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
            return {"ok": False, "failures": [{"code": "verifier_command_failed", "message": completed.stderr or completed.stdout}]}
    return json.loads(completed.stdout)


def render_package(metadata: dict[str, Any], verifier: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Use Case 15 Handoff Evaluation Package",
            "",
            f"- Handoff report: `{metadata['handoff_report_path']}`",
            f"- UC14 readiness report: `{metadata['uc14_readiness_report_path']}`",
            "",
            "## Metadata",
            "",
            "```json",
            json.dumps(redact_value(metadata), indent=2, sort_keys=True),
            "```",
            "",
            "## Verifier",
            "",
            "```json",
            json.dumps(redact_value(verifier), indent=2, sort_keys=True),
            "```",
            "",
            "Evaluator: judge whether the handoff is clear, honest, and actionable without treating deterministic checks as prose judgment.",
            "",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    repo_root = Path(__file__).resolve().parents[3]
    python = repo_root / "run" / "test-venvs" / "project-init-workflow" / "bin" / "python"
    if Path(sys.executable).resolve() != python.resolve():
        raise SystemExit(f"run with {python}, not {sys.executable}")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_root = repo_root / "docker" / "client-harness" / "evidence" / "use-case-15"
    output_root.mkdir(parents=True, exist_ok=True)
    uc14_report = latest(repo_root / "docker" / "client-harness" / "evidence" / "use-case-14", "use-case-14-readiness-report-*.md")
    metadata_path = output_root / f"use-case-15-metadata-{timestamp}.json"
    verifier_path = output_root / f"use-case-15-verifier-{timestamp}.json"
    handoff_path = output_root / f"use-case-15-handoff-{timestamp}.md"
    package_path = output_root / f"use-case-15-evaluation-package-{timestamp}.md"
    metadata: dict[str, Any] = {
        "use_case": "use-case-15",
        "issue": 257,
        "timestamp": timestamp,
        "deterministic_checks_are_structural_only": True,
        "semantic_handoff_review_required": True,
        "clients": list(CLIENTS),
        "uc14_readiness_report_path": str(uc14_report),
        "handoff": build_handoff(),
        "issue_statuses": read_issue_statuses(repo_root),
        "metadata_path": str(metadata_path),
        "verifier_path": str(verifier_path),
        "handoff_report_path": str(handoff_path),
        "evaluation_package_path": str(package_path),
    }
    metadata_path.write_text(json.dumps(redact_value(metadata), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    handoff_path.write_text(render_handoff(metadata), encoding="utf-8")
    package_path.write_text(render_package(metadata, {"ok": None, "status": "pending"}), encoding="utf-8")
    verifier = run_verifier(repo_root, python, metadata_path)
    verifier_path.write_text(json.dumps(redact_value(verifier), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    package_path.write_text(render_package(metadata, verifier), encoding="utf-8")
    summary = {
        "ok": bool(verifier.get("ok")),
        "metadata": str(metadata_path),
        "verifier": str(verifier_path),
        "handoff_report": str(handoff_path),
        "evaluation_package_markdown": str(package_path),
        "ok_scope": "handoff structure only; semantic handoff judgment requires non-Spark evaluator",
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
