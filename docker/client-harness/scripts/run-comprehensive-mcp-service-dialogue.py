#!/usr/bin/env python3
"""Run one comprehensive MCP service test through a real Pi/OpenCode client."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


DEFAULT_SERENA_LANGUAGE = "python"
DEFAULT_CONTEXTFORGE_HOST_BASE_URL = "http://127.0.0.1:4445"
DEFAULT_CONTEXTFORGE_CONTAINER_BASE_URL = "http://host.docker.internal:4445"
SCOPED_TOKEN_PERMISSIONS = [
    "servers.use",
    "tools.read",
    "tools.execute",
    "resources.read",
    "prompts.read",
]


def load_uc1_module() -> Any:
    path = Path(__file__).with_name("run-use-case-1-dialogue.py")
    spec = importlib.util.spec_from_file_location("use_case_1_runner", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_service_map(harness_root: Path) -> dict[str, dict[str, Any]]:
    data = json.loads((harness_root / "comprehensive-mcp-testing-services.json").read_text(encoding="utf-8"))
    return {str(item["slug"]): item for item in data["services"]}


def default_session_id(client: str, service: str, phase: str, timestamp: str) -> str:
    compact = timestamp.lower().replace("t", "").replace("z", "")
    if client == "opencode":
        safe = service.replace("-", "_")
        return f"ses_mcp_{safe}_{phase}_{compact}"
    return f"mcp-{service}-{phase}-{timestamp}"


def service_test_prompt(service: str, display: str, issue: int, global_issue: int) -> str:
    return (
        f"Test the {display} MCP service now. "
        "Use the MCP tools already exposed in this assistant session; do not use shell scripts, package installs, or direct upstream calls as substitutes. "
        "Use each safe function once if visible. "
        "Skip mutating functions unless there is a dry-run or no-op target. "
        "If the service tools are not visible, say that directly. "
        "Do not test unrelated services or governance routes. "
        "Keep the report under 20 lines with function, result, and issue target "
        f"(#{issue} for {service}, #{global_issue} for shared wrapper/client problems)."
    )


def activation_prompts(service: str, display: str) -> list[str]:
    prompts = ["hello", display]
    if service == "serena":
        prompts.append(DEFAULT_SERENA_LANGUAGE)
    prompts.append("approve")
    return prompts


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value.strip().strip("\"'")
    return values


def request_json(
    method: str,
    base_url: str,
    path: str,
    *,
    token: str | None = None,
    body: dict[str, Any] | None = None,
) -> Any:
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
        detail = exc.read().decode(errors="replace")
        raise RuntimeError(f"{method} {path} failed: HTTP {exc.code} {exc.reason}: {detail}") from exc
    return json.loads(payload) if payload else None


def items(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        return data["items"]
    if isinstance(data, list):
        return data
    return []


def login(base_url: str, env_file: Path) -> str:
    env = read_env(env_file)
    email = env.get("PLATFORM_ADMIN_EMAIL")
    password = env.get("PLATFORM_ADMIN_PASSWORD")
    if not email or not password:
        raise RuntimeError(f"missing PLATFORM_ADMIN_EMAIL or PLATFORM_ADMIN_PASSWORD in {env_file}")
    response = request_json("POST", base_url, "/auth/login", body={"email": email, "password": password})
    token = response.get("access_token") if isinstance(response, dict) else None
    if not isinstance(token, str) or not token:
        raise RuntimeError("ContextForge login did not return an access token")
    return token


def virtual_server(base_url: str, admin_token: str, server_name: str) -> dict[str, Any]:
    servers = items(request_json("GET", base_url, "/servers?include_inactive=true&limit=1000", token=admin_token))
    matches = [server for server in servers if server.get("name") == server_name]
    if len(matches) != 1:
        raise RuntimeError(f"expected one virtual server named {server_name!r}, found {len(matches)}")
    return matches[0]


def create_probe_token(base_url: str, admin_token: str, server_id: str, service: str) -> tuple[str, str]:
    response = request_json(
        "POST",
        base_url,
        "/tokens",
        token=admin_token,
        body={
            "name": f"comprehensive-mcp-{service}-{uuid4().hex[:12]}",
            "description": f"Ephemeral comprehensive MCP dialogue token for {service}.",
            "expires_in_days": 1,
            "scope": {
                "server_id": server_id,
                "permissions": SCOPED_TOKEN_PERMISSIONS,
            },
            "tags": ["contextforge", "comprehensive-mcp", service, "probe", "ephemeral"],
        },
    )
    token_record = response.get("token") if isinstance(response, dict) else None
    token_id = token_record.get("id") if isinstance(token_record, dict) else None
    access_token = response.get("access_token") if isinstance(response, dict) else None
    if not isinstance(token_id, str) or not token_id:
        raise RuntimeError("ContextForge token create did not return token.id")
    if not isinstance(access_token, str) or not access_token:
        raise RuntimeError("ContextForge token create did not return access_token")
    return token_id, access_token


def revoke_probe_token(base_url: str, admin_token: str, token_id: str) -> None:
    request_json(
        "DELETE",
        base_url,
        f"/tokens/{token_id}",
        token=admin_token,
        body={"reason": "comprehensive MCP dialogue test complete"},
    )


def write_scoped_env(container_base_url: str, server_id: str, access_token: str) -> Path:
    handle = tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        prefix="contextforge-comprehensive-mcp-token-",
        suffix=".env",
        delete=False,
    )
    path = Path(handle.name)
    try:
        handle.write(f"CONTEXTFORGE_BASE_URL={container_base_url}\n")
        handle.write(f"CONTEXTFORGE_SERVER_ID={server_id}\n")
        handle.write(f"CONTEXTFORGE_BEARER_TOKEN={access_token}\n")
        handle.write("CONTEXTFORGE_CONFIG_ENV=/tmp/missing-contextforge.env\n")
        handle.write("CONTEXTFORGE_TOKEN_CACHE=/tmp/contextforge-wrapper-token.local.json\n")
        handle.write("CONTEXTFORGE_TOKEN_LOCK=/tmp/contextforge-wrapper-token.local.json.lock\n")
    finally:
        handle.close()
    os.chmod(path, 0o600)
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client", choices=["pi", "opencode"], required=True)
    parser.add_argument("--service", required=True)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--no-build", action="store_true")
    parser.add_argument("--contextforge-host-base-url", default=os.environ.get("CONTEXTFORGE_HOST_BASE_URL", DEFAULT_CONTEXTFORGE_HOST_BASE_URL))
    parser.add_argument("--contextforge-container-base-url", default=os.environ.get("CONTEXTFORGE_CONTAINER_BASE_URL", DEFAULT_CONTEXTFORGE_CONTAINER_BASE_URL))
    parser.add_argument(
        "--contextforge-env-file",
        type=Path,
        default=Path(os.environ["CONTEXTFORGE_DEV_ENV_FILE"]) if os.environ.get("CONTEXTFORGE_DEV_ENV_FILE") else None,
    )
    args = parser.parse_args(argv)
    if args.timeout < 90:
        raise SystemExit("--timeout must be at least 90 seconds")

    uc1 = load_uc1_module()
    repo_root = Path(__file__).resolve().parents[3]
    harness_root = repo_root / "docker" / "client-harness"
    service_map = load_service_map(harness_root)
    if args.service not in service_map:
        raise SystemExit(f"unknown service {args.service!r}; see comprehensive-mcp-testing-services.json")
    service = service_map[args.service]
    global_issue = 316

    lock_file = uc1.acquire_harness_lock(harness_root)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_root = harness_root / "evidence" / "comprehensive-mcp" / args.service / args.client / timestamp
    output_root.mkdir(parents=True, exist_ok=True)
    container = f"cf-mcp-{args.service[:18].replace('-', '')}-{args.client}-{timestamp.lower().replace('z', '')}"
    activation_session = default_session_id(args.client, args.service, "activate", timestamp)
    test_session = default_session_id(args.client, args.service, "test", timestamp)
    commands: list[dict[str, Any]] = []
    admin_token = ""
    scoped_token_id = ""
    scoped_env_file: Path | None = None
    scoped_server_id = ""
    scoped_token_revoked = False

    try:
        virtual_server_name = str(service.get("virtual_server") or "")
        if virtual_server_name:
            if args.contextforge_env_file is None or not args.contextforge_env_file.exists():
                raise RuntimeError(
                    "comprehensive MCP client-visible tests require --contextforge-env-file "
                    "or CONTEXTFORGE_DEV_ENV_FILE pointing at an ignored harness env file"
                )
            admin_token = login(args.contextforge_host_base_url, args.contextforge_env_file)
            server = virtual_server(args.contextforge_host_base_url, admin_token, virtual_server_name)
            scoped_server_id = str(server["id"])
            scoped_token_id, access_token = create_probe_token(
                args.contextforge_host_base_url,
                admin_token,
                scoped_server_id,
                args.service,
            )
            scoped_env_file = write_scoped_env(args.contextforge_container_base_url, scoped_server_id, access_token)

        reset = uc1.run(
            [
                sys.executable,
                str(harness_root / "scripts" / "reset-client-harness-state.py"),
                "--client",
                uc1.reset_client_name(args.client),
                "--reset-home-volume",
                "--evidence-dir",
                "docker/client-harness/evidence/comprehensive-mcp/prior",
            ],
            cwd=repo_root,
            timeout=120,
            commands=commands,
        )
        reset_json = uc1.parse_json_or_text(reset["stdout"])

        local_env = harness_root / "env" / "local-llama.env"
        if not local_env.exists():
            uc1.run([str(harness_root / "scripts" / "make-local-llama-env.sh")], cwd=harness_root, timeout=60, commands=commands)

        build_result = None
        if not args.no_build:
            build_result = uc1.run(
                ["docker", "compose", "-f", str(harness_root / "compose.yml"), "build", "base", uc1.build_service_name(args.client)],
                cwd=repo_root,
                timeout=600,
                commands=commands,
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
        if scoped_env_file is not None:
            launch_command.extend(["--env-from-file", str(scoped_env_file)])
        launch_command.extend([uc1.compose_service_name(args.client), "sleep", "infinity"])
        launch = uc1.run(
            launch_command,
            cwd=repo_root,
            timeout=120,
            commands=commands,
        )
        runtime = uc1.run(
            ["docker", "exec", container, "bash", "-lc", uc1.runtime_readback_command(args.client)],
            cwd=repo_root,
            timeout=120,
            commands=commands,
        )

        turns: list[dict[str, Any]] = []
        prompts = activation_prompts(args.service, str(service["display"]))
        for index, prompt in enumerate(prompts, start=1):
            command = uc1.target_client_command(
                args.client,
                activation_session,
                prompt,
                create_session=args.client == "opencode" and index == 1,
            )
            result = uc1.run(["docker", "exec", container, "bash", "-lc", command], cwd=repo_root, timeout=args.timeout, commands=commands)
            path = output_root / f"activation-turn-{index}.raw.txt"
            path.write_text(uc1.render_command_block(result), encoding="utf-8")
            turns.append({"phase": "activation", "turn": index, "prompt": prompt, "path": str(path), **result})
            if args.client == "opencode" and index == 1:
                discovered = uc1.extract_opencode_session_id(str(result.get("stdout") or ""))
                if discovered:
                    activation_session = discovered

        prompt = service_test_prompt(args.service, str(service["display"]), int(service["issue"]), global_issue)
        command = uc1.target_client_command(
            args.client,
            test_session,
            prompt,
            create_session=args.client == "opencode",
        )
        result = uc1.run(["docker", "exec", container, "bash", "-lc", command], cwd=repo_root, timeout=args.timeout, commands=commands)
        path = output_root / "service-test-turn.raw.txt"
        path.write_text(uc1.render_command_block(result), encoding="utf-8")
        turns.append({"phase": "service_test", "turn": 1, "prompt": prompt, "path": str(path), **result})
        if args.client == "opencode":
            discovered = uc1.extract_opencode_session_id(str(result.get("stdout") or ""))
            if discovered:
                test_session = discovered

        if scoped_token_id and admin_token:
            revoke_probe_token(args.contextforge_host_base_url, admin_token, scoped_token_id)
            scoped_token_revoked = True

        summary = {
            "schema_uri": "contextforge://client-harness/comprehensive-mcp-service-dialogue-run/v1",
            "ok_scope": "runner completed; semantic acceptance requires evaluator review",
            "semantic_acceptance": "requires_non_spark_evaluator",
            "client": args.client,
            "service": args.service,
            "service_issue": service["issue"],
            "global_issue": global_issue,
            "timestamp": timestamp,
            "container": container,
            "activation_session": activation_session,
            "test_session": test_session,
            "activation_prompts": prompts,
            "output_root": str(output_root),
            "contextforge": {
                "host_base_url": args.contextforge_host_base_url,
                "container_base_url": args.contextforge_container_base_url,
                "virtual_server": service.get("virtual_server"),
                "server_id": scoped_server_id or None,
                "probe_token_id": scoped_token_id or None,
                "probe_token_env_file": str(scoped_env_file) if scoped_env_file is not None else None,
                "probe_token_revoked": scoped_token_revoked,
            },
            "reset": reset_json,
            "build_returncode": None if build_result is None else build_result["returncode"],
            "launch_returncode": launch["returncode"],
            "runtime_returncode": runtime["returncode"],
            "turns": [
                {
                    "phase": turn["phase"],
                    "turn": turn["turn"],
                    "prompt": turn["prompt"],
                    "path": turn["path"],
                    "returncode": turn["returncode"],
                    "timeout": turn["timeout"],
                }
                for turn in turns
            ],
            "command_ledger": commands,
            "deterministic_non_actions": [
                "runner does not score free-form assistant prose",
                "runner does not mutate host/global client config",
                "runner does not call service tools directly outside the tested client",
                "runner does not update GitHub issues or Project fields",
            ],
            "evaluator_required_narrative": [
                "judge whether all safe functions were actually exercised",
                "reject direct upstream package execution or shell-emulated MCP calls as substitutes for client-visible ContextForge tools",
                "separate service-specific defects from cross-service wrapper/client defects",
                "triage findings to the service issue or #316",
                "identify any mutating functions skipped with acceptable rationale",
                "classify qwen context-window or timeout failures as runner/package defects unless isolated to one service",
            ],
        }
        write_json(output_root / "run-summary.json", summary)
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0 if all(not turn["timeout"] and turn["returncode"] == 0 for turn in turns) else 1
    finally:
        if scoped_env_file is not None:
            try:
                scoped_env_file.unlink(missing_ok=True)
            except OSError:
                pass
        if scoped_token_id and admin_token and not scoped_token_revoked:
            try:
                revoke_probe_token(args.contextforge_host_base_url, admin_token, scoped_token_id)
            except Exception as exc:  # pragma: no cover - best-effort cleanup path
                print(f"warning: failed to revoke probe token {scoped_token_id}: {exc}", file=sys.stderr)
        lock_file.close()


if __name__ == "__main__":
    raise SystemExit(main())
