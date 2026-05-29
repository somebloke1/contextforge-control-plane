#!/usr/bin/env python3
"""Launch a ContextForge virtual server as a stdio MCP server for Codex."""

from __future__ import annotations

import json
import os
import ssl
import sys
import urllib.error
import urllib.request
import base64
import fcntl
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_ENV = REPO_ROOT / "config" / "contextforge.env"
TLS_CERT = REPO_ROOT / "config" / "tls" / "contextforge-local.crt"
TOKEN_CACHE = REPO_ROOT / "run" / "contextforge-wrapper-token.local.json"
TOKEN_LOCK = REPO_ROOT / "run" / "contextforge-wrapper-token.local.lock"
GATEWAY_BASE = os.environ.get(
    "CONTEXTFORGE_BASE_URL",
    "http://127.0.0.1:4444",
).rstrip("/")


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


def _token(email: str, password: str) -> str:
    env_token = os.environ.get("CONTEXTFORGE_BEARER_TOKEN")
    if env_token:
        return env_token.removeprefix("Bearer ").strip()

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


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: contextforge_mcp_wrapper.py <virtual-server-name>", file=sys.stderr)
        return 2

    server_name = sys.argv[1]
    env = _read_env(CONFIG_ENV)
    email = env.get("PLATFORM_ADMIN_EMAIL")
    password = env.get("PLATFORM_ADMIN_PASSWORD")
    if not email or not password:
        print(f"missing PLATFORM_ADMIN_EMAIL or PLATFORM_ADMIN_PASSWORD in {CONFIG_ENV}", file=sys.stderr)
        return 1

    try:
        token = _token(email, password)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    servers = _items(_request("GET", "/servers?include_inactive=true&limit=1000", token=token))
    matches = [server for server in servers if server.get("name") == server_name]
    if len(matches) != 1:
        print(f"expected one virtual server named {server_name!r}, found {len(matches)}", file=sys.stderr)
        return 1

    server_id = matches[0]["id"]
    os.environ["MCP_SERVER_URL"] = f"{GATEWAY_BASE}/servers/{server_id}/mcp/"
    os.environ["MCP_AUTH"] = f"Bearer {token}"
    if GATEWAY_BASE.startswith("https://"):
        os.environ["SSL_CERT_FILE"] = str(TLS_CERT)

    python = str(REPO_ROOT / ".venv" / "bin" / "python")
    os.execv(python, [python, "-m", "mcpgateway.wrapper", "--timeout", "120"])
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
