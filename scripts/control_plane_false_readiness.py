#!/usr/bin/env python3
"""Deterministic false-readiness fixture classifier for ContextForge evidence."""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import control_plane_contracts as contracts


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES_PATH = REPO_ROOT / "tests/fixtures/control_plane_false_readiness_cases.json"
SCHEMA_VERSION = 1
DEFAULT_GENERATED_AT = "2026-06-18T12:00:00Z"

READINESS_GUARDRAIL_REF = "docs/readiness-claim-guardrails.md#false-readiness-fixture-reasons"
CLAIM_STATUSES_REQUIRING_CLIENT_PROOF = frozenset({"target_client_ready", "verified"})
TOKEN_PASSING_SCOPES = frozenset({"client-visible-validation", "target-client-proof"})

FAILURE_REASONS: dict[str, dict[str, str]] = {
    "stale_or_mismatched_model_id": {
        "category": "model_identity",
        "summary": "The run did not prove the expected current model id.",
    },
    "absent_scoped_probe_token": {
        "category": "auth",
        "summary": "No scoped probe token was present for the client-visible proof.",
    },
    "revoked_scoped_probe_token": {
        "category": "auth",
        "summary": "The scoped probe token was revoked before or during the proof.",
    },
    "missing_client_binding_fixture": {
        "category": "client_binding",
        "summary": "The target Pi/OpenCode client binding fixture was absent.",
    },
    "backend_only_claimed_client_visible": {
        "category": "surface",
        "summary": "Backend-only evidence was claimed as target-client-visible proof.",
    },
    "wrapper_tool_call_failure": {
        "category": "tool_call",
        "summary": "The wrapper or target-client tool call failed.",
    },
    "stale_timestamp": {
        "category": "freshness",
        "summary": "The evidence timestamp is older than the allowed freshness window.",
    },
    "wrong_exercised_surface": {
        "category": "surface",
        "summary": "The exercised surface did not match the claimed target surface.",
    },
}


class FalseReadinessError(ValueError):
    """Raised when false-readiness fixture data is malformed."""


def load_false_readiness_cases(path: str | Path = DEFAULT_CASES_PATH) -> dict[str, Any]:
    return validate_false_readiness_cases(_load_json(path))


def validate_false_readiness_cases(data: Mapping[str, Any]) -> dict[str, Any]:
    fixture = _json_copy(data)
    if fixture.get("version") != SCHEMA_VERSION:
        raise FalseReadinessError("false-readiness fixture version must be 1")
    cases = fixture.get("cases")
    if not isinstance(cases, list) or not cases:
        raise FalseReadinessError("false-readiness fixture requires a non-empty cases list")

    seen: set[str] = set()
    covered_reasons: set[str] = set()
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            raise FalseReadinessError(f"case at index {index} must be an object")
        name = _require_string(case, "name", f"cases[{index}]")
        if name in seen:
            raise FalseReadinessError(f"duplicate false-readiness case name: {name}")
        seen.add(name)
        _require_mapping(case, "claim", name)
        _require_mapping(case, "evidence", name)
        expected = _require_mapping(case, "expected", name)
        expected_decision = _require_string(expected, "decision", name)
        if expected_decision not in {"allow_readiness_claim", "block_readiness_claim"}:
            raise FalseReadinessError(f"{name}.expected.decision is invalid")
        expected_reasons = _string_list(expected.get("failure_reason_ids"))
        unknown = sorted(set(expected_reasons) - set(FAILURE_REASONS))
        if unknown:
            raise FalseReadinessError(f"{name} references unknown failure reasons: {', '.join(unknown)}")
        covered_reasons.update(expected_reasons)

        claim = _require_mapping(case, "claim", name)
        _require_string(claim, "status", name)
        _require_string(claim, "target_client", name)
        _require_string(claim, "expected_model_id", name)
        _require_string(claim, "expected_exercised_surface", name)

    missing = sorted(set(FAILURE_REASONS) - covered_reasons)
    if missing:
        raise FalseReadinessError("fixture does not cover failure reasons: " + ", ".join(missing))
    return fixture


def evaluate_false_readiness_case(
    case: Mapping[str, Any],
    *,
    now: str | None = None,
) -> dict[str, Any]:
    fixture_case = _json_copy(case)
    name = _require_string(fixture_case, "name", "case")
    claim = _require_mapping(fixture_case, "claim", name)
    evidence = _require_mapping(fixture_case, "evidence", name)
    generated_at = now or str(fixture_case.get("generated_at") or DEFAULT_GENERATED_AT)
    max_age_seconds = int(fixture_case.get("max_evidence_age_seconds") or 86_400)

    blockers: list[dict[str, Any]] = []
    blockers.extend(_model_identity_blockers(claim, evidence))
    blockers.extend(_probe_token_blockers(evidence))
    blockers.extend(_client_binding_blockers(claim, evidence))
    blockers.extend(_proof_surface_blockers(claim, evidence))
    blockers.extend(_wrapper_tool_call_blockers(evidence))
    blockers.extend(_freshness_blockers(evidence, now=generated_at, max_age_seconds=max_age_seconds))

    failure_reason_ids = _dedupe([blocker["reason_id"] for blocker in blockers])
    decision = "block_readiness_claim" if blockers else "allow_readiness_claim"
    result = {
        "case_name": name,
        "decision": decision,
        "status": "false_readiness" if blockers else "readiness_claim_supported",
        "claimed_status": claim["status"],
        "target_client": claim["target_client"],
        "expected_exercised_surface": claim["expected_exercised_surface"],
        "observed_exercised_surface": _get(evidence, "proof.exercised_surface"),
        "failure_reason_ids": failure_reason_ids,
        "blockers": blockers,
        "non_actions": [
            "did_not_probe_live_contextforge",
            "did_not_mutate_client_config",
            "did_not_create_or_revoke_tokens",
        ],
        "guardrail_ref": READINESS_GUARDRAIL_REF,
        "redaction_status": "passed",
    }
    contracts.validate_redacted(result, require_status=True)
    return result


def build_false_readiness_report(
    cases: Mapping[str, Any],
    *,
    now: str | None = None,
) -> dict[str, Any]:
    fixture = validate_false_readiness_cases(cases)
    generated_at = now or str(fixture.get("generated_at") or DEFAULT_GENERATED_AT)
    case_results = [
        evaluate_false_readiness_case(case, now=generated_at)
        for case in fixture["cases"]
    ]
    blocked = [result for result in case_results if result["decision"] == "block_readiness_claim"]
    reason_summary = []
    for reason_id in sorted(FAILURE_REASONS):
        names = [
            result["case_name"]
            for result in blocked
            if reason_id in result["failure_reason_ids"]
        ]
        reason_summary.append(
            {
                "reason_id": reason_id,
                "category": FAILURE_REASONS[reason_id]["category"],
                "summary": FAILURE_REASONS[reason_id]["summary"],
                "case_names": names,
            }
        )
    report = {
        "report_id": "contextforge-false-readiness-fixture-report-v1",
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "source_fixture_ref": str(DEFAULT_CASES_PATH.relative_to(REPO_ROOT)),
        "readiness_guardrail_ref": READINESS_GUARDRAIL_REF,
        "case_results": case_results,
        "failure_reason_summary": reason_summary,
        "decision_summary": {
            "total_cases": len(case_results),
            "blocked_claims": len(blocked),
            "allowed_claims": len(case_results) - len(blocked),
            "covered_failure_reasons": sorted(
                {
                    reason_id
                    for result in case_results
                    for reason_id in result["failure_reason_ids"]
                }
            ),
        },
        "redaction_status": "passed",
    }
    contracts.validate_redacted(report, require_status=True)
    return report


def _model_identity_blockers(claim: Mapping[str, Any], evidence: Mapping[str, Any]) -> list[dict[str, Any]]:
    expected = str(claim.get("expected_model_id") or "")
    observed = str(_get(evidence, "model.model_id") or "")
    if not observed or observed != expected:
        return [
            _blocker(
                "stale_or_mismatched_model_id",
                "model_identity",
                f"expected model id {expected!r} but observed {observed!r}",
                evidence_refs=_refs(evidence, "model"),
            )
        ]
    return []


def _probe_token_blockers(evidence: Mapping[str, Any]) -> list[dict[str, Any]]:
    token = _mapping(evidence.get("scoped_probe_token"))
    if token.get("present") is not True:
        return [
            _blocker(
                "absent_scoped_probe_token",
                "scoped_probe_token",
                "scoped probe token is absent",
                evidence_refs=_refs(evidence, "scoped_probe_token"),
            )
        ]
    if token.get("revoked") is True:
        return [
            _blocker(
                "revoked_scoped_probe_token",
                "scoped_probe_token",
                "scoped probe token was revoked",
                evidence_refs=_refs(evidence, "scoped_probe_token"),
            )
        ]
    if str(token.get("scope") or "") not in TOKEN_PASSING_SCOPES:
        return [
            _blocker(
                "absent_scoped_probe_token",
                "scoped_probe_token",
                "scoped probe token does not name target-client proof scope",
                evidence_refs=_refs(evidence, "scoped_probe_token"),
            )
        ]
    return []


def _client_binding_blockers(claim: Mapping[str, Any], evidence: Mapping[str, Any]) -> list[dict[str, Any]]:
    target_client = str(claim.get("target_client") or "")
    if target_client not in {"pi", "opencode"}:
        return []
    binding = _mapping(evidence.get("client_binding_fixture"))
    if binding.get("present") is True and binding.get("fixture_ref") and binding.get("client") == target_client:
        return []
    return [
        _blocker(
            "missing_client_binding_fixture",
            "client_binding_fixture",
            f"missing {target_client} client binding fixture",
            evidence_refs=_refs(evidence, "client_binding_fixture"),
        )
    ]


def _proof_surface_blockers(claim: Mapping[str, Any], evidence: Mapping[str, Any]) -> list[dict[str, Any]]:
    proof = _mapping(evidence.get("proof"))
    claimed_status = str(claim.get("status") or "")
    proof_type = str(proof.get("proof_type") or "")
    if claimed_status in CLAIM_STATUSES_REQUIRING_CLIENT_PROOF and (
        proof.get("backend_only") is True or proof_type in {"backend_health", "contextforge_registry"}
    ):
        return [
            _blocker(
                "backend_only_claimed_client_visible",
                "proof_surface",
                "backend-only proof cannot support target-client readiness",
                evidence_refs=_refs(evidence, "proof"),
            )
        ]
    expected_surface = str(claim.get("expected_exercised_surface") or "")
    observed_surface = str(proof.get("exercised_surface") or "")
    expected_client = str(claim.get("target_client") or "")
    observed_client = str(proof.get("client") or "")
    if observed_surface != expected_surface or observed_client != expected_client:
        return [
            _blocker(
                "wrong_exercised_surface",
                "proof_surface",
                f"expected {expected_client}/{expected_surface} but observed {observed_client}/{observed_surface}",
                evidence_refs=_refs(evidence, "proof"),
            )
        ]
    return []


def _wrapper_tool_call_blockers(evidence: Mapping[str, Any]) -> list[dict[str, Any]]:
    wrapper = _mapping(evidence.get("wrapper"))
    proof = _mapping(evidence.get("proof"))
    tool_call = _mapping(proof.get("tool_call"))
    if wrapper.get("status") == "failed" or tool_call.get("status") == "failed" or proof.get("status") == "failed":
        detail = str(wrapper.get("error_class") or tool_call.get("error_class") or "target-client tool call failed")
        return [
            _blocker(
                "wrapper_tool_call_failure",
                "tool_call",
                detail,
                evidence_refs=[*_refs(evidence, "wrapper"), *_refs(evidence, "proof")],
            )
        ]
    return []


def _freshness_blockers(
    evidence: Mapping[str, Any],
    *,
    now: str,
    max_age_seconds: int,
) -> list[dict[str, Any]]:
    proof_observed_at = str(_get(evidence, "proof.observed_at") or "")
    if not proof_observed_at:
        return [
            _blocker(
                "stale_timestamp",
                "freshness",
                "proof timestamp is missing",
                evidence_refs=_refs(evidence, "proof"),
            )
        ]
    age_seconds = (_parse_timestamp(now) - _parse_timestamp(proof_observed_at)).total_seconds()
    if age_seconds < 0 or age_seconds > max_age_seconds:
        return [
            _blocker(
                "stale_timestamp",
                "freshness",
                f"proof timestamp age {int(age_seconds)}s exceeds {max_age_seconds}s",
                evidence_refs=_refs(evidence, "proof"),
            )
        ]
    return []


def _blocker(reason_id: str, check_id: str, detail: str, *, evidence_refs: Sequence[str]) -> dict[str, Any]:
    reason = FAILURE_REASONS[reason_id]
    return {
        "reason_id": reason_id,
        "category": reason["category"],
        "check_id": check_id,
        "detail": detail,
        "evidence_refs": list(evidence_refs),
        "remediation_boundary": "collect fresh target-client-visible proof before claiming readiness",
    }


def _refs(evidence: Mapping[str, Any], field: str) -> list[str]:
    ref = _get(evidence, f"{field}.ref")
    if isinstance(ref, str) and ref:
        return [ref]
    return [f"fixture:{field}"]


def _load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _json_copy(value: Any) -> Any:
    return copy.deepcopy(json.loads(json.dumps(value, sort_keys=True)))


def _require_mapping(data: Mapping[str, Any], key: str, context: str) -> Mapping[str, Any]:
    value = data.get(key)
    if not isinstance(value, Mapping):
        raise FalseReadinessError(f"{context}.{key} must be an object")
    return value


def _require_string(data: Mapping[str, Any], key: str, context: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise FalseReadinessError(f"{context}.{key} must be a non-empty string")
    return value


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _get(data: Mapping[str, Any], dotted_path: str) -> Any:
    current: Any = data
    for part in dotted_path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current


def _dedupe(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    result = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _parse_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise FalseReadinessError(f"invalid timestamp: {value}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
