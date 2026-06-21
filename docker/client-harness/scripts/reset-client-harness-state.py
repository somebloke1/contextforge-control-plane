#!/usr/bin/env python3
"""Idempotently reset one client harness surface for dialogue validation."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


CLIENTS = {
    "codex-cli": {
        "services": ["codex-cli", "codex-cli-authenticated"],
        "home_volume": "contextforge-client-harness_codex-cli-home",
        "authenticated_image": "contextforge-client-codex-cli:authenticated",
    },
    "pi": {
        "services": ["pi", "pi-ephemeral"],
        "home_volume": "contextforge-client-harness_pi-home",
    },
    "opencode": {
        "services": ["opencode", "opencode-ephemeral"],
        "home_volume": "contextforge-client-harness_opencode-home",
    },
}


def run(command: list[str], *, cwd: Path, dry_run: bool) -> dict[str, object]:
    if dry_run:
        return {"command": command, "returncode": 0, "stdout": "", "stderr": "", "dry_run": True}
    completed = subprocess.run(command, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def docker_ids(command: list[str], *, cwd: Path, dry_run: bool) -> tuple[list[str], dict[str, object]]:
    result = run(command, cwd=cwd, dry_run=dry_run)
    if result["returncode"] != 0:
        return [], result
    return [line.strip() for line in str(result["stdout"]).splitlines() if line.strip()], result


def docker_volume_absent(result: dict[str, object], *, dry_run: bool) -> bool:
    if dry_run:
        return True
    if int(result.get("returncode", 0)) == 0:
        return False
    stderr = str(result.get("stderr", ""))
    stdout = str(result.get("stdout", ""))
    message = f"{stdout}\n{stderr}".lower()
    return "no such volume" in message or "not found" in message


def preserve_workspace(workspace: Path, evidence_dir: Path, *, dry_run: bool) -> dict[str, object]:
    entries = sorted(item for item in workspace.iterdir() if item.name != ".gitkeep") if workspace.exists() else []
    if not entries:
        return {"preserved": False, "entries": []}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = evidence_dir / f"workspace-preserved-{stamp}"
    if not dry_run:
        target.mkdir(parents=True, exist_ok=False)
        for item in entries:
            shutil.move(str(item), str(target / item.name))
    return {"preserved": True, "target": str(target), "entries": [item.name for item in entries]}


def reset_workspace(workspace: Path, evidence_dir: Path, *, dry_run: bool) -> dict[str, object]:
    workspace.mkdir(parents=True, exist_ok=True)
    preserved = preserve_workspace(workspace, evidence_dir, dry_run=dry_run)
    if not dry_run:
        for item in list(workspace.iterdir()):
            if item.name == ".gitkeep":
                continue
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
        (workspace / ".gitkeep").write_text("\n", encoding="utf-8")
    entries = [".gitkeep"] if dry_run else sorted(item.name for item in workspace.iterdir())
    return {
        "preservation": preserved,
        "entries": entries,
        "allowlist": [".gitkeep"],
        "postcondition": entries == [".gitkeep"],
    }


def reset_project_scoped_service_state(repo_root: Path, workspace: Path, evidence_dir: Path, *, dry_run: bool) -> dict[str, object]:
    """Reset harness-owned project-scoped backend state for the virgin workspace.

    The client containers mount the active repo at /repo and use /workspace as
    the project root. Serena project instances are legitimate helper-managed
    state, but a clean dialogue run must not inherit a prior /workspace
    instance.
    """

    server_instances = repo_root / "server-instances"
    roots = {"/workspace", str(workspace)}
    targets: list[Path] = []
    for manifest in server_instances.glob("serena-*/instance.json"):
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if str(data.get("canonical_project_root") or "") in roots:
            targets.append(manifest.parent)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    preserved_root = evidence_dir / f"server-instances-preserved-{stamp}"
    preserved: list[str] = []
    if not dry_run:
        for target in targets:
            if not target.exists():
                continue
            preserved_root.mkdir(parents=True, exist_ok=True)
            shutil.move(str(target), str(preserved_root / target.name))
            preserved.append(target.name)
    else:
        preserved = [target.name for target in targets]

    remaining: list[str] = []
    for manifest in server_instances.glob("serena-*/instance.json"):
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if str(data.get("canonical_project_root") or "") in roots:
            remaining.append(str(manifest.parent))

    return {
        "roots": sorted(roots),
        "matched": [str(target) for target in targets],
        "preserved": bool(preserved),
        "preservation_target": str(preserved_root) if preserved else None,
        "preserved_entries": preserved,
        "remaining": remaining,
        "postcondition": not remaining,
    }


def reset_client(client: str, compose_file: Path, repo_root: Path, *, reset_home_volume: bool, dry_run: bool) -> dict[str, object]:
    spec = CLIENTS[client]
    commands: list[dict[str, object]] = []
    compose = ["docker", "compose", "-f", str(compose_file)]
    commands.append(run([*compose, "rm", "-sf", *spec["services"]], cwd=repo_root, dry_run=dry_run))
    volume = str(spec["home_volume"])
    holder_ids, holder_ps = docker_ids(["docker", "ps", "-aq", "--filter", f"volume={volume}"], cwd=repo_root, dry_run=dry_run)
    commands.append(holder_ps)
    if holder_ids:
        commands.append(run(["docker", "rm", "-f", *holder_ids], cwd=repo_root, dry_run=dry_run))
    volume_rm: dict[str, object] | None = None
    if reset_home_volume:
        volume_rm = run(["docker", "volume", "rm", volume], cwd=repo_root, dry_run=dry_run)
        commands.append(volume_rm)
    remaining, remaining_ps = docker_ids(["docker", "ps", "-aq", "--filter", f"volume={volume}"], cwd=repo_root, dry_run=dry_run)
    commands.append(remaining_ps)
    volume_inspect: dict[str, object] | None = None
    volume_absent = True
    if reset_home_volume:
        volume_inspect = run(["docker", "volume", "inspect", volume], cwd=repo_root, dry_run=dry_run)
        commands.append(volume_inspect)
        volume_absent = docker_volume_absent(volume_inspect, dry_run=dry_run)
    command_failures = [command for command in commands if int(command.get("returncode", 0)) != 0]
    tolerated_failures: list[dict[str, object]] = []
    if volume_inspect is not None and volume_inspect in command_failures and volume_absent:
        tolerated_failures.append(volume_inspect)
    hard_failures = [command for command in command_failures if command not in tolerated_failures]
    if volume_rm is not None and int(volume_rm.get("returncode", 0)) != 0 and docker_volume_absent(volume_rm, dry_run=dry_run):
        hard_failures = [command for command in hard_failures if command is not volume_rm]
    return {
        "client": client,
        "commands": commands,
        "home_volume": volume,
        "authenticated_image": spec.get("authenticated_image"),
        "authenticated_image_preserved": bool(spec.get("authenticated_image")),
        "home_volume_reset_requested": reset_home_volume,
        "home_volume_absent": volume_absent,
        "remaining_target_volume_containers": remaining,
        "command_failures": hard_failures,
        "postcondition": not remaining and not hard_failures and volume_absent,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client", required=True, choices=sorted(CLIENTS))
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[3]))
    parser.add_argument("--compose-file", default="docker/client-harness/compose.yml")
    parser.add_argument("--workspace", default="docker/client-harness/workspace")
    parser.add_argument("--evidence-dir", default="docker/client-harness/evidence/use-case-1/prior")
    parser.add_argument("--reset-home-volume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    compose_file = (repo_root / args.compose_file).resolve()
    workspace = (repo_root / args.workspace).resolve()
    evidence_dir = (repo_root / args.evidence_dir).resolve()
    result = {
        "ok": True,
        "client": args.client,
        "repo_root": str(repo_root),
        "workspace": str(workspace),
        "evidence_dir": str(evidence_dir),
        "client_reset": reset_client(args.client, compose_file, repo_root, reset_home_volume=args.reset_home_volume, dry_run=args.dry_run),
        "workspace_reset": reset_workspace(workspace, evidence_dir, dry_run=args.dry_run),
        "project_scoped_service_reset": reset_project_scoped_service_state(repo_root, workspace, evidence_dir, dry_run=args.dry_run),
    }
    result["ok"] = bool(
        result["client_reset"]["postcondition"]
        and result["workspace_reset"]["postcondition"]
        and result["project_scoped_service_reset"]["postcondition"]
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
