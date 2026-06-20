#!/usr/bin/env python3
"""Project-state helpers for the ContextForge control plane."""

from __future__ import annotations

import errno
import hashlib
import json
import os
import re
import stat
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator, Mapping

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
CMU_MATH_FOUNDATIONS_ROOT = Path("/home/dgk/gdrive/__CMU/classes/00_MathFoundationsML").resolve()
SAFE_PROJECT_ROOTS = frozenset({WORKSPACE_ROOT, CMU_MATH_FOUNDATIONS_ROOT})
DENIED_PROJECT_ROOTS = frozenset({Path("/").resolve(), HOME, WORKSPACE_ROOT})
ADDITIONAL_SAFE_ROOTS_ENV = "CONTEXTFORGE_ADDITIONAL_SAFE_PROJECT_ROOTS"
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
HOOK_PROMPT_ACTIVE = "active"
HOOK_PROMPT_COMPLETED_VERIFIED = "completed_verified"
HOOK_PROMPT_COMPLETED_UNVERIFIED = "completed_unverified"
HOOK_PROMPT_DISABLED = "disabled"
HOOK_PROMPT_STATES = frozenset(
    {
        HOOK_PROMPT_ACTIVE,
        HOOK_PROMPT_COMPLETED_VERIFIED,
        HOOK_PROMPT_COMPLETED_UNVERIFIED,
        HOOK_PROMPT_DISABLED,
    }
)
HOOK_PROMPT_SUPPRESSING_STATES = frozenset(
    {
        HOOK_PROMPT_COMPLETED_VERIFIED,
        HOOK_PROMPT_COMPLETED_UNVERIFIED,
        HOOK_PROMPT_DISABLED,
    }
)
CLIENT_INIT_SUPPRESSING_STATUSES = frozenset({"verified", "presumed_working", "disabled"})
CLIENTS_REQUIRING_PROJECT_RELOAD = frozenset({"codex", "gemini", "opencode", "pi"})
PROJECT_SCOPED_INSTANTIATION_CLASSES = frozenset({"instance_per_project", "project_scoped_shared_backend"})
PROVISION_STATUSES = frozenset({"none", "pending", "created", "degraded", "failed", "removed", "verified"})
SERVICE_LIFECYCLE_ACTIVATIONS = frozenset({"project_scoped_service_provision", "shared_contextforge_service"})


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


def additional_safe_project_roots() -> frozenset[Path]:
    raw = os.environ.get(ADDITIONAL_SAFE_ROOTS_ENV, "")
    roots = {
        canonical_root(item)
        for item in raw.split(os.pathsep)
        if item.strip()
    }
    return frozenset(root for root in roots if root not in DENIED_PROJECT_ROOTS)


def safe_project_roots() -> frozenset[Path]:
    return SAFE_PROJECT_ROOTS | additional_safe_project_roots()


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def is_safe_project_root(path: Path) -> bool:
    return any(is_relative_to(path, root) for root in safe_project_roots()) and path not in DENIED_PROJECT_ROOTS


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
        if not any(is_relative_to(display_path.resolve(strict=False), root) for root in safe_project_roots()):
            raise RootValidationError(f"project root is not a safe workspace child: {canonical}")
        if not is_safe_project_root(canonical):
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


def state_file_artifact_digest(project_root: str | Path) -> str | None:
    path = project_state_path(project_root)
    if not path.exists():
        return None
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


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
    normalize_service_identity_fields(state)
    normalize_project_service_lifecycle_fields(state)
    normalize_project_init_client_states(state)
    ensure_no_secret_value_fields(state)
    ensure_service_identity_invariants(state)
    ensure_project_init_invariants(state)
    loaded_schema = schema or load_schema()
    if jsonschema is None:
        return
    try:
        jsonschema.Draft202012Validator(loaded_schema).validate(state)
    except jsonschema.ValidationError as exc:
        path = ".".join(str(part) for part in exc.absolute_path)
        location = f" at {path}" if path else ""
        raise StateValidationError(f"invalid project state{location}: {exc.message}") from exc


def ensure_project_init_invariants(state: dict[str, Any]) -> None:
    project_init = state.get("project_init")
    if project_init is None:
        return
    if not isinstance(project_init, dict):
        raise StateValidationError("project_init must be an object")
    current_job_id = project_init.get("current_job_id")
    jobs = project_init.get("activation_jobs")
    if not isinstance(jobs, dict):
        raise StateValidationError("project_init.activation_jobs must be an object")
    if current_job_id is not None and current_job_id not in jobs:
        raise StateValidationError("project_init.current_job_id does not exist in activation_jobs")
    client_states = project_init.get("client_states")
    if not isinstance(client_states, dict):
        raise StateValidationError("project_init.client_states must be an object")
    for key, client_state in client_states.items():
        if not isinstance(client_state, dict):
            raise StateValidationError(f"project_init client state must be an object: {key}")
        if client_state.get("client_type") != key:
            raise StateValidationError(f"project_init client state key does not match client_type: {key}")
        client_job_id = client_state.get("current_job_id")
        if client_job_id is not None and client_job_id not in jobs:
            raise StateValidationError(f"project_init client state current_job_id does not exist in activation_jobs: {key}")
    for key, job in jobs.items():
        if not isinstance(job, dict):
            raise StateValidationError(f"activation job must be an object: {key}")
        if job.get("job_id") != key:
            raise StateValidationError(f"activation job key does not match job_id: {key}")
        if not job.get("consent_receipt_refs"):
            raise StateValidationError(f"activation job missing consent receipt refs: {key}")
        service_ids = job.get("selected_service_ids")
        if not isinstance(service_ids, list) or not all(isinstance(item, str) and item for item in service_ids):
            raise StateValidationError(f"activation job selected_service_ids must be non-empty strings: {key}")
        records = job.get("validation_records")
        if not isinstance(records, dict):
            raise StateValidationError(f"activation job validation_records must be an object: {key}")
        if job.get("status") == "verified":
            for service_key, record in records.items():
                if not isinstance(record, dict):
                    raise StateValidationError(f"validation record must be an object: {service_key}")
                if record.get("status") != "passed" or record.get("target_client_visible") is not True:
                    raise StateValidationError(f"verified activation job has unverified validation record: {service_key}")


def normalize_service_identity_fields(state: dict[str, Any]) -> None:
    services = state.get("services")
    if not isinstance(services, dict):
        return
    by_binding: dict[str, str] = {}
    by_legacy_key: dict[str, str] = {}
    for service_key, service in services.items():
        if not isinstance(service, dict):
            continue
        identity = _state_service_identity_for(service)
        service["x_descriptor_digest"] = identity["descriptor_digest"]
        if identity["contextforge_server_id"]:
            service["x_contextforge_server_id"] = identity["contextforge_server_id"]
        else:
            service.pop("x_contextforge_server_id", None)
        service["x_service_identity"] = {
            "id": identity["id"],
            "descriptor_digest": identity["descriptor_digest"],
            "contextforge_server_id": identity["contextforge_server_id"],
            "source": "project_state_service_record",
        }
        service["x_service_identity_id"] = identity["id"]
        binding = str(service.get("service_binding") or service_key)
        by_binding[binding] = identity["id"]
        by_legacy_key[_state_map_key(binding)] = identity["id"]
        target_clients = service.get("target_clients")
        if isinstance(target_clients, dict):
            for target_client in target_clients.values():
                if not isinstance(target_client, dict):
                    continue
                target_client["service_identity_id"] = identity["id"]
                if identity["contextforge_server_id"]:
                    target_client["contextforge_server_id"] = identity["contextforge_server_id"]
                else:
                    target_client.pop("contextforge_server_id", None)
    decisions = state.get("decisions")
    if isinstance(decisions, dict):
        for decision in decisions.values():
            if not isinstance(decision, dict):
                continue
            binding = str(decision.get("service_binding") or "")
            identity_id = by_binding.get(binding)
            if identity_id:
                decision["x_service_identity_id"] = identity_id
    project_init = state.get("project_init")
    jobs = project_init.get("activation_jobs") if isinstance(project_init, dict) and isinstance(project_init.get("activation_jobs"), dict) else {}
    for job in jobs.values():
        if not isinstance(job, dict):
            continue
        selected_ids = [str(item) for item in job.get("selected_service_ids") or [] if item]
        selected_bindings = [str(item) for item in job.get("selected_service_bindings") or [] if item]
        if not selected_ids and selected_bindings:
            selected_ids = [by_binding.get(binding) or by_legacy_key.get(_state_map_key(binding)) or binding for binding in selected_bindings]
        job["selected_service_ids"] = selected_ids
        records = job.get("validation_records")
        if not isinstance(records, dict):
            continue
        for binding, identity_id in by_binding.items():
            legacy_key = _state_map_key(binding)
            record = records.get(binding) or records.get(legacy_key)
            if isinstance(record, dict) and identity_id not in records:
                record["x_service_binding"] = binding
                record["x_service_identity_id"] = identity_id
                records[identity_id] = record


def normalize_project_service_lifecycle_fields(state: dict[str, Any]) -> None:
    services = state.get("services")
    if not isinstance(services, dict):
        return
    for service in services.values():
        if not isinstance(service, dict):
            continue
        instantiation_class = str(service.get("instantiation_class") or "shared_canonical")
        expected_activation = (
            "project_scoped_service_provision"
            if instantiation_class in PROJECT_SCOPED_INSTANTIATION_CLASSES
            else "shared_contextforge_service"
        )
        lifecycle = service.get("lifecycle") if isinstance(service.get("lifecycle"), dict) else {}
        lifecycle["activation"] = expected_activation
        lifecycle["non_actions"] = _dedupe_strings(lifecycle.get("non_actions") or [])
        service["lifecycle"] = lifecycle
        if service.get("provision_status") not in PROVISION_STATUSES:
            service["provision_status"] = "none"


def ensure_service_identity_invariants(state: dict[str, Any]) -> None:
    services = state.get("services")
    if not isinstance(services, dict):
        return
    service_identity_keys: dict[str, str] = {}
    service_bindings: dict[str, str] = {}
    project_scoped_backends: dict[tuple[str, str, str], str] = {}
    for service_key, service in services.items():
        if not isinstance(service, dict):
            continue
        binding = str(service.get("service_binding") or service_key)
        previous_binding_key = service_bindings.setdefault(binding, service_key)
        if previous_binding_key != service_key:
            raise StateValidationError(
                f"duplicate service_binding records are not allowed: {binding} in {previous_binding_key} and {service_key}"
            )
        identity_id = str(service.get("x_service_identity_id") or _state_service_identity_for(service)["id"])
        previous_identity_key = service_identity_keys.setdefault(identity_id, service_key)
        if previous_identity_key != service_key:
            raise StateValidationError(
                f"duplicate service identity records are not allowed: {identity_id} in {previous_identity_key} and {service_key}"
            )
        instantiation_class = str(service.get("instantiation_class") or "")
        if instantiation_class not in PROJECT_SCOPED_INSTANTIATION_CLASSES:
            continue
        backend_instance = str(service.get("backend_instance") or "")
        virtual_server = str(service.get("virtual_server") or "")
        if not backend_instance and not virtual_server:
            continue
        backend_key = (str(service.get("service_family") or ""), backend_instance, virtual_server)
        previous_backend_key = project_scoped_backends.setdefault(backend_key, service_key)
        if previous_backend_key != service_key:
            raise StateValidationError(
                "duplicate project-scoped service backend records are not allowed: "
                f"{backend_key!r} in {previous_backend_key} and {service_key}"
            )


def normalize_project_init_client_states(state: dict[str, Any]) -> None:
    project_init = state.get("project_init")
    if not isinstance(project_init, dict):
        return
    jobs = project_init.get("activation_jobs") if isinstance(project_init.get("activation_jobs"), dict) else {}
    existing = project_init.get("client_states") if isinstance(project_init.get("client_states"), dict) else {}
    derived: dict[str, dict[str, Any]] = {}
    updated_at = str((state.get("meta") if isinstance(state.get("meta"), dict) else {}).get("updated_at") or now_timestamp())

    for job in jobs.values():
        if not isinstance(job, dict):
            continue
        client_type = str(job.get("client_type") or "")
        if not client_type:
            continue
        derived[client_type] = _client_state_from_job(client_type, job, updated_at=updated_at)

    for client_type, state_from_services in _client_states_from_service_targets(state, updated_at=updated_at).items():
        derived.setdefault(client_type, state_from_services)

    normalized: dict[str, dict[str, Any]] = {}
    for client_type, state_record in derived.items():
        normalized[client_type] = _normalize_client_state_record(client_type, state_record, fallback=None, updated_at=updated_at)
        existing_record = existing.get(client_type)
        if isinstance(existing_record, dict):
            for key, value in existing_record.items():
                if str(key).startswith("x_"):
                    normalized[client_type][key] = value

    for client_type, state_record in existing.items():
        if client_type in normalized or not isinstance(state_record, dict):
            continue
        normalized[client_type] = _normalize_client_state_record(str(client_type), state_record, fallback=None, updated_at=updated_at)

    project_init["client_states"] = normalized


def _client_states_from_service_targets(state: dict[str, Any], *, updated_at: str) -> dict[str, dict[str, Any]]:
    services = state.get("services")
    if not isinstance(services, dict):
        return {}
    by_client: dict[str, dict[str, Any]] = {}
    for service_key, service in services.items():
        if not isinstance(service, dict):
            continue
        binding = str(service.get("service_binding") or service_key)
        target_clients = service.get("target_clients")
        if not isinstance(target_clients, dict):
            continue
        service_identity_id = str(service.get("x_service_identity_id") or _state_service_identity_for(service)["id"])
        for client_type, target_record in target_clients.items():
            if not isinstance(target_record, dict):
                continue
            client = str(client_type)
            record = by_client.setdefault(
                client,
                {
                    "client_type": client,
                    "status": "validation_pending",
                    "current_job_id": None,
                    "activation_surface": target_record.get("surface"),
                    "selected_service_ids": [],
                    "selected_service_bindings": [],
                    "validation_status": "not_started",
                    "reload_status": "unknown",
                    "updated_at": updated_at,
                    "last_plan_id": None,
                    "local_client_config_digest": None,
                    "x_validation_statuses": [],
                },
            )
            if target_record.get("surface") and not record.get("activation_surface"):
                record["activation_surface"] = target_record.get("surface")
            record["selected_service_ids"].append(str(target_record.get("service_identity_id") or service_identity_id))
            record["selected_service_bindings"].append(binding)
            record.setdefault("x_validation_statuses", []).append(str(target_record.get("validation_status") or "pending"))

    for record in by_client.values():
        validation_status = _aggregate_client_validation_status(list(record.pop("x_validation_statuses", [])))
        record["validation_status"] = validation_status
        record["status"] = _client_lifecycle_status_from_validation(validation_status)
        record["selected_service_ids"] = _dedupe_strings(record.get("selected_service_ids") or [])
        record["selected_service_bindings"] = _dedupe_strings(record.get("selected_service_bindings") or [])
    return by_client


def _client_state_from_job(client_type: str, job: dict[str, Any], *, updated_at: str) -> dict[str, Any]:
    validation_records = job.get("validation_records") if isinstance(job.get("validation_records"), dict) else {}
    validation_status = _aggregate_client_validation_status(
        [str(record.get("status") or "pending") for record in validation_records.values() if isinstance(record, dict)]
    )
    reload_status = _client_reload_status_from_job(client_type, job)
    status = _client_lifecycle_status_from_job(job, validation_status=validation_status, reload_status=reload_status)
    return {
        "client_type": client_type,
        "status": status,
        "current_job_id": str(job.get("job_id") or "") or None,
        "activation_surface": _surface_from_job_or_client(client_type, job),
        "selected_service_ids": _dedupe_strings(job.get("selected_service_ids") or []),
        "selected_service_bindings": _dedupe_strings(job.get("selected_service_bindings") or []),
        "validation_status": validation_status,
        "reload_status": reload_status,
        "updated_at": updated_at,
        "last_plan_id": str(job.get("plan_id") or "") or None,
        "local_client_config_digest": job.get("local_client_config_digest"),
    }


def _normalize_client_state_record(
    client_type: str,
    record: dict[str, Any],
    *,
    fallback: dict[str, Any] | None,
    updated_at: str,
) -> dict[str, Any]:
    fallback = fallback or {}
    selected_ids = _dedupe_strings(record.get("selected_service_ids") or fallback.get("selected_service_ids") or [])
    selected_bindings = _dedupe_strings(record.get("selected_service_bindings") or fallback.get("selected_service_bindings") or [])
    status = str(record.get("status") or fallback.get("status") or ("validation_pending" if selected_ids or selected_bindings else "uninitialized"))
    if status not in {"uninitialized", "activation_pending", "reload_required", "validation_pending", "installed", "presumed_working", "verified", "disabled", "blocked"}:
        status = "validation_pending"
    validation_status = str(record.get("validation_status") or fallback.get("validation_status") or "not_started")
    if validation_status not in {"not_started", "pending", "installed", "passed", "presumed_working", "skipped", "mixed", "blocked"}:
        validation_status = "pending"
    reload_status = str(record.get("reload_status") or fallback.get("reload_status") or "unknown")
    if reload_status not in {"not_required", "required", "acknowledged", "pending_reload", "reload_observed", "reload_acknowledged", "unknown"}:
        reload_status = "unknown"
    return {
        "client_type": client_type,
        "status": status,
        "current_job_id": record.get("current_job_id") or fallback.get("current_job_id"),
        "activation_surface": record.get("activation_surface") or fallback.get("activation_surface"),
        "selected_service_ids": selected_ids,
        "selected_service_bindings": selected_bindings,
        "validation_status": validation_status,
        "reload_status": reload_status,
        "updated_at": record.get("updated_at") or fallback.get("updated_at") or updated_at,
        "last_plan_id": record.get("last_plan_id") or fallback.get("last_plan_id"),
        "local_client_config_digest": record.get("local_client_config_digest") or fallback.get("local_client_config_digest"),
    }


def _dedupe_strings(values: Any) -> list[str]:
    return list(dict.fromkeys(str(value) for value in values if value))


def _aggregate_client_validation_status(statuses: list[str]) -> str:
    normalized = []
    for status in statuses:
        if status in {"passed", "verified"}:
            normalized.append("passed")
        elif status == "presumed_working":
            normalized.append("presumed_working")
        elif status == "installed":
            normalized.append("installed")
        elif status == "skipped":
            normalized.append("skipped")
        elif status in {"blocked", "failed"}:
            normalized.append("blocked")
        elif status in {"pending", "pending_user_choice", "validation_pending"}:
            normalized.append("pending")
        elif status:
            normalized.append("mixed")
    if not normalized:
        return "not_started"
    if all(status == "passed" for status in normalized):
        return "passed"
    if all(status == "presumed_working" for status in normalized):
        return "presumed_working"
    if all(status == "installed" for status in normalized):
        return "installed"
    if all(status == "skipped" for status in normalized):
        return "skipped"
    if any(status == "blocked" for status in normalized):
        return "blocked"
    if any(status == "pending" for status in normalized):
        return "pending"
    return "mixed"


def _client_lifecycle_status_from_validation(validation_status: str) -> str:
    if validation_status == "passed":
        return "verified"
    if validation_status == "presumed_working":
        return "presumed_working"
    if validation_status == "installed":
        return "installed"
    if validation_status == "blocked":
        return "blocked"
    return "validation_pending"


def _client_reload_status_from_job(client_type: str, job: dict[str, Any]) -> str:
    if client_type not in CLIENTS_REQUIRING_PROJECT_RELOAD:
        return "not_required"
    fsm = job.get("x_client_reload_fsm") if isinstance(job.get("x_client_reload_fsm"), dict) else {}
    if str(fsm.get("client_type") or "") == client_type:
        state = str(fsm.get("state") or "")
        if state in {"pending_reload", "reload_observed", "reload_acknowledged"}:
            return state
    ack = job.get("x_client_reload_ack") if isinstance(job.get("x_client_reload_ack"), dict) else {}
    if str(ack.get("client_type") or "") == client_type and bool(ack.get("acknowledged_at")):
        return "reload_acknowledged"
    if job.get("status") in {"verified", "presumed_working"}:
        return "unknown"
    return "pending_reload"


def _client_lifecycle_status_from_job(job: dict[str, Any], *, validation_status: str, reload_status: str) -> str:
    job_status = str(job.get("status") or "")
    recovery_state = str(job.get("recovery_state") or "")
    if job_status == "verified" or validation_status == "passed":
        return "verified"
    if job_status == "presumed_working" or validation_status == "presumed_working":
        return "presumed_working"
    if job_status == "installed" or validation_status == "installed":
        return "installed"
    if job_status in {"failed", "fresh_approval_required", "manual_recovery"} or recovery_state in {"manual_recovery", "fresh_approval_required"}:
        return "blocked"
    if reload_status in {"required", "pending_reload", "reload_observed"}:
        return "reload_required"
    return "validation_pending"


def _surface_from_job_or_client(client_type: str, job: dict[str, Any]) -> str | None:
    if client_type == "codex":
        return ".codex/config.toml"
    if client_type == "gemini":
        return ".gemini/settings.json"
    if client_type == "opencode":
        return "opencode.json"
    if client_type == "pi":
        return "contextforge-global-shim"
    return None


def project_init_client_state(state: dict[str, Any], client_type: str) -> dict[str, Any] | None:
    project_init = state.get("project_init") if isinstance(state.get("project_init"), dict) else {}
    client_states = project_init.get("client_states") if isinstance(project_init.get("client_states"), dict) else {}
    record = client_states.get(client_type)
    return dict(record) if isinstance(record, dict) else None


def project_init_current_job_id_for_client(state: dict[str, Any], client_type: str) -> str | None:
    client_state = project_init_client_state(state, client_type)
    if client_state and client_state.get("current_job_id"):
        return str(client_state.get("current_job_id"))
    project_init = state.get("project_init") if isinstance(state.get("project_init"), dict) else {}
    return str(project_init.get("current_job_id") or "") or None


def client_hook_prompt_state_for(state: dict[str, Any], client_type: str) -> str:
    if str(state.get("status") or "") == "disabled":
        return HOOK_PROMPT_DISABLED
    project_init = state.get("project_init") if isinstance(state.get("project_init"), dict) else {}
    client_states = project_init.get("client_states") if isinstance(project_init.get("client_states"), dict) else {}
    client_state = client_states.get(client_type) if isinstance(client_states.get(client_type), dict) else None
    if client_state is None:
        return HOOK_PROMPT_ACTIVE if client_states else hook_prompt_state_for(state)
    status = str(client_state.get("status") or "uninitialized")
    if status == "disabled":
        return HOOK_PROMPT_DISABLED
    if status == "verified":
        return HOOK_PROMPT_COMPLETED_VERIFIED
    if status == "presumed_working":
        return HOOK_PROMPT_COMPLETED_UNVERIFIED
    if status == "installed":
        return HOOK_PROMPT_COMPLETED_UNVERIFIED
    return HOOK_PROMPT_ACTIVE


def _state_service_identity_for(service: dict[str, Any]) -> dict[str, Any]:
    identity = service.get("x_service_identity") if isinstance(service.get("x_service_identity"), dict) else {}
    explicit_id = service.get("x_service_identity_id") or identity.get("id")
    descriptor_digest = str(service.get("x_descriptor_digest") or identity.get("descriptor_digest") or _service_descriptor_digest(service))
    contextforge_server_id = service.get("x_contextforge_server_id") or identity.get("contextforge_server_id")
    if contextforge_server_id is not None:
        contextforge_server_id = str(contextforge_server_id)
    computed_id = _service_identity_id(
        binding=str(service.get("service_binding") or service.get("service_family") or ""),
        descriptor_digest=descriptor_digest,
        backend_instance=service.get("backend_instance"),
        virtual_server=service.get("virtual_server"),
        contextforge_server_id=contextforge_server_id,
    )
    return {
        "id": str(explicit_id or computed_id),
        "descriptor_digest": descriptor_digest,
        "contextforge_server_id": contextforge_server_id,
    }


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


def default_project_init() -> dict[str, Any]:
    return {
        "current_job_id": None,
        "client_states": {},
        "activation_jobs": {},
        "x_hook_prompt_state": HOOK_PROMPT_ACTIVE,
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
        "project_init": default_project_init(),
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


def apply_project_init_activation_to_state(
    state: dict[str, Any],
    selected_services: list[dict[str, Any]],
    *,
    target_client: str,
    client_config_plan: dict[str, Any],
    validation_plan: dict[str, Any],
    validation_results: dict[str, Any] | None = None,
    activation_job: dict[str, Any] | None = None,
    consent_receipt_refs: list[str] | None = None,
    updated_by: str = DEFAULT_UPDATED_BY,
) -> dict[str, Any]:
    """Return updated project-init state for approved local service activation.

    This helper is intentionally limited to project-local state semantics. It
    records selected ContextForge virtual-server bindings, the target-client
    config write status, validation mode/results, and explicit non-actions. It
    does not create backend ownership claims or treat client config as service
    identity.
    """

    next_state = json.loads(json.dumps(state))
    validate_supported_schema_version(next_state)
    validation_results = validation_results or {}
    consent_receipt_refs = list(consent_receipt_refs or [])
    if not consent_receipt_refs:
        raise StateValidationError("project-init activation state requires scoped consent receipt refs")
    now = now_timestamp()
    next_state["meta"]["updated_at"] = now
    next_state["meta"]["updated_by"] = updated_by
    next_state["meta"]["last_plan_id"] = _activation_plan_id(selected_services, client_config_plan, validation_plan)
    next_state.setdefault("decisions", {})
    next_state.setdefault("services", {})
    next_state.setdefault("client_trust", {})
    next_state.setdefault("open_items", [])
    next_state.setdefault("artifact_refs", empty_artifact_refs())
    next_state.setdefault("project_init", default_project_init())
    next_state["project_init"].setdefault("x_hook_prompt_state", HOOK_PROMPT_ACTIVE)
    next_state["project_init"].setdefault("client_states", {})
    plan_id = next_state["meta"]["last_plan_id"]

    all_target_client_verified = bool(selected_services)
    for service in selected_services:
        binding = str(service.get("service_binding") or service.get("service_family") or "")
        if not binding:
            raise StateValidationError("selected service missing service_binding")
        service_key = _state_map_key(binding)
        legacy_service_key = _service_key_for_binding(next_state["services"], binding)
        existing_service = next_state["services"].get(legacy_service_key or service_key)
        existing_service = existing_service if isinstance(existing_service, dict) else {}
        existing_target_clients = existing_service.get("target_clients") if isinstance(existing_service.get("target_clients"), dict) else {}
        target_clients = json.loads(json.dumps(existing_target_clients))
        existing_receipts = [str(item) for item in existing_service.get("consent_receipt_refs") or [] if item]
        existing_evidence = list(existing_service.get("evidence") or []) if isinstance(existing_service.get("evidence"), list) else []
        contract_ref = _service_ref("service-bindings", binding)
        capsule_ref = _service_ref("capability-capsules", binding) if service.get("instantiation_class") == "shared_canonical" else None
        semantic_policy_ref = _service_ref("semantic-tool-policies", binding)
        identity_service = dict(service)
        stale_contextforge_server_id = _existing_contextforge_server_id(next_state["services"].get(service_key))
        if (
            stale_contextforge_server_id
            and not identity_service.get("contextforge_server_id")
            and not _contextforge_id_is_authoritatively_absent(identity_service)
        ):
            identity_service["contextforge_server_id"] = stale_contextforge_server_id
        service_identity = _service_identity_for(identity_service)
        descriptor_digest = service_identity["descriptor_digest"]
        service_identity_id = service_identity["id"]
        contextforge_server_id = service_identity["contextforge_server_id"]
        stale_identity_id = _existing_service_identity_id(next_state["services"].get(service_key))
        if stale_identity_id and stale_identity_id != service_identity_id:
            _record_stale_service_id(
                next_state,
                binding=binding,
                stale_id=stale_identity_id,
                current_id=service_identity_id,
                id_kind="service_identity",
                now=now,
            )
        if (
            stale_contextforge_server_id
            and stale_contextforge_server_id != contextforge_server_id
            and (contextforge_server_id or _contextforge_id_is_authoritatively_absent(service))
        ):
            _record_stale_service_id(
                next_state,
                binding=binding,
                stale_id=stale_contextforge_server_id,
                current_id=contextforge_server_id if contextforge_server_id else None,
                id_kind="contextforge_server",
                now=now,
            )
        result = _validation_result_for(validation_results, binding, service_identity_id)
        validation_status = _service_validation_status(validation_plan, binding, result)
        if validation_status != "passed":
            all_target_client_verified = False
        target_clients[target_client] = _target_client_activation_record(
            service,
            target_client=target_client,
            client_config_plan=client_config_plan,
            validation_status=validation_status,
        )
        service_evidence = [
            {
                "kind": "project_init_activation",
                "target_client": target_client,
                "service_identity_id": service_identity_id,
                "contextforge_server_id": contextforge_server_id,
                "descriptor_digest": descriptor_digest,
                "client_config_after_digest": client_config_plan.get("after_digest"),
                "validation_mode": validation_plan.get("validation_mode"),
                "validation_status": validation_status,
                "client_configs_are_service_identities": False,
            }
        ]
        next_state["decisions"][service_key] = {
            "decision_kind": "service",
            "state": "accepted",
            "x_service_identity_id": service_identity_id,
            "service_binding": binding,
            "contract_card_ref": contract_ref,
            "decided_at": now,
            "decided_by": updated_by,
            "source_plan_id": next_state["meta"]["last_plan_id"],
            "reopened_at": None,
            "notes": "project-local ContextForge service activation approved",
            "x_validation_mode": validation_plan.get("validation_mode"),
            "x_non_actions": list(service.get("non_actions") or []),
        }
        if legacy_service_key and legacy_service_key != service_key:
            del next_state["services"][legacy_service_key]
        next_state["services"][service_key] = {
            "service_family": str(service.get("service_family") or service_key),
            "service_binding": binding,
            "instantiation_class": str(service.get("instantiation_class") or "shared_canonical"),
            "contract_card_ref": contract_ref,
            "capability_capsule_ref": capsule_ref,
            "semantic_tool_policy_ref": semantic_policy_ref,
            "backend_instance": service.get("backend_instance"),
            "virtual_server": service.get("virtual_server"),
            "provision_status": _provision_status_for(service, validation_status, existing_service=existing_service),
            "lifecycle": _service_lifecycle_for(service, existing_service=existing_service),
            "language_profile": None,
            "required_verification_layers": ["contextforge_gateway", "target_client", "tool_policy", "redaction"],
            "verification_layers": {
                "contextforge_gateway": {"status": service.get("contextforge_readback_status") or "not_checked"},
                "target_client": {
                    "status": _target_client_validation_summary(target_clients),
                    "mode": "per_client",
                    "proof": "see target_clients for client-specific validation evidence",
                },
                "tool_policy": {"status": "safe_default_selected", "policy": service.get("validation_policy")},
                "redaction": {"status": "passed"},
            },
            "target_clients": target_clients,
            "verification_trace_refs": list(result.get("verification_trace_refs") or []),
            "consent_receipt_refs": _dedupe_strings([*existing_receipts, *consent_receipt_refs]),
            "evidence": [*existing_evidence, *service_evidence],
            "x_non_actions": list(service.get("non_actions") or []),
            "x_descriptor_digest": descriptor_digest,
            **({"x_contextforge_server_id": contextforge_server_id} if contextforge_server_id else {}),
            "x_service_identity": {
                "id": service_identity_id,
                "descriptor_digest": descriptor_digest,
                "contextforge_server_id": contextforge_server_id,
                "source": "project_init_selected_service_descriptor",
            },
        }

    job_record = _activation_job_record(
        plan_id=plan_id,
        selected_services=selected_services,
        target_client=target_client,
        client_config_plan=client_config_plan,
        validation_plan=validation_plan,
        validation_results=validation_results,
        consent_receipt_refs=consent_receipt_refs,
        activation_job=activation_job,
    )
    next_state["project_init"]["current_job_id"] = job_record["job_id"]
    next_state["project_init"].setdefault("activation_jobs", {})[job_record["job_id"]] = job_record
    client_state = _client_state_from_job(target_client, job_record, updated_at=now)
    client_state["activation_surface"] = client_config_plan.get("surface") or client_state.get("activation_surface")
    client_state["local_client_config_digest"] = client_config_plan.get("after_digest")
    next_state["project_init"].setdefault("client_states", {})[target_client] = client_state

    next_state["client_trust"][target_client] = {
        "state": "not_required" if target_client == "pi" else "unknown",
        "root": next_state["project"]["root"],
        "trust_surface": _trust_surface_for(target_client),
        "approval_record": None,
        "verified_at": None,
        "last_probe": None,
    }
    installation_only = validation_plan.get("validation_mode") == "installed"
    if installation_only:
        next_state["status"] = "initialized"
        next_state["project_init"]["x_hook_prompt_state"] = HOOK_PROMPT_COMPLETED_UNVERIFIED
        _resolve_open_item(next_state, "project-init-validation")
    elif all_target_client_verified:
        next_state["status"] = "initialized"
        next_state["project_init"]["x_hook_prompt_state"] = HOOK_PROMPT_COMPLETED_VERIFIED
        _resolve_open_item(next_state, "project-init-validation")
    else:
        next_state["status"] = "in_progress"
        next_state["project_init"]["x_hook_prompt_state"] = (
            HOOK_PROMPT_COMPLETED_UNVERIFIED
            if validation_plan.get("validation_mode") == "presume_working"
            else HOOK_PROMPT_ACTIVE
        )
        _upsert_open_item(
            next_state,
            {
                "id": "project-init-validation",
                "type": "verification",
                "severity": "warning",
                "blocks_initialized": False,
                "resource": "target-client post-install check",
                "created_at": now,
                "resolution_state": "deferred" if validation_plan.get("validation_mode") == "presume_working" else "open",
                "detail": {
                    "validation_mode": validation_plan.get("validation_mode"),
                    "reason": "target-client validation was not completed during activation",
                    "accepted_state": "bindings recorded but not verified as working",
                },
            },
        )
    validate_state(next_state)
    return next_state


def read_json_file(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StateValidationError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise StateValidationError(f"project state must be a JSON object: {path}")
    return data


def hook_prompt_state_for(state: dict[str, Any]) -> str:
    status = str(state.get("status") or "")
    if status == "initialized":
        return HOOK_PROMPT_COMPLETED_VERIFIED
    if status == "disabled":
        return HOOK_PROMPT_DISABLED
    project_init = state.get("project_init") if isinstance(state.get("project_init"), dict) else {}
    raw = project_init.get("x_hook_prompt_state")
    if raw in HOOK_PROMPT_STATES:
        return str(raw)
    return HOOK_PROMPT_ACTIVE


def root_match_details(raw_state: Any, root: Path) -> dict[str, Any]:
    if not isinstance(raw_state, dict):
        return {
            "root_matches": False,
            "root_hash_matches": False,
            "state_root": None,
            "state_root_hash": None,
            "expected_root": str(root),
            "expected_root_hash": project_root_hash(root),
        }
    project = raw_state.get("project") if isinstance(raw_state.get("project"), dict) else {}
    state_root = project.get("root")
    state_hash = project.get("root_hash")
    expected_hash = project_root_hash(root)
    return {
        "root_matches": state_root == str(root),
        "root_hash_matches": state_hash == expected_hash,
        "state_root": state_root,
        "state_root_hash": state_hash,
        "expected_root": str(root),
        "expected_root_hash": expected_hash,
    }


def inspect_project_init_state(
    project_root: str | Path,
    *,
    require_workspace: bool = False,
    target_client: str | None = None,
) -> dict[str, Any]:
    """Return a non-throwing project-init lifecycle inspection.

    The hook layer needs to distinguish missing, valid, repairable-invalid, and
    blocked-invalid state without collapsing every load failure into a fresh
    initialization prompt.
    """

    try:
        root = validate_project_root(project_root, require_workspace=require_workspace)
    except Exception as exc:
        return {
            "lifecycle_status": "invalid_blocked",
            "raw_status": None,
            "schema_error": str(exc),
            "root_matches": False,
            "root_hash_matches": False,
            "project_init_present": False,
            "hook_prompt_state": HOOK_PROMPT_ACTIVE,
            "target_client": target_client,
            "target_client_state": None,
            "recommended_action": "blocked_repair",
            "should_suppress_hook": False,
            "state_path": str(project_state_path(project_root)),
        }

    path = project_state_path(root)
    if not path.exists():
        return {
            "lifecycle_status": "missing",
            "raw_status": None,
            "schema_error": None,
            "root_matches": None,
            "root_hash_matches": None,
            "project_init_present": False,
            "hook_prompt_state": HOOK_PROMPT_ACTIVE,
            "target_client": target_client,
            "target_client_state": None,
            "recommended_action": "fresh_initialization",
            "should_suppress_hook": False,
            "state_path": str(path),
        }

    raw_state: dict[str, Any] | None = None
    try:
        raw_state = read_json_file(path)
    except StateValidationError as exc:
        return {
            "lifecycle_status": "invalid_blocked",
            "raw_status": None,
            "schema_error": str(exc),
            "root_matches": False,
            "root_hash_matches": False,
            "project_init_present": False,
            "hook_prompt_state": HOOK_PROMPT_ACTIVE,
            "target_client": target_client,
            "target_client_state": None,
            "recommended_action": "blocked_repair",
            "should_suppress_hook": False,
            "state_path": str(path),
        }

    raw_status = str(raw_state.get("status") or "")
    project_init_present = isinstance(raw_state.get("project_init"), dict)
    root_details = root_match_details(raw_state, root)
    raw_hook_state = HOOK_PROMPT_ACTIVE
    if project_init_present:
        value = raw_state["project_init"].get("x_hook_prompt_state")
        if value in HOOK_PROMPT_STATES:
            raw_hook_state = str(value)

    try:
        state = load_state(root, require_workspace=require_workspace)
        assert state is not None
    except StateValidationError as exc:
        repairable = (
            root_details["root_matches"] is True
            and root_details["root_hash_matches"] is True
            and not project_init_present
            and isinstance(raw_state.get("services"), dict)
            and bool(raw_state.get("services"))
        )
        return {
            "lifecycle_status": "invalid_repairable" if repairable else "invalid_blocked",
            "raw_status": raw_status,
            "schema_error": str(exc),
            **root_details,
            "project_init_present": project_init_present,
            "hook_prompt_state": raw_hook_state,
            "target_client": target_client,
            "target_client_state": None,
            "recommended_action": "repair_project_init_state" if repairable else "blocked_repair",
            "should_suppress_hook": False,
            "state_path": str(path),
        }

    client_state = project_init_client_state(state, target_client) if target_client else None
    hook_state = client_hook_prompt_state_for(state, target_client) if target_client else hook_prompt_state_for(state)
    status = str(state.get("status") or "unknown")
    should_suppress = hook_state in HOOK_PROMPT_SUPPRESSING_STATES
    if should_suppress:
        action = "suppress"
    elif client_state and client_state.get("status") in {"activation_pending", "reload_required", "validation_pending"}:
        action = "resume_project_init"
    elif status == "in_progress":
        action = "resume_project_init"
    else:
        action = "fresh_initialization"
    return {
        "lifecycle_status": "valid",
        "raw_status": status,
        "schema_error": None,
        **root_match_details(state, root),
        "project_init_present": True,
        "hook_prompt_state": hook_state,
        "target_client": target_client,
        "target_client_state": client_state,
        "recommended_action": action,
        "should_suppress_hook": should_suppress,
        "state_path": str(path),
    }


def _activation_plan_id(
    selected_services: list[dict[str, Any]],
    client_config_plan: dict[str, Any],
    validation_plan: dict[str, Any],
) -> str:
    payload = {
        "services": [
            {
                "service_identity_id": _service_identity_for(service)["id"],
                "target_alias": service.get("codex_alias"),
            }
            for service in selected_services
        ],
        "client_config_after_digest": client_config_plan.get("after_digest"),
        "validation_mode": validation_plan.get("validation_mode"),
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return f"project-init-activation-{digest[:16]}"


def _activation_surface_for(target_client: str) -> str:
    if target_client == "pi":
        return "pi_global_extension_shim_activation"
    if target_client == "gemini":
        return "gemini_project_local_mcp_settings"
    if target_client == "opencode":
        return "opencode_project_local_mcp_config"
    return "project_local_client_binding"


def _service_identity_for(service: dict[str, Any]) -> dict[str, Any]:
    binding = str(service.get("service_binding") or service.get("service_family") or "")
    descriptor_digest = str(service.get("descriptor_digest") or _service_descriptor_digest(service))
    contextforge_server_id = service.get("contextforge_server_id")
    if contextforge_server_id is not None:
        contextforge_server_id = str(contextforge_server_id)
    return {
        "id": _service_identity_id(
            binding=binding,
            descriptor_digest=descriptor_digest,
            backend_instance=service.get("backend_instance"),
            virtual_server=service.get("virtual_server"),
            contextforge_server_id=contextforge_server_id,
        ),
        "descriptor_digest": descriptor_digest,
        "contextforge_server_id": contextforge_server_id,
    }


def _service_descriptor_digest(service: dict[str, Any]) -> str:
    payload = {
        "service_family": service.get("service_family"),
        "service_binding": service.get("service_binding"),
        "instantiation_class": service.get("instantiation_class"),
        "backend_instance": service.get("backend_instance"),
        "virtual_server": service.get("virtual_server"),
        "validation_policy": service.get("validation_policy"),
    }
    return _sha256_ref(payload)


def _service_identity_id(
    *,
    binding: str,
    descriptor_digest: str,
    backend_instance: Any,
    virtual_server: Any,
    contextforge_server_id: Any = None,
) -> str:
    payload = {
        "binding": binding,
        "contextforge_server_id": contextforge_server_id,
        "descriptor_digest": descriptor_digest,
        "backend_instance": backend_instance,
        "virtual_server": virtual_server,
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()
    return f"contextforge-service-{digest[:24]}"


def _existing_service_identity_id(record: Any) -> str | None:
    if not isinstance(record, dict):
        return None
    identity = record.get("x_service_identity")
    if isinstance(identity, dict) and isinstance(identity.get("id"), str):
        return identity["id"]
    if isinstance(record.get("x_service_identity_id"), str):
        return record["x_service_identity_id"]
    return None


def _existing_contextforge_server_id(record: Any) -> str | None:
    if isinstance(record, dict) and isinstance(record.get("x_contextforge_server_id"), str):
        return record["x_contextforge_server_id"]
    return None


def _contextforge_id_is_authoritatively_absent(service: dict[str, Any]) -> bool:
    return service.get("contextforge_readback_status") in {"missing", "not_found", "absent"}


def _record_stale_service_id(
    next_state: dict[str, Any],
    *,
    binding: str,
    stale_id: str,
    current_id: str | None,
    id_kind: str,
    now: str,
) -> None:
    drift = next_state.setdefault("drift", {"last_checked_at": None, "status": "unknown", "findings": [], "reconciled_by_name": [], "stale_ids": []})
    existing = [
        item
        for item in list(drift.get("stale_ids") or [])
        if not (isinstance(item, dict) and item.get("id") == stale_id and item.get("service_binding") == binding)
    ]
    existing.append(
        {
            "id": stale_id,
            "id_kind": id_kind,
            "service_binding": binding,
            "replaced_by": current_id,
            "reason": "id_absent_from_current_contextforge_readback" if current_id is None else "reconciled_to_current_contextforge_readback",
            "detected_at": now,
        }
    )
    drift["stale_ids"] = sorted(existing, key=lambda item: json.dumps(item, sort_keys=True, default=str))
    drift["last_checked_at"] = now
    drift["status"] = "drift_found"


def _trust_surface_for(target_client: str) -> str:
    if target_client == "pi":
        return "global Pi extension installation status"
    if target_client == "gemini":
        return "user-global Gemini helper MCP config and project-local settings"
    if target_client == "opencode":
        return "OpenCode user-home plugin plus project-local config loading"
    if target_client == "codex":
        return "user-global Codex project trust"
    return f"{target_client} client trust"


def _target_client_activation_record(
    service: dict[str, Any],
    *,
    target_client: str,
    client_config_plan: dict[str, Any],
    validation_status: str,
) -> dict[str, Any]:
    if target_client == "pi":
        prefix = _pi_tool_prefix(service)
        return {
            "status": "shim_activation_planned" if client_config_plan.get("write_allowed") else "blocked",
            "surface": client_config_plan.get("surface"),
            "service_identity_id": _service_identity_for(service)["id"],
            "contextforge_server_id": service.get("contextforge_server_id"),
            "alias": prefix,
            "pi_tool_prefix": prefix,
            "virtual_server": service.get("virtual_server"),
            "validation_status": validation_status,
            "shim": "contextforge-global-shim",
        }
    if target_client == "gemini":
        return {
            "status": "project_local_settings_planned" if client_config_plan.get("write_allowed") else "blocked",
            "surface": client_config_plan.get("surface"),
            "service_identity_id": _service_identity_for(service)["id"],
            "contextforge_server_id": service.get("contextforge_server_id"),
            "alias": service.get("codex_alias"),
            "virtual_server": service.get("virtual_server"),
            "validation_status": validation_status,
        }
    if target_client == "opencode":
        return {
            "status": "project_local_opencode_config_planned" if client_config_plan.get("write_allowed") else "blocked",
            "surface": client_config_plan.get("surface"),
            "service_identity_id": _service_identity_for(service)["id"],
            "contextforge_server_id": service.get("contextforge_server_id"),
            "alias": service.get("codex_alias"),
            "virtual_server": service.get("virtual_server"),
            "validation_status": validation_status,
            "global_trigger_surface": client_config_plan.get("global_trigger_surface"),
        }
    return {
        "status": "project_local_config_planned" if client_config_plan.get("write_allowed") else "blocked",
        "surface": client_config_plan.get("surface"),
        "service_identity_id": _service_identity_for(service)["id"],
        "contextforge_server_id": service.get("contextforge_server_id"),
        "alias": service.get("codex_alias"),
        "virtual_server": service.get("virtual_server"),
        "validation_status": validation_status,
    }


def _pi_tool_prefix(service: dict[str, Any]) -> str:
    value = str(service.get("pi_tool_prefix") or service.get("codex_alias") or service.get("service_family") or "service")
    prefix = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return prefix or "service"


def _activation_job_record(
    *,
    plan_id: str,
    selected_services: list[dict[str, Any]],
    target_client: str,
    client_config_plan: dict[str, Any],
    validation_plan: dict[str, Any],
    validation_results: dict[str, Any],
    consent_receipt_refs: list[str],
    activation_job: dict[str, Any] | None,
) -> dict[str, Any]:
    if activation_job:
        record = json.loads(json.dumps(activation_job))
    else:
        record = {}
    job_id = str(record.get("job_id") or f"job-{plan_id}")
    if record.get("client_type") not in {None, target_client}:
        raise StateValidationError("activation job client_type does not match target client")
    expected_bindings = [
        str(service.get("service_binding") or service.get("service_family") or "service") for service in selected_services
    ]
    expected_service_ids = [_service_identity_for(dict(service))["id"] for service in selected_services]
    record_bindings = record.get("selected_service_bindings")
    if record_bindings is not None and record_bindings != expected_bindings:
        raise StateValidationError("activation job selected_service_bindings do not match selected services")
    record_service_ids = record.get("selected_service_ids")
    if record_service_ids is not None and record_service_ids != expected_service_ids:
        raise StateValidationError("activation job selected_service_ids do not match selected services")
    if record.get("local_client_config_digest") not in {None, client_config_plan.get("after_digest")}:
        raise StateValidationError("activation job local_client_config_digest does not match config plan")
    validation_mode = str(validation_plan.get("validation_mode") or "pending_choice")
    validation_records = {
        _service_identity_for(dict(service))["id"]: _validation_record(
            service,
            target_client=target_client,
            validation_mode=validation_mode,
            validation_result=_validation_result_for(
                validation_results,
                str(service.get("service_binding") or service.get("service_family") or "service"),
                _service_identity_for(dict(service))["id"],
            ),
        )
        for service in selected_services
    }
    if validation_mode == "installed":
        status = "installed"
        recovery_state = "none"
    elif validation_mode == "pending_choice":
        status = "applied_validation_choice_pending"
        recovery_state = "local_written_validation_pending"
    elif validation_mode == "presume_working":
        status = "presumed_working"
        recovery_state = "validation_pending"
    elif all(item["status"] == "passed" for item in validation_records.values()):
        status = "verified"
        recovery_state = "none"
    else:
        status = "validation_pending"
        recovery_state = "validation_pending"
    result = {
        "job_id": job_id,
        "plan_id": str(record.get("plan_id") or plan_id),
        "plan_digest": _valid_job_plan_digest(record.get("plan_digest")) or _sha256_ref({"plan_id": plan_id, "services": selected_services}),
        "status": status,
        "client_type": target_client,
        "selected_service_ids": expected_service_ids,
        "selected_service_bindings": expected_bindings,
        "step_statuses": list(
            record.get("step_statuses")
            or [
                {
                    "operation_id": _client_activation_operation_id(target_client),
                    "operation_type": _client_activation_operation_type(target_client),
                    "status": "completed" if client_config_plan.get("write_allowed") else "blocked",
                    "idempotency_key": _sha256_ref({"plan_id": plan_id, "op": target_client})[:32],
                    "pre_digest": client_config_plan.get("before_digest"),
                    "post_digest": client_config_plan.get("after_digest"),
                    "recovery_state": None,
                },
                {
                    "operation_id": "write-project-state",
                    "operation_type": "write_project_state",
                    "status": "completed",
                    "idempotency_key": _sha256_ref({"plan_id": plan_id, "op": "project-state"})[:32],
                    "pre_digest": None,
                    "post_digest": None,
                    "recovery_state": None,
                },
            ]
        ),
        "stale_plan_inputs": dict(record.get("stale_plan_inputs") or {}),
        "consent_receipt_refs": list(record.get("consent_receipt_refs") or consent_receipt_refs),
        "local_client_config_digest": client_config_plan.get("after_digest"),
        "validation_records": validation_records,
        "recovery_state": recovery_state,
        "non_actions": list(
            record.get("non_actions")
            or [
                "no user-global config or trust mutation",
                "no ContextForge registry or catalog mutation",
                "no secret or token material write",
            ]
        ),
    }
    if isinstance(record.get("x_client_reload_ack"), dict):
        result["x_client_reload_ack"] = json.loads(json.dumps(record["x_client_reload_ack"]))
    if isinstance(record.get("x_client_reload_fsm"), dict):
        result["x_client_reload_fsm"] = json.loads(json.dumps(record["x_client_reload_fsm"]))
    elif target_client in CLIENTS_REQUIRING_PROJECT_RELOAD and status in {"applied_validation_choice_pending", "validation_pending"}:
        result["x_client_reload_fsm"] = {
            "state": "pending_reload",
            "client_type": target_client,
            "job_id": job_id,
            "plan_id": result["plan_id"],
            "command": _client_reload_command(target_client),
            "local_client_config_digest": client_config_plan.get("after_digest"),
        }
    return result


def _client_reload_command(target_client: str) -> str | None:
    if target_client == "codex":
        return "start_new_session"
    if target_client == "gemini":
        return "restart_session"
    if target_client == "opencode":
        return "start_new_session"
    if target_client == "pi":
        return "/reload"
    return None


def _client_activation_operation_id(target_client: str) -> str:
    if target_client == "pi":
        return "record-pi-shim-activation-metadata"
    if target_client == "gemini":
        return "write-gemini-project-settings"
    if target_client == "opencode":
        return "write-opencode-project-config"
    return "write-managed-client-config"


def _client_activation_operation_type(target_client: str) -> str:
    if target_client == "pi":
        return "record_pi_shim_activation_metadata"
    if target_client == "gemini":
        return "write_gemini_project_settings"
    if target_client == "opencode":
        return "write_opencode_project_config"
    return "write_managed_client_config"


def _validation_record(service: dict[str, Any], *, target_client: str, validation_mode: str, validation_result: dict[str, Any]) -> dict[str, Any]:
    service_identity_id = _service_identity_for(dict(service))["id"]
    service_binding = str(service.get("service_binding") or "")
    if validation_mode == "pending_choice":
        return {
            "mode": "pending_choice",
            "status": "pending_user_choice",
            "target_client_visible": False,
            "proof_ref": None,
            "skipped_reason": None,
            "safe_probe_id": None,
            "x_service_identity_id": service_identity_id,
            "x_service_binding": service_binding,
        }
    status = _service_validation_status(
        {"validation_mode": validation_mode, "target_client": target_client},
        str(service.get("service_binding") or ""),
        validation_result,
    )
    trace_refs = list(validation_result.get("verification_trace_refs") or [])
    record = {
        "mode": validation_mode,
        "status": status,
        "target_client_visible": bool(validation_result.get("target_client_visible") is True and status == "passed"),
        "proof_ref": trace_refs[0] if trace_refs else None,
        "skipped_reason": validation_result.get("skipped_reason") if status == "skipped" else None,
        "safe_probe_id": validation_result.get("safe_probe_id") or (service.get("validation_policy") or {}).get("mode"),
        "x_service_identity_id": service_identity_id,
        "x_service_binding": service_binding,
    }
    if validation_result.get("proof_kind"):
        record["x_proof_kind"] = validation_result.get("proof_kind")
    if validation_result.get("safe_probe_result"):
        record["x_safe_probe_result"] = validation_result.get("safe_probe_result")
    return record


def _provision_status_for(
    service: dict[str, Any],
    validation_status: str,
    *,
    existing_service: dict[str, Any] | None = None,
) -> str:
    explicit = service.get("provision_status")
    if explicit in PROVISION_STATUSES:
        return str(explicit)
    provisioning = service.get("provisioning") if isinstance(service.get("provisioning"), dict) else {}
    provisioning_status = provisioning.get("provision_status") or provisioning.get("status")
    if provisioning_status in PROVISION_STATUSES:
        return str(provisioning_status)
    existing = existing_service.get("provision_status") if isinstance(existing_service, dict) else None
    if existing in PROVISION_STATUSES and existing != "none":
        return str(existing)
    instantiation_class = str(service.get("instantiation_class") or "shared_canonical")
    if instantiation_class not in PROJECT_SCOPED_INSTANTIATION_CLASSES:
        return "none"
    return "verified" if validation_status == "passed" else str(existing or "none")


def _service_lifecycle_for(service: dict[str, Any], *, existing_service: dict[str, Any] | None = None) -> dict[str, Any]:
    existing = existing_service.get("lifecycle") if isinstance(existing_service, dict) and isinstance(existing_service.get("lifecycle"), dict) else {}
    existing_instantiation_class = existing_service.get("instantiation_class") if isinstance(existing_service, dict) else None
    instantiation_class = str(service.get("instantiation_class") or existing_instantiation_class or "shared_canonical")
    if instantiation_class in PROJECT_SCOPED_INSTANTIATION_CLASSES:
        activation = "project_scoped_service_provision"
    else:
        activation = "shared_contextforge_service"
    return {
        "activation": existing.get("activation") if existing.get("activation") in {"project_scoped_service_provision", "shared_contextforge_service"} else activation,
        "contextforge_readback_status": service.get("contextforge_readback_status") or existing.get("contextforge_readback_status"),
        "gateway": service.get("gateway") or existing.get("gateway"),
        "non_actions": _dedupe_strings([*(existing.get("non_actions") or []), *(service.get("non_actions") or [])]),
    }


def _target_client_validation_summary(target_clients: dict[str, Any]) -> str:
    statuses = [
        str(record.get("validation_status") or "pending")
        for record in target_clients.values()
        if isinstance(record, dict)
    ]
    normalized = _aggregate_client_validation_status(statuses)
    if normalized == "passed":
        return "passed"
    if any(status in {"passed", "verified"} for status in statuses):
        return "mixed"
    return normalized


def _valid_job_plan_digest(value: Any) -> str | None:
    if isinstance(value, str) and re.match(r"^sha256:[a-f0-9]{64}$", value):
        return value
    if value is None:
        return None
    raise StateValidationError("activation job plan_digest is invalid")


def _sha256_ref(value: Any) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


def _state_map_key(value: str) -> str:
    key = re.sub(r"[^A-Za-z0-9_.:-]+", "-", value).strip("-._:")
    if not key:
        return "service"
    if not re.match(r"^[A-Za-z0-9]", key):
        key = f"service-{key}"
    return key[:192]


def _service_key_for_binding(services: Mapping[str, Any], binding: str) -> str | None:
    for service_key, service in services.items():
        if isinstance(service, Mapping) and str(service.get("service_binding") or service_key) == binding:
            return str(service_key)
    return None


def _service_ref(prefix: str, binding: str) -> str:
    return f"contextforge://control-plane/{prefix}/{_state_map_key(binding)}"


def _validation_result_for(validation_results: dict[str, Any], binding: str, service_identity_id: str | None = None) -> dict[str, Any]:
    result = (
        (validation_results.get(service_identity_id) if service_identity_id else None)
        or validation_results.get(binding)
        or validation_results.get(_state_map_key(binding))
        or {}
    )
    return result if isinstance(result, dict) else {}


def _service_validation_status(validation_plan: dict[str, Any], binding: str, result: dict[str, Any]) -> str:
    if validation_plan.get("validation_mode") == "pending_choice":
        return "pending"
    if validation_plan.get("validation_mode") == "installed":
        return "installed"
    if validation_plan.get("validation_mode") == "presume_working":
        return "presumed_working"
    if validation_plan.get("target_client") == "pi" and result.get("status") in {"passed", "verified"}:
        return "passed" if _pi_safe_probe_result_passed(result) else "pending"
    if result.get("target_client_visible") is True and result.get("status") in {"passed", "verified"}:
        return "passed"
    if result.get("status") == "skipped":
        return "skipped"
    return "pending"


def _pi_safe_probe_result_passed(result: dict[str, Any]) -> bool:
    if result.get("target_client_visible") is not True:
        return False
    if result.get("proof_kind") != "pi_safe_probe_result":
        return False
    if result.get("safe_probe_result") != "passed":
        return False
    if not result.get("safe_probe_id"):
        return False
    return bool(result.get("verification_trace_refs"))


def _upsert_open_item(state: dict[str, Any], item: dict[str, Any]) -> None:
    items = state.setdefault("open_items", [])
    for index, existing in enumerate(items):
        if existing.get("id") == item["id"]:
            items[index] = item
            return
    items.append(item)


def _resolve_open_item(state: dict[str, Any], item_id: str) -> None:
    for item in state.setdefault("open_items", []):
        if item.get("id") == item_id:
            item["resolution_state"] = "resolved"
            item["blocks_initialized"] = False


def load_state(project_root: str | Path, *, require_workspace: bool = False) -> dict[str, Any] | None:
    root = validate_project_root(project_root, require_workspace=require_workspace)
    path = project_state_path(root)
    if not path.exists():
        return None
    state = read_json_file(path)
    validate_state_root(state, root)
    validate_state(state)
    return state


def read_or_default(
    project_root: str | Path,
    *,
    require_workspace: bool = False,
    allow_invalid_existing: bool = False,
) -> dict[str, Any]:
    root = validate_project_root(project_root, require_workspace=require_workspace)
    try:
        return load_state(root, require_workspace=require_workspace) or default_state(root)
    except StateValidationError:
        if allow_invalid_existing and project_state_path(root).exists():
            return default_state(root)
        raise


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
    allow_invalid_existing: bool = False,
) -> dict[str, Any]:
    root = validate_project_root(project_root)
    path = project_state_path(root)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    validate_state_root(state, root)

    with state_lock(root, stale_after_seconds=stale_after_seconds):
        if path.exists():
            try:
                current = load_state(root)
            except StateValidationError:
                if not allow_invalid_existing:
                    raise
                current = None
        else:
            current = None
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
