from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import control_plane_auth_wrappers as wrappers


RAW_TOKEN = "fixture-wrapper-token-material"


def safe_leak_evidence() -> dict[str, Any]:
    return {
        "argv": ["python", "-m", "mcpgateway.translate", "--token-file", "/ignored/contextforge-token"],
        "process_title_snapshot": "python -m mcpgateway.translate --token-file <redacted>",
        "stdout": "ready",
        "stderr": "",
        "shell_trace": "set +x",
        "wrapper_logs": [{"level": "info", "message": "wrapper started"}],
        "diagnostics": {"token_source_class": "restrictive_local_token_file", "path_class": "ignored_local_secret_file"},
        "audit_excerpts": [{"event": "wrapper_started", "redaction_status": "passed"}],
        "project_state": {"auth": {"material": "redacted", "token_source_class": "restrictive_local_token_file"}},
        "catalog_output": {"auth": {"token_source": "restrictive_local_token_file"}},
        "child_environment_snapshot": {"PATH": "/usr/bin", "CONTEXTFORGE_TOKEN": "<redacted>"},
    }


def local_file_source(**overrides: Any) -> dict[str, Any]:
    source = {
        "class": "restrictive_local_token_file",
        "source_id": "local-assistant",
        "path_class": "ignored_local_secret_file",
        "storage_class": "local_file",
        "ignored_by_vcs": True,
        "owner_matches_current_user": True,
        "mode": "0600",
        "cached_token_state": "fresh",
        "token_profile": "loopback_authenticated_http",
    }
    source.update(overrides)
    return source


class ControlPlaneAuthWrapperTests(unittest.TestCase):
    def test_safe_local_token_file_provider_and_broker_sources_pass(self) -> None:
        safe_sources = [
            local_file_source(),
            {
                "class": "contextforge_token_provider_api",
                "source_id": "contextforge-provider",
                "provider_class": "contextforge",
                "endpoint_class": "loopback_authenticated_http",
                "cached_token_state": "fresh",
            },
            {
                "class": "wrapper_bound_brokered_token",
                "source_id": "claude-wrapper-broker",
                "wrapper_bound": True,
                "brokered": True,
                "ephemeral": True,
                "cached_token_state": "fresh",
            },
        ]
        for source in safe_sources:
            with self.subTest(source=source["class"]):
                result = wrappers.evaluate_wrapper_auth_security(
                    token_source=source,
                    wrapper_command={"argv": ["python", "-m", "mcpgateway.translate", "--token-file", "/ignored/contextforge-token"]},
                    leak_evidence=safe_leak_evidence(),
                    raw_token_markers=[RAW_TOKEN],
                )

                self.assertEqual("allow_wrapper_auth_evidence", result["decision"])
                self.assertEqual("passed", result["status"])
                self.assertEqual("passed", result["redaction_status"])
                self.assertIn("did_not_run_wrapper", result["non_actions"])
                encoded = json.dumps(result, sort_keys=True)
                self.assertNotIn(RAW_TOKEN, encoded)

    def test_wrapper_command_snapshot_redacts_token_values_and_blocks_argv_leak(self) -> None:
        result = wrappers.evaluate_wrapper_auth_security(
            token_source=local_file_source(),
            wrapper_command={"argv": ["wrapper", "--authorization", f"Bearer {RAW_TOKEN}"]},
            leak_evidence=safe_leak_evidence(),
            raw_token_markers=[RAW_TOKEN],
        )

        self.assertEqual("block_wrapper_auth_evidence", result["decision"])
        blockers = {blocker["name"] for blocker in result["blockers"]}
        self.assertIn("wrapper_command_snapshot_safe", blockers)
        encoded = json.dumps(result["wrapper_command_snapshot"], sort_keys=True)
        self.assertNotIn(RAW_TOKEN, encoded)
        self.assertNotIn("Bearer ", encoded)

    def test_leak_checks_reject_env_logs_diagnostics_audit_project_catalog_and_child_env(self) -> None:
        leaking_evidence = safe_leak_evidence()
        leaking_evidence.update(
            {
                "argv": ["wrapper", "--token", RAW_TOKEN],
                "process_title_snapshot": f"wrapper auth-marker {RAW_TOKEN}",
                "stdout": f"Bearer {RAW_TOKEN}",
                "stderr": f"auth-marker {RAW_TOKEN}",
                "shell_trace": f"+ CONTEXTFORGE_AUTH_MARKER {RAW_TOKEN}",
                "wrapper_logs": [{"message": f"auth-marker {RAW_TOKEN}"}],
                "diagnostics": {"auth_token": RAW_TOKEN},
                "audit_excerpts": [{"request": {"Authorization": f"Bearer {RAW_TOKEN}"}}],
                "project_state": {"token": RAW_TOKEN},
                "catalog_output": {"api_key": RAW_TOKEN},
                "child_environment_snapshot": {"CONTEXTFORGE_TOKEN": RAW_TOKEN},
            }
        )

        result = wrappers.evaluate_wrapper_leak_checks(leaking_evidence, raw_token_markers=[RAW_TOKEN])

        self.assertEqual("block_wrapper_leak_checks", result["decision"])
        failed = {check["name"] for check in result["checks"] if check["status"] == "failed"}
        self.assertEqual(
            {
                "argv_leak_check",
                "process_title_snapshot_leak_check",
                "stdout_leak_check",
                "stderr_leak_check",
                "shell_trace_leak_check",
                "wrapper_logs_leak_check",
                "diagnostics_leak_check",
                "audit_excerpts_leak_check",
                "project_state_leak_check",
                "catalog_output_leak_check",
                "child_environment_snapshot_leak_check",
            },
            failed,
        )
        self.assertGreaterEqual(len(result["findings"]), len(failed))
        self.assertNotIn(RAW_TOKEN, json.dumps(result, sort_keys=True))

    def test_missing_required_leak_surfaces_fail_closed(self) -> None:
        result = wrappers.evaluate_wrapper_auth_security(
            token_source=local_file_source(),
            wrapper_command={"argv": ["python", "-m", "mcpgateway.translate"]},
            leak_evidence={},
            raw_token_markers=[RAW_TOKEN],
        )

        self.assertEqual("block_wrapper_auth_evidence", result["decision"])
        missing = {check["name"] for check in result["leak_checks"]["checks"] if check["status"] == "failed"}
        self.assertEqual({f"{surface}_leak_check" for surface in wrappers.LEAK_SURFACES}, missing)

    def test_world_readable_token_file_mode_fails_closed(self) -> None:
        result = wrappers.evaluate_token_source(local_file_source(mode="0644"))

        self.assertEqual("block_token_source", result["decision"])
        checks = {check["name"]: check for check in result["checks"]}
        self.assertEqual("failed", checks["local_token_file_mode"]["status"])
        self.assertIn("0600", checks["local_token_file_mode"]["reason"])

    def test_revoked_or_stale_cached_token_blocks_source(self) -> None:
        for state in ["revoked", "stale"]:
            with self.subTest(state=state):
                result = wrappers.evaluate_token_source(local_file_source(cached_token_state=state))

                self.assertEqual("block_token_source", result["decision"])
                checks = {check["name"]: check for check in result["checks"]}
                self.assertEqual("failed", checks["cached_token_not_revoked_or_stale"]["status"])

    def test_local_shared_token_reused_for_remote_binding_blocks(self) -> None:
        result = wrappers.evaluate_token_source(
            local_file_source(**{"reuses_local_shared_token": True}),
            binding_scope="remote",
        )

        self.assertEqual("block_token_source", result["decision"])
        checks = {check["name"]: check for check in result["checks"]}
        self.assertEqual("failed", checks["remote_binding_token_separation"]["status"])

    def test_approved_remote_token_store_passes_remote_binding(self) -> None:
        result = wrappers.evaluate_token_source(
            {
                "class": "approved_remote_token_store",
                "source_id": "remote-store",
                "approved": True,
                "separate_remote_token": True,
                "revocation_profile": "remote_separate",
                "cached_token_state": "fresh",
                "token_profile": "remote_ready",
            },
            binding_scope="remote",
        )

        self.assertEqual("allow_token_source", result["decision"])
        checks = {check["name"]: check for check in result["checks"]}
        self.assertEqual("passed", checks["remote_binding_token_separation"]["status"])

    def test_long_lived_inherited_environment_fails_closed(self) -> None:
        result = wrappers.evaluate_token_source(
            {
                "class": "inherited_environment",
                "source_id": "env-token",
                "long_lived": True,
                "rfc_approved": False,
            }
        )

        self.assertEqual("block_token_source", result["decision"])
        self.assertEqual("failed", result["checks"][0]["status"])

    def test_rfc_approved_non_long_lived_environment_exception_can_be_modeled(self) -> None:
        result = wrappers.evaluate_token_source(
            {
                "class": "inherited_environment",
                "source_id": "env-token",
                "long_lived": False,
                "rfc_approved": True,
                "leak_probes_passed": True,
                "cached_token_state": "fresh",
            }
        )

        self.assertEqual("allow_token_source", result["decision"])
        checks = {check["name"]: check for check in result["checks"]}
        self.assertEqual("passed", checks["token_source_class_allowed"]["status"])


if __name__ == "__main__":
    unittest.main()
