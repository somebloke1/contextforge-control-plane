#!/usr/bin/env python3
"""Deterministic harness foundations for ContextForge control-plane scenarios."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import control_plane_contracts as contracts


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REQUIREMENTS_PATH = REPO_ROOT / "tests/fixtures/control_plane_requirements.json"
DEFAULT_SCENARIOS_PATH = REPO_ROOT / "tests/fixtures/control_plane_scenarios.json"
SCHEMA_VERSION = 1
STAMP = "2026-05-30T21:00:00Z"

REQUIREMENT_FIELDS = frozenset(
    {
        "requirement_id",
        "source_section",
        "summary",
        "evidence_types",
        "required_layers",
        "mvs_required",
        "deferrability",
        "acceptance_gate",
    }
)
DEFERRABILITY_VALUES = frozenset({"non_deferrable", "deferrable_with_governance_waiver", "post_mvs"})
ACCEPTANCE_GATES = frozenset(
    {"must_pass_mvs", "must_pass_before_remote_or_expansion", "deferrable_with_governance_waiver"}
)
EVIDENCE_TYPES = frozenset(
    {
        "unit_test",
        "deterministic_assertion",
        "integration_probe",
        "scenario_ledger",
        "evaluator_verdict",
    }
)
REQUIRED_LAYERS = frozenset({"deterministic", "probe", "inference_inclusive"})
ASSERTION_TYPES = frozenset(
    {
        "scenario_has_requirement",
        "expected_non_action",
        "forbidden_mutation",
        "required_trace",
        "required_receipt",
        "expected_state_value",
        "inferential_isolation",
    }
)


class HarnessValidationError(ValueError):
    """Raised when harness fixture data is malformed."""


@dataclass(frozen=True)
class AssertionResult:
    assertion_id: str
    requirement_id: str
    assertion_type: str
    result: str
    evidence_ref: str
    evidence_hash: str
    summary: str

    def as_ledger_item(self) -> dict[str, Any]:
        return {
            "assertion_id": self.assertion_id,
            "requirement_id": self.requirement_id,
            "assertion_type": self.assertion_type,
            "result": self.result,
            "evidence_ref": self.evidence_ref,
            "evidence_hash": self.evidence_hash,
            "summary": self.summary,
        }


@dataclass(frozen=True)
class ScenarioRunResult:
    run_id: str
    scenario_id: str
    requirement_ids: tuple[str, ...]
    assertion_results: tuple[AssertionResult, ...]
    transcript_capture: dict[str, Any]
    world_state_capture: dict[str, Any]
    ledger: dict[str, Any]
    assistant_executed: bool = False

    @property
    def passed(self) -> bool:
        return all(result.result == "passed" for result in self.assertion_results)


def load_requirements(path: str | Path = DEFAULT_REQUIREMENTS_PATH) -> dict[str, Any]:
    return validate_requirement_registry(_load_json(path))


def load_scenarios(
    path: str | Path = DEFAULT_SCENARIOS_PATH,
    *,
    requirement_ids: set[str] | None = None,
) -> dict[str, Any]:
    return validate_scenario_registry(_load_json(path), requirement_ids=requirement_ids)


def validate_requirement_registry(data: dict[str, Any]) -> dict[str, Any]:
    if data.get("version") != SCHEMA_VERSION:
        raise HarnessValidationError("requirement registry version must be 1")
    requirements = data.get("requirements")
    if not isinstance(requirements, list) or not requirements:
        raise HarnessValidationError("requirement registry requires a non-empty requirements list")

    seen: set[str] = set()
    for index, requirement in enumerate(requirements):
        if not isinstance(requirement, dict):
            raise HarnessValidationError(f"requirement at index {index} must be an object")
        missing = REQUIREMENT_FIELDS - set(requirement)
        if missing:
            raise HarnessValidationError(
                f"requirement at index {index} missing fields: {', '.join(sorted(missing))}"
            )
        requirement_id = _require_string(requirement, "requirement_id", f"requirements[{index}]")
        if requirement_id in seen:
            raise HarnessValidationError(f"duplicate requirement_id: {requirement_id}")
        seen.add(requirement_id)
        _require_string(requirement, "source_section", requirement_id)
        _require_string(requirement, "summary", requirement_id)
        _require_string_list(requirement, "evidence_types", requirement_id, allowed=EVIDENCE_TYPES)
        _require_string_list(requirement, "required_layers", requirement_id, allowed=REQUIRED_LAYERS)
        if not isinstance(requirement.get("mvs_required"), bool):
            raise HarnessValidationError(f"{requirement_id}.mvs_required must be boolean")
        if requirement["deferrability"] not in DEFERRABILITY_VALUES:
            raise HarnessValidationError(f"{requirement_id}.deferrability is invalid")
        if requirement["acceptance_gate"] not in ACCEPTANCE_GATES:
            raise HarnessValidationError(f"{requirement_id}.acceptance_gate is invalid")
        if requirement["mvs_required"] and requirement["acceptance_gate"] != "must_pass_mvs":
            raise HarnessValidationError(f"{requirement_id} is MVS-required but not gated as must_pass_mvs")
    return data


def validate_scenario_registry(
    data: dict[str, Any],
    *,
    requirement_ids: set[str] | None = None,
) -> dict[str, Any]:
    if data.get("version") != SCHEMA_VERSION:
        raise HarnessValidationError("scenario registry version must be 1")
    scenarios = data.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        raise HarnessValidationError("scenario registry requires a non-empty scenarios list")

    known_requirements = set(requirement_ids or ())
    seen: set[str] = set()
    for index, scenario in enumerate(scenarios):
        if not isinstance(scenario, dict):
            raise HarnessValidationError(f"scenario at index {index} must be an object")
        contracts.validate_artifact("requirement_scenario", scenario)
        scenario_id = _require_string(scenario, "scenario_id", f"scenarios[{index}]")
        if scenario_id in seen:
            raise HarnessValidationError(f"duplicate scenario_id: {scenario_id}")
        seen.add(scenario_id)
        for requirement_id in scenario["requirement_ids"]:
            if known_requirements and requirement_id not in known_requirements:
                raise HarnessValidationError(f"{scenario_id} references unknown requirement_id: {requirement_id}")
        for assertion in scenario.get("deterministic_assertions", []):
            _validate_assertion(scenario_id, assertion, known_requirements)
        for rubric in scenario.get("inference_rubric", []):
            requirement_id = rubric.get("requirement_id") if isinstance(rubric, dict) else None
            if not isinstance(requirement_id, str) or not requirement_id:
                raise HarnessValidationError(f"{scenario_id} inference rubric requires requirement_id")
            if known_requirements and requirement_id not in known_requirements:
                raise HarnessValidationError(f"{scenario_id} rubric references unknown requirement_id: {requirement_id}")
    return data


def build_coverage_matrix(requirements: dict[str, Any], scenarios: dict[str, Any]) -> dict[str, Any]:
    requirement_rows = []
    scenario_list = scenarios.get("scenarios", [])
    for requirement in requirements["requirements"]:
        if not requirement["mvs_required"]:
            continue
        requirement_id = requirement["requirement_id"]
        deterministic = []
        probe = []
        inference = []
        for scenario in scenario_list:
            scenario_id = scenario["scenario_id"]
            if requirement_id not in scenario["requirement_ids"]:
                continue
            for assertion in scenario.get("deterministic_assertions", []):
                if assertion.get("requirement_id") != requirement_id:
                    continue
                slot = {
                    "scenario_id": scenario_id,
                    "assertion_id": assertion["assertion_id"],
                    "assertion_type": assertion["type"],
                }
                deterministic.append(slot)
                if assertion["type"] in {"required_trace", "required_receipt"}:
                    probe.append(slot)
            for rubric in scenario.get("inference_rubric", []):
                if rubric.get("requirement_id") == requirement_id:
                    inference.append({"scenario_id": scenario_id, "rubric_id": rubric.get("rubric_id")})

        required_layers = set(requirement["required_layers"])
        gaps = []
        if "deterministic" in required_layers and not deterministic:
            gaps.append({"slot": "deterministic", "reason": "no deterministic assertion cites requirement"})
        if "probe" in required_layers and not probe:
            gaps.append({"slot": "probe", "reason": "no required trace, receipt, or probe slot cites requirement"})
        if "inference_inclusive" in required_layers and not inference:
            gaps.append({"slot": "inference_inclusive", "reason": "no inference rubric cites requirement"})

        requirement_rows.append(
            {
                "requirement_id": requirement_id,
                "acceptance_gate": requirement["acceptance_gate"],
                "deferrability": requirement["deferrability"],
                "deterministic": deterministic,
                "probe": probe,
                "inference_inclusive": inference,
                "gaps": gaps,
                "governance_waiver_ref": None,
            }
        )

    return {
        "version": SCHEMA_VERSION,
        "mvs_requirement_count": len(requirement_rows),
        "coverage_complete": all(not row["gaps"] for row in requirement_rows),
        "requirements": requirement_rows,
    }


def run_deterministic_scenarios(
    requirements: dict[str, Any],
    scenarios: dict[str, Any],
    *,
    run_id: str = "run-deterministic-001",
    timestamp: str = STAMP,
) -> list[ScenarioRunResult]:
    requirement_ids = {requirement["requirement_id"] for requirement in requirements["requirements"]}
    validate_requirement_registry(requirements)
    validate_scenario_registry(scenarios, requirement_ids=requirement_ids)

    results = []
    for scenario in scenarios["scenarios"]:
        assertion_results = tuple(_evaluate_assertion(scenario, assertion) for assertion in scenario["deterministic_assertions"])
        transcript_capture = build_transcript_capture(scenario, run_id=run_id, timestamp=timestamp)
        world_state_capture = build_world_state_capture(scenario, run_id=run_id, timestamp=timestamp)
        ledger = build_evidence_ledger(
            scenario,
            assertion_results,
            run_id=run_id,
            timestamp=timestamp,
            transcript_ref=transcript_capture["artifact_ref"]["ref"],
            world_state_diff_ref=world_state_capture["world_state_diff_ref"],
        )
        results.append(
            ScenarioRunResult(
                run_id=run_id,
                scenario_id=scenario["scenario_id"],
                requirement_ids=tuple(scenario["requirement_ids"]),
                assertion_results=assertion_results,
                transcript_capture=transcript_capture,
                world_state_capture=world_state_capture,
                ledger=ledger,
            )
        )
    return results


def build_transcript_capture(scenario: dict[str, Any], *, run_id: str, timestamp: str = STAMP) -> dict[str, Any]:
    scenario_id = scenario["scenario_id"]
    entries = [
        {
            "entry_id": "prompt-1",
            "actor": "user",
            "visibility": "tested_agent",
            "payload": {"text": scenario["tested_agent_view"]["user_prompt"]},
        }
    ]
    for event in scenario.get("during_test_events", []):
        visible_to_agent = "tested_agent" in event.get("visible_to", [])
        output_visible = event.get("tool_output_visibility") == "tested_agent"
        if visible_to_agent or output_visible:
            entries.append(
                {
                    "entry_id": event["event_id"],
                    "actor": event["actor"],
                    "visibility": "tested_agent",
                    "payload": copy.deepcopy(event["payload"]),
                }
            )

    capture = {
        "transcript_id": f"transcript-{run_id}-{scenario_id}",
        "run_id": run_id,
        "scenario_id": scenario_id,
        "captured_at": timestamp,
        "visibility": "tested_agent",
        "hidden_state_included": False,
        "remediation_context_included": False,
        "entries": entries,
        "redaction_status": "passed",
    }
    return {
        "capture": capture,
        "artifact_ref": contracts.artifact_ref(
            f"run/{run_id}/{scenario_id}/tested-agent-transcript.json",
            capture,
            resolved_at=timestamp,
        ),
    }


def build_world_state_capture(scenario: dict[str, Any], *, run_id: str, timestamp: str = STAMP) -> dict[str, Any]:
    scenario_id = scenario["scenario_id"]
    initial_ref = contracts.artifact_ref(
        f"run/{run_id}/{scenario_id}/initial-world-state.redacted.json",
        scenario["hidden_initial_conditions"],
        resolved_at=timestamp,
    )
    diff = {
        "world_state_diff_id": f"world-state-diff-{run_id}-{scenario_id}",
        "run_id": run_id,
        "scenario_id": scenario_id,
        "visibility": "evaluator_only",
        "allowed_mutations": copy.deepcopy(scenario["allowed_mutations"]),
        "forbidden_mutations": copy.deepcopy(scenario["forbidden_mutations"]),
        "expected_outcomes": copy.deepcopy(scenario["expected_outcomes"]),
        "observed_mutations": [],
        "redaction_status": "passed",
    }
    diff_ref = contracts.artifact_ref(
        f"run/{run_id}/{scenario_id}/world-state-diff.redacted.json",
        diff,
        resolved_at=timestamp,
    )
    return {
        "world_state_capture_id": f"world-state-{run_id}-{scenario_id}",
        "run_id": run_id,
        "scenario_id": scenario_id,
        "captured_at": timestamp,
        "initial_world_state_ref": initial_ref,
        "world_state_diff": diff,
        "world_state_diff_ref": diff_ref["ref"],
        "world_state_diff_artifact_ref": diff_ref,
        "redaction_status": "passed",
    }


def build_evidence_ledger(
    scenario: dict[str, Any],
    assertion_results: tuple[AssertionResult, ...] | list[AssertionResult],
    *,
    run_id: str,
    timestamp: str = STAMP,
    transcript_ref: str | None = None,
    world_state_diff_ref: str | None = None,
    evaluator_verdict_refs: list[dict[str, Any]] | None = None,
    remediation_refs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    scenario_id = scenario["scenario_id"]
    evidence_hashes = [result.evidence_hash for result in assertion_results]
    ledger = {
        "ledger_id": f"ledger-{run_id}-{scenario_id}",
        "schema_uri": "contextforge://control-plane/schemas/evidence-ledger/v1",
        "run_id": run_id,
        "requirement_ids": list(scenario["requirement_ids"]),
        "scenario_ref": f"tests/fixtures/control_plane_scenarios.json#{scenario_id}",
        "tested_agent_transcript_ref": transcript_ref or f"run/{run_id}/{scenario_id}/tested-agent-transcript.json",
        "deterministic_assertion_results": [result.as_ledger_item() for result in assertion_results],
        "consent_receipt_refs": [
            _ref("receipts", receipt_id, {"scenario_id": scenario_id, "receipt_id": receipt_id}, timestamp)
            for receipt_id in scenario["expected_outcomes"]["required_receipts"]
        ],
        "verification_trace_refs": [
            _ref("traces", trace_id, {"scenario_id": scenario_id, "trace_id": trace_id}, timestamp)
            for trace_id in scenario["expected_outcomes"]["required_traces"]
        ],
        "world_state_diff_ref": world_state_diff_ref or f"run/{run_id}/{scenario_id}/world-state-diff.redacted.json",
        "evaluator_verdict_refs": evaluator_verdict_refs or [],
        "remediation_refs": remediation_refs or [],
        "redaction_status": "passed",
        "evidence_hashes": evidence_hashes,
    }
    contracts.validate_artifact("evidence_ledger", ledger)
    return ledger


def build_evaluator_verdict(
    scenario: dict[str, Any],
    ledger: dict[str, Any],
    *,
    verdict: str = "pass",
    failed_requirements: list[str] | None = None,
    likely_cause: str = "implementation_failure",
    remediation_target: str = "code",
    timestamp: str = STAMP,
) -> dict[str, Any]:
    failures = failed_requirements or []
    if verdict == "fail" and not failures:
        failures = list(scenario["requirement_ids"])
    evidence_hash = contracts.artifact_digest(ledger)
    artifact_ref = contracts.artifact_ref(
        f"contextforge://control-plane/evidence-ledgers/{ledger['ledger_id']}",
        ledger,
        resolved_at=timestamp,
    )
    verdict_artifact = {
        "verdict_id": f"verdict-{ledger['run_id']}-{scenario['scenario_id']}",
        "schema_uri": "contextforge://control-plane/schemas/evaluator-verdict/v1",
        "created_at": timestamp,
        "evaluator_run": {"model_or_agent": None, "prompt_digest": None},
        "verdict": verdict,
        "scenario_id": scenario["scenario_id"],
        "requirement_ids": list(scenario["requirement_ids"]),
        "evaluated_artifact_refs": [
            contracts.artifact_ref(
                f"tests/fixtures/control_plane_scenarios.json#{scenario['scenario_id']}",
                scenario,
                resolved_at=timestamp,
            )
        ],
        "deterministic_assertion_refs": [artifact_ref],
        "failed_requirements": failures,
        "evidence": [
            {
                "source": "audit",
                "reference": ledger["ledger_id"],
                "summary": "redacted deterministic run ledger",
                "evidence_hash": evidence_hash,
            }
        ],
        "likely_cause": likely_cause if verdict != "pass" else "flaky_environment",
        "remediation_target": remediation_target,
        "redaction_status": "passed",
        "evidence_hashes": [evidence_hash],
        "requirement_gap_proposal": "review requirement wording" if verdict == "requirement_gap" else None,
    }
    contracts.validate_artifact("evaluator_verdict", verdict_artifact)
    return verdict_artifact


def build_remediation_handoff(
    scenario: dict[str, Any],
    verdict: dict[str, Any],
    *,
    timestamp: str = STAMP,
) -> dict[str, Any]:
    handoff = {
        "handoff_id": f"remediation-{verdict['verdict_id']}",
        "schema_uri": "contextforge://control-plane/schemas/remediation-handoff/v1",
        "created_at": timestamp,
        "scenario_id": scenario["scenario_id"],
        "requirement_ids": list(verdict["requirement_ids"]),
        "failed_requirements": list(verdict["failed_requirements"]),
        "verdict_ref": contracts.artifact_ref(
            f"contextforge://control-plane/verdicts/{verdict['verdict_id']}",
            verdict,
            resolved_at=timestamp,
        ),
        "evidence_refs": copy.deepcopy(verdict["evaluated_artifact_refs"]),
        "remediation_target": verdict["remediation_target"],
        "allowed_context": [
            "scenario tested-agent view",
            "failed deterministic assertions",
            "cited redacted evidence",
            "evaluator verdict",
        ],
        "forbidden_context": [
            "test-generation rationale",
            "future evaluator prompts",
            "broader orchestration state",
            "oracle mutation",
        ],
        "redaction_status": "passed",
    }
    contracts.validate_redacted(handoff, require_status=True)
    return handoff


def _load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _require_string(data: dict[str, Any], key: str, context: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise HarnessValidationError(f"{context}.{key} must be a non-empty string")
    return value


def _require_string_list(
    data: dict[str, Any],
    key: str,
    context: str,
    *,
    allowed: frozenset[str],
) -> list[str]:
    value = data.get(key)
    if not isinstance(value, list) or not value:
        raise HarnessValidationError(f"{context}.{key} must be a non-empty list")
    for item in value:
        if not isinstance(item, str) or not item:
            raise HarnessValidationError(f"{context}.{key} contains a non-string item")
        if item not in allowed:
            raise HarnessValidationError(f"{context}.{key} contains invalid value: {item}")
    return value


def _validate_assertion(scenario_id: str, assertion: dict[str, Any], known_requirements: set[str]) -> None:
    if not isinstance(assertion, dict):
        raise HarnessValidationError(f"{scenario_id} deterministic assertion must be an object")
    for field in ("assertion_id", "requirement_id", "type"):
        _require_string(assertion, field, scenario_id)
    if assertion["type"] not in ASSERTION_TYPES:
        raise HarnessValidationError(f"{scenario_id} assertion has unsupported type: {assertion['type']}")
    if known_requirements and assertion["requirement_id"] not in known_requirements:
        raise HarnessValidationError(
            f"{scenario_id} assertion references unknown requirement_id: {assertion['requirement_id']}"
        )


def _evaluate_assertion(scenario: dict[str, Any], assertion: dict[str, Any]) -> AssertionResult:
    assertion_type = assertion["type"]
    passed = False
    if assertion_type == "scenario_has_requirement":
        passed = assertion["requirement_id"] in scenario["requirement_ids"]
    elif assertion_type == "expected_non_action":
        passed = assertion.get("value") in scenario["expected_outcomes"]["non_actions"]
    elif assertion_type == "forbidden_mutation":
        expected_path = assertion.get("path")
        passed = any(item.get("path") == expected_path for item in scenario["forbidden_mutations"])
    elif assertion_type == "required_trace":
        passed = assertion.get("trace_id") in scenario["expected_outcomes"]["required_traces"]
    elif assertion_type == "required_receipt":
        passed = assertion.get("receipt_id") in scenario["expected_outcomes"]["required_receipts"]
    elif assertion_type == "expected_state_value":
        passed = _read_path(scenario["expected_outcomes"]["state"], assertion.get("path", [])) == assertion.get("equals")
    elif assertion_type == "inferential_isolation":
        contracts.validate_artifact("requirement_scenario", scenario)
        passed = True
    else:
        raise HarnessValidationError(f"unsupported assertion type: {assertion_type}")

    result = "passed" if passed else "failed"
    evidence = {
        "scenario_id": scenario["scenario_id"],
        "assertion_id": assertion["assertion_id"],
        "requirement_id": assertion["requirement_id"],
        "result": result,
    }
    return AssertionResult(
        assertion_id=assertion["assertion_id"],
        requirement_id=assertion["requirement_id"],
        assertion_type=assertion_type,
        result=result,
        evidence_ref=f"run/deterministic/{scenario['scenario_id']}/{assertion['assertion_id']}.json",
        evidence_hash=contracts.artifact_digest(evidence),
        summary=assertion.get("summary", f"{assertion_type} {result}"),
    )


def _read_path(value: Any, path: Any) -> Any:
    if not isinstance(path, list):
        raise HarnessValidationError("expected_state_value assertion path must be a list")
    current = value
    for part in path:
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _ref(kind: str, item_id: str, data: dict[str, Any], timestamp: str) -> dict[str, Any]:
    return contracts.artifact_ref(
        f"contextforge://control-plane/{kind}/{item_id}",
        data,
        resolved_at=timestamp,
        catalog_revision_or_etag=None,
    )
