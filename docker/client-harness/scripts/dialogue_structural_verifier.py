from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def verify_dialogue_structure(
    *,
    use_case: str,
    client: str,
    evidence_path: Path,
    metadata_path: Path | None,
    session_id: str = "",
    expected_prompt_count: int | None = None,
) -> dict[str, Any]:
    failures: list[dict[str, str]] = []
    checks: dict[str, bool] = {}

    checks["evidence_file_exists"] = evidence_path.exists() and evidence_path.is_file()
    if not checks["evidence_file_exists"]:
        failures.append(failure("missing_evidence_file", "evidence file must exist"))
    checks["evidence_file_nonempty"] = checks["evidence_file_exists"] and evidence_path.stat().st_size > 0
    if not checks["evidence_file_nonempty"]:
        failures.append(failure("empty_evidence_file", "evidence file must be non-empty"))

    metadata: dict[str, Any] | None = None
    checks["metadata_supplied"] = metadata_path is not None
    if not metadata_path:
        failures.append(failure("missing_metadata", "structural verifier requires runner metadata JSON"))
    elif not metadata_path.exists() or not metadata_path.is_file():
        failures.append(failure("missing_metadata_file", "metadata JSON file must exist"))
    else:
        try:
            loaded = json.loads(metadata_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            failures.append(failure("invalid_metadata_json", f"metadata JSON must parse: {exc.msg}"))
        else:
            if isinstance(loaded, dict):
                metadata = loaded
            else:
                failures.append(failure("metadata_not_object", "metadata JSON must be an object"))

    if metadata is not None:
        checks.update(check_metadata(metadata, use_case, client, session_id, expected_prompt_count, failures))

    return {
        "ok": not failures,
        "ok_scope": "deterministic structure only; no semantic judgment over generated prose",
        "requires_agent_evaluation": True,
        "client": client,
        "use_case": use_case,
        "evidence": str(evidence_path),
        "metadata": str(metadata_path) if metadata_path else "",
        "session_id": session_id or (str(metadata.get("session_id") or "") if metadata else ""),
        "checks": checks,
        "failures": failures,
        "semantic_evaluation_required": True,
        "semantic_criteria": semantic_criteria_for(use_case),
        "deterministic_boundary": (
            "This verifier checks artifact structure, command status, reset JSON shape, "
            "generation-report structure, and declared runner contract fields. It does not "
            "use matched strings, regexes, keywords, or string parsing to decide meaning."
        ),
    }


def check_metadata(
    metadata: dict[str, Any],
    use_case: str,
    client: str,
    session_id: str,
    expected_prompt_count: int | None,
    failures: list[dict[str, str]],
) -> dict[str, bool]:
    checks: dict[str, bool] = {}

    checks["metadata_client_matches"] = metadata.get("client") == client
    if not checks["metadata_client_matches"]:
        failures.append(failure("metadata_client_mismatch", "metadata client must match verifier client"))

    checks["metadata_use_case_matches"] = metadata.get("use_case") == use_case
    if not checks["metadata_use_case_matches"]:
        failures.append(failure("metadata_use_case_mismatch", "metadata use_case must match verifier use case"))

    metadata_session_id = metadata.get("session_id")
    checks["metadata_session_id_present"] = isinstance(metadata_session_id, str) and bool(metadata_session_id)
    if not checks["metadata_session_id_present"]:
        failures.append(failure("missing_session_id", "metadata must include a stable session id"))
    if session_id:
        checks["metadata_session_id_matches_arg"] = metadata_session_id == session_id
        if not checks["metadata_session_id_matches_arg"]:
            failures.append(failure("session_id_mismatch", "metadata session id must match supplied session id"))

    checks["semantic_acceptance_declared"] = metadata.get("semantic_acceptance") == "requires_agent_evaluation"
    if not checks["semantic_acceptance_declared"]:
        failures.append(failure("missing_semantic_acceptance_boundary", "metadata must declare evaluator-required semantic acceptance"))

    runner_contract = metadata.get("runner_contract")
    checks["runner_contract_object"] = isinstance(runner_contract, dict)
    if not isinstance(runner_contract, dict):
        failures.append(failure("missing_runner_contract", "metadata must include runner_contract object"))
    else:
        required_true = [
            "non_ephemeral_container",
            "reset_home_volume_requested",
            "virgin_workspace_reset_requested",
            "deterministic_checks_are_structural_only",
        ]
        for key in required_true:
            check_key = f"runner_contract_{key}"
            checks[check_key] = runner_contract.get(key) is True
            if not checks[check_key]:
                failures.append(failure(check_key, f"runner_contract.{key} must be true"))

    reset_json = metadata.get("reset_json")
    checks["reset_json_object"] = isinstance(reset_json, dict)
    if not isinstance(reset_json, dict):
        failures.append(failure("missing_reset_json", "metadata must include reset_json object"))
    else:
        checks["reset_ok_true"] = reset_json.get("ok") is True
        checks["reset_client_matches"] = reset_json.get("client") == client
        client_reset = reset_json.get("client_reset")
        workspace_reset = reset_json.get("workspace_reset")
        checks["client_reset_postcondition_true"] = isinstance(client_reset, dict) and client_reset.get("postcondition") is True
        checks["workspace_reset_postcondition_true"] = isinstance(workspace_reset, dict) and workspace_reset.get("postcondition") is True
        for key in (
            "reset_ok_true",
            "reset_client_matches",
            "client_reset_postcondition_true",
            "workspace_reset_postcondition_true",
        ):
            if not checks[key]:
                failures.append(failure(key, f"reset_json failed structural check {key}"))

    generation_report = metadata.get("generation_report")
    checks["generation_report_object"] = isinstance(generation_report, dict)
    if not isinstance(generation_report, dict):
        failures.append(failure("missing_generation_report", "metadata must include generation_report object"))
    else:
        checks.update(check_generation_report(generation_report, expected_prompt_count, failures))

    commands = metadata.get("commands")
    checks["commands_list"] = isinstance(commands, list) and bool(commands)
    if not checks["commands_list"]:
        failures.append(failure("missing_commands", "metadata must include a non-empty command ledger list"))
    elif isinstance(commands, list):
        for index, command in enumerate(commands, start=1):
            if not isinstance(command, dict):
                failures.append(failure("command_not_object", f"command ledger item {index} must be an object"))
                continue
            if not isinstance(command.get("returncode"), int):
                failures.append(failure("command_returncode_missing", f"command ledger item {index} must include integer returncode"))
            if not isinstance(command.get("timeout"), bool):
                failures.append(failure("command_timeout_missing", f"command ledger item {index} must include boolean timeout"))

    required_statuses = metadata.get("required_command_statuses")
    checks["required_command_statuses_object"] = isinstance(required_statuses, dict) and bool(required_statuses)
    if not checks["required_command_statuses_object"]:
        failures.append(failure("missing_required_command_statuses", "metadata must include required command status objects"))
    elif isinstance(required_statuses, dict):
        for name, status in required_statuses.items():
            if not isinstance(status, dict):
                failures.append(failure("required_status_not_object", f"required command status {name} must be an object"))
                continue
            if status.get("returncode") != 0:
                failures.append(failure("required_command_nonzero", f"required command {name} must have returncode 0"))
            if status.get("timeout") is not False:
                failures.append(failure("required_command_timeout", f"required command {name} must not time out"))

    semantic_criteria = metadata.get("semantic_criteria")
    checks["semantic_criteria_list"] = isinstance(semantic_criteria, list) and bool(semantic_criteria)
    if not checks["semantic_criteria_list"]:
        failures.append(failure("missing_semantic_criteria", "metadata must include semantic criteria for evaluator review"))

    return checks


def check_generation_report(
    generation_report: dict[str, Any],
    expected_prompt_count: int | None,
    failures: list[dict[str, str]],
) -> dict[str, bool]:
    checks: dict[str, bool] = {}
    checks["generation_report_model_dependent"] = generation_report.get("model_dependent") is True
    if not checks["generation_report_model_dependent"]:
        failures.append(failure("generation_report_not_model_dependent", "generation_report.model_dependent must be true"))
    steps = generation_report.get("step_generations")
    checks["step_generations_list"] = isinstance(steps, list) and bool(steps)
    if not checks["step_generations_list"]:
        failures.append(failure("missing_step_generations", "generation_report must include non-empty step_generations"))
    totals = generation_report.get("totals")
    checks["generation_totals_object"] = isinstance(totals, dict)
    if not isinstance(totals, dict):
        failures.append(failure("missing_generation_totals", "generation_report must include totals object"))
    else:
        prompt_count = totals.get("prompt_count")
        generation_step_count = totals.get("generation_step_count")
        checks["prompt_count_integer"] = isinstance(prompt_count, int) and prompt_count > 0
        checks["generation_step_count_integer"] = isinstance(generation_step_count, int) and generation_step_count > 0
        if not checks["prompt_count_integer"]:
            failures.append(failure("invalid_prompt_count", "generation_report.totals.prompt_count must be positive integer"))
        if not checks["generation_step_count_integer"]:
            failures.append(failure("invalid_generation_step_count", "generation_report.totals.generation_step_count must be positive integer"))
        if expected_prompt_count is not None:
            checks["prompt_count_matches_use_case"] = prompt_count == expected_prompt_count
            if not checks["prompt_count_matches_use_case"]:
                failures.append(failure("prompt_count_mismatch", "generation_report prompt count must match use case"))
    if isinstance(steps, list):
        for index, step in enumerate(steps, start=1):
            if not isinstance(step, dict):
                failures.append(failure("step_generation_not_object", f"step generation {index} must be an object"))
                continue
            if step.get("model_dependent") is not True:
                failures.append(failure("step_not_model_dependent", f"step generation {index} must declare model_dependent true"))
            if step.get("returncode") != 0:
                failures.append(failure("step_returncode_nonzero", f"step generation {index} must have returncode 0"))
            if step.get("timeout") is not False:
                failures.append(failure("step_timeout", f"step generation {index} must not time out"))
    return checks


def semantic_criteria_for(use_case: str) -> list[dict[str, str]]:
    shared = [
        {
            "id": "natural_user_prompts",
            "question": "Were the user prompts minimal, ordinary, and free of internal helper/tool coaching?",
        },
        {
            "id": "visible_reply_quality",
            "question": "Did the visible assistant replies naturally satisfy the localized user-facing story?",
        },
        {
            "id": "hidden_instruction_boundary",
            "question": "Did hidden/tool guidance remain hidden and avoid leaking into user-facing prose?",
        },
        {
            "id": "non_actions",
            "question": "Did the interaction avoid forbidden shortcuts, mutations, validation/probing, and overclaims?",
        },
    ]
    localized: dict[str, list[dict[str, str]]] = {
        "use-case-1": [
            {
                "id": "install_only_terminal_boundary",
                "question": "Did the flow end at installed plus reload/new-session-required, without post-install validation?",
            }
        ],
        "use-case-2": [
            {
                "id": "initialized_tool_availability",
                "question": "Did the assistant report available ContextForge tools for an initialized project without restarting onboarding?",
            }
        ],
        "use-case-3": [
            {
                "id": "initialized_capability_summary",
                "question": "Did the assistant summarize what it can do in the initialized project without restarting onboarding?",
            }
        ],
        "use-case-4": [
            {
                "id": "governance_read_only_answer",
                "question": "Did the assistant answer the governance question through the ContextForge-exposed mentality service without direct ledger-file substitutes or mutations?",
            }
        ],
        "use-case-7": [
            {
                "id": "project_state_readback_honesty",
                "question": "Did the assistant describe current ContextForge state and readiness layers without claiming interactive proof?",
            }
        ],
    }
    return shared + localized.get(use_case, [])


def failure(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}
