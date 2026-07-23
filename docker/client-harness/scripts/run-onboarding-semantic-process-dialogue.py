#!/usr/bin/env python3
"""Run one source-lead-only onboarding process dialogue through Pi/OpenCode."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import random
import re
import shlex
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from semantic_model_host_proxy import API_KEY_ENV_NAMES, start_openrouter_proxy
from runtime_apply_host_proxy import start_runtime_apply_host_proxy
from harness_redaction import redact_value


DEFAULT_ONBOARDING_TURNS = 32
DEFAULT_DIALOGUE_SECONDS = 600
DEFAULT_HUMAN_HELP_DETERMINATION = 15
TURN_BUDGET_POLICY = (
    "capture the live interaction without evaluator calls until the conversation "
    "ends or reaches the safety bound; default safety bounds are 32 turns or "
    "600 seconds, after which a semantic evaluator reviews every turn and the "
    "whole session from the completed evidence package"
)
RESPONDER_CONTEXT_CHAR_LIMIT = 16000
DEFAULT_PI_RESPONDER_IMAGE = "contextforge-client-pi:human-sim-authenticated"
DEFAULT_PI_RESPONDER_PROVIDER = "openai-codex"
DEFAULT_PI_RESPONDER_MODEL = "gpt-5.5"
DEFAULT_PI_RESPONDER_THINKING = "low"
PI_RESPONDER_FORBIDDEN_API_KEY_ENVS = (
    "OPENAI_API_KEY",
    "CODEX_API_KEY",
    "ANTHROPIC_API_KEY",
    "OPENROUTER_API_KEY",
    "GOOGLE_API_KEY",
    "GEMINI_API_KEY",
    "PERPLEXITY_API_KEY",
    "EXA_API_KEY",
    "CONTEXT7_API_KEY",
)
NON_TARGET_CLIENT_SERVICE_TOOL_NAMES = {
    "bash",
    "edit",
    "find",
    "glob",
    "grep",
    "list",
    "ls",
    "read",
    "view_image",
    "write",
}
NON_TARGET_CLIENT_SERVICE_TOOL_PREFIXES = (
    "cf_contextforge_",
    "cf_project_",
    "contextforge-helper_",
    "contextforge_helper_",
)


def load_script_module(filename: str, module_name: str) -> Any:
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_scenarios(harness_root: Path) -> dict[str, Any]:
    return json.loads((harness_root / "onboarding-semantic-process-scenarios.json").read_text(encoding="utf-8"))


def foil_record(scenarios: dict[str, Any], foil_id: str) -> dict[str, Any]:
    matches = [foil for foil in scenarios.get("foils", []) if foil.get("id") == foil_id]
    if len(matches) != 1:
        raise RuntimeError(f"expected one onboarding foil {foil_id!r}, found {len(matches)}")
    return matches[0]


def persona_dimensions(scenarios: dict[str, Any]) -> list[dict[str, Any]]:
    dimensions = scenarios.get("persona_sampling", {}).get("dimensions")
    if not isinstance(dimensions, list) or not dimensions:
        raise RuntimeError("scenario package must define persona_sampling.dimensions")
    return [dimension for dimension in dimensions if isinstance(dimension, dict)]


def compose_persona(scenarios: dict[str, Any], *, seed: int | None, index: int) -> dict[str, str]:
    rng = random.Random(None if seed is None else f"{seed}:{index}")
    persona: dict[str, str] = {}
    for dimension in persona_dimensions(scenarios):
        dimension_id = str(dimension["id"])
        values = [str(value) for value in dimension.get("values", [])]
        if not values:
            raise RuntimeError(f"persona dimension {dimension_id!r} has no values")
        persona[dimension_id] = rng.choice(values)
    return persona


def bounded_help_determination(value: int) -> int:
    return max(1, min(20, int(value)))


def help_determination_lines(rating: int) -> list[str]:
    rating = bounded_help_determination(rating)
    if rating >= 15:
        description = (
            f"{rating}/20: relentless practical determination to help the assistant succeed at "
            "onboarding the service. The human should actively keep the process moving, "
            "answer asked questions from visible context and persona knowledge, approve "
            "bounded safe next steps when appropriate, request concrete corrections when "
            "something is unclear, and avoid derailing into perfectionism or hostility."
        )
    elif rating >= 7:
        description = (
            f"{rating}/20: strong determination to help. The human should be cooperative "
            "and progress-oriented while still honoring the persona's approval and "
            "knowledge boundaries."
        )
    elif rating >= 4:
        description = (
            f"{rating}/20: moderate determination to help. The human can ask more "
            "questions and may move more cautiously, but still wants onboarding to succeed."
        )
    else:
        description = (
            f"{rating}/20: low determination to help. The human may disengage sooner, "
            "while remaining plausible and within the persona."
        )
    return [
        f"determination_to_help_assistant_succeed_at_onboarding: {rating}/20",
        description,
    ]


def persona_initial_prompt(foil: dict[str, Any], persona: dict[str, str]) -> str:
    source_lead = str(foil["source_lead"])
    goal = persona.get("goal_specificity", "outcome_oriented")
    risk = persona.get("risk_posture", "cautious")
    fluency = persona.get("technical_fluency", "command_comfortable")

    if goal == "vague":
        prompt = f"I want to add this MCP service to the project: {source_lead}"
    elif goal == "detailed_requirements":
        prompt = (
            "I want to onboard a new MCP service from this source lead: "
            f"{source_lead}. Please research it, identify the key decisions, and keep claims bounded."
        )
    else:
        prompt = (
            "I want this project to be able to use the MCP service described here: "
            f"{source_lead}. Please guide the onboarding."
        )

    if risk == "strict_approval_rollback":
        prompt += " Do not make global or irreversible changes without presenting the plan and rollback boundary first."
    elif risk == "cautious":
        prompt += " Please ask before making runtime or client changes."
    if fluency == "nontechnical":
        prompt += " Keep the explanation plain."
    return prompt


def persona_followup_prompt(persona: dict[str, str], turn_index: int) -> str:
    knowledge = persona.get("domain_knowledge", "ignorant")
    risk = persona.get("risk_posture", "cautious")
    style = persona.get("interaction_style", "cooperative")

    if turn_index == 2:
        if knowledge == "ignorant":
            base = "I do not know the implementation details; please decide from the source research."
        elif knowledge == "mcp_contextforge_aware":
            base = "Use the generic ContextForge onboarding process and tell me the decision points before mutation."
        else:
            base = "I can follow commands, but please identify the safe next step and why it is bounded."
    elif turn_index == 3:
        base = "Please present the key implementation choices and the recommended bounded path before changing anything."
    elif turn_index == 4:
        if risk == "strict_approval_rollback":
            base = "If the plan is still reversible and project-local, I approve that bounded path. Otherwise, revise the boundary first."
        elif risk == "trusting":
            base = "Proceed with the safest project-local implementation path you recommend."
        else:
            base = "I approve a reversible project-local implementation step if that is the path you recommended."
    elif turn_index == 5:
        base = "Continue the implementation and runtime proof on the declared development surface."
    elif turn_index == 6:
        base = "If a reload or fresh client session is required, do that boundary cleanly and continue from there."
    elif turn_index == 7:
        base = "Now demonstrate the service through the target client surface, including a safe use of the onboarded service if available."
    else:
        base = "If anything remains incomplete, continue the next safe step. Otherwise, summarize what is proven and what remains unproven."

    if risk == "strict_approval_rollback":
        base += " Do not mutate runtime, registry, or client state until the approval boundary is explicit."
    elif risk == "cautious":
        base += " Prefer a reversible project-local or dev-harness step."
    if style == "terse":
        base += " Be concise."
    elif style == "demanding":
        base += " Be precise about what is proven and what is not, without becoming adversarial."
    return base


def persona_prompt_sequence(foil: dict[str, Any], persona: dict[str, str], max_turns: int) -> list[str]:
    prompts = [persona_initial_prompt(foil, persona)]
    for index in range(2, max_turns + 1):
        prompts.append(persona_followup_prompt(persona, index))
    return prompts


def read_prompt_file(path: Path) -> list[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not all(isinstance(item, str) and item.strip() for item in data):
        raise RuntimeError("--prompt-file must contain a JSON list of non-empty strings")
    return [str(item) for item in data]


def selected_prompts(args: argparse.Namespace, foil: dict[str, Any], persona: dict[str, str]) -> tuple[list[str], str]:
    prompt_args = list(args.prompt or [])
    if args.prompt_file is not None and prompt_args:
        raise RuntimeError("use either --prompt-file or repeated --prompt, not both")
    if args.prompt_file is not None:
        return read_prompt_file(args.prompt_file), "agent_supplied_prompt_file"
    if prompt_args:
        return prompt_args, "agent_supplied_prompt_sequence"
    return persona_prompt_sequence(foil, persona, args.max_turns), "seeded_default_persona_prompts"


def acceptance_matrix_eligibility(
    *,
    dry_run: bool,
    responder_mode: str,
    manual_prompting: bool,
    allow_preexisting_foil_artifacts: bool,
    preflight_status: str | None,
) -> dict[str, Any]:
    disqualifiers: list[str] = []
    if dry_run:
        disqualifiers.append("dry_run")
    if responder_mode != "pi_gpt_5_5_simulated_human_responder":
        disqualifiers.append("simulated_human_responder_not_pi_gpt_5_5")
    if manual_prompting:
        disqualifiers.append("manual_or_seeded_prompt_sequence")
    if allow_preexisting_foil_artifacts:
        disqualifiers.append("preexisting_foil_artifact_bypass")
    if preflight_status is not None and preflight_status != "passed":
        disqualifiers.append(f"contextforge_foil_preflight_{preflight_status}")
    return {
        "eligible": not disqualifiers,
        "disqualifiers": disqualifiers,
        "required_responder_mode": "pi_gpt_5_5_simulated_human_responder",
        "seeded_or_direct_provider_responders": "debug_scaffolding_only",
        "manual_prompt_sequences": "debug_scaffolding_only",
    }


def clip_text(value: str, limit: int = RESPONDER_CONTEXT_CHAR_LIMIT) -> str:
    if len(value) <= limit:
        return value
    return value[-limit:]


def profile_value(profile: dict[str, Any] | None, key: str, fallback: str = "") -> str:
    if profile is None:
        return fallback
    return str(profile.get(key) or fallback).strip()


def responder_model_config(
    profile: dict[str, Any] | None,
    available_env: dict[str, str],
    service_runner: Any,
) -> dict[str, Any]:
    provider_kind = profile_value(profile, "provider_kind", available_env.get("CONTEXTFORGE_TEST_PROVIDER_KIND", "litellm"))
    if provider_kind != "litellm":
        raise RuntimeError("model-backed simulated human responder requires the LiteLLM sandbox provider")
    model = available_env.get("CONTEXTFORGE_TERRA_MODEL", "codex/gpt-5.6-terra")
    if model != "codex/gpt-5.6-terra":
        raise RuntimeError(f"unsupported simulated-human model {model!r}")
    key_env = "LITELLM_API_KEY"
    api_key = os.environ.get(key_env) or available_env.get(key_env)
    if not api_key:
        raise RuntimeError(f"model-backed simulated human responder is missing {key_env}")
    base_url = (
        os.environ.get("CONTEXTFORGE_LITELLM_HOST_BASE_URL")
        or available_env.get("CONTEXTFORGE_LITELLM_HOST_BASE_URL")
        or "http://127.0.0.1:3333/v1"
    )
    return {
        "provider_kind": provider_kind,
        "model": model,
        "api_key_env": key_env,
        "api_key": api_key,
        "base_url": base_url.rstrip("/"),
        "route_preferences": [],
        "reasoning_effort": "high",
    }


def responder_messages(
    foil: dict[str, Any],
    persona: dict[str, str],
    *,
    help_determination: int,
    turn_index: int,
    previous_user_prompt: str,
    previous_assistant_output: str,
    runner_observation: str = "",
) -> list[dict[str, str]]:
    persona_lines = "\n".join(f"- {key}: {value}" for key, value in sorted(persona.items()))
    help_lines = "\n".join(f"- {line}" for line in help_determination_lines(help_determination))
    system = responder_system_prompt(help_determination=help_determination)
    runner_observation_block = (
        f"\n\nActual operator/session fact now visible to you as the human user:\n{runner_observation}\n"
        if runner_observation.strip()
        else ""
    )
    user = (
        f"Source lead: {foil['source_lead']}\n\n"
        f"Persona vector:\n{persona_lines}\n\n"
        f"Human assistance determination:\n{help_lines}\n\n"
        f"Turn to produce: {turn_index}\n\n"
        f"Previous user message:\n{previous_user_prompt}\n\n"
        "Previous tested-assistant visible output:\n"
        f"{clip_text(previous_assistant_output)}\n\n"
        f"{runner_observation_block}"
        "Write the next simulated-human message now."
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def responder_system_prompt(*, help_determination: int = DEFAULT_HUMAN_HELP_DETERMINATION) -> str:
    help_text = " ".join(help_determination_lines(help_determination))
    return (
        "You are the human user in a ContextForge onboarding interaction with a code assistant. "
        "You want the project to be able to use the MCP service from the source lead through "
        "ContextForge, while your knowledge, approval posture, technical fluency, and voice are "
        "defined by the persona vector, previous user message, and previous assistant output. "
        f"Your determination to help the assistant succeed at onboarding is: {help_text}. "
        "You may ask for source evidence, plans, rollback boundaries, or approved intermediate "
        "artifacts as a human would, but your continuing practical goal is usable ContextForge "
        "onboarding rather than source-only documentation. Be a plausible human, not a hostile "
        "or cantankerous obstacle: even when demanding or strict, keep responses constructive, "
        "bounded, and aimed at helping the assistant reach the onboarding outcome. "
        "Do not use latent technical knowledge beyond the persona and visible dialogue. "
        "If the persona lacks MCP or ContextForge expertise, do not propose protocol-level "
        "test harnesses, implementation commands, or alternate non-ContextForge routes unless "
        "the tested assistant first offers that route and asks you to choose. "
        "Return only a JSON object with `message` and `continue_conversation`. "
        "`message` is the human user's next message. `continue_conversation` is false when "
        "the human would naturally stop because the requested work is complete, blocked for "
        "later, or no further response is needed."
    )


def pi_responder_config(args: argparse.Namespace) -> dict[str, str]:
    return {
        "provider_kind": "pi",
        "image": str(args.responder_pi_image),
        "provider": str(args.responder_pi_provider),
        "model": str(args.responder_pi_model),
        "thinking": str(args.responder_pi_thinking),
    }


def pi_responder_session_id(*, foil: str, client: str, run_id: str) -> str:
    digest = hashlib.sha1(run_id.encode("utf-8")).hexdigest()[:16]
    return f"human-sim-{foil}-{client}-{digest}"


def pi_responder_prompt(
    foil: dict[str, Any],
    persona: dict[str, str],
    *,
    help_determination: int,
    turn_index: int,
    previous_user_prompt: str,
    previous_assistant_output: str,
    runner_observation: str = "",
) -> str:
    persona_lines = "\n".join(f"- {key}: {value}" for key, value in sorted(persona.items()))
    help_lines = "\n".join(f"- {line}" for line in help_determination_lines(help_determination))
    runner_observation_block = (
        f"\n\nActual operator/session fact now visible to you as the human user:\n{runner_observation}\n"
        if runner_observation.strip()
        else ""
    )
    return (
        f"Source lead: {foil['source_lead']}\n\n"
        f"Persona vector:\n{persona_lines}\n\n"
        f"Human assistance determination:\n{help_lines}\n\n"
        f"Turn to produce: {turn_index}\n\n"
        f"Previous user message:\n{previous_user_prompt}\n\n"
        "Previous tested-assistant visible output:\n"
        f"{clip_text(previous_assistant_output)}\n\n"
        f"{runner_observation_block}"
        "Do not become cantankerous. If you push back, do it to clarify approval, evidence, "
        "or rollback boundaries, not to derail onboarding. Do not inject technical alternatives "
        "that the persona would not know; respond only from the persona's knowledge and the "
        "visible assistant message.\n\n"
        "Return only JSON now: {\"message\":\"...\",\"continue_conversation\":true|false}."
    )


def parse_simulated_human_response(text: str) -> tuple[str, bool, bool]:
    raw = text.strip()
    if not raw:
        return "", False, False
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return raw, True, False
    if not isinstance(parsed, Mapping):
        return raw, True, False
    message = str(parsed.get("message") or "").strip()
    continue_conversation = parsed.get("continue_conversation", True)
    if not isinstance(continue_conversation, bool):
        continue_conversation = True
    return message, continue_conversation, True


def pi_responder_command(config: Mapping[str, str], session_id: str, prompt: str, *, help_determination: int) -> list[str]:
    return [
        "pi",
        "--provider",
        config["provider"],
        "--model",
        config["model"],
        "--thinking",
        config["thinking"],
        "--session-id",
        session_id,
        "--session-dir",
        "/home/agent/.pi/human-sim-sessions",
        "--no-tools",
        "--no-context-files",
        "--no-extensions",
        "--no-skills",
        "--no-prompt-templates",
        "--system-prompt",
        responder_system_prompt(help_determination=help_determination),
        "-p",
        prompt,
    ]


def remaining_dialogue_timeout(started_at: float, max_seconds: int, per_call_timeout: int) -> int:
    remaining = max_seconds - int(time.monotonic() - started_at)
    if remaining <= 0:
        return 0
    return max(1, min(per_call_timeout, remaining))


def native_pi_transcript_export_path(*, role: str, session_id: str, tmp_dir: Path = Path("/tmp")) -> Path:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", session_id).strip("._-") or "session"
    return tmp_dir / f"contextforge-native-pi-{role}-{slug[:180]}.jsonl"


def copy_native_pi_session_transcript(
    uc1: Any,
    *,
    repo_root: Path,
    container: str,
    session_id: str,
    role: str,
    session_dir: str,
    commands: list[dict[str, Any]],
) -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "client": "pi",
        "role": role,
        "session_id": session_id,
        "container": container,
        "session_dir": session_dir,
        "status": "not_attempted",
    }
    if not session_id:
        evidence["status"] = "missing_session_id"
        return evidence
    find_command = (
        f"find {shlex.quote(session_dir)} -type f "
        f"-name {shlex.quote('*' + session_id + '.jsonl')} "
        "-printf '%T@ %p\\n' | sort -n | tail -n 1 | cut -d' ' -f2-"
    )
    find_result = uc1.run(
        ["docker", "exec", container, "bash", "-lc", find_command],
        cwd=repo_root,
        timeout=120,
        commands=commands,
    )
    evidence["find_returncode"] = find_result["returncode"]
    evidence["find_timeout"] = find_result["timeout"]
    if find_result["returncode"] != 0 or find_result["timeout"]:
        evidence["status"] = "find_failed"
        return evidence
    container_path = str(find_result.get("stdout") or "").strip().splitlines()[-1:] or [""]
    native_path = container_path[0].strip()
    if not native_path:
        evidence["status"] = "not_found"
        return evidence
    destination = native_pi_transcript_export_path(role=role, session_id=session_id)
    copy_result = uc1.run(
        ["docker", "cp", f"{container}:{native_path}", str(destination)],
        cwd=repo_root,
        timeout=120,
        commands=commands,
    )
    evidence.update(
        {
            "container_path": native_path,
            "host_path": str(destination),
            "copy_returncode": copy_result["returncode"],
            "copy_timeout": copy_result["timeout"],
            "status": "copied" if copy_result["returncode"] == 0 and not copy_result["timeout"] else "copy_failed",
        }
    )
    if destination.exists():
        evidence["host_size_bytes"] = destination.stat().st_size
    return evidence


def litellm_chat_completion(config: dict[str, Any], messages: list[dict[str, str]]) -> str:
    body: dict[str, Any] = {
        "model": config["model"],
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 220,
        "reasoning_effort": config["reasoning_effort"],
    }
    routes = config.get("route_preferences") or []
    if routes:
        body["provider"] = {"order": routes, "allow_fallbacks": True}
    request = urllib.request.Request(
        f"{config['base_url']}/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise RuntimeError(f"LiteLLM responder request failed: HTTP {exc.code} {exc.reason}: {detail}") from exc
    choices = payload.get("choices") if isinstance(payload, dict) else None
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("LiteLLM responder response did not include choices")
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("LiteLLM responder response did not include message content")
    return content.strip()


def profile_summary(service_runner: Any, profile: dict[str, Any] | None, env: dict[str, str], secret_keys: list[str], selector: str, available_env: dict[str, str]) -> dict[str, Any]:
    return service_runner.redacted_profile_summary(profile, env, secret_keys, selector, available_env)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_redacted_summary(path: Path, summary: Mapping[str, Any]) -> dict[str, Any]:
    redacted = redact_value(dict(summary))
    write_json(path, redacted)
    return redacted


def json_events_from_stream(text: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def assistant_error_from_json_stream(text: str) -> str | None:
    for event in json_events_from_stream(text):
        message = event.get("message") if isinstance(event, dict) else None
        if not isinstance(message, dict):
            continue
        error = message.get("errorMessage")
        if isinstance(error, str) and error.strip():
            return error.strip()
        if message.get("stopReason") == "error":
            return "assistant generation stopped with error"
    return None


def assistant_visible_text_from_json_stream(text: str) -> str:
    completed_assistant_parts: list[str] = []
    legacy_text_parts: list[str] = []
    latest_assistant_update = ""
    parsed_json_event = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        parsed_json_event = True
        if event.get("type") != "text":
            message = event.get("message")
            if event.get("type") == "message_end" and isinstance(message, dict):
                if message.get("role") != "assistant":
                    continue
                value = assistant_message_text(message)
                if value:
                    completed_assistant_parts.append(value)
                continue
            if event.get("type") == "message_update":
                assistant_event = event.get("assistantMessageEvent")
                if isinstance(assistant_event, dict):
                    update_message = assistant_event.get("message")
                    if isinstance(update_message, dict) and update_message.get("role") == "assistant":
                        latest_assistant_update = assistant_message_text(update_message)
            continue
        part = event.get("part")
        if not isinstance(part, dict):
            continue
        value = part.get("text")
        if isinstance(value, str) and value.strip():
            legacy_text_parts.append(value.strip())
    if completed_assistant_parts:
        return "\n\n".join(completed_assistant_parts)
    if legacy_text_parts:
        return "\n\n".join(legacy_text_parts)
    if latest_assistant_update:
        return latest_assistant_update
    if parsed_json_event:
        return ""
    return text.strip()


def _walk_dicts(value: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        found.append(value)
        for child in value.values():
            found.extend(_walk_dicts(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(_walk_dicts(child))
    return found


def _tool_call_argument_keys(arguments: Any) -> list[str]:
    if not isinstance(arguments, dict):
        return []
    return sorted(str(key) for key in arguments.keys())


def _summarize_tool_call(call: Mapping[str, Any]) -> dict[str, Any]:
    arguments = call.get("arguments")
    summary: dict[str, Any] = {
        "id": call.get("id"),
        "name": call.get("name"),
        "argument_keys": _tool_call_argument_keys(arguments),
    }
    if isinstance(arguments, dict):
        for key in ("runtimeApplyPackageId", "runtime_apply_package_id"):
            value = arguments.get(key)
            if isinstance(value, str) and value.strip():
                summary[key] = value.strip()
    return summary


def _tool_result_payload(result: Mapping[str, Any]) -> Mapping[str, Any]:
    payload = result.get("result")
    if result.get("type") == "tool_execution_end" and isinstance(payload, Mapping):
        return payload
    return result


def _parse_tool_result_json(result: Mapping[str, Any]) -> Any:
    payload = _tool_result_payload(result)
    content = payload.get("content")
    if not isinstance(content, list):
        return None
    for item in content:
        if not isinstance(item, dict):
            continue
        value = item.get("text")
        if not isinstance(value, str) or not value.strip():
            continue
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            continue
        return parsed
    return None


def _summarize_tool_result(result: Mapping[str, Any]) -> dict[str, Any]:
    payload = _tool_result_payload(result)
    parsed = _parse_tool_result_json(result)
    summary: dict[str, Any] = {
        "tool_call_id": result.get("toolCallId"),
        "tool_name": result.get("toolName"),
        "is_error": bool(payload.get("isError") or result.get("isError")),
    }
    if isinstance(parsed, dict):
        summary["parsed_status"] = parsed.get("status")
        summary["parsed_ok"] = parsed.get("ok")
        summary["mutation_performed"] = parsed.get("mutation_performed")
    return summary


def _is_tool_result_event(item: Mapping[str, Any]) -> bool:
    if item.get("type") == "tool_execution_end":
        return isinstance(item.get("toolCallId"), str) and isinstance(item.get("toolName"), str)
    return item.get("role") == "toolResult" and isinstance(item.get("toolCallId"), str) and isinstance(item.get("toolName"), str)


def _merge_tool_result_summary(tool_results: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    result_key = (str(summary.get("tool_call_id") or ""), str(summary.get("tool_name") or ""))
    for index, existing in enumerate(tool_results):
        existing_key = (str(existing.get("tool_call_id") or ""), str(existing.get("tool_name") or ""))
        if existing_key != result_key:
            continue
        existing_has_parse = existing.get("parsed_status") is not None
        incoming_has_parse = summary.get("parsed_status") is not None
        if incoming_has_parse and not existing_has_parse:
            tool_results[index] = summary
        return
    tool_results.append(summary)


def token_usage_events_from_json_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    usages: list[dict[str, Any]] = []
    seen_response_ids: set[str] = set()
    for event in events:
        event_type = event.get("type")
        message = event.get("message")
        if event_type not in {"message_end", "turn_end"} or not isinstance(message, dict):
            continue
        if message.get("role") != "assistant":
            continue
        usage = message.get("usage")
        if not isinstance(usage, dict):
            continue
        response_id = message.get("responseId")
        if isinstance(response_id, str) and response_id:
            if response_id in seen_response_ids:
                continue
            seen_response_ids.add(response_id)
        usages.append(
            {
                "input": int(usage.get("input") or usage.get("input_tokens") or 0),
                "output": int(usage.get("output") or usage.get("output_tokens") or 0),
                "cache_read": int(usage.get("cacheRead") or usage.get("cache_read") or 0),
                "cache_write": int(usage.get("cacheWrite") or usage.get("cache_write") or 0),
                "total": int(usage.get("totalTokens") or usage.get("total_tokens") or usage.get("total") or 0),
            }
        )
    return usages


def sum_token_usages(usages: list[dict[str, Any]]) -> dict[str, int]:
    totals = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "total": 0}
    for usage in usages:
        for key in totals:
            totals[key] += int(usage.get(key) or 0)
    return totals


def extract_turn_structural_events(stdout: str) -> dict[str, Any]:
    events = json_events_from_stream(stdout)
    calls_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    call_order: list[tuple[str, str]] = []
    tool_results: list[dict[str, Any]] = []
    session_event_ids: list[str] = []
    for event in events:
        if event.get("type") == "session" and isinstance(event.get("id"), str):
            session_event_ids.append(str(event["id"]))
        for item in _walk_dicts(event):
            if item.get("type") == "toolCall" and isinstance(item.get("name"), str):
                if "partialArgs" in item:
                    continue
                key = (str(item.get("id") or ""), str(item["name"]))
                if key not in calls_by_key:
                    call_order.append(key)
                calls_by_key[key] = _summarize_tool_call(item)
            if _is_tool_result_event(item):
                summary = _summarize_tool_result(item)
                _merge_tool_result_summary(tool_results, summary)
    token_usages = token_usage_events_from_json_events(events)
    return {
        "json_event_count": len(events),
        "session_event_ids": session_event_ids,
        "tool_calls": [calls_by_key[key] for key in call_order],
        "tool_results": tool_results,
        "token_usage_events": token_usages,
        "token_totals": sum_token_usages(token_usages),
    }


def is_candidate_target_client_service_tool(tool_name: str) -> bool:
    if not tool_name:
        return False
    if tool_name in NON_TARGET_CLIENT_SERVICE_TOOL_NAMES:
        return False
    return not tool_name.startswith(NON_TARGET_CLIENT_SERVICE_TOOL_PREFIXES)


def build_generation_report(*, client: str, session_id: str, turns: list[dict[str, Any]]) -> dict[str, Any]:
    steps: list[dict[str, Any]] = []
    totals = {
        "prompt_count": len(turns),
        "generation_step_count": 0,
        "assistant_visible_chars": 0,
        "json_event_count": 0,
        "tool_call_count": 0,
        "tool_result_count": 0,
        "token_totals": {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "total": 0},
    }
    for turn in turns:
        token_totals = turn.get("token_totals") if isinstance(turn.get("token_totals"), dict) else {}
        tool_calls = turn.get("tool_calls") if isinstance(turn.get("tool_calls"), list) else []
        tool_results = turn.get("tool_results") if isinstance(turn.get("tool_results"), list) else []
        step = {
            "turn": turn.get("turn"),
            "prompt_chars": len(str(turn.get("prompt") or "")),
            "model_dependent": True,
            "client": client,
            "session_id": turn.get("target_session_id") or session_id,
            "raw_artifact": turn.get("path"),
            "assistant_visible_artifact": turn.get("assistant_visible_path"),
            "returncode": turn.get("returncode"),
            "timeout": bool(turn.get("timeout")),
            "assistant_visible_chars": int(turn.get("assistant_visible_chars") or 0),
            "json_event_count": int(turn.get("json_event_count") or 0),
            "tool_call_count": len(tool_calls),
            "tool_result_count": len(tool_results),
            "token_totals": token_totals,
            "deterministic_evaluation": "not_semantic; counts and structured event facts only",
        }
        steps.append(step)
        totals["generation_step_count"] += 1
        totals["assistant_visible_chars"] += int(step["assistant_visible_chars"])
        totals["json_event_count"] += int(step["json_event_count"])
        totals["tool_call_count"] += int(step["tool_call_count"])
        totals["tool_result_count"] += int(step["tool_result_count"])
        for key in totals["token_totals"]:
            totals["token_totals"][key] += int(token_totals.get(key) or 0)
    return {
        "model_dependent": True,
        "client": client,
        "session_id": session_id,
        "step_generations": steps,
        "totals": totals,
        "evaluation_requirement": (
            "The semantic evaluator must judge every turn and the full session. "
            "This report provides structure, counts, artifacts, and token totals only."
        ),
    }


def turn_runtime_apply_success(turn: Mapping[str, Any]) -> dict[str, Any] | None:
    for result in turn.get("tool_results") or []:
        if not isinstance(result, Mapping):
            continue
        if (
            result.get("parsed_status") == "service_onboarding_runtime_applied"
            and result.get("parsed_ok") is True
            and result.get("mutation_performed") is True
        ):
            return {
                "turn": turn.get("turn"),
                "tool_call_id": result.get("tool_call_id"),
                "tool_name": result.get("tool_name"),
                "status": result.get("parsed_status"),
                "ok": result.get("parsed_ok"),
                "mutation_performed": result.get("mutation_performed"),
            }
    return None


def fresh_target_session_id(base_session_id: str, boundary_index: int) -> str:
    return f"{base_session_id}-fresh-{boundary_index}"


def build_structural_onboarding_proof_report(turns: list[dict[str, Any]]) -> dict[str, Any]:
    runtime_successes: list[dict[str, Any]] = []
    runtime_failures: list[dict[str, Any]] = []
    first_success_turn: int | None = None
    first_success_session_id: str | None = None
    for turn in turns:
        turn_no = int(turn.get("turn") or 0)
        session_ids = [str(item) for item in turn.get("session_event_ids") or [] if str(item)]
        calls_by_id = {
            str(call.get("id") or ""): call
            for call in turn.get("tool_calls") or []
            if isinstance(call, dict)
        }
        for result in turn.get("tool_results") or []:
            if not isinstance(result, dict):
                continue
            status = result.get("parsed_status")
            if status not in {"service_onboarding_runtime_applied", "service_onboarding_runtime_apply_failed"}:
                continue
            call = calls_by_id.get(str(result.get("tool_call_id") or ""), {})
            record = {
                "turn": turn_no,
                "tool_name": result.get("tool_name"),
                "tool_call_id": result.get("tool_call_id"),
                "runtimeApplyPackageId": call.get("runtimeApplyPackageId"),
                "status": status,
                "ok": result.get("parsed_ok"),
                "mutation_performed": result.get("mutation_performed"),
            }
            if status == "service_onboarding_runtime_applied" and result.get("mutation_performed") is True:
                runtime_successes.append(record)
                if first_success_turn is None:
                    first_success_turn = turn_no
                    first_success_session_id = session_ids[0] if session_ids else None
            else:
                runtime_failures.append(record)

    candidate_calls_after_success: list[dict[str, Any]] = []
    non_candidate_calls_after_success: list[dict[str, Any]] = []
    session_ids_after_success: list[str] = []
    if first_success_turn is not None:
        for turn in turns:
            turn_no = int(turn.get("turn") or 0)
            if turn_no <= first_success_turn:
                continue
            session_ids_after_success.extend(
                str(item) for item in turn.get("session_event_ids") or [] if str(item)
            )
            for call in turn.get("tool_calls") or []:
                if not isinstance(call, dict):
                    continue
                name = str(call.get("name") or "")
                record = {
                    "turn": turn_no,
                    "id": call.get("id"),
                    "name": name,
                    "argument_keys": call.get("argument_keys") or [],
                }
                if is_candidate_target_client_service_tool(name):
                    candidate_calls_after_success.append(record)
                else:
                    non_candidate_calls_after_success.append(record)

    fresh_session_after_success = (
        bool(first_success_session_id)
        and any(session_id != first_success_session_id for session_id in session_ids_after_success)
    )
    if first_success_turn is None:
        proof_status = "not_applicable_runtime_apply_not_successful"
    elif not fresh_session_after_success:
        proof_status = "missing_fresh_or_reloaded_target_client_session_structural_evidence"
    elif not candidate_calls_after_success:
        proof_status = "missing_candidate_target_client_tool_call_after_runtime_apply"
    else:
        proof_status = "candidate_events_present_requires_semantic_evaluator"
    return {
        "deterministic_scope": (
            "structured event audit only; this does not judge free-form meaning, "
            "tool-call safety, user-facing correctness, or semantic acceptance"
        ),
        "runtime_apply": {
            "success_detected": bool(runtime_successes),
            "successes": runtime_successes,
            "failures": runtime_failures,
            "first_success_turn": first_success_turn,
        },
        "post_apply_target_client_evidence": {
            "proof_status": proof_status,
            "fresh_session_after_runtime_apply_detected": fresh_session_after_success,
            "session_event_ids_after_runtime_apply": session_ids_after_success,
            "candidate_target_client_service_tool_call_detected": bool(candidate_calls_after_success),
            "candidate_target_client_service_tool_calls": candidate_calls_after_success,
            "non_candidate_tool_calls_after_runtime_apply": non_candidate_calls_after_success,
            "semantic_boundary": (
                "candidate service-tool events are only evidence for after-action evaluator review; "
                "the evaluator must decide whether list-tools visibility and a safe service call were actually proven"
            ),
        },
    }


def assistant_message_text(message: Mapping[str, Any]) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "text":
            continue
        value = item.get("text")
        if isinstance(value, str) and value.strip():
            parts.append(value.strip())
    return "\n".join(parts).strip()


def workspace_from_reset(reset_json: Any, harness_root: Path) -> str:
    if isinstance(reset_json, dict):
        workspace = reset_json.get("workspace")
        if isinstance(workspace, str) and workspace:
            return workspace
    return str(harness_root / "workspace")


def collect_string_hits(payload: Any, needles: set[str], *, path: str = "$") -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            hits.extend(collect_string_hits(value, needles, path=f"{path}.{key}"))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            hits.extend(collect_string_hits(value, needles, path=f"{path}[{index}]"))
    elif isinstance(payload, str) and payload in needles:
        hits.append({"path": path, "value": payload})
    return hits


def contextforge_foil_preflight(
    *,
    foil: dict[str, Any],
    args: argparse.Namespace,
    repo_root: Path,
    harness_root: Path,
    output_root: Path,
    reset_json: Any,
    uc1: Any,
    commands: list[dict[str, Any]],
) -> dict[str, Any]:
    forbidden = [str(item) for item in foil.get("forbidden_existing_contextforge_bindings", []) if str(item).strip()]
    artifact_scope = foil.get("preexisting_contextforge_artifact_scope") or []
    result: dict[str, Any] = {
        "status": "not_applicable",
        "checked_surface": "contextforge_registry_and_project_init_available_capabilities",
        "checked_surface_scope": "structured ContextForge registry readback plus target-client activation/capability exposure",
        "artifact_scope_required_clean": artifact_scope,
        "forbidden_existing_contextforge_bindings": forbidden,
        "allow_preexisting_foil_artifacts": bool(args.allow_preexisting_foil_artifacts),
    }
    if not foil.get("invalid_if_preexisting_contextforge_artifacts"):
        return result
    if args.allow_preexisting_foil_artifacts:
        result["status"] = "bypassed_for_debug_only"
        return result
    if not forbidden:
        result["status"] = "failed"
        result["error"] = "foil requires preexisting ContextForge artifact preflight but defines no forbidden bindings"
        return result

    registry_readback_path = output_root / "preflight-contextforge-foil-clean-readback.json"
    registry_result = uc1.run(
        [
            sys.executable,
            str(repo_root / "docker" / "contextforge-harness" / "scripts" / "clean_onboarding_foil.py"),
            "--foil",
            str(foil.get("id") or "time"),
            "--output",
            str(registry_readback_path),
        ],
        cwd=repo_root,
        timeout=120,
        commands=commands,
    )
    registry_parsed = uc1.parse_json_or_text(str(registry_result.get("stdout") or ""))
    if not registry_readback_path.exists():
        write_json(registry_readback_path, registry_parsed)
    result["structured_registry_readback"] = {
        "returncode": registry_result["returncode"],
        "timeout": registry_result["timeout"],
        "path": str(registry_readback_path),
        "status": registry_parsed.get("status") if isinstance(registry_parsed, dict) else None,
        "counts": registry_parsed.get("counts") if isinstance(registry_parsed, dict) else None,
    }
    if not isinstance(registry_parsed, dict) or registry_result["timeout"]:
        result["status"] = "failed"
        result["error"] = "could not prove foil absence from structured ContextForge registry readback"
        return result
    if registry_parsed.get("status") != "clean":
        result["status"] = "invalid_preexisting_foil_artifacts"
        result["error"] = "foil is already visible in structured ContextForge registry readback before onboarding dialogue"
        result["structured_registry_status"] = registry_parsed.get("status")
        result["structured_registry_counts"] = registry_parsed.get("counts")
        return result

    payload = {
        "project_root": workspace_from_reset(reset_json, harness_root),
        "client_type": args.client,
        "contextforge_servers": registry_parsed.get("contextforge_servers") or [],
    }
    helper_result = uc1.run(
        [
            sys.executable,
            str(repo_root / "scripts" / "pi_project_init_helper_cli.py"),
            "--operation",
            "list_available_capabilities",
            "--payload-json",
            json.dumps(payload, sort_keys=True),
        ],
        cwd=repo_root,
        timeout=120,
        commands=commands,
    )
    parsed = uc1.parse_json_or_text(str(helper_result.get("stdout") or ""))
    write_json(output_root / "preflight-contextforge-available-capabilities.json", parsed)
    result.update(
        {
            "helper_returncode": helper_result["returncode"],
            "helper_timeout": helper_result["timeout"],
            "payload": payload,
            "readback_path": str(output_root / "preflight-contextforge-available-capabilities.json"),
        }
    )
    if helper_result["returncode"] != 0 or helper_result["timeout"] or not isinstance(parsed, dict) or not parsed.get("ok"):
        result["status"] = "failed"
        result["error"] = "could not prove foil absence from ContextForge available-capabilities readback"
        return result

    hits = collect_string_hits(parsed, set(forbidden))
    result["hits"] = hits
    if hits:
        result["status"] = "invalid_preexisting_foil_artifacts"
        result["error"] = "foil is already visible in ContextForge available-capabilities readback before onboarding dialogue"
        return result
    result["status"] = "passed"
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client", choices=["pi", "opencode"], required=True)
    parser.add_argument("--foil", default="time")
    parser.add_argument("--timeout", type=int, default=420)
    parser.add_argument("--max-turns", type=int, default=DEFAULT_ONBOARDING_TURNS)
    parser.add_argument("--max-dialogue-seconds", type=int, default=DEFAULT_DIALOGUE_SECONDS)
    parser.add_argument(
        "--prompt",
        action="append",
        help=(
            "User prompt from the simulated human responder; repeat to provide an agent-authored "
            "persona-consistent sequence. If omitted, the runner uses --responder-mode."
        ),
    )
    parser.add_argument("--prompt-file", type=Path, help="JSON list of agent-authored simulated-human prompts.")
    parser.add_argument(
        "--responder-mode",
        choices=["pi", "model", "seeded"],
        default="pi",
        help="Use a Pi gpt-5.5 simulated-human responder by default; seeded mode is debug scaffolding.",
    )
    parser.add_argument(
        "--responder-pi-image",
        default=os.environ.get("CONTEXTFORGE_PI_HUMAN_SIM_IMAGE", DEFAULT_PI_RESPONDER_IMAGE),
        help="Authenticated Pi image used when --responder-mode=pi.",
    )
    parser.add_argument("--responder-pi-provider", default=os.environ.get("CONTEXTFORGE_PI_HUMAN_SIM_PROVIDER", DEFAULT_PI_RESPONDER_PROVIDER))
    parser.add_argument("--responder-pi-model", default=os.environ.get("CONTEXTFORGE_PI_HUMAN_SIM_MODEL", DEFAULT_PI_RESPONDER_MODEL))
    parser.add_argument(
        "--responder-pi-thinking",
        choices=["off", "minimal", "low", "medium", "high", "xhigh"],
        default=os.environ.get("CONTEXTFORGE_PI_HUMAN_SIM_THINKING", DEFAULT_PI_RESPONDER_THINKING),
    )
    parser.add_argument("--semantic-model-profile", default=os.environ.get("CONTEXTFORGE_SEMANTIC_MODEL_PROFILE", "random"))
    parser.add_argument("--persona-seed", type=int)
    parser.add_argument("--persona-index", type=int, default=1)
    parser.add_argument(
        "--human-help-determination",
        type=int,
        default=int(os.environ.get("CONTEXTFORGE_HUMAN_HELP_DETERMINATION", DEFAULT_HUMAN_HELP_DETERMINATION)),
        help="Simulated-human determination to help the tested assistant succeed at onboarding, from 1 to 20.",
    )
    parser.add_argument("--run-suffix", default="")
    parser.add_argument("--isolation-root", type=Path)
    parser.add_argument(
        "--allow-preexisting-foil-artifacts",
        action="store_true",
        help="Debug only: bypass fail-closed preflight when the foil is already visible in ContextForge.",
    )
    parser.add_argument("--no-build", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if args.timeout < 90:
        raise SystemExit("--timeout must be at least 90 seconds")
    if args.max_turns < 1:
        raise SystemExit("--max-turns must be at least 1")
    if args.max_dialogue_seconds < 90:
        raise SystemExit("--max-dialogue-seconds must be at least 90 seconds")
    args.human_help_determination = bounded_help_determination(args.human_help_determination)

    repo_root = Path(__file__).resolve().parents[3]
    harness_root = repo_root / "docker" / "client-harness"
    scenarios = load_scenarios(harness_root)
    foil = foil_record(scenarios, args.foil)
    persona = compose_persona(scenarios, seed=args.persona_seed, index=args.persona_index)
    manual_prompting = bool(args.prompt or args.prompt_file)
    if manual_prompting or args.responder_mode == "seeded" or args.dry_run:
        prompts, responder_mode = selected_prompts(args, foil, persona)
        if args.responder_mode == "model" and args.dry_run and not manual_prompting:
            responder_mode = "model_backed_simulated_human_responder_dry_run_seed_preview"
        if args.responder_mode == "pi" and args.dry_run and not manual_prompting:
            responder_mode = "pi_gpt_5_5_simulated_human_responder_dry_run_seed_preview"
    else:
        prompts = [persona_initial_prompt(foil, persona)]
        responder_mode = (
            "pi_gpt_5_5_simulated_human_responder"
            if args.responder_mode == "pi"
            else "model_backed_simulated_human_responder"
        )
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_suffix = "".join(ch.lower() if ch.isalnum() else "-" for ch in args.run_suffix).strip("-")
    run_id = timestamp if not run_suffix else f"{timestamp}-{run_suffix}"
    output_root = harness_root / "evidence" / "onboarding-semantic-process" / args.foil / args.client / run_id
    output_root.mkdir(parents=True, exist_ok=True)

    service_runner = load_script_module("run-comprehensive-mcp-service-dialogue.py", "comprehensive_service_runner")
    uc1 = service_runner.load_uc1_module()
    commands: list[dict[str, Any]] = []
    compose_env: dict[str, str] = {}
    isolated_reset: dict[str, Any] | None = None
    reset_json: Any = None
    lock_file = None
    semantic_host_proxy = None
    runtime_apply_host_proxy = None

    def stop_host_proxies() -> None:
        if semantic_host_proxy is not None:
            semantic_host_proxy.stop()
        if runtime_apply_host_proxy is not None:
            runtime_apply_host_proxy.stop()

    if not args.dry_run:
        if args.isolation_root is not None:
            compose_env, isolated_reset, _client_scoped_dir = service_runner.prepare_isolated_harness(args, harness_root)
            reset_json = isolated_reset
            commands.append(
                {
                    "command_text": f"isolated-harness-reset {args.isolation_root}",
                    "cwd": str(repo_root),
                    "returncode": 0 if isolated_reset.get("postcondition") else 1,
                    "timeout": False,
                }
            )
        else:
            lock_file = uc1.acquire_harness_lock(harness_root)
            reset = uc1.run(
                [
                    sys.executable,
                    str(harness_root / "scripts" / "reset-client-harness-state.py"),
                    "--client",
                    uc1.reset_client_name(args.client),
                    "--reset-home-volume",
                    "--evidence-dir",
                    "docker/client-harness/evidence/onboarding-semantic-process/prior",
                ],
                cwd=repo_root,
                timeout=120,
                commands=commands,
            )
            reset_json = uc1.parse_json_or_text(reset["stdout"])

        uc1.ensure_semantic_model_env(harness_root, client=args.client, commands=commands, runner=uc1.run)
    semantic_env_file = harness_root / "env" / "semantic-model.env"
    available_model_env = service_runner.read_env(semantic_env_file) if semantic_env_file.exists() else {}
    selected_profile = service_runner.choose_semantic_model_profile(
        harness_root,
        args.client,
        args.semantic_model_profile,
        available_model_env,
    )
    if selected_profile is None:
        semantic_overrides = service_runner.semantic_model_env_overrides()
        selected_secret_env_keys: list[str] = []
    else:
        semantic_overrides, selected_secret_env_keys = service_runner.selected_profile_env(
            selected_profile,
            args.client,
            available_model_env,
        )
    secret_env_keys = sorted(set(selected_secret_env_keys))
    if selected_profile is not None and str(selected_profile.get("provider_kind") or "") == "openrouter":
        api_key_env = str(selected_profile.get("api_key_env") or "OPENROUTER_API_KEY")
        upstream_base_url = (
            os.environ.get(str(selected_profile.get("base_url_env") or ""))
            or available_model_env.get(str(selected_profile.get("base_url_env") or ""))
            or str(selected_profile.get("default_base_url") or "https://openrouter.ai/api/v1")
        )
        if not args.dry_run:
            semantic_host_proxy = start_openrouter_proxy(
                script_path=harness_root / "scripts" / "semantic_model_host_proxy.py",
                api_key_env=api_key_env,
                upstream_base_url=upstream_base_url,
                host_env=available_model_env,
            )
            semantic_overrides["OPENROUTER_BASE_URL"] = semantic_host_proxy.container_base_url
            semantic_overrides[api_key_env] = semantic_host_proxy.container_api_key
    if not args.dry_run:
        runtime_apply_host_proxy = start_runtime_apply_host_proxy(
            script_path=harness_root / "scripts" / "runtime_apply_host_proxy.py",
            repo_root=repo_root,
        )
        semantic_overrides["CONTEXTFORGE_RUNTIME_APPLY_PROXY_URL"] = runtime_apply_host_proxy.container_url
        semantic_overrides["CONTEXTFORGE_RUNTIME_APPLY_PROXY_TOKEN"] = runtime_apply_host_proxy.token
        semantic_overrides["CONTEXTFORGE_RUNTIME_APPLY_PROXY_BASE_URL"] = "http://127.0.0.1:4445"
        semantic_overrides["CONTEXTFORGE_RUNTIME_APPLY_PROXY_ENV_FILE"] = str(
            repo_root / "docker" / "contextforge-harness" / "env" / "contextforge.env"
        )
    docker_run_env = {**compose_env, **{key: "" for key in API_KEY_ENV_NAMES}}
    semantic_profile = profile_summary(
        service_runner,
        selected_profile,
        semantic_overrides,
        secret_env_keys,
        args.semantic_model_profile,
        available_model_env,
    )
    responder_config: dict[str, Any] | None = None
    responder_profile_summary: dict[str, Any] | None = None
    if responder_mode == "model_backed_simulated_human_responder":
        responder_config = responder_model_config(selected_profile, available_model_env, service_runner)
        responder_profile_summary = {
            "provider_kind": responder_config["provider_kind"],
            "model": responder_config["model"],
            "api_key_env": responder_config["api_key_env"],
            "api_key_present": True,
            "base_url": responder_config["base_url"],
            "route_preferences": responder_config["route_preferences"],
        }
    elif responder_mode == "pi_gpt_5_5_simulated_human_responder":
        responder_config = pi_responder_config(args)
        responder_profile_summary = {
            "provider_kind": "pi",
            "image": responder_config["image"],
            "provider": responder_config["provider"],
            "model": responder_config["model"],
            "thinking": responder_config["thinking"],
            "tools_enabled": False,
            "context_files_enabled": False,
        }

    summary_base = {
        "schema_uri": "contextforge://client-harness/onboarding-semantic-process-dialogue-run/v1",
        "ok_scope": "runner package only; semantic acceptance requires evaluator review",
        "semantic_acceptance": "requires_non_spark_evaluator",
        "deterministic_semantic_oracles_allowed": False,
        "client": args.client,
        "foil": args.foil,
        "source_lead": foil["source_lead"],
        "timestamp": timestamp,
        "run_id": run_id,
        "output_root": str(output_root),
        "persona_seed": args.persona_seed,
        "persona_index": args.persona_index,
        "persona": persona,
        "human_help_determination": {
            "rating": args.human_help_determination,
            "scale": "n/20",
            "description": " ".join(help_determination_lines(args.human_help_determination)),
            "scope": "simulated-human responder only; not sent to the tested assistant except through normal human messages",
        },
        "simulated_human_responder_mode": responder_mode,
        "simulated_human_responder_profile": responder_profile_summary,
        "acceptance_matrix_eligibility": acceptance_matrix_eligibility(
            dry_run=args.dry_run,
            responder_mode=responder_mode,
            manual_prompting=manual_prompting,
            allow_preexisting_foil_artifacts=bool(args.allow_preexisting_foil_artifacts),
            preflight_status=None,
        ),
        "separate_simulated_human_responder_required": True,
        "default_turn_budget": DEFAULT_ONBOARDING_TURNS,
        "default_dialogue_seconds": DEFAULT_DIALOGUE_SECONDS,
        "turn_budget_policy": TURN_BUDGET_POLICY,
        "configured_max_turns": args.max_turns,
        "configured_max_dialogue_seconds": args.max_dialogue_seconds,
        "controller_live_check_policy": {
            "checkpoints_seconds": [120, 360],
            "also_report": ["run_start", "completion_or_error"],
            "scope": "operator cadence only; not a tested-assistant prompt or semantic scoring rule",
        },
        "initial_prompt_count": len(prompts),
        "prompt_count": len(prompts),
        "prompt_count_scope": "initial_or_dry_run_preview_until_final_summary_overrides",
        "prompts": prompts,
        "semantic_model_profile": semantic_profile,
        "semantic_model_host_proxy": None if semantic_host_proxy is None else semantic_host_proxy.summary(),
        "runtime_apply_host_proxy": None if runtime_apply_host_proxy is None else runtime_apply_host_proxy.summary(),
        "container_receives_real_semantic_model_api_key": False,
        "reset": reset_json,
        "isolation": isolated_reset,
        "gate_reference": "docker/client-harness/ONBOARDING_SEMANTIC_PROCESS_GATE.md",
        "scenario_reference": "docker/client-harness/onboarding-semantic-process-scenarios.json",
        "foil_preexistence_policy": {
            "invalid_if_preexisting_contextforge_artifacts": bool(foil.get("invalid_if_preexisting_contextforge_artifacts")),
            "artifact_scope_required_clean": foil.get("preexisting_contextforge_artifact_scope") or [],
            "cleanup_requirement": foil.get("preexisting_contextforge_cleanup_requirement"),
        },
        "deterministic_non_actions": [
            "runner does not score free-form assistant prose",
            "runner does not use Codex as tested assistant",
            "runner seeded prompts are structural scaffolding, not semantic human-response acceptance",
            "runner does not provide service-specific package names, tool names, bridge commands, or probe payloads",
            "runner does not mutate live legacy ContextForge",
        ],
        "evaluator_required_narrative": [
            "after the live dialogue ends or hits a safety bound, evaluate every user/assistant turn and the whole session in one after-action review",
            "judge whether the tested assistant stayed behind the source-lead-only veil",
            "judge whether the runner supplied simulated-human identity and knowledge context without leaking hidden controller facts",
            "judge whether implementation decisions and claim boundaries were surfaced",
            "judge whether any target-client-visible list-tools and safe-call claims are proven",
            "judge interaction efficiency relative to the sampled persona overhead and required outcome",
            "classify failures as runner, simulated-human, tested-client, generic-support, model, service-specific, or environment defects",
        ],
    }

    if args.dry_run:
        summary = {**summary_base, "dry_run": True, "exit_code": 0, "turns": [], "command_ledger": commands}
        redacted_summary = write_redacted_summary(output_root / "run-summary.json", summary)
        print(json.dumps(redacted_summary, indent=2, sort_keys=True))
        stop_host_proxies()
        if lock_file is not None:
            lock_file.close()
        return 0

    preflight = contextforge_foil_preflight(
        foil=foil,
        args=args,
        repo_root=repo_root,
        harness_root=harness_root,
        output_root=output_root,
        reset_json=reset_json,
        uc1=uc1,
        commands=commands,
    )
    summary_base["contextforge_foil_preflight"] = preflight
    summary_base["acceptance_matrix_eligibility"] = acceptance_matrix_eligibility(
        dry_run=False,
        responder_mode=responder_mode,
        manual_prompting=manual_prompting,
        allow_preexisting_foil_artifacts=bool(args.allow_preexisting_foil_artifacts),
        preflight_status=str(preflight.get("status") or ""),
    )
    if preflight.get("status") not in {"passed", "not_applicable", "bypassed_for_debug_only"}:
        summary = {
            **summary_base,
            "dry_run": False,
            "status": "invalid_or_failed_pre_dialogue_preflight",
            "exit_code": 1,
            "turns": [],
            "responder_turns": [],
            "prompt_count": 0,
            "prompts": [],
            "command_ledger": commands,
        }
        redacted_summary = write_redacted_summary(output_root / "run-summary.json", summary)
        print(json.dumps(redacted_summary, indent=2, sort_keys=True))
        stop_host_proxies()
        if lock_file is not None:
            lock_file.close()
        return 1

    if responder_mode == "pi_gpt_5_5_simulated_human_responder" and responder_config is not None:
        image_check = uc1.run(
            ["docker", "image", "inspect", responder_config["image"]],
            cwd=repo_root,
            timeout=120,
            commands=commands,
        )
        if image_check["returncode"] != 0 or image_check["timeout"]:
            summary = {
                **summary_base,
                "dry_run": False,
                "status": "missing_simulated_human_responder_image",
                "exit_code": 1,
                "simulated_human_responder_runtime": {
                    "image": responder_config["image"],
                    "image_check_returncode": image_check["returncode"],
                    "image_check_timeout": image_check["timeout"],
                    "error": (
                        f"Pi simulated-human responder image {responder_config['image']!r} is unavailable; "
                        "create/authenticate the baseline image before model-backed acceptance runs."
                    ),
                },
                "turns": [],
                "responder_turns": [],
                "prompt_count": 0,
                "prompts": [],
                "command_ledger": commands,
            }
            redacted_summary = write_redacted_summary(output_root / "run-summary.json", summary)
            print(json.dumps(redacted_summary, indent=2, sort_keys=True))
            stop_host_proxies()
            if lock_file is not None:
                lock_file.close()
            return 1

    build_result = None
    if not args.no_build:
        build_result = uc1.run(
            ["docker", "compose", "-f", str(harness_root / "compose.yml"), "build", "base", uc1.build_service_name(args.client)],
            cwd=repo_root,
            timeout=600,
            commands=commands,
            env=compose_env or None,
        )

    container_run_id = run_id.lower().replace("z", "").replace("_", "-")
    container = f"cf-onboard-{args.foil[:10]}-{args.client}-{container_run_id}"
    launch_command = [
        "docker",
        "compose",
        "-f",
        str(harness_root / "compose.yml"),
        "--env-file",
        str(semantic_env_file),
        "run",
        "--name",
        container,
        "--no-deps",
        "-d",
    ]
    for key, value in sorted(semantic_overrides.items()):
        launch_command.extend(["-e", f"{key}={value}"])
    launch_command.extend([uc1.compose_service_name(args.client), "sleep", "infinity"])
    launch = uc1.run(launch_command, cwd=repo_root, timeout=120, commands=commands, env=docker_run_env or None)
    runtime = uc1.run(
        ["docker", "exec", container, "bash", "-lc", uc1.runtime_readback_command(args.client)],
        cwd=repo_root,
        timeout=120,
        commands=commands,
    )

    responder_container = None
    responder_runtime: dict[str, Any] | None = None
    if responder_mode == "pi_gpt_5_5_simulated_human_responder" and responder_config is not None:
        responder_container = f"cf-human-sim-pi-{container_run_id}"
        responder_launch = uc1.run(
            [
                "docker",
                "run",
                "--name",
                responder_container,
                "-d",
            ]
            + [item for key in PI_RESPONDER_FORBIDDEN_API_KEY_ENVS for item in ("--env", f"{key}=")]
            + [
                responder_config["image"],
                "sleep",
                "infinity",
            ],
            cwd=repo_root,
            timeout=120,
            commands=commands,
        )
        responder_runtime = {
            "container": responder_container,
            "image": responder_config["image"],
            "launch_returncode": responder_launch["returncode"],
            "launch_timeout": responder_launch["timeout"],
            "session_id": pi_responder_session_id(foil=args.foil, client=args.client, run_id=run_id),
        }
        if responder_launch["returncode"] == 0 and not responder_launch["timeout"]:
            version = uc1.run(
                ["docker", "exec", responder_container, "bash", "-lc", "pi --version"],
                cwd=repo_root,
                timeout=120,
                commands=commands,
            )
            responder_runtime["version_returncode"] = version["returncode"]
            responder_runtime["version_timeout"] = version["timeout"]
        else:
            responder_runtime["error"] = (
                f"Pi simulated-human responder image {responder_config['image']!r} is unavailable or failed to launch; "
                "create/authenticate the baseline image before model-backed acceptance runs."
            )

    session_id = f"onboarding-{args.foil}-{args.client}-{run_id}"
    base_session_id = session_id
    target_session_ids: list[str] = [session_id]
    target_session_boundary_events: list[dict[str, Any]] = []
    pending_fresh_target_session: dict[str, Any] | None = None
    fresh_target_session_count = 0
    turns: list[dict[str, Any]] = []
    responder_turns: list[dict[str, Any]] = []
    actual_prompts: list[str] = []
    previous_user_prompt = ""
    previous_assistant_output = ""
    dialogue_started_at = time.monotonic()
    dialogue_stop_reason = "turn_safety_cap_reached"
    for index in range(1, args.max_turns + 1):
        create_target_session = args.client == "opencode" and index == 1
        turn_session_boundary_event: dict[str, Any] | None = None
        runner_observation = ""
        if pending_fresh_target_session is not None:
            fresh_target_session_count += 1
            old_session_id = session_id
            requested_session_id = fresh_target_session_id(base_session_id, fresh_target_session_count)
            runner_observation = (
                "A fresh/reloaded target-client session has been started before this next assistant turn "
                "because the previous assistant/helper output said target-client usability required a new "
                "session or reload. You may tell the assistant that you started the fresh session if that is "
                "a natural response for your persona. Do not add package names, tool names, commands, or "
                "other service-specific facts not visible in the dialogue."
            )
            turn_session_boundary_event = {
                "type": "fresh_target_client_session_after_runtime_apply",
                "before_turn": index,
                "previous_session_id": old_session_id,
                "requested_session_id": requested_session_id,
                "reason": pending_fresh_target_session,
                "operator_fact_visible_to_simulated_human": True,
            }
            if args.client == "opencode":
                create_target_session = True
                turn_session_boundary_event["new_session_id"] = "pending_opencode_discovery"
            else:
                session_id = requested_session_id
                turn_session_boundary_event["new_session_id"] = session_id
                if session_id not in target_session_ids:
                    target_session_ids.append(session_id)
            pending_fresh_target_session = None
        turn_timeout = remaining_dialogue_timeout(dialogue_started_at, args.max_dialogue_seconds, args.timeout)
        if turn_timeout <= 0:
            dialogue_stop_reason = "time_safety_cap_reached_before_turn"
            break
        if index == 1:
            prompt = prompts[0]
        elif responder_mode == "model_backed_simulated_human_responder" and responder_config is not None:
            messages = responder_messages(
                foil,
                persona,
                help_determination=args.human_help_determination,
                turn_index=index,
                previous_user_prompt=previous_user_prompt,
                previous_assistant_output=previous_assistant_output,
                runner_observation=runner_observation,
            )
            try:
                responder_text = litellm_chat_completion(responder_config, messages)
                prompt, continue_conversation, parsed_structured = parse_simulated_human_response(responder_text)
                responder_turns.append(
                    {
                        "turn": index,
                        "mode": "model_backed",
                        "model": responder_config["model"],
                        "route_preferences": responder_config["route_preferences"],
                        "response_chars": len(responder_text),
                        "message_chars": len(prompt),
                        "structured_response": parsed_structured,
                        "continue_conversation": continue_conversation,
                    }
                )
                if not continue_conversation:
                    dialogue_stop_reason = "simulated_human_declared_complete"
                    break
            except Exception as exc:
                responder_turns.append(
                    {
                        "turn": index,
                        "mode": "model_backed",
                        "model": responder_config["model"],
                        "route_preferences": responder_config["route_preferences"],
                        "error": str(exc),
                    }
                )
                dialogue_stop_reason = "simulated_human_responder_failed"
                break
        elif responder_mode == "pi_gpt_5_5_simulated_human_responder" and responder_config is not None and responder_runtime is not None:
            if responder_runtime.get("launch_returncode") != 0 or responder_runtime.get("version_returncode") not in {0, None}:
                responder_turns.append(
                    {
                        "turn": index,
                        "mode": "pi_model_backed",
                        "model": responder_config["model"],
                        "image": responder_config["image"],
                        "error": responder_runtime.get("error", "Pi simulated-human responder is not available"),
                    }
                )
                dialogue_stop_reason = "simulated_human_responder_unavailable"
                break
            responder_timeout = remaining_dialogue_timeout(dialogue_started_at, args.max_dialogue_seconds, args.timeout)
            if responder_timeout <= 0:
                dialogue_stop_reason = "time_safety_cap_reached_before_responder"
                break
            prompt_request = pi_responder_prompt(
                foil,
                persona,
                help_determination=args.human_help_determination,
                turn_index=index,
                previous_user_prompt=previous_user_prompt,
                previous_assistant_output=previous_assistant_output,
                runner_observation=runner_observation,
            )
            command_args = pi_responder_command(
                responder_config,
                str(responder_runtime["session_id"]),
                prompt_request,
                help_determination=args.human_help_determination,
            )
            result = uc1.run(
                ["docker", "exec", str(responder_runtime["container"]), *command_args],
                cwd=repo_root,
                timeout=responder_timeout,
                commands=commands,
            )
            responder_path = output_root / f"human-responder-turn-{index}.raw.txt"
            responder_path.write_text(uc1.render_command_block(result), encoding="utf-8")
            if result["returncode"] != 0 or result["timeout"]:
                responder_turns.append(
                    {
                        "turn": index,
                        "mode": "pi_model_backed",
                        "model": responder_config["model"],
                        "image": responder_config["image"],
                        "returncode": result["returncode"],
                        "timeout": result["timeout"],
                        "error": "Pi simulated-human responder turn failed",
                        "path": str(responder_path),
                    }
                )
                dialogue_stop_reason = "simulated_human_responder_failed"
                break
            responder_text = str(result.get("stdout") or "").strip()
            prompt, continue_conversation, parsed_structured = parse_simulated_human_response(responder_text)
            responder_turns.append(
                {
                    "turn": index,
                    "mode": "pi_model_backed",
                    "model": responder_config["model"],
                    "image": responder_config["image"],
                    "response_chars": len(responder_text),
                    "message_chars": len(prompt),
                    "path": str(responder_path),
                    "structured_response": parsed_structured,
                    "continue_conversation": continue_conversation,
                }
            )
            if not prompt:
                responder_turns[-1]["error"] = "Pi simulated-human responder returned an empty prompt"
                dialogue_stop_reason = "simulated_human_responder_empty_prompt"
                break
            if not continue_conversation:
                dialogue_stop_reason = "simulated_human_declared_complete"
                break
        elif index <= len(prompts):
            prompt = prompts[index - 1]
        else:
            dialogue_stop_reason = "prompt_sequence_exhausted"
            break
        assistant_timeout = remaining_dialogue_timeout(dialogue_started_at, args.max_dialogue_seconds, args.timeout)
        if assistant_timeout <= 0:
            dialogue_stop_reason = "time_safety_cap_reached_before_assistant"
            break
        actual_prompts.append(prompt)
        command = uc1.target_client_command(
            args.client,
            session_id,
            prompt,
            create_session=create_target_session,
        )
        result = uc1.run(["docker", "exec", container, "bash", "-lc", command], cwd=repo_root, timeout=assistant_timeout, commands=commands)
        if args.client == "opencode" and create_target_session:
            discovered = uc1.extract_opencode_session_id(str(result.get("stdout") or ""))
            if discovered:
                session_id = discovered
                if session_id not in target_session_ids:
                    target_session_ids.append(session_id)
                if turn_session_boundary_event is not None:
                    turn_session_boundary_event["new_session_id"] = session_id
        path = output_root / f"turn-{index}.raw.txt"
        path.write_text(uc1.render_command_block(result), encoding="utf-8")
        assistant_stdout = str(result.get("stdout") or "")
        assistant_error = assistant_error_from_json_stream(assistant_stdout)
        assistant_visible_output = assistant_visible_text_from_json_stream(assistant_stdout)
        structural_events = extract_turn_structural_events(assistant_stdout)
        visible_path = output_root / f"turn-{index}.assistant-visible.txt"
        visible_path.write_text(assistant_visible_output + ("\n" if assistant_visible_output else ""), encoding="utf-8")
        previous_user_prompt = prompt
        previous_assistant_output = assistant_visible_output
        turn_record = {
            "turn": index,
            "prompt": prompt,
            "path": str(path),
            "assistant_visible_path": str(visible_path),
            "target_session_id": session_id,
            "target_session_boundary": turn_session_boundary_event,
            "returncode": result["returncode"],
            "timeout": result["timeout"],
            "assistant_error": assistant_error,
            "assistant_visible_chars": len(assistant_visible_output),
            "json_event_count": structural_events["json_event_count"],
            "session_event_ids": structural_events["session_event_ids"],
            "tool_calls": structural_events["tool_calls"],
            "tool_results": structural_events["tool_results"],
            "token_usage_events": structural_events["token_usage_events"],
            "token_totals": structural_events["token_totals"],
        }
        turns.append(turn_record)
        if turn_session_boundary_event is not None:
            target_session_boundary_events.append(turn_session_boundary_event)
        success = turn_runtime_apply_success(turn_record)
        if success is not None and fresh_target_session_count == 0 and pending_fresh_target_session is None:
            pending_fresh_target_session = {
                "after_turn": index,
                "runtime_apply_success": success,
                "deterministic_scope": "structured runtime-apply result only; semantic adequacy remains evaluator-owned",
            }
        if result["timeout"]:
            dialogue_stop_reason = "tested_assistant_timeout"
            break
        if result["returncode"] != 0 or assistant_error:
            dialogue_stop_reason = "tested_assistant_failed"
            break
    else:
        dialogue_stop_reason = "turn_safety_cap_reached"

    dialogue_elapsed_seconds = round(time.monotonic() - dialogue_started_at, 3)

    responder_ok = all("error" not in turn for turn in responder_turns)
    responder_runtime_ok = (
        responder_runtime is None
        or (
            responder_runtime.get("launch_returncode") == 0
            and responder_runtime.get("launch_timeout") is False
            and responder_runtime.get("version_returncode") == 0
            and responder_runtime.get("version_timeout") is False
        )
    )
    ok = (
        launch["returncode"] == 0
        and runtime["returncode"] == 0
        and responder_runtime_ok
        and responder_ok
        and all(not turn["timeout"] and turn["returncode"] == 0 and not turn.get("assistant_error") for turn in turns)
    )
    exit_code = 0 if ok else 1
    native_transcript_exports: list[dict[str, Any]] = []
    if args.client == "pi":
        for transcript_session_id in dict.fromkeys(target_session_ids):
            native_transcript_exports.append(
                copy_native_pi_session_transcript(
                    uc1,
                    repo_root=repo_root,
                    container=container,
                    session_id=transcript_session_id,
                    role="target",
                    session_dir="/home/agent/.pi/agent/sessions",
                    commands=commands,
                )
            )
    if (
        responder_mode == "pi_gpt_5_5_simulated_human_responder"
        and responder_runtime is not None
        and isinstance(responder_runtime.get("container"), str)
        and isinstance(responder_runtime.get("session_id"), str)
    ):
        native_transcript_exports.append(
            copy_native_pi_session_transcript(
                uc1,
                repo_root=repo_root,
                container=str(responder_runtime["container"]),
                session_id=str(responder_runtime["session_id"]),
                role="human-sim",
                session_dir="/home/agent/.pi/human-sim-sessions",
                commands=commands,
            )
        )
    native_transcript_export_manifest = output_root / "native-transcript-exports.json"
    write_json(native_transcript_export_manifest, {"exports": native_transcript_exports})
    generation_report = build_generation_report(client=args.client, session_id=session_id, turns=turns)
    structural_onboarding_proof = build_structural_onboarding_proof_report(turns)
    summary = {
        **summary_base,
        "dry_run": False,
        "exit_code": exit_code,
        "container": container,
        "session_id": session_id,
        "target_session_ids": target_session_ids,
        "target_session_boundary_events": target_session_boundary_events,
        "build_returncode": None if build_result is None else build_result["returncode"],
        "launch_returncode": launch["returncode"],
        "runtime_returncode": runtime["returncode"],
        "simulated_human_responder_runtime": responder_runtime,
        "evidence_exports": {
            "native_pi_transcript_manifest": str(native_transcript_export_manifest),
            "native_pi_transcripts": native_transcript_exports,
        },
        "generation_report": generation_report,
        "structural_onboarding_proof": structural_onboarding_proof,
        "turns": turns,
        "responder_turns": responder_turns,
        "dialogue_stop_reason": dialogue_stop_reason,
        "dialogue_elapsed_seconds": dialogue_elapsed_seconds,
        "dialogue_safety_bounds": {
            "max_turns": args.max_turns,
            "max_dialogue_seconds": args.max_dialogue_seconds,
            "policy": "capture first; evaluate every turn and whole-session semantics after the interaction",
        },
        "prompt_count": len(actual_prompts),
        "prompts": actual_prompts,
        "command_ledger": commands,
    }
    redacted_summary = write_redacted_summary(output_root / "run-summary.json", summary)
    print(json.dumps(redacted_summary, indent=2, sort_keys=True))
    stop_host_proxies()
    if lock_file is not None:
        lock_file.close()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
