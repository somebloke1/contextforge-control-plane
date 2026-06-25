#!/usr/bin/env python3
"""Run a qwen-only known-service management state story in Pi or OpenCode."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from harness_redaction import redact_value

LOCAL_QWEN_ENV = Path("env/local-llama.env")
DEFAULT_CONTEXTFORGE_GATEWAY_CONTAINER = "contextforge-harness-contextforge-gateway-1"
DEFAULT_CONTEXTFORGE_HOST_BASE_URL = "http://127.0.0.1:4445"
DEFAULT_CONTEXTFORGE_CONTAINER_BASE_URL = "http://host.docker.internal:4445"
WRAPPER_TOKEN_CACHE = "/tmp/contextforge-wrapper-token.local.json"
WRAPPER_TOKEN_LOCK = "/tmp/contextforge-wrapper-token.local.json.lock"

EXPECTED_SERVICE_BINDINGS = [
    "context7:canonical",
    "mentality:static_repo_local",
    "github:canonical",
    "web-search:credential_scoped",
    "exa-search:credential_scoped",
    "playwright:session_scoped",
    "ssh-tmux:session_scoped",
    "openzeppelin-solidity-contracts:canonical",
    "serena:4a93a92afaa7",
]

STATE_STORY_PROMPTS = [
    "I want to manage this project's ContextForge services. Show the available services and keep it concise.",
    "Enable context7.",
    "approve",
    "Show details for context7.",
    "Remove context7. Confirm with context7 if the helper asks for a typed service name.",
    "context7",
    "Repair context7.",
    "approve",
    "Enable mentality, github, and web-search.",
    "approve",
    "Disable github.",
    "approve",
    "Disable mentality.",
    "approve",
    "Enable exa-search, playwright, and ssh-tmux.",
    "approve",
    "Disable all currently enabled ContextForge services.",
    "approve",
    "Enable all available ContextForge services. If Serena asks for a language, choose Python.",
    "python",
    "approve",
    "Show final service status and details for all enabled services.",
]


def load_uc1_module() -> Any:
    path = Path(__file__).with_name("run-use-case-1-dialogue.py")
    spec = importlib.util.spec_from_file_location("use_case_1_runner", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("\"'")
    return values


def request_json(method: str, base_url: str, path: str, *, token: str | None = None, body: dict[str, Any] | None = None) -> Any:
    headers = {"Accept": "application/json"}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(f"{base_url.rstrip('/')}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = response.read()
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"{method} {path} failed on {base_url.rstrip('/')}: HTTP {exc.code} {exc.reason}") from exc
    return json.loads(payload) if payload else None


def docker_container_env(container_name: str) -> dict[str, str]:
    raw = subprocess.check_output(["docker", "inspect", container_name, "--format", "{{json .Config.Env}}"], text=True)
    values: dict[str, str] = {}
    for item in json.loads(raw):
        if not isinstance(item, str) or "=" not in item:
            continue
        key, value = item.split("=", 1)
        values[key] = value
    return values


def contextforge_login_token(*, gateway_container: str, host_base_url: str) -> tuple[str, dict[str, Any]]:
    env = docker_container_env(gateway_container)
    email = env.get("PLATFORM_ADMIN_EMAIL")
    password = env.get("PLATFORM_ADMIN_PASSWORD")
    if not email or not password:
        raise RuntimeError(f"{gateway_container} does not expose PLATFORM_ADMIN_EMAIL and PLATFORM_ADMIN_PASSWORD")
    last_error: Exception | None = None
    for login_path in ("/auth/login", "/auth/email/login"):
        try:
            response = request_json("POST", host_base_url, login_path, body={"email": email, "password": password})
        except Exception as exc:
            last_error = exc
            continue
        token = response.get("access_token") if isinstance(response, dict) else None
        if isinstance(token, str) and token:
            return token, {
                "host_base_url": host_base_url.rstrip("/"),
                "gateway_container": gateway_container,
                "login_path": login_path,
                "identity": email,
                "token_present": True,
            }
    raise RuntimeError(f"ContextForge login did not return an access token: {last_error}")


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def safe_run_suffix(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-")


def default_session_id(client: str, timestamp: str) -> str:
    compact = timestamp.lower().replace("t", "").replace("z", "")
    if client == "opencode":
        return f"ses_service_state_{compact}"
    return f"service-state-{client}-{timestamp}"


def qwen_launch_env(harness_root: Path) -> tuple[dict[str, str], dict[str, Any]]:
    env_path = harness_root / LOCAL_QWEN_ENV
    env = read_env(env_path)
    required = ["LOCAL_LLAMA_BASE_URL", "LOCAL_LLAMA_MODEL", "LOCAL_LLAMA_KEY"]
    missing = [key for key in required if not env.get(key)]
    if missing:
        raise RuntimeError(f"{env_path} missing required keys: {', '.join(missing)}")
    model = env["LOCAL_LLAMA_MODEL"]
    launch_env = {
        "CONTEXTFORGE_TEST_PROVIDER": "local llama.cpp",
        "CONTEXTFORGE_TEST_PROVIDER_KIND": "openai_compatible",
        "CONTEXTFORGE_TEST_MODEL": model,
        "CONTEXTFORGE_TEST_MODEL_NAME": "Local llama.cpp Qwen 3.6 A3B",
        "CONTEXTFORGE_TEST_CONTEXT_WINDOW": "131072",
        "CONTEXTFORGE_PI_DEFAULT_PROVIDER": "local-llama-qwen",
        "CONTEXTFORGE_PI_DEFAULT_MODEL": model,
        "CONTEXTFORGE_OPENCODE_DEFAULT_MODEL": f"llama.cpp/{model}",
        "CONTEXTFORGE_OPENCODE_SMALL_MODEL": f"llama.cpp/{model}",
        "LOCAL_LLAMA_BASE_URL": env["LOCAL_LLAMA_BASE_URL"],
        "LOCAL_LLAMA_MODEL": model,
        "LOCAL_LLAMA_KEY": env["LOCAL_LLAMA_KEY"],
        "CONTEXTFORGE_REDACT_VALUES": env["LOCAL_LLAMA_KEY"],
    }
    summary = {
        "provider_kind": "openai_compatible",
        "provider_label": "local llama.cpp",
        "model": model,
        "display_name": "Local llama.cpp Qwen 3.6 A3B",
        "base_url": env["LOCAL_LLAMA_BASE_URL"],
        "api_key_present": True,
        "api_key_delivered_to_container": True,
        "api_key_delivery_reason": "local llama.cpp requires an API key; no hosted provider key is passed",
    }
    os.environ["LOCAL_LLAMA_KEY"] = env["LOCAL_LLAMA_KEY"]
    os.environ["CONTEXTFORGE_REDACT_VALUES"] = env["LOCAL_LLAMA_KEY"]
    return launch_env, summary


def write_client_scoped_env(
    run_root: Path,
    *,
    gateway_container: str,
    host_base_url: str,
    container_base_url: str,
) -> tuple[Path, dict[str, Any]]:
    token, auth_summary = contextforge_login_token(gateway_container=gateway_container, host_base_url=host_base_url)
    client_scoped_dir = run_root / "client-scoped"
    client_scoped_dir.mkdir(parents=True, exist_ok=True)
    env_path = client_scoped_dir / "contextforge.env"
    env_path.write_text(
        "\n".join(
            [
                f"CONTEXTFORGE_BASE_URL={container_base_url.rstrip('/')}",
                f"CONTEXTFORGE_BEARER_TOKEN={token}",
                f"CONTEXTFORGE_TOKEN_CACHE={WRAPPER_TOKEN_CACHE}",
                f"CONTEXTFORGE_TOKEN_LOCK={WRAPPER_TOKEN_LOCK}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    os.chmod(env_path, 0o600)
    os.environ["CONTEXTFORGE_REDACT_VALUES"] = "\n".join(
        value for value in [os.environ.get("CONTEXTFORGE_REDACT_VALUES", ""), token] if value
    )
    return client_scoped_dir, {
        "path": str(env_path),
        "base_url": container_base_url.rstrip("/"),
        "bearer_token_present": True,
        "token_source": "contextforge_harness_admin_login",
        "auth": auth_summary,
        "shared_harness_env_mutated": False,
    }


def state_readback_command(expected_bindings: list[str]) -> str:
    script = f"""
import json
from pathlib import Path

root = Path('/workspace')
state_path = root / '.project' / 'context_forge_state.json'
opencode_path = root / 'opencode.json'
expected = {expected_bindings!r}
payload = {{
    'state_exists': state_path.exists(),
    'opencode_json_exists': opencode_path.exists(),
    'expected_bindings': expected,
    'services': {{}},
    'service_count': 0,
    'missing_expected': list(expected),
    'present_expected': [],
    'target_client_projection': {{}},
    'status': None,
    'revision': None,
}}
if state_path.exists():
    try:
        state = json.loads(state_path.read_text(encoding='utf-8'))
        payload['status'] = state.get('status')
        payload['revision'] = state.get('meta', {{}}).get('revision')
        services = state.get('services') if isinstance(state, dict) else {{}}
        if isinstance(services, dict):
            payload['service_count'] = len(services)
            payload['services'] = {{
                key: {{
                    'service_family': value.get('service_family') if isinstance(value, dict) else None,
                    'service_binding': value.get('service_binding') if isinstance(value, dict) else None,
                    'provision_status': value.get('provision_status') if isinstance(value, dict) else None,
                    'target_clients': sorted((value.get('target_clients') or {{}}).keys()) if isinstance(value, dict) else [],
                }}
                for key, value in sorted(services.items())
            }}
            present = [binding for binding in expected if binding in services]
            payload['present_expected'] = present
            payload['missing_expected'] = [binding for binding in expected if binding not in services]
            payload['target_client_projection'] = {{
                binding: payload['services'][binding].get('target_clients', [])
                for binding in present
            }}
    except Exception as exc:
        payload['state_error'] = exc.__class__.__name__ + ': ' + str(exc)
print(json.dumps(payload, indent=2, sort_keys=True))
"""
    return "python3 - <<'PY'\n" + script.strip() + "\nPY"


def run_turn(
    uc1: Any,
    *,
    client: str,
    container: str,
    session_id: str,
    prompt: str,
    turn_index: int,
    output_root: Path,
    repo_root: Path,
    timeout: int,
    commands: list[dict[str, Any]],
) -> tuple[str, dict[str, Any]]:
    command = uc1.target_client_command(
        client,
        session_id,
        prompt,
        create_session=client == "opencode" and turn_index == 1,
    )
    result = uc1.run(["docker", "exec", container, "bash", "-lc", command], cwd=repo_root, timeout=timeout, commands=commands)
    raw_path = output_root / f"turn-{turn_index:02d}.raw.txt"
    raw_path.write_text(uc1.render_command_block(result), encoding="utf-8")
    if client == "opencode" and turn_index == 1:
        discovered = uc1.extract_opencode_session_id(str(result.get("stdout") or ""))
        if discovered:
            session_id = discovered
    readback = uc1.run(
        ["docker", "exec", container, "bash", "-lc", state_readback_command(EXPECTED_SERVICE_BINDINGS)],
        cwd=repo_root,
        timeout=60,
        commands=commands,
    )
    readback_path = output_root / f"turn-{turn_index:02d}.state.json"
    try:
        readback_payload = json.loads(readback.get("stdout") or "{}")
    except json.JSONDecodeError:
        readback_payload = {"raw": readback.get("stdout") or "", "parse_error": True}
    write_json(readback_path, readback_payload)
    return session_id, {
        "turn": turn_index,
        "prompt": prompt,
        "raw_path": str(raw_path),
        "state_readback_path": str(readback_path),
        "returncode": result["returncode"],
        "timeout": result["timeout"],
        "state_returncode": readback["returncode"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client", choices=["pi", "opencode"], required=True)
    parser.add_argument("--timeout", type=int, default=420)
    parser.add_argument("--no-build", action="store_true")
    parser.add_argument("--run-suffix", default="")
    parser.add_argument("--contextforge-gateway-container", default=DEFAULT_CONTEXTFORGE_GATEWAY_CONTAINER)
    parser.add_argument("--contextforge-host-base-url", default=DEFAULT_CONTEXTFORGE_HOST_BASE_URL)
    parser.add_argument("--contextforge-container-base-url", default=DEFAULT_CONTEXTFORGE_CONTAINER_BASE_URL)
    args = parser.parse_args(argv)
    if args.timeout < 90:
        raise SystemExit("--timeout must be at least 90 seconds")

    uc1 = load_uc1_module()
    repo_root = Path(__file__).resolve().parents[3]
    harness_root = repo_root / "docker" / "client-harness"
    lock_file = uc1.acquire_harness_lock(harness_root)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = safe_run_suffix(args.run_suffix)
    run_id = timestamp if not suffix else f"{timestamp}-{suffix}"
    output_root = harness_root / "evidence" / "known-service-management-state-story" / args.client / run_id
    output_root.mkdir(parents=True, exist_ok=True)
    container = f"cf-service-state-{args.client}-{run_id.lower().replace('z', '').replace('_', '-')}"
    session_id = default_session_id(args.client, run_id)
    commands: list[dict[str, Any]] = []
    launched = False
    try:
        qwen_env, qwen_summary = qwen_launch_env(harness_root)
        client_scoped_dir, client_scoped_summary = write_client_scoped_env(
            output_root,
            gateway_container=args.contextforge_gateway_container,
            host_base_url=args.contextforge_host_base_url,
            container_base_url=args.contextforge_container_base_url,
        )
        compose_env = {
            "CONTEXTFORGE_CLIENT_HARNESS_CLIENT_SCOPED": str(client_scoped_dir),
            "OPENAI_API_KEY": "",
            "CODEX_API_KEY": "",
            "ANTHROPIC_API_KEY": "",
            "OPENROUTER_API_KEY": "",
            "GOOGLE_API_KEY": "",
            "GEMINI_API_KEY": "",
            "PERPLEXITY_API_KEY": "",
            "EXA_API_KEY": "",
            "CONTEXT7_API_KEY": "",
            "CONTEXTFORGE_REDACT_VALUES": os.environ.get("CONTEXTFORGE_REDACT_VALUES", ""),
        }
        reset = uc1.run(
            [
                sys.executable,
                str(harness_root / "scripts" / "reset-client-harness-state.py"),
                "--client",
                uc1.reset_client_name(args.client),
                "--reset-home-volume",
            ],
            cwd=repo_root,
            timeout=120,
            commands=commands,
        )
        reset_json = uc1.parse_json_or_text(reset["stdout"])
        if not args.no_build:
            uc1.run(
                ["docker", "compose", "-f", str(harness_root / "compose.yml"), "build", "base", uc1.build_service_name(args.client)],
                cwd=repo_root,
                timeout=600,
                commands=commands,
                env=compose_env,
            )
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
        for key, value in sorted(qwen_env.items()):
            launch_command.extend(["-e", f"{key}={value}"])
        launch_command.extend([uc1.compose_service_name(args.client), "sleep", "infinity"])
        launch = uc1.run(launch_command, cwd=repo_root, timeout=120, commands=commands, env=compose_env)
        launched = launch["returncode"] == 0
        runtime = uc1.run(
            ["docker", "exec", container, "bash", "-lc", uc1.runtime_readback_command(args.client)],
            cwd=repo_root,
            timeout=120,
            commands=commands,
        )
        turns: list[dict[str, Any]] = []
        for index, prompt in enumerate(STATE_STORY_PROMPTS, start=1):
            session_id, turn = run_turn(
                uc1,
                client=args.client,
                container=container,
                session_id=session_id,
                prompt=prompt,
                turn_index=index,
                output_root=output_root,
                repo_root=repo_root,
                timeout=args.timeout,
                commands=commands,
            )
            turns.append(turn)
        final_state = json.loads((output_root / f"turn-{len(STATE_STORY_PROMPTS):02d}.state.json").read_text(encoding="utf-8"))
        structural_checks = {
            "all_turn_commands_completed": all(turn["returncode"] == 0 and not turn["timeout"] for turn in turns),
            "all_state_readbacks_completed": all(turn["state_returncode"] == 0 for turn in turns),
            "final_state_exists": bool(final_state.get("state_exists")),
            "final_all_expected_present": not bool(final_state.get("missing_expected")),
            "operation_set_sizes_declared": [1, 3, "all"],
            "operation_types_declared": ["list", "details", "enable", "disable", "remove", "repair", "status"],
            "long_story_minimum_changes": ">=5 configuration changes expected; manual/semantic review must confirm from transcripts and readbacks",
        }
        summary = {
            "schema_uri": "contextforge://client-harness/known-service-management-state-story-run/v1",
            "ok_scope": "runner completed; manual inspection and semantic evaluator review required for assistant-behavior acceptance",
            "semantic_acceptance": "requires_manual_or_non_spark_evaluator_review",
            "deterministic_semantic_oracles_allowed": False,
            "client": args.client,
            "model_requirement": "qwen_only",
            "semantic_model": redact_value(qwen_summary),
            "timestamp": timestamp,
            "run_id": run_id,
            "container": container,
            "session_id": session_id,
            "output_root": str(output_root),
            "client_scoped_env": redact_value(client_scoped_summary),
            "reset": reset_json,
            "runtime_returncode": runtime["returncode"],
            "prompts": STATE_STORY_PROMPTS,
            "expected_service_bindings": EXPECTED_SERVICE_BINDINGS,
            "turns": turns,
            "final_state": final_state,
            "structural_checks": structural_checks,
            "acceptance_matrix": {
                "target_client": args.client,
                "model": "local llama.cpp qwen3.6-a3b",
                "operation_types": ["list", "details", "enable", "disable", "remove", "repair", "status"],
                "enable_set_sizes": ["1 service", "3 services", "all services"],
                "long_state_story": [
                    "install 3 services",
                    "disable one of the three",
                    "disable another of the three",
                    "install 3 more",
                    "disable all",
                    "enable all",
                ],
            },
            "manual_review_required": [
                "confirm qwen used the helper-visible ContextForge service management tools rather than shell/file substitutes",
                "confirm each requested operation was semantically understood and completed or transparently blocked",
                "confirm state emerged, persisted, and mutated coherently across the single session",
                "inspect configuration/state files after the run, especially final .project/context_forge_state.json and client config",
                "confirm user-facing text stayed concise and did not revive validation rituals",
            ],
            "command_ledger": redact_value(commands),
        }
        write_json(output_root / "run-summary.json", redact_value(summary))
        print(json.dumps(redact_value(summary), indent=2, sort_keys=True))
        return 0 if all(structural_checks[key] for key in ("all_turn_commands_completed", "all_state_readbacks_completed", "final_state_exists", "final_all_expected_present")) else 1
    finally:
        if launched:
            uc1.run(["docker", "rm", "-f", container], cwd=repo_root, timeout=30, commands=commands)
        try:
            shutil.rmtree(output_root / "client-scoped")
        except FileNotFoundError:
            pass
        lock_file.close()


if __name__ == "__main__":
    raise SystemExit(main())
