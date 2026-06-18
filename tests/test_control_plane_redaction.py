from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import control_plane_redaction as redaction


FIXTURE_PATH = REPO_ROOT / "tests/fixtures/control_plane_diagnostics.json"


class ControlPlaneRedactionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def test_sensitive_key_classification(self) -> None:
        cases = {
            "api_key": "api_key",
            "Authorization": "bearer_token",
            "refresh-token": "token",
            "clientSecret": "secret",
            "DOWNSTREAM_PASSWORD": "password",
            "private_key_pem": "private_key",
            "credential_scope": "credential",
            "service_name": None,
        }
        for key, expected in cases.items():
            with self.subTest(key=key):
                self.assertEqual(expected, redaction.classify_sensitive_key(key))

    def test_nested_redaction_preserves_non_secret_structure(self) -> None:
        payload = {
            "service": {
                "name": "github",
                "api_key": "fixture nested credential value",
                "limits": {"requests_per_minute": 60},
                "headers": {"Authorization": "Bearer <placeholder>"},
            },
            "notes": ["visible diagnostic note"],
        }
        result = redaction.redact_with_report(payload)
        self.assertEqual("github", result.data["service"]["name"])
        self.assertEqual(60, result.data["service"]["limits"]["requests_per_minute"])
        self.assertEqual(["visible diagnostic note"], result.data["notes"])
        self.assertTrue(result.data["service"]["api_key"]["redacted"])
        self.assertTrue(result.data["service"]["headers"]["Authorization"]["redacted"])
        self.assertEqual("api_key", result.data["service"]["api_key"]["classification"])
        self.assertEqual("bearer_token", result.data["service"]["headers"]["Authorization"]["classification"])
        self.assertGreaterEqual(len(result.events), 2)
        redaction.assert_no_sensitive_raw_values(
            result.data,
            raw_values=["fixture nested credential value", "Bearer <placeholder>"],
        )

    def test_env_summary_redacts_all_raw_env_values(self) -> None:
        summary = redaction.redact_env_summary(
            {
                "CONTEXTFORGE_TOKEN": "fixture env auth material",
                "PLAIN_SETTING": "fixture env plain value",
            },
            source_path="config/contextforge.env",
        )
        self.assertEqual("redacted", summary["redaction_status"])
        self.assertEqual(2, summary["variable_count"])
        self.assertEqual("token", summary["variables"]["CONTEXTFORGE_TOKEN"]["classification"])
        self.assertEqual("env_value", summary["variables"]["PLAIN_SETTING"]["classification"])
        self.assertEqual("config/contextforge.env", summary["variables"]["PLAIN_SETTING"]["source_path"])
        redaction.assert_no_sensitive_raw_values(
            summary,
            raw_values=["fixture env auth material", "fixture env plain value"],
        )

    def test_fixture_diagnostic_bundle_shape(self) -> None:
        fixture_input = self.fixture["input"]
        expected = self.fixture["expected_redacted_shape"]
        bundle = redaction.build_diagnostic_bundle(
            source=self.fixture["source"],
            catalog=fixture_input["catalog"],
            env=fixture_input["env"],
            tokens=fixture_input["tokens"],
            audit=fixture_input["audit"],
            traces=fixture_input["traces"],
            metadata=fixture_input["metadata"],
            generated_at=self.fixture["generated_at"],
            raw_values=expected["raw_values_absent"],
        )

        self.assertEqual(redaction.SCHEMA_URI, bundle["schema_uri"])
        self.assertEqual(expected["redaction_status"], bundle["redaction_status"])
        self.assertEqual(expected["sections"], sorted(bundle["sections"].keys()))
        self.assertEqual(expected["env_variable_count"], bundle["sections"]["env"]["variable_count"])
        self.assertEqual(
            expected["preserved_catalog_service"],
            bundle["sections"]["catalog"]["services"][0]["canonical_name"],
        )
        self.assertEqual(expected["preserved_audit_actor"], bundle["sections"]["audit"]["actor"])
        self.assertEqual(
            expected["catalog_secret_classification"],
            bundle["sections"]["catalog"]["services"][0]["auth"]["api_key"]["classification"],
        )
        downstream_credentials = bundle["sections"]["catalog"]["services"][0]["auth"]["downstream_credentials"]
        self.assertEqual(expected["catalog_downstream_credentials_classification"], downstream_credentials["classification"])
        self.assertEqual(["password"], downstream_credentials["shape"]["keys"])
        self.assertEqual(
            expected["token_path_classification"],
            bundle["sections"]["tokens"]["local_client"]["token_path"]["classification"],
        )
        self.assertEqual("ignored local file", bundle["sections"]["tokens"]["local_client"]["token_source"])
        self.assertEqual(
            expected["audit_authorization_classification"],
            bundle["sections"]["audit"]["request_headers"]["Authorization"]["classification"],
        )
        self.assertEqual(
            expected["trace_auth_token_classification"],
            bundle["sections"]["traces"]["probe_events"][0]["auth_token"]["classification"],
        )
        self.assertGreaterEqual(bundle["redaction"]["redacted_value_count"], 8)
        redaction.assert_no_sensitive_raw_values(bundle, raw_values=expected["raw_values_absent"])

    def test_failure_diagnostics_bundle_is_compact_and_redacted(self) -> None:
        fixture = self.fixture["failure_diagnostics"]
        expected = fixture["expected"]
        bundle = redaction.build_failure_diagnostics_bundle(
            workflow=fixture["workflow"],
            service_slug=fixture["service_slug"],
            canonical_service_identity=fixture["canonical_service_identity"],
            registry_id=fixture["registry_id"],
            virtual_server_id=fixture["virtual_server_id"],
            transport_path=fixture["transport_path"],
            bridge_or_transceiver_reason=fixture["bridge_or_transceiver_reason"],
            client_visibility_target=fixture["client_visibility_target"],
            last_probe=fixture["last_probe"],
            failing_call_shape=fixture["failing_call_shape"],
            failure_summary=fixture["failure_summary"],
            next_safe_diagnostic_action=fixture["next_safe_diagnostic_action"],
            generated_at=self.fixture["generated_at"],
            raw_values=expected["raw_values_absent"],
        )

        self.assertEqual(expected["schema_uri"], bundle["schema_uri"])
        self.assertEqual(expected["workflow"], bundle["workflow"])
        self.assertEqual(expected["redaction_status"], bundle["redaction_status"])
        self.assertEqual(fixture["service_slug"], bundle["service"]["service_slug"])
        self.assertEqual(fixture["canonical_service_identity"], bundle["service"]["canonical_service_identity"])
        self.assertEqual(fixture["registry_id"], bundle["service"]["registry_id"])
        self.assertEqual(fixture["virtual_server_id"], bundle["service"]["virtual_server_id"])
        self.assertEqual(fixture["transport_path"], bundle["transport"]["path"])
        self.assertEqual(fixture["bridge_or_transceiver_reason"], bundle["transport"]["bridge_or_transceiver_reason"])
        self.assertEqual(fixture["client_visibility_target"], bundle["client_visibility"]["target"])
        self.assertIn(bundle["client_visibility"]["target"], {"pi", "opencode"})
        self.assertEqual(fixture["next_safe_diagnostic_action"], bundle["next_safe_diagnostic_action"])
        self.assertEqual("failed", bundle["last_probe"]["result"])
        self.assertEqual("tools/call", bundle["failing_call_shape"]["method"])
        self.assertEqual("requests", bundle["failing_call_shape"]["arguments"]["libraryName"])
        self.assertEqual("bearer_token", bundle["failing_call_shape"]["headers"]["Authorization"]["classification"])
        self.assertEqual("explicit_raw_value", bundle["failing_call_shape"]["url"]["classification"])
        self.assertEqual("password", bundle["failing_call_shape"]["arguments"]["password"]["classification"])
        self.assertEqual("secret", bundle["failure_summary"]["client_secret"]["classification"])
        self.assertGreaterEqual(bundle["redaction"]["redacted_value_count"], expected["redacted_value_count"])
        redaction.assert_no_sensitive_raw_values(bundle, raw_values=expected["raw_values_absent"])

    def test_failure_diagnostics_validates_workflow_and_required_context(self) -> None:
        fixture = self.fixture["failure_diagnostics"]
        bundle = redaction.build_failure_diagnostics_bundle(
            workflow="project activation",
            service_slug=fixture["service_slug"],
            canonical_service_identity=fixture["canonical_service_identity"],
            transport_path=fixture["transport_path"],
            bridge_or_transceiver_reason=fixture["bridge_or_transceiver_reason"],
            client_visibility_target=fixture["client_visibility_target"],
            last_probe=fixture["last_probe"],
            failing_call_shape=fixture["failing_call_shape"],
            next_safe_diagnostic_action=fixture["next_safe_diagnostic_action"],
            raw_values=fixture["expected"]["raw_values_absent"],
        )

        self.assertEqual("activation", bundle["workflow"])
        self.assertIsNone(bundle["service"]["registry_id"])
        self.assertIsNone(bundle["service"]["virtual_server_id"])
        with self.assertRaises(ValueError):
            redaction.build_failure_diagnostics_bundle(
                workflow="delete",
                service_slug=fixture["service_slug"],
                canonical_service_identity=fixture["canonical_service_identity"],
                transport_path=fixture["transport_path"],
                bridge_or_transceiver_reason=fixture["bridge_or_transceiver_reason"],
                client_visibility_target=fixture["client_visibility_target"],
                last_probe=fixture["last_probe"],
                failing_call_shape=fixture["failing_call_shape"],
                next_safe_diagnostic_action=fixture["next_safe_diagnostic_action"],
            )
        with self.assertRaises(ValueError):
            redaction.build_failure_diagnostics_bundle(
                workflow="repair",
                service_slug="",
                canonical_service_identity=fixture["canonical_service_identity"],
                transport_path=fixture["transport_path"],
                bridge_or_transceiver_reason=fixture["bridge_or_transceiver_reason"],
                client_visibility_target=fixture["client_visibility_target"],
                last_probe=fixture["last_probe"],
                failing_call_shape=fixture["failing_call_shape"],
                next_safe_diagnostic_action=fixture["next_safe_diagnostic_action"],
            )

    def test_assert_no_sensitive_raw_values_detects_leaks(self) -> None:
        with self.assertRaises(redaction.RedactionLeakError):
            redaction.assert_no_sensitive_raw_values(
                {"safe": "fixture raw value still present"},
                raw_values=["fixture raw value"],
            )
        with self.assertRaises(redaction.RedactionLeakError):
            redaction.assert_no_sensitive_raw_values({"stdout": "Bearer <placeholder>"})


if __name__ == "__main__":
    unittest.main()
