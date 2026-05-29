#!/usr/bin/env python3
"""Shared helpers for ContextForge project initialization."""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


HOME = Path.home().resolve()
WORKSPACE_ROOT = Path("/home/dgk/workspace").resolve()
REPO_ROOT = Path(__file__).resolve().parents[1]
RUN_ROOT = REPO_ROOT / "run"

PROJECT_INIT_PROMPT_NAME = "project_init_prompt"
PROJECT_INIT_RESOURCE_URI = "contextforge://context-portal/project-init/v1"
SERENA_GUIDANCE_PROMPT_NAME = "serena_project_instance_guidance"
SERENA_GUIDANCE_RESOURCE_URI = "contextforge://context-portal/serena-project-instance-guidance/v1"
PROMPT_VERSION = "v1"

ENV_PROJECT_INIT_STATUS = "CONTEXTFORGE_PROJECT_INIT_DIALOGUE_STATUS"
ENV_SERENA_DECISION = "CONTEXTFORGE_SERENA_DECISION"
ENV_SERENA_PROVISION_STATUS = "CONTEXTFORGE_SERENA_PROVISION_STATUS"
ENV_SERENA_INSTANCE_SLUG = "CONTEXTFORGE_SERENA_INSTANCE_SLUG"
ENV_SERENA_SERVER_NAME = "CONTEXTFORGE_SERENA_SERVER_NAME"

PROJECT_ENV_KEYS = {
    ENV_PROJECT_INIT_STATUS,
    ENV_SERENA_DECISION,
    ENV_SERENA_PROVISION_STATUS,
    ENV_SERENA_INSTANCE_SLUG,
    ENV_SERENA_SERVER_NAME,
}

PROJECT_INIT_ACTIVE_STATES = {"unasked", "asked"}
PROJECT_INIT_TERMINAL_STATES = {"complete", "disabled"}
SERENA_DECISION_STATES = {"unasked", "accepted", "declined", "disabled"}
SERENA_PROVISION_STATES = {"none", "pending", "created", "failed", "removed"}

DENIED_PROJECT_ROOTS = {
    Path("/").resolve(),
    HOME,
    WORKSPACE_ROOT,
}

PROJECT_MARKERS = (
    ".git",
    ".codex",
    ".env",
    "pyproject.toml",
    "package.json",
    "Cargo.toml",
    "go.mod",
    "uv.lock",
    "README.md",
)


@dataclass(frozen=True)
class ProjectIdentity:
    root: Path
    slug: str
    hash: str
    instance_slug: str
    server_name: str
    root_hash: str


def canonical_path(value: str | Path) -> Path:
    return Path(value).expanduser().resolve(strict=False)


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def is_denied_project_root(path: Path) -> bool:
    return path in DENIED_PROJECT_ROOTS


def safe_workspace_project_root(path: Path) -> bool:
    return is_relative_to(path, WORKSPACE_ROOT) and path != WORKSPACE_ROOT and not is_denied_project_root(path)


def normalize_slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "project"


def project_root_hash(root: Path, uid: int | None = None) -> str:
    uid_value = os.getuid() if uid is None else uid
    return hashlib.sha256(f"{uid_value}:{root}".encode("utf-8")).hexdigest()


def project_identity(root: str | Path) -> ProjectIdentity:
    canonical_root = canonical_path(root)
    root_hash = project_root_hash(canonical_root)
    short_hash = root_hash[:12]
    slug = normalize_slug(canonical_root.name)
    server_slug = slug.replace("-", "_")
    instance_slug = f"serena-{slug}-{short_hash}"
    server_name = f"serena_{server_slug}_{short_hash}_server"
    return ProjectIdentity(
        root=canonical_root,
        slug=slug,
        hash=short_hash,
        instance_slug=instance_slug,
        server_name=server_name,
        root_hash=root_hash,
    )


def validate_project_root(root: str | Path, *, require_workspace: bool = False) -> Path:
    canonical_root = canonical_path(root)
    if is_denied_project_root(canonical_root):
        raise ValueError(f"refusing denied project root: {canonical_root}")
    if canonical_root == Path("/").resolve():
        raise ValueError("refusing filesystem root as project root")
    if require_workspace and not safe_workspace_project_root(canonical_root):
        raise ValueError(f"project root is not a safe /home/dgk/workspace child: {canonical_root}")
    if canonical_root == HOME or is_relative_to(HOME, canonical_root):
        raise ValueError(f"refusing user home or parent of user home as project root: {canonical_root}")
    return canonical_root


def _git_root(cwd: Path) -> Path | None:
    try:
        proc = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
            text=True,
            capture_output=True,
            timeout=2,
            check=False,
        )
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    root = proc.stdout.strip()
    return canonical_path(root) if root else None


def _marker_root(cwd: Path) -> Path | None:
    for candidate in (cwd, *cwd.parents):
        if candidate in DENIED_PROJECT_ROOTS:
            return None
        if any((candidate / marker).exists() for marker in PROJECT_MARKERS):
            return candidate
    return None


def _empty_workspace_dir_root(cwd: Path) -> Path | None:
    if not safe_workspace_project_root(cwd):
        return None
    if not cwd.is_dir():
        return None
    try:
        next(cwd.iterdir())
    except StopIteration:
        return cwd
    except OSError:
        return None
    return None


def _workspace_child_root(cwd: Path) -> Path | None:
    if not is_relative_to(cwd, WORKSPACE_ROOT) or cwd == WORKSPACE_ROOT:
        return None
    relative = cwd.relative_to(WORKSPACE_ROOT)
    if not relative.parts:
        return None
    return WORKSPACE_ROOT / relative.parts[0]


def detect_project_root(cwd: str | Path) -> Path | None:
    """Resolve a canonical project root without ever returning home/root/workspace."""

    canonical_cwd = canonical_path(cwd)
    candidates = []
    git_root = _git_root(canonical_cwd)
    if git_root is not None:
        candidates.append(git_root)
    empty_workspace_dir = _empty_workspace_dir_root(canonical_cwd)
    if empty_workspace_dir is not None:
        candidates.append(empty_workspace_dir)
    marker_root = _marker_root(canonical_cwd)
    if marker_root is not None:
        candidates.append(marker_root)
    workspace_child = _workspace_child_root(canonical_cwd)
    if workspace_child is not None:
        candidates.append(workspace_child)

    for candidate in candidates:
        canonical_candidate = canonical_path(candidate)
        if is_denied_project_root(canonical_candidate):
            continue
        if canonical_candidate == Path("/").resolve():
            continue
        if canonical_candidate == HOME:
            continue
        return canonical_candidate
    return None


def read_project_env(project_root: str | Path) -> dict[str, str]:
    env_path = canonical_path(project_root) / ".env"
    values: dict[str, str] = {}
    if not env_path.exists():
        return values
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key not in PROJECT_ENV_KEYS:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def write_project_env(project_root: str | Path, updates: dict[str, str]) -> None:
    unknown = set(updates) - PROJECT_ENV_KEYS
    if unknown:
        raise ValueError(f"refusing non-whitelisted .env keys: {sorted(unknown)}")

    root = canonical_path(project_root)
    env_path = root / ".env"
    existing = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    remaining = dict(updates)
    output: list[str] = []

    for raw_line in existing:
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            output.append(raw_line)
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in remaining:
            output.append(f"{key}={remaining.pop(key)}")
        else:
            output.append(raw_line)

    for key in sorted(remaining):
        output.append(f"{key}={remaining[key]}")

    env_path.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")
