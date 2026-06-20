from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import unittest
from unittest import mock
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import contextforge_mcp_wrapper as wrapper
import diagnose_contextforge_wrappers as diagnostics


class ContextForgeMcpWrapperLifecycleTests(unittest.TestCase):
    def test_diagnostics_falls_back_to_wrapper_cmdline_server_name(self) -> None:
        cmdline = [
            "/home/dgk/workspace/legacy-controlplane-archive/.venv/bin/python",
            "/home/dgk/workspace/legacy-controlplane-archive/scripts/contextforge_mcp_wrapper.py",
            "mentality_server",
        ]

        self.assertEqual("mentality_server", diagnostics._wrapper_server_name_from_cmdline(cmdline))

    def test_idle_buffer_returns_eof_after_timeout_with_reason(self) -> None:
        read_fd, write_fd = os.pipe()
        try:
            with os.fdopen(read_fd, "rb", buffering=0) as read_handle:
                lifecycle = wrapper.WrapperLifecycle(
                    server_name="mentality_server",
                    server_url="http://127.0.0.1:4444/servers/test/mcp/",
                    parent_pid=os.getppid(),
                    idle_timeout_seconds=0.05,
                )
                buffer = wrapper._LifecycleStdinBuffer(read_handle, lifecycle)

                started = time.monotonic()
                self.assertEqual(b"", buffer.readline())

            self.assertLess(time.monotonic() - started, 1.0)
            self.assertEqual("idle_timeout", lifecycle.stop_reason)
        finally:
            os.close(write_fd)

    def test_partial_stdin_line_times_out_without_blocking_readline(self) -> None:
        read_fd, write_fd = os.pipe()
        try:
            os.write(write_fd, b'{"jsonrpc":"2.0"')
            with os.fdopen(read_fd, "rb", buffering=0) as read_handle:
                lifecycle = wrapper.WrapperLifecycle(
                    server_name="mentality_server",
                    server_url="http://127.0.0.1:4444/servers/test/mcp/",
                    parent_pid=os.getppid(),
                    idle_timeout_seconds=0.05,
                )
                buffer = wrapper._LifecycleStdinBuffer(read_handle, lifecycle)

                started = time.monotonic()
                self.assertEqual(b"", buffer.readline())

            self.assertLess(time.monotonic() - started, 1.0)
            self.assertEqual("idle_timeout", lifecycle.stop_reason)
        finally:
            os.close(write_fd)

    def test_wrapper_supports_dev_harness_env_overrides(self) -> None:
        source = (REPO_ROOT / "scripts" / "contextforge_mcp_wrapper.py").read_text(encoding="utf-8")

        self.assertIn('CONTEXTFORGE_CONFIG_ENV", REPO_ROOT / "config" / "contextforge.env"', source)
        self.assertIn('CONTEXTFORGE_TOKEN_CACHE", REPO_ROOT / "run" / "contextforge-wrapper-token.local.json"', source)
        self.assertIn('CONTEXTFORGE_TOKEN_LOCK", f"{TOKEN_CACHE}.lock"', source)
        self.assertIn('os.environ.get("CONTEXTFORGE_BEARER_TOKEN")', source)
        self.assertIn('os.environ.get("CONTEXTFORGE_SERVER_ID", "").strip()', source)
        self.assertIn("SCOPED_SERVER_TOKEN_PERMISSIONS", source)
        self.assertIn('"/tokens"', source)
        self.assertIn('"servers.use"', source)
        self.assertIn("refresh_email = None if scoped_token_id else email", source)
        self.assertIn("refresh_password = None if scoped_token_id else password", source)
        self.assertIn("if not email or not password:", source)

    def test_wrapper_scoped_server_token_create_and_revoke_use_catalog_api(self) -> None:
        calls: list[dict[str, object]] = []

        def fake_request(method: str, path: str, *, token: str | None = None, body: dict | None = None):
            calls.append({"method": method, "path": path, "token": token, "body": body})
            if method == "POST":
                return {"token": {"id": "tok-123"}, "access_token": "scoped-token"}
            return None

        with mock.patch.object(wrapper, "_request", side_effect=fake_request):
            token_id, access_token = wrapper._create_scoped_server_token("admin-token", "server-123", "context7_local_server")
            wrapper._revoke_scoped_server_token("admin-token", token_id)

        self.assertEqual("tok-123", token_id)
        self.assertEqual("scoped-token", access_token)
        self.assertEqual("POST", calls[0]["method"])
        self.assertEqual("/tokens", calls[0]["path"])
        self.assertEqual("admin-token", calls[0]["token"])
        body = calls[0]["body"]
        assert isinstance(body, dict)
        self.assertEqual("server-123", body["scope"]["server_id"])
        self.assertIn("servers.use", body["scope"]["permissions"])
        self.assertEqual("DELETE", calls[1]["method"])
        self.assertEqual("/tokens/tok-123", calls[1]["path"])

    def test_scoped_token_creation_event_does_not_log_access_token(self) -> None:
        with mock.patch("sys.stderr") as stderr:
            wrapper._log_bootstrap_event(
                "context7_local_server",
                "contextforge_wrapper_scoped_token_created",
                server_id="server-123",
                token_id="tok-123",
                permissions=wrapper.SCOPED_SERVER_TOKEN_PERMISSIONS,
            )

        written = "".join(str(call.args[0]) for call in stderr.write.call_args_list if call.args)
        payload = json.loads(written.strip())
        self.assertEqual("contextforge_wrapper_scoped_token_created", payload["event"])
        self.assertEqual("server-123", payload["server_id"])
        self.assertEqual("tok-123", payload["token_id"])
        self.assertIn("servers.use", payload["permissions"])
        self.assertNotIn("access_token", payload)
        self.assertNotIn("Bearer", written)

    def test_wrapper_can_bootstrap_with_bearer_token_without_env_file(self) -> None:
        env = os.environ.copy()
        env["CONTEXTFORGE_CONFIG_ENV"] = str(REPO_ROOT / "run" / "missing-dev-contextforge.env")
        env["CONTEXTFORGE_TOKEN_CACHE"] = str(REPO_ROOT / "run" / "test-wrapper-token-cache.local.json")
        env["CONTEXTFORGE_BEARER_TOKEN"] = "Bearer test-token"
        code = (
            "import sys; "
            f"sys.path.insert(0, {str(REPO_ROOT / 'scripts')!r}); "
            "import contextforge_mcp_wrapper as w; "
            "print(w.CONFIG_ENV); print(w.TOKEN_CACHE); print(w.TOKEN_LOCK); print(w._token(None, None))"
        )

        result = subprocess.run(
            [sys.executable, "-c", code],
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )

        lines = result.stdout.strip().splitlines()
        self.assertEqual(env["CONTEXTFORGE_CONFIG_ENV"], lines[0])
        self.assertEqual(env["CONTEXTFORGE_TOKEN_CACHE"], lines[1])
        self.assertEqual(f"{env['CONTEXTFORGE_TOKEN_CACHE']}.lock", lines[2])
        self.assertEqual("test-token", lines[3])

if __name__ == "__main__":
    unittest.main()
