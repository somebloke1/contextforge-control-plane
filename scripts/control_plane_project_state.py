#!/usr/bin/env python3
"""Project-state helpers for the ContextForge control plane."""

from __future__ import annotations

import errno
import hashlib
import json
import os
import stat
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

try:
    import jsonschema
except ImportError:  # pragma: no cover - jsonschema is present in the project venv.
    jsonschema = None  # type: ignore[assignment]


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schemas/control-plane/project-state.schema.json"
STATE_DIR_NAME = ".project"
STATE_FILE_NAME = "context_forge_state.json"
LOCK_FILE_NAME = "context_forge_state.lock"
SCHEMA_VERSION = 1
SCHEMA_URI = "contextforge://control-plane/project-state/v1"
SUPPORTED_SCHEMA_MAJOR = 1
DEFAULT_UPDATED_BY = "control_plane_project_state"
HOME = Path.home().resolve()
WORKSPACE_ROOT = Path("/home/dgk/workspace").resolve()
DENIED_PROJECT_ROOTS = frozenset({Path("/").resolve(), HOME, WORKSPACE_ROOT})
LEGACY_ENV_KEYS = frozenset(
    {
        "CONTEXTFORGE_PROJECT_INIT_DIALOGUE_STATUS",
        "CONTEXTFORGE_SERENA_DECISION",
        "CONTEXTFORGE_SERENA_PROVISION_STATUS",
        "CONTEXTFORGE_SERENA_INSTANCE_SLUG",
        "CONTEXTFORGE_SERENA_SERVER_NAME",
    }
)
LEGACY_PROJECT_STATUSES = frozenset({"unasked", "asked", "complete", "disabled", "deferred"})
LEGACY_SERENA_DECISIONS = frozenset({"unasked", "accepted", "declined", "disabled", "deferred"})
LEGACY_SERENA_PROVISION_STATUSES = frozenset({"none", "pending", "created", "failed", "removed", "verified"})
SECRET_FIELD_PATTERNS = (
    "secret",
    "token",
    "password",
    "passwd",
    "api_key",
    "apikey",
    "bearer",
    "jwt",
    "auth_encryption_key",
)


class ProjectStateError(Exception):
    """Base class for project-state failures."""


class RootValidationError(ProjectStateError, ValueError):
    """Raised when a project root is unsafe."""


class StateValidationError(ProjectStateError, ValueError):
    """Raised when project state does not satisfy the schema or local rules."""


class RevisionMismatchError(ProjectStateError):
    """Raised when compare-and-swap revision checks fail."""


class StateLockError(ProjectStateError):
    """Raised when project-state locking fails."""


@dataclass(frozen=True)
class LegacyEnvMigration:
    disposition: str
    digest: str | None
    keys_seen: tuple[str, ...]
    decisions: dict[str, Any]
    conflicts: tuple[dict[str, Any], ...] = ()
    open_items: tuple[dict[str, Any], ...] = ()

    def as_state_fragment(self) -> dict[str, Any]:
        imported_at = now_timestamp() if self.disposition == "imported" else None
        return {
            "migration": {
                "legacy_env_seen": bool(self.keys_seen or self.digest),
                "legacy_env_disposition": self.disposition,
                "legacy_env_digest": self.digest,
                "imported_at": imported_at,
                "conflicts": list(self.conflicts),
                "client_config_migrations": {},
            },
            "decisions": dict(self.decisions),
            "open_items": list(self.open_items),
        }


def canonical_root(root: str | Path) -> Path:
    return Path(root).expanduser().resolve(strict=False)


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def validate_project_root(
    root: str | Path,
    *,
    require_workspace: bool = False,
    denied_roots: set[str | Path] | frozenset[Path] | None = None,
) -> Path:
    display_path = Path(root).expanduser()
    canonical = display_path.resolve(strict=False)
    denied = {canonical_root(item) for item in (denied_roots or DENIED_PROJECT_ROOTS)}
    if canonical in denied:
        raise RootValidationError(f"refusing denied project root: {canonical}")
    if canonical == Path("/").resolve():
        raise RootValidationError("refusing filesystem root as project root")
    if canonical == HOME or is_relative_to(HOME, canonical):
        raise RootValidationError(f"refusing user home or parent of user home as project root: {canonical}")
    if require_workspace:
        if not is_relative_to(display_path.resolve(strict=False), WORKSPACE_ROOT):
            raise RootValidationError(f"project root is not a safe workspace child: {canonical}")
        if not is_relative_to(canonical, WORKSPACE_ROOT) or canonical == WORKSPACE_ROOT:
            raise RootValidationError(f"project root resolves outside safe workspace: {canonical}")
    return canonical


def project_root_hash(root: str | Path, *, uid: int | None = None) -> str:
    uid_value = os.getuid() if uid is None else uid
    canonical = canonical_root(root)
    return hashlib.sha256(f"{uid_value}:{canonical}".encode("utf-8")).hexdigest()


def project_state_dir(project_root: str | Path) -> Path:
    return canonical_root(project_root) / STATE_DIR_NAME


def project_state_path(project_root: str | Path) -> Path:
    return project_state_dir(project_root) / STATE_FILE_NAME


def project_state_lock_path(project_root: str | Path) -> Path:
    return project_state_dir(project_root) / LOCK_FILE_NAME


def load_schema(schema_path: Path = SCHEMA_PATH) -> dict[str, Any]:
    return json.loads(schema_path.read_text(encoding="utf-8"))


def schema_major(schema_version: Any) -> int:
    if isinstance(schema_version, int):
        return schema_version
    try:
        return int(str(schema_version).split(".", 1)[0])
    except (TypeError, ValueError) as exc:
        raise StateValidationError(f"invalid meta.schema_version: {schema_version!r}") from exc


def state_revision(state: dict[str, Any]) -> int:
    try:
        return int(state["meta"]["revision"])
    except (KeyError, TypeError, ValueError) as exc:
        raise StateValidationError("project state missing integer meta.revision") from exc


def validate_supported_schema_version(state: dict[str, Any]) -> None:
    meta = state.get("meta")
    if not isinstance(meta, dict):
        raise StateValidationError("project state missing meta object")
    version = meta.get("schema_version")
    if schema_major(version) != SUPPORTED_SCHEMA_MAJOR:
        raise StateValidationError(f"unsupported project-state schema major version: {version!r}")


def _secret_path_hits(value: Any, path: tuple[str, ...] = ()) -> list[str]:
    hits: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).lower().replace("-", "_")
            child_path = (*path, str(key))
            if any(pattern in normalized for pattern in SECRET_FIELD_PATTERNS):
                hits.append(".".join(child_path))
            hits.extend(_secret_path_hits(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            hits.extend(_secret_path_hits(child, (*path, str(index))))
    return hits


def ensure_no_secret_value_fields(state: dict[str, Any]) -> None:
    hits = _secret_path_hits(state)
    if hits:
        raise StateValidationError(f"project state contains secret-like fields: {', '.join(sorted(hits))}")


def validate_state(state: dict[str, Any], *, schema: dict[str, Any] | None = None) -> None:
    validate_supported_schema_version(state)
    ensure_no_secret_value_fields(state)
    loaded_schema = schema or load_schema()
    if jsonschema is None:
        return
    try:
        jsonschema.Draft202012Validator(loaded_schema).validate(state)
    except jsonschema.ValidationError as exc:
        path = ".".join(str(part) for part in exc.absolute_path)
        location = f" at {path}" if path else ""
        raise StateValidationError(f"invalid project state{location}: {exc.message}") from exc


def now_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def empty_artifact_refs() -> dict[str, list[dict[str, Any]]]:
    return {
        "contract_cards": [],
        "capability_capsules": [],
        "semantic_tool_policies": [],
        "consent_receipts": [],
        "verification_traces": [],
        "evidence_ledgers": [],
        "governance_reconciliation_packs": [],
    }


def default_migration() -> dict[str, Any]:
    return {
        "legacy_env_seen": False,
        "legacy_env_disposition": "not_present",
        "legacy_env_digest": None,
        "imported_at": None,
        "conflicts": [],
        "client_config_migrations": {},
    }


def default_state(
    project_root: str | Path,
    *,
    status: str = "uninitialized",
    display_root: str | None = None,
    updated_by: str = DEFAULT_UPDATED_BY,
) -> dict[str, Any]:
    canonical = validate_project_root(project_root)
    timestamp = now_timestamp()
    return {
        "meta": {
            "schema_version": SCHEMA_VERSION,
            "schema_uri": SCHEMA_URI,
            "created_at": timestamp,
            "updated_at": timestamp,
            "updated_by": updated_by,
            "revision": 0,
            "last_plan_id": None,
            "last_audit_record": None,
        },
        "project": {
            "root": str(canonical),
            "root_hash": project_root_hash(canonical),
            "name": canonical.name,
            "display_root": display_root,
        },
        "diagnostics": {"related_instances": []},
        "migration": default_migration(),
        "artifact_refs": empty_artifact_refs(),
        "status": status,
        "decisions": {},
        "services": {},
        "client_trust": {},
        "memory_policy": {"mode": "ledger_authoritative_references_only"},
        "drift": {
            "last_checked_at": None,
            "status": "unknown",
            "findings": [],
            "reconciled_by_name": [],
            "stale_ids": [],
        },
        "open_items": [],
    }


def read_json_file(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StateValidationError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise StateValidationError(f"project state must be a JSON object: {path}")
    return data


def load_state(project_root: str | Path, *, require_workspace: bool = False) -> dict[str, Any] | None:
    root = validate_project_root(project_root, require_workspace=require_workspace)
    path = project_state_path(root)
    if not path.exists():
        return None
    state = read_json_file(path)
    validate_state_root(state, root)
    validate_state(state)
    return state


def read_or_default(project_root: str | Path, *, require_workspace: bool = False) -> dict[str, Any]:
    root = validate_project_root(project_root, require_workspace=require_workspace)
    return load_state(root, require_workspace=require_workspace) or default_state(root)


def validate_state_root(state: dict[str, Any], project_root: str | Path) -> None:
    root = validate_project_root(project_root)
    project = state.get("project")
    if not isinstance(project, dict):
        raise StateValidationError("project state missing project object")
    state_root = project.get("root")
    state_hash = project.get("root_hash")
    if state_root != str(root):
        raise StateValidationError(f"project state root mismatch: {state_root!r} != {str(root)!r}")
    expected_hash = project_root_hash(root)
    if state_hash != expected_hash:
        raise StateValidationError("project state root_hash mismatch")


def parse_env_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None
    key, value = stripped.split("=", 1)
    key = key.strip()
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return key, value


def parse_legacy_env_text(text: str) -> tuple[dict[str, str], list[str]]:
    values: dict[str, str] = {}
    malformed: list[str] = []
    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        parsed = parse_env_line(raw_line)
        stripped = raw_line.strip()
        if parsed is None:
            if stripped and not stripped.startswith("#") and stripped.startswith("CONTEXTFORGE_"):
                malformed.append(f"line {line_no}")
            continue
        key, value = parsed
        if key in LEGACY_ENV_KEYS:
            values[key] = value
    return values, malformed


def legacy_env_digest(values: dict[str, str], *, malformed: list[str] | None = None) -> str:
    payload = {"values": {key: values[key] for key in sorted(values)}, "malformed": malformed or []}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def decision_record(state: str, *, notes: str | None = None) -> dict[str, Any]:
    return {
        "decision_kind": "service",
        "state": state,
        "service_binding": None,
        "contract_card_ref": None,
        "decided_at": now_timestamp(),
        "decided_by": "legacy_env_migration",
        "source_plan_id": None,
        "reopened_at": None,
        "notes": notes,
    }


def migration_conflict(reason: str) -> dict[str, Any]:
    return {"source": "legacy_env", "reason": reason}


def open_item(item_id: str, detail: dict[str, Any], *, severity: str = "blocking") -> dict[str, Any]:
    return {
        "id": item_id,
        "type": "migration",
        "severity": severity,
        "blocks_initialized": severity == "blocking",
        "resource": ".env",
        "created_at": now_timestamp(),
        "resolution_state": "open",
        "detail": detail,
    }


def classify_legacy_env(values: dict[str, str], *, malformed: list[str] | None = None) -> LegacyEnvMigration:
    malformed = malformed or []
    keys_seen = tuple(sorted(values))
    digest = legacy_env_digest(values, malformed=malformed) if values or malformed else None
    if not values and not malformed:
        return LegacyEnvMigration("not_present", None, (), {})

    invalid = []
    project_status = values.get("CONTEXTFORGE_PROJECT_INIT_DIALOGUE_STATUS")
    serena_decision = values.get("CONTEXTFORGE_SERENA_DECISION")
    provision_status = values.get("CONTEXTFORGE_SERENA_PROVISION_STATUS")
    if project_status is not None and project_status not in LEGACY_PROJECT_STATUSES:
        invalid.append("CONTEXTFORGE_PROJECT_INIT_DIALOGUE_STATUS")
    if serena_decision is not None and serena_decision not in LEGACY_SERENA_DECISIONS:
        invalid.append("CONTEXTFORGE_SERENA_DECISION")
    if provision_status is not None and provision_status not in LEGACY_SERENA_PROVISION_STATUSES:
        invalid.append("CONTEXTFORGE_SERENA_PROVISION_STATUS")

    conflict = False
    if serena_decision in {"declined", "disabled"} and provision_status in {"pending", "created", "verified"}:
        conflict = True
    if serena_decision == "accepted" and project_status == "disabled":
        conflict = True

    if invalid or malformed or conflict:
        conflicts = (migration_conflict("malformed_or_conflicting_legacy_env"),)
        return LegacyEnvMigration(
            "conflict",
            digest,
            keys_seen,
            {},
            conflicts,
            (
                open_item(
                    "legacy-env-migration-conflict",
                    {"invalid_keys": invalid, "malformed": malformed, "conflict": conflict},
                ),
            ),
        )

    if serena_decision == "declined":
        return LegacyEnvMigration(
            "imported",
            digest,
            keys_seen,
            {"serena": decision_record("declined", notes="sticky_decline_from_legacy_env")},
        )
    if serena_decision == "deferred" or project_status == "deferred":
        return LegacyEnvMigration(
            "imported",
            digest,
            keys_seen,
            {"serena": decision_record("deferred")},
            (migration_conflict("deferred_legacy_decision_requires_review"),),
            (
                open_item(
                    "legacy-env-deferred",
                    {"reason": "Legacy .env deferred project-init decision needs explicit review."},
                    severity="warning",
                ),
            ),
        )
    if serena_decision == "disabled" or project_status == "disabled":
        return LegacyEnvMigration(
            "imported",
            digest,
            keys_seen,
            {"serena": decision_record("disabled", notes="sticky_disabled_from_legacy_env")},
        )
    if serena_decision == "accepted" or provision_status in {"pending", "created", "verified"}:
        return LegacyEnvMigration(
            "conflict",
            digest,
            keys_seen,
            {},
            (migration_conflict("accepted_or_provisioned_legacy_state_requires_current_verification"),),
            (
                open_item(
                    "legacy-env-accepted-requires-verification",
                    {"reason": "Legacy accepted or provisioned state requires explicit import criteria and current verification."},
                ),
            ),
        )

    return LegacyEnvMigration("ignored", digest, keys_seen, {})


def classify_legacy_env_file(project_root: str | Path) -> LegacyEnvMigration:
    root = validate_project_root(project_root)
    env_path = root / ".env"
    if not env_path.exists():
        return classify_legacy_env({})
    values, malformed = parse_legacy_env_text(env_path.read_text(encoding="utf-8"))
    return classify_legacy_env(values, malformed=malformed)


def apply_legacy_migration(default: dict[str, Any], migration: LegacyEnvMigration) -> dict[str, Any]:
    state = json.loads(json.dumps(default))
    fragment = migration.as_state_fragment()
    state["migration"] = fragment["migration"]
    state["decisions"].update(fragment["decisions"])
    state["open_items"].extend(fragment["open_items"])
    if state["decisions"] and all(item.get("state") in {"declined", "disabled"} for item in state["decisions"].values()):
        state["status"] = "disabled"
    return state


@contextmanager
def state_lock(project_root: str | Path, *, stale_after_seconds: float = 60.0) -> Iterator[Path]:
    root = validate_project_root(project_root)
    lock_path = project_state_lock_path(root)
    lock_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    payload = {"pid": os.getpid(), "created_at": time.time()}
    while True:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            try:
                age = time.time() - lock_path.stat().st_mtime
            except FileNotFoundError:
                continue
            if age >= stale_after_seconds:
                try:
                    lock_path.unlink()
                    continue
                except FileNotFoundError:
                    continue
            raise StateLockError(f"project-state lock already held: {lock_path}")
        else:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            break
    try:
        yield lock_path
    finally:
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def fsync_directory(path: Path) -> None:
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError as exc:  # pragma: no cover - platform dependent.
        if exc.errno in {errno.EINVAL, errno.EACCES, errno.EPERM}:
            return
        raise
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write_state_atomic(
    project_root: str | Path,
    state: dict[str, Any],
    *,
    expected_revision: int | None = None,
    stale_after_seconds: float = 60.0,
    updated_by: str = DEFAULT_UPDATED_BY,
) -> dict[str, Any]:
    root = validate_project_root(project_root)
    path = project_state_path(root)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    validate_state_root(state, root)

    with state_lock(root, stale_after_seconds=stale_after_seconds):
        current = load_state(root) if path.exists() else None
        current_revision = None if current is None else state_revision(current)
        if expected_revision is not None and current_revision != expected_revision:
            raise RevisionMismatchError(
                f"project-state revision mismatch: expected {expected_revision}, found {current_revision}"
            )
        next_state = json.loads(json.dumps(state))
        next_state["meta"]["revision"] = 1 if current_revision is None else current_revision + 1
        next_state["meta"]["updated_at"] = now_timestamp()
        next_state["meta"]["updated_by"] = updated_by
        validate_state(next_state)

        fd, tmp_name = tempfile.mkstemp(prefix=f".{STATE_FILE_NAME}.", suffix=".tmp", dir=path.parent)
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(next_state, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(tmp_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
            os.replace(tmp_path, path)
            fsync_directory(path.parent)
        finally:
            if tmp_path.exists():
                tmp_path.unlink()
    return next_state
