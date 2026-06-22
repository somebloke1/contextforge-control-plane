#!/usr/bin/env python3
"""Host-side OpenRouter proxy for semantic-test client containers.

The client containers receive only a dummy API key and a host-gateway base URL.
This process runs on the host, reads the real provider key from its own
environment, replaces Authorization, and forwards OpenAI-compatible requests.
"""

from __future__ import annotations

import argparse
import http.server
import json
import os
import secrets
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


DUMMY_API_KEY_PREFIX = "contextforge-host-proxy-dummy-"
API_KEY_ENV_NAMES = (
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


def redact_url(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.query:
        return url.removesuffix("?" + parsed.query) + "?<redacted>"
    return url


def free_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def host_gateway_base_url(port: int) -> str:
    return f"http://host.docker.internal:{port}/api/v1"


def strip_api_v1_prefix(path: str) -> str:
    if path == "/api/v1":
        return ""
    if path.startswith("/api/v1/"):
        return path[len("/api/v1") :]
    return path


class OpenRouterProxy(http.server.BaseHTTPRequestHandler):
    server_version = "ContextForgeOpenRouterProxy/1.0"

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return

    def do_GET(self) -> None:  # noqa: N802
        self.forward()

    def do_POST(self) -> None:  # noqa: N802
        self.forward()

    def forward(self) -> None:
        upstream_base = str(self.server.upstream_base_url).rstrip("/")  # type: ignore[attr-defined]
        api_key = str(self.server.api_key)  # type: ignore[attr-defined]
        expected_auth = str(self.server.expected_authorization)  # type: ignore[attr-defined]
        if self.headers.get("Authorization") != expected_auth:
            payload = json.dumps({"error": "unauthorized semantic model proxy request"}).encode()
            self.send_response(401)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        length = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(length) if length else None
        suffix = strip_api_v1_prefix(self.path)
        target = upstream_base + suffix
        headers = {
            key: value
            for key, value in self.headers.items()
            if key.lower() not in {"host", "authorization", "content-length", "connection"}
        }
        headers["Authorization"] = f"Bearer {api_key}"
        if body is not None:
            headers["Content-Length"] = str(len(body))
        request = urllib.request.Request(target, data=body, headers=headers, method=self.command)
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                payload = response.read()
                self.send_response(response.status)
                for key, value in response.headers.items():
                    if key.lower() not in {"transfer-encoding", "connection"}:
                        self.send_header(key, value)
                self.end_headers()
                self.wfile.write(payload)
        except urllib.error.HTTPError as exc:
            payload = exc.read()
            self.send_response(exc.code)
            for key, value in exc.headers.items():
                if key.lower() not in {"transfer-encoding", "connection"}:
                    self.send_header(key, value)
            self.end_headers()
            self.wfile.write(payload)
        except Exception as exc:  # pragma: no cover - defensive runtime path
            payload = json.dumps({"error": "semantic model host proxy failed", "detail": str(exc)}).encode()
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)


def serve(args: argparse.Namespace) -> int:
    api_key = os.environ.get(args.api_key_env)
    if not api_key:
        raise RuntimeError(f"missing host API key env {args.api_key_env}")
    if not args.expected_dummy_key:
        raise RuntimeError("--expected-dummy-key is required")
    server = http.server.ThreadingHTTPServer((args.listen_host, args.port), OpenRouterProxy)
    server.upstream_base_url = args.upstream_base_url.rstrip("/")  # type: ignore[attr-defined]
    server.api_key = api_key  # type: ignore[attr-defined]
    server.expected_authorization = f"Bearer {args.expected_dummy_key}"  # type: ignore[attr-defined]
    print(
        json.dumps(
            {
                "ready": True,
                "listen_host": args.listen_host,
                "port": args.port,
                "container_base_url": host_gateway_base_url(args.port),
                "upstream_base_url": redact_url(args.upstream_base_url.rstrip("/")),
                "api_key_env": args.api_key_env,
                "dummy_key_present": True,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    server.serve_forever()
    return 0


@dataclass
class HostProxy:
    provider_kind: str
    api_key_env: str
    upstream_base_url: str
    port: int
    container_api_key: str
    process: subprocess.Popen[str]

    @property
    def container_base_url(self) -> str:
        return host_gateway_base_url(self.port)

    def summary(self) -> dict[str, Any]:
        return {
            "provider_kind": self.provider_kind,
            "credential_location": "host_process_environment",
            "container_receives_real_api_key": False,
            "container_api_key_value": "ephemeral_dummy",
            "container_api_key_present": True,
            "api_key_env": self.api_key_env,
            "container_base_url": self.container_base_url,
            "upstream_base_url": redact_url(self.upstream_base_url),
            "port": self.port,
        }

    def stop(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)


def start_openrouter_proxy(
    *,
    script_path: Path,
    api_key_env: str,
    upstream_base_url: str,
    host_env: dict[str, str],
) -> HostProxy:
    api_key = host_env.get(api_key_env) or os.environ.get(api_key_env)
    if not api_key:
        raise RuntimeError(f"cannot start semantic model host proxy without host {api_key_env}")
    port = free_local_port()
    container_api_key = DUMMY_API_KEY_PREFIX + secrets.token_urlsafe(24)
    process_env = {key: value for key, value in os.environ.items() if key not in API_KEY_ENV_NAMES}
    process_env[api_key_env] = api_key
    command = [
        sys.executable,
        str(script_path),
        "--serve-openrouter",
        "--listen-host",
        "0.0.0.0",
        "--port",
        str(port),
        "--api-key-env",
        api_key_env,
        "--upstream-base-url",
        upstream_base_url,
        "--expected-dummy-key",
        container_api_key,
    ]
    process = subprocess.Popen(
        command,
        text=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=process_env,
    )
    assert process.stdout is not None
    deadline = time.time() + 10
    while time.time() < deadline:
        line = process.stdout.readline()
        if line:
            data = json.loads(line)
            if data.get("ready"):
                return HostProxy(
                    provider_kind="openrouter",
                    api_key_env=api_key_env,
                    upstream_base_url=upstream_base_url,
                    port=port,
                    container_api_key=container_api_key,
                    process=process,
                )
        if process.poll() is not None:
            stderr = process.stderr.read() if process.stderr is not None else ""
            raise RuntimeError(f"semantic model host proxy exited early: {stderr}")
        time.sleep(0.05)
    process.terminate()
    raise RuntimeError("semantic model host proxy did not become ready")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serve-openrouter", action="store_true")
    parser.add_argument("--listen-host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--api-key-env", default="OPENROUTER_API_KEY")
    parser.add_argument("--upstream-base-url", default="https://openrouter.ai/api/v1")
    parser.add_argument("--expected-dummy-key", default="")
    args = parser.parse_args()
    if args.serve_openrouter:
        return serve(args)
    parser.error("--serve-openrouter is required")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
