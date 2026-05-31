#!/usr/bin/env python3
"""ContextForge-backed language profile metadata for control-plane services."""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from pathlib import PurePosixPath
from typing import Any


SCHEMA_URI = "contextforge://control-plane/schemas/language-profile/v1"
RESOURCE_URI_PREFIX = "contextforge://control-plane/language-profiles"
HELPER_VERSION = 1
PROFILE_IDS = ("python", "typescript_javascript", "rust", "bash")
INSTALL_POLICIES = frozenset({"disabled", "approved-manual", "approved-instance-local", "host-required"})
INSTALL_SCOPES = frozenset({"instance_local", "project_local", "host_global"})


class LanguageProfileError(ValueError):
    """Raised when language profile inputs or records are invalid."""


def stable_digest(value: Any) -> str:
    """Return a stable sha256 digest for JSON-compatible language profile data."""

    encoded = json.dumps(_json_copy(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def language_profile_uri(profile_id: str) -> str:
    """Return the ContextForge resource URI for a v1 language profile."""

    _require_profile_id(profile_id)
    return f"{RESOURCE_URI_PREFIX}/{profile_id}/v1"


def build_language_profile_resources() -> list[dict[str, Any]]:
    """Build all v1 ContextForge resource-shaped language profile records."""

    return [build_language_profile_resource(profile_id) for profile_id in PROFILE_IDS]


def build_language_profile_resource(profile_id: str) -> dict[str, Any]:
    """Build one ContextForge resource-shaped language profile record."""

    profile = _profile_content(profile_id)
    resource = {
        "uri": language_profile_uri(profile_id),
        "name": f"Control Plane Language Profile: {profile['display_name']}",
        "description": f"v1 language profile policy and verification metadata for {profile['display_name']}.",
        "mime_type": "application/json",
        "tags": ["control-plane", "language-profile", "v1", profile_id],
        "content": profile,
    }
    validate_language_profile_resource(resource)
    return resource


def get_language_profile(profile_id: str) -> dict[str, Any]:
    """Return a copy of one normalized language profile content record."""

    return _profile_content(profile_id)


def validate_language_profile_resource(resource: Mapping[str, Any]) -> Mapping[str, Any]:
    """Validate the resource shape and embedded v1 language profile content."""

    if not isinstance(resource, Mapping):
        raise LanguageProfileError("language profile resource must be a mapping")
    content = resource.get("content")
    if not isinstance(content, Mapping):
        raise LanguageProfileError("language profile resource content must be a mapping")
    profile_id = validate_language_profile(content)["language_id"]
    expected_uri = language_profile_uri(profile_id)
    if resource.get("uri") != expected_uri:
        raise LanguageProfileError(f"language profile resource uri must be {expected_uri}")
    tags = resource.get("tags")
    if not isinstance(tags, list) or not {"control-plane", "language-profile", "v1", profile_id}.issubset(tags):
        raise LanguageProfileError("language profile resource tags must identify control-plane language profile v1")
    if resource.get("mime_type") != "application/json":
        raise LanguageProfileError("language profile resource mime_type must be application/json")
    return resource


def validate_language_profile(profile: Mapping[str, Any]) -> Mapping[str, Any]:
    """Validate one normalized language profile content record."""

    profile_id = str(profile.get("language_id") or "")
    _require_profile_id(profile_id)
    if profile.get("schema_uri") != SCHEMA_URI:
        raise LanguageProfileError(f"{profile_id}: schema_uri must be {SCHEMA_URI}")
    if profile.get("schema_version") != HELPER_VERSION:
        raise LanguageProfileError(f"{profile_id}: schema_version must be {HELPER_VERSION}")
    if not profile.get("display_name"):
        raise LanguageProfileError(f"{profile_id}: display_name is required")
    _require_non_empty_list(profile, "tags", profile_id)
    detection = _require_mapping(profile, "detection", profile_id)
    _require_non_empty_list(detection, "markers", profile_id)
    _require_non_empty_list(detection, "extensions", profile_id)
    _require_non_empty_list(profile, "service_requirements", profile_id)
    _require_non_empty_list(profile, "baseline_probes", profile_id)
    _require_non_empty_list(profile, "backend_options", profile_id)
    _validate_install_policy(profile_id, _require_mapping(profile, "install_policy", profile_id))
    _validate_evidence_expectations(profile_id, _require_mapping(profile, "verification_evidence_expectations", profile_id))
    _validate_probe_artifact_policy(profile_id, _require_mapping(profile, "probe_artifact_policy", profile_id))
    return profile


def detect_language_profiles(
    project_paths: Iterable[str],
    *,
    selected_profile_id: str | None = None,
) -> dict[str, Any]:
    """Detect matching profiles from project-relative paths without accepting services."""

    paths = sorted(_normalize_project_path(path) for path in project_paths if str(path).strip())
    matches = []
    for profile_id in PROFILE_IDS:
        profile = get_language_profile(profile_id)
        detection = profile["detection"]
        marker_hits = _marker_hits(paths, detection["markers"])
        extension_hits = _extension_hits(paths, detection["extensions"])
        if marker_hits or extension_hits:
            score = len(marker_hits) * 20 + min(len(extension_hits), 20)
            matches.append(
                {
                    "language_id": profile_id,
                    "display_name": profile["display_name"],
                    "confidence": min(100, score),
                    "marker_hits": marker_hits,
                    "extension_hits": extension_hits,
                    "resource_uri": language_profile_uri(profile_id),
                }
            )
    matches.sort(key=lambda item: (-int(item["confidence"]), str(item["language_id"])))
    selected = None
    open_items = []
    if selected_profile_id is not None:
        _require_profile_id(selected_profile_id)
        selected = {
            "language_id": selected_profile_id,
            "resource_uri": language_profile_uri(selected_profile_id),
            "selection_source": "explicit_user_or_approved_plan",
            "detected": any(item["language_id"] == selected_profile_id for item in matches),
        }
    elif len(matches) == 1:
        selected = {
            "language_id": matches[0]["language_id"],
            "resource_uri": matches[0]["resource_uri"],
            "selection_source": "single_profile_detection",
            "detected": True,
        }
    else:
        reason = "empty_project_requires_explicit_language_selection" if not matches else "multiple_profiles_require_primary_selection"
        open_items.append(
            _open_item(
                reason,
                "blocking",
                "Select a primary language profile before provisioning language-dependent services.",
                {"candidate_profile_ids": [item["language_id"] for item in matches]},
            )
        )

    return {
        "schema_uri": "contextforge://control-plane/schemas/language-profile-detection/v1",
        "helper_version": HELPER_VERSION,
        "matched_profiles": matches,
        "selected_primary_profile": selected,
        "service_acceptance_decisions": [],
        "open_items": open_items,
        "non_actions": [
            "does not accept or provision services",
            "does not install language tooling",
            "does not default empty projects to python",
        ],
    }


def build_profile_selection_plan(
    *,
    current_selected_profile_id: str | None,
    requested_profile_id: str,
    detection_report: Mapping[str, Any],
    approval_ref: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Plan a primary profile selection or change; changes require approval."""

    _require_profile_id(requested_profile_id)
    if current_selected_profile_id is not None:
        _require_profile_id(current_selected_profile_id)
    changing = current_selected_profile_id is not None and current_selected_profile_id != requested_profile_id
    approved = bool(approval_ref)
    decision = "select" if not changing or approved else "block"
    open_items = []
    if changing and not approved:
        open_items.append(
            _open_item(
                "language_profile_change_requires_approval",
                "blocking",
                "Changing the selected primary language profile requires a new approved plan.",
                {"from": current_selected_profile_id, "to": requested_profile_id},
            )
        )
    return {
        "schema_uri": "contextforge://control-plane/schemas/language-profile-selection-plan/v1",
        "helper_version": HELPER_VERSION,
        "decision": decision,
        "current_selected_profile_id": current_selected_profile_id,
        "requested_profile_id": requested_profile_id,
        "requested_profile_ref": {"ref": language_profile_uri(requested_profile_id)},
        "detected_profile_ids": [item["language_id"] for item in detection_report.get("matched_profiles", [])],
        "approval_required": changing,
        "approval_ref": _json_copy(approval_ref) if approval_ref else None,
        "open_items": open_items,
        "service_acceptance_decisions": [],
        "non_actions": ["does not mutate project state", "does not accept services"],
    }


def build_install_workflow_plan(
    *,
    profile_id: str,
    missing_tool_ids: Sequence[str],
    backend_option_id: str | None = None,
    requested_scope: str = "instance_local",
    execution_approved: bool = False,
    global_mutation_approved: bool = False,
) -> dict[str, Any]:
    """Build explicit plan-first install workflow metadata without executing installs."""

    profile = get_language_profile(profile_id)
    if requested_scope not in INSTALL_SCOPES:
        raise LanguageProfileError(f"unknown install scope: {requested_scope}")
    backend_options = {option["option_id"]: option for option in profile["backend_options"]}
    selected_option_id = backend_option_id or profile["install_policy"]["default_backend_option_id"]
    if selected_option_id not in backend_options:
        raise LanguageProfileError(f"{profile_id}: unknown backend option: {selected_option_id}")
    missing = sorted({str(item) for item in missing_tool_ids if str(item).strip()})
    blockers = []
    open_items = []
    if missing:
        open_items.append(
            _open_item(
                "missing_language_tooling",
                "blocking",
                "Missing language tooling requires an explicit approved install plan or manual remediation.",
                {"language_id": profile_id, "missing_tool_ids": missing},
            )
        )
    if not execution_approved and missing:
        blockers.append("execution_requires_separate_approval")
    if requested_scope == "host_global" and not global_mutation_approved:
        blockers.append("global_language_tooling_mutation_blocked")
        open_items.append(
            _open_item(
                "global_language_tooling_mutation_requires_approval",
                "blocking",
                "Host-global language tooling mutation is non-default and requires separate approval.",
                {"requested_scope": requested_scope},
            )
        )
    choices = [
        {
            "choice_id": f"use-{option['option_id']}",
            "backend_option_id": option["option_id"],
            "display_name": option["display_name"],
            "scope": option["scope"],
            "curated_source_allowlist": option["curated_source_allowlist"],
            "plan_first": True,
            "execute_without_approval": False,
        }
        for option in profile["backend_options"]
    ]
    return {
        "schema_uri": "contextforge://control-plane/schemas/language-tool-install-workflow-plan/v1",
        "helper_version": HELPER_VERSION,
        "language_id": profile_id,
        "language_profile_ref": {"ref": language_profile_uri(profile_id), "content_digest": stable_digest(profile)},
        "selected_backend_option_id": selected_option_id,
        "requested_scope": requested_scope,
        "execution_approved": execution_approved,
        "global_mutation_approved": global_mutation_approved,
        "decision": "block" if blockers else "plan_only",
        "blockers": blockers,
        "missing_tool_ids": missing,
        "choices": choices,
        "open_items": open_items,
        "install_policy": _json_copy(profile["install_policy"]),
        "probe_artifact_policy": _json_copy(profile["probe_artifact_policy"]),
        "verification_evidence_expectations": _json_copy(profile["verification_evidence_expectations"]),
        "non_actions": [
            "does not run install commands",
            "does not mutate global language tooling",
            "does not write service instance files",
        ],
    }


def _profile_content(profile_id: str) -> dict[str, Any]:
    _require_profile_id(profile_id)
    data = _profile_definitions()[profile_id]
    profile = {
        "schema_uri": SCHEMA_URI,
        "schema_version": HELPER_VERSION,
        "kind": "language_profile",
        "language_id": profile_id,
        "display_name": data["display_name"],
        "tags": ["control-plane", "language-profile", "v1", profile_id],
        "detection": data["detection"],
        "service_requirements": data["service_requirements"],
        "baseline_probes": data["baseline_probes"],
        "optional_capabilities": data["optional_capabilities"],
        "backend_options": data["backend_options"],
        "install_policy": data["install_policy"],
        "verification_evidence_expectations": data["verification_evidence_expectations"],
        "probe_artifact_policy": data["probe_artifact_policy"],
    }
    validate_language_profile(profile)
    return _json_copy(profile)


def _profile_definitions() -> dict[str, dict[str, Any]]:
    common_requirements = [
        {
            "requirement_id": "project_language_profile_selected",
            "description": "Language-dependent services must consume the selected profile separately from service acceptance.",
            "blocking": True,
        }
    ]
    common_evidence = {
        "required_fields": ["profile_ref", "selected_primary_profile", "baseline_probe_results", "probe_artifact_policy"],
        "trace_layers": ["language_profile", "project_root", "backend_tooling", "redaction"],
        "records_service_acceptance": False,
    }
    return {
        "python": {
            "display_name": "Python",
            "detection": {
                "markers": ["pyproject.toml", "requirements.txt", "setup.py", "setup.cfg", "poetry.lock", "uv.lock", "Pipfile"],
                "extensions": [".py", ".pyi"],
            },
            "service_requirements": common_requirements
            + [{"requirement_id": "python_baseline_probe_available", "blocking": True}],
            "baseline_probes": [
                {"probe_id": "python-version", "tool": "python", "args": ["--version"], "blocking": True},
                {"probe_id": "python-parse-probe", "tool": "python", "args": ["-m", "py_compile", "<probe_artifact>"], "blocking": True},
            ],
            "optional_capabilities": ["symbols", "references", "implementations", "type_checking"],
            "backend_options": [
                {
                    "option_id": "python-venv-pyright",
                    "display_name": "Instance-local Python venv with pyright",
                    "scope": "instance_local",
                    "curated_source_allowlist": ["pypi.org/project/pyright", "github.com/microsoft/pyright"],
                    "install_commands": ["uv venv", "uv pip install pyright"],
                }
            ],
            "install_policy": _install_policy("python-venv-pyright"),
            "verification_evidence_expectations": common_evidence,
            "probe_artifact_policy": _probe_artifact_policy("python", "probe.py", True),
        },
        "typescript_javascript": {
            "display_name": "TypeScript/JavaScript",
            "detection": {
                "markers": ["package.json", "tsconfig.json", "jsconfig.json", "pnpm-lock.yaml", "package-lock.json", "yarn.lock", "bun.lockb"],
                "extensions": [".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"],
            },
            "service_requirements": common_requirements
            + [{"requirement_id": "typescript_javascript_baseline_probe_available", "blocking": True}],
            "baseline_probes": [
                {"probe_id": "node-version", "tool": "node", "args": ["--version"], "blocking": True},
                {"probe_id": "typescript-syntax-probe", "tool": "node", "args": ["<probe_artifact>"], "blocking": True},
            ],
            "optional_capabilities": ["symbols", "references", "implementations", "typescript_diagnostics"],
            "backend_options": [
                {
                    "option_id": "node-typescript-language-server",
                    "display_name": "Instance-local Node tooling with TypeScript language server",
                    "scope": "instance_local",
                    "curated_source_allowlist": ["npmjs.com/package/typescript", "npmjs.com/package/typescript-language-server"],
                    "install_commands": ["npm install --prefix <instance_home> typescript typescript-language-server"],
                }
            ],
            "install_policy": _install_policy("node-typescript-language-server"),
            "verification_evidence_expectations": common_evidence,
            "probe_artifact_policy": _probe_artifact_policy("typescript_javascript", "probe.js", True),
        },
        "rust": {
            "display_name": "Rust",
            "detection": {
                "markers": ["Cargo.toml", "Cargo.lock", "rust-toolchain", "rust-toolchain.toml"],
                "extensions": [".rs"],
            },
            "service_requirements": common_requirements
            + [{"requirement_id": "rust_baseline_probe_available", "blocking": True}],
            "baseline_probes": [
                {"probe_id": "rustc-version", "tool": "rustc", "args": ["--version"], "blocking": True},
                {"probe_id": "rust-analyzer-version", "tool": "rust-analyzer", "args": ["--version"], "blocking": True},
            ],
            "optional_capabilities": ["symbols", "references", "implementations", "cargo_metadata"],
            "backend_options": [
                {
                    "option_id": "rustup-rust-analyzer-instance",
                    "display_name": "Approved Rust toolchain with rust-analyzer metadata",
                    "scope": "instance_local",
                    "curated_source_allowlist": ["rust-lang.org/tools/install", "github.com/rust-lang/rust-analyzer"],
                    "install_commands": ["rustup component add rust-analyzer --toolchain <approved-toolchain>"],
                }
            ],
            "install_policy": _install_policy("rustup-rust-analyzer-instance"),
            "verification_evidence_expectations": common_evidence,
            "probe_artifact_policy": _probe_artifact_policy("rust", "probe.rs", True),
        },
        "bash": {
            "display_name": "Bash",
            "detection": {
                "markers": [".bashrc", ".bash_profile", "shellcheckrc", ".shellcheckrc"],
                "extensions": [".sh", ".bash"],
            },
            "service_requirements": common_requirements
            + [{"requirement_id": "bash_advisory_probe_recorded", "blocking": False}],
            "baseline_probes": [
                {"probe_id": "bash-version", "tool": "bash", "args": ["--version"], "blocking": False},
                {"probe_id": "shellcheck-version", "tool": "shellcheck", "args": ["--version"], "blocking": False},
            ],
            "optional_capabilities": ["shellcheck_diagnostics", "formatting"],
            "backend_options": [
                {
                    "option_id": "instance-local-shellcheck",
                    "display_name": "Instance-local shellcheck/shfmt metadata",
                    "scope": "instance_local",
                    "curated_source_allowlist": ["shellcheck.net", "github.com/mvdan/sh"],
                    "install_commands": ["install shellcheck/shfmt into <instance_home> by approved workflow"],
                }
            ],
            "install_policy": _install_policy("instance-local-shellcheck"),
            "verification_evidence_expectations": common_evidence,
            "probe_artifact_policy": _probe_artifact_policy("bash", "probe.sh", False),
        },
    }


def _install_policy(default_backend_option_id: str) -> dict[str, Any]:
    return {
        "policy": "approved-instance-local",
        "default_backend_option_id": default_backend_option_id,
        "plan_first": True,
        "execute_silently": False,
        "instance_local_by_default": True,
        "global_mutation_default": False,
        "global_mutation_requires_separate_approval": True,
        "missing_tooling_behavior": "emit_plan_open_items_and_choices",
        "audit_provenance_required": True,
    }


def _probe_artifact_policy(profile_id: str, filename: str, failure_blocks_verification: bool) -> dict[str, Any]:
    return {
        "policy_id": f"{profile_id}-empty-project-probe-artifact",
        "applies_to": "empty_project_or_no_source_files",
        "path": f"generated/language-probes/{profile_id}/{filename}",
        "cleanup": "delete_after_probe_unless_preserved_for_debug_with_approval",
        "gitignore_status": "generated/ ignored by default",
        "consent_class": "project_state_write",
        "requires_prior_consent": True,
        "failure_blocks_verification": failure_blocks_verification,
    }


def _validate_install_policy(profile_id: str, policy: Mapping[str, Any]) -> None:
    if policy.get("policy") not in INSTALL_POLICIES:
        raise LanguageProfileError(f"{profile_id}: unknown install policy")
    required_true = ("plan_first", "instance_local_by_default", "global_mutation_requires_separate_approval", "audit_provenance_required")
    for key in required_true:
        if policy.get(key) is not True:
            raise LanguageProfileError(f"{profile_id}: install_policy.{key} must be true")
    if policy.get("execute_silently") is not False or policy.get("global_mutation_default") is not False:
        raise LanguageProfileError(f"{profile_id}: install policy must not allow silent execution or default global mutation")
    if policy.get("missing_tooling_behavior") != "emit_plan_open_items_and_choices":
        raise LanguageProfileError(f"{profile_id}: missing tooling must produce plan/open-item metadata")


def _validate_evidence_expectations(profile_id: str, evidence: Mapping[str, Any]) -> None:
    required = set(evidence.get("required_fields") or [])
    expected = {"profile_ref", "selected_primary_profile", "baseline_probe_results", "probe_artifact_policy"}
    if not expected.issubset(required):
        raise LanguageProfileError(f"{profile_id}: verification evidence expectations are incomplete")
    if evidence.get("records_service_acceptance") is not False:
        raise LanguageProfileError(f"{profile_id}: language evidence must not record service acceptance")


def _validate_probe_artifact_policy(profile_id: str, policy: Mapping[str, Any]) -> None:
    for key in ("path", "cleanup", "gitignore_status", "consent_class", "failure_blocks_verification"):
        if key not in policy:
            raise LanguageProfileError(f"{profile_id}: probe artifact policy missing {key}")
    if policy.get("consent_class") != "project_state_write":
        raise LanguageProfileError(f"{profile_id}: probe artifact policy must name project_state_write consent")


def _require_profile_id(profile_id: str) -> None:
    if profile_id not in PROFILE_IDS:
        raise LanguageProfileError(f"unknown language profile id: {profile_id}")


def _require_mapping(data: Mapping[str, Any], key: str, profile_id: str) -> Mapping[str, Any]:
    value = data.get(key)
    if not isinstance(value, Mapping):
        raise LanguageProfileError(f"{profile_id}: {key} must be a mapping")
    return value


def _require_non_empty_list(data: Mapping[str, Any], key: str, profile_id: str) -> list[Any]:
    value = data.get(key)
    if not isinstance(value, list) or not value:
        raise LanguageProfileError(f"{profile_id}: {key} must be a non-empty list")
    return value


def _normalize_project_path(path: str) -> str:
    normalized = str(PurePosixPath(str(path).replace("\\", "/"))).lstrip("/")
    return "" if normalized == "." else normalized


def _marker_hits(paths: Sequence[str], markers: Sequence[str]) -> list[str]:
    marker_set = set(markers)
    hits = []
    for path in paths:
        name = PurePosixPath(path).name
        if path in marker_set or name in marker_set:
            hits.append(path)
    return sorted(set(hits))


def _extension_hits(paths: Sequence[str], extensions: Sequence[str]) -> list[str]:
    extension_set = set(extensions)
    hits = [path for path in paths if PurePosixPath(path).suffix in extension_set]
    return sorted(set(hits))


def _open_item(item_type: str, severity: str, message: str, detail: Mapping[str, Any]) -> dict[str, Any]:
    return {"type": item_type, "severity": severity, "message": message, "detail": _json_copy(detail)}


def _json_copy(value: Any) -> Any:
    return copy.deepcopy(value)
