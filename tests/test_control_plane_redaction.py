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
