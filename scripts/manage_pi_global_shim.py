#!/usr/bin/env python3
"""Plan or apply installation of the user-global Pi ContextForge shim."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from project_init_common import client_reload_requirement, stable_digest


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = REPO_ROOT / "pi-extensions" / "contextforge-global-shim"
TARGET_DIR = Path.home() / ".pi" / "agent" / "extensions" / "contextforge-global-shim"
CONFIRM_FLAG = "I_APPROVE_USER_GLOBAL_PI_EXTENSION_WRITE"
ROOT_CONFIG = "contextforge-root.json"
SHIM_FILES = ("index.ts", "README.md", "package.json")


def file_digest(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    return stable_digest(path.read_text(encoding="utf-8"))


def root_config_payload(repo_root: Path = REPO_ROOT) -> dict[str, str]:
    return {
        "portalRoot": str(repo_root),
        "schema": "contextforge.pi-shim-root.v1",
    }


def read_root_config(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return dict(data) if isinstance(data, dict) else None


def write_root_config(target_dir: Path, repo_root: Path = REPO_ROOT) -> None:
    payload = root_config_payload(repo_root)
    (target_dir / ROOT_CONFIG).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def directory_status(source_dir: Path = SOURCE_DIR, target_dir: Path = TARGET_DIR) -> dict[str, Any]:
    source_index = source_dir / "index.ts"
    target_index = target_dir / "index.ts"
    source_digest = file_digest(source_index)
    target_digest = file_digest(target_index)
    expected_root_config = root_config_payload()
    target_root_config = read_root_config(target_dir / ROOT_CONFIG)
    files_match = all(
        file_digest(source_dir / filename) == file_digest(target_dir / filename)
        for filename in SHIM_FILES
        if (source_dir / filename).exists()
    )
    root_config_matches = target_root_config == expected_root_config
    if not source_index.exists():
        status = "source_missing"
    elif not target_index.exists():
        status = "not_installed"
    elif files_match and root_config_matches:
        status = "installed_current"
    else:
        status = "installed_different"
    return {
        "status": status,
        "source_dir": str(source_dir),
        "target_dir": str(target_dir),
        "source_index": str(source_index),
        "target_index": str(target_index),
        "root_config": str(target_dir / ROOT_CONFIG),
        "expected_root_config": expected_root_config,
        "target_root_config": target_root_config,
        "source_digest": source_digest,
        "target_digest": target_digest,
        "non_actions": [
            "status and plan do not mutate user-global Pi files",
            "ordinary project activation does not install or upgrade this extension",
            "no secrets or token material are written",
        ],
    }


def install_plan(source_dir: Path = SOURCE_DIR, target_dir: Path = TARGET_DIR) -> dict[str, Any]:
    status = directory_status(source_dir, target_dir)
    reload_requirement = client_reload_requirement("pi", event="global_extension_install_or_upgrade")
    return {
        **status,
        "operation": "install_or_upgrade_user_global_pi_extension",
        "requires_explicit_confirmation": CONFIRM_FLAG,
        "planned_writes": [str(target_dir / filename) for filename in (*SHIM_FILES, ROOT_CONFIG)],
        "planned_non_writes": [
            str(Path.home() / ".pi" / "agent" / "settings.json"),
            str(Path.home() / ".pi" / "agent" / "extensions" / "mcp-bridge"),
        ],
        "client_reload": reload_requirement,
        "next_turn": {
            "question_id": "pi-client-reload-after-install",
            "prompt": "Issue /reload in Pi so the newly installed ContextForge tools register.",
            "choices": [
                {
                    "number": 1,
                    "id": "issue_reload",
                    "label": "Issue /reload",
                    "effect": "Reload Pi extension code so the newly installed or changed ContextForge shim is available.",
                }
            ],
            "response_form": {
                "type": "single_select",
                "options": [
                    {
                        "number": 1,
                        "id": "issue_reload",
                        "label": "Issue /reload",
                        "effect": "Reload Pi extension code so the newly installed or changed ContextForge shim is available.",
                    }
                ],
                "respond_with": "selection number or option id",
            },
            "allowed_response_shape": "issue /reload in Pi, then resume project init from the reloaded Pi session",
            "must_stop": True,
        },
    }


def apply_install(source_dir: Path, target_dir: Path, confirmation: str | None) -> dict[str, Any]:
    if confirmation != CONFIRM_FLAG:
        raise ValueError(f"refusing user-global Pi extension write without --confirm {CONFIRM_FLAG}")
    source_index = source_dir / "index.ts"
    if not source_index.exists():
        raise FileNotFoundError(source_index)
    target_dir.mkdir(parents=True, exist_ok=True)
    for filename in SHIM_FILES:
        source = source_dir / filename
        if source.exists():
            shutil.copy2(source, target_dir / filename)
    write_root_config(target_dir)
    reload_requirement = client_reload_requirement("pi", event="global_extension_install_or_upgrade")
    return {
        "status": "installed",
        **directory_status(source_dir, target_dir),
        "client_reload": reload_requirement,
        "next_action": reload_requirement["instruction"] if reload_requirement else None,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manage the user-global Pi ContextForge shim installation.")
    parser.add_argument("command", choices=["status", "plan", "install"])
    parser.add_argument("--source-dir", type=Path, default=SOURCE_DIR)
    parser.add_argument("--target-dir", type=Path, default=TARGET_DIR)
    parser.add_argument("--confirm")
    args = parser.parse_args(argv)
    if args.command == "status":
        result = directory_status(args.source_dir, args.target_dir)
    elif args.command == "plan":
        result = install_plan(args.source_dir, args.target_dir)
    else:
        result = apply_install(args.source_dir, args.target_dir, args.confirm)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
