#!/usr/bin/env python3
"""Run one comprehensive MCP service test through a real Pi/OpenCode client."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
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
    if service == "context7":
        return (
            "Please use this project's documentation lookup capability to answer: "
            "In current Next.js, how should Server Actions handle authentication? "
            "Keep the answer concise and cite the documentation source you used."
        )
    return (
        f"Please use the project's {display} capability for a small ordinary task that fits it. "
        "Keep the answer concise and mention any limitation that prevents completion."
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


CLIENT_SCOPED_ENV_PATH = "/run/contextforge-client-scoped/contextforge.env"
WRAPPER_TOKEN_CACHE = "/tmp/contextforge-wrapper-token.local.json"
WRAPPER_TOKEN_LOCK = "/tmp/contextforge-wrapper-token.local.json.lock"
HOST_CLIENT_SCOPED_ENV_RELATIVE = Path("client-scoped/contextforge.env")


def scoped_env_text(container_base_url: str, server_id: str, access_token: str) -> str:
    return "\n".join(
        [
            f"CONTEXTFORGE_BASE_URL={container_base_url}",
            f"CONTEXTFORGE_SERVER_ID={server_id}",
            f"CONTEXTFORGE_BEARER_TOKEN={access_token}",
            f"CONTEXTFORGE_TOKEN_CACHE={WRAPPER_TOKEN_CACHE}",
            f"CONTEXTFORGE_TOKEN_LOCK={WRAPPER_TOKEN_LOCK}",
            "",
        ]
    )


def write_host_client_scoped_env(harness_root: Path, payload: str) -> Path:
    path = harness_root / HOST_CLIENT_SCOPED_ENV_RELATIVE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")
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
    scoped_env_payload = ""
    host_scoped_env_file: Path | None = None
    scoped_env_installed = False
    scoped_env_removed = False
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
            scoped_env_payload = scoped_env_text(args.contextforge_container_base_url, scoped_server_id, access_token)
            host_scoped_env_file = write_host_client_scoped_env(harness_root, scoped_env_payload)
            scoped_env_installed = True

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

        uc1.ensure_semantic_model_env(harness_root, client=args.client, commands=commands, runner=uc1.run)

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

        tool_inventory: dict[str, Any] | None = None
        if args.client == "pi":
            inventory_prompt = "What ContextForge tools are available in this project?"
            inventory_session = default_session_id(args.client, args.service, "inventory", timestamp)
            command = uc1.target_client_command(args.client, inventory_session, inventory_prompt)
            inventory_result = uc1.run(
                ["docker", "exec", container, "bash", "-lc", command],
                cwd=repo_root,
                timeout=args.timeout,
                commands=commands,
            )
            inventory_path = output_root / "tool-inventory-turn.raw.txt"
            inventory_path.write_text(uc1.render_command_block(inventory_result), encoding="utf-8")
            tool_inventory = {
                "phase": "tool_inventory",
                "prompt": inventory_prompt,
                "path": str(inventory_path),
                "returncode": inventory_result["returncode"],
                "timeout": inventory_result["timeout"],
            }

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

        mcp_status: dict[str, Any] | None = None
        if args.client == "opencode":
            mcp_status = uc1.run(
                [
                    "docker",
                    "exec",
                    container,
                    "bash",
                    "-lc",
                    "cd /workspace && opencode mcp list --print-logs --log-level DEBUG",
                ],
                cwd=repo_root,
                timeout=120,
                commands=commands,
            )
            mcp_status_path = output_root / "opencode-mcp-status.raw.txt"
            mcp_status_path.write_text(uc1.render_command_block(mcp_status), encoding="utf-8")
            mcp_status["path"] = str(mcp_status_path)

        cleanup = uc1.run(
            [
                "docker",
                "exec",
                container,
                "bash",
                "-lc",
                f"rm -f {WRAPPER_TOKEN_CACHE} {WRAPPER_TOKEN_LOCK}",
            ],
            cwd=repo_root,
            timeout=30,
            commands=commands,
        )
        cache_removed = cleanup["returncode"] == 0
        if host_scoped_env_file is not None:
            try:
                host_scoped_env_file.unlink()
                scoped_env_removed = True
            except FileNotFoundError:
                scoped_env_removed = True
        else:
            scoped_env_removed = cache_removed

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
                "probe_token_delivery": "client_scoped_env_file" if scoped_env_payload else None,
                "client_scoped_env_path": CLIENT_SCOPED_ENV_PATH if scoped_env_payload else None,
                "host_client_scoped_env_file": str(HOST_CLIENT_SCOPED_ENV_RELATIVE) if scoped_env_payload else None,
                "client_scoped_env_installed": scoped_env_installed,
                "client_scoped_env_removed": scoped_env_removed,
                "probe_token_revoked": scoped_token_revoked,
            },
            "reset": reset_json,
            "build_returncode": None if build_result is None else build_result["returncode"],
            "launch_returncode": launch["returncode"],
            "runtime_returncode": runtime["returncode"],
            "mcp_status": None
            if mcp_status is None
            else {
                "path": mcp_status["path"],
                "returncode": mcp_status["returncode"],
                "timeout": mcp_status["timeout"],
            },
            "tool_inventory": tool_inventory,
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
                "classify semantic model context-window or timeout failures as runner/package defects unless isolated to one service",
            ],
        }
        write_json(output_root / "run-summary.json", summary)
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0 if all(not turn["timeout"] and turn["returncode"] == 0 for turn in turns) else 1
    finally:
        if scoped_env_payload and not scoped_env_removed:
            if host_scoped_env_file is not None:
                try:
                    host_scoped_env_file.unlink()
                except FileNotFoundError:
                    pass
            try:
                uc1.run(
                    [
                        "docker",
                        "exec",
                        container,
                        "bash",
                        "-lc",
                        f"rm -f {WRAPPER_TOKEN_CACHE} {WRAPPER_TOKEN_LOCK}",
                    ],
                    cwd=repo_root,
                    timeout=30,
                    commands=commands,
                )
            except Exception:
                pass
        if scoped_token_id and admin_token and not scoped_token_revoked:
            try:
                revoke_probe_token(args.contextforge_host_base_url, admin_token, scoped_token_id)
            except Exception as exc:  # pragma: no cover - best-effort cleanup path
                print(f"warning: failed to revoke probe token {scoped_token_id}: {exc}", file=sys.stderr)
        lock_file.close()


if __name__ == "__main__":
    raise SystemExit(main())
