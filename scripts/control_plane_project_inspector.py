#!/usr/bin/env python3
"""Pure read-only project-inspector behavior for ContextForge control-plane proofs."""

from __future__ import annotations

import hashlib
import mimetypes
import os
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

import control_plane_language_profiles as language_profiles
import control_plane_project_state as project_state
import control_plane_redaction as redaction


SCHEMA_URI = "contextforge://control-plane/schemas/project-inspector-report/v1"
HELPER_VERSION = 1
MAX_FILE_BYTES = 256 * 1024
MAX_SNIPPET_BYTES = 2048
MAX_WALK_ENTRIES = 500
DEFAULT_EXCLUDED_DIRS = frozenset({".git", ".hg", ".svn", ".venv", "venv", "node_modules", "__pycache__"})
DEFAULT_EXCLUDED_FILES = frozenset({".env", ".env.local", ".envrc"})
MUTATING_TOOL_NAMES = frozenset(
    {
        "write_file",
        "edit_file",
        "delete_file",
        "move_file",
        "copy_file",
        "create_file",
        "mkdir",
        "rmdir",
        "apply_patch",
        "git_commit",
        "git_stage",
    }
)
SHELL_TOOL_NAMES = frozenset({"shell", "run_shell", "exec", "exec_command", "subprocess", "command"})
CONTENT_TOOL_NAMES = frozenset({"read_file", "cat", "dump_file", "get_file_contents", "download_file"})


class ProjectInspectorError(ValueError):
    """Base exception for project-inspector request failures."""


class ProjectInspectorAccessError(ProjectInspectorError):
    """Raised when a path or request escapes the project-inspector boundary."""


class ProjectInspectorRequestError(ProjectInspectorError):
    """Raised when a caller asks for forbidden or malformed behavior."""


@dataclass(frozen=True)
class InspectorEvidence:
    """Caller-supplied status evidence; the inspector never runs shell commands."""

    ignored_paths: tuple[str, ...] = ()
    excluded_paths: tuple[str, ...] = ()
    dirty_worktree: Mapping[str, Any] | None = None
    marker_paths: tuple[str, ...] = ()
    package_manifests: tuple[str, ...] = ()

    @classmethod
    def from_mapping(cls, evidence: Mapping[str, Any] | None) -> "InspectorEvidence":
        if evidence is None:
            return cls()
        return cls(
            ignored_paths=_tuple_of_strings(evidence.get("ignored_paths", ())),
            excluded_paths=_tuple_of_strings(evidence.get("excluded_paths", ())),
            dirty_worktree=dict(evidence.get("dirty_worktree") or {}),
            marker_paths=_tuple_of_strings(evidence.get("marker_paths", ())),
            package_manifests=_tuple_of_strings(evidence.get("package_manifests", ())),
        )


@dataclass(frozen=True)
class ProjectInspector:
    """Root-bound read-only inspector facade."""

    project_root: Path
    evidence: InspectorEvidence = field(default_factory=InspectorEvidence)

    @classmethod
    def for_root(
        cls,
        project_root: str | Path,
        *,
        evidence: Mapping[str, Any] | InspectorEvidence | None = None,
        require_workspace: bool = True,
    ) -> "ProjectInspector":
        root = project_state.validate_project_root(project_root, require_workspace=require_workspace)
        parsed = evidence if isinstance(evidence, InspectorEvidence) else InspectorEvidence.from_mapping(evidence)
        return cls(project_root=root, evidence=parsed)

    def project_identity(self) -> dict[str, Any]:
        return {
            "schema_uri": SCHEMA_URI,
            "helper_version": HELPER_VERSION,
            "project": {
                "root": str(self.project_root),
                "root_hash": project_state.project_root_hash(self.project_root),
                "name": self.project_root.name,
                "identity_source": "canonical_realpath_plus_uid",
            },
            "safety": {
                "root_bound": True,
                "read_only": True,
                "shell_allowed": False,
                "mutation_allowed": False,
                "arbitrary_file_content_dump_allowed": False,
            },
        }

    def classify_path(self, path: str | Path) -> dict[str, Any]:
        target = self._resolve_inside_root(path)
        relative = _relative_posix(target, self.project_root)
        ignored = self._matches_evidence(relative, self.evidence.ignored_paths)
        excluded = _is_default_excluded(relative) or self._matches_evidence(relative, self.evidence.excluded_paths)
        status = "denied_ignored" if ignored else "denied_excluded" if excluded else "allowed"
        return {
            "input_path": str(path),
            "canonical_path": str(target),
            "relative_path": _sanitize_path(relative),
            "status": status,
            "root_bound": status == "allowed",
            "ignored": ignored,
            "excluded": excluded,
            "is_symlink": Path(path).expanduser().is_symlink(),
        }

    def file_metadata(self, path: str | Path, *, include_snippet: bool = False) -> dict[str, Any]:
        classification = self.classify_path(path)
        if classification["status"] != "allowed":
            raise ProjectInspectorAccessError(f"path is not inspectable: {classification['status']}")
        target = Path(classification["canonical_path"])
        try:
            stat_result = target.stat()
        except OSError as exc:
            raise ProjectInspectorAccessError(f"path is not stat-readable: {classification['relative_path']}") from exc

        metadata: dict[str, Any] = {
            "relative_path": classification["relative_path"],
            "kind": _path_kind(target),
            "size_bytes": stat_result.st_size,
            "mode": oct(stat_result.st_mode & 0o777),
            "mime_type": mimetypes.guess_type(target.name)[0],
            "sanitized": True,
        }
        if target.is_file():
            metadata["content_digest"] = _file_digest(target) if stat_result.st_size <= MAX_FILE_BYTES else None
            metadata["content_digest_status"] = "computed" if metadata["content_digest"] else "skipped_large_file"
        if include_snippet:
            metadata["snippet"] = self._safe_snippet(target, stat_result.st_size)
        return metadata

    def detected_languages(self) -> dict[str, Any]:
        paths = self._project_paths()
        report = language_profiles.detect_language_profiles(paths)
        report["project_root_hash"] = project_state.project_root_hash(self.project_root)
        report["input_path_count"] = len(paths)
        return report

    def ignored_path_summary(self) -> dict[str, Any]:
        return {
            "ignored_paths": [_sanitize_path(_normalize_relative_path(path)) for path in self.evidence.ignored_paths],
            "excluded_paths": sorted(
                {_sanitize_path(path) for path in (*self.evidence.excluded_paths, *DEFAULT_EXCLUDED_DIRS, *DEFAULT_EXCLUDED_FILES)}
            ),
            "source": "caller_supplied_evidence_plus_static_defaults",
        }

    def dirty_worktree_summary(self) -> dict[str, Any]:
        evidence = dict(self.evidence.dirty_worktree or {})
        entries = []
        for entry in evidence.get("entries", ()):
            if not isinstance(entry, Mapping):
                continue
            path = _normalize_relative_path(str(entry.get("path") or ""))
            if not path or self._matches_evidence(path, self.evidence.ignored_paths):
                continue
            entries.append(
                {
                    "path": _sanitize_path(path),
                    "status": str(entry.get("status") or "unknown"),
                    "source": str(entry.get("source") or evidence.get("source") or "caller_supplied"),
                }
            )
        return {
            "source": str(evidence.get("source") or "caller_supplied_evidence"),
            "clean": bool(evidence.get("clean")) if "clean" in evidence else not entries,
            "entry_count": len(entries),
            "entries": entries,
            "shell_executed": False,
        }

    def inspect(self, *, paths: Sequence[str | Path] = (), include_snippets: bool = False) -> dict[str, Any]:
        metadata = [self.file_metadata(path, include_snippet=include_snippets) for path in paths]
        return {
            **self.project_identity(),
            "path_classifications": [self.classify_path(path) for path in paths],
            "detected_languages": self.detected_languages(),
            "ignored_path_summary": self.ignored_path_summary(),
            "dirty_worktree": self.dirty_worktree_summary(),
            "file_metadata": metadata,
        }

    def handle_request(self, tool_name: str, arguments: Mapping[str, Any] | None = None) -> dict[str, Any]:
        normalized = str(tool_name).strip().lower().replace("-", "_")
        args = dict(arguments or {})
        if normalized in MUTATING_TOOL_NAMES or any(word in normalized for word in ("write", "delete", "edit", "mutate")):
            raise ProjectInspectorRequestError("project-inspector is read-only and rejects mutation requests")
        if normalized in SHELL_TOOL_NAMES or any(word in normalized for word in ("shell", "command", "exec")):
            raise ProjectInspectorRequestError("project-inspector does not execute shell commands")
        if normalized in CONTENT_TOOL_NAMES:
            raise ProjectInspectorRequestError("project-inspector does not provide arbitrary file content dumps")
        if normalized == "get_project_identity":
            return self.project_identity()
        if normalized == "classify_path":
            return self.classify_path(_require_arg(args, "path"))
        if normalized == "get_file_metadata":
            return self.file_metadata(_require_arg(args, "path"), include_snippet=bool(args.get("include_snippet", False)))
        if normalized == "get_detected_languages":
            return self.detected_languages()
        if normalized == "get_ignored_path_summary":
            return self.ignored_path_summary()
        if normalized == "get_dirty_worktree_summary":
            return self.dirty_worktree_summary()
        raise ProjectInspectorRequestError(f"unknown project-inspector request: {tool_name}")

    def _safe_path(self, path: str | Path) -> Path:
        resolved = self._resolve_inside_root(path)
        relative = _relative_posix(resolved, self.project_root)
        if _is_default_excluded(relative) or self._matches_evidence(relative, self.evidence.excluded_paths):
            raise ProjectInspectorAccessError(f"path is excluded from project-inspector access: {_sanitize_path(relative)}")
        if self._matches_evidence(relative, self.evidence.ignored_paths):
            raise ProjectInspectorAccessError(f"path is ignored and not inspectable: {_sanitize_path(relative)}")
        return resolved

    def _resolve_inside_root(self, path: str | Path) -> Path:
        raw = Path(path).expanduser()
        candidate = raw if raw.is_absolute() else self.project_root / raw
        resolved = candidate.resolve(strict=False)
        if not project_state.is_relative_to(resolved, self.project_root):
            raise ProjectInspectorAccessError(f"path resolves outside project root: {path}")
        return resolved

    def _safe_snippet(self, target: Path, size_bytes: int) -> dict[str, Any]:
        if not target.is_file():
            raise ProjectInspectorRequestError("snippets are only available for regular files")
        if size_bytes > MAX_SNIPPET_BYTES:
            raise ProjectInspectorRequestError("file is too large for bounded snippet inspection")
        data = target.read_bytes()
        if _looks_binary(data):
            raise ProjectInspectorRequestError("binary files are not eligible for snippet inspection")
        text = data.decode("utf-8", errors="replace")
        result = redaction.redact_with_report(text[:MAX_SNIPPET_BYTES])
        redaction.assert_no_sensitive_raw_values(result.data)
        return {
            "status": "bounded_sanitized_snippet",
            "max_bytes": MAX_SNIPPET_BYTES,
            "text": result.data,
            "redaction": result.summary(),
        }

    def _project_paths(self) -> list[str]:
        paths: list[str] = []
        for current, dirnames, filenames in os.walk(self.project_root):
            current_path = Path(current)
            current_relative = "" if current_path == self.project_root else _relative_posix(current_path, self.project_root)
            dirnames[:] = [
                name
                for name in sorted(dirnames)
                if not self._path_blocked(_join_relative(current_relative, name), directory=True)
            ]
            for name in sorted(filenames):
                relative = _join_relative(current_relative, name)
                if self._path_blocked(relative, directory=False):
                    continue
                paths.append(relative)
                if len(paths) >= MAX_WALK_ENTRIES:
                    return paths
        paths.extend(path for path in self.evidence.marker_paths if path not in paths)
        paths.extend(path for path in self.evidence.package_manifests if path not in paths)
        return sorted({_normalize_relative_path(path) for path in paths if path})

    def _path_blocked(self, relative: str, *, directory: bool) -> bool:
        normalized = _normalize_relative_path(relative)
        if not normalized:
            return False
        return (
            _is_default_excluded(normalized)
            or self._matches_evidence(normalized, self.evidence.ignored_paths)
            or self._matches_evidence(normalized, self.evidence.excluded_paths)
        )

    def _matches_evidence(self, relative: str, evidence_paths: Iterable[str]) -> bool:
        normalized = _normalize_relative_path(relative)
        for item in evidence_paths:
            evidence = _normalize_relative_path(item)
            if normalized == evidence or normalized.startswith(f"{evidence}/"):
                return True
        return False


def inspect_project(
    project_root: str | Path,
    *,
    evidence: Mapping[str, Any] | InspectorEvidence | None = None,
    paths: Sequence[str | Path] = (),
    include_snippets: bool = False,
    require_workspace: bool = True,
) -> dict[str, Any]:
    inspector = ProjectInspector.for_root(project_root, evidence=evidence, require_workspace=require_workspace)
    return inspector.inspect(paths=paths, include_snippets=include_snippets)


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _looks_binary(data: bytes) -> bool:
    return b"\x00" in data


def _path_kind(path: Path) -> str:
    if path.is_dir():
        return "directory"
    if path.is_file():
        return "file"
    if path.is_symlink():
        return "symlink"
    return "other"


def _relative_posix(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _join_relative(parent: str, child: str) -> str:
    return child if not parent else f"{parent}/{child}"


def _normalize_relative_path(path: str) -> str:
    if not path:
        return ""
    pure = PurePosixPath(str(path).replace("\\", "/"))
    parts = [part for part in pure.parts if part not in {"", "."}]
    if any(part == ".." for part in parts):
        raise ProjectInspectorAccessError(f"relative path must not contain parent traversal: {path}")
    return PurePosixPath(*parts).as_posix() if parts else ""


def _sanitize_path(path: str) -> str:
    parts = []
    for part in _normalize_relative_path(path).split("/"):
        if not part:
            continue
        if redaction.classify_sensitive_key(part) or redaction.classify_sensitive_value(part):
            parts.append(redaction.REDACTED_MARKER)
        else:
            parts.append(part)
    return "/".join(parts)


def _is_default_excluded(relative: str) -> bool:
    normalized = _normalize_relative_path(relative)
    if not normalized:
        return False
    parts = normalized.split("/")
    return any(part in DEFAULT_EXCLUDED_DIRS for part in parts) or normalized in DEFAULT_EXCLUDED_FILES


def _tuple_of_strings(values: Any) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        return (values,)
    if not isinstance(values, Iterable):
        raise ProjectInspectorRequestError("evidence path collections must be iterable")
    return tuple(str(value) for value in values if str(value).strip())


def _require_arg(arguments: Mapping[str, Any], key: str) -> Any:
    if key not in arguments:
        raise ProjectInspectorRequestError(f"missing required argument: {key}")
    return arguments[key]
