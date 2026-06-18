#!/usr/bin/env python3
"""Generate a compact SuperLoop re-entry card for resumed operators.

The report is read-only and uses local git evidence where available plus
explicitly supplied scope inputs for issue/PR/project context.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence


PROHIBITED_SURFACES: tuple[str, ...] = (
    "legacy/live ContextForge mutation",
    "runtime/services",
    "process/systemd",
    "ContextForge registry",
    "Docker",
    "client/global config",
    "hook trust/state",
    "runtime secrets/OAuth/trust tokens",
    "helper apply/recovery state",
    "Serena provisioning",
    "project-init state writes",
    "retired legacy checkout mutation",
)


@dataclass(frozen=True)
class GitSummary:
    branch: str
    base: str
    merge_base: str | None
    ahead: int | None
    behind: int | None
    clean: bool


def _normalize_issue_or_pr(raw: str | None) -> str | None:
    if raw is None:
        return None
    value = raw.strip()
    return value[1:] if value.startswith("#") else value


def _run_git(
    args: Sequence[str],
    *,
    cwd: Path,
    runner: Callable[[Sequence[str], Path], subprocess.CompletedProcess[str]],
) -> str:
    result = runner(["git", *args], cwd=cwd, check=False, text=True, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"git {" ".join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def _default_git_runner(args: Sequence[str], cwd: Path, **kwargs: Any) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, **kwargs)


def _to_int(raw: str | None) -> int | None:
    if raw is None:
        return None
    value = raw.strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _git_summary(*, base: str, repo_root: Path, runner: Callable[[Sequence[str], Path], subprocess.CompletedProcess[str]]) -> GitSummary:
    branch = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_root, runner=runner)
    if branch == "HEAD":
        branch = "detached"

    status_output = _run_git(["status", "--short", "--branch"], cwd=repo_root, runner=runner)
    status_lines = [line for line in status_output.splitlines() if line.strip()]
    clean = all(line.startswith("##") for line in status_lines)

    try:
        merge_base = _run_git(["merge-base", base, branch], cwd=repo_root, runner=runner)
    except RuntimeError:
        merge_base = None

    try:
        ahead = _to_int(_run_git(["rev-list", "--count", f"{base}..{branch}"], cwd=repo_root, runner=runner))
    except RuntimeError:
        ahead = None

    try:
        behind = _to_int(_run_git(["rev-list", "--count", f"{branch}..{base}"], cwd=repo_root, runner=runner))
    except RuntimeError:
        behind = None

    return GitSummary(branch=branch, base=base, merge_base=merge_base, ahead=ahead, behind=behind, clean=clean)


def _compact_next_action(
    *,
    git_summary: GitSummary,
    issue: str | None,
    pr: str | None,
    project_item: str | None,
) -> str:
    if not issue and not pr and not project_item:
        return (
            "Re-run with explicit issue/PR/project scope inputs before any state-changing action. "
            "This resume card is intentionally conservative until scope is explicit."
        )

    if not git_summary.clean:
        return (
            "Worktree is dirty. Stage, stash, or commit current local edits before resuming resume work "
            "to preserve operator continuity and auditability."
        )

    if git_summary.behind and git_summary.behind > 0:
        return "Rebase or fast-forward branch against base relation before coordination actions, then resume."

    return (
        "Proceed read-only: reconcile controller/issue context, then continue SuperLoop re-entry from this card "
        "without runtime, system, or service mutations."
    )


def build_reentry_card(
    *,
    repo_root: Path,
    issue: str | None = None,
    issue_state: str | None = None,
    issue_title: str | None = None,
    pr: str | None = None,
    pr_state: str | None = None,
    project_item: str | None = None,
    project_state: str | None = None,
    base: str = "origin/dev-root",
    controller_run_id: str | None = None,
    worker_agent_id: str | None = None,
    runner: Callable[[Sequence[str], Path], subprocess.CompletedProcess[str]] | None = None,
) -> dict[str, Any]:
    resolved_runner = runner or _default_git_runner
    git_summary = _git_summary(base=base, repo_root=repo_root, runner=resolved_runner)

    issue_value = _normalize_issue_or_pr(issue)
    pr_value = _normalize_issue_or_pr(pr)

    evidence_authority: list[dict[str, Any]] = [
        {
            "source": "local git",
            "surface": "read-only",
            "commands": [
                "git status --short --branch",
                "git rev-parse --abbrev-ref HEAD",
                "git merge-base",
                "git rev-list --count base..HEAD",
                "git rev-list --count HEAD..base",
            ],
        }
    ]

    explicit_inputs: list[str] = []
    if issue_value:
        explicit_inputs.append("issue")
    if pr_value:
        explicit_inputs.append("pr")
    if project_item:
        explicit_inputs.append("project_item")

    if explicit_inputs:
        evidence_authority.append(
            {
                "source": "explicit inputs",
                "surface": "operator-provided",
                "items": explicit_inputs,
            }
        )

    card = {
        "reentry_identity": {
            "controller_run_id": controller_run_id or "unset",
            "worker_agent_id": worker_agent_id or "unset",
        },
        "branch_state": {
            "branch": git_summary.branch,
            "base": git_summary.base,
            "merge_base": git_summary.merge_base,
            "ahead": git_summary.ahead,
            "behind": git_summary.behind,
            "clean": git_summary.clean,
        },
        "active_scope": {
            "issue": {
                "id": issue_value or "placeholder",
                "state": issue_state or "placeholder",
                "title": issue_title or "placeholder",
            },
            "pull_request": {
                "id": pr_value or "placeholder",
                "state": pr_state or "placeholder",
            },
            "project_item": {
                "id": project_item or "placeholder",
                "state": project_state or "placeholder",
            },
        },
        "evidence_authority": evidence_authority,
        "prohibited_surfaces": list(PROHIBITED_SURFACES),
        "next_safe_action": _compact_next_action(
            git_summary=git_summary,
            issue=issue_value,
            pr=pr_value,
            project_item=project_item,
        ),
    }

    return card


def render_card_text(card: Mapping[str, Any], *, compact: bool = True) -> str:
    branch = card["branch_state"]
    scope = card["active_scope"]

    rows: list[str] = [
        "SuperLoop Re-entry Card",
        "- identity: controller={controller_run_id}, worker={worker_agent_id}".format(
            **card["reentry_identity"],
        ),
        f"- branch: {branch['branch']} (base={branch['base']}, ahead={branch['ahead']}, behind={branch['behind']}, clean={branch['clean']})",
        f"- merge_base: {branch['merge_base'] or 'unknown'}",
        f"- issue: {scope['issue']['id']} | state={scope['issue']['state']} | title={scope['issue']['title']}",
        f"- pull_request: {scope['pull_request']['id']} | state={scope['pull_request']['state']}",
        f"- project_item: {scope['project_item']['id']} | state={scope['project_item']['state']}",
        f"- evidence_authority: {', '.join(item['source'] + ':' + item['surface'] for item in card['evidence_authority'])}",
        f"- prohibited_surfaces: {', '.join(card['prohibited_surfaces'])}",
        f"- next_safe_action: {card['next_safe_action']}",
    ]

    if compact:
        return "\n".join(rows)

    payload = json.dumps(card, indent=2, sort_keys=True)
    return "\n".join(rows + ["- payload:", payload])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a compact SuperLoop re-entry card")
    parser.add_argument("--issue", default=None)
    parser.add_argument("--issue-state", default=None)
    parser.add_argument("--issue-title", default=None)
    parser.add_argument("--pr", default=None)
    parser.add_argument("--pr-state", default=None)
    parser.add_argument("--project-item", default=None)
    parser.add_argument("--project-state", default=None)
    parser.add_argument("--base", default="origin/dev-root")
    parser.add_argument("--controller-run-id", default=None)
    parser.add_argument("--worker-agent-id", default=None)
    parser.add_argument("--workspace", type=Path, default=Path("."))
    parser.add_argument("--format", choices=("text", "json"), default="text")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    card = build_reentry_card(
        repo_root=args.workspace,
        issue=args.issue,
        issue_state=args.issue_state,
        issue_title=args.issue_title,
        pr=args.pr,
        pr_state=args.pr_state,
        project_item=args.project_item,
        project_state=args.project_state,
        base=args.base,
        controller_run_id=args.controller_run_id,
        worker_agent_id=args.worker_agent_id,
        runner=None,
    )

    if args.format == "json":
        print(json.dumps(card, indent=2, sort_keys=True))
    else:
        print(render_card_text(card))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
