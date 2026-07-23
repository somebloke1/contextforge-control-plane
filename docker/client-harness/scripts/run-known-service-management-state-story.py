#!/usr/bin/env python3
"""Run a Luna/medium known-service management state story in Pi or OpenCode."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from harness_redaction import redact_text, redact_value

SEMANTIC_MODEL_ENV = Path("env/semantic-model.env")
DEFAULT_CONTEXTFORGE_GATEWAY_CONTAINER = "contextforge-harness-contextforge-gateway-1"
DEFAULT_CONTEXTFORGE_HOST_BASE_URL = "http://127.0.0.1:4445"
DEFAULT_CONTEXTFORGE_CONTAINER_BASE_URL = "http://host.docker.internal:4445"
WRAPPER_TOKEN_CACHE = "/tmp/contextforge-wrapper-token.local.json"
WRAPPER_TOKEN_LOCK = "/tmp/contextforge-wrapper-token.local.json.lock"
SESS_OBS_STATE_PATH = Path.home() / ".sess-obs.json"
SESS_OBS_STREAM_NAME = "sess-obs-stream.jsonl"
SCOPED_TOKEN_PERMISSIONS = [
    "resources.read",
    "servers.read",
    "gateways.read",
    "tools.read",
    "prompts.read",
]

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


def create_client_scoped_token(*, host_base_url: str, admin_token: str, run_id: str) -> tuple[str, str, dict[str, Any]]:
    response = request_json(
        "POST",
        host_base_url,
        "/tokens",
        token=admin_token,
        body={
            "name": f"known-service-state-story-{run_id}-{uuid4().hex[:10]}",
            "description": "Ephemeral known-service management state-story token.",
            "expires_in_days": 1,
            "scope": {"permissions": SCOPED_TOKEN_PERMISSIONS},
            "tags": ["contextforge", "known-service-state-story", "client-harness", "ephemeral"],
        },
    )
    token_record = response.get("token") if isinstance(response, dict) else None
    token_id = token_record.get("id") if isinstance(token_record, dict) else None
    access_token = response.get("access_token") if isinstance(response, dict) else None
    if not isinstance(token_id, str) or not token_id:
        raise RuntimeError("ContextForge token create did not return token.id")
    if not isinstance(access_token, str) or not access_token:
        raise RuntimeError("ContextForge token create did not return access_token")
    return token_id, access_token, {
        "token_id": token_id,
        "expires_in_days": 1,
        "permissions": SCOPED_TOKEN_PERMISSIONS,
        "token_present": True,
    }


def revoke_client_scoped_token(*, host_base_url: str, admin_token: str, token_id: str) -> None:
    request_json(
        "DELETE",
        host_base_url,
        f"/tokens/{token_id}",
        token=admin_token,
        body={"reason": "known service management state-story run complete"},
    )


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_jsonl(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(redact_value(data), sort_keys=True) + "\n")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def write_sess_obs_state(
    output_root: Path,
    *,
    client: str,
    run_id: str,
    session_id: str,
    container: str,
    status: str,
    current_turn: int | None = None,
    current_prompt: str | None = None,
) -> None:
    stream_path = str(output_root / SESS_OBS_STREAM_NAME)
    last_offset = 0
    last_raw_files: list[str] = []
    try:
        existing = json.loads(SESS_OBS_STATE_PATH.read_text(encoding="utf-8"))
        if isinstance(existing, dict) and existing.get("stream_path") == stream_path:
            last_offset = int(existing.get("last_offset") or 0)
            last_raw_files = [str(item) for item in existing.get("last_raw_files", []) if isinstance(item, str)]
    except Exception:
        pass
    state = {
        "version": 1,
        "source_type": "semantic_test_session",
        "client_type": client,
        "session_id": session_id,
        "run_id": run_id,
        "container": container,
        "output_root": str(output_root),
        "stream_path": stream_path,
        "summary_path": str(output_root / "run-summary.json"),
        "raw_glob": str(output_root / "turn-*.raw.txt"),
        "status": status,
        "current_turn": current_turn,
        "current_prompt": current_prompt,
        "runner_pid": os.getpid(),
        "updated_at": utc_now_iso(),
        "last_offset": last_offset,
        "last_raw_files": last_raw_files,
    }
    tmp = SESS_OBS_STATE_PATH.with_suffix(SESS_OBS_STATE_PATH.suffix + ".tmp")
    tmp.write_text(json.dumps(redact_value(state), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, SESS_OBS_STATE_PATH)


def sess_obs_event(
    output_root: Path,
    event_type: str,
    text: str = "",
    *,
    client: str,
    run_id: str,
    session_id: str,
    turn_index: int | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    payload: dict[str, Any] = {
        "type": event_type,
        "client_type": client,
        "run_id": run_id,
        "session_id": session_id,
        "turn": turn_index,
        "text": text,
        "timestamp": utc_now_iso(),
    }
    if extra:
        payload.update(extra)
    append_jsonl(output_root / SESS_OBS_STREAM_NAME, payload)


def safe_run_suffix(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-")


def default_session_id(client: str, timestamp: str) -> str:
    compact = timestamp.lower().replace("t", "").replace("z", "")
    if client == "opencode":
        return f"ses_service_state_{compact}"
    return f"service-state-{client}-{timestamp}"


def luna_launch_env(harness_root: Path) -> tuple[dict[str, str], dict[str, Any], Path]:
    env_path = harness_root / SEMANTIC_MODEL_ENV
    env = read_env(env_path)
    required = ["LITELLM_BASE_URL", "LITELLM_API_KEY"]
    missing = [key for key in required if not env.get(key)]
    if missing:
        raise RuntimeError(f"{env_path} missing required keys: {', '.join(missing)}")
    if env["LITELLM_BASE_URL"].rstrip("/") != "http://host.docker.internal:3333/v1":
        raise RuntimeError(f"{env_path} must use sandbox LiteLLM on host.docker.internal:3333")
    expected = {
        "CONTEXTFORGE_PI_DEFAULT_PROVIDER": "litellm",
        "CONTEXTFORGE_PI_DEFAULT_MODEL": "codex/gpt-5.6-luna",
        "CONTEXTFORGE_PI_DEFAULT_THINKING": "medium",
        "CONTEXTFORGE_OPENCODE_DEFAULT_MODEL": "litellm/codex/gpt-5.6-luna",
        "CONTEXTFORGE_OPENCODE_SMALL_MODEL": "litellm/codex/gpt-5.6-luna",
        "CONTEXTFORGE_OPENCODE_DEFAULT_VARIANT": "medium",
    }
    drift = {key: env.get(key) for key, value in expected.items() if env.get(key) != value}
    if drift:
        raise RuntimeError(f"{env_path} does not provide the Luna/medium sandbox contract: {drift!r}")
    launch_env = {
        "CONTEXTFORGE_TEST_PROVIDER": "LiteLLM",
        "CONTEXTFORGE_TEST_PROVIDER_KIND": "litellm",
        "CONTEXTFORGE_TEST_MODEL": "codex/gpt-5.6-luna",
        "CONTEXTFORGE_TEST_MODEL_NAME": "GPT-5.6 Luna via LiteLLM",
        "CONTEXTFORGE_TEST_CONTEXT_WINDOW": "1050000",
        **expected,
    }
    summary = {
        "provider_kind": "litellm",
        "provider_label": "LiteLLM",
        "model": "codex/gpt-5.6-luna",
        "display_name": "GPT-5.6 Luna via LiteLLM",
        "semantic_role": "blind",
        "reasoning_effort": "medium",
        "base_url": env["LITELLM_BASE_URL"],
        "api_key_present": True,
        "api_key_delivered_to_container": True,
        "api_key_delivery_reason": "the ignored semantic model env file is passed directly to the container",
    }
    return launch_env, summary, env_path


def write_client_scoped_env(
    run_root: Path,
    *,
    gateway_container: str,
    host_base_url: str,
    container_base_url: str,
    run_id: str,
) -> tuple[Path, dict[str, Any], dict[str, str]]:
    admin_token, auth_summary = contextforge_login_token(gateway_container=gateway_container, host_base_url=host_base_url)
    token_id, token, token_summary = create_client_scoped_token(
        host_base_url=host_base_url,
        admin_token=admin_token,
        run_id=run_id,
    )
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
        "token_source": "contextforge_harness_ephemeral_scoped_token",
        "auth": auth_summary,
        "scoped_token": token_summary,
        "shared_harness_env_mutated": False,
    }, {
        "host_base_url": host_base_url.rstrip("/"),
        "gateway_container": gateway_container,
        "admin_token": admin_token,
        "token_id": token_id,
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


def extract_session_id_from_line(line: str) -> str:
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        event = None
    if isinstance(event, dict):
        for key in ("sessionID", "session_id"):
            value = event.get(key)
            if isinstance(value, str) and value:
                return value
        part = event.get("part")
        if isinstance(part, dict):
            value = part.get("sessionID")
            if isinstance(value, str) and value:
                return value
        if event.get("type") == "session":
            value = event.get("id")
            if isinstance(value, str) and value:
                return value
    match = re.search(r'"sessionID"\s*:\s*"([^"]+)"', line)
    if match:
        return match.group(1)
    match = re.search(r"\bses_[A-Za-z0-9_:-]+", line)
    return match.group(0) if match else ""


def sess_obs_events_from_stdout_line(client: str, line: str) -> list[tuple[str, str]]:
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        return []
    if not isinstance(event, dict):
        return []
    events: list[tuple[str, str]] = []
    if client == "opencode":
        part = event.get("part")
        if isinstance(part, dict):
            part_type = part.get("type")
            if event.get("type") == "text" or part_type == "text":
                text = str(part.get("text") or "")
                if text:
                    events.append(("assistant", text))
            elif part_type in {"thinking", "reasoning"}:
                text = str(part.get("text") or part.get("thinking") or "")
                if text:
                    events.append(("thinking", text))
        return events
    if client == "pi" and event.get("type") == "message_end":
        message = event.get("message")
        if isinstance(message, dict) and message.get("role") == "assistant":
            content = message.get("content")
            if isinstance(content, list):
                assistant_parts: list[str] = []
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "thinking":
                        if assistant_parts:
                            events.append(("assistant", "\n".join(part for part in assistant_parts if part)))
                            assistant_parts = []
                        thinking = str(block.get("thinking") or "")
                        if thinking:
                            events.append(("thinking", thinking))
                    elif block.get("type") == "text":
                        assistant_parts.append(str(block.get("text") or ""))
                if assistant_parts:
                    events.append(("assistant", "\n".join(part for part in assistant_parts if part)))
            elif isinstance(content, str) and content:
                events.append(("assistant", content))
    return events


def read_pipe_lines(pipe: Any, name: str, output: "queue.Queue[tuple[str, str | None]]") -> None:
    try:
        for line in iter(pipe.readline, ""):
            output.put((name, line))
    finally:
        output.put((name, None))


def run_observed_client_command(
    uc1: Any,
    cmd: list[str],
    *,
    cwd: Path,
    timeout: int,
    commands: list[dict[str, Any]],
    client: str,
    output_root: Path,
    run_id: str,
    session_id: str,
    container: str,
    turn_index: int,
) -> tuple[str, dict[str, Any]]:
    command_text = uc1.shell_join(cmd)
    stdout_parts: list[str] = []
    stderr_parts: list[str] = []
    seen_session_id = session_id
    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    output: "queue.Queue[tuple[str, str | None]]" = queue.Queue()
    threads = [
        threading.Thread(target=read_pipe_lines, args=(proc.stdout, "stdout", output), daemon=True),
        threading.Thread(target=read_pipe_lines, args=(proc.stderr, "stderr", output), daemon=True),
    ]
    for thread in threads:
        thread.start()
    deadline = time.monotonic() + timeout
    finished_streams: set[str] = set()
    timed_out = False
    while len(finished_streams) < 2:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            timed_out = True
            proc.kill()
            break
        try:
            stream_name, line = output.get(timeout=min(0.2, remaining))
        except queue.Empty:
            continue
        if line is None:
            finished_streams.add(stream_name)
            continue
        if stream_name == "stdout":
            stdout_parts.append(line)
            discovered = extract_session_id_from_line(line)
            if discovered and discovered != seen_session_id:
                seen_session_id = discovered
                write_sess_obs_state(
                    output_root,
                    client=client,
                    run_id=run_id,
                    session_id=seen_session_id,
                    container=container,
                    status="running",
                    current_turn=turn_index,
                )
            for event_type, text in sess_obs_events_from_stdout_line(client, line):
                sess_obs_event(
                    output_root,
                    event_type,
                    text,
                    client=client,
                    run_id=run_id,
                    session_id=seen_session_id,
                    turn_index=turn_index,
                )
        else:
            stderr_parts.append(line)
    try:
        returncode = proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        timed_out = True
        proc.kill()
        returncode = proc.wait(timeout=5)
    for thread in threads:
        thread.join(timeout=1)
    while not output.empty():
        stream_name, line = output.get_nowait()
        if line is None:
            continue
        if stream_name == "stdout":
            stdout_parts.append(line)
        else:
            stderr_parts.append(line)
    result = {
        "command": cmd,
        "command_text": command_text,
        "cwd": str(cwd),
        "returncode": 124 if timed_out else returncode,
        "stdout": redact_text("".join(stdout_parts)),
        "stderr": redact_text("".join(stderr_parts)),
        "timeout": timed_out,
    }
    if timed_out:
        cleanup = uc1.run_timeout_cleanup(cmd, cwd=cwd, env=None)
        if cleanup is not None:
            result["timeout_cleanup"] = cleanup
    commands.append({key: result[key] for key in ("command_text", "cwd", "returncode", "timeout")})
    if result.get("timeout_cleanup"):
        cleanup = dict(result["timeout_cleanup"])
        cleanup["cwd"] = str(cwd)
        commands.append({key: cleanup[key] for key in ("command_text", "cwd", "returncode", "timeout")})
    return seen_session_id, result


def run_turn(
    uc1: Any,
    *,
    client: str,
    container: str,
    session_id: str,
    run_id: str,
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
    write_sess_obs_state(
        output_root,
        client=client,
        run_id=run_id,
        session_id=session_id,
        container=container,
        status="running",
        current_turn=turn_index,
        current_prompt=prompt,
    )
    sess_obs_event(
        output_root,
        "prompt",
        prompt,
        client=client,
        run_id=run_id,
        session_id=session_id,
        turn_index=turn_index,
    )
    session_id, result = run_observed_client_command(
        uc1,
        ["docker", "exec", container, "bash", "-lc", command],
        cwd=repo_root,
        timeout=timeout,
        commands=commands,
        client=client,
        output_root=output_root,
        run_id=run_id,
        session_id=session_id,
        container=container,
        turn_index=turn_index,
    )
    raw_path = output_root / f"turn-{turn_index:02d}.raw.txt"
    raw_path.write_text(uc1.render_command_block(result), encoding="utf-8")
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
    scoped_token_revoke: dict[str, str] | None = None
    write_sess_obs_state(
        output_root,
        client=args.client,
        run_id=run_id,
        session_id=session_id,
        container=container,
        status="initializing",
    )
    sess_obs_event(
        output_root,
        "session",
        client=args.client,
        run_id=run_id,
        session_id=session_id,
        extra={"status": "initializing", "output_root": str(output_root)},
    )
    try:
        uc1.ensure_semantic_model_env(harness_root, client=args.client, commands=commands, runner=uc1.run)
        semantic_env, semantic_summary, semantic_env_path = luna_launch_env(harness_root)
        client_scoped_dir, client_scoped_summary, scoped_token_revoke = write_client_scoped_env(
            output_root,
            gateway_container=args.contextforge_gateway_container,
            host_base_url=args.contextforge_host_base_url,
            container_base_url=args.contextforge_container_base_url,
            run_id=run_id,
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
            "--env-file",
            str(semantic_env_path),
            "run",
            "--name",
            container,
            "--no-deps",
            "-d",
        ]
        for key, value in sorted(semantic_env.items()):
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
                run_id=run_id,
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
            "model_requirement": "luna_medium_via_litellm",
            "semantic_model": redact_value(semantic_summary),
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
                "model": "codex/gpt-5.6-luna via LiteLLM with medium reasoning",
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
                "confirm Luna used the helper-visible ContextForge service management tools rather than shell/file substitutes",
                "confirm each requested operation was semantically understood and completed or transparently blocked",
                "confirm state emerged, persisted, and mutated coherently across the single session",
                "inspect configuration/state files after the run, especially final .project/context_forge_state.json and client config",
                "confirm user-facing text stayed concise and did not revive validation rituals",
            ],
            "command_ledger": redact_value(commands),
        }
        write_json(output_root / "run-summary.json", redact_value(summary))
        final_status = "complete" if all(structural_checks[key] for key in ("all_turn_commands_completed", "all_state_readbacks_completed", "final_state_exists", "final_all_expected_present")) else "failed"
        write_sess_obs_state(
            output_root,
            client=args.client,
            run_id=run_id,
            session_id=session_id,
            container=container,
            status=final_status,
            current_turn=len(STATE_STORY_PROMPTS),
        )
        sess_obs_event(
            output_root,
            "session",
            client=args.client,
            run_id=run_id,
            session_id=session_id,
            extra={"status": final_status, "output_root": str(output_root)},
        )
        print(json.dumps(redact_value(summary), indent=2, sort_keys=True))
        return 0 if final_status == "complete" else 1
    finally:
        if launched:
            uc1.run(["docker", "rm", "-f", container], cwd=repo_root, timeout=30, commands=commands)
        if scoped_token_revoke is not None:
            try:
                revoke_client_scoped_token(
                    host_base_url=scoped_token_revoke["host_base_url"],
                    admin_token=scoped_token_revoke["admin_token"],
                    token_id=scoped_token_revoke["token_id"],
                )
            except Exception:
                pass
        try:
            shutil.rmtree(output_root / "client-scoped")
        except FileNotFoundError:
            pass
        lock_file.close()


if __name__ == "__main__":
    raise SystemExit(main())
