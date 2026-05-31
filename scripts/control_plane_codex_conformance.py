#!/usr/bin/env python3
"""Deterministic Codex client-adapter conformance helpers.

This module is intentionally pure.  It evaluates supplied evidence snapshots
for the Codex target-client path and never reads or mutates user-global trust,
project-local Codex config, or project state.
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import control_plane_contracts as contracts
import control_plane_project_state as project_state


PACK_ID = "codex/v1"
PACK_SCHEMA_URI = "contextforge://control-plane/schemas/client-adapter-conformance-pack/v1"
DEFAULT_GENERATED_AT = "2026-05-30T00:00:00Z"
ALLOWED_OWNED_BLOCK_CLASSES = frozenset({"owned", "legacy_owned", "absent"})
BLOCKED_OWNED_BLOCK_CLASSES = frozenset({"user_modified_owned", "unmanaged_same_name", "unsupported_schema"})
PASSING_AUTH_STRENGTHS = frozenset({"shared_token", "wrapper_bound", "per_client_token"})
REQUIRED_CHECKS = (
    "project_local_config_loaded",
    "project_root_matches",
    "owned_block_supported",
    "trust_state_allows_loading",
    "restart_satisfied",
    "config_not_stale",
    "auth_strength_sufficient",
    "auth_material_source_matches",
    "list_tools_proof",
    "call_tool_proof",
    "target_client_visibility",
)


class CodexConformanceError(ValueError):
    """Raised when a conformance fixture or evidence snapshot is malformed."""


def build_codex_conformance_pack(*, generated_at: str = DEFAULT_GENERATED_AT) -> dict[str, Any]:
    """Build the versioned Codex conformance-pack artifact."""

    pack = {
        "pack_id": PACK_ID,
        "schema_uri": PACK_SCHEMA_URI,
        "client_name": "codex",
        "version_constraints": ["codex-desktop>=2026.05", "codex-terminal>=2026.05"],
        "config_surface_fixtures": [
            {
                "surface": ".codex/config.toml",
                "scope": "project_local",
                "required": True,
                "loads_only_after_global_project_trust": True,
            }
        ],
        "owned_block_classes": [
            "owned",
            "legacy_owned",
            "user_modified_owned",
            "unmanaged_same_name",
            "unsupported_schema",
            "absent",
        ],
        "direct_http_header_support": True,
        "stdio_wrapper_behavior": {
            "required": False,
            "package_bridge_allowed_only_for_missing_transport": True,
        },
        "trust_requirements": {
            "global_trust_required": True,
            "mutation_allowed_by_pack": False,
            "report_only_states": ["required", "missing", "approved", "verified", "declined"],
        },
        "trust_broker_interface": {
            "inspect": "read trust state for exact project root",
            "approval_mutation": "out_of_scope_for_w6_a",
            "verification": "Codex-visible project-local config consumption",
        },
        "restart_model": {
            "restart_blocks_initialized": True,
            "required_when_config_or_trust_generation_changes": True,
        },
        "stale_config_probes": [
            {
                "probe": "loaded_config_generation_matches_expected",
                "failure_classification": "client_restart_or_stale_config",
            }
        ],
        "list_tools_probes": [
            {
                "probe": "codex_target_client_list_tools",
                "must_be_client_visible": True,
            }
        ],
        "call_tool_probes": [
            {
                "probe": "codex_target_client_call_tool",
                "must_be_client_visible": True,
            }
        ],
        "token_source_constraints": [
            "source-client auth strength must be at least shared_token",
            "auth material source must match the approved project-local binding source",
            "raw secret values must not appear in argv, fixtures, traces, or logs",
        ],
        "negative_tool_policy_visibility_checks": [
            {
                "probe": "codex_target_client_denied_tool_absent",
                "status_required_for_service_proof": "passed",
                "compiler_owned_by": "W6-C",
            },
            {
                "probe": "wrong_project_root_not_visible",
                "status_required_for_service_proof": "passed",
            },
        ],
        "known_unsupported_behaviors": [
            {
                "behavior": "automatic_user_global_trust_mutation",
                "blocking_for_v1": False,
                "status": "declined_in_w6_a",
            },
            {
                "behavior": "serena_service_provisioning_assumption",
                "blocking_for_v1": False,
                "status": "declined_in_w6_a",
            },
        ],
        "redaction_status": "passed",
        "x_generated_at": generated_at,
        "x_required_checks": list(REQUIRED_CHECKS),
        "x_passing_statuses": ["passing_conformance"],
        "x_blocking_statuses": ["blocked_limitation", "failed_conformance"],
    }
    contracts.validate_artifact("client_adapter_conformance_pack", pack)
    return pack


def evaluate_codex_conformance(
    evidence: Mapping[str, Any],
    *,
    expected_project_root: str | Path,
    expected_service_binding: str,
    expected_auth_material_source: str,
    generated_at: str = DEFAULT_GENERATED_AT,
) -> dict[str, Any]:
    """Evaluate Codex adapter evidence and return a deterministic verdict."""

    root = str(project_state.validate_project_root(expected_project_root, require_workspace=False))
    snapshot = _json_copy(evidence)
    pack = build_codex_conformance_pack(generated_at=generated_at)
    checks = [
        _project_local_config_loaded(snapshot, root),
        _project_root_matches(snapshot, root),
        _owned_block_supported(snapshot),
        _trust_state_allows_loading(snapshot, root),
        _restart_satisfied(snapshot),
        _config_not_stale(snapshot),
        _auth_strength_sufficient(snapshot),
        _auth_material_source_matches(snapshot, expected_auth_material_source),
        _list_tools_proof(snapshot, expected_service_binding, root),
        _call_tool_proof(snapshot, expected_service_binding, root),
        _target_client_visibility(snapshot, expected_service_binding, root),
    ]
    status = _overall_status(checks)
    blockers = [check for check in checks if check["status"] in {"failed", "blocked"}]
    result = {
        "pack_id": pack["pack_id"],
        "client_name": "codex",
        "status": status,
        "decision": "allow_target_client_proof" if status == "passing_conformance" else "block_target_client_proof",
        "project_root": root,
        "project_root_hash": project_state.project_root_hash(root),
        "service_binding": expected_service_binding,
        "checks": checks,
        "blockers": blockers,
        "backend_health_observed": bool(_get(snapshot, "backend.health_passed")),
        "trust_report": _trust_report(snapshot, root),
        "conformance_pack": pack,
        "evidence_digest": _stable_digest(_redacted_evidence_fingerprint(snapshot)),
        "generated_at": generated_at,
        "redaction_status": "passed",
    }
    _assert_no_secret_shaped_literals(result)
    return result


def validate_codex_target_client_proof(
    evidence: Mapping[str, Any],
    *,
    expected_project_root: str | Path,
    expected_service_binding: str,
    expected_auth_material_source: str,
    generated_at: str = DEFAULT_GENERATED_AT,
) -> dict[str, Any]:
    """Fail closed unless Codex-visible list-tools and call-tool proof passes."""

    result = evaluate_codex_conformance(
        evidence,
        expected_project_root=expected_project_root,
        expected_service_binding=expected_service_binding,
        expected_auth_material_source=expected_auth_material_source,
        generated_at=generated_at,
    )
    if result["status"] != "passing_conformance":
        return result
    required_names = {check["name"] for check in result["checks"] if check["status"] == "passed"}
    if "list_tools_proof" not in required_names or "call_tool_proof" not in required_names:
        result = _with_synthetic_blocker(result, "target_client_proof_missing", "missing Codex list-tools or call-tool proof")
    return result


def run_fixture_case(case: Mapping[str, Any], *, generated_at: str | None = None) -> dict[str, Any]:
    """Evaluate one JSON fixture case."""

    for key in ("name", "expected_project_root", "expected_service_binding", "expected_auth_material_source", "evidence"):
        if key not in case:
            raise CodexConformanceError(f"fixture case missing {key}")
    return validate_codex_target_client_proof(
        case["evidence"],
        expected_project_root=str(case["expected_project_root"]),
        expected_service_binding=str(case["expected_service_binding"]),
        expected_auth_material_source=str(case["expected_auth_material_source"]),
        generated_at=generated_at or str(case.get("generated_at") or DEFAULT_GENERATED_AT),
    )


def _project_local_config_loaded(evidence: Mapping[str, Any], root: str) -> dict[str, Any]:
    config = _mapping(evidence.get("config"))
    if config.get("scope") != "project_local":
        return _check("project_local_config_loaded", "failed", "config surface is not project-local")
    if config.get("surface") != ".codex/config.toml":
        return _check("project_local_config_loaded", "failed", "unexpected Codex config surface")
    if config.get("loaded_by_client") is not True:
        return _check("project_local_config_loaded", "blocked", "Codex has not loaded project-local config")
    if str(config.get("project_root") or "") != root:
        return _check("project_local_config_loaded", "failed", "loaded config root does not match project root")
    return _check("project_local_config_loaded", "passed", "project-local Codex config is loaded")


def _project_root_matches(evidence: Mapping[str, Any], root: str) -> dict[str, Any]:
    observed_roots = {
        source: str(value)
        for source, value in {
            "client.project_root": _get(evidence, "client.project_root"),
            "config.project_root": _get(evidence, "config.project_root"),
            "list_tools.project_root": _get(evidence, "list_tools.project_root"),
            "call_tool.project_root": _get(evidence, "call_tool.project_root"),
        }.items()
        if value not in {None, ""}
    }
    if not observed_roots:
        return _check("project_root_matches", "failed", "missing client-visible project root")
    mismatched = sorted(source for source, value in observed_roots.items() if value != root)
    if mismatched:
        return _check("project_root_matches", "failed", f"client-visible root does not match expected root: {', '.join(mismatched)}")
    return _check("project_root_matches", "passed", "client-visible root matches expected root")


def _owned_block_supported(evidence: Mapping[str, Any]) -> dict[str, Any]:
    block_class = str(_get(evidence, "config.owned_block_class") or "")
    if not block_class:
        return _check("owned_block_supported", "failed", "missing owned-block classification")
    if block_class in BLOCKED_OWNED_BLOCK_CLASSES:
        return _check("owned_block_supported", "blocked", f"owned-block class requires user action: {block_class}")
    if block_class not in ALLOWED_OWNED_BLOCK_CLASSES:
        return _check("owned_block_supported", "failed", f"unknown owned-block class: {block_class}")
    return _check("owned_block_supported", "passed", f"owned-block class is supported: {block_class}")


def _trust_state_allows_loading(evidence: Mapping[str, Any], root: str) -> dict[str, Any]:
    trust = _mapping(evidence.get("trust"))
    state = str(trust.get("state") or "")
    if trust.get("global_trust_required") is not True:
        return _check("trust_state_allows_loading", "failed", "Codex global project trust requirement is missing")
    if str(trust.get("project_root") or "") != root:
        return _check("trust_state_allows_loading", "failed", "trust evidence root does not match project root")
    if trust.get("mutated_by_conformance") is True:
        return _check("trust_state_allows_loading", "failed", "conformance pack must not mutate Codex trust")
    if state in {"verified", "trusted"}:
        return _check("trust_state_allows_loading", "passed", "Codex trust verified for project root")
    if state in {"approved", "trusted_requires_restart"}:
        return _check("trust_state_allows_loading", "blocked", "Codex trust is approved but not verified as loaded")
    if state in {"required", "missing", "unknown", "untrusted", "reported", "approval_requested"}:
        return _check("trust_state_allows_loading", "blocked", "Codex trust gap remains")
    if state == "declined":
        return _check("trust_state_allows_loading", "blocked", "Codex trust was declined")
    return _check("trust_state_allows_loading", "failed", "missing or unknown Codex trust state")


def _restart_satisfied(evidence: Mapping[str, Any]) -> dict[str, Any]:
    restart = _mapping(evidence.get("restart"))
    if restart.get("required") is not True:
        return _check("restart_satisfied", "passed", "restart not required")
    if restart.get("completed_after_change") is True:
        return _check("restart_satisfied", "passed", "restart completed after config/trust change")
    return _check("restart_satisfied", "blocked", "Codex restart is required before target-client proof")


def _config_not_stale(evidence: Mapping[str, Any]) -> dict[str, Any]:
    expected = _get(evidence, "config.expected_generation")
    loaded = _get(evidence, "config.loaded_generation")
    if expected is None or loaded is None:
        return _check("config_not_stale", "failed", "missing config generation evidence")
    if str(expected) != str(loaded):
        return _check("config_not_stale", "blocked", "Codex loaded stale config generation")
    if _get(evidence, "client.loaded_generation") not in {None, loaded, str(loaded)}:
        return _check("config_not_stale", "blocked", "client generation does not match loaded config")
    return _check("config_not_stale", "passed", "loaded config generation matches expected generation")


def _auth_strength_sufficient(evidence: Mapping[str, Any]) -> dict[str, Any]:
    strength = str(_get(evidence, "auth.strength") or "")
    if strength in PASSING_AUTH_STRENGTHS:
        return _check("auth_strength_sufficient", "passed", f"source-client auth strength is {strength}")
    if strength in {"none", "asserted"}:
        return _check("auth_strength_sufficient", "failed", f"source-client auth strength is insufficient: {strength}")
    return _check("auth_strength_sufficient", "failed", "missing or unknown source-client auth strength")


def _auth_material_source_matches(evidence: Mapping[str, Any], expected_source: str) -> dict[str, Any]:
    observed = _get(evidence, "auth.material_source")
    if not observed:
        return _check("auth_material_source_matches", "failed", "missing auth material source evidence")
    if str(observed) != expected_source:
        return _check("auth_material_source_matches", "failed", "auth material source does not match approved source")
    return _check("auth_material_source_matches", "passed", "auth material source matches approved source")


def _list_tools_proof(evidence: Mapping[str, Any], service_binding: str, root: str) -> dict[str, Any]:
    proof = _mapping(evidence.get("list_tools"))
    if proof.get("client") != "codex" or proof.get("status") != "passed":
        return _check("list_tools_proof", "failed", "missing passing Codex list-tools proof")
    if str(proof.get("project_root") or "") != root:
        return _check("list_tools_proof", "failed", "Codex list-tools proof used the wrong project root")
    if service_binding not in _string_list(proof.get("visible_service_bindings")):
        return _check("list_tools_proof", "failed", "service binding is not visible in Codex list-tools output")
    tools = _string_list(proof.get("tools"))
    if not tools:
        return _check("list_tools_proof", "failed", "Codex list-tools proof has no visible tools")
    return _check("list_tools_proof", "passed", "Codex list-tools proof exposes expected binding")


def _call_tool_proof(evidence: Mapping[str, Any], service_binding: str, root: str) -> dict[str, Any]:
    proof = _mapping(evidence.get("call_tool"))
    if proof.get("client") != "codex" or proof.get("status") != "passed":
        return _check("call_tool_proof", "failed", "missing passing Codex call-tool proof")
    if str(proof.get("project_root") or "") != root:
        return _check("call_tool_proof", "failed", "Codex call-tool proof used the wrong project root")
    if proof.get("service_binding") != service_binding:
        return _check("call_tool_proof", "failed", "Codex call-tool proof used the wrong service binding")
    if proof.get("backend_health_only") is True:
        return _check("call_tool_proof", "failed", "backend health alone cannot satisfy Codex call-tool proof")
    result_digest = str(proof.get("result_digest") or "")
    if not result_digest.startswith("sha256:"):
        return _check("call_tool_proof", "failed", "Codex call-tool proof lacks redacted result digest")
    return _check("call_tool_proof", "passed", "Codex call-tool proof passed for expected binding")


def _target_client_visibility(evidence: Mapping[str, Any], service_binding: str, root: str) -> dict[str, Any]:
    visibility = _mapping(evidence.get("negative_visibility"))
    if visibility.get("status") != "passed":
        return _check("target_client_visibility", "failed", "missing passing negative target-client visibility checks")
    if visibility.get("wrong_root_visible") is True:
        return _check("target_client_visibility", "failed", "wrong project root is visible to Codex")
    if visibility.get("backend_only_pass") is True:
        return _check("target_client_visibility", "failed", "backend-only proof was treated as target-client visibility")
    denied = _string_list(visibility.get("denied_tools_visible"))
    if denied:
        return _check("target_client_visibility", "failed", "denied tools remain visible to Codex")
    if visibility.get("project_root") not in {root, None}:
        return _check("target_client_visibility", "failed", "negative visibility check used the wrong project root")
    if visibility.get("service_binding") not in {service_binding, None}:
        return _check("target_client_visibility", "failed", "negative visibility check used the wrong service binding")
    return _check("target_client_visibility", "passed", "negative Codex visibility checks passed")


def _trust_report(evidence: Mapping[str, Any], root: str) -> dict[str, Any]:
    trust = _mapping(evidence.get("trust"))
    state = str(trust.get("state") or "unknown")
    return {
        "state": state,
        "project_root": str(trust.get("project_root") or root),
        "global_trust_required": trust.get("global_trust_required") is True,
        "approval_evidence": str(trust.get("approval_evidence") or "missing"),
        "mutation_allowed": False,
        "mutation_performed": trust.get("mutated_by_conformance") is True,
    }


def _overall_status(checks: Sequence[Mapping[str, Any]]) -> str:
    statuses = {str(check["status"]) for check in checks}
    if "failed" in statuses:
        return "failed_conformance"
    if "blocked" in statuses:
        return "blocked_limitation"
    if statuses == {"passed"}:
        return "passing_conformance"
    return "failed_conformance"


def _with_synthetic_blocker(result: Mapping[str, Any], name: str, reason: str) -> dict[str, Any]:
    updated = copy.deepcopy(dict(result))
    blocker = _check(name, "failed", reason)
    updated["checks"].append(blocker)
    updated["blockers"].append(blocker)
    updated["status"] = "failed_conformance"
    updated["decision"] = "block_target_client_proof"
    return updated


def _check(name: str, status: str, reason: str) -> dict[str, str]:
    return {"name": name, "status": status, "reason": reason}


def _get(data: Mapping[str, Any], dotted_path: str) -> Any:
    current: Any = data
    for part in dotted_path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str)]


def _json_copy(value: Any) -> Any:
    return copy.deepcopy(json.loads(json.dumps(value, sort_keys=True)))


def _stable_digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _redacted_evidence_fingerprint(evidence: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "client": _get(evidence, "client.name"),
        "config": {
            "surface": _get(evidence, "config.surface"),
            "scope": _get(evidence, "config.scope"),
            "project_root": _get(evidence, "config.project_root"),
            "loaded_generation": _get(evidence, "config.loaded_generation"),
            "expected_generation": _get(evidence, "config.expected_generation"),
            "owned_block_class": _get(evidence, "config.owned_block_class"),
        },
        "trust": _trust_report(evidence, str(_get(evidence, "config.project_root") or "")),
        "restart": _mapping(evidence.get("restart")),
        "auth": {
            "strength": _get(evidence, "auth.strength"),
            "material_source": _get(evidence, "auth.material_source"),
        },
        "list_tools": {
            "client": _get(evidence, "list_tools.client"),
            "status": _get(evidence, "list_tools.status"),
            "visible_service_bindings": _get(evidence, "list_tools.visible_service_bindings"),
            "tools": _get(evidence, "list_tools.tools"),
        },
        "call_tool": {
            "client": _get(evidence, "call_tool.client"),
            "status": _get(evidence, "call_tool.status"),
            "service_binding": _get(evidence, "call_tool.service_binding"),
            "result_digest": _get(evidence, "call_tool.result_digest"),
        },
        "negative_visibility": _mapping(evidence.get("negative_visibility")),
    }


def _assert_no_secret_shaped_literals(data: Any) -> None:
    encoded = json.dumps(data, sort_keys=True)
    if contracts.SECRET_VALUE_RE.search(encoded):
        raise CodexConformanceError("conformance result contains secret-shaped literal")
