#!/usr/bin/env python3
"""Read-only diagnostics for ContextForge Codex wrapper lifecycle and latency."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
PYTHON = REPO_ROOT / ".venv" / "bin" / "python"
DEFAULT_REPO = "/home/dgk/gdrive/__CMU/classes/00_MathFoundationsML"
DEFAULT_BRIDGE_URL = "http://127.0.0.1:9100/mcp"
DEFAULT_SERVER_NAME = "mentality_server"

sys.path.insert(0, str(SCRIPTS_DIR))


def _json_dump(data: Any) -> None:
    print(json.dumps(data, indent=2, sort_keys=True))


def _proc_cmdline(pid: int) -> list[str]:
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return []
    return [part.decode("utf-8", "replace") for part in raw.split(b"\0") if part]


def _proc_environ(pid: int) -> dict[str, str]:
    try:
        raw = Path(f"/proc/{pid}/environ").read_bytes()
    except OSError:
        return {}
    env: dict[str, str] = {}
    for part in raw.split(b"\0"):
        if b"=" not in part:
            continue
        key, value = part.split(b"=", 1)
        key_text = key.decode("utf-8", "replace")
        if key_text in {"CONTEXTFORGE_WRAPPER_SERVER_NAME", "MCP_SERVER_URL", "CONTEXTFORGE_BASE_URL"}:
            env[key_text] = value.decode("utf-8", "replace")
    return env


def _wrapper_server_name_from_cmdline(cmdline: list[str]) -> str | None:
    for index, part in enumerate(cmdline):
        if part.endswith("contextforge_mcp_wrapper.py") and index + 1 < len(cmdline):
            return cmdline[index + 1]
    return None


def _proc_stat(pid: int) -> dict[str, Any]:
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
        status = Path(f"/proc/{pid}/status").read_text()
    except OSError:
        return {}
    state = stat.split()[2] if len(stat.split()) > 2 else ""
    ppid_match = re.search(r"^PPid:\s+(\d+)$", status, re.MULTILINE)
    return {"state": state, "ppid": int(ppid_match.group(1)) if ppid_match else None}


def _fd_summary(pid: int) -> dict[str, Any]:
    fd_dir = Path(f"/proc/{pid}/fd")
    targets: dict[str, str] = {}
    try:
        fds = list(fd_dir.iterdir())
    except OSError:
        return {"fd_count": None, "stdio": {}}
    for fd in ("0", "1", "2"):
        try:
            targets[fd] = os.readlink(fd_dir / fd)
        except OSError:
            targets[fd] = "unreadable"
    return {"fd_count": len(fds), "stdio": targets}


def _cgroup(pid: int) -> list[str]:
    try:
        return Path(f"/proc/{pid}/cgroup").read_text().splitlines()
    except OSError:
        return []


def _ss_by_pid() -> dict[int, list[dict[str, str]]]:
    try:
        completed = subprocess.run(
            ["ss", "-tanp"],
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError:
        return {}
    sockets: dict[int, list[dict[str, str]]] = {}
    for line in completed.stdout.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 5:
            continue
        users = " ".join(parts[5:])
        for pid_text in re.findall(r"pid=(\d+)", users):
            pid = int(pid_text)
            sockets.setdefault(pid, []).append(
                {
                    "state": parts[0],
                    "recv_q": parts[1],
                    "send_q": parts[2],
                    "local": parts[3],
                    "peer": parts[4],
                }
            )
    return sockets


def process_report() -> dict[str, Any]:
    sockets = _ss_by_pid()
    rows: list[dict[str, Any]] = []
    for proc in sorted(Path("/proc").iterdir(), key=lambda item: int(item.name) if item.name.isdigit() else -1):
        if not proc.name.isdigit():
            continue
        pid = int(proc.name)
        cmdline = _proc_cmdline(pid)
        joined = " ".join(cmdline)
        if not any(
            marker in joined
            for marker in (
                "contextforge_mcp_wrapper.py",
                "mcpgateway.wrapper",
                "contextforge_helper_mcp.py",
                "node_repl",
            )
        ):
            continue
        env = _proc_environ(pid)
        server_name = env.get("CONTEXTFORGE_WRAPPER_SERVER_NAME") or _wrapper_server_name_from_cmdline(cmdline)
        stat = _proc_stat(pid)
        socket_rows = sockets.get(pid, [])
        rows.append(
            {
                "pid": pid,
                "ppid": stat.get("ppid"),
                "state": stat.get("state"),
                "kind": _classify_process(joined),
                "server_name": server_name,
                "mcp_server_url": env.get("MCP_SERVER_URL"),
                "cmdline": cmdline,
                "fd": _fd_summary(pid),
                "cgroup": _cgroup(pid),
                "sockets": socket_rows,
                "close_wait_count": sum(1 for item in socket_rows if item["state"] == "CLOSE-WAIT"),
            }
        )
    counts: dict[str, int] = {}
    by_server: dict[str, int] = {}
    for row in rows:
        counts[row["kind"]] = counts.get(row["kind"], 0) + 1
        if row.get("server_name"):
            by_server[row["server_name"]] = by_server.get(row["server_name"], 0) + 1
    return {
        "ok": True,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "counts": counts,
        "wrapper_counts_by_server_name": by_server,
        "processes": rows,
    }


def _classify_process(cmdline: str) -> str:
    if "contextforge_mcp_wrapper.py" in cmdline or "mcpgateway.wrapper" in cmdline:
        return "codex_contextforge_wrapper"
    if "contextforge_helper_mcp.py" in cmdline:
        return "contextforge_helper"
    if "node_repl" in cmdline:
        return "node_repl"
    return "other"


def _time_call(name: str, func: Any) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        result = func()
        ok = True
        error = None
    except Exception as exc:  # pragma: no cover - diagnostic boundary
        result = None
        ok = False
        error = {"type": exc.__class__.__name__, "message": str(exc)}
    return {
        "name": name,
        "ok": ok,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
        "result_preview": _preview(result),
        "error": error,
    }


def _preview(value: Any) -> Any:
    if isinstance(value, dict):
        if isinstance(value.get("tool_call"), dict):
            return _preview(value["tool_call"])
        preview = {key: value.get(key) for key in ("ok", "path", "status_filter", "entries") if key in value}
        if isinstance(preview.get("entries"), list):
            preview["entries_count"] = len(preview.pop("entries"))
        return preview
    return value


def _mcp_request(id_value: int | str, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    request: dict[str, Any] = {"jsonrpc": "2.0", "id": id_value, "method": method}
    if params is not None:
        request["params"] = params
    return request


def _mcp_notification(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    request: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        request["params"] = params
    return request


def _tool_call_payload(repo: str, tool_name: str) -> dict[str, Any]:
    return _mcp_request(
        2,
        "tools/call",
        {
            "name": tool_name,
            "arguments": {
                "repo": repo,
                "ledger": "abeyant-intentions",
                "status": "parked",
            },
        },
    )


def _initialize_payload() -> dict[str, Any]:
    return _mcp_request(
        1,
        "initialize",
        {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "contextforge-wrapper-diagnostic", "version": "1"},
        },
    )


def _stdio_mcp_call(command: list[str], repo: str, timeout: float, tool_name: str) -> dict[str, Any]:
    proc = subprocess.Popen(
        command,
        cwd=REPO_ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert proc.stdin is not None
    assert proc.stdout is not None
    try:
        _write_json_line(proc.stdin, _initialize_payload())
        init_response = _read_response(proc.stdout, 1, timeout)
        _write_json_line(proc.stdin, _mcp_notification("notifications/initialized"))
        _write_json_line(proc.stdin, _tool_call_payload(repo, tool_name))
        tool_response = _read_response(proc.stdout, 2, timeout)
        return {"initialize": init_response, "tool_call": _extract_tool_result(tool_response)}
    finally:
        if proc.stdin:
            proc.stdin.close()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.terminate()
            proc.wait(timeout=5)


def _write_json_line(handle: Any, payload: dict[str, Any]) -> None:
    handle.write(json.dumps(payload, separators=(",", ":")) + "\n")
    handle.flush()


def _read_response(handle: Any, id_value: int | str, timeout: float) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        line = handle.readline()
        if not line:
            break
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if payload.get("id") == id_value:
            return payload
    raise TimeoutError(f"timed out waiting for MCP response id={id_value}")


def _extract_tool_result(response: dict[str, Any]) -> Any:
    structured = response.get("result", {}).get("structuredContent")
    if structured is not None:
        return structured
    content = response.get("result", {}).get("content")
    if not content:
        return response
    first = content[0]
    if isinstance(first, dict) and isinstance(first.get("text"), str):
        try:
            return json.loads(first["text"])
        except json.JSONDecodeError:
            return first["text"]
    return response


def _http_post_json(url: str, payload: dict[str, Any], headers: dict[str, str] | None = None, timeout: float = 20) -> tuple[dict[str, Any], dict[str, str]]:
    data = json.dumps(payload).encode()
    request_headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if headers:
        request_headers.update(headers)
    request = urllib.request.Request(url, data=data, headers=request_headers, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read()
        response_headers = {key.lower(): value for key, value in response.headers.items()}
        content_type = response_headers.get("content-type", "")
        parsed = json.loads(body) if body.strip() and "json" in content_type else {}
        return parsed, response_headers


def _http_mcp_call(url: str, repo: str, timeout: float, tool_name: str, auth: str | None = None) -> dict[str, Any]:
    headers = {"Authorization": auth} if auth else {}
    init_response, response_headers = _http_post_json(url, _initialize_payload(), headers=headers, timeout=timeout)
    session_id = response_headers.get("mcp-session-id")
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    _http_post_json(url, _mcp_notification("notifications/initialized"), headers=headers, timeout=timeout)
    tool_response, _ = _http_post_json(url, _tool_call_payload(repo, tool_name), headers=headers, timeout=timeout)
    return {"initialize": init_response, "tool_call": _extract_tool_result(tool_response)}


def _contextforge_server_url(server_name: str) -> tuple[str, str]:
    import contextforge_mcp_wrapper as gateway

    env = gateway._read_env(gateway.CONFIG_ENV)
    token = gateway._token(env["PLATFORM_ADMIN_EMAIL"], env["PLATFORM_ADMIN_PASSWORD"])
    servers = gateway._items(gateway._request("GET", "/servers?include_inactive=true&limit=1000", token=token))
    matches = [server for server in servers if server.get("name") == server_name]
    if len(matches) != 1:
        raise RuntimeError(f"expected one virtual server named {server_name!r}, found {len(matches)}")
    return f"{gateway.GATEWAY_BASE}/servers/{matches[0]['id']}/mcp/", f"Bearer {token}"


def timing_report(repo: str, server_name: str, bridge_url: str, timeout: float) -> dict[str, Any]:
    import governance_registry

    gateway_url, auth = _contextforge_server_url(server_name)
    wrapper_command = [str(PYTHON), str(SCRIPTS_DIR / "contextforge_mcp_wrapper.py"), server_name]
    stdio_command = [str(PYTHON), str(SCRIPTS_DIR / "governance_mcp.py")]
    return {
        "ok": True,
        "repo": repo,
        "server_name": server_name,
        "timings": [
            _time_call("governance_registry.list_entries", lambda: governance_registry.list_entries(repo, "abeyant-intentions", "parked")),
            _time_call("scripts/governance_mcp.py stdio", lambda: _stdio_mcp_call(stdio_command, repo, timeout, "governance_list")),
            _time_call(f"{bridge_url} direct bridge", lambda: _http_mcp_call(bridge_url, repo, timeout, "governance_list")),
            _time_call(
                f"{gateway_url} ContextForge virtual server",
                lambda: _http_mcp_call(gateway_url, repo, timeout, "mentality-governance-list", auth=auth),
            ),
            _time_call(
                "scripts/contextforge_mcp_wrapper.py stdio",
                lambda: _stdio_mcp_call(wrapper_command, repo, timeout, "mentality-governance-list"),
            ),
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("process-report", help="Report wrapper/helper/node_repl process, fd, cgroup, and socket state.")
    timing = subparsers.add_parser("time-mentality-path", help="Time each layer of the mentality governance_list path.")
    timing.add_argument("--repo", default=DEFAULT_REPO)
    timing.add_argument("--server-name", default=DEFAULT_SERVER_NAME)
    timing.add_argument("--bridge-url", default=DEFAULT_BRIDGE_URL)
    timing.add_argument("--timeout", type=float, default=20.0)
    args = parser.parse_args(argv)

    if args.command == "process-report":
        _json_dump(process_report())
        return 0
    if args.command == "time-mentality-path":
        _json_dump(timing_report(args.repo, args.server_name, args.bridge_url, args.timeout))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
