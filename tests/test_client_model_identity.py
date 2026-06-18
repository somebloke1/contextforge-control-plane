from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "client_model_identity.py"

spec = importlib.util.spec_from_file_location("client_model_identity", SCRIPT)
assert spec is not None
client_model_identity = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = client_model_identity
spec.loader.exec_module(client_model_identity)


class ClientModelIdentityTests(unittest.TestCase):
    def test_extracts_openai_compatible_model_ids(self) -> None:
        payload = {
            "object": "list",
            "data": [
                {"id": "qwen3.6-a3b", "object": "model"},
                {"id": "other-model", "object": "model"},
            ],
        }

        self.assertEqual(
            ["other-model", "qwen3.6-a3b"],
            client_model_identity.advertised_model_ids(payload),
        )

    def test_current_report_requires_exact_expected_model_id(self) -> None:
        report = client_model_identity.build_identity_report(
            expected_model_id="qwen3.6-a3b",
            payload={"data": [{"id": "qwen3.6-a3b"}]},
            surface="Pi client Docker",
            client="pi",
            base_url="http://host.docker.internal:8742/v1",
        )

        self.assertEqual("current", report["status"])
        self.assertTrue(report["exact_match"])
        self.assertEqual(["qwen3.6-a3b"], report["advertised_model_ids"])
        self.assertIn("no model server install", report["non_actions"])

    def test_nearby_alias_is_stale_not_current(self) -> None:
        report = client_model_identity.build_identity_report(
            expected_model_id="qwen3.6-a3b",
            payload={"data": [{"id": "qwen3.6-a3b-q4"}]},
            surface="OpenCode client Docker",
            client="opencode",
        )

        self.assertEqual("stale", report["status"])
        self.assertFalse(report["exact_match"])
        self.assertEqual(["qwen3.6-a3b-q4"], report["advertised_model_ids"])

    def test_cli_exits_nonzero_on_stale_when_requested(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--expected-model-id",
                "qwen3.6-a3b",
                "--surface",
                "Pi client Docker",
                "--client",
                "pi",
                "--fail-on-stale",
            ],
            input=json.dumps({"data": [{"id": "qwen3.6-a3b-q4"}]}),
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(2, result.returncode)
        self.assertIn('"status": "stale"', result.stdout)


if __name__ == "__main__":
    unittest.main()
