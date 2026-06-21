#!/usr/bin/env python3
"""Launch a ContextForge virtual server as a stdio MCP server for Codex."""

from __future__ import annotations

import json
import os
import select
import ssl
import sys
import urllib.error
import urllib.request
import base64
from dataclasses import dataclass
import fcntl
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_ENV = Path(os.environ.get("CONTEXTFORGE_CONFIG_ENV", REPO_ROOT / "config" / "contextforge.env"))
TLS_CERT = REPO_ROOT / "config" / "tls" / "contextforge-local.crt"
TOKEN_CACHE = Path(os.environ.get("CONTEXTFORGE_TOKEN_CACHE", REPO_ROOT / "run" / "contextforge-wrapper-token.local.json"))
TOKEN_LOCK = Path(os.environ.get("CONTEXTFORGE_TOKEN_LOCK", f"{TOKEN_CACHE}.lock"))
GATEWAY_BASE = os.environ.get(
    "CONTEXTFORGE_BASE_URL",
    "http://127.0.0.1:4444",
).rstrip("/")
DEFAULT_WRAPPER_IDLE_TIMEOUT_SECONDS = 300
DEFAULT_WRAPPER_TOOL_TIMEOUT_SECONDS = 120
SCOPED_SERVER_TOKEN_PERMISSIONS = [
    "servers.use",
    "tools.read",
    "tools.execute",
    "resources.read",
    "prompts.read",
]


@dataclass
class WrapperLifecycle:
    server_name: str
    server_url: str
    parent_pid: int
    idle_timeout_seconds: float
    stop_reason: str | None = None
    exit_code: int | None = None


def _log_lifecycle(event: str, lifecycle: WrapperLifecycle, **extra: Any) -> None:
    payload = {
        "event": event,
        "pid": os.getpid(),
        "ppid": os.getppid(),
        "initial_ppid": lifecycle.parent_pid,
        "server_name": lifecycle.server_name,
        "mcp_server_url": lifecycle.server_url,
        "idle_timeout_seconds": lifecycle.idle_timeout_seconds,
    }
    payload.update(extra)
    print(json.dumps(payload, sort_keys=True), file=sys.stderr, flush=True)


def _log_bootstrap_event(server_name: str, event: str, **extra: Any) -> None:
    payload = {
        "event": event,
        "pid": os.getpid(),
        "ppid": os.getppid(),
        "server_name": server_name,
    }
    payload.update(extra)
    print(json.dumps(payload, sort_keys=True), file=sys.stderr, flush=True)


def _log_bootstrap_error(server_name: str, stage: str, exc: Exception | str) -> None:
    payload = {
        "event": "contextforge_wrapper_bootstrap_error",
        "pid": os.getpid(),
        "ppid": os.getppid(),
        "server_name": server_name,
        "stage": stage,
        "error_type": exc.__class__.__name__ if isinstance(exc, Exception) else "RuntimeError",
        "error": str(exc),
    }
    print(json.dumps(payload, sort_keys=True), file=sys.stderr, flush=True)


def _float_env(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return max(0.0, value)


class _LifecycleStdinBuffer:
    """Expose stdin.readline with idle and parent-liveness termination."""

    def __init__(self, wrapped: Any, lifecycle: WrapperLifecycle) -> None:
        self._wrapped = wrapped
        self._lifecycle = lifecycle
        self._pending = b""

    def __getattr__(self, name: str) -> Any:
        return getattr(self._wrapped, name)

    def readline(self, *args: Any, **kwargs: Any) -> bytes:
        timeout = self._lifecycle.idle_timeout_seconds
        if timeout <= 0 or not hasattr(self._wrapped, "fileno"):
            line = self._wrapped.readline(*args, **kwargs)
            if not line:
                self._lifecycle.stop_reason = self._lifecycle.stop_reason or "stdin_eof"
            return line

        fd = self._wrapped.fileno()
        deadline = time.monotonic() + timeout
        while True:
            if b"\n" in self._pending:
                line, self._pending = self._pending.split(b"\n", 1)
                return line + b"\n"
            if os.getppid() != self._lifecycle.parent_pid:
                self._lifecycle.stop_reason = "parent_pid_changed"
                return b""
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                self._lifecycle.stop_reason = "idle_timeout"
                return b""
            try:
                readable, _, _ = select.select([fd], [], [], min(remaining, 1.0))
            except InterruptedError:
                continue
            if not readable:
                continue
            chunk = os.read(fd, 4096)
            if not chunk:
                self._lifecycle.stop_reason = self._lifecycle.stop_reason or "stdin_eof"
                if self._pending:
                    line = self._pending
                    self._pending = b""
                    return line
                return b""
            self._pending += chunk


class _LifecycleStdin:
    def __init__(self, wrapped: Any, lifecycle: WrapperLifecycle) -> None:
        self._wrapped = wrapped
        self.buffer = _LifecycleStdinBuffer(wrapped.buffer, lifecycle)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._wrapped, name)

    def readline(self, *args: Any, **kwargs: Any) -> str:
        line = self.buffer.readline(*args, **kwargs)
        return line.decode(getattr(self._wrapped, "encoding", None) or "utf-8") if isinstance(line, bytes) else line


def _read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value.strip().strip("\"'")
    return values


def _request(method: str, path: str, *, token: str | None = None, body: dict[str, Any] | None = None) -> Any:
    headers = {"Accept": "application/json"}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(f"{GATEWAY_BASE}{path}", data=data, headers=headers, method=method)
    kwargs: dict[str, Any] = {"timeout": 20}
    if GATEWAY_BASE.startswith("https://"):
        kwargs["context"] = ssl.create_default_context(cafile=str(TLS_CERT))
    with urllib.request.urlopen(request, **kwargs) as response:
        payload = response.read()
    return json.loads(payload) if payload else None


def _items(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        return data["items"]
    if isinstance(data, list):
        return data
    return []


def _jwt_exp(token: str) -> int | None:
    parts = token.split(".")
    if len(parts) != 3:
        return None
    payload = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        claims = json.loads(base64.urlsafe_b64decode(payload.encode()))
    except (ValueError, json.JSONDecodeError):
        return None
    exp = claims.get("exp")
    return exp if isinstance(exp, int) else None


def _cached_token() -> str | None:
    if not TOKEN_CACHE.exists():
        return None
    try:
        data = json.loads(TOKEN_CACHE.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    token = data.get("access_token") if isinstance(data, dict) else None
    if not isinstance(token, str):
        return None
    exp = _jwt_exp(token)
    if exp is None or exp - int(time.time()) < 60:
        return None
    return token


def _write_token_cache(token: str) -> None:
    TOKEN_CACHE.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"access_token": token}, indent=2)
    fd = os.open(TOKEN_CACHE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as handle:
        handle.write(payload)
        handle.write("\n")


def _login_token(email: str, password: str) -> str:
    login: dict[str, Any] | None = None
    for attempt in range(4):
        try:
            login = _request("POST", "/auth/email/login", body={"email": email, "password": password})
            break
        except urllib.error.HTTPError as exc:
            if exc.code != 429 or attempt == 3:
                raise
            retry_after = exc.headers.get("Retry-After")
            delay = int(retry_after) if retry_after and retry_after.isdigit() else 10 * (attempt + 1)
            time.sleep(delay)
    if login is None:
        raise RuntimeError("ContextForge login attempts exhausted")
    token = login.get("access_token")
    if not token:
        raise RuntimeError("ContextForge login did not return an access token")
    _write_token_cache(token)
    return token


def _token(email: str | None, password: str | None, bearer_token: str | None = None) -> str:
    env_token = bearer_token or os.environ.get("CONTEXTFORGE_BEARER_TOKEN")
    if env_token:
        return env_token.removeprefix("Bearer ").strip()
    if not email or not password:
        raise RuntimeError(f"missing PLATFORM_ADMIN_EMAIL or PLATFORM_ADMIN_PASSWORD in {CONFIG_ENV}")

    cached = _cached_token()
    if cached:
        return cached

    TOKEN_CACHE.parent.mkdir(parents=True, exist_ok=True)
    with TOKEN_LOCK.open("a+") as lock_handle:
        fcntl.flock(lock_handle, fcntl.LOCK_EX)
        cached = _cached_token()
        if cached:
            return cached
        return _login_token(email, password)


def _create_scoped_server_token(admin_token: str, server_id: str, server_name: str) -> tuple[str, str]:
    response = _request(
        "POST",
        "/tokens",
        token=admin_token,
        body={
            "name": f"wrapper-{server_name}-{uuid4().hex[:12]}",
            "description": f"Ephemeral wrapper token for {server_name}.",
            "expires_in_days": 1,
            "scope": {
                "server_id": server_id,
                "permissions": SCOPED_SERVER_TOKEN_PERMISSIONS,
            },
            "tags": ["contextforge", "wrapper", "ephemeral"],
        },
    )
    if not isinstance(response, dict):
        raise RuntimeError("ContextForge scoped token create did not return JSON")
    token_record = response.get("token")
    token_id = token_record.get("id") if isinstance(token_record, dict) else None
    access_token = response.get("access_token")
    if not isinstance(token_id, str) or not token_id:
        raise RuntimeError("ContextForge scoped token create did not return token.id")
    if not isinstance(access_token, str) or not access_token:
        raise RuntimeError("ContextForge scoped token create did not return access_token")
    return token_id, access_token


def _revoke_scoped_server_token(admin_token: str, token_id: str) -> None:
    _request(
        "DELETE",
        f"/tokens/{token_id}",
        token=admin_token,
        body={"reason": "wrapper process complete"},
    )


def _jsonrpc_ids(payload: Any) -> set[Any]:
    if isinstance(payload, dict) and "id" in payload:
        return {payload["id"]}
    if isinstance(payload, list):
        return {item["id"] for item in payload if isinstance(item, dict) and "id" in item}
    return set()


def _jsonrpc_error(request_id: Any, message: str, code: int, data: Any = None) -> dict[str, Any]:
    error = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": request_id, "error": error}


def _install_transport_shim(stock_wrapper: Any, lifecycle: WrapperLifecycle, email: str | None, password: str | None) -> None:
    """Patch stock wrapper forwarding to be id/session aware for streamable HTTP."""

    session: dict[str, str | None] = {"mcp_session_id": None}

    async def forward_once(client: Any, settings: Any, payload: Any, *, refresh_allowed: bool = True) -> None:
        if stock_wrapper.shutting_down():
            return

        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json, application/x-ndjson, text/event-stream",
        }
        if settings.auth_header:
            headers["Authorization"] = settings.auth_header
        if session["mcp_session_id"]:
            headers["Mcp-Session-Id"] = session["mcp_session_id"]

        body_bytes = stock_wrapper.orjson.dumps(payload)
        expected_ids = _jsonrpc_ids(payload)
        seen_ids: set[Any] = set()

        async with client.stream("POST", settings.server_url, data=body_bytes, headers=headers) as resp:
            if resp.headers.get("mcp-session-id"):
                session["mcp_session_id"] = resp.headers["mcp-session-id"]
            status = resp.status_code
            ctype = (resp.headers.get("Content-Type") or "").lower()
            if status == 401 and refresh_allowed and email and password:
                token = _login_token(email, password)
                settings.auth_header = f"Bearer {token}"
                os.environ["MCP_AUTH"] = settings.auth_header
                lifecycle.stop_reason = None
                _log_lifecycle("contextforge_wrapper_token_refreshed", lifecycle)
                await forward_once(client, settings, payload, refresh_allowed=False)
                return
            if status < 200 or status >= 300:
                _log_lifecycle(
                    "contextforge_wrapper_http_error",
                    lifecycle,
                    status=status,
                    content_type=ctype,
                    classification="inside_gateway_or_upstream_http",
                )
                request_ids = expected_ids or {"bridge"}
                for request_id in request_ids:
                    stock_wrapper.send_to_stdout(_jsonrpc_error(request_id, f"HTTP {status}", status))
                return
            if not expected_ids:
                return

            async def process_line(line: str | bytes) -> bool:
                if stock_wrapper.shutting_down():
                    return True
                try:
                    obj = stock_wrapper.orjson.loads(line)
                except Exception:
                    line_text = line if isinstance(line, str) else line.decode("utf-8", "replace")
                    _log_lifecycle(
                        "contextforge_wrapper_invalid_gateway_json",
                        lifecycle,
                        classification="inside_gateway_or_bridge_response",
                    )
                    for request_id in expected_ids:
                        stock_wrapper.send_to_stdout(_jsonrpc_error(request_id, "Invalid JSON from server", stock_wrapper.JSONRPC_PARSE_ERROR, line_text))
                    return True
                stock_wrapper.send_to_stdout(obj)
                if isinstance(obj, dict) and obj.get("id") in expected_ids:
                    seen_ids.add(obj.get("id"))
                if isinstance(obj, list):
                    seen_ids.update(item.get("id") for item in obj if isinstance(item, dict) and item.get("id") in expected_ids)
                return expected_ids.issubset(seen_ids)

            if "event-stream" in ctype:
                async for data_payload in stock_wrapper.sse_events(resp):
                    if await process_line(data_payload):
                        return
                return
            if "x-ndjson" in ctype or "ndjson" in ctype:
                async for line in stock_wrapper.ndjson_lines(resp):
                    if await process_line(line):
                        return
                return
            if "application/json" in ctype:
                raw = await resp.aread()
                if raw.strip():
                    await process_line(raw)
                return
            async for line in stock_wrapper.ndjson_lines(resp):
                if await process_line(line):
                    return

    stock_wrapper.forward_once = forward_once


def _run_stock_wrapper(lifecycle: WrapperLifecycle, email: str | None, password: str | None) -> int:
    """Run stock ContextForge's stdio wrapper with local lifecycle guards."""

    original_stdin = sys.stdin
    original_argv = sys.argv[:]
    sys.stdin = _LifecycleStdin(sys.stdin, lifecycle)
    sys.argv = [
        "mcpgateway.wrapper",
        "--timeout",
        str(int(_float_env("CONTEXTFORGE_WRAPPER_TOOL_TIMEOUT_SECONDS", DEFAULT_WRAPPER_TOOL_TIMEOUT_SECONDS))),
    ]
    _log_lifecycle("contextforge_wrapper_start", lifecycle, tool_timeout_seconds=sys.argv[-1])
    try:
        from mcpgateway import wrapper as stock_wrapper  # pylint: disable=import-outside-toplevel

        _install_transport_shim(stock_wrapper, lifecycle, email, password)
        stock_wrapper.main()
        lifecycle.stop_reason = lifecycle.stop_reason or "stock_wrapper_returned"
        lifecycle.exit_code = 0
        return 0
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
        lifecycle.exit_code = code
        lifecycle.stop_reason = lifecycle.stop_reason or "system_exit"
        return code
    except BrokenPipeError:
        lifecycle.exit_code = 1
        lifecycle.stop_reason = lifecycle.stop_reason or "broken_stdout_pipe"
        return 1
    except Exception as exc:  # pragma: no cover - defensive process boundary
        lifecycle.exit_code = 1
        lifecycle.stop_reason = lifecycle.stop_reason or exc.__class__.__name__
        _log_lifecycle("contextforge_wrapper_error", lifecycle, error_type=exc.__class__.__name__, error=str(exc))
        return 1
    finally:
        sys.stdin = original_stdin
        sys.argv = original_argv
        _log_lifecycle(
            "contextforge_wrapper_stop",
            lifecycle,
            stop_reason=lifecycle.stop_reason or "unknown",
            exit_code=lifecycle.exit_code,
        )


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: contextforge_mcp_wrapper.py <virtual-server-name>", file=sys.stderr)
        return 2

    server_name = sys.argv[1]
    env = _read_env(CONFIG_ENV) if CONFIG_ENV.exists() else {}
    email = env.get("PLATFORM_ADMIN_EMAIL")
    password = env.get("PLATFORM_ADMIN_PASSWORD")

    env_bearer_token = env.get("CONTEXTFORGE_BEARER_TOKEN") or os.environ.get("CONTEXTFORGE_BEARER_TOKEN")
    try:
        token = _token(email, password, env_bearer_token)
    except RuntimeError as exc:
        _log_bootstrap_error(server_name, "auth_token", exc)
        print(str(exc), file=sys.stderr)
        return 1

    server_id = (os.environ.get("CONTEXTFORGE_SERVER_ID") or env.get("CONTEXTFORGE_SERVER_ID") or "").strip()
    if not server_id:
        try:
            servers = _items(_request("GET", "/servers?include_inactive=true&limit=1000", token=token))
        except Exception as exc:
            _log_bootstrap_error(server_name, "contextforge_server_readback", exc)
            print(str(exc), file=sys.stderr)
            return 1
        matches = [server for server in servers if server.get("name") == server_name]
        if len(matches) != 1:
            message = f"expected one virtual server named {server_name!r}, found {len(matches)}"
            _log_bootstrap_error(server_name, "contextforge_server_match", message)
            print(message, file=sys.stderr)
            return 1
        server_id = matches[0]["id"]

    scoped_token_id = ""
    scoped_token_admin_token = ""
    mcp_token = token
    if not env_bearer_token:
        try:
            scoped_token_id, mcp_token = _create_scoped_server_token(token, server_id, server_name)
            scoped_token_admin_token = token
            _log_bootstrap_event(
                server_name,
                "contextforge_wrapper_scoped_token_created",
                server_id=server_id,
                token_id=scoped_token_id,
                permissions=SCOPED_SERVER_TOKEN_PERMISSIONS,
            )
        except Exception as exc:
            _log_bootstrap_error(server_name, "scoped_server_token", exc)
            print(str(exc), file=sys.stderr)
            return 1

    os.environ["MCP_SERVER_URL"] = f"{GATEWAY_BASE}/servers/{server_id}/mcp/"
    os.environ["MCP_AUTH"] = f"Bearer {mcp_token}"
    if GATEWAY_BASE.startswith("https://"):
        os.environ["SSL_CERT_FILE"] = str(TLS_CERT)
    os.environ["CONTEXTFORGE_WRAPPER_SERVER_NAME"] = server_name
    os.environ.setdefault("MCP_WRAPPER_LOG_LEVEL", "INFO")
    os.environ["FORGE_CONTENT_TYPE"] = "application/json"

    lifecycle = WrapperLifecycle(
        server_name=server_name,
        server_url=os.environ["MCP_SERVER_URL"],
        parent_pid=os.getppid(),
        idle_timeout_seconds=_float_env(
            "CONTEXTFORGE_WRAPPER_IDLE_TIMEOUT_SECONDS",
            DEFAULT_WRAPPER_IDLE_TIMEOUT_SECONDS,
        ),
    )
    refresh_email = None if scoped_token_id or env_bearer_token else email
    refresh_password = None if scoped_token_id or env_bearer_token else password
    try:
        return _run_stock_wrapper(lifecycle, refresh_email, refresh_password)
    finally:
        if scoped_token_id and scoped_token_admin_token:
            try:
                _revoke_scoped_server_token(scoped_token_admin_token, scoped_token_id)
                _log_lifecycle("contextforge_wrapper_scoped_token_revoked", lifecycle, token_id=scoped_token_id)
            except Exception as exc:  # pragma: no cover - process boundary logging
                _log_lifecycle(
                    "contextforge_wrapper_scoped_token_revoke_failed",
                    lifecycle,
                    token_id=scoped_token_id,
                    error_type=exc.__class__.__name__,
                    error=str(exc),
                )


if __name__ == "__main__":
    raise SystemExit(main())
