#!/usr/bin/env python3
"""Run merge-queue validation in a disposable worktree.

The active project-local Codex config intentionally pins absolute paths for the
canonical checkout. A disposable validation worktree needs those paths to point
at itself so full test discovery can exercise the merged queue as a real
worktree without editing the canonical source tree by hand.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


DEFAULT_CANONICAL_ROOT = Path("/home/dgk/workspace/cf-controlplane")
DEFAULT_WORKTREE_PARENT = Path("/home/dgk/workspace")
RETIRED_NAME_LITERALS = (
    "context-" + "portal",
    "contextforge-" + "slices",
    "serena-" + "context-" + "portal",
    "contextforge://context-" + "portal",
)
DEFAULT_RETIRED_NAME_PATTERN = "|".join(RETIRED_NAME_LITERALS)


@dataclass(frozen=True)
class CommandResult:
    args: list[str]
    returncode: int
    stdout: str
    stderr: str


def run_command(
    args: Sequence[str],
    *,
    cwd: Path,
    check: bool = True,
    env: dict[str, str] | None = None,
) -> CommandResult:
    completed = subprocess.run(
        list(args),
        cwd=cwd,
        check=False,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    result = CommandResult(list(args), completed.returncode, completed.stdout, completed.stderr)
    if check and result.returncode != 0:
        raise RuntimeError(format_command_failure(result))
    return result


def format_command_failure(result: CommandResult) -> str:
    return (
        f"command failed with exit {result.returncode}: {' '.join(result.args)}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )


def replace_canonical_paths(text: str, *, canonical_root: Path, worktree_root: Path) -> str:
    canonical = canonical_root.as_posix()
    replacement = worktree_root.as_posix()
    if canonical == replacement:
        return text
    return text.replace(canonical, replacement)


def normalize_codex_config_paths(
    worktree_root: Path,
    *,
    canonical_root: Path = DEFAULT_CANONICAL_ROOT,
) -> dict[str, object]:
    config_path = worktree_root / ".codex" / "config.toml"
    before = config_path.read_text(encoding="utf-8")
    after = replace_canonical_paths(before, canonical_root=canonical_root, worktree_root=worktree_root)
    config_path.write_text(after, encoding="utf-8")
    return {
        "config_path": str(config_path),
        "canonical_root": str(canonical_root),
        "worktree_root": str(worktree_root),
        "replacements": before.count(canonical_root.as_posix()),
        "changed": before != after,
    }


def ensure_workspace_child(path: Path, *, parent: Path = DEFAULT_WORKTREE_PARENT) -> Path:
    resolved = path.expanduser().resolve(strict=False)
    resolved_parent = parent.expanduser().resolve(strict=False)
    try:
        resolved.relative_to(resolved_parent)
    except ValueError as exc:
        raise ValueError(f"dry-run worktree must be under {resolved_parent}: {resolved}") from exc
    if resolved == resolved_parent:
        raise ValueError(f"dry-run worktree must be a child of {resolved_parent}, not the parent itself")
    return resolved


def default_worktree_path(parent: Path = DEFAULT_WORKTREE_PARENT) -> Path:
    return parent / f"cf-controlplane-queue-dry-run-{int(time.time())}"


def create_worktree(*, repo_root: Path, base_ref: str, worktree_root: Path) -> None:
    run_command(["git", "fetch", "--quiet", "origin", "dev-root"], cwd=repo_root)
    run_command(["git", "worktree", "add", "--detach", str(worktree_root), base_ref], cwd=repo_root)


def remove_worktree(*, repo_root: Path, worktree_root: Path) -> None:
    result = run_command(
        ["git", "worktree", "remove", "--force", str(worktree_root)],
        cwd=repo_root,
        check=False,
    )
    if result.returncode != 0 and worktree_root.exists():
        shutil.rmtree(worktree_root, ignore_errors=True)


def dry_merge_heads(*, worktree_root: Path, heads: Sequence[str]) -> list[str]:
    merged: list[str] = []
    for head in heads:
        run_command(["git", "merge", "--no-edit", head], cwd=worktree_root)
        rev = run_command(["git", "rev-parse", "--short", "HEAD"], cwd=worktree_root)
        merged.append(rev.stdout.strip())
    return merged


def run_validation(
    *,
    repo_root: Path,
    worktree_root: Path,
    base_ref: str,
    heads: Sequence[str],
    canonical_root: Path,
    test_command: Sequence[str],
    retired_name_pattern: str,
    keep_worktree: bool,
) -> int:
    worktree_root = ensure_workspace_child(worktree_root)
    if worktree_root.exists():
        raise FileExistsError(f"dry-run worktree already exists: {worktree_root}")

    created = False
    try:
        create_worktree(repo_root=repo_root, base_ref=base_ref, worktree_root=worktree_root)
        created = True
        merged_revs = dry_merge_heads(worktree_root=worktree_root, heads=heads)
        normalization = normalize_codex_config_paths(worktree_root, canonical_root=canonical_root)

        test_env = os.environ.copy()
        test_env["CONTEXTFORGE_CONFIG_CONTRACT_ROOT"] = worktree_root.as_posix()
        test_result = run_command(test_command, cwd=worktree_root, env=test_env)
        diff_check = run_command(["git", "diff", "--check", f"{base_ref}...HEAD"], cwd=worktree_root)
        changed_files = run_command(["git", "diff", "--name-only", f"{base_ref}...HEAD"], cwd=worktree_root)
        changed_file_list = [line for line in changed_files.stdout.splitlines() if line.strip()]
        scan_result = CommandResult(["rg", retired_name_pattern], 1, "", "")
        if changed_file_list:
            scan_result = run_command(
                ["rg", "-n", retired_name_pattern, *changed_file_list],
                cwd=worktree_root,
                check=False,
            )
            if scan_result.returncode == 0:
                raise RuntimeError(
                    "retired-name scan found matches in changed queue files\n"
                    f"{scan_result.stdout}{scan_result.stderr}"
                )
            if scan_result.returncode not in {1}:
                raise RuntimeError(format_command_failure(scan_result))

        print("queue_dry_run_ok")
        print(f"worktree_root={worktree_root}")
        print(f"merged_revs={','.join(merged_revs)}")
        print(f"normalized_config={normalization}")
        print(f"tests_stdout_bytes={len(test_result.stdout)}")
        print(f"tests_stderr_bytes={len(test_result.stderr)}")
        print(f"diff_check_stdout_bytes={len(diff_check.stdout)}")
        print(f"changed_file_count={len(changed_file_list)}")
        print("retired_name_scan=0_matches")
        return 0
    finally:
        if created and not keep_worktree:
            remove_worktree(repo_root=repo_root, worktree_root=worktree_root)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_CANONICAL_ROOT)
    parser.add_argument("--base-ref", default="origin/dev-root")
    parser.add_argument("--head", action="append", required=True, help="Queue head SHA/ref to dry-merge in order.")
    parser.add_argument("--worktree-root", type=Path, default=None)
    parser.add_argument("--canonical-root", type=Path, default=DEFAULT_CANONICAL_ROOT)
    parser.add_argument("--keep-worktree", action="store_true")
    parser.add_argument("--retired-name-pattern", default=DEFAULT_RETIRED_NAME_PATTERN)
    parser.add_argument(
        "--test-command",
        nargs=argparse.REMAINDER,
        default=None,
        help="Command to run after dry-merge. Defaults to full unittest discovery.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    test_command = args.test_command or [
        str(args.canonical_root / ".venv/bin/python"),
        "-m",
        "unittest",
        "discover",
        "-s",
        "tests",
        "-v",
    ]
    worktree_root = args.worktree_root or default_worktree_path()
    return run_validation(
        repo_root=args.repo_root.expanduser().resolve(strict=False),
        worktree_root=worktree_root,
        base_ref=args.base_ref,
        heads=args.head,
        canonical_root=args.canonical_root.expanduser().resolve(strict=False),
        test_command=test_command,
        retired_name_pattern=args.retired_name_pattern,
        keep_worktree=args.keep_worktree,
    )


if __name__ == "__main__":
    sys.exit(main())
