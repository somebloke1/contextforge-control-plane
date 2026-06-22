#!/usr/bin/env python3
"""Run one source-lead-only onboarding process dialogue through Pi/OpenCode."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import random
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from semantic_model_host_proxy import API_KEY_ENV_NAMES, start_openrouter_proxy


DEFAULT_ONBOARDING_TURNS = 8
TURN_BUDGET_POLICY = (
    "interaction length is persona- and outcome-dependent; default seeded runs "
    "use a generous budget, but semantic adequacy is judged by required outcomes, "
    "not by a fixed turn count"
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
        base += " Be precise about what is proven and what is not."
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
    provider_kind = profile_value(profile, "provider_kind", available_env.get("CONTEXTFORGE_TEST_PROVIDER_KIND", "openrouter"))
    if provider_kind != "openrouter":
        raise RuntimeError("model-backed simulated human responder currently requires an OpenRouter semantic profile")
    model = profile_value(profile, "model", available_env.get("OPENROUTER_MODEL") or available_env.get("CONTEXTFORGE_TEST_MODEL"))
    if not model:
        raise RuntimeError("model-backed simulated human responder could not determine an OpenRouter model")
    key_env = profile_value(profile, "api_key_env", "OPENROUTER_API_KEY")
    api_key = os.environ.get(key_env) or available_env.get(key_env)
    if not api_key:
        raise RuntimeError(f"model-backed simulated human responder is missing {key_env}")
    base_url_env = profile_value(profile, "base_url_env", "OPENROUTER_BASE_URL")
    base_url = (
        (os.environ.get(base_url_env) or available_env.get(base_url_env))
        if base_url_env
        else ""
    ) or profile_value(profile, "default_base_url", "https://openrouter.ai/api/v1")
    routes = service_runner.route_preferences(profile) if profile is not None else []
    return {
        "provider_kind": provider_kind,
        "model": model,
        "api_key_env": key_env,
        "api_key": api_key,
        "base_url": base_url.rstrip("/"),
        "route_preferences": routes,
    }


def responder_messages(
    foil: dict[str, Any],
    persona: dict[str, str],
    *,
    turn_index: int,
    previous_user_prompt: str,
    previous_assistant_output: str,
) -> list[dict[str, str]]:
    persona_lines = "\n".join(f"- {key}: {value}" for key, value in sorted(persona.items()))
    system = responder_system_prompt()
    user = (
        f"Source lead: {foil['source_lead']}\n\n"
        f"Persona vector:\n{persona_lines}\n\n"
        f"Turn to produce: {turn_index}\n\n"
        f"Previous user message:\n{previous_user_prompt}\n\n"
        "Previous tested-assistant visible output:\n"
        f"{clip_text(previous_assistant_output)}\n\n"
        "Write the next simulated-human message now."
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def responder_system_prompt() -> str:
    return (
        "You are the human user in a ContextForge onboarding interaction with a code assistant. "
        "Your world, goal, knowledge, and voice are defined by the source lead, persona vector, "
        "previous user message, and previous assistant output. Write the human user's next message."
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
    turn_index: int,
    previous_user_prompt: str,
    previous_assistant_output: str,
) -> str:
    persona_lines = "\n".join(f"- {key}: {value}" for key, value in sorted(persona.items()))
    return (
        f"Source lead: {foil['source_lead']}\n\n"
        f"Persona vector:\n{persona_lines}\n\n"
        f"Turn to produce: {turn_index}\n\n"
        f"Previous user message:\n{previous_user_prompt}\n\n"
        "Previous tested-assistant visible output:\n"
        f"{clip_text(previous_assistant_output)}\n\n"
        "Write the next simulated-human message now."
    )


def pi_responder_command(config: Mapping[str, str], session_id: str, prompt: str) -> list[str]:
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
        responder_system_prompt(),
        "-p",
        prompt,
    ]


def openrouter_chat_completion(config: dict[str, Any], messages: list[dict[str, str]]) -> str:
    body: dict[str, Any] = {
        "model": config["model"],
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 220,
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
        raise RuntimeError(f"OpenRouter responder request failed: HTTP {exc.code} {exc.reason}: {detail}") from exc
    choices = payload.get("choices") if isinstance(payload, dict) else None
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("OpenRouter responder response did not include choices")
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("OpenRouter responder response did not include message content")
    return content.strip()


def profile_summary(service_runner: Any, profile: dict[str, Any] | None, env: dict[str, str], secret_keys: list[str], selector: str, available_env: dict[str, str]) -> dict[str, Any]:
    return service_runner.redacted_profile_summary(profile, env, secret_keys, selector, available_env)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def assistant_error_from_json_stream(text: str) -> str | None:
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
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
    parts: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") != "text":
            continue
        part = event.get("part")
        if not isinstance(part, dict):
            continue
        value = part.get("text")
        if isinstance(value, str) and value.strip():
            parts.append(value.strip())
    if parts:
        return "\n\n".join(parts)
    return text.strip()


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
        "checked_surface": "contextforge_project_init_available_capabilities",
        "checked_surface_scope": "visible activation/capability exposure; broader service/tool/virtual-server/prompt/resource cleanup remains required by gate policy",
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
        "simulated_human_responder_mode": responder_mode,
        "simulated_human_responder_profile": responder_profile_summary,
        "separate_simulated_human_responder_required": True,
        "default_turn_budget": DEFAULT_ONBOARDING_TURNS,
        "turn_budget_policy": TURN_BUDGET_POLICY,
        "configured_max_turns": args.max_turns,
        "initial_prompt_count": len(prompts),
        "prompt_count": len(prompts),
        "prompt_count_scope": "initial_or_dry_run_preview_until_final_summary_overrides",
        "prompts": prompts,
        "semantic_model_profile": semantic_profile,
        "semantic_model_host_proxy": None if semantic_host_proxy is None else semantic_host_proxy.summary(),
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
            "judge whether the tested assistant stayed behind the source-lead-only veil",
            "judge whether the runner supplied simulated-human identity and knowledge context without leaking hidden controller facts",
            "judge whether implementation decisions and claim boundaries were surfaced",
            "judge whether any target-client-visible list-tools and safe-call claims are proven",
            "judge interaction efficiency relative to the sampled persona overhead and required outcome",
            "classify failures as runner, simulated-human, tested-client, generic-support, model, service-specific, or environment defects",
        ],
    }

    if args.dry_run:
        summary = {**summary_base, "dry_run": True, "turns": [], "command_ledger": commands}
        write_json(output_root / "run-summary.json", summary)
        print(json.dumps(summary, indent=2, sort_keys=True))
        if semantic_host_proxy is not None:
            semantic_host_proxy.stop()
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
    if preflight.get("status") not in {"passed", "not_applicable", "bypassed_for_debug_only"}:
        summary = {
            **summary_base,
            "dry_run": False,
            "status": "invalid_or_failed_pre_dialogue_preflight",
            "turns": [],
            "responder_turns": [],
            "prompt_count": 0,
            "prompts": [],
            "command_ledger": commands,
        }
        write_json(output_root / "run-summary.json", summary)
        print(json.dumps(summary, indent=2, sort_keys=True))
        if semantic_host_proxy is not None:
            semantic_host_proxy.stop()
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
            write_json(output_root / "run-summary.json", summary)
            print(json.dumps(summary, indent=2, sort_keys=True))
            if semantic_host_proxy is not None:
                semantic_host_proxy.stop()
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
    turns: list[dict[str, Any]] = []
    responder_turns: list[dict[str, Any]] = []
    actual_prompts: list[str] = []
    previous_user_prompt = ""
    previous_assistant_output = ""
    for index in range(1, args.max_turns + 1):
        if index == 1:
            prompt = prompts[0]
        elif responder_mode == "model_backed_simulated_human_responder" and responder_config is not None:
            messages = responder_messages(
                foil,
                persona,
                turn_index=index,
                previous_user_prompt=previous_user_prompt,
                previous_assistant_output=previous_assistant_output,
            )
            try:
                prompt = openrouter_chat_completion(responder_config, messages)
                responder_turns.append(
                    {
                        "turn": index,
                        "mode": "model_backed",
                        "model": responder_config["model"],
                        "route_preferences": responder_config["route_preferences"],
                        "response_chars": len(prompt),
                    }
                )
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
                break
            prompt_request = pi_responder_prompt(
                foil,
                persona,
                turn_index=index,
                previous_user_prompt=previous_user_prompt,
                previous_assistant_output=previous_assistant_output,
            )
            command_args = pi_responder_command(responder_config, str(responder_runtime["session_id"]), prompt_request)
            result = uc1.run(
                ["docker", "exec", str(responder_runtime["container"]), *command_args],
                cwd=repo_root,
                timeout=args.timeout,
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
                break
            prompt = str(result.get("stdout") or "").strip()
            responder_turns.append(
                {
                    "turn": index,
                    "mode": "pi_model_backed",
                    "model": responder_config["model"],
                    "image": responder_config["image"],
                    "response_chars": len(prompt),
                    "path": str(responder_path),
                }
            )
            if not prompt:
                responder_turns[-1]["error"] = "Pi simulated-human responder returned an empty prompt"
                break
        elif index <= len(prompts):
            prompt = prompts[index - 1]
        else:
            break
        actual_prompts.append(prompt)
        command = uc1.target_client_command(
            args.client,
            session_id,
            prompt,
            create_session=args.client == "opencode" and index == 1,
        )
        result = uc1.run(["docker", "exec", container, "bash", "-lc", command], cwd=repo_root, timeout=args.timeout, commands=commands)
        if args.client == "opencode" and index == 1:
            discovered = uc1.extract_opencode_session_id(str(result.get("stdout") or ""))
            if discovered:
                session_id = discovered
        path = output_root / f"turn-{index}.raw.txt"
        path.write_text(uc1.render_command_block(result), encoding="utf-8")
        assistant_error = assistant_error_from_json_stream(str(result.get("stdout") or ""))
        assistant_visible_output = assistant_visible_text_from_json_stream(str(result.get("stdout") or ""))
        visible_path = output_root / f"turn-{index}.assistant-visible.txt"
        visible_path.write_text(assistant_visible_output + ("\n" if assistant_visible_output else ""), encoding="utf-8")
        previous_user_prompt = prompt
        previous_assistant_output = assistant_visible_output
        turns.append(
            {
                "turn": index,
                "prompt": prompt,
                "path": str(path),
                "assistant_visible_path": str(visible_path),
                "returncode": result["returncode"],
                "timeout": result["timeout"],
                "assistant_error": assistant_error,
            }
        )

    summary = {
        **summary_base,
        "dry_run": False,
        "container": container,
        "session_id": session_id,
        "build_returncode": None if build_result is None else build_result["returncode"],
        "launch_returncode": launch["returncode"],
        "runtime_returncode": runtime["returncode"],
        "simulated_human_responder_runtime": responder_runtime,
        "turns": turns,
        "responder_turns": responder_turns,
        "prompt_count": len(actual_prompts),
        "prompts": actual_prompts,
        "command_ledger": commands,
    }
    write_json(output_root / "run-summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    if semantic_host_proxy is not None:
        semantic_host_proxy.stop()
    if lock_file is not None:
        lock_file.close()
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
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
