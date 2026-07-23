from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
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

        self.assertIn("TARGET_PROFILE_KEYS", source)
        self.assertIn("CONTEXTFORGE_OPENCODE_WRAPPER_CONFIG_ENV", source)
        self.assertIn("CONTEXTFORGE_CODEX_WRAPPER_BASE_URL", source)
        self.assertIn("CONTEXTFORGE_PI_WRAPPER_TOKEN_CACHE", source)
        self.assertIn('CONTEXTFORGE_TOKEN_LOCK", f"{TOKEN_CACHE}.lock"', source)
        self.assertIn('env.get("CONTEXTFORGE_BEARER_TOKEN") or os.environ.get("CONTEXTFORGE_BEARER_TOKEN")', source)
        self.assertIn('env.get("CONTEXTFORGE_SERVER_ID")', source)
        self.assertIn("SCOPED_SERVER_TOKEN_PERMISSIONS", source)
        self.assertIn('"/tokens"', source)
        self.assertIn('"servers.use"', source)
        self.assertIn("refresh_email = None if scoped_token_id or env_bearer_token else email", source)
        self.assertIn("refresh_password = None if scoped_token_id or env_bearer_token else password", source)
        self.assertIn("if not email or not password:", source)

    def test_wrapper_selects_opencode_target_profile_atomically(self) -> None:
        env = os.environ.copy()
        target_keys = {
            *wrapper.GENERIC_TARGET_KEYS,
            *(key for keys in wrapper.TARGET_PROFILE_KEYS.values() for key in keys),
            "CONTEXTFORGE_TOKEN_LOCK",
        }
        for key in target_keys:
            env.pop(key, None)
        env.update(
            {
                "CONTEXTFORGE_OPENCODE_WRAPPER_CONFIG_ENV": "/run/opencode/contextforge.env",
                "CONTEXTFORGE_OPENCODE_WRAPPER_BASE_URL": "http://host.docker.internal:4445",
                "CONTEXTFORGE_OPENCODE_WRAPPER_TOKEN_CACHE": "/tmp/opencode-token.local.json",
                "CONTEXTFORGE_BASE_URL": "http://127.0.0.1:4444",
            }
        )
        code = (
            "import json,sys; "
            f"sys.path.insert(0, {str(REPO_ROOT / 'scripts')!r}); "
            "import contextforge_mcp_wrapper as w; "
            "print(json.dumps({'profile': w.TARGET_PROFILE, 'config': str(w.CONFIG_ENV), "
            "'base': w.GATEWAY_BASE, 'cache': str(w.TOKEN_CACHE), 'lock': str(w.TOKEN_LOCK), "
            "'base_source': w.GATEWAY_BASE_SOURCE}))"
        )

        result = subprocess.run(
            [sys.executable, "-c", code],
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )

        selected = json.loads(result.stdout)
        self.assertEqual("opencode", selected["profile"])
        self.assertEqual("/run/opencode/contextforge.env", selected["config"])
        self.assertEqual("http://host.docker.internal:4445", selected["base"])
        self.assertEqual("/tmp/opencode-token.local.json", selected["cache"])
        self.assertEqual("/tmp/opencode-token.local.json.lock", selected["lock"])
        self.assertEqual("CONTEXTFORGE_OPENCODE_WRAPPER_BASE_URL", selected["base_source"])

    def test_wrapper_rejects_partial_profile_instead_of_mixing_target_sources(self) -> None:
        env = os.environ.copy()
        for key in {
            *wrapper.GENERIC_TARGET_KEYS,
            *(key for keys in wrapper.TARGET_PROFILE_KEYS.values() for key in keys),
        }:
            env.pop(key, None)
        env.update(
            {
                "CONTEXTFORGE_OPENCODE_WRAPPER_CONFIG_ENV": "/run/opencode/contextforge.env",
                "CONTEXTFORGE_BASE_URL": "http://127.0.0.1:4444",
            }
        )
        code = (
            "import sys; "
            f"sys.path.insert(0, {str(REPO_ROOT / 'scripts')!r}); "
            "import contextforge_mcp_wrapper as w; print(w.TARGET_CONFIGURATION_ERROR)"
        )

        result = subprocess.run(
            [sys.executable, "-c", code],
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )

        self.assertIn("incomplete opencode ContextForge target profile", result.stdout)
        self.assertIn("CONTEXTFORGE_OPENCODE_WRAPPER_BASE_URL", result.stdout)

    def test_cached_token_is_bound_to_exact_contextforge_base_url(self) -> None:
        payload = wrapper.base64.urlsafe_b64encode(
            json.dumps({"exp": int(time.time()) + 3600}).encode()
        ).decode().rstrip("=")
        token = f"header.{payload}.signature"
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "run") as tmp:
            cache = Path(tmp) / "target-bound-token.local.json"
            with mock.patch.object(wrapper, "TOKEN_CACHE", cache), mock.patch.object(
                wrapper,
                "GATEWAY_BASE",
                "http://127.0.0.1:4445",
            ):
                wrapper._write_token_cache(token)
                self.assertEqual(token, wrapper._cached_token())
                with mock.patch.object(wrapper, "GATEWAY_BASE", "http://127.0.0.1:4444"):
                    self.assertIsNone(wrapper._cached_token())

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

    def test_bootstrap_error_includes_non_secret_contextforge_diagnostics(self) -> None:
        exc = urllib.error.HTTPError(
            url="http://127.0.0.1:4445/resources",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=None,
        )
        with mock.patch("sys.stderr") as stderr:
            wrapper._log_bootstrap_error(
                "context7_local_server",
                "wrapper_bootstrap_contextforge_api",
                exc,
            )

        written = "".join(str(call.args[0]) for call in stderr.write.call_args_list if call.args)
        payload = json.loads(written.strip())
        self.assertEqual("contextforge_wrapper_bootstrap_error", payload["event"])
        self.assertEqual("wrapper_bootstrap_contextforge_api", payload["stage"])
        self.assertEqual(401, payload["http_status"])
        self.assertEqual(wrapper.GATEWAY_BASE, payload["contextforge_base_url"])
        self.assertEqual(str(wrapper.CONFIG_ENV), payload["contextforge_config_env"])
        self.assertEqual(wrapper.CONFIG_ENV.exists(), payload["contextforge_config_env_exists"])
        self.assertEqual(str(wrapper.TOKEN_CACHE), payload["contextforge_token_cache"])
        self.assertNotIn("CONTEXTFORGE_BEARER_TOKEN", written)
        self.assertNotIn("Authorization", written)
        self.assertNotIn("Bearer", written)

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

    def test_signal_handler_records_reason_and_raises_controlled_exit(self) -> None:
        lifecycle = wrapper.WrapperLifecycle(
            server_name="context7_local_server",
            server_url="http://127.0.0.1:4445/servers/server-123/mcp/",
            parent_pid=os.getppid(),
            idle_timeout_seconds=300,
        )
        previous = wrapper._install_signal_cleanup_handlers(lifecycle)
        try:
            handler = signal.getsignal(signal.SIGTERM)
            self.assertTrue(callable(handler))
            with self.assertRaises(wrapper._WrapperSignalExit) as raised:
                assert callable(handler)
                handler(signal.SIGTERM, None)
        finally:
            wrapper._restore_signal_handlers(previous)

        self.assertEqual(143, raised.exception.code)
        self.assertEqual("signal_SIGTERM", lifecycle.stop_reason)
        self.assertEqual(143, lifecycle.exit_code)

    def test_main_revokes_scoped_token_after_controlled_signal_exit(self) -> None:
        def fake_run_stock(
            lifecycle: wrapper.WrapperLifecycle,
            refresh_email: str | None,
            refresh_password: str | None,
        ) -> int:
            self.assertIsNone(refresh_email)
            self.assertIsNone(refresh_password)
            lifecycle.stop_reason = "signal_SIGTERM"
            raise wrapper._WrapperSignalExit(143)

        environ = {
            "CONTEXTFORGE_BEARER_TOKEN": "",
            "CONTEXTFORGE_SERVER_ID": "",
        }
        with (
            mock.patch.object(sys, "argv", ["contextforge_mcp_wrapper.py", "context7_local_server"]),
            mock.patch.dict(os.environ, environ, clear=False),
            mock.patch.object(wrapper, "_token", return_value="admin-token"),
            mock.patch.object(
                wrapper,
                "_request",
                return_value={"items": [{"id": "server-123", "name": "context7_local_server"}]},
            ),
            mock.patch.object(
                wrapper,
                "_create_scoped_server_token",
                return_value=("tok-123", "scoped-access-token"),
            ),
            mock.patch.object(wrapper, "_run_stock_wrapper", side_effect=fake_run_stock),
            mock.patch.object(wrapper, "_revoke_scoped_server_token") as revoke,
        ):
            self.assertEqual(143, wrapper.main())

        revoke.assert_called_once_with("admin-token", "tok-123")

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

    def test_wrapper_can_read_scoped_bearer_token_from_config_file(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "run") as tmp:
            config_env = Path(tmp) / "contextforge-client-scoped.env"
            config_env.write_text(
                "CONTEXTFORGE_BEARER_TOKEN=Bearer scoped-token\n"
                "CONTEXTFORGE_SERVER_ID=server-123\n",
                encoding="utf-8",
            )
            env = os.environ.copy()
            env["CONTEXTFORGE_CONFIG_ENV"] = str(config_env)
            env.pop("CONTEXTFORGE_BEARER_TOKEN", None)
            env.pop("CONTEXTFORGE_SERVER_ID", None)
            code = (
                "import sys; "
                f"sys.path.insert(0, {str(REPO_ROOT / 'scripts')!r}); "
                "import contextforge_mcp_wrapper as w; "
                "env = w._read_env(w.CONFIG_ENV); "
                "print(w._token(None, None, env.get('CONTEXTFORGE_BEARER_TOKEN'))); "
                "print((__import__('os').environ.get('CONTEXTFORGE_SERVER_ID') or env.get('CONTEXTFORGE_SERVER_ID') or '').strip())"
            )

            result = subprocess.run(
                [sys.executable, "-c", code],
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )

        self.assertEqual(["scoped-token", "server-123"], result.stdout.strip().splitlines())

if __name__ == "__main__":
    unittest.main()
