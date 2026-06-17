from __future__ import annotations

import os
import subprocess
import sys
import time
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import contextforge_mcp_wrapper as wrapper
import diagnose_contextforge_wrappers as diagnostics


class ContextForgeMcpWrapperLifecycleTests(unittest.TestCase):
    def test_diagnostics_falls_back_to_wrapper_cmdline_server_name(self) -> None:
        cmdline = [
            "/home/dgk/workspace/context-portal/.venv/bin/python",
            "/home/dgk/workspace/context-portal/scripts/contextforge_mcp_wrapper.py",
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
        self.assertIn("if not email or not password:", source)

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
